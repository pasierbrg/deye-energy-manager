"""Local deterministic optimizer for the 48-hour Deye energy plan.

The module is intentionally independent from Home Assistant and from the
physical Deye write layer.  It accepts a plain input snapshot and returns only
finite, serializable proposals.  Applying a proposal is a separate, explicit
operation handled by the existing, guarded manager transaction.
"""

from __future__ import annotations

import contextvars
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from .const import DEFAULT_INVERTER_MAX_POWER_W
except ImportError:
    DEFAULT_INVERTER_MAX_POWER_W = 13000


ALGORITHM_VERSION = "0.8.0-local-optimizer-3"
PLAN_SCHEMA_VERSION = 6
HISTORY_SCHEMA_VERSION = 4
MAX_BUNDLE_BUILD_PLAN_CALLS = 64
MAX_BUNDLE_SOLVER_PASSES = 512
MAX_BUNDLE_SIMULATIONS = 640
DEFAULT_PRICE_EQUIVALENCE_BAND = 0.05
DEFAULT_MINIMUM_AUTO_SELL_POWER_W = 1000.0


class CoreOperationBudgetExceeded(RuntimeError):
    """Raised internally when one deterministic bundle budget is exhausted."""


class _CoreOperationBudget:
    def __init__(self) -> None:
        self.limits = {
            "build_energy_plan_calls": MAX_BUNDLE_BUILD_PLAN_CALLS,
            "solver_passes": MAX_BUNDLE_SOLVER_PASSES,
            "simulate_calls": MAX_BUNDLE_SIMULATIONS,
        }
        self.usage = {key: 0 for key in self.limits}

    def consume(self, key: str) -> None:
        self.usage[key] += 1
        if self.usage[key] > self.limits[key]:
            raise CoreOperationBudgetExceeded(f"{key}:{self.usage[key]}>{self.limits[key]}")

    def public(self) -> dict[str, Any]:
        return {
            "kind": "deterministic_operation_budget",
            "limits": dict(self.limits),
            "usage": dict(self.usage),
        }


_ACTIVE_CORE_BUDGET: contextvars.ContextVar[_CoreOperationBudget | None] = (
    contextvars.ContextVar("deye_optimizer_core_budget", default=None)
)
STRATEGIES = {
    "safe": {
        "reserve_buffer_pct": 8.0,
        "power_limit_pct": 65.0,
        "minimum_profit_threshold": 0.30,
        "forecast_quantile": "low",
        "terminal_soc_target": 55.0,
    },
    "balanced": {
        "reserve_buffer_pct": 0.0,
        "power_limit_pct": 100.0,
        "minimum_profit_threshold": 0.20,
        "forecast_quantile": "mid",
        "terminal_soc_target": 45.0,
    },
    "profit": {
        "reserve_buffer_pct": 0.0,
        "power_limit_pct": 100.0,
        "minimum_profit_threshold": 0.20,
        "forecast_quantile": "high",
        "terminal_soc_target": 30.0,
    },
}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _optional(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def quantize_power_w(
    value_w: Any,
    *,
    step_w: Any,
    minimum_w: Any = 0.0,
    maximum_w: Any = None,
) -> float:
    """Floor automatic power to one physical number-entity lattice.

    The origin of the lattice is the entity minimum, matching Home Assistant's
    number validation.  Automatic control deliberately floors instead of using
    nearest-step rounding so quantization can never cross an already evaluated
    physical, profile or configured hard cap.
    """
    value = _optional(value_w)
    step = _optional(step_w)
    minimum = _optional(minimum_w)
    maximum = _optional(maximum_w)
    if value is None or value <= 0:
        return 0.0
    minimum = max(0.0, minimum if minimum is not None else 0.0)
    if maximum is not None:
        maximum = max(0.0, maximum)
        value = min(value, maximum)
    if value < minimum:
        return 0.0
    if step is None or step <= 0:
        return value
    # The tiny relative epsilon only neutralizes binary representation error at
    # an exact lattice point; it is far too small to change half-step policy.
    units = math.floor((value - minimum) / step + 1e-12)
    quantized = minimum + units * step
    if maximum is not None and quantized > maximum:
        units = math.floor((maximum - minimum) / step + 1e-12)
        quantized = minimum + max(0, units) * step
    result = round(max(0.0, quantized), 9)
    return int(round(result)) if math.isclose(result, round(result), abs_tol=1e-9) else result


def _price_equivalence_band(inputs: dict[str, Any]) -> float:
    """Return the single bounded raw sell-price equivalence threshold."""
    return max(
        0.0,
        _finite(
            inputs.get("price_equivalence_band"),
            DEFAULT_PRICE_EQUIVALENCE_BAND,
        ),
    )


def _minimum_automatic_sell_power_w(
    inputs: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> float:
    """Return the writable automatic Sell threshold on the physical lattice.

    Required profiles may use the inverter's physical minimum to finish their
    explicit target. Manager always supplies the canonical product setting
    (default 1000 W) for preferred and autonomous proposals. A missing key is
    treated as the legacy direct-Core contract and keeps the physical minimum;
    this prevents a silent behaviour change for external/test callers that do
    not pass the Manager settings snapshot.
    """
    physical_minimum = max(0.0, _finite(inputs.get("sell_power_minimum_w"), 0.0))
    if isinstance(request, dict) and bool(request.get("required")):
        configured = physical_minimum
    else:
        configured = max(
            physical_minimum,
            _finite(inputs.get("minimum_auto_sell_power_w"), physical_minimum),
        )
    step = max(0.0, _finite(inputs.get("sell_power_step_w"), 1.0))
    if step <= 0 or configured <= physical_minimum:
        return configured
    units = math.ceil((configured - physical_minimum) / step - 1e-12)
    return round(physical_minimum + max(0, units) * step, 9)


def _price_equivalence_groups(
    ordered: list[tuple[int, dict[str, Any], float]],
    band: float,
) -> list[list[tuple[int, dict[str, Any], float]]]:
    """Group adjacent ranked slots against the best value in each group."""
    if band <= 0:
        return [[item] for item in ordered]
    groups: list[list[tuple[int, dict[str, Any], float]]] = []
    for item in ordered:
        if not groups or abs(groups[-1][0][2] - item[2]) > band + 1e-9:
            groups.append([item])
        else:
            groups[-1].append(item)
    return groups


def _waterfill_group(
    group: list[tuple[int, dict[str, Any], float]],
    capacities: dict[int, float],
    target_kwh: float,
    inputs: dict[str, Any],
) -> dict[int, float]:
    """Minimize peak power in the smallest useful ranked subset of a group."""
    remaining_target = max(0.0, target_kwh)
    selected: list[tuple[int, dict[str, Any], float]] = []
    selected_capacity = 0.0
    for item in group:
        selected.append(item)
        selected_capacity += max(0.0, capacities.get(item[0], 0.0))
        if selected_capacity + 1e-9 >= remaining_target:
            break
    if not selected or remaining_target <= 1e-9:
        return {}

    allocations: dict[int, float] = {item[0]: 0.0 for item in selected}
    active = list(selected)
    remaining = min(remaining_target, selected_capacity)
    while active and remaining > 1e-9:
        hours = {
            item[0]: max(1e-9, _slot_capacity_hours(inputs, item[0]))
            for item in active
        }
        equal_power_w = remaining * 1000.0 / sum(hours.values())
        capped = [
            item
            for item in active
            if capacities.get(item[0], 0.0) / hours[item[0]] * 1000.0
            <= equal_power_w + 1e-9
        ]
        if not capped:
            for item in active:
                allocations[item[0]] += equal_power_w / 1000.0 * hours[item[0]]
            remaining = 0.0
            break
        for item in capped:
            index = item[0]
            addition = max(0.0, capacities.get(index, 0.0) - allocations[index])
            allocations[index] += addition
            remaining = max(0.0, remaining - addition)
            active.remove(item)
    return allocations


def _rounded(value: Any, digits: int = 5) -> float:
    return round(_finite(value), digits)


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        return round(value, 8) if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def snapshot_id(inputs: dict[str, Any]) -> str:
    """Return a stable id for all values that can change the plan."""
    ignored = {"generation_reason", "generated_at", "previous_plan_id"}
    payload = {key: value for key, value in inputs.items() if key not in ignored}
    raw = json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hour_map(value: Any) -> dict[int, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[int, float] = {}
    for key, raw in value.items():
        try:
            hour = int(str(key).split(":", 1)[0])
            number = float(raw)
        except (TypeError, ValueError):
            continue
        # Zero and negative prices are valid market data.  Missing data is
        # represented exclusively by a missing key/None, never by its sign.
        if 0 <= hour <= 23 and math.isfinite(number):
            result[hour] = number
    return result


def _profile24(value: Any) -> list[float]:
    if isinstance(value, dict):
        return [max(0.0, _finite(value.get(hour, value.get(str(hour))))) for hour in range(24)]
    if isinstance(value, list):
        return [max(0.0, _finite(value[hour])) if hour < len(value) else 0.0 for hour in range(24)]
    return [0.0] * 24


def _profile48(inputs: dict[str, Any]) -> list[float]:
    value = inputs.get("load_profile_48h")
    if isinstance(value, list) and any(_finite(item) > 0 for item in value[:48]):
        return [max(0.0, _finite(value[index])) if index < len(value) else 0.0 for index in range(48)]
    day = _profile24(inputs.get("load_profile"))
    return day + day


def _load_profile_quality(inputs: dict[str, Any]) -> tuple[list[float], list[bool]]:
    """Return the numeric load series and whether every value is evidence-based."""
    raw = inputs.get("load_profile_48h")
    sources = inputs.get("load_profile_sources_48h")
    if isinstance(raw, list):
        values: list[float] = []
        known: list[bool] = []
        for index in range(48):
            value = _optional(raw[index]) if index < len(raw) else None
            source = (
                sources[index].get("source")
                if isinstance(sources, list)
                and index < len(sources)
                and isinstance(sources[index], dict)
                else None
            )
            values.append(max(0.0, value) if value is not None else 0.0)
            known.append(value is not None and str(source or "explicit") != "missing")
        return values, known
    day = inputs.get("load_profile")
    if isinstance(day, (dict, list)):
        values = _profile24(day)
        return values + values, [True] * 48
    return [0.0] * 48, [False] * 48


def _normalised_solar_shape(value: Any) -> tuple[list[float], bool]:
    profile = _profile24(value)
    total = sum(profile)
    if total > 0:
        return [item / total for item in profile], True
    curve = [max(0.0, math.sin(math.pi * (hour - 5.5) / 13.0)) for hour in range(24)]
    curve_total = sum(curve) or 1.0
    return [item / curve_total for item in curve], False


def _parse_start(inputs: dict[str, Any]) -> tuple[date, datetime]:
    start_date = date.fromisoformat(str(inputs.get("date")))
    try:
        local_zone = ZoneInfo(str(inputs.get("timezone") or "UTC"))
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    generated_raw = inputs.get("generated_at")
    if generated_raw:
        try:
            generated = datetime.fromisoformat(str(generated_raw).replace("Z", "+00:00"))
            generated = (
                generated.replace(tzinfo=local_zone)
                if generated.tzinfo is None
                else generated.astimezone(local_zone)
            )
        except ValueError:
            generated = datetime.combine(start_date, datetime.min.time(), tzinfo=local_zone)
    else:
        generated = datetime.combine(start_date, datetime.min.time(), tzinfo=local_zone)
    return start_date, generated


def _profile_confidence(
    inputs: dict[str, Any],
    prefix: str,
    default_samples: float,
    default_total_cells: int,
) -> float:
    """Score a learned profile using samples, real cell coverage and rejections."""
    samples = max(
        0.0,
        _finite(inputs.get(f"{prefix}_profile_sample_count"), default_samples),
    )
    rejected = max(
        0.0,
        _finite(inputs.get(f"{prefix}_profile_rejected_count"), 0),
    )
    total_cells = max(
        1.0,
        _finite(inputs.get(f"{prefix}_profile_total_cells"), default_total_cells),
    )
    covered_cells = max(
        0.0,
        _finite(
            inputs.get(f"{prefix}_profile_covered_cells"),
            min(total_cells, samples),
        ),
    )
    sample_score = min(100.0, samples / total_cells * 100)
    coverage_score = min(100.0, covered_cells / total_cells * 100)
    accepted_total = samples + rejected
    acceptance_score = (
        min(100.0, samples / accepted_total * 100)
        if accepted_total > 0
        else 0.0
    )
    return (
        0.45 * coverage_score
        + 0.35 * sample_score
        + 0.20 * acceptance_score
    )


def _osd_available_hours(inputs: dict[str, Any]) -> int:
    """Return the real 48-hour OSD coverage instead of a binary flag."""
    if bool(inputs.get("price_includes_distribution")):
        return 48
    if inputs.get("osd_available_hours") is not None:
        return max(0, min(48, int(_finite(inputs.get("osd_available_hours")))))
    if "osd_data_complete" in inputs:
        return 48 if bool(inputs.get("osd_data_complete")) else 0
    distribution = inputs.get("distribution")
    if isinstance(distribution, list):
        return min(48, sum(value is not None for value in distribution[:48]))
    return 0


def _confidence(inputs: dict[str, Any], day_index: int, pv_learned: bool) -> tuple[float, dict[str, float]]:
    recorded = max(0, int(_finite(inputs.get("recorded_days"))))
    source_quality = inputs.get("data_quality") if isinstance(inputs.get("data_quality"), dict) else {}
    usable_history_hours = max(0.0, _finite(source_quality.get("usable_history_hours")))
    # Learning starts with the first usable hour. Full 24-hour days remain a
    # stronger signal, but incomplete calendar days no longer erase progress.
    equivalent_learning_days = max(float(recorded), usable_history_hours / 24.0)
    sells = inputs.get("sell_prices") if isinstance(inputs.get("sell_prices"), list) else []
    buys = inputs.get("buy_prices") if isinstance(inputs.get("buy_prices"), list) else []
    sell_coverage = len(_hour_map(sells[day_index] if day_index < len(sells) else {})) / 24
    buy_coverage = len(_hour_map(buys[day_index] if day_index < len(buys) else {})) / 24
    price = (sell_coverage + buy_coverage) / 2
    forecast = inputs.get("pv_forecast_available")
    pv_available = not isinstance(forecast, list) or (day_index < len(forecast) and bool(forecast[day_index]))
    maturity = (
        inputs.get("learning_maturity")
        if isinstance(inputs.get("learning_maturity"), dict)
        else None
    )
    learning = (
        max(0.0, min(1.0, _finite(maturity.get("score")) / 100.0))
        if maturity is not None
        else min(1.0, equivalent_learning_days / 21.0)
    )
    quality_score = _optional(source_quality.get("score"))
    sources = source_quality.get("sources") if isinstance(source_quality.get("sources"), dict) else {}
    score_map = {"good": 100.0, "degraded": 70.0, "low": 40.0, "unavailable": 0.0}
    source_scores = [
        score_map.get(str(item.get("quality") or "").lower(), 0.0)
        for item in sources.values()
        if isinstance(item, dict)
    ]
    nested_score = sum(source_scores) / len(source_scores) if source_scores else None
    entity_score = (
        min(max(quality_score, 0.0), 100.0)
        if quality_score is not None and nested_score is None
        else min(max(nested_score, 0.0), 100.0)
        if quality_score is None and nested_score is not None
        else min(max((quality_score + nested_score) / 2, 0.0), 100.0)
        if quality_score is not None and nested_score is not None
        else 85.0
    )
    soc_source = sources.get("battery_soc") if isinstance(sources.get("battery_soc"), dict) else {}
    soc_score = score_map.get(str(soc_source.get("quality") or "").lower(), 100.0 if inputs.get("soc") is not None else 0.0)
    tariff_score = _osd_available_hours(inputs) / 48 * 100
    load_profile = _profile_confidence(
        inputs,
        "load",
        max(recorded * 24, int(usable_history_hours)),
        168,
    )
    pv_profile = (
        _profile_confidence(
            inputs,
            "pv",
            max(recorded * 24, int(usable_history_hours)),
            288,
        )
        if pv_learned
        else 45.0
    )
    components = {
        "prices": round(price * 100, 1),
        "solcast": 100.0 if pv_available else 25.0,
        "learning": round(learning * 100, 1),
        "load_profile": round(load_profile, 1),
        "pv_profile": round(pv_profile, 1),
        "entities": round(entity_score, 1),
        "soc": round(soc_score, 1),
        "tariff_osd": round(tariff_score, 1),
    }
    # Preserve the established material-component weights. Maturity contributes
    # proportionally through the 14% learning component; it never caps the
    # otherwise valid plan merely because the integration is only N days old.
    value = (
        0.18 * components["prices"]
        + 0.18 * components["solcast"]
        + 0.14 * components["learning"]
        + 0.12 * components["load_profile"]
        + 0.10 * components["pv_profile"]
        + 0.12 * components["entities"]
        + 0.08 * components["soc"]
        + 0.08 * components["tariff_osd"]
    )
    # Legacy fixtures/integrations without the new maturity contract retain the
    # historical cap. Production 5G.4D payloads always supply maturity and are
    # therefore governed by evidence rather than the 7/21/60-day ladder.
    if maturity is None:
        if equivalent_learning_days < 7:
            value = min(value, 49.0)
        elif equivalent_learning_days < 14:
            value = min(value, 70.0)
        stage = inputs.get("learning_stage") if isinstance(inputs.get("learning_stage"), dict) else {}
        stage_cap = _optional(stage.get("confidence_cap"))
        if stage_cap is not None:
            value = min(value, max(0.0, min(100.0, stage_cap)))
    return round(max(20.0, min(95.0, value)), 1), components


def _data_quality_score(components: dict[str, float]) -> float:
    """Return current input quality without the separate maturity component."""

    weights = {
        "prices": 0.18,
        "solcast": 0.18,
        "load_profile": 0.12,
        "pv_profile": 0.10,
        "entities": 0.12,
        "soc": 0.08,
        "tariff_osd": 0.08,
    }
    total_weight = sum(weights.values())
    return round(
        sum(weights[key] * max(0.0, min(100.0, _finite(components.get(key)))) for key in weights)
        / total_weight,
        1,
    )


def _forecast_series(inputs: dict[str, Any]) -> dict[str, Any]:
    shape, learned = _normalised_solar_shape(inputs.get("pv_profile"))
    totals = inputs.get("pv_forecast") if isinstance(inputs.get("pv_forecast"), list) else [0, 0]
    full = inputs.get("pv_forecast_full") if isinstance(inputs.get("pv_forecast_full"), list) else totals
    available = inputs.get("pv_forecast_available")
    if not isinstance(available, list):
        available = [True, True]
    weather = inputs.get("weather_factors") if isinstance(inputs.get("weather_factors"), list) else []
    apply_weather = bool(inputs.get("apply_weather_correction", False))
    correction = max(0.4, min(1.6, _finite(inputs.get("forecast_correction"), 1.0)))
    accuracy = _optional(inputs.get("forecast_accuracy"))
    error = max(0.08, min(0.35, (100.0 - accuracy) / 100.0)) if accuracy is not None else 0.25
    current_hour = max(0, min(23, int(_finite(inputs.get("current_hour")))))
    operational: list[float] = []
    operational_raw: list[float] = []
    raw: list[float | None] = []
    corrected: list[float | None] = []
    low: list[float | None] = []
    high: list[float | None] = []
    for day_index in range(2):
        remaining_total = max(0.0, _finite(totals[day_index] if day_index < len(totals) else 0))
        active_shape = [
            0.0 if day_index == 0 and hour < current_hour else shape[hour]
            for hour in range(24)
        ]
        active_sum = sum(active_shape) or 1.0
        full_total = max(0.0, _finite(full[day_index] if day_index < len(full) else 0))
        for hour in range(24):
            index = day_index * 24 + hour
            factor_raw = weather[index] if index < len(weather) else None
            weather_factor = (
                max(0.65, min(1.05, _finite(factor_raw, 1.0)))
                if apply_weather and factor_raw is not None
                else 1.0
            )
            raw_operational = max(0.0, remaining_total * active_shape[hour] / active_sum)
            operational_raw.append(raw_operational)
            operational.append(raw_operational * correction * weather_factor)
            if day_index >= len(available) or not available[day_index]:
                raw.append(None)
                corrected.append(None)
                low.append(None)
                high.append(None)
                continue
            raw_value = full_total * shape[hour]
            corrected_value = max(0.0, raw_value * correction * weather_factor)
            raw.append(raw_value)
            corrected.append(corrected_value)
            low.append(corrected_value * (1.0 - error))
            high.append(corrected_value * (1.0 + error))
    return {
        "operational": operational,
        "operational_raw": operational_raw,
        "operational_low": [value * (1.0 - error) for value in operational],
        "operational_high": [value * (1.0 + error) for value in operational],
        "raw": raw,
        "corrected": corrected,
        "low": low,
        "high": high,
        "weather": weather if apply_weather else [],
        "weather_correction_applied": apply_weather,
        "learned": learned,
    }


def _prices(inputs: dict[str, Any]) -> dict[str, Any]:
    canonical = inputs.get("canonical_prices") if isinstance(inputs.get("canonical_prices"), dict) else {}
    if canonical.get("schema_version") == 1:
        buy_rows = canonical.get("buy", {}).get("rows", []) if isinstance(canonical.get("buy"), dict) else []
        sell_rows = canonical.get("sell", {}).get("rows", []) if isinstance(canonical.get("sell"), dict) else []

        def canonical_row_maps(rows: Any, field: str) -> list[dict[int, float]]:
            maps: list[dict[int, float]] = [{}, {}]
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict) or row.get("quality") != "ready":
                    continue
                day = 0 if row.get("day") == "today" else 1 if row.get("day") == "tomorrow" else -1
                hour = row.get("hour")
                value = _optional(row.get(field))
                if day in (0, 1) and isinstance(hour, int) and 0 <= hour <= 23 and value is not None:
                    maps[day][hour] = value
            return maps

        source_buys = canonical_row_maps(buy_rows, "source_price_pln_kwh")
        final_buys = canonical_row_maps(buy_rows, "final_price_pln_kwh")
        final_sells = canonical_row_maps(sell_rows, "final_price_pln_kwh")
        canonical_distribution = [0.0] * 48
        canonical_buy_rows: dict[int, dict[str, Any]] = {}
        canonical_sell_rows: dict[int, dict[str, Any]] = {}
        for direction_rows, target in ((buy_rows, canonical_buy_rows), (sell_rows, canonical_sell_rows)):
            for row in direction_rows if isinstance(direction_rows, list) else []:
                day = 0 if row.get("day") == "today" else 1 if row.get("day") == "tomorrow" else -1
                hour = row.get("hour")
                if day in (0, 1) and isinstance(hour, int) and 0 <= hour <= 23:
                    target[day * 24 + hour] = row
                    if target is canonical_buy_rows:
                        canonical_distribution[day * 24 + hour] = max(0.0, _finite(row.get("added_distribution")))
        return {
            "sell": final_sells,
            "buy": source_buys,
            "distribution": canonical_distribution,
            "effective_buy": final_buys,
            "included": True,
            "canonical": True,
            "canonical_buy_rows": canonical_buy_rows,
            "canonical_sell_rows": canonical_sell_rows,
        }
    sell_source = inputs.get("sell_prices") if isinstance(inputs.get("sell_prices"), list) else []
    buy_source = inputs.get("buy_prices") if isinstance(inputs.get("buy_prices"), list) else []
    sells = [_hour_map(sell_source[index] if index < len(sell_source) else {}) for index in range(2)]
    buys = [_hour_map(buy_source[index] if index < len(buy_source) else {}) for index in range(2)]
    distribution_raw = inputs.get("distribution") if isinstance(inputs.get("distribution"), list) else []
    distribution = [max(0.0, _finite(distribution_raw[index])) if index < len(distribution_raw) else 0.0 for index in range(48)]
    included = bool(inputs.get("price_includes_distribution"))
    effective_buy = [
        {
            hour: value if included else round(value + distribution[day_index * 24 + hour], 10)
            for hour, value in buys[day_index].items()
        }
        for day_index in range(2)
    ]
    return {
        "sell": sells,
        "buy": buys,
        "distribution": distribution,
        "effective_buy": effective_buy,
        "included": included,
        "canonical": False,
        "canonical_buy_rows": {},
        "canonical_sell_rows": {},
    }


def _ui_insights(
    inputs: dict[str, Any],
    prices: dict[str, Any],
    rows: list[dict[str, Any]],
    benefit: float,
    neutrality_threshold: float,
) -> dict[str, Any]:
    """Build deterministic, read-only UI summaries without changing dispatch."""
    start_date, _generated = _parse_start(inputs)
    tariff = inputs.get("tariff_context") if isinstance(inputs.get("tariff_context"), dict) else {}
    tariff_rows = tariff.get("hourly_profile") if isinstance(tariff.get("hourly_profile"), list) else []
    osd_complete = bool(inputs.get("osd_data_complete"))
    included = bool(prices.get("included"))
    profiles_root = inputs.get("user_profiles") if isinstance(inputs.get("user_profiles"), dict) else {}
    profiles = profiles_root.get("profiles") if isinstance(profiles_root.get("profiles"), dict) else {}
    current_hour = max(0, min(23, int(_finite(inputs.get("current_hour"), 0))))
    labels = {
        "morning_sale": "Poranna sprzedaż",
        "evening_sale": "Wieczorna sprzedaż",
        "charging": "Ładowanie",
    }

    purchase_days: dict[str, list[dict[str, Any]]] = {"today": [], "tomorrow": []}
    for day_index, day_name in enumerate(("today", "tomorrow")):
        day = start_date + timedelta(days=day_index)
        for hour, energy_price in prices["buy"][day_index].items():
            index = day_index * 24 + hour
            tariff_row = tariff_rows[index] if index < len(tariff_rows) and isinstance(tariff_rows[index], dict) else {}
            canonical_row = prices.get("canonical_buy_rows", {}).get(index, {})
            distribution = prices["distribution"][index]
            purchase_days[day_name].append({
                "day": day_name,
                "date": day.isoformat(),
                "hour": hour,
                "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
                "energy_price": round(_finite(canonical_row.get("energy_component"), energy_price), 5),
                "source_price": round(_finite(canonical_row.get("source_price_pln_kwh"), energy_price), 5),
                "distribution_price": round(distribution if prices.get("canonical") else 0.0 if included else distribution, 5),
                "added_vat": round(_finite(canonical_row.get("added_vat")), 5),
                "added_other_variable": round(_finite(canonical_row.get("added_other_variable")), 5),
                "effective_price": round(prices["effective_buy"][day_index][hour], 5),
                "zone": tariff_row.get("zone"),
                "season": tariff_row.get("season"),
                "day_type": tariff_row.get("day_type"),
                "provider": tariff.get("provider"),
                "provider_name": tariff.get("provider_name"),
                "plan": tariff.get("plan"),
                "plan_name": tariff.get("plan_name"),
                "price_includes_distribution": (
                    canonical_row.get("source_semantic_scope") == "all_in_variable"
                    or bool(canonical_row.get("added_distribution") == 0 and included)
                ),
                "source_adapter": canonical_row.get("source_adapter"),
                "source_unit": canonical_row.get("source_unit"),
                "source_basis": canonical_row.get("source_basis"),
                "source_semantic_scope": canonical_row.get("source_semantic_scope"),
                "coverage_minutes": canonical_row.get("coverage_minutes"),
                "quality": canonical_row.get("quality", "legacy"),
                "osd_complete": bool(included or osd_complete),
            })
        ranked = sorted(purchase_days[day_name], key=lambda item: (item["effective_price"], item["hour"]))
        for rank, item in enumerate(ranked, 1):
            item["price_rank"] = rank
        purchase_days[day_name].sort(key=lambda item: item["hour"])

    sale_profiles: dict[str, Any] = {}
    for profile_id in ("morning_sale", "evening_sale"):
        profile = profiles.get(profile_id) if isinstance(profiles.get(profile_id), dict) else {}
        enabled = bool(profile.get("enabled"))
        minimum = _finite(profile.get("min_price", profile.get("minimum_price")), 0)
        target = max(0.0, _finite(profile.get("target_energy_kwh"), 0))
        profile_days: dict[str, list[dict[str, Any]]] = {"today": [], "tomorrow": []}
        profile_active_days: dict[str, bool] = {"today": False, "tomorrow": False}
        active_local_dates = set(_profile_local_dates(inputs, profile))
        for day_index, day_name in enumerate(("today", "tomorrow")):
            day = start_date + timedelta(days=day_index)
            profile_active_days[day_name] = day.isoformat() in active_local_dates
            if not profile_active_days[day_name]:
                continue
            for hour, price in prices["sell"][day_index].items():
                if not _time_in_window(hour, profile.get("start"), profile.get("end")):
                    continue
                if not _active_today(profile, _profile_window_day(profile, day, hour)):
                    continue
                plan_row = rows[day_index * 24 + hour]
                planned_for_profile = f"profile:{profile_id}" in plan_row.get("reason_codes", [])
                qualifies = price + 1e-9 >= minimum
                is_past = day_index == 0 and hour < current_hour
                recommended = bool(
                    enabled
                    and qualifies
                    and planned_for_profile
                    and plan_row.get("proposed")
                    and not is_past
                )
                profile_fulfillment = (
                    max(0.0, _finite(plan_row.get("profile_contribution_kwh"), 0.0))
                    if enabled and qualifies and planned_for_profile and not is_past
                    else 0.0
                )
                limit_reasons = [
                    str(code).split(":", 1)[1]
                    for code in plan_row.get("reason_codes", [])
                    if str(code).startswith("limit:")
                ]
                profile_days[day_name].append({
                    "day": day_name,
                    "date": day.isoformat(),
                    "hour": hour,
                    "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
                    "sell_price": round(price, 5),
                    "qualifies_minimum": qualifies,
                    "recommended": recommended,
                    "planned_energy_kwh": profile_fulfillment,
                    "battery_to_grid_kwh": plan_row.get("battery_to_grid_kwh", 0.0),
                    "pv_to_grid_kwh": plan_row.get("pv_to_grid_kwh", 0.0),
                    "planned_power_w": plan_row.get("planned_power_w", 0.0) if recommended else 0.0,
                    "soc_before": plan_row.get("soc_start_pct"),
                    "soc_after": plan_row.get("soc_end_pct"),
                    "decision_source": f"profile:{profile_id}" if planned_for_profile else "informational",
                    "is_past": is_past,
                    "actionable": not is_past,
                    "home_load_kwh": plan_row.get("home_load_kwh"),
                    "pv_kwh": plan_row.get("pv_kwh"),
                    "conversion_losses_kwh": plan_row.get("conversion_losses_kwh"),
                    "requested_energy_kwh": plan_row.get("requested_action_energy_kwh"),
                    "power_limit_w": plan_row.get("power_limit_w"),
                    "duration_minutes": plan_row.get("duration_minutes"),
                    "power_basis": plan_row.get("power_basis"),
                    "limit_reasons": limit_reasons,
                    "skip_reason": (
                        "past_window"
                        if is_past
                        else "below_minimum_price"
                        if not qualifies
                        else None
                        if recommended
                        else limit_reasons[0]
                        if limit_reasons
                        else "not_selected_by_energy_budget"
                    ),
                })
            ranked = sorted(profile_days[day_name], key=lambda item: (-item["sell_price"], item["hour"]))
            for rank, item in enumerate(ranked, 1):
                item["price_rank"] = rank
            profile_days[day_name].sort(key=lambda item: item["hour"])
        minimum_soc = max(0.0, _finite(profile.get("min_soc_after", profile.get("minimum_soc")), 0))
        capacity = max(0.1, _finite(inputs.get("battery_capacity_kwh"), 10))
        discharge_efficiency = max(0.5, min(1.0, _finite(inputs.get("discharge_efficiency"), 0.95)))
        day_summaries: dict[str, dict[str, Any]] = {}
        for day_index, day_name in enumerate(("today", "tomorrow")):
            day_rows = profile_days[day_name]
            day_target = target if profile_active_days[day_name] else 0.0
            actionable_rows = [item for item in day_rows if not item["is_past"]]
            selected_day_rows = [item for item in day_rows if item["recommended"]]
            profile_energy = round(sum(
                _finite(item["planned_energy_kwh"])
                for item in day_rows
                if not item["is_past"]
            ), 5)
            optimizer_rows = [
                item
                for item in rows
                if item.get("day") == day_name
                and item.get("action") == "sell"
                and item.get("proposed")
                and not item.get("profile_id")
                and _time_in_window(int(_finite(item.get("hour"), -1)), profile.get("start"), profile.get("end"))
                and not (day_index == 0 and int(_finite(item.get("hour"), -1)) < current_hour)
            ]
            optimizer_energy = round(sum(_finite(item.get("planned_energy_kwh")) for item in optimizer_rows), 5)
            day_limit_counts: dict[str, int] = {}
            for item in actionable_rows:
                for reason in item["limit_reasons"]:
                    day_limit_counts[reason] = day_limit_counts.get(reason, 0) + 1
            window_ended = bool(
                day_name == "today"
                and profile_active_days[day_name]
                and day_rows
                and not actionable_rows
            )
            if not enabled:
                day_primary_constraint = "disabled"
            elif not profile_active_days[day_name]:
                day_primary_constraint = "inactive_day"
            elif not day_rows:
                day_primary_constraint = "missing_prices"
            elif window_ended:
                day_primary_constraint = "past_window"
            elif day_limit_counts:
                day_primary_constraint = max(day_limit_counts, key=lambda key: (day_limit_counts[key], key))
            elif not any(item["qualifies_minimum"] for item in actionable_rows):
                day_primary_constraint = "price_threshold"
            elif profile_energy + 1e-6 < day_target:
                day_primary_constraint = "unresolved_daily_constraint"
            else:
                day_primary_constraint = "target_reached"
            day_initial_soc = next(
                (item["soc_before"] for item in actionable_rows if item["soc_before"] is not None),
                next((item["soc_before"] for item in day_rows if item["soc_before"] is not None), None),
            )
            day_usable_at_start = (
                max(0.0, capacity * (_finite(day_initial_soc) - minimum_soc) / 100.0) * discharge_efficiency
                if day_initial_soc is not None else None
            )
            day_summaries[day_name] = {
                "day": day_name,
                "date": (start_date + timedelta(days=day_index)).isoformat(),
                "active": profile_active_days[day_name],
                "window_ended": window_ended,
                "target_energy_kwh": day_target,
                "profile_planned_energy_kwh": profile_energy,
                "optimizer_extra_energy_kwh": optimizer_energy,
                "total_proposed_energy_kwh": round(profile_energy + optimizer_energy, 5),
                "missing_profile_energy_kwh": round(max(0.0, day_target - profile_energy), 5),
                "primary_constraint": day_primary_constraint,
                "limiting_factors": sorted(day_limit_counts, key=lambda key: (-day_limit_counts[key], key)),
                "initial_soc_pct": day_initial_soc,
                "minimum_soc_pct": minimum_soc,
                "battery_capacity_kwh": capacity,
                "usable_energy_at_window_start_kwh": (
                    round(day_usable_at_start, 5) if day_usable_at_start is not None else None
                ),
                "forecast_home_in_window_kwh": round(
                    sum(_finite(item["home_load_kwh"]) for item in actionable_rows), 5
                ),
                "forecast_pv_in_window_kwh": round(
                    sum(_finite(item["pv_kwh"]) for item in actionable_rows), 5
                ),
                "conversion_losses_kwh": round(
                    sum(_finite(item["conversion_losses_kwh"]) for item in selected_day_rows), 5
                ),
                "selected_profile_hours": len(selected_day_rows),
                "optimizer_extra_hours": len(optimizer_rows),
                "qualified_future_hours": sum(bool(item["qualifies_minimum"]) for item in actionable_rows),
            }
        horizon_planned = round(sum(
            item["planned_energy_kwh"]
            for day_rows in profile_days.values()
            for item in day_rows
            if not item["is_past"]
        ), 5)
        qualified = sum(
            1
            for day_rows in profile_days.values()
            for item in day_rows
            if item["qualifies_minimum"]
        )
        selected_rows = [
            item for day_rows in profile_days.values() for item in day_rows if item["recommended"]
        ]
        future_rows = [
            item for day_rows in profile_days.values() for item in day_rows if not item["is_past"]
        ]
        limit_counts: dict[str, int] = {}
        for item in selected_rows:
            for reason in item["limit_reasons"]:
                limit_counts[reason] = limit_counts.get(reason, 0) + 1
        primary_summary = day_summaries["today"]
        primary_constraint = (
            max(limit_counts, key=lambda key: (limit_counts[key], key))
            if limit_counts
            else "price_threshold"
            if not any(item["qualifies_minimum"] for item in future_rows)
            else "unresolved_daily_constraint"
            if primary_summary["profile_planned_energy_kwh"] + 1e-6
            < primary_summary["target_energy_kwh"]
            else "target_reached"
        )
        initial_soc = next((item["soc_before"] for item in future_rows if item["soc_before"] is not None), None)
        usable_at_start = (
            max(0.0, capacity * (_finite(initial_soc) - minimum_soc) / 100.0) * discharge_efficiency
            if initial_soc is not None else None
        )
        horizon_target = round(sum(
            target for summary in day_summaries.values() if summary["active"]
        ), 5)
        sale_profiles[profile_id] = {
            "profile_id": profile_id,
            "name": str(profile.get("name") or labels[profile_id]),
            "enabled": enabled,
            "start": str(profile.get("start") or ""),
            "end": str(profile.get("end") or ""),
            "target_energy_kwh": target,
            "planned_energy_kwh": horizon_planned,
            "missing_energy_kwh": round(max(0.0, horizon_target - horizon_planned), 5),
            "minimum_price": minimum,
            "minimum_soc_after": _optional(profile.get("min_soc_after")),
            "qualified_hours": qualified,
            "explanation": {
                "primary_constraint": primary_constraint,
                "limiting_factors": sorted(limit_counts, key=lambda key: (-limit_counts[key], key)),
                "initial_soc_pct": initial_soc,
                "minimum_soc_pct": minimum_soc,
                "battery_capacity_kwh": capacity,
                "usable_energy_at_window_start_kwh": round(usable_at_start, 5) if usable_at_start is not None else None,
                "forecast_home_in_window_kwh": round(sum(_finite(item["home_load_kwh"]) for item in future_rows), 5),
                "forecast_pv_in_window_kwh": round(sum(_finite(item["pv_kwh"]) for item in future_rows), 5),
                "conversion_losses_kwh": round(sum(_finite(item["conversion_losses_kwh"]) for item in selected_rows), 5),
                "selected_hours": len(selected_rows),
                "qualified_future_hours": sum(bool(item["qualifies_minimum"]) for item in future_rows),
            },
            "status": (
                "disabled"
                if not enabled
                else "no_hours_above_minimum"
                if qualified == 0
                else "partially_possible"
                if primary_summary["profile_planned_energy_kwh"] + 1e-6
                < primary_summary["target_energy_kwh"]
                else "ready"
            ),
            "days": profile_days,
            "day_summaries": day_summaries,
            "horizon_totals": {
                "target_energy_kwh": horizon_target,
                "profile_planned_energy_kwh": horizon_planned,
                "missing_profile_energy_kwh": round(max(0.0, horizon_target - horizon_planned), 5),
            },
        }

    if benefit > neutrality_threshold:
        assessment = "better"
        decision_title = "Plan z wyższym wynikiem modelowanym"
    elif benefit < -neutrality_threshold:
        assessment = "worse"
        decision_title = "Realizacja profilu użytkownika"
    else:
        assessment = "neutral"
        decision_title = "Plan praktycznie taki sam jak plan bazowy"

    tomorrow_actions = [row for row in rows if row.get("day") == "tomorrow" and row.get("proposed")]
    return {
        "sale_profiles": sale_profiles,
        "purchase_ranking": {
            "days": purchase_days,
            "provider": tariff.get("provider"),
            "provider_name": tariff.get("provider_name"),
            "plan": tariff.get("plan"),
            "plan_name": tariff.get("plan_name"),
            "price_includes_distribution": included,
            "osd_complete": bool(included or osd_complete),
            "warning": None if included or osd_complete else "missing_osd_data",
            "coverage_today": len(purchase_days["today"]),
            "coverage_tomorrow": len(purchase_days["tomorrow"]),
            "energy_source": inputs.get("buy_price_source"),
        },
        "comparison": {
            "assessment": assessment,
            "decision_title": decision_title,
            "benefit_vs_baseline_pln": round(benefit, 5),
            "neutrality_threshold_pln": round(neutrality_threshold, 5),
        },
        "tomorrow_plan_status": (
            "blocked"
            if any(row.get("dispatch_status") == "blocked" for row in rows)
            else "proposal_pending"
            if tomorrow_actions
            else "forecast_ready"
        ),
        "minimum_soc": {
            "hard_min_soc_pct": max(0.0, min(100.0, _finite(inputs.get("min_soc"), 20))),
            "effective_min_soc_pct": max(0.0, min(100.0, _finite(inputs.get("effective_min_soc"), 20))),
        },
        "price_publication": {
            "expected_tomorrow_after_hour": 13,
            "warning_after_hour": 14,
            "warning_after_minute": 30,
            "tomorrow_status": (
                "complete"
                if len(prices["sell"][1]) == 24 and len(prices["buy"][1]) == 24
                else "awaiting_publication"
                if (_generated.hour, _generated.minute) < (14, 30)
                else "missing_after_publication"
            ),
            "today_sell_coverage": len(prices["sell"][0]),
            "today_buy_coverage": len(prices["buy"][0]),
            "tomorrow_sell_coverage": len(prices["sell"][1]),
            "tomorrow_buy_coverage": len(prices["buy"][1]),
        },
    }


def _time_in_window(hour: int, start: Any, end: Any) -> bool:
    try:
        begin = int(str(start).split(":", 1)[0])
        finish = int(str(end).split(":", 1)[0])
    except (TypeError, ValueError):
        return False
    return begin <= hour < finish if begin < finish else hour >= begin or hour < finish


def _active_today(profile: dict[str, Any], day: date) -> bool:
    days = profile.get("active_days")
    if not isinstance(days, list) or not days:
        return True
    normalized = {str(item).lower() for item in days}
    aliases = {
        day.strftime("%A").lower(),
        str(day.weekday()),
        ("pon", "wt", "śr", "czw", "pt", "sob", "niedz")[day.weekday()],
    }
    return bool(normalized & aliases)


def _profile_window_day(profile: dict[str, Any], day: date, hour: int) -> date:
    """Anchor the after-midnight tail of a window to the day it started."""
    start = _hour_value(profile.get("start"))
    end = _hour_value(profile.get("end"), 23)
    if start >= end and hour < end:
        return day - timedelta(days=1)
    return day


def _profile_local_dates(inputs: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Return active calendar dates represented by profile slots in the 48 h horizon.

    ``active_days`` keeps its established window-start semantics for windows that
    cross midnight.  The energy target is intentionally different: every slot
    consumes the pool of its own local calendar date.
    """
    start_date, _generated = _parse_start(inputs)
    result: list[str] = []
    for index in range(48):
        day_index, hour = divmod(index, 24)
        day = start_date + timedelta(days=day_index)
        if not _time_in_window(hour, profile.get("start"), profile.get("end")):
            continue
        if not _active_today(profile, _profile_window_day(profile, day, hour)):
            continue
        key = day.isoformat()
        if key not in result:
            result.append(key)
    return result


def _hour_value(value: Any, default: int = 0) -> int:
    try:
        return max(0, min(23, int(str(value).split(":", 1)[0])))
    except (TypeError, ValueError):
        return default


def _canonical_purpose(value: Any) -> str:
    raw = str(value or "mixed").strip().lower()
    aliases = {
        "general": "mixed",
        "both_sales": "sale",
        "morning_sale": "sale",
        "evening_sale": "sale",
        "cheap_home": "home",
        "home_reserve": "reserve",
        "backup": "reserve",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in {"sale", "home", "reserve", "mixed"} else "mixed"


def _deadline_index(index: int, profile: dict[str, Any]) -> int:
    """Return the absolute deadline belonging to the candidate's local window."""
    hour = index % 24
    day_index = index // 24
    start = _hour_value(profile.get("start"))
    end = _hour_value(profile.get("end"), 23)
    deadline = _hour_value(profile.get("deadline"), end)
    crosses_midnight = start >= end
    anchor_day = day_index - 1 if crosses_midnight and hour < end else day_index
    result = anchor_day * 24 + deadline
    if crosses_midnight and deadline <= start:
        result += 24
    elif not crosses_midnight and deadline <= start:
        result += 24
    return max(0, min(48, result))


def _charge_economics(
    inputs: dict[str, Any],
    prices: dict[str, Any],
    index: int,
    purpose: str,
    deadline: int,
) -> dict[str, Any]:
    """Value a charge only against a strictly later use before its deadline."""
    efficiency = max(0.5, min(1.0, _finite(inputs.get("battery_efficiency"), 0.9)))
    cycle_cost = max(0.0, _finite(inputs.get("battery_cycle_cost_per_kwh"), 0.0))
    day_index, hour = divmod(index, 24)
    cost = prices["effective_buy"][day_index].get(hour)
    if cost is None:
        return {"expected_margin": None, "future_target_type": None, "future_target_hour": None}
    load = _profile48(inputs)
    future = range(index + 1, max(index + 1, min(48, deadline)))
    sale_values = [
        (later, prices["sell"][later // 24].get(later % 24))
        for later in future
    ]
    sale_values = [(later, value) for later, value in sale_values if value is not None and value > 0]
    home_values = [
        (later, prices["effective_buy"][later // 24].get(later % 24))
        for later in future
        if load[later] > 1e-9
    ]
    home_values = [(later, value) for later, value in home_values if value is not None]

    options: list[tuple[str, int | None, float, float]] = []
    if purpose in {"sale", "mixed"} and sale_values:
        later, value = max(sale_values, key=lambda item: (item[1], -item[0]))
        options.append(("sale", later, value, value * efficiency - cost - 2 * cycle_cost))
    if purpose in {"home", "mixed"} and home_values:
        later, value = max(home_values, key=lambda item: (item[1], -item[0]))
        options.append(("home_load", later, value, value * efficiency - cost - 2 * cycle_cost))
    if purpose == "reserve":
        reserve_value = max(0.0, _finite(inputs.get("terminal_energy_value_per_kwh"), 0.0))
        options.append(("reserve", None, reserve_value, reserve_value * efficiency - cost - cycle_cost))
    if not options:
        return {
            "expected_margin": None,
            "future_target_type": None,
            "future_target_hour": None,
            "future_target_price": None,
        }
    target_type, target_hour, target_price, margin = max(options, key=lambda item: item[3])
    return {
        "expected_margin": round(margin, 6),
        "future_target_type": target_type,
        "future_target_hour": target_hour,
        "future_target_price": round(target_price, 6),
    }


def _slot_capacity_hours(inputs: dict[str, Any], index: int) -> float:
    """Return the real wall-clock capacity of one horizon slot."""
    current_hour = max(0, min(23, int(_finite(inputs.get("current_hour"), 0))))
    if index < current_hour:
        return 0.0
    if index == current_hour:
        return max(
            1.0,
            min(60.0, _finite(inputs.get("current_hour_remaining_minutes"), 60)),
        ) / 60.0
    start_date, generated = _parse_start(inputs)
    day_index, hour = divmod(index, 24)
    day = start_date + timedelta(days=day_index)
    hour_start = datetime.combine(
        day,
        datetime.min.time(),
        tzinfo=generated.tzinfo,
    ).replace(hour=hour)
    next_day = day + timedelta(days=1) if hour == 23 else day
    next_hour = 0 if hour == 23 else hour + 1
    hour_end = datetime.combine(
        next_day,
        datetime.min.time(),
        tzinfo=generated.tzinfo,
    ).replace(hour=next_hour)
    return max(
        0.0,
        (
            hour_end.astimezone(timezone.utc)
            - hour_start.astimezone(timezone.utc)
        ).total_seconds() / 3600.0,
    )


def _positive_min(*values: Any, fallback: float = 0.0) -> float:
    candidates = [
        number
        for value in values
        if (number := _optional(value)) is not None and number > 0
    ]
    return min(candidates) if candidates else max(0.0, fallback)


def _profile_slot_capacity_kwh(
    inputs: dict[str, Any],
    request: dict[str, Any],
    index: int,
    default_power_w: float,
) -> float:
    """Conservative pre-simulation capacity used by target allocation."""
    profile_limit = _optional(request.get("power_limit_w"))
    if request.get("action") == "charge":
        effective_power = _positive_min(
            profile_limit,
            inputs.get("battery_charge_limit_w"),
            inputs.get("grid_import_limit_w"),
            inputs.get("inverter_ac_limit_w"),
            fallback=default_power_w,
        )
    else:
        effective_power = _positive_min(
            profile_limit,
            inputs.get("max_sell_power_w"),
            inputs.get("effective_power_limit_w"),
            inputs.get("battery_discharge_limit_w"),
            inputs.get("grid_export_limit_w"),
            inputs.get("inverter_ac_limit_w"),
            fallback=default_power_w,
        )
        effective_power = quantize_power_w(
            effective_power,
            step_w=inputs.get("sell_power_step_w", 1.0),
            minimum_w=inputs.get("sell_power_minimum_w", 0.0),
            maximum_w=effective_power,
        )
    return max(0.0, effective_power / 1000.0 * _slot_capacity_hours(inputs, index))


def _sell_capacity_limit_reasons(inputs: dict[str, Any], profile_limit: Any) -> list[str]:
    """Return the original source(s) of the binding pre-allocation power cap."""
    names = {
        "plan": "global_max_sell_power",
        "export": "export_limit",
        "inverter": "inverter_power",
        "entity": "max_sell_power_entity",
        "current_voltage": "current_voltage_battery_limit",
        "configured_battery_discharge": "configured_battery_discharge_limit",
    }
    candidates: list[tuple[str, float]] = []
    source_limits = inputs.get("sell_power_limits_w")
    if isinstance(source_limits, dict):
        candidates.extend(
            (names.get(str(key), str(key)), value)
            for key, raw in source_limits.items()
            if (value := _optional(raw)) is not None and value > 0
        )
    for reason, raw in (
        ("profile_max_power", profile_limit),
        ("global_max_sell_power", inputs.get("max_sell_power_w")),
        ("battery_discharge_limit", inputs.get("battery_discharge_limit_w")),
        ("export_limit", inputs.get("grid_export_limit_w")),
        ("inverter_power", inputs.get("inverter_ac_limit_w")),
    ):
        value = _optional(raw)
        if value is not None and value > 0:
            candidates.append((reason, value))
    if not candidates:
        return []
    minimum = min(value for _reason, value in candidates)
    return list(dict.fromkeys(
        reason for reason, value in candidates if value <= minimum + 1e-6
    ))


def _profile_requests(
    inputs: dict[str, Any],
    prices: dict[str, Any],
    *,
    return_metadata: bool = False,
) -> Any:
    root = inputs.get("user_profiles") if isinstance(inputs.get("user_profiles"), dict) else {}
    profiles = root.get("profiles") if isinstance(root.get("profiles"), dict) else {}
    start_date = date.fromisoformat(str(inputs.get("date")))
    candidates: dict[int, list[dict[str, Any]]] = {}
    profile_candidates: dict[tuple[str, str], list[tuple[int, dict[str, Any], float]]] = {}
    profile_pool_specs: dict[tuple[str, str], dict[str, Any]] = {}
    supporting_charge_requests: list[tuple[int, dict[str, Any]]] = []
    default_power_w = max(
        0.0,
        _finite(inputs.get("effective_power_limit_w"), _finite(inputs.get("max_sell_power_w"), 5000)),
    )
    blocked = {str(item) for item in inputs.get("_blocked_profile_ids", [])}
    for key, profile in profiles.items():
        if not isinstance(profile, dict) or not bool(profile.get("enabled")):
            continue
        if str(key) in blocked:
            continue
        kind = "charge" if key == "charging" or str(profile.get("type")).lower() == "charging" else "sell"
        priority_map = {"low": 10, "normal": 50, "high": 90}
        priority = priority_map.get(str(profile.get("priority")).lower(), int(_finite(profile.get("priority"), 50)))
        required = str(profile.get("goal_character") or "preferred") == "required"
        target_energy = _finite(
            profile.get("target_value")
            if kind == "charge" and profile.get("target_type") == "energy"
            else profile.get("target_energy_kwh"),
            0,
        )
        if kind == "sell" and target_energy <= 0:
            continue
        if kind == "charge" and profile.get("target_type") == "energy" and target_energy <= 0:
            continue
        profile_id = str(key)
        for local_date in _profile_local_dates(inputs, profile):
            profile_pool_specs[(profile_id, local_date)] = {
                "action": kind,
                "profile_id": profile_id,
                "profile_date": local_date,
                "target_type": str(profile.get("target_type") or "energy"),
                "target_basis": str(profile.get("target_basis") or "battery_to_grid"),
                "target_energy_kwh": target_energy,
                "distribution_method": str(profile.get("distribution_method") or "best_hours"),
            }
        for index in range(48):
            day_index, hour = divmod(index, 24)
            day = start_date + timedelta(days=day_index)
            in_window = _time_in_window(hour, profile.get("start"), profile.get("end"))
            earlier_allowed = kind == "charge" and bool(profile.get("allow_earlier_grid_charge"))
            policy_day = _profile_window_day(profile, day, hour) if in_window else day
            if not _active_today(profile, policy_day) or (not in_window and not earlier_allowed):
                continue
            if kind == "sell":
                price = prices["sell"][day_index].get(hour)
                threshold = _finite(profile.get("min_price", profile.get("minimum_price")), 0)
                if price is None or price < threshold:
                    continue
            else:
                price = prices["effective_buy"][day_index].get(hour)
                threshold = _finite(profile.get("max_effective_price", profile.get("maximum_total_price")), 0)
                if price is None or (threshold > 0 and price > threshold):
                    continue
            deadline = _deadline_index(index, profile)
            if kind == "charge" and index >= deadline:
                continue
            if kind == "charge" and not in_window:
                later_window_prices = [
                    prices["effective_buy"][later // 24].get(later % 24)
                    for later in range(index + 1, deadline)
                    if _time_in_window(later % 24, profile.get("start"), profile.get("end"))
                ]
                later_window_prices = [value for value in later_window_prices if value is not None]
                if not later_window_prices or price >= min(later_window_prices) - 1e-9:
                    continue
            purpose = _canonical_purpose(profile.get("purpose"))
            economics = (
                _charge_economics(inputs, prices, index, purpose, deadline)
                if kind == "charge"
                else {}
            )
            profitable_only = bool(profile.get("profitable_only", False))
            if (
                kind == "charge"
                and profitable_only
                and purpose != "reserve"
                and (
                    economics.get("expected_margin") is None
                    or economics["expected_margin"] <= _finite(profile.get("minimum_margin"), 0)
                )
            ):
                continue
            request = {
                "action": kind,
                "priority": priority,
                "required": required,
                "goal_character": "required" if required else "preferred",
                "profile_id": str(key),
                "profile_date": day.isoformat(),
                "reason": f"profile:{key}",
                "power_limit_w": _optional(profile.get("preferred_power_w", profile.get("power_limit_w"))),
                "target_soc": (
                    _optional(profile.get("target_value", profile.get("target_soc")))
                    if kind == "charge" and profile.get("target_type") == "soc"
                    else None
                ),
                "target_type": str(profile.get("target_type") or "energy"),
                "target_basis": str(profile.get("target_basis") or "battery_to_grid"),
                "target_energy_kwh": target_energy,
                "distribution_method": str(profile.get("distribution_method") or "best_hours"),
                "min_soc_after": _optional(profile.get("min_soc_after", profile.get("minimum_soc"))),
                "allow_partial": bool(profile.get("allow_partial", True)),
                "min_net_result": _finite(profile.get("min_net_result"), 0),
                "minimum_confidence": max(0.0, min(100.0, _finite(profile.get("minimum_confidence"), 0))),
                "charge_source": str(profile.get("source") or "auto"),
                "max_grid_energy_kwh": _optional(profile.get("max_grid_energy_kwh")),
                "preserve_pv_room": bool(profile.get("preserve_pv_room")),
                "minimum_free_room_kwh": max(0.0, _finite(profile.get("minimum_free_room_kwh"), 0)),
                "profitable_only": profitable_only,
                "purpose": purpose,
                "deadline": profile.get("deadline"),
                "deadline_index": deadline,
                "charge_missing_only": bool(profile.get("charge_missing_only", True)),
                "use_corrected_pv": bool(profile.get("use_corrected_pv", True)),
                "price": float(price),
                **economics,
            }
            if kind == "charge" and purpose == "reserve":
                request["reason"] = "profile:reserve-goal"
            elif kind == "charge" and not in_window:
                request["reason"] = f"profile:{key}:earlier-grid-charge"
            profile_candidates.setdefault((str(key), day.isoformat()), []).append(
                (index, request, float(price))
            )

    # An explicit sale profile may permit an earlier grid charge.  This is a
    # supporting action for that same profile, never a separate hidden goal.
    capacity = max(0.1, _finite(inputs.get("battery_capacity_kwh"), 10))
    soc = max(0.0, min(100.0, _finite(inputs.get("soc"), 0)))
    discharge_eff = max(0.5, min(1.0, _finite(inputs.get("discharge_efficiency"), 0.95)))
    charge_eff = max(0.5, min(1.0, _finite(inputs.get("charge_efficiency"), 0.95)))
    for profile_id, profile in profiles.items():
        if (
            not isinstance(profile, dict)
            or not profile.get("enabled")
            or not profile.get("allow_earlier_grid_charge")
            or str(profile_id) in blocked
        ):
            continue
        sale_rows = [
            item
            for (candidate_profile_id, _local_date), pool_rows in profile_candidates.items()
            if candidate_profile_id == str(profile_id)
            for item in pool_rows
        ]
        if not sale_rows or sale_rows[0][1].get("action") != "sell":
            continue
        target = max(0.0, _finite(profile.get("target_energy_kwh"), 0))
        minimum_soc = max(0.0, _finite(profile.get("min_soc_after", profile.get("minimum_soc")), 0))
        available = max(0.0, capacity * (soc - minimum_soc) / 100.0) * discharge_eff
        missing_input = max(0.0, target - available) / charge_eff
        if missing_input <= 1e-9:
            continue
        first_sale = min(index for index, _request, _price in sale_rows)
        sale_by_index = {index: (price, request) for index, request, price in sale_rows}
        earlier: list[tuple[int, float, int, float, float, str]] = []
        for index in range(max(0, int(_finite(inputs.get("current_hour"), 0))), first_sale):
            buy = prices["effective_buy"][index // 24].get(index % 24)
            later_sales = [
                (later, price, request)
                for later, (price, request) in sale_by_index.items()
                if later > index
            ]
            if buy is None or not later_sales:
                continue
            later, sell, later_request = max(later_sales, key=lambda item: (item[1], -item[0]))
            margin = sell * _finite(inputs.get("battery_efficiency"), 0.9) - buy
            if margin <= max(0.0, _finite(profile.get("min_net_result"), 0) / max(target, 1e-9)):
                continue
            earlier.append((
                index,
                buy,
                later,
                sell,
                margin,
                str(later_request.get("profile_date") or ""),
            ))
        for index, buy, later, sell, margin, profile_date in sorted(
            earlier, key=lambda item: (item[1], item[0])
        ):
            cap = max(
                0.0,
                _finite(profile.get("preferred_power_w"), default_power_w) / 1000.0,
            )
            requested = min(cap, missing_input)
            if requested <= 1e-9:
                break
            missing_input -= requested
            supporting_charge_requests.append((index, {
                "action": "charge",
                "priority": 95,
                "required": False,
                "profile_id": str(profile_id),
                "profile_date": profile_date,
                "reason": f"profile:{profile_id}:earlier-grid-charge",
                "power_limit_w": _optional(profile.get("preferred_power_w")),
                "requested_energy_kwh": requested,
                "target_type": "energy",
                "target_basis": "grid_to_battery",
                "target_energy_kwh": target,
                "min_soc_after": minimum_soc,
                "allow_partial": bool(profile.get("allow_partial", True)),
                "minimum_confidence": max(0.0, min(100.0, _finite(profile.get("minimum_confidence"), 0))),
                "charge_source": "grid",
                "purpose": "sale",
                "deadline": profile.get("deadline"),
                "deadline_index": later,
                "use_corrected_pv": True,
                "preserve_pv_room": False,
                "minimum_free_room_kwh": 0.0,
                "profitable_only": True,
                "expected_margin": round(margin, 6),
                "future_target_type": "sale",
                "future_target_hour": later,
                "future_target_price": sell,
                "price": buy,
            }))

    allocation_overrides = (
        inputs.get("_profile_allocation_overrides")
        if isinstance(inputs.get("_profile_allocation_overrides"), dict)
        else {}
    )
    allocation_metadata: dict[tuple[str, str], Any] = {}

    # Convert each user's energy target into explicit per-hour requests before
    # resolving conflicts between profiles.  This keeps profile intent separate
    # from the battery simulation and makes all three distribution modes
    # deterministic.
    for pool_key in sorted(profile_pool_specs):
        profile_id, profile_date = pool_key
        rows = profile_candidates.get(pool_key, [])
        sample = rows[0][1] if rows else profile_pool_specs[pool_key]
        target = max(0.0, _finite(sample.get("target_energy_kwh"), 0))
        is_soc_target = sample["action"] == "charge" and sample.get("target_type") == "soc"
        method = str(sample.get("distribution_method") or "best_hours")
        if sample["action"] == "sell":
            ordered = sorted(rows, key=lambda item: (-item[2], item[0])) if method == "best_hours" else sorted(rows)
        else:
            ordered = sorted(rows, key=lambda item: (item[2], item[0])) if method == "best_hours" else sorted(rows)
        price_band = _price_equivalence_band(inputs)
        equivalence_groups = (
            _price_equivalence_groups(ordered, price_band)
            if sample["action"] == "sell" and method == "best_hours"
            else [[item] for item in ordered]
        )
        group_by_index: dict[int, int] = {}
        for group_rank, group in enumerate(equivalence_groups):
            for index, request, price in group:
                group_by_index[index] = group_rank
                request["economic_value"] = price
                request["price_equivalence_band"] = price_band
                request["price_equivalence_group"] = group_rank
                request["price_equivalence_group_size"] = len(group)
                request["allocation_reason_codes"] = (
                    ["near_equal_price_group", "peak_power_balancing"]
                    if len(group) > 1 and method == "best_hours"
                    else []
                )
        capacities = {
            index: _profile_slot_capacity_kwh(inputs, request, index, default_power_w)
            for index, request, _price in ordered
        }
        profile_override = allocation_overrides.get(str(profile_id))
        if isinstance(profile_override, dict) and isinstance(profile_override.get(profile_date), dict):
            profile_override = profile_override[profile_date]
        elif not isinstance(profile_override, dict):
            profile_override = None
        remaining = target
        allocations: dict[int, float] = {}
        waterfill_allocations: dict[int, float] | None = None
        if (
            profile_override is None
            and sample["action"] == "sell"
            and method == "best_hours"
        ):
            waterfill_allocations = {}
            for group in equivalence_groups:
                group_target = min(
                    remaining,
                    sum(max(0.0, capacities.get(item[0], 0.0)) for item in group),
                )
                group_allocations = _waterfill_group(
                    group,
                    capacities,
                    group_target,
                    inputs,
                )
                waterfill_allocations.update(group_allocations)
                remaining = max(0.0, remaining - sum(group_allocations.values()))
                if remaining <= 1e-9:
                    break
            remaining = target
        for position, (index, request, _price) in enumerate(ordered):
            cap = capacities[index]
            if profile_override is not None:
                requested = max(
                    0.0,
                    _finite(
                        profile_override.get(index, profile_override.get(str(index))),
                        0.0,
                    ),
                )
                if not is_soc_target:
                    requested = min(cap, requested)
            elif is_soc_target:
                requested = None
            elif waterfill_allocations is not None:
                requested = min(cap, max(0.0, waterfill_allocations.get(index, 0.0)))
            elif method == "even":
                requested = min(cap, target / len(ordered)) if ordered else 0.0
            elif method == "constant_power":
                remaining_slots = max(1, len(ordered) - position)
                requested = min(cap, remaining / remaining_slots)
            else:
                requested = min(cap, remaining)
            if requested is not None:
                remaining = max(0.0, remaining - requested)
                allocations[index] = requested
                if requested <= 1e-9 and index >= int(_finite(inputs.get("current_hour"), 0)):
                    continue
            request["requested_energy_kwh"] = requested
            request["slot_capacity_kwh"] = cap
            request["capacity_limit_reasons"] = (
                _sell_capacity_limit_reasons(inputs, request.get("power_limit_w"))
                if request.get("action") == "sell"
                else []
            )
            request["started_hour_limited"] = bool(
                index == int(_finite(inputs.get("current_hour"), 0))
                and _slot_capacity_hours(inputs, index) < 1.0 - 1e-9
            )
            candidates.setdefault(index, []).append(request)
        allocation_metadata[pool_key] = {
            "profile_id": profile_id,
            "date": profile_date,
            "target_kwh": target,
            "basis": sample.get("target_basis"),
            "method": method,
            "price_equivalence_band": price_band,
            "equivalence_groups": [
                [index for index, _request, _price in group]
                for group in equivalence_groups
            ],
            "group_by_index": group_by_index,
            "ordered_indices": [index for index, _request, _price in ordered],
            "capacities_kwh": capacities,
            "allocations_kwh": allocations,
            "capacity_limit_reasons": list(dict.fromkeys(
                reason
                for _index, request, _price in ordered
                for reason in request.get("capacity_limit_reasons", [])
            )),
        }
    for index, request in supporting_charge_requests:
        candidates.setdefault(index, []).append(request)
    result = {}
    for index, rows in candidates.items():
        rows.sort(
            key=lambda row: (row["required"], row["priority"], row["action"] == "sell", row["profile_id"]),
            reverse=True,
        )
        result[index] = rows[0]
    if return_metadata:
        return result, allocation_metadata
    return result


def _baseline_action(inputs: dict[str, Any], index: int) -> dict[str, Any]:
    schedule = inputs.get("baseline_schedule")
    if not isinstance(schedule, list) or index >= len(schedule) or not isinstance(schedule[index], dict):
        return {"action": "none", "mode": "Bez zmiany", "reason": "baseline:no-scheduled-change"}
    slot = schedule[index]
    mode = str(slot.get("mode") or "")
    enabled = bool(slot.get("enabled"))
    if not enabled:
        return {"action": "none", "mode": "Bez zmiany", "reason": "baseline:disabled-slot"}
    if mode == "Selling First":
        return {
            "action": "sell",
            "mode": mode,
            "reason": "baseline:existing-sell-slot",
            "power_limit_w": _finite(slot.get("sell_power_w"), 0),
        }
    if mode == "Charge" and bool(slot.get("charge_enabled")):
        return {
            "action": "charge",
            "mode": mode,
            "reason": "baseline:existing-charge-slot",
            "power_limit_w": _finite(slot.get("charge_power_w"), 0),
        }
    return {"action": "none", "mode": mode or "Bez zmiany", "reason": "baseline:existing-normal-slot"}


def _strategy_actions(
    inputs: dict[str, Any],
    strategy: str,
    prices: dict[str, Any],
    forecast: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = STRATEGIES[strategy]
    current_hour = max(0, min(23, int(_finite(inputs.get("current_hour")))))
    allow_sell = bool(inputs.get("allow_battery_sell", True))
    allow_charge = bool(inputs.get("allow_grid_charge", True)) and (
        bool(inputs.get("price_includes_distribution"))
        or bool(inputs.get("osd_data_complete", True))
    )
    minimum_sell = _finite(inputs.get("min_sell_price"), 0)
    maximum_buy = _finite(inputs.get("max_buy_price"), 999)
    efficiency = max(0.5, min(1.0, _finite(inputs.get("battery_efficiency"), 0.9)))
    profile_requests = _profile_requests(inputs, prices)
    profiles = (
        inputs.get("user_profiles", {}).get("profiles", {})
        if isinstance(inputs.get("user_profiles"), dict)
        else {}
    )
    explicit_charge_profile = any(
        isinstance(profile, dict)
        and profile.get("enabled")
        and (str(key) == "charging" or str(profile.get("type")).lower() == "charging")
        for key, profile in profiles.items()
    ) if isinstance(profiles, dict) else False
    positive_sell_prices = [
        value
        for day in prices["sell"]
        for value in day.values()
        if value > 0
    ]
    horizon_peak = max(positive_sell_prices, default=0.0)
    automatic_sell_threshold = max(0.0, minimum_sell, horizon_peak * 0.90)
    actions = [{"action": "none", "mode": "Bez zmiany", "reason": "optimizer:no-profitable-change"} for _ in range(48)]
    load, load_known = _load_profile_quality(inputs)
    operational_pv = (
        forecast.get({"low": "operational_low", "high": "operational_high"}.get(
            str(cfg["forecast_quantile"]), "operational"
        ), [0.0] * 48)
        if isinstance(forecast, dict)
        else [0.0] * 48
    )
    cycle_cost = max(0.0, _finite(inputs.get("battery_cycle_cost_per_kwh"), 0.0))

    # First select export opportunities. A battery kWh is retained when its
    # evidenced value for a later uncovered home load is higher than selling it
    # now. Missing load evidence is handled fail-safe in the chronological
    # simulation and never silently becomes additional sellable energy.
    for index in range(current_hour, 48):
        day_index, hour = divmod(index, 24)
        sell_price = prices["sell"][day_index].get(hour)
        if allow_sell and sell_price is not None and sell_price >= automatic_sell_threshold:
            future_home_values = [
                prices["effective_buy"][later // 24].get(later % 24)
                for later in range(index + 1, 48)
                if load_known[later]
                and load[later] > max(0.0, _finite(operational_pv[later])) + 1e-9
                and prices["effective_buy"][later // 24].get(later % 24) is not None
            ]
            future_home_value = max(future_home_values, default=None)
            if future_home_value is not None and future_home_value > sell_price + 1e-9:
                actions[index] = {
                    "action": "none",
                    "mode": "Bez zmiany",
                    "reason": "optimizer:preserve-for-expensive-home-load",
                    "future_target_type": "home_load",
                    "future_target_price": future_home_value,
                }
                continue
            actions[index] = {
                "action": "sell",
                "mode": "Selling First",
                "reason": "optimizer:high-net-export-price",
            }

    # Then value every potential grid charge against an action which remains in
    # the final local policy: a later selected sale or an evidenced expensive
    # home load. This prevents orphaned charge-before-sale reasons.
    for index in range(current_hour, 48):
        if actions[index].get("action") != "none":
            continue
        day_index, hour = divmod(index, 24)
        buy_price = prices["effective_buy"][day_index].get(hour)
        future_sales = [
            (later, prices["sell"][later // 24].get(later % 24))
            for later in range(index + 1, 48)
            if actions[later].get("action") == "sell"
        ]
        future_sales = [
            (later, value)
            for later, value in future_sales
            if value is not None and value > 0
        ]
        future_home = [
            (later, prices["effective_buy"][later // 24].get(later % 24))
            for later in range(index + 1, 48)
            if load_known[later]
            and load[later] > max(0.0, _finite(operational_pv[later])) + 1e-9
        ]
        future_home = [(later, value) for later, value in future_home if value is not None]
        if (
            explicit_charge_profile
            or not allow_charge
            or buy_price is None
            or buy_price > maximum_buy
            or (not future_sales and not future_home)
        ):
            continue
        opportunities: list[tuple[str, int, float, float]] = []
        if future_sales:
            future_hour, future_value = max(future_sales, key=lambda item: (item[1], -item[0]))
            opportunities.append((
                "sale",
                future_hour,
                future_value,
                future_value * efficiency - buy_price - 2 * cycle_cost,
            ))
        if future_home:
            future_hour, future_value = max(future_home, key=lambda item: (item[1], -item[0]))
            opportunities.append((
                "home_load",
                future_hour,
                future_value,
                future_value * efficiency - buy_price - 2 * cycle_cost,
            ))
        target_type, future_hour, future_value, raw_margin = max(
            opportunities, key=lambda item: (item[3], -item[1])
        )
        expected_margin = raw_margin - float(cfg["minimum_profit_threshold"])
        if expected_margin > 0:
            actions[index] = {
                "action": "charge",
                "mode": "Charge",
                "reason": (
                    "optimizer:profitable-charge-before-sale"
                    if target_type == "sale"
                    else "optimizer:profitable-charge-before-home-load"
                ),
                "purpose": "sale" if target_type == "sale" else "home",
                "future_target_type": target_type,
                "future_target_hour": future_hour,
                "future_target_price": future_value,
                "expected_margin": expected_margin,
            }
    if bool(inputs.get("_global_ranked")):
        capacity = max(0.1, _finite(inputs.get("battery_capacity_kwh"), 10))
        soc = max(0.0, min(100.0, _finite(inputs.get("soc"), 0)))
        directional_limit_kwh = max(
            0.001,
            _finite(inputs.get("effective_power_limit_w"), _finite(inputs.get("max_sell_power_w"), 5000)) / 1000.0,
        )
        terminal_soc = max(
            _finite(inputs.get("effective_min_soc"), _finite(inputs.get("min_soc"), 20)),
            float(cfg["terminal_soc_target"]),
        )
        # Rank against a full physically usable battery, not only initial SOC.
        # A low-SOC battery can first charge and then serve the best sell slot.
        usable_export = max(0.0, capacity * (100.0 - terminal_soc) / 100.0) * efficiency
        sale_slots = max(0, math.ceil(usable_export / directional_limit_kwh - 1e-9))
        automatic_sales = [
            index for index, item in enumerate(actions)
            if item.get("action") == "sell" and not item.get("profile_id")
        ]
        keep_sales = set(sorted(
            automatic_sales,
            key=lambda index: (-_finite(prices["sell"][index // 24].get(index % 24), -1), index),
        )[:sale_slots])
        for index in automatic_sales:
            if index not in keep_sales:
                actions[index] = {
                    "action": "none",
                    "mode": "Bez zmiany",
                    "reason": "shadow:lower-ranked-sale-hour",
                }
        room_input = max(0.0, capacity * (100.0 - soc) / 100.0) / max(0.5, efficiency)
        charge_slots = max(0, math.ceil(room_input / directional_limit_kwh - 1e-9))
        automatic_charges = [
            index for index, item in enumerate(actions)
            if item.get("action") == "charge" and not item.get("profile_id")
        ]
        keep_charges = set(sorted(
            automatic_charges,
            key=lambda index: (_finite(prices["effective_buy"][index // 24].get(index % 24), 999999), index),
        )[:charge_slots])
        for index in automatic_charges:
            if index not in keep_charges:
                actions[index] = {
                    "action": "none",
                    "mode": "Bez zmiany",
                    "reason": "shadow:higher-ranked-charge-hour",
                }
        for index in inputs.get("_global_excluded_sale_indices", []):
            if (
                isinstance(index, int)
                and 0 <= index < len(actions)
                and actions[index].get("action") == "sell"
                and not actions[index].get("profile_id")
            ):
                actions[index] = {
                    "action": "none",
                    "mode": "Bez zmiany",
                    "reason": "optimizer:terminal-reserve-48h",
                }
        for index in inputs.get("_global_excluded_charge_indices", []):
            if (
                isinstance(index, int)
                and 0 <= index < len(actions)
                and actions[index].get("action") == "charge"
                and not actions[index].get("profile_id")
            ):
                actions[index] = {
                    "action": "none",
                    "mode": "Bez zmiany",
                    "reason": "optimizer:orphaned-charge-removed",
                }
        for index in inputs.get("_global_forced_charge_indices", []):
            if (
                isinstance(index, int)
                and 0 <= index < len(actions)
                and not actions[index].get("profile_id")
            ):
                actions[index] = {
                    "action": "charge",
                    "mode": "Charge",
                    "reason": "optimizer:terminal-reserve-charge-48h",
                    "purpose": "terminal_reserve",
                    "charge_source": "grid",
                }
    for index, request in profile_requests.items():
        actions[index] = {
            "action": request["action"],
            "mode": "Charge" if request["action"] == "charge" else "Selling First",
            "reason": request["reason"],
            "profile_id": request["profile_id"],
            "profile_date": request.get("profile_date"),
            "power_limit_w": request.get("power_limit_w"),
            "target_soc": request.get("target_soc"),
            "required": request.get("required"),
            "priority": request.get("priority"),
            "goal_character": request.get("goal_character"),
            "requested_energy_kwh": request.get("requested_energy_kwh"),
            "slot_capacity_kwh": request.get("slot_capacity_kwh"),
            "started_hour_limited": request.get("started_hour_limited"),
            "capacity_limit_reasons": request.get("capacity_limit_reasons", []),
            "target_type": request.get("target_type"),
            "target_basis": request.get("target_basis"),
            "target_energy_kwh": request.get("target_energy_kwh"),
            "distribution_method": request.get("distribution_method"),
            "economic_value": request.get("economic_value"),
            "price_equivalence_band": request.get("price_equivalence_band"),
            "price_equivalence_group": request.get("price_equivalence_group"),
            "price_equivalence_group_size": request.get("price_equivalence_group_size"),
            "allocation_reason_codes": request.get("allocation_reason_codes", []),
            "min_soc_after": request.get("min_soc_after"),
            "allow_partial": request.get("allow_partial"),
            "minimum_confidence": request.get("minimum_confidence"),
            "charge_source": request.get("charge_source"),
            "max_grid_energy_kwh": request.get("max_grid_energy_kwh"),
            "preserve_pv_room": request.get("preserve_pv_room"),
            "minimum_free_room_kwh": request.get("minimum_free_room_kwh"),
            "profitable_only": request.get("profitable_only"),
            "purpose": request.get("purpose"),
            "deadline": request.get("deadline"),
            "deadline_index": request.get("deadline_index"),
            "charge_missing_only": request.get("charge_missing_only"),
            "use_corrected_pv": request.get("use_corrected_pv"),
            "expected_margin": request.get("expected_margin"),
            "future_target_type": request.get("future_target_type"),
            "future_target_hour": request.get("future_target_hour"),
            "future_target_price": request.get("future_target_price"),
        }
    # Read-only candidate simulations may replace at most five slots.  This is
    # an internal Core input, never a direct inverter command.
    candidate_actions = inputs.get("_candidate_actions")
    if isinstance(candidate_actions, dict):
        for raw_index, candidate in list(candidate_actions.items())[:5]:
            try:
                candidate_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if not 0 <= candidate_index < 48 or not isinstance(candidate, dict):
                continue
            candidate_action = str(candidate.get("action") or "none")
            if candidate_action not in {"none", "sell", "charge"}:
                continue
            actions[candidate_index] = {
                "action": candidate_action,
                "mode": "Charge" if candidate_action == "charge" else "Selling First" if candidate_action == "sell" else "Bez zmiany",
                "reason": "candidate:locally-resimulated",
                "power_limit_w": max(0.0, _finite(candidate.get("power_w"), 0.0)),
                "charge_source": "grid",
            }
    # Installation-wide safety switches always dominate user profiles.  A
    # profile may request an action, but it must never silently bypass the
    # operator's global permission for grid charging or battery export.
    for action_spec in actions:
        if action_spec["action"] == "sell" and not allow_sell:
            action_spec.update({
                "action": "none",
                "mode": "Bez zmiany",
                "reason": "safety:battery-sale-disabled",
            })
        elif action_spec["action"] == "charge" and not allow_charge:
            action_spec.update({
                "action": "none",
                "mode": "Bez zmiany",
                "reason": "safety:grid-charge-disabled",
            })
    return actions


def _core_action_contract(
    inputs: dict[str, Any],
    *,
    index: int,
    day: date,
    hour_start: datetime,
    hour_end: datetime,
    action: str,
    action_spec: dict[str, Any],
    planned_energy_kwh: float,
    planned_power_w: float,
    effective_min_soc: float,
    target_soc: float,
    confidence: float | None,
    net_result: float,
    reason_code: str,
    reason_summary: str,
    physical_limits: dict[str, float],
) -> dict[str, Any]:
    """Freeze the exact logical schedule values validated by this simulation."""
    baseline = inputs.get("baseline_schedule")
    baseline_slot = (
        baseline[index]
        if isinstance(baseline, list) and index < len(baseline) and isinstance(baseline[index], dict)
        else {}
    )
    voltage = _optional(inputs.get("battery_voltage_v"))
    estimated_current = (
        min(240.0, max(0.0, planned_power_w / voltage))
        if voltage is not None and voltage > 0 and planned_power_w > 0
        else None
    )
    existing_tou = _optional(baseline_slot.get("tou_soc"))
    existing_minimum_sell = _optional(baseline_slot.get("minimum_sell_soc"))
    existing_discharge = _optional(baseline_slot.get("discharge_current_a"))
    existing_charge = _optional(baseline_slot.get("charge_current_a"))
    existing_grid_charge = _optional(baseline_slot.get("grid_charge_current_a"))
    charge_from_grid = action == "charge" and str(action_spec.get("charge_source") or "grid") != "pv"
    minimum_sell_soc = (
        effective_min_soc if action == "sell" else existing_minimum_sell
    )
    tou_soc = target_soc if action == "charge" else existing_tou
    # A sell-power estimate is not the inverter's global maximum battery
    # discharge current.  Keep it diagnostic only; the user-owned physical
    # current limit is an input to feasibility and must never become a sell
    # schedule output.
    discharge_current = None if action == "sell" else existing_discharge
    charge_current = estimated_current if action == "charge" and estimated_current is not None else existing_charge
    grid_charge_current = (
        estimated_current
        if charge_from_grid and estimated_current is not None
        else 0.0
        if action == "charge" and not charge_from_grid
        else existing_grid_charge
    )
    schedule_update: dict[str, Any] = {
        "slot_key": f"{index % 24:02d}_{(index + 1) % 24:02d}",
        "enabled": True,
        "mode": "Sprzedaż" if action == "sell" else "Ładowanie" if action == "charge" else "Normalna Praca",
    }
    execution_fields = (
        (("sell_power", planned_power_w),)
        if action == "sell"
        else (
            ("discharge_current", discharge_current),
            ("charge_current", charge_current),
            ("grid_charge_current", grid_charge_current),
            ("tou_soc", tou_soc),
        )
        if action == "charge"
        else ()
    )
    for key, value in execution_fields:
        if value is not None:
            schedule_update[key] = round(float(value), 4)
    if action == "charge":
        schedule_update["charge_enabled"] = bool(charge_from_grid)
    return {
        "schema_version": 1,
        "date": day.isoformat(),
        "slot": schedule_update["slot_key"],
        "start": hour_start.isoformat(),
        "end": hour_end.isoformat(),
        "action": action,
        "source": (
            f"profile:{action_spec.get('profile_id')}"
            if action_spec.get("profile_id")
            else "optimizer"
        ),
        "profile_id": action_spec.get("profile_id"),
        "priority": action_spec.get("priority"),
        "goal_character": action_spec.get("goal_character"),
        "allow_partial": action_spec.get("allow_partial"),
        "planned_energy_kwh": round(planned_energy_kwh, 5),
        "planned_power_w": round(planned_power_w, 2),
        "effective_min_soc": round(effective_min_soc, 4),
        "minimum_sell_soc": round(minimum_sell_soc, 4) if minimum_sell_soc is not None else None,
        "target_soc": round(target_soc, 4),
        "tou_soc": round(tou_soc, 4) if tou_soc is not None else None,
        "charge_enabled": schedule_update.get("charge_enabled"),
        "charge_current": round(charge_current, 4) if charge_current is not None else None,
        "grid_charge_current": round(grid_charge_current, 4) if grid_charge_current is not None else None,
        "discharge_current": round(discharge_current, 4) if discharge_current is not None else None,
        "estimated_battery_current_a": (
            round(estimated_current, 4)
            if action == "sell" and estimated_current is not None
            else None
        ),
        "conversion": {
            "battery_voltage_v": round(voltage, 4) if voltage is not None else None,
            "basis": (
                "diagnostic_sell_power_divided_by_battery_voltage"
                if action == "sell" and estimated_current is not None
                else "planned_power_divided_by_battery_voltage"
                if estimated_current is not None
                else "existing_slot_fallback"
            ),
        },
        "deployment_ready": bool(action != "charge" or estimated_current is not None),
        "confidence": confidence,
        "net_result": round(net_result, 5),
        "reason_code": reason_code,
        "reason_summary": reason_summary,
        "constraints": dict(physical_limits),
        "schedule_update": schedule_update,
    }


def _simulate(
    inputs: dict[str, Any],
    strategy: str,
    *,
    baseline: bool,
    forecast: dict[str, Any],
    prices: dict[str, Any],
) -> dict[str, Any]:
    budget = _ACTIVE_CORE_BUDGET.get()
    if budget is not None:
        budget.consume("simulate_calls")
    cfg = STRATEGIES[strategy]
    start_date, generated = _parse_start(inputs)
    current_hour = max(0, min(23, int(_finite(inputs.get("current_hour")))))
    capacity = max(0.1, _finite(inputs.get("battery_capacity_kwh"), 10))
    soc_input = _optional(inputs.get("soc"))
    fail_closed = soc_input is None
    soc = max(0.0, min(100.0, soc_input if soc_input is not None else 0.0))
    charge_eff = max(0.5, min(1.0, _finite(inputs.get("charge_efficiency"), math.sqrt(
        max(0.5, min(1.0, _finite(inputs.get("battery_efficiency"), 0.9)))
    ))))
    discharge_eff = max(0.5, min(1.0, _finite(inputs.get("discharge_efficiency"), charge_eff)))
    hard_min = max(0.0, min(100.0, _finite(inputs.get("min_soc"), 20)))
    effective_min = max(hard_min, min(100.0, _finite(inputs.get("effective_min_soc"), hard_min)))
    strategy_min = min(100.0, effective_min + float(cfg["reserve_buffer_pct"]))
    target_max = max(strategy_min, min(100.0, _finite(inputs.get("target_soc"), 100)))
    raw_base_limit = max(0.0, _finite(
        inputs.get("effective_power_limit_w"),
        _finite(inputs.get("max_sell_power_w"), 5000),
    ))
    sell_power_step_w = max(1e-9, _finite(inputs.get("sell_power_step_w"), 1.0))
    sell_power_minimum_w = max(0.0, _finite(inputs.get("sell_power_minimum_w"), 0.0))
    sell_power_maximum_w = _optional(inputs.get("sell_power_maximum_w"))
    if sell_power_maximum_w is not None:
        raw_base_limit = min(raw_base_limit, max(0.0, sell_power_maximum_w))
    base_limit = raw_base_limit * float(cfg["power_limit_pct"]) / 100.0
    charge_limit_w = max(0.0, _finite(inputs.get("battery_charge_limit_w"), raw_base_limit))
    discharge_limit_w = max(0.0, _finite(inputs.get("battery_discharge_limit_w"), raw_base_limit))
    grid_import_limit_w = max(0.0, _finite(inputs.get("grid_import_limit_w"), raw_base_limit))
    grid_export_limit_w = max(0.0, _finite(inputs.get("grid_export_limit_w"), raw_base_limit))
    inverter_ac_limit_w = max(0.0, _finite(inputs.get("inverter_ac_limit_w"), raw_base_limit))
    raw_sell_power_limits = (
        inputs.get("sell_power_limits_w")
        if isinstance(inputs.get("sell_power_limits_w"), dict)
        else {}
    )
    power_reason_names = {
        "plan": "global_max_sell_power",
        "export": "export_limit",
        "inverter": "inverter_power",
        "entity": "max_sell_power_entity",
        "current_voltage": "current_voltage_battery_limit",
        "configured_battery_discharge": "configured_battery_discharge_limit",
    }
    discharge_limit_sources = {
        power_reason_names.get(str(name), str(name)): value
        for name, raw_value in raw_sell_power_limits.items()
        if (value := _optional(raw_value)) is not None and value > 0
    }
    charge_request = max(0.0, _finite(inputs.get("charge_kwh_per_hour"), capacity * 0.25))
    duration_first = max(1, min(60, int(_finite(inputs.get("current_hour_remaining_minutes"), 60))))
    load, load_known = _load_profile_quality(inputs)
    live_state = inputs.get("live_state") if isinstance(inputs.get("live_state"), dict) else {}
    current_partial = (
        inputs.get("current_hour_partial")
        if isinstance(inputs.get("current_hour_partial"), dict)
        else {}
    )
    history_map: dict[tuple[str, int], dict[str, Any]] = {}
    for item in inputs.get("historical_hours", []):
        if not isinstance(item, dict):
            continue
        date_key = str(item.get("local_date") or item.get("hour") or "")[:10]
        hour_value = item.get("local_hour")
        if hour_value is None:
            hour_text = str(item.get("hour") or "")[11:13]
            hour_value = int(hour_text) if hour_text.isdigit() else None
        if date_key and hour_value is not None:
            history_map[(date_key, int(hour_value))] = item
    actions = [
        _baseline_action(inputs, index)
        for index in range(48)
    ] if baseline else _strategy_actions(inputs, strategy, prices, forecast)
    cycle_cost_rate = max(0.0, _finite(inputs.get("battery_cycle_cost_per_kwh"), 0.0))
    configured_terminal_rate = _optional(inputs.get("terminal_energy_value_per_kwh"))
    known_future_buy_prices = [
        value
        for day_prices in prices["effective_buy"]
        for value in day_prices.values()
        if value is not None and value >= 0
    ]
    terminal_rate = (
        max(0.0, configured_terminal_rate)
        if configured_terminal_rate is not None
        else (min(known_future_buy_prices) * discharge_eff if known_future_buy_prices else 0.0)
    )
    terminal_value_basis = "configured" if configured_terminal_rate is not None else "minimum_known_import_price"
    rows = []
    totals = {
        "gross_export_revenue": 0.0,
        "import_energy_cost": 0.0,
        "distribution_cost": 0.0,
        "loss_cost": 0.0,
        "battery_cycle_cost": 0.0,
        "net_result": 0.0,
        "sold_kwh": 0.0,
        "bought_kwh": 0.0,
        "conversion_losses_kwh": 0.0,
        "battery_throughput_kwh": 0.0,
        "unpriced_import_kwh": 0.0,
        "unpriced_export_kwh": 0.0,
    }
    day_start_soc = soc
    day_summaries = []
    profile_energy: dict[tuple[str, str], float] = {}
    profile_grid_energy: dict[str, float] = {}
    profile_charge_remaining: dict[tuple[str, str], float] = {}
    profile_shortfall: dict[tuple[str, str], float] = {}
    for index in range(48):
        day_index, hour = divmod(index, 24)
        day = start_date + timedelta(days=day_index)
        hour_start = datetime.combine(
            day,
            datetime.min.time(),
            tzinfo=generated.tzinfo,
        ).replace(hour=hour)
        next_day = day + timedelta(days=1) if hour == 23 else day
        next_hour = 0 if hour == 23 else hour + 1
        hour_boundary_end = datetime.combine(
            next_day,
            datetime.min.time(),
            tzinfo=generated.tzinfo,
        ).replace(hour=next_hour)
        wall_duration = max(
            0,
            round(
                (
                    hour_boundary_end.astimezone(timezone.utc)
                    - hour_start.astimezone(timezone.utc)
                ).total_seconds()
                / 60
            ),
        )
        duration = duration_first if index == current_hour else wall_duration
        if day_index == 0 and hour < current_hour:
            duration = 0
        hour_end = (
            hour_boundary_end
            if index != current_hour
            else hour_start + timedelta(minutes=duration)
        )
        confidence, components = _confidence(inputs, day_index, bool(forecast["learned"]))
        effective_confidence = None if fail_closed else confidence
        action_spec = actions[index]
        action = action_spec["action"]
        missing_load_block = False
        if action == "sell" and not all(load_known[index:]):
            action_spec = {
                **action_spec,
                "action": "none",
                "mode": "Bez zmiany",
                "reason": "safety:missing-load-forecast",
            }
            action = "none"
            missing_load_block = True
        candidate_action = action
        required_confidence = max(0.0, min(100.0, _finite(action_spec.get("minimum_confidence"), 0)))
        confidence_blocked = bool(
            candidate_action in {"sell", "charge"}
            and confidence + 1e-9 < required_confidence
        )
        proposal_block_reason = (
            "missing_load_forecast" if missing_load_block else
            "slot_elapsed" if duration <= 0 and candidate_action in {"sell", "charge"} else
            "critical_input_missing" if fail_closed and candidate_action in {"sell", "charge"} else
            "confidence_below_profile_minimum" if confidence_blocked else
            None
        )
        if (
            duration <= 0
            or fail_closed
            or confidence + 1e-9 < _finite(action_spec.get("minimum_confidence"), 0)
        ):
            action = "none"
        power_limit = _optional(action_spec.get("power_limit_w"))
        if power_limit is None or power_limit <= 0:
            power_limit = base_limit
        slot_hours = duration / 60.0
        automatic_sell_minimum_w = (
            sell_power_minimum_w
            if baseline
            else _minimum_automatic_sell_power_w(inputs, action_spec)
        )
        action_limit_w = min(
            power_limit,
            charge_limit_w if action == "charge" else discharge_limit_w,
        )
        max_energy = action_limit_w / 1000 * slot_hours if action_limit_w > 0 else 0.0
        candidate_limit_w = min(
            power_limit,
            charge_limit_w if candidate_action == "charge" else discharge_limit_w,
        ) if candidate_action in {"sell", "charge"} else 0.0
        candidate_max_energy = candidate_limit_w / 1000.0 * slot_hours
        candidate_requested = _optional(action_spec.get("requested_energy_kwh"))
        if candidate_requested is None and candidate_action == "sell":
            candidate_requested = _optional(action_spec.get("target_energy_kwh"))
        if candidate_requested is None and candidate_action == "charge":
            candidate_requested = charge_request
        candidate_energy = min(
            candidate_max_energy,
            max(0.0, candidate_requested if candidate_requested is not None else candidate_max_energy),
        )
        candidate_power = (
            candidate_energy * 1000.0 / slot_hours
            if slot_hours > 0 and candidate_action in {"sell", "charge"}
            else 0.0
        )
        if candidate_action == "sell" and candidate_power > 0:
            candidate_power = quantize_power_w(
                candidate_power,
                step_w=sell_power_step_w,
                minimum_w=sell_power_minimum_w,
                maximum_w=min(candidate_power, candidate_limit_w),
            )
            if 0 < candidate_power < automatic_sell_minimum_w - 1e-9:
                candidate_power = 0.0
            candidate_energy = candidate_power / 1000.0 * slot_hours
        charge_budget = charge_limit_w / 1000 * slot_hours
        discharge_budget = discharge_limit_w / 1000 * slot_hours
        import_budget = grid_import_limit_w / 1000 * slot_hours
        export_budget = grid_export_limit_w / 1000 * slot_hours
        inverter_budget = inverter_ac_limit_w / 1000 * slot_hours
        quantile_key = {
            "low": "operational_low",
            "high": "operational_high",
        }.get(str(cfg["forecast_quantile"]), "operational")
        pv = max(0.0, _finite(forecast[quantile_key][index]))
        home = max(0.0, load[index])
        input_origin = "forecast"
        if day_index == 0 and hour == current_hour:
            duration_factor = duration / max(1.0, wall_duration)
            pv *= duration_factor
            home *= duration_factor
            live_pv = _optional(live_state.get("pv_power_w"))
            live_home = _optional(live_state.get("home_power_w"))
            partial_channels = current_partial.get("channels") if isinstance(current_partial.get("channels"), dict) else {}
            quality_scores = [
                _finite(details.get("average_quality_score"), 0.0)
                for details in partial_channels.values()
                if isinstance(details, dict)
            ]
            live_weight = (
                max(0.2, min(0.8, sum(quality_scores) / len(quality_scores) / 100.0))
                if quality_scores else 0.35
            )
            if live_pv is not None:
                projected = max(0.0, live_pv) / 1000.0 * duration / 60.0
                pv = pv * (1.0 - live_weight) + projected * live_weight
            if live_home is not None:
                projected = max(0.0, live_home) / 1000.0 * duration / 60.0
                home = home * (1.0 - live_weight) + projected * live_weight
            input_origin = "measured_anchor_plus_forecast"
        energy = capacity * soc / 100.0
        profile_id = str(action_spec.get("profile_id") or "")
        profile_date = str(action_spec.get("profile_date") or day.isoformat())
        profile_pool = (profile_id, profile_date)
        charge_remaining_pool = (
            (profile_id, "__soc_target__")
            if action_spec.get("target_type") == "soc"
            else profile_pool
        )
        if (
            action == "charge"
            and profile_id
            and action_spec.get("target_type") == "soc"
            and action_spec.get("charge_missing_only")
            and charge_remaining_pool not in profile_charge_remaining
        ):
            target_energy = capacity * min(
                target_max,
                max(strategy_min, _finite(action_spec.get("target_soc"), target_max)),
            ) / 100.0
            profile_charge_remaining[charge_remaining_pool] = max(0.0, target_energy - energy) / charge_eff
        automatic_terminal_floor = (
            float(cfg["terminal_soc_target"])
            if action == "sell" and not profile_id and not baseline
            else strategy_min
        )
        action_min_soc = max(
            strategy_min,
            automatic_terminal_floor,
            _finite(action_spec.get("min_soc_after"), strategy_min),
        )
        minimum_energy = capacity * min(100.0, action_min_soc) / 100.0
        higher_priority_profile_reserve = 0.0
        other_profile_future_reserve = 0.0
        same_profile_future_reserve = 0.0
        if action == "sell" and profile_id:
            current_rank = (
                1 if action_spec.get("required") else 0,
                int(_finite(action_spec.get("priority"), 50)),
            )
            current_price = prices["sell"][day_index].get(hour)
            protected: dict[tuple[str, str], tuple[int, float]] = {}
            same_profile_protected: list[tuple[int, float]] = []
            for later in range(index + 1, 48):
                later_spec = actions[later]
                later_profile = str(later_spec.get("profile_id") or "")
                later_date = str(later_spec.get("profile_date") or "")
                later_pool = (later_profile, later_date)
                if later_spec.get("action") != "sell" or not later_profile:
                    continue
                if later_date != profile_date:
                    continue
                later_price = prices["sell"][later // 24].get(later % 24)
                if later_profile == profile_id:
                    current_group = action_spec.get("price_equivalence_group")
                    later_group = later_spec.get("price_equivalence_group")
                    economically_better = (
                        current_group is not None
                        and later_group is not None
                        and int(later_group) < int(current_group)
                    ) or (
                        (current_group is None or later_group is None)
                        and later_price is not None
                        and current_price is not None
                        and later_price
                        > current_price + _price_equivalence_band(inputs) + 1e-9
                    )
                    if economically_better:
                        requested_later = max(
                            0.0,
                            _finite(later_spec.get("requested_energy_kwh"), 0.0),
                        )
                        if requested_later > 1e-9:
                            same_profile_protected.append((later, requested_later))
                    continue
                later_rank = (
                    1 if later_spec.get("required") else 0,
                    int(_finite(later_spec.get("priority"), 50)),
                )
                outranks = later_rank > current_rank or (
                    later_rank == current_rank
                    and later_price is not None
                    and current_price is not None
                    and later_price > current_price + 1e-9
                )
                if not outranks or later_pool in protected:
                    continue
                remaining = max(
                    0.0,
                    _finite(later_spec.get("target_energy_kwh"), 0.0)
                    - profile_energy.get(later_pool, 0.0),
                )
                protected[later_pool] = (later, remaining)
            if protected or same_profile_protected:
                first_protected = min([
                    *(item[0] for item in protected.values()),
                    *(item[0] for item in same_profile_protected),
                ])
                same_profile_future_reserve = (
                    sum(item[1] for item in same_profile_protected) / discharge_eff
                )
                other_profile_future_reserve = (
                    sum(item[1] for item in protected.values()) / discharge_eff
                )
                required_battery = (
                    other_profile_future_reserve + same_profile_future_reserve
                )
                forecast_key = {
                    "low": "operational_low",
                    "high": "operational_high",
                }.get(str(cfg["forecast_quantile"]), "operational")
                evidenced_surplus = sum(
                    max(0.0, _finite(forecast[forecast_key][later]) - load[later]) * charge_eff
                    for later in range(index + 1, first_protected + 1)
                    if load_known[later]
                )
                higher_priority_profile_reserve = max(0.0, required_battery - evidenced_surplus)
                minimum_energy = min(
                    capacity,
                    minimum_energy + higher_priority_profile_reserve,
                )
        action_target_soc = (
            _finite(action_spec.get("target_soc"), target_max)
            if action == "charge"
            else target_max
        )
        maximum_energy = capacity * max(strategy_min, min(target_max, action_target_soc)) / 100.0
        required_pv_room = max(0.0, _finite(action_spec.get("minimum_free_room_kwh"), 0))
        pv_forecast_source = (
            "corrected"
            if action_spec.get("use_corrected_pv", True)
            else "solcast_raw"
        )
        if action == "charge" and action_spec.get("preserve_pv_room"):
            room_series = (
                forecast["operational"]
                if pv_forecast_source == "corrected"
                else forecast["operational_raw"]
            )
            room_end = max(index + 1, min(48, int(_finite(action_spec.get("deadline_index"), index + 24))))
            predicted_surplus = sum(
                max(0.0, _finite(room_series[later]) - max(0.0, load[later]))
                for later in range(index + 1, room_end)
            )
            export_limit_kwh = max(
                0.0,
                _finite(inputs.get("grid_export_limit_w"), base_limit) / 1000.0,
            )
            possible_pv_export = sum(
                min(
                    export_limit_kwh,
                    max(0.0, _finite(room_series[later]) - max(0.0, load[later])),
                )
                for later in range(index + 1, room_end)
            )
            required_pv_room = min(
                capacity,
                max(required_pv_room, predicted_surplus - possible_pv_export),
            )
        else:
            predicted_surplus = 0.0
            possible_pv_export = 0.0
            maximum_energy = min(
                maximum_energy,
                max(minimum_energy, capacity - required_pv_room),
            )
        pv_to_home = min(pv, home, inverter_budget)
        pv_surplus = pv - pv_to_home
        remaining_home = home - pv_to_home
        pv_to_battery = (
            0.0
            if action == "sell" and action_spec.get("target_basis") == "total_export"
            else min(pv_surplus, charge_budget, max(0.0, maximum_energy - energy) / charge_eff)
        )
        energy += pv_to_battery * charge_eff
        charge_budget -= pv_to_battery
        inverter_budget = max(0.0, inverter_budget - pv_to_home)
        pv_export_available = max(0.0, pv_surplus - pv_to_battery)
        pv_to_grid = min(pv_export_available, export_budget, inverter_budget)
        pv_curtailed = max(0.0, pv_export_available - pv_to_grid)
        export_budget -= pv_to_grid
        inverter_budget -= pv_to_grid
        available = max(0.0, energy - minimum_energy)
        battery_to_home = min(remaining_home, discharge_budget, inverter_budget, available * discharge_eff)
        energy -= battery_to_home / discharge_eff
        discharge_budget -= battery_to_home
        inverter_budget -= battery_to_home
        requested_grid_home = max(0.0, remaining_home - battery_to_home)
        grid_to_home = min(requested_grid_home, import_budget)
        import_budget -= grid_to_home
        unmet_home_load = max(0.0, requested_grid_home - grid_to_home)
        grid_to_battery = 0.0
        battery_to_grid = 0.0
        profile_contribution = 0.0
        limit_reasons = []
        if other_profile_future_reserve > 1e-9:
            limit_reasons.append("higher_priority_profile_reserve")
        if same_profile_future_reserve > 1e-9:
            limit_reasons.append("higher_value_slot_reserved")
        requested_action_energy = 0.0
        requested_profile_contribution = 0.0
        if action == "charge":
            source = str(action_spec.get("charge_source") or "auto").lower()
            requested_setting = _optional(action_spec.get("requested_energy_kwh"))
            if action_spec.get("target_type") == "soc":
                requested_setting = max(0.0, maximum_energy - energy) / charge_eff
                if action_spec.get("charge_missing_only") and profile_id:
                    requested_setting = min(
                        requested_setting,
                        profile_charge_remaining.get(charge_remaining_pool, requested_setting),
                    )
            requested = min(
                charge_request if requested_setting is None else max(
                    0.0,
                    requested_setting + profile_shortfall.get(profile_pool, 0.0),
                ),
                max_energy,
            )
            requested_action_energy = requested
            max_grid = _optional(action_spec.get("max_grid_energy_kwh"))
            if max_grid is not None:
                requested = min(requested, max(0.0, max_grid - profile_grid_energy.get(profile_id, 0.0)))
            room = max(0.0, maximum_energy - energy)
            grid_to_battery = 0.0 if source == "pv" else min(
                requested,
                room / charge_eff,
                charge_budget,
                import_budget,
            )
            energy += grid_to_battery * charge_eff
            charge_budget -= grid_to_battery
            import_budget -= grid_to_battery
            profile_contribution = grid_to_battery
            if profile_id:
                profile_energy[profile_pool] = profile_energy.get(profile_pool, 0.0) + profile_contribution
                profile_grid_energy[profile_id] = profile_grid_energy.get(profile_id, 0.0) + grid_to_battery
                profile_shortfall[profile_pool] = max(0.0, requested - profile_contribution)
            requested_profile_contribution = requested
            if charge_remaining_pool in profile_charge_remaining:
                profile_charge_remaining[charge_remaining_pool] = max(
                    0.0,
                    profile_charge_remaining[charge_remaining_pool] - grid_to_battery,
                )
            if source == "pv":
                limit_reasons.append("pv_only_profile")
            if grid_to_battery + 1e-7 < requested:
                limit_reasons.append("target_soc")
        elif action == "sell":
            available = max(0.0, energy - minimum_energy)
            requested_contribution = _optional(action_spec.get("requested_energy_kwh"))
            if requested_contribution is None:
                requested_contribution = max_energy
            elif profile_id:
                requested_contribution += profile_shortfall.get(profile_pool, 0.0)
                target_energy = max(0.0, _finite(action_spec.get("target_energy_kwh"), 0.0))
                if target_energy > 0:
                    requested_contribution = min(
                        requested_contribution,
                        max(0.0, target_energy - profile_energy.get(profile_pool, 0.0)),
                    )
            requested_profile_contribution = max(0.0, requested_contribution)
            requested = requested_profile_contribution
            if action_spec.get("target_basis") == "total_export":
                requested = max(0.0, requested_profile_contribution - pv_to_grid)
            requested_action_energy = requested
            binding_discharge_reasons = [
                reason
                for reason, watts in discharge_limit_sources.items()
                if watts <= discharge_limit_w + 1e-6
            ]
            action_power_reason = (
                "profile_max_power"
                if _optional(action_spec.get("power_limit_w")) is not None
                and power_limit <= discharge_limit_w + 1e-6
                else "global_max_sell_power"
            )
            sell_caps = {
                action_power_reason: max_energy,
                "minimum_soc": available * discharge_eff,
                "grid_export_limit": export_budget,
                "inverter_ac_limit": inverter_budget,
            }
            for reason in binding_discharge_reasons or ["battery_discharge_limit"]:
                sell_caps[reason] = discharge_budget
            battery_to_grid = min(
                max_energy,
                max(0.0, requested),
                available * discharge_eff,
                discharge_budget,
                export_budget,
                inverter_budget,
            )
            raw_sell_power_w = (
                battery_to_grid * 1000.0 / slot_hours
                if slot_hours > 0
                else 0.0
            )
            final_sell_power_w = quantize_power_w(
                raw_sell_power_w,
                step_w=sell_power_step_w,
                minimum_w=sell_power_minimum_w,
                maximum_w=min(raw_sell_power_w, action_limit_w),
            )
            residual_below_minimum = bool(
                0 < final_sell_power_w < automatic_sell_minimum_w - 1e-9
            )
            if residual_below_minimum:
                final_sell_power_w = 0.0
                limit_reasons.extend([
                    "residual_below_minimum",
                    "minimum_auto_sell_power",
                ])
            battery_to_grid = final_sell_power_w / 1000.0 * slot_hours
            energy -= battery_to_grid / discharge_eff
            discharge_budget -= battery_to_grid
            export_budget -= battery_to_grid
            inverter_budget -= battery_to_grid
            profile_contribution = (
                min(requested_profile_contribution, pv_to_grid + battery_to_grid)
                if action_spec.get("target_basis") == "total_export"
                else battery_to_grid
            )
            if profile_id:
                profile_energy[profile_pool] = profile_energy.get(profile_pool, 0.0) + profile_contribution
                profile_shortfall[profile_pool] = max(
                    0.0,
                    requested_profile_contribution - profile_contribution,
                )
            if battery_to_grid + 1e-7 < requested:
                limit_reasons.append("dynamic_power_cap")
                active_limits = [
                    reason for reason, value in sell_caps.items()
                    if value <= battery_to_grid + 1e-7
                ]
                limit_reasons.extend(active_limits or ["physical_energy_budget"])
            slot_capacity = _optional(action_spec.get("slot_capacity_kwh"))
            if (
                profile_id
                and slot_capacity is not None
                and requested_profile_contribution + 1e-7 >= slot_capacity
            ):
                limit_reasons.extend(action_spec.get("capacity_limit_reasons", []))
        if pv_curtailed > 1e-7:
            limit_reasons.append("pv_curtailed_by_export_or_inverter_limit")
        if unmet_home_load > 1e-7:
            limit_reasons.append("grid_import_limit")
        if fail_closed:
            limit_reasons = ["missing_current_soc_fail_closed"]
        elif action_spec.get("started_hour_limited") and requested_profile_contribution > 0:
            limit_reasons.append("started_hour_duration")
        energy = min(maximum_energy, max(minimum_energy, energy))
        soc_end = energy / capacity * 100.0
        sell_price = prices["sell"][day_index].get(hour)
        buy_price = prices["buy"][day_index].get(hour)
        distribution = prices["distribution"][index]
        effective_buy = prices["effective_buy"][day_index].get(hour)
        canonical_buy_row = prices.get("canonical_buy_rows", {}).get(index)
        canonical_sell_row = prices.get("canonical_sell_rows", {}).get(index)
        export_energy = pv_to_grid + battery_to_grid
        import_energy = grid_to_home + grid_to_battery
        export_revenue = export_energy * sell_price if sell_price is not None else 0.0
        if prices.get("canonical") and effective_buy is not None:
            import_source_cost = import_energy * (effective_buy - distribution)
            distribution_cost = import_energy * distribution
        else:
            import_source_cost = import_energy * buy_price if buy_price is not None else 0.0
            distribution_cost = 0.0 if prices["included"] else import_energy * distribution
        losses = (
            (pv_to_battery + grid_to_battery) * (1.0 - charge_eff)
            + (battery_to_home + battery_to_grid) * (1.0 / discharge_eff - 1.0)
        )
        loss_cost = 0.0
        battery_throughput = (
            (grid_to_battery + pv_to_battery) * charge_eff
            + (battery_to_home + battery_to_grid) / discharge_eff
        ) / 2.0
        cycle_cost = battery_throughput * cycle_cost_rate
        unpriced_import = import_energy if buy_price is None else 0.0
        unpriced_export = export_energy if sell_price is None else 0.0
        net = export_revenue - import_source_cost - distribution_cost - loss_cost - cycle_cost
        for key, value in (
            ("gross_export_revenue", export_revenue),
            ("import_energy_cost", import_source_cost),
            ("distribution_cost", distribution_cost),
            ("loss_cost", loss_cost),
            ("battery_cycle_cost", cycle_cost),
            ("net_result", net),
            ("sold_kwh", export_energy),
            ("bought_kwh", import_energy),
            ("conversion_losses_kwh", losses),
            ("battery_throughput_kwh", battery_throughput),
            ("unpriced_import_kwh", unpriced_import),
            ("unpriced_export_kwh", unpriced_export),
        ):
            totals[key] += value
        planned_action_energy = (
            grid_to_battery
            if action == "charge"
            else battery_to_grid
            if action == "sell"
            else 0.0
        )
        proposed = (
            action != "none"
            and duration > 0
            and not fail_closed
            and planned_action_energy > 1e-6
        )
        # ``power_limit`` is only the upper bound used by the simulation.
        # The schedule, however, works with one fixed power value for the
        # whole slot.  Expose the power that actually corresponds to the
        # planned slot energy so that e.g. 1.00 kWh in a full hour becomes
        # 1000 W, not the profile's 5000 W ceiling.
        planned_power = (
            power_limit
            if baseline and proposed
            else planned_action_energy * 1000.0 * 60.0 / duration
            if proposed and duration > 0
            else 0.0
        )
        reason_codes = [str(action_spec.get("reason") or "optimizer:none")]
        reason_codes.extend(action_spec.get("allocation_reason_codes", []))
        if limit_reasons:
            reason_codes.extend(f"limit:{item}" for item in limit_reasons)
        future_sell_prices = [
            value
            for later in range(index + 1, 48)
            if (value := prices["sell"][later // 24].get(later % 24)) is not None
        ]
        future_best_sell = max(future_sell_prices, default=None)
        key_factors = []
        if sell_price is not None:
            key_factors.append(f"cena_sprzedazy={round(sell_price, 4)}")
        key_factors.append(f"soc_start={round(soc, 1)}%")
        key_factors.append(f"rezerwa={round(action_min_soc, 1)}%")
        if future_best_sell is not None:
            key_factors.append(f"najlepsza_pozniejsza_cena={round(future_best_sell, 4)}")
        if action == "sell":
            reason_summary = (
                "Wysoka cena, wystarczający SOC i zachowana rezerwa 48 h; "
                "energia ma niższą lub porównywalną wartość alternatywną później."
                if future_best_sell is None or sell_price is None or sell_price >= future_best_sell * discharge_eff
                else "Sprzedaż mieści się w budżecie energii 48 h mimo wyższej późniejszej ceny."
            )
        elif action == "charge":
            reason_summary = (
                "Niski koszt ładowania, dostępne miejsce w baterii i dodatnia wartość późniejszego użycia."
            )
        elif fail_closed:
            reason_summary = "Brak aktualnego, wiarygodnego SOC — Core działa fail-closed."
        elif duration <= 0:
            reason_summary = "Slot już minął."
        elif confidence + 1e-9 < _finite(action_spec.get("minimum_confidence"), 0):
            reason_summary = "Pewność danych jest niższa od minimum profilu."
        else:
            reason_summary = "Brak opłacalnej zmiany względem bieżącego planu i rezerwy 48 h."
        data_quality = {
            "forecast": "missing" if forecast["raw"][index] is None else "available",
            "load_profile": (
                inputs.get("load_profile_sources_48h", [{}] * 48)[index].get("source")
                if isinstance(inputs.get("load_profile_sources_48h"), list)
                and index < len(inputs.get("load_profile_sources_48h"))
                and isinstance(inputs.get("load_profile_sources_48h")[index], dict)
                else "hourly_or_fallback"
            ),
            "prices": "available" if sell_price is not None or buy_price is not None else "missing",
        }
        physical_limits = {
            "battery_charge_limit_w": round(charge_limit_w, 2),
            "battery_discharge_limit_w": round(discharge_limit_w, 2),
            "grid_import_limit_w": round(grid_import_limit_w, 2),
            "grid_export_limit_w": round(grid_export_limit_w, 2),
            "inverter_ac_limit_w": round(inverter_ac_limit_w, 2),
        }
        action_contract = _core_action_contract(
            inputs,
            index=index,
            day=day,
            hour_start=hour_start,
            hour_end=hour_end,
            action=action,
            action_spec=action_spec,
            planned_energy_kwh=planned_action_energy,
            planned_power_w=planned_power,
            effective_min_soc=strategy_min,
            target_soc=action_target_soc,
            confidence=effective_confidence,
            net_result=net,
            reason_code=reason_codes[0],
            reason_summary=reason_summary,
            physical_limits=physical_limits,
        )
        row = {
            "index": index,
            "day": "today" if day_index == 0 else "tomorrow",
            "date": day.isoformat(),
            "hour": hour,
            "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
            "hour_start": hour_start.isoformat(),
            "hour_end": hour_end.isoformat(),
            "duration_minutes": duration,
            "action": action,
            "profile_id": action_spec.get("profile_id"),
            "profile_date": action_spec.get("profile_date"),
            "required": bool(action_spec.get("required")),
            "decision_source": (
                f"profile:{action_spec.get('profile_id')}"
                if action_spec.get("profile_id")
                else "optimizer"
                if action != "none"
                else "baseline"
            ),
            "purpose": action_spec.get("purpose"),
            "deadline": action_spec.get("deadline"),
            "expected_margin": action_spec.get("expected_margin"),
            "future_target_type": action_spec.get("future_target_type"),
            "future_target_hour": action_spec.get("future_target_hour"),
            "future_target_price": action_spec.get("future_target_price"),
            "deadline_index": action_spec.get("deadline_index"),
            "pv_forecast_source": pv_forecast_source,
            "minimum_free_room_kwh": max(
                0.0,
                _finite(action_spec.get("minimum_free_room_kwh"), 0),
            ),
            "required_pv_room_kwh": round(required_pv_room, 5),
            "predicted_pv_surplus_kwh": round(predicted_surplus, 5),
            "possible_pv_export_kwh": round(possible_pv_export, 5),
            "max_soc_before_pv_pct": round(maximum_energy / capacity * 100.0, 4),
            "charge_source": (
                str(action_spec.get("charge_source") or "grid")
                if action == "charge"
                else None
            ),
            "mode": action_spec.get("mode", "Bez zmiany"),
            "proposed": proposed,
            "candidate_action": candidate_action if candidate_action in {"sell", "charge"} else None,
            "candidate_energy_kwh": round(candidate_energy, 5),
            "candidate_power_w": round(candidate_power, 2),
            "required_confidence": round(required_confidence, 1),
            "actual_confidence": effective_confidence,
            "candidate_source_profile": action_spec.get("profile_id"),
            "proposal_block_reason": proposal_block_reason,
            "blocked_reason": proposal_block_reason,
            "deployment_block_reason": (
                "critical_input_missing" if fail_closed else None
            ),
            "power_limit_w": round(action_limit_w if proposed else 0.0, 2),
            "planned_power_w": round(planned_power, 2),
            "planned_energy_kwh": round(
                grid_to_battery if action == "charge" else battery_to_grid if action == "sell" else 0.0,
                5,
            ),
            "requested_action_energy_kwh": round(max(0.0, requested_action_energy), 5),
            "requested_profile_contribution_kwh": round(
                max(0.0, requested_profile_contribution),
                5,
            ),
            "profile_contribution_kwh": round(max(0.0, profile_contribution), 5),
            "profile_target_basis": action_spec.get("target_basis"),
            "power_limit_source": (
                next(iter(dict.fromkeys(limit_reasons)), None)
                if action == "sell"
                else None
            ),
            "power_limit_sources_w": {
                **{key: round(value, 2) for key, value in discharge_limit_sources.items()},
                **(
                    {"profile_max_power": round(power_limit, 2)}
                    if action == "sell" and _optional(action_spec.get("power_limit_w")) is not None
                    else {}
                ),
            },
            "power_limit_reasons": list(dict.fromkeys(limit_reasons)),
            "power_basis": (
                next(iter(dict.fromkeys(limit_reasons)), "physical_energy_budget")
                if limit_reasons
                else "profile_energy_allocation"
                if profile_id and proposed
                else "optimizer_energy_allocation"
                if proposed
                else "no_action"
            ),
            "energy_kwh": round(
                grid_to_battery if action == "charge" else battery_to_grid if action == "sell" else 0.0,
                3,
            ),
            "target_soc": round(_finite(action_spec.get("target_soc"), target_max), 2),
            "minimum_sell_soc": action_contract["minimum_sell_soc"],
            "tou_soc": action_contract["tou_soc"],
            "charge_enabled": action_contract["charge_enabled"],
            "charge_current": action_contract["charge_current"],
            "grid_charge_current": action_contract["grid_charge_current"],
            "discharge_current": action_contract["discharge_current"],
            "estimated_battery_current_a": action_contract["estimated_battery_current_a"],
            "soc_start_pct": round(soc, 4),
            "soc_end_pct": round(soc_end, 4),
            "soc_after": round(soc_end, 1),
            "hard_min_soc_pct": round(hard_min, 4),
            "effective_min_soc_pct": round(strategy_min, 4),
            "pv_raw_kwh": _rounded(forecast["raw"][index]) if forecast["raw"][index] is not None else None,
            "solcast_kwh": round(forecast["raw"][index], 3) if forecast["raw"][index] is not None else None,
            "pv_corrected_kwh": _rounded(forecast["corrected"][index]) if forecast["corrected"][index] is not None else None,
            "corrected_pv_kwh": round(forecast["corrected"][index], 3) if forecast["corrected"][index] is not None else None,
            "forecast_low_kwh": round(forecast["low"][index], 3) if forecast["low"][index] is not None else None,
            "forecast_high_kwh": round(forecast["high"][index], 3) if forecast["high"][index] is not None else None,
            "pv_kwh": round(pv, 3),
            "load_kwh": round(home, 3),
            "home_load_kwh": round(home, 5),
            "pv_to_home_kwh": round(pv_to_home, 5),
            "pv_to_battery_kwh": round(pv_to_battery, 5),
            "pv_to_grid_kwh": round(pv_to_grid, 5),
            "pv_curtailed_kwh": round(pv_curtailed, 5),
            "grid_to_battery_kwh": round(grid_to_battery, 5),
            "battery_to_home_kwh": round(battery_to_home, 5),
            "battery_to_grid_kwh": round(battery_to_grid, 5),
            "grid_to_home_kwh": round(grid_to_home, 5),
            "unmet_home_load_kwh": round(unmet_home_load, 5),
            "physical_limits": physical_limits,
            "expected_import_kwh": round(import_energy, 5),
            "expected_export_kwh": round(export_energy, 5),
            "buy_price": buy_price,
            "distribution": round(distribution, 5),
            "distribution_price": round(distribution, 5),
            "effective_buy_price": effective_buy,
            "total_buy_price": effective_buy,
            "sell_price": sell_price,
            "canonical_buy_price": canonical_buy_row,
            "canonical_sell_price": canonical_sell_row,
            "economic_value": action_spec.get("economic_value", sell_price),
            "price_equivalence_band": round(_price_equivalence_band(inputs), 5),
            "price_equivalence_group": action_spec.get("price_equivalence_group"),
            "minimum_auto_sell_power_w": round(automatic_sell_minimum_w, 2),
            "export_revenue": round(export_revenue, 5),
            "import_cost": round(import_source_cost, 5),
            "distribution_cost": round(distribution_cost, 5),
            "loss_cost": round(loss_cost, 5),
            "conversion_losses_kwh": round(losses, 5),
            "battery_throughput_kwh": round(battery_throughput, 5),
            "financial_data_complete": unpriced_import <= 1e-9 and unpriced_export <= 1e-9,
            "battery_cycle_cost": round(cycle_cost, 5),
            "terminal_value": 0.0,
            "net_result": round(net, 5),
            "balance_pln": round(net, 2),
            "benefit": 0.0,
            "raw_confidence": confidence,
            "effective_confidence": effective_confidence,
            "confidence": effective_confidence,
            "confidence_components": components,
            "data_quality_score": _data_quality_score(components),
            "plan_confidence": effective_confidence,
            "reason_code": reason_codes[0],
            "reason_summary": reason_summary,
            "key_factors": key_factors,
            "reason_codes": reason_codes,
            "limit_reason": " / ".join(limit_reasons) if limit_reasons else None,
            "data_quality": data_quality,
            "input_origin": input_origin,
            "current_hour_partial": current_partial if day_index == 0 and hour == current_hour else None,
            "dispatch_status": "blocked" if fail_closed else "skipped" if not proposed else "planned",
            "weather_factor": (
                forecast["weather"][index]
                if index < len(forecast["weather"])
                else None
            ),
        }
        historical = history_map.get((day.isoformat(), hour))
        if duration <= 0 and historical is not None:
            historical_soc_start = _optional(historical.get("soc_start"))
            historical_soc_end = _optional(historical.get("soc_end"))
            row.update({
                "input_origin": "historical",
                "soc_source": "historical",
                "soc_start_pct": historical_soc_start,
                "soc_end_pct": historical_soc_end,
                "soc_after": round(historical_soc_end, 1) if historical_soc_end is not None else None,
                "pv_kwh": _optional(historical.get("pv_kwh")),
                "load_kwh": _optional(historical.get("load_kwh")),
                "home_load_kwh": _optional(historical.get("load_kwh")),
                "expected_import_kwh": _optional(historical.get("grid_import_kwh")),
                "expected_export_kwh": _optional(historical.get("grid_export_kwh")),
                "battery_charge_kwh": _optional(historical.get("battery_charge_kwh")),
                "battery_discharge_kwh": _optional(historical.get("battery_discharge_kwh")),
                "historical_quality": historical.get("channel_quality"),
                "historical_energy_balance": historical.get("energy_balance"),
            })
        elif day_index == 0 and hour == current_hour:
            row["soc_source"] = "measured"
        else:
            row["soc_source"] = "forecast"
        # Today/Tomorrow can deploy only concrete proposals. Keeping the full
        # contract off no-op/blocked rows avoids roughly 55 kB of repeated
        # schedule metadata in a stable 48-hour public bundle.
        if proposed:
            row["action_contract"] = action_contract
        rows.append(row)
        soc = soc_end
        if hour == 23:
            day_rows = [item for item in rows if item["day"] == row["day"]]
            day_summaries.append({
                "day": row["day"],
                "date": day.isoformat(),
                "start_soc": round(day_start_soc, 1),
                "end_soc": round(soc, 1),
                "sold_kwh": round(sum(_finite(item.get("expected_export_kwh")) for item in day_rows), 3),
                "bought_kwh": round(sum(_finite(item.get("expected_import_kwh")) for item in day_rows), 3),
                "balance_pln": round(sum(item["net_result"] for item in day_rows), 2),
                "confidence": confidence,
                "prices_available": bool(prices["sell"][day_index] or prices["buy"][day_index]),
                "financial_data_complete": all(
                    bool(item.get("financial_data_complete", False)) for item in day_rows
                ),
                "unpriced_import_kwh": round(sum(
                    _finite(item.get("expected_import_kwh"))
                    for item in day_rows if item.get("buy_price") is None
                ), 5),
                "unpriced_export_kwh": round(sum(
                    _finite(item.get("expected_export_kwh"))
                    for item in day_rows if item.get("sell_price") is None
                ), 5),
            })
            day_start_soc = soc
    terminal_energy = capacity * soc / 100.0
    terminal_value = terminal_energy * terminal_rate
    terminal_target_energy = capacity * float(cfg["terminal_soc_target"]) / 100.0
    terminal_shortfall = max(0.0, terminal_target_energy - terminal_energy)
    terminal_shortfall_penalty = terminal_shortfall * terminal_rate
    totals["terminal_value"] = terminal_value
    totals["terminal_value_rate"] = terminal_rate
    totals["terminal_value_basis"] = terminal_value_basis
    totals["terminal_target_shortfall_kwh"] = terminal_shortfall
    totals["terminal_shortfall_penalty"] = terminal_shortfall_penalty
    totals["financial_data_complete"] = (
        totals["unpriced_import_kwh"] <= 1e-9
        and totals["unpriced_export_kwh"] <= 1e-9
    )
    totals["net_result_with_terminal"] = totals["net_result"] + terminal_value - terminal_shortfall_penalty
    rows[-1]["terminal_value"] = round(terminal_value, 5)
    rows[-1]["net_result"] = round(rows[-1]["net_result"] + terminal_value, 5)
    checkpoints = {}
    for name, day_name, hour in (
        ("today_end", "today", 23),
        ("tomorrow_00", "tomorrow", 0),
        ("tomorrow_05", "tomorrow", 5),
        ("tomorrow_09", "tomorrow", 9),
        ("tomorrow_end", "tomorrow", 23),
    ):
        found = next((row for row in rows if row["day"] == day_name and row["hour"] == hour), None)
        checkpoints[name] = found["soc_after"] if found else None
    return {
        "rows": rows,
        "days": day_summaries,
        "checkpoints": checkpoints,
        "financials": {
            key: round(value, 5)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else value
            for key, value in totals.items()
        },
        "end_soc": round(soc, 4),
        "fail_closed": fail_closed,
    }


def _solve_profile_fulfillment(
    inputs: dict[str, Any],
    strategy: str,
    *,
    forecast: dict[str, Any],
    prices: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bounded local solver that returns post-clamp shortfall to target pools."""
    # Only the private allocation override is mutated.  A shallow snapshot keeps
    # the solver local without copying 48 h history/profile payloads per plan.
    solver_inputs = dict(inputs)
    pass_count = 0
    optimized: dict[str, Any] = {}
    final_metadata: dict[str, Any] = {}
    for pass_index in range(48):
        budget = _ACTIVE_CORE_BUDGET.get()
        if budget is not None:
            budget.consume("solver_passes")
        pass_count = pass_index + 1
        optimized = _simulate(
            solver_inputs,
            strategy,
            baseline=False,
            forecast=forecast,
            prices=prices,
        )
        _requests, allocation_metadata = _profile_requests(
            solver_inputs,
            prices,
            return_metadata=True,
        )
        final_metadata = allocation_metadata
        overrides = deepcopy(
            solver_inputs.get("_profile_allocation_overrides")
            if isinstance(solver_inputs.get("_profile_allocation_overrides"), dict)
            else {}
        )
        changed = False
        for pool_key, metadata in allocation_metadata.items():
            profile_id, profile_date = pool_key
            target = max(0.0, _finite(metadata.get("target_kwh"), 0.0))
            if target <= 1e-6:
                continue
            profile_rows = [
                row
                for row in optimized.get("rows", [])
                if str(row.get("profile_id") or "") == str(profile_id)
                and str(row.get("profile_date") or row.get("date") or "") == profile_date
            ]
            fulfilled = sum(
                max(0.0, _finite(row.get("profile_contribution_kwh"), 0.0))
                for row in profile_rows
            )
            remaining = max(0.0, target - fulfilled)
            if remaining <= 1e-6:
                continue
            current_allocations = {
                int(index): max(0.0, _finite(value, 0.0))
                for index, value in metadata.get("allocations_kwh", {}).items()
            }
            actual_by_index = {
                int(row.get("index")): max(
                    0.0,
                    _finite(row.get("profile_contribution_kwh"), 0.0),
                )
                for row in profile_rows
                if row.get("index") is not None
            }
            row_by_index = {
                int(row.get("index")): row
                for row in profile_rows
                if row.get("index") is not None
            }
            profile_changed = False
            redistribution_order: list[int] = []
            grouped_indices = metadata.get("equivalence_groups")
            if isinstance(grouped_indices, list):
                for group in grouped_indices:
                    if not isinstance(group, list):
                        continue
                    redistribution_order.extend(sorted(
                        (int(raw_index) for raw_index in group),
                        key=lambda candidate_index: (
                            actual_by_index.get(candidate_index, current_allocations.get(candidate_index, 0.0))
                            / max(1e-9, _slot_capacity_hours(inputs, candidate_index)),
                            candidate_index,
                        ),
                    ))
            if not redistribution_order:
                redistribution_order = [
                    int(raw_index) for raw_index in metadata.get("ordered_indices", [])
                ]
            for index in redistribution_order:
                allocated = current_allocations.get(index, 0.0)
                actual = actual_by_index.get(index, 0.0)
                # A slot already clamped below its request has no proven spare
                # capacity. Redistribute to another eligible slot instead.
                if allocated > 1e-6 and actual + 1e-6 < allocated:
                    continue
                capacity = max(
                    0.0,
                    _finite(metadata.get("capacities_kwh", {}).get(index), 0.0),
                )
                spare = max(0.0, capacity - allocated)
                if spare <= 1e-6:
                    continue
                addition = min(spare, remaining)
                row = row_by_index.get(index, {})
                if row.get("action") == "sell":
                    duration_minutes = max(
                        0.0,
                        _finite(row.get("duration_minutes"), 60.0),
                    )
                    energy_quantum = (
                        max(0.0, _finite(inputs.get("sell_power_step_w"), 1.0))
                        / 1000.0
                        * duration_minutes
                        / 60.0
                    )
                    # A residual smaller than one writable power increment can
                    # never alter the schedule.  Leave it in the fulfillment
                    # ledger instead of cycling the bounded solver over an
                    # allocation that the physical quantizer will discard.
                    if energy_quantum > 0 and addition + 1e-9 < energy_quantum:
                        continue
                    required_profile = bool(row.get("required"))
                    minimum_power_w = _minimum_automatic_sell_power_w(
                        inputs,
                        {"required": required_profile},
                    )
                    minimum_energy = (
                        minimum_power_w / 1000.0 * duration_minutes / 60.0
                    )
                    if (
                        not required_profile
                        and allocated + addition > 1e-9
                        and allocated + addition + 1e-9 < minimum_energy
                    ):
                        continue
                current_allocations[index] = allocated + addition
                remaining -= addition
                profile_changed = True
                if remaining <= 1e-6:
                    break
            if profile_changed:
                profile_overrides = overrides.get(str(profile_id))
                if not isinstance(profile_overrides, dict):
                    profile_overrides = {}
                profile_overrides[profile_date] = current_allocations
                overrides[str(profile_id)] = profile_overrides
                changed = True
        if not changed:
            break
        solver_inputs["_profile_allocation_overrides"] = overrides

    ledgers: dict[str, Any] = {}
    for pool_key in sorted(final_metadata):
        profile_id, profile_date = pool_key
        metadata = final_metadata[pool_key]
        rows = [
            row
            for row in optimized.get("rows", [])
            if str(row.get("profile_id") or "") == str(profile_id)
            and str(row.get("profile_date") or row.get("date") or "") == profile_date
        ]
        target = max(0.0, _finite(metadata.get("target_kwh"), 0.0))
        contributions = {
            str(int(row.get("index"))): round(
                max(0.0, _finite(row.get("profile_contribution_kwh"), 0.0)),
                5,
            )
            for row in rows
            if row.get("index") is not None
            and _finite(row.get("profile_contribution_kwh"), 0.0) > 1e-9
        }
        fulfilled = sum(contributions.values())
        daily_ledger = {
            "date": profile_date,
            "target_kwh": round(target, 5),
            "fulfilled_kwh": round(fulfilled, 5),
            "remaining_kwh": round(max(0.0, target - fulfilled), 5),
            "basis": metadata.get("basis"),
            "slot_contributions": contributions,
            "limiting_reasons": list(dict.fromkeys([
                *(
                    metadata.get("capacity_limit_reasons", [])
                    if target - fulfilled > 1e-6
                    else []
                ),
                *(
                    reason
                    for row in rows
                    for reason in row.get("power_limit_reasons", [])
                ),
            ])),
            "solver_passes": pass_count,
        }
        profile_ledger = ledgers.setdefault(str(profile_id), {
            "daily_target_kwh": round(target, 5),
            "days": {},
            "horizon_totals": {
                "target_kwh": 0.0,
                "fulfilled_kwh": 0.0,
                "remaining_kwh": 0.0,
            },
        })
        profile_ledger["days"][profile_date] = daily_ledger
        totals = profile_ledger["horizon_totals"]
        totals["target_kwh"] = round(totals["target_kwh"] + daily_ledger["target_kwh"], 5)
        totals["fulfilled_kwh"] = round(totals["fulfilled_kwh"] + daily_ledger["fulfilled_kwh"], 5)
        totals["remaining_kwh"] = round(totals["remaining_kwh"] + daily_ledger["remaining_kwh"], 5)
        first_date = min(profile_ledger["days"])
        first_day = profile_ledger["days"][first_date]
        # Compatibility fields represent the first local day, never a hidden
        # 48-hour pool. Consumers that need both days must use ``days`` or the
        # explicitly named ``horizon_totals``.
        profile_ledger.update({
            "date": first_date,
            "target_kwh": first_day["target_kwh"],
            "fulfilled_kwh": first_day["fulfilled_kwh"],
            "remaining_kwh": first_day["remaining_kwh"],
            "basis": first_day["basis"],
            "slot_contributions": first_day["slot_contributions"],
            "limiting_reasons": first_day["limiting_reasons"],
            "solver_passes": max(
                int(_finite(item.get("solver_passes"), 1))
                for item in profile_ledger["days"].values()
            ),
        })
    return optimized, ledgers


def _metadata(inputs: dict[str, Any], strategy: str, input_id: str, duration_ms: float = 0.0) -> dict[str, Any]:
    start_date, generated = _parse_start(inputs)
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=generated.tzinfo)
    raw_stage = inputs.get("learning_stage")
    status = (
        raw_stage.get("status", raw_stage.get("label"))
        if isinstance(raw_stage, dict)
        else raw_stage
    )
    recorded = int(_finite(inputs.get("recorded_days")))
    if not status:
        status = "gotowe" if recorded >= 14 else "wstępne uczenie"
    plan_seed = f"{input_id}:{strategy}:{ALGORITHM_VERSION}"
    return {
        "plan_id": hashlib.sha256(plan_seed.encode("utf-8")).hexdigest()[:24],
        "generated_at": generated.isoformat(),
        "horizon_start": start.isoformat(),
        "horizon_end": (start + timedelta(hours=48)).isoformat(),
        "generation_reason": str(inputs.get("generation_reason") or "input_snapshot_changed"),
        "algorithm_version": ALGORITHM_VERSION,
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "history_schema_version": int(_finite(inputs.get("history_schema_version"), HISTORY_SCHEMA_VERSION)),
        "input_snapshot_id": input_id,
        "selected_variant": strategy,
        "learning_status": status,
        "plan_status": "blocked" if _optional(inputs.get("soc")) is None else "proposal",
        "duration_ms": round(max(0.0, duration_ms), 3),
        "previous_plan_id": inputs.get("previous_plan_id"),
        "superseded_by_plan_id": None,
    }


def build_energy_plan(
    inputs: dict[str, Any],
    strategy: str = "balanced",
    *,
    analysis_detail: bool = True,
) -> dict[str, Any]:
    """Build one optimizer variant plus a comparable existing-schedule baseline."""
    selected = strategy if strategy in STRATEGIES else "balanced"
    learning_contract = (
        inputs.get("learning_stage")
        if isinstance(inputs.get("learning_stage"), dict)
        else {}
    )
    maturity_contract = (
        inputs.get("learning_maturity")
        if isinstance(inputs.get("learning_maturity"), dict)
        else {}
    )
    learning_apply_allowed = bool(
        maturity_contract.get("application_ready")
        if maturity_contract
        else learning_contract.get("apply_allowed", True)
    )
    input_id = snapshot_id(inputs)
    forecast = _forecast_series(inputs)
    prices = _prices(inputs)
    optimized, profile_fulfillment = _solve_profile_fulfillment(
        inputs,
        selected,
        forecast=forecast,
        prices=prices,
    )
    candidate_profile_fulfillment = deepcopy(profile_fulfillment)
    baseline = _simulate(inputs, selected, baseline=True, forecast=forecast, prices=prices)
    profile_definitions = (
        inputs.get("user_profiles", {}).get("profiles", {})
        if isinstance(inputs.get("user_profiles"), dict)
        and isinstance(inputs.get("user_profiles", {}).get("profiles"), dict)
        else {}
    )
    requires_profile_preflight = bool(analysis_detail) or any(
        isinstance(profile, dict)
        and profile.get("enabled")
        and (
            not bool(profile.get("allow_partial", True))
            or _finite(profile.get("min_net_result"), 0) > 0
        )
        for profile in profile_definitions.values()
    )
    profile_preflight: dict[str, dict[str, Any]] = {}
    blocked_profiles: list[str] = []
    for profile_id, profile in profile_definitions.items():
        if not isinstance(profile, dict) or not profile.get("enabled"):
            continue
        kind = "charging" if profile_id == "charging" or profile.get("type") == "charging" else "sale"
        rows = [row for row in optimized["rows"] if row.get("profile_id") == profile_id]
        configured_daily_target = _finite(
            profile.get("target_value")
            if kind == "charging" and profile.get("target_type") == "energy"
            else profile.get("target_energy_kwh"),
            0,
        )
        fulfillment = profile_fulfillment.get(str(profile_id), {})
        fulfillment_days = (
            fulfillment.get("days")
            if isinstance(fulfillment.get("days"), dict)
            else {}
        )
        possible = sum(
            max(0.0, _finite(item.get("fulfilled_kwh"), 0.0))
            for item in fulfillment_days.values()
            if isinstance(item, dict)
        )
        requested = sum(
            max(0.0, _finite(item.get("target_kwh"), configured_daily_target))
            for item in fulfillment_days.values()
            if isinstance(item, dict)
        )
        if not fulfillment_days:
            requested = configured_daily_target * len(_profile_local_dates(inputs, profile))
        counterfactual_result = optimized["financials"]["net_result_with_terminal"]
        incremental = 0.0
        if requires_profile_preflight:
            counterfactual_inputs = deepcopy(inputs)
            counterfactual_inputs["_blocked_profile_ids"] = [str(profile_id)]
            counterfactual, _counterfactual_fulfillment = _solve_profile_fulfillment(
                counterfactual_inputs,
                selected,
                forecast=forecast,
                prices=prices,
            )
            counterfactual_result = counterfactual["financials"]["net_result_with_terminal"]
            incremental = (
                optimized["financials"]["net_result_with_terminal"]
                - counterfactual_result
            )
        block_reason = None
        incomplete_days = [
            local_date
            for local_date, item in fulfillment_days.items()
            if isinstance(item, dict)
            and _finite(item.get("fulfilled_kwh"), 0.0) + 1e-6
            < _finite(item.get("target_kwh"), configured_daily_target)
        ]
        if requested > 0 and not bool(profile.get("allow_partial", True)) and incomplete_days:
            block_reason = "partial_not_allowed"
        elif (
            _finite(profile.get("min_net_result"), 0) > 0
            and incremental + 1e-6 < _finite(profile.get("min_net_result"), 0)
        ):
            block_reason = "min_net_result"
        profile_preflight[str(profile_id)] = {
            "possible_energy_kwh": possible,
            "requested_energy_kwh": requested,
            "daily_target_energy_kwh": configured_daily_target,
            "days": deepcopy(fulfillment_days),
            "incomplete_dates": incomplete_days,
            "profile_net_result_pln": incremental,
            "counterfactual_plan_result_pln": counterfactual_result,
            "block_reason": block_reason,
        }
        if block_reason:
            blocked_profiles.append(str(profile_id))
    if blocked_profiles:
        filtered_inputs = deepcopy(inputs)
        filtered_inputs["_blocked_profile_ids"] = blocked_profiles
        optimized, profile_fulfillment = _solve_profile_fulfillment(
            filtered_inputs,
            selected,
            forecast=forecast,
            prices=prices,
        )
    for profile_id, profile in profile_definitions.items():
        if not isinstance(profile, dict) or not profile.get("enabled"):
            continue
        kind = "charging" if profile_id == "charging" or profile.get("type") == "charging" else "sale"
        requested = max(0.0, _finite(
            profile.get("target_value")
            if kind == "charging" and profile.get("target_type") == "energy"
            else profile.get("target_energy_kwh"),
            0.0,
        ))
        if requested <= 0 or str(profile_id) in profile_fulfillment:
            continue
        candidate_ledger = candidate_profile_fulfillment.get(str(profile_id), {})
        preflight = profile_preflight.get(str(profile_id), {})
        reason = preflight.get("block_reason") or "price_filter_or_no_qualified_hours"
        basis = profile.get("target_basis") or (
            "grid_to_battery" if kind == "charging" else "battery_to_grid"
        )
        local_dates = _profile_local_dates(inputs, profile)
        days = {
            local_date: {
                "date": local_date,
                "target_kwh": round(requested, 5),
                "fulfilled_kwh": 0.0,
                "remaining_kwh": round(requested, 5),
                "basis": basis,
                "slot_contributions": {},
                "limiting_reasons": list(dict.fromkeys([
                    reason,
                    *candidate_ledger.get("limiting_reasons", []),
                ])),
                "solver_passes": candidate_ledger.get("solver_passes", 1),
            }
            for local_date in local_dates
        }
        first_date = local_dates[0] if local_dates else None
        first_day = days.get(first_date, {})
        profile_fulfillment[str(profile_id)] = {
            "date": first_date,
            "daily_target_kwh": round(requested, 5),
            "target_kwh": round(requested, 5),
            "fulfilled_kwh": 0.0,
            "remaining_kwh": round(requested, 5),
            "basis": basis,
            "slot_contributions": {},
            "limiting_reasons": first_day.get("limiting_reasons", [reason]),
            "solver_passes": candidate_ledger.get("solver_passes", 1),
            "candidate_fulfilled_kwh": candidate_ledger.get("fulfilled_kwh", 0.0),
            "days": days,
            "horizon_totals": {
                "target_kwh": round(requested * len(local_dates), 5),
                "fulfilled_kwh": 0.0,
                "remaining_kwh": round(requested * len(local_dates), 5),
            },
        }
    baseline_id = hashlib.sha256(f"{input_id}:baseline:{ALGORITHM_VERSION}".encode("utf-8")).hexdigest()[:24]
    optimized_result = optimized["financials"]["net_result_with_terminal"]
    baseline_result = baseline["financials"]["net_result_with_terminal"]
    benefit = optimized_result - baseline_result
    neutrality_threshold = max(0.20, abs(baseline_result) * 0.01)
    practically_same = abs(benefit) <= neutrality_threshold
    technical_changes = []
    for opt_row, base_row in zip(optimized["rows"], baseline["rows"]):
        opt_row["benefit"] = round(opt_row["net_result"] - base_row["net_result"], 5)
        fields = {
            "action": (base_row.get("action"), opt_row.get("action")),
            "mode": (base_row.get("mode"), opt_row.get("mode")),
            "planned_power_w": (
                round(_finite(base_row.get("planned_power_w")), 2),
                round(_finite(opt_row.get("planned_power_w")), 2),
            ),
            "planned_energy_kwh": (
                round(_finite(base_row.get("planned_energy_kwh")), 5),
                round(_finite(opt_row.get("planned_energy_kwh")), 5),
            ),
        }
        changed_fields = [name for name, values in fields.items() if values[0] != values[1]]
        opt_row["technical_difference"] = bool(changed_fields)
        opt_row["technical_changed_fields"] = changed_fields
        if changed_fields:
            technical_changes.append({
                "date": opt_row.get("date"),
                "hour": opt_row.get("hour"),
                "fields": changed_fields,
            })
        if practically_same and opt_row["proposed"]:
            opt_row["reason_codes"].append("comparison:practically-the-same")
    metadata = _metadata(inputs, selected, input_id)
    terminal = {
        "terminal_soc_target_pct": float(STRATEGIES[selected]["terminal_soc_target"]),
        "terminal_soc_actual_pct": optimized["end_soc"],
        "terminal_energy_kwh": round(
            _finite(inputs.get("battery_capacity_kwh"), 10) * optimized["end_soc"] / 100,
            5,
        ),
        "terminal_energy_value_pln": optimized["financials"]["terminal_value"],
        "terminal_value_delta_pln": round(
            optimized["financials"]["terminal_value"] - baseline["financials"]["terminal_value"],
            5,
        ),
    }
    financial_delta = {
        "export_revenue_delta": round(
            optimized["financials"]["gross_export_revenue"] - baseline["financials"]["gross_export_revenue"],
            5,
        ),
        "import_cost_delta": round(
            baseline["financials"]["import_energy_cost"] - optimized["financials"]["import_energy_cost"],
            5,
        ),
        "distribution_cost_delta": round(
            baseline["financials"]["distribution_cost"] - optimized["financials"]["distribution_cost"],
            5,
        ),
        "loss_cost_delta": round(
            baseline["financials"]["loss_cost"] - optimized["financials"]["loss_cost"],
            5,
        ),
        "battery_cycle_cost_delta": round(
            baseline["financials"]["battery_cycle_cost"] - optimized["financials"]["battery_cycle_cost"],
            5,
        ),
        "terminal_value_delta": terminal["terminal_value_delta_pln"],
    }
    financial_delta["other_rounding_delta"] = round(benefit - sum(financial_delta.values()), 5)
    profile_impacts = []
    execution_rows = inputs.get("profile_execution") if isinstance(inputs.get("profile_execution"), list) else []
    horizon_start, _generated = _parse_start(inputs)
    horizon_dates = {
        horizon_start.isoformat(),
        (horizon_start + timedelta(days=1)).isoformat(),
    }
    for profile_id, profile in profile_definitions.items():
        if not isinstance(profile, dict):
            continue
        enabled = bool(profile.get("enabled"))
        profile_rows = [
            row
            for row in optimized["rows"]
            if f"profile:{profile_id}" in row.get("reason_codes", [])
        ]
        kind = "charging" if profile_id == "charging" or profile.get("type") == "charging" else "sale"
        requested = _finite(
            profile.get("target_value")
            if kind == "charging" and profile.get("target_type") == "energy"
            else profile.get("target_energy_kwh"),
            0,
        )
        preflight = profile_preflight.get(str(profile_id), {})
        fulfillment = profile_fulfillment.get(str(profile_id), {})
        fulfillment_days = fulfillment.get("days") if isinstance(fulfillment.get("days"), dict) else {}
        block_reason = preflight.get("block_reason")
        preflight_days = preflight.get("days") if isinstance(preflight.get("days"), dict) else {}
        active_dates = _profile_local_dates(inputs, profile)
        impact_days: dict[str, Any] = {}
        for local_date in active_dates:
            day_rows = [row for row in profile_rows if str(row.get("date") or "") == local_date]
            day_ledger = fulfillment_days.get(local_date, {})
            planned_day = (
                max(0.0, _finite(day_ledger.get("fulfilled_kwh"), 0.0))
                if enabled else 0.0
            )
            possible_day = max(
                planned_day,
                _finite(preflight_days.get(local_date, {}).get("fulfilled_kwh"), planned_day)
                if isinstance(preflight_days.get(local_date), dict)
                else planned_day,
            )
            actual_day = sum(
                _finite(
                    item.get("actual_energy_kwh", item.get("executed_energy_kwh", item.get("energy_kwh"))),
                    0,
                )
                for item in execution_rows
                if isinstance(item, dict)
                and str(item.get("profile_id") or "") == str(profile_id)
                and str(item.get("date") or "") == local_date
            )
            day_target = max(0.0, _finite(day_ledger.get("target_kwh"), requested))
            day_missing = max(0.0, day_target - planned_day)
            impact_days[local_date] = {
                "date": local_date,
                "requested_energy_kwh": round(day_target, 5),
                "planned_energy_kwh": round(planned_day, 5),
                "possible_energy_kwh": round(possible_day, 5),
                "missing_energy_kwh": round(day_missing, 5),
                "actual_energy_kwh": round(actual_day, 5),
                "remaining_energy_kwh": round(max(0.0, day_target - actual_day), 5),
                "qualified_hours": len(day_rows),
                "limiting_reasons": list(day_ledger.get("limiting_reasons", [])),
            }
        primary_date = active_dates[0] if active_dates else horizon_start.isoformat()
        primary_day = impact_days.get(primary_date, {
            "requested_energy_kwh": requested,
            "planned_energy_kwh": 0.0,
            "possible_energy_kwh": 0.0,
            "missing_energy_kwh": requested,
            "actual_energy_kwh": 0.0,
            "remaining_energy_kwh": requested,
            "qualified_hours": 0,
            "limiting_reasons": [],
        })
        planned = _finite(primary_day.get("planned_energy_kwh"), 0.0)
        possible = _finite(primary_day.get("possible_energy_kwh"), planned)
        actual = _finite(primary_day.get("actual_energy_kwh"), 0.0)
        missing = _finite(primary_day.get("missing_energy_kwh"), max(0.0, requested - planned))
        if not enabled:
            status = "disabled"
        elif block_reason == "partial_not_allowed":
            status = "blocked_partial_not_allowed"
        elif block_reason == "min_net_result":
            status = "blocked_min_net_result"
        elif requested > 0 and actual + 1e-6 >= requested:
            status = "completed"
        elif actual > 0:
            status = "partially_executed"
        elif requested > 0 and planned + 1e-6 < requested and planned > 0:
            status = "partial"
        elif profile_rows:
            first_profile_row = min(
                profile_rows,
                key=lambda row: (0 if row.get("day") == "today" else 1, int(row.get("hour", 0))),
            )
            status = (
                "waiting"
                if first_profile_row.get("day") == "tomorrow"
                or int(first_profile_row.get("hour", 0)) > int(_finite(inputs.get("current_hour"), 0))
                else "running"
            )
        else:
            status = "no_qualified_hours"
        profile_impacts.append({
            "profile_id": profile_id,
            "profile_type": kind,
            "profile_name": str(profile.get("name") or profile_id),
            "enabled": enabled,
            "start": profile.get("start"),
            "end": profile.get("end"),
            "deadline": profile.get("deadline"),
            "allow_partial": bool(profile.get("allow_partial", True)),
            "purpose": _canonical_purpose(profile.get("purpose")),
            "requested_energy_kwh": round(requested, 5),
            "planned_energy_kwh": round(planned, 5),
            "possible_energy_kwh": round(possible, 5),
            "missing_energy_kwh": round(missing, 5),
            "actual_energy_kwh": round(actual, 5),
            "remaining_energy_kwh": round(max(0.0, requested - actual), 5),
            "qualified_hours": int(_finite(primary_day.get("qualified_hours"), 0)),
            "rejected_hours": 0,
            "minimum_price": _finite(profile.get("min_price", profile.get("minimum_price")), 0),
            "maximum_effective_price": _finite(
                profile.get("max_effective_price", profile.get("maximum_total_price")),
                0,
            ),
            "min_net_result": _finite(profile.get("min_net_result"), 0),
            "source": profile.get("source"),
            "preserve_pv_room": bool(profile.get("preserve_pv_room")),
            "minimum_free_room_kwh": max(
                0.0,
                _finite(profile.get("minimum_free_room_kwh"), 0),
            ),
            "average_realized_price": round(
                sum(
                    _finite(row["effective_buy_price"] if kind == "charging" else row["sell_price"])
                    for row in profile_rows
                ) / len(profile_rows),
                5,
            ) if profile_rows else None,
            "soc_before": profile_rows[0]["soc_start_pct"] if profile_rows else None,
            "soc_after": profile_rows[-1]["soc_end_pct"] if profile_rows else None,
            "expected_soc_after": profile_rows[-1]["soc_end_pct"] if profile_rows else None,
            "actual_net_result_pln": None,
            "expected_net_result_pln": round(sum(row["net_result"] for row in profile_rows), 5),
            "profile_net_result_pln": round(_finite(preflight.get("profile_net_result_pln")), 5),
            "block_reason": block_reason,
            "partial_execution": bool(enabled and requested > 0 and planned + 1e-6 < requested),
            "status": status,
            "skip_reason": None if profile_rows or not enabled else "no_qualified_hours",
            "limit_reason": next((row["limit_reason"] for row in profile_rows if row["limit_reason"]), None),
            "confidence": min(
                (row["confidence"] for row in profile_rows if row.get("confidence") is not None),
                default=None if optimized["fail_closed"] else 0,
            ),
            "date": primary_date,
            "days": impact_days,
            "horizon_totals": {
                "target_energy_kwh": round(sum(
                    _finite(item.get("requested_energy_kwh"), 0.0)
                    for item in impact_days.values()
                ), 5),
                "planned_energy_kwh": round(sum(
                    _finite(item.get("planned_energy_kwh"), 0.0)
                    for item in impact_days.values()
                ), 5),
                "actual_energy_kwh": round(sum(
                    _finite(item.get("actual_energy_kwh"), 0.0)
                    for item in impact_days.values()
                ), 5),
                "remaining_energy_kwh": round(sum(
                    _finite(item.get("remaining_energy_kwh"), 0.0)
                    for item in impact_days.values()
                ), 5),
            },
        })
    recommended_write_by_day: dict[str, dict[str, Any]] = {}
    empty_reason_by_day: dict[str, dict[str, str]] = {}
    execution_by_day: dict[str, dict[str, Any]] = {}
    for row in optimized["rows"]:
        if not isinstance(row, dict):
            continue
        has_candidate = row.get("candidate_action") in {"sell", "charge"}
        contract = row.get("action_contract") if isinstance(row.get("action_contract"), dict) else {}
        if row.get("proposed") and contract.get("deployment_ready") is False:
            row["deployment_block_reason"] = "action_contract_not_deployment_ready"
        elif has_candidate and not learning_apply_allowed:
            row["deployment_block_reason"] = "learning_evidence_insufficient"
    for day_name in ("today", "tomorrow"):
        day_rows = [row for row in optimized["rows"] if row.get("day") == day_name]
        day_summary = next((item for item in optimized["days"] if item.get("day") == day_name), {})
        baseline_summary = next((item for item in baseline["days"] if item.get("day") == day_name), {})
        day_benefit = _finite(day_summary.get("balance_pln")) - _finite(baseline_summary.get("balance_pln"))
        deployable_rows = [
            row
            for row in day_rows
            if row.get("proposed")
            and (
                not isinstance(row.get("action_contract"), dict)
                or row["action_contract"].get("deployment_ready") is not False
            )
        ]
        profile_proposal = any(row.get("profile_id") for row in deployable_rows)
        optimizer_proposal = any(not row.get("profile_id") for row in deployable_rows)
        candidates = [
            row for row in day_rows
            if row.get("candidate_action") in {"sell", "charge"}
        ]
        proposal_block_reason = next(
            (str(row.get("proposal_block_reason")) for row in candidates if row.get("proposal_block_reason")),
            None,
        )
        deployment_block_reason = next(
            (str(row.get("deployment_block_reason")) for row in candidates if row.get("deployment_block_reason")),
            None,
        )
        complete = bool(day_summary.get("financial_data_complete", False))
        allowed = bool(
            not optimized["fail_closed"]
            and learning_apply_allowed
            and complete
            and (profile_proposal or (optimizer_proposal and day_benefit > neutrality_threshold))
        )
        readiness_status = (
            "blocked" if optimized["fail_closed"] or not complete else
            "confirmable" if allowed else
            "preview"
        )
        readiness_label = {
            "blocked": "Zablokowany",
            "preview": "Podgląd",
            "confirmable": "Gotowy do potwierdzenia",
        }[readiness_status]
        execution_by_day[day_name] = {
            "status": readiness_status,
            "label": readiness_label,
            "candidate_count": len(candidates),
            "confirmable_count": len(deployable_rows) if allowed else 0,
            "proposal_block_reason": proposal_block_reason,
            "deployment_block_reason": deployment_block_reason,
        }
        recommended_write_by_day[day_name] = {
            "allowed": allowed,
            "financial_data_complete": complete,
            "benefit_vs_baseline_pln": round(day_benefit, 5),
            "proposal_block_reason": proposal_block_reason,
            "deployment_block_reason": deployment_block_reason,
            "execution_readiness": readiness_status,
            "reason": (
                "critical_input_missing"
                if optimized["fail_closed"]
                else "financial_data_incomplete"
                if not complete
                else proposal_block_reason
                if proposal_block_reason and not deployable_rows
                else deployment_block_reason
                if deployment_block_reason and not deployable_rows
                else "profile_confirmation_available"
                if profile_proposal
                else "positive_day_benefit"
                if optimizer_proposal and day_benefit > neutrality_threshold
                else "no_recommended_changes"
            ),
        }
        if optimized["fail_closed"]:
            empty_code = "core_blocked_missing_soc"
            empty_summary = "Core zablokowany — brak aktualnego, wiarygodnego SOC."
        elif any(row.get("proposed") for row in day_rows):
            empty_code = "proposals_available"
            empty_summary = "Core utworzył propozycje dla tego dnia."
        elif candidates and proposal_block_reason == "confidence_below_profile_minimum":
            empty_code = "confidence_below_profile_minimum"
            empty_summary = "Kandydaci są widoczni, lecz ich pewność jest niższa od minimum profilu."
        elif candidates and not learning_apply_allowed:
            empty_code = "learning_evidence_insufficient"
            empty_summary = "Kandydaci są dostępni do podglądu; profil nie ma jeszcze wystarczającego evidence."
        elif not complete:
            empty_code = "missing_prices"
            empty_summary = "Brak kompletnych cen potrzebnych do wiarygodnej propozycji."
        elif any("minimum profilu" in str(row.get("reason_summary")) for row in day_rows):
            empty_code = "confidence_below_minimum"
            empty_summary = "Pewność danych jest niższa od minimum aktywnego profilu."
        elif day_name == "today" and any(
            isinstance(profile, dict)
            and profile.get("enabled")
            and not _time_in_window(
                int(_finite(inputs.get("current_hour"))),
                profile.get("start"),
                profile.get("end"),
            )
            for profile in profile_definitions.values()
        ):
            empty_code = "profile_window_ended"
            empty_summary = "Aktywne okno profilu na dziś już się zakończyło albo jeszcze się nie rozpoczęło."
        elif abs(day_benefit) <= neutrality_threshold:
            empty_code = "current_plan_already_optimal"
            empty_summary = "Bieżący harmonogram jest już praktycznie optymalny finansowo."
        else:
            empty_code = "no_profitable_hours"
            empty_summary = "Brak opłacalnych godzin spełniających limity SOC, mocy i rezerwy."
        empty_reason_by_day[day_name] = {"code": empty_code, "summary": empty_summary}

    result = {
        **metadata,
        "strategy": selected,
        "variant_id": f"{metadata['plan_id']}:{selected}",
        "variant_settings": deepcopy(STRATEGIES[selected]),
        "rows": optimized["rows"],
        "days": optimized["days"],
        "checkpoints": optimized["checkpoints"],
        "financials": optimized["financials"],
        "terminal": terminal,
        "financial_delta": financial_delta,
        "profile_impacts": profile_impacts,
        "profile_fulfillment": profile_fulfillment,
        "baseline_plan_id": baseline_id,
        "baseline_result": round(baseline_result, 5),
        "optimized_result": round(optimized_result, 5),
        "benefit": round(benefit, 5),
        "neutrality_threshold": round(neutrality_threshold, 5),
        "comparison": "Praktycznie taki sam" if practically_same else "Lepszy" if benefit > 0 else "Gorszy",
        "comparison_details": {
            "financially_practically_same": practically_same,
            "technically_different": bool(technical_changes),
            "technical_change_count": len(technical_changes),
            "technical_changes": technical_changes,
        },
        # A profile is user policy, not implicit authorization for a physical
        # write.  Keep every concrete profile proposal behind the existing
        # confirmation/future-plan transaction even when joint optimization
        # finds a financially better slot elsewhere in the 48-hour horizon.
        "confirmation_required": bool(
            any(row.get("proposed") and row.get("profile_id") for row in optimized["rows"])
        ),
        "recommended_write": any(item["allowed"] for item in recommended_write_by_day.values()),
        "recommended_write_by_day": recommended_write_by_day,
        "execution_readiness": {
            "status": (
                "confirmable"
                if any(item["status"] == "confirmable" for item in execution_by_day.values())
                else "blocked"
                if all(item["status"] == "blocked" for item in execution_by_day.values())
                else "preview"
            ),
            "label": (
                "Gotowy do potwierdzenia"
                if any(item["status"] == "confirmable" for item in execution_by_day.values())
                else "Zablokowany"
                if all(item["status"] == "blocked" for item in execution_by_day.values())
                else "Podgląd"
            ),
            "by_day": execution_by_day,
        },
        "learning_maturity": deepcopy(maturity_contract),
        "plan_confidence": round(
            sum(_finite(item.get("confidence")) for item in optimized["days"])
            / max(1, len(optimized["days"])),
            1,
        ),
        "plan_confidence_by_day": {
            str(item.get("day")): item.get("confidence")
            for item in optimized["days"]
        },
        "empty_reason_by_day": empty_reason_by_day,
        "baseline": {
            "plan_id": baseline_id,
            "rows": baseline["rows"],
            "days": baseline["days"],
            "checkpoints": baseline["checkpoints"],
            "financials": baseline["financials"],
        },
        # The frontend consumes the exact same normalized price rows as the
        # optimizer.  Keeping this contract in the result prevents a second,
        # browser-side interpretation of provider-specific attributes.
        "canonical_prices": deepcopy(inputs.get("canonical_prices", {}))
        if isinstance(inputs.get("canonical_prices"), dict)
        else {},
        "data_quality": {
            "score": round(
                sum(_finite(row.get("data_quality_score")) for row in optimized["rows"])
                / max(1, len(optimized["rows"])),
                1,
            ),
            "learning_stage": str(
                learning_contract.get("status")
                or ("gotowe" if int(_finite(inputs.get("recorded_days"))) >= 14 else "wstępne uczenie")
            ),
            "learning_contract": deepcopy(learning_contract),
            "learning_maturity": deepcopy(maturity_contract),
            "learning_apply_allowed": learning_apply_allowed,
            "learning_dry_run": bool(learning_contract.get("dry_run", False)),
            "recorded_days": int(_finite(inputs.get("recorded_days"))),
            "pv_profile_learned": bool(forecast["learned"]),
            "load_profile_samples": int(_finite(inputs.get("load_profile_sample_count"))),
            "load_profile_rejected_samples": int(_finite(inputs.get("load_profile_rejected_count"))),
            "load_profile_covered_cells": int(_finite(inputs.get("load_profile_covered_cells"))),
            "load_profile_total_cells": int(_finite(inputs.get("load_profile_total_cells"), 168)),
            "pv_profile_samples": int(_finite(inputs.get("pv_profile_sample_count"))),
            "pv_profile_rejected_samples": int(_finite(inputs.get("pv_profile_rejected_count"))),
            "pv_profile_covered_cells": int(_finite(inputs.get("pv_profile_covered_cells"))),
            "pv_profile_total_cells": int(_finite(inputs.get("pv_profile_total_cells"), 288)),
            "today_sell_prices": len(prices["sell"][0]),
            "today_buy_prices": len(prices["buy"][0]),
            "tomorrow_sell_prices": len(prices["sell"][1]),
            "tomorrow_buy_prices": len(prices["buy"][1]),
            "osd_hours": _osd_available_hours(inputs),
            "weather_hours": sum(value is not None for value in forecast["weather"][:48]),
            "fail_closed": optimized["fail_closed"],
            "fail_closed_reason": (
                (inputs.get("soc_diagnostics") or {}).get("reason")
                if optimized["fail_closed"] and isinstance(inputs.get("soc_diagnostics"), dict)
                else None
            ),
            "soc": deepcopy(inputs.get("soc_diagnostics", {})),
            "osd_complete": _osd_available_hours(inputs) == 48,
            "price_sources": deepcopy(
                (inputs.get("canonical_prices") or {}).get("diagnostics", {})
                if isinstance(inputs.get("canonical_prices"), dict)
                else {}
            ),
            "usable_history_hours": int(_finite(
                (inputs.get("data_quality") or {}).get("usable_history_hours")
                if isinstance(inputs.get("data_quality"), dict)
                else 0
            )),
            "history_first_hour": (
                (inputs.get("data_quality") or {}).get("history_first_hour")
                if isinstance(inputs.get("data_quality"), dict)
                else None
            ),
            "history_last_hour": (
                (inputs.get("data_quality") or {}).get("history_last_hour")
                if isinstance(inputs.get("data_quality"), dict)
                else None
            ),
            "channel_diagnostics": deepcopy(
                (inputs.get("data_quality") or {}).get("channel_diagnostics", {})
                if isinstance(inputs.get("data_quality"), dict)
                else {}
            ),
        },
        "input_data_summary": {
            "history_schema_version": int(_finite(inputs.get("history_schema_version"), HISTORY_SCHEMA_VERSION)),
            "history_revision": inputs.get("history_revision"),
            "historical_hours_supplied": len(inputs.get("historical_hours", []))
            if isinstance(inputs.get("historical_hours"), list)
            else 0,
            "live_state": deepcopy(inputs.get("live_state", {}))
            if isinstance(inputs.get("live_state"), dict)
            else {},
            "current_hour_partial": deepcopy(inputs.get("current_hour_partial", {}))
            if isinstance(inputs.get("current_hour_partial"), dict)
            else {},
            "channel_diagnostics": deepcopy(
                (inputs.get("data_quality") or {}).get("channel_diagnostics", {})
                if isinstance(inputs.get("data_quality"), dict)
                else {}
            ),
        },
    }
    result["ui_insights"] = _ui_insights(
        inputs,
        prices,
        optimized["rows"],
        benefit,
        neutrality_threshold,
    )
    return _canonical(result)


def _budgeted_energy_plan(
    inputs: dict[str, Any],
    strategy: str,
    *,
    analysis_detail: bool,
) -> dict[str, Any]:
    budget = _ACTIVE_CORE_BUDGET.get()
    if budget is not None:
        budget.consume("build_energy_plan_calls")
    return build_energy_plan(inputs, strategy, analysis_detail=analysis_detail)


def _build_plan_bundle_unbudgeted(
    inputs: dict[str, Any], selected_strategy: str = "balanced"
) -> dict[str, Any]:
    """Run all variants independently and return the selected complete plan."""
    ranked_inputs = deepcopy(inputs)
    # Rank automatic charge/sale opportunities across the complete horizon.
    # The ranking uses prices, physical energy budgets, efficiency, cycle cost,
    # PV/load simulation and each strategy's terminal reserve; midnight never
    # resets the battery state.
    ranked_inputs["_global_ranked"] = True
    def ranked_variant(
        name: str, required_terminal: float
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        variant_inputs = deepcopy(ranked_inputs)
        excluded: list[int] = []
        excluded_charges: list[int] = []
        forced_charges: list[int] = []
        ineffective_charge_candidates: set[int] = set()
        for _iteration in range(128):
            variant_inputs["_global_excluded_sale_indices"] = excluded
            variant_inputs["_global_excluded_charge_indices"] = excluded_charges
            variant_inputs["_global_forced_charge_indices"] = forced_charges
            candidate = _budgeted_energy_plan(
                variant_inputs,
                name,
                analysis_detail=False,
            )
            if candidate["terminal"]["terminal_soc_actual_pct"] + 0.01 >= required_terminal:
                # A removed sale is never final merely because an earlier pass
                # lacked reserve. Re-evaluate it with all newly selected charge
                # actions and keep it when the complete plan stays feasible and
                # economically no worse.
                restored = False
                for sale_index in sorted(
                    excluded,
                    key=lambda index: (
                        -_finite(candidate["rows"][index].get("sell_price"), -1),
                        index,
                    ),
                ):
                    trial_inputs = deepcopy(variant_inputs)
                    trial_inputs["_global_excluded_sale_indices"] = [
                        index for index in excluded if index != sale_index
                    ]
                    trial = _budgeted_energy_plan(
                        trial_inputs,
                        name,
                        analysis_detail=False,
                    )
                    if (
                        trial["terminal"]["terminal_soc_actual_pct"] + 0.01 >= required_terminal
                        and trial["optimized_result"] + 1e-6 >= candidate["optimized_result"]
                        and trial["rows"][sale_index].get("proposed")
                    ):
                        excluded.remove(sale_index)
                        restored = True
                        break
                if restored:
                    continue

                # Remove an automatic charge whose promised sale no longer
                # exists. The terminal pass may replace it with an explicitly
                # labelled reserve charge when that energy is still required.
                orphaned = [
                    index
                    for index, row in enumerate(candidate["rows"])
                    if row.get("action") == "charge"
                    and row.get("decision_source") == "optimizer"
                    and row.get("reason_code") == "optimizer:profitable-charge-before-sale"
                    and (
                        not isinstance(row.get("future_target_hour"), int)
                        or not candidate["rows"][row["future_target_hour"]].get("proposed")
                        or candidate["rows"][row["future_target_hour"]].get("action") != "sell"
                    )
                    and index not in excluded_charges
                ]
                if orphaned:
                    excluded_charges.extend(orphaned)
                    continue
                return candidate, deepcopy(variant_inputs)
            forced_charge_allowed = bool(variant_inputs.get("allow_grid_charge", True)) and (
                bool(variant_inputs.get("price_includes_distribution"))
                or bool(variant_inputs.get("osd_data_complete", True))
            )
            charge_candidates = [
                index
                for index, row in enumerate(candidate["rows"])
                if row.get("action") == "none"
                and not row.get("profile_id")
                and row.get("effective_buy_price") is not None
                and _finite(row.get("duration_minutes"), 0) > 0
                and index not in forced_charges
                and index not in ineffective_charge_candidates
                and _finite(row.get("soc_end_pct"), 100)
                + 0.01
                < _finite(row.get("target_soc"), 100)
            ] if forced_charge_allowed else []
            charge_candidates.sort(key=lambda index: (
                _finite(candidate["rows"][index].get("effective_buy_price"), 999999),
                -index,
            ))
            improved = False
            for charge_index in charge_candidates:
                trial_inputs = deepcopy(variant_inputs)
                trial_inputs["_global_forced_charge_indices"] = [
                    *forced_charges,
                    charge_index,
                ]
                trial = _budgeted_energy_plan(
                    trial_inputs,
                    name,
                    analysis_detail=False,
                )
                if (
                    trial["terminal"]["terminal_soc_actual_pct"]
                    > candidate["terminal"]["terminal_soc_actual_pct"] + 0.01
                ):
                    forced_charges.append(charge_index)
                    improved = True
                    break
                ineffective_charge_candidates.add(charge_index)
            if improved:
                continue

            removable = [
                index
                for index, row in enumerate(candidate["rows"])
                if row.get("action") == "sell"
                and row.get("decision_source") == "optimizer"
                and index not in excluded
            ]
            if removable:
                # No feasible charge improved the terminal trajectory. Remove
                # only the globally least valuable automatic sale and run the
                # complete chronological simulation again.
                remove_index = min(
                    removable,
                    key=lambda index: (
                        _finite(candidate["rows"][index].get("sell_price"), -1),
                        -index,
                    ),
                )
                excluded.append(remove_index)
                ineffective_charge_candidates.clear()
                continue
            return candidate, deepcopy(variant_inputs)
        return candidate, deepcopy(variant_inputs)

    profit, profit_inputs = ranked_variant(
        "profit", float(STRATEGIES["profit"]["terminal_soc_target"])
    )
    balanced, balanced_inputs = ranked_variant(
        "balanced",
        max(
            float(STRATEGIES["balanced"]["terminal_soc_target"]),
            _finite(profit["terminal"]["terminal_soc_actual_pct"]),
        ),
    )
    safe, safe_inputs = ranked_variant(
        "safe",
        max(
            float(STRATEGIES["safe"]["terminal_soc_target"]),
            _finite(balanced["terminal"]["terminal_soc_actual_pct"]),
        ),
    )
    variants = {"safe": safe, "balanced": balanced, "profit": profit}
    variant_inputs = {
        "safe": safe_inputs,
        "balanced": balanced_inputs,
        "profit": profit_inputs,
    }
    selected = selected_strategy if selected_strategy in variants else "balanced"
    # Ranking trials need rows/terminal/score, not a separate counterfactual
    # solver and ledger analysis for every temporary candidate.  Rebuild only
    # the selected final candidate with the complete public 5G.4J contract.
    result = deepcopy(_budgeted_energy_plan(
        variant_inputs[selected],
        selected,
        analysis_detail=True,
    ))
    result["selected_strategy"] = selected
    result["variants"] = {
        key: {
            "variant_id": value["variant_id"],
            "variant_settings": value["variant_settings"],
            "days": value["days"],
            "checkpoints": value["checkpoints"],
            "financials": value["financials"],
            "terminal_soc_target_pct": value["terminal"]["terminal_soc_target_pct"],
            "terminal_soc_actual_pct": value["terminal"]["terminal_soc_actual_pct"],
            "baseline_result": value["baseline_result"],
            "optimized_result": value["optimized_result"],
            "benefit": value["benefit"],
            "comparison": value["comparison"],
            "recommended_write": value["recommended_write"],
        }
        for key, value in variants.items()
    }
    signatures = {
        key: [
            (row["action"], row["planned_energy_kwh"], row["soc_end_pct"])
            for row in value["rows"]
        ]
        for key, value in variants.items()
    }
    result["variant_equivalence"] = {
        "safe_equals_balanced": signatures["safe"] == signatures["balanced"],
        "balanced_equals_profit": signatures["balanced"] == signatures["profit"],
        "safe_equals_profit": signatures["safe"] == signatures["profit"],
    }
    shadow_inputs = deepcopy(inputs)
    shadow = _budgeted_energy_plan(
        shadow_inputs,
        selected,
        analysis_detail=False,
    )
    changed_slots = [
        {
            "index": index,
            "legacy_action": legacy_row.get("action"),
            "candidate_action": candidate_row.get("action"),
            "legacy_power_w": legacy_row.get("planned_power_w"),
            "candidate_power_w": candidate_row.get("planned_power_w"),
        }
        for index, (legacy_row, candidate_row) in enumerate(zip(result["rows"], shadow["rows"]))
        if (
            legacy_row.get("action"),
            legacy_row.get("planned_power_w"),
        ) != (
            candidate_row.get("action"),
            candidate_row.get("planned_power_w"),
        )
    ]
    result["optimizer_shadow"] = {
        "mode": "comparison_only",
        "legacy_plan_id": result["plan_id"],
        "candidate_plan_id": shadow["plan_id"],
        "candidate_algorithm": "legacy_unranked_comparison",
        "legacy_result": result["optimized_result"],
        "candidate_result": shadow["optimized_result"],
        "candidate_delta": round(shadow["optimized_result"] - result["optimized_result"], 5),
        "changed_slots": changed_slots,
        "manual_confirmation_required": True,
        "writes_performed": False,
    }
    return _canonical(result)


def build_plan_bundle(
    inputs: dict[str, Any], selected_strategy: str = "balanced"
) -> dict[str, Any]:
    """Build a complete bundle inside one deterministic, fail-closed budget."""
    budget = _CoreOperationBudget()
    token = _ACTIVE_CORE_BUDGET.set(budget)
    try:
        result = _build_plan_bundle_unbudgeted(inputs, selected_strategy)
    except CoreOperationBudgetExceeded as err:
        return _canonical({
            "budget_exceeded": True,
            "core_status": "budget_exceeded",
            "failure_reason": str(err),
            "plan_status": "blocked",
            "generation_reason": "core_budget_exceeded",
            "input_snapshot_id": snapshot_id(inputs),
            "selected_strategy": (
                selected_strategy if selected_strategy in STRATEGIES else "balanced"
            ),
            "rows": [],
            "recommended_write": False,
            "writes_performed": False,
            "core_budget": budget.public(),
        })
    finally:
        _ACTIVE_CORE_BUDGET.reset(token)
    result = dict(result)
    result["core_budget"] = budget.public()
    result["budget_exceeded"] = False
    return _canonical(result)


def simulate_alternative(
    inputs: dict[str, Any],
    *,
    strategy: str = "balanced",
    overrides: dict[str, Any] | None = None,
    changes: list[dict[str, Any]] | None = None,
    start_index: int = 0,
) -> dict[str, Any]:
    """Validate and locally re-simulate a read-only candidate plan."""
    merged = deepcopy(inputs)
    if overrides:
        merged.update(deepcopy(overrides))
    source_plan = build_energy_plan(merged, strategy)
    max_candidate_power_w = _finite(
        inputs.get("effective_power_limit_w"),
        DEFAULT_INVERTER_MAX_POWER_W,
    )
    profile_root = inputs.get("user_profiles") if isinstance(inputs.get("user_profiles"), dict) else {}
    profile_definitions = (
        profile_root.get("profiles")
        if isinstance(profile_root.get("profiles"), dict)
        else {}
    )
    start_date, _generated = _parse_start(inputs)
    normalized_changes: dict[int, dict[str, Any]] = {}
    for change in changes or []:
        if not isinstance(change, dict):
            raise ValueError("Candidate change must be an object")
        try:
            change_index = int(change.get("index"))
        except (TypeError, ValueError) as err:
            raise ValueError("Candidate index must be an integer") from err
        action = str(change.get("action") or "none")
        power_w = _optional(change.get("power_w"))
        if not 0 <= change_index < 48:
            raise ValueError("Candidate index is outside the 48-hour horizon")
        if action not in {"none", "sell", "charge"}:
            raise ValueError("Candidate action is not supported")
        if power_w is None or not 0 <= power_w <= max_candidate_power_w:
            raise ValueError("Candidate power is outside the safe range")
        if action in {"sell", "charge"}:
            required_profiles = [
                profile
                for profile_id, profile in profile_definitions.items()
                if isinstance(profile, dict)
                and profile.get("enabled")
                and str(profile.get("goal_character") or "preferred") == "required"
                and (
                    action == "charge"
                    if profile_id == "charging" or str(profile.get("type")).lower() == "charging"
                    else action == "sell"
                )
            ]
            if required_profiles:
                day_index, hour = divmod(change_index, 24)
                day = start_date + timedelta(days=day_index)
                inside_required_policy = any(
                    _time_in_window(hour, profile.get("start"), profile.get("end"))
                    and _active_today(profile, _profile_window_day(profile, day, hour))
                    for profile in required_profiles
                )
                if not inside_required_policy:
                    raise ValueError("Candidate action is outside a required user profile window")
        normalized_changes[change_index] = {"action": action, "power_w": power_w}
    if len(normalized_changes) > 5:
        raise ValueError("Candidate may change at most five slots")
    # A syntactically valid AI charge is still only advisory.  Do not let it
    # manufacture a grid-charge purpose which does not exist in the local
    # policy.  A different slot of an already selected charging profile is a
    # legitimate alternative; otherwise the same future-value test used by
    # Core must find a later selected sale or evidenced expensive home load.
    # Neutralized requests remain in ``candidate_changes`` so the caller can
    # distinguish schema validity from local acceptance.
    simulated_changes = deepcopy(normalized_changes)
    pre_rejections: dict[int, str] = {}
    prices = _prices(merged)
    load, load_known = _load_profile_quality(merged)
    forecast = _forecast_series(merged)
    operational_pv = forecast.get(
        {"safe": "operational_low", "profit": "operational_high"}.get(
            str(strategy), "operational"
        ),
        [0.0] * 48,
    )
    efficiency = max(0.5, min(1.0, _finite(merged.get("battery_efficiency"), 0.9)))
    cycle_cost = max(0.0, _finite(merged.get("battery_cycle_cost_per_kwh"), 0.0))
    minimum_margin = float(
        STRATEGIES.get(str(strategy), STRATEGIES["balanced"])["minimum_profit_threshold"]
    )
    source_rows = source_plan.get("rows") if isinstance(source_plan.get("rows"), list) else []
    for change_index, requested in normalized_changes.items():
        if requested["action"] != "charge":
            continue
        source_row = source_rows[change_index] if change_index < len(source_rows) else {}
        if source_row.get("action") == "charge" and source_row.get("proposed"):
            continue
        profile_id = source_row.get("profile_id")
        profile_has_selected_charge = bool(profile_id) and any(
            row.get("profile_id") == profile_id
            and row.get("action") == "charge"
            and row.get("proposed")
            for row in source_rows
        )
        if profile_has_selected_charge:
            continue
        day_index, hour = divmod(change_index, 24)
        buy_cost = prices["effective_buy"][day_index].get(hour)
        future_values: list[float] = []
        if buy_cost is not None:
            future_values.extend(
                float(value)
                for later in range(change_index + 1, 48)
                if later < len(source_rows)
                and source_rows[later].get("action") == "sell"
                and source_rows[later].get("proposed")
                and (value := prices["sell"][later // 24].get(later % 24)) is not None
                and value > 0
            )
            future_values.extend(
                float(value)
                for later in range(change_index + 1, 48)
                if load_known[later]
                and load[later] > max(0.0, _finite(operational_pv[later])) + 1e-9
                and (value := prices["effective_buy"][later // 24].get(later % 24)) is not None
            )
        profitable = bool(future_values) and (
            max(future_values) * efficiency
            - float(buy_cost)
            - 2 * cycle_cost
            - minimum_margin
            > 0
        )
        if not profitable:
            simulated_changes[change_index] = {"action": "none", "power_w": 0.0}
            pre_rejections[change_index] = "candidate:unprofitable-charge-without-local-purpose"
    if simulated_changes:
        merged["_candidate_actions"] = simulated_changes
    plan = build_energy_plan(merged, strategy)
    index = max(0, min(47, int(start_index)))
    accepted_changes = []
    for change_index, requested in sorted(normalized_changes.items()):
        actual = plan["rows"][change_index]
        accepted = (
            actual.get("action") == requested["action"]
            and (
                requested["action"] == "none"
                or bool(actual.get("proposed"))
                and _finite(actual.get("planned_power_w"), 0) > 0
            )
        )
        accepted_changes.append({
            "index": change_index,
            "requested_action": requested["action"],
            "actual_action": actual.get("action"),
            "actual_power_w": actual.get("planned_power_w"),
            "accepted": accepted,
            "reason_code": pre_rejections.get(change_index) or actual.get("reason_code"),
        })
    accepted_by_core = bool(accepted_changes) and all(
        item["accepted"] for item in accepted_changes
    )
    return {
        "source_plan_id": source_plan["plan_id"],
        "source_input_snapshot_id": source_plan["input_snapshot_id"],
        "candidate_plan_id": plan["plan_id"],
        "candidate_changes": [
            {"index": key, **value}
            for key, value in sorted(normalized_changes.items())
        ],
        "start_index": index,
        "one_hour": deepcopy(plan["rows"][index]),
        "remaining_horizon": deepcopy(plan["rows"][index:]),
        "financials": deepcopy(plan["financials"]),
        "comparison": {
            "source_core_result": source_plan["optimized_result"],
            "candidate_result": plan["optimized_result"],
            "candidate_vs_source": round(plan["optimized_result"] - source_plan["optimized_result"], 5),
            "deye_baseline_result": source_plan["baseline_result"],
            "candidate_vs_deye_baseline": round(plan["optimized_result"] - source_plan["baseline_result"], 5),
        },
        "schema_valid": True,
        "locally_simulated": True,
        "accepted_by_core": accepted_by_core,
        "acceptance": accepted_changes,
        # Backward-compatible field now means full local acceptance, not merely
        # successful schema parsing.
        "locally_validated": accepted_by_core,
        "manual_confirmation_required": True,
        "writes_performed": False,
    }

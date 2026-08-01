"""Local deterministic optimizer for the 48-hour Deye energy plan.

The module is intentionally independent from Home Assistant and from the
physical Deye write layer.  It accepts a plain input snapshot and returns only
finite, serializable proposals.  Applying a proposal is a separate, explicit
operation handled by the existing, guarded manager transaction.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ALGORITHM_VERSION = "0.7.9-local-optimizer-3"
PLAN_SCHEMA_VERSION = 3
HISTORY_SCHEMA_VERSION = 4
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
    learning = min(1.0, equivalent_learning_days / 21.0)
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
    # Keep the learning-stage cap, but make every visible input contribute
    # directly and prevent a degraded nested source from becoming 100%.
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
    if equivalent_learning_days < 7:
        value = min(value, 49.0)
    elif equivalent_learning_days < 14:
        value = min(value, 70.0)
    return round(max(20.0, min(95.0, value)), 1), components


def _forecast_series(inputs: dict[str, Any]) -> dict[str, Any]:
    shape, learned = _normalised_solar_shape(inputs.get("pv_profile"))
    totals = inputs.get("pv_forecast") if isinstance(inputs.get("pv_forecast"), list) else [0, 0]
    full = inputs.get("pv_forecast_full") if isinstance(inputs.get("pv_forecast_full"), list) else totals
    available = inputs.get("pv_forecast_available")
    if not isinstance(available, list):
        available = [True, True]
    weather = inputs.get("weather_factors") if isinstance(inputs.get("weather_factors"), list) else []
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
            weather_factor = 1.0 if factor_raw is None else max(0.65, min(1.05, _finite(factor_raw, 1.0)))
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
        "weather": weather,
        "learned": learned,
    }


def _prices(inputs: dict[str, Any]) -> dict[str, Any]:
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
            distribution = prices["distribution"][index]
            purchase_days[day_name].append({
                "day": day_name,
                "date": day.isoformat(),
                "hour": hour,
                "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
                "energy_price": round(energy_price, 5),
                "distribution_price": round(0.0 if included else distribution, 5),
                "effective_price": round(prices["effective_buy"][day_index][hour], 5),
                "zone": tariff_row.get("zone"),
                "season": tariff_row.get("season"),
                "day_type": tariff_row.get("day_type"),
                "provider": tariff.get("provider"),
                "provider_name": tariff.get("provider_name"),
                "plan": tariff.get("plan"),
                "plan_name": tariff.get("plan_name"),
                "price_includes_distribution": included,
                "osd_complete": bool(included or osd_complete),
            })
        purchase_days[day_name].sort(key=lambda item: (item["effective_price"], item["hour"]))

    sale_profiles: dict[str, Any] = {}
    for profile_id in ("morning_sale", "evening_sale"):
        profile = profiles.get(profile_id) if isinstance(profiles.get(profile_id), dict) else {}
        enabled = bool(profile.get("enabled"))
        minimum = _finite(profile.get("min_price", profile.get("minimum_price")), 0)
        target = max(0.0, _finite(profile.get("target_energy_kwh"), 0))
        profile_days: dict[str, list[dict[str, Any]]] = {"today": [], "tomorrow": []}
        for day_index, day_name in enumerate(("today", "tomorrow")):
            day = start_date + timedelta(days=day_index)
            if not _active_today(profile, day):
                continue
            for hour, price in prices["sell"][day_index].items():
                if not _time_in_window(hour, profile.get("start"), profile.get("end")):
                    continue
                plan_row = rows[day_index * 24 + hour]
                planned_for_profile = f"profile:{profile_id}" in plan_row.get("reason_codes", [])
                qualifies = price + 1e-9 >= minimum
                profile_days[day_name].append({
                    "day": day_name,
                    "date": day.isoformat(),
                    "hour": hour,
                    "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
                    "sell_price": round(price, 5),
                    "qualifies_minimum": qualifies,
                    "recommended": bool(enabled and qualifies and planned_for_profile),
                    "planned_energy_kwh": plan_row.get("planned_energy_kwh", 0.0) if planned_for_profile else 0.0,
                    "planned_power_w": plan_row.get("planned_power_w", 0.0) if planned_for_profile else 0.0,
                    "soc_before": plan_row.get("soc_start_pct"),
                    "soc_after": plan_row.get("soc_end_pct"),
                    "decision_source": f"profile:{profile_id}" if planned_for_profile else "informational",
                })
            profile_days[day_name].sort(key=lambda item: (-item["sell_price"], item["hour"]))
        planned = round(sum(
            item["planned_energy_kwh"]
            for day_rows in profile_days.values()
            for item in day_rows
            if item["recommended"]
        ), 5)
        qualified = sum(
            1
            for day_rows in profile_days.values()
            for item in day_rows
            if item["qualifies_minimum"]
        )
        sale_profiles[profile_id] = {
            "profile_id": profile_id,
            "name": str(profile.get("name") or labels[profile_id]),
            "enabled": enabled,
            "start": str(profile.get("start") or ""),
            "end": str(profile.get("end") or ""),
            "target_energy_kwh": target,
            "planned_energy_kwh": planned,
            "missing_energy_kwh": round(max(0.0, target - planned), 5),
            "minimum_price": minimum,
            "minimum_soc_after": _optional(profile.get("min_soc_after")),
            "qualified_hours": qualified,
            "status": (
                "disabled"
                if not enabled
                else "no_hours_above_minimum"
                if qualified == 0
                else "partially_possible"
                if planned + 1e-6 < target
                else "ready"
            ),
            "days": profile_days,
        }

    if benefit > neutrality_threshold:
        assessment = "better"
        decision_title = "Najlepsza decyzja"
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


def _profile_requests(inputs: dict[str, Any], prices: dict[str, Any]) -> dict[int, dict[str, Any]]:
    root = inputs.get("user_profiles") if isinstance(inputs.get("user_profiles"), dict) else {}
    profiles = root.get("profiles") if isinstance(root.get("profiles"), dict) else {}
    start_date = date.fromisoformat(str(inputs.get("date")))
    candidates: dict[int, list[dict[str, Any]]] = {}
    profile_candidates: dict[str, list[tuple[int, dict[str, Any], float]]] = {}
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
        for index in range(48):
            day_index, hour = divmod(index, 24)
            day = start_date + timedelta(days=day_index)
            in_window = _time_in_window(hour, profile.get("start"), profile.get("end"))
            earlier_allowed = kind == "charge" and bool(profile.get("allow_earlier_grid_charge"))
            if not _active_today(profile, day) or (not in_window and not earlier_allowed):
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
                "profile_id": str(key),
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
            profile_candidates.setdefault(str(key), []).append((index, request, float(price)))

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
        sale_rows = profile_candidates.get(str(profile_id), [])
        if not sale_rows or sale_rows[0][1].get("action") != "sell":
            continue
        target = max(0.0, _finite(profile.get("target_energy_kwh"), 0))
        minimum_soc = max(0.0, _finite(profile.get("min_soc_after", profile.get("minimum_soc")), 0))
        available = max(0.0, capacity * (soc - minimum_soc) / 100.0) * discharge_eff
        missing_input = max(0.0, target - available) / charge_eff
        if missing_input <= 1e-9:
            continue
        first_sale = min(index for index, _request, _price in sale_rows)
        sale_by_index = {index: price for index, _request, price in sale_rows}
        earlier: list[tuple[int, float, int, float, float]] = []
        for index in range(max(0, int(_finite(inputs.get("current_hour"), 0))), first_sale):
            buy = prices["effective_buy"][index // 24].get(index % 24)
            later_sales = [(later, price) for later, price in sale_by_index.items() if later > index]
            if buy is None or not later_sales:
                continue
            later, sell = max(later_sales, key=lambda item: (item[1], -item[0]))
            margin = sell * _finite(inputs.get("battery_efficiency"), 0.9) - buy
            if margin <= max(0.0, _finite(profile.get("min_net_result"), 0) / max(target, 1e-9)):
                continue
            earlier.append((index, buy, later, sell, margin))
        for index, buy, later, sell, margin in sorted(earlier, key=lambda item: (item[1], item[0])):
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

    # Convert each user's energy target into explicit per-hour requests before
    # resolving conflicts between profiles.  This keeps profile intent separate
    # from the battery simulation and makes all three distribution modes
    # deterministic.
    for profile_id, rows in profile_candidates.items():
        if not rows:
            continue
        sample = rows[0][1]
        target = max(0.0, _finite(sample.get("target_energy_kwh"), 0))
        is_soc_target = sample["action"] == "charge" and sample.get("target_type") == "soc"
        method = str(sample.get("distribution_method") or "best_hours")
        cap = max(
            0.0,
            _finite(sample.get("power_limit_w"), default_power_w) / 1000.0,
        )
        if sample["action"] == "sell":
            ordered = sorted(rows, key=lambda item: (-item[2], item[0])) if method == "best_hours" else sorted(rows)
        else:
            ordered = sorted(rows, key=lambda item: (item[2], item[0])) if method == "best_hours" else sorted(rows)
        remaining = target
        for position, (index, request, _price) in enumerate(ordered):
            if is_soc_target:
                requested = None
            elif method == "even":
                requested = min(cap, target / len(ordered)) if ordered else 0.0
            elif method == "constant_power":
                remaining_slots = max(1, len(ordered) - position)
                requested = min(cap, remaining / remaining_slots)
            else:
                requested = min(cap, remaining)
            if requested is not None:
                remaining = max(0.0, remaining - requested)
                if requested <= 1e-9:
                    continue
            request["requested_energy_kwh"] = requested
            candidates.setdefault(index, []).append(request)
    for index, request in supporting_charge_requests:
        candidates.setdefault(index, []).append(request)
    result = {}
    for index, rows in candidates.items():
        rows.sort(
            key=lambda row: (row["required"], row["priority"], row["action"] == "sell", row["profile_id"]),
            reverse=True,
        )
        result[index] = rows[0]
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


def _strategy_actions(inputs: dict[str, Any], strategy: str, prices: dict[str, Any]) -> list[dict[str, Any]]:
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
    # Evaluate every available hour independently.  There is deliberately no
    # fixed "best 1/3/4 hours" cap: physical SOC and power constraints stop the
    # dispatch, not an arbitrary strategy constant.
    for index in range(current_hour, 48):
        day_index, hour = divmod(index, 24)
        sell_price = prices["sell"][day_index].get(hour)
        if allow_sell and sell_price is not None and sell_price >= automatic_sell_threshold:
            actions[index] = {
                "action": "sell",
                "mode": "Selling First",
                "reason": "optimizer:high-net-export-price",
            }
            continue
        buy_price = prices["effective_buy"][day_index].get(hour)
        future_sales = [
            (later, prices["sell"][later // 24].get(later % 24))
            for later in range(index + 1, 48)
        ]
        future_sales = [
            (later, value)
            for later, value in future_sales
            if value is not None and value > 0
        ]
        if (
            explicit_charge_profile
            or not allow_charge
            or buy_price is None
            or buy_price > maximum_buy
            or not future_sales
        ):
            continue
        future_hour, future_sell = max(future_sales, key=lambda item: (item[1], -item[0]))
        expected_margin = future_sell * efficiency - buy_price - float(cfg["minimum_profit_threshold"])
        if expected_margin > 0:
            actions[index] = {
                "action": "charge",
                "mode": "Charge",
                "reason": "optimizer:profitable-charge-before-sale",
                "purpose": "sale",
                "future_target_type": "sale",
                "future_target_hour": future_hour,
                "future_target_price": future_sell,
                "expected_margin": expected_margin,
            }
    for index, request in profile_requests.items():
        actions[index] = {
            "action": request["action"],
            "mode": "Charge" if request["action"] == "charge" else "Selling First",
            "reason": request["reason"],
            "profile_id": request["profile_id"],
            "power_limit_w": request.get("power_limit_w"),
            "target_soc": request.get("target_soc"),
            "required": request.get("required"),
            "requested_energy_kwh": request.get("requested_energy_kwh"),
            "target_type": request.get("target_type"),
            "target_basis": request.get("target_basis"),
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
    return actions


def _simulate(
    inputs: dict[str, Any],
    strategy: str,
    *,
    baseline: bool,
    forecast: dict[str, Any],
    prices: dict[str, Any],
) -> dict[str, Any]:
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
    base_limit = _finite(inputs.get("effective_power_limit_w"), _finite(inputs.get("max_sell_power_w"), 5000))
    base_limit = max(0.0, base_limit) * float(cfg["power_limit_pct"]) / 100.0
    charge_request = max(0.0, _finite(inputs.get("charge_kwh_per_hour"), capacity * 0.25))
    duration_first = max(1, min(60, int(_finite(inputs.get("current_hour_remaining_minutes"), 60))))
    load = _profile48(inputs)
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
    ] if baseline else _strategy_actions(inputs, strategy, prices)
    cycle_cost_rate = max(0.0, _finite(inputs.get("battery_cycle_cost_per_kwh"), 0.0))
    terminal_rate = max(0.0, _finite(inputs.get("terminal_energy_value_per_kwh"), 0.0))
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
    }
    day_start_soc = soc
    day_summaries = []
    profile_energy: dict[str, float] = {}
    profile_charge_remaining: dict[str, float] = {}
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
        action_spec = actions[index]
        action = action_spec["action"]
        if (
            duration <= 0
            or fail_closed
            or confidence + 1e-9 < _finite(action_spec.get("minimum_confidence"), 0)
        ):
            action = "none"
        power_limit = _optional(action_spec.get("power_limit_w"))
        if power_limit is None or power_limit <= 0:
            power_limit = base_limit
        max_energy = power_limit / 1000 * duration / 60 if power_limit > 0 else 0.0
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
            if live_pv is not None:
                projected = max(0.0, live_pv) / 1000.0 * duration / 60.0
                pv = pv * 0.65 + projected * 0.35
            if live_home is not None:
                projected = max(0.0, live_home) / 1000.0 * duration / 60.0
                home = home * 0.65 + projected * 0.35
            input_origin = "measured_anchor_plus_forecast"
        energy = capacity * soc / 100.0
        profile_id = str(action_spec.get("profile_id") or "")
        if (
            action == "charge"
            and profile_id
            and action_spec.get("target_type") == "soc"
            and action_spec.get("charge_missing_only")
            and profile_id not in profile_charge_remaining
        ):
            target_energy = capacity * min(
                target_max,
                max(strategy_min, _finite(action_spec.get("target_soc"), target_max)),
            ) / 100.0
            profile_charge_remaining[profile_id] = max(0.0, target_energy - energy) / charge_eff
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
        pv_to_home = min(pv, home)
        pv_surplus = pv - pv_to_home
        remaining_home = home - pv_to_home
        pv_to_battery = (
            0.0
            if action == "sell" and action_spec.get("target_basis") == "total_export"
            else min(pv_surplus, max_energy, max(0.0, maximum_energy - energy) / charge_eff)
        )
        energy += pv_to_battery * charge_eff
        pv_to_grid = max(0.0, pv_surplus - pv_to_battery)
        available = max(0.0, energy - minimum_energy)
        battery_to_home = min(remaining_home, max_energy, available * discharge_eff)
        energy -= battery_to_home / discharge_eff
        grid_to_home = max(0.0, remaining_home - battery_to_home)
        grid_to_battery = 0.0
        battery_to_grid = 0.0
        limit_reasons = []
        if action == "charge":
            source = str(action_spec.get("charge_source") or "auto").lower()
            requested_setting = _optional(action_spec.get("requested_energy_kwh"))
            if action_spec.get("target_type") == "soc":
                requested_setting = max(0.0, maximum_energy - energy) / charge_eff
                if action_spec.get("charge_missing_only") and profile_id:
                    requested_setting = min(
                        requested_setting,
                        profile_charge_remaining.get(profile_id, requested_setting),
                    )
            requested = min(
                charge_request if requested_setting is None else max(0.0, requested_setting),
                max_energy,
            )
            max_grid = _optional(action_spec.get("max_grid_energy_kwh"))
            if max_grid is not None:
                requested = min(requested, max(0.0, max_grid - profile_energy.get(profile_id, 0.0)))
            room = max(0.0, maximum_energy - energy)
            grid_to_battery = 0.0 if source == "pv" else min(requested, room / charge_eff)
            energy += grid_to_battery * charge_eff
            profile_energy[profile_id] = profile_energy.get(profile_id, 0.0) + grid_to_battery
            if profile_id in profile_charge_remaining:
                profile_charge_remaining[profile_id] = max(
                    0.0,
                    profile_charge_remaining[profile_id] - grid_to_battery,
                )
            if source == "pv":
                limit_reasons.append("pv_only_profile")
            if grid_to_battery + 1e-7 < requested:
                limit_reasons.append("target_soc")
        elif action == "sell":
            available = max(0.0, energy - minimum_energy)
            requested = _optional(action_spec.get("requested_energy_kwh"))
            if requested is None:
                requested = max_energy
            if action_spec.get("target_basis") == "total_export":
                requested = max(0.0, requested - pv_to_grid)
            battery_to_grid = min(max_energy, max(0.0, requested), available * discharge_eff)
            energy -= battery_to_grid / discharge_eff
            profile_energy[profile_id] = profile_energy.get(profile_id, 0.0) + battery_to_grid
            if battery_to_grid + 1e-7 < requested:
                limit_reasons.append("minimum_soc")
        if fail_closed:
            limit_reasons = ["missing_current_soc_fail_closed"]
        energy = min(maximum_energy, max(minimum_energy, energy))
        soc_end = energy / capacity * 100.0
        sell_price = prices["sell"][day_index].get(hour)
        buy_price = prices["buy"][day_index].get(hour)
        distribution = prices["distribution"][index]
        effective_buy = prices["effective_buy"][day_index].get(hour)
        export_energy = pv_to_grid + battery_to_grid
        import_energy = grid_to_home + grid_to_battery
        export_revenue = export_energy * (sell_price or 0.0)
        import_source_cost = import_energy * (buy_price or 0.0)
        distribution_cost = 0.0 if prices["included"] else import_energy * distribution
        losses = (
            (pv_to_battery + grid_to_battery) * (1.0 - charge_eff)
            + (battery_to_home + battery_to_grid) * (1.0 / discharge_eff - 1.0)
        )
        loss_cost = losses * (effective_buy or 0.0)
        cycle_cost = (grid_to_battery + pv_to_battery + battery_to_home + battery_to_grid) * cycle_cost_rate
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
        if limit_reasons:
            reason_codes.extend(f"limit:{item}" for item in limit_reasons)
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
        row = {
            "day": "today" if day_index == 0 else "tomorrow",
            "date": day.isoformat(),
            "hour": hour,
            "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
            "hour_start": hour_start.isoformat(),
            "hour_end": hour_end.isoformat(),
            "duration_minutes": duration,
            "action": action,
            "profile_id": action_spec.get("profile_id"),
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
            "power_limit_w": round(power_limit if proposed else 0.0, 2),
            "planned_power_w": round(planned_power, 2),
            "planned_energy_kwh": round(
                grid_to_battery if action == "charge" else battery_to_grid if action == "sell" else 0.0,
                5,
            ),
            "energy_kwh": round(
                grid_to_battery if action == "charge" else battery_to_grid if action == "sell" else 0.0,
                3,
            ),
            "target_soc": round(_finite(action_spec.get("target_soc"), target_max), 2),
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
            "grid_to_battery_kwh": round(grid_to_battery, 5),
            "battery_to_home_kwh": round(battery_to_home, 5),
            "battery_to_grid_kwh": round(battery_to_grid, 5),
            "grid_to_home_kwh": round(grid_to_home, 5),
            "expected_import_kwh": round(import_energy, 5),
            "expected_export_kwh": round(export_energy, 5),
            "buy_price": buy_price,
            "distribution": round(distribution, 5),
            "distribution_price": round(distribution, 5),
            "effective_buy_price": effective_buy,
            "total_buy_price": effective_buy,
            "sell_price": sell_price,
            "export_revenue": round(export_revenue, 5),
            "import_cost": round(import_source_cost, 5),
            "distribution_cost": round(distribution_cost, 5),
            "loss_cost": round(loss_cost, 5),
            "battery_cycle_cost": round(cycle_cost, 5),
            "terminal_value": 0.0,
            "net_result": round(net, 5),
            "balance_pln": round(net, 2),
            "benefit": 0.0,
            "confidence": confidence,
            "confidence_components": components,
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
            })
            day_start_soc = soc
    terminal_energy = capacity * soc / 100.0
    terminal_value = terminal_energy * terminal_rate
    totals["terminal_value"] = terminal_value
    totals["net_result_with_terminal"] = totals["net_result"] + terminal_value
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
        "financials": {key: round(value, 5) for key, value in totals.items()},
        "end_soc": round(soc, 4),
        "fail_closed": fail_closed,
    }


def _metadata(inputs: dict[str, Any], strategy: str, input_id: str, duration_ms: float = 0.0) -> dict[str, Any]:
    start_date, generated = _parse_start(inputs)
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=generated.tzinfo)
    raw_stage = inputs.get("learning_stage")
    status = raw_stage.get("label") if isinstance(raw_stage, dict) else raw_stage
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


def build_energy_plan(inputs: dict[str, Any], strategy: str = "balanced") -> dict[str, Any]:
    """Build one optimizer variant plus a comparable existing-schedule baseline."""
    selected = strategy if strategy in STRATEGIES else "balanced"
    input_id = snapshot_id(inputs)
    forecast = _forecast_series(inputs)
    prices = _prices(inputs)
    optimized = _simulate(inputs, selected, baseline=False, forecast=forecast, prices=prices)
    baseline = _simulate(inputs, selected, baseline=True, forecast=forecast, prices=prices)
    profile_definitions = (
        inputs.get("user_profiles", {}).get("profiles", {})
        if isinstance(inputs.get("user_profiles"), dict)
        and isinstance(inputs.get("user_profiles", {}).get("profiles"), dict)
        else {}
    )
    profile_preflight: dict[str, dict[str, Any]] = {}
    blocked_profiles: list[str] = []
    for profile_id, profile in profile_definitions.items():
        if not isinstance(profile, dict) or not profile.get("enabled"):
            continue
        kind = "charging" if profile_id == "charging" or profile.get("type") == "charging" else "sale"
        rows = [row for row in optimized["rows"] if row.get("profile_id") == profile_id]
        possible = sum(
            row["grid_to_battery_kwh"] if kind == "charging" else row["battery_to_grid_kwh"]
            for row in rows
        )
        requested = _finite(
            profile.get("target_value")
            if kind == "charging" and profile.get("target_type") == "energy"
            else profile.get("target_energy_kwh"),
            0,
        )
        incremental = sum(
            row["net_result"] - baseline["rows"][row["hour"] + (0 if row["day"] == "today" else 24)]["net_result"]
            for row in rows
        )
        block_reason = None
        if requested > 0 and not bool(profile.get("allow_partial", True)) and possible + 1e-6 < requested:
            block_reason = "partial_not_allowed"
        elif (
            _finite(profile.get("min_net_result"), 0) > 0
            and incremental + 1e-6 < _finite(profile.get("min_net_result"), 0)
        ):
            block_reason = "min_net_result"
        profile_preflight[str(profile_id)] = {
            "possible_energy_kwh": possible,
            "requested_energy_kwh": requested,
            "profile_net_result_pln": incremental,
            "block_reason": block_reason,
        }
        if block_reason:
            blocked_profiles.append(str(profile_id))
    if blocked_profiles:
        filtered_inputs = deepcopy(inputs)
        filtered_inputs["_blocked_profile_ids"] = blocked_profiles
        optimized = _simulate(
            filtered_inputs,
            selected,
            baseline=False,
            forecast=forecast,
            prices=prices,
        )
    baseline_id = hashlib.sha256(f"{input_id}:baseline:{ALGORITHM_VERSION}".encode("utf-8")).hexdigest()[:24]
    optimized_result = optimized["financials"]["net_result_with_terminal"]
    baseline_result = baseline["financials"]["net_result_with_terminal"]
    benefit = optimized_result - baseline_result
    neutrality_threshold = max(0.20, abs(baseline_result) * 0.01)
    practically_same = abs(benefit) <= neutrality_threshold
    for opt_row, base_row in zip(optimized["rows"], baseline["rows"]):
        opt_row["benefit"] = round(opt_row["net_result"] - base_row["net_result"], 5)
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
        planned = sum(
            row["grid_to_battery_kwh"] if kind == "charging" else row["battery_to_grid_kwh"]
            for row in profile_rows
        )
        requested = _finite(
            profile.get("target_value")
            if kind == "charging" and profile.get("target_type") == "energy"
            else profile.get("target_energy_kwh"),
            0,
        )
        actual = sum(
            _finite(
                item.get("actual_energy_kwh", item.get("executed_energy_kwh", item.get("energy_kwh"))),
                0,
            )
            for item in execution_rows
            if isinstance(item, dict)
            and str(item.get("profile_id") or "") == str(profile_id)
            and str(item.get("date") or "") in horizon_dates
        )
        planned = sum(
            row["grid_to_battery_kwh"] if kind == "charging" else row["battery_to_grid_kwh"]
            for row in profile_rows
        ) if enabled else 0.0
        preflight = profile_preflight.get(str(profile_id), {})
        possible = _finite(preflight.get("possible_energy_kwh"), planned)
        block_reason = preflight.get("block_reason")
        missing = max(0.0, requested - planned)
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
            "qualified_hours": len(profile_rows),
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
            "confidence": min((row["confidence"] for row in profile_rows), default=0),
        })
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
        "baseline_plan_id": baseline_id,
        "baseline_result": round(baseline_result, 5),
        "optimized_result": round(optimized_result, 5),
        "benefit": round(benefit, 5),
        "neutrality_threshold": round(neutrality_threshold, 5),
        "comparison": "Praktycznie taki sam" if practically_same else "Lepszy" if benefit > 0 else "Gorszy",
        "confirmation_required": bool(
            benefit <= neutrality_threshold
            and any(row.get("proposed") and row.get("profile_id") for row in optimized["rows"])
        ),
        "recommended_write": bool(
            not optimized["fail_closed"]
            and (
                benefit > neutrality_threshold
                or any(row.get("proposed") and row.get("profile_id") for row in optimized["rows"])
            )
        ),
        "baseline": {
            "plan_id": baseline_id,
            "rows": baseline["rows"],
            "days": baseline["days"],
            "checkpoints": baseline["checkpoints"],
            "financials": baseline["financials"],
        },
        "data_quality": {
            "learning_stage": "gotowe" if int(_finite(inputs.get("recorded_days"))) >= 14 else "wstępne uczenie",
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
            "osd_complete": _osd_available_hours(inputs) == 48,
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


def build_plan_bundle(inputs: dict[str, Any], selected_strategy: str = "balanced") -> dict[str, Any]:
    """Run all variants independently and return the selected complete plan."""
    variants = {name: build_energy_plan(inputs, name) for name in ("safe", "balanced", "profit")}
    selected = selected_strategy if selected_strategy in variants else "balanced"
    result = deepcopy(variants[selected])
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
    return _canonical(result)


def simulate_alternative(
    inputs: dict[str, Any],
    *,
    strategy: str = "balanced",
    overrides: dict[str, Any] | None = None,
    start_index: int = 0,
) -> dict[str, Any]:
    """Read-only what-if simulation for one future hour or the remaining horizon."""
    merged = deepcopy(inputs)
    if overrides:
        merged.update(deepcopy(overrides))
    plan = build_energy_plan(merged, strategy)
    index = max(0, min(47, int(start_index)))
    return {
        "source_plan_id": plan["plan_id"],
        "start_index": index,
        "one_hour": deepcopy(plan["rows"][index]),
        "remaining_horizon": deepcopy(plan["rows"][index:]),
        "financials": deepcopy(plan["financials"]),
        "writes_performed": False,
    }

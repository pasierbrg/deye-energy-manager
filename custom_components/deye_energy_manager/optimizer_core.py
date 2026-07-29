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


ALGORITHM_VERSION = "0.7.7-local-optimizer-1"
HISTORY_SCHEMA_VERSION = 2
STRATEGIES = {
    "safe": {
        "reserve_buffer_pct": 8.0,
        "power_limit_pct": 65.0,
        "minimum_profit_threshold": 0.30,
        "forecast_quantile": "low",
        "terminal_soc_target": 55.0,
        "sell_hours": 1,
        "charge_hours": 1,
    },
    "balanced": {
        "reserve_buffer_pct": 0.0,
        "power_limit_pct": 100.0,
        "minimum_profit_threshold": 0.20,
        "forecast_quantile": "mid",
        "terminal_soc_target": 45.0,
        "sell_hours": 3,
        "charge_hours": 2,
    },
    "profit": {
        "reserve_buffer_pct": 0.0,
        "power_limit_pct": 100.0,
        "minimum_profit_threshold": 0.20,
        "forecast_quantile": "high",
        "terminal_soc_target": 30.0,
        "sell_hours": 4,
        "charge_hours": 3,
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
        if 0 <= hour <= 23 and math.isfinite(number) and number >= 0:
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
    generated_raw = inputs.get("generated_at")
    if generated_raw:
        try:
            generated = datetime.fromisoformat(str(generated_raw).replace("Z", "+00:00"))
        except ValueError:
            generated = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    else:
        generated = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    return start_date, generated


def _confidence(inputs: dict[str, Any], day_index: int, pv_learned: bool) -> tuple[float, dict[str, float]]:
    recorded = max(0, int(_finite(inputs.get("recorded_days"))))
    sells = inputs.get("sell_prices") if isinstance(inputs.get("sell_prices"), list) else []
    buys = inputs.get("buy_prices") if isinstance(inputs.get("buy_prices"), list) else []
    price = 1.0 if _hour_map(sells[day_index] if day_index < len(sells) else {}) and _hour_map(
        buys[day_index] if day_index < len(buys) else {}
    ) else 0.35
    forecast = inputs.get("pv_forecast_available")
    pv_available = not isinstance(forecast, list) or (day_index < len(forecast) and bool(forecast[day_index]))
    learning = min(1.0, recorded / 21)
    source_quality = inputs.get("data_quality") if isinstance(inputs.get("data_quality"), dict) else {}
    source = 0.85 if not source_quality else 1.0 if all(
        not isinstance(item, dict) or item.get("quality") in (None, "good")
        for item in source_quality.values()
    ) else 0.65
    components = {
        "prices": round(price * 100, 1),
        "forecast": 100.0 if pv_available else 25.0,
        "learning": round(learning * 100, 1),
        "sources": round(source * 100, 1),
        "pv_profile": 100.0 if pv_learned else 45.0,
    }
    value = 0.25 * components["prices"] + 0.25 * components["forecast"] + 0.25 * components["learning"]
    value += 0.15 * components["sources"] + 0.10 * components["pv_profile"]
    if recorded < 7:
        value = min(value, 49.0)
    elif recorded < 14:
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
            operational.append(max(0.0, remaining_total * active_shape[hour] / active_sum * correction * weather_factor))
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
            hour: value if included else value + distribution[day_index * 24 + hour]
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


def _profile_requests(inputs: dict[str, Any], prices: dict[str, Any]) -> dict[int, dict[str, Any]]:
    root = inputs.get("user_profiles") if isinstance(inputs.get("user_profiles"), dict) else {}
    profiles = root.get("profiles") if isinstance(root.get("profiles"), dict) else {}
    start_date = date.fromisoformat(str(inputs.get("date")))
    candidates: dict[int, list[dict[str, Any]]] = {}
    profile_candidates: dict[str, list[tuple[int, dict[str, Any], float]]] = {}
    default_power_w = max(
        0.0,
        _finite(inputs.get("effective_power_limit_w"), _finite(inputs.get("max_sell_power_w"), 5000)),
    )
    for key, profile in profiles.items():
        if not isinstance(profile, dict) or not bool(profile.get("enabled")):
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
            if not _active_today(profile, day) or not _time_in_window(hour, profile.get("start"), profile.get("end")):
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
                "minimum_confidence": max(0.0, min(100.0, _finite(profile.get("minimum_confidence"), 0))),
                "charge_source": str(profile.get("source") or "auto"),
                "max_grid_energy_kwh": _optional(profile.get("max_grid_energy_kwh")),
                "preserve_pv_room": bool(profile.get("preserve_pv_room")),
                "minimum_free_room_kwh": max(0.0, _finite(profile.get("minimum_free_room_kwh"), 0)),
                "profitable_only": bool(profile.get("profitable_only", False)),
                "price": float(price),
            }
            profile_candidates.setdefault(str(key), []).append((index, request, float(price)))

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
    result = {}
    for index, rows in candidates.items():
        rows.sort(
            key=lambda row: (row["required"], row["priority"], row["action"] == "sell", row["profile_id"]),
            reverse=True,
        )
        result[index] = rows[0]
    return result


def _best_window(
    values: dict[int, float],
    hours: list[int],
    length: int,
    *,
    maximize: bool,
    threshold: float,
    excluded: set[int] | None = None,
) -> set[int]:
    if length <= 0:
        return set()
    excluded = excluded or set()
    allowed = set(hours)
    best: tuple[float, list[int]] | None = None
    for start in hours:
        window = list(range(start, start + length))
        if any(hour not in allowed or hour in excluded or hour not in values for hour in window):
            continue
        candidates = [values[hour] for hour in window]
        if maximize and any(value < threshold for value in candidates):
            continue
        if not maximize and any(value > threshold for value in candidates):
            continue
        score = sum(candidates) / len(candidates)
        if best is None or (maximize and score > best[0]) or (not maximize and score < best[0]):
            best = score, window
    return set(best[1]) if best else set()


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
    allow_charge = bool(inputs.get("allow_grid_charge", True))
    minimum_sell = _finite(inputs.get("min_sell_price"), 0)
    maximum_buy = _finite(inputs.get("max_buy_price"), 999)
    efficiency = max(0.5, min(1.0, _finite(inputs.get("battery_efficiency"), 0.9)))
    profile_requests = _profile_requests(inputs, prices)
    actions = [{"action": "none", "mode": "Bez zmiany", "reason": "optimizer:no-profitable-change"} for _ in range(48)]
    for day_index in range(2):
        active = list(range(current_hour, 24)) if day_index == 0 else list(range(24))
        sell_hours = set()
        if allow_sell:
            sell_hours = _best_window(
                prices["sell"][day_index],
                active,
                int(cfg["sell_hours"]),
                maximize=True,
                threshold=minimum_sell,
            )
        future_sell = max(
            (value for later in range(day_index, 2) for value in prices["sell"][later].values()),
            default=0.0,
        )
        profitable = future_sell * efficiency - float(cfg["minimum_profit_threshold"])
        buy_threshold = min(maximum_buy, profitable)
        buy_hours = set()
        if allow_charge and future_sell > 0 and buy_threshold >= 0:
            buy_hours = _best_window(
                prices["effective_buy"][day_index],
                active,
                int(cfg["charge_hours"]),
                maximize=False,
                threshold=buy_threshold,
                excluded=sell_hours,
            )
        for hour in sell_hours:
            actions[day_index * 24 + hour] = {
                "action": "sell",
                "mode": "Selling First",
                "reason": "optimizer:high-net-export-price",
            }
        for hour in buy_hours:
            actions[day_index * 24 + hour] = {
                "action": "charge",
                "mode": "Charge",
                "reason": "optimizer:profitable-charge-before-sale",
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
    for index in range(48):
        day_index, hour = divmod(index, 24)
        duration = duration_first if index == current_hour else 60
        if day_index == 0 and hour < current_hour:
            duration = 0
        day = start_date + timedelta(days=day_index)
        hour_start = datetime.combine(day, datetime.min.time(), tzinfo=generated.tzinfo) + timedelta(hours=hour)
        hour_end = hour_start + timedelta(minutes=duration)
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
        energy = capacity * soc / 100.0
        action_min_soc = max(strategy_min, _finite(action_spec.get("min_soc_after"), strategy_min))
        minimum_energy = capacity * min(100.0, action_min_soc) / 100.0
        action_target_soc = (
            _finite(action_spec.get("target_soc"), target_max)
            if action == "charge"
            else target_max
        )
        maximum_energy = capacity * max(strategy_min, min(target_max, action_target_soc)) / 100.0
        if action == "charge" and action_spec.get("preserve_pv_room"):
            maximum_energy = min(
                maximum_energy,
                max(minimum_energy, capacity - _finite(action_spec.get("minimum_free_room_kwh"), 0)),
            )
        pv_to_home = min(pv, home)
        pv_surplus = pv - pv_to_home
        remaining_home = home - pv_to_home
        pv_to_battery = min(pv_surplus, max_energy, max(0.0, maximum_energy - energy) / charge_eff)
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
            profile_id = str(action_spec.get("profile_id") or "")
            source = str(action_spec.get("charge_source") or "auto").lower()
            requested_setting = _optional(action_spec.get("requested_energy_kwh"))
            if action_spec.get("target_type") == "soc":
                requested_setting = max(0.0, maximum_energy - energy) / charge_eff
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
            if source == "pv":
                limit_reasons.append("pv_only_profile")
            if grid_to_battery + 1e-7 < requested:
                limit_reasons.append("target_soc")
        elif action == "sell":
            profile_id = str(action_spec.get("profile_id") or "")
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
        proposed = action != "none" and duration > 0 and not fail_closed
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
            "charge_source": (
                str(action_spec.get("charge_source") or "grid")
                if action == "charge"
                else None
            ),
            "mode": action_spec.get("mode", "Bez zmiany"),
            "proposed": proposed,
            "planned_power_w": round(power_limit if proposed else 0.0, 2),
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
            "dispatch_status": "blocked" if fail_closed else "skipped" if not proposed else "planned",
            "weather_factor": (
                forecast["weather"][index]
                if index < len(forecast["weather"])
                else None
            ),
        }
        rows.append(row)
        soc = soc_end
        if hour == 23:
            day_rows = [item for item in rows if item["day"] == row["day"]]
            day_summaries.append({
                "day": row["day"],
                "date": day.isoformat(),
                "start_soc": round(day_start_soc, 1),
                "end_soc": round(soc, 1),
                "sold_kwh": round(sum(item["expected_export_kwh"] for item in day_rows), 3),
                "bought_kwh": round(sum(item["expected_import_kwh"] for item in day_rows), 3),
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
    profile_definitions = (
        inputs.get("user_profiles", {}).get("profiles", {})
        if isinstance(inputs.get("user_profiles"), dict)
        and isinstance(inputs.get("user_profiles", {}).get("profiles"), dict)
        else {}
    )
    profile_impacts = []
    for profile_id, profile in profile_definitions.items():
        if not isinstance(profile, dict) or not profile.get("enabled"):
            continue
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
        profile_impacts.append({
            "profile_id": profile_id,
            "profile_type": kind,
            "requested_energy_kwh": round(requested, 5),
            "planned_energy_kwh": round(planned, 5),
            "actual_energy_kwh": None,
            "qualified_hours": len(profile_rows),
            "rejected_hours": 0,
            "minimum_price": _finite(profile.get("min_price", profile.get("minimum_price")), 0),
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
            "partial_execution": bool(requested > 0 and planned + 1e-6 < requested),
            "skip_reason": None if profile_rows else "no_qualified_hours",
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
        "recommended_write": bool(benefit > neutrality_threshold and not optimized["fail_closed"]),
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
            "tomorrow_sell_prices": len(prices["sell"][1]),
            "tomorrow_buy_prices": len(prices["buy"][1]),
            "weather_hours": sum(value is not None for value in forecast["weather"][:48]),
            "fail_closed": optimized["fail_closed"],
        },
    }
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

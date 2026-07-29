"""Deterministic battery and SOC model for the local Optimizer Core."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def migrate_efficiencies(round_trip_efficiency: Any) -> dict[str, float]:
    """Split the legacy cycle efficiency without changing its round-trip value."""
    legacy = _finite(round_trip_efficiency)
    legacy = max(0.5, min(1.0, legacy if legacy is not None else 0.9))
    directional = math.sqrt(legacy)
    return {
        "charge_efficiency": round(directional, 6),
        "discharge_efficiency": round(directional, 6),
        "round_trip_efficiency": round(legacy, 6),
        "migration": "sqrt_legacy_round_trip",
    }


def effective_minimum(
    *,
    hard_min_soc_pct: float,
    reserve_kwh: float,
    capacity_kwh: float,
    reserve_mode: str = "additional",
) -> dict[str, Any]:
    """Explain the exact planning floor; 0.7.6 semantics stay additive."""
    capacity = max(0.001, float(capacity_kwh))
    hard = max(0.0, min(100.0, float(hard_min_soc_pct)))
    reserve_pct = max(0.0, float(reserve_kwh)) / capacity * 100
    if reserve_mode == "alternative":
        effective = max(hard, reserve_pct)
        label = "Rezerwa jako alternatywne minimum"
    else:
        effective = hard + reserve_pct
        label = "Dodatkowa rezerwa ponad minimalny SOC"
    effective = max(hard, min(100.0, effective))
    return {
        "hard_min_soc_pct": round(hard, 3),
        "reserve_kwh": round(max(0.0, float(reserve_kwh)), 3),
        "reserve_mode": reserve_mode if reserve_mode in ("additional", "alternative") else "additional",
        "reserve_label": label,
        "reserve_soc_pct": round(reserve_pct, 3),
        "effective_min_soc_pct": round(effective, 3),
        "effective_min_energy_kwh": round(capacity * effective / 100, 4),
    }


def effective_power_limit(
    *,
    plan_limit_w: float | None,
    export_limit_w: float | None,
    inverter_limit_w: float | None,
    current_limit_a: float | None,
    battery_voltage_v: float | None,
    entity_limit_w: float | None,
) -> dict[str, Any]:
    candidates: dict[str, float] = {}
    for key, value in (
        ("plan", plan_limit_w),
        ("export", export_limit_w),
        ("inverter", inverter_limit_w),
        ("entity", entity_limit_w),
    ):
        number = _finite(value)
        if number is not None and number > 0:
            candidates[key] = number
    current = _finite(current_limit_a)
    voltage = _finite(battery_voltage_v)
    if current is not None and current > 0 and voltage is not None and voltage > 0:
        candidates["current_voltage"] = current * voltage
    if not candidates:
        return {
            "effective_limit_w": 0.0,
            "limit_reason": "brak poprawnego limitu",
            "limits_w": {},
            "current_limit_a": current,
            "voltage_v": voltage,
            "estimated_dc_power_w": current * voltage if current and voltage else None,
        }
    reason, limit = min(candidates.items(), key=lambda item: item[1])
    return {
        "effective_limit_w": round(limit, 3),
        "limit_reason": reason,
        "limits_w": {key: round(value, 3) for key, value in candidates.items()},
        "current_limit_a": current,
        "voltage_v": voltage,
        "estimated_dc_power_w": round(current * voltage, 3) if current and voltage else None,
    }


def remaining_minutes_in_hour(moment: datetime) -> int:
    end = moment.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return max(1, min(60, math.ceil((end - moment).total_seconds() / 60)))


def simulate_hour(
    *,
    soc_start_pct: float,
    capacity_kwh: float,
    effective_min_soc_pct: float,
    target_max_soc_pct: float,
    pv_kwh: float,
    home_load_kwh: float,
    charge_efficiency: float,
    discharge_efficiency: float,
    duration_minutes: int = 60,
    power_limit_w: float = 0,
    allow_battery_for_home: bool = True,
    grid_charge_request_kwh: float = 0,
    battery_sale_request_kwh: float = 0,
    source: str = "forecast",
    data_quality: Any = None,
) -> dict[str, Any]:
    """Simulate one full energy balance in kWh."""
    capacity = max(0.001, float(capacity_kwh))
    duration = max(0, min(60, int(duration_minutes)))
    charge_eff = max(0.5, min(1.0, float(charge_efficiency)))
    discharge_eff = max(0.5, min(1.0, float(discharge_efficiency)))
    minimum_energy = capacity * max(0.0, min(100.0, effective_min_soc_pct)) / 100
    maximum_energy = capacity * max(0.0, min(100.0, target_max_soc_pct)) / 100
    energy_start = capacity * max(0.0, min(100.0, soc_start_pct)) / 100
    energy = max(minimum_energy, min(maximum_energy, energy_start))
    max_ac_energy = max(0.0, float(power_limit_w)) / 1000 * duration / 60 if power_limit_w > 0 else float("inf")

    pv = max(0.0, float(pv_kwh))
    load = max(0.0, float(home_load_kwh))
    pv_to_home = min(pv, load)
    pv_surplus = pv - pv_to_home
    remaining_load = load - pv_to_home

    room = max(0.0, maximum_energy - energy)
    pv_to_battery = min(pv_surplus, max_ac_energy, room / charge_eff)
    energy += pv_to_battery * charge_eff
    pv_to_grid = max(0.0, pv_surplus - pv_to_battery)

    available_dc = max(0.0, energy - minimum_energy)
    battery_to_home = 0.0
    if allow_battery_for_home and remaining_load > 0:
        battery_to_home = min(remaining_load, max_ac_energy, available_dc * discharge_eff)
        energy -= battery_to_home / discharge_eff
        remaining_load -= battery_to_home
    grid_to_home = max(0.0, remaining_load)

    room = max(0.0, maximum_energy - energy)
    grid_to_battery = min(max(0.0, float(grid_charge_request_kwh)), max_ac_energy, room / charge_eff)
    energy += grid_to_battery * charge_eff

    available_dc = max(0.0, energy - minimum_energy)
    battery_to_grid = min(max(0.0, float(battery_sale_request_kwh)), max_ac_energy, available_dc * discharge_eff)
    energy -= battery_to_grid / discharge_eff

    losses = (
        pv_to_battery * (1 - charge_eff)
        + grid_to_battery * (1 - charge_eff)
        + (battery_to_home + battery_to_grid) * (1 / discharge_eff - 1)
    )
    energy = max(minimum_energy, min(maximum_energy, energy))
    soc_end = energy / capacity * 100
    limit_reasons = []
    if energy <= minimum_energy + 1e-7 and (remaining_load > 0 or battery_sale_request_kwh > battery_to_grid):
        limit_reasons.append("SOC")
    if energy >= maximum_energy - 1e-7 and (pv_surplus > pv_to_battery or grid_charge_request_kwh > grid_to_battery):
        limit_reasons.append("docelowy SOC")
    requested = max(grid_charge_request_kwh, battery_sale_request_kwh, load)
    if math.isfinite(max_ac_energy) and requested > max_ac_energy + 1e-7:
        limit_reasons.append("moc/prąd")
    if duration < 60:
        limit_reasons.append("czas")

    return {
        "soc_start_pct": round(energy_start / capacity * 100, 4),
        "soc_end_pct": round(soc_end, 4),
        "battery_energy_start_kwh": round(energy_start, 5),
        "battery_energy_end_kwh": round(energy, 5),
        "pv_to_home_kwh": round(pv_to_home, 5),
        "pv_to_battery_kwh": round(pv_to_battery, 5),
        "pv_to_grid_kwh": round(pv_to_grid, 5),
        "grid_to_battery_kwh": round(grid_to_battery, 5),
        "battery_to_home_kwh": round(battery_to_home, 5),
        "battery_to_grid_kwh": round(battery_to_grid, 5),
        "home_load_kwh": round(load, 5),
        "grid_to_home_kwh": round(grid_to_home, 5),
        "losses_kwh": round(losses, 5),
        "duration_minutes": duration,
        "power_limit_w": round(max(0.0, power_limit_w), 3),
        "planned_energy_kwh": round(
            max(pv_to_battery, grid_to_battery, battery_to_home, battery_to_grid),
            5,
        ),
        "limit_reason": " / ".join(limit_reasons) if limit_reasons else None,
        "data_quality": data_quality,
        "source": source,
    }


def simulate_horizon(
    *,
    initial_soc_pct: float | None,
    hours: list[dict[str, Any]],
    capacity_kwh: float,
    effective_min_soc_pct: float,
    target_max_soc_pct: float,
    charge_efficiency: float,
    discharge_efficiency: float,
    default_power_limit_w: float,
) -> list[dict[str, Any]]:
    """Run a sequential horizon; midnight never resets SOC."""
    if initial_soc_pct is None or _finite(initial_soc_pct) is None:
        return [
            {
                **hour,
                "source": "missing",
                "soc_start_pct": None,
                "soc_end_pct": None,
                "limit_reason": "brak aktualnego SOC — fail-closed",
            }
            for hour in hours
        ]
    soc = float(initial_soc_pct)
    result = []
    for hour in hours:
        row = simulate_hour(
            soc_start_pct=soc,
            capacity_kwh=capacity_kwh,
            effective_min_soc_pct=effective_min_soc_pct,
            target_max_soc_pct=target_max_soc_pct,
            pv_kwh=float(hour.get("pv_kwh") or 0),
            home_load_kwh=float(hour.get("home_load_kwh") or 0),
            charge_efficiency=charge_efficiency,
            discharge_efficiency=discharge_efficiency,
            duration_minutes=int(hour.get("duration_minutes") or 60),
            power_limit_w=float(hour.get("power_limit_w") or default_power_limit_w),
            allow_battery_for_home=bool(hour.get("allow_battery_for_home", True)),
            grid_charge_request_kwh=float(hour.get("grid_charge_request_kwh") or 0),
            battery_sale_request_kwh=float(hour.get("battery_sale_request_kwh") or 0),
            source="forecast",
            data_quality=hour.get("data_quality"),
        )
        combined = {**hour, **row}
        result.append(combined)
        soc = float(row["soc_end_pct"])
    return result


def build_soc_timeline(
    *,
    now: datetime,
    historical_hours: list[dict[str, Any]],
    current_soc_pct: float | None,
    forecast_hours: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge immutable past, one current point and explicit forecast points."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    history_index = {
        str(row.get("hour") or "")[:13]: row
        for row in historical_hours
        if isinstance(row, dict)
    }
    forecast_index = {
        str(row.get("timestamp") or row.get("hour") or "")[:13]: row
        for row in forecast_hours
        if isinstance(row, dict)
    }
    points = []
    for index in range(48):
        moment = start + timedelta(hours=index)
        key = moment.isoformat()[:13]
        if moment.hour < now.hour and moment.date() == now.date():
            stored = history_index.get(key)
            value = stored.get("soc_end") if stored else None
            if value is None and stored:
                value = stored.get("soc_end_pct")
            points.append({
                "timestamp": moment.isoformat(),
                "soc_pct": value,
                "source": "actual" if value is not None else "missing",
                "reason": None if value is not None else "brak godzinowego zapisu SOC",
            })
        elif moment.hour == now.hour and moment.date() == now.date():
            points.append({
                "timestamp": now.isoformat(),
                "soc_pct": current_soc_pct,
                "source": "actual" if _finite(current_soc_pct) is not None else "missing",
                "boundary": "now",
                "reason": None if _finite(current_soc_pct) is not None else "brak aktualnego SOC — fail-closed",
            })
        else:
            forecast = forecast_index.get(key)
            value = forecast.get("soc_end_pct") if forecast else None
            points.append({
                "timestamp": moment.isoformat(),
                "soc_pct": value,
                "source": "forecast" if value is not None and _finite(current_soc_pct) is not None else "missing",
                "reason": None if value is not None else "brak prognozy SOC",
            })
    return points

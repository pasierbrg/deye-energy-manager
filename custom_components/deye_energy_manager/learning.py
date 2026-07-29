"""Lightweight local learning models used by Optimizer Core."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
from statistics import mean
from typing import Any


LEARNING_PROFILE_VERSION = 1
PV_RATIO_MIN = 0.4
PV_RATIO_MAX = 1.6


def learning_stage(completed_days: int) -> dict[str, Any]:
    days = max(0, int(completed_days))
    if days < 3:
        name, cap, ready, dry_run = "Zbieranie danych", 25, False, True
    elif days < 7:
        name, cap, ready, dry_run = "Plan wstępny", 35, False, True
    elif days < 21:
        name, cap, ready, dry_run = "Wstępne uczenie", 70, True, False
    elif days < 60:
        name, cap, ready, dry_run = "Profil podstawowy gotowy", 85, True, False
    else:
        name, cap, ready, dry_run = "Profil rozszerzony", 100, True, False
    return {
        "status": name,
        "completed_days": days,
        "confidence_cap": cap,
        "suggestion_ready": ready,
        "dry_run": dry_run,
        "apply_allowed": ready,
        "readiness": {
            "first_plan": {"value": min(days, 3), "target": 3},
            "home_profile": {"value": min(days, 7), "target": 7},
            "solcast_correction": {"value": min(days, 21), "target": 21},
            "extended_profile": {"value": min(days, 60), "target": 60},
        },
    }


def _cell_key(moment: datetime) -> str:
    return f"{moment.weekday()}-{moment.hour:02d}"


def update_load_profile(
    profile: dict[str, Any] | None,
    *,
    moment: datetime,
    load_kwh: float | None,
    complete: bool,
    quality_score: float,
) -> dict[str, Any]:
    """Update one of 168 EWMA cells without learning from incomplete data."""
    result = deepcopy(profile) if isinstance(profile, dict) else {}
    result.setdefault("schema_version", LEARNING_PROFILE_VERSION)
    cells = result.setdefault("cells", {})
    result.setdefault("accepted_samples", 0)
    result.setdefault("rejected_samples", 0)
    key = _cell_key(moment)
    value = float(load_kwh) if load_kwh is not None and math.isfinite(float(load_kwh)) else None
    if not complete or value is None or value < 0 or quality_score < 60:
        result["rejected_samples"] += 1
        result["last_rejection_reason"] = (
            "niepełna godzina" if not complete else
            "brak poprawnego zużycia" if value is None or value < 0 else
            "niska jakość źródła LOAD"
        )
        return result

    cell = dict(cells.get(key)) if isinstance(cells.get(key), dict) else {}
    samples = int(cell.get("samples", 0))
    previous = cell.get("mean_kwh")
    # Limit one extreme sample before EWMA; the raw value remains in history.
    if isinstance(previous, (int, float)) and previous > 0 and samples >= 3:
        bounded = max(previous * 0.25, min(previous * 4.0, value))
    else:
        bounded = value
    alpha = max(0.08, min(0.35, 2.0 / (samples + 2.0)))
    predicted = float(previous) if isinstance(previous, (int, float)) else bounded
    error = abs(value - predicted)
    average = bounded if samples == 0 else (1 - alpha) * predicted + alpha * bounded
    mae = float(cell.get("mae_kwh", error))
    mae = error if samples == 0 else (mae * samples + error) / (samples + 1)
    cells[key] = {
        "weekday": moment.weekday(),
        "hour": moment.hour,
        "mean_kwh": round(max(0.0, average), 5),
        "mae_kwh": round(max(0.0, mae), 5),
        "samples": samples + 1,
        "last_value_kwh": round(value, 5),
        "last_updated": moment.isoformat(),
    }
    result["accepted_samples"] += 1
    result["last_updated"] = moment.isoformat()
    return result


def forecast_load(profile: dict[str, Any] | None, moment: datetime) -> tuple[float | None, str, int]:
    """Return the most specific load estimate and its transparent fallback."""
    cells = profile.get("cells", {}) if isinstance(profile, dict) else {}
    exact = cells.get(_cell_key(moment)) if isinstance(cells, dict) else None
    if isinstance(exact, dict) and int(exact.get("samples", 0)) > 0:
        return float(exact.get("mean_kwh", 0)), "weekday_hour", int(exact.get("samples", 0))

    same_hour = [
        cell for cell in cells.values()
        if isinstance(cell, dict)
        and int(cell.get("hour", -1)) == moment.hour
        and ((int(cell.get("weekday", 0)) >= 5) == (moment.weekday() >= 5))
        and int(cell.get("samples", 0)) > 0
    ]
    if same_hour:
        return mean(float(cell.get("mean_kwh", 0)) for cell in same_hour), "day_type_hour", sum(int(cell.get("samples", 0)) for cell in same_hour)
    all_hour = [
        cell for cell in cells.values()
        if isinstance(cell, dict) and int(cell.get("hour", -1)) == moment.hour and int(cell.get("samples", 0)) > 0
    ]
    if all_hour:
        return mean(float(cell.get("mean_kwh", 0)) for cell in all_hour), "hour_only", sum(int(cell.get("samples", 0)) for cell in all_hour)
    return None, "missing", 0


def load_profile_diagnostics(
    profile: dict[str, Any] | None,
    *,
    completed_days: int,
) -> dict[str, Any]:
    cells = profile.get("cells", {}) if isinstance(profile, dict) else {}
    valid = [cell for cell in cells.values() if isinstance(cell, dict) and int(cell.get("samples", 0)) > 0]
    daily = sum(float(cell.get("mean_kwh", 0)) for cell in valid) / 7 if valid else None
    errors = [float(cell.get("mae_kwh", 0)) for cell in valid]
    base = min((float(cell.get("mean_kwh", 0)) for cell in valid), default=None)
    morning = max((float(cell.get("mean_kwh", 0)) for cell in valid if 5 <= int(cell.get("hour", 0)) <= 10), default=None)
    evening = max((float(cell.get("mean_kwh", 0)) for cell in valid if 16 <= int(cell.get("hour", 0)) <= 23), default=None)
    stage = learning_stage(completed_days)
    return {
        "status": stage["status"] if valid else "Brak wiarygodnych próbek",
        "completed_days": completed_days,
        "covered_cells": len(valid),
        "total_cells": 168,
        "accepted_samples": int(profile.get("accepted_samples", 0)) if isinstance(profile, dict) else 0,
        "rejected_samples": int(profile.get("rejected_samples", 0)) if isinstance(profile, dict) else 0,
        "average_daily_kwh": round(daily, 3) if daily is not None else None,
        "base_load_kwh": round(base, 3) if base is not None else None,
        "morning_peak_kwh": round(morning, 3) if morning is not None else None,
        "evening_peak_kwh": round(evening, 3) if evening is not None else None,
        "forecast_error_7d_kwh": round(mean(errors[-7 * 24:]), 3) if errors else None,
        "forecast_error_30d_kwh": round(mean(errors[-30 * 24:]), 3) if errors else None,
        "separate_weekday_weekend": any(int(cell.get("weekday", 0)) >= 5 for cell in valid) and any(int(cell.get("weekday", 0)) < 5 for cell in valid),
        "last_updated": profile.get("last_updated") if isinstance(profile, dict) else None,
        "reason": profile.get("last_rejection_reason") if not valid and isinstance(profile, dict) else None,
    }


def pv_quality_flags(
    *,
    battery_soc: float | None,
    work_mode: str,
    grid_available: bool,
    actual_power_w: float | None,
    inverter_limit_w: float | None,
    sensor_stale: bool,
    manual_override: bool,
    export_limit_active: bool = False,
) -> dict[str, bool]:
    battery_full = battery_soc is not None and battery_soc >= 98
    zero_export = str(work_mode).startswith("Zero Export")
    clipping = (
        actual_power_w is not None
        and inverter_limit_w is not None
        and inverter_limit_w > 0
        and actual_power_w >= inverter_limit_w * 0.97
    )
    flags = {
        "battery_full": battery_full,
        "export_limit_active": bool(export_limit_active),
        "zero_export_active": zero_export,
        "inverter_clipping": clipping,
        "grid_unavailable": not grid_available,
        "sensor_stale": bool(sensor_stale),
        "fallback_used": False,
        "manual_override": bool(manual_override),
    }
    flags["pv_curtailed"] = bool(
        (battery_full and zero_export)
        or export_limit_active
        or clipping
        or not grid_available
        or sensor_stale
        or manual_override
    )
    return flags


def update_pv_profile(
    profile: dict[str, Any] | None,
    *,
    moment: datetime,
    forecast_kwh: float | None,
    actual_kwh: float | None,
    flags: dict[str, Any],
    complete: bool,
) -> dict[str, Any]:
    """Learn bounded hourly/seasonal Solcast ratios, rejecting curtailment."""
    result = deepcopy(profile) if isinstance(profile, dict) else {}
    result.setdefault("schema_version", LEARNING_PROFILE_VERSION)
    result.setdefault("cells", {})
    result.setdefault("accepted_samples", 0)
    result.setdefault("rejected_samples", 0)
    result.setdefault("curtailed_hours", 0)
    result.setdefault("clipping_hours", 0)
    result.setdefault("unknown_limit_hours", 0)
    forecast = float(forecast_kwh) if forecast_kwh is not None else None
    actual = float(actual_kwh) if actual_kwh is not None else None
    curtailed = bool(flags.get("pv_curtailed"))
    if curtailed:
        result["curtailed_hours"] += 1
    if flags.get("inverter_clipping"):
        result["clipping_hours"] += 1
    if actual is not None and forecast is not None and actual < forecast * 0.5 and not any(flags.values()):
        result["unknown_limit_hours"] += 1
    if not complete or forecast is None or actual is None or forecast < 0.05 or curtailed:
        result["rejected_samples"] += 1
        result["last_rejection_reason"] = (
            "curtailment lub clipping" if curtailed else
            "niepełna godzina" if not complete else
            "brak wiarygodnej prognozy godzinowej"
        )
        return result

    key = f"{moment.month:02d}-{moment.hour:02d}"
    cell = dict(result["cells"].get(key)) if isinstance(result["cells"].get(key), dict) else {}
    samples = int(cell.get("samples", 0))
    raw_ratio = actual / forecast
    ratio = max(PV_RATIO_MIN, min(PV_RATIO_MAX, raw_ratio))
    alpha = max(0.08, min(0.3, 2.0 / (samples + 2.0)))
    previous = float(cell.get("ratio", 1.0))
    corrected_before = forecast * previous
    cell.update({
        "month": moment.month,
        "hour": moment.hour,
        "ratio": round(ratio if samples == 0 else previous * (1 - alpha) + ratio * alpha, 5),
        "samples": samples + 1,
        "solcast_abs_error_kwh": round((float(cell.get("solcast_abs_error_kwh", 0)) * samples + abs(actual - forecast)) / (samples + 1), 5),
        "corrected_abs_error_kwh": round((float(cell.get("corrected_abs_error_kwh", 0)) * samples + abs(actual - corrected_before)) / (samples + 1), 5),
        "last_updated": moment.isoformat(),
    })
    result["cells"][key] = cell
    result["accepted_samples"] += 1
    result["last_updated"] = moment.isoformat()
    return result


def corrected_pv_forecast(
    profile: dict[str, Any] | None,
    *,
    moment: datetime,
    forecast_kwh: float | None,
) -> tuple[float | None, float, int]:
    if forecast_kwh is None or forecast_kwh < 0.05:
        return forecast_kwh, 1.0, 0
    cells = profile.get("cells", {}) if isinstance(profile, dict) else {}
    cell = cells.get(f"{moment.month:02d}-{moment.hour:02d}") if isinstance(cells, dict) else None
    if not isinstance(cell, dict):
        return forecast_kwh, 1.0, 0
    samples = int(cell.get("samples", 0))
    learned = float(cell.get("ratio", 1.0))
    weight = min(1.0, samples / 21.0)
    applied = 1.0 + (learned - 1.0) * weight
    return max(0.0, forecast_kwh * applied), applied, samples


def pv_profile_diagnostics(profile: dict[str, Any] | None, *, completed_days: int) -> dict[str, Any]:
    cells = profile.get("cells", {}) if isinstance(profile, dict) else {}
    valid = [cell for cell in cells.values() if isinstance(cell, dict) and int(cell.get("samples", 0)) > 0]
    solcast_errors = [float(cell.get("solcast_abs_error_kwh", 0)) for cell in valid]
    corrected_errors = [float(cell.get("corrected_abs_error_kwh", 0)) for cell in valid]

    def period_ratio(start: int, end: int) -> float | None:
        values = [float(cell.get("ratio", 1)) for cell in valid if start <= int(cell.get("hour", 0)) <= end]
        return mean(values) if values else None

    solcast_mae = mean(solcast_errors) if solcast_errors else None
    corrected_mae = mean(corrected_errors) if corrected_errors else None
    return {
        "status": learning_stage(completed_days)["status"] if valid else "Brak wiarygodnych próbek",
        "completed_days": completed_days,
        "accepted_samples": int(profile.get("accepted_samples", 0)) if isinstance(profile, dict) else 0,
        "rejected_samples": int(profile.get("rejected_samples", 0)) if isinstance(profile, dict) else 0,
        "curtailed_hours": int(profile.get("curtailed_hours", 0)) if isinstance(profile, dict) else 0,
        "clipping_hours": int(profile.get("clipping_hours", 0)) if isinstance(profile, dict) else 0,
        "unknown_limit_hours": int(profile.get("unknown_limit_hours", 0)) if isinstance(profile, dict) else 0,
        "solcast_mae_kwh": round(solcast_mae, 3) if solcast_mae is not None else None,
        "corrected_mae_kwh": round(corrected_mae, 3) if corrected_mae is not None else None,
        "improvement_percent": round((solcast_mae - corrected_mae) / solcast_mae * 100, 1) if solcast_mae and corrected_mae is not None else None,
        "morning_correction": round(period_ratio(5, 10), 3) if period_ratio(5, 10) is not None else None,
        "midday_correction": round(period_ratio(11, 15), 3) if period_ratio(11, 15) is not None else None,
        "evening_correction": round(period_ratio(16, 21), 3) if period_ratio(16, 21) is not None else None,
        "last_updated": profile.get("last_updated") if isinstance(profile, dict) else None,
        "reason": profile.get("last_rejection_reason") if not valid and isinstance(profile, dict) else None,
    }

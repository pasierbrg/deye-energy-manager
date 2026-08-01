"""Independent telemetry quality and hourly energy-balance helpers.

The helpers are deliberately free of Home Assistant dependencies so that the
minute-to-hour pipeline can be regression-tested without starting HA.
"""

from __future__ import annotations

import math
from typing import Any


QUALITY_SCORE = {
    "good": 100.0,
    "degraded": 70.0,
    "low": 40.0,
    "unavailable": 0.0,
}


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def new_channel() -> dict[str, Any]:
    return {
        "samples": 0,
        "valid_samples": 0,
        "covered_seconds": 0.0,
        "quality_sum": 0.0,
        "last_status": "unavailable",
        "last_source": "unavailable",
        "last_value": None,
    }


def record_channel(
    channel: dict[str, Any] | None,
    *,
    value: Any,
    elapsed_seconds: float,
    quality: str = "good",
    status: str = "ok",
    source: str = "primary",
) -> dict[str, Any]:
    """Record one independent channel sample without converting missing to 0."""
    result = dict(channel) if isinstance(channel, dict) else new_channel()
    result["samples"] = int(result.get("samples", 0)) + 1
    result["last_status"] = str(status or "unavailable")
    result["last_source"] = str(source or "unavailable")
    number = finite(value)
    if number is None:
        result["last_value"] = None
        return result
    seconds = max(0.0, min(120.0, finite(elapsed_seconds) or 0.0))
    result["valid_samples"] = int(result.get("valid_samples", 0)) + 1
    result["covered_seconds"] = float(result.get("covered_seconds", 0.0)) + seconds
    result["quality_sum"] = float(result.get("quality_sum", 0.0)) + QUALITY_SCORE.get(
        str(quality),
        0.0,
    )
    result["last_value"] = number
    return result


def channel_summary(
    channel: dict[str, Any] | None,
    *,
    expected_seconds: float = 3600.0,
) -> dict[str, Any]:
    item = channel if isinstance(channel, dict) else {}
    samples = max(0, int(item.get("samples", 0)))
    valid = max(0, int(item.get("valid_samples", 0)))
    covered = max(0.0, float(item.get("covered_seconds", 0.0)))
    expected = max(1.0, float(expected_seconds))
    coverage = min(100.0, covered / expected * 100.0)
    average_quality = (
        float(item.get("quality_sum", 0.0)) / valid
        if valid
        else 0.0
    )
    if valid == 0 or coverage <= 0:
        level = "missing"
    elif coverage >= 90:
        level = "full"
    elif coverage >= 60:
        level = "partial"
    else:
        level = "very_low"
    return {
        "samples": samples,
        "valid_samples": valid,
        "missing_samples": max(0, samples - valid),
        "covered_seconds": round(covered, 1),
        "coverage_percent": round(coverage, 1),
        "quality_score": round(average_quality, 1),
        "level": level,
        "usable_for_learning": valid > 0 and average_quality >= 40,
        "last_status": item.get("last_status"),
        "last_source": item.get("last_source"),
    }


def split_directional_power(
    *,
    grid_power_w: Any,
    battery_power_w: Any,
) -> dict[str, float | None]:
    """Expose both physical directions while preserving missing measurements.

    Grid power is positive for import and battery power is positive for
    discharge. A valid zero remains a valid zero; an unavailable signed channel
    produces two unavailable directional channels.
    """
    grid = finite(grid_power_w)
    battery = finite(battery_power_w)
    return {
        "grid_import_power": max(0.0, grid) if grid is not None else None,
        "grid_export_power": max(0.0, -grid) if grid is not None else None,
        "battery_charge_power": max(0.0, -battery) if battery is not None else None,
        "battery_discharge_power": max(0.0, battery) if battery is not None else None,
    }


def energy_balance(
    *,
    pv_kwh: Any,
    load_kwh: Any,
    grid_import_kwh: Any,
    grid_export_kwh: Any,
    battery_charge_kwh: Any,
    battery_discharge_kwh: Any,
) -> dict[str, Any]:
    """Compare hourly energy entering and leaving the local installation."""
    pv = finite(pv_kwh)
    load = finite(load_kwh)
    imported = finite(grid_import_kwh)
    exported = finite(grid_export_kwh)
    charged = finite(battery_charge_kwh)
    discharged = finite(battery_discharge_kwh)
    values = (pv, load, imported, exported, charged, discharged)
    if any(value is None for value in values):
        return {
            "status": "insufficient_data",
            "difference_kwh": None,
            "difference_percent": None,
            "usable": False,
        }
    incoming = pv + imported + discharged
    outgoing = load + exported + charged
    difference = incoming - outgoing
    reference = max(0.05, incoming, outgoing)
    percent = abs(difference) / reference * 100.0
    status = "ok" if percent <= 10 else "warning" if percent <= 25 else "inconsistent"
    return {
        "status": status,
        "incoming_kwh": round(incoming, 5),
        "outgoing_kwh": round(outgoing, 5),
        "difference_kwh": round(difference, 5),
        "difference_percent": round(percent, 1),
        "usable": status != "inconsistent",
    }

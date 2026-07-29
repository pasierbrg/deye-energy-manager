"""Versioned history helpers for Deye Energy Manager.

The Home Assistant ``Store`` envelope intentionally stays at version 1 so an
upgrade can always read files written by 0.7.6.  ``schema_version`` below is
the application-level payload version and is migrated without deleting or
renaming historical rows.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any

HISTORY_SCHEMA_VERSION = 2
PROFILE_SCHEMA_VERSION = 2

UNKNOWN_STATES = {"", "unknown", "unavailable", "none", "nan", "inf", "-inf"}
POWER_UNITS = {"w": 1.0, "kw": 1000.0}
ENERGY_UNITS = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}


def finite_float(value: Any) -> float | None:
    """Return a finite number or ``None`` without inventing a zero."""
    if isinstance(value, str) and value.strip().lower() in UNKNOWN_STATES:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def power_w(value: Any, unit: Any) -> float | None:
    """Normalize a power state to watts and reject an incompatible unit."""
    number = finite_float(value)
    factor = POWER_UNITS.get(str(unit or "").strip().lower())
    return number * factor if number is not None and factor is not None else None


def energy_kwh(value: Any, unit: Any) -> float | None:
    """Normalize an energy state to kWh and reject an incompatible unit."""
    number = finite_float(value)
    factor = ENERGY_UNITS.get(str(unit or "").strip().lower())
    return number * factor if number is not None and factor is not None else None


@dataclass(frozen=True)
class CounterUpdate:
    """One monotonic contribution from a daily or total energy counter."""

    delta_kwh: float
    reset_detected: bool
    first_sample: bool
    state: dict[str, Any]


def update_energy_counter(
    previous: dict[str, Any] | None,
    *,
    value_kwh: float,
    day: str,
    timestamp: str,
    total_increasing: bool,
) -> CounterUpdate:
    """Update a counter without turning midnight reset into negative energy.

    For a daily counter, the first valid sample of a new day is a contribution
    since midnight.  For a lifetime ``total_increasing`` counter, a decrease is
    treated as a meter reset and only the new non-negative value contributes.
    """
    current = max(0.0, float(value_kwh))
    old = previous if isinstance(previous, dict) else {}
    old_value = finite_float(old.get("value_kwh"))
    old_day = str(old.get("day") or "")
    first = old_value is None
    reset = False

    if first:
        delta = 0.0 if total_increasing else current
    elif day != old_day and not total_increasing:
        reset = True
        delta = current
    elif current + 1e-9 < old_value:
        reset = True
        delta = current
    else:
        delta = current - old_value

    state = {
        "value_kwh": round(current, 6),
        "day": day,
        "timestamp": timestamp,
        "reset_detected": reset,
        "last_delta_kwh": round(max(0.0, delta), 6),
        "total_increasing": bool(total_increasing),
    }
    return CounterUpdate(max(0.0, delta), reset, first, state)


def migrate_ai_payload(raw: Any) -> tuple[dict[str, Any], bool]:
    """Migrate the shared AI/settings payload while preserving 0.7.6 data."""
    data = deepcopy(raw) if isinstance(raw, dict) else {}
    changed = int(finite_float(data.get("schema_version")) or 1) < HISTORY_SCHEMA_VERSION
    data["schema_version"] = HISTORY_SCHEMA_VERSION
    profiles = data.get("user_profiles")
    if not isinstance(profiles, dict):
        data["user_profiles"] = default_user_profiles()
        changed = True
    else:
        normalized = default_user_profiles()
        for key, defaults in normalized["profiles"].items():
            stored = profiles.get("profiles", {}).get(key) if isinstance(profiles.get("profiles"), dict) else None
            if isinstance(stored, dict):
                defaults.update(stored)
                if defaults.get("priority") not in ("low", "normal", "high"):
                    legacy_priority = finite_float(defaults.get("priority"))
                    defaults["priority"] = (
                        "high" if legacy_priority is not None and legacy_priority >= 75
                        else "low" if legacy_priority is not None and legacy_priority < 25
                        else "normal"
                    )
        normalized["schema_version"] = PROFILE_SCHEMA_VERSION
        if normalized != profiles:
            changed = True
        data["user_profiles"] = normalized
    return data, changed


def migrate_solcast_payload(raw: Any) -> tuple[dict[str, Any], bool]:
    """Add unambiguous forecast snapshot fields to old Solcast rows."""
    data = deepcopy(raw) if isinstance(raw, dict) else {}
    changed = int(finite_float(data.get("schema_version")) or 1) < HISTORY_SCHEMA_VERSION
    history = data.get("history") if isinstance(data.get("history"), list) else []
    migrated: list[dict[str, Any]] = []
    for source in history:
        row = dict(source) if isinstance(source, dict) else {}
        legacy = finite_float(row.get("forecast_kwh"))
        if "initial_forecast_kwh" not in row:
            row["initial_forecast_kwh"] = legacy
            changed = True
        if "latest_forecast_kwh" not in row:
            row["latest_forecast_kwh"] = legacy
            changed = True
        row.setdefault("forecast_snapshots", [])
        migrated.append(row)
    tracking = dict(data.get("tracking")) if isinstance(data.get("tracking"), dict) else {}
    legacy_tracking = finite_float(tracking.get("forecast"))
    if tracking and "initial_forecast_kwh" not in tracking:
        tracking["initial_forecast_kwh"] = legacy_tracking
        changed = True
    if tracking and "latest_forecast_kwh" not in tracking:
        tracking["latest_forecast_kwh"] = legacy_tracking
        changed = True
    tracking.setdefault("forecast_snapshots", [])
    data.update(
        schema_version=HISTORY_SCHEMA_VERSION,
        history=migrated,
        tracking=tracking,
    )
    return data, changed


def migrate_learning_payload(raw: Any) -> tuple[dict[str, Any], bool]:
    data = deepcopy(raw) if isinstance(raw, dict) else {}
    changed = int(finite_float(data.get("schema_version")) or 1) < HISTORY_SCHEMA_VERSION
    data["schema_version"] = HISTORY_SCHEMA_VERSION
    data.setdefault("history", [])
    data.setdefault("tracking", {})
    data.setdefault("load_profile_7x24", {})
    data.setdefault("pv_profile", {})
    data.setdefault("profile_execution", [])
    return data, changed


def migrate_energy_payload(raw: Any) -> tuple[dict[str, Any], bool]:
    data = deepcopy(raw) if isinstance(raw, dict) else {}
    changed = int(finite_float(data.get("schema_version")) or 1) < HISTORY_SCHEMA_VERSION
    data["schema_version"] = HISTORY_SCHEMA_VERSION
    data.setdefault("samples", [])
    data.setdefault("daily", [])
    data.setdefault("monthly", [])
    data.setdefault("counter_state", {})
    return data, changed


def default_user_profiles() -> dict[str, Any]:
    """Safe migration defaults: every new strategy is opt-in."""
    sale = {
        "enabled": False,
        "type": "sale",
        "active_days": [],
        "start": "06:00",
        "end": "09:00",
        "priority": "normal",
        "goal_character": "preferred",
        "allow_partial": True,
        "minimum_confidence": 50.0,
        "note": "",
        "target_energy_kwh": 0.0,
        "target_basis": "battery_to_grid",
        "min_price": 0.0,
        "preferred_power_w": None,
        "distribution_method": "best_hours",
        "min_soc_after": 30.0,
        "allow_earlier_grid_charge": False,
        "min_net_result": 0.0,
        # Legacy aliases remain readable by the 0.7.6 frontend.
        "minimum_price": 0.0,
        "minimum_soc": 30.0,
        "target_soc": 30.0,
        "power_limit_w": None,
    }
    charge = {
        "enabled": False,
        "type": "charging",
        "active_days": [],
        "start": "22:00",
        "end": "06:00",
        "priority": "normal",
        "goal_character": "preferred",
        "allow_partial": True,
        "minimum_confidence": 50.0,
        "note": "",
        "source": "auto",
        "target_type": "soc",
        "target_value": 80.0,
        "deadline": "06:00",
        "max_effective_price": 0.0,
        "max_grid_energy_kwh": None,
        "preferred_power_w": None,
        "purpose": "general",
        "charge_missing_only": True,
        "use_corrected_pv": True,
        "preserve_pv_room": True,
        "minimum_free_room_kwh": 0.0,
        "profitable_only": True,
        # Legacy aliases remain readable by the 0.7.6 frontend.
        "maximum_total_price": 0.0,
        "target_soc": 80.0,
        "power_limit_w": None,
    }
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profiles": {
            "morning_sale": {**sale, "name": "Poranna sprzedaż"},
            "evening_sale": {
                **sale,
                "name": "Wieczorna sprzedaż",
                "start": "17:00",
                "end": "22:00",
            },
            "charging": {**charge, "name": "Ładowanie"},
        },
    }

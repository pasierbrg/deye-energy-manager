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

HISTORY_SCHEMA_VERSION = 4
PROFILE_SCHEMA_VERSION = 2
ENERGY_COMPACT_FORMAT_VERSION = 2

ENERGY_COMPACT_FIELDS = (
    "timestamp",
    "interval_seconds",
    "pv_power",
    "load_power",
    "grid_power",
    "battery_power",
    "soc",
    "sell_price",
    "buy_price",
)

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
    # Every normalized nested value below is replaced with a new container.
    # A shallow root copy avoids duplicating a potentially large restored plan
    # before it is compacted by the manager.
    data = dict(raw) if isinstance(raw, dict) else {}
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
    archive = data.get("plan_execution_archive")
    if not isinstance(archive, list):
        data["plan_execution_archive"] = []
        changed = True
    else:
        normalized_archive = [
            dict(row)
            for row in archive
            if isinstance(row, dict)
            and isinstance(row.get("date"), str)
            and finite_float(row.get("hour")) is not None
        ][:2160]
        if normalized_archive != archive:
            changed = True
        data["plan_execution_archive"] = normalized_archive
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
    if tracking and "forecast_snapshots" not in tracking:
        tracking["forecast_snapshots"] = []
        changed = True
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
    source_history = data.get("history") if isinstance(data.get("history"), list) else []
    history: list[dict[str, Any]] = []
    field_map = {
        "pv": ("pv_kwh",),
        "load": ("load_kwh",),
        "load_l1": ("load_l1_kwh",),
        "load_l2": ("load_l2_kwh",),
        "load_l3": ("load_l3_kwh",),
        "grid": ("grid_import_kwh", "grid_export_kwh"),
        "battery": ("battery_charge_kwh", "battery_discharge_kwh"),
        "soc": ("soc_start", "soc_end", "soc_avg"),
        "sell_price": ("sell_price_avg",),
        "buy_price": ("buy_price_avg",),
    }
    for source in source_history:
        row = dict(source) if isinstance(source, dict) else {}
        row["schema_version"] = HISTORY_SCHEMA_VERSION
        if not isinstance(row.get("channel_quality"), dict):
            samples = max(0, int(finite_float(row.get("samples")) or 0))
            coverage = finite_float(row.get("completeness_percent"))
            if coverage is None:
                coverage = min(100.0, samples / 60.0 * 100.0)
            global_quality = (
                finite_float((row.get("source_quality") or {}).get("score"))
                if isinstance(row.get("source_quality"), dict)
                else None
            )
            quality = 70.0 if global_quality is None else global_quality
            channels: dict[str, dict[str, Any]] = {}
            for name, fields in field_map.items():
                available = any(finite_float(row.get(field)) is not None for field in fields)
                effective_coverage = coverage if available else 0.0
                level = (
                    "full" if effective_coverage >= 90
                    else "partial" if effective_coverage >= 60
                    else "very_low" if effective_coverage > 0
                    else "missing"
                )
                channels[name] = {
                    "samples": samples,
                    "valid_samples": samples if available else 0,
                    "missing_samples": 0 if available else samples,
                    "covered_seconds": round(effective_coverage / 100.0 * 3600.0, 1),
                    "coverage_percent": round(effective_coverage, 1),
                    "quality_score": round(quality, 1) if available else 0.0,
                    "level": level,
                    "usable_for_learning": available and quality >= 40,
                    "last_status": "legacy_migrated" if available else "unavailable",
                    "last_source": "legacy_hourly_history",
                }
            row["channel_quality"] = channels
            changed = True
        history.append(row)
    data["history"] = history
    data.setdefault("tracking", {})
    data.setdefault("load_profile_7x24", {})
    data.setdefault("pv_profile", {})
    data.setdefault("profile_execution", [])
    usable_hours = {
        str(row.get("hour"))
        for row in history
        if row.get("hour")
        and any(
            item.get("usable_for_learning")
            for item in (row.get("channel_quality") or {}).values()
            if isinstance(item, dict)
        )
    }
    if "learning_revision" not in data:
        data["learning_revision"] = len(usable_hours)
        changed = True
    else:
        revision = max(0, int(finite_float(data.get("learning_revision")) or 0))
        if data.get("learning_revision") != revision:
            data["learning_revision"] = revision
            changed = True
    if "history_watermark" not in data:
        data["history_watermark"] = max(
            (str(row.get("hour")) for row in history if row.get("hour")),
            default="",
        )
        changed = True
    return data, changed


def compact_energy_sample(value: Any) -> dict[str, Any]:
    """Return the lossless algorithm/archive subset of a raw energy sample."""
    source = value if isinstance(value, dict) else {}
    return {
        key: source.get(key)
        for key in ENERGY_COMPACT_FIELDS
        if key in source
    }


def migrate_energy_payload(raw: Any) -> tuple[dict[str, Any], bool]:
    """Migrate raw one-minute history to the compact, restart-safe format.

    The last 288 detailed samples remain available separately for the public AI
    sensor. Older details were never consumed by an algorithm; their compact
    fields are exactly those used by the archive integrator.
    """
    source = raw if isinstance(raw, dict) else {}
    samples = source.get("samples") if isinstance(source.get("samples"), list) else []
    recent_source = (
        source.get("recent_details")
        if isinstance(source.get("recent_details"), list)
        else samples[-288:]
    )
    compact_samples = [
        compact_energy_sample(row)
        for row in samples
        if isinstance(row, dict)
    ]
    recent_details = [
        dict(row)
        for row in recent_source[-288:]
        if isinstance(row, dict)
    ]
    format_version = int(finite_float(source.get("energy_format_version")) or 1)
    changed = (
        int(finite_float(source.get("schema_version")) or 1) < HISTORY_SCHEMA_VERSION
        or format_version < ENERGY_COMPACT_FORMAT_VERSION
        or len(compact_samples) != len(samples)
        or source.get("recent_details") != recent_details
        or source.get("samples") != compact_samples
    )
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "energy_format_version": ENERGY_COMPACT_FORMAT_VERSION,
        "samples": compact_samples,
        "recent_details": recent_details,
        "daily": source.get("daily") if isinstance(source.get("daily"), list) else [],
        "monthly": source.get("monthly") if isinstance(source.get("monthly"), list) else [],
        "counter_state": (
            source.get("counter_state")
            if isinstance(source.get("counter_state"), dict)
            else {}
        ),
        "last_sample": source.get("last_sample"),
        "learning_checkpoint": (
            dict(source.get("learning_checkpoint"))
            if isinstance(source.get("learning_checkpoint"), dict)
            else {}
        ),
    }, changed


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
        "purpose": "mixed",
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

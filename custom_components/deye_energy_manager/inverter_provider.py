"""Provider-specific translation for Deye entities exposed in Home Assistant.

The manager always works with its stable logical Deye model.  This module is
the only place where provider-specific entity domains and option labels are
translated.  It deliberately contains no MQTT client and never writes raw
registers.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .const import (
    ABSOLUTE_INVERTER_MAX_POWER_W,
    CONF_INVERTER_PROVIDER,
    CONF_WORK_MODE_SELL_OPTION,
    CONF_WORK_MODE_ZERO_LOAD_OPTION,
    CONF_WORK_MODE_ZERO_CT_OPTION,
    CONF_TOU_GRID_ENABLE_OPTION,
    CONF_TOU_GRID_DISABLE_OPTION,
    CONF_TOU_GRID_GENERATOR_OPTION,
    CONF_TOU_GRID_BOTH_OPTION,
    DEFAULT_INVERTER_PROVIDER,
    MODE_NORMAL_OPERATION,
    MODE_SELLING_FIRST,
    MODE_ZERO_EXPORT,
    MODE_ZERO_EXPORT_CT,
    PHYSICAL_NORMAL_MODES,
    PROVIDER_CUSTOM,
    PROVIDER_DEYE_ADDON,
    PROVIDER_LEWA_REKA,
    PROVIDER_SOLARMAN,
    PROVIDER_SUNSYNK,
)


def detect_entity_max_power_w(state: Any, *, absolute_max: int = ABSOLUTE_INVERTER_MAX_POWER_W) -> int | None:
    """Return a reliable Max Sell Power entity maximum in watts.

    Accepts only ``W`` or ``kW`` as the unit of measurement. Other units
    (Wh, kWh, A, %, unknown or missing) are rejected and reported as None.
    Values outside the 1000–absolute_max W range are also rejected.
    """
    if state is None or state.state in ("unknown", "unavailable", "none", ""):
        return None
    attrs = getattr(state, "attributes", {}) or {}
    try:
        maximum = float(attrs["max"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(maximum) or maximum <= 0:
        return None
    unit = str(attrs.get("unit_of_measurement", "")).strip().lower()
    if unit == "kw":
        maximum *= 1000
    elif unit != "w":
        return None
    detected = int(round(maximum))
    if not 1000 <= detected <= absolute_max:
        return None
    return detected


@dataclass(frozen=True)
class NumberEntityRange:
    """Physical limits of a Home Assistant number entity, always in watts."""

    minimum_w: float | None
    maximum_w: float | None
    step_w: float | None
    native_unit: str | None


_INVALID_NUMBER_UNITS = {"wh", "kwh", "a", "%", ""}


def number_entity_range(state: Any) -> NumberEntityRange:
    """Return physical min/max/step of a number entity in watts.

    Accepts only ``W`` or ``kW`` as the unit of measurement. Other units
    (Wh, kWh, A, %, missing or unknown) are treated as unreliable and all
    limits are reported as None. The caller is then responsible for applying
    its own safe bounds.
    """
    if state is None or state.state in ("unknown", "unavailable", "none", ""):
        return NumberEntityRange(None, None, None, None)
    attrs = getattr(state, "attributes", {}) or {}
    unit = str(attrs.get("unit_of_measurement", "")).strip().lower()
    if unit in _INVALID_NUMBER_UNITS:
        return NumberEntityRange(None, None, None, unit if unit else None)
    if unit == "kw":
        factor = 1000.0
    elif unit == "w":
        factor = 1.0
    else:
        return NumberEntityRange(None, None, None, unit)
    try:
        minimum = float(attrs["min"]) * factor
        maximum = float(attrs["max"]) * factor
        step = float(attrs["step"]) * factor
    except (KeyError, TypeError, ValueError):
        return NumberEntityRange(None, None, None, unit)
    if not math.isfinite(minimum) or not math.isfinite(maximum) or not math.isfinite(step):
        return NumberEntityRange(None, None, None, unit)
    if step <= 0 or minimum > maximum:
        return NumberEntityRange(None, None, None, unit)
    return NumberEntityRange(minimum, maximum, step, unit)


def convert_w_to_native_unit(value_w: float, native_unit: str | None) -> float:
    """Convert a watt value to the entity's native unit before writing."""
    if native_unit is not None and native_unit.lower() == "kw":
        return value_w / 1000.0
    return value_w


@dataclass(frozen=True)
class ProviderProfile:
    key: str
    label: str
    work_mode_domains: tuple[str, ...]
    tou_start_domains: tuple[str, ...]
    tou_grid_domains: tuple[str, ...]
    sell_mode_option: str
    normal_mode_options: dict[str, str]
    default_normal_mode: str
    grid_enabled: str
    grid_disabled: str
    needs_aux_export_switch: bool = False
    native_tou: bool = True
    basic_control: bool = True
    notes: str = ""


PROFILES: dict[str, ProviderProfile] = {
    PROVIDER_LEWA_REKA: ProviderProfile(
        PROVIDER_LEWA_REKA,
        "ESPHome Deye Inverter — Lewa-Reka",
        ("select",),
        ("time",),
        ("switch",),
        "Selling First",
        {
            MODE_ZERO_EXPORT: MODE_ZERO_EXPORT,
            MODE_ZERO_EXPORT_CT: MODE_ZERO_EXPORT_CT,
        },
        MODE_ZERO_EXPORT,
        "on",
        "off",
    ),
    PROVIDER_SOLARMAN: ProviderProfile(
        PROVIDER_SOLARMAN,
        "Solarman",
        ("select",),
        ("time",),
        ("select",),
        "Export First",
        {
            MODE_ZERO_EXPORT: MODE_ZERO_EXPORT,
            MODE_ZERO_EXPORT_CT: MODE_ZERO_EXPORT_CT,
        },
        MODE_ZERO_EXPORT,
        "Grid",
        "Disabled",
    ),
    PROVIDER_SUNSYNK: ProviderProfile(
        PROVIDER_SUNSYNK,
        "Sunsynk",
        ("select",),
        ("select",),
        ("select",),
        "Allow Export",
        {
            MODE_ZERO_EXPORT: "Essentials",
            MODE_ZERO_EXPORT_CT: "Zero Export",
        },
        MODE_ZERO_EXPORT,
        "Allow Grid",
        "No Grid or Gen",
        needs_aux_export_switch=True,
    ),
    # Pinned source:
    # https://github.com/kbialek/deye-inverter-mqtt/tree/0fd4b4d6416f93118829fa7c133c1533bb6440f2
    # It publishes safe HA readings, but this revision does not expose a
    # complete native set of Work Mode and six Time Of Use slot controls. Keep
    # this provider read-only instead of guessing register writes or sending
    # raw MQTT commands.
    PROVIDER_DEYE_ADDON: ProviderProfile(
        PROVIDER_DEYE_ADDON,
        "Deye Inverter MQTT",
        ("select",),
        ("time", "select"),
        ("switch", "select"),
        "Selling First",
        {
            MODE_ZERO_EXPORT: MODE_ZERO_EXPORT,
            MODE_ZERO_EXPORT_CT: MODE_ZERO_EXPORT_CT,
        },
        MODE_ZERO_EXPORT,
        "on",
        "off",
        native_tou=False,
        basic_control=False,
        notes=(
            "kbialek/deye-inverter-mqtt publikuje odczyty, ale w przypiętej "
            "rewizji nie udostępnia kompletnego, natywnego sterowania Work Mode "
            "i sześcioma slotami Time Of Use."
        ),
    ),
    PROVIDER_CUSTOM: ProviderProfile(
        PROVIDER_CUSTOM,
        "Mapowanie niestandardowe",
        ("select",),
        ("time", "select"),
        ("switch", "select"),
        MODE_SELLING_FIRST,
        {
            MODE_ZERO_EXPORT: MODE_ZERO_EXPORT,
            MODE_ZERO_EXPORT_CT: MODE_ZERO_EXPORT_CT,
        },
        MODE_ZERO_EXPORT,
        "on",
        "off",
    ),
}

# Polish labels shown to the user for the physical normal-mode options of each
# provider.  The underlying technical option sent to the inverter is unchanged.
PHYSICAL_NORMAL_MODE_LABELS: dict[str, str] = {
    "Zero Export To Load": "Eksport wyłączony — pomiar Load",
    "Zero Export To CT": "Eksport wyłączony — pomiar CT",
    "Essentials": "Zasilanie odbiorów podstawowych",
    "Zero Export": "Eksport wyłączony",
}


def physical_normal_mode_label(option: str) -> str:
    """Return the Polish label for a technical normal-mode option."""
    return PHYSICAL_NORMAL_MODE_LABELS.get(str(option), str(option))


def normal_profile_mode_metadata(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return canonical, localized normal-mode choices for the frontend.

    Raw provider options deliberately stay inside this adapter.  Custom
    mappings are available only when the user configured the corresponding
    option; no synthetic inverter value is advertised to the card.
    """
    item = profile(data)
    rows: list[dict[str, Any]] = []
    canonical_labels = {
        MODE_ZERO_EXPORT: "Eksport wyłączony — pomiar Load",
        MODE_ZERO_EXPORT_CT: "Eksport wyłączony — pomiar CT",
    }
    for key in PHYSICAL_NORMAL_MODES:
        try:
            raw_option = logical_mode_option(data, MODE_NORMAL_OPERATION, key)
        except ValueError:
            raw_option = None
        available = bool(item.basic_control and raw_option)
        label = (
            canonical_labels[key]
            if provider_key(data) == PROVIDER_CUSTOM
            else physical_normal_mode_label(raw_option)
        )
        rows.append({"value": key, "label": label, "available": available})
    return rows


def normal_profile_mode_options(data: dict[str, Any]) -> list[str]:
    """Return Polish labels for the normal-profile mode select options."""
    return [row["label"] for row in normal_profile_mode_metadata(data) if row["available"]]


def normal_profile_mode_label_to_key(data: dict[str, Any], label: str) -> str | None:
    """Map a Polish select label to the internal physical-mode key."""
    for row in normal_profile_mode_metadata(data):
        if row["available"] and row["label"] == label:
            return str(row["value"])
    return None


def physical_normal_option_to_key(data: dict[str, Any], option: str) -> str | None:
    """Map a legacy technical provider option to the internal physical-mode key."""
    if provider_key(data) == PROVIDER_CUSTOM:
        load_option = data.get(CONF_WORK_MODE_ZERO_LOAD_OPTION)
        ct_option = data.get(CONF_WORK_MODE_ZERO_CT_OPTION)
        if load_option and option == load_option:
            return MODE_ZERO_EXPORT
        if ct_option and option == ct_option:
            return MODE_ZERO_EXPORT_CT
        return None
    for key, value in profile(data).normal_mode_options.items():
        if value == option:
            return key
    return None


def provider_key(data: dict[str, Any]) -> str:
    """Return a known provider, migrating old entries to Lewa-Reka."""
    value = str(data.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER))
    return value if value in PROFILES else DEFAULT_INVERTER_PROVIDER


def profile(data_or_key: dict[str, Any] | str) -> ProviderProfile:
    key = provider_key(data_or_key) if isinstance(data_or_key, dict) else str(data_or_key)
    return PROFILES.get(key, PROFILES[DEFAULT_INVERTER_PROVIDER])


def logical_mode_option(
    data: dict[str, Any],
    logical_mode: str,
    physical_work_mode: str | None = None,
) -> str:
    """Translate a logical Deye Energy Manager mode to the exact provider option.

    ``physical_work_mode`` is required for ``Normalna Praca`` and must be one of
    ``PHYSICAL_NORMAL_MODES``.  For ``Sprzedaż`` it is ignored.
    """
    if logical_mode == MODE_SELLING_FIRST:
        if provider_key(data) == PROVIDER_CUSTOM:
            configured = data.get(CONF_WORK_MODE_SELL_OPTION)
            if configured:
                return str(configured)
            raise ValueError("Brak skonfigurowanej opcji Sprzedaż dla providera Custom")
        return profile(data).sell_mode_option
    if logical_mode == MODE_NORMAL_OPERATION:
        physical = physical_work_mode or profile(data).default_normal_mode
        if physical not in PHYSICAL_NORMAL_MODES:
            raise ValueError(f"Nieznany kanoniczny wariant Normalnej Pracy: {physical}")
        if provider_key(data) == PROVIDER_CUSTOM:
            physical_to_key = {
                MODE_ZERO_EXPORT: CONF_WORK_MODE_ZERO_LOAD_OPTION,
                MODE_ZERO_EXPORT_CT: CONF_WORK_MODE_ZERO_CT_OPTION,
            }
            configured = data.get(physical_to_key.get(physical, ""))
            if configured:
                return str(configured)
            raise ValueError(
                f"Brak skonfigurowanej opcji {physical} dla providera Custom"
            )
        configured = profile(data).normal_mode_options.get(physical)
        if configured:
            return configured
        raise ValueError(f"Provider {profile(data).label} nie obsługuje wariantu {physical}")
    raise ValueError(f"Logical mode has no direct inverter work mode option: {logical_mode}")


def logical_mode_matches(
    data: dict[str, Any],
    logical_mode: str,
    state: str,
    physical_work_mode: str | None = None,
) -> bool:
    return str(state) == logical_mode_option(data, logical_mode, physical_work_mode)


def boolean_option(data: dict[str, Any], role: str, enabled: bool) -> str:
    item = profile(data)
    if provider_key(data) == PROVIDER_CUSTOM and role == "grid":
        key = CONF_TOU_GRID_ENABLE_OPTION if enabled else CONF_TOU_GRID_DISABLE_OPTION
        configured = data.get(key)
        if configured:
            return str(configured)
    if role == "grid":
        return item.grid_enabled if enabled else item.grid_disabled
    raise ValueError(f"Unknown provider boolean role: {role}")


def _normalized_option(value: Any) -> str:
    return " ".join(str(value).strip().casefold().split())


def select_option_matches(actual: Any, expected: Any) -> bool:
    """Match provider options, including Solarman Disable/Disabled variants."""
    actual_value = _normalized_option(actual)
    expected_value = _normalized_option(expected)
    if actual_value == expected_value:
        return True
    disabled_aliases = {"disable", "disabled"}
    return actual_value in disabled_aliases and expected_value in disabled_aliases


def resolve_select_option(options: Any, expected: str) -> str | None:
    """Return the exact provider spelling accepted by the HA select entity."""
    if not isinstance(options, (list, tuple)):
        return expected
    return next((str(option) for option in options if select_option_matches(option, expected)), None)


def state_matches_boolean(data: dict[str, Any], role: str, enabled: bool, state: str) -> bool:
    logical = boolean_state(data, role, state)
    return logical is enabled


def boolean_state(data: dict[str, Any], role: str, state: Any) -> bool | None:
    """Translate a physical provider option to its logical boolean meaning.

    Grid-source selects can expose more than the two values written by the
    manager.  In particular, Sunsynk and Custom distinguish generator-only and
    grid-plus-generator states.  Treating those as a simple equality with the
    preferred write option would make an unrelated TOU edit overwrite the raw
    provider value.  This reader therefore preserves all four meanings while
    writes continue to use the provider's configured true/false options.
    """
    if role != "grid":
        raise ValueError(f"Unknown provider boolean role: {role}")

    actual = _normalized_option(state)
    if not actual or actual in {"unknown", "unavailable", "none"}:
        return None

    provider = provider_key(data)
    if provider == PROVIDER_SUNSYNK:
        if actual in {_normalized_option("Allow Grid"), _normalized_option("Allow Grid & Gen")}:
            return True
        if actual in {_normalized_option("No Grid or Gen"), _normalized_option("Allow Gen")}:
            return False
    if provider == PROVIDER_CUSTOM:
        options = custom_grid_options(data)
        if actual in {
            _normalized_option(options["grid"]),
            _normalized_option(options["both"]),
        }:
            return True
        if actual in {
            _normalized_option(options["disabled"]),
            _normalized_option(options["generator"]),
        }:
            return False

    if select_option_matches(state, boolean_option(data, role, True)):
        return True
    if select_option_matches(state, boolean_option(data, role, False)):
        return False
    return None


def custom_grid_options(data: dict[str, Any]) -> dict[str, str]:
    """Return all four charging-source meanings for a custom select.

    The manager automatically writes only Disabled or Grid. Generator and Both
    are kept so an existing physical state can be diagnosed and restored
    without silently translating it to Grid.
    """
    return {
        "disabled": str(data.get(CONF_TOU_GRID_DISABLE_OPTION, "off")),
        "grid": str(data.get(CONF_TOU_GRID_ENABLE_OPTION, "on")),
        "generator": str(data.get(CONF_TOU_GRID_GENERATOR_OPTION, "Generator")),
        "both": str(data.get(CONF_TOU_GRID_BOTH_OPTION, "Both")),
    }


def operation_for_entity(entity_id: str | None, role: str = "") -> str:
    """Describe the exact HA operation used for a mapped entity."""
    domain = str(entity_id or "").split(".", 1)[0]
    if domain == "number":
        return "number.set_value"
    if domain == "select":
        return "select.select_option"
    if domain == "switch":
        return "switch.turn_on/off"
    if domain == "time":
        return "time.set_value"
    if domain == "sensor":
        return "odczyt"
    return "brak" if not role else f"brak ({role})"


def format_time_option(options: Any, value: str) -> str:
    """Select an available HH:MM or HH:MM:SS representation."""
    short = str(value)[:5]
    candidates = (short, f"{short}:00")
    if isinstance(options, (list, tuple)):
        for candidate in candidates:
            if candidate in options:
                return candidate
    return short


def provider_tou_field_capabilities(key: str) -> dict[str, dict[str, Any]]:
    """Return the physical per-slot TOU fields supported by a provider.

    The matrix lists only fields that are actually written to or read from a
    Deye Time Of Use slot entity.  Global inverter settings (sell power,
    charge/discharge/grid-charge currents) are reported separately.
    """
    item = profile(key)
    read_only = not item.native_tou
    physical_supported = item.native_tou
    return {
        "start": {
            "supported": physical_supported,
            "domains": item.tou_start_domains,
            "per_slot": True,
            "read_only": read_only,
        },
        "end": {
            "supported": physical_supported,
            "domains": item.tou_start_domains,
            "per_slot": True,
            "note": "stored as the start of the next slot",
            "read_only": read_only,
        },
        "soc": {
            "supported": physical_supported,
            "domains": ("number",),
            "per_slot": True,
            "read_only": read_only,
        },
        "grid_charge": {
            "supported": physical_supported,
            "domains": item.tou_grid_domains,
            "per_slot": True,
            "read_only": read_only,
        },
        "out_power": {
            "supported": False,
            "domains": (),
            "per_slot": False,
            "read_only": read_only,
        },
        "sell_power": {
            "supported": False,
            "domains": (),
            "per_slot": False,
            "note": "global number.deye_inverter_max_sell_power",
            "read_only": read_only,
        },
        "charge_current": {
            "supported": False,
            "domains": (),
            "per_slot": False,
            "note": "global charge_current_number",
            "read_only": read_only,
        },
        "discharge_current": {
            "supported": False,
            "domains": (),
            "per_slot": False,
            "note": "global discharge_current_number",
            "read_only": read_only,
        },
        "grid_charge_current": {
            "supported": False,
            "domains": (),
            "per_slot": False,
            "note": "global grid_charge_current_number",
            "read_only": read_only,
        },
    }

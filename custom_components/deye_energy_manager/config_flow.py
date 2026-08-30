from __future__ import annotations

from typing import Any, Iterable

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    ABSOLUTE_INVERTER_MAX_POWER_W,
    CONF_BATTERY_BMS_VOLTAGE_SENSOR,
    CONF_BATTERY_CURRENT_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
    CONF_BATTERY_SOC_SENSOR,
    CONF_BATTERY_SOH_SENSOR,
    CONF_BATTERY_TEMPERATURE_SENSOR,
    CONF_BUY_PRICE_TODAY_SENSOR,
    CONF_BUY_PRICE_TOMORROW_SENSOR,
    CONF_BUY_PRICE_CONTRACT,
    CONF_CHARGE_CURRENT_NUMBER,
    CONF_DAILY_BATTERY_CHARGE_SENSOR,
    CONF_DAILY_BATTERY_DISCHARGE_SENSOR,
    CONF_DAILY_ENERGY_BOUGHT_SENSOR,
    CONF_DAILY_ENERGY_SOLD_SENSOR,
    CONF_DAILY_LOAD_CONSUMPTION_SENSOR,
    CONF_DAILY_PV_PRODUCTION_SENSOR,
    CONF_DISCHARGE_CURRENT_NUMBER,
    CONF_GRID_CHARGE_CURRENT_NUMBER,
    CONF_GRID_L1_POWER_SENSOR,
    CONF_GRID_L1_VOLTAGE_SENSOR,
    CONF_GRID_L2_POWER_SENSOR,
    CONF_GRID_L2_VOLTAGE_SENSOR,
    CONF_GRID_L3_POWER_SENSOR,
    CONF_GRID_L3_VOLTAGE_SENSOR,
    CONF_GRID_POWER_SENSOR,
    CONF_INVERTER_AC_TEMPERATURE_SENSOR,
    CONF_INVERTER_DEVICE_ID,
    CONF_INVERTER_MAX_POWER_W,
    CONF_INVERTER_PROVIDER,
    CONF_LOAD_FREQUENCY_SENSOR,
    CONF_LOAD_L1_POWER_SENSOR,
    CONF_LOAD_L2_POWER_SENSOR,
    CONF_LOAD_L3_POWER_SENSOR,
    CONF_LOAD_POWER_SENSOR,
    CONF_MAPPING_MODE,
    CONF_MAX_SELL_POWER_NUMBER,
    CONF_PRICE_SENSOR,
    CONF_PV1_CURRENT_SENSOR,
    CONF_PV1_POWER_SENSOR,
    CONF_PV1_VOLTAGE_SENSOR,
    CONF_PV2_CURRENT_SENSOR,
    CONF_PV2_POWER_SENSOR,
    CONF_PV2_VOLTAGE_SENSOR,
    CONF_PV3_POWER_SENSOR,
    CONF_PV_POWER_SENSOR,
    CONF_SELL_PRICE_TOMORROW_SENSOR,
    CONF_SELL_PRICE_CONTRACT,
    CONF_SOLCAST_CURRENT_POWER_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_3_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_4_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_5_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_6_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_7_SENSOR,
    CONF_SOLCAST_FORECAST_TODAY_SENSOR,
    CONF_SOLCAST_FORECAST_TOMORROW_SENSOR,
    CONF_SOLCAST_PEAK_POWER_TODAY_SENSOR,
    CONF_SOLCAST_PEAK_TIME_TODAY_SENSOR,
    CONF_SOLCAST_REMAINING_TODAY_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_WORK_MODE_SELECT,
    CONF_WORK_MODE_AUX_ENTITY,
    CONF_WORK_MODE_SELL_OPTION,
    CONF_WORK_MODE_ZERO_LOAD_OPTION,
    CONF_WORK_MODE_ZERO_CT_OPTION,
    CONF_TOU_GRID_ENABLE_OPTION,
    CONF_TOU_GRID_DISABLE_OPTION,
    CONF_TOU_GRID_GENERATOR_OPTION,
    CONF_TOU_GRID_BOTH_OPTION,
    DEFAULT_BATTERY_BMS_VOLTAGE_SENSOR,
    DEFAULT_BATTERY_CURRENT_SENSOR,
    DEFAULT_BATTERY_POWER_SENSOR,
    DEFAULT_BATTERY_SOC,
    DEFAULT_BATTERY_SOH_SENSOR,
    DEFAULT_BATTERY_TEMPERATURE_SENSOR,
    DEFAULT_BUY_PRICE_TODAY_SENSOR,
    DEFAULT_BUY_PRICE_TOMORROW_SENSOR,
    DEFAULT_CHARGE_CURRENT,
    DEFAULT_DAILY_BATTERY_CHARGE_SENSOR,
    DEFAULT_DAILY_BATTERY_DISCHARGE_SENSOR,
    DEFAULT_DAILY_ENERGY_BOUGHT_SENSOR,
    DEFAULT_DAILY_ENERGY_SOLD_SENSOR,
    DEFAULT_DAILY_LOAD_CONSUMPTION_SENSOR,
    DEFAULT_DAILY_PV_PRODUCTION_SENSOR,
    DEFAULT_DISCHARGE_CURRENT,
    DEFAULT_GRID_CHARGE_CURRENT,
    DEFAULT_GRID_L1_POWER_SENSOR,
    DEFAULT_GRID_L1_VOLTAGE_SENSOR,
    DEFAULT_GRID_L2_POWER_SENSOR,
    DEFAULT_GRID_L2_VOLTAGE_SENSOR,
    DEFAULT_GRID_L3_POWER_SENSOR,
    DEFAULT_GRID_L3_VOLTAGE_SENSOR,
    DEFAULT_GRID_POWER_SENSOR,
    DEFAULT_INVERTER_AC_TEMPERATURE_SENSOR,
    DEFAULT_INVERTER_PROVIDER,
    DEFAULT_INVERTER_MAX_POWER_W,
    DEFAULT_LOAD_FREQUENCY_SENSOR,
    DEFAULT_LOAD_L1_POWER_SENSOR,
    DEFAULT_LOAD_L2_POWER_SENSOR,
    DEFAULT_LOAD_L3_POWER_SENSOR,
    DEFAULT_LOAD_POWER_SENSOR,
    DEFAULT_MAPPING_MODE,
    DEFAULT_MAX_SELL_POWER,
    DEFAULT_PV1_CURRENT_SENSOR,
    DEFAULT_PV1_POWER_SENSOR,
    DEFAULT_PV1_VOLTAGE_SENSOR,
    DEFAULT_PV2_CURRENT_SENSOR,
    DEFAULT_PV2_POWER_SENSOR,
    DEFAULT_PV2_VOLTAGE_SENSOR,
    DEFAULT_PV3_POWER_SENSOR,
    DEFAULT_PV_POWER_SENSOR,
    DEFAULT_PRICE_SENSOR,
    DEFAULT_SELL_PRICE_TOMORROW_SENSOR,
    DEFAULT_SOLCAST_CURRENT_POWER_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_3_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_4_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_5_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_6_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_7_SENSOR,
    DEFAULT_SOLCAST_FORECAST_TODAY_SENSOR,
    DEFAULT_SOLCAST_FORECAST_TOMORROW_SENSOR,
    DEFAULT_SOLCAST_PEAK_POWER_TODAY_SENSOR,
    DEFAULT_SOLCAST_PEAK_TIME_TODAY_SENSOR,
    DEFAULT_SOLCAST_REMAINING_TODAY_SENSOR,
    DEFAULT_WEATHER_ENTITY,
    DEFAULT_WORK_MODE_SELECT,
    INVERTER_PROVIDERS,
    PROVIDER_DEYE_ADDON,
    PROVIDER_LEWA_REKA,
    PROVIDER_SOLARMAN,
    PROVIDER_SUNSYNK,
    PROVIDER_CUSTOM,
    conf_tou_entity,
    DOMAIN,
)
from .price_sources import (
    detect_source_adapter,
    price_mapping_fingerprint,
    rebuild_price_contract,
    resolve_contract_schemas,
)
from .inverter_provider import (
    detect_entity_max_power_w,
    operation_for_entity,
    profile as provider_profile,
    select_option_matches,
)


ENTITY_SPECS: dict[str, tuple[str, str | tuple[str, ...], tuple[str, ...]]] = {
    CONF_WORK_MODE_SELECT: (DEFAULT_WORK_MODE_SELECT, "select", ("system work mode", "tryb pracy", "work mode")),
    CONF_MAX_SELL_POWER_NUMBER: (DEFAULT_MAX_SELL_POWER, "number", ("max sell power", "maksymalna moc sprzedaży")),
    CONF_DISCHARGE_CURRENT_NUMBER: (DEFAULT_DISCHARGE_CURRENT, "number", ("battery discharge current", "prąd rozładowania")),
    CONF_CHARGE_CURRENT_NUMBER: (DEFAULT_CHARGE_CURRENT, "number", ("battery charge current", "prąd ładowania")),
    CONF_GRID_CHARGE_CURRENT_NUMBER: (DEFAULT_GRID_CHARGE_CURRENT, "number", ("grid charge current", "ładowania z sieci")),
    CONF_BATTERY_SOC_SENSOR: (DEFAULT_BATTERY_SOC, "sensor", ("battery", "soc", "stan baterii")),
    CONF_GRID_POWER_SENSOR: (DEFAULT_GRID_POWER_SENSOR, "sensor", ("grid power", "moc sieci")),
    CONF_PV_POWER_SENSOR: (DEFAULT_PV_POWER_SENSOR, "sensor", ("pv power", "moc pv")),
    CONF_LOAD_POWER_SENSOR: (DEFAULT_LOAD_POWER_SENSOR, "sensor", ("load power", "moc domu", "zużycie")),
    CONF_BATTERY_POWER_SENSOR: (DEFAULT_BATTERY_POWER_SENSOR, "sensor", ("battery power", "moc baterii")),
    CONF_DAILY_PV_PRODUCTION_SENSOR: (DEFAULT_DAILY_PV_PRODUCTION_SENSOR, "sensor", ("daily pv production", "produkcja pv dzisiaj")),
    CONF_PRICE_SENSOR: (DEFAULT_PRICE_SENSOR, "sensor", ("cena sprzedaży", "sell price", "rce")),
    CONF_SELL_PRICE_TOMORROW_SENSOR: (DEFAULT_SELL_PRICE_TOMORROW_SENSOR, "sensor", ("cena sprzedaży jutro", "sell price tomorrow")),
    CONF_BUY_PRICE_TODAY_SENSOR: (DEFAULT_BUY_PRICE_TODAY_SENSOR, "sensor", ("cena zakupu", "buy price today")),
    CONF_BUY_PRICE_TOMORROW_SENSOR: (DEFAULT_BUY_PRICE_TOMORROW_SENSOR, "sensor", ("cena zakupu jutro", "buy price tomorrow")),
    CONF_SOLCAST_CURRENT_POWER_SENSOR: (DEFAULT_SOLCAST_CURRENT_POWER_SENSOR, "sensor", ("solcast", "aktualna moc")),
    CONF_SOLCAST_FORECAST_TODAY_SENSOR: (DEFAULT_SOLCAST_FORECAST_TODAY_SENSOR, "sensor", ("solcast", "prognoza na dzisiaj")),
    CONF_SOLCAST_FORECAST_TOMORROW_SENSOR: (DEFAULT_SOLCAST_FORECAST_TOMORROW_SENSOR, "sensor", ("solcast", "prognoza na jutro")),
    CONF_SOLCAST_FORECAST_DAY_3_SENSOR: (DEFAULT_SOLCAST_FORECAST_DAY_3_SENSOR, "sensor", ("solcast", "dzień 3", "day 3")),
    CONF_SOLCAST_FORECAST_DAY_4_SENSOR: (DEFAULT_SOLCAST_FORECAST_DAY_4_SENSOR, "sensor", ("solcast", "dzień 4", "day 4")),
    CONF_SOLCAST_FORECAST_DAY_5_SENSOR: (DEFAULT_SOLCAST_FORECAST_DAY_5_SENSOR, "sensor", ("solcast", "dzień 5", "day 5")),
    CONF_SOLCAST_FORECAST_DAY_6_SENSOR: (DEFAULT_SOLCAST_FORECAST_DAY_6_SENSOR, "sensor", ("solcast", "dzień 6", "day 6")),
    CONF_SOLCAST_FORECAST_DAY_7_SENSOR: (DEFAULT_SOLCAST_FORECAST_DAY_7_SENSOR, "sensor", ("solcast", "dzień 7", "day 7")),
    CONF_SOLCAST_REMAINING_TODAY_SENSOR: (DEFAULT_SOLCAST_REMAINING_TODAY_SENSOR, "sensor", ("solcast", "pozostała prognoza")),
    CONF_SOLCAST_PEAK_POWER_TODAY_SENSOR: (DEFAULT_SOLCAST_PEAK_POWER_TODAY_SENSOR, "sensor", ("solcast", "szczytowa moc")),
    CONF_SOLCAST_PEAK_TIME_TODAY_SENSOR: (DEFAULT_SOLCAST_PEAK_TIME_TODAY_SENSOR, "sensor", ("solcast", "czas szczytowej")),
    CONF_WEATHER_ENTITY: (DEFAULT_WEATHER_ENTITY, "weather", ("forecast home", "prognoza domu", "weather")),
    # Status panel detail sources
    CONF_PV1_POWER_SENSOR: (DEFAULT_PV1_POWER_SENSOR, "sensor", ("pv1 power", "moc pv1")),
    CONF_PV1_VOLTAGE_SENSOR: (DEFAULT_PV1_VOLTAGE_SENSOR, "sensor", ("pv1 voltage", "napięcie pv1")),
    CONF_PV1_CURRENT_SENSOR: (DEFAULT_PV1_CURRENT_SENSOR, "sensor", ("pv1 current", "prąd pv1")),
    CONF_PV2_POWER_SENSOR: (DEFAULT_PV2_POWER_SENSOR, "sensor", ("pv2 power", "moc pv2")),
    CONF_PV2_VOLTAGE_SENSOR: (DEFAULT_PV2_VOLTAGE_SENSOR, "sensor", ("pv2 voltage", "napięcie pv2")),
    CONF_PV2_CURRENT_SENSOR: (DEFAULT_PV2_CURRENT_SENSOR, "sensor", ("pv2 current", "prąd pv2")),
    CONF_PV3_POWER_SENSOR: (DEFAULT_PV3_POWER_SENSOR, "sensor", ("pv3 power", "moc pv3")),
    CONF_BATTERY_BMS_VOLTAGE_SENSOR: (DEFAULT_BATTERY_BMS_VOLTAGE_SENSOR, "sensor", ("battery bms voltage", "napięcie baterii bms")),
    CONF_BATTERY_CURRENT_SENSOR: (DEFAULT_BATTERY_CURRENT_SENSOR, "sensor", ("battery current", "prąd baterii")),
    CONF_BATTERY_TEMPERATURE_SENSOR: (DEFAULT_BATTERY_TEMPERATURE_SENSOR, "sensor", ("battery temperature", "temperatura baterii")),
    CONF_BATTERY_SOH_SENSOR: (DEFAULT_BATTERY_SOH_SENSOR, "sensor", ("battery soh", "stan zdrowia baterii", "state of health")),
    CONF_DAILY_BATTERY_CHARGE_SENSOR: (DEFAULT_DAILY_BATTERY_CHARGE_SENSOR, "sensor", ("daily battery charge", "naładowano dzisiaj")),
    CONF_DAILY_BATTERY_DISCHARGE_SENSOR: (DEFAULT_DAILY_BATTERY_DISCHARGE_SENSOR, "sensor", ("daily battery discharge", "rozładowano dzisiaj")),
    CONF_DAILY_ENERGY_BOUGHT_SENSOR: (DEFAULT_DAILY_ENERGY_BOUGHT_SENSOR, "sensor", ("daily energy bought", "kupiono dzisiaj")),
    CONF_DAILY_ENERGY_SOLD_SENSOR: (DEFAULT_DAILY_ENERGY_SOLD_SENSOR, "sensor", ("daily energy sold", "sprzedano dzisiaj")),
    CONF_GRID_L1_POWER_SENSOR: (DEFAULT_GRID_L1_POWER_SENSOR, "sensor", ("grid l1 power", "moc l1")),
    CONF_GRID_L1_VOLTAGE_SENSOR: (DEFAULT_GRID_L1_VOLTAGE_SENSOR, "sensor", ("grid l1 voltage", "napięcie l1")),
    CONF_GRID_L2_POWER_SENSOR: (DEFAULT_GRID_L2_POWER_SENSOR, "sensor", ("grid l2 power", "moc l2")),
    CONF_GRID_L2_VOLTAGE_SENSOR: (DEFAULT_GRID_L2_VOLTAGE_SENSOR, "sensor", ("grid l2 voltage", "napięcie l2")),
    CONF_GRID_L3_POWER_SENSOR: (DEFAULT_GRID_L3_POWER_SENSOR, "sensor", ("grid l3 power", "moc l3")),
    CONF_GRID_L3_VOLTAGE_SENSOR: (DEFAULT_GRID_L3_VOLTAGE_SENSOR, "sensor", ("grid l3 voltage", "napięcie l3")),
    CONF_LOAD_FREQUENCY_SENSOR: (DEFAULT_LOAD_FREQUENCY_SENSOR, "sensor", ("load frequency", "częstotliwość")),
    CONF_DAILY_LOAD_CONSUMPTION_SENSOR: (DEFAULT_DAILY_LOAD_CONSUMPTION_SENSOR, "sensor", ("daily load consumption", "zużycie domu dzisiaj")),
    CONF_LOAD_L1_POWER_SENSOR: (DEFAULT_LOAD_L1_POWER_SENSOR, "sensor", ("load l1 power", "moc obciążenia l1")),
    CONF_LOAD_L2_POWER_SENSOR: (DEFAULT_LOAD_L2_POWER_SENSOR, "sensor", ("load l2 power", "moc obciążenia l2")),
    CONF_LOAD_L3_POWER_SENSOR: (DEFAULT_LOAD_L3_POWER_SENSOR, "sensor", ("load l3 power", "moc obciążenia l3")),
    CONF_INVERTER_AC_TEMPERATURE_SENSOR: (DEFAULT_INVERTER_AC_TEMPERATURE_SENSOR, "sensor", ("ac temperature", "temperatura falownika")),
}

TOU_FIELDS = tuple(
    conf_tou_entity(index, kind)
    for index in range(1, 7)
    for kind in ("start", "soc", "grid")
)

ENTITY_SPECS[CONF_WORK_MODE_AUX_ENTITY] = ("", "switch", ("solar export", "export solar"))
for _index in range(1, 7):
    ENTITY_SPECS[conf_tou_entity(_index, "start")] = (
        "",
        ("time", "select"),
        (f"time of use {_index} start", f"program {_index} time", f"prog{_index} time"),
    )
    ENTITY_SPECS[conf_tou_entity(_index, "soc")] = (
        "",
        "number",
        (f"time of use {_index} soc", f"program {_index} soc", f"prog{_index} capacity"),
    )
    ENTITY_SPECS[conf_tou_entity(_index, "grid")] = (
        "",
        ("switch", "select"),
        (f"time of use {_index} grid charge", f"program {_index} charging", f"prog{_index} charge"),
    )

INVERTER_FIELDS = (
    CONF_WORK_MODE_SELECT, CONF_MAX_SELL_POWER_NUMBER, CONF_DISCHARGE_CURRENT_NUMBER,
    CONF_CHARGE_CURRENT_NUMBER, CONF_GRID_CHARGE_CURRENT_NUMBER, CONF_BATTERY_SOC_SENSOR,
    CONF_GRID_POWER_SENSOR, CONF_PV_POWER_SENSOR, CONF_LOAD_POWER_SENSOR,
    CONF_BATTERY_POWER_SENSOR, CONF_DAILY_PV_PRODUCTION_SENSOR,
)
PRICE_FIELDS = (CONF_PRICE_SENSOR, CONF_SELL_PRICE_TOMORROW_SENSOR, CONF_BUY_PRICE_TODAY_SENSOR, CONF_BUY_PRICE_TOMORROW_SENSOR)

ENERGY_DETAIL_FIELDS = (
    CONF_PV1_POWER_SENSOR, CONF_PV1_VOLTAGE_SENSOR, CONF_PV1_CURRENT_SENSOR,
    CONF_PV2_POWER_SENSOR, CONF_PV2_VOLTAGE_SENSOR, CONF_PV2_CURRENT_SENSOR,
    CONF_PV3_POWER_SENSOR,
    CONF_BATTERY_BMS_VOLTAGE_SENSOR, CONF_BATTERY_CURRENT_SENSOR, CONF_BATTERY_TEMPERATURE_SENSOR,
    CONF_BATTERY_SOH_SENSOR,
    CONF_DAILY_BATTERY_CHARGE_SENSOR, CONF_DAILY_BATTERY_DISCHARGE_SENSOR,
    CONF_DAILY_ENERGY_BOUGHT_SENSOR, CONF_DAILY_ENERGY_SOLD_SENSOR,
    CONF_DAILY_LOAD_CONSUMPTION_SENSOR,
    CONF_GRID_L1_POWER_SENSOR, CONF_GRID_L2_POWER_SENSOR, CONF_GRID_L3_POWER_SENSOR,
    CONF_GRID_L1_VOLTAGE_SENSOR, CONF_GRID_L2_VOLTAGE_SENSOR, CONF_GRID_L3_VOLTAGE_SENSOR,
    CONF_LOAD_FREQUENCY_SENSOR,
    CONF_LOAD_L1_POWER_SENSOR, CONF_LOAD_L2_POWER_SENSOR, CONF_LOAD_L3_POWER_SENSOR,
    CONF_INVERTER_AC_TEMPERATURE_SENSOR,
)

SOLCAST_FIELDS = (
    CONF_SOLCAST_CURRENT_POWER_SENSOR, CONF_SOLCAST_FORECAST_TODAY_SENSOR,
    CONF_SOLCAST_FORECAST_TOMORROW_SENSOR, CONF_SOLCAST_FORECAST_DAY_3_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_4_SENSOR, CONF_SOLCAST_FORECAST_DAY_5_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_6_SENSOR, CONF_SOLCAST_FORECAST_DAY_7_SENSOR,
    CONF_SOLCAST_REMAINING_TODAY_SENSOR, CONF_SOLCAST_PEAK_POWER_TODAY_SENSOR,
    CONF_SOLCAST_PEAK_TIME_TODAY_SENSOR,
)
REQUIRED_FIELDS = {
    CONF_WORK_MODE_SELECT,
    CONF_MAX_SELL_POWER_NUMBER,
    CONF_DISCHARGE_CURRENT_NUMBER,
    CONF_CHARGE_CURRENT_NUMBER,
    CONF_GRID_CHARGE_CURRENT_NUMBER,
    CONF_BATTERY_SOC_SENSOR,
}

# Keys from older versions that referred to a global Time Of Use switch. They are
# tolerated at runtime but removed when the user consciously resaves Options Flow.
_REMOVED_GLOBAL_TOU_KEYS = frozenset(("tou_enable_entity", "tou_enable_option", "tou_disable_option"))

PROVIDER_LABELS = {
    PROVIDER_LEWA_REKA: "ESPHome Deye Inverter — Lewa-Reka",
    PROVIDER_SOLARMAN: "Solarman",
    PROVIDER_SUNSYNK: "Sunsynk",
    PROVIDER_DEYE_ADDON: "Deye Inverter MQTT",
    PROVIDER_CUSTOM: "Mapowanie niestandardowe",
}

CUSTOM_OPTION_FIELDS = (
    CONF_WORK_MODE_SELL_OPTION,
    CONF_WORK_MODE_ZERO_LOAD_OPTION,
    CONF_WORK_MODE_ZERO_CT_OPTION,
    CONF_TOU_GRID_ENABLE_OPTION,
    CONF_TOU_GRID_DISABLE_OPTION,
    CONF_TOU_GRID_GENERATOR_OPTION,
    CONF_TOU_GRID_BOTH_OPTION,
)

PROVIDER_ENTITY_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    PROVIDER_SOLARMAN: {
        CONF_WORK_MODE_SELECT: ("work mode",),
        CONF_MAX_SELL_POWER_NUMBER: ("export surplus power", "max sell power"),
        CONF_DISCHARGE_CURRENT_NUMBER: ("battery max discharging current",),
        CONF_CHARGE_CURRENT_NUMBER: ("battery max charging current",),
        CONF_GRID_CHARGE_CURRENT_NUMBER: ("battery grid charging current",),
        CONF_BATTERY_SOC_SENSOR: ("battery soc",),
        CONF_GRID_POWER_SENSOR: ("total grid power", "grid total power", "external ct power"),
        CONF_GRID_L1_POWER_SENSOR: ("grid l1 power", "grid phase 1 power", "grid power l1"),
        CONF_GRID_L2_POWER_SENSOR: ("grid l2 power", "grid phase 2 power", "grid power l2"),
        CONF_GRID_L3_POWER_SENSOR: ("grid l3 power", "grid phase 3 power", "grid power l3"),
        CONF_PV_POWER_SENSOR: ("total pv power", "pv total power", "dc power"),
        CONF_LOAD_POWER_SENSOR: ("total load power", "load total power", "load power"),
        CONF_BATTERY_POWER_SENSOR: ("battery power",),
        CONF_DAILY_ENERGY_BOUGHT_SENSOR: ("daily energy bought", "daily grid import", "daily energy from grid"),
        CONF_DAILY_ENERGY_SOLD_SENSOR: ("daily energy sold", "daily grid export", "daily energy to grid"),
        CONF_DAILY_PV_PRODUCTION_SENSOR: ("daily production", "daily pv production", "daily solar production"),
        CONF_DAILY_LOAD_CONSUMPTION_SENSOR: ("daily load consumption", "daily load energy"),
    },
    PROVIDER_SUNSYNK: {
        CONF_WORK_MODE_SELECT: ("load limit",),
        CONF_WORK_MODE_AUX_ENTITY: ("solar export",),
        CONF_MAX_SELL_POWER_NUMBER: ("max sell power",),
        CONF_DISCHARGE_CURRENT_NUMBER: ("battery max discharge current",),
        CONF_CHARGE_CURRENT_NUMBER: ("battery max charge current",),
        CONF_GRID_CHARGE_CURRENT_NUMBER: ("grid charge battery current",),
        CONF_BATTERY_SOC_SENSOR: ("battery soc",),
        CONF_GRID_POWER_SENSOR: ("grid power", "grid total power"),
        CONF_GRID_L1_POWER_SENSOR: ("grid l1 power", "grid phase 1 power"),
        CONF_GRID_L2_POWER_SENSOR: ("grid l2 power", "grid phase 2 power"),
        CONF_GRID_L3_POWER_SENSOR: ("grid l3 power", "grid phase 3 power"),
        CONF_DAILY_ENERGY_BOUGHT_SENSOR: ("daily grid import", "daily energy bought"),
        CONF_DAILY_ENERGY_SOLD_SENSOR: ("daily grid export", "daily energy sold"),
    },
    PROVIDER_DEYE_ADDON: {
        CONF_BATTERY_SOC_SENSOR: ("battery soc", "battery state of charge"),
        CONF_GRID_POWER_SENSOR: ("grid power", "external ct power"),
        CONF_PV_POWER_SENSOR: ("pv power", "dc power"),
        CONF_LOAD_POWER_SENSOR: ("load power", "load total power"),
        CONF_BATTERY_POWER_SENSOR: ("battery power",),
    },
}


def select_with_labels(options: list[tuple[str, str]]):
    return selector.SelectSelector(selector.SelectSelectorConfig(
        options=[{"value": value, "label": label} for value, label in options],
        mode="dropdown",
    ))


def _mapping_semantics_match(key: str | None, state: Any) -> bool:
    """Reject only metadata that is impossible for an automatic mapping.

    Missing metadata remains acceptable because many third-party integrations do
    not expose a device class or unit.  Explicit choices made by the user are not
    passed through this heuristic.
    """
    if not key:
        return True
    attributes = getattr(state, "attributes", {}) or {}
    device_class = str(attributes.get("device_class") or "").strip().lower()
    unit = str(attributes.get("unit_of_measurement") or "").strip().lower().replace(" ", "")

    incompatible_classes = {
        "signal_strength", "data_rate", "duration", "timestamp",
    }
    if device_class in incompatible_classes:
        return False

    if key in PRICE_FIELDS:
        if device_class in {
            "power", "energy", "voltage", "current", "battery",
            "temperature", "frequency", "signal_strength",
        }:
            return False
        return not unit or any(token in unit for token in ("/kwh", "/mwh", "pln", "eur", "usd", "gbp", "zł"))

    semantic_units: tuple[set[str], ...] = ()
    if "power" in key:
        semantic_units = ({"w", "kw", "mw"},)
        if device_class and device_class != "power":
            return False
    elif "voltage" in key:
        semantic_units = ({"v", "mv", "kv"},)
        if device_class and device_class != "voltage":
            return False
    elif "current" in key:
        semantic_units = ({"a", "ma"},)
        if device_class and device_class != "current":
            return False
    elif "temperature" in key:
        semantic_units = ({"°c", "c", "°f", "f"},)
        if device_class and device_class != "temperature":
            return False
    elif "frequency" in key:
        semantic_units = ({"hz", "khz"},)
        if device_class and device_class != "frequency":
            return False
    elif key in {CONF_BATTERY_SOC_SENSOR, CONF_BATTERY_SOH_SENSOR}:
        semantic_units = ({"%"},)
        if device_class and device_class != "battery":
            return False
    elif key.startswith("daily_"):
        semantic_units = ({"wh", "kwh", "mwh"},)
        if device_class and device_class != "energy":
            return False

    return not semantic_units or not unit or unit in semantic_units[0]


def discover_entity(
    states: Iterable[Any],
    domain: str | tuple[str, ...],
    default: str,
    tokens: tuple[str, ...],
    *,
    semantic_key: str | None = None,
) -> str:
    domains = (domain,) if isinstance(domain, str) else domain
    candidates = [
        state for state in states
        if any(str(getattr(state, "entity_id", "")).startswith(f"{item}.") for item in domains)
    ]
    if any(
        state.entity_id == default and _mapping_semantics_match(semantic_key, state)
        for state in candidates
    ):
        return default
    best_score = 0
    best: list[str] = []
    for state in candidates:
        if not _mapping_semantics_match(semantic_key, state):
            continue
        haystack = " ".join((state.entity_id, str(getattr(state, "attributes", {}).get("friendly_name", "")))).lower()
        score = sum(3 if token in haystack else 0 for token in tokens)
        # The vendor name is only a tie-breaker.  It must never be sufficient
        # to map an unrelated device-local sensor (for example Wi-Fi RSSI).
        if score <= 0:
            continue
        score += 1 if "deye" in haystack else 0
        if score > best_score:
            best_score = score
            best = [state.entity_id]
        elif score == best_score and score > 0:
            best.append(state.entity_id)
    # An ambiguous automatic match is less safe than leaving the field empty.
    return best[0] if best_score > 0 and len(best) == 1 else default


class MappingWizardMixin:
    _values: dict[str, Any]
    _is_options = False

    def _prepare_values(self) -> None:
        if hasattr(self, "_values"):
            return
        current = {**self.config_entry.data, **self.config_entry.options} if self._is_options else {}
        # 5G.4K.3A could persist a cleared selector only inside its contract.
        # Hydrate the central mapping key presence-aware so the Options form
        # shows the saved empty value instead of a legacy/provider suggestion.
        for contract_key, today_key, tomorrow_key in (
            (CONF_BUY_PRICE_CONTRACT, CONF_BUY_PRICE_TODAY_SENSOR, CONF_BUY_PRICE_TOMORROW_SENSOR),
            (CONF_SELL_PRICE_CONTRACT, CONF_PRICE_SENSOR, CONF_SELL_PRICE_TOMORROW_SENSOR),
        ):
            contract = current.get(contract_key)
            if not isinstance(contract, dict):
                continue
            if today_key not in current and "today_entity" in contract:
                current[today_key] = str(contract.get("today_entity") or "")
            if tomorrow_key not in current and "tomorrow_entity" in contract:
                current[tomorrow_key] = str(contract.get("tomorrow_entity") or "")
        self._values = current
        self._original_provider = current.get(CONF_INVERTER_PROVIDER)
        self._original_device_id = current.get(CONF_INVERTER_DEVICE_ID)

    def _clear_inverter_mapping_if_source_changed(self) -> None:
        """Discard only temporary wizard suggestions when provider/device changed."""
        provider_changed = (
            self._original_provider is not None
            and self._values.get(CONF_INVERTER_PROVIDER) != self._original_provider
        )
        device_changed = (
            self._original_device_id is not None
            and self._values.get(CONF_INVERTER_DEVICE_ID) != self._original_device_id
        )
        if provider_changed or device_changed:
            for key in (*INVERTER_FIELDS, *TOU_FIELDS, *ENERGY_DETAIL_FIELDS):
                self._values.pop(key, None)

    def _device_entity_ids(self) -> set[str] | None:
        """Return entities belonging to the selected inverter device."""
        device_id = str(self._values.get(CONF_INVERTER_DEVICE_ID) or "").strip()
        if not device_id:
            return None
        registry = er.async_get(self.hass)
        return {
            entry.entity_id
            for entry in registry.entities.values()
            if entry.device_id == device_id
        }

    def _discovery_states(self, domain: str | tuple[str, ...]) -> list[Any]:
        domains = domain if isinstance(domain, tuple) else (domain,)
        states = [
            state
            for item in domains
            for state in self.hass.states.async_all(item)
        ]
        allowed = self._device_entity_ids()
        return states if allowed is None else [state for state in states if state.entity_id in allowed]

    def _mapping_device_issues(self) -> list[str]:
        device_id = str(self._values.get(CONF_INVERTER_DEVICE_ID) or "").strip()
        if not device_id:
            return []
        registry = er.async_get(self.hass)
        issues = []
        for key in (*INVERTER_FIELDS, *TOU_FIELDS, *ENERGY_DETAIL_FIELDS):
            entity_id = str(self._values.get(key) or "").strip()
            if not entity_id:
                continue
            entry = registry.entities.get(entity_id)
            # Sensors not registered below a HA device (device_id=None) are
            # allowed.  Only an explicit assignment to a different device is
            # a hard safety conflict.  Prices, Solcast and weather are not
            # checked here because they intentionally belong elsewhere.
            if entry is not None and entry.device_id and entry.device_id != device_id:
                issues.append(f"{key}={entity_id}")
        return issues

    def _entity_default(self, key: str) -> str:
        default, domain, tokens = ENTITY_SPECS[key]
        current = self._values.get(key)
        if key in PRICE_FIELDS and key in self._values:
            # An explicit empty selector is a persisted user decision, not a
            # request to rediscover or restore the provider default.
            return str(current or "")
        # A valid saved choice always wins. Automatic suggestions are allowed
        # to fill only fields that are still missing.
        if current:
            return str(current)
        provider = str(self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER))
        tokens = PROVIDER_ENTITY_TOKENS.get(provider, {}).get(key, tokens)
        if key.startswith("tou_") and provider == PROVIDER_SOLARMAN:
            index = key.split("_", 2)[1]
            kind = key.rsplit("_", 2)[-2]
            tokens = {
                "start": (f"program {index} time",),
                "soc": (f"program {index} soc",),
                "grid": (f"program {index} charging",),
            }.get(kind, tokens)
        if key.startswith("tou_") and provider == PROVIDER_SUNSYNK:
            index = key.split("_", 2)[1]
            kind = key.rsplit("_", 2)[-2]
            tokens = {
                "start": (f"prog{index} time", f"prog {index} time"),
                "soc": (f"prog{index} capacity", f"prog {index} capacity"),
                "grid": (f"prog{index} charge", f"prog {index} charge"),
            }.get(kind, tokens)
        if provider != PROVIDER_LEWA_REKA and default.startswith(("select.deye_inverter_", "number.deye_inverter_", "sensor.deye_inverter_", "switch.deye_inverter_", "time.deye_inverter_")):
            default = ""
        if self._values.get(CONF_MAPPING_MODE, DEFAULT_MAPPING_MODE) == "automatic":
            candidate = discover_entity(
                self._discovery_states(domain),
                domain,
                default,
                tokens,
                semantic_key=key,
            )
            if self.hass.states.get(candidate) is not None:
                return candidate
        return str(current or default)

    def _entity_schema(self, fields: tuple[str, ...]) -> vol.Schema:
        schema: dict[Any, Any] = {}
        for key in fields:
            _default, domain, _tokens = ENTITY_SPECS[key]
            entity_domain = list(domain) if isinstance(domain, tuple) else domain
            # Every entity selector is optional at mapping time.  REQUIRED_FIELDS
            # describes the controls needed for full operation, not fields that
            # must block saving a read-only or otherwise partial configuration.
            default = self._entity_default(key)
            if key in PRICE_FIELDS:
                # HA optional entity selectors can omit a cleared field.  A
                # voluptuous default would silently put the old entity back
                # before async_step_prices can observe that omission.  A
                # suggested value is presentation-only and preserves presence.
                marker = vol.Optional(
                    key,
                    description={"suggested_value": default},
                )
            else:
                marker = vol.Optional(key, default=default) if default else vol.Optional(key)
            schema[marker] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=entity_domain)
            )
        return vol.Schema(schema)

    def _price_binding(self, entity_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        registry = er.async_get(self.hass)
        entry = registry.entities.get(entity_id) if registry is not None else None
        binding: dict[str, Any] = {"entity_id": entity_id}
        metadata: dict[str, Any] = {"platform": None, "config_entry_domain": None}
        if entry is None:
            return binding, metadata
        binding.update({
            "registry_entry_id": str(getattr(entry, "id", "") or ""),
            "platform": str(getattr(entry, "platform", "") or ""),
            "config_entry_id": str(getattr(entry, "config_entry_id", "") or ""),
            "unique_id": str(getattr(entry, "unique_id", "") or ""),
            "device_id": str(getattr(entry, "device_id", "") or ""),
        })
        metadata["platform"] = binding["platform"] or None
        source_entry = (
            self.hass.config_entries.async_get_entry(binding["config_entry_id"])
            if binding["config_entry_id"] and hasattr(self.hass.config_entries, "async_get_entry")
            else None
        )
        metadata["config_entry_domain"] = str(getattr(source_entry, "domain", "") or "") or None
        return binding, metadata

    def _resolve_price_mapping_contracts(self) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        contracts: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        definitions = {
            "buy": (CONF_BUY_PRICE_CONTRACT, CONF_BUY_PRICE_TODAY_SENSOR, CONF_BUY_PRICE_TOMORROW_SENSOR),
            "sell": (CONF_SELL_PRICE_CONTRACT, CONF_PRICE_SENSOR, CONF_SELL_PRICE_TOMORROW_SENSOR),
        }
        for direction, (contract_key, today_key, tomorrow_key) in definitions.items():
            existing = self._values.get(contract_key) if isinstance(self._values.get(contract_key), dict) else {}
            today_entity = str(
                (self._values.get(today_key) or "")
                if today_key in self._values
                else (existing.get("today_entity") or "")
            )
            tomorrow_entity = str(
                (self._values.get(tomorrow_key) or "")
                if tomorrow_key in self._values
                else (existing.get("tomorrow_entity") or "")
            )
            bindings: dict[str, dict[str, Any]] = {}
            metadata_by_day: dict[str, dict[str, Any]] = {}
            identity_matches: dict[str, bool] = {}
            for day_name, entity_id in (("today", today_entity), ("tomorrow", tomorrow_entity)):
                captured, metadata = self._price_binding(entity_id) if entity_id else ({}, {})
                saved_binding = existing.get(f"{day_name}_binding")
                saved_binding = dict(saved_binding) if isinstance(saved_binding, dict) else {}
                saved_entity = str(existing.get(f"{day_name}_entity") or saved_binding.get("entity_id") or "")
                same_identity = bool(
                    saved_entity == entity_id
                    or (
                        entity_id
                        and saved_binding.get("registry_entry_id")
                        and captured.get("registry_entry_id")
                        and saved_binding.get("registry_entry_id") == captured.get("registry_entry_id")
                    )
                )
                identity_matches[day_name] = same_identity
                bindings[day_name] = saved_binding if same_identity and saved_binding else captured
                metadata_by_day[day_name] = metadata
            reusable = dict(existing)
            if all(identity_matches.values()):
                reusable.update({
                    "today_entity": today_entity,
                    "tomorrow_entity": tomorrow_entity,
                    "mapping_fingerprint": price_mapping_fingerprint(today_entity, tomorrow_entity),
                })
            adapters: dict[str, str] = {}
            for day_name, entity_id in (("today", today_entity), ("tomorrow", tomorrow_entity)):
                metadata = metadata_by_day[day_name]
                detected = detect_source_adapter(
                    entity_id,
                    platform=metadata.get("platform"),
                    config_entry_domain=metadata.get("config_entry_domain"),
                )
                saved_adapter = str(
                    existing.get(f"resolved_adapter_{day_name}")
                    or existing.get("source_adapter")
                    or ""
                )
                adapters[day_name] = (
                    saved_adapter
                    if detected == "generic"
                    and identity_matches[day_name]
                    and saved_adapter in {"pstryk", "rce_pse", "generic", "custom"}
                    else detected
                )
            contract = rebuild_price_contract(
                reusable,
                direction,
                today_entity,
                tomorrow_entity,
                adapters["today"],
                adapters["tomorrow"],
            )
            contract.update({
                "today_entity": today_entity,
                "tomorrow_entity": tomorrow_entity,
                "resolved_today_entity": today_entity,
                "resolved_tomorrow_entity": tomorrow_entity,
                "today_binding": bindings["today"],
                "tomorrow_binding": bindings["tomorrow"],
                "stable_identity_today_status": "unmapped" if not today_entity else "bound" if bindings["today"].get("registry_entry_id") else "entity_id_only",
                "stable_identity_tomorrow_status": "unmapped" if not tomorrow_entity else "bound" if bindings["tomorrow"].get("registry_entry_id") else "entity_id_only",
                "stable_identity_today_reason": "user_unmapped" if not today_entity else "",
                "stable_identity_tomorrow_reason": "user_unmapped" if not tomorrow_entity else "",
            })
            if not today_entity:
                contract["today_binding"] = {}
                contract["resolved_schema_today"] = {}
            if not tomorrow_entity:
                contract["tomorrow_binding"] = {}
                contract["resolved_schema_tomorrow"] = {}
            today_state = self.hass.states.get(today_entity) if today_entity else None
            tomorrow_state = self.hass.states.get(tomorrow_entity) if tomorrow_entity else None
            contract, diagnostics = resolve_contract_schemas(contract, today_state, tomorrow_state)
            if today_entity and today_state is None:
                errors[today_key] = "mapped_entity_missing"
            elif today_state is not None and diagnostics["today"]["status"] == "unsupported_price_schema":
                errors[today_key] = "unsupported_price_schema"
            if tomorrow_entity and tomorrow_state is None:
                errors[tomorrow_key] = "mapped_entity_missing"
            elif tomorrow_state is not None and diagnostics["tomorrow"]["status"] == "unsupported_price_schema":
                errors[tomorrow_key] = "unsupported_price_schema"
            contracts[direction] = contract
        return contracts, errors

    def _required_fields(self) -> set[str]:
        provider = str(self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER))
        if provider == PROVIDER_DEYE_ADDON:
            return set()
        if provider == PROVIDER_CUSTOM:
            return set()
        return set(REQUIRED_FIELDS)

    def _missing_required(self) -> list[str]:
        missing = []
        for key in self._required_fields():
            entity_id = self._values.get(key)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is None or state.state in ("unknown", "unavailable"):
                missing.append(key)
        return missing

    def _missing_provider_controls(self) -> list[str]:
        """Validate extra controls for providers that actually expose native TOU."""
        provider = str(self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER))
        if not provider_profile(provider).native_tou:
            return []
        # A custom mapping may intentionally expose only readings or only one
        # safe control group.  Solarman and Sunsynk presets, on the other hand,
        # promise complete native TOU and therefore validate all six ranges.
        required = [] if provider == PROVIDER_CUSTOM else list(TOU_FIELDS)
        if provider == PROVIDER_SUNSYNK:
            required.append(CONF_WORK_MODE_AUX_ENTITY)
        missing = []
        for key in required:
            entity_id = self._values.get(key)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is None or state.state in ("unknown", "unavailable"):
                missing.append(key)
        if provider == PROVIDER_CUSTOM:
            custom_required = {
                CONF_WORK_MODE_SELL_OPTION,
                CONF_WORK_MODE_ZERO_LOAD_OPTION,
                CONF_WORK_MODE_ZERO_CT_OPTION,
            } if self._values.get(CONF_WORK_MODE_SELECT) else set()
            if any(str(self._values.get(conf_tou_entity(idx, "grid"), "")).startswith("select.") for idx in range(1, 7)):
                custom_required.update((
                    CONF_TOU_GRID_ENABLE_OPTION,
                    CONF_TOU_GRID_DISABLE_OPTION,
                    CONF_TOU_GRID_GENERATOR_OPTION,
                    CONF_TOU_GRID_BOTH_OPTION,
                ))
            missing.extend(key for key in custom_required if not str(self._values.get(key, "")).strip())
        missing.extend(self._provider_option_issues())
        return list(dict.fromkeys(missing))

    def _provider_option_issues(self) -> list[str]:
        """Read-only validation of provider option semantics."""
        provider_key = str(self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER))
        item = provider_profile(provider_key)
        if not item.basic_control and not item.native_tou:
            return []

        def missing_options(entity_id: str | None, expected: Iterable[str], label: str) -> list[str]:
            if not entity_id or not str(entity_id).startswith("select."):
                return []
            state = self.hass.states.get(entity_id)
            options = [] if state is None else list((getattr(state, "attributes", {}) or {}).get("options") or [])
            return [
                f"{label}:{value}"
                for value in expected
                if value and not any(select_option_matches(option, value) for option in options)
            ]

        if provider_key == PROVIDER_CUSTOM:
            work_values = (
                str(self._values.get(CONF_WORK_MODE_SELL_OPTION, "")),
                str(self._values.get(CONF_WORK_MODE_ZERO_LOAD_OPTION, "")),
                str(self._values.get(CONF_WORK_MODE_ZERO_CT_OPTION, "")),
            )
            grid_values = (
                str(self._values.get(CONF_TOU_GRID_ENABLE_OPTION, "")),
                str(self._values.get(CONF_TOU_GRID_DISABLE_OPTION, "")),
            )
        else:
            work_values = tuple(dict.fromkeys([item.sell_mode_option, *item.normal_mode_options.values()]))
            grid_values = (item.grid_enabled, item.grid_disabled)

        issues = missing_options(self._values.get(CONF_WORK_MODE_SELECT), work_values, "work_mode_option")
        for idx in range(1, 7):
            issues.extend(missing_options(
                self._values.get(conf_tou_entity(idx, "grid")),
                grid_values,
                f"tou_{idx}_grid_option",
            ))
        return issues

    def _capability_report(self) -> dict[str, dict[str, Any]]:
        """Read-only capability check used by the wizard and diagnostics."""
        def available(key: str) -> bool:
            entity_id = self._values.get(key)
            state = self.hass.states.get(entity_id) if entity_id else None
            return state is not None and state.state not in ("unknown", "unavailable", "none", "")

        groups = {
            "readings": (CONF_BATTERY_SOC_SENSOR, CONF_GRID_POWER_SENSOR, CONF_PV_POWER_SENSOR, CONF_LOAD_POWER_SENSOR, CONF_BATTERY_POWER_SENSOR),
            "basic_control": (CONF_WORK_MODE_SELECT, CONF_MAX_SELL_POWER_NUMBER, CONF_DISCHARGE_CURRENT_NUMBER, CONF_CHARGE_CURRENT_NUMBER, CONF_GRID_CHARGE_CURRENT_NUMBER),
            "selling": (CONF_WORK_MODE_SELECT, CONF_MAX_SELL_POWER_NUMBER, CONF_DISCHARGE_CURRENT_NUMBER, CONF_BATTERY_SOC_SENSOR),
            "charging": (CONF_WORK_MODE_SELECT, CONF_CHARGE_CURRENT_NUMBER, CONF_GRID_CHARGE_CURRENT_NUMBER, CONF_BATTERY_SOC_SENSOR),
            "full_tou": TOU_FIELDS,
            "core_ai": (CONF_BATTERY_SOC_SENSOR, CONF_GRID_POWER_SENSOR, CONF_PV_POWER_SENSOR, CONF_LOAD_POWER_SENSOR, CONF_BATTERY_POWER_SENSOR, CONF_PRICE_SENSOR, CONF_SOLCAST_FORECAST_TODAY_SENSOR),
        }
        provider = provider_profile(str(self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER)))
        report: dict[str, dict[str, Any]] = {}
        for name, fields in groups.items():
            missing = [key for key in fields if not available(key)]
            supported = not (name in ("basic_control", "selling", "charging") and not provider.basic_control)
            supported = supported and not (name == "full_tou" and not provider.native_tou)
            report[name] = {"ok": bool(supported and not missing), "supported": supported, "missing": missing}
        option_issues = self._provider_option_issues()
        work_issues = [item for item in option_issues if item.startswith("work_mode_option")]
        tou_issues = [item for item in option_issues if not item.startswith("work_mode_option")]
        for name in ("basic_control", "selling", "charging"):
            report[name]["missing"].extend(work_issues)
            report[name]["ok"] = bool(report[name]["supported"] and not report[name]["missing"])
        report["full_tou"]["missing"].extend(tou_issues)
        report["full_tou"]["ok"] = bool(report["full_tou"]["supported"] and not report["full_tou"]["missing"])
        operations = {
            key: operation_for_entity(str(value))
            for key, value in self._values.items()
            if key in ENTITY_SPECS and value
        }
        report["operations"] = {"ok": True, "supported": True, "missing": [], "values": operations}
        device_issues = self._mapping_device_issues()
        report["device"] = {
            "ok": bool(self._values.get(CONF_INVERTER_DEVICE_ID) and not device_issues),
            "supported": True,
            "missing": device_issues or ([] if self._values.get(CONF_INVERTER_DEVICE_ID) else [CONF_INVERTER_DEVICE_ID]),
        }
        return report

    async def async_step_inverter_device(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            self._clear_inverter_mapping_if_source_changed()
            return await self.async_step_mapping_mode()
        current = self._values.get(CONF_INVERTER_DEVICE_ID)
        field = (
            vol.Required(CONF_INVERTER_DEVICE_ID, default=current)
            if current
            else vol.Required(CONF_INVERTER_DEVICE_ID)
        )
        return self.async_show_form(
            step_id="inverter_device",
            data_schema=vol.Schema({
                field: selector.DeviceSelector(selector.DeviceSelectorConfig()),
            }),
        )

    async def async_step_inverter(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            provider = str(self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER))
            if provider == PROVIDER_CUSTOM:
                return await self.async_step_provider_options()
            if provider_profile(provider).native_tou:
                return await self.async_step_tou_1_3()
            return await self.async_step_energy_details()
        return self.async_show_form(step_id="inverter", data_schema=self._entity_schema(INVERTER_FIELDS))

    async def async_step_provider_options(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_tou_1_3()
        defaults = {
            CONF_WORK_MODE_SELL_OPTION: "Selling First",
            CONF_WORK_MODE_ZERO_LOAD_OPTION: "Zero Export To Load",
            CONF_WORK_MODE_ZERO_CT_OPTION: "Zero Export To CT",
            CONF_TOU_GRID_ENABLE_OPTION: "on",
            CONF_TOU_GRID_DISABLE_OPTION: "off",
            CONF_TOU_GRID_GENERATOR_OPTION: "Generator",
            CONF_TOU_GRID_BOTH_OPTION: "Both",
        }
        return self.async_show_form(
            step_id="provider_options",
            data_schema=vol.Schema({
                vol.Required(key, default=self._values.get(key, default)): str
                for key, default in defaults.items()
            }),
        )

    async def async_step_tou_1_3(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_tou_4_6()
        fields = ()
        if str(self._values.get(CONF_INVERTER_PROVIDER)) == PROVIDER_SUNSYNK:
            fields += (CONF_WORK_MODE_AUX_ENTITY,)
        fields += tuple(
            conf_tou_entity(index, kind)
            for index in range(1, 4)
            for kind in ("start", "soc", "grid")
        )
        return self.async_show_form(step_id="tou_1_3", data_schema=self._entity_schema(fields))

    async def async_step_tou_4_6(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_energy_details()
        fields = tuple(
            conf_tou_entity(index, kind)
            for index in range(4, 7)
            for kind in ("start", "soc", "grid")
        )
        return self.async_show_form(step_id="tou_4_6", data_schema=self._entity_schema(fields))

    async def async_step_energy_details(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_prices()
        return self.async_show_form(
            step_id="energy_details",
            data_schema=self._entity_schema(ENERGY_DETAIL_FIELDS),
            description_placeholders={"section": "Falownik Deye i przepływy energii — szczegóły"},
        )

    async def async_step_prices(self, user_input=None):
        if user_input is not None:
            # Optional entity selectors may omit a cleared field entirely.
            # Persist all four keys explicitly so reload/reconfigure cannot
            # confuse a user-cleared field with an old, never-configured entry.
            for key in PRICE_FIELDS:
                self._values[key] = str(user_input.get(key) or "")
            contracts, errors = self._resolve_price_mapping_contracts()
            if not errors:
                self._values[CONF_BUY_PRICE_CONTRACT] = contracts["buy"]
                self._values[CONF_SELL_PRICE_CONTRACT] = contracts["sell"]
                return await self.async_step_solcast()
            return self.async_show_form(
                step_id="prices",
                data_schema=self._entity_schema(PRICE_FIELDS),
                errors=errors,
                description_placeholders={"validation": "Popraw mapowanie lub jawny schema źródła cen."},
            )
        # This wizard maps Home Assistant entities only. Operator, tariff,
        # rates and flow signs are edited in the card after explicit saving.
        return self.async_show_form(step_id="prices", data_schema=self._entity_schema(PRICE_FIELDS))

    async def async_step_solcast(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_weather()
        return self.async_show_form(step_id="solcast", data_schema=self._entity_schema(SOLCAST_FIELDS))

    async def async_step_weather(self, user_input=None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_capabilities()
        return self.async_show_form(step_id="weather", data_schema=self._entity_schema((CONF_WEATHER_ENTITY,)))

    async def async_step_capabilities(self, user_input=None):
        report = self._capability_report()
        if user_input is not None and bool(user_input.get("continue")):
            return await self.async_step_inverter_power()
        labels = ("device", "readings", "basic_control", "selling", "charging", "full_tou", "core_ai")
        return self.async_show_form(
            step_id="capabilities",
            data_schema=vol.Schema({vol.Required("continue", default=False): selector.BooleanSelector()}),
            description_placeholders={
                key: ("OK" if report[key]["ok"] else "NIEDOSTĘPNE" if not report[key]["supported"] else "BRAKI: " + ", ".join(report[key]["missing"]))
                for key in labels
            },
        )

    def _detected_entity_max_power_w(self) -> int | None:
        """Read the configured Max Sell Power entity's native maximum if available."""
        entity_id = self._values.get(CONF_MAX_SELL_POWER_NUMBER)
        if not entity_id:
            return None
        return detect_entity_max_power_w(
            self.hass.states.get(entity_id) if self.hass is not None else None
        )

    async def async_step_inverter_power(self, user_input=None):
        """Configure the inverter maximum AC power ceiling."""
        detected = self._detected_entity_max_power_w()
        current = self._values.get(CONF_INVERTER_MAX_POWER_W, DEFAULT_INVERTER_MAX_POWER_W)
        errors: dict[str, str] = {}
        if user_input is not None:
            value = int(user_input[CONF_INVERTER_MAX_POWER_W])
            if not 1000 <= value <= ABSOLUTE_INVERTER_MAX_POWER_W:
                errors[CONF_INVERTER_MAX_POWER_W] = "invalid_inverter_max_power_w"
            if not errors:
                self._values[CONF_INVERTER_MAX_POWER_W] = value
                return await self.async_step_summary()
        proposal = current
        if proposal == DEFAULT_INVERTER_MAX_POWER_W and detected is not None:
            proposal = detected
        return self.async_show_form(
            step_id="inverter_power",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_INVERTER_MAX_POWER_W,
                    default=proposal,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=1000, max=ABSOLUTE_INVERTER_MAX_POWER_W),
                ),
            }),
            errors=errors,
            description_placeholders={
                "detected": str(detected) if detected is not None else "brak",
                "default": str(DEFAULT_INVERTER_MAX_POWER_W),
                "absolute": str(ABSOLUTE_INVERTER_MAX_POWER_W),
            },
        )

    async def async_step_summary(self, user_input=None):
        missing = self._missing_required()
        provider_missing = self._missing_provider_controls()
        device_issues = self._mapping_device_issues()
        # Missing entities intentionally reduce the capability report but do not
        # prevent the user from saving after explicit confirmation.  An entity
        # belonging to another HA device is different: accepting it could target
        # the wrong inverter, so that remains a hard safety error.
        if user_input is not None and bool(user_input.get("confirm")) and not device_issues:
            data = {
                key: value
                for key, value in self._values.items()
                if key not in _REMOVED_GLOBAL_TOU_KEYS
            }
            configured_name = str(data.pop(CONF_NAME, "Deye Energy Manager"))
            title = "" if self._is_options else configured_name
            return self.async_create_entry(title=title, data=data)
        errors = {"confirm": "entity_from_other_device"} if device_issues else {}
        mapped = sum(1 for key in ENTITY_SPECS if self._values.get(key))
        total = len(ENTITY_SPECS)
        return self.async_show_form(
            step_id="summary",
            data_schema=vol.Schema({vol.Required("confirm", default=False): selector.BooleanSelector()}),
            errors=errors,
            description_placeholders={
                "total": str(total),
                "mapped": str(mapped),
                "skipped": str(total - mapped),
                "missing": ", ".join(missing) if missing else "brak",
                "provider_missing": ", ".join(provider_missing) if provider_missing else "brak",
                "device_issues": ", ".join(device_issues) if device_issues else "brak",
                "capabilities": ", ".join(
                    key for key, value in self._capability_report().items()
                    if key != "operations" and value.get("ok")
                ) or "tylko częściowe mapowanie",
            },
        )


class DeyeEnergyManagerConfigFlow(MappingWizardMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration wizard for Deye Energy Manager."""

    VERSION = 1
    MINOR_VERSION = 24

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DeyeEnergyManagerOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self._prepare_values()
        if user_input is not None:
            self._values.update(user_input)
            self._clear_inverter_mapping_if_source_changed()
            return await self.async_step_inverter_device()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default="Deye Energy Manager"): str,
                vol.Required(CONF_INVERTER_PROVIDER, default=DEFAULT_INVERTER_PROVIDER): select_with_labels([
                    (provider, PROVIDER_LABELS[provider]) for provider in INVERTER_PROVIDERS
                ]),
            }),
        )

    async def async_step_mapping_mode(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._values.update(user_input)
            return await self.async_step_inverter()
        return self.async_show_form(
            step_id="mapping_mode",
            data_schema=vol.Schema({
                vol.Required(CONF_MAPPING_MODE, default=DEFAULT_MAPPING_MODE): select_with_labels([
                    ("automatic", "Automatyczne podpowiedzi (zalecane)"),
                    ("manual", "Wybór ręczny"),
                ]),
            }),
        )


class DeyeEnergyManagerOptionsFlow(MappingWizardMixin, config_entries.OptionsFlowWithReload):
    _is_options = True

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        self._prepare_values()
        if user_input is not None:
            self._values.update(user_input)
            self._clear_inverter_mapping_if_source_changed()
            return await self.async_step_inverter_device()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_INVERTER_PROVIDER,
                    default=self._values.get(CONF_INVERTER_PROVIDER, DEFAULT_INVERTER_PROVIDER),
                ): select_with_labels([(provider, PROVIDER_LABELS[provider]) for provider in INVERTER_PROVIDERS]),
            }),
        )

    async def async_step_mapping_mode(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            if user_input.get(CONF_MAPPING_MODE) == "existing":
                # This action is deliberately a no-op: no discovery, no wizard,
                # no history/profile reset and no new optional defaults.
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.data, **self.config_entry.options},
                )
            self._values.update(user_input)
            return await self.async_step_inverter()
        return self.async_show_form(
            step_id="mapping_mode",
            data_schema=vol.Schema({
                vol.Required(CONF_MAPPING_MODE, default=self._values.get(CONF_MAPPING_MODE, DEFAULT_MAPPING_MODE)): select_with_labels([("automatic", "Automatyczne podpowiedzi (zalecane)"), ("manual", "Wybór ręczny"), ("existing", "Zachowaj bieżące mapowanie")]),
            }),
        )

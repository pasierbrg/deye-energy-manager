from __future__ import annotations

import inspect
import json
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from pathlib import Path

from .const import DOMAIN, PLATFORMS, WORK_MODES, PHYSICAL_NORMAL_MODES
from .manager import DeyeEnergyManagerRuntime

APPLY_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): vol.In(WORK_MODES),
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=13000)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Optional("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Optional("grid_charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
    }
)
MANUAL_SELL_SCHEMA = vol.Schema(
    {
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=13000)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
    }
)
CHARGE_SCHEMA = vol.Schema(
    {vol.Required("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240))}
)
AI_DATA_SCHEMA = vol.Schema({vol.Required("data"): vol.All(cv.string, vol.Length(max=200000))})
AI_RATING_SCHEMA = vol.Schema({vol.Required("timestamp"): vol.Coerce(float), vol.Required("rating"): vol.All(vol.Coerce(int), vol.Range(min=1, max=5))})
DEFAULT_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): vol.In(WORK_MODES),
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=13000)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("grid_charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
    }
)
SCHEDULE_PATCH_SCHEMA = vol.Schema(
    {vol.Required("data"): vol.All(cv.string, vol.Length(max=100000))}
)
TARIFF_SETTINGS_SCHEMA = vol.Schema(
    {vol.Required("data"): vol.All(cv.string, vol.Length(max=50000))}
)
CHARGE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("grid_charge_enabled"): cv.boolean,
        vol.Required("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("grid_charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("target_soc"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    }
)
NORMAL_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("physical_work_mode"): vol.In(list(PHYSICAL_NORMAL_MODES)),
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=13000)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("grid_charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("tou_soc"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    }
)
SERVICE_NAMES = (
    "apply_settings",
    "manual_sell",
    "charge_now",
    "stop_selling",
    "restore_defaults",
    "resume_manager",
    "emergency_stop",
    "save_ai_settings",
    "save_ai_analysis",
    "clear_ai_history",
    "rate_ai_analysis",
    "clear_history",
    "apply_schedule_patch",
    "save_tariff_settings",
    "save_charge_profile",
    "save_normal_profile",
    "save_default_settings",
    "refresh_tariff_catalog",
    "save_future_plan",
    "cancel_future_plan",
)
_STATIC_PATH_REGISTERED = False

# Helper entities that the card expects.  They must be visible in the entity
# registry so that the profile forms and slot Charge copy work even after a
# reinstall or a registry reset.
_PROFILE_HELPER_ENTITY_KEYS = {
    "number": [
        "charge_profile_charge_current",
        "charge_profile_discharge_current",
        "charge_profile_grid_charge_current",
        "charge_profile_target_soc",
        "normal_profile_sell_power",
        "normal_profile_discharge_current",
        "normal_profile_charge_current",
        "normal_profile_grid_charge_current",
        "normal_profile_tou_soc",
    ],
    "switch": ["charge_profile_grid_enabled"],
    "select": ["normal_profile_mode"],
}


def _ensure_profile_entities_enabled(hass: HomeAssistant, entry_id: str) -> None:
    """Make sure profile helper entities are enabled in the registry.

    If an entity was disabled by a previous install or by the user, re-enable
    it so the platform setup creates and publishes it.  This keeps stable
    unique_id and entity_id.
    """
    registry = er.async_get(hass)
    for platform, keys in _PROFILE_HELPER_ENTITY_KEYS.items():
        for key in keys:
            unique_id = f"{entry_id}_{key}"
            entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id is None:
                continue
            reg_entry = registry.async_get(entity_id)
            if reg_entry is not None and reg_entry.disabled_by is not None:
                registry.async_update_entity(entity_id, disabled_by=None)


def _parse_json_payload(value: str, expected_type: type | tuple[type, ...]) -> Any:
    """Parse a JSON string passed from the Lovelace card and validate its type.

    Raises a clear ValueError for malformed JSON or unexpected type so that
    the service call fails with a controlled message instead of an unhandled
    exception.
    """
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as err:
        raise ValueError("Nieprawidłowy JSON") from err
    if not isinstance(parsed, expected_type):
        raise ValueError(f"Oczekiwano typu {expected_type}, otrzymano {type(parsed).__name__}")
    return parsed


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    global _STATIC_PATH_REGISTERED
    runtime = DeyeEnergyManagerRuntime(
        hass=hass,
        entry_id=entry.entry_id,
        data={**entry.data, **entry.options},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await runtime.async_start()
    # Make profile helper entities visible before platform setup so they are
    # created and published even if a previous run disabled them.
    _ensure_profile_entities_enabled(hass, entry.entry_id)
    if not _STATIC_PATH_REGISTERED:
        static_path = str(Path(__file__).parent / "www")
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [StaticPathConfig("/deye_energy_manager", static_path, True)]
            )
        elif hasattr(hass.http, "async_register_static_path"):
            result = hass.http.async_register_static_path("/deye_energy_manager", static_path, True)
            if inspect.isawaitable(result):
                await result
        elif hasattr(hass.http, "register_static_path"):
            hass.http.register_static_path("/deye_energy_manager", static_path, True)
        _STATIC_PATH_REGISTERED = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_apply_settings(call: ServiceCall) -> None:
        await runtime.async_apply_settings(
            call.data["mode"],
            call.data["sell_power"],
            call.data["discharge_current"],
            call.data.get("charge_current", runtime.default_charge_current),
            call.data.get("grid_charge_current", runtime.default_grid_charge_current),
        )

    async def handle_manual_sell(call: ServiceCall) -> None:
        runtime.manual_sell_power = call.data["sell_power"]
        runtime.manual_discharge_current = call.data["discharge_current"]
        await runtime.async_manual_sell()

    async def handle_charge_now(call: ServiceCall) -> None:
        runtime.manual_charge_current = call.data["charge_current"]
        await runtime.async_charge_now()

    async def handle_stop_selling(call: ServiceCall) -> None:
        await runtime.async_request_stop()

    async def handle_restore_defaults(call: ServiceCall) -> None:
        await runtime.async_restore_defaults()

    async def handle_resume_manager(call: ServiceCall) -> None:
        await runtime.async_resume_manager()

    async def handle_emergency_stop(call: ServiceCall) -> None:
        await runtime.async_emergency_stop()

    async def handle_save_ai_settings(call: ServiceCall) -> None:
        data = _parse_json_payload(call.data["data"], dict)
        await runtime.async_set_ai_settings(data)

    async def handle_save_ai_analysis(call: ServiceCall) -> None:
        data = _parse_json_payload(call.data["data"], dict)
        await runtime.async_add_ai_analysis(data)

    async def handle_clear_ai_history(call: ServiceCall) -> None:
        await runtime.async_clear_ai_history()

    async def handle_rate_ai_analysis(call: ServiceCall) -> None:
        await runtime.async_rate_ai_analysis(call.data["timestamp"], call.data["rating"])

    async def handle_clear_history(call: ServiceCall) -> None:
        await runtime.async_clear_all_history()

    async def handle_apply_schedule_patch(call: ServiceCall) -> None:
        updates = _parse_json_payload(call.data["data"], list)
        await runtime.async_apply_schedule_patch(updates)

    async def handle_save_tariff_settings(call: ServiceCall) -> None:
        settings = _parse_json_payload(call.data["data"], dict)
        normalized = await runtime.async_update_tariff_settings(settings)
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, **normalized},
        )

    async def handle_save_charge_profile(call: ServiceCall) -> None:
        await runtime.async_save_charge_profile(dict(call.data))

    async def handle_save_normal_profile(call: ServiceCall) -> None:
        await runtime.async_save_normal_profile(dict(call.data))

    async def handle_save_default_settings(call: ServiceCall) -> None:
        await runtime.async_save_default_settings(dict(call.data))

    async def handle_refresh_tariff_catalog(call: ServiceCall) -> None:
        await runtime.async_refresh_tariff_catalog()

    async def handle_save_future_plan(call: ServiceCall) -> None:
        plan = _parse_json_payload(call.data["data"], dict)
        await runtime.async_save_future_plan(plan)

    async def handle_cancel_future_plan(call: ServiceCall) -> None:
        await runtime.async_cancel_future_plan()

    hass.services.async_register(DOMAIN, "apply_settings", handle_apply_settings, schema=APPLY_SCHEMA)
    hass.services.async_register(DOMAIN, "manual_sell", handle_manual_sell, schema=MANUAL_SELL_SCHEMA)
    hass.services.async_register(DOMAIN, "charge_now", handle_charge_now, schema=CHARGE_SCHEMA)
    hass.services.async_register(DOMAIN, "stop_selling", handle_stop_selling)
    hass.services.async_register(DOMAIN, "restore_defaults", handle_restore_defaults)
    hass.services.async_register(DOMAIN, "resume_manager", handle_resume_manager)
    hass.services.async_register(DOMAIN, "emergency_stop", handle_emergency_stop)
    hass.services.async_register(DOMAIN, "save_ai_settings", handle_save_ai_settings, schema=AI_DATA_SCHEMA)
    hass.services.async_register(DOMAIN, "save_ai_analysis", handle_save_ai_analysis, schema=AI_DATA_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_ai_history", handle_clear_ai_history)
    hass.services.async_register(DOMAIN, "rate_ai_analysis", handle_rate_ai_analysis, schema=AI_RATING_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_history", handle_clear_history)
    hass.services.async_register(
        DOMAIN,
        "apply_schedule_patch",
        handle_apply_schedule_patch,
        schema=SCHEDULE_PATCH_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "save_tariff_settings",
        handle_save_tariff_settings,
        schema=TARIFF_SETTINGS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "save_charge_profile",
        handle_save_charge_profile,
        schema=CHARGE_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "save_normal_profile",
        handle_save_normal_profile,
        schema=NORMAL_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "save_default_settings",
        handle_save_default_settings,
        schema=DEFAULT_SETTINGS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "refresh_tariff_catalog",
        handle_refresh_tariff_catalog,
    )
    hass.services.async_register(DOMAIN, "save_future_plan", handle_save_future_plan, schema=AI_DATA_SCHEMA)
    hass.services.async_register(DOMAIN, "cancel_future_plan", handle_cancel_future_plan)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime:
        await runtime.async_unload()
    if unload_ok and DOMAIN in hass.data and not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
        for service_name in SERVICE_NAMES:
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry and enable profile helper entities.

    Bumping the minor version triggers this so missing/disabled profile helper
    entities are recreated after a reinstall or registry reset.
    """
    _ensure_profile_entities_enabled(hass, config_entry.entry_id)
    return True

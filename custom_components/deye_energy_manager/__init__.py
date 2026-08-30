from __future__ import annotations

import json
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from .const import (
    ABSOLUTE_INVERTER_MAX_POWER_W,
    CONF_BUY_SELLER_ID,
    CONF_BUY_SELLER_TARIFF_ID,
    CONF_INVERTER_PROVIDER,
    DEFAULT_BUY_SELLER_ID,
    DEFAULT_BUY_SELLER_TARIFF_ID,
    DOMAIN,
    PHYSICAL_NORMAL_MODES,
    PLATFORMS,
    PROVIDER_LEWA_REKA,
    WORK_MODES,
)
from .frontend import async_setup_frontend, cancel_frontend_followup
from .manager import DeyeEnergyManagerRuntime
from .price_sources import (
    contract_mapping_matches,
    detect_source_adapter,
    migrate_legacy_price_contracts,
    rebuild_price_contract,
    resolve_contract_schemas,
)

APPLY_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): vol.In(WORK_MODES),
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=ABSOLUTE_INVERTER_MAX_POWER_W)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Optional("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Optional("grid_charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
    }
)
MANUAL_SELL_SCHEMA = vol.Schema(
    {
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=ABSOLUTE_INVERTER_MAX_POWER_W)),
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
        vol.Optional("physical_work_mode"): vol.In(list(PHYSICAL_NORMAL_MODES)),
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=ABSOLUTE_INVERTER_MAX_POWER_W)),
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
        vol.Required("sell_power"): vol.All(vol.Coerce(float), vol.Range(min=0, max=ABSOLUTE_INVERTER_MAX_POWER_W)),
        vol.Required("discharge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("grid_charge_current"): vol.All(vol.Coerce(float), vol.Range(min=0, max=240)),
        vol.Required("tou_soc"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    }
)
PLAN_EXECUTION_SCHEMA = vol.Schema(
    {
        vol.Optional("date"): vol.All(cv.string, vol.Length(max=10)),
    }
)
TOU_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
        vol.Optional("start"): vol.All(cv.string, vol.Length(max=5)),
        vol.Optional("end"): vol.All(cv.string, vol.Length(max=5)),
        vol.Optional("soc"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional("grid_charge"): cv.boolean,
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
    "save_ai_profiles",
    "save_ai_api_settings",
    "test_ai_api",
    "analyze_ai_api",
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
    "get_plan_execution",
    "set_tou_slot",
)
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration domain before config entries are loaded.

    The runtime remains config-entry-only.  This lightweight domain hook is
    required by Home Assistant during the normal integration setup phase and
    also keeps a legacy YAML domain declaration from preventing config entries
    and the frontend resource from loading.
    """
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy entries without changing any mapped entity identifier.

    Entries created before the provider layer are Lewa-Reka mappings.  Adding
    the explicit provider is data-only and deliberately leaves options and all
    entity IDs untouched.
    """
    if entry.version != 1:
        return False
    if entry.minor_version >= 24:
        return True
    data = dict(entry.data)
    options = dict(entry.options)
    if entry.minor_version >= 23:
        if CONF_BUY_SELLER_ID not in data and CONF_BUY_SELLER_ID not in options:
            options[CONF_BUY_SELLER_ID] = DEFAULT_BUY_SELLER_ID
        if CONF_BUY_SELLER_TARIFF_ID not in data and CONF_BUY_SELLER_TARIFF_ID not in options:
            options[CONF_BUY_SELLER_TARIFF_ID] = DEFAULT_BUY_SELLER_TARIFF_ID
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            minor_version=24,
        )
        return True
    if CONF_INVERTER_PROVIDER not in data and CONF_INVERTER_PROVIDER not in options:
        data[CONF_INVERTER_PROVIDER] = PROVIDER_LEWA_REKA
    merged = migrate_legacy_price_contracts({**data, **options})
    definitions = {
        "buy_price_contract": ("buy_price_today_sensor", "buy_price_tomorrow_sensor"),
        "sell_price_contract": ("price_sensor", "sell_price_tomorrow_sensor"),
    }
    for key, mapping_keys in definitions.items():
        saved_contract = dict(merged.get(key) or {})
        entities = {
            day_name: str(
                merged.get(mapping_key) or ""
                if mapping_key in merged
                else saved_contract.get(f"{day_name}_entity") or ""
            )
            for day_name, mapping_key in zip(("today", "tomorrow"), mapping_keys)
        }
        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(hass)
        except (AttributeError, ImportError, TypeError):
            registry = None
        states = []
        bindings: dict[str, dict[str, str]] = {}
        adapters: dict[str, str] = {}
        for day_name in ("today", "tomorrow"):
            entity_id = entities[day_name]
            registry_entry = registry.async_get(entity_id) if registry is not None and hasattr(registry, "async_get") else None
            if registry_entry is None and registry is not None:
                registry_entry = getattr(registry, "entities", {}).get(entity_id)
            binding = {"entity_id": entity_id} if entity_id else {}
            if registry_entry is not None:
                binding.update({
                    "registry_entry_id": str(getattr(registry_entry, "id", "") or ""),
                    "platform": str(getattr(registry_entry, "platform", "") or ""),
                    "config_entry_id": str(getattr(registry_entry, "config_entry_id", "") or ""),
                    "unique_id": str(getattr(registry_entry, "unique_id", "") or ""),
                    "device_id": str(getattr(registry_entry, "device_id", "") or ""),
                })
            bindings[day_name] = binding
            detected = detect_source_adapter(
                entity_id,
                platform=str(getattr(registry_entry, "platform", "") or "") or None,
            )
            saved_adapter = str(
                saved_contract.get(f"resolved_adapter_{day_name}")
                or saved_contract.get("source_adapter")
                or ""
            )
            adapters[day_name] = (
                saved_adapter
                if detected == "generic"
                and contract_mapping_matches(saved_contract, entities["today"], entities["tomorrow"])
                and saved_adapter in {"pstryk", "rce_pse", "custom"}
                else detected
            )
            states.append(hass.states.get(entity_id) if entity_id else None)
        contract = rebuild_price_contract(
            saved_contract,
            "buy" if key == "buy_price_contract" else "sell",
            entities["today"],
            entities["tomorrow"],
            adapters["today"],
            adapters["tomorrow"],
        )
        for day_name in ("today", "tomorrow"):
            entity_id = entities[day_name]
            binding = bindings[day_name]
            contract[f"{day_name}_binding"] = binding
            contract[f"resolved_{day_name}_entity"] = entity_id
            contract[f"stable_identity_{day_name}_status"] = "unmapped" if not entity_id else "bound" if binding.get("registry_entry_id") else "entity_id_only"
            contract[f"stable_identity_{day_name}_reason"] = "user_unmapped" if not entity_id else ""
            if not entity_id:
                contract[f"resolved_schema_{day_name}"] = {}
        contract, _diagnostics = resolve_contract_schemas(contract, states[0], states[1])
        if key in data:
            data[key] = contract
        else:
            options[key] = contract
        for mapping_key, entity_field in zip(mapping_keys, ("today_entity", "tomorrow_entity")):
            value = entities["today" if entity_field == "today_entity" else "tomorrow"]
            if mapping_key in data:
                data[mapping_key] = value
            elif mapping_key in options:
                options[mapping_key] = value
            elif key in data:
                data[mapping_key] = value
            else:
                options[mapping_key] = value
    if CONF_BUY_SELLER_ID not in data and CONF_BUY_SELLER_ID not in options:
        options[CONF_BUY_SELLER_ID] = DEFAULT_BUY_SELLER_ID
    if CONF_BUY_SELLER_TARIFF_ID not in data and CONF_BUY_SELLER_TARIFF_ID not in options:
        options[CONF_BUY_SELLER_TARIFF_ID] = DEFAULT_BUY_SELLER_TARIFF_ID
    hass.config_entries.async_update_entry(
        entry,
        data=data,
        options=options,
        minor_version=24,
    )
    return True


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
    runtime = DeyeEnergyManagerRuntime(
        hass=hass,
        entry_id=entry.entry_id,
        data={**entry.data, **entry.options},
    )
    runtime._platform_setup_in_progress = True
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await runtime.async_start()
    await async_setup_frontend(hass)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        runtime._platform_setup_in_progress = False
        raise
    else:
        runtime.finish_platform_setup()

    async def handle_apply_settings(call: ServiceCall) -> None:
        sell_power = call.data["sell_power"]
        runtime.validate_manual_sell_power_w("apply_settings", sell_power)
        await runtime.async_apply_settings(
            call.data["mode"],
            sell_power,
            call.data["discharge_current"],
            call.data.get("charge_current", runtime.default_charge_current),
            call.data.get("grid_charge_current", runtime.default_grid_charge_current),
        )

    async def handle_manual_sell(call: ServiceCall) -> None:
        sell_power = call.data["sell_power"]
        runtime.validate_manual_sell_power_w("manual_sell", sell_power)
        runtime.manual_sell_power = sell_power
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

    async def handle_save_ai_profiles(call: ServiceCall) -> None:
        data = _parse_json_payload(call.data["data"], dict)
        await runtime.async_set_user_profiles(data)

    async def handle_save_ai_api_settings(call: ServiceCall) -> None:
        data = _parse_json_payload(call.data["data"], dict)
        normalized = runtime.update_ai_api_config(data)
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, "ai_api": normalized},
        )

    async def handle_test_ai_api(call: ServiceCall) -> None:
        await runtime.async_run_ai_api(connection_test=True, force=True)

    async def handle_analyze_ai_api(call: ServiceCall) -> None:
        await runtime.async_run_ai_api(force=True)

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
        payload = _parse_json_payload(call.data["data"], (list, dict))
        if isinstance(payload, list):
            await runtime.async_apply_schedule_patch(payload)
            return
        unknown = set(payload) - {"updates", "replace_day", "date"}
        if unknown:
            raise ValueError(
                "Nieobsługiwane pola Apply Today: " + ", ".join(sorted(unknown))
            )
        if payload.get("replace_day") is not True:
            raise ValueError("Obiektowy payload harmonogramu wymaga replace_day=true")
        updates = payload.get("updates")
        if not isinstance(updates, list):
            raise ValueError("Apply Today wymaga listy updates")
        await runtime.async_apply_schedule_patch(
            updates,
            replace_day=True,
            date=str(payload.get("date") or ""),
        )

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

    async def handle_get_plan_execution(call: ServiceCall) -> dict[str, Any]:
        return runtime.plan_execution_day(call.data.get("date"))

    async def handle_set_tou_slot(call: ServiceCall) -> None:
        await runtime.async_set_physical_tou_slot(
            call.data["slot"],
            start=call.data.get("start"),
            end=call.data.get("end"),
            soc=call.data.get("soc"),
            grid_charge=call.data.get("grid_charge"),
        )

    hass.services.async_register(DOMAIN, "apply_settings", handle_apply_settings, schema=APPLY_SCHEMA)
    hass.services.async_register(DOMAIN, "manual_sell", handle_manual_sell, schema=MANUAL_SELL_SCHEMA)
    hass.services.async_register(DOMAIN, "charge_now", handle_charge_now, schema=CHARGE_SCHEMA)
    hass.services.async_register(DOMAIN, "stop_selling", handle_stop_selling)
    hass.services.async_register(DOMAIN, "restore_defaults", handle_restore_defaults)
    hass.services.async_register(DOMAIN, "resume_manager", handle_resume_manager)
    hass.services.async_register(DOMAIN, "emergency_stop", handle_emergency_stop)
    hass.services.async_register(DOMAIN, "save_ai_settings", handle_save_ai_settings, schema=AI_DATA_SCHEMA)
    hass.services.async_register(DOMAIN, "save_ai_profiles", handle_save_ai_profiles, schema=AI_DATA_SCHEMA)
    hass.services.async_register(DOMAIN, "save_ai_api_settings", handle_save_ai_api_settings, schema=AI_DATA_SCHEMA)
    hass.services.async_register(DOMAIN, "test_ai_api", handle_test_ai_api)
    hass.services.async_register(DOMAIN, "analyze_ai_api", handle_analyze_ai_api)
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
    hass.services.async_register(
        DOMAIN,
        "get_plan_execution",
        handle_get_plan_execution,
        schema=PLAN_EXECUTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "set_tou_slot",
        handle_set_tou_slot,
        schema=TOU_SLOT_SCHEMA,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime:
        await runtime.async_unload()
    if unload_ok and DOMAIN in hass.data and not hass.data[DOMAIN]:
        cancel_frontend_followup(hass)
        hass.data.pop(DOMAIN)
        for service_name in SERVICE_NAMES:
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
    return unload_ok

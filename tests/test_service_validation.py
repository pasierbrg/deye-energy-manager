from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "deye_energy_manager"


class _FakeVolRequired:
    def __init__(self, key, default=None):
        self.key = key
        self.default = default


class _FakeVolOptional:
    def __init__(self, key, default=None, description=None):
        self.key = key
        self.default = default
        self.description = description or {}


class _FakeVolInvalid(Exception):
    pass


class _FakeVolSchema:
    def __init__(self, schema):
        self.schema = schema

    def __call__(self, data):
        if not isinstance(data, dict):
            raise _FakeVolInvalid("expected dict")
        result = dict(data)
        for key, validator in self.schema.items():
            actual_key = key.key if isinstance(key, (_FakeVolRequired, _FakeVolOptional)) else key
            if actual_key not in result:
                if isinstance(key, _FakeVolRequired):
                    raise _FakeVolInvalid(f"required key {actual_key} missing")
                if isinstance(key, _FakeVolOptional) and key.default is not None:
                    result[actual_key] = key.default
                continue
            try:
                result[actual_key] = validator(result[actual_key])
            except Exception as err:
                raise _FakeVolInvalid(f"invalid value for {actual_key}: {err}") from err
        return result


def _fake_vol_all(*validators):
    def _run(value):
        for validator in validators:
            value = validator(value)
        return value
    return _run


def _fake_vol_range(*, min=None, max=None):
    def _run(value):
        if not isinstance(value, (int, float)):
            raise _FakeVolInvalid("not a number")
        if min is not None and value < min:
            raise _FakeVolInvalid(f"below {min}")
        if max is not None and value > max:
            raise _FakeVolInvalid(f"above {max}")
        return value
    return _run


def _fake_vol_coerce(type_):
    def _run(value):
        try:
            return type_(value)
        except Exception as err:
            raise _FakeVolInvalid(f"cannot coerce to {type_}") from err
    return _run


def _fake_vol_in(options):
    def _run(value):
        if value not in options:
            raise _FakeVolInvalid(f"not in {options}")
        return value
    return _run


def _fake_vol_length(*, max=None):
    def _run(value):
        if max is not None and len(value) > max:
            raise _FakeVolInvalid(f"length above {max}")
        return value
    return _run


def _install_dependencies() -> None:
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = _FakeVolSchema
    voluptuous.Required = _FakeVolRequired
    voluptuous.Optional = _FakeVolOptional
    voluptuous.All = _fake_vol_all
    voluptuous.Range = _fake_vol_range
    voluptuous.Coerce = _fake_vol_coerce
    voluptuous.In = _fake_vol_in
    voluptuous.Length = _fake_vol_length
    voluptuous.Invalid = _FakeVolInvalid
    sys.modules["voluptuous"] = voluptuous

    cv = types.ModuleType("homeassistant.helpers.config_validation")
    cv.string = lambda value: value if isinstance(value, str) else (_ for _ in ()).throw(TypeError("expected string"))
    cv.boolean = bool
    sys.modules["homeassistant.helpers.config_validation"] = cv


def _install_home_assistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    helpers_typing = types.ModuleType("homeassistant.helpers.typing")
    helpers_typing.ConfigType = dict
    event = types.ModuleType("homeassistant.helpers.event")
    storage = types.ModuleType("homeassistant.helpers.storage")
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object

    class _ConfigFlowBase:
        pass

    class ConfigFlowMeta(type):
        def __init__(cls, name, bases, namespace, **kwargs):
            super().__init__(name, bases, namespace)

    class ConfigFlow(_ConfigFlowBase, metaclass=ConfigFlowMeta):
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlowWithReload = object
    const = types.ModuleType("homeassistant.const")
    const.CONF_NAME = "name"
    selector = types.ModuleType("homeassistant.helpers.selector")

    selector.SelectSelector = lambda config: None
    selector.SelectSelectorConfig = lambda **kwargs: kwargs
    selector.EntitySelector = lambda config: (lambda value: value)
    selector.EntitySelectorConfig = lambda **kwargs: kwargs
    selector.DeviceSelector = lambda config: None
    selector.DeviceSelectorConfig = lambda **kwargs: kwargs
    selector.BooleanSelector = lambda: None
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda _hass: types.SimpleNamespace(entities={})
    sys.modules["homeassistant.helpers.selector"] = selector
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
    helpers.entity_registry = entity_registry
    helpers.selector = selector
    sys.modules["homeassistant.const"] = const

    core.HomeAssistant = object
    core.ServiceCall = object
    core.SupportsResponse = types.SimpleNamespace(ONLY="only")
    core.callback = lambda function: function
    event.async_track_time_interval = lambda *_args, **_kwargs: lambda: None
    event.async_track_point_in_time = lambda *_args, **_kwargs: lambda: None
    event.async_track_state_change_event = lambda *_args, **_kwargs: lambda: None

    class Store:
        def __init__(self, *_args, **_kwargs):
            pass

    storage.Store = Store
    dt.now = lambda: None

    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.core": core,
            "homeassistant.config_entries": config_entries,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.typing": helpers_typing,
            "homeassistant.helpers.event": event,
            "homeassistant.helpers.storage": storage,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
        }
    )


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_install_dependencies()
_install_home_assistant_stubs()
package = types.ModuleType("custom_components.deye_energy_manager")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package
const = _load_module(f"{package.__name__}.const", PACKAGE / "const.py")
manager = _load_module(f"{package.__name__}.manager", PACKAGE / "manager.py")
init = _load_module(f"{package.__name__}", PACKAGE / "__init__.py")


config_flow = _load_module(f"{package.__name__}.config_flow", PACKAGE / "config_flow.py")


class ConfigFlowRequiredEntitiesTests(unittest.TestCase):
    """Verify full-control requirements without blocking partial mappings."""

    def test_required_fields_includes_all_control_entities(self):
        required = config_flow.REQUIRED_FIELDS
        self.assertIn(const.CONF_WORK_MODE_SELECT, required)
        self.assertIn(const.CONF_MAX_SELL_POWER_NUMBER, required)
        self.assertIn(const.CONF_DISCHARGE_CURRENT_NUMBER, required)
        self.assertIn(const.CONF_CHARGE_CURRENT_NUMBER, required)
        self.assertIn(const.CONF_GRID_CHARGE_CURRENT_NUMBER, required)
        self.assertIn(const.CONF_BATTERY_SOC_SENSOR, required)

    def test_price_sensors_are_not_required_globally(self):
        self.assertNotIn(const.CONF_PRICE_SENSOR, config_flow.REQUIRED_FIELDS)
        self.assertNotIn(const.CONF_SELL_PRICE_TOMORROW_SENSOR, config_flow.REQUIRED_FIELDS)

    def test_new_pv3_and_battery_soh_mappings_are_optional_and_empty(self):
        self.assertNotIn(const.CONF_PV3_POWER_SENSOR, config_flow.REQUIRED_FIELDS)
        self.assertNotIn(const.CONF_BATTERY_SOH_SENSOR, config_flow.REQUIRED_FIELDS)
        self.assertEqual(config_flow.ENTITY_SPECS[const.CONF_PV3_POWER_SENSOR][0], "")
        self.assertEqual(config_flow.ENTITY_SPECS[const.CONF_BATTERY_SOH_SENSOR][0], "")

    def test_issue_6_vendor_name_alone_never_discovers_unrelated_wifi_sensor(self):
        wifi = types.SimpleNamespace(
            entity_id="sensor.deye_wifi_signal",
            attributes={
                "friendly_name": "Deye WiFi signal",
                "device_class": "signal_strength",
                "unit_of_measurement": "dBm",
            },
        )
        self.assertEqual(
            config_flow.discover_entity(
                [wifi],
                "sensor",
                "",
                ("current electricity market price", "cena sprzedaży"),
                semantic_key=const.CONF_PRICE_SENSOR,
            ),
            "",
        )

    def test_issue_6_price_discovery_rejects_impossible_signal_metadata(self):
        wifi_named_price = types.SimpleNamespace(
            entity_id="sensor.deye_cena_sprzedazy_wifi",
            attributes={
                "friendly_name": "Deye cena sprzedaży",
                "device_class": "signal_strength",
                "unit_of_measurement": "dBm",
            },
        )
        self.assertEqual(
            config_flow.discover_entity(
                [wifi_named_price],
                "sensor",
                "",
                ("cena sprzedaży",),
                semantic_key=const.CONF_PRICE_SENSOR,
            ),
            "",
        )

    def test_issue_6_semantically_valid_price_candidate_is_discovered(self):
        price = types.SimpleNamespace(
            entity_id="sensor.market_sell_price",
            attributes={
                "friendly_name": "Cena sprzedaży energii",
                "unit_of_measurement": "PLN/kWh",
            },
        )
        self.assertEqual(
            config_flow.discover_entity(
                [price],
                "sensor",
                "",
                ("cena sprzedaży",),
                semantic_key=const.CONF_PRICE_SENSOR,
            ),
            price.entity_id,
        )

    def test_issue_3_optional_pv3_and_soh_require_compatible_semantics(self):
        pv_bad = types.SimpleNamespace(
            entity_id="sensor.deye_pv3_power_cost",
            attributes={"friendly_name": "PV3 power", "unit_of_measurement": "PLN"},
        )
        pv_good = types.SimpleNamespace(
            entity_id="sensor.deye3fm2lr_pv3_power",
            attributes={"friendly_name": "PV3 power", "device_class": "power", "unit_of_measurement": "W"},
        )
        soh_bad = types.SimpleNamespace(
            entity_id="sensor.deye_battery_soh_energy",
            attributes={"friendly_name": "Battery SOH", "unit_of_measurement": "kWh"},
        )
        soh_good = types.SimpleNamespace(
            entity_id="sensor.inverter_battery_soh",
            attributes={"friendly_name": "Battery SOH", "device_class": "battery", "unit_of_measurement": "%"},
        )
        self.assertEqual(
            config_flow.discover_entity(
                [pv_bad, pv_good], "sensor", "", ("pv3 power",),
                semantic_key=const.CONF_PV3_POWER_SENSOR,
            ),
            pv_good.entity_id,
        )
        self.assertEqual(
            config_flow.discover_entity(
                [soh_bad, soh_good], "sensor", "", ("battery soh",),
                semantic_key=const.CONF_BATTERY_SOH_SENSOR,
            ),
            soh_good.entity_id,
        )

    def test_all_existing_optional_detailed_mappings_remain_single_fields(self):
        for key in (
            const.CONF_LOAD_L1_POWER_SENSOR,
            const.CONF_LOAD_L2_POWER_SENSOR,
            const.CONF_LOAD_L3_POWER_SENSOR,
            const.CONF_DAILY_ENERGY_BOUGHT_SENSOR,
            const.CONF_DAILY_ENERGY_SOLD_SENSOR,
            const.CONF_DAILY_BATTERY_CHARGE_SENSOR,
            const.CONF_DAILY_BATTERY_DISCHARGE_SENSOR,
        ):
            self.assertEqual(config_flow.ENERGY_DETAIL_FIELDS.count(key), 1)

    def test_every_entity_selector_is_optional_at_mapping_time(self):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._values = {const.CONF_MAPPING_MODE: "manual"}
        schema = wizard._entity_schema(config_flow.INVERTER_FIELDS)
        self.assertTrue(schema.schema)
        self.assertTrue(all(isinstance(marker, _FakeVolOptional) for marker in schema.schema))


class ConfigFlowPartialMappingTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_saves_confirmed_mapping_despite_missing_capabilities(self):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._values = {"name": "Test", const.CONF_INVERTER_PROVIDER: const.PROVIDER_SOLARMAN}
        wizard._is_options = False
        wizard._missing_required = lambda: [const.CONF_BATTERY_SOC_SENSOR]
        wizard._missing_provider_controls = lambda: [const.conf_tou_entity(1, "grid")]
        wizard._mapping_device_issues = lambda: []
        wizard.async_create_entry = lambda **kwargs: kwargs

        result = await wizard.async_step_summary({"confirm": True})

        self.assertEqual("Test", result["title"])
        self.assertEqual(const.PROVIDER_SOLARMAN, result["data"][const.CONF_INVERTER_PROVIDER])

    async def test_summary_still_blocks_entity_from_another_device(self):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._values = {}
        wizard._is_options = True
        wizard._missing_required = lambda: []
        wizard._missing_provider_controls = lambda: []
        wizard._mapping_device_issues = lambda: ["grid_power_sensor:inne_urzadzenie"]
        wizard._capability_report = lambda: {}
        wizard.async_show_form = lambda **kwargs: kwargs

        result = await wizard.async_step_summary({"confirm": True})

        self.assertEqual({"confirm": "entity_from_other_device"}, result["errors"])


class ServiceJsonValidationTests(unittest.TestCase):
    """Verify that backend services reject malformed JSON with a clear error."""

    def test_parse_json_payload_rejects_invalid_json(self):
        with self.assertRaises(ValueError) as ctx:
            init._parse_json_payload("not json", dict)
        self.assertIn("Nieprawidłowy JSON", str(ctx.exception))

    def test_parse_json_payload_rejects_wrong_type(self):
        with self.assertRaises(ValueError) as ctx:
            init._parse_json_payload('["list"]', dict)
        self.assertIn("dict", str(ctx.exception))

    def test_parse_json_payload_accepts_valid_object(self):
        result = init._parse_json_payload('{"key": "value"}', dict)
        self.assertEqual(result, {"key": "value"})

    def test_parse_json_payload_accepts_valid_list(self):
        result = init._parse_json_payload('[{"slot": "00_01"}]', list)
        self.assertEqual(result, [{"slot": "00_01"}])

    def test_parse_json_payload_rejects_empty_string(self):
        with self.assertRaises(ValueError):
            init._parse_json_payload("", dict)

    def test_ai_data_schema_enforces_string(self):
        with self.assertRaises(Exception):
            init.AI_DATA_SCHEMA({"data": 123})

    def test_ai_data_schema_rejects_oversized_payload(self):
        with self.assertRaises(Exception):
            init.AI_DATA_SCHEMA({"data": "x" * 200001})

    def test_schedule_patch_schema_accepts_valid_json_string(self):
        result = init.SCHEDULE_PATCH_SCHEMA({"data": '[{"slot": "00_01"}]'})
        self.assertEqual(result["data"], '[{"slot": "00_01"}]')

    def test_tariff_settings_schema_rejects_non_string(self):
        with self.assertRaises(Exception):
            init.TARIFF_SETTINGS_SCHEMA({"data": {"provider": "pge"}})

    def test_plan_execution_schema_is_optional_and_length_limited(self):
        self.assertEqual({}, init.PLAN_EXECUTION_SCHEMA({}))
        self.assertEqual(
            "2026-07-30",
            init.PLAN_EXECUTION_SCHEMA({"date": "2026-07-30"})["date"],
        )
        with self.assertRaises(Exception):
            init.PLAN_EXECUTION_SCHEMA({"date": "2026-07-300"})

    def test_plan_execution_service_is_registered_as_response_only(self):
        source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('"get_plan_execution"', source)
        self.assertIn("supports_response=SupportsResponse.ONLY", source)
        self.assertIn("return runtime.plan_execution_day", source)

    def test_apply_settings_schema_accepts_optional_charge_current(self):
        result = init.APPLY_SCHEMA({
            "mode": "Sprzedaż",
            "sell_power": 3000,
            "discharge_current": 80,
        })
        self.assertNotIn("charge_current", result)

    def test_apply_settings_schema_accepts_optional_grid_charge_current(self):
        result = init.APPLY_SCHEMA({
            "mode": "Sprzedaż",
            "sell_power": 3000,
            "discharge_current": 80,
            "grid_charge_current": 60,
        })
        self.assertEqual(result.get("grid_charge_current"), 60)

    def test_apply_settings_schema_rejects_unknown_mode(self):
        with self.assertRaises(Exception):
            init.APPLY_SCHEMA({
                "mode": "Nieznany Tryb",
                "sell_power": 3000,
                "discharge_current": 80,
            })

    def test_default_settings_card_to_schema_to_runtime(self):
        """Use the real card payload, service schema and runtime validation."""
        manager.ha_now = lambda: datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
        completed = subprocess.run(
            ["node", str(ROOT / "tests" / "test_default_settings_card.js"), "--emit-payloads"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payloads = json.loads(completed.stdout)
        self.assertEqual([item["mode"] for item in payloads], ["Normalna Praca", "Sprzedaż"])

        class State:
            def __init__(self, state, attributes=None):
                self.state = str(state)
                self.attributes = attributes or {}

        class States:
            def __init__(self, values):
                self.values = values

            def get(self, entity_id):
                return self.values.get(entity_id)

            def async_all(self, domain=None):
                prefix = f"{domain}." if domain else ""
                return [value for key, value in self.values.items() if key.startswith(prefix)]

        class Hass:
            def __init__(self):
                self.states = States({
                    const.DEFAULT_WORK_MODE_SELECT: State(
                        "Zero Export To Load",
                        {"options": ["Selling First", "Zero Export To Load", "Zero Export To CT"]},
                    ),
                    const.DEFAULT_MAX_SELL_POWER: State("3000"),
                    const.DEFAULT_DISCHARGE_CURRENT: State("80"),
                    const.DEFAULT_CHARGE_CURRENT: State("70"),
                    const.DEFAULT_GRID_CHARGE_CURRENT: State("40"),
                })

            def async_create_task(self, coroutine):
                coroutine.close()

        for payload, expected_raw in zip(payloads, ["Zero Export To Load", "Selling First"]):
            validated = init.DEFAULT_SETTINGS_SCHEMA(payload)
            runtime = manager.DeyeEnergyManagerRuntime(
                hass=Hass(),
                entry_id="card-schema-runtime",
                data={
                    const.CONF_INVERTER_PROVIDER: const.PROVIDER_LEWA_REKA,
                    const.CONF_WORK_MODE_SELECT: const.DEFAULT_WORK_MODE_SELECT,
                    const.CONF_MAX_SELL_POWER_NUMBER: const.DEFAULT_MAX_SELL_POWER,
                    const.CONF_DISCHARGE_CURRENT_NUMBER: const.DEFAULT_DISCHARGE_CURRENT,
                    const.CONF_CHARGE_CURRENT_NUMBER: const.DEFAULT_CHARGE_CURRENT,
                    const.CONF_GRID_CHARGE_CURRENT_NUMBER: const.DEFAULT_GRID_CHARGE_CURRENT,
                },
            )
            seen = []
            original = runtime._validate_select_entity

            def capture(label, entity_id, option):
                seen.append(option)
                return original(label, entity_id, option)

            runtime._validate_select_entity = capture
            asyncio.run(runtime.async_save_default_settings(validated))
            self.assertEqual(runtime.default_work_mode, payload["mode"])
            self.assertEqual(seen, [expected_raw])

    def test_set_tou_slot_schema_accepts_each_partial_payload(self):
        for payload in (
            {"slot": 1, "start": "04:00"},
            {"slot": 1, "end": "08:00"},
            {"slot": 1, "soc": 55},
            {"slot": 1, "grid_charge": True},
        ):
            self.assertEqual(init.TOU_SLOT_SCHEMA(payload), payload)

    def test_set_tou_slot_schema_keeps_slot_required(self):
        with self.assertRaises(Exception):
            init.TOU_SLOT_SCHEMA({"soc": 55})

    def test_set_tou_slot_handler_passes_optional_fields_by_name(self):
        source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('start=call.data.get("start")', source)
        self.assertIn('end=call.data.get("end")', source)
        self.assertIn('soc=call.data.get("soc")', source)
        self.assertIn('grid_charge=call.data.get("grid_charge")', source)


class IntegrationSetupTests(unittest.IsolatedAsyncioTestCase):
    """Verify Home Assistant can initialize the domain before config entries."""

    async def test_domain_setup_initializes_runtime_container(self):
        hass = types.SimpleNamespace(data={})

        result = await init.async_setup(hass, {})

        self.assertTrue(result)
        self.assertEqual({}, hass.data[const.DOMAIN])


class ConfigFlowCleanupTests(unittest.IsolatedAsyncioTestCase):
    """Verify obsolete global TOU keys are removed only on conscious Options Flow save."""

    def _make_wizard(self, values):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._values = dict(values)
        wizard._is_options = True
        wizard.async_create_entry = lambda **kwargs: kwargs

        class _Registry:
            entities = {}

        config_flow.er.async_get = lambda _hass: _Registry()

        class _States:
            @staticmethod
            def get(entity_id):
                return _SimpleState("0")

        class _Hass:
            pass

        wizard.hass = _Hass()
        wizard.hass.states = _States()
        return wizard

    async def test_options_resave_removes_old_global_tou_keys(self):
        wizard = self._make_wizard({
            const.CONF_INVERTER_PROVIDER: const.PROVIDER_LEWA_REKA,
            const.CONF_WORK_MODE_SELECT: const.DEFAULT_WORK_MODE_SELECT,
            const.CONF_BATTERY_SOC_SENSOR: const.DEFAULT_BATTERY_SOC,
            "tou_enable_entity": "switch.deye_inverter_time_of_use",
            "tou_enable_option": "Week",
            "tou_disable_option": "Disabled",
        })
        result = await wizard.async_step_summary({"confirm": True})

        self.assertIn("data", result)
        self.assertNotIn("tou_enable_entity", result["data"])
        self.assertNotIn("tou_enable_option", result["data"])
        self.assertNotIn("tou_disable_option", result["data"])
        self.assertIn(const.CONF_WORK_MODE_SELECT, result["data"])

    async def test_options_resave_keeps_valid_keys(self):
        wizard = self._make_wizard({
            const.CONF_INVERTER_PROVIDER: const.PROVIDER_LEWA_REKA,
            const.CONF_WORK_MODE_SELECT: const.DEFAULT_WORK_MODE_SELECT,
            "some_future_key": "preserved",
        })
        result = await wizard.async_step_summary({"confirm": True})

        self.assertIn("some_future_key", result["data"])


class EntityRegistrySafetyTests(unittest.TestCase):
    """Verify that the integration never overrides user/system entity choices."""

    def test_config_flow_minor_version_tracks_provider_mapping_schema(self):
        config_flow_source = (ROOT / "custom_components" / "deye_energy_manager" / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("MINOR_VERSION = 24", config_flow_source)

    def test_init_does_not_auto_enable_entities_and_migration_preserves_mapping(self):
        init_source = (ROOT / "custom_components" / "deye_energy_manager" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("_ensure_profile_entities_enabled", init_source)
        self.assertIn("async def async_migrate_entry", init_source)
        self.assertIn("data[CONF_INVERTER_PROVIDER] = PROVIDER_LEWA_REKA", init_source)
        migration = init_source.split("async def async_migrate_entry")[1].split("def _parse_json_payload")[0]
        self.assertNotIn("data[CONF_PRICE_SENSOR]", migration)
        self.assertIn("registry_entry_id", migration)
        self.assertNotIn("async_update_entity", migration)
        self.assertNotIn("disabled_by", init_source)
        self.assertNotIn("async_update_entity", init_source)

    def test_async_setup_entry_does_not_call_registry_helpers(self):
        init_source = (ROOT / "custom_components" / "deye_energy_manager" / "__init__.py").read_text(encoding="utf-8")
        setup_entry = init_source.split("async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:")[1]
        self.assertNotIn("async_get_entity_id", setup_entry)
        self.assertNotIn("async_update_entity", setup_entry)
        self.assertNotIn("disabled_by", setup_entry)

    def test_setup_does_not_mutate_old_global_tou_keys(self):
        init_source = (ROOT / "custom_components" / "deye_energy_manager" / "__init__.py").read_text(encoding="utf-8")
        setup_entry = init_source.split("async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:")[1]
        self.assertNotIn("tou_enable_entity", setup_entry)
        self.assertNotIn("tou_enable_option", setup_entry)
        self.assertNotIn("tou_disable_option", setup_entry)
        # async_update_entry is used for unrelated features (AI API, tariff
        # settings), never to clean obsolete global TOU keys during startup.
        self.assertNotIn("_REMOVED_GLOBAL_TOU_KEYS", setup_entry)

    def test_domain_setup_hook_exists_and_is_side_effect_free(self):
        init_source = (ROOT / "custom_components" / "deye_energy_manager" / "__init__.py").read_text(encoding="utf-8")
        domain_setup = init_source.split("async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:")[1]
        domain_setup = domain_setup.split("async def async_migrate_entry", 1)[0]
        self.assertIn("hass.data.setdefault(DOMAIN, {})", domain_setup)
        self.assertIn("return True", domain_setup)
        self.assertNotIn("DeyeEnergyManagerRuntime(", domain_setup)
        self.assertNotIn("async_register", domain_setup)


class PriceContractMigrationTests(unittest.IsolatedAsyncioTestCase):
    """Exercise durable source-contract migrations against central mappings."""

    async def test_minor_20_rebuilds_stale_adapter_and_preserves_explicit_empty(self):
        rce_today = "sensor.rce_buy_today"
        rce_tomorrow = "sensor.rce_buy_tomorrow"
        stale_pstryk = {
            "source_adapter": "pstryk",
            "today_entity": "sensor.old_pstryk_today",
            "tomorrow_entity": "sensor.old_pstryk_tomorrow",
            "resolved_adapter_today": "pstryk",
            "resolved_adapter_tomorrow": "pstryk",
            "resolved_schema_today": {"schema_id": "pstryk_aio_interval_v1"},
            "resolved_schema_tomorrow": {"schema_id": "pstryk_aio_interval_v1"},
        }
        entry = types.SimpleNamespace(
            version=1,
            minor_version=20,
            data={
                const.CONF_BUY_PRICE_TODAY_SENSOR: rce_today,
                const.CONF_BUY_PRICE_TOMORROW_SENSOR: rce_tomorrow,
                const.CONF_BUY_PRICE_CONTRACT: stale_pstryk,
                const.CONF_PRICE_SENSOR: "",
                const.CONF_SELL_PRICE_TOMORROW_SENSOR: "",
                const.CONF_SELL_PRICE_CONTRACT: stale_pstryk,
            },
            options={},
        )
        registry_entries = {
            rce_today: types.SimpleNamespace(
                id="rce-today-id", platform="rce_pse", config_entry_id="rce-entry",
                unique_id="rce-buy-today", device_id="rce-device",
            ),
            rce_tomorrow: types.SimpleNamespace(
                id="rce-tomorrow-id", platform="rce_pse", config_entry_id="rce-entry",
                unique_id="rce-buy-tomorrow", device_id="rce-device",
            ),
        }
        registry = types.SimpleNamespace(
            entities=registry_entries,
            async_get=lambda entity_id: registry_entries.get(entity_id),
        )
        er_module = sys.modules["homeassistant.helpers.entity_registry"]
        old_async_get = er_module.async_get
        er_module.async_get = lambda _hass: registry
        updates = []
        hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda _entity_id: None),
            config_entries=types.SimpleNamespace(
                async_update_entry=lambda migrated_entry, **kwargs: updates.append((migrated_entry, kwargs))
            ),
        )
        try:
            self.assertTrue(await init.async_migrate_entry(hass, entry))
        finally:
            er_module.async_get = old_async_get

        self.assertEqual(len(updates), 1)
        migrated_entry, payload = updates[0]
        self.assertIs(migrated_entry, entry)
        self.assertEqual(payload["minor_version"], 24)
        buy = payload["data"][const.CONF_BUY_PRICE_CONTRACT]
        self.assertEqual(buy["source_adapter"], "rce_pse")
        self.assertEqual(buy["economic_role"], "energy_only")
        self.assertEqual(buy["resolved_adapter_today"], "rce_pse")
        self.assertEqual(buy["resolved_adapter_tomorrow"], "rce_pse")
        self.assertEqual(buy["today_entity"], rce_today)
        self.assertEqual(buy["tomorrow_entity"], rce_tomorrow)
        self.assertEqual(buy["today_binding"]["registry_entry_id"], "rce-today-id")
        self.assertNotEqual(buy["resolved_schema_today"].get("schema_id"), "pstryk_aio_interval_v1")
        sell = payload["data"][const.CONF_SELL_PRICE_CONTRACT]
        self.assertEqual(sell["today_entity"], "")
        self.assertEqual(sell["tomorrow_entity"], "")
        self.assertEqual(sell["today_binding"], {})
        self.assertEqual(sell["tomorrow_binding"], {})
        self.assertEqual(sell["resolved_schema_today"], {})
        self.assertEqual(sell["resolved_schema_tomorrow"], {})

    async def test_minor_21_to_22_sanitizes_known_adapter_and_keeps_custom(self):
        rce_today = "sensor.rce_today"
        custom_today = "sensor.custom_sell"
        stale_pstryk = {
            "source_adapter": "pstryk", "today_entity": rce_today, "tomorrow_entity": "",
            "resolved_adapter_today": "pstryk", "semantic_scope": "all_in_variable",
            "includes_distribution_variable": True, "includes_excise": True,
            "includes_service_margin": True, "price_basis": "gross", "unit": "PLN/kWh",
        }
        custom = {
            "source_adapter": "custom", "today_entity": custom_today, "tomorrow_entity": "",
            "resolved_adapter_today": "custom", "semantic_scope": "energy_only",
            "includes_distribution_variable": False, "price_basis": "gross", "unit": "PLN/kWh",
            "list_attribute": "hourly", "value_field": "amount",
        }
        entry = types.SimpleNamespace(
            version=1, minor_version=21,
            data={
                const.CONF_BUY_PRICE_TODAY_SENSOR: rce_today,
                const.CONF_BUY_PRICE_TOMORROW_SENSOR: "",
                const.CONF_BUY_PRICE_CONTRACT: stale_pstryk,
                const.CONF_PRICE_SENSOR: custom_today,
                const.CONF_SELL_PRICE_TOMORROW_SENSOR: "",
                const.CONF_SELL_PRICE_CONTRACT: custom,
            },
            options={},
        )
        registry_entries = {
            rce_today: types.SimpleNamespace(id="rce-id", platform="rce_pse", config_entry_id="rce", unique_id="rce", device_id=None),
            custom_today: types.SimpleNamespace(id="custom-id", platform="other_prices", config_entry_id="custom", unique_id="custom", device_id=None),
        }
        registry = types.SimpleNamespace(entities=registry_entries, async_get=lambda entity_id: registry_entries.get(entity_id))
        er_module = sys.modules["homeassistant.helpers.entity_registry"]
        old_async_get = er_module.async_get
        er_module.async_get = lambda _hass: registry
        updates = []
        hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda _entity_id: None),
            config_entries=types.SimpleNamespace(async_update_entry=lambda migrated_entry, **kwargs: updates.append(kwargs)),
        )
        try:
            self.assertTrue(await init.async_migrate_entry(hass, entry))
        finally:
            er_module.async_get = old_async_get

        payload = updates[0]
        self.assertEqual(payload["minor_version"], 24)
        buy = payload["data"][const.CONF_BUY_PRICE_CONTRACT]
        self.assertEqual(buy["source_adapter"], "rce_pse")
        self.assertEqual(buy["economic_role"], "energy_only")
        self.assertEqual(buy["semantic_scope"], "energy_only")
        self.assertFalse(buy["includes_distribution_variable"])
        self.assertFalse(buy["includes_excise"])
        self.assertFalse(buy["includes_service_margin"])
        sell = payload["data"][const.CONF_SELL_PRICE_CONTRACT]
        self.assertEqual(sell["source_adapter"], "custom")
        self.assertEqual(sell["economic_role"], "")
        self.assertEqual(sell["list_attribute"], "hourly")
        self.assertEqual(sell["value_field"], "amount")

    async def test_minor_22_to_23_adds_known_roles_without_guessing_custom(self):
        buy_today = "sensor.pstryk_buy_today"
        buy_tomorrow = "sensor.pstryk_buy_tomorrow"
        custom_sell = "sensor.custom_sell"
        entry = types.SimpleNamespace(
            version=1,
            minor_version=22,
            data={
                const.CONF_BUY_PRICE_TODAY_SENSOR: buy_today,
                const.CONF_BUY_PRICE_TOMORROW_SENSOR: buy_tomorrow,
                const.CONF_BUY_PRICE_CONTRACT: {
                    "source_adapter": "pstryk",
                    "today_entity": buy_today,
                    "tomorrow_entity": buy_tomorrow,
                },
                const.CONF_PRICE_SENSOR: custom_sell,
                const.CONF_SELL_PRICE_TOMORROW_SENSOR: "",
                const.CONF_SELL_PRICE_CONTRACT: {
                    "source_adapter": "custom",
                    "today_entity": custom_sell,
                    "tomorrow_entity": "",
                    "semantic_scope": "energy_only",
                    "includes_distribution_variable": False,
                    "price_basis": "gross",
                    "unit": "PLN/kWh",
                    "list_attribute": "hourly",
                    "value_field": "amount",
                },
            },
            options={},
        )
        registry_entries = {
            buy_today: types.SimpleNamespace(id="pstryk-today", platform="pstryk", config_entry_id="p", unique_id="bt", device_id=None),
            buy_tomorrow: types.SimpleNamespace(id="pstryk-tomorrow", platform="pstryk", config_entry_id="p", unique_id="bm", device_id=None),
            custom_sell: types.SimpleNamespace(id="custom-sell", platform="other_prices", config_entry_id="c", unique_id="cs", device_id=None),
        }
        registry = types.SimpleNamespace(entities=registry_entries, async_get=lambda entity_id: registry_entries.get(entity_id))
        er_module = sys.modules["homeassistant.helpers.entity_registry"]
        old_async_get = er_module.async_get
        er_module.async_get = lambda _hass: registry
        updates = []
        hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda _entity_id: None),
            config_entries=types.SimpleNamespace(async_update_entry=lambda migrated_entry, **kwargs: updates.append(kwargs)),
        )
        try:
            self.assertTrue(await init.async_migrate_entry(hass, entry))
        finally:
            er_module.async_get = old_async_get

        payload = updates[0]
        self.assertEqual(payload["minor_version"], 24)
        self.assertEqual(payload["data"][const.CONF_BUY_PRICE_TODAY_SENSOR], buy_today)
        self.assertEqual(payload["data"][const.CONF_BUY_PRICE_TOMORROW_SENSOR], buy_tomorrow)
        self.assertEqual(payload["data"][const.CONF_BUY_PRICE_CONTRACT]["economic_role"], "retail_buy_all_in")
        self.assertEqual(payload["data"][const.CONF_SELL_PRICE_CONTRACT]["economic_role"], "")
        self.assertEqual(payload["data"][const.CONF_SELL_PRICE_TOMORROW_SENSOR], "")

    async def test_minor_23_to_24_adds_explicit_empty_seller_without_touching_mappings(self):
        buy_today = "sensor.pstryk_buy_today"
        entry = types.SimpleNamespace(
            version=1,
            minor_version=23,
            data={
                const.CONF_BUY_PRICE_TODAY_SENSOR: buy_today,
                const.CONF_BUY_PRICE_TOMORROW_SENSOR: "",
                const.CONF_BUY_PRICE_CONTRACT: {
                    "source_adapter": "pstryk",
                    "today_entity": buy_today,
                    "tomorrow_entity": "",
                },
            },
            options={"preserved": "yes"},
        )
        updates = []
        hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(
                async_update_entry=lambda migrated_entry, **kwargs: updates.append(kwargs)
            )
        )

        self.assertTrue(await init.async_migrate_entry(hass, entry))

        self.assertEqual(len(updates), 1)
        payload = updates[0]
        self.assertEqual(payload["minor_version"], 24)
        self.assertEqual(payload["data"], entry.data)
        self.assertEqual(payload["options"]["preserved"], "yes")
        self.assertEqual(payload["options"][const.CONF_BUY_SELLER_ID], "")
        self.assertEqual(payload["options"][const.CONF_BUY_SELLER_TARIFF_ID], "")


class InverterMaxPowerConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Verify the inverter power step detects and stores the AC ceiling."""

    def _make_wizard(self, values, states):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._values = dict(values)
        wizard._is_options = True
        wizard.async_show_form = lambda **kwargs: kwargs

        class _States:
            pass

        class _Hass:
            pass

        wizard.hass = _Hass()
        wizard.hass.states = _States()
        wizard.hass.states.get = lambda entity_id: states.get(entity_id)
        return wizard

    def _default_for_key(self, schema, key_name):
        for key in schema.schema:
            if getattr(key, "key", None) == key_name:
                return key.default
        return None

    async def test_inverter_power_step_detects_entity_max(self):
        states = {
            const.DEFAULT_MAX_SELL_POWER: _SimpleState("0", {"max": 15000, "unit_of_measurement": "W"}),
        }
        wizard = self._make_wizard({const.CONF_MAX_SELL_POWER_NUMBER: const.DEFAULT_MAX_SELL_POWER}, states)
        result = await wizard.async_step_inverter_power()
        self.assertEqual(result["step_id"], "inverter_power")
        self.assertEqual(self._default_for_key(result["data_schema"], const.CONF_INVERTER_MAX_POWER_W), 15000)

    async def test_inverter_power_step_preserves_configured_value(self):
        states = {
            const.DEFAULT_MAX_SELL_POWER: _SimpleState("0", {"max": 15000, "unit_of_measurement": "W"}),
        }
        wizard = self._make_wizard(
            {const.CONF_MAX_SELL_POWER_NUMBER: const.DEFAULT_MAX_SELL_POWER, const.CONF_INVERTER_MAX_POWER_W: 12000},
            states,
        )
        result = await wizard.async_step_inverter_power()
        self.assertEqual(self._default_for_key(result["data_schema"], const.CONF_INVERTER_MAX_POWER_W), 12000)

    async def test_inverter_power_step_rejects_out_of_range(self):
        states = {const.DEFAULT_MAX_SELL_POWER: _SimpleState("0", {"max": 15000, "unit_of_measurement": "W"})}
        wizard = self._make_wizard({const.CONF_MAX_SELL_POWER_NUMBER: const.DEFAULT_MAX_SELL_POWER}, states)

        async def _summary(user_input=None):
            return None

        wizard.async_step_summary = _summary
        result = await wizard.async_step_inverter_power({const.CONF_INVERTER_MAX_POWER_W: 60000})
        self.assertEqual(result["step_id"], "inverter_power")
        self.assertIn("invalid_inverter_max_power_w", result["errors"].get(const.CONF_INVERTER_MAX_POWER_W, ""))
        self.assertNotIn(const.CONF_INVERTER_MAX_POWER_W, wizard._values)

    def test_detected_entity_max_ignores_unreliable_attributes(self):
        states = {
            const.DEFAULT_MAX_SELL_POWER: _SimpleState("0", {"max": 500, "unit_of_measurement": "W"}),
        }
        wizard = self._make_wizard({const.CONF_MAX_SELL_POWER_NUMBER: const.DEFAULT_MAX_SELL_POWER}, states)
        self.assertIsNone(wizard._detected_entity_max_power_w())


class PriceMappingConfigFlowTests(unittest.TestCase):
    """Exercise schema validation performed when mapped price entities are saved."""

    def _wizard(self, values, states, entries):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._values = dict(values)

        registry = types.SimpleNamespace(entities=entries)
        config_flow.er.async_get = lambda _hass: registry
        wizard.hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda entity_id: states.get(entity_id)),
            config_entries=types.SimpleNamespace(
                async_get_entry=lambda entry_id: types.SimpleNamespace(domain="pstryk")
                if entry_id == "prices-entry" else None
            ),
        )
        return wizard

    def test_pstryk_metadata_binds_entity_and_resolves_real_today_schema(self):
        entity_id = "sensor.any_user_name"
        state = _SimpleState("unknown", {"today_prices": [
            {"start": "2026-08-23T00:00:00+02:00", "end": "2026-08-23T01:00:00+02:00", "price": 0.4}
        ]})
        entry = types.SimpleNamespace(
            id="registry-price", platform="pstryk", config_entry_id="prices-entry",
            unique_id="buy-today", device_id="price-device",
        )
        wizard = self._wizard(
            {const.CONF_BUY_PRICE_TODAY_SENSOR: entity_id},
            {entity_id: state},
            {entity_id: entry},
        )
        contracts, errors = wizard._resolve_price_mapping_contracts()
        buy = contracts["buy"]
        self.assertEqual(errors, {})
        self.assertEqual(buy["source_adapter"], "pstryk")
        self.assertEqual(buy["today_binding"]["registry_entry_id"], "registry-price")
        self.assertEqual(buy["resolved_schema_today"]["schema_id"], "pstryk_aio_interval_v1")
        self.assertEqual(buy["resolved_schema_today"]["list_attribute"], "today_prices")

    def test_unsupported_mapped_series_is_rejected_on_the_selected_field(self):
        entity_id = "sensor.unsupported_user_price"
        entry = types.SimpleNamespace(
            id="registry-custom", platform="other_prices", config_entry_id="other-entry",
            unique_id="unsupported", device_id="price-device",
        )
        wizard = self._wizard(
            {const.CONF_BUY_PRICE_TODAY_SENSOR: entity_id},
            {entity_id: _SimpleState("0.50", {"not_a_series": [{"foo": "bar"}]})},
            {entity_id: entry},
        )
        _contracts, errors = wizard._resolve_price_mapping_contracts()
        self.assertEqual(errors[const.CONF_BUY_PRICE_TODAY_SENSOR], "unsupported_price_schema")

    def test_price_step_persists_omitted_cleared_fields_and_reload_stays_empty(self):
        sell_today = "sensor.rce_sell_today"
        sell_tomorrow = "sensor.rce_sell_tomorrow"
        entries = {
            sell_today: types.SimpleNamespace(id="sell-today", platform="rce_pse", config_entry_id="rce", unique_id="st", device_id=None),
            sell_tomorrow: types.SimpleNamespace(id="sell-tomorrow", platform="rce_pse", config_entry_id="rce", unique_id="stm", device_id=None),
        }
        state = _SimpleState("unknown", {"prices": [{
            "period": "00:00 - 00:15", "dtime": "2026-08-23 00:15:00",
            "business_date": "2026-08-23", "rce_pln": 0.8,
        }]})
        wizard = self._wizard(
            {
                const.CONF_PRICE_SENSOR: "sensor.previous_sell",
                const.CONF_SELL_PRICE_TOMORROW_SENSOR: "sensor.previous_sell_tomorrow",
                const.CONF_BUY_PRICE_TODAY_SENSOR: "sensor.previous_buy",
                const.CONF_BUY_PRICE_TOMORROW_SENSOR: "sensor.previous_buy_tomorrow",
            },
            {sell_today: state, sell_tomorrow: state},
            entries,
        )

        async def next_step(user_input=None):
            return {"next": True}

        wizard.async_step_solcast = next_step
        schema = wizard._entity_schema(config_flow.PRICE_FIELDS)
        submitted = schema({
            const.CONF_PRICE_SENSOR: sell_today,
            const.CONF_SELL_PRICE_TOMORROW_SENSOR: sell_tomorrow,
            # BUY fields are deliberately omitted by cleared optional selectors.
        })
        self.assertNotIn(const.CONF_BUY_PRICE_TODAY_SENSOR, submitted)
        self.assertNotIn(const.CONF_BUY_PRICE_TOMORROW_SENSOR, submitted)
        markers = {marker.key: marker for marker in schema.schema if hasattr(marker, "key")}
        self.assertIsNone(markers[const.CONF_BUY_PRICE_TODAY_SENSOR].default)
        self.assertEqual(
            markers[const.CONF_BUY_PRICE_TODAY_SENSOR].description["suggested_value"],
            "sensor.previous_buy",
        )
        result = asyncio.run(wizard.async_step_prices(submitted))
        self.assertEqual(result, {"next": True})
        self.assertEqual(wizard._values[const.CONF_BUY_PRICE_TODAY_SENSOR], "")
        self.assertEqual(wizard._values[const.CONF_BUY_PRICE_TOMORROW_SENSOR], "")
        self.assertEqual(wizard._values[const.CONF_BUY_PRICE_CONTRACT]["today_entity"], "")
        self.assertEqual(wizard._values[const.CONF_BUY_PRICE_CONTRACT]["stable_identity_today_status"], "unmapped")

        reloaded = self._wizard(dict(wizard._values), {sell_today: state, sell_tomorrow: state}, entries)
        self.assertEqual(reloaded._entity_default(const.CONF_BUY_PRICE_TODAY_SENSOR), "")
        schema = reloaded._entity_schema(config_flow.PRICE_FIELDS)
        defaults = {
            key.key: key.default
            for key in schema.schema
            if hasattr(key, "key")
        }
        self.assertIsNone(defaults[const.CONF_BUY_PRICE_TODAY_SENSOR])
        self.assertIsNone(defaults[const.CONF_BUY_PRICE_TOMORROW_SENSOR])

    def test_each_of_four_price_fields_can_be_cleared_independently(self):
        for cleared_key in config_flow.PRICE_FIELDS:
            values = {key: f"sensor.{key}" for key in config_flow.PRICE_FIELDS}
            values[cleared_key] = ""
            wizard = self._wizard(values, {}, {})
            self.assertEqual(wizard._entity_default(cleared_key), "")
            for other_key in config_flow.PRICE_FIELDS:
                if other_key != cleared_key:
                    self.assertEqual(wizard._entity_default(other_key), values[other_key])

    def test_options_prepare_promotes_empty_contract_entity_without_provider_default(self):
        wizard = object.__new__(config_flow.MappingWizardMixin)
        wizard._is_options = True
        wizard.config_entry = types.SimpleNamespace(
            data={},
            options={
                const.CONF_BUY_PRICE_CONTRACT: {
                    "source_adapter": "pstryk", "today_entity": "", "tomorrow_entity": "",
                },
            },
        )
        wizard._prepare_values()
        self.assertIn(const.CONF_BUY_PRICE_TODAY_SENSOR, wizard._values)
        self.assertIn(const.CONF_BUY_PRICE_TOMORROW_SENSOR, wizard._values)
        self.assertEqual(wizard._values[const.CONF_BUY_PRICE_TODAY_SENSOR], "")
        self.assertEqual(wizard._values[const.CONF_BUY_PRICE_TOMORROW_SENSOR], "")


class ServicesYamlContractTests(unittest.TestCase):
    SERVICES = yaml.safe_load(
        (ROOT / "custom_components" / "deye_energy_manager" / "services.yaml").read_text(
            encoding="utf-8"
        )
    )

    def _mode_options(self, service_name):
        return self.SERVICES[service_name]["fields"]["mode"]["selector"]["select"]["options"]

    def test_services_yaml_exposes_only_polish_manager_modes(self):
        options = self._mode_options("apply_settings")
        self.assertIn(const.MODE_NORMAL_OPERATION, options)
        self.assertIn(const.MODE_SELLING_FIRST, options)
        self.assertNotIn("Selling First", options)
        self.assertNotIn("Charge", options)
        self.assertNotIn("Zero Export To Load", options)
        self.assertNotIn("Zero Export To CT", options)

    def test_services_yaml_does_not_offer_selling_first(self):
        for service, definition in self.SERVICES.items():
            text = str(definition)
            self.assertNotIn("Selling First", text, f"{service} still mentions Selling First")

    def test_services_yaml_does_not_offer_charge_as_manager_mode(self):
        for service, definition in self.SERVICES.items():
            for field in definition.get("fields", {}).values():
                sel = field.get("selector", {})
                if "select" in sel:
                    options = sel["select"].get("options", [])
                    self.assertNotIn(
                        "Charge",
                        options,
                        f"{service} offers Charge as a select option",
                    )

    def test_legacy_english_service_mode_is_still_normalized(self):
        self.assertEqual(
            const.normalize_manager_mode("Selling First"), const.MODE_SELLING_FIRST
        )
        self.assertEqual(
            const.normalize_manager_mode("Charge"), const.MODE_CHARGE
        )
        self.assertEqual(
            const.normalize_manager_mode("normal"), const.MODE_NORMAL_OPERATION
        )

    def test_set_tou_slot_yaml_marks_only_slot_as_required(self):
        fields = self.SERVICES["set_tou_slot"]["fields"]
        self.assertTrue(fields["slot"]["required"])
        for field in ("start", "end", "soc", "grid_charge"):
            self.assertFalse(fields[field]["required"])


class _SimpleState:
    def __init__(self, state, attributes=None):
        self.state = str(state)
        self.attributes = attributes or {}


if __name__ == "__main__":
    unittest.main()

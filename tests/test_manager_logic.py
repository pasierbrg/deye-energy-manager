from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "deye_energy_manager"


def _install_home_assistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    event = types.ModuleType("homeassistant.helpers.event")
    storage = types.ModuleType("homeassistant.helpers.storage")
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    components = types.ModuleType("homeassistant.components")
    components_number = types.ModuleType("homeassistant.components.number")
    components_select = types.ModuleType("homeassistant.components.select")
    components_switch = types.ModuleType("homeassistant.components.switch")
    config_entries = types.ModuleType("homeassistant.config_entries")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    restore_state = types.ModuleType("homeassistant.helpers.restore_state")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    entity_module = types.ModuleType("homeassistant.helpers.entity")

    core.HomeAssistant = object
    core.callback = lambda function: function
    core.ServiceCall = object
    core.SupportsResponse = object
    event.async_track_time_interval = lambda *_args, **_kwargs: lambda: None
    event.async_track_point_in_time = lambda *_args, **_kwargs: lambda: None
    event.async_track_state_change_event = lambda *_args, **_kwargs: lambda: None

    class Store:
        def __init__(self, *_args, **_kwargs):
            pass

    class NumberEntity:
        pass

    class SelectEntity:
        pass

    class SwitchEntity:
        pass

    class RestoreEntity:
        async def async_get_last_state(self):
            return None

    class AddEntitiesCallback:
        pass

    class ConfigEntry:
        pass

    class EntityRegistry:
        pass

    class DeviceInfo:
        pass

    class Entity:
        entity_id = None
        hass = None

        @property
        def name(self):
            return getattr(self, "_attr_name", None)

        def async_write_ha_state(self):
            if self.hass is None or self.entity_id is None:
                return
            self.hass.states.values[self.entity_id] = types.SimpleNamespace(
                entity_id=self.entity_id,
                state="on" if bool(getattr(self, "is_on", False)) else "off",
                attributes={"friendly_name": getattr(self, "_attr_name", None)},
            )

    storage.Store = Store
    dt.now = lambda: datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    components_number.NumberEntity = NumberEntity
    components_select.SelectEntity = SelectEntity
    components_switch.SwitchEntity = SwitchEntity
    restore_state.RestoreEntity = RestoreEntity
    entity_platform.AddEntitiesCallback = AddEntitiesCallback
    config_entries.ConfigEntry = ConfigEntry
    entity_registry.async_get = lambda *_args, **_kwargs: None
    device_registry.DeviceInfo = DeviceInfo
    entity_module.Entity = Entity

    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.core": core,
            "homeassistant.components": components,
            "homeassistant.components.number": components_number,
            "homeassistant.components.select": components_select,
            "homeassistant.components.switch": components_switch,
            "homeassistant.config_entries": config_entries,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.event": event,
            "homeassistant.helpers.storage": storage,
            "homeassistant.helpers.entity_platform": entity_platform,
            "homeassistant.helpers.restore_state": restore_state,
            "homeassistant.helpers.entity_registry": entity_registry,
            "homeassistant.helpers.device_registry": device_registry,
            "homeassistant.helpers.entity": entity_module,
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


_install_home_assistant_stubs()
package = types.ModuleType("custom_components.deye_energy_manager")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package
const = _load_module(f"{package.__name__}.const", PACKAGE / "const.py")
manager = _load_module(f"{package.__name__}.manager", PACKAGE / "manager.py")
manager.ha_now = lambda: datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
number = _load_module(f"{package.__name__}.number", PACKAGE / "number.py")
select_module = _load_module(f"{package.__name__}.select", PACKAGE / "select.py")
switch_module = _load_module(f"{package.__name__}.switch", PACKAGE / "switch.py")


class FakeState:
    def __init__(self, state, attributes=None, entity_id=""):
        self.entity_id = entity_id
        self.state = str(state)
        self.attributes = attributes or {}
        # Mirror the minimum timestamp contract of a real HA State. Individual
        # freshness tests may still add/advance ``last_reported`` explicitly.
        self.last_changed = manager.ha_now()
        self.last_updated = manager.ha_now()


class FakeStates:
    def __init__(self, values=None):
        self.values = values or {}
        for entity_id, state in self.values.items():
            state.entity_id = entity_id

    def get(self, entity_id):
        return self.values.get(entity_id)

    def async_all(self, domain=None):
        prefix = f"{domain}." if domain else ""
        return [state for entity_id, state in self.values.items() if entity_id.startswith(prefix)]


class FakeServices:
    def __init__(self, hass):
        self.hass = hass
        self.calls = []
        self.failures = []

    def ignore_once(self, domain, service, *, entity_id=None, option=None):
        self.failures.append({"domain": domain, "service": service, "entity_id": entity_id, "option": option, "remaining": 1, "ignore": True})

    def fail_once(self, domain, service, *, entity_id=None, option=None):
        self.failures.append(
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "option": option,
                "remaining": 1,
            }
        )

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, dict(data), blocking))
        for failure in self.failures:
            if failure["remaining"] <= 0:
                continue
            if failure["domain"] != domain or failure["service"] != service:
                continue
            if failure["entity_id"] is not None and data.get("entity_id") != failure["entity_id"]:
                continue
            if failure["option"] is not None and data.get("option") != failure["option"]:
                continue
            failure["remaining"] -= 1
            if failure.get("ignore"):
                return
            raise RuntimeError(f"Injected {domain}.{service} failure")

        entity_id = data.get("entity_id")
        if not entity_id:
            return
        if domain == "select" and service == "select_option":
            value = data["option"]
        elif domain == "number" and service == "set_value":
            value = data["value"]
        elif domain == "switch":
            value = "on" if service == "turn_on" else "off"
        elif domain == "time" and service == "set_value":
            value = data["time"]
        else:
            return
        self.hass.states.values[entity_id] = FakeState(value, entity_id=entity_id)


class FakeHass:
    def __init__(self, states):
        self.states = FakeStates(states)
        self.services = FakeServices(self)

    def async_create_task(self, coroutine):
        coroutine.close()
        return None


def make_runtime(soc="50", price="0.50", default_mode=None):
    states = {
        const.DEFAULT_WORK_MODE_SELECT: FakeState(const.MODE_ZERO_EXPORT),
        const.DEFAULT_MAX_SELL_POWER: FakeState("0"),
        const.DEFAULT_DISCHARGE_CURRENT: FakeState("0"),
        const.DEFAULT_CHARGE_CURRENT: FakeState("0"),
        const.DEFAULT_GRID_CHARGE_CURRENT: FakeState("0"),
    }
    for idx in range(1, 7):
        states[f"time.deye_inverter_time_of_use_{idx}_start"] = FakeState("00:00:00")
        states[f"number.deye_inverter_time_of_use_{idx}_soc"] = FakeState("20")
        states[f"switch.deye_inverter_time_of_use_{idx}_grid_charge"] = FakeState("off")
    if soc is not None:
        states[const.DEFAULT_BATTERY_SOC] = FakeState(soc)
    if price is not None:
        states[const.DEFAULT_PRICE_SENSOR] = FakeState(price)
    runtime = manager.DeyeEnergyManagerRuntime(
        hass=FakeHass(states),
        entry_id="test",
        data={
            const.CONF_WORK_MODE_SELECT: const.DEFAULT_WORK_MODE_SELECT,
            const.CONF_MAX_SELL_POWER_NUMBER: const.DEFAULT_MAX_SELL_POWER,
            const.CONF_DISCHARGE_CURRENT_NUMBER: const.DEFAULT_DISCHARGE_CURRENT,
            const.CONF_CHARGE_CURRENT_NUMBER: const.DEFAULT_CHARGE_CURRENT,
            const.CONF_GRID_CHARGE_CURRENT_NUMBER: const.DEFAULT_GRID_CHARGE_CURRENT,
            const.CONF_BATTERY_SOC_SENSOR: const.DEFAULT_BATTERY_SOC,
            const.CONF_PRICE_SENSOR: const.DEFAULT_PRICE_SENSOR,
            **{
                const.conf_tou_entity(idx, kind): entity_id
                for idx in range(1, 7)
                for kind, entity_id in (
                    ("start", f"time.deye_inverter_time_of_use_{idx}_start"),
                    ("soc", f"number.deye_inverter_time_of_use_{idx}_soc"),
                    ("grid", f"switch.deye_inverter_time_of_use_{idx}_grid_charge"),
                )
            },
        },
    )
    runtime.default_work_mode = default_mode or const.MODE_NORMAL_OPERATION
    runtime.default_sell_power = const.DEFAULT_INVERTER_MAX_POWER_W
    runtime.default_discharge_current = 120
    runtime.default_charge_current = 120
    runtime.default_grid_charge_current = 60
    # The regular fixture represents a configuration whose physical TOU SOC
    # values have already been confirmed. Dedicated migration coverage below
    # verifies the intentionally unconfirmed ``None`` state.
    for slot in runtime.slots.values():
        slot.tou_soc = 20
    return runtime


CONTROL_NUMBERS = {
    const.DEFAULT_MAX_SELL_POWER: const.DEFAULT_INVERTER_MAX_POWER_W,
    const.DEFAULT_DISCHARGE_CURRENT: 120,
    const.DEFAULT_CHARGE_CURRENT: 120,
    const.DEFAULT_GRID_CHARGE_CURRENT: 60,
}


def configure_selling_slot(runtime):
    runtime.scheduler_enabled = True
    active = runtime.slots[runtime.active_slot_key()]
    active.enabled = True
    active.mode = const.MODE_SELLING_FIRST
    active.sell_power = 5000
    active.discharge_current = 120
    # Provide a default physical TOU SOC so schedule apply tests are not blocked
    # by an unconfirmed SOC.  Tests that explicitly need tou_soc=None can reset it.
    active.tou_soc = 10
    return active


def control_number_calls(runtime):
    return [
        call
        for call in runtime.hass.services.calls
        if call[:2] == ("number", "set_value") and call[2].get("entity_id") in CONTROL_NUMBERS
    ]


class DataSourceQualityTests(unittest.TestCase):
    @staticmethod
    def _power(value, unit="W"):
        return FakeState(value, {"unit_of_measurement": unit})

    def test_load_power_remains_primary_and_phases_are_not_added_twice(self):
        runtime = make_runtime()
        runtime.hass.states.values.update({
            const.DEFAULT_LOAD_POWER_SENSOR: self._power(756),
            const.DEFAULT_LOAD_L1_POWER_SENSOR: self._power(44),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: self._power(535),
            const.DEFAULT_LOAD_L3_POWER_SENSOR: self._power(177),
        })
        reading = runtime.load_power_reading()
        self.assertEqual(reading["source"], "primary")
        self.assertEqual(reading["value"], 756)
        self.assertEqual(reading["phase_sum_w"], 756)

    def test_complete_load_phases_are_fallback_when_total_is_unavailable(self):
        runtime = make_runtime()
        runtime.hass.states.values.update({
            const.DEFAULT_LOAD_POWER_SENSOR: FakeState("unavailable", {"unit_of_measurement": "W"}),
            const.DEFAULT_LOAD_L1_POWER_SENSOR: self._power(100),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: self._power(200),
            const.DEFAULT_LOAD_L3_POWER_SENSOR: self._power(300),
        })
        reading = runtime.load_power_reading()
        self.assertEqual(reading["source"], "load_phases")
        self.assertEqual(reading["value"], 600)
        self.assertEqual(reading["quality"], "degraded")

    def test_missing_phase_prevents_phase_sum_fallback(self):
        runtime = make_runtime()
        runtime.hass.states.values.update({
            const.DEFAULT_LOAD_POWER_SENSOR: FakeState("unavailable", {"unit_of_measurement": "W"}),
            const.DEFAULT_LOAD_L1_POWER_SENSOR: self._power(100),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: self._power(200),
        })
        reading = runtime.load_power_reading()
        self.assertNotEqual(reading["source"], "load_phases")
        self.assertIsNone(reading["value"])

    def test_load_disagreement_reduces_quality_without_replacing_total(self):
        runtime = make_runtime()
        runtime.hass.states.values.update({
            const.DEFAULT_LOAD_POWER_SENSOR: self._power(1000),
            const.DEFAULT_LOAD_L1_POWER_SENSOR: self._power(100),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: self._power(100),
            const.DEFAULT_LOAD_L3_POWER_SENSOR: self._power(100),
        })
        reading = runtime.load_power_reading()
        self.assertEqual(reading["value"], 1000)
        self.assertEqual(reading["status"], "inconsistent")
        self.assertEqual(reading["quality"], "degraded")

    def test_direct_battery_power_wins_over_voltage_times_current(self):
        runtime = make_runtime()
        runtime.hass.states.values.update({
            const.DEFAULT_BATTERY_POWER_SENSOR: self._power(500),
            const.DEFAULT_BATTERY_BMS_VOLTAGE_SENSOR: FakeState(50, {"unit_of_measurement": "V"}),
            const.DEFAULT_BATTERY_CURRENT_SENSOR: FakeState(20, {"unit_of_measurement": "A"}),
        })
        reading = runtime.battery_power_reading()
        self.assertEqual(reading["source"], "primary")
        self.assertEqual(reading["value"], 500)

    def test_solarman_rejects_misleading_grid_total_and_uses_phase_sum(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_SOLARMAN
        runtime.data.update({
            const.CONF_GRID_POWER_SENSOR: const.DEFAULT_GRID_POWER_SENSOR,
            const.CONF_GRID_L1_POWER_SENSOR: const.DEFAULT_GRID_L1_POWER_SENSOR,
            const.CONF_GRID_L2_POWER_SENSOR: const.DEFAULT_GRID_L2_POWER_SENSOR,
            const.CONF_GRID_L3_POWER_SENSOR: const.DEFAULT_GRID_L3_POWER_SENSOR,
        })
        runtime.hass.states.values.update({
            const.DEFAULT_GRID_POWER_SENSOR: self._power(85),
            const.DEFAULT_GRID_L1_POWER_SENSOR: self._power(-1000),
            const.DEFAULT_GRID_L2_POWER_SENSOR: self._power(-991),
            const.DEFAULT_GRID_L3_POWER_SENSOR: self._power(-998),
        })

        reading = runtime.grid_power_reading()

        self.assertEqual(reading["source"], "grid_phases")
        self.assertEqual(reading["value"], -2989)
        self.assertEqual(runtime.normalized_grid_power(), -2989)
        self.assertEqual(reading["quality"], "degraded")

    def test_non_solarman_keeps_grid_total_but_marks_phase_disagreement(self):
        runtime = make_runtime()
        runtime.hass.states.values.update({
            const.DEFAULT_GRID_POWER_SENSOR: self._power(85),
            const.DEFAULT_GRID_L1_POWER_SENSOR: self._power(-1000),
            const.DEFAULT_GRID_L2_POWER_SENSOR: self._power(-991),
            const.DEFAULT_GRID_L3_POWER_SENSOR: self._power(-998),
        })

        reading = runtime.grid_power_reading()

        self.assertEqual(reading["value"], 85)
        self.assertEqual(reading["status"], "inconsistent")
        self.assertEqual(reading["quality"], "degraded")

    def test_daily_energy_value_normalizes_wh_to_kwh(self):
        runtime = make_runtime()
        entity_id = "sensor.solarman_daily_grid_export"
        runtime.hass.states.values[entity_id] = FakeState(
            600,
            {"unit_of_measurement": "Wh"},
            entity_id=entity_id,
        )

        self.assertAlmostEqual(runtime.daily_energy_value(entity_id), 0.6)

    def test_physical_tou_end_comes_from_next_actual_start(self):
        runtime = make_runtime()
        starts = ("00:00:00", "06:00:00", "09:00:00", "13:00:00", "16:00:00", "20:00:00")
        for index, value in enumerate(starts, start=1):
            runtime.hass.states.values[f"time.deye_inverter_time_of_use_{index}_start"] = FakeState(value)

        rows = runtime.physical_tou_snapshot()

        self.assertEqual(
            [row["actual_end"][:5] for row in rows],
            ["06:00", "09:00", "13:00", "16:00", "20:00", "00:00"],
        )

    def test_daily_export_counter_is_authoritative_for_current_day_energy(self):
        runtime = make_runtime()
        entity_id = "sensor.solarman_daily_grid_export"
        runtime.data[const.CONF_DAILY_ENERGY_SOLD_SENSOR] = entity_id
        runtime.hass.states.values[entity_id] = FakeState(
            0.60,
            {"unit_of_measurement": "kWh"},
            entity_id=entity_id,
        )
        runtime.sales_stats = runtime.empty_sales_stats()
        runtime.sales_stats["hourly"]["12"] = {"kwh": 0.02, "value": 0.01}

        runtime.refresh_sales_totals()

        self.assertEqual(runtime.sold_energy_today, 0.6)
        self.assertEqual(runtime.sold_value_today, 0.01)
        self.assertEqual(runtime.data_quality["sales_today"]["energy_source"], "daily_export_counter")
        self.assertEqual(runtime.data_quality["sales_today"]["difference_kwh"], 0.58)

    def test_hourly_price_parser_preserves_zero_and_negative_values(self):
        runtime = make_runtime()
        entity_id = "sensor.test_hourly_prices"
        runtime.hass.states.values[entity_id] = FakeState(
            "unavailable",
            {
                "prices": [
                    {"hour": "01:00", "price": 0.0},
                    {"hour": "02:00", "price": -0.25},
                    {"hour": "03:00", "price": None},
                ]
            },
            entity_id=entity_id,
        )
        self.assertEqual({1: 0.0, 2: -0.25}, runtime.price_map(entity_id))


class SafetyTests(unittest.TestCase):
    def test_default_control_confirmation_window_is_30_seconds(self):
        self.assertEqual(make_runtime().control_confirmation_timeout, 30.0)

    def test_required_entities_complete_includes_battery_soc(self):
        runtime = make_runtime()
        self.assertTrue(runtime.required_entities_complete)

    def test_required_entities_complete_false_when_soc_missing(self):
        runtime = make_runtime(soc=None)
        self.assertFalse(runtime.required_entities_complete)
        self.assertTrue(runtime.data_available)

    def test_required_entities_complete_false_when_charge_current_missing(self):
        runtime = make_runtime()
        del runtime.hass.states.values[const.DEFAULT_CHARGE_CURRENT]
        self.assertFalse(runtime.required_entities_complete)
        self.assertFalse(runtime.data_available)

    def test_read_only_provider_fails_closed_even_with_old_control_entities(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON

        self.assertFalse(runtime.data_available)
        self.assertFalse(runtime.required_entities_complete)
        with self.assertRaisesRegex(ValueError, "does not support inverter control"):
            asyncio.run(runtime.async_set_work_mode(const.MODE_SELLING_FIRST))
        self.assertEqual(runtime.hass.services.calls, [])

    def test_read_only_provider_rejects_plan_before_first_write(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON

        with self.assertRaisesRegex(ValueError, "does not support inverter control"):
            runtime._validate_control_plan(
                const.MODE_NORMAL_OPERATION,
                0.0,
                0.0,
                0.0,
                0.0,
            )
        self.assertEqual(runtime.hass.services.calls, [])

    def test_missing_soc_blocks_selling(self):
        runtime = make_runtime(soc=None)
        self.assertTrue(runtime.data_available)
        self.assertFalse(runtime.soc_ok)
        self.assertFalse(runtime.sell_allowed)

    def test_unavailable_and_non_finite_soc_block_selling(self):
        for value in ("unavailable", "unknown", "nan", "inf"):
            with self.subTest(value=value):
                runtime = make_runtime(soc=value)
                self.assertFalse(runtime.soc_ok)
                self.assertFalse(runtime.sell_allowed)

    def test_price_guard_fails_closed(self):
        runtime = make_runtime(price=None)
        runtime.price_guard_enabled = True
        runtime.price_sell_threshold = 0.2
        self.assertTrue(runtime.data_available)
        self.assertFalse(runtime.price_ok)
        self.assertFalse(runtime.sell_allowed)

    def test_disabled_price_guard_does_not_require_price(self):
        runtime = make_runtime(price=None)
        runtime.price_guard_enabled = False
        runtime.price_sell_threshold = 0.2
        self.assertTrue(runtime.data_available)
        self.assertTrue(runtime.price_ok)

    def test_slot_price_limit_is_enforced_without_global_guard(self):
        runtime = make_runtime(price=None)
        runtime.scheduler_enabled = True
        runtime.price_guard_enabled = False
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.min_sell_price = 0.2
        self.assertTrue(runtime.data_available)
        self.assertFalse(runtime.price_ok)


class NotifyUpdateTests(unittest.TestCase):
    def test_tick_notifies_on_stats_change_with_active_slot(self):
        runtime = make_runtime()
        runtime.scheduler_enabled = True
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_NORMAL_OPERATION
        active.physical_work_mode = const.MODE_ZERO_EXPORT
        active.sell_power = 0
        active.discharge_current = 0
        active.charge_current = 0
        active.grid_charge_current = 0
        active.tou_soc = 20
        counts = []
        original_notify = runtime.notify_update

        def counting_notify():
            counts.append(None)
            original_notify()

        runtime.notify_update = counting_notify
        runtime.sold_energy_today = 1.0
        runtime.sold_value_today = 1.0
        asyncio.run(runtime._async_tick_impl())
        self.assertGreaterEqual(len(counts), 1)


class MappingAndTransactionTests(unittest.TestCase):
    def assert_safe_defaults(self, runtime, expected_mode=const.MODE_ZERO_EXPORT):
        calls = control_number_calls(runtime)
        self.assertTrue(calls)
        for entity_id, expected in CONTROL_NUMBERS.items():
            entity_calls = [call for call in calls if call[2]["entity_id"] == entity_id]
            self.assertTrue(entity_calls, entity_id)
            self.assertEqual(entity_calls[-1][2]["value"], expected, entity_id)
        self.assertFalse(
            any(call[2]["value"] == 0 for call in calls),
            "Control entities must never be automatically zeroed",
        )
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertTrue(select_calls)
        self.assertEqual(select_calls[-1][2]["option"], expected_mode)


    def test_stop_sell_applies_defaults_and_remains_latched(self):
        runtime = make_runtime()
        asyncio.run(runtime.async_request_stop())
        self.assertEqual(runtime.control_mode, "Stop Sell")
        self.assert_safe_defaults(runtime)
        self.assertEqual(runtime.default_sell_power, const.DEFAULT_INVERTER_MAX_POWER_W)
        self.assertEqual(runtime.default_discharge_current, 120)
        self.assertEqual(runtime.default_charge_current, 120)
        self.assertEqual(runtime.default_grid_charge_current, 60)
        runtime.hass.services.calls.clear()
        asyncio.run(runtime.async_tick())
        self.assertEqual(runtime.control_mode, "Stop Sell")
        self.assert_safe_defaults(runtime)

    def test_emergency_stop_latches_stopped_control_mode(self):
        runtime = make_runtime()
        runtime.scheduler_enabled = True
        asyncio.run(runtime.async_emergency_stop())
        self.assertTrue(runtime.emergency_stop)
        self.assertEqual(runtime.control_mode, "Stop Sell")
        self.assert_safe_defaults(runtime)
        runtime.emergency_stop = False
        runtime.hass.services.calls.clear()
        asyncio.run(runtime.async_tick())
        self.assertEqual(runtime.control_mode, "Stop Sell")
        self.assert_safe_defaults(runtime)

    def test_safe_defaults_preserve_a_configured_selling_first_mode(self):
        runtime = make_runtime(default_mode=const.MODE_SELLING_FIRST)
        asyncio.run(runtime.async_emergency_stop())
        self.assert_safe_defaults(runtime, "Selling First")

    def test_safe_defaults_preserve_zero_export_to_ct(self):
        runtime = make_runtime(default_mode=const.MODE_NORMAL_OPERATION)
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        asyncio.run(runtime.async_emergency_stop())
        self.assert_safe_defaults(runtime, const.MODE_ZERO_EXPORT_CT)

    def test_user_selected_zero_defaults_are_respected(self):
        runtime = make_runtime()
        runtime.default_sell_power = 0
        runtime.default_discharge_current = 0
        runtime.default_charge_current = 0
        runtime.default_grid_charge_current = 0
        asyncio.run(runtime.async_request_stop())
        calls = control_number_calls(runtime)
        self.assertEqual({call[2]["value"] for call in calls}, {0})

    def test_partial_safe_default_failure_is_reported_as_critical(self):
        runtime = make_runtime(default_mode=const.MODE_NORMAL_OPERATION)
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        runtime.hass.services.fail_once(
            "number",
            "set_value",
            entity_id=const.DEFAULT_CHARGE_CURRENT,
        )
        self.assertFalse(asyncio.run(runtime.async_apply_safe_defaults("Test awarii")))
        self.assertIn("KRYTYCZNY", runtime.last_error)
        self.assertIn("Maximum Battery Charge Current", runtime.last_error)
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertTrue(select_calls)
        self.assertTrue(all(call[2]["option"] == const.MODE_ZERO_EXPORT_CT for call in select_calls))

    def test_missing_and_unavailable_soc_apply_defaults(self):
        for soc in (None, "unavailable", "unknown"):
            with self.subTest(soc=soc):
                runtime = make_runtime(soc=soc)
                configure_selling_slot(runtime)
                self.assertFalse(asyncio.run(runtime.async_apply_targets()))
                self.assert_safe_defaults(runtime)

    def test_price_error_applies_defaults(self):
        runtime = make_runtime(price=None)
        runtime.price_guard_enabled = True
        runtime.price_sell_threshold = 0.2
        configure_selling_slot(runtime)
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assert_safe_defaults(runtime)

    def test_low_slot_soc_blocks_sale_without_schedule_error(self):
        runtime = make_runtime(soc="40")
        active = configure_selling_slot(runtime)
        active.minimum_sell_soc = 45

        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ ZABLOKOWANA")
        self.assertIn("SOC", runtime.decision_reason)
        self.assertEqual(runtime.last_schedule_attempt["status"], "applied")
        self.assertEqual(runtime.last_error, "")
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state,
            const.MODE_ZERO_EXPORT,
        )
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_MAX_SELL_POWER).state,
            str(runtime.default_sell_power),
        )

        calls_after_first_block = list(runtime.hass.services.calls)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.services.calls, calls_after_first_block)
        self.assertEqual(runtime.last_schedule_attempt["status"], "blocked")
        self.assertIn("SOC", runtime.last_action)

    def test_sale_stops_at_35_but_physical_tou_soc_remains_15(self):
        runtime = make_runtime(soc="35")
        active = configure_selling_slot(runtime)
        active.minimum_sell_soc = 35
        active.tou_soc = 15

        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ ZABLOKOWANA")
        self.assertEqual(runtime.target_mode, runtime.default_work_mode)
        # After 5A.1 physical TOU SOC is always tou_soc, never minimum_sell_soc.
        self.assertEqual(runtime.physical_tou_soc_for_slot(runtime.active_slot_key()), 15)
        self.assertIn("osiągnął", runtime.decision_reason)

    def test_low_slot_price_blocks_sale_without_schedule_error(self):
        runtime = make_runtime(price="0.15")
        active = configure_selling_slot(runtime)
        active.min_sell_price = 0.20

        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ ZABLOKOWANA")
        self.assertIn("cena", runtime.decision_reason)
        self.assertEqual(runtime.last_schedule_attempt["status"], "applied")
        self.assertEqual(runtime.last_error, "")
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state,
            const.MODE_ZERO_EXPORT,
        )

    def test_direct_selling_is_blocked_without_soc(self):
        runtime = make_runtime(soc=None)
        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 0))
        self.assert_safe_defaults(runtime)

    def test_apply_settings_uses_custom_grid_charge_current(self):
        runtime = make_runtime()
        runtime.default_grid_charge_current = 30
        asyncio.run(runtime.async_apply_settings(const.MODE_NORMAL_OPERATION, 0, 120, 120, 60))
        grid_calls = [call for call in runtime.hass.services.calls if call[:2] == ("number", "set_value") and call[2].get("entity_id") == const.DEFAULT_GRID_CHARGE_CURRENT]
        self.assertTrue(grid_calls)
        self.assertEqual(grid_calls[-1][2]["value"], 60)

    def test_apply_settings_uses_default_grid_charge_current_when_omitted(self):
        runtime = make_runtime()
        runtime.default_grid_charge_current = 45
        asyncio.run(runtime.async_apply_settings(const.MODE_NORMAL_OPERATION, 0, 120, 120))
        grid_calls = [call for call in runtime.hass.services.calls if call[:2] == ("number", "set_value") and call[2].get("entity_id") == const.DEFAULT_GRID_CHARGE_CURRENT]
        self.assertTrue(grid_calls)
        self.assertEqual(grid_calls[-1][2]["value"], 45)

    def test_more_than_six_segments_is_rejected(self):
        runtime = make_runtime()
        for index, slot in enumerate(runtime.slots.values()):
            slot.enabled = True
            slot.mode = const.MODE_CHARGE if index % 2 else const.MODE_SELLING_FIRST
            # After 5A.1 the physical key is (tou_soc, grid_charge).  Make Charge
            # and Selling slots alternate on both values to create 24 ranges.
            slot.tou_soc = 100 if slot.mode == const.MODE_CHARGE else 20
            slot.minimum_sell_soc = 20
        self.assertTrue(runtime.mapping_error)
        self.assertGreater(len(runtime._tou_mapping.slots), 6)
        calls_before = list(runtime.hass.services.calls)
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.services.calls, calls_before)
        self.assertIn("maksymalnie 6", runtime.last_error)

    def test_invalid_patch_rolls_back_and_keeps_safe_mode(self):
        runtime = make_runtime()
        updates = []
        for index, slot_key in enumerate(list(runtime.slots)[:8]):
            updates.append(
                {
                    "slot_key": slot_key,
                    "enabled": True,
                    "mode": const.MODE_CHARGE if index % 2 else const.MODE_SELLING_FIRST,
                }
            )
        calls_before = list(runtime.hass.services.calls)
        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_apply_schedule_patch(updates))
        self.assertTrue(all(not slot.enabled for slot in runtime.slots.values()))
        self.assertEqual(runtime.hass.services.calls, calls_before)

    def test_tou_write_error_rolls_back_without_safe_defaults(self):
        runtime = make_runtime(default_mode=const.MODE_NORMAL_OPERATION)
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        configure_selling_slot(runtime)
        calls_before = list(runtime.hass.services.calls)
        runtime.hass.services.fail_once("time", "set_value")
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        # A TOU write failure that rolls back must not apply safe defaults.
        self.assertFalse(any(
            call[0] == "select" and call[1] == "select_option"
            and call[2].get("entity_id") == const.DEFAULT_WORK_MODE_SELECT
            and call[2].get("option") == const.MODE_ZERO_EXPORT_CT
            for call in runtime.hass.services.calls[len(calls_before):]
        ))
        self.assertIn("Przywrócono poprzednie ustawienia", runtime.last_error)

    def test_numeric_write_error_restores_defaults(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.services.fail_once(
            "number",
            "set_value",
            entity_id=const.DEFAULT_MAX_SELL_POWER,
        )
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assert_safe_defaults(runtime)

    def test_target_mode_error_restores_defaults(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.services.fail_once(
            "select",
            "select_option",
            option="Selling First",
        )
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assert_safe_defaults(runtime)

    def test_schedule_patch_saves_immediately_and_background_failure_restores_defaults(self):
        runtime = make_runtime()
        slot_key = runtime.active_slot_key()
        runtime.hass.services.fail_once(
            "number",
            "set_value",
            entity_id=const.DEFAULT_MAX_SELL_POWER,
        )
        asyncio.run(
            runtime.async_apply_schedule_patch(
                [
                    {
                        "slot_key": slot_key,
                        "enabled": True,
                        "mode": const.MODE_SELLING_FIRST,
                        "sell_power": 5000,
                        "discharge_current": 120,
                    }
                ]
            )
        )
        self.assertTrue(runtime.slots[slot_key].enabled)
        self.assertEqual(runtime.slots[slot_key].mode, const.MODE_SELLING_FIRST)
        self.assertEqual(runtime.hass.services.calls, [])

        asyncio.run(runtime._async_reconcile_schedule_changes())

        # A physical failure no longer discards the user's saved schedule.
        # The existing safety path still restores inverter defaults.
        self.assertTrue(runtime.slots[slot_key].enabled)
        self.assertEqual(runtime.slots[slot_key].mode, const.MODE_SELLING_FIRST)
        self.assert_safe_defaults(runtime)

    def test_schedule_patch_does_not_block_on_full_tick(self):
        runtime = make_runtime()
        slot_key = next(key for key in runtime.slots if key != runtime.active_slot_key())
        tick_calls = 0

        async def tracked_tick():
            nonlocal tick_calls
            tick_calls += 1
            return True

        runtime._async_tick_impl = tracked_tick
        asyncio.run(
            runtime.async_apply_schedule_patch(
                [{"slot_key": slot_key, "sell_power": 3456}]
            )
        )

        self.assertEqual(runtime.slots[slot_key].sell_power, 3456)
        self.assertEqual(tick_calls, 0)
        self.assertTrue(runtime._schedule_reconcile_requested)

    def test_background_schedule_reconciliation_coalesces_rapid_requests(self):
        runtime = make_runtime()

        async def scenario():
            tick_calls = 0

            async def tracked_tick():
                nonlocal tick_calls
                tick_calls += 1
                return True

            runtime._async_tick_impl = tracked_tick
            runtime.hass.async_create_task = asyncio.create_task
            runtime._schedule_schedule_reconciliation()
            first_task = runtime._schedule_reconcile_task
            runtime._schedule_schedule_reconciliation()

            self.assertIs(first_task, runtime._schedule_reconcile_task)
            await first_task
            self.assertEqual(tick_calls, 1)
            self.assertIsNone(runtime._schedule_reconcile_task)
            self.assertFalse(runtime._schedule_reconcile_requested)

        asyncio.run(scenario())

    def test_selling_update_writes_numbers_before_target_mode(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(select_calls[-1][2]["option"], "Selling First")
        self.assertFalse(any(call[2]["value"] == 0 for call in control_number_calls(runtime)))
        ordered_control_calls = [
            call
            for call in runtime.hass.services.calls
            if call[:2] in (("select", "select_option"), ("number", "set_value"))
            and (
                call[2].get("entity_id") == const.DEFAULT_WORK_MODE_SELECT
                or call[2].get("entity_id") in CONTROL_NUMBERS
            )
        ]
        self.assertEqual(ordered_control_calls[-1][2]["option"], "Selling First")
        self.assertTrue(all(call[:2] == ("number", "set_value") for call in ordered_control_calls[:-1]))

    def test_delayed_work_mode_waits_without_rewriting_and_confirms(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.services.ignore_once(
            "select", "select_option", entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option="Selling First",
        )
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(len(select_calls), 1)
        self.assertEqual(runtime.last_schedule_attempt["status"], "pending")
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ AKTYWNA")
        # Deye may publish the selected mode later.  A fast confirmation
        # recheck must only read the first transaction, never write it again.
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState(
            "Selling First",
            entity_id=const.DEFAULT_WORK_MODE_SELECT,
        )
        asyncio.run(runtime._async_recheck_pending_control())
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(len(select_calls), 1)
        self.assertEqual(runtime.last_schedule_attempt["status"], "applied")

    def test_failed_schedule_is_reported_instead_of_selling_active(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.control_confirmation_timeout = 0
        runtime.hass.services.ignore_once("select", "select_option", entity_id=const.DEFAULT_WORK_MODE_SELECT, option="Selling First")
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "BŁĄD APLIKACJI HARMONOGRAMU")
        self.assertEqual(runtime.last_schedule_attempt["status"], "failed")
        self.assertIn("System Work Mode", runtime.last_schedule_attempt["message"])

    def test_resume_manager_enables_schedule_without_legacy_charge_scheduler(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.control_mode = "Stop Sell"
        runtime.scheduler_enabled = False
        asyncio.run(runtime.async_resume_manager())
        self.assertEqual(runtime.control_mode, "Schedule")
        self.assertTrue(runtime.scheduler_enabled)
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state, "Selling First")

    def test_direct_settings_do_not_use_transitional_zeroes(self):
        runtime = make_runtime()
        asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120))
        self.assertFalse(any(call[2]["value"] == 0 for call in control_number_calls(runtime)))
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(len(select_calls), 1)
        self.assertEqual(select_calls[-1][2]["option"], "Selling First")

    def test_restore_defaults_uses_exact_mode_after_all_numeric_values(self):
        for default_mode, physical_variant, expected_option in (
            (const.MODE_NORMAL_OPERATION, const.MODE_ZERO_EXPORT, const.MODE_ZERO_EXPORT),
            (const.MODE_NORMAL_OPERATION, const.MODE_ZERO_EXPORT_CT, const.MODE_ZERO_EXPORT_CT),
            (const.MODE_SELLING_FIRST, None, "Selling First"),
        ):
            with self.subTest(mode=default_mode, physical=physical_variant):
                runtime = make_runtime(default_mode=default_mode)
                if physical_variant:
                    runtime.normal_profile_physical_work_mode = physical_variant
                runtime.scheduler_enabled = True

                asyncio.run(runtime.async_restore_defaults())

                ordered_control_calls = [
                    call
                    for call in runtime.hass.services.calls
                    if call[:2] in (("select", "select_option"), ("number", "set_value"))
                    and (
                        call[2].get("entity_id") == const.DEFAULT_WORK_MODE_SELECT
                        or call[2].get("entity_id") in CONTROL_NUMBERS
                    )
                ]
                self.assertEqual(
                    [call[2]["entity_id"] for call in ordered_control_calls[:-1]],
                    list(CONTROL_NUMBERS),
                )
                self.assertEqual(
                    [call[2]["value"] for call in ordered_control_calls[:-1]],
                    list(CONTROL_NUMBERS.values()),
                )
                self.assertEqual(ordered_control_calls[-1][2]["option"], expected_option)
                self.assertFalse(runtime.scheduler_enabled)
                self.assertEqual(runtime.last_error, "")

    def test_restore_defaults_raises_when_full_set_is_not_confirmed(self):
        runtime = make_runtime(default_mode=const.MODE_NORMAL_OPERATION)
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        runtime.hass.services.fail_once(
            "number",
            "set_value",
            entity_id=const.DEFAULT_CHARGE_CURRENT,
        )

        with self.assertRaisesRegex(RuntimeError, "KRYTYCZNY"):
            asyncio.run(runtime.async_restore_defaults())

        self.assertIn("Maximum Battery Charge Current", runtime.last_error)
        self.assertNotEqual(runtime.last_error, "")


class ApplySettingsTransactionTests(unittest.TestCase):
    @staticmethod
    async def _run_under_fake_time(runtime, coro, state_restorer):
        """Run coroutine with patched loop.time() and manager.asyncio.sleep.

        ``state_restorer`` receives the fake monotonic time after each sleep.
        """
        fake_time = [0.0]
        loop = asyncio.get_running_loop()
        real_time = loop.time
        real_sleep = manager.asyncio.sleep

        async def fake_sleep(delay, result=None):
            fake_time[0] += delay
            state_restorer(fake_time[0])
            await real_sleep(0)
            return result

        with mock.patch.object(loop, "time", side_effect=lambda: fake_time[0]):
            with mock.patch.object(manager.asyncio, "sleep", fake_sleep):
                try:
                    return await coro
                finally:
                    loop.time = real_time

    def test_apply_settings_confirms_immediately_when_values_match(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState("Selling First")
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState("5000")
        runtime.hass.states.values[const.DEFAULT_DISCHARGE_CURRENT] = FakeState("120")
        runtime.hass.states.values[const.DEFAULT_CHARGE_CURRENT] = FakeState("120")
        runtime.hass.states.values[const.DEFAULT_GRID_CHARGE_CURRENT] = FakeState("60")

        asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60))

        self.assertEqual(runtime.last_action, "Zastosowano ustawienia bezpośrednie")
        self.assertEqual(runtime.last_error, "")

    def test_apply_settings_rejects_unreadable_snapshot_entities(self):
        runtime = make_runtime()
        # A non-numeric number state is still "available" for sell_allowed, but
        # the snapshot parser cannot read it, so the transaction aborts early.
        runtime.hass.states.values[const.DEFAULT_CHARGE_CURRENT] = FakeState("not_a_number")

        with self.assertRaisesRegex(RuntimeError, "snapshotu"):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60))

    def test_apply_settings_rolls_back_on_write_failure(self):
        runtime = make_runtime()
        runtime.hass.services.fail_once(
            "number", "set_value", entity_id=const.DEFAULT_CHARGE_CURRENT
        )
        original_values = {
            const.DEFAULT_WORK_MODE_SELECT: str(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state),
            const.DEFAULT_MAX_SELL_POWER: str(runtime.hass.states.get(const.DEFAULT_MAX_SELL_POWER).state),
            const.DEFAULT_DISCHARGE_CURRENT: str(runtime.hass.states.get(const.DEFAULT_DISCHARGE_CURRENT).state),
            const.DEFAULT_CHARGE_CURRENT: str(runtime.hass.states.get(const.DEFAULT_CHARGE_CURRENT).state),
            const.DEFAULT_GRID_CHARGE_CURRENT: str(runtime.hass.states.get(const.DEFAULT_GRID_CHARGE_CURRENT).state),
        }

        with self.assertRaises(RuntimeError):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60))

        self.assertIn("Wycofano zmiany", runtime.last_action)
        for entity_id, expected in original_values.items():
            actual = runtime.hass.states.values[entity_id].state
            if entity_id == const.DEFAULT_WORK_MODE_SELECT:
                self.assertEqual(str(actual), expected, entity_id)
            else:
                self.assertAlmostEqual(float(actual), float(expected), places=3, msg=entity_id)

    def test_apply_settings_rolls_back_on_confirmation_timeout(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0
        # Prevent the work mode write from updating the fake state so confirmation
        # fails immediately within the zero-second window.
        runtime.hass.services.ignore_once(
            "select", "select_option", entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option="Selling First",
        )
        original_values = {
            const.DEFAULT_WORK_MODE_SELECT: str(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state),
            const.DEFAULT_MAX_SELL_POWER: str(runtime.hass.states.get(const.DEFAULT_MAX_SELL_POWER).state),
            const.DEFAULT_DISCHARGE_CURRENT: str(runtime.hass.states.get(const.DEFAULT_DISCHARGE_CURRENT).state),
            const.DEFAULT_CHARGE_CURRENT: str(runtime.hass.states.get(const.DEFAULT_CHARGE_CURRENT).state),
            const.DEFAULT_GRID_CHARGE_CURRENT: str(runtime.hass.states.get(const.DEFAULT_GRID_CHARGE_CURRENT).state),
        }

        with self.assertRaisesRegex(RuntimeError, "Niepotwierdzone ustawienia"):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60))

        self.assertIn("Wycofano zmiany", runtime.last_action)
        for entity_id, expected in original_values.items():
            actual = runtime.hass.states.values[entity_id].state
            if entity_id == const.DEFAULT_WORK_MODE_SELECT:
                self.assertEqual(str(actual), expected, entity_id)
            else:
                self.assertAlmostEqual(float(actual), float(expected), places=3, msg=entity_id)

    def test_rollback_uses_control_confirmation_timeout(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 7.0

        snapshot, _ = runtime._control_entities_to_write(const.MODE_SELLING_FIRST)
        # Put wrong values on the entities so rollback has something to restore.
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState("Selling First")
        for entity_id in CONTROL_NUMBERS:
            runtime.hass.states.values[entity_id] = FakeState("9999")

        # Ignore rollback writes so readback lags and confirmation loop is exercised.
        for entity_id in CONTROL_NUMBERS:
            runtime.hass.services.ignore_once("number", "set_value", entity_id=entity_id)
        runtime.hass.services.ignore_once(
            "select", "select_option",
            entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option=snapshot[const.DEFAULT_WORK_MODE_SELECT][1],
        )

        restored = [False]

        def restore_states(fake_time):
            if not restored[0] and fake_time > 5.5:
                runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState(
                    snapshot[const.DEFAULT_WORK_MODE_SELECT][1]
                )
                for entity_id in CONTROL_NUMBERS:
                    runtime.hass.states.values[entity_id] = FakeState(snapshot[entity_id][1])
                restored[0] = True

        async def _scenario():
            return await self._run_under_fake_time(
                runtime, runtime._async_rollback_control_values(snapshot), restore_states
            )

        self.assertTrue(asyncio.run(_scenario()))

    def test_delayed_confirmation_succeeds_without_rewriting(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0.5

        # Ignore the real writes so states lag and confirmation loop is needed.
        for entity_id in CONTROL_NUMBERS:
            runtime.hass.services.ignore_once("number", "set_value", entity_id=entity_id)
        runtime.hass.services.ignore_once(
            "select", "select_option",
            entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option="Selling First",
        )

        expected = {
            const.DEFAULT_WORK_MODE_SELECT: "Selling First",
            const.DEFAULT_MAX_SELL_POWER: "5000",
            const.DEFAULT_DISCHARGE_CURRENT: "120",
            const.DEFAULT_CHARGE_CURRENT: "120",
            const.DEFAULT_GRID_CHARGE_CURRENT: "60",
        }

        def restore_states(fake_time):
            if fake_time > 0.2:
                for entity_id, value in expected.items():
                    runtime.hass.states.values[entity_id] = FakeState(value, entity_id=entity_id)

        async def _scenario():
            await self._run_under_fake_time(
                runtime,
                runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60),
                restore_states,
            )

        asyncio.run(_scenario())

        self.assertEqual(runtime.last_action, "Zastosowano ustawienia bezpośrednie")
        self.assertEqual(runtime.last_error, "")
        for entity_id in CONTROL_NUMBERS:
            calls = [
                c for c in runtime.hass.services.calls
                if c[:2] == ("number", "set_value") and c[2].get("entity_id") == entity_id
            ]
            self.assertEqual(len(calls), 1, entity_id)
        mode_calls = [
            c for c in runtime.hass.services.calls
            if c[:2] == ("select", "select_option")
            and c[2].get("entity_id") == const.DEFAULT_WORK_MODE_SELECT
        ]
        self.assertEqual(len(mode_calls), 1)

    def test_incomplete_rollback_triggers_safe_defaults(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0.5

        # Ignore the initial work mode write so the confirmation loop fails and
        # triggers rollback; number writes still update states so we can observe
        # partial restoration.
        runtime.hass.services.ignore_once(
            "select", "select_option",
            entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option="Selling First",
        )

        original_restore = runtime._async_restore_raw_entity

        async def failing_restore(entity_id: str, raw_value: str) -> None:
            if entity_id == const.DEFAULT_CHARGE_CURRENT:
                raise RuntimeError("Injected rollback failure for Maximum Battery Charge Current")
            await original_restore(entity_id, raw_value)

        runtime._async_restore_raw_entity = failing_restore

        with self.assertRaises(RuntimeError):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60))

        self.assertIn("Zastosowano ustawienia domyślne", runtime.last_action)
        self.assertIn("Maximum Battery Charge Current", runtime.last_error)
        # Entities restored before the failing one received rollback commands.
        max_sell_rollback = [
            c for c in runtime.hass.services.calls
            if c[:2] == ("number", "set_value")
            and c[2].get("entity_id") == const.DEFAULT_MAX_SELL_POWER
            and c[2].get("value") == 0
        ]
        discharge_rollback = [
            c for c in runtime.hass.services.calls
            if c[:2] == ("number", "set_value")
            and c[2].get("entity_id") == const.DEFAULT_DISCHARGE_CURRENT
            and c[2].get("value") == 0
        ]
        charge_rollback = [
            c for c in runtime.hass.services.calls
            if c[:2] == ("number", "set_value")
            and c[2].get("entity_id") == const.DEFAULT_CHARGE_CURRENT
            and c[2].get("value") == 0
        ]
        self.assertTrue(max_sell_rollback)
        self.assertTrue(discharge_rollback)
        self.assertFalse(charge_rollback)

    def test_emergency_stop_aborts_pending_confirmation(self):
        runtime = make_runtime()
        original_wait = runtime._async_wait_for_control_confirmation

        async def _wait_with_emergency(*args, **kwargs):
            runtime.emergency_stop = True
            return await original_wait(*args, **kwargs)

        runtime._async_wait_for_control_confirmation = _wait_with_emergency

        with self.assertRaisesRegex(RuntimeError, "zatrzymanie awaryjne"):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60))

        self.assertTrue(runtime.emergency_stop)

    def test_real_emergency_stop_during_confirmation(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 10.0

        # Ignore writes so async_apply_settings stays in the confirmation loop.
        for entity_id in CONTROL_NUMBERS:
            runtime.hass.services.ignore_once("number", "set_value", entity_id=entity_id)
        runtime.hass.services.ignore_once(
            "select", "select_option",
            entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option="Selling First",
        )

        async def _scenario():
            apply_task = asyncio.create_task(
                runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60)
            )
            await asyncio.sleep(0.1)
            self.assertFalse(runtime.emergency_stop)
            stop_task = asyncio.create_task(runtime.async_emergency_stop())
            results = await asyncio.gather(apply_task, stop_task, return_exceptions=True)
            return results

        results = asyncio.run(_scenario())
        apply_result = results[0]

        self.assertIsInstance(apply_result, RuntimeError)
        self.assertIn("zatrzymanie awaryjne", str(apply_result).lower())
        self.assertTrue(runtime.emergency_stop)
        self.assertEqual(runtime.control_mode, "Stop Sell")
        # async_emergency_stop() applied safe defaults exactly once.
        self.assertIn("Zastosowano ustawienia domyślne", runtime.last_action)
        self.assertIn("Zatrzymanie awaryjne", runtime.last_error)

    def test_emergency_stop_sets_flag_before_acquiring_lock(self):
        runtime = make_runtime()

        async def _hold_lock():
            async with runtime._operation_lock:
                # Give async_emergency_stop time to set the flag while blocked.
                await asyncio.sleep(0.1)
                self.assertTrue(runtime.emergency_stop)

        async def _main():
            await asyncio.gather(_hold_lock(), runtime.async_emergency_stop())

        asyncio.run(_main())
        self.assertTrue(runtime.emergency_stop)
        self.assertEqual(runtime.control_mode, "Stop Sell")

    def test_cancellation_performs_bounded_cleanup_and_leaves_no_task(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0.1

        # Ignore writes so async_apply_settings stays in the confirmation loop.
        for entity_id in CONTROL_NUMBERS:
            runtime.hass.services.ignore_once("number", "set_value", entity_id=entity_id)
        runtime.hass.services.ignore_once(
            "select", "select_option",
            entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option="Selling First",
        )

        async def _scenario():
            apply_task = asyncio.create_task(
                runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120, 60)
            )
            await asyncio.sleep(0.05)
            apply_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await apply_task
            # Give cleanup a moment to finish.
            await asyncio.sleep(0.05)

        asyncio.run(_scenario())

        self.assertIsNone(runtime._rollback_task)
        self.assertNotIn("Wycofano zmiany", runtime.last_action)
        self.assertNotIn("Zastosowano ustawienia domyślne", runtime.last_action)


class GridAndSlotSafetyTests(unittest.TestCase):
    def configure_charge_slot(self, runtime, grid: bool):
        runtime.scheduler_enabled = True
        runtime.charge_profile_charge_current = 120
        runtime.charge_profile_discharge_current = 120
        runtime.charge_profile_grid_charge_current = 60
        runtime.charge_profile_target_soc = 90
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_CHARGE
        runtime.charge_profile_grid_enabled = grid
        # This represents a slot immediately after selecting Charge: the
        # profile has been copied once and the slot is now authoritative.
        slot.charge_enabled = grid
        slot.charge_current = 120
        slot.discharge_current = 120
        slot.grid_charge_current = 60
        slot.tou_soc = 90
        slot.minimum_sell_soc = 90
        return slot

    def grid_switch_calls(self, runtime):
        return [
            call for call in runtime.hass.services.calls
            if call[:2] == ("switch", "turn_on")
            and "_grid_charge" in str(call[2].get("entity_id"))
        ]

    def test_charge_with_grid_no_never_enables_grid_charge(self):
        runtime = make_runtime()
        self.configure_charge_slot(runtime, grid=False)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(self.grid_switch_calls(runtime), [])
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_GRID_CHARGE_CURRENT).state,
            "60",
        )

    def test_grid_no_repairs_an_externally_enabled_tou_grid_charge(self):
        runtime = make_runtime()
        self.configure_charge_slot(runtime, grid=False)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        runtime.hass.services.calls.clear()
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(
            runtime.hass.states.get("switch.deye_inverter_time_of_use_1_grid_charge").state,
            "off",
        )

    def test_charge_with_grid_yes_enables_grid_charge(self):
        runtime = make_runtime()
        self.configure_charge_slot(runtime, grid=True)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertTrue(self.grid_switch_calls(runtime))

    def test_legacy_charge_scheduler_flag_cannot_change_schedule_result(self):
        runtime = make_runtime()
        self.configure_charge_slot(runtime, grid=False)
        runtime.charge_scheduler_enabled = True  # Simulates an old restored value.
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(self.grid_switch_calls(runtime), [])

    def test_zero_export_with_battery_charge_current_and_grid_no(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT
        slot.charge_current = 120
        slot.grid_charge_current = 0
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state, const.MODE_ZERO_EXPORT_CT)
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_CHARGE_CURRENT).state, "120")
        self.assertEqual(self.grid_switch_calls(runtime), [])

    def test_zero_export_does_not_require_price_or_sale_soc(self):
        runtime = make_runtime(soc=None, price=None)
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT
        slot.charge_current = 120
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state, const.MODE_ZERO_EXPORT)

    def test_sell_soc_and_charge_target_soc_are_independent(self):
        runtime = make_runtime()
        slot = self.configure_charge_slot(runtime, grid=False)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 85
        runtime.charge_profile_target_soc = 70
        segments = runtime._tou_mapping.slots
        self.assertIn(85, [segment.soc for segment in segments])
        self.assertEqual(slot.minimum_sell_soc, 20)

    def test_charge_slot_keeps_default_ct_topology_and_uses_slot_values(self):
        runtime = make_runtime(default_mode=const.MODE_NORMAL_OPERATION)
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        slot = self.configure_charge_slot(runtime, grid=False)
        slot.charge_current = 95
        slot.discharge_current = 35
        slot.grid_charge_current = 55
        slot.tou_soc = 88
        # Later changes of the template must not overwrite the slot.
        runtime.charge_profile_charge_current = 95
        runtime.charge_profile_discharge_current = 25
        runtime.charge_profile_grid_charge_current = 45
        runtime.charge_profile_target_soc = 78

        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state, const.MODE_ZERO_EXPORT_CT)
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_CHARGE_CURRENT).state, "95")
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_DISCHARGE_CURRENT).state, "35")
        tou_soc_values = [
            runtime.hass.states.get(f"number.deye_inverter_time_of_use_{idx}_soc").state
            for idx in range(1, 7)
        ]
        self.assertIn("88.0", tou_soc_values)

    def test_save_charge_profile_only_updates_the_template(self):
        runtime = make_runtime()
        slot = self.configure_charge_slot(runtime, grid=True)
        before_slot = dict(vars(slot))
        calls_before = list(runtime.hass.services.calls)
        asyncio.run(runtime.async_save_charge_profile({
            "charge_current": 120,
            "discharge_current": 30,
            "grid_charge_current": 40,
            "target_soc": 85,
            "grid_charge_enabled": True,
        }))

        self.assertEqual(runtime.charge_profile_charge_current, 120)
        self.assertEqual(runtime.charge_profile_discharge_current, 30)
        self.assertEqual(runtime.charge_profile_grid_charge_current, 40)
        self.assertEqual(runtime.charge_profile_target_soc, 85)
        self.assertTrue(runtime.charge_profile_grid_enabled)
        self.assertEqual(vars(slot), before_slot)
        self.assertEqual(runtime.hass.services.calls, calls_before)

    def test_save_charge_profile_while_stopped_persists_without_deye_calls(self):
        runtime = make_runtime()
        runtime.control_mode = "Stop Sell"
        runtime.scheduler_enabled = False
        calls_before = list(runtime.hass.services.calls)

        asyncio.run(runtime.async_save_charge_profile({
            "charge_current": 120,
            "discharge_current": 30,
            "grid_charge_current": 40,
            "target_soc": 85,
            "grid_charge_enabled": True,
        }))

        self.assertEqual(runtime.hass.services.calls, calls_before)
        self.assertEqual(runtime.charge_profile_charge_current, 120)
        self.assertEqual(
            runtime.last_action,
            "Zapisano szablon ustawień ładowania",
        )

    def test_charge_profile_does_not_mutate_non_charge_slot_settings(self):
        runtime = make_runtime()
        runtime.control_mode = "Stop Sell"
        runtime.scheduler_enabled = False
        modes = (
            const.MODE_SELLING_FIRST,
            const.MODE_NORMAL_OPERATION,
            const.MODE_NORMAL_OPERATION,
        )
        physical_variants = (None, const.MODE_ZERO_EXPORT, const.MODE_ZERO_EXPORT_CT)
        protected = []
        for slot, mode, physical in zip(runtime.slots.values(), modes, physical_variants):
            slot.enabled = True
            slot.mode = mode
            if physical:
                slot.physical_work_mode = physical
            slot.sell_power = 4321
            slot.discharge_current = 45
            slot.charge_current = 55
            slot.grid_charge_current = 65
            slot.minimum_sell_soc = 25
            slot.tou_soc = 35
            protected.append((slot, dict(vars(slot))))

        asyncio.run(runtime.async_save_charge_profile({
            "charge_current": 120,
            "discharge_current": 30,
            "grid_charge_current": 40,
            "target_soc": 85,
            "grid_charge_enabled": True,
        }))

        for slot, before in protected:
            self.assertEqual(vars(slot), before)

    def test_selecting_charge_copies_template_once_and_keeps_manual_override(self):
        runtime = make_runtime()
        runtime.charge_profile_charge_current = 101
        runtime.charge_profile_discharge_current = 31
        runtime.charge_profile_grid_charge_current = 41
        runtime.charge_profile_target_soc = 81
        runtime.charge_profile_grid_enabled = True
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        slot.mode = const.MODE_NORMAL_OPERATION

        runtime.set_work_mode_for_slot(slot_key, const.MODE_CHARGE)
        self.assertEqual(slot.charge_current, 101)
        self.assertEqual(slot.discharge_current, 31)
        self.assertEqual(slot.grid_charge_current, 41)
        self.assertEqual(slot.tou_soc, 81)
        self.assertTrue(slot.charge_enabled)

        slot.charge_current = 77
        slot.tou_soc = 66
        asyncio.run(runtime.async_save_charge_profile({
            "charge_current": 120,
            "discharge_current": 40,
            "grid_charge_current": 50,
            "target_soc": 90,
            "grid_charge_enabled": False,
        }))
        runtime.set_work_mode_for_slot(slot_key, const.MODE_CHARGE)
        self.assertEqual(slot.charge_current, 77)
        self.assertEqual(slot.tou_soc, 66)
        self.assertTrue(slot.charge_enabled)

    def test_existing_charge_slots_keep_independent_manual_values(self):
        runtime = make_runtime()
        runtime.charge_profile_charge_current = 105
        runtime.charge_profile_discharge_current = 35
        runtime.charge_profile_grid_charge_current = 45
        runtime.charge_profile_target_soc = 82
        runtime.charge_profile_grid_enabled = True
        charge_slots = list(runtime.slots.values())[:2]
        for index, slot in enumerate(charge_slots):
            slot.enabled = True
            slot.mode = const.MODE_CHARGE
            slot.charge_enabled = index == 0
            slot.charge_current = 5 + index
            slot.discharge_current = 6 + index
            slot.grid_charge_current = 7 + index
            slot.tou_soc = 8 + index

        segments = runtime._tou_mapping.slots
        self.assertEqual(segments[0].soc, 8)
        self.assertTrue(segments[0].grid_charge)
        self.assertEqual(segments[1].soc, 9)
        self.assertFalse(segments[1].grid_charge)

    def test_grid_charge_yes_is_reflected_in_physical_mapping(self):
        runtime = make_runtime()
        runtime.charge_profile_target_soc = 80
        runtime.charge_profile_grid_enabled = True
        charge_slot = list(runtime.slots.values())[5]
        charge_slot.enabled = True
        charge_slot.mode = const.MODE_CHARGE
        charge_slot.charge_enabled = True
        charge_slot.grid_charge_current = 40
        charge_slot.tou_soc = 80

        segments = runtime._tou_mapping.slots
        self.assertTrue(any(segment.grid_charge for segment in segments))
        self.assertTrue(any(segment.soc == 80 and segment.grid_charge for segment in segments))

    def test_concurrent_profile_save_and_tick_do_not_duplicate_physical_writes(self):
        runtime = make_runtime()
        self.configure_charge_slot(runtime, grid=True)

        async def run_both():
            await asyncio.gather(
                runtime.async_save_charge_profile({
                    "charge_current": 120,
                    "discharge_current": 30,
                    "grid_charge_current": 40,
                    "target_soc": 85,
                    "grid_charge_enabled": True,
                }),
                runtime.async_tick(),
            )

        asyncio.run(run_both())
        physical = [
            (domain, service, data.get("entity_id"))
            for domain, service, data, _blocking in runtime.hass.services.calls
            if domain in ("number", "select", "switch", "time")
        ]
        self.assertEqual(len(physical), len(set(physical)))

    def test_same_slot_failure_restores_defaults_once_per_fingerprint(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.services.fail_once(
            "number", "set_value", entity_id=const.DEFAULT_MAX_SELL_POWER
        )
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        first_defaults = len(control_number_calls(runtime))
        runtime.hass.services.calls.clear()
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(control_number_calls(runtime), [])
        self.assertGreater(first_defaults, 0)

    def test_resume_and_tick_are_serialized(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.control_mode = "Stop Sell"
        runtime.scheduler_enabled = False
        original_tick = runtime._async_tick_impl
        active = 0
        maximum = 0

        async def tracked_tick(*args):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0)
                return await original_tick(*args)
            finally:
                active -= 1

        runtime._async_tick_impl = tracked_tick

        async def run_both():
            await asyncio.gather(runtime.async_resume_manager(), runtime.async_tick())

        asyncio.run(run_both())
        self.assertEqual(maximum, 1)


class NormalProfileTests(unittest.TestCase):
    def configure_normal_profile(self, runtime):
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        runtime.normal_profile_sell_power = 2500
        runtime.normal_profile_discharge_current = 80
        runtime.normal_profile_charge_current = 90
        runtime.normal_profile_grid_charge_current = 10
        runtime.normal_profile_tou_soc = 75

    def test_selecting_normal_operation_copies_template_once(self):
        runtime = make_runtime()
        self.configure_normal_profile(runtime)
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        slot.mode = const.MODE_SELLING_FIRST

        runtime.set_work_mode_for_slot(slot_key, const.MODE_NORMAL_OPERATION)
        self.assertEqual(slot.mode, const.MODE_NORMAL_OPERATION)
        self.assertEqual(slot.physical_work_mode, const.MODE_ZERO_EXPORT_CT)
        self.assertEqual(slot.sell_power, 2500)
        self.assertEqual(slot.discharge_current, 80)
        self.assertEqual(slot.charge_current, 90)
        self.assertEqual(slot.grid_charge_current, 10)
        self.assertEqual(slot.tou_soc, 75)

    def test_manual_slot_values_survive_template_change(self):
        runtime = make_runtime()
        self.configure_normal_profile(runtime)
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        slot.mode = const.MODE_SELLING_FIRST

        runtime.set_work_mode_for_slot(slot_key, const.MODE_NORMAL_OPERATION)
        slot.sell_power = 999
        slot.tou_soc = 50

        runtime.normal_profile_sell_power = 3000
        runtime.normal_profile_tou_soc = 80
        runtime.set_work_mode_for_slot(slot_key, const.MODE_NORMAL_OPERATION)
        self.assertEqual(slot.sell_power, 999)
        self.assertEqual(slot.tou_soc, 50)

    def test_force_copy_normal_profile_reloads_template(self):
        runtime = make_runtime()
        self.configure_normal_profile(runtime)
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        runtime.set_work_mode_for_slot(slot_key, const.MODE_NORMAL_OPERATION)
        slot.sell_power = 999
        slot.tou_soc = 50

        runtime.normal_profile_sell_power = 3000
        runtime.normal_profile_tou_soc = 80
        asyncio.run(runtime.async_apply_schedule_patch([
            {
                "slot_key": slot_key,
                "mode": const.MODE_NORMAL_OPERATION,
                "force_copy_normal_profile": True,
            }
        ]))
        self.assertEqual(slot.sell_power, 3000)
        self.assertEqual(slot.tou_soc, 80)

    def test_target_mode_returns_logical_normal_label(self):
        runtime = make_runtime()
        self.configure_normal_profile(runtime)
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT

        self.assertEqual(runtime.target_mode, const.MODE_NORMAL_OPERATION)
        self.assertNotEqual(runtime.target_mode, const.MODE_ZERO_EXPORT_CT)

    def test_save_normal_profile_rejects_non_physical_mode(self):
        runtime = make_runtime()
        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_save_normal_profile({
                "physical_work_mode": const.MODE_NORMAL_OPERATION,
                "sell_power": 1000,
                "discharge_current": 50,
                "charge_current": 50,
                "grid_charge_current": 10,
                "tou_soc": 50,
            }))

    def test_save_normal_profile_partial_update_preserves_existing_tou_soc(self):
        runtime = make_runtime()
        self.configure_normal_profile(runtime)
        asyncio.run(runtime.async_save_normal_profile({
            "physical_work_mode": const.MODE_ZERO_EXPORT,
        }))
        self.assertEqual(runtime.normal_profile_physical_work_mode, const.MODE_ZERO_EXPORT)
        self.assertEqual(runtime.normal_profile_tou_soc, 75)
        self.assertEqual(runtime.normal_profile_sell_power, 2500)

    def test_save_normal_profile_rejects_explicit_nan_tou_soc(self):
        runtime = make_runtime()
        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_save_normal_profile({
            "physical_work_mode": const.MODE_ZERO_EXPORT,
                "sell_power": 1000,
                "discharge_current": 50,
                "charge_current": 50,
                "grid_charge_current": 10,
                "tou_soc": None,
            }))


class ChargeProfileSlotReloadTests(unittest.TestCase):
    """Regression coverage for copying the Charge template into slots."""

    def _configure_charge_profile(self, runtime):
        runtime.charge_profile_charge_current = 120
        runtime.charge_profile_discharge_current = 120
        runtime.charge_profile_grid_charge_current = 60
        runtime.charge_profile_target_soc = 80
        runtime.charge_profile_grid_enabled = True

    def test_force_copy_charge_profile_reloads_whole_template(self):
        runtime = make_runtime()
        self._configure_charge_profile(runtime)
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        slot.mode = const.MODE_CHARGE
        slot.charge_current = 5
        slot.discharge_current = 6
        slot.grid_charge_current = 7
        slot.tou_soc = 10
        slot.charge_enabled = False

        asyncio.run(runtime.async_apply_schedule_patch([{
            "slot_key": slot_key,
            "mode": const.MODE_CHARGE,
            "force_copy_charge_profile": True,
        }]))

        self.assertEqual(slot.mode, const.MODE_CHARGE)
        self.assertEqual(slot.charge_current, 120)
        self.assertEqual(slot.discharge_current, 120)
        self.assertEqual(slot.grid_charge_current, 60)
        self.assertEqual(slot.tou_soc, 80)
        self.assertTrue(slot.charge_enabled)

    def test_force_copy_charge_profile_affects_only_requested_slot(self):
        runtime = make_runtime()
        self._configure_charge_profile(runtime)
        keys = list(runtime.slots.keys())
        first = runtime.slots[keys[0]]
        second = runtime.slots[keys[1]]
        first.mode = const.MODE_CHARGE
        second.mode = const.MODE_CHARGE
        first.charge_current = 5
        second.charge_current = 7

        asyncio.run(runtime.async_apply_schedule_patch([{
            "slot_key": keys[0],
            "mode": const.MODE_CHARGE,
            "force_copy_charge_profile": True,
        }]))

        self.assertEqual(first.charge_current, 120)
        self.assertEqual(second.charge_current, 7)

    def test_new_charge_slot_copies_full_template_from_runtime(self):
        runtime = make_runtime()
        self._configure_charge_profile(runtime)
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = 30

        runtime.set_work_mode_for_slot(slot_key, const.MODE_CHARGE)
        self.assertEqual(slot.charge_current, 120)
        self.assertEqual(slot.discharge_current, 120)
        self.assertEqual(slot.grid_charge_current, 60)
        self.assertEqual(slot.tou_soc, 80)
        self.assertTrue(slot.charge_enabled)

    def test_existing_charge_slot_keeps_manual_values_after_template_change(self):
        runtime = make_runtime()
        self._configure_charge_profile(runtime)
        slot_key = runtime.active_slot_key()
        slot = runtime.slots[slot_key]
        runtime.set_work_mode_for_slot(slot_key, const.MODE_CHARGE)
        slot.tou_soc = 55

        runtime.charge_profile_target_soc = 90
        runtime.charge_profile_grid_enabled = False
        runtime.set_work_mode_for_slot(slot_key, const.MODE_CHARGE)

        self.assertEqual(slot.tou_soc, 55)
        self.assertTrue(slot.charge_enabled)


class GridChargeIndependenceTests(unittest.TestCase):
    """charge_enabled is a physical hourly Grid Charge flag, not a mode."""

    def test_switching_from_charge_to_normal_preserves_grid_charge(self):
        runtime = make_runtime()
        slot = runtime.slots["05_06"]
        slot.mode = const.MODE_CHARGE
        slot.charge_enabled = True
        runtime.set_work_mode_for_slot("05_06", const.MODE_NORMAL_OPERATION)
        self.assertTrue(slot.charge_enabled)

    def test_switching_from_charge_to_selling_preserves_grid_charge(self):
        runtime = make_runtime()
        slot = runtime.slots["05_06"]
        slot.mode = const.MODE_CHARGE
        slot.charge_enabled = True
        runtime.set_work_mode_for_slot("05_06", const.MODE_SELLING_FIRST)
        self.assertTrue(slot.charge_enabled)

    def test_explicit_grid_charge_overrides_charge_mode_default(self):
        runtime = make_runtime()
        runtime.charge_profile_grid_enabled = False
        slot = runtime.slots["05_06"]
        slot.mode = const.MODE_NORMAL_OPERATION
        asyncio.run(
            runtime.async_apply_schedule_patch(
                [{"slot_key": "05_06", "mode": const.MODE_CHARGE, "charge_enabled": True}]
            )
        )
        self.assertTrue(slot.charge_enabled)

    def test_grid_charge_remains_independent_of_manager_mode(self):
        runtime = make_runtime()
        slot = runtime.slots["05_06"]
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.charge_enabled = True
        asyncio.run(
            runtime.async_apply_schedule_patch(
                [{"slot_key": "05_06", "mode": const.MODE_SELLING_FIRST, "minimum_sell_soc": 20}]
            )
        )
        self.assertTrue(slot.charge_enabled)


class NormalProfileSelectTests(unittest.TestCase):
    """Polish labels for the normal-profile physical mode select."""

    def _runtime_for_provider(self, provider):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = provider
        return runtime

    def test_normal_profile_select_exposes_only_polish_labels(self):
        runtime = self._runtime_for_provider(const.PROVIDER_LEWA_REKA)
        select = select_module.DeyeNormalProfileModeSelect(runtime)
        self.assertEqual(
            select.options,
            [
                "Eksport wyłączony — pomiar Load",
                "Eksport wyłączony — pomiar CT",
            ],
        )

    def test_normal_profile_select_restores_legacy_provider_value_as_polish_label(self):
        runtime = self._runtime_for_provider(const.PROVIDER_LEWA_REKA)
        key = select_module.physical_normal_option_to_key(
            runtime.data, "Zero Export To CT"
        )
        self.assertEqual(key, const.MODE_ZERO_EXPORT_CT)

    def test_normal_profile_polish_label_maps_to_lewa_reka_option(self):
        runtime = self._runtime_for_provider(const.PROVIDER_LEWA_REKA)
        key = select_module.normal_profile_mode_label_to_key(
            runtime.data, "Eksport wyłączony — pomiar Load"
        )
        self.assertEqual(key, const.MODE_ZERO_EXPORT)

    def test_normal_profile_polish_label_maps_to_solarman_option(self):
        runtime = self._runtime_for_provider(const.PROVIDER_SOLARMAN)
        select = select_module.DeyeNormalProfileModeSelect(runtime)
        self.assertEqual(
            select.options,
            [
                "Eksport wyłączony — pomiar Load",
                "Eksport wyłączony — pomiar CT",
            ],
        )
        key = select_module.normal_profile_mode_label_to_key(
            runtime.data, "Eksport wyłączony — pomiar Load"
        )
        self.assertEqual(key, const.MODE_ZERO_EXPORT)

    def test_normal_profile_polish_label_maps_to_sunsynk_option(self):
        runtime = self._runtime_for_provider(const.PROVIDER_SUNSYNK)
        select = select_module.DeyeNormalProfileModeSelect(runtime)
        self.assertEqual(
            select.options,
            [
                "Zasilanie odbiorów podstawowych",
                "Eksport wyłączony",
            ],
        )
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT
        self.assertEqual(select.current_option, "Zasilanie odbiorów podstawowych")
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        self.assertEqual(select.current_option, "Eksport wyłączony")


class CardBackendModeContract5FTests(unittest.TestCase):
    """The card's current mode values must be accepted by the real backend."""

    def test_card_manager_modes_match_real_backend_validation(self):
        source = (
            ROOT
            / "custom_components"
            / "deye_energy_manager"
            / "www"
            / "deye-energy-manager-card.js"
        ).read_text(encoding="utf-8")
        start = source.index("  slotWorkModes() {")
        method = source[start : source.index("\n  }", start) + 4]

        for mode in const.SLOT_MODES:
            self.assertIn(f'"{mode}"', method)
        self.assertNotIn('"Selling First"', method)
        self.assertNotIn('"Charge"', method)

        for mode in const.SLOT_MODES:
            runtime = make_runtime()
            runtime.control_enabled = False
            runtime.control_status = "Wyłączone"
            asyncio.run(
                runtime.async_apply_schedule_patch(
                    [{"slot_key": "06_07", "mode": mode}]
                )
            )
            self.assertEqual(runtime.slots["06_07"].mode, mode)


class TouSocMappingTests(unittest.TestCase):
    """Regression coverage for logical SOC versus physical Deye TOU SOC."""

    def test_schedule_mapping_snapshot_has_no_legacy_schedule_function(self):
        runtime = make_runtime()
        snapshot = runtime.schedule_mapping_snapshot()
        self.assertTrue(snapshot)
        for item in snapshot:
            self.assertNotIn("schedule_function", item)
            self.assertEqual(
                set(item), {"range", "start", "end", "tou_soc", "grid_charge"}
            )

    @staticmethod
    def _active_physical_segment(runtime):
        hour = manager.ha_now().hour
        for segment in runtime._tou_mapping.slots:
            start = int(segment.start)
            end = 24 if int(segment.end) == 0 else int(segment.end)
            if start <= hour < end:
                return segment.index, segment
        raise AssertionError("Nie znaleziono fizycznego zakresu dla aktywnej godziny")

    def _map_active_slot(self, runtime, expected_soc, expected_grid):
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        index, segment = self._active_physical_segment(runtime)
        self.assertEqual(segment.soc, expected_soc)
        self.assertEqual(segment.grid_charge, expected_grid)
        self.assertEqual(
            runtime.hass.states.get(f"number.deye_inverter_time_of_use_{index}_soc").state,
            str(float(expected_soc)),
        )
        self.assertEqual(
            runtime.hass.states.get(f"switch.deye_inverter_time_of_use_{index}_grid_charge").state,
            "on" if expected_grid else "off",
        )

    def test_selling_slot_uses_tou_soc_as_physical_tou_soc(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 10
        self._map_active_slot(runtime, 10, False)

    def test_selling_slot_minimum_sell_soc_is_only_logical_guard(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 20
        # With tou_soc still missing, the physical mapping cannot be written.
        slot.tou_soc = None
        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertIn("wymaga potwierdzenia", runtime.last_error)

    def test_zero_export_load_maps_its_own_tou_soc(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT
        slot.minimum_sell_soc = 30
        slot.tou_soc = 12
        self._map_active_slot(runtime, 12, False)

    def test_zero_export_ct_maps_its_own_tou_soc(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT
        slot.minimum_sell_soc = 25
        slot.tou_soc = 15
        self._map_active_slot(runtime, 15, False)

    def test_charge_slot_target_soc_and_grid_enabled_are_mapped(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_CHARGE
        slot.tou_soc = 80
        slot.charge_enabled = True
        runtime.charge_profile_target_soc = 80
        runtime.charge_profile_grid_enabled = False
        self._map_active_slot(runtime, 80, True)

    def test_charge_slot_target_soc_and_grid_disabled_are_mapped(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_CHARGE
        slot.tou_soc = 70
        slot.charge_enabled = False
        runtime.charge_profile_target_soc = 70
        runtime.charge_profile_grid_enabled = True
        self._map_active_slot(runtime, 70, False)

    def test_disabled_slot_keeps_its_tou_soc_instead_of_zero(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = False
        slot.tou_soc = 10
        self._map_active_slot(runtime, 10, False)

    def test_diagnostics_show_tou_soc_as_effective_physical_tou_soc(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 10
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        diagnostics = runtime.diagnostics()
        active = diagnostics["active_slot_control"]
        self.assertEqual(active["minimum_sell_soc"], 20)
        self.assertEqual(active["tou_soc"], 10)
        # After 5A.1 effective_tou_soc is the physical tou_soc, not the sale guard.
        self.assertEqual(active["effective_tou_soc"], 10)
        self.assertEqual(active["physical_soc_actual"], "10.0")
        self.assertFalse(active["grid_charge_expected"])
        self.assertEqual(active["grid_charge_actual"], "off")
        self.assertEqual(len(diagnostics["physical_tou"]), 6)

    def test_unconfirmed_tou_soc_blocks_physical_write_without_substitution(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.tou_soc = None
        calls_before = list(runtime.hass.services.calls)

        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertIn("wymaga potwierdzenia", runtime.last_error)
        self.assertEqual(runtime.hass.services.calls, calls_before)

    def test_unconfirmed_charge_tou_soc_also_blocks_physical_write(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_CHARGE
        slot.charge_enabled = True
        slot.tou_soc = None
        calls_before = list(runtime.hass.services.calls)

        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertIn("wymaga potwierdzenia", runtime.last_error)
        self.assertEqual(runtime.hass.services.calls, calls_before)

    def test_changing_minimum_sell_soc_does_not_change_tou_mapping(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.tou_soc = 17
        slot.minimum_sell_soc = 20
        before = [(s.start, s.end, s.soc, s.grid_charge) for s in runtime._tou_mapping.slots]
        slot.minimum_sell_soc = 90
        after = [(s.start, s.end, s.soc, s.grid_charge) for s in runtime._tou_mapping.slots]
        self.assertEqual(before, after)
        self.assertIn(17.0, {segment.soc for segment in runtime._tou_mapping.slots})

    def test_changing_selling_tou_soc_changes_physical_mapping(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 17
        before = [(s.start, s.end, s.soc, s.grid_charge) for s in runtime._tou_mapping.slots]
        slot.tou_soc = 90
        after = runtime._tou_mapping.slots
        self.assertNotEqual(before, [(s.start, s.end, s.soc, s.grid_charge) for s in after])
        self.assertIn(90.0, {segment.soc for segment in after})

    def test_nonphysical_slot_parameters_do_not_create_tou_boundary(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.tou_soc = 20
        before = runtime._tou_mapping.slots
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT
        slot.sell_power = 5000
        slot.charge_current = 120
        slot.discharge_current = 30
        slot.grid_charge_current = 60
        slot.minimum_sell_soc = 90
        after = runtime._tou_mapping.slots
        self.assertEqual(
            [(s.start, s.end, s.soc, s.grid_charge) for s in before],
            [(s.start, s.end, s.soc, s.grid_charge) for s in after],
        )

    def test_logical_modes_keep_charge_and_sale_as_natural_tou_boundaries(self):
        runtime = make_runtime()
        for slot in runtime.slots.values():
            slot.enabled = True
            slot.mode = const.MODE_NORMAL_OPERATION
            slot.tou_soc = 10
            slot.charge_enabled = False

        for index, slot in enumerate(runtime.slots.values()):
            if index == 8:
                slot.mode = const.MODE_CHARGE
                slot.tou_soc = 100
                slot.charge_enabled = True
            elif 13 <= index < 19:
                slot.tou_soc = 20
            elif 19 <= index < 23:
                slot.mode = const.MODE_SELLING_FIRST
                slot.minimum_sell_soc = 10
                slot.tou_soc = 10

        segments = runtime._tou_mapping.slots

        self.assertEqual(
            [
                (
                    segment.start,
                    segment.end,
                    "normal",
                    segment.soc,
                    segment.grid_charge,
                )
                for segment in segments
            ],
            [
                (0, 4, "normal", 10, False),
                (4, 8, "normal", 10, False),
                (8, 9, "normal", 100, True),
                (9, 13, "normal", 10, False),
                (13, 19, "normal", 20, False),
                (19, 0, "normal", 10, False),
            ],
        )

    def test_seven_ranges_report_mapping_error(self):
        runtime = make_runtime()
        slots = list(runtime.slots.values())
        for slot in slots:
            slot.enabled = True
            slot.mode = const.MODE_NORMAL_OPERATION
            slot.tou_soc = 10
            slot.charge_enabled = False

        slots[10].mode = const.MODE_CHARGE
        slots[10].tou_soc = 100
        slots[10].charge_enabled = True
        for slot in slots[13:19]:
            slot.tou_soc = 20
        slots[19].mode = const.MODE_SELLING_FIRST
        slots[19].minimum_sell_soc = 10
        slots[19].tou_soc = 10
        for slot in slots[20:23]:
            slot.mode = const.MODE_SELLING_FIRST
            slot.minimum_sell_soc = 35
            slot.tou_soc = 35

        mapping = runtime._tou_mapping
        self.assertEqual(len(mapping.slots), 7)
        self.assertTrue(runtime.mapping_error)

    def test_schedule_mapping_recalculates_after_schedule_change(self):
        runtime = make_runtime()
        slots = list(runtime.slots.values())
        for slot in slots:
            slot.enabled = True
            slot.mode = const.MODE_NORMAL_OPERATION
            slot.tou_soc = 10
            slot.charge_enabled = False
        for slot in slots[13:19]:
            slot.tou_soc = 20
        for slot in slots[19:23]:
            slot.mode = const.MODE_SELLING_FIRST
            slot.minimum_sell_soc = 30
            slot.tou_soc = 30

        slots[8].mode = const.MODE_CHARGE
        slots[8].tou_soc = 100
        slots[8].charge_enabled = True
        first_mapping = runtime.schedule_mapping_snapshot()

        slots[8].mode = const.MODE_NORMAL_OPERATION
        slots[8].tou_soc = 10
        slots[8].charge_enabled = False
        for slot in slots[8:10]:
            slot.mode = const.MODE_CHARGE
            slot.tou_soc = 100
            slot.charge_enabled = True
        second_mapping = runtime.schedule_mapping_snapshot()

        self.assertNotEqual(first_mapping, second_mapping)
        self.assertIn(
            {
                "range": 2,
                "start": 8,
                "end": 10,
                "tou_soc": 100.0,
                "grid_charge": True,
            },
            second_mapping,
        )
        self.assertEqual(len(first_mapping), 6)
        self.assertEqual(len(second_mapping), 6)

    def test_mapping_snapshot_covers_normal_disabled_charge_and_sale(self):
        runtime = make_runtime()
        slots = list(runtime.slots.values())
        for slot in slots:
            slot.enabled = True
            slot.mode = const.MODE_NORMAL_OPERATION
            slot.tou_soc = 10
            slot.charge_enabled = False

        for slot in slots[4:8]:
            slot.enabled = False
        slots[8].mode = const.MODE_CHARGE
        slots[8].tou_soc = 100
        slots[8].charge_enabled = True
        for slot in slots[13:19]:
            slot.tou_soc = 20
        for slot in slots[19:24]:
            slot.mode = const.MODE_SELLING_FIRST
            slot.minimum_sell_soc = 35
            slot.tou_soc = 35

        self.assertEqual(
            runtime.schedule_mapping_snapshot(),
            [
                {"range": 1, "start": 0, "end": 4, "tou_soc": 10.0, "grid_charge": False},
                {"range": 2, "start": 4, "end": 8, "tou_soc": 10.0, "grid_charge": False},
                {"range": 3, "start": 8, "end": 9, "tou_soc": 100.0, "grid_charge": True},
                {"range": 4, "start": 9, "end": 13, "tou_soc": 10.0, "grid_charge": False},
                {"range": 5, "start": 13, "end": 19, "tou_soc": 20.0, "grid_charge": False},
                {"range": 6, "start": 19, "end": 0, "tou_soc": 35.0, "grid_charge": False},
            ],
        )

    def test_sale_soc_changes_create_exact_six_range_mapping(self):
        runtime = make_runtime()
        slots = list(runtime.slots.values())
        for slot in slots:
            slot.enabled = True
            slot.mode = const.MODE_NORMAL_OPERATION
            slot.tou_soc = 10
        for slot in slots[13:19]:
            slot.tou_soc = 20
        for slot in slots[19:21]:
            slot.mode = const.MODE_SELLING_FIRST
            slot.minimum_sell_soc = 10
            slot.tou_soc = 10
        for slot in slots[21:23]:
            slot.mode = const.MODE_SELLING_FIRST
            slot.minimum_sell_soc = 35
            slot.tou_soc = 35

        self.assertEqual(
            [
                (item.start, item.end, "normal", item.soc)
                for item in runtime._tou_mapping.slots
            ],
            [
                (0, 6, "normal", 10.0),
                (6, 13, "normal", 10.0),
                (13, 19, "normal", 20.0),
                (19, 21, "normal", 10.0),
                (21, 23, "normal", 35.0),
                (23, 0, "normal", 10.0),
            ],
        )

    def test_changing_tou_soc_creates_a_physical_boundary(self):
        runtime = make_runtime()
        before = runtime._tou_mapping.slots
        self.assertEqual({segment.soc for segment in before}, {20.0})

        changed = list(runtime.slots.values())[8]
        changed.tou_soc = 33
        after = runtime._tou_mapping.slots

        self.assertEqual({segment.soc for segment in after}, {20.0, 33.0})
        self.assertTrue(any(
            segment.start == 8 and segment.end == 9 and segment.soc == 33
            for segment in after
        ))

    def test_migration_preserves_existing_tou_soc_beside_legacy_min_soc(self):
        runtime = make_runtime()
        normalized = runtime._validate_future_plan_updates([{
            "slot_key": "05_06",
            "mode": const.MODE_SELLING_FIRST,
            "min_soc": 80,
            "tou_soc": 37,
        }])[0]

        self.assertEqual(normalized["minimum_sell_soc"], 80)
        self.assertNotIn("tou_soc", normalized)


class SellingTouSocSeparationTests(unittest.TestCase):
    """Stage 5A.1: minimum_sell_soc is a logical guard; tou_soc is physical."""

    def _configure_blocked_selling_slot(self, runtime, min_sell=35, tou_soc=15):
        active = configure_selling_slot(runtime)
        active.minimum_sell_soc = min_sell
        active.tou_soc = tou_soc
        runtime.default_work_mode = const.MODE_NORMAL_OPERATION
        runtime.default_sell_power = 250
        runtime.default_discharge_current = 75
        return active

    def test_blocked_sale_uses_default_work_mode(self):
        runtime = make_runtime(soc="30")
        self._configure_blocked_selling_slot(runtime, min_sell=35)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ ZABLOKOWANA")
        self.assertEqual(runtime.target_mode, runtime.default_work_mode)
        self.assertEqual(runtime.target_mode, const.MODE_NORMAL_OPERATION)

    def test_blocked_sale_uses_default_sell_power(self):
        runtime = make_runtime(soc="30")
        self._configure_blocked_selling_slot(runtime, min_sell=35)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_MAX_SELL_POWER).state,
            "250",
        )

    def test_blocked_sale_preserves_nonzero_default_discharge_current(self):
        runtime = make_runtime(soc="30")
        self._configure_blocked_selling_slot(runtime, min_sell=35)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_DISCHARGE_CURRENT).state,
            "75",
        )

    def test_reverse_sync_updates_selling_tou_soc_not_minimum_sell_soc(self):
        runtime = make_runtime()
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_SELLING_FIRST
        active.minimum_sell_soc = 30
        active.tou_soc = 15
        # Mutate the physical mapping so the active hour has a different SOC.
        mapping = runtime._tou_mapping
        active_hour = int(active.key[:2])
        for segment in mapping.slots:
            if active_hour in segment.source_hours:
                segment.soc = 55
        patch = runtime.tou_mapping_to_schedule_patch(mapping)
        active_update = next(p for p in patch if p["slot_key"] == active.key)
        self.assertEqual(active_update["tou_soc"], 55)
        self.assertNotIn("minimum_sell_soc", active_update)
        self.assertEqual(active.minimum_sell_soc, 30)
        self.assertEqual(active.tou_soc, 15)
        # Apply the patch to verify only tou_soc is changed.
        asyncio.run(runtime.async_apply_schedule_patch(patch))
        self.assertEqual(active.tou_soc, 55)
        self.assertEqual(active.minimum_sell_soc, 30)

    def test_sale_and_normal_hours_with_same_tou_soc_and_grid_can_share_physical_range(self):
        runtime = make_runtime()
        slots = list(runtime.slots.values())
        for slot in slots:
            slot.enabled = True
            slot.mode = const.MODE_NORMAL_OPERATION
            slot.tou_soc = 10
            slot.charge_enabled = False
        for slot in slots[4:8]:
            slot.tou_soc = 20
        for slot in slots[8:12]:
            slot.mode = const.MODE_SELLING_FIRST
            slot.minimum_sell_soc = 30
            slot.tou_soc = 20
        for slot in slots[12:16]:
            slot.tou_soc = 30
        for slot in slots[16:20]:
            slot.tou_soc = 40
        for slot in slots[20:22]:
            slot.tou_soc = 50
        for slot in slots[22:24]:
            slot.tou_soc = 60
        segments = [
            (segment.start, segment.end, segment.soc, segment.grid_charge)
            for segment in runtime._tou_mapping.slots
        ]
        # Normal 04:00-08:00 and Selling 08:00-12:00 share one physical range
        # because the physical key is (tou_soc, grid_charge) and ignores mode.
        self.assertIn((4, 12, 20.0, False), segments)
        self.assertEqual(len(runtime._tou_mapping.slots), 6)

    def _mark_all_slot_entities_restored(self, runtime):
        for key in runtime.slots:
            runtime._restored_slot_mode_keys.add(key)
            runtime._restored_slot_tou_soc_keys.add(key)
            runtime._restored_slot_minimum_sell_soc_keys.add(key)

    def _configure_distinct_physical_tou_starts(self, runtime):
        """Give each physical TOU range a realistic 4-hour start boundary."""
        starts = ["00:00:00", "04:00:00", "08:00:00", "12:00:00", "16:00:00", "20:00:00"]
        for idx, start in enumerate(starts, start=1):
            runtime.hass.states.values[f"time.deye_inverter_time_of_use_{idx}_start"] = FakeState(start)

    def test_tou_soc_migration_preserves_valid_restored_value(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = 45
        slot.minimum_sell_soc = 30
        self._mark_all_slot_entities_restored(runtime)
        runtime._tou_soc_migration_done = False
        runtime._migrate_selling_tou_soc()
        self.assertEqual(slot.tou_soc, 45)
        self.assertTrue(runtime._tou_soc_migration_done)

    def test_tou_soc_migration_preserves_valid_physical_readback(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = None
        slot.minimum_sell_soc = 30
        self._configure_distinct_physical_tou_starts(runtime)
        self._mark_all_slot_entities_restored(runtime)
        runtime._tou_soc_migration_done = False
        # Physical readback from make_runtime is 20%.
        runtime._migrate_selling_tou_soc()
        self.assertEqual(slot.tou_soc, 20)
        self.assertTrue(runtime._tou_soc_migration_done)

    def test_tou_soc_migration_runs_before_any_tou_mapping_or_write(self):
        # Static proof: within async_tick(), _migrate_selling_tou_soc() is called
        # before async_process_future_plan() and before the _async_tick_impl()
        # lock, so it always runs before schedule_to_tou_mapping() or
        # async_apply_time_of_use_map().
        source = Path(__file__).resolve().parents[1].joinpath(
            "custom_components", "deye_energy_manager", "manager.py"
        ).read_text(encoding="utf-8")
        tick_start = source.index("async def async_tick(self, *_args: Any) -> None:")
        tick_end = source.index("async def async_start(self) -> None:", tick_start)
        tick_body = source[tick_start:tick_end]
        migrate_pos = tick_body.index("self._migrate_selling_tou_soc()")
        plan_pos = tick_body.index("await self.async_process_future_plan()")
        lock_pos = tick_body.index("async with self._operation_lock:")
        impl_pos = tick_body.index("await self._async_tick_impl(*_args)")
        self.assertLess(migrate_pos, plan_pos)
        self.assertLess(migrate_pos, lock_pos)
        self.assertLess(migrate_pos, impl_pos)
        self.assertLess(plan_pos, lock_pos)
        self.assertLess(lock_pos, impl_pos)

    def test_tou_soc_migration_blocks_tou_write_until_ready(self):
        runtime = make_runtime()
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_SELLING_FIRST
        active.tou_soc = None
        # Required entities are not marked restored, so migration is not ready.
        runtime._tou_soc_migration_done = False
        services_before = list(runtime.hass.services.calls)
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assertIn("wymaga potwierdzenia", runtime.last_error)
        tou_calls = [
            call for call in runtime.hass.services.calls
            if call not in services_before and call[0] == "time"
        ]
        self.assertEqual(tou_calls, [])
        # Mark entities restored and supply a physical readback; migration resolves
        # tou_soc and the next TOU write can proceed.
        self._configure_distinct_physical_tou_starts(runtime)
        self._mark_all_slot_entities_restored(runtime)
        runtime._migrate_selling_tou_soc()
        self.assertEqual(active.tou_soc, 20)
        self.assertTrue(runtime._tou_soc_migration_done)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))

    def test_tou_soc_migration_uses_fallback_when_provider_has_no_readback_capability(self):
        # Provider without native TOU readback capability cannot provide a physical
        # SOC, so migration must immediately fall back to the logical sale guard.
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = None
        slot.minimum_sell_soc = 40
        self._mark_all_slot_entities_restored(runtime)
        runtime._tou_soc_migration_done = False
        runtime._migrate_selling_tou_soc()
        self.assertEqual(slot.tou_soc, 40)
        self.assertTrue(runtime._tou_soc_migration_done)

    def test_selling_tou_soc_restore_remains_none_when_no_safe_source_exists(self):
        # Without readback capability and without a finite minimum_sell_soc there
        # is no safe source to resolve tou_soc.
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = None
        slot.minimum_sell_soc = float("nan")
        self._mark_all_slot_entities_restored(runtime)
        runtime._tou_soc_migration_done = False
        runtime._migrate_selling_tou_soc()
        self.assertIsNone(slot.tou_soc)
        self.assertFalse(runtime._tou_soc_migration_done)

    def test_tou_soc_migration_is_idempotent(self):
        # Provider without readback capability: migration resolves once and must
        # not overwrite an already resolved value on subsequent ticks.
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = None
        slot.minimum_sell_soc = 40
        self._mark_all_slot_entities_restored(runtime)
        runtime._tou_soc_migration_done = False
        runtime._migrate_selling_tou_soc()
        self.assertEqual(slot.tou_soc, 40)
        self.assertTrue(runtime._tou_soc_migration_done)
        slot.minimum_sell_soc = 80
        runtime._tou_soc_migration_done = False
        runtime._migrate_selling_tou_soc()
        self.assertEqual(slot.tou_soc, 40)
        self.assertTrue(runtime._tou_soc_migration_done)

    def test_selling_tou_soc_migration_waits_for_required_restored_entities(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = None
        slot.minimum_sell_soc = 40
        runtime._tou_soc_migration_done = False
        # Do not mark any entities restored.
        runtime._migrate_selling_tou_soc()
        self.assertIsNone(slot.tou_soc)
        self.assertFalse(runtime._tou_soc_migration_done)

    def test_tou_soc_migration_retries_when_existing_entity_is_unavailable(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_SELLING_FIRST
        slot.tou_soc = None
        slot.minimum_sell_soc = float("nan")
        for idx in range(1, 7):
            runtime.hass.states.values[f"time.deye_inverter_time_of_use_{idx}_start"] = FakeState("unavailable")
        self._mark_all_slot_entities_restored(runtime)
        runtime._tou_soc_migration_done = False
        # First attempt: no safe source, migration stays incomplete.
        runtime._migrate_selling_tou_soc()
        self.assertIsNone(slot.tou_soc)
        self.assertFalse(runtime._tou_soc_migration_done)
        # Provider becomes readable, minimum_sell_soc is still missing.
        self._configure_distinct_physical_tou_starts(runtime)
        runtime._migrate_selling_tou_soc()
        self.assertEqual(slot.tou_soc, 20)
        self.assertTrue(runtime._tou_soc_migration_done)

    def test_sale_currently_resumes_above_minimum_sell_soc_without_hysteresis(self):
        runtime = make_runtime(soc="34")
        active = configure_selling_slot(runtime)
        active.minimum_sell_soc = 35
        active.tou_soc = 15
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ ZABLOKOWANA")
        # SOC rises above the threshold; sale should resume immediately.
        runtime.hass.states.values[const.DEFAULT_BATTERY_SOC] = FakeState("36")
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SPRZEDAŻ AKTYWNA")
        self.assertEqual(runtime.target_mode, const.MODE_SELLING_FIRST)
        self.assertEqual(runtime.target_sell_power, 5000)


class ProviderMappingTests(unittest.TestCase):
    """Provider adapters must translate controls without changing the logical plan."""

    @staticmethod
    def _set_valid_tou_starts(runtime, hours=(0, 4, 8, 12, 16, 20)):
        for idx, hour in enumerate(hours, start=1):
            entity_id = runtime._tou_entity(idx, "start")
            state = runtime.hass.states.get(entity_id)
            attrs = {} if state is None else dict(state.attributes)
            runtime.hass.states.values[entity_id] = FakeState(f"{hour:02d}:00:00", attrs)
            soc_entity = runtime._tou_entity(idx, "soc")
            soc_state = runtime.hass.states.get(soc_entity)
            soc_attrs = {} if soc_state is None else dict(soc_state.attributes)
            runtime.hass.states.values[soc_entity] = FakeState(str(idx * 10), soc_attrs)

    @staticmethod
    def _add_solarman_entities(runtime):
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_SOLARMAN
        runtime.data[const.CONF_WORK_MODE_SELECT] = "select.solarman_work_mode"
        runtime.hass.states.values["select.solarman_work_mode"] = FakeState(
            "Zero Export To Load",
            {"options": ["Export First", "Zero Export To Load", "Zero Export To CT"]},
        )
        for idx in range(1, 7):
            start = f"time.solarman_program_{idx}_time"
            soc = f"number.solarman_program_{idx}_soc"
            grid = f"select.solarman_program_{idx}_charging"
            runtime.data[const.conf_tou_entity(idx, "start")] = start
            runtime.data[const.conf_tou_entity(idx, "soc")] = soc
            runtime.data[const.conf_tou_entity(idx, "grid")] = grid
            runtime.hass.states.values[start] = FakeState("00:00:00")
            runtime.hass.states.values[soc] = FakeState("20", {"min": 0, "max": 100, "step": 1})
            runtime.hass.states.values[grid] = FakeState(
                "Disabled", {"options": ["Disabled", "Grid", "Generator", "Both"]}
            )

    @staticmethod
    def _add_sunsynk_entities(runtime):
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_SUNSYNK
        runtime.data[const.CONF_WORK_MODE_SELECT] = "select.sunsynk_load_limit"
        runtime.data[const.CONF_WORK_MODE_AUX_ENTITY] = "switch.sunsynk_solar_export"
        runtime.hass.states.values["select.sunsynk_load_limit"] = FakeState(
            "Essentials", {"options": ["Allow Export", "Essentials", "Zero Export"]}
        )
        runtime.hass.states.values["switch.sunsynk_solar_export"] = FakeState("off")
        time_options = [f"{hour:02d}:00" for hour in range(24)]
        for idx in range(1, 7):
            start = f"select.sunsynk_prog_{idx}_time"
            soc = f"number.sunsynk_prog_{idx}_capacity"
            grid = f"select.sunsynk_prog_{idx}_charge"
            runtime.data[const.conf_tou_entity(idx, "start")] = start
            runtime.data[const.conf_tou_entity(idx, "soc")] = soc
            runtime.data[const.conf_tou_entity(idx, "grid")] = grid
            runtime.hass.states.values[start] = FakeState("00:00", {"options": time_options})
            runtime.hass.states.values[soc] = FakeState("20", {"min": 0, "max": 100, "step": 1})
            runtime.hass.states.values[grid] = FakeState(
                "No Grid or Gen",
                {"options": ["No Grid or Gen", "Allow Grid", "Allow Gen", "Allow Grid & Gen"]},
            )

    def test_solarman_translates_work_mode_and_complete_tou_map(self):
        runtime = make_runtime()
        self._add_solarman_entities(runtime)
        # Make every charging source differ from the planned disabled state.
        for idx in range(1, 7):
            runtime.hass.states.values[f"select.solarman_program_{idx}_charging"] = FakeState(
                "Grid", {"options": ["Disabled", "Grid", "Generator", "Both"]}
            )

        asyncio.run(runtime.async_set_work_mode(const.MODE_SELLING_FIRST))
        self.assertIn(
            ("select", "select_option", {"entity_id": "select.solarman_work_mode", "option": "Export First"}, True),
            runtime.hass.services.calls,
        )

        runtime.hass.services.calls.clear()
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        self.assertFalse(any(
            data.get("entity_id") == "select.solarman_time_of_use"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))
        self.assertTrue(any(
            domain == "time" and service == "set_value"
            for domain, service, _data, _blocking in runtime.hass.services.calls
        ))
        grid_calls = [
            data for domain, service, data, _blocking in runtime.hass.services.calls
            if domain == "select" and service == "select_option" and "charging" in data.get("entity_id", "")
        ]
        self.assertEqual(len(grid_calls), 6)
        self.assertTrue(all(item["option"] == "Disabled" for item in grid_calls))

    def test_solarman_accepts_disable_alias_and_uses_grid_only_for_charge(self):
        runtime = make_runtime()
        self._add_solarman_entities(runtime)
        grid_entity = "select.solarman_program_1_charging"
        runtime.hass.states.values[grid_entity] = FakeState(
            "Disable", {"options": ["Disable", "Grid", "Generator", "Both"]}
        )

        asyncio.run(runtime.async_set_boolean_control(grid_entity, False, "grid"))
        self.assertEqual(
            runtime.hass.services.calls[-1],
            ("select", "select_option", {"entity_id": grid_entity, "option": "Disable"}, True),
        )

        asyncio.run(runtime.async_set_boolean_control(grid_entity, True, "grid"))
        self.assertEqual(
            runtime.hass.services.calls[-1],
            ("select", "select_option", {"entity_id": grid_entity, "option": "Grid"}, True),
        )

    def test_manual_tou_slot_edit_updates_range_and_next_boundary(self):
        runtime = make_runtime()
        self._set_valid_tou_starts(runtime, (0, 4, 6, 10, 16, 20))

        asyncio.run(
            runtime.async_set_physical_tou_slot(
                3,
                "08:00",
                "09:00",
                100,
                True,
            )
        )

        self.assertEqual(
            runtime.hass.states.get("time.deye_inverter_time_of_use_3_start").state,
            "08:00:00",
        )
        self.assertEqual(
            runtime.hass.states.get("time.deye_inverter_time_of_use_4_start").state,
            "09:00:00",
        )
        self.assertEqual(
            runtime.hass.states.get("number.deye_inverter_time_of_use_3_soc").state,
            "100.0",
        )
        self.assertEqual(
            runtime.hass.states.get(
                "switch.deye_inverter_time_of_use_3_grid_charge"
            ).state,
            "on",
        )

    def test_sunsynk_uses_safe_composite_mode_order_and_select_tou(self):
        runtime = make_runtime()
        self._add_sunsynk_entities(runtime)
        # Make at least one time slot and every charging source differ from plan.
        runtime.hass.states.values["select.sunsynk_prog_1_time"] = FakeState(
            "01:00", {"options": [f"{h:02d}:00" for h in range(24)]}
        )
        for idx in range(1, 7):
            runtime.hass.states.values[f"select.sunsynk_prog_{idx}_charge"] = FakeState(
                "Allow Grid", {"options": ["No Grid or Gen", "Allow Grid", "Allow Gen", "Allow Grid & Gen"]}
            )

        asyncio.run(runtime.async_set_work_mode(const.MODE_SELLING_FIRST))

        self.assertEqual(runtime.hass.services.calls[-2][0:2], ("select", "select_option"))
        self.assertEqual(runtime.hass.services.calls[-2][2]["option"], "Allow Export")
        self.assertEqual(runtime.hass.services.calls[-1][0:2], ("switch", "turn_on"))

        runtime.hass.services.calls.clear()
        asyncio.run(runtime.async_set_work_mode(const.MODE_ZERO_EXPORT))
        self.assertEqual(runtime.hass.services.calls[0][0:2], ("switch", "turn_off"))
        self.assertEqual(runtime.hass.services.calls[1][0:2], ("select", "select_option"))
        self.assertEqual(runtime.hass.services.calls[1][2]["option"], "Essentials")

        runtime.hass.services.calls.clear()
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertFalse(any(
            data.get("entity_id") == "switch.sunsynk_use_timer"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))
        self.assertTrue(any(
            domain == "select" and service == "select_option" and "prog_1_time" in data.get("entity_id", "")
            for domain, service, data, _blocking in runtime.hass.services.calls
        ))
        self.assertTrue(all(
            data["option"] == "No Grid or Gen"
            for domain, service, data, _blocking in runtime.hass.services.calls
            if domain == "select" and service == "select_option" and "_charge" in data.get("entity_id", "")
        ))

        grid_entity = "select.sunsynk_prog_1_charge"
        asyncio.run(runtime.async_set_boolean_control(grid_entity, True, "grid"))
        self.assertEqual(
            runtime.hass.services.calls[-1],
            ("select", "select_option", {"entity_id": grid_entity, "option": "Allow Grid"}, True),
        )

    def test_global_tou_entity_is_never_written_for_lewa_reka(self):
        runtime = make_runtime()
        # Make every physical grid switch differ from the planned disabled state
        # so the diff-plan actually writes all six grid entities.
        for idx in range(1, 7):
            runtime.hass.states.values[f"switch.deye_inverter_time_of_use_{idx}_grid_charge"] = FakeState("on")
        runtime.hass.services.calls.clear()

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        self.assertFalse(any(
            data.get("entity_id") == "switch.deye_inverter_time_of_use"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))
        grid_calls = [
            data
            for domain, service, data, _blocking in runtime.hass.services.calls
            if domain == "switch"
            and service in ("turn_on", "turn_off")
            and "_grid_charge" in data.get("entity_id", "")
        ]
        self.assertEqual(len(grid_calls), 6)

    def test_global_tou_entity_is_never_written_for_solarman(self):
        runtime = make_runtime()
        self._add_solarman_entities(runtime)
        # Make every charging source differ from the planned disabled state.
        for idx in range(1, 7):
            runtime.hass.states.values[f"select.solarman_program_{idx}_charging"] = FakeState(
                "Grid", {"options": ["Disabled", "Grid", "Generator", "Both"]}
            )
        runtime.hass.states.values["select.solarman_time_of_use"] = FakeState(
            "Disabled", {"options": ["Disabled", "Week"]}
        )
        runtime.hass.services.calls.clear()

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        self.assertFalse(any(
            data.get("entity_id") == "select.solarman_time_of_use"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))

    def test_global_tou_entity_is_never_written_for_sunsynk(self):
        runtime = make_runtime()
        self._add_sunsynk_entities(runtime)
        # Make every charging source differ from the planned disabled state.
        for idx in range(1, 7):
            runtime.hass.states.values[f"select.sunsynk_prog_{idx}_charge"] = FakeState(
                "Allow Grid", {"options": ["No Grid or Gen", "Allow Grid", "Allow Gen", "Allow Grid & Gen"]}
            )
        runtime.hass.states.values["switch.sunsynk_use_timer"] = FakeState("off")
        runtime.hass.services.calls.clear()

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        self.assertFalse(any(
            data.get("entity_id") == "switch.sunsynk_use_timer"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))

    def test_missing_global_tou_does_not_block_setup(self):
        runtime = make_runtime()
        runtime.hass.states.values.pop("switch.deye_inverter_time_of_use", None)
        # Make a grid switch differ so the diff-plan produces a switch call.
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertEqual(runtime.last_error, "")
        self.assertTrue(any(
            domain == "switch" and service in ("turn_on", "turn_off")
            for domain, service, _data, _blocking in runtime.hass.services.calls
        ))

    def test_missing_global_tou_does_not_reduce_provider_capabilities(self):
        runtime = make_runtime()
        capabilities = runtime.provider_capabilities()

        self.assertIn("full_tou", capabilities)
        self.assertNotIn("switch.deye_inverter_time_of_use", capabilities["full_tou"]["missing"])
        self.assertNotIn("tou_enable_entity", capabilities["operations"])

    def test_old_global_tou_key_in_entry_data_is_ignored(self):
        runtime = make_runtime()
        runtime.data["tou_enable_entity"] = "switch.deye_inverter_time_of_use"
        runtime.data["tou_enable_option"] = "Week"
        runtime.data["tou_disable_option"] = "Disabled"

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertNotIn("switch.deye_inverter_time_of_use", [
            data.get("entity_id")
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ])

    def test_old_global_tou_key_in_entry_options_is_ignored(self):
        runtime = make_runtime()
        runtime.data["tou_enable_entity"] = "switch.deye_inverter_time_of_use"
        runtime.hass.services.calls.clear()

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertFalse(any(
            data.get("entity_id") == "switch.deye_inverter_time_of_use"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))

    def test_global_tou_entity_is_not_in_control_snapshot(self):
        runtime = make_runtime()
        runtime.data[const.CONF_WORK_MODE_SELECT] = const.DEFAULT_WORK_MODE_SELECT
        snapshot, missing = runtime._control_entities_to_write(const.MODE_SELLING_FIRST)

        self.assertFalse(missing)
        self.assertNotIn("switch.deye_inverter_time_of_use", snapshot)

    def test_global_tou_entity_is_not_in_physical_tou_snapshot(self):
        runtime = make_runtime()
        snapshot = runtime._tou_raw_snapshot()

        self.assertNotIn("switch.deye_inverter_time_of_use", snapshot)
        for idx in range(1, 7):
            self.assertIn(f"time.deye_inverter_time_of_use_{idx}_start", snapshot)
            self.assertIn(f"number.deye_inverter_time_of_use_{idx}_soc", snapshot)
            self.assertIn(f"switch.deye_inverter_time_of_use_{idx}_grid_charge", snapshot)

    def test_global_tou_entity_is_not_restored_by_tou_rollback(self):
        runtime = make_runtime()
        before = runtime._tou_raw_snapshot()
        entity_id = "time.deye_inverter_time_of_use_2_start"
        old_value = before[entity_id]
        runtime.hass.states.values[entity_id] = FakeState("12:00:00")

        snapshot: dict[str, str] = {entity_id: old_value}
        item = runtime._make_tou_transaction_item(entity_id, "start", 2, old_value, snapshot)
        snapshot[entity_id] = old_value
        item["previous_logical_value"] = old_value
        item["written"] = True
        asyncio.run(runtime._async_rollback_tou_transaction([item], snapshot))

        restored = set(runtime._tou_raw_snapshot().keys())
        self.assertNotIn("switch.deye_inverter_time_of_use", restored)
        self.assertEqual(len(restored), len(before))
        self.assertEqual(runtime.hass.states.get(entity_id).state, old_value)

    def test_successful_tou_rollback_is_not_reported_as_mismatch(self):
        runtime = make_runtime()
        entity_id = "number.deye_inverter_time_of_use_1_soc"
        snapshot = {entity_id: "20"}
        item = runtime._make_tou_transaction_item(entity_id, "soc", 1, 55, snapshot)
        item["written"] = True
        runtime.hass.states.values[entity_id] = FakeState(
            "55", {"min": 0, "max": 100, "step": 1}
        )

        success, errors = asyncio.run(
            runtime._async_rollback_tou_transaction([item], snapshot)
        )

        self.assertTrue(success)
        self.assertEqual(errors, [])
        self.assertNotEqual(item["status"], "mismatch")

    def test_successful_tou_rollback_marks_restored_items_confirmed(self):
        runtime = make_runtime()
        entity_id = "number.deye_inverter_time_of_use_1_soc"
        snapshot = {entity_id: "20"}
        item = runtime._make_tou_transaction_item(entity_id, "soc", 1, 55, snapshot)
        item["written"] = True
        runtime.hass.states.values[entity_id] = FakeState(
            "55", {"min": 0, "max": 100, "step": 1}
        )

        success, _errors = asyncio.run(
            runtime._async_rollback_tou_transaction([item], snapshot)
        )

        self.assertTrue(success)
        self.assertTrue(item["confirmed"])

    def test_successful_tou_rollback_reports_rolled_back_status(self):
        runtime = make_runtime()
        entity_id = "number.deye_inverter_time_of_use_1_soc"
        snapshot = {entity_id: "20"}
        item = runtime._make_tou_transaction_item(entity_id, "soc", 1, 55, snapshot)
        item["written"] = True
        runtime.hass.states.values[entity_id] = FakeState(
            "55", {"min": 0, "max": 100, "step": 1}
        )

        asyncio.run(runtime._async_rollback_tou_transaction([item], snapshot))

        self.assertEqual(item["status"], "rolled_back")
        self.assertEqual(item["legacy_status"], "rollback_confirmed")

    def test_global_tou_entity_is_not_required_for_tou_mapping(self):
        runtime = make_runtime()
        runtime.hass.states.values.pop("switch.deye_inverter_time_of_use", None)
        # Make a grid switch differ so the diff-plan produces a switch call.
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertTrue(any(
            domain == "switch" and service in ("turn_on", "turn_off")
            for domain, service, _data, _blocking in runtime.hass.services.calls
        ))

    def test_global_tou_entity_is_not_required_for_manual_tou_save(self):
        runtime = make_runtime()
        runtime.hass.states.values.pop("switch.deye_inverter_time_of_use", None)
        self._set_valid_tou_starts(runtime, (0, 2, 6, 10, 16, 20))

        asyncio.run(runtime.async_set_physical_tou_slot(2, "03:00", "04:00", 55, True))

        self.assertEqual(
            runtime.hass.states.get("time.deye_inverter_time_of_use_2_start").state,
            "03:00:00",
        )
        self.assertEqual(
            runtime.hass.states.get("time.deye_inverter_time_of_use_3_start").state,
            "04:00:00",
        )

    def test_six_physical_tou_slots_remain_supported(self):
        runtime = make_runtime()
        entities = runtime._tou_entities()

        self.assertEqual(len(entities), 18)
        for idx in range(1, 7):
            self.assertEqual(runtime._tou_entity(idx, "start"), f"time.deye_inverter_time_of_use_{idx}_start")
            self.assertEqual(runtime._tou_entity(idx, "soc"), f"number.deye_inverter_time_of_use_{idx}_soc")
            self.assertEqual(runtime._tou_entity(idx, "grid"), f"switch.deye_inverter_time_of_use_{idx}_grid_charge")

    def test_custom_provider_does_not_require_global_tou(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        runtime.data[const.CONF_WORK_MODE_SELECT] = "select.custom_work_mode"
        runtime.data[const.CONF_WORK_MODE_SELL_OPTION] = "CUSTOM SELL"
        runtime.data[const.CONF_WORK_MODE_ZERO_LOAD_OPTION] = "CUSTOM LOAD"
        runtime.data[const.CONF_WORK_MODE_ZERO_CT_OPTION] = "CUSTOM CT"
        runtime.data[const.CONF_TOU_GRID_ENABLE_OPTION] = "GRID"
        runtime.data[const.CONF_TOU_GRID_DISABLE_OPTION] = "NO GRID"
        runtime.hass.states.values["select.custom_work_mode"] = FakeState(
            "CUSTOM LOAD", {"options": ["CUSTOM SELL", "CUSTOM LOAD", "CUSTOM CT"]}
        )
        for idx in range(1, 7):
            start = f"select.custom_tou_{idx}_time"
            soc = f"number.custom_tou_{idx}_soc"
            grid = f"select.custom_tou_{idx}_grid"
            runtime.data[const.conf_tou_entity(idx, "start")] = start
            runtime.data[const.conf_tou_entity(idx, "soc")] = soc
            runtime.data[const.conf_tou_entity(idx, "grid")] = grid
            runtime.hass.states.values[start] = FakeState("00:00", {"options": [f"{h:02d}:00" for h in range(24)]})
            runtime.hass.states.values[soc] = FakeState("20", {"min": 0, "max": 100, "step": 1})
            runtime.hass.states.values[grid] = FakeState("NO GRID", {"options": ["NO GRID", "GRID"]})

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertFalse(any(
            "tou_enable" in str(data.get("entity_id", ""))
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))

    def test_solarman_disabled_slot_is_not_global_tou_disable(self):
        runtime = make_runtime()
        self._add_solarman_entities(runtime)
        # Make every charging source differ from the planned disabled state.
        for idx in range(1, 7):
            runtime.hass.states.values[f"select.solarman_program_{idx}_charging"] = FakeState(
                "Grid", {"options": ["Disabled", "Grid", "Generator", "Both"]}
            )
        runtime.hass.states.values["select.solarman_time_of_use"] = FakeState(
            "Disabled", {"options": ["Disabled", "Week"]}
        )
        runtime.hass.services.calls.clear()

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        self.assertFalse(any(
            data.get("entity_id") == "select.solarman_time_of_use"
            for _domain, _service, data, _blocking in runtime.hass.services.calls
        ))
        program_calls = [
            data for _domain, _service, data, _blocking in runtime.hass.services.calls
            if data.get("entity_id", "").startswith("select.solarman_program_") and data.get("entity_id", "").endswith("_charging")
        ]
        self.assertEqual(len(program_calls), 6)
        self.assertTrue(all(
            call["option"] == "Disabled"
            for call in program_calls
        ))

    def test_deye_addon_without_native_tou_fails_closed_before_service_call(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        calls_before = list(runtime.hass.services.calls)

        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertIn("nie udostępnia bezpiecznego sterowania Time Of Use", runtime.last_error)
        self.assertEqual(runtime.hass.services.calls, calls_before)

    def test_custom_mapping_uses_only_explicit_option_values(self):
        runtime = make_runtime()
        runtime.data.update({
            const.CONF_INVERTER_PROVIDER: const.PROVIDER_CUSTOM,
            const.CONF_WORK_MODE_SELL_OPTION: "CUSTOM SELL",
            const.CONF_WORK_MODE_ZERO_LOAD_OPTION: "CUSTOM LOAD",
            const.CONF_WORK_MODE_ZERO_CT_OPTION: "CUSTOM CT",
        })
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState(
            "CUSTOM LOAD", {"options": ["CUSTOM SELL", "CUSTOM LOAD", "CUSTOM CT"]}
        )

        asyncio.run(runtime.async_set_work_mode(const.MODE_SELLING_FIRST))

        self.assertEqual(runtime.hass.services.calls[-1][2]["option"], "CUSTOM SELL")

    def test_custom_provider_normalizes_tou_grid_select(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        runtime.data[const.CONF_WORK_MODE_SELECT] = "select.custom_work_mode"
        runtime.data[const.CONF_TOU_GRID_ENABLE_OPTION] = "CUSTOM GRID"
        runtime.data[const.CONF_TOU_GRID_DISABLE_OPTION] = "CUSTOM OFF"
        runtime.hass.states.values["select.custom_work_mode"] = FakeState(
            "CUSTOM LOAD", {"options": ["CUSTOM SELL", "CUSTOM LOAD", "CUSTOM CT"]}
        )
        for idx in range(1, 7):
            start = f"select.custom_tou_{idx}_time"
            soc = f"number.custom_tou_{idx}_soc"
            grid = f"select.custom_tou_{idx}_grid"
            runtime.data[const.conf_tou_entity(idx, "start")] = start
            runtime.data[const.conf_tou_entity(idx, "soc")] = soc
            runtime.data[const.conf_tou_entity(idx, "grid")] = grid
            runtime.hass.states.values[start] = FakeState("00:00", {"options": [f"{h:02d}:00" for h in range(24)]})
            runtime.hass.states.values[soc] = FakeState("20", {"min": 0, "max": 100, "step": 1})
            runtime.hass.states.values[grid] = FakeState(
                "CUSTOM OFF", {"options": ["CUSTOM OFF", "CUSTOM GRID"]}
            )
        # Make one grid source differ from the planned disabled state.
        runtime.hass.states.values["select.custom_tou_1_grid"] = FakeState(
            "CUSTOM GRID", {"options": ["CUSTOM OFF", "CUSTOM GRID"]}
        )
        runtime.hass.services.calls.clear()

        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        grid_calls = [
            data
            for domain, service, data, _blocking in runtime.hass.services.calls
            if domain == "select" and service == "select_option" and "_grid" in data.get("entity_id", "")
        ]
        self.assertEqual(len(grid_calls), 1)
        self.assertEqual(grid_calls[0]["option"], "CUSTOM OFF")
        self.assertEqual(grid_calls[0]["entity_id"], "select.custom_tou_1_grid")

    def test_unconfirmed_tou_write_is_rolled_back_to_exact_previous_map(self):

        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0.1
        before = {
            entity_id: state.state
            for entity_id, state in runtime.hass.states.values.items()
            if "time_of_use" in entity_id
        }
        runtime.hass.services.ignore_once(
            "time",
            "set_value",
            entity_id="time.deye_inverter_time_of_use_2_start",
        )

        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))

        after = {
            entity_id: state.state
            for entity_id, state in runtime.hass.states.values.items()
            if "time_of_use" in entity_id
        }
        for entity_id, previous in before.items():
            if entity_id.startswith("number."):
                self.assertAlmostEqual(float(after[entity_id]), float(previous))
            else:
                self.assertEqual(after[entity_id], previous)
        self.assertIn("Przywrócono poprzednie ustawienia", runtime.last_error)
        self.assertEqual(runtime._last_tou_signature, "")

    def test_deye_addon_reports_read_only_control_capabilities(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON

        capabilities = runtime.provider_capabilities()

        self.assertFalse(capabilities["basic_control"]["supported"])
        self.assertFalse(capabilities["selling"]["supported"])
        self.assertFalse(capabilities["charging"]["supported"])
        self.assertFalse(capabilities["full_tou"]["supported"])
        self.assertIn("nie udostępnia", capabilities["provider"]["note"])

    def test_capability_operations_describe_real_home_assistant_services(self):
        runtime = make_runtime()
        operations = runtime.provider_capabilities()["operations"]

        self.assertEqual(operations["work_mode"]["operation"], "select.select_option")
        self.assertEqual(operations["sell_power"]["operation"], "number.set_value")
        self.assertNotIn("tou_enable", operations)
        self.assertEqual(operations["tou_1_start"]["operation"], "time.set_value")


class ProviderProfileValidationTests(unittest.TestCase):
    """Profile saves validate exact raw options exposed by each provider."""

    @staticmethod
    def _lewa_reka_runtime():
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_LEWA_REKA
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState(
            const.MODE_ZERO_EXPORT,
            {"options": ["Selling First", const.MODE_ZERO_EXPORT, const.MODE_ZERO_EXPORT_CT]},
        )
        return runtime

    @staticmethod
    def _solarman_runtime():
        runtime = make_runtime()
        ProviderMappingTests._add_solarman_entities(runtime)
        return runtime

    @staticmethod
    def _sunsynk_runtime():
        runtime = make_runtime()
        ProviderMappingTests._add_sunsynk_entities(runtime)
        return runtime

    @staticmethod
    def _custom_runtime(*, load="CUSTOM LOAD", ct="CUSTOM CT", sell="CUSTOM SELL"):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        if load is not None:
            runtime.data[const.CONF_WORK_MODE_ZERO_LOAD_OPTION] = load
        if ct is not None:
            runtime.data[const.CONF_WORK_MODE_ZERO_CT_OPTION] = ct
        if sell is not None:
            runtime.data[const.CONF_WORK_MODE_SELL_OPTION] = sell
        runtime.data[const.conf_tou_entity(1, "soc")] = "number.deye_inverter_time_of_use_1_soc"
        options = [item for item in (sell, load, ct) if item is not None]
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState(
            options[0] if options else "unknown",
            {"options": options},
        )
        return runtime

    @staticmethod
    def _default_values(mode, physical_mode=const.MODE_ZERO_EXPORT):
        return {
            "mode": mode,
            "physical_work_mode": physical_mode,
            "sell_power": 3000,
            "discharge_current": 80,
            "charge_current": 70,
            "grid_charge_current": 40,
        }

    @staticmethod
    def _normal_values(physical_mode):
        return {
            "physical_work_mode": physical_mode,
            "sell_power": 3000,
            "discharge_current": 80,
            "charge_current": 70,
            "grid_charge_current": 40,
            "tou_soc": 20,
        }

    def test_save_default_settings_normalna_praca_lewa_reka_with_real_select_options(self):
        runtime = self._lewa_reka_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_NORMAL_OPERATION)))
        self.assertEqual(runtime.default_work_mode, const.MODE_NORMAL_OPERATION)

    def test_save_default_settings_sprzedaz_lewa_reka_with_real_select_options(self):
        runtime = self._lewa_reka_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_SELLING_FIRST)))
        self.assertEqual(runtime.default_work_mode, const.MODE_SELLING_FIRST)

    def test_save_default_settings_normalna_praca_solarman_with_real_select_options(self):
        runtime = self._solarman_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_NORMAL_OPERATION)))
        self.assertEqual(runtime.default_physical_work_mode, const.MODE_ZERO_EXPORT)

    def test_save_default_settings_sprzedaz_solarman_with_real_select_options(self):
        runtime = self._solarman_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_SELLING_FIRST)))
        self.assertEqual(runtime.default_work_mode, const.MODE_SELLING_FIRST)

    def test_save_default_settings_normalna_praca_sunsynk_with_real_select_options(self):
        runtime = self._sunsynk_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_NORMAL_OPERATION)))
        self.assertEqual(runtime.default_physical_work_mode, const.MODE_ZERO_EXPORT)

    def test_save_default_settings_sprzedaz_sunsynk_with_real_select_options(self):
        runtime = self._sunsynk_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_SELLING_FIRST)))
        self.assertEqual(runtime.default_work_mode, const.MODE_SELLING_FIRST)

    def test_save_default_settings_normalna_praca_custom_with_real_select_options(self):
        runtime = self._custom_runtime()
        asyncio.run(runtime.async_save_default_settings(self._default_values(const.MODE_NORMAL_OPERATION)))
        self.assertEqual(runtime.default_physical_work_mode, const.MODE_ZERO_EXPORT)

    def test_save_normal_profile_lewa_reka_translates_canonical_variant(self):
        runtime = self._lewa_reka_runtime()
        asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT_CT)))
        self.assertEqual(runtime.normal_profile_physical_work_mode, const.MODE_ZERO_EXPORT_CT)

    def test_save_normal_profile_solarman_translates_canonical_variant(self):
        runtime = self._solarman_runtime()
        asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT_CT)))
        self.assertEqual(runtime.normal_profile_physical_work_mode, const.MODE_ZERO_EXPORT_CT)

    def test_save_normal_profile_sunsynk_load_maps_to_essentials(self):
        runtime = self._sunsynk_runtime()
        asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT)))
        self.assertEqual(runtime.normal_profile_physical_work_mode, const.MODE_ZERO_EXPORT)

    def test_save_normal_profile_sunsynk_ct_maps_to_zero_export(self):
        runtime = self._sunsynk_runtime()
        asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT_CT)))
        self.assertEqual(runtime.normal_profile_physical_work_mode, const.MODE_ZERO_EXPORT_CT)

    def test_save_normal_profile_custom_uses_configured_raw_option(self):
        runtime = self._custom_runtime()
        asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT_CT)))
        self.assertEqual(runtime.normal_profile_physical_work_mode, const.MODE_ZERO_EXPORT_CT)

    def test_save_normal_profile_rejects_missing_custom_provider_option(self):
        runtime = self._custom_runtime(load=None)
        with self.assertRaisesRegex(ValueError, "Brak skonfigurowanej opcji"):
            asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT)))

    def test_normal_profile_validation_checks_translated_provider_option_not_canonical_key(self):
        runtime = self._sunsynk_runtime()
        state = runtime.hass.states.get(runtime.work_mode_select)
        self.assertNotIn(const.MODE_ZERO_EXPORT, state.attributes["options"])
        asyncio.run(runtime.async_save_normal_profile(self._normal_values(const.MODE_ZERO_EXPORT)))

    def test_custom_metadata_exposes_only_configured_normal_variant(self):
        runtime = self._custom_runtime(load="Essentials", ct=None)
        rows = manager.normal_profile_mode_metadata(runtime.data)
        self.assertEqual(
            [row for row in rows if row["available"]],
            [{
                "value": const.MODE_ZERO_EXPORT,
                "label": "Eksport wyłączony — pomiar Load",
                "available": True,
            }],
        )

    def test_apply_defaults_uses_explicit_physical_variant_not_active_profile(self):
        runtime = self._lewa_reka_runtime()
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        runtime.default_physical_work_mode = const.MODE_ZERO_EXPORT
        runtime.default_work_mode = const.MODE_NORMAL_OPERATION

        self.assertTrue(asyncio.run(runtime.async_apply_safe_defaults("Test 5F.1")))

        mode_calls = [
            call for call in runtime.hass.services.calls
            if call[0] == "select" and call[1] == "select_option"
        ]
        self.assertEqual(mode_calls[-1][2]["option"], const.MODE_ZERO_EXPORT)


class ChargeProfilePersistenceTests(unittest.TestCase):
    class MemoryStore:
        def __init__(self, value=None, fail=False):
            self.value = value
            self.fail = fail

        async def async_save(self, value):
            if self.fail:
                raise RuntimeError("storage unavailable")
            self.value = value

        async def async_load(self):
            return self.value

    @staticmethod
    def profile(grid_enabled=True, charge_current=120, discharge_current=35,
                grid_charge_current=60, target_soc=90):
        return {
            "charge_current": charge_current,
            "discharge_current": discharge_current,
            "grid_charge_current": grid_charge_current,
            "target_soc": target_soc,
            "grid_charge_enabled": grid_enabled,
        }

    def load_from_store(self, store):
        runtime = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            asyncio.run(runtime.async_load_ai_data())
        finally:
            manager.Store = previous_store
        return runtime

    def test_complete_profile_with_grid_yes_survives_restart(self):
        store = self.MemoryStore()
        runtime = make_runtime()
        runtime._ai_store = store
        asyncio.run(runtime.async_save_charge_profile(self.profile()))

        self.assertEqual(store.value["charge_profile"], {
            "charge_current": 120.0,
            "discharge_current": 35.0,
            "grid_charge_current": 60.0,
            "target_soc": 90.0,
            "grid_charge_enabled": True,
        })
        reloaded = self.load_from_store(store)
        self.assertTrue(reloaded._charge_profile_loaded_from_store)
        self.assertTrue(reloaded.charge_profile_grid_enabled)
        self.assertEqual(reloaded.charge_profile_charge_current, 120)
        self.assertEqual(reloaded.charge_profile_discharge_current, 35)
        self.assertEqual(reloaded.charge_profile_grid_charge_current, 60)
        self.assertEqual(reloaded.charge_profile_target_soc, 90)

    def test_complete_profile_with_grid_no_and_different_values_survives_restart(self):
        store = self.MemoryStore()
        runtime = make_runtime()
        runtime._ai_store = store
        asyncio.run(runtime.async_save_charge_profile(self.profile(
            grid_enabled=False,
            charge_current=75,
            discharge_current=25,
            grid_charge_current=15,
            target_soc=82,
        )))

        reloaded = self.load_from_store(store)
        self.assertFalse(reloaded.charge_profile_grid_enabled)
        self.assertEqual(reloaded.charge_profile_charge_current, 75)
        self.assertEqual(reloaded.charge_profile_discharge_current, 25)
        self.assertEqual(reloaded.charge_profile_grid_charge_current, 15)
        self.assertEqual(reloaded.charge_profile_target_soc, 82)

    def test_invalid_profile_keeps_previous_runtime_and_stored_record(self):
        store = self.MemoryStore()
        runtime = make_runtime()
        runtime._ai_store = store
        asyncio.run(runtime.async_save_charge_profile(self.profile()))
        stored_before = dict(store.value["charge_profile"])

        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_save_charge_profile(self.profile(charge_current=float("nan"))))

        self.assertEqual(runtime.charge_profile_charge_current, 120)
        self.assertEqual(store.value["charge_profile"], stored_before)

    def test_failed_durable_write_rolls_back_complete_runtime_profile(self):
        runtime = make_runtime()
        runtime.charge_profile_charge_current = 101
        runtime.charge_profile_discharge_current = 31
        runtime.charge_profile_grid_charge_current = 41
        runtime.charge_profile_target_soc = 81
        runtime.charge_profile_grid_enabled = False
        runtime._charge_profile_loaded_from_store = True
        runtime._ai_store = self.MemoryStore(fail=True)

        with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
            asyncio.run(runtime.async_save_charge_profile(self.profile()))

        self.assertEqual(runtime.charge_profile_charge_current, 101)
        self.assertEqual(runtime.charge_profile_discharge_current, 31)
        self.assertEqual(runtime.charge_profile_grid_charge_current, 41)
        self.assertEqual(runtime.charge_profile_target_soc, 81)
        self.assertFalse(runtime.charge_profile_grid_enabled)
        self.assertTrue(runtime._charge_profile_loaded_from_store)


class PlanExecutionArchiveTests(unittest.TestCase):
    @staticmethod
    def plan(*, pv_future=2.0):
        return {
            "plan_id": "plan-a",
            "generated_at": "2026-07-18T12:00:00+00:00",
            "strategy": "balanced",
            "rows": [
                {
                    "date": "2026-07-18", "hour": 11, "label": "11:00–12:00",
                    "action": "none", "proposed": False, "dispatch_status": "skipped",
                    "corrected_pv_kwh": 1.0, "load_kwh": 0.5,
                    "expected_import_kwh": 0, "expected_export_kwh": 0.5,
                    "soc_end_pct": 60, "confidence": 80,
                },
                {
                    "date": "2026-07-18", "hour": 13, "label": "13:00–14:00",
                    "action": "sell", "proposed": True, "dispatch_status": "planned",
                    "profile_id": "morning_sale", "planned_power_w": 3000,
                    "planned_energy_kwh": 1.2, "corrected_pv_kwh": pv_future,
                    "load_kwh": 0.8, "expected_import_kwh": 0,
                    "expected_export_kwh": 2.4, "soc_end_pct": 55,
                    "sell_price": 0.8, "net_result": 1.92, "confidence": 75,
                },
            ],
        }

    def test_past_hour_is_frozen_but_future_proposal_can_refresh(self):
        runtime = make_runtime()
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(runtime._sync_plan_execution_archive(self.plan(), now))
        changed = self.plan(pv_future=3.5)
        changed["rows"][0]["corrected_pv_kwh"] = 9.0
        runtime._sync_plan_execution_archive(changed, now)
        day = runtime.plan_execution_day("2026-07-18")
        self.assertEqual(1.0, day["rows"][0]["corrected_pv_kwh"])
        self.assertEqual(3.5, day["rows"][1]["corrected_pv_kwh"])
        self.assertIsNotNone(day["rows"][0]["frozen_at"])

    def test_finalized_measurement_is_attached_with_transparent_errors(self):
        runtime = make_runtime()
        runtime._sync_plan_execution_archive(
            self.plan(),
            datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
        )
        runtime._attach_plan_execution_actual({
            "local_date": "2026-07-18",
            "local_hour": 13,
            "pv_kwh": 1.5,
            "load_kwh": 1.0,
            "grid_import_kwh": 0.1,
            "grid_export_kwh": 1.8,
            "battery_charge_kwh": 0,
            "battery_discharge_kwh": 1.0,
            "soc_end": 53,
            "sell_price_avg": 0.8,
            "buy_price_avg": 1.2,
            "complete": True,
            "completeness_percent": 100,
            "tariff": {"distribution_rate": 0.2},
        })
        day = runtime.plan_execution_day("2026-07-18")
        row = next(item for item in day["rows"] if item["hour"] == 13)
        self.assertEqual("completed", row["actual_status"])
        self.assertEqual(1.5, row["actual"]["pv_kwh"])
        self.assertEqual(-25.0, row["errors"]["pv_percent"])
        self.assertEqual(2, day["summary"]["hours_planned"])
        self.assertEqual(1, day["summary"]["hours_measured"])

    def test_missing_measurements_are_not_recorded_as_zero_execution(self):
        runtime = make_runtime()
        runtime._sync_plan_execution_archive(
            self.plan(),
            datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
        )
        runtime._attach_plan_execution_actual({
            "local_date": "2026-07-18",
            "local_hour": 13,
            "pv_kwh": None,
            "load_kwh": None,
            "grid_import_kwh": None,
            "grid_export_kwh": None,
            "battery_charge_kwh": None,
            "battery_discharge_kwh": None,
            "soc_end": None,
            "sell_price_avg": None,
            "buy_price_avg": None,
            "complete": False,
            "completeness_percent": 0,
        })
        day = runtime.plan_execution_day("2026-07-18")
        row = next(item for item in day["rows"] if item["hour"] == 13)
        self.assertEqual("partial", row["actual_status"])
        self.assertIsNone(row["actual"]["pv_kwh"])
        self.assertIsNone(row["actual"]["grid_import_kwh"])
        self.assertIsNone(row["actual"]["net_result_pln"])
        self.assertIsNone(row["errors"]["pv_kwh"])

    def test_invalid_history_date_is_rejected(self):
        runtime = make_runtime()
        with self.assertRaisesRegex(ValueError, "RRRR-MM-DD"):
            runtime.plan_execution_day("18-07-2026")


class FuturePlanTests(unittest.TestCase):
    @staticmethod
    def mark_soc_reported(runtime, moment):
        """Represent the fresh source report required by future-sale revalidation."""
        state = runtime.hass.states.get(runtime.battery_soc_sensor)
        state.last_updated = moment
        state.last_reported = moment

    class MemoryStore:
        def __init__(self):
            self.value = None

        async def async_save(self, value):
            self.value = value

        async def async_load(self):
            return self.value

    def test_future_plan_is_stored_exactly_and_not_applied_early(self):
        runtime = make_runtime()
        runtime.learning_summary = lambda: {"learning_stage": {"apply_allowed": True}}
        runtime._ai_store = self.MemoryStore()
        runtime.plan_execution_archive = [{
            "date": "2026-07-19", "hour": 5,
            "approval_status": "not_selected",
            "deployment_status": "not_deployed",
        }]
        update = {
            "slot_key": "05_06", "enabled": True,
            "mode": const.MODE_SELLING_FIRST, "sell_power": 5000,
            "discharge_current": 120, "charge_current": 0,
            "grid_charge_current": 0, "minimum_sell_soc": 20, "min_sell_price": 0.9,
        }
        asyncio.run(runtime.async_save_future_plan({
            "date": "2026-07-19", "strategy": "balanced",
            "labels": ["05:00–06:00"], "updates": [update],
        }))
        self.assertEqual("scheduled", runtime.future_plan["status"])
        self.assertEqual(24, len(runtime.future_plan["updates"]))
        self.assertEqual({key for key, _label, _start, _end in const.SLOTS}, {
            item["slot_key"] for item in runtime.future_plan["updates"]
        })
        self.assertEqual([{
            "slot_key": "05_06",
            "enabled": True,
            "mode": const.MODE_SELLING_FIRST,
            "sell_power": 5000,
        }], [
            item for item in runtime.future_plan["updates"]
            if item["slot_key"] == "05_06"
        ])
        self.assertTrue(runtime.future_plan["authoritative_day"])
        self.assertEqual(["05_06"], runtime.future_plan["selected_slot_keys"])
        self.assertEqual("approved", runtime.plan_execution_archive[0]["approval_status"])
        before = list(runtime.hass.services.calls)
        asyncio.run(runtime.async_process_future_plan())
        self.assertEqual(before, runtime.hass.services.calls)
        self.assertEqual("scheduled", runtime.future_plan["status"])

    def test_future_plan_rejects_wrong_date(self):
        runtime = make_runtime()
        runtime.learning_summary = lambda: {"learning_stage": {"apply_allowed": True}}
        runtime._ai_store = self.MemoryStore()
        with self.assertRaisesRegex(ValueError, "wyłącznie na jutro"):
            asyncio.run(runtime.async_save_future_plan({
                "date": "2026-07-18",
                "updates": [{"slot_key": "05_06", "mode": const.MODE_SELLING_FIRST}],
            }))

    def test_future_plan_survives_runtime_reload_and_can_be_cancelled(self):
        store = self.MemoryStore()
        store.value = {
            "settings": {}, "history": [], "last_saved_at": "",
            "future_plan": {
                "plan_id": "plan-cancel",
                "date": "2026-07-19", "status": "scheduled",
                "updates": [{
                    "slot_key": "05_06",
                    "mode": const.MODE_SELLING_FIRST,
                    "sell_power": 3000,
                }],
                "slot_validations": {
                    "05_06": {"profile_id": "morning_sale"},
                },
            },
        }
        runtime = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            asyncio.run(runtime.async_load_ai_data())
        finally:
            manager.Store = previous_store
        self.assertEqual("scheduled", runtime.future_plan["status"])
        asyncio.run(runtime.async_cancel_future_plan())
        self.assertEqual("cancelled", runtime.future_plan["status"])
        self.assertEqual("cancelled", store.value["future_plan"]["status"])
        self.assertEqual("cancelled", runtime.profile_execution[0]["status"])
        self.assertEqual("morning_sale", runtime.profile_execution[0]["profile_id"])

    def test_failed_slot_validation_blocks_only_current_slot_without_writes(self):
        runtime = make_runtime(price=None, default_mode=const.MODE_NORMAL_OPERATION)
        runtime.normal_profile_physical_work_mode = const.MODE_ZERO_EXPORT_CT
        runtime._ai_store = self.MemoryStore()
        runtime.future_plan = {
            "date": "2026-07-19", "status": "scheduled",
            "updates": [{
                "slot_key": "05_06", "enabled": True,
                "mode": const.MODE_SELLING_FIRST,
                "sell_power": 5000, "discharge_current": 120, "min_sell_price": 0.9,
            }],
            "slot_validations": {
                "05_06": {"profile_id": "morning_sale"},
            },
        }
        previous_now = manager.ha_now
        manager.ha_now = lambda: datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual("scheduled", runtime.future_plan["status"])
        self.assertEqual(
            "waiting_data",
            runtime.future_plan["slot_results"]["05_06"]["status"],
        )
        self.assertIn("cenę sprzedaży", runtime.future_plan["slot_results"]["05_06"]["reason"])
        self.assertEqual([], runtime.profile_execution)
        self.assertEqual([], control_number_calls(runtime))

    def test_failed_future_plan_write_records_failed_profile_execution(self):
        runtime = make_runtime(price=1.2)
        runtime._ai_store = self.MemoryStore()
        current = datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        self.mark_soc_reported(runtime, current)

        async def fail_write(_updates, **_kwargs):
            raise RuntimeError("symulowany błąd zapisu")

        runtime.async_apply_schedule_patch = fail_write
        runtime.future_plan = {
            "plan_id": "plan-write-failure",
            "date": "2026-07-19",
            "status": "scheduled",
            "updates": [{
                "slot_key": "05_06",
                "enabled": True,
                "mode": const.MODE_SELLING_FIRST,
                "sell_power": 3000,
            }],
            "slot_validations": {
                "05_06": {
                    "profile_id": "morning_sale",
                    "minimum_price": 0.4,
                    "minimum_soc": 20,
                    "allow_partial": True,
                },
            },
            "slot_results": {},
        }
        previous_now = manager.ha_now
        manager.ha_now = lambda: current
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual("failed", runtime.profile_execution[0]["status"])
        self.assertEqual("morning_sale", runtime.profile_execution[0]["profile_id"])
        self.assertIn("symulowany błąd zapisu", runtime.profile_execution[0]["failure_reason"])

    def test_future_slot_uses_separate_profile_threshold_without_overwriting_schedule_fields(self):
        runtime = make_runtime(price=0.3)
        runtime._ai_store = self.MemoryStore()
        current = datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        self.mark_soc_reported(runtime, current)
        applied = []

        async def apply_patch(updates, **_kwargs):
            applied.append(updates)

        runtime.async_apply_schedule_patch = apply_patch
        runtime.future_plan = {
            "date": "2026-07-19",
            "status": "scheduled",
            "updates": [{
                "slot_key": "05_06",
                "enabled": True,
                "mode": const.MODE_SELLING_FIRST,
                "sell_power": 3000,
            }],
            "slot_validations": {
                "05_06": {
                    "minimum_price": 0.4,
                    "minimum_soc": 20,
                    "allow_partial": True,
                }
            },
            "slot_results": {},
        }
        previous_now = manager.ha_now
        manager.ha_now = lambda: current
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual([], applied)
        self.assertEqual("partial", runtime.future_plan["status"])
        self.assertEqual("blocked", runtime.future_plan["slot_results"]["05_06"]["status"])

    def test_future_charge_slot_revalidates_effective_buy_price(self):
        runtime = make_runtime()
        runtime._ai_store = self.MemoryStore()
        runtime.hass.states.values[const.DEFAULT_BUY_PRICE_TODAY_SENSOR] = FakeState("1.20")
        runtime.data[const.CONF_PRICE_INCLUDES_DISTRIBUTION] = True
        runtime.data[const.CONF_BUY_PRICE_TODAY_SENSOR] = const.DEFAULT_BUY_PRICE_TODAY_SENSOR
        runtime.data[const.CONF_BUY_PRICE_CONTRACT] = {
            "source_adapter": "generic",
            "today_entity": const.DEFAULT_BUY_PRICE_TODAY_SENSOR,
            "economic_role": "retail_buy_all_in",
            "semantic_scope": "all_in_variable",
            "includes_distribution_variable": True,
            "price_basis": "gross",
            "unit": "PLN/kWh",
            "current_price_only": True,
            "allow_state_fallback": True,
        }
        runtime.future_plan = {
            "date": "2026-07-19",
            "status": "scheduled",
            "updates": [{
                "slot_key": "05_06",
                "enabled": True,
                "mode": "Charge",
            }],
            "slot_validations": {
                "05_06": {
                    "maximum_effective_price": 1.0,
                    "allow_partial": True,
                    "planned_energy_kwh": 1.0,
                    "planned_price": 0.8,
                }
            },
            "slot_results": {},
        }
        previous_now = manager.ha_now
        manager.ha_now = lambda: datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual("blocked", runtime.future_plan["slot_results"]["05_06"]["status"])
        self.assertIn("koszt zakupu", runtime.future_plan["slot_results"]["05_06"]["reason"])

    def test_future_sale_slot_caps_power_to_remaining_profile_target(self):
        runtime = make_runtime(price=1.2)
        runtime._ai_store = self.MemoryStore()
        current = datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        self.mark_soc_reported(runtime, current)
        applied = []

        async def apply_patch(updates, **_kwargs):
            applied.append(updates)

        runtime.async_apply_schedule_patch = apply_patch
        runtime.profile_execution = [{
            "profile_id": "morning_sale",
            "date": "2026-07-19",
            "executed_kwh": 0.5,
            "remaining_kwh": 0.5,
        }]
        runtime.future_plan = {
            "date": "2026-07-19",
            "status": "scheduled",
            "updates": [{
                "slot_key": "05_06",
                "enabled": True,
                "mode": const.MODE_SELLING_FIRST,
                "sell_power": 1000,
            }],
            "slot_validations": {
                "05_06": {
                    "profile_id": "morning_sale",
                    "target_energy_kwh": 1.0,
                    "remaining_target_kwh": 1.0,
                    "possible_energy_kwh": 1.5,
                    "planned_energy_kwh": 1.0,
                    "duration_minutes": 60,
                    "planned_price": 1.2,
                    "minimum_price": 0.4,
                    "minimum_soc": 20,
                    "allow_partial": True,
                }
            },
            "slot_results": {},
        }
        previous_now = manager.ha_now
        manager.ha_now = lambda: current
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual(500, applied[0][0]["sell_power"])

    def test_future_plan_revalidates_and_applies_only_current_slot(self):
        runtime = make_runtime(price=1.2)
        runtime._ai_store = self.MemoryStore()
        current = datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        self.mark_soc_reported(runtime, current)
        applied = []

        async def apply_patch(updates, **_kwargs):
            applied.append(updates)

        runtime.async_apply_schedule_patch = apply_patch
        runtime.future_plan = {
            "date": "2026-07-19",
            "status": "scheduled",
            "updates": [
                {"slot_key": "05_06", "enabled": True, "mode": const.MODE_SELLING_FIRST, "sell_power": 3000, "minimum_sell_soc": 20, "min_sell_price": 0.4},
                {"slot_key": "06_07", "enabled": True, "mode": const.MODE_SELLING_FIRST, "sell_power": 2000, "minimum_sell_soc": 20, "min_sell_price": 0.4},
            ],
            "slot_validations": {"05_06": {"allow_partial": True}},
            "slot_results": {},
        }
        previous_now = manager.ha_now
        manager.ha_now = lambda: current
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual([[
            {
                "slot_key": "05_06",
                "enabled": True,
                "mode": const.MODE_SELLING_FIRST,
                "sell_power": 3000,
            }
        ]], applied)
        self.assertEqual("scheduled", runtime.future_plan["status"])
        self.assertEqual("physical_pending", runtime.future_plan["slot_results"]["05_06"]["status"])


class StatisticsTests(unittest.TestCase):
    def test_current_day_reports_progress_not_accuracy(self):
        runtime = make_runtime()
        runtime.solcast_tracking = {"date": "2026-07-18", "forecast": 50.0, "actual": 10.0}
        rows = runtime.history_daily_summary()
        today = next(row for row in rows if row["date"] == "2026-07-18")
        self.assertIsNone(today["accuracy_percent"])
        self.assertEqual(today["forecast_progress_percent"], 20.0)
        self.assertFalse(today["day_complete"])

    def test_historical_accuracy_uses_only_completed_days(self):
        runtime = make_runtime()
        runtime.solcast_history = [
            {"date": "2026-07-17", "forecast_kwh": 50, "actual_kwh": 40, "accuracy_percent": 80, "day_complete": True},
            {"date": "2026-07-16", "forecast_kwh": 20, "actual_kwh": 40, "accuracy_percent": 0, "day_complete": True},
            {"date": "2026-07-18", "forecast_kwh": 60, "actual_kwh": 6, "accuracy_percent": None, "day_complete": False},
        ]
        runtime.solcast_tracking = {"date": "2026-07-18", "forecast": 60, "actual": 6}
        summary = runtime.learning_summary()
        self.assertEqual(summary["solcast_accuracy_days"], 2)
        self.assertEqual(summary["solcast_accuracy_avg"], 40.0)
        self.assertEqual(summary["solcast_correction_factor"], 1.013)
        self.assertEqual(summary["current_forecast_progress"], 10.0)

    def test_g12w_weekend_is_offpeak_all_day(self):
        saturday = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        profile = manager.hourly_tariff_profile(saturday, "g12w", 0.5, 0.2)
        self.assertTrue(all(row["zone"] == "offpeak" for row in profile))
        self.assertTrue(all(row["rate"] == 0.2 for row in profile))

    def test_flow_signs_are_configurable(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_GRID_POWER_SENSOR] = FakeState("500")
        runtime.hass.states.values[const.DEFAULT_BATTERY_POWER_SENSOR] = FakeState("-700")
        runtime.data[const.CONF_GRID_POWER_SENSOR] = const.DEFAULT_GRID_POWER_SENSOR
        runtime.data[const.CONF_BATTERY_POWER_SENSOR] = const.DEFAULT_BATTERY_POWER_SENSOR
        self.assertEqual(runtime.normalized_grid_power(), 500)
        self.assertEqual(runtime.normalized_battery_power(), -700)
        runtime.data[const.CONF_GRID_POSITIVE_IS_IMPORT] = False
        runtime.data[const.CONF_BATTERY_POSITIVE_IS_DISCHARGE] = False
        self.assertEqual(runtime.normalized_grid_power(), -500)
        self.assertEqual(runtime.normalized_battery_power(), 700)


class AiProfileValidationTests(unittest.IsolatedAsyncioTestCase):
    def valid_profiles(self):
        return manager.default_user_profiles()

    def test_safe_migration_profiles_are_disabled_and_versioned(self):
        profiles = self.valid_profiles()
        self.assertEqual(2, profiles["schema_version"])
        self.assertTrue(all(not item["enabled"] for item in profiles["profiles"].values()))

    def test_manager_rejects_cached_plan_from_previous_algorithm(self):
        source = Path(manager.__file__).read_text(encoding="utf-8")
        self.assertIn(
            'self.optimizer_plan.get("algorithm_version") == ALGORITHM_VERSION',
            source,
        )
        self.assertIn(
            'self.optimizer_plan.get("plan_schema_version") == PLAN_SCHEMA_VERSION',
            source,
        )

    def test_learning_profile_stats_read_top_level_counters_and_cell_coverage(self):
        runtime = make_runtime()
        profile = {
            "accepted_samples": 437,
            "rejected_samples": 2287,
            "cells": {
                "07-06": {"samples": 20},
                "07-07": {"samples": 12},
                "empty": {"samples": 0},
            },
        }
        self.assertEqual(
            {
                "accepted_samples": 437,
                "rejected_samples": 2287,
                "covered_cells": 2,
            },
            runtime._learning_profile_stats(profile),
        )

    def test_learning_profile_stats_support_legacy_direct_cell_map(self):
        runtime = make_runtime()
        profile = {
            "0-00": {"samples": 3},
            "0-01": {"samples": 2},
        }
        self.assertEqual(
            {
                "accepted_samples": 5,
                "rejected_samples": 0,
                "covered_cells": 2,
            },
            runtime._learning_profile_stats(profile),
        )

    def test_validation_preserves_independent_sale_profiles_and_midnight_charge(self):
        profiles = self.valid_profiles()
        profiles["profiles"]["morning_sale"].update({"enabled": True, "target_energy_kwh": 3.5, "min_price": 0.7})
        profiles["profiles"]["evening_sale"].update({"enabled": True, "target_energy_kwh": 5.0, "min_price": 1.1})
        profiles["profiles"]["charging"].update({"enabled": True, "start": "22:00", "end": "06:00", "target_value": 85})
        result = manager.DeyeEnergyManagerRuntime.validate_user_profiles(profiles)
        self.assertEqual(3.5, result["profiles"]["morning_sale"]["target_energy_kwh"])
        self.assertEqual(5.0, result["profiles"]["evening_sale"]["target_energy_kwh"])
        self.assertEqual(("22:00", "06:00"), (result["profiles"]["charging"]["start"], result["profiles"]["charging"]["end"]))

    def test_validation_normalizes_legacy_charging_purpose_and_deadline(self):
        profiles = self.valid_profiles()
        profiles["profiles"]["charging"].update({
            "purpose": "home_reserve",
            "deadline": "6:05",
            "preferred_power_w": 4200,
        })
        result = manager.DeyeEnergyManagerRuntime.validate_user_profiles(profiles)
        charging = result["profiles"]["charging"]
        self.assertEqual("reserve", charging["purpose"])
        self.assertEqual("06:05", charging["deadline"])
        self.assertEqual(4200, charging["preferred_power_w"])

    def test_invalid_empty_window_soc_power_and_negative_price_are_rejected(self):
        cases = []
        profile = self.valid_profiles()
        profile["profiles"]["morning_sale"]["end"] = profile["profiles"]["morning_sale"]["start"]
        cases.append(profile)
        profile = self.valid_profiles()
        profile["profiles"]["morning_sale"]["min_soc_after"] = 101
        cases.append(profile)
        profile = self.valid_profiles()
        profile["profiles"]["morning_sale"]["preferred_power_w"] = 14000
        cases.append(profile)
        profile = self.valid_profiles()
        profile["profiles"]["morning_sale"]["min_price"] = -0.1
        cases.append(profile)
        for payload in cases:
            with self.assertRaises(ValueError):
                manager.DeyeEnergyManagerRuntime.validate_user_profiles(payload)

    async def test_saving_profiles_requests_semantic_recalc_without_deye_calls(self):
        runtime = make_runtime()
        saved = []
        async def save():
            saved.append(True)
        runtime.async_save_ai_data = save
        profiles = self.valid_profiles()
        profiles["profiles"]["morning_sale"]["enabled"] = True
        runtime._optimizer_input_snapshot_id = "old"
        await runtime.async_set_user_profiles(profiles)
        self.assertEqual("old", runtime._optimizer_input_snapshot_id)
        self.assertEqual("user_profiles_changed", runtime._optimizer_generation_reason)
        self.assertEqual(1, runtime.runtime_metrics["optimizer_recalc_requested"])
        self.assertEqual(1, runtime.runtime_metrics["optimizer_recalc_reasons"]["profile"])
        self.assertEqual([], runtime.hass.services.calls)
        self.assertEqual([True], saved)

    def test_profile_execution_is_recorded_locally_without_changing_user_parameters(self):
        runtime = make_runtime()
        runtime.user_profiles = self.valid_profiles()
        runtime.user_profiles["profiles"]["morning_sale"].update(
            {
                "enabled": True,
                "start": "06:00",
                "end": "09:00",
                "target_energy_kwh": 6,
                "min_price": 0.7,
            }
        )
        original = repr(runtime.user_profiles)
        runtime.optimizer_plan = {
            "plan_id": "plan-078",
            "rows": [
                {
                    "date": "2026-07-18",
                    "hour": 7,
                    "profile_id": "morning_sale",
                    "action": "sell",
                    "planned_energy_kwh": 2,
                }
            ],
        }
        runtime.profile_execution = []
        runtime._record_profile_execution(
            {
                "hour": "2026-07-18T07:00:00+00:00",
                "grid_export_kwh": 1.4,
                "battery_discharge_kwh": 1.1,
            }
        )
        self.assertEqual(1, len(runtime.profile_execution))
        self.assertEqual("morning_sale", runtime.profile_execution[0]["profile_id"])
        self.assertEqual(1.1, runtime.profile_execution[0]["actual_energy_kwh"])
        self.assertEqual("local_measurement", runtime.profile_execution[0]["source"])
        self.assertEqual("sale", runtime.profile_execution[0]["profile_type"])
        self.assertEqual(6, runtime.profile_execution[0]["target_kwh"])
        self.assertEqual(2, runtime.profile_execution[0]["planned_kwh"])
        self.assertEqual(4.9, runtime.profile_execution[0]["remaining_kwh"])
        self.assertIn(runtime.profile_execution[0]["status"], {"running", "partial", "completed"})
        for field in (
            "window_start", "window_end", "planned_soc_start", "planned_soc_end",
            "actual_soc_start", "actual_soc_end", "planned_price", "actual_average_price",
            "planned_import_kwh", "actual_import_kwh", "planned_export_kwh",
            "actual_export_kwh", "planned_result_pln", "actual_result_pln",
            "failure_reason", "data_quality", "created_at", "updated_at",
        ):
            self.assertIn(field, runtime.profile_execution[0])
        self.assertEqual(original, repr(runtime.user_profiles))
        self.assertEqual([], runtime.hass.services.calls)

    def test_profile_execution_supports_complete_lifecycle_contract(self):
        runtime = make_runtime()
        runtime.user_profiles = self.valid_profiles()
        runtime.user_profiles["profiles"]["morning_sale"].update(
            {
                "enabled": True,
                "start": "06:00",
                "end": "10:00",
                "target_energy_kwh": 6,
            }
        )
        runtime.optimizer_plan = {
            "plan_id": "plan-lifecycle",
            "rows": [
                {
                    "date": "2026-07-31",
                    "hour": 6,
                    "profile_id": "morning_sale",
                    "action": "sell",
                    "planned_energy_kwh": 2,
                    "soc_start_pct": 80,
                    "soc_end_pct": 70,
                    "sell_price": 0.8,
                    "expected_export_kwh": 2,
                    "net_result": 1.6,
                }
            ],
        }
        required_fields = {
            "plan_id", "profile_id", "profile_type", "date", "window_start",
            "window_end", "target_kwh", "planned_kwh", "executed_kwh",
            "remaining_kwh", "planned_soc_start", "planned_soc_end",
            "actual_soc_start", "actual_soc_end", "planned_price",
            "actual_average_price", "planned_import_kwh", "actual_import_kwh",
            "planned_export_kwh", "actual_export_kwh", "planned_result_pln",
            "actual_result_pln", "status", "failure_reason", "data_quality",
            "created_at", "updated_at",
        }
        statuses = {
            "waiting", "running", "completed", "partial", "blocked", "failed",
            "skipped", "cancelled", "manual_override",
        }
        for status in statuses:
            entry = runtime._set_profile_execution_status(
                "morning_sale",
                "2026-07-31",
                status,
                failure_reason=(
                    "test"
                    if status in {"blocked", "failed", "cancelled", "manual_override"}
                    else None
                ),
            )
            self.assertEqual(status, entry["status"])
            self.assertTrue(required_fields.issubset(entry))
        self.assertEqual(1, len(runtime.profile_execution))
        self.assertEqual([], runtime.hass.services.calls)

    def test_new_optimizer_plan_seeds_waiting_blocked_and_skipped_executions(self):
        runtime = make_runtime()
        runtime.user_profiles = self.valid_profiles()
        for profile_id in ("morning_sale", "evening_sale", "charging"):
            runtime.user_profiles["profiles"][profile_id]["enabled"] = True
        plan = {
            "plan_id": "plan-seed",
            "rows": [
                {
                    "date": "2026-07-31",
                    "day": "tomorrow",
                    "hour": 6,
                    "profile_id": "morning_sale",
                    "action": "sell",
                    "planned_energy_kwh": 1,
                }
            ],
            "profile_impacts": [
                {
                    "profile_id": "morning_sale",
                    "profile_type": "sale",
                    "enabled": True,
                    "status": "waiting",
                },
                {
                    "profile_id": "evening_sale",
                    "profile_type": "sale",
                    "enabled": True,
                    "status": "blocked_min_net_result",
                    "block_reason": "min_net_result",
                },
                {
                    "profile_id": "charging",
                    "profile_type": "charging",
                    "enabled": True,
                    "status": "no_qualified_hours",
                    "skip_reason": "no_qualified_hours",
                },
            ],
        }
        runtime._sync_profile_execution_from_plan(
            plan,
            datetime.fromisoformat("2026-07-30T12:00:00+00:00"),
        )
        by_profile = {row["profile_id"]: row for row in runtime.profile_execution}
        self.assertEqual("waiting", by_profile["morning_sale"]["status"])
        self.assertEqual("blocked", by_profile["evening_sale"]["status"])
        self.assertEqual("skipped", by_profile["charging"]["status"])
        self.assertEqual("min_net_result", by_profile["evening_sale"]["failure_reason"])

    def test_manual_control_marks_only_active_profile_as_manual_override(self):
        runtime = make_runtime()
        runtime.control_mode = "Schedule"
        runtime.user_profiles = self.valid_profiles()
        runtime.optimizer_plan = {
            "plan_id": "plan-manual",
            "rows": [
                {
                    "date": manager.ha_now().date().isoformat(),
                    "hour": manager.ha_now().hour,
                    "profile_id": "evening_sale",
                    "action": "sell",
                    "planned_energy_kwh": 1,
                }
            ],
        }
        runtime.set_control_mode("Manual Sell")
        self.assertEqual("manual_override", runtime.profile_execution[0]["status"])
        self.assertEqual("evening_sale", runtime.profile_execution[0]["profile_id"])


class InverterMaxPowerTests(unittest.IsolatedAsyncioTestCase):
    def test_default_configured_limit(self):
        runtime = make_runtime()
        self.assertEqual(runtime.configured_inverter_max_power_w, const.DEFAULT_INVERTER_MAX_POWER_W)

    def test_configured_limit_is_clamped(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 500
        self.assertEqual(runtime.configured_inverter_max_power_w, 1000)
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 50000
        self.assertEqual(runtime.configured_inverter_max_power_w, const.ABSOLUTE_INVERTER_MAX_POWER_W)

    def test_detected_entity_max_from_number_attributes(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"max": 16000, "unit_of_measurement": "W"}
        )
        self.assertEqual(runtime.detected_entity_max_power_w, 16000)

    def test_detect_entity_max_power_w_helper_is_shared(self):
        """The same validation logic is used by runtime and config flow."""
        inverter_provider = sys.modules["custom_components.deye_energy_manager.inverter_provider"]
        detect = inverter_provider.detect_entity_max_power_w
        good = FakeState("0", attributes={"max": 16000, "unit_of_measurement": "W"})
        self.assertEqual(detect(good), 16000)
        self.assertIsNone(detect(FakeState("0", attributes={"max": 500, "unit_of_measurement": "W"})))
        self.assertIsNone(detect(FakeState("unavailable", attributes={"max": 16000, "unit_of_measurement": "W"})))
        self.assertIsNone(detect(None))
        self.assertEqual(detect(FakeState("0", attributes={"max": 16, "unit_of_measurement": "kW"})), 16000)

    def test_detected_entity_max_converts_kw(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"max": 16, "unit_of_measurement": "kW"}
        )
        self.assertEqual(runtime.detected_entity_max_power_w, 16000)

    def test_effective_limit_uses_configured_when_no_detection(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 15000
        self.assertIsNone(runtime.detected_entity_max_power_w)
        self.assertEqual(runtime.effective_inverter_max_power_w, 15000)

    def test_effective_limit_ignores_detected_entity_max(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 15000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"max": 12000, "unit_of_measurement": "W"}
        )
        self.assertEqual(runtime.detected_entity_max_power_w, 12000)
        self.assertEqual(runtime.effective_inverter_max_power_w, 15000)

    async def test_apply_settings_rejects_sell_power_above_effective_limit(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"max": 12000, "unit_of_measurement": "W"}
        )
        with self.assertRaisesRegex(ValueError, "8000"):
            await runtime.async_apply_settings(const.MODE_SELLING_FIRST, 10000, 120, 120, 60)

    async def test_apply_targets_caps_sell_power_to_effective_limit(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"max": 12000, "unit_of_measurement": "W"}
        )
        runtime.scheduler_enabled = True
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_SELLING_FIRST
        active.sell_power = 10000

        await runtime.async_apply_targets()

        written = [
            call for call in runtime.hass.services.calls
            if call[0] == "number" and call[1] == "set_value" and call[2].get("entity_id") == const.DEFAULT_MAX_SELL_POWER
        ]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0][2]["value"], 8000)
        self.assertIn("8000 W", runtime.last_action)

    async def test_apply_safe_defaults_caps_default_sell_power(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.default_sell_power = 10000
        runtime.default_work_mode = const.MODE_NORMAL_OPERATION

        await runtime.async_apply_safe_defaults("Test")

        written = [
            call for call in runtime.hass.services.calls
            if call[0] == "number" and call[1] == "set_value" and call[2].get("entity_id") == const.DEFAULT_MAX_SELL_POWER
        ]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0][2]["value"], 8000)

    def test_validate_user_profiles_uses_max_power_parameter(self):
        profiles = {
            "morning_sale": {
                "enabled": True,
                "start": "06:00",
                "end": "10:00",
                "active_days": ["monday"],
                "priority": "normal",
                "goal_character": "preferred",
                "minimum_confidence": 50,
                "target_energy_kwh": 5,
                "preferred_power_w": 15000,
                "target_basis": "battery_to_grid",
                "distribution_method": "constant_power",
            }
        }
        with self.assertRaisesRegex(ValueError, "10000"):
            manager.DeyeEnergyManagerRuntime.validate_user_profiles(profiles, max_power_w=10000)
        result = manager.DeyeEnergyManagerRuntime.validate_user_profiles(profiles, max_power_w=20000)
        self.assertEqual(result["profiles"]["morning_sale"]["preferred_power_w"], 15000)

    def test_two_entries_have_independent_effective_limits(self):
        first = make_runtime()
        first.data[const.CONF_INVERTER_MAX_POWER_W] = 9000
        second = make_runtime()
        second.data[const.CONF_INVERTER_MAX_POWER_W] = 15000
        self.assertEqual(first.effective_inverter_max_power_w, 9000)
        self.assertEqual(second.effective_inverter_max_power_w, 15000)
        # The applied sell power ceiling must follow the per-entry limit.
        first.default_sell_power = 12000
        second.default_sell_power = 12000
        self.assertEqual(first.applied_sell_power, 9000)
        self.assertEqual(second.applied_sell_power, 12000)

    def test_options_update_changes_runtime_effective_limit(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        self.assertEqual(runtime.effective_inverter_max_power_w, 8000)
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 14000
        self.assertEqual(runtime.effective_inverter_max_power_w, 14000)

    def test_old_slot_value_is_not_rewritten_after_physical_normalization(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        runtime.scheduler_enabled = True
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_SELLING_FIRST
        active.sell_power = 13000
        self.assertEqual(runtime.target_sell_power, 13000)
        self.assertEqual(runtime.applied_sell_power, 8000)
        self.assertEqual(active.sell_power, 13000)

    def test_optimizer_grid_import_limit_is_not_capped_by_inverter_power(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.ai_settings["gridImportLimitW"] = 14000
        inputs = runtime.optimizer_core_inputs()
        self.assertEqual(inputs["grid_import_limit_w"], 14000)

    def test_optimizer_grid_export_limit_remains_independent(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.ai_settings["exportLimitW"] = 6000
        inputs = runtime.optimizer_core_inputs()
        self.assertEqual(inputs["grid_export_limit_w"], 6000)
        self.assertEqual(inputs["inverter_ac_limit_w"], 8000)

    def test_optimizer_final_sell_power_respects_inverter_and_export_limits(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        runtime.ai_settings["exportLimitW"] = 6000
        inputs = runtime.optimizer_core_inputs()
        self.assertEqual(inputs["grid_export_limit_w"], 6000)
        self.assertEqual(inputs["inverter_ac_limit_w"], 8000)
        self.assertLessEqual(inputs["max_sell_power_w"], 8000)

    def test_optimizer_best_hours_product_defaults_have_one_backend_contract(self):
        runtime = make_runtime()
        inputs = runtime.optimizer_core_inputs()
        self.assertEqual(inputs["price_equivalence_band"], 0.05)
        self.assertEqual(inputs["minimum_auto_sell_power_w"], 1000)

    def test_optimizer_best_hours_product_settings_are_forwarded_to_core(self):
        runtime = make_runtime()
        runtime.ai_settings.update({
            "priceEquivalenceBand": 0.10,
            "minimumAutoSellPowerW": 1250,
        })
        inputs = runtime.optimizer_core_inputs()
        self.assertEqual(inputs["price_equivalence_band"], 0.10)
        self.assertEqual(inputs["minimum_auto_sell_power_w"], 1250)

    def test_explicit_battery_discharge_limit_can_only_lower_model_limit(self):
        runtime = make_runtime()
        model = runtime.battery_model_context()
        model_limit = model["power_limit"]["effective_limit_w"]
        runtime.ai_settings["batteryDischargeLimitW"] = model_limit + 2500
        higher = runtime.optimizer_core_inputs(battery_model=model)
        self.assertEqual(higher["battery_discharge_limit_w"], model_limit)
        runtime.ai_settings["batteryDischargeLimitW"] = model_limit / 2
        lower = runtime.optimizer_core_inputs(battery_model=model)
        self.assertEqual(lower["battery_discharge_limit_w"], model_limit / 2)
        self.assertEqual(
            lower["sell_power_limits_w"]["configured_battery_discharge"],
            model_limit / 2,
        )

    def test_physical_sell_power_range_converts_kw_to_w(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12, "step": 0.1, "unit_of_measurement": "kW"}
        )
        physical = runtime.max_sell_power_range
        self.assertEqual(physical.minimum_w, 0)
        self.assertEqual(physical.maximum_w, 12000)
        self.assertEqual(physical.step_w, 100)
        self.assertEqual(physical.native_unit, "kw")

    def test_physical_sell_power_command_converts_w_to_kw(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12, "step": 0.1, "unit_of_measurement": "kW"}
        )
        asyncio.run(runtime.async_set_max_sell_power_number(9955))
        written = [
            call for call in runtime.hass.services.calls
            if call[0] == "number" and call[1] == "set_value" and call[2].get("entity_id") == const.DEFAULT_MAX_SELL_POWER
        ]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0][2]["value"], 9.9)

    def test_physical_sell_power_rejects_kwh_unit(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12, "step": 0.1, "unit_of_measurement": "kWh"}
        )
        physical = runtime.max_sell_power_range
        self.assertIsNone(physical.maximum_w)
        self.assertIsNone(physical.step_w)

    def test_manual_sell_power_rejects_value_above_physical_max(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 15000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        with self.assertRaisesRegex(ValueError, "fizyczny limit"):
            runtime.validate_manual_sell_power_w("Test", 12500)

    def test_manual_sell_power_rejects_value_below_physical_min(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 1000, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        with self.assertRaisesRegex(ValueError, "fizycznego minimum"):
            runtime.validate_manual_sell_power_w("Test", 500)

    def test_manual_sell_power_rejects_value_not_matching_step(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        with self.assertRaisesRegex(ValueError, "fizycznym krokiem"):
            runtime.validate_manual_sell_power_w("Test", 9955)

    def test_automatic_sell_power_rounds_down_to_physical_step(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        self.assertEqual(runtime.normalize_automatic_sell_power_w(9955), 9900)

    def test_automatic_sell_power_never_rounds_up(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        self.assertEqual(runtime.normalize_automatic_sell_power_w(9999), 9900)
        self.assertLessEqual(runtime.normalize_automatic_sell_power_w(9999), 9999)

    def test_matching_zero_sell_power_is_not_rewritten_for_non_selling_slot(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        runtime.scheduler_enabled = True
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_NORMAL_OPERATION
        active.sell_power = 0

        asyncio.run(runtime.async_apply_targets())

        written = [
            call for call in runtime.hass.services.calls
            if call[0] == "number" and call[1] == "set_value" and call[2].get("entity_id") == const.DEFAULT_MAX_SELL_POWER
        ]
        self.assertEqual(written, [])

    def test_zero_sell_power_is_not_raised_to_physical_minimum(self):
        runtime = make_runtime()
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 1000, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        self.assertEqual(runtime.normalize_automatic_sell_power_w(0), 0)

    def test_zero_sell_power_does_not_write_below_physical_entity_min(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 1000, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        runtime.scheduler_enabled = True
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_NORMAL_OPERATION
        active.sell_power = 0

        asyncio.run(runtime.async_apply_targets())

        written = [
            call for call in runtime.hass.services.calls
            if call[0] == "number" and call[1] == "set_value" and call[2].get("entity_id") == const.DEFAULT_MAX_SELL_POWER
        ]
        self.assertEqual(len(written), 0)

    def test_two_entries_build_independent_optimizer_inputs(self):
        first = make_runtime()
        first.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        first.ai_settings["maxSellPower"] = 30000
        second = make_runtime()
        second.data[const.CONF_INVERTER_MAX_POWER_W] = 20000
        second.ai_settings["maxSellPower"] = 30000
        first_inputs = first.optimizer_core_inputs()
        second_inputs = second.optimizer_core_inputs()
        self.assertEqual(first_inputs["inverter_ac_limit_w"], 8000)
        self.assertEqual(second_inputs["inverter_ac_limit_w"], 20000)
        self.assertEqual(first_inputs["max_sell_power_w"], 8000)
        self.assertEqual(second_inputs["max_sell_power_w"], 20000)

    def test_two_entries_build_independent_ai_schemas(self):
        first = make_runtime()
        first.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        second = make_runtime()
        second.data[const.CONF_INVERTER_MAX_POWER_W] = 20000
        from custom_components.deye_energy_manager.ai_assistant import response_schema
        first_schema = response_schema(first.effective_inverter_max_power_w)
        second_schema = response_schema(second.effective_inverter_max_power_w)
        power_key = first_schema["schema"]["properties"]["alternative"]["properties"]["hours"]["items"]["properties"]["power_w"]
        self.assertEqual(power_key["maximum"], 8000)
        power_key = second_schema["schema"]["properties"]["alternative"]["properties"]["hours"]["items"]["properties"]["power_w"]
        self.assertEqual(power_key["maximum"], 20000)


class SellPowerNumberEntityTests(unittest.IsolatedAsyncioTestCase):
    async def test_number_entity_accepts_valid_sell_power(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        entity = number.DeyeManagerNumber(
            runtime, "default_sell_power", "Default sell power", "default_sell_power", 0, const.DEFAULT_INVERTER_MAX_POWER_W, 100, "W"
        )
        await entity.async_set_native_value(9900)
        self.assertEqual(runtime.default_sell_power, 9900)

    async def test_number_entity_rejects_sell_power_above_effective_limit(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        entity = number.DeyeManagerNumber(
            runtime, "default_sell_power", "Default sell power", "default_sell_power", 0, const.DEFAULT_INVERTER_MAX_POWER_W, 100, "W"
        )
        with self.assertRaises(ValueError):
            await entity.async_set_native_value(11000)

    async def test_number_entity_rejects_sell_power_not_matching_step(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = FakeState(
            "0", attributes={"min": 0, "max": 12000, "step": 100, "unit_of_measurement": "W"}
        )
        entity = number.DeyeManagerNumber(
            runtime, "default_sell_power", "Default sell power", "default_sell_power", 0, const.DEFAULT_INVERTER_MAX_POWER_W, 100, "W"
        )
        with self.assertRaises(ValueError):
            await entity.async_set_native_value(9955)

    async def test_number_entity_native_value_caps_to_effective_limit(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_MAX_POWER_W] = 10000
        runtime.default_sell_power = const.DEFAULT_INVERTER_MAX_POWER_W
        entity = number.DeyeManagerNumber(
            runtime, "default_sell_power", "Default sell power", "default_sell_power", 0, const.DEFAULT_INVERTER_MAX_POWER_W, 100, "W"
        )
        self.assertEqual(entity.native_value, 10000)

    def test_two_entries_number_entities_have_independent_maximums(self):
        first = make_runtime()
        first.data[const.CONF_INVERTER_MAX_POWER_W] = 8000
        second = make_runtime()
        second.data[const.CONF_INVERTER_MAX_POWER_W] = 20000
        first_entity = number.DeyeManagerNumber(
            first, "default_sell_power", "Default sell power", "default_sell_power", 0, const.DEFAULT_INVERTER_MAX_POWER_W, 100, "W"
        )
        second_entity = number.DeyeManagerNumber(
            second, "default_sell_power", "Default sell power", "default_sell_power", 0, const.DEFAULT_INVERTER_MAX_POWER_W, 100, "W"
        )
        self.assertEqual(first_entity.native_max_value, 8000)
        self.assertEqual(second_entity.native_max_value, 20000)


class ControlMasterTests(unittest.IsolatedAsyncioTestCase):
    class MemoryStore:
        def __init__(self, value=None):
            self.value = value
            self.save_count = 0

        async def async_save(self, value):
            self.save_count += 1
            self.value = value

        async def async_load(self):
            return self.value

    async def _setup_switch_platform(self, runtime, registry=None, renamed_entity_id=None):
        """Run the actual switch platform setup and emulate HA registry assignment."""
        registry = registry if registry is not None else {}
        runtime.hass.data = {const.DOMAIN: {runtime.entry_id: runtime}}
        entry = types.SimpleNamespace(entry_id=runtime.entry_id)
        added = []
        await switch_module.async_setup_entry(runtime.hass, entry, added.extend)
        for entity in added:
            unique_id = entity._attr_unique_id
            if unique_id not in registry:
                registry[unique_id] = getattr(entity, "entity_id", None) or f"switch.{entity._attr_name.lower().replace(' ', '_')}"
            if unique_id == f"{runtime.entry_id}_control" and renamed_entity_id:
                registry[unique_id] = renamed_entity_id
            entity.entity_id = registry[unique_id]
            entity.hass = runtime.hass
            if hasattr(entity, "async_added_to_hass"):
                await entity.async_added_to_hass()
            entity.async_write_ha_state()
        control = next(item for item in added if isinstance(item, switch_module.DeyeControlSwitch))
        return control, added, registry

    async def test_control_defaults_to_active(self):
        runtime = make_runtime()
        self.assertTrue(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Aktywne")

    async def test_control_switch_has_stable_identity_and_uses_runtime_only(self):
        runtime = make_runtime()
        runtime.async_enable_control = mock.AsyncMock()
        runtime.async_disable_control = mock.AsyncMock()
        entity = switch_module.DeyeControlSwitch(runtime)

        self.assertEqual(entity._attr_unique_id, "test_control")
        self.assertEqual(entity.entity_id, "switch.deye_energy_manager_control")
        self.assertEqual(entity._attr_name, "Sterowanie Deye")
        await entity.async_turn_off()
        await entity.async_turn_on()
        runtime.async_disable_control.assert_awaited_once_with()
        runtime.async_enable_control.assert_awaited_once_with()

    async def test_control_switch_is_created_during_real_setup(self):
        runtime = make_runtime()
        control, added, _registry = await self._setup_switch_platform(runtime)

        self.assertIsInstance(control, switch_module.SwitchEntity)
        self.assertIn(control, added)
        self.assertEqual(control._attr_name, "Sterowanie Deye")
        self.assertEqual(runtime.control_entity_id, "switch.deye_energy_manager_control")
        self.assertIn(runtime.control_entity_id, runtime.hass.states.values)

    async def test_control_switch_has_stable_unique_id(self):
        first = make_runtime()
        control, _added, registry = await self._setup_switch_platform(first)
        first_unique_id = control._attr_unique_id

        second = make_runtime()
        reloaded, _added, _registry = await self._setup_switch_platform(second, registry)

        self.assertEqual(first_unique_id, "test_control")
        self.assertEqual(reloaded._attr_unique_id, first_unique_id)
        self.assertEqual(reloaded.entity_id, control.entity_id)

    async def test_control_switch_turn_off_disables_runtime_control(self):
        runtime = make_runtime()
        runtime._ai_store = self.MemoryStore()
        control, _added, _registry = await self._setup_switch_platform(runtime)

        await control.async_turn_off()

        self.assertFalse(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Wyłączone")
        self.assertEqual(runtime.hass.states.get(control.entity_id).state, "off")

    async def test_control_switch_turn_on_enables_runtime_control(self):
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        runtime._ai_store = self.MemoryStore({"control_enabled": False})
        control, _added, _registry = await self._setup_switch_platform(runtime)

        await control.async_turn_on()

        self.assertTrue(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Aktywne")
        self.assertEqual(runtime.hass.states.get(control.entity_id).state, "on")

    async def test_disable_control_eventually_enters_disabled_state(self):
        runtime = make_runtime()

        await runtime.async_disable_control()

        self.assertFalse(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Wyłączone")

    async def test_disable_control_with_cleanup_finishes_in_disabled_state(self):
        runtime = make_runtime()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def active_operation():
            async with runtime._control_operation("cleanup-test"):
                entered.set()
                await release.wait()

        operation_task = asyncio.create_task(active_operation())
        await entered.wait()
        disable_task = asyncio.create_task(runtime.async_disable_control())
        while runtime.control_status != "Wyłączanie":
            await asyncio.sleep(0)
        self.assertFalse(disable_task.done())

        release.set()
        await operation_task
        await disable_task

        self.assertFalse(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Wyłączone")

    async def test_disable_control_timeout_finishes_in_disabled_state(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0.01
        entered = asyncio.Event()
        release = asyncio.Event()

        async def stuck_operation():
            async with runtime._control_operation("timeout-test"):
                entered.set()
                await release.wait()

        operation_task = asyncio.create_task(stuck_operation())
        await entered.wait()
        await runtime.async_disable_control()

        self.assertFalse(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Wyłączone")
        self.assertIn("Stare operacje zostały unieważnione", runtime.last_error)
        release.set()
        await operation_task

    async def test_control_toggle_can_enable_after_reload_from_disabled_state(self):
        store = self.MemoryStore()
        runtime = make_runtime()
        runtime._ai_store = store
        control, _added, registry = await self._setup_switch_platform(runtime)
        await control.async_turn_off()

        reloaded = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            await reloaded.async_load_ai_data()
        finally:
            manager.Store = previous_store
        restored, _added, _registry = await self._setup_switch_platform(reloaded, registry)
        self.assertFalse(restored.is_on)

        await restored.async_turn_on()

        self.assertTrue(restored.is_on)
        self.assertTrue(reloaded.control_enabled)
        self.assertEqual(reloaded.control_status, "Aktywne")

    async def test_control_switch_state_tracks_runtime_after_reload(self):
        store = self.MemoryStore()
        runtime = make_runtime()
        runtime._ai_store = store
        control, _added, registry = await self._setup_switch_platform(runtime)
        await control.async_turn_off()

        reloaded = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            await reloaded.async_load_ai_data()
        finally:
            manager.Store = previous_store
        restored, _added, _registry = await self._setup_switch_platform(reloaded, registry)

        self.assertFalse(restored.is_on)
        self.assertEqual(restored.entity_id, control.entity_id)
        self.assertEqual(reloaded.control_status, "Wyłączone")

    async def test_control_switch_on_state_tracks_runtime_after_reload(self):
        store = self.MemoryStore({"control_enabled": False})
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        runtime._ai_store = store
        control, _added, registry = await self._setup_switch_platform(runtime)
        await control.async_turn_on()

        reloaded = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            await reloaded.async_load_ai_data()
        finally:
            manager.Store = previous_store
        restored, _added, _registry = await self._setup_switch_platform(reloaded, registry)

        self.assertTrue(restored.is_on)
        self.assertEqual(reloaded.control_status, "Aktywne")

    async def test_control_switch_is_not_duplicated_after_reload(self):
        runtime = make_runtime()
        control, _added, registry = await self._setup_switch_platform(runtime)
        renamed = "switch.recznie_przemianowane_sterowanie_deye"
        registry[control._attr_unique_id] = renamed

        reloaded = make_runtime()
        restored, added, registry = await self._setup_switch_platform(reloaded, registry)
        control_entities = [item for item in added if isinstance(item, switch_module.DeyeControlSwitch)]

        self.assertEqual(len(control_entities), 1)
        self.assertEqual(len([key for key in registry if key == "test_control"]), 1)
        self.assertEqual(restored.entity_id, renamed)
        self.assertEqual(reloaded.control_entity_id, renamed)

    async def test_control_switch_is_available_for_read_only_provider(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        control, _added, _registry = await self._setup_switch_platform(runtime)

        self.assertTrue(control.is_on)
        self.assertEqual(runtime.control_entity_id, control.entity_id)

    async def test_control_switch_old_store_without_control_key_defaults_on(self):
        store = self.MemoryStore({"settings": {}})
        runtime = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            await runtime.async_load_ai_data()
        finally:
            manager.Store = previous_store
        control, _added, _registry = await self._setup_switch_platform(runtime)

        self.assertTrue(control.is_on)
        self.assertEqual(runtime.control_status, "Aktywne")

    async def test_card_switch_runtime_e2e_off_and_on(self):
        output = subprocess.run(
            ["node", str(ROOT / "tests" / "test_control_switch_card.js"), "--emit-payloads"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        off_call, on_call = json.loads(output.stdout)
        runtime = make_runtime()
        runtime._ai_store = self.MemoryStore()
        renamed = "switch.recznie_przemianowane_sterowanie_deye"
        control, _added, _registry = await self._setup_switch_platform(
            runtime, renamed_entity_id=renamed
        )

        self.assertEqual(off_call, {"domain": "switch", "service": "turn_off", "data": {"entity_id": renamed}})
        self.assertEqual(off_call["data"]["entity_id"], control.entity_id)
        await control.async_turn_off()
        self.assertEqual((runtime.control_enabled, runtime.control_status), (False, "Wyłączone"))

        self.assertEqual(on_call["service"], "turn_on")
        self.assertEqual(on_call["data"]["entity_id"], control.entity_id)
        await control.async_turn_on()
        self.assertEqual((runtime.control_enabled, runtime.control_status), (True, "Aktywne"))

    async def test_disable_persists_false_once_and_reload_never_restores_disabling(self):
        store = self.MemoryStore()
        runtime = make_runtime()
        runtime._ai_store = store

        await asyncio.wait_for(runtime.async_disable_control(), timeout=0.5)

        self.assertFalse(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Wyłączone")
        self.assertEqual(store.save_count, 1)
        self.assertFalse(store.value["control_enabled"])

        reloaded = make_runtime()
        previous_store = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            await reloaded.async_load_ai_data()
        finally:
            manager.Store = previous_store
        self.assertFalse(reloaded.control_enabled)
        self.assertEqual(reloaded.control_status, "Wyłączone")

    async def test_low_level_guard_blocks_every_physical_write_family(self):
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        calls = (
            runtime.async_set_work_mode(const.MODE_SELLING_FIRST),
            runtime.async_set_number(runtime.max_sell_power_number, 5000),
            runtime.async_set_number(runtime.charge_current_number, 80),
            runtime.async_set_number(runtime.discharge_current_number, 80),
            runtime.async_set_number(runtime.grid_charge_current_number, 40),
            runtime.async_set_switch("switch.deye_inverter_time_of_use_1_grid_charge", True),
            runtime.async_set_time("time.deye_inverter_time_of_use_1_start", "01:00"),
        )
        for coroutine in calls:
            with self.assertRaises(manager.ControlDisabledError):
                await coroutine
        with self.assertRaises(manager.ControlDisabledError):
            await runtime.async_set_physical_tou_slot(1, "01:00", "02:00", 50, True)
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_rollback_scope_allows_only_exact_original_transaction_snapshot(self):
        runtime = make_runtime()
        entity_id = runtime.charge_current_number
        switch_id = "switch.deye_inverter_time_of_use_1_grid_charge"
        snapshot = {
            entity_id: runtime.hass.states.get(entity_id).state,
            switch_id: runtime.hass.states.get(switch_id).state,
        }
        async with runtime._control_operation("test") as transaction_id:
            runtime._set_control_transaction_snapshot(transaction_id, snapshot)
            runtime.control_enabled = False
            runtime.control_status = "Wyłączanie"
            with runtime._control_rollback_scope(transaction_id, snapshot):
                await runtime.async_set_number(entity_id, 0)
                with self.assertRaises(manager.ControlDisabledError):
                    await runtime.async_set_number(entity_id, 5)
                with self.assertRaises(manager.ControlDisabledError):
                    await runtime.async_set_number("number.unrelated", 0)
                runtime._guard_physical_write(switch_id, "off")
                with self.assertRaises(manager.ControlDisabledError):
                    runtime._guard_physical_write(switch_id, "niepoprawna-wartość")
            with self.assertRaises(manager.ControlDisabledError):
                await runtime.async_set_number(entity_id, 0)
        self.assertEqual(len(runtime.hass.services.calls), 1)

    async def test_disabling_blocks_new_work_rejects_enable_and_waits_for_cleanup(self):
        runtime = make_runtime()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def old_operation():
            async with runtime._control_operation("old"):
                entered.set()
                await release.wait()

        operation_task = asyncio.create_task(old_operation())
        await entered.wait()
        first_cleanup_event = runtime._control_cleanup_event
        disable_task = asyncio.create_task(runtime.async_disable_control())
        while runtime.control_status != "Wyłączanie":
            await asyncio.sleep(0)

        self.assertFalse(runtime.control_enabled)
        self.assertIsNot(first_cleanup_event, runtime._control_cleanup_event)
        with self.assertRaises(manager.ControlDisabledError):
            await runtime.async_set_number(runtime.charge_current_number, 10)
        with self.assertRaisesRegex(manager.ControlDisabledError, "Trwa wyłączanie"):
            await runtime.async_enable_control()
        self.assertFalse(disable_task.done())

        release.set()
        await operation_task
        await disable_task
        self.assertEqual(runtime.control_status, "Wyłączone")

    async def test_each_disable_cycle_uses_its_own_cleanup_event(self):
        runtime = make_runtime()
        await runtime.async_disable_control()
        first_event = runtime._control_cleanup_event
        await runtime.async_enable_control()
        await runtime.async_disable_control()
        self.assertIsNot(first_event, runtime._control_cleanup_event)
        self.assertEqual(runtime.control_status, "Wyłączone")

    async def test_cleanup_timeout_invalidates_late_completion(self):
        runtime = make_runtime()
        runtime.control_confirmation_timeout = 0.01
        entered = asyncio.Event()
        release = asyncio.Event()

        async def late_operation():
            async with runtime._control_operation("late") as transaction_id:
                entered.set()
                await release.wait()
                if runtime._control_result_is_current(transaction_id):
                    runtime.executed_manager_action = "NIEAKTUALNY SUKCES"
                    runtime.last_error = ""

        operation_task = asyncio.create_task(late_operation())
        await entered.wait()
        await runtime.async_disable_control()
        timeout_error = runtime.last_error
        self.assertEqual(runtime.control_status, "Wyłączone")
        self.assertIn("Stare operacje zostały unieważnione", timeout_error)

        release.set()
        await operation_task
        self.assertEqual(runtime.control_status, "Wyłączone")
        self.assertEqual(runtime.last_error, timeout_error)
        self.assertEqual(runtime.executed_manager_action, "Nie wykonano — sterowanie wyłączone")

    async def test_enable_does_not_write_or_clear_emergency_stop(self):
        runtime = make_runtime()
        await runtime.async_disable_control()
        runtime.emergency_stop = True
        runtime.hass.services.calls.clear()

        await runtime.async_enable_control()

        self.assertTrue(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Aktywne")
        self.assertTrue(runtime.emergency_stop)
        self.assertEqual(runtime.executed_manager_action, "Nie wykonano — zatrzymanie awaryjne")
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_emergency_stop_is_logical_only_while_control_is_disabled(self):
        runtime = make_runtime()
        await runtime.async_disable_control()
        runtime.hass.services.calls.clear()

        await runtime.async_emergency_stop()

        self.assertTrue(runtime.emergency_stop)
        self.assertEqual(runtime.control_mode, "Stop Sell")
        self.assertEqual(runtime.executed_manager_action, "Nie wykonano — zatrzymanie awaryjne")
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_schedule_edit_stays_local_and_mapping_still_works_when_disabled(self):
        runtime = make_runtime()
        await runtime.async_disable_control()
        runtime.hass.services.calls.clear()
        runtime._schedule_schedule_reconciliation = mock.Mock()
        slot_key = runtime.active_slot_key()

        await runtime.async_apply_schedule_patch([
            {"slot_key": slot_key, "mode": const.MODE_CHARGE, "tou_soc": 73, "charge_enabled": True}
        ])

        slot = runtime.slots[slot_key]
        self.assertEqual(slot.mode, const.MODE_CHARGE)
        self.assertEqual(slot.tou_soc, 73)
        self.assertTrue(slot.charge_enabled)
        self.assertLessEqual(len(runtime.schedule_to_tou_mapping()), 6)
        runtime._schedule_schedule_reconciliation.assert_not_called()
        self.assertFalse(runtime._schedule_reconcile_requested)
        self.assertIn("nie wysłano ich do falownika", runtime.last_action)
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_disabled_tick_keeps_monitoring_and_updates_planned_not_executed(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        runtime.weather_last_updated = manager.ha_now()
        monitored = (
            "async_update_sold_energy_today",
            "async_update_solcast_history",
            "async_update_learning_history",
            "async_update_energy_sample",
        )
        for name in monitored:
            setattr(runtime, name, mock.AsyncMock())

        self.assertTrue(await runtime._async_tick_impl())

        for name in monitored:
            getattr(runtime, name).assert_awaited_once_with()
        self.assertEqual(runtime.planned_manager_action, "Sprzedaż — 5,0 kW — tylko monitorowanie")
        self.assertEqual(runtime.executed_manager_action, "Nie wykonano — sterowanie wyłączone")
        self.assertEqual(runtime.manager_status, "TYLKO MONITOROWANIE")
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_pending_control_is_cleared_without_safe_defaults(self):
        runtime = make_runtime()
        runtime._pending_control_transaction = {"key": "old"}
        runtime.unsub_confirmation_timer = mock.Mock()
        runtime.unsub_confirmation_listener = mock.Mock()
        runtime.unsub_confirmation_poll = mock.Mock()
        runtime.async_apply_safe_defaults = mock.AsyncMock()

        await runtime.async_disable_control()

        self.assertEqual(runtime._pending_control_transaction, {})
        runtime.async_apply_safe_defaults.assert_not_awaited()
        self.assertIsNone(runtime.unsub_confirmation_timer)
        self.assertIsNone(runtime.unsub_confirmation_listener)
        self.assertIsNone(runtime.unsub_confirmation_poll)

    async def test_disable_during_apply_settings_uses_existing_snapshot_rollback(self):
        runtime = make_runtime()
        original = {
            entity_id: runtime.hass.states.get(entity_id).state
            for entity_id in (
                runtime.work_mode_select,
                runtime.max_sell_power_number,
                runtime.discharge_current_number,
                runtime.charge_current_number,
                runtime.grid_charge_current_number,
            )
        }
        confirming = asyncio.Event()

        async def wait_until_disabled(*_args, **_kwargs):
            confirming.set()
            while runtime._control_is_active():
                await asyncio.sleep(0)
            return False

        runtime._async_wait_for_control_confirmation = wait_until_disabled
        apply_task = asyncio.create_task(runtime.async_apply_settings(
            const.MODE_SELLING_FIRST, 5000, 40, 50, 30
        ))
        await confirming.wait()
        disable_task = asyncio.create_task(runtime.async_disable_control())

        with self.assertRaises(manager.ControlDisabledError):
            await apply_task
        await disable_task
        self.assertEqual(runtime.control_status, "Wyłączone")
        for entity_id, value in original.items():
            restored = runtime.hass.states.get(entity_id).state
            if entity_id.startswith("number."):
                self.assertAlmostEqual(float(restored), float(value))
            else:
                self.assertEqual(restored, value)

    async def test_disable_cancels_tou_without_cancelling_task_and_allows_rollback(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        grid_entity = "switch.deye_inverter_time_of_use_1_grid_charge"
        runtime.hass.states.values[grid_entity] = FakeState("on")
        runtime.hass.services.ignore_once("switch", "turn_off", entity_id=grid_entity)
        runtime.control_confirmation_timeout = 2

        tou_task = asyncio.create_task(runtime.async_apply_time_of_use_map())
        while runtime._active_tou_cancel_event is None and not tou_task.done():
            await asyncio.sleep(0)
        self.assertFalse(tou_task.done())
        disable_task = asyncio.create_task(runtime.async_disable_control())

        self.assertFalse(await tou_task)
        await disable_task
        self.assertEqual(runtime.hass.states.get(grid_entity).state, "on")
        self.assertFalse(runtime.tou_write_pending)
        self.assertIsNone(runtime._tou_confirmation_unsub)
        self.assertEqual(runtime.control_status, "Wyłączone")

    async def test_late_tou_cleanup_cannot_overwrite_disable_timeout(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        grid_entity = "switch.deye_inverter_time_of_use_1_grid_charge"
        runtime.hass.states.values[grid_entity] = FakeState("on")
        runtime.hass.services.ignore_once("switch", "turn_off", entity_id=grid_entity)
        runtime.control_confirmation_timeout = 2
        rollback_started = asyncio.Event()
        release_rollback = asyncio.Event()
        original_rollback = runtime._async_rollback_tou_transaction

        async def delayed_rollback(items, snapshot):
            rollback_started.set()
            await release_rollback.wait()
            return await original_rollback(items, snapshot)

        runtime._async_rollback_tou_transaction = delayed_rollback
        tou_task = asyncio.create_task(runtime.async_apply_time_of_use_map())
        while runtime._active_tou_cancel_event is None and not tou_task.done():
            await asyncio.sleep(0)

        runtime.control_confirmation_timeout = 0.05
        await runtime.async_disable_control()
        timeout_error = runtime.last_error
        self.assertIn("Stare operacje zostały unieważnione", timeout_error)
        await rollback_started.wait()
        release_rollback.set()
        self.assertFalse(await tou_task)

        self.assertEqual(runtime.control_status, "Wyłączone")
        self.assertEqual(runtime.last_error, timeout_error)
        self.assertEqual(runtime.executed_manager_action, "Nie wykonano — sterowanie wyłączone")

    def test_source_audit_leaves_only_guarded_writes_and_weather_read(self):
        source = (PACKAGE / "manager.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("self.hass.services.async_call("), 2)
        self.assertIn("async def _async_physical_service_call", source)
        self.assertIn('"weather",\n                "get_forecasts"', source)
        for helper in (
            "async_set_work_mode",
            "async_set_number",
            "async_set_switch",
            "async_set_time",
            "async_set_boolean_control",
            "_async_restore_raw_entity",
        ):
            body = source.split(f"async def {helper}", 1)[1].split("\n    def ", 1)[0].split("\n    async def ", 1)[0]
            self.assertNotIn("self.hass.services.async_call(", body)


class TouTransactionTests(unittest.IsolatedAsyncioTestCase):
    """Stage 5B: physical Deye TOU write transaction behavior."""

    def _align_physical_tou_starts(self, runtime):
        for idx, segment in enumerate(runtime._tou_mapping.slots, start=1):
            runtime.hass.states.values[f"time.deye_inverter_time_of_use_{idx}_start"] = FakeState(
                f"{int(segment.start):02d}:00:00"
            )

    def test_tou_transaction_writes_only_changed_entities(self):
        runtime = make_runtime()
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_SELLING_FIRST
        active.tou_soc = 20  # matches the physical fixture, so no writes expected
        active.sell_power = 5000
        runtime.scheduler_enabled = True
        self._align_physical_tou_starts(runtime)

        runtime.hass.services.calls.clear()
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertFalse(any(
            domain in ("time", "number", "switch")
            and "time_of_use" in str(data.get("entity_id", ""))
            for domain, _service, data, _blocking in runtime.hass.services.calls
        ))

        # Change the planned SOC; only the affected number entity should be written.
        active.tou_soc = 30
        self._align_physical_tou_starts(runtime)
        runtime.hass.services.calls.clear()
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        written = [data.get("entity_id") for _d, _s, data, _b in runtime.hass.services.calls]
        # The active hour (12:00) falls into physical slot 4 of the default split.
        self.assertIn("number.deye_inverter_time_of_use_4_soc", written)
        self.assertEqual(len([e for e in written if "time_of_use" in e]), 1)

    def test_tou_transaction_write_order_is_start_then_soc_then_grid(self):
        runtime = make_runtime()
        runtime.hass.states.values["time.deye_inverter_time_of_use_1_start"] = FakeState("01:00:00")
        runtime.hass.states.values["number.deye_inverter_time_of_use_1_soc"] = FakeState("50")
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        runtime.hass.services.calls.clear()
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        written = [data.get("entity_id") for _d, _s, data, _b in runtime.hass.services.calls]
        start_idx = written.index("time.deye_inverter_time_of_use_1_start")
        soc_idx = written.index("number.deye_inverter_time_of_use_1_soc")
        grid_idx = written.index("switch.deye_inverter_time_of_use_1_grid_charge")
        self.assertLess(start_idx, soc_idx)
        self.assertLess(soc_idx, grid_idx)

    def test_tou_operation_status_follows_transaction_lifecycle(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        captured: list[str] = []
        original_wait = runtime._async_wait_for_tou_confirmation

        async def _patched_wait(items, operation_name, expected_value_key="expected_logical_value"):
            captured.append(runtime.tou_operation_status)
            return await original_wait(items, operation_name, expected_value_key)

        runtime._async_wait_for_tou_confirmation = _patched_wait
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertEqual(captured, ["confirming"])
        self.assertEqual(runtime.tou_operation_status, "success")
        self.assertFalse(runtime.tou_write_pending)

    def test_tou_transaction_log_contains_every_plan_item(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertTrue(runtime.tou_transaction_log)
        for item in runtime.tou_transaction_log:
            self.assertIn("entity_id", item)
            self.assertIn("field", item)
            self.assertIn("slot_index", item)
            self.assertIn("changed", item)
            self.assertIn("written", item)
            self.assertIn("status", item)

    def test_diagnostics_expose_tou_transaction_state(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.tou_write_pending = True
        runtime.tou_operation_status = "writing"
        runtime.tou_last_error = "test error"
        diag = runtime.diagnostics()
        tx = diag["tou_transaction"]
        self.assertTrue(tx["tou_write_pending"])
        self.assertEqual(tx["tou_operation_status"], "writing")
        self.assertEqual(tx["tou_last_error"], "test error")
        self.assertEqual(tx["tou_operation_started_at"], None)
        self.assertIsInstance(tx["tou_transaction_log"], list)

    def test_second_tou_operation_is_rejected_while_pending(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        started = asyncio.Event()
        proceed = asyncio.Event()

        async def _patched_wait(items, operation_name, expected_value_key="expected_logical_value"):
            started.set()
            await proceed.wait()
            return []

        runtime._async_wait_for_tou_confirmation = _patched_wait

        async def _run() -> None:
            task = asyncio.create_task(runtime.async_apply_time_of_use_map())
            await started.wait()
            self.assertTrue(runtime.tou_write_pending)
            with self.assertRaises(ValueError) as ctx:
                await runtime.async_set_physical_tou_slot(2, "03:00", "04:00", 55, True)
            self.assertIn("Trwa zapis Deye Time Of Use", str(ctx.exception))
            proceed.set()
            self.assertTrue(await task)

        asyncio.run(_run())

    def test_tou_confirmation_listener_is_removed_after_timeout(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        runtime.control_confirmation_timeout = 0.05
        runtime.hass.services.ignore_once(
            "switch", "turn_off", entity_id="switch.deye_inverter_time_of_use_1_grid_charge"
        )
        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))
        self.assertIsNone(runtime._tou_confirmation_unsub)
        self.assertIn("Przywrócono poprzednie ustawienia", runtime.last_error)

    def test_tou_rollback_restores_only_written_entities(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        runtime.hass.states.values["switch.deye_inverter_time_of_use_2_grid_charge"] = FakeState("on")
        runtime.control_confirmation_timeout = 0.05
        runtime.hass.services.ignore_once(
            "switch", "turn_off", entity_id="switch.deye_inverter_time_of_use_2_grid_charge"
        )
        before = {
            entity_id: state.state
            for entity_id, state in runtime.hass.states.values.items()
            if "_grid_charge" in entity_id
        }
        self.assertFalse(asyncio.run(runtime.async_apply_time_of_use_map()))
        after = {
            entity_id: state.state
            for entity_id, state in runtime.hass.states.values.items()
            if "_grid_charge" in entity_id
        }
        # Entity 1 was written and rolled back; entity 2 was never touched.
        self.assertEqual(after["switch.deye_inverter_time_of_use_1_grid_charge"], before["switch.deye_inverter_time_of_use_1_grid_charge"])
        self.assertEqual(after["switch.deye_inverter_time_of_use_2_grid_charge"], before["switch.deye_inverter_time_of_use_2_grid_charge"])

    async def test_tou_confirmation_listener_wakes_wait_loop(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        runtime.control_confirmation_timeout = 30.0
        captured: dict[str, Any] = {}
        original = manager.async_track_state_change_event

        def _fake_track(hass, entity_ids, callback):
            captured["entity_ids"] = list(entity_ids)
            captured["callback"] = callback
            def _unsub():
                captured["unsubbed"] = True
            return _unsub

        manager.async_track_state_change_event = _fake_track
        try:
            loop = asyncio.get_event_loop()
            start = loop.time()
            task = asyncio.create_task(runtime.async_apply_time_of_use_map())
            while "callback" not in captured and not task.done():
                await asyncio.sleep(0)
            captured["callback"](None)
            result = await task
            elapsed = loop.time() - start
            self.assertTrue(result)
            self.assertLess(elapsed, 0.5)
            self.assertIn("switch.deye_inverter_time_of_use_1_grid_charge", captured["entity_ids"])
            self.assertTrue(captured.get("unsubbed"))
            self.assertIsNone(runtime._tou_confirmation_unsub)
        finally:
            manager.async_track_state_change_event = original

    async def test_tou_transaction_cancellation_performs_rollback_and_cleanup(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        before = runtime.hass.states.get("switch.deye_inverter_time_of_use_1_grid_charge").state
        runtime.control_confirmation_timeout = 30.0
        runtime.hass.services.ignore_once(
            "switch", "turn_off", entity_id="switch.deye_inverter_time_of_use_1_grid_charge"
        )
        captured: dict[str, Any] = {}
        event_count = 0
        original_event_factory = runtime._tou_confirmation_event
        wait_event = asyncio.Event()
        rollback_event = asyncio.Event()

        def _patched_event_factory():
            nonlocal event_count
            event_count += 1
            return wait_event if event_count == 1 else rollback_event

        runtime._tou_confirmation_event = _patched_event_factory
        original_track = manager.async_track_state_change_event

        def _fake_track(hass, entity_ids, callback):
            def _unsub():
                captured["unsubbed"] = True
            return _unsub

        manager.async_track_state_change_event = _fake_track
        try:
            task = asyncio.create_task(runtime.async_apply_time_of_use_map())
            while runtime._tou_confirmation_unsub is None and not task.done():
                await asyncio.sleep(0)
            self.assertTrue(runtime.tou_write_pending)
            task.cancel()
            rollback_event.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(runtime.tou_write_pending)
            self.assertTrue(captured.get("unsubbed"))
            self.assertIsNone(runtime._tou_confirmation_unsub)
            self.assertEqual(
                runtime.hass.states.get("switch.deye_inverter_time_of_use_1_grid_charge").state,
                before,
            )
        finally:
            runtime._tou_confirmation_event = original_event_factory
            manager.async_track_state_change_event = original_track

    async def test_unload_clears_tou_listener_and_pending_flag(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.states.values["switch.deye_inverter_time_of_use_1_grid_charge"] = FakeState("on")
        runtime.control_confirmation_timeout = 30.0
        runtime.hass.services.ignore_once(
            "switch", "turn_off", entity_id="switch.deye_inverter_time_of_use_1_grid_charge"
        )
        proceed = asyncio.Event()
        original_event_factory = runtime._tou_confirmation_event
        unsubbed = False

        def _patched_event_factory():
            return proceed

        runtime._tou_confirmation_event = _patched_event_factory
        original_track = manager.async_track_state_change_event

        def _fake_track(hass, entity_ids, callback):
            def _unsub():
                nonlocal unsubbed
                unsubbed = True
            return _unsub

        manager.async_track_state_change_event = _fake_track
        try:
            task = asyncio.create_task(runtime.async_apply_time_of_use_map())
            while runtime._tou_confirmation_unsub is None and not task.done():
                await asyncio.sleep(0)
            self.assertTrue(runtime.tou_write_pending)
            await runtime.async_unload()
            self.assertTrue(unsubbed)
            self.assertFalse(runtime.tou_write_pending)
            task.cancel()
            proceed.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            runtime._tou_confirmation_event = original_event_factory
            manager.async_track_state_change_event = original_track


class TouBackendContract5C1Tests(unittest.IsolatedAsyncioTestCase):
    """Stage 5C.1: authoritative backend contract for manual physical TOU."""

    @staticmethod
    def _set_starts(runtime, hours=(0, 4, 8, 12, 16, 20)):
        ProviderMappingTests._set_valid_tou_starts(runtime, hours)

    @staticmethod
    def _tou_calls(runtime):
        return [
            call
            for call in runtime.hass.services.calls
            if "time_of_use" in str(call[2].get("entity_id", ""))
            or "program_" in str(call[2].get("entity_id", ""))
            or "prog_" in str(call[2].get("entity_id", ""))
            or "custom_tou" in str(call[2].get("entity_id", ""))
        ]

    def test_tou_capabilities_are_exposed_per_slot(self):
        runtime = make_runtime()
        rows = runtime.diagnostics()["tou_capabilities"]
        self.assertEqual(len(rows), 6)
        self.assertEqual([row["slot_index"] for row in rows], list(range(1, 7)))
        self.assertIn("fields", rows[0])

    def test_tou_capabilities_lewa_reka(self):
        row = make_runtime().tou_slot_capabilities()[0]
        self.assertTrue(row["supports_start"])
        self.assertTrue(row["supports_end_as_next_start"])
        self.assertEqual(row["fields"]["start"]["domain"], "time")
        self.assertEqual(row["fields"]["soc"]["domain"], "number")
        self.assertEqual(row["fields"]["grid_charge"]["domain"], "switch")
        self.assertFalse(row["read_only"])

    def test_tou_capabilities_solarman(self):
        runtime = make_runtime()
        ProviderMappingTests._add_solarman_entities(runtime)
        self._set_starts(runtime)
        row = runtime.tou_slot_capabilities()[0]
        self.assertEqual(row["fields"]["start"]["domain"], "time")
        self.assertEqual(row["fields"]["grid_charge"]["domain"], "select")
        self.assertTrue(row["supports_soc"])

    def test_tou_capabilities_sunsynk(self):
        runtime = make_runtime()
        ProviderMappingTests._add_sunsynk_entities(runtime)
        self._set_starts(runtime)
        row = runtime.tou_slot_capabilities()[0]
        self.assertEqual(row["fields"]["start"]["domain"], "select")
        self.assertEqual(row["fields"]["grid_charge"]["domain"], "select")
        self.assertFalse(row["read_only"])

    def test_tou_capabilities_custom_partial_mapping(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        for idx in range(1, 7):
            for kind in ("start", "soc", "grid"):
                runtime.data.pop(const.conf_tou_entity(idx, kind), None)
        entity_id = "number.custom_tou_1_soc"
        runtime.data[const.conf_tou_entity(1, "soc")] = entity_id
        runtime.hass.states.values[entity_id] = FakeState("20", {"min": 0, "max": 100, "step": 1})
        row = runtime.tou_slot_capabilities()[0]
        self.assertTrue(row["supports_soc"])
        self.assertFalse(row["supports_start"])
        self.assertFalse(row["supports_grid_charge"])

    def test_tou_capabilities_read_only_provider(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        row = runtime.tou_slot_capabilities()[0]
        self.assertTrue(row["read_only"])
        self.assertFalse(row["control_writable"])
        self.assertFalse(any(field["writable"] for field in row["fields"].values()))

    def test_tou_capabilities_do_not_depend_on_card_provider_name_guessing(self):
        runtime = make_runtime()
        capabilities = runtime.provider_capabilities()["physical_tou_slots"]
        self.assertEqual(capabilities[0]["provider"], const.PROVIDER_LEWA_REKA)
        self.assertIn("read_only", capabilities[0])
        self.assertIn("control_writable", capabilities[0])

    async def test_set_tou_slot_accepts_start_only(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, start="05:00")
        calls = self._tou_calls(runtime)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2]["entity_id"], "time.deye_inverter_time_of_use_2_start")

    async def test_set_tou_slot_accepts_end_only(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, end="09:00")
        self.assertEqual(
            self._tou_calls(runtime)[0][2]["entity_id"],
            "time.deye_inverter_time_of_use_3_start",
        )

    async def test_set_tou_slot_accepts_soc_only(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, soc=55)
        self.assertEqual(len(self._tou_calls(runtime)), 1)
        self.assertEqual(float(runtime.hass.states.get("number.deye_inverter_time_of_use_2_soc").state), 55)

    async def test_set_tou_slot_accepts_grid_charge_only(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, grid_charge=True)
        self.assertEqual(len(self._tou_calls(runtime)), 1)
        self.assertEqual(runtime.hass.states.get("switch.deye_inverter_time_of_use_2_grid_charge").state, "on")

    async def test_set_tou_slot_does_not_write_omitted_fields(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, soc=55)
        written = [call[2]["entity_id"] for call in self._tou_calls(runtime)]
        self.assertEqual(written, ["number.deye_inverter_time_of_use_2_soc"])

    async def test_custom_partial_tou_payload_does_not_require_missing_fields(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        starts = (0, 4, 8, 12, 16, 20)
        for idx, hour in enumerate(starts, start=1):
            start_entity = f"time.custom_tou_{idx}_start"
            soc_entity = f"number.custom_tou_{idx}_soc"
            grid_entity = f"switch.custom_tou_{idx}_grid"
            runtime.data[const.conf_tou_entity(idx, "start")] = start_entity
            runtime.data[const.conf_tou_entity(idx, "soc")] = soc_entity
            runtime.data[const.conf_tou_entity(idx, "grid")] = grid_entity
            runtime.hass.states.values[start_entity] = FakeState(f"{hour:02d}:00:00")
            runtime.hass.states.values[soc_entity] = FakeState(
                str(idx * 10), {"min": 0, "max": 100, "step": 1}
            )
            runtime.hass.states.values[grid_entity] = FakeState("on" if idx % 2 else "off")
        entity_id = "number.custom_tou_1_soc"
        await runtime.async_set_physical_tou_slot(1, soc=60)
        self.assertEqual(float(runtime.hass.states.get(entity_id).state), 60)
        written = [call[2]["entity_id"] for call in self._tou_calls(runtime)]
        self.assertEqual(written, [entity_id])

    async def test_manual_tou_end_writes_next_slot_start(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, end="09:00")
        self.assertEqual(runtime.hass.states.get("time.deye_inverter_time_of_use_3_start").state, "09:00:00")

    async def test_manual_tou_last_end_writes_first_slot_start(self):
        runtime = make_runtime()
        self._set_starts(runtime, (1, 4, 8, 12, 16, 20))
        await runtime.async_set_physical_tou_slot(6, end="00:00")
        self.assertEqual(runtime.hass.states.get("time.deye_inverter_time_of_use_1_start").state, "00:00:00")

    async def test_tou_transaction_log_marks_end_as_end(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(2, end="09:00")
        self.assertEqual(runtime.tou_transaction_log[0]["field"], "end")
        self.assertEqual(runtime.tou_transaction_log[0]["slot_index"], 2)

    async def test_manual_tou_start_and_end_are_confirmed_atomically(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        captured = []
        original = runtime._async_wait_for_tou_confirmation

        async def inspect(items, operation_name, expected_value_key="expected_logical_value", **kwargs):
            captured.append([(item["field"], item["status"]) for item in items])
            return await original(items, operation_name, expected_value_key, **kwargs)

        runtime._async_wait_for_tou_confirmation = inspect
        await runtime.async_set_physical_tou_slot(2, start="05:00", end="09:00")
        self.assertEqual({field for field, _status in captured[0]}, {"start", "end"})
        self.assertTrue(all(item["confirmed"] for item in runtime.tou_transaction_log))

    async def test_manual_tou_end_failure_rolls_back_both_boundaries(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        first = "time.deye_inverter_time_of_use_2_start"
        second = "time.deye_inverter_time_of_use_3_start"
        before = (runtime.hass.states.get(first).state, runtime.hass.states.get(second).state)
        runtime.control_confirmation_timeout = 0.01
        runtime.hass.services.ignore_once("time", "set_value", entity_id=second)
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, start="05:00", end="09:00")
        self.assertEqual((runtime.hass.states.get(first).state, runtime.hass.states.get(second).state), before)

    async def test_tou_rejects_non_hour_boundary(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        with self.assertRaisesRegex(ValueError, "pełną godzinę"):
            await runtime.async_set_physical_tou_slot(2, start="06:30")

    async def test_tou_rejects_identical_start_and_end(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        with self.assertRaisesRegex(ValueError, "tej samej godziny"):
            await runtime.async_set_physical_tou_slot(2, start="06:00", end="06:00")

    async def test_tou_rejects_duplicate_starts(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        with self.assertRaisesRegex(ValueError, "unikalny"):
            await runtime.async_set_physical_tou_slot(2, start="08:00")

    async def test_tou_rejects_invalid_slot_order(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        with self.assertRaisesRegex(ValueError, "ścisłą kolejność"):
            await runtime.async_set_physical_tou_slot(2, start="10:00")

    def test_tou_accepts_single_midnight_wrap(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        self.assertEqual(runtime._validated_tou_start_vector(2), ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"])

    async def test_tou_rejects_overlapping_ranges(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        with self.assertRaisesRegex(ValueError, "ścisłą kolejność"):
            await runtime.async_set_physical_tou_slot(4, end="11:00")

    def test_tou_validates_full_24h_coverage(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        starts = runtime._validated_tou_start_vector(1)
        lengths = [
            ((int(starts[(idx + 1) % 6][:2]) - int(starts[idx][:2])) % 24)
            for idx in range(6)
        ]
        self.assertEqual(sum(lengths), 24)

    async def test_sunsynk_soc_only_write_preserves_allow_gen(self):
        runtime = make_runtime()
        ProviderMappingTests._add_sunsynk_entities(runtime)
        self._set_starts(runtime)
        entity = "select.sunsynk_prog_2_charge"
        runtime.hass.states.values[entity] = FakeState("Allow Gen", {"options": ["No Grid or Gen", "Allow Grid", "Allow Gen", "Allow Grid & Gen"]})
        await runtime.async_set_physical_tou_slot(2, soc=55)
        self.assertEqual(runtime.hass.states.get(entity).state, "Allow Gen")

    async def test_sunsynk_soc_only_write_preserves_allow_grid_and_gen(self):
        runtime = make_runtime()
        ProviderMappingTests._add_sunsynk_entities(runtime)
        self._set_starts(runtime)
        entity = "select.sunsynk_prog_2_charge"
        runtime.hass.states.values[entity] = FakeState("Allow Grid & Gen", {"options": ["No Grid or Gen", "Allow Grid", "Allow Gen", "Allow Grid & Gen"]})
        await runtime.async_set_physical_tou_slot(2, soc=55)
        self.assertEqual(runtime.hass.states.get(entity).state, "Allow Grid & Gen")

    async def test_solarman_soc_only_write_preserves_disabled_alias(self):
        runtime = make_runtime()
        ProviderMappingTests._add_solarman_entities(runtime)
        self._set_starts(runtime)
        entity = "select.solarman_program_2_charging"
        runtime.hass.states.values[entity] = FakeState("Disable", {"options": ["Disable", "Grid", "Generator", "Both"]})
        await runtime.async_set_physical_tou_slot(2, soc=55)
        self.assertEqual(runtime.hass.states.get(entity).state, "Disable")

    async def test_tou_rollback_restores_exact_provider_grid_option(self):
        runtime = make_runtime()
        ProviderMappingTests._add_sunsynk_entities(runtime)
        entity = "select.sunsynk_prog_2_charge"
        runtime.hass.states.values[entity] = FakeState("Allow Gen", {"options": ["No Grid or Gen", "Allow Grid", "Allow Gen", "Allow Grid & Gen"]})
        original = runtime._async_wait_for_tou_confirmation
        calls = 0

        async def fail_first(items, operation_name, expected_value_key="expected_logical_value", **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return [item for item in items if item.get("written")]
            return await original(items, operation_name, expected_value_key, **kwargs)

        runtime._async_wait_for_tou_confirmation = fail_first
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, grid_charge=True)
        self.assertEqual(runtime.hass.states.get(entity).state, "Allow Gen")

    async def test_second_tou_write_is_rejected_before_operation_lock_wait(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime._operation_lock.acquire()
        first = asyncio.create_task(runtime.async_set_physical_tou_slot(1, soc=55))
        while not runtime.tou_write_pending:
            await asyncio.sleep(0)
        with self.assertRaisesRegex(ValueError, "Trwa zapis"):
            await runtime.async_set_physical_tou_slot(2, soc=60)
        runtime._operation_lock.release()
        await first

    async def test_tou_pending_reservation_is_race_safe(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime._operation_lock.acquire()
        first = asyncio.create_task(runtime.async_set_physical_tou_slot(1, soc=55))
        while not runtime.tou_write_pending:
            await asyncio.sleep(0)
        second = asyncio.create_task(runtime.async_set_physical_tou_slot(2, soc=60))
        await asyncio.sleep(0)
        runtime._operation_lock.release()
        results = await asyncio.gather(first, second, return_exceptions=True)
        self.assertEqual(sum(isinstance(result, ValueError) for result in results), 1)

    async def test_tou_pending_is_cleared_after_validation_error(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(1, start="01:30")
        self.assertFalse(runtime.tou_write_pending)

    async def test_tou_pending_is_cleared_after_success(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertFalse(runtime.tou_write_pending)

    async def test_tou_pending_is_cleared_after_timeout(self):
        runtime = make_runtime()
        entity = "number.deye_inverter_time_of_use_1_soc"
        runtime.control_confirmation_timeout = 0.01
        runtime.hass.services.ignore_once("number", "set_value", entity_id=entity)
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertFalse(runtime.tou_write_pending)

    async def test_tou_pending_is_cleared_after_cancellation(self):
        runtime = make_runtime()
        waiting = asyncio.Event()
        release = asyncio.Event()
        original = runtime._async_wait_for_tou_confirmation

        async def wait(items, operation_name, expected_value_key="expected_logical_value", **kwargs):
            if expected_value_key == "previous_logical_value":
                return await original(items, operation_name, expected_value_key, **kwargs)
            waiting.set()
            await release.wait()
            return []

        runtime._async_wait_for_tou_confirmation = wait
        task = asyncio.create_task(runtime.async_set_physical_tou_slot(1, soc=55))
        await waiting.wait()
        task.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(runtime.tou_write_pending)

    async def test_tou_transaction_field_status_waiting(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        captured = []
        original = runtime._async_wait_for_tou_confirmation

        async def inspect(items, operation_name, expected_value_key="expected_logical_value", **kwargs):
            captured.extend(item["status"] for item in items if item["changed"])
            self.assertEqual(runtime.tou_contract_status, "waiting")
            return await original(items, operation_name, expected_value_key, **kwargs)

        runtime._async_wait_for_tou_confirmation = inspect
        await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(captured, ["waiting"])

    async def test_tou_transaction_field_status_confirmed(self):
        runtime = make_runtime()
        self._set_starts(runtime)
        await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(runtime.tou_transaction_log[0]["status"], "confirmed")
        self.assertEqual(runtime.tou_contract_status, "confirmed")

    async def test_tou_transaction_field_status_rolled_back_after_confirmed_restore(self):
        runtime = make_runtime()
        entity = "number.deye_inverter_time_of_use_1_soc"
        runtime.control_confirmation_timeout = 0.01
        runtime.hass.services.ignore_once("number", "set_value", entity_id=entity)
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(runtime.tou_transaction_log[0]["status"], "rolled_back")
        self.assertTrue(runtime.tou_transaction_log[0]["confirmed"])

    async def test_tou_transaction_field_status_unavailable(self):
        runtime = make_runtime()
        entity = "number.deye_inverter_time_of_use_1_soc"
        runtime.hass.states.values[entity] = FakeState("unavailable")
        snapshot = {}
        item = runtime._make_tou_transaction_item(entity, "soc", 1, 55, snapshot)
        item["written"] = True
        runtime.control_confirmation_timeout = 0
        await runtime._async_wait_for_tou_confirmation([item], "test")
        self.assertEqual(item["status"], "unavailable")

    def test_tou_diagnostics_expose_actual_expected_and_capability(self):
        runtime = make_runtime()
        row = runtime.physical_tou_snapshot()[0]
        for field in ("start", "end", "soc", "grid_charge"):
            self.assertIn("actual", row["fields"][field])
            self.assertIn("expected", row["fields"][field])
            self.assertIn("capability", row["fields"][field])

    async def test_tou_operation_status_reports_rollback(self):
        runtime = make_runtime()
        entity = "number.deye_inverter_time_of_use_1_soc"
        runtime.control_confirmation_timeout = 0.01
        runtime.hass.services.ignore_once("number", "set_value", entity_id=entity)
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(runtime.tou_contract_status, "rollback")

    async def test_tou_operation_status_reports_rollback_failed(self):
        runtime = make_runtime()
        entity = "number.deye_inverter_time_of_use_1_soc"
        runtime.control_confirmation_timeout = 0.01
        runtime.hass.services.ignore_once("number", "set_value", entity_id=entity)

        async def fail_rollback(_items, _snapshot):
            return False, ["test"]

        runtime._async_rollback_tou_transaction = fail_rollback
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(runtime.tou_contract_status, "rollback_failed")

    async def test_tou_write_is_blocked_by_master_control(self):
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        with self.assertRaisesRegex(manager.ControlDisabledError, "Sterowanie Deye jest wyłączone"):
            await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(self._tou_calls(runtime), [])

    def test_tou_diagnostics_remain_available_when_master_control_disabled(self):
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        row = runtime.physical_tou_snapshot()[0]
        self.assertEqual(row["actual_soc"], "20")
        self.assertTrue(row["blocked_by_master_control"])
        self.assertFalse(row["control_writable"])

    async def test_read_only_provider_rejects_tou_write_without_service_call(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        before = list(runtime.hass.services.calls)
        with self.assertRaisesRegex(ValueError, "nie udostępnia bezpiecznej edycji"):
            await runtime.async_set_physical_tou_slot(1, soc=55)
        self.assertEqual(runtime.hass.services.calls, before)


class TouReverseSync5C2Tests(unittest.IsolatedAsyncioTestCase):
    """Stage 5C.2: confirmed physical TOU readback updates only physical schedule fields."""

    STARTS = (0, 4, 8, 12, 16, 20)
    SOCS = (10, 20, 30, 40, 50, 60)
    GRIDS = (False, True, False, True, False, True)
    PRESERVED_FIELDS = (
        "mode",
        "enabled",
        "minimum_sell_soc",
        "sell_power",
        "charge_current",
        "grid_charge_current",
        "discharge_current",
        "min_sell_price",
        "physical_work_mode",
    )

    @classmethod
    def _runtime(cls, provider=const.PROVIDER_LEWA_REKA):
        runtime = make_runtime()
        if provider == const.PROVIDER_SOLARMAN:
            ProviderMappingTests._add_solarman_entities(runtime)
        elif provider == const.PROVIDER_SUNSYNK:
            ProviderMappingTests._add_sunsynk_entities(runtime)
        elif provider == const.PROVIDER_CUSTOM:
            runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
            for idx in range(1, 7):
                runtime.data[const.conf_tou_entity(idx, "start")] = f"time.custom_tou_{idx}_start"
                runtime.data[const.conf_tou_entity(idx, "soc")] = f"number.custom_tou_{idx}_soc"
                runtime.data[const.conf_tou_entity(idx, "grid")] = f"switch.custom_tou_{idx}_grid"
                runtime.hass.states.values[f"time.custom_tou_{idx}_start"] = FakeState("00:00:00")
                runtime.hass.states.values[f"number.custom_tou_{idx}_soc"] = FakeState(
                    "20", {"min": 0, "max": 100, "step": 1}
                )
                runtime.hass.states.values[f"switch.custom_tou_{idx}_grid"] = FakeState("off")
        cls._set_physical(runtime)
        for hour, (key, _label, _start, _end) in enumerate(const.SLOTS):
            slot = runtime.slots[key]
            slot.mode = (
                const.MODE_SELLING_FIRST
                if hour % 3 == 0
                else const.MODE_CHARGE
                if hour % 3 == 1
                else const.MODE_NORMAL_OPERATION
            )
            slot.enabled = hour % 2 == 0
            slot.minimum_sell_soc = 35 + (hour % 5)
            slot.sell_power = 1000 + hour
            slot.charge_current = 40 + hour
            slot.grid_charge_current = 20 + hour
            slot.discharge_current = 60 + hour
            slot.min_sell_price = round(0.2 + hour / 100, 2)
            slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT
            slot.tou_soc = 99
            slot.charge_enabled = False
        return runtime

    @classmethod
    def _set_physical(cls, runtime, *, starts=None, socs=None, grids=None):
        starts = tuple(starts or cls.STARTS)
        socs = tuple(socs or cls.SOCS)
        grids = tuple(grids or cls.GRIDS)
        for idx, (hour, soc, grid) in enumerate(zip(starts, socs, grids), start=1):
            start_entity = runtime._tou_entity(idx, "start")
            start_state = runtime.hass.states.get(start_entity)
            start_attrs = {} if start_state is None else dict(start_state.attributes)
            start_value = f"{hour:02d}:00" if start_entity.startswith("select.") else f"{hour:02d}:00:00"
            runtime.hass.states.values[start_entity] = FakeState(start_value, start_attrs)
            soc_entity = runtime._tou_entity(idx, "soc")
            soc_state = runtime.hass.states.get(soc_entity)
            soc_attrs = {"min": 0, "max": 100, "step": 1} if soc_state is None else dict(soc_state.attributes)
            runtime.hass.states.values[soc_entity] = FakeState(str(soc), soc_attrs)
            grid_entity = runtime._tou_entity(idx, "grid")
            grid_state = runtime.hass.states.get(grid_entity)
            grid_attrs = {} if grid_state is None else dict(grid_state.attributes)
            if grid_entity.startswith("switch."):
                grid_value = "on" if grid else "off"
            elif runtime.inverter_provider == const.PROVIDER_SUNSYNK:
                grid_value = "Allow Grid" if grid else "No Grid or Gen"
            else:
                grid_value = "Grid" if grid else "Disabled"
            runtime.hass.states.values[grid_entity] = FakeState(grid_value, grid_attrs)

    @staticmethod
    def _slot(runtime, hour):
        key = next(key for key, _label, start, _end in const.SLOTS if int(start) == hour)
        return runtime.slots[key]

    @classmethod
    def _preserved_snapshot(cls, runtime):
        return {
            key: {field: getattr(slot, field) for field in cls.PRESERVED_FIELDS}
            for key, slot in runtime.slots.items()
        }

    async def test_manual_tou_soc_updates_tou_soc_only(self):
        runtime = self._runtime()
        preserved = self._preserved_snapshot(runtime)
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertTrue(all(self._slot(runtime, hour).tou_soc == 25 for hour in range(4, 8)))
        self.assertEqual(self._preserved_snapshot(runtime), preserved)

    async def test_manual_tou_soc_does_not_change_minimum_sell_soc(self):
        runtime = self._runtime()
        before = [slot.minimum_sell_soc for slot in runtime.slots.values()]
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual([slot.minimum_sell_soc for slot in runtime.slots.values()], before)

    async def test_manual_tou_soc_in_selling_range_preserves_sell_guard(self):
        runtime = self._runtime()
        target = self._slot(runtime, 4)
        target.mode = const.MODE_SELLING_FIRST
        target.minimum_sell_soc = 35
        target.tou_soc = 15
        await runtime.async_set_physical_tou_slot(2, soc=20)
        self.assertEqual(target.tou_soc, 20)
        self.assertEqual(target.minimum_sell_soc, 35)

    async def test_reverse_sync_updates_all_hours_in_soc_range(self):
        runtime = self._runtime()
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual([self._slot(runtime, hour).tou_soc for hour in range(4, 8)], [25] * 4)

    async def test_manual_grid_charge_updates_charge_enabled_only(self):
        runtime = self._runtime()
        preserved = self._preserved_snapshot(runtime)
        await runtime.async_set_physical_tou_slot(2, grid_charge=False)
        self.assertTrue(all(not self._slot(runtime, hour).charge_enabled for hour in range(4, 8)))
        self.assertEqual(self._preserved_snapshot(runtime), preserved)

    async def test_manual_grid_charge_does_not_change_manager_mode(self):
        runtime = self._runtime()
        before = [slot.mode for slot in runtime.slots.values()]
        await runtime.async_set_physical_tou_slot(2, grid_charge=False)
        self.assertEqual([slot.mode for slot in runtime.slots.values()], before)

    async def test_manual_grid_charge_does_not_change_currents(self):
        runtime = self._runtime()
        before = [(slot.charge_current, slot.grid_charge_current, slot.discharge_current) for slot in runtime.slots.values()]
        await runtime.async_set_physical_tou_slot(2, grid_charge=False)
        self.assertEqual(
            [(slot.charge_current, slot.grid_charge_current, slot.discharge_current) for slot in runtime.slots.values()],
            before,
        )

    async def test_reverse_sync_updates_all_hours_in_grid_range(self):
        runtime = self._runtime()
        await runtime.async_set_physical_tou_slot(2, grid_charge=False)
        self.assertEqual([self._slot(runtime, hour).charge_enabled for hour in range(4, 8)], [False] * 4)

    def test_reverse_sync_assigns_hours_using_half_open_ranges(self):
        runtime = self._runtime()
        patch = runtime.tou_mapping_to_schedule_patch(runtime.read_physical_tou_mapping())
        values = {int(next(start for key, _l, start, _e in const.SLOTS if key == row["slot_key"])): row["tou_soc"] for row in patch}
        self.assertEqual([values[hour] for hour in range(4, 8)], [20] * 4)
        self.assertEqual(values[8], 30)

    def test_reverse_sync_handles_midnight_range(self):
        runtime = self._runtime()
        self._set_physical(runtime, starts=(2, 6, 10, 14, 18, 22))
        patch = runtime.tou_mapping_to_schedule_patch(runtime.read_physical_tou_mapping())
        values = {int(next(start for key, _l, start, _e in const.SLOTS if key == row["slot_key"])): row["tou_soc"] for row in patch}
        self.assertEqual([values[hour] for hour in (22, 23, 0, 1)], [60] * 4)

    def test_reverse_sync_start_boundary_belongs_to_new_range(self):
        runtime = self._runtime()
        patch = runtime.tou_mapping_to_schedule_patch(runtime.read_physical_tou_mapping())
        row = next(row for row in patch if row["slot_key"] == self._slot(runtime, 4).key)
        self.assertEqual(row["tou_soc"], 20)

    def test_reverse_sync_end_boundary_does_not_belong_to_previous_range(self):
        runtime = self._runtime()
        patch = runtime.tou_mapping_to_schedule_patch(runtime.read_physical_tou_mapping())
        row = next(row for row in patch if row["slot_key"] == self._slot(runtime, 8).key)
        self.assertNotEqual(row["tou_soc"], 20)
        self.assertEqual(row["tou_soc"], 30)

    async def _assert_preserved(self, field):
        runtime = self._runtime()
        before = [getattr(slot, field) for slot in runtime.slots.values()]
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual([getattr(slot, field) for slot in runtime.slots.values()], before)

    async def test_tou_reverse_sync_preserves_manager_mode(self):
        await self._assert_preserved("mode")

    async def test_tou_reverse_sync_preserves_enabled(self):
        await self._assert_preserved("enabled")

    async def test_tou_reverse_sync_preserves_sell_power(self):
        await self._assert_preserved("sell_power")

    async def test_tou_reverse_sync_preserves_charge_current(self):
        await self._assert_preserved("charge_current")

    async def test_tou_reverse_sync_preserves_grid_charge_current(self):
        await self._assert_preserved("grid_charge_current")

    async def test_tou_reverse_sync_preserves_discharge_current(self):
        await self._assert_preserved("discharge_current")

    async def test_tou_reverse_sync_preserves_minimum_sell_soc(self):
        await self._assert_preserved("minimum_sell_soc")

    async def test_tou_reverse_sync_preserves_min_sell_price(self):
        await self._assert_preserved("min_sell_price")

    async def test_tou_reverse_sync_preserves_physical_work_mode(self):
        await self._assert_preserved("physical_work_mode")

    async def test_tou_reverse_sync_round_trip_is_stable(self):
        runtime = self._runtime()
        await runtime.async_set_physical_tou_slot(2, soc=25)
        first = runtime._tou_mapping_rows(runtime.schedule_to_tou_mapping())
        second = runtime._tou_mapping_rows(runtime.schedule_to_tou_mapping())
        self.assertEqual(first, second)

    async def test_tou_reverse_sync_round_trip_matches_confirmed_readback(self):
        runtime = self._runtime()
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertTrue(runtime._tou_mappings_match(runtime.read_physical_tou_mapping(), runtime.schedule_to_tou_mapping()))

    async def test_reverse_sync_does_not_schedule_reconciliation(self):
        runtime = self._runtime()
        runtime._schedule_schedule_reconciliation = mock.Mock(side_effect=AssertionError("reconciliation"))
        await runtime.async_set_physical_tou_slot(2, soc=25)
        runtime._schedule_schedule_reconciliation.assert_not_called()

    async def test_reverse_sync_does_not_write_tou_again(self):
        runtime = self._runtime()
        runtime.hass.services.calls.clear()
        await runtime.async_set_physical_tou_slot(2, soc=25)
        tou_calls = [call for call in runtime.hass.services.calls if "time_of_use" in str(call[2].get("entity_id", ""))]
        self.assertEqual(len(tou_calls), 1)

    async def test_reverse_sync_uses_confirmed_readback_not_request_payload(self):
        runtime = self._runtime()
        entity = runtime._tou_entity(2, "soc")
        original = runtime.async_set_number

        async def provider_rounding(entity_id, value):
            await original(entity_id, value)
            if entity_id == entity:
                state = runtime.hass.states.get(entity_id)
                runtime.hass.states.values[entity_id] = FakeState("25.05", dict(state.attributes))

        runtime.async_set_number = provider_rounding
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual(self._slot(runtime, 4).tou_soc, 25.05)

    async def test_reverse_sync_failure_restores_schedule_snapshot(self):
        runtime = self._runtime()
        before = {key: replace(slot) for key, slot in runtime.slots.items()}
        runtime._apply_reverse_sync_patch_locked = mock.Mock(side_effect=ValueError("test reverse"))
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual(runtime.slots, before)

    async def test_round_trip_failure_rolls_back_physical_written_entities(self):
        runtime = self._runtime()
        self._set_physical(runtime, socs=(20,) * 6, grids=(False,) * 6)
        entity = runtime._tou_entity(2, "start")
        before = runtime.hass.states.get(entity).state
        with self.assertRaisesRegex(ValueError, "Round-trip"):
            await runtime.async_set_physical_tou_slot(2, start="05:00")
        self.assertEqual(runtime.hass.states.get(entity).state, before)

    async def test_round_trip_failure_restores_local_schedule(self):
        runtime = self._runtime()
        self._set_physical(runtime, socs=(20,) * 6, grids=(False,) * 6)
        before = {key: replace(slot) for key, slot in runtime.slots.items()}
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, start="05:00")
        self.assertEqual(runtime.slots, before)

    async def test_reverse_sync_rollback_failure_reports_critical_status(self):
        runtime = self._runtime()
        runtime._apply_reverse_sync_patch_locked = mock.Mock(side_effect=ValueError("test reverse"))

        async def failed(_items, _snapshot):
            return False, ["test rollback"]

        runtime._async_rollback_tou_transaction = failed
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual(runtime.reverse_sync_status, "rollback_failed")
        self.assertEqual(runtime.tou_contract_status, "rollback_failed")

    async def test_reverse_sync_failure_does_not_apply_safe_defaults(self):
        runtime = self._runtime()
        runtime._apply_reverse_sync_patch_locked = mock.Mock(side_effect=ValueError("test reverse"))
        runtime.async_apply_safe_defaults = mock.AsyncMock()
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, soc=25)
        runtime.async_apply_safe_defaults.assert_not_awaited()

    async def test_disabled_control_does_not_run_reverse_sync(self):
        runtime = self._runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        runtime._async_reverse_sync_after_manual_tou_locked = mock.AsyncMock()
        with self.assertRaises(manager.ControlDisabledError):
            await runtime.async_set_physical_tou_slot(2, soc=25)
        runtime._async_reverse_sync_after_manual_tou_locked.assert_not_awaited()

    async def test_control_disabled_during_tou_write_does_not_apply_partial_reverse_sync(self):
        runtime = self._runtime()
        entity = runtime._tou_entity(2, "soc")
        runtime.control_confirmation_timeout = 2
        runtime.hass.services.ignore_once("number", "set_value", entity_id=entity)
        before = {key: replace(slot) for key, slot in runtime.slots.items()}
        task = asyncio.create_task(runtime.async_set_physical_tou_slot(2, soc=25))
        while runtime._active_tou_cancel_event is None and not task.done():
            await asyncio.sleep(0)
        await runtime.async_disable_control()
        with self.assertRaises((manager.ControlDisabledError, ValueError)):
            await task
        self.assertEqual(runtime.slots, before)

    async def test_cancelled_tou_transaction_preserves_schedule_snapshot(self):
        runtime = self._runtime()
        before = {key: replace(slot) for key, slot in runtime.slots.items()}
        waiting = asyncio.Event()
        release = asyncio.Event()
        original = runtime._async_wait_for_tou_confirmation

        async def wait(items, operation_name, expected_value_key="expected_logical_value", **kwargs):
            if expected_value_key == "previous_logical_value":
                return await original(items, operation_name, expected_value_key, **kwargs)
            waiting.set()
            await release.wait()
            return []

        runtime._async_wait_for_tou_confirmation = wait
        task = asyncio.create_task(runtime.async_set_physical_tou_slot(2, soc=25))
        await waiting.wait()
        task.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(runtime.slots, before)

    async def _assert_provider_round_trip(self, provider):
        runtime = self._runtime(provider)
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertTrue(runtime.reverse_sync_round_trip_ok)
        self.assertTrue(runtime._tou_mappings_match(runtime.read_physical_tou_mapping(), runtime.schedule_to_tou_mapping()))

    async def test_lewa_reka_reverse_sync_round_trip(self):
        await self._assert_provider_round_trip(const.PROVIDER_LEWA_REKA)

    async def test_solarman_reverse_sync_round_trip(self):
        await self._assert_provider_round_trip(const.PROVIDER_SOLARMAN)

    async def test_sunsynk_reverse_sync_round_trip(self):
        await self._assert_provider_round_trip(const.PROVIDER_SUNSYNK)

    async def test_custom_reverse_sync_round_trip(self):
        await self._assert_provider_round_trip(const.PROVIDER_CUSTOM)

    async def test_read_only_provider_never_runs_reverse_sync(self):
        runtime = self._runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        runtime._async_reverse_sync_after_manual_tou_locked = mock.AsyncMock()
        with self.assertRaises(ValueError):
            await runtime.async_set_physical_tou_slot(2, soc=25)
        runtime._async_reverse_sync_after_manual_tou_locked.assert_not_awaited()

    async def test_partial_custom_readback_rolls_back_without_false_success(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        for idx in range(1, 7):
            for kind in ("start", "soc", "grid"):
                runtime.data.pop(const.conf_tou_entity(idx, kind), None)
        entity_id = "number.custom_tou_1_soc"
        runtime.data[const.conf_tou_entity(1, "soc")] = entity_id
        runtime.hass.states.values[entity_id] = FakeState(
            "20", {"min": 0, "max": 100, "step": 1}
        )
        with self.assertRaisesRegex(ValueError, "pełnego potwierdzonego readbacku"):
            await runtime.async_set_physical_tou_slot(1, soc=60)
        self.assertEqual(float(runtime.hass.states.get(entity_id).state), 20)
        self.assertEqual(runtime.reverse_sync_status, "rollback")
        self.assertEqual(runtime.tou_contract_status, "rollback")

    async def test_reverse_sync_respects_physical_boundaries_with_identical_soc_and_grid(self):
        runtime = self._runtime()
        self._set_physical(runtime, socs=(20,) * 6, grids=(False,) * 6)
        before = runtime.hass.states.get(runtime._tou_entity(2, "start")).state
        with self.assertRaisesRegex(ValueError, "nie przechowuje takiej granicy"):
            await runtime.async_set_physical_tou_slot(2, start="05:00")
        self.assertEqual(runtime.hass.states.get(runtime._tou_entity(2, "start")).state, before)

    def test_uniform_physical_values_round_trip_is_deterministic(self):
        runtime = self._runtime()
        self._set_physical(runtime, socs=(20,) * 6, grids=(False,) * 6)
        physical = runtime.read_physical_tou_mapping()
        patch = runtime.tou_mapping_to_schedule_patch(physical)
        runtime._apply_reverse_sync_patch_locked(patch)
        first = runtime._tou_mapping_rows(runtime.schedule_to_tou_mapping())
        second = runtime._tou_mapping_rows(runtime.schedule_to_tou_mapping())
        self.assertEqual(first, second)
        self.assertNotEqual(first, runtime._tou_mapping_rows(physical))

    def test_reverse_sync_diagnostics_are_exposed(self):
        runtime = self._runtime()
        data = runtime.diagnostics()["tou_reverse_sync"]
        self.assertEqual(data["reverse_sync_status"], "idle")
        self.assertIn("reverse_sync_changed_hours", data)
        self.assertIn("reverse_sync_round_trip_ok", data)

    async def test_reverse_sync_leaves_last_tou_signature_invalid_for_next_cycle(self):
        runtime = self._runtime()
        runtime._last_tou_signature = "cached"
        await runtime.async_set_physical_tou_slot(2, soc=25)
        self.assertEqual(runtime._last_tou_signature, "")


class ScheduleSlotDraftBackend5C4Tests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_slot_save_triggers_single_mapping_recalculation(self):
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        slot_key = runtime.active_slot_key()
        original = runtime.schedule_to_tou_mapping
        with mock.patch.object(runtime, "schedule_to_tou_mapping", wraps=original) as mapping:
            await runtime.async_apply_schedule_patch(
                [{"slot_key": slot_key, "sell_power": 4321}]
            )
        self.assertEqual(mapping.call_count, 1)

    async def test_schedule_slot_patch_accepts_canonical_physical_work_mode(self):
        runtime = make_runtime()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        slot_key = runtime.active_slot_key()
        await runtime.async_apply_schedule_patch(
            [
                {
                    "slot_key": slot_key,
                    "mode": const.MODE_NORMAL_OPERATION,
                    "physical_work_mode": const.MODE_ZERO_EXPORT_CT,
                }
            ]
        )
        self.assertEqual(
            runtime.slots[slot_key].physical_work_mode,
            const.MODE_ZERO_EXPORT_CT,
        )


class TouExternalReconciliation5DTests(unittest.IsolatedAsyncioTestCase):
    """Stage 5D: external physical TOU changes cannot hide behind cache."""

    @classmethod
    def _runtime(cls, provider=const.PROVIDER_LEWA_REKA):
        runtime = TouReverseSync5C2Tests._runtime(provider)
        physical = runtime.read_physical_tou_mapping()
        runtime._apply_reverse_sync_patch_locked(
            runtime.tou_mapping_to_schedule_patch(physical)
        )
        runtime.scheduler_enabled = True
        active = runtime.slots[runtime.active_slot_key()]
        active.enabled = True
        active.mode = const.MODE_NORMAL_OPERATION
        active.physical_work_mode = const.MODE_ZERO_EXPORT
        runtime._refresh_tou_reconciliation_state()
        runtime._last_tou_signature = runtime.tou_expected_signature
        return runtime

    @staticmethod
    def _tou_entity_ids(runtime):
        return {
            runtime._tou_entity(idx, kind)
            for idx in range(1, 7)
            for kind in ("start", "soc", "grid")
            if runtime._tou_entity(idx, kind)
        }

    @classmethod
    def _tou_calls(cls, runtime):
        entity_ids = cls._tou_entity_ids(runtime)
        return [call for call in runtime.hass.services.calls if call[2].get("entity_id") in entity_ids]

    @staticmethod
    def _set_start(runtime, idx, hour):
        entity = runtime._tou_entity(idx, "start")
        state = runtime.hass.states.get(entity)
        value = f"{hour:02d}:00" if entity.startswith("select.") else f"{hour:02d}:00:00"
        runtime.hass.states.values[entity] = FakeState(value, dict(state.attributes))

    @staticmethod
    def _set_soc(runtime, idx, value):
        entity = runtime._tou_entity(idx, "soc")
        state = runtime.hass.states.get(entity)
        runtime.hass.states.values[entity] = FakeState(str(value), dict(state.attributes))

    @staticmethod
    def _set_grid(runtime, idx, enabled):
        entity = runtime._tou_entity(idx, "grid")
        state = runtime.hass.states.get(entity)
        if entity.startswith("switch."):
            value = "on" if enabled else "off"
        elif runtime.inverter_provider == const.PROVIDER_SUNSYNK:
            value = "Allow Grid & Gen" if enabled else "Allow Gen"
        else:
            value = "Grid" if enabled else "Disable"
        runtime.hass.states.values[entity] = FakeState(value, dict(state.attributes))

    @staticmethod
    def _disable_control(runtime):
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"

    @staticmethod
    def _enable_control(runtime):
        runtime.control_enabled = True
        runtime.control_status = "Aktywne"

    @staticmethod
    def _stub_periodic_updates(runtime):
        for name in (
            "async_update_sold_energy_today",
            "async_update_solcast_history",
            "async_update_learning_history",
            "async_update_energy_sample",
            "async_update_weather_forecast",
        ):
            setattr(runtime, name, mock.AsyncMock())

    async def test_last_tou_signature_does_not_hide_external_start_change(self):
        runtime = self._runtime()
        self._set_start(runtime, 2, 5)
        runtime.hass.services.calls.clear()
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(len(self._tou_calls(runtime)), 1)
        self.assertEqual(runtime._time_to_minutes(runtime.hass.states.get(runtime._tou_entity(2, "start")).state), 4 * 60)

    async def test_last_tou_signature_does_not_hide_external_soc_change(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime.hass.services.calls.clear()
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(len(self._tou_calls(runtime)), 1)
        self.assertEqual(float(runtime.hass.states.get(runtime._tou_entity(2, "soc")).state), 20)

    async def test_last_tou_signature_does_not_hide_external_grid_change(self):
        runtime = self._runtime()
        self._set_grid(runtime, 2, False)
        runtime.hass.services.calls.clear()
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(len(self._tou_calls(runtime)), 1)
        self.assertTrue(manager.provider_boolean_state(runtime.data, "grid", runtime.hass.states.get(runtime._tou_entity(2, "grid")).state))

    async def test_physical_tou_signature_is_based_on_readback(self):
        runtime = self._runtime()
        original = runtime.tou_physical_signature
        self._set_soc(runtime, 2, 25)
        runtime._refresh_tou_reconciliation_state()
        self.assertNotEqual(runtime.tou_physical_signature, original)
        self.assertNotEqual(runtime.tou_physical_signature, runtime.tou_expected_signature)

    async def test_matching_schedule_and_physical_signature_skips_write(self):
        runtime = self._runtime()
        runtime.hass.services.calls.clear()
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(self._tou_calls(runtime), [])

    async def test_external_start_change_is_reconciled_when_control_active(self):
        runtime = self._runtime()
        self._set_start(runtime, 2, 5)
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(runtime.tou_reconciliation_status, "in_sync")

    async def test_external_soc_change_is_reconciled_when_control_active(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(runtime.tou_reconciliation_status, "in_sync")

    async def test_external_grid_change_is_reconciled_when_control_active(self):
        runtime = self._runtime()
        self._set_grid(runtime, 2, False)
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(runtime.tou_reconciliation_status, "in_sync")

    async def test_external_mismatch_writes_only_changed_entity(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime.hass.services.calls.clear()
        await runtime.async_apply_time_of_use_map()
        self.assertEqual([call[2]["entity_id"] for call in self._tou_calls(runtime)], [runtime._tou_entity(2, "soc")])

    async def test_external_reconciliation_uses_existing_confirmation_and_rollback(self):
        runtime = self._runtime()
        entity = runtime._tou_entity(2, "soc")
        self._set_soc(runtime, 2, 25)
        runtime.control_confirmation_timeout = 0
        runtime.hass.services.ignore_once("number", "set_value", entity_id=entity)
        self.assertFalse(await runtime.async_apply_time_of_use_map())
        self.assertIn(runtime.tou_contract_status, ("rollback", "rollback_failed"))
        self.assertEqual(float(runtime.hass.states.get(entity).state), 25)

    async def test_external_tou_change_is_not_overwritten_when_control_disabled(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self._disable_control(runtime)
        runtime.hass.services.calls.clear()
        runtime._refresh_tou_reconciliation_state()
        self.assertEqual(self._tou_calls(runtime), [])
        self.assertEqual(float(runtime.hass.states.get(runtime._tou_entity(2, "soc")).state), 25)

    async def test_external_tou_mismatch_is_reported_when_control_disabled(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self._disable_control(runtime)
        self.assertFalse(runtime._refresh_tou_reconciliation_state())
        self.assertEqual(runtime.tou_reconciliation_status, "blocked_control_disabled")

    async def test_reenabling_control_reconciles_external_tou_change_on_next_tick(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self._disable_control(runtime)
        runtime._refresh_tou_reconciliation_state()
        self._enable_control(runtime)
        self._stub_periodic_updates(runtime)
        runtime.hass.services.calls.clear()
        await runtime.async_tick()
        self.assertEqual(float(runtime.hass.states.get(runtime._tou_entity(2, "soc")).state), 20)

    async def test_external_tou_change_is_not_overwritten_during_emergency_stop(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime.emergency_stop = True
        runtime.hass.services.calls.clear()
        runtime._refresh_tou_reconciliation_state()
        self.assertFalse(await runtime.async_apply_time_of_use_map())
        self.assertEqual(runtime.tou_reconciliation_status, "blocked_emergency_stop")
        self.assertEqual(self._tou_calls(runtime), [])

    async def test_resume_manager_allows_reconciliation_on_next_tick(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime.emergency_stop = True
        runtime.control_mode = "Stop Sell"
        self._stub_periodic_updates(runtime)
        await runtime.async_resume_manager()
        self.assertEqual(float(runtime.hass.states.get(runtime._tou_entity(2, "soc")).state), 20)

    async def test_unavailable_physical_readback_is_not_treated_as_in_sync(self):
        runtime = self._runtime()
        entity = runtime._tou_entity(2, "soc")
        runtime.hass.states.values[entity] = FakeState("unavailable")
        self.assertFalse(runtime._refresh_tou_reconciliation_state())
        self.assertFalse(runtime.tou_reconciliation_in_sync)
        self.assertFalse(runtime.tou_readback_complete)

    async def test_unavailable_physical_readback_does_not_trigger_blind_full_write(self):
        runtime = self._runtime()
        runtime.hass.states.values[runtime._tou_entity(2, "soc")] = FakeState("unavailable")
        runtime.hass.services.calls.clear()
        self.assertFalse(await runtime.async_apply_time_of_use_map())
        self.assertEqual(self._tou_calls(runtime), [])

    async def test_readback_recovery_allows_normal_reconciliation(self):
        runtime = self._runtime()
        entity = runtime._tou_entity(2, "soc")
        runtime.hass.states.values[entity] = FakeState("unavailable")
        self.assertFalse(await runtime.async_apply_time_of_use_map())
        self._set_soc(runtime, 2, 25)
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(float(runtime.hass.states.get(entity).state), 20)

    async def _assert_provider_detection(self, provider):
        runtime = self._runtime(provider)
        self._set_soc(runtime, 2, 25)
        self.assertFalse(runtime._refresh_tou_reconciliation_state())
        self.assertIn("slot_2.soc", runtime.tou_mismatched_fields)

    async def test_lewa_reka_external_tou_change_detection(self):
        await self._assert_provider_detection(const.PROVIDER_LEWA_REKA)

    async def test_solarman_external_tou_change_detection(self):
        await self._assert_provider_detection(const.PROVIDER_SOLARMAN)

    async def test_sunsynk_external_tou_change_detection(self):
        await self._assert_provider_detection(const.PROVIDER_SUNSYNK)

    async def test_custom_full_mapping_external_tou_change_detection(self):
        await self._assert_provider_detection(const.PROVIDER_CUSTOM)

    async def test_custom_partial_mapping_does_not_claim_full_tou_sync(self):
        runtime = make_runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_CUSTOM
        for idx in range(1, 7):
            for kind in ("start", "soc", "grid"):
                runtime.data.pop(const.conf_tou_entity(idx, kind), None)
        runtime.data[const.conf_tou_entity(1, "soc")] = "number.custom_tou_1_soc"
        runtime.hass.states.values["number.custom_tou_1_soc"] = FakeState("20")
        self.assertFalse(runtime._refresh_tou_reconciliation_state())
        self.assertFalse(runtime.tou_readback_complete)
        self.assertEqual(runtime.tou_reconciliation_status, "waiting_readback")

    async def test_read_only_provider_reports_mismatch_without_write(self):
        runtime = self._runtime()
        for idx in range(1, 7):
            for kind in ("start", "soc", "grid"):
                runtime.data[const.conf_tou_entity(idx, kind)] = runtime._tou_entity(idx, kind)
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        self._set_soc(runtime, 2, 25)
        runtime.hass.services.calls.clear()
        self.assertFalse(runtime._refresh_tou_reconciliation_state())
        self.assertEqual(runtime.tou_reconciliation_status, "read_only")
        self.assertEqual(self._tou_calls(runtime), [])

    async def test_own_confirmed_tou_write_does_not_trigger_second_write(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        runtime.hass.services.calls.clear()
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(self._tou_calls(runtime), [])

    async def test_reverse_synced_tou_does_not_create_reconciliation_loop(self):
        runtime = self._runtime()
        await runtime.async_set_physical_tou_slot(2, soc=25)
        runtime.hass.services.calls.clear()
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertEqual(self._tou_calls(runtime), [])

    async def test_reconciliation_updates_physical_signature_after_confirmation(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime._refresh_tou_reconciliation_state()
        stale = runtime.tou_physical_signature
        self.assertTrue(await runtime.async_apply_time_of_use_map())
        self.assertNotEqual(runtime.tou_physical_signature, stale)
        self.assertEqual(runtime._last_physical_tou_signature, runtime.tou_expected_signature)

    async def test_reload_does_not_trust_stale_tou_signature(self):
        runtime = self._runtime()
        stale = runtime._last_tou_signature
        self._set_start(runtime, 2, 5)
        runtime._last_tou_signature = stale
        runtime._last_physical_tou_signature = stale
        self.assertFalse(runtime._refresh_tou_reconciliation_state())
        self.assertIn("slot_2.start", runtime.tou_mismatched_fields)

    async def test_first_tick_confirms_physical_tou_before_skipping_write(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime._last_tou_signature = runtime.tou_expected_signature
        self._stub_periodic_updates(runtime)
        runtime.hass.services.calls.clear()
        await runtime.async_tick()
        self.assertEqual(float(runtime.hass.states.get(runtime._tou_entity(2, "soc")).state), 20)

    async def test_tou_reconciliation_diagnostics_report_in_sync(self):
        runtime = self._runtime()
        data = runtime.diagnostics()["tou_reconciliation"]
        self.assertTrue(data["in_sync"])
        self.assertEqual(data["reconciliation_status"], "in_sync")

    async def test_tou_reconciliation_diagnostics_report_mismatch(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime._refresh_tou_reconciliation_state()
        data = runtime.diagnostics()["tou_reconciliation"]
        self.assertFalse(data["in_sync"])
        self.assertEqual(data["reconciliation_status"], "mismatch")

    async def test_tou_reconciliation_diagnostics_report_control_block(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self._disable_control(runtime)
        runtime._refresh_tou_reconciliation_state()
        self.assertEqual(runtime.diagnostics()["tou_reconciliation"]["reconciliation_status"], "blocked_control_disabled")

    async def test_tou_reconciliation_diagnostics_report_emergency_stop_block(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        runtime.emergency_stop = True
        runtime._refresh_tou_reconciliation_state()
        self.assertEqual(runtime.diagnostics()["tou_reconciliation"]["reconciliation_status"], "blocked_emergency_stop")

    async def test_tou_reconciliation_diagnostics_list_mismatched_fields(self):
        runtime = self._runtime()
        self._set_soc(runtime, 2, 25)
        self._set_grid(runtime, 2, False)
        runtime._refresh_tou_reconciliation_state()
        self.assertIn("slot_2.soc", runtime.tou_mismatched_fields)
        self.assertIn("slot_2.grid_charge", runtime.tou_mismatched_fields)


class ControlReenableReconciliation5F5Tests(unittest.IsolatedAsyncioTestCase):
    """Stage 5F.5: enabling master control immediately runs the normal Manager decision."""

    @staticmethod
    def _stub_periodic_updates(runtime):
        for name in (
            "async_update_sold_energy_today",
            "async_update_solcast_history",
            "async_update_learning_history",
            "async_update_energy_sample",
            "async_update_weather_forecast",
        ):
            setattr(runtime, name, mock.AsyncMock())

    def _prepare_runtime(self, runtime=None):
        runtime = runtime or make_runtime()
        runtime.hass.async_create_task = asyncio.create_task
        self._stub_periodic_updates(runtime)
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
        return runtime

    async def _enable_and_wait(self, runtime):
        await runtime.async_enable_control()
        task = runtime._schedule_reconcile_task
        self.assertIsNotNone(task, "enable must schedule an immediate reconciliation task")
        await task
        self.assertIsNone(runtime._schedule_reconcile_task)
        self.assertFalse(runtime._schedule_reconcile_requested)

    @staticmethod
    def _set_physical(runtime, *, mode, sell, discharge, charge, grid):
        runtime.hass.states.values[runtime.work_mode_select] = FakeState(mode)
        runtime.hass.states.values[runtime.max_sell_power_number] = FakeState(str(sell))
        runtime.hass.states.values[runtime.discharge_current_number] = FakeState(str(discharge))
        runtime.hass.states.values[runtime.charge_current_number] = FakeState(str(charge))
        runtime.hass.states.values[runtime.grid_charge_current_number] = FakeState(str(grid))

    @staticmethod
    def _control_calls(runtime):
        ids = {
            runtime.work_mode_select,
            runtime.max_sell_power_number,
            runtime.discharge_current_number,
            runtime.charge_current_number,
            runtime.grid_charge_current_number,
        }
        return [call for call in runtime.hass.services.calls if call[2].get("entity_id") in ids]

    async def test_reenable_control_immediately_applies_current_schedule_slot(self):
        runtime = self._prepare_runtime()
        slot = configure_selling_slot(runtime)
        slot.charge_current = 75
        slot.charge_enabled = False
        self._set_physical(runtime, mode=const.MODE_ZERO_EXPORT, sell=1234, discharge=25, charge=15, grid=10)
        runtime.hass.services.calls.clear()

        await self._enable_and_wait(runtime)

        self.assertTrue(manager.logical_mode_matches(
            runtime.data,
            const.MODE_SELLING_FIRST,
            runtime.hass.states.get(runtime.work_mode_select).state,
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), 5000)
        self.assertEqual(float(runtime.hass.states.get(runtime.discharge_current_number).state), 120)
        self.assertEqual(float(runtime.hass.states.get(runtime.charge_current_number).state), 75)
        self.assertTrue(self._control_calls(runtime))

    async def test_reenable_control_does_not_wait_for_periodic_manager_tick(self):
        runtime = self._prepare_runtime()
        runtime.async_tick = mock.AsyncMock(side_effect=AssertionError("periodic tick must not be called"))
        runtime._async_tick_impl = mock.AsyncMock(return_value=True)

        await self._enable_and_wait(runtime)

        runtime._async_tick_impl.assert_awaited_once_with()
        runtime.async_tick.assert_not_awaited()

    async def test_reenable_control_applies_current_normal_slot(self):
        runtime = self._prepare_runtime()
        runtime.scheduler_enabled = True
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT
        slot.sell_power = 3100
        slot.discharge_current = 55
        slot.charge_current = 45
        self._set_physical(runtime, mode="Selling First", sell=9000, discharge=90, charge=90, grid=5)

        await self._enable_and_wait(runtime)

        self.assertTrue(manager.logical_mode_matches(
            runtime.data,
            const.MODE_NORMAL_OPERATION,
            runtime.hass.states.get(runtime.work_mode_select).state,
            const.MODE_ZERO_EXPORT_CT,
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), 3100)
        self.assertEqual(float(runtime.hass.states.get(runtime.discharge_current_number).state), 55)
        self.assertEqual(float(runtime.hass.states.get(runtime.charge_current_number).state), 45)

    async def test_reenable_control_applies_current_charge_slot(self):
        runtime = self._prepare_runtime()
        runtime.scheduler_enabled = True
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_CHARGE
        slot.charge_enabled = True
        slot.charge_current = 88
        slot.discharge_current = 44
        slot.grid_charge_current = 33
        slot.tou_soc = 90
        self._set_physical(runtime, mode="Selling First", sell=1000, discharge=10, charge=10, grid=10)

        await self._enable_and_wait(runtime)

        self.assertTrue(manager.logical_mode_matches(
            runtime.data,
            const.MODE_NORMAL_OPERATION,
            runtime.hass.states.get(runtime.work_mode_select).state,
            runtime.default_normal_physical_work_mode(),
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.discharge_current_number).state), 44)
        self.assertEqual(float(runtime.hass.states.get(runtime.charge_current_number).state), 88)
        self.assertEqual(float(runtime.hass.states.get(runtime.grid_charge_current_number).state), 33)
        self.assertTrue(any(
            call[:2] == ("switch", "turn_on") and "_grid_charge" in str(call[2].get("entity_id"))
            for call in runtime.hass.services.calls
        ))

    async def test_reenable_control_applies_current_selling_slot(self):
        runtime = self._prepare_runtime()
        slot = configure_selling_slot(runtime)
        slot.discharge_current = 111
        slot.charge_current = 66
        self._set_physical(runtime, mode=const.MODE_ZERO_EXPORT, sell=2500, discharge=22, charge=33, grid=12)

        await self._enable_and_wait(runtime)

        self.assertTrue(manager.logical_mode_matches(
            runtime.data,
            const.MODE_SELLING_FIRST,
            runtime.hass.states.get(runtime.work_mode_select).state,
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), 5000)
        self.assertEqual(float(runtime.hass.states.get(runtime.discharge_current_number).state), 111)
        self.assertEqual(float(runtime.hass.states.get(runtime.charge_current_number).state), 66)

    async def test_reenable_control_uses_standard_defaults_for_disabled_slot(self):
        runtime = self._prepare_runtime()
        runtime.scheduler_enabled = True
        runtime.active_slot.enabled = False
        self._set_physical(runtime, mode="Selling First", sell=2500, discharge=22, charge=33, grid=12)

        await self._enable_and_wait(runtime)

        self.assertTrue(manager.logical_mode_matches(
            runtime.data,
            const.MODE_NORMAL_OPERATION,
            runtime.hass.states.get(runtime.work_mode_select).state,
            runtime.default_normal_physical_work_mode(),
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), runtime.default_sell_power)
        self.assertEqual(float(runtime.hass.states.get(runtime.discharge_current_number).state), runtime.default_discharge_current)

    async def test_reenable_control_respects_minimum_sell_soc(self):
        runtime = self._prepare_runtime(make_runtime(soc="20"))
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 30

        await self._enable_and_wait(runtime)

        self.assertFalse(manager.logical_mode_matches(
            runtime.data,
            const.MODE_SELLING_FIRST,
            runtime.hass.states.get(runtime.work_mode_select).state,
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), runtime.default_sell_power)

    async def test_reenable_control_respects_min_sell_price(self):
        runtime = self._prepare_runtime(make_runtime(price="0.50"))
        slot = configure_selling_slot(runtime)
        slot.min_sell_price = 1.00

        await self._enable_and_wait(runtime)

        self.assertFalse(manager.logical_mode_matches(
            runtime.data,
            const.MODE_SELLING_FIRST,
            runtime.hass.states.get(runtime.work_mode_select).state,
        ))
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), runtime.default_sell_power)

    async def test_reenable_control_does_not_apply_targets_during_emergency_stop(self):
        runtime = self._prepare_runtime()
        configure_selling_slot(runtime)
        runtime.emergency_stop = True
        runtime.hass.services.calls.clear()

        await runtime.async_enable_control()
        await asyncio.sleep(0)

        self.assertTrue(runtime.control_enabled)
        self.assertEqual(runtime.control_status, "Aktywne")
        self.assertTrue(runtime.emergency_stop)
        self.assertIsNone(runtime._schedule_reconcile_task)
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_reenable_control_writes_only_changed_current_slot_targets(self):
        runtime = self._prepare_runtime()
        configure_selling_slot(runtime)
        self._set_physical(runtime, mode="Selling First", sell=5000, discharge=5, charge=120, grid=60)
        runtime.hass.services.calls.clear()

        await self._enable_and_wait(runtime)

        calls = self._control_calls(runtime)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2]["entity_id"], runtime.discharge_current_number)
        self.assertEqual(float(calls[0][2]["value"]), 120)

    async def test_reenable_control_reconciles_external_tou_change(self):
        runtime = self._prepare_runtime(TouExternalReconciliation5DTests._runtime())
        TouExternalReconciliation5DTests._set_soc(runtime, 2, 25)
        runtime._refresh_tou_reconciliation_state()
        runtime.hass.services.calls.clear()

        await self._enable_and_wait(runtime)

        calls = TouExternalReconciliation5DTests._tou_calls(runtime)
        self.assertEqual([call[2]["entity_id"] for call in calls], [runtime._tou_entity(2, "soc")])
        self.assertEqual(float(runtime.hass.states.get(runtime._tou_entity(2, "soc")).state), 20)

    async def test_reenable_control_does_not_rewrite_matching_tou(self):
        runtime = self._prepare_runtime(TouExternalReconciliation5DTests._runtime())
        runtime.hass.services.calls.clear()

        await self._enable_and_wait(runtime)

        self.assertEqual(TouExternalReconciliation5DTests._tou_calls(runtime), [])

    async def test_fast_off_on_does_not_start_duplicate_reconciliation(self):
        runtime = self._prepare_runtime()
        tick_calls = 0

        async def tracked_tick():
            nonlocal tick_calls
            tick_calls += 1
            return True

        runtime._async_tick_impl = tracked_tick
        await runtime.async_enable_control()
        first_task = runtime._schedule_reconcile_task
        await runtime.async_disable_control()
        await runtime.async_enable_control()

        self.assertIs(first_task, runtime._schedule_reconcile_task)
        await first_task
        self.assertEqual(tick_calls, 1)
        self.assertIsNone(runtime._schedule_reconcile_task)


class ManagerActionSemantics5F6Tests(unittest.IsolatedAsyncioTestCase):
    """Stage 5F.6: planned and executed actions describe one real Manager cycle."""

    @staticmethod
    def _stub_periodic_updates(runtime):
        runtime.weather_last_updated = manager.ha_now()
        for name in (
            "async_update_sold_energy_today",
            "async_update_solcast_history",
            "async_update_learning_history",
            "async_update_energy_sample",
            "async_update_weather_forecast",
        ):
            setattr(runtime, name, mock.AsyncMock())

    def _runtime(self):
        runtime = make_runtime()
        self._stub_periodic_updates(runtime)
        runtime.notify_update = mock.Mock()
        return runtime

    @staticmethod
    def _normal_slot(runtime, physical=const.MODE_ZERO_EXPORT):
        runtime.scheduler_enabled = True
        slot = runtime.active_slot
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = physical
        return slot

    async def test_planned_action_describes_current_normal_slot(self):
        runtime = self._runtime()
        self._normal_slot(runtime, const.MODE_ZERO_EXPORT)

        self.assertEqual(runtime._planned_manager_action_text(), "Normalna praca — pomiar Load")

    async def test_planned_action_describes_current_selling_slot(self):
        runtime = self._runtime()
        configure_selling_slot(runtime)

        self.assertEqual(runtime._planned_manager_action_text(), "Sprzedaż — 5,0 kW")

    async def test_planned_action_describes_current_charge_slot(self):
        runtime = self._runtime()
        runtime.scheduler_enabled = True
        slot = runtime.active_slot
        slot.enabled = True
        slot.mode = const.MODE_CHARGE
        slot.charge_enabled = True
        slot.charge_current = 88
        slot.tou_soc = 90

        self.assertEqual(
            runtime._planned_manager_action_text(),
            "Ładowanie z sieci — 88 A, cel SOC 90%",
        )

    async def test_executed_action_reports_no_change_when_targets_already_match(self):
        runtime = self._runtime()
        self._normal_slot(runtime)

        async def apply_matching_target():
            changed = await runtime.async_set_number_if_needed(
                runtime.max_sell_power_number, 0
            )
            self.assertFalse(changed)
            return True

        runtime.async_apply_targets = apply_matching_target
        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(runtime.executed_manager_action, "Bez zmian — ustawienia zgodne")
        self.assertEqual(runtime._physical_write_count, 0)

    async def test_executed_action_reports_applied_when_write_occurs(self):
        runtime = self._runtime()
        self._normal_slot(runtime)

        async def apply_changed_target():
            changed = await runtime.async_set_number_if_needed(
                runtime.max_sell_power_number, 5000
            )
            self.assertTrue(changed)
            return True

        runtime.async_apply_targets = apply_changed_target
        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Zastosowano: Normalna praca — pomiar Load",
        )
        self.assertEqual(runtime._physical_write_count, 1)

    async def test_executed_action_reports_control_disabled(self):
        runtime = self._runtime()
        self._normal_slot(runtime)
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"

        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Nie wykonano — sterowanie wyłączone",
        )

    async def test_executed_action_reports_emergency_stop(self):
        runtime = self._runtime()
        runtime.emergency_stop = True
        runtime.async_apply_safe_defaults = mock.AsyncMock(return_value=True)

        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Nie wykonano — zatrzymanie awaryjne",
        )

    async def test_planned_action_still_updates_when_control_disabled(self):
        runtime = self._runtime()
        configure_selling_slot(runtime)
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"

        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.planned_manager_action,
            "Sprzedaż — 5,0 kW — tylko monitorowanie",
        )

    async def test_actions_do_not_show_idle_after_successful_manager_cycle(self):
        runtime = self._runtime()
        self._normal_slot(runtime)
        runtime.async_apply_targets = mock.AsyncMock(return_value=True)

        self.assertTrue(await runtime._async_tick_impl())

        self.assertNotIn("idle", runtime.planned_manager_action.lower())
        self.assertNotIn("idle", runtime.executed_manager_action.lower())
        self.assertEqual(runtime.executed_manager_action, "Bez zmian — ustawienia zgodne")

    async def test_actions_show_waiting_before_first_manager_cycle(self):
        runtime = self._runtime()

        self.assertEqual(
            runtime.planned_manager_action,
            "Oczekiwanie na pierwszy cykl Managera",
        )
        self.assertEqual(
            runtime.executed_manager_action,
            "Oczekiwanie na pierwszy cykl Managera",
        )

    async def test_solarman_planned_and_executed_actions_are_meaningful(self):
        runtime = self._runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_SOLARMAN
        self._normal_slot(runtime, const.MODE_ZERO_EXPORT)
        runtime.async_apply_targets = mock.AsyncMock(return_value=True)

        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(runtime.planned_manager_action, "Normalna praca — pomiar Load")
        self.assertEqual(runtime.executed_manager_action, "Bez zmian — ustawienia zgodne")

    async def test_solarman_executed_action_reports_real_change(self):
        runtime = self._runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_SOLARMAN
        self._normal_slot(runtime, const.MODE_ZERO_EXPORT)

        async def apply_changed_target():
            return await runtime.async_set_number_if_needed(
                runtime.max_sell_power_number, 4321
            ) or True

        runtime.async_apply_targets = apply_changed_target
        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Zastosowano: Normalna praca — pomiar Load",
        )
        self.assertEqual(float(runtime.hass.states.get(runtime.max_sell_power_number).state), 4321)

    async def test_manager_actions_follow_control_off_and_reenable_cycle(self):
        runtime = self._runtime()
        self._normal_slot(runtime, const.MODE_ZERO_EXPORT_CT)
        runtime.hass.async_create_task = asyncio.create_task
        runtime.async_apply_targets = mock.AsyncMock(return_value=True)

        await runtime.async_disable_control()
        self.assertEqual(
            runtime.planned_manager_action,
            "Normalna praca — pomiar CT — tylko monitorowanie",
        )
        self.assertTrue(await runtime._async_tick_impl())
        self.assertIn("pomiar CT", runtime.planned_manager_action)
        self.assertIn("tylko monitorowanie", runtime.planned_manager_action)
        self.assertEqual(
            runtime.executed_manager_action,
            "Nie wykonano — sterowanie wyłączone",
        )

        await runtime.async_enable_control()
        await runtime._schedule_reconcile_task

        self.assertEqual(runtime.planned_manager_action, "Normalna praca — pomiar CT")
        self.assertEqual(runtime.executed_manager_action, "Bez zmian — ustawienia zgodne")

    async def test_executed_action_reports_error_without_traceback(self):
        runtime = self._runtime()
        self._normal_slot(runtime)

        async def fail_targets():
            runtime.last_error = "Brak poprawnego odczytu ustawień falownika"
            return False

        runtime.async_apply_targets = fail_targets
        self.assertFalse(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Błąd wykonania — Brak poprawnego odczytu ustawień falownika",
        )
        self.assertNotIn("Traceback", runtime.executed_manager_action)

    async def test_executed_action_reports_rollback(self):
        runtime = self._runtime()
        self._normal_slot(runtime)

        async def rollback_targets():
            runtime.last_error = "Przywrócono poprzednie ustawienia po błędzie zapisu"
            return False

        runtime.async_apply_targets = rollback_targets
        self.assertFalse(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Przywrócono poprzednie ustawienia po błędzie",
        )

    async def test_planned_action_explains_sale_blocked_by_soc(self):
        runtime = self._runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 60

        action = runtime._planned_manager_action_text()

        self.assertIn("Sprzedaż wstrzymana", action)
        self.assertIn("SOC 50%", action)
        self.assertIn("limitu 60%", action)

    async def test_planned_action_explains_sale_blocked_by_price(self):
        runtime = self._runtime()
        slot = configure_selling_slot(runtime)
        slot.min_sell_price = 1.00

        action = runtime._planned_manager_action_text()

        self.assertIn("Sprzedaż wstrzymana", action)
        self.assertIn("cena 0.50 PLN/kWh", action)
        self.assertIn("progu 1.00 PLN/kWh", action)

    async def test_read_only_provider_reports_explicit_execution_block(self):
        runtime = self._runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        self._normal_slot(runtime)

        self.assertTrue(await runtime._async_tick_impl())

        self.assertIn("tylko do odczytu", runtime.executed_manager_action)
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_read_only_provider_keeps_emergency_status_priority(self):
        runtime = self._runtime()
        runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
        runtime.emergency_stop = True

        self.assertTrue(await runtime._async_tick_impl())

        self.assertEqual(
            runtime.executed_manager_action,
            "Nie wykonano — zatrzymanie awaryjne",
        )
        self.assertEqual(runtime.hass.services.calls, [])

    async def test_completed_action_is_published_without_energy_change(self):
        runtime = self._runtime()
        self._normal_slot(runtime)
        runtime.async_apply_targets = mock.AsyncMock(return_value=True)

        await runtime._async_tick_impl()

        runtime.notify_update.assert_called()
        self.assertEqual(runtime.executed_manager_action, "Bez zmian — ustawienia zgodne")


class CanonicalPriceManagerIntegrationTests(unittest.TestCase):
    def test_explicit_empty_four_fields_survive_runtime_reload_without_provider_fallback(self):
        runtime = make_runtime()
        for key in (
            const.CONF_PRICE_SENSOR,
            const.CONF_SELL_PRICE_TOMORROW_SENSOR,
            const.CONF_BUY_PRICE_TODAY_SENSOR,
            const.CONF_BUY_PRICE_TOMORROW_SENSOR,
        ):
            runtime.data[key] = ""
        runtime.hass.states.values.update({
            const.DEFAULT_BUY_PRICE_TODAY_SENSOR: FakeState("0.20"),
            const.DEFAULT_BUY_PRICE_TOMORROW_SENSOR: FakeState("0.21"),
            const.DEFAULT_PRICE_SENSOR: FakeState("0.80"),
            const.DEFAULT_SELL_PRICE_TOMORROW_SENSOR: FakeState("0.81"),
        })
        self.assertIsNone(runtime.buy_price_today_sensor)
        self.assertIsNone(runtime.buy_price_tomorrow_sensor)
        self.assertIsNone(runtime.price_sensor)
        self.assertIsNone(runtime.sell_price_tomorrow_sensor)
        canonical = runtime.canonical_price_context(manager.ha_now(), [])
        self.assertEqual(canonical["buy"]["rows"], [])
        self.assertEqual(canonical["sell"]["rows"], [])
        self.assertEqual(canonical["buy"]["diagnostics"]["status"], "price_source_not_configured")
        self.assertEqual(canonical["sell"]["diagnostics"]["status"], "price_source_not_configured")
        reloaded = manager.DeyeEnergyManagerRuntime(runtime.hass, "reload", dict(runtime.data))
        self.assertIsNone(reloaded.buy_price_today_sensor)
        self.assertIsNone(reloaded.price_sensor)
        self.assertEqual(reloaded.price_contract("buy")["today_entity"], "")
        self.assertEqual(reloaded.price_contract("sell")["today_entity"], "")

    def test_tariff_editor_save_persists_explicit_empty_over_previous_defaults(self):
        runtime = make_runtime()
        runtime.data.update({
            const.CONF_BUY_PRICE_TODAY_SENSOR: "",
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: "",
            const.CONF_PRICE_SENSOR: "",
            const.CONF_SELL_PRICE_TOMORROW_SENSOR: "",
        })
        runtime._tariff_catalog_manager = types.SimpleNamespace(catalog={
            "providers": {
                const.DEFAULT_OSD_PROVIDER: {
                    "tariffs": {const.DEFAULT_TARIFF_PLAN: {}},
                },
            },
        })
        normalized = runtime.validate_tariff_settings({
            const.CONF_BUY_PRICE_CONTRACT: {
                "source_adapter": "pstryk", "today_entity": "sensor.stale_buy", "tomorrow_entity": "sensor.stale_buy_tomorrow",
            },
            const.CONF_SELL_PRICE_CONTRACT: {
                "source_adapter": "pstryk", "today_entity": "sensor.stale_sell", "tomorrow_entity": "sensor.stale_sell_tomorrow",
            },
        })
        self.assertEqual(normalized[const.CONF_BUY_PRICE_TODAY_SENSOR], "")
        self.assertEqual(normalized[const.CONF_BUY_PRICE_TOMORROW_SENSOR], "")
        self.assertEqual(normalized[const.CONF_PRICE_SENSOR], "")
        self.assertEqual(normalized[const.CONF_SELL_PRICE_TOMORROW_SENSOR], "")
        runtime.data.update(normalized)
        self.assertIsNone(runtime.buy_price_today_sensor)
        self.assertIsNone(runtime.price_sensor)
        self.assertEqual(runtime.price_contract("buy")["stable_identity_today_status"], "unmapped")
        self.assertEqual(runtime.price_contract("sell")["stable_identity_today_reason"], "user_unmapped")

    def test_mixed_sell_rce_and_buy_empty_keeps_directions_independent(self):
        runtime = make_runtime()
        now = manager.ha_now()
        sell_today = "sensor.rce_sell_today"
        sell_tomorrow = "sensor.rce_sell_tomorrow"

        def quarters(day):
            rows = []
            for index in range(96):
                start = day.replace(hour=0, minute=0) + timedelta(minutes=index * 15)
                end = start + timedelta(minutes=15)
                rows.append({
                    "period": f"{start:%H:%M} - {'24:00' if end.date() != start.date() else end.strftime('%H:%M')}",
                    "dtime": end.strftime("%Y-%m-%d %H:%M:%S"),
                    "business_date": start.date().isoformat(),
                    "rce_pln": 0.8,
                })
            return rows

        runtime.data.update({
            const.CONF_BUY_PRICE_TODAY_SENSOR: "",
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: "",
            const.CONF_PRICE_SENSOR: sell_today,
            const.CONF_SELL_PRICE_TOMORROW_SENSOR: sell_tomorrow,
            const.CONF_SELL_PRICE_CONTRACT: {
                "source_adapter": "rce_pse", "semantic_scope": "energy_only",
                "includes_distribution_variable": False, "price_basis": "gross",
                "unit": "PLN/kWh", "list_attribute": "prices",
                "today_entity": sell_today, "tomorrow_entity": sell_tomorrow,
            },
        })
        runtime.hass.states.values[sell_today] = FakeState("unknown", {"prices": quarters(now)}, sell_today)
        runtime.hass.states.values[sell_tomorrow] = FakeState("unknown", {"prices": quarters(now + timedelta(days=1))}, sell_tomorrow)
        canonical = runtime.canonical_price_context(now, [])
        self.assertEqual(canonical["buy"]["rows"], [])
        self.assertEqual(canonical["buy"]["diagnostics"]["status"], "price_source_not_configured")
        self.assertEqual(len(canonical["sell"]["rows"]), 48)
        self.assertEqual(canonical["sell"]["contract"]["source_adapter"], "rce_pse")

    def test_mixed_buy_pstryk_and_sell_empty_keeps_directions_independent(self):
        runtime = make_runtime()
        now = manager.ha_now()
        buy_today = "sensor.buy_today_selected"
        buy_tomorrow = "sensor.buy_tomorrow_selected"
        runtime.data.update({
            const.CONF_PRICE_SENSOR: "",
            const.CONF_SELL_PRICE_TOMORROW_SENSOR: "",
            const.CONF_BUY_PRICE_TODAY_SENSOR: buy_today,
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: buy_tomorrow,
            const.CONF_BUY_PRICE_CONTRACT: {
                "source_adapter": "pstryk", "today_entity": buy_today, "tomorrow_entity": buy_tomorrow,
            },
        })
        runtime.hass.states.values[buy_today] = FakeState("unknown", {"today_prices": [
            {"start": now.replace(hour=hour).isoformat(), "end": (now.replace(hour=hour) + timedelta(hours=1)).isoformat(), "price": 0.3}
            for hour in range(24)
        ]}, buy_today)
        tomorrow = now + timedelta(days=1)
        runtime.hass.states.values[buy_tomorrow] = FakeState("unknown", {"tomorrow_prices": [
            {"start": tomorrow.replace(hour=hour).isoformat(), "end": (tomorrow.replace(hour=hour) + timedelta(hours=1)).isoformat(), "price": 0.4}
            for hour in range(24)
        ]}, buy_tomorrow)
        canonical = runtime.canonical_price_context(now, [])
        self.assertEqual(len(canonical["buy"]["rows"]), 48)
        self.assertEqual(canonical["sell"]["rows"], [])
        self.assertEqual(canonical["sell"]["diagnostics"]["status"], "price_source_not_configured")

    def test_user_mapping_is_absolute_and_missing_mapping_never_falls_back_to_provider_default(self):
        runtime = make_runtime()
        runtime.data[const.CONF_BUY_PRICE_TODAY_SENSOR] = "sensor.user_selected_missing"
        runtime.hass.states.values[const.DEFAULT_BUY_PRICE_TODAY_SENSOR] = FakeState(
            "unknown",
            {"today_prices": [
                {"start": manager.ha_now().replace(hour=hour).isoformat(),
                 "end": (manager.ha_now().replace(hour=hour) + timedelta(hours=1)).isoformat(),
                 "price": 0.11}
                for hour in range(24)
            ]},
            const.DEFAULT_BUY_PRICE_TODAY_SENSOR,
        )
        contract = runtime.price_contract("buy")
        self.assertEqual(contract["today_entity"], "sensor.user_selected_missing")
        self.assertEqual(contract["stable_identity_today_status"], "mapped_entity_missing")
        canonical = runtime.canonical_price_context(manager.ha_now(), [])
        self.assertEqual(canonical["buy"]["rows"], [])
        self.assertEqual(
            canonical["buy"]["diagnostics"]["resolver"]["today"]["status"],
            "mapped_entity_missing",
        )

    def test_stable_registry_identity_survives_rename_without_switching_entity(self):
        runtime = make_runtime()
        old_entity = "sensor.old_price_name"
        new_entity = "sensor.moja_cena"
        now = manager.ha_now()
        runtime.hass.states.values[new_entity] = FakeState(
            "unknown",
            {"today_prices": [
                {"start": now.replace(hour=hour).isoformat(),
                 "end": (now.replace(hour=hour) + timedelta(hours=1)).isoformat(),
                 "price": 0.44}
                for hour in range(24)
            ]},
            new_entity,
        )
        registry_entry = types.SimpleNamespace(
            id="stable-entry", entity_id=new_entity, platform="pstryk",
            config_entry_id="pstryk-config", unique_id="stable-price", device_id="device-1",
        )
        registry = types.SimpleNamespace(entities={new_entity: registry_entry}, async_get=lambda entity_id: registry.entities.get(entity_id))
        runtime.data[const.CONF_BUY_PRICE_TODAY_SENSOR] = old_entity
        runtime.data[const.CONF_BUY_PRICE_CONTRACT] = {
            "source_adapter": "pstryk",
            "today_entity": old_entity,
            "today_binding": {
                "entity_id": old_entity, "registry_entry_id": "stable-entry",
                "platform": "pstryk", "config_entry_id": "pstryk-config",
                "unique_id": "stable-price", "device_id": "device-1",
            },
        }
        entity_registry = sys.modules["homeassistant.helpers.entity_registry"]
        with mock.patch.object(entity_registry, "async_get", return_value=registry):
            contract = runtime.price_contract("buy")
            self.assertEqual(contract["resolved_today_entity"], new_entity)
            self.assertEqual(contract["stable_identity_today_status"], "renamed_resolved")
            self.assertEqual(contract["source_adapter"], "pstryk")
            canonical = runtime.canonical_price_context(now, [])
        self.assertEqual(len(canonical["buy"]["rows"]), 24)
        self.assertEqual(canonical["buy"]["diagnostics"]["resolver"]["today"]["mapped_entity"], old_entity)
        self.assertEqual(canonical["buy"]["diagnostics"]["resolver"]["today"]["resolved_entity"], new_entity)

    def test_reused_old_entity_id_cannot_override_saved_stable_identity(self):
        runtime = make_runtime()
        old_entity = "sensor.old_price_name"
        new_entity = "sensor.same_source_after_rename"
        runtime.hass.states.values[old_entity] = FakeState("unknown", {"today_prices": []}, old_entity)
        runtime.hass.states.values[new_entity] = FakeState("unknown", {"today_prices": []}, new_entity)
        wrong_entry = types.SimpleNamespace(id="other-entry", entity_id=old_entity, platform="other", config_entry_id="other", unique_id="other", device_id="other")
        right_entry = types.SimpleNamespace(id="stable-entry", entity_id=new_entity, platform="pstryk", config_entry_id="pstryk", unique_id="price", device_id="device")
        registry = types.SimpleNamespace(
            entities={old_entity: wrong_entry, new_entity: right_entry},
            async_get=lambda entity_id: registry.entities.get(entity_id),
        )
        binding = {"entity_id": old_entity, "registry_entry_id": "stable-entry", "platform": "pstryk", "config_entry_id": "pstryk", "unique_id": "price"}
        entity_registry = sys.modules["homeassistant.helpers.entity_registry"]
        with mock.patch.object(entity_registry, "async_get", return_value=registry):
            resolved, status, _reason = runtime.resolve_price_binding(old_entity, binding)
        self.assertEqual(resolved, new_entity)
        self.assertEqual(status, "renamed_resolved")

    def test_strict_contract_validation_rejects_unsupported_mapped_series(self):
        runtime = make_runtime()
        entity_id = "sensor.unsupported_price_series"
        runtime.hass.states.values[entity_id] = FakeState("0.50", {"not_prices": [{"foo": "bar"}]}, entity_id)
        contract = {
            "source_adapter": "generic", "direction": "buy",
            "today_entity": entity_id, "tomorrow_entity": "",
            "semantic_scope": "energy_only", "includes_distribution_variable": False,
            "price_basis": "gross", "unit": "PLN/kWh",
        }
        with self.assertRaisesRegex(ValueError, "unsupported_price_schema"):
            runtime.validate_and_bind_price_contract(contract, strict=True)

    def test_manager_builds_one_shared_pstryk_price_truth_without_double_osd(self):
        runtime = make_runtime()
        today = manager.ha_now()
        tomorrow = today + timedelta(days=1)
        runtime.data.update({
            const.CONF_BUY_PRICE_TODAY_SENSOR: const.DEFAULT_BUY_PRICE_TODAY_SENSOR,
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: const.DEFAULT_BUY_PRICE_TOMORROW_SENSOR,
            const.CONF_BUY_PRICE_CONTRACT: {
                "source_adapter": "pstryk",
                "today_entity": const.DEFAULT_BUY_PRICE_TODAY_SENSOR,
                "tomorrow_entity": const.DEFAULT_BUY_PRICE_TOMORROW_SENSOR,
            },
        })
        runtime.hass.states.values[const.DEFAULT_BUY_PRICE_TODAY_SENSOR] = FakeState(
            "0.23",
            {"today_prices": [
                {"start": today.replace(hour=hour).isoformat(),
                 "end": (today.replace(hour=hour) + timedelta(hours=1)).isoformat(),
                 "price": 0.23}
                for hour in range(24)
            ]},
            const.DEFAULT_BUY_PRICE_TODAY_SENSOR,
        )
        runtime.hass.states.values[const.DEFAULT_BUY_PRICE_TOMORROW_SENSOR] = FakeState(
            "unknown",
            {"tomorrow_prices": [
                {"start": tomorrow.replace(hour=hour).isoformat(),
                 "end": (tomorrow.replace(hour=hour) + timedelta(hours=1)).isoformat(),
                 "price": 0.24}
                for hour in range(24)
            ]},
            const.DEFAULT_BUY_PRICE_TOMORROW_SENSOR,
        )
        tariff_rows = [
            {"date": (today + timedelta(days=day)).date().isoformat(), "hour": hour,
             "available": True, "total_distribution_rate": 0.16}
            for day in (0, 1) for hour in range(24)
        ]
        canonical = runtime.canonical_price_context(today, tariff_rows)
        self.assertEqual(48, len(canonical["buy"]["rows"]))
        self.assertTrue(all(row["final_price_pln_kwh"] in (0.23, 0.24) for row in canonical["buy"]["rows"]))
        self.assertTrue(all(row["added_distribution"] == 0 for row in canonical["buy"]["rows"]))
        self.assertEqual(canonical, runtime._canonical_price_snapshot)

    def test_pstryk_to_rce_rebuilds_contract_without_stale_pstryk_semantics(self):
        runtime = make_runtime()
        now = manager.ha_now().replace(hour=0, minute=0, second=0, microsecond=0)
        pstryk_today, pstryk_tomorrow = "sensor.pstryk_buy", "sensor.pstryk_buy_tomorrow"
        rce_today, rce_tomorrow = "sensor.rce_pse_cena", "sensor.rce_pse_cena_jutro"
        runtime.data.update({
            const.CONF_BUY_PRICE_TODAY_SENSOR: pstryk_today,
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: pstryk_tomorrow,
            const.CONF_BUY_PRICE_CONTRACT: {
                "source_adapter": "pstryk", "today_entity": pstryk_today,
                "tomorrow_entity": pstryk_tomorrow,
            },
        })
        runtime.hass.states.values[pstryk_today] = FakeState("unknown", {"today_prices": [
            {"start": now.replace(hour=hour).isoformat(), "end": (now.replace(hour=hour) + timedelta(hours=1)).isoformat(), "price": 0.5}
            for hour in range(24)
        ]}, pstryk_today)
        runtime.hass.states.values[pstryk_tomorrow] = FakeState("unknown", {"tomorrow_prices": [
            {"start": (now + timedelta(days=1)).replace(hour=hour).isoformat(), "end": ((now + timedelta(days=1)).replace(hour=hour) + timedelta(hours=1)).isoformat(), "price": 0.6}
            for hour in range(24)
        ]}, pstryk_tomorrow)

        def rce_rows(day):
            return [
                {
                    "period": f"{(day + timedelta(minutes=index * 15)):%H:%M} - {('24:00' if index == 95 else (day + timedelta(minutes=(index + 1) * 15)).strftime('%H:%M'))}",
                    "dtime": (day + timedelta(minutes=(index + 1) * 15)).strftime("%Y-%m-%d %H:%M:%S"),
                    "business_date": day.date().isoformat(), "rce_pln": 0.7,
                }
                for index in range(96)
            ]

        runtime.hass.states.values[rce_today] = FakeState("unknown", {"prices": rce_rows(now)}, rce_today)
        runtime.hass.states.values[rce_tomorrow] = FakeState("unknown", {"prices": rce_rows(now + timedelta(days=1))}, rce_tomorrow)
        entries = {
            entity_id: types.SimpleNamespace(
                id=f"id-{index}", entity_id=entity_id, platform=platform,
                config_entry_id=platform, unique_id=f"u-{index}", device_id=None,
            )
            for index, (entity_id, platform) in enumerate((
                (pstryk_today, "pstryk"), (pstryk_tomorrow, "pstryk"),
                (rce_today, "rce_pse"), (rce_tomorrow, "rce_pse"),
            ))
        }
        registry = types.SimpleNamespace(entities=entries, async_get=lambda entity_id: entries.get(entity_id))
        entity_registry = sys.modules["homeassistant.helpers.entity_registry"]
        with mock.patch.object(entity_registry, "async_get", return_value=registry):
            initial = runtime.price_contract("buy")
            self.assertEqual(initial["source_adapter"], "pstryk")
            runtime.data[const.CONF_BUY_PRICE_TODAY_SENSOR] = rce_today
            runtime.data[const.CONF_BUY_PRICE_TOMORROW_SENSOR] = rce_tomorrow
            switched = runtime.price_contract("buy")
            canonical = runtime.canonical_price_context(now, [])
        self.assertEqual(switched["source_adapter"], "rce_pse")
        self.assertEqual(switched["resolved_adapter_today"], "rce_pse")
        self.assertEqual(switched["resolved_schema_today"]["schema_id"], "rce_interval_v1")
        self.assertFalse(switched["includes_distribution_variable"])
        self.assertEqual(switched["semantic_scope"], "energy_only")
        self.assertNotEqual(switched.get("today_list_attribute"), "today_prices")
        self.assertEqual(len(canonical["buy"]["rows"]), 48)
        self.assertTrue(all(row["source_adapter"] == "rce_pse" for row in canonical["buy"]["rows"]))

    def test_rce_to_pstryk_and_mixed_days_use_current_per_day_adapters(self):
        runtime = make_runtime()
        now = manager.ha_now().replace(hour=0, minute=0, second=0, microsecond=0)
        pstryk_today, pstryk_tomorrow = "sensor.pstryk_today", "sensor.pstryk_tomorrow"
        rce_today, rce_tomorrow = "sensor.rce_today", "sensor.rce_tomorrow"
        runtime.hass.states.values[pstryk_today] = FakeState("unknown", {"today_prices": [
            {"start": now.replace(hour=hour).isoformat(), "end": (now.replace(hour=hour) + timedelta(hours=1)).isoformat(), "price": 0.4}
            for hour in range(24)
        ]}, pstryk_today)
        runtime.hass.states.values[pstryk_tomorrow] = FakeState("unknown", {"tomorrow_prices": [
            {"start": (now + timedelta(days=1)).replace(hour=hour).isoformat(), "end": ((now + timedelta(days=1)).replace(hour=hour) + timedelta(hours=1)).isoformat(), "price": 0.45}
            for hour in range(24)
        ]}, pstryk_tomorrow)

        def rce_rows(day):
            return [{
                "period": f"{(day + timedelta(minutes=index * 15)):%H:%M} - {('24:00' if index == 95 else (day + timedelta(minutes=(index + 1) * 15)).strftime('%H:%M'))}",
                "dtime": (day + timedelta(minutes=(index + 1) * 15)).strftime("%Y-%m-%d %H:%M:%S"),
                "business_date": day.date().isoformat(), "rce_pln": 0.8,
            } for index in range(96)]

        runtime.hass.states.values[rce_today] = FakeState("unknown", {"prices": rce_rows(now)}, rce_today)
        runtime.hass.states.values[rce_tomorrow] = FakeState("unknown", {"prices": rce_rows(now + timedelta(days=1))}, rce_tomorrow)
        entries = {
            entity_id: types.SimpleNamespace(id=f"id-{index}", entity_id=entity_id, platform=platform, config_entry_id=platform, unique_id=f"u-{index}", device_id=None)
            for index, (entity_id, platform) in enumerate(((pstryk_today, "pstryk"), (pstryk_tomorrow, "pstryk"), (rce_today, "rce_pse"), (rce_tomorrow, "rce_pse")))
        }
        registry = types.SimpleNamespace(entities=entries, async_get=lambda entity_id: entries.get(entity_id))
        entity_registry = sys.modules["homeassistant.helpers.entity_registry"]
        runtime.data.update({
            const.CONF_BUY_PRICE_TODAY_SENSOR: rce_today,
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: rce_tomorrow,
            const.CONF_BUY_PRICE_CONTRACT: {"source_adapter": "rce_pse", "today_entity": rce_today, "tomorrow_entity": rce_tomorrow},
        })
        with mock.patch.object(entity_registry, "async_get", return_value=registry):
            self.assertEqual(runtime.price_contract("buy")["source_adapter"], "rce_pse")
            runtime.data[const.CONF_BUY_PRICE_TODAY_SENSOR] = pstryk_today
            runtime.data[const.CONF_BUY_PRICE_TOMORROW_SENSOR] = pstryk_tomorrow
            pstryk = runtime.price_contract("buy")
            self.assertEqual(pstryk["source_adapter"], "pstryk")
            self.assertEqual(pstryk["resolved_schema_today"]["schema_id"], "pstryk_aio_interval_v1")
            runtime.data[const.CONF_BUY_PRICE_TOMORROW_SENSOR] = rce_tomorrow
            mixed = runtime.price_contract("buy")
            canonical = runtime.canonical_price_context(now, [])
        self.assertEqual(mixed["adapter_summary"], "mixed")
        self.assertEqual(mixed["resolved_adapter_today"], "pstryk")
        self.assertEqual(mixed["resolved_adapter_tomorrow"], "rce_pse")
        self.assertEqual(len(canonical["buy"]["rows"]), 48)
        self.assertTrue(all(row["source_adapter"] == "pstryk" for row in canonical["buy"]["rows"] if row["day"] == "today"))
        self.assertTrue(all(row["source_adapter"] == "rce_pse" for row in canonical["buy"]["rows"] if row["day"] == "tomorrow"))

    def test_stale_persisted_buy_row_is_removed_without_touching_sell(self):
        runtime = make_runtime()
        runtime.data.update({
            const.CONF_BUY_PRICE_TODAY_SENSOR: "",
            const.CONF_BUY_PRICE_TOMORROW_SENSOR: "",
            const.CONF_BUY_PRICE_CONTRACT: {
                "source_adapter": "pstryk",
                "today_entity": "sensor.old_pstryk_buy",
                "tomorrow_entity": "sensor.old_pstryk_buy_tomorrow",
                "semantic_scope": "all_in_variable",
                "includes_distribution_variable": True,
            },
            const.CONF_PRICE_SOURCE: "pstryk",
        })
        sell_contract = runtime.price_contract("sell")
        sell_adapter = sell_contract.get("resolved_adapter_today") or sell_contract.get("source_adapter")
        sell_semantic = manager.effective_contract_for_day(sell_contract, 0).get("semantic_scope")
        stale_buy_row = {
            "day": "tomorrow", "hour": 23, "quality": "ready",
            "source_adapter": "pstryk", "source_semantic_scope": "all_in_variable",
            "final_price_pln_kwh": 1.16,
        }
        valid_sell_row = {
            "day": "today", "hour": 12, "quality": "ready",
            "source_adapter": sell_adapter, "source_semantic_scope": sell_semantic,
            "final_price_pln_kwh": 0.8,
        }
        runtime.optimizer_plan = {
            "canonical_prices": {
                "schema_version": 1,
                "buy": {
                    "contract": dict(runtime.data[const.CONF_BUY_PRICE_CONTRACT]),
                    "rows": [stale_buy_row],
                    "diagnostics": {"coverage_today": 0, "coverage_tomorrow": 1},
                },
                "sell": {
                    "contract": sell_contract,
                    "rows": [valid_sell_row],
                    "diagnostics": {"coverage_today": 1, "coverage_tomorrow": 0},
                },
            }
        }

        self.assertTrue(runtime._sanitize_cached_price_plans())
        canonical = runtime.optimizer_plan["canonical_prices"]
        self.assertEqual(canonical["buy"]["rows"], [])
        self.assertEqual(canonical["buy"]["diagnostics"]["coverage_tomorrow"], 0)
        self.assertEqual(canonical["buy"]["diagnostics"]["resolver"]["tomorrow"]["mapped_entity"], "")
        self.assertEqual(canonical["buy"]["contract"]["adapter_summary"], "unmapped")
        self.assertNotIn("semantic_scope", canonical["buy"]["contract"])
        self.assertEqual(canonical["sell"]["rows"], [valid_sell_row])


if __name__ == "__main__":
    unittest.main()

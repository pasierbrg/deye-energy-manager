from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest


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

    core.HomeAssistant = object
    core.callback = lambda function: function
    event.async_track_time_interval = lambda *_args, **_kwargs: lambda: None
    event.async_track_point_in_time = lambda *_args, **_kwargs: lambda: None
    event.async_track_state_change_event = lambda *_args, **_kwargs: lambda: None

    class Store:
        def __init__(self, *_args, **_kwargs):
            pass

    storage.Store = Store
    dt.now = lambda: datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)

    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
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


_install_home_assistant_stubs()
package = types.ModuleType("custom_components.deye_energy_manager")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package
const = _load_module(f"{package.__name__}.const", PACKAGE / "const.py")
manager = _load_module(f"{package.__name__}.manager", PACKAGE / "manager.py")
manager.ha_now = lambda: datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


class FakeState:
    def __init__(self, state, attributes=None, entity_id=""):
        self.entity_id = entity_id
        self.state = str(state)
        self.attributes = attributes or {}


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
    states["switch.deye_inverter_time_of_use"] = FakeState("off")
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
        },
    )
    runtime.default_work_mode = default_mode or const.MODE_ZERO_EXPORT
    runtime.default_sell_power = 13000
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
    const.DEFAULT_MAX_SELL_POWER: 13000,
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
    def test_default_control_confirmation_window_is_12_seconds(self):
        self.assertEqual(make_runtime().control_confirmation_timeout, 12.0)

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
        active.mode = const.MODE_ZERO_EXPORT
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
        self.assertEqual(runtime.default_sell_power, 13000)
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
        self.assert_safe_defaults(runtime, const.MODE_SELLING_FIRST)

    def test_safe_defaults_preserve_zero_export_to_ct(self):
        runtime = make_runtime(default_mode=const.MODE_ZERO_EXPORT_CT)
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
        runtime = make_runtime(default_mode=const.MODE_ZERO_EXPORT_CT)
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
        self.assertEqual(runtime.manager_status, "SELL BLOCKED")
        self.assertIn("SOC", runtime.decision_reason)
        self.assertEqual(runtime.last_schedule_attempt["status"], "applied")
        self.assertEqual(runtime.last_error, "")
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state,
            runtime.default_work_mode,
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

    def test_low_slot_price_blocks_sale_without_schedule_error(self):
        runtime = make_runtime(price="0.15")
        active = configure_selling_slot(runtime)
        active.min_sell_price = 0.20

        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SELL BLOCKED")
        self.assertIn("cena", runtime.decision_reason)
        self.assertEqual(runtime.last_schedule_attempt["status"], "applied")
        self.assertEqual(runtime.last_error, "")
        self.assertEqual(
            runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state,
            runtime.default_work_mode,
        )

    def test_direct_selling_is_blocked_without_soc(self):
        runtime = make_runtime(soc=None)
        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 0))
        self.assert_safe_defaults(runtime)

    def test_apply_settings_uses_custom_grid_charge_current(self):
        runtime = make_runtime()
        runtime.default_grid_charge_current = 30
        asyncio.run(runtime.async_apply_settings(const.MODE_ZERO_EXPORT, 0, 120, 120, 60))
        grid_calls = [call for call in runtime.hass.services.calls if call[:2] == ("number", "set_value") and call[2].get("entity_id") == const.DEFAULT_GRID_CHARGE_CURRENT]
        self.assertTrue(grid_calls)
        self.assertEqual(grid_calls[-1][2]["value"], 60)

    def test_apply_settings_uses_default_grid_charge_current_when_omitted(self):
        runtime = make_runtime()
        runtime.default_grid_charge_current = 45
        asyncio.run(runtime.async_apply_settings(const.MODE_ZERO_EXPORT, 0, 120, 120))
        grid_calls = [call for call in runtime.hass.services.calls if call[:2] == ("number", "set_value") and call[2].get("entity_id") == const.DEFAULT_GRID_CHARGE_CURRENT]
        self.assertTrue(grid_calls)
        self.assertEqual(grid_calls[-1][2]["value"], 45)

    def test_more_than_six_segments_is_rejected(self):
        runtime = make_runtime()
        for index, slot in enumerate(runtime.slots.values()):
            slot.enabled = True
            slot.tou_soc = 10 if index % 2 else 20
        self.assertTrue(runtime.mapping_error)
        self.assertGreater(len(runtime._compress_schedule_segments()), 6)
        calls_before = list(runtime.hass.services.calls)
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.services.calls, calls_before)
        self.assertIn("maksymalnie 6", runtime.last_error)

    def test_invalid_patch_rolls_back_and_keeps_safe_mode(self):
        runtime = make_runtime()
        updates = []
        for index, slot_key in enumerate(list(runtime.slots)[:8]):
            updates.append({"slot_key": slot_key, "enabled": True, "tou_soc": 10 if index % 2 else 20})
        calls_before = list(runtime.hass.services.calls)
        with self.assertRaises(ValueError):
            asyncio.run(runtime.async_apply_schedule_patch(updates))
        self.assertTrue(all(not slot.enabled for slot in runtime.slots.values()))
        self.assertEqual(runtime.hass.services.calls, calls_before)

    def test_tou_write_error_restores_defaults(self):
        runtime = make_runtime(default_mode=const.MODE_ZERO_EXPORT_CT)
        configure_selling_slot(runtime)
        runtime.hass.services.fail_once("time", "set_value")
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assert_safe_defaults(runtime, const.MODE_ZERO_EXPORT_CT)
        self.assertIn("ustawienia domyślne", runtime.last_error)

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
            option=const.MODE_SELLING_FIRST,
        )
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assert_safe_defaults(runtime)

    def test_failed_schedule_patch_rolls_back_and_restores_defaults(self):
        runtime = make_runtime()
        slot_key = runtime.active_slot_key()
        runtime.hass.services.fail_once(
            "number",
            "set_value",
            entity_id=const.DEFAULT_MAX_SELL_POWER,
        )
        with self.assertRaises(RuntimeError):
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
        self.assertFalse(runtime.slots[slot_key].enabled)
        self.assert_safe_defaults(runtime)

    def test_selling_update_writes_numbers_before_target_mode(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(select_calls[-1][2]["option"], const.MODE_SELLING_FIRST)
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
        self.assertEqual(ordered_control_calls[-1][2]["option"], const.MODE_SELLING_FIRST)
        self.assertTrue(all(call[:2] == ("number", "set_value") for call in ordered_control_calls[:-1]))

    def test_delayed_work_mode_waits_without_rewriting_and_confirms(self):
        runtime = make_runtime()
        configure_selling_slot(runtime)
        runtime.hass.services.ignore_once(
            "select", "select_option", entity_id=const.DEFAULT_WORK_MODE_SELECT,
            option=const.MODE_SELLING_FIRST,
        )
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(len(select_calls), 1)
        self.assertEqual(runtime.last_schedule_attempt["status"], "pending")
        self.assertEqual(runtime.manager_status, "SELLING ACTIVE")
        # Deye may publish the selected mode later.  A fast confirmation
        # recheck must only read the first transaction, never write it again.
        runtime.hass.states.values[const.DEFAULT_WORK_MODE_SELECT] = FakeState(
            const.MODE_SELLING_FIRST,
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
        runtime.hass.services.ignore_once("select", "select_option", entity_id=const.DEFAULT_WORK_MODE_SELECT, option=const.MODE_SELLING_FIRST)
        self.assertFalse(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.manager_status, "SCHEDULE APPLY ERROR")
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
        self.assertFalse(hasattr(runtime, "charge_scheduler_enabled"))
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state, const.MODE_SELLING_FIRST)

    def test_direct_settings_do_not_use_transitional_zeroes(self):
        runtime = make_runtime()
        asyncio.run(runtime.async_apply_settings(const.MODE_SELLING_FIRST, 5000, 120, 120))
        self.assertFalse(any(call[2]["value"] == 0 for call in control_number_calls(runtime)))
        select_calls = [call for call in runtime.hass.services.calls if call[:2] == ("select", "select_option")]
        self.assertEqual(len(select_calls), 1)
        self.assertEqual(select_calls[-1][2]["option"], const.MODE_SELLING_FIRST)

    def test_restore_defaults_uses_exact_mode_after_all_numeric_values(self):
        for mode in (
            const.MODE_ZERO_EXPORT,
            const.MODE_ZERO_EXPORT_CT,
            const.MODE_SELLING_FIRST,
        ):
            with self.subTest(mode=mode):
                runtime = make_runtime(default_mode=mode)
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
                self.assertEqual(ordered_control_calls[-1][2]["option"], mode)
                self.assertFalse(runtime.scheduler_enabled)
                self.assertEqual(runtime.last_error, "")

    def test_restore_defaults_raises_when_full_set_is_not_confirmed(self):
        runtime = make_runtime(default_mode=const.MODE_ZERO_EXPORT_CT)
        runtime.hass.services.fail_once(
            "number",
            "set_value",
            entity_id=const.DEFAULT_CHARGE_CURRENT,
        )

        with self.assertRaisesRegex(RuntimeError, "KRYTYCZNY"):
            asyncio.run(runtime.async_restore_defaults())

        self.assertIn("Maximum Battery Charge Current", runtime.last_error)
        self.assertNotEqual(runtime.last_error, "")


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
        slot.mode = const.MODE_ZERO_EXPORT_CT
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
        slot.mode = const.MODE_ZERO_EXPORT
        slot.charge_current = 120
        self.assertTrue(asyncio.run(runtime.async_apply_targets()))
        self.assertEqual(runtime.hass.states.get(const.DEFAULT_WORK_MODE_SELECT).state, const.MODE_ZERO_EXPORT)

    def test_sell_soc_and_charge_target_soc_are_independent(self):
        runtime = make_runtime()
        slot = self.configure_charge_slot(runtime, grid=False)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 85
        runtime.charge_profile_target_soc = 70
        segments = runtime._compress_schedule_segments()
        self.assertIn(85, [segment["tou_soc"] for segment in segments])
        self.assertEqual(slot.minimum_sell_soc, 20)

    def test_charge_slot_keeps_default_ct_topology_and_uses_slot_values(self):
        runtime = make_runtime(default_mode=const.MODE_ZERO_EXPORT_CT)
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
            const.MODE_ZERO_EXPORT,
            const.MODE_ZERO_EXPORT_CT,
        )
        protected = []
        for slot, mode in zip(runtime.slots.values(), modes):
            slot.enabled = True
            slot.mode = mode
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
        slot.mode = const.MODE_ZERO_EXPORT

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

        segments = runtime._compress_schedule_segments()
        self.assertEqual(segments[0]["mode"], const.MODE_CHARGE)
        self.assertTrue(segments[0]["grid_charge"])
        self.assertEqual(segments[0]["charge_current"], 5)
        self.assertEqual(segments[0]["discharge_current"], 6)
        self.assertEqual(segments[0]["grid_charge_current"], 7)
        self.assertEqual(segments[0]["tou_soc"], 8)
        self.assertEqual(segments[1]["mode"], const.MODE_CHARGE)
        self.assertFalse(segments[1]["grid_charge"])
        self.assertEqual(segments[1]["charge_current"], 6)
        self.assertEqual(segments[1]["discharge_current"], 7)
        self.assertEqual(segments[1]["tou_soc"], 9)

    def test_grid_charge_yes_is_limited_to_charge_ranges(self):
        runtime = make_runtime()
        runtime.charge_profile_target_soc = 80
        runtime.charge_profile_grid_enabled = True
        charge_slot = list(runtime.slots.values())[5]
        charge_slot.enabled = True
        charge_slot.mode = const.MODE_CHARGE
        charge_slot.charge_enabled = True
        charge_slot.grid_charge_current = 40
        charge_slot.tou_soc = 80

        segments = runtime._compress_schedule_segments()
        self.assertTrue(any(segment["grid_charge"] for segment in segments))
        self.assertTrue(all(
            not segment["grid_charge"] or segment["mode"] == const.MODE_CHARGE
            for segment in segments
        ))

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

    def test_target_mode_never_returns_logical_normal_label(self):
        runtime = make_runtime()
        self.configure_normal_profile(runtime)
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = const.MODE_ZERO_EXPORT_CT

        self.assertEqual(runtime.target_mode, const.MODE_ZERO_EXPORT_CT)
        self.assertNotEqual(runtime.target_mode, const.MODE_NORMAL_OPERATION)

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


class TouSocMappingTests(unittest.TestCase):
    """Regression coverage for logical SOC versus physical Deye TOU SOC."""

    @staticmethod
    def _active_physical_segment(runtime):
        hour = manager.ha_now().hour
        for idx, segment in enumerate(runtime._compress_schedule_segments(), start=1):
            start = int(segment["start"])
            end = 24 if int(segment["end"]) == 0 else int(segment["end"])
            if start <= hour < end:
                return idx, segment
        raise AssertionError("Nie znaleziono fizycznego zakresu dla aktywnej godziny")

    def _map_active_slot(self, runtime, expected_soc, expected_grid):
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))
        index, segment = self._active_physical_segment(runtime)
        self.assertEqual(segment["tou_soc"], expected_soc)
        self.assertEqual(segment["grid_charge"], expected_grid)
        self.assertEqual(
            runtime.hass.states.get(f"number.deye_inverter_time_of_use_{index}_soc").state,
            str(float(expected_soc)),
        )
        self.assertEqual(
            runtime.hass.states.get(f"switch.deye_inverter_time_of_use_{index}_grid_charge").state,
            "on" if expected_grid else "off",
        )

    def test_selling_first_maps_slot_tou_soc_not_minimum_sell_soc(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 10
        self._map_active_slot(runtime, 10, False)

    def test_zero_export_load_maps_its_own_tou_soc(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_ZERO_EXPORT
        slot.minimum_sell_soc = 30
        slot.tou_soc = 12
        self._map_active_slot(runtime, 12, False)

    def test_zero_export_ct_maps_its_own_tou_soc(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_ZERO_EXPORT_CT
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

    def test_diagnostics_keep_sale_guard_and_physical_tou_soc_separate(self):
        runtime = make_runtime()
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 20
        slot.tou_soc = 10
        self.assertTrue(asyncio.run(runtime.async_apply_time_of_use_map()))

        diagnostics = runtime.diagnostics()
        active = diagnostics["active_slot_control"]
        self.assertEqual(active["minimum_sell_soc"], 20)
        self.assertEqual(active["tou_soc"], 10)
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
        before = runtime._compress_schedule_segments()
        slot.minimum_sell_soc = 90
        after = runtime._compress_schedule_segments()
        self.assertEqual(before, after)

    def test_nonphysical_slot_parameters_do_not_create_tou_boundary(self):
        runtime = make_runtime()
        slot = runtime.slots[runtime.active_slot_key()]
        slot.enabled = True
        slot.mode = const.MODE_ZERO_EXPORT
        slot.tou_soc = 20
        before = runtime._compress_schedule_segments()
        slot.mode = const.MODE_ZERO_EXPORT_CT
        slot.sell_power = 5000
        slot.charge_current = 120
        slot.discharge_current = 30
        slot.grid_charge_current = 60
        slot.minimum_sell_soc = 90
        after = runtime._compress_schedule_segments()
        self.assertEqual(before, after)

    def test_changing_tou_soc_creates_a_physical_boundary(self):
        runtime = make_runtime()
        before = runtime._compress_schedule_segments()
        self.assertEqual({segment["tou_soc"] for segment in before}, {20.0})

        changed = list(runtime.slots.values())[8]
        changed.tou_soc = 33
        after = runtime._compress_schedule_segments()

        self.assertEqual({segment["tou_soc"] for segment in after}, {20.0, 33.0})
        self.assertTrue(any(
            segment["start"] == 8 and segment["end"] == 9 and segment["tou_soc"] == 33
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
        self.assertEqual(normalized["tou_soc"], 37)
        self.assertNotEqual(normalized["tou_soc"], normalized["minimum_sell_soc"])
        self.assertNotEqual(normalized["tou_soc"], 0)


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
    class MemoryStore:
        def __init__(self):
            self.value = None

        async def async_save(self, value):
            self.value = value

        async def async_load(self):
            return self.value

    def test_future_plan_is_stored_exactly_and_not_applied_early(self):
        runtime = make_runtime()
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
        self.assertEqual([update], runtime.future_plan["updates"])
        self.assertEqual("approved", runtime.plan_execution_archive[0]["approval_status"])
        before = list(runtime.hass.services.calls)
        asyncio.run(runtime.async_process_future_plan())
        self.assertEqual(before, runtime.hass.services.calls)
        self.assertEqual("scheduled", runtime.future_plan["status"])

    def test_future_plan_rejects_wrong_date(self):
        runtime = make_runtime()
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
                "updates": [{"slot_key": "05_06", "mode": const.MODE_SELLING_FIRST}],
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
        runtime = make_runtime(price=None, default_mode=const.MODE_ZERO_EXPORT_CT)
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
        self.assertEqual("partial", runtime.future_plan["status"])
        self.assertEqual("blocked", runtime.future_plan["slot_results"]["05_06"]["status"])
        self.assertEqual("blocked", runtime.profile_execution[0]["status"])
        self.assertEqual("morning_sale", runtime.profile_execution[0]["profile_id"])
        self.assertEqual([], control_number_calls(runtime))

    def test_failed_future_plan_write_records_failed_profile_execution(self):
        runtime = make_runtime(price=1.2)
        runtime._ai_store = self.MemoryStore()

        async def fail_write(_updates):
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
        manager.ha_now = lambda: datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
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
        applied = []

        async def apply_patch(updates):
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
        manager.ha_now = lambda: datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
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
        applied = []

        async def apply_patch(updates):
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
        manager.ha_now = lambda: datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual(500, applied[0][0]["sell_power"])

    def test_future_plan_revalidates_and_applies_only_current_slot(self):
        runtime = make_runtime(price=1.2)
        runtime._ai_store = self.MemoryStore()
        applied = []

        async def apply_patch(updates):
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
        manager.ha_now = lambda: datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)
        try:
            asyncio.run(runtime.async_process_future_plan())
        finally:
            manager.ha_now = previous_now
        self.assertEqual([[runtime.future_plan["updates"][0]]], applied)
        self.assertEqual("scheduled", runtime.future_plan["status"])
        self.assertEqual("completed", runtime.future_plan["slot_results"]["05_06"]["status"])


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
        self.assertEqual(summary["solcast_correction_factor"], 1.15)
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

    async def test_saving_profiles_invalidates_plan_without_daye_calls(self):
        runtime = make_runtime()
        saved = []
        async def save():
            saved.append(True)
        runtime.async_save_ai_data = save
        profiles = self.valid_profiles()
        profiles["profiles"]["morning_sale"]["enabled"] = True
        runtime._optimizer_input_snapshot_id = "old"
        await runtime.async_set_user_profiles(profiles)
        self.assertEqual("", runtime._optimizer_input_snapshot_id)
        self.assertEqual("user_profiles_changed", runtime._optimizer_generation_reason)
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


if __name__ == "__main__":
    unittest.main()

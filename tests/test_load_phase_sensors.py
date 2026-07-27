from __future__ import annotations

import unittest

from tests.test_manager_logic import (
    const,
    FakeHass,
    FakeState,
    make_runtime,
    manager,
)


def runtime_with_load_states(load_states: dict[str, FakeState]):
    """Return a runtime whose load_l1/l2/l3 source sensors have the given states."""
    runtime = make_runtime()
    merged = dict(runtime.hass.states.values)
    merged.update(load_states)
    runtime.hass = FakeHass(merged)
    return runtime


class LoadPhaseSensorTests(unittest.TestCase):
    def test_only_l1_available(self):
        states = {const.DEFAULT_LOAD_L1_POWER_SENSOR: FakeState("1500")}
        runtime = runtime_with_load_states(states)
        self.assertEqual(runtime.state_float_or_none(runtime.load_l1_power_sensor), 1500)
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l2_power_sensor))
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l3_power_sensor))

    def test_l1_and_l2_available(self):
        states = {
            const.DEFAULT_LOAD_L1_POWER_SENSOR: FakeState("1500"),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: FakeState("2300"),
        }
        runtime = runtime_with_load_states(states)
        self.assertEqual(runtime.state_float_or_none(runtime.load_l1_power_sensor), 1500)
        self.assertEqual(runtime.state_float_or_none(runtime.load_l2_power_sensor), 2300)
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l3_power_sensor))

    def test_all_l1_l2_l3_available(self):
        states = {
            const.DEFAULT_LOAD_L1_POWER_SENSOR: FakeState("1500"),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: FakeState("2300"),
            const.DEFAULT_LOAD_L3_POWER_SENSOR: FakeState("1800"),
        }
        runtime = runtime_with_load_states(states)
        self.assertEqual(runtime.state_float_or_none(runtime.load_l1_power_sensor), 1500)
        self.assertEqual(runtime.state_float_or_none(runtime.load_l2_power_sensor), 2300)
        self.assertEqual(runtime.state_float_or_none(runtime.load_l3_power_sensor), 1800)

    def test_no_load_phases_available(self):
        runtime = runtime_with_load_states({})
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l1_power_sensor))
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l2_power_sensor))
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l3_power_sensor))

    def test_unavailable_source_is_treated_as_missing(self):
        states = {
            const.DEFAULT_LOAD_L1_POWER_SENSOR: FakeState("unavailable"),
            const.DEFAULT_LOAD_L2_POWER_SENSOR: FakeState("unknown"),
            const.DEFAULT_LOAD_L3_POWER_SENSOR: FakeState(""),
        }
        runtime = runtime_with_load_states(states)
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l1_power_sensor))
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l2_power_sensor))
        self.assertIsNone(runtime.state_float_or_none(runtime.load_l3_power_sensor))

    def test_missing_phase_does_not_invent_zero(self):
        """A missing phase must not render as 0 W; the card should display the dash."""
        runtime = runtime_with_load_states({})
        self.assertIsNone(
            manager.DeyeEnergyManagerRuntime.state_float_or_none(
                runtime, runtime.load_l2_power_sensor
            )
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components" / "deye_energy_manager" / "battery_model.py"
SPEC = importlib.util.spec_from_file_location("deye_battery_model_test", MODULE)
battery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = battery
assert SPEC.loader is not None
SPEC.loader.exec_module(battery)


class BatteryConfigurationTests(unittest.TestCase):
    def test_additional_reserve_preserves_076_effective_minimum(self):
        result = battery.effective_minimum(
            hard_min_soc_pct=20,
            reserve_kwh=4,
            capacity_kwh=30,
            reserve_mode="additional",
        )
        self.assertAlmostEqual(result["effective_min_soc_pct"], 33.333, places=3)
        self.assertEqual(result["reserve_label"], "Dodatkowa rezerwa ponad minimalny SOC")

    def test_legacy_efficiency_split_preserves_round_trip(self):
        result = battery.migrate_efficiencies(0.9)
        self.assertAlmostEqual(
            result["charge_efficiency"] * result["discharge_efficiency"],
            0.9,
            places=5,
        )

    def test_effective_power_is_smallest_physical_limit(self):
        result = battery.effective_power_limit(
            plan_limit_w=5000,
            export_limit_w=6000,
            inverter_limit_w=8000,
            current_limit_a=80,
            battery_voltage_v=52,
            entity_limit_w=13000,
        )
        self.assertEqual(result["effective_limit_w"], 4160)
        self.assertEqual(result["limit_reason"], "current_voltage")


class HourlySocTests(unittest.TestCase):
    def test_night_load_reduces_soc_above_minimum(self):
        row = battery.simulate_hour(
            soc_start_pct=80,
            capacity_kwh=10,
            effective_min_soc_pct=20,
            target_max_soc_pct=100,
            pv_kwh=0,
            home_load_kwh=1,
            charge_efficiency=0.95,
            discharge_efficiency=0.9,
            power_limit_w=5000,
        )
        self.assertLess(row["soc_end_pct"], 80)
        self.assertEqual(row["grid_to_home_kwh"], 0)
        self.assertEqual(row["battery_to_home_kwh"], 1)

    def test_minimum_soc_moves_remaining_load_to_grid(self):
        row = battery.simulate_hour(
            soc_start_pct=25,
            capacity_kwh=10,
            effective_min_soc_pct=20,
            target_max_soc_pct=100,
            pv_kwh=0,
            home_load_kwh=2,
            charge_efficiency=0.95,
            discharge_efficiency=0.9,
            power_limit_w=5000,
        )
        self.assertEqual(row["soc_end_pct"], 20)
        self.assertGreater(row["grid_to_home_kwh"], 1)
        self.assertIn("SOC", row["limit_reason"])

    def test_grid_charge_increases_soc(self):
        row = battery.simulate_hour(
            soc_start_pct=20,
            capacity_kwh=10,
            effective_min_soc_pct=20,
            target_max_soc_pct=90,
            pv_kwh=0,
            home_load_kwh=0,
            charge_efficiency=0.9,
            discharge_efficiency=0.9,
            grid_charge_request_kwh=2,
            power_limit_w=5000,
        )
        self.assertEqual(row["grid_to_battery_kwh"], 2)
        self.assertEqual(row["soc_end_pct"], 38)

    def test_sale_then_later_home_load_is_sequential(self):
        rows = battery.simulate_horizon(
            initial_soc_pct=90,
            hours=[
                {"battery_sale_request_kwh": 2, "home_load_kwh": 0, "pv_kwh": 0},
                {"home_load_kwh": 1, "pv_kwh": 0},
            ],
            capacity_kwh=10,
            effective_min_soc_pct=20,
            target_max_soc_pct=100,
            charge_efficiency=0.9,
            discharge_efficiency=0.9,
            default_power_limit_w=5000,
        )
        self.assertEqual(rows[1]["soc_start_pct"], rows[0]["soc_end_pct"])
        self.assertLess(rows[1]["soc_end_pct"], rows[0]["soc_end_pct"])

    def test_current_hour_uses_remaining_time(self):
        for minute, expected in ((1, 59), (30, 30), (55, 5)):
            with self.subTest(minute=minute):
                moment = datetime(2026, 7, 29, 12, minute, tzinfo=timezone.utc)
                duration = battery.remaining_minutes_in_hour(moment)
                self.assertEqual(duration, expected)
                row = battery.simulate_hour(
                    soc_start_pct=90,
                    capacity_kwh=20,
                    effective_min_soc_pct=20,
                    target_max_soc_pct=100,
                    pv_kwh=0,
                    home_load_kwh=0,
                    charge_efficiency=1,
                    discharge_efficiency=1,
                    battery_sale_request_kwh=10,
                    duration_minutes=duration,
                    power_limit_w=5000,
                )
                self.assertLessEqual(row["battery_to_grid_kwh"], 5 * duration / 60 + 1e-5)
                if duration < 60:
                    self.assertIn("czas", row["limit_reason"])

    def test_energy_change_matches_flows_and_losses(self):
        row = battery.simulate_hour(
            soc_start_pct=70,
            capacity_kwh=10,
            effective_min_soc_pct=20,
            target_max_soc_pct=100,
            pv_kwh=0.5,
            home_load_kwh=1.5,
            charge_efficiency=0.95,
            discharge_efficiency=0.9,
            power_limit_w=5000,
        )
        removed = row["battery_energy_start_kwh"] - row["battery_energy_end_kwh"]
        self.assertAlmostEqual(removed, row["battery_to_home_kwh"] / 0.9, places=4)


class HorizonAndTimelineTests(unittest.TestCase):
    @staticmethod
    def _hours(count):
        return [{"pv_kwh": 0, "home_load_kwh": 0.4} for _ in range(count)]

    def test_48h_horizon_does_not_reset_at_midnight(self):
        rows = battery.simulate_horizon(
            initial_soc_pct=80,
            hours=self._hours(48),
            capacity_kwh=30,
            effective_min_soc_pct=20,
            target_max_soc_pct=100,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
            default_power_limit_w=5000,
        )
        self.assertEqual(len(rows), 48)
        self.assertEqual(rows[24]["soc_start_pct"], rows[23]["soc_end_pct"])
        self.assertLess(rows[24]["soc_end_pct"], rows[23]["soc_end_pct"])

    def test_missing_current_soc_is_fail_closed_without_false_line(self):
        rows = battery.simulate_horizon(
            initial_soc_pct=None,
            hours=self._hours(4),
            capacity_kwh=10,
            effective_min_soc_pct=20,
            target_max_soc_pct=100,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
            default_power_limit_w=5000,
        )
        self.assertTrue(all(row["soc_end_pct"] is None for row in rows))
        self.assertTrue(all(row["source"] == "missing" for row in rows))

    def test_historical_points_are_immutable_and_missing_hour_stays_gap(self):
        now = datetime(2026, 7, 29, 12, 30, tzinfo=timezone.utc)
        history = [
            {
                "hour": (now.replace(hour=hour, minute=0) - timedelta(0)).isoformat(),
                "soc_end": 80 - hour,
            }
            for hour in range(12)
            if hour != 5
        ]
        first = battery.build_soc_timeline(
            now=now,
            historical_hours=history,
            current_soc_pct=60,
            forecast_hours=[],
        )
        second = battery.build_soc_timeline(
            now=now,
            historical_hours=history,
            current_soc_pct=40,
            forecast_hours=[],
        )
        self.assertEqual(first[0]["soc_pct"], second[0]["soc_pct"])
        self.assertEqual(first[5]["source"], "missing")
        self.assertIsNone(first[5]["soc_pct"])
        self.assertEqual(first[12]["source"], "actual")
        self.assertEqual(first[12]["boundary"], "now")
        self.assertNotEqual(first[12]["soc_pct"], second[12]["soc_pct"])


if __name__ == "__main__":
    unittest.main()

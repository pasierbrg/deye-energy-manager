from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / "custom_components" / "deye_energy_manager" / filename,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


telemetry = load("telemetry_0794_tests", "telemetry.py")
learning = load("learning_0794_tests", "learning.py")
optimizer = load("optimizer_0794_tests", "optimizer_core.py")


class TelemetryPipeline0794Tests(unittest.TestCase):
    def test_missing_sample_is_not_counted_as_zero_or_covered(self):
        channel = telemetry.new_channel()
        channel = telemetry.record_channel(
            channel,
            value=None,
            elapsed_seconds=60,
            quality="unavailable",
            status="unavailable",
        )
        summary = telemetry.channel_summary(channel)
        self.assertEqual(0, summary["valid_samples"])
        self.assertEqual(0, summary["covered_seconds"])
        self.assertEqual("missing", summary["level"])
        self.assertFalse(summary["usable_for_learning"])

    def test_channel_coverage_levels_are_independent(self):
        channel = telemetry.new_channel()
        for _ in range(54):
            channel = telemetry.record_channel(
                channel,
                value=100,
                elapsed_seconds=60,
                quality="good",
            )
        self.assertEqual("full", telemetry.channel_summary(channel)["level"])
        partial = telemetry.new_channel()
        for _ in range(36):
            partial = telemetry.record_channel(
                partial,
                value=100,
                elapsed_seconds=60,
                quality="good",
            )
        self.assertEqual("partial", telemetry.channel_summary(partial)["level"])

    def test_energy_balance_reports_inconsistency_without_guessing(self):
        missing = telemetry.energy_balance(
            pv_kwh=None,
            load_kwh=1,
            grid_import_kwh=0,
            grid_export_kwh=0,
            battery_charge_kwh=0,
            battery_discharge_kwh=0,
        )
        self.assertEqual("insufficient_data", missing["status"])
        valid = telemetry.energy_balance(
            pv_kwh=3,
            load_kwh=2,
            grid_import_kwh=0,
            grid_export_kwh=1,
            battery_charge_kwh=0,
            battery_discharge_kwh=0,
        )
        self.assertEqual("ok", valid["status"])

    def test_signed_channels_are_split_without_inventing_missing_zeroes(self):
        result = telemetry.split_directional_power(
            grid_power_w=-2300,
            battery_power_w=1800,
        )
        self.assertEqual(0, result["grid_import_power"])
        self.assertEqual(2300, result["grid_export_power"])
        self.assertEqual(0, result["battery_charge_power"])
        self.assertEqual(1800, result["battery_discharge_power"])
        missing = telemetry.split_directional_power(
            grid_power_w=None,
            battery_power_w=None,
        )
        self.assertTrue(all(value is None for value in missing.values()))

    def test_partial_load_hour_updates_profile_with_lower_weight(self):
        result = learning.update_load_profile(
            {},
            moment=datetime(2026, 7, 30, 10),
            load_kwh=0.3,
            complete=False,
            quality_score=100,
            completeness_percent=50,
        )
        cell = result["cells"]["3-10"]
        self.assertEqual(1, cell["samples"])
        self.assertEqual(1, cell["partial_samples"])
        self.assertAlmostEqual(0.5, cell["weighted_samples"])
        self.assertAlmostEqual(0.6, cell["mean_kwh"])

    def test_core_uses_historical_soc_for_past_and_measured_soc_for_now(self):
        inputs = {
            "date": "2026-07-30",
            "generated_at": "2026-07-30T10:30:00+02:00",
            "current_hour": 10,
            "current_hour_remaining_minutes": 30,
            "soc": 42,
            "battery_capacity_kwh": 10,
            "battery_efficiency": 0.9,
            "min_soc": 20,
            "effective_min_soc": 20,
            "target_soc": 100,
            "effective_power_limit_w": 5000,
            "max_sell_power_w": 5000,
            "sell_prices": [{hour: 0.5 for hour in range(24)}] * 2,
            "buy_prices": [{hour: 1.0 for hour in range(24)}] * 2,
            "distribution": [0] * 48,
            "price_includes_distribution": True,
            "pv_forecast": [0, 0],
            "pv_forecast_full": [0, 0],
            "pv_forecast_available": [True, True],
            "pv_profile": [0] * 24,
            "load_profile_48h": [1] * 48,
            "recorded_days": 1,
            "data_quality": {"score": 100, "sources": {}},
            "historical_hours": [{
                "local_date": "2026-07-30",
                "local_hour": 5,
                "soc_start": 31,
                "soc_end": 29,
                "load_kwh": 0.4,
                "pv_kwh": 0,
                "grid_import_kwh": 0.4,
                "grid_export_kwh": 0,
                "battery_charge_kwh": 0,
                "battery_discharge_kwh": 0,
            }],
            "live_state": {"home_power_w": 600, "pv_power_w": 0},
            "current_hour_partial": {"elapsed_minutes": 30, "soc_current_pct": 42},
            "baseline_schedule": [{} for _ in range(48)],
            "user_profiles": {"profiles": {}},
        }
        plan = optimizer.build_energy_plan(inputs)
        past = next(row for row in plan["rows"] if row["hour"] == 5)
        current = next(row for row in plan["rows"] if row["hour"] == 10)
        self.assertEqual("historical", past["soc_source"])
        self.assertEqual(29, past["soc_after"])
        self.assertEqual("measured", current["soc_source"])
        self.assertEqual(42, current["soc_start_pct"])
        self.assertLess(current["load_kwh"], 1.0)

    def test_usable_partial_hours_advance_learning_confidence(self):
        base = {
            "recorded_days": 0,
            "sell_prices": [{hour: 0.5 for hour in range(24)}] * 2,
            "buy_prices": [{hour: 1.0 for hour in range(24)}] * 2,
            "pv_forecast_available": [True, True],
            "data_quality": {"score": 100, "sources": {}, "usable_history_hours": 0},
        }
        without_history, _ = optimizer._confidence(base, 0, True)
        with_history, components = optimizer._confidence(
            {
                **base,
                "data_quality": {
                    "score": 100,
                    "sources": {},
                    "usable_history_hours": 72,
                },
            },
            0,
            True,
        )
        self.assertGreater(components["learning"], 0)
        self.assertGreaterEqual(with_history, without_history)

    def test_tomorrow_soc_continues_through_overnight_home_consumption(self):
        inputs = {
            "date": "2026-07-30",
            "generated_at": "2026-07-30T20:30:00+02:00",
            "current_hour": 20,
            "current_hour_remaining_minutes": 30,
            "soc": 100,
            "battery_capacity_kwh": 20,
            "battery_efficiency": 0.9,
            "min_soc": 20,
            "effective_min_soc": 20,
            "target_soc": 100,
            "effective_power_limit_w": 5000,
            "max_sell_power_w": 5000,
            "sell_prices": [{hour: 0.01 for hour in range(24)}] * 2,
            "buy_prices": [{hour: 5.0 for hour in range(24)}] * 2,
            "distribution": [0] * 48,
            "price_includes_distribution": True,
            "pv_forecast": [0, 0],
            "pv_forecast_full": [0, 0],
            "pv_forecast_available": [True, True],
            "pv_profile": [0] * 24,
            "load_profile_48h": [0.5] * 48,
            "recorded_days": 0,
            "data_quality": {
                "score": 100,
                "sources": {},
                "usable_history_hours": 6,
            },
            "live_state": {"home_power_w": 500, "pv_power_w": 0},
            "current_hour_partial": {
                "elapsed_minutes": 30,
                "remaining_minutes": 30,
                "soc_current_pct": 100,
            },
            "baseline_schedule": [{} for _ in range(48)],
            "user_profiles": {"profiles": {}},
        }
        plan = optimizer.build_energy_plan(inputs)
        rows = plan["baseline"]["rows"]
        midnight = next(
            row for row in rows
            if row["day"] == "tomorrow" and row["hour"] == 0
        )
        morning = next(
            row for row in rows
            if row["day"] == "tomorrow" and row["hour"] == 5
        )
        self.assertLess(morning["soc_after"], midnight["soc_after"])
        self.assertEqual("forecast", morning["soc_source"])


if __name__ == "__main__":
    unittest.main()

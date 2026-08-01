from __future__ import annotations

from datetime import date
import importlib.util
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "optimizer_core.py"
SPEC = importlib.util.spec_from_file_location("optimizer_core_079_tests", MODULE_PATH)
optimizer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(optimizer)


def base_inputs() -> dict:
    solar = [0.0] * 6 + [0.05, 0.15, 0.5, 0.9, 1.2, 1.5, 1.7, 1.6, 1.3, 0.9, 0.5, 0.2] + [0.0] * 6
    return {
        "date": date(2026, 7, 29).isoformat(),
        "generated_at": "2026-07-29T00:00:00+02:00",
        "timezone": "Europe/Warsaw",
        "current_hour": 0,
        "current_hour_remaining_minutes": 60,
        "soc": 70,
        "battery_capacity_kwh": 20,
        "battery_efficiency": 0.9,
        "charge_efficiency": math.sqrt(0.9),
        "discharge_efficiency": math.sqrt(0.9),
        "min_soc": 10,
        "effective_min_soc": 20,
        "target_soc": 95,
        "max_sell_power_w": 5000,
        "effective_power_limit_w": 5000,
        "charge_kwh_per_hour": 5,
        "min_sell_price": 0.2,
        "max_buy_price": 2,
        "allow_battery_sell": True,
        "allow_grid_charge": True,
        "sell_prices": [
            {hour: 0.5 for hour in range(24)},
            {hour: 0.5 for hour in range(24)},
        ],
        "buy_prices": [
            {hour: 0.6 for hour in range(24)},
            {hour: 0.6 for hour in range(24)},
        ],
        "distribution": [0.2] * 48,
        "price_includes_distribution": False,
        "osd_data_complete": True,
        "pv_forecast": [20, 20],
        "pv_forecast_full": [24, 24],
        "pv_forecast_available": [True, True],
        "forecast_correction": 0.5,
        "forecast_accuracy": 80,
        "pv_profile": solar,
        "load_profile_48h": [0.5] * 48,
        "weather_factors": [1.0] * 48,
        "recorded_days": 21,
        "load_profile_sample_count": 168,
        "pv_profile_sample_count": 168,
        "history_schema_version": 2,
        "generation_reason": "test-079",
        "baseline_schedule": [
            {
                "enabled": False,
                "mode": "Normal Operation",
                "sell_power_w": 0,
                "charge_enabled": False,
                "charge_power_w": 0,
            }
            for _ in range(48)
        ],
        "user_profiles": {"schema_version": 2, "profiles": {}},
        "profile_execution": [],
        "data_quality": {
            "score": 100,
            "sources": {
                "battery_soc": {"quality": "good"},
                "pv_power": {"quality": "good"},
                "load_power": {"quality": "good"},
            },
        },
        "battery_cycle_cost_per_kwh": 0.05,
        "terminal_energy_value_per_kwh": 0.25,
    }


def sale_profile(**overrides) -> dict:
    profile = {
        "name": "Poranna sprzedaż",
        "enabled": True,
        "type": "sale",
        "start": "06:00",
        "end": "10:00",
        "active_days": [],
        "priority": "high",
        "goal_character": "preferred",
        "allow_partial": True,
        "minimum_confidence": 0,
        "target_energy_kwh": 6,
        "target_basis": "battery_to_grid",
        "min_price": 0.4,
        "preferred_power_w": 3000,
        "distribution_method": "best_hours",
        "min_soc_after": 20,
        "allow_earlier_grid_charge": False,
        "min_net_result": 0,
    }
    profile.update(overrides)
    return profile


def charge_profile(**overrides) -> dict:
    profile = {
        "name": "Ładowanie",
        "enabled": True,
        "type": "charging",
        "start": "22:00",
        "end": "06:00",
        "deadline": "06:00",
        "active_days": [],
        "priority": "high",
        "goal_character": "preferred",
        "allow_partial": True,
        "minimum_confidence": 0,
        "source": "grid",
        "target_type": "soc",
        "target_value": 80,
        "max_effective_price": 2,
        "max_grid_energy_kwh": 20,
        "preferred_power_w": 3000,
        "purpose": "mixed",
        "charge_missing_only": True,
        "use_corrected_pv": True,
        "preserve_pv_room": False,
        "minimum_free_room_kwh": 0,
        "profitable_only": False,
    }
    profile.update(overrides)
    return profile


class OptimizerCore079Tests(unittest.TestCase):
    def test_zero_and_negative_prices_remain_valid(self):
        values = base_inputs()
        values["buy_prices"][0].update({1: 0.0, 2: -0.25})
        values["sell_prices"][0].update({3: 0.0, 4: -0.3})
        prices = optimizer._prices(values)
        self.assertEqual(0.0, prices["buy"][0][1])
        self.assertEqual(-0.25, prices["buy"][0][2])
        self.assertEqual(0.0, prices["sell"][0][3])
        self.assertEqual(-0.3, prices["sell"][0][4])
        self.assertEqual(-0.05, prices["effective_buy"][0][2])

    def test_negative_sell_price_never_creates_automatic_battery_export(self):
        values = base_inputs()
        values["sell_prices"] = [{hour: -0.2 for hour in range(24)} for _ in range(2)]
        values["min_sell_price"] = -1
        plan = optimizer.build_energy_plan(values, "profit")
        self.assertFalse(any(
            row["battery_to_grid_kwh"] > 0 and row["decision_source"] == "optimizer"
            for row in plan["rows"]
        ))

    def test_allow_partial_false_blocks_incomplete_profile_but_reports_possible(self):
        values = base_inputs()
        values["soc"] = 30
        values["user_profiles"]["profiles"]["morning_sale"] = sale_profile(
            target_energy_kwh=20,
            allow_partial=False,
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        impact = next(item for item in plan["profile_impacts"] if item["profile_id"] == "morning_sale")
        self.assertEqual("blocked_partial_not_allowed", impact["status"])
        self.assertEqual(0, impact["planned_energy_kwh"])
        self.assertGreater(impact["possible_energy_kwh"], 0)
        self.assertGreater(impact["missing_energy_kwh"], 0)
        self.assertFalse(any(row["proposed"] and row["profile_id"] == "morning_sale" for row in plan["rows"]))

    def test_allow_partial_true_keeps_incomplete_profile_with_shortfall(self):
        values = base_inputs()
        values["soc"] = 30
        values["user_profiles"]["profiles"]["morning_sale"] = sale_profile(
            target_energy_kwh=20,
            allow_partial=True,
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        impact = next(item for item in plan["profile_impacts"] if item["profile_id"] == "morning_sale")
        self.assertEqual("partial", impact["status"])
        self.assertGreater(impact["planned_energy_kwh"], 0)
        self.assertGreater(impact["missing_energy_kwh"], 0)

    def test_min_net_result_blocks_profile_below_incremental_threshold(self):
        values = base_inputs()
        values["sell_prices"][0].update({hour: 0.41 for hour in range(6, 10)})
        values["user_profiles"]["profiles"]["morning_sale"] = sale_profile(min_net_result=100)
        plan = optimizer.build_energy_plan(values, "balanced")
        impact = next(item for item in plan["profile_impacts"] if item["profile_id"] == "morning_sale")
        self.assertEqual("blocked_min_net_result", impact["status"])
        self.assertFalse(any(row["proposed"] and row["profile_id"] == "morning_sale" for row in plan["rows"]))

    def test_charge_missing_only_uses_projected_soc_deficit(self):
        values = base_inputs()
        values["soc"] = 72
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="00:00",
            end="03:00",
            deadline="03:00",
            target_value=80,
            charge_missing_only=True,
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        charged = sum(row["grid_to_battery_kwh"] for row in plan["rows"] if row["profile_id"] == "charging")
        expected_input = values["battery_capacity_kwh"] * 0.08 / values["charge_efficiency"]
        self.assertLessEqual(charged, expected_input + 0.01)

    def test_use_corrected_pv_changes_forecast_source(self):
        corrected = base_inputs()
        corrected["user_profiles"]["profiles"]["charging"] = charge_profile(use_corrected_pv=True)
        raw = base_inputs()
        raw["user_profiles"]["profiles"]["charging"] = charge_profile(use_corrected_pv=False)
        corrected_plan = optimizer.build_energy_plan(corrected, "balanced")
        raw_plan = optimizer.build_energy_plan(raw, "balanced")
        corrected_row = next(row for row in corrected_plan["rows"] if row["profile_id"] == "charging")
        raw_row = next(row for row in raw_plan["rows"] if row["profile_id"] == "charging")
        self.assertEqual("corrected", corrected_row["pv_forecast_source"])
        self.assertEqual("solcast_raw", raw_row["pv_forecast_source"])

    def test_deadline_crossing_midnight_excludes_later_slots(self):
        values = base_inputs()
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="22:00",
            end="08:00",
            deadline="03:00",
            target_type="energy",
            target_value=20,
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        rows = [row for row in plan["rows"] if row["profile_id"] == "charging"]
        self.assertTrue(rows)
        self.assertTrue(all(row["hour"] in {22, 23, 0, 1, 2} for row in rows))

    def test_deadline_same_day_excludes_deadline_and_later_slots(self):
        values = base_inputs()
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="10:00",
            end="16:00",
            deadline="13:00",
            target_type="energy",
            target_value=20,
        )
        rows = [
            row for row in optimizer.build_energy_plan(values, "balanced")["rows"]
            if row["profile_id"] == "charging"
        ]
        self.assertTrue(rows)
        self.assertTrue(all(row["hour"] in {10, 11, 12} for row in rows))

    def test_sale_profile_can_request_cheaper_earlier_grid_charge(self):
        values = base_inputs()
        values["soc"] = 21
        values["buy_prices"][0][4] = 0.0
        values["buy_prices"][0][5] = 1.5
        values["sell_prices"][0][6] = 2.0
        values["user_profiles"]["profiles"]["morning_sale"] = sale_profile(
            start="06:00",
            end="07:00",
            target_energy_kwh=3,
            allow_earlier_grid_charge=True,
        )
        rows = optimizer.build_energy_plan(values, "balanced")["rows"]
        support = [row for row in rows if row["profile_id"] == "morning_sale" and row["action"] == "charge"]
        self.assertTrue(support)
        self.assertTrue(all(row["hour"] < 6 for row in support))
        self.assertTrue(all(row["future_target_hour"] == 6 for row in support))

    def test_sale_profile_does_not_charge_earlier_when_option_disabled(self):
        values = base_inputs()
        values["soc"] = 21
        values["buy_prices"][0][4] = 0.0
        values["sell_prices"][0][6] = 2.0
        values["user_profiles"]["profiles"]["morning_sale"] = sale_profile(
            start="06:00",
            end="07:00",
            target_energy_kwh=3,
            allow_earlier_grid_charge=False,
        )
        rows = optimizer.build_energy_plan(values, "balanced")["rows"]
        self.assertFalse(any(
            row["profile_id"] == "morning_sale" and row["action"] == "charge"
            for row in rows
        ))

    def test_profitable_sale_charge_requires_later_sale(self):
        values = base_inputs()
        values["current_hour"] = 15
        values["buy_prices"][0][15] = 0.1
        values["sell_prices"][0][12] = 2.0
        values["sell_prices"][0][20] = 0.2
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="15:00",
            end="16:00",
            deadline="22:00",
            purpose="sale",
            profitable_only=True,
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        row = plan["rows"][15]
        self.assertNotEqual("profitable-charge-before-sale", row["reason_codes"][0])
        self.assertFalse(row["proposed"])

    def test_profitable_home_charge_uses_later_avoided_import(self):
        values = base_inputs()
        values["current_hour"] = 10
        values["buy_prices"][0][10] = 0.0
        values["buy_prices"][0][18] = 2.0
        values["load_profile_48h"][18] = 5
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="10:00",
            end="11:00",
            deadline="20:00",
            purpose="home",
            profitable_only=True,
        )
        row = optimizer.build_energy_plan(values, "balanced")["rows"][10]
        self.assertTrue(row["proposed"])
        self.assertEqual("home", row["purpose"])
        self.assertEqual("home_load", row["future_target_type"])
        self.assertGreater(row["expected_margin"], 0)

    def test_reserve_purpose_is_explicit_even_without_arbitrage(self):
        values = base_inputs()
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="00:00",
            end="01:00",
            deadline="01:00",
            purpose="reserve",
            profitable_only=True,
        )
        row = optimizer.build_energy_plan(values, "balanced")["rows"][0]
        self.assertEqual("reserve", row["purpose"])
        self.assertIn("profile:reserve-goal", row["reason_codes"])

    def test_dynamic_pv_room_is_at_least_configured_minimum(self):
        values = base_inputs()
        values["soc"] = 40
        values["pv_forecast"] = [40, 40]
        values["pv_forecast_full"] = [40, 40]
        values["effective_power_limit_w"] = 500
        values["user_profiles"]["profiles"]["charging"] = charge_profile(
            start="00:00",
            end="02:00",
            deadline="02:00",
            preserve_pv_room=True,
            minimum_free_room_kwh=3,
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        row = next(row for row in plan["rows"] if row["profile_id"] == "charging")
        self.assertGreaterEqual(row["required_pv_room_kwh"], 3)
        self.assertLessEqual(row["max_soc_before_pv_pct"], 85)

    def test_nested_degraded_sources_reduce_confidence(self):
        good = base_inputs()
        degraded = base_inputs()
        degraded["data_quality"] = {
            "score": 35,
            "sources": {
                "battery_soc": {"quality": "degraded"},
                "pv_power": {"quality": "unavailable"},
                "load_power": {"quality": "low"},
            },
        }
        good_confidence = optimizer.build_energy_plan(good, "balanced")["rows"][0]["confidence"]
        degraded_plan = optimizer.build_energy_plan(degraded, "balanced")
        degraded_confidence = degraded_plan["rows"][0]["confidence"]
        self.assertLess(degraded_confidence, good_confidence)
        self.assertLess(degraded_plan["rows"][0]["confidence_components"]["entities"], 100)

    def test_positive_energy_price_with_high_osd_uses_effective_cost(self):
        values = base_inputs()
        values["buy_prices"][0][2] = 0.05
        values["distribution"][2] = 1.25
        prices = optimizer._prices(values)
        self.assertEqual(1.30, prices["effective_buy"][0][2])

    def test_explicit_profile_worse_than_baseline_requires_confirmation(self):
        values = base_inputs()
        values["sell_prices"][0].update({hour: 0.4 for hour in range(6, 10)})
        values["user_profiles"]["profiles"]["morning_sale"] = sale_profile()
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertTrue(any(row["profile_id"] == "morning_sale" and row["proposed"] for row in plan["rows"]))
        self.assertTrue(plan["confirmation_required"])
        self.assertTrue(plan["recommended_write"])

    def test_variant_terminal_soc_targets_affect_automatic_result(self):
        values = base_inputs()
        values["sell_prices"] = [{hour: 2.0 for hour in range(24)} for _ in range(2)]
        bundle = optimizer.build_plan_bundle(values, "balanced")
        safe = bundle["variants"]["safe"]["terminal_soc_actual_pct"]
        balanced = bundle["variants"]["balanced"]["terminal_soc_actual_pct"]
        profit = bundle["variants"]["profit"]["terminal_soc_actual_pct"]
        self.assertGreaterEqual(safe + 0.01, balanced)
        self.assertGreaterEqual(balanced + 0.01, profit)
        self.assertGreaterEqual(safe, 55 - 0.1)
        self.assertGreaterEqual(balanced, 45 - 0.1)
        self.assertGreaterEqual(profit, 30 - 0.1)

    def test_local_timezone_accounts_for_dst_slot_duration(self):
        spring = base_inputs()
        spring.update({
            "date": "2026-03-29",
            "generated_at": "2026-03-29T01:05:00+01:00",
            "current_hour": 1,
        })
        spring_plan = optimizer.build_energy_plan(spring, "balanced")
        spring_two = next(
            row for row in spring_plan["rows"]
            if row["day"] == "today" and row["hour"] == 2
        )
        self.assertEqual(0, spring_two["duration_minutes"])

        autumn = base_inputs()
        autumn.update({
            "date": "2026-10-25",
            "generated_at": "2026-10-25T01:05:00+02:00",
            "current_hour": 1,
        })
        autumn_plan = optimizer.build_energy_plan(autumn, "balanced")
        autumn_two = next(
            row for row in autumn_plan["rows"]
            if row["day"] == "today" and row["hour"] == 2
        )
        self.assertEqual(120, autumn_two["duration_minutes"])

    def test_automatic_strategy_has_no_fixed_sell_hour_cap(self):
        values = base_inputs()
        values["soc"] = 100
        values["battery_capacity_kwh"] = 100
        values["effective_min_soc"] = 0
        values["min_soc"] = 0
        values["sell_prices"] = [{hour: 2.0 for hour in range(24)} for _ in range(2)]
        plan = optimizer.build_energy_plan(values, "profit")
        proposed = [row for row in plan["rows"] if row["proposed"] and row["action"] == "sell"]
        self.assertGreater(len(proposed), 4)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import date
import importlib.util
import json
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "optimizer_core.py"
SPEC = importlib.util.spec_from_file_location("optimizer_core_tests", MODULE_PATH)
optimizer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(optimizer)


def inputs() -> dict:
    solar = [0] * 6 + [0.1, 0.3, 0.7, 1.1, 1.5, 1.8, 2.0, 1.8, 1.4, 1.0, 0.6, 0.2] + [0] * 6
    return {
        "date": date(2026, 7, 29).isoformat(),
        "generated_at": "2026-07-29T00:00:00+02:00",
        "current_hour": 0,
        "current_hour_remaining_minutes": 60,
        "soc": 50,
        "battery_capacity_kwh": 30,
        "battery_efficiency": 0.92,
        "charge_efficiency": math.sqrt(0.92),
        "discharge_efficiency": math.sqrt(0.92),
        "min_soc": 20,
        "effective_min_soc": 33.333,
        "target_soc": 90,
        "max_sell_power_w": 5000,
        "effective_power_limit_w": 5000,
        "charge_kwh_per_hour": 5,
        "min_sell_price": 0.2,
        "max_buy_price": 0.8,
        "allow_battery_sell": True,
        "allow_grid_charge": True,
        "sell_prices": [
            {hour: 0.3 + hour * 0.01 for hour in range(24)},
            {hour: (1.4 if 5 <= hour <= 8 else 0.35) for hour in range(24)},
        ],
        "buy_prices": [
            {hour: (0.18 if hour in (22, 23) else 0.7) for hour in range(24)},
            {hour: (0.2 if hour in (0, 1) else 0.75) for hour in range(24)},
        ],
        "distribution": [0.1] * 48,
        "price_includes_distribution": False,
        "pv_forecast": [24, 18],
        "pv_forecast_full": [30, 18],
        "pv_forecast_available": [True, True],
        "forecast_correction": 0.9,
        "forecast_accuracy": 82,
        "pv_profile": solar,
        "load_profile_48h": [0.5] * 48,
        "weather_factors": [1.0] * 48,
        "recorded_days": 20,
        "history_schema_version": 2,
        "generation_reason": "test",
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
    }


class OptimizerCoreTests(unittest.TestCase):
    def test_complete_contract_and_stable_plan_identity(self):
        first = optimizer.build_energy_plan(inputs(), "balanced")
        second = optimizer.build_energy_plan(inputs(), "balanced")
        self.assertEqual(first["plan_id"], second["plan_id"])
        for key in (
            "plan_id", "generated_at", "horizon_start", "horizon_end",
            "generation_reason", "algorithm_version", "history_schema_version",
            "input_snapshot_id", "selected_variant", "learning_status",
            "plan_status", "duration_ms", "previous_plan_id", "superseded_by_plan_id",
        ):
            self.assertIn(key, first)
        required = {
            "hour_start", "hour_end", "duration_minutes", "action", "charge_source",
            "planned_power_w", "planned_energy_kwh", "target_soc", "soc_start_pct",
            "soc_end_pct", "pv_raw_kwh", "pv_corrected_kwh", "home_load_kwh",
            "pv_to_home_kwh", "pv_to_battery_kwh", "pv_to_grid_kwh",
            "grid_to_battery_kwh", "battery_to_home_kwh", "battery_to_grid_kwh",
            "grid_to_home_kwh", "expected_import_kwh", "expected_export_kwh",
            "buy_price", "distribution_price", "effective_buy_price", "sell_price",
            "export_revenue", "import_cost", "distribution_cost", "loss_cost",
            "battery_cycle_cost", "terminal_value", "net_result", "benefit",
            "confidence", "confidence_components", "reason_codes", "limit_reason",
            "data_quality", "dispatch_status",
        }
        self.assertEqual(48, len(first["rows"]))
        self.assertFalse(required - set(first["rows"][0]))

    def test_soc_is_continuous_across_midnight_and_bounded(self):
        plan = optimizer.build_energy_plan(inputs(), "profit")
        self.assertAlmostEqual(plan["rows"][23]["soc_end_pct"], plan["rows"][24]["soc_start_pct"], places=4)
        self.assertTrue(all(33.333 - 0.01 <= row["soc_end_pct"] <= 90.01 for row in plan["rows"]))

    def test_missing_soc_is_fail_closed(self):
        values = inputs()
        values["soc"] = None
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertEqual("blocked", plan["plan_status"])
        self.assertFalse(plan["recommended_write"])
        self.assertTrue(all(row["action"] == "none" for row in plan["rows"]))
        self.assertTrue(all(row["dispatch_status"] == "blocked" for row in plan["rows"]))

    def test_distribution_is_not_double_counted(self):
        separate = optimizer.build_energy_plan(inputs(), "balanced")
        included_values = inputs()
        included_values["price_includes_distribution"] = True
        included = optimizer.build_energy_plan(included_values, "balanced")
        hour = 0
        self.assertAlmostEqual(
            separate["rows"][hour]["effective_buy_price"],
            separate["rows"][hour]["buy_price"] + separate["rows"][hour]["distribution_price"],
        )
        self.assertEqual(included["rows"][hour]["effective_buy_price"], included["rows"][hour]["buy_price"])
        self.assertTrue(all(row["distribution_cost"] == 0 for row in included["rows"]))

    def test_baseline_uses_existing_schedule_without_unsafe_defaults(self):
        values = inputs()
        values["baseline_schedule"][5] = {
            "enabled": True,
            "mode": "Selling First",
            "sell_power_w": 3500,
            "charge_enabled": False,
            "charge_power_w": 0,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        baseline = plan["baseline"]["rows"][5]
        self.assertEqual("sell", baseline["action"])
        self.assertEqual(3500, baseline["planned_power_w"])
        self.assertFalse(any(
            row["action"] == "charge" and row["planned_power_w"] == 0
            for row in plan["baseline"]["rows"]
        ))

    def test_profile_is_an_optimizer_input_not_a_direct_dispatch(self):
        values = inputs()
        values["user_profiles"]["profiles"]["morning_sale"] = {
            "enabled": True,
            "start": "06:00",
            "end": "08:00",
            "active_days": [],
            "priority": "high",
            "goal_character": "required",
            "min_price": 0,
            "preferred_power_w": 2500,
            "min_soc_after": 35,
            "target_energy_kwh": 10,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        profile_rows = [row for row in plan["rows"] if "profile:morning_sale" in row["reason_codes"]]
        self.assertEqual(4, len(profile_rows))
        planned_rows = [row for row in profile_rows if row["proposed"]]
        skipped_rows = [row for row in profile_rows if not row["proposed"]]
        self.assertTrue(all(row["dispatch_status"] == "planned" for row in planned_rows))
        self.assertTrue(all(row["planned_energy_kwh"] == 0 for row in skipped_rows))
        self.assertTrue(all(row["dispatch_status"] == "skipped" for row in skipped_rows))
        self.assertTrue(all(row["dispatch_status"] != "confirmed" for row in profile_rows))

    def test_sale_profile_honors_target_minimum_price_and_best_hours(self):
        values = inputs()
        values["user_profiles"]["profiles"]["morning_sale"] = {
            "enabled": True,
            "start": "05:00",
            "end": "09:00",
            "active_days": [],
            "priority": "high",
            "goal_character": "preferred",
            "target_energy_kwh": 4,
            "target_basis": "battery_to_grid",
            "min_price": 1.0,
            "preferred_power_w": 2500,
            "distribution_method": "best_hours",
            "min_soc_after": 33.333,
        }
        values["sell_prices"][1].update({5: 1.05, 6: 1.15, 7: 1.30, 8: 1.40})
        plan = optimizer.build_energy_plan(values, "balanced")
        rows = [row for row in plan["rows"] if "profile:morning_sale" in row["reason_codes"]]
        self.assertTrue(rows)
        self.assertTrue(all(row["sell_price"] >= 1.0 for row in rows))
        self.assertLessEqual(sum(row["battery_to_grid_kwh"] for row in rows), 4.00001)
        self.assertEqual([7, 8], [row["hour"] for row in rows])

    def test_profile_slot_power_matches_planned_energy_not_profile_ceiling(self):
        values = inputs()
        values["user_profiles"]["profiles"]["evening_sale"] = {
            "enabled": True,
            "start": "20:00",
            "end": "21:00",
            "active_days": [],
            "priority": "high",
            "goal_character": "preferred",
            "target_energy_kwh": 1,
            "target_basis": "battery_to_grid",
            "min_price": 0,
            "preferred_power_w": 5000,
            "distribution_method": "best_hours",
            "min_soc_after": 20,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        row = next(
            row
            for row in plan["rows"]
            if "profile:evening_sale" in row["reason_codes"]
        )
        self.assertAlmostEqual(1.0, row["planned_energy_kwh"], places=4)
        self.assertEqual(5000, row["power_limit_w"])
        self.assertAlmostEqual(1000, row["planned_power_w"], places=2)

    def test_evening_profile_uses_best_hours_and_reduces_last_slot_power(self):
        values = inputs()
        values.update(
            soc=100,
            battery_capacity_kwh=100,
            min_soc=0,
            effective_min_soc=0,
            target_soc=100,
        )
        values["sell_prices"][0].update({19: 0.9, 20: 1.3, 21: 1.2, 22: 1.1, 23: 1.0})
        values["sell_prices"][1].update({hour: 0.4 for hour in range(19, 24)})
        values["user_profiles"]["profiles"]["evening_sale"] = {
            "enabled": True,
            "start": "19:00",
            "end": "00:00",
            "active_days": [],
            "priority": "high",
            "goal_character": "preferred",
            "target_energy_kwh": 16,
            "target_basis": "battery_to_grid",
            "min_price": 0.4,
            "preferred_power_w": 5000,
            "distribution_method": "best_hours",
            "min_soc_after": 0,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        rows = [
            row
            for row in plan["rows"]
            if "profile:evening_sale" in row["reason_codes"]
        ]
        self.assertEqual([20, 21, 22, 23], [row["hour"] for row in rows])
        self.assertEqual([5, 5, 5, 1], [row["planned_energy_kwh"] for row in rows])
        self.assertEqual([5000, 5000, 5000, 1000], [row["planned_power_w"] for row in rows])

    def test_sale_distribution_even_and_constant_power(self):
        totals = {}
        powers = {}
        for method in ("even", "constant_power"):
            values = inputs()
            values["user_profiles"]["profiles"]["morning_sale"] = {
                "enabled": True,
                "start": "06:00",
                "end": "09:00",
                "active_days": ["2"],
                "priority": "normal",
                "target_energy_kwh": 3,
                "min_price": 0,
                "preferred_power_w": 2000,
                "distribution_method": method,
                "min_soc_after": 20,
            }
            plan = optimizer.build_energy_plan(values, "balanced")
            rows = [row for row in plan["rows"] if "profile:morning_sale" in row["reason_codes"]]
            totals[method] = sum(row["battery_to_grid_kwh"] for row in rows)
            powers[method] = [round(row["battery_to_grid_kwh"], 4) for row in rows]
        self.assertAlmostEqual(3, totals["even"], places=4)
        self.assertAlmostEqual(3, totals["constant_power"], places=4)
        self.assertEqual([1, 1, 1], powers["even"])
        self.assertEqual([1, 1, 1], powers["constant_power"])

    def test_total_export_target_counts_pv_export(self):
        base = inputs()
        profile = {
            "enabled": True,
            "start": "12:00",
            "end": "13:00",
            "active_days": ["2"],
            "priority": "high",
            "target_energy_kwh": 2,
            "min_price": 0,
            "preferred_power_w": 5000,
            "distribution_method": "best_hours",
            "min_soc_after": 20,
        }
        battery_values = dict(base)
        battery_values["user_profiles"] = {"profiles": {"morning_sale": {**profile, "target_basis": "battery_to_grid"}}}
        total_values = dict(base)
        total_values["user_profiles"] = {"profiles": {"morning_sale": {**profile, "target_basis": "total_export"}}}
        battery = optimizer.build_energy_plan(battery_values, "balanced")["rows"][12]
        total = optimizer.build_energy_plan(total_values, "balanced")["rows"][12]
        self.assertLess(total["battery_to_grid_kwh"], battery["battery_to_grid_kwh"])
        self.assertEqual(0, total["battery_to_grid_kwh"])
        self.assertFalse(total["proposed"])
        self.assertEqual(0, total["planned_power_w"])

    def test_algorithm_version_invalidates_pre_fix_cached_plans(self):
        self.assertEqual("0.7.9-local-optimizer-3", optimizer.ALGORITHM_VERSION)
        self.assertEqual(3, optimizer.PLAN_SCHEMA_VERSION)

    def test_confidence_uses_real_profile_coverage_and_rejection_ratio(self):
        values = inputs()
        values.update({
            "load_profile_sample_count": 168,
            "load_profile_covered_cells": 84,
            "load_profile_rejected_count": 168,
            "load_profile_total_cells": 168,
            "pv_profile_sample_count": 437,
            "pv_profile_covered_cells": 48,
            "pv_profile_rejected_count": 2287,
            "pv_profile_total_cells": 288,
        })
        plan = optimizer.build_energy_plan(values, "balanced")
        components = plan["rows"][0]["confidence_components"]
        self.assertLess(components["load_profile"], 100)
        self.assertLess(components["pv_profile"], 100)
        self.assertEqual(84, plan["data_quality"]["load_profile_covered_cells"])
        self.assertEqual(48, plan["data_quality"]["pv_profile_covered_cells"])
        self.assertEqual(168, plan["data_quality"]["load_profile_rejected_samples"])
        self.assertEqual(2287, plan["data_quality"]["pv_profile_rejected_samples"])

    def test_price_coverage_and_confidence_are_derived_from_same_maps(self):
        values = inputs()
        values["sell_prices"] = [{}, {}]
        values["buy_prices"] = [{}, {}]
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertEqual(0, plan["data_quality"]["today_sell_prices"])
        self.assertEqual(0, plan["data_quality"]["today_buy_prices"])
        self.assertEqual(0, plan["rows"][0]["confidence_components"]["prices"])

    def test_osd_quality_reports_partial_coverage(self):
        values = inputs()
        values["osd_available_hours"] = 24
        values["osd_data_complete"] = False
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertEqual(24, plan["data_quality"]["osd_hours"])
        self.assertEqual(50, plan["rows"][0]["confidence_components"]["tariff_osd"])

    def test_charge_energy_target_crosses_midnight_and_respects_grid_cap(self):
        values = inputs()
        values["user_profiles"]["profiles"]["charging"] = {
            "enabled": True,
            "type": "charging",
            "start": "22:00",
            "end": "02:00",
            "active_days": [],
            "priority": "high",
            "target_type": "energy",
            "target_value": 6,
            "max_effective_price": 1,
            "max_grid_energy_kwh": 3,
            "preferred_power_w": 2000,
            "source": "grid",
            "preserve_pv_room": False,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        rows = [row for row in plan["rows"] if "profile:charging" in row["reason_codes"]]
        self.assertTrue({22, 23, 0}.issubset({row["hour"] for row in rows}))
        self.assertLessEqual(sum(row["grid_to_battery_kwh"] for row in rows), 3.00001)

    def test_charge_soc_target_and_pv_only_source(self):
        values = inputs()
        values["user_profiles"]["profiles"]["charging"] = {
            "enabled": True,
            "type": "charging",
            "start": "00:00",
            "end": "03:00",
            "active_days": ["2"],
            "priority": "high",
            "target_type": "soc",
            "target_value": 60,
            "max_effective_price": 1,
            "preferred_power_w": 5000,
            "source": "grid",
            "preserve_pv_room": False,
        }
        grid_plan = optimizer.build_energy_plan(values, "balanced")
        self.assertLessEqual(grid_plan["rows"][2]["soc_end_pct"], 60.0001)
        values["user_profiles"]["profiles"]["charging"]["source"] = "pv"
        pv_plan = optimizer.build_energy_plan(values, "balanced")
        profile_rows = [row for row in pv_plan["rows"] if "profile:charging" in row["reason_codes"]]
        self.assertTrue(profile_rows)
        self.assertTrue(all(row["grid_to_battery_kwh"] == 0 for row in profile_rows))

    def test_conflict_priority_and_minimum_confidence(self):
        values = inputs()
        values["forecast_accuracy"] = 0
        values["recorded_days"] = 0
        values["pv_forecast_available"] = [False, False]
        values["user_profiles"]["profiles"] = {
            "morning_sale": {
                "enabled": True, "start": "06:00", "end": "07:00", "active_days": ["2"],
                "priority": "high", "target_energy_kwh": 1, "min_price": 0,
                "minimum_confidence": 100, "min_soc_after": 20,
            },
            "charging": {
                "enabled": True, "type": "charging", "start": "06:00", "end": "07:00",
                "active_days": ["2"], "priority": "low", "target_type": "energy",
                "target_value": 1, "max_effective_price": 2, "source": "grid",
            },
        }
        row = optimizer.build_energy_plan(values, "balanced")["rows"][6]
        self.assertEqual("none", row["action"])
        self.assertIn("profile:morning_sale", row["reason_codes"])

    def test_financial_deltas_equal_reported_benefit(self):
        plan = optimizer.build_energy_plan(inputs(), "balanced")
        self.assertAlmostEqual(
            plan["optimized_result"] - plan["baseline_result"],
            plan["benefit"],
            places=4,
        )
        self.assertAlmostEqual(sum(row["benefit"] for row in plan["rows"]), plan["benefit"], places=4)
        threshold = max(0.20, abs(plan["baseline_result"]) * 0.01)
        self.assertAlmostEqual(threshold, plan["neutrality_threshold"], places=4)

    def test_variants_expose_parameters_and_equivalence(self):
        bundle = optimizer.build_plan_bundle(inputs(), "profit")
        self.assertEqual({"safe", "balanced", "profit"}, set(bundle["variants"]))
        for key, value in bundle["variants"].items():
            self.assertIn("reserve_buffer_pct", value["variant_settings"])
            self.assertIn("power_limit_pct", value["variant_settings"])
            self.assertIn("minimum_profit_threshold", value["variant_settings"])
            self.assertIn("terminal_soc_target", value["variant_settings"])
        self.assertEqual(
            {"safe_equals_balanced", "balanced_equals_profit", "safe_equals_profit"},
            set(bundle["variant_equivalence"]),
        )

    def test_what_if_is_read_only_and_covers_remaining_horizon(self):
        result = optimizer.simulate_alternative(
            inputs(),
            strategy="safe",
            overrides={"target_soc": 80},
            start_index=12,
        )
        self.assertFalse(result["writes_performed"])
        self.assertEqual(12, result["start_index"])
        self.assertEqual(result["one_hour"], result["remaining_horizon"][0])
        self.assertEqual(36, len(result["remaining_horizon"]))

    def test_payload_is_json_finite(self):
        payload = optimizer.build_plan_bundle(inputs(), "balanced")
        raw = json.dumps(payload, allow_nan=False)
        self.assertNotIn("NaN", raw)
        self.assertNotIn("Infinity", raw)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import date, timedelta
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
            "data_quality", "dispatch_status", "requested_action_energy_kwh",
            "power_limit_reasons", "power_basis",
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
            and row["day"] == "today"
        ]
        self.assertEqual([20, 21, 22, 23], [row["hour"] for row in rows])
        self.assertEqual([4.5, 4.5, 4.5, 2.5], [row["planned_energy_kwh"] for row in rows])
        self.assertEqual([4500, 4500, 4500, 2500], [row["planned_power_w"] for row in rows])

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
        self.assertEqual("0.8.0-local-optimizer-3", optimizer.ALGORITHM_VERSION)
        self.assertEqual(6, optimizer.PLAN_SCHEMA_VERSION)

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

    def test_shared_charge_budget_covers_pv_and_grid_together(self):
        values = inputs()
        values["soc"] = 20
        values["effective_min_soc"] = 20
        values["battery_charge_limit_w"] = 5000
        values["grid_import_limit_w"] = 10000
        values["inverter_ac_limit_w"] = 10000
        values["pv_forecast"] = [0, 0]
        values["pv_forecast_full"] = [0, 0]
        values["pv_profile"] = [0] * 48
        values["live_state"] = {"pv_power_w": 5000, "home_power_w": 0}
        values["user_profiles"]["profiles"]["charging"] = {
            "enabled": True, "type": "charging", "start": "00:00", "end": "01:00",
            "active_days": ["2"], "priority": "high", "target_type": "energy",
            "target_value": 5, "max_effective_price": 2, "preferred_power_w": 5000,
            "source": "grid", "preserve_pv_room": False,
        }
        row = optimizer.build_energy_plan(values, "balanced")["rows"][0]
        self.assertLessEqual(row["pv_to_battery_kwh"] + row["grid_to_battery_kwh"], 5.00001)
        self.assertEqual(5000, row["physical_limits"]["battery_charge_limit_w"])

    def test_shared_discharge_and_export_budgets_cover_all_flows(self):
        values = inputs()
        values["soc"] = 90
        values["effective_min_soc"] = 20
        values["battery_discharge_limit_w"] = 5000
        values["grid_export_limit_w"] = 5000
        values["inverter_ac_limit_w"] = 5000
        values["load_profile_48h"] = [3] * 48
        values["sell_prices"][0][0] = 10
        row = optimizer.build_energy_plan(values, "profit")["rows"][0]
        self.assertLessEqual(row["battery_to_home_kwh"] + row["battery_to_grid_kwh"], 5.00001)
        self.assertLessEqual(row["pv_to_grid_kwh"] + row["battery_to_grid_kwh"], 5.00001)

    def test_global_permissions_dominate_user_profiles(self):
        values = inputs()
        values["allow_battery_sell"] = False
        values["allow_grid_charge"] = False
        values["user_profiles"]["profiles"] = {
            "morning_sale": {
                "enabled": True, "start": "06:00", "end": "07:00", "active_days": ["2"],
                "priority": "high", "target_energy_kwh": 2, "min_price": 0,
            },
            "charging": {
                "enabled": True, "type": "charging", "start": "07:00", "end": "08:00",
                "active_days": ["2"], "priority": "high", "target_type": "energy",
                "target_value": 2, "max_effective_price": 2, "source": "grid",
            },
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertEqual("none", plan["rows"][6]["action"])
        self.assertIn("safety:battery-sale-disabled", plan["rows"][6]["reason_codes"])
        self.assertEqual("none", plan["rows"][7]["action"])
        self.assertIn("safety:grid-charge-disabled", plan["rows"][7]["reason_codes"])

    def test_candidate_is_locally_resimulated_and_never_written(self):
        result = optimizer.simulate_alternative(
            inputs(),
            changes=[{"index": 20, "action": "sell", "power_w": 2500}],
        )
        self.assertTrue(result["locally_validated"])
        self.assertTrue(result["manual_confirmation_required"])
        self.assertFalse(result["writes_performed"])
        self.assertIn("candidate:locally-resimulated", result["remaining_horizon"][20]["reason_codes"])
        self.assertIn("candidate_vs_source", result["comparison"])

    def test_candidate_rejects_too_many_or_out_of_horizon_changes(self):
        with self.assertRaises(ValueError):
            optimizer.simulate_alternative(
                inputs(),
                changes=[{"index": index, "action": "none", "power_w": 0} for index in range(6)],
            )
        with self.assertRaises(ValueError):
            optimizer.simulate_alternative(
                inputs(),
                changes=[{"index": 48, "action": "sell", "power_w": 1000}],
            )

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
        self.assertEqual("comparison_only", bundle["optimizer_shadow"]["mode"])
        self.assertFalse(bundle["optimizer_shadow"]["writes_performed"])
        self.assertTrue(bundle["optimizer_shadow"]["manual_confirmation_required"])

    def test_conversion_losses_are_not_charged_twice(self):
        values = inputs()
        values["battery_cycle_cost_per_kwh"] = 0
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertGreaterEqual(plan["financials"]["conversion_losses_kwh"], 0)
        self.assertEqual(0, plan["financials"]["loss_cost"])

    def test_missing_prices_are_reported_as_incomplete_not_free_energy(self):
        values = inputs()
        values["buy_prices"] = [{}, {}]
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertFalse(plan["financials"]["financial_data_complete"])
        self.assertGreater(plan["financials"]["unpriced_import_kwh"], 0)
        self.assertFalse(plan["recommended_write"])

    def test_rankings_are_chronological_and_keep_price_rank(self):
        values = inputs()
        values["user_profiles"]["profiles"]["evening_sale"] = {
            "enabled": True,
            "start": "17:00",
            "end": "00:00",
            "active_days": [],
            "priority": "high",
            "target_energy_kwh": 3,
            "min_price": 0,
            "min_soc_after": 20,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        sales = plan["ui_insights"]["sale_profiles"]["evening_sale"]["days"]["today"]
        purchases = plan["ui_insights"]["purchase_ranking"]["days"]["today"]
        self.assertEqual(sorted(row["hour"] for row in sales), [row["hour"] for row in sales])
        self.assertEqual(sorted(row["hour"] for row in purchases), [row["hour"] for row in purchases])
        best_sale = max(sales, key=lambda row: row["sell_price"])
        cheapest_purchase = min(purchases, key=lambda row: row["effective_price"])
        self.assertEqual(1, best_sale["price_rank"])
        self.assertEqual(1, cheapest_purchase["price_rank"])

    def test_past_profile_hours_are_not_recommended(self):
        values = inputs()
        values["current_hour"] = 12
        values["generated_at"] = "2026-07-29T12:00:00+02:00"
        values["user_profiles"]["profiles"]["morning_sale"] = {
            "enabled": True,
            "start": "05:00",
            "end": "10:00",
            "active_days": [],
            "priority": "high",
            "target_energy_kwh": 3,
            "min_price": 0,
            "min_soc_after": 20,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        rows = plan["ui_insights"]["sale_profiles"]["morning_sale"]["days"]["today"]
        self.assertTrue(rows)
        self.assertTrue(all(row["is_past"] for row in rows))
        self.assertTrue(all(not row["recommended"] for row in rows))
        self.assertTrue(all(row["skip_reason"] == "past_window" for row in rows))
        summary = plan["ui_insights"]["sale_profiles"]["morning_sale"]["day_summaries"]["today"]
        self.assertTrue(summary["window_ended"])
        self.assertEqual("past_window", summary["primary_constraint"])

    def test_profile_explanations_keep_today_and_tomorrow_totals_separate(self):
        values = inputs()
        values["current_hour"] = 0
        values["user_profiles"]["profiles"]["evening_sale"] = {
            "enabled": True,
            "start": "17:00",
            "end": "00:00",
            "active_days": [],
            "priority": "high",
            "target_energy_kwh": 6,
            "min_price": 0,
            "min_soc_after": 20,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        profile = plan["ui_insights"]["sale_profiles"]["evening_sale"]
        today = profile["day_summaries"]["today"]
        tomorrow = profile["day_summaries"]["tomorrow"]
        today_rows = profile["days"]["today"]
        tomorrow_rows = profile["days"]["tomorrow"]
        self.assertEqual(values["date"], today["date"])
        self.assertNotEqual(today["date"], tomorrow["date"])
        self.assertAlmostEqual(
            sum(row["planned_energy_kwh"] for row in today_rows if row["recommended"]),
            today["profile_planned_energy_kwh"],
            places=5,
        )
        self.assertAlmostEqual(
            sum(row["planned_energy_kwh"] for row in tomorrow_rows if row["recommended"]),
            tomorrow["profile_planned_energy_kwh"],
            places=5,
        )
        self.assertAlmostEqual(
            today["profile_planned_energy_kwh"] + tomorrow["profile_planned_energy_kwh"],
            profile["planned_energy_kwh"],
            places=5,
        )
        for summary in (today, tomorrow):
            self.assertAlmostEqual(
                max(0, summary["target_energy_kwh"] - summary["profile_planned_energy_kwh"]),
                summary["missing_profile_energy_kwh"],
                places=5,
            )
            self.assertAlmostEqual(
                summary["profile_planned_energy_kwh"] + summary["optimizer_extra_energy_kwh"],
                summary["total_proposed_energy_kwh"],
                places=5,
            )

    def test_profile_ui_rows_expose_power_inputs_for_frontend_explanation(self):
        values = inputs()
        values["current_hour"] = 0
        values["user_profiles"]["profiles"]["evening_sale"] = {
            "enabled": True,
            "start": "17:00",
            "end": "00:00",
            "active_days": [],
            "priority": "high",
            "target_energy_kwh": 3,
            "min_price": 0,
            "min_soc_after": 20,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        selected = [
            row for row in plan["ui_insights"]["sale_profiles"]["evening_sale"]["days"]["today"]
            if row["recommended"]
        ]
        self.assertTrue(selected)
        for row in selected:
            self.assertGreater(row["planned_power_w"], 0)
            self.assertGreater(row["duration_minutes"], 0)
            self.assertIsNotNone(row["power_limit_w"])
            self.assertTrue(row["power_basis"])

    def test_today_write_is_independent_from_missing_tomorrow_prices(self):
        values = inputs()
        values["generated_at"] = "2026-07-29T12:00:00+02:00"
        values["soc"] = 100
        values["effective_min_soc"] = 20
        values["sell_prices"][1] = {}
        values["buy_prices"][1] = {}
        values["user_profiles"]["profiles"]["evening_sale"] = {
            "enabled": True,
            "start": "19:00",
            "end": "23:00",
            "active_days": [],
            "priority": "high",
            "target_energy_kwh": 3,
            "min_price": 0,
            "min_soc_after": 20,
        }
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertTrue(plan["recommended_write_by_day"]["today"]["allowed"])
        self.assertFalse(plan["recommended_write_by_day"]["tomorrow"]["allowed"])
        self.assertEqual("awaiting_publication", plan["ui_insights"]["price_publication"]["tomorrow_status"])

    def test_missing_tomorrow_prices_after_publication_are_reported(self):
        values = inputs()
        values["generated_at"] = "2026-07-29T15:00:00+02:00"
        values["timezone"] = "Europe/Warsaw"
        values["sell_prices"][1] = {}
        values["buy_prices"][1] = {}
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertEqual("missing_after_publication", plan["ui_insights"]["price_publication"]["tomorrow_status"])

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

    def test_canonical_prices_are_the_only_core_economic_price_truth(self):
        values = inputs()
        canonical = {"schema_version": 1, "diagnostics": {"contract": "test"}, "buy": {"rows": []}, "sell": {"rows": []}}
        for day_index, day_name in enumerate(("today", "tomorrow")):
            local_date = (date(2026, 7, 29) + timedelta(days=day_index)).isoformat()
            for hour in range(24):
                canonical["buy"]["rows"].append({
                    "day": day_name, "date": local_date, "hour": hour, "quality": "ready",
                    "source_adapter": "pstryk", "source_unit": "PLN/kWh", "source_basis": "gross",
                    "source_semantic_scope": "all_in_variable", "source_price_pln_kwh": 0.23,
                    "energy_component": 0.23, "added_distribution": 0.0, "added_vat": 0.0,
                    "added_other_variable": 0.0, "final_price_pln_kwh": 0.23,
                })
                canonical["sell"]["rows"].append({
                    "day": day_name, "date": local_date, "hour": hour, "quality": "ready",
                    "source_adapter": "custom", "source_price_pln_kwh": 1.0,
                    "final_price_pln_kwh": 1.0,
                })
        values["canonical_prices"] = canonical
        # Conflicting legacy arrays prove that the canonical contract wins.
        values["buy_prices"] = [{hour: 9.0 for hour in range(24)}] * 2
        values["distribution"] = [7.0] * 48
        plan = optimizer.build_energy_plan(values, "balanced")
        self.assertEqual(0.23, plan["rows"][0]["effective_buy_price"])
        self.assertEqual(0.0, plan["rows"][0]["distribution_price"])
        self.assertEqual(1.0, plan["rows"][0]["sell_price"])
        self.assertEqual(canonical, plan["canonical_prices"])
        purchase = plan["ui_insights"]["purchase_ranking"]["days"]["today"][0]
        self.assertEqual("pstryk", purchase["source_adapter"])
        self.assertTrue(purchase["price_includes_distribution"])


if __name__ == "__main__":
    unittest.main()

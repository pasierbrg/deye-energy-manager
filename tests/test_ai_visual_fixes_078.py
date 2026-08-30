from __future__ import annotations

from datetime import date
import importlib.util
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER_PATH = ROOT / "custom_components" / "deye_energy_manager" / "optimizer_core.py"
SPEC = importlib.util.spec_from_file_location("optimizer_visual_078_tests", OPTIMIZER_PATH)
optimizer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(optimizer)


def tariff_rows(
    *,
    provider: str = "pge",
    plan: str = "g12w",
    first_rate: float = 0.8,
    second_rate: float = 0.1,
) -> list[dict]:
    result = []
    for index in range(48):
        hour = index % 24
        result.append(
            {
                "date": "2026-07-29" if index < 24 else "2026-07-30",
                "hour": hour,
                "available": True,
                "rate": first_rate if hour == 0 else second_rate if hour == 1 else 0.35,
                "total_distribution_rate": first_rate if hour == 0 else second_rate if hour == 1 else 0.35,
                "zone": "peak" if hour == 0 else "offpeak",
                "season": "summer",
                "day_type": "weekday" if index < 24 else "holiday",
                "provider": provider,
                "plan": plan,
            }
        )
    return result


def base_inputs() -> dict:
    solar = [0.0] * 24
    profiles = {
        "morning_sale": {
            "name": "Poranna sprzedaż",
            "enabled": True,
            "type": "sale",
            "start": "06:00",
            "end": "09:00",
            "active_days": [],
            "priority": "high",
            "goal_character": "preferred",
            "allow_partial": True,
            "minimum_confidence": 0,
            "target_energy_kwh": 4,
            "target_basis": "battery_to_grid",
            "min_price": 0.5,
            "preferred_power_w": 2000,
            "distribution_method": "best_hours",
            "min_soc_after": 20,
        },
        "evening_sale": {
            "name": "Wieczorna sprzedaż",
            "enabled": True,
            "type": "sale",
            "start": "18:00",
            "end": "22:00",
            "active_days": [],
            "priority": "high",
            "goal_character": "preferred",
            "allow_partial": True,
            "minimum_confidence": 0,
            "target_energy_kwh": 4,
            "target_basis": "battery_to_grid",
            "min_price": 0.5,
            "preferred_power_w": 2000,
            "distribution_method": "best_hours",
            "min_soc_after": 20,
        },
        "charging": {
            "name": "Ładowanie",
            "enabled": False,
            "type": "charging",
            "start": "22:00",
            "end": "06:00",
            "active_days": [],
            "target_type": "energy",
            "target_value": 5,
            "max_effective_price": 1,
        },
    }
    sell_today = {hour: 0.3 for hour in range(24)}
    sell_today.update({6: 0.8, 7: 0.9, 8: 0.9, 18: 1.0, 19: 1.2, 20: 1.1, 21: 0.7})
    sell_tomorrow = dict(sell_today)
    return {
        "date": date(2026, 7, 29).isoformat(),
        "generated_at": "2026-07-29T00:00:00+02:00",
        "current_hour": 0,
        "current_hour_remaining_minutes": 60,
        "soc": 90,
        "battery_capacity_kwh": 30,
        "battery_efficiency": 0.92,
        "charge_efficiency": math.sqrt(0.92),
        "discharge_efficiency": math.sqrt(0.92),
        "min_soc": 20,
        "effective_min_soc": 33.3,
        "target_soc": 95,
        "max_sell_power_w": 5000,
        "effective_power_limit_w": 5000,
        "charge_kwh_per_hour": 5,
        "min_sell_price": 0.2,
        "max_buy_price": 2,
        "allow_battery_sell": True,
        "allow_grid_charge": True,
        "sell_prices": [sell_today, sell_tomorrow],
        "buy_prices": [
            {hour: 0.2 if hour == 0 else 0.5 if hour == 1 else 0.7 for hour in range(24)},
            {hour: 0.25 if hour == 0 else 0.55 if hour == 1 else 0.75 for hour in range(24)},
        ],
        "distribution": [
            row["total_distribution_rate"] for row in tariff_rows()
        ],
        "price_includes_distribution": False,
        "osd_data_complete": True,
        "tariff_context": {
            "provider": "pge",
            "provider_name": "PGE Dystrybucja",
            "plan": "g12w",
            "plan_name": "G12w",
            "configured": True,
            "hourly_profile": tariff_rows(),
        },
        "buy_price_source": "sensor.pstryk_buy_price",
        "pv_forecast": [0, 0],
        "pv_forecast_full": [0, 0],
        "pv_forecast_available": [True, True],
        "forecast_correction": 1,
        "forecast_accuracy": 90,
        "pv_profile": solar,
        "load_profile_48h": [0.2] * 48,
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
        "user_profiles": {"schema_version": 2, "profiles": profiles},
        "profile_execution": [],
    }


class AiVisualPayloadTests(unittest.TestCase):
    def test_morning_and_evening_rankings_use_user_windows(self):
        plan = optimizer.build_energy_plan(base_inputs(), "balanced")
        rankings = plan["ui_insights"]["sale_profiles"]
        morning = rankings["morning_sale"]["days"]["today"]
        evening = rankings["evening_sale"]["days"]["today"]
        self.assertTrue(all(6 <= row["hour"] < 9 for row in morning))
        self.assertTrue(all(18 <= row["hour"] < 22 for row in evening))
        self.assertFalse({row["hour"] for row in morning} & {row["hour"] for row in evening})

    def test_sale_ranking_is_chronological_and_keeps_price_rank(self):
        plan = optimizer.build_energy_plan(base_inputs(), "balanced")
        morning = plan["ui_insights"]["sale_profiles"]["morning_sale"]["days"]["today"]
        self.assertEqual([6, 7, 8], [row["hour"] for row in morning])
        self.assertEqual([3, 1, 2], [row["price_rank"] for row in morning])

    def test_minimum_sale_price_and_no_hours_status(self):
        values = base_inputs()
        values["user_profiles"]["profiles"]["morning_sale"]["min_price"] = 2
        plan = optimizer.build_energy_plan(values, "balanced")
        profile = plan["ui_insights"]["sale_profiles"]["morning_sale"]
        self.assertEqual("no_hours_above_minimum", profile["status"])
        self.assertTrue(all(not row["recommended"] for row in profile["days"]["today"]))

    def test_partial_sale_target_exposes_missing_energy(self):
        values = base_inputs()
        values["user_profiles"]["profiles"]["morning_sale"]["target_energy_kwh"] = 30
        plan = optimizer.build_energy_plan(values, "balanced")
        profile = plan["ui_insights"]["sale_profiles"]["morning_sale"]
        self.assertEqual("partially_possible", profile["status"])
        self.assertGreater(profile["missing_energy_kwh"], 0)

    def test_disabled_profile_is_informational_not_active(self):
        values = base_inputs()
        values["user_profiles"]["profiles"]["morning_sale"]["enabled"] = False
        plan = optimizer.build_energy_plan(values, "balanced")
        profile = plan["ui_insights"]["sale_profiles"]["morning_sale"]
        self.assertEqual("disabled", profile["status"])
        self.assertTrue(all(not row["recommended"] for row in profile["days"]["today"]))

    def test_purchase_ranking_is_chronological_and_keeps_cost_rank(self):
        plan = optimizer.build_energy_plan(base_inputs(), "balanced")
        ranking = plan["ui_insights"]["purchase_ranking"]["days"]["today"]
        self.assertEqual(list(range(24)), [row["hour"] for row in ranking])
        cheapest = min(ranking, key=lambda row: row["price_rank"])
        self.assertEqual(1, cheapest["hour"])
        self.assertEqual(
            cheapest["effective_price"],
            round(cheapest["energy_price"] + cheapest["distribution_price"], 5),
        )

    def test_distribution_is_included_only_once(self):
        values = base_inputs()
        values["price_includes_distribution"] = True
        plan = optimizer.build_energy_plan(values, "balanced")
        row = plan["ui_insights"]["purchase_ranking"]["days"]["today"][0]
        self.assertEqual(0, row["distribution_price"])
        self.assertEqual(row["energy_price"], row["effective_price"])

    def test_operator_tariff_season_day_type_and_manual_profile_are_exposed(self):
        values = base_inputs()
        values["tariff_context"].update(
            provider="custom",
            provider_name="Profil ręczny",
            plan="manual",
            plan_name="Taryfa ręczna",
        )
        plan = optimizer.build_energy_plan(values, "balanced")
        ranking = plan["ui_insights"]["purchase_ranking"]
        first = ranking["days"]["today"][0]
        tomorrow = ranking["days"]["tomorrow"][0]
        self.assertEqual("Profil ręczny", ranking["provider_name"])
        self.assertEqual("Taryfa ręczna", ranking["plan_name"])
        self.assertEqual("summer", first["season"])
        self.assertEqual("weekday", first["day_type"])
        self.assertEqual("holiday", tomorrow["day_type"])

    def test_tariff_profile_changes_purchase_rank_without_changing_chronology(self):
        first = optimizer.build_energy_plan(base_inputs(), "balanced")
        values = base_inputs()
        values["distribution"][0] = 0
        values["distribution"][1] = 1
        values["tariff_context"]["hourly_profile"][0]["total_distribution_rate"] = 0
        values["tariff_context"]["hourly_profile"][1]["total_distribution_rate"] = 1
        second = optimizer.build_energy_plan(values, "balanced")
        first_rows = first["ui_insights"]["purchase_ranking"]["days"]["today"]
        second_rows = second["ui_insights"]["purchase_ranking"]["days"]["today"]
        self.assertEqual([row["hour"] for row in first_rows], [row["hour"] for row in second_rows])
        self.assertNotEqual(
            {row["hour"]: row["price_rank"] for row in first_rows},
            {row["hour"]: row["price_rank"] for row in second_rows},
        )

    def test_missing_osd_warns_and_blocks_optimizer_grid_charge(self):
        values = base_inputs()
        values["osd_data_complete"] = False
        values["tariff_context"]["configured"] = False
        plan = optimizer.build_energy_plan(values, "balanced")
        ranking = plan["ui_insights"]["purchase_ranking"]
        self.assertEqual("missing_osd_data", ranking["warning"])
        self.assertFalse(ranking["osd_complete"])
        self.assertFalse(any(
            row["action"] == "charge" and row["decision_source"] == "optimizer"
            for row in plan["rows"]
        ))

    def test_profile_goal_planned_actual_remaining_are_separate(self):
        values = base_inputs()
        values["profile_execution"] = [
            {
                "profile_id": "morning_sale",
                "date": "2026-07-29",
                "hour": 7,
                "actual_energy_kwh": 1.25,
            }
        ]
        plan = optimizer.build_energy_plan(values, "balanced")
        impact = next(row for row in plan["profile_impacts"] if row["profile_id"] == "morning_sale")
        self.assertEqual(4, impact["requested_energy_kwh"])
        self.assertGreater(impact["planned_energy_kwh"], 0)
        self.assertEqual(1.25, impact["actual_energy_kwh"])
        self.assertEqual(2.75, impact["remaining_energy_kwh"])

    def test_evening_before_start_and_disabled_charging_are_visible(self):
        plan = optimizer.build_energy_plan(base_inputs(), "balanced")
        impacts = {row["profile_id"]: row for row in plan["profile_impacts"]}
        self.assertEqual(0, impacts["evening_sale"]["actual_energy_kwh"])
        self.assertIn(impacts["evening_sale"]["status"], {"waiting", "no_qualified_hours"})
        self.assertEqual("disabled", impacts["charging"]["status"])

    def test_comparison_classifies_better_neutral_and_worse(self):
        values = base_inputs()
        prices = optimizer._prices(values)
        rows = optimizer._simulate(
            values,
            "balanced",
            baseline=False,
            forecast=optimizer._forecast_series(values),
            prices=prices,
        )["rows"]
        better = optimizer._ui_insights(values, prices, rows, 1, 0.2)["comparison"]
        self.assertEqual("better", better["assessment"])
        self.assertEqual("Plan z wyższym wynikiem modelowanym", better["decision_title"])
        self.assertEqual("neutral", optimizer._ui_insights(values, prices, rows, 0.1, 0.2)["comparison"]["assessment"])
        worse = optimizer._ui_insights(values, prices, rows, -1, 0.2)["comparison"]
        self.assertEqual("worse", worse["assessment"])
        self.assertEqual("Realizacja profilu użytkownika", worse["decision_title"])

    def test_tomorrow_proposal_is_not_reported_as_unplanned(self):
        plan = optimizer.build_energy_plan(base_inputs(), "balanced")
        self.assertIn(
            plan["ui_insights"]["tomorrow_plan_status"],
            {"proposal_pending", "forecast_ready"},
        )

    def test_soc_and_minimums_are_bounded_and_available(self):
        plan = optimizer.build_energy_plan(base_inputs(), "balanced")
        minimum = plan["ui_insights"]["minimum_soc"]
        self.assertEqual(20, minimum["hard_min_soc_pct"])
        self.assertEqual(33.3, minimum["effective_min_soc_pct"])
        self.assertTrue(all(0 <= row["soc_end_pct"] <= 100 for row in plan["rows"]))
        self.assertTrue(all("hard_min_soc_pct" in row and "effective_min_soc_pct" in row for row in plan["rows"]))


class AiVisualSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            ROOT
            / "custom_components"
            / "deye_energy_manager"
            / "www"
            / "deye-energy-manager-card.js"
        ).read_text(encoding="utf-8")

    def test_overview_is_compact_without_full_daily_or_weather_cards(self):
        start = self.source.index("  renderAiOverview(")
        end = self.source.index("  renderAiProposalView(", start)
        method = self.source[start:end]
        self.assertNotIn("aiReadableEnergyChart(", method)
        self.assertNotIn("aiWeatherCard(", method)
        self.assertIn("aiCompactWeather()", method)

    def test_action_footer_exists_only_in_proposals_and_is_sticky(self):
        self.assertEqual(1, self.source.count('<footer class="ai-action-footer">'))
        self.assertIn(".ai-action-footer{position:sticky;bottom:0", self.source)
        self.assertIn("Zaznacz przynajmniej jedną godzinę", self.source)

    def test_polish_translations_and_api_error_are_user_friendly(self):
        for text in (
            "Korzyść całego planu względem bazowego",
            "Wynik z pamięci — dane wejściowe bez zmian",
            "Profil: Poranna sprzedaż",
            "Profil: Wieczorna sprzedaż",
            "Asystent AI: błąd autoryzacji",
            "Sprawdź klucz API dostawcy.",
            "Uzasadnienie planu",
        ):
            self.assertIn(text, self.source)

    def test_chart_contract_is_zero_to_one_hundred_and_future_actual_is_hidden(self):
        self.assertIn("Oś energii zaczyna się od 0 kWh", self.source)
        self.assertIn("oś SOC ma zakres 0–100%", self.source)
        self.assertIn('row.date !== todayKey || Number(row.hour) > now.getHours()', self.source)
        self.assertIn("Efektywne minimum planu", self.source)

    def test_crisp_chart_uses_one_hour_grid_for_weather_statuses_and_axes(self):
        start = self.source.index("  aiReadableDayChart(")
        end = self.source.index("  aiApiPresentation(", start)
        method = self.source[start:end]
        self.assertIn('["sell", "Sprzedaż"]', method)
        self.assertIn('["charge", "Ładowanie"]', method)
        self.assertIn('["tariff", "Tania taryfa"]', method)
        self.assertIn("const sameMinimum", method)
        self.assertIn("(użytkownik = plan)", method)
        self.assertIn('class="ai-crisp-axis-values"', method)
        self.assertIn('style="left:${currentPercent}%"', method)
        self.assertNotIn("<span>Sprzedaż</span>", method)
        self.assertNotIn("<span>Ładowanie</span>", method)
        self.assertNotIn("<span>Tania dystrybucja</span>", method)
        weather = method.index('<div class="ai-crisp-weather-grid">')
        statuses = method.index('<div class="ai-crisp-status">')
        hours = method.index('<div class="ai-crisp-time-grid">')
        self.assertLess(weather, statuses)
        self.assertLess(statuses, hours)
        self.assertIn(
            ".ai-crisp-status>div{display:grid;grid-template-columns:repeat(24,minmax(0,1fr))",
            self.source,
        )
        self.assertIn(
            ".ai-crisp-axis-values{height:100%;display:flex;flex-direction:column;justify-content:space-between}",
            self.source,
        )

    def test_overview_contains_required_sections(self):
        start = self.source.index("  renderAiOverview(")
        end = self.source.index("  renderAiProposalView(", start)
        method = self.source[start:end]
        for title in (
            "Wynik i porównanie",
            "Najlepsze godziny sprzedaży",
            "Najtańsze godziny zakupu",
            "Prognoza SOC 48 h",
            "Wynik modelowany całego planu",
            "Profile użytkownika",
            "Status planu",
            "Najważniejsze ostrzeżenia",
        ):
            self.assertIn(title, method)

    def test_browser_planner_is_diagnostic_only_and_cannot_create_fallback_plan(self):
        self.assertNotIn("aiBestWindow(", self.source)
        self.assertNotIn("aiProposal(", self.source)
        self.assertNotIn("applyAiProposal(", self.source)
        self.assertNotIn("data-apply-ai-proposal", self.source)
        planner_start = self.source.index("  aiPlannerData(")
        planner_end = self.source.index("  aiRowsForDay(", planner_start)
        planner = self.source[planner_start:planner_end]
        self.assertIn("diagnostic_only: true", planner)
        self.assertIn("Brak planu — backendowy Optimizer Core jest niedostępny.", planner)
        self.assertIn("plan_status: \"blocked\"", planner)
        self.assertIn("recommended_write: false", planner)

    def test_tomorrow_plan_sends_per_slot_revalidation_contract(self):
        start = self.source.index("  async applyAiDayPlan(")
        end = self.source.index("  aiConfidenceClass(", start)
        method = self.source[start:end]
        for field in (
            "slot_validations", "minimum_price", "minimum_soc", "allow_partial",
            "remaining_target_kwh", "min_net_result", "profile_net_result_pln",
            "max_soc_before_pv_pct", "deadline_next_day",
        ):
            self.assertIn(field, method)
        self.assertIn("profile.minimum_price ?? 0", method)
        self.assertIn("profile.allow_partial !== false", method)

    def test_sale_status_fallback_recomputes_qualified_hours(self):
        start = self.source.index("  aiSaleInsights(")
        end = self.source.index("  renderAiSaleRankings(", start)
        method = self.source[start:end]
        self.assertIn("qualified_hours: qualified", method)
        self.assertIn("price + 1e-9 >= minimum", method)
        self.assertIn("configured.min_price", method)
        self.assertLess(
            method.index("configured.min_price"),
            method.index("supplied.minimum_price"),
        )
        self.assertNotIn("return backend;", method)

    def test_ai_prices_use_two_decimal_polish_format_and_price_ranking(self):
        sale_start = self.source.index("  renderAiSaleRankings(")
        purchase_end = self.source.index("  aiLegacyWeatherCard(", sale_start)
        methods = self.source[sale_start:purchase_end]
        self.assertIn("Cena nr", methods)
        self.assertIn("const visible = rows.slice().sort", methods)
        self.assertIn("const rows = ranked.slice(0, 8).sort", methods)
        self.assertNotIn("aiFormatNumber(row.sell_price, 4)", methods)
        self.assertNotIn("aiFormatNumber(row.effective_price, 4)", methods)
        self.assertIn("aiFormatNumber(row.sell_price, 2)", methods)

    def test_ai_schedule_patch_uses_exact_row_power_and_filters_sell_currents(self):
        power_start = self.source.index("  aiPlannedSlotPower(")
        start = self.source.index("  aiRowUpdate(")
        end = self.source.index("  async applyAiDayPlan(", start)
        power_method = self.source[power_start:start]
        method = self.source[start:end]
        self.assertIn("energy * 1000 * 60 / duration", power_method)
        self.assertIn("this.aiPlannedSlotPower(row)", method)
        self.assertIn("update.sell_power", method)
        self.assertIn('if (charging)', method)
        self.assertIn("this.chargeProfileStoredValues()", method)
        self.assertIn("charge_current: profile.charge_current", method)
        self.assertIn("discharge_current: profile.discharge_current", method)
        self.assertIn("grid_charge_current: profile.grid_charge_current", method)
        self.assertIn("tou_soc: profile.target_soc", method)
        contract_path, legacy_path = method.split('    const selling = row.action === "sell";', 1)
        self.assertIn("row?.action_contract?.schedule_update", contract_path)
        self.assertIn('row.action === "sell"', contract_path)
        self.assertIn('new Set(["slot_key", "enabled", "mode", "sell_power"])', contract_path)
        self.assertIn('"minimum_sell_soc"', contract_path)
        self.assertIn('"min_sell_price"', contract_path)
        for forbidden in (
            "maxSellPower",
            "minimum_sell_soc",
            "min_sell_price",
        ):
            self.assertNotIn(forbidden, legacy_path)

    def test_invalid_or_unprofitable_optimizer_rows_cannot_be_applied(self):
        start = self.source.index("  aiIsApplicableProposal(")
        end = self.source.index("  initialiseAiSelections(", start)
        method = self.source[start:end]
        self.assertIn("energy <= 1e-6", method)
        self.assertIn("this.aiPlannedSlotPower(row) <= 0", method)
        self.assertIn("row.benefit", method)
        self.assertIn("<= 0.005", method)

    def test_sale_profiles_use_full_width_and_day_columns_remain_local(self):
        self.assertIn(
            ".ai-sale-rankings,.ai-profile-cards{display:grid;grid-template-columns:minmax(0,1fr)",
            self.source,
        )
        self.assertIn(".ai-price-columns{display:grid;grid-template-columns:1fr 1fr", self.source)
        self.assertIn(".ai-rank-row summary strong{color:#fff;text-align:right;white-space:nowrap}", self.source)

    def test_proposal_view_distinguishes_slot_power_from_estimated_energy(self):
        start = self.source.index("  renderAiProposalView(")
        end = self.source.index("  renderAiLegacyQualityCard(", start)
        method = self.source[start:end]
        for text in (
            "Moc do slotu",
            "Szacowana energia",
            "wartość szacowana",
            "Co zostanie zapisane?",
            "Pozostałe pola",
        ):
            self.assertIn(text, self.source)
        self.assertIn("dokładną moc sprzedaży", method)

    def test_ai_api_settings_keep_editable_privacy_controls_and_polish_response(self):
        start = self.source.index("  renderAiApiSettings(")
        end = self.source.index("  collectAiApiDraft(", start)
        method = self.source[start:end]
        for text in (
            "Walidacja odpowiedzi",
            "Format odpowiedzi poprawny",
            "Wysyłaj tylko dane godzinowe",
            "Usuń nazwy encji i urządzeń",
            "Nie wysyłaj dokładnej lokalizacji",
            "Maksymalny zakres historii",
            "odpowiedzi po polsku",
        ):
            self.assertIn(text, self.source)
        self.assertNotIn("checked disabled", method)
        self.assertNotIn("last_analysis_locale", method)

    def test_charging_purpose_uses_only_canonical_optimizer_values(self):
        start = self.source.index("  renderAiChargeProfile(")
        end = self.source.index("  renderAiGeneralSettings(", start)
        method = self.source[start:end]
        for value in ("mixed", "sale", "home", "reserve"):
            self.assertIn(f'["{value}"', method)
        for legacy in ("home_reserve", "morning_sale", "evening_sale", "both_sales", "cheap_home"):
            self.assertNotIn(f'["{legacy}"', method)

    def test_quality_card_explains_confidence_components(self):
        start = self.source.index("  renderAiQualityCard(")
        end = self.source.index("  renderAiPlanDay(", start)
        method = self.source[start:end]
        for key in (
            "prices", "solcast", "learning", "load_profile",
            "pv_profile", "entities", "soc", "tariff_osd",
        ):
            self.assertIn(f'{key}:', method)
        self.assertIn("Pewność końcowa planu", method)
        self.assertIn("Pewność planu dzisiaj", method)
        self.assertIn("Pewność planu jutro", method)
        self.assertIn("aiFormatPercent", method)
        self.assertIn("aiQualityCoverage", method)
        self.assertNotIn("quality.today_sell_prices || 0", method)
        self.assertNotIn("quality.osd_hours || 0", method)
        self.assertNotIn('`${this.aiFormatNumber(confidenceComponents[key], 0)}%`', method)
        self.assertNotIn("Status planu / wykonania", method)
        self.assertIn("Status propozycji", method)
        self.assertIn("Status realizacji profilu", method)


if __name__ == "__main__":
    unittest.main()

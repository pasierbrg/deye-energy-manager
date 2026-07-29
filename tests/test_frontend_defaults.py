from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CARD_PATHS = (
    ROOT / "custom_components" / "deye_energy_manager" / "www" / "deye-energy-manager-card.js",
    ROOT / "www" / "deye-energy-manager-card.js",
)


def extract_method(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(source)):
        character = source[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in ('"', "'", "`"):
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Nie znaleziono końca metody: {signature}")


class FrontendDefaultRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [path.read_text(encoding="utf-8") for path in CARD_PATHS]

    def test_distributed_card_copies_are_identical(self):
        self.assertEqual(CARD_PATHS[0].read_bytes(), CARD_PATHS[1].read_bytes())

    def test_apply_defaults_uses_one_backend_service_call_only(self):
        method = extract_method(self.sources[0], "async applyDefaultValues()")
        self.assertEqual(method.count("this.callService("), 1)
        self.assertIn(
            'this.callService("deye_energy_manager", "restore_defaults", {})',
            method,
        )
        for forbidden in (
            "select_option",
            "set_value",
            "default_work_mode",
            "default_sell_power",
            "default_discharge_current",
            "default_charge_current",
            "default_grid_charge_current",
            "Zero Export To Load",
            "numberState(",
        ):
            self.assertNotIn(forbidden, method)

    def test_apply_defaults_blocks_duplicates_and_reports_all_states(self):
        method = extract_method(self.sources[0], "async applyDefaultValues()")
        for required in (
            "if (this._defaultsApplying) return false",
            "Stosowanie ustawień domyślnych…",
            "Zastosowano ustawienia domyślne",
            "Nie udało się potwierdzić pełnego zestawu ustawień domyślnych",
        ):
            self.assertIn(required, method)
        self.assertIn("data-default-action", self.sources[0])
        self.assertIn("button.disabled = this._defaultsApplying", self.sources[0])

    def test_stop_manager_reuses_the_same_backend_path(self):
        method = extract_method(self.sources[0], "async stopManager()")
        self.assertIn("return this.applyDefaultValues()", method)
        self.assertNotIn("callService", method)


    def test_resume_manager_uses_dedicated_backend_service(self):
        method = extract_method(self.sources[0], "async resumeManager()")
        self.assertEqual(method.count("this.callService("), 1)
        self.assertIn('this.callService("deye_energy_manager", "resume_manager", {})', method)
        self.assertIn("data-resume-manager", self.sources[0])
        self.assertIn("SCHEDULE APPLY ERROR", self.sources[0])

    def test_ai_dialog_contains_approved_navigation_and_controls(self):
        source = self.sources[0]
        for required in (
            "Przegląd",
            "Proponowane zmiany",
            "Plan na dziś",
            "Plan na jutro",
            "Plan energii 48h",
            "Jakość danych",
            "Zaznacz wszystkie",
            "Odznacz wszystkie",
            "Pełne 24h",
            "save_future_plan",
            "cancel_future_plan",
            "Produkcja rzeczywista",
            "Prognoza Solcast",
            "Prognoza skorygowana",
            "Przedział prognozy",
            "data-ai-chart-point",
            "data-ai-weather-mode",
            "aiReadableEnergyChart",
            "aiReadableDayChart",
            "ai-crisp-weather-grid",
            "data-ai-chart-series",
            "ai-readable-weather",
            "ai-status-sell",
            "ai-status-charge",
            "ai-status-tariff",
        ):
            self.assertIn(required, source)
        self.assertNotIn(">P50<", source)

    def test_energy_flow_panel_keeps_desktop_layout_without_media_queries(self):
        method = extract_method(self.sources[0], "energyFlowPanel()")
        self.assertNotIn("@media", method)
        self.assertNotIn("flow-svg{display:none", method)
        self.assertIn(".flow-tile-pv{grid-column:1;grid-row:1", method)
        self.assertIn(".flow-tile-grid{grid-column:1;grid-row:1", method)
        self.assertIn(".flow-tile-battery{grid-column:3;grid-row:1", method)
        self.assertIn(".flow-tile-home{grid-column:3;grid-row:1", method)
        self.assertIn(".flow-inverter{grid-column:2;grid-row:1", method)
        self.assertIn(".flow-wrapper{", self.sources[0])
        self.assertIn(".flow-scaler{", self.sources[0])
        self.assertIn("scaleFlowPanel()", self.sources[0])
        self.assertIn(".dialog-host{", self.sources[0])

    def test_dashboard_has_common_scaling_logic(self):
        method = extract_method(self.sources[0], "scaleFlowPanel() {")
        self.assertIn("const baseWidth = parseFloat(scaler.dataset.baseWidth) || 1116", method)
        self.assertIn("Math.min(1, Math.max(available / baseWidth, 0.2))", method)
        self.assertIn("scaler.style.transform", method)
        self.assertIn("wrapper.style.height", method)

    def test_update_flow_lines_uses_dynamic_geometry(self):
        method = extract_method(self.sources[0], "updateFlowLines() {")
        self.assertIn("const scaler = this.querySelector(\".flow-scaler\");", method)
        self.assertIn("parseFloat(scaler?.dataset.tileWidth) || 230", method)
        self.assertIn("parseFloat(scaler?.dataset.tileGap) || 0", method)
        self.assertIn("parseFloat(scaler?.dataset.inverterWidth) || 640", method)
        self.assertIn("path.setAttribute(\"d\", d);", method)

    def test_energy_flow_panel_matches_reference_2(self):
        method = extract_method(self.sources[0], "energyFlowPanel()")
        # No big arrow markers
        self.assertNotIn("marker-end", method)
        self.assertNotIn("markerWidth", method)
        # Smooth dashed-line animation instead of jumping SVG dots
        self.assertIn("@keyframes flowDash", method)
        self.assertIn("stroke-dasharray:4 20", method)
        # Energy panel uses configurable layout
        self.assertIn("const layout = this.effectiveLayout();", method)
        self.assertIn("const tileWidth = layout.energy_tile_width;", method)
        self.assertIn("const inverterWidth = Math.round(640 * inverterScale);", method)
        self.assertIn("const boardWidth = tileWidth * 2 + inverterWidth + tileGap * 2;", method)
        self.assertIn("animation:flowDash ${flowDuration}s linear infinite", method)
        self.assertIn("grid-template-columns:${tileWidth}px ${inverterWidth}px ${tileWidth}px", method)
        self.assertIn(".flow-tile{width:${tileWidth}px", method)
        # No power values next to lines
        self.assertNotIn("flow-value-pv", method)
        self.assertNotIn("flow-value-bat", method)
        self.assertNotIn("flow-value-grid", method)
        self.assertNotIn("flow-value-home", method)
        self.assertNotIn('data-live="pv-line-value"', method)
        self.assertNotIn('data-live="battery-line-value"', method)
        self.assertNotIn('data-live="grid-line-value"', method)
        self.assertNotIn('data-live="load-line-value"', method)
        # No duplicated total row in PV tile
        self.assertNotIn("Razem:", method)
        # Sold-today tile under inverter, single line kWh / PLN, no legend
        self.assertIn("Sprzedano dzisiaj", method)
        self.assertIn("flow-sold-tile", method)
        self.assertIn('data-live="sold-today-line"', method)
        self.assertNotIn("flow-legend", method)
        self.assertNotIn("Falownik Deye", method)
        # Centered layout with tiles in correct corners
        self.assertIn(".flow-tile-pv{grid-column:1;grid-row:1", method)
        self.assertIn(".flow-tile-grid{grid-column:1;grid-row:1", method)
        self.assertIn(".flow-tile-battery{grid-column:3;grid-row:1", method)
        self.assertIn(".flow-tile-home{grid-column:3;grid-row:1", method)
        self.assertIn(".flow-inverter{grid-column:2;grid-row:1", method)
        # New SVG icons
        self.assertIn('this.iconSvg("pv2")', method)
        self.assertIn('this.iconSvg("grid2")', method)
        self.assertIn('this.iconSvg("battery2")', method)
        self.assertIn('this.iconSvg("home2")', method)
        # Bottom bar separators and 4 sections
        self.assertIn(".flow-status-tile{", method)
        self.assertIn("border-right", method)
        self.assertIn("grid-template-columns:repeat(4,1fr)", method)
        # Mode colors aligned with schedule
        self.assertIn("mode-selling", method)
        self.assertIn("mode-normal", method)
        self.assertIn("mode-charge", method)
        self.assertIn("mode-disabled", method)
        self.assertIn('data-live="decision-reason"', method)
        # External container is centered and capped
        self.assertIn(".dem-v073{", self.sources[0])
        self.assertIn("max-width:1280px", self.sources[0])
        self.assertIn("margin:0 auto", self.sources[0])

    def test_deye_mode_shows_raw_system_work_mode(self):
        source = self.sources[0]
        method = extract_method(source, "energyFlowPanel()")
        # Must show the raw select value, not the translated manager label
        self.assertIn('data-live="deye-mode"', method)
        self.assertNotIn('${this.slotModeLabel(currentMode)}', method)
        update = extract_method(source, "updateDynamicValues() {")
        self.assertIn("data-live='deye-mode'", update)
        self.assertIn("currentModeValue", update)
        self.assertNotIn("slotModeLabel(currentModeValue)", update)

    def test_energy_flow_panel_updates_all_detailed_fields(self):
        source = self.sources[0]
        self.assertIn("data-live='pv1-power'", source)
        self.assertIn("data-live='pv1-volts'", source)
        self.assertIn("data-live='pv1-amps'", source)
        self.assertIn("data-live='pv2-power'", source)
        self.assertIn("data-live='pv2-volts'", source)
        self.assertIn("data-live='pv2-amps'", source)
        self.assertIn("data-live='grid-l1-power'", source)
        self.assertIn("data-live='grid-l1-volt'", source)
        self.assertIn("data-live='grid-l2-power'", source)
        self.assertIn("data-live='grid-l2-volt'", source)
        self.assertIn("data-live='grid-l3-power'", source)
        self.assertIn("data-live='grid-l3-volt'", source)
        self.assertIn("data-live='grid-bought'", source)
        self.assertIn("data-live='grid-sold'", source)
        self.assertIn("data-live='grid-frequency'", source)
        self.assertIn("data-live='battery-voltage'", source)
        self.assertIn("data-live='battery-current'", source)
        self.assertIn("data-live='battery-temp'", source)
        self.assertIn("data-live='battery-charge-daily'", source)
        self.assertIn("data-live='battery-discharge-daily'", source)
        self.assertIn("data-live='load-l1-power'", source)
        self.assertIn("data-live='load-l2-power'", source)
        self.assertIn("data-live='load-l3-power'", source)
        self.assertIn("data-live='inverter-temp'", source)
        self.assertIn("data-live='pv-daily'", source)
        self.assertIn("data-live='load-daily'", source)
        update = extract_method(source, "updateDynamicValues() {")
        for key in [
            "pv1-power", "pv1-volts", "pv1-amps", "pv2-power", "pv2-volts", "pv2-amps",
            "grid-l1-power", "grid-l1-volt", "grid-l2-power", "grid-l2-volt",
            "grid-l3-power", "grid-l3-volt", "grid-bought", "grid-sold", "grid-frequency",
            "battery-voltage", "battery-current", "battery-temp",
            "battery-charge-daily", "battery-discharge-daily",
            "load-l1-power", "load-l2-power", "load-l3-power",
            "inverter-temp", "pv-daily", "load-daily", "sold-today-line",
        ]:
            self.assertIn(f"data-live='{key}'", update)

    def test_documentation_uses_current_card_cache_revision(self):
        for name in ("README.md", "INSTALL_PL.md"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("deye-energy-manager-card.js?v=21", source)
            self.assertNotIn("deye-energy-manager-card.js?v=10", source)
            self.assertNotIn("deye-energy-manager-card.js?v=09", source)
            self.assertNotIn("deye-energy-manager-card.js?v=08", source)
            self.assertNotIn("deye-energy-manager-card.js?v=07", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0780", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0778", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0777", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0774", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0773", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0772", source)
            self.assertNotIn("deye-energy-manager-card.js?v=0765", source)

    def test_dashboard_yaml_includes_layout_examples(self):
        yaml_path = ROOT / "dashboard" / "energy_manager.yaml"
        self.assertTrue(yaml_path.exists(), "dashboard/energy_manager.yaml must exist")
        source = yaml_path.read_text(encoding="utf-8")
        for key in (
            "layout:",
            "layout_mode:",
            "sections:",
            "dashboard_width:",
            "mobile:",
            "energy_tile_width:",
            "energy_tile_gap:",
            "inverter_scale:",
            "flow_animation_speed:",
            "prices_ratio:",
            "buy_prices_ratio:",
            "solcast_ratio:",
        ):
            self.assertIn(key, source)

    def test_card_has_explicit_direct_edit_path_for_physical_tou_entities(self):
        source = self.sources[0]
        self.assertIn("data-open-tou", source)
        tou_dialog = extract_method(source, "renderDialog(slots, touStarts)")
        for required in (
            "this.timeInput(tou.",
            "this.numberInput(tou.",
            "this.pill(tou.grid)",
        ):
            self.assertIn(required, tou_dialog)

    def test_unconfirmed_logical_tou_soc_never_renders_as_zero(self):
        source = self.sources[0]
        self.assertIn("touSocInput(entityId)", source)
        self.assertIn('placeholder="wymaga potwierdzenia"', source)
        dialog = extract_method(source, "renderDialog(slots, touStarts)")
        self.assertIn("this.touSocInput(entities.touSoc)", dialog)
        self.assertNotIn("this.numberInput(entities.touSoc", dialog)

    def test_mapping_distinguishes_charge_from_grid_permission(self):
        source = self.sources[0]
        self.assertIn("chargeMode: isCharge", source)
        self.assertIn('item.chargeMode ? "Charge" : "Limit SOC"', source)

    def test_charge_profile_save_uses_one_backend_service_only(self):
        method = extract_method(self.sources[0], "async saveChargeProfile()")
        self.assertEqual(method.count("this.callService("), 1)
        self.assertIn(
            'this.callService("deye_energy_manager", "save_charge_profile", values)',
            method,
        )
        for forbidden in (
            "number.set_value",
            "switch.turn_on",
            "switch.turn_off",
            "select.select_option",
            "setNumber(",
            "turnSwitch(",
            "setSelect(",
        ):
            self.assertNotIn(forbidden, method)
        # The save must not block when helper entities are missing; it uses a
        # pending state that is confirmed by manager_status.
        self.assertNotIn("Brak encji profilu", method)
        self.assertIn("this._chargeProfilePending", method)
        self.assertIn("this._chargeProfileDraft = {}", method)
        self.assertIn("this._chargeProfileGridDraft = null", method)

    def test_charge_current_input_keeps_draft_and_physical_range_without_zero_fallback(self):
        method = extract_method(self.sources[0], "chargeProfileInput(name, entityId, unit = \"\")")
        for required in (
            "this._chargeProfileDraft",
            '["unknown", "unavailable", ""]',
            "entity?.attributes?.min",
            "entity?.attributes?.max",
            "entity?.attributes?.step",
            'type="number"',
            'data-charge-profile-number=',
            "fallback.min",
            "fallback.max",
        ):
            self.assertIn(required, method)
        for forbidden in ("?? 0", "|| 0", 'value="0"'):
            self.assertNotIn(forbidden, method)

    def test_charge_profile_draft_survives_input_change_and_rerender(self):
        source = self.sources[0]
        self.assertIn(
            "this._chargeProfileDraft[el.dataset.chargeProfileNumber] = el.value",
            source,
        )
        self.assertIn('el.addEventListener("input", saveDraft)', source)
        self.assertIn('el.addEventListener("change", saveDraft)', source)
        self.assertIn(
            'this.chargeProfileInput("charge_current", this.entity("number", "charge_profile_charge_current"), "A")',
            source,
        )

    def test_charge_profile_form_falls_back_to_persisted_manager_status(self):
        source = self.sources[0]
        self.assertIn('this.entity("sensor", "manager_status")', source)
        self.assertIn("attributes?.charge_profile", source)
        self.assertIn("this.chargeProfileStoredValues()[profileKey]", source)
        self.assertIn(
            "this.chargeProfileStoredValues().grid_charge_enabled",
            source,
        )

    def test_normal_profile_form_uses_dedicated_backend_service(self):
        method = extract_method(self.sources[0], "async saveNormalProfile()")
        self.assertEqual(method.count("this.callService("), 1)
        self.assertIn(
            'this.callService("deye_energy_manager", "save_normal_profile", values)',
            method,
        )
        self.assertIn("physical_work_mode", method)
        self.assertIn("tou_soc", method)

    def test_normal_profile_form_falls_back_to_persisted_manager_status(self):
        source = self.sources[0]
        self.assertIn('this.entity("sensor", "manager_status")', source)
        self.assertIn("attributes?.normal_profile", source)
        self.assertIn("this.normalProfileStoredValues()[profileKey]", source)

    def test_normal_profile_input_never_disabled_and_uses_fallback_ranges(self):
        method = extract_method(self.sources[0], "normalProfileInput(name, entityId, unit = \"\")")
        self.assertNotIn("disabled", method)
        self.assertIn("fallback", method)
        self.assertIn("min", method)
        self.assertIn("max", method)
        self.assertIn("step", method)

    def test_normal_profile_mode_prefers_draft_then_stored_then_entity(self):
        method = extract_method(self.sources[0], "normalProfileMode()")
        self.assertIn("this._normalProfileDraft.physical_work_mode", method)
        self.assertIn("this.normalProfileStoredValues().physical_work_mode", method)
        self.assertIn('this.entity("select", "normal_profile_mode")', method)

    def test_normal_profile_mode_select_has_placeholder(self):
        source = self.sources[0]
        dialog = extract_method(source, "renderDialog(slots, touStarts)")
        self.assertIn("this.normalProfileMode()", dialog)
        self.assertIn('["", "-- wybierz --"]', dialog)
        self.assertIn('["Zero Export To Load", "Zero Export To Load"]', dialog)
        self.assertIn('["Zero Export To CT", "Zero Export To CT"]', dialog)

    def test_normal_profile_save_rejects_empty_values(self):
        method = extract_method(self.sources[0], "async saveNormalProfile()")
        self.assertIn('raw === ""', method)
        self.assertIn('this.failSave("normal_profile"', method)

    def test_normal_profile_reload_button_calls_apply_schedule_patch_with_force_flag(self):
        source = self.sources[0]
        method = extract_method(source, "async reloadNormalProfileSlot(slotKey)")
        self.assertIn('"apply_schedule_patch"', method)
        self.assertIn('force_copy_normal_profile: true', method)
        self.assertIn('"Normalna Praca"', method)
        self.assertIn(
            'this.reloadNormalProfileSlot(el.dataset.reloadNormalProfile)',
            source,
        )

    def test_charge_profile_reload_button_calls_apply_schedule_patch_with_force_flag(self):
        source = self.sources[0]
        method = extract_method(source, "async reloadChargeProfileSlot(slotKey)")
        self.assertIn('"apply_schedule_patch"', method)
        self.assertIn('force_copy_charge_profile: true', method)
        self.assertIn('"Charge"', method)
        self.assertIn('data-reload-charge-profile', source)
        self.assertIn(
            'this.reloadChargeProfileSlot(el.dataset.reloadChargeProfile)',
            source,
        )

    def test_charge_profile_save_uses_pending_until_manager_status_confirms(self):
        method = extract_method(self.sources[0], "async saveChargeProfile()")
        self.assertIn("this._chargeProfilePending = { ...values }", method)
        self.assertIn("checkChargeProfilePending()", self.sources[0])
        self.assertIn("_chargeProfilePendingMatches", self.sources[0])

    def test_normal_profile_numeric_prefers_stored_over_entity(self):
        method = extract_method(self.sources[0], "normalProfileNumericValue(entitySuffix, profileKey)")
        # Draft -> pending -> stored -> entity, per the specification.
        self.assertIn("this.normalProfileStoredValues()[profileKey]", method)
        stored_index = method.index("this.normalProfileStoredValues()[profileKey]")
        entity_index = method.index('this.entity("number", entitySuffix)')
        self.assertLess(stored_index, entity_index)

    def test_charge_profile_numeric_prefers_stored_over_entity(self):
        method = extract_method(self.sources[0], "chargeProfileNumericValue(entitySuffix, profileKey)")
        self.assertIn("this.chargeProfileStoredValues()[profileKey]", method)
        stored_index = method.index("this.chargeProfileStoredValues()[profileKey]")
        entity_index = method.index('this.entity("number", entitySuffix)')
        self.assertLess(stored_index, entity_index)

    def test_settings_menu_and_forms_follow_the_approved_layout(self):
        source = self.sources[0]
        dialog = extract_method(source, "renderDialog(slots, touStarts)")
        self.assertIn('tabButton("defaults", "Ustawienia Tryb', dialog)
        self.assertNotIn('tabButton("charge"', dialog)
        defaults_heading = dialog.index("Ustawienia domy")
        charge_heading = dialog.index("Ustawienia ", defaults_heading + 1)
        self.assertGreater(charge_heading, defaults_heading)
        self.assertIn("data-save-default-settings", dialog)
        self.assertIn("data-save-charge-profile", dialog)

    def test_default_and_charge_forms_have_independent_backend_calls(self):
        default_method = extract_method(self.sources[0], "async saveDefaultSettings()")
        charge_method = extract_method(self.sources[0], "async saveChargeProfile()")
        self.assertIn('"save_default_settings"', default_method)
        self.assertNotIn('"save_charge_profile"', default_method)
        self.assertIn('"save_charge_profile"', charge_method)
        self.assertNotIn('"save_default_settings"', charge_method)

    def test_charge_slot_is_editable_and_profile_is_only_a_template(self):
        source = self.sources[0]
        dialog = extract_method(source, "renderDialog(slots, touStarts)")
        for required in (
            "numberInput(entities.chargeCurrent",
            "numberInput(entities.dischargeCurrent",
            "numberInput(entities.gridChargeCurrent",
            "touSocInput(entities.touSoc)",
            "pill(entities.chargeEnabled)",
            "Wartości początkowe skopiowano",
        ):
            self.assertIn(required, dialog)
        self.assertIn("pill(entities.chargeEnabled)", dialog)
        self.assertIn("const isSelling", dialog)
        self.assertIn("const socField", dialog)
        self.assertEqual(dialog.count("${socField}"), 1)
        self.assertIn('this.pill(null, "NIE")', dialog)

    def test_slot_mode_selector_contains_exactly_three_supported_modes(self):
        method = extract_method(self.sources[0], "slotWorkModes()")
        for mode in (
            "Selling First",
            "Normalna Praca",
            "Charge",
        ):
            self.assertIn(mode, method)
        self.assertNotIn("Zero Export To Load", method)
        self.assertNotIn("Zero Export To CT", method)

    def test_slot_modes_use_polish_display_labels(self):
        source = self.sources[0]
        mode_meta = extract_method(source, "modeMeta(mode, enabled = true)")
        self.assertIn('title: "Sprzeda\\u017c"', mode_meta)
        self.assertIn('title: "Normalna Praca"', mode_meta)
        self.assertIn('title: "\\u0141adowanie"', mode_meta)
        self.assertIn('title: "Wy\\u0142\\u0105czono"', mode_meta)
        self.assertIn('subtitle: "Normalny tryb pracy"', mode_meta)
        self.assertIn('subtitle: "Slot nieaktywny"', mode_meta)

    def test_slot_mode_selectors_map_technical_values_to_polish_labels(self):
        source = self.sources[0]
        self.assertIn("slotModeLabel(mode)", source)
        self.assertIn("slotModeOptions()", source)
        self.assertIn("this.slotModeLabel(option))", source)
        self.assertIn("this.slotModeOptions(), bulk.mode)", source)
        self.assertNotIn('this.rawSelect("multi-mode", this.slotWorkModes(), bulk.mode)', source)

    def test_zero_export_physical_modes_display_as_normal_operation(self):
        import re
        def norm(value):
            return re.sub(r"[^a-z0-9]", "", value.lower())
        mode_meta = extract_method(self.sources[0], "modeMeta(mode, enabled = true)")
        self.assertIn('normalized.includes("zeroexport")', mode_meta)
        self.assertIn('normalized.includes("normal")', mode_meta)
        self.assertNotIn('normalized.includes("zero export")', mode_meta)
        self.assertNotIn('normalized.includes("normalna praca")', mode_meta)
        self.assertIn('title: "Normalna Praca"', mode_meta)
        self.assertIn('cls: "normal"', mode_meta)
        for raw in ("Zero Export To Load", "Zero Export To CT", "Normalna Praca"):
            self.assertTrue("normal" in norm(raw) or "zeroexport" in norm(raw), f"{raw} nie mapuje się na Normalna Praca")
        label_method = extract_method(self.sources[0], "slotModeLabel(mode)")
        self.assertIn('normalized.includes("zeroexport")', label_method)
        self.assertIn('normalized.includes("normal")', label_method)
        self.assertIn('return "Normalna Praca"', label_method)

    def test_normal_profile_settings_keep_physical_mode_names(self):
        source = self.sources[0]
        dialog = extract_method(source, "renderDialog(slots, touStarts)")
        self.assertIn('this.rawSelect("normal-profile-mode",', dialog)
        self.assertIn('["Zero Export To Load", "Zero Export To Load"]', dialog)
        self.assertIn('["Zero Export To CT", "Zero Export To CT"]', dialog)

    def test_disabled_state_is_not_a_work_mode_option(self):
        source = self.sources[0]
        dialog = extract_method(source, "renderDialog(slots, touStarts)")
        self.assertIn("selectInput(entities.mode", dialog)
        self.assertNotIn("Wy\\u0142\\u0105czono", dialog)

    def test_schedule_table_always_displays_stored_grid_permission_and_current(self):
        source = self.sources[0]
        self.assertIn('const gridChargeLabel = isChargeMode ? (gridCharge ? "tak" : "nie") : "nie dotyczy"', source)
        self.assertIn('class="pill ${gridChargeClass}"', source)
        self.assertNotIn("this.pill(null, gridChargeLabel)", source)
        self.assertIn("${gridChargeCurrent} A", source)
        self.assertNotIn(
            'isCharge ? (slot.chargeEnabled === "on" ? "tak" : "nie") : "nie dotyczy"',
            source,
        )

    def test_settings_dialog_scrolls_on_desktop_tablet_and_phone(self):
        source = self.sources[0]
        self.assertIn(".settings-content{min-width:0;overflow:auto", source)
        self.assertIn("@media(max-width:980px)", source)
        self.assertIn(".settings-layout{grid-template-columns:1fr", source)
        self.assertIn("@media(max-width:620px)", source)
        self.assertIn(".settings-content{padding:9px}", source)

    def test_diagnostics_show_logical_and_physical_soc_separately(self):
        method = extract_method(self.sources[0], "renderDiagnostics(slots)")
        for required in (
            "active_slot_control",
            "physical_tou",
            "minimum_sell_soc",
            "tou_soc",
            "charge_profile_target_soc",
            "effective_tou_soc",
            "physical_soc_actual",
            "grid_charge_expected",
            "grid_charge_actual",
            "currents",
        ):
            self.assertIn(required, method)

    def test_layout_config_has_defaults_and_mobile_overrides(self):
        source = self.sources[0]
        method = extract_method(source, "layoutConfig() {")
        for required in (
            'layout_mode: "auto"',
            "dashboard_width: 1280",
            "center_dashboard: true",
            "fit_to_width: false",
            "allow_horizontal_scroll: false",
            "prices_ratio: 0.80",
            "buy_prices_ratio: 0.80",
            "solcast_ratio: 1.40",
            "energy_tile_width: 230",
            "energy_tile_gap: 28",
            "inverter_scale: 1",
            "flow_animation_speed: 6",
            'mobile: {',
            'mode: "auto"',
            "mobile_breakpoint: 768",
        ):
            self.assertIn(required, method)
        # Validation helpers
        self.assertIn("asString(", method)
        self.assertIn("asNumber(", method)
        self.assertIn("asBool(", method)
        self.assertIn("clamp(", method)

    def test_render_uses_layout_config_for_dashboard(self):
        source = self.sources[0]
        render = extract_method(source, "renderV073()")
        self.assertIn("const layout = this.effectiveLayout();", render)
        self.assertIn(r"dashStyle.push(`max-width:${layout.dashboard_width}px`)", render)
        self.assertIn('if (layout.center_dashboard) dashStyle.push("margin:0 auto")', render)
        self.assertIn('if (layout.fit_to_width) dashStyle.push("width:100%")', render)
        self.assertIn('if (layout.allow_horizontal_scroll) {', render)
        self.assertIn('dashStyle.push("overflow-x:auto")', render)
        self.assertIn('dashStyle.push("overflow-x:hidden")', render)
        self.assertIn('layout.is_mobile ? "grid-template-columns:minmax(0,1fr)"', render)
        self.assertIn(r"grid-template-columns:${layout.prices_ratio}fr ${layout.buy_prices_ratio}fr ${layout.solcast_ratio}fr", render)
        self.assertIn('if (layout.layout_mode === "grid" && layout.grid_columns)', render)
        self.assertIn("const showStatus = isSingle ? layout.section === \"status_energy\" : layout.sections.status_energy;", render)
        self.assertIn("if (isSingle && [\"ai\", \"settings\"].includes(layout.section) && !this._dialog)", render)
        self.assertIn('<div class="dem-v073" style="${demStyle}">', render)
        self.assertIn("${statusSection}", render)
        self.assertIn("${infoGridSection}", render)
        # Mobile-safe min-width/max-width reset
        self.assertIn(".dem-v073>*,.info-grid>.panel,.panel,.schedule-shell,.sales-panel{min-width:0;max-width:100%;box-sizing:border-box}", render)
        self.assertIn("${scheduleSection}", render)
        self.assertIn("${salesSection}", render)

    def test_dialog_host_renders_outside_dashboard_container(self):
        source = self.sources[0]
        render = extract_method(source, "renderV073()")
        # Dialog host must be a sibling of .dem-v073, not inside it.
        self.assertIn('</div>\n          <div class="dialog-host">${this.renderDialog(slots, touStarts)}</div>', render)
        self.assertIn("this._lastSlots = slots;", render)
        self.assertIn("this._lastTouStarts = touStarts;", render)

    def test_render_dialog_only_updates_dialog_independently(self):
        source = self.sources[0]
        method = extract_method(source, "renderDialogOnly() {")
        for required in (
            "if (!this._lastSlots) return;",
            'const host = this.querySelector(".dialog-host");',
            "host.innerHTML = this.renderDialog(this._lastSlots, this._lastTouStarts);",
            "this.bindDialogControls(this._lastSlots);",
            "this.restoreScrollPositions();",
        ):
            self.assertIn(required, method)

    def test_effective_layout_reports_mobile_flag(self):
        source = self.sources[0]
        method = extract_method(source, "effectiveLayout() {")
        self.assertIn("layout.is_mobile = isMobile;", method)

    def test_desktop_info_grid_uses_yaml_ratios(self):
        source = self.sources[0]
        render = extract_method(source, "renderV073()")
        # Desktop path keeps proportional ratios
        self.assertIn(r"grid-template-columns:${layout.prices_ratio}fr ${layout.buy_prices_ratio}fr ${layout.solcast_ratio}fr", render)
        # Mobile path collapses to single column
        self.assertIn('layout.is_mobile ? "grid-template-columns:minmax(0,1fr)"', render)

    def test_allow_horizontal_scroll_false_hides_global_overflow(self):
        source = self.sources[0]
        render = extract_method(source, "renderV073()")
        self.assertIn('dashStyle.push("overflow-x:hidden")', render)

    def test_local_scroll_containers_preserved(self):
        source = self.sources[0]
        # Schedule table scrolls inside its own card (mobile media query turns overflow-x:auto)
        self.assertIn(".schedule-table-card{border:1px solid rgba(107,157,182,.28);border-radius:8px;overflow:hidden", source)
        self.assertIn(".schedule-table-card{overflow-x:auto", source)
        self.assertIn(".schedule-table{min-width:", source)
        # Solcast days can scroll horizontally on mobile
        self.assertIn(".solcast-days{display:grid;grid-template-columns:repeat(7,minmax(58px,1fr))", source)
        self.assertIn(".solcast-days{display:flex;gap:6px;overflow-x:auto", source)
        # Price table scrolls inside its own card
        self.assertIn(".price-scroll{height:auto;flex:0 0 auto;min-height:0;overflow:visible", source)
        self.assertIn(".price-scroll{height:260px;overflow:auto", source)

    def test_layout_mode_grid_columns_one_on_mobile(self):
        source = self.sources[0]
        render = extract_method(source, "renderV073()")
        self.assertIn('grid-template-columns:repeat(${layout.grid_columns},minmax(0,1fr))', render)

    def test_dialog_host_and_dashboard_render_unchanged(self):
        source = self.sources[0]
        render = extract_method(source, "renderV073()")
        self.assertIn('</div>\n          <div class="dialog-host">${this.renderDialog(slots, touStarts)}</div>', render)
        self.assertIn("${statusSection}", render)
        self.assertIn("${infoGridSection}", render)
        self.assertIn("${scheduleSection}", render)
        self.assertIn("${salesSection}", render)


if __name__ == "__main__":
    unittest.main()

const fs = require("fs");
const path = require("path");

global.window = {
  setTimeout: (fn, ms) => (ms >= 1000 ? 1 : setTimeout(fn, ms)),
  clearTimeout: (id) => { if (id && id !== 1) clearTimeout(id); },
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
  addEventListener: () => {},
  removeEventListener: () => {},
};
global.requestAnimationFrame = global.window.requestAnimationFrame;
global.cancelAnimationFrame = global.window.cancelAnimationFrame;
global.document = { scrollingElement: {}, documentElement: {}, body: {} };
class HTMLElement {}
global.HTMLElement = HTMLElement;
global.customElements = { define: () => {} };

const componentCard = path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js");
const rootCard = path.join(__dirname, "..", "www", "deye-energy-manager-card.js");
eval(fs.readFileSync(componentCard, "utf8") + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
function assertTrue(value, message) {
  if (!value) { failures += 1; console.error(`FAIL: ${message}`); }
}
function assertEqual(actual, expected, message) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures += 1;
    console.error(`FAIL: ${message}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
  }
}

const KEY = "06_07";
const LABEL = "06:00-07:00";
const BACKEND_MANAGER_MODES = ["Normalna Praca", "Sprzedaż", "Ładowanie"];
function originalSlot(overrides = {}) {
  return {
    enabled: true,
    mode: "Sprzedaż",
    physical_work_mode: null,
    sell_power: 4000,
    discharge_current: 100,
    charge_enabled: false,
    charge_current: 30,
    grid_charge_current: 40,
    minimum_sell_soc: 35,
    tou_soc: 15,
    min_sell_price: 0.5,
    ...overrides,
  };
}

function entityId(domain, suffix) { return `${domain}.deye_energy_manager_${suffix}`; }
function makeCard(options = {}) {
  const slot = originalSlot(options.slot);
  const attrs = {
    control_enabled: options.controlEnabled !== false,
    control_status: options.controlEnabled === false ? "Wyłączone" : "Aktywne",
    schedule_slots: { [KEY]: { ...slot } },
    normal_profile: {
      physical_work_mode: "Zero Export To CT",
      sell_power: 3000,
      discharge_current: 80,
      charge_current: 25,
      grid_charge_current: 35,
      tou_soc: 45,
    },
    charge_profile: {
      grid_charge_enabled: false,
      charge_current: 60,
      discharge_current: 70,
      grid_charge_current: 50,
      target_soc: 85,
    },
  };
  const calls = [];
  let failNext = options.failNext === true;
  const states = {
    [entityId("sensor", "manager_status")]: { state: "Aktywny", attributes: attrs },
    [entityId("switch", "control")]: { state: options.controlEnabled === false ? "off" : "on", attributes: {} },
  };
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = {
    states,
    services: { deye_energy_manager: { apply_schedule_patch: true } },
    callService: async (domain, service, data) => {
      calls.push({ domain, service, data });
      if (failNext) { failNext = false; throw new Error("Awaria zapisu Harmonogramu"); }
      if (domain === "deye_energy_manager" && service === "apply_schedule_patch" && options.autoRefresh !== false) {
        const [patch] = JSON.parse(data.data);
        if (patch.mode !== undefined && !BACKEND_MANAGER_MODES.includes(patch.mode)) {
          throw new Error(`Unsupported slot mode: ${patch.mode}`);
        }
        Object.entries(patch).forEach(([field, value]) => { if (field !== "slot_key") attrs.schedule_slots[KEY][field] = value; });
      }
    },
  };
  card.querySelector = () => null;
  card.querySelectorAll = () => [];
  card.captureScrollPositions = () => {};
  card.updateSaveIndicator = () => {};
  card.render = () => {};
  card.renderDialogOnly = () => {};
  card.openScheduleSlotEditor(KEY, LABEL);
  return { card, attrs, calls, setFailNext: () => { failNext = true; } };
}

function dialogHtml(card) { return card.renderDialog(card.scheduleSlots(), []); }
function change(card, field, value) { card.updateSlotDraftField(field, value); }
function servicePayload(calls) {
  const call = calls.find((item) => item.domain === "deye_energy_manager" && item.service === "apply_schedule_patch");
  return call ? JSON.parse(call.data.data) : null;
}

function test_schedule_slot_edit_does_not_save_on_field_change() {
  const { card, calls } = makeCard(); change(card, "sell_power", 5000);
  assertEqual(calls.length, 0, "field edit must not call a service");
}
function test_schedule_slot_edit_uses_local_draft() {
  const { card, attrs } = makeCard(); change(card, "sell_power", 5000);
  assertEqual(card._slotEditDraft.values.sell_power, 5000, "draft must change");
  assertEqual(attrs.schedule_slots[KEY].sell_power, 4000, "backend snapshot must remain unchanged");
}
function test_schedule_slot_hass_update_does_not_overwrite_dirty_draft() {
  const { card, attrs } = makeCard(); change(card, "sell_power", 5000);
  attrs.schedule_slots[KEY].sell_power = 4500;
  card.syncSlotEditorAfterHass();
  assertEqual(card._slotEditDraft.values.sell_power, 5000, "HA refresh must not overwrite draft");
}
function test_schedule_slot_dirty_comparison_normalizes_numeric_types() {
  const { card } = makeCard(); change(card, "sell_power", "4000");
  assertTrue(!card.slotEditDirty(), "numeric string and number must compare equal");
}
function test_schedule_slot_cancel_discards_all_changes() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card.cancelScheduleSlotEdit();
  assertTrue(card._slotEditDraft === null && card._slotEditOriginal === null, "cancel must clear original and draft");
}
function test_schedule_slot_cancel_performs_no_service_call() {
  const { card, calls } = makeCard(); change(card, "sell_power", 5000); card.cancelScheduleSlotEdit();
  assertEqual(calls.length, 0, "cancel must not call service");
}
function test_schedule_slot_reopen_after_cancel_uses_backend_state() {
  const { card, attrs } = makeCard(); change(card, "sell_power", 5000); card.cancelScheduleSlotEdit();
  attrs.schedule_slots[KEY].sell_power = 4200; card.openScheduleSlotEditor(KEY, LABEL);
  assertEqual(card._slotEditDraft.values.sell_power, 4200, "reopen must use current backend state");
}
async function test_schedule_slot_save_applies_all_changes_once() {
  const { card, calls } = makeCard(); change(card, "sell_power", 5000); change(card, "minimum_sell_soc", 30); change(card, "tou_soc", 20);
  await card.saveScheduleSlotDraft();
  const patch = servicePayload(calls)[0];
  assertEqual([patch.sell_power, patch.minimum_sell_soc, patch.tou_soc], [5000, 30, 20], "one patch must contain every change");
}
async function test_schedule_slot_save_uses_single_apply_schedule_patch_call() {
  const { card, calls } = makeCard(); change(card, "sell_power", 5000); change(card, "tou_soc", 20); await card.saveScheduleSlotDraft();
  assertEqual(calls.filter((item) => item.service === "apply_schedule_patch").length, 1, "save must call apply_schedule_patch once");
}
async function test_schedule_slot_save_triggers_single_mapping_recalculation() {
  const { card } = makeCard(); let applies = 0; card.applySchedulePatch = async () => { applies += 1; return false; };
  change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertEqual(applies, 1, "one logical save must enter backend patch path once");
}
async function test_schedule_slot_unchanged_save_performs_no_service_call() {
  const { card, calls } = makeCard(); await card.saveScheduleSlotDraft();
  assertEqual(calls.length, 0, "unchanged save must not call service");
}
async function test_schedule_slot_save_with_control_disabled_stays_local() {
  const { card, attrs } = makeCard({ controlEnabled: false }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertEqual(attrs.schedule_slots[KEY].sell_power, 5000, "disabled control must still save schedule locally");
}
async function test_schedule_slot_save_with_control_disabled_does_not_write_tou() {
  const { card, calls } = makeCard({ controlEnabled: false }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertTrue(!calls.some((item) => item.service === "set_tou_slot" || item.domain === "number" || item.domain === "switch" || item.domain === "select"), "disabled control save must not write inverter entities");
}
async function test_schedule_slot_save_with_control_disabled_shows_local_only_message() {
  const { card } = makeCard({ controlEnabled: false }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertTrue(card._saveMessage.includes("nie wysłano ich do falownika"), "local-only message must be shown");
}
async function test_schedule_slot_save_error_keeps_dialog_open() {
  const { card } = makeCard({ failNext: true }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertTrue(card._dialog?.key === KEY, "error must keep dialog open");
}
async function test_schedule_slot_save_error_keeps_draft() {
  const { card } = makeCard({ failNext: true }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertEqual(card._slotEditDraft.values.sell_power, 5000, "error must keep draft");
}
async function test_schedule_slot_save_error_reenables_save_button() {
  const { card } = makeCard({ failNext: true }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertTrue(!card._slotSaving && dialogHtml(card).includes("Zapisz"), "error must re-enable save");
}
async function test_schedule_slot_save_can_be_retried_after_error() {
  const { card, calls } = makeCard({ failNext: true }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft(); await card.saveScheduleSlotDraft();
  assertEqual(calls.filter((item) => item.service === "apply_schedule_patch").length, 2, "failed save must be retryable");
}
async function test_schedule_slot_success_refreshes_actual_state() {
  const { card, attrs } = makeCard(); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertEqual(attrs.schedule_slots[KEY].sell_power, 5000, "success must use refreshed backend state");
}
async function test_schedule_slot_success_clears_draft() {
  const { card } = makeCard(); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertTrue(card._slotEditDraft === null && card._slotEditOriginal === null, "success must clear draft and original");
}
async function test_schedule_slot_success_closes_dialog_after_backend_refresh() {
  const { card, attrs } = makeCard({ autoRefresh: false }); change(card, "sell_power", 5000); await card.saveScheduleSlotDraft();
  assertTrue(card._dialog !== null, "dialog must wait for backend refresh");
  attrs.schedule_slots[KEY].sell_power = 5000; card.syncSlotEditorAfterHass();
  assertTrue(card._dialog === null, "matching backend refresh must close dialog");
}
function test_schedule_slot_save_button_is_disabled_while_saving() {
  const { card } = makeCard(); card._slotSaving = true;
  assertTrue(dialogHtml(card).includes('data-save-slot-edit="1" disabled') && dialogHtml(card).includes("Zapisywanie…"), "saving button must be disabled");
}
async function test_schedule_slot_second_save_is_blocked_while_saving() {
  const { card, calls } = makeCard(); change(card, "sell_power", 5000); card._slotSaving = true; await card.saveScheduleSlotDraft();
  assertEqual(calls.length, 0, "second save must be blocked");
}
function test_schedule_slot_close_is_blocked_while_saving() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card._slotSaving = true;
  assertTrue(card.closeDialog() === false && card._dialog !== null && !card._slotDiscardPrompt, "close must be blocked while saving");
}
function test_schedule_slot_unsaved_changes_warn_on_close() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card.closeDialog();
  assertTrue(card._slotDiscardPrompt, "X close path must warn about dirty draft");
}
function test_schedule_slot_unsaved_changes_warn_on_escape() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card.closeDialog();
  assertTrue(dialogHtml(card).includes("Masz niezapisane zmiany"), "escape close path must show warning dialog");
}
function test_schedule_slot_unsaved_changes_warn_on_overlay_click() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card.closeDialog();
  assertTrue(card._slotDiscardPrompt && card._dialog !== null, "overlay close path must preserve dirty editor behind warning");
}
function test_schedule_slot_close_without_changes_needs_no_warning() {
  const { card } = makeCard(); card.closeDialog();
  assertTrue(card._dialog === null && !card._slotDiscardPrompt, "clean close must not warn");
}
function test_schedule_slot_discard_changes_closes_dialog() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card.closeDialog(); card.discardScheduleSlotChanges();
  assertTrue(card._dialog === null && card._slotEditDraft === null, "discard must close and clear draft");
}
function test_schedule_slot_return_to_editing_preserves_draft() {
  const { card } = makeCard(); change(card, "sell_power", 5000); card.closeDialog(); card.returnToScheduleSlotEditing();
  assertEqual(card._slotEditDraft.values.sell_power, 5000, "return must preserve draft");
}
function test_selling_slot_draft_keeps_minimum_sell_soc_and_tou_soc_separate() {
  const { card } = makeCard(); change(card, "minimum_sell_soc", 30); change(card, "tou_soc", 20);
  assertEqual([card._slotEditDraft.values.minimum_sell_soc, card._slotEditDraft.values.tou_soc], [30, 20], "selling SOC fields must stay separate");
}
function test_selling_slot_mode_change_does_not_copy_minimum_sell_soc_to_tou_soc() {
  const { card } = makeCard({ slot: { mode: "Normalna Praca", physical_work_mode: "Zero Export To Load", minimum_sell_soc: 35, tou_soc: 15 } });
  change(card, "mode", "Sprzedaż");
  assertEqual([card._slotEditDraft.values.minimum_sell_soc, card._slotEditDraft.values.tou_soc], [35, 15], "mode change must not copy selling guard to physical SOC");
}
async function test_selling_slot_save_sends_minimum_sell_soc_and_tou_soc_separately() {
  const { card, calls } = makeCard(); change(card, "minimum_sell_soc", 30); change(card, "tou_soc", 20); await card.saveScheduleSlotDraft();
  const patch = servicePayload(calls)[0]; assertEqual([patch.minimum_sell_soc, patch.tou_soc], [30, 20], "payload must keep both SOC values separate");
}
function test_charge_slot_draft_keeps_grid_charge_independent() {
  const { card } = makeCard(); change(card, "mode", "Ładowanie"); change(card, "charge_current", 90); change(card, "charge_enabled", true);
  assertTrue(card._slotEditDraft.values.charge_enabled === true, "grid permission must be independent from current");
}
function test_charge_slot_mode_change_does_not_force_grid_charge_off() {
  const { card } = makeCard({ slot: { charge_enabled: true } }); change(card, "mode", "Ładowanie");
  assertTrue(card._slotEditDraft.values.charge_enabled === true, "mode change must preserve explicit grid permission");
}
async function test_charge_slot_explicit_grid_charge_value_is_preserved_on_save() {
  const { card, calls } = makeCard(); change(card, "mode", "Ładowanie"); change(card, "charge_enabled", true); await card.saveScheduleSlotDraft();
  assertTrue(servicePayload(calls)[0].charge_enabled === true, "explicit grid permission must be sent");
}
function test_normal_slot_draft_preserves_physical_work_mode() {
  const { card } = makeCard({ slot: { mode: "Normalna Praca", physical_work_mode: "Zero Export To CT" } });
  assertEqual(card._slotEditDraft.values.physical_work_mode, "Zero Export To CT", "draft must use canonical physical mode");
}
async function test_normal_slot_save_uses_canonical_physical_work_mode() {
  const { card, calls } = makeCard({ slot: { mode: "Normalna Praca", physical_work_mode: "Zero Export To Load" } });
  change(card, "physical_work_mode", "Zero Export To CT"); await card.saveScheduleSlotDraft();
  assertEqual(servicePayload(calls)[0].physical_work_mode, "Zero Export To CT", "patch must carry canonical physical mode");
}
function test_normal_slot_cancel_restores_original_physical_work_mode() {
  const { card, attrs } = makeCard({ slot: { mode: "Normalna Praca", physical_work_mode: "Zero Export To Load" } });
  change(card, "physical_work_mode", "Zero Export To CT"); card.cancelScheduleSlotEdit(); card.openScheduleSlotEditor(KEY, LABEL);
  assertEqual(card._slotEditDraft.values.physical_work_mode, attrs.schedule_slots[KEY].physical_work_mode, "cancel must restore backend physical mode");
}
function test_card_uses_polish_manager_modes() {
  const card = new DeyeEnergyManagerCard();
  assertEqual(card.slotWorkModes(), BACKEND_MANAGER_MODES, "card modes must match the backend canonical values");
}
function test_card_does_not_offer_selling_first_as_current_mode() {
  const card = new DeyeEnergyManagerCard();
  assertTrue(!card.slotWorkModes().includes("Selling First"), "Selling First must remain legacy input only");
}
function test_card_does_not_offer_charge_as_current_mode() {
  const card = new DeyeEnergyManagerCard();
  assertTrue(!card.slotWorkModes().includes("Charge"), "Charge must remain legacy input only");
}
async function assertBackendModeRoundTrip(mode) {
  const { card, attrs, calls } = makeCard({ slot: {
    mode,
    physical_work_mode: mode === "Normalna Praca" ? "Zero Export To Load" : null,
  } });
  assertEqual(card._slotEditDraft.values.mode, mode, `draft must open with ${mode}`);
  change(card, "sell_power", 4100);
  await card.saveScheduleSlotDraft();
  const patch = servicePayload(calls)[0];
  assertEqual(patch.mode, mode, `payload must reassert canonical mode ${mode}`);
  assertEqual(attrs.schedule_slots[KEY].mode, mode, `backend mock must accept ${mode}`);
}
async function test_schedule_slot_backend_selling_mode_round_trip() { await assertBackendModeRoundTrip("Sprzedaż"); }
async function test_schedule_slot_backend_charging_mode_round_trip() { await assertBackendModeRoundTrip("Ładowanie"); }
async function test_schedule_slot_backend_normal_mode_round_trip() { await assertBackendModeRoundTrip("Normalna Praca"); }
async function test_bulk_edit_uses_polish_manager_modes() {
  const { card } = makeCard();
  card._selectedSlots = new Set([KEY]);
  card.collectBulkEditState = () => ({
    values: { active: "on", mode: "Ładowanie", sellPower: 0, dischargeCurrent: 0, chargeCurrent: 0, minSoc: 0, minSellPrice: 0 },
    fields: { active: false, mode: true, sellPower: false, dischargeCurrent: false, chargeCurrent: false, minSoc: false, minSellPrice: false },
  });
  let captured = null;
  card.applySchedulePatch = async (updates) => { captured = updates; return true; };
  await card.applyMultiEdit(card.scheduleSlots());
  assertEqual(captured[0].mode, "Ładowanie", "bulk edit must send a canonical Polish mode");
}
function test_mode_meta_handles_polish_selling() {
  assertEqual((new DeyeEnergyManagerCard()).modeMeta("Sprzedaż").cls, "selling", "Sprzedaż metadata must be selling");
}
function test_mode_meta_handles_polish_charging() {
  assertEqual((new DeyeEnergyManagerCard()).modeMeta("Ładowanie").cls, "charge", "Ładowanie metadata must be charge");
}
function test_mode_meta_handles_polish_normal() {
  assertEqual((new DeyeEnergyManagerCard()).modeMeta("Normalna Praca").cls, "normal", "Normalna Praca metadata must be normal");
}
function test_legacy_selling_first_is_normalized_to_sprzedaz() {
  assertEqual(makeCard({ slot: { mode: "Selling First" } }).card._slotEditDraft.values.mode, "Sprzedaż", "legacy selling mode must normalize");
}
function test_legacy_charge_is_normalized_to_ladowanie() {
  assertEqual(makeCard({ slot: { mode: "Charge" } }).card._slotEditDraft.values.mode, "Ładowanie", "legacy charging mode must normalize");
}
function test_legacy_normal_is_normalized_to_normalna_praca() {
  assertEqual(makeCard({ slot: { mode: "normal" } }).card._slotEditDraft.values.mode, "Normalna Praca", "legacy normal mode must normalize");
}
async function test_legacy_mode_is_saved_back_as_canonical_polish_value() {
  const { card, calls } = makeCard({ slot: { mode: "Charge" } });
  change(card, "sell_power", 4100);
  await card.saveScheduleSlotDraft();
  assertEqual(servicePayload(calls)[0].mode, "Ładowanie", "legacy mode must be written back canonically");
}
function test_card_mapping_does_not_depend_on_legacy_schedule_function() {
  const card = new DeyeEnergyManagerCard();
  card.mappingPlanDiagnostics = () => [{ range: 1, start: 0, end: 4, tou_soc: 20, grid_charge: false }];
  const [segment] = card.scheduleSegments([]);
  assertEqual(segment, { start: 0, end: 4, touSoc: 20, chargeEnabled: false }, "physical mapping must use only physical fields");
  assertTrue(!card.scheduleSegments.toString().includes("schedule_function"), "card mapping must not depend on legacy schedule_function");
}
function noDirectWriteTest(domain, service, field, value) {
  const { card, calls } = makeCard(); change(card, field, value);
  assertTrue(!calls.some((item) => item.domain === domain && item.service === service), `${domain}.${service} must not run during edit`);
}
function test_schedule_slot_dialog_does_not_call_number_set_value_during_edit() { noDirectWriteTest("number", "set_value", "sell_power", 5000); }
function test_schedule_slot_dialog_does_not_call_select_select_option_during_edit() { noDirectWriteTest("select", "select_option", "mode", "Ładowanie"); }
function test_schedule_slot_dialog_does_not_call_switch_service_during_edit() { noDirectWriteTest("switch", "turn_on", "charge_enabled", true); }
function test_both_card_copies_remain_identical_after_schedule_draft_changes() {
  assertEqual(fs.readFileSync(componentCard), fs.readFileSync(rootCard), "both card copies must remain identical");
}

const tests = [
  test_schedule_slot_edit_does_not_save_on_field_change, test_schedule_slot_edit_uses_local_draft,
  test_schedule_slot_hass_update_does_not_overwrite_dirty_draft, test_schedule_slot_dirty_comparison_normalizes_numeric_types,
  test_schedule_slot_cancel_discards_all_changes, test_schedule_slot_cancel_performs_no_service_call,
  test_schedule_slot_reopen_after_cancel_uses_backend_state, test_schedule_slot_save_applies_all_changes_once,
  test_schedule_slot_save_uses_single_apply_schedule_patch_call, test_schedule_slot_save_triggers_single_mapping_recalculation,
  test_schedule_slot_unchanged_save_performs_no_service_call, test_schedule_slot_save_with_control_disabled_stays_local,
  test_schedule_slot_save_with_control_disabled_does_not_write_tou, test_schedule_slot_save_with_control_disabled_shows_local_only_message,
  test_schedule_slot_save_error_keeps_dialog_open, test_schedule_slot_save_error_keeps_draft,
  test_schedule_slot_save_error_reenables_save_button, test_schedule_slot_save_can_be_retried_after_error,
  test_schedule_slot_success_refreshes_actual_state, test_schedule_slot_success_clears_draft,
  test_schedule_slot_success_closes_dialog_after_backend_refresh, test_schedule_slot_save_button_is_disabled_while_saving,
  test_schedule_slot_second_save_is_blocked_while_saving, test_schedule_slot_close_is_blocked_while_saving,
  test_schedule_slot_unsaved_changes_warn_on_close, test_schedule_slot_unsaved_changes_warn_on_escape,
  test_schedule_slot_unsaved_changes_warn_on_overlay_click, test_schedule_slot_close_without_changes_needs_no_warning,
  test_schedule_slot_discard_changes_closes_dialog, test_schedule_slot_return_to_editing_preserves_draft,
  test_selling_slot_draft_keeps_minimum_sell_soc_and_tou_soc_separate,
  test_selling_slot_mode_change_does_not_copy_minimum_sell_soc_to_tou_soc,
  test_selling_slot_save_sends_minimum_sell_soc_and_tou_soc_separately,
  test_charge_slot_draft_keeps_grid_charge_independent, test_charge_slot_mode_change_does_not_force_grid_charge_off,
  test_charge_slot_explicit_grid_charge_value_is_preserved_on_save, test_normal_slot_draft_preserves_physical_work_mode,
  test_normal_slot_save_uses_canonical_physical_work_mode, test_normal_slot_cancel_restores_original_physical_work_mode,
  test_card_uses_polish_manager_modes, test_card_does_not_offer_selling_first_as_current_mode,
  test_card_does_not_offer_charge_as_current_mode, test_schedule_slot_backend_selling_mode_round_trip,
  test_schedule_slot_backend_charging_mode_round_trip, test_schedule_slot_backend_normal_mode_round_trip,
  test_bulk_edit_uses_polish_manager_modes, test_mode_meta_handles_polish_selling,
  test_mode_meta_handles_polish_charging, test_mode_meta_handles_polish_normal,
  test_legacy_selling_first_is_normalized_to_sprzedaz, test_legacy_charge_is_normalized_to_ladowanie,
  test_legacy_normal_is_normalized_to_normalna_praca, test_legacy_mode_is_saved_back_as_canonical_polish_value,
  test_card_mapping_does_not_depend_on_legacy_schedule_function,
  test_schedule_slot_dialog_does_not_call_number_set_value_during_edit,
  test_schedule_slot_dialog_does_not_call_select_select_option_during_edit,
  test_schedule_slot_dialog_does_not_call_switch_service_during_edit,
  test_both_card_copies_remain_identical_after_schedule_draft_changes,
];

(async () => {
  for (const test of tests) {
    try { await test(); } catch (error) {
      failures += 1;
      console.error(`FAIL: ${test.name}\n  ${error?.stack || error}`);
    }
  }
  if (failures) process.exit(1);
  console.log(`All schedule slot draft tests passed (${tests.length})`);
})();

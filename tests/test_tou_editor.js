const fs = require("fs");
const path = require("path");

global.window = {
  setTimeout: (fn, ms) => (ms >= 1000 ? 1 : setTimeout(fn, ms)),
  clearTimeout: (id) => { if (id && id !== 1) clearTimeout(id); },
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
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
  if (!value) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
}
function assertEqual(actual, expected, message) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures += 1;
    console.error(`FAIL: ${message}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
  }
}

function field(fieldName, actual, options = {}) {
  const supported = options.supported !== false;
  const currentAvailable = options.current_available !== false;
  const readable = options.readable !== undefined ? options.readable : supported && currentAvailable;
  const writable = options.writable !== undefined ? options.writable : readable;
  const capability = {
    field: fieldName,
    supported,
    readable,
    writable,
    current_available: currentAvailable,
    read_only: options.read_only === true,
    actual,
  };
  return {
    capability,
    actual: currentAvailable ? actual : null,
    expected: options.expected !== undefined ? options.expected : actual,
    status: options.status || (currentAvailable ? "confirmed" : "unavailable"),
    writable,
  };
}

function diagnostics(options = {}) {
  const starts = options.starts || ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"];
  const supported = options.supported || { start: true, end: true, soc: true, grid_charge: true };
  const readOnly = options.readOnly === true;
  const rows = [];
  const physical = [];
  for (let slot = 1; slot <= 6; slot += 1) {
    const values = {
      start: starts[slot - 1],
      end: starts[slot % 6],
      soc: 10 * slot,
      grid_charge: slot % 2 === 0,
    };
    const fields = {};
    Object.keys(values).forEach((name) => {
      const overrides = options.fieldOverrides?.[slot]?.[name] || options.fieldOverrides?.all?.[name] || {};
      fields[name] = field(name, values[name], {
        supported: supported[name] !== false,
        writable: readOnly ? false : undefined,
        read_only: readOnly,
        ...overrides,
      });
    });
    const capabilityFields = Object.fromEntries(Object.entries(fields).map(([name, item]) => [name, item.capability]));
    rows.push({
      slot_index: slot,
      provider: options.provider || "dowolna_nazwa",
      read_only: readOnly,
      blocked_by_master_control: options.controlEnabled === false,
      control_writable: !readOnly && options.controlEnabled !== false && options.pending !== true,
      fields: capabilityFields,
    });
    physical.push({ range: slot, fields, capabilities: rows[rows.length - 1] });
  }
  return {
    tou_capabilities: rows,
    physical_tou: physical,
    control: {
      control_enabled: options.controlEnabled !== false,
      control_status: options.controlEnabled === false ? "Wyłączone" : "Aktywne",
    },
    tou_transaction: {
      tou_write_pending: options.pending === true,
      operation_status: options.operationStatus || "idle",
      tou_last_error: options.transactionError || "none",
    },
    tou_reverse_sync: {
      reverse_sync_status: options.reverseStatus || "idle",
      reverse_sync_last_error: options.reverseError || "none",
      reverse_sync_changed_hours: options.changedHours || [],
      reverse_sync_round_trip_ok: options.roundTrip ?? null,
    },
  };
}

function makeCard(options = {}) {
  const attrs = diagnostics(options);
  const calls = [];
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = {
    states: {},
    services: { deye_energy_manager: { set_tou_slot: true } },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card.diagnosticsAttributes = () => attrs;
  card.querySelector = () => null;
  card.querySelectorAll = () => [];
  card.render = () => {};
  card.renderDialogOnly = () => {};
  card.updateSaveIndicator = () => {};
  return { card, attrs, calls };
}

function editorHtml(card, slot = 1) {
  card.openTouEditor(slot);
  return card.renderDialog([], []);
}

function draft(card, changes, slot = 1) {
  card.openTouEditor(slot);
  Object.assign(card._touEditDraft.values, changes);
}

function payloadFor(changes, options = {}) {
  const { card } = makeCard(options);
  draft(card, changes);
  return card.buildTouPartialPayload(1);
}

function test_tou_editor_uses_backend_capabilities() {
  const { card } = makeCard({ supported: { start: true, end: false, soc: true, grid_charge: false } });
  const html = editorHtml(card);
  assertTrue(html.includes('data-tou-editor-field="start"') && html.includes('data-tou-editor-field="soc"'), "supported backend fields must render");
}
function test_tou_editor_does_not_guess_provider_by_name() {
  const { card, attrs } = makeCard({ provider: "deye_addon" });
  attrs.tou_capabilities[0].provider = "zupełnie_inna_nazwa";
  assertTrue(card.hasWritablePhysicalTou(1), "provider name must not decide writability");
}
function test_tou_editor_hides_unsupported_fields() {
  const { card } = makeCard({ supported: { start: true, end: false, soc: true, grid_charge: false } });
  const html = editorHtml(card);
  assertTrue(!html.includes('data-tou-editor-field="end"'), "unsupported end must be hidden");
}
function test_tou_editor_shows_readable_nonwritable_field_as_read_only() {
  const { card } = makeCard({ fieldOverrides: { all: { soc: { writable: false } } } });
  assertTrue(editorHtml(card).includes('data-tou-readonly="soc"'), "readable nonwritable SOC must be read-only");
}
function test_tou_editor_handles_partial_custom_capabilities() {
  const { card } = makeCard({ supported: { start: true, end: true, soc: true, grid_charge: false } });
  const html = editorHtml(card);
  assertTrue(html.includes("SOC Deye TOU") && !html.includes('data-tou-editor-field="grid_charge"'), "partial Custom fields must render independently");
}
function test_tou_editor_hides_grid_charge_when_not_supported() {
  const { card } = makeCard({ supported: { start: true, end: true, soc: true, grid_charge: false } });
  assertTrue(!editorHtml(card).includes('data-tou-editor-field="grid_charge"'), "unsupported grid field must be hidden");
}
function test_manual_tou_editor_really_exposes_end_field() {
  const { card } = makeCard();
  assertTrue(editorHtml(card).includes('data-tou-field="end"'), "end input must be exposed");
}
function test_tou_editor_end_uses_next_slot_actual_start() {
  const { card } = makeCard();
  card.openTouEditor(2);
  assertEqual(card._touEditDraft.values.end, "08:00", "slot end must use next start");
}
function test_tou_editor_last_end_uses_first_slot_actual_start() {
  const { card } = makeCard();
  card.openTouEditor(6);
  assertEqual(card._touEditDraft.values.end, "00:00", "last end must wrap to first start");
}
async function test_tou_editor_rejects_non_hour_time_before_service_call() {
  const { card, calls } = makeCard();
  draft(card, { start: "06:30" });
  const result = await card.savePhysicalTouSlot(1);
  assertTrue(!result && calls.length === 0, "non-hour time must be rejected before service");
}
function test_tou_editor_soc_only_save_sends_only_soc() {
  assertEqual(payloadFor({ soc: 55 }), { slot: 1, soc: 55 }, "SOC-only payload");
}
function test_tou_editor_start_only_save_sends_only_start() {
  assertEqual(payloadFor({ start: "01:00" }), { slot: 1, start: "01:00" }, "start-only payload");
}
function test_tou_editor_end_only_save_sends_only_end() {
  assertEqual(payloadFor({ end: "05:00" }), { slot: 1, end: "05:00" }, "end-only payload");
}
function test_tou_editor_grid_only_save_sends_only_grid_charge() {
  assertEqual(payloadFor({ grid_charge: true }), { slot: 1, grid_charge: true }, "grid-only payload");
}
function test_tou_editor_start_end_save_sends_both_boundaries() {
  assertEqual(payloadFor({ start: "01:00", end: "05:00" }), { slot: 1, start: "01:00", end: "05:00" }, "both boundaries payload");
}
function test_tou_editor_unchanged_fields_are_not_sent() {
  assertEqual(payloadFor({ soc: 10, grid_charge: false }), { slot: 1 }, "unchanged values must be omitted");
}
function test_tou_editor_shows_actual_and_expected() {
  const { card } = makeCard({ fieldOverrides: { 1: { soc: { expected: 55, status: "waiting" } } } });
  const html = editorHtml(card);
  assertTrue(html.includes("Aktualna wartość") && html.includes("Oczekiwana wartość") && html.includes("55%"), "actual and expected must render");
}
function statusTest(status, label) {
  const { card } = makeCard({ fieldOverrides: { 1: { soc: { status } } } });
  assertTrue(editorHtml(card).includes(label), `${status} status must be translated`);
}
function test_tou_editor_shows_waiting_status() { statusTest("waiting", "Oczekiwanie"); }
function test_tou_editor_shows_confirmed_status() { statusTest("confirmed", "Potwierdzono"); }
function test_tou_editor_shows_mismatch_status() { statusTest("mismatch", "Niezgodność"); }
function test_tou_editor_shows_unavailable_status() {
  const { card } = makeCard({ fieldOverrides: { 1: { soc: { current_available: false, status: "unavailable" } } } });
  assertTrue(editorHtml(card).includes("Niedostępne"), "unavailable status must render");
}
async function test_tou_editor_refreshes_from_readback_after_success() {
  const { card, attrs } = makeCard({ operationStatus: "confirmed" });
  draft(card, { soc: 55 });
  card.callService = async () => { attrs.physical_tou[0].fields.soc.actual = 55; attrs.physical_tou[0].fields.soc.capability.actual = 55; };
  await card.savePhysicalTouSlot(1);
  assertEqual(card._touEditDraft.values.soc, 55, "confirmed save must refresh from actual readback");
}
function test_tou_editor_restores_actual_values_after_rollback() {
  const { card } = makeCard({ operationStatus: "rollback" });
  draft(card, { soc: 55 });
  card.refreshTouEditorFromActual(1, false);
  assertEqual(card._touEditDraft.values.soc, 10, "rollback must restore actual");
}
function test_tou_editor_shows_rollback_failed_error() {
  const { card } = makeCard({ operationStatus: "rollback_failed", transactionError: "Błąd krytyczny rollbacku" });
  assertTrue(editorHtml(card).includes("Błąd krytyczny rollbacku"), "rollback_failed error must be visible");
}
function test_card_disables_tou_save_while_backend_pending() {
  const { card } = makeCard({ pending: true });
  assertTrue(editorHtml(card).includes("Trwa zapis Deye Time Of Use") && editorHtml(card).includes("disabled"), "backend pending must disable save");
}
function test_card_disables_tou_save_while_local_save_pending() {
  const { card } = makeCard();
  card._touSaving = true;
  assertTrue(editorHtml(card).includes("disabled"), "local save must disable save");
}
async function test_card_does_not_send_second_tou_save_while_pending() {
  const { card, calls } = makeCard({ pending: true });
  draft(card, { soc: 55 });
  assertTrue(!(await card.savePhysicalTouSlot(1)) && calls.length === 0, "pending backend must block another service call");
}
function test_tou_editor_respects_master_control_switch() {
  const { card } = makeCard({ controlEnabled: false });
  assertTrue(editorHtml(card).includes("Sterowanie Deye jest wyłączone."), "master control status must be shown");
}
async function test_disabled_master_control_blocks_manual_tou_save() {
  const { card, calls } = makeCard({ controlEnabled: false });
  draft(card, { soc: 55 });
  assertTrue(!(await card.savePhysicalTouSlot(1)) && calls.length === 0, "disabled master must block save");
}
function test_disabled_master_control_still_shows_tou_readback() {
  const { card } = makeCard({ controlEnabled: false });
  assertTrue(editorHtml(card).includes("10%"), "readback must remain visible while master is disabled");
}
function test_read_only_provider_disables_tou_write() {
  const { card } = makeCard({ readOnly: true });
  assertTrue(!editorHtml(card).includes("data-save-tou"), "read-only provider must not expose save");
}
function test_read_only_provider_shows_readback_only() {
  const { card } = makeCard({ readOnly: true });
  const html = editorHtml(card);
  assertTrue(html.includes("tylko do odczytu") && html.includes('data-tou-readonly="soc"'), "read-only provider must show actual values");
}
function test_read_only_provider_without_readback_shows_no_fields_message() {
  const { card } = makeCard({ supported: { start: false, end: false, soc: false, grid_charge: false }, readOnly: true });
  assertTrue(card.renderTouSettingsContent().includes("Brak dostępnych pól Deye Time Of Use"), "provider without readback must show no-fields message");
}
function test_sunsynk_soc_only_ui_save_does_not_send_grid_charge() {
  assertTrue(!Object.prototype.hasOwnProperty.call(payloadFor({ soc: 55 }, { provider: "sunsynk" }), "grid_charge"), "Sunsynk SOC-only save must preserve raw grid option");
}
function test_solarman_soc_only_ui_save_does_not_send_grid_charge() {
  assertTrue(!Object.prototype.hasOwnProperty.call(payloadFor({ soc: 55 }, { provider: "solarman" }), "grid_charge"), "Solarman SOC-only save must preserve raw grid option");
}
function test_tou_editor_shows_reverse_sync_confirmed() {
  const { card } = makeCard({ reverseStatus: "confirmed", roundTrip: true });
  assertTrue(card.renderTouReverseSyncSummary().includes("Potwierdzona") && card.renderTouReverseSyncSummary().includes("Zgodny"), "confirmed reverse sync must render");
}
function test_tou_editor_shows_reverse_sync_error() {
  const { card } = makeCard({ reverseStatus: "rollback", reverseError: "Błąd synchronizacji" });
  assertTrue(card.renderTouReverseSyncSummary().includes("Błąd synchronizacji"), "reverse sync error must render");
}
function test_tou_editor_shows_changed_hours() {
  const { card } = makeCard({ changedHours: [6, 7, 8, 9] });
  assertTrue(card.renderTouReverseSyncSummary().includes("6, 7, 8, 9"), "changed hours must render");
}
function test_both_card_copies_remain_identical() {
  assertEqual(fs.readFileSync(componentCard), fs.readFileSync(rootCard), "both card copies must remain identical");
}

const tests = [
  test_tou_editor_uses_backend_capabilities,
  test_tou_editor_does_not_guess_provider_by_name,
  test_tou_editor_hides_unsupported_fields,
  test_tou_editor_shows_readable_nonwritable_field_as_read_only,
  test_tou_editor_handles_partial_custom_capabilities,
  test_tou_editor_hides_grid_charge_when_not_supported,
  test_manual_tou_editor_really_exposes_end_field,
  test_tou_editor_end_uses_next_slot_actual_start,
  test_tou_editor_last_end_uses_first_slot_actual_start,
  test_tou_editor_rejects_non_hour_time_before_service_call,
  test_tou_editor_soc_only_save_sends_only_soc,
  test_tou_editor_start_only_save_sends_only_start,
  test_tou_editor_end_only_save_sends_only_end,
  test_tou_editor_grid_only_save_sends_only_grid_charge,
  test_tou_editor_start_end_save_sends_both_boundaries,
  test_tou_editor_unchanged_fields_are_not_sent,
  test_tou_editor_shows_actual_and_expected,
  test_tou_editor_shows_waiting_status,
  test_tou_editor_shows_confirmed_status,
  test_tou_editor_shows_mismatch_status,
  test_tou_editor_shows_unavailable_status,
  test_tou_editor_refreshes_from_readback_after_success,
  test_tou_editor_restores_actual_values_after_rollback,
  test_tou_editor_shows_rollback_failed_error,
  test_card_disables_tou_save_while_backend_pending,
  test_card_disables_tou_save_while_local_save_pending,
  test_card_does_not_send_second_tou_save_while_pending,
  test_tou_editor_respects_master_control_switch,
  test_disabled_master_control_blocks_manual_tou_save,
  test_disabled_master_control_still_shows_tou_readback,
  test_read_only_provider_disables_tou_write,
  test_read_only_provider_shows_readback_only,
  test_read_only_provider_without_readback_shows_no_fields_message,
  test_sunsynk_soc_only_ui_save_does_not_send_grid_charge,
  test_solarman_soc_only_ui_save_does_not_send_grid_charge,
  test_tou_editor_shows_reverse_sync_confirmed,
  test_tou_editor_shows_reverse_sync_error,
  test_tou_editor_shows_changed_hours,
  test_both_card_copies_remain_identical,
];

(async () => {
  for (const test of tests) {
    try { await test(); } catch (error) {
      failures += 1;
      console.error(`FAIL: ${test.name}\n  ${error?.stack || error}`);
    }
  }
  if (failures) process.exit(1);
  console.log(`All TOU editor tests passed (${tests.length})`);
})();

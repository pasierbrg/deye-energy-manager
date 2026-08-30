const fs = require("fs");
const path = require("path");

global.window = {
  setTimeout,
  clearTimeout,
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: clearTimeout,
  addEventListener: () => {},
  removeEventListener: () => {},
};
global.requestAnimationFrame = window.requestAnimationFrame;
global.cancelAnimationFrame = window.cancelAnimationFrame;
global.document = { scrollingElement: {}, documentElement: {}, body: {} };
global.HTMLElement = class {};
global.customElements = { define: () => {} };

const cardPath = path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js");
eval(fs.readFileSync(cardPath, "utf8") + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

const LEWA_OPTIONS = [
  { value: "Zero Export To Load", label: "Eksport wyłączony — pomiar Load", available: true },
  { value: "Zero Export To CT", label: "Eksport wyłączony — pomiar CT", available: true },
];
const SUNSYNK_OPTIONS = [
  { value: "Zero Export To Load", label: "Zasilanie odbiorów podstawowych", available: true },
  { value: "Zero Export To CT", label: "Eksport wyłączony", available: true },
];

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

function numberState(value) {
  return { state: String(value), attributes: { min: 0, max: 240, step: 1 } };
}

function makeCard(options = LEWA_OPTIONS) {
  const attrs = {
    default_settings: {
      mode: "Normalna Praca",
      physical_work_mode: "Zero Export To Load",
      sell_power: 3000,
      discharge_current: 80,
      charge_current: 70,
      grid_charge_current: 40,
    },
    normal_profile: { physical_work_mode: "Zero Export To Load" },
  };
  if (options !== null) attrs.normal_profile_options = options;
  const calls = [];
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = {
    states: {
      "sensor.deye_energy_manager_manager_status": { state: "idle", attributes: attrs },
      "select.deye_energy_manager_default_work_mode": { state: "Normalna Praca", attributes: { options: ["Normalna Praca", "Sprzedaż"] } },
      "number.deye_energy_manager_default_sell_power": numberState(3000),
      "number.deye_energy_manager_default_discharge_current": numberState(80),
      "number.deye_energy_manager_default_charge_current": numberState(70),
      "number.deye_energy_manager_default_grid_charge_current": numberState(40),
    },
    services: { deye_energy_manager: { save_default_settings: true } },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card.render = () => {};
  card.beginSave = () => {};
  card.finishSave = () => {};
  card.updateSaveIndicator = () => {};
  card.failSave = (_key, error) => { card._testError = error; };
  return { card, calls };
}

function defaultInput(key, value) {
  return { value: String(value), dataset: { defaultProfileNumber: key } };
}

async function saveDefaultPayload(mode, physical = "Zero Export To Load", options = LEWA_OPTIONS) {
  const { card, calls } = makeCard(options);
  card.querySelector = (selector) => {
    if (selector === '[data-raw="default-work-mode"]') return { value: mode };
    if (selector === '[data-raw="default-physical-work-mode"]') return { value: physical };
    return null;
  };
  card.querySelectorAll = (selector) => selector === "[data-default-profile-number]" ? [
    defaultInput("sell_power", 3000),
    defaultInput("discharge_current", 80),
    defaultInput("charge_current", 70),
    defaultInput("grid_charge_current", 40),
  ] : [];
  const ok = await card.saveDefaultSettings();
  if (!ok) throw card._testError || new Error("saveDefaultSettings failed");
  return calls[0].data;
}

function test_default_settings_card_uses_logical_manager_modes() {
  assertEqual(makeCard().card.defaultWorkModes(), ["Normalna Praca", "Sprzedaż"], "default modes must be logical and Polish");
}
function test_default_settings_card_does_not_offer_selling_first() {
  assertTrue(!makeCard().card.defaultWorkModes().includes("Selling First"), "Selling First must not be offered");
}
function test_default_settings_card_does_not_offer_zero_export_as_logical_mode() {
  const modes = makeCard().card.defaultWorkModes();
  assertTrue(!modes.includes("Zero Export To Load") && !modes.includes("Zero Export To CT"), "physical values must not be logical modes");
}
async function test_default_settings_card_sends_normalna_praca() {
  assertEqual((await saveDefaultPayload("Normalna Praca")).mode, "Normalna Praca", "card must send Normalna Praca");
}
async function test_default_settings_card_sends_sprzedaz() {
  assertEqual((await saveDefaultPayload("Sprzedaż")).mode, "Sprzedaż", "card must send Sprzedaż");
}
async function test_default_settings_card_keeps_physical_normal_variant_separate() {
  const payload = await saveDefaultPayload("Normalna Praca", "Zero Export To CT");
  assertEqual(payload.mode, "Normalna Praca", "logical mode must stay canonical");
  assertEqual(payload.physical_work_mode, "Zero Export To CT", "physical variant must use its own field");
}
function test_normal_profile_card_uses_backend_provider_options() {
  assertEqual(makeCard(SUNSYNK_OPTIONS).card.normalProfileModeOptions(), SUNSYNK_OPTIONS.map((row) => [row.value, row.label]), "card must use backend metadata");
}
function test_normal_profile_card_lewa_reka_uses_load_ct_labels() {
  assertEqual(makeCard(LEWA_OPTIONS).card.normalProfileModeOptions().map((row) => row[1]), ["Eksport wyłączony — pomiar Load", "Eksport wyłączony — pomiar CT"], "Lewa-Reka labels must be localized");
}
function test_normal_profile_card_sunsynk_uses_essentials_zero_export_labels() {
  assertEqual(makeCard(SUNSYNK_OPTIONS).card.normalProfileModeOptions().map((row) => row[1]), ["Zasilanie odbiorów podstawowych", "Eksport wyłączony"], "Sunsynk labels must reflect provider semantics");
}
function test_normal_profile_card_custom_shows_only_configured_variants() {
  const custom = [
    { value: "Zero Export To Load", label: "Eksport wyłączony — pomiar Load", available: true },
    { value: "Zero Export To CT", label: "Eksport wyłączony — pomiar CT", available: false },
  ];
  assertEqual(makeCard(custom).card.normalProfileModeOptions(), [["Zero Export To Load", "Eksport wyłączony — pomiar Load"]], "Custom must hide missing variants");
}
function test_normal_profile_card_does_not_guess_provider_labels() {
  assertEqual(makeCard(null).card.normalProfileModeOptions(), [], "card must not guess without backend metadata");
}

const tests = [
  test_default_settings_card_uses_logical_manager_modes,
  test_default_settings_card_does_not_offer_selling_first,
  test_default_settings_card_does_not_offer_zero_export_as_logical_mode,
  test_default_settings_card_sends_normalna_praca,
  test_default_settings_card_sends_sprzedaz,
  test_default_settings_card_keeps_physical_normal_variant_separate,
  test_normal_profile_card_uses_backend_provider_options,
  test_normal_profile_card_lewa_reka_uses_load_ct_labels,
  test_normal_profile_card_sunsynk_uses_essentials_zero_export_labels,
  test_normal_profile_card_custom_shows_only_configured_variants,
  test_normal_profile_card_does_not_guess_provider_labels,
];

(async () => {
  if (process.argv.includes("--emit-payloads")) {
    process.stdout.write(JSON.stringify([
      await saveDefaultPayload("Normalna Praca", "Zero Export To Load"),
      await saveDefaultPayload("Sprzedaż", "Zero Export To CT"),
    ]));
    return;
  }
  for (const test of tests) await test();
  if (failures) process.exit(1);
  console.log("All default settings and provider profile card tests passed");
})().catch((error) => { console.error(error); process.exit(1); });

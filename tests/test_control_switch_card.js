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
const cardSource = fs.readFileSync(cardPath, "utf8");
eval(cardSource + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

const RENAMED_ENTITY_ID = "switch.recznie_przemianowane_sterowanie_deye";
const MISSING_MESSAGE = "Nie znaleziono encji Sterowanie Deye. Przeładuj integrację lub sprawdź konfigurację.";

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

function makeCard({ enabled = true, status = "Aktywne", entityId = RENAMED_ENTITY_ID, entityState } = {}) {
  const calls = [];
  const control = { entity_id: entityId, enabled, status };
  const states = {
    "sensor.deye_energy_manager_manager_status": {
      state: "Aktywny",
      attributes: { control },
    },
  };
  if (entityId && entityState !== null) {
    states[entityId] = { state: entityState || (enabled ? "on" : "off"), attributes: { friendly_name: "Sterowanie Deye" } };
  }
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = {
    states,
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card.render = () => {};
  return { card, calls, control, states };
}

function test_card_control_toggle_uses_backend_entity_id() {
  const { card } = makeCard();
  assertEqual(card.controlEntityId(), RENAMED_ENTITY_ID, "card must use the entity id from manager_status.control");
}

function test_card_control_toggle_does_not_hardcode_default_entity_id() {
  assertTrue(!cardSource.includes("switch.deye_energy_manager_control"), "card source must not hardcode the preferred entity id");
}

async function test_card_control_toggle_calls_turn_off_when_active() {
  const { card, calls } = makeCard({ enabled: true, status: "Aktywne" });
  assertTrue(await card.toggleControl(), "active control should be switchable off");
  assertEqual(calls, [{ domain: "switch", service: "turn_off", data: { entity_id: RENAMED_ENTITY_ID } }], "active control must call switch.turn_off");
}

async function test_card_control_toggle_calls_turn_on_when_disabled() {
  const { card, calls } = makeCard({ enabled: false, status: "Wyłączone" });
  assertTrue(await card.toggleControl(), "disabled control should be switchable on");
  assertEqual(calls, [{ domain: "switch", service: "turn_on", data: { entity_id: RENAMED_ENTITY_ID } }], "disabled control must call switch.turn_on");
}

async function test_card_control_toggle_is_blocked_while_disabling() {
  const { card, calls } = makeCard({ enabled: false, status: "Wyłączanie", entityState: "off" });
  assertTrue(!(await card.toggleControl()), "toggle must be blocked while disabling");
  assertEqual(calls, [], "blocked toggle must not call a service");
}

async function test_control_toggle_same_button_off_then_on() {
  const { card, calls, control, states } = makeCard({ enabled: true, status: "Aktywne" });
  card._hass.callService = async (domain, service, data) => {
    calls.push({ domain, service, data });
    if (service === "turn_off") {
      control.enabled = false;
      control.status = "Wyłączone";
      states[RENAMED_ENTITY_ID].state = "off";
    } else {
      control.enabled = true;
      control.status = "Aktywne";
      states[RENAMED_ENTITY_ID].state = "on";
    }
  };

  assertTrue(await card.toggleControl(), "the shared button must switch active control off");
  assertEqual(card.controlStatus(), "Wyłączone", "the shared button must observe the disabled state");
  assertTrue(await card.toggleControl(), "the same button must switch disabled control on again");
  assertEqual(card.controlStatus(), "Aktywne", "the same button must observe the active state again");
  assertEqual(calls.map((call) => call.service), ["turn_off", "turn_on"], "one component must emit OFF then ON");
}

async function test_control_toggle_is_blocked_only_while_disabling() {
  const { card, calls, control, states } = makeCard({ enabled: true, status: "Aktywne" });
  let releaseDisable;
  const disableReleased = new Promise((resolve) => { releaseDisable = resolve; });
  card._hass.callService = async (domain, service, data) => {
    calls.push({ domain, service, data });
    if (service === "turn_off") {
      control.enabled = false;
      control.status = "Wyłączanie";
      states[RENAMED_ENTITY_ID].state = "off";
      await disableReleased;
      control.status = "Wyłączone";
      return;
    }
    control.enabled = true;
    control.status = "Aktywne";
    states[RENAMED_ENTITY_ID].state = "on";
  };

  const disabling = card.toggleControl();
  await Promise.resolve();
  assertEqual(card.controlStatus(), "Wyłączanie", "runtime transition must be visible while cleanup is pending");
  assertTrue(!(await card.toggleControl()), "a second click must be blocked during cleanup only");
  assertEqual(calls.map((call) => call.service), ["turn_off"], "no duplicate service call is allowed while disabling");
  releaseDisable();
  await disabling;
  assertEqual(card.controlStatus(), "Wyłączone", "cleanup must expose the stable disabled state");
  assertTrue(await card.toggleControl(), "clicking must be allowed again after cleanup");
  assertEqual(calls.map((call) => call.service), ["turn_off", "turn_on"], "the next click must turn control on");
}

function test_control_button_and_disabled_banner_use_same_control_state() {
  const { card, control } = makeCard({ enabled: false, status: "Wyłączanie", entityState: "off" });
  const classes = new Set();
  const button = {
    textContent: "Sterowanie Deye — Wyłączanie",
    disabled: true,
    classList: {
      toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
    },
  };
  const banner = { className: "", textContent: "" };
  card._controlFeedbackActive = true;
  card._controlExpectedEnabled = false;
  card.querySelectorAll = (selector) => selector === "[data-control-toggle]" ? [button] : [];
  card.querySelector = (selector) => selector === "[data-save-indicator]" ? banner : null;

  card.updateControlUi();
  assertEqual(button.textContent, "Sterowanie Deye — Wyłączanie", "button must use the transitional control state");
  assertTrue(button.disabled, "button must be disabled during cleanup");
  assertEqual(banner.textContent, "Wyłączanie Sterowania Deye…", "banner must describe the same transitional state");

  control.status = "Wyłączone";
  card.updateControlUi();
  assertEqual(button.textContent, "Sterowanie Deye — Wyłączone", "button must be patched after the final HA update");
  assertTrue(!button.disabled, "the same button must be re-enabled after cleanup");
  assertTrue(!classes.has("active"), "disabled control must not keep the active class");
  assertEqual(banner.textContent, "Sterowanie Deye jest wyłączone.", "banner and button must settle on the same state");
}

async function test_card_control_toggle_reports_missing_entity() {
  const { card, calls } = makeCard({ entityId: null, entityState: null });
  assertTrue(!(await card.toggleControl()), "missing entity must fail");
  assertEqual(calls, [], "missing entity must not call a service");
  assertEqual(card._saveMessage, MISSING_MESSAGE, "card must show the required Polish error");
  assertEqual(card._saveStatus, "error", "missing entity must be visible as an error");
}

function test_card_control_status_updates_from_backend_state() {
  const { card, control } = makeCard({ enabled: true, status: "Aktywne" });
  assertEqual(card.controlStatus(), "Aktywne", "initial runtime status must be visible");
  control.enabled = false;
  control.status = "Wyłączanie";
  assertEqual(card.controlStatus(), "Wyłączanie", "disabling runtime status must be visible");
  control.status = "Wyłączone";
  assertEqual(card.controlStatus(), "Wyłączone", "disabled runtime status must be visible");
}

async function emittedPayloads() {
  const fixture = makeCard({ enabled: true, status: "Aktywne" });
  fixture.card._hass.callService = async (domain, service, data) => {
    fixture.calls.push({ domain, service, data });
    fixture.control.enabled = service === "turn_on";
    fixture.control.status = service === "turn_on" ? "Aktywne" : "Wyłączone";
    fixture.states[RENAMED_ENTITY_ID].state = service === "turn_on" ? "on" : "off";
  };
  await fixture.card.toggleControl();
  await fixture.card.toggleControl();
  return fixture.calls;
}

const tests = [
  test_card_control_toggle_uses_backend_entity_id,
  test_card_control_toggle_does_not_hardcode_default_entity_id,
  test_card_control_toggle_calls_turn_off_when_active,
  test_card_control_toggle_calls_turn_on_when_disabled,
  test_card_control_toggle_is_blocked_while_disabling,
  test_control_toggle_same_button_off_then_on,
  test_control_toggle_is_blocked_only_while_disabling,
  test_control_button_and_disabled_banner_use_same_control_state,
  test_card_control_toggle_reports_missing_entity,
  test_card_control_status_updates_from_backend_state,
];

(async () => {
  if (process.argv.includes("--emit-payloads")) {
    process.stdout.write(JSON.stringify(await emittedPayloads()));
    return;
  }
  for (const test of tests) await test();
  if (failures) process.exit(1);
  console.log("All control switch card tests passed");
})().catch((error) => { console.error(error); process.exit(1); });

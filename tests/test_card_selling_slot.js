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

const cardPath = path.join(
  __dirname,
  "..",
  "custom_components",
  "deye_energy_manager",
  "www",
  "deye-energy-manager-card.js"
);
eval(fs.readFileSync(cardPath, "utf8") + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    failures += 1;
    console.error(`FAIL: ${message}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
  }
}
function assertTrue(value, message) {
  if (!value) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
}
function assertFalse(value, message) {
  if (value) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
}

function entityId(domain, suffix) {
  return `${domain}.deye_energy_manager_${suffix}`;
}

function defaultStates() {
  const states = {
    [entityId("sensor", "manager_status")]: { state: "Normalna Praca", attributes: { mapping_plan: [] } },
  };
  for (let hour = 0; hour < 24; hour++) {
    const next = (hour + 1) % 24;
    const key = `${String(hour).padStart(2, "0")}_${String(next).padStart(2, "0")}`;
    states[entityId("switch", `slot_${key}_enabled`)] = { state: "off", attributes: {} };
    states[entityId("select", `slot_${key}_mode`)] = { state: "Normalna Praca", attributes: {} };
    states[entityId("number", `slot_${key}_tou_soc`)] = { state: "0", attributes: {} };
    states[entityId("number", `slot_${key}_minimum_sell_soc`)] = { state: "0", attributes: {} };
    states[entityId("switch", `slot_${key}_charge_enabled`)] = { state: "off", attributes: {} };
  }
  return states;
}

function makeCard(overrides = {}) {
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._isRendered = true;
  card.captureScrollPositions = () => {};
  card.updateSaveIndicator = () => {};
  card.querySelectorAll = () => [];
  const states = defaultStates();
  for (const [id, value] of Object.entries(overrides)) {
    states[id] = value;
  }
  card._hass = {
    states,
    services: {},
    callService: async () => {},
  };
  return card;
}

function setSlot(states, key, values) {
  const prefix = `slot_${key}`;
  if (values.enabled !== undefined) {
    states[entityId("switch", `${prefix}_enabled`)] = { state: values.enabled ? "on" : "off", attributes: {} };
  }
  if (values.mode !== undefined) {
    states[entityId("select", `${prefix}_mode`)] = { state: values.mode, attributes: {} };
  }
  if (values.touSoc !== undefined) {
    states[entityId("number", `${prefix}_tou_soc`)] = { state: String(values.touSoc), attributes: {} };
  }
  if (values.minimumSellSoc !== undefined) {
    states[entityId("number", `${prefix}_minimum_sell_soc`)] = { state: String(values.minimumSellSoc), attributes: {} };
  }
  if (values.chargeEnabled !== undefined) {
    states[entityId("switch", `${prefix}_charge_enabled`)] = { state: values.chargeEnabled ? "on" : "off", attributes: {} };
  }
}

function findSegmentForHour(segments, hour) {
  return segments.find((segment) => {
    const end = segment.end === 0 ? 24 : segment.end;
    if (segment.start <= end) {
      return segment.start <= hour && hour < end;
    }
    return hour >= segment.start || hour < end;
  });
}

function extractAttribute(html, label, attr) {
  const regex = new RegExp(`<span>${label}</span>[^]*?${attr}="([^"]+)"`, "i");
  const match = html.match(regex);
  return match ? match[1] : null;
}

function test_card_selling_slot_keeps_minimum_sell_soc_and_tou_soc_separate() {
  const slots = (new DeyeEnergyManagerCard()).scheduleSlots();
  const states = {};
  setSlot(states, "06_07", { enabled: true, mode: "Sprzedaż", touSoc: 15, minimumSellSoc: 30 });
  const card = makeCard(states);
  const segments = card.scheduleSegments(slots);
  const segment = findSegmentForHour(segments, 6);
  assertEqual(segment.touSoc, 15, "selling segment must use tou_soc as physical SOC");
  assertEqual(segment.mode, "Sprzedaż", "segment must keep canonical logical mode");
  assertEqual(segment.minimumSellSoc, 30, "segment must keep minimum_sell_soc as logical guard");
}

function test_card_mapping_preview_uses_tou_soc_for_selling() {
  const slots = (new DeyeEnergyManagerCard()).scheduleSlots();
  const states = {};
  setSlot(states, "06_07", { enabled: true, mode: "Sprzedaż", touSoc: 15, minimumSellSoc: 30 });
  setSlot(states, "07_08", { enabled: true, mode: "Normalna Praca", touSoc: 15, minimumSellSoc: 0 });
  const card = makeCard(states);
  const segments = card.scheduleSegments(slots);
  const segment = findSegmentForHour(segments, 6);
  assertEqual(segment.touSoc, 15, "shared physical range must use tou_soc");
  assertEqual(segment.end, 8, "selling and normal hours with same tou_soc/grid must share a physical range");
}

function test_card_selling_slot_save_does_not_copy_minimum_sell_soc_to_tou_soc() {
  const slots = (new DeyeEnergyManagerCard()).scheduleSlots();
  const states = {};
  setSlot(states, "06_07", { enabled: true, mode: "Sprzedaż", touSoc: 15, minimumSellSoc: 30 });
  const card = makeCard(states);
  card._dialog = { type: "sell", key: "06_07" };
  const html = card.renderDialog(slots, []);
  assertTrue(html.includes("Zatrzymaj sprzedaż przy SOC"), "selling dialog must show stop SOC label");
  assertTrue(html.includes("SOC Deye TOU / rezerwa baterii"), "selling dialog must show physical TOU SOC label");
  assertTrue(html.includes('data-slot-draft-field="minimum_sell_soc"'), "stop SOC input must target minimum_sell_soc draft field");
  assertTrue(html.includes('data-slot-draft-field="tou_soc"'), "physical TOU input must target tou_soc draft field");
  assertEqual(card._slotEditDraft.values.minimum_sell_soc, 30, "stop SOC draft must use minimum_sell_soc backend value");
  assertEqual(card._slotEditDraft.values.tou_soc, 15, "physical TOU draft must use tou_soc backend value");
}

function test_card_schedule_segment_key_does_not_include_minimum_sell_soc() {
  const states = {};
  setSlot(states, "06_07", { enabled: true, mode: "Sprzedaż", touSoc: 15, minimumSellSoc: 30 });
  const card = makeCard(states);
  const segmentCode = card.scheduleSegments.toString();
  assertTrue(segmentCode.includes("\"touSoc\""), "schedule segment key must include touSoc");
  assertTrue(segmentCode.includes("\"chargeEnabled\""), "schedule segment key must include chargeEnabled");
  assertFalse(segmentCode.includes("\"minimumSellSoc\""), "schedule segment key must not include minimumSellSoc");
  assertFalse(segmentCode.includes("\"minimum_sell_soc\""), "schedule segment key must not include minimum_sell_soc");
}

function test_both_card_copies_remain_identical() {
  const a = fs.readFileSync(path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js"));
  const b = fs.readFileSync(path.join(__dirname, "..", "www", "deye-energy-manager-card.js"));
  assertTrue(a.length === b.length && a.equals(b), "both card copies must remain identical");
}

(async () => {
  test_card_selling_slot_keeps_minimum_sell_soc_and_tou_soc_separate();
  test_card_mapping_preview_uses_tou_soc_for_selling();
  test_card_selling_slot_save_does_not_copy_minimum_sell_soc_to_tou_soc();
  test_card_schedule_segment_key_does_not_include_minimum_sell_soc();
  test_both_card_copies_remain_identical();

  if (failures) process.exit(1);
  console.log("All selling slot card tests passed");
})();

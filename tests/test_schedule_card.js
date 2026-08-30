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

const modeEntity = "select.deye_energy_manager_slot_06_07_mode";
function hassWithMode(mode, pv = "0") {
  return {
    states: {
      [modeEntity]: { state: mode, attributes: {} },
      "sensor.deye_energy_manager_pv_power": { state: pv, attributes: {} },
    },
    services: { select: { select_option: true }, deye_energy_manager: { apply_schedule_patch: true } },
    callService: async () => {},
  };
}

function makeRenderedCard(mode = "Normalna Praca") {
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = hassWithMode(mode);
  card._isRendered = true;
  card._scheduleEntityIds = [modeEntity];
  card._lastScheduleSignature = `${modeEntity}:${mode}`;
  card.captureScrollPositions = () => {};
  card.updateSaveIndicator = () => {};
  card.querySelectorAll = () => [];
  return card;
}

function makeBulkPanel(values, fields) {
  return {
    querySelector(selector) {
      const raw = selector.match(/^\[data-raw="(.+)"\]$/)?.[1];
      if (raw) return { value: String(values[raw]) };
      const field = selector.match(/^\[data-apply-field="(.+)"\]$/)?.[1];
      if (field) return { checked: Boolean(fields[field]) };
      return null;
    },
  };
}

function makeBulkCard() {
  const card = makeRenderedCard();
  const values = {
    "multi-active": "on",
    "multi-mode": "Sprzedaż",
    "multi-sell-power": "5100",
    "multi-discharge-current": "90",
    "multi-charge-current": "45",
    "multi-min-soc": "30",
    "multi-min-sell-price": "0.45",
  };
  const fields = {
    active: true,
    mode: true,
    sellPower: false,
    dischargeCurrent: false,
    chargeCurrent: false,
    minSoc: true,
    minSellPrice: false,
  };
  const panel = makeBulkPanel(values, fields);
  card.querySelector = (selector) => selector === ".bulk-panel" ? panel : null;
  card.querySelectorAll = () => [];
  card.render = () => {};
  card.captureScrollPositions = () => {};
  card._selectedSlots = new Set(["06_07", "08_09"]);
  return card;
}

(async () => {
  // Etap 1: zmiana encji harmonogramu wymusza render, zmiana samej telemetrii nie.
  {
    const card = makeRenderedCard();
    let renders = 0;
    card.render = () => { renders += 1; };
    card.isInteracting = () => false;
    card.hass = hassWithMode("Sprzedaż");
    assertEqual(renders, 1, "schedule state change must render the card");
  }
  {
    const card = makeRenderedCard();
    let renders = 0;
    card.render = () => { renders += 1; };
    card.updateDynamicValues = () => {};
    card.isInteracting = () => false;
    card.hass = hassWithMode("Normalna Praca", "9000");
    assertEqual(renders, 0, "telemetry-only change must not render the schedule");
  }
  {
    const card = makeRenderedCard();
    let renders = 0;
    let interacting = true;
    card.render = () => { renders += 1; };
    card.updateDynamicValues = () => {};
    card.isInteracting = () => interacting;
    card.hass = hassWithMode("Sprzedaż");
    assertTrue(card._pendingRender, "schedule render must be deferred while editing");
    assertEqual(renders, 0, "deferred schedule update must not interrupt editing");
    interacting = false;
    card.flushPendingRender();
    assertEqual(renders, 1, "deferred schedule update must render after interaction");
  }
  {
    const card = makeRenderedCard();
    let renders = 0;
    card.render = () => { renders += 1; };
    await card.setSelect(modeEntity, "Sprzedaż");
    assertEqual(card._optimisticStates[modeEntity], "Sprzedaż", "slot mode must be optimistic until HA confirms it");
    assertEqual(renders, 1, "slot mode selection must render immediately");
  }

  // Etap 2: boczny przycisk musi mieć listener w głównym dashboardzie.
  {
    const card = makeRenderedCard();
    const listeners = {};
    const applyButton = { addEventListener: (type, handler) => { listeners[type] = handler; } };
    const root = {
      querySelectorAll: (selector) => selector === "[data-apply-multi]" ? [applyButton] : [],
    };
    card.querySelector = (selector) => selector === ".dem-v073" ? root : null;
    let called = 0;
    card.applyMultiEdit = () => { called += 1; };
    card.bindDashboardControls([["06_07", "06:00-07:00", 2]]);
    assertTrue(typeof listeners.click === "function", "dashboard bulk apply button must receive a click listener");
    listeners.click();
    assertEqual(called, 1, "dashboard bulk apply click must call applyMultiEdit once");
  }

  // Pakiet zawiera tylko zaznaczone sloty i zaznaczone pola.
  {
    const card = makeBulkCard();
    let captured = null;
    card.applySchedulePatch = async (updates) => { captured = updates; return true; };
    const slots = [
      ["06_07", "06:00-07:00", 2],
      ["07_08", "07:00-08:00", 2],
      ["08_09", "08:00-09:00", 3],
    ];
    const result = await card.applyMultiEdit(slots);
    assertTrue(result, "valid bulk edit must succeed");
    assertEqual(captured.length, 2, "only selected slots must be sent");
    assertEqual(captured[0].slot_key, "06_07", "first selected slot must be sent");
    assertEqual(captured[1].slot_key, "08_09", "second selected slot must be sent");
    assertEqual(captured[0].mode, "Sprzedaż", "checked mode must be sent canonically");
    assertEqual(captured[0].enabled, true, "checked active state must be sent");
    assertEqual(captured[0].minimum_sell_soc, "30", "checked SOC must be sent");
    assertTrue(!Object.prototype.hasOwnProperty.call(captured[0], "sell_power"), "unchecked sell power must not be sent");
    assertTrue(!Object.prototype.hasOwnProperty.call(captured[0], "charge_current"), "unchecked charge current must not be sent");
  }

  // Trwający zapis blokuje drugie wywołanie, a błąd zachowuje formularz i zaznaczenie.
  {
    const card = makeBulkCard();
    let release;
    let calls = 0;
    card.applySchedulePatch = () => {
      calls += 1;
      return new Promise((resolve) => { release = resolve; });
    };
    const slots = [["06_07", "06:00-07:00", 2], ["08_09", "08:00-09:00", 3]];
    const first = card.applyMultiEdit(slots);
    const second = await card.applyMultiEdit(slots);
    assertEqual(second, false, "second bulk apply must be ignored while save is active");
    assertEqual(calls, 1, "double click must create one service request");
    release(true);
    await first;
  }
  {
    const card = makeBulkCard();
    card.applySchedulePatch = async () => false;
    const slots = [["06_07", "06:00-07:00", 2], ["08_09", "08:00-09:00", 3]];
    const result = await card.applyMultiEdit(slots);
    assertEqual(result, false, "failed bulk edit must report failure");
    assertEqual(card._bulkEditDraft.mode, "Sprzedaż", "failed bulk edit must keep form values");
    assertEqual(card._selectedSlots.size, 2, "failed bulk edit must keep selected slots");
  }

  if (failures) process.exit(1);
  console.log("All schedule card behavior tests passed");
})();

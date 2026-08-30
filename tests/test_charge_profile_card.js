const fs = require("fs");
const path = require("path");

// Minimal browser mock required by the card.
global.window = {
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (id) => clearTimeout(id),
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
};
global.document = {
  scrollingElement: {},
  documentElement: {},
  body: {},
};
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

function makeHass(overrides = {}) {
  const managerStatus = overrides.managerStatus || {
    state: "idle",
    attributes: {},
  };
  return {
    states: {
      "sensor.deye_energy_manager_manager_status": managerStatus,
      "number.deye_energy_manager_charge_profile_charge_current": overrides.chargeCurrentEntity || { state: "unavailable", attributes: {} },
      "number.deye_energy_manager_charge_profile_discharge_current": overrides.dischargeCurrentEntity || { state: "unavailable", attributes: {} },
      "number.deye_energy_manager_charge_profile_grid_charge_current": overrides.gridChargeCurrentEntity || { state: "unavailable", attributes: {} },
      "number.deye_energy_manager_charge_profile_target_soc": overrides.targetSocEntity || { state: "unavailable", attributes: {} },
      "switch.deye_energy_manager_charge_profile_grid_enabled": overrides.gridEnabledEntity || { state: "unavailable", attributes: {} },
    },
    services: { deye_energy_manager: { save_charge_profile: true } },
  };
}

function makeCard(overrides = {}) {
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = makeHass(overrides);
  card.render = () => {};
  card.captureScrollPositions = () => {};
  card.beginSave = () => {};
  card.finishSave = () => {};
  card.failSave = () => {};
  card.updateSaveIndicator = () => {};
  return card;
}

function fakeInput(key, value) {
  return {
    value: String(value),
    dataset: { chargeProfileNumber: key },
    tagName: "INPUT",
    type: "number",
    addEventListener: () => {},
  };
}

function fakeSelect(value) {
  return {
    value: String(value),
    dataset: {},
    tagName: "SELECT",
    addEventListener: () => {},
  };
}

// 1. Brakujące encje nie podstawiają wartości domyślnych; używany jest manager_status.
{
  const card = makeCard({
    managerStatus: {
      state: "idle",
      attributes: {
        charge_profile: {
          grid_charge_enabled: true,
          charge_current: 120,
          discharge_current: 120,
          grid_charge_current: 60,
          target_soc: 80,
        },
      },
    },
  });
  assertEqual(card.chargeProfileNumericValue("charge_profile_target_soc", "target_soc"), "80", "target_soc must come from manager_status when entity is unavailable");
  assertTrue(card.chargeProfileGridEnabled(), "grid_charge_enabled must come from manager_status");
}

// 2. target_soc 100 z manager_status nie jest nadpisywane przez brak encji.
{
  const card = makeCard({
    managerStatus: {
      state: "idle",
      attributes: {
        charge_profile: {
          grid_charge_enabled: false,
          charge_current: 0,
          discharge_current: 0,
          grid_charge_current: 0,
          target_soc: 100,
        },
      },
    },
  });
  assertEqual(card.chargeProfileNumericValue("charge_profile_target_soc", "target_soc"), "100", "target_soc 100 must be preserved");
  assertTrue(!card.chargeProfileGridEnabled(), "grid_charge_enabled false must be preserved");
}

// 3. Zapis szablonu Ładowania działa bez wszystkich encji pomocniczych i ustawia stan oczekujący.
{
  const card = makeCard({
    managerStatus: {
      state: "idle",
      attributes: {
        charge_profile: {
          grid_charge_enabled: false,
          charge_current: 0,
          discharge_current: 0,
          grid_charge_current: 0,
          target_soc: 100,
        },
      },
    },
  });
  card.querySelector = (selector) => {
    if (selector === '[data-raw="charge-profile-grid"]') return fakeSelect("on");
    return null;
  };
  card.querySelectorAll = (selector) => {
    if (selector === "[data-charge-profile-number]") {
      return [
        fakeInput("charge_current", "120"),
        fakeInput("discharge_current", "120"),
        fakeInput("grid_charge_current", "60"),
        fakeInput("target_soc", "80"),
      ];
    }
    return [];
  };
  const calls = [];
  card.callService = (domain, service, data) => {
    calls.push({ domain, service, data });
    return Promise.resolve();
  };
  (async () => {
    const result = await card.saveChargeProfile();
    assertTrue(result, "saveChargeProfile should succeed even with missing helpers");
    assertEqual(calls.length, 1, "saveChargeProfile must call exactly one service");
    assertEqual(calls[0].domain, "deye_energy_manager", "service domain must be deye_energy_manager");
    assertEqual(calls[0].service, "save_charge_profile", "service must be save_charge_profile");
    assertEqual(calls[0].data.target_soc, 80, "saved target_soc must be 80");
    assertEqual(calls[0].data.grid_charge_enabled, true, "saved grid_charge_enabled must be true");
    assertEqual(calls[0].data.charge_current, 120, "saved charge_current must be 120");
    assertEqual(card._chargeProfilePending.target_soc, 80, "pending state must store target_soc 80");
    assertEqual(Object.keys(card._chargeProfileDraft).length, 0, "draft must be cleared after successful save");
  })();
}

// 4. Potwierdzenie przez manager_status usuwa stan oczekujący Ładowania.
{
  const card = makeCard({
    managerStatus: {
      state: "idle",
      attributes: {
        charge_profile: {
          grid_charge_enabled: true,
          charge_current: 120,
          discharge_current: 120,
          grid_charge_current: 60,
          target_soc: 80,
        },
      },
    },
  });
  card._chargeProfilePending = {
    grid_charge_enabled: true,
    charge_current: 120,
    discharge_current: 120,
    grid_charge_current: 60,
    target_soc: 80,
  };
  card.checkChargeProfilePending();
  assertEqual(card._chargeProfilePending, null, "pending state must be cleared after manager_status confirmation");
}

// 5. Przycisk przeładowania Ładowania wysyła force_copy_charge_profile.
{
  const card = makeCard();
  const calls = [];
  card.callService = (domain, service, data) => {
    calls.push({ domain, service, data });
    return Promise.resolve();
  };
  (async () => {
    const result = await card.reloadChargeProfileSlot("12_13");
    assertTrue(result, "reloadChargeProfileSlot should succeed");
    assertEqual(calls.length, 1, "reload must call exactly one service");
    assertEqual(calls[0].service, "apply_schedule_patch", "service must be apply_schedule_patch");
    const updates = JSON.parse(calls[0].data.data);
    assertEqual(updates.length, 1, "patch must contain one update");
    assertEqual(updates[0].slot_key, "12_13", "slot_key must be 12_13");
    assertEqual(updates[0].mode, "Ładowanie", "mode must be canonical Ładowanie");
    assertEqual(updates[0].force_copy_charge_profile, true, "force_copy_charge_profile must be true");
  })();
}

setTimeout(() => {
  if (failures) {
    console.error(`\n${failures} test(s) failed`);
    process.exit(1);
  }
  console.log("All charge profile card behavior tests passed");
  process.exit(0);
}, 50);

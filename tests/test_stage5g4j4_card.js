const fs = require("fs");
const path = require("path");

global.window = {
  confirm: () => true,
  alert: () => {},
  setTimeout,
  clearTimeout,
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: clearTimeout,
};
global.document = { scrollingElement: {}, documentElement: {}, body: {} };
global.HTMLElement = class HTMLElement {};
global.customElements = { define: () => {} };

const cardPath = path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js");
eval(fs.readFileSync(cardPath, "utf8") + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
const check = (condition, message) => {
  if (!condition) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
};

function proposal(hour, action = "sell") {
  const slotKey = `${String(hour).padStart(2, "0")}_${String((hour + 1) % 24).padStart(2, "0")}`;
  return {
    day: "today",
    date: "2026-07-18",
    hour,
    label: `${String(hour).padStart(2, "0")}:00`,
    action,
    proposed: true,
    profile_id: "profile",
    planned_energy_kwh: 1,
    planned_power_w: action === "sell" ? 1000 : 0,
    confidence: 90,
    actual_confidence: 90,
    action_contract: {
      deployment_ready: true,
      schedule_update: action === "sell"
        ? { slot_key: slotKey, enabled: true, mode: "Sprzedaż", sell_power: 1000 }
        : { slot_key: slotKey, enabled: true, mode: "Ładowanie", charge_current: 80, discharge_current: 30, grid_charge_current: 40, tou_soc: 80, charge_enabled: true },
    },
  };
}

async function run() {
  const selectedRow = proposal(19);
  const unselectedRow = proposal(20);
  const candidate = {
    ...proposal(21),
    action: "none",
    proposed: false,
    candidate_action: "sell",
    candidate_power_w: 1000,
    candidate_energy_kwh: 1,
    proposal_block_reason: "confidence_below_profile_minimum",
  };
  const unchanged = { day: "today", date: "2026-07-18", hour: 22, action: "none", proposed: false };
  const planner = {
    rows: [selectedRow, unselectedRow, candidate, unchanged],
    plan_status: "ready",
    recommended_write: true,
    recommended_write_by_day: { today: { allowed: true } },
    execution_readiness: { by_day: { today: { status: "confirmable" } } },
    selected_strategy: "balanced",
    data_quality: {},
  };
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = { states: {} };
  card.aiPlannerData = () => planner;
  card.aiSuggestions = () => [];
  card.saveAiAnalysis = () => {};
  card.startSell = async () => {};
  card.render = () => {};
  card._aiShow24 = true;
  card._aiSelections = { today: new Set(["19_20"]), tomorrow: new Set(["23_00"]) };
  let captured = null;
  card.applySchedulePatch = async (updates, options) => {
    captured = { updates, options };
    return true;
  };

  await card.applyAiDayPlan([], "today");
  check(captured !== null, "Today apply must call schedule service path");
  check(captured.options.replaceDay === true, "Today payload must declare authoritative replace_day intent");
  check(captured.options.date === "2026-07-18", "Today payload must carry the selected row date");
  check(captured.updates.length === 1, "only selected writable rows may be sent as special actions");
  check(captured.updates[0].slot_key === "19_20", "unselected proposal and candidate-only rows must not be sent");
  check(card._aiSelections.tomorrow.has("23_00"), "Today apply must not mutate Tomorrow selection state");

  const html = card.renderAiProposalView([], planner);
  check(html.includes("Wszystkie pozostałe godziny zostaną ustawione jako Normalna Praca"), "explainer must describe Normal Operation for all remaining hours");
  check(html.includes("odznaczonych propozycji") && html.includes("starych akcji"), "explainer must cover unselected and old actions");
  check(html.includes("Zastosuj wybrane na dziś (1)"), "button count must include selected special actions only");
  check(html.includes("Pozostałe godziny — po zastosowaniu Normalna Praca"), "no-change section must have an unambiguous label");

  captured = null;
  card._aiSelections.today = new Set();
  await card.applyAiDayPlan([], "today");
  check(captured === null, "N=0 must not permit a full-day reset");
  const emptyHtml = card.renderAiProposalView([], planner);
  check(emptyHtml.includes("Zaznacz przynajmniej jedną godzinę") && emptyHtml.includes("disabled"), "N=0 button must stay safely disabled");

  const serviceCard = new DeyeEnergyManagerCard();
  serviceCard.setConfig({});
  serviceCard._hass = {
    states: {},
    services: { deye_energy_manager: { apply_schedule_patch: {} } },
    callService: async (_domain, _service, data) => { captured = JSON.parse(data.data); },
  };
  serviceCard.slotControlEnabled = () => true;
  serviceCard.render = () => {};
  serviceCard.beginSave = () => {};
  serviceCard.finishSave = () => {};
  await serviceCard.applySchedulePatch([selectedRow.action_contract.schedule_update], {
    replaceDay: true,
    date: "2026-07-18",
  });
  check(captured.replace_day === true && captured.date === "2026-07-18", "service payload must represent full-day intent");
  check(Array.isArray(captured.updates) && captured.updates.length === 1, "service wrapper must contain selected special actions only");
}

run().then(() => {
  if (failures) process.exit(1);
  console.log("Stage 5G.4J.4 full-day card tests passed");
}).catch((error) => {
  console.error(error);
  process.exit(1);
});

const fs = require("fs");
const path = require("path");

let confirmation = "";
global.window = {
  confirm: (message) => { confirmation = message; return true; },
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
const source = fs.readFileSync(cardPath, "utf8");
eval(source + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
const check = (condition, message) => {
  if (!condition) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
};

async function run() {
  const date = "2026-07-30";
  const row = {
    day: "tomorrow",
    date,
    hour: 19,
    label: "19:00–20:00",
    action: "sell",
    proposed: true,
    profile_id: "evening_sale",
    planned_energy_kwh: 2.5,
    planned_power_w: 2500,
    sell_price: 1.5,
    confidence: 90,
    actual_confidence: 90,
    action_contract: {
      deployment_ready: true,
      schedule_update: {
        slot_key: "19_20",
        enabled: true,
        mode: "Sprzedaż",
        sell_power: 2500,
      },
    },
  };
  const planner = {
    plan_id: "future-8b",
    plan_status: "proposal",
    selected_strategy: "balanced",
    rows: [
      row,
      {
        day: "tomorrow", date, hour: 18, label: "18:00–19:00",
        action: "sell", proposed: true, profile_id: "evening_sale",
        planned_energy_kwh: 1, planned_power_w: 1000,
        confidence: 90, actual_confidence: 90,
        action_contract: { deployment_ready: true, schedule_update: {
          slot_key: "18_19", enabled: true, mode: "Sprzedaż", sell_power: 1000,
        } },
      },
      {
        day: "tomorrow", date, hour: 17, label: "17:00–18:00",
        action: "none", candidate_action: "sell", proposed: false,
        candidate_power_w: 900, candidate_energy_kwh: 0.9,
        proposal_block_reason: "confidence_below_threshold",
      },
      { day: "tomorrow", date, hour: 16, label: "16:00–17:00", action: "none", proposed: false },
    ],
    recommended_write: true,
    recommended_write_by_day: { tomorrow: { allowed: true } },
    execution_readiness: { by_day: { tomorrow: { status: "confirmable" } } },
    profile_impacts: [{
      profile_id: "evening_sale",
      days: { [date]: { requested_energy_kwh: 16, remaining_energy_kwh: 13.5 } },
    }],
  };

  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = { states: {} };
  card.aiPlannerData = () => planner;
  card._aiDay = "tomorrow";
  card._aiSelections = { today: new Set(), tomorrow: new Set(["19_20"]) };
  card._aiShow24 = true;
  card.render = () => {};
  let saved = null;
  card.callService = async (_domain, service, data) => {
    if (service === "save_future_plan") saved = JSON.parse(data.data);
  };

  const html = card.renderAiProposalView([], planner);
  check(html.includes("jedynymi specjalnymi akcjami kompletnego, datowanego planu na jutro"), "Tomorrow UI must state authoritative special-action ownership");
  check(html.includes("Wszystkie pozostałe godziny otrzymają cel Normalna Praca"), "Tomorrow UI must state Normal target for every remaining hour");
  check(html.includes("wykonanie nastąpi jutro JIT, wyłącznie dla aktualnego slotu"), "Tomorrow UI must explain current-slot JIT execution");

  await card.applyAiDayPlan([], "tomorrow");
  check(saved?.date === date, "FuturePlan payload must carry the target date");
  check(saved?.replace_day === true, "FuturePlan payload must explicitly request replace_day");
  check(saved?.updates?.length === 1 && saved.updates[0].slot_key === "19_20", "frontend sends only selected special actions for backend canonicalization");
  check(!saved?.updates?.some((item) => ["18_19", "17_18", "16_17"].includes(item.slot_key)), "unselected, candidate-only and no-proposal rows must not be sent as special actions");
  check(confirmation.includes("jedynymi specjalnymi akcjami jutrzejszego planu"), "confirmation must explain authoritative Tomorrow scope");
  check(confirmation.includes("wykonany jutro JIT"), "confirmation must explain deferred JIT execution");
  check(source.includes('replace_day: true,'), "card source must retain explicit authoritative FuturePlan flag");

  card._aiSelections.tomorrow = new Set();
  const zeroHtml = card.renderAiProposalView([], planner);
  check(zeroHtml.includes("Zaznacz przynajmniej jedną godzinę"), "N=0 must remain safely disabled");
  check(zeroHtml.includes('data-apply-ai-day="1" disabled'), "N=0 apply button must be disabled");
  card._aiDay = "today";
  const todayHtml = card.renderAiProposalView([], { ...planner, rows: planner.rows.map((item) => ({ ...item, day: "today" })) });
  check(todayHtml.includes("jedynymi specjalnymi akcjami kompletnego planu na dziś"), "Today authoritative explanation must remain intact");
}

run().then(() => {
  if (failures) process.exit(1);
  console.log("Stage 5G.4J.8B authoritative FuturePlan card tests passed");
}).catch((error) => {
  console.error(error);
  process.exit(1);
});

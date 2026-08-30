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
const source = fs.readFileSync(cardPath, "utf8");
eval(source + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
const check = (condition, message) => {
  if (!condition) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
};

const today = "2026-07-29";
const tomorrow = "2026-07-30";
const summary = (day, date, target, planned, reason) => ({
  day,
  date,
  active: true,
  target_energy_kwh: target,
  profile_planned_energy_kwh: planned,
  optimizer_extra_energy_kwh: 0,
  total_proposed_energy_kwh: planned,
  missing_profile_energy_kwh: Math.max(0, target - planned),
  primary_constraint: reason,
  initial_soc_pct: day === "today" ? 35 : 90,
  minimum_soc_pct: 20,
  usable_energy_at_window_start_kwh: 10,
  forecast_home_in_window_kwh: 1,
  forecast_pv_in_window_kwh: 2,
});

const profileInsight = (target, todayPlanned, tomorrowPlanned) => ({
  enabled: true,
  name: target === 6 ? "Poranna sprzedaż" : "Wieczorna sprzedaż",
  target_energy_kwh: target,
  minimum_soc_after: 20,
  days: { today: [], tomorrow: [] },
  day_summaries: {
    today: summary("today", today, target, todayPlanned, "started_hour_duration"),
    tomorrow: summary("tomorrow", tomorrow, target, tomorrowPlanned, "minimum_soc"),
  },
});

const planner = {
  generated_at: "2026-07-29T12:00:00+02:00",
  plan_status: "proposal",
  selected_strategy: "balanced",
  rows: [
    { day: "today", date: today, hour: 12, action: "none", proposed: false },
    { day: "tomorrow", date: tomorrow, hour: 12, action: "none", proposed: false },
  ],
  ui_insights: {
    sale_profiles: {
      morning_sale: profileInsight(6, 0.94, 6),
      evening_sale: profileInsight(16, 16, 12.5),
    },
    price_publication: { tomorrow_status: "complete" },
  },
  profile_impacts: [],
  optimizer_shadow: {},
};

async function run() {
  const card = new DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = { states: {} };
  card.aiProfiles = () => ({ profiles: {
    morning_sale: { enabled: true, target_energy_kwh: 6, start: "06:00", end: "10:00", min_price: 0 },
    evening_sale: { enabled: true, target_energy_kwh: 16, start: "18:00", end: "22:00", min_price: 0 },
  } });
  card._aiExplanationDay = "today";
  const todayHtml = card.renderAiExplanation(planner);
  card._aiExplanationDay = "tomorrow";
  const tomorrowHtml = card.renderAiExplanation(planner);

  check(todayHtml.includes("0,94 kWh") || todayHtml.includes("0.94 kWh"), "Today must render only Today planned fulfillment");
  check(tomorrowHtml.includes("6,00 kWh") || tomorrowHtml.includes("6.00 kWh"), "Tomorrow Morning must render its full daily target and plan");
  check(tomorrowHtml.includes("12,50 kWh") || tomorrowHtml.includes("12.50 kWh"), "Tomorrow Evening must render its own planned value");
  check(tomorrowHtml.includes("16,00 kWh") || tomorrowHtml.includes("16.00 kWh"), "Tomorrow Evening must retain its full 16 kWh daily target");
  check(!tomorrowHtml.includes("budżet energii profilu"), "Known daily constraints must not fall back to profile_energy_budget");
  check(source.includes('unresolved_daily_constraint: "nierozstrzygnięte ograniczenie dziennego celu profilu"'), "neutral daily reason must have a UI label");
  check(source.includes('const dailyTarget = this.asNumber(summary.target_energy_kwh) ?? target;'), "explanation must take target from the selected day summary");

  const row = {
    day: "tomorrow",
    date: tomorrow,
    hour: 19,
    label: "19:00–20:00",
    action: "sell",
    proposed: true,
    profile_id: "morning_sale",
    planned_energy_kwh: 2,
    planned_power_w: 2000,
    sell_price: 1.5,
    confidence: 90,
    actual_confidence: 90,
    action_contract: {
      deployment_ready: true,
      schedule_update: { slot_key: "19_20", enabled: true, mode: "Sprzedaż", sell_power: 2000 },
    },
  };
  const futurePlanner = {
    ...planner,
    rows: [row],
    recommended_write: true,
    recommended_write_by_day: { tomorrow: { allowed: true } },
    execution_readiness: { by_day: { tomorrow: { status: "confirmable" } } },
    profile_impacts: [{
      profile_id: "morning_sale",
      requested_energy_kwh: 99,
      remaining_energy_kwh: 99,
      days: {
        [tomorrow]: {
          requested_energy_kwh: 6,
          remaining_energy_kwh: 4,
          possible_energy_kwh: 6,
        },
      },
    }],
  };
  card.aiPlannerData = () => futurePlanner;
  card._aiSelections = { today: new Set(), tomorrow: new Set(["19_20"]) };
  card._aiShow24 = true;
  card.render = () => {};
  let saved = null;
  card.callService = async (_domain, service, data) => {
    if (service === "save_future_plan") saved = JSON.parse(data.data);
  };
  await card.applyAiDayPlan([], "tomorrow");
  const validation = saved?.slot_validations?.["19_20"];
  check(validation?.target_energy_kwh === 6, "Tomorrow validation must use the date-specific daily target");
  check(validation?.remaining_target_kwh === 4, "Tomorrow validation must use the date-specific daily remainder");
}

run().then(() => {
  if (failures) process.exit(1);
  console.log("Stage 5G.4J.8A daily target card tests passed");
}).catch((error) => {
  console.error(error);
  process.exit(1);
});

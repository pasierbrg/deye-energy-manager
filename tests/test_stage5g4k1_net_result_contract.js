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

const proposal = (day, date, hour, netResult, benefit, extra = {}) => ({
  day,
  date,
  hour,
  label: `${String(hour).padStart(2, "0")}:00–${String((hour + 1) % 24).padStart(2, "0")}:00`,
  action: "sell",
  proposed: true,
  profile_id: "evening_sale",
  planned_energy_kwh: 1,
  planned_power_w: 1000,
  sell_price: 1,
  net_result: netResult,
  benefit,
  confidence: 90,
  actual_confidence: 90,
  soc_after: 60,
  reason_codes: ["terminal_value_delta"],
  action_contract: {
    deployment_ready: true,
    schedule_update: {
      slot_key: `${String(hour).padStart(2, "0")}_${String((hour + 1) % 24).padStart(2, "0")}`,
      enabled: true,
      mode: "Sprzedaż",
      sell_power: 1000,
    },
  },
  ...extra,
});

const today = "2026-08-23";
const tomorrow = "2026-08-24";
const todayFirst = proposal("today", today, 8, 1, 0.1);
const todayHigherNet = proposal("today", today, 9, 100, 50);
const terminalRow = proposal("today", today, 23, 999, 900, { terminal_value: 500 });
const tomorrowFirst = proposal("tomorrow", tomorrow, 6, 2, 0.2);
const tomorrowHigherNet = proposal("tomorrow", tomorrow, 7, 200, 100);

const planner = {
  plan_id: "5g4k1",
  plan_status: "proposal",
  generated_at: "2026-08-23T12:00:00+02:00",
  selected_strategy: "balanced",
  optimized_result: 20,
  baseline_result: 15,
  benefit: 5,
  neutrality_threshold: 0.2,
  rows: [tomorrowHigherNet, terminalRow, todayHigherNet, tomorrowFirst, todayFirst],
  checkpoints: { today_end: 70, tomorrow_05: 65, tomorrow_09: 55, tomorrow_end: 40 },
  data_quality: { learning_stage: "gotowe" },
  profile_impacts: [],
  variants: {},
  ui_insights: {
    comparison: {
      assessment: "better",
      decision_title: "Najlepsza decyzja",
      comparison_details: "Plan jest lepszy od bazowego.",
    },
    sale_profiles: {},
    purchase_ranking: { days: { today: [], tomorrow: [] } },
    price_publication: { tomorrow_status: "complete" },
  },
  recommended_write_by_day: { today: { allowed: true }, tomorrow: { allowed: true } },
  execution_readiness: {
    by_day: { today: { status: "confirmable" }, tomorrow: { status: "confirmable" } },
  },
};

const card = new global.DeyeEnergyManagerCard();
card.setConfig({});
card._hass = { states: {} };
card._aiSelections = { today: new Set(["08_09"]), tomorrow: new Set(["06_07"]) };
card._aiShow24 = true;

const representative = card.aiRepresentativeProposal(planner.rows);
check(representative === todayFirst, "representative proposal must be the first chronological row, not the highest net_result or benefit");

const terminalEconomics = card.aiSlotEconomics(terminalRow);
check(terminalEconomics.slotResult === 999, "net_result must remain the complete slot result");
check(terminalEconomics.baselineSlotDelta === 900, "row benefit must remain a slot-vs-baseline delta");
check(terminalEconomics.terminalValue === 500, "terminal value must remain explicitly detectable");
check(terminalEconomics.marginalDecisionBenefit === null, "row benefit must not be exposed as an isolated marginal decision benefit");

const overviewHtml = card.renderAiOverview([], planner);
const overviewCard = overviewHtml.match(/<section class="ai-metric-card ai-best-decision">[\s\S]*?<\/section>/)?.[0] || "";
check(overviewCard.includes("Przykładowa proponowana zmiana"), "overview must use the safe fallback label");
check(overviewCard.includes("08:00–09:00"), "overview must show the chronological representative Today row");
check(!overviewCard.includes("09:00–10:00") && !overviewCard.includes("23:00–00:00"), "higher net_result and terminal rows must not win overview presentation");
check(!overviewHtml.includes("Najlepsza decyzja"), "backend decision_title must not restore the misleading per-row label");
check(overviewHtml.includes("Wynik modelowany slotu"), "overview must name the modeled slot result explicitly");
check(/nie jest to marginalny zysk wywołany samą decyzją/i.test(overviewHtml), "overview must explain that slot result is not marginal decision benefit");
check(overviewHtml.includes("Korzyść całego planu względem bazowego"), "planner benefit must be labelled as a whole-plan comparison");
check(overviewHtml.includes("Pełny wynik ekonomiczny modelowanego planu przy uwzględnieniu przepływów energii i cen."), "whole-plan result must expose the modeled economic-result contract");

card._aiDay = "today";
const todayHtml = card.renderAiProposalView([], planner);
check(todayHtml.includes("Przykładowa proponowana zmiana"), "Today must use the safe representative label");
check(todayHtml.includes("08:00–09:00"), "Today must select the first chronological proposal for presentation");
check(todayHtml.includes(">Wynik modelowany</th>"), "proposal table must use the unambiguous modeled-result label");
check(todayHtml.includes("Pełny wynik ekonomiczny modelowanego slotu przy uwzględnieniu przepływów energii i cen."), "slot-result tooltip must state the complete-flow contract");
check(todayHtml.includes("Różnica modelowanych wyników slotu względem bazowego"), "detail must not call row benefit a marginal decision gain");
check(/ostatni slot może obejmować wartość terminalną baterii/i.test(todayHtml), "terminal value caveat must be visible");
check(!todayHtml.includes("terminal_value_delta"), "raw backend reason keys must not be exposed");

card._aiDay = "tomorrow";
const tomorrowHtml = card.renderAiProposalView([], planner);
check(tomorrowHtml.includes("06:00–07:00"), "Tomorrow must use the same chronological presentation contract");
check(!tomorrowHtml.includes("Najlepsza decyzja"), "Tomorrow must not restore the misleading label");
check(tomorrowHtml.includes("Wynik modelowany"), "Tomorrow must use the same modeled-result label");

["ai-proposals-view", "ai-plan-table", "ai-decision-grid", "ai-action-footer"].forEach((className) => {
  check(todayHtml.includes(className) && tomorrowHtml.includes(className), `existing Sugestie AI layout class ${className} must remain present`);
});

if (failures) process.exit(1);
console.log("Stage 5G.4K.1 net-result presentation contract tests passed");

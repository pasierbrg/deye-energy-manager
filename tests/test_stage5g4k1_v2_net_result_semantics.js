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

const row = (hour, action, netResult, extra = {}) => ({
  day: "today",
  date: "2026-08-28",
  hour,
  label: `${String(hour).padStart(2, "0")}:00–${String((hour + 1) % 24).padStart(2, "0")}:00`,
  action,
  proposed: action !== "normal",
  planned_energy_kwh: action === "normal" ? 0 : 1,
  planned_power_w: action === "normal" ? 0 : 1000,
  sell_price: extra.sell_price ?? 1,
  effective_buy_price: extra.effective_buy_price ?? 0.5,
  net_result: netResult,
  confidence: 90,
  actual_confidence: 90,
  soc_after: 60,
  reason_codes: [],
  action_contract: {
    deployment_ready: true,
    schedule_update: {
      slot_key: `${String(hour).padStart(2, "0")}_${String((hour + 1) % 24).padStart(2, "0")}`,
      enabled: action !== "normal",
      mode: action === "sell" ? "Sprzedaż" : "Normalna Praca",
      sell_power: action === "sell" ? 1000 : 0,
    },
  },
  ...extra,
});

const normalHigher = row(10, "normal", 10, { proposed: false });
const sellLower = row(11, "sell", 8);
const negativeMarket = row(12, "sell", -1.25, { sell_price: -0.2 });
const planner = {
  plan_id: "5g4k1-v2",
  plan_status: "proposal",
  generated_at: "2026-08-28T12:00:00+02:00",
  selected_strategy: "balanced",
  optimized_result: 16.75,
  baseline_result: 15,
  benefit: 1.75,
  neutrality_threshold: 0.2,
  rows: [sellLower, negativeMarket, normalHigher],
  days: [{ day: "today", balance_pln: 16.75, sold_kwh: 2, bought_kwh: 0, financial_data_complete: true }],
  checkpoints: {},
  data_quality: { learning_stage: "gotowe" },
  profile_impacts: [],
  variants: {},
  ui_insights: {
    comparison: { assessment: "better", decision_title: "Najlepsza decyzja" },
    sale_profiles: {},
    purchase_ranking: { days: { today: [], tomorrow: [] } },
    price_publication: { tomorrow_status: "complete" },
  },
  recommended_write_by_day: { today: { allowed: true } },
  execution_readiness: { by_day: { today: { status: "confirmable" } } },
};

const card = new global.DeyeEnergyManagerCard();
card.setConfig({});
card._hass = { states: {} };
card._aiDay = "today";
card._aiShow24 = true;
card._aiSelections = { today: new Set(["11_12", "12_13"]), tomorrow: new Set() };

const html = card.renderAiProposalView([], planner);
const overview = card.renderAiOverview([], planner);
check(html.includes("Wynik modelowany"), "row.net_result must be presented as a modeled result");
check(html.includes("Pełny wynik ekonomiczny modelowanego slotu przy uwzględnieniu przepływów energii i cen."), "the preferred semantic tooltip must be present");
check(overview.includes("Wynik modelowany całego planu"), "the complete plan result must remain distinct from slot results");
check(overview.includes("Korzyść całego planu względem bazowego"), "the real whole-plan baseline delta must remain distinct");
check(!html.includes("Najlepsza decyzja") && !overview.includes("Najlepsza decyzja"), "backend wording must not turn row.net_result into a best-decision claim");
check(!html.includes("Normalna Praca jest lepszą decyzją o 2") && !overview.includes("Normalna Praca jest lepszą decyzją o 2"), "10 PLN Normal versus 8 PLN Sell must not be described as a 2 PLN marginal decision benefit");
check(/\+10[,.]00 zł/.test(html) && /\+8[,.]00 zł/.test(html), "both modeled row results must remain numerically unchanged");
check(/-1[,.]25 zł/.test(html), "negative market-result presentation must remain stable");

const sameSlotNormal = row(13, "normal", 10, { proposed: false });
const sameSlotSell = row(13, "sell", 8);
check(card.aiSlotEconomics(sameSlotNormal).marginalDecisionBenefit === null, "Normal alternative must not synthesize a decision delta");
check(card.aiSlotEconomics(sameSlotSell).marginalDecisionBenefit === null, "Sell alternative must not synthesize a decision delta");
check(!/net_result\s*[-+]\s*[^;\n]*net_result/.test(source), "frontend must not derive a delta by subtracting row.net_result values");

const unavailableBuyPlanner = {
  ...planner,
  plan_status: "blocked",
  optimized_result: null,
  baseline_result: null,
  benefit: null,
  rows: [row(14, "normal", null, { proposed: false, financial_data_complete: false })],
  days: [{ day: "today", balance_pln: null, financial_data_complete: false }],
  recommended_write: false,
  recommended_write_by_day: { today: { allowed: false, reason: "financial_data_incomplete" } },
};
const unavailableHtml = card.renderAiOverview([], unavailableBuyPlanner);
check(!unavailableHtml.includes("Najlepsza decyzja"), "missing BUY prices must not create a false best-decision label");
check(unavailableHtml.includes("wynik częściowy — brak cen"), "missing prices must remain explicit and fail-closed in presentation");

check(!source.includes("gwarantowany zysk"), "UI must not promise a guaranteed profit");
check(source.startsWith("// Resource revision: v=0.8.0.44"), "resource revision must be v=0.8.0.44");

if (failures) process.exit(1);
console.log("Stage 5G.4K.1 v2 net-result semantic contract tests passed");

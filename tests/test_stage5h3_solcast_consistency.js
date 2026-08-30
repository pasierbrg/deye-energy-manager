const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(
  "custom_components/deye_energy_manager/www/deye-energy-manager-card.js",
  "utf8",
);
const sandbox = {
  console,
  HTMLElement: class {},
  customElements: { define() {} },
  setTimeout,
  clearTimeout,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(`${source}\nthis.Card = DeyeEnergyManagerCard;`, sandbox);

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const card = new sandbox.Card();
card._historyFilters = { from: "", to: "", type: "all" };
card.historyData = () => ({
  analyses: [],
  monthly: [],
  solcast: [],
  daily: [{
    date: "2026-08-29",
    forecast_kwh: 33.10,
    actual_kwh: 31.10,
    accuracy_percent: null,
    realization_today_pct: 94.0,
  }],
});
card.filteredAnalyses = () => [];

const history = card.renderHistoryTab();
check(history.includes("W toku (94.0% realizacji)"), "history must render canonical realization");
check(!history.includes("78.8%"), "history must not retain the mismatched denominator result");
check(
  source.includes("solcastAccuracyAttrs.realization_today_pct"),
  "main Solcast card must read canonical realization_today_pct",
);
check(
  source.includes("solcastAccuracyAttrs.historical_accuracy_pct"),
  "historical accuracy must be a separate frontend field",
);
check(
  source.includes("solcastAccuracyAttrs.forecast_difference_today_kwh"),
  "difference must come from the canonical backend contract",
);
check(
  !source.includes("dailyPvValue - solcastForecastValue"),
  "frontend must not independently calculate the difference",
);
check(
  !source.includes("solcastAccuracyAttrs.forecast_progress_percent"),
  "main card must not consume the legacy progress alias",
);
check(
  source.includes("aiState?.attributes?.solcast_current_day"),
  "local suggestions must consume the canonical Solcast context",
);
for (const field of [
  "forecastTodayKwh",
  "productionTodayKwh",
  "remainingForecastKwh",
  "realizationTodayPct",
  "historicalAccuracyPct",
  "forecastTomorrowKwh",
]) {
  check(source.includes(field), `AI history must preserve explicit ${field}`);
}
check(source.startsWith("// Resource revision: v=0.8.0.44"), "resource revision must be .44");

console.log("Stage 5H.3 Solcast frontend contract checks passed");

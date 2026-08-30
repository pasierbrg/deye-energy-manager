const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync("custom_components/deye_energy_manager/www/deye-energy-manager-card.js", "utf8");
const sandbox = { console, HTMLElement: class {}, customElements: { define() {} }, setTimeout, clearTimeout };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(`${source}\nthis.Card = DeyeEnergyManagerCard;`, sandbox);

function check(condition, message) { if (!condition) throw new Error(message); }
const card = new sandbox.Card();
card._config = {};
card._hass = { states: {} };

const emptyContract = {
  source_adapter: "pstryk",
  today_entity: "",
  tomorrow_entity: "",
  semantic_scope: "all_in_variable",
  price_basis: "gross",
  unit: "PLN/kWh",
};
const editor = card.renderPriceContract("buy", emptyContract);
check(editor.includes("Today — mapowanie nadrzędne") && editor.includes("brak"), "BUY Today must render empty read-only mapping");
check(!editor.includes('data-contract-field="today_entity"'), "tariff editor must not edit BUY Today mapping");
check(!editor.includes('data-contract-field="tomorrow_entity"'), "tariff editor must not edit BUY Tomorrow mapping");
check(!editor.includes("sensor.pstryk_aio_"), "editor must not inject a Pstryk entity default");

const unmapped = (day) => ({
  mapped_entity: "",
  resolved_entity: "",
  stable_identity_status: "unmapped",
  detected_adapter: "pstryk",
  resolved_schema: "unknown",
  list_attribute: "",
  value_field: "",
  unit: "PLN/kWh",
  semantic_scope: "all_in_variable",
  coverage_hours: 0,
  status: "unmapped",
  reason: "user_unmapped",
  day,
});
const rceRows = Array.from({ length: 48 }, (_, index) => ({
  day: index < 24 ? "today" : "tomorrow",
  hour: index % 24,
  quality: "ready",
  final_price_pln_kwh: 0.8,
}));
const canonical = {
  schema_version: 1,
  buy: {
    contract: emptyContract,
    rows: [],
    diagnostics: {
      status: "price_source_not_configured", coverage_today: 0, coverage_tomorrow: 0,
      resolver: { today: unmapped("today"), tomorrow: unmapped("tomorrow") },
    },
  },
  sell: {
    contract: { source_adapter: "rce_pse", semantic_scope: "energy_only", price_basis: "gross", unit: "PLN/kWh", granularity: "15m" },
    rows: rceRows,
    diagnostics: {
      status: "ready", coverage_today: 24, coverage_tomorrow: 24,
      resolver: { today: {}, tomorrow: {} },
    },
  },
};
card._hass = { states: {
  "sensor.deye_energy_manager_ai_state": { attributes: { planner_48h: { canonical_prices: canonical } } },
} };
check(card.canonicalPriceMaps("buy")[0].size === 0, "unmapped BUY must have no canonical rows");
check(card.canonicalPriceMaps("sell")[0].size === 24, "independent RCE SELL Today must remain available");
check(card.canonicalPriceMaps("sell")[1].size === 24, "independent RCE SELL Tomorrow must remain available");
const diagnostics = card.renderPriceDiagnostics({ price_diagnostics: canonical, price_contracts: { buy: emptyContract } });
check(diagnostics.includes("źródło cen nie skonfigurowane"), "missing direction status must be readable");
check(diagnostics.includes("nie skonfigurowano") && diagnostics.includes("usunięto w mapowaniu"), "explicit empty reason must be readable");
check(diagnostics.includes("brak"), "empty mapped entity must be displayed as missing");
check(!diagnostics.includes("sensor.pstryk_aio_"), "diagnostics must not display a provider fallback");
check(source.startsWith("// Resource revision: v=0.8.0.44"), "resource revision must be v=0.8.0.44");
console.log("stage5g4k3b explicit-empty card contract OK");

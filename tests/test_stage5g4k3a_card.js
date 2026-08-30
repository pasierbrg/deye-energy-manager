const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync("custom_components/deye_energy_manager/www/deye-energy-manager-card.js", "utf8");
const sandbox = { console, HTMLElement: class {}, customElements: { define() {} }, setTimeout, clearTimeout };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(`${source}\nthis.Card = DeyeEnergyManagerCard;`, sandbox);

function check(condition, message) { if (!condition) throw new Error(message); }
const rows = (direction, todayValue, tomorrowValue) => Array.from({ length: 48 }, (_, index) => ({
  day: index < 24 ? "today" : "tomorrow",
  hour: index % 24,
  direction,
  quality: "ready",
  final_price_pln_kwh: index < 24 ? todayValue : tomorrowValue,
}));
const resolver = (mapped, resolved, adapter, schema, listAttribute) => ({
  mapped_entity: mapped,
  resolved_entity: resolved,
  stable_identity_status: mapped === resolved ? "mapped_entity" : "renamed_resolved",
  detected_adapter: adapter,
  resolved_schema: schema,
  list_attribute: listAttribute,
  value_field: adapter === "rce_pse" ? "rce_pln" : "price",
  unit: "PLN/kWh",
  semantic_scope: adapter === "pstryk" ? "all_in_variable" : "energy_only",
  coverage_hours: 24,
  status: "ready",
  reason: mapped === resolved ? "" : "resolved_by_stable_identity",
});

const canonical = {
  schema_version: 1,
  buy: {
    contract: { source_adapter: "pstryk", semantic_scope: "all_in_variable", unit: "PLN/kWh", price_basis: "gross", granularity: "60m" },
    rows: rows("buy", 0.31, 0.32),
    diagnostics: {
      status: "ready", coverage_today: 24, coverage_tomorrow: 24,
      resolver: {
        today: resolver("sensor.old_buy", "sensor.moja_cena", "pstryk", "pstryk_aio_interval_v1", "today_prices"),
        tomorrow: resolver("sensor.buy_tomorrow", "sensor.buy_tomorrow", "pstryk", "pstryk_aio_interval_v1", "tomorrow_prices"),
      },
    },
  },
  sell: {
    contract: { source_adapter: "rce_pse", semantic_scope: "energy_only", unit: "PLN/kWh", price_basis: "gross", granularity: "15m" },
    rows: rows("sell", 0.81, 0.82),
    diagnostics: {
      status: "ready", coverage_today: 24, coverage_tomorrow: 24,
      resolver: {
        today: resolver("sensor.sell_today", "sensor.sell_today", "rce_pse", "rce_interval_v1", "prices"),
        tomorrow: resolver("sensor.sell_tomorrow", "sensor.sell_tomorrow", "rce_pse", "rce_interval_v1", "prices"),
      },
    },
  },
};

const card = new sandbox.Card();
card._config = {};
card._hass = { states: {
  "sensor.deye_energy_manager_ai_state": { attributes: { planner_48h: { canonical_prices: canonical } } },
} };

const buy = card.canonicalPriceMaps("buy");
const sell = card.canonicalPriceMaps("sell");
check(buy[0].size === 24 && buy[1].size === 24, "Pstryk canonical Today/Tomorrow must render 24/24");
check(sell[0].size === 24 && sell[1].size === 24, "RCE canonical Today/Tomorrow must render 24/24");
check(buy[0].get(7) === 0.31 && buy[1].get(7) === 0.32, "BUY days must remain independent");
check(sell[0].get(7) === 0.81 && sell[1].get(7) === 0.82, "SELL must remain independent from BUY");

const html = card.renderPriceDiagnostics({ price_diagnostics: canonical, price_contracts: {} });
check(html.includes("Resolver mapowanych encji"), "resolver diagnostics heading missing");
check(html.includes("sensor.old_buy") && html.includes("sensor.moja_cena"), "mapped/resolved rename status must be visible");
check(html.includes("pstryk_aio_interval_v1") && html.includes("rce_interval_v1"), "resolved schemas must be visible");
check(html.includes("today_prices") && html.includes("tomorrow_prices"), "Pstryk list attributes must be visible");
check(html.includes("24/24"), "coverage must be visible");
check(!html.includes("stable-entry") && !html.includes("config_entry_id"), "technical registry IDs must stay hidden");
check(source.includes("Frontend nie odczytuje ani nie zgaduje schematu"), "backend-only parsing contract missing");
check(source.startsWith("// Resource revision: v=0.8.0.44"), "resource revision must be 0.8.0.44");
console.log("stage5g4k3a card contract OK");

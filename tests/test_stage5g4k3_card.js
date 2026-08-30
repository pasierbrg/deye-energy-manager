const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync("custom_components/deye_energy_manager/www/deye-energy-manager-card.js", "utf8");
const sandbox = { console, HTMLElement: class {}, customElements: { define() {} }, setTimeout, clearTimeout };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(`${source}\nthis.Card = DeyeEnergyManagerCard;`, sandbox);
const card = new sandbox.Card();
card._config = {};
card._hass = { states: {
  "sensor.deye_energy_manager_ai_state": { attributes: { planner_48h: { canonical_prices: {
    schema_version: 1,
    buy: { rows: [
      { day: "today", hour: 3, quality: "ready", final_price_pln_kwh: 0.23, source_price_pln_kwh: 0.23, source_semantic_scope: "all_in_variable" },
      { day: "tomorrow", hour: 4, quality: "ready", final_price_pln_kwh: -0.10 },
    ] },
    sell: { rows: [{ day: "today", hour: 5, quality: "ready", final_price_pln_kwh: 1.25 }] },
  } } } },
} };

function check(condition, message) { if (!condition) throw new Error(message); }
const buy = card.canonicalPriceMaps("buy");
check(buy[0].get(3) === 0.23, "today BUY must come from canonical backend row");
check(buy[1].get(4) === -0.10, "negative tomorrow BUY must be retained");
check(card.canonicalPriceMaps("sell")[0].get(5) === 1.25, "SELL must use its independent contract rows");
check(source.includes('this.canonicalPriceMaps(scrollKey.startsWith("buy") ? "buy" : "sell")'), "price tables must use backend canonical rows");
check(!source.includes("price + distributionCost(todayKey, hour)"), "browser must not add OSD to a canonical BUY price");
check(source.includes("Źródło pełne"), "all-in Pstryk breakdown must be labelled as a full source price");
check(source.includes("v=0.8.0.44"), "resource revision must be 0.8.0.44");
console.log("stage5g4k3 card contract OK");

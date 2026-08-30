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

const known = {
  source_adapter: "rce_pse", adapter_summary: "rce_pse",
  resolved_adapter_today: "rce_pse", resolved_adapter_tomorrow: "rce_pse",
  today_entity: "sensor.rce_pse_cena", tomorrow_entity: "sensor.rce_pse_cena_jutro",
  semantic_scope: "energy_only", includes_distribution_variable: false,
  price_basis: "gross", unit: "PLN/kWh",
};
const knownEditor = card.renderPriceContract("buy", known);
check(knownEditor.includes("automatyczne / tylko odczyt"), "known adapter must be read-only");
check(knownEditor.includes("sensor.rce_pse_cena"), "current central mapping must be displayed");
check(!knownEditor.includes("data-price-contract"), "known adapter must not submit technical contract fields");
check(!knownEditor.includes('data-contract-field="today_entity"'), "tariff editor must never edit mapped entities");

const custom = {
  source_adapter: "custom", adapter_summary: "custom",
  resolved_adapter_today: "custom", resolved_adapter_tomorrow: "unmapped",
  today_entity: "sensor.my_custom_prices", tomorrow_entity: "",
  semantic_scope: "energy_only", includes_distribution_variable: false,
  price_basis: "gross", unit: "PLN/kWh", list_attribute: "hourly", value_field: "amount",
};
const customEditor = card.renderPriceContract("buy", custom);
check(customEditor.includes("Zaawansowane / Custom"), "custom advanced editor must remain available");
check(customEditor.includes('data-contract-field="value_field"'), "custom schema must remain editable");
check(!customEditor.includes('data-contract-field="today_entity"'), "custom mapping still belongs to Options Flow");

card.tariffData = () => ({
  mode: "automatic", provider: "pge", plan: "g11", providers: [], tariffs: [],
  price_source: "pstryk", price_contracts: { buy: known, sell: known }, hourly_profile: [],
});
const tariffHtml = card.renderTariffTab();
check(!tariffHtml.includes('data-tariff-field="price_source"'), "legacy price source selector must not be runtime authority");
check(tariffHtml.includes("Wykryte źródło:"), "UI must present a derived source instead of a selector");
check(source.startsWith("// Resource revision: v=0.8.0.44"), "resource revision must be v=0.8.0.44");
console.log("stage5g4k3b1 v2 source authority card OK");

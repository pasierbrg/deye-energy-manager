const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync("custom_components/deye_energy_manager/www/deye-energy-manager-card.js", "utf8");
const sandbox = { console, HTMLElement: class {}, customElements: { define() {} }, setTimeout, clearTimeout };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(`${source}\nthis.Card = DeyeEnergyManagerCard;`, sandbox);

function check(condition, message) { if (!condition) throw new Error(message); }
function count(text, needle) { return text.split(needle).length - 1; }

const card = new sandbox.Card();
card._config = {};
card._hass = { states: {} };

function known(adapter, direction) {
  const role = adapter === "pstryk"
    ? (direction === "buy" ? "retail_buy_all_in" : "prosumer_sell")
    : (direction === "buy" ? "energy_only" : "market_reference");
  return {
    source_adapter: adapter,
    adapter_summary: adapter,
    resolved_adapter_today: adapter,
    resolved_adapter_tomorrow: adapter,
    today_entity: `sensor.${adapter}_${direction}_today`,
    tomorrow_entity: `sensor.${adapter}_${direction}_tomorrow`,
    stable_identity_today_status: "bound",
    stable_identity_tomorrow_status: "bound",
    resolved_source_today: { economic_role: role, semantic_scope: adapter === "pstryk" ? "all_in_variable" : "energy_only", includes_distribution_variable: adapter === "pstryk" },
    resolved_source_tomorrow: { economic_role: role, semantic_scope: adapter === "pstryk" ? "all_in_variable" : "energy_only", includes_distribution_variable: adapter === "pstryk" },
  };
}

function tariffData(provider = "pge", plan = "g11", contracts = null) {
  return {
    mode: provider === "other" || plan === "custom" ? "manual" : "automatic",
    provider,
    plan,
    provider_name: provider === "other" ? "Inny operator" : "PGE Dystrybucja",
    plan_name: plan.toUpperCase(),
    configured: true,
    providers: [
      { id: "pge", name: "PGE Dystrybucja", tariffs: [{ id: "g11", name: "G11" }] },
      { id: "other", name: "Inny operator", tariffs: [{ id: "custom", name: "Profil ręczny" }] },
    ],
    tariffs: provider === "other" ? [{ id: "custom", name: "Profil ręczny" }] : [{ id: "g11", name: "G11" }],
    hourly_profile: [],
    price_contracts: contracts || { buy: known("pstryk", "buy"), sell: known("pstryk", "sell") },
    price_diagnostics: {},
  };
}

card.tariffData = () => tariffData();
const standard = card.renderTariffTab();
const standardBlock = standard.split('<section class="diagnostic-section"><h3>Ustawienia operatora i taryfy</h3>', 2)[1].split("</section>", 1)[0];

check(count(standardBlock, "data-tariff-field=") === 2, "standard tariff block must have exactly two editable tariff fields");
check(standardBlock.includes('data-tariff-field="osd_provider"'), "standard tariff block must edit OSD provider");
check(standardBlock.includes('data-tariff-field="tariff_plan"'), "standard tariff block must edit tariff");
check(!standard.includes('data-tariff-field="tariff_mode"'), "legacy tariff mode selector must be hidden");
check(!standard.includes("manual-osd-profile"), "manual OSD fields must not render for catalog tariff");
check(!standard.includes("data-price-contract"), "known adapters must expose no contract override");
check(count(standard, "price-mapping-summary-row") === 4, "standard view must summarize exactly four central mappings");
check(standard.includes("Encje cen BUY/SELL konfiguruje się w ustawieniach integracji."), "mapping authority note missing");
check(standard.includes("Wykryte źródło: pstryk / pstryk"), "detected adapters must be informational");
check(standard.includes("OSD zawarte"), "Pstryk BUY must say OSD is included");
check(standard.includes('<details class="diagnostic-section tariff-advanced">'), "polarity must be in collapsed Advanced");
check(!standard.includes('<details class="diagnostic-section tariff-advanced" open'), "Advanced must be collapsed by default");
check(standard.includes('<details class="diagnostic-section tariff-price-diagnostics">'), "technical diagnostics must remain available");
check(!standard.includes('<details class="diagnostic-section tariff-price-diagnostics" open'), "technical diagnostics must be collapsed by default");
check(standard.includes("resolver, schema i pokrycie"), "collapsed diagnostics must retain resolver/schema/coverage");

card.tariffData = () => tariffData("other", "custom");
const manual = card.renderTariffTab();
check(manual.includes("manual-osd-profile"), "manual/custom OSD must render manual profile fields");
check(manual.includes('data-tariff-field="distribution_peak_rate"'), "manual peak rate must remain editable");
check(manual.includes('data-tariff-field="distribution_offpeak_rate"'), "manual off-peak rate must remain editable");

const customBuy = {
  source_adapter: "custom",
  adapter_summary: "custom",
  resolved_adapter_today: "custom",
  today_entity: "sensor.custom_buy",
  tomorrow_entity: "",
  economic_role: "energy_only",
  semantic_scope: "energy_only",
  includes_distribution_variable: false,
  price_basis: "gross",
  unit: "PLN/kWh",
};
card.tariffData = () => tariffData("pge", "g11", { buy: customBuy, sell: known("pstryk", "sell") });
const custom = card.renderTariffTab();
check(count(custom, "custom-price-contract") === 1, "only the actual Custom direction must expose advanced source settings");
check(custom.includes('data-contract-field="economic_role"'), "Custom must expose explicit economic role");
check(custom.includes('data-contract-field="value_field"'), "Custom schema must remain editable after expansion");
check(custom.includes("Zaawansowane / Custom — ustawienia własnego źródła"), "Custom section label missing");

const snapshot = card.configurationSnapshot();
check(!Object.prototype.hasOwnProperty.call(snapshot.tariff_settings, "price_source"), "legacy price_source must not be exported in normal UI DTO");
check(source.startsWith("// Resource revision: v=0.8.0.44"), "resource revision must be .44");
console.log("stage5g4k3d UX and semantics card OK");

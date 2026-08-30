const fs = require("fs");
const path = require("path");

global.window = { setTimeout, clearTimeout };
global.document = {};
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

const card = new global.DeyeEnergyManagerCard();
card.setConfig({});
const defaults = card.aiDefaults();
const settingsHtml = card.renderAiGeneralSettings();

check(defaults.minimumAutoSellPowerW === 1000, "minimum automatic Sell defaults to 1000 W");
check(defaults.priceEquivalenceBand === 0.05, "price equivalence band defaults to 0.05 PLN/kWh");
check(settingsHtml.includes("Minimalna moc automatycznej sprzedaży"), "minimum setting is visible in Polish");
check(settingsHtml.includes("Różnica ceny uznawana za zbliżoną"), "price band setting is visible in Polish");
check(settingsHtml.includes("nie ogranicza ręcznego sterowania"), "minimum description preserves manual control");
check(card.aiUiText("higher_value_slot_reserved").includes("droższej godziny"), "future reserve reason is localized");
check(card.aiUiText("near_equal_price_group").includes("zbliżonych cen"), "equivalence reason is localized");
check(card.aiUiText("residual_below_minimum").includes("poniżej"), "minimum residual reason is localized");

if (failures) process.exit(1);
console.log("Stage 5G.4J.10A v2 card tests passed");

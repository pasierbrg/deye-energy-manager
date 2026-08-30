const fs = require("fs");
const path = require("path");

global.window = {
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (id) => clearTimeout(id),
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
};
global.document = { scrollingElement: {}, documentElement: {}, body: {} };
global.HTMLElement = class {};
global.customElements = { define: () => {} };

const cardPath = path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js");
eval(fs.readFileSync(cardPath, "utf8") + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
function check(value, message) {
  if (!value) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
}

const card = new DeyeEnergyManagerCard();
card.setConfig({});

const legacySell = {
  hour: 19,
  proposed: true,
  action: "sell",
  profile_id: "evening_sale",
  planned_energy_kwh: 4,
  confidence: 90,
  actual_confidence: 90,
  planned_power_w: 4000,
  action_contract: {
    deployment_ready: true,
    schedule_update: {
      slot_key: "19_20",
      enabled: true,
      mode: "Sprzedaż",
      sell_power: 4000,
      discharge_current: 76.9231,
      charge_current: 10,
      grid_charge_current: 10,
      minimum_sell_soc: 20,
      tou_soc: 15,
      charge_enabled: false,
    },
  },
};
const sellUpdate = card.aiRowUpdate(legacySell);
check(sellUpdate.sell_power === 4000, "AI Sell must preserve exact sell power");
check(Object.keys(sellUpdate).sort().join(",") === "enabled,mode,sell_power,slot_key", "AI Sell must be power-only");
check(!("discharge_current" in sellUpdate), "legacy sell current must be filtered");

const charge = {
  hour: 2,
  proposed: true,
  action: "charge",
  profile_id: "charging",
  planned_energy_kwh: 1,
  confidence: 90,
  actual_confidence: 90,
  planned_power_w: 1000,
  action_contract: {
    deployment_ready: true,
    schedule_update: {
      slot_key: "02_03",
      enabled: true,
      mode: "Ładowanie",
      charge_current: 20,
      discharge_current: 7,
      grid_charge_current: 20,
      tou_soc: 50,
      charge_enabled: true,
    },
  },
};
check(card.aiRowUpdate(charge).discharge_current === 7, "Charge contract must remain unchanged");

if (failures) process.exit(1);
console.log("Stage 5G.4J.6 power-only Sell card tests passed");

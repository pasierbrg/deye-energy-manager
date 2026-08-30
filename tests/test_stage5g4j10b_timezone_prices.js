const fs = require("fs");
const path = require("path");

global.window = { setTimeout, clearTimeout };
global.document = {};
global.HTMLElement = class HTMLElement {};
global.customElements = { define: () => {} };

const cardPath = path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js");
const source = fs.readFileSync(cardPath, "utf8");
eval(source + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

const card = new global.DeyeEnergyManagerCard();
card.setConfig({});
card._hass = {
  config: { time_zone: "Europe/Warsaw" },
  states: {},
};

const entity = (prices) => ({ state: "unavailable", attributes: { prices } });
const equal = (actual, expected, message) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}: ${JSON.stringify(actual)} !== ${JSON.stringify(expected)}`);
  }
};

[
  "2026-08-24T18:00:00Z",
  "2026-08-24T18:00:00+00:00",
  "2026-08-24T20:00:00+02:00",
].forEach((stamp) => {
  equal(card.priceSlotFromValue(stamp), { date: "2026-08-24", hour: 20 }, `aware conversion ${stamp}`);
});

equal(
  card.priceSlotFromValue("2026-08-24T18:00:00"),
  { date: "2026-08-24", hour: 18 },
  "naive ISO remains local wall time",
);
equal(card.priceSlotFromValue("01:00"), { date: null, hour: 1 }, "plain label");

card._hass.states["sensor.today"] = entity([
  { datetime: "2026-08-24T18:00:00Z", price: 1.1 },
  { datetime: "2026-08-24T23:00:00Z", price: 2.2 },
]);
let maps = card.readPriceMaps(
  "sensor.today",
  "sensor.tomorrow",
  new Date("2026-08-24T10:00:00Z"),
);
equal([...maps[0]], [[20, 1.1]], "today bucket");
equal([...maps[1]], [[1, 2.2]], "tomorrow bucket after UTC midnight crossing");

card._hass.states["sensor.spring"] = entity([
  { datetime: "2026-03-29T00:00:00Z", price: 0 },
  { datetime: "2026-03-29T01:00:00Z", price: -0.25 },
]);
maps = card.readPriceMaps("sensor.spring", null, new Date("2026-03-29T10:00:00Z"));
equal([...maps[0]], [[1, 0], [3, -0.25]], "spring DST skips nonexistent 02:00 and keeps non-positive prices");

card._hass.states["sensor.fall"] = entity([
  { datetime: "2026-10-25T00:00:00Z", price: 1.0 },
  { datetime: "2026-10-25T01:00:00Z", price: 2.0 },
]);
maps = card.readPriceMaps("sensor.fall", null, new Date("2026-10-25T10:00:00Z"));
equal([...maps[0]], [[2, 1.0]], "autumn duplicate local hour keeps first provider value");

console.log("Stage 5G.4J.10B timezone price card tests passed");

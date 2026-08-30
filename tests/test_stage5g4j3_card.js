const fs = require("fs");
const path = require("path");

global.window = {
  innerWidth: 1440,
  setTimeout,
  clearTimeout,
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: clearTimeout,
};
global.document = { scrollingElement: {}, documentElement: {}, body: {} };
global.HTMLElement = class HTMLElement {};
global.customElements = { define: () => {} };

const cardPath = path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js");
eval(fs.readFileSync(cardPath, "utf8") + "\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;");

let failures = 0;
const check = (condition, message) => {
  if (!condition) {
    failures += 1;
    console.error(`FAIL: ${message}`);
  }
};

const card = new DeyeEnergyManagerCard();
card.setConfig({});
card._hass = { states: {} };
card.tariffData = () => ({});
card.aiApiPresentation = () => ({ external: false });

const row = {
  day: "today",
  hour: 19,
  label: "19:00–20:00",
  action: "sell",
  proposed: true,
  profile_id: "evening_sale",
  planned_energy_kwh: 2.917,
  planned_power_w: 2917,
  duration_minutes: 60,
  confidence: 90,
  actual_confidence: 90,
  reason_summary: "Sprzedaż mieści się w budżecie energii 48 h mimo wyższej późniejszej ceny.",
  key_factors: [
    "cena_sprzedazy=1.2546",
    "soc_start=100.0%",
    "rezerwa=20.0%",
    "najlepsza_pozniejsza_cena=1.2737",
  ],
  action_contract: {
    deployment_ready: true,
    schedule_update: {
      slot_key: "19_20",
      enabled: true,
      mode: "Sprzedaż",
      sell_power: 2917,
    },
  },
};
const planner = {
  rows: [row],
  execution_readiness: { by_day: { today: { status: "confirmable" } } },
  recommended_write_by_day: { today: { allowed: true } },
  selected_strategy: "balanced",
  data_quality: {},
};

check(card.aiPlannedSlotPower(row) === 2917, "preview power must use the exact action-contract value");
check(card.aiRowUpdate(row).sell_power === 2917, "apply payload must preserve the exact previewed power");
check(card.aiReadableKeyFactor("cena_sprzedazy=1.2546") === "Cena tej godziny: 1,25 zł/kWh", "sale price must have a readable Polish label and unit");
check(card.aiReadableKeyFactor("soc_start=100.0%") === "SOC na starcie: 100,0%", "SOC must use Polish decimal formatting");
check(card.aiReadableKeyFactor("rezerwa=20.0%") === "Rezerwa: 20,0%", "reserve must use a readable label");
check(card.aiReadableKeyFactor("najlepsza_pozniejsza_cena=1.2737") === "Najlepsza późniejsza cena: 1,27 zł/kWh", "later price must have a readable label and unit");

for (const width of [1440, 390]) {
  global.window.innerWidth = width;
  const html = card.renderAiProposalView([], planner);
  check(html.includes("2917 W"), `rendered ${width}px fixture must show the exact write power`);
  check(html.includes("2,92 kWh"), `rendered ${width}px fixture must show energy derived from quantized power`);
  check(html.includes("Cena tej godziny: 1,25 zł/kWh"), `rendered ${width}px fixture must show readable price`);
  check(html.includes("SOC na starcie: 100,0%"), `rendered ${width}px fixture must show readable SOC`);
  check(
    !html.includes("cena_sprzedazy=")
      && !html.includes("cena_sprzedaży=")
      && !html.includes("soc_start=")
      && !html.includes("najlepsza_pozniejsza_cena=")
      && !html.includes("najlepsza_późniejsza_cena="),
    `rendered ${width}px fixture must hide raw backend keys`,
  );
}

if (failures) process.exit(1);
console.log("Stage 5G.4J.3 card behavior tests passed");

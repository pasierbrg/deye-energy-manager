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
card.setConfig({});
card._hass = { states: {}, config: { time_zone: "Europe/Warsaw" } };

const required = {
  higher_priority_profile_reserve: "Energia zachowana dla profilu o wyższym priorytecie",
  "material_live_input_changed:battery_power": "Przeliczono po istotnej zmianie mocy baterii",
  pv_only_profile: "Profil dopuszcza ładowanie wyłącznie z PV",
  pv_curtailed_by_export_or_inverter_limit: "Produkcja PV ograniczona limitem eksportu lub falownika",
  price_filter_or_no_qualified_hours: "Brak godzin spełniających warunki cenowe",
  core_budget_exceeded: "Przekroczono budżet obliczeń Core",
  price_mapping_cache_invalidated: "Przeliczono po zmianie mapowania cen",
  core_blocked_missing_soc: "Brak wiarygodnych danych SOC",
  missing_prices: "Brak kompletnych danych cenowych",
  no_profitable_hours: "Brak opłacalnych godzin",
};

for (const [code, expected] of Object.entries(required)) {
  const actual = card.aiUiText(code);
  check(actual === expected, `${code} must map to the required Polish label`);
  check(!actual.includes(code), `${code} must not leak as its user-facing label`);
}

const materialFields = {
  soc: "SOC",
  price_today: "cen na dziś",
  price_tomorrow: "cen na jutro",
  solcast: "prognozy Solcast",
  pv: "produkcji PV",
  load: "zużycia domu",
  grid: "przepływu sieci",
  battery_power: "mocy baterii",
  soc_health: "wiarygodności danych SOC",
  soc_freshness: "aktualności danych SOC",
  weather: "prognozy pogody",
};
for (const [field, expectedPart] of Object.entries(materialFields)) {
  const code = `material_live_input_changed:${field}`;
  const actual = card.aiUiText(code);
  check(actual.includes(expectedPart), `${code} must identify the real input in Polish`);
  check(!actual.includes("material_live_input_changed"), `${code} must hide the internal prefix`);
}

check(
  card.aiUiText("material_live_input_changed:unknown_sensor")
    === "Przeliczono po istotnej zmianie danych wejściowych",
  "unknown material input must use the safe Polish prefix fallback",
);
check(
  card.aiUiText("some_future_internal_reason") === "Wystąpiło ograniczenie planu",
  "unknown internal reason must use a neutral Polish fallback",
);
check(
  card.aiUiText("higher_priority_profile_reserve / pv_only_profile")
    === "Energia zachowana dla profilu o wyższym priorytecie / Profil dopuszcza ładowanie wyłącznie z PV",
  "compound limit reasons must map every component",
);

const existing = {
  grid_import_limit: "limit poboru z sieci",
  higher_value_slot_reserved: "energia zachowana dla droższej godziny tego profilu",
  current_voltage_battery_limit: "moc baterii wynikająca z prądu i napięcia",
  battery_discharge_limit: "maksymalna moc rozładowania baterii",
};
for (const [code, expected] of Object.entries(existing)) {
  check(card.aiUiText(code) === expected, `${code} Polish regression`);
  check(card.aiUiText(`limit:${code}`).toLowerCase().includes(expected), `limit:${code} Polish regression`);
}

const evidence = "Kandydaci są dostępni do podglądu; profil nie ma jeszcze wystarczającego evidence.";
check(
  card.aiUiText(evidence)
    === "Kandydaci są dostępni do podglądu; profil nie ma jeszcze wystarczających danych historycznych.",
  "mixed Polish/English evidence sentence must be fully Polish",
);

const socFreshnessSources = {
  own_soc_report: "Bezpośredni raport źródła SOC",
  sibling_health: "Stan źródła SOC potwierdzony przez powiązaną encję",
  "sibling_health:sensor.deye_battery_voltage": "Stan źródła SOC potwierdzony przez powiązaną encję",
  event_observed_at: "Zmiana SOC zaobserwowana przez Home Assistant",
  last_updated_fallback: "Czas ostatniej aktualizacji encji SOC",
  compatibility_fallback: "Zastępcza ocena aktualności SOC",
  no_fresh_source_health: "Brak świeżego potwierdzenia źródła SOC",
};
for (const [code, expected] of Object.entries(socFreshnessSources)) {
  check(card.aiUiText(code) === expected, `${code} SOC freshness source must be user-facing Polish`);
}

const [executionStatus] = card.aiExecutionStatus({
  proposal_status: "blocked",
  deployment_reason: "higher_priority_profile_reserve",
});
check(executionStatus.includes(required.higher_priority_profile_reserve), "Plan and execution must use the mapper");
check(!executionStatus.includes("higher_priority_profile_reserve"), "Plan and execution must not leak raw reason");

check(
  source.includes("this.aiUiText(emptyReason.summary || emptyReason.code || \"no_proposals\")"),
  "empty reason must be routed through the central mapper",
);
check(
  !source.includes("(${this.escapeHtml(emptyReason.code"),
  "normal empty state must not append the raw technical code",
);
check(
  source.includes("this.aiUiText(planner.generation_reason || \"brak\")"),
  "Status planu and Ostatnia analiza must use the central mapper",
);
check(
  source.includes("this.aiUiText(detail.limit_reason || \"brak\")"),
  "Dlaczego ten plan must map binding limits",
);
check(
  source.includes("this.aiUiText(detail.reason_summary)"),
  "Dlaczego ten plan must map reason summaries",
);
check(
  source.includes("this.aiUiText(socDiagnostics.source_health_source || socDiagnostics.freshness_reason || \"brak\")"),
  "SOC freshness source in Data quality must use the central mapper",
);
check(
  source.startsWith("// Resource revision: v=0.8.0.44"),
  "resource revision must be v=0.8.0.44",
);

console.log("Stage 5G.4K.4 user-facing reason translation tests passed");

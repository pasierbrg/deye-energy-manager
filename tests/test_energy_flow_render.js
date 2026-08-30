const assert = require("assert");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const cardPath = path.join(
  root,
  "custom_components",
  "deye_energy_manager",
  "www",
  "deye-energy-manager-card.js",
);

global.window = {
  setTimeout,
  clearTimeout,
  requestAnimationFrame: (callback) => setTimeout(callback, 0),
  cancelAnimationFrame: (handle) => clearTimeout(handle),
  addEventListener() {},
  removeEventListener() {},
  innerWidth: 1280,
  confirm: () => true,
  alert() {},
  customCards: [],
};
global.requestAnimationFrame = window.requestAnimationFrame;
global.cancelAnimationFrame = window.cancelAnimationFrame;
global.localStorage = {
  getItem: () => null,
  setItem() {},
  removeItem() {},
};
global.document = {
  activeElement: null,
  scrollingElement: { scrollTop: 0 },
  documentElement: { scrollTop: 0 },
  body: { scrollTop: 0 },
};
global.ResizeObserver = class {
  observe() {}
  disconnect() {}
};
global.HTMLElement = class {
  constructor() {
    this.innerHTML = "";
    this.clientWidth = 1280;
    this.ownerDocument = {
      activeElement: null,
      addEventListener() {},
      removeEventListener() {},
    };
    this.classList = {
      add() {},
      remove() {},
      toggle() {},
    };
  }

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  contains() {
    return false;
  }

  getBoundingClientRect() {
    return { width: 1280, height: 800, top: 0, left: 0 };
  }

  addEventListener() {}
  removeEventListener() {}
};
global.customElements = { define() {} };

const source = fs.readFileSync(cardPath, "utf8");
eval(`${source}\nglobal.DeyeEnergyManagerCard = DeyeEnergyManagerCard;`);

function makeState(state, attributes = {}) {
  return { state, attributes };
}

function makeHass(managerStatus = "present") {
  const states = {
    "switch.recznie_przemianowane_sterowanie_deye": makeState("on", {
      friendly_name: "Ręcznie przemianowane sterowanie Deye",
    }),
    "sensor.deye_energy_manager_pv_power": makeState("4200"),
    "sensor.deye_energy_manager_grid_power": makeState("-350"),
    "sensor.deye_energy_manager_load_power": makeState("2800"),
    "sensor.deye_energy_manager_battery_power": makeState("1050"),
    "sensor.deye_energy_manager_battery_soc": makeState("67"),
  };

  if (managerStatus === "present") {
    states["sensor.deye_energy_manager_manager_status"] = makeState("Aktywny", {
      control: {
        entity_id: "switch.recznie_przemianowane_sterowanie_deye",
        enabled: true,
        status: "Aktywne",
      },
      planned_manager_action: "Plan testowy",
      executed_manager_action: "Wykonano test",
    });
  } else if (managerStatus === "unavailable") {
    states["sensor.deye_energy_manager_manager_status"] = makeState(
      "unavailable",
      {},
    );
  }

  return {
    states,
    services: {},
    locale: { language: "pl" },
    callService: async () => {},
  };
}

function makeCard(managerStatus = "present") {
  const card = new global.DeyeEnergyManagerCard();
  card.setConfig({});
  card._hass = makeHass(managerStatus);
  return card;
}

function test_energy_flow_panel_renders_without_reference_error() {
  const card = makeCard();
  const html = card.energyFlowPanel();
  assert.match(html, /class="energy-flow-panel"/);
  assert.match(html, /Plan testowy/);
  assert.match(html, /Wykonano test/);
}

function test_card_full_render_with_manager_status_control_contract() {
  const card = new global.DeyeEnergyManagerCard();
  card.setConfig({});
  card.hass = makeHass();
  assert.match(card.innerHTML, /class="dem-v073"/);
  assert.match(card.innerHTML, /class="energy-flow-panel"/);
  assert.match(card.innerHTML, /Plan testowy/);
  assert.match(card.innerHTML, /Wykonano test/);
  assert.match(card.innerHTML, /Sterowanie Deye/);
  assert.match(card.innerHTML, /Aktywne/);
  assert.strictEqual(
    card.controlEntityId(),
    "switch.recznie_przemianowane_sterowanie_deye",
  );
}

function test_card_render_survives_missing_manager_status_entity() {
  const card = new global.DeyeEnergyManagerCard();
  card.setConfig({});
  card.hass = makeHass("missing");
  assert.match(card.innerHTML, /class="energy-flow-panel"/);
}

function test_card_render_survives_unavailable_manager_status_entity() {
  const card = new global.DeyeEnergyManagerCard();
  card.setConfig({});
  card.hass = makeHass("unavailable");
  assert.match(card.innerHTML, /class="energy-flow-panel"/);
}

test_energy_flow_panel_renders_without_reference_error();
test_card_full_render_with_manager_status_control_contract();
test_card_render_survives_missing_manager_status_entity();
test_card_render_survives_unavailable_manager_status_entity();
console.log("energy flow render tests passed");

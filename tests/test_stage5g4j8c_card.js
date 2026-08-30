const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(
  path.join(__dirname, "..", "custom_components", "deye_energy_manager", "www", "deye-energy-manager-card.js"),
  "utf8",
);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function testPendingIsNotCompleted() {
  assert(source.includes('physical_pending: "Oczekuje na falownik"'), "missing physical pending label");
  assert(!source.includes('results[key]?.status === "completed") row.deployment_status = "deployed"'), "legacy false-complete mapping remains");
}

function testConfirmedRequiresBackendConfirmedState() {
  assert(source.includes('results[key]?.status === "confirmed"'), "confirmed backend state is not mapped");
  assert(source.includes('row.deployment_status === "confirmed"'), "confirmed execution label is missing");
}

function testManualOverrideAndMissedAreReadable() {
  assert(source.includes('manual_override: "Zmieniono ręcznie"'), "manual override label missing");
  assert(source.includes('missed: "Pominięto"'), "missed label missing");
}

function testResourceRevision() {
  assert(source.startsWith("// Resource revision: v=0.8.0.44"), "wrong resource revision");
}

[
  testPendingIsNotCompleted,
  testConfirmedRequiresBackendConfirmedState,
  testManualOverrideAndMissedAreReadable,
  testResourceRevision,
].forEach((test) => test());

console.log("5G.4J.8C frontend lifecycle tests passed");

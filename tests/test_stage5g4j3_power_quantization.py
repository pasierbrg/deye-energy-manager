from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


target = _load("stage5g4j3_target", ROOT / "tests" / "test_stage5g4j_target_fulfillment.py")
manager_test = _load("stage5g4j3_manager", ROOT / "tests" / "test_manager_logic.py")
core = target.core


def _sale_plan(
    step_w: float,
    target_kwh: float = 2.9176555,
    *,
    start: str = "19:00",
    end: str = "20:00",
    preferred_power_w: float = 5000,
    basis: str = "battery_to_grid",
) -> tuple[dict, dict, dict]:
    values = target.physical_case(13000)
    values.update({
        "sell_power_minimum_w": 0,
        "sell_power_maximum_w": 13000,
        "sell_power_step_w": step_w,
    })
    values["user_profiles"]["profiles"]["sale"] = target.sale_profile(
        target_kwh,
        preferred_power_w,
        start=start,
        end=end,
        basis=basis,
    )
    plan = core.build_energy_plan(values)
    row = next(item for item in plan["rows"] if item.get("profile_id") == "sale" and item["action"] == "sell")
    return values, plan, row


@pytest.mark.parametrize(
    ("step_w", "expected_power_w", "expected_energy_kwh"),
    [(1, 2917, 2.917), (10, 2910, 2.91), (50, 2900, 2.9)],
)
def test_core_quantizes_before_row_contract_energy_and_fulfillment(
    step_w, expected_power_w, expected_energy_kwh
):
    _values, plan, row = _sale_plan(step_w)
    contract = row["action_contract"]["schedule_update"]
    ledger = plan["profile_fulfillment"]["sale"]
    impact = next(item for item in plan["profile_impacts"] if item["profile_id"] == "sale")

    assert row["planned_power_w"] == expected_power_w
    assert row["candidate_power_w"] == expected_power_w
    assert contract["sell_power"] == expected_power_w
    assert row["action_contract"]["planned_power_w"] == expected_power_w
    assert row["action_contract"]["planned_energy_kwh"] == pytest.approx(expected_energy_kwh)
    assert row["planned_energy_kwh"] == pytest.approx(expected_energy_kwh)
    assert row["battery_to_grid_kwh"] == pytest.approx(expected_energy_kwh)
    assert row["profile_contribution_kwh"] == pytest.approx(expected_energy_kwh)
    assert ledger["fulfilled_kwh"] == pytest.approx(expected_energy_kwh)
    assert ledger["remaining_kwh"] == pytest.approx(2.9176555 - expected_energy_kwh, abs=1e-5)
    assert impact["planned_energy_kwh"] == pytest.approx(expected_energy_kwh)
    assert impact["missing_energy_kwh"] == pytest.approx(2.9176555 - expected_energy_kwh, abs=1e-5)


def test_canonical_quantizer_supports_custom_step_and_never_rounds_up():
    assert core.quantize_power_w(2917.6555, step_w=2.5, minimum_w=0, maximum_w=13000) == 2917.5
    assert core.quantize_power_w(2925, step_w=50, minimum_w=0, maximum_w=2925) == 2900
    assert core.quantize_power_w(1125, step_w=50, minimum_w=100, maximum_w=12000) == 1100
    assert core.quantize_power_w(13001, step_w=50, minimum_w=0, maximum_w=12975) == 12950


def test_started_hour_uses_quantized_power_for_partial_slot_energy():
    values = target.physical_case(13000)
    values.update({
        "generated_at": "2026-07-29T06:24:00+02:00",
        "current_hour": 6,
        "current_hour_remaining_minutes": 36,
        "sell_power_minimum_w": 0,
        "sell_power_maximum_w": 13000,
        "sell_power_step_w": 10,
    })
    values["user_profiles"]["profiles"]["sale"] = target.sale_profile(
        1.751, 5000, start="06:00", end="07:00"
    )
    plan = core.build_energy_plan(values)
    row = next(item for item in plan["rows"] if item.get("profile_id") == "sale" and item["action"] == "sell")

    assert row["duration_minutes"] == 36
    assert row["planned_power_w"] == 2910
    assert row["planned_energy_kwh"] == pytest.approx(1.746)
    assert plan["profile_fulfillment"]["sale"]["fulfilled_kwh"] == pytest.approx(1.746)


def test_redistribution_uses_only_writable_power_quanta():
    _values, plan, _row = _sale_plan(
        50,
        target_kwh=5.85,
        start="18:00",
        end="21:00",
        preferred_power_w=2925,
    )
    rows = [
        row for row in plan["rows"]
        if row.get("profile_id") == "sale"
        and row["action"] == "sell"
        and row["planned_power_w"] > 0
    ]
    ledger = plan["profile_fulfillment"]["sale"]

    assert sorted(row["planned_power_w"] for row in rows) == [50, 2900, 2900]
    assert ledger["fulfilled_kwh"] == pytest.approx(5.85)
    assert ledger["remaining_kwh"] == 0
    assert ledger["solver_passes"] <= 2


def test_sub_step_residual_is_reported_without_solver_churn():
    _values, plan, _row = _sale_plan(
        50,
        target_kwh=2.9004,
        start="18:00",
        end="20:00",
        preferred_power_w=2925,
    )
    ledger = plan["profile_fulfillment"]["sale"]
    rows = [
        row for row in plan["rows"]
        if row.get("profile_id") == "sale"
        and row["action"] == "sell"
        and row["planned_power_w"] > 0
    ]

    assert [row["planned_power_w"] for row in rows] == [2900]
    assert ledger["fulfilled_kwh"] == pytest.approx(2.9)
    assert ledger["remaining_kwh"] == pytest.approx(0.0004, abs=1e-5)
    assert ledger["solver_passes"] <= 2


def test_total_export_fulfillment_uses_quantized_battery_component():
    values = target.physical_case(13000)
    solar = [0] * 24
    solar[19] = 1
    values.update({
        "pv_profile": solar,
        "pv_forecast": [1, 0],
        "pv_forecast_full": [1, 0],
        "sell_power_minimum_w": 0,
        "sell_power_maximum_w": 13000,
        "sell_power_step_w": 10,
    })
    values["user_profiles"]["profiles"]["sale"] = target.sale_profile(
        3.9176555,
        5000,
        start="19:00",
        end="20:00",
        basis="total_export",
        method="constant_power",
    )
    plan = core.build_energy_plan(values)
    row = next(item for item in plan["rows"] if item.get("profile_id") == "sale")
    ledger = plan["profile_fulfillment"]["sale"]

    assert row["planned_power_w"] == 2910
    assert row["battery_to_grid_kwh"] == pytest.approx(2.91)
    assert row["profile_contribution_kwh"] == pytest.approx(row["pv_to_grid_kwh"] + 2.91)
    assert ledger["fulfilled_kwh"] == pytest.approx(row["profile_contribution_kwh"])


def test_runtime_exposes_real_entity_lattice_to_core():
    runtime = manager_test.make_runtime()
    runtime.hass.states.values[manager_test.const.DEFAULT_MAX_SELL_POWER] = manager_test.FakeState(
        "0", attributes={"min": 0, "max": 13000, "step": 10, "unit_of_measurement": "W"}
    )
    inputs = runtime.optimizer_core_inputs()

    assert inputs["sell_power_minimum_w"] == 0
    assert inputs["sell_power_maximum_w"] == 13000
    assert inputs["sell_power_step_w"] == 10


def test_generated_contract_passes_backend_validation_but_raw_value_does_not():
    runtime = manager_test.make_runtime()
    runtime.hass.states.values[manager_test.const.DEFAULT_MAX_SELL_POWER] = manager_test.FakeState(
        "0", attributes={"min": 0, "max": 13000, "step": 1, "unit_of_measurement": "W"}
    )
    _values, _plan, row = _sale_plan(1)
    update = row["action_contract"]["schedule_update"]

    asyncio.run(runtime.async_apply_schedule_patch([update]))
    assert runtime.slots[update["slot_key"]].sell_power == 2917
    with pytest.raises(ValueError, match="fizycznym krokiem"):
        runtime.validate_manual_sell_power_w("sell_power dla 19_20", 2917.6555)

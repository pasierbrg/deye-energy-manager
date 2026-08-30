from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "optimizer_core.py"
BASE_TEST_PATH = ROOT / "tests" / "test_optimizer_core.py"

core_spec = importlib.util.spec_from_file_location("stage5g4j_core", CORE_PATH)
core = importlib.util.module_from_spec(core_spec)
assert core_spec.loader is not None
core_spec.loader.exec_module(core)

base_spec = importlib.util.spec_from_file_location("stage5g4j_base", BASE_TEST_PATH)
base = importlib.util.module_from_spec(base_spec)
assert base_spec.loader is not None
base_spec.loader.exec_module(base)


def physical_case(limit_w: float = 12000) -> dict:
    values = base.inputs()
    values.update({
        "soc": 100,
        "battery_capacity_kwh": 100,
        "min_soc": 0,
        "effective_min_soc": 0,
        "target_soc": 100,
        "pv_profile": [0] * 24,
        "pv_forecast": [0, 0],
        "pv_forecast_full": [0, 0],
        "forecast_correction": 1,
        "load_profile_48h": [0] * 48,
        "min_sell_price": 100,
        "max_sell_power_w": limit_w,
        "effective_power_limit_w": limit_w,
        "battery_discharge_limit_w": limit_w,
        "grid_export_limit_w": 20000,
        "inverter_ac_limit_w": 20000,
        "sell_power_limits_w": {"plan": limit_w},
        # Legacy fulfillment/quantization fixtures exercise strict best-hours.
        # Stage 5G.4J.10A v2 tests opt into the production 0.05 band explicitly.
        "price_equivalence_band": 0,
    })
    return values


def sale_profile(
    target_kwh: float,
    power_w: float,
    *,
    start: str = "18:00",
    end: str = "22:00",
    basis: str = "battery_to_grid",
    method: str = "best_hours",
) -> dict:
    return {
        "enabled": True,
        "start": start,
        "end": end,
        "active_days": ["śr"],
        "priority": "high",
        "goal_character": "required",
        "allow_partial": True,
        "min_price": 0,
        "preferred_power_w": power_w,
        "min_soc_after": 0,
        "target_energy_kwh": target_kwh,
        "target_basis": basis,
        "distribution_method": method,
    }


@pytest.mark.parametrize(
    ("target_kwh", "power_w", "hours"),
    [(4, 2000, 3), (6, 3000, 3), (10, 4000, 3), (16, 5000, 4), (7.5, 2500, 4)],
)
def test_parametric_target_and_profile_power(target_kwh, power_w, hours):
    values = physical_case()
    values["user_profiles"]["profiles"]["sale"] = sale_profile(
        target_kwh,
        power_w,
        start="18:00",
        end=f"{18 + hours:02d}:00",
    )
    ledger = core.build_energy_plan(values)["profile_fulfillment"]["sale"]
    expected = min(target_kwh, power_w / 1000 * hours)
    assert ledger["fulfilled_kwh"] == pytest.approx(expected, abs=1e-5)
    assert ledger["remaining_kwh"] == pytest.approx(target_kwh - expected, abs=1e-5)


def test_started_hour_capacity_is_18_kwh_and_target_moves_forward():
    values = physical_case()
    values.update({
        "generated_at": "2026-07-29T06:24:00+02:00",
        "current_hour": 6,
        "current_hour_remaining_minutes": 36,
        "sell_prices": [{hour: 1 for hour in range(24)} for _ in range(2)],
    })
    values["user_profiles"]["profiles"]["morning"] = sale_profile(
        6, 3000, start="06:00", end="10:00"
    )
    plan = core.build_energy_plan(values)
    rows = [row for row in plan["rows"] if row.get("profile_id") == "morning"]
    ledger = plan["profile_fulfillment"]["morning"]
    assert [(row["hour"], row["profile_contribution_kwh"]) for row in rows] == [
        (6, 1.8), (7, 3.0), (8, 1.2)
    ]
    assert "started_hour_duration" in rows[0]["power_limit_reasons"]
    assert ledger["fulfilled_kwh"] == pytest.approx(6)


def test_evening_real_global_3000_caps_5000_profile_at_12_kwh():
    values = physical_case(3000)
    values["user_profiles"]["profiles"]["evening"] = sale_profile(16, 5000)
    plan = core.build_energy_plan(values)
    ledger = plan["profile_fulfillment"]["evening"]
    assert ledger["fulfilled_kwh"] == pytest.approx(12)
    assert ledger["remaining_kwh"] == pytest.approx(4)
    assert "global_max_sell_power" in ledger["limiting_reasons"]
    assert all(
        row["planned_power_w"] <= 3000
        for row in plan["rows"]
        if row.get("profile_id") == "evening"
    )


def test_evening_profile_5000_reaches_16_when_physical_limit_allows_it():
    values = physical_case(8000)
    values["user_profiles"]["profiles"]["evening"] = sale_profile(16, 5000)
    ledger = core.build_energy_plan(values)["profile_fulfillment"]["evening"]
    assert ledger["fulfilled_kwh"] == pytest.approx(16)
    assert ledger["remaining_kwh"] == 0


def test_post_clamp_shortfall_activates_previously_omitted_slot():
    values = physical_case(5000)
    solar = [0] * 24
    solar[8] = 1
    values.update({
        "pv_profile": solar,
        "pv_forecast": [3, 0],
        "pv_forecast_full": [3, 0],
        "grid_export_limit_w": 5000,
        "sell_prices": [
            {hour: (10 if hour == 8 else 9 if hour == 7 else 8) for hour in range(24)}
            for _ in range(2)
        ],
    })
    values["user_profiles"]["profiles"]["sale"] = sale_profile(
        5, 5000, start="06:00", end="09:00"
    )
    plan = core.build_energy_plan(values)
    ledger = plan["profile_fulfillment"]["sale"]
    assert ledger["solver_passes"] == 2
    assert ledger["fulfilled_kwh"] == pytest.approx(5)
    assert set(ledger["slot_contributions"]) == {"7", "8"}


def test_total_export_uses_one_pv_plus_battery_contribution_everywhere():
    values = physical_case(5000)
    solar = [0] * 24
    solar[18] = 1
    values.update({
        "pv_profile": solar,
        "pv_forecast": [2, 0],
        "pv_forecast_full": [2, 0],
    })
    values["user_profiles"]["profiles"]["sale"] = sale_profile(
        6, 3000, start="18:00", end="20:00", basis="total_export", method="constant_power"
    )
    plan = core.build_energy_plan(values)
    first = next(row for row in plan["rows"] if row.get("profile_id") == "sale")
    ledger = plan["profile_fulfillment"]["sale"]
    impact = next(item for item in plan["profile_impacts"] if item["profile_id"] == "sale")
    assert first["pv_to_grid_kwh"] == pytest.approx(2)
    assert first["battery_to_grid_kwh"] == pytest.approx(1)
    assert first["profile_contribution_kwh"] == pytest.approx(3)
    assert ledger["fulfilled_kwh"] == pytest.approx(6)
    assert impact["planned_energy_kwh"] == pytest.approx(6)


@pytest.mark.parametrize("goal_character", ["preferred", "required"])
@pytest.mark.parametrize("allow_partial", [True, False])
@pytest.mark.parametrize("case", ["sufficient", "insufficient", "price_blocked"])
def test_required_preferred_partial_matrix(goal_character, allow_partial, case):
    physical_limit = 2000 if case == "insufficient" else 8000
    target = 10 if case == "insufficient" else 4
    values = physical_case(physical_limit)
    profile = sale_profile(target, 5000, start="18:00", end="20:00")
    profile["goal_character"] = goal_character
    profile["allow_partial"] = allow_partial
    if case == "price_blocked":
        profile["min_price"] = 2
        values["sell_prices"] = [{hour: 1 for hour in range(24)} for _ in range(2)]
    values["user_profiles"]["profiles"]["sale"] = profile
    plan = core.build_energy_plan(values)
    impact = next(item for item in plan["profile_impacts"] if item["profile_id"] == "sale")
    if case == "sufficient":
        assert impact["planned_energy_kwh"] == pytest.approx(target)
    elif allow_partial and case == "insufficient":
        assert impact["planned_energy_kwh"] == pytest.approx(4)
        assert impact["missing_energy_kwh"] == pytest.approx(6)
    else:
        assert impact["planned_energy_kwh"] == 0
        ledger = plan["profile_fulfillment"]["sale"]
        assert ledger["fulfilled_kwh"] == 0
        assert ledger["remaining_kwh"] == pytest.approx(target)
    if not allow_partial and case != "sufficient":
        assert impact["block_reason"] == "partial_not_allowed"


@pytest.mark.parametrize(
    ("reason", "source_key"),
    [
        ("global_max_sell_power", "plan"),
        ("export_limit", "export"),
        ("inverter_power", "inverter"),
        ("max_sell_power_entity", "entity"),
        ("current_voltage_battery_limit", "current_voltage"),
    ],
)
def test_original_physical_power_limit_reason_is_preserved(reason, source_key):
    values = physical_case(10000)
    values["effective_power_limit_w"] = 2500
    values["battery_discharge_limit_w"] = 2500
    values["sell_power_limits_w"] = {source_key: 2500}
    if source_key == "plan":
        values["max_sell_power_w"] = 2500
    if source_key == "export":
        values["grid_export_limit_w"] = 2500
    if source_key == "inverter":
        values["inverter_ac_limit_w"] = 2500
    values["user_profiles"]["profiles"]["sale"] = sale_profile(
        4, 5000, start="18:00", end="19:00"
    )
    plan = core.build_energy_plan(values)
    row = next(item for item in plan["rows"] if item.get("profile_id") == "sale")
    assert row["power_basis"] == reason
    assert reason in plan["profile_fulfillment"]["sale"]["limiting_reasons"]


def test_profile_power_limit_reason_is_distinct_from_physical_limits():
    values = physical_case(10000)
    values["user_profiles"]["profiles"]["sale"] = sale_profile(
        4, 2000, start="18:00", end="19:00"
    )
    plan = core.build_energy_plan(values)
    row = next(item for item in plan["rows"] if item.get("profile_id") == "sale")
    assert row["power_basis"] == "profile_max_power"
    assert plan["profile_fulfillment"]["sale"]["remaining_kwh"] == pytest.approx(2)

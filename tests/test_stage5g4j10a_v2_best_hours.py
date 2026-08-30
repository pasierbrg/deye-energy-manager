from __future__ import annotations

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


target = _load(
    "stage5g4j10a_target",
    ROOT / "tests" / "test_stage5g4j_target_fulfillment.py",
)
core = target.core
TODAY = "2026-07-29"


def sale_case(
    prices: dict[int, float],
    *,
    target_kwh: float,
    power_w: float = 5000,
    start: str,
    end: str,
    band: float = 0.05,
    minimum_w: float = 1000,
    required: bool = False,
    capacity_kwh: float = 100,
    soc: float = 100,
    min_soc: float = 0,
    load: dict[int, float] | None = None,
    step_w: float = 1,
) -> dict:
    values = target.physical_case(5000)
    today_prices = {hour: 0.1 for hour in range(24)}
    today_prices.update(prices)
    values.update({
        "soc": soc,
        "battery_capacity_kwh": capacity_kwh,
        "min_soc": min_soc,
        "effective_min_soc": min_soc,
        "target_soc": 100,
        "sell_prices": [today_prices, dict(today_prices)],
        "price_equivalence_band": band,
        "minimum_auto_sell_power_w": minimum_w,
        "sell_power_minimum_w": 0,
        "sell_power_step_w": step_w,
        "load_profile_48h": [0.0] * 48,
    })
    for hour, energy in (load or {}).items():
        values["load_profile_48h"][hour] = energy
    profile = target.sale_profile(
        target_kwh,
        power_w,
        start=start,
        end=end,
    )
    profile.update({
        "active_days": ["śr"],
        "goal_character": "required" if required else "preferred",
        "min_soc_after": min_soc,
    })
    values["user_profiles"]["profiles"] = {"sale": profile}
    return values


def sale_rows(plan: dict) -> dict[int, dict]:
    return {
        row["hour"]: row
        for row in plan["rows"]
        if row.get("profile_id") == "sale" and row.get("date") == TODAY
    }


def test_later_100_price_wins_over_earlier_090_with_limited_soc():
    values = sale_case(
        {6: 0.90, 7: 1.00},
        target_kwh=6,
        power_w=3000,
        start="06:00",
        end="08:00",
        capacity_kwh=10,
        soc=50,
        min_soc=20,
    )

    plan = core.build_energy_plan(values)
    rows = sale_rows(plan)

    assert rows[6]["profile_contribution_kwh"] == 0
    assert rows[7]["profile_contribution_kwh"] == pytest.approx(3.0, abs=1e-3)
    assert "higher_value_slot_reserved" in rows[6]["power_limit_reasons"]


def test_near_equal_096_099_preserves_energy_for_later_slot_without_peak_concentration():
    values = sale_case(
        {6: 0.96, 7: 0.99},
        target_kwh=2.8,
        power_w=3000,
        start="06:00",
        end="08:00",
        capacity_kwh=10,
        soc=50,
        min_soc=20,
    )

    rows = sale_rows(core.build_energy_plan(values))

    assert 6 not in rows
    assert rows[7]["planned_power_w"] == pytest.approx(2800, abs=1)
    assert rows[7]["profile_contribution_kwh"] > 0
    assert "near_equal_price_group" in rows[7]["reason_codes"]


def test_large_gap_fixture_keeps_strict_max_profit_order():
    prices = {18: 1.06, 19: 1.39, 20: 1.50, 21: 1.15, 22: 0.97}
    values = sale_case(
        prices,
        target_kwh=16,
        start="18:00",
        end="23:00",
    )

    rows = sale_rows(core.build_energy_plan(values))

    assert {hour: rows.get(hour, {}).get("planned_energy_kwh", 0) for hour in prices} == pytest.approx({
        18: 1.0,
        19: 5.0,
        20: 5.0,
        21: 5.0,
        22: 0.0,
    })


def test_near_equal_group_waterfills_and_reduces_peak_power():
    values = sale_case(
        {19: 0.85, 20: 0.89, 21: 0.90, 22: 0.88},
        target_kwh=16,
        start="19:00",
        end="23:00",
    )

    rows = sale_rows(core.build_energy_plan(values))
    powers = [rows[hour]["planned_power_w"] for hour in (19, 20, 21, 22)]

    assert powers == pytest.approx([4000, 4000, 4000, 4000], abs=1)
    assert max(powers) < 5000
    assert sum(rows[hour]["planned_energy_kwh"] for hour in rows) == pytest.approx(16)


@pytest.mark.parametrize(
    ("prices", "same_group"),
    [({18: 0.85, 19: 0.90}, True), ({18: 0.85, 19: 0.91}, False)],
)
def test_price_band_uses_inclusive_distance_from_group_best(prices, same_group):
    values = sale_case(
        prices,
        target_kwh=6,
        start="18:00",
        end="20:00",
    )
    rows = sale_rows(core.build_energy_plan(values))

    if same_group:
        assert rows[18]["planned_power_w"] == pytest.approx(3000)
        assert rows[19]["planned_power_w"] == pytest.approx(3000)
    else:
        assert rows[18]["planned_power_w"] == pytest.approx(1000)
        assert rows[19]["planned_power_w"] == pytest.approx(5000)


def test_near_equal_equalization_respects_load_driven_dynamic_cap():
    values = sale_case(
        {18: 0.90, 19: 0.89, 20: 0.88, 21: 0.87},
        target_kwh=16,
        start="18:00",
        end="22:00",
        load={20: 2.0},
    )

    plan = core.build_energy_plan(values)
    rows = sale_rows(plan)

    assert rows[20]["planned_power_w"] <= 3000
    assert "dynamic_power_cap" in rows[20]["power_limit_reasons"]
    assert plan["profile_fulfillment"]["sale"]["fulfilled_kwh"] == pytest.approx(16)


def test_small_target_uses_smallest_useful_subset_of_near_equal_group():
    values = sale_case(
        {18: 0.90, 19: 0.89, 20: 0.88, 21: 0.87},
        target_kwh=3,
        start="18:00",
        end="22:00",
    )
    rows = sale_rows(core.build_energy_plan(values))

    assert [hour for hour, row in rows.items() if row["planned_power_w"] > 0] == [18]
    assert rows[18]["planned_power_w"] == 3000


def test_zero_band_preserves_strict_best_hours():
    values = sale_case(
        {18: 0.85, 19: 0.90},
        target_kwh=6,
        start="18:00",
        end="20:00",
        band=0,
    )
    rows = sale_rows(core.build_energy_plan(values))

    assert rows[18]["planned_power_w"] == 1000
    assert rows[19]["planned_power_w"] == 5000


def test_wider_band_is_deterministic():
    values = sale_case(
        {18: 0.80, 19: 0.85, 20: 0.90},
        target_kwh=9,
        start="18:00",
        end="21:00",
        band=0.10,
    )

    first = sale_rows(core.build_energy_plan(values))
    second = sale_rows(core.build_energy_plan(values))

    assert [first.get(hour, {}).get("planned_power_w", 0) for hour in (18, 19, 20)] == [0, 4500, 4500]
    assert [first.get(hour, {}).get("planned_power_w", 0) for hour in (18, 19, 20)] == [
        second.get(hour, {}).get("planned_power_w", 0) for hour in (18, 19, 20)
    ]


@pytest.mark.parametrize(
    ("target_kwh", "step_w", "expected_power"),
    [(0.999, 1, 0), (1.0, 1, 1000), (1.001, 50, 1000)],
)
def test_preferred_minimum_auto_sell_boundary(target_kwh, step_w, expected_power):
    values = sale_case(
        {18: 1.0},
        target_kwh=target_kwh,
        start="18:00",
        end="19:00",
        step_w=step_w,
    )
    rows = sale_rows(core.build_energy_plan(values))

    assert rows[18]["planned_power_w"] == expected_power


@pytest.mark.parametrize("residual", [0.188, 0.210, 0.448])
def test_preferred_subminimum_residual_becomes_explicit_shortfall(residual):
    values = sale_case(
        {18: 1.0, 19: 0.8},
        target_kwh=5 + residual,
        start="18:00",
        end="20:00",
        band=0,
    )

    plan = core.build_energy_plan(values)
    rows = sale_rows(plan)
    ledger = plan["profile_fulfillment"]["sale"]

    assert rows[18]["planned_power_w"] == 5000
    assert rows[19]["planned_power_w"] == 0
    assert "residual_below_minimum" in rows[19]["power_limit_reasons"]
    assert ledger["remaining_kwh"] == pytest.approx(residual, abs=1e-5)


def test_required_profile_may_use_physical_subminimum_to_finish_target():
    values = sale_case(
        {18: 1.0},
        target_kwh=0.188,
        start="18:00",
        end="19:00",
        required=True,
    )
    rows = sale_rows(core.build_energy_plan(values))

    assert rows[18]["planned_power_w"] == 188

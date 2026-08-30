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


target = _load("stage5g4j8a_target", ROOT / "tests" / "test_stage5g4j_target_fulfillment.py")
core = target.core

TODAY = "2026-07-29"
TOMORROW = "2026-07-30"


def daily_case(*, capacity_kwh: float = 100, soc: float = 100) -> dict:
    values = target.physical_case(13000)
    values.update({
        "soc": soc,
        "battery_capacity_kwh": capacity_kwh,
        "current_hour": 0,
        "generated_at": "2026-07-29T00:00:00+02:00",
        "current_hour_remaining_minutes": 60,
        "sell_power_minimum_w": 0,
        "sell_power_maximum_w": 13000,
        "sell_power_step_w": 1,
        "sell_prices": [{hour: 1 + hour / 100 for hour in range(24)} for _ in range(2)],
        "buy_prices": [{hour: 0.5 for hour in range(24)} for _ in range(2)],
    })
    return values


def profile(
    target_kwh: float,
    power_w: float,
    *,
    start: str,
    end: str,
    priority: str = "high",
    goal: str = "required",
    basis: str = "battery_to_grid",
    active_days: list[str] | None = None,
) -> dict:
    result = target.sale_profile(
        target_kwh,
        power_w,
        start=start,
        end=end,
        basis=basis,
    )
    result.update({
        "active_days": [] if active_days is None else active_days,
        "priority": priority,
        "goal_character": goal,
        "min_soc_after": 0,
    })
    return result


def day_ledger(plan: dict, profile_id: str, local_date: str) -> dict:
    return plan["profile_fulfillment"][profile_id]["days"][local_date]


def test_daily_target_and_energy_ledger_are_independent_for_today_and_tomorrow():
    values = daily_case()
    values["user_profiles"]["profiles"]["morning"] = profile(
        6, 3000, start="06:00", end="08:00"
    )
    plan = core.build_energy_plan(values)
    ledger = plan["profile_fulfillment"]["morning"]

    assert list(ledger["days"]) == [TODAY, TOMORROW]
    assert day_ledger(plan, "morning", TODAY)["target_kwh"] == 6
    assert day_ledger(plan, "morning", TOMORROW)["target_kwh"] == 6
    assert day_ledger(plan, "morning", TODAY)["fulfilled_kwh"] == pytest.approx(6)
    assert day_ledger(plan, "morning", TOMORROW)["fulfilled_kwh"] == pytest.approx(6)
    assert ledger["horizon_totals"] == {
        "target_kwh": 12.0,
        "fulfilled_kwh": 12.0,
        "remaining_kwh": 0.0,
    }
    assert ledger["target_kwh"] == 6  # compatibility is one local day, not a 48 h pool


def test_partial_today_never_becomes_tomorrow_remaining_target():
    values = daily_case()
    values.update({
        "current_hour": 23,
        "generated_at": "2026-07-29T23:41:00+02:00",
        "current_hour_remaining_minutes": 19,
    })
    values["user_profiles"]["profiles"]["morning"] = profile(
        6, 2968, start="21:00", end="00:00"
    )
    plan = core.build_energy_plan(values)
    today = day_ledger(plan, "morning", TODAY)
    tomorrow = day_ledger(plan, "morning", TOMORROW)

    assert today["fulfilled_kwh"] == pytest.approx(0.93987, abs=1e-5)
    assert today["remaining_kwh"] == pytest.approx(5.06013, abs=1e-5)
    assert tomorrow["target_kwh"] == 6
    assert tomorrow["fulfilled_kwh"] == pytest.approx(6)
    assert tomorrow["remaining_kwh"] == 0


def test_evening_16_kwh_today_does_not_zero_tomorrow_request():
    values = daily_case()
    values["user_profiles"]["profiles"]["evening"] = profile(
        16, 5000, start="18:00", end="22:00"
    )
    plan = core.build_energy_plan(values)

    for local_date in (TODAY, TOMORROW):
        ledger = day_ledger(plan, "evening", local_date)
        assert ledger["target_kwh"] == 16
        assert ledger["fulfilled_kwh"] == pytest.approx(16)
        assert ledger["remaining_kwh"] == 0


def test_ui_target_plan_shortfall_and_reason_use_the_same_local_date():
    values = daily_case()
    values["user_profiles"]["profiles"]["morning_sale"] = profile(
        6, 2000, start="06:00", end="08:00"
    )
    plan = core.build_energy_plan(values)
    summaries = plan["ui_insights"]["sale_profiles"]["morning_sale"]["day_summaries"]

    for day_name, local_date in (("today", TODAY), ("tomorrow", TOMORROW)):
        summary = summaries[day_name]
        ledger = day_ledger(plan, "morning_sale", local_date)
        assert summary["date"] == local_date
        assert summary["target_energy_kwh"] == ledger["target_kwh"] == 6
        assert summary["profile_planned_energy_kwh"] == pytest.approx(ledger["fulfilled_kwh"])
        assert summary["missing_profile_energy_kwh"] == pytest.approx(ledger["remaining_kwh"])
        assert summary["primary_constraint"] in {
            "profile_max_power",
            "unresolved_daily_constraint",
        }
        assert summary["primary_constraint"] != "profile_energy_budget"


def test_tomorrow_priority_reserves_energy_for_later_higher_profile_same_date():
    values = daily_case(capacity_kwh=22)
    values["user_profiles"]["profiles"] = {
        "morning": profile(
            6, 3000, start="06:00", end="08:00", priority="normal", active_days=["czw"]
        ),
        "evening": profile(
            16, 5000, start="18:00", end="22:00", priority="high", active_days=["czw"]
        ),
    }
    plan = core.build_energy_plan(values)
    morning = day_ledger(plan, "morning", TOMORROW)
    evening = day_ledger(plan, "evening", TOMORROW)
    morning_rows = [
        row for row in plan["rows"]
        if row.get("profile_id") == "morning" and row.get("date") == TOMORROW
    ]

    assert evening["target_kwh"] == 16
    assert evening["fulfilled_kwh"] == pytest.approx(16, abs=1e-4)
    assert morning["fulfilled_kwh"] < 6
    assert any("higher_priority_profile_reserve" in row["power_limit_reasons"] for row in morning_rows)


def test_forecast_pv_between_profiles_reduces_reserve_without_resetting_soc():
    no_pv = daily_case(capacity_kwh=22)
    profiles = {
        "morning": profile(
            6, 3000, start="06:00", end="08:00", priority="normal", active_days=["czw"]
        ),
        "evening": profile(
            16, 5000, start="18:00", end="22:00", priority="high", active_days=["czw"]
        ),
    }
    no_pv["user_profiles"]["profiles"] = profiles
    without = core.build_energy_plan(no_pv)

    with_pv = daily_case(capacity_kwh=22)
    solar = [0] * 24
    solar[12] = 1
    with_pv.update({
        "pv_profile": solar,
        "pv_forecast": [0, 8],
        "pv_forecast_full": [0, 8],
        "forecast_correction": 1,
    })
    with_pv["user_profiles"]["profiles"] = profiles
    with_plan = core.build_energy_plan(with_pv)

    without_morning = day_ledger(without, "morning", TOMORROW)["fulfilled_kwh"]
    with_morning = day_ledger(with_plan, "morning", TOMORROW)["fulfilled_kwh"]
    assert with_morning >= without_morning
    assert with_plan["rows"][23]["soc_end_pct"] == with_plan["rows"][24]["soc_start_pct"]


@pytest.mark.parametrize("basis", ["battery_to_grid", "total_export"])
def test_target_basis_and_quantization_are_applied_per_day(basis):
    values = daily_case()
    values["sell_power_step_w"] = 50
    solar = [0] * 24
    solar[18] = 1
    values.update({
        "pv_profile": solar,
        "pv_forecast": [1, 1],
        "pv_forecast_full": [1, 1],
        "forecast_correction": 1,
    })
    values["user_profiles"]["profiles"]["sale"] = profile(
        3.9176555, 5000, start="18:00", end="19:00", basis=basis
    )
    plan = core.build_energy_plan(values)

    for local_date in (TODAY, TOMORROW):
        row = next(
            row for row in plan["rows"]
            if row.get("profile_id") == "sale" and row.get("date") == local_date
        )
        ledger = day_ledger(plan, "sale", local_date)
        assert row["planned_power_w"] % 50 == 0
        assert ledger["fulfilled_kwh"] == pytest.approx(row["profile_contribution_kwh"])
        assert ledger["remaining_kwh"] == pytest.approx(
            ledger["target_kwh"] - ledger["fulfilled_kwh"], abs=1e-5
        )


def test_started_hour_today_and_full_hour_tomorrow_keep_separate_capacities():
    values = daily_case()
    values.update({
        "current_hour": 6,
        "generated_at": "2026-07-29T06:24:00+02:00",
        "current_hour_remaining_minutes": 36,
    })
    values["user_profiles"]["profiles"]["sale"] = profile(
        3, 3000, start="06:00", end="07:00"
    )
    plan = core.build_energy_plan(values)
    today_row = next(row for row in plan["rows"] if row.get("profile_id") == "sale" and row["date"] == TODAY)
    tomorrow_row = next(row for row in plan["rows"] if row.get("profile_id") == "sale" and row["date"] == TOMORROW)

    assert today_row["duration_minutes"] == 36
    assert today_row["profile_contribution_kwh"] == pytest.approx(1.8)
    assert tomorrow_row["duration_minutes"] == 60
    assert tomorrow_row["profile_contribution_kwh"] == pytest.approx(3)
    assert day_ledger(plan, "sale", TOMORROW)["target_kwh"] == 3


def test_cross_midnight_hours_consume_their_own_calendar_date_pool():
    values = daily_case()
    values["user_profiles"]["profiles"]["sale"] = profile(
        4, 2000, start="22:00", end="02:00", active_days=["śr"]
    )
    plan = core.build_energy_plan(values)
    rows = [row for row in plan["rows"] if row.get("profile_id") == "sale"]

    assert {row["profile_date"] for row in rows} == {TODAY, TOMORROW}
    assert all(row["profile_date"] == row["date"] for row in rows)
    assert day_ledger(plan, "sale", TODAY)["target_kwh"] == 4
    assert day_ledger(plan, "sale", TOMORROW)["target_kwh"] == 4
    assert any(row["hour"] == 23 and row["date"] == TODAY for row in rows)
    assert any(row["hour"] == 0 and row["date"] == TOMORROW for row in rows)


def test_screen_like_morning_evening_fixture_has_independent_tomorrow_constraints():
    values = daily_case(capacity_kwh=45, soc=90)
    values["load_profile_48h"] = [0.25] * 48
    solar = [0] * 24
    for hour in range(9, 16):
        solar[hour] = 1
    values.update({
        "pv_profile": solar,
        "pv_forecast": [8, 10],
        "pv_forecast_full": [8, 10],
        "forecast_correction": 0.9,
    })
    values["user_profiles"]["profiles"] = {
        "morning_sale": profile(6, 3000, start="06:00", end="10:00", priority="normal"),
        "evening_sale": profile(16, 5000, start="18:00", end="22:00", priority="high"),
    }
    plan = core.build_energy_plan(values)

    assert day_ledger(plan, "morning_sale", TOMORROW)["target_kwh"] == 6
    assert day_ledger(plan, "evening_sale", TOMORROW)["target_kwh"] == 16
    for profile_id in ("morning_sale", "evening_sale"):
        tomorrow = day_ledger(plan, profile_id, TOMORROW)
        assert tomorrow["fulfilled_kwh"] + tomorrow["remaining_kwh"] == pytest.approx(
            tomorrow["target_kwh"], abs=1e-5
        )
        assert "profile_energy_budget" not in tomorrow["limiting_reasons"]
    assert plan["rows"][23]["soc_end_pct"] == plan["rows"][24]["soc_start_pct"]
    assert all(
        row["battery_to_home_kwh"] <= row["home_load_kwh"] + 1e-9
        for row in plan["rows"]
    )


def test_daily_split_stays_inside_existing_solver_budget_and_sell_contract():
    values = daily_case()
    values["user_profiles"]["profiles"]["sale"] = profile(
        16, 5000, start="18:00", end="22:00"
    )
    bundle = core.build_plan_bundle(values)
    plan = bundle

    assert all(
        bundle["core_budget"]["usage"][name] <= limit
        for name, limit in bundle["core_budget"]["limits"].items()
    )
    assert plan["profile_fulfillment"]["sale"]["solver_passes"] <= 48
    for row in plan["rows"]:
        if row.get("profile_id") == "sale" and row.get("proposed"):
            update = row["action_contract"]["schedule_update"]
            assert set(update) <= {"slot_key", "enabled", "mode", "sell_power"}

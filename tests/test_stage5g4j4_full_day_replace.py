from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
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


manager_test = _load("stage5g4j4_manager", ROOT / "tests" / "test_manager_logic.py")
manager = manager_test.manager
const = manager_test.const
TODAY = manager.ha_now().date().isoformat()


def sell(slot_key: str, power: float) -> dict:
    return {
        "slot_key": slot_key,
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": power,
    }


def charge(slot_key: str, *, soc: float = 80, grid: bool = True) -> dict:
    return {
        "slot_key": slot_key,
        "enabled": True,
        "mode": const.MODE_CHARGE,
        "charge_current": 87,
        "discharge_current": 31,
        "grid_charge_current": 42,
        "tou_soc": soc,
        "charge_enabled": grid,
    }


def apply_today(runtime, updates: list[dict]) -> None:
    asyncio.run(
        runtime.async_apply_schedule_patch(
            updates,
            replace_day=True,
            date=TODAY,
        )
    )


def test_old_sale_is_removed_and_selected_19_to_midnight_is_authoritative():
    runtime = manager_test.make_runtime()
    for key in ("18_19", "19_20", "20_21"):
        runtime.slots[key].enabled = True
        runtime.slots[key].mode = const.MODE_SELLING_FIRST
        runtime.slots[key].sell_power = 3000
    runtime.slots["18_19"].minimum_sell_soc = 35
    runtime.slots["18_19"].tou_soc = 15

    selected = [
        sell("19_20", 4165),
        sell("20_21", 3928),
        sell("21_22", 3491),
        sell("22_23", 2541),
        sell("23_00", 1875),
    ]
    apply_today(runtime, selected)

    assert runtime.slots["18_19"].mode == const.MODE_NORMAL_OPERATION
    assert runtime.slots["18_19"].sell_power == runtime.normal_profile_sell_power
    assert runtime.slots["18_19"].minimum_sell_soc == 35
    assert runtime.slots["18_19"].tou_soc == 15
    assert all(
        runtime.slots[key].mode == const.MODE_NORMAL_OPERATION
        for key, _label, start, _end in const.SLOTS
        if start < 19
    )
    assert [runtime.slots[item["slot_key"]].sell_power for item in selected] == [
        4165, 3928, 3491, 2541, 1875
    ]
    assert all(
        runtime.slots[item["slot_key"]].mode == const.MODE_SELLING_FIRST
        for item in selected
    )


def test_unselected_proposal_and_hours_without_proposal_become_normal():
    runtime = manager_test.make_runtime()
    for key in ("18_19", "19_20", "20_21", "21_22"):
        runtime.slots[key].enabled = True
        runtime.slots[key].mode = const.MODE_SELLING_FIRST
        runtime.slots[key].sell_power = 3000

    # 18_19 represents an unselected proposal, 21_22 an old/no-proposal action.
    apply_today(runtime, [sell("19_20", 2800), sell("20_21", 2700)])

    assert runtime.slots["18_19"].mode == const.MODE_NORMAL_OPERATION
    assert runtime.slots["21_22"].mode == const.MODE_NORMAL_OPERATION
    assert runtime.slots["19_20"].mode == const.MODE_SELLING_FIRST
    assert runtime.slots["20_21"].mode == const.MODE_SELLING_FIRST


def test_unselected_old_charge_has_no_ghost_grid_charge():
    runtime = manager_test.make_runtime()
    old = runtime.slots["18_19"]
    old.enabled = True
    old.mode = const.MODE_CHARGE
    old.charge_enabled = True
    old.charge_current = 111
    old.grid_charge_current = 77
    old.tou_soc = 63

    apply_today(runtime, [sell("19_20", 2900)])

    cleared = runtime.slots["18_19"]
    assert cleared.mode == const.MODE_NORMAL_OPERATION
    assert cleared.charge_enabled is False
    assert cleared.charge_current == runtime.normal_profile_charge_current
    assert cleared.grid_charge_current == runtime.normal_profile_grid_charge_current
    assert cleared.tou_soc == 63


def test_selected_sell_and_charge_preserve_exact_action_contract_fields():
    runtime = manager_test.make_runtime()
    selected_sell = sell("19_20", 2917)
    selected_charge = charge("20_21", soc=84, grid=True)

    apply_today(runtime, [selected_sell, selected_charge])

    selling = runtime.slots["19_20"]
    charging = runtime.slots["20_21"]
    assert selling.mode == selected_sell["mode"]
    assert selling.sell_power == selected_sell["sell_power"]
    assert selling.ai_sell_power_only is True
    assert charging.mode == selected_charge["mode"]
    assert charging.charge_current == selected_charge["charge_current"]
    assert charging.discharge_current == selected_charge["discharge_current"]
    assert charging.grid_charge_current == selected_charge["grid_charge_current"]
    assert charging.tou_soc == selected_charge["tou_soc"]
    assert charging.charge_enabled is selected_charge["charge_enabled"]


def test_regular_schedule_patch_remains_partial():
    runtime = manager_test.make_runtime()
    runtime.slots["18_19"].enabled = True
    runtime.slots["18_19"].mode = const.MODE_SELLING_FIRST
    runtime.slots["18_19"].sell_power = 3000

    asyncio.run(runtime.async_apply_schedule_patch([sell("19_20", 2917)]))

    assert runtime.slots["18_19"].mode == const.MODE_SELLING_FIRST
    assert runtime.slots["18_19"].sell_power == 3000


def test_quantized_sell_power_still_passes_and_fractional_manual_value_fails():
    runtime = manager_test.make_runtime()
    runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = manager_test.FakeState(
        "0", attributes={"min": 0, "max": 13000, "step": 1, "unit_of_measurement": "W"}
    )
    apply_today(runtime, [sell("19_20", 2917)])
    assert runtime.slots["19_20"].sell_power == 2917

    with pytest.raises(ValueError, match="fizycznym krokiem"):
        apply_today(runtime, [sell("19_20", 2917.6555)])


def test_full_day_diff_only_does_not_schedule_reconciliation_when_already_equal():
    runtime = manager_test.make_runtime()
    normal_physical = runtime.default_normal_physical_work_mode()
    for slot in runtime.slots.values():
        slot.enabled = True
        slot.mode = const.MODE_NORMAL_OPERATION
        slot.physical_work_mode = normal_physical
        slot.charge_enabled = False
    special = runtime.slots["19_20"]
    special.mode = const.MODE_SELLING_FIRST
    special.physical_work_mode = None
    special.sell_power = 2917
    special.discharge_current = runtime.user_schedule_discharge_current
    special.minimum_sell_soc = 20
    special.ai_sell_power_only = True
    runtime.scheduler_enabled = True
    runtime._schedule_reconcile_requested = False

    apply_today(runtime, [sell("19_20", 2917)])

    assert runtime._schedule_reconcile_requested is False
    assert "już zgodny" in runtime.last_action


def test_invalid_selected_action_rolls_back_complete_logical_target():
    runtime = manager_test.make_runtime()
    runtime.hass.states.values[const.DEFAULT_MAX_SELL_POWER] = manager_test.FakeState(
        "0", attributes={"min": 0, "max": 13000, "step": 1, "unit_of_measurement": "W"}
    )
    runtime.slots["18_19"].enabled = True
    runtime.slots["18_19"].mode = const.MODE_SELLING_FIRST
    runtime.slots["18_19"].sell_power = 3000
    before = {key: replace(slot) for key, slot in runtime.slots.items()}

    with pytest.raises(ValueError, match="fizycznym krokiem"):
        apply_today(runtime, [sell("19_20", 2917), sell("20_21", 3928.5)])

    assert runtime.slots == before


def test_midnight_slot_does_not_modify_tomorrow_plan_or_00_01():
    runtime = manager_test.make_runtime()
    runtime.future_plan = {
        "date": "2026-07-19",
        "updates": [sell("00_01", 1234)],
        "status": "pending",
    }
    tomorrow_before = deepcopy(runtime.future_plan)
    runtime.slots["00_01"].tou_soc = 47

    apply_today(runtime, [sell("23_00", 1875)])

    assert runtime.slots["23_00"].mode == const.MODE_SELLING_FIRST
    assert runtime.slots["23_00"].sell_power == 1875
    assert runtime.slots["00_01"].mode == const.MODE_NORMAL_OPERATION
    assert runtime.slots["00_01"].tou_soc == 47
    assert runtime.future_plan == tomorrow_before


def test_elapsed_selected_hour_is_rejected_without_catch_up():
    runtime = manager_test.make_runtime()
    before = {key: replace(slot) for key, slot in runtime.slots.items()}

    with pytest.raises(ValueError, match="już minęła"):
        apply_today(runtime, [sell("11_12", 2000)])

    assert runtime.slots == before
    assert runtime.hass.services.calls == []


def test_more_than_six_tou_ranges_fails_closed_and_rolls_back():
    runtime = manager_test.make_runtime()
    before = {key: replace(slot) for key, slot in runtime.slots.items()}
    updates = [
        charge(f"{hour:02d}_{(hour + 1) % 24:02d}", soc=10 + offset * 10, grid=bool(offset % 2))
        for offset, hour in enumerate(range(12, 19))
    ]

    with pytest.raises(ValueError, match="maksymalnie 6"):
        apply_today(runtime, updates)

    assert runtime.slots == before
    assert runtime.hass.services.calls == []


@pytest.mark.parametrize("blocked", ["master", "emergency"])
def test_master_off_and_emergency_never_start_physical_write(blocked):
    runtime = manager_test.make_runtime()
    if blocked == "master":
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
    else:
        runtime.emergency_stop = True

    apply_today(runtime, [sell("19_20", 2917)])

    assert runtime.hass.services.calls == []
    assert runtime._schedule_reconcile_requested is False


def test_zero_selected_actions_and_tomorrow_date_are_safe_rejections():
    runtime = manager_test.make_runtime()
    before = {key: replace(slot) for key, slot in runtime.slots.items()}

    with pytest.raises(ValueError, match="at least one slot"):
        apply_today(runtime, [])
    with pytest.raises(ValueError, match="dzisiejszej daty"):
        asyncio.run(
            runtime.async_apply_schedule_patch(
                [sell("19_20", 2917)],
                replace_day=True,
                date="2026-07-19",
            )
        )

    assert runtime.slots == before

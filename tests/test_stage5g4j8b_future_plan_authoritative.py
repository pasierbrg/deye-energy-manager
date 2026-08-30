from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
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


manager_test = _load("stage5g4j8b_manager", ROOT / "tests" / "test_manager_logic.py")
manager = manager_test.manager
const = manager_test.const


class MemoryStore:
    def __init__(self, value=None):
        self.value = value
        self.saves = 0

    async def async_save(self, value):
        self.saves += 1
        self.value = deepcopy(value)

    async def async_load(self):
        return deepcopy(self.value)


def sell(slot_key: str, power: float = 2917) -> dict:
    return {
        "slot_key": slot_key,
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": power,
        # Legacy/extraneous executable fields must never survive a Sell intent.
        "discharge_current": 120,
        "charge_current": 80,
        "grid_charge_current": 60,
        "tou_soc": 20,
        "charge_enabled": True,
    }


def charge(slot_key: str) -> dict:
    return {
        "slot_key": slot_key,
        "enabled": True,
        "mode": const.MODE_CHARGE,
        "charge_current": 80,
        "discharge_current": 30,
        "grid_charge_current": 40,
        "tou_soc": 85,
        "charge_enabled": True,
    }


def save_tomorrow(runtime, selected: list[dict], *, now: datetime) -> None:
    previous_now = manager.ha_now
    manager.ha_now = lambda: now
    runtime._ai_store = MemoryStore()
    runtime.optimizer_plan = {}
    runtime.learning_summary = lambda: {}
    try:
        asyncio.run(runtime.async_save_future_plan({
            "date": "2026-07-19",
            "plan_id": "plan-8b",
            "strategy": "balanced",
            "replace_day": True,
            "labels": [item["slot_key"] for item in selected],
            "updates": selected,
            "slot_validations": {
                item["slot_key"]: {"allow_partial": True}
                for item in selected
            },
        }))
    finally:
        manager.ha_now = previous_now


def test_acceptance_builds_dated_authoritative_24h_intent_without_touching_today():
    runtime = manager_test.make_runtime()
    runtime.slots["05_06"].mode = const.MODE_SELLING_FIRST
    runtime.slots["05_06"].sell_power = 1111
    before_slots = {key: replace(slot) for key, slot in runtime.slots.items()}
    before_calls = list(runtime.hass.services.calls)

    save_tomorrow(
        runtime,
        [sell("19_20"), charge("20_21")],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )

    plan = runtime.future_plan
    assert plan["date"] == "2026-07-19"
    assert plan["authoritative_day"] is True
    assert plan["replace_day"] is True
    assert plan["intent_schema_version"] == 2
    assert plan["selected_slot_keys"] == ["19_20", "20_21"]
    assert len(plan["updates"]) == 24
    assert {item["slot_key"] for item in plan["updates"]} == set(runtime.slots)
    normal = next(item for item in plan["updates"] if item["slot_key"] == "05_06")
    assert normal == {
        "slot_key": "05_06",
        "enabled": True,
        "mode": const.MODE_NORMAL_OPERATION,
        "charge_enabled": False,
    }
    stored_sell = next(item for item in plan["updates"] if item["slot_key"] == "19_20")
    assert stored_sell == {
        "slot_key": "19_20",
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": 2917,
    }
    assert runtime.slots == before_slots
    assert runtime.hass.services.calls == before_calls


def test_unselected_proposal_candidate_and_no_proposal_are_all_normal_intents():
    runtime = manager_test.make_runtime()
    # The backend deliberately receives only the authoritative selected
    # allowlist.  These three absent keys represent each frontend row class.
    unselected_proposal = "18_19"
    candidate_only = "17_18"
    no_proposal = "16_17"
    save_tomorrow(
        runtime,
        [sell("19_20")],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    by_key = {item["slot_key"]: item for item in runtime.future_plan["updates"]}
    for key in (unselected_proposal, candidate_only, no_proposal):
        assert by_key[key]["mode"] == const.MODE_NORMAL_OPERATION
        assert by_key[key]["charge_enabled"] is False


def test_jit_materializes_only_current_normal_and_clears_ghost_action():
    runtime = manager_test.make_runtime()
    for key in ("05_06", "06_07"):
        runtime.slots[key].enabled = True
        runtime.slots[key].mode = const.MODE_CHARGE
        runtime.slots[key].charge_enabled = True
        runtime.slots[key].charge_current = 99
    save_tomorrow(
        runtime,
        [sell("19_20")],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    runtime._schedule_reconcile_requested = False

    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 19, 5, 20, tzinfo=timezone.utc)
    try:
        asyncio.run(runtime.async_process_future_plan())
    finally:
        manager.ha_now = previous_now

    assert runtime.slots["05_06"].mode == const.MODE_NORMAL_OPERATION
    assert runtime.slots["05_06"].charge_enabled is False
    assert runtime.slots["05_06"].charge_current == runtime.normal_profile_charge_current
    # No catch-ahead: the next hour is still untouched until its own JIT tick.
    assert runtime.slots["06_07"].mode == const.MODE_CHARGE
    assert runtime.slots["06_07"].charge_enabled is True
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "physical_pending"


def test_jit_sell_uses_only_current_slot_and_sell_power_contract():
    runtime = manager_test.make_runtime(price=1.2)
    save_tomorrow(
        runtime,
        [sell("05_06", 2917), sell("06_07", 2800)],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    applied = []

    async def capture(updates, **kwargs):
        applied.append((deepcopy(updates), kwargs))

    runtime.async_apply_schedule_patch = capture
    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    try:
        asyncio.run(runtime.async_process_future_plan())
    finally:
        manager.ha_now = previous_now

    assert applied[0][0] == [{
        "slot_key": "05_06",
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": 2917,
    }]
    assert applied[0][1]["ai_source"] is True
    assert applied[0][1]["change_source"] == "future_plan"


def test_no_catch_up_marks_elapsed_special_and_executes_only_current_normal():
    runtime = manager_test.make_runtime(price=1.2)
    save_tomorrow(
        runtime,
        [sell("19_20")],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    applied = []

    async def capture(updates, **kwargs):
        applied.append(deepcopy(updates))

    runtime.async_apply_schedule_patch = capture
    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 19, 20, 10, tzinfo=timezone.utc)
    try:
        asyncio.run(runtime.async_process_future_plan())
    finally:
        manager.ha_now = previous_now

    assert runtime.future_plan["slot_results"]["19_20"]["status"] == "missed"
    assert applied == [[{
        "slot_key": "20_21",
        "enabled": True,
        "mode": const.MODE_NORMAL_OPERATION,
        "charge_enabled": False,
    }]]


def test_23_00_executes_on_target_date_and_never_becomes_00_01():
    runtime = manager_test.make_runtime(price=1.2)
    save_tomorrow(
        runtime,
        [sell("23_00", 1800)],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    applied = []

    async def capture(updates, **kwargs):
        applied.append(deepcopy(updates))

    runtime.async_apply_schedule_patch = capture
    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 19, 23, 20, tzinfo=timezone.utc)
    try:
        asyncio.run(runtime.async_process_future_plan())
    finally:
        manager.ha_now = previous_now

    assert applied == [[{
        "slot_key": "23_00",
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": 1800,
    }]]
    assert all(item[0]["slot_key"] != "00_01" for item in applied)


def test_legacy_selected_only_plan_is_migrated_without_inferred_special_actions():
    store = MemoryStore({
        "settings": {},
        "history": [],
        "future_plan": {
            "plan_id": "legacy",
            "date": "2026-07-19",
            "status": "scheduled",
            "updates": [{
                "slot_key": "19_20",
                "enabled": True,
                "mode": const.MODE_SELLING_FIRST,
                "sell_power": 2500,
            }],
            "slot_validations": {"19_20": {"profile_id": "evening_sale"}},
        },
    })
    runtime = manager_test.make_runtime()
    runtime.slots["05_06"].mode = const.MODE_CHARGE
    previous_store = manager.Store
    manager.Store = lambda *_args, **_kwargs: store
    try:
        asyncio.run(runtime.async_load_ai_data())
    finally:
        manager.Store = previous_store

    assert runtime.future_plan["status"] == "scheduled"
    assert len(runtime.future_plan["updates"]) == 24
    assert runtime.future_plan["selected_slot_keys"] == ["19_20"]
    migrated_05 = next(
        item for item in runtime.future_plan["updates"] if item["slot_key"] == "05_06"
    )
    assert migrated_05["mode"] == const.MODE_NORMAL_OPERATION
    assert store.value["future_plan"]["authoritative_day"] is True


def test_store_restore_and_quantized_sell_round_trip_remain_exact():
    original = manager_test.make_runtime()
    save_tomorrow(
        original,
        [sell("19_20", 2917)],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    stored_payload = deepcopy(original._ai_store.value)
    store = MemoryStore(stored_payload)
    restored = manager_test.make_runtime(price=1.2)
    previous_store = manager.Store
    manager.Store = lambda *_args, **_kwargs: store
    try:
        asyncio.run(restored.async_load_ai_data())
    finally:
        manager.Store = previous_store

    update = next(
        item for item in restored.future_plan["updates"]
        if item["slot_key"] == "19_20"
    )
    assert update["sell_power"] == 2917
    assert set(update) == {"slot_key", "enabled", "mode", "sell_power"}
    assert len(restored.future_plan["updates"]) == 24
    applied = []

    async def capture(updates, **kwargs):
        applied.append(deepcopy(updates))

    restored.async_apply_schedule_patch = capture
    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 19, 19, 10, tzinfo=timezone.utc)
    try:
        asyncio.run(restored.async_process_future_plan())
    finally:
        manager.ha_now = previous_now
    assert applied == [[{
        "slot_key": "19_20",
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": 2917,
    }]]


def test_future_plan_store_deduplicates_unchanged_24h_payload():
    runtime = manager_test.make_runtime()
    save_tomorrow(
        runtime,
        [sell("19_20")],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    store = runtime._ai_store
    saves_before = store.saves
    asyncio.run(runtime.async_save_ai_data())
    asyncio.run(runtime.async_save_ai_data())
    assert store.saves == saves_before


def test_invalid_legacy_plan_fails_closed_for_reapproval():
    runtime = manager_test.make_runtime()
    migrated, changed = runtime._normalize_stored_future_plan({
        "date": "2026-07-19",
        "status": "scheduled",
        "updates": [{"slot_key": "19_20", "mode": const.MODE_SELLING_FIRST}],
    })
    assert changed is True
    assert migrated["status"] == "cancelled"
    assert migrated["migration_requires_reapproval"] is True


@pytest.mark.parametrize("blocked", ["master", "emergency"])
def test_jit_under_central_guard_never_starts_physical_write(blocked):
    runtime = manager_test.make_runtime()
    save_tomorrow(
        runtime,
        [sell("19_20")],
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    if blocked == "master":
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"
    else:
        runtime.emergency_stop = True
    before_calls = list(runtime.hass.services.calls)

    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 19, 5, 5, tzinfo=timezone.utc)
    try:
        asyncio.run(runtime.async_process_future_plan())
    finally:
        manager.ha_now = previous_now

    assert runtime.hass.services.calls == before_calls
    assert runtime._schedule_reconcile_requested is False


def test_zero_selected_and_explicit_partial_contract_are_rejected():
    runtime = manager_test.make_runtime()
    runtime._ai_store = MemoryStore()
    runtime.optimizer_plan = {}
    runtime.learning_summary = lambda: {}
    previous_now = manager.ha_now
    manager.ha_now = lambda: datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    try:
        with pytest.raises(ValueError, match="nie zawiera wybranych godzin"):
            asyncio.run(runtime.async_save_future_plan({
                "date": "2026-07-19", "replace_day": True, "updates": [],
            }))
        with pytest.raises(ValueError, match="replace_day=true"):
            asyncio.run(runtime.async_save_future_plan({
                "date": "2026-07-19", "replace_day": False,
                "updates": [sell("19_20")],
            }))
    finally:
        manager.ha_now = previous_now

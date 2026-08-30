from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


manager_test = _load("stage5g4j8c_manager", ROOT / "tests" / "test_manager_logic.py")
manager = manager_test.manager
const = manager_test.const


class MemoryStore:
    def __init__(self, value=None):
        self.value = value

    async def async_save(self, value):
        self.value = deepcopy(value)

    async def async_load(self):
        return deepcopy(self.value)


def sell(key="05_06", power=3000):
    return {"slot_key": key, "enabled": True, "mode": const.MODE_SELLING_FIRST, "sell_power": power}


def charge(key="05_06"):
    return {"slot_key": key, "enabled": True, "mode": const.MODE_CHARGE, "charge_enabled": True}


def accept(runtime, now, updates, plan_id="plan-8c"):
    runtime._ai_store = MemoryStore()
    runtime.optimizer_plan = {}
    runtime.learning_summary = lambda: {}
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        asyncio.run(runtime.async_save_future_plan({
            "date": (now.date() + manager.timedelta(days=1)).isoformat(),
            "plan_id": plan_id,
            "replace_day": True,
            "updates": updates,
            "slot_validations": {item["slot_key"]: {"allow_partial": True} for item in updates},
        }))
    finally:
        manager.ha_now = previous


def run_at(runtime, now):
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        asyncio.run(runtime.async_process_future_plan())
    finally:
        manager.ha_now = previous


def pending_runtime(now, *, status="physical_pending"):
    runtime = manager_test.make_runtime()
    runtime._ai_store = MemoryStore()
    key = f"{now.hour:02d}_{(now.hour + 1) % 24:02d}"
    runtime.slots[key].enabled = True
    runtime.slots[key].mode = const.MODE_SELLING_FIRST
    runtime._claim_schedule_slots([key], "future_plan", {
        "plan_id": "p", "target_date": now.date().isoformat(), "intent_revision": 1,
    })
    runtime.future_plan = {
        "plan_id": "p", "date": now.date().isoformat(), "status": "scheduled",
        "updates": [sell(key)], "slot_results": {key: {
            "status": status,
            "correlation": {
                "plan_id": "p", "target_date": now.date().isoformat(),
                "slot_key": key, "intent_revision": 1,
                "physical_write_count_before": 0,
                "expected_fingerprint": manager.snapshot_id({}),
            },
        }},
    }
    return runtime, key


def test_01_logical_apply_is_not_confirmation():
    runtime = manager_test.make_runtime(price=1.2)
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "logical_applied"


def test_02_write_and_readback_can_confirm_exact_intent():
    now = datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    runtime, key = pending_runtime(now)
    runtime._physical_write_count = 1
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        asyncio.run(runtime._async_finish_future_plan_physical(True, expected={}))
    finally:
        manager.ha_now = previous
    assert runtime.future_plan["slot_results"][key]["status"] == "confirmed"


def test_03_physical_failure_is_blocked():
    now = datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    runtime, key = pending_runtime(now)
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        asyncio.run(runtime._async_finish_future_plan_physical(False, "write failed"))
    finally:
        manager.ha_now = previous
    assert runtime.future_plan["slot_results"][key]["status"] == "blocked"


def test_04_rollback_never_confirms():
    now = datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    runtime, key = pending_runtime(now)
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        runtime._physical_write_count = 1
        asyncio.run(runtime._async_finish_future_plan_physical(True, expected={"rollback": True}))
        assert runtime.future_plan["slot_results"][key]["status"] == "physical_pending"
        asyncio.run(runtime._async_finish_future_plan_physical(False, "rollback"))
    finally:
        manager.ha_now = previous
    assert "rollback" in runtime.future_plan["slot_results"][key]["reason"]


def test_05_master_off_cannot_confirm():
    now = datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    runtime, key = pending_runtime(now)
    runtime.control_enabled = False
    runtime._physical_write_count = 1
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        asyncio.run(runtime._async_finish_future_plan_physical(True, expected={}))
    finally:
        manager.ha_now = previous
    assert runtime.future_plan["slot_results"][key]["status"] == "physical_pending"


def test_06_emergency_cannot_confirm():
    now = datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    runtime, key = pending_runtime(now)
    runtime.emergency_stop = True
    runtime._physical_write_count = 1
    previous = manager.ha_now
    manager.ha_now = lambda: now
    try:
        asyncio.run(runtime._async_finish_future_plan_physical(True, expected={}))
    finally:
        manager.ha_now = previous
    assert runtime.future_plan["slot_results"][key]["status"] == "physical_pending"


def test_07_master_off_elapsed_slot_is_missed_without_catchup():
    runtime = manager_test.make_runtime(price=1.2)
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    run_at(runtime, datetime(2026, 7, 19, 6, 10, tzinfo=timezone.utc))
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "missed"


def test_08_restart_pending_resets_local_write_correlation_only():
    runtime = manager_test.make_runtime()
    raw = {"date": "2026-07-19", "status": "scheduled", "plan_id": "p", "updates": [sell()],
           "lifecycle_schema_version": 1, "slot_results": {"05_06": {"status": "physical_pending", "correlation": {"physical_write_count_before": 99}}}}
    normalized, _ = runtime._normalize_stored_future_plan(raw)
    assert normalized["slot_results"]["05_06"]["correlation"]["physical_write_count_before"] == 0


def test_09_confirmed_restore_is_terminal_and_not_rewritten():
    runtime, key = pending_runtime(datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc), status="confirmed")
    calls = []
    runtime.async_apply_schedule_patch = lambda *_a, **_k: calls.append(1)
    run_at(runtime, datetime(2026, 7, 19, 5, 20, tzinfo=timezone.utc))
    assert calls == [] and runtime.future_plan["slot_results"][key]["status"] == "confirmed"


def test_10_expired_future_sell_is_cleaned_to_normal():
    runtime, key = pending_runtime(datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 20, 5, 10, tzinfo=timezone.utc))
    assert runtime.slots[key].mode == const.MODE_NORMAL_OPERATION


def test_11_expired_future_charge_is_cleaned_to_normal():
    runtime = manager_test.make_runtime()
    key = "05_06"
    runtime.slots[key].mode = const.MODE_CHARGE
    runtime._claim_schedule_slots([key], "future_plan", {"plan_id": "p", "target_date": "2026-07-19", "intent_revision": 1})
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 20, 5, 10, tzinfo=timezone.utc))
    assert runtime.slots[key].mode == const.MODE_NORMAL_OPERATION


def test_12_cleanup_preserves_newer_manual_owner():
    runtime, key = pending_runtime(datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    runtime.slots[key].sell_power = 1234
    runtime._claim_schedule_slots([key], "manual")
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 20, 5, 10, tzinfo=timezone.utc))
    assert runtime.slots[key].sell_power == 1234


def test_13_cleanup_preserves_newer_apply_today_owner():
    runtime, key = pending_runtime(datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    runtime.slots[key].sell_power = 2222
    runtime._claim_schedule_slots([key], "apply_today")
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 20, 5, 10, tzinfo=timezone.utc))
    assert runtime.slots[key].sell_power == 2222


def test_14_manual_edit_after_acceptance_wins():
    runtime = manager_test.make_runtime(price=1.2)
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    runtime.slots["05_06"].sell_power = 1111
    runtime._claim_schedule_slots(["05_06"], "manual")
    run_at(runtime, datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "manual_override"


def test_15_manual_edit_before_acceptance_is_the_base():
    runtime = manager_test.make_runtime(price=1.2)
    runtime.slots["05_06"].sell_power = 1111
    runtime._claim_schedule_slots(["05_06"], "manual")
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "logical_applied"


def test_16_own_jit_claim_is_not_a_manual_conflict():
    runtime = manager_test.make_runtime(price=1.2)
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    runtime.control_enabled = False
    now = datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc)
    run_at(runtime, now)
    run_at(runtime, now)
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "logical_applied"


def test_17_reacceptance_supersedes_same_date_plan():
    runtime = manager_test.make_runtime()
    now = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    accept(runtime, now, [sell()], "old")
    accept(runtime, now, [sell("06_07")], "new")
    assert runtime.future_plan["superseded_plans"][-1]["plan_id"] == "old"


def test_18_removed_old_special_is_normal_in_new_authoritative_plan():
    runtime = manager_test.make_runtime()
    now = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    accept(runtime, now, [sell()], "old")
    accept(runtime, now, [sell("06_07")], "new")
    row = next(item for item in runtime.future_plan["updates"] if item["slot_key"] == "05_06")
    assert row["mode"] == const.MODE_NORMAL_OPERATION


def test_19_23_00_is_not_cleaned_before_midnight():
    runtime = manager_test.make_runtime()
    key = "23_00"
    runtime.slots[key].mode = const.MODE_SELLING_FIRST
    runtime._claim_schedule_slots([key], "future_plan", {"plan_id": "p", "target_date": "2026-07-19", "intent_revision": 1})
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 19, 23, 59, tzinfo=timezone.utc))
    assert runtime.slots[key].mode == const.MODE_SELLING_FIRST


def test_20_midnight_cleanup_does_not_touch_new_day_00_01():
    runtime = manager_test.make_runtime()
    runtime.slots["23_00"].mode = const.MODE_SELLING_FIRST
    runtime.slots["00_01"].mode = const.MODE_CHARGE
    runtime._claim_schedule_slots(["23_00"], "future_plan", {"plan_id": "p", "target_date": "2026-07-19", "intent_revision": 1})
    runtime._claim_schedule_slots(["00_01"], "manual")
    runtime.control_enabled = False
    run_at(runtime, datetime(2026, 7, 20, 0, 1, tzinfo=timezone.utc))
    assert runtime.slots["23_00"].mode == const.MODE_NORMAL_OPERATION
    assert runtime.slots["00_01"].mode == const.MODE_CHARGE


def test_21_store_payload_contains_lifecycle_ownership_and_revisions():
    runtime, key = pending_runtime(datetime(2026, 7, 19, 5, 10, tzinfo=timezone.utc))
    payload = runtime._ai_store_payload()
    assert payload["schedule_revision"] == 1
    assert payload["schedule_slot_revisions"][key] == 1
    assert payload["schedule_slot_ownership"][key]["plan_id"] == "p"


def test_22_future_sell_remains_power_only():
    runtime = manager_test.make_runtime()
    normalized = runtime._validate_future_plan_updates([{**sell(), "discharge_current": 120, "tou_soc": 20}])[0]
    assert set(runtime._sanitize_ai_sell_execution_update(normalized)) == {"slot_key", "enabled", "mode", "sell_power"}


def test_23_authoritative_future_plan_still_has_24_intents():
    runtime = manager_test.make_runtime()
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    assert len(runtime.future_plan["updates"]) == 24


def test_24_acceptance_keeps_daily_profile_date_in_validation():
    runtime = manager_test.make_runtime()
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    assert runtime.future_plan["date"] == "2026-07-19"
    assert runtime.future_plan["slot_bases"]["05_06"]["base_fingerprint"]


def test_25_elapsed_slot_never_calls_future_jit_again():
    runtime = manager_test.make_runtime(price=1.2)
    accept(runtime, datetime(2026, 7, 18, 12, tzinfo=timezone.utc), [sell()])
    calls = []
    async def capture(*args, **kwargs):
        calls.append((args, kwargs))
    runtime.async_apply_schedule_patch = capture
    run_at(runtime, datetime(2026, 7, 19, 6, 10, tzinfo=timezone.utc))
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "missed"
    assert not any(call[0][0][0].get("slot_key") == "05_06" for call in calls)

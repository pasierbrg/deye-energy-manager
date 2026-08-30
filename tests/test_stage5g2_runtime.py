"""Stage 5G.2 runtime feedback-loop and event-loop guardrails."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import threading
from pathlib import Path

from test_manager_logic import manager
from test_stage5g1_lifecycle import task_runtime


def _prepared(snapshot: str, value: int = 1) -> dict:
    return {
        "payload": {"value": value},
        "selected_strategy": "balanced",
        "snapshot_id": snapshot,
        "current": datetime.now(UTC),
        "battery_model": {},
    }


def _install_semantic_core(runtime, snapshot=lambda: "stable", on_execute=None):
    state = {"last": None, "calls": []}
    runtime._prepare_ai_plan_48h = lambda: _prepared(str(snapshot()), int(getattr(runtime, "_test_value", 1)))
    runtime._optimizer_plan_is_current = lambda prepared: state["last"] == prepared["snapshot_id"]

    def apply(prepared, result):
        state["last"] = prepared["snapshot_id"]
        return result, True

    runtime._apply_prepared_ai_plan = apply

    async def execute(function, payload, strategy):
        assert function is manager.build_plan_bundle
        assert isinstance(payload, dict)
        assert strategy == "balanced"
        state["calls"].append(deepcopy(payload))
        if on_execute is not None:
            on_execute(runtime, len(state["calls"]))
        return {"rows": []}

    runtime.hass.async_add_executor_job = execute
    runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None
    return state


def _capture_input_listener(runtime):
    captured = {"registrations": 0, "timers": 0, "active": 0}
    original_state = manager.async_track_state_change_event
    original_point = manager.async_track_point_in_time

    def track_state(_hass, entities, callback):
        captured["registrations"] += 1
        captured["active"] += 1
        captured["entities"] = tuple(entities)
        captured["callback"] = callback

        def unsubscribe():
            captured["active"] -= 1

        return unsubscribe

    def track_point(_hass, callback, _when):
        captured["timers"] += 1
        captured["timer_callback"] = callback
        return lambda: None

    manager.async_track_state_change_event = track_state
    manager.async_track_point_in_time = track_point
    runtime.schedule_ai_api_analysis = lambda: None

    def restore():
        manager.async_track_state_change_event = original_state
        manager.async_track_point_in_time = original_point

    return captured, restore


def test_optimizer_output_state_changes_do_not_retrigger_optimizer():
    async def scenario():
        runtime = task_runtime()
        captured, restore = _capture_input_listener(runtime)
        try:
            runtime._start_schedule_input_listener()
            state = _install_semantic_core(runtime)
            captured["callback"]({"entity_id": runtime.battery_soc_sensor})
            captured["timer_callback"](datetime.now(UTC))
            await runtime._optimizer_recalc_task
            assert len(state["calls"]) == 1
            requests = runtime.runtime_metrics["optimizer_recalc_requested"]
            captured["callback"]({"entity_id": "sensor.deye_energy_manager_ai_state"})
            captured["callback"]({"entity_id": "sensor.deye_energy_manager_system_diagnostics"})
            assert runtime.runtime_metrics["optimizer_recalc_requested"] == requests
            assert runtime.runtime_metrics["self_entity_event_ignored"] == 2
        finally:
            restore()

    asyncio.run(scenario())


def test_optimizer_pending_followup_stops_when_snapshot_unchanged():
    async def scenario():
        runtime = task_runtime()

        def during_first_run(active_runtime, call_number):
            if call_number == 1:
                for _ in range(20):
                    active_runtime.request_optimizer_recalc("soc")

        state = _install_semantic_core(runtime, on_execute=during_first_run)
        await runtime.request_optimizer_recalc("soc")
        assert len(state["calls"]) == 1
        assert runtime.runtime_metrics["optimizer_recalc_followup"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_skipped_same_snapshot"] == 1
        assert runtime._optimizer_recalc_pending is False
        assert runtime._optimizer_recalc_task is None

    asyncio.run(scenario())


def test_stable_inputs_do_not_recalculate_forever():
    async def scenario():
        runtime = task_runtime()
        state = _install_semantic_core(runtime)
        for _logical_minute in range(10):
            await runtime.request_optimizer_recalc("manual")
        assert len(state["calls"]) == 1
        assert runtime.runtime_metrics["optimizer_recalc_started"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_skipped_same_snapshot"] == 9
        assert runtime.runtime_metrics["optimizer_recalc_max_active"] == 1

    asyncio.run(scenario())


def test_timestamp_only_change_does_not_change_semantic_input_snapshot():
    runtime = task_runtime()
    first = {
        "soc_diagnostics": {
            "status": "valid", "normalized_value": 50, "last_updated": "2026-08-09T10:00:00Z", "age_seconds": 1,
        },
        "generated_at": "2026-08-09T10:00:01Z",
    }
    second = deepcopy(first)
    second["soc_diagnostics"]["last_updated"] = "2026-08-09T10:05:00Z"
    second["soc_diagnostics"]["age_seconds"] = 12
    second["generated_at"] = "2026-08-09T10:05:01Z"
    assert runtime._semantic_optimizer_inputs(first) == runtime._semantic_optimizer_inputs(second)


def test_identical_value_with_new_last_updated_does_not_recalculate():
    runtime = task_runtime()
    first = {"live_state": {"pv": {"value": 1200, "status": "ok", "last_updated": "old"}}}
    second = {"live_state": {"pv": {"value": 1200, "status": "ok", "last_updated": "new"}}}
    assert runtime._semantic_optimizer_inputs(first) == runtime._semantic_optimizer_inputs(second)


def test_real_input_value_change_changes_semantic_snapshot():
    runtime = task_runtime()
    first = {"live_state": {"load": {"value": 800, "status": "ok", "last_updated": "old"}}}
    second = {"live_state": {"load": {"value": 900, "status": "ok", "last_updated": "new"}}}
    assert runtime._semantic_optimizer_inputs(first) != runtime._semantic_optimizer_inputs(second)


def test_freshness_threshold_transition_changes_semantic_snapshot():
    runtime = task_runtime()
    fresh = {"soc_diagnostics": {"status": "valid", "normalized_value": 50, "age_seconds": 899}}
    stale = {"soc_diagnostics": {"status": "stale", "normalized_value": None, "age_seconds": 901, "reason": "901 s"}}
    assert runtime._semantic_optimizer_inputs(fresh) != runtime._semantic_optimizer_inputs(stale)


def test_optimizer_core_runs_in_executor_without_blocking_event_loop():
    async def scenario():
        runtime = task_runtime()
        runtime._prepare_ai_plan_48h = lambda: _prepared("slow")
        runtime._optimizer_plan_is_current = lambda _prepared: False
        runtime._apply_prepared_ai_plan = lambda _prepared, result: (result, True)
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None
        started = threading.Event()
        release = threading.Event()
        worker_threads = []

        async def execute(function, payload, strategy):
            assert function is manager.build_plan_bundle
            assert payload == {"value": 1}

            def slow_pure_core():
                worker_threads.append(threading.get_ident())
                started.set()
                release.wait()
                return {"rows": []}

            return await asyncio.to_thread(slow_pure_core)

        runtime.hass.async_add_executor_job = execute
        task = runtime.request_optimizer_recalc("manual")
        await asyncio.to_thread(started.wait)
        marker = []

        async def simple_coroutine():
            marker.append("event-loop-responsive")

        await simple_coroutine()
        assert marker == ["event-loop-responsive"]
        assert not task.done()
        assert worker_threads != [threading.get_ident()]
        release.set()
        await task

    asyncio.run(scenario())


def test_ai_recalc_does_not_write_all_manager_entities():
    async def scenario():
        runtime = task_runtime()

        class Entity:
            def __init__(self, key):
                self._deye_manager_key = key
                self.hass = object()
                self.writes = 0

            def async_write_ha_state(self):
                self.writes += 1

        entities = [Entity("ai_state"), Entity("diagnostics"), Entity("manager_status"), Entity("target_mode")]
        runtime.entities = entities
        runtime.build_ai_state_snapshot = lambda: {"planner_48h": {"plan_id": "one"}}
        runtime.diagnostics = lambda: {"connected": True, "optimizer_runtime": {}}
        await runtime.request_sensor_snapshot_refresh()
        assert [entity.writes for entity in entities] == [1, 1, 0, 0]
        await runtime.request_sensor_snapshot_refresh()
        assert [entity.writes for entity in entities] == [1, 1, 0, 0]

    asyncio.run(scenario())


def test_reload_does_not_duplicate_optimizer_listeners():
    runtime = task_runtime()
    captured, restore = _capture_input_listener(runtime)
    try:
        runtime._start_schedule_input_listener()
        runtime._start_schedule_input_listener()
        assert captured["registrations"] == 1
        assert captured["active"] == 1
        assert len(captured["entities"]) == len(set(captured["entities"]))
    finally:
        if runtime.unsub_input_listener:
            runtime.unsub_input_listener()
        restore()


def test_disable_enable_does_not_duplicate_state_listeners():
    async def scenario():
        runtime = task_runtime()
        captured, restore = _capture_input_listener(runtime)
        try:
            runtime._start_schedule_input_listener()
            assert captured["active"] == 1
            await runtime.async_unload()
            assert captured["active"] == 0
            replacement = task_runtime()
            replacement._start_schedule_input_listener()
            assert replacement is not runtime
            assert captured["registrations"] == 2
            assert captured["active"] == 1
            await replacement.async_unload()
            assert captured["active"] == 0
        finally:
            restore()

    asyncio.run(scenario())


def test_optimizer_listener_is_exact_allowlist_without_own_outputs():
    runtime = task_runtime()
    runtime.data[manager.CONF_PV_POWER_SENSOR] = "sensor.external_pv"
    runtime.data[manager.CONF_LOAD_POWER_SENSOR] = "sensor.external_load"
    captured, restore = _capture_input_listener(runtime)
    try:
        runtime._start_schedule_input_listener()
        assert "sensor.external_pv" in captured["entities"]
        assert "sensor.external_load" in captured["entities"]
        assert all("deye_energy_manager_" not in entity_id for entity_id in captured["entities"])
        assert "soc" in runtime._optimizer_input_reasons.values()
        assert "pv" in runtime._optimizer_input_reasons.values()
        assert "load" in runtime._optimizer_input_reasons.values()
    finally:
        if runtime.unsub_input_listener:
            runtime.unsub_input_listener()
        restore()


def test_runtime_metrics_expose_reasons_and_balanced_counts():
    async def scenario():
        runtime = task_runtime()
        _install_semantic_core(runtime)
        await runtime.request_optimizer_recalc({"soc", "pv", "load"})
        metrics = runtime.diagnostics_public_snapshot()["optimizer_runtime"]
        assert metrics["optimizer_recalc_requested"] == 1
        assert metrics["optimizer_recalc_started"] == 1
        assert metrics["optimizer_recalc_completed"] == 1
        assert metrics["optimizer_recalc_max_active"] == 1
        assert metrics["optimizer_recalc_reasons"] == {"soc": 1, "pv": 1, "load": 1}
        assert metrics["optimizer_recalc_reason_soc"] == 1
        assert metrics["optimizer_recalc_reason_pv"] == 1
        assert metrics["optimizer_recalc_reason_load"] == 1
        assert metrics["pending"] is False

    asyncio.run(scenario())


def test_enable_lifecycle_stays_bounded_across_events_and_logical_ticks():
    async def scenario():
        runtime = task_runtime()
        captured, restore = _capture_input_listener(runtime)
        try:
            runtime._start_schedule_input_listener()
            state = _install_semantic_core(runtime)
            for entity_id in captured["entities"][:6]:
                captured["callback"]({"entity_id": entity_id})
            assert captured["timers"] == 1
            captured["timer_callback"](datetime.now(UTC))
            await runtime._optimizer_recalc_task
            for _logical_minute in range(5):
                await runtime.request_optimizer_recalc("manual")
            captured["callback"]({"entity_id": "sensor.deye_energy_manager_manager_status"})
            assert len(state["calls"]) == 1
            assert runtime.runtime_metrics["optimizer_recalc_max_active"] == 1
            assert runtime.runtime_metrics["self_entity_event_ignored"] == 1
            assert captured["registrations"] == 1
            assert runtime._optimizer_recalc_task is None
        finally:
            if runtime.unsub_input_listener:
                runtime.unsub_input_listener()
            restore()

    asyncio.run(scenario())


def test_runtime_optimizer_roundtrip_returns_48_hours_off_loop():
    async def scenario():
        runtime = task_runtime()
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None
        await runtime.request_optimizer_recalc("manual")
        assert runtime.runtime_metrics["optimizer_recalc_started"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_completed"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_max_active"] == 1
        assert len(runtime.optimizer_plan["rows"]) == 48

    asyncio.run(scenario())


def test_ai_api_uses_async_optimizer_instead_of_sync_core_wrapper():
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components/deye_energy_manager/manager.py"
    ).read_text(encoding="utf-8")
    start = source.index("    async def async_run_ai_api(")
    end = source.index("    def schedule_ai_api_analysis", start)
    method = source[start:end]
    assert 'request_optimizer_recalc("manual")' in method
    assert "self.ai_plan_48h()" not in method
    assert "await asyncio.shield(optimizer_task)" in method


def test_platform_restore_storm_coalesces_publish_and_recalc():
    async def scenario():
        runtime = task_runtime()
        # This legacy storm test covers the reload path.  Cold startup is now
        # deferred until HOMEASSISTANT_STARTED by Stage 5G.4J.2.
        runtime.hass.state = "running"
        runtime._platform_setup_in_progress = True

        class Entity:
            def __init__(self, key):
                self._deye_manager_key = key
                self.hass = object()
                self.writes = 0

            def async_write_ha_state(self):
                self.writes += 1

        entities = [Entity("ai_state"), Entity("diagnostics"), Entity("manager_status"), Entity("target_mode")]
        runtime.entities = entities
        runtime.build_ai_state_snapshot = lambda: {"planner_48h": {"plan_id": "initial"}}
        runtime.diagnostics = lambda: {"connected": True, "optimizer_runtime": {}}
        runtime._prepare_ai_plan_48h = lambda: _prepared("restored")
        runtime._optimizer_plan_is_current = lambda _prepared: False
        runtime._apply_prepared_ai_plan = lambda _prepared, result: (result, False)

        async def execute(_function, *_args):
            return {"rows": []}

        runtime.hass.async_add_executor_job = execute
        for _ in range(50):
            runtime.notify_update()
            runtime.request_optimizer_recalc("schedule")
        assert runtime.hass.created_tasks == []
        assert [entity.writes for entity in entities] == [0, 0, 0, 0]
        runtime.finish_platform_setup()
        assert len(runtime.hass.created_tasks) == 2
        await asyncio.gather(*runtime.hass.created_tasks)
        assert runtime.runtime_metrics["optimizer_recalc_started"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_max_active"] == 1
        # One coherent all-entity publish, then only AI/diagnostic channels.
        assert [entity.writes for entity in entities] == [2, 3, 1, 1]

    asyncio.run(scenario())


def test_async_setup_entry_gates_restore_entities_until_platforms_finish():
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components/deye_energy_manager/__init__.py"
    ).read_text(encoding="utf-8")
    start = source.index("async def async_setup_entry(")
    end = source.index("async def async_unload_entry", start)
    setup = source[start:end]
    gate = setup.index("runtime._platform_setup_in_progress = True")
    forward = setup.index("async_forward_entry_setups")
    finish = setup.index("runtime.finish_platform_setup()")
    assert gate < forward < finish

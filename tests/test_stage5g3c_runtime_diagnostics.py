"""Stage 5G.3C private aggregate runtime diagnostics."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from pathlib import Path

import pytest

from test_manager_logic import manager
from test_stage5g1_lifecycle import task_runtime


PERF_LOGGER = "custom_components.deye_energy_manager.performance"


def test_monitor_is_private_inactive_and_has_no_public_persistence():
    runtime = task_runtime()

    runtime._performance.inc("optimizer_request_total")

    assert runtime._performance.counter("optimizer_request_total") == 0
    assert not runtime._performance.active
    assert all(
        "performance" not in str(getattr(entity, "_deye_manager_key", ""))
        for entity in runtime.entities
    )
    source = Path("custom_components/deye_energy_manager/performance.py").read_text(
        encoding="utf-8"
    )
    assert "Store(" not in source
    assert "async_track_state_change_event" not in source


def test_lag_probe_uses_monotonic_plan_and_threshold_buckets():
    runtime = task_runtime()
    monitor = runtime._performance
    monitor.start(now=10.0)

    monitor.record_lag_tick(now=11.275)

    assert monitor.counter("event_loop_lag_samples") == 1
    assert monitor.counter("event_loop_lag_max_ms") == pytest.approx(275)
    assert monitor.counter("event_loop_lag_ge_50ms") == 1
    assert monitor.counter("event_loop_lag_ge_100ms") == 1
    assert monitor.counter("event_loop_lag_ge_250ms") == 1
    assert monitor.counter("event_loop_lag_ge_500ms") == 0


def test_aggregate_report_is_one_record_has_required_sections_and_resets(caplog):
    runtime = task_runtime()
    runtime._performance.start(now=10.0)
    runtime._performance.record_optimizer_request({"pv"})
    runtime._performance.record_input_event(
        "sensor.pv", accepted=True, coalesced=False
    )
    runtime._performance.record_proxy_event("sensor.pv")
    runtime._performance.record_entity_write(
        "pv_power", "proxy_source_event", channel="proxy"
    )
    runtime._performance.record_lag_tick(now=11.050)

    with caplog.at_level(logging.WARNING, logger=PERF_LOGGER):
        message = runtime._performance.emit_report(runtime, now=70.0)

    records = [record for record in caplog.records if record.name == PERF_LOGGER]
    assert len(records) == 1
    assert message is not None and message.startswith("DEM PERF 60s")
    for section in (
        "event_loop_lag",
        "optimizer_timing",
        "snapshots",
        "publish",
        "proxy",
        "optimizer_inputs",
        "learning",
        "energy",
        "stores",
        "control",
        "payload_bytes",
    ):
        assert section in message
    assert "sensor.pv:1" in message
    assert runtime._performance.counter("optimizer_request_total") == 0
    assert runtime._performance.mapped("optimizer_request_by_reason") == {}
    assert runtime._performance.reports_emitted == 1


def test_hot_path_counters_do_not_log_per_event(caplog):
    runtime = task_runtime()
    runtime._performance.start()

    with caplog.at_level(logging.DEBUG, logger=PERF_LOGGER):
        for _index in range(100):
            runtime._performance.record_input_event(
                "sensor.fast", accepted=False, coalesced=True
            )
            runtime._performance.record_proxy_event("sensor.fast")

    assert [record for record in caplog.records if record.name == PERF_LOGGER] == []
    assert runtime._performance.counter("optimizer_input_events_total") == 100
    assert runtime._performance.counter("proxy_source_events_total") == 100


def test_platform_finish_keeps_production_profiler_inactive_and_timer_free():
    async def scenario():
        runtime = task_runtime()
        runtime._platform_setup_in_progress = True
        runtime.request_optimizer_recalc = lambda *_args, **_kwargs: None
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None
        registrations = []
        unsubscribed = []
        original = manager.async_track_time_interval

        def track(_hass, callback, interval):
            index = len(registrations)
            registrations.append((callback, interval.total_seconds()))

            def unsubscribe():
                unsubscribed.append(index)

            return unsubscribe

        manager.async_track_time_interval = track
        try:
            assert not runtime._performance.active
            runtime.finish_platform_setup()
            assert not runtime._performance.active
            assert registrations == []
            runtime.finish_platform_setup()
            assert registrations == []
            await runtime.async_unload()
            assert unsubscribed == []
            assert not runtime._performance.active
            assert runtime.unsub_performance_lag is None
            assert runtime.unsub_performance_report is None
        finally:
            manager.async_track_time_interval = original

    asyncio.run(scenario())


def test_optimizer_worker_captures_queue_wall_thread_cpu_and_apply():
    async def scenario():
        runtime = task_runtime()
        runtime._performance.start()
        state = {"current": False}
        runtime._prepare_ai_plan_48h = lambda: {
            "payload": {"value": 7},
            "selected_strategy": "balanced",
            "snapshot_id": "snapshot",
            "current": datetime.now(UTC),
            "battery_model": {},
        }
        runtime._optimizer_plan_is_current = lambda _prepared: state["current"]

        def apply(_prepared, result):
            state["current"] = True
            return result, True

        runtime._apply_prepared_ai_plan = apply
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

        async def execute(function, payload, strategy):
            return function(payload, strategy)

        runtime.hass.async_add_executor_job = execute
        original_core = manager.build_plan_bundle
        manager.build_plan_bundle = lambda payload, strategy: {
            "rows": [],
            "payload": payload,
            "strategy": strategy,
        }
        try:
            await runtime.request_optimizer_recalc("pv")
        finally:
            manager.build_plan_bundle = original_core

        assert runtime._performance.counter("optimizer_started") == 1
        assert runtime._performance.counter("optimizer_completed") == 1
        assert runtime._performance.counter("optimizer_executor_queue_wait_count") == 1
        assert runtime._performance.counter("optimizer_core_wall_count") == 1
        assert runtime._performance.counter("optimizer_core_thread_cpu_count") == 1
        assert runtime._performance.counter("optimizer_apply_result_count") == 1

    asyncio.run(scenario())


def test_timestamp_only_optimizer_requests_preserve_semantic_dedup():
    async def scenario():
        runtime = task_runtime()
        runtime._performance.start()
        state = {"last": None, "calls": 0}
        runtime._prepare_ai_plan_48h = lambda: {
            "payload": {"live_state": {"timestamp": "technical", "pv_power_w": 1000}},
            "selected_strategy": "balanced",
            "snapshot_id": "stable",
            "current": datetime.now(UTC),
            "battery_model": {},
        }
        runtime._optimizer_plan_is_current = (
            lambda prepared: state["last"] == prepared["snapshot_id"]
        )

        def apply(prepared, result):
            state["last"] = prepared["snapshot_id"]
            return result, True

        runtime._apply_prepared_ai_plan = apply
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

        async def execute(function, payload, strategy):
            state["calls"] += 1
            return function(payload, strategy)

        runtime.hass.async_add_executor_job = execute
        original_core = manager.build_plan_bundle
        manager.build_plan_bundle = lambda _payload, _strategy: {"rows": []}
        try:
            for _index in range(10):
                await runtime.request_optimizer_recalc("pv")
        finally:
            manager.build_plan_bundle = original_core

        assert state["calls"] == 1
        assert runtime._performance.counter("optimizer_semantic_snapshot_changed") == 1
        assert runtime._performance.counter("optimizer_semantic_snapshot_same") == 9
        assert runtime._performance.counter("optimizer_skipped_same_snapshot") == 9

    asyncio.run(scenario())


def test_full_and_granular_publish_counters_preserve_write_counts():
    runtime = task_runtime()
    runtime._performance.start()
    runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

    class Entity:
        hass = object()

        def __init__(self, key, proxy=False):
            self._deye_manager_key = key
            self.source_fn = (lambda _runtime: "sensor.source") if proxy else None
            self.writes = 0

        def async_write_ha_state(self):
            self.writes += 1

    ai = Entity("ai_state")
    diagnostics = Entity("diagnostics")
    proxy = Entity("pv_power", proxy=True)
    runtime.entities = [ai, diagnostics, proxy]

    runtime.notify_update(reason="tick_final")
    runtime._notify_entities_from_cache({"diagnostics"}, reason="optimizer_diagnostics")

    assert [ai.writes, diagnostics.writes, proxy.writes] == [1, 2, 1]
    assert runtime._performance.counter("notify_update_full_calls") == 1
    assert runtime._performance.counter("notify_granular_calls") == 1
    assert runtime._performance.counter("attempted_entity_writes_total") == 4
    assert runtime._performance.mapped("notify_update_full_by_reason") == {
        "tick_final": 1
    }
    channels = runtime._performance.mapped("attempted_entity_writes_by_channel")
    assert channels["ai_state"] == 1
    assert channels["diagnostics"] == 2
    assert channels["proxy"] == 1


def test_store_counters_count_only_actual_saves():
    async def scenario():
        runtime = task_runtime()
        runtime._performance.start()

        class Store:
            def __init__(self):
                self.calls = 0

            async def async_save(self, _payload):
                self.calls += 1

        runtime._ai_store = Store()
        runtime._learning_store = Store()
        runtime._samples_store = Store()
        await runtime.async_save_ai_data()
        await runtime.async_save_learning_history()
        await runtime.async_save_energy_history()

        assert runtime._ai_store.calls == 1
        assert runtime._learning_store.calls == 1
        assert runtime._samples_store.calls == 1
        assert runtime._performance.counter("ai_store_save_count") == 1
        assert runtime._performance.counter("learning_store_save_count") == 1
        assert runtime._performance.counter("energy_store_save_count") == 1
        assert runtime._performance.counter("energy_store_prepare_count") == 1

    asyncio.run(scenario())


def test_master_control_off_records_request_but_zero_executed_writes():
    async def scenario():
        runtime = task_runtime()
        runtime._performance.start()
        runtime.control_enabled = False
        runtime.control_status = "Wyłączone"

        with pytest.raises(manager.ControlDisabledError):
            await runtime._async_physical_service_call(
                "number",
                "set_value",
                {"entity_id": "number.deye_target", "value": 10},
                target_value=10,
            )

        assert runtime._performance.counter("inverter_write_requested") == 1
        assert runtime._performance.counter("inverter_write_executed") == 0
        assert runtime._performance.counter("tou_write_executed") == 0

    asyncio.run(scenario())


def test_payload_estimator_is_bounded_for_large_sequences():
    monitor = task_runtime()._performance
    small = [{"key": "x" * 20} for _index in range(16)]
    large = [{"key": "x" * 20}] * 100_000

    small_size = monitor._estimate_json_bytes(small)
    large_size = monitor._estimate_json_bytes(large)

    assert large_size > small_size
    assert large_size < 10_000_000

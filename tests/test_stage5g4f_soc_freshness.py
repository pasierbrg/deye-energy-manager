"""Stage 5G.4F SAFE: SOC report freshness, recovery and storm guardrails."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from test_manager_logic import (
    configure_selling_slot,
    control_number_calls,
    make_runtime,
    manager,
)


@contextmanager
def at(moment: datetime):
    previous = manager.ha_now
    manager.ha_now = lambda: moment
    try:
        yield
    finally:
        manager.ha_now = previous


def _timestamped_soc(runtime, moment: datetime, value: str = "80"):
    state = runtime.hass.states.get(runtime.battery_soc_sensor)
    state.state = value
    state.last_changed = moment
    state.last_updated = moment
    state.last_reported = moment
    return state


async def _noop(*_args, **_kwargs):
    return None


def test_identical_soc_stays_fresh_for_sixty_minutes_of_real_reports():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state = _timestamped_soc(runtime, started)
    semantic_snapshots = []

    for minutes in (0, 5, 10, 20, 60):
        reported = started + timedelta(minutes=minutes)
        state.last_reported = reported
        with at(reported):
            diagnostics = runtime.soc_diagnostics()
            assert diagnostics["status"] == "valid"
            assert diagnostics["freshness_source"] == "last_reported"
            assert diagnostics["reported_at"] == reported.isoformat()
            assert diagnostics["value_changed_at"] == started.isoformat()
            assert diagnostics["age_seconds"] == 0.0
            assert runtime.current_soc_or_none() == 80
            semantic_snapshots.append(
                runtime._semantic_optimizer_inputs({"soc_diagnostics": diagnostics})
            )

    assert semantic_snapshots == [semantic_snapshots[0]] * len(semantic_snapshots)


def test_soc_becomes_stale_only_after_no_report_for_more_than_900_seconds():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _timestamped_soc(runtime, started)

    with at(started + timedelta(seconds=900)):
        assert runtime.current_soc_or_none() == 80
        assert runtime.soc_diagnostics()["status"] == "valid"

    with at(started + timedelta(seconds=901)):
        diagnostics = runtime.soc_diagnostics()
        assert diagnostics["status"] == "stale"
        assert diagnostics["normalized_value"] is None
        assert diagnostics["age_seconds"] == 901.0
        assert runtime.current_soc_or_none() is None


def test_real_event_is_compatibility_observation_when_last_reported_is_missing():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state = runtime.hass.states.get(runtime.battery_soc_sensor)
    state.last_updated = started
    runtime._soc_quality_signature = runtime._soc_semantic_signature(
        runtime.soc_diagnostics()
    )

    observed = started + timedelta(minutes=10)
    with at(observed):
        material = runtime._observe_soc_source_event({
            "entity_id": runtime.battery_soc_sensor,
            "new_state": state,
        })
        diagnostics = runtime.soc_diagnostics()

    assert material is False
    assert diagnostics["status"] == "valid"
    assert diagnostics["freshness_source"] == "event_observed_at"
    assert diagnostics["observed_at"] == observed.isoformat()
    assert diagnostics["age_seconds"] == 0.0


def test_reload_does_not_make_an_unreported_source_fresh():
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    reloaded = make_runtime(soc="80")
    _timestamped_soc(reloaded, started)

    with at(started + timedelta(seconds=901)):
        diagnostics = reloaded.soc_diagnostics()
        current_soc = reloaded.current_soc_or_none()

    assert diagnostics["status"] == "stale"
    assert diagnostics["reported_at"] == started.isoformat()
    assert diagnostics["observed_at"] is None
    assert current_soc is None


def test_stale_to_valid_same_value_revalidates_and_releases_failure_latch():
    runtime = make_runtime(soc="80", price="1.00")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state = _timestamped_soc(runtime, started)

    with at(started):
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 10
        runtime._soc_quality_signature = runtime._soc_semantic_signature(
            runtime.soc_diagnostics()
        )

    stale_at = started + timedelta(seconds=901)
    with at(stale_at):
        assert runtime._refresh_soc_quality_signature() is True
        assert runtime.soc_diagnostics()["status"] == "stale"
        assert asyncio.run(runtime.async_apply_targets()) is False
        stale_fingerprint = runtime._last_slot_failure_signature
        first_defaults = len(control_number_calls(runtime))
        runtime.hass.services.calls.clear()
        assert asyncio.run(runtime.async_apply_targets()) is False
        assert control_number_calls(runtime) == []

    assert stale_fingerprint
    assert first_defaults > 0

    recovered_at = stale_at + timedelta(seconds=1)
    state.last_reported = recovered_at
    with at(recovered_at):
        valid_fingerprint = runtime._slot_failure_fingerprint("")
        assert valid_fingerprint != stale_fingerprint
        assert runtime._refresh_soc_quality_signature() is True
        assert runtime.current_soc_or_none() == 80
        assert asyncio.run(runtime.async_apply_targets()) is True

    assert runtime._last_slot_failure_signature == ""

    with at(recovered_at + timedelta(seconds=901)):
        assert runtime._refresh_soc_quality_signature() is True
        assert runtime.soc_diagnostics()["status"] == "stale"
        assert asyncio.run(runtime.async_apply_targets()) is False
        assert runtime._last_slot_failure_signature


def test_one_hundred_identical_reports_create_no_core_publish_save_or_write_storm():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state = _timestamped_soc(runtime, started)
    captured = {"timers": 0}
    original_state = manager.async_track_state_change_event
    original_point = manager.async_track_point_in_time

    def track_state(_hass, _entities, callback):
        captured["callback"] = callback
        return lambda: None

    def track_point(_hass, _callback, _when):
        captured["timers"] += 1
        return lambda: None

    manager.async_track_state_change_event = track_state
    manager.async_track_point_in_time = track_point
    runtime.schedule_ai_api_analysis = lambda: None
    before_requests = runtime.runtime_metrics["optimizer_recalc_requested"]
    before_notifies = runtime.runtime_metrics["notify_update_count"]
    before_calls = list(runtime.hass.services.calls)
    before_ai_dirty = runtime._ai_save_dirty
    before_learning_dirty = runtime._learning_save_dirty
    before_energy_dirty = runtime._energy_save_dirty
    try:
        with at(started):
            runtime._start_schedule_input_listener()
        for second in range(1, 101):
            report_time = started + timedelta(seconds=second)
            state.last_reported = report_time
            with at(report_time):
                captured["callback"]({
                    "entity_id": runtime.battery_soc_sensor,
                    "new_state": state,
                })
                assert runtime.current_soc_or_none() == 80
    finally:
        manager.async_track_state_change_event = original_state
        manager.async_track_point_in_time = original_point

    assert captured["timers"] == 0
    assert runtime.runtime_metrics["optimizer_recalc_requested"] == before_requests
    assert runtime.runtime_metrics["notify_update_count"] == before_notifies
    assert runtime.hass.services.calls == before_calls
    assert runtime._ai_save_dirty == before_ai_dirty
    assert runtime._learning_save_dirty == before_learning_dirty
    assert runtime._energy_save_dirty == before_energy_dirty
    assert runtime._optimizer_recalc_task is None


def test_minute_tick_requests_exactly_one_recalc_per_quality_transition():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state = _timestamped_soc(runtime, started)
    requests = []
    runtime._soc_quality_signature = runtime._soc_semantic_signature(
        runtime.soc_diagnostics()
    )
    runtime.request_optimizer_recalc = lambda reason: requests.append(reason)
    runtime.async_update_sold_energy_today = _noop
    runtime.async_update_solcast_history = _noop
    runtime.async_update_learning_history = _noop
    runtime.async_update_energy_sample = _noop
    runtime.async_update_weather_forecast = _noop
    runtime._refresh_tou_reconciliation_state = lambda: None
    runtime.control_enabled = False
    runtime.notify_update = lambda *_args, **_kwargs: None

    stale_at = started + timedelta(seconds=901)
    with at(stale_at):
        asyncio.run(runtime._async_tick_impl())
        asyncio.run(runtime._async_tick_impl())
    assert requests == ["soc"]

    state.last_reported = stale_at + timedelta(seconds=1)
    with at(state.last_reported):
        asyncio.run(runtime._async_tick_impl())
        asyncio.run(runtime._async_tick_impl())
    assert requests == ["soc", "soc"]

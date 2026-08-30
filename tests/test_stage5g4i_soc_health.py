"""Stage 5G.4I SAFE: provider-agnostic SOC source health contract."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from test_manager_logic import (
    FakeState,
    configure_selling_slot,
    control_number_calls,
    const,
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


def _install_same_device_health(runtime, started: datetime, *, same_device: bool = True):
    soc_id = runtime.battery_soc_sensor
    sibling_id = const.DEFAULT_BATTERY_POWER_SENSOR
    runtime.data[const.CONF_BATTERY_POWER_SENSOR] = sibling_id
    soc_state = runtime.hass.states.get(soc_id)
    soc_state.last_changed = started
    soc_state.last_updated = started
    soc_state.last_reported = started
    sibling = FakeState("0", {"unit_of_measurement": "W"})
    sibling.last_changed = started
    sibling.last_updated = started
    sibling.last_reported = started
    runtime.hass.states.values[sibling_id] = sibling
    identities = {
        soc_id: ("device", "inverter-a"),
        sibling_id: ("device", "inverter-a" if same_device else "inverter-b"),
    }
    runtime._entity_source_identity = lambda entity_id: identities.get(entity_id)
    return soc_state, sibling_id, sibling


def _health_event(entity_id, state, moment, *, old_state=None):
    return SimpleNamespace(
        data={"entity_id": entity_id, "old_state": old_state, "new_state": state},
        time_fired=moment,
    )


def test_silent_soc_remains_valid_for_three_hours_with_verified_sibling_health():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    soc_state, sibling_id, sibling = _install_same_device_health(runtime, started)
    requests = []
    runtime.request_optimizer_recalc = lambda reason: requests.append(reason)

    for minutes in range(5, 181, 5):
        moment = started + timedelta(minutes=minutes)
        sibling.last_reported = moment
        with at(moment):
            runtime._observe_soc_sibling_event(_health_event(sibling_id, sibling, moment))
            expected_reason = "own_soc_report" if minutes <= 15 else "sibling_health"
            assert runtime.soc_diagnostics()["freshness_reason"] == expected_reason
            assert runtime.current_soc_or_none() == 80

    assert soc_state.last_reported == started
    assert requests == []
    assert control_number_calls(runtime) == []


def test_all_health_stale_fails_closed_once_without_repeating_defaults():
    runtime = make_runtime(soc="80", price="1.00")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, _sibling_id, sibling = _install_same_device_health(runtime, started)
    with at(started):
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 10
        runtime._soc_quality_signature = runtime._soc_semantic_signature(runtime.soc_diagnostics())

    stale_at = started + timedelta(seconds=901)
    with at(stale_at):
        assert runtime._refresh_soc_quality_signature() is True
        assert runtime.current_soc_or_none() is None
        assert asyncio.run(runtime.async_apply_targets()) is False
        first_defaults = len(control_number_calls(runtime))
        runtime.hass.services.calls.clear()
        assert asyncio.run(runtime.async_apply_targets()) is False

    assert sibling.last_reported == started
    assert first_defaults > 0
    assert control_number_calls(runtime) == []


def test_zero_and_stable_measurements_are_valid_health_evidence():
    runtime = make_runtime(soc="100")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, sibling_id, sibling = _install_same_device_health(runtime, started)
    moment = started + timedelta(hours=3)
    sibling.last_reported = moment
    with at(moment):
        runtime._observe_soc_sibling_event(_health_event(sibling_id, sibling, moment))
        diagnostics = runtime.soc_diagnostics()
    assert sibling.state == "0"
    assert diagnostics["status"] == "valid"
    assert diagnostics["normalized_value"] == 100


def test_soc_value_change_is_one_material_transition():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state, _sibling_id, _sibling = _install_same_device_health(runtime, started)
    with at(started):
        runtime._soc_quality_signature = runtime._soc_semantic_signature(runtime.soc_diagnostics())
    changed = started + timedelta(minutes=1)
    state.state = "79"
    state.last_changed = changed
    state.last_updated = changed
    state.last_reported = changed
    with at(changed):
        assert runtime._observe_soc_source_event(
            _health_event(runtime.battery_soc_sensor, state, changed)
        ) is True
        assert runtime.current_soc_or_none() == 79
        assert runtime._refresh_soc_quality_signature() is False


def test_same_soc_recovers_from_sibling_health_and_releases_latch():
    runtime = make_runtime(soc="80", price="1.00")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, sibling_id, sibling = _install_same_device_health(runtime, started)
    with at(started):
        slot = configure_selling_slot(runtime)
        slot.minimum_sell_soc = 10
        runtime._soc_quality_signature = runtime._soc_semantic_signature(runtime.soc_diagnostics())
    stale_at = started + timedelta(seconds=901)
    with at(stale_at):
        assert runtime._refresh_soc_quality_signature() is True
        assert asyncio.run(runtime.async_apply_targets()) is False
        stale_fingerprint = runtime._last_slot_failure_signature

    recovered = stale_at + timedelta(seconds=1)
    sibling.last_reported = recovered
    with at(recovered):
        assert runtime._observe_soc_sibling_event(
            _health_event(sibling_id, sibling, recovered)
        ) is True
        assert runtime.current_soc_or_none() == 80
        assert runtime._slot_failure_fingerprint("") != stale_fingerprint
        assert asyncio.run(runtime.async_apply_targets()) is True
    assert runtime._last_slot_failure_signature == ""


def test_wrong_device_sibling_cannot_confirm_soc_health():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, sibling_id, sibling = _install_same_device_health(
        runtime, started, same_device=False
    )
    moment = started + timedelta(hours=3)
    sibling.last_reported = moment
    with at(moment):
        assert runtime._observe_soc_sibling_event(
            _health_event(sibling_id, sibling, moment)
        ) is False
        diagnostics = runtime.soc_diagnostics()
    assert diagnostics["status"] == "stale"
    assert diagnostics["freshness_reason"] == "no_fresh_source_health"


@pytest.mark.parametrize("provider", ["lewa_reka", "solarman", "sunsynk", "custom"])
def test_registry_health_contract_is_provider_agnostic(provider):
    runtime = make_runtime(soc="80")
    runtime.data[const.CONF_INVERTER_PROVIDER] = provider
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, sibling_id, sibling = _install_same_device_health(runtime, started)
    moment = started + timedelta(hours=3)
    sibling.last_reported = moment
    with at(moment):
        diagnostics = runtime.soc_diagnostics()
    assert diagnostics["status"] == "valid"
    assert diagnostics["freshness_reason"] == "sibling_health"
    assert diagnostics["source_health_source"] == f"sibling_health:{sibling_id}"


def test_restart_uses_real_state_health_but_never_artificial_now():
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    now = started + timedelta(hours=3)

    stale_runtime = make_runtime(soc="80")
    stale_soc = stale_runtime.hass.states.get(stale_runtime.battery_soc_sensor)
    stale_soc.last_updated = started
    stale_soc.last_reported = started
    with at(now):
        assert stale_runtime.soc_diagnostics()["status"] == "stale"
        assert stale_runtime._soc_source_observed_at == {}

    healthy_runtime = make_runtime(soc="80")
    _soc, _sibling_id, sibling = _install_same_device_health(healthy_runtime, started)
    sibling.last_reported = now
    with at(now):
        diagnostics = healthy_runtime.soc_diagnostics()
    assert diagnostics["status"] == "valid"
    assert diagnostics["freshness_reason"] == "sibling_health"
    assert healthy_runtime._soc_source_observed_at == {}


def test_one_hundred_health_reports_do_not_create_runtime_storm():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, sibling_id, sibling = _install_same_device_health(runtime, started)
    runtime._soc_quality_signature = runtime._soc_semantic_signature(runtime.soc_diagnostics())
    before_requests = runtime.runtime_metrics["optimizer_recalc_requested"]
    before_notifies = runtime.runtime_metrics["notify_update_count"]
    before_calls = list(runtime.hass.services.calls)
    before_dirty = (
        runtime._ai_save_dirty,
        runtime._learning_save_dirty,
        runtime._energy_save_dirty,
    )

    for second in range(1, 101):
        moment = started + timedelta(seconds=second)
        sibling.last_reported = moment
        with at(moment):
            assert runtime._observe_soc_sibling_event(
                _health_event(sibling_id, sibling, moment)
            ) is False

    assert runtime.runtime_metrics["optimizer_recalc_requested"] == before_requests
    assert runtime.runtime_metrics["notify_update_count"] == before_notifies
    assert runtime.hass.services.calls == before_calls
    assert (
        runtime._ai_save_dirty,
        runtime._learning_save_dirty,
        runtime._energy_save_dirty,
    ) == before_dirty
    assert runtime._optimizer_recalc_task is None


def test_one_hundred_health_reports_follow_real_listener_without_storm():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    _soc, sibling_id, sibling = _install_same_device_health(runtime, started)
    old_state = FakeState("0", {"unit_of_measurement": "W"})
    old_state.last_reported = started
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
    before_dirty = (
        runtime._ai_save_dirty,
        runtime._learning_save_dirty,
        runtime._energy_save_dirty,
    )
    try:
        with at(started):
            runtime._start_schedule_input_listener()
        for second in range(1, 101):
            moment = started + timedelta(seconds=second)
            sibling.last_reported = moment
            with at(moment):
                captured["callback"](_health_event(
                    sibling_id,
                    sibling,
                    moment,
                    old_state=old_state,
                ))
    finally:
        manager.async_track_state_change_event = original_state
        manager.async_track_point_in_time = original_point

    assert captured["timers"] == 0
    assert runtime.runtime_metrics["optimizer_recalc_requested"] == before_requests
    assert runtime.runtime_metrics["notify_update_count"] == before_notifies
    assert runtime.hass.services.calls == before_calls
    assert (
        runtime._ai_save_dirty,
        runtime._learning_save_dirty,
        runtime._energy_save_dirty,
    ) == before_dirty
    assert runtime._optimizer_recalc_task is None


def test_provider_without_health_uses_bounded_compatibility_then_fails_closed():
    runtime = make_runtime(soc="80")
    started = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    state = runtime.hass.states.get(runtime.battery_soc_sensor)
    state.last_updated = started
    if hasattr(state, "last_reported"):
        del state.last_reported
    with at(started + timedelta(seconds=900)):
        diagnostics = runtime.soc_diagnostics()
        assert diagnostics["status"] == "valid"
        assert diagnostics["freshness_reason"] == "compatibility_fallback"
    with at(started + timedelta(seconds=901)):
        diagnostics = runtime.soc_diagnostics()
        assert diagnostics["status"] == "stale"
        assert diagnostics["freshness_reason"] == "no_fresh_source_health"

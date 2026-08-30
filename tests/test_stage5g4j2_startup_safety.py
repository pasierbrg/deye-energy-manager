"""Stage 5G.4J.2 cold-start lifecycle, budget and timeout regressions."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import types

import pytest

from test_manager_logic import FakeState, const, manager
from test_stage5g1_lifecycle import task_runtime
from test_stage5g4j_target_fulfillment import core, physical_case, sale_profile


ROOT = Path(__file__).resolve().parents[1]


class FakeBus:
    def __init__(self):
        self._listeners = []

    def async_listen_once(self, event_type, callback):
        record = [event_type, callback, True]
        self._listeners.append(record)

        def unsubscribe():
            record[2] = False

        return unsubscribe

    @property
    def active(self):
        return sum(1 for _event, _callback, enabled in self._listeners if enabled)

    def fire(self, event_type="homeassistant_started"):
        for record in list(self._listeners):
            registered, callback, enabled = record
            if enabled and registered == event_type:
                record[2] = False
                callback(SimpleNamespace(event_type=event_type))


def three_profile_inputs() -> dict:
    values = physical_case(13000)
    values["user_profiles"]["profiles"] = {
        "morning_sale": sale_profile(6, 3000, start="06:00", end="10:00"),
        "evening_sale": sale_profile(16, 5000, start="18:00", end="22:00"),
        "charging": {
            "enabled": True,
            "type": "charging",
            "start": "10:00",
            "end": "16:00",
            "active_days": ["śr"],
            "priority": "normal",
            "goal_character": "preferred",
            "allow_partial": True,
            "target_type": "energy",
            "target_value": 8,
            "preferred_power_w": 3000,
            "source": "any",
            "min_net_result": 0,
        },
    }
    return values


def install_core(runtime, *, real=False, during_execute=None):
    state = {"calls": 0, "published": 0}
    payload = three_profile_inputs()
    runtime._prepare_ai_plan_48h = lambda: {
        "payload": deepcopy(payload),
        "selected_strategy": "balanced",
        "snapshot_id": f"snapshot-{state['calls']}",
        "current": datetime.now(UTC),
        "battery_model": {},
    }
    runtime._optimizer_plan_is_current = lambda _prepared: False

    def apply(_prepared, result):
        runtime.optimizer_plan = result
        state["published"] += 1
        return result, True

    runtime._apply_prepared_ai_plan = apply
    runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

    async def execute(function, values, strategy):
        state["calls"] += 1
        if during_execute is not None:
            during_execute(runtime, state["calls"])
        if real:
            return await asyncio.to_thread(function, values, strategy)
        return {"rows": [], "plan_id": f"plan-{state['calls']}"}

    runtime.hass.async_add_executor_job = execute
    return state


def cold_runtime():
    runtime = task_runtime()
    runtime.hass.state = "starting"
    runtime.hass.bus = FakeBus()
    runtime._platform_setup_in_progress = True
    runtime._initial_optimizer_pending = True
    return runtime


def test_cold_setup_finishes_with_zero_core_and_zero_optimizer_tasks():
    async def scenario():
        runtime = cold_runtime()
        state = install_core(runtime)
        runtime.finish_platform_setup()
        await asyncio.sleep(0)
        assert state["calls"] == 0
        assert runtime._optimizer_recalc_task is None
        assert runtime.hass.created_tasks == []
        assert runtime.hass.bus.active == 1

    asyncio.run(scenario())


def test_large_restored_cache_is_published_without_prestarted_core():
    async def scenario():
        runtime = cold_runtime()
        restored = core.build_plan_bundle(three_profile_inputs(), "balanced")
        runtime.optimizer_plan = restored
        runtime._optimizer_public_snapshot = restored
        runtime.optimizer_plan_history = [
            {"plan_id": f"history-{index}", "comparison": {"same": True}}
            for index in range(30)
        ]
        state = install_core(runtime)
        runtime.finish_platform_setup()
        await asyncio.sleep(0)
        assert state["calls"] == 0
        assert runtime.optimizer_plan["plan_id"] == restored["plan_id"]
        assert len(runtime.optimizer_plan_history) == 30
        assert runtime.hass.created_tasks == []

    asyncio.run(scenario())


@pytest.mark.parametrize("fresh", [True, False])
def test_valid_and_stale_soc_do_not_bypass_cold_start_gate(fresh):
    async def scenario():
        runtime = cold_runtime()
        soc = runtime.hass.states.get(runtime.battery_soc_sensor)
        if not fresh:
            soc.last_updated = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
            soc.last_changed = soc.last_updated
        state = install_core(runtime)
        runtime.finish_platform_setup()
        await asyncio.sleep(0)
        assert state["calls"] == 0
        assert runtime._optimizer_recalc_task is None

    asyncio.run(scenario())


def test_hundred_prestarted_requests_remain_pending_without_creating_a_task():
    async def scenario():
        runtime = cold_runtime()
        state = install_core(runtime)
        runtime.finish_platform_setup()
        for _index in range(100):
            runtime.request_optimizer_recalc("prestarted_burst")
        await asyncio.sleep(0)

        assert state["calls"] == 0
        assert runtime._optimizer_recalc_task is None
        assert runtime.hass.created_tasks == []
        assert runtime._optimizer_recalc_pending is True
        assert "prestarted_burst" in runtime._optimizer_pending_reasons

    asyncio.run(scenario())


def test_full_setup_entry_returns_before_started_then_real_core_runs_once():
    async def scenario():
        cv = types.ModuleType("homeassistant.helpers.config_validation")
        cv.string = str
        cv.boolean = bool
        typing_module = types.ModuleType("homeassistant.helpers.typing")
        typing_module.ConfigType = dict
        voluptuous = types.ModuleType("voluptuous")
        voluptuous.Schema = lambda value: value
        voluptuous.Required = lambda key: key
        voluptuous.Optional = lambda key: key
        voluptuous.All = lambda *_validators: (lambda value: value)
        voluptuous.In = lambda _values: (lambda value: value)
        voluptuous.Coerce = lambda converter: converter
        voluptuous.Range = lambda **_kwargs: (lambda value: value)
        voluptuous.Length = lambda **_kwargs: (lambda value: value)
        sys.modules[cv.__name__] = cv
        sys.modules[typing_module.__name__] = typing_module
        sys.modules[voluptuous.__name__] = voluptuous
        sys.modules["homeassistant.core"].SupportsResponse = SimpleNamespace(ONLY="only")

        name = "custom_components.deye_energy_manager.stage5g4j2_integration"
        spec = importlib.util.spec_from_file_location(
            name,
            ROOT / "custom_components" / "deye_energy_manager" / "__init__.py",
        )
        integration = importlib.util.module_from_spec(spec)
        sys.modules[name] = integration
        assert spec.loader is not None
        spec.loader.exec_module(integration)

        runtime = cold_runtime()
        state = install_core(runtime, real=True)

        async def lightweight_start():
            runtime._initial_optimizer_pending = True
            runtime._optimizer_pending_reasons.add("startup")
            runtime._optimizer_recalc_pending = True

        runtime.async_start = lightweight_start
        integration.DeyeEnergyManagerRuntime = lambda **_kwargs: runtime
        integration._STATIC_PATH_REGISTERED = False
        runtime.hass.data = {}
        runtime.hass.http = SimpleNamespace(
            async_register_static_path=lambda *_args, **_kwargs: None
        )

        class ConfigEntries:
            async def async_forward_entry_setups(self, _entry, _platforms):
                return None

        runtime.hass.config_entries = ConfigEntries()
        runtime.hass.services.async_register = lambda *_args, **_kwargs: None
        entry = SimpleNamespace(entry_id="setup-entry", data={}, options={})

        started = time.perf_counter()
        assert await integration.async_setup_entry(runtime.hass, entry) is True
        assert time.perf_counter() - started < 0.2
        assert state["calls"] == 0
        assert runtime._optimizer_recalc_task is None
        assert runtime.hass.created_tasks == []

        runtime.hass.state = "running"
        runtime.hass.bus.fire()
        await runtime._optimizer_recalc_task
        assert state["calls"] == 1
        assert runtime.optimizer_plan.get("plan_id")
        assert runtime.runtime_metrics["optimizer_recalc_max_active"] == 1

    asyncio.run(scenario())


def test_started_event_runs_exactly_one_initial_real_core():
    async def scenario():
        runtime = cold_runtime()
        state = install_core(runtime, real=True)
        runtime.finish_platform_setup()
        runtime.hass.state = "running"
        runtime.hass.bus.fire()
        task = runtime._optimizer_recalc_task
        assert task is not None
        await task
        runtime.hass.bus.fire()
        await asyncio.sleep(0)
        assert state["calls"] == 1
        assert runtime.runtime_metrics["optimizer_initial_requested"] == 1
        assert runtime.runtime_metrics["optimizer_initial_completed"] == 1
        assert runtime._initial_optimizer_completed is True

    asyncio.run(scenario())


def test_reload_while_running_starts_initial_core_without_listener():
    async def scenario():
        runtime = cold_runtime()
        runtime.hass.state = "running"
        state = install_core(runtime)
        runtime.finish_platform_setup()
        await runtime._optimizer_recalc_task
        assert state["calls"] == 1
        assert runtime.hass.bus.active == 0

    asyncio.run(scenario())


def test_hundred_events_allow_one_initial_and_one_followup_without_recovery():
    async def scenario():
        def burst(runtime, call_number):
            if call_number in (1, 2):
                for _index in range(100):
                    runtime.request_optimizer_recalc("startup_burst")

        runtime = cold_runtime()
        state = install_core(runtime, during_execute=burst)
        runtime.finish_platform_setup()
        runtime.hass.state = "running"
        runtime.hass.bus.fire()
        initial_task = runtime._optimizer_recalc_task
        await initial_task
        await asyncio.sleep(0)
        assert state["calls"] == 2
        assert runtime.runtime_metrics["optimizer_recalc_followup"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_max_active"] == 1
        assert len(runtime.hass.created_tasks) == 1
        assert runtime._optimizer_recalc_task is None
        assert runtime._optimizer_recalc_pending is True

    asyncio.run(scenario())


def test_unload_before_started_removes_callback_and_never_runs_core():
    async def scenario():
        runtime = cold_runtime()
        state = install_core(runtime)
        runtime.finish_platform_setup()
        assert runtime.hass.bus.active == 1
        await runtime.async_unload()
        assert runtime.hass.bus.active == 0
        runtime.hass.state = "running"
        runtime.hass.bus.fire()
        await asyncio.sleep(0)
        assert state["calls"] == 0
        assert runtime._optimizer_recalc_task is None

    asyncio.run(scenario())


def test_unload_active_core_is_bounded():
    async def scenario():
        runtime = cold_runtime()
        release = asyncio.Event()
        runtime._prepare_ai_plan_48h = lambda: {
            "payload": {},
            "selected_strategy": "balanced",
            "snapshot_id": "pending",
            "current": datetime.now(UTC),
            "battery_model": {},
        }
        runtime._optimizer_plan_is_current = lambda _prepared: False
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

        async def execute(_function, *_args):
            await release.wait()
            return {"rows": []}

        runtime.hass.async_add_executor_job = execute
        runtime.finish_platform_setup()
        runtime.hass.state = "running"
        runtime.hass.bus.fire()
        await asyncio.sleep(0)
        started = time.perf_counter()
        await runtime.async_unload()
        assert time.perf_counter() - started < 1.0
        assert runtime._optimizer_recalc_task is None

    asyncio.run(scenario())


def test_weather_timeout_preserves_cache_and_does_not_fail_startup():
    async def scenario():
        runtime = task_runtime()
        entity_id = "weather.slow"
        runtime.data[const.CONF_WEATHER_ENTITY] = entity_id
        runtime.hass.states.values[entity_id] = FakeState("sunny", {})
        runtime.weather_forecast_timeout = 0.01
        runtime.weather_forecast = [{"datetime": "2026-08-20T12:00:00+00:00"}]
        runtime.weather_daily_forecast = [{"datetime": "2026-08-20"}]

        async def never_returns(*_args, **_kwargs):
            await asyncio.Event().wait()

        runtime.hass.services.async_call = never_returns
        started = time.perf_counter()
        await runtime.async_update_weather_forecast()
        assert time.perf_counter() - started < 0.2
        assert runtime.weather_forecast == [{"datetime": "2026-08-20T12:00:00+00:00"}]
        assert runtime.weather_daily_forecast == [{"datetime": "2026-08-20"}]
        assert "timeout" in runtime.weather_last_error

    asyncio.run(scenario())


def test_bundle_operation_budget_returns_controlled_fail_closed_result():
    original = core.MAX_BUNDLE_BUILD_PLAN_CALLS
    core.MAX_BUNDLE_BUILD_PLAN_CALLS = 1
    try:
        result = core.build_plan_bundle(three_profile_inputs(), "balanced")
    finally:
        core.MAX_BUNDLE_BUILD_PLAN_CALLS = original
    assert result["budget_exceeded"] is True
    assert result["recommended_write"] is False
    assert result["writes_performed"] is False
    assert result["rows"] == []
    assert result["core_budget"]["usage"]["build_energy_plan_calls"] == 2


def test_realistic_exhausted_charge_path_hits_default_budget_under_five_seconds():
    values = three_profile_inputs()
    values.update(
        soc=0,
        min_soc=0,
        effective_min_soc=0,
        target_soc=100,
        charge_kwh_per_hour=0,
        allow_grid_charge=True,
        price_includes_distribution=True,
        osd_data_complete=True,
    )
    started = time.perf_counter()
    result = core.build_plan_bundle(values, "safe")
    elapsed = time.perf_counter() - started

    assert elapsed < 5
    assert result["budget_exceeded"] is True
    assert result["recommended_write"] is False
    assert result["writes_performed"] is False
    assert result["rows"] == []
    assert result["core_budget"]["limits"]["build_energy_plan_calls"] == 64
    assert result["core_budget"]["usage"]["build_energy_plan_calls"] == 65


def test_manager_keeps_last_plan_after_budget_exceeded():
    async def scenario():
        runtime = task_runtime()
        previous = {"plan_id": "last-good", "algorithm_version": manager.ALGORITHM_VERSION}
        runtime.optimizer_plan = deepcopy(previous)
        runtime._prepare_ai_plan_48h = lambda: {
            "payload": {},
            "selected_strategy": "balanced",
            "snapshot_id": "expensive-input",
            "current": datetime.now(UTC),
            "battery_model": {},
        }
        runtime._optimizer_plan_is_current = lambda _prepared: False
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

        async def execute(_function, *_args):
            return {
                "budget_exceeded": True,
                "failure_reason": "simulate_calls:641>640",
                "core_budget": {"limits": {"simulate_calls": 640}, "usage": {"simulate_calls": 641}},
            }

        runtime.hass.async_add_executor_job = execute
        await runtime.request_optimizer_recalc("test_budget")
        assert runtime.optimizer_plan == previous
        assert runtime._optimizer_budget_status["status"] == "budget_exceeded"
        assert runtime._optimizer_budget_blocked_snapshot_id == "expensive-input"
        assert runtime.runtime_metrics["optimizer_budget_exceeded"] == 1

    asyncio.run(scenario())


def test_identical_fulfillment_is_stable_and_does_not_run_core_again():
    async def scenario():
        runtime = task_runtime()
        plan = core.build_plan_bundle(three_profile_inputs(), "balanced")
        snapshot = "stable-input"
        runtime.optimizer_plan = plan
        runtime._optimizer_input_snapshot_id = snapshot
        runtime._optimizer_last_plan_id = plan["plan_id"]
        runtime._prepare_ai_plan_48h = lambda: {
            "payload": three_profile_inputs(),
            "selected_strategy": "balanced",
            "snapshot_id": snapshot,
            "current": datetime.now(UTC),
            "battery_model": {},
        }
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None
        calls = 0

        async def execute(*_args):
            nonlocal calls
            calls += 1
            return {}

        runtime.hass.async_add_executor_job = execute
        await runtime.request_optimizer_recalc("same_ledger")
        assert calls == 0
        assert runtime.runtime_metrics["optimizer_recalc_skipped_same_snapshot"] == 1

    asyncio.run(scenario())


def test_mainthread_prepare_and_snapshot_workload_stays_bounded():
    runtime = task_runtime()
    runtime.hass.config = SimpleNamespace(time_zone="UTC")
    runtime.optimizer_plan = core.build_plan_bundle(three_profile_inputs(), "balanced")
    runtime._optimizer_public_snapshot = runtime.optimizer_plan
    runtime.learning_history = [
        {
            "hour": f"2026-08-{1 + index // 24:02d}T{index % 24:02d}:00:00+00:00",
            "local_date": f"2026-08-{1 + index // 24:02d}",
            "local_hour": index % 24,
            "pv_kwh": 1.0,
            "load_kwh": 0.8,
            "soc_start": 50,
            "soc_end": 50,
        }
        for index in range(168)
    ]
    durations = []
    for _index in range(20):
        started = time.perf_counter()
        runtime._prepare_ai_plan_48h()
        snapshot = runtime.build_ai_state_snapshot()
        manager.snapshot_id(snapshot)
        durations.append((time.perf_counter() - started) * 1000)
    ordered = sorted(durations)
    p95 = ordered[int(len(ordered) * 0.95) - 1]
    assert p95 <= 50
    assert max(durations) <= 200

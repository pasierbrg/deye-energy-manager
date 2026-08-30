"""Behavior-preserving performance regressions for Stage 5G.3B.1."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import types

import pytest

from test_manager_logic import FakeState, const, make_runtime, manager
from test_stage5g1_lifecycle import task_runtime


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "deye_energy_manager"


def _load_sensor_module():
    """Load the real sensor helpers on top of the lightweight HA test stubs."""
    sensor_component = types.ModuleType("homeassistant.components.sensor")
    sensor_component.SensorEntity = type("SensorEntity", (), {})
    sensor_component.SensorDeviceClass = types.SimpleNamespace(
        BATTERY="battery",
        POWER="power",
        ENERGY="energy",
        CURRENT="current",
        VOLTAGE="voltage",
        TEMPERATURE="temperature",
        FREQUENCY="frequency",
    )
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.MATCH_ALL = "*"
    previous_sensor = sys.modules.get("homeassistant.components.sensor")
    previous_const = sys.modules.get("homeassistant.const")
    module_name = "custom_components.deye_energy_manager.sensor_stage5g3b1"
    try:
        sys.modules["homeassistant.components.sensor"] = sensor_component
        sys.modules["homeassistant.const"] = ha_const
        spec = importlib.util.spec_from_file_location(module_name, PACKAGE / "sensor.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_sensor is None:
            sys.modules.pop("homeassistant.components.sensor", None)
        else:
            sys.modules["homeassistant.components.sensor"] = previous_sensor
        if previous_const is None:
            sys.modules.pop("homeassistant.const", None)
        else:
            sys.modules["homeassistant.const"] = previous_const


sensor_module = _load_sensor_module()


def _count_learning_builds(runtime):
    original = runtime._build_learning_summary
    counter = {"calls": 0}

    def counted(**kwargs):
        counter["calls"] += 1
        return original(**kwargs)

    runtime._build_learning_summary = counted
    return counter


def _history_row(hour="2026-08-10T12:00:00+00:00", pv=1.5):
    return {
        "hour": hour,
        "complete": True,
        "pv_kwh": pv,
        "load_kwh": 1.0,
        "grid_export_kwh": 0.2,
        "battery_charge_kwh": 0.1,
        "battery_discharge_kwh": 0.1,
        "soc_avg": 50.0,
        "sell_price_avg": 0.5,
        "buy_price_avg": 0.7,
        "channel_quality": {
            "pv": {
                "usable_for_learning": True,
                "level": "full",
                "coverage_percent": 100,
                "quality_score": 100,
            }
        },
    }


def test_learning_summary_reuses_one_heavy_build_for_unchanged_inputs():
    runtime = make_runtime()
    runtime.learning_history = [_history_row()]
    counter = _count_learning_builds(runtime)

    first = runtime.learning_summary()
    second = runtime.learning_summary()

    assert counter["calls"] == 1
    assert second is first
    assert second == first


def test_learning_history_replacement_invalidates_cached_summary():
    runtime = make_runtime()
    runtime.learning_history = [_history_row(pv=1.0)]
    counter = _count_learning_builds(runtime)
    first = runtime.learning_summary()

    runtime.learning_history = [_history_row(pv=2.0)]
    second = runtime.learning_summary()

    assert counter["calls"] == 2
    assert first["hourly_profile"][0]["pv_kwh"] == 1.0
    assert second["hourly_profile"][0]["pv_kwh"] == 2.0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda runtime: setattr(
            runtime,
            "solcast_history",
            [{
                "date": "2026-08-09",
                "forecast_kwh": 10,
                "actual_kwh": 9,
                "accuracy_percent": 90,
                "day_complete": True,
            }],
        ),
        lambda runtime: runtime.solcast_tracking.update(forecast=10, actual=5),
        lambda runtime: setattr(runtime, "load_profile_7x24", {"0:0": {"value": 1}}),
        lambda runtime: setattr(runtime, "pv_learning_profile", {"0": {"value": 1}}),
        lambda runtime: runtime.energy_samples.append({"timestamp": "2026-08-10T12:00:00+00:00"}),
        lambda runtime: runtime.daily_archive.append({"date": "2026-08-09"}),
        lambda runtime: runtime.monthly_archive.append({"month": "2026-08"}),
    ],
)
def test_every_learning_summary_data_family_invalidates_cache(mutate):
    runtime = make_runtime()
    counter = _count_learning_builds(runtime)
    runtime.learning_summary()

    mutate(runtime)
    runtime.learning_summary()

    assert counter["calls"] == 2


def test_weather_public_context_change_invalidates_learning_cache():
    runtime = make_runtime()
    runtime.data[const.CONF_WEATHER_ENTITY] = "weather.home"
    runtime.hass.states.values["weather.home"] = FakeState(
        "sunny", {"temperature": 20, "cloud_coverage": 10}
    )
    counter = _count_learning_builds(runtime)
    first = runtime.learning_summary()

    runtime.hass.states.values["weather.home"] = FakeState(
        "rainy", {"temperature": 14, "cloud_coverage": 90}
    )
    second = runtime.learning_summary()

    assert counter["calls"] == 2
    assert first["weather"]["condition"] == "sunny"
    assert second["weather"]["condition"] == "rainy"


def test_historical_solcast_value_and_attrs_share_one_cached_heavy_snapshot(monkeypatch):
    runtime = make_runtime()
    monkeypatch.setattr(
        manager,
        "ha_now",
        lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    runtime.solcast_history = [{
        "date": "2026-08-09",
        "forecast_kwh": 10,
        "actual_kwh": 8,
        "accuracy_percent": 80,
        "day_complete": True,
    }]
    runtime.solcast_tracking = {"date": "2026-08-10", "forecast": 12, "actual": 3}
    counter = _count_learning_builds(runtime)

    native_value = sensor_module.solcast_accuracy_value(runtime)
    attributes = sensor_module.solcast_accuracy_attrs(runtime)

    assert counter["calls"] == 1
    assert native_value == 80.0
    assert attributes["history"] == runtime.solcast_history
    assert attributes["historical_accuracy_pct"] == 80.0
    assert attributes["historical_accuracy_percent"] == 80.0
    assert attributes["historical_correction_factor"] == pytest.approx(0.99)
    assert attributes["completed_days"] == 1
    assert attributes["current_day"] == "2026-08-10"
    assert attributes["forecast_today_kwh"] == 12.0
    assert attributes["production_today_kwh"] == 3.0
    assert attributes["actual_today_kwh"] == 3.0
    assert attributes["forecast_difference_today_kwh"] == -9.0
    assert attributes["difference_today_kwh"] == -9.0
    assert attributes["realization_today_pct"] == 25.0
    assert attributes["forecast_progress_percent"] == 25.0
    assert attributes["day_complete"] is False
    assert isinstance(native_value, float)
    assert isinstance(attributes["history"], list)


def test_live_state_timestamp_is_technical_but_freshness_status_is_semantic():
    runtime = make_runtime()
    fresh = {
        "live_state": {
            "timestamp": "2026-08-10T12:00:00+00:00",
            "soc_pct": 50,
            "pv_power_w": 1200,
            "channels": {"soc": {"status": "ok", "usable": True}},
        },
        "soc_diagnostics": {"status": "valid", "valid": True, "age_seconds": 1},
    }
    later = deepcopy(fresh)
    later["live_state"]["timestamp"] = "2026-08-10T12:00:59+00:00"
    later["soc_diagnostics"]["age_seconds"] = 60
    stale = deepcopy(later)
    stale["live_state"]["channels"]["soc"].update(status="stale", usable=False)
    stale["soc_diagnostics"].update(
        status="stale", valid=False, reason="Odczyt SOC (901 s)"
    )

    assert runtime._semantic_optimizer_inputs(fresh) == runtime._semantic_optimizer_inputs(later)
    assert runtime._semantic_optimizer_inputs(fresh) != runtime._semantic_optimizer_inputs(stale)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("soc_diagnostics", "normalized_value"), 51),
        (("live_state", "pv_power_w"), 1300),
        (("live_state", "home_power_w"), 850),
        (("live_state", "grid_power_w"), -250),
        (("live_state", "sell_price"), 0.75),
        (("pv_forecast", "0"), 6.5),
    ],
)
def test_real_optimizer_input_change_remains_semantic(path, value):
    runtime = make_runtime()
    first = {
        "soc_diagnostics": {"status": "valid", "normalized_value": 50},
        "live_state": {
            "timestamp": "2026-08-10T12:00:00+00:00",
            "pv_power_w": 1200,
            "home_power_w": 800,
            "grid_power_w": 0,
            "sell_price": 0.5,
        },
        "pv_forecast": [5.0, 7.0],
    }
    second = deepcopy(first)
    parent, key = path
    if isinstance(second[parent], list):
        second[parent][int(key)] = value
    else:
        second[parent][key] = value

    assert runtime._semantic_optimizer_inputs(first) != runtime._semantic_optimizer_inputs(second)


def test_sixty_timestamp_only_requests_run_core_once_and_real_change_runs_again():
    async def scenario():
        runtime = task_runtime()
        state = {"timestamp": 0, "pv": 1200, "last": None, "core_calls": 0}

        def prepare():
            payload = {
                "live_state": {
                    "timestamp": (
                        datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
                        + timedelta(seconds=state["timestamp"])
                    ).isoformat(),
                    "pv_power_w": state["pv"],
                    "home_power_w": 800,
                }
            }
            semantic = runtime._semantic_optimizer_inputs(payload)
            return {
                "payload": payload,
                "selected_strategy": "balanced",
                "snapshot_id": manager.snapshot_id({"semantic_inputs": semantic}),
                "current": datetime.now(UTC),
                "battery_model": {},
            }

        runtime._prepare_ai_plan_48h = prepare
        runtime._optimizer_plan_is_current = (
            lambda prepared: state["last"] == prepared["snapshot_id"]
        )

        def apply(prepared, result):
            state["last"] = prepared["snapshot_id"]
            return result, True

        runtime._apply_prepared_ai_plan = apply
        runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

        async def execute(_function, _payload, _strategy):
            state["core_calls"] += 1
            return {"rows": []}

        runtime.hass.async_add_executor_job = execute
        for second in range(60):
            state["timestamp"] = second
            await runtime.request_optimizer_recalc("pv")

        assert state["core_calls"] == 1
        assert runtime.runtime_metrics["optimizer_recalc_skipped_same_snapshot"] == 59

        state["pv"] = 1300
        await runtime.request_optimizer_recalc("pv")
        assert state["core_calls"] == 2

    asyncio.run(scenario())


def test_stage5g3b1_does_not_change_full_publish_contract():
    runtime = make_runtime()

    class Entity:
        def __init__(self, key):
            self._deye_manager_key = key
            self.hass = object()
            self.writes = 0

        def async_write_ha_state(self):
            self.writes += 1

    runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None
    runtime.entities = [Entity("manager_status"), Entity("ai_state"), Entity("diagnostics")]

    runtime.notify_update()

    assert [entity.writes for entity in runtime.entities] == [1, 1, 1]

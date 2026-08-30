"""Stage 5H.3 canonical Solcast contract and consumer regressions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from test_manager_logic import FakeState, make_runtime, manager
from test_stage5g3b1_performance import sensor_module


ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components" / "deye_energy_manager" / "www" / "deye-energy-manager-card.js"


def _set_tracking(
    runtime,
    now: datetime,
    *,
    initial: float,
    latest: float,
    actual: float,
    status: str = "ok",
) -> None:
    runtime.solcast_tracking = {
        "date": now.date().isoformat(),
        "forecast": initial,
        "initial_forecast_kwh": initial,
        "latest_forecast_kwh": latest,
        "actual": actual,
        "updated_at": now.isoformat(),
        "forecast_status": status,
        "forecast_source": runtime.solcast_forecast_today_sensor,
    }
    runtime._invalidate_learning_summary_cache()


def _set_solcast_states(
    runtime,
    *,
    today: float,
    actual: float,
    remaining: float,
    tomorrow: float,
) -> None:
    runtime.hass.states.values[runtime.solcast_forecast_today_sensor] = FakeState(str(today))
    runtime.hass.states.values[runtime.daily_pv_production_sensor] = FakeState(str(actual))
    runtime.hass.states.values[runtime.solcast_remaining_today_sensor] = FakeState(str(remaining))
    runtime.hass.states.values[runtime.solcast_forecast_tomorrow_sensor] = FakeState(str(tomorrow))


def test_t1_latest_forecast_is_the_single_realization_denominator(monkeypatch):
    now = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    _set_tracking(runtime, now, initial=39.47, latest=33.10, actual=31.10)

    metrics = runtime.solcast_current_day_metrics(historical_accuracy_pct=77.1)

    assert metrics["forecast_today_kwh"] == 33.10
    assert metrics["production_today_kwh"] == 31.10
    assert metrics["forecast_difference_today_kwh"] == -2.0
    assert metrics["realization_today_pct"] == 94.0
    assert metrics["historical_accuracy_pct"] == 77.1
    assert metrics["initial_forecast_kwh"] == 39.47


def test_t2_realization_above_100_percent_is_not_clamped(monkeypatch):
    now = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    _set_tracking(runtime, now, initial=30, latest=30, actual=35)

    assert runtime.solcast_current_day_metrics()["realization_today_pct"] == 116.7


def test_t3_zero_forecast_is_unknown_not_a_false_zero_percent(monkeypatch):
    now = datetime(2026, 8, 29, 1, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    _set_tracking(runtime, now, initial=0, latest=0, actual=0)

    metrics = runtime.solcast_current_day_metrics()

    assert metrics["forecast_today_kwh"] is None
    assert metrics["realization_today_pct"] is None
    assert metrics["forecast_difference_today_kwh"] is None
    assert metrics["data_status"] == "zero_forecast"


@pytest.mark.parametrize("status", ("unavailable", "stale"))
def test_t4_unavailable_or_stale_forecast_fails_closed(monkeypatch, status):
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    _set_tracking(runtime, now, initial=33.1, latest=33.1, actual=31.1, status=status)

    metrics = runtime.solcast_current_day_metrics()

    assert metrics["forecast_today_kwh"] is None
    assert metrics["realization_today_pct"] is None
    assert metrics["data_status"] == status


def test_t4_source_timestamp_is_rejected_after_daily_freshness_window(monkeypatch):
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    stale = FakeState("33.1")
    stale.last_updated = now - timedelta(hours=31)
    runtime.hass.states.values[runtime.solcast_forecast_today_sensor] = stale

    reading = runtime.solcast_forecast_today_reading()

    assert reading["status"] == "stale"
    assert runtime.solcast_forecast_today_value() == 0


def test_t5_live_realization_and_historical_accuracy_stay_separate_everywhere(monkeypatch):
    now = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    runtime.solcast_history = [{
        "date": "2026-08-28",
        "forecast_kwh": 40,
        "actual_kwh": 30.84,
        "accuracy_percent": 77.1,
        "day_complete": True,
    }]
    _set_tracking(runtime, now, initial=39.47, latest=33.10, actual=31.10)

    attrs = sensor_module.solcast_accuracy_attrs(runtime)
    snapshot = runtime.build_ai_state_snapshot()

    assert attrs["realization_today_pct"] == 94.0
    assert attrs["historical_accuracy_pct"] == 77.1
    assert attrs["forecast_progress_percent"] == attrs["realization_today_pct"]
    assert attrs["historical_accuracy_percent"] == attrs["historical_accuracy_pct"]
    assert snapshot["solcast_current_day"]["realization_today_pct"] == 94.0
    assert snapshot["solcast_current_day"]["historical_accuracy_pct"] == 77.1


def test_t6_history_uses_the_same_canonical_current_day_value(monkeypatch):
    now = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    _set_tracking(runtime, now, initial=39.47, latest=33.10, actual=31.10)

    metrics = runtime.solcast_current_day_metrics()
    row = next(item for item in runtime.history_daily_summary() if item["date"] == "2026-08-29")

    assert row["realization_today_pct"] == metrics["realization_today_pct"] == 94.0
    assert row["forecast_progress_percent"] == metrics["realization_today_pct"]
    card_source = CARD.read_text(encoding="utf-8")
    assert "solcastAccuracyAttrs.realization_today_pct" in card_source
    assert "item.realization_today_pct ?? item.forecast_progress_percent" in card_source


def test_t7_core_input_contains_kwh_forecasts_and_historical_accuracy_only(monkeypatch):
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    runtime.hass.config = SimpleNamespace(time_zone="Europe/Warsaw")
    _set_solcast_states(runtime, today=33.10, actual=31.10, remaining=0.13, tomorrow=50.08)
    base_learning = runtime.learning_summary()
    runtime.learning_summary = lambda: {
        **base_learning,
        "solcast_accuracy_avg": 77.1,
        "solcast_correction_factor": 0.97,
    }

    payload = runtime._prepare_ai_plan_48h()["payload"]

    assert payload["pv_forecast"] == [0.13, 50.08]
    assert payload["pv_forecast_full"] == [33.10, 50.08]
    assert payload["pv_forecast_available"] == [True, True]
    assert payload["forecast_accuracy"] == 77.1
    assert payload["forecast_correction"] == 0.97
    assert len(payload["pv_profile"]) == 24
    assert "realization_today_pct" not in payload


def test_t8_external_ai_receives_hourly_forecast_not_ambiguous_accuracy():
    plan = {
        "plan_id": "plan-1",
        "input_snapshot_id": "snapshot-1",
        "algorithm_version": "test",
        "plan_schema_version": 1,
        "rows": [{
            "hour_start": "2026-08-29T12:00:00+02:00",
            "duration_minutes": 60,
            "action": "normal",
            "pv_corrected_kwh": 1.25,
            "forecast_low_kwh": 1.0,
            "forecast_high_kwh": 1.5,
            "confidence": 77.1,
        }],
    }

    payload = manager.build_private_payload(plan, {"current_soc_pct": 50})
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["role"] == "advisory_only"
    assert payload["local_plan"]["hours"][0]["pv_kwh"] == 1.25
    assert payload["local_plan"]["hours"][0]["forecast_low_kwh"] == 1.0
    assert payload["local_plan"]["hours"][0]["forecast_high_kwh"] == 1.5
    for aggregate in (
        "forecast_today_kwh",
        "production_today_kwh",
        "remaining_forecast_kwh",
        "realization_today_pct",
        "historical_accuracy_pct",
        '"accuracy"',
    ):
        assert aggregate not in encoded


def test_t9_no_independent_legacy_formula_remains_in_sensor_or_card():
    sensor_source = (ROOT / "custom_components" / "deye_energy_manager" / "sensor.py").read_text(encoding="utf-8")
    card_source = CARD.read_text(encoding="utf-8")

    assert 'tracking.get("forecast")' not in sensor_source
    assert "min(100, actual / forecast * 100)" not in sensor_source
    assert "dailyPvValue - solcastForecastValue" not in card_source
    assert "solcastAccuracyAttrs.forecast_progress_percent" not in card_source


def test_t10_midnight_rollover_keeps_issue_8_initial_forecast_history(monkeypatch):
    now = datetime(2026, 8, 30, 0, 15, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    runtime.solcast_tracking = {
        "date": "2026-08-29",
        "forecast": 39.47,
        "initial_forecast_kwh": 39.47,
        "latest_forecast_kwh": 33.10,
        "forecast_snapshots": [],
        "actual": 31.10,
    }
    _set_solcast_states(runtime, today=50.08, actual=0.0, remaining=50.08, tomorrow=20.0)

    asyncio.run(runtime.async_update_solcast_history())

    completed = runtime.solcast_history[0]
    assert completed["date"] == "2026-08-29"
    assert completed["forecast_kwh"] == 39.47
    assert completed["initial_forecast_kwh"] == 39.47
    assert completed["latest_forecast_kwh"] == 33.10
    assert completed["day_complete"] is True
    assert runtime.solcast_tracking["date"] == "2026-08-30"


def test_t11_remaining_forecast_is_not_the_full_day_denominator(monkeypatch):
    now = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)
    monkeypatch.setattr(manager, "ha_now", lambda: now)
    runtime = make_runtime()
    _set_solcast_states(runtime, today=33.10, actual=31.10, remaining=0.13, tomorrow=50.08)

    asyncio.run(runtime.async_update_solcast_history())
    metrics = runtime.solcast_current_day_metrics()

    assert metrics["forecast_today_kwh"] == 33.10
    assert metrics["remaining_forecast_kwh"] == 0.13
    assert metrics["realization_today_pct"] == 94.0


def test_t12_dst_fallback_keeps_the_same_local_day(monkeypatch):
    warsaw = ZoneInfo("Europe/Warsaw")
    first_0230 = datetime(2026, 10, 25, 0, 30, tzinfo=UTC).astimezone(warsaw)
    second_0230 = datetime(2026, 10, 25, 1, 30, tzinfo=UTC).astimezone(warsaw)
    runtime = make_runtime()

    monkeypatch.setattr(manager, "ha_now", lambda: first_0230)
    _set_tracking(runtime, first_0230, initial=30, latest=30, actual=15)
    first = runtime.solcast_current_day_metrics()

    runtime.solcast_tracking["updated_at"] = second_0230.isoformat()
    monkeypatch.setattr(manager, "ha_now", lambda: second_0230)
    second = runtime.solcast_current_day_metrics()

    assert first_0230.fold == 0 and second_0230.fold == 1
    assert first["local_day"] == second["local_day"] == "2026-10-25"
    assert first["realization_today_pct"] == second["realization_today_pct"] == 50.0

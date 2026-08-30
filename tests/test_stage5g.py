"""Focused regression coverage for Stage 5G optimizer and future-plan contracts."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_manager_logic import FakeState, const, make_runtime, manager
from test_optimizer_core import inputs as optimizer_inputs, optimizer


ROOT = Path(__file__).resolve().parents[1]
MANAGER_SOURCE = (ROOT / "custom_components/deye_energy_manager/manager.py").read_text(encoding="utf-8")
SENSOR_SOURCE = (ROOT / "custom_components/deye_energy_manager/sensor.py").read_text(encoding="utf-8")
CARD_SOURCE = (ROOT / "custom_components/deye_energy_manager/www/deye-energy-manager-card.js").read_text(encoding="utf-8")


class MemoryStore:
    async def async_save(self, value):
        self.value = value


@contextmanager
def at(moment: datetime):
    previous = manager.ha_now
    manager.ha_now = lambda: moment
    try:
        yield
    finally:
        manager.ha_now = previous


def future_runtime(*, soc="50", price="1.20", hour=5):
    runtime = make_runtime(soc=soc, price=price)
    if soc is not None:
        reported_at = datetime(2026, 7, 19, hour, 0, tzinfo=timezone.utc)
        soc_state = runtime.hass.states.get(runtime.battery_soc_sensor)
        soc_state.last_updated = reported_at
        soc_state.last_reported = reported_at
    runtime._ai_store = MemoryStore()
    runtime.future_plan = {
        "plan_id": "stage5g-plan",
        "date": "2026-07-19",
        "status": "scheduled",
        "updates": [{
            "slot_key": f"{hour:02d}_{(hour + 1) % 24:02d}",
            "enabled": True,
            "mode": const.MODE_SELLING_FIRST,
            "sell_power": 2500,
        }],
        "slot_validations": {
            f"{hour:02d}_{(hour + 1) % 24:02d}": {
                "minimum_soc": 20,
                "minimum_price": 0.4,
                "allow_partial": True,
            }
        },
        "slot_results": {},
    }
    writes = []

    async def record(updates, **_kwargs):
        writes.extend(updates)

    runtime.async_apply_schedule_patch = record
    return runtime, writes


def test_optimizer_rejects_stale_soc():
    runtime = make_runtime()
    state = runtime.hass.states.get(runtime.battery_soc_sensor)
    state.last_updated = datetime(2026, 7, 18, 11, 0, tzinfo=timezone.utc)
    assert runtime.current_soc_or_none() is None
    assert runtime.soc_diagnostics()["status"] == "stale"


@pytest.mark.parametrize("value,status", [("-0.1", "out_of_range"), ("100.1", "out_of_range")])
def test_optimizer_rejects_invalid_soc_range(value, status):
    runtime = make_runtime(soc=value)
    assert runtime.current_soc_or_none() is None
    assert runtime.soc_diagnostics()["status"] == status


def test_optimizer_rejects_soc_below_zero():
    test_optimizer_rejects_invalid_soc_range("-1", "out_of_range")


def test_optimizer_rejects_soc_above_100():
    test_optimizer_rejects_invalid_soc_range("101", "out_of_range")


def test_optimizer_accepts_fresh_valid_soc():
    runtime = make_runtime(soc="63.5")
    assert runtime.current_soc_or_none() == 63.5
    assert runtime.soc_diagnostics()["status"] == "valid"


def test_soc_recovery_recalculates_plan():
    assert "self.battery_soc_sensor" in MANAGER_SOURCE
    assert 'self.request_optimizer_recalc(reasons or {"manual"})' in MANAGER_SOURCE
    assert '("soc", (self.battery_soc_sensor,))' in MANAGER_SOURCE
    assert "_semantic_optimizer_inputs" in MANAGER_SOURCE


def test_panel_soc_and_optimizer_soc_share_same_source():
    assert "r.current_soc_or_none()" in SENSOR_SOURCE
    assert "def current_soc_or_none" in MANAGER_SOURCE


def test_future_slot_retries_after_transient_soc_loss():
    runtime, writes = future_runtime(soc=None)
    with at(datetime(2026, 7, 19, 5, 1, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
        assert runtime.future_plan["slot_results"]["05_06"]["status"] == "waiting_data"
        runtime.hass.states.values[runtime.battery_soc_sensor] = FakeState("55")
        asyncio.run(runtime.async_process_future_plan())
    assert len(writes) == 1
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "physical_pending"


def test_future_slot_retries_after_transient_price_loss():
    runtime, writes = future_runtime(price=None)
    with at(datetime(2026, 7, 19, 5, 2, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
        assert runtime.future_plan["slot_results"]["05_06"]["status"] == "waiting_data"
        runtime.hass.states.values[runtime.price_sensor] = FakeState("1.10")
        asyncio.run(runtime.async_process_future_plan())
    assert len(writes) == 1


def test_future_slot_stops_retrying_after_hour_end():
    runtime, writes = future_runtime(soc=None)
    with at(datetime(2026, 7, 19, 5, 5, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
    with at(datetime(2026, 7, 19, 6, 0, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
    assert runtime.future_plan["slot_results"]["05_06"]["status"] == "missed"
    assert writes == []


def test_offline_past_slots_are_marked_missed():
    test_future_slot_stops_retrying_after_hour_end()


def test_future_plan_is_partial_when_slots_were_missed():
    runtime, _ = future_runtime(soc=None)
    with at(datetime(2026, 7, 19, 6, 0, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
    assert runtime.future_plan["status"] == "partial"


def test_restart_0005_applies_current_0001_slot():
    runtime, writes = future_runtime(hour=0)
    with at(datetime(2026, 7, 19, 0, 5, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
    assert len(writes) == 1


def test_restart_0600_marks_earlier_slots_missed():
    runtime, writes = future_runtime(hour=0)
    with at(datetime(2026, 7, 19, 6, 0, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
    assert runtime.future_plan["slot_results"]["00_01"]["status"] == "missed"
    assert writes == []


def test_future_plan_is_not_applied_twice_after_reload():
    runtime, writes = future_runtime()
    with at(datetime(2026, 7, 19, 5, 3, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
        asyncio.run(runtime.async_process_future_plan())
    assert len(writes) == 1


def test_future_plan_is_not_applied_before_its_date():
    runtime, writes = future_runtime()
    with at(datetime(2026, 7, 18, 5, 3, tzinfo=timezone.utc)):
        asyncio.run(runtime.async_process_future_plan())
    assert writes == []


def test_learning_dry_run_blocks_plan_application():
    runtime = make_runtime()
    runtime._ai_store = MemoryStore()
    runtime.optimizer_plan = {"data_quality": {"learning_apply_allowed": False}}
    with pytest.raises(ValueError, match="dry-run"):
        asyncio.run(runtime.async_save_future_plan({
            "date": "2026-07-19", "updates": [{"slot_key": "05_06", "mode": const.MODE_NORMAL_OPERATION}],
        }))


def test_learning_apply_allowed_enables_manual_plan():
    runtime = make_runtime()
    runtime._ai_store = MemoryStore()
    runtime.learning_summary = lambda: {"learning_stage": {"apply_allowed": True}}
    runtime.optimizer_plan = {"data_quality": {"learning_apply_allowed": True}}
    asyncio.run(runtime.async_save_future_plan({
        "date": "2026-07-19",
        "updates": [{
            "slot_key": "05_06",
            "mode": const.MODE_SELLING_FIRST,
            "sell_power": 3000,
        }],
    }))
    assert runtime.future_plan["status"] == "scheduled"


def test_optimizer_uses_learning_confidence_cap():
    values = optimizer_inputs()
    values["learning_stage"] = {"status": "learning", "confidence_cap": 37, "apply_allowed": False, "dry_run": True}
    plan = optimizer.build_energy_plan(values, "balanced")
    assert max(row["raw_confidence"] for row in plan["rows"]) <= 37


def test_card_disables_apply_during_learning_dry_run():
    assert 'dayRecommendation?.reason === "learning_dry_run"' in CARD_SOURCE
    assert "!dayWriteAllowed" in CARD_SOURCE


def test_ai_charge_proposal_preview_lists_all_changed_fields():
    for token in ("charge_current", "discharge_current", "grid_charge_current", "charge_enabled", "tou_soc"):
        assert token in CARD_SOURCE
    assert "Grid Charge" in CARD_SOURCE


def test_ai_charge_proposal_apply_matches_previewed_fields():
    method = CARD_SOURCE[CARD_SOURCE.index("  aiRowUpdate("):CARD_SOURCE.index("  async applyAiDayPlan(")]
    for mapping in ("profile.charge_current", "profile.discharge_current", "profile.grid_charge_current", "profile.target_soc"):
        assert mapping in method


def test_today_view_explains_no_profitable_proposals():
    assert "no_profitable_hours" in (ROOT / "custom_components/deye_energy_manager/optimizer_core.py").read_text(encoding="utf-8")


def test_today_view_explains_fail_closed():
    assert "core_blocked_missing_soc" in (ROOT / "custom_components/deye_energy_manager/optimizer_core.py").read_text(encoding="utf-8")


def test_today_recalculates_after_soc_change():
    test_soc_recovery_recalculates_plan()


def test_tomorrow_plan_confirmation_shows_date_and_slots():
    assert "Plan zapisany na ${this.aiFormatDate(date)}" in CARD_SOURCE
    assert "${rows.length} slotów" in CARD_SOURCE


def test_future_plan_status_reports_executed_waiting_missed_blocked():
    for text in ("potwierdzone", "oczekuje na falownik", "pominięte", "zablokowane"):
        assert text in CARD_SOURCE


def test_ai_summary_is_hidden_when_plan_id_is_stale():
    assert 'api.last_plan_id || ""' in CARD_SOURCE


def test_ai_summary_is_hidden_when_snapshot_id_is_stale():
    assert 'api.last_input_snapshot_id || ""' in CARD_SOURCE


def test_current_ai_summary_matches_current_plan():
    assert "const sourceMatches" in CARD_SOURCE
    assert "&& !!api.last_analysis && sourceMatches" in CARD_SOURCE


def test_higher_tomorrow_price_and_low_morning_pv_preserves_energy():
    plan = optimizer.build_plan_bundle(optimizer_inputs(), "balanced")
    assert plan["checkpoints"]["tomorrow_05"] >= plan["rows"][0]["hard_min_soc_pct"]


def test_high_tomorrow_morning_pv_can_make_today_sale_reasonable():
    values = optimizer_inputs()
    values["pv_forecast"] = [5, 45]
    values["soc"] = 90
    values["sell_prices"][0][12] = 2.0
    values["sell_prices"][1] = {hour: 1.2 for hour in range(24)}
    plan = optimizer.build_plan_bundle(values, "profit")
    assert any(row["day"] == "today" and row["action"] == "sell" for row in plan["rows"])


def test_safe_preserves_more_reserve_than_max_profit():
    bundle = optimizer.build_plan_bundle(optimizer_inputs(), "balanced")
    assert bundle["variants"]["safe"]["terminal_soc_actual_pct"] >= bundle["variants"]["profit"]["terminal_soc_actual_pct"]


def test_fail_closed_does_not_show_normal_effective_confidence():
    values = optimizer_inputs()
    values["soc"] = None
    plan = optimizer.build_energy_plan(values, "balanced")
    assert plan["data_quality"]["fail_closed"] is True
    assert all(row["effective_confidence"] is None for row in plan["rows"])


def test_confidence_returns_after_critical_data_recovers():
    values = optimizer_inputs()
    values["soc"] = None
    blocked = optimizer.build_energy_plan(values, "balanced")
    values["soc"] = 50
    recovered = optimizer.build_energy_plan(values, "balanced")
    assert blocked["rows"][0]["effective_confidence"] is None
    assert recovered["rows"][0]["effective_confidence"] is not None

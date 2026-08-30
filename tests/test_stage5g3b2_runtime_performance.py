"""Stage 5G.3B.2 behavior-preserving runtime performance regressions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from test_manager_logic import manager
from test_stage5g1_lifecycle import task_runtime

from custom_components.deye_energy_manager.history import (
    ENERGY_COMPACT_FORMAT_VERSION,
    migrate_energy_payload,
)


def _raw_energy_sample(index: int) -> dict:
    return {
        "schema_version": 4,
        "timestamp": f"2026-08-10T12:{index % 60:02d}:00+00:00",
        "interval_seconds": 60,
        "pv_power": 1000 + index,
        "load_power": 500,
        "grid_power": -250,
        "battery_power": 250,
        "soc": 50,
        "sell_price": 0.5,
        "buy_price": 0.7,
        "readings": {"pv": {"value": 1000 + index, "status": "ok"}},
        "source_quality": {"score": 100},
        "weather": {"condition": "sunny"},
    }


def test_energy_migration_compacts_archive_and_preserves_public_recent_details():
    raw = {
        "schema_version": 4,
        "samples": [_raw_energy_sample(index) for index in range(400)],
        "daily": [{"date": "2026-08-09", "pv_kwh": 10}],
        "monthly": [{"month": "2026-08", "pv_kwh": 10}],
        "counter_state": {"daily_pv": {"value_kwh": 10}},
        "last_sample": "2026-08-10T12:39:00+00:00",
    }

    migrated, changed = migrate_energy_payload(raw)
    again, changed_again = migrate_energy_payload(migrated)

    assert changed is True
    assert changed_again is False
    assert migrated == again
    assert migrated["energy_format_version"] == ENERGY_COMPACT_FORMAT_VERSION
    assert len(migrated["samples"]) == 400
    assert len(migrated["recent_details"]) == 288
    assert "readings" not in migrated["samples"][0]
    assert migrated["recent_details"] == raw["samples"][-288:]
    assert migrated["daily"] == raw["daily"]
    assert migrated["monthly"] == raw["monthly"]
    assert migrated["counter_state"] == raw["counter_state"]


def test_energy_store_singleflight_latest_revision_wins_and_releases_legacy_backup():
    async def scenario():
        runtime = task_runtime()
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        class Store:
            def __init__(self):
                self.payloads = []

            async def async_save(self, payload):
                self.payloads.append(payload)
                if len(self.payloads) == 1:
                    first_started.set()
                    await release_first.wait()

        store = Store()
        runtime._samples_store = store
        runtime._energy_legacy_payload_backup = {"samples": [_raw_energy_sample(0)]}
        runtime.energy_samples = [{"timestamp": "one", "pv_power": 1}]
        runtime._energy_revision = 1
        first = runtime.request_energy_save()
        await first_started.wait()

        runtime.energy_samples.append({"timestamp": "two", "pv_power": 2})
        runtime._energy_revision = 2
        runtime.request_energy_save()
        release_first.set()
        await first

        assert len(store.payloads) == 2
        assert store.payloads[0]["samples"] == [{"timestamp": "one", "pv_power": 1}]
        assert store.payloads[1]["samples"][-1]["timestamp"] == "two"
        assert runtime._energy_saved_revision == 2
        assert runtime._energy_legacy_payload_backup is None

    asyncio.run(scenario())


def test_core_apply_marks_derived_state_dirty_without_starting_store_tasks():
    runtime = task_runtime()
    runtime.optimizer_plan = {
        "plan_id": "old",
        "algorithm_version": manager.ALGORITHM_VERSION,
        "plan_schema_version": manager.PLAN_SCHEMA_VERSION,
        "rows": [{"date": "2026-08-10", "hour": 12}],
    }
    runtime._ai_store = object()
    runtime._learning_store = object()
    runtime._sync_profile_execution_from_plan = lambda *_args: None
    runtime._sync_plan_execution_archive = lambda *_args: False
    prepared = {
        "current": datetime(2026, 8, 10, 12, tzinfo=UTC),
        "battery_model": {},
        "snapshot_id": "snapshot",
    }
    result = {
        "plan_id": "new",
        "algorithm_version": manager.ALGORITHM_VERSION,
        "plan_schema_version": manager.PLAN_SCHEMA_VERSION,
        "rows": [],
    }

    runtime._apply_prepared_ai_plan(prepared, result)

    assert runtime._ai_save_dirty is True
    assert runtime._learning_save_dirty is True
    assert runtime._ai_save_task is None
    assert runtime._learning_save_task is None
    assert runtime.optimizer_plan_history == [{
        "plan_id": "old",
        "algorithm_version": manager.ALGORITHM_VERSION,
        "plan_schema_version": manager.PLAN_SCHEMA_VERSION,
        "superseded_by_plan_id": "new",
        "data_quality": {},
    }]
    assert "rows" not in runtime.optimizer_plan_history[0]


def test_old_ai_store_migrates_full_plan_history_to_compact_records():
    async def scenario():
        full_plan = {
            "plan_id": "old-plan",
            "algorithm_version": manager.ALGORITHM_VERSION,
            "plan_schema_version": manager.PLAN_SCHEMA_VERSION,
            "rows": [{"hour": hour, "action": "none"} for hour in range(48)],
            "baseline": {"rows": [{"hour": hour} for hour in range(48)]},
        }
        raw = {
            "schema_version": 4,
            "settings": {},
            "history": [],
            "optimizer_plan": full_plan,
            "optimizer_plan_history": [full_plan],
        }

        class Store:
            def __init__(self):
                self.saved = []

            async def async_load(self):
                return raw

            async def async_save(self, payload):
                self.saved.append(payload)

        store = Store()
        original = manager.Store
        manager.Store = lambda *_args, **_kwargs: store
        try:
            runtime = task_runtime()
            await runtime.async_load_ai_data()
        finally:
            manager.Store = original

        assert len(runtime.optimizer_plan["rows"]) == 48
        assert runtime.optimizer_plan_history[0]["plan_id"] == "old-plan"
        assert "rows" not in runtime.optimizer_plan_history[0]
        assert store.saved
        assert "rows" not in store.saved[-1]["optimizer_plan_history"][0]

    asyncio.run(scenario())


def test_repeated_full_publish_skips_unchanged_public_state_but_granular_forces_it():
    runtime = task_runtime()
    runtime.request_sensor_snapshot_refresh = lambda *_args, **_kwargs: None

    class Entity:
        hass = object()
        available = True
        extra_state_attributes = {"stable": True}

        def __init__(self):
            self._deye_manager_key = "manager_status"
            self._value = "idle"
            self.writes = 0

        @property
        def native_value(self):
            return self._value

        def async_write_ha_state(self):
            self.writes += 1

    entity = Entity()
    runtime.entities = [entity]
    runtime.notify_update()
    runtime.notify_update()
    assert entity.writes == 1

    entity._value = "changed"
    runtime.notify_update()
    assert entity.writes == 2

    runtime._notify_entities_from_cache({"manager_status"})
    assert entity.writes == 3


def test_external_ai_daily_attempt_limit_persists_and_retry_counts_as_attempt():
    async def scenario():
        runtime = task_runtime()
        now = manager.ha_now()
        runtime.ai_api_limit_state = {
            "date": now.date().isoformat(),
            "count": 7,
            "last_request_at": None,
            "last_success_at": None,
            "last_input_fingerprint": None,
        }
        runtime._ai_store = None

        await runtime._record_ai_api_attempt(0)
        try:
            await runtime._record_ai_api_attempt(1)
        except manager.ExternalAIDailyLimitError:
            pass
        else:
            raise AssertionError("retry above the eighth actual attempt was not blocked")

        assert runtime.ai_api_limit_state["count"] == 8
        assert runtime.ai_api_metrics["executed"] == 1
        assert runtime.ai_api_metrics["retry"] == 0
        assert runtime._ai_store_payload()["ai_api_limit"]["count"] == 8

    asyncio.run(scenario())


def test_external_ai_24h_scheduler_never_creates_more_than_eight_requests():
    async def scenario():
        runtime = task_runtime()
        runtime.ai_api_config = {"enabled": True}
        runtime._ai_store = None
        base = manager.ha_now().replace(hour=0, minute=0, second=0, microsecond=0)
        runtime.ai_api_limit_state = {
            "date": base.date().isoformat(),
            "count": 0,
            "last_request_at": None,
            "last_success_at": None,
            "last_input_fingerprint": None,
        }
        original_now = manager.ha_now

        async def fake_run(**_kwargs):
            await runtime._record_ai_api_attempt(0)
            fingerprint = manager.material_review_fingerprint(runtime.optimizer_plan)
            runtime.ai_api_limit_state["last_success_at"] = manager.ha_now().isoformat(
                timespec="seconds"
            )
            runtime.ai_api_limit_state["last_input_fingerprint"] = fingerprint
            return {"status": "ok"}

        runtime.async_run_ai_api = fake_run
        try:
            for minute in range(24 * 60):
                current = base + timedelta(minutes=minute)
                manager.ha_now = lambda current=current: current
                semantic_window = minute // 120
                runtime.optimizer_plan = {
                    "rows": [{
                        "action": "sell",
                        "planned_power_w": 500 + semantic_window * 250,
                        "soc_end_pct": 50,
                    }],
                    "data_quality": {"fail_closed": False},
                }
                runtime.schedule_ai_api_analysis()
                if runtime._ai_api_task is not None and not runtime._ai_api_task.done():
                    await runtime._ai_api_task
        finally:
            manager.ha_now = original_now

        assert runtime.ai_api_limit_state["count"] == 8
        assert runtime.ai_api_metrics["executed"] == 8
        assert len(runtime.hass.created_tasks) == 8
        assert runtime.ai_api_metrics["skipped_daily_limit"] > 0

    asyncio.run(scenario())


def test_external_ai_auto_cooldown_blocks_task_but_manual_bypasses_cooldown():
    async def scenario():
        runtime = task_runtime()
        now = manager.ha_now()
        runtime.ai_api_config = {"enabled": True}
        runtime.optimizer_plan = {"rows": [], "data_quality": {"fail_closed": False}}
        runtime.ai_api_limit_state = {
            "date": now.date().isoformat(),
            "count": 1,
            "last_request_at": now.isoformat(timespec="seconds"),
            "last_success_at": None,
            "last_input_fingerprint": None,
        }
        calls = []

        async def fake_run(**kwargs):
            calls.append(kwargs)
            return {"status": "ok"}

        runtime.async_run_ai_api = fake_run
        runtime.schedule_ai_api_analysis()
        assert runtime.hass.created_tasks == []
        assert runtime.ai_api_metrics["skipped_cooldown"] == 1

        runtime.schedule_ai_api_analysis(force=True)
        await runtime._ai_api_task
        assert calls == [{"force": True}]

    asyncio.run(scenario())

"""Stage 5G.4B SAFE regressions for Core policy and deployment contracts."""

from __future__ import annotations

from copy import deepcopy
import asyncio

import pytest

from test_ai_assistant import assistant, plan as ai_plan
from test_manager_logic import make_runtime, manager as manager_module
from test_optimizer_core import inputs as optimizer_inputs, optimizer


def _flat_market() -> dict:
    values = optimizer_inputs()
    values.update({
        "current_hour": 0,
        "current_hour_remaining_minutes": 60,
        "battery_capacity_kwh": 10,
        "charge_efficiency": 0.95,
        "discharge_efficiency": 0.95,
        "battery_efficiency": 0.9025,
        "min_soc": 20,
        "effective_min_soc": 20,
        "target_soc": 100,
        "effective_power_limit_w": 3000,
        "battery_charge_limit_w": 3000,
        "battery_discharge_limit_w": 3000,
        "grid_import_limit_w": 3000,
        "grid_export_limit_w": 3000,
        "inverter_ac_limit_w": 3000,
        "charge_kwh_per_hour": 3,
        "price_includes_distribution": True,
        "distribution": [0.0] * 48,
        "pv_forecast": [0, 0],
        "pv_forecast_full": [0, 0],
        "pv_profile": [0.0] * 24,
        "load_profile_48h": [0.2] * 48,
        "load_profile_sources_48h": [
            {"source": "weekday_hour", "samples": 10} for _ in range(48)
        ],
        "sell_prices": [{hour: 0.2 for hour in range(24)} for _ in range(2)],
        "buy_prices": [{hour: 0.8 for hour in range(24)} for _ in range(2)],
        "baseline_schedule": [
            {
                "enabled": False,
                "mode": "Normal Operation",
                "sell_power_w": 0,
                "charge_enabled": False,
                "charge_power_w": 0,
                "charge_current_a": 0,
                "grid_charge_current_a": 0,
                "discharge_current_a": 0,
                "tou_soc": 15,
                "minimum_sell_soc": 20,
            }
            for _ in range(48)
        ],
    })
    return values


def _sale_profile(*, start: str, end: str, priority: str, target: float) -> dict:
    return {
        "enabled": True,
        "type": "sale",
        "active_days": ["2"],
        "start": start,
        "end": end,
        "priority": priority,
        "goal_character": "preferred",
        "allow_partial": True,
        "minimum_confidence": 0,
        "target_energy_kwh": target,
        "target_basis": "battery_to_grid",
        "min_price": 0,
        "preferred_power_w": 3000,
        "distribution_method": "best_hours",
        "min_soc_after": 20,
        "allow_earlier_grid_charge": False,
        "min_net_result": 0,
    }


def test_joint_terminal_optimization_keeps_profitable_charge_and_later_sale():
    values = _flat_market()
    values["soc"] = 35
    values["buy_prices"][0][2] = -0.2
    values["buy_prices"][1][22] = -0.2
    values["sell_prices"][0][6] = 1.5

    plan = optimizer.build_plan_bundle(values, "balanced")

    assert any(row["action"] == "charge" and row["proposed"] for row in plan["rows"])
    assert plan["rows"][6]["action"] == "sell"
    assert plan["rows"][6]["proposed"]
    assert plan["terminal"]["terminal_soc_actual_pct"] + 0.01 >= 45
    assert not any(
        row["reason_code"] == "optimizer:profitable-charge-before-sale"
        and row["future_target_hour"] == 6
        for row in plan["rows"]
        if row["action"] == "charge" and not plan["rows"][6]["proposed"]
    )


def test_higher_priority_evening_profile_reserves_energy_from_morning_profile():
    values = _flat_market()
    # Just enough energy for the higher-priority 3 kWh evening target plus
    # the 20% reserve; there is no legitimate morning surplus to consume.
    values["soc"] = 51.6
    values["allow_grid_charge"] = False
    values["load_profile_48h"] = [0.0] * 48
    values["sell_prices"][0][6] = 1.0
    values["sell_prices"][0][18] = 1.2
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {
            "morning_sale": _sale_profile(
                start="06:00", end="09:00", priority="normal", target=3
            ),
            "evening_sale": _sale_profile(
                start="17:00", end="22:00", priority="high", target=3
            ),
        },
    }

    plan = optimizer.build_energy_plan(values, "balanced")
    morning = sum(
        row["battery_to_grid_kwh"]
        for row in plan["rows"]
        if row.get("profile_id") == "morning_sale"
    )
    evening = sum(
        row["battery_to_grid_kwh"]
        for row in plan["rows"]
        if row.get("profile_id") == "evening_sale"
    )

    assert morning == pytest.approx(0, abs=0.01)
    assert evening == pytest.approx(3, abs=0.01)


def test_cross_midnight_profile_uses_window_anchor_day():
    values = _flat_market()
    values["date"] = "2026-08-16"  # Sunday; after-midnight tail is Monday.
    values["soc"] = 30
    values["buy_prices"] = [{hour: 1.0 for hour in range(24)} for _ in range(2)]
    values["buy_prices"][1][1] = 0.1
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {
            "charging": {
                "enabled": True,
                "type": "charging",
                "active_days": ["6"],
                "start": "22:00",
                "end": "06:00",
                "priority": "high",
                "goal_character": "required",
                "allow_partial": True,
                "minimum_confidence": 0,
                "source": "grid",
                "target_type": "energy",
                "target_value": 1,
                "deadline": "06:00",
                "max_effective_price": 0.2,
                "preferred_power_w": 1000,
                "purpose": "reserve",
                "charge_missing_only": True,
                "use_corrected_pv": True,
                "preserve_pv_room": False,
                "minimum_free_room_kwh": 0,
                "profitable_only": False,
            }
        },
    }

    plan = optimizer.build_energy_plan(values, "balanced")

    assert plan["rows"][25]["profile_id"] == "charging"
    assert plan["rows"][25]["action"] == "charge"


@pytest.mark.parametrize(
    ("start_date", "active_day"),
    [
        ("2026-08-12", "wednesday"),
        ("2026-08-15", "sob"),
        ("2026-08-16", "6"),
    ],
)
def test_profile_day_selection_supports_workday_weekend_and_individual_day(
    start_date: str,
    active_day: str,
):
    values = _flat_market()
    values.update(date=start_date, soc=80)
    values["load_profile_48h"] = [0.0] * 48
    values["sell_prices"][0][6] = 2.0
    profile = _sale_profile(start="06:00", end="07:00", priority="high", target=1)
    profile["active_days"] = [active_day]
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {"morning_sale": profile},
    }

    plan = optimizer.build_energy_plan(values, "balanced")

    assert plan["rows"][6]["profile_id"] == "morning_sale"
    assert plan["rows"][6]["proposed"] is True


def test_missing_load_is_not_treated_as_aggressive_zero_for_sale():
    values = _flat_market()
    values["soc"] = 90
    values["sell_prices"][0][18] = 2.0
    values["load_profile_48h"] = [None] * 48
    values["load_profile_sources_48h"] = [
        {"source": "missing", "samples": 0} for _ in range(48)
    ]

    plan = optimizer.build_energy_plan(values, "balanced")

    assert not any(row["action"] == "sell" and row["proposed"] for row in plan["rows"])
    assert "safety:missing-load-forecast" in plan["rows"][18]["reason_codes"]


def test_core_action_contract_keeps_sell_guards_diagnostic_not_executable():
    values = _flat_market()
    values["soc"] = 80
    values["battery_voltage_v"] = 50
    values["effective_min_soc"] = 35
    values["sell_prices"][0][18] = 2.0

    row = optimizer.build_energy_plan(values, "balanced")["rows"][18]
    contract = row["action_contract"]
    update = contract["schedule_update"]

    assert contract["action"] == "sell"
    assert update["sell_power"] == pytest.approx(row["planned_power_w"])
    assert contract["minimum_sell_soc"] == pytest.approx(35)
    assert contract["tou_soc"] == pytest.approx(15)
    assert set(update) == {"slot_key", "enabled", "mode", "sell_power"}


def test_charge_action_contract_converts_final_power_to_current():
    values = _flat_market()
    values["soc"] = 30
    values["battery_voltage_v"] = 50
    values["buy_prices"][0][2] = 0.1
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {
            "charging": {
                "enabled": True,
                "type": "charging",
                "active_days": ["2"],
                "start": "02:00",
                "end": "03:00",
                "priority": "high",
                "goal_character": "required",
                "allow_partial": True,
                "minimum_confidence": 0,
                "source": "grid",
                "target_type": "soc",
                "target_value": 50,
                "deadline": "03:00",
                "max_effective_price": 0.2,
                "preferred_power_w": 1000,
                "purpose": "reserve",
                "charge_missing_only": True,
                "use_corrected_pv": True,
                "preserve_pv_room": False,
                "minimum_free_room_kwh": 0,
                "profitable_only": False,
            }
        },
    }

    row = optimizer.build_energy_plan(values, "balanced")["rows"][2]
    update = row["action_contract"]["schedule_update"]
    expected_current = row["planned_power_w"] / 50

    assert update["charge_current"] == pytest.approx(expected_current, abs=0.01)
    assert update["grid_charge_current"] == pytest.approx(expected_current, abs=0.01)
    assert update["tou_soc"] == pytest.approx(50)
    assert update["charge_enabled"] is True


def test_ai_fingerprint_tracks_material_profile_change_but_ignores_row_noise():
    local_plan = ai_plan()
    profiles = {"profiles": {"morning_sale": {"enabled": True, "min_price": 0.4}}}
    changed = deepcopy(profiles)
    changed["profiles"]["morning_sale"]["min_price"] = 0.6
    noisy = deepcopy(local_plan)
    noisy["rows"][0]["soc_end_pct"] += 0.4

    original = assistant.material_review_fingerprint(local_plan, user_profiles=profiles)
    assert original == assistant.material_review_fingerprint(noisy, user_profiles=profiles)
    assert original != assistant.material_review_fingerprint(local_plan, user_profiles=changed)


def test_ai_alternative_statuses_separate_schema_simulation_and_core_acceptance():
    accepted = optimizer.simulate_alternative(
        optimizer_inputs(),
        changes=[{"index": 20, "action": "sell", "power_w": 1000}],
    )

    assert accepted["schema_valid"] is True
    assert accepted["locally_simulated"] is True
    assert accepted["accepted_by_core"] is True
    assert accepted["locally_validated"] is True


def test_ai_alternative_outside_required_profile_window_is_rejected():
    values = _flat_market()
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {
            "morning_sale": {
                **_sale_profile(start="05:00", end="10:00", priority="high", target=1),
                "goal_character": "required",
            }
        },
    }

    with pytest.raises(ValueError, match="outside a required user profile window"):
        optimizer.simulate_alternative(
            values,
            changes=[{"index": 18, "action": "sell", "power_w": 1000}],
        )


def test_ai_alternative_that_breaks_reserve_is_simulated_but_not_accepted():
    values = _flat_market()
    values["soc"] = 21

    result = optimizer.simulate_alternative(
        values,
        changes=[{"index": 2, "action": "sell", "power_w": 3000}],
    )

    assert result["schema_valid"] is True
    assert result["locally_simulated"] is True
    assert result["accepted_by_core"] is False
    assert result["acceptance"][0]["actual_power_w"] == 0


def test_ai_unprofitable_charge_without_local_purpose_is_neutralized():
    values = _flat_market()
    values["soc"] = 30
    values["sell_prices"] = [{hour: 0.1 for hour in range(24)} for _ in range(2)]
    values["buy_prices"] = [{hour: 1.0 for hour in range(24)} for _ in range(2)]

    result = optimizer.simulate_alternative(
        values,
        changes=[{"index": 2, "action": "charge", "power_w": 1000}],
    )

    assert result["schema_valid"] is True
    assert result["locally_simulated"] is True
    assert result["accepted_by_core"] is False
    assert result["acceptance"][0]["actual_action"] != "charge"
    assert result["acceptance"][0]["reason_code"] == (
        "candidate:unprofitable-charge-without-local-purpose"
    )


def test_ai_response_cache_and_learning_checkpoint_are_bounded_persistent_state():
    runtime = make_runtime()
    runtime.ai_api_cache = {
        "at": "2026-08-13T12:00:00+02:00",
        "material_fingerprint": "abc",
        "analysis": {"summary": "ok"},
        "candidate": {"accepted_by_core": True},
    }
    runtime.learning_tracking = {
        "hour": "2026-08-13T12:00:00+0200",
        "last_sample": "2026-08-13T12:05:00+02:00",
        "samples": 5,
    }

    assert runtime._ai_store_payload()["ai_api_cache"] == runtime.ai_api_cache
    assert runtime._energy_store_payload()["learning_checkpoint"] == runtime.learning_tracking


def test_ai_cache_and_learning_checkpoint_survive_runtime_reload():
    class MemoryStore:
        def __init__(self, payload):
            self.payload = deepcopy(payload)

        async def async_load(self):
            return deepcopy(self.payload)

        async def async_save(self, payload):
            self.payload = deepcopy(payload)

    source = make_runtime()
    source.ai_api_cache = {
        "at": "2026-08-13T12:00:00+02:00",
        "material_fingerprint": "persistent-material",
        "analysis": {"summary": "cached review"},
        "candidate": {"accepted_by_core": True},
    }
    ai_store = MemoryStore(source._ai_store_payload())
    restored_ai = make_runtime()
    previous_store = manager_module.Store
    manager_module.Store = lambda *_args, **_kwargs: ai_store
    try:
        asyncio.run(restored_ai.async_load_ai_data())
    finally:
        manager_module.Store = previous_store
    assert restored_ai.ai_api_cache == source.ai_api_cache

    source.learning_tracking = {
        "hour": "2026-08-13T12:00:00+0200",
        "last_sample": "2026-08-13T12:14:00+02:00",
        "samples": 14,
    }
    energy_store = MemoryStore(source._energy_store_payload())
    restored_learning = make_runtime()
    restored_learning.learning_tracking = {
        "last_sample": "2026-08-13T12:00:00+02:00",
        "samples": 0,
    }
    manager_module.Store = lambda *_args, **_kwargs: energy_store
    try:
        asyncio.run(restored_learning.async_load_energy_history())
    finally:
        manager_module.Store = previous_store
    assert restored_learning.learning_tracking == source.learning_tracking


def test_core_schedule_update_reaches_manager_logical_target_one_to_one():
    values = _flat_market()
    values["soc"] = 80
    values["battery_voltage_v"] = 50
    values["effective_min_soc"] = 35
    values["sell_prices"][0][18] = 2.0
    row = optimizer.build_energy_plan(values, "balanced")["rows"][18]
    update = row["action_contract"]["schedule_update"]
    runtime = make_runtime()
    runtime.control_enabled = False

    normalized = runtime._validate_future_plan_updates([update])[0]
    asyncio.run(runtime.async_apply_schedule_patch([normalized]))
    slot = runtime.slots[update["slot_key"]]

    assert slot.sell_power == pytest.approx(update["sell_power"])
    assert "discharge_current" not in update
    assert "minimum_sell_soc" not in update
    assert "tou_soc" not in update


def test_charge_core_schedule_update_reaches_manager_logical_target_one_to_one():
    values = _flat_market()
    values.update(soc=30, battery_voltage_v=50)
    values["buy_prices"][0][2] = 0.1
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {
            "charging": {
                "enabled": True,
                "type": "charging",
                "active_days": ["2"],
                "start": "02:00",
                "end": "03:00",
                "priority": "high",
                "goal_character": "required",
                "allow_partial": True,
                "minimum_confidence": 0,
                "source": "grid",
                "target_type": "soc",
                "target_value": 50,
                "deadline": "03:00",
                "max_effective_price": 0.2,
                "preferred_power_w": 1000,
                "purpose": "reserve",
                "charge_missing_only": True,
                "use_corrected_pv": True,
                "preserve_pv_room": False,
                "minimum_free_room_kwh": 0,
                "profitable_only": False,
            }
        },
    }
    row = optimizer.build_energy_plan(values, "balanced")["rows"][2]
    update = row["action_contract"]["schedule_update"]
    runtime = make_runtime()
    runtime.control_enabled = False

    normalized = runtime._validate_future_plan_updates([update])[0]
    asyncio.run(runtime.async_apply_schedule_patch([normalized]))
    slot = runtime.slots[update["slot_key"]]

    assert slot.mode == update["mode"]
    assert slot.charge_current == pytest.approx(update["charge_current"])
    assert slot.grid_charge_current == pytest.approx(update["grid_charge_current"])
    assert slot.discharge_current == pytest.approx(update["discharge_current"])
    assert slot.tou_soc == pytest.approx(update["tou_soc"])
    assert slot.charge_enabled is True

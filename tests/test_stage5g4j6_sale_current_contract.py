"""Stage 5G.4J.6 regressions for the power-only Core Sell contract."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import pytest

from test_manager_logic import FakeState, const, make_runtime, manager, select_module
from test_stage5g4b_safe import _flat_market, _sale_profile, optimizer


TODAY = manager.ha_now().date().isoformat()


def _sell_contract(power_w: float, voltage_v: float = 52.0) -> dict:
    start = datetime(2026, 8, 21, 18, tzinfo=timezone.utc)
    return optimizer._core_action_contract(
        {
            "battery_voltage_v": voltage_v,
            "baseline_schedule": [
                {
                    "discharge_current_a": 120,
                    "charge_current_a": 80,
                    "grid_charge_current_a": 60,
                    "minimum_sell_soc": 20,
                    "tou_soc": 15,
                }
                for _ in range(48)
            ],
        },
        index=18,
        day=date(2026, 8, 21),
        hour_start=start,
        hour_end=start.replace(hour=19),
        action="sell",
        action_spec={"action": "sell", "profile_id": "evening_sale"},
        planned_energy_kwh=power_w / 1000,
        planned_power_w=power_w,
        effective_min_soc=20,
        target_soc=100,
        confidence=90,
        net_result=1.0,
        reason_code="profile",
        reason_summary="test",
        physical_limits={"battery_discharge_limit_w": 6240},
    )


@pytest.mark.parametrize(
    ("power_w", "expected_current"),
    [(4000, 4000 / 52), (130, 130 / 52)],
)
def test_sell_contract_keeps_current_diagnostic_only(power_w, expected_current):
    contract = _sell_contract(power_w)

    assert contract["schedule_update"] == {
        "slot_key": "18_19",
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": power_w,
    }
    assert contract["discharge_current"] is None
    assert contract["estimated_battery_current_a"] == pytest.approx(expected_current)
    assert "discharge_current" not in contract["schedule_update"]
    assert contract["conversion"]["basis"] == (
        "diagnostic_sell_power_divided_by_battery_voltage"
    )


def _apply_legacy_ai_sell(runtime, power_w: float, legacy_current: float) -> None:
    slot_key = runtime.active_slot_key()
    asyncio.run(
        runtime.async_apply_schedule_patch(
            [
                {
                    "slot_key": slot_key,
                    "enabled": True,
                    "mode": const.MODE_SELLING_FIRST,
                    "sell_power": power_w,
                    "discharge_current": legacy_current,
                    "charge_current": 2,
                    "grid_charge_current": 2,
                    "minimum_sell_soc": 99,
                    "tou_soc": 99,
                    "charge_enabled": True,
                }
            ],
            replace_day=True,
            date=TODAY,
        )
    )


@pytest.mark.parametrize(
    ("power_w", "legacy_current"),
    [(4000, 4000 / 52), (130, 130 / 52)],
)
def test_apply_today_sell_ignores_legacy_current_and_preserves_user_120a(
    power_w, legacy_current
):
    runtime = make_runtime()
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    active = runtime.active_slot
    active.discharge_current = 120
    old_minimum = active.minimum_sell_soc
    old_tou = active.tou_soc

    _apply_legacy_ai_sell(runtime, power_w, legacy_current)

    active = runtime.active_slot
    assert active.mode == const.MODE_SELLING_FIRST
    assert active.sell_power == power_w
    assert active.discharge_current == 120
    assert runtime.target_discharge_current == 120
    assert active.minimum_sell_soc == old_minimum
    assert active.tou_soc == old_tou
    assert active.charge_enabled is False
    assert active.ai_sell_power_only is True


def test_normal_sell_normal_cycle_keeps_user_current_stable():
    runtime = make_runtime()
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    runtime.active_slot.discharge_current = 120

    assert runtime.target_discharge_current == 120
    _apply_legacy_ai_sell(runtime, 4000, 4000 / 52)
    assert runtime.target_discharge_current == 120

    asyncio.run(
        runtime.async_apply_schedule_patch(
            [{"slot_key": runtime.active_slot_key(), "mode": const.MODE_NORMAL_OPERATION}]
        )
    )
    assert runtime.active_slot.ai_sell_power_only is False
    assert runtime.target_discharge_current == 120


def test_manual_sell_current_patch_remains_supported():
    runtime = make_runtime()
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    runtime.active_slot.discharge_current = 120
    _apply_legacy_ai_sell(runtime, 4000, 4000 / 52)

    asyncio.run(
        runtime.async_apply_schedule_patch(
            [
                {
                    "slot_key": runtime.active_slot_key(),
                    "mode": const.MODE_SELLING_FIRST,
                    "discharge_current": 90,
                }
            ]
        )
    )

    assert runtime.active_slot.ai_sell_power_only is False
    assert runtime.active_slot.discharge_current == 90
    assert runtime.target_discharge_current == 90


def test_legacy_tomorrow_sell_is_sanitized_and_deploys_as_power_only():
    runtime = make_runtime()
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    runtime.active_slot.discharge_current = 120
    legacy = {
        "slot_key": runtime.active_slot_key(),
        "enabled": True,
        "mode": const.MODE_SELLING_FIRST,
        "sell_power": 130,
        "discharge_current": 2.5,
        "charge_current": 2.5,
        "grid_charge_current": 2.5,
        "minimum_sell_soc": 99,
        "tou_soc": 99,
        "charge_enabled": True,
    }

    normalized = runtime._validate_future_plan_updates([legacy])
    assert normalized == [
        {
            "slot_key": runtime.active_slot_key(),
            "enabled": True,
            "mode": const.MODE_SELLING_FIRST,
            "sell_power": 130,
            "minimum_sell_soc": 99,
        }
    ]
    asyncio.run(runtime.async_apply_schedule_patch(normalized, ai_source=True))

    assert runtime.active_slot.ai_sell_power_only is True
    assert runtime.active_slot.discharge_current == 120
    assert runtime.target_discharge_current == 120


def test_user_current_times_voltage_remains_a_feasibility_input():
    values = _flat_market()
    values.update(
        soc=100,
        battery_voltage_v=52,
        battery_discharge_limit_w=60 * 52,
        effective_power_limit_w=10000,
        grid_export_limit_w=10000,
        inverter_ac_limit_w=10000,
    )
    values["load_profile_48h"] = [2.0] * 48
    values["sell_prices"][0][18] = 2.0
    profile = _sale_profile(start="18:00", end="19:00", priority="high", target=10)
    profile["preferred_power_w"] = 10000
    values["user_profiles"] = {
        "schema_version": 2,
        "profiles": {"evening_sale": profile},
    }

    row = optimizer.build_energy_plan(values, "balanced")["rows"][18]

    assert row["battery_to_home_kwh"] + row["battery_to_grid_kwh"] <= 3.12 + 1e-6
    assert row["planned_power_w"] <= 3120
    assert "discharge_current" not in row["action_contract"]["schedule_update"]


@pytest.mark.parametrize(
    "provider",
    [
        const.PROVIDER_LEWA_REKA,
        const.PROVIDER_SOLARMAN,
        const.PROVIDER_SUNSYNK,
        const.PROVIDER_CUSTOM,
    ],
)
def test_writable_providers_share_power_only_ai_sell_contract(provider):
    runtime = make_runtime()
    runtime.data[const.CONF_INVERTER_PROVIDER] = provider
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    runtime.active_slot.discharge_current = 120

    _apply_legacy_ai_sell(runtime, 4000, 4000 / 52)

    assert runtime.active_slot.ai_sell_power_only is True
    assert runtime.active_slot.sell_power == 4000
    assert runtime.target_discharge_current == 120


def test_read_only_provider_cannot_write_global_current():
    runtime = make_runtime()
    runtime.data[const.CONF_INVERTER_PROVIDER] = const.PROVIDER_DEYE_ADDON
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    runtime.active_slot.discharge_current = 120
    _apply_legacy_ai_sell(runtime, 4000, 4000 / 52)
    runtime.control_enabled = True
    runtime.control_status = "Aktywne"
    runtime.hass.services.calls.clear()

    assert asyncio.run(runtime.async_apply_targets()) is False
    assert not any(
        call[:2] == ("number", "set_value")
        and call[2].get("entity_id") == runtime.discharge_current_number
        for call in runtime.hass.services.calls
    )


def test_ai_sell_at_matching_120a_does_not_emit_global_current_write():
    runtime = make_runtime()
    runtime.normal_profile_discharge_current = 120
    runtime._normal_profile_loaded_from_store = True
    runtime.active_slot.discharge_current = 120
    _apply_legacy_ai_sell(runtime, 4000, 4000 / 52)
    runtime.control_enabled = True
    runtime.control_status = "Aktywne"
    runtime.hass.states.values[runtime.discharge_current_number] = FakeState("120")
    runtime.hass.states.values[runtime.charge_current_number] = FakeState("120")
    runtime.hass.states.values[runtime.grid_charge_current_number] = FakeState("60")
    runtime.hass.services.calls.clear()

    assert asyncio.run(runtime.async_apply_targets()) is True
    assert not any(
        call[:2] == ("number", "set_value")
        and call[2].get("entity_id") == runtime.discharge_current_number
        for call in runtime.hass.services.calls
    )


def test_ai_sell_power_only_marker_survives_slot_mode_restore():
    runtime = make_runtime()
    slot_key = runtime.active_slot_key()
    entity = select_module.DeyeSlotModeSelect(
        runtime,
        slot_key,
        runtime.slots[slot_key].label,
    )

    async def restored_state():
        return FakeState(
            const.MODE_SELLING_FIRST,
            {"ai_sell_power_only": True},
        )

    entity.async_get_last_state = restored_state
    asyncio.run(entity.async_added_to_hass())

    assert runtime.slots[slot_key].mode == const.MODE_SELLING_FIRST
    assert runtime.slots[slot_key].ai_sell_power_only is True
    assert entity.extra_state_attributes == {"ai_sell_power_only": True}

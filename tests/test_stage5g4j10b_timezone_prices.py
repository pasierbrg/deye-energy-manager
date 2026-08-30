from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from test_manager_logic import FakeState, make_runtime, manager
from test_stage5g4j10a_v2_best_hours import core, sale_case


WARSAW = ZoneInfo("Europe/Warsaw")


def set_now(monkeypatch: pytest.MonkeyPatch, value: datetime) -> None:
    monkeypatch.setattr(manager, "ha_now", lambda: value)


def add_prices(runtime, entity_id: str, rows: list[dict]) -> None:
    runtime.hass.states.values[entity_id] = FakeState(
        "unavailable",
        {"prices": rows},
        entity_id=entity_id,
    )


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-08-24T18:00:00Z",
        "2026-08-24T18:00:00+00:00",
        "2026-08-24T20:00:00+02:00",
    ],
)
def test_aware_iso_is_converted_before_local_date_and_hour(monkeypatch, stamp):
    set_now(monkeypatch, datetime(2026, 8, 24, 12, tzinfo=WARSAW))
    runtime = make_runtime()

    local_date, hour = runtime._price_slot_from_value(stamp)

    assert local_date.isoformat() == "2026-08-24"
    assert hour == 20


def test_utc_crossing_midnight_moves_entry_to_tomorrow(monkeypatch):
    current = datetime(2026, 8, 24, 12, tzinfo=WARSAW)
    set_now(monkeypatch, current)
    runtime = make_runtime()
    entity = "sensor.utc_crossing_prices"
    add_prices(runtime, entity, [{"datetime": "2026-08-24T23:00:00Z", "price": 1.23}])

    today, tomorrow = runtime.price_maps(entity, None, current=current)

    assert today == {}
    assert tomorrow == {1: 1.23}


def test_aware_timestamp_can_map_to_previous_local_date(monkeypatch):
    new_york = ZoneInfo("America/New_York")
    set_now(monkeypatch, datetime(2026, 8, 24, 12, tzinfo=new_york))
    runtime = make_runtime()

    local_date, hour = runtime._price_slot_from_value("2026-08-24T02:00:00Z")

    assert local_date.isoformat() == "2026-08-23"
    assert hour == 22


def test_naive_iso_and_plain_hour_labels_keep_local_semantics(monkeypatch):
    set_now(monkeypatch, datetime(2026, 8, 24, 12, tzinfo=WARSAW))
    runtime = make_runtime()

    assert runtime._price_slot_from_value("2026-08-24T18:00:00") == (
        datetime(2026, 8, 24).date(),
        18,
    )
    assert runtime._price_slot_from_value("01:00") == (None, 1)
    assert runtime._price_slot_from_value("1:00") == (None, 1)
    assert runtime._price_slot_from_value("01") == (None, 1)


def test_zero_negative_and_duplicate_local_hour_preserve_first_value(monkeypatch):
    current = datetime(2026, 10, 25, 12, tzinfo=WARSAW)
    set_now(monkeypatch, current)
    runtime = make_runtime()
    entity = "sensor.fall_prices"
    add_prices(runtime, entity, [
        {"datetime": "2026-10-25T00:00:00Z", "price": 0.0},
        {"datetime": "2026-10-25T01:00:00Z", "price": -0.25},
    ])

    today, _tomorrow = runtime.price_maps(entity, None, current=current)

    assert today == {2: 0.0}


def test_buy_and_sell_maps_remain_separate(monkeypatch):
    current = datetime(2026, 8, 24, 12, tzinfo=WARSAW)
    set_now(monkeypatch, current)
    runtime = make_runtime()
    sell = "sensor.sell_utc"
    buy = "sensor.buy_utc"
    add_prices(runtime, sell, [{"datetime": "2026-08-24T18:00:00Z", "price": -0.10}])
    add_prices(runtime, buy, [{"datetime": "2026-08-24T18:00:00Z", "price": 0.70}])

    sell_maps = runtime.price_maps(sell, None, current=current)
    buy_maps = runtime.price_maps(buy, None, current=current)

    assert sell_maps[0] == {20: -0.10}
    assert buy_maps[0] == {20: 0.70}


def test_dst_spring_skips_nonexistent_local_hour(monkeypatch):
    current = datetime(2026, 3, 29, 12, tzinfo=WARSAW)
    set_now(monkeypatch, current)
    runtime = make_runtime()
    entity = "sensor.spring_prices"
    add_prices(runtime, entity, [
        {"datetime": "2026-03-29T00:00:00Z", "price": 1.0},
        {"datetime": "2026-03-29T01:00:00Z", "price": 2.0},
    ])

    today, _tomorrow = runtime.price_maps(entity, None, current=current)

    assert today == {1: 1.0, 3: 2.0}
    assert 2 not in today


def test_standard_days_keep_24_by_24_coverage(monkeypatch):
    current = datetime(2026, 8, 24, 12, tzinfo=WARSAW)
    set_now(monkeypatch, current)
    runtime = make_runtime()
    today_entity = "sensor.standard_today"
    tomorrow_entity = "sensor.standard_tomorrow"
    add_prices(runtime, today_entity, [
        {"datetime": f"2026-08-24T{hour:02d}:00:00+02:00", "price": hour}
        for hour in range(24)
    ])
    add_prices(runtime, tomorrow_entity, [
        {"datetime": f"2026-08-25T{hour:02d}:00:00+02:00", "price": hour + 24}
        for hour in range(24)
    ])

    today, tomorrow = runtime.price_maps(today_entity, tomorrow_entity, current=current)

    assert len(today) == 24
    assert len(tomorrow) == 24
    assert today[0] == 0
    assert tomorrow[23] == 47


def test_manager_local_price_reaches_same_core_proposal_slot(monkeypatch):
    current = datetime(2026, 8, 24, 12, tzinfo=WARSAW)
    set_now(monkeypatch, current)
    runtime = make_runtime()
    entity = "sensor.core_price_utc"
    add_prices(runtime, entity, [{"datetime": "2026-08-24T18:00:00Z", "price": 1.75}])
    sell_maps = runtime.price_maps(entity, None, current=current)
    values = sale_case(
        {20: 1.75},
        target_kwh=1,
        start="20:00",
        end="21:00",
    )
    values["sell_prices"] = sell_maps

    plan = core.build_energy_plan(values)
    row = next(row for row in plan["rows"] if row["date"] == "2026-07-29" and row["hour"] == 20)

    assert sell_maps[0][20] == 1.75
    assert row["sell_price"] == 1.75

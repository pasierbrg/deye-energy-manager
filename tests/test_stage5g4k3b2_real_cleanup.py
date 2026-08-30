from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "price_sources.py"
SPEC = importlib.util.spec_from_file_location("stage5g4k3b2_price_sources", MODULE_PATH)
assert SPEC and SPEC.loader
price_sources = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = price_sources
SPEC.loader.exec_module(price_sources)

NOW = datetime(2026, 8, 26, 0, 0, tzinfo=timezone(timedelta(hours=2)))


@dataclass
class State:
    entity_id: str
    attributes: dict
    state: str = "unknown"


def rce_rows(day: datetime, price: float = 0.8) -> list[dict]:
    rows = []
    for index in range(96):
        start = day + timedelta(minutes=index * 15)
        end = day + timedelta(minutes=(index + 1) * 15)
        rows.append({
            "period": f"{start:%H:%M} - {'24:00' if index == 95 else end.strftime('%H:%M')}",
            "dtime": end.strftime("%Y-%m-%d %H:%M:%S"),
            "business_date": day.date().isoformat(),
            "rce_pln": price,
        })
    return rows


def test_explicit_empty_ignores_stale_states_and_has_zero_rows_for_both_days() -> None:
    stale = {
        "source_adapter": "pstryk",
        "today_entity": "sensor.old_pstryk_today",
        "tomorrow_entity": "sensor.old_pstryk_tomorrow",
        "semantic_scope": "all_in_variable",
        "includes_distribution_variable": True,
        "includes_excise": True,
        "includes_service_margin": True,
        "resolved_schema_tomorrow": {"schema_id": "pstryk_aio_interval_v1"},
    }
    contract = price_sources.rebuild_price_contract(stale, "buy", "", "", "generic", "generic")
    stale_today = State("sensor.old_pstryk_today", {"today_prices": [{
        "start": NOW.isoformat(), "end": (NOW + timedelta(hours=1)).isoformat(), "price": 0.9,
    }]})
    stale_tomorrow = State("sensor.old_pstryk_tomorrow", {"tomorrow_prices": [{
        "start": (NOW + timedelta(days=1, hours=23)).isoformat(),
        "end": (NOW + timedelta(days=2)).isoformat(), "price": 1.16,
    }]})

    result = price_sources.build_canonical_direction(contract, stale_today, stale_tomorrow, NOW, {})

    assert result["rows"] == []
    assert result["diagnostics"]["coverage_today"] == 0
    assert result["diagnostics"]["coverage_tomorrow"] == 0
    assert result["diagnostics"]["resolver"]["tomorrow"]["status"] == "unmapped"
    assert result["contract"]["adapter_summary"] == "unmapped"
    for forbidden in (
        "source_adapter", "semantic_scope", "includes_distribution_variable",
        "includes_excise", "includes_service_margin", "list_attribute", "value_field",
    ):
        assert forbidden not in result["contract"]


def test_stale_pstryk_contract_rebuilds_clean_rce_and_aggregates_96_to_24() -> None:
    stale = {
        "source_adapter": "pstryk",
        "today_entity": "sensor.old_pstryk",
        "tomorrow_entity": "sensor.old_pstryk_tomorrow",
        "semantic_scope": "all_in_variable",
        "includes_distribution_variable": True,
        "includes_excise": True,
        "includes_service_margin": True,
        "today_list_attribute": "today_prices",
        "tomorrow_list_attribute": "tomorrow_prices",
    }
    contract = price_sources.rebuild_price_contract(
        stale, "buy", "sensor.rce_today", "sensor.rce_tomorrow", "rce_pse", "rce_pse"
    )
    result = price_sources.build_canonical_direction(
        contract,
        State("sensor.rce_today", {"prices": rce_rows(NOW)}),
        State("sensor.rce_tomorrow", {"prices": rce_rows(NOW + timedelta(days=1), 0.9)}),
        NOW,
        {},
    )

    assert len([row for row in result["rows"] if row["day"] == "today"]) == 24
    assert len([row for row in result["rows"] if row["day"] == "tomorrow"]) == 24
    assert contract["semantic_scope"] == "energy_only"
    assert contract["includes_distribution_variable"] is False
    assert contract["includes_excise"] is False
    assert contract["includes_service_margin"] is False
    assert contract["value_field"] == "rce_pln"
    assert contract["period_field"] == "period"
    assert contract["timestamp_field"] == "dtime"
    assert contract["business_date_field"] == "business_date"
    assert contract["granularity"] == "15m"
    assert all(row["source_adapter"] == "rce_pse" for row in result["rows"])
    assert all(row["source_semantic_scope"] == "energy_only" for row in result["rows"])


def test_clear_buy_does_not_change_independent_rce_sell_contract() -> None:
    buy = price_sources.rebuild_price_contract({}, "buy", "", "", "generic", "generic")
    sell = price_sources.rebuild_price_contract(
        {}, "sell", "sensor.rce_sell_today", "sensor.rce_sell_tomorrow", "rce_pse", "rce_pse"
    )
    buy_result = price_sources.build_canonical_direction(buy, None, None, NOW, {})
    sell_result = price_sources.build_canonical_direction(
        sell,
        State("sensor.rce_sell_today", {"prices": rce_rows(NOW)}),
        State("sensor.rce_sell_tomorrow", {"prices": rce_rows(NOW + timedelta(days=1))}),
        NOW,
        {},
    )

    assert buy_result["rows"] == []
    assert len(sell_result["rows"]) == 48
    assert sell_result["contract"]["source_adapter"] == "rce_pse"

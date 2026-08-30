from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "price_sources.py"
SPEC = importlib.util.spec_from_file_location("stage5g4k3a_price_sources", MODULE_PATH)
assert SPEC and SPEC.loader
price_sources = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = price_sources
SPEC.loader.exec_module(price_sources)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone(timedelta(hours=2)))


@dataclass
class State:
    entity_id: str
    state: str = "unknown"
    attributes: dict | None = None

    def __post_init__(self) -> None:
        self.attributes = self.attributes or {}


def interval_rows(day: datetime, value: float, *, value_key: str = "price", start_key: str = "start", end_key: str = "end") -> list[dict]:
    return [
        {
            start_key: day.replace(hour=hour, minute=0).isoformat(),
            end_key: (day.replace(hour=hour, minute=0) + timedelta(hours=1)).isoformat(),
            value_key: value,
        }
        for hour in range(24)
    ]


def explicit_contract(direction: str, adapter: str = "generic", **extra) -> dict:
    today = str(extra.pop("today_entity", "sensor.today"))
    tomorrow = str(extra.pop("tomorrow_entity", "sensor.tomorrow"))
    value = {
        "source_adapter": adapter,
        "economic_role": "energy_only" if direction == "buy" else "market_reference",
        "semantic_scope": "energy_only" if direction == "buy" else "partial",
        "includes_distribution_variable": False,
        "price_basis": "gross",
        "unit": "PLN/kWh",
        **extra,
    }
    return price_sources.normalize_price_contract(value, direction, adapter, today, tomorrow)


@pytest.mark.parametrize(
    ("entity_id", "attribute"),
    [
        ("sensor.foo", "today_prices"),
        ("sensor.bar", "tomorrow_prices"),
        ("sensor.buy_tomorrow_custom_name", "today_prices"),
        ("sensor.sprzedaz_x", "tomorrow_prices"),
    ],
)
def test_pstryk_schema_is_independent_of_entity_id(entity_id: str, attribute: str) -> None:
    day_offset = 0 if attribute == "today_prices" else 1
    day = NOW + timedelta(days=day_offset)
    contract = price_sources.normalize_price_contract(
        {"source_adapter": "pstryk"},
        "buy",
        "pstryk",
        entity_id if day_offset == 0 else "",
        entity_id if day_offset == 1 else "",
    )
    state = State(entity_id, attributes={attribute: interval_rows(day, 0.51)})
    result = price_sources.build_canonical_direction(
        contract,
        state if day_offset == 0 else None,
        state if day_offset == 1 else None,
        NOW,
        {(day.date(), hour): 0.75 for hour in range(24)},
    )
    assert len(result["rows"]) == 24
    assert {row["day"] for row in result["rows"]} == {"today" if day_offset == 0 else "tomorrow"}
    assert all(row["source_price_pln_kwh"] == pytest.approx(0.51) for row in result["rows"])
    assert all(row["added_distribution"] == 0 for row in result["rows"])


def test_real_pstryk_four_mapped_entities_have_24_plus_24_independent_buy_sell() -> None:
    today, tomorrow = NOW, NOW + timedelta(days=1)
    states = {
        "buy_today": State("sensor.foo", attributes={"today_prices": interval_rows(today, 0.31)}),
        "buy_tomorrow": State("sensor.bar", attributes={"tomorrow_prices": interval_rows(tomorrow, 0.32)}),
        "sell_today": State("sensor.sprzedaz_x", attributes={"today_prices": interval_rows(today, 0.81)}),
        "sell_tomorrow": State("sensor.sell_future", attributes={"tomorrow_prices": interval_rows(tomorrow, 0.82)}),
    }
    buy = price_sources.build_canonical_direction(
        price_sources.normalize_price_contract({"source_adapter": "pstryk"}, "buy", "pstryk", "sensor.foo", "sensor.bar"),
        states["buy_today"], states["buy_tomorrow"], NOW,
        {(NOW.date() + timedelta(days=day), hour): 0.55 for day in (0, 1) for hour in range(24)},
    )
    sell = price_sources.build_canonical_direction(
        price_sources.normalize_price_contract({"source_adapter": "pstryk"}, "sell", "pstryk", "sensor.sprzedaz_x", "sensor.sell_future"),
        states["sell_today"], states["sell_tomorrow"], NOW, {},
    )
    assert buy["diagnostics"]["coverage_today"] == buy["diagnostics"]["coverage_tomorrow"] == 24
    assert sell["diagnostics"]["coverage_today"] == sell["diagnostics"]["coverage_tomorrow"] == 24
    assert all(row["added_distribution"] == 0 for row in buy["rows"])
    assert {row["source_price_pln_kwh"] for row in buy["rows"]} == {0.31, 0.32}
    assert {row["source_price_pln_kwh"] for row in sell["rows"]} == {0.81, 0.82}


def test_provider_name_is_never_adapter_identity() -> None:
    misleading = "sensor.pstryk_aio_obecna_cena_zakupu_pradu"
    assert price_sources.detect_source_adapter(misleading) == "generic"
    assert price_sources.detect_source_adapter(misleading, platform="custom_prices") == "generic"
    assert price_sources.detect_source_adapter(misleading, explicit="custom") == "custom"


@pytest.mark.parametrize(
    ("today_attr", "tomorrow_attr"),
    [("today_prices", "tomorrow_prices"), ("prices", "prices")],
)
def test_generic_supported_list_schemas_do_not_gain_pstryk_semantics(today_attr: str, tomorrow_attr: str) -> None:
    contract = explicit_contract("buy")
    result = price_sources.build_canonical_direction(
        contract,
        State("sensor.today", attributes={today_attr: interval_rows(NOW, 0.4)}),
        State("sensor.tomorrow", attributes={tomorrow_attr: interval_rows(NOW + timedelta(days=1), 0.5)}),
        NOW,
        {(NOW.date() + timedelta(days=day), hour): 0.2 for day in (0, 1) for hour in range(24)},
    )
    assert len(result["rows"]) == 48
    assert result["contract"]["source_adapter"] == "generic"
    assert result["contract"]["semantic_scope"] == "energy_only"
    assert all(row["added_distribution"] == pytest.approx(0.2) for row in result["rows"])


def test_generic_time_price_and_start_value_schemas() -> None:
    time_rows = [{"time": f"{hour:02d}:00", "price": 0.7} for hour in range(24)]
    start_rows = [{"start": f"{hour:02d}:00", "value": 0.8} for hour in range(24)]
    for rows, attribute, expected in ((time_rows, "today_prices", 0.7), (start_rows, "prices", 0.8)):
        result = price_sources.build_canonical_direction(
            explicit_contract("sell", list_attribute=attribute),
            State("sensor.today", attributes={attribute: rows}), None, NOW, {},
        )
        assert len(result["rows"]) == 24
        assert all(row["source_price_pln_kwh"] == pytest.approx(expected) for row in result["rows"])


def test_custom_explicit_fields_are_resolved_once_and_preserved_on_reload() -> None:
    contract = explicit_contract(
        "sell", "custom", list_attribute="series", value_field="cost",
        start_field="from", end_field="to", granularity="60m",
    )
    state = State("sensor.today", attributes={"series": interval_rows(NOW, 0.91, value_key="cost", start_key="from", end_key="to")})
    resolved, diagnostics = price_sources.resolve_contract_schemas(contract, state, None)
    assert diagnostics["today"]["status"] == "ready"
    assert resolved["resolved_schema_today"]["list_attribute"] == "series"
    assert resolved["resolved_schema_today"]["start_field"] == "from"
    reloaded = price_sources.normalize_price_contract(resolved, "sell", "custom", "sensor.today", "")
    assert reloaded["resolved_schema_today"] == resolved["resolved_schema_today"]
    assert len(price_sources.build_canonical_direction(reloaded, state, None, NOW, {})["rows"]) == 24


def test_numeric_state_is_allowed_only_for_explicit_current_price_contract() -> None:
    state = State("sensor.today", state="0.62", attributes={"unit_of_measurement": "PLN/kWh"})
    series = explicit_contract("sell", current_price_only=False)
    current = explicit_contract("sell", current_price_only=True, allow_state_fallback=True)
    assert price_sources.build_canonical_direction(series, state, None, NOW, {})["rows"] == []
    current_result = price_sources.build_canonical_direction(current, state, None, NOW, {})
    assert len(current_result["rows"]) == 1
    assert current_result["rows"][0]["hour"] == NOW.hour


def test_unsupported_series_fails_closed_instead_of_using_numeric_state() -> None:
    state = State("sensor.today", state="1.23", attributes={"unsupported": [{"foo": 1}]})
    result = price_sources.build_canonical_direction(explicit_contract("sell"), state, None, NOW, {})
    assert result["rows"] == []
    assert result["diagnostics"]["resolver"]["today"]["status"] == "unsupported_price_schema"


def test_migration_maps_pse_rce_alias_and_preserves_selected_entities() -> None:
    source = {
        "price_source": "pse_rce",
        "buy_price_today_sensor": "sensor.my_rce",
        "buy_price_tomorrow_sensor": "sensor.my_rce_tomorrow",
        "price_sensor": "sensor.my_sell",
        "sell_price_tomorrow_sensor": "sensor.my_sell_tomorrow",
    }
    migrated = price_sources.migrate_legacy_price_contracts(source)
    assert migrated["buy_price_contract"]["source_adapter"] == "rce_pse"
    assert migrated["buy_price_contract"]["today_entity"] == "sensor.my_rce"
    assert migrated["sell_price_contract"]["tomorrow_entity"] == "sensor.my_sell_tomorrow"


def test_config_and_frontend_contracts_expose_validation_and_backend_only_diagnostics() -> None:
    config = (ROOT / "custom_components" / "deye_energy_manager" / "config_flow.py").read_text(encoding="utf-8")
    card = (ROOT / "custom_components" / "deye_energy_manager" / "www" / "deye-energy-manager-card.js").read_text(encoding="utf-8")
    assert "_resolve_price_mapping_contracts" in config
    assert "unsupported_price_schema" in config
    assert "mapped_entity_missing" in config
    assert 'field("start_field"' in card and 'field("end_field"' in card
    assert "Resolver mapowanych encji" in card
    assert "canonical_prices" in card
    assert "Frontend nie odczytuje ani nie zgaduje schematu" in card

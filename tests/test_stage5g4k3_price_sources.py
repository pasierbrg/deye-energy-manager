from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import random
import sys

import pytest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "deye_energy_manager" / "price_sources.py"
SPEC = importlib.util.spec_from_file_location("stage5g4k3_price_sources", MODULE_PATH)
assert SPEC and SPEC.loader
price_sources = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = price_sources
SPEC.loader.exec_module(price_sources)
PriceInterval = price_sources.PriceInterval
aggregate_hourly = price_sources.aggregate_hourly
build_canonical_direction = price_sources.build_canonical_direction
default_price_contract = price_sources.default_price_contract
detect_source_adapter = price_sources.detect_source_adapter
migrate_legacy_price_contracts = price_sources.migrate_legacy_price_contracts
normalize_price_contract = price_sources.normalize_price_contract


@dataclass
class State:
    entity_id: str
    state: str = "unknown"
    attributes: dict | None = None

    def __post_init__(self) -> None:
        self.attributes = self.attributes or {}


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone(timedelta(hours=2)))


def rce_rows(day: str, base: float = 0.4) -> list[dict]:
    rows = []
    for quarter in range(96):
        start_minute = quarter * 15
        end_minute = start_minute + 15
        sh, sm = divmod(start_minute, 60)
        eh, em = divmod(end_minute, 60)
        period_end = "24:00" if eh == 24 else f"{eh:02d}:{em:02d}"
        dtime_day = datetime.fromisoformat(day) + timedelta(minutes=end_minute)
        rows.append({
            "dtime": dtime_day.strftime("%Y-%m-%d %H:%M:%S"),
            "period": f"{sh:02d}:{sm:02d} - {period_end}",
            "rce_pln": base + quarter / 1000,
            "business_date": day,
        })
    return rows


def rce_contract(direction: str = "buy", **overrides) -> dict:
    value = {
        "source_adapter": "rce_pse",
        "price_basis": "gross",
        "unit": "PLN/kWh",
        "list_attribute": "value_json",
        **overrides,
    }
    return normalize_price_contract(value, direction, "rce_pse", "sensor.rce_today", "sensor.rce_tomorrow")


def test_adapter_detection_prefers_metadata_and_explicit_override() -> None:
    assert detect_source_adapter("sensor.renamed", platform="pstryk") == "pstryk"
    assert detect_source_adapter("sensor.renamed", config_entry_domain="rce_pse") == "rce_pse"
    assert detect_source_adapter("sensor.renamed", device_metadata="Pstryk energy service") == "pstryk"
    assert detect_source_adapter("sensor.pstryk_name", explicit="custom") == "custom"
    assert detect_source_adapter("sensor.unknown") == "generic"


def test_pstryk_contract_is_forced_all_in_gross_and_never_adds_osd() -> None:
    contract = normalize_price_contract(
        {"source_adapter": "pstryk", "price_basis": "net", "includes_distribution_variable": False},
        "buy", "pstryk", "sensor.pstryk_buy", "sensor.pstryk_buy_tomorrow",
    )
    assert contract["semantic_scope"] == "all_in_variable"
    assert contract["price_basis"] == "gross"
    assert contract["unit"] == "PLN/kWh"
    assert contract["includes_distribution_variable"] is True
    state = State("sensor.pstryk_buy", attributes={"prices": [
        {"datetime": f"2026-08-23T{hour:02d}:00:00+02:00", "price_gross": 0.23}
        for hour in range(24)
    ]})
    result = build_canonical_direction(contract, state, None, NOW, {(NOW.date(), hour): 0.55 for hour in range(24)})
    assert len(result["rows"]) == 24
    assert all(row["added_distribution"] == 0 for row in result["rows"])
    assert all(row["final_price_pln_kwh"] == pytest.approx(0.23) for row in result["rows"])


def test_rce_96_quarters_aggregate_to_24_duration_weighted_hours() -> None:
    today = State("sensor.rce_today", attributes={"value_json": rce_rows("2026-08-23")})
    tomorrow = State("sensor.rce_tomorrow", attributes={"value_json": rce_rows("2026-08-24", 0.8)})
    distribution = {
        (NOW.date() + timedelta(days=day), hour): 0.2
        for day in (0, 1) for hour in range(24)
    }
    result = build_canonical_direction(rce_contract(), today, tomorrow, NOW, distribution)
    assert result["diagnostics"]["status"] == "ready"
    assert len(result["rows"]) == 48
    first = result["rows"][0]
    assert first["source_price_pln_kwh"] == pytest.approx(sum(0.4 + i / 1000 for i in range(4)) / 4)
    assert first["added_distribution"] == pytest.approx(0.2)
    assert first["final_price_pln_kwh"] == pytest.approx(first["source_price_pln_kwh"] + 0.2)
    assert first["coverage_minutes"] == 60


def test_rce_order_is_irrelevant_and_business_date_owns_24_00_boundary() -> None:
    rows = rce_rows("2026-08-23")
    random.Random(42).shuffle(rows)
    result = build_canonical_direction(
        rce_contract(), State("sensor.rce_today", attributes={"value_json": rows}), None, NOW, {}
    )
    assert len(result["rows"]) == 24
    assert result["rows"][-1]["date"] == "2026-08-23"
    assert result["rows"][-1]["hour"] == 23
    assert result["rows"][-1]["source_metadata"]["interval_count"] == 4


def test_partial_and_overlap_hours_fail_closed() -> None:
    base = NOW.replace(hour=0)
    complete, diag = aggregate_hourly([
        PriceInterval(base, base + timedelta(minutes=45), 1.0, "x", 0),
    ])
    assert complete == {}
    assert diag["partial_hours"]
    complete, diag = aggregate_hourly([
        PriceInterval(base, base + timedelta(minutes=40), 1.0, "x", 0),
        PriceInterval(base + timedelta(minutes=30), base + timedelta(hours=1), 2.0, "x", 1),
    ])
    assert complete == {}
    assert diag["invalid_hours"]


def test_units_net_vat_negative_prices_and_unknown_contracts() -> None:
    contract = normalize_price_contract({
        "source_adapter": "custom", "economic_role": "energy_only", "semantic_scope": "energy_only",
        "includes_distribution_variable": False, "price_basis": "net", "vat_rate": 0.23,
        "unit": "PLN/MWh", "list_attribute": "rows", "value_field": "amount",
        "timestamp_field": "start", "granularity": "60m",
    }, "buy", "custom", "sensor.custom", "")
    state = State("sensor.custom", attributes={"rows": [
        {"start": f"2026-08-23T{hour:02d}:00:00+02:00", "amount": -100 if hour == 0 else 100}
        for hour in range(24)
    ]})
    result = build_canonical_direction(contract, state, None, NOW, {(NOW.date(), hour): 0.2 for hour in range(24)})
    assert result["rows"][0]["source_price_pln_kwh"] == pytest.approx(-0.1)
    assert result["rows"][0]["added_vat"] == pytest.approx(-0.023)
    assert result["rows"][0]["final_price_pln_kwh"] == pytest.approx(0.077)
    unknown = default_price_contract("buy", "custom", "sensor.x", "")
    assert build_canonical_direction(unknown, state, None, NOW)["diagnostics"]["status"] == "unknown_price_basis"


def test_rce_sell_current_sensor_never_becomes_forecast() -> None:
    result = build_canonical_direction(
        rce_contract("sell", semantic_scope="partial", includes_distribution_variable="unknown"),
        State("sensor.rce_sell", state="0.75"), None, NOW, {},
    )
    assert result["rows"] == []
    assert result["diagnostics"]["status"] == "missing_sell_forecast"
    assert result["diagnostics"]["current_value_available"] is True


def test_legacy_migration_preserves_entities_and_separates_directions() -> None:
    legacy = {
        "price_source": "pstryk", "price_includes_distribution": False,
        "price_sensor": "sensor.renamed_sell", "buy_price_today_sensor": "sensor.renamed_buy",
    }
    migrated = migrate_legacy_price_contracts(legacy)
    assert migrated["price_sensor"] == "sensor.renamed_sell"
    assert migrated["buy_price_contract"]["today_entity"] == "sensor.renamed_buy"
    assert migrated["sell_price_contract"]["today_entity"] == "sensor.renamed_sell"
    assert migrated["buy_price_contract"] is not migrated["sell_price_contract"]

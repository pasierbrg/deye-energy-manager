from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "price_sources.py"
SPEC = importlib.util.spec_from_file_location("stage5g4k3b_price_sources", MODULE_PATH)
assert SPEC and SPEC.loader
price_sources = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = price_sources
SPEC.loader.exec_module(price_sources)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone(timedelta(hours=2)))
PRICE_KEYS = (
    "buy_price_today_sensor",
    "buy_price_tomorrow_sensor",
    "price_sensor",
    "sell_price_tomorrow_sensor",
)


@dataclass
class State:
    entity_id: str
    state: str = "unknown"
    attributes: dict | None = None

    def __post_init__(self) -> None:
        self.attributes = self.attributes or {}


def test_normalizer_distinguishes_absent_entity_from_explicit_empty() -> None:
    absent = price_sources.normalize_price_contract(
        {"source_adapter": "pstryk"}, "buy", "pstryk", "sensor.default_today", "sensor.default_tomorrow"
    )
    empty = price_sources.normalize_price_contract(
        {"source_adapter": "pstryk", "today_entity": None, "tomorrow_entity": ""},
        "buy", "pstryk", "sensor.default_today", "sensor.default_tomorrow",
    )
    assert absent["today_entity"] == "sensor.default_today"
    assert absent["tomorrow_entity"] == "sensor.default_tomorrow"
    assert empty["today_entity"] == ""
    assert empty["tomorrow_entity"] == ""


def test_absent_legacy_keys_receive_one_time_defaults() -> None:
    migrated = price_sources.migrate_legacy_price_contracts({"price_source": "pstryk"})
    assert all(key in migrated for key in PRICE_KEYS)
    assert migrated["buy_price_today_sensor"].startswith("sensor.pstryk_aio_")
    assert migrated["sell_price_contract"]["today_entity"] == migrated["price_sensor"]


def test_explicit_empty_legacy_keys_are_never_migrated_to_provider_defaults() -> None:
    migrated = price_sources.migrate_legacy_price_contracts({
        "price_source": "pstryk",
        "buy_price_today_sensor": "",
        "buy_price_tomorrow_sensor": None,
        "price_sensor": "",
        "sell_price_tomorrow_sensor": None,
    })
    assert all(migrated[key] == "" for key in PRICE_KEYS)
    assert migrated["buy_price_contract"]["today_entity"] == ""
    assert migrated["buy_price_contract"]["tomorrow_entity"] == ""
    assert migrated["sell_price_contract"]["today_entity"] == ""
    assert migrated["sell_price_contract"]["tomorrow_entity"] == ""


def test_existing_contract_empty_is_promoted_to_central_mapping_on_upgrade() -> None:
    migrated = price_sources.migrate_legacy_price_contracts({
        "price_source": "pstryk",
        "buy_price_contract": {"source_adapter": "pstryk", "today_entity": "", "tomorrow_entity": ""},
    })
    assert migrated["buy_price_today_sensor"] == ""
    assert migrated["buy_price_tomorrow_sensor"] == ""


def test_mapping_key_empty_overrides_stale_contract_entity() -> None:
    migrated = price_sources.migrate_legacy_price_contracts({
        "price_source": "pstryk",
        "buy_price_today_sensor": "",
        "buy_price_contract": {
            "source_adapter": "pstryk",
            "today_entity": "sensor.previous_pstryk",
            "tomorrow_entity": "sensor.previous_tomorrow",
        },
    })
    assert migrated["buy_price_contract"]["today_entity"] == ""
    assert migrated["buy_price_contract"]["tomorrow_entity"] == "sensor.previous_tomorrow"


def test_unmapped_contract_has_no_rows_no_state_fallback_and_clear_status() -> None:
    contract = price_sources.normalize_price_contract(
        {
            "source_adapter": "pstryk",
            "today_entity": "",
            "tomorrow_entity": "",
            "current_price_only": True,
            "allow_state_fallback": True,
        },
        "buy", "pstryk", "sensor.provider_default", "sensor.provider_tomorrow",
    )
    result = price_sources.build_canonical_direction(contract, None, None, NOW, {})
    assert result["rows"] == []
    assert result["diagnostics"]["status"] == "price_source_not_configured"
    assert result["diagnostics"]["resolver"]["today"]["status"] == "unmapped"
    assert result["diagnostics"]["resolver"]["tomorrow"]["status"] == "unmapped"


def test_one_day_explicit_empty_does_not_remove_other_day() -> None:
    rows = [
        {
            "start": (NOW + timedelta(days=1)).replace(hour=hour, minute=0).isoformat(),
            "end": ((NOW + timedelta(days=1)).replace(hour=hour, minute=0) + timedelta(hours=1)).isoformat(),
            "price": 0.7,
        }
        for hour in range(24)
    ]
    contract = price_sources.normalize_price_contract(
        {"source_adapter": "pstryk", "today_entity": "", "tomorrow_entity": "sensor.only_tomorrow"},
        "sell", "pstryk", "sensor.provider_today", "sensor.only_tomorrow",
    )
    result = price_sources.build_canonical_direction(
        contract, None, State("sensor.only_tomorrow", attributes={"tomorrow_prices": rows}), NOW, {}
    )
    assert len(result["rows"]) == 24
    assert {row["day"] for row in result["rows"]} == {"tomorrow"}
    assert result["diagnostics"]["resolver"]["today"]["status"] == "unmapped"


def test_no_or_default_semantics_remain_in_price_mapping_hotspots() -> None:
    manager = (ROOT / "custom_components" / "deye_energy_manager" / "manager.py").read_text(encoding="utf-8")
    flow = (ROOT / "custom_components" / "deye_energy_manager" / "config_flow.py").read_text(encoding="utf-8")
    migration = (ROOT / "custom_components" / "deye_energy_manager" / "price_sources.py").read_text(encoding="utf-8")
    assert "return str(configured) if configured else DEFAULT_PRICE_SENSOR" not in manager
    assert "migrated.get(\"buy_price_today_sensor\") or" not in migration
    assert "migrated.get(\"price_sensor\") or" not in migration
    assert "for key in PRICE_FIELDS:" in flow
    assert "if key in PRICE_FIELDS and key in self._values:" in flow

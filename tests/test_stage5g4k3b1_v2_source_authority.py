from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "price_sources.py"
SPEC = importlib.util.spec_from_file_location("stage5g4k3b1_price_sources", MODULE_PATH)
assert SPEC and SPEC.loader
price_sources = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = price_sources
SPEC.loader.exec_module(price_sources)


def test_pstryk_to_rce_discards_all_auto_metadata_from_old_mapping() -> None:
    saved = price_sources.rebuild_price_contract(
        {}, "buy", "sensor.pstryk_buy", "sensor.pstryk_buy_tomorrow", "pstryk", "pstryk"
    )
    saved["resolved_schema_today"] = {
        "schema_id": "pstryk_aio_interval_v1", "list_attribute": "today_prices",
    }
    switched = price_sources.rebuild_price_contract(
        saved, "buy", "sensor.rce_pse_cena", "sensor.rce_pse_cena_jutro", "rce_pse", "rce_pse"
    )
    assert switched["source_adapter"] == "rce_pse"
    assert switched["resolved_adapter_today"] == "rce_pse"
    assert switched["resolved_schema_today"] == {}
    assert switched["semantic_scope"] == "energy_only"
    assert switched["includes_distribution_variable"] is False
    assert switched["value_field"] == "rce_pln"
    assert switched["today_list_attribute"] != "today_prices"
    assert switched["mapping_fingerprint"] != saved["mapping_fingerprint"]


def test_rce_to_pstryk_discards_rce_schema_and_rebuilds_pstryk() -> None:
    saved = price_sources.rebuild_price_contract(
        {}, "buy", "sensor.rce", "sensor.rce_tomorrow", "rce_pse", "rce_pse"
    )
    saved["resolved_schema_today"] = {
        "schema_id": "rce_interval_v1", "list_attribute": "prices", "value_field": "rce_pln",
    }
    switched = price_sources.rebuild_price_contract(
        saved, "buy", "sensor.pstryk", "sensor.pstryk_tomorrow", "pstryk", "pstryk"
    )
    assert switched["source_adapter"] == "pstryk"
    assert switched["resolved_schema_today"] == {}
    assert switched["semantic_scope"] == "all_in_variable"
    assert switched["includes_distribution_variable"] is True
    assert switched["value_field"] == "price"


def test_clear_removes_binding_schema_adapter_and_provider_semantics() -> None:
    saved = price_sources.rebuild_price_contract(
        {}, "buy", "sensor.pstryk", "sensor.pstryk_tomorrow", "pstryk", "pstryk"
    )
    saved["today_binding"] = {"entity_id": "sensor.pstryk", "registry_entry_id": "old"}
    saved["resolved_schema_today"] = {"schema_id": "pstryk_aio_interval_v1"}
    cleared = price_sources.rebuild_price_contract(saved, "buy", "", "", "generic", "generic")
    assert cleared["today_entity"] == ""
    assert cleared["tomorrow_entity"] == ""
    assert cleared["resolved_adapter_today"] == "unmapped"
    assert cleared["resolved_source_today"] == {}
    assert cleared["resolved_schema_today"] == {}
    assert cleared["adapter_summary"] == "unmapped"


def test_custom_overrides_survive_same_mapping_but_not_entity_switch() -> None:
    custom = price_sources.rebuild_price_contract(
        {
            "source_adapter": "custom", "today_entity": "sensor.custom",
            "tomorrow_entity": "", "semantic_scope": "energy_only",
            "includes_distribution_variable": False, "price_basis": "gross",
            "unit": "PLN/kWh", "list_attribute": "hourly", "value_field": "amount",
        },
        "buy", "sensor.custom", "", "custom", "generic",
    )
    same = price_sources.rebuild_price_contract(
        custom, "buy", "sensor.custom", "", "generic", "generic"
    )
    changed = price_sources.rebuild_price_contract(
        custom, "buy", "sensor.other", "", "generic", "generic"
    )
    assert same["source_adapter"] == "custom"
    assert same["value_field"] == "amount"
    assert changed["source_adapter"] == "generic"
    assert changed["value_field"] == "price"
    assert changed["price_basis"] == "unknown"


def test_one_changed_day_preserves_other_day_schema_and_uses_mixed_profiles() -> None:
    saved = price_sources.rebuild_price_contract(
        {}, "buy", "sensor.pstryk_today", "sensor.pstryk_tomorrow", "pstryk", "pstryk"
    )
    today_schema = {"schema_id": "pstryk_aio_interval_v1", "list_attribute": "today_prices"}
    saved["resolved_schema_today"] = today_schema
    saved["resolved_schema_tomorrow"] = {"schema_id": "pstryk_aio_interval_v1"}
    mixed = price_sources.rebuild_price_contract(
        saved, "buy", "sensor.pstryk_today", "sensor.rce_tomorrow", "pstryk", "rce_pse"
    )
    assert mixed["adapter_summary"] == "mixed"
    assert mixed["resolved_schema_today"] == today_schema
    assert mixed["resolved_schema_tomorrow"] == {}
    assert price_sources.effective_contract_for_day(mixed, 0)["source_adapter"] == "pstryk"
    assert price_sources.effective_contract_for_day(mixed, 1)["source_adapter"] == "rce_pse"


def test_legacy_source_selector_is_not_runtime_authority_for_present_mapping_keys() -> None:
    manager_source = (ROOT / "custom_components" / "deye_energy_manager" / "manager.py").read_text(encoding="utf-8")
    flow_source = (ROOT / "custom_components" / "deye_energy_manager" / "config_flow.py").read_text(encoding="utf-8")
    assert 'if self.price_source == "none"' not in manager_source
    assert 'buy_source["source_adapter"] = adapter' not in manager_source
    assert 'vol.Optional(\n                    key,\n                    description={"suggested_value": default}' in flow_source

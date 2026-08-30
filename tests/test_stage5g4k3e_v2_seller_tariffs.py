from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types

import pytest


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "tariffs.py"
SPEC = importlib.util.spec_from_file_location("stage5g4k3e_v2_tariffs", MODULE_PATH)
assert SPEC and SPEC.loader
tariffs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tariffs)

NOW = datetime(2026, 8, 27, 12, tzinfo=timezone(timedelta(hours=2)))

EXPECTED_GROUPS = {
    "pge": {"g11", "g12", "g12w", "g12n", "g12as", "g12e"},
    "tauron": {"g11", "g12", "g12w", "g12as", "g13", "g13s", "g14dynamic"},
    "enea": {"g11", "g11pewna", "g12", "g12w", "g12as", "g12sezon", "g13active", "g11p", "g12p"},
    "energa": {"g11", "g11f", "g12", "g12w", "g12r", "g12as"},
    "stoen": {"g11", "g12", "g12w", "g12as", "g12eko"},
    "other": {"custom"},
}

SUPPORTED = {
    "pge": {"g11", "g12", "g12w", "g12n"},
    "tauron": {"g11", "g12", "g12w", "g13"},
    "enea": {"g11", "g12", "g12w", "g11p", "g12p"},
    "energa": {"g11", "g12", "g12w", "g12r"},
    "stoen": {"g11", "g12", "g12w", "g12as"},
}


def catalog():
    return tariffs.load_bundled_catalog()


def distribution_profile(cat, provider="pge", plan="g12w", value=None):
    if value is not None:
        return {
            ((NOW + timedelta(days=offset)).date(), hour): value
            for offset in (0, 1)
            for hour in range(24)
        }
    profile = tariffs.catalog_hourly_profile(NOW, cat, provider, plan, 48)
    return {
        (date.fromisoformat(row["date"]), row["hour"]): row["total_distribution_rate"]
        for row in profile
    }


def test_every_osd_tariff_has_an_explicit_seller_support_classification():
    cat = catalog()
    actual = {
        provider: set(payload["tariffs"])
        for provider, payload in cat["providers"].items()
    }
    matrix = {provider: set(rows) for provider, rows in cat["seller_support_matrix"].items()}
    assert actual == EXPECTED_GROUPS
    assert matrix == actual
    assert sum(len(groups) for provider, groups in actual.items() if provider != "other") == 33


def test_only_the_21_audited_ordinary_contracts_are_supported():
    cat = catalog()
    for provider, groups in EXPECTED_GROUPS.items():
        for group in groups:
            row = tariffs.seller_support_entry(cat, provider, group)
            if group in SUPPORTED.get(provider, set()):
                assert row["status"] == "SUPPORTED_TARIFF_BUY"
                assert row["seller_tariff_id"]
            else:
                assert row["status"] != "SUPPORTED_TARIFF_BUY"
                assert not row.get("seller_tariff_id")
    assert sum(len(seller["tariffs"]) for seller in cat["seller_tariffs"].values()) == 21


def test_pge_g12w_generates_complete_canonical_buy_and_counts_components_once():
    cat = catalog()
    result = tariffs.seller_catalog_canonical_buy(
        NOW, cat, "pge_obrot", "", "pge", "g12w", distribution_profile(cat)
    )
    assert result["diagnostics"]["status"] == "ready"
    assert result["diagnostics"]["coverage_today"] == 24
    assert result["diagnostics"]["coverage_tomorrow"] == 24
    assert len(result["rows"]) == 48
    for row in result["rows"]:
        assert row["added_vat"] == 0
        assert row["added_other_variable"] == 0
        assert row["source_basis"] == "gross"
        assert row["final_price_pln_kwh"] == pytest.approx(
            row["source_price_pln_kwh"] + row["added_distribution"]
        )


def test_explicit_seller_is_required_and_unsupported_special_is_fail_closed():
    cat = catalog()
    no_seller = tariffs.seller_catalog_canonical_buy(
        NOW, cat, "", "", "pge", "g12w", distribution_profile(cat)
    )
    special = tariffs.seller_catalog_canonical_buy(
        NOW, cat, "pge_obrot", "", "pge", "g12as", distribution_profile(cat, "pge", "g12as")
    )
    assert no_seller["rows"] == []
    assert no_seller["diagnostics"]["status"] == "seller_not_selected"
    assert special["rows"] == []
    assert special["diagnostics"]["status"] == "no_valid_standard_tariff"


def test_missing_distribution_slot_is_fail_closed_instead_of_assuming_zero():
    cat = catalog()
    distribution = distribution_profile(cat)
    distribution.pop(next(iter(distribution)))
    result = tariffs.seller_catalog_canonical_buy(
        NOW, cat, "pge_obrot", "", "pge", "g12w", distribution
    )
    assert result["rows"] == []
    assert result["diagnostics"]["status"] == "distribution_slot_unavailable"


def dated_catalog(old_end: str, new_start: str, new_end: str):
    cat = deepcopy(catalog())
    original = deepcopy(cat["seller_tariffs"]["pge_obrot"]["tariffs"]["pge_g11_2026"])
    old = deepcopy(original)
    old.update({"valid_from": "2026-01-01", "valid_to": old_end, "rates": {"all_day": 0.61}})
    new = deepcopy(original)
    new.update({"valid_from": new_start, "valid_to": new_end, "rates": {"all_day": 0.71}, "revision": "test-new"})
    seller_tariffs = cat["seller_tariffs"]["pge_obrot"]["tariffs"]
    del seller_tariffs["pge_g11_2026"]
    seller_tariffs.update({"pge_g11_old": old, "pge_g11_new": new})
    cat["seller_support_matrix"]["pge"]["g11"]["seller_tariff_id"] = "pge_g11_old"
    cat["valid_to"] = max("2026-12-31", new_end)
    return cat


@pytest.mark.parametrize(
    ("old_end", "new_start", "new_end", "target"),
    [
        ("2026-06-30", "2026-07-01", "2026-12-31", date(2026, 7, 1)),
        ("2026-12-31", "2027-01-01", "2027-12-31", date(2027, 1, 1)),
    ],
)
def test_validity_first_transitions_mid_year_and_new_year(old_end, new_start, new_end, target):
    cat = dated_catalog(old_end, new_start, new_end)
    tariffs.validate_catalog(cat)
    tariff_id, entry, status = tariffs.resolve_seller_tariff(
        cat, "pge_obrot", "pge_g11_old", "pge", "g11", target
    )
    assert tariff_id == "pge_g11_new"
    assert entry["rates"]["all_day"] == 0.71
    assert status == "validity_transition"


def test_expired_price_is_never_used_as_fallback():
    cat = dated_catalog("2026-06-30", "2026-07-01", "2026-12-31")
    del cat["seller_tariffs"]["pge_obrot"]["tariffs"]["pge_g11_new"]
    tariff_id, entry, status = tariffs.resolve_seller_tariff(
        cat, "pge_obrot", "pge_g11_old", "pge", "g11", date(2026, 7, 1)
    )
    assert tariff_id == ""
    assert entry is None
    assert status == "selected_tariff_expired"


def test_catalog_validator_rejects_overlap_unit_basis_and_missing_matrix():
    overlapping = dated_catalog("2026-07-01", "2026-07-01", "2026-12-31")
    with pytest.raises(ValueError, match="Overlapping"):
        tariffs.validate_catalog(overlapping)
    for field, value, message in (
        ("unit", "PLN/MWh", "unit"),
        ("price_basis", "net", "gross"),
        ("includes_distribution", True, "energy-only"),
    ):
        malformed = deepcopy(catalog())
        malformed["seller_tariffs"]["pge_obrot"]["tariffs"]["pge_g11_2026"][field] = value
        with pytest.raises(ValueError, match=message):
            tariffs.validate_catalog(malformed)
    incomplete = deepcopy(catalog())
    del incomplete["seller_support_matrix"]["pge"]["g12e"]
    with pytest.raises(ValueError, match="incomplete"):
        tariffs.validate_catalog(incomplete)


def test_manager_precedence_has_no_osd_to_seller_or_sell_to_buy_guess():
    source = (ROOT / "custom_components" / "deye_energy_manager" / "manager.py").read_text(encoding="utf-8")
    canonical = source.split("def canonical_price_context(", 1)[1].split("def _weather_factors_48h", 1)[0]
    migration = (ROOT / "custom_components" / "deye_energy_manager" / "__init__.py").read_text(encoding="utf-8")
    assert 'direction == "buy"' in canonical
    assert 'not str(contract.get("today_entity") or "")' in canonical
    assert 'not str(contract.get("tomorrow_entity") or "")' in canonical
    assert "self.buy_seller_id" in canonical
    assert "seller_catalog_canonical_buy" in canonical
    assert "CONF_BUY_SELLER_ID" in migration
    assert "DEFAULT_BUY_SELLER_ID" in migration
    assert "suggested_seller_id" not in migration
    assert "minor_version=24" in migration


def test_shared_updater_is_rare_atomic_and_reports_full_status():
    source = (ROOT / "custom_components" / "deye_energy_manager" / "tariff_catalog.py").read_text(encoding="utf-8")
    assert "REFRESH_INTERVAL = timedelta(days=90)" in source
    assert source.index("validate_catalog(candidate)") < source.index("self.catalog = candidate")
    for field in (
        "catalog_local_version", "catalog_remote_version", "catalog_last_checked",
        "catalog_update_result", "catalog_current_validity", "catalog_valid_to",
    ):
        assert field in source
    assert "error_last_known_good" in source


def load_catalog_manager_class():
    package_name = "stage5g4k3e_catalog_package"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "custom_components" / "deye_energy_manager")]
    sys.modules[package_name] = package
    sys.modules[f"{package_name}.tariffs"] = tariffs

    const_spec = importlib.util.spec_from_file_location(
        f"{package_name}.const", ROOT / "custom_components" / "deye_energy_manager" / "const.py"
    )
    assert const_spec and const_spec.loader
    const_module = importlib.util.module_from_spec(const_spec)
    sys.modules[const_spec.name] = const_module
    const_spec.loader.exec_module(const_module)

    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = object
    helpers = types.ModuleType("homeassistant.helpers")
    homeassistant = types.ModuleType("homeassistant")
    sys.modules.setdefault("homeassistant", homeassistant)
    sys.modules.setdefault("homeassistant.helpers", helpers)
    sys.modules["homeassistant.helpers.storage"] = storage

    module_spec = importlib.util.spec_from_file_location(
        f"{package_name}.tariff_catalog",
        ROOT / "custom_components" / "deye_energy_manager" / "tariff_catalog.py",
    )
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module.TariffCatalogManager


def test_updater_activation_is_atomic_and_keeps_last_known_good():
    manager_class = load_catalog_manager_class()
    manager = object.__new__(manager_class)
    active = catalog()
    manager.catalog = active
    manager.source = "bundled"

    invalid = deepcopy(active)
    invalid["catalog_version"] = "2026.08.27.2"
    invalid["seller_tariffs"]["pge_obrot"]["tariffs"]["pge_g11_2026"]["unit"] = "PLN/MWh"
    with pytest.raises(ValueError):
        manager._activate_if_newer(invalid, "online")
    assert manager.catalog is active
    assert manager.source == "bundled"

    valid = deepcopy(active)
    valid["catalog_version"] = "2026.08.27.2"
    assert manager._activate_if_newer(valid, "online") is True
    assert manager.catalog is valid
    assert manager.source == "online"

    obsolete = {"schema_version": 1, "catalog_version": "2025.1"}
    assert manager._activate_if_newer(obsolete, "online") is False
    assert manager.catalog is valid


def test_updater_due_check_uses_90_day_interval():
    manager_class = load_catalog_manager_class()
    manager = object.__new__(manager_class)
    manager.last_checked = "2026-01-01T00:00:00+00:00"
    assert manager.refresh_due(datetime(2026, 3, 31, tzinfo=timezone.utc)) is False
    assert manager.refresh_due(datetime(2026, 4, 1, tzinfo=timezone.utc)) is True

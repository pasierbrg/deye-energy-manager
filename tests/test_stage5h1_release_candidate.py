"""Stage 5H.1 local release-candidate contract tests."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "deye_energy_manager"


def test_release_identity_and_resource_revision_are_080_44():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    config_flow = (PACKAGE / "config_flow.py").read_text(encoding="utf-8")
    frontend = (PACKAGE / "frontend.py").read_text(encoding="utf-8")
    component_card = PACKAGE / "www" / "deye-energy-manager-card.js"
    public_card = ROOT / "www" / "deye-energy-manager-card.js"

    assert manifest["version"] == "0.8.0"
    assert "MINOR_VERSION = 24" in config_flow
    assert 'CARD_RESOURCE_REVISION = "0.8.0.44"' in frontend
    assert component_card.read_bytes() == public_card.read_bytes()
    assert component_card.read_text(encoding="utf-8").startswith(
        "// Resource revision: v=0.8.0.44\n"
    )


def test_runtime_static_route_uses_only_packaged_component_www():
    frontend = (PACKAGE / "frontend.py").read_text(encoding="utf-8")
    assert 'Path(__file__).parent / "www"' in frontend
    assert 'ROOT / "www"' not in frontend
    assert 'CARD_STATIC_ROOT = f"/{DOMAIN}"' in frontend


def test_release_notes_cover_final_rc_contract_without_overclaiming():
    notes = (ROOT / "RELEASE_NOTES_0.8.0.md").read_text(encoding="utf-8")
    required = (
        "automatycznie",
        "PriceSourceContract",
        "Pstryk",
        "PSE/RCE",
        "sprzedawc",
        "OSD",
        "FuturePlan",
        "JIT",
        "0 A",
        "Solcast",
        "issues #1, #2, #3, #5, #6, #7 i #9",
        "Issue #8",
        "deterministyczne obliczenia",
        "wyłącznie doradczy",
        "nie zastępuje zabezpieczeń sprzętowych",
    )
    for phrase in required:
        assert phrase in notes
    for forbidden in ("bezbłędny", "w 100% bezpieczny", "AI steruje falownikiem"):
        assert forbidden not in notes


def test_storage_and_yaml_installation_paths_are_explicitly_separated():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "INSTALL_PL.md").read_text(encoding="utf-8")
    canonical = "/deye_energy_manager/deye-energy-manager-card.js?v=0.8.0.44"

    assert "trybie UI/storage" in readme
    assert "automatycznie rejestruje" in readme
    assert "Tryb UI/storage — automatyczny zasób" in install
    assert "Tryb YAML — konfiguracja ręczna" in install
    assert canonical in readme and canonical in install


def test_active_release_files_use_only_canonical_repository_slug():
    old_slug = "deye-energy-manager-" + "0.7.1-main"
    canonical = "https://github.com/pasierbrg/deye-energy-manager"
    active_files = (
        ROOT / "README.md",
        ROOT / "INSTALL_PL.md",
        ROOT / "RELEASE_NOTES_0.8.0.md",
        PACKAGE / "manifest.json",
        PACKAGE / "const.py",
        PACKAGE / "tariff_catalog.py",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
    assert old_slug not in combined
    assert canonical in combined

"""Stage 5H.0 safe Lovelace resource and release-infrastructure tests."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "deye_energy_manager"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


package = ModuleType("stage5h0_deye_energy_manager")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package
_load_module(f"{package.__name__}.const", PACKAGE / "const.py")
frontend = _load_module(f"{package.__name__}.frontend", PACKAGE / "frontend.py")


class FakeCollection:
    def __init__(self, items=None, *, fail=False):
        self.items = deepcopy(items or [])
        self.fail = fail
        self.creates = []
        self.updates = []
        self.deletes = []

    def async_items(self):
        if self.fail:
            raise RuntimeError("collection failed")
        return deepcopy(self.items)

    async def async_create_item(self, data):
        self.creates.append(deepcopy(data))
        item = {
            "id": f"resource-{len(self.items) + 1}",
            "url": data["url"],
            "type": data["res_type"],
        }
        self.items.append(item)
        return deepcopy(item)

    async def async_update_item(self, item_id, data):
        self.updates.append((item_id, deepcopy(data)))
        for item in self.items:
            if item.get("id") == item_id:
                item.update(url=data["url"], type=data["res_type"])
                return deepcopy(item)
        raise KeyError(item_id)

    async def async_delete_item(self, item_id):
        self.deletes.append(item_id)


class FakeHttp:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    async def async_register_static_path(self, url_path, path, cache_headers):
        if self.fail:
            raise RuntimeError("static route failed")
        self.calls.append((url_path, path, cache_headers))


class FakeBus:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.listeners = []

    def async_listen_once(self, event_type, callback):
        if self.fail:
            raise RuntimeError("listener registration failed")
        record = [event_type, callback, True]
        self.listeners.append(record)

        def unsubscribe():
            record[2] = False

        return unsubscribe

    def fire(self, event_type="homeassistant_started"):
        for record in list(self.listeners):
            registered, callback, active = record
            if active and registered == event_type:
                record[2] = False
                callback(SimpleNamespace(event_type=event_type))


class FakeHass:
    def __init__(self, resources=...):
        self.data = {}
        if resources is not ...:
            self.data["lovelace"] = SimpleNamespace(resources=resources)
        self.http = FakeHttp()
        self.bus = FakeBus()
        self.tasks = []

    def async_create_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task


def resource(resource_id, url, resource_type="module"):
    return {"id": resource_id, "url": url, "type": resource_type}


def test_storage_without_resource_creates_exactly_one_module():
    async def scenario():
        collection = FakeCollection()
        hass = FakeHass(collection)

        state = await frontend.async_setup_frontend(hass)

        assert state["resource_result"]["status"] == "created"
        assert collection.creates == [
            {"url": frontend.CARD_RESOURCE_URL, "res_type": "module"}
        ]
        assert len(collection.items) == 1

    asyncio.run(scenario())


def test_current_storage_resource_is_unchanged_and_not_duplicated():
    async def scenario():
        original = resource("dem", frontend.CARD_RESOURCE_URL)
        collection = FakeCollection([original])
        hass = FakeHass(collection)

        await frontend.async_setup_frontend(hass)

        assert collection.items == [original]
        assert collection.creates == []
        assert collection.updates == []

    asyncio.run(scenario())


def test_old_revision_updates_existing_item_in_place():
    async def scenario():
        collection = FakeCollection(
            [resource("dem", f"{frontend.CARD_RESOURCE_PATH}?v=0.8.0.42")]
        )
        hass = FakeHass(collection)

        await frontend.async_setup_frontend(hass)

        assert collection.creates == []
        assert collection.updates == [
            (
                "dem",
                {"url": frontend.CARD_RESOURCE_URL, "res_type": "module"},
            )
        ]
        assert collection.items[0]["url"] == frontend.CARD_RESOURCE_URL

    asyncio.run(scenario())


def test_next_bundled_revision_reconciles_without_user_edit():
    async def scenario():
        collection = FakeCollection([resource("dem", frontend.CARD_RESOURCE_URL)])
        hass = FakeHass(collection)
        await frontend.async_setup_frontend(hass)

        original_url = frontend.CARD_RESOURCE_URL
        frontend.CARD_RESOURCE_URL = f"{frontend.CARD_RESOURCE_PATH}?v=0.8.0.45"
        try:
            await frontend.async_reconcile_lovelace_resource(hass)
        finally:
            frontend.CARD_RESOURCE_URL = original_url

        assert collection.updates == [
            (
                "dem",
                {
                    "url": f"{frontend.CARD_RESOURCE_PATH}?v=0.8.0.45",
                    "res_type": "module",
                },
            )
        ]

    asyncio.run(scenario())


def test_legacy_local_resource_migrates_in_place_and_preserves_type():
    async def scenario():
        collection = FakeCollection(
            [resource("legacy", "/local/deye-energy-manager-card.js?v=0.7.9.11", "js")]
        )
        hass = FakeHass(collection)

        await frontend.async_setup_frontend(hass)

        assert collection.creates == []
        assert collection.updates == [
            (
                "legacy",
                {"url": frontend.CARD_RESOURCE_URL, "res_type": "js"},
            )
        ]

    asyncio.run(scenario())


def test_reload_and_second_config_entry_keep_one_resource_and_one_static_route():
    async def scenario():
        collection = FakeCollection()
        hass = FakeHass(collection)

        await frontend.async_setup_frontend(hass)
        await frontend.async_setup_frontend(hass)

        assert len(collection.items) == 1
        assert len(collection.creates) == 1
        assert len(hass.http.calls) == 1

    asyncio.run(scenario())


def test_restart_simulation_keeps_one_current_resource():
    async def scenario():
        collection = FakeCollection()
        first_hass = FakeHass(collection)
        await frontend.async_setup_frontend(first_hass)

        restarted_hass = FakeHass(collection)
        await frontend.async_setup_frontend(restarted_hass)

        assert len(collection.items) == 1
        assert len(collection.creates) == 1
        assert collection.updates == []

    asyncio.run(scenario())


def test_yaml_mode_does_not_write_and_backend_facing_call_returns_normally():
    async def scenario():
        hass = FakeHass(None)
        hass.data["lovelace"].mode = "yaml"

        state = await frontend.async_setup_frontend(hass)

        assert state["resource_result"] == {"status": "yaml_mode", "changed": False}
        assert state["resource_complete"] is True

    asyncio.run(scenario())


def test_collection_not_ready_defers_once_then_reconciles_after_started():
    async def scenario():
        hass = FakeHass()

        first = await frontend.async_setup_frontend(hass)
        await frontend.async_setup_frontend(hass)

        assert first["resource_result"]["status"] == "deferred_until_started"
        assert len(hass.bus.listeners) == 1

        collection = FakeCollection()
        hass.data["lovelace"] = SimpleNamespace(resources=collection)
        hass.bus.fire()
        await asyncio.gather(*hass.tasks)

        assert len(collection.items) == 1
        assert hass.data[frontend.FRONTEND_DATA_KEY]["resource_result"]["status"] == "created"

    asyncio.run(scenario())


def test_unrelated_resources_remain_semantically_unchanged():
    async def scenario():
        unrelated = [
            resource("weather", "/hacsfiles/weather-radar-card/weather-radar-card.js"),
            resource("other-deye", "/local/deye-dashboard-card.js"),
        ]
        collection = FakeCollection(unrelated)
        hass = FakeHass(collection)

        await frontend.async_setup_frontend(hass)

        assert collection.items[:2] == unrelated
        assert len(collection.items) == 3
        assert collection.deletes == []

    asyncio.run(scenario())


def test_ambiguous_owned_duplicates_fail_safe_without_update_or_delete():
    async def scenario():
        original = [
            resource("canonical", frontend.CARD_RESOURCE_URL),
            resource("legacy", "/local/deye-energy-manager-card.js?v=0.8.0.42"),
        ]
        collection = FakeCollection(original)
        hass = FakeHass(collection)

        state = await frontend.async_setup_frontend(hass)

        assert state["resource_result"]["status"] == "ambiguous_duplicates"
        assert collection.items == original
        assert collection.creates == collection.updates == collection.deletes == []

    asyncio.run(scenario())


def test_collection_and_static_failures_are_isolated():
    async def scenario():
        collection = FakeCollection(fail=True)
        hass = FakeHass(collection)
        hass.http = FakeHttp(fail=True)

        state = await frontend.async_setup_frontend(hass)
        await frontend.async_setup_frontend(hass)

        assert state["static_status"] == "error"
        assert state["static_complete"] is True
        assert state["resource_result"] == {"status": "error", "changed": False}

    asyncio.run(scenario())


def test_readiness_listener_failure_is_isolated_from_backend_setup():
    async def scenario():
        hass = FakeHass()
        hass.bus = FakeBus(fail=True)

        state = await frontend.async_setup_frontend(hass)

        assert state["static_registered"] is True
        assert state["resource_result"] == {
            "status": "setup_error",
            "changed": False,
        }

    asyncio.run(scenario())


def test_resource_ownership_requires_exact_card_basename():
    assert frontend.is_owned_resource_url(frontend.CARD_RESOURCE_URL)
    assert frontend.is_owned_resource_url("/local/deye-energy-manager-card.js?v=1")
    assert not frontend.is_owned_resource_url("/local/deye-energy-manager-card.js.bak")
    assert not frontend.is_owned_resource_url("/local/some-deye-card.js")
    assert not frontend.is_owned_resource_url("/hacsfiles/deye-inverter/card.js")


def test_revision_is_single_backend_source_and_matches_unchanged_card():
    component_card = PACKAGE / "www" / frontend.CARD_FILENAME
    public_card = ROOT / "www" / frontend.CARD_FILENAME
    assert component_card.read_bytes() == public_card.read_bytes()
    first_line = component_card.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == f"// Resource revision: v={frontend.CARD_RESOURCE_REVISION}"
    assert frontend.CARD_RESOURCE_URL == (
        "/deye_energy_manager/deye-energy-manager-card.js?v=0.8.0.44"
    )


def test_active_repository_metadata_uses_canonical_slug_only():
    old_slug = "deye-energy-manager-" + "0.7.1-main"
    canonical = "https://github.com/pasierbrg/deye-energy-manager"
    active_files = [
        ROOT / "README.md",
        ROOT / "INSTALL_PL.md",
        ROOT / "RELEASE_NOTES_0.8.0.md",
        PACKAGE / "manifest.json",
        PACKAGE / "const.py",
        PACKAGE / "tariff_catalog.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
    assert old_slug not in combined
    assert canonical in combined


def test_hacs_manifest_and_packaged_brand_assets_are_valid():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    assert hacs["name"] == manifest["name"] == "Deye Energy Manager"
    assert manifest["domain"] == "deye_energy_manager"
    assert manifest["version"] == "0.8.0"
    assert manifest["documentation"] == "https://github.com/pasierbrg/deye-energy-manager"
    assert manifest["issue_tracker"].endswith("/deye-energy-manager/issues")

    required_assets = [
        "icon.png",
        "icon@2x.png",
        "logo.png",
        "logo@2x.png",
        "dark_icon.png",
        "dark_icon@2x.png",
        "dark_logo.png",
        "dark_logo@2x.png",
    ]
    for filename in required_assets:
        packaged = PACKAGE / "brand" / filename
        repository = ROOT / "brand" / filename
        assert packaged.is_file() and packaged.stat().st_size > 0
        assert repository.is_file() and repository.stat().st_size > 0
        assert packaged.read_bytes() == repository.read_bytes()

    tracked = set(
        subprocess.run(
            ["git", "ls-files", "custom_components/deye_energy_manager/brand/**"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    assert {
        f"custom_components/deye_energy_manager/brand/{filename}"
        for filename in required_assets
    } <= tracked


def test_last_entry_unload_cancels_only_pending_readiness_callback():
    async def scenario():
        hass = FakeHass()
        await frontend.async_setup_frontend(hass)
        state = hass.data[frontend.FRONTEND_DATA_KEY]

        assert state["resource_deferred"] is True
        assert hass.bus.listeners[0][2] is True

        frontend.cancel_frontend_followup(hass)

        assert state["resource_deferred"] is False
        assert hass.bus.listeners[0][2] is False
        assert state["static_registered"] is True

    asyncio.run(scenario())

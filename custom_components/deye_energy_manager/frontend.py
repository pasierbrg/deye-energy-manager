"""Safe, domain-level frontend resource registration for Deye Energy Manager."""

from __future__ import annotations

import asyncio
import inspect
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "deye-energy-manager-card.js"
CARD_RESOURCE_REVISION = "0.8.0.44"
CARD_STATIC_ROOT = f"/{DOMAIN}"
CARD_RESOURCE_PATH = f"{CARD_STATIC_ROOT}/{CARD_FILENAME}"
CARD_RESOURCE_URL = f"{CARD_RESOURCE_PATH}?v={CARD_RESOURCE_REVISION}"

FRONTEND_DATA_KEY = f"{DOMAIN}_frontend"
LOVELACE_DATA_KEY = "lovelace"
HOMEASSISTANT_STARTED_EVENT = "homeassistant_started"

_MISSING = object()


def _frontend_state(hass: Any) -> dict[str, Any]:
    """Return state shared by all DEM config entries in one HA instance."""
    state = hass.data.setdefault(FRONTEND_DATA_KEY, {})
    state.setdefault("lock", asyncio.Lock())
    state.setdefault("static_registered", False)
    state.setdefault("static_complete", False)
    state.setdefault("resource_complete", False)
    state.setdefault("resource_deferred", False)
    return state


async def _async_maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _async_register_static_path(hass: Any, state: dict[str, Any]) -> None:
    """Register the bundled card exactly once for the HA process."""
    if state["static_complete"]:
        return

    static_path = str(Path(__file__).parent / "www")
    http = getattr(hass, "http", None)
    if http is None:
        state["static_status"] = "http_unavailable"
        state["static_complete"] = True
        _LOGGER.warning("DEM card static path was not registered: HA HTTP is unavailable")
        return

    try:
        if hasattr(http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig

            await http.async_register_static_paths(
                [StaticPathConfig(CARD_STATIC_ROOT, static_path, True)]
            )
        elif hasattr(http, "async_register_static_path"):
            await _async_maybe_await(
                http.async_register_static_path(CARD_STATIC_ROOT, static_path, True)
            )
        elif hasattr(http, "register_static_path"):
            http.register_static_path(CARD_STATIC_ROOT, static_path, True)
        else:
            state["static_status"] = "api_unavailable"
            state["static_complete"] = True
            _LOGGER.warning(
                "DEM card static path was not registered: no supported HA static-path API"
            )
            return
    except Exception:  # Frontend setup must never block the integration backend.
        state["static_status"] = "error"
        state["static_complete"] = True
        _LOGGER.exception("DEM card static path registration failed")
        return

    state["static_registered"] = True
    state["static_complete"] = True
    state["static_status"] = "registered"


def _lovelace_resources(hass: Any) -> tuple[Any | None, str]:
    """Return the loaded storage collection or a safe non-storage status."""
    lovelace = hass.data.get(LOVELACE_DATA_KEY)
    if lovelace is None:
        return None, "not_ready"

    if isinstance(lovelace, dict):
        resources = lovelace.get("resources", _MISSING)
        mode = str(lovelace.get("mode") or "").lower()
    else:
        resources = getattr(lovelace, "resources", _MISSING)
        mode = str(getattr(lovelace, "mode", "") or "").lower()

    if resources is _MISSING:
        return None, "not_ready"
    if resources is None:
        if mode == "storage":
            return None, "not_ready"
        return None, "yaml_mode"
    if not callable(getattr(resources, "async_items", None)):
        return None, "collection_unavailable"
    return resources, "storage"


def _resource_path(url: Any) -> str:
    """Normalize a Lovelace resource URL to its path without cache query."""
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        path = urlsplit(text).path
    except ValueError:
        return ""
    return "/" + path.lstrip("/")


def is_owned_resource_url(url: Any) -> bool:
    """Recognize only the canonical DEM path or the exact DEM card basename."""
    path = _resource_path(url)
    if path == CARD_RESOURCE_PATH:
        return True
    return bool(path) and path.rsplit("/", 1)[-1] == CARD_FILENAME


def _resource_type(item: dict[str, Any]) -> str:
    """Preserve the existing HA resource type during a migration/update."""
    value = str(item.get("type") or item.get("res_type") or "module").strip()
    return value or "module"


async def _async_reconcile_collection(collection: Any) -> dict[str, Any]:
    """Create or update one unambiguous DEM storage resource."""
    items = await _async_maybe_await(collection.async_items())
    if not isinstance(items, (list, tuple)):
        return {"status": "collection_invalid", "changed": False}

    owned = [item for item in items if isinstance(item, dict) and is_owned_resource_url(item.get("url"))]
    if len(owned) > 1:
        return {
            "status": "ambiguous_duplicates",
            "changed": False,
            "owned_count": len(owned),
        }

    if not owned:
        create = getattr(collection, "async_create_item", None)
        if not callable(create):
            return {"status": "create_api_unavailable", "changed": False}
        await _async_maybe_await(
            create({"url": CARD_RESOURCE_URL, "res_type": "module"})
        )
        return {"status": "created", "changed": True, "owned_count": 1}

    current = owned[0]
    if str(current.get("url") or "") == CARD_RESOURCE_URL:
        return {"status": "current", "changed": False, "owned_count": 1}

    resource_id = current.get("id")
    update = getattr(collection, "async_update_item", None)
    if resource_id in (None, "") or not callable(update):
        return {"status": "update_api_unavailable", "changed": False, "owned_count": 1}

    await _async_maybe_await(
        update(
            resource_id,
            {"url": CARD_RESOURCE_URL, "res_type": _resource_type(current)},
        )
    )
    return {"status": "updated", "changed": True, "owned_count": 1}


def _schedule_started_followup(hass: Any, state: dict[str, Any]) -> bool:
    """Schedule at most one lifecycle-based follow-up without polling or sleeps."""
    if state["resource_deferred"]:
        return True
    bus = getattr(hass, "bus", None)
    listen_once = getattr(bus, "async_listen_once", None)
    if not callable(listen_once):
        return False

    async def _followup() -> None:
        await async_reconcile_lovelace_resource(hass, allow_defer=False)

    def _started(_event: Any) -> None:
        state["resource_deferred"] = False
        state.pop("resource_unsubscribe", None)
        creator = getattr(hass, "async_create_task", None)
        coroutine = _followup()
        if callable(creator):
            creator(coroutine)
        else:
            asyncio.create_task(coroutine)

    state["resource_deferred"] = True
    state["resource_unsubscribe"] = listen_once(HOMEASSISTANT_STARTED_EVENT, _started)
    return True


def cancel_frontend_followup(hass: Any) -> None:
    """Cancel only a pending readiness callback when the last entry unloads."""
    state = hass.data.get(FRONTEND_DATA_KEY)
    if not isinstance(state, dict):
        return
    unsubscribe = state.pop("resource_unsubscribe", None)
    if callable(unsubscribe):
        unsubscribe()
    state["resource_deferred"] = False


async def async_reconcile_lovelace_resource(
    hass: Any,
    *,
    allow_defer: bool = True,
) -> dict[str, Any]:
    """Safely reconcile the DEM resource without affecting backend setup."""
    state = _frontend_state(hass)
    async with state["lock"]:
        if (
            state["resource_complete"]
            and state.get("resource_target") == CARD_RESOURCE_URL
        ):
            return dict(state.get("resource_result") or {})
        state["resource_complete"] = False

        collection, mode = _lovelace_resources(hass)
        if collection is None:
            if mode == "not_ready" and allow_defer and _schedule_started_followup(hass, state):
                result = {"status": "deferred_until_started", "changed": False}
                state["resource_result"] = result
                return dict(result)

            result = {"status": mode, "changed": False}
            state["resource_result"] = result
            state["resource_complete"] = True
            state["resource_target"] = CARD_RESOURCE_URL
            if mode == "yaml_mode":
                _LOGGER.info(
                    "DEM Lovelace resources are YAML-managed; add %s manually",
                    CARD_RESOURCE_URL,
                )
            else:
                _LOGGER.warning(
                    "DEM Lovelace resource was not changed: resource collection status is %s",
                    mode,
                )
            return dict(result)

        try:
            result = await _async_reconcile_collection(collection)
        except Exception:  # Resource failure is isolated from DEM backend setup.
            result = {"status": "error", "changed": False}
            _LOGGER.exception("DEM Lovelace resource reconciliation failed")
        else:
            if result["status"] == "ambiguous_duplicates":
                _LOGGER.warning(
                    "DEM found multiple owned Lovelace resources; no entry was changed or deleted"
                )
            elif result["status"] in {"created", "updated"}:
                _LOGGER.info("DEM Lovelace resource %s: %s", result["status"], CARD_RESOURCE_URL)

        state["resource_result"] = result
        state["resource_complete"] = True
        state["resource_target"] = CARD_RESOURCE_URL
        return dict(result)


async def async_setup_frontend(hass: Any) -> dict[str, Any]:
    """Set up the static route and storage resource for all DEM entries."""
    state = _frontend_state(hass)
    await _async_register_static_path(hass, state)
    try:
        await async_reconcile_lovelace_resource(hass)
    except Exception:  # A readiness/listener failure must not block DEM entities.
        state["resource_result"] = {"status": "setup_error", "changed": False}
        state["resource_complete"] = True
        state["resource_target"] = CARD_RESOURCE_URL
        _LOGGER.exception("DEM Lovelace resource setup failed")
    return state

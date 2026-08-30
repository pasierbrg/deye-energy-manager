"""Validated, cached tariff catalog updates for Deye Energy Manager."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .tariffs import load_bundled_catalog, validate_catalog

_LOGGER = logging.getLogger(__name__)

DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/pasierbrg/deye-energy-manager/"
    "main/custom_components/deye_energy_manager/tariff_catalog.json"
)
MAX_CATALOG_BYTES = 1_000_000
REFRESH_INTERVAL = timedelta(days=90)


class TariffCatalogManager:
    """Select the newest valid catalog and retain the last working copy."""

    def __init__(self, hass, entry_id: str, url: str | None = None) -> None:
        self.hass = hass
        self.url = str(url or DEFAULT_CATALOG_URL)
        self.store = Store(hass, 1, f"{DOMAIN}_{entry_id}_tariff_catalog")
        self.catalog: dict[str, Any] = {}
        self.source = "bundled"
        self.last_checked = ""
        self.last_updated = ""
        self.last_error = ""
        self.remote_version = ""
        self.last_result = "not_checked"

    @staticmethod
    def _version_key(value: str) -> tuple[int, ...]:
        parts: list[int] = []
        for part in str(value).replace("-", ".").split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    def _activate_if_newer(self, candidate: dict[str, Any], source: str) -> bool:
        if not isinstance(candidate, dict):
            raise ValueError("Tariff catalog payload is not an object")
        current = self._version_key(self.catalog.get("catalog_version", "0"))
        incoming = self._version_key(candidate.get("catalog_version", "0"))
        if incoming < current:
            return False
        validate_catalog(candidate)
        if incoming == current:
            return False
        self.catalog = candidate
        self.source = source
        return True

    async def async_load(self) -> None:
        executor = getattr(self.hass, "async_add_executor_job", None)
        self.catalog = (
            await executor(load_bundled_catalog)
            if callable(executor)
            else await asyncio.to_thread(load_bundled_catalog)
        )
        cached = await self.store.async_load()
        if not isinstance(cached, dict):
            return
        self.last_checked = str(cached.get("last_checked") or "")
        self.last_updated = str(cached.get("last_updated") or "")
        self.remote_version = str(cached.get("remote_version") or "")
        self.last_result = str(cached.get("last_result") or "not_checked")
        candidate = cached.get("catalog")
        if isinstance(candidate, dict):
            try:
                self._activate_if_newer(candidate, "cache")
            except ValueError as err:
                self.last_error = f"Odrzucono uszkodzony katalog w pamięci: {err}"

    def refresh_due(self, now: datetime | None = None) -> bool:
        if not self.last_checked:
            return True
        try:
            checked = datetime.fromisoformat(self.last_checked)
        except ValueError:
            return True
        current = now or datetime.now(timezone.utc)
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return current - checked >= REFRESH_INTERVAL

    async def async_refresh(self, force: bool = False) -> bool:
        if not force and not self.refresh_due():
            return False
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.last_checked = now
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            async with session.get(self.url, timeout=15) as response:
                response.raise_for_status()
                raw = await response.read()
            if len(raw) > MAX_CATALOG_BYTES:
                raise ValueError("katalog przekracza dopuszczalny rozmiar")
            candidate = json.loads(raw.decode("utf-8"))
            self.remote_version = str(candidate.get("catalog_version") or "") if isinstance(candidate, dict) else ""
            current_version = self._version_key(self.catalog.get("catalog_version", "0"))
            remote_version = self._version_key(self.remote_version)
            changed = self._activate_if_newer(candidate, "online")
            if changed:
                self.last_updated = now
                self.last_result = "updated"
            elif remote_version < current_version:
                self.last_result = "older_remote_ignored"
            else:
                self.last_result = "up_to_date"
            self.last_error = ""
        except Exception as err:  # network and validation must always fall back safely
            changed = False
            self.last_result = "error_last_known_good"
            self.last_error = f"Aktualizacja katalogu nie powiodła się: {err}"
            _LOGGER.warning("Tariff catalog refresh failed; using %s catalog: %s", self.source, err)
        await self.store.async_save({
            "last_checked": self.last_checked,
            "last_updated": self.last_updated,
            "remote_version": self.remote_version,
            "last_result": self.last_result,
            "catalog": self.catalog,
        })
        return changed

    def status(self) -> dict[str, Any]:
        validity = "unknown"
        try:
            starts = date.fromisoformat(str(self.catalog.get("effective_from")))
            ends = date.fromisoformat(str(self.catalog.get("valid_to")))
            today = date.today()
            validity = "not_yet_valid" if today < starts else "expired" if today > ends else "valid"
        except ValueError:
            validity = "invalid"
        return {
            "catalog_version": self.catalog.get("catalog_version"),
            "catalog_local_version": self.catalog.get("catalog_version"),
            "catalog_remote_version": self.remote_version,
            "catalog_generated_at": self.catalog.get("generated_at"),
            "catalog_effective_from": self.catalog.get("effective_from"),
            "catalog_valid_to": self.catalog.get("valid_to"),
            "catalog_current_validity": validity,
            "catalog_source": self.source,
            "catalog_url": self.url,
            "catalog_last_checked": self.last_checked,
            "catalog_last_updated": self.last_updated,
            "catalog_refresh_days": int(REFRESH_INTERVAL.total_seconds() / 86400),
            "catalog_update_result": self.last_result,
            "catalog_error": self.last_error,
        }

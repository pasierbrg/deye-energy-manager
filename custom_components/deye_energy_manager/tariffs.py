"""Polish distribution tariff catalog and hourly profile engine."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


CATALOG_PATH = Path(__file__).with_name("tariff_catalog.json")


def load_bundled_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        catalog = json.load(file)
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: Any) -> dict[str, Any]:
    """Validate the externally updateable catalog before it becomes active."""
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 2:
        raise ValueError("Unsupported tariff catalog schema")
    if not isinstance(catalog.get("catalog_version"), str):
        raise ValueError("Missing tariff catalog version")
    if catalog.get("currency") != "PLN" or catalog.get("vat_included") is not True:
        raise ValueError("Tariff catalog must contain gross PLN rates")
    try:
        effective_from = date.fromisoformat(str(catalog.get("effective_from")))
        valid_to = date.fromisoformat(str(catalog.get("valid_to")))
        datetime.fromisoformat(str(catalog.get("generated_at")).replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError("Invalid tariff catalog dates") from err
    if valid_to < effective_from:
        raise ValueError("Tariff catalog validity is inverted")
    common_fees = catalog.get("common_variable_fees")
    if not isinstance(common_fees, dict):
        raise ValueError("Missing common variable fees")
    for rate in common_fees.values():
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= float(rate) <= 10:
            raise ValueError("Invalid common variable fee")

    def validate_windows(windows: Any, location: str) -> None:
        if not isinstance(windows, list):
            raise ValueError(f"Invalid time windows in {location}")
        for window in windows:
            if not isinstance(window, list) or len(window) != 2:
                raise ValueError(f"Invalid time window in {location}")
            start, end = window
            if any(isinstance(value, bool) or not isinstance(value, int) for value in window):
                raise ValueError(f"Invalid time window in {location}")
            if not 0 <= start <= 23 or not 0 <= end <= 24 or start == end:
                raise ValueError(f"Invalid time window in {location}")

    def validate_zones(zones: Any, location: str, rates: dict[str, Any]) -> None:
        if not isinstance(zones, dict):
            raise ValueError(f"Invalid zones in {location}")
        for zone, windows in zones.items():
            if zone not in rates:
                raise ValueError(f"Zone {zone} has no rate in {location}")
            validate_windows(windows, location)

    providers = catalog.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("Tariff catalog has no providers")
    for provider_id, provider in providers.items():
        if not isinstance(provider_id, str) or not isinstance(provider, dict):
            raise ValueError("Invalid tariff provider")
        source = provider.get("source")
        if not isinstance(provider.get("name"), str) or not isinstance(source, str) or not (source == "manual" or source.startswith("https://")):
            raise ValueError(f"Provider {provider_id} has no trusted source")
        tariffs = provider.get("tariffs")
        if not isinstance(tariffs, dict) or not tariffs:
            raise ValueError(f"Provider {provider_id} has no tariffs")
        for plan_id, plan in tariffs.items():
            if not isinstance(plan_id, str) or not isinstance(plan, dict):
                raise ValueError(f"Invalid tariff plan for {provider_id}")
            rates = plan.get("rates")
            if not isinstance(rates, dict) or not rates:
                raise ValueError(f"Tariff {provider_id}/{plan_id} has no rates")
            for rate in rates.values():
                if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= float(rate) <= 10:
                    raise ValueError(f"Invalid rate in {provider_id}/{plan_id}")
            for zone_key in ("all_day_zone", "default_zone", "weekend_zone", "holiday_zone", "weekday_zone", "saturday_zone"):
                zone = plan.get(zone_key)
                if zone is not None and zone not in rates:
                    raise ValueError(f"Unknown {zone_key} in {provider_id}/{plan_id}")
            if "zones" in plan:
                validate_zones(plan["zones"], f"{provider_id}/{plan_id}", rates)
            for windows_key in ("weekday_windows", "saturday_windows"):
                if windows_key in plan:
                    validate_windows(plan[windows_key], f"{provider_id}/{plan_id}/{windows_key}")
            for season_name, season in plan.get("seasons", {}).items():
                if not isinstance(season, dict) or not isinstance(season.get("months"), list):
                    raise ValueError(f"Invalid season in {provider_id}/{plan_id}")
                season_rates = {**rates, **season.get("rates", {})}
                if "zones" in season:
                    validate_zones(season["zones"], f"{provider_id}/{plan_id}/{season_name}", season_rates)
            for month, zones in plan.get("month_zones", {}).items():
                if str(month) not in {str(value) for value in range(1, 13)}:
                    raise ValueError(f"Invalid month in {provider_id}/{plan_id}")
                validate_zones(zones, f"{provider_id}/{plan_id}/month-{month}", rates)
            if plan.get("effective_from"):
                try:
                    date.fromisoformat(str(plan["effective_from"]))
                except ValueError as err:
                    raise ValueError(f"Invalid effective date in {provider_id}/{plan_id}") from err
    support_statuses = {
        "SUPPORTED_TARIFF_BUY",
        "SUPPORTED_SPECIAL_PRICE_LIST",
        "DYNAMIC_EXTERNAL_SIGNAL_REQUIRED",
        "OSD_ONLY_NO_STANDARD_SELLER_TARIFF",
        "UNKNOWN_REQUIRES_RESEARCH",
    }
    seller_tariffs = catalog.get("seller_tariffs")
    if not isinstance(seller_tariffs, dict) or not seller_tariffs:
        raise ValueError("Tariff catalog has no seller tariffs")
    indexed_seller_tariffs: dict[str, tuple[str, dict[str, Any]]] = {}
    overlap_groups: dict[tuple[str, str, str, str], list[tuple[date, date, str]]] = {}
    required_entry_fields = {
        "seller_id", "seller_name", "tariff_group", "product_variant", "price_list_id",
        "valid_from", "valid_to", "currency", "unit", "price_basis", "includes_vat",
        "includes_excise", "includes_distribution", "economic_role", "rates",
        "schedule_source", "source_authority", "source_title", "source_url",
        "source_effective_date", "source_checked_at", "revision",
    }
    for seller_id, seller in seller_tariffs.items():
        if not isinstance(seller_id, str) or not isinstance(seller, dict):
            raise ValueError("Invalid seller catalog entry")
        if not isinstance(seller.get("seller_name"), str) or not str(seller.get("source") or "").startswith("https://"):
            raise ValueError(f"Seller {seller_id} has no trusted source")
        entries = seller.get("tariffs")
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"Seller {seller_id} has no tariffs")
        for tariff_id, entry in entries.items():
            location = f"{seller_id}/{tariff_id}"
            if not isinstance(tariff_id, str) or not isinstance(entry, dict):
                raise ValueError(f"Invalid seller tariff {location}")
            if required_entry_fields - set(entry):
                raise ValueError(f"Seller tariff {location} is incomplete")
            if tariff_id in indexed_seller_tariffs:
                raise ValueError(f"Duplicate seller tariff id {tariff_id}")
            if entry.get("seller_id") != seller_id or entry.get("seller_name") != seller.get("seller_name"):
                raise ValueError(f"Seller identity mismatch in {location}")
            if entry.get("currency") != "PLN" or entry.get("unit") != "PLN/kWh":
                raise ValueError(f"Unsupported seller price unit in {location}")
            if entry.get("price_basis") != "gross" or entry.get("includes_vat") is not True or entry.get("includes_excise") is not True:
                raise ValueError(f"Seller tariff {location} must contain gross prices with VAT and excise")
            if entry.get("includes_distribution") is not False or entry.get("economic_role") != "energy_only":
                raise ValueError(f"Seller tariff {location} must be energy-only")
            if entry.get("schedule_source") not in {"osd_same_tariff", "own_schedule"}:
                raise ValueError(f"Unknown seller schedule source in {location}")
            if not str(entry.get("source_url") or "").startswith("https://"):
                raise ValueError(f"Seller tariff {location} has no official source")
            for metadata_key in (
                "seller_name", "tariff_group", "product_variant", "price_list_id",
                "source_authority", "source_title", "revision",
            ):
                if not isinstance(entry.get(metadata_key), str) or not str(entry.get(metadata_key)).strip():
                    raise ValueError(f"Seller tariff {location} has invalid {metadata_key}")
            try:
                starts = date.fromisoformat(str(entry["valid_from"]))
                ends = date.fromisoformat(str(entry["valid_to"]))
                date.fromisoformat(str(entry["source_effective_date"]))
                date.fromisoformat(str(entry["source_checked_at"]))
            except ValueError as err:
                raise ValueError(f"Invalid seller validity in {location}") from err
            if ends < starts:
                raise ValueError(f"Inverted seller validity in {location}")
            rates = entry.get("rates")
            if not isinstance(rates, dict) or not rates:
                raise ValueError(f"Seller tariff {location} has no rates")
            for rate in rates.values():
                if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 < float(rate) <= 10:
                    raise ValueError(f"Invalid seller rate in {location}")
            applicable = entry.get("applicable_osd")
            if not isinstance(applicable, list) or not applicable or any(item not in providers for item in applicable):
                raise ValueError(f"Invalid OSD scope in {location}")
            if entry.get("schedule_source") == "own_schedule":
                if "all_day_zone" in entry and entry["all_day_zone"] not in rates:
                    raise ValueError(f"Unknown all-day seller zone in {location}")
                if "zones" in entry:
                    validate_zones(entry["zones"], location, rates)
            else:
                for provider_id in applicable:
                    osd_plan = providers.get(provider_id, {}).get("tariffs", {}).get(entry.get("tariff_group"))
                    if not isinstance(osd_plan, dict):
                        raise ValueError(f"Seller tariff {location} has no matching OSD tariff")
                    missing_zones = set(osd_plan.get("rates", {})) - set(rates)
                    if missing_zones:
                        raise ValueError(
                            f"Seller tariff {location} misses OSD schedule zones: {sorted(missing_zones)}"
                        )
            indexed_seller_tariffs[tariff_id] = (seller_id, entry)
            for provider_id in applicable:
                key = (seller_id, str(entry["tariff_group"]), provider_id, str(entry["product_variant"]))
                overlap_groups.setdefault(key, []).append((starts, ends, tariff_id))
    for key, intervals in overlap_groups.items():
        ordered = sorted(intervals)
        latest_end: date | None = None
        for starts, ends, _tariff_id in ordered:
            if latest_end is not None and starts <= latest_end:
                raise ValueError(f"Overlapping seller tariff validity for {'/'.join(key)}")
            latest_end = ends if latest_end is None else max(latest_end, ends)

    matrix = catalog.get("seller_support_matrix")
    if not isinstance(matrix, dict):
        raise ValueError("Tariff catalog has no seller support matrix")
    if set(matrix) != set(providers):
        raise ValueError("Seller support matrix does not cover every OSD")
    for provider_id, provider in providers.items():
        rows = matrix.get(provider_id)
        tariffs = provider.get("tariffs", {})
        if not isinstance(rows, dict) or set(rows) != set(tariffs):
            raise ValueError(f"Seller support matrix is incomplete for {provider_id}")
        for plan_id, row in rows.items():
            location = f"{provider_id}/{plan_id}"
            if not isinstance(row, dict) or row.get("status") not in support_statuses:
                raise ValueError(f"Invalid seller support status for {location}")
            seller_id = str(row.get("suggested_seller_id") or "")
            if seller_id and seller_id not in seller_tariffs:
                raise ValueError(f"Unknown suggested seller for {location}")
            tariff_id = str(row.get("seller_tariff_id") or "")
            if row.get("status") == "SUPPORTED_TARIFF_BUY" and not tariff_id:
                raise ValueError(f"Supported seller tariff missing for {location}")
            if tariff_id:
                indexed = indexed_seller_tariffs.get(tariff_id)
                if indexed is None:
                    raise ValueError(f"Unknown seller tariff {tariff_id} for {location}")
                indexed_seller, entry = indexed
                if indexed_seller != seller_id or provider_id not in entry.get("applicable_osd", []):
                    raise ValueError(f"Seller tariff scope mismatch for {location}")
                if str(entry.get("tariff_group")) != plan_id:
                    raise ValueError(f"Seller tariff group mismatch for {location}")
    return catalog


def catalog_labels(catalog: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    source = catalog or load_bundled_catalog()
    providers = {
        key: str(value.get("name") or key)
        for key, value in source.get("providers", {}).items()
    }
    tariffs: dict[str, str] = {"custom": "Profil własny"}
    for provider in source.get("providers", {}).values():
        for key, value in provider.get("tariffs", {}).items():
            tariffs.setdefault(key, str(value.get("name") or key.upper()))
    return providers, tariffs


_BUNDLED: dict[str, Any] | None = None
# Labels are resolved from the asynchronously loaded runtime catalog.  Keeping
# import-time constants empty avoids opening tariff_catalog.json on HA's event
# loop while preserving backward-compatible names for external imports.
PROVIDER_LABELS: dict[str, str] = {}
TARIFF_LABELS: dict[str, str] = {"custom": "Profil własny"}


def bundled_catalog_cached() -> dict[str, Any]:
    """Load once for synchronous non-HA callers; HA startup uses an executor."""
    global _BUNDLED
    if _BUNDLED is None:
        _BUNDLED = load_bundled_catalog()
    return _BUNDLED


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    length = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * length) // 451
    month = (h + length - 7 * m + 114) // 31
    day = ((h + length - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def polish_holidays(year: int) -> set[date]:
    easter = _easter_sunday(year)
    fixed = {
        date(year, 1, 1), date(year, 1, 6), date(year, 5, 1),
        date(year, 5, 3), date(year, 8, 15), date(year, 11, 1),
        date(year, 11, 11), date(year, 12, 24), date(year, 12, 25),
        date(year, 12, 26),
    }
    return fixed | {
        easter,
        easter + timedelta(days=1),
        easter + timedelta(days=49),
        easter + timedelta(days=60),
    }


def is_polish_holiday(day: date) -> bool:
    return day in polish_holidays(day.year)


def tariff_season(day: date) -> str:
    return "summer" if 4 <= day.month <= 9 else "winter"


def day_type(moment: datetime) -> str:
    if is_polish_holiday(moment.date()):
        return "holiday"
    if moment.weekday() >= 5:
        return "weekend"
    return "workday"


def parse_windows(value: str | Iterable[tuple[int, int]] | None) -> list[tuple[int, int]]:
    if not value:
        return []
    if not isinstance(value, str):
        return [(max(0, int(start)), min(24, int(end))) for start, end in value]
    windows: list[tuple[int, int]] = []
    for item in value.split(","):
        if "-" not in item:
            continue
        raw_start, raw_end = item.strip().split("-", 1)
        try:
            start = int(raw_start.split(":", 1)[0])
            end = int(raw_end.split(":", 1)[0])
        except (TypeError, ValueError):
            continue
        if 0 <= start <= 23 and 0 <= end <= 24 and start != end:
            windows.append((start, end))
    return windows


def hour_in_windows(hour: int, windows: Iterable[tuple[int, int]]) -> bool:
    hour = int(hour) % 24
    for start, end in windows:
        if start < end and start <= hour < end:
            return True
        if start > end and (hour >= start or hour < end):
            return True
    return False


def get_tariff(catalog: dict[str, Any], provider: str, plan: str) -> dict[str, Any] | None:
    return catalog.get("providers", {}).get(provider, {}).get("tariffs", {}).get(plan)


def tariff_availability(plan: dict[str, Any], on_date: date | None = None) -> tuple[bool, str]:
    """Tell the UI and optimizer whether a catalog plan can be used safely."""
    if plan.get("requires_dynamic_signal"):
        return False, "wymaga osobnego sygnału stref dynamicznych"
    effective_from = plan.get("effective_from")
    if effective_from:
        try:
            effective_day = date.fromisoformat(str(effective_from))
        except ValueError:
            return False, "ma nieprawidłową datę obowiązywania"
        if effective_day > (on_date or date.today()):
            return False, f"obowiązuje od {effective_day.isoformat()}"
    return True, ""


def available_tariffs(catalog: dict[str, Any], provider: str) -> list[dict[str, Any]]:
    tariffs = catalog.get("providers", {}).get(provider, {}).get("tariffs", {})
    result: list[dict[str, Any]] = []
    for key, value in tariffs.items():
        available, reason = tariff_availability(value)
        result.append({
            "id": key,
            "name": str(value.get("name") or key.upper()),
            "available": available,
            "unavailable_reason": reason,
        })
    return result


def seller_support_entry(
    catalog: dict[str, Any],
    provider: str,
    plan: str,
) -> dict[str, Any]:
    """Return the audited OSD/seller relation without inferring a selection."""
    row = catalog.get("seller_support_matrix", {}).get(provider, {}).get(plan)
    if not isinstance(row, dict):
        return {
            "status": "UNKNOWN_REQUIRES_RESEARCH",
            "suggested_seller_id": "",
            "seller_tariff_id": "",
            "reason": "Brak zweryfikowanej relacji OSD–sprzedawca w katalogu.",
        }
    return dict(row)


def seller_catalog_options(catalog: dict[str, Any]) -> list[dict[str, str]]:
    """Return names only; the simple UI must not expose tariff internals."""
    return [
        {"id": str(seller_id), "name": str(seller.get("seller_name") or seller_id)}
        for seller_id, seller in catalog.get("seller_tariffs", {}).items()
        if isinstance(seller_id, str) and isinstance(seller, dict)
    ]


def _seller_entry_valid_on(entry: dict[str, Any], on_date: date) -> bool:
    try:
        return date.fromisoformat(str(entry.get("valid_from"))) <= on_date <= date.fromisoformat(
            str(entry.get("valid_to"))
        )
    except ValueError:
        return False


def seller_tariff_options(
    catalog: dict[str, Any],
    seller_id: str,
    provider: str,
    plan: str,
    on_date: date,
) -> list[dict[str, str]]:
    """Return valid, exact-scope products for an explicitly chosen seller."""
    seller = catalog.get("seller_tariffs", {}).get(seller_id, {})
    result: list[dict[str, str]] = []
    for tariff_id, entry in seller.get("tariffs", {}).items():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("tariff_group") or "") != plan:
            continue
        if provider not in entry.get("applicable_osd", []):
            continue
        if not _seller_entry_valid_on(entry, on_date):
            continue
        result.append({
            "id": str(tariff_id),
            "name": str(entry.get("product_variant") or entry.get("price_list_id") or tariff_id),
        })
    return sorted(result, key=lambda item: (item["name"], item["id"]))


def resolve_seller_tariff(
    catalog: dict[str, Any],
    seller_id: str,
    seller_tariff_id: str,
    provider: str,
    plan: str,
    on_date: date,
) -> tuple[str, dict[str, Any] | None, str]:
    """Resolve only an explicit seller and never fall back to an expired price."""
    if not seller_id:
        return "", None, "seller_not_selected"
    seller = catalog.get("seller_tariffs", {}).get(seller_id)
    if not isinstance(seller, dict):
        return "", None, "unknown_seller"
    tariffs = seller.get("tariffs", {})
    if not isinstance(tariffs, dict):
        return "", None, "seller_catalog_unavailable"

    scoped = {
        str(tariff_id): entry
        for tariff_id, entry in tariffs.items()
        if isinstance(entry, dict)
        and str(entry.get("tariff_group") or "") == plan
        and provider in entry.get("applicable_osd", [])
    }
    valid = {
        tariff_id: entry
        for tariff_id, entry in scoped.items()
        if _seller_entry_valid_on(entry, on_date)
    }
    selected = scoped.get(seller_tariff_id) if seller_tariff_id else None
    if selected is not None and _seller_entry_valid_on(selected, on_date):
        return seller_tariff_id, selected, "ready"
    if selected is not None:
        # A catalog update may replace a dated price list. Transition is safe only
        # within the exact same seller/product/group/OSD tuple and only when unique.
        variant = str(selected.get("product_variant") or "")
        replacements = [
            (tariff_id, entry)
            for tariff_id, entry in valid.items()
            if str(entry.get("product_variant") or "") == variant
        ]
        if len(replacements) == 1:
            tariff_id, entry = replacements[0]
            return tariff_id, entry, "validity_transition"
        return "", None, "selected_tariff_expired"
    if seller_tariff_id:
        return "", None, "unknown_seller_tariff"
    if len(valid) == 1:
        tariff_id, entry = next(iter(valid.items()))
        return tariff_id, entry, "unique_valid_tariff"
    if not valid:
        return "", None, "no_valid_standard_tariff"
    return "", None, "ambiguous_seller_tariff"


def _seller_price_for_zone(
    entry: dict[str, Any],
    moment: datetime,
    osd_zone: str,
) -> tuple[str, float | None]:
    if entry.get("schedule_source") == "osd_same_tariff":
        zone = osd_zone
    else:
        rule = _active_rule(entry, moment)
        zone = str(rule.get("all_day_zone") or rule.get("default_zone") or "")
        if not rule.get("all_day_zone"):
            kind = day_type(moment)
            if kind == "holiday" and rule.get("holiday_zone"):
                zone = str(rule["holiday_zone"])
            elif kind == "weekend" and rule.get("weekend_zone"):
                zone = str(rule["weekend_zone"])
            for candidate_zone, windows in rule.get("zones", {}).items():
                if hour_in_windows(moment.hour, windows):
                    zone = str(candidate_zone)
                    break
    raw = entry.get("rates", {}).get(zone)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return zone, None
    return zone, float(raw)


def seller_catalog_canonical_buy(
    reference: datetime,
    catalog: dict[str, Any],
    seller_id: str,
    seller_tariff_id: str,
    provider: str,
    plan: str,
    distribution_by_slot: dict[tuple[date, int], float],
) -> dict[str, Any]:
    """Build 24+24 gross BUY rows from a selected seller plus OSD exactly once."""
    rows: list[dict[str, Any]] = []
    start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    resolved_ids: set[str] = set()
    resolver_statuses: set[str] = set()
    failure = ""
    for offset in range(48):
        moment = start + timedelta(hours=offset)
        tariff_id, entry, resolver_status = resolve_seller_tariff(
            catalog, seller_id, seller_tariff_id, provider, plan, moment.date()
        )
        resolver_statuses.add(resolver_status)
        if entry is None:
            failure = resolver_status
            break
        slot_key = (moment.date(), moment.hour)
        if slot_key not in distribution_by_slot:
            failure = "distribution_slot_unavailable"
            break
        osd_row = catalog_tariff_row(moment, catalog, provider, plan)
        seller_zone, source_price = _seller_price_for_zone(entry, moment, str(osd_row.get("zone") or ""))
        if source_price is None:
            failure = f"seller_rate_unavailable:{seller_zone or 'unknown'}"
            break
        distribution = max(0.0, float(distribution_by_slot[slot_key]))
        resolved_ids.add(tariff_id)
        rows.append({
            "date": moment.date().isoformat(),
            "day": "today" if offset < 24 else "tomorrow",
            "hour": moment.hour,
            "direction": "buy",
            "source_adapter": "seller_catalog",
            "source_price_pln_kwh": round(source_price, 10),
            "energy_component": round(source_price, 10),
            "added_distribution": round(distribution, 10),
            "added_vat": 0.0,
            "added_other_variable": 0.0,
            "final_price_pln_kwh": round(source_price + distribution, 10),
            "coverage_minutes": 60.0,
            "source_unit": "PLN/kWh",
            "source_basis": "gross",
            "source_semantic_scope": "energy_only",
            "source_economic_role": "energy_only",
            "source_metadata": {
                "seller_id": seller_id,
                "seller_tariff_id": tariff_id,
                "seller_zone": seller_zone,
                "osd_provider": provider,
                "osd_tariff": plan,
                "osd_zone": osd_row.get("zone"),
            },
            "quality": "ready",
            "status": "ready",
        })
    if failure:
        rows = []
    ready = len(rows) == 48
    status = "ready" if ready else failure or "incomplete"
    day_status = {
        name: "ready" if ready else status
        for name in ("today", "tomorrow")
    }
    resolver = {
        name: {
            "status": "seller_catalog" if ready else status,
            "resolved_schema": "seller_catalog_v1",
            "mapped_entity": "",
            "resolved_entity": "",
            "stable_identity_status": "catalog" if ready else "unbound",
            "detected_adapter": "seller_catalog",
            "list_attribute": "",
            "value_field": "",
            "unit": "PLN/kWh",
            "economic_role": "energy_only",
            "semantic_scope": "energy_only",
            "coverage_hours": 24 if ready else 0,
            "reason": "" if ready else status,
            "seller_id": seller_id,
            "seller_tariff_ids": sorted(resolved_ids),
        }
        for name in ("today", "tomorrow")
    }
    return {
        "schema_version": 1,
        "direction": "buy",
        "contract": {
            "direction": "buy",
            "source_adapter": "seller_catalog",
            "today_entity": "",
            "tomorrow_entity": "",
            "seller_id": seller_id,
            "seller_tariff_id": seller_tariff_id,
            "resolved_seller_tariff_ids": sorted(resolved_ids),
            "price_basis": "gross",
            "unit": "PLN/kWh",
            "economic_role": "energy_only",
            "semantic_scope": "energy_only",
            "includes_distribution_variable": False,
            "includes_vat": True,
            "includes_excise": True,
        },
        "rows": rows,
        "diagnostics": {
            "status": status,
            "day_status": day_status,
            "coverage_today": 24 if ready else 0,
            "coverage_tomorrow": 24 if ready else 0,
            "partial_hours": [],
            "invalid_hours": [],
            "resolver": resolver,
            "resolver_statuses": sorted(resolver_statuses),
        },
        "source_statuses": ["ready", "ready"] if ready else [status, status],
    }


def _active_rule(plan: dict[str, Any], moment: datetime) -> dict[str, Any]:
    rule: dict[str, Any] = plan
    for candidate in plan.get("seasons", {}).values():
        if moment.month in candidate.get("months", []):
            rule = {**plan, **candidate, "rates": {**plan.get("rates", {}), **candidate.get("rates", {})}}
            break
    month_rule = plan.get("month_zones", {}).get(str(moment.month))
    if isinstance(month_rule, dict):
        rule = {**plan, "zones": month_rule}
    if moment.weekday() >= 5:
        weekend_rates = plan.get("weekend_rates", {}).get(tariff_season(moment.date()))
        if isinstance(weekend_rates, dict):
            rule = {**rule, "rates": weekend_rates}
    return rule


def catalog_tariff_row(
    moment: datetime,
    catalog: dict[str, Any],
    provider: str,
    plan_id: str,
) -> dict[str, Any]:
    plan = get_tariff(catalog, provider, plan_id)
    if plan is None:
        raise ValueError(f"Unknown tariff {provider}/{plan_id}")
    kind = day_type(moment)
    season = tariff_season(moment.date())
    if plan.get("requires_dynamic_signal"):
        zone = "dynamic_unavailable"
        rate = 0.0
    elif plan.get("all_day_zone"):
        zone = str(plan["all_day_zone"])
        rate = float(plan.get("rates", {}).get(zone, 0.0))
    else:
        rule = _active_rule(plan, moment)
        zone = str(rule.get("default_zone") or plan.get("default_zone") or "peak")
        if kind == "holiday" and plan.get("holiday_zone"):
            zone = str(plan["holiday_zone"])
        elif kind == "weekend" and plan.get("weekend_zone"):
            zone = str(plan["weekend_zone"])
        else:
            if moment.weekday() == 5 and plan.get("saturday_zone"):
                zone = str(plan.get("default_zone") or zone)
                if hour_in_windows(moment.hour, plan.get("saturday_windows", [])):
                    zone = str(plan["saturday_zone"])
            if moment.weekday() < 5 and plan.get("weekday_zone"):
                zone = str(plan.get("default_zone") or zone)
                if hour_in_windows(moment.hour, plan.get("weekday_windows", [])):
                    zone = str(plan["weekday_zone"])
            windows = rule.get("zones", plan.get("zones", {}))
            for candidate_zone, candidate_windows in windows.items():
                if hour_in_windows(moment.hour, candidate_windows):
                    zone = str(candidate_zone)
                    break
        rates = rule.get("rates", plan.get("rates", {}))
        rate = float(rates.get(zone, plan.get("rates", {}).get(zone, 0.0)))
    common = catalog.get("common_variable_fees", {})
    common_rate = sum(float(value) for value in common.values() if isinstance(value, (int, float)))
    return {
        "date": moment.date().isoformat(),
        "hour": moment.hour,
        "label": f"{moment.hour:02d}:00-{(moment.hour + 1) % 24:02d}:00",
        "zone": zone,
        "rate": round(max(0.0, rate), 4),
        "common_rate": round(common_rate, 5),
        "total_distribution_rate": round(max(0.0, rate + common_rate), 5),
        "day_type": kind,
        "weekend": moment.weekday() >= 5,
        "holiday": is_polish_holiday(moment.date()),
        "season": season,
    }


def catalog_hourly_profile(
    moment: datetime,
    catalog: dict[str, Any],
    provider: str,
    plan: str,
    hours: int = 48,
) -> list[dict[str, Any]]:
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return [catalog_tariff_row(start + timedelta(hours=offset), catalog, provider, plan) for offset in range(hours)]


def tariff_zone(
    moment: datetime,
    plan: str,
    custom_windows: str | None = None,
    provider: str = "other",
) -> str:
    """Backward-compatible two-zone helper used by earlier tests and migrations."""
    normalized_plan = str(plan).lower()
    if normalized_plan == "custom":
        return "offpeak" if hour_in_windows(moment.hour, parse_windows(custom_windows)) else "peak"
    catalog = bundled_catalog_cached()
    if get_tariff(catalog, provider, plan):
        return catalog_tariff_row(moment, catalog, provider, plan)["zone"]
    if normalized_plan == "g11":
        return "all_day"
    if normalized_plan == "g12w" and (moment.weekday() >= 5 or is_polish_holiday(moment.date())):
        return "offpeak"
    return "offpeak" if hour_in_windows(moment.hour, parse_windows(custom_windows)) else "peak"


def hourly_tariff_profile(
    moment: datetime,
    plan: str,
    peak_rate: float,
    offpeak_rate: float,
    custom_windows: str | None = None,
    provider: str = "other",
) -> list[dict[str, Any]]:
    """Backward-compatible manually priced 24-hour profile."""
    profile: list[dict[str, Any]] = []
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    for hour in range(24):
        current = start + timedelta(hours=hour)
        zone = tariff_zone(current, plan, custom_windows, provider)
        rate = peak_rate if zone in ("all_day", "peak") else offpeak_rate
        profile.append({
            "date": current.date().isoformat(),
            "hour": hour,
            "label": f"{hour:02d}:00-{(hour + 1) % 24:02d}:00",
            "zone": zone,
            "rate": round(max(0.0, float(rate)), 4),
            "day_type": day_type(current),
            "weekend": current.weekday() >= 5,
            "holiday": is_polish_holiday(current.date()),
            "season": tariff_season(current.date()),
        })
    return profile

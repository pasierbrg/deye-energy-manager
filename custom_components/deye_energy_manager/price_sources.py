"""Canonical energy-price source contracts and interval aggregation.

This module is deliberately Home-Assistant independent.  The runtime supplies
plain state snapshots and receives deterministic, JSON-serialisable rows which
are shared by Optimizer Core and the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import math
import re
from typing import Any, Iterable


PRICE_CONTRACT_VERSION = 1
SUPPORTED_UNITS = {"PLN/kWh", "PLN/MWh"}
SUPPORTED_BASES = {"gross", "net"}
SUPPORTED_SCOPES = {"all_in_variable", "energy_only", "partial"}
SUPPORTED_ADAPTERS = {"pstryk", "rce_pse", "generic", "custom"}
SUPPORTED_ECONOMIC_ROLES = {
    "retail_buy_all_in",
    "energy_only",
    "market_reference",
    "prosumer_sell",
    "custom",
}

_DAY_SOURCE_FIELDS = (
    "source_adapter",
    "economic_role",
    "semantic_scope",
    "includes_distribution_variable",
    "price_basis",
    "includes_excise",
    "includes_service_margin",
    "unit",
    "granularity",
    "current_price_only",
    "list_attribute",
    "today_list_attribute",
    "tomorrow_list_attribute",
    "value_field",
    "start_field",
    "end_field",
    "period_field",
    "timestamp_field",
    "timestamp_role",
    "business_date_field",
    "missing_policy",
    "vat_rate",
    "allow_state_fallback",
)


@dataclass(frozen=True)
class PriceInterval:
    start: datetime
    end: datetime
    price_pln_kwh: float
    entity_id: str
    source_index: int


def _tri_state(value: Any) -> bool | str:
    return value if isinstance(value, bool) else "unknown"


def _text_choice(value: Any, allowed: set[str], fallback: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in allowed else fallback


def detect_source_adapter(
    entity_id: str | None,
    *,
    platform: str | None = None,
    config_entry_domain: str | None = None,
    device_metadata: str | None = None,
    explicit: str | None = None,
) -> str:
    """Detect a known adapter from stable integration metadata.

    Entity identifiers are intentionally the final, weak hint because users
    can rename them.  An explicit saved override always wins.
    """
    if explicit in SUPPORTED_ADAPTERS:
        return str(explicit)
    metadata = " ".join(
        str(value or "").lower()
        for value in (platform, config_entry_domain, device_metadata)
    )
    if "pstryk" in metadata:
        return "pstryk"
    if "rce_pse" in metadata or "ha-rce-pse" in metadata or "lewa_reka_rce" in metadata:
        return "rce_pse"
    # An entity_id may be renamed or deliberately mimic another integration.
    # It is diagnostic-only and never binds a provider adapter.
    return "generic"


def default_price_contract(
    direction: str,
    adapter: str,
    today_entity: str | None,
    tomorrow_entity: str | None,
    *,
    legacy_includes_distribution: bool | None = None,
) -> dict[str, Any]:
    """Return a complete versioned contract with fail-closed defaults."""
    direction = "sell" if direction == "sell" else "buy"
    adapter = _text_choice(adapter, SUPPORTED_ADAPTERS, "generic")
    contract: dict[str, Any] = {
        "version": PRICE_CONTRACT_VERSION,
        "direction": direction,
        "source_adapter": adapter,
        "economic_role": "",
        "semantic_scope": "partial",
        "includes_distribution_variable": "unknown",
        "price_basis": "unknown",
        "includes_excise": "unknown",
        "includes_service_margin": "unknown",
        "unit": "unknown",
        "granularity": "unknown",
        "current_price_only": False,
        "today_entity": today_entity or "",
        "tomorrow_entity": tomorrow_entity or "",
        "resolved_today_entity": today_entity or "",
        "resolved_tomorrow_entity": tomorrow_entity or "",
        "stable_identity_today_status": "unbound",
        "stable_identity_tomorrow_status": "unbound",
        "today_binding": {},
        "tomorrow_binding": {},
        "resolved_schema_today": {},
        "resolved_schema_tomorrow": {},
        "list_attribute": "prices",
        "today_list_attribute": "",
        "tomorrow_list_attribute": "",
        "value_field": "price",
        "start_field": "start",
        "end_field": "end",
        "period_field": "period",
        "timestamp_field": "datetime",
        "timestamp_role": "start",
        "business_date_field": "",
        "missing_policy": "fail_closed",
        "vat_rate": None,
        "allow_state_fallback": direction == "buy",
    }
    if adapter == "pstryk":
        contract.update({
            "economic_role": "retail_buy_all_in" if direction == "buy" else "prosumer_sell",
            "semantic_scope": "all_in_variable",
            "includes_distribution_variable": True,
            "price_basis": "gross",
            "includes_excise": True,
            "includes_service_margin": True,
            "unit": "PLN/kWh",
            "granularity": "60m",
            "today_list_attribute": "today_prices",
            "tomorrow_list_attribute": "tomorrow_prices",
            "value_field": "price",
            "start_field": "start",
            "end_field": "end",
            "allow_state_fallback": False,
        })
    elif adapter == "rce_pse":
        contract.update({
            "economic_role": "energy_only" if direction == "buy" else "market_reference",
            "semantic_scope": "energy_only",
            "includes_distribution_variable": False,
            "includes_excise": False,
            "includes_service_margin": False,
            # rce_pln is the provider's ready-to-use PLN/kWh energy component.
            # This is adapter-owned metadata, never inherited from Pstryk.
            "price_basis": "gross",
            "unit": "PLN/kWh",
            "granularity": "15m",
            "value_field": "rce_pln",
            "period_field": "period",
            "timestamp_field": "dtime",
            "timestamp_role": "end",
            "business_date_field": "business_date",
            "allow_state_fallback": False,
        })
    elif direction == "buy" and legacy_includes_distribution is not None:
        contract.update({
            "semantic_scope": "all_in_variable" if legacy_includes_distribution else "energy_only",
            "includes_distribution_variable": bool(legacy_includes_distribution),
        })
    return contract


def normalize_price_contract(
    value: Any,
    direction: str,
    adapter: str,
    today_entity: str | None,
    tomorrow_entity: str | None,
    *,
    legacy_includes_distribution: bool | None = None,
) -> dict[str, Any]:
    """Overlay an explicit contract on safe adapter defaults."""
    explicit = value if isinstance(value, dict) else {}
    selected_adapter = _text_choice(explicit.get("source_adapter", adapter), SUPPORTED_ADAPTERS, adapter)
    result = default_price_contract(
        direction,
        selected_adapter,
        today_entity,
        tomorrow_entity,
        legacy_includes_distribution=legacy_includes_distribution,
    )
    for key in result:
        if key in explicit:
            result[key] = explicit[key]
    result["version"] = PRICE_CONTRACT_VERSION
    result["direction"] = "sell" if direction == "sell" else "buy"
    result["source_adapter"] = _text_choice(result.get("source_adapter"), SUPPORTED_ADAPTERS, selected_adapter)
    result["economic_role"] = _text_choice(
        result.get("economic_role"), SUPPORTED_ECONOMIC_ROLES, ""
    )
    result["semantic_scope"] = _text_choice(result.get("semantic_scope"), SUPPORTED_SCOPES, "partial")
    result["price_basis"] = _text_choice(result.get("price_basis"), SUPPORTED_BASES, "unknown")
    result["unit"] = _text_choice(result.get("unit"), SUPPORTED_UNITS, "unknown")
    result["granularity"] = _text_choice(
        result.get("granularity"), {"15m", "60m", "timestamp_series"}, "unknown"
    )
    result["timestamp_role"] = _text_choice(result.get("timestamp_role"), {"start", "end"}, "start")
    result["includes_distribution_variable"] = _tri_state(result.get("includes_distribution_variable"))
    result["includes_excise"] = _tri_state(result.get("includes_excise"))
    result["includes_service_margin"] = _tri_state(result.get("includes_service_margin"))
    result["missing_policy"] = "fail_closed"
    # Presence is semantic: an explicit empty entity means that the user
    # deliberately unmapped the source.  It must not be resurrected by a
    # provider/legacy default passed by the caller.
    result["today_entity"] = str(
        (explicit.get("today_entity") or "")
        if "today_entity" in explicit
        else (result.get("today_entity") or today_entity or "")
    )
    result["tomorrow_entity"] = str(
        (explicit.get("tomorrow_entity") or "")
        if "tomorrow_entity" in explicit
        else (result.get("tomorrow_entity") or tomorrow_entity or "")
    )
    result["today_binding"] = dict(result.get("today_binding") or {}) if isinstance(result.get("today_binding"), dict) else {}
    result["tomorrow_binding"] = dict(result.get("tomorrow_binding") or {}) if isinstance(result.get("tomorrow_binding"), dict) else {}
    result["resolved_schema_today"] = dict(result.get("resolved_schema_today") or {}) if isinstance(result.get("resolved_schema_today"), dict) else {}
    result["resolved_schema_tomorrow"] = dict(result.get("resolved_schema_tomorrow") or {}) if isinstance(result.get("resolved_schema_tomorrow"), dict) else {}
    result["current_price_only"] = bool(result.get("current_price_only", False))
    result["allow_state_fallback"] = bool(
        result.get("allow_state_fallback", False) and result["current_price_only"]
    )
    vat_rate = result.get("vat_rate")
    try:
        result["vat_rate"] = float(vat_rate) if vat_rate not in (None, "") else None
    except (TypeError, ValueError):
        result["vat_rate"] = None
    if result["vat_rate"] is not None and not 0 <= result["vat_rate"] <= 1:
        result["vat_rate"] = None
    # Known adapters own their non-negotiable source semantics.  User options
    # may select entities and the RCE tax basis/unit, but cannot reintroduce a
    # double-count or turn a current-only prosumer sensor into a forecast.
    if result["source_adapter"] == "pstryk":
        result.update({
            "economic_role": "retail_buy_all_in" if result["direction"] == "buy" else "prosumer_sell",
            "semantic_scope": "all_in_variable",
            "includes_distribution_variable": True,
            "price_basis": "gross",
            "includes_excise": True,
            "includes_service_margin": True,
            "unit": "PLN/kWh",
            "granularity": "60m",
            "today_list_attribute": "today_prices",
            "tomorrow_list_attribute": "tomorrow_prices",
            "value_field": "price",
            "start_field": "start",
            "end_field": "end",
            "allow_state_fallback": False,
            "current_price_only": False,
        })
    elif result["source_adapter"] == "rce_pse":
        result.update({
            "economic_role": "energy_only" if result["direction"] == "buy" else "market_reference",
            "semantic_scope": "energy_only",
            "includes_distribution_variable": False,
            "includes_excise": False,
            "includes_service_margin": False,
            "price_basis": "gross",
            "unit": "PLN/kWh",
            "value_field": "rce_pln",
            "period_field": "period",
            "timestamp_field": "dtime",
            "timestamp_role": "end",
            "business_date_field": "business_date",
            "granularity": "15m",
            "allow_state_fallback": False,
        })
    # Runtime-resolved per-day metadata is an extension of the v1 contract.
    # Keep it across normalization so mixed Today/Tomorrow adapters cannot be
    # collapsed back to the primary adapter during canonical row generation.
    for key in (
        "mapping_fingerprint", "adapter_summary", "auto_metadata_origin",
        "resolved_adapter_today", "resolved_adapter_tomorrow",
        "resolved_source_today", "resolved_source_tomorrow",
    ):
        if key in explicit:
            result[key] = explicit[key]
    return result


def unmapped_price_contract(direction: str) -> dict[str, Any]:
    """Return the minimal inactive contract for two explicitly empty slots.

    Deliberately omit parser and economic fields.  They describe an active
    source and must never survive a clear as apparently current metadata.
    """
    direction = "sell" if direction == "sell" else "buy"
    return {
        "version": PRICE_CONTRACT_VERSION,
        "direction": direction,
        "today_entity": "",
        "tomorrow_entity": "",
        "resolved_today_entity": "",
        "resolved_tomorrow_entity": "",
        "today_binding": {},
        "tomorrow_binding": {},
        "resolved_schema_today": {},
        "resolved_schema_tomorrow": {},
        "resolved_source_today": {},
        "resolved_source_tomorrow": {},
        "resolved_adapter_today": "unmapped",
        "resolved_adapter_tomorrow": "unmapped",
        "stable_identity_today_status": "unmapped",
        "stable_identity_tomorrow_status": "unmapped",
        "stable_identity_today_reason": "user_unmapped",
        "stable_identity_tomorrow_reason": "user_unmapped",
        "mapping_fingerprint": price_mapping_fingerprint("", ""),
        "adapter_summary": "unmapped",
        "auto_metadata_origin": "current_mapping",
    }


def price_mapping_fingerprint(today_entity: str | None, tomorrow_entity: str | None) -> str:
    """Return a deterministic identity for the two persisted mapping slots."""
    today = str(today_entity or "")
    tomorrow = str(tomorrow_entity or "")
    return f"{len(today)}:{today}|{len(tomorrow)}:{tomorrow}"


def contract_mapping_matches(
    contract: dict[str, Any] | None,
    today_entity: str | None,
    tomorrow_entity: str | None,
) -> bool:
    """Tell whether saved metadata still belongs to the current mappings."""
    saved = contract if isinstance(contract, dict) else {}
    fingerprint = str(saved.get("mapping_fingerprint") or "")
    expected = price_mapping_fingerprint(today_entity, tomorrow_entity)
    if fingerprint:
        return fingerprint == expected
    return (
        str(saved.get("today_entity") or "") == str(today_entity or "")
        and str(saved.get("tomorrow_entity") or "") == str(tomorrow_entity or "")
    )


def rebuild_price_contract(
    existing: dict[str, Any] | None,
    direction: str,
    today_entity: str | None,
    tomorrow_entity: str | None,
    today_adapter: str,
    tomorrow_adapter: str,
    *,
    preserve_custom: bool = True,
) -> dict[str, Any]:
    """Build auto metadata from current mappings, never from a stale provider.

    Known adapters are always rebuilt from their adapter contract.  A custom
    contract is reusable only while its persisted mapping fingerprint matches.
    Per-day profiles keep mixed Today/Tomorrow providers independent.
    """
    saved = dict(existing or {}) if isinstance(existing, dict) else {}
    today = str(today_entity or "")
    tomorrow = str(tomorrow_entity or "")
    if not today and not tomorrow:
        return unmapped_price_contract(direction)
    saved_adapter = str(saved.get("source_adapter") or "")

    adapters = {
        "today": today_adapter if today and today_adapter in SUPPORTED_ADAPTERS else "generic",
        "tomorrow": tomorrow_adapter if tomorrow and tomorrow_adapter in SUPPORTED_ADAPTERS else "generic",
    }
    same_day_mapping = {
        day_name: str(saved.get(f"{day_name}_entity") or "") == entity_id
        for day_name, entity_id in (("today", today), ("tomorrow", tomorrow))
    }
    if preserve_custom:
        for day_name, entity_id in (("today", today), ("tomorrow", tomorrow)):
            saved_day_adapter = str(saved.get(f"resolved_adapter_{day_name}") or saved_adapter)
            if (
                entity_id
                and same_day_mapping[day_name]
                and adapters[day_name] == "generic"
                and saved_day_adapter in {"generic", "custom"}
            ):
                adapters[day_name] = saved_day_adapter
    mapped_adapters = [
        adapters[day_name]
        for day_name, entity_id in (("today", today), ("tomorrow", tomorrow))
        if entity_id
    ]
    primary_adapter = mapped_adapters[0] if mapped_adapters else "generic"
    primary_day = "today" if today else "tomorrow"
    primary_saved_adapter = str(saved.get(f"resolved_adapter_{primary_day}") or saved_adapter)
    manual_primary_reusable = bool(
        preserve_custom
        and same_day_mapping[primary_day]
        and primary_saved_adapter in {"generic", "custom"}
        and primary_saved_adapter == primary_adapter
    )
    source = saved if manual_primary_reusable else {}
    contract = normalize_price_contract(source, direction, primary_adapter, today, tomorrow)
    contract.update({
        "today_entity": today,
        "tomorrow_entity": tomorrow,
        "mapping_fingerprint": price_mapping_fingerprint(today, tomorrow),
        "adapter_summary": (
            mapped_adapters[0]
            if mapped_adapters and len(set(mapped_adapters)) == 1
            else "mixed"
            if mapped_adapters
            else "unmapped"
        ),
        "auto_metadata_origin": "current_mapping",
    })

    for day_name, entity_id in (("today", today), ("tomorrow", tomorrow)):
        adapter = adapters[day_name]
        contract[f"resolved_adapter_{day_name}"] = adapter if entity_id else "unmapped"
        if not entity_id:
            contract[f"resolved_source_{day_name}"] = {}
            contract[f"resolved_schema_{day_name}"] = {}
            continue
        saved_day_adapter = str(saved.get(f"resolved_adapter_{day_name}") or saved_adapter)
        manual_day_reusable = bool(
            preserve_custom
            and same_day_mapping[day_name]
            and saved_day_adapter in {"generic", "custom"}
            and saved_day_adapter == adapter
        )
        profile_source = saved if manual_day_reusable else {}
        profile = normalize_price_contract(
            profile_source,
            direction,
            adapter,
            entity_id if day_name == "today" else "",
            entity_id if day_name == "tomorrow" else "",
        )
        contract[f"resolved_source_{day_name}"] = {
            key: profile.get(key)
            for key in _DAY_SOURCE_FIELDS
        }
        saved_day_adapter = str(saved.get(f"resolved_adapter_{day_name}") or saved_adapter)
        saved_schema = saved.get(f"resolved_schema_{day_name}")
        if same_day_mapping[day_name] and saved_day_adapter == adapter and isinstance(saved_schema, dict):
            contract[f"resolved_schema_{day_name}"] = dict(saved_schema)
        else:
            contract[f"resolved_schema_{day_name}"] = {}
    return contract


def effective_contract_for_day(contract: dict[str, Any], source_day: int) -> dict[str, Any]:
    """Return current per-day adapter semantics for parsing and economics."""
    day_name = "today" if source_day == 0 else "tomorrow"
    profile = contract.get(f"resolved_source_{day_name}")
    effective = dict(contract)
    if isinstance(profile, dict):
        effective.update(profile)
    adapter = str(contract.get(f"resolved_adapter_{day_name}") or "")
    if adapter in SUPPORTED_ADAPTERS:
        effective["source_adapter"] = adapter
    return effective


def migrate_legacy_price_contracts(data: dict[str, Any]) -> dict[str, Any]:
    """Create independent BUY/SELL contracts without changing entity mapping."""
    migrated = dict(data)
    source = str(migrated.get("price_source") or "pstryk").lower()
    adapter = {"pstryk": "pstryk", "pse_rce": "rce_pse", "rce_pse": "rce_pse"}.get(
        source, "generic"
    )
    legacy = bool(migrated.get("price_includes_distribution", False))
    definitions = {
        "buy_price_contract": (
            "buy",
            "buy_price_today_sensor",
            "buy_price_tomorrow_sensor",
            "sensor.pstryk_aio_obecna_cena_zakupu_pradu",
            "sensor.pstryk_aio_cena_zakupu_pradu_jutro",
        ),
        "sell_price_contract": (
            "sell",
            "price_sensor",
            "sell_price_tomorrow_sensor",
            "sensor.pstryk_aio_obecna_cena_sprzedazy_pradu",
            "sensor.pstryk_aio_cena_sprzedazy_pradu_jutro",
        ),
    }
    for contract_key, (direction, today_key, tomorrow_key, default_today, default_tomorrow) in definitions.items():
        existing = migrated.get(contract_key)
        if isinstance(existing, dict):
            contract = dict(existing)
            # Explicit mapping keys own the contract, including null/empty.
            for mapping_key, entity_field in ((today_key, "today_entity"), (tomorrow_key, "tomorrow_entity")):
                if mapping_key in migrated:
                    contract[entity_field] = str(migrated.get(mapping_key) or "")
                elif entity_field in contract:
                    # Stage 5G.4K.3A could persist the empty choice only in the
                    # contract. Promote it to the central mapping key on upgrade.
                    migrated[mapping_key] = str(contract.get(entity_field) or "")
            migrated[contract_key] = contract
            continue
        today_entity = str(migrated.get(today_key) or "") if today_key in migrated else default_today
        tomorrow_entity = str(migrated.get(tomorrow_key) or "") if tomorrow_key in migrated else default_tomorrow
        migrated[today_key] = today_entity
        migrated[tomorrow_key] = tomorrow_entity
        migrated[contract_key] = default_price_contract(
            direction,
            adapter,
            today_entity,
            tomorrow_entity,
            legacy_includes_distribution=legacy if direction == "buy" else None,
        )
    return migrated


def _attribute_rows(state: Any, attribute: str) -> list[Any] | dict[str, Any] | None:
    attrs = getattr(state, "attributes", {}) or {}
    value = attrs.get(attribute) if attribute else None
    return value if isinstance(value, (list, dict)) else None


def resolve_price_schema(
    state: Any,
    contract: dict[str, Any],
    source_day: int,
) -> tuple[dict[str, Any], str]:
    """Resolve one bounded, explicit schema without scanning other entities."""
    contract = effective_contract_for_day(contract, source_day)
    day_name = "today" if source_day == 0 else "tomorrow"
    saved_key = f"resolved_schema_{day_name}"
    saved = contract.get(saved_key) if isinstance(contract.get(saved_key), dict) else {}
    if not str(contract.get(f"{day_name}_entity") or ""):
        return {}, "unmapped"
    if state is None:
        return saved, "mapped_entity_missing"
    if saved and _attribute_rows(state, str(saved.get("list_attribute") or "")) is not None:
        return dict(saved), "ready"

    adapter = str(contract.get("source_adapter") or "generic")
    explicit_attribute = str(
        contract.get(f"{day_name}_list_attribute") or contract.get("list_attribute") or ""
    )
    if adapter == "custom":
        attributes = [explicit_attribute] if explicit_attribute else []
    elif adapter == "pstryk":
        attributes = [
            explicit_attribute,
            "today_prices" if source_day == 0 else "tomorrow_prices",
            "prices",
        ]
    elif adapter == "rce_pse":
        attributes = [explicit_attribute, "prices", "value_json"]
    else:
        attributes = [
            explicit_attribute,
            "today_prices" if source_day == 0 else "tomorrow_prices",
            "prices",
        ]
    attributes = list(dict.fromkeys(item for item in attributes if item))
    for attribute in attributes:
        raw = _attribute_rows(state, attribute)
        if raw is None:
            continue
        rows = list(raw.values()) if isinstance(raw, dict) else raw
        sample = next((row for row in rows if isinstance(row, dict)), None)
        if sample is None:
            if adapter == "pstryk" and attribute in {"today_prices", "tomorrow_prices"}:
                return {
                    "schema_id": "pstryk_aio_interval_v1",
                    "list_attribute": attribute,
                    "value_field": "price",
                    "start_field": "start",
                    "end_field": "end",
                    "granularity": "60m",
                }, "empty_series"
            continue
        if "rce_pln" in sample and any(key in sample for key in ("period", "dtime", "business_date")):
            return {
                "schema_id": "rce_interval_v1",
                "list_attribute": attribute,
                "value_field": "rce_pln",
                "period_field": "period",
                "timestamp_field": "dtime",
                "timestamp_role": "end",
                "business_date_field": "business_date",
                "granularity": "15m",
            }, "ready"
        value_field = next(
            (key for key in (str(contract.get("value_field") or ""), "price", "value", "price_gross", "price_prosumer_gross") if key and key in sample),
            None,
        )
        if value_field is None:
            continue
        start_field = str(contract.get("start_field") or "start")
        end_field = str(contract.get("end_field") or "end")
        if start_field in sample and end_field in sample:
            schema_id = "pstryk_aio_interval_v1" if adapter == "pstryk" and value_field == "price" else "start_end_price_v1"
            return {
                "schema_id": schema_id,
                "list_attribute": attribute,
                "value_field": value_field,
                "start_field": start_field,
                "end_field": end_field,
                "granularity": str(contract.get("granularity") if contract.get("granularity") in {"15m", "60m"} else "60m"),
            }, "ready"
        timestamp_field = next(
            (key for key in (str(contract.get("timestamp_field") or ""), "time", "start", "datetime", "timestamp", "hour") if key and key in sample),
            None,
        )
        if timestamp_field is not None:
            return {
                "schema_id": "timestamp_price_v1",
                "list_attribute": attribute,
                "value_field": value_field,
                "timestamp_field": timestamp_field,
                "timestamp_role": str(contract.get("timestamp_role") or "start"),
                "granularity": str(contract.get("granularity") if contract.get("granularity") in {"15m", "60m"} else "60m"),
            }, "ready"
    return {}, "unsupported_price_schema"


def resolve_contract_schemas(
    contract: dict[str, Any],
    today_state: Any,
    tomorrow_state: Any,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Resolve and persistable-copy the schema for each mapped series."""
    resolved = dict(contract)
    diagnostics: dict[str, dict[str, Any]] = {}
    for source_day, state in enumerate((today_state, tomorrow_state)):
        day_name = "today" if source_day == 0 else "tomorrow"
        schema, status = resolve_price_schema(state, resolved, source_day)
        if schema:
            resolved[f"resolved_schema_{day_name}"] = schema
        diagnostics[day_name] = {"status": status, "resolved_schema": schema}
    return resolved, diagnostics


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unit_from_state(contract: dict[str, Any], state: Any) -> str:
    configured = str(contract.get("unit") or "unknown")
    if configured in SUPPORTED_UNITS:
        return configured
    attrs = getattr(state, "attributes", {}) if state is not None else {}
    raw = str(attrs.get("unit_of_measurement") or "").replace(" ", "")
    normalized = {"PLN/kWh": "PLN/kWh", "PLN/MWh": "PLN/MWh"}.get(raw)
    return normalized or "unknown"


def _normalize_unit(value: float, unit: str) -> float | None:
    if unit == "PLN/kWh":
        return value
    if unit == "PLN/MWh":
        return value / 1000.0
    return None


def _parse_iso(value: Any, reference: datetime) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=reference.tzinfo)
    return parsed.astimezone(reference.tzinfo) if reference.tzinfo is not None else parsed


def _clock(text: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour == 24 and minute == 0:
        return 24, 0
    return (hour, minute) if 0 <= hour <= 23 and 0 <= minute <= 59 else None


def _period_interval(period: Any, business_day: date, reference: datetime) -> tuple[datetime, datetime] | None:
    parts = re.split(r"\s*[-–—]\s*", str(period or "").strip())
    if len(parts) != 2:
        return None
    start_clock, end_clock = _clock(parts[0]), _clock(parts[1])
    if start_clock is None or end_clock is None or start_clock == (24, 0):
        return None
    start = datetime.combine(business_day, time(*start_clock), tzinfo=reference.tzinfo)
    if end_clock == (24, 0):
        end = datetime.combine(business_day + timedelta(days=1), time(0, 0), tzinfo=reference.tzinfo)
    else:
        end = datetime.combine(business_day, time(*end_clock), tzinfo=reference.tzinfo)
        if end <= start:
            end += timedelta(days=1)
    return (start, end) if end > start else None


def _value_from_row(row: Any, contract: dict[str, Any]) -> float | None:
    if isinstance(row, (list, tuple)) and len(row) >= 2:
        return _finite(row[1])
    if not isinstance(row, dict):
        return _finite(row)
    explicit = str(contract.get("value_field") or "")
    bounded = [explicit] if explicit else []
    bounded.extend(("price", "value", "price_gross", "price_prosumer_gross", "gross_price", "net_price", "state"))
    for key in dict.fromkeys(key for key in bounded if key):
        if key in row and (value := _finite(row.get(key))) is not None:
            return value
    return None


def _row_interval(
    row: Any,
    contract: dict[str, Any],
    reference: datetime,
    source_day: int,
    fallback_index: int | None,
) -> tuple[datetime, datetime] | None:
    day = reference.date() + timedelta(days=source_day)
    if isinstance(row, dict):
        business_key = str(contract.get("business_date_field") or "")
        if business_key and row.get(business_key):
            try:
                day = date.fromisoformat(str(row[business_key]))
            except ValueError:
                return None
        period_key = str(contract.get("period_field") or "")
        if period_key and row.get(period_key) is not None:
            interval = _period_interval(row.get(period_key), day, reference)
            if interval is not None:
                return interval
        start_key = str(contract.get("start_field") or "")
        end_key = str(contract.get("end_field") or "")
        if start_key and end_key and row.get(start_key) is not None and row.get(end_key) is not None:
            start_value = _parse_iso(row.get(start_key), reference)
            end_value = _parse_iso(row.get(end_key), reference)
            if start_value is not None and end_value is not None and end_value > start_value:
                return start_value, end_value
        time_key = str(contract.get("timestamp_field") or "")
        raw_time = row.get(time_key) if time_key else None
        if raw_time is None:
            for key in ("start", "time", "datetime", "timestamp", "hour"):
                if key in row:
                    raw_time = row[key]
                    break
    elif isinstance(row, (list, tuple)) and len(row) >= 2:
        raw_time = row[0]
    else:
        raw_time = fallback_index
    parsed = _parse_iso(raw_time, reference)
    if parsed is None:
        match = re.search(r"(?:^|\D)(\d{1,2})(?::(\d{2}))?", str(raw_time or ""))
        if match and 0 <= int(match.group(1)) <= 23:
            parsed = datetime.combine(
                day,
                time(int(match.group(1)), int(match.group(2) or 0)),
                tzinfo=reference.tzinfo,
            )
    if parsed is None and fallback_index is not None and 0 <= fallback_index <= 23:
        parsed = datetime.combine(day, time(fallback_index), tzinfo=reference.tzinfo)
    if parsed is None:
        return None
    minutes = 15 if contract.get("granularity") == "15m" else 60
    if contract.get("timestamp_role") == "end":
        return parsed - timedelta(minutes=minutes), parsed
    return parsed, parsed + timedelta(minutes=minutes)


def _source_rows(state: Any, contract: dict[str, Any]) -> list[Any]:
    if state is None:
        return []
    attrs = getattr(state, "attributes", {}) or {}
    key = str(contract.get("list_attribute") or "prices")
    source = attrs.get(key)
    if isinstance(source, list):
        return source
    if isinstance(source, dict):
        return [
            ({**value, "hour": value.get("hour", item_key)} if isinstance(value, dict) else [item_key, value])
            for item_key, value in source.items()
        ]
    return []


def _intervals_for_state(
    state: Any,
    contract: dict[str, Any],
    reference: datetime,
    source_day: int,
) -> tuple[list[PriceInterval], str, dict[str, Any]]:
    day_contract = effective_contract_for_day(contract, source_day)
    day_name = "today" if source_day == 0 else "tomorrow"
    if not str(contract.get(f"{day_name}_entity") or ""):
        return [], "unmapped", {}
    if state is None:
        saved = contract.get("resolved_schema_today" if source_day == 0 else "resolved_schema_tomorrow")
        return [], "mapped_entity_missing", dict(saved) if isinstance(saved, dict) else {}
    schema, schema_status = resolve_price_schema(state, contract, source_day)
    effective = {**day_contract, **schema}
    unit = _unit_from_state(effective, state)
    if unit == "unknown":
        return [], "unsupported_unit", schema
    rows = _source_rows(state, effective)
    intervals: list[PriceInterval] = []
    entity_id = str(getattr(state, "entity_id", "") or contract.get("today_entity") or "")
    for index, row in enumerate(rows):
        value = _value_from_row(row, effective)
        interval = _row_interval(row, effective, reference, source_day, index if index < 24 else None)
        normalized = _normalize_unit(value, unit) if value is not None else None
        if interval is not None and normalized is not None:
            intervals.append(PriceInterval(interval[0], interval[1], normalized, entity_id, index))
    if not intervals and source_day == 0 and bool(effective.get("current_price_only")):
        value = _finite(getattr(state, "state", None))
        normalized = _normalize_unit(value, unit) if value is not None else None
        if normalized is not None:
            start = reference.replace(minute=0, second=0, microsecond=0)
            intervals.append(PriceInterval(start, start + timedelta(hours=1), normalized, entity_id, -1))
    if intervals:
        return intervals, "ready", schema
    return intervals, schema_status if schema_status != "ready" else "incomplete_price_series", schema


def _split_by_hour(interval: PriceInterval) -> Iterable[tuple[tuple[date, int], datetime, datetime, float]]:
    cursor = interval.start
    while cursor < interval.end:
        boundary = (cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        segment_end = min(interval.end, boundary)
        if segment_end <= cursor:
            break
        yield (cursor.date(), cursor.hour), cursor, segment_end, interval.price_pln_kwh
        cursor = segment_end


def aggregate_hourly(intervals: Iterable[PriceInterval]) -> tuple[dict[tuple[date, int], dict[str, Any]], dict[str, Any]]:
    """Aggregate intervals into complete, non-overlapping local hours."""
    buckets: dict[tuple[date, int], list[tuple[datetime, datetime, float]]] = {}
    for interval in intervals:
        for key, start, end, price in _split_by_hour(interval):
            buckets.setdefault(key, []).append((start, end, price))
    complete: dict[tuple[date, int], dict[str, Any]] = {}
    partial_hours: list[str] = []
    invalid_hours: list[str] = []
    for key, segments in buckets.items():
        ordered = sorted(segments, key=lambda item: (item[0], item[1], item[2]))
        overlap = any(current[0] < previous[1] for previous, current in zip(ordered, ordered[1:]))
        coverage = sum((end - start).total_seconds() / 60.0 for start, end, _price in ordered)
        label = f"{key[0].isoformat()}T{key[1]:02d}:00"
        if overlap or coverage > 60.000001:
            invalid_hours.append(label)
            continue
        if abs(coverage - 60.0) > 0.000001:
            partial_hours.append(label)
            continue
        weighted = sum(price * ((end - start).total_seconds() / 60.0) for start, end, price in ordered)
        complete[key] = {
            "source_price_pln_kwh": weighted / coverage,
            "coverage_minutes": round(coverage, 6),
            "interval_count": len(ordered),
        }
    return complete, {
        "partial_hours": sorted(partial_hours),
        "invalid_hours": sorted(invalid_hours),
    }


def build_canonical_direction(
    contract: dict[str, Any],
    today_state: Any,
    tomorrow_state: Any,
    reference: datetime,
    distribution_by_slot: dict[tuple[date, int], float] | None = None,
) -> dict[str, Any]:
    """Build canonical Today/Tomorrow rows for one independent direction."""
    raw_direction = "sell" if str(contract.get("direction") or "buy") == "sell" else "buy"
    if not str(contract.get("today_entity") or "") and not str(contract.get("tomorrow_entity") or ""):
        inactive = unmapped_price_contract(raw_direction)
        diagnostics = {
            "status": "price_source_not_configured",
            "day_status": {"today": "unmapped", "tomorrow": "unmapped"},
            "coverage_today": 0,
            "coverage_tomorrow": 0,
            "partial_hours": [],
            "invalid_hours": [],
            "resolver": {
                "today": {"status": "unmapped", "resolved_schema": {}},
                "tomorrow": {"status": "unmapped", "resolved_schema": {}},
            },
        }
        return {
            "schema_version": 1,
            "direction": raw_direction,
            "contract": inactive,
            "rows": [],
            "diagnostics": diagnostics,
            "source_statuses": ["unmapped", "unmapped"],
        }
    contract = normalize_price_contract(
        contract,
        str(contract.get("direction") or "buy"),
        str(contract.get("source_adapter") or "generic"),
        str(contract.get("today_entity") or ""),
        str(contract.get("tomorrow_entity") or ""),
    )
    contract, schema_diagnostics = resolve_contract_schemas(contract, today_state, tomorrow_state)
    direction = contract["direction"]
    diagnostics: dict[str, Any] = {
        "status": "ready",
        "day_status": {},
        "partial_hours": [],
        "invalid_hours": [],
        "resolver": schema_diagnostics,
    }
    day_contracts = [effective_contract_for_day(contract, source_day) for source_day in (0, 1)]
    for source_day, (day_contract, state) in enumerate(zip(day_contracts, (today_state, tomorrow_state))):
        day_name = "today" if source_day == 0 else "tomorrow"
        if not str(contract.get(f"{day_name}_entity") or ""):
            continue
        if day_contract["price_basis"] not in SUPPORTED_BASES:
            diagnostics["status"] = "unknown_price_basis"
            return {"schema_version": 1, "direction": direction, "contract": contract, "rows": [], "diagnostics": diagnostics}
        if day_contract.get("economic_role") not in SUPPORTED_ECONOMIC_ROLES:
            diagnostics["status"] = "unknown_economic_role"
            return {"schema_version": 1, "direction": direction, "contract": contract, "rows": [], "diagnostics": diagnostics}
        if day_contract["unit"] == "unknown" and _unit_from_state(day_contract, state) == "unknown":
            diagnostics["status"] = "unsupported_unit"
            return {"schema_version": 1, "direction": direction, "contract": contract, "rows": [], "diagnostics": diagnostics}
        if day_contract["semantic_scope"] == "partial" and not isinstance(day_contract["includes_distribution_variable"], bool):
            diagnostics["status"] = "ambiguous_price_source"
            return {"schema_version": 1, "direction": direction, "contract": contract, "rows": [], "diagnostics": diagnostics}
        if day_contract["price_basis"] == "net" and day_contract.get("vat_rate") is None:
            diagnostics["status"] = "unknown_price_basis"
            return {"schema_version": 1, "direction": direction, "contract": contract, "rows": [], "diagnostics": diagnostics}
    if (
        direction == "sell"
        and any(
            str(contract.get(f"resolved_adapter_{day_name}") or contract.get("source_adapter") or "") == "rce_pse"
            and str(contract.get(f"{day_name}_entity") or "")
            for day_name in ("today", "tomorrow")
        )
        and not any(
            item.get("status") in {"ready", "empty_series"}
            for item in schema_diagnostics.values()
        )
    ):
        diagnostics["status"] = "missing_sell_forecast"
        diagnostics["current_value_available"] = _finite(getattr(today_state, "state", None)) is not None
        return {"schema_version": 1, "direction": direction, "contract": contract, "rows": [], "diagnostics": diagnostics}
    intervals: list[PriceInterval] = []
    source_statuses: list[str] = []
    for source_day, state in enumerate((today_state, tomorrow_state)):
        parsed, status, schema = _intervals_for_state(state, contract, reference, source_day)
        intervals.extend(parsed)
        source_statuses.append(status)
        name = "today" if source_day == 0 else "tomorrow"
        diagnostics["resolver"][name] = {"status": status, "resolved_schema": schema}
    hourly, aggregation = aggregate_hourly(intervals)
    diagnostics.update(aggregation)
    distribution_by_slot = distribution_by_slot or {}
    rows: list[dict[str, Any]] = []
    for (local_date, hour), aggregated in sorted(hourly.items()):
        offset = (local_date - reference.date()).days
        if offset not in (0, 1):
            continue
        day_contract = day_contracts[offset]
        source_price = float(aggregated["source_price_pln_kwh"])
        added_vat = source_price * float(day_contract.get("vat_rate") or 0.0) if day_contract["price_basis"] == "net" else 0.0
        energy_component = source_price + added_vat
        distribution = max(0.0, float(distribution_by_slot.get((local_date, hour), 0.0)))
        add_distribution = (
            direction == "buy"
            and day_contract["economic_role"] in {"energy_only", "custom"}
            and day_contract["includes_distribution_variable"] is False
            and day_contract["semantic_scope"] in {"energy_only", "partial"}
        )
        added_distribution = distribution if add_distribution else 0.0
        final_price = energy_component + added_distribution
        rows.append({
            "date": local_date.isoformat(),
            "day": "today" if offset == 0 else "tomorrow",
            "hour": hour,
            "direction": direction,
            "source_adapter": day_contract["source_adapter"],
            "source_price_pln_kwh": round(source_price, 10),
            "energy_component": round(energy_component, 10),
            "added_distribution": round(added_distribution, 10),
            "added_vat": round(added_vat, 10),
            "added_other_variable": 0.0,
            "final_price_pln_kwh": round(final_price, 10),
            "coverage_minutes": aggregated["coverage_minutes"],
            "source_unit": day_contract["unit"] if day_contract["unit"] != "unknown" else _unit_from_state(day_contract, today_state if offset == 0 else tomorrow_state),
            "source_basis": day_contract["price_basis"],
            "source_semantic_scope": day_contract["semantic_scope"],
            "source_economic_role": day_contract["economic_role"],
            "source_metadata": {"interval_count": aggregated["interval_count"]},
            "quality": "ready",
            "status": "ready",
        })
    for offset, name in enumerate(("today", "tomorrow")):
        count = sum(row["day"] == name for row in rows)
        diagnostics["day_status"][name] = (
            "unmapped"
            if source_statuses[offset] == "unmapped"
            else "ready"
            if count == 24
            else "waiting_data"
            if count == 0 and offset == 1
            else "incomplete"
        )
        diagnostics[f"coverage_{name}"] = count
    if diagnostics["invalid_hours"]:
        diagnostics["status"] = "invalid_overlap"
    elif diagnostics["partial_hours"] or any(value == "incomplete" for value in diagnostics["day_status"].values()):
        diagnostics["status"] = "incomplete"
    elif not rows:
        diagnostics["status"] = "waiting_data"
    return {
        "schema_version": 1,
        "direction": direction,
        "contract": contract,
        "rows": rows,
        "diagnostics": diagnostics,
        "source_statuses": source_statuses,
    }


def canonical_maps(result: dict[str, Any]) -> list[dict[int, float]]:
    maps: list[dict[int, float]] = [{}, {}]
    for row in result.get("rows", []):
        if not isinstance(row, dict) or row.get("quality") != "ready":
            continue
        day = 0 if row.get("day") == "today" else 1 if row.get("day") == "tomorrow" else -1
        hour = row.get("hour")
        price = _finite(row.get("final_price_pln_kwh"))
        if day in (0, 1) and isinstance(hour, int) and 0 <= hour <= 23 and price is not None:
            maps[day][hour] = price
    return maps

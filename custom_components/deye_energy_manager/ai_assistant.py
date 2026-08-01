"""Optional external AI reviewer for a locally calculated energy plan.

The provider can explain or suggest an alternative, but this module has no
access to Home Assistant services and never changes the authoritative local
plan.  Every response is parsed and validated before it is exposed to the UI.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import math
import time
from typing import Any


PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "models_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/models",
    },
    "openrouter": {
        "name": "OpenRouter",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "models_endpoint": "https://openrouter.ai/api/v1/models",
    },
    "openai": {
        "name": "OpenAI",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "models_endpoint": "https://api.openai.com/v1/models",
    },
    "opencode": {
        "name": "OpenCode / OpenCode Go",
        "endpoint": "https://console.opencode.ai/inference/openai/v1/chat/completions",
        "models_endpoint": "https://console.opencode.ai/inference/openai/v1/models",
    },
    "custom": {
        "name": "Własny endpoint zgodny z OpenAI API",
        "endpoint": "",
        "models_endpoint": "",
    },
}

ROLES = {"explain", "review", "experimental"}
ALLOWED_ACTIONS = {"none", "sell", "charge"}
ALLOWED_ASSESSMENTS = {"safe", "caution", "unsafe"}
ALLOWED_OPTIONS = {"safe", "balanced", "profit", "none"}

RESPONSE_SCHEMA = {
    "name": "deye_energy_plan_review",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status", "summary", "plan_assessment", "confidence_adjustment",
            "best_option", "alternative", "reasons", "risks",
        ],
        "properties": {
            "status": {"type": "string", "enum": ["ok", "warning", "rejected"]},
            "summary": {"type": "string", "maxLength": 1200},
            "plan_assessment": {"type": "string", "enum": sorted(ALLOWED_ASSESSMENTS)},
            "confidence_adjustment": {"type": "number", "minimum": -25, "maximum": 10},
            "best_option": {"type": "string", "enum": sorted(ALLOWED_OPTIONS)},
            "alternative": {
                "type": "object",
                "additionalProperties": False,
                "required": ["enabled", "hours"],
                "properties": {
                    "enabled": {"type": "boolean"},
                    "hours": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["start", "end", "action", "power_w"],
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "action": {"type": "string", "enum": sorted(ALLOWED_ACTIONS)},
                                "power_w": {"type": "number", "minimum": 0, "maximum": 13000},
                            },
                        },
                    },
                },
            },
            "reasons": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 500}},
            "risks": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 500}},
        },
    },
}


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a diagnostic-safe configuration with no recoverable secret."""
    result = {
        key: deepcopy(value)
        for key, value in config.items()
        if key not in {"api_key", "token", "authorization"}
    }
    key = str(config.get("api_key") or "")
    result["api_key_configured"] = bool(key)
    result["api_key"] = "***" if key else ""
    return result


def normalize_config(raw: dict[str, Any], previous_secret: str = "") -> dict[str, Any]:
    provider = str(raw.get("provider") or "openrouter")
    if provider not in PROVIDERS:
        raise ValueError("Nieobsługiwany dostawca AI")
    role = str(raw.get("role") or "review")
    if role not in ROLES:
        raise ValueError("Nieobsługiwana rola modelu")
    endpoint = str(raw.get("endpoint") or "").strip()
    if provider == "custom":
        if not endpoint.lower().startswith("https://"):
            raise ValueError("Własny endpoint musi używać HTTPS")
        if not endpoint.rstrip("/").endswith("/chat/completions"):
            endpoint = f"{endpoint.rstrip('/')}/chat/completions"
    else:
        endpoint = PROVIDERS[provider]["endpoint"]
    model = str(raw.get("model") or "").strip()
    if bool(raw.get("enabled")) and not model:
        raise ValueError("Podaj identyfikator modelu")
    incoming_key = str(raw.get("api_key") or "")
    api_key = incoming_key if incoming_key else previous_secret
    if bool(raw.get("enabled")) and not api_key:
        raise ValueError("Podaj osobny klucz API dla integracji")
    history_hours = int(_finite(raw.get("max_history_hours")) or 0)
    if not 0 <= history_hours <= 168:
        raise ValueError("Zakres historii musi mieścić się w zakresie 0–168 godzin")
    return {
        "enabled": bool(raw.get("enabled")),
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "endpoint": endpoint,
        "role": role,
        "hourly_only": bool(raw.get("hourly_only", True)),
        "remove_entity_names": bool(raw.get("remove_entity_names", True)),
        "remove_exact_location": bool(raw.get("remove_exact_location", True)),
        "max_history_hours": history_hours,
    }


def _clean_number(value: Any, digits: int = 5) -> float | None:
    number = _finite(value)
    return round(number, digits) if number is not None else None


def _private_profiles(user_profiles: dict[str, Any] | None) -> dict[str, Any]:
    """Return only profile fields needed to review the local plan."""
    root = user_profiles if isinstance(user_profiles, dict) else {}
    profiles = root.get("profiles") if isinstance(root.get("profiles"), dict) else {}
    allowed = {
        "name", "enabled", "type", "start", "end", "active_days", "priority",
        "goal_character", "allow_partial", "minimum_confidence",
        "target_energy_kwh", "target_basis", "min_price", "preferred_power_w",
        "distribution_method", "min_soc_after", "target_type", "target_value",
        "source", "max_effective_price", "max_grid_energy_kwh",
        "preserve_pv_room", "minimum_free_room_kwh",
    }
    return {
        str(profile_id): {
            key: deepcopy(value)
            for key, value in profile.items()
            if key in allowed
        }
        for profile_id, profile in profiles.items()
        if isinstance(profile, dict)
    }


def build_private_payload(
    local_plan: dict[str, Any],
    battery: dict[str, Any] | None = None,
    *,
    config: dict[str, Any] | None = None,
    user_profiles: dict[str, Any] | None = None,
    tariff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Polish, privacy-safe advisory payload without entity/location data."""
    rows = []
    for row in (local_plan.get("rows") if isinstance(local_plan.get("rows"), list) else [])[:48]:
        if not isinstance(row, dict):
            continue
        rows.append({
            "hour_start": row.get("hour_start"),
            "duration_minutes": int(_finite(row.get("duration_minutes")) or 0),
            "action": row.get("action"),
            "planned_power_w": _clean_number(row.get("planned_power_w"), 2),
            "soc_start_pct": _clean_number(row.get("soc_start_pct"), 2),
            "soc_end_pct": _clean_number(row.get("soc_end_pct", row.get("soc_after")), 2),
            "pv_kwh": _clean_number(row.get("pv_corrected_kwh", row.get("corrected_pv_kwh"))),
            "forecast_low_kwh": _clean_number(row.get("forecast_low_kwh")),
            "forecast_high_kwh": _clean_number(row.get("forecast_high_kwh")),
            "load_kwh": _clean_number(row.get("home_load_kwh", row.get("load_kwh"))),
            "sell_price": _clean_number(row.get("sell_price")),
            "effective_buy_price": _clean_number(row.get("effective_buy_price")),
            "net_result": _clean_number(row.get("net_result", row.get("balance_pln"))),
            "confidence": _clean_number(row.get("confidence"), 1),
            "warnings": [
                str(value)
                for value in (row.get("reason_codes") or [])
                if str(value).startswith(("limit:", "safety:"))
            ][:6],
        })
    variants = {}
    for key, value in (local_plan.get("variants") or {}).items():
        if not isinstance(value, dict):
            continue
        variants[str(key)] = {
            "benefit": _clean_number(value.get("benefit")),
            "optimized_result": _clean_number(value.get("optimized_result")),
            "comparison": value.get("comparison"),
            "recommended_write": bool(value.get("recommended_write")),
        }
    input_summary = (
        local_plan.get("input_data_summary")
        if isinstance(local_plan.get("input_data_summary"), dict)
        else {}
    )
    channels = (
        input_summary.get("channel_diagnostics")
        if isinstance(input_summary.get("channel_diagnostics"), dict)
        else {}
    )
    return {
        "schema_version": 2,
        "role": "advisory_only",
        "requested_role": str((config or {}).get("role") or "review"),
        "locale": "pl-PL",
        "timezone": "Europe/Warsaw",
        "currency": "PLN",
        "units": {"energy": "kWh", "power": "W", "price": "zł/kWh", "soc": "%"},
        "current_soc_pct": _clean_number((battery or {}).get("current_soc_pct")),
        "battery": {
            "capacity_kwh": _clean_number((battery or {}).get("capacity_kwh")),
            "effective_min_soc_pct": _clean_number((battery or {}).get("effective_min_soc_pct")),
            "power_limit_w": _clean_number((battery or {}).get("power_limit_w"), 2),
        },
        "local_plan": {
            "plan_id": local_plan.get("plan_id"),
            "selected_variant": local_plan.get("selected_variant"),
            "plan_status": local_plan.get("plan_status"),
            "optimized_result": _clean_number(local_plan.get("optimized_result")),
            "baseline_result": _clean_number(local_plan.get("baseline_result")),
            "benefit": _clean_number(local_plan.get("benefit")),
            "neutrality_threshold": _clean_number(local_plan.get("neutrality_threshold")),
            "recommended_write": bool(local_plan.get("recommended_write")),
            "variants": variants,
            "hours": rows,
        },
        "user_profiles": _private_profiles(user_profiles),
        "tariff": {
            key: deepcopy((tariff or {}).get(key))
            for key in (
                "provider", "provider_name", "plan", "plan_name", "mode",
                "price_includes_distribution", "configured",
            )
        },
        # Only non-identifying aggregate quality counters are shared. Live
        # telemetry, entity ids and raw history remain local to Home Assistant.
        "data_quality_summary": {
            "history_schema_version": input_summary.get("history_schema_version"),
            "historical_hours_supplied": int(
                _finite(input_summary.get("historical_hours_supplied")) or 0
            ),
            "channels": {
                str(name): {
                    key: deepcopy(details.get(key))
                    for key in (
                        "usable_hours", "full_hours", "partial_hours",
                        "very_low_hours", "missing_hours",
                        "average_coverage_percent", "average_quality_score",
                    )
                }
                for name, details in channels.items()
                if isinstance(details, dict)
            },
        },
        "privacy": {
            "entity_names_included": False,
            "device_names_included": False,
            "exact_location_included": False,
            "raw_history_included": False,
            "protection_enforced": True,
        },
    }


def validate_response(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Odpowiedź AI nie jest obiektem JSON")
    required = {
        "status", "summary", "plan_assessment", "confidence_adjustment",
        "best_option", "alternative", "reasons", "risks",
    }
    if set(value) != required:
        raise ValueError("Odpowiedź AI ma niezgodny zestaw pól")
    if value["status"] not in ("ok", "warning", "rejected"):
        raise ValueError("Nieprawidłowy status odpowiedzi AI")
    summary = str(value["summary"])
    if not summary or len(summary) > 1200:
        raise ValueError("Nieprawidłowe podsumowanie AI")
    if value["plan_assessment"] not in ALLOWED_ASSESSMENTS:
        raise ValueError("Nieprawidłowa ocena planu")
    adjustment = _finite(value["confidence_adjustment"])
    if adjustment is None or not -25 <= adjustment <= 10:
        raise ValueError("Nieprawidłowa korekta pewności")
    if value["best_option"] not in ALLOWED_OPTIONS:
        raise ValueError("Nieprawidłowy wariant AI")
    alternative = value["alternative"]
    if not isinstance(alternative, dict) or set(alternative) != {"enabled", "hours"} or not isinstance(alternative["enabled"], bool):
        raise ValueError("Nieprawidłowa alternatywa AI")
    if not isinstance(alternative["hours"], list) or len(alternative["hours"]) > 12:
        raise ValueError("Nieprawidłowa lista godzin alternatywy")
    hours = []
    for row in alternative["hours"]:
        if not isinstance(row, dict) or set(row) != {"start", "end", "action", "power_w"}:
            raise ValueError("Nieprawidłowa godzina alternatywy")
        start, end = str(row["start"]), str(row["end"])
        for field, text in (("start", start), ("end", end)):
            try:
                hour, minute = (int(item) for item in text.split(":", 1))
            except (ValueError, TypeError) as err:
                raise ValueError(f"Nieprawidłowy czas {field}") from err
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError(f"Nieprawidłowy czas {field}")
        action = str(row["action"])
        power = _finite(row["power_w"])
        if action not in ALLOWED_ACTIONS or power is None or not 0 <= power <= 13000:
            raise ValueError("Nieprawidłowa akcja lub moc alternatywy")
        hours.append({"start": start, "end": end, "action": action, "power_w": round(power, 2)})
    reasons = value["reasons"]
    risks = value["risks"]
    if not isinstance(reasons, list) or not isinstance(risks, list) or len(reasons) > 12 or len(risks) > 12:
        raise ValueError("Nieprawidłowe uzasadnienia lub ryzyka")
    if any(not isinstance(item, str) or len(item) > 500 for item in reasons + risks):
        raise ValueError("Nieprawidłowy tekst uzasadnienia lub ryzyka")
    return {
        "status": value["status"],
        "summary": summary,
        "plan_assessment": value["plan_assessment"],
        "confidence_adjustment": round(adjustment, 2),
        "best_option": value["best_option"],
        "alternative": {"enabled": alternative["enabled"], "hours": hours},
        "reasons": list(reasons),
        "risks": list(risks),
    }


def _extract_content(response: dict[str, Any]) -> Any:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("Odpowiedź dostawcy nie zawiera choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("Odpowiedź dostawcy nie zawiera message")
    content = message.get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("Odpowiedź dostawcy nie zawiera treści JSON")
    try:
        return json.loads(content)
    except json.JSONDecodeError as err:
        raise ValueError("Dostawca zwrócił nieprawidłowy JSON") from err


def request_body(config: dict[str, Any], payload: dict[str, Any], *, connection_test: bool = False) -> dict[str, Any]:
    role = str(config.get("role") or "review")
    role_instruction = {
        "explain": (
            "Wyjaśnij plan lokalny. Nie proponuj alternatywnych godzin; ustaw "
            "alternative.enabled na false i alternative.hours na pustą listę."
        ),
        "review": (
            "Sprawdź plan lokalny i tylko w razie rzeczywistej korzyści możesz "
            "zaproponować bezpieczną alternatywę."
        ),
        "experimental": (
            "Wykonaj pogłębioną analizę wariantów, ale traktuj ją wyłącznie "
            "jako opinię i zachowaj wszystkie lokalne ograniczenia bezpieczeństwa."
        ),
    }.get(role, "Sprawdź plan lokalny jako niezależny doradca.")
    prompt_data = (
        {
            "connection_test": True,
            "locale": "pl-PL",
            "instruction": (
                "Zwróć testową odpowiedź zgodną ze schematem bez analizowania "
                "instalacji. Wszystkie pola tekstowe zapisz po polsku."
            ),
        }
        if connection_test
        else payload
    )
    return {
        "model": config["model"],
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Jesteś polskojęzycznym doradcą analizującym plan energii. "
                    "Lokalny deterministyczny Optimizer Core jest nadrzędny, a Twoja "
                    "odpowiedź nigdy nie steruje falownikiem ani harmonogramem. "
                    f"{role_instruction} "
                    "Wartości summary, reasons i risks muszą być napisane wyłącznie "
                    "po polsku. Nazwy technicznych kluczy i wartości enum pozostaw "
                    "zgodne ze schematem. Zwróć wyłącznie JSON zgodny ze schematem."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False, separators=(",", ":"))},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": RESPONSE_SCHEMA,
        },
    }


async def request_analysis(
    session: Any,
    config: dict[str, Any],
    payload: dict[str, Any],
    *,
    connection_test: bool = False,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Call one provider with one bounded retry for transient status codes."""
    endpoint = config["endpoint"]
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    body = request_body(config, payload, connection_test=connection_test)
    started = time.monotonic()
    last_error = None
    for attempt in range(2):
        try:
            async with asyncio.timeout(timeout_seconds):
                async with session.post(endpoint, headers=headers, json=body) as response:
                    text = await response.text()
                    if response.status in (429, 502, 503) and attempt == 0:
                        retry_after = _finite(response.headers.get("Retry-After")) or 0
                        await asyncio.sleep(min(2.0, max(0.0, retry_after)))
                        continue
                    if response.status < 200 or response.status >= 300:
                        message = {
                            400: "Dostawca odrzucił format żądania",
                            401: "Błąd autoryzacji — sprawdź klucz API",
                            403: "Dostawca odmówił dostępu",
                            404: "Nie znaleziono endpointu lub modelu",
                            429: "Przekroczono limit zapytań dostawcy",
                            500: "Wewnętrzny błąd dostawcy",
                            502: "Brama dostawcy jest chwilowo niedostępna",
                            503: "Usługa dostawcy jest chwilowo niedostępna",
                        }.get(response.status, "Dostawca zwrócił błąd")
                        raise ValueError(f"{message} (HTTP {response.status})")
                    try:
                        envelope = json.loads(text)
                    except json.JSONDecodeError as err:
                        raise ValueError("Dostawca zwrócił nieprawidłową kopertę JSON") from err
                    validated = validate_response(_extract_content(envelope))
                    return {
                        "status": "ok",
                        "provider": config["provider"],
                        "model": envelope.get("model") or config["model"],
                        "response_ms": round((time.monotonic() - started) * 1000, 1),
                        "json_schema": "valid",
                        "analysis": validated,
                        "writes_performed": False,
                    }
        except (TimeoutError, ValueError, OSError) as err:
            last_error = err
            if attempt == 0 and isinstance(err, OSError):
                continue
            break
    if isinstance(last_error, TimeoutError):
        raise ValueError("Przekroczono limit czasu API") from last_error
    if isinstance(last_error, OSError):
        raise ValueError("Błąd połączenia z dostawcą AI") from last_error
    raise ValueError(str(last_error or "Nieznany błąd API"))

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "deye_energy_manager" / "ai_assistant.py"
SPEC = importlib.util.spec_from_file_location("ai_assistant_tests", MODULE_PATH)
assistant = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(assistant)


def valid_analysis():
    return {
        "status": "ok",
        "summary": "Plan lokalny jest bezpieczny.",
        "plan_assessment": "safe",
        "confidence_adjustment": -2,
        "best_option": "balanced",
        "alternative": {
            "enabled": True,
            "hours": [{"start": "20:00", "end": "21:00", "action": "sell", "power_w": 4000}],
        },
        "reasons": ["Wysoka cena sprzedaży"],
        "risks": ["Krótka historia"],
    }


def plan():
    return {
        "plan_id": "local-1",
        "selected_variant": "balanced",
        "plan_status": "proposal",
        "optimized_result": 12,
        "baseline_result": 10,
        "benefit": 2,
        "neutrality_threshold": 0.2,
        "recommended_write": True,
        "variants": {"balanced": {"benefit": 2, "optimized_result": 12, "comparison": "Lepszy", "recommended_write": True}},
        "rows": [{
            "hour_start": "2026-07-29T20:00:00+02:00",
            "duration_minutes": 60,
            "action": "sell",
            "planned_power_w": 4000,
            "soc_start_pct": 75,
            "soc_end_pct": 60,
            "pv_corrected_kwh": 0,
            "forecast_low_kwh": 0,
            "forecast_high_kwh": 0,
            "home_load_kwh": 0.5,
            "sell_price": 1.2,
            "effective_buy_price": 0.8,
            "net_result": 4.2,
            "confidence": 68,
            "reason_codes": ["optimizer:high-price", "limit:power"],
            "entity_id": "sensor.private_name",
            "location": "secret-location",
        }],
    }


class FakeResponse:
    def __init__(self, status, payload, headers=None):
        self.status = status
        self.payload = payload
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def text(self):
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, endpoint, *, headers, json):
        self.calls.append({"endpoint": endpoint, "headers": headers, "json": json})
        return self.responses.pop(0)


class AiAssistantTests(unittest.IsolatedAsyncioTestCase):
    def config(self, provider="openrouter"):
        return assistant.normalize_config({
            "enabled": True,
            "provider": provider,
            "api_key": "separate-test-key",
            "model": "test-model",
            "role": "review",
            "hourly_only": True,
            "remove_entity_names": True,
            "remove_exact_location": True,
            "max_history_hours": 0,
            **({"endpoint": "https://example.invalid/v1"} if provider == "custom" else {}),
        })

    def test_opencode_uses_official_console_endpoint_and_separate_key(self):
        config = self.config("opencode")
        self.assertEqual(
            "https://console.opencode.ai/inference/openai/v1/chat/completions",
            config["endpoint"],
        )
        self.assertEqual("separate-test-key", config["api_key"])

    def test_custom_endpoint_requires_https_and_chat_completions_is_normalized(self):
        config = self.config("custom")
        self.assertEqual("https://example.invalid/v1/chat/completions", config["endpoint"])
        with self.assertRaises(ValueError):
            assistant.normalize_config({
                "enabled": True, "provider": "custom", "endpoint": "http://localhost:1234",
                "api_key": "x", "model": "m",
            })

    def test_secret_is_redacted_and_never_in_private_payload(self):
        public = assistant.redact_config(self.config())
        self.assertEqual("***", public["api_key"])
        self.assertNotIn("separate-test-key", json.dumps(public))
        payload = assistant.build_private_payload(plan(), {"current_soc_pct": 50})
        raw = json.dumps(payload)
        self.assertNotIn("sensor.private_name", raw)
        self.assertNotIn("secret-location", raw)
        self.assertNotIn('"entity_id"', raw)
        self.assertFalse(payload["privacy"]["entity_names_included"])

    def test_private_payload_contains_only_safe_polish_review_context(self):
        payload = assistant.build_private_payload(
            plan(),
            {"current_soc_pct": 50},
            config={"role": "review"},
            user_profiles={
                "profiles": {
                    "morning_sale": {
                        "enabled": True,
                        "start": "05:00",
                        "end": "10:00",
                        "target_energy_kwh": 6,
                        "preferred_power_w": 3000,
                        "min_price": 0.4,
                        "note": "prywatna notatka",
                    },
                },
            },
            tariff={"provider_name": "PGE Dystrybucja", "plan_name": "G12w"},
        )
        self.assertEqual("pl-PL", payload["locale"])
        self.assertEqual("review", payload["requested_role"])
        self.assertEqual(3000, payload["user_profiles"]["morning_sale"]["preferred_power_w"])
        self.assertNotIn("note", payload["user_profiles"]["morning_sale"])
        self.assertEqual("PGE Dystrybucja", payload["tariff"]["provider_name"])
        self.assertTrue(payload["privacy"]["protection_enforced"])

    def test_response_schema_accepts_valid_and_rejects_unknown_fields(self):
        self.assertEqual("safe", assistant.validate_response(valid_analysis())["plan_assessment"])
        invalid = valid_analysis()
        invalid["direct_write"] = True
        with self.assertRaises(ValueError):
            assistant.validate_response(invalid)

    def test_response_rejects_power_time_and_soc_like_untrusted_values(self):
        invalid = valid_analysis()
        invalid["alternative"]["hours"][0]["power_w"] = 99999
        with self.assertRaises(ValueError):
            assistant.validate_response(invalid)
        invalid = valid_analysis()
        invalid["alternative"]["hours"][0]["start"] = "25:00"
        with self.assertRaises(ValueError):
            assistant.validate_response(invalid)

    async def test_valid_api_response_is_advisory_and_performs_no_write(self):
        envelope = {
            "model": "actual-model",
            "choices": [{"message": {"content": json.dumps(valid_analysis())}}],
        }
        session = FakeSession([FakeResponse(200, envelope)])
        local = plan()
        before = json.dumps(local, sort_keys=True)
        result = await assistant.request_analysis(
            session,
            self.config(),
            assistant.build_private_payload(local),
        )
        self.assertEqual("valid", result["json_schema"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(before, json.dumps(local, sort_keys=True))

    async def test_invalid_json_fails_without_fabricated_result(self):
        envelope = {"choices": [{"message": {"content": "not-json"}}]}
        with self.assertRaisesRegex(ValueError, "nieprawidłowy JSON"):
            await assistant.request_analysis(
                FakeSession([FakeResponse(200, envelope)]),
                self.config(),
                assistant.build_private_payload(plan()),
            )

    async def test_transient_error_has_one_bounded_retry(self):
        envelope = {"choices": [{"message": {"content": json.dumps(valid_analysis())}}]}
        session = FakeSession([
            FakeResponse(503, {"error": "busy"}, {"Retry-After": "0"}),
            FakeResponse(200, envelope),
        ])
        result = await assistant.request_analysis(session, self.config(), assistant.build_private_payload(plan()))
        self.assertEqual("ok", result["status"])
        self.assertEqual(2, len(session.calls))

    def test_request_uses_json_schema_and_contains_no_shell_or_agent_action(self):
        body = assistant.request_body(self.config(), assistant.build_private_payload(plan()))
        self.assertEqual("json_schema", body["response_format"]["type"])
        raw = json.dumps(body).lower()
        self.assertNotIn("subprocess", raw)
        self.assertNotIn("auth.json", raw)
        self.assertNotIn("write inverter", raw)
        self.assertIn("wyłącznie po polsku", body["messages"][0]["content"])

    def test_explain_role_forbids_external_alternative(self):
        config = self.config()
        config["role"] = "explain"
        body = assistant.request_body(config, assistant.build_private_payload(plan()))
        self.assertIn("alternative.enabled na false", body["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()

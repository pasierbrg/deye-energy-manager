"""Stage 5G.4D SAFE: adaptive learning, confidence and readiness contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

from test_history import history
from test_manager_logic import manager as manager_module
from test_optimizer_core import inputs as optimizer_inputs, optimizer


ROOT = Path(__file__).resolve().parents[1]
LEARNING_PATH = ROOT / "custom_components" / "deye_energy_manager" / "learning.py"
SPEC = importlib.util.spec_from_file_location("stage5g4d_learning", LEARNING_PATH)
learning = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(learning)


def _maturity(**overrides):
    values = {
        "valid_hours": 500,
        "complete_days": 20,
        "load_covered_cells": 168,
        "pv_covered_cells": 75,
        "pv_accepted_samples": 135,
        "pv_rejected_samples": 366,
        "forecast_accuracy_days": 20,
        "history_last_hour": "2026-08-13T20:00:00+02:00",
        "now": datetime(2026, 8, 13, 21, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return learning.learning_maturity(**values)


def _profile(minimum_confidence: float) -> dict:
    return {
        "enabled": True,
        "type": "sale",
        "active_days": ["2"],
        "start": "06:00",
        "end": "07:00",
        "priority": "high",
        "goal_character": "preferred",
        "allow_partial": True,
        "minimum_confidence": minimum_confidence,
        "target_energy_kwh": 1.0,
        "target_basis": "battery_to_grid",
        "min_price": 0,
        "preferred_power_w": 1000,
        "distribution_method": "best_hours",
        "min_soc_after": 20,
        "allow_earlier_grid_charge": False,
        "min_net_result": 0,
    }


def _profile_plan_inputs(minimum_confidence: float) -> dict:
    values = optimizer_inputs()
    values.update({
        "soc": 80,
        "effective_min_soc": 20,
        "load_profile_48h": [0.1] * 48,
        "load_profile_sources_48h": [
            {"source": "weekday_hour", "samples": 10} for _ in range(48)
        ],
        "learning_maturity": {"status": "stable", "label": "Profil stabilny", "score": 70, "application_ready": True},
        "learning_stage": {"status": "Plan wstępny", "confidence_cap": 35, "apply_allowed": False},
        "user_profiles": {"profiles": {"morning_sale": _profile(minimum_confidence)}},
    })
    values["sell_prices"][0][6] = 2.0
    return values


def test_fresh_install_is_bootstrap_and_not_application_ready():
    result = learning.learning_maturity(now=datetime(2026, 8, 13, tzinfo=timezone.utc))
    assert result["status"] == "bootstrap"
    assert result["score"] == 0
    assert result["application_ready"] is False


def test_existing_500_valid_hours_bootstrap_without_waiting_for_new_seven_days():
    result = _maturity()
    assert result["status"] in {"stable", "mature"}
    assert result["application_ready"] is True
    assert result["evidence"]["valid_hours"]["score"] > 99
    assert result["complete_days"] == 20


def test_learning_migration_revision_and_watermark_are_idempotent():
    raw = {
        "schema_version": history.HISTORY_SCHEMA_VERSION,
        "history": [{
            "hour": "2026-08-13T20:00:00+02:00",
            "channel_quality": {"load": {"usable_for_learning": True}},
        }],
    }
    first, changed = history.migrate_learning_payload(raw)
    second, changed_again = history.migrate_learning_payload(first)
    assert changed is True
    assert changed_again is False
    assert first == second
    assert second["learning_revision"] == 1
    assert second["history_watermark"] == "2026-08-13T20:00:00+02:00"


def test_invalid_hour_and_rejected_pv_do_not_inflate_accepted_evidence():
    before = _maturity(valid_hours=10, pv_accepted_samples=3, pv_rejected_samples=2)
    invalid = _maturity(valid_hours=10, pv_accepted_samples=3, pv_rejected_samples=3)
    assert invalid["valid_hours"] == before["valid_hours"]
    assert invalid["pv_accepted_samples"] == before["pv_accepted_samples"]
    assert invalid["score"] <= before["score"]


def test_seasonal_pv_evidence_uses_separate_month_hour_cells():
    january = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    july = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    profile = learning.update_pv_profile(
        {}, moment=january, forecast_kwh=2, actual_kwh=1,
        flags={"pv_curtailed": False}, complete=True,
    )
    profile = learning.update_pv_profile(
        profile, moment=july, forecast_kwh=2, actual_kwh=3,
        flags={"pv_curtailed": False}, complete=True,
    )
    january_value, january_factor, _ = learning.corrected_pv_forecast(
        profile, moment=january, forecast_kwh=2,
    )
    july_value, july_factor, _ = learning.corrected_pv_forecast(
        profile, moment=july, forecast_kwh=2,
    )
    assert set(profile["cells"]) == {"01-12", "07-12"}
    assert january_factor < 1 < july_factor
    assert january_value < 2 < july_value


def test_new_maturity_is_proportional_and_legacy_day_cap_no_longer_applies():
    values = optimizer_inputs()
    values.update({
        "recorded_days": 6,
        "learning_stage": {"status": "Plan wstępny", "confidence_cap": 35, "apply_allowed": False},
        "learning_maturity": {"status": "stable", "label": "Profil stabilny", "score": 99, "application_ready": True},
        "load_profile_sample_count": 500,
        "load_profile_covered_cells": 168,
        "load_profile_total_cells": 168,
        "pv_profile_sample_count": 135,
        "pv_profile_rejected_count": 366,
        "pv_profile_covered_cells": 75,
        "pv_profile_total_cells": 288,
        "osd_available_hours": 48,
    })
    result = optimizer.build_energy_plan(values, "balanced")
    assert result["plan_confidence"] > 35
    assert result["learning_maturity"]["score"] == 99
    assert result["data_quality"]["score"] != result["learning_maturity"]["score"]


def test_low_confidence_candidate_remains_preview_with_explicit_reason(monkeypatch):
    values = _profile_plan_inputs(50)
    monkeypatch.setattr(optimizer, "_confidence", lambda *_args, **_kwargs: (35.0, {
        "prices": 100, "solcast": 100, "learning": 70, "load_profile": 100,
        "pv_profile": 30, "entities": 100, "soc": 100, "tariff_osd": 100,
    }))
    result = optimizer.build_energy_plan(values, "balanced")
    row = result["rows"][6]
    assert row["candidate_action"] == "sell"
    assert row["candidate_energy_kwh"] > 0
    assert row["actual_confidence"] == 35
    assert row["required_confidence"] == 50
    assert row["proposed"] is False
    assert row["proposal_block_reason"] == "confidence_below_profile_minimum"
    assert result["execution_readiness"]["by_day"]["today"]["status"] == "preview"


def test_confidence_above_profile_minimum_is_confirmable_but_not_auto_applied(monkeypatch):
    values = _profile_plan_inputs(50)
    monkeypatch.setattr(optimizer, "_confidence", lambda *_args, **_kwargs: (70.0, {
        "prices": 100, "solcast": 100, "learning": 70, "load_profile": 100,
        "pv_profile": 50, "entities": 100, "soc": 100, "tariff_osd": 100,
    }))
    result = optimizer.build_energy_plan(values, "balanced")
    row = result["rows"][6]
    assert row["proposed"] is True
    assert result["execution_readiness"]["by_day"]["today"]["status"] == "confirmable"
    assert result["confirmation_required"] is True


def test_material_live_deviation_buckets_filter_noise_but_keep_real_change():
    bucket = manager_module.DeyeEnergyManagerRuntime._material_deviation_bucket
    assert bucket(1010, 1.0) == 0.0
    assert bucket(1100, 1.0) == 0.0
    assert bucket(1500, 1.0) == 0.5
    first = manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
        "current_hour_remaining_minutes": 59,
        "current_hour_partial": {"elapsed_minutes": 1, "pv_kwh": 0.01},
        "live_state": {"timestamp": "a", "pv_power_w": 1010, "pv_forecast_deviation": 0.0},
    })
    noisy = manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
        "current_hour_remaining_minutes": 42,
        "current_hour_partial": {"elapsed_minutes": 18, "pv_kwh": 0.4},
        "live_state": {"timestamp": "b", "pv_power_w": 1100, "pv_forecast_deviation": 0.0},
    })
    material = manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
        "live_state": {"timestamp": "c", "pv_power_w": 1500, "pv_forecast_deviation": 0.5},
    })
    assert first == noisy
    assert first != material
    sixty_noise_snapshots = {
        str(manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
            "soc": 50,
            "pv_forecast": [10, 11],
            "current_hour_remaining_minutes": 60 - index,
            "live_state": {
                "timestamp": str(index),
                "pv_power_w": 1000 + index,
                "pv_forecast_deviation": 0.0,
            },
        }))
        for index in range(60)
    }
    assert len(sixty_noise_snapshots) == 1
    material_soc = manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
        "soc": 51, "pv_forecast": [10, 11],
        "live_state": {"pv_forecast_deviation": 0.0},
    })
    material_solcast = manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
        "soc": 50, "pv_forecast": [12, 11],
        "live_state": {"pv_forecast_deviation": 0.0},
    })
    base = manager_module.DeyeEnergyManagerRuntime._semantic_optimizer_inputs({
        "soc": 50, "pv_forecast": [10, 11],
        "live_state": {"pv_forecast_deviation": 0.0},
    })
    assert base != material_soc
    assert base != material_solcast

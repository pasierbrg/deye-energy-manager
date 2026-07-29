from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components" / "deye_energy_manager" / "learning.py"
SPEC = importlib.util.spec_from_file_location("deye_learning_test", MODULE)
learning = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = learning
assert SPEC.loader is not None
SPEC.loader.exec_module(learning)


class LoadProfileTests(unittest.TestCase):
    def test_profile_has_independent_weekday_hour_cells(self):
        profile = {}
        monday = datetime(2026, 7, 27, 7, tzinfo=timezone.utc)
        saturday = datetime(2026, 8, 1, 7, tzinfo=timezone.utc)
        profile = learning.update_load_profile(profile, moment=monday, load_kwh=0.5, complete=True, quality_score=100)
        profile = learning.update_load_profile(profile, moment=saturday, load_kwh=1.2, complete=True, quality_score=100)
        weekday, source_a, _ = learning.forecast_load(profile, monday)
        weekend, source_b, _ = learning.forecast_load(profile, saturday)
        self.assertEqual(source_a, "weekday_hour")
        self.assertEqual(source_b, "weekday_hour")
        self.assertEqual(weekday, 0.5)
        self.assertEqual(weekend, 1.2)
        self.assertEqual(len(profile["cells"]), 2)

    def test_incomplete_or_low_quality_hour_is_rejected(self):
        moment = datetime(2026, 7, 27, 7, tzinfo=timezone.utc)
        profile = learning.update_load_profile({}, moment=moment, load_kwh=0.5, complete=False, quality_score=100)
        profile = learning.update_load_profile(profile, moment=moment, load_kwh=0.5, complete=True, quality_score=40)
        self.assertEqual(profile["accepted_samples"], 0)
        self.assertEqual(profile["rejected_samples"], 2)
        self.assertEqual(profile["cells"], {})

    def test_fallback_prefers_same_day_type_before_all_days(self):
        monday = datetime(2026, 7, 27, 8, tzinfo=timezone.utc)
        tuesday = datetime(2026, 7, 28, 8, tzinfo=timezone.utc)
        profile = learning.update_load_profile({}, moment=monday, load_kwh=0.7, complete=True, quality_score=100)
        value, source, samples = learning.forecast_load(profile, tuesday)
        self.assertEqual(source, "day_type_hour")
        self.assertEqual(value, 0.7)
        self.assertEqual(samples, 1)


class PvLearningTests(unittest.TestCase):
    def test_curtailed_hour_is_counted_but_never_lowers_correction(self):
        moment = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
        flags = learning.pv_quality_flags(
            battery_soc=100,
            work_mode="Zero Export To Load",
            grid_available=True,
            actual_power_w=500,
            inverter_limit_w=10000,
            sensor_stale=False,
            manual_override=False,
        )
        profile = learning.update_pv_profile(
            {},
            moment=moment,
            forecast_kwh=5,
            actual_kwh=0.5,
            flags=flags,
            complete=True,
        )
        self.assertTrue(flags["pv_curtailed"])
        self.assertEqual(profile["accepted_samples"], 0)
        self.assertEqual(profile["rejected_samples"], 1)
        self.assertEqual(profile["curtailed_hours"], 1)
        corrected, factor, samples = learning.corrected_pv_forecast(profile, moment=moment, forecast_kwh=5)
        self.assertEqual(corrected, 5)
        self.assertEqual(factor, 1)
        self.assertEqual(samples, 0)

    def test_valid_samples_learn_bounded_gradual_hourly_correction(self):
        moment = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
        profile = {}
        for day in range(5):
            profile = learning.update_pv_profile(
                profile,
                moment=moment.replace(day=27 + day),
                forecast_kwh=4,
                actual_kwh=3,
                flags={"pv_curtailed": False},
                complete=True,
            )
        corrected, factor, samples = learning.corrected_pv_forecast(profile, moment=moment, forecast_kwh=4)
        self.assertEqual(samples, 5)
        self.assertGreater(factor, 0.9)
        self.assertLess(factor, 1.0)
        self.assertLess(corrected, 4)

    def test_night_or_tiny_forecast_is_not_corrected(self):
        moment = datetime(2026, 7, 27, 1, tzinfo=timezone.utc)
        corrected, factor, samples = learning.corrected_pv_forecast({}, moment=moment, forecast_kwh=0.01)
        self.assertEqual(corrected, 0.01)
        self.assertEqual(factor, 1)
        self.assertEqual(samples, 0)


class LearningStageTests(unittest.TestCase):
    def test_required_stage_caps_and_apply_rules(self):
        cases = [
            (0, "Zbieranie danych", 25, False),
            (3, "Plan wstępny", 35, False),
            (7, "Wstępne uczenie", 70, True),
            (21, "Profil podstawowy gotowy", 85, True),
            (60, "Profil rozszerzony", 100, True),
        ]
        for days, label, cap, apply_allowed in cases:
            with self.subTest(days=days):
                stage = learning.learning_stage(days)
                self.assertEqual(stage["status"], label)
                self.assertEqual(stage["confidence_cap"], cap)
                self.assertEqual(stage["apply_allowed"], apply_allowed)


if __name__ == "__main__":
    unittest.main()

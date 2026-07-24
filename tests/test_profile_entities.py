from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NUMBER_SOURCE = (ROOT / "custom_components" / "deye_energy_manager" / "number.py").read_text(encoding="utf-8")
SWITCH_SOURCE = (ROOT / "custom_components" / "deye_energy_manager" / "switch.py").read_text(encoding="utf-8")
SELECT_SOURCE = (ROOT / "custom_components" / "deye_energy_manager" / "select.py").read_text(encoding="utf-8")
INIT_SOURCE = (ROOT / "custom_components" / "deye_energy_manager" / "__init__.py").read_text(encoding="utf-8")
ENTITY_SOURCE = (ROOT / "custom_components" / "deye_energy_manager" / "entity.py").read_text(encoding="utf-8")


class ProfileHelperEntityContractTests(unittest.TestCase):
    """Ensure profile helper entities are created, enabled and publish runtime values."""

    def test_missing_charge_current_number_is_created(self):
        self.assertIn(
            'DeyeManagerNumber(runtime, "charge_profile_charge_current", "Charge profile battery charge current", "charge_profile_charge_current", 0, 240, 5, "A")',
            NUMBER_SOURCE,
        )

    def test_missing_normal_profile_tou_soc_number_is_created(self):
        self.assertIn(
            'DeyeManagerNumber(runtime, "normal_profile_tou_soc", "Normal profile Deye TOU SOC", "normal_profile_tou_soc", 0, 100, 1, "%")',
            NUMBER_SOURCE,
        )

    def test_missing_grid_enabled_switch_is_created(self):
        self.assertIn(
            'DeyeManagerSwitch(runtime, "charge_profile_grid_enabled", "Charge profile grid charge", "charge_profile_grid_enabled")',
            SWITCH_SOURCE,
        )

    def test_missing_normal_profile_mode_select_is_created(self):
        self.assertIn(
            'DeyeNormalProfileModeSelect(runtime)',
            SELECT_SOURCE,
        )
        self.assertIn('"normal_profile_mode"', SELECT_SOURCE)

    def test_base_entity_does_not_force_registry_enabled_default(self):
        # Setting this in the base class would affect every entity and is not
        # needed; the HA default is already True for newly registered entities.
        self.assertNotIn("_attr_entity_registry_enabled_default", ENTITY_SOURCE)

    def test_unique_id_is_stable_entry_id_based(self):
        self.assertIn('self._attr_unique_id = f"{runtime.entry_id}_{key}"', ENTITY_SOURCE)

    def test_integration_does_not_auto_enable_entities(self):
        # Automatic re-enabling would override user/system choices.
        self.assertNotIn("_ensure_profile_entities_enabled", INIT_SOURCE)
        self.assertNotIn("disabled_by", INIT_SOURCE)
        self.assertNotIn("async_migrate_entry", INIT_SOURCE)
        self.assertNotIn("entity_registry", INIT_SOURCE)

    def test_charge_entities_publish_runtime_values(self):
        for attr in (
            "charge_profile_charge_current",
            "charge_profile_discharge_current",
            "charge_profile_grid_charge_current",
            "charge_profile_target_soc",
        ):
            self.assertIn(f'"{attr}"', NUMBER_SOURCE)
        self.assertIn("return getattr(self.runtime, self.attr)", NUMBER_SOURCE)

    def test_normal_profile_entities_publish_runtime_values(self):
        for attr in (
            "normal_profile_sell_power",
            "normal_profile_discharge_current",
            "normal_profile_charge_current",
            "normal_profile_grid_charge_current",
            "normal_profile_tou_soc",
        ):
            self.assertIn(f'"{attr}"', NUMBER_SOURCE)
        self.assertIn("return getattr(self.runtime, self.attr)", NUMBER_SOURCE)

    def test_normal_profile_mode_select_publishes_runtime_mode(self):
        self.assertIn("return self.runtime.normal_profile_physical_work_mode", SELECT_SOURCE)

    def test_grid_enabled_switch_publishes_runtime_flag(self):
        self.assertIn('return bool(getattr(self.runtime, self.attr))', SWITCH_SOURCE)

    def test_normal_profile_number_edit_calls_save_normal_profile(self):
        self.assertIn("await self.runtime.async_save_normal_profile(values)", NUMBER_SOURCE)
        self.assertIn("self.attr.startswith(\"normal_profile_\")", NUMBER_SOURCE)

    def test_normal_profile_partial_update_keeps_other_fields(self):
        # The number helper builds a full profile dict from current runtime values
        # and only replaces the edited field.
        self.assertIn("field_map[self.attr]: value", NUMBER_SOURCE)
        for key in ("sell_power", "discharge_current", "charge_current", "grid_charge_current", "tou_soc"):
            self.assertIn(f'"{key}": self.runtime.normal_profile_{key}', NUMBER_SOURCE)

    def test_charge_profile_number_edit_calls_save_charge_profile(self):
        self.assertIn("await self.runtime.async_save_charge_profile({", NUMBER_SOURCE)

    def test_services_use_dedicated_profile_savers(self):
        self.assertIn("await runtime.async_save_charge_profile(dict(call.data))", INIT_SOURCE)
        self.assertIn("await runtime.async_save_normal_profile(dict(call.data))", INIT_SOURCE)


if __name__ == "__main__":
    unittest.main()

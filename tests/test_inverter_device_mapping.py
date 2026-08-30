from pathlib import Path
import hashlib
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG_FLOW = ROOT / "custom_components" / "deye_energy_manager" / "config_flow.py"
PROVIDER = ROOT / "custom_components" / "deye_energy_manager" / "inverter_provider.py"
CARD_SOURCE = ROOT / "custom_components" / "deye_energy_manager" / "www" / "deye-energy-manager-card.js"
CARD_COPY = ROOT / "www" / "deye-energy-manager-card.js"


class InverterDeviceMappingSourceTests(unittest.TestCase):
    def test_wizard_requires_a_concrete_home_assistant_device(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        self.assertIn("async_step_inverter_device", source)
        self.assertIn("selector.DeviceSelector", source)
        self.assertIn("entry.device_id == device_id", source)
        self.assertIn("_mapping_device_issues", source)

    def test_discovery_is_filtered_before_provider_tokens_are_applied(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        self.assertIn("def _discovery_states", source)
        self.assertIn("state.entity_id in allowed", source)
        self.assertIn("PROVIDER_ENTITY_TOKENS", source)
        self.assertIn("Solarman: całkowita moc sieci", (ROOT / "custom_components" / "deye_energy_manager" / "manager.py").read_text(encoding="utf-8"))

    def test_provider_profiles_keep_read_only_addon_and_native_tou_presets_separate(self):
        source = PROVIDER.read_text(encoding="utf-8")
        self.assertIn('"Solarman"', source)
        self.assertIn('"Sunsynk"', source)
        self.assertIn("native_tou=False", source)
        self.assertIn("basic_control=False", source)
        self.assertIn('"Grid"', source)
        self.assertIn('"Allow Grid"', source)
        self.assertNotIn('"Week"', source)

    def test_native_tou_providers_include_lewa_reka_in_tou_wizard(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        self.assertIn("if not provider_profile(provider).native_tou:", source)
        self.assertIn("if provider_profile(provider).native_tou:", source)
        self.assertNotIn(
            "provider != PROVIDER_LEWA_REKA and provider_profile(provider).native_tou",
            source,
        )

    def test_tou_wizard_maps_only_six_physical_slots(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        tou_fields = source[source.index("TOU_FIELDS = tuple("):source.index(
            "ENTITY_SPECS[CONF_WORK_MODE_AUX_ENTITY]"
        )]
        self.assertIn('for index in range(1, 7)', tou_fields)
        self.assertIn('for kind in ("start", "soc", "grid")', tou_fields)
        self.assertNotIn("CONF_TOU_ENABLE_ENTITY", tou_fields)

    def test_provider_discovery_never_autofills_global_tou_control(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        provider_tokens = source[source.index("PROVIDER_ENTITY_TOKENS"):source.index(
            "def select_with_labels"
        )]
        self.assertNotIn("CONF_TOU_ENABLE_ENTITY", provider_tokens)
        self.assertNotIn("use timer", provider_tokens.lower())

    def test_pinned_deye_mqtt_profile_is_read_only(self):
        source = PROVIDER.read_text(encoding="utf-8")
        self.assertIn('"Deye Inverter MQTT"', source)
        self.assertIn(
            "https://github.com/kbialek/deye-inverter-mqtt/tree/"
            "0fd4b4d6416f93118829fa7c133c1533bb6440f2",
            source,
        )
        profile = source[source.index("PROVIDER_DEYE_ADDON: ProviderProfile("):source.index(
            "PROVIDER_CUSTOM: ProviderProfile("
        )]
        self.assertIn("native_tou=False", profile)
        self.assertIn("basic_control=False", profile)

    def test_partial_provider_mapping_is_warning_not_save_blocker(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        self.assertIn('errors = {"confirm": "entity_from_other_device"} if device_issues else {}', source)
        self.assertNotIn('and not provider_missing:', source)
        self.assertIn('marker = vol.Optional(key, default=default) if default else vol.Optional(key)', source)

    def test_empty_optional_entity_has_no_invalid_empty_default(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        self.assertIn("default = self._entity_default(key)", source)
        self.assertNotIn("vol.Optional(key, default=self._entity_default(key))", source)

    def test_device_safety_checks_only_explicit_foreign_device_assignments(self):
        source = CONFIG_FLOW.read_text(encoding="utf-8")
        self.assertIn("entry is not None and entry.device_id and entry.device_id != device_id", source)
        self.assertIn("(*INVERTER_FIELDS, *TOU_FIELDS, *ENERGY_DETAIL_FIELDS)", source)
        self.assertNotIn("entity_id not in allowed", source)


class CardSourceContractTests(unittest.TestCase):
    def test_card_source_has_no_global_tou_dependency(self):
        source = CARD_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("tou_enable_entity", source)
        self.assertIsNone(re.search(r"switch\.deye_inverter_time_of_use\b", source))
        self.assertIsNone(re.search(r"\buse_timer\b", source))
        self.assertIn("Deye Time Of Use", source)
        self.assertNotIn("deye_inverter_time_of_use_", source)

    def test_card_source_copies_are_identical(self):
        self.assertEqual(
            hashlib.sha256(CARD_SOURCE.read_bytes()).hexdigest(),
            hashlib.sha256(CARD_COPY.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()

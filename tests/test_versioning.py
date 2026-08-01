from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseVersionTests(unittest.TestCase):
    def test_backend_manifest_is_079(self):
        manifest = json.loads(
            (ROOT / "custom_components" / "deye_energy_manager" / "manifest.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual("0.7.9", manifest["version"])

    def test_frontend_copies_and_versions_are_consistent(self):
        paths = (
            ROOT / "custom_components" / "deye_energy_manager" / "www" / "deye-energy-manager-card.js",
            ROOT / "www" / "deye-energy-manager-card.js",
        )
        self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
        source = paths[0].read_text(encoding="utf-8-sig")
        self.assertTrue(source.startswith("// Resource revision: v=0.7.9.11"))
        self.assertIn('version: "0.7.9"', source)
        self.assertIn('integration_version || "0.7.9"', source)
        self.assertIn("Deye Energy Manager 0.7.9", source)
        self.assertIn("karta 0.7.9 (rewizja zasobu v=0.7.9.11)", source)

    def test_docs_and_dashboard_use_current_release(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        install = (ROOT / "INSTALL_PL.md").read_text(encoding="utf-8-sig")
        dashboard = (ROOT / "dashboard" / "energy_manager.yaml").read_text(encoding="utf-8-sig")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
        self.assertIn("version-0.7.9", readme)
        self.assertIn("deye-energy-manager-card.js?v=0.7.9.11", readme)
        self.assertIn("Deye Energy Manager 0.7.9", install)
        self.assertIn("deye-energy-manager-card.js?v=0.7.9.11", install)
        self.assertIn("(v=0.7.9.11)", dashboard)
        self.assertIn("## [0.7.9]", changelog)

    def test_target_release_identity_is_consistent(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "INSTALL_PL.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        combined = "\n".join((readme, install, changelog))
        self.assertIn("Deye Energy Manager 0.7.9", combined)
        self.assertIn("v=0.7.9.11", combined)
        for stale in ("v=24", "v=25", "v=26", "v=078", "v=079", "v=0.7.7", "v=0.7.8"):
            self.assertNotIn(f"deye-energy-manager-card.js?{stale}", combined)


if __name__ == "__main__":
    unittest.main()

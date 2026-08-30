"""Execute the dependency-free Stage 5G.4B frontend contract checks."""

from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_stage5g4b_core_action_contract_frontend_round_trip():
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "test_stage5g4b_card.js")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")

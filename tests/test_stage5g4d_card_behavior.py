from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_stage5g4d_card_behavior_contracts():
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "test_stage5g4d_card.js")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

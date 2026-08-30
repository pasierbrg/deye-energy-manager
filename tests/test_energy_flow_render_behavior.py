import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_energy_flow_render_behavior() -> None:
    subprocess.run(
        ["node", str(ROOT / "tests" / "test_energy_flow_render.js")],
        cwd=ROOT,
        check=True,
    )

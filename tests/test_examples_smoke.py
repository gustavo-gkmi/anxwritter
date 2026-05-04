"""Smoke test: the public examples build clean.

The bundled `examples/investigation_chart.py` is the canonical user-facing
usage walkthrough. Any breaking change to the public API should fail here
before it reaches users.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture(scope="module")
def investigation_module():
    sys.path.insert(0, str(EXAMPLES_DIR.parent))
    try:
        mod = importlib.import_module("examples.investigation_chart")
    finally:
        sys.path.pop(0)
    return mod


def test_investigation_chart_builds(investigation_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    chart = investigation_module.build()
    path = chart.to_anx(tmp_path / "investigation")

    assert Path(path).exists(), f"Expected .anx file at {path}"
    assert Path(path).stat().st_size > 0


def test_investigation_import_has_no_side_effects(tmp_path, monkeypatch):
    """Importing the module must NOT run the build.

    The ``if __name__ == '__main__':`` block is the only place that calls
    `build()` — this test would fail if someone refactored the module to
    run the build at import time.
    """
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(EXAMPLES_DIR.parent))
    try:
        # Force a fresh import
        sys.modules.pop("examples.investigation_chart", None)
        importlib.import_module("examples.investigation_chart")
    finally:
        sys.path.pop(0)

    output_dir = tmp_path / "output"
    if output_dir.exists():
        assert list(output_dir.iterdir()) == [], (
            "examples/investigation_chart.py executed a build at import time"
        )

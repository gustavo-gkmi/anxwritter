"""Golden-master characterization: pin .anx output across refactors.

Builds a representative set of charts (the equivalence specs plus the bundled
examples), normalizes each one's XML, and asserts a stable ``sha256`` per chart
against a committed baseline.

This is the cross-commit byte-stability anchor. ``test_determinism.py`` only
compares two builds of the *same* code, so it cannot catch a refactor that
changes output *consistently*; this test can. A behavior-preserving refactor
MUST NOT change any digest here.

Normalization
-------------
``canonical_xml`` (from ``tests.helpers.chart_equivalence``) re-parses the
document, which already drops the XML declaration and the ``Built with ...``
comment (so the package version never leaks into the digest) and sorts
attributes. The only remaining volatile content is the ``Origin`` timestamp
defaulted from ``datetime.now()`` in ``builder._emit_summary`` — those few
attributes are blanked before hashing.

Re-blessing
-----------
If output changes *intentionally*, regenerate the map and review the diff::

    uv run --extra dev python -m tests.test_golden_digest

Paste the printed ``EXPECTED`` body below. Never re-bless to make a red pure
refactor go green — investigate the digest change first.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

import pytest

from anxwritter import ANXChart
from tests.fixtures.equivalence_specs import ALL_SPECS, build_via_from_dict
from tests.helpers.chart_equivalence import canonical_xml

_REPO_ROOT = Path(__file__).parent.parent

# Origin attributes defaulted from datetime.now() in builder._emit_summary.
_VOLATILE_ORIGIN_ATTRS = ("CreatedDate", "LastSaveDate", "LastPrintDate")


def _stable_xml(chart: ANXChart) -> str:
    """Canonical XML with volatile Origin timestamps blanked, for hashing."""
    root = ET.fromstring(canonical_xml(chart))
    for origin in root.iter("Origin"):
        for attr in _VOLATILE_ORIGIN_ATTRS:
            if attr in origin.attrib:
                origin.set(attr, "<volatile>")
    return ET.tostring(root, encoding="unicode")


def _digest(chart: ANXChart) -> str:
    return hashlib.sha256(_stable_xml(chart).encode("utf-8")).hexdigest()


def _example_charts() -> Dict[str, ANXChart]:
    """Build the bundled example charts (no files written — build() only)."""
    sys.path.insert(0, str(_REPO_ROOT))
    try:
        inv = importlib.import_module("examples.investigation_chart")
        ls = importlib.import_module("examples.link_styling")
        ds = importlib.import_module("examples.display_synthesizers_example")
    finally:
        sys.path.pop(0)
    charts: Dict[str, ANXChart] = {
        "example:investigation_chart": inv.build(),
        "example:link_styling": ls.build(),
    }
    for name, builder in ds.BUILDERS.items():
        charts[f"example:display_synth:{name}"] = builder()
    return charts


def _all_charts() -> Dict[str, ANXChart]:
    charts: Dict[str, ANXChart] = {
        f"spec:{name}": build_via_from_dict(spec) for name, spec in ALL_SPECS.items()
    }
    charts.update(_example_charts())
    return charts


# Baseline digests captured at Phase 0 (refactor start). Regenerate only via the
# documented re-bless flow in this module's docstring.
EXPECTED: Dict[str, str] = {
    "example:display_synth:display_attribute_combo": "6015d63d205f04e51c3ee086351bac4bc794ee5070fd1b207ca009d5e43246e7",
    "example:display_synth:display_date_range": "3f90f3d7a507a813152355013f666b689bfa8819cc15361203a580dbe42a3ffb",
    "example:display_synth:display_label_per_type": "cb6a17e567869f4b566fef12ff9741d3680b49a34b3f54ea795190ce2d37ee83",
    "example:display_synth:display_single_date": "97d22c2a43f12bbf7fbf90ee1300b8229c1ae3766530ff53e7ab91066b6e2051",
    "example:investigation_chart": "5c68eca074322ef1c477d698d82902407414c6b9493eba5b4dad62edef995570",
    "example:link_styling": "a83ccea58c533cbd3f83e57f75c4efc447882eb1d8425bfa122681910a618b24",
    "spec:ENTITIES_ONLY": "f16f55c4a51f92d0f8ac854bfd3575b25e6b83241a6dc8bbd41f970951e037b1",
    "spec:FULL": "e96b586d0334853f5f07b9d123a891a0c353917a8de42cfeae0ddbd49209948b",
    "spec:REGISTRY_ONLY": "b21483e068c2bbd009a6e15ba613d7d6a1079c343f3503a95f8358deee026d13",
    "spec:SETTINGS_ONLY": "c982b6fe1a2d6a571088f01a60a4f0255905abc28cd1da9dd96b90c93cccb45a",
}


@pytest.fixture(scope="module")
def digests() -> Dict[str, str]:
    return {name: _digest(chart) for name, chart in _all_charts().items()}


def test_golden_no_drift(digests: Dict[str, str]) -> None:
    """Every produced chart has a pinned digest and vice-versa (no silent drift)."""
    produced, pinned = set(digests), set(EXPECTED)
    assert produced == pinned, (
        f"golden set drift — only produced: {sorted(produced - pinned)}; "
        f"only pinned: {sorted(pinned - produced)}"
    )


def test_golden_digests_match(digests: Dict[str, str]) -> None:
    """Output is byte-stable vs the committed baseline (modulo volatile timestamps)."""
    mismatches = {
        name: (got, EXPECTED.get(name))
        for name, got in digests.items()
        if got != EXPECTED.get(name)
    }
    assert not mismatches, (
        "ANX output changed vs the golden baseline (digest mismatch). A pure "
        "refactor must not change output — investigate before re-blessing.\n"
        + "\n".join(f"  {n}: got {g} expected {e}" for n, (g, e) in sorted(mismatches.items()))
    )


def _generate() -> None:
    print("EXPECTED: Dict[str, str] = {")
    for name, chart in sorted(_all_charts().items()):
        print(f"    {name!r}: {_digest(chart)!r},")
    print("}")


if __name__ == "__main__":
    _generate()

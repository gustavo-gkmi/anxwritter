"""Determinism tests.

Prove chart.to_xml() is deterministic: same spec → same bytes, repeatable.
Catches nondeterministic dict iteration, random ID generation, time leakage,
and accidental mutation of inputs during build.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from anxwritter import ANXChart, Icon, Link

from tests.fixtures import equivalence_specs as specs
from tests.helpers.chart_equivalence import (
    canonical_xml,
    chart_state_snapshot,
)


SPECS = [
    ("ENTITIES_ONLY", specs.ENTITIES_ONLY_SPEC),
    ("FULL", specs.FULL_SPEC),
]


@pytest.mark.parametrize("spec_name,spec", SPECS)
class TestXmlDeterminism:
    def test_same_chart_xml_stable_across_calls(self, spec_name, spec):
        """Two to_xml() calls on the same instance must be byte-identical."""
        chart = specs.build_via_from_dict(spec)
        first = chart.to_xml()
        second = chart.to_xml()
        assert first == second, (
            f"{spec_name}: to_xml() on the same chart instance diverged "
            f"between calls. Something is mutating during build."
        )

    def test_two_fresh_charts_produce_same_xml(self, spec_name, spec):
        """Two freshly-built charts from the same spec must match byte-for-byte."""
        c1 = specs.build_via_from_dict(spec)
        c2 = specs.build_via_from_dict(spec)
        assert c1.to_xml() == c2.to_xml(), (
            f"{spec_name}: fresh charts from the same spec produced different "
            f"XML. Process-level nondeterminism (random IDs, dict ordering)."
        )

    def test_canonical_xml_stable_across_calls(self, spec_name, spec):
        chart = specs.build_via_from_dict(spec)
        assert canonical_xml(chart) == canonical_xml(chart)


@pytest.mark.parametrize("spec_name,spec", SPECS)
class TestStateDeterminism:
    def test_state_snapshot_stable_across_calls(self, spec_name, spec):
        chart = specs.build_via_from_dict(spec)
        s1 = chart_state_snapshot(chart)
        s2 = chart_state_snapshot(chart)
        assert s1 == s2, (
            f"{spec_name}: chart_state_snapshot() changed between reads. "
            f"Internal state is being mutated on read."
        )

    def test_state_stable_after_to_xml(self, spec_name, spec):
        """Building XML must not mutate the internal state snapshot."""
        chart = specs.build_via_from_dict(spec)
        before = chart_state_snapshot(chart)
        chart.to_xml()
        after = chart_state_snapshot(chart)
        assert before == after, (
            f"{spec_name}: to_xml() mutated internal chart state."
        )


@pytest.mark.parametrize("spec_name,spec", SPECS)
class TestInputMutation:
    def test_from_dict_does_not_mutate_source_spec(self, spec_name, spec):
        """from_dict must not write back into the user's input dict."""
        pristine = copy.deepcopy(spec)
        mutable = copy.deepcopy(spec)
        ANXChart.from_dict(mutable)
        assert pristine == mutable, (
            f"{spec_name}: from_dict mutated its input dict. "
            f"Users passing shared config dicts will hit aliasing bugs."
        )

    def test_to_xml_does_not_mutate_typed_entity(self, spec_name, spec):
        """Building XML must not mutate Icon/Link objects the user constructed."""
        # Skip if there are no icons in the spec
        icons_data = spec.get("entities", {}).get("icons", [])
        if not icons_data:
            pytest.skip("no icons in spec")

        first_icon_dict = {
            k: v for k, v in icons_data[0].items() if v is not None
        }
        first_icon_dict.pop("cards", None)  # cards would need Card() reconstruction
        first_icon_dict.pop("attributes", None)  # attributes dict would be aliased

        original_icon = Icon(**first_icon_dict)
        reference_snapshot = dataclasses.asdict(
            Icon(**first_icon_dict)  # independent copy
        )

        chart = ANXChart()
        chart.add(original_icon)
        # Add a partner so we can add a link
        chart.add(Icon(id="__partner__", type="X"))
        chart.add_link(from_id=original_icon.id, to_id="__partner__", type="Rel")
        chart.to_xml()

        after_snapshot = dataclasses.asdict(original_icon)
        assert after_snapshot == reference_snapshot, (
            f"{spec_name}: to_xml() mutated the user's Icon instance. "
            f"Diff in fields: "
            f"{[k for k in reference_snapshot if reference_snapshot[k] != after_snapshot.get(k)]}"
        )


class TestNegativeGuardrails:
    def test_comparator_rejects_mutated_bytes(self):
        """Sanity check: two different charts must NOT compare equal."""
        c1 = specs.build_via_from_dict({"entities": {"icons": [{"id": "A", "type": "T"}]}})
        c2 = specs.build_via_from_dict({"entities": {"icons": [{"id": "B", "type": "T"}]}})
        assert c1.to_xml() != c2.to_xml()

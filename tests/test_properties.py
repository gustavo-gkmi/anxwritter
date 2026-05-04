"""Property-based tests with Hypothesis.

Random-spec smoke testing. Finds edge cases we'd never write by hand
(unicode in labels, extreme attribute values, empty-but-present sections,
entity-ID collisions at construction time).
"""

from __future__ import annotations

import dataclasses

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, HealthCheck

from anxwritter import ANXChart, Settings
from anxwritter.errors import ANXValidationError

from tests.fixtures.strategies import chart_spec_strategy, settings_dict_strategy
from tests.helpers.chart_equivalence import canonical_xml


_DEFAULT_SETTINGS = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


class TestFromDictSmoke:
    @_DEFAULT_SETTINGS
    @given(spec=chart_spec_strategy())
    def test_from_dict_never_crashes(self, spec):
        """A generated valid spec always builds a chart without raising."""
        chart = ANXChart.from_dict(spec)
        assert chart is not None
        assert len(chart._entities) == len(spec["entities"]["icons"])
        assert len(chart._links) == len(spec["links"])

    @_DEFAULT_SETTINGS
    @given(spec=chart_spec_strategy())
    def test_valid_spec_has_no_validation_errors(self, spec):
        chart = ANXChart.from_dict(spec)
        errors = chart.validate()
        assert errors == [], (
            f"generated valid spec produced validation errors: "
            f"{[e['type'] for e in errors]}"
        )

    @_DEFAULT_SETTINGS
    @given(spec=chart_spec_strategy())
    def test_to_xml_never_crashes(self, spec):
        """Build completes and produces a non-empty XML string."""
        chart = ANXChart.from_dict(spec)
        try:
            xml = chart.to_xml()
        except ANXValidationError as e:
            pytest.fail(
                f"to_xml raised on a valid generated spec: "
                f"{[err['type'] for err in e.errors]}"
            )
        assert xml
        assert "<Chart" in xml


class TestDeterminismOverRandomInputs:
    @_DEFAULT_SETTINGS
    @given(spec=chart_spec_strategy())
    def test_canonical_xml_is_deterministic(self, spec):
        """Two fresh charts from the same spec must produce the same canonical XML.

        Catches spec-shape-specific nondeterminism — e.g. a bug that only
        reorders output when a specific combination of fields is set.
        """
        c1 = ANXChart.from_dict(spec)
        c2 = ANXChart.from_dict(spec)
        assert canonical_xml(c1) == canonical_xml(c2)

    @_DEFAULT_SETTINGS
    @given(spec=chart_spec_strategy())
    def test_to_xml_is_deterministic_same_instance(self, spec):
        chart = ANXChart.from_dict(spec)
        assert chart.to_xml() == chart.to_xml()


class TestSettingsRoundTrip:
    @_DEFAULT_SETTINGS
    @given(settings_dict=settings_dict_strategy())
    def test_settings_from_dict_stable_across_cycles(self, settings_dict):
        """Settings.from_dict → asdict → from_dict is a fixed point after cycle 1.

        The first cycle can add None fields for defaults; the second cycle
        must be equal to the first.
        """
        s1 = Settings.from_dict(settings_dict)
        d1 = dataclasses.asdict(s1)
        s2 = Settings.from_dict(d1)
        d2 = dataclasses.asdict(s2)
        assert d1 == d2, (
            f"Settings round-trip diverged on second cycle. "
            f"Input: {settings_dict}"
        )

    @_DEFAULT_SETTINGS
    @given(settings_dict=settings_dict_strategy())
    def test_settings_in_chart_constructor_matches_from_dict(self, settings_dict):
        """ANXChart(settings=dict) and ANXChart(settings=Settings.from_dict(dict))
        produce identical internal state."""
        c1 = ANXChart(settings=settings_dict)
        c2 = ANXChart(settings=Settings.from_dict(settings_dict))
        assert dataclasses.asdict(c1.settings) == dataclasses.asdict(c2.settings)

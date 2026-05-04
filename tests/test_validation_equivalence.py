"""Validation-error equivalence tests.

Proves that the same invalid spec yields the same validate() error list
(order-insensitive, message-agnostic) regardless of which input form was used
to build the chart. Catches the class of bug where valid-looking YAML
silently produces different errors than equivalent Python API calls.

See plans/cheerful-soaring-oasis-followups.md Plan A for the full rationale.
"""

from __future__ import annotations

import pytest

from anxwritter import ANXChart

from tests.fixtures import equivalence_specs as specs
from tests.fixtures.invalid_specs import INVALID_SPECS, EXPECTED
from tests.helpers.chart_equivalence import (
    assert_validation_equivalent,
    validation_error_signature,
)


# Builder pairs — three is enough: parser + convenience API + generic-add
# covers every dispatch boundary. Adding more would be redundant because all
# paths funnel through _apply_data or the same dataclass constructors.
BUILDER_PAIRS = [
    (
        "from_dict",
        "convenience",
        specs.build_via_from_dict,
        specs.build_via_convenience_methods,
    ),
    (
        "from_dict",
        "generic_add",
        specs.build_via_from_dict,
        specs.build_via_generic_add,
    ),
    (
        "from_json",
        "from_yaml",
        specs.build_via_from_json,
        specs.build_via_from_yaml,
    ),
]


def _build_safely(builder, spec):
    """Run builder(spec), returning (chart_or_None, exception_or_None)."""
    try:
        return builder(spec), None
    except Exception as exc:  # noqa: BLE001 — we want to catch any raise
        return None, exc


@pytest.mark.parametrize(
    "spec_name,spec,expected",
    [(n, s, e) for n, s, e in INVALID_SPECS],
    ids=[n for n, _, _ in INVALID_SPECS],
)
@pytest.mark.parametrize(
    "label_a,label_b,build_a,build_b",
    BUILDER_PAIRS,
    ids=[f"{a}-vs-{b}" for a, b, _, _ in BUILDER_PAIRS],
)
class TestValidationEquivalence:
    def test_same_error_signature(
        self, spec_name, spec, expected, label_a, label_b, build_a, build_b
    ):
        c1, e1 = _build_safely(build_a, spec)
        c2, e2 = _build_safely(build_b, spec)

        # Either both paths raised or neither did — any mismatch is a
        # divergence we care about.
        if (e1 is None) != (e2 is None):
            raise AssertionError(
                f"One builder raised, the other did not.\n"
                f"  {label_a}: {type(e1).__name__ if e1 else 'ok'}\n"
                f"  {label_b}: {type(e2).__name__ if e2 else 'ok'}"
            )

        if e1 is not None:
            # Both raised — confirm same exception type (messages may differ)
            assert type(e1) is type(e2), (
                f"{label_a} raised {type(e1).__name__}, "
                f"{label_b} raised {type(e2).__name__}"
            )
            return

        assert_validation_equivalent(c1, c2, label_a=label_a, label_b=label_b)


@pytest.mark.parametrize(
    "spec_name,spec,expected",
    [(n, s, e) for n, s, e in INVALID_SPECS],
    ids=[n for n, _, _ in INVALID_SPECS],
)
class TestExpectedErrorsHit:
    """Sanity check: each invalid spec actually triggers the error it claims.

    Without this, an unreachable spec could pass the equivalence test above
    (both paths emit an empty error list → equivalent → green) while silently
    failing to exercise the category it was designed for.
    """

    def test_expected_errors_present(self, spec_name, spec, expected):
        try:
            chart = ANXChart.from_dict(spec)
        except Exception:
            # If the spec raises at build time, the raising behavior is what
            # the equivalence test locks in — nothing to check here.
            return
        errors = {e["type"] for e in chart.validate()}
        missing = expected - errors
        assert not missing, (
            f"{spec_name}: expected error types {missing} not in "
            f"validate() output. Got: {sorted(errors)}"
        )


class TestValidationEquivalenceSanity:
    """Negative guardrails so a broken comparator doesn't silently pass."""

    def test_valid_chart_has_no_errors(self):
        chart = specs.build_via_from_dict(specs.ENTITIES_ONLY_SPEC)
        assert validation_error_signature(chart) == []

    def test_different_errors_not_equivalent(self):
        c1 = specs.build_via_from_dict(
            {"entities": {"icons": [{"id": "A", "type": "Person", "color": "bogus"}]}}
        )
        c2 = specs.build_via_from_dict(
            {"entities": {"icons": [{"id": "A", "type": "Person", "date": "bad"}]}}
        )
        with pytest.raises(AssertionError):
            assert_validation_equivalent(c1, c2)

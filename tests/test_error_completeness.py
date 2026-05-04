"""Validation error type completeness.

Guards three properties of the ErrorType / validation surface:

1. Every error type expected by an entry in invalid_specs.py is a real
   ErrorType member — catches typos.
2. Every ErrorType actually emitted from validation.py is covered by at
   least one invalid_specs entry — forces tests to accompany new checks.
3. The set of "dead" ErrorType members (defined but never emitted) equals
   the documented known-dead set. Either promoting or removing a dead
   member flips this test, forcing an explicit decision.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from anxwritter.errors import ErrorType

from tests.fixtures.invalid_specs import INVALID_SPECS


# The set of ErrorType members that are defined in errors.py but never
# emitted by validation.py. Update this set when you wire one up or add
# a new dead member — it forces an explicit decision rather than silent
# drift.
KNOWN_DEAD_ERROR_TYPES = {
    ErrorType.CONFIG_CONFLICT,
    ErrorType.INVALID_DATETIME_FORMAT,
}


def _validation_source() -> str:
    src = Path(__file__).parent.parent / "anxwritter" / "validation.py"
    return src.read_text(encoding="utf-8")


def _emitted_error_types() -> set:
    """Parse anxwritter/validation.py and return the set of ErrorType
    members referenced anywhere in the module.

    Captures both direct emit sites (``ErrorType.X.value``) and indirect
    references through local variables (``err_type = ErrorType.X``).
    Either form means the code path produces the error.
    """
    text = _validation_source()
    pattern = re.compile(r"ErrorType\.([A-Z_]+)")
    matches = set(pattern.findall(text))
    return {ErrorType[name] for name in matches if name in ErrorType.__members__}


# Cache at module scope so tests share the parse.
EMITTED_ERROR_TYPES = _emitted_error_types()


class TestInvalidSpecsErrorTypesAreReal:
    """Every error type an invalid_specs entry claims to trigger must exist."""

    @pytest.mark.parametrize(
        "spec_name,expected",
        [(n, e) for n, _, e in INVALID_SPECS],
        ids=[n for n, _, _ in INVALID_SPECS],
    )
    def test_expected_error_types_are_valid(self, spec_name, expected):
        valid_values = {m.value for m in ErrorType}
        invalid = expected - valid_values
        assert not invalid, (
            f"{spec_name}: invalid_specs references unknown error types {invalid}. "
            f"Valid: {sorted(valid_values)}"
        )


class TestEmittedErrorTypesHaveCoverage:
    """Every error type emitted by validation.py must be covered by at least
    one invalid_specs entry."""

    def test_every_emitted_error_type_has_a_spec(self):
        covered = set()
        for _name, _spec, expected in INVALID_SPECS:
            covered.update(expected)

        emitted_values = {e.value for e in EMITTED_ERROR_TYPES}
        uncovered = emitted_values - covered

        # Allow a narrow allowlist for error types that are emitted by
        # validation.py but are genuinely hard to trigger from a pure-dict
        # spec (e.g. connection conflict needs two conflicting Link objects
        # with incompatible multiplicity, which invalid_specs doesn't
        # construct). Add new items here deliberately.
        ALLOWLIST = {
            "duplicate_name",
            "missing_target",
            "invalid_legend_type",
            "invalid_timezone",
            "timezone_without_datetime",
            "invalid_multiplicity",
            "invalid_theme_wiring",
            "connection_conflict",
            "palette_type_mismatch",
            "unsupported_representation",
            "invalid_merge_behaviour",
            "invalid_paste_behaviour",
            "invalid_semantic_type",
            "invalid_grade_default",
        }

        uncovered_unallowed = uncovered - ALLOWLIST
        assert not uncovered_unallowed, (
            f"Emitted ErrorType(s) not covered by any invalid_specs entry: "
            f"{sorted(uncovered_unallowed)}\n"
            f"Add a spec in tests/fixtures/invalid_specs.py or add the "
            f"error type to ALLOWLIST above with a justification."
        )


class TestDeadErrorTypes:
    """Pin the set of defined-but-unemitted ErrorType members."""

    def test_dead_set_matches_known(self):
        all_members = set(ErrorType)
        dead = all_members - EMITTED_ERROR_TYPES

        new_dead = dead - KNOWN_DEAD_ERROR_TYPES
        resurrected = KNOWN_DEAD_ERROR_TYPES - dead

        msg_parts = []
        if new_dead:
            msg_parts.append(
                f"New dead ErrorType(s) — defined but never emitted: "
                f"{sorted(m.name for m in new_dead)}. "
                f"Either wire them up in validation.py or add them to "
                f"KNOWN_DEAD_ERROR_TYPES in this file."
            )
        if resurrected:
            msg_parts.append(
                f"Previously-dead ErrorType(s) are now emitted: "
                f"{sorted(m.name for m in resurrected)}. "
                f"Remove them from KNOWN_DEAD_ERROR_TYPES in this file."
            )
        assert not msg_parts, "\n".join(msg_parts)

    def test_emitted_set_is_not_empty(self):
        """Sanity: the source-parse found SOME error types. If this fails,
        the regex parse is broken, not the library."""
        assert len(EMITTED_ERROR_TYPES) > 10, (
            f"Only {len(EMITTED_ERROR_TYPES)} emitted error types parsed "
            f"from validation.py — regex may be broken."
        )

"""Validation error type completeness.

Guards four properties of the ErrorType / validation surface:

1. Every error type expected by an entry in invalid_specs.py is a real
   ErrorType member — catches typos.
2. Every ErrorType actually emitted from validation.py is covered by at
   least one invalid_specs entry — forces tests to accompany new checks.
3. The set of "dead" ErrorType members (defined but never emitted) equals
   the documented known-dead set. Either promoting or removing a dead
   member flips this test, forcing an explicit decision.
4. Every error code emitted as a raw ``'type': '...'`` string literal in
   validation.py maps to a real ErrorType member — catches codes that
   bypass the enum entirely (the enum→emission scan in #1–#3 only reads
   ``ErrorType.X`` references, so a raw string literal would otherwise slip
   through undetected).
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
    # Emitted from chart.py (_apply_config), not validation.py — the regex
    # scan below only reads validation.py, so these read as "dead" here.
    ErrorType.LOCKED_OVERRIDE,
    ErrorType.DELETE_CONTRACT,
    # Raised as ValueError from Validator/AttributeClassEnforce/...Enforce
    # __post_init__ at dataclass construction time (eager regex compile),
    # never reaches the error-dict path. Reserved for future use if regex
    # compilation ever moves out of __post_init__.
    ErrorType.INVALID_VALIDATOR_PATTERN,
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


def _raw_emitted_type_strings() -> set:
    """Parse anxwritter/validation.py for error codes emitted as raw string
    literals — i.e. ``'type': '<code>'`` rather than ``'type': ErrorType.X.value``.

    Returns the set of literal code strings. Every one of these must be a
    real ErrorType *value*; otherwise the code bypasses the central registry
    and a structured-error consumer filtering on ``ErrorType.X.value`` would
    silently miss it.
    """
    text = _validation_source()
    # Match    'type': 'some_code'    (single or double quoted code).
    pattern = re.compile(r"""['"]type['"]\s*:\s*['"]([a-z_]+)['"]""")
    return set(pattern.findall(text))


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
            # Emitted from the datetime_formats / palettes config sections,
            # which the convenience/generic_add equivalence builders don't
            # construct. Covered directly in tests/test_datetime_format.py and
            # tests/test_audit_gaps.py.
            "invalid_value",
            "palette_unknown_ref",
            "palette_invalid_class",
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


class TestRawTypeStringsAreEnumMembers:
    """Every raw ``'type': '...'`` string literal in validation.py must map
    to a real ErrorType value — the emission→enum direction."""

    def test_no_raw_code_bypasses_the_enum(self):
        valid_values = {m.value for m in ErrorType}
        raw_codes = _raw_emitted_type_strings()
        orphans = raw_codes - valid_values
        assert not orphans, (
            f"validation.py emits error code(s) as raw string literals with no "
            f"matching ErrorType member: {sorted(orphans)}.\n"
            f"Add them to ErrorType in anxwritter/errors.py and emit via "
            f"ErrorType.X.value so the central registry stays authoritative."
        )

    def test_regex_catches_a_raw_literal(self):
        """Sanity: the parser regex actually matches a raw ``'type': '...'``
        literal. The desired steady state is ZERO raw codes in validation.py,
        so we can't assert a non-empty parse there — instead verify the regex
        against a synthetic sample, so a broken regex can't make
        test_no_raw_code_bypasses_the_enum pass vacuously."""
        pattern = re.compile(r"""['"]type['"]\s*:\s*['"]([a-z_]+)['"]""")
        sample = "errors.append({'type': 'some_raw_code', 'message': 'x'})"
        assert pattern.findall(sample) == ["some_raw_code"]

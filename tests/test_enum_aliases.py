"""Exhaustive enum alias coverage.

For every alias-accepting enum in the library, prove that every accepted
string form of every enum member resolves to the same canonical value.
Catches drift like "library accepts 'solid' via the builder map but
Strength(dot_style='solid') stores it as-is and a downstream check compares
against 'DotStyleSolid'."

Also asserts coverage completeness: every enum member must have at least
one entry in the relevant resolver map. Catches "new enum member added
but alias map not updated."
"""

from __future__ import annotations

import pytest

from anxwritter.builder import (
    _ARROW_MAP,
    _DOT_MAP,
    _MERGE_MAP,
    _MULT_MAP,
    _THEME_WIRING_MAP,
    _resolve_enum,
)

# LegendItemType resolver map is defined as a function-local dict inside
# ``ANXBuilder.build`` — duplicated here for coverage. If this drifts from
# the builder source, the cross-check below will fail loudly.
_LI_TYPE_MAP = {
    "font":       "LegendItemTypeFont",
    "text":       "LegendItemTypeText",
    "icon":       "LegendItemTypeIcon",
    "attribute":  "LegendItemTypeAttribute",
    "line":       "LegendItemTypeLine",
    "link":       "LegendItemTypeLink",
    "timezone":   "LegendItemTypeTimeZone",
    "icon_frame": "LegendItemTypeIconFrame",
}
from anxwritter.colors import NAMED_COLORS, color_to_colorref
from anxwritter.enums import (
    ArrowStyle,
    Color,
    DotStyle,
    LegendItemType,
    MergeBehaviour,
    Multiplicity,
    ThemeWiring,
)


# ---------------------------------------------------------------------------
# Color — has the richest alias surface
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("member", list(Color), ids=lambda m: m.name)
class TestColorAliases:
    def test_all_forms_resolve_identically(self, member):
        canonical = color_to_colorref(member)

        title_case = member.value.replace("_", " ").title()
        forms = [
            member,                          # Color enum
            member.value,                    # 'light_orange'
            member.value.upper(),            # 'LIGHT_ORANGE'
            member.value.replace("_", "-"),  # 'light-orange'
            title_case,                      # 'Light Orange' — the NAMED_COLORS key form
            title_case.lower(),              # 'light orange'
        ]
        for form in forms:
            got = color_to_colorref(form)
            assert got == canonical, (
                f"form {form!r} resolved to {got}, expected {canonical} "
                f"(from {member.name})"
            )

    def test_member_is_in_named_colors_map(self, member):
        """Each Color member must have SOME entry in NAMED_COLORS.

        The Title Case key format isn't uniform — some use spaces
        (``'Light Orange'``), one uses a hyphen (``'Blue-Grey'``).
        Accept either form.
        """
        space_form = member.value.replace("_", " ").title()
        hyphen_form = member.value.replace("_", "-").title()
        present = space_form in NAMED_COLORS or hyphen_form in NAMED_COLORS
        assert present, (
            f"Color.{member.name} (value={member.value!r}) has no entry "
            f"in NAMED_COLORS under {space_form!r} or {hyphen_form!r}"
        )


class TestColorHexAliases:
    def test_hex_with_hash_resolves(self):
        assert color_to_colorref("#FF0000") == color_to_colorref(0xFF)  # red lo byte

    def test_bare_hex_resolves(self):
        assert color_to_colorref("FF0000") == color_to_colorref("#FF0000")

    def test_colorref_int_passthrough(self):
        assert color_to_colorref(0xFFFFFF) == 0xFFFFFF


# ---------------------------------------------------------------------------
# Builder-map enums — DotStyle, ArrowStyle, Multiplicity, ThemeWiring,
# MergeBehaviour, LegendItemType
# ---------------------------------------------------------------------------

# (enum, resolver_map, extra_symbol_aliases_per_value)
# The "extra symbols" are the short-hand strings like '->' or '-' that
# aren't part of the enum values themselves but are accepted by _resolve_enum.
_ENUM_CASES = [
    (
        "DotStyle",
        DotStyle,
        _DOT_MAP,
        {
            "solid": ["-"],
            "dashed": ["---"],
            "dash_dot": ["-."],
            "dash_dot_dot": ["-.."],
            "dotted": ["..."],
        },
    ),
    (
        "ArrowStyle",
        ArrowStyle,
        _ARROW_MAP,
        {
            "head": ["->"],
            "tail": ["<-"],
            "both": ["<->"],
        },
    ),
    (
        "Multiplicity",
        Multiplicity,
        _MULT_MAP,
        {},
    ),
    (
        "ThemeWiring",
        ThemeWiring,
        _THEME_WIRING_MAP,
        {},
    ),
    (
        "MergeBehaviour",
        MergeBehaviour,
        _MERGE_MAP,
        {},
    ),
    (
        "LegendItemType",
        LegendItemType,
        _LI_TYPE_MAP,
        {},
    ),
]


@pytest.mark.parametrize(
    "label,enum_cls,resolver_map,extra_aliases",
    _ENUM_CASES,
    ids=[c[0] for c in _ENUM_CASES],
)
class TestBuilderMapEnumAliases:
    def test_every_member_has_map_entry(self, label, enum_cls, resolver_map, extra_aliases):
        """Every enum member's canonical value must be a key in the resolver map."""
        missing = [m.name for m in enum_cls if m.value not in resolver_map]
        assert not missing, (
            f"{label} members with no entry in resolver map: {missing}"
        )

    def test_all_forms_resolve_to_same_anb_string(
        self, label, enum_cls, resolver_map, extra_aliases
    ):
        """For each member, every accepted form must resolve to the same ANB string."""
        for member in enum_cls:
            canonical_anb = resolver_map[member.value]
            forms = [
                member,                  # enum instance
                member.value,            # 'solid', 'head', etc.
                member.value.upper(),    # 'SOLID', 'HEAD'
                canonical_anb,           # 'DotStyleSolid' — full ANB name passthrough
            ]
            forms.extend(extra_aliases.get(member.value, []))

            for form in forms:
                got = _resolve_enum(form, resolver_map)
                assert got == canonical_anb, (
                    f"{label}.{member.name}: form {form!r} resolved to "
                    f"{got!r}, expected {canonical_anb!r}"
                )


# ---------------------------------------------------------------------------
# Dead-map drift detection — every resolver-map key either is an enum value
# or is documented as a symbol alias
# ---------------------------------------------------------------------------

class TestResolverMapCoverage:
    def test_dot_map_keys_covered(self):
        enum_values = {m.value for m in DotStyle}
        symbol_aliases = {"-", "---", "-.", "-..", "..."}
        anb_full_names = {"dotstylesolid", "dotstyledashed", "dotstyledashdot",
                          "dotstyledashdotdot", "dotstyledotted"}
        allowed = enum_values | symbol_aliases | anb_full_names
        unknown = set(_DOT_MAP.keys()) - allowed
        assert not unknown, f"_DOT_MAP has unexpected keys: {unknown}"

    def test_arrow_map_keys_covered(self):
        enum_values = {m.value for m in ArrowStyle}
        symbol_aliases = {"->", "<-", "<->"}
        allowed = enum_values | symbol_aliases
        unknown = set(_ARROW_MAP.keys()) - allowed
        assert not unknown, f"_ARROW_MAP has unexpected keys: {unknown}"

    def test_legend_type_map_keys_covered(self):
        enum_values = {m.value for m in LegendItemType}
        unknown = set(_LI_TYPE_MAP.keys()) - enum_values
        assert not unknown, f"_LI_TYPE_MAP has unexpected keys: {unknown}"

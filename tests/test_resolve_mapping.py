"""Characterization of builder.resolve_entity / resolve_link field mapping and
the _resolve_font_color null-ish branches.

This is the hard prerequisite for the Phase 2.2 colour-coercion merge: the
existing FontColour byte-asserts only cover the str->int / int-passthrough
happy paths, so these tests pin the None / bool / NaN / empty-string -> None
behaviour that a naive merge would silently break.
"""

from __future__ import annotations

import math

from anxwritter import Color, Font, Icon, Link, Representation, Show, color_to_colorref
from anxwritter.builder import ANXBuilder


class TestResolveFontColor:
    def setup_method(self):
        self.b = ANXBuilder()

    def test_none(self):
        assert self.b._resolve_font_color(None) is None

    def test_true_false_are_none(self):
        # bool must not be treated as an int COLORREF.
        assert self.b._resolve_font_color(True) is None
        assert self.b._resolve_font_color(False) is None

    def test_nan_is_none(self):
        assert self.b._resolve_font_color(float("nan")) is None

    def test_empty_and_whitespace_are_none(self):
        assert self.b._resolve_font_color("") is None
        assert self.b._resolve_font_color("   ") is None

    def test_int_passthrough(self):
        assert self.b._resolve_font_color(255) == 255

    def test_float_truncated_to_int(self):
        assert self.b._resolve_font_color(255.0) == 255

    def test_hex_string(self):
        assert self.b._resolve_font_color("#FF0000") == color_to_colorref("#FF0000")

    def test_named_string(self):
        assert self.b._resolve_font_color("Red") == color_to_colorref("Red")

    def test_color_enum_unwrapped_to_int(self):
        member = next(iter(Color))
        result = self.b._resolve_font_color(member)
        assert isinstance(result, int)
        assert result == color_to_colorref(member)


class TestResolveEntityMapping:
    def test_entity_fields_mapped(self):
        b = ANXBuilder()
        icon = Icon(
            id="A",
            type="Person",
            label="Alice",
            date="2024-01-15",
            time="14:30:00",
            attributes={"phone": "555", "age": 39},
            label_font=Font(color="#FF0000", bg_color="Blue", name="Arial", size=12, bold=True),
            show=Show(label=True, date=True),
        )
        re = b.resolve_entity(icon)

        assert re.identity == "A"
        assert re.entity_type == "Person"
        assert re.label == "Alice"
        assert re.representation == Representation.ICON.value
        # Font colours resolved to COLORREF ints.
        assert re.label_color == color_to_colorref("#FF0000")
        assert re.label_bg_color == color_to_colorref("Blue")
        assert re.label_face == "Arial"
        assert re.label_size == 12
        assert re.label_bold is True
        # Datetime parsed.
        assert re.date_set is True
        assert re.time_set is True
        assert re.datetime_str.startswith("2024-01-15T14:30:00")
        # Attributes mapped to ResolvedAttr(class_name, ac_ref_id, value_str).
        assert {a.class_name for a in re.attributes} == {"phone", "age"}
        # SubItem visibility passthrough.
        assert re.show_label is True
        assert re.show_date is True
        # Default strength.
        assert re.strength == "Default"

    def test_label_defaults_to_identity(self):
        b = ANXBuilder()
        re = b.resolve_entity(Icon(id="Solo", type="Person"))
        assert re.label == "Solo"

    def test_dedup_returns_none_on_second_resolve(self):
        b = ANXBuilder()
        assert b.resolve_entity(Icon(id="A", type="Person")) is not None
        assert b.resolve_entity(Icon(id="A", type="Person")) is None

    def test_missing_id_returns_none(self):
        assert ANXBuilder().resolve_entity(Icon(type="Person")) is None


class TestResolveLinkMapping:
    def _builder_with_endpoints(self):
        b = ANXBuilder()
        b.resolve_entity(Icon(id="A", type="Person"))
        b.resolve_entity(Icon(id="B", type="Person"))
        return b

    def test_link_fields_mapped(self):
        b = self._builder_with_endpoints()
        rl = b.resolve_link(
            Link(
                from_id="A",
                to_id="B",
                type="Call",
                arrow="->",
                label="calls",
                line_color="#00FF00",
                line_width=3,
                label_font=Font(color="Red"),
            )
        )
        assert rl.link_type == "Call"
        assert rl.arrow == "ArrowOnHead"
        assert rl.line_color == color_to_colorref("#00FF00")
        assert rl.line_width == 3
        assert rl.label == "calls"
        assert rl.label_color == color_to_colorref("Red")
        assert rl.from_int_id != rl.to_int_id
        assert rl.strength == "Default"

    def test_link_defaults(self):
        b = self._builder_with_endpoints()
        rl = b.resolve_link(Link(from_id="A", to_id="B"))
        assert rl.arrow == "ArrowNone"
        assert rl.line_color == 0
        assert rl.line_width == 1
        assert rl.link_type == "Link"

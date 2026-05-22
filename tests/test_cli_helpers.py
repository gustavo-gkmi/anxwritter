"""Unit tests for the CLI's pure config helpers.

These functions drive ``--show-config`` provenance output and config-layer
diffing. They were previously exercised only end-to-end via subprocess (0%
line coverage). Characterizing them directly pins the YAML-quoting and
flat-path rules before the Phase 2/3 refactors touch nearby code.
"""

from __future__ import annotations

from anxwritter.cli import (
    _diff_config,
    _flatten_config,
    _render_annotated_config,
    _yaml_scalar,
)


class TestFlattenConfig:
    def test_nested_dict(self):
        flat = dict(_flatten_config({"a": 1, "b": {"c": 2}}))
        assert flat == {"a": 1, "b.c": 2}

    def test_list_of_named_dicts_indexed_by_name(self):
        flat = dict(_flatten_config({"entity_types": [{"name": "Person", "color": "Blue"}]}))
        assert flat == {
            "entity_types[Person].name": "Person",
            "entity_types[Person].color": "Blue",
        }

    def test_list_without_name_uses_integer_index(self):
        flat = dict(_flatten_config({"xs": [10, 20]}))
        assert flat == {"xs[0]": 10, "xs[1]": 20}

    def test_settings_path(self):
        flat = dict(_flatten_config({"settings": {"chart": {"bg_color": 123}}}))
        assert flat == {"settings.chart.bg_color": 123}


class TestDiffConfig:
    def test_changed_and_added_paths(self):
        old = {"a": 1, "keep": "x"}
        new = {"a": 2, "keep": "x", "b": 3}
        assert _diff_config(old, new) == {"a", "b"}

    def test_identical_is_empty(self):
        assert _diff_config({"a": 1}, {"a": 1}) == set()


class TestYamlScalar:
    def test_none(self):
        assert _yaml_scalar(None) == "null"

    def test_bools(self):
        assert _yaml_scalar(True) == "true"
        assert _yaml_scalar(False) == "false"

    def test_numbers(self):
        assert _yaml_scalar(5) == "5"
        assert _yaml_scalar(1.5) == "1.5"

    def test_empty_string(self):
        assert _yaml_scalar("") == "''"

    def test_yaml_sentinels_get_quoted(self):
        assert _yaml_scalar("yes") == "'yes'"
        assert _yaml_scalar("null") == "'null'"
        assert _yaml_scalar("off") == "'off'"

    def test_numeric_looking_strings_get_quoted(self):
        assert _yaml_scalar("123") == "'123'"
        assert _yaml_scalar("1.5") == "'1.5'"

    def test_plain_string_passes_through(self):
        assert _yaml_scalar("plain") == "plain"

    def test_special_char_quoted(self):
        assert _yaml_scalar("has: colon") == "'has: colon'"

    def test_single_quote_escaped(self):
        assert _yaml_scalar("it's") == "'it''s'"

    def test_leading_space_quoted(self):
        assert _yaml_scalar(" leading") == "' leading'"


class TestRenderAnnotatedConfig:
    def test_nested_scalar_with_provenance(self):
        obj = {"settings": {"chart": {"bg_color": 123}}}
        prov = {"settings.chart.bg_color": "base.json"}
        out = _render_annotated_config(obj, prov)
        lines = out.splitlines()
        assert "settings:" in lines
        assert "  chart:" in lines
        assert "    bg_color: 123  # from: base.json" in lines

    def test_list_by_name_with_provenance(self):
        obj = {"entity_types": [{"name": "Person", "color": "Blue"}]}
        prov = {"entity_types[Person].color": "a.json"}
        out = _render_annotated_config(obj, prov)
        lines = out.splitlines()
        assert "entity_types:" in lines
        assert "- name: Person" in lines
        assert "  color: Blue  # from: a.json" in lines

    def test_no_provenance_no_comment(self):
        out = _render_annotated_config({"settings": {"chart": {"bg_color": 1}}}, {})
        assert "# from:" not in out
        assert out.endswith("\n")

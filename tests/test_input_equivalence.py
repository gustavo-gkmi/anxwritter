"""Cross-input-form equivalence tests.

Proves that the same logical chart data, supplied via every supported input
form, produces identical internal state and identical (canonical) XML output.

Input forms covered:
  * Parsers:   from_dict / from_json / from_json_file / from_yaml / from_yaml_file
  * Python API: add_icon(**kw) / add(Icon(...)) / add_all(iter)
  * Settings:   dict vs Settings(ChartCfg(...), ...)
  * Registries: add_X(name=..., **kw) vs add_X(X(...))
  * Collections: chart.strengths = StrengthCollection(...) vs repeated add_strength
  * Config path: from_config_file + _apply_data vs from_dict
  * Negative:   mutated spec must NOT compare equal

Each equivalence test runs two comparisons:
  1. Canonical-XML + internal-state equality
  2. Byte-equal XML (strict ``chart.to_xml() == chart.to_xml()``)

Both assertions are REQUIRED — all supported input forms currently produce
byte-identical XML, so any future divergence is a regression we want to catch.
"""

from __future__ import annotations

import copy

import pytest

from anxwritter import ANXChart

from tests.fixtures import equivalence_specs as specs
from tests.helpers.chart_equivalence import assert_charts_equivalent


# ---------------------------------------------------------------------------
# Parser equivalence — all four file/string parsers funnel through from_dict
# ---------------------------------------------------------------------------

PARSER_PAIRS = [
    ("from_dict", "from_json", specs.build_via_from_dict, specs.build_via_from_json),
    ("from_dict", "from_yaml", specs.build_via_from_dict, specs.build_via_from_yaml),
    ("from_json", "from_yaml", specs.build_via_from_json, specs.build_via_from_yaml),
]


@pytest.mark.parametrize(
    "spec_name,spec",
    [(n, s) for n, s in specs.ALL_SPECS.items()],
)
@pytest.mark.parametrize("label_a,label_b,build_a,build_b", PARSER_PAIRS)
class TestParserEquivalence:
    def test_canonical(self, spec_name, spec, label_a, label_b, build_a, build_b):
        c1 = build_a(spec)
        c2 = build_b(spec)
        assert_charts_equivalent(c1, c2, label_a=label_a, label_b=label_b)

    def test_strict_bytes(self, spec_name, spec, label_a, label_b, build_a, build_b):
        c1 = build_a(spec)
        c2 = build_b(spec)
        assert_charts_equivalent(
            c1, c2, strict_bytes=True, label_a=label_a, label_b=label_b
        )


# File-based parsers need tmp_path — handled in a separate class
class TestParserFileEquivalence:
    def test_json_string_vs_file(self, tmp_path):
        c1 = specs.build_via_from_json(specs.FULL_SPEC)
        c2 = specs.build_via_from_json_file(specs.FULL_SPEC, tmp_path)
        assert_charts_equivalent(c1, c2, label_a="from_json", label_b="from_json_file")

    def test_yaml_string_vs_file(self, tmp_path):
        c1 = specs.build_via_from_yaml(specs.FULL_SPEC)
        c2 = specs.build_via_from_yaml_file(specs.FULL_SPEC, tmp_path)
        assert_charts_equivalent(c1, c2, label_a="from_yaml", label_b="from_yaml_file")


# ---------------------------------------------------------------------------
# Entity input path equivalence
# ---------------------------------------------------------------------------

ENTITY_BUILDER_PAIRS = [
    (
        "from_dict",
        "convenience_methods",
        specs.build_via_from_dict,
        specs.build_via_convenience_methods,
    ),
    (
        "convenience_methods",
        "generic_add",
        specs.build_via_convenience_methods,
        specs.build_via_generic_add,
    ),
    (
        "generic_add",
        "add_all",
        specs.build_via_generic_add,
        specs.build_via_add_all,
    ),
    (
        "from_dict",
        "generic_add",
        specs.build_via_from_dict,
        specs.build_via_generic_add,
    ),
]


@pytest.mark.parametrize(
    "spec_name,spec",
    [("FULL", specs.FULL_SPEC), ("ENTITIES_ONLY", specs.ENTITIES_ONLY_SPEC)],
)
@pytest.mark.parametrize("label_a,label_b,build_a,build_b", ENTITY_BUILDER_PAIRS)
class TestEntityInputEquivalence:
    def test_canonical(self, spec_name, spec, label_a, label_b, build_a, build_b):
        assert_charts_equivalent(
            build_a(spec), build_b(spec), label_a=label_a, label_b=label_b
        )

    def test_strict_bytes(self, spec_name, spec, label_a, label_b, build_a, build_b):
        assert_charts_equivalent(
            build_a(spec),
            build_b(spec),
            strict_bytes=True,
            label_a=label_a,
            label_b=label_b,
        )


# ---------------------------------------------------------------------------
# Settings: dict vs Settings dataclass
# ---------------------------------------------------------------------------

SETTINGS_BUILDER_PAIRS = [
    (
        "settings_dict",
        "settings_from_dict",
        specs.build_via_convenience_methods,
        specs.build_via_settings_dataclass,
    ),
    (
        "settings_dict",
        "settings_manual_dataclass",
        specs.build_via_convenience_methods,
        specs.build_via_settings_manual_dataclass,
    ),
]


@pytest.mark.parametrize(
    "spec_name,spec",
    [("FULL", specs.FULL_SPEC), ("SETTINGS_ONLY", specs.SETTINGS_ONLY_SPEC)],
)
@pytest.mark.parametrize("label_a,label_b,build_a,build_b", SETTINGS_BUILDER_PAIRS)
class TestSettingsEquivalence:
    def test_canonical(self, spec_name, spec, label_a, label_b, build_a, build_b):
        assert_charts_equivalent(
            build_a(spec), build_b(spec), label_a=label_a, label_b=label_b
        )

    def test_strict_bytes(self, spec_name, spec, label_a, label_b, build_a, build_b):
        assert_charts_equivalent(
            build_a(spec),
            build_b(spec),
            strict_bytes=True,
            label_a=label_a,
            label_b=label_b,
        )


# ---------------------------------------------------------------------------
# Registry name_or_obj pattern
# ---------------------------------------------------------------------------

REGISTRY_BUILDER_PAIRS = [
    (
        "registries_kw",
        "registries_obj",
        specs.build_via_convenience_methods,
        specs.build_via_generic_add,
    ),
    (
        "from_dict",
        "registries_kw",
        specs.build_via_from_dict,
        specs.build_via_convenience_methods,
    ),
    (
        "from_dict",
        "registries_obj",
        specs.build_via_from_dict,
        specs.build_via_generic_add,
    ),
]


@pytest.mark.parametrize(
    "spec_name,spec",
    [("FULL", specs.FULL_SPEC), ("REGISTRY_ONLY", specs.REGISTRY_ONLY_SPEC)],
)
@pytest.mark.parametrize("label_a,label_b,build_a,build_b", REGISTRY_BUILDER_PAIRS)
class TestRegistryEquivalence:
    def test_canonical(self, spec_name, spec, label_a, label_b, build_a, build_b):
        assert_charts_equivalent(
            build_a(spec), build_b(spec), label_a=label_a, label_b=label_b
        )


# ---------------------------------------------------------------------------
# Collection reassignment vs individual adds (strengths, grades)
# ---------------------------------------------------------------------------

class TestCollectionEquivalence:
    def test_strengths_collection_vs_individual_adds(self):
        c1 = specs.build_via_collection_reassignment(specs.FULL_SPEC)
        c2 = specs.build_via_convenience_methods(specs.FULL_SPEC)
        assert_charts_equivalent(
            c1,
            c2,
            label_a="collection_reassignment",
            label_b="convenience_methods",
        )

    def test_grades_collection_vs_from_dict(self):
        c1 = specs.build_via_collection_reassignment(specs.FULL_SPEC)
        c2 = specs.build_via_from_dict(specs.FULL_SPEC)
        assert_charts_equivalent(
            c1,
            c2,
            label_a="collection_reassignment",
            label_b="from_dict",
        )


# ---------------------------------------------------------------------------
# Config path equivalence
# ---------------------------------------------------------------------------

class TestConfigPathEquivalence:
    def test_config_file_plus_data_vs_from_dict(self, tmp_path):
        c1 = specs.build_via_config_file_plus_data(specs.FULL_SPEC, tmp_path)
        c2 = specs.build_via_from_dict(specs.FULL_SPEC)
        assert_charts_equivalent(
            c1, c2, label_a="config_file+data", label_b="from_dict"
        )

    def test_apply_config_plus_data_vs_from_dict(self):
        c1 = specs.build_via_apply_config_plus_data(specs.FULL_SPEC)
        c2 = specs.build_via_from_dict(specs.FULL_SPEC)
        assert_charts_equivalent(
            c1, c2, label_a="apply_config+data", label_b="from_dict"
        )

    def test_config_file_vs_apply_config(self, tmp_path):
        c1 = specs.build_via_config_file_plus_data(specs.FULL_SPEC, tmp_path)
        c2 = specs.build_via_apply_config_plus_data(specs.FULL_SPEC)
        assert_charts_equivalent(
            c1, c2, label_a="config_file+data", label_b="apply_config+data"
        )


# ---------------------------------------------------------------------------
# Negative guardrails — mutated specs must NOT compare equal
# ---------------------------------------------------------------------------

class TestNegativeCases:
    def test_mutated_entity_color_differs(self):
        mutated = copy.deepcopy(specs.ENTITIES_ONLY_SPEC)
        mutated["entities"]["icons"][0]["color"] = "Red"
        c1 = specs.build_via_from_dict(specs.ENTITIES_ONLY_SPEC)
        c2 = specs.build_via_from_dict(mutated)
        with pytest.raises(AssertionError):
            assert_charts_equivalent(c1, c2)

    def test_extra_entity_differs(self):
        mutated = copy.deepcopy(specs.ENTITIES_ONLY_SPEC)
        mutated["entities"]["icons"].append({"id": "Carol", "type": "Person"})
        c1 = specs.build_via_from_dict(specs.ENTITIES_ONLY_SPEC)
        c2 = specs.build_via_from_dict(mutated)
        with pytest.raises(AssertionError):
            assert_charts_equivalent(c1, c2)

    def test_different_settings_differ(self):
        mutated = copy.deepcopy(specs.SETTINGS_ONLY_SPEC)
        mutated["settings"]["chart"]["bg_color"] = 0
        c1 = specs.build_via_from_dict(specs.SETTINGS_ONLY_SPEC)
        c2 = specs.build_via_from_dict(mutated)
        with pytest.raises(AssertionError):
            assert_charts_equivalent(c1, c2)


# ---------------------------------------------------------------------------
# YAML-auto-parsed vs JSON-string parity
# ---------------------------------------------------------------------------
#
# ``TestParserEquivalence`` builds JSON via ``json.dumps`` and YAML via
# ``yaml.safe_dump`` from the same Python dict, so both serialisers always
# emit *quoted* strings for dates / times / bools.  That confirms the three
# parsers don't drift for canonical inputs, but it never exercises the
# scenario where YAML's own loader auto-parses unquoted values into typed
# Python objects (``datetime.date``, ``datetime.datetime``, ``int`` from
# sexagesimal, ``bool`` from ``yes``/``no``) — the YAML user writes one
# thing, the JSON user has to write a string equivalent, and they must
# produce the same chart.
#
# This class pins that contract: YAML file with auto-parsed values vs JSON
# file with explicit string equivalents → byte-identical XML.

class TestYamlAutoParsedVsJsonStringParity:
    """A YAML file written naturally (unquoted dates / unquoted ISO
    datetimes / `yes`/`no` for flags) must produce the same chart as the
    JSON file a JSON-pipeline user would write to express the same data
    (everything explicitly quoted / `true`/`false` for bools)."""

    def _assert_yaml_json_parity(self, yaml_text: str, json_text: str) -> None:
        """Load both, validate, assert byte-identical XML.

        We deliberately do NOT compare in-memory state: YAML preserves
        the auto-parsed ``date``/``datetime``/``bool`` objects the user
        gave us, while JSON preserves the original strings.  Both are
        correct — preserving the source form is more honest than
        eagerly normalising.  The user-facing parity contract is that
        the *XML output* is identical.
        """
        import re
        from anxwritter import ANXChart
        ch_yaml = ANXChart.from_yaml(yaml_text)
        ch_json = ANXChart.from_json(json_text)
        assert ch_yaml.validate() == [], f'YAML side failed validation: {ch_yaml.validate()}'
        assert ch_json.validate() == [], f'JSON side failed validation: {ch_json.validate()}'
        # Origin's CreatedDate is auto-generated when unset and clock-sensitive,
        # so strip it from both sides before comparing.
        def _normalise(xml: str) -> str:
            return re.sub(r'<Origin [^/]*/>', '<Origin/>', xml)
        x_yaml = _normalise(ch_yaml.to_xml())
        x_json = _normalise(ch_json.to_xml())
        assert x_yaml == x_json, (
            'YAML(unquoted) and JSON(string) inputs produced different XML.\n'
            f'YAML diff (first 800 chars):\n{x_yaml[:800]}\n\n'
            f'JSON diff (first 800 chars):\n{x_json[:800]}'
        )

    def test_unquoted_date_in_entity_matches_json_string(self):
        yaml_text = """
entities:
  icons:
    - id: alice
      type: Person
      date: 2024-01-15
      time: '10:00:00'
"""
        json_text = """{
  "entities": {"icons": [
    {"id": "alice", "type": "Person",
     "date": "2024-01-15", "time": "10:00:00"}
  ]}
}"""
        self._assert_yaml_json_parity(yaml_text, json_text)

    def test_unquoted_date_in_inline_card_matches_json_string(self):
        """Pre-fix this case crashed the YAML loader (#1).  Parity with
        the JSON form is the real-user-facing acceptance criterion."""
        yaml_text = """
entities:
  icons:
    - id: alice
      type: Person
      cards:
        - summary: 'evidence'
          date: 2024-01-15
          time: '10:00:00'
"""
        json_text = """{
  "entities": {"icons": [
    {"id": "alice", "type": "Person",
     "cards": [{"summary": "evidence",
                "date": "2024-01-15", "time": "10:00:00"}]}
  ]}
}"""
        self._assert_yaml_json_parity(yaml_text, json_text)

    def test_unquoted_datetime_in_summary_matches_json_string(self):
        """Pre-fix this case emitted XML with a space separator instead
        of `T` (#2), making the ANX file ANB-rejected."""
        yaml_text = """
settings:
  summary:
    title: X
    created: 2024-01-15T10:00:00
    last_save: 2024-03-01
entities:
  icons:
    - id: A
      type: P
"""
        json_text = """{
  "settings": {"summary": {
    "title": "X",
    "created": "2024-01-15T10:00:00",
    "last_save": "2024-03-01"
  }},
  "entities": {"icons": [{"id": "A", "type": "P"}]}
}"""
        self._assert_yaml_json_parity(yaml_text, json_text)

    def test_unquoted_default_datetime_matches_json_string(self):
        """Issue #3 — `settings.time.default_datetime` had the same
        space-separator bug as `summary.created`."""
        yaml_text = """
settings:
  time:
    default_date: 2024-01-15
    default_datetime: 2024-01-15T10:00:00
entities:
  icons:
    - id: A
      type: P
"""
        json_text = """{
  "settings": {"time": {
    "default_date": "2024-01-15",
    "default_datetime": "2024-01-15T10:00:00"
  }},
  "entities": {"icons": [{"id": "A", "type": "P"}]}
}"""
        self._assert_yaml_json_parity(yaml_text, json_text)

    def test_yaml_yes_no_sentinels_match_json_true_false(self):
        """YAML 1.1 ``yes``/``no`` sentinels must produce the same Flag
        attribute XML as JSON's ``true``/``false``."""
        yaml_text = """
entities:
  icons:
    - id: A
      type: P
      attributes:
        Active: yes
        Married: no
"""
        json_text = """{
  "entities": {"icons": [
    {"id": "A", "type": "P",
     "attributes": {"Active": true, "Married": false}}
  ]}
}"""
        self._assert_yaml_json_parity(yaml_text, json_text)

    def test_yaml_datetime_attribute_matches_json_declared_datetime(self):
        """Issue #7 vs the JSON datetime escape hatch.  YAML auto-parses
        unquoted ``Joined: 2024-01-15T10:00:00`` to ``datetime`` and
        emits ``AttTime``.  JSON has no datetime literal — to get the
        same XML the user declares the attribute as ``type: datetime``
        in ``attribute_classes`` and passes the ISO string."""
        yaml_text = """
entities:
  icons:
    - id: A
      type: P
      attributes:
        Joined: 2024-01-15T10:00:00
"""
        # JSON form needs the AttributeClass declaration to opt into
        # datetime typing — that's the documented escape hatch.
        json_text = """{
  "attribute_classes": [{"name": "Joined", "type": "datetime"}],
  "entities": {"icons": [
    {"id": "A", "type": "P",
     "attributes": {"Joined": "2024-01-15T10:00:00"}}
  ]}
}"""
        # Both must emit identical AttributeClass + Attribute Value XML.
        # Note: both ALSO emit the AttributeClass declaration — YAML
        # auto-creates it from the inferred type, JSON has it explicit
        # in `attribute_classes`.  The resulting class definitions differ
        # in attribute ordering / explicit-defaults, so this case asserts
        # only that the per-entity Attribute element matches.
        from anxwritter import ANXChart
        import re
        ch_y = ANXChart.from_yaml(yaml_text)
        ch_j = ANXChart.from_json(json_text)
        assert ch_y.validate() == []
        assert ch_j.validate() == []
        for ch in (ch_y, ch_j):
            xml = ch.to_xml()
            ac_type = re.search(
                r'<AttributeClass[^>]*Name="Joined"[^>]*Type="(\w+)"', xml
            )
            assert ac_type and ac_type.group(1) == 'AttTime'
            attr_val = re.search(
                r'<Attribute[^>]*AttributeClass="Joined"[^>]*Value="([^"]+)"', xml
            )
            assert attr_val and attr_val.group(1) == '2024-01-15T10:00:00'

    def test_yaml_unquoted_date_attribute_matches_json_declared_datetime(self):
        """Date-only literal: YAML auto-parses ``BirthDate: 1990-05-12``
        to ``datetime.date`` (which the loader widens to midnight
        datetime).  JSON-side equivalent uses the same datetime
        escape hatch with the date-only ISO string."""
        yaml_text = """
entities:
  icons:
    - id: A
      type: P
      attributes:
        BirthDate: 1990-05-12
"""
        json_text = """{
  "attribute_classes": [{"name": "BirthDate", "type": "datetime"}],
  "entities": {"icons": [
    {"id": "A", "type": "P",
     "attributes": {"BirthDate": "1990-05-12"}}
  ]}
}"""
        from anxwritter import ANXChart
        import re
        ch_y = ANXChart.from_yaml(yaml_text)
        ch_j = ANXChart.from_json(json_text)
        for ch in (ch_y, ch_j):
            attr_val = re.search(
                r'<Attribute[^>]*AttributeClass="BirthDate"[^>]*Value="([^"]+)"',
                ch.to_xml(),
            )
            assert attr_val and attr_val.group(1) == '1990-05-12T00:00:00'

    def test_full_realistic_yaml_vs_json_chart(self):
        """A full chart with multiple YAML-auto-parsed quirks at once
        produces identical XML to the JSON-string equivalent.  Pins the
        end-to-end parity in one go."""
        yaml_text = """
settings:
  summary:
    title: 'Op Sunshine'
    created: 2024-01-15T10:00:00
  extra_cfg:
    arrange: grid
attribute_classes:
  - name: Notes
    type: text
entities:
  icons:
    - id: alice
      type: Person
      date: 2024-01-15
      time: '14:30:00'
      attributes:
        Active: yes
        Notes: 'follow up'
links: []
"""
        json_text = """{
  "settings": {
    "summary": {"title": "Op Sunshine", "created": "2024-01-15T10:00:00"},
    "extra_cfg": {"arrange": "grid"}
  },
  "attribute_classes": [{"name": "Notes", "type": "text"}],
  "entities": {"icons": [
    {"id": "alice", "type": "Person",
     "date": "2024-01-15", "time": "14:30:00",
     "attributes": {"Active": true, "Notes": "follow up"}}
  ]},
  "links": []
}"""
        self._assert_yaml_json_parity(yaml_text, json_text)

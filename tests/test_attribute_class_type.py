"""Tests for AttributeClass.type enforcement and type-conflict validation.

Covers:
- ``type`` is mandatory on explicit AttributeClass declarations.
- Explicit ``type`` is authoritative; merge/paste validity checks apply to
  the declared type.
- Data-vs-data type conflicts (same attribute name with different Python
  value types) are collected as deferred ``type_conflict`` errors.
- Config-vs-data conflicts (declared type disagrees with inferred data
  type) are collected as ``type_conflict`` errors.
- Declared AttributeClass instances are emitted in the XML even when no
  entity/link data references them (no silent drop).
"""

import xml.etree.ElementTree as ET

import pytest

from anxwritter import ANXChart, AttributeClass, AttributeType


def _parse_xml(chart: ANXChart) -> ET.Element:
    return ET.fromstring(chart.to_xml())


class TestTypeRequired:
    def test_ac_without_type_raises_missing_required(self):
        c = ANXChart()
        c.add_attribute_class(name='X')
        c.add_icon(id='A', type='T', attributes={'X': 'v'})
        errors = c.validate()
        matches = [
            e for e in errors
            if e['type'] == 'missing_required'
            and e.get('location') == 'attribute_classes[0].type'
        ]
        assert len(matches) == 1
        assert "'X'" in matches[0]['message']
        assert 'type' in matches[0]['message']

    def test_ac_with_explicit_type_passes(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Score': 42})
        c.add_attribute_class(name='Score', type=AttributeType.NUMBER)
        errors = c.validate()
        assert not any(
            e['type'] == 'missing_required'
            and 'Score' in e.get('message', '')
            for e in errors
        )

    def test_ac_without_type_does_not_raise_at_construction(self):
        """Dataclass-level construction must still accept type=None.
        Enforcement is deferred to validate() per the project pattern."""
        ac = AttributeClass(name='X')
        assert ac.type is None
        chart = ANXChart()
        chart.add_attribute_class(ac)  # must not raise


class TestExplicitTypeIsAuthoritative:
    def test_behaviour_validated_against_declared_type_flag(self):
        """Explicit type=FLAG + merge='or' must pass; merge='add_space' must fail."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Active': True})
        c.add_attribute_class(
            name='Active', type=AttributeType.FLAG, merge_behaviour='or',
        )
        errors = c.validate()
        assert not any(
            e['type'] in ('invalid_merge_behaviour', 'invalid_paste_behaviour')
            for e in errors
        )

    def test_invalid_behaviour_for_declared_type(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Score': 42})
        c.add_attribute_class(
            name='Score', type=AttributeType.TEXT, merge_behaviour='max',
        )
        errors = c.validate()
        assert any(e['type'] == 'invalid_merge_behaviour' for e in errors)


class TestConfigVsDataTypeConflict:
    def test_declared_text_with_bool_data(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Flag1': True})
        c.add_attribute_class(name='Flag1', type=AttributeType.TEXT)
        errors = c.validate()
        ac_conflicts = [
            e for e in errors
            if e['type'] == 'type_conflict'
            and e.get('location', '').startswith('attribute_classes[')
        ]
        assert len(ac_conflicts) == 1
        msg = ac_conflicts[0]['message']
        assert "'Flag1'" in msg
        assert 'text' in msg and 'flag' in msg

    def test_declared_number_with_string_data(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Note': 'hello'})
        c.add_attribute_class(name='Note', type=AttributeType.NUMBER)
        errors = c.validate()
        assert any(
            e['type'] == 'type_conflict'
            and "'Note'" in e.get('message', '')
            for e in errors
        )

    def test_declared_type_matching_data_no_error(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Balance': 12.5})
        c.add_attribute_class(name='Balance', type=AttributeType.NUMBER)
        errors = c.validate()
        assert not any(
            e['type'] == 'type_conflict'
            and e.get('location', '').startswith('attribute_classes[')
            for e in errors
        )

    def test_config_vs_data_conflict_for_link_attribute(self):
        """Conflict detection must cover link attributes."""
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(
            from_id='A', to_id='B', type='X',
            attributes={'Duration': 'long'},
        )
        c.add_attribute_class(name='Duration', type=AttributeType.NUMBER)
        errors = c.validate()
        assert any(e['type'] == 'type_conflict' for e in errors)


class TestDataVsDataTypeConflict:
    """Data-vs-data type conflicts are handled by check_attr_types (the
    existing per-row walker inside validate_entities/validate_links), which
    emits one type_conflict error per conflicting row. The tests below lock
    that contract in."""

    def test_same_name_different_types_on_entities(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Count': 'not a number'})
        c.add_icon(id='B', type='T', attributes={'Count': 42})
        errors = c.validate()
        conflicts = [e for e in errors if e['type'] == 'type_conflict']
        # First entity establishes the type; second entity is flagged.
        assert len(conflicts) == 1
        assert "'Count'" in conflicts[0]['message']

    def test_entity_vs_link_same_attribute_name_conflict(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'X': 'abc'})
        c.add_icon(id='B', type='T')
        c.add_link(
            from_id='A', to_id='B', type='X', attributes={'X': 42},
        )
        errors = c.validate()
        assert any(e['type'] == 'type_conflict' for e in errors)

    def test_consistent_types_no_conflict(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Name': 'abc'})
        c.add_icon(id='B', type='T', attributes={'Name': 'def'})
        errors = c.validate()
        assert not any(e['type'] == 'type_conflict' for e in errors)

    def test_per_row_reporting(self):
        """Each conflicting row is flagged individually — the first row
        sets the type, every subsequent row that disagrees is an error."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'X': 'str'})
        c.add_icon(id='B', type='T', attributes={'X': 1})
        c.add_icon(id='C', type='T', attributes={'X': 2.5})
        c.add_icon(id='D', type='T', attributes={'X': True})
        errors = c.validate()
        conflicts = [e for e in errors if e['type'] == 'type_conflict']
        # 3 rows after the first, all differing from the first-seen Text type.
        assert len(conflicts) == 3


class TestDeclaredClassAlwaysEmitted:
    """Explicit AttributeClass declarations must appear in the XML even
    when no entity/link data references them. Previously they were
    silently dropped."""

    def test_unused_declared_class_is_emitted(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_attribute_class(name='Ghost', type=AttributeType.FLAG)
        root = _parse_xml(c)
        ac = root.find('.//AttributeClassCollection/AttributeClass[@Name="Ghost"]')
        assert ac is not None
        assert ac.get('Type') == 'AttFlag'

    def test_mixed_used_and_unused_classes(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Used': 'yes'})
        c.add_attribute_class(name='Used', type=AttributeType.TEXT)
        c.add_attribute_class(name='Unused', type=AttributeType.NUMBER)
        root = _parse_xml(c)
        names = {
            ac.get('Name'): ac.get('Type')
            for ac in root.findall('.//AttributeClassCollection/AttributeClass')
        }
        assert names.get('Used') == 'AttText'
        assert names.get('Unused') == 'AttNumber'

    def test_declared_class_type_is_authoritative_in_xml(self):
        """The emitted Type must reflect the declared type even when
        data usage exists (explicit beats inference at emission)."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'X': 'string-like'})
        c.add_attribute_class(name='X', type=AttributeType.TEXT)
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="X"]')
        assert ac is not None
        assert ac.get('Type') == 'AttText'


class TestYamlPath:
    """End-to-end: the YAML loader path must surface the same errors."""

    def test_yaml_path_catches_missing_type(self, tmp_path):
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(
            "attribute_classes:\n"
            "  - name: Phone\n"
            "    prefix: 'Tel: '\n",
            encoding="utf-8",
        )
        c = ANXChart()
        c.apply_config_file(str(cfg))
        errors = c.validate()
        assert any(
            e['type'] == 'missing_required'
            and 'Phone' in e.get('message', '')
            and 'type' in e.get('message', '')
            for e in errors
        )

    def test_yaml_path_declared_class_reaches_xml(self, tmp_path):
        data = tmp_path / "data.yaml"
        cfg = tmp_path / "config.yaml"
        data.write_text(
            "entities:\n"
            "  icons:\n"
            "    - id: A\n"
            "      type: Person\n",
            encoding="utf-8",
        )
        cfg.write_text(
            "attribute_classes:\n"
            "  - name: Phone\n"
            "    type: Text\n"
            "    prefix: 'Tel: '\n",
            encoding="utf-8",
        )
        c = ANXChart.from_yaml_file(str(data))
        c.apply_config_file(str(cfg))
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="Phone"]')
        assert ac is not None
        assert ac.get('Type') == 'AttText'
        assert ac.get('Prefix') == 'Tel: '

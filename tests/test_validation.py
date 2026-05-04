"""Tests for chart validation — all error types."""

import pytest
from anxwritter import ANXChart, ANXValidationError, AttributeType, GradeCollection


class TestMissingRequired:
    def test_entity_missing_id(self):
        c = ANXChart()
        c.add_icon(type='Person')  # no id
        errors = c.validate()
        assert len(errors) == 1
        assert errors[0]['type'] == 'missing_required'

    def test_link_missing_from_id(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_link(to_id='A', type='X')
        errors = c.validate()
        assert any(e['type'] == 'missing_required' for e in errors)

    def test_link_missing_to_id(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_link(from_id='A', type='X')
        errors = c.validate()
        assert any(e['type'] == 'missing_required' for e in errors)


class TestDuplicateId:
    def test_same_type(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='A', type='T')
        errors = c.validate()
        assert any(e['type'] == 'duplicate_id' for e in errors)

    def test_across_types(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_box(id='A', type='T')
        errors = c.validate()
        assert any(e['type'] == 'duplicate_id' for e in errors)


class TestMissingEntity:
    def test_from_id_not_found(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_link(from_id='X', to_id='A', type='L')
        errors = c.validate()
        assert any(e['type'] == 'missing_entity' and 'from_id' in e['message'] for e in errors)

    def test_to_id_not_found(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_link(from_id='A', to_id='X', type='L')
        errors = c.validate()
        assert any(e['type'] == 'missing_entity' and 'to_id' in e['message'] for e in errors)


class TestUnknownColour:
    def test_bad_entity_color(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', color='Banana')
        errors = c.validate()
        assert any(e['type'] == 'unknown_color' for e in errors)

    def test_valid_named_color(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', color='Blue')
        errors = c.validate()
        assert not any(e['type'] == 'unknown_color' for e in errors)

    def test_valid_hex_color(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', color='#FF0000')
        errors = c.validate()
        assert not any(e['type'] == 'unknown_color' for e in errors)

    def test_bad_link_color(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', line_color='Nope')
        errors = c.validate()
        assert any(e['type'] == 'unknown_color' for e in errors)


class TestInvalidDate:
    def test_bad_format(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', date='01-15-2024')
        errors = c.validate()
        assert any(e['type'] == 'invalid_date' for e in errors)

    def test_impossible_date(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', date='2024-13-01')
        errors = c.validate()
        assert any(e['type'] == 'invalid_date' for e in errors)

    def test_valid_date(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', date='2024-01-15')
        errors = c.validate()
        assert not any(e['type'] == 'invalid_date' for e in errors)


class TestInvalidTime:
    def test_bad_time(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', time='25:00:00')
        errors = c.validate()
        assert any(e['type'] == 'invalid_time' for e in errors)

    def test_valid_time(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', time='14:30:00')
        errors = c.validate()
        assert not any(e['type'] == 'invalid_time' for e in errors)


class TestTypeConflict:
    def test_same_attr_different_types(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'val': 42})
        c.add_icon(id='B', type='T', attributes={'val': 'text'})
        errors = c.validate()
        assert any(e['type'] == 'type_conflict' for e in errors)

    def test_same_type_no_conflict(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'val': 42})
        c.add_icon(id='B', type='T', attributes={'val': 99})
        errors = c.validate()
        assert not any(e['type'] == 'type_conflict' for e in errors)


class TestInvalidStrength:
    def test_unknown_strength(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', strength='SuperStrong')
        errors = c.validate()
        assert any(e['type'] == 'invalid_strength' for e in errors)

    def test_default_strength_ok(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', strength='Default')
        errors = c.validate()
        assert not any(e['type'] == 'invalid_strength' for e in errors)


class TestGradeOutOfRange:
    def test_grade_one_out_of_range(self):
        c = ANXChart()
        c.grades_one = GradeCollection(items=['A', 'B'])
        c.add_icon(id='X', type='T', grade_one=5)
        errors = c.validate()
        assert any(e['type'] == 'grade_out_of_range' for e in errors)

    def test_grade_in_range(self):
        c = ANXChart()
        c.grades_one = GradeCollection(items=['A', 'B'])
        c.add_icon(id='X', type='T', grade_one=1)
        errors = c.validate()
        assert not any(e['type'] == 'grade_out_of_range' for e in errors)


class TestGradeDefaultValidation:
    def test_unknown_grade_default(self):

        c = ANXChart()
        c.grades_one = GradeCollection(default='Nonexistent', items=['A', 'B'])
        c.add_icon(id='X', type='T')
        errors = c.validate()
        assert any(e['type'] == 'invalid_grade_default' for e in errors)

    def test_valid_grade_default(self):

        c = ANXChart()
        c.grades_one = GradeCollection(default='A', items=['A', 'B'])
        c.add_icon(id='X', type='T')
        errors = c.validate()
        assert not any(e['type'] == 'invalid_grade_default' for e in errors)


class TestStrengthDefaultValidation:
    def test_unknown_strength_default(self):
        from anxwritter import StrengthCollection, Strength, DotStyle
        c = ANXChart()
        c.strengths = StrengthCollection(
            default='Nonexistent',
            items=[Strength(name='Default', dot_style=DotStyle.SOLID)],
        )
        c.add_icon(id='X', type='T')
        errors = c.validate()
        assert any(e['type'] == 'invalid_strength_default' for e in errors)


class TestUnsupportedRepresentation:
    def test_ole_object_rejected(self):
        """OLE_OBJECT representation is not supported — should fail validation."""
        c = ANXChart()
        c.add_entity_type(name='OleType', representation='ole_object')
        c.add_icon(id='A', type='OleType')
        errors = c.validate()
        assert any(e['type'] == 'unsupported_representation' for e in errors)
        assert any('OLE_OBJECT' in e['message'] for e in errors)

    def test_valid_representations_ok(self):
        """Standard representations should not trigger unsupported error."""
        c = ANXChart()
        c.add_entity_type(name='IconType', representation='icon')
        c.add_entity_type(name='BoxType', representation='box')
        c.add_icon(id='A', type='IconType')
        c.add_box(id='B', type='BoxType')
        errors = c.validate()
        assert not any(e['type'] == 'unsupported_representation' for e in errors)


class TestSelfLoop:
    def test_self_loop(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_link(from_id='A', to_id='A', type='L')
        errors = c.validate()
        assert any(e['type'] == 'self_loop' for e in errors)


class TestValidateRaises:
    def test_to_xml_raises(self):
        c = ANXChart()
        c.add_icon(type='Person')  # no id
        with pytest.raises(ANXValidationError) as exc_info:
            c.to_xml()
        assert len(exc_info.value.errors) == 1

    def test_to_anx_raises(self, tmp_path):
        c = ANXChart()
        c.add_icon(type='Person')  # no id
        with pytest.raises(ANXValidationError):
            c.to_anx(str(tmp_path / 'test'))


class TestEmptyChartValid:
    def test_empty(self):
        c = ANXChart()
        assert c.validate() == []


class TestMultipleErrors:
    def test_collects_all(self):
        c = ANXChart()
        c.add_icon(type='T')  # missing id
        c.add_icon(id='A', type='T', color='Bad')
        c.add_icon(id='B', type='T', date='nope')
        errors = c.validate()
        types = {e['type'] for e in errors}
        assert 'missing_required' in types
        assert 'unknown_color' in types
        assert 'invalid_date' in types


class TestAttributeClassBehaviourPerType:
    """Per-type validity for merge_behaviour and paste_behaviour.

    Regression: previously the validator only checked name uniqueness and
    silently emitted whatever merge/paste string the user passed, so ANB
    would reject the resulting .anx at import time with
    'LNAttributeClass::SetPasteBehaviour: Invalid paste behaviour for
    classes of this type'. The validator now catches these before build.
    """

    def test_merge_xor_invalid_on_text(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Notes': 'hello'})
        c.add_attribute_class(name='Notes', type=AttributeType.TEXT, merge_behaviour='xor')
        errors = c.validate()
        assert any(
            e['type'] == 'invalid_merge_behaviour'
            and 'Notes' in e['message']
            for e in errors
        )

    def test_paste_xor_invalid_on_text(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Notes': 'hello'})
        c.add_attribute_class(name='Notes', type=AttributeType.TEXT, paste_behaviour='xor')
        errors = c.validate()
        assert any(
            e['type'] == 'invalid_paste_behaviour'
            and 'Notes' in e['message']
            for e in errors
        )

    def test_merge_add_space_invalid_on_number(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Balance': 42.5})
        c.add_attribute_class(name='Balance', type=AttributeType.NUMBER, merge_behaviour='add_space')
        errors = c.validate()
        assert any(e['type'] == 'invalid_merge_behaviour' for e in errors)

    def test_subtract_only_valid_on_number_paste(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Active': True})
        c.add_attribute_class(name='Active', type=AttributeType.FLAG, paste_behaviour='subtract')
        errors = c.validate()
        assert any(e['type'] == 'invalid_paste_behaviour' for e in errors)

    def test_assign_rejected_as_merge(self):
        """assign/noop are paste-only; they are invalid as merge_behaviour."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Notes': 'hello'})
        c.add_attribute_class(name='Notes', type=AttributeType.TEXT, merge_behaviour='assign')
        errors = c.validate()
        assert any(e['type'] == 'invalid_merge_behaviour' for e in errors)

    def test_anb_prefixed_uppercase_accepted(self):
        """Legacy ANB-prefixed names (AttMergeOR etc.) must canonicalize
        the same way regardless of casing."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Active': True})
        c.add_attribute_class(
            name='Active', type=AttributeType.FLAG,
            merge_behaviour='AttMergeOR',
            paste_behaviour='AttMergeXOR',
        )
        errors = c.validate()
        assert not any(
            e['type'] in ('invalid_merge_behaviour', 'invalid_paste_behaviour')
            for e in errors
        )

    def test_unknown_behaviour_name(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Notes': 'hello'})
        c.add_attribute_class(name='Notes', type=AttributeType.TEXT, paste_behaviour='bogus')
        errors = c.validate()
        assert any(
            e['type'] == 'invalid_paste_behaviour'
            and 'bogus' in e['message']
            for e in errors
        )

    def test_valid_per_type_combinations_pass(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={
            'Notes': 'hello', 'Balance': 42.5, 'Active': True,
        })
        c.add_attribute_class(
            name='Notes', type=AttributeType.TEXT,
            merge_behaviour='add_space', paste_behaviour='assign',
        )
        c.add_attribute_class(
            name='Balance', type=AttributeType.NUMBER,
            merge_behaviour='add', paste_behaviour='subtract',
        )
        c.add_attribute_class(
            name='Active', type=AttributeType.FLAG,
            merge_behaviour='or', paste_behaviour='xor',
        )
        errors = c.validate()
        assert not any(
            e['type'] in ('invalid_merge_behaviour', 'invalid_paste_behaviour')
            for e in errors
        )

    def test_behaviour_check_on_link_attributes(self):
        """Behaviour check must apply to attribute classes used on links."""
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='X', attributes={'Weight': 3.14})
        c.add_attribute_class(name='Weight', type=AttributeType.NUMBER, paste_behaviour='xor')
        errors = c.validate()
        assert any(e['type'] == 'invalid_paste_behaviour' for e in errors)

    def test_explicit_type_is_authoritative(self):
        """Explicit ac.type is authoritative; behaviour check applies to it."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Count': 5})
        c.add_attribute_class(
            name='Count', type=AttributeType.TEXT, merge_behaviour='max',
        )
        errors = c.validate()
        # max is invalid for Text (the explicit type), so should flag
        assert any(e['type'] == 'invalid_merge_behaviour' for e in errors)

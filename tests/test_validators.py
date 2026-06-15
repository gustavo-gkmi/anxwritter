"""Focused tests for the 1.17.0 value-enforcement feature.

Covers the three places rules can be declared (AttributeClass.enforce,
EntityType/LinkType.enforce, top-level validators[]) and the cross-cutting
concerns: synthesized keys, compound AND semantics, the smart-truncating
ANXValidationError message, and Python API parity.

The equivalence test suite (tests/test_validation_equivalence.py) already
covers that the same invalid spec produces the same errors across every
input form; this file focuses on the rule semantics themselves.
"""
from __future__ import annotations

import pytest

from anxwritter import (
    ANXChart,
    AttributeClass,
    AttributeClassEnforce,
    ANXValidationError,
    EntityType,
    EntityTypeEnforce,
    ErrorType,
    LinkType,
    LinkTypeEnforce,
    Validator,
)
from anxwritter.utils import synthesize_validator_key


# ---------------------------------------------------------------------------
# Synthetic key
# ---------------------------------------------------------------------------


class TestSynthesizedKey:
    def test_entity_scope(self):
        assert synthesize_validator_key('Person', None, 'CPF') == 'E::Person::CPF'

    def test_link_scope(self):
        assert synthesize_validator_key(None, 'Transfer', 'Currency') == 'L::Transfer::Currency'

    def test_both_scopes_set_returns_none(self):
        assert synthesize_validator_key('A', 'B', 'x') is None

    def test_neither_scope_set_returns_none(self):
        assert synthesize_validator_key(None, None, 'x') is None

    def test_missing_attribute_returns_none(self):
        assert synthesize_validator_key('Person', None, None) is None
        assert synthesize_validator_key('Person', None, '') is None

    def test_validator_key_property(self):
        v = Validator(entity_type='Person', attribute='CPF',
                      pattern=r'^\d+$', description='digits')
        assert v.key == 'E::Person::CPF'


# ---------------------------------------------------------------------------
# Dataclass construction
# ---------------------------------------------------------------------------


class TestDataclassConstruction:
    def test_bad_regex_raises_on_validator(self):
        with pytest.raises(ValueError, match='not a valid regex'):
            Validator(entity_type='X', attribute='y', pattern='[bad',
                      description='x')

    def test_bad_regex_raises_on_ac_enforce(self):
        with pytest.raises(ValueError, match='not a valid regex'):
            AttributeClassEnforce(pattern='[bad', description='x')

    def test_bad_regex_raises_on_entity_type_enforce(self):
        with pytest.raises(ValueError, match='not a valid regex'):
            EntityTypeEnforce(id_pattern='[bad', id_pattern_description='x')

    def test_bad_regex_raises_on_link_type_enforce(self):
        with pytest.raises(ValueError, match='not a valid regex'):
            LinkTypeEnforce(id_pattern='[bad', id_pattern_description='x')

    def test_both_shapes_raises_on_validator(self):
        with pytest.raises(ValueError, match='exactly one'):
            Validator(entity_type='X', attribute='y',
                      pattern='.', allowed_values=['a'])

    def test_both_shapes_raises_on_ac_enforce(self):
        with pytest.raises(ValueError, match='exactly one'):
            AttributeClassEnforce(pattern='.', allowed_values=['a'])

    def test_eager_compile_stores_pattern_object(self):
        v = Validator(entity_type='X', attribute='y',
                      pattern=r'^\d+$', description='d')
        assert v._compiled_pattern is not None
        assert v._compiled_pattern.fullmatch('123') is not None
        assert v._compiled_pattern.fullmatch('abc') is None


# ---------------------------------------------------------------------------
# id_pattern enforcement
# ---------------------------------------------------------------------------


class TestIdPattern:
    def test_passes_on_match(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'Person', 'icon_file': 'person',
             'enforce': {'id_pattern': r'^\d{11}$',
                         'id_pattern_description': '11 digits'}},
        ]})
        c.add_icon(id='12345678901', type='Person')
        errors = c.validate()
        # No id_pattern_mismatch errors
        assert not any(e['type'] == ErrorType.ID_PATTERN_MISMATCH.value for e in errors)

    def test_fires_on_mismatch(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'Person', 'icon_file': 'person',
             'enforce': {'id_pattern': r'^\d{11}$',
                         'id_pattern_description': '11 digits'}},
        ]})
        c.add_icon(id='abc', type='Person')
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ID_PATTERN_MISMATCH.value]
        assert len(errors) == 1
        e = errors[0]
        assert e['entity_id'] == 'abc'
        assert e['entity_type'] == 'Person'
        assert e['pattern'] == r'^\d{11}$'
        assert e['description'] == '11 digits'
        assert e['rule_source'] == 'entity_type[Person]'

    def test_no_pattern_set_is_noop(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'Person', 'icon_file': 'person',
             'enforce': {'required_attributes': ['Name']}},
        ]})
        c.add_icon(id='anything-goes', type='Person',
                   attributes={'Name': 'Alice'})
        assert not c.validate()

    def test_anchors_are_optional_because_fullmatch(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'Person', 'icon_file': 'person',
             'enforce': {'id_pattern': r'\d{11}',
                         'id_pattern_description': '11 digits'}},
        ]})
        c.add_icon(id='12345678901', type='Person')   # exact 11 digits — OK
        c.add_icon(id='12345678901extra', type='Person')   # trailing extra — bad
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ID_PATTERN_MISMATCH.value]
        assert len(errors) == 1
        assert errors[0]['entity_id'] == '12345678901extra'


# ---------------------------------------------------------------------------
# required_attributes
# ---------------------------------------------------------------------------


class TestRequiredAttributes:
    def test_fires_on_missing(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'Person', 'icon_file': 'person',
             'enforce': {'required_attributes': ['CPF', 'Name']}},
        ]})
        c.add_icon(id='A', type='Person', attributes={'CPF': '111'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.REQUIRED_ATTRIBUTE_MISSING.value]
        assert len(errors) == 1
        assert errors[0]['attribute_name'] == 'Name'

    def test_passes_when_all_present(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'Person', 'icon_file': 'person',
             'enforce': {'required_attributes': ['CPF']}},
        ]})
        c.add_icon(id='A', type='Person', attributes={'CPF': '111'})
        assert not [e for e in c.validate()
                    if e['type'] == ErrorType.REQUIRED_ATTRIBUTE_MISSING.value]

    def test_required_attrs_on_link_type(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'Person', 'icon_file': 'person'}],
            'link_types': [{'name': 'Transfer',
                            'enforce': {'required_attributes': ['Amount']}}],
        })
        c.add_icon(id='A', type='Person')
        c.add_icon(id='B', type='Person')
        c.add_link(from_id='A', to_id='B', type='Transfer')
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.REQUIRED_ATTRIBUTE_MISSING.value]
        assert len(errors) == 1
        assert errors[0]['link_index'] == 0
        assert errors[0]['attribute_name'] == 'Amount'


# ---------------------------------------------------------------------------
# AttributeClass.enforce — wide value rules
# ---------------------------------------------------------------------------


class TestAttributeClassEnforce:
    def test_pattern_fires_on_value_mismatch(self):
        c = ANXChart()
        c.apply_config({'attribute_classes': [
            {'name': 'CPF', 'type': 'text',
             'enforce': {'pattern': r'^\d{11}$', 'description': 'digits'}},
        ]})
        c.add_icon(id='A', type='Person',
                   attributes={'CPF': '123.456.789-01'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value]
        assert len(errors) == 1
        assert errors[0]['rule_source'] == 'attribute_class[CPF]'
        assert errors[0]['received_value'] == '123.456.789-01'

    def test_allowed_values_fires_on_mismatch(self):
        c = ANXChart()
        c.apply_config({'attribute_classes': [
            {'name': 'Status', 'type': 'text',
             'enforce': {'allowed_values': ['Active', 'Inactive']}},
        ]})
        c.add_icon(id='A', type='Person', attributes={'Status': 'unknown'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_VALUE_NOT_ALLOWED.value]
        assert len(errors) == 1
        assert errors[0]['allowed_values'] == ['Active', 'Inactive']

    def test_allowed_values_is_case_sensitive_by_default(self):
        c = ANXChart()
        c.apply_config({'attribute_classes': [
            {'name': 'Status', 'type': 'text',
             'enforce': {'allowed_values': ['Active']}},
        ]})
        c.add_icon(id='A', type='Person', attributes={'Status': 'active'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_VALUE_NOT_ALLOWED.value]
        assert len(errors) == 1

    def test_no_enforce_means_no_check(self):
        c = ANXChart()
        c.apply_config({'attribute_classes': [
            {'name': 'CPF', 'type': 'text'},
        ]})
        c.add_icon(id='A', type='Person', attributes={'CPF': 'anything'})
        assert not c.validate()


# ---------------------------------------------------------------------------
# Top-level validators[]
# ---------------------------------------------------------------------------


class TestTopLevelValidators:
    def test_entity_scope_pattern(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'Person', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'Person', 'attribute': 'CPF',
                 'pattern': r'^\d{11}$', 'description': 'digits'},
            ],
        })
        c.add_icon(id='A', type='Person', attributes={'CPF': 'bad'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value]
        assert len(errors) == 1
        assert errors[0]['rule_source'] == 'validator[E::Person::CPF]'

    def test_link_scope_allowed_values(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'link_types': [{'name': 'T'}],
            'validators': [
                {'link_type': 'T', 'attribute': 'Currency',
                 'allowed_values': ['BRL', 'USD']},
            ],
        })
        c.add_icon(id='A', type='P')
        c.add_icon(id='B', type='P')
        c.add_link(from_id='A', to_id='B', type='T',
                   attributes={'Currency': 'YEN'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_VALUE_NOT_ALLOWED.value]
        assert len(errors) == 1
        assert errors[0]['rule_source'] == 'validator[L::T::Currency]'

    def test_validator_with_only_entity_type_doesnt_match_link(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'link_types': [{'name': 'T'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'pattern': r'^\d+$', 'description': 'digits'},
            ],
        })
        c.add_icon(id='A', type='P')
        c.add_icon(id='B', type='P')
        # Link's CPF should NOT match the entity-scoped validator.
        c.add_link(from_id='A', to_id='B', type='T',
                   attributes={'CPF': 'whatever'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value]
        assert errors == []


# ---------------------------------------------------------------------------
# Compound AND semantics
# ---------------------------------------------------------------------------


class TestCompoundAnd:
    def test_ac_and_validator_both_fire(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'Person', 'icon_file': 'person'}],
            'attribute_classes': [
                {'name': 'CPF', 'type': 'text',
                 'enforce': {'pattern': r'^\d{11}$', 'description': 'digits'}},
            ],
            'validators': [
                {'entity_type': 'Person', 'attribute': 'CPF',
                 'pattern': r'^[1-9]\d{10}$',
                 'description': 'first digit non-zero'},
            ],
        })
        c.add_icon(id='A', type='Person',
                   attributes={'CPF': '00000000000'})
        # 11 digits → passes AC pattern; starts with 0 → fails validator
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value]
        assert len(errors) == 1
        assert errors[0]['rule_source'] == 'validator[E::Person::CPF]'

    def test_both_rules_fail_emit_both(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'Person', 'icon_file': 'person'}],
            'attribute_classes': [
                {'name': 'CPF', 'type': 'text',
                 'enforce': {'pattern': r'^\d{11}$', 'description': 'digits'}},
            ],
            'validators': [
                {'entity_type': 'Person', 'attribute': 'CPF',
                 'pattern': r'^[1-9]\d{10}$',
                 'description': 'first digit non-zero'},
            ],
        })
        # 'mask' fails both rules
        c.add_icon(id='A', type='Person',
                   attributes={'CPF': '123.456.789-01'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value]
        assert len(errors) == 2
        sources = {e['rule_source'] for e in errors}
        assert 'attribute_class[CPF]' in sources
        assert 'validator[E::Person::CPF]' in sources


# ---------------------------------------------------------------------------
# Config-load checks
# ---------------------------------------------------------------------------


class TestConfigLoadChecks:
    def test_reserved_attribute_id(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'id',
                 'pattern': '.', 'description': 'x'},
            ],
        })
        errors = c.validate()
        assert any(e['type'] == ErrorType.VALIDATOR_RESERVED_ATTRIBUTE.value
                   for e in errors)

    def test_unknown_type_reference(self):
        c = ANXChart()
        c.apply_config({
            'validators': [
                {'entity_type': 'Ghost', 'attribute': 'x',
                 'pattern': '.', 'description': 'x'},
            ],
        })
        errors = c.validate()
        assert any(e['type'] == ErrorType.VALIDATOR_UNKNOWN_TYPE.value
                   for e in errors)

    def test_pattern_without_description(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'x', 'pattern': '.'},
            ],
        })
        errors = c.validate()
        assert any(e['type'] == ErrorType.PATTERN_MISSING_DESCRIPTION.value
                   for e in errors)

    def test_allowed_values_no_description_is_ok(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'x',
                 'allowed_values': ['a']},
            ],
        })
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.PATTERN_MISSING_DESCRIPTION.value]
        assert errors == []

    def test_ac_pattern_without_description(self):
        c = ANXChart()
        c.apply_config({
            'attribute_classes': [
                {'name': 'CPF', 'type': 'text',
                 'enforce': {'pattern': r'^\d+$'}},
            ],
        })
        errors = c.validate()
        assert any(e['type'] == ErrorType.PATTERN_MISSING_DESCRIPTION.value
                   for e in errors)


# ---------------------------------------------------------------------------
# Smart-truncating ANXValidationError.__str__
# ---------------------------------------------------------------------------


class TestSmartTruncation:
    def test_uncapped_errors_list(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'P', 'icon_file': 'person',
             'enforce': {'id_pattern': r'^\d+$',
                         'id_pattern_description': 'digits'}},
        ]})
        for i in range(50):
            c.add_icon(id=f'bad-{i}', type='P')
        errors = c.validate()
        # Programmatic consumers get the full list.
        assert len(errors) == 50

    def test_group_truncation_in_str(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'P', 'icon_file': 'person',
             'enforce': {'id_pattern': r'^\d+$',
                         'id_pattern_description': 'digits'}},
        ]})
        for i in range(30):
            c.add_icon(id=f'bad-{i}', type='P')
        errors = c.validate()
        msg = str(ANXValidationError(errors))
        assert '30 rows — showing first 5' in msg
        assert '... 25 more' in msg
        # First 5 are explicitly shown
        for i in range(5):
            assert f"bad-{i}" in msg
        # Not all 30 shown
        assert "bad-29" not in msg

    def test_small_groups_render_normally(self):
        c = ANXChart()
        c.apply_config({'entity_types': [
            {'name': 'P', 'icon_file': 'person',
             'enforce': {'id_pattern': r'^\d+$',
                         'id_pattern_description': 'digits'}},
        ]})
        c.add_icon(id='bad', type='P')
        errors = c.validate()
        msg = str(ANXValidationError(errors))
        # No truncation header
        assert 'showing first' not in msg
        assert "bad" in msg

    def test_non_rule_errors_preserve_format(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        c.add_icon(id='A', type='Person')  # duplicate
        errors = c.validate()
        msg = str(ANXValidationError(errors))
        # Existing format: "  - [duplicate_id] ..."
        assert '  - [duplicate_id]' in msg


# ---------------------------------------------------------------------------
# Python API parity
# ---------------------------------------------------------------------------


class TestPythonApiParity:
    def test_add_validator_builder(self):
        c = ANXChart()
        c.add_validator(entity_type='P', attribute='CPF',
                        pattern=r'^\d+$', description='digits')
        assert len(c._validators) == 1
        assert c._validators[0].key == 'E::P::CPF'

    def test_add_validator_upsert(self):
        c = ANXChart()
        c.add_validator(entity_type='P', attribute='CPF',
                        pattern=r'^\d+$', description='v1')
        c.add_validator(entity_type='P', attribute='CPF',
                        pattern=r'^\d{11}$', description='v2')
        assert len(c._validators) == 1
        assert c._validators[0].description == 'v2'

    def test_generic_add_validator(self):
        c = ANXChart()
        c.add(Validator(entity_type='P', attribute='CPF',
                        pattern=r'^\d+$', description='d'))
        assert len(c._validators) == 1

    def test_constructed_validator_in_apply_config(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                Validator(entity_type='P', attribute='CPF',
                          pattern=r'^\d+$', description='d'),
            ],
        })
        assert len(c._validators) == 1


# ---------------------------------------------------------------------------
# Config layering for validators
# ---------------------------------------------------------------------------


class TestConfigLayering:
    def test_field_merge_across_layers(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'pattern': r'^\d+$', 'description': 'v1'},
            ],
        })
        c.apply_config({
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'description': 'v2'},  # pattern stays, description overrides
            ],
        })
        assert len(c._validators) == 1
        assert c._validators[0].pattern == r'^\d+$'
        assert c._validators[0].description == 'v2'

    def test_lock_blocks_later_change(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'pattern': r'^\d{11}$', 'description': 'locked'},
            ],
        }, lock=True)
        c.apply_config({
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'pattern': r'^.*$'},
            ],
        })
        errors = c.validate()
        assert any(e['type'] == ErrorType.LOCKED_OVERRIDE.value for e in errors)
        # Locked value preserved
        assert c._validators[0].pattern == r'^\d{11}$'

    def test_delete_by_scope(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'pattern': r'^\d+$', 'description': 'd'},
            ],
        })
        c.apply_config({
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF'},
            ],
        }, operation='delete')
        assert len(c._validators) == 0

    def test_source_attribution(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'validators': [
                {'entity_type': 'P', 'attribute': 'CPF',
                 'pattern': r'^\d+$', 'description': 'd'},
            ],
        }, source_name='org.yaml')
        c.add_icon(id='bad-cpf', type='P', attributes={'CPF': 'X'})
        errors = [e for e in c.validate()
                  if e['type'] == ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value]
        assert len(errors) == 1
        assert errors[0].get('source') == 'org.yaml'


# ---------------------------------------------------------------------------
# Validation does NOT fire when no enforcement is declared
# ---------------------------------------------------------------------------


class TestNoEnforcementMeansNoErrors:
    def test_chart_without_any_enforcement_passes(self):
        c = ANXChart()
        c.apply_config({
            'entity_types': [{'name': 'P', 'icon_file': 'person'}],
            'attribute_classes': [{'name': 'CPF', 'type': 'text'}],
        })
        c.add_icon(id='whatever', type='P', attributes={'CPF': 'anything'})
        assert c.validate() == []

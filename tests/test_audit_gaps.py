"""Coverage-gap tests added during the test-suite audit.

Each class targets a public-API surface or validation rule that the existing
suite either left silent or only exercised indirectly via the
``test_error_completeness.py`` allowlist. The file is deliberately thin and
focused on rules visible to library users — the goal is *signal*, not bulk.

Categories (mirroring tests_audit.md):
- Coverage gaps in palette validation (palette_unknown_ref / palette_invalid_class
  / palette_type_mismatch).
- Coverage gaps in semantic-type adders (``add_semantic_link`` /
  ``add_semantic_property``) and the corresponding ``add()`` dispatch.
- Coverage gaps in validators that ``test_error_completeness.py`` only
  allowlisted: ``invalid_timezone``, ``timezone_without_datetime``,
  ``invalid_multiplicity``, ``invalid_theme_wiring``, ``connection_conflict``,
  ``invalid_semantic_type``, ``missing_target``, ``invalid_legend_type``,
  ``duplicate_name`` (entity/link/AC/strength).
- Edge cases in :mod:`anxwritter.utils` not previously covered: NaN floats,
  ``datetime.date`` / ``datetime.time`` instance acceptance, whitespace-only
  strings.
- ``ANXValidationError`` exception structure (``.errors`` and ``str()``).
- ``add()`` generic-dispatch ``TypeError`` for unknown types.

These tests pin behaviour, not implementation. Where a check shares a code
path with another test, this file uses the smallest spec that triggers the
intended error and asserts only the type — keeping it robust against
future message wording changes.
"""

from __future__ import annotations

from datetime import date, datetime, time

import math
import pytest

from anxwritter import (
    ANXChart,
    ANXValidationError,
    AttributeClass,
    AttributeType,
    Card,
    DateTimeFormat,
    EntityType,
    LegendItem,
    LegendItemType,
    Link,
    LinkType,
    Multiplicity,
    Palette,
    PaletteAttributeEntry,
    SemanticEntity,
    SemanticLink,
    SemanticProperty,
    Strength,
    ThemeWiring,
    TimeZone,
)
from anxwritter.utils import _is_valid_color, _validate_date, _validate_time


# ─────────────────────────────────────────────────────────────────────────
# Palette validation — validate_palettes was untested end-to-end
# ─────────────────────────────────────────────────────────────────────────


class TestPaletteUnknownRef:
    """`palette_unknown_ref` errors when a palette references a name that
    isn't in the corresponding registry."""

    def test_unknown_entity_type(self):
        c = ANXChart()
        c.add_entity_type(name='Person', icon_file='person')
        c.add_palette(name='Bad', entity_types=['Ghost'])
        errors = c.validate()
        assert any(e['type'] == 'palette_unknown_ref' and 'Ghost' in e['message']
                   for e in errors)

    def test_unknown_link_type(self):
        c = ANXChart()
        c.add_link_type(name='Call', color=0)
        c.add_palette(name='Bad', link_types=['Telegram'])
        errors = c.validate()
        assert any(e['type'] == 'palette_unknown_ref' and 'Telegram' in e['message']
                   for e in errors)

    def test_unknown_attribute_class(self):
        c = ANXChart()
        c.add_attribute_class(name='Phone', type=AttributeType.TEXT)
        c.add_palette(name='Bad', attribute_classes=['NotRegistered'])
        errors = c.validate()
        assert any(e['type'] == 'palette_unknown_ref'
                   and 'NotRegistered' in e['message']
                   for e in errors)

    def test_known_refs_pass(self):
        c = ANXChart()
        c.add_entity_type(name='Person', icon_file='person')
        c.add_link_type(name='Call', color=0)
        c.add_attribute_class(name='Phone', type=AttributeType.TEXT)
        c.add_palette(
            name='Good',
            entity_types=['Person'],
            link_types=['Call'],
            attribute_classes=['Phone'],
        )
        assert not any(e['type'] == 'palette_unknown_ref'
                       for e in c.validate())


class TestPaletteInvalidClass:
    """`palette_invalid_class` flags AttributeClass entries that ANB rejects
    (is_user=False or user_can_add=False)."""

    def test_is_user_false_rejected(self):
        c = ANXChart()
        c.add_attribute_class(name='Sys', type=AttributeType.TEXT, is_user=False)
        c.add_palette(name='Bad', attribute_classes=['Sys'])
        errors = c.validate()
        assert any(e['type'] == 'palette_invalid_class' and 'is_user' in e['message']
                   for e in errors)

    def test_user_can_add_false_rejected(self):
        c = ANXChart()
        c.add_attribute_class(name='Locked', type=AttributeType.TEXT,
                              user_can_add=False)
        c.add_palette(name='Bad', attribute_classes=['Locked'])
        errors = c.validate()
        assert any(e['type'] == 'palette_invalid_class'
                   and 'user_can_add' in e['message']
                   for e in errors)

    def test_attribute_entry_is_user_false_rejected(self):
        c = ANXChart()
        c.add_attribute_class(name='Sys', type=AttributeType.TEXT, is_user=False)
        c.add_palette(
            name='Bad',
            attribute_entries=[PaletteAttributeEntry(name='Sys', value='x')],
        )
        errors = c.validate()
        assert any(
            e['type'] == 'palette_invalid_class'
            and 'is_user' in e['message']
            and 'attribute_entries' in e['location']
            for e in errors
        )

    def test_attribute_entry_user_can_add_false_rejected(self):
        c = ANXChart()
        c.add_attribute_class(
            name='Locked', type=AttributeType.TEXT, user_can_add=False,
        )
        c.add_palette(
            name='Bad',
            attribute_entries=[PaletteAttributeEntry(name='Locked', value='x')],
        )
        errors = c.validate()
        assert any(e['type'] == 'palette_invalid_class'
                   and 'user_can_add' in e['message']
                   for e in errors)

    def test_attribute_entry_missing_name(self):
        c = ANXChart()
        c.add_palette(
            name='Bad',
            attribute_entries=[PaletteAttributeEntry(name='', value='x')],
        )
        errors = c.validate()
        assert any(e['type'] == 'missing_required'
                   and 'attribute_entries' in e['location']
                   for e in errors)


class TestPaletteTypeMismatch:
    """`palette_type_mismatch` flags pre-filled palette values that don't
    match the AttributeClass type — but only when the type is inferred from
    entity/link data (Title-Case keys), not from an explicit AttributeClass
    declaration (lowercase keys).

    See ``test_audit_gaps.py`` xfail block below: the explicit-declaration
    path is broken (``validation.py`` compares against ``'Number'`` /
    ``'Flag'`` / ``'DateTime'`` Title Case but ``_enum_val(AttributeType.X)``
    returns lowercase). Tests below pin the working inference path.
    """

    def test_number_value_must_be_numeric_via_inference(self):
        c = ANXChart()
        # Inference: attr 'Balance' on an entity makes it a 'Number' in
        # ac_type_map. No explicit AttributeClass declared.
        c.add_icon(id='X', type='T', attributes={'Balance': 42.5})
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Balance', value='abc')],
        )
        errors = c.validate()
        assert any(e['type'] == 'palette_type_mismatch' for e in errors)

    def test_number_value_accepts_numeric_string_via_inference(self):
        c = ANXChart()
        c.add_icon(id='X', type='T', attributes={'Balance': 42.5})
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Balance', value='42.5')],
        )
        assert not any(e['type'] == 'palette_type_mismatch'
                       for e in c.validate())

    def test_flag_value_must_be_boolean_string_via_inference(self):
        c = ANXChart()
        c.add_icon(id='X', type='T', attributes={'Active': True})
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Active', value='maybe')],
        )
        errors = c.validate()
        assert any(e['type'] == 'palette_type_mismatch' for e in errors)

    @pytest.mark.parametrize('val', ['true', 'false', 'TRUE', 'False'])
    def test_flag_value_accepts_true_false_via_inference(self, val):
        c = ANXChart()
        c.add_icon(id='X', type='T', attributes={'Active': True})
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Active', value=val)],
        )
        assert not any(e['type'] == 'palette_type_mismatch'
                       for e in c.validate())


class TestPaletteTypeMismatchExplicitDeclaration:
    """``palette_type_mismatch`` fires for explicit AttributeClass declarations.

    Regression guard for the case-mismatch bug previously documented as
    PALETTE-1: ``ac_type_map`` was populated with lowercase strings from
    ``_enum_val(ac.type)`` while the downstream comparisons used Title
    Case, so the check silently never fired when a user declared an
    AttributeClass with explicit ``type=``. ``validate_palettes`` now
    canonicalises to Title Case at population time, matching the inferred
    branch.
    """

    def test_explicit_number_class_flags_bad_value(self):
        c = ANXChart()
        c.add_attribute_class(name='Balance', type=AttributeType.NUMBER)
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Balance', value='abc')],
        )
        assert any(e['type'] == 'palette_type_mismatch' for e in c.validate())

    def test_explicit_number_class_accepts_numeric_value(self):
        c = ANXChart()
        c.add_attribute_class(name='Balance', type=AttributeType.NUMBER)
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Balance', value='42.5')],
        )
        assert not any(e['type'] == 'palette_type_mismatch' for e in c.validate())

    def test_explicit_flag_class_flags_bad_value(self):
        c = ANXChart()
        c.add_attribute_class(name='Active', type=AttributeType.FLAG)
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Active', value='maybe')],
        )
        assert any(e['type'] == 'palette_type_mismatch' for e in c.validate())

    def test_explicit_flag_class_accepts_true_false(self):
        c = ANXChart()
        c.add_attribute_class(name='Active', type=AttributeType.FLAG)
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='Active', value='true')],
        )
        assert not any(e['type'] == 'palette_type_mismatch' for e in c.validate())

    def test_explicit_datetime_class_flags_bad_value(self):
        c = ANXChart()
        c.add_attribute_class(name='When', type=AttributeType.DATETIME)
        c.add_palette(
            name='P',
            attribute_entries=[PaletteAttributeEntry(name='When', value='yesterday')],
        )
        assert any(e['type'] == 'palette_type_mismatch' for e in c.validate())

    def test_explicit_datetime_class_accepts_xsd_format(self):
        c = ANXChart()
        c.add_attribute_class(name='When', type=AttributeType.DATETIME)
        c.add_palette(
            name='P',
            attribute_entries=[
                PaletteAttributeEntry(name='When', value='2024-01-15T14:30:00'),
            ],
        )
        assert not any(e['type'] == 'palette_type_mismatch' for e in c.validate())


# ─────────────────────────────────────────────────────────────────────────
# Semantic add_* convenience methods + add() dispatch
# ─────────────────────────────────────────────────────────────────────────


class TestSemanticLinkAdd:
    def test_kwargs(self):
        c = ANXChart()
        c.add_semantic_link(name='Surveilled', kind_of='Associate Of')
        assert len(c._semantic_links) == 1
        assert c._semantic_links[0].name == 'Surveilled'
        assert c._semantic_links[0].kind_of == 'Associate Of'

    def test_object(self):
        c = ANXChart()
        sl = SemanticLink(name='Watched', kind_of='Associate Of')
        c.add_semantic_link(sl)
        assert c._semantic_links[0] is sl

    def test_positional_name(self):
        c = ANXChart()
        c.add_semantic_link('Tracked', kind_of='Associate Of')
        assert c._semantic_links[0].name == 'Tracked'

    def test_upsert_replaces_by_name(self):
        c = ANXChart()
        c.add_semantic_link(name='X', kind_of='A')
        c.add_semantic_link(name='X', kind_of='B')
        assert len(c._semantic_links) == 1
        assert c._semantic_links[0].kind_of == 'B'

    def test_add_dispatch(self):
        c = ANXChart()
        c.add(SemanticLink(name='Z', kind_of='Associate Of'))
        assert len(c._semantic_links) == 1


class TestSemanticPropertyAdd:
    def test_kwargs(self):
        c = ANXChart()
        c.add_semantic_property(name='CPF Number', base_property='Abstract Text')
        assert c._semantic_properties[0].name == 'CPF Number'

    def test_object(self):
        c = ANXChart()
        sp = SemanticProperty(name='X', base_property='Abstract Text')
        c.add_semantic_property(sp)
        assert c._semantic_properties[0] is sp

    def test_positional_name(self):
        c = ANXChart()
        c.add_semantic_property('Y', base_property='Abstract Text')
        assert c._semantic_properties[0].name == 'Y'

    def test_upsert_replaces_by_name(self):
        c = ANXChart()
        c.add_semantic_property(name='X', base_property='Abstract Text')
        c.add_semantic_property(name='X', base_property='Abstract Number')
        assert len(c._semantic_properties) == 1
        assert c._semantic_properties[0].base_property == 'Abstract Number'

    def test_add_dispatch(self):
        c = ANXChart()
        c.add(SemanticProperty(name='Z', base_property='Abstract Text'))
        assert len(c._semantic_properties) == 1


class TestGenericAddDispatch:
    """`add()` dispatches on type. These specific branches were not covered
    by existing tests."""

    def test_add_palette_via_dispatch(self):
        c = ANXChart()
        c.add(Palette(name='P'))
        assert len(c._palettes) == 1

    def test_add_datetime_format_via_dispatch(self):
        c = ANXChart()
        c.add(DateTimeFormat(name='ISO', format='yyyy-MM-dd'))
        assert len(c._datetime_formats) == 1

    def test_add_entity_type_via_dispatch(self):
        c = ANXChart()
        c.add(EntityType(name='Person', icon_file='person'))
        assert len(c._entity_types) == 1

    def test_add_link_type_via_dispatch(self):
        c = ANXChart()
        c.add(LinkType(name='Call', color=0))
        assert len(c._link_types) == 1

    def test_add_unknown_type_raises(self):
        c = ANXChart()
        with pytest.raises(TypeError, match='Cannot add item of type'):
            c.add(object())

    def test_add_string_raises(self):
        c = ANXChart()
        with pytest.raises(TypeError):
            c.add('not a chart item')


# ─────────────────────────────────────────────────────────────────────────
# Validation rules previously only on the allowlist
# ─────────────────────────────────────────────────────────────────────────


class TestInvalidTimezone:
    """`invalid_timezone` errors when TimeZone is malformed."""

    def test_id_out_of_range(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='T', date='2024-01-15', time='10:00:00',
            timezone=TimeZone(id=999, name='UTC'),
        )
        assert any(e['type'] == 'invalid_timezone' for e in c.validate())

    def test_id_zero_is_invalid(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='T', date='2024-01-15', time='10:00:00',
            timezone=TimeZone(id=0, name='UTC'),
        )
        assert any(e['type'] == 'invalid_timezone' for e in c.validate())

    def test_missing_name(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='T', date='2024-01-15', time='10:00:00',
            timezone=TimeZone(id=1, name=''),
        )
        assert any(e['type'] == 'invalid_timezone' for e in c.validate())

    def test_wrong_type(self):
        c = ANXChart()
        # Bypass dataclass type check by setting the attribute directly to a
        # non-TimeZone, non-dict value to exercise the else branch.
        c.add_icon(id='A', type='T', date='2024-01-15', time='10:00:00')
        c._entities[0].timezone = "not a timezone"
        assert any(e['type'] == 'invalid_timezone' for e in c.validate())

    def test_dict_form_accepted(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', date='2024-01-15', time='10:00:00')
        c._entities[0].timezone = {'id': 1, 'name': 'UTC'}
        assert not any(e['type'] == 'invalid_timezone' for e in c.validate())


class TestTimezoneWithoutDatetime:
    def test_timezone_with_no_date_or_time(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', timezone=TimeZone(id=1, name='UTC'))
        assert any(e['type'] == 'timezone_without_datetime'
                   for e in c.validate())

    def test_timezone_with_only_date(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='T', date='2024-01-15',
            timezone=TimeZone(id=1, name='UTC'),
        )
        assert any(e['type'] == 'timezone_without_datetime'
                   for e in c.validate())

    def test_timezone_with_only_time(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='T', time='10:00:00',
            timezone=TimeZone(id=1, name='UTC'),
        )
        assert any(e['type'] == 'timezone_without_datetime'
                   for e in c.validate())

    def test_card_timezone_requires_both(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='T', date='2024-01-15', time='10:00:00',
            cards=[Card(date='2024-01-16', timezone=TimeZone(id=1, name='UTC'))],
        )
        assert any(e['type'] == 'timezone_without_datetime'
                   for e in c.validate())


class TestInvalidMultiplicity:
    def test_unknown_multiplicity_string(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', multiplicity='octuple')
        assert any(e['type'] == 'invalid_multiplicity'
                   for e in c.validate())

    def test_known_multiplicity_passes(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L',
                   multiplicity=Multiplicity.SINGLE)
        assert not any(e['type'] == 'invalid_multiplicity'
                       for e in c.validate())


class TestInvalidThemeWiring:
    def test_unknown_theme_wiring_string(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', theme_wiring='zigzag')
        assert any(e['type'] == 'invalid_theme_wiring'
                   for e in c.validate())

    def test_known_theme_wiring_passes(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L',
                   theme_wiring=ThemeWiring.GOES_TO_NEXT_EVENT)
        assert not any(e['type'] == 'invalid_theme_wiring'
                       for e in c.validate())


class TestConnectionConflict:
    def test_two_links_same_pair_conflicting_styles(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', multiplicity='single')
        c.add_link(from_id='A', to_id='B', type='L', multiplicity='multiple')
        assert any(e['type'] == 'connection_conflict' for e in c.validate())

    def test_two_links_same_pair_same_style_no_conflict(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', multiplicity='single')
        c.add_link(from_id='A', to_id='B', type='L', multiplicity='single')
        assert not any(e['type'] == 'connection_conflict'
                       for e in c.validate())

    def test_pair_canonically_sorted(self):
        """A->B and B->A are the same canonical pair — conflict must be
        detected regardless of direction."""
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', multiplicity='single')
        c.add_link(from_id='B', to_id='A', type='L', multiplicity='multiple')
        assert any(e['type'] == 'connection_conflict' for e in c.validate())


class TestInvalidSemanticType:
    """`invalid_semantic_type` flags i2 COM API names (LN-pattern)."""

    def test_ln_entity_pattern_rejected_on_entity_type(self):
        c = ANXChart()
        c.add_entity_type(name='Person', semantic_type='LNEntityPerson')
        assert any(e['type'] == 'invalid_semantic_type'
                   for e in c.validate())

    def test_ln_link_pattern_rejected_on_link_type(self):
        c = ANXChart()
        c.add_link_type(name='Call', semantic_type='LNLinkCall')
        assert any(e['type'] == 'invalid_semantic_type'
                   for e in c.validate())

    def test_ln_property_pattern_rejected_on_attribute_class(self):
        c = ANXChart()
        c.add_attribute_class(name='X', type=AttributeType.TEXT,
                              semantic_type='LNPropertyPhone')
        assert any(e['type'] == 'invalid_semantic_type'
                   for e in c.validate())

    def test_standard_name_passes(self):
        c = ANXChart()
        c.add_entity_type(name='Person', semantic_type='Person')
        assert not any(e['type'] == 'invalid_semantic_type'
                       for e in c.validate())


class TestSemanticEntityRequiredFields:
    def test_missing_name_flagged(self):
        c = ANXChart()
        c.add(SemanticEntity(name='', kind_of='Entity'))
        assert any(
            e['type'] == 'missing_required'
            and 'semantic_entities[0]' in e['location']
            for e in c.validate()
        )

    def test_missing_kind_of_when_not_abstract(self):
        c = ANXChart()
        c.add(SemanticEntity(name='X', kind_of='', abstract=False))
        assert any(
            e['type'] == 'missing_required'
            and 'semantic_entities[0]' in e['location']
            for e in c.validate()
        )

    def test_abstract_skips_kind_of_check(self):
        c = ANXChart()
        c.add(SemanticEntity(name='X', kind_of='', abstract=True))
        # No missing_required for kind_of when abstract
        errs = c.validate()
        kind_of_missing = [
            e for e in errs
            if e['type'] == 'missing_required'
            and 'semantic_entities[0]' in e['location']
        ]
        assert kind_of_missing == []

    def test_semantic_link_missing_name(self):
        c = ANXChart()
        c.add(SemanticLink(name='', kind_of='Associate Of'))
        assert any(
            e['type'] == 'missing_required'
            and 'semantic_links[0]' in e['location']
            for e in c.validate()
        )

    def test_semantic_property_missing_base_property(self):
        c = ANXChart()
        c.add(SemanticProperty(name='X', base_property='', abstract=False))
        assert any(
            e['type'] == 'missing_required'
            and 'semantic_properties[0]' in e['location']
            for e in c.validate()
        )


# ─────────────────────────────────────────────────────────────────────────
# Loose card target validation
# ─────────────────────────────────────────────────────────────────────────


class TestLooseCardMissingTarget:
    def test_unknown_entity_id(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_card(entity_id='Ghost', summary='hi')
        assert any(e['type'] == 'missing_target'
                   and 'entity_id' in e['message']
                   for e in c.validate())

    def test_unknown_link_id(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='L', link_id='call_001')
        c.add_card(link_id='no_such_link', summary='hi')
        assert any(e['type'] == 'missing_target'
                   and 'link_id' in e['message']
                   for e in c.validate())

    def test_known_entity_id_passes(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_card(entity_id='A', summary='hi')
        assert not any(e['type'] == 'missing_target'
                       for e in c.validate())


# ─────────────────────────────────────────────────────────────────────────
# Legend item validation
# ─────────────────────────────────────────────────────────────────────────


class TestInvalidLegendType:
    def test_unknown_string_type(self):
        c = ANXChart()
        c.add_legend_item(name='X', item_type='NotALegendType')
        assert any(e['type'] == 'invalid_legend_type'
                   for e in c.validate())

    def test_legend_missing_name(self):
        c = ANXChart()
        c.add_legend_item(LegendItem(name='', item_type=LegendItemType.ICON))
        assert any(e['type'] == 'missing_required'
                   and 'legend_items[0]' in e['location']
                   for e in c.validate())

    @pytest.mark.parametrize('val', [
        LegendItemType.ICON, 'icon', 'Icon', 'ICON',
        LegendItemType.LINK, 'link', 'Link',
        LegendItemType.ICON_FRAME, 'icon_frame', 'IconFrame',
    ])
    def test_known_type_aliases_pass(self, val):
        c = ANXChart()
        c.add_legend_item(name='X', item_type=val)
        assert not any(e['type'] == 'invalid_legend_type'
                       for e in c.validate())


# ─────────────────────────────────────────────────────────────────────────
# Duplicate-name validation across registries
# ─────────────────────────────────────────────────────────────────────────


class TestDuplicateNameRegistries:
    """`duplicate_name` errors when two entries share a name in a registry
    that requires uniqueness. Tested by injecting duplicates directly into
    the underlying list — the public `add_*` methods upsert by name, so
    they can't surface this error path."""

    def test_duplicate_entity_type(self):
        c = ANXChart()
        c._entity_types.append(EntityType(name='Person'))
        c._entity_types.append(EntityType(name='Person'))
        assert any(e['type'] == 'duplicate_name'
                   and 'entity_types' in e['location']
                   for e in c.validate())

    def test_duplicate_link_type(self):
        c = ANXChart()
        c._link_types.append(LinkType(name='Call'))
        c._link_types.append(LinkType(name='Call'))
        assert any(e['type'] == 'duplicate_name'
                   and 'link_types' in e['location']
                   for e in c.validate())

    def test_duplicate_attribute_class(self):
        c = ANXChart()
        c._attribute_classes.append(
            AttributeClass(name='Phone', type=AttributeType.TEXT)
        )
        c._attribute_classes.append(
            AttributeClass(name='Phone', type=AttributeType.TEXT)
        )
        assert any(e['type'] == 'duplicate_name'
                   and 'attribute_classes' in e['location']
                   for e in c.validate())

    def test_duplicate_strength_name(self):
        c = ANXChart()
        from anxwritter import StrengthCollection, DotStyle
        c.strengths = StrengthCollection(items=[
            Strength(name='Confirmed', dot_style=DotStyle.SOLID),
            Strength(name='Confirmed', dot_style=DotStyle.DASHED),
        ])
        assert any(e['type'] == 'duplicate_name'
                   and 'strengths' in e['location']
                   for e in c.validate())


# ─────────────────────────────────────────────────────────────────────────
# Utility edge cases
# ─────────────────────────────────────────────────────────────────────────


class TestIsValidColorEdges:
    def test_nan_float_rejected(self):
        # NaN is not a valid colour value — branch in utils.py:55-57
        assert _is_valid_color(float('nan')) is False

    def test_float_in_range_accepted(self):
        # Floats in [0, 0xFFFFFF] are considered valid (branch coverage)
        assert _is_valid_color(123.45) is True

    def test_float_out_of_range_rejected(self):
        assert _is_valid_color(-1.0) is False
        assert _is_valid_color(float(0x1000000)) is False

    def test_invalid_hex_with_hash_falls_through(self):
        # Triggers the branch where '#XXXXXX' is 7 chars but parse fails.
        # color_to_colorref then raises and the function returns False.
        assert _is_valid_color('#GGGGGG') is False


class TestValidateDateTypes:
    def test_python_date_instance_accepted(self):
        assert _validate_date(date(2024, 1, 15)) is True

    def test_python_datetime_instance_accepted(self):
        assert _validate_date(datetime(2024, 1, 15, 14, 30)) is True

    def test_whitespace_only_string_rejected(self):
        assert _validate_date('   ') is False


class TestValidateTimeTypes:
    def test_python_time_instance_accepted(self):
        assert _validate_time(time(14, 30, 0)) is True

    def test_python_datetime_instance_accepted(self):
        assert _validate_time(datetime(2024, 1, 15, 14, 30)) is True

    def test_whitespace_only_string_rejected(self):
        assert _validate_time('   ') is False


# ─────────────────────────────────────────────────────────────────────────
# ANXValidationError exception structure
# ─────────────────────────────────────────────────────────────────────────


class TestANXValidationError:
    def test_errors_attribute_preserved(self):
        c = ANXChart()
        c.add_icon(type='Person')  # no id
        with pytest.raises(ANXValidationError) as exc_info:
            c.to_xml()
        assert isinstance(exc_info.value.errors, list)
        assert len(exc_info.value.errors) >= 1
        assert 'type' in exc_info.value.errors[0]

    def test_str_includes_count_and_messages(self):
        c = ANXChart()
        c.add_icon(type='Person')  # no id
        c.add_icon(id='B', type='T', color='Banana')
        with pytest.raises(ANXValidationError) as exc_info:
            c.to_xml()
        msg = str(exc_info.value)
        assert 'validation error' in msg
        assert 'missing_required' in msg
        assert 'unknown_color' in msg

    def test_can_be_caught_as_exception(self):
        c = ANXChart()
        c.add_icon(type='Person')
        with pytest.raises(Exception):
            c.to_xml()

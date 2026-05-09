"""Tests for entity and link typed API."""

import pytest

from anxwritter import ANXChart, Card, EntityType, LinkType, GradeCollection, TimeZone
from anxwritter.entities import Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label
from anxwritter.models import Link, AttributeClass, Strength, LegendItem
from anxwritter.enums import DotStyle, AttributeType


class TestEntityAdd:
    def test_add_icon(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        assert len(c._entities) == 1
        assert isinstance(c._entities[0], Icon)

    def test_add_box(self):
        c = ANXChart()
        c.add_box(id='B', type='Org', width=150)
        assert len(c._entities) == 1
        assert isinstance(c._entities[0], Box)
        assert c._entities[0].width == 150

    def test_add_circle(self):
        c = ANXChart()
        c.add_circle(id='C', type='Event')
        assert isinstance(c._entities[0], Circle)

    def test_add_theme_line(self):
        c = ANXChart()
        c.add_theme_line(id='T', type='Period')
        assert isinstance(c._entities[0], ThemeLine)

    def test_add_event_frame(self):
        c = ANXChart()
        c.add_event_frame(id='E', type='Frame')
        assert isinstance(c._entities[0], EventFrame)

    def test_add_text_block(self):
        c = ANXChart()
        c.add_text_block(id='TB', type='Note')
        assert isinstance(c._entities[0], TextBlock)

    def test_add_label(self):
        c = ANXChart()
        c.add_label(id='L', type='Label')
        assert isinstance(c._entities[0], Label)

    def test_add_generic_entity(self):
        c = ANXChart()
        c.add(Icon(id='X', type='T'))
        assert len(c._entities) == 1

    def test_add_all(self):
        c = ANXChart()
        c.add_all([Icon(id='A', type='T'), Box(id='B', type='O')])
        assert len(c._entities) == 2

    def test_add_wrong_type_raises(self):
        c = ANXChart()
        try:
            c.add("not an entity")
            assert False, "Should have raised TypeError"
        except TypeError:
            pass


class TestLinkAdd:
    def test_add_link_kwargs(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call')
        assert len(c._links) == 1
        assert c._links[0].from_id == 'A'

    def test_add_link_object(self):
        c = ANXChart()
        c.add(Link(from_id='A', to_id='B'))
        assert len(c._links) == 1


class TestStrengthAdd:
    def test_default_strength_present(self):
        c = ANXChart()
        names = [st.name for st in c.strengths]
        assert 'Default' in names

    def test_add_strength_kwargs(self):
        c = ANXChart()
        c.add_strength(name='Confirmed', dot_style=DotStyle.SOLID)
        names = [st.name for st in c.strengths]
        assert 'Confirmed' in names

    def test_add_strength_object(self):
        c = ANXChart()
        c.add(Strength(name='Dashed', dot_style=DotStyle.DASHED))
        assert len(c.strengths) == 2


class TestAttributeClassAdd:
    def test_add_attribute_class_kwargs(self):
        c = ANXChart()
        c.add_attribute_class(name='Phone', prefix='Tel: ')
        assert len(c._attribute_classes) == 1
        assert c._attribute_classes[0].name == 'Phone'
        assert c._attribute_classes[0].prefix == 'Tel: '

    def test_add_attribute_class_positional(self):
        c = ANXChart()
        c.add_attribute_class('Balance', prefix='R$ ')
        assert c._attribute_classes[0].name == 'Balance'

    def test_add_attribute_class_object(self):
        c = ANXChart()
        c.add(AttributeClass(name='Score', type=AttributeType.NUMBER))
        assert len(c._attribute_classes) == 1


class TestLegendItemAdd:
    def test_add_legend_item_kwargs(self):
        c = ANXChart()
        c.add_legend_item(name='Person', item_type='Icon')
        assert len(c._legend_items) == 1
        assert c._legend_items[0].name == 'Person'

    def test_add_legend_item_positional(self):
        c = ANXChart()
        c.add_legend_item('My Name')
        assert c._legend_items[0].name == 'My Name'


class TestGradesAndSourceTypes:
    def test_grades_one_list(self):
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Always reliable', 'Usually reliable'])
        assert len(c.grades_one) == 2

    def test_source_types_list(self):
        c = ANXChart()
        c.source_types = ['Witness', 'Officer']
        assert c.source_types[1] == 'Officer'


class TestEntityBuild:
    def test_icon_builds_xml(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        xml = c.to_xml()
        assert 'Person' in xml

    def test_box_builds_xml(self):
        c = ANXChart()
        c.add_box(id='A', type='Org')
        xml = c.to_xml()
        assert 'Org' in xml

    def test_circle_builds_xml(self):
        c = ANXChart()
        c.add_circle(id='A', type='Event')
        xml = c.to_xml()
        assert 'Event' in xml

    def test_mixed_entities_build(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        c.add_box(id='B', type='Org')
        c.add_circle(id='C', type='Event')
        c.add_link(from_id='A', to_id='B', type='Works')
        xml = c.to_xml()
        assert 'Person' in xml
        assert 'Org' in xml
        assert 'Event' in xml


class TestEntityTypeAdd:
    def test_add_entity_type_kwargs(self):
        c = ANXChart()
        c.add_entity_type(name='Person', icon_file='person', color='Blue')
        assert len(c._entity_types) == 1
        assert c._entity_types[0].name == 'Person'

    def test_add_entity_type_object(self):
        c = ANXChart()
        c.add(EntityType(name='Vehicle', icon_file='vehicle'))
        assert len(c._entity_types) == 1

    def test_add_link_type_kwargs(self):
        c = ANXChart()
        c.add_link_type(name='Call', color=255)
        assert len(c._link_types) == 1
        assert c._link_types[0].name == 'Call'

    def test_add_link_type_object(self):
        c = ANXChart()
        c.add(LinkType(name='Owns', color=0))
        assert len(c._link_types) == 1


class TestStrengthReplace:
    def test_strength_replace_by_name(self):
        c = ANXChart()
        # Default is pre-populated as DotStyleSolid
        c.add_strength('Default', dot_style=DotStyle.DASHED)
        # Should replace, not duplicate
        assert len(c.strengths.items) == 1
        assert c.strengths.items[0].dot_style == DotStyle.DASHED


class TestCustomProperty:
    def test_add_custom_property(self):
        c = ANXChart()
        c.add_custom_property('CaseRef', 'CR-2025-001')
        c.add_custom_property('Classification', 'RESTRICTED')
        # Check that properties are stored correctly
        assert len(c.settings.summary.custom_properties) == 2
        assert c.settings.summary.custom_properties[0].name == 'CaseRef'
        assert c.settings.summary.custom_properties[0].value == 'CR-2025-001'
        assert c.settings.summary.custom_properties[1].name == 'Classification'
        assert c.settings.summary.custom_properties[1].value == 'RESTRICTED'

    def test_custom_property_in_xml(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')  # need at least one entity
        c.add_custom_property('TestProp', 'TestValue')
        xml = c.to_xml()
        assert 'CustomPropertyCollection' in xml
        assert 'Name="TestProp"' in xml
        assert 'Value="TestValue"' in xml


class TestPaletteAdd:
    def test_add_palette_kwargs(self):
        from anxwritter import Palette
        c = ANXChart()
        c.add_entity_type(name='Person', icon_file='person')
        c.add_link_type(name='Call', color=0)
        c.add_palette(name='Investigation', entity_types=['Person'], link_types=['Call'])
        assert len(c._palettes) == 1
        assert c._palettes[0].name == 'Investigation'
        assert 'Person' in c._palettes[0].entity_types
        assert 'Call' in c._palettes[0].link_types

    def test_add_palette_object(self):
        from anxwritter import Palette
        c = ANXChart()
        c.add_entity_type(name='Vehicle', icon_file='vehicle')
        c.add(Palette(name='Standard', entity_types=['Vehicle']))
        assert len(c._palettes) == 1
        assert c._palettes[0].name == 'Standard'

    def test_palette_in_xml(self):
        from anxwritter import Palette
        c = ANXChart()
        c.add_entity_type(name='Person', icon_file='person')
        c.add_icon(id='A', type='Person')
        c.add_palette(name='MyPalette', entity_types=['Person'])
        xml = c.to_xml()
        assert 'PaletteCollection' in xml
        assert 'Name="MyPalette"' in xml


class TestCardsCoercion:
    """``cards=`` on entities and links accepts dicts (parity with YAML loader)
    and rejects non-Card/non-dict items with a clear TypeError pointing at
    ``anxwritter.Card``. Direct dataclass construction is also covered, since
    coercion lives in ``__post_init__``."""

    def test_link_cards_accepts_dict(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(
            from_id='A', to_id='B', type='Call',
            cards=[{'summary': 'intercept', 'date': '2024-01-15'}],
        )
        link_card = c._links[0].cards[0]
        assert isinstance(link_card, Card)
        assert link_card.summary == 'intercept'
        xml = c.to_xml()
        assert 'Summary="intercept"' in xml

    def test_entity_cards_accepts_dict(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='Person',
            cards=[{'summary': 'main suspect', 'date': '2024-01-15'}],
        )
        entity_card = c._entities[0].cards[0]
        assert isinstance(entity_card, Card)
        assert entity_card.summary == 'main suspect'
        xml = c.to_xml()
        assert 'Summary="main suspect"' in xml

    def test_card_dict_with_dict_timezone(self):
        c = ANXChart()
        c.add_icon(
            id='A', type='Person',
            cards=[{
                'summary': 'tz card',
                'date': '2024-01-15',
                'time': '14:30:00',
                'timezone': {'id': 1, 'name': 'UTC'},
            }],
        )
        card = c._entities[0].cards[0]
        assert isinstance(card.timezone, TimeZone)
        assert card.timezone.id == 1
        # End-to-end: builds without raising
        c.to_xml()

    def test_link_cards_rejects_non_card_non_dict(self):
        with pytest.raises(TypeError, match=r'anxwritter\.Card'):
            Link(from_id='A', to_id='B', cards=['not a card'])

    def test_entity_cards_rejects_non_card_non_dict(self):
        with pytest.raises(TypeError, match=r'anxwritter\.Card'):
            Icon(id='A', type='T', cards=[42])

    def test_add_link_cards_rejects_non_card_non_dict(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        with pytest.raises(TypeError, match=r'anxwritter\.Card'):
            c.add_link(from_id='A', to_id='B', cards=[None])

    def test_card_instances_pass_through_unchanged(self):
        original = Card(summary='kept', date='2024-01-15')
        link = Link(from_id='A', to_id='B', cards=[original])
        assert link.cards[0] is original

    def test_mixed_card_and_dict(self):
        link = Link(
            from_id='A', to_id='B',
            cards=[
                Card(summary='one'),
                {'summary': 'two'},
            ],
        )
        assert all(isinstance(c, Card) for c in link.cards)
        assert [c.summary for c in link.cards] == ['one', 'two']

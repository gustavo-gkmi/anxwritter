"""Characterization of palette serialization across the config-export path
(``to_config_dict``) and the build path (``to_xml`` → ``<Palette>``).

These two paths historically built the palette dict independently with subtly
different shapes (config drops falsy ``locked`` and ``None`` entry values; build
keeps them). This pins both shapes before they are unified behind one helper.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from anxwritter import ANXChart, Palette, PaletteAttributeEntry


def _chart_with_palette(locked: bool) -> ANXChart:
    c = ANXChart()
    c.add_attribute_class('Phone', type='text')
    c.add_entity_type('Person')
    c.add_link_type('Call')
    c.add_icon(id='A', type='Person')
    c.add_palette(Palette(
        name='P',
        locked=locked,
        entity_types=['Person'],
        link_types=['Call'],
        attribute_classes=['Phone'],
        attribute_entries=[
            PaletteAttributeEntry(name='Phone', value='x'),
            PaletteAttributeEntry(name='Phone'),  # value None
        ],
    ))
    return c


class TestConfigExportShape:
    def test_locked_false_omitted_and_none_value_dropped(self):
        pals = _chart_with_palette(locked=False).to_config_dict()['palettes']
        assert pals == [{
            'name': 'P',
            'entity_types': ['Person'],
            'link_types': ['Call'],
            'attribute_classes': ['Phone'],
            'attribute_entries': [{'name': 'Phone', 'value': 'x'}, {'name': 'Phone'}],
        }]

    def test_locked_true_present(self):
        pals = _chart_with_palette(locked=True).to_config_dict()['palettes']
        assert pals[0]['locked'] is True


class TestBuildEmission:
    def test_palette_element_emitted(self):
        root = ET.fromstring(_chart_with_palette(locked=True).to_xml())
        pal = root.find('.//Palette')
        assert pal is not None
        assert pal.get('Name') == 'P'
        assert pal.get('Locked') == 'true'
        # Entity / link / attribute-class entry collections present.
        assert pal.find('.//EntityTypeEntry').get('Entity') == 'Person'
        assert pal.find('.//LinkTypeEntry').get('LinkType') == 'Call'
        # One attribute entry carries a Value, the None one does not.
        values = [e.get('Value') for e in pal.findall('.//AttributeEntryCollection/AttributeClassEntry')]
        assert 'x' in values
        assert None in values

    def test_unlocked_palette_has_no_locked_attr(self):
        root = ET.fromstring(_chart_with_palette(locked=False).to_xml())
        pal = root.find('.//Palette')
        assert pal.get('Locked') is None

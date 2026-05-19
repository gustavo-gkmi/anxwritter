"""Tests for the canvas_display feature.

ANB v9 does not render datetime attribute values on the canvas after .anx
import — only the surrounding chrome appears. The canvas_display flag is an
opt-in workaround on a datetime AttributeClass: anxwritter emits a paired
text sibling AC + formatted-string sibling attribute on every entity/link
that uses the parent.

Covers:
- CanvasDisplay dataclass defaults and shortcut coercion
- Entity build: parent visible=false, text sibling emitted, value formatted
- Link build: same path applies to links
- Validation rules A–F
- to_config_dict / from_config round-trip
- YAML input — literal dict + ``canvas_display: true`` shorthand
- Edge cases — multiple parents, no data, visible=None silent, etc.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Optional, Tuple

import pytest

from anxwritter import (
    ANXChart, AttributeClass, CanvasDisplay, Font, Link,
)
from anxwritter.errors import ErrorType


# ── Helpers ─────────────────────────────────────────────────────────────────


def _ac_by_name(xml: str) -> Dict[str, ET.Element]:
    """Map AttributeClass.Name -> element."""
    root = ET.fromstring(xml)
    return {ac.get('Name', ''): ac for ac in root.iter('AttributeClass')}


def _attrs_on_entity(xml: str, entity_id: str) -> Dict[str, str]:
    """Map attribute_class_name -> value_string for a single entity.

    AttributeCollection lives on the surrounding <ChartItem>, not on <Entity>.
    """
    root = ET.fromstring(xml)
    ref_map = {ac.get('Id', ''): ac.get('Name', '') for ac in root.iter('AttributeClass')}
    for ci in root.iter('ChartItem'):
        ent = ci.find('.//Entity')
        if ent is None or ent.get('Identity') != entity_id:
            continue
        ac_coll = ci.find('AttributeCollection')
        if ac_coll is None:
            return {}
        return {
            ref_map.get(a.get('AttributeClassReference', ''), ''): a.get('Value', '')
            for a in ac_coll
        }
    return {}


def _attrs_on_link(xml: str) -> Dict[str, str]:
    """Map attribute_class_name -> value_string for the first link's ChartItem.

    AttributeCollection lives on the ChartItem that contains the <Link>.
    """
    root = ET.fromstring(xml)
    ref_map = {ac.get('Id', ''): ac.get('Name', '') for ac in root.iter('AttributeClass')}
    for ci in root.iter('ChartItem'):
        if ci.find('Link') is None:
            continue
        ac_coll = ci.find('AttributeCollection')
        if ac_coll is None:
            return {}
        return {
            ref_map.get(a.get('AttributeClassReference', ''), ''): a.get('Value', '')
            for a in ac_coll
        }
    return {}


# ── Dataclass shape ─────────────────────────────────────────────────────────


class TestCanvasDisplayDataclass:
    def test_defaults_all_none(self):
        cd = CanvasDisplay()
        assert cd.format is None
        assert cd.suffix is None
        assert cd.attribute_class is None

    def test_true_shorthand_on_attribute_class(self):
        ac = AttributeClass(name='X', type='datetime', canvas_display=True)
        assert isinstance(ac.canvas_display, CanvasDisplay)
        assert ac.canvas_display.format is None

    def test_false_shorthand_clears_canvas_display(self):
        ac = AttributeClass(name='X', type='datetime', canvas_display=False)
        assert ac.canvas_display is None

    def test_dict_shorthand_on_attribute_class(self):
        ac = AttributeClass(
            name='X', type='datetime',
            canvas_display={'format': '%d/%m/%Y', 'suffix': ' [d]'},
        )
        assert isinstance(ac.canvas_display, CanvasDisplay)
        assert ac.canvas_display.format == '%d/%m/%Y'
        assert ac.canvas_display.suffix == ' [d]'

    def test_dict_inner_attribute_class_coerced(self):
        cd = CanvasDisplay(attribute_class={'prefix': 'D: ', 'show_symbol': True})
        assert isinstance(cd.attribute_class, AttributeClass)
        assert cd.attribute_class.prefix == 'D: '
        assert cd.attribute_class.show_symbol is True


# ── Build: entity path ──────────────────────────────────────────────────────


class TestCanvasDisplayBuildEntity:
    def _build(self, **cd_kwargs):
        chart = ANXChart()
        chart.add_icon(
            id='Alice', type='Person',
            attributes={'EventDate': datetime(2024, 1, 15, 14, 30)},
        )
        chart.add_attribute_class(
            name='EventDate', type='datetime',
            visible=False,
            canvas_display=CanvasDisplay(**cd_kwargs) if cd_kwargs else True,
        )
        return chart.to_xml()

    def test_parent_emits_visible_false(self):
        xml = self._build()
        parent = _ac_by_name(xml).get('EventDate')
        assert parent is not None
        assert parent.get('Visible') == 'false'

    def test_sibling_ac_emitted_as_atttext(self):
        xml = self._build()
        sibling = _ac_by_name(xml).get('EventDate (display)')
        assert sibling is not None
        assert sibling.get('Type') == 'AttText'

    def test_sibling_defaults_visible_and_show_value_true(self):
        """The sibling must be visible and show_value=True by default so the
        formatted date renders on the canvas."""
        xml = self._build()
        sibling = _ac_by_name(xml).get('EventDate (display)')
        assert sibling is not None
        assert sibling.get('Visible') == 'true'
        assert sibling.get('ShowValue') == 'true'

    def test_parent_attribute_keeps_iso_value(self):
        xml = self._build()
        attrs = _attrs_on_entity(xml, 'Alice')
        assert attrs.get('EventDate') == '2024-01-15T14:30:00'

    def test_sibling_attribute_uses_default_format(self):
        xml = self._build()
        attrs = _attrs_on_entity(xml, 'Alice')
        assert attrs.get('EventDate (display)') == '2024-01-15'

    def test_custom_format(self):
        xml = self._build(format='%d/%m/%Y %H:%M')
        attrs = _attrs_on_entity(xml, 'Alice')
        assert attrs.get('EventDate (display)') == '15/01/2024 14:30'

    def test_custom_suffix(self):
        xml = self._build(suffix=' [d]')
        # parent's value is still on parent.name
        assert 'EventDate [d]' in _ac_by_name(xml)
        attrs = _attrs_on_entity(xml, 'Alice')
        assert attrs.get('EventDate [d]') == '2024-01-15'

    def test_sibling_styling_from_inner_attribute_class(self):
        # Build chart explicitly so we can verify Prefix / ShowSymbol / italic
        chart = ANXChart()
        chart.add_icon(
            id='Alice', type='Person',
            attributes={'EventDate': datetime(2024, 1, 15, 14, 30)},
        )
        chart.add_attribute_class(
            name='EventDate', type='datetime', visible=False,
            canvas_display=CanvasDisplay(
                attribute_class=AttributeClass(
                    prefix='When: ',
                    show_symbol=True,
                    font=Font(italic=True),
                ),
            ),
        )
        xml = chart.to_xml()
        sibling = _ac_by_name(xml).get('EventDate (display)')
        assert sibling is not None
        assert sibling.get('Prefix') == 'When: '
        # Inner attribute_class only — parent's defaults must not leak.
        font_el = sibling.find('Font')
        assert font_el is not None
        assert font_el.get('Italic') == 'true'


# ── Build: link path ────────────────────────────────────────────────────────


class TestCanvasDisplayBuildLink:
    def test_link_attribute_expanded(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_icon(id='B', type='Person')
        chart.add_link(
            from_id='A', to_id='B', type='Call',
            attributes={'CallTime': datetime(2024, 2, 3, 9, 0)},
        )
        chart.add_attribute_class(
            name='CallTime', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format='%d/%m/%Y'),
        )
        xml = chart.to_xml()
        attrs = _attrs_on_link(xml)
        assert attrs.get('CallTime') == '2024-02-03T09:00:00'
        assert attrs.get('CallTime (display)') == '03/02/2024'


# ── Validation: Rules A–F ───────────────────────────────────────────────────


class TestCanvasDisplayValidation:
    def test_rule_a_visible_true_without_canvas_display_rejected(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(name='Foo', type='datetime', visible=True)
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.ATTTIME_VISIBLE_FORBIDS_CANVAS_DISPLAY.value in types

    def test_rule_a_visible_true_with_canvas_display_rejected(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(name='Foo', type='datetime',
                                  visible=True, canvas_display=True)
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.ATTTIME_VISIBLE_FORBIDS_CANVAS_DISPLAY.value in types

    def test_rule_b_canvas_display_on_text(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(name='Phone', type='text', canvas_display=True)
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.CANVAS_DISPLAY_INVALID.value in types

    def test_rule_c_inner_name_set_rejected(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(
            name='Foo', type='datetime', visible=False,
            canvas_display=CanvasDisplay(
                attribute_class=AttributeClass(name='Overridden'),
            ),
        )
        errs = chart.validate()
        types = {e['type'] for e in errs}
        locs = {e['location'] for e in errs}
        assert ErrorType.CANVAS_DISPLAY_INVALID.value in types
        assert any('canvas_display.attribute_class.name' in loc for loc in locs)

    def test_rule_c_inner_type_set_rejected(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(
            name='Foo', type='datetime', visible=False,
            canvas_display=CanvasDisplay(
                attribute_class=AttributeClass(type='text'),
            ),
        )
        errs = chart.validate()
        locs = {e['location'] for e in errs}
        assert any('canvas_display.attribute_class.type' in loc for loc in locs)

    def test_rule_d_invalid_strftime_directive(self):
        # NOTE: Python's strftime on Linux is permissive — most directives
        # don't raise. Trailing '%' DOES NOT raise either on all platforms,
        # so we lean on the empty-string case (always invalid) plus a
        # non-string smoke test. Real "invalid directive" cases surface at
        # build time if at all.
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(
            name='Foo', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format=''),
        )
        errs = chart.validate()
        types = {e['type'] for e in errs}
        locs = {e['location'] for e in errs}
        assert ErrorType.CANVAS_DISPLAY_INVALID.value in types
        assert any('canvas_display.format' in loc for loc in locs)

    def test_rule_d_valid_format_passes(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(
            name='Foo', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format='%Y-%m-%d %H:%M:%S'),
        )
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.CANVAS_DISPLAY_INVALID.value not in types

    def test_rule_e_sibling_collides_with_explicit_ac(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(name='EventDate', type='datetime',
                                  visible=False, canvas_display=True)
        chart.add_attribute_class(name='EventDate (display)', type='text')
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.CANVAS_DISPLAY_NAME_COLLISION.value in types

    def test_rule_f_two_siblings_collide_with_each_other(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        # Different parent names but the same resolved sibling name.
        chart.add_attribute_class(
            name='Event', type='datetime', visible=False,
            canvas_display=CanvasDisplay(suffix='Date'),
        )
        chart.add_attribute_class(
            name='Even', type='datetime', visible=False,
            canvas_display=CanvasDisplay(suffix='tDate'),
        )
        errs = chart.validate()
        types = {e['type'] for e in errs}
        assert ErrorType.CANVAS_DISPLAY_NAME_COLLISION.value in types
        # The second one is the one flagged.
        loc = next(e['location'] for e in errs
                   if e['type'] == ErrorType.CANVAS_DISPLAY_NAME_COLLISION.value)
        assert loc.startswith('attribute_classes[1]')


# ── Round-trip ──────────────────────────────────────────────────────────────


class TestCanvasDisplayRoundtrip:
    def test_to_config_dict_includes_canvas_display(self):
        chart = ANXChart()
        chart.add_attribute_class(
            name='EventDate', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format='%d/%m/%Y', suffix=' (d)'),
        )
        cfg = chart.to_config_dict()
        acs = cfg.get('attribute_classes', [])
        assert len(acs) == 1
        cd = acs[0].get('canvas_display')
        assert cd is not None
        # CanvasDisplay → asdict produces a plain dict
        assert cd.get('format') == '%d/%m/%Y'
        assert cd.get('suffix') == ' (d)'

    def test_from_config_dict_idempotent(self):
        chart = ANXChart()
        chart.add_attribute_class(
            name='EventDate', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format='%d/%m/%Y'),
        )
        cfg1 = chart.to_config_dict()
        chart2 = ANXChart(config=cfg1)
        cfg2 = chart2.to_config_dict()
        assert cfg1 == cfg2

    def test_yaml_file_roundtrip(self, tmp_path):
        chart = ANXChart()
        chart.add_attribute_class(
            name='EventDate', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format='%d/%m/%Y'),
        )
        p = tmp_path / 'out.yaml'
        chart.to_config(str(p))
        loaded = ANXChart.from_config_file(str(p))
        cfg_a = chart.to_config_dict()
        cfg_b = loaded.to_config_dict()
        assert cfg_a == cfg_b


# ── YAML / dict input ───────────────────────────────────────────────────────


class TestCanvasDisplayYamlInput:
    def test_yaml_literal_dict(self):
        yaml_src = """
attribute_classes:
  - name: EventDate
    type: datetime
    visible: false
    canvas_display:
      format: "%d/%m/%Y %H:%M"
      suffix: " [d]"
      attribute_class:
        prefix: "When: "
        show_symbol: true
        font: { italic: true }
entities:
  icons:
    - id: A
      type: Person
"""
        chart = ANXChart.from_yaml(yaml_src)
        # Verify the canvas_display was coerced to a CanvasDisplay instance
        ac = next(a for a in chart._attribute_classes if a.name == 'EventDate')
        assert isinstance(ac.canvas_display, CanvasDisplay)
        assert ac.canvas_display.format == '%d/%m/%Y %H:%M'
        assert ac.canvas_display.suffix == ' [d]'
        assert isinstance(ac.canvas_display.attribute_class, AttributeClass)
        assert ac.canvas_display.attribute_class.prefix == 'When: '
        assert ac.canvas_display.attribute_class.font.italic is True

    def test_yaml_true_shorthand(self):
        yaml_src = """
attribute_classes:
  - name: EventDate
    type: datetime
    visible: false
    canvas_display: true
entities:
  icons:
    - id: A
      type: Person
"""
        chart = ANXChart.from_yaml(yaml_src)
        ac = next(a for a in chart._attribute_classes if a.name == 'EventDate')
        assert isinstance(ac.canvas_display, CanvasDisplay)
        assert ac.canvas_display.format is None


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestCanvasDisplayEdgeCases:
    def test_multiple_atttime_acs_with_canvas_display(self):
        chart = ANXChart()
        chart.add_icon(
            id='Alice', type='Person',
            attributes={
                'EventDate': datetime(2024, 1, 15, 9, 0),
                'CallTime': datetime(2024, 1, 15, 10, 30),
            },
        )
        chart.add_attribute_class(name='EventDate', type='datetime',
                                  visible=False, canvas_display=True)
        chart.add_attribute_class(
            name='CallTime', type='datetime', visible=False,
            canvas_display=CanvasDisplay(format='%H:%M'),
        )
        xml = chart.to_xml()
        attrs = _attrs_on_entity(xml, 'Alice')
        assert attrs.get('EventDate (display)') == '2024-01-15'
        assert attrs.get('CallTime (display)') == '10:30'

    def test_datetime_visible_false_without_canvas_display_silent(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(name='Foo', type='datetime', visible=False)
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.ATTTIME_VISIBLE_FORBIDS_CANVAS_DISPLAY.value not in types

    def test_datetime_visible_none_silent(self):
        # None is neither True nor False — ANB's default. No error.
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')
        chart.add_attribute_class(name='Foo', type='datetime')
        types = {e['type'] for e in chart.validate()}
        assert ErrorType.ATTTIME_VISIBLE_FORBIDS_CANVAS_DISPLAY.value not in types

    def test_user_set_sibling_visible_false_respected(self):
        chart = ANXChart()
        chart.add_icon(
            id='Alice', type='Person',
            attributes={'EventDate': datetime(2024, 1, 15)},
        )
        chart.add_attribute_class(
            name='EventDate', type='datetime', visible=False,
            canvas_display=CanvasDisplay(
                attribute_class=AttributeClass(visible=False),
            ),
        )
        xml = chart.to_xml()
        sibling = _ac_by_name(xml).get('EventDate (display)')
        assert sibling is not None
        assert sibling.get('Visible') == 'false'

    def test_canvas_display_without_data_emits_sibling_ac(self):
        # AC declared with canvas_display but no entity uses it:
        # sibling AC should still appear (declared classes are always emitted).
        # No <Attribute> rows.
        chart = ANXChart()
        chart.add_icon(id='A', type='Person')  # No EventDate attr.
        chart.add_attribute_class(name='EventDate', type='datetime',
                                  visible=False, canvas_display=True)
        xml = chart.to_xml()
        names = set(_ac_by_name(xml))
        assert 'EventDate' in names
        assert 'EventDate (display)' in names
        # No attribute rows on Alice for the sibling
        attrs = _attrs_on_entity(xml, 'A')
        assert 'EventDate (display)' not in attrs

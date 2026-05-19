"""Tests for ``extra_cfg.date_attribute_displays`` — the datetime → text
sibling synthesizer that works around ANB v9's failure to render datetime
attribute values on the canvas.

Covers:
- Happy paths: single-date, range (both bounds present), custom format /
  separator / name, sibling AC styling via ``attribute_class``.
- Missing-bound policies: ``skip`` (default), ``substitute`` with per-bound
  placeholders, ``truncate`` (render the present bound alone), ``error``
  (surface at validate() time per-item).
- Validation negatives: missing start, undeclared AC ref, non-datetime AC,
  source AC visible!=False, end==start, range without name, bad strftime,
  invalid missing policy, inner.name/.type set, name collisions
  (display↔AC and display↔display).
- Cross-path parity: dict / YAML / JSON parsers produce the same XML.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from anxwritter import ANXChart, DateAttributeDisplay, AttributeClass, Font
from anxwritter.errors import ErrorType


def _xml_for(chart: ANXChart) -> str:
    return chart.to_xml()


def _validation_types(chart: ANXChart):
    return {e['type'] for e in chart.validate()}


# ─────────────────────────────────────────────────────────────────────────────
# Happy paths
# ─────────────────────────────────────────────────────────────────────────────


class TestSingleDateMode:
    def test_default_format_and_suffix(self):
        chart = ANXChart()
        chart.add_attribute_class(name='event_date', type='datetime', visible=False)
        chart.add_date_attribute_display(start='event_date')
        chart.add_icon(id='A', type='Person',
                       attributes={'event_date': datetime(2024, 1, 15, 14, 30, 0)})
        xml = _xml_for(chart)
        assert 'event_date (display)' in xml
        assert '2024-01-15' in xml

    def test_custom_format(self):
        chart = ANXChart()
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(start='ed', format='%d/%m/%Y')
        chart.add_icon(id='A', type='Person',
                       attributes={'ed': datetime(2024, 3, 7)})
        assert '07/03/2024' in _xml_for(chart)

    def test_custom_suffix(self):
        chart = ANXChart()
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(start='ed', suffix=' shown')
        chart.add_icon(id='A', type='Person', attributes={'ed': datetime(2024, 1, 1)})
        assert 'ed shown' in _xml_for(chart)

    def test_explicit_name_overrides_suffix(self):
        chart = ANXChart()
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(start='ed', name='Event', suffix=' ignored')
        chart.add_icon(id='A', type='Person', attributes={'ed': datetime(2024, 1, 1)})
        xml = _xml_for(chart)
        assert 'Event' in xml
        assert 'ed ignored' not in xml

    def test_missing_value_silently_skipped(self):
        chart = ANXChart()
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(start='ed')
        chart.add_icon(id='A', type='Person')  # no attribute
        # Validates clean and builds; no sibling row painted for this item.
        chart.to_xml()  # no raise

    def test_sibling_styling_via_attribute_class(self):
        chart = ANXChart()
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(
            start='ed',
            attribute_class=AttributeClass(
                prefix='[',
                suffix=']',
                font=Font(italic=True),
            ),
        )
        chart.add_icon(id='A', type='Person', attributes={'ed': datetime(2024, 1, 1)})
        xml = _xml_for(chart)
        # The prefix/suffix attributes appear on the emitted AttributeClass row.
        assert 'Prefix' in xml
        assert 'Italic' in xml


class TestRangeMode:
    def _chart(self, **display_kwargs) -> ANXChart:
        chart = ANXChart()
        chart.add_attribute_class(name='sd', type='datetime', visible=False)
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(
            start='sd', end='ed', name='Period', **display_kwargs,
        )
        return chart

    def test_both_bounds_present_default_separator(self):
        chart = self._chart()
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1),
                                   'ed': datetime(2024, 12, 31)})
        xml = _xml_for(chart)
        assert 'Period' in xml
        assert '2024-01-01 - 2024-12-31' in xml

    def test_custom_separator(self):
        chart = self._chart(separator=' to ')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1),
                                   'ed': datetime(2024, 12, 31)})
        assert '2024-01-01 to 2024-12-31' in _xml_for(chart)

    def test_custom_format_applies_to_both_bounds(self):
        chart = self._chart(format='%d/%m/%Y', separator=' – ')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 5),
                                   'ed': datetime(2024, 1, 12)})
        assert '05/01/2024 – 12/01/2024' in _xml_for(chart)

    def test_works_on_links_too(self):
        chart = self._chart()
        chart.add_icon(id='A', type='Person')
        chart.add_icon(id='B', type='Person')
        chart.add_link(from_id='A', to_id='B', type='Surveils',
                       attributes={'sd': datetime(2024, 1, 1),
                                   'ed': datetime(2024, 6, 30)})
        assert '2024-01-01 - 2024-06-30' in _xml_for(chart)


# ─────────────────────────────────────────────────────────────────────────────
# Missing-bound policies
# ─────────────────────────────────────────────────────────────────────────────


class TestMissingPolicies:
    def _range_with_policy(self, policy, **extra):
        chart = ANXChart()
        chart.add_attribute_class(name='sd', type='datetime', visible=False)
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(
            start='sd', end='ed', name='Period', missing=policy, **extra,
        )
        return chart

    def test_skip_default_when_end_missing(self):
        chart = self._range_with_policy('skip')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1)})
        xml = _xml_for(chart)
        # The sibling AC is still declared, but no Period value is painted on A.
        assert 'Period' in xml  # AC declaration
        # No Period attribute value
        assert '2024-01-01' not in xml or 'AttributeValue' not in xml.split('Period', 1)[1][:500]

    def test_substitute_end_missing(self):
        chart = self._range_with_policy('substitute', end_placeholder='ongoing')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1)})
        assert '2024-01-01 - ongoing' in _xml_for(chart)

    def test_substitute_start_missing(self):
        chart = self._range_with_policy('substitute', start_placeholder='?')
        chart.add_icon(id='A', type='Person',
                       attributes={'ed': datetime(2024, 12, 31)})
        assert '? - 2024-12-31' in _xml_for(chart)

    def test_substitute_empty_placeholder(self):
        chart = self._range_with_policy('substitute')  # default ''
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1)})
        # Result is "2024-01-01 - " with trailing separator
        assert '2024-01-01 - ' in _xml_for(chart)

    def test_truncate_end_missing(self):
        chart = self._range_with_policy('truncate')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1)})
        xml = _xml_for(chart)
        # Truncate emits just the present bound, no separator
        # The literal "2024-01-01 -" should NOT appear (no trailing separator)
        period_section = xml.split('Period', 1)[1] if 'Period' in xml else ''
        assert '2024-01-01' in period_section
        # Substring after Period should not include " - "
        assert '2024-01-01 - ' not in period_section[:200]

    def test_truncate_start_missing(self):
        chart = self._range_with_policy('truncate')
        chart.add_icon(id='A', type='Person',
                       attributes={'ed': datetime(2024, 12, 31)})
        assert '2024-12-31' in _xml_for(chart)

    def test_both_missing_always_skipped(self):
        # Even with substitute, both-missing emits no sibling row
        chart = self._range_with_policy('substitute', end_placeholder='X',
                                        start_placeholder='Y')
        chart.add_icon(id='A', type='Person')
        xml = _xml_for(chart)
        # Sibling AC declared but no "Y - X" pair painted
        assert 'Y - X' not in xml

    def test_error_policy_surfaces_at_validate_time(self):
        chart = self._range_with_policy('error')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1)})  # no end
        errs = chart.validate()
        types = {e['type'] for e in errs}
        assert ErrorType.DATE_DISPLAY_INVALID.value in types
        # Error location points at the missing attribute on the item
        msgs = [e['message'] for e in errs if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any("entities[0]" in (e.get('location') or '') and 'no \'ed\'' in m
                   for e, m in zip(errs, msgs) if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value)


# ─────────────────────────────────────────────────────────────────────────────
# Validation negatives
# ─────────────────────────────────────────────────────────────────────────────


class TestValidationNegatives:
    def test_start_required(self):
        chart = ANXChart()
        chart.add_date_attribute_display()  # no start
        assert ErrorType.DATE_DISPLAY_INVALID.value in _validation_types(chart)

    def test_start_undeclared(self):
        chart = ANXChart()
        chart.add_date_attribute_display(start='nope')
        assert ErrorType.DATE_DISPLAY_INVALID.value in _validation_types(chart)

    def test_start_not_datetime(self):
        chart = ANXChart()
        chart.add_attribute_class(name='phone', type='text')
        chart.add_date_attribute_display(start='phone')
        errs = chart.validate()
        types = {e['type'] for e in errs}
        assert ErrorType.DATE_DISPLAY_INVALID.value in types

    def test_start_ac_visible_not_false(self):
        chart = ANXChart()
        # visible=True triggers both rules; visible=None (default) triggers
        # only the date-display rule. Test both.
        chart.add_attribute_class(name='d', type='datetime')  # visible None
        chart.add_date_attribute_display(start='d')
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any('visible=False' in m for m in msgs)

    def test_end_equals_start(self):
        chart = ANXChart()
        chart.add_attribute_class(name='same', type='datetime', visible=False)
        chart.add_date_attribute_display(start='same', end='same', name='X')
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any("cannot equal 'start'" in m for m in msgs)

    def test_range_without_name(self):
        chart = ANXChart()
        chart.add_attribute_class(name='s', type='datetime', visible=False)
        chart.add_attribute_class(name='e', type='datetime', visible=False)
        chart.add_date_attribute_display(start='s', end='e')  # no name
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any('range' in m and "'name' is required" in m for m in msgs)

    def test_invalid_strftime(self):
        # Empty string is one of the few formats that's universally invalid
        # across libc implementations (glibc is permissive with unknown
        # directives, so e.g. '%Q' may pass).
        chart = ANXChart()
        chart.add_attribute_class(name='d', type='datetime', visible=False)
        chart.add_date_attribute_display(start='d', format='')
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any('strftime' in m for m in msgs)

    def test_invalid_missing_policy(self):
        chart = ANXChart()
        chart.add_attribute_class(name='d', type='datetime', visible=False)
        chart.add_date_attribute_display(start='d', missing='bogus')
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any('missing' in m and 'invalid' in m.lower() for m in msgs)

    def test_inner_attribute_class_name_forbidden(self):
        chart = ANXChart()
        chart.add_attribute_class(name='d', type='datetime', visible=False)
        chart.add_date_attribute_display(
            start='d',
            attribute_class=AttributeClass(name='nope'),
        )
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any('attribute_class.name' in m for m in msgs)

    def test_inner_attribute_class_type_forbidden(self):
        chart = ANXChart()
        chart.add_attribute_class(name='d', type='datetime', visible=False)
        chart.add_date_attribute_display(
            start='d',
            attribute_class=AttributeClass(type='number'),
        )
        msgs = [e['message'] for e in chart.validate()
                if e['type'] == ErrorType.DATE_DISPLAY_INVALID.value]
        assert any('attribute_class.type' in m for m in msgs)

    def test_sibling_name_collides_with_explicit_ac(self):
        chart = ANXChart()
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_attribute_class(name='ed (display)', type='text')
        chart.add_date_attribute_display(start='ed')
        types = _validation_types(chart)
        assert ErrorType.DATE_DISPLAY_NAME_COLLISION.value in types

    def test_two_displays_collide(self):
        chart = ANXChart()
        chart.add_attribute_class(name='d1', type='datetime', visible=False)
        chart.add_attribute_class(name='d2', type='datetime', visible=False)
        chart.add_date_attribute_display(start='d1', name='Shared')
        chart.add_date_attribute_display(start='d2', name='Shared')
        types = _validation_types(chart)
        assert ErrorType.DATE_DISPLAY_NAME_COLLISION.value in types

    def test_datetime_ac_forbids_visible_true(self):
        chart = ANXChart()
        chart.add_attribute_class(name='d', type='datetime', visible=True)
        types = _validation_types(chart)
        assert ErrorType.DATETIME_AC_FORBIDS_VISIBLE.value in types


# ─────────────────────────────────────────────────────────────────────────────
# Cross-path parity (dict / yaml / json)
# ─────────────────────────────────────────────────────────────────────────────


_SPEC = {
    'entities': {
        'icons': [
            {'id': 'A', 'type': 'Person',
             'attributes': {'sd': datetime(2024, 1, 1),
                            'ed': datetime(2024, 12, 31)}},
        ],
    },
    'attribute_classes': [
        {'name': 'sd', 'type': 'datetime', 'visible': False},
        {'name': 'ed', 'type': 'datetime', 'visible': False},
    ],
    'settings': {
        'extra_cfg': {
            'date_attribute_displays': [
                {'start': 'sd', 'end': 'ed', 'name': 'Period',
                 'separator': ' to ', 'format': '%Y-%m-%d'},
            ],
        },
    },
}


class TestCrossPathParity:
    def test_python_api_emits_period(self):
        chart = ANXChart()
        chart.add_attribute_class(name='sd', type='datetime', visible=False)
        chart.add_attribute_class(name='ed', type='datetime', visible=False)
        chart.add_date_attribute_display(start='sd', end='ed', name='Period',
                                          separator=' to ', format='%Y-%m-%d')
        chart.add_icon(id='A', type='Person',
                       attributes={'sd': datetime(2024, 1, 1),
                                   'ed': datetime(2024, 12, 31)})
        assert '2024-01-01 to 2024-12-31' in _xml_for(chart)

    def test_from_dict_path(self):
        chart = ANXChart.from_dict(_SPEC)
        assert '2024-01-01 to 2024-12-31' in _xml_for(chart)

    def test_yaml_path(self):
        yaml = """
entities:
  icons:
    - id: A
      type: Person
      attributes:
        sd: 2024-01-01
        ed: 2024-12-31
attribute_classes:
  - name: sd
    type: datetime
    visible: false
  - name: ed
    type: datetime
    visible: false
settings:
  extra_cfg:
    date_attribute_displays:
      - start: sd
        end: ed
        name: Period
        separator: ' to '
        format: '%Y-%m-%d'
"""
        chart = ANXChart.from_yaml(yaml)
        assert '2024-01-01 to 2024-12-31' in _xml_for(chart)

    def test_json_path_uses_string_datetimes_with_declared_ac(self):
        # JSON has no datetime literal; relies on AC-declaration coercion.
        json_str = """
{
  "entities": {"icons": [
    {"id": "A", "type": "Person",
     "attributes": {"sd": "2024-01-01T00:00:00", "ed": "2024-12-31T00:00:00"}}
  ]},
  "attribute_classes": [
    {"name": "sd", "type": "datetime", "visible": false},
    {"name": "ed", "type": "datetime", "visible": false}
  ],
  "settings": {"extra_cfg": {"date_attribute_displays": [
    {"start": "sd", "end": "ed", "name": "Period",
     "separator": " to ", "format": "%Y-%m-%d"}
  ]}}
}
"""
        chart = ANXChart.from_json(json_str)
        assert '2024-01-01 to 2024-12-31' in _xml_for(chart)


# ─────────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_spec_byte_identical(self):
        def build():
            chart = ANXChart()
            chart.add_attribute_class(name='ed', type='datetime', visible=False)
            chart.add_date_attribute_display(start='ed', format='%Y-%m-%d')
            chart.add_icon(id='A', type='Person',
                           attributes={'ed': datetime(2024, 5, 19)})
            return chart.to_xml()

        assert build() == build()

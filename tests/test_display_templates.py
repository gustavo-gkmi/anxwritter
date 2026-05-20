"""Tests for ``extra_cfg.display_templates`` — multi-attribute synthesizer
that renders source attribute values through a Python ``str.format_map``
template and routes the output to either a synthesized text-sibling AC
(``target='attribute'``) or the entity/link label (``target='label'``).

Covers:
- Happy paths: both targets, named substitution, alias for non-identifier
  AC names, datetime source via ``{d:%d/%m/%Y}``, decimal/thousand
  separator swap, per-source missing policies, override_existing.
- Validation negatives: missing template/sources, undeclared AC ref,
  visible!=False source AC for target=attribute, invalid target/missing
  enum, alias collisions, name collisions across explicit ACs, other
  display_templates entries, and date_attribute_displays siblings.
- Cross-path parity: dict / YAML / JSON parsers produce the same XML.
"""
from __future__ import annotations

import json

import pytest
import yaml

from anxwritter import (
    ANXChart, DisplayTemplate, DisplaySource, DateAttributeDisplay,
    AttributeClass, Font,
)
from anxwritter.errors import ErrorType


def _xml(chart: ANXChart) -> str:
    return chart.to_xml()


def _validation_types(chart: ANXChart):
    return {e['type'] for e in chart.validate()}


# ─────────────────────────────────────────────────────────────────────────────
# Happy paths — target='attribute'
# ─────────────────────────────────────────────────────────────────────────────


class TestTargetAttribute:
    def test_basic_two_source_template(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'tx', 'type': 'number', 'visible': False},
                {'name': 'amount', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'Activity',
                'template': '{tx}x · R$ {amount:,.2f}',
                'sources': [{'attribute': 'tx'}, {'attribute': 'amount'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person'},
                {'id': 'B', 'type': 'Person'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'Transfer',
                'attributes': {'tx': 5, 'amount': 12345.67},
            }],
        })
        assert chart.validate() == []
        xml = _xml(chart)
        assert 'Name="Activity"' in xml
        assert 'Value="5x · R$ 12,345.67"' in xml

    def test_default_attribute_name_is_display(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [{'name': 'tx', 'type': 'number', 'visible': False}],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{tx} transfers',
                'sources': [{'attribute': 'tx'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person'}, {'id': 'B', 'type': 'Person'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'T',
                'attributes': {'tx': 3},
            }],
        })
        assert chart.validate() == []
        xml = _xml(chart)
        assert 'Name="display"' in xml
        assert 'Value="3 transfers"' in xml

    def test_alias_for_non_identifier_attribute_name(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'quantia em real', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'Money',
                'template': 'R$ {amount:,.2f}',
                'sources': [{
                    'attribute': 'quantia em real',
                    'alias': 'amount',
                }],
            }]}},
            'entities': {'icons': [{
                'id': 'A', 'type': 'Person',
                'attributes': {'quantia em real': 9999.99},
            }]},
        })
        assert chart.validate() == []
        assert 'Value="R$ 9,999.99"' in _xml(chart)

    def test_datetime_source_with_strftime_spec(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'when', 'type': 'datetime', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'When',
                'template': 'em {when:%d/%m/%Y}',
                'sources': [{'attribute': 'when'}],
            }]}},
            'entities': {'icons': [{
                'id': 'A', 'type': 'Person',
                'attributes': {'when': '2024-03-15'},
            }]},
        })
        assert chart.validate() == []
        assert 'Value="em 15/03/2024"' in _xml(chart)

    def test_br_separators(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'amount', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'Money',
                'template': 'R$ {amount:,.2f}',
                'decimal_separator': ',',
                'thousand_separator': '.',
                'sources': [{'attribute': 'amount'}],
            }]}},
            'entities': {'icons': [{
                'id': 'A', 'type': 'Person',
                'attributes': {'amount': 100000.50},
            }]},
        })
        assert chart.validate() == []
        assert 'Value="R$ 100.000,50"' in _xml(chart)

    def test_static_text_separators_not_swapped(self):
        """Literal commas/dots in the template stay put — only formatted
        numeric values get the separator swap."""
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'a', 'type': 'number', 'visible': False},
                {'name': 'b', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'Pair',
                'template': '{a}, {b:,.2f}',  # literal comma after {a}
                'decimal_separator': ',',
                'thousand_separator': '.',
                'sources': [{'attribute': 'a'}, {'attribute': 'b'}],
            }]}},
            'entities': {'icons': [{
                'id': 'A', 'type': 'Person',
                'attributes': {'a': 5, 'b': 1234.56},
            }]},
        })
        assert chart.validate() == []
        # The first comma (literal) survives; the formatted value applies the
        # swap to its thousands sep but the static comma is not touched.
        assert 'Value="5, 1.234,56"' in _xml(chart)

    def test_attribute_class_styling_template(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'tx', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'Activity',
                'template': '{tx}x',
                'sources': [{'attribute': 'tx'}],
                'attribute_class': {
                    'prefix': '⚡ ',
                    'show_symbol': False,
                },
            }]}},
            'entities': {'icons': [{
                'id': 'A', 'type': 'Person', 'attributes': {'tx': 7},
            }]},
        })
        assert chart.validate() == []
        xml = _xml(chart)
        assert 'Prefix="⚡ "' in xml
        assert 'ShowSymbol="false"' in xml


# ─────────────────────────────────────────────────────────────────────────────
# Happy paths — target='label'
# ─────────────────────────────────────────────────────────────────────────────


class TestTargetLabel:
    def test_fills_empty_label(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [{'name': 'tx', 'type': 'number'}],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'label',
                'template': '{tx}x',
                'sources': [{'attribute': 'tx'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person'}, {'id': 'B', 'type': 'Person'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'T',
                'attributes': {'tx': 9},
            }],
        })
        assert chart.validate() == []
        xml = _xml(chart)
        # The link ChartItem (the one with no manual label) picks up "9x"
        assert 'Label="9x"' in xml

    def test_preserves_manual_label_by_default(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [{'name': 'tx', 'type': 'number'}],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'label',
                'template': '{tx}x',
                'sources': [{'attribute': 'tx'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person'}, {'id': 'B', 'type': 'Person'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'T',
                'label': 'manual annotation',
                'attributes': {'tx': 9},
            }],
        })
        assert chart.validate() == []
        xml = _xml(chart)
        assert 'Label="manual annotation"' in xml
        assert 'Label="9x"' not in xml

    def test_override_existing_stomps_manual_label(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [{'name': 'tx', 'type': 'number'}],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'label',
                'override_existing': True,
                'template': '{tx}x',
                'sources': [{'attribute': 'tx'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person'}, {'id': 'B', 'type': 'Person'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'T',
                'label': 'manual',
                'attributes': {'tx': 9},
            }],
        })
        assert chart.validate() == []
        xml = _xml(chart)
        assert 'Label="9x"' in xml
        assert 'Label="manual"' not in xml

    def test_source_ac_visibility_not_constrained(self):
        """target='label' allows source ACs to remain visible — structured
        data shows in the attribute stack AND the formatted summary shows
        on the label."""
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'tx', 'type': 'number'},  # visible=True (default)
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'label',
                'template': '{tx}x',
                'sources': [{'attribute': 'tx'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person'}, {'id': 'B', 'type': 'Person'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'T',
                'attributes': {'tx': 9},
            }],
        })
        assert chart.validate() == []


# ─────────────────────────────────────────────────────────────────────────────
# Missing-value handling per source
# ─────────────────────────────────────────────────────────────────────────────


class TestMissingPolicies:
    def test_skip_default_drops_item_with_missing_source(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'tx', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'X',
                'template': '{tx}',
                'sources': [{'attribute': 'tx'}],  # no missing → default skip
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person', 'attributes': {'tx': 1}},
                {'id': 'B', 'type': 'Person'},  # no tx attribute
            ]},
        })
        assert chart.validate() == []
        xml = _xml(chart)
        # A gets the X attribute synthesized
        assert 'Value="1"' in xml
        # Make sure B didn't get a phantom X synthesized — exactly one
        # <Attribute ... Value=...> tag referencing AC X should appear.
        attribute_refs = xml.count('<Attribute AttributeClass="X"')
        assert attribute_refs == 1

    def test_substitute_uses_placeholder(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'tx', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'X',
                'template': '{tx}',
                'sources': [{
                    'attribute': 'tx',
                    'missing': 'substitute',
                    'placeholder': 'N/A',
                }],
            }]}},
            'entities': {'icons': [
                {'id': 'B', 'type': 'Person'},  # no tx
            ]},
        })
        assert chart.validate() == []
        assert 'Value="N/A"' in _xml(chart)

    def test_error_surfaces_per_item_at_validate(self):
        chart = ANXChart.from_dict({
            'attribute_classes': [
                {'name': 'tx', 'type': 'number', 'visible': False},
            ],
            'settings': {'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'X',
                'template': '{tx}',
                'sources': [{'attribute': 'tx', 'missing': 'error'}],
            }]}},
            'entities': {'icons': [
                {'id': 'A', 'type': 'Person', 'attributes': {'tx': 1}},
                {'id': 'B', 'type': 'Person'},
            ]},
        })
        errs = chart.validate()
        assert any(
            e['type'] == ErrorType.DISPLAY_TEMPLATE_INVALID.value
            and 'B' in e['message'] or 'entities[1]' in e['location']
            for e in errs
        )


# ─────────────────────────────────────────────────────────────────────────────
# Validation negatives
# ─────────────────────────────────────────────────────────────────────────────


class TestValidationNegatives:
    def _types(self, **kwargs):
        chart = ANXChart.from_dict(kwargs)
        return _validation_types(chart)

    def test_missing_template(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number'}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'sources': [{'attribute': 'tx'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_empty_sources(self):
        types = self._types(
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': 'hi',
                'sources': [],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_invalid_target(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number'}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'banana',
                'template': '{tx}',
                'sources': [{'attribute': 'tx'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_undeclared_source_ac(self):
        types = self._types(
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{ghost}',
                'sources': [{'attribute': 'ghost'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_source_ac_visible_required_for_attribute_target(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number'}],  # visible defaults True
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{tx}',
                'sources': [{'attribute': 'tx'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_alias_required_for_non_identifier(self):
        types = self._types(
            attribute_classes=[{'name': 'has spaces', 'type': 'number', 'visible': False}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{x}',
                'sources': [{'attribute': 'has spaces'}],  # no alias
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_alias_collision_within_entry(self):
        types = self._types(
            attribute_classes=[
                {'name': 'a', 'type': 'number', 'visible': False},
                {'name': 'b', 'type': 'number', 'visible': False},
            ],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{same}',
                'sources': [
                    {'attribute': 'a', 'alias': 'same'},
                    {'attribute': 'b', 'alias': 'same'},
                ],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_invalid_missing_enum(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number', 'visible': False}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{tx}',
                'sources': [{'attribute': 'tx', 'missing': 'banana'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_attribute_class_name_must_be_none(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number', 'visible': False}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{tx}',
                'sources': [{'attribute': 'tx'}],
                'attribute_class': {'name': 'Forbidden'},
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_attribute_class_type_must_be_none(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number', 'visible': False}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{tx}',
                'sources': [{'attribute': 'tx'}],
                'attribute_class': {'type': 'text'},
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_template_syntax_error(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number', 'visible': False}],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'template': '{tx',  # unclosed brace
                'sources': [{'attribute': 'tx'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_INVALID.value in types

    def test_collision_with_explicit_ac(self):
        types = self._types(
            attribute_classes=[
                {'name': 'tx', 'type': 'number', 'visible': False},
                {'name': 'Activity', 'type': 'text'},  # explicit AC
            ],
            settings={'extra_cfg': {'display_templates': [{
                'target': 'attribute',
                'attribute_name': 'Activity',  # collision
                'template': '{tx}',
                'sources': [{'attribute': 'tx'}],
            }]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_NAME_COLLISION.value in types

    def test_collision_with_other_display_template(self):
        types = self._types(
            attribute_classes=[{'name': 'tx', 'type': 'number', 'visible': False}],
            settings={'extra_cfg': {'display_templates': [
                {
                    'target': 'attribute',
                    'attribute_name': 'Dupe',
                    'template': '{tx}',
                    'sources': [{'attribute': 'tx'}],
                },
                {
                    'target': 'attribute',
                    'attribute_name': 'Dupe',  # collision
                    'template': '{tx}',
                    'sources': [{'attribute': 'tx'}],
                },
            ]}},
        )
        assert ErrorType.DISPLAY_TEMPLATE_NAME_COLLISION.value in types

    def test_collision_with_date_attribute_displays(self):
        types = self._types(
            attribute_classes=[
                {'name': 'tx', 'type': 'number', 'visible': False},
                {'name': 'when', 'type': 'datetime', 'visible': False},
            ],
            settings={'extra_cfg': {
                'date_attribute_displays': [{
                    'start': 'when',
                    'name': 'Shared',
                }],
                'display_templates': [{
                    'target': 'attribute',
                    'attribute_name': 'Shared',  # collision with date sibling
                    'template': '{tx}',
                    'sources': [{'attribute': 'tx'}],
                }],
            }},
        )
        assert ErrorType.DISPLAY_TEMPLATE_NAME_COLLISION.value in types


# ─────────────────────────────────────────────────────────────────────────────
# Cross-path parity: dict / YAML / JSON / Python API all agree
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossPathParity:
    """The same display_templates config built four different ways should
    produce identical XML output."""

    CANONICAL = {
        'attribute_classes': [
            {'name': 'tx', 'type': 'number', 'visible': False},
            {'name': 'amount', 'type': 'number', 'visible': False},
        ],
        'settings': {'extra_cfg': {'display_templates': [{
            'target': 'attribute',
            'attribute_name': 'Activity',
            'template': '{tx}x R$ {amount:,.2f}',
            'decimal_separator': ',',
            'thousand_separator': '.',
            'sources': [
                {'attribute': 'tx'},
                {'attribute': 'amount'},
            ],
        }]}},
        'entities': {'icons': [
            {'id': 'A', 'type': 'Person'}, {'id': 'B', 'type': 'Person'},
        ]},
        'links': [{
            'from_id': 'A', 'to_id': 'B', 'type': 'T',
            'attributes': {'tx': 5, 'amount': 1234.56},
        }],
    }

    def test_from_dict(self):
        chart = ANXChart.from_dict(self.CANONICAL)
        assert chart.validate() == []
        assert 'Value="5x R$ 1.234,56"' in _xml(chart)

    def test_from_yaml(self):
        chart = ANXChart.from_yaml(yaml.safe_dump(self.CANONICAL))
        assert chart.validate() == []
        assert 'Value="5x R$ 1.234,56"' in _xml(chart)

    def test_from_json(self):
        chart = ANXChart.from_json(json.dumps(self.CANONICAL))
        assert chart.validate() == []
        assert 'Value="5x R$ 1.234,56"' in _xml(chart)

    def test_python_api_equivalent(self):
        chart = ANXChart()
        chart.add_attribute_class(AttributeClass(name='tx', type='number', visible=False))
        chart.add_attribute_class(AttributeClass(name='amount', type='number', visible=False))
        chart.add_display_template(DisplayTemplate(
            target='attribute',
            attribute_name='Activity',
            template='{tx}x R$ {amount:,.2f}',
            decimal_separator=',',
            thousand_separator='.',
            sources=[
                DisplaySource(attribute='tx'),
                DisplaySource(attribute='amount'),
            ],
        ))
        chart.add_icon(id='A', type='Person')
        chart.add_icon(id='B', type='Person')
        chart.add_link(from_id='A', to_id='B', type='T',
                       attributes={'tx': 5, 'amount': 1234.56})
        assert chart.validate() == []
        assert 'Value="5x R$ 1.234,56"' in _xml(chart)

    def test_generic_add_dispatches(self):
        chart = ANXChart()
        chart.add_attribute_class(AttributeClass(name='tx', type='number', visible=False))
        chart.add(DisplayTemplate(
            target='attribute',
            attribute_name='X',
            template='{tx}',
            sources=[DisplaySource(attribute='tx')],
        ))
        chart.add_icon(id='A', type='Person', attributes={'tx': 1})
        assert chart.validate() == []


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency — calling to_xml() twice should not mutate inputs
# ─────────────────────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_double_build_same_output(self):
        chart = ANXChart()
        chart.add_attribute_class(AttributeClass(name='tx', type='number', visible=False))
        chart.add_display_template(DisplayTemplate(
            target='attribute',
            attribute_name='X',
            template='{tx}',
            sources=[DisplaySource(attribute='tx')],
        ))
        chart.add_icon(id='A', type='Person', attributes={'tx': 1})
        chart.add_icon(id='B', type='Person', attributes={'tx': 2})
        xml1 = chart.to_xml()
        xml2 = chart.to_xml()
        assert xml1 == xml2

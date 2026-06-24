"""Tests for the icon_map feature (extra_cfg.icon_map).

Covers:
- Attribute-value → icon mapping (matched / unrecognised → default / absent →
  default_when_absent / skip)
- id → icon mapping
- Type filter on attribute rules
- Precedence ladder: explicit > id > typed-attr > untyped-attr; last-wins
  within a tier
- strict_match vs default case/accent-insensitive matching
- Integration with registered custom icons (bare name → emitted) and entity
  types (name → icon_file)
- Validation errors (icon_map_invalid)
- to_config_dict round-trip + add_icon_map_rule builder
- No mutation of user objects / build idempotency
"""

from __future__ import annotations

import json
import re

import pytest

from anxwritter import ANXChart, Icon, IconMapCfg, IconRule
from anxwritter.transforms import apply_icon_map
from anxwritter.errors import ErrorType


# ── Helpers ─────────────────────────────────────────────────────────────────


def _icon_of(xml: str, label: str) -> str | None:
    """Return the TypeIconName emitted for the entity with the given Label,
    or None when no per-entity icon override was emitted."""
    m = re.search(rf'Label="{re.escape(label)}".*?(?=<ChartItem|$)', xml, re.S)
    if not m:
        return None
    tin = re.search(r'TypeIconName="([^"]+)"', m.group(0))
    return tin.group(1) if tin else None


def _build(rules, entities, entity_types=None):
    chart = ANXChart(settings={'extra_cfg': {'icon_map': {'rules': rules}}})
    for et in (entity_types or []):
        chart.add_entity_type(**et)
    for e in entities:
        chart.add(e)
    return chart


# ── Attribute matching ───────────────────────────────────────────────────────


def test_attribute_value_matched():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'bank_code',
          'mapping': {'400': 'itau', '237': 'bradesco'}}],
        [Icon(id='A', type='Acc', attributes={'bank_code': 400}),
         Icon(id='B', type='Acc', attributes={'bank_code': 237})],
    )
    xml = chart.to_xml()
    assert _icon_of(xml, 'A') == 'itau'
    assert _icon_of(xml, 'B') == 'bradesco'


def test_attribute_unrecognised_uses_default():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k',
          'mapping': {'x': 'hit'}, 'default': 'fallback'}],
        [Icon(id='A', type='T', attributes={'k': 'unknown'})],
    )
    assert _icon_of(chart.to_xml(), 'A') == 'fallback'


def test_attribute_unrecognised_no_default_skips():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'x': 'hit'}}],
        [Icon(id='A', type='T', attributes={'k': 'unknown'})],
    )
    assert _icon_of(chart.to_xml(), 'A') is None


def test_attribute_absent_uses_default_when_absent():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'x': 'hit'},
          'default': 'fallback', 'default_when_absent': 'no_attr'}],
        [Icon(id='A', type='T', attributes={'other': 1})],
    )
    # absent → default_when_absent, NOT default
    assert _icon_of(chart.to_xml(), 'A') == 'no_attr'


def test_attribute_absent_no_default_when_absent_skips():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'x': 'hit'},
          'default': 'fallback'}],
        [Icon(id='A', type='T', attributes={'other': 1})],
    )
    assert _icon_of(chart.to_xml(), 'A') is None


def test_type_filter_restricts_rule():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'type': 'Acc',
          'mapping': {'v': 'hit'}}],
        [Icon(id='A', type='Acc', attributes={'k': 'v'}),
         Icon(id='B', type='Person', attributes={'k': 'v'})],
    )
    xml = chart.to_xml()
    assert _icon_of(xml, 'A') == 'hit'
    assert _icon_of(xml, 'B') is None


# ── id matching ──────────────────────────────────────────────────────────────


def test_id_rule():
    chart = _build(
        [{'match': 'id', 'mapping': {'A': 'special', 'C': 'other'}}],
        [Icon(id='A', type='T'), Icon(id='B', type='T')],
    )
    xml = chart.to_xml()
    assert _icon_of(xml, 'A') == 'special'
    assert _icon_of(xml, 'B') is None


# ── Precedence ───────────────────────────────────────────────────────────────


def test_explicit_icon_beats_all_rules():
    chart = _build(
        [{'match': 'id', 'mapping': {'A': 'id_icon'}},
         {'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'attr_icon'}}],
        [Icon(id='A', type='T', icon='explicit', attributes={'k': 'v'})],
    )
    assert _icon_of(chart.to_xml(), 'A') == 'explicit'


def test_id_beats_attribute():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'attr_icon'}},
         {'match': 'id', 'mapping': {'A': 'id_icon'}}],
        [Icon(id='A', type='T', attributes={'k': 'v'})],
    )
    assert _icon_of(chart.to_xml(), 'A') == 'id_icon'


def test_typed_attribute_beats_untyped():
    # untyped declared LAST — but typed (higher tier) must still win.
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'type': 'T',
          'mapping': {'v': 'typed'}},
         {'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'untyped'}}],
        [Icon(id='A', type='T', attributes={'k': 'v'})],
    )
    assert _icon_of(chart.to_xml(), 'A') == 'typed'


def test_last_wins_within_same_tier():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'first'}},
         {'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'second'}}],
        [Icon(id='A', type='T', attributes={'k': 'v'})],
    )
    assert _icon_of(chart.to_xml(), 'A') == 'second'


def test_lower_tier_declared_later_does_not_override():
    # id rule (tier 3) declared first, untyped attr (tier 1) declared later.
    chart = _build(
        [{'match': 'id', 'mapping': {'A': 'id_icon'}},
         {'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'attr_icon'}}],
        [Icon(id='A', type='T', attributes={'k': 'v'})],
    )
    assert _icon_of(chart.to_xml(), 'A') == 'id_icon'


# ── Matching normalisation ───────────────────────────────────────────────────


def test_default_matching_is_case_and_accent_insensitive():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'city', 'mapping': {'São Paulo': 'sp'}}],
        [Icon(id='A', type='T', attributes={'city': 'sao paulo'}),
         Icon(id='B', type='T', attributes={'city': 'SÃO PAULO'})],
    )
    xml = chart.to_xml()
    assert _icon_of(xml, 'A') == 'sp'
    assert _icon_of(xml, 'B') == 'sp'


def test_strict_match_requires_exact():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'Valor': 'hit'},
          'strict_match': True}],
        [Icon(id='A', type='T', attributes={'k': 'valor'}),
         Icon(id='B', type='T', attributes={'k': 'Valor'})],
    )
    xml = chart.to_xml()
    assert _icon_of(xml, 'A') is None
    assert _icon_of(xml, 'B') == 'hit'


# ── Integration: entity types and custom icons ───────────────────────────────


def test_mapped_value_resolves_entity_type_name_to_icon_file():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'Pessoa'}}],
        [Icon(id='A', type='T', attributes={'k': 'v'})],
        entity_types=[{'name': 'Pessoa', 'icon_file': 'person'}],
    )
    # bare type name → its icon_file
    assert _icon_of(chart.to_xml(), 'A') == 'person'


def _make_bmp(w=8, h=8, bpp=24):
    import struct
    row = (w * (bpp // 8) + 3) & ~3
    pixels = b'\x00' * (row * h)
    info = struct.pack('<IiiHHIIiiII', 40, w, h, 1, bpp, 0, len(pixels), 2835, 2835, 0, 0)
    return b'BM' + struct.pack('<IHHI', 54 + len(pixels), 0, 0, 54) + info + pixels


def test_mapped_value_resolves_registered_custom_icon():
    chart = ANXChart(settings={'extra_cfg': {'icon_map': {'rules': [
        {'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'myicon'}},
    ]}}})
    # a ready BMP embeds with no Pillow
    chart.add_custom_entity_icon('myicon', _make_bmp())
    chart.add_icon(id='A', type='T', attributes={'k': 'v'})
    xml = chart.to_xml()
    # bare name resolves to the emitted (prefixed) custom icon name
    assert _icon_of(xml, 'A') == 'anxW_myicon'


# ── Non-icon representations are skipped ──────────────────────────────────────


def test_non_icon_entities_unaffected():
    from anxwritter import Box
    overrides = apply_icon_map(
        [Box(id='A', type='T', attributes={'k': 'v'})],
        IconMapCfg(rules=[IconRule(match='attribute', attribute_name='k',
                                   mapping={'v': 'hit'})]),
    )
    # Box has no `icon` field — excluded from icon_map
    assert overrides == {}


# ── Validation ───────────────────────────────────────────────────────────────


def test_validation_bad_match():
    chart = _build([{'match': 'nope', 'mapping': {'a': 'b'}}], [Icon(id='A', type='T')])
    types = {e['type'] for e in chart.validate()}
    assert ErrorType.ICON_MAP_INVALID.value in types


def test_validation_empty_mapping():
    chart = _build([{'match': 'attribute', 'attribute_name': 'k', 'mapping': {}}],
                   [Icon(id='A', type='T')])
    errs = [e for e in chart.validate() if e['type'] == ErrorType.ICON_MAP_INVALID.value]
    assert any('mapping' in e['location'] for e in errs)


def test_validation_id_rule_rejects_default_and_type():
    chart = _build(
        [{'match': 'id', 'mapping': {'a': 'b'}, 'default': 'x', 'type': 'T'}],
        [Icon(id='A', type='T')],
    )
    errs = [e for e in chart.validate() if e['type'] == ErrorType.ICON_MAP_INVALID.value]
    locs = {e['location'].rsplit('.', 1)[-1] for e in errs}
    assert 'default' in locs
    assert 'type' in locs


def test_validation_missing_attribute_name():
    chart = _build([{'match': 'attribute', 'mapping': {'a': 'b'}}], [Icon(id='A', type='T')])
    errs = [e for e in chart.validate() if e['type'] == ErrorType.ICON_MAP_INVALID.value]
    assert any('attribute_name' in e['location'] for e in errs)


def test_validation_unknown_type_filter():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'type': 'Ghost', 'mapping': {'a': 'b'}}],
        [Icon(id='A', type='Known')],
    )
    errs = [e for e in chart.validate() if e['type'] == ErrorType.ICON_MAP_INVALID.value]
    assert any('type' in e['location'].rsplit('.', 1)[-1] for e in errs)


def test_validation_observed_type_passes():
    # type filter referencing an observed (not registered) type is fine.
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'type': 'Acc', 'mapping': {'a': 'b'}}],
        [Icon(id='A', type='Acc', attributes={'k': 'a'})],
    )
    assert chart.validate() == []


# ── Round-trip + builder ─────────────────────────────────────────────────────


def test_to_config_dict_round_trip():
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'i1'}},
         {'match': 'id', 'mapping': {'A': 'i2'}}],
        [Icon(id='A', type='T', attributes={'k': 'v'})],
    )
    cfg = chart.to_config_dict()
    assert 'icon_map' in cfg['settings']['extra_cfg']
    chart2 = ANXChart.from_config(json.dumps(cfg))
    rules = chart2.settings.extra_cfg.icon_map.rules
    assert len(rules) == 2
    assert isinstance(rules[0], IconRule)


def test_add_icon_map_rule_builder():
    chart = ANXChart()
    chart.add_icon_map_rule(match='attribute', attribute_name='k', mapping={'a': 'b'})
    chart.add_icon_map_rule(IconRule(match='id', mapping={'z': 'q'}))
    rules = chart.settings.extra_cfg.icon_map.rules
    assert [r.match for r in rules] == ['attribute', 'id']


# ── Purity / idempotency ─────────────────────────────────────────────────────


def test_does_not_mutate_user_entities_and_is_idempotent():
    e = Icon(id='A', type='T', attributes={'k': 'v'})
    chart = _build(
        [{'match': 'attribute', 'attribute_name': 'k', 'mapping': {'v': 'hit'}}],
        [e],
    )
    x1 = chart.to_xml()
    x2 = chart.to_xml()
    assert e.icon is None       # user object untouched
    assert x1 == x2             # idempotent
    assert _icon_of(x1, 'A') == 'hit'

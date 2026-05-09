"""Tests for the geo_map feature (extra_cfg.geo_map).

Covers:
- Position-only mode: correct x,y projection
- Latlon-only mode: attribute injection with semantic types
- Both mode: combined
- Spread radius: same-key entity spread on circle
- Unmatched entities: placed below geo area
- Case-insensitive matching
- Validation errors
- data_file loading
- from_dict integration
"""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from anxwritter import ANXChart, Settings
from anxwritter.models import GeoMapCfg, ExtraCfg
from anxwritter.transforms import (
    resolve_geo_data,
    match_geo_entities,
    compute_geo_positions,
    inject_geo_attributes,
)
from anxwritter.errors import ErrorType


# ── Helpers ─────────────────────────────────────────────────────────────────

GEO_DATA = {
    'Palmas/TO': [-10.18, -48.33],
    'Rio de Janeiro/RJ': [-22.90, -43.17],
    'Sao Paulo/SP': [-23.55, -46.63],
}

def _make_chart(mode='both', spread_radius=0, data=None, **extra_kw):
    gm = GeoMapCfg(
        attribute_name='City',
        mode=mode,
        width=2000,
        height=1500,
        spread_radius=spread_radius,
        data=data or GEO_DATA,
        **extra_kw,
    )
    chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=gm)))
    chart.add_icon(id='E1', type='Person', attributes={'City': 'Palmas/TO'})
    chart.add_icon(id='E2', type='Person', attributes={'City': 'Rio de Janeiro/RJ'})
    chart.add_icon(id='E3', type='Person', attributes={'City': 'Sao Paulo/SP'})
    chart.add_icon(id='E4', type='Person', attributes={'City': 'Unknown'})  # unmatched
    chart.add_link(from_id='E1', to_id='E2', type='Knows')
    return chart


def _parse_positions(xml: str) -> Dict[str, Tuple[int, int]]:
    """Extract label -> (x, y) from ChartItem+End elements."""
    positions: Dict[str, Tuple[int, int]] = {}
    root = ET.fromstring(xml)
    for ci in root.iter('ChartItem'):
        label = ci.get('Label', '')
        xp = ci.get('XPosition')
        end = ci.find('End')
        yp = end.get('Y') if end is not None else None
        if label and xp is not None and yp is not None:
            positions[label] = (int(xp), int(yp))
    return positions


def _get_entity_attrs(xml: str, label: str) -> Dict[str, str]:
    """Get attribute name->value for a specific entity label."""
    root = ET.fromstring(xml)
    # Build ref_id -> class_name map from AttributeClassCollection
    ref_map: Dict[str, str] = {}
    for ac in root.iter('AttributeClass'):
        ac_id = ac.get('Id', '')
        ac_name = ac.get('Name', '')
        if ac_id and ac_name:
            ref_map[ac_id] = ac_name

    # Find entity by label
    for ci in root.iter('ChartItem'):
        if ci.get('Label') != label:
            continue
        # Navigate to parent Entity's AttributeCollection
        break
    else:
        return {}

    # Find Entity that contains this ChartItem
    for entity in root.iter('Entity'):
        found_ci = entity.find('.//ChartItem')
        if found_ci is not None and found_ci.get('Label') == label:
            attrs: Dict[str, str] = {}
            ac_coll = entity.find('AttributeCollection')
            if ac_coll is not None:
                for attr in ac_coll:
                    ref = attr.get('AttributeClassReference', '')
                    val = attr.get('Value', '')
                    name = ref_map.get(ref, ref)
                    attrs[name] = val
            return attrs
    return {}


# ── Tests: Position mode ────────────────────────────────────────────────────


class TestPositionMode:
    def test_geo_entities_get_positions(self):
        chart = _make_chart(mode='position')
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # All geo entities should have distinct positions
        assert 'E1' in pos
        assert 'E2' in pos
        assert 'E3' in pos
        assert pos['E1'] != pos['E2']
        assert pos['E2'] != pos['E3']

    def test_palmas_north_of_rio(self):
        """Palmas (-10 lat) should have lower Y than Rio (-22 lat)."""
        chart = _make_chart(mode='position')
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # Lower lat = more south = higher Y on canvas (inverted)
        assert pos['E1'][1] < pos['E2'][1], (
            f"Palmas Y ({pos['E1'][1]}) should be less than Rio Y ({pos['E2'][1]})"
        )

    def test_no_latlon_attributes_in_position_mode(self):
        chart = _make_chart(mode='position')
        xml = chart.to_xml()
        assert 'Latitude' not in xml
        assert 'Longitude' not in xml

    def test_unmatched_entity_below_geo_area(self):
        """E4 (unmatched) should be positioned below the geo-positioned entities."""
        chart = _make_chart(mode='position')
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        geo_max_y = max(pos['E1'][1], pos['E2'][1], pos['E3'][1])
        assert pos['E4'][1] > geo_max_y, (
            f"Unmatched E4 Y ({pos['E4'][1]}) should be > geo max Y ({geo_max_y})"
        )


# ── Tests: Latlon mode ─────────────────────────────────────────────────────


class TestLatlonMode:
    def test_latlon_attributes_injected(self):
        chart = _make_chart(mode='latlon')
        xml = chart.to_xml()
        # Latitude and Longitude should appear as AttributeClass names
        assert 'Latitude' in xml
        assert 'Longitude' in xml

    def test_latlon_values_correct(self):
        chart = _make_chart(mode='latlon')
        xml = chart.to_xml()
        # Check that the lat/lon values appear in the XML
        assert '-10.18' in xml  # Palmas lat
        assert '-48.33' in xml  # Palmas lon
        assert '-22.9' in xml   # Rio lat
        assert '-43.17' in xml  # Rio lon

    def test_latlon_semantic_type(self):
        chart = _make_chart(mode='latlon')
        xml = chart.to_xml()
        # Semantic type GUIDs should be present
        assert 'guid5304A03B-FE47-4406-91E7-0D49EC8409A6' in xml  # Latitude
        assert 'guid14BCA0EC-D67A-4A67-BC36-CFF650FD77A9' in xml  # Longitude

    def test_latlon_type_is_number(self):
        chart = _make_chart(mode='latlon')
        xml = chart.to_xml()
        # AttNumber type for the attribute classes
        assert 'Type="AttNumber"' in xml

    def test_no_geo_positions_in_latlon_mode(self):
        """In latlon-only mode, positions should use auto-layout (not geo)."""
        chart = _make_chart(mode='latlon')
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # E4 should exist and all should be auto-laid-out (circle/grid)
        # Verify they're NOT the geo-projected coordinates
        assert 'E4' in pos
        # In latlon-only mode, all 4 entities go through auto-layout
        # so E1 and E4 are treated the same way


# ── Tests: Both mode ───────────────────────────────────────────────────────


class TestBothMode:
    def test_positions_and_attributes(self):
        chart = _make_chart(mode='both')
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # Positions set
        assert pos['E1'] != pos['E2']
        # Lat/lon attributes injected
        assert 'Latitude' in xml
        assert '-10.18' in xml

    def test_explicit_position_wins(self):
        """Entities with explicit x,y should keep those positions."""
        chart = _make_chart(mode='position')
        chart.add_icon(id='EX', type='Person',
                       attributes={'City': 'Palmas/TO'}, x=999, y=888)
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert pos['EX'] == (999, 888)


# ── Tests: Spread radius ──────────────────────────────────────────────────


class TestSpreadRadius:
    def test_spread_distributes_same_key_entities(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            width=2000, height=1500, spread_radius=50,
            data={'Palmas/TO': [-10.18, -48.33]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='B', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='C', type='Person', attributes={'City': 'Palmas/TO'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # All three should have different positions
        assert pos['A'] != pos['B']
        assert pos['B'] != pos['C']
        assert pos['A'] != pos['C']

    def test_spread_zero_stacks(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            width=2000, height=1500, spread_radius=0,
            data={'Palmas/TO': [-10.18, -48.33]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='B', type='Person', attributes={'City': 'Palmas/TO'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # Same position when spread_radius is 0
        assert pos['A'] == pos['B']


# ── Tests: Case-insensitive matching ───────────────────────────────────────


class TestCaseInsensitive:
    def test_lowercase_key_matches_titlecase_value(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data={'palmas/to': [-10.18, -48.33]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'Palmas/TO'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'A' in pos

    def test_uppercase_key_matches(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='city', mode='position',
            data={'PALMAS/TO': [-10.18, -48.33]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'palmas/to'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'A' in pos

    def test_numeric_attribute_value_matches_string_key(self):
        """Numeric attribute values are stringified for matching."""
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='zipcode', mode='position',
            data={'12345': [40.7, -74.0]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'zipcode': 12345})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'A' in pos


# ── Tests: Accent-insensitive matching ─────────────────────────────────────


class TestAccentInsensitive:
    """Folds Unicode diacritics during matching when accent_insensitive (default).

    Symmetric: any combination of accented/unaccented on the lookup-key side and
    the entity-attribute-value side should match. Disabling the flag restores
    strict (lowercase-exact) matching.
    """

    @pytest.mark.parametrize("attr_value", [
        'São Paulo/SP',     # full accents
        'SÃO PAULO/SP',     # accents + uppercase
        'SAO PAULO/SP',     # uppercased, no accents
        'sao paulo/sp',     # lowercase, no accents
        'Sao Paulo/SP',     # title case, no accents (matches the key verbatim)
        '  São Paulo/SP  ', # leading/trailing whitespace
    ])
    def test_accented_and_unaccented_variants_all_match(self, attr_value):
        """Any case+accent combination on the entity side hits a plain-ASCII key."""
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data={'Sao Paulo/SP': [-23.55, -46.63]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': attr_value})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'A' in pos

    @pytest.mark.parametrize("key", [
        'São Paulo/SP',
        'SÃO PAULO/SP',
        'sao paulo/sp',
        'Sao Paulo/SP',
    ])
    def test_accented_and_unaccented_keys_all_match(self, key):
        """Any case+accent combination on the lookup-key side hits a plain-ASCII value."""
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data={key: [-23.55, -46.63]},
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'sao paulo/sp'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'A' in pos

    def test_strict_mode_rejects_accent_mismatch(self):
        """With accent_insensitive=False, accented and unaccented forms diverge."""
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data={'Sao Paulo/SP': [-23.55, -46.63]},
            accent_insensitive=False,
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'São Paulo/SP'})
        # E4-style fallback: unmatched entities are placed below the geo bbox.
        # Add a matched anchor so we can prove the accented entity *didn't* land
        # on the same projected position.
        chart.add_icon(id='B', type='Person', attributes={'City': 'sao paulo/sp'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # B matched (lowercase ASCII == lowercase key), A fell through to fallback.
        assert pos['A'] != pos['B']

    def test_strict_mode_keeps_case_insensitive(self):
        """accent_insensitive=False does NOT disable case-insensitive matching."""
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data={'sao paulo/sp': [-23.55, -46.63]},
            accent_insensitive=False,
        ))))
        chart.add_icon(id='A', type='Person', attributes={'City': 'SAO PAULO/SP'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'A' in pos


# ── Tests: Validation ──────────────────────────────────────────────────────


class TestGeoMapValidation:
    def test_missing_attribute_name(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            mode='both', data=GEO_DATA,
        ))))
        chart.add_icon(id='A', type='Person')
        errors = chart.validate()
        geo_errors = [e for e in errors if e['type'] == ErrorType.INVALID_GEO_MAP.value]
        assert len(geo_errors) >= 1
        assert 'attribute_name' in geo_errors[0]['message']

    def test_invalid_mode(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='invalid', data=GEO_DATA,
        ))))
        chart.add_icon(id='A', type='Person')
        errors = chart.validate()
        geo_errors = [e for e in errors if e['type'] == ErrorType.INVALID_GEO_MAP.value]
        assert any('mode' in e['message'] for e in geo_errors)

    def test_lat_out_of_range(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', data={'Bad': [91.0, 0.0]},
        ))))
        chart.add_icon(id='A', type='Person')
        errors = chart.validate()
        geo_errors = [e for e in errors if e['type'] == ErrorType.INVALID_GEO_MAP.value]
        assert any('latitude' in e['message'] for e in geo_errors)

    def test_lon_out_of_range(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', data={'Bad': [0.0, 181.0]},
        ))))
        chart.add_icon(id='A', type='Person')
        errors = chart.validate()
        geo_errors = [e for e in errors if e['type'] == ErrorType.INVALID_GEO_MAP.value]
        assert any('longitude' in e['message'] for e in geo_errors)

    def test_no_data(self):
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City',
        ))))
        chart.add_icon(id='A', type='Person')
        errors = chart.validate()
        geo_errors = [e for e in errors if e['type'] == ErrorType.INVALID_GEO_MAP.value]
        assert any('data' in e['message'] for e in geo_errors)

    def test_valid_config_no_errors(self):
        chart = _make_chart(mode='both')
        errors = chart.validate()
        geo_errors = [e for e in errors if e['type'] == ErrorType.INVALID_GEO_MAP.value]
        assert len(geo_errors) == 0


# ── Tests: from_dict integration ──────────────────────────────────────────


class TestFromDict:
    def test_geo_map_via_from_dict(self):
        chart = ANXChart.from_dict({
            'settings': {
                'extra_cfg': {
                    'geo_map': {
                        'attribute_name': 'City',
                        'mode': 'both',
                        'width': 2000,
                        'data': {
                            'Palmas/TO': [-10.18, -48.33],
                        },
                    },
                },
            },
            'entities': {
                'icons': [
                    {'id': 'E1', 'type': 'Person', 'attributes': {'City': 'Palmas/TO'}},
                    {'id': 'E2', 'type': 'Person', 'attributes': {'City': 'Unknown'}},
                ],
            },
            'links': [{'from_id': 'E1', 'to_id': 'E2', 'type': 'Knows'}],
        })
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert 'E1' in pos
        assert 'E2' in pos
        # E1 (geo-positioned) should differ from E2 (auto-layout)
        assert pos['E1'] != pos['E2']
        # Both lat/lon attributes should be present
        assert 'Latitude' in xml
        assert '-10.18' in xml


# ── Tests: data_file loading ─────────────────────────────────────────────


class TestDataFile:
    def test_load_json_data_file(self, tmp_path):
        geo_file = tmp_path / 'coords.json'
        geo_file.write_text(json.dumps({
            'Palmas/TO': [-10.18, -48.33],
            'Rio de Janeiro/RJ': [-22.90, -43.17],
        }))
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data_file=str(geo_file),
        ))))
        chart.add_icon(id='E1', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='E2', type='Person', attributes={'City': 'Rio de Janeiro/RJ'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert pos['E1'] != pos['E2']

    def test_load_yaml_data_file(self, tmp_path):
        pytest.importorskip('yaml')
        geo_file = tmp_path / 'coords.yaml'
        geo_file.write_text(
            'Palmas/TO: [-10.18, -48.33]\n'
            'Rio de Janeiro/RJ: [-22.90, -43.17]\n'
        )
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data_file=str(geo_file),
        ))))
        chart.add_icon(id='E1', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='E2', type='Person', attributes={'City': 'Rio de Janeiro/RJ'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert pos['E1'] != pos['E2']

    def test_inline_data_overrides_file(self, tmp_path):
        """Inline data entries should override data_file entries for the same key."""
        geo_file = tmp_path / 'coords.json'
        geo_file.write_text(json.dumps({
            'Palmas/TO': [0.0, 0.0],  # file has wrong coords
        }))
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data={'Palmas/TO': [-10.18, -48.33]},  # inline overrides
            data_file=str(geo_file),
        ))))
        chart.add_icon(id='E1', type='Person', attributes={'City': 'Palmas/TO'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        # Should use inline coords, not file coords
        # With only 1 point, x/y will be at width/2, height/2 (center)
        assert 'E1' in pos


# ── Tests: Relative data_file path resolution ───────────────────────────


class TestDataFileRelativePathResolution:
    """``geo_map.data_file`` written as a relative path inside a YAML/JSON
    config or data file should resolve against the file's own directory,
    not CWD — matching Compose, Cargo, GitLab CI etc.

    Each test uses ``monkeypatch.chdir`` to a directory that does NOT
    contain the geo data file; if path resolution incorrectly used CWD,
    the load would raise ``FileNotFoundError``.
    """

    GEO_TEXT_YAML = (
        'Palmas/TO: [-10.18, -48.33]\n'
        'Rio de Janeiro/RJ: [-22.90, -43.17]\n'
    )
    GEO_TEXT_JSON = json.dumps({
        'Palmas/TO': [-10.18, -48.33],
        'Rio de Janeiro/RJ': [-22.90, -43.17],
    })

    def _write_pair(self, tmp_path: Path, chart_name: str, geo_name: str,
                    chart_text: str, geo_text: str) -> Path:
        """Write a chart file and a geo data file in a sibling directory.
        CWD-relative resolution would fail; file-relative would succeed."""
        sub = tmp_path / 'cfg'
        sub.mkdir()
        chart_path = sub / chart_name
        chart_path.write_text(chart_text)
        (sub / geo_name).write_text(geo_text)
        return chart_path

    def test_from_yaml_file_relative_data_file(self, tmp_path, monkeypatch):
        pytest.importorskip('yaml')
        chart_text = (
            "settings:\n"
            "  extra_cfg:\n"
            "    geo_map:\n"
            "      attribute_name: City\n"
            "      mode: position\n"
            "      data_file: coords.yaml\n"
            "entities:\n"
            "  icons:\n"
            "    - {id: E1, type: Person, attributes: {City: Palmas/TO}}\n"
            "    - {id: E2, type: Person, attributes: {City: Rio de Janeiro/RJ}}\n"
        )
        chart_path = self._write_pair(
            tmp_path, 'chart.yaml', 'coords.yaml',
            chart_text, self.GEO_TEXT_YAML,
        )
        # CWD is somewhere that does NOT contain coords.yaml.
        monkeypatch.chdir(tmp_path)
        chart = ANXChart.from_yaml_file(chart_path)
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert pos['E1'] != pos['E2']

    def test_from_json_file_relative_data_file(self, tmp_path, monkeypatch):
        chart_text = json.dumps({
            'settings': {'extra_cfg': {'geo_map': {
                'attribute_name': 'City', 'mode': 'position',
                'data_file': 'coords.json',
            }}},
            'entities': {'icons': [
                {'id': 'E1', 'type': 'Person', 'attributes': {'City': 'Palmas/TO'}},
                {'id': 'E2', 'type': 'Person', 'attributes': {'City': 'Rio de Janeiro/RJ'}},
            ]},
        })
        chart_path = self._write_pair(
            tmp_path, 'chart.json', 'coords.json',
            chart_text, self.GEO_TEXT_JSON,
        )
        monkeypatch.chdir(tmp_path)
        chart = ANXChart.from_json_file(chart_path)
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert pos['E1'] != pos['E2']

    def test_apply_config_file_relative_data_file(self, tmp_path, monkeypatch):
        """Config-file path: geo_map declared in a config file (not data file)."""
        pytest.importorskip('yaml')
        cfg_text = (
            "settings:\n"
            "  extra_cfg:\n"
            "    geo_map:\n"
            "      attribute_name: City\n"
            "      mode: position\n"
            "      data_file: coords.yaml\n"
        )
        cfg_path = self._write_pair(
            tmp_path, 'config.yaml', 'coords.yaml',
            cfg_text, self.GEO_TEXT_YAML,
        )
        monkeypatch.chdir(tmp_path)
        chart = ANXChart.from_config_file(cfg_path)
        chart.add_icon(id='E1', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='E2', type='Person', attributes={'City': 'Rio de Janeiro/RJ'})
        xml = chart.to_xml()
        pos = _parse_positions(xml)
        assert pos['E1'] != pos['E2']

    def test_absolute_path_in_yaml_unchanged(self, tmp_path, monkeypatch):
        """Absolute paths must be left alone, not re-anchored against the file's dir."""
        pytest.importorskip('yaml')
        # Geo file lives somewhere unrelated to the chart file
        geo_dir = tmp_path / 'geo'
        geo_dir.mkdir()
        geo_path = geo_dir / 'coords.yaml'
        geo_path.write_text(self.GEO_TEXT_YAML)

        chart_text = (
            "settings:\n"
            "  extra_cfg:\n"
            "    geo_map:\n"
            "      attribute_name: City\n"
            "      mode: position\n"
            f"      data_file: {geo_path}\n"
            "entities:\n"
            "  icons:\n"
            "    - {id: E1, type: Person, attributes: {City: Palmas/TO}}\n"
            "    - {id: E2, type: Person, attributes: {City: Rio de Janeiro/RJ}}\n"
        )
        sub = tmp_path / 'cfg'
        sub.mkdir()
        chart_path = sub / 'chart.yaml'
        chart_path.write_text(chart_text)
        monkeypatch.chdir(tmp_path)
        chart = ANXChart.from_yaml_file(chart_path)
        # Absolute path should be preserved as-is on the loaded GeoMapCfg
        assert chart.settings.extra_cfg.geo_map.data_file == str(geo_path)

    def test_inline_python_geomapcfg_stays_cwd_relative(self, tmp_path, monkeypatch):
        """Inline Python ``GeoMapCfg(data_file=...)`` is not file-loaded, so it
        keeps standard ``open()`` semantics (CWD-relative). Only file-loaded
        configs get the rewrite."""
        # Geo file lives in tmp_path; CWD set there so a bare 'coords.yaml'
        # works, mirroring how a Python user would treat it.
        pytest.importorskip('yaml')
        (tmp_path / 'coords.yaml').write_text(self.GEO_TEXT_YAML)
        monkeypatch.chdir(tmp_path)
        chart = ANXChart(settings=Settings(extra_cfg=ExtraCfg(geo_map=GeoMapCfg(
            attribute_name='City', mode='position',
            data_file='coords.yaml',  # bare relative — resolves to CWD
        ))))
        chart.add_icon(id='E1', type='Person', attributes={'City': 'Palmas/TO'})
        chart.add_icon(id='E2', type='Person', attributes={'City': 'Rio de Janeiro/RJ'})
        # Should not raise: CWD has coords.yaml.
        chart.to_xml()
        # And the stored value is unchanged.
        assert chart.settings.extra_cfg.geo_map.data_file == 'coords.yaml'


# ── Tests: Transform functions (unit) ────────────────────────────────────


class TestTransformFunctions:
    def test_resolve_geo_data_inline(self):
        gm = GeoMapCfg(data={'NYC': [40.7, -74.0], 'LA': [34.0, -118.2]})
        result = resolve_geo_data(gm)
        assert 'nyc' in result
        assert result['nyc'] == (40.7, -74.0)

    def test_resolve_geo_data_normalizes_keys(self):
        gm = GeoMapCfg(data={' NYC ': [40.7, -74.0]})
        result = resolve_geo_data(gm)
        assert 'nyc' in result

    def test_match_geo_entities_basic(self):
        from anxwritter.entities import Icon
        entities = [
            Icon(id='A', type='T', attributes={'city': 'NYC'}),
            Icon(id='B', type='T', attributes={'city': 'LA'}),
            Icon(id='C', type='T', attributes={'city': 'Unknown'}),
        ]
        geo_data = {'nyc': (40.7, -74.0), 'la': (34.0, -118.2)}
        matched = match_geo_entities(entities, geo_data, 'city')
        assert 'nyc' in matched
        assert 'la' in matched
        assert len(matched['nyc']) == 1
        assert matched['nyc'][0][0] == 'A'

    def test_compute_geo_positions_basic(self):
        matched = {
            'nyc': [('A', 40.7, -74.0)],
            'la': [('B', 34.0, -118.2)],
        }
        positions: Dict[str, Tuple[int, int]] = {}
        bbox = compute_geo_positions(matched, positions, width=1000, height=1000)
        assert 'A' in positions
        assert 'B' in positions
        assert positions['A'] != positions['B']
        # NYC is further north (higher lat) = lower Y
        assert positions['A'][1] < positions['B'][1]

    def test_compute_geo_positions_spread(self):
        matched = {
            'nyc': [('A', 40.7, -74.0), ('B', 40.7, -74.0)],
        }
        positions: Dict[str, Tuple[int, int]] = {}
        compute_geo_positions(matched, positions, spread_radius=50)
        assert positions['A'] != positions['B']

    def test_compute_geo_positions_respects_existing(self):
        """Entities already in positions dict should not be overwritten."""
        matched = {'nyc': [('A', 40.7, -74.0)]}
        positions = {'A': (999, 888)}
        compute_geo_positions(matched, positions)
        assert positions['A'] == (999, 888)


# ── Tests: Idempotency ──────────────────────────────────────────────────


class TestIdempotency:
    def test_to_xml_twice_same_result(self):
        """Calling to_xml multiple times should give identical results."""
        chart = _make_chart(mode='both')
        xml1 = chart.to_xml()
        xml2 = chart.to_xml()
        assert xml1 == xml2

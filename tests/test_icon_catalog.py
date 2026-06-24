"""Tests for the custom-icon catalog (1.20.0).

Covers IconCatalog (bake/validate/export/round-trip), the build-time
``referenced`` filter (default) vs ``all``, the config-only Pillow gate, the
layering mini-engine (merge/wipe/lock/delete + cascade.mode), apply/export on
the chart, and the ``custom_icons_include`` validation.
"""

import base64
import os
import re
import struct
import tempfile

import pytest

from anxwritter import ANXChart, IconCatalog
from anxwritter import custom_icons


# ── Pillow-free BMP helpers ───────────────────────────────────────────────────

def _make_bmp(w=8, h=8):
    row = b'\xff\x00\xff' * w
    row += b'\x00' * ((4 - (len(row) % 4)) % 4)
    pixels = row * h
    info = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
    return b'BM' + struct.pack('<IHHI', 54 + len(pixels), 0, 0, 54) + info + pixels


def _bmp_uri(w=8, h=8):
    return "data:image/bmp;base64," + base64.b64encode(_make_bmp(w, h)).decode()


def _n_images(xml):
    return len(re.findall(r'<CustomImage ', xml))


# ── IconCatalog ───────────────────────────────────────────────────────────────

class TestIconCatalog:
    def test_add_validate_to_dict(self):
        cat = IconCatalog()
        cat.add_custom_entity_icon('suspect', _make_bmp())
        cat.add_custom_attribute_icon('cpf', _bmp_uri())
        assert cat.validate() == []
        d = cat.to_dict()
        assert {e['name'] for e in d['custom_entity_icons']} == {'suspect'}
        assert {e['name'] for e in d['custom_attribute_icons']} == {'cpf'}
        # compiled form: data + datalength, no raw `image`
        row = d['custom_entity_icons'][0]
        assert 'data' in row and 'datalength' in row and 'image' not in row

    def test_export_roundtrip_and_determinism(self):
        cat = IconCatalog()
        cat.add_custom_entity_icon('a', _make_bmp())
        cat.add_custom_attribute_icon('b', _make_bmp(6, 6))
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'cat.yaml')
        cat.export_catalog(p)
        first = open(p, encoding='utf-8').read()
        cat.export_catalog(p)                      # re-export
        assert open(p, encoding='utf-8').read() == first   # deterministic
        loaded = IconCatalog.from_file(p)
        assert loaded._entity == cat._entity
        assert loaded._attribute == cat._attribute

    def test_export_json(self):
        cat = IconCatalog()
        cat.add_custom_entity_icon('a', _make_bmp())
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'cat.json')
        cat.export_catalog(p, format='json')
        assert IconCatalog.from_file(p)._entity == cat._entity

    def test_export_cascade_mode(self):
        cat = IconCatalog()
        cat.add_custom_entity_icon('a', _make_bmp())
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'cat.yaml')
        cat.export_catalog(p, cascade_mode='lock')
        import yaml
        doc = yaml.safe_load(open(p, encoding='utf-8'))
        assert doc['cascade'] == {'mode': 'lock'}
        assert doc['_meta']['format'] == custom_icons.CATALOG_FORMAT

    def test_validate_flags_corrupt_blob(self):
        cat = IconCatalog()
        cat.add_custom_entity_icon('ok', _make_bmp())
        cat._entity['bad'] = {'emitted': 'anxW_bad', 'prefix': 'anxW_',
                              'data': 'not-base64!!', 'datalength': 10}
        errs = cat.validate()
        assert any(e['type'] == 'invalid_icon_blob' for e in errs)

    def test_from_files_later_wins(self):
        d = tempfile.mkdtemp()
        c1 = IconCatalog(); c1.add_custom_entity_icon('x', _make_bmp(8, 8))
        p1 = os.path.join(d, 'a.yaml'); c1.export_catalog(p1)
        c2 = IconCatalog(); c2.add_custom_entity_icon('x', _make_bmp(6, 6))
        p2 = os.path.join(d, 'b.yaml'); c2.export_catalog(p2)
        merged = IconCatalog.from_files([p1, p2])
        assert merged._entity['x'] == c2._entity['x']

    def test_include_in_config(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'org.yaml')
        import yaml
        with open(p, 'w', encoding='utf-8') as fh:
            yaml.safe_dump({'entity_types': [{'name': 'Person'}]}, fh)
        cat = IconCatalog(); cat.add_custom_entity_icon('logo', _make_bmp())
        cat.include_in_config(p)
        doc = yaml.safe_load(open(p, encoding='utf-8'))
        assert doc['entity_types'] == [{'name': 'Person'}]      # preserved
        assert doc['custom_entity_icons'][0]['name'] == 'logo'  # injected


# ── Referenced filter (default) vs all ────────────────────────────────────────

class TestReferencedFilter:
    def test_default_referenced_prunes_unreferenced(self):
        c = ANXChart()
        c.add_custom_entity_icon('used', _make_bmp())
        c.add_custom_entity_icon('unused', _make_bmp())
        c.add_entity_type(name='Person', icon_file='used')
        c.add_icon(id='A', type='Person')
        assert _n_images(c.to_xml()) == 1     # 'unused' pruned

    def test_include_all_keeps_everything(self):
        c = ANXChart(settings={'extra_cfg': {'custom_icons_include': 'all'}})
        c.add_custom_entity_icon('used', _make_bmp())
        c.add_custom_entity_icon('unused', _make_bmp())
        c.add_entity_type(name='Person', icon_file='used')
        c.add_icon(id='A', type='Person')
        assert _n_images(c.to_xml()) == 2

    def test_per_entity_reference_counts(self):
        c = ANXChart()
        c.add_custom_entity_icon('star', _make_bmp())
        c.add_icon(id='X', type='Foo', icon='star')
        assert _n_images(c.to_xml()) == 1

    def test_attribute_icon_referenced_by_ac(self):
        c = ANXChart()
        c.add_custom_attribute_icon('cpf', _make_bmp())
        c.add_custom_attribute_icon('orphan', _make_bmp())
        c.add_attribute_class(name='CPF', type='text', icon_file='cpf')
        c.add_icon(id='A', type='Person', attributes={'CPF': '123'})
        assert _n_images(c.to_xml()) == 1     # only the AC-declared one


# ── Pillow gate (config gates, data doesn't) ──────────────────────────────────

class TestPillowGate:
    def test_config_png_path_raises(self):
        c = ANXChart()
        with pytest.raises(ValueError, match="IconCatalog"):
            c.apply_config({'custom_entity_icons': [{'name': 'x', 'image': 'foo.png'}]})

    def test_config_bmp_uri_ok(self):
        c = ANXChart()
        c.apply_config({'custom_entity_icons': [{'name': 'x', 'image': _bmp_uri()}]})
        assert 'x' in c._custom_entity_icons

    def test_config_compiled_ok(self):
        cat = IconCatalog(); cat.add_custom_entity_icon('x', _make_bmp())
        c = ANXChart()
        c.apply_config(cat.to_dict())          # compiled data/datalength
        assert 'x' in c._custom_entity_icons

    def test_data_path_bmp_ok(self):
        c = ANXChart.from_dict({
            'custom_entity_icons': [{'name': 'x', 'image': _bmp_uri()}],
            'entities': {'icons': []},
        })
        assert 'x' in c._custom_entity_icons

    def test_data_path_png_converts(self):
        if not custom_icons.HAS_PILLOW:
            pytest.skip("Pillow not installed")
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new('RGBA', (10, 10), (0, 128, 255, 255)).save(buf, format='PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        c = ANXChart.from_dict({
            'custom_entity_icons': [{'name': 'x', 'image': uri}],
            'entities': {'icons': []},
        })
        assert 'x' in c._custom_entity_icons   # Pillow-converted on the data path


# ── Layering mini-engine ──────────────────────────────────────────────────────

class TestLayeringMiniEngine:
    def test_merge_later_wins(self):
        c = ANXChart()
        c.apply_config({'custom_entity_icons': [{'name': 's', 'image': _bmp_uri(8, 8)}]})
        c.apply_config({'custom_entity_icons': [{'name': 's', 'image': _bmp_uri(6, 6)}]})
        assert c._custom_entity_icons['s']['datalength'] == len(_make_bmp(6, 6))

    def test_lock_blocks_later_change(self):
        c = ANXChart()
        c.apply_config({'custom_entity_icons': [{'name': 's', 'image': _bmp_uri(8, 8)}]}, lock=True)
        c.apply_config({'custom_entity_icons': [{'name': 's', 'image': _bmp_uri(6, 6)}]})
        assert any(e['type'] == 'locked_override' for e in c.validate())
        # locked value preserved
        assert c._custom_entity_icons['s']['datalength'] == len(_make_bmp(8, 8))

    def test_delete_removes_named(self):
        c = ANXChart()
        c.apply_config({'custom_entity_icons': [
            {'name': 's', 'image': _bmp_uri()}, {'name': 't', 'image': _bmp_uri()}]})
        c.apply_config({'custom_entity_icons': [{'name': 's'}]}, operation='delete')
        assert 's' not in c._custom_entity_icons
        assert 't' in c._custom_entity_icons

    def test_delete_absent_is_noop(self):
        c = ANXChart()
        c.apply_config({'custom_entity_icons': [{'name': 'ghost'}]}, operation='delete')
        assert c._custom_entity_icons == {}

    def test_wipe_clears_section(self):
        c = ANXChart()
        c.apply_config({'custom_entity_icons': [
            {'name': 'a', 'image': _bmp_uri()}, {'name': 'b', 'image': _bmp_uri()}]})
        c.apply_config({'custom_entity_icons': [{'name': 'c', 'image': _bmp_uri()}]},
                       wipe_previous=True)
        assert set(c._custom_entity_icons) == {'c'}

    def test_cascade_mode_lock_in_file(self):
        c = ANXChart()
        c.apply_icon_catalog({'cascade': {'mode': 'lock'},
                              'custom_entity_icons': [{'name': 'z', 'image': _bmp_uri(8, 8)}]})
        c.apply_config({'custom_entity_icons': [{'name': 'z', 'image': _bmp_uri(6, 6)}]})
        assert any(e['type'] == 'locked_override' for e in c.validate())


# ── Chart apply/export ────────────────────────────────────────────────────────

class TestChartApplyExport:
    def test_apply_catalog_object(self):
        cat = IconCatalog()
        cat.add_custom_entity_icon('logo', _make_bmp())
        cat.add_custom_attribute_icon('cpf', _make_bmp())
        c = ANXChart()
        c.apply_icon_catalog(cat, include='all')
        assert 'logo' in c._custom_entity_icons
        assert 'cpf' in c._custom_attribute_icons
        assert c.settings.extra_cfg.custom_icons_include == 'all'

    def test_export_then_apply_roundtrip(self):
        c = ANXChart()
        c.add_custom_entity_icon('logo', _make_bmp())
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'cat.yaml')
        c.export_icon_catalog(p)
        c2 = ANXChart()
        c2.apply_icon_catalog(p)
        assert c2._custom_entity_icons.keys() == c._custom_entity_icons.keys()

    def test_apply_bad_type_raises(self):
        with pytest.raises(TypeError):
            ANXChart().apply_icon_catalog(123)

    def test_invalid_include_value_validation(self):
        c = ANXChart(settings={'extra_cfg': {'custom_icons_include': 'bogus'}})
        c.add_icon(id='A', type='Person')
        assert any(e['type'] == 'invalid_custom_icons_include' for e in c.validate())

    def test_apply_include_kwarg_validation(self):
        with pytest.raises(ValueError):
            ANXChart().apply_icon_catalog(IconCatalog(), include='nope')

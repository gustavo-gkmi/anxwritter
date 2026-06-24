"""Tests for embedded custom icons (1.19.0)."""

import base64
import io
import re
import struct
import zlib

import pytest

from anxwritter import ANXChart, AttributeType
from anxwritter import custom_icons


# ── Pillow-free helpers + name/key/passthrough ────────────────────────────────

def _make_bmp(w=8, h=8, bpp=24):
    """Hand-build a minimal BMP with the stdlib (no Pillow) — magenta fill."""
    if bpp == 24:
        row = b'\xff\x00\xff' * w
        row += b'\x00' * ((4 - (len(row) % 4)) % 4)
    else:
        row = b'\xff\x00\xff\x00' * w
    pixels = row * h
    info = struct.pack('<IiiHHIIiiII', 40, w, h, 1, bpp, 0, len(pixels), 2835, 2835, 0, 0)
    return b'BM' + struct.pack('<IHHI', 54 + len(pixels), 0, 0, 54) + info + pixels


def _bmp_data_uri(bpp=24):
    return "data:image/bmp;base64," + base64.b64encode(_make_bmp(bpp=bpp)).decode()


class TestNameAndKey:
    def test_valid_names(self):
        for n in ('Person', 'company_logo', 'Icon Sample', 'anxW_x', 'x' * 120):
            assert custom_icons.validate_icon_name(n) is None

    @pytest.mark.parametrize('bad', ['', '   ', 'a,b', 'a/b', 'a:b', 'x' * 121])
    def test_invalid_names(self, bad):
        assert custom_icons.validate_icon_name(bad) is not None

    def test_composite_key(self):
        assert custom_icons.composite_key('anxW_P', 'Icon') == 'anxW_P,Screen,Icon'
        assert custom_icons.composite_key('anxW_P', 'Attribute') == 'anxW_P,Screen,Attribute'

    def test_data_uri_coercion(self):
        out = custom_icons.coerce_image_source(_bmp_data_uri())
        assert isinstance(out, bytes) and out[:2] == b'BM'
        assert custom_icons.coerce_image_source('path.png') == 'path.png'  # passthrough

    def test_data_uri_errors(self):
        with pytest.raises(custom_icons.CustomIconError):
            custom_icons.coerce_image_source('data:image/png,notbase64')


class TestBmpPassthrough:
    def test_verbatim(self):
        bmp = _make_bmp()
        assert custom_icons.prepare_icon_bmp(bmp) == bmp

    def test_reject_32bit(self):
        with pytest.raises(custom_icons.CustomIconError, match='black box'):
            custom_icons.prepare_icon_bmp(_make_bmp(bpp=32))

    def test_reject_oversize(self):
        with pytest.raises(custom_icons.CustomIconError, match='too large'):
            custom_icons.prepare_icon_bmp(_make_bmp(300, 300))


class TestRegistryNoPillow:
    """The registry API works with a BMP / data: URI and no Pillow."""

    def test_register_and_emit(self, monkeypatch):
        monkeypatch.setattr(custom_icons, 'HAS_PILLOW', False)
        c = ANXChart()
        c.add_custom_entity_icon('vip', _make_bmp())
        c.add_entity_type(name='P', icon_file='vip')
        c.add_icon(id='A', type='P', x=0, y=0)
        xml = c.to_xml()
        assert 'Id="anxW_vip,Screen,Icon"' in xml
        assert re.search(r'<EntityType[^>]*IconFile="anxW_vip"', xml)

    def test_data_uri(self):
        c = ANXChart()
        c.add_custom_entity_icon('logo', _bmp_data_uri())
        c.add_entity_type(name='P', icon_file='logo')
        c.add_icon(id='A', type='P', x=0, y=0)
        assert 'Id="anxW_logo,Screen,Icon"' in c.to_xml()

    def test_printer_guard(self):
        c = ANXChart()
        with pytest.raises(NotImplementedError, match='not yet shipped'):
            c.add_custom_entity_icon('vip', _make_bmp(), printer=True)

    def test_empty_name_raises(self):
        c = ANXChart()
        with pytest.raises(ValueError, match='empty'):
            c.add_custom_entity_icon('', _make_bmp())

    def test_comma_name_raises(self):
        c = ANXChart()
        with pytest.raises(ValueError):
            c.add_custom_entity_icon('a,b', _make_bmp())

    def test_prefix_variants(self):
        c = ANXChart()
        c.add_custom_entity_icon('a', _make_bmp())                  # default anxW_
        c.add_custom_entity_icon('b', _make_bmp(), prefix='')       # none
        c.add_custom_entity_icon('d', _make_bmp(), prefix='acme_')  # custom
        c.add_entity_type(name='TA', icon_file='a')
        c.add_entity_type(name='TB', icon_file='b')
        c.add_entity_type(name='TD', icon_file='d')
        c.add_icon(id='x', type='TA', x=0, y=0)
        xml = c.to_xml()
        assert 'anxW_a,Screen,Icon' in xml
        assert 'Id="b,Screen,Icon"' in xml
        assert 'acme_d,Screen,Icon' in xml

    def test_passthrough_when_not_registered(self):
        c = ANXChart()
        c.add_entity_type(name='P', icon_file='car')   # not registered → verbatim
        c.add_icon(id='A', type='P', x=0, y=0)
        xml = c.to_xml()
        assert '<CustomImageCollection>' not in xml
        assert 'IconFile="car"' in xml

    def test_upsert_last_wins(self):
        c = ANXChart()
        c.add_custom_entity_icon('vip', _make_bmp(8, 8))
        c.add_custom_entity_icon('vip', _make_bmp(16, 16))   # re-register → replaces
        c.add_entity_type(name='P', icon_file='vip')
        c.add_icon(id='A', type='P', x=0, y=0)
        assert c.to_xml().count('<CustomImage ') == 1


# ── Pillow-required: conversion + full emission ───────────────────────────────

requires_pil = pytest.mark.skipif(
    not custom_icons.HAS_PILLOW, reason='custom icon conversion needs Pillow'
)
if custom_icons.HAS_PILLOW:
    from PIL import Image, ImageDraw


def _png(color=(255, 0, 0, 255), size=(64, 64)):
    im = Image.new('RGBA', size, color)
    ImageDraw.Draw(im).ellipse([8, 8, size[0] - 8, size[1] - 8], fill=(0, 0, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return buf.getvalue()


@requires_pil
class TestConversion:
    def test_24bit_square_downscale_only(self):
        bmp = custom_icons.convert_to_bmp(_png(size=(400, 200)), max_size=128)
        assert struct.unpack('<H', bmp[28:30])[0] == 24
        w, h = struct.unpack('<ii', bmp[18:26])
        assert w == h and max(w, h) <= 128

    def test_no_upscale(self):
        bmp = custom_icons.convert_to_bmp(_png(size=(20, 20)))
        w, h = struct.unpack('<ii', bmp[18:26])
        assert max(w, h) == 20

    def test_deterministic(self):
        assert custom_icons.convert_to_bmp(_png()) == custom_icons.convert_to_bmp(_png())

    def test_unreadable_raises(self):
        with pytest.raises(custom_icons.CustomIconError):
            custom_icons.convert_to_bmp(b'not an image')


@requires_pil
class TestEmission:
    def test_entity_attribute_and_per_entity(self):
        c = ANXChart()
        c.add_custom_entity_icon('vip', _png())
        c.add_custom_attribute_icon('flag', _png((0, 255, 0, 255)))
        c.add_entity_type(name='Person', icon_file='vip')
        c.add_attribute_class(name='Priority', type=AttributeType.TEXT, icon_file='flag')
        c.add_icon(id='Alice', type='Person', x=0, y=0, attributes={'Priority': 'hi'})
        c.add_icon(id='Bob', type='Person', icon='vip', x=0, y=0)   # per-entity override
        xml = c.to_xml()
        assert 'Id="anxW_vip,Screen,Icon"' in xml
        assert 'Id="anxW_flag,Screen,Attribute"' in xml
        assert re.search(r'<EntityType[^>]*IconFile="anxW_vip"', xml)
        assert re.search(r'<AttributeClass[^>]*IconFile="anxW_flag"', xml)
        assert 'TypeIconName="anxW_vip"' in xml   # Bob's override resolved

    def test_deterministic_output(self):
        c = ANXChart()
        c.add_custom_entity_icon('vip', _png())
        c.add_entity_type(name='P', icon_file='vip')
        c.add_icon(id='A', type='P', x=0, y=0)
        assert c.to_xml() == c.to_xml()

    def test_data_round_trips_as_bmp(self):
        c = ANXChart()
        c.add_custom_entity_icon('vip', _png())
        c.add_entity_type(name='P', icon_file='vip')
        c.add_icon(id='A', type='P', x=0, y=0)
        data = re.search(r'<CustomImage [^>]*Data="([^"]+)"', c.to_xml()).group(1)
        assert zlib.decompress(base64.b64decode(data))[:2] == b'BM'


@requires_pil
class TestConfig:
    def test_yaml_config_sections(self):
        uri = _bmp_data_uri()
        c = ANXChart.from_yaml(
            "custom_entity_icons:\n"
            f"  - {{name: vip, image: '{uri}'}}\n"
            "entity_types:\n"
            "  - {name: Person, icon_file: vip}\n"
            "entities:\n"
            "  icons:\n"
            "    - {id: Alice, type: Person}\n"
        )
        xml = c.to_xml()
        assert 'Id="anxW_vip,Screen,Icon"' in xml
        assert re.search(r'<EntityType[^>]*IconFile="anxW_vip"', xml)

    def test_config_round_trip(self):
        c = ANXChart()
        c.add_custom_entity_icon('vip', _png(), prefix='acme_')
        cfg = c.to_config_dict()
        assert cfg['custom_entity_icons'][0]['name'] == 'vip'
        assert cfg['custom_entity_icons'][0]['prefix'] == 'acme_'
        assert cfg['custom_entity_icons'][0]['image'].startswith('data:image/bmp;base64,')
        # re-import the exported config → same emitted name
        c2 = ANXChart()
        c2.apply_config(cfg)
        c2.add_entity_type(name='P', icon_file='vip')
        c2.add_icon(id='A', type='P', x=0, y=0)
        assert 'Id="acme_vip,Screen,Icon"' in c2.to_xml()

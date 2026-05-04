"""Tests for color parsing: named colors, #RRGGBB, COLORREF int."""

import pytest
from anxwritter import Color
from anxwritter.colors import color_to_colorref, rgb_to_colorref, NAMED_COLORS


class TestRgbToColorref:
    def test_black(self):
        assert rgb_to_colorref(0, 0, 0) == 0

    def test_white(self):
        assert rgb_to_colorref(255, 255, 255) == 16777215

    def test_red(self):
        # R=255 → 255 + 0*256 + 0*65536
        assert rgb_to_colorref(255, 0, 0) == 255

    def test_green(self):
        assert rgb_to_colorref(0, 255, 0) == 65280

    def test_blue(self):
        assert rgb_to_colorref(0, 0, 255) == 16711680


class TestColorToColorref:
    def test_named_color(self):
        result = color_to_colorref('Blue')
        assert isinstance(result, int)
        assert result == NAMED_COLORS['Blue']

    def test_hex_color(self):
        result = color_to_colorref('#FF0000')
        assert result == rgb_to_colorref(255, 0, 0)

    def test_hex_without_hash(self):
        result = color_to_colorref('00FF00')
        assert result == rgb_to_colorref(0, 255, 0)

    def test_integer_passthrough(self):
        assert color_to_colorref(12345) == 12345

    def test_float_passthrough(self):
        assert color_to_colorref(12345.0) == 12345

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown color"):
            color_to_colorref('NotAColor')

    def test_all_named_colors_valid(self):
        for name, expected in NAMED_COLORS.items():
            assert color_to_colorref(name) == expected


class TestColorEnum:
    def test_enum_member_count(self):
        assert len(list(Color)) == 40

    def test_enum_resolves_blue(self):
        assert color_to_colorref(Color.BLUE) == NAMED_COLORS['Blue']

    def test_enum_resolves_light_orange(self):
        assert color_to_colorref(Color.LIGHT_ORANGE) == NAMED_COLORS['Light Orange']

    def test_lowercase_string(self):
        assert color_to_colorref('blue') == NAMED_COLORS['Blue']

    def test_uppercase_string(self):
        assert color_to_colorref('BLUE') == NAMED_COLORS['Blue']

    def test_normalized_multi_word(self):
        # All forms should resolve to the same color
        ref = NAMED_COLORS['Light Orange']
        assert color_to_colorref('light_orange') == ref
        assert color_to_colorref('light orange') == ref
        assert color_to_colorref('light-orange') == ref
        assert color_to_colorref('Light Orange') == ref
        assert color_to_colorref('LIGHT ORANGE') == ref

    def test_normalized_blue_grey(self):
        ref = NAMED_COLORS['Blue-Grey']
        assert color_to_colorref(Color.BLUE_GREY) == ref
        assert color_to_colorref('blue_grey') == ref
        assert color_to_colorref('blue-grey') == ref
        assert color_to_colorref('Blue-Grey') == ref

    def test_int_passthrough(self):
        assert color_to_colorref(0xFF0000) == 0xFF0000

    def test_chart_with_enum_color(self):
        from anxwritter import ANXChart, Icon
        c = ANXChart()
        c.add_icon(id='A', type='Person', color=Color.BLUE)
        xml = c.to_xml()
        assert str(NAMED_COLORS['Blue']) in xml

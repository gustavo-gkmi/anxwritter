"""Tests for utility helpers: _is_valid_color, _validate_date, _validate_time, _enum_val."""

import pytest

from anxwritter.utils import (
    _enum_val,
    _is_valid_color,
    _validate_date,
    _validate_time,
)
from anxwritter.enums import DotStyle


class TestEnumVal:
    def test_none(self):
        assert _enum_val(None) == ''

    def test_enum(self):
        assert _enum_val(DotStyle.SOLID) == 'solid'

    def test_string(self):
        assert _enum_val('foo') == 'foo'

    def test_int(self):
        assert _enum_val(42) == '42'


class TestIsValidColor:
    def test_none_is_valid(self):
        assert _is_valid_color(None) is True

    def test_bool_rejected(self):
        # bool is a subclass of int — must reject
        assert _is_valid_color(True) is False
        assert _is_valid_color(False) is False

    def test_int_in_range(self):
        assert _is_valid_color(0) is True
        assert _is_valid_color(0xFFFFFF) is True
        assert _is_valid_color(12345) is True

    def test_int_out_of_range(self):
        assert _is_valid_color(-1) is False
        assert _is_valid_color(0x1000000) is False

    def test_named_color_title_case(self):
        assert _is_valid_color('Blue') is True

    def test_named_color_lowercase(self):
        # Case-insensitive bug fix
        assert _is_valid_color('blue') is True

    def test_named_color_uppercase(self):
        assert _is_valid_color('BLUE') is True

    def test_named_color_with_whitespace(self):
        assert _is_valid_color('  Blue  ') is True

    def test_named_color_multi_word(self):
        assert _is_valid_color('Light Orange') is True
        assert _is_valid_color('light orange') is True
        assert _is_valid_color('LIGHT ORANGE') is True

    def test_hex_with_hash(self):
        assert _is_valid_color('#FF0000') is True
        assert _is_valid_color('#ff0000') is True

    def test_hex_without_hash(self):
        # Falls through to color_to_colorref
        assert _is_valid_color('FF0000') is True

    def test_unknown_string(self):
        assert _is_valid_color('NotAColor') is False

    def test_list_rejected(self):
        assert _is_valid_color([1, 2, 3]) is False

    def test_dict_rejected(self):
        assert _is_valid_color({'r': 1}) is False

    def test_empty_string(self):
        assert _is_valid_color('') is False


class TestValidateDate:
    def test_canonical(self):
        assert _validate_date('2024-01-15') is True

    def test_dd_mm_yyyy(self):
        assert _validate_date('15/01/2024') is True

    def test_yyyymmdd_compact(self):
        assert _validate_date('20240115') is True

    def test_us_format_rejected(self):
        # '01/15/2024' is ambiguous; only dd/mm/yyyy supported.
        # 01/15/2024 fails because 15 is not a valid month under dd/mm/yyyy
        assert _validate_date('01/15/2024') is False

    def test_impossible_month(self):
        assert _validate_date('2024-13-01') is False

    def test_impossible_day(self):
        assert _validate_date('2024-02-30') is False

    def test_two_digit_year(self):
        assert _validate_date('24-01-15') is False

    def test_empty(self):
        assert _validate_date('') is False

    def test_non_string(self):
        assert _validate_date(20240115) is False
        assert _validate_date(None) is False


class TestValidateTime:
    def test_canonical(self):
        assert _validate_time('14:30:00') is True

    def test_midnight(self):
        assert _validate_time('00:00:00') is True

    def test_end_of_day(self):
        assert _validate_time('23:59:59') is True

    def test_microseconds(self):
        assert _validate_time('14:30:00.500') is True

    def test_no_seconds(self):
        # Phase 4: HH:MM accepted
        assert _validate_time('14:30') is True

    def test_12_hour(self):
        # Phase 4: 12-hour AM/PM accepted
        assert _validate_time('2:30 PM') is True

    def test_invalid_hour(self):
        assert _validate_time('24:00:00') is False

    def test_invalid_minute(self):
        assert _validate_time('14:60:00') is False

    def test_invalid_25(self):
        assert _validate_time('25:00:00') is False

    def test_non_string(self):
        assert _validate_time(143000) is False
        assert _validate_time(None) is False

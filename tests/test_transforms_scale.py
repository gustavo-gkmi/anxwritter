"""Unit tests for the styling scale / colour math (anxwritter/transforms.py,
anxwritter/colors.py).

These pure numeric functions were previously exercised only through full chart
builds. Testing them directly pins the scale curves, domain resolution, ramp
interpolation, and legend sampling before any refactor touches them.
"""

from __future__ import annotations

import math

import pytest

from anxwritter import (
    CategoricalCfg,
    CategoricalStyleCfg,
    IntensityCfg,
    IntensityWidthCfg,
    Link,
)
from anxwritter.colors import color_to_colorref, interpolate_ramp, lerp_rgb
from anxwritter.transforms import (
    _categorical_legend_rows,
    _diverging_t,
    _intensity_legend_rows,
    _invert_scale_t,
    _percentile,
    apply_scale,
    resolve_intensity_domain,
)


class TestPercentile:
    def test_empty(self):
        assert _percentile([], 50.0) == 0.0

    def test_single(self):
        assert _percentile([7.0], 50.0) == 7.0

    def test_midpoint_interpolates(self):
        assert _percentile([0.0, 10.0], 50.0) == 5.0


class TestResolveIntensityDomain:
    def test_empty_values(self):
        assert resolve_intensity_domain([], None) == (0.0, 1.0)

    def test_none_uses_min_max(self):
        assert resolve_intensity_domain([1.0, 2.0, 3.0], None) == (1.0, 3.0)

    def test_explicit_pair(self):
        assert resolve_intensity_domain([1.0, 2.0], [0, 10]) == (0.0, 10.0)

    def test_robust_percentiles(self):
        lo, hi = resolve_intensity_domain([float(i) for i in range(101)], "robust")
        assert lo == pytest.approx(5.0)
        assert hi == pytest.approx(95.0)

    def test_robust_collapse_falls_back_to_range(self):
        assert resolve_intensity_domain([5.0, 5.0, 5.0], "robust") == (5.0, 5.0)


class TestApplyScale:
    def test_degenerate_domain_returns_half(self):
        assert apply_scale(5.0, 10.0, 10.0, "linear") == 0.5

    def test_linear_midpoint(self):
        assert apply_scale(5.0, 0.0, 10.0, "linear") == 0.5

    def test_sqrt(self):
        assert apply_scale(2.5, 0.0, 10.0, "sqrt") == pytest.approx(0.5)

    def test_log_midpoint(self):
        assert apply_scale(10.0, 1.0, 100.0, "log") == pytest.approx(0.5)

    def test_power(self):
        assert apply_scale(5.0, 0.0, 10.0, "power", power=2.0) == pytest.approx(0.25)

    def test_quantile_median(self):
        sv = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert apply_scale(3.0, 1.0, 5.0, "quantile", sorted_vals=sv) == pytest.approx(0.5)

    def test_unknown_scale_is_zero(self):
        assert apply_scale(5.0, 0.0, 10.0, "bogus") == 0.0

    def test_final_clamp(self):
        assert apply_scale(99.0, 0.0, 10.0, "linear") == 1.0
        assert apply_scale(-99.0, 0.0, 10.0, "linear", clip=False) == 0.0


class TestDivergingT:
    def test_midpoint_is_half(self):
        assert _diverging_t(0.0, -10.0, 0.0, 10.0, True) == 0.5

    def test_low_end(self):
        assert _diverging_t(-10.0, -10.0, 0.0, 10.0, True) == 0.0

    def test_high_end(self):
        assert _diverging_t(10.0, -10.0, 0.0, 10.0, True) == 1.0

    def test_quarter_below_mid(self):
        assert _diverging_t(-5.0, -10.0, 0.0, 10.0, True) == pytest.approx(0.25)

    def test_clip_beyond_hi(self):
        assert _diverging_t(20.0, -10.0, 0.0, 10.0, True) == 1.0


class TestInvertScaleT:
    def test_linear(self):
        assert _invert_scale_t(0.5, 0.0, 10.0, "linear", 0.5, []) == pytest.approx(5.0)

    def test_sqrt_roundtrip(self):
        v = _invert_scale_t(0.5, 0.0, 10.0, "sqrt", 0.5, [])
        assert apply_scale(v, 0.0, 10.0, "sqrt") == pytest.approx(0.5)

    def test_log_roundtrip(self):
        v = _invert_scale_t(0.5, 1.0, 100.0, "log", 0.5, [])
        assert v == pytest.approx(10.0)

    def test_power_roundtrip(self):
        v = _invert_scale_t(0.5, 0.0, 10.0, "power", 2.0, [])
        assert apply_scale(v, 0.0, 10.0, "power", power=2.0) == pytest.approx(0.5)

    def test_quantile_picks_rank(self):
        sv = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _invert_scale_t(0.5, 1.0, 5.0, "quantile", 0.5, sv) == 3.0

    def test_degenerate_returns_lo(self):
        assert _invert_scale_t(0.5, 5.0, 5.0, "linear", 0.5, []) == 5.0


class TestInterpolateRamp:
    def test_endpoints_exact(self):
        assert interpolate_ramp([0x000000, 0xFFFFFF], 0.0) == 0x000000
        assert interpolate_ramp([0x000000, 0xFFFFFF], 1.0) == 0xFFFFFF

    def test_single_color(self):
        assert interpolate_ramp([0x123456], 0.5) == 0x123456

    def test_three_color_midpoint_is_middle_stop(self):
        assert interpolate_ramp([0x000000, 0x808080, 0xFFFFFF], 0.5) == 0x808080

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            interpolate_ramp([], 0.5)

    def test_rgb_space_naive_midpoint(self):
        # Naive sRGB midpoint of black/white is mid-grey.
        assert interpolate_ramp([0x000000, 0xFFFFFF], 0.5, "rgb") == 0x808080

    def test_rgb_linear_differs_from_naive(self):
        naive = interpolate_ramp([0x000000, 0xFFFFFF], 0.5, "rgb")
        gamma = interpolate_ramp([0x000000, 0xFFFFFF], 0.5, "rgb_linear")
        assert naive != gamma

    def test_lerp_rgb_endpoints(self):
        assert lerp_rgb(0x111111, 0x222222, 0.0) == 0x111111
        assert lerp_rgb(0x111111, 0x222222, 1.0) == 0x222222


class TestIntensityLegendRows:
    def test_width_rows_span_range_in_t_space(self):
        links = [
            Link("A", "B", attributes={"w": 0.0}),
            Link("A", "B", attributes={"w": 5.0}),
            Link("A", "B", attributes={"w": 10.0}),
        ]
        icfg = IntensityCfg(attribute="w", legend_count=3, width=IntensityWidthCfg(range=[2, 20]))
        rows = _intensity_legend_rows(icfg, links)
        assert [r["line_width"] for r in rows] == [2, 11, 20]
        assert all(r["item_type"] == "Line" for r in rows)
        assert rows[0]["name"] == "0" and rows[-1]["name"] == "10"

    def test_no_matching_values_returns_empty(self):
        icfg = IntensityCfg(attribute="missing", width=IntensityWidthCfg(range=[1, 5]))
        assert _intensity_legend_rows(icfg, [Link("A", "B", attributes={})]) == []


class TestCategoricalLegendRows:
    def test_one_row_per_style_in_order(self):
        ccfg = CategoricalCfg(
            attribute="role",
            styles={
                "Witness": CategoricalStyleCfg(line_color="Red", line_width=3),
                "Informant": CategoricalStyleCfg(line_color="Blue"),
            },
        )
        rows = _categorical_legend_rows(ccfg)
        assert [r["name"] for r in rows] == ["Witness", "Informant"]
        assert rows[0]["color"] == color_to_colorref("Red")
        assert rows[0]["line_width"] == 3
        assert rows[1]["line_width"] == 1  # default when unset

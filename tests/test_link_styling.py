"""Tests for ``extra_cfg.styling.links`` (intensity + categorical).

Covers:
- Each intensity scale's monotonicity and endpoint exactness.
- Color-space interpolation (rgb / rgb_linear / hsl), ramp evaluation.
- Categorical lookup with case- and accent-insensitive matching.
- Precedence: explicit > categorical > intensity > link_match_entity_color.
- Styling conflict detection (same attribute targeted twice).
- Legend auto-generation for both intensity and categorical.
- Back-compat: charts without a styling block emit unchanged XML.
"""
from __future__ import annotations

import math
import re

import pytest

from anxwritter import ANXChart, ANXValidationError, ErrorType
from anxwritter.colors import (
    color_to_colorref,
    interpolate_ramp,
    lerp_hsl,
    lerp_rgb,
    lerp_rgb_linear,
)
from anxwritter.transforms import (
    _diverging_t,
    apply_scale,
    resolve_intensity_domain,
)


# ── Scales ────────────────────────────────────────────────────────────────


class TestIntensityScales:
    @pytest.mark.parametrize("scale", ["linear", "log", "sqrt", "power", "quantile"])
    def test_endpoint_exactness(self, scale: str) -> None:
        sorted_vals = [1.0, 2.0, 5.0, 10.0, 100.0]
        kwargs = {"sorted_vals": sorted_vals} if scale == "quantile" else {}
        t_lo = apply_scale(1.0, 1.0, 100.0, scale, **kwargs)
        t_hi = apply_scale(100.0, 1.0, 100.0, scale, **kwargs)
        assert t_lo == pytest.approx(0.0, abs=1e-9), f"{scale}: lo→{t_lo}"
        assert t_hi == pytest.approx(1.0, abs=1e-9), f"{scale}: hi→{t_hi}"

    @pytest.mark.parametrize("scale", ["linear", "log", "sqrt"])
    def test_monotonicity(self, scale: str) -> None:
        vals = [1.0, 2.0, 5.0, 10.0, 50.0, 100.0]
        ts = [apply_scale(v, 1.0, 100.0, scale) for v in vals]
        for prev, cur in zip(ts, ts[1:]):
            assert prev <= cur, f"{scale} not monotonic: {ts}"

    def test_linear_midpoint(self) -> None:
        assert apply_scale(50.0, 0.0, 100.0, "linear") == pytest.approx(0.5)

    def test_log_midpoint(self) -> None:
        # log(10) is midway between log(1) and log(100)
        assert apply_scale(10.0, 1.0, 100.0, "log") == pytest.approx(0.5, abs=1e-6)

    def test_sqrt_midpoint(self) -> None:
        # sqrt(0.5) ≈ 0.7071 — high values compressed
        assert apply_scale(50.0, 0.0, 100.0, "sqrt") == pytest.approx(0.5 ** 0.5, abs=1e-6)

    def test_power_2_midpoint(self) -> None:
        # power(2) exaggerates high values: midway → 0.25
        assert apply_scale(50.0, 0.0, 100.0, "power", power=2.0) == pytest.approx(0.25)

    def test_power_equals_sqrt_when_k_is_half(self) -> None:
        a = apply_scale(50.0, 0.0, 100.0, "sqrt")
        b = apply_scale(50.0, 0.0, 100.0, "power", power=0.5)
        assert a == pytest.approx(b, abs=1e-9)

    def test_quantile_uses_ranks(self) -> None:
        # Four-value list: ranks 0, 1, 2, 3 → t in [0, 1/3, 2/3, 1]
        s = [1.0, 10.0, 100.0, 1000.0]
        t = apply_scale(10.0, 1.0, 1000.0, "quantile", sorted_vals=s)
        assert t == pytest.approx(1.0 / 3.0, abs=1e-9)

    def test_degenerate_domain_returns_midpoint(self) -> None:
        assert apply_scale(5.0, 5.0, 5.0, "linear") == pytest.approx(0.5)

    def test_clip_true_clamps_to_endpoints(self) -> None:
        assert apply_scale(150.0, 0.0, 100.0, "linear", clip=True) == pytest.approx(1.0)
        assert apply_scale(-50.0, 0.0, 100.0, "linear", clip=True) == pytest.approx(0.0)


class TestDomain:
    def test_auto_domain_uses_min_max(self) -> None:
        lo, hi = resolve_intensity_domain([1.0, 2.0, 3.0, 100.0], None)
        assert (lo, hi) == (1.0, 100.0)

    def test_explicit_domain_passes_through(self) -> None:
        lo, hi = resolve_intensity_domain([1.0, 1000.0], [0.0, 50.0])
        assert (lo, hi) == (0.0, 50.0)

    def test_robust_domain_excludes_outliers(self) -> None:
        # 5/95 percentile on a heavy-tail sample shouldn't be near 1000.
        lo, hi = resolve_intensity_domain([1.0, 2.0, 3.0, 4.0, 5.0, 1000.0], "robust")
        assert lo < 100, f"robust lo {lo} too high"
        assert hi < 1000, f"robust hi {hi} too high"

    def test_robust_falls_back_when_percentiles_collapse(self) -> None:
        lo, hi = resolve_intensity_domain([5.0, 5.0, 5.0, 5.0, 5.0], "robust")
        assert (lo, hi) == (5.0, 5.0)


class TestDiverging:
    def test_midpoint_maps_to_half(self) -> None:
        assert _diverging_t(0.0, -100.0, 0.0, 100.0, clip=True) == pytest.approx(0.5)

    def test_extremes(self) -> None:
        assert _diverging_t(-100.0, -100.0, 0.0, 100.0, clip=True) == pytest.approx(0.0)
        assert _diverging_t(100.0, -100.0, 0.0, 100.0, clip=True) == pytest.approx(1.0)

    def test_clip_clamps_to_extremes(self) -> None:
        assert _diverging_t(-200.0, -100.0, 0.0, 100.0, clip=True) == pytest.approx(0.0)
        assert _diverging_t(200.0, -100.0, 0.0, 100.0, clip=True) == pytest.approx(1.0)


# ── Color interpolation ──────────────────────────────────────────────────


class TestColorInterpolation:
    @pytest.mark.parametrize("lerp_fn", [lerp_rgb, lerp_rgb_linear, lerp_hsl])
    def test_endpoint_exactness(self, lerp_fn) -> None:
        red = color_to_colorref("Red")
        blue = color_to_colorref("Blue")
        assert lerp_fn(red, blue, 0.0) == red
        assert lerp_fn(red, blue, 1.0) == blue

    def test_naive_rgb_midpoint(self) -> None:
        # Naive midpoint of FF0000 and 0000FF is (128, 0, 128) — dark muddy purple.
        red = color_to_colorref("Red")
        blue = color_to_colorref("Blue")
        mid = lerp_rgb(red, blue, 0.5)
        r = mid & 0xFF
        g = (mid >> 8) & 0xFF
        b = (mid >> 16) & 0xFF
        assert (r, g, b) == (128, 0, 128)

    def test_rgb_linear_midpoint_brighter_than_naive(self) -> None:
        # Gamma-correct midpoint pulls toward ~(187, 0, 187) — visibly brighter.
        red = color_to_colorref("Red")
        blue = color_to_colorref("Blue")
        mid = lerp_rgb_linear(red, blue, 0.5)
        r = mid & 0xFF
        g = (mid >> 8) & 0xFF
        b = (mid >> 16) & 0xFF
        assert 180 <= r <= 195, f"r={r}"
        assert g == 0
        assert 180 <= b <= 195, f"b={b}"

    def test_three_stop_ramp_midpoint_returns_middle_color(self) -> None:
        red = color_to_colorref("Red")
        yellow = color_to_colorref("Yellow")
        blue = color_to_colorref("Blue")
        mid = interpolate_ramp([red, yellow, blue], 0.5, "rgb_linear")
        assert mid == yellow

    def test_ramp_endpoints_byte_identical(self) -> None:
        red = color_to_colorref("Red")
        green = color_to_colorref("Green")
        blue = color_to_colorref("Blue")
        ramp = [red, green, blue]
        assert interpolate_ramp(ramp, 0.0, "rgb_linear") == red
        assert interpolate_ramp(ramp, 1.0, "rgb_linear") == blue

    def test_ramp_clamps_out_of_range_t(self) -> None:
        red = color_to_colorref("Red")
        blue = color_to_colorref("Blue")
        assert interpolate_ramp([red, blue], -0.5, "rgb_linear") == red
        assert interpolate_ramp([red, blue], 1.5, "rgb_linear") == blue

    def test_hsl_lerp_pure_hue(self) -> None:
        # Red → Blue through HSL takes the short hue arc → magenta midpoint.
        red = color_to_colorref("Red")
        blue = color_to_colorref("Blue")
        mid = lerp_hsl(red, blue, 0.5)
        r = mid & 0xFF
        b = (mid >> 16) & 0xFF
        g = (mid >> 8) & 0xFF
        # Pure magenta on a hue-only lerp at midway: r=255, g=0, b=255.
        assert (r, g, b) == (255, 0, 255)


# ── End-to-end intensity / categorical ───────────────────────────────────


def _make_chart(styling: dict, links: list, **kw) -> ANXChart:
    """Construct a minimal chart with the given styling block and link list."""
    chart = ANXChart(settings={"extra_cfg": {"styling": styling, **kw.get("extra_cfg", {})}})
    seen = set()
    for link in links:
        for end in (link["from_id"], link["to_id"]):
            if end not in seen:
                chart.add_icon(id=end, type="Person")
                seen.add(end)
        chart.add_link(**link)
    return chart


def _xml_line_widths(xml: str) -> list:
    return [int(w) for w in re.findall(r"<LinkStyle[^>]*LineWidth=\"(\d+)\"", xml)]


def _xml_line_colors(xml: str) -> list:
    return [int(c) for c in re.findall(r"<LinkStyle[^>]*LineColour=\"(\d+)\"", xml)]


class TestIntensityEndToEnd:
    def test_linear_width_mapping(self) -> None:
        chart = _make_chart(
            {"links": {"intensity": {
                "attribute": "amount", "scale": "linear",
                "width": {"range": [1, 10]},
            }}},
            [
                {"from_id": "A", "to_id": "B", "type": "Call", "attributes": {"amount": 0}},
                {"from_id": "A", "to_id": "B", "type": "Call", "attributes": {"amount": 50}},
                {"from_id": "A", "to_id": "B", "type": "Call", "attributes": {"amount": 100}},
            ],
        )
        widths = _xml_line_widths(chart.to_xml())
        # Width=1 is omitted by the builder; expect 6 (midway) and 10 (max).
        assert 10 in widths
        assert 6 in widths or 5 in widths

    def test_log_scale_validates_positive(self) -> None:
        chart = _make_chart(
            {"links": {"intensity": {
                "attribute": "amount", "scale": "log",
                "width": {"range": [1, 10]},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"amount": 0}}],
        )
        errs = chart.validate()
        assert any(e["type"] == ErrorType.INVALID_INTENSITY_DOMAIN.value for e in errs)

    def test_log_scale_with_positive_values(self) -> None:
        chart = _make_chart(
            {"links": {"intensity": {
                "attribute": "amount", "scale": "log",
                "width": {"range": [1, 10]},
            }}},
            [
                {"from_id": "A", "to_id": "B", "type": "Call",
                 "attributes": {"amount": 1}},
                {"from_id": "A", "to_id": "B", "type": "Call",
                 "attributes": {"amount": 100}},
            ],
        )
        assert chart.validate() == []
        xml = chart.to_xml()
        widths = _xml_line_widths(xml)
        # Lo→1 (omitted), Hi→10. Hi must be present.
        assert 10 in widths

    def test_color_ramp_mapping(self) -> None:
        chart = _make_chart(
            {"links": {"intensity": {
                "attribute": "amount",
                "color": {"ramp": ["Light Yellow", "Red"]},
            }}},
            [
                {"from_id": "A", "to_id": "B", "type": "Call",
                 "attributes": {"amount": 0}},
                {"from_id": "A", "to_id": "B", "type": "Call",
                 "attributes": {"amount": 100}},
            ],
        )
        xml = chart.to_xml()
        colors = _xml_line_colors(xml)
        assert color_to_colorref("Red") in colors  # max → end of ramp

    def test_missing_attribute_falls_through(self) -> None:
        chart = _make_chart(
            {"links": {"intensity": {
                "attribute": "amount",
                "width": {"range": [1, 10]},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call"}],
        )
        xml = chart.to_xml()
        # No width attribute or default — emitted XML should not crash, link width = 1 (omitted).
        assert _xml_line_widths(xml) == []

    def test_explicit_line_width_wins_over_intensity(self) -> None:
        chart = _make_chart(
            {"links": {"intensity": {
                "attribute": "amount",
                "width": {"range": [1, 10]},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"amount": 100}, "line_width": 7}],
        )
        assert _xml_line_widths(chart.to_xml()) == [7]


class TestCategoricalEndToEnd:
    def test_basic_lookup(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Witness": {"line_color": "Green", "line_width": 2}},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"src": "Witness"}}],
        )
        xml = chart.to_xml()
        assert _xml_line_colors(xml) == [color_to_colorref("Green")]
        assert _xml_line_widths(xml) == [2]

    def test_case_insensitive_by_default(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Witness": {"line_color": "Green"}},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"src": "WITNESS"}}],
        )
        assert _xml_line_colors(chart.to_xml()) == [color_to_colorref("Green")]

    def test_case_sensitive_opt_in(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src", "case_sensitive": True,
                "styles": {"Witness": {"line_color": "Green"}},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"src": "WITNESS"}}],
        )
        # Case-sensitive: WITNESS doesn't match Witness → no color attribute emitted.
        assert _xml_line_colors(chart.to_xml()) == []

    def test_accent_insensitive_by_default(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Testemunha": {"line_color": "Green"}},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"src": "Tëstémuñha"}}],
        )
        assert _xml_line_colors(chart.to_xml()) == [color_to_colorref("Green")]

    def test_default_fallback_for_unmatched(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Witness": {"line_color": "Green"}},
                "default": {"line_color": "Grey"},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"src": "Unknown"}}],
        )
        assert _xml_line_colors(chart.to_xml()) == [color_to_colorref("Grey")]

    def test_missing_error_policy_surfaces_at_validate(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src", "missing": "error",
                "styles": {"Witness": {"line_color": "Green"}},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call"}],
        )
        errs = chart.validate()
        assert any(e["type"] == ErrorType.INVALID_CATEGORICAL_ATTRIBUTE.value for e in errs)

    def test_explicit_line_color_wins(self) -> None:
        chart = _make_chart(
            {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Witness": {"line_color": "Green"}},
            }}},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "line_color": "Blue", "attributes": {"src": "Witness"}}],
        )
        assert _xml_line_colors(chart.to_xml()) == [color_to_colorref("Blue")]


# ── Precedence ────────────────────────────────────────────────────────────


class TestPrecedence:
    def test_categorical_overrides_intensity(self) -> None:
        # Both target different attributes; both match this link. Categorical wins.
        chart = _make_chart(
            {"links": {
                "intensity": {
                    "attribute": "amount",
                    "color": {"ramp": ["Light Yellow", "Red"]},
                },
                "categorical": {
                    "attribute": "src",
                    "styles": {"Witness": {"line_color": "Blue"}},
                },
            }},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"amount": 100, "src": "Witness"}}],
        )
        assert _xml_line_colors(chart.to_xml()) == [color_to_colorref("Blue")]

    def test_intensity_overrides_link_match_entity_color(self) -> None:
        chart = ANXChart(settings={
            "extra_cfg": {
                "link_match_entity_color": True,
                "styling": {"links": {"intensity": {
                    "attribute": "amount", "scale": "linear",
                    "color": {"ramp": ["Light Yellow", "Red"]},
                }}},
            },
        })
        chart.add_icon(id="A", type="Person", color="Green")
        chart.add_icon(id="B", type="Person", color="Yellow")
        # Two links spanning the domain — the max-amount link maps to ramp end.
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"amount": 0})
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"amount": 100})
        xml = chart.to_xml()
        colors = _xml_line_colors(xml)
        # The max-amount link must be Red (intensity won over match_entity_color
        # which would have set it to Yellow = B's color).
        assert color_to_colorref("Red") in colors
        assert color_to_colorref("Yellow") not in colors

    def test_explicit_overrides_everything(self) -> None:
        chart = ANXChart(settings={
            "extra_cfg": {
                "link_match_entity_color": True,
                "styling": {"links": {
                    "intensity": {"attribute": "amount", "color": {"ramp": ["Light Yellow", "Red"]}},
                    "categorical": {"attribute": "src", "styles": {"Witness": {"line_color": "Green"}}},
                }},
            },
        })
        chart.add_icon(id="A", type="Person", color="Yellow")
        chart.add_icon(id="B", type="Person", color="Pink")
        chart.add_link(from_id="A", to_id="B", type="Call",
                       line_color="Black", line_width=9,
                       attributes={"amount": 100, "src": "Witness"})
        xml = chart.to_xml()
        # line_color was set to Black explicitly → 0 → omitted by builder. line_width=9 emitted.
        assert _xml_line_widths(xml) == [9]


# ── Validation conflict ──────────────────────────────────────────────────


class TestStylingConflict:
    def test_same_attribute_conflict(self) -> None:
        chart = _make_chart(
            {"links": {
                "intensity": {"attribute": "risk", "width": {"range": [1, 5]}},
                "categorical": {"attribute": "risk", "styles": {"high": {"line_color": "Red"}}},
            }},
            [{"from_id": "A", "to_id": "B", "type": "Call",
              "attributes": {"risk": 1}}],
        )
        errs = chart.validate()
        assert any(e["type"] == ErrorType.STYLING_CONFLICT.value for e in errs)


# ── Legend auto-generation ───────────────────────────────────────────────


class TestLegendAutoGen:
    def test_categorical_emits_one_row_per_entry(self) -> None:
        chart = ANXChart(settings={
            "extra_cfg": {"styling": {"links": {"categorical": {
                "attribute": "src",
                "styles": {
                    "Witness": {"line_color": "Green", "line_width": 2},
                    "Informant": {"line_color": "Orange"},
                },
                "legend": True,
            }}}},
            "legend_cfg": {"show": True},
        })
        chart.add_icon(id="A", type="P")
        chart.add_icon(id="B", type="P")
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"src": "Witness"})
        xml = chart.to_xml()
        labels = re.findall(r"<LegendItem [^>]*Label=\"([^\"]+)\"", xml)
        assert labels == ["Witness", "Informant"]

    def test_intensity_emits_n_rows(self) -> None:
        chart = ANXChart(settings={
            "extra_cfg": {"styling": {"links": {"intensity": {
                "attribute": "amount", "scale": "linear",
                "width": {"range": [1, 10]},
                "legend": True, "legend_count": 4,
            }}}},
            "legend_cfg": {"show": True},
        })
        chart.add_icon(id="A", type="P")
        chart.add_icon(id="B", type="P")
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"amount": 10})
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"amount": 100})
        xml = chart.to_xml()
        labels = re.findall(r"<LegendItem [^>]*Label=\"([^\"]+)\"", xml)
        assert len(labels) == 4
        # Linear domain [10, 100] sampled at t=0, 1/3, 2/3, 1
        # → 10, 40, 70, 100
        assert labels[0] == "10"
        assert labels[-1] == "100"

    def test_intensity_legend_uses_declared_format(self) -> None:
        # End-to-end: AC prefix/decimals + Brazilian separators → readable
        # labels, no scientific notation on large values.
        chart = ANXChart(settings={
            "extra_cfg": {"styling": {"links": {"intensity": {
                "attribute": "amount", "scale": "linear",
                "decimal_separator": ",", "thousand_separator": ".",
                "width": {"range": [1, 10]},
                "legend": True, "legend_count": 2,
            }}}},
            "legend_cfg": {"show": True},
        })
        chart.add_attribute_class(name="amount", type="number",
                                  prefix="R$ ", decimal_places=2)
        chart.add_icon(id="A", type="P")
        chart.add_icon(id="B", type="P")
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"amount": 0})
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"amount": 507123.40})
        xml = chart.to_xml()
        labels = re.findall(r"<LegendItem [^>]*Label=\"([^\"]+)\"", xml)
        assert not any("e+" in lbl.lower() for lbl in labels)
        assert labels[-1] == "R$ 507.123,40"

    def test_no_legend_when_flag_unset(self) -> None:
        chart = ANXChart(settings={
            "extra_cfg": {"styling": {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Witness": {"line_color": "Green"}},
                # no 'legend' field — defaults to None → no auto-gen
            }}}},
        })
        chart.add_icon(id="A", type="P")
        chart.add_icon(id="B", type="P")
        chart.add_link(from_id="A", to_id="B", type="Call",
                       attributes={"src": "Witness"})
        xml = chart.to_xml()
        assert "<LegendItem" not in xml


# ── Back-compat guardrails ───────────────────────────────────────────────


class TestNoStylingBackcompat:
    def test_empty_chart_unchanged(self) -> None:
        # Chart with no styling block builds and validates cleanly.
        chart = ANXChart()
        chart.add_icon(id="A", type="P")
        chart.add_icon(id="B", type="P")
        chart.add_link(from_id="A", to_id="B", type="Call")
        assert chart.validate() == []
        xml = chart.to_xml()
        assert "<LinkStyle" in xml

    def test_link_match_entity_color_still_works(self) -> None:
        # Existing extra_cfg.link_match_entity_color must still apply when no
        # styling overrides it (lowest-precedence dynamic source).
        chart = ANXChart(settings={"extra_cfg": {"link_match_entity_color": True}})
        chart.add_icon(id="A", type="Person", color="Green")
        chart.add_icon(id="B", type="Person", color="Yellow")
        chart.add_link(from_id="A", to_id="B", type="Call")
        xml = chart.to_xml()
        # Link should inherit B's color (Yellow).
        assert _xml_line_colors(xml) == [color_to_colorref("Yellow")]

    def test_empty_styling_is_no_op(self) -> None:
        # An empty styling block (no intensity, no categorical) must be a no-op,
        # not a validation error.
        chart = ANXChart(settings={"extra_cfg": {"styling": {"links": {}}}})
        chart.add_icon(id="A", type="P")
        chart.add_icon(id="B", type="P")
        chart.add_link(from_id="A", to_id="B", type="Call")
        assert chart.validate() == []
        # XML still builds.
        xml = chart.to_xml()
        assert "<LinkStyle" in xml


# ── YAML path equivalence (light smoke test; FULL_SPEC covers the heavy work) ─


class TestYamlPathEquivalence:
    def test_yaml_and_dict_produce_same_styling(self) -> None:
        spec = {
            "settings": {"extra_cfg": {"styling": {"links": {"categorical": {
                "attribute": "src",
                "styles": {"Witness": {"line_color": "Green", "line_width": 2}},
            }}}}},
            "entities": {"icons": [
                {"id": "A", "type": "P"},
                {"id": "B", "type": "P"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"src": "Witness"}}],
        }
        c_dict = ANXChart.from_dict(spec)
        import yaml
        c_yaml = ANXChart.from_yaml(yaml.safe_dump(spec))
        assert c_dict.to_xml() == c_yaml.to_xml()

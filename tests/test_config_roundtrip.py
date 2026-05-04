"""Config round-trip idempotence tests.

Proves that ``from_config -> to_config_dict`` is a fixed point, multi-cycle
stable, and survives YAML file serialization without structural drift.

See plans/cheerful-soaring-oasis-followups.md Plan B for rationale.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict

import pytest
import yaml

from anxwritter import ANXChart

from tests.fixtures import equivalence_specs as specs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _config_only(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Strip entities/links from a spec to get a pure config dict."""
    return {k: copy.deepcopy(v) for k, v in spec.items() if k not in ("entities", "links")}


FULL_CONFIG_SPEC = _config_only(specs.FULL_SPEC)


def _strip_none_recursive(obj: Any) -> Any:
    """Recursively drop keys whose values are None, and drop empty dicts."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if v is None:
                continue
            cleaned = _strip_none_recursive(v)
            if cleaned == {} or cleaned == []:
                continue
            out[k] = cleaned
        return out
    if isinstance(obj, list):
        return [_strip_none_recursive(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Core idempotence
# ---------------------------------------------------------------------------

class TestConfigRoundtrip:
    def test_single_cycle_idempotent_after_strip(self):
        """After None-stripping, the input config equals the exported config.

        ``to_config_dict`` doesn't recursively None-strip nested dataclass
        fields (e.g. the ``font`` sub-dict on AttributeClass), so the raw
        output contains keys the input didn't. Once both sides are
        None-stripped they must match.
        """
        chart = ANXChart(config=copy.deepcopy(FULL_CONFIG_SPEC))
        out = chart.to_config_dict()
        assert _strip_none_recursive(FULL_CONFIG_SPEC) == _strip_none_recursive(out)

    def test_multi_cycle_stable(self):
        """Second cycle must produce exactly what the first cycle produced."""
        chart1 = ANXChart(config=copy.deepcopy(FULL_CONFIG_SPEC))
        out1 = chart1.to_config_dict()

        chart2 = ANXChart(config=copy.deepcopy(out1))
        out2 = chart2.to_config_dict()

        assert out1 == out2, "second round-trip cycle diverged — not a fixed point"

    def test_three_cycle_stable(self):
        chart1 = ANXChart(config=copy.deepcopy(FULL_CONFIG_SPEC))
        out1 = chart1.to_config_dict()
        chart2 = ANXChart(config=copy.deepcopy(out1))
        out2 = chart2.to_config_dict()
        chart3 = ANXChart(config=copy.deepcopy(out2))
        out3 = chart3.to_config_dict()
        assert out2 == out3

    def test_yaml_file_roundtrip(self, tmp_path):
        """to_config(yaml) + from_config_file produce equivalent charts."""
        chart1 = ANXChart(config=copy.deepcopy(FULL_CONFIG_SPEC))
        path = tmp_path / "cfg.yaml"
        chart1.to_config(str(path))

        chart2 = ANXChart.from_config_file(str(path))
        assert chart1.to_config_dict() == chart2.to_config_dict()

    def test_json_file_roundtrip(self, tmp_path):
        """Same as YAML test but for JSON file extension."""
        chart1 = ANXChart(config=copy.deepcopy(FULL_CONFIG_SPEC))
        path = tmp_path / "cfg.json"
        chart1.to_config(str(path))

        chart2 = ANXChart.from_config_file(str(path))
        assert chart1.to_config_dict() == chart2.to_config_dict()


# ---------------------------------------------------------------------------
# Known-tricky cases
# ---------------------------------------------------------------------------

class TestKnownTrickyCases:
    def test_default_strength_not_exported(self):
        """Pre-populated ``Default`` strength must not leak into the export."""
        chart = ANXChart()  # only has pre-populated Default
        out = chart.to_config_dict()
        assert "strengths" not in out, (
            f"empty chart exported strengths section: {out.get('strengths')}"
        )

    def test_default_strength_stripped_alongside_custom(self):
        """Custom strengths are exported but the pre-populated Default is not."""
        chart = ANXChart(
            config={
                "strengths": {
                    "items": [
                        {"name": "Confirmed", "dot_style": "solid"},
                        {"name": "Tentative", "dot_style": "dashed"},
                    ]
                }
            }
        )
        out = chart.to_config_dict()
        names = [s["name"] for s in out["strengths"]["items"]]
        assert "Default" not in names, f"Default leaked into export: {names}"
        assert set(names) == {"Confirmed", "Tentative"}

    def test_strengths_export_shape_is_dict(self):
        """to_config_dict must emit strengths as {items: [...]} even without default.

        A plain list is not accepted by _apply_config — this was a real bug
        fixed alongside this test: see the ``strengths`` branch of
        to_config_dict in chart.py.
        """
        chart = ANXChart(
            config={"strengths": {"items": [{"name": "X", "dot_style": "solid"}]}}
        )
        out = chart.to_config_dict()
        assert isinstance(out["strengths"], dict)
        assert "items" in out["strengths"]
        # And crucially: this shape round-trips back through apply_config
        chart2 = ANXChart(config=out)
        names = [s.name for s in chart2.strengths.items]
        assert "X" in names

    def test_grade_sentinel_not_in_config_export(self):
        """The '-' sentinel appended at build time must NOT appear in config export.

        When ``grades_one.default`` is None, anxwritter appends a '-' sentinel
        at build time so every item has a deterministic grade. That sentinel
        is a *build artifact*, not a user-provided config value — exporting
        it would cause it to be re-appended on the next build (double
        sentinel).
        """
        chart = ANXChart(config={"grades_one": {"items": ["Reliable", "Unreliable"]}})
        out = chart.to_config_dict()
        items = out["grades_one"]["items"]
        assert "-" not in items, f"sentinel leaked into grade export: {items}"
        assert items == ["Reliable", "Unreliable"]

    def test_auto_palette_not_exported(self):
        """When no palettes are user-defined, the auto palette must not be exported."""
        chart = ANXChart(
            config={
                "entity_types": [{"name": "Person", "icon_file": "person"}],
            }
        )
        out = chart.to_config_dict()
        assert "palettes" not in out, (
            f"auto-generated palette leaked into export: {out.get('palettes')}"
        )

    def test_user_palette_is_exported(self):
        """An explicitly-added palette must survive the round-trip."""
        chart = ANXChart(
            config={
                "entity_types": [{"name": "Person", "icon_file": "person"}],
                "palettes": [
                    {
                        "name": "Investigation",
                        "entity_types": ["Person"],
                    }
                ],
            }
        )
        out = chart.to_config_dict()
        assert "palettes" in out
        assert out["palettes"][0]["name"] == "Investigation"
        assert out["palettes"][0]["entity_types"] == ["Person"]

    def test_settings_none_stripped(self):
        """Only explicitly-set Settings fields appear in the export."""
        chart = ANXChart(
            config={"settings": {"chart": {"bg_color": 8421504}}}
        )
        out = chart.to_config_dict()
        assert out["settings"] == {"chart": {"bg_color": 8421504}}, (
            f"Settings export leaked None/default fields: {out['settings']}"
        )

    def test_empty_chart_exports_empty_config(self):
        """A pristine ANXChart() must export an empty config dict.

        This is the strongest idempotence check: if the default chart emits
        anything, that 'anything' gets re-applied to itself on load — which
        may or may not be a fixed point.
        """
        chart = ANXChart()
        out = chart.to_config_dict()
        assert out == {}, f"empty chart exported: {out}"


# ---------------------------------------------------------------------------
# Per-section round-trip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "section_name,section_value",
    [
        ("entity_types", [{"name": "Person", "icon_file": "person", "color": "Blue"}]),
        ("link_types", [{"name": "Call", "color": 255}]),
        (
            "attribute_classes",
            [{"name": "phone", "type": "Text", "prefix": "Tel: "}],
        ),
        ("source_types", ["Witness", "Informant"]),
        (
            "grades_one",
            {"default": "Reliable", "items": ["Reliable", "Unreliable"]},
        ),
        (
            "grades_two",
            {"items": ["Confirmed", "Probable"]},
        ),
    ],
)
class TestPerSectionRoundtrip:
    """Each config section round-trips independently.

    Catches cases where a single section's export/import shape mismatch is
    masked by the full-spec test because a different section soaks up the
    drift.
    """

    def test_single_section_idempotent(self, section_name, section_value):
        cfg = {section_name: section_value}
        chart1 = ANXChart(config=copy.deepcopy(cfg))
        out1 = chart1.to_config_dict()
        chart2 = ANXChart(config=copy.deepcopy(out1))
        out2 = chart2.to_config_dict()
        assert out1 == out2, (
            f"section {section_name!r} diverged on second cycle.\n"
            f"  out1: {out1}\n  out2: {out2}"
        )


# ---------------------------------------------------------------------------
# Sanity: idempotence comparator actually detects drift
# ---------------------------------------------------------------------------

class TestRoundtripSanity:
    def test_mutated_dict_not_equal(self):
        """Ensure equality comparison isn't accidentally always True."""
        chart = ANXChart(config=copy.deepcopy(FULL_CONFIG_SPEC))
        out = chart.to_config_dict()
        mutated = copy.deepcopy(out)
        mutated["settings"]["chart"]["bg_color"] = 999999
        assert out != mutated

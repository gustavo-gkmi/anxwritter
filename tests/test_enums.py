"""Tests for new enums: LegendItemType, Color."""

import pytest

from anxwritter import (
    ANXChart,
    LegendItem,
    LegendItemType,
)
from anxwritter.colors import NAMED_COLORS


# ── LegendItemType ───────────────────────────────────────────────────────────


class TestLegendItemType:
    def test_enum_instance_builds(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_legend_item(LegendItem(name='X', item_type=LegendItemType.ICON))
        assert not c.validate()
        c.to_xml()  # smoke

    def test_lowercase_string_builds(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_legend_item(LegendItem(name='X', item_type='icon'))
        assert not c.validate()
        c.to_xml()

    def test_legacy_title_case_builds(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_legend_item(LegendItem(name='X', item_type='Icon'))
        assert not c.validate()
        c.to_xml()

    def test_uppercase_builds(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_legend_item(LegendItem(name='X', item_type='ICON'))
        assert not c.validate()
        c.to_xml()

    def test_nonsense_rejected(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_legend_item(LegendItem(name='X', item_type='nonsense'))
        errors = c.validate()
        assert any(e['type'] == 'invalid_legend_type' for e in errors)

    def test_all_enum_values(self):
        for et in LegendItemType:
            c = ANXChart(settings={'legend_cfg': {'show': True}})
            c.add_legend_item(LegendItem(name='X', item_type=et))
            assert not c.validate(), f"failed for {et}"

"""Tests for the Settings dataclass: defaults, dict construction, merging."""

from anxwritter import ANXChart, Settings, ChartCfg, ExtraCfg


class TestDefaults:
    def test_empty_settings_by_default(self):
        c = ANXChart()
        assert isinstance(c.settings, Settings)
        # All groups present, all fields None / empty
        assert c.settings.chart.bg_color is None
        assert c.settings.font.name is None
        assert c.settings.legend_cfg.show is None
        assert c.settings.legend_cfg.font.name is None
        assert c.settings.summary.custom_properties == []

    def test_dict_constructor(self):
        c = ANXChart(settings={'extra_cfg': {'arrange': 'grid'}})
        assert c.settings.extra_cfg.arrange == 'grid'

    def test_settings_constructor(self):
        s = Settings(chart=ChartCfg(bg_color=8421504))
        c = ANXChart(settings=s)
        assert c.settings.chart.bg_color == 8421504


class TestOverride:
    def test_single_override(self):
        c = ANXChart(settings={'extra_cfg': {'arrange': 'grid'}})
        assert c.settings.extra_cfg.arrange == 'grid'

    def test_multiple_overrides(self):
        c = ANXChart(settings={
            'extra_cfg': {'arrange': 'grid', 'entity_auto_color': True},
        })
        assert c.settings.extra_cfg.arrange == 'grid'
        assert c.settings.extra_cfg.entity_auto_color is True

    def test_unknown_group_raises(self):
        import pytest
        with pytest.raises(TypeError, match="Unknown settings group"):
            ANXChart(settings={'bogus_group': {}})

    def test_unknown_field_raises(self):
        import pytest
        with pytest.raises(TypeError):
            ANXChart(settings={'chart': {'bogus_field': 1}})


class TestSettingsMutation:
    def test_modify_after_construction(self):
        c = ANXChart()
        c.settings.extra_cfg.arrange = 'grid'
        assert c.settings.extra_cfg.arrange == 'grid'

    def test_independent_instances(self):
        c1 = ANXChart(settings={'extra_cfg': {'arrange': 'grid'}})
        c2 = ANXChart()
        assert c1.settings.extra_cfg.arrange == 'grid'
        assert c2.settings.extra_cfg.arrange is None

"""Tests for config file loading, merging, conflict detection, and export."""

import json
import os
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

from anxwritter import ANXChart, AttributeClass, Strength, LegendItem, EntityType, LinkType
from anxwritter.enums import DotStyle


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    'settings': {'extra_cfg': {'arrange': 'grid', 'entity_auto_color': True}},
    'entity_types': [
        {'name': 'Person', 'icon_file': 'person', 'color': 'Blue'},
        {'name': 'Vehicle', 'icon_file': 'vehicle'},
    ],
    'link_types': [
        {'name': 'Call', 'color': 255},
    ],
    'attribute_classes': [
        {'name': 'Phone', 'type': 'Text', 'prefix': 'Tel: '},
        {'name': 'Balance', 'type': 'Number', 'prefix': 'R$ ', 'decimal_places': 2},
    ],
    'strengths': {
        'items': [
            {'name': 'Confirmed', 'dot_style': 'DotStyleSolid'},
            {'name': 'Tentative', 'dot_style': 'DotStyleDashed'},
        ],
    },
    'grades_one': {'items': ['Always reliable', 'Usually reliable']},
    'grades_two': {'items': ['Confirmed', 'Probably true']},
    'grades_three': {'items': ['High', 'Medium', 'Low']},
    'source_types': ['Discovery', 'Informant'],
    'legend_items': [
        {'name': 'Person', 'item_type': 'Icon'},
    ],
}

SAMPLE_DATA = {
    'settings': {'extra_cfg': {'arrange': 'circle'}, 'grid': {'snap': True}},
    'entities': {
        'icons': [
            {'id': 'Alice', 'type': 'Person'},
            {'id': 'Bob', 'type': 'Person'},
        ],
    },
    'links': [
        {'from_id': 'Alice', 'to_id': 'Bob', 'type': 'Call'},
    ],
}


def _write_json(data, suffix='.json'):
    """Write data to a temp JSON file. Returns path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    return path


def _write_yaml(data, suffix='.yaml'):
    """Write data to a temp YAML file. Returns path."""
    import yaml
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
    return path


# ── Config loading ────────────────────────────────────────────────────────────

class TestConfigLoading:

    def test_from_config_file_json(self):
        path = _write_json(SAMPLE_CONFIG)
        try:
            chart = ANXChart.from_config_file(path)
            assert chart.settings.extra_cfg.arrange == 'grid'
            assert chart.settings.extra_cfg.entity_auto_color is True
            assert len(chart._entity_types) == 2
            assert len(chart._link_types) == 1
            assert len(chart._attribute_classes) == 2
            assert chart.grades_one.items == ['Always reliable', 'Usually reliable']
            assert chart.grades_two.items == ['Confirmed', 'Probably true']
            assert chart.grades_three.items == ['High', 'Medium', 'Low']
            assert chart.source_types == ['Discovery', 'Informant']
            assert len(chart._legend_items) == 1
            assert chart._has_config is True
        finally:
            os.unlink(path)

    def test_from_config_file_yaml(self):
        path = _write_yaml(SAMPLE_CONFIG)
        try:
            chart = ANXChart.from_config_file(path)
            assert chart.settings.extra_cfg.arrange == 'grid'
            assert len(chart._entity_types) == 2
            assert chart._has_config is True
        finally:
            os.unlink(path)

    def test_from_config_string_json(self):
        chart = ANXChart.from_config(json.dumps(SAMPLE_CONFIG))
        assert chart.settings.extra_cfg.arrange == 'grid'
        assert len(chart._entity_types) == 2

    def test_from_config_string_yaml(self):
        import yaml
        chart = ANXChart.from_config(yaml.dump(SAMPLE_CONFIG))
        assert chart.settings.extra_cfg.arrange == 'grid'
        assert len(chart._entity_types) == 2

    def test_config_ignores_entities_and_links(self):
        config_with_data = dict(SAMPLE_CONFIG)
        config_with_data['entities'] = {'icons': [{'id': 'X', 'type': 'Person'}]}
        config_with_data['links'] = [{'from_id': 'X', 'to_id': 'Y', 'type': 'Call'}]
        chart = ANXChart()
        chart.apply_config(config_with_data)
        assert len(chart._entities) == 0
        assert len(chart._links) == 0
        assert chart._has_config is True

    def test_init_config_file_param(self):
        path = _write_json(SAMPLE_CONFIG)
        try:
            chart = ANXChart(config_file=path)
            assert chart.settings.extra_cfg.arrange == 'grid'
            assert chart._has_config is True
        finally:
            os.unlink(path)

    def test_init_config_dict_param(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        assert chart.settings.extra_cfg.arrange == 'grid'
        assert chart._has_config is True


# ── Merge semantics ───────────────────────────────────────────────────────────

class TestMergeSemantics:

    def test_settings_data_wins(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        chart._apply_data(SAMPLE_DATA)
        # data overrides config's 'arrange'
        assert chart.settings.extra_cfg.arrange == 'circle'
        # config's 'entity_auto_color' survives
        assert chart.settings.extra_cfg.entity_auto_color is True
        # data adds 'grid.snap'
        assert chart.settings.grid.snap is True

    def test_apply_config_layered(self):
        config1 = {
            'entity_types': [
                {'name': 'Person', 'color': 'Blue'},
            ],
            'grades_one': {'items': ['A', 'B']},
        }
        config2 = {
            'entity_types': [
                {'name': 'Person', 'color': 'Red'},  # overrides config1
                {'name': 'Vehicle'},
            ],
            'grades_one': {'items': ['X', 'Y', 'Z']},  # appends + dedups
        }
        chart = ANXChart()
        chart.apply_config(config1)
        chart.apply_config(config2)
        # Layered configs: "later wins per name" — Person is replaced, not duplicated.
        assert len(chart._entity_types) == 2
        by_name = {et.name: et for et in chart._entity_types}
        assert 'Person' in by_name and 'Vehicle' in by_name
        assert by_name['Person'].color == 'Red'  # config2 wins
        # Grades append + dedup by default (no overlap here, full extension).
        assert chart.grades_one.items == ['A', 'B', 'X', 'Y', 'Z']

    def test_apply_config_layered_deep_merges_nested_settings(self):
        """A second config layer with a partial nested settings dict must
        preserve unrelated fields set by earlier layers — deep merge, not
        shallow replace."""
        config1 = {
            'settings': {
                'legend_cfg': {
                    'show': True,
                    'x': 100,
                    'font': {'name': 'Segoe UI', 'size': 11, 'bold': False},
                },
            },
        }
        config2 = {
            'settings': {
                'legend_cfg': {
                    'x': 200,  # override
                    'font': {'bold': True},  # partial nested merge
                },
            },
        }
        chart = ANXChart()
        chart.apply_config(config1)
        chart.apply_config(config2)
        # Top-level overrides
        assert chart.settings.legend_cfg.show is True       # from config1 (untouched)
        assert chart.settings.legend_cfg.x == 200           # from config2
        # Deep merge of nested Font dataclass — all three fields survive
        assert chart.settings.legend_cfg.font.name == 'Segoe UI'  # from config1
        assert chart.settings.legend_cfg.font.size == 11          # from config1
        assert chart.settings.legend_cfg.font.bold is True        # from config2

    def test_apply_config_layered_upserts_all_named_sections(self):
        """Every named-collection section must follow later-wins-per-name."""
        config1 = {
            'entity_types': [{'name': 'Person', 'color': 'Blue'}],
            'link_types': [{'name': 'Call', 'color': 255}],
            'attribute_classes': [{'name': 'Phone', 'type': 'Text', 'prefix': 'Tel: '}],
            'strengths': {'items': [{'name': 'Confirmed', 'dot_style': 'solid'}]},
            'datetime_formats': [{'name': 'ISO', 'format': 'yyyy-MM-dd'}],
        }
        config2 = {
            'entity_types': [{'name': 'Person', 'color': 'Red'}],
            'link_types': [{'name': 'Call', 'color': 0}],
            'attribute_classes': [{'name': 'Phone', 'type': 'Text', 'prefix': 'Phone: '}],
            'strengths': {'items': [{'name': 'Confirmed', 'dot_style': 'dashed'}]},
            'datetime_formats': [{'name': 'ISO', 'format': 'dd/MM/yyyy'}],
        }
        chart = ANXChart()
        chart.apply_config(config1)
        chart.apply_config(config2)
        assert len(chart._entity_types) == 1
        assert chart._entity_types[0].color == 'Red'
        assert len(chart._link_types) == 1
        assert chart._link_types[0].color == 0
        assert len(chart._attribute_classes) == 1
        assert chart._attribute_classes[0].prefix == 'Phone: '
        assert len([s for s in chart.strengths.items if s.name == 'Confirmed']) == 1
        assert next(s for s in chart.strengths.items if s.name == 'Confirmed').dot_style == 'dashed'
        assert len(chart._datetime_formats) == 1
        assert chart._datetime_formats[0].format == 'dd/MM/yyyy'

    def test_data_can_add_new_entity_type(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data_with_new_type = dict(SAMPLE_DATA)
        data_with_new_type['entity_types'] = [{'name': 'Building', 'icon_file': 'building'}]
        chart._apply_data(data_with_new_type)
        names = [et.name for et in chart._entity_types]
        assert 'Building' in names
        assert len(chart._config_conflicts) == 0

    def test_data_can_add_new_strength(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data_with_strength = dict(SAMPLE_DATA)
        data_with_strength['strengths'] = {'items': [{'name': 'Weak', 'dot_style': 'DotStyleDotted'}]}
        chart._apply_data(data_with_strength)
        names = [s.name for s in chart.strengths]
        assert 'Weak' in names
        assert len(chart._config_conflicts) == 0


# ── Conflict detection ────────────────────────────────────────────────────────

class TestConflictDetection:

    def test_conflict_entity_type_different_specs(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['entity_types'] = [{'name': 'Person', 'color': 'Red'}]
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 1
        assert conflicts[0]['section'] == 'entity_types'
        assert conflicts[0]['name'] == 'Person'

    def test_conflict_attribute_class_different_prefix(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['attribute_classes'] = [{'name': 'Phone', 'type': 'Text', 'prefix': '+'}]
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 1
        assert conflicts[0]['section'] == 'attribute_classes'
        assert conflicts[0]['name'] == 'Phone'

    def test_conflict_link_type_different_color(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['link_types'] = [{'name': 'Call', 'color': 0}]
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 1
        assert conflicts[0]['section'] == 'link_types'

    def test_conflict_strength_different_dot_style(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['strengths'] = {'items': [{'name': 'Confirmed', 'dot_style': 'DotStyleDotted'}]}
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 1
        assert conflicts[0]['section'] == 'strengths'

    def test_conflict_grades_different_list(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['grades_one'] = {'items': ['Different', 'Values']}
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 1
        assert conflicts[0]['section'] == 'grades_one'

    def test_conflict_source_types_different(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['source_types'] = ['Witness', 'Record']
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 1
        assert conflicts[0]['section'] == 'source_types'

    def test_no_conflict_identical_skip(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        # Re-declare Person with identical specs → should be silently skipped
        data['entity_types'] = [{'name': 'Person', 'icon_file': 'person', 'color': 'Blue'}]
        data['grades_one'] = {'items': ['Always reliable', 'Usually reliable']}
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 0

    def test_no_conflict_without_config(self):
        # No config applied → from_dict works as before, no conflict detection
        data = dict(SAMPLE_DATA)
        data['entity_types'] = [
            {'name': 'Person', 'color': 'Blue'},
            {'name': 'Person', 'color': 'Red'},  # duplicate, but no config → no conflict error
        ]
        chart = ANXChart.from_dict(data)
        errors = chart.validate()
        # Should get duplicate_name error, NOT config_conflict
        conflict_errors = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflict_errors) == 0

    def test_conflict_error_format(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['entity_types'] = [{'name': 'Person', 'color': 'Red'}]
        chart._apply_data(data)
        errors = chart.validate()
        conflict = [e for e in errors if e['type'] == 'config_conflict'][0]
        assert 'section' in conflict
        assert 'name' in conflict
        assert 'message' in conflict
        assert 'config_value' in conflict
        assert 'data_value' in conflict

    def test_multiple_conflicts_collected(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        data = dict(SAMPLE_DATA)
        data['entity_types'] = [{'name': 'Person', 'color': 'Red'}]
        data['link_types'] = [{'name': 'Call', 'color': 0}]
        data['attribute_classes'] = [{'name': 'Phone', 'type': 'Text', 'prefix': '+'}]
        data['grades_one'] = {'items': ['Different']}
        chart._apply_data(data)
        errors = chart.validate()
        conflicts = [e for e in errors if e['type'] == 'config_conflict']
        assert len(conflicts) == 4


# ── Export ────────────────────────────────────────────────────────────────────

class TestConfigExport:

    def test_to_config_dict_roundtrip(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        exported = chart.to_config_dict()
        assert exported['settings'] == SAMPLE_CONFIG['settings']
        assert exported['grades_one']['items'] == SAMPLE_CONFIG['grades_one']['items']
        assert exported['source_types'] == SAMPLE_CONFIG['source_types']
        assert len(exported['entity_types']) == 2
        assert len(exported['attribute_classes']) == 2

    def test_to_config_file_json(self):
        chart = ANXChart(config=SAMPLE_CONFIG)
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        try:
            abs_path = chart.to_config(path)
            assert os.path.exists(abs_path)
            with open(abs_path) as f:
                reloaded = json.load(f)
            assert reloaded['settings']['extra_cfg']['arrange'] == 'grid'
            assert len(reloaded['entity_types']) == 2
        finally:
            os.unlink(path)

    def test_to_config_file_yaml(self):
        import yaml
        chart = ANXChart(config=SAMPLE_CONFIG)
        fd, path = tempfile.mkstemp(suffix='.yaml')
        os.close(fd)
        try:
            abs_path = chart.to_config(path)
            assert os.path.exists(abs_path)
            with open(abs_path) as f:
                reloaded = yaml.safe_load(f)
            assert reloaded['settings']['extra_cfg']['arrange'] == 'grid'
        finally:
            os.unlink(path)

    def test_to_config_excludes_default_strength(self):
        chart = ANXChart()
        # Only the pre-populated Default strength exists
        exported = chart.to_config_dict()
        assert 'strengths' not in exported

    def test_to_config_includes_modified_default_strength(self):
        chart = ANXChart()
        chart.add_strength('Default', dot_style=DotStyle.DASHED)
        exported = chart.to_config_dict()
        assert 'strengths' in exported
        # strengths is always exported as {items: [...]} (+ default when set)
        # so the config shape round-trips cleanly through _apply_config.
        assert exported['strengths']['items'][0]['name'] == 'Default'

    def test_to_config_empty_chart(self):
        chart = ANXChart()
        exported = chart.to_config_dict()
        # Empty chart → empty dict (or only has strengths if default is excluded)
        assert 'entities' not in exported
        assert 'links' not in exported


class TestStandardLibraryViaSemanticDefs:
    """Test standard library types defined as semantic_entities/links/properties with explicit GUIDs."""

    def test_standard_types_enable_custom_extensions(self):
        """Standard library types with explicit GUIDs enable custom type kind_of resolution."""
        config = {
            'semantic_entities': [
                {'name': 'Legal Entity', 'guid': 'guid00000000-0000-0000-0000-000000000001', 'kind_of': 'Entity'},
                {'name': 'Person', 'guid': 'guid00000000-0000-0000-0000-000000000002', 'kind_of': 'Legal Entity'},
                {'name': 'Suspect', 'kind_of': 'Person', 'description': 'A suspect'},
            ],
            'entity_types': [{'name': 'Person', 'icon_file': 'person', 'semantic_type': 'Person'}],
        }
        chart = ANXChart(config=config)
        chart.add_icon(id='Alice', type='Person')
        xml = chart.to_xml()

        assert 'LibraryCatalogue' in xml
        assert 'Suspect' in xml
        assert 'SemanticTypeGuid' in xml


# ── CLI ───────────────────────────────────────────────────────────────────────

class TestCLIConfig:

    def _run_cli(self, *args, stdin_data=None):
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "anxwritter.cli"] + list(args)
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def test_cli_config_flag(self):
        cfg_path = _write_json(SAMPLE_CONFIG)
        data_path = _write_json(SAMPLE_DATA)
        fd, out_path = tempfile.mkstemp(suffix='.anx')
        os.close(fd)
        try:
            rc, stdout, stderr = self._run_cli(
                '--config', cfg_path, data_path, '-o', out_path
            )
            assert rc == 0, f"CLI failed: {stderr}"
            assert os.path.exists(out_path)
        finally:
            os.unlink(cfg_path)
            os.unlink(data_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_cli_config_only(self):
        cfg_path = _write_json(SAMPLE_CONFIG)
        fd, out_path = tempfile.mkstemp(suffix='.anx')
        os.close(fd)
        try:
            rc, stdout, stderr = self._run_cli(
                '--config', cfg_path, '-o', out_path
            )
            assert rc == 0, f"CLI failed: {stderr}"
        finally:
            os.unlink(cfg_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_cli_config_conflict_exits(self):
        cfg_path = _write_json(SAMPLE_CONFIG)
        conflict_data = dict(SAMPLE_DATA)
        conflict_data['entity_types'] = [{'name': 'Person', 'color': 'Red'}]
        data_path = _write_json(conflict_data)
        fd, out_path = tempfile.mkstemp(suffix='.anx')
        os.close(fd)
        try:
            rc, stdout, stderr = self._run_cli(
                '--config', cfg_path, data_path, '-o', out_path
            )
            assert rc != 0
            error_data = json.loads(stderr)
            conflicts = [e for e in error_data if e['type'] == 'config_conflict']
            assert len(conflicts) >= 1
        finally:
            os.unlink(cfg_path)
            os.unlink(data_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_cli_multiple_configs(self):
        config1 = {'settings': {'extra_cfg': {'arrange': 'grid'}}, 'grades_one': {'items': ['A']}}
        config2 = {'settings': {'grid': {'snap': True}}, 'grades_one': {'items': ['X', 'Y']}}
        cfg1_path = _write_json(config1)
        cfg2_path = _write_json(config2)
        data_path = _write_json(SAMPLE_DATA)
        fd, out_path = tempfile.mkstemp(suffix='.anx')
        os.close(fd)
        try:
            rc, stdout, stderr = self._run_cli(
                '--config', cfg1_path, '--config', cfg2_path,
                data_path, '-o', out_path
            )
            assert rc == 0, f"CLI failed: {stderr}"
        finally:
            os.unlink(cfg1_path)
            os.unlink(cfg2_path)
            os.unlink(data_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


# ── Append + dedup defaults & replace=True opt-in (added with new layering model) ──

class TestAppendDedupAndReplace:
    """Default merge behavior is additive across all sections; replace=True
    is a per-section opt-out for the rare 'narrow the list' case."""

    # ── source_types: append + exact-text dedup ──

    def test_source_types_appends_by_default(self):
        chart = ANXChart()
        chart.apply_config({'source_types': ['Witness', 'Informant']})
        chart.apply_config({'source_types': ['Officer']})
        assert chart.source_types == ['Witness', 'Informant', 'Officer']

    def test_source_types_dedups_exact_text(self):
        chart = ANXChart()
        chart.apply_config({'source_types': ['Witness', 'Informant']})
        chart.apply_config({'source_types': ['Witness', 'Officer']})  # 'Witness' duplicates
        assert chart.source_types == ['Witness', 'Informant', 'Officer']

    def test_source_types_dedup_is_case_sensitive(self):
        # Documented foot-gun: 'Witness' and 'witness' are NOT deduped.
        chart = ANXChart()
        chart.apply_config({'source_types': ['Witness']})
        chart.apply_config({'source_types': ['witness', 'WITNESS']})
        assert chart.source_types == ['Witness', 'witness', 'WITNESS']

    def test_source_types_replace_wipes_previous(self):
        chart = ANXChart()
        chart.apply_config({'source_types': ['Witness', 'Informant']})
        chart.apply_config({'source_types': ['Officer']}, replace=True)
        assert chart.source_types == ['Officer']

    # ── grades: append + exact-text dedup ──

    def test_grades_items_append_by_default(self):
        chart = ANXChart()
        chart.apply_config({'grades_one': {'items': ['A', 'B']}})
        chart.apply_config({'grades_one': {'items': ['C', 'D']}})
        assert chart.grades_one.items == ['A', 'B', 'C', 'D']

    def test_grades_items_dedup_exact_text(self):
        chart = ANXChart()
        chart.apply_config({'grades_one': {'items': ['A', 'B']}})
        chart.apply_config({'grades_one': {'items': ['B', 'C']}})  # 'B' duplicates
        assert chart.grades_one.items == ['A', 'B', 'C']

    def test_grades_default_later_wins_when_non_none(self):
        chart = ANXChart()
        chart.apply_config({'grades_one': {'default': 'A', 'items': ['A', 'B']}})
        chart.apply_config({'grades_one': {'default': 'B', 'items': ['B']}})
        assert chart.grades_one.default == 'B'

    def test_grades_default_keeps_earlier_when_later_is_none(self):
        chart = ANXChart()
        chart.apply_config({'grades_one': {'default': 'A', 'items': ['A', 'B']}})
        # Layer 2 extends items but doesn't set default — earlier default survives.
        chart.apply_config({'grades_one': {'items': ['C']}})
        assert chart.grades_one.default == 'A'
        assert chart.grades_one.items == ['A', 'B', 'C']

    def test_grades_replace_wipes_previous(self):
        chart = ANXChart()
        chart.apply_config({'grades_one': {'default': 'A', 'items': ['A', 'B']}})
        chart.apply_config({'grades_one': {'items': ['X', 'Y']}}, replace=True)
        assert chart.grades_one.items == ['X', 'Y']
        assert chart.grades_one.default is None  # replaced wholesale

    # ── replace=True is per-section, not per-config ──

    def test_replace_only_touches_sections_the_layer_mentions(self):
        chart = ANXChart()
        chart.apply_config({
            'entity_types': [{'name': 'Person', 'color': 'Blue'}],
            'source_types': ['Witness', 'Informant'],
            'grades_one': {'items': ['A', 'B']},
        })
        # Replace layer only mentions source_types — entity_types and
        # grades_one must survive.
        chart.apply_config({'source_types': ['Officer']}, replace=True)
        assert chart.source_types == ['Officer']
        assert [et.name for et in chart._entity_types] == ['Person']
        assert chart.grades_one.items == ['A', 'B']

    def test_replace_settings_replaces_section_wholesale(self):
        chart = ANXChart()
        chart.apply_config({
            'settings': {
                'extra_cfg': {'arrange': 'grid', 'entity_auto_color': True},
                'grid': {'snap': True},
            },
        })
        # replace=True swaps settings entirely with what the layer specifies.
        chart.apply_config({
            'settings': {'extra_cfg': {'arrange': 'circle'}},
        }, replace=True)
        assert chart.settings.extra_cfg.arrange == 'circle'
        # entity_auto_color and grid.snap are gone (back to defaults)
        assert chart.settings.extra_cfg.entity_auto_color is None
        assert chart.settings.grid.snap is None

    def test_replace_named_sections_wipes_earlier_entries(self):
        chart = ANXChart()
        chart.apply_config({'entity_types': [
            {'name': 'Person', 'color': 'Blue'},
            {'name': 'Vehicle', 'color': 'Red'},
        ]})
        chart.apply_config({'entity_types': [
            {'name': 'Building', 'color': 'Green'},
        ]}, replace=True)
        names = [et.name for et in chart._entity_types]
        assert names == ['Building']

    def test_replace_legend_items_clears_earlier(self):
        chart = ANXChart()
        chart.apply_config({'legend_items': [
            {'name': 'Person', 'item_type': 'Icon'},
            {'name': 'Place', 'item_type': 'Icon'},
        ]})
        chart.apply_config({'legend_items': [
            {'name': 'Org', 'item_type': 'Icon'},
        ]}, replace=True)
        names = [li.name for li in chart._legend_items]
        assert names == ['Org']

    def test_replace_strengths_wipes_pre_populated_default(self):
        chart = ANXChart()
        # Pre-populated 'Default' is gone after replace.
        chart.apply_config({'strengths': {'items': [
            {'name': 'Confirmed', 'dot_style': 'solid'},
        ]}}, replace=True)
        names = [s.name for s in chart.strengths.items]
        assert names == ['Confirmed']

    # ── Real-world scenario: extending a base catalog ──

    def test_extending_base_catalog_no_relisting_required(self):
        """The user's review motivating example: layered scrapers extend
        a base catalog without needing to re-list base entries to keep them."""
        base = {
            'source_types': ['Outros'],
            'grades_one': {'default': 'Reliable', 'items': ['Reliable', 'Unreliable']},
            'entity_types': [{'name': 'Person', 'color': 'Blue'}],
        }
        scraper_censec = {
            'source_types': ['Censec'],
            'entity_types': [{'name': 'CourtCase'}],
        }
        chart = ANXChart()
        chart.apply_config(base)
        chart.apply_config(scraper_censec)
        assert chart.source_types == ['Outros', 'Censec']
        assert [et.name for et in chart._entity_types] == ['Person', 'CourtCase']
        assert chart.grades_one.default == 'Reliable'  # base default survives
        assert chart.grades_one.items == ['Reliable', 'Unreliable']


# ── CLI: --config / --config-replace interleaving ──

class TestCLIConfigReplaceInterleaving:

    def _run_cli(self, *args, stdin_data=None):
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "anxwritter.cli"] + list(args)
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def test_cli_config_replace_flag_is_per_layer(self):
        """--config A --config-replace B --config C: A merges in, B replaces
        sections it mentions, C merges into the result."""
        cfg_a = _write_json({'source_types': ['A1', 'A2']})
        cfg_b = _write_json({'source_types': ['B1']})  # will replace
        cfg_c = _write_json({'source_types': ['C1']})  # will append
        try:
            rc, stdout, stderr = self._run_cli(
                '--show-config',
                '--config', cfg_a,
                '--config-replace', cfg_b,
                '--config', cfg_c,
            )
            assert rc == 0, f"CLI failed: {stderr}"
            # After: B replaced with [B1], then C appended with dedup → [B1, C1]
            assert 'B1' in stdout and 'C1' in stdout
            assert 'A1' not in stdout and 'A2' not in stdout
        finally:
            os.unlink(cfg_a)
            os.unlink(cfg_b)
            os.unlink(cfg_c)

    def test_cli_config_replace_alone_works(self):
        cfg = _write_json({'source_types': ['Only']})
        try:
            rc, stdout, stderr = self._run_cli(
                '--show-config', '--config-replace', cfg,
            )
            assert rc == 0, f"CLI failed: {stderr}"
            assert 'Only' in stdout
        finally:
            os.unlink(cfg)


# ── Source name (layer provenance on validation errors) ──────────────────────


class TestSourceName:
    """`source_name` kwarg + auto-derivation tag config entries with the layer
    that contributed them, so validators can surface a `source` key on errors
    and the ANXValidationError message can say which file produced the bug."""

    def _find_err(self, errors, **match):
        """Return the first error dict matching every key/value in *match*."""
        for e in errors:
            if all(e.get(k) == v for k, v in match.items()):
                return e
        return None

    def test_apply_config_explicit_source_name(self):
        """Explicit source_name on a dict-form apply_config call tags errors."""
        chart = ANXChart()
        # AttributeClass missing 'type' → missing_required at .type
        chart.apply_config(
            {'attribute_classes': [{'name': 'Phone'}]},
            source_name='my_layer',
        )
        errors = chart.validate()
        e = self._find_err(errors, type='missing_required',
                           location='attribute_classes[0].type')
        assert e is not None
        assert e.get('source') == 'my_layer'

    def test_apply_config_file_auto_source_name_is_basename(self):
        """apply_config_file auto-defaults source_name to the file basename."""
        cfg = _write_yaml({
            'attribute_classes': [{'name': 'Phone'}],  # missing type → error
        })
        try:
            chart = ANXChart()
            chart.apply_config_file(cfg)
            errors = chart.validate()
            e = self._find_err(errors, type='missing_required',
                               location='attribute_classes[0].type')
            assert e is not None
            # Default is Path(path).name → basename, not full path.
            assert e.get('source') == Path(cfg).name
            assert e.get('source') != cfg  # not the absolute path
        finally:
            os.unlink(cfg)

    def test_apply_config_file_explicit_source_name_overrides_basename(self):
        cfg = _write_yaml({'attribute_classes': [{'name': 'Phone'}]})
        try:
            chart = ANXChart()
            chart.apply_config_file(cfg, source_name='logical_name')
            errors = chart.validate()
            e = self._find_err(errors, type='missing_required',
                               location='attribute_classes[0].type')
            assert e is not None
            assert e.get('source') == 'logical_name'
        finally:
            os.unlink(cfg)

    def test_layered_configs_later_layer_wins_source_attribution(self):
        """When two layers both contribute the same name, the later layer's
        source is what shows up on validation errors for that entry."""
        chart = ANXChart()
        # First layer registers Phone with a valid type
        chart.apply_config(
            {'attribute_classes': [{'name': 'Phone', 'type': 'Text'}]},
            source_name='base.yaml',
        )
        # Second layer overrides Phone — but with a bad merge_behaviour
        # (Text doesn't accept 'xor').
        chart.apply_config(
            {'attribute_classes': [{'name': 'Phone', 'type': 'Text',
                                    'merge_behaviour': 'xor'}]},
            source_name='override.yaml',
        )
        errors = chart.validate()
        e = self._find_err(errors, type='invalid_merge_behaviour')
        assert e is not None
        assert e.get('source') == 'override.yaml'  # later layer wins

    def test_no_source_when_python_api_only(self):
        """Charts built without apply_config/_file get no `source` key on errors —
        non-breaking for callers who never opt in."""
        chart = ANXChart()
        chart.add_attribute_class(name='Phone')  # missing type → error
        errors = chart.validate()
        e = self._find_err(errors, type='missing_required',
                           location='attribute_classes[0].type')
        assert e is not None
        assert 'source' not in e

    def test_no_source_when_source_name_omitted(self):
        """apply_config without source_name leaves errors un-tagged even though
        the entry came from a config layer."""
        chart = ANXChart()
        chart.apply_config({'attribute_classes': [{'name': 'Phone'}]})
        errors = chart.validate()
        e = self._find_err(errors, type='missing_required',
                           location='attribute_classes[0].type')
        assert e is not None
        assert 'source' not in e

    def test_config_conflict_includes_config_source(self):
        """config_conflict errors get config_source attribution from the layer
        that locked the original entry."""
        chart = ANXChart()
        chart.apply_config({
            'attribute_classes': [{'name': 'Phone', 'type': 'Text'}],
        }, source_name='base.yaml')
        # Data file redefines Phone with a different type → config_conflict
        chart._apply_data({
            'attribute_classes': [{'name': 'Phone', 'type': 'Number'}],
            'entities': {},
            'links': [],
        })
        errors = chart.validate()
        e = self._find_err(errors, type='config_conflict', name='Phone')
        assert e is not None
        assert e.get('config_source') == 'base.yaml'

    def test_anx_validation_error_message_includes_source(self):
        """ANXValidationError str() appends a `(source: X)` suffix when an
        error carries the `source` key. Format is documented as unstable —
        this test pins current behavior, not a contract."""
        from anxwritter.errors import ANXValidationError
        errors = [
            {'type': 'missing_required',
             'message': "AttributeClass 'X' must declare 'type'",
             'location': 'attribute_classes[0].type',
             'source': 'base.yaml'},
        ]
        exc = ANXValidationError(errors)
        assert '(source: base.yaml)' in str(exc)

    def test_anx_validation_error_message_includes_config_source(self):
        from anxwritter.errors import ANXValidationError
        errors = [
            {'type': 'config_conflict',
             'message': "Data redefines 'X'",
             'section': 'attribute_classes',
             'name': 'X',
             'config_source': 'base.yaml',
             'config_value': {},
             'data_value': {}},
        ]
        exc = ANXValidationError(errors)
        assert '(config source: base.yaml)' in str(exc)

    def test_grades_section_source(self):
        """Grade collection errors get source from section-level tracking."""
        chart = ANXChart()
        chart.apply_config(
            {'grades_one': {'default': 'missing', 'items': ['A', 'B']}},
            source_name='grades.yaml',
        )
        errors = chart.validate()
        e = self._find_err(errors, type='invalid_grade_default')
        assert e is not None
        assert e.get('source') == 'grades.yaml'

    def test_entity_type_source_on_bad_color(self):
        chart = ANXChart()
        chart.apply_config(
            {'entity_types': [{'name': 'Person', 'color': 'NotARealColor'}]},
            source_name='types.yaml',
        )
        errors = chart.validate()
        e = self._find_err(errors, type='unknown_color',
                           location='entity_types[0]')
        assert e is not None
        assert e.get('source') == 'types.yaml'

    def test_from_config_file_propagates_source_name(self):
        cfg = _write_yaml({'attribute_classes': [{'name': 'Phone'}]})
        try:
            chart = ANXChart.from_config_file(cfg)
            errors = chart.validate()
            e = self._find_err(errors, type='missing_required',
                               location='attribute_classes[0].type')
            assert e is not None
            assert e.get('source') == Path(cfg).name
        finally:
            os.unlink(cfg)

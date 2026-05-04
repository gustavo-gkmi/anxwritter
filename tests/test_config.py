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
            'grades_one': {'items': ['X', 'Y', 'Z']},  # replaces config1
        }
        chart = ANXChart()
        chart.apply_config(config1)
        chart.apply_config(config2)
        # Layered configs: "later wins per name" — Person is replaced, not duplicated.
        assert len(chart._entity_types) == 2
        by_name = {et.name: et for et in chart._entity_types}
        assert 'Person' in by_name and 'Vehicle' in by_name
        assert by_name['Person'].color == 'Red'  # config2 wins
        # Last config replaces grades wholesale (flat list, no natural key).
        assert chart.grades_one.items == ['X', 'Y', 'Z']

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

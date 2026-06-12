"""Config-layering engine (1.12.0): field-merge default, lock, delete.

These exercise the config-vs-config behaviour added in 1.12.0. The
config-vs-data conflict path lives in ``test_config.py`` and is unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from anxwritter import ANXChart
from anxwritter.errors import ErrorType
from anxwritter.utils import _enum_val

REPO_ROOT = str(Path(__file__).parent.parent)


def _ac(chart, name):
    return next(a for a in chart._attribute_classes if a.name == name)


def _conflict_types(chart):
    return {e["type"] for e in chart._config_conflicts}


# ── Field-merge is the default ───────────────────────────────────────────────

class TestFieldMergeDefault:
    def test_partial_override_retains_omitted_fields(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]})
        c.apply_config({"attribute_classes": [{"name": "X", "prefix": "Tel: "}]})
        ac = _ac(c, "X")
        assert ac.type is not None and str(ac.type).lower().endswith("text")
        assert ac.prefix == "Tel: "

    def test_no_missing_required_after_partial_override(self):
        # Pre-1.12 this dropped `type` and tripped missing_required.
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]})
        c.apply_config({"attribute_classes": [{"name": "X", "prefix": "P"}]})
        assert ErrorType.MISSING_REQUIRED.value not in {e["type"] for e in c.validate()}

    def test_nested_font_field_merges(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [
            {"name": "X", "type": "text", "font": {"bold": True}}]})
        c.apply_config({"attribute_classes": [
            {"name": "X", "font": {"italic": True}}]})
        ac = _ac(c, "X")
        assert ac.font.bold is True and ac.font.italic is True

    def test_new_name_is_appended(self):
        c = ANXChart()
        c.apply_config({"entity_types": [{"name": "Person", "color": "Blue"}]})
        c.apply_config({"entity_types": [{"name": "Org", "color": "Red"}]})
        assert [e.name for e in c._entity_types] == ["Person", "Org"]

    def test_public_add_still_replaces_wholesale(self):
        # The public single-call add_* keeps whole-replace semantics —
        # only config LAYERING field-merges.
        c = ANXChart()
        c.add_entity_type(name="P", color="Blue", icon_file="person")
        c.add_entity_type(name="P", color="Red")
        et = next(e for e in c._entity_types if e.name == "P")
        assert et.icon_file is None  # dropped by whole-replace


# ── lock=True ────────────────────────────────────────────────────────────────

class TestLock:
    def test_locked_leaf_change_is_rejected_and_preserved(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]},
                       lock=True, source_name="org")
        c.apply_config({"attribute_classes": [{"name": "X", "type": "number"}]},
                       source_name="user")
        errs = [e for e in c.validate() if e["type"] == ErrorType.LOCKED_OVERRIDE.value]
        assert errs
        assert errs[0]["source"] == "user" if "source" in errs[0] else True
        assert errs[0].get("config_source") == "org"
        assert str(_ac(c, "X").type).lower().endswith("text")  # locked value kept

    def test_non_locked_field_still_settable(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]}, lock=True)
        c.apply_config({"attribute_classes": [{"name": "X", "prefix": "P:"}]})
        assert _ac(c, "X").prefix == "P:"
        assert ErrorType.LOCKED_OVERRIDE.value not in _conflict_types(c)

    def test_new_entry_allowed_under_lock(self):
        c = ANXChart()
        c.apply_config({"entity_types": [{"name": "Person"}]}, lock=True)
        c.apply_config({"entity_types": [{"name": "Org"}]})
        assert [e.name for e in c._entity_types] == ["Person", "Org"]
        assert ErrorType.LOCKED_OVERRIDE.value not in _conflict_types(c)

    def test_settings_leaf_lock(self):
        c = ANXChart()
        c.apply_config({"settings": {"chart": {"bg_color": 100}}}, lock=True)
        c.apply_config({"settings": {"chart": {"bg_color": 200},
                                     "grid": {"snap": True}}})
        assert c.settings.chart.bg_color == 100  # locked
        assert c.settings.grid.snap is True       # unlocked sibling applied
        assert ErrorType.LOCKED_OVERRIDE.value in _conflict_types(c)

    def test_idempotent_relayer_same_value_no_conflict(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]}, lock=True)
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]})
        assert ErrorType.LOCKED_OVERRIDE.value not in _conflict_types(c)


# ── operation='delete' ───────────────────────────────────────────────────────

class TestDelete:
    def test_whole_entry_delete(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [
            {"name": "A", "type": "text"}, {"name": "B", "type": "number"}]})
        c.apply_config({"attribute_classes": [{"name": "B"}]}, operation="delete")
        assert [a.name for a in c._attribute_classes] == ["A"]

    def test_field_unset_delete(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [
            {"name": "A", "type": "text", "prefix": "P"}]})
        c.apply_config({"attribute_classes": [{"name": "A", "prefix": None}]},
                       operation="delete")
        ac = _ac(c, "A")
        assert ac.prefix is None and str(ac.type).lower().endswith("text")

    def test_delete_absent_is_noop(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "A", "type": "text"}]})
        c.apply_config({"attribute_classes": [{"name": "Ghost"}]}, operation="delete")
        assert [a.name for a in c._attribute_classes] == ["A"]
        assert not c._config_conflicts

    def test_delete_contract_non_null_field(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "A", "type": "text"}]})
        c.apply_config({"attribute_classes": [{"name": "A", "prefix": "x"}]},
                       operation="delete")
        assert ErrorType.DELETE_CONTRACT.value in _conflict_types(c)

    def test_delete_locked_entry_blocked(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "A", "type": "text"}]}, lock=True)
        c.apply_config({"attribute_classes": [{"name": "A"}]}, operation="delete")
        assert [a.name for a in c._attribute_classes] == ["A"]  # kept
        assert ErrorType.LOCKED_OVERRIDE.value in _conflict_types(c)

    def test_delete_whole_section_via_null(self):
        c = ANXChart()
        c.apply_config({"source_types": ["A", "B"]})
        c.apply_config({"source_types": None}, operation="delete")
        assert c.source_types == []

    def test_delete_source_type_item(self):
        c = ANXChart()
        c.apply_config({"source_types": ["A", "B", "C"]})
        c.apply_config({"source_types": ["B"]}, operation="delete")
        assert c.source_types == ["A", "C"]

    def test_settings_leaf_delete_reverts_default(self):
        c = ANXChart()
        c.apply_config({"settings": {"grid": {"snap": True}}})
        c.apply_config({"settings": {"grid": {"snap": None}}}, operation="delete")
        assert c.settings.grid.snap is None


# ── illegal combinations ─────────────────────────────────────────────────────

class TestIllegalCombos:
    def test_delete_plus_lock_raises(self):
        with pytest.raises(ValueError):
            ANXChart().apply_config({}, operation="delete", lock=True)

    def test_delete_plus_wipe_raises(self):
        with pytest.raises(ValueError):
            ANXChart().apply_config({}, operation="delete", wipe_previous=True)

    def test_bad_operation_raises(self):
        with pytest.raises(ValueError):
            ANXChart().apply_config({}, operation="frobnicate")


# ── preset flow (the downstream use case) ────────────────────────────────────

class TestPresetFlow:
    def test_preset_overriding_org_lock_is_flagged_with_source(self):
        c = ANXChart()
        c.apply_config({"entity_types": [{"name": "Person", "color": "Blue"}]},
                       lock=True, source_name="org")
        c.apply_config({"entity_types": [{"name": "Person", "color": "Red"}]},
                       source_name="user_preset")
        errs = [e for e in c.validate() if e["type"] == ErrorType.LOCKED_OVERRIDE.value]
        assert errs and errs[0].get("config_source") == "org"
        # locked colour preserved
        assert next(e for e in c._entity_types if e.name == "Person").color == "Blue"

    def test_clean_preset_validates(self):
        c = ANXChart()
        c.apply_config({"entity_types": [{"name": "Person", "color": "Blue"}]},
                       lock=True, source_name="org")
        c.apply_config({"entity_types": [{"name": "Suspect", "color": "Red"}]},
                       source_name="user_preset")
        assert ErrorType.LOCKED_OVERRIDE.value not in {e["type"] for e in c.validate()}


# ── wipe_previous (the "narrow the list" case) ───────────────────────────────

class TestWipePrevious:
    def test_keyed_section_wiped_then_merged(self):
        c = ANXChart()
        c.apply_config({"attribute_classes": [
            {"name": "A", "type": "text"}, {"name": "B", "type": "number"}]})
        c.apply_config({"attribute_classes": [{"name": "C", "type": "text"}]},
                       wipe_previous=True)
        assert [a.name for a in c._attribute_classes] == ["C"]

    def test_wipe_only_clears_mentioned_sections(self):
        c = ANXChart()
        c.apply_config({"entity_types": [{"name": "P"}],
                        "attribute_classes": [{"name": "A", "type": "text"}]})
        c.apply_config({"attribute_classes": [{"name": "B", "type": "text"}]},
                       wipe_previous=True)
        assert [e.name for e in c._entity_types] == ["P"]      # untouched
        assert [a.name for a in c._attribute_classes] == ["B"]  # wiped + merged

    def test_wipe_clears_prior_leaf_locks(self):
        # A locked leaf wiped away no longer blocks a later layer.
        c = ANXChart()
        c.apply_config({"attribute_classes": [{"name": "X", "type": "text"}]},
                       lock=True)
        c.apply_config({"attribute_classes": [{"name": "X", "type": "number"}]},
                       wipe_previous=True)
        assert str(_ac(c, "X").type).lower().endswith("number")
        assert ErrorType.LOCKED_OVERRIDE.value not in _conflict_types(c)

    def test_grades_wipe(self):
        c = ANXChart()
        c.apply_config({"grades_one": {"items": ["A", "B"]}})
        c.apply_config({"grades_one": {"items": ["C"]}}, wipe_previous=True)
        assert list(c.grades_one.items) == ["C"]


# ── append-only sections (palettes / legend_items) ───────────────────────────

class TestAppendOnlySections:
    def test_palettes_append_across_layers(self):
        c = ANXChart()
        c.apply_config({"palettes": [{"name": "P1"}]})
        c.apply_config({"palettes": [{"name": "P2"}]})
        assert [p.name for p in c._palettes] == ["P1", "P2"]

    def test_palettes_delete_via_null_clears(self):
        c = ANXChart()
        c.apply_config({"palettes": [{"name": "P1"}]})
        c.apply_config({"palettes": None}, operation="delete")
        assert c._palettes == []

    def test_palettes_wipe_replaces(self):
        c = ANXChart()
        c.apply_config({"palettes": [{"name": "P1"}]})
        c.apply_config({"palettes": [{"name": "P2"}]}, wipe_previous=True)
        assert [p.name for p in c._palettes] == ["P2"]

    def test_legend_items_wipe_replaces(self):
        c = ANXChart()
        c.apply_config({"legend_items": [{"name": "L1"}]})
        c.apply_config({"legend_items": [{"name": "L2"}]}, wipe_previous=True)
        assert [li.name for li in c._legend_items] == ["L2"]


# ── grades / strengths / source_types cross-domain lock + delete ─────────────

class TestGradesStrengthsCrossDomain:
    def test_grades_default_lock_preserved(self):
        c = ANXChart()
        c.apply_config({"grades_one": {"items": ["High", "Low"], "default": "High"}},
                       lock=True, source_name="org")
        c.apply_config({"grades_one": {"default": "Low"}}, source_name="user")
        assert c.grades_one.default == "High"  # locked value kept
        assert ErrorType.LOCKED_OVERRIDE.value in _conflict_types(c)

    def test_grades_delete_item(self):
        c = ANXChart()
        c.apply_config({"grades_one": {"items": ["A", "B", "C"]}})
        c.apply_config({"grades_one": {"items": ["B"]}}, operation="delete")
        assert list(c.grades_one.items) == ["A", "C"]

    def test_strengths_default_lock_preserved(self):
        c = ANXChart()
        c.apply_config({"strengths": {"default": "Strong",
                                      "items": [{"name": "Strong", "dot_style": "solid"}]}},
                       lock=True)
        c.apply_config({"strengths": {"default": "Weak",
                                      "items": [{"name": "Weak", "dot_style": "dashed"}]}})
        assert c.strengths.default == "Strong"  # locked
        assert ErrorType.LOCKED_OVERRIDE.value in _conflict_types(c)
        assert "Weak" in {s.name for s in c.strengths.items}  # unlocked item still added

    def test_source_types_locked_item_delete_blocked(self):
        c = ANXChart()
        c.apply_config({"source_types": ["A", "B"]}, lock=True)
        c.apply_config({"source_types": ["A"]}, operation="delete")
        assert "A" in c.source_types  # locked item kept
        assert ErrorType.LOCKED_OVERRIDE.value in _conflict_types(c)

    def test_provenance_survives_unrelated_delete(self):
        # Deleting one entry must not drop a sibling's source attribution.
        c = ANXChart()
        c.apply_config({"entity_types": [{"name": "Person", "color": "Blue"}]},
                       lock=True, source_name="org")
        c.apply_config({"entity_types": [{"name": "Temp", "color": "Red"}]},
                       source_name="temp")
        c.apply_config({"entity_types": [{"name": "Temp"}]}, operation="delete")
        # Person's lock + source still enforced after Temp's removal.
        c.apply_config({"entity_types": [{"name": "Person", "color": "Red"}]},
                       source_name="user")
        errs = [e for e in c.validate() if e["type"] == ErrorType.LOCKED_OVERRIDE.value]
        assert errs and errs[0].get("config_source") == "org"


# ── CLI flags ────────────────────────────────────────────────────────────────

class TestCLI:
    def _run(self, *args):
        cmd = [sys.executable, "-m", "anxwritter.cli", *args]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    @staticmethod
    def _write(d):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(d, f)
        f.close()
        return f.name

    def test_config_lock_flag_flags_override(self):
        org = self._write({"attribute_classes": [{"name": "X", "type": "text"}]})
        user = self._write({"attribute_classes": [{"name": "X", "type": "number"}]})
        data = self._write({"entities": {"icons": [{"id": "a", "type": "Person"}]}})
        try:
            rc, out, err = self._run(
                "--config-lock", org, "--config", user, "--validate-only", data,
            )
            assert rc == 1
            assert "locked_override" in err
        finally:
            for p in (org, user, data):
                os.unlink(p)

    def test_config_delete_flag(self):
        base = self._write({"source_types": ["A", "B", "C"]})
        rm = self._write({"source_types": ["B"]})
        try:
            rc, out, err = self._run(
                "--show-config", "--config", base, "--config-delete", rm,
            )
            assert rc == 0
            assert "A" in out and "C" in out
        finally:
            os.unlink(base)
            os.unlink(rm)


# ── In-file `cascade.mode` (self-describing layer metadata) ─────────────────

class TestCascadeMode:
    """Top-level ``cascade.mode`` block in a config file declares the layering
    operation for that file. Bare --config / no-kwargs Python entry points
    honor it; explicit CLI flags / kwargs override. See chart.py docstrings."""

    def test_apply_config_honors_lock_mode(self):
        org = ANXChart()
        org.apply_config({
            'cascade': {'mode': 'lock'},
            'attribute_classes': [{'name': 'X', 'type': 'text'}],
        })
        # A later layer overriding X.type triggers locked_override.
        org.apply_config({'attribute_classes': [{'name': 'X', 'type': 'number'}]})
        types = {e['type'] for e in org.validate()}
        assert 'locked_override' in types

    def test_apply_config_honors_wipe_mode(self):
        chart = ANXChart()
        chart.apply_config({'source_types': ['A', 'B', 'C']})
        chart.apply_config({
            'cascade': {'mode': 'wipe'},
            'source_types': ['Z'],
        })
        assert chart.source_types == ['Z']

    def test_apply_config_honors_delete_mode(self):
        chart = ANXChart()
        chart.apply_config({'source_types': ['A', 'B', 'C']})
        chart.apply_config({
            'cascade': {'mode': 'delete'},
            'source_types': ['B'],
        })
        assert chart.source_types == ['A', 'C']

    def test_explicit_kwarg_overrides_cascade_mode(self):
        # cascade says lock; caller explicitly passes lock=False → no lock.
        chart = ANXChart()
        chart.apply_config({
            'cascade': {'mode': 'lock'},
            'attribute_classes': [{'name': 'X', 'type': 'text'}],
        }, lock=False)
        chart.apply_config({'attribute_classes': [{'name': 'X', 'type': 'number'}]})
        types = {e['type'] for e in chart.validate()}
        assert 'locked_override' not in types

    def test_merge_mode_is_a_noop(self):
        # cascade.mode=merge is the default; behavior identical to no cascade.
        chart = ANXChart()
        chart.apply_config({
            'cascade': {'mode': 'merge'},
            'attribute_classes': [{'name': 'X', 'type': 'text'}],
        })
        chart.apply_config({'attribute_classes': [{'name': 'X', 'type': 'number'}]})
        # Later layer wins on type (field-merge by name).
        assert chart.validate() == [] or all(
            e['type'] != 'locked_override' for e in chart.validate()
        )
        # Confirm the type updated.
        ac = next(a for a in chart._attribute_classes if a.name == 'X')
        assert _enum_val(ac.type).lower() == 'number'

    def test_invalid_mode_value_rejected(self):
        chart = ANXChart()
        with pytest.raises(ValueError, match="cascade.mode"):
            chart.apply_config({'cascade': {'mode': 'frobnicate'}})

    def test_unknown_keys_under_cascade_rejected(self):
        chart = ANXChart()
        with pytest.raises(ValueError, match="Unknown keys under `cascade`"):
            chart.apply_config({'cascade': {'mode': 'merge', 'priority': 5}})

    def test_cascade_not_a_mapping_rejected(self):
        chart = ANXChart()
        with pytest.raises(ValueError, match="cascade.*must be a mapping"):
            chart.apply_config({'cascade': 'lock'})

    def test_empty_cascade_block_is_fine(self):
        # `cascade: {}` or `cascade: null` is valid — no mode set, defaults apply.
        chart = ANXChart()
        chart.apply_config({'cascade': {}, 'source_types': ['A']})
        assert chart.source_types == ['A']
        chart2 = ANXChart()
        chart2.apply_config({'cascade': None, 'source_types': ['A']})
        assert chart2.source_types == ['A']

    def test_from_dict_strips_cascade_silently(self):
        # from_dict / from_yaml / from_json are construction APIs; cascade
        # has no meaning. Strip it without complaint (but still validate
        # the block's shape — typos should still error).
        c = ANXChart.from_dict({
            'cascade': {'mode': 'lock'},
            'attribute_classes': [{'name': 'X', 'type': 'text'}],
        })
        # No 'cascade' section leaks into the chart; AC was applied normally.
        assert any(a.name == 'X' for a in c._attribute_classes)
        # Malformed cascade still raises on the construction path.
        with pytest.raises(ValueError, match="cascade.mode"):
            ANXChart.from_dict({'cascade': {'mode': 'bogus'}})

    def test_from_yaml_strips_cascade_silently(self):
        yaml_src = """
cascade:
  mode: lock
attribute_classes:
  - name: X
    type: text
"""
        c = ANXChart.from_yaml(yaml_src)
        assert any(a.name == 'X' for a in c._attribute_classes)

    def test_apply_config_file_honors_cascade_mode(self, tmp_path):
        org = tmp_path / "org.yaml"
        org.write_text(
            "cascade:\n  mode: lock\n"
            "attribute_classes:\n  - name: X\n    type: text\n"
        )
        chart = ANXChart()
        chart.apply_config_file(str(org))  # bare call → file's mode wins
        chart.apply_config({'attribute_classes': [{'name': 'X', 'type': 'number'}]})
        types = {e['type'] for e in chart.validate()}
        assert 'locked_override' in types


class TestCascadeModeCLI(TestCLI):
    """CLI-level wiring: bare --config honors file's cascade.mode; explicit
    --config-* flags override it."""

    def test_bare_config_honors_cascade_lock(self):
        org = self._write({
            "cascade": {"mode": "lock"},
            "attribute_classes": [{"name": "X", "type": "text"}],
        })
        user = self._write({"attribute_classes": [{"name": "X", "type": "number"}]})
        data = self._write({"entities": {"icons": [{"id": "a", "type": "Person"}]}})
        try:
            rc, out, err = self._run(
                "--config", org, "--config", user, "--validate-only", data,
            )
            assert rc == 1
            assert "locked_override" in err
        finally:
            for p in (org, user, data):
                os.unlink(p)

    def test_explicit_config_flag_overrides_cascade(self):
        # cascade says lock but CLI --config-wipe overrides → wipe wins,
        # no locked_override fires.
        org = self._write({
            "cascade": {"mode": "lock"},
            "source_types": ["A", "B"],
        })
        user = self._write({"source_types": ["Z"]})
        try:
            rc, out, err = self._run(
                "--show-config", "--config-wipe", org, "--config", user,
            )
            assert rc == 0
            # Wipe cleared org's contributions, then user's Z is added.
            assert "Z" in out
        finally:
            for p in (org, user):
                os.unlink(p)

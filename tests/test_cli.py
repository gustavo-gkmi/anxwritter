"""Tests for CLI argparse, exit codes, error JSON output."""

import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args, stdin_data=None):
    """Run the CLI as a subprocess, return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "anxwritter.cli"] + list(args)
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


VALID_JSON = json.dumps({
    "entities": {
        "icons": [
            {"id": "Alice", "type": "Person"},
            {"id": "Bob", "type": "Person"},
        ]
    },
    "links": [
        {"from_id": "Alice", "to_id": "Bob", "type": "Call"}
    ],
})

INVALID_JSON = json.dumps({
    "entities": {
        "icons": [{"type": "Person"}]  # missing id
    }
})


class TestValidateOnly:
    def test_valid_returns_zero(self):
        rc, out, err = _run_cli("--validate-only", stdin_data=VALID_JSON)
        assert rc == 0
        assert json.loads(out) == []

    def test_invalid_returns_one(self):
        rc, out, err = _run_cli("--validate-only", stdin_data=INVALID_JSON)
        assert rc == 1
        errors = json.loads(err)
        assert len(errors) >= 1
        assert errors[0]['type'] == 'missing_required'


class TestFileOutput:
    def test_writes_anx(self, tmp_path):
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli("-o", out_path, stdin_data=VALID_JSON)
        assert rc == 0
        assert out.endswith('.anx')

    def test_auto_extension(self, tmp_path):
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli("-o", out_path, stdin_data=VALID_JSON)
        assert out.endswith('.anx')

    def test_validation_error_on_output(self, tmp_path):
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli("-o", out_path, stdin_data=INVALID_JSON)
        assert rc == 1
        errors = json.loads(err)
        assert len(errors) >= 1


class TestRequiredArgs:
    def test_no_output_no_validate(self):
        rc, out, err = _run_cli(stdin_data=VALID_JSON)
        assert rc == 2  # argparse error


class TestFileInput:
    def test_json_file(self, tmp_path):
        p = tmp_path / "input.json"
        p.write_text(VALID_JSON, encoding="utf-8")
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli(str(p), "-o", out_path)
        assert rc == 0
        assert out.endswith('.anx')


VALID_YAML = """\
entities:
  icons:
    - id: Alice
      type: Person
    - id: Bob
      type: Person
links:
  - from_id: Alice
    to_id: Bob
    type: Call
"""


class TestYAMLInput:
    def test_yaml_file(self, tmp_path):
        p = tmp_path / "input.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli(str(p), "-o", out_path)
        assert rc == 0, f"CLI failed: {err}"
        assert out.endswith('.anx')

    def test_yml_extension(self, tmp_path):
        p = tmp_path / "input.yml"
        p.write_text(VALID_YAML, encoding="utf-8")
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli(str(p), "-o", out_path)
        assert rc == 0, f"CLI failed: {err}"

    def test_config_with_yaml_data(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"settings": {"extra_cfg": {"arrange": "grid"}}}), encoding="utf-8")
        data = tmp_path / "data.yaml"
        data.write_text(VALID_YAML, encoding="utf-8")
        out_path = str(tmp_path / "out")
        rc, out, err = _run_cli("--config", str(cfg), str(data), "-o", out_path)
        assert rc == 0, f"CLI failed: {err}"

    def test_validate_only_with_config(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"settings": {"extra_cfg": {"arrange": "grid"}}}), encoding="utf-8")
        rc, out, err = _run_cli("--config", str(cfg), "--validate-only", stdin_data=VALID_JSON)
        assert rc == 0


class TestNonAsciiStdin:
    def test_stdin_accepts_non_ascii_json(self):
        payload = {
            "entities": {
                "icons": [
                    {"id": "alice", "type": "Person",
                     "label": "Alice — Operação Fraude",
                     "description": "Investigação em São Paulo"},
                ],
            },
        }
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "anxwritter.cli", "--validate-only"],
            input=stdin_bytes,
            capture_output=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr.decode('utf-8', errors='replace')}"
        assert json.loads(result.stdout.decode("utf-8")) == []

    def test_stderr_non_ascii_error_message(self):
        payload = {
            "entities": {
                "icons": [{"type": "Person", "label": "São Paulo"}],
            },
        }
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "anxwritter.cli", "--validate-only"],
            input=stdin_bytes,
            capture_output=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1
        errors = json.loads(result.stderr.decode("utf-8"))
        assert any(e["type"] == "missing_required" for e in errors)


class TestShowConfig:
    """--show-config prints the resolved merged config with provenance comments."""

    def _write(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_single_config_prints_without_requiring_output(self, tmp_path):
        cfg = tmp_path / "base.json"
        self._write(cfg, {"settings": {"chart": {"bg_color": 123}}})
        rc, out, err = _run_cli("--show-config", "--config", str(cfg))
        assert rc == 0, f"stderr: {err}"
        assert "bg_color: 123" in out
        assert "# from: base.json" in out

    def test_two_layer_override_shows_later_wins(self, tmp_path):
        company = tmp_path / "company.json"
        project = tmp_path / "project.json"
        self._write(company, {
            "settings": {"chart": {"bg_color": 111, "bg_filled": True}},
            "entity_types": [{"name": "Person", "color": "Blue"}],
        })
        self._write(project, {
            "settings": {"chart": {"bg_color": 222}},
            "entity_types": [{"name": "Person", "color": "Red"}],
        })
        rc, out, err = _run_cli("--show-config",
                                "--config", str(company),
                                "--config", str(project))
        assert rc == 0, f"stderr: {err}"
        # Overridden keys show the later layer
        assert "bg_color: 222  # from: project.json" in out
        assert "color: Red  # from: project.json" in out
        # Untouched keys keep their original layer
        assert "bg_filled: true  # from: company.json" in out

    def test_deep_merge_nested_settings_provenance(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        self._write(a, {"settings": {"legend_cfg": {"font": {"name": "Segoe UI", "size": 11}}}})
        self._write(b, {"settings": {"legend_cfg": {"font": {"bold": True}}}})
        rc, out, err = _run_cli("--show-config", "--config", str(a), "--config", str(b))
        assert rc == 0, f"stderr: {err}"
        assert "name: Segoe UI  # from: a.json" in out
        assert "size: 11  # from: a.json" in out
        assert "bold: true  # from: b.json" in out

    def test_new_entries_in_later_layer_attributed(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        self._write(a, {"entity_types": [{"name": "Person"}]})
        self._write(b, {"entity_types": [{"name": "Vehicle", "color": "Green"}]})
        rc, out, err = _run_cli("--show-config", "--config", str(a), "--config", str(b))
        assert rc == 0, f"stderr: {err}"
        assert "name: Person  # from: a.json" in out
        assert "name: Vehicle  # from: b.json" in out
        assert "color: Green  # from: b.json" in out

    def test_data_file_provenance(self, tmp_path):
        cfg = tmp_path / "base.json"
        data = tmp_path / "chart.json"
        self._write(cfg, {"settings": {"chart": {"bg_color": 111}}})
        self._write(data, {
            "settings": {"extra_cfg": {"arrange": "grid"}},
            "entities": {"icons": [{"id": "a", "type": "Person"}]},
        })
        rc, out, err = _run_cli("--show-config", "--config", str(cfg), str(data))
        assert rc == 0, f"stderr: {err}"
        assert "bg_color: 111  # from: base.json" in out
        assert "arrange: grid  # from: chart.json" in out

    def test_exits_zero_without_writing_anx(self, tmp_path):
        cfg = tmp_path / "base.json"
        self._write(cfg, {"settings": {"chart": {"bg_color": 1}}})
        out_target = tmp_path / "should_not_exist.anx"
        rc, out, err = _run_cli("--show-config", "--config", str(cfg))
        assert rc == 0
        assert not out_target.exists()

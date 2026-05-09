"""anxwritter CLI — convert JSON/YAML to .anx files."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from anxwritter.chart import ANXChart
from anxwritter.errors import ANXValidationError


def _force_utf8_stdio() -> None:
    # On Windows, Python stdio falls back to the system code page (often
    # cp1252) when input/output is piped, breaking non-ASCII text. Force UTF-8.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="strict")
        except (AttributeError, io.UnsupportedOperation):
            pass


def _flatten_config(obj, prefix: str = ""):
    """Yield ``(flat_path, value)`` pairs from a nested config dict.

    List items that are dicts with a ``name`` key are indexed by that name
    (e.g. ``entity_types[Person].icon_file``); other list items use their
    integer index. This matches the "later wins per name" layering model.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                yield from _flatten_config(v, child)
            else:
                yield child, v
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, dict) and "name" in item:
                key = f"[{item['name']}]"
            else:
                key = f"[{i}]"
            child = f"{prefix}{key}"
            if isinstance(item, (dict, list)):
                yield from _flatten_config(item, child)
            else:
                yield child, item


def _diff_config(old: dict, new: dict) -> set:
    """Return flat paths present in ``new`` with a different value than ``old``."""
    old_flat = dict(_flatten_config(old))
    new_flat = dict(_flatten_config(new))
    return {p for p, v in new_flat.items() if old_flat.get(p) != v}


_YAML_QUOTE_SENTINELS = {"true", "false", "null", "yes", "no", "~", "on", "off"}


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if not isinstance(v, str):
        v = str(v)
    if not v:
        return "''"
    if v.lower() in _YAML_QUOTE_SENTINELS:
        return f"'{v}'"
    # Quote if the string looks like a number (avoids type drift on reparse).
    try:
        int(v)
        return f"'{v}'"
    except ValueError:
        pass
    try:
        float(v)
        return f"'{v}'"
    except ValueError:
        pass
    # Quote if special chars would confuse a parser.
    special = set(":#{}[]&*!|>%@`\"'\n")
    if any(c in special for c in v) or v != v.strip():
        return "'" + v.replace("'", "''") + "'"
    return v


def _render_annotated_config(obj, provenance: dict) -> str:
    """Render a config dict as YAML-compatible text with inline
    ``# from: FILE`` comments on every leaf that has a recorded source.

    Custom emitter (not yaml.safe_dump) because we need the flat path of
    each leaf as we walk, including list items keyed by their ``name``
    field. Matches the path format used by ``_flatten_config``.
    """
    lines: list = []

    def _emit_map(d: dict, indent: int, path: str) -> None:
        ind = " " * indent
        for k, v in d.items():
            child_path = f"{path}.{k}" if path else k
            if isinstance(v, dict) and v:
                lines.append(f"{ind}{k}:")
                _emit_map(v, indent + 2, child_path)
            elif isinstance(v, list) and v:
                lines.append(f"{ind}{k}:")
                _emit_list(v, indent, child_path)
            else:
                scalar = _yaml_scalar(v)
                comment = f"  # from: {provenance[child_path]}" if child_path in provenance else ""
                lines.append(f"{ind}{k}: {scalar}{comment}")

    def _emit_list(lst: list, indent: int, path: str) -> None:
        ind = " " * indent
        for i, item in enumerate(lst):
            if isinstance(item, dict) and "name" in item:
                seg = f"[{item['name']}]"
            else:
                seg = f"[{i}]"
            child_path = f"{path}{seg}"

            if isinstance(item, dict) and item:
                keys = list(item.keys())
                for j, k in enumerate(keys):
                    v = item[k]
                    key_path = f"{child_path}.{k}"
                    marker = "- " if j == 0 else "  "
                    if isinstance(v, dict) and v:
                        lines.append(f"{ind}{marker}{k}:")
                        _emit_map(v, indent + 4, key_path)
                    elif isinstance(v, list) and v:
                        lines.append(f"{ind}{marker}{k}:")
                        _emit_list(v, indent + 2, key_path)
                    else:
                        scalar = _yaml_scalar(v)
                        comment = f"  # from: {provenance[key_path]}" if key_path in provenance else ""
                        lines.append(f"{ind}{marker}{k}: {scalar}{comment}")
            elif isinstance(item, list):
                lines.append(f"{ind}-")
                _emit_list(item, indent + 2, child_path)
            else:
                scalar = _yaml_scalar(item)
                comment = f"  # from: {provenance[child_path]}" if child_path in provenance else ""
                lines.append(f"{ind}- {scalar}{comment}")

    if isinstance(obj, dict):
        _emit_map(obj, 0, "")
    elif isinstance(obj, list):
        _emit_list(obj, 0, "")
    return "\n".join(lines) + "\n"


def _load_input(path: str | None) -> dict:
    """Load chart data from a file path or stdin.

    JSON is the default for stdin. File extension determines format
    (.yaml/.yml → YAML, anything else → JSON). Relative paths inside the
    loaded data (currently ``geo_map.data_file``) are rewritten to absolute,
    anchored at the input file's directory. Stdin input keeps CWD-relative
    semantics since there's no source file to anchor against.
    """
    if path is None:
        # stdin → JSON; no source dir, leave paths CWD-relative
        raw = sys.stdin.read()
        return json.loads(raw)

    p = Path(path)
    if not p.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    ext = p.suffix.lower()
    text = p.read_text(encoding="utf-8")

    if ext in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            print("Error: pyyaml is required for YAML input. Install with: pip install pyyaml",
                  file=sys.stderr)
            sys.exit(1)
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    ANXChart._resolve_relative_paths(data, p.parent)
    return data


def main(argv: list[str] | None = None) -> None:
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="anxwritter",
        description="Convert JSON/YAML chart data to i2 Analyst's Notebook .anx files.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Input file path (JSON or YAML by extension). Reads stdin if omitted.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output .anx file path (required unless --validate-only).",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        help="Config file path (JSON or YAML). Repeatable for layered configs. "
             "Config files define org-level settings, types, grades, etc. "
             "Data file can add new definitions but cannot override config names.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run validation only — print errors as JSON, do not write a file.",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print the resolved merged config as YAML (with per-key '# from: FILE' "
             "provenance comments) and exit. Does not build or write an .anx.",
    )
    parser.add_argument(
        "--geo-data",
        help="Path to a JSON or YAML file with geo coordinate data "
             "(key -> [lat, lon] mapping). Populates settings.extra_cfg.geo_map.data.",
    )

    args = parser.parse_args(argv)

    # Require --output unless --validate-only or --show-config
    if not args.validate_only and not args.show_config and not args.output:
        parser.error("-o/--output is required unless --validate-only or --show-config is set")

    # Build chart: config files first, then data
    chart = ANXChart()

    # Provenance map: flat_path -> source filename (only populated when --show-config)
    provenance: dict = {}
    prev_snapshot: dict = {}

    # Apply config files in order
    for cfg_path in args.config:
        p = Path(cfg_path)
        if not p.exists():
            print(f"Error: config file not found: {cfg_path}", file=sys.stderr)
            sys.exit(1)
        try:
            chart.apply_config_file(cfg_path)
        except (json.JSONDecodeError, ValueError) as exc:
            print(json.dumps({"error": f"Failed to parse config {cfg_path}: {exc}"}),
                  file=sys.stderr)
            sys.exit(1)
        if args.show_config:
            curr_snapshot = chart.to_config_dict()
            for path in _diff_config(prev_snapshot, curr_snapshot):
                provenance[path] = Path(cfg_path).name
            prev_snapshot = curr_snapshot

    # Load and apply data file (if provided). Skip data reading in
    # --show-config mode when no input was explicitly given — it's a
    # pure config-inspection tool and blocking on stdin would surprise users.
    data_file_provided = args.input is not None
    if data_file_provided or (not args.show_config and not args.config):
        try:
            data = _load_input(args.input)
        except (json.JSONDecodeError, ValueError) as exc:
            print(json.dumps({"error": f"Failed to parse input: {exc}"}), file=sys.stderr)
            sys.exit(1)

        # Apply CLI overrides to settings in the data dict
        settings = data.get("settings", {}) or {}
        extra = dict(settings.get("extra_cfg") or {})
        if args.geo_data:
            geo_map = dict(extra.get("geo_map") or {})
            geo_file = Path(args.geo_data)
            if not geo_file.exists():
                print(f"Error: geo-data file not found: {args.geo_data}", file=sys.stderr)
                sys.exit(1)
            try:
                geo_text = geo_file.read_text(encoding="utf-8")
                if geo_file.suffix.lower() in (".yaml", ".yml"):
                    import yaml
                    geo_raw = yaml.safe_load(geo_text)
                else:
                    geo_raw = json.loads(geo_text)
            except (json.JSONDecodeError, ValueError) as exc:
                print(json.dumps({"error": f"Failed to parse geo-data: {exc}"}),
                      file=sys.stderr)
                sys.exit(1)
            geo_map["data"] = geo_raw
            extra["geo_map"] = geo_map
        if extra:
            settings["extra_cfg"] = extra
        data["settings"] = settings

        chart._apply_data(data)
        if args.show_config:
            curr_snapshot = chart.to_config_dict()
            data_src = Path(args.input).name if args.input else "<stdin>"
            for path in _diff_config(prev_snapshot, curr_snapshot):
                provenance[path] = data_src
            prev_snapshot = curr_snapshot
    else:
        # Config-only mode: apply CLI overrides directly to chart settings
        if args.geo_data:
            from .models import GeoMapCfg
            geo_file = Path(args.geo_data)
            if not geo_file.exists():
                print(f"Error: geo-data file not found: {args.geo_data}", file=sys.stderr)
                sys.exit(1)
            try:
                geo_text = geo_file.read_text(encoding="utf-8")
                if geo_file.suffix.lower() in (".yaml", ".yml"):
                    import yaml
                    geo_raw = yaml.safe_load(geo_text)
                else:
                    geo_raw = json.loads(geo_text)
            except (json.JSONDecodeError, ValueError) as exc:
                print(json.dumps({"error": f"Failed to parse geo-data: {exc}"}),
                      file=sys.stderr)
                sys.exit(1)
            if chart.settings.extra_cfg.geo_map is None:
                chart.settings.extra_cfg.geo_map = GeoMapCfg()
            chart.settings.extra_cfg.geo_map.data = geo_raw

    # --show-config: print resolved config and exit (no validate, no build)
    if args.show_config:
        final_config = chart.to_config_dict()
        sys.stdout.write(_render_annotated_config(final_config, provenance))
        sys.exit(0)

    # Validate-only mode
    if args.validate_only:
        errors = chart.validate()
        if errors:
            print(json.dumps(errors, indent=2), file=sys.stderr)
            sys.exit(1)
        else:
            print(json.dumps([], indent=2))
            sys.exit(0)

    # Build and write
    try:
        out_path = args.output
        if not out_path.lower().endswith(".anx"):
            out_path += ".anx"
        abs_path = chart.to_anx(out_path)
        print(abs_path)
    except ANXValidationError as exc:
        print(json.dumps(exc.errors, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

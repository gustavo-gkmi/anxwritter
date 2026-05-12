# CLI Reference

Command-line interface for converting JSON/YAML data files into `.anx` files.

> For an end-to-end walk-through of writing the input files (every section,
> every field, plus YAML gotchas) see the
> [YAML / JSON Guide](../guide/yaml-json-guide.md).

---

## Entry point

```
anxwritter
```

Installed as a console script via the `anxwritter = "anxwritter.cli:main"` entry point in `pyproject.toml`.

---

## Synopsis

```
anxwritter [OPTIONS] [INPUT_FILE]
```

---

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `INPUT_FILE` | no | Path to a JSON or YAML data file. When omitted, reads from stdin (pipe mode) or uses config-only mode if `--config` is provided. |

---

## Options

| Flag | Long form | Description |
|------|-----------|-------------|
| `-o` | `--output` | Output `.anx` file path. The `.anx` extension is added automatically if missing. Required unless `--validate-only` or `--show-config` is set. |
| | `--config` | Path to a config file (YAML or JSON). Repeatable -- multiple flags are applied in order (layered, additive merge). See [constructors.md](constructors.md) for config file shape and conflict detection. |
| | `--config-replace` | Like `--config`, but every section this layer mentions REPLACES the chart's current state for that section wholesale. Sections the layer does not mention survive untouched. Repeatable; freely interleaves with `--config` (cross-flag CLI order is preserved). |
| | `--validate-only` | Validate the input data without writing an output file. Prints validation errors to stderr as JSON; exits `0` with `[]` on stdout when valid. |
| | `--show-config` | Print the resolved merged config as YAML to stdout, with inline `# from: FILE` provenance comments on every leaf, then exit `0`. Does not validate or build. `-o` is not required. |
| | `--geo-data` | Path to a JSON or YAML file with a `key -> [lat, lon]` mapping. Populates `settings.extra_cfg.geo_map.data` for geographic positioning. |

---

## Input formats

The CLI accepts JSON and YAML files. Format is detected from the file extension (`.json` or `.yaml`/`.yml`). The file content must follow the `from_dict()` structure documented in [constructors.md](constructors.md).

---

## Stdin pipe mode

When no `INPUT_FILE` is provided, the CLI reads from stdin.

```bash
cat input.json | anxwritter -o output/chart.anx
```

---

## Config layering

`--config` and `--config-replace` can both be repeated and freely interleaved. Order
is preserved across the two flags, and the merge mode is decided per-layer at the
moment that layer is processed.

```bash
# All layers merge in (additive)
anxwritter --config base.yaml --config project.yaml data.json -o output/chart.anx

# Mix merge and replace — base merges, narrow replaces sections it mentions
anxwritter --config base.yaml --config-replace narrow.yaml data.json -o output/chart.anx

# --config-replace alone (single replace layer)
anxwritter --config-replace project.yaml data.json -o output/chart.anx
```

The default (`--config`) is additive: same-name entries in named-registry sections
upsert (later wins), `source_types` and `grades_*.items` append with case-sensitive
exact-text dedup, `settings` deep-merges, `legend_items` / `palettes` always append.
`--config-replace` makes a layer wipe each section it touches before applying its
own entries — useful when an override needs to *narrow* a base catalog rather than
extend it. See [constructors.md](constructors.md#layered-configs) for the full
per-section rule table.

When `--config` is provided without an `INPUT_FILE`, a config-only chart is created (no entities or links).

```bash
anxwritter --config org_defaults.yaml -o output/empty_chart.anx
```

---

## Inspecting the resolved config

`--show-config` prints the merged config (after all `--config` layers and any data-file `settings` overrides have been applied) as YAML, with a `# from: FILE` comment on every leaf key showing which source last set the value. Useful for debugging layered configs.

```bash
anxwritter --show-config --config company.yaml --config project.yaml
anxwritter --show-config --config company.yaml --config project.yaml data.json
```

Exits `0` without building or writing an `.anx`. Stdin is not read when no input path is given, so the command never blocks.

---

## Geographic positioning data

`--geo-data` points at an external file containing a `key -> [lat, lon]` lookup table — typically a long list that would bloat a config file. The data is injected into `settings.extra_cfg.geo_map.data`; the rest of the geo_map config (matching attribute, mode, projection size) still comes from `--config` or the data file.

```bash
anxwritter --config org.yaml --geo-data coords.json data.json -o output/chart.anx
```

The file is a flat top-level mapping of key → `[lat, lon]`. JSON and YAML are
both accepted; pick by file extension.

`coords.json`:

```json
{
  "New York": [40.7128, -74.0060],
  "London": [51.5074, -0.1278],
  "Tokyo": [35.6762, 139.6503]
}
```

`coords.yaml`:

```yaml
New York: [40.7128, -74.0060]
London: [51.5074, -0.1278]
Tokyo: [35.6762, 139.6503]
```

---

## Exit codes

| Code | Meaning | Output |
|------|---------|--------|
| `0` | Success | Absolute path of the written `.anx` file printed to stdout. |
| `1` | Error | Validation errors printed to stderr as JSON. |

---

## Examples

```bash
# Convert JSON to ANX
anxwritter input.json -o output/chart.anx

# Convert YAML to ANX
anxwritter input.yaml -o output/chart.anx

# With config file
anxwritter --config org_defaults.yaml data.json -o output/chart.anx

# Multiple layered configs (additive merge)
anxwritter --config config.yaml --config overrides.yaml data.json -o output/chart.anx

# Mix --config (merge) and --config-replace (wipe-and-set per section)
anxwritter --config base.yaml --config-replace narrow.yaml data.json -o output/chart.anx

# Config-only (no entity/link data)
anxwritter --config org_defaults.yaml -o output/empty_chart.anx

# Read from stdin
cat input.json | anxwritter -o output/chart.anx

# Validate only (no file written)
anxwritter --validate-only input.json

# Inspect the resolved merged config (with provenance comments)
anxwritter --show-config --config company.yaml --config project.yaml

# Geographic positioning from an external coords file
anxwritter --config org.yaml --geo-data coords.json data.json -o output/chart.anx
```

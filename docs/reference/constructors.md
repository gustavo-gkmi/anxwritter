# Constructors and Config Files

All methods for creating an `ANXChart` from structured data: dicts, JSON, YAML, and config files.

> Driving anxwritter from YAML or JSON files (rather than from Python)?
> See the [YAML / JSON Guide](../guide/yaml-json-guide.md) for a practical
> walk-through of every section, plus YAML-specific gotchas (date/time
> quoting, `yes`/`no` boolean sentinels, enum string forms, the
> `name`-vs-`label` legend item trap).

---

## `ANXChart.from_dict(data)`

Creates a chart from a Python dict. All other constructors (`from_json`, `from_yaml`, config files) delegate to `from_dict` internally.

### Dict structure

```python
data = {
    # Settings (optional)
    "settings": { ... },

    # Entity data, keyed by representation type (optional)
    "entities": {
        "icons":        [ {...}, {...} ],
        "boxes":        [ {...}, {...} ],
        "circles":      [ {...}, {...} ],
        "theme_lines":  [ {...}, {...} ],
        "event_frames": [ {...}, {...} ],
        "text_blocks":  [ {...}, {...} ],
        "labels":       [ {...}, {...} ],
    },

    # Link data (optional)
    "links": [ {...}, {...} ],

    # Grade collections (optional, dict with default/items or GradeCollection)
    "grades_one":   {"items": ["Always reliable", "Usually reliable"]},
    "grades_two":   {"default": "Confirmed", "items": ["Confirmed", "Probably true"]},
    "grades_three": {"items": ["High", "Medium", "Low"]},

    # Source type hints (optional, List[str])
    "source_types": ["Witness", "Informant"],

    # Type definitions (optional, List[dict])
    "entity_types":     [ {"name": "Person", "icon_file": "person", "color": "Blue"} ],
    "link_types":       [ {"name": "Call", "color": 255} ],
    "attribute_classes": [ {"name": "Phone", "type": "text", "prefix": "Tel: "} ],
    "strengths":        {"items": [{"name": "Confirmed", "dot_style": "solid"}]},
    "datetime_formats": [ {"name": "ISO", "format": "yyyy-MM-dd"} ],

    # Legend items (optional, List[dict])
    "legend_items": [ {"name": "Person", "item_type": "Icon"} ],

    # Palette definitions (optional, List[dict])
    "palettes": [ {"name": "Standard", "entity_types": ["Person"]} ],

    # Semantic type definitions (optional, List[dict])
    "semantic_entities":   [ {"name": "Suspect", "kind_of": "Person"} ],
    "semantic_links":      [ {"name": "Intercepted Call", "kind_of": "Phone Call To"} ],
    "semantic_properties": [ {"name": "CPF Number", "base_property": "Abstract Text"} ],
}
```

### Entity keys

The `"entities"` dict uses these keys, each mapping to the corresponding entity class:

| Key | Entity class |
|-----|-------------|
| `icons` | `Icon` |
| `boxes` | `Box` |
| `circles` | `Circle` |
| `theme_lines` | `ThemeLine` |
| `event_frames` | `EventFrame` |
| `text_blocks` | `TextBlock` |
| `labels` | `Label` |

Each item in the list is a dict of keyword arguments passed to the entity class constructor.

---

## `ANXChart.from_json(source)` / `ANXChart.from_json_file(path)`

### `from_json(source: str) -> ANXChart`

Creates a chart from a raw JSON string. The string is parsed with `json.loads()` and passed to `from_dict()`.

```python
chart = ANXChart.from_json('{"settings": {...}, "entities": {"icons": [...]}, "links": [...]}')
```

### `from_json_file(path: str) -> ANXChart`

Creates a chart from a JSON file path.

```python
chart = ANXChart.from_json_file('data/my_chart.json')
```

---

## `ANXChart.from_yaml(source)` / `ANXChart.from_yaml_file(path)`

### `from_yaml(source: str) -> ANXChart`

Creates a chart from a raw YAML string. Uses `yaml.safe_load` internally, then delegates to `from_dict`.

```python
chart = ANXChart.from_yaml("""
settings:
  extra_cfg:
    arrange: grid
entities:
  icons:
    - id: Alice
      type: Person
      color: Blue
links:
  - from_id: Alice
    to_id: Bob
    type: Call
    arrow: '->'
""")
```

### `from_yaml_file(path: str) -> ANXChart`

Creates a chart from a YAML file path.

```python
chart = ANXChart.from_yaml_file('data/my_chart.yaml')
```

---

## Config files

Config files separate org-level chart configuration from entity/link data. A config file uses the same dict structure as `from_dict()` but contains **only** configuration sections. The `entities` and `links` keys are silently ignored if present.

### Config file shape

A config file can contain any combination of:

| Section | Description |
|---------|-------------|
| `settings` | Chart-level settings (all groups) |
| `entity_types` | EntityType definitions |
| `link_types` | LinkType definitions |
| `attribute_classes` | AttributeClass definitions |
| `strengths` | Strength definitions |
| `datetime_formats` | DateTimeFormat definitions |
| `palettes` | Palette definitions |
| `grades_one` | Source reliability grade labels |
| `grades_two` | Information reliability grade labels |
| `grades_three` | Third dimension grade labels |
| `source_types` | Source type dropdown labels |
| `legend_items` | Legend item definitions |
| `semantic_entities` | Entity semantic type definitions |
| `semantic_links` | Link semantic type definitions |
| `semantic_properties` | Property semantic type definitions |

### Loading a config

```python
# Via constructor argument
chart = ANXChart(config_file='org_defaults.yaml')

# Via constructor with dict
chart = ANXChart(config={'entity_types': [{'name': 'Person', 'icon_file': 'person'}]})

# Via classmethod (from file)
chart = ANXChart.from_config_file('org_defaults.yaml')

# Via classmethod (from JSON or YAML string -- auto-detects format)
chart = ANXChart.from_config('{"entity_types": [...]}')
```

### Layered configs

Apply multiple config files in order. Each layer **field-merges** into the chart by
default. Three opt-in knobs change a layer's behaviour: `wipe_previous=True`
(clear each section the layer mentions, then merge), `operation='delete'`
(subtract by shape), and `lock=True` (freeze the leaves this layer declares).

```python
chart = ANXChart()
chart.apply_config_file('base.yaml')
chart.apply_config_file('project_overrides.yaml')          # field-merge (default)
chart.apply_config_file('narrow.yaml', wipe_previous=True)  # clear-and-set per section
chart.apply_config_file('strip.yaml', operation='delete')   # remove entries/fields

# Now add entities and links:
chart.add_icon(id='Alice', type='Person')
```

#### Per-section merge rules (default)

| Section | Rule |
|---|---|
| `settings` | Deep merge per leaf — only leaves the layer sets overwrite. |
| `entity_types`, `link_types`, `attribute_classes`, `datetime_formats`, `semantic_entities/links/properties`, `strengths.items`, `extra_cfg.display_attribute` / `display_label` | **Field-merge by identity** (`name` / `key`) — a later layer's declared fields merge into the same-identity entry; omitted fields are retained; new identities are appended. |
| `strengths.default`, `grades_*.default` | Later wins if non-None, otherwise the earlier layer's default is kept. |
| `source_types`, `grades_one/two/three.items` | Append with **case-sensitive exact-text dedup**. |
| `legend_items`, `palettes` | Always append — no natural key. |

> **Note:** the public single-call builders (`add_entity_type`, `add_attribute_class`,
> …) still REPLACE wholesale on a repeated `name`. Field-merge applies only to config
> *layering* (`apply_config*`).

#### `wipe_previous=True`

Clears every section the layer mentions, then merges. Sections the layer does not
mention survive untouched. Use to *narrow* a base catalog to a subset.

```python
chart.apply_config_file('full_catalog.yaml')
chart.apply_config({'source_types': ['Witness', 'Officer']}, wipe_previous=True)
# entity_types, grades, settings, etc. from full_catalog.yaml all survive.
```

#### `lock=True` (immutable baselines)

Freezes exactly the leaves the layer declares. A later config layer that changes a
locked leaf records a `locked_override` validation error and the locked value is
kept (a later layer may still *add* unrelated leaves/entries). Built for "an org
config the user can't alter, then a user preset layered on top":

```python
chart.apply_config_file('org.yaml', lock=True, source_name='org')
chart.apply_config(user_preset, source_name='user_preset')
errors = chart.validate()   # any override of an org-locked leaf surfaces here,
                            # tagged with source='user_preset' + config_source='org'
```

#### `operation='delete'`

Subtract by shape (the mirror of merge): a key with a null/empty value removes the
whole section/entry; a list entry with only its identity removes that entry; an entry
naming fields (which must be `null`) unsets those fields. A non-null value on a
non-identity field is a `delete_contract` error; deleting an absent target is a no-op.
`operation='delete'` combined with `lock` or `wipe_previous` is a `ValueError`.

```python
chart.apply_config({'attribute_classes': [{'name': 'CPF'}]}, operation='delete')      # drop CPF
chart.apply_config({'attribute_classes': [{'name': 'CPF', 'prefix': None}]},
                   operation='delete')  # keep CPF, unset just its prefix
```

### Applying config to an existing chart

```python
chart.apply_config(data_dict)         # from a dict
chart.apply_config_file('path.yaml')  # from a file
```

### Tagging layers with `source_name`

When you layer multiple configs (a bundled template + a user override, for
example), `validate()` errors can identify which layer set the offending
entry. Pass `source_name=` to tag every entry the call contributes:

```python
chart.apply_config(bundled_dict, source_name='org_defaults')
chart.apply_config_file('project.yaml')   # auto-derives 'project.yaml' from the path
chart.apply_config(user_dict, source_name='inline override')
```

`apply_config_file` and `from_config_file` default `source_name` to
`Path(path).name` (just the basename). Pass an explicit value to override
with a logical layer name. `apply_config` and `from_config` accept no
default — pass one if you want attribution.

Each validation error that originated from a tagged entry then carries an
optional `source` key:

```python
errors = chart.validate()
# errors[i] == {
#   'type': 'unknown_color',
#   'location': 'entity_types[2]',
#   'message': "...",
#   'source': 'project.yaml',   # ← present only when known
# }
```

`config_conflict` errors gain a separate `config_source` key identifying
the layer that locked the original entry (the data file is the other
side). `ANXValidationError`'s formatted message string appends
`(source: X)` per line, but that string format is **explicitly
unstable** — match on the error dict's `type` / `location` keys, not the
message text.

### Exporting config

Save the current chart configuration (without entities/links) for reuse.

```python
chart.to_config('exported_config.yaml')   # writes file, returns absolute path
config_dict = chart.to_config_dict()      # returns plain dict
```

---

## Config conflict detection

When a config is applied (via `config_file`, `--config`, `apply_config`, or `apply_config_file`), all named definitions and list-based sections are **locked**. Subsequent data loading enforces the following rules:

| Section | Same name + identical specs | Same name + different specs | New name |
|---------|----------------------------|----------------------------|----------|
| `entity_types` | Silent skip | `config_conflict` error | Allowed |
| `link_types` | Silent skip | `config_conflict` error | Allowed |
| `attribute_classes` | Silent skip | `config_conflict` error | Allowed |
| `strengths` | Silent skip | `config_conflict` error | Allowed |
| `datetime_formats` | Silent skip | `config_conflict` error | Allowed |
| `grades_one` / `grades_two` / `grades_three` | Silent skip | `config_conflict` error | N/A (list, not named) |
| `source_types` | Silent skip | `config_conflict` error | N/A (list, not named) |
| `settings` | Merge (data wins on key conflicts) | Merge (data wins) | Merge |
| `legend_items` | Always append | Always append | Always append |

Conflict errors are collected at validate/build time (not parse time). Each error dict includes: `type` (`"config_conflict"`), `section`, `name`, `message`, `config_value`, and `data_value`.

When **no config** is applied (`_has_config` is `False`), conflict detection is disabled and `from_dict()` behaves as normal.

### Internal tracking

| Internal attribute | Type | Description |
|--------------------|------|-------------|
| `_config_locked` | `Dict[str, Dict[str, dict]]` | section name -> {entry name: asdict} of locked entries |
| `_config_locked_grades` | `Dict[str, GradeCollection]` | grade key (`grades_one`/`two`/`three`) -> locked `GradeCollection` |
| `_config_locked_source_types` | `Optional[List[str]]` | locked source_types list (`None` until a config sets it) |
| `_config_conflicts` | `List[Dict[str, Any]]` | Collected conflict errors |
| `_has_config` | `bool` | `True` after any `apply_config()` call |

---

## CLI `--config` / `--config-wipe` / `--config-delete` / `--config-lock`

All four flags can be repeated and freely interleaved; order is preserved across
them. Each layer applies its own mode at the moment it is processed.

```bash
# Single config
anxwritter --config org.yaml data.json -o output/chart.anx

# Layered merges (applied in order)
anxwritter --config base.yaml --config project.yaml data.json -o output/chart.anx

# Mix merge and wipe — base merges in, narrow clears sections it mentions then sets them
anxwritter --config base.yaml --config-wipe narrow.yaml data.json -o output/chart.anx

# Locked org baseline + user preset (preset may add, not alter org-locked leaves)
anxwritter --config-lock org.yaml --config user.yaml --validate-only data.json

# Config-only (no data file)
anxwritter --config org.yaml -o output/empty_chart.anx
```

See [cli.md](cli.md) for full CLI reference.

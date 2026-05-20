# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.11.0] - 2026-05-20

### Added

- **`extra_cfg.display_templates`** — multi-attribute synthesizer that
  renders one or more source attribute values through a Python
  `str.format_map`-style template and emits the result either as a
  synthesized text-sibling `AttributeClass` (`target='attribute'`,
  default) or directly into the entity/link label (`target='label'`).
  Sister synthesizer to `date_attribute_displays`; both coexist (neither
  deprecates the other).
  - **Template syntax**: Python f-string format-spec mini-language via
    `str.format_map`. No code execution; supports `{alias}`,
    `{alias:format_spec}` including `{x:,.2f}`, `{x:>10}`,
    `{d:%d/%m/%Y}`. Write the body of an f-string without the `f` prefix
    (which is Python source syntax, not part of the template).
  - **Two target slots, picked per entry**:
    `target='attribute'` synthesizes a text AC named via `attribute_name`
    (default `'display'`); source ACs must declare `visible=False`.
    `target='label'` writes to the entity/link label; default
    `override_existing=False` preserves manually-set labels (consistent
    with the library convention that explicit wins over calculated; flip
    to `True` for chart-wide consistency).
  - **Source aliases** via `DisplaySource.alias`: required when an AC
    name isn't a valid Python identifier (spaces, accents, etc).
    Optional otherwise — the attribute name is reused as the template key.
  - **Per-source missing policy** (`'skip'` default / `'substitute'` /
    `'error'`) with per-source `placeholder` for `substitute`.
  - **Number formatting**: top-level `decimal_separator` /
    `thousand_separator` swap separators in numeric format-spec output
    only. Static template text (e.g. literal commas) is untouched. Useful
    for Brazilian-style `100.000,50` formatting without any locale
    machinery.
  - **Datetime sources**: source ACs declaring `type='datetime'` are
    auto-parsed back to `datetime.datetime` before binding so
    `{d:%d/%m/%Y}` style specs work directly.
  - New dataclasses: `DisplayTemplate`, `DisplaySource`. New enum
    `DisplayTarget` (`'attribute'` | `'label'`). New top-level exports.
  - New chart method: `chart.add_display_template(target=..., template=...,
    sources=[...], ...)`. Generic `chart.add(DisplayTemplate(...))`
    dispatch also routes here.
  - New `ErrorType` members: `DISPLAY_TEMPLATE_INVALID` (structural
    issues + per-item `missing='error'`) and
    `DISPLAY_TEMPLATE_NAME_COLLISION` (synthesized name collides with
    an explicit AC, with another `display_templates` entry, or with any
    `date_attribute_displays` sibling).
  - New example `examples/display_templates_example.py` covering both
    targets, datetime sources, BR separators, and mixed-target charts.
  - **Note for users coming from "stacked attributes look messy on the
    canvas"**: declare a `display_templates` entry that combines the
    relevant source ACs into one formatted string and either set source
    ACs `visible=False` (so the synthesized sibling replaces the stack)
    or pick `target='label'` to get the summary onto the link's label
    line. See `docs/reference/attributes.md` § Display templates.

## [1.10.2] - 2026-05-19

### Changed

- **`AttributeClass.ShowValue` is now always emitted, defaulting to `"true"`.**
  Previously omitted from the XML when `show_value` was unset, leaving ANB to
  apply its own default. The default was assumed to be `true` (and documented
  as such), but ANB's silent fallback for an omitted `ShowValue` is actually
  `false` — so any attribute class that didn't explicitly set `show_value=True`
  rendered with no visible value on the canvas. The library now emits
  `ShowValue="true"` by default, matching what 99% of charts want. To hide a
  value, set `show_value=False` explicitly (emits `ShowValue="false"`).
  Behavioural impact: attribute values that previously rendered blank on the
  canvas will now render. Charts that intentionally relied on the silent-hide
  behaviour (none known) need to add `show_value: false` to the affected ACs.

### Documentation

- Added gotcha #11 to the YAML/JSON guide: quote `prefix:` / `suffix:` (and
  `separator:` on `extra_cfg.date_attribute_displays`) when leading or
  trailing whitespace is meaningful. YAML's plain-scalar parsing strips
  whitespace, so an unquoted `prefix: R$ ` silently becomes `'R$'`. JSON and
  the Python API are unaffected.

## [1.10.1] - 2026-05-19

### Breaking

- **`canvas_display` on `AttributeClass` was removed** and replaced with a
  chart-level synthesizer under `extra_cfg.date_attribute_displays`. The
  field-on-AC shape forced an arbitrary "owner" choice and didn't generalize
  to date ranges (two source ACs, no natural owner). The new shape sits
  alongside `styling` / `geo_map` / `entity_auto_color` — same chart-level
  synthesizer family. Since v1.10.0 had been live for hours when the redesign
  shipped and the lib has no known external consumers of `canvas_display`,
  this is treated as a hotfix patch rather than a major version bump.
- The `CanvasDisplay` dataclass was renamed to `DateAttributeDisplay`. Both
  the top-level export (`anxwritter.CanvasDisplay`) and the field
  (`AttributeClass.canvas_display`) are gone.
- `ErrorType` members renamed:
  `ATTTIME_VISIBLE_FORBIDS_CANVAS_DISPLAY` → `DATETIME_AC_FORBIDS_VISIBLE`;
  `CANVAS_DISPLAY_INVALID` → `DATE_DISPLAY_INVALID`;
  `CANVAS_DISPLAY_NAME_COLLISION` → `DATE_DISPLAY_NAME_COLLISION`.

### Added

- **`extra_cfg.date_attribute_displays`** — opt-in chart-level synthesizer
  that replaces v1.10.0's `canvas_display`. Each entry declares a synthesised
  text-sibling AttributeClass derived from one (single-date) or two (range)
  datetime ACs. Range mode renders both bounds into one canvas-visible string
  via `start`, `end`, `name`, `separator`, and a `format` shared by both
  bounds.
  - **Missing-bound policies** for range mode: `missing='skip'` (default),
    `'substitute'` (with per-bound `start_placeholder` / `end_placeholder`,
    e.g. `'ongoing'` for open-ended investigations), `'truncate'` (render
    the present bound alone, no separator), or `'error'` (surface
    `date_display_invalid` per item at `validate()` time).
  - **Source ACs must declare `visible=False` explicitly.** The transform no
    longer mutates user-declared ACs. Validation emits `date_display_invalid`
    with a fix-it message naming the AC, the display index, and the
    `visible=False` requirement. The cross-cutting "any datetime AC with
    `visible=True` is rejected" rule (`datetime_ac_forbids_visible`) remains
    in place independently.
  - **Range mode requires an explicit `name`** — there's no natural single-AC
    base to auto-derive from. Single-date mode keeps the
    `f"{start}{suffix}"` auto-derivation with `suffix` defaulting to
    `' (display)'`.
  - **Sibling-name collisions** surface as `date_display_name_collision`
    against either explicit ACs or other displays.
  - YAML/JSON form: a list under `settings.extra_cfg.date_attribute_displays`.
    `AttributeClass` styling template is supported under each entry's
    `attribute_class` field (inner `.name` and `.type` must be `None`, same
    as v1.10.0).
- New top-level export: `DateAttributeDisplay`.
- New chart method: `chart.add_date_attribute_display(start=..., end=..., name=..., ...)`.
- New example `examples/date_attribute_displays_example.py` — single-date,
  range, and range-with-substitute charts.

## [1.10.0] - 2026-05-19

### Added
- **`canvas_display` on `AttributeClass`** — opt-in workaround for ANB v9 not
  rendering `datetime` attribute values on the canvas after `.anx` import.
  When set on a `datetime` AC, anxwritter emits a paired text sibling AC named
  `<parent.name><suffix>` plus a formatted-string sibling attribute on every
  entity/link that carries the parent. The parent's `visible` is forced to
  `False`; the sibling defaults to `visible=True` + `show_value=True` so the
  formatted date actually renders. The original `datetime` parent is still
  emitted, so the properties panel, time-wheel, sort, and filter keep working.
  - Three accepted forms, all normalized to `CanvasDisplay` internally:
    `canvas_display=True` (defaults), `canvas_display={'format': '%d/%m/%Y'}`
    (dict shortcut), `canvas_display=CanvasDisplay(format=..., suffix=...,
    attribute_class=AttributeClass(prefix=..., font=Font(italic=True)))`
    (full control). Default `format` is `'%Y-%m-%d'` (ISO, locale-neutral);
    default `suffix` is `' (display)'`.
  - YAML equivalent supports the same three forms, including
    `canvas_display: true` shorthand and the nested-dict form. The sibling AC's
    inner `attribute_class.name` and `.type` must be `None` — the sibling is
    auto-named (`<parent>+suffix`) and auto-typed as text. No inheritance
    from the parent.
  - New top-level export: `CanvasDisplay` (also accepts dict-shape coercion
    for `attribute_class` and nested `font` via the Python API).
  - New `ErrorType` members:
    - `ATTTIME_VISIBLE_FORBIDS_CANVAS_DISPLAY` — `type=datetime` +
      `visible=True` is rejected with or without `canvas_display`, since ANB
      would render the chrome with no value either way.
    - `CANVAS_DISPLAY_INVALID` — `canvas_display` on a non-`datetime` AC,
      `canvas_display.attribute_class.name` or `.type` set (must be `None`),
      or an unparseable `strftime` format.
    - `CANVAS_DISPLAY_NAME_COLLISION` — the derived sibling name collides with
      another explicit AC, or two parents resolve to the same sibling name.
- New example `examples/canvas_display_example.py` — baseline vs workaround
  charts to open side-by-side in ANB.

## [1.9.0] - 2026-05-19

### Added
- **Data-driven link styling** under `extra_cfg.styling.links`. Two pure-function
  styling modes that share precedence rules and missing-value policy:
  - `intensity`: numeric link attribute → `line_width` and/or `line_color`
    via a configurable scale (`linear` / `log` / `sqrt` / `power` / `quantile`)
    and a color ramp (`rgb` / `rgb_linear` (default) / `hsl` spaces; multi-stop
    ramps; optional `diverging: true` + `midpoint` for symmetric mapping).
    Domain can be auto, explicit `[min, max]`, or `robust` (5th/95th percentile,
    immune to single outliers).
  - `categorical`: string link attribute → style lookup. Each style entry can
    set `line_color`, `line_width`, and `strength` (named strength must be
    registered separately). Case-insensitive and accent-insensitive by default,
    matching the `geo_map` convention; both flags overridable. Optional `default`
    for unmatched values.
  - Both modes support `legend: true` for auto-emitted `LegendItem` rows
    (intensity samples N points in scale-space; categorical emits one row per
    `styles` entry in insertion order).
  - Precedence: **explicit per-link > categorical > intensity >
    `link_match_entity_color` > LinkType default**. An explicit
    `Link.line_color` always beats every data-driven rule.
  - New dataclasses (all importable from top-level): `StylingCfg`,
    `LinkStylingCfg`, `IntensityCfg`, `IntensityWidthCfg`, `IntensityColorCfg`,
    `CategoricalCfg`, `CategoricalStyleCfg`. New enums: `IntensityScale`,
    `ColorSpace`, `MissingPolicy`.
  - New `ErrorType` members: `INVALID_INTENSITY_CONFIG`,
    `INVALID_INTENSITY_ATTRIBUTE`, `INVALID_INTENSITY_DOMAIN`,
    `INVALID_INTENSITY_RANGE`, `INVALID_INTENSITY_RAMP`,
    `INVALID_CATEGORICAL_CONFIG`, `INVALID_CATEGORICAL_ATTRIBUTE`,
    `INVALID_CATEGORICAL_STYLE`, `STYLING_CONFLICT`. Both intensity and
    categorical targeting the same attribute is a `STYLING_CONFLICT` error —
    the user must pick one (mixed numeric-and-lookup styling on the same
    attribute has ambiguous precedence).
- New example `examples/link_styling.py` — fictional money-flow chart using
  log-scale intensity on `Amount` and categorical color on `source_type`.
- New colors helpers (public): `lerp_rgb`, `lerp_rgb_linear`, `lerp_hsl`,
  `interpolate_ramp` in `anxwritter.colors`.
- New transforms (public): `apply_scale`, `resolve_intensity_domain` in
  `anxwritter.transforms`, exposed for users who want to reuse the same scale
  math outside the styling pipeline.

### Scope policy

> anxwritter supports two kinds of data-driven styling: **continuous** (numeric
> attribute → scale → width/color) and **categorical** (attribute value → style
> lookup). Both are pure functions of a single attribute. Anything that
> involves conditions across multiple attributes, range comparisons on text,
> regex matching, or computed predicates is business logic — compute the
> result in your data pipeline and either set `line_color` / `line_width`
> explicitly per link, or precompute a synthetic attribute upstream (e.g.
> `risk_class: "high"`) and use categorical on that.

## [1.8.0] - 2026-05-15

### Added
- `source_name` keyword argument on `apply_config`, `apply_config_file`,
  `from_config`, and `from_config_file`. Tags every entry the layer
  contributes (entity types, link types, attribute classes, strengths,
  datetime formats, grades, source types) with that string. When set,
  `validate()` enriches every error dict that originates from a tagged
  entry with an optional `source` key identifying the layer that produced
  the offending entry. Aimed at downstream tools layering a bundled config
  + a user config + data, where "which file broke?" is otherwise hard to
  answer.
- `config_source` key on `config_conflict` error dicts — identifies the
  config layer that locked the original entry the data file is now
  trying to redefine.
- `apply_config_file` and `from_config_file` auto-default `source_name`
  to `Path(path).name` (basename). Pass an explicit `source_name=` to
  override with a logical layer name.

### Changed
- `ANXValidationError` message string now appends a `(source: X)` suffix
  to each error line that carries a `source` key (or `(config source: X)`
  for `config_conflict` errors with `config_source`). The exception
  message string format is explicitly documented as **unstable** — match
  on the error dict's `type` and `location` keys, not the formatted
  message text. The error dict shape (`type`, `location`, `message`,
  optional `source`/`config_source`) remains the stable contract.
  Non-breaking for anyone consuming the dicts; potentially affects callers
  that regex-match `str(exc)`.

## [1.7.2] - 2026-05-13

### Added
- README shields: PyPI version, Python versions, License, PyPI monthly downloads.
- README hero image (`.github/hero.png`) — composite of charts built with
  anxwritter (timeline of transfers, trafficking network, theme lines +
  event frames, link styles, auto-colored entities), shown above the
  audience hook.

### Fixed
- `validate()` now rejects `semantic_type` values that aren't registered via
  `add_semantic_entity` / `add_semantic_link` / `add_semantic_property` and
  don't start with `guid`. Previously these were silently passed through and
  emitted into `SemanticTypeGuid`, which ANB then rejected at load time with
  a cryptic XSD/`xs:NCName` error pointing at the wrong line of the file.
  The check covers all five emission sites: `EntityType.semantic_type`,
  `LinkType.semantic_type`, `AttributeClass.semantic_type`, and per-instance
  `semantic_type` on entities and links. New `ErrorType.UNKNOWN_SEMANTIC_TYPE`.
  Raw `guid…` literals continue to pass through unchecked — they're the
  documented advanced-user escape hatch and your responsibility to keep
  resolvable in ANB.

## [1.7.1] - 2026-05-13

### Added
- `CHANGELOG.md` (this file) — release history reconstructed from git tags v1.0.0 onward.
- `Homepage`, `Documentation`, and `Changelog` entries in `[project.urls]`,
  surfaced on the PyPI sidebar.
- `.github/workflows/publish.yml` — release workflow using PyPI Trusted
  Publishing (OIDC, no long-lived token). Triggers on GitHub Release
  publication or manual `workflow_dispatch`.
- README audience hook line naming law enforcement, OSINT, and intelligence
  analysts as the target users.
- README `**Status:**` line linking to the changelog and naming 2.0 as the
  API-stabilization target.

### Changed
- README "What's in the box" reordered — differentiated features
  (geographic positioning, org-level config files, semantic types) lead;
  the auto-layout bullet now names the three force-directed algorithms
  (Fruchterman-Reingold, ForceAtlas2, tidy tree); the CLI bullet mentions
  `--show-config` and `--geo-data`.
- README disclaimer block collapsed from three blockquote paragraphs to one,
  with the full interoperability / trademark / attribution statement
  moved to [NOTICE.md](NOTICE.md).
- README documentation and `LICENSE` links rewritten to absolute GitHub
  URLs so they resolve correctly on PyPI's rendered page.
- PyPI keywords trimmed and re-targeted: dropped `i2`, `analyst-notebook`
  (collapsed into `i2-analyst-notebook`), `chart`, `xml`; added `osint`,
  `investigation`, `network-analysis`, `fraud`.

## [1.7.0] - 2026-05-12

### Changed (breaking)
- Layered configs: `source_types` and `grades_one/two/three.items` now
  append-with-exact-text-dedup across config layers instead of replacing
  wholesale. `grades_*.default` and `strengths.default` follow
  later-wins-if-non-None. Named registries (`entity_types`, `link_types`,
  `attribute_classes`, `datetime_formats`, `semantic_entities`,
  `semantic_links`, `semantic_properties`) continue to upsert-by-name as
  before — no behavior change for those in default mode.

### Added
- `replace=False` kwarg on `apply_config` / `apply_config_file` (Python API)
  and matching `--config-replace` CLI flag to opt back into per-section
  wholesale replace semantics. When `replace=True` for a given layer,
  every section the layer mentions is wiped before its entries are
  applied — including the named registries above, `palettes`,
  `legend_items`, and `settings`. Sections the layer does not mention
  survive untouched.
- `--config` and `--config-replace` can be freely interleaved on the CLI;
  the rule applies per-layer at the moment that layer is processed.

## [1.6.0] - 2026-05-11

### Changed (breaking)
- `pyyaml` promoted from optional `[yaml]` extra to a mandatory dependency.
  `pip install anxwritter[yaml]` is no longer needed (and the extra is gone) —
  `pip install anxwritter` now installs everything required to load YAML
  configs and data files.

### Added
- `.gitattributes` and `.editorconfig` to enforce LF line endings across
  the repository.

## [1.5.0] - 2026-05-09

### Changed (breaking)
- `settings.extra_cfg.geo_map.data_file` is now resolved relative to the
  config file's directory (matching Compose / Cargo / GitLab CI). Previously
  it was resolved relative to the current working directory. Inline Python
  construction, YAML/JSON parsed from strings, and the CLI `--geo-data`
  argument keep CWD-relative semantics.

### Added
- `Link.cards=[{...}]` and entity `cards=[{...}]` now accept dicts directly
  via the Python API (previously only the YAML/JSON loader did the
  coercion). Dicts become `Card` instances at construction time; anything
  else raises `TypeError`.
- Ruff lint job added to CI (Python 3.12, `ruff check anxwritter/`).

### Fixed
- Multiplicity documentation clarified.

## [1.4.0] - 2026-05-08

### Changed (breaking)
- Geo-map matching is now accent-insensitive by default — `São Paulo`,
  `SAO PAULO`, and `sao paulo` all collapse to the same key via Unicode
  NFKD fold + combining-mark strip. Set `accent_insensitive=False` on
  `GeoMapCfg` for the previous strict matching behaviour.

### Added
- Geo-map data file example.

## [1.3.1] - 2026-05-07

### Added
- New `settings.extra_cfg.layout_scale` knob — uniform spread multiplier
  applied to every `arrange` algorithm (`2.0` doubles distances, `0.5`
  halves them). Pinned positions are absolute and ignore the multiplier.

### Fixed
- ForceAtlas2 dispatcher default iteration count aligned to 60.

## [1.3.0] - 2026-05-07

### Added
- Three topology-aware layout algorithms for `settings.extra_cfg.arrange`:
  - `'fr'` — Fruchterman-Reingold (clean-room implementation of the 1991
    paper).
  - `'forceatlas2'` (alias `'fa2'`) — ForceAtlas2 (clean-room
    implementation of Jacomy et al. 2014, CC-BY).
  - `'tree'` (aliases `'reingold_tilford'`, `'tidy_tree'`) — tidy n-ary
    tree (Reingold-Tilford 1981).
  - Pinned entities (explicit `x`/`y`) act as fixed anchors for the
    force-directed modes; for tree mode pinned positions are kept verbatim.

## [1.2.0] - 2026-05-06

### Added
- New `'radial'` value for `settings.extra_cfg.arrange`, now the default
  when `arrange` is unset (previously `'circle'`). Existing layout modes
  are unchanged.

## [1.1.0] - 2026-05-06

### Added
- Entities, links, and cards can now reference a grade by name on
  `grade_one` / `grade_two` / `grade_three` (e.g. `grade_one='Reliable'`)
  in addition to the 0-based index. Names resolve against
  `chart.grades_one/two/three.items` at validate/build time.
- New `ErrorType.UNKNOWN_GRADE` for unrecognised grade names (no
  auto-create).

## [1.0.0] - 2026-05-04

### Added
- Initial public release.

[1.7.1]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.7.1
[1.7.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.7.0
[1.6.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.6.0
[1.5.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.5.0
[1.4.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.4.0
[1.3.1]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.3.1
[1.3.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.3.0
[1.2.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.2.0
[1.1.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.1.0
[1.0.0]: https://github.com/gustavo-gkmi/anxwritter/releases/tag/v1.0.0

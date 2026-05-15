# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

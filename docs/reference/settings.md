# Settings Reference

All chart-level settings live on the `Settings` dataclass in `anxwritter.models`. `Settings` is composed of 10 groups, each a separate dataclass.

```python
from anxwritter import (
    Settings, ChartCfg, Font, ViewCfg, GridCfg, WiringCfg,
    LinksCfg, TimeCfg, SummaryCfg, LegendCfg, ExtraCfg,
)
```

---

## Constructor patterns

### Dict form

Pass a nested dict to the `ANXChart` constructor. Unknown top-level keys raise `TypeError`. Unknown nested keys also raise `TypeError` via the dataclass constructor -- no silent drops.

```python
from anxwritter import ANXChart

chart = ANXChart(settings={
    'chart': {'bg_color': 8421504},
    'extra_cfg': {'entity_auto_color': True, 'arrange': 'grid'},
    'grid': {'snap': True},
    'view': {'time_bar': True},
})
```

### Dataclass form

Pass a `Settings` instance for full IDE autocomplete.

```python
from anxwritter import ANXChart, Settings, ChartCfg, ExtraCfg, GridCfg

chart = ANXChart(settings=Settings(
    chart=ChartCfg(bg_color=8421504),
    extra_cfg=ExtraCfg(entity_auto_color=True, arrange='grid'),
    grid=GridCfg(snap=True),
))
```

### Mutation after construction

All settings fields can be mutated after construction.

```python
chart = ANXChart()
chart.settings.chart.bg_color = 8421504
chart.settings.view.time_bar = True
chart.settings.legend_cfg.show = True
chart.settings.legend_cfg.font.bold = True
```

---

## Settings groups overview

| Group | Dataclass | Access path | Purpose |
|---|---|---|---|
| `extra_cfg` | `ExtraCfg` | `settings.extra_cfg` | anxwritter-only knobs (NOT written to ANX XML) |
| `chart` | `ChartCfg` | `settings.chart` | Core `<Chart>` background and engine flags |
| `font` | `Font` | `settings.font` | Chart-level default `<Font>` element |
| `view` | `ViewCfg` | `settings.view` | View / display toggles |
| `grid` | `GridCfg` | `settings.grid` | Grid size, snap, visibility |
| `wiring` | `WiringCfg` | `settings.wiring` | Theme/event wiring rendering |
| `links_cfg` | `LinksCfg` | `settings.links_cfg` | Chart-level link defaults |
| `time` | `TimeCfg` | `settings.time` | Date/time/timezone defaults |
| `summary` | `SummaryCfg` | `settings.summary` | Document metadata, origin, custom properties |
| `legend_cfg` | `LegendCfg` | `settings.legend_cfg` | Legend appearance, position, nested `Font` |

Every field on every group defaults to `None`. Only fields you explicitly set become XML attributes. ANB uses its own defaults for omitted attributes. The "ANB default" values listed in the tables below are ANB's fallback values, not values emitted by anxwritter.

---

## `extra_cfg` -- anxwritter-only knobs

These fields control anxwritter behavior only. They are NOT written to the ANX XML output.

| Field | Type | Default | Description |
|---|---|---|---|
| `entity_auto_color` | `Optional[bool]` | `None` | Distribute evenly-spaced HSV hues across entities with no explicit `color`. Also derives `label_font.color` and `label_font.bg_color` for contrast. Explicit field values on individual entities always win. |
| `link_match_entity_color` | `Optional[bool]` | `None` | Set `LineColour` on each link to match its `to_id` entity's resolved color. Only affects the line color, not the label font. An explicit `line_color` on a `Link` overrides this. |
| `arrange` | `Optional[str]` | `None` (= `'radial'`) | Auto-layout algorithm applied to entities without explicit `x`/`y`. Geometric: `'radial'` (default), `'circle'`, `'grid'`, `'random'`. Topology-aware: `'fr'` (Fruchterman-Reingold), `'forceatlas2'` (recommended for community/cluster reveal), `'tree'` (tidy tree). Aliases like `'fa2'`, `'fruchterman_reingold'`, `'reingold_tilford'` are accepted. Pinned entities (explicit `x`/`y`) act as fixed anchors for force-directed modes; tree mode keeps them at their pinned coordinates. |
| `layout_scale` | `Optional[float]` | `None` (= `1.0`) | Uniform spread multiplier applied to every layout algorithm. `2.0` doubles the distance between entities; `0.5` halves it. Useful when default spacing feels too tight or too loose for a particular chart. Pinned entity positions are absolute and ignore `layout_scale`. Non-positive or non-numeric values silently fall back to `1.0`. |
| `link_arc_offset` | `Optional[int]` | `None` (= `20`) | Default pixel offset between parallel links sharing the same entity pair. Set to `0` to disable auto-spacing. An explicit `offset` on a `Link` always wins. |
| `geo_map` | `Optional[GeoMapCfg]` | `None` | Geographic positioning configuration. Maps entity attribute values to lat/lon coordinates for canvas positioning and/or ANB Esri Maps integration. See `GeoMapCfg` fields below. |
| `icon_map` | `Optional[IconMapCfg]` | `None` | Attribute-value / id → icon mapping. Sets each matching entity's icon at build time from a central lookup, instead of setting `icon=` per entity. See `IconMapCfg` / `IconRule` fields below. |

### `GeoMapCfg` fields

`GeoMapCfg` (in `anxwritter.models`) configures geographic positioning. Pass either a `GeoMapCfg` instance or a nested dict to `extra_cfg.geo_map`.

| Field | Type | Default | Description |
|---|---|---|---|
| `attribute_name` | `Optional[str]` | `None` | Entity attribute name to match against geo data keys (required when `geo_map` is set). |
| `mode` | `Optional[str]` | `None` (= `'both'`) | `'position'` (canvas x,y only), `'latlon'` (inject Latitude/Longitude attributes only), or `'both'`. |
| `width` | `Optional[int]` | `None` (= `3000`) | Canvas projection area width in chart units. |
| `height` | `Optional[int]` | `None` (= `2000`) | Canvas projection area height in chart units. |
| `spread_radius` | `Optional[int]` | `None` (= `0`) | Circle radius for separating multiple entities sharing the same geo key. |
| `data` | `Optional[Dict[str, List[float]]]` | `None` | Inline lookup: `{key: [lat, lon]}`. |
| `data_file` | `Optional[str]` | `None` | Path to an external JSON or YAML file with the same shape as `data`. Inline `data` takes precedence on key conflicts. |
| `accent_insensitive` | `Optional[bool]` | `None` (= `True`) | Fold Unicode diacritics during matching, so `São Paulo`, `SAO PAULO`, and `sao paulo` all match the same key. Applied symmetrically to lookup keys and entity attribute values. Set to `False` for strict matching when your keys intentionally distinguish accented and unaccented forms. |

### `IconMapCfg` / `IconRule` fields

`IconMapCfg` (in `anxwritter.models`) maps entity **attribute values** or **ids**
to icons, the same way `geo_map` resolves coordinates — keep one central lookup
instead of setting `icon=` on every entity. It is a chart-level synthesizer
(same family as `geo_map` / `styling` / `display_attribute`), applied before
icon resolution. **Entity-only**, and only on representations that carry an icon
(`Icon`, `EventFrame`, `ThemeLine`); other representations and links are
skipped.

Pass either an `IconMapCfg` instance or a nested dict to `extra_cfg.icon_map`.
`IconMapCfg` has a single field, `rules` (a list of `IconRule`). Builder:
`chart.add_icon_map_rule(...)`.

The mapped value is a **bare icon name**, resolved exactly like the per-entity
`Icon.icon` field: a native / pre-installed ANB key, a registered entity-type
name (translated to its `icon_file`), or a registered **custom icon** name
(see [custom-icons.md](custom-icons.md)). Icon *values* are not validated — ANB
icon keys aren't enumerable.

**`IconRule` fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `match` | `Optional[str]` | `None` (= `'attribute'`) | `'attribute'` looks up `attribute_name`'s value in `mapping`; `'id'` looks up the entity `id`. |
| `attribute_name` | `Optional[str]` | `None` | Entity attribute to look up. Required when `match='attribute'`. |
| `type` | `Optional[str]` | `None` | Optional entity-type filter (attribute rules only). Must reference a registered or observed entity type. |
| `mapping` | `Dict[str, str]` | `{}` | Lookup of attribute value (or id) → icon name. Required (non-empty). |
| `default` | `Optional[str]` | `None` | Icon used when the attribute is **present but its value isn't in `mapping`**. Omit to skip. Attribute rules only. |
| `default_when_absent` | `Optional[str]` | `None` | Icon used when the entity **lacks the attribute entirely**. Omit to skip. Attribute rules only. |
| `strict_match` | `Optional[bool]` | `None` (= `False`) | Match attribute values exactly. Default folds case and Unicode diacritics (like `geo_map` / categorical styling). |

**Precedence** (highest wins): explicit per-entity `icon` > id rule > typed
attribute rule > untyped attribute rule. Within a single tier, the **last
matching rule wins**. Precedence is by tier, not raw list order — a lower-tier
rule declared later never overrides a higher-tier match.

**Outcomes for an attribute rule:** value in `mapping` → mapped icon; value
present but unrecognised → `default` (or skip); attribute absent →
`default_when_absent` (or skip). The rule is purely presentational and never
raises on data — to *require* an attribute be present, use
`EntityType.enforce.required_attributes` (see [validation.md](validation.md)).

There is deliberately **no `data_file`** field: an external rule table is just
another `--config` layer, which can also carry the `custom_entity_icons` the
rules reference.

```yaml
extra_cfg:
  icon_map:
    rules:
      - match: attribute
        attribute_name: bank_code
        type: Bank Account            # optional type filter
        mapping: {'341': money, '237': money}
        default: question             # present but unrecognised
        default_when_absent: box      # attribute missing entirely
      - match: id
        mapping: {acct_1: star}       # id beats the attribute rule above
```

Validation errors are reported as `icon_map_invalid` (bad `match`, empty
`mapping`, `default`/`default_when_absent`/`type` on an id rule, an attribute
rule missing `attribute_name`, or a `type` filter that references an unknown
entity type).

---

## `chart` -- core `<Chart>` element attributes

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `bg_color` | `Optional[Union[int, str]]` | `16777215` (white) | `BackColour` | Chart background color. Accepts COLORREF int, named color, or `#RRGGBB`. |
| `bg_filled` | `Optional[bool]` | `True` | `IsBackColourFilled` | Whether the background color is filled. |
| `label_merge_rule` | `Optional[str]` | `'merge'` | `LabelRule` | How labels are combined when entities merge. Values: `'merge'`, `'append'`, `'discard'`. Full ANB names also accepted. |
| `icon_quality` | `Optional[str]` | `'HighQuality'` | `TypeIconDrawingMode` | Icon rendering quality mode. |
| `rigorous` | `Optional[bool]` | `True` | `Rigorous` | Enables rigorous validation mode. |
| `id_reference_linking` | `Optional[bool]` | `True` | `IdReferenceLinking` | Enables ID-based reference linking. |

---

## `font` -- chart-level default font

Maps to `<Chart><Font>`. The `<Font>` element is only emitted when at least one field is explicitly set. When omitted entirely, i2 uses its own defaults (Tahoma 10pt).

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `name` | `Optional[str]` | `'Tahoma'` | `FaceName` | Typeface name. |
| `size` | `Optional[int]` | `10` | `PointSize` | Font size in points. |
| `color` | `Optional[Union[int, str]]` | `0` (black) | `FontColour` | Text color. Accepts COLORREF int, named color, or `#RRGGBB`. |
| `bg_color` | `Optional[Union[int, str]]` | `16777215` (white) | `BackColour` | Text background color. |
| `bold` | `Optional[bool]` | `False` | `Bold` | Bold weight. |
| `italic` | `Optional[bool]` | `False` | `Italic` | Italic style. |
| `strikeout` | `Optional[bool]` | `False` | `Strikeout` | Strikethrough. |
| `underline` | `Optional[bool]` | `False` | `Underline` | Underline. |

The `Font` dataclass is shared across chart-level font, `legend_cfg.font`, entity/link `label_font`, and `AttributeClass.font`. The same fields and emission rules apply in all contexts.

---

## `view` -- display toggles

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `show_pages_boundaries` | `Optional[bool]` | `False` | `ShowPages` | Show page boundary lines on the canvas. |
| `show_all` | `Optional[bool]` | `False` | `ShowAllFlag` | Show all items including hidden ones. |
| `hidden_items` | `Optional[str]` | `'hidden'` | `HiddenItemsVisibility` | How hidden items appear. Values: `'hidden'`, `'normal'`, `'grayed'`. |
| `cover_sheet_on_open` | `Optional[bool]` | `False` | `CoverSheetShowOnOpen` | Display the cover sheet when the chart is opened. |
| `time_bar` | `Optional[bool]` | `False` | `TimeBarVisible` | Show the time bar at the bottom of the chart. |

---

## `grid` -- grid settings

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `width` | `Optional[float]` | `0.29527...` | `GridWidthSize` | Grid cell width in inches. |
| `height` | `Optional[float]` | `0.29527...` | `GridHeightSize` | Grid cell height in inches. |
| `snap` | `Optional[bool]` | `False` | `SnapToGrid` | Snap entities to grid positions when dragging. |
| `visible` | `Optional[bool]` | `False` | `GridVisibleOnAllViews` | Display the grid on all chart views. |

---

## `wiring` -- theme/event wiring rendering

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `distance_far` | `Optional[float]` | `0.39370...` | `WiringDistanceFar` | Far wiring distance in inches. |
| `distance_near` | `Optional[float]` | `0.07874...` | `WiringDistanceNear` | Near wiring distance in inches. |
| `height` | `Optional[float]` | `0.11811...` | `WiringHeight` | Wiring height in inches. |
| `spacing` | `Optional[float]` | `0.19685...` | `WiringSpacing` | Wiring spacing in inches. |
| `use_height_for_theme_icon` | `Optional[bool]` | `True` | `UseWiringHeightForThemeIcon` | Use the wiring height for theme icon sizing. |

---

## `links_cfg` -- chart-level link defaults

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `spacing` | `Optional[float]` | `0.29527...` | `DefaultLinkSpacing` | Default spacing between link lines. |
| `use_default_spacing_when_dragging` | `Optional[bool]` | `True` | `UseDefaultLinkSpacingWhenDragging` | Apply default spacing when dragging links. |
| `blank_labels` | `Optional[bool]` | `False` | `BlankLinkLabels` | Suppress link label display. |
| `sum_numeric_labels` | `Optional[bool]` | `False` | `LabelSumNumericLinks` | Automatically sum numeric link labels. |

---

## `time` -- date/time/timezone defaults

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `default_date` | `Optional[str]` | `'2000-01-01T00:00:00.000'` | `DefaultDate` | Default date value for new items. |
| `default_datetime` | `Optional[str]` | `'2000-01-01T00:00:00.000'` | `DefaultDateTimeForNewChart` | Default date/time for new charts. |
| `tick_rate` | `Optional[float]` | `0.0031` | `DefaultTickRate` | Timeline tick rate. |
| `local_tz` | `Optional[bool]` | `True` | `UseLocalTimeZone` | Whether ANB uses the local time zone for display. |
| `hide_matching_tz_format` | `Optional[bool]` | `False` | `HideMatchingTimeZoneFormat` | Hide the timezone format when it matches. |

---

## `summary` -- document metadata

Maps to the `<Summary>` element. The entire `<Summary>` is omitted when no field is set. Origin fields (`created`, `revision`, `edit_time`, `last_print`, `last_save`) are folded into this group -- there is no separate `origin` group.

| Field | Type | ANB default | XML element/attribute | Description |
|---|---|---|---|---|
| `title` | `Optional[str]` | `None` | `<Field Type="SummaryFieldTitle">` | Document title. |
| `subject` | `Optional[str]` | `None` | `<Field Type="SummaryFieldSubject">` | Document subject. |
| `author` | `Optional[str]` | `None` | `<Field Type="SummaryFieldAuthor">` | Document author. |
| `keywords` | `Optional[str]` | `None` | `<Field Type="SummaryFieldKeywords">` | Document keywords. |
| `category` | `Optional[str]` | `None` | `<Field Type="SummaryFieldCategory">` | Document category. |
| `comments` | `Optional[str]` | `None` | `<Field Type="SummaryFieldComments">` | Document comments. |
| `template` | `Optional[str]` | `None` | `<Field Type="SummaryFieldTemplate">` | Template identifier. |
| `created` | `Optional[str]` | current datetime | `<Origin CreatedDate>` | Creation timestamp. Auto-populated with the current datetime when any summary field is set. |
| `revision` | `Optional[int]` | `1` | `<Origin RevisionNumber>` | Revision number. |
| `edit_time` | `Optional[int]` | `0` | `<Origin EditTime>` | Total edit time in ticks. |
| `last_print` | `Optional[str]` | omitted | `<Origin LastPrintDate>` | Last print date. Omitted by default. |
| `last_save` | `Optional[str]` | omitted | `<Origin LastSaveDate>` | Last save date. Omitted by default. |
| `custom_properties` | `List[CustomProperty]` | `[]` | `<CustomPropertyCollection>` | List of `CustomProperty` dataclasses with `name` and `value` fields. Always `Type="String"` in XML. Use `chart.add_custom_property(name, value)` as a convenience method. |

---

## `legend_cfg` -- legend appearance and position

| Field | Type | ANB default | XML attribute | Description |
|---|---|---|---|---|
| `show` | `Optional[bool]` | `False` | `Shown` | Whether the legend panel is visible. Legend items are still generated when `False`. |
| `x` | `Optional[int]` | `0` | `X` | Legend panel X position on the canvas. |
| `y` | `Optional[int]` | `0` | `Y` | Legend panel Y position on the canvas. |
| `arrange` | `Optional[str]` | `'wide'` | `Arrange` | Legend layout. Values: `'wide'`, `'tall'`, `'square'`. Resolved to full ANB names (`LegendArrangementWide`, etc.). |
| `valign` | `Optional[str]` | `'free'` | `VerticalAlignment` | Vertical alignment. Values: `'free'`, `'top'`, `'bottom'`. Resolved to full ANB names (`LegendAlignmentFree`, etc.). |
| `halign` | `Optional[str]` | `'free'` | `HorizontalAlignment` | Horizontal alignment. Values: `'free'`, `'left'`, `'right'`. |
| `font` | `Font` | `Font()` | nested `<Font>` child | Legend font settings. Same `Font` dataclass as the chart-level font. |

The entire `<LegendDefinition>` element is omitted when no legend settings, legend font overrides, or legend items exist.

ANB always groups and displays legend items by type in this fixed rendering order, regardless of insertion order: **Text -> Attribute -> Icon -> Line -> Font -> Link -> TimeZone -> IconFrame**.

---

## Output methods

### `to_anx(path)`

```python
chart.to_anx(path: str, *, stream: bool = True, compact: bool = True) -> str
```

Writes the `.anx` file. The `.anx` extension is added automatically if missing. Returns the absolute path of the written file. Calls `validate()` internally and raises `ANXValidationError` on errors.

The write is **atomic** — content goes to a temp file in the destination directory and is renamed into place with `os.replace()` (a metadata-only rename on the same filesystem). A failure mid-build never publishes a partial/corrupt `.anx`, and any existing file is preserved until the new one is complete.

- `stream=True` (default) — serialize and write incrementally: the `<ChartItem>` elements are emitted and discarded one at a time, so peak memory is roughly the resolved-item set rather than the whole element tree plus output string (~0.37× the buffered peak; also faster on large charts, negligibly slower on tiny ones). `stream=False` builds the whole document first. The written bytes are identical either way.
- `compact=True` (default) — drop indentation (newlines kept) for a smaller file. ANB ignores indentation and imports a compact file identically to the pretty form. `compact=False` writes the indented layout.

### `to_xml()`

```python
xml_str = chart.to_xml(*, compact: bool = False) -> str
```

Returns the ANX XML as a string without writing a file. Also validates internally and raises `ANXValidationError` on errors. Default `compact=False` returns the pretty, indented layout — the human-readable inspection form, unchanged across releases. Pass `compact=True` for the unindented form.

### `iter_xml(*, compact=True)` / `iter_anx_bytes(*, compact=True)`

```python
for chunk in chart.iter_xml(compact=True):        # Iterator[str]  — XML text chunks
    ...
for chunk in chart.iter_anx_bytes(compact=True):  # Iterator[bytes] — UTF-16 LE, BOM first
    sink.write(chunk)
```

Stream the chart without materializing the whole document — the `<ChartItem>` elements are serialized and discarded one at a time, so peak memory is roughly the resolved-item set rather than the full element tree plus output string (measured **~0.36× the peak of `to_xml()`** and **~20% faster** on large charts). Ideal for writing straight to a file or an HTTP response.

- Both validate **up front** (before yielding any chunk) and raise `ANXValidationError` if the chart is invalid — same contract as `to_anx()`/`to_xml()`.
- `compact=True` (default) drops indentation, keeping newlines, for smaller output; `compact=False` yields the **exact bytes** of the pretty `to_xml()`.
- `iter_anx_bytes` emits the UTF-16 LE BOM once on the first chunk; concatenated output equals what `to_anx()` writes to disk.
- `to_xml()` with its default `compact=False` is the pretty, indented inspection form, unchanged across releases.

### `validate()`

```python
errors = chart.validate() -> list[dict]
```

Validates chart data without building. Returns a list of error dicts. An empty list means the chart is valid.

---

## Validation error types

Every error dict contains a `type`, a human-readable `message`, and (almost always) a `location` string pointing at the offending row (e.g. `"entities[2] (Icon)"`, `"links[7]"`, `"attribute_classes[0].type"`). The `config_conflict` error additionally carries `section`, `name`, `config_value`, and `data_value`. No other error types add fields.

| Error type | Trigger |
|---|---|
| `missing_required` | Required field missing -- `id`/`type` on entities, `from_id`/`to_id` on links, `name` on `LegendItem` / `EntityType` / `LinkType` / `Strength` / `DateTimeFormat`, both `name` AND `type` on `AttributeClass`, `name` on `PaletteAttributeEntry`, `name` and `kind_of` on `SemanticEntity`/`SemanticLink`, `name` and `base_property` on `SemanticProperty`. |
| `duplicate_id` | Same entity `id` used more than once. |
| `duplicate_name` | Duplicate `name` in `EntityType`, `LinkType`, `Strength`, `AttributeClass`, or `DateTimeFormat` definitions. |
| `missing_entity` | Link `from_id` or `to_id` references an entity that was not added to the chart. |
| `missing_target` | Loose card `entity_id` or `link_id` does not match any added entity or `Link.link_id`. |
| `unknown_color` | Color value is not a valid COLORREF int, named color, or `#RRGGBB` string. |
| `invalid_date` | Date string does not match any supported format (`yyyy-MM-dd`, `dd/MM/yyyy`, `yyyymmdd`). |
| `invalid_time` | Time string does not match any supported format (`HH:MM:SS`, `HH:MM:SS.ffffff`, `HH:MM`, `HH:MM AM/PM`). |
| `type_conflict` | Same attribute name used with different inferred Python types across entities/links, or an `AttributeClass.type` declaration disagrees with the data. |
| `invalid_strength` | Strength name referenced on an entity or link is not registered via `add_strength()`. |
| `invalid_strength_default` | `StrengthCollection.default` references a name not present in `items`. |
| `invalid_arrow` | Link `arrow` value is not a valid arrow style (`'head'`/`'->'`, `'tail'`/`'<-'`, `'both'`/`'<->'`, or full ANB names). |
| `invalid_grade_default` | `GradeCollection.default` references a name not present in `items`. |
| `grade_out_of_range` | Grade index is negative or exceeds the size of the corresponding grade collection. |
| `self_loop` | Link `from_id` equals `to_id`. |
| `invalid_ordered` | `ordered=True` on a link whose endpoints are not both ThemeLines. |
| `invalid_legend_type` | Unrecognised `item_type` value on a `LegendItem`. |
| `invalid_timezone` | `TimeZone` dataclass malformed -- missing `id`/`name` field, or `id` not an integer 1-122. |
| `timezone_without_datetime` | Timezone set on entity/link/card but `date` or `time` is missing. ANB silently ignores the timezone in this case. |
| `invalid_multiplicity` | `multiplicity` value is not a valid `Multiplicity` enum string. |
| `invalid_theme_wiring` | `theme_wiring` value is not a valid `ThemeWiring` enum string. |
| `connection_conflict` | Links between the same entity pair set conflicting connection style tuples `(multiplicity, fan_out, theme_wiring)`. |
| `unregistered_datetime_format` | `datetime_format` value on an entity or link is not registered via `add_datetime_format()`. ANB 9 only accepts registered format names. |
| `invalid_value` | Value exceeds length limits -- e.g. `DateTimeFormat` name > 250 chars or format string > 259 chars. |
| `unsupported_representation` | `EntityType.representation` is set to `'OLE_OBJECT'` (or equivalent), which the builder does not yet implement. |
| `invalid_semantic_type` | `semantic_type` references an `LN`-prefixed name (e.g. `'LNEntityPerson'`) — these are i2 COM API names that ANB rejects. Use the standard type name (`'Person'`) or a raw GUID. |
| `invalid_merge_behaviour` | `AttributeClass.merge_behaviour` is unknown or invalid for the declared attribute type. |
| `invalid_paste_behaviour` | `AttributeClass.paste_behaviour` is unknown or invalid for the declared attribute type. |
| `invalid_geo_map` | `extra_cfg.geo_map` configuration is invalid -- missing `attribute_name`, unknown `mode`, non-positive `width`/`height`, negative `spread_radius`, no `data` or `data_file`, or out-of-range lat/lon coordinates. |
| `icon_map_invalid` | `extra_cfg.icon_map` rule is invalid -- unknown `match`, empty `mapping`, `default`/`default_when_absent`/`type` on an id rule, attribute rule missing `attribute_name`, or a `type` filter referencing an unknown entity type. |
| `config_conflict` | Data file redefines a config-locked name with different specs (only when a config file was applied). Adds `section`, `name`, `config_value`, `data_value` keys to the error dict. |
| `palette_unknown_ref` | Palette references an entity type, link type, or attribute class name that is not registered. |
| `palette_invalid_class` | Palette references an attribute class with `is_user=False` or `user_can_add=False`. ANB rejects these. |
| `palette_type_mismatch` | Palette attribute entry value does not match the attribute class type. |

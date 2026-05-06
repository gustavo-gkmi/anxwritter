# Link Reference

`Link` is a dataclass in `anxwritter.models`, exported from the top-level `anxwritter` package.

```python
from anxwritter import Link
```

Add links with `chart.add_link(**kw)`, `chart.add(Link(...))`, or `chart.add_all(iterable)`.

---

## Link fields

All fields except `from_id` and `to_id` are optional.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `from_id` | `str` | **yes** | `""` | Source entity `id`. Must reference an entity added to the chart. |
| `to_id` | `str` | **yes** | `""` | Target entity `id`. Must reference an entity added to the chart. |
| `type` | `Optional[str]` | no | `None` | Link type label, e.g. `'Call'`, `'Financial Transfer'`. When a `LinkType` is registered with a matching name, `LinkTypeReference` is emitted on `<LinkStyle>`. |
| `arrow` | `Optional[str]` | no | `None` | Arrow direction. See the Arrow styles table below. When omitted, no arrow is drawn. |
| `label` | `Optional[str]` | no | `None` | Text label displayed on the link line. |
| `date` | `Optional[str]` | no | `None` | Date string. Supported formats: `yyyy-MM-dd` (canonical, recommended), `dd/MM/yyyy`, `yyyymmdd`. The ambiguous US `mm/dd/yyyy` is intentionally rejected. ANB interprets all date/time values as UTC. |
| `time` | `Optional[str]` | no | `None` | Time string. Supported formats: `HH:MM:SS` (canonical), `HH:MM:SS.ffffff` (microseconds), `HH:MM` (no seconds), `HH:MM AM/PM` (12-hour). Stored as UTC -- no automatic timezone adjustment. |
| `description` | `Optional[str]` | no | `None` | Free-text link description. |
| `datetime_description` | `Optional[str]` | no | `None` | Free-text description of the date/time (e.g. `'Morning call'`). Written as `DateTimeDescription` attribute on `<ChartItem>`. Use with `show_datetime_description=True` to display this instead of raw values. |
| `attributes` | `dict` | no | `{}` | Key/value metadata dict. Type inferred from Python value. See [Attributes](attributes.md). |
| `cards` | `List[Card]` | no | `[]` | Evidence cards attached to this link. `<CardCollection>` is emitted inside `<Link>` before `<LinkStyle>`. See [Entities](entities.md) for Card fields. |
| `ordered` | `Optional[bool]` | no | `None` | When `True`, emits `Ordered="true"` on `<ChartItem>` -- ANB **Controladores** mode. Requires both `date` and `time`. **Constraint**: `ordered=True` is only valid when both link ends are ThemeLine entities. ANB rejects it otherwise. See Ordering modes below. |
| `strength` | `Optional[str]` | no | `None` | Named strength for the link line, e.g. `'Default'`, `'Confirmed'`. Must match a name registered via `add_strength()`. |
| `offset` | `Optional[int]` | no | `None` | Pixel offset for parallel link arc separation. Explicit value always wins over auto-spacing from `extra_cfg.link_arc_offset`. Omit to use the auto-computed value. |
| `line_color` | `Optional[Union[int, str, Color]]` | no | `None` | Line color. Accepts the `Color` enum, named color (case-insensitive), `#RRGGBB`, or COLORREF integer. Default `0` (black). Overrides `extra_cfg.link_match_entity_color` when explicitly set. |
| `line_width` | `Optional[int]` | no | `None` | Line thickness in pixels (integer). Default `1`. Only emitted when not `1`. |
| `grade_one` | `Optional[Union[int, str]]` | no | `None` | Source reliability grade. Accepts a 0-based index into `chart.grades_one` or the grade name string (e.g. `'Reliable'`); the name is resolved at validate/build time. Unknown names raise `unknown_grade`. When `None`, `GradeOneIndex` is not emitted. |
| `grade_two` | `Optional[Union[int, str]]` | no | `None` | Information reliability grade. Accepts a 0-based index into `chart.grades_two` or the grade name string. |
| `grade_three` | `Optional[Union[int, str]]` | no | `None` | Third grading dimension. Accepts a 0-based index into `chart.grades_three` or the grade name string. |
| `label_font` | `Font` | no | `Font()` | Font styling for the link's display label. Uses the shared `Font` dataclass -- see [Settings](settings.md) for `Font` fields. Only explicitly-set fields are emitted. |
| `timezone` | `Optional[TimeZone]` | no | `None` | TimeZone for the ChartItem. Uses the `TimeZone` dataclass with `id` (int, ANB UniqueID 1-122) and `name` (str). Example: `TimeZone(id=1, name='UTC')`. The link must have both `date` and `time` set -- ANB silently ignores the timezone otherwise. |
| `source_ref` | `Optional[str]` | no | `None` | Source reference string. |
| `source_type` | `Optional[str]` | no | `None` | Source type label string. Should match an entry in `chart.source_types`. |
| `show` | `Show` | no | `Show()` | Sub-item visibility flags. Same `Show` dataclass as entities -- see [Entities](entities.md). |
| `background` | `Optional[bool]` | no | `None` | `CIStyle.Background` -- makes the link a non-selectable background element. |
| `show_datetime_description` | `Optional[bool]` | no | `None` | `CIStyle.ShowDateTimeDescription` -- displays `datetime_description` instead of raw date/time values. |
| `datetime_format` | `Optional[str]` | no | `None` | Name of a registered `DateTimeFormat`. Must be added via `add_datetime_format()` first. ANB 9 resolves the name against the `DateTimeFormatCollection`. Inline format strings are NOT supported. |
| `sub_text_width` | `Optional[float]` | no | `None` | `CIStyle.SubTextWidth`. Exact effect not fully confirmed. |
| `use_sub_text_width` | `Optional[bool]` | no | `None` | `CIStyle.UseSubTextWidth`. Exact effect not fully confirmed. |
| `multiplicity` | `Optional[Union[str, Multiplicity]]` | no | `None` | Connection multiplicity. Accepts the `Multiplicity` enum or short string. See Connection fields below. |
| `fan_out` | `Optional[int]` | no | `None` | Arc spread for parallel links in world coordinates. All links between the same entity pair must agree. |
| `theme_wiring` | `Optional[Union[str, ThemeWiring]]` | no | `None` | Theme line wiring behavior. Accepts the `ThemeWiring` enum or short string. See Connection fields below. |
| `link_id` | `Optional[str]` | no | `None` | **INTERNAL ONLY** -- used to target loose `Card` attachment via `add_card(link_id=...)`. NOT written to XML. |
| `semantic_type` | `Optional[str]` | no | `None` | Per-instance `SemanticTypeGuid` override on the `<Link>` element. Overrides the `LinkType`-level semantic type. Resolved to a GUID at build time. |

---

## Arrow styles

| Short value | Alias | Full ANB name | Direction |
|---|---|---|---|
| `'head'` | `'->'` | `ArrowOnHead` | Source -> Target |
| `'tail'` | `'<-'` | `ArrowOnTail` | Source <- Target |
| `'both'` | `'<->'` | `ArrowOnBoth` | Bidirectional |
| *(omitted)* | | `ArrowNone` | No arrow |

Full ANB names (`ArrowOnHead`, `ArrowOnTail`, `ArrowOnBoth`) are also accepted as passthrough values.

`ArrowStyle` is omitted from `<LinkStyle>` entirely when no arrow is set (`ArrowNone`).

---

## Parallel link auto-spacing

When multiple links connect the same entity pair, anxwritter automatically distributes them into symmetric arcs using the `extra_cfg.link_arc_offset` setting (default `20`).

The offset pattern for N links between the same pair:

| Link count | Parity | Offsets (spacing=20) | Offsets (spacing=40) |
|---|---|---|---|
| 1 | odd | `0` | `0` |
| 2 | even | `+10, -10` | `+20, -20` |
| 3 | odd | `0, +20, -20` | `0, +40, -40` |
| 4 | even | `+10, -10, +30, -30` | `+20, -20, +60, -60` |

Rules:

- An explicit `offset` value on a `Link` always overrides the auto-computed value for that link.
- Set `extra_cfg.link_arc_offset=0` in settings to disable auto-spacing entirely (all links overlap at offset 0).
- The entity pair is direction-sensitive -- A->B and B->A get separate auto-spacing groups. (Connection-style validation and dedup do use canonically sorted pairs, so they are direction-insensitive.)

---

## Ordering modes

ANB has three ordering states, controlled by the `ordered` field and whether `date`/`time` are set. The `ordered` field is available on both entities and links.

| ANB mode | `ordered` value | `date` set? | Description |
|---|---|---|---|
| **Livre** | `False` / omitted | no | Unordered, floating item |
| **Ordenado** | `False` / omitted | yes | Sorted by date/time on the timeline |
| **Controladores** | `True` | yes (+ `time`) | Controls/pins timeline ordering. Requires both `date` and `time`. |

**Link-specific constraint**: `ordered=True` on a link is only valid when both link ends (`from_id` and `to_id`) are ThemeLine entities. ANB rejects this combination at import time and reports it as an "Ordered link must connect themes" error in the import log. Validation catches this as `invalid_ordered`. This constraint does not apply to entities.

---

## Connection fields

Connection fields control how ANB groups and renders links between the same entity pair. These fields are only relevant when multiple links exist between two entities.

### `multiplicity`

How multiple links between the same entity pair are displayed. Use the `Multiplicity` enum or short strings.

| Short value | Full ANB name | Description |
|---|---|---|
| `'multiple'` | `MultiplicityMultiple` | Each ChartItem rendered as a separate parallel arc (default) |
| `'single'` | `MultiplicitySingle` | All ChartItems for the connection collapse into one link with a card stack |
| `'directed'` | `MultiplicityDirected` | Directional grouping (schema-valid) |

### `fan_out`

Integer arc spread for parallel links in world coordinates. Controls how widely fanned out the parallel arcs are. All links between the same entity pair must agree on this value.

### `theme_wiring`

Controls theme line behavior after passing through an event frame connection. Only relevant for ThemeLine-to-EventFrame connections. Use the `ThemeWiring` enum or short strings.

| Short value | Full ANB name | Description |
|---|---|---|
| `'keep_event'` | `KeepsAtEventHeight` | Stays at event frame height |
| `'return_theme'` | `ReturnsToThemeHeight` | Returns to original theme height |
| `'next_event'` | `GoesToNextEventHeight` | Changes to next event frame height |
| `'no_diversion'` | `NoDiversion` | Theme line passes straight through |

### Connection conflict detection

All links between the same entity pair must set the same connection style tuple `(multiplicity, fan_out, theme_wiring)`. If two links between the same pair set conflicting values, validation reports a `connection_conflict` error.

### `<ConnectionCollection>` conditional emission

The `<ConnectionCollection>` element is only emitted when at least one Link has `multiplicity`, `fan_out`, or `theme_wiring` set. When no link sets these fields, no `<ConnectionCollection>` or `ConnectionReference` is generated -- zero overhead for charts that do not use connection features.

Connection styles are resolved during build (`builder.resolve_link()`) via O(1) dict lookups -- no XML patching in `build()`. The entity pair key is canonically sorted (`tuple(sorted((A, B)))`) so A->B and B->A share the same connection.

---

## `<LinkStyle>` emission rules

Only `Strength` is always emitted on `<LinkStyle>`. All other attributes are conditional:

| Attribute | Emitted when |
|---|---|
| `Strength` | Always |
| `ArrowStyle` | Arrow is not `ArrowNone` |
| `LineWidth` | Value is not `1` |
| `LineColour` | Value is not `0` (black) |
| `Type` | Link has an explicit type |
| `LinkTypeReference` | Always emitted alongside `Type` (link types are auto-registered when first referenced) |

---

## `<Link>` element attributes

Only `End1Id` and `End2Id` are always emitted on the `<Link>` element. Additional attributes are conditional:

| Attribute | Emitted when |
|---|---|
| `End1Id` | Always (references source entity) |
| `End2Id` | Always (references target entity) |
| `Offset` | Non-zero offset value |
| `ConnectionReference` | Connection fields are set |

`End1Reference`, `End2Reference`, `LabelPos`, and `LabelSegment` are not emitted.

---

## Link cards

Link cards use the same `Card` class as entity cards. `<CardCollection>` is emitted directly inside `<Link>` before `<LinkStyle>`. Attach cards inline via the `cards` field on a `Link` object, or use `chart.add_card(link_id=...)` for loose cards (requires the link to have `link_id` set).

```python
chart.add_link(
    from_id='Alice', to_id='Bob', type='Call',
    link_id='call_001',
    cards=[Card(summary='Report A', date='2024-01-17')],
)

# Loose card attached by link_id at build time
chart.add_card(link_id='call_001', summary='Intercept', date='2024-01-18')
```

---

## Self-loop validation

A link where `from_id` equals `to_id` is reported as a `self_loop` validation error. ANB does not support self-referential links.

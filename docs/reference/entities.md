# Entity Reference

All entity classes live in `anxwritter.entities` and are exported from the top-level `anxwritter` package. They all inherit from `_BaseEntity` (internal; not exported).

```python
from anxwritter import Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label
```

---

## Entity classes

Each class maps to a distinct ANB visual representation. The class you instantiate determines the shape rendered in i2 Analyst's Notebook.

| Class | ANB representation | XML style element |
|---|---|---|
| `Icon` | Image with label (default) | `<IconStyle>` |
| `Box` | Rectangle | `<BoxStyle>` |
| `Circle` | Ellipse | `<CircleStyle>` |
| `ThemeLine` | Horizontal band spanning full chart width | `<ThemeStyle>` |
| `EventFrame` | Time-bounded region with icon | `<EventStyle>` |
| `TextBlock` | Free-standing text box | `<TextBlockStyle>` |
| `Label` | Transparent text overlay (no visible border) | `<TextBlockStyle>` with `RepresentAsBorder` |

---

## Shared fields (all entity classes)

All fields except `id` and `type` are optional and default to `None` unless otherwise noted. Fields set to `None` are not emitted in the XML output -- ANB uses its own library defaults.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | `str` | **yes** | `""` | Unique entity identity string. Maps to `Entity.Identity` in ANX XML. Globally unique within a chart -- the same identity cannot exist with two different entity types. |
| `type` | `str` | **yes** | `""` | Entity type name, e.g. `'Person'`, `'Vehicle'`, `'Bank Account'`. |
| `label` | `Optional[str]` | no | `None` | Display label shown beneath/beside the entity. Defaults to the value of `id` in the XML builder when omitted. |
| `date` | `Optional[str]` | no | `None` | Date string. Supported formats: `yyyy-MM-dd` (canonical, recommended), `dd/MM/yyyy`, `yyyymmdd`. The ambiguous US `mm/dd/yyyy` is intentionally rejected. ANB interprets all date/time values as UTC. |
| `time` | `Optional[str]` | no | `None` | Time string. Supported formats: `HH:MM:SS` (canonical), `HH:MM:SS.ffffff` (microseconds), `HH:MM` (no seconds), `HH:MM AM/PM` (12-hour). Stored as UTC -- no automatic timezone adjustment. |
| `description` | `Optional[str]` | no | `None` | Free-text entity description. |
| `datetime_description` | `Optional[str]` | no | `None` | Free-text description of the date/time (e.g. `'About 3pm'`). Written as the `DateTimeDescription` attribute on `<ChartItem>`. Use with `show_datetime_description=True` to display this instead of raw date/time values. |
| `ordered` | `Optional[bool]` | no | `None` | When `True`, emits `Ordered="true"` on `<ChartItem>` -- ANB **Controladores** mode (ordered with date and time). Requires both `date` and `time` to be set. When `False`/`None` with a date set, ANB uses **Ordenado** mode. Without a date, ANB uses **Livre** mode. |
| `attributes` | `dict` | no | `{}` | Key/value metadata dict. Type is inferred from the Python value: `str` -> Text, `int`/`float` -> Number, `bool` -> Flag, `datetime` -> DateTime. See [Attributes](attributes.md). |
| `cards` | `List[Card]` | no | `[]` | Evidence cards attached to this entity. See the Card fields section below. |
| `x` | `Optional[int]` | no | `None` | Manual canvas X position (integer). When set, auto-layout is skipped for this entity. |
| `y` | `Optional[int]` | no | `None` | Manual canvas Y position (integer). When set, auto-layout is skipped for this entity. |
| `strength` | `Optional[str]` | no | `None` | Named strength for the entity border, e.g. `'Default'`, `'Confirmed'`. Must match a name registered via `add_strength()`. The chart is pre-populated with `Default=solid`. |
| `grade_one` | `Optional[Union[int, str]]` | no | `None` | Source reliability grade. Accepts a 0-based index into `chart.grades_one` or the grade name string (e.g. `'Reliable'`); the name is resolved to its index at validate/build time. Unknown names raise `unknown_grade`. When `None`, `GradeOneIndex` is not emitted and ANB shows it as unset. |
| `grade_two` | `Optional[Union[int, str]]` | no | `None` | Information reliability grade. Accepts a 0-based index into `chart.grades_two` or the grade name string. |
| `grade_three` | `Optional[Union[int, str]]` | no | `None` | Third grading dimension. Accepts a 0-based index into `chart.grades_three` or the grade name string. |
| `label_font` | `Font` | no | `Font()` | Font styling for the entity's display label. Uses the shared `Font` dataclass -- see [Settings](settings.md) for `Font` fields. Only explicitly-set fields are emitted in the XML. |
| `timezone` | `Optional[TimeZone]` | no | `None` | TimeZone for the ChartItem. Uses the `TimeZone` dataclass with `id` (int, ANB UniqueID 1-122) and `name` (str, cosmetic display string). Both fields are required by ANB 9. Example: `TimeZone(id=1, name='UTC')`. The entity must have both `date` and `time` set -- ANB silently ignores `<TimeZone>` when `TimeSet="false"`. Generates `<TimeZone UniqueID="..." Name="..."/>` inside `<ChartItem>` after `<CIStyle>`. |
| `source_ref` | `Optional[str]` | no | `None` | Source reference string. |
| `source_type` | `Optional[str]` | no | `None` | Source type label string. Should match an entry in `chart.source_types`. |
| `show` | `Show` | no | `Show()` | Sub-item visibility flags. Uses the `Show` dataclass. Each field defaults to `None` -- ANB library defaults apply (`label=True`, all others `False`). See the Show dataclass section below. |
| `background` | `Optional[bool]` | no | `None` | `CIStyle.Background` -- when `True`, makes the entity a non-selectable background image. |
| `show_datetime_description` | `Optional[bool]` | no | `None` | `CIStyle.ShowDateTimeDescription` -- when `True`, displays the `datetime_description` string instead of the raw date/time values. |
| `datetime_format` | `Optional[str]` | no | `None` | Name of a registered `DateTimeFormat`. Must be added via `add_datetime_format()` first. ANB 9 resolves the name against the chart-level `DateTimeFormatCollection`. Inline format strings are NOT supported -- ANB 9 rejects them. Emitted as `DateTimeFormat` attribute on `<CIStyle>`. |
| `sub_text_width` | `Optional[float]` | no | `None` | `CIStyle.SubTextWidth`. Exact effect not fully confirmed. |
| `use_sub_text_width` | `Optional[bool]` | no | `None` | `CIStyle.UseSubTextWidth`. Exact effect not fully confirmed. |
| `semantic_type` | `Optional[str]` | no | `None` | Per-instance `SemanticTypeGuid` on the `<Entity>` element. Overrides the type-level semantic type set on `EntityType`. Resolved to a GUID at build time from the catalogue or custom semantic entity definitions. |

---

## Per-type specific fields

Fields unique to each entity class. All are optional (default `None` unless noted).

All color-typed fields below have type `Optional[Union[int, str, Color]]` — i.e. they accept a COLORREF integer, a string (named color, hex, or normalized form), or a `Color` enum value. See [visual-styling.md](visual-styling.md#named-colors-and-the-color-enum) for the complete acceptance rules.

| Field | Type | Icon | Box | Circle | ThemeLine | EventFrame | TextBlock | Label | Description |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `color` | `Optional[Union[int, str, Color]]` | Y | | | | | | | Icon shading color. Accepts the `Color` enum (`Color.BLUE`), named color (case-insensitive), `#RRGGBB` hex, or a COLORREF integer. Written as `IconShadingColour` in ANX XML. |
| `icon` | `Optional[str]` | Y | | | Y | Y | | | Per-entity icon override. Accepts a canonical ANB icon key (e.g. `'person'`) or a registered entity type name (e.g. `'Pessoa'`) -- type names are auto-translated to their `icon_file` via `_etype_meta`. Emits `OverrideTypeIcon="true"` + `TypeIconName` on the style element. |
| `frame` | `Frame` | Y | | | Y | | | | Frame highlight border. Uses the `Frame` dataclass. Default `Frame()` (all fields `None`). See the Frame dataclass section below. |
| `text_x` | `Optional[int]` | Y | | | | | | | Horizontal offset of the label text relative to the icon. Omitted from XML when `None`. |
| `text_y` | `Optional[int]` | Y | | | | | | | Vertical offset of the label text relative to the icon. Omitted from XML when `None`. |
| `enlargement` | `Optional[str]` | Y | | | Y | Y | | | Icon enlargement size. Use the `Enlargement` enum (`'half'`, `'single'`, `'double'`, `'triple'`, `'quadruple'`) or raw string. Omitted from XML when `None`. |
| `shade_color` | `Optional[Union[int, str, Color]]` | | | | Y | Y | | | Icon shading color for ThemeLine/EventFrame. Same color forms as `color`. |
| `bg_color` | `Optional[Union[int, str, Color]]` | | Y | Y | | Y | Y | Y | Fill/background color. ANB default `16777215` (white). |
| `filled` | `Optional[bool]` | | Y | Y | | Y | Y | Y | Whether the shape is filled. ANB default `True` for most types, `False` for Box. |
| `line_color` | `Optional[Union[int, str, Color]]` | | | | Y | Y | Y | Y | Line/border color. Omitted when `None` -- ANB uses its default. Note: Box and Circle do not expose `line_color` (ANB does not support `LineColour` on `BoxStyle`/`CircleStyle`). |
| `line_width` | `Optional[int]` | | Y | Y | Y | Y | Y | Y | Line thickness in pixels (integer). ANB default `1` for most types, `3` for ThemeLine. |
| `width` | `Optional[int]` | | Y | | | | Y | Y | Width in canvas units. Box: integer direct (default `100`). TextBlock: divided by 100 -> inches (default `138`). Label: divided by 100 -> inches (default `100`). |
| `height` | `Optional[int]` | | Y | | | | Y | Y | Height in canvas units. Box: integer direct (default `100`). TextBlock: divided by 100 -> inches (default `79`). Label: divided by 100 -> inches (default `39`). |
| `depth` | `Optional[int]` | | Y | | | | | | Box 3-D depth. Optional -- omitted when `None`. |
| `diameter` | `Optional[int]` | | | Y | | | | | Circle diameter in canvas units. Divided by 100 before writing to ANX (ANB stores diameter as a decimal inch value). Default `138`. `diameter=100` is roughly the same visual size as a default `width=100, height=100` Box. |
| `autosize` | `Optional[bool]` | | | Y | | | | | Whether the circle auto-sizes to fit its label. Default `False`. |
| `alignment` | `Optional[str]` | | | | | | Y | Y | Text alignment: `'centre'`/`'center'`, `'left'`, `'right'`. Resolved to full ANB names (`'TextAlignCentre'`, `'TextAlignLeft'`, `'TextAlignRight'`). Default `'centre'`. |

---

## Show dataclass

Controls sub-item visibility flags shown in ANB's item panel. Maps to `<SubItem Type="...">` children inside `<SubItemCollection>`.

```python
from anxwritter import Show

show = Show(description=True, grades=True, label=True)
```

| Field | Type | Default | XML SubItem type | ANB library default |
|---|---|---|---|---|
| `description` | `Optional[bool]` | `None` | `SubItemDescription` | `False` |
| `grades` | `Optional[bool]` | `None` | `SubItemGrades` | `False` |
| `label` | `Optional[bool]` | `None` | `SubItemLabel` | `True` |
| `date` | `Optional[bool]` | `None` | `SubItemDateTime` | `False` |
| `source_ref` | `Optional[bool]` | `None` | `SubItemSourceReference` | `False` |
| `source_type` | `Optional[bool]` | `None` | `SubItemSourceType` | `False` |
| `pin` | `Optional[bool]` | `None` | `SubItemPin` | `False` |

When a field is `None`, the builder preserves the ANB library default. There are always 7 `<SubItem>` entries per ChartItem when the `<SubItemCollection>` is emitted.

---

## Frame dataclass

Frame highlight border, available on `Icon` and `ThemeLine` only. Maps to `<FrameStyle>` in ANX XML.

```python
from anxwritter import Frame

frame = Frame(color=16764057, margin=2, visible=True)
```

| Field | Type | Default | XML attribute | ANB default |
|---|---|---|---|---|
| `color` | `Optional[Union[int, str, Color]]` | `None` | `FrameStyle.Colour` | `16764057` (light yellow) |
| `margin` | `Optional[int]` | `None` | `FrameStyle.Margin` | `2` |
| `visible` | `Optional[bool]` | `None` | `FrameStyle.Visible` | `False` |

---

## Entity deduplication

Entities are deduplicated by their `id` (identity) string. The same identity always reuses the same `<ChartItem>` in the XML output. Identity is globally unique in ANB -- the same identity string cannot exist with two different entity types on the same chart.

- First occurrence of an `id` creates the `<Entity>` and `<ChartItem>` elements.
- Subsequent additions with the same `id` are no-ops in the builder.
- Validation reports `duplicate_id` if the same `id` appears more than once.

---

## ThemeLine auto Y-offset

When multiple `ThemeLine` entities appear on the same chart without an explicit `y` field value, the library auto-assigns Y positions: 0, 30, 60, ... in the order they were added. Explicit `y` always wins. ThemeLines with explicit `y` but no `x` are pinned to `x=0` (X has no visual effect on ThemeLines since they span the full chart width).

---

## Label XML implementation

`Label` uses `<TextBlock>/<TextBlockStyle>` (the same XML element as `TextBlock`) with `RepresentAsBorder` in `PreferredRepresentation`. The `BackColour` and `LineColour` are both set to the chart background color with `Filled="false"` -- this makes the border and fill invisible, approximating i2's native Label appearance. Setting `LineWidth=0` still renders the border visibly; matching colors to the background is the correct approach.

---

## Icon name translation

When the `icon` field value matches a registered entity type name in `_etype_meta` (populated by `add_entity_type()`), it is auto-translated to that type's `icon_file`.

```python
chart.add_entity_type(name='Pessoa', icon_file='person')
chart.add_icon(id='Carlos', type='Vehicle', icon='Pessoa')
# Emits TypeIconName="person" (translated from type name to icon_file)
```

Raw ANB icon keys (e.g. `'witness'`) that do not match any registered type name pass through unchanged.

---

## Card fields

Cards provide source/grading metadata visible in ANB's card panel. Attach them inline via the `cards` field on the entity, or loosely via `chart.add_card(entity_id=...)` or `chart.add_card(link_id=...)`.

| Field | Type | Description |
|---|---|---|
| `summary` | `Optional[str]` | Short summary text shown in ANB's card panel. Maps to `Summary` XML attribute. |
| `date` | `Optional[str]` | Date string. Same supported formats as entity/link `date`: `yyyy-MM-dd` (canonical), `dd/MM/yyyy`, `yyyymmdd`. Interpreted as UTC. |
| `time` | `Optional[str]` | Time string. Same supported formats as entity/link `time`: `HH:MM:SS` (canonical), `HH:MM:SS.ffffff`, `HH:MM`, `HH:MM AM/PM`. Interpreted as UTC. |
| `description` | `Optional[str]` | Long-form card body text. Maps to `Text` XML attribute. |
| `datetime_description` | `Optional[str]` | Free-text description of the date/time (e.g. `'About 3pm'`). Written as `DateTimeDescription` attribute on `<Card>`. |
| `source_ref` | `Optional[str]` | Source document reference string. |
| `source_type` | `Optional[str]` | Source type label string (e.g. `'Witness'`). |
| `grade_one` | `Optional[Union[int, str]]` | Source reliability grade -- 0-based index into `chart.grades_one` or the grade name string. |
| `grade_two` | `Optional[Union[int, str]]` | Information reliability grade -- 0-based index into `chart.grades_two` or the grade name string. |
| `grade_three` | `Optional[Union[int, str]]` | Third grading dimension -- 0-based index into `chart.grades_three` or the grade name string. |
| `timezone` | `Optional[TimeZone]` | TimeZone for the card. Uses the `TimeZone` dataclass with `id` (int, ANB UniqueID 1-122) and `name` (str). Example: `TimeZone(id=1, name='UTC')`. The card must have both `date` and `time` set -- ANB logs a warning and ignores the timezone otherwise. |
| `entity_id` | `Optional[str]` | **INTERNAL ONLY** -- routes a loose card to an entity at build time. NOT written to XML. |
| `link_id` | `Optional[str]` | **INTERNAL ONLY** -- routes a loose card to a link by `Link.link_id` at build time. NOT written to XML. |

`<TimeZone>` is the only valid child element of `<Card>` in ANB 9+.

---

## Unsupported representations

- **OLE Object**: Not exposed in the public API. The internal `Representation.OLE_OBJECT` enum exists but the builder falls back to emitting an `<Icon>`/`<IconStyle>` element. Validation rejects `representation='ole_object'` on `EntityType` with the `unsupported_representation` error type.
- **Box / Circle `line_color`**: ANB does not expose `LineColour` on `<BoxStyle>` or `<CircleStyle>`.

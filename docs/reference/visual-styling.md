# Visual Styling

Entity types, link types, strengths, legend items, label fonts, auto-coloring, named colors, and palettes.

---

## EntityType

Pre-register entity types to control the `<EntityType>` element in ANX XML. Entity types are **only** created when explicitly registered via `add_entity_type()`. Entities do not auto-register types. If no `EntityType` is registered for a type name, no `<EntityTypeCollection>` entry or `EntityTypeReference` is emitted.

```python
from anxwritter import EntityType

chart.add_entity_type(EntityType(name='Person', icon_file='person', shade_color='Blue'))
chart.add_entity_type(name='Vehicle', icon_file='vehicle')
```

### EntityType fields

| Field | Type | Default | XML attribute | Description |
|-------|------|---------|---------------|-------------|
| `name` | `str` | `''` | `Name` | Entity type name (required, mandatory in XML). |
| `icon_file` | `str` | `None` | `IconFile` | ANB icon key. Omitted when `None`. When empty, ANB looks up the type name in the loaded library catalogue. |
| `color` | `Optional[Union[int, str, Color]]` | `None` | `Colour` | **Line color** (not icon shading). `Color` enum, named color, `#RRGGBB`, or COLORREF int. Omitted when `None`. |
| `shade_color` | `Optional[Union[int, str, Color]]` | `None` | `IconShadingColour` | Icon tint/shading color. Same color forms as `color`. Omitted when `None`. |
| `representation` | `Optional[Union[str, Representation]]` | `None` | `PreferredRepresentation` | `'Icon'`, `'Box'`, `'Circle'`, `'ThemeLine'`, `'EventFrame'`, `'TextBlock'`, `'Label'` (or the matching `Representation` enum member). Omitted when `None`. |
| `semantic_type` | `Optional[str]` | `None` | `SemanticTypeGuid` | Type name resolved from semantic definitions or raw GUID. See [semantic-types.md](semantic-types.md). |

### i2 behaviour notes

- **`EntityTypeReference` precedence**: when set on `<IconStyle>`, i2 resolves the entity type from the referenced `<EntityType>.Name`, even if `<IconStyle>.Type` is also set with a different value.
- **`IconShadingColour` precedence**: can be set on both `<EntityType>` (type-level default) and `<IconStyle>` (per-entity override). Per-entity always wins.
- **Mandatory XML attributes**: only `Id` and `Name` are required. All others are optional.

---

## LinkType

Pre-register link types to control the `<LinkType>` element in ANX XML.

```python
from anxwritter import LinkType

chart.add_link_type(name='Call', color=255)
chart.add_link_type(LinkType(name='Transaction', color='Green', semantic_type='Transaction To'))
```

### LinkType fields

| Field | Type | Default | XML attribute | Description |
|-------|------|---------|---------------|-------------|
| `name` | `str` | `''` | `Name` | Link type name (required, mandatory in XML). |
| `color` | `Optional[Union[int, str, Color]]` | `None` | `Colour` | Line color. `Color` enum, named color, `#RRGGBB`, or COLORREF int. Omitted when `None`. |
| `semantic_type` | `Optional[str]` | `None` | `SemanticTypeGuid` | Type name resolved from semantic definitions or raw GUID. See [semantic-types.md](semantic-types.md). |

---

## Strengths

Strengths define named line styles (dash/dot patterns) for entity borders and link lines. The chart is pre-populated with `Default=solid`.

```python
from anxwritter import DotStyle, Strength

chart.add_strength(name='Confirmed', dot_style=DotStyle.SOLID)
chart.add_strength(name='Unconfirmed', dot_style=DotStyle.DASHED)
chart.add_strength(name='Tentative', dot_style=DotStyle.DOTTED)

# Reference on entities and links:
chart.add_icon(id='Alice', type='Person', strength='Confirmed')
chart.add_link(from_id='Alice', to_id='Bob', strength='Unconfirmed')
```

### Strength fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Strength name (required). Referenced by the `strength` field on entity and `Link` objects. |
| `dot_style` | `DotStyle\|str` | Line style. Accepts `DotStyle` enum or string literal. |

### `DotStyle` enum

```python
from anxwritter import DotStyle
```

| Enum value | String literal | Alias | Visual pattern |
|------------|---------------|-------|----------------|
| `DotStyle.SOLID` | `'solid'` | `'-'` | Solid line |
| `DotStyle.DASHED` | `'dashed'` | `'---'` | Long dashes |
| `DotStyle.DASH_DOT` | `'dash_dot'` | `'-.'` | Dash + dot alternating |
| `DotStyle.DASH_DOT_DOT` | `'dash_dot_dot'` | `'-..'` | Dash + two dots alternating |
| `DotStyle.DOTTED` | `'dotted'` | `'...'` | Evenly-spaced dots |

Full ANB names (`DotStyleSolid`, `DotStyleDashed`, etc.) are also accepted as passthrough.

---

## Legend items

Legend items define rows shown inside the legend overlay. Requires `legend_cfg.show=True` in settings for the legend panel to be visible (items are still generated when `show` is `False`/unset).

```python
from anxwritter import LegendItem, Font

chart.add_legend_item(name='Person', item_type='Icon', shade_color='Blue')
chart.add_legend_item(name='Knows', item_type='Link', color=0, line_width=1, arrows='->')
chart.add_legend_item(name='Confirmed', item_type='Line', color='Dark Blue', line_width=2)
chart.add_legend_item(name='Note', item_type='Font', font=Font(bold=True))
```

### ANB rendering order

Regardless of insertion order or XML order, ANB always groups and displays legend items in this fixed sequence:

**Text -> Attribute -> Icon -> Line -> Font -> Link -> TimeZone -> IconFrame**

### `LegendItemType` enum

The `item_type` field accepts the `LegendItemType` enum, lowercase strings, or the legacy
Title Case strings interchangeably. Validation rejects values outside this set.

```python
from anxwritter import LegendItem, LegendItemType

chart.add_legend_item(LegendItem(name='Person', item_type=LegendItemType.ICON))
chart.add_legend_item(LegendItem(name='Place',  item_type='icon'))         # equivalent
chart.add_legend_item(LegendItem(name='Thing',  item_type='Icon'))         # legacy form
```

| Enum value | Lowercase string | Legacy Title Case | ANB XML name |
|---|---|---|---|
| `LegendItemType.FONT` | `'font'` | `'Font'` (default) | `LegendItemTypeFont` |
| `LegendItemType.TEXT` | `'text'` | `'Text'` | `LegendItemTypeText` |
| `LegendItemType.ICON` | `'icon'` | `'Icon'` | `LegendItemTypeIcon` |
| `LegendItemType.ATTRIBUTE` | `'attribute'` | `'Attribute'` | `LegendItemTypeAttribute` |
| `LegendItemType.LINE` | `'line'` | `'Line'` | `LegendItemTypeLine` |
| `LegendItemType.LINK` | `'link'` | `'Link'` | `LegendItemTypeLink` |
| `LegendItemType.TIMEZONE` | `'timezone'` | `'TimeZone'` | `LegendItemTypeTimeZone` |
| `LegendItemType.ICON_FRAME` | `'icon_frame'` | `'IconFrame'` | `LegendItemTypeIconFrame` |

### `<Font>` child emission by type

| Behaviour | Item types |
|-----------|------------|
| **Always** emitted (auto-emitted with defaults) | Font, Text, TimeZone |
| **Only when font fields are set** | Icon, Attribute, IconFrame |
| **Never** emitted | Line, Link |

### LegendItem fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | **yes** | Text label for the legend item. Emitted as the `Label` XML attribute on `<LegendItem>`. |
| `item_type` | `Optional[Union[str, LegendItemType]]` | no | Legend item type. Default `'Font'`. Accepts the `LegendItemType` enum, lowercase string, or legacy Title Case string. |
| `color` | `Optional[Union[int, str, Color]]` | no | Line or frame color. `Color` enum, named color, `#RRGGBB`, or COLORREF int. Applies to `Line`, `Link`, and `IconFrame`. |
| `line_width` | `Optional[int]` | no | Line thickness (1--20). Applies to `Line` and `Link`. |
| `dash_style` | `Optional[str]` | no | Dash pattern: `'solid'`/`'-'`, `'dashed'`/`'---'`, `'dash_dot'`, `'dash_dot_dot'`, `'dotted'`/`'...'`. Default `'solid'`. |
| `arrows` | `Optional[str]` | no | Arrow style for `Link` only: `'head'`/`'->'`, `'tail'`/`'<-'`, `'both'`/`'<->'`. |
| `image_name` | `Optional[str]` | no | Icon key for `Icon`/`Attribute` rows (e.g. `'reddot'`, `'phone'`, `'national identifier'`). Emitted as `ImageName="..."` **attribute** on `<LegendItem>`. Confirmed working in ANB 9 (2026-04-24). Note: for `LegendItemTypeAttribute` rows, this is a free-form icon picker — the legend entry does NOT link to any `<AttributeClass>`. Not yet validated for `IconFrame`/`TimeZone`. |
| `shade_color` | `Optional[Union[int, str, Color]]` | no | Icon tint color for `Icon`/`Attribute`. `Color` enum, named color, `#RRGGBB`, or COLORREF int. Emits `IconShadingColour` attribute. |
| `font` | `Font` | no | Shared `Font` dataclass. Only emitted when at least one field is set. Font/Text/TimeZone types always emit a `<Font>` child (empty if no fields). |

---

## Label font (`Font` dataclass)

The `Font` dataclass is shared across chart-level font, legend font, attribute class font, and per-item label font. All fields are optional; omitting them preserves ANB defaults.

```python
from anxwritter import Font

# On entities
chart.add_icon(id='Alice', type='Person',
               label_font=Font(color='White', bg_color='Dark Blue',
                               name='Arial', size=12, bold=True))

# On links
chart.add_link(from_id='Alice', to_id='Bob', type='Call',
               label_font=Font(italic=True, color='Dark Blue'))
```

### Font fields

| Field | Type | Default | XML attribute |
|-------|------|---------|---------------|
| `name` | `str` | `'Tahoma'` | `FaceName` |
| `size` | `int` | `10` | `PointSize` |
| `color` | `int\|str` | `0` (black) | `FontColour` |
| `bg_color` | `int\|str` | `16777215` (white) | `BackColour` |
| `bold` | `bool` | `False` | `Bold` |
| `italic` | `bool` | `False` | `Italic` |
| `strikeout` | `bool` | `False` | `Strikeout` |
| `underline` | `bool` | `False` | `Underline` |

The `<Font>` element is only emitted when at least one field is explicitly set. When no fields are set, the element is omitted entirely and ANB uses its own defaults.

**Note:** `label_font.bg_color` styles the **label text background**, not the entity icon shading. Icon shading is controlled by the `color` field on `Icon` entities or `shade_color` on other types.

---

## Auto-coloring

### `entity_auto_color`

When `extra_cfg.entity_auto_color=True`, evenly-spaced HSV hues are distributed across entities that have no explicit `color`. Also sets `label_font.bg_color` to match and `label_font.color` to black or white for contrast.

Explicit values on any of `color`, `label_font.color`, or `label_font.bg_color` always take priority over auto-computed values.

```python
chart = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})

chart.add_icon(id='Hub', type='Person', color='Gold')      # kept as-is
chart.add_icon(id='Spoke-1', type='Person')                  # auto-colored
chart.add_icon(id='Spoke-2', type='Person')                  # auto-colored
```

### `link_match_entity_color`

When `extra_cfg.link_match_entity_color=True`, each link's `LineColour` is set to the resolved color of its `to_id` entity. This only affects the line color, not the link label font. An explicit `line_color` on a `Link` always overrides this.

```python
chart = ANXChart(settings={
    'extra_cfg': {'entity_auto_color': True, 'link_match_entity_color': True},
})
```

---

## Named colors and the `Color` enum

All color-typed fields across the API (`color`, `bg_color`, `line_color`, `shade_color`,
`label_font.color`, `label_font.bg_color`, `Frame.color`, `EntityType.color`,
`LinkType.color`, etc.) have type `Optional[Union[int, str, Color]]` and accept any of
these forms:

| Form | Example | Notes |
|---|---|---|
| `Color` enum | `Color.BLUE`, `Color.LIGHT_ORANGE` | IDE autocomplete; one member per ANB shading color. |
| Title Case name | `'Blue'`, `'Light Orange'`, `'Blue-Grey'` | Canonical form, kept for backward compat. |
| Lowercase / mixed case | `'blue'`, `'BLUE'`, `'light orange'` | **Case-insensitive** — `'blue'`, `'BLUE'`, and `'Blue'` all resolve. |
| Snake case / hyphen | `'light_orange'`, `'light-orange'`, `'blue_grey'` | Normalized via `colors._normalize_name`. |
| `#RRGGBB` hex | `'#FF0000'` | 6-digit hex with `#` prefix. |
| Bare 6-char hex | `'FF0000'` | Same as above without `#`. |
| COLORREF int | `0xFFFFFF`, `16711680` | Windows COLORREF: `R + G*256 + B*65536`. |

```python
from anxwritter import ANXChart, Color

chart = ANXChart()
chart.add_icon(id='Alice', type='Person', color=Color.BLUE)
chart.add_icon(id='Bob',   type='Person', color='light_orange')   # equivalent to Color.LIGHT_ORANGE
chart.add_icon(id='Carol', type='Person', color='#FF6600')
```

The `Color` enum has 40 members — one per `NAMED_COLORS` key. Member names use
`UPPER_SNAKE_CASE` (`BLUE_GREY`, `LIGHT_ORANGE`); values are `lowercase_snake_case`
(`'blue_grey'`, `'light_orange'`).

### All 40 named colors

| Name | RGB | Hex |
|------|-----|-----|
| Black | (0, 0, 0) | `#000000` |
| Brown | (153, 51, 0) | `#993300` |
| Olive Green | (51, 51, 0) | `#333300` |
| Dark Green | (0, 51, 0) | `#003300` |
| Dark Teal | (0, 51, 102) | `#003366` |
| Dark Blue | (0, 0, 128) | `#000080` |
| Indigo | (51, 51, 153) | `#333399` |
| Dark Grey | (51, 51, 51) | `#333333` |
| Dark Red | (128, 0, 0) | `#800000` |
| Orange | (255, 102, 0) | `#FF6600` |
| Dark Yellow | (128, 128, 0) | `#808000` |
| Green | (0, 128, 0) | `#008000` |
| Teal | (0, 128, 128) | `#008080` |
| Blue | (0, 0, 255) | `#0000FF` |
| Blue-Grey | (102, 102, 153) | `#666699` |
| Grey | (128, 128, 128) | `#808080` |
| Red | (255, 0, 0) | `#FF0000` |
| Light Orange | (255, 153, 0) | `#FF9900` |
| Lime | (153, 204, 0) | `#99CC00` |
| Sea Green | (51, 153, 102) | `#339966` |
| Aqua | (51, 204, 204) | `#33CCCC` |
| Light Blue | (51, 102, 255) | `#3366FF` |
| Violet | (128, 0, 128) | `#800080` |
| Light Grey | (153, 153, 153) | `#999999` |
| Pink | (255, 0, 255) | `#FF00FF` |
| Gold | (255, 204, 0) | `#FFCC00` |
| Yellow | (255, 255, 0) | `#FFFF00` |
| Bright Green | (0, 255, 0) | `#00FF00` |
| Turquoise | (0, 255, 255) | `#00FFFF` |
| Sky Blue | (0, 204, 255) | `#00CCFF` |
| Plum | (153, 51, 102) | `#993366` |
| Silver | (192, 192, 192) | `#C0C0C0` |
| Rose | (255, 153, 204) | `#FF99CC` |
| Tan | (255, 204, 153) | `#FFCC99` |
| Light Yellow | (255, 255, 153) | `#FFFF99` |
| Light Green | (204, 255, 204) | `#CCFFCC` |
| Light Turquoise | (204, 255, 255) | `#CCFFFF` |
| Pale Blue | (153, 204, 255) | `#99CCFF` |
| Lavender | (204, 153, 255) | `#CC99FF` |
| White | (255, 255, 255) | `#FFFFFF` |

Color conversion utilities are available in `anxwritter.colors`:

- `color_to_colorref(color: Any) -> int` -- accepts `Color` enum, named color, normalized name (`'light_orange'`), `#RRGGBB`, or int passthrough.
- `rgb_to_colorref(r: int, g: int, b: int) -> int` -- converts an RGB triple to a COLORREF integer.
- `NAMED_COLORS` -- dict mapping the 40 Title Case color names to COLORREF integers.
- `_normalize_name(name: str) -> str` -- internal helper that produces the canonical lookup key (`'Light Orange'` / `'light-orange'` -> `'light_orange'`).
- `_NAMED_COLORS_NORM` -- internal dict mapping normalized names to COLORREF integers; used by both `color_to_colorref` and `utils._is_valid_color`.

---

## Palettes

Palettes define the contents of ANB's "Insert from Palette" UI panel.

```python
from anxwritter import Palette, PaletteAttributeEntry

chart.add_palette(Palette(
    name='Investigation',
    entity_types=['Person', 'Organization'],
    link_types=['Call', 'Transaction'],
    attribute_classes=['Phone', 'Balance'],
    attribute_entries=[PaletteAttributeEntry(name='Currency', value='BRL')],
))
```

### Palette fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `'Standard'` | Palette name shown in ANB UI. |
| `locked` | `bool` | `False` | Locks the order of entity types within the palette. |
| `entity_types` | `List[str]` | `[]` | List of `EntityType` names to include. |
| `link_types` | `List[str]` | `[]` | List of `LinkType` names to include. |
| `attribute_classes` | `List[str]` | `[]` | List of `AttributeClass` names (no values). |
| `attribute_entries` | `List[PaletteAttributeEntry]` | `[]` | Attribute entries with pre-filled values. |

### PaletteAttributeEntry fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `''` | `AttributeClass` name (required). |
| `value` | `str` | `None` | Pre-filled value. `None` = class only, no default value. |

### Auto-populate behaviour

When no palettes are explicitly defined, a single `"anxwritter"` palette is auto-generated containing all registered entity types, link types, and attribute classes (excluding those with `is_user=False` or `user_can_add=False`). `attribute_entries` are never auto-populated.

When the user defines at least one palette explicitly, only those palettes are emitted -- no auto-population.

### Constraints

- Attribute classes with `is_user=False` **cannot** appear in palettes. ANB rejects palette entries pointing at non-user-addable attribute classes at import time.
- Attribute classes with `user_can_add=False` **cannot** appear in palettes. Same rejection.
- Palette entry values are type-checked against the attribute class type at validation time.
- Validation errors: `palette_unknown_ref`, `palette_invalid_class`, `palette_type_mismatch`. See [validation.md](validation.md).

### XML structure

```xml
<PaletteCollection>
  <Palette Name="Investigation">
    <AttributeClassEntryCollection>...</AttributeClassEntryCollection>
    <AttributeEntryCollection>...</AttributeEntryCollection>
    <EntityTypeEntryCollection>...</EntityTypeEntryCollection>
    <LinkTypeEntryCollection>...</LinkTypeEntryCollection>
  </Palette>
</PaletteCollection>
```

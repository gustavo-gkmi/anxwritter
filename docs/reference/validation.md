# Validation

How chart validation works, the `ANXValidationError` exception, all validation error types, and common pitfalls.

---

## How `validate()` works

```python
errors = chart.validate()   # returns list of error dicts; empty = valid
```

`validate()` checks the chart data for structural and referential integrity without building XML. It returns a list of error dicts. An empty list means the chart is valid.

`to_anx()` and `to_xml()` call `validate()` internally. If any errors are found, they raise `ANXValidationError`.

```python
from anxwritter.errors import ANXValidationError

try:
    chart.to_anx('output/my_chart')
except ANXValidationError as e:
    print(e)
```

---

## `ANXValidationError`

Defined in `anxwritter.errors`. Raised by `to_anx()` and `to_xml()` when `validate()` returns a non-empty error list.

```python
from anxwritter.errors import ANXValidationError
```

The exception message contains a human-readable summary of all validation errors. The underlying error list is accessible on the exception object.

---

## Validation error types

Every error dict has a `type`, a `message`, and (almost always) a `location` string pointing at the offending row (e.g. `"entities[2] (Icon)"`, `"links[7]"`, `"attribute_classes[0].type"`). The `config_conflict` error additionally includes `section`, `name`, `config_value`, and `data_value`. No other error types add fields.

| Error type | Trigger | Notes |
|------------|---------|-------|
| `missing_required` | Required field missing. | `id`/`type` on entities, `from_id`/`to_id` on links, `name` on `LegendItem` / `EntityType` / `LinkType` / `Strength` / `DateTimeFormat`, both `name` AND `type` on `AttributeClass`, `name` on `PaletteAttributeEntry`, `name` and `kind_of` on `SemanticEntity`/`SemanticLink`, `name` and `base_property` on `SemanticProperty`. |
| `duplicate_id` | Same entity `id` used more than once. | Entity identity is globally unique in ANB. |
| `duplicate_name` | Duplicate `name` in type definitions. | Applies to `EntityType`, `LinkType`, `Strength`, `AttributeClass`, and `DateTimeFormat` definitions. |
| `missing_entity` | Link endpoint references a nonexistent entity. | `from_id` or `to_id` does not match any added entity `id`. |
| `missing_target` | Loose card target not found. | `entity_id` does not match any added entity, or `link_id` does not match any `Link.link_id`. |
| `unknown_color` | Invalid color value. | Value is not a valid COLORREF integer, named color from the 40 ANB names (case-insensitive, normalized form accepted), `Color` enum, or `#RRGGBB` hex string. |
| `invalid_date` | Date format violation. | Date string is not in any of the supported formats: `yyyy-MM-dd` (canonical), `dd/MM/yyyy`, `yyyymmdd`. The ambiguous US `mm/dd/yyyy` is intentionally rejected. |
| `invalid_time` | Time format violation. | Time string is not in any of the supported formats: `HH:MM:SS` (canonical), `HH:MM:SS.ffffff` (microseconds), `HH:MM` (no seconds), `HH:MM AM/PM` (12-hour). |
| `type_conflict` | Attribute type mismatch. | Same attribute name used with different inferred Python types across entities/links (e.g. `Balance` as `float` in one entity and `str` in another), or an `AttributeClass.type` declaration disagrees with the data. |
| `invalid_strength` | Unknown strength name. | Strength name referenced on an entity or link is not registered via `add_strength()`. |
| `invalid_strength_default` | Unknown default strength. | `StrengthCollection.default` references a name not present in `items`. |
| `invalid_arrow` | Invalid arrow style. | Link `arrow` value is not `'head'`/`'->'`, `'tail'`/`'<-'`, `'both'`/`'<->'`, or a full ANB name. |
| `invalid_grade_default` | Unknown default grade. | `GradeCollection.default` references a name not present in `items`. |
| `grade_out_of_range` | Grade index exceeds collection bounds. | Grade index is negative or >= the length of the corresponding grade collection (`grades_one`, `grades_two`, or `grades_three`). |
| `unknown_grade` | Grade name not found in collection. | A `grade_one`/`grade_two`/`grade_three` value is given as a name string but does not match any entry in the corresponding `GradeCollection.items`. No auto-create -- register the name first. |
| `self_loop` | Link endpoints are the same entity. | `from_id` equals `to_id`. |
| `invalid_ordered` | Invalid `ordered=True` usage on a link. | `ordered=True` on a link whose endpoints are not both ThemeLine entities. ANB rejects this combination at import time and reports it as an "Ordered link must connect themes" error in the import log. |
| `invalid_legend_type` | Unrecognized legend item type. | `item_type` on a `LegendItem` is not a `LegendItemType` enum value, lowercase string (`'icon'`), or legacy Title Case (`'Icon'`). See [visual-styling.md](visual-styling.md#legenditemtype-enum). |
| `invalid_timezone` | Malformed timezone. | `TimeZone` dataclass missing `id` or `name` field, or `id` is not an integer in the range 1--122. |
| `timezone_without_datetime` | Timezone set without both date and time. | Timezone is set on an entity, link, or card but `date` or `time` is missing. ANB silently ignores the timezone in this case. |
| `invalid_multiplicity` | Invalid multiplicity value. | `multiplicity` on a `Link` is not `'multiple'`, `'single'`, or `'directed'`. |
| `invalid_theme_wiring` | Invalid theme wiring value. | `theme_wiring` on a `Link` is not `'keep_event'`, `'return_theme'`, `'next_event'`, or `'no_diversion'`. |
| `connection_conflict` | Conflicting connection styles between same entity pair. | Links between the same entity pair set different `(multiplicity, fan_out, theme_wiring)` tuples. Error message reports the specific tuple comparison. |
| `unregistered_datetime_format` | Unregistered format name. | `datetime_format` on an entity or link references a name not registered via `add_datetime_format()`. ANB 9 only accepts registered names. |
| `invalid_value` | Value exceeds limits. | e.g. `DateTimeFormat.name` > 250 chars, `DateTimeFormat.format` > 259 chars. |
| `unsupported_representation` | OLE Object representation declared. | `EntityType.representation` is set to `'OLE_OBJECT'` (or equivalent), which the builder does not yet implement. Use `'icon'`, `'box'`, `'circle'`, `'theme_line'`, `'event_frame'`, `'text_block'`, or `'label'`. |
| `invalid_semantic_type` | LN-prefixed semantic type name. | `semantic_type` value matches the i2 COM API name pattern (e.g. `'LNEntityPerson'`). Use the standard type name (`'Person'`) or a raw GUID instead. |
| `invalid_merge_behaviour` | Invalid merge behaviour. | `AttributeClass.merge_behaviour` is unknown or invalid for the declared attribute type (e.g. `'add_space'` on a Number class). |
| `invalid_paste_behaviour` | Invalid paste behaviour. | `AttributeClass.paste_behaviour` is unknown or invalid for the declared attribute type. |
| `invalid_geo_map` | Invalid geo_map configuration. | `extra_cfg.geo_map` is missing `attribute_name`, has an unknown `mode`, non-positive `width`/`height`, negative `spread_radius`, no `data` or `data_file`, or out-of-range lat/lon coordinates. |
| `config_conflict` | Config-locked name redefined with different specs. | Only raised when a config file was applied. The data file attempts to redefine a config-locked entry with different values. Error dict includes `section`, `name`, `config_value`, and `data_value`. See [constructors.md](constructors.md). |
| `palette_unknown_ref` | Palette references unregistered name. | An entity type, link type, or attribute class name in a palette definition is not registered. |
| `palette_invalid_class` | Palette references restricted attribute class. | Attribute class with `is_user=False` or `user_can_add=False` cannot appear in palettes. ANB rejects palette entries pointing at non-user-addable attribute classes at import time. |
| `palette_type_mismatch` | Palette entry value/type mismatch. | Palette attribute entry value does not match the attribute class type (e.g. non-numeric string for a Number class). |

---

## Common pitfalls

| Issue | Fix |
|-------|-----|
| Entity not shown | Ensure `id` and `type` are set on the entity. |
| Link not shown | Ensure `from_id` and `to_id` match an existing entity `id`. |
| Invalid color | Use one of the 40 named colors (case-insensitive — `'blue'`, `'BLUE'`, and `'Blue'` all work), the `Color` enum (`Color.BLUE`), a `#RRGGBB` hex string, or a COLORREF integer. See [visual-styling.md](visual-styling.md) for the full list. |
| `label_font.bg_color` vs `color` | `color` sets icon shading. `label_font.bg_color` sets the text-label background. They are independent. |
| Auto-color overridden | `entity_auto_color` only fills in `color`/`label_font.color`/`label_font.bg_color` when they are `None`. Set them explicitly to prevent auto-coloring for specific entities. |
| Attribute type conflict | All uses of the same attribute name must resolve to the same Python type. Mixing types (e.g. `str` and `int` for the same key) is reported as `type_conflict` and `to_anx()`/`to_xml()` raise `ANXValidationError`. |
| `strength` not applied | `strength` only produces a visible effect on Box, Circle, ThemeLine, and EventFrame. No visible effect on Icon entities. |
| Wrong entity class | `add_box()` renders as a Rectangle, `add_icon()` renders as an Icon. Use the class matching the intended ANB shape. |
| Loose card not resolved | `add_card(entity_id=...)` raises `ANXValidationError` at build time if `entity_id` does not match any added entity. Same for `link_id`. |
| TimeZone without date+time | `timezone` is silently ignored by ANB when an item has no `date` and `time` set. Always provide both. Validation warns with `timezone_without_datetime`. |
| `ordered=True` on non-ThemeLine link | Only valid when both link endpoints are ThemeLine entities. Other combinations raise `invalid_ordered`. |
| Inline format string as `datetime_format` | ANB 9 rejects inline format strings. Register the format first with `add_datetime_format()` and reference by name. |
| Palette with `is_user=False` class | Attribute classes with `is_user=False` or `user_can_add=False` cannot be included in palettes. |

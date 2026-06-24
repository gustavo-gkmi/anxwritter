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

Every error dict has a `type`, a `message`, and (almost always) a `location` string pointing at the offending row (e.g. `"entities[2] (Icon)"`, `"links[7]"`, `"attribute_classes[0].type"`). The `config_conflict` error additionally includes `section`, `name`, `config_value`, and `data_value`.

Errors that originate from a config-tagged entry (see [`source_name`](constructors.md#tagging-layers-with-source_name)) also carry an optional `source` key naming the layer; `config_conflict` errors gain a `config_source` key naming the layer that locked the original entry. Both are present only when the layer supplied a `source_name` (or was loaded via `apply_config_file` / `from_config_file`, which auto-derive one from the path). `ANXValidationError`'s formatted message string (`str(exc)`) appends `(source: X)` / `(config source: X)` per line — that string format is **explicitly unstable** and may change between releases. Match on the dict keys, not the rendered text.

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
| `icon_map_invalid` | Invalid icon_map rule. | `extra_cfg.icon_map` rule has an unknown `match`, an empty `mapping`, `default`/`default_when_absent`/`type` set on an id rule, an attribute rule missing `attribute_name`, or a `type` filter referencing an unknown entity type. |
| `config_conflict` | Config-locked name redefined with different specs. | Only raised when a config file was applied. The data file attempts to redefine a config-locked entry with different values. Error dict includes `section`, `name`, `config_value`, `data_value`, and (when the locking layer was tagged) `config_source`. See [constructors.md](constructors.md). |
| `palette_unknown_ref` | Palette references unregistered name. | An entity type, link type, or attribute class name in a palette definition is not registered. |
| `palette_invalid_class` | Palette references restricted attribute class. | Attribute class with `is_user=False` or `user_can_add=False` cannot appear in palettes. ANB rejects palette entries pointing at non-user-addable attribute classes at import time. |
| `palette_type_mismatch` | Palette entry value/type mismatch. | Palette attribute entry value does not match the attribute class type (e.g. non-numeric string for a Number class). |
| `invalid_intensity_config` | Bad intensity styling config. | `extra_cfg.styling.links.intensity` has an unknown `scale`, missing `power` when `scale='power'`, `diverging: true` without `midpoint`, or another structural error. |
| `invalid_intensity_attribute` | Intensity attribute missing or non-numeric. | The attribute named by `intensity.attribute` is missing on every link, or some links have non-numeric values. |
| `invalid_intensity_domain` | Bad domain or log-scale with non-positive value. | `domain` is malformed, or `scale: log` was used with a value ≤ 0. |
| `invalid_intensity_range` | Bad `width.range`. | Width range is malformed, negative, or `range[0] >= range[1]`. |
| `invalid_intensity_ramp` | Bad color ramp. | Ramp has fewer than two colors or contains an unresolvable color. |
| `invalid_categorical_config` | Bad categorical styling config. | `extra_cfg.styling.links.categorical` has missing/empty `styles` or unknown `missing` policy. |
| `invalid_categorical_attribute` | Categorical attribute missing or unresolved. | The attribute named by `categorical.attribute` is missing on a link (only emitted when `missing: 'error'`), or the `attribute` field itself is missing. |
| `invalid_categorical_style` | Bad style entry. | A `styles` value has no settable fields, an unresolvable `line_color`, a negative `line_width`, or references an unregistered `strength`. |
| `styling_conflict` | Both intensity and categorical target the same attribute. | Pick one — mixed numeric-and-lookup styling on the same attribute has ambiguous precedence. |
| `datetime_ac_forbids_visible` | `datetime` AttributeClass with `visible=True`. | ANB v9 does not render datetime values on the canvas, so the chrome would render with no value. Set `visible=False` and add an `extra_cfg.display_attribute` entry with a `"{d:%Y-%m-%d}"`-style template referencing this AC to render the formatted date as a paired text sibling. See [attributes.md → Display synthesizers](attributes.md#display-synthesizers). |
| `display_invalid` | Malformed `display_attribute` / `display_label` entry. | Missing `key` or `template`; empty `sources` when the template references placeholders (a placeholder-free static template needs no sources); missing `attribute_name` (attribute family); undeclared source AC; non-identifier attribute name without `alias`; duplicate alias within an entry; inner `attribute_class.name`/`.type` set; template syntax error; `missing='error'` triggered for an item. (A visible source AC is allowed; a visible `datetime` source is caught by `datetime_ac_forbids_visible` instead.) |
| `display_name_collision` | Synthesised AC name collides. | A `display_attribute` `attribute_name` collides with an explicit `AttributeClass`. (Multiple `display_attribute` entries may share an `attribute_name` for disjoint `(kind, type)` scopes.) |
| `display_overlap_conflict` | Two display entries fight over one slot. | Two same-specificity entries could paint the same slot — the label, or the same `attribute_name` — for an overlapping `(kind, type)`. Scope them to disjoint types or merge them. A `type`-scoped entry beats an untyped one (no conflict). |
| `locked_override` | A config layer changed a locked leaf. | A later config layer tried to change a leaf frozen by an earlier `lock=True` layer (merge, or delete). The locked value is preserved; carries `locked_value` / `attempted_value` and (when known) `config_source`. |
| `delete_contract` | Bad `operation='delete'` layer entry. | A non-identity field in a delete layer carries a non-null value. Write `field:` (null) to unset a field, or list only the identity to remove the whole entry. |
| `id_pattern_mismatch` | Entity/link `id` fails its type's `enforce.id_pattern`. | `EntityType.enforce.id_pattern` (or `LinkType.enforce.id_pattern`) declared a regex; the `id` value didn't match. Carries `entity_id`/`link_index`, `entity_type`/`link_type`, `received_value`, `pattern`, `description`, `rule_source=entity_type[<name>]`/`link_type[<name>]`. |
| `attribute_pattern_mismatch` | Attribute value fails a pattern rule. | `AttributeClass.enforce.pattern` or a top-level `validators[]` entry's `pattern` failed for an attribute on an entity/link. Carries `entity_id`/`link_index`, `attribute_name`, `received_value`, `pattern`, `description`, `rule_source` (`attribute_class[<name>]` or `validator[<synthetic_key>]`). |
| `attribute_value_not_allowed` | Attribute value not in `allowed_values`. | `AttributeClass.enforce.allowed_values` or a `validators[]` entry's `allowed_values` rejected the value. Carries `received_value`, `allowed_values`, and the same identity / rule_source fields as `attribute_pattern_mismatch`. |
| `required_attribute_missing` | A required attribute is absent. | `EntityType.enforce.required_attributes` (or `LinkType.enforce.required_attributes`) named an attribute that isn't on the entity/link. |
| `validator_invalid_scope` | Validator entry's scope is malformed. | Top-level `validators[]` entry sets both `entity_type` AND `link_type`, or neither. Set exactly one. |
| `validator_invalid_shape` | Validator entry's shape is malformed. | `pattern` AND `allowed_values` both set in one entry, or neither. Set exactly one. |
| `validator_reserved_attribute` | Validator targets the reserved `id` attribute. | Use `EntityType.enforce.id_pattern` (or `LinkType.enforce.id_pattern`) for entity/link identity rules. |
| `validator_unknown_type` | Validator references an unregistered type. | The `entity_type` / `link_type` named in the validator entry isn't registered in `entity_types` / `link_types`. |
| `validator_duplicate_key` | Two validators synthesize the same key. | Two entries with the same `(entity_type|link_type, attribute)` scope in the same layer. Only one rule per pair is allowed. (Cross-layer duplicates field-merge — that's how overrides work.) |
| `pattern_missing_description` | `pattern` declared without `description`. | Regex is unreadable to non-developers; the description is the user-facing error message. Required for any `pattern` declaration (`AttributeClass.enforce.pattern`, `EntityType.enforce.id_pattern`, `LinkType.enforce.id_pattern`, `Validator.pattern`). `allowed_values` is self-documenting and doesn't need one. |

---

## Value enforcement (1.17.0)

Declarative value rules for entity/link `id` format, required attributes, and
attribute value constraints (regex or closed enum). Three places to declare them:

| Where | Field | Purpose |
|---|---|---|
| `AttributeClass.enforce.pattern` / `allowed_values` | (with `description`) | Wide rule: every value of this attribute, wherever it appears (entity or link), must satisfy the rule. |
| `EntityType.enforce.id_pattern` / `required_attributes` | (with `id_pattern_description`) | Per-type identity format + required-attribute list. |
| `LinkType.enforce.id_pattern` / `required_attributes` | (with `id_pattern_description`) | Same shape as EntityType. (`id_pattern` is a no-op until `link_id` becomes external; `required_attributes` works today.) |
| Top-level `validators[]` | scope: `entity_type` OR `link_type`, `attribute`, + `pattern` OR `allowed_values` | Flexible per-(type, attribute) rule. Synthesized key `E::<type>::<attr>` / `L::<type>::<attr>` is the identity for layering, lock, delete, and error `rule_source`. |

**Compound AND semantics.** When both an AC-level rule and a top-level
`validators[]` rule target the same value, both fire. Each error dict
carries `rule_source` (`attribute_class[<name>]` or
`validator[<synthetic_key>]`) so consumers can route, dedupe, or group.

**No normalization.** The library never rewrites values to satisfy
patterns. Drift surfaces as errors so the consumer pipeline knows it's
broken. If you want to accept both masked and unmasked CPF, express it
in the regex (e.g. `^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$|^\d{11}$`).

**Library is locale-neutral.** No bundled named validators (CPF, SSN,
NHS, etc.). Regex covers format; closed enums use `allowed_values`.
Check-digit / locale-specific validation is the consumer's responsibility.

**Pattern matching uses `re.fullmatch`** — the entire string must match.
Anchors (`^` / `$`) are optional. Bad regex raises at config load
(`ValueError` at dataclass construction).

**Cross-layer shape switch.** Changing a validator entry from `pattern`
to `allowed_values` across config layers requires explicitly nulling the
previous field in the overriding layer (e.g. `pattern: null` alongside
`allowed_values: [...]`); otherwise field-merge leaves both set and
surfaces as `validator_invalid_shape` at validate time.

### Minimal YAML

```yaml
entity_types:
  - name: Person
    icon_file: person
    enforce:
      id_pattern: '^\d{11}$'
      id_pattern_description: 'CPF — 11 digits, no punctuation'
      required_attributes: [Name, CPF]

link_types:
  - name: Transfer
    enforce:
      required_attributes: [Amount, Currency]

attribute_classes:
  - name: CPF
    type: text
    enforce:
      pattern: '^\d{11}$'
      description: 'CPF — 11 digits, no punctuation'
  - name: Country
    type: text
    enforce:
      allowed_values: ['BR', 'US', 'UK', 'PT']

validators:
  - entity_type: Person
    attribute: CPF
    pattern: '^[1-9]\d{10}$'
    description: 'CPF must not start with 0'
  - link_type: Transfer
    attribute: Currency
    allowed_values: ['BRL', 'USD', 'EUR']
```

### Smart-truncating error message

`str(ANXValidationError)` groups errors by `(rule_source, type)` and
shows up to 5 examples per group with a "... N more" tail. The
underlying `errors` list stays uncapped for programmatic consumers.
The formatted string format is explicitly **unstable** — match on the
dict keys, not `str(exc)`.

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
| ANB rejects file with `CreateAttributeClass: failed to create attribute class` | An `attribute_classes` entry collides with a name ANB 9 reserves internally (e.g. `Peso` in some locales). Bisect `attribute_classes` to isolate the offending name, then remove that declaration — ANB supplies the class automatically. See [attributes.md → ANB built-in / reserved attribute names](attributes.md#anb-built-in--reserved-attribute-names). |

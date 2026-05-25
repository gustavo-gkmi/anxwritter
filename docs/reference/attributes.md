# Attributes Reference

Attributes are extra key/value metadata attached to entities or links via the `attributes` dict field.

```python
from anxwritter import ANXChart, AttributeClass
from anxwritter import MergeBehaviour
```

---

## Attribute type inference

The attribute type is inferred from the Python value type. All uses of the same attribute name across all entities and links in a chart must resolve to the same type.

| Python type | anxwritter type | ANX XML type | Notes |
|---|---|---|---|
| `str` | `Text` | `AttText` | String values. |
| `int` | `Number` | `AttNumber` | Integer values. |
| `float` | `Number` | `AttNumber` | Decimal values. |
| `bool` | `Flag` | `AttFlag` | Boolean values. Emitted as `"true"` / `"false"` strings in XML. |
| `datetime` | `DateTime` | `AttTime` | Serialized to `YYYY-MM-DDTHH:MM:SS` (ISO 8601, `T` separator required). Python `datetime` objects are automatically serialized to this format. Do NOT use `str(datetime_obj)` directly -- that produces a space separator which ANB rejects. |

User-facing API type strings are the lowercase `AttributeType` enum values: `'text'`, `'number'`, `'flag'`, `'datetime'` (case-insensitive when passed as strings). Internally the inferred type tags from Python values are Title Case (`'Text'`, `'Number'`, `'Flag'`, `'DateTime'`). The ANX XML uses the `Att`-prefixed names (`AttText`, `AttNumber`, `AttFlag`, `AttTime`).

`AttDateTime` and `AttDate` are invalid ANX XML type values -- they cause schema errors. Python `datetime` values always map to `AttTime`.

> **JSON / YAML callers — datetime escape hatch.** JSON has no datetime
> literal, so a value like `"Joined": "2024-01-15T10:00:00"` parses as a
> plain string and would otherwise become a Text attribute. Declare the
> attribute name in `attribute_classes` with `type: datetime` and the
> loader will coerce matching ISO 8601 string values to `datetime`
> instances during `from_dict` / `from_json` / `from_yaml`. See the
> [YAML / JSON Guide § Datetime attribute values](../guide/yaml-json-guide.md#datetime-attribute-values).

### Usage

```python
from datetime import datetime

chart.add_icon(id='Alice', type='Person', attributes={
    'Phone Number': '555-0001',            # str   -> Text (AttText)
    'Call Count':   12,                    # int   -> Number (AttNumber)
    'Balance':      4500.50,               # float -> Number (AttNumber)
    'Active':       True,                  # bool  -> Flag (AttFlag)
    'Joined':       datetime(2022, 6, 15), # datetime -> DateTime (AttTime)
})
```

---

## Type conflict validation

If the same attribute name is used with different inferred types across entities or links, validation reports a `type_conflict` error and `to_anx()`/`to_xml()` raise `ANXValidationError`. All uses of the same attribute name must resolve to the same type.

```python
# validate() returns a type_conflict error; to_anx() raises ANXValidationError
chart.add_icon(id='A', type='Person', attributes={'Balance': 4500.50})
chart.add_icon(id='B', type='Person', attributes={'Balance': 'unknown'})
```

If an `AttributeClass` object declares a `type` that contradicts the type inferred from the data, the same `type_conflict` error is reported (also surfaced as `ANXValidationError` on build). The type is never coerced.

---

## `AttributeClass` configuration

`AttributeClass` controls class-level display settings for named attribute types. Every explicit declaration must include a `type` -- validation emits `missing_required` otherwise. Add only entries you want to customize; attribute names that appear in entity/link `attributes` dicts but are never declared get a class auto-registered with the inferred type and ANB's default display settings.

```python
chart.add_attribute_class(name='Balance', type='number', prefix='R$ ', decimal_places=2)
chart.add_attribute_class(name='Phone',   type='text',   prefix='Tel: ')
chart.add_attribute_class(name='Active',  type='flag',   show_if_set=True)

# Or pass the dataclass directly
chart.add(AttributeClass(name='Balance', type='number', prefix='R$ ', decimal_places=2))
```

### `AttributeClass` fields

Every field is declared `Optional[...] = None` on the dataclass. The "ANB default" column shows the value ANB falls back to when the attribute is omitted from the XML; it is **not** the field's Python default. Only fields you explicitly set become XML attributes.

| Field | Type | ANX attribute | Applies to | ANB default | Description |
|---|---|---|---|---|---|
| `name` | `str` | `Name` | All | `''` (**required**) | Attribute class name. Primary key -- uniquely identifies the class within the chart. |
| `type` | `Optional[AttributeType]` | `Type` | All | **required** on every declaration | Attribute data type. Use the `AttributeType` enum or one of the lowercase strings `'text'`, `'number'`, `'flag'`, `'datetime'`. Validation emits `missing_required` if omitted, and `type_conflict` if it disagrees with the inferred type from data. The library never infers the type for declared classes. |
| `prefix` | `Optional[str]` | `Prefix` | All | `''` | Prefix string displayed before the value. When set to a non-empty string, `ShowPrefix="true"` is auto-emitted. |
| `suffix` | `Optional[str]` | `Suffix` | All | `''` | Suffix string displayed after the value. When set to a non-empty string, `ShowSuffix="true"` is auto-emitted. |
| `show_value` | `Optional[bool]` | `ShowValue` | All | `True` -- always emitted | Whether the attribute value is displayed. Always emitted as `ShowValue="true"` when unset (ANB's silent default for omitted `ShowValue` is `false`; anxwritter forces `true` because the value is what analysts want to see in 99% of charts). Set `show_value=False` explicitly to hide. |
| `decimal_places` | `Optional[int]` | `DecimalPlaces` | Number | `0` | Number of decimal places for Number attributes. |
| `show_date` | `Optional[bool]` | `ShowDate` | DateTime | `True` | Whether the date part is displayed for DateTime attributes. |
| `show_time` | `Optional[bool]` | `ShowTime` | DateTime | `True` | Whether the time part is displayed for DateTime attributes. |
| `show_seconds` | `Optional[bool]` | `ShowSeconds` | DateTime | `False` | Whether seconds are displayed for DateTime attributes. |
| `show_if_set` | `Optional[bool]` | `ShowIfSet` | Flag | `False` | Whether the Flag attribute is shown when its value is `True`. |
| `show_class_name` | `Optional[bool]` | `ShowClassName` | All | `False` | Whether the attribute class name is displayed alongside the value. |
| `show_symbol` | `Optional[bool]` | `ShowSymbol` | All | `True` | Whether the attribute symbol/icon is displayed. |
| `visible` | `Optional[bool]` | `Visible` | All | `True` | Whether the attribute is visible in the ANB UI. |
| `is_user` | `Optional[bool]` | `IsUser` | All | `True` | Whether the attribute was defined by the user (vs. system). Always emitted in XML, defaults to `True` when not set. Attribute classes with `is_user=False` cannot appear in palettes. |
| `user_can_add` | `Optional[bool]` | `UserCanAdd` | All | `True` | Whether users can add this attribute to items in the ANB UI. Always emitted in XML, defaults to `True` when not set. Attribute classes with `user_can_add=False` cannot appear in palettes. |
| `user_can_remove` | `Optional[bool]` | `UserCanRemove` | All | `True` | Whether users can remove this attribute from items in the ANB UI. Always emitted in XML, defaults to `True` when not set. |
| `icon_file` | `Optional[str]` | `IconFile` | All | `None` | ANB icon key for the attribute symbol (e.g. `'phone'`). Passed directly to the XML -- user must supply the canonical ANB key. First registration wins. |
| `semantic_type` | `Optional[str]` | `SemanticTypeGuid` | All | `None` | NCName from i2 Semantic Type Library. Property name resolved from semantic definitions (with explicit `guid`) or custom property definitions. Must be unique across all attribute classes in the chart. Only emitted when set. |
| `merge_behaviour` | `Optional[MergeBehaviour]` | `MergeBehaviour` | All | omitted | Merge behavior when two items with the same attribute are merged. Omitted by default -- ANB uses its own built-in default. Only set to override. See Merge behaviour values below. |
| `paste_behaviour` | `Optional[MergeBehaviour]` | `PasteBehaviour` | All | omitted | Paste behavior when an attribute value is pasted onto an item. Omitted by default. See Paste behaviour values below. |
| `font` | `Font` | `<Font>` child | All | `Font()` | Font styling for the attribute display. Same shared `Font` dataclass used by chart/legend/entity fonts. The `<Font>` element is only emitted when at least one field is explicitly set. i2 defaults: Tahoma 8pt. |

> **`datetime` ACs cannot have `visible=True`.** ANB v9 does not render
> datetime values on the canvas; the chrome would render with no value.
> Validation rejects `type=datetime` + `visible=True` with
> `datetime_ac_forbids_visible`. Use
> [`extra_cfg.display_attribute`](#display-synthesizers) with a
> `"{d:%Y-%m-%d}"`-style template to synthesise a text sibling that renders
> the formatted date.

---

## Display synthesizers {#display-synthesizers}

Two chart-level synthesizers under `extra_cfg` turn raw attribute values into
analyst-friendly presentation, declaratively:

- **`extra_cfg.display_attribute`** -- render one or more source attributes
  through a template into a synthesized **text-sibling `AttributeClass`**.
- **`extra_cfg.display_label`** -- render straight into the entity/link
  **label**.

Both are keyed lists: each entry carries an explicit **`key`** (its identity
for config layering / `lock` / `delete`) and optional **`kind`** / **`type`**
scoping. They sit in the same family as `geo_map` and `styling`.

### Template syntax

`template` is the body of a Python f-string format spec (the `f` prefix is
Python syntax, not part of the template). It is evaluated with
`str.format_map` -- **no code execution**, only `{alias}` and
`{alias:format_spec}` substitutions such as `{x:,.2f}`, `{x:>10}`,
`{d:%d/%m/%Y}`.

Each `DisplaySource` names a source `attribute` and an `alias` used in the
template. `alias` is **required** when the attribute name isn't a valid Python
identifier (spaces, accents, etc.), and otherwise optional (the attribute name
is reused). Per-source `missing` policy is `'skip'` (default -- drop the whole
rendered output for that item), `'substitute'` (use `placeholder`), or
`'error'` (a `validate()` error per missing item).

Numeric format-spec output honours top-level `decimal_separator` /
`thousand_separator` (e.g. BR-style `100.000,50`); literal separators in the
static template text are untouched. Source ACs declared `type=datetime` are
auto-parsed back to a `datetime`, so `{d:%Y-%m-%d}` works directly.

### `display_attribute`

Synthesizes a text AC named by `attribute_name` (**required**) and appends the
rendered value to each matching item. Source ACs **may be visible** -- the raw
value then renders alongside the synthesized sibling (a deliberate
double-render, e.g. composing already-shown numeric ACs into one string). Set
`visible=False` on a source to suppress its own rendering. (A `datetime` source
must still be `visible=False` -- see the workaround below.) Sibling styling
comes from the optional inner `attribute_class` template (its `.name` / `.type`
must be `None` -- the sibling is auto-named and auto-typed text).

```python
chart.add_attribute_class(name="tx_count", type="number", visible=False)
chart.add_attribute_class(name="total", type="number", visible=False)
chart.add_display_attribute(
    key="activity",
    attribute_name="Activity",
    template="{q}x  R$ {amt:,.2f}",
    decimal_separator=",", thousand_separator=".",
    sources=[
        {"attribute": "tx_count", "alias": "q"},
        {"attribute": "total", "alias": "amt"},
    ],
)
```

**Datetime canvas-render workaround.** Because a `datetime` AC can't be
`visible=True`, render the date as a text sibling -- a single source for one
date, or two sources for a range:

```python
chart.add_attribute_class(name="start_dt", type="datetime", visible=False)
chart.add_attribute_class(name="end_dt", type="datetime", visible=False)
chart.add_display_attribute(
    key="period",
    attribute_name="Investigation Period",
    template="{s:%Y-%m-%d} - {e:%Y-%m-%d}",
    sources=[
        {"attribute": "start_dt", "alias": "s"},
        {"attribute": "end_dt", "alias": "e",
         "missing": "substitute", "placeholder": "ongoing"},
    ],
)
```

### `display_label`

Renders into `item.label`. By default a manually-set label is preserved
(explicit wins over calculated); set `override_existing=True` to replace it. An
entity whose label defaults to its id, or a link with no label, counts as
"unset" and is filled. No `visible=False` constraint on source ACs (nothing is
synthesized).

```python
chart.add_display_label(
    key="person_lbl", kind="entity", type="Person",
    template="Person ({age})",
    sources=[{"attribute": "age"}],
)
```

### `kind` / `type` scoping

`kind` (`'entity'` | `'link'` | `'both'`, default `'both'`) and optional `type`
(a registered entity/link type name) select which items an entry paints. For a
given slot (the label, or a given `attribute_name`) a **`type`-scoped entry
beats an untyped one** (specificity). Two entries at the same specificity tier
that could paint the same slot are a `display_overlap_conflict` validation
error -- scope them to disjoint types or merge them.

> **Scope policy (important).** `kind`/`type` filter by *structural metadata*
> only -- a finite, config-time-known set. Conditioning on attribute *values*
> (ranges, regex, comparisons, compound predicates) is **out of scope**:
> precompute a synthetic attribute or entity/link type upstream and scope on
> that. This keeps the synthesizers pure functions, not a rules engine.

### `DisplayAttribute` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | -- (required) | Identity for config layering / lock / delete. |
| `attribute_name` | `str` | -- (required) | Name of the synthesized text-sibling AC. |
| `kind` | `str` | `'both'` | `'entity'` / `'link'` / `'both'`. |
| `type` | `Optional[str]` | `None` | Entity/link type-name filter. |
| `template` | `str` | -- (required) | f-string-style format body. |
| `decimal_separator` | `str` | `'.'` | Numeric output only. |
| `thousand_separator` | `str` | `','` | Numeric output only. |
| `sources` | `List[DisplaySource]` | `[]` | At least one required. |
| `attribute_class` | `Optional[AttributeClass]` | `None` | Sibling styling (inner `.name`/`.type` must be `None`). |

### `DisplayLabel` fields

Same as `DisplayAttribute` minus `attribute_name` and `attribute_class`, plus
`override_existing: Optional[bool]` (default `False`).

### `DisplaySource` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `attribute` | `str` | -- (required) | Source AC name. |
| `alias` | `Optional[str]` | `None` | Template key; required for non-identifier attribute names. |
| `missing` | `Optional[str]` | `'skip'` | `'skip'` / `'substitute'` / `'error'`. |
| `placeholder` | `Optional[str]` | `''` | Used by `'substitute'`. |

### Validation rules

| Error type | Condition |
|---|---|
| `display_invalid` | Missing `key` / `template`; empty `sources`; missing `attribute_name` (attribute family); undeclared source AC; non-identifier attribute name without `alias`; duplicate alias; inner `attribute_class.name`/`.type` set; template syntax error; `missing='error'` triggered for an item. (A visible source AC is **not** an error — visible `datetime` sources are caught separately by `datetime_ac_forbids_visible`.) |
| `display_name_collision` | Synthesized `attribute_name` collides with an explicit AC. |
| `display_overlap_conflict` | Two same-specificity entries could paint the same `(kind, type)` slot. |

### Migrating from `date_attribute_displays`

`extra_cfg.date_attribute_displays` (removed in 1.12.0) is fully covered by
`display_attribute` -- see the date examples above and the CHANGELOG migration
table. The `missing: truncate` policy has no equivalent; use `substitute` with
a placeholder.

---

## Merge behaviour values

`merge_behaviour` controls what happens when two chart items with the same attribute are merged. Use string literals or the `MergeBehaviour` enum.

Emitting an invalid value for the attribute type (e.g. `'add_space'` on a Number class) is caught at validation time as `invalid_merge_behaviour` / `invalid_paste_behaviour`, so `to_anx()` raises `ANXValidationError` before writing the file. (Earlier versions surfaced this only at ANB import time as `LNAttributeClass::SetMergeBehaviour: Invalid merge behaviour for classes of this type`.)

| String literal | `MergeBehaviour` enum | Valid for Text | Valid for Number | Valid for DateTime | Valid for Flag | Description |
|---|---|:---:|:---:|:---:|:---:|---|
| `'add'` | `MergeBehaviour.ADD` | Y | Y | | | Concatenate (Text) or sum (Number). |
| `'add_space'` | `MergeBehaviour.ADD_WITH_SPACE` | Y | | | | Concatenate with a space separator. |
| `'add_line_break'` | `MergeBehaviour.ADD_WITH_LINE_BREAK` | Y | | | | Concatenate with a line break separator. |
| `'max'` | `MergeBehaviour.MAX` | | Y | Y | | Keep the higher value (Number) or later timestamp (DateTime). |
| `'min'` | `MergeBehaviour.MIN` | | Y | Y | | Keep the lower value (Number) or earlier timestamp (DateTime). |
| `'or'` | `MergeBehaviour.OR` | | | | Y | Boolean OR. |
| `'and'` | `MergeBehaviour.AND` | | | | Y | Boolean AND. |
| `'xor'` | `MergeBehaviour.XOR` | | | | Y | Boolean XOR. |

`'assign'` and `'noop'` are NOT valid for `merge_behaviour`. They are paste-only values.

---

## Paste behaviour values

`paste_behaviour` controls what happens when an attribute value is pasted onto an item. Accepts all merge values (for the appropriate types) plus the following additional values.

| String literal | `MergeBehaviour` enum | Valid for Text | Valid for Number | Valid for DateTime | Valid for Flag | Description |
|---|---|:---:|:---:|:---:|:---:|---|
| `'assign'` | `MergeBehaviour.ASSIGN` | Y | Y | Y | Y | Replace with the pasted value ("pasted value"). |
| `'noop'` | `MergeBehaviour.NO_OP` | Y | Y | Y | Y | Keep existing value, ignore pasted ("existing value"). |
| `'add'` | `MergeBehaviour.ADD` | Y | Y | | | Concatenate (Text) or sum (Number). |
| `'add_space'` | `MergeBehaviour.ADD_WITH_SPACE` | Y | | | | Concatenate with a space separator. |
| `'add_line_break'` | `MergeBehaviour.ADD_WITH_LINE_BREAK` | Y | | | | Concatenate with a line break separator. |
| `'max'` | `MergeBehaviour.MAX` | | Y | Y | | Keep the higher/later value. |
| `'min'` | `MergeBehaviour.MIN` | | Y | Y | | Keep the lower/earlier value. |
| `'subtract'` | `MergeBehaviour.SUBTRACT` | | Y | | | Existing minus pasted. |
| `'subtract_swap'` | `MergeBehaviour.SUBTRACT_SWAP` | | Y | | | Pasted minus existing. |
| `'or'` | `MergeBehaviour.OR` | | | | Y | Boolean OR. |
| `'and'` | `MergeBehaviour.AND` | | | | Y | Boolean AND. |
| `'xor'` | `MergeBehaviour.XOR` | | | | Y | Boolean XOR. |

Full ANB XML names (e.g. `AttMergeAssign`, `AttMergeAdd`) are also accepted as passthrough values.

---

## `MergeBehaviour` enum reference

All 12 enum members. The enum is used for both `merge_behaviour` and `paste_behaviour` fields.

| Enum member | String value | ANB XML value |
|---|---|---|
| `MergeBehaviour.ASSIGN` | `'assign'` | `AttMergeAssign` |
| `MergeBehaviour.NO_OP` | `'noop'` | `AttMergeNoOp` |
| `MergeBehaviour.ADD` | `'add'` | `AttMergeAdd` |
| `MergeBehaviour.ADD_WITH_SPACE` | `'add_space'` | `AttMergeAddWithSpace` |
| `MergeBehaviour.ADD_WITH_LINE_BREAK` | `'add_line_break'` | `AttMergeAddWithLineBreak` |
| `MergeBehaviour.MAX` | `'max'` | `AttMergeMax` |
| `MergeBehaviour.MIN` | `'min'` | `AttMergeMin` |
| `MergeBehaviour.SUBTRACT` | `'subtract'` | `AttMergeSubtract` |
| `MergeBehaviour.SUBTRACT_SWAP` | `'subtract_swap'` | `AttMergeSubtractSwap` |
| `MergeBehaviour.OR` | `'or'` | `AttMergeOR` |
| `MergeBehaviour.AND` | `'and'` | `AttMergeAND` |
| `MergeBehaviour.XOR` | `'xor'` | `AttMergeXOR` |

---

## Font on `AttributeClass`

The `font` field on `AttributeClass` accepts the same shared `Font` dataclass used by chart-level font, legend font, and entity/link label fonts. See [Settings](settings.md) for the full `Font` field table.

The `<Font>` child element inside `<AttributeClass>` is only emitted when at least one font field is explicitly set. When omitted, anxwritter's emission helper falls back to Tahoma 8pt for attribute class fonts (vs. Tahoma 10pt for chart-level font).

```python
chart.add_attribute_class(
    name='Important Note', type='text',
    font=Font(bold=True, color='Red', size=10),
)
```

---

## ANB built-in / reserved attribute names

> **Warning.** ANB 9 pre-registers some `AttributeClass` names internally. Declaring one
> of these names again in your config causes ANB to reject the entire import with this
> entry in the import log:
>
> ```
> CreateAttributeClass: failed to create attribute class
> ```
>
> Real-world example: `Peso` (Portuguese for "weight") is one such name in localized ANB
> builds and is rejected on re-declaration. Treat any error matching the line above as
> a reserved-name collision regardless of locale.
>
> anxwritter cannot detect the collision up front — the error only surfaces when ANB
> opens the file.
>
> **If you see the error above:**
>
> 1. Bisect your `attribute_classes:` section — comment out half, rebuild, open in ANB.
> 2. Repeat on whichever half still fails until you isolate the offending name.
> 3. Delete that declaration from your config. ANB supplies the class automatically with
>    its built-in defaults — you don't need (and aren't allowed) to redeclare it.
>
> When in doubt about whether a name is reserved, open a blank chart in ANB and check
> the **Attribute Class collection** dialog: anything already listed there is reserved
> for your ANB version + locale.

---

## Behaviour summary by type

This table summarizes which `merge_behaviour` and `paste_behaviour` values are valid for each attribute type.

| Attribute type | Valid `merge_behaviour` | Valid `paste_behaviour` |
|---|---|---|
| Text (`AttText`) | `add`, `add_space`, `add_line_break` | `assign`, `noop`, `add`, `add_space`, `add_line_break` |
| Number (`AttNumber`) | `add`, `max`, `min` | `assign`, `noop`, `add`, `max`, `min`, `subtract`, `subtract_swap` |
| DateTime (`AttTime`) | `max`, `min` | `assign`, `noop`, `max`, `min` |
| Flag (`AttFlag`) | `or`, `and`, `xor` | `assign`, `noop`, `or`, `and`, `xor` |

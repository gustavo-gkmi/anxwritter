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
> [`extra_cfg.date_attribute_displays`](#date-attribute-displays) to
> synthesise a text sibling that renders the formatted date.

---

## Date attribute displays {#date-attribute-displays}

ANB v9 does not render datetime attribute values on the canvas after `.anx`
import. The values load correctly -- they appear in the properties panel and
work for time-wheel, sort, and filter -- but on the canvas, only the
surrounding chrome (symbol, prefix, suffix, class name) appears next to each
entity/link. The date itself is blank.

`extra_cfg.date_attribute_displays` is an opt-in chart-level synthesizer that
declares one or more text-sibling AttributeClasses derived from datetime ACs.
The synthesizer also supports **date ranges** -- two datetime ACs combined
into one canvas-rendered string -- which the single-AC workaround on its own
couldn't express.

### What it does

For each `DateAttributeDisplay` entry, anxwritter:

1. Computes the sibling AC's name (the entry's `name` field if set, else
   `f"{start}{suffix}"` with suffix defaulting to `' (display)'` in
   single-date mode).
2. Registers the sibling as a text AttributeClass (`visible=True`,
   `show_value=True` by default; override via `attribute_class=...`).
3. Walks every entity/link in the chart and appends a sibling attribute
   whose value is the parent's datetime(s) formatted via `strftime`
   (default `'%Y-%m-%d'`).

The original datetime ACs are still emitted and ANB still loads them. They
**must have `visible=False`** -- validation requires it explicitly. ANB never
renders the datetime value on the canvas, so leaving the parent visible
would render the chrome with no value. The synthesised sibling carries the
canvas-rendered text.

### Single-date mode

```python
from anxwritter import ANXChart, AttributeClass, Font

chart = ANXChart()
chart.add_attribute_class(name='event_date', type='datetime', visible=False)
chart.add_date_attribute_display(
    start='event_date',
    format='%d/%m/%Y',
    attribute_class=AttributeClass(prefix='Event: ', font=Font(italic=True)),
)
chart.add_icon(id='A', type='Person',
               attributes={'event_date': datetime(2024, 1, 15)})
# Canvas shows: Event: 15/01/2024
```

The synthesised AC's name auto-derives as `event_date (display)`. Set
`name='Event'` on the display to override.

### Range mode

```python
chart = ANXChart()
chart.add_attribute_class(name='investigation_start', type='datetime', visible=False)
chart.add_attribute_class(name='investigation_end',   type='datetime', visible=False)
chart.add_date_attribute_display(
    start='investigation_start',
    end='investigation_end',
    name='Period',                 # required in range mode
    format='%Y-%m-%d',
    separator=' – ',
)
chart.add_icon(id='Case A', type='Event',
               attributes={'investigation_start': datetime(2023, 6, 1),
                           'investigation_end': datetime(2023, 12, 31)})
# Canvas shows: 2023-06-01 – 2023-12-31
```

`name` is required in range mode -- there's no single source AC to
auto-derive from.

### Missing bounds

By default, items missing one bound emit no sibling row for that item. Four
policies are available via `missing=`:

| Policy | End missing (start present) | Start missing (end present) | Both missing |
|---|---|---|---|
| `'skip'` (default) | no sibling row | no sibling row | no sibling row |
| `'substitute'` | `"2024-01-15 – {end_placeholder}"` | `"{start_placeholder} – 2024-12-31"` | no sibling row |
| `'truncate'` | `"2024-01-15"` (no separator) | `"2024-12-31"` | no sibling row |
| `'error'` | `validate()` row at `entities[i].attributes.<end>` | symmetric | no error |

Per-bound placeholders default to `''`; set them via `start_placeholder=`
and `end_placeholder=`. Common values: `'?'`, `'…'`, `'N/A'`, `'ongoing'`.

```python
chart.add_date_attribute_display(
    start='investigation_start', end='investigation_end', name='Period',
    missing='substitute', end_placeholder='ongoing',
)
# Open investigation (no end_date): Canvas shows "2024-01-10 – ongoing"
```

### YAML form

```yaml
attribute_classes:
  - name: investigation_start
    type: datetime
    visible: false
  - name: investigation_end
    type: datetime
    visible: false

settings:
  extra_cfg:
    date_attribute_displays:
      - start: investigation_start
        end: investigation_end
        name: Period
        format: '%Y-%m-%d'
        separator: ' – '
        missing: substitute
        end_placeholder: ongoing
```

### `DateAttributeDisplay` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `start` | `Optional[str]` | -- (required) | Name of the source datetime AC. |
| `end` | `Optional[str]` | `None` | Range mode: name of the end-date AC. Must differ from `start`. |
| `name` | `Optional[str]` | auto | Sibling AC name. Required in range mode; auto-derived as `f"{start}{suffix}"` in single-date mode. |
| `suffix` | `Optional[str]` | `' (display)'` | Used only when `name` is None (single-date mode). |
| `format` | `Optional[str]` | `'%Y-%m-%d'` | `strftime` format applied to both bounds. |
| `separator` | `Optional[str]` | `' - '` | Range mode only. |
| `missing` | `Optional[str]` | `'skip'` | One of `skip` / `substitute` / `truncate` / `error`. |
| `start_placeholder` | `Optional[str]` | `''` | `substitute` mode: text for missing start bound. |
| `end_placeholder` | `Optional[str]` | `''` | `substitute` mode: text for missing end bound. |
| `attribute_class` | `Optional[AttributeClass]` | `None` | Styling template for the sibling AC. Inner `.name` and `.type` must be `None` -- the sibling is auto-named and auto-typed as text. No inheritance from the source ACs. |

### Validation rules

`chart.validate()` emits these errors before `to_anx()` will write the file:

| Error type | Condition |
|---|---|
| `datetime_ac_forbids_visible` | Any `type=datetime` AC has `visible=True`. ANB v9 will render the chrome with no value. |
| `date_display_invalid` | `start` missing or references undeclared / non-datetime AC; `start` AC has `visible!=False`; `end` references undeclared / non-datetime AC; `end` AC has `visible!=False`; `end == start`; range mode without `name`; `format` is not a valid strftime; `missing` not in valid set; inner `attribute_class.name` / `.type` set; or `missing='error'` and an item has only one of two bounds. |
| `date_display_name_collision` | The synthesised sibling name collides with an explicit AC, or two displays produce the same sibling name. |

### Forward-compat note

If a future ANB release renders datetime values on the canvas without this
workaround, `date_attribute_displays` entries become redundant -- the text
siblings still emit alongside the now-rendering datetime parents (after
removing `visible=False`). A future anxwritter release may add a deprecation
warning and eventually remove the transform. **Existing configs will not
break** -- the synthesizer will degrade gracefully to "redundant but
harmless."

---

## Display templates {#display-templates}

`extra_cfg.display_templates` is an opt-in chart-level synthesizer that
takes one or more source attribute values, renders them through a Python
`str.format_map`-style template, and emits the result either as a
**synthesized text-sibling AttributeClass** (`target='attribute'`, default)
or **directly into the entity/link label** (`target='label'`).

Lives under `settings.extra_cfg.display_templates` -- same chart-level
synthesizer family as [`date_attribute_displays`](#date-attribute-displays),
`geo_map`, and `styling`. Coexists with `date_attribute_displays`; neither
deprecates the other.

### What it does

ANB renders each AttributeClass on its own row in the attribute stack. A
link with `transaction_count=5` plus `total_value=12345.67` shows as **two
lines** stacked vertically. `display_templates` turns that into a single
formatted string -- "5x R$ 12,345.67" -- and puts it where you want it:
either as a new AC on its own row (replacing the source rows by setting
those `visible=False`), or directly on the link label.

The template is plain Python `str.format_map` syntax -- the same field
spec mini-language used by f-strings, without the `f` prefix (which is
Python source syntax, not part of the template). Examples: `{qty}`,
`{amount:,.2f}`, `{when:%d/%m/%Y}`, `{x:>10}`.

### target='attribute' (default)

Synthesizes a new text AC, named via `attribute_name` (default
`'display'`), with the rendered string as its per-item value. Source ACs
**must** declare `visible=False` -- the synthesized sibling renders in
place of the source rows in the attribute stack.

```python
from anxwritter import ANXChart, AttributeClass, DisplayTemplate, DisplaySource

chart = ANXChart()
chart.add_attribute_class(AttributeClass(
    name='transaction_count', type='number', visible=False,
))
chart.add_attribute_class(AttributeClass(
    name='total_value', type='number', visible=False,
))
chart.add_display_template(DisplayTemplate(
    target='attribute',
    attribute_name='Activity',
    template='{qty}x R$ {amount:,.2f}',
    sources=[
        DisplaySource(attribute='transaction_count', alias='qty'),
        DisplaySource(attribute='total_value', alias='amount'),
    ],
))
```

### target='label'

Writes the rendered string into the entity/link `label` field. By default
(`override_existing=False`), only items with an empty label are filled --
manually-annotated labels are preserved. Source ACs have no visibility
constraint in this mode; users can keep the structured data visible in the
attribute stack AND show the formatted summary on the label.

```python
chart.add_display_template(DisplayTemplate(
    target='label',
    template='{qty}x R$ {amount:,.2f}',
    sources=[
        DisplaySource(attribute='transaction_count', alias='qty'),
        DisplaySource(attribute='total_value', alias='amount'),
    ],
))
```

Set `override_existing=True` to stomp existing labels too. The default
(`False`) keeps the library-wide convention that explicit values always
win over calculated ones; the flag is for "I really want chart-wide
consistency" cases where the user is fine with the synthesizer taking
over.

### Source aliases

When a source attribute name isn't a valid Python identifier (contains
spaces, accents, etc), you must give it an `alias` for use in the
template:

```yaml
sources:
  - attribute: "quantia em real"   # spaces -- not a valid identifier
    alias: amount                   # use {amount} in template
template: "R$ {amount:,.2f}"
```

When the attribute name is identifier-safe, the alias is optional --
the attribute name is reused as the template key.

### Decimal / thousand separators

Python's standard `,.2f` format spec always renders US-style
(`100,000.50`). For Brazilian (`100.000,50`) and other separator
conventions, set `decimal_separator` and `thousand_separator` on the
entry:

```yaml
decimal_separator: ','
thousand_separator: '.'
template: "R$ {amount:,.2f}"
# 100000.50 → "R$ 100.000,50"
```

The swap is applied **only to formatted numeric values** -- literal
commas/periods in the static template text are untouched, so
`"qtd: {qty}, total"` keeps its literal comma after `{qty}`.

### Datetime sources

When a source AC declares `type: datetime`, the library parses the value
back into a `datetime.datetime` before binding into the format dict, so
strftime-style format specs work directly:

```yaml
attribute_classes:
  - name: when
    type: datetime
    visible: false

settings:
  extra_cfg:
    display_templates:
      - target: attribute
        attribute_name: When
        template: "em {when:%d/%m/%Y}"
        sources:
          - attribute: when
# datetime(2024, 3, 15) → "em 15/03/2024"
```

### Missing-value handling

Per-source `missing` policy controls behaviour when an item is missing
that source attribute. Default `'skip'`.

| Policy | Behaviour |
|---|---|
| `skip` (default) | Drop the item -- no sibling AC emitted / no label change. |
| `substitute` | Use the source's `placeholder` string in place of the missing value. |
| `error` | Surface a `display_template_invalid` validation error per missing item at `validate()` time. |

```yaml
sources:
  - attribute: tx
    missing: substitute
    placeholder: "0"
```

### YAML form

```yaml
attribute_classes:
  - name: transaction_count
    type: number
    visible: false
  - name: total_value
    type: number
    visible: false

settings:
  extra_cfg:
    display_templates:
      - target: attribute
        attribute_name: Activity
        template: "{qty}x R$ {amount:,.2f}"
        decimal_separator: ','
        thousand_separator: '.'
        sources:
          - attribute: transaction_count
            alias: qty
          - attribute: total_value
            alias: amount
```

### `DisplayTemplate` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `target` | `Optional[str]` | `'attribute'` | `'attribute'` or `'label'`. Picks the output slot. |
| `attribute_name` | `Optional[str]` | `'display'` | Synthesized AC name when `target='attribute'`. Ignored for `'label'`. |
| `override_existing` | `Optional[bool]` | `False` | `target='label'` only. Stomp existing labels when `True`. |
| `template` | `Optional[str]` | -- (required) | f-string-style format body. Use `{alias}` and `{alias:format_spec}` substitutions. |
| `decimal_separator` | `Optional[str]` | `'.'` | Applied to numeric format-spec output. Literal template text untouched. |
| `thousand_separator` | `Optional[str]` | `','` | Same. |
| `sources` | `List[DisplaySource]` | `[]` | At least one source required. |
| `attribute_class` | `Optional[AttributeClass]` | `None` | Styling template for the synthesized AC (`target='attribute'` only). Inner `.name` and `.type` must be `None`. |

### `DisplaySource` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `attribute` | `Optional[str]` | -- (required) | Source AttributeClass name. |
| `alias` | `Optional[str]` | `None` | Template key. Required when `attribute` isn't a valid Python identifier. |
| `missing` | `Optional[str]` | `None` | Per-source override of the default `'skip'`. One of `'skip'`, `'substitute'`, `'error'`. |
| `placeholder` | `Optional[str]` | `''` | Used when `missing='substitute'`. |

### Validation rules

| Error type | Condition |
|---|---|
| `display_template_invalid` | Missing/empty `template`; empty `sources`; undeclared source AC; source AC has `visible != False` when `target='attribute'`; invalid `target` or `missing` enum; alias collision within an entry; `alias` required (non-identifier attribute name) but omitted; `attribute_class.name` or `.type` set; template syntax error (unclosed brace, bad format spec); `missing='error'` triggered per item. |
| `display_template_name_collision` | Synthesized `attribute_name` collides with an explicit AC, with another `display_templates` entry's name, or with any `date_attribute_displays` sibling name. |

### Non-goals

`display_templates` is intentionally a pure function of declared source
attributes:

- **No compound conditions / regex / multi-attribute rules.** Precompute
  upstream as a synthetic attribute and reference it here.
- **No arithmetic expressions in templates** (`{a + b}`). Only
  `{alias:format_spec}` substitutions.
- **No per-source `prefix` / `suffix` / `format` / separator overrides.**
  All formatting lives in the template; per-source decoration is
  intentionally not supported to keep one source of truth for the
  rendered shape.
- **No filter by entity/link type.** Applies to every item that has the
  source ACs; use distinct AC names per type if you need scoping.

### Coexists with `date_attribute_displays`

The two synthesizers run independently. `date_attribute_displays` is the
convenience form for the common single-AC date / two-AC range case (no
template needed, just `start`/`end`/`format`/`separator`).
`display_templates` is the general form for everything else (multiple
sources, custom formatting, label target). Synthesized AC names share one
namespace -- collisions across the two families are caught at
`validate()` time.

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

# anxwritter -- Practical Guide for Analysts

This guide walks you through building i2 Analyst's Notebook charts with
anxwritter. It assumes you can write basic Python, YAML, or JSON and want
to produce `.anx` files that open in ANB 9+ via **File > Open**.

---

## 1. Building charts in Python

The fastest way to get started is with the convenience methods.

```python
from anxwritter import ANXChart

chart = ANXChart()

# Add two people
chart.add_icon(id='Alice', type='Person', color='Blue',
               attributes={'Phone': '555-0001'})
chart.add_icon(id='Bob', type='Person', color='Red')

# Connect them
chart.add_link(from_id='Alice', to_id='Bob', type='Call',
               arrow='->', date='2024-01-15',
               attributes={'duration': 120})

# Write the file
chart.to_anx('output/my_chart')   # creates output/my_chart.anx
```

### Convenience methods

Each entity type has its own `add_` method:

```python
chart.add_icon(id='A1', type='Person', color='Blue')
chart.add_box(id='HQ', type='Location', width=150, height=100)
chart.add_circle(id='E1', type='Event', diameter=80)
chart.add_theme_line(id='TL1', type='Timeline')
chart.add_event_frame(id='EF1', type='Operation')
chart.add_text_block(id='TB1', type='Note', label='Some text here')
chart.add_label(id='LBL1', type='Label', label='Caption')
chart.add_link(from_id='A1', to_id='HQ', type='Works At', arrow='->')
```

### The three-tier API

anxwritter offers three ways to add items, from simplest to most flexible:

```python
from anxwritter import Icon, Link

# Tier 1: Convenience methods (shown above) -- keyword args
chart.add_icon(id='Alice', type='Person')

# Tier 2: Generic dispatch -- pass any typed object
chart.add(Icon(id='Bob', type='Person'))
chart.add(Link(from_id='Alice', to_id='Bob', type='Call'))

# Tier 3: Bulk -- accepts any iterable (generators, database cursors, etc.)
people = [Icon(id=f'P{i}', type='Person') for i in range(100)]
chart.add_all(people)
```

### Output

```python
# Write to file -- returns the absolute path
path = chart.to_anx('output/my_chart')

# Get XML string without writing a file
xml_string = chart.to_xml()

# Validate without building (returns a list of error dicts, empty = valid)
errors = chart.validate()
```

---

## 2. Building charts from YAML

You can define your entire chart in YAML and convert it from the command line
or from Python.

> The rest of this guide focuses on the Python API. For a YAML/JSON-first
> walk-through (every section, every field, gotchas), see the
> [YAML / JSON Guide](yaml-json-guide.md).

### YAML template

```yaml
settings:
  extra_cfg:
    arrange: grid
    entity_auto_color: true

entities:
  icons:
    - id: Alice
      type: Person
      color: Blue
      attributes:
        Phone: "555-0001"
    - id: Bob
      type: Person
      color: Red

  boxes:
    - id: HQ
      type: Location
      label: Headquarters

links:
  - from_id: Alice
    to_id: Bob
    type: Call
    arrow: "->"
    date: "2024-01-15"
    attributes:
      duration: 120

  - from_id: Alice
    to_id: HQ
    type: Works At
    arrow: "->"
```

### JSON equivalent

The same structure works in JSON -- entity types go under `entities.icons`,
`entities.boxes`, etc., and links go in a `links` array. See the YAML above
for the field names.

### Loading from Python

```python
chart = ANXChart.from_yaml_file('data.yaml')   # or from_json_file('data.json')
chart.to_anx('output/my_chart')
```

### CLI usage

```bash
# YAML input
anxwritter data.yaml -o output/chart.anx

# JSON input
anxwritter data.json -o output/chart.anx

# Validate only (no file written)
anxwritter data.yaml --validate-only

# Use org config files (layered, applied in order)
anxwritter --config org.yaml data.yaml -o output/chart.anx
anxwritter --config config.yaml --config overrides.yaml data.yaml -o output/chart.anx

# Config-only (no entity/link data)
anxwritter --config org.yaml -o output/chart.anx
```

---

## 3. Entities

anxwritter supports all seven ANB entity representations. Use whichever
best matches the item you are charting.

| Type | Best for | Example |
|------|----------|---------|
| **Icon** | People, vehicles, phones, objects | A suspect, a car, a phone number |
| **Box** | Locations, organisations, accounts | A bank account, a building, a company |
| **Circle** | Events, meetings, incidents | A robbery, a meeting, a transaction |
| **ThemeLine** | Timeline bands spanning the chart | An investigation timeline, a phone line |
| **EventFrame** | Time-bounded regions on a timeline | An operation window, a surveillance period |
| **TextBlock** | Free-standing text with a border | An analyst note, a paragraph of context |
| **Label** | Transparent text overlay (no border) | A chart title, a section heading |

### Common fields (all entity types)

Every entity type shares these fields:

```python
chart.add_icon(
    id='Alice',              # required -- unique identity
    type='Person',           # required -- entity type name
    label='Alice Smith',     # display label (defaults to id)
    date='2024-01-15',       # date in yyyy-MM-dd format
    time='14:30:00',         # time in HH:mm:ss format
    description='Main suspect in Op Sunshine',
    attributes={'Phone': '555-0001', 'Age': 39},
    x=100, y=200,            # manual canvas position (skips auto-layout)
)
```

Other shared fields include `strength` (line style name), `grade_one`/`grade_two`/
`grade_three` (evidence grading indices), `source_ref`, `source_type`, `timezone`,
and `show` (sub-item visibility).

The `ordered` field enables ANB's "Controladores" mode (ordered with date and time)
when set to `True`. The `show` field is a `Show(...)` dataclass that controls which
sub-items are visible:

```python
from anxwritter import Show

chart.add_icon(
    id='Alice', type='Person',
    date='2024-06-01', time='09:00:00',
    show=Show(description=True, date=True, source_ref=True),
)
```

---

## 4. Links

Links connect two entities by their `id` values.

```python
chart.add_link(
    from_id='Alice',         # must match an entity id
    to_id='Bob',             # must match an entity id
    type='Call',             # link type name
    arrow='->',              # arrow direction
    label='Mobile call',     # display label
    date='2024-01-15',
    time='14:30:00',
    description='Intercepted call, 2 minutes',
    attributes={'Duration': 120, 'Call Type': 'Mobile'},
)
```

### Arrow shorthand

| Value | Meaning |
|-------|---------|
| `'->'` or `'head'` | Arrow pointing from source to destination |
| `'<-'` or `'tail'` | Arrow pointing from destination to source |
| `'<->'` or `'both'` | Arrows on both ends |
| *(omit)* | No arrow (plain line) |

### Parallel link spacing

When multiple links exist between the same pair of entities, anxwritter
automatically spaces them as arcs so they do not overlap. The default offset
is 20 pixels. You can adjust it globally:

```python
chart = ANXChart(settings={'extra_cfg': {'link_arc_offset': 30}})
```

Or override per link:

```python
chart.add_link(from_id='A', to_id='B', type='Call', offset=40)
```

### Multiplicity

By default, each link renders as a separate arc (`'multiple'`). You can
collapse all links between the same pair into a single line with a card stack:

```python
chart.add_link(from_id='A', to_id='B', type='Call', multiplicity='single')
```

### Link ID for card attachment

If you need to attach loose cards to a link later, give it a `link_id`:

```python
chart.add_link(from_id='A', to_id='B', type='Call', link_id='call_001')
chart.add_card(link_id='call_001', summary='Intercept report')
```

---

## 5. Attributes

Attributes are key-value pairs attached to entities or links. The data type
is inferred automatically from the Python value:

| Python type | ANB type | Example |
|-------------|----------|---------|
| `str` | Text | `'555-0001'` |
| `int` or `float` | Number | `120`, `3200.50` |
| `bool` | Flag | `True`, `False` |
| `datetime` | DateTime | `datetime(2024, 1, 15, 14, 30)` |

```python
from datetime import datetime

chart.add_icon(
    id='Alice', type='Person',
    attributes={
        'Phone': '555-0001',       # Text
        'Age': 39,                  # Number
        'Active': True,             # Flag
        'Joined': datetime(2024, 1, 15),  # DateTime
    },
)
```

**Important**: if the same attribute name is used on different items with
different Python types (e.g. `'Balance'` as a `float` on one entity and a
`str` on another), validation reports a `type_conflict` error and
`to_anx()`/`to_xml()` raise `ANXValidationError`.

### Configuring attribute display

Use `add_attribute_class()` to control how attributes are formatted in ANB.
Every explicit declaration must include a `type` (one of `'text'`, `'number'`,
`'flag'`, `'datetime'`):

```python
chart.add_attribute_class(name='Balance', type='number', prefix='R$ ', decimal_places=2)
chart.add_attribute_class(name='Phone',   type='text',   prefix='Tel: ')
chart.add_attribute_class(name='Active',  type='flag',   show_if_set=True)
```

Common options:

| Option | Effect |
|--------|--------|
| `type` | **Required.** Attribute data type (`'text'`/`'number'`/`'flag'`/`'datetime'`) |
| `prefix` | Text before the value (e.g. `'R$ '`) |
| `suffix` | Text after the value (e.g. `' kg'`) |
| `decimal_places` | Number of decimal digits (Number attributes) |
| `show_if_set` | Show the attribute name when a Flag is `True` |
| `show_class_name` | Show the attribute class name alongside the value |
| `visible` | Whether the attribute is visible on the chart |
| `icon_file` | ANB icon key for the attribute symbol |

### Merge and paste behaviour

When entities are merged in ANB, you can control how attribute values combine:

```python
from anxwritter import MergeBehaviour

chart.add_attribute_class(
    name='Notes', type='text',
    merge_behaviour=MergeBehaviour.ADD_WITH_LINE_BREAK,
    paste_behaviour=MergeBehaviour.ADD_WITH_LINE_BREAK,
)
chart.add_attribute_class(
    name='Balance', type='number',
    merge_behaviour=MergeBehaviour.ADD,   # sum both values
    decimal_places=2,
)
```

### ⚠ ANB built-in attribute names

Some `AttributeClass` names are pre-registered by ANB 9 itself. If your config declares one
of those names again, ANB refuses to open the chart and writes a CreateAttributeClass
failure entry to the import log.

anxwritter has no way to know which names are reserved (ANB does not publish the list), so
the error only surfaces when you open the `.anx`. If you hit it:

1. Comment out half of your `attribute_classes:` section and rebuild.
2. Repeat until you isolate the offending name.
3. Delete that entry from your config — **don't redeclare built-in names**. ANB provides
   them automatically with its own display defaults.

See [reference/attributes.md](../reference/attributes.md#anb-built-in-reserved-attribute-names) for the reference
note.

---

## 6. Cards and evidence

Cards are the evidence records attached to entities and links in ANB.

### Inline cards on entities

```python
from anxwritter import Card

chart.add_icon(
    id='Alice', type='Person',
    cards=[
        Card(
            summary='Main suspect',
            date='2024-01-15',
            time='14:30:00',
            description='Identified from CCTV footage at the scene.',
            source_ref='REP-001',
            source_type='Witness',
            grade_one=0,     # index into chart.grades_one
            grade_two=1,     # index into chart.grades_two
        ),
        Card(summary='Second sighting', date='2024-02-01'),
    ],
)
```

### Inline cards on links

```python
chart.add_link(
    from_id='Alice', to_id='Bob', type='Call',
    link_id='call_001',
    cards=[
        Card(summary='Intercepted call', date='2024-01-17',
             source_ref='RPT-001'),
        Card(summary='Follow-up analysis', date='2024-02-01'),
    ],
)
```

### Loose cards (attached by ID)

Add cards separately and route them to an entity or link by ID:

```python
chart.add_card(entity_id='Alice', summary='New intel', date='2024-03-01')
chart.add_card(link_id='call_001', summary='Transcript available')
```

### Card fields

| Field | Description |
|-------|-------------|
| `summary` | Short text shown in ANB's card panel |
| `date` | Date string `yyyy-MM-dd` |
| `time` | Time string `HH:mm:ss` |
| `description` | Longer card body text |
| `source_ref` | Source document reference |
| `source_type` | Source type label (should match `chart.source_types`) |
| `grade_one` | Source reliability index (0-based) |
| `grade_two` | Information reliability index (0-based) |
| `grade_three` | Third grading dimension index (0-based) |
| `timezone` | `TimeZone` dataclass with `id` (int 1-122) and `name` (str) |

### Grade collections

Grade indices reference the chart-level grade label lists. Define them as
`GradeCollection` objects:

```python
from anxwritter import GradeCollection

chart.grades_one = GradeCollection(items=[
    'Always reliable', 'Usually reliable', 'Fairly reliable',
    'Not usually reliable', 'Unreliable', 'Cannot be judged',
])
chart.grades_two = GradeCollection(items=[
    'Confirmed', 'Probably true', 'Possibly true',
    'Doubtful', 'Improbable', 'Cannot be judged',
])
chart.grades_three = GradeCollection(items=['High', 'Medium', 'Low'])
```

Then use indices on entities, links, and cards:

```python
chart.add_icon(id='Alice', type='Person', grade_one=0, grade_two=1)
# grade_one=0 --> 'Always reliable', grade_two=1 --> 'Probably true'
```

### Source types

Define the source type dropdown entries:

```python
chart.source_types = ['Discovery', 'Informant', 'Intelligence',
                      'Officer', 'Record', 'Victim', 'Witness']
```

Reference them on entities, links, and cards via the `source_type` field.

---

## 7. Visual styling

### Colors

anxwritter accepts colors in several forms — pick whichever is most natural:

```python
from anxwritter import Color

chart.add_icon(id='A', type='Person', color=Color.BLUE)        # Color enum (recommended)
chart.add_icon(id='B', type='Person', color='Blue')            # Title Case name
chart.add_icon(id='C', type='Person', color='blue')            # lowercase (case-insensitive)
chart.add_icon(id='D', type='Person', color='light_orange')    # snake_case
chart.add_icon(id='E', type='Person', color='#FF6600')         # hex RGB
chart.add_link(from_id='A', to_id='B', line_color=16711680)    # COLORREF int
```

**The `Color` enum** has 40 members — one per ANB shading color. It gives you IDE
autocomplete and type safety:

```python
from anxwritter import Color

Color.BLUE           # 'blue'  -> resolves to NAMED_COLORS['Blue']
Color.LIGHT_ORANGE   # 'light_orange'
Color.BLUE_GREY      # 'blue_grey'
```

**Named colors** (40 ANB color names — **case-insensitive**, hyphens / underscores /
spaces all interchangeable):

> Black, Brown, Olive Green, Dark Green, Dark Teal, Dark Blue, Indigo,
> Dark Grey, Dark Red, Orange, Dark Yellow, Green, Teal, Blue, Blue-Grey,
> Grey, Red, Light Orange, Lime, Sea Green, Aqua, Light Blue, Violet,
> Light Grey, Pink, Gold, Yellow, Bright Green, Turquoise, Sky Blue, Plum,
> Silver, Rose, Tan, Light Yellow, Light Green, Light Turquoise, Pale Blue,
> Lavender, White

`'Blue'`, `'blue'`, `'BLUE'`, and `Color.BLUE` are all equivalent. Same for
`'Light Orange'`, `'light orange'`, `'light_orange'`, `'light-orange'`, and
`Color.LIGHT_ORANGE`.

**Hex colors**: standard `#RRGGBB` strings like `'#FF0000'` for red.

**COLORREF integers**: Windows BGR format (`R + G*256 + B*65536`). You can
compute them with the helper:

```python
from anxwritter import rgb_to_colorref
red = rgb_to_colorref(255, 0, 0)   # 255
```

### Auto-color

Let anxwritter assign evenly-spaced colours automatically:

```python
chart = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
```

Entities with an explicit `color` keep it; only entities without a color get
auto-assigned. To also colour link lines to match their destination entity:

```python
chart = ANXChart(settings={
    'extra_cfg': {
        'entity_auto_color': True,
        'link_match_entity_color': True,
    },
})
```

### Label font styling

Customise the font on any entity or link label:

```python
from anxwritter import Font

chart.add_icon(
    id='Alice', type='Person',
    label_font=Font(color='Red', bold=True, size=12),
)
chart.add_link(
    from_id='Alice', to_id='Bob', type='Call',
    label_font=Font(italic=True, color='Dark Blue'),
)
```

Font fields: `name`, `size`, `color`, `bg_color`, `bold`, `italic`,
`strikeout`, `underline`.

### Strengths and line styles

Strengths define named line dash patterns. The chart comes with `Default`
(solid). Add more as needed:

```python
from anxwritter import DotStyle

chart.add_strength(name='Confirmed', dot_style=DotStyle.SOLID)
chart.add_strength(name='Unconfirmed', dot_style=DotStyle.DASHED)
chart.add_strength(name='Tentative', dot_style=DotStyle.DOTTED)
```

Then reference them on entities or links:

```python
chart.add_icon(id='Alice', type='Person', strength='Confirmed')
chart.add_link(from_id='A', to_id='B', strength='Tentative')
```

Available dot styles: `SOLID` (`'-'`), `DASHED` (`'---'`), `DASH_DOT`
(`'-.'`), `DASH_DOT_DOT` (`'-..'`), `DOTTED` (`'...'`).

### Legend items

Add items to the chart legend:

```python
from anxwritter import LegendItemType

chart = ANXChart(settings={'legend_cfg': {'show': True}})

# Use the LegendItemType enum (recommended), the lowercase string,
# or the legacy Title Case string -- all three are accepted.
chart.add_legend_item(name='Person',    item_type=LegendItemType.ICON)
chart.add_legend_item(name='Confirmed', item_type='line',  # lowercase
                      color=0, line_width=2, dash_style='solid')
chart.add_legend_item(name='Call', item_type='Link',  # legacy Title Case
                      color=0, line_width=1, arrows='->')
chart.add_legend_item(name='Important', item_type=LegendItemType.FONT,
                      font=Font(bold=True, color='Red'))
```

Legend item types -- pick whichever form you prefer:

| `LegendItemType` enum | Lowercase | Legacy Title Case |
|---|---|---|
| `LegendItemType.FONT` | `'font'` | `'Font'` (default) |
| `LegendItemType.TEXT` | `'text'` | `'Text'` |
| `LegendItemType.ICON` | `'icon'` | `'Icon'` |
| `LegendItemType.ATTRIBUTE` | `'attribute'` | `'Attribute'` |
| `LegendItemType.LINE` | `'line'` | `'Line'` |
| `LegendItemType.LINK` | `'link'` | `'Link'` |
| `LegendItemType.TIMEZONE` | `'timezone'` | `'TimeZone'` |
| `LegendItemType.ICON_FRAME` | `'icon_frame'` | `'IconFrame'` |

ANB always displays legend items grouped by type in a fixed order:
Text, Attribute, Icon, Line, Font, Link, TimeZone, IconFrame.

#### Icons on `Icon` / `Attribute` rows

Pick the icon shown next to the label with `image_name` (a canonical ANB icon key):

```python
chart.add_legend_item(name='Identificador Nacional', item_type='attribute',
                      image_name='national identifier')
chart.add_legend_item(name='Alerta', item_type='icon',
                      image_name='reddot', shade_color='Red')
```

Two things to know about `item_type='attribute'`:

- It's a free-form icon picker — ANB does **not** link the legend row to any
  `<AttributeClass>` definition. You choose any icon key and set any label.
- The icon key is the ANB internal identifier (e.g. `'phone'`, `'national identifier'`,
  `'reddot'`), not the pt-BR localized name. Resolve pt-BR names via the locale map if
  needed.

---

## 8. EntityType and LinkType

Pre-registering types gives you control over the icon, colour, and
representation used in ANB's type system and palette.

```python
chart.add_entity_type(name='Person', icon_file='person', color='Blue')
chart.add_entity_type(name='Vehicle', icon_file='vehicle', color='Green')
chart.add_entity_type(name='Location', icon_file='location', color='Red',
                      representation='Box')
chart.add_link_type(name='Call', color='Dark Blue')
chart.add_link_type(name='Transaction', color='Dark Red')
```

Any entity whose `type` matches a registered `EntityType.name` automatically
uses that type's icon and settings.

### Org-wide types via config files

Define types once in a YAML config and reuse across charts:

```yaml
# org_types.yaml
entity_types:
  - name: Person
    icon_file: person
    color: Blue
  - name: Vehicle
    icon_file: vehicle
    color: Green

link_types:
  - name: Call
    color: Dark Blue
```

```python
chart = ANXChart(config_file='org_types.yaml')
chart.add_icon(id='Alice', type='Person')   # uses the Person type definition
chart.to_anx('output/chart')
```

---

## 9. Semantic types

Semantic types are ANB's type library system. They give your entity types,
link types, and attributes a standardised meaning that ANB recognises across
charts and organisations.

**When do you need them?** If your organisation uses ANB's semantic type
library (e.g. standard i2 types like Person, Vehicle, Phone Call To), you
should map your types to their semantic equivalents.

### Where to get the standard types

anxwritter does not ship i2's standard semantic-type library. You have two options:

**Option A — define your own taxonomy.** Skip ANB's standard library entirely
and create the types you need in your config file. Use the `Entity`/`Link`
roots and the four abstract property roots (`Abstract Text`, `Abstract
Number`, `Abstract Date & Time`, `Abstract Flag`) as parents.

```yaml
# in your config file
semantic_entities:
  - name: Pessoa
    kind_of: Entity
  - name: Suspeito
    kind_of: Pessoa
semantic_properties:
  - name: CPF
    base_property: Abstract Text
```

**Option B — skip semantic types.** If you don't need ANB's library-aware
features (palette filtering, type-aware search, Esri Maps), don't set
`semantic_type` on anything. The chart still builds and opens in ANB; entity
types and link types still drive icons and colors as usual.

### Custom semantic types

Extend the standard library with your own types:

```python
# Custom entity type
chart.add_semantic_entity(
    name='Suspect', kind_of='Person',
    description='Person under investigation',
    synonyms=['POI', 'Suspeito'],
)
chart.add_entity_type(name='Suspect', icon_file='person', color='Red',
                      semantic_type='Suspect')

# Custom link type
chart.add_semantic_link(name='Surveilled', kind_of='Associate Of')
chart.add_link_type(name='Surveilled', semantic_type='Surveilled')
```

### Per-instance overrides

Individual entities and links can override their type-level semantic type:

```python
chart.add_icon(id='Alice', type='Person', semantic_type='Suspect')
chart.add_link(from_id='A', to_id='B', type='Call',
               semantic_type='Surveilled')
```

### Property semantic types (for attributes)

```python
chart.add_semantic_property(
    name='CPF Number',
    base_property='Abstract Text',
    synonyms=['CPF', 'Cadastro de Pessoa Fisica'],
)
chart.add_attribute_class(name='CPF', type='text', semantic_type='CPF Number')
```

---

## 10. Palettes

Palettes populate ANB's "Insert from Palette" panel, letting users drag
pre-configured entity and link types onto the chart.

```python
from anxwritter import Palette, PaletteAttributeEntry

chart.add_palette(Palette(
    name='Investigation',
    entity_types=['Person', 'Vehicle', 'Location'],
    link_types=['Call', 'Transaction'],
    attribute_classes=['Phone', 'Balance'],
    attribute_entries=[PaletteAttributeEntry(name='Currency', value='BRL')],
))
```

Or with keyword args:

```python
chart.add_palette(name='Standard', entity_types=['Person'], link_types=['Call'])
```

**Auto-populate**: when you define no palettes at all, anxwritter auto-generates
a single palette named `"anxwritter"` containing all registered entity types,
link types, and attribute classes. Defining any palette explicitly disables
this auto-population.

---

## 11. Dates, times, and timezones

### Date and time format

The recommended canonical formats are `yyyy-MM-dd` for dates and `HH:MM:SS` for times:

```python
chart.add_icon(id='Alice', type='Person',
               date='2024-01-15', time='14:30:00')
chart.add_link(from_id='A', to_id='B', type='Call',
               date='2024-01-15', time='09:00:00')
```

The validator and the builder both accept several other formats so you can pass
data from spreadsheets and CSV imports without reformatting first:

| Field | Supported formats | Notes |
|---|---|---|
| `date` | `yyyy-MM-dd` (canonical), `dd/MM/yyyy`, `yyyymmdd` | Ambiguous US `mm/dd/yyyy` is **rejected**. |
| `time` | `HH:MM:SS` (canonical), `HH:MM:SS.ffffff`, `HH:MM`, `HH:MM AM/PM` | All convert to canonical form internally. |

```python
chart.add_icon(id='Bob',  type='Person', date='15/01/2024', time='14:30')
chart.add_icon(id='Carl', type='Person', date='20240115',   time='2:30 PM')
```

See [reference/datetime-and-timezones.md](../reference/datetime-and-timezones.md#supported-datetime-input-formats) for the full table.

**Note**: ANB interprets date/time values as UTC (GMT+0). If you work in a
different timezone, you may need to adjust accordingly.

### DateTimeFormat collection

Register named display formats at the chart level, then reference them on
individual items:

```python
from anxwritter import DateTimeFormat

chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
chart.add_datetime_format(name='BR', format='dd/MM/yyyy')
chart.add_datetime_format(name='US', format='MM/dd/yyyy HH:mm')

chart.add_icon(id='Alice', type='Person',
               date='2024-01-15', datetime_format='ISO')
chart.add_link(from_id='A', to_id='B', type='Call',
               date='2024-01-15', datetime_format='BR')
```

The `datetime_format` field must be the **name** of a registered format.
Inline format strings are not supported (ANB rejects them).

### Timezones

Set a timezone on entities, links, or cards using the `TimeZone` dataclass
with `id` (ANB's internal UniqueID integer) and `name` (a display string):

```python
from anxwritter import TimeZone

chart.add_icon(id='Alice', type='Person',
               date='2024-01-15', time='14:30:00',
               timezone=TimeZone(id=55, name='Argentina'))
```

**Both `date` and `time` must be set** when using a timezone. ANB silently
ignores the timezone if only the date is set.

### Common timezone IDs

| ID | Timezone | UTC offset |
|----|----------|------------|
| 1 | UTC | +0:00 |
| 32 | GMT | +0:00 |
| 27 | Eastern (US) | -5:00 |
| 20 | Central (US) | -6:00 |
| 52 | Pacific (US) | -8:00 |
| 17 | Central European | +1:00 |
| 21 | China | +8:00 |
| 65 | Japan | +9:00 |
| 55 | Argentina | -3:00 |
| 37 | India | +5:30 |
| 40 | Korea | +9:00 |

The full mapping (IDs 1-122) is in `anxwritter/timezones.json`.

---

## 12. Settings overview

All chart-level settings are passed via a nested dict (or a `Settings`
dataclass) to the `ANXChart` constructor.

```python
chart = ANXChart(settings={
    'extra_cfg': {
        'arrange': 'grid',            # layout: 'circle', 'grid', or 'random'
        'entity_auto_color': True,    # auto-assign colours to entities
        'link_match_entity_color': True,
        'link_arc_offset': 20,        # parallel link spacing in pixels
    },
    'chart': {
        'bg_color': 'Light Grey',     # chart background colour
    },
    'view': {
        'time_bar': True,             # show the ANB time bar
    },
    'grid': {
        'snap': True,                 # snap entities to grid
    },
    'summary': {
        'title': 'Op Sunshine',
        'author': 'J. Doe',
        'keywords': 'fraud, money',
    },
    'legend_cfg': {
        'show': True,                 # display the legend panel
    },
})
```

You can also mutate settings after construction:

```python
chart = ANXChart()
chart.settings.extra_cfg.arrange = 'grid'
chart.settings.summary.title = 'Op Sunshine'
chart.settings.view.time_bar = True
```

### Most useful settings at a glance

| Setting | What it does |
|---------|-------------|
| `extra_cfg.arrange` | Layout algorithm: `'circle'` (default), `'grid'`, `'random'` |
| `extra_cfg.entity_auto_color` | Auto-assign colours to uncoloured entities |
| `extra_cfg.link_match_entity_color` | Colour link lines to match the destination entity |
| `extra_cfg.link_arc_offset` | Pixel spacing between parallel links (default 20) |
| `chart.bg_color` | Chart background colour |
| `view.time_bar` | Show/hide the ANB time bar |
| `grid.snap` | Snap entities to the grid |
| `summary.title` | Chart title (shown in ANB properties) |
| `summary.author` | Chart author |
| `legend_cfg.show` | Show the legend panel |

For all available settings fields, see the [settings reference](../reference/settings.md).

---

## 13. Validation and common pitfalls

### How validation works

`chart.validate()` checks your chart data and returns a list of error dicts.
An empty list means the chart is valid.

```python
errors = chart.validate()
for err in errors:
    print(err['type'], '--', err['message'])
```

`to_anx()` and `to_xml()` call `validate()` internally and raise
`ANXValidationError` if any errors are found:

```python
from anxwritter import ANXValidationError

try:
    chart.to_anx('output/chart')
except ANXValidationError as e:
    for err in e.errors:
        print(err)
```

### Common pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| Entity not shown on chart | `id` or `type` is empty/missing | Make sure both `id` and `type` are set |
| Link not shown | `from_id` or `to_id` does not match any entity `id` | Check spelling -- IDs are case-sensitive |
| Invalid color error | Colour name does not match ANB's list | Use one of the 40 named colours (case-insensitive — `'dark blue'`, `'DARK BLUE'`, and `'Dark Blue'` all work), the `Color` enum (`Color.DARK_BLUE`), or a `#RRGGBB` hex string. |
| Auto-color ignored on some entities | Explicit `color` always wins | Remove the explicit `color` field to let auto-color work |
| Attribute type conflict | Same attribute name used with different Python types | Ensure `'Balance'` is always `float` (or always `str`), never mixed |
| Loose card not attached | `entity_id`/`link_id` does not match | Check that the ID matches an entity `id` or a link's `link_id` field |
| Timezone ignored | Only `date` is set, `time` is missing | Both `date` and `time` must be set for timezone to take effect |
| DateTimeFormat rejected | Used an inline format string instead of a registered name | Register the format with `add_datetime_format()` first, then reference by name |
| Ordered link rejected | `ordered=True` on a non-ThemeLine link | `ordered=True` only works when both link ends are ThemeLine entities |
| Config conflict error | Data file redefines a name locked by config | Remove the conflicting definition from the data file, or change the config |

---

## 14. Full examples

### Example A: Phone calls

Two people connected by a phone call with attributes and evidence cards.

```python
from anxwritter import ANXChart, Card, GradeCollection

chart = ANXChart(settings={
    'extra_cfg': {'arrange': 'circle'},
    'summary': {'title': 'Phone Call Analysis'},
})

# Grade collections
chart.grades_one = GradeCollection(items=['Always reliable', 'Usually reliable', 'Fairly reliable'])
chart.grades_two = GradeCollection(items=['Confirmed', 'Probably true', 'Possibly true'])

# Entities
chart.add_icon(
    id='Alice', type='Person', color='Blue',
    attributes={'Phone Number': '555-0001'},
    cards=[
        Card(summary='Primary suspect', source_ref='REP-001',
             source_type='Intelligence', grade_one=0, grade_two=0),
    ],
)
chart.add_icon(
    id='Bob', type='Person', color='Red',
    attributes={'Phone Number': '555-0002'},
)

# Link with attributes
chart.add_link(
    from_id='Alice', to_id='Bob', type='Telephone Call',
    arrow='->', date='2024-01-15', time='14:30:00',
    label='Mobile',
    attributes={'Duration (sec)': 120, 'Call Type': 'Mobile'},
)

path = chart.to_anx('output/phone_calls')
print(f'Written: {path}')
```

### Example B: Financial transfers

Three people, two bank accounts, and transfer links with monetary amounts.

```python
from anxwritter import ANXChart

chart = ANXChart(settings={
    'extra_cfg': {'arrange': 'grid', 'entity_auto_color': True},
    'summary': {'title': 'Financial Transfer Network'},
})

# Attribute formatting
chart.add_attribute_class(name='Amount',   type='number', prefix='R$ ', decimal_places=2)
chart.add_attribute_class(name='Currency', type='text',   prefix='(', suffix=')')
chart.add_attribute_class(name='Role',     type='text')

# People
chart.add_icon(id='Alice', type='Person',
               attributes={'Role': 'Account holder'})
chart.add_icon(id='Bob', type='Person',
               attributes={'Role': 'Account holder'})
chart.add_icon(id='Charlie', type='Person',
               attributes={'Role': 'Intermediary'})

# Accounts
chart.add_box(id='ACC-001', type='Bank Account', label='Alice Savings',
              width=150, height=80)
chart.add_box(id='ACC-002', type='Bank Account', label='Bob Current',
              width=150, height=80)

# Ownership links
chart.add_link(from_id='Alice', to_id='ACC-001', type='Owns', arrow='->')
chart.add_link(from_id='Bob', to_id='ACC-002', type='Owns', arrow='->')

# Transfer links
chart.add_link(
    from_id='ACC-001', to_id='ACC-002', type='Transfer',
    arrow='->', date='2024-02-01', label='TX-001',
    attributes={'Amount': 1500.00, 'Currency': 'BRL'},
)
chart.add_link(
    from_id='ACC-002', to_id='ACC-001', type='Transfer',
    arrow='->', date='2024-02-03', label='TX-002',
    attributes={'Amount': 500.00, 'Currency': 'BRL'},
)
chart.add_link(
    from_id='Charlie', to_id='ACC-001', type='Deposit',
    arrow='->', date='2024-02-05',
    attributes={'Amount': 10000.00, 'Currency': 'BRL'},
)

path = chart.to_anx('output/financial_transfers')
print(f'Written: {path}')
```

### Example C: Configured attributes

Entities with attribute classes customised for display: prefixes, suffixes,
decimal places, and merge behaviour.

```python
from anxwritter import ANXChart, MergeBehaviour, DotStyle

chart = ANXChart(settings={
    'extra_cfg': {'arrange': 'grid'},
    'legend_cfg': {'show': True},
})

# Attribute class configuration
chart.add_attribute_class(name='Balance', type='number', prefix='R$ ', decimal_places=2,
                          merge_behaviour=MergeBehaviour.ADD)
chart.add_attribute_class(name='Phone',  type='text',   prefix='Tel: ')
chart.add_attribute_class(name='Active', type='flag',   show_if_set=True)
chart.add_attribute_class(name='Weight', type='number', suffix=' kg', decimal_places=1)

# Strengths
chart.add_strength(name='Confirmed', dot_style=DotStyle.SOLID)
chart.add_strength(name='Tentative', dot_style=DotStyle.DASHED)

# Legend
chart.add_legend_item(name='Person', item_type='Icon')
chart.add_legend_item(name='Confirmed', item_type='Line',
                      color=0, line_width=2, dash_style='solid')
chart.add_legend_item(name='Tentative', item_type='Line',
                      color=0, line_width=1, dash_style='dashed')

# Entities with attributes
chart.add_icon(
    id='Alice', type='Person', color='Blue',
    strength='Confirmed',
    attributes={
        'Phone': '555-0001',
        'Balance': 12500.75,
        'Active': True,
        'Weight': 68.5,
    },
)
chart.add_icon(
    id='Bob', type='Person', color='Red',
    strength='Tentative',
    attributes={
        'Phone': '555-0002',
        'Balance': 340.00,
        'Active': False,
        'Weight': 82.3,
    },
)

chart.add_link(from_id='Alice', to_id='Bob', type='Associate',
               strength='Tentative')

path = chart.to_anx('output/configured_attributes')
print(f'Written: {path}')
```

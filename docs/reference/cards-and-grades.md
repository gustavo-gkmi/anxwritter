# Cards, Grades, and Source Types

Evidence cards, grading collections, and source type definitions for entities and links.

---

## Card

`Card` is a dataclass in `anxwritter.models`. Cards provide source/grading metadata visible in ANB's card panel. They can be attached to both entities and links.

### Card fields

All fields are optional.

| Field | Type | Description |
|-------|------|-------------|
| `summary` | `str` | Short summary text shown in ANB's card panel. Maps to `Summary` XML attribute. |
| `date` | `str` | Date string `yyyy-MM-dd` (UTC). |
| `time` | `str` | Time string `HH:mm:ss` (UTC). |
| `description` | `str` | Long-form card body text. Maps to `Text` XML attribute on `<Card>`. |
| `datetime_description` | `str` | Free-text description of the date/time (e.g. `'About 3pm'`). Written as `DateTimeDescription` attribute on `<Card>`. |
| `source_ref` | `str` | Source document reference string. |
| `source_type` | `str` | Source type label (e.g. `'Witness'`). Should match an entry in `chart.source_types`. |
| `grade_one` | `Union[int, str]` | Source reliability grade. Accepts a 0-based index into `chart.grades_one` or the grade name string (e.g. `'Reliable'`); the name is resolved at validate/build time. |
| `grade_two` | `Union[int, str]` | Information reliability grade. Accepts a 0-based index into `chart.grades_two` or the grade name string. |
| `grade_three` | `Union[int, str]` | Third grading dimension. Accepts a 0-based index into `chart.grades_three` or the grade name string. |
| `timezone` | `TimeZone` | TimeZone for the card. Uses the `TimeZone` dataclass with `id` (int, ANB UniqueID 1--122) and `name` (str). Example: `TimeZone(id=1, name='UTC')`. Requires both `date` and `time` to be set. See [datetime-and-timezones.md](datetime-and-timezones.md). |
| `entity_id` | `str` | **INTERNAL ONLY** -- routes loose card to an entity at build time. NOT written to XML. |
| `link_id` | `str` | **INTERNAL ONLY** -- routes loose card to a link at build time. NOT written to XML. |

### XML structure

Cards are emitted as `<CardCollection>` children.

- Inside `<Entity>`: `<CardCollection>` is a direct child of `<Entity>`.
- Inside `<Link>`: `<CardCollection>` must appear **before** `<LinkStyle>`.

`<TimeZone UniqueID="..." Name="..."/>` is the only valid child element of `<Card>`. It is emitted when `timezone` is set (a `TimeZone` dataclass with `id` and `name` fields).

Grade indices (`GradeOneIndex`, `GradeTwoIndex`, `GradeThreeIndex`) are only emitted when explicitly set. Omitting them leaves the grade unset in ANB.

---

## Inline cards on entities

Attach cards directly to an entity via the `cards` field on any entity class (`Icon`, `Box`, `Circle`, `ThemeLine`, `EventFrame`, `TextBlock`, `Label`).

```python
from anxwritter import Card

chart.add_icon(
    id='Alice', type='Person',
    cards=[
        Card(
            summary='Main suspect',
            source_ref='REP-001',
            source_type='Witness',
            grade_one=2,
            grade_two=1,
            date='2024-01-15',
            time='14:30:00',
        ),
    ],
)
```

---

## Inline cards on links

Attach cards directly to a `Link` via its `cards` field. The `link_id` field on the `Link` is only needed if you also plan to use `add_card(link_id=...)` for loose cards targeting the same link.

```python
from anxwritter import Link, Card

chart.add_link(
    from_id='Alice', to_id='Bob', type='Call',
    link_id='call_001',
    cards=[
        Card(summary='Witness account', date='2024-01-17',
             source_ref='RPT-001', grade_one=1, grade_two=2),
        Card(summary='Report B', date='2024-02-01'),
    ],
)
```

---

## Loose cards

Loose cards are added separately via `add_card()` and routed to their target entity or link at build time. Unresolved `entity_id` or `link_id` values raise `ANXValidationError` (error type: `missing_target`).

### Loose card on an entity

```python
chart.add_card(entity_id='Alice', summary='Report B', date='2024-02-01')

# Equivalent using add():
chart.add(Card(entity_id='Alice', summary='Report C'))
```

### Loose card on a link

The target link must have a `link_id` set. The `link_id` field is internal only and not written to XML.

```python
chart.add_link(
    from_id='Alice', to_id='Bob', type='Call',
    link_id='call_001',
)

chart.add_card(link_id='call_001', summary='Intercept', date='2024-01-18', time='09:00:00')
```

---

## Grade collections

Three separate grade collection attributes on `ANXChart`, each a plain `List[str]`. Empty by default -- when omitted, ANB uses its built-in labels.

| Attribute | Grading dimension | XML element |
|-----------|-------------------|-------------|
| `chart.grades_one` | Source reliability | `<GradeOne>` |
| `chart.grades_two` | Information reliability | `<GradeTwo>` |
| `chart.grades_three` | Third dimension | `<GradeThree>` |

### Reference by index or by name

`grade_one`, `grade_two`, and `grade_three` on entities, links, and cards accept **either** a 0-based index into the corresponding `GradeCollection.items` list **or** the grade name string. Names are resolved to indices at validate/build time. Unknown names raise `unknown_grade` -- there is no auto-create.

```python
from anxwritter import GradeCollection

chart.grades_one = GradeCollection(items=[
    'Always reliable', 'Usually reliable', 'Fairly reliable',
    'Not usually reliable', 'Unreliable', 'Cannot be judged',
])
chart.grades_two = GradeCollection(items=['Confirmed', 'Probably true', 'Possibly true'])
chart.grades_three = GradeCollection(items=['High', 'Medium', 'Low'])

# Reference by index:
chart.add_icon(id='Alice', type='Person', grade_one=0, grade_two=1)
# grade_one=0 -> 'Always reliable'
# grade_two=1 -> 'Probably true'

# Or reference by name -- equivalent to the above:
chart.add_icon(id='Bob', type='Person',
               grade_one='Always reliable', grade_two='Probably true')

# With a default — ungraded items get 'Confirmed' instead of a '-' sentinel:
chart.grades_two = GradeCollection(
    default='Confirmed',
    items=['Confirmed', 'Probably true', 'Possibly true'],
)
```

### XML structure

```xml
<GradeOne>
  <StringCollection>
    <String Id="ID7" Text="Always reliable"/>
    <String Id="ID8" Text="Usually reliable"/>
  </StringCollection>
</GradeOne>
```

`Id` is a required IDREF target -- omitting it causes "IDREF not specified" errors. anxwritter auto-generates IDs as `ID<N>` (sequential integers).

### Validation

- `grade_out_of_range`: grade index is negative or exceeds the size of the corresponding grade collection.
- `unknown_grade`: grade is given as a name string but does not match any entry in the corresponding `GradeCollection.items`. No auto-create -- the name must be registered first.
- `invalid_grade_default`: `default` references a name not present in the `items` list of the same `GradeCollection`.
- When a grade field is omitted (set to `None`), the `GradeOneIndex`/`GradeTwoIndex`/`GradeThreeIndex` XML attribute is not emitted and ANB treats the grade as unset.

---

## Source types

`chart.source_types` is a plain `List[str]`. Defines the SourceType dropdown entries in the ANB UI (the `<SourceHints>` collection). Empty by default.

```python
chart.source_types = ['Discovery', 'Informant', 'Intelligence',
                      'Officer', 'Record', 'Victim', 'Witness']

# Reference by label string on entities, links, and cards:
chart.add_icon(id='Alice', type='Person', source_type='Witness')
```

### XML structure

```xml
<SourceHints>
  <StringCollection>
    <String Id="ID12" Text="Discovery"/>
    <String Id="ID13" Text="Informant"/>
  </StringCollection>
</SourceHints>
```

IDs are auto-generated as `ID<N>` (sequential integers).

The `source_type` field on entities, links, and cards is a free-text string that should match one of these labels.

### Config locking

When a config file is applied (via `--config` or `config_file`), the source types list is locked. Providing a different list in data raises a `config_conflict` validation error. An identical list is silently skipped. See [constructors.md](constructors.md) for conflict detection rules.

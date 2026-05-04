# DateTimeFormat and TimeZones

Supported date/time input formats, named date/time display formats, timezone assignment on entities/links/cards, and the full ANB timezone ID mapping.

---

## Supported date/time input formats

The `date` and `time` fields on entities, links, and cards each accept several string
formats. The validator (`utils._validate_date` / `utils._validate_time`) and the builder
(`builder.ANXBuilder._format_datetime`) iterate the same format tuples, so any string that
validates also builds.

### Date

| Format | Example | Notes |
|---|---|---|
| `yyyy-MM-dd` | `'2024-01-15'` | **Canonical, recommended.** ISO 8601 date. |
| `dd/MM/yyyy` | `'15/01/2024'` | European day/month/year. |
| `yyyymmdd` | `'20240115'` | Compact ISO. |

The ambiguous US format `mm/dd/yyyy` is **intentionally rejected**. Use the canonical form
or `dd/MM/yyyy` instead. Validation reports the rejection as `invalid_date`.

### Time

| Format | Example | Notes |
|---|---|---|
| `HH:MM:SS` | `'14:30:00'` | **Canonical, recommended.** 24-hour clock. |
| `HH:MM:SS.ffffff` | `'14:30:00.500000'` | With microseconds. |
| `HH:MM` | `'14:30'` | No seconds (treated as `:00`). |
| `HH:MM AM/PM` | `'2:30 PM'` | 12-hour clock. |

Invalid hours/minutes/seconds (e.g. `'25:00:00'`, `'14:60:00'`) are reported as
`invalid_time`.

### When to use which

- **Always prefer the canonical form** (`yyyy-MM-dd` / `HH:MM:SS`) for new code — it is
  unambiguous and round-trippable.
- The non-canonical formats exist to accept data from spreadsheets, CSV imports, and
  legacy systems without requiring callers to reformat first.
- The builder normalizes everything to the canonical ANX form (`yyyy-MM-ddTHH:MM:SS.000`)
  before writing XML, so the choice of input format has no effect on the output file.

### Adding a new supported format

The format tuples live in two places:

- `anxwritter/utils.py` — `_DATE_FORMATS` and `_TIME_FORMATS` (validator side).
- `anxwritter/builder.py` — `_format_datetime()` (builder side).

To add a new format, edit both tuples in lockstep so the validator and builder stay
agreed. Test by adding entries to `tests/test_utils.py::TestValidateDate` /
`TestValidateTime` and `tests/test_chart_build.py::TestDateTimeFormatAcceptance`.

---

## DateTimeFormat

Named date/time display formats control how ANB renders date/time values on chart items. Formats must be registered at chart level before referencing them on entities or links. ANB 9 **only** accepts registered format names, not inline format strings.

```python
from anxwritter import DateTimeFormat

chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
chart.add_datetime_format(name='BR', format='dd/MM/yyyy HH:mm')
chart.add_datetime_format(name='Time Only', format='HH:mm:ss')

# Or using the typed dataclass:
chart.add(DateTimeFormat(name='US', format='MM/dd/yyyy'))
```

### DateTimeFormat fields

| Field | Type | Required | Max length | Description |
|-------|------|----------|------------|-------------|
| `name` | `str` | **yes** | 250 chars | Format name. Natural key -- duplicate names replace the earlier entry. |
| `format` | `str` | no | 259 chars | Format pattern string. e.g. `'dd/MM/yyyy'`, `'yyyy-MM-dd HH:mm'`. When empty, only the name is registered. |

### XML structure

```xml
<DateTimeFormatCollection>
  <DateTimeFormat Id="ID7" Name="ISO" Format="yyyy-MM-dd"/>
  <DateTimeFormat Id="ID8" Name="BR" Format="dd/MM/yyyy HH:mm"/>
</DateTimeFormatCollection>
```

IDs are auto-generated as `ID<N>` (sequential integers). Position in `<Chart>`: after `LinkTypeCollection`, before the chart-level `<Font>`/`<ChartItemCollection>`.

### ANB 9 constraint

Inline format strings (not registered in the collection) are rejected at import time by SetDateTimeFormat. Always register formats first via `add_datetime_format()`.

`DateTimeFormatReference` (IDREF) must **not** be used. ANB 9 rejects it. The `DateTimeFormat` string attribute on `<CIStyle>` is the correct approach.

---

## Per-item `datetime_format` field

Available on all entity classes (`Icon`, `Box`, `Circle`, `ThemeLine`, `EventFrame`, `TextBlock`, `Label`) and `Link`.

The value must be the **name** of a registered `DateTimeFormat`. It is emitted as the `DateTimeFormat` attribute on `<CIStyle>`. ANB 9 resolves the name against the `DateTimeFormatCollection` internally.

```python
chart.add_icon(id='Alice', type='Person', date='2024-01-15', datetime_format='ISO')
chart.add_link(from_id='Alice', to_id='Bob', type='Call',
               date='2024-01-15', datetime_format='BR')
```

Validation catches unregistered names with the `unregistered_datetime_format` error type. See [validation.md](validation.md).

---

## Time zone note

ANB treats all `DateTime` values as **UTC (GMT+0)**. There is no automatic adjustment for the user's local time zone. To display the correct local time, add your UTC offset to the stored value.

| Desired display (GMT-3) | Store in `time` |
|-------------------------|-----------------|
| `08:00:00` | `11:00:00` |
| `11:00:00` | `14:00:00` |
| `16:00:00` | `19:00:00` |

---

## TimeZone on entities and links

The `timezone` field on entities and links uses the `TimeZone` dataclass with two required fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | ANB internal UniqueID integer (1--122). NOT the Windows timezone registry Index. |
| `name` | `str` | Cosmetic display name string. ANB resolves the timezone from `id` alone. |

Both fields are required. Omitting either causes a schema error.

```python
from anxwritter import TimeZone

chart.add_icon(id='Alice', type='Person',
               date='2024-01-15', time='10:00:00',
               timezone=TimeZone(id=55, name='Argentina Time'))
```

### XML output

```xml
<ChartItem ...>
  <CIStyle .../>
  <TimeZone UniqueID="55" Name="Argentina Time"/>
</ChartItem>
```

`<TimeZone>` must appear **after** `<CIStyle>` in the child sequence. Placing it before `<CIStyle>` causes ANB 9 to report `CIStyle` as invalid.

### Requirement: both date and time

The entity or link **must have both `date` and `time` set** when using `timezone`. ANB silently ignores `<TimeZone>` when the item has `TimeSet="false"`. Validation catches this with the `timezone_without_datetime` error type.

---

## TimeZone on cards

Cards use the same `TimeZone` dataclass as entities and links.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | ANB internal UniqueID integer (1--122). |
| `name` | `str` | Display name string. |

```python
from anxwritter import Card, TimeZone

Card(
    summary='Report',
    date='2024-01-15',
    time='14:30:00',
    timezone=TimeZone(id=55, name='Argentina Time'),
)
```

`<TimeZone UniqueID="..." Name="..."/>` is the only valid child element of `<Card>` in ANB 9+.

The card **must have both `date` and `time` set**. If only `date` is set (`TimeSet="false"`), ANB opens the file but ignores the timezone and writes a warning to the import log.

---

## Common timezone values (quick reference)

| UniqueID | UTC offset | Long name | Short |
|----------|-----------|-----------|-------|
| 1 | UTC+0 | Coordinated Universal Time | UTC |
| 32 | UTC+0 | Greenwich Mean Time | GMT |
| 88 | UTC+0 | Zulu | Z |
| 55 | UTC-3 | Argentina Time | ART |
| 27 | UTC-5 | Eastern Standard Time | EST |
| 20 | UTC-6 | Central Standard Time | CST |
| 43 | UTC-7 | Mountain Standard Time | MST |
| 52 | UTC-8 | Pacific Standard Time | PST |
| 36 | UTC-10 | Hawaiian Standard Time | HST |
| 17 | UTC+1 | Central Europe Time | CET |
| 31 | UTC+2 | Eastern Europe Time | EET |
| 54 | UTC+3 | Moscow Time | MSK |
| 37 | UTC+5:30 | India Standard Time | IST |
| 21 | UTC+8 | China Standard Time | China |
| 60 | UTC+8 | Malay Peninsula Standard Time | SGT |
| 40 | UTC+9 | Korea Standard Time | KST |
| 65 | UTC+9 | Japan Standard Time | JST |
| 24 | UTC+10 | Australian Eastern Standard Time | AEST |
| 47 | UTC+13 | New Zealand Daylight Time | NZDT |

---

## Full timezone table (IDs 1--122)

Full mapping stored in `anxwritter/timezones.json`. Derived from the timezone enumeration shipped with ANB and verified against the application's import behaviour.

| ID | Offset | Long name | Short |
|----|--------|-----------|-------|
| 1 | +00:00 | Coordinated Universal Time | UTC |
| 2 | +04:30 | Afghanistan Standard Time | AFT |
| 3 | -09:00 | Alaska Standard Time | AKST |
| 4 | +03:00 | Arab Standard Time | AST |
| 5 | +04:00 | Arabian Standard Time | Arabian |
| 6 | +03:00 | Arabic Standard Time | AST |
| 7 | -04:00 | Atlantic Standard Time | AST |
| 8 | +09:30 | Australian Central Standard Time | ACST |
| 9 | +11:00 | Australian Eastern Daylight Time | AEDT |
| 10 | -01:00 | Azores Standard Time | AZOST |
| 11 | -06:00 | Canada Central Standard Time | CST |
| 12 | -01:00 | Cape Verde Standard Time | CVT |
| 13 | +04:00 | Caucasus Standard Time | Caucasus |
| 14 | +10:30 | Australian Central Daylight Time | ACDT |
| 15 | -06:00 | Central America Standard Time | CT |
| 16 | +06:00 | Central Asia Standard Time | Central Asia |
| 17 | +01:00 | Central Europe Time | CET |
| 18 | +01:00 | Central Europe Time | CET |
| 19 | +11:00 | Central Pacific Standard Time | Central Pacific |
| 20 | -06:00 | Central Standard Time | CST |
| 21 | +08:00 | China Standard Time | China |
| 22 | -12:00 | Dateline Standard Time | Dateline |
| 23 | +03:00 | E. Africa Standard Time | EAT |
| 24 | +10:00 | Australian Eastern Standard Time | AEST |
| 25 | -02:00 | E. South America Daylight Time | E. South America DST |
| 26 | -02:00 | E. South America Daylight Time | E. South America DST |
| 27 | -05:00 | Eastern Standard Time | EST |
| 28 | +02:00 | Egypt Standard Time | Egypt |
| 29 | +05:00 | Ekaterinburg Standard Time | YEKST |
| 30 | +12:00 | Fiji Standard Time | Fiji |
| 31 | +02:00 | Eastern Europe Time | EET |
| 32 | +00:00 | Greenwich Mean Time | GMT |
| 33 | -03:00 | Greenland Standard Time | GST |
| 34 | +00:00 | Greenwich Standard Time | WET |
| 35 | +02:00 | Eastern Europe Time | EET |
| 36 | -10:00 | Hawaiian Standard Time | HST |
| 37 | +05:30 | India Standard Time | IST |
| 38 | +03:30 | Iran Standard Time | IRST |
| 39 | +02:00 | Jerusalem Standard Time | Israel |
| 40 | +09:00 | Korea Standard Time | KST |
| 41 | -06:00 | Central Standard Time (Mexico) | CST(M) |
| 42 | -02:00 | Mid-Atlantic Standard Time | Mid-Atlantic |
| 43 | -07:00 | Mountain Standard Time | MST |
| 44 | +06:30 | Myanmar Standard Time | Myanmar |
| 45 | +06:00 | N. Central Asia Standard Time | N. Central Asia |
| 46 | +05:45 | Nepal Standard Time | Nepal |
| 47 | +13:00 | New Zealand Daylight Time | NZDT |
| 48 | -03:30 | Newfoundland Standard Time | NFT |
| 49 | +08:00 | North Asia East Standard Time | North Asia East |
| 50 | +07:00 | North Asia Standard Time | North Asia |
| 51 | -03:00 | Chile Summer Time | CLST |
| 52 | -08:00 | Pacific Standard Time | PST |
| 53 | +01:00 | Central Europe Time | CET |
| 54 | +03:00 | Moscow Time | MSK |
| 55 | -03:00 | Argentina Time | ART |
| 56 | -05:00 | SA Pacific Standard Time | SA Pacific |
| 57 | -04:00 | SA Western Standard Time | SA Western |
| 58 | -11:00 | Samoa Standard Time | SST |
| 59 | +07:00 | SE Asia Standard Time | SE Asia |
| 60 | +08:00 | Malay Peninsula Standard Time | SGT |
| 61 | +02:00 | South Africa Standard Time | SAST |
| 62 | +05:30 | Sri Lanka Standard Time | Sri Lanka |
| 63 | +08:00 | Taipei Standard Time | Taipei |
| 64 | +11:00 | Australian Eastern Daylight Time | AEDT |
| 65 | +09:00 | Japan Standard Time | JST |
| 66 | +13:00 | Tonga Standard Time | Tonga |
| 67 | -05:00 | Eastern Standard Time | EST |
| 68 | -07:00 | Mountain Standard Time (Arizona) | MST |
| 69 | +10:00 | Vladivostok Standard Time | VLAST |
| 70 | +09:00 | Australian Western Daylight Time | AWDT |
| 71 | +01:00 | W. Central Africa Standard Time | W. Central Africa |
| 72 | +01:00 | Central Europe Time | CET |
| 73 | +05:00 | Pakistan Standard Time | PKST |
| 74 | +10:00 | West Pacific Standard Time | West Pacific |
| 75 | +09:00 | Yakutsk Standard Time | YAKST |
| 76 | -12:00 | Yankee (military) | Y |
| 77 | -11:00 | X-ray (military) | X |
| 78 | -10:00 | Whiskey (military) | W |
| 79 | -09:00 | Victor (military) | V |
| 80 | -08:00 | Uniform (military) | U |
| 81 | -07:00 | Tango (military) | T |
| 82 | -06:00 | Sierra (military) | S |
| 83 | -05:00 | Romeo (military) | R |
| 84 | -04:00 | Quebec (military) | Q |
| 85 | -03:00 | Papa (military) | P |
| 86 | -02:00 | Oscar (military) | O |
| 87 | -01:00 | November (military) | N |
| 88 | +00:00 | Zulu (military) | Z |
| 89 | +01:00 | Alpha (military) | A |
| 90 | +02:00 | Bravo (military) | B |
| 91 | +03:00 | Charlie (military) | C |
| 92 | +04:00 | Delta (military) | D |
| 93 | +05:00 | Echo (military) | E |
| 94 | +06:00 | Foxtrot (military) | F |
| 95 | +07:00 | Golf (military) | G |
| 96 | +08:00 | Hotel (military) | H |
| 97 | +09:00 | India (military) | I |
| 98 | +10:00 | Kilo (military) | K |
| 99 | +11:00 | Lima (military) | L |
| 100 | +12:00 | Mike (military) | M |
| 101 | +02:00 | Jordan Standard Time | JST |
| 102 | +00:00 | Irish Standard Time | Ireland |
| 103 | +00:00 | Western Europe Time | WET |
| 104 | -06:00 | Galapagos Standard Time | GALT |
| 105 | -05:00 | Easter Island Summer Time (Chile) | EASST |
| 106 | -05:00 | Cuba Time | Cuba |
| 107 | -03:00 | Falkland Islands Summer Time | FKST |
| 108 | -03:00 | Paraguay Summer Time | PYST |
| 109 | -02:00 | E. South America Daylight Time | E. South America DST |
| 110 | -02:00 | Eastern Brazil Daylight Time | E Brazil DST |
| 111 | -03:00 | Uruguay Time | UYT |
| 112 | -03:00 | French Guiana Time | GFT |
| 113 | -02:00 | Fernando de Noronha Standard Time (Brazil) | FST |
| 114 | +05:00 | West Asia Standard Time | WAST |
| 115 | +02:00 | Namibia Daylight Time | Namibia DST |
| 116 | +01:00 | Tunisia Standard Time | Tunisia |
| 117 | +04:00 | Caucasus Standard Time | Caucasus |
| 118 | +02:00 | Middle East Standard Time | MEST |
| 119 | +06:00 | N. Central Asia Standard Time | N. Central Asia |
| 120 | -07:00 | Mountain Standard Time (Mexico) | MST(M) |
| 121 | -08:00 | Pacific Standard Time (Mexico) | PST(M) |
| 122 | -03:00 | Central Brazilian Daylight Time | C.Brazil DST |

---

## NATO military timezones

IDs 76--100 use the NATO military phonetic alphabet. They span from Yankee (UTC-12) at ID 76 through Zulu (UTC+0) at ID 88 to Mike (UTC+12) at ID 100.

---

## Invalid IDs

IDs 123--150 are **invalid**. ANB falls back to the machine's local timezone for any UniqueID above 122.

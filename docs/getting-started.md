# Getting Started

`anxwritter` is a Python library that generates i2 Analyst's Notebook Exchange (`.anx`) files from Python objects, YAML, or JSON. The output files open directly in i2 ANB 9+ via **File > Open** — no import wizard needed.

---

## Installation

```bash
# With uv (recommended)
uv add anxwritter

# Or with pip
pip install anxwritter
```

---

## Your first chart

```python
from anxwritter import ANXChart

chart = ANXChart()

# Add two people
chart.add_icon(id='Alice', type='Person', color='Blue')
chart.add_icon(id='Bob',   type='Person', color='Red')

# Connect them
chart.add_link(from_id='Alice', to_id='Bob',
               type='Telephone Call', arrow='->',
               date='2024-01-15')

# Write the .anx file
chart.to_anx('output/my_chart')
```

This creates `output/my_chart.anx`. Open it in i2 ANB via **File > Open**.

> **Color names** match ANB's 40-name palette (e.g. `'Blue'`, `'Light Orange'`,
> `'Violet'` — note: ANB names violet `Violet`, not `purple`). Lookup is
> case- and whitespace-insensitive (`'blue'`, `'BLUE'`, `'light_orange'`,
> `'light-orange'` all work). Hex (`'#FF6600'`) and `Color` enum
> (`from anxwritter import Color; Color.BLUE`) also work, and you can
> introspect the full set with
> `from anxwritter import NAMED_COLORS`. Full table:
> [visual-styling.md → All 40 named colors](reference/visual-styling.md#all-40-named-colors).

---

## Or use YAML + CLI

Create a file `chart.yaml`:

```yaml
entities:
  icons:
    - id: Alice
      type: Person
      color: Blue
    - id: Bob
      type: Person
      color: Red

links:
  - from_id: Alice
    to_id: Bob
    type: Telephone Call
    arrow: '->'
    date: '2024-01-15'
```

Then run:

```bash
anxwritter chart.yaml -o output/my_chart.anx
```

---

## Catching errors before you build

`chart.to_anx()` and `chart.to_xml()` validate the chart and raise
`ANXValidationError` if anything is wrong. To get the same checks as a
plain list of error dicts (without building XML), call `chart.validate()`:

```python
errors = chart.validate()
for e in errors:
    print(f"[{e['type']}] {e.get('location', '-')}: {e['message']}")
```

`validate()` is a full schema lint — it walks every declared entity type,
link type, attribute class, palette, and semantic type, plus all entities
and links, regardless of whether each item is referenced elsewhere. So a
bad color on a `LinkType` no link uses still surfaces. Loading via
`from_config_file` / `apply_config_file` does **not** validate
automatically (the chart is still being assembled — entities and links
typically arrive after the config), so call `validate()` yourself once
the chart is populated, or just let `to_anx()` raise.

---

## Output: streaming & compact (the defaults)

`to_anx()` **streams** by default and writes **compact** output — it serializes
the chart items one at a time rather than holding the whole document in memory,
keeping peak memory low (~0.37× the buffered peak), and drops indentation for a
smaller file. ANB ignores indentation, so a compact `.anx` opens identically to
a pretty one. The write is atomic (temp file + rename), so a failure never leaves
a partial file.

```python
# Default: streamed, compact, atomic write:
chart.to_anx('output/big_chart')

# Opt back into the indented layout, or the buffered (whole-document) path:
chart.to_anx('output/big_chart', compact=False)   # pretty
chart.to_anx('output/big_chart', stream=False)     # build whole doc first

# Stream UTF-16 .anx bytes (e.g. straight into an HTTP response):
for chunk in chart.iter_anx_bytes():
    sink.write(chunk)

# Or stream the XML as text chunks:
for chunk in chart.iter_xml():
    ...
```

`to_xml()` returns the **pretty** (indented) string by default — the
human-readable inspection form; pass `compact=True` for the unindented form.
All of these validate the chart first and raise `ANXValidationError` if it is
invalid.

---

## What to read next

| If you want to... | Read |
|---|---|
| Learn every feature through practical Python examples | [Analyst Guide (Python)](guide/analyst-guide.md) |
| Build charts from YAML or JSON files (CLI or pipelines) | [YAML / JSON Guide](guide/yaml-json-guide.md) |
| Look up specific field names and options | [Reference docs](reference/) |
| See complete working scripts and YAML/JSON files | [`examples/`](../examples/) directory |

# Getting Started

`anxwritter` is a Python library that generates i2 Analyst's Notebook Exchange (`.anx`) files from Python objects, YAML, or JSON. The output files open directly in i2 ANB 9+ via **File > Open** — no import wizard needed.

---

## Installation

```bash
# With uv (recommended)
uv add anxwritter

# Or with pip
pip install anxwritter

# Add YAML support (optional)
pip install anxwritter[yaml]
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

## What to read next

| If you want to... | Read |
|---|---|
| Learn every feature through practical Python examples | [Analyst Guide (Python)](guide/analyst-guide.md) |
| Build charts from YAML or JSON files (CLI or pipelines) | [YAML / JSON Guide](guide/yaml-json-guide.md) |
| Look up specific field names and options | [Reference docs](reference/) |
| See complete working scripts and YAML/JSON files | [`examples/`](../examples/) directory |

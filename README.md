# anxwritter

Write i2 Analyst's Notebook Exchange (`.anx`) files from Python, JSON, or YAML.

Output files open directly in i2 ANB 9+ via **File > Open** — no import wizard, no intermediate CSV. The `.anx` file embeds the entire chart as XML.

> This project is independent and not affiliated with, endorsed by, or sponsored by the makers of i2 Analyst's Notebook — past or present — including IBM, i2 Group Limited, i2 Limited, N.Harris Computer Corporation, Harris Computer Corporation, or Constellation Software Inc. — nor by Esri, Microsoft, or Google. "i2", "i2 Analyst's Notebook", "ANB", "Esri", "Esri Maps", "Microsoft", and "Google" are trademarks of their respective owners and are referenced here solely to identify the file format and the tools this library interoperates with (nominative use).
>
> To produce structurally valid `.anx` files, this library embeds nine format identifiers: six abstract-root GUIDs required by the `lcx:LibraryCatalogue` schema and three geo-map property GUIDs required by ANB's Esri Maps subsystem. These are functional tokens (format anchors), not creative content, reproduced for interoperability purposes. The library ships nothing else from i2's type system — no standard-library types, no icon catalog, no palette definitions. All of that content stays in the user's licensed ANB installation and must be supplied by the user.
>
> This design is intentional: organisations are free to define their own default semantic types, palettes, icon mappings, link types, and attribute classes.

---

## Install

```bash
# As a library — import in your own code
pip install anxwritter

# As a command-line tool only (isolated venv, no env conflicts)
pipx install anxwritter
```

With [uv](https://docs.astral.sh/uv/):

```bash
# Add to a uv-managed project
uv add anxwritter

# Install globally as a CLI tool
uv tool install anxwritter

# One-off run without installing
uvx anxwritter chart.yaml -o my_chart.anx
```

Requires Python 3.10+.

> Want a standalone executable? `pip install pyinstaller` (or `nuitka`) and
> point it at `anxwritter/cli.py`. anxwritter does not ship pre-built binaries.

---

## Quick example

```python
from anxwritter import ANXChart

chart = ANXChart()

chart.add_icon(id='Alice', type='Person', color='Blue')
chart.add_icon(id='Bob',   type='Person', color='Red')

chart.add_link(
    from_id='Alice', to_id='Bob',
    type='Telephone Call', arrow='->',
    date='2024-01-15',
)

chart.to_anx('output/my_chart')
```

This writes `output/my_chart.anx`. Open it in ANB.

### YAML + CLI

```yaml
# chart.yaml
entities:
  icons:
    - { id: Alice, type: Person, color: Blue }
    - { id: Bob,   type: Person, color: Red }
links:
  - { from_id: Alice, to_id: Bob, type: Telephone Call, arrow: '->', date: '2024-01-15' }
```

```bash
anxwritter chart.yaml -o output/my_chart.anx
```

---

## What's in the box

- **Typed dataclass API** — `Icon`, `Box`, `Circle`, `ThemeLine`, `EventFrame`, `TextBlock`, `Label`, `Link`, `Card`
- **Three input forms** — Python objects, JSON, or YAML; all paths produce identical output
- **Org-level config files** — separate entity types, link types, attribute classes, palettes from per-chart data; layered configs supported
- **Auto-layout** — circle, grid, or random placement; manual `x`/`y` always wins
- **Geographic positioning** — map entity attributes to lat/lon for canvas layout and/or ANB Esri Maps
- **Auto-coloring** — distribute HSV hues across entities; matching link colors
- **Validation** — collects every error in one pass before writing the file
- **Semantic types** — full `lcx:LibraryCatalogue` support with custom type extension
- **CLI** — `anxwritter [--config org.yaml ...] data.{json,yaml} -o out.anx`

---

## Customize everything ANB exposes

No fixed catalog — every configurable surface in ANB is yours to define:

- **Entity types & link types** — names, icons, colors, shading, semantic-type bindings
- **Attribute classes** — type, prefix/suffix, decimals, font, merge behavior, icons, visibility
- **Palettes** — your own "Insert from Palette" panels with grouped types and pre-filled attribute entries
- **Legend** — 8 item types (icon, link, line, font, text, attribute, timezone, icon-frame) with full styling
- **Colors** — 40 named, hex, COLORREF, or auto-distributed HSV with link colors that follow the entity
- **Strengths, grades, source types, datetime formats, semantic types** — all configurable

Define your defaults once in `config.yaml`, layer overrides on top, reuse across every chart.

---

## Documentation

- [Getting started](docs/getting-started.md) — install, first chart, where to go next
- [Analyst guide](docs/guide/analyst-guide.md) — every feature via practical examples
- [Reference docs](docs/reference/) — field-by-field API reference

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2024-2026 [gustavo-gkmi](https://github.com/gustavo-gkmi).

> Developed with the help of AI coding assistants.

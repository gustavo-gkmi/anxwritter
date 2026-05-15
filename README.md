# anxwritter

[![PyPI version](https://img.shields.io/pypi/v/anxwritter.svg)](https://pypi.org/project/anxwritter/)
[![Python versions](https://img.shields.io/pypi/pyversions/anxwritter.svg)](https://pypi.org/project/anxwritter/)
[![License](https://img.shields.io/pypi/l/anxwritter.svg)](https://github.com/gustavo-gkmi/anxwritter/blob/main/LICENSE)
[![PyPI downloads](https://img.shields.io/pypi/dm/anxwritter.svg)](https://pypi.org/project/anxwritter/)

![Charts built with anxwritter — timeline of transfers, trafficking network, theme lines + event frames, link styles, auto-colored entities](https://github.com/gustavo-gkmi/anxwritter/raw/main/.github/hero.png)

For law enforcement, OSINT practitioners, and intelligence analysts who need to generate i2 Analyst's Notebook charts programmatically from case data, scrapers, or ETL pipelines, with reusable organization-level defaults instead of dragging entities by hand.

Write i2 Analyst's Notebook Exchange (`.anx`) files from Python, JSON, or YAML.

i2 Analyst's Notebook is an excellent link-analysis tool, and I've always appreciated how intuitive and powerful it is. But as someone who develops applications that produce data for it, I wanted a simpler workflow than exporting denormalized data into `.xlsx` or `.csv` files and maintaining separate `.ximp` import specifications. So I created anxwritter to generate `.anx` charts directly, making chart creation faster, cleaner, and easier for both developers and analysts.

> Independent project — not affiliated with IBM, i2 Group, N.Harris Computer Corporation, or any other vendor. "i2", "i2 Analyst's Notebook", and "ANB" are trademarks of their respective owners (nominative use). See [NOTICE.md](https://github.com/gustavo-gkmi/anxwritter/blob/main/NOTICE.md) for the full interoperability, trademark, and attribution statement.

**Status:** active development. See [CHANGELOG.md](https://github.com/gustavo-gkmi/anxwritter/blob/main/CHANGELOG.md) for breaking changes between releases. API stabilization targeted for 2.0.

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

- **Geographic positioning** — map entity attributes to lat/lon for canvas layout and/or ANB Esri Maps
- **Org-level config files** — separate entity types, link types, attribute classes, and palettes from per-chart data; layered configs with append-and-dedup or wholesale-replace semantics
- **Semantic types** — full `lcx:LibraryCatalogue` support with custom type extension; per-instance overrides
- **Auto-layout** — geometric (circle, grid, radial, random) plus topology-aware force-directed: Fruchterman-Reingold, ForceAtlas2, tidy tree (Reingold-Tilford). Manual `x`/`y` always wins; pinned entities act as anchors
- **Auto-coloring** — distribute HSV hues across entities; matching link colors that follow the target entity
- **CLI** — `anxwritter [--config org.yaml ...] data.{json,yaml} -o out.anx`, with `--show-config` provenance and `--geo-data` for external geo lookups
- **Three input forms** — Python objects, JSON, or YAML; all paths produce identical output
- **Typed dataclass API** — `Icon`, `Box`, `Circle`, `ThemeLine`, `EventFrame`, `TextBlock`, `Label`, `Link`, `Card`
- **Validation** — collects every error in one pass before writing the file

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

- [Getting started](https://github.com/gustavo-gkmi/anxwritter/blob/main/docs/getting-started.md) — install, first chart, where to go next
- [Analyst guide](https://github.com/gustavo-gkmi/anxwritter/blob/main/docs/guide/analyst-guide.md) — every feature via practical examples
- [Reference docs](https://github.com/gustavo-gkmi/anxwritter/tree/main/docs/reference) — field-by-field API reference

---

## License

MIT — see [LICENSE](https://github.com/gustavo-gkmi/anxwritter/blob/main/LICENSE). Copyright (c) 2024-2026 [gustavo-gkmi](https://github.com/gustavo-gkmi).

> Developed with the help of AI coding assistants.

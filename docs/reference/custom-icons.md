# Custom icons

Embed your own images as **entity-type**, **per-entity**, and **attribute-class**
icons. The image is stored inside the `.anx`, so the recipient sees it with **no
install and no restart** — it travels with the chart.

Added in **1.19.0**.

Converting an ordinary image (PNG, JPEG, a file path, a PIL image, or a `data:`
URI) needs the optional Pillow dependency:

```bash
pip install anxwritter[icons]
```

A ready **BMP** is embedded with no Pillow at all — see
[Bringing your own BMP](#bringing-your-own-bmp-no-pillow).

## Quick start

You register an image **once** under a name, then reference it by that bare name:

```python
from anxwritter import ANXChart, AttributeType

chart = ANXChart()

chart.add_custom_entity_icon("person", "person.png")     # register an entity icon
chart.add_custom_entity_icon("vip", "crown.png")
chart.add_custom_attribute_icon("priority", "flag.png")  # register an attribute icon

chart.add_entity_type(name="Person", icon_file="person")               # type icon
chart.add_attribute_class(name="Priority", type=AttributeType.TEXT, icon_file="priority")

chart.add_icon(id="Alice", type="Person", attributes={"Priority": "high"})
chart.add_icon(id="Bob",   type="Person", icon="vip")    # per-entity override
chart.to_anx("output/case")
```

`add_custom_entity_icon` / `add_custom_attribute_icon` accept the image as a
**path**, raw **bytes**, a **PIL image**, or a **`data:...;base64,...` URI**.

## Referencing icons

Three places take an icon name, and each resolves it the same way — **if the name
was registered with `add_custom_*_icon`, the embedded icon is used; otherwise the
name passes through** as a built-in or pre-installed ANB icon:

| reference | field |
|---|---|
| entity **type** | `EntityType.icon_file` |
| single **entity** | `Icon.icon` (also `EventFrame.icon`, `ThemeLine.icon`) |
| **attribute** class | `AttributeClass.icon_file` |

```python
chart.add_icon(id="Eve", type="Person", icon="car")   # "car" not registered → built-in "car"
```

Because unregistered names pass through, you can also reference an icon that was
**embedded by a previous chart** (ANB keeps extracted icons in the user's folder)
or one an **org pre-installs** — no re-embedding needed.

## Naming and the prefix

Every embedded icon name is prefixed (default `anxW_`) so it can never collide
with one of ANB's built-in icons (which would otherwise make your image silently
lose). **You always reference by the bare name** — the prefix is added for you and
only appears in ANB's icon picker and the extracted filename.

```python
chart.add_custom_entity_icon("logo", "logo.png")                  # → anxW_logo
chart.add_custom_entity_icon("logo", "logo.png", prefix="")       # → logo  (you own collisions)
chart.add_custom_entity_icon("logo", "logo.png", prefix="acme_")  # → acme_logo  (org namespace)
```

`prefix` is prepended verbatim — include your own separator (`acme_`, not `acme`).
Registering the same name again just replaces it (upsert).

## Images

Any image is conditioned for ANB automatically: **downscaled** (never upscaled) to
fit 128 px, **padded to square**, and converted to a **24-bit BMP** with magenta
`(255, 0, 255)` as the transparent key (PNG alpha is flattened to a hard 1-bit
edge).

- **Transparency is 1-bit** — smooth/anti-aliased edges become hard edges; pixel
  art and flat-colour icons look best.
- **Avoid pure magenta `(255, 0, 255)` in artwork** — those pixels render transparent.
- ANB **ignores icon shading** for custom icons, so `entity_auto_color` won't tint them.

## YAML / JSON config

Two config sections mirror the Python methods. Reference fields are unchanged:

```yaml
custom_entity_icons:
  - name: vip
    image: icons/crown.png                         # path, relative to this file
  - name: org_logo
    image: "data:image/png;base64,iVBORw0KG..."    # inline, no filesystem
    prefix: acme_

custom_attribute_icons:
  - name: flag
    image: icons/flag.png

entity_types:
  - { name: Person, icon_file: vip }
attribute_classes:
  - { name: Priority, type: text, icon_file: flag }
entities:
  icons:
    - { id: Bob, type: Person, icon: vip }
```

A `data:` URI carries the image inline (handy for the HTTP server, which has no
filesystem). `to_config_dict()` exports registered icons as `data:` BMP URIs so a
config round-trips.

The example above is a **data document** (it has `entities:`), so it is loaded
through the data path (`from_dict` / `from_yaml` / the CLI data file) where a
`image:` source is converted with Pillow as needed. A **config layer** is
stricter — see *Catalogs* below.

## Catalogs

A **catalog** is a reusable library of icons you build once and pull into many
charts. It is a plain config file — the same `custom_entity_icons` /
`custom_attribute_icons` sections — but with the images **baked** (already a BMP),
so consuming it needs no Pillow.

Build one with `IconCatalog` (Pillow is used here, only to convert a non-BMP
image), then export:

```python
from anxwritter import IconCatalog

cat = IconCatalog()
cat.add_custom_entity_icon('suspect', 'suspect.png')
cat.add_custom_attribute_icon('cpf', 'cpf.png')
cat.validate()                      # blob integrity — catches a black-box BMP early
cat.export_catalog('org_icons.yaml')   # baked → Pillow-free to consume
```

Consume it (no Pillow needed):

```python
from anxwritter import ANXChart, IconCatalog

chart = ANXChart()
chart.apply_icon_catalog('org_icons.yaml')          # path, dict, or IconCatalog
# or fold the icons into an existing config file in place:
IconCatalog.from_file('org_icons.yaml').include_in_config('org_config.yaml')
```

A catalog file drops straight into `--config` / `apply_config_file` and honours
the full layering vocabulary — `merge` (default), `wipe`, `lock`, `delete`, and
an in-file `cascade: {mode: ...}` — exactly like every other config section.

### `referenced` vs `all`

By default a chart writes only the icons it actually **references** (named by a
registered entity type, attribute class, or per-entity override), so a chart that
uses 6 icons from a 200-icon catalog carries only 6. Set the whole-library mode
explicitly when you need it:

```python
chart.apply_icon_catalog('org_icons.yaml', include='all')   # emit every icon
# equivalently: settings.extra_cfg.custom_icons_include = 'all'
```

### The config Pillow gate

A config layer must carry **baked** icons — a ready BMP (`data:image/bmp` /
BMP bytes) or a compiled `data`/`datalength` payload. A source that would need
conversion (a path, PNG, PIL image, or `data:image/png`) raises, pointing you at
`IconCatalog`. This keeps a shared config self-contained and Pillow-free for
everyone who consumes it. The data path and the direct `add_custom_*_icon` API
are unaffected — they still convert via Pillow.

## Bringing your own BMP (no Pillow)

Pass `image` as raw `bytes` that are already a BMP (or a `data:image/bmp;base64,…`
URI) and anxwritter embeds them **verbatim with no Pillow** — only the standard
library. The BMP is not conditioned, so it must be **24-bit (or 8-bit)**, **≤ 256
px** per side, and magenta-keyed for transparency (32-bit and oversize BMPs are
rejected — ANB renders them as a black box).

## Rendering notes

- Type, per-entity, and attribute icons all render. Attribute icons render
  immediately.
- For **entity** icons, ANB may not paint a pre-existing entity's on-canvas glyph
  until the chart is reopened (or the entity is touched); the type/palette icon
  shows on first open, and newly-added entities render immediately. This is an ANB
  redraw quirk, not a data problem.

## Scope

- Supported: entity-type, per-entity, and attribute-class icons.
- Not in this version: separate high-resolution **print** icons. `printer=True`
  raises a "planned, not yet shipped" error — the screen icon is used for printing.

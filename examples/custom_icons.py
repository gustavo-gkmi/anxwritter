"""Embedded custom icons (1.19.0) + reusable catalogs (1.20.0).

Embed your own images as entity-type, per-entity, and attribute-class icons.
The image travels inside the ``.anx`` — the recipient needs no install and no
restart. A *catalog* (1.20.0) packages many baked icons in one file you can
export once (with Pillow) and apply to any chart (no Pillow needed).

Requires Pillow:  pip install anxwritter[icons]

Run:  uv run python examples/custom_icons.py   →  output/custom_icons.anx
"""

import io
import math
import os

from anxwritter import ANXChart, AttributeType, IconCatalog

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit("This example needs Pillow:  pip install anxwritter[icons]") from None


def _heart_png(size=96):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    for i in range(361):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((size / 2 + x * size / 40, size / 2 - y * size / 40))
    d.polygon(pts, fill=(220, 20, 60, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _crown_png(size=64):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(8, 50), (8, 22), (22, 36), (32, 16), (42, 36), (56, 22), (56, 50)],
              fill=(255, 190, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def build_chart():
    chart = ANXChart()

    # Register the images once, by name.
    chart.add_custom_entity_icon("person", _heart_png())
    chart.add_custom_entity_icon("vip", _crown_png())
    chart.add_custom_attribute_icon("priority", _crown_png())

    # Reference them by their bare names (the anxW_ prefix is added for you).
    chart.add_entity_type(name="Person", icon_file="person")
    chart.add_attribute_class(name="Priority", type=AttributeType.TEXT, icon_file="priority")

    chart.add_icon(id="Alice", type="Person", x=200, y=200,
                   attributes={"Priority": "high"})
    chart.add_icon(id="Bob", type="Person", x=500, y=200, icon="vip")  # per-entity override
    chart.add_link(from_id="Alice", to_id="Bob", type="Knows", arrow="->")
    return chart


def build_catalog_demo():
    """Catalog flow (1.20.0): author once with Pillow, export a baked file,
    then apply it to a chart with no Pillow on the consume side."""
    os.makedirs("output", exist_ok=True)

    # 1) Author the catalog (Pillow converts the PNGs to baked BMP blobs).
    cat = IconCatalog()
    cat.add_custom_entity_icon("person", _heart_png())
    cat.add_custom_entity_icon("vip", _crown_png())
    cat.add_custom_attribute_icon("priority", _crown_png())
    assert cat.validate() == []                      # blob integrity OK
    catalog_path = cat.export_catalog("output/icon_catalog.yaml")

    # 2) Consume it — IconCatalog.from_file needs no Pillow; default
    #    include='referenced' so only icons the chart actually uses are embedded.
    chart = ANXChart()
    chart.apply_icon_catalog(catalog_path)           # path, dict, or IconCatalog
    chart.add_entity_type(name="Person", icon_file="person")
    chart.add_attribute_class(name="Priority", type=AttributeType.TEXT, icon_file="priority")
    chart.add_icon(id="Alice", type="Person", attributes={"Priority": "high"})
    chart.add_icon(id="Bob", type="Person", icon="vip")
    return chart


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    print(f"wrote {build_chart().to_anx('output/custom_icons')}")
    print(f"wrote {build_catalog_demo().to_anx('output/custom_icons_catalog')}")

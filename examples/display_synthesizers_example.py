"""
display_synthesizers_example.py — derive attributes and labels from a template.

Two chart-level synthesizers under ``extra_cfg`` turn raw attribute values into
analyst-friendly presentation, declaratively:

- ``display_attribute`` renders one or more source attributes through a Python
  ``str.format_map`` template into a **synthesized text-sibling AttributeClass**.
  This is also the ANB v9 datetime canvas-render workaround: a hidden
  (``visible=False``) ``datetime`` AC plus a ``{d:%Y-%m-%d}`` template gives a
  visible, formatted date row (single date *or* a two-source range).
- ``display_label`` renders straight into the entity/link **label**, optionally
  scoped per entity/link ``type``.

Each entry has an explicit ``key`` (identity for config layering / lock /
delete) and optional ``kind`` (entity|link|both) + ``type`` filters. Scoping is
by structural metadata only — conditioning on attribute *values* is out of
scope; precompute a synthetic attribute upstream and use that.

Run from the examples/ directory:

    python display_synthesizers_example.py

Output: ./output/<name>.anx — open in i2 Analyst's Notebook. Everything is
fictional.
"""
from datetime import datetime
from pathlib import Path

from anxwritter import ANXChart


def build_attribute_combo() -> ANXChart:
    """Combine a count + a value into one text row via display_attribute."""
    chart = ANXChart()
    chart.add_attribute_class(name="tx_count", type="number", visible=False)
    chart.add_attribute_class(name="total", type="number", visible=False)
    chart.add_icon(id="acct_a", type="Account",
                   attributes={"tx_count": 12, "total": 100_000.50})
    chart.add_icon(id="acct_b", type="Account",
                   attributes={"tx_count": 3, "total": 4_250.00})
    chart.add_display_attribute(
        key="activity",
        attribute_name="Activity",
        template="{q}x  R$ {amt:,.2f}",
        decimal_separator=",", thousand_separator=".",   # BR: 100.000,50
        sources=[
            {"attribute": "tx_count", "alias": "q"},
            {"attribute": "total", "alias": "amt"},
        ],
    )
    return chart


def build_single_date() -> ANXChart:
    """The single-date canvas-render workaround (former date_attribute_displays)."""
    chart = ANXChart()
    chart.add_attribute_class(name="EventDate", type="datetime", visible=False)
    chart.add_icon(id="meet", type="Event",
                   attributes={"EventDate": datetime(2024, 1, 15)})
    chart.add_display_attribute(
        key="event_date",
        attribute_name="Event Date",
        template="{d:%Y-%m-%d}",
        sources=[{"attribute": "EventDate", "alias": "d"}],
    )
    return chart


def build_date_range() -> ANXChart:
    """A two-source date range, with an open end via per-source substitute."""
    chart = ANXChart()
    chart.add_attribute_class(name="start_dt", type="datetime", visible=False)
    chart.add_attribute_class(name="end_dt", type="datetime", visible=False)
    chart.add_icon(id="op_closed", type="Operation",
                   attributes={"start_dt": datetime(2024, 1, 15),
                               "end_dt": datetime(2024, 6, 30)})
    chart.add_icon(id="op_ongoing", type="Operation",
                   attributes={"start_dt": datetime(2024, 3, 1)})  # no end yet
    chart.add_display_attribute(
        key="period",
        attribute_name="Investigation Period",
        template="{s:%Y-%m-%d} - {e:%Y-%m-%d}",
        sources=[
            {"attribute": "start_dt", "alias": "s"},
            {"attribute": "end_dt", "alias": "e",
             "missing": "substitute", "placeholder": "ongoing"},
        ],
    )
    return chart


def build_label_per_type() -> ANXChart:
    """Per-type labels via display_label + a kind/type filter."""
    chart = ANXChart()
    chart.add_attribute_class(name="age", type="number")
    chart.add_attribute_class(name="cnpj", type="text")
    chart.add_icon(id="alice", type="Person", attributes={"age": 41})
    chart.add_icon(id="acme", type="Organization", attributes={"cnpj": "12.345.678/0001-90"})
    # Person label shows age; Organization label shows the CNPJ.
    chart.add_display_label(
        key="person_lbl", kind="entity", type="Person",
        template="Person ({age})", sources=[{"attribute": "age"}],
    )
    chart.add_display_label(
        key="org_lbl", kind="entity", type="Organization",
        template="Org {cnpj}", sources=[{"attribute": "cnpj"}],
    )
    return chart


# Smoke-test entry points (one .anx per builder).
BUILDERS = {
    "display_attribute_combo": build_attribute_combo,
    "display_single_date": build_single_date,
    "display_date_range": build_date_range,
    "display_label_per_type": build_label_per_type,
}


if __name__ == "__main__":
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    for name, builder in BUILDERS.items():
        path = builder().to_anx(str(out_dir / name))
        print(f"wrote {path}")

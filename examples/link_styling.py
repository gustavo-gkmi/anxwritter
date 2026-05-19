"""
link_styling.py — Data-driven link width and colour.

Builds a small money-flow chart where:
- link **width** scales with the transferred amount on a log curve
  (heavy-tailed money data — log compresses the high end so the small
  transfers are still visible);
- link **colour** is picked from a categorical lookup on the link's
  ``source_type`` attribute (Discovery / Informant / Intercept).

Run from the examples/ directory:

    python link_styling.py

Output: ./output/link_styling.anx — open in i2 Analyst's Notebook.

Everything is fictional. Amounts are illustrative.
"""
from pathlib import Path

from anxwritter import ANXChart


# Transfers — span four orders of magnitude so the log scale shows its value.
TRANSFERS = [
    ("acct_alex",   "acct_acme",  120.00, "Discovery"),
    ("acct_alex",   "acct_acme",  450.00, "Discovery"),
    ("acct_alex",   "acct_acme",  3_500.00, "Informant"),
    ("acct_acme",   "acct_jamie", 8_200.00, "Informant"),
    ("acct_acme",   "acct_morgan", 45_000.00, "Intercept"),
    ("acct_morgan", "acct_jamie", 320.00, "Discovery"),
    ("acct_jamie",  "acct_alex",  280_000.00, "Intercept"),
]


def build() -> ANXChart:
    """Construct the chart. Kept side-effect-free so the smoke test can import.

    The ``__name__ == '__main__'`` block at the bottom is the only place that
    writes a file to disk.
    """
    chart = ANXChart(settings={
        "chart": {"bg_color": 16777215, "rigorous": True},
        "view": {"time_bar": True},
        "grid": {"snap": True},
        "legend_cfg": {"show": True, "x": 50, "y": 50},
        "extra_cfg": {
            "arrange": "grid",
            "entity_auto_color": True,
            "styling": {
                "links": {
                    "intensity": {
                        "attribute": "Amount",
                        "scale": "log",
                        "domain": "robust",
                        "width": {"range": [1, 10]},
                        "legend": True,
                        "legend_count": 4,
                    },
                    "categorical": {
                        "attribute": "source_type",
                        "styles": {
                            "Discovery": {"line_color": "Green", "line_width": 2},
                            "Informant": {"line_color": "Orange"},
                            "Intercept": {"line_color": "Red", "line_width": 3},
                        },
                        "default": {"line_color": "Grey"},
                        "legend": True,
                    },
                },
            },
        },
    })

    chart.add_entity_type(name="Person", icon_file="adult")
    chart.add_entity_type(name="Bank Account", icon_file="cash")

    # Three suspects and four bank accounts.
    for pid, label in [
        ("alex",   "Alex Carter"),
        ("jamie",  "Jamie Rivera"),
        ("morgan", "Morgan Bennett"),
    ]:
        chart.add_icon(id=pid, type="Person", label=label)

    for aid, label in [
        ("acct_alex",   "Carter Personal"),
        ("acct_acme",   "Acme Operating"),
        ("acct_jamie",  "Rivera Personal"),
        ("acct_morgan", "Bennett Holdings"),
    ]:
        chart.add_icon(id=aid, type="Bank Account", label=label)

    # Ownership (no Amount attribute → fall through to defaults).
    for owner, acct in [
        ("alex",   "acct_alex"),
        ("jamie",  "acct_jamie"),
        ("morgan", "acct_morgan"),
    ]:
        chart.add_link(from_id=owner, to_id=acct, type="Owns", arrow="->")

    # Transfers — width scales with Amount, colour by source_type.
    for src, dst, amount, source in TRANSFERS:
        chart.add_link(
            from_id=src, to_id=dst,
            type="Transfers Money", arrow="->",
            attributes={"Amount": amount, "source_type": source},
        )

    # Explicit per-link override beats every data-driven rule.
    chart.add_link(
        from_id="morgan", to_id="alex",
        type="Knows",
        line_color="Black", line_width=1,
        attributes={"source_type": "Discovery"},  # ignored — explicit wins
    )
    return chart


if __name__ == "__main__":
    out = Path(__file__).parent / "output" / "link_styling.anx"
    out.parent.mkdir(exist_ok=True)
    build().to_anx(str(out))
    print(f"wrote {out}")

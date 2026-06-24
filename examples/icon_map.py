"""
icon_map.py — Map entity attribute values / ids to icons.

``extra_cfg.icon_map`` sets each matching entity's icon at build time, the same
way ``geo_map`` resolves coordinates — you keep one central lookup instead of
setting ``icon=`` on every entity by hand.

This chart shows a set of bank accounts whose icon is chosen from a
``bank_code`` attribute, plus one VIP account pinned to a special icon by its
id. Precedence (highest wins): explicit per-entity ``icon`` > id rule > typed
attribute rule > untyped attribute rule.

Run from the examples/ directory:

    python icon_map.py

Output: ./output/icon_map.anx — open in i2 Analyst's Notebook.

Everything is fictional. Icon keys ('cash', 'bank', …) are ANB built-ins.
"""
from pathlib import Path

from anxwritter import ANXChart


# Accounts: (id, label, bank_code). Code 999 is unrecognised → falls to the
# rule default; the last account has no bank_code at all → default_when_absent.
ACCOUNTS = [
    ("acct_1", "Carter — Itaú",      "341"),
    ("acct_2", "Acme — Bradesco",    "237"),
    ("acct_3", "Rivera — Santander", "033"),
    ("acct_4", "Bennett — Unknown",  "999"),   # unrecognised → generic
    ("acct_5", "Petty cash",         None),    # absent → not-a-bank icon
]


def build() -> ANXChart:
    """Construct the chart. Side-effect-free so the smoke test can import it."""
    chart = ANXChart(settings={
        "chart": {"bg_color": 16777215},
        "extra_cfg": {
            "arrange": "grid",
            "icon_map": {
                "rules": [
                    # Attribute rule, scoped to Bank Account entities.
                    {
                        "match": "attribute",
                        "attribute_name": "bank_code",
                        "type": "Bank Account",
                        "mapping": {
                            "341": "money",     # Itaú
                            "237": "money",     # Bradesco
                            "033": "money",     # Santander
                        },
                        "default": "question",          # known code, unrecognised value
                        "default_when_absent": "box",   # no bank_code at all
                    },
                    # id rule — one account gets a bespoke icon. id beats the
                    # attribute rule above, so acct_1 shows 'star' not 'money'.
                    {
                        "match": "id",
                        "mapping": {"acct_1": "star"},
                    },
                ]
            },
        },
    })

    chart.add_entity_type(name="Bank Account", icon_file="box")

    for aid, label, code in ACCOUNTS:
        attrs = {"bank_code": code} if code is not None else {}
        chart.add_icon(id=aid, type="Bank Account", label=label, attributes=attrs)

    # Explicit per-entity icon always wins — even over the id rule.
    chart.add_icon(
        id="acct_1b", type="Bank Account", label="Carter — manual",
        icon="reddot", attributes={"bank_code": "341"},
    )
    return chart


if __name__ == "__main__":
    out = Path(__file__).parent / "output" / "icon_map.anx"
    out.parent.mkdir(exist_ok=True)
    build().to_anx(str(out))
    print(f"wrote {out}")

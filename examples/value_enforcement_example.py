"""Org-level value enforcement (1.17.0) — runnable demo.

Declares three layers of rules:

- ``AttributeClass.enforce`` — wide value rules on attributes by name.
- ``EntityType.enforce`` — per-type id_pattern + required_attributes.
- Top-level ``validators[]`` — per-(type, attribute) flexible rules,
  identity = synthesized scope key ``E::Person::CPF`` etc.

Then feeds the chart a mix of compliant and non-compliant rows, catches
the ANXValidationError, and prints the smart-truncated error message
so you can see the grouping/truncation in action.

Run:

    uv run python examples/value_enforcement_example.py
"""
from __future__ import annotations

from anxwritter import ANXChart, ANXValidationError


def build_chart() -> ANXChart:
    chart = ANXChart()

    chart.apply_config({
        "entity_types": [
            {
                "name": "Person",
                "icon_file": "person",
                "color": "Blue",
                "enforce": {
                    "id_pattern": r"^\d{11}$",
                    "id_pattern_description": "CPF — 11 digits, no punctuation",
                    "required_attributes": ["Name", "CPF"],
                },
            },
            {
                "name": "Vehicle",
                "icon_file": "car",
                "enforce": {
                    "id_pattern": r"^[A-Z]{3}-?\d{4}$",
                    "id_pattern_description": "BR plate (3 letters, optional dash, 4 digits)",
                },
            },
        ],
        "link_types": [
            {
                "name": "Transfer",
                "color": "Green",
                "enforce": {"required_attributes": ["Amount", "Currency"]},
            },
        ],
        "attribute_classes": [
            {
                "name": "CPF",
                "type": "text",
                "enforce": {
                    "pattern": r"^\d{11}$",
                    "description": "CPF — digits only, no punctuation",
                },
            },
            {
                "name": "Status",
                "type": "text",
                "enforce": {"allowed_values": ["Active", "Inactive", "Suspended"]},
            },
            {"name": "Amount", "type": "number"},
            {
                "name": "Currency",
                "type": "text",
                "enforce": {"allowed_values": ["BRL", "USD", "EUR"]},
            },
            {"name": "Name", "type": "text"},
        ],
        "validators": [
            {
                "entity_type": "Person",
                "attribute": "CPF",
                "pattern": r"^[1-9]\d{10}$",
                "description": "CPF must not start with 0 (would be a placeholder/test value)",
            },
        ],
    }, source_name="org.yaml")

    # ── Good row ──
    chart.add_icon(
        id="12345678901",
        type="Person",
        attributes={"Name": "Alice", "CPF": "12345678901", "Status": "Active"},
    )

    # ── Bad rows — every layer fires for at least one of these ──
    # 1. Bad id format, missing Name, bad CPF value, bad Status value
    chart.add_icon(
        id="not-a-cpf",
        type="Person",
        attributes={"CPF": "123.456.789-01", "Status": "active"},
    )

    # 2. CPF starts with 0 — passes AC pattern, fails the top-level validator
    chart.add_icon(
        id="01234567890",
        type="Person",
        attributes={"Name": "Bob", "CPF": "01234567890", "Status": "Active"},
    )

    # 3. Vehicle with bad plate
    chart.add_icon(id="ABCD-1234", type="Vehicle")

    # 4. Transfer link missing required attributes
    chart.add_link(
        from_id="12345678901", to_id="01234567890", type="Transfer",
        attributes={"Currency": "JPY"},  # missing Amount, currency not allowed
    )

    return chart


def main() -> None:
    chart = build_chart()

    errors = chart.validate()
    print(f"validate() returned {len(errors)} error(s).\n")

    # The structured list is the stable contract. Consumers should match
    # on dict keys, not parse str(exc) — but the formatted string is the
    # easy way to see the smart-truncated grouping.
    try:
        chart.to_xml()
    except ANXValidationError as exc:
        print("─" * 78)
        print("ANXValidationError formatted message:")
        print("─" * 78)
        print(exc)
        print("─" * 78)
        print()
        print("Programmatic access — first error dict in full:")
        first = exc.errors[0]
        for k, v in first.items():
            print(f"  {k}: {v!r}")


if __name__ == "__main__":
    main()

"""Example: ``extra_cfg.display_templates`` — multi-attribute synthesiser
that renders a formatted string from N source attribute values and emits
the result as either a synthesized text-sibling AttributeClass
(``target='attribute'``) or as the entity/link label (``target='label'``).

Run::

    uv run python examples/display_templates_example.py

Four charts are emitted into ``output/``:

1. ``display_template_sibling_ac.anx``: target='attribute'. Transfer links
   declare a 1-row summary AC ``Activity`` synthesised from two source ACs
   (``transaction_count`` + ``total_value``). The source ACs are hidden
   (``visible=False``) so the canvas shows only the formatted sibling.
2. ``display_template_label.anx``: target='label'. Same data, but the
   formatted string goes onto the link's label instead of an attribute row.
   One link carries an explicit ``label='manual annotation'`` to demonstrate
   that ``override_existing=False`` (default) preserves manual labels.
3. ``display_template_br_dates.anx``: BR decimal/thousand separators plus
   a datetime source rendered via ``{when:%d/%m/%Y}``. Shows
   ``"em DD/MM/YYYY · R$ 100.000,50"`` per entity.
4. ``display_template_mixed_targets.anx``: one chart with one
   target='attribute' entry AND one target='label' entry — both run
   independently on the same data.

All four charts also keep the source ACs alive in the properties panel /
sort / filter (those work off the original typed values). Only the
canvas-visible chrome is the rendered template output.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from anxwritter import (
    ANXChart,
    AttributeClass,
    DisplayTemplate,
    DisplaySource,
)


OUTPUT_DIR = Path(__file__).parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


def _add_transfer_dataset(chart: ANXChart, *, label_overrides=None):
    """Add a small money-flow dataset shared by the first two examples."""
    chart.add_icon(id='Alice', type='Person')
    chart.add_icon(id='Bob', type='Person')
    chart.add_icon(id='Carol', type='Person')
    chart.add_icon(id='Dave', type='Person')

    label_overrides = label_overrides or {}

    chart.add_link(
        from_id='Alice', to_id='Bob', type='Transfer',
        attributes={'transaction_count': 5, 'total_value': 12345.67},
        label=label_overrides.get(('Alice', 'Bob'), None),
    )
    chart.add_link(
        from_id='Alice', to_id='Carol', type='Transfer',
        attributes={'transaction_count': 18, 'total_value': 99999.99},
        label=label_overrides.get(('Alice', 'Carol'), None),
    )
    chart.add_link(
        from_id='Bob', to_id='Dave', type='Transfer',
        attributes={'transaction_count': 2, 'total_value': 75.00},
        label=label_overrides.get(('Bob', 'Dave'), None),
    )


def chart_sibling_ac() -> ANXChart:
    """target='attribute' — synthesises an Activity AC per link."""
    chart = ANXChart()
    chart.add_attribute_class(AttributeClass(
        name='transaction_count', type='number', visible=False,
    ))
    chart.add_attribute_class(AttributeClass(
        name='total_value', type='number', visible=False,
    ))
    chart.add_display_template(DisplayTemplate(
        target='attribute',
        attribute_name='Activity',
        template='{qty}x · total R$ {amount:,.2f}',
        sources=[
            DisplaySource(attribute='transaction_count', alias='qty'),
            DisplaySource(attribute='total_value', alias='amount'),
        ],
    ))
    _add_transfer_dataset(chart)
    return chart


def chart_label() -> ANXChart:
    """target='label' — formatted string lives on each link's label.

    Default ``override_existing=False`` preserves manually-annotated labels.
    """
    chart = ANXChart()
    chart.add_attribute_class(AttributeClass(
        name='transaction_count', type='number',
    ))
    chart.add_attribute_class(AttributeClass(
        name='total_value', type='number',
    ))
    chart.add_display_template(DisplayTemplate(
        target='label',
        template='{qty}x · R$ {amount:,.2f}',
        sources=[
            DisplaySource(attribute='transaction_count', alias='qty'),
            DisplaySource(attribute='total_value', alias='amount'),
        ],
    ))
    _add_transfer_dataset(chart, label_overrides={
        ('Alice', 'Carol'): 'flagged for review',
    })
    return chart


def chart_br_dates() -> ANXChart:
    """BR separators + datetime source rendered via ``{when:%d/%m/%Y}``."""
    chart = ANXChart()
    chart.add_attribute_class(AttributeClass(
        name='when', type='datetime', visible=False,
    ))
    chart.add_attribute_class(AttributeClass(
        name='amount', type='number', visible=False,
    ))
    chart.add_display_template(DisplayTemplate(
        target='attribute',
        attribute_name='Movimento',
        template='em {when:%d/%m/%Y} · R$ {amount:,.2f}',
        decimal_separator=',',
        thousand_separator='.',
        sources=[
            DisplaySource(attribute='when'),
            DisplaySource(attribute='amount'),
        ],
    ))
    chart.add_icon(id='Conta A', type='Bank Account', attributes={
        'when': datetime(2025, 3, 15),
        'amount': 100000.50,
    })
    chart.add_icon(id='Conta B', type='Bank Account', attributes={
        'when': datetime(2025, 4, 1),
        'amount': 87.42,
    })
    chart.add_icon(id='Conta C', type='Bank Account', attributes={
        'when': datetime(2025, 4, 22),
        'amount': 7500000.00,
    })
    return chart


def chart_mixed_targets() -> ANXChart:
    """One chart, two display_templates entries — one writes an attribute,
    the other writes the label. They run independently on the same data.

    Source ACs declare ``visible=False`` because the target='attribute'
    entry requires it. The target='label' entry doesn't add a visibility
    constraint — it can read from any AC regardless of visibility.
    """
    chart = ANXChart()
    chart.add_attribute_class(AttributeClass(
        name='transaction_count', type='number', visible=False,
    ))
    chart.add_attribute_class(AttributeClass(
        name='total_value', type='number', visible=False,
    ))
    chart.add_display_template(DisplayTemplate(
        target='attribute',
        attribute_name='Summary',
        template='{qty}x R$ {amount:,.2f}',
        sources=[
            DisplaySource(attribute='transaction_count', alias='qty'),
            DisplaySource(attribute='total_value', alias='amount'),
        ],
    ))
    chart.add_display_template(DisplayTemplate(
        target='label',
        template='R$ {amount:,.2f}',
        sources=[DisplaySource(attribute='total_value', alias='amount')],
    ))
    _add_transfer_dataset(chart)
    return chart


def main():
    chart_sibling_ac().to_anx(str(OUTPUT_DIR / 'display_template_sibling_ac'))
    chart_label().to_anx(str(OUTPUT_DIR / 'display_template_label'))
    chart_br_dates().to_anx(str(OUTPUT_DIR / 'display_template_br_dates'))
    chart_mixed_targets().to_anx(str(OUTPUT_DIR / 'display_template_mixed_targets'))
    print(f"Wrote 4 charts to {OUTPUT_DIR.resolve()}")


if __name__ == '__main__':
    main()

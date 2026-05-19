"""Example: ``extra_cfg.date_attribute_displays`` — the datetime → text
sibling synthesizer that works around ANB v9's failure to render datetime
attribute values on the canvas.

Run::

    uv run python examples/date_attribute_displays_example.py

Three charts are emitted into ``output/``:

1. ``single_date_workaround.anx``: one datetime AC (``event_date``) +
   one ``DateAttributeDisplay(start='event_date')`` → canvas shows the
   formatted date via a synthesised text sibling.
2. ``range_period.anx``: two datetime ACs (``investigation_start``,
   ``investigation_end``) + a range display → canvas shows
   ``"YYYY-MM-DD - YYYY-MM-DD"`` per entity.
3. ``range_ongoing.anx``: range display with ``missing='substitute'`` and
   ``end_placeholder='ongoing'`` — open investigations (no end date yet)
   render as ``"YYYY-MM-DD - ongoing"``.

All three charts also keep the source datetime ACs alive in the properties
panel / time wheel / sort / filter (those work off the original ``AttTime``
values). Only the canvas-visible chrome is the synthesised text sibling.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from anxwritter import (
    ANXChart, AttributeClass, DateAttributeDisplay, Font,
)


OUT_DIR = Path(__file__).parent.parent / 'output'


def build_single_date() -> ANXChart:
    """Single datetime AC + canvas display sibling."""
    chart = ANXChart()
    chart.add_attribute_class(
        name='event_date',
        type='datetime',
        visible=False,  # required: ANB v9 won't render AttTime on canvas
    )
    chart.add_date_attribute_display(
        start='event_date',
        format='%d/%m/%Y',
        attribute_class=AttributeClass(
            prefix='Event: ',
            font=Font(italic=True),
        ),
    )

    chart.add_icon(id='Alice', type='Person',
                   attributes={'event_date': datetime(2024, 1, 15)})
    chart.add_icon(id='Bob', type='Person',
                   attributes={'event_date': datetime(2024, 3, 7)})
    chart.add_link(from_id='Alice', to_id='Bob', type='Call',
                   attributes={'event_date': datetime(2024, 1, 20)})
    return chart


def build_range_period() -> ANXChart:
    """Two datetime ACs + a range display covering both bounds."""
    chart = ANXChart()
    chart.add_attribute_class(name='investigation_start', type='datetime', visible=False)
    chart.add_attribute_class(name='investigation_end', type='datetime', visible=False)
    chart.add_date_attribute_display(
        start='investigation_start',
        end='investigation_end',
        name='Period',
        format='%Y-%m-%d',
        separator=' – ',
    )

    chart.add_icon(id='Case A', type='Event',
                   attributes={'investigation_start': datetime(2023, 6, 1),
                               'investigation_end': datetime(2023, 12, 31)})
    chart.add_icon(id='Case B', type='Event',
                   attributes={'investigation_start': datetime(2024, 1, 10),
                               'investigation_end': datetime(2024, 5, 14)})
    return chart


def build_range_ongoing() -> ANXChart:
    """Range display with substitute policy for open-ended investigations."""
    chart = ANXChart()
    chart.add_attribute_class(name='investigation_start', type='datetime', visible=False)
    chart.add_attribute_class(name='investigation_end', type='datetime', visible=False)
    chart.add_date_attribute_display(
        start='investigation_start',
        end='investigation_end',
        name='Period',
        format='%Y-%m-%d',
        separator=' – ',
        missing='substitute',
        end_placeholder='ongoing',
    )

    chart.add_icon(id='Closed', type='Event',
                   attributes={'investigation_start': datetime(2023, 6, 1),
                               'investigation_end': datetime(2023, 12, 31)})
    chart.add_icon(id='Open', type='Event',
                   attributes={'investigation_start': datetime(2024, 1, 10)})
    return chart


BUILDERS = {
    'single_date_workaround': build_single_date,
    'range_period': build_range_period,
    'range_ongoing': build_range_ongoing,
}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for name, builder in BUILDERS.items():
        out = builder().to_anx(OUT_DIR / name)
        print(f"wrote {out}")


if __name__ == '__main__':
    main()

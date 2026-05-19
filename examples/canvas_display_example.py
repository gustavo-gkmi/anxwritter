"""canvas_display: render datetime attribute values on the canvas in ANB v9.

ANB v9 does not render datetime attribute values on the canvas after .anx
import. The value loads correctly — it shows up in the properties panel and
works for time-wheel / sort / filter — but on the canvas, only the
surrounding chrome (symbol, prefix, suffix, class name) appears next to each
entity or link. The actual date is blank.

The ``canvas_display`` flag on a datetime AttributeClass is the workaround.
anxwritter emits a paired text sibling AttributeClass and a formatted-string
sibling attribute on every entity/link that uses the parent. The original
datetime is still loaded by ANB, so the properties panel and time-wheel keep
working; the canvas renders the formatted text sibling.

This script emits two charts side by side:

    output/canvas_display_baseline.anx — datetime AC with no canvas_display.
                                         Date appears in the properties
                                         panel, NOT on the canvas.
    output/canvas_display_workaround.anx — same data, canvas_display enabled.
                                           Date renders on the canvas via
                                           the text sibling.

Open both in ANB to compare.
"""
from datetime import datetime
from pathlib import Path

from anxwritter import (
    ANXChart, AttributeClass, CanvasDisplay, Font,
)


def _populate(chart: ANXChart) -> None:
    chart.add_icon(
        id='Alice', type='Person',
        attributes={'EventDate': datetime(2024, 1, 15, 14, 30)},
    )
    chart.add_icon(
        id='Bob', type='Person',
        attributes={'EventDate': datetime(2024, 2, 3, 9, 0)},
    )
    chart.add_link(
        from_id='Alice', to_id='Bob', type='Call', arrow='->',
        attributes={'CallTime': datetime(2024, 2, 3, 9, 0)},
    )


def build_baseline() -> ANXChart:
    """Plain datetime AC — ANB v9 will load the values but not render them."""
    chart = ANXChart()
    _populate(chart)
    # datetime AC with visible=False hides the chrome that would otherwise
    # render with a blank value. ANB still holds the value internally for
    # time-wheel / sort / filter.
    chart.add_attribute_class(
        name='EventDate', type='datetime', visible=False,
    )
    chart.add_attribute_class(
        name='CallTime', type='datetime', visible=False,
    )
    return chart


def build_workaround() -> ANXChart:
    """Same data — canvas_display emits a paired text sibling that renders."""
    chart = ANXChart()
    _populate(chart)
    # Entity datetime: default ISO format ('%Y-%m-%d').
    chart.add_attribute_class(
        name='EventDate', type='datetime', visible=False,
        canvas_display=True,
    )
    # Link datetime: custom format + styled sibling.
    chart.add_attribute_class(
        name='CallTime', type='datetime', visible=False,
        canvas_display=CanvasDisplay(
            format='%d/%m/%Y %H:%M',
            suffix=' (display)',
            attribute_class=AttributeClass(
                prefix='Call: ',
                show_symbol=True,
                font=Font(italic=True),
            ),
        ),
    )
    return chart


if __name__ == '__main__':
    out_dir = Path('output')
    out_dir.mkdir(exist_ok=True)
    baseline = build_baseline().to_anx(out_dir / 'canvas_display_baseline')
    workaround = build_workaround().to_anx(out_dir / 'canvas_display_workaround')
    print(f'Wrote {baseline}')
    print(f'Wrote {workaround}')
    print('Open both in ANB to compare canvas rendering.')

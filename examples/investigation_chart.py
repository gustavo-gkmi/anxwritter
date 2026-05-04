"""
investigation_chart.py — Build a sample investigation chart from Python.

Builds the same fictional case as `data.yaml` / `data.json`, plus extras that
are easier to express in code than in config: evidence cards on entities and
links, manual entity placement, a chart-level summary, and a legend.

Run from the examples/ directory:

    python investigation_chart.py

Output: ./output/investigation_chart.anx — open in i2 Analyst's Notebook.

Everything is fictional. US phone numbers use the (555) 0100–0199 range
that the NANP reserves for fiction.
"""
from pathlib import Path

from anxwritter import (
    ANXChart,
    Icon, Link, Card,
    AttributeClass, AttributeType,
    EntityType, LinkType,
    Strength, DotStyle,
    LegendItem, LegendItemType,
    GradeCollection, StrengthCollection,
    Settings, ChartCfg, ViewCfg, GridCfg, LegendCfg, SummaryCfg, ExtraCfg,
    Font, Show,
)


def build() -> ANXChart:
    chart = ANXChart(settings=Settings(
        chart=ChartCfg(bg_color=16777215, rigorous=True),
        view=ViewCfg(time_bar=True),
        grid=GridCfg(snap=True, visible=False),
        summary=SummaryCfg(
            title='Operation Northstar — Network Analysis',
            subject='Fictional fraud investigation example',
            author='anxwritter examples',
            keywords='example, fraud, link analysis',
            category='Sample',
            custom_properties=[
                {'name': 'Case', 'value': 'EX-2026-001'},
                {'name': 'Classification', 'value': 'PUBLIC SAMPLE'},
            ],
        ),
        legend_cfg=LegendCfg(
            show=True, x=50, y=50, arrange='wide',
            font=Font(name='Segoe UI', size=10, bold=True),
        ),
        extra_cfg=ExtraCfg(
            entity_auto_color=True,
            link_match_entity_color=True,
            arrange='grid',
            link_arc_offset=25,
        ),
    ))

    # ── Type registries ────────────────────────────────────────────
    chart.add_entity_type(name='Person',       icon_file='adult')
    chart.add_entity_type(name='Company',      icon_file='building')
    chart.add_entity_type(name='Vehicle',      icon_file='car')
    chart.add_entity_type(name='Bank Account', icon_file='cash')

    chart.add_link_type(name='Calls',           color=16711680)
    chart.add_link_type(name='Transfers Money', color=32768)
    chart.add_link_type(name='Owns',            color=128)
    chart.add_link_type(name='Employs',         color=8388736)
    chart.add_link_type(name='Associated With', color=8421504)

    # ── Attribute classes ──────────────────────────────────────────
    chart.add_attribute_class(name='Phone Number', type=AttributeType.TEXT,
                              prefix='Tel: ', icon_file='phone')
    chart.add_attribute_class(name='Balance',      type=AttributeType.NUMBER,
                              prefix='$', decimal_places=2, icon_file='cash')
    chart.add_attribute_class(name='Address',      type=AttributeType.TEXT,
                              icon_file='house')
    chart.add_attribute_class(name='License Plate', type=AttributeType.TEXT,
                              prefix='Plate: ', icon_file='car')
    chart.add_attribute_class(name='Account ID',   type=AttributeType.TEXT,
                              prefix='Acct: ')
    chart.add_attribute_class(name='Active',       type=AttributeType.FLAG,
                              show_if_set=True, show_class_name=True)

    # ── Confidence levels and grading scales ───────────────────────
    chart.strengths = StrengthCollection(
        default='Confirmed',
        items=[
            Strength(name='Confirmed', dot_style=DotStyle.SOLID),
            Strength(name='Probable',  dot_style=DotStyle.DASHED),
            Strength(name='Possible',  dot_style=DotStyle.DOTTED),
        ],
    )
    chart.grades_one = GradeCollection(
        default='Usually reliable',
        items=[
            'Always reliable', 'Usually reliable', 'Fairly reliable',
            'Not usually reliable', 'Unreliable',
        ],
    )
    chart.grades_two = GradeCollection(
        default='Probably true',
        items=['Confirmed', 'Probably true', 'Possibly true', 'Doubtful'],
    )
    chart.source_types = ['Witness', 'Informant', 'Officer',
                          'Intelligence', 'Discovery']

    # ── Persons ────────────────────────────────────────────────────
    chart.add_icon(
        id='alex_carter', type='Person', label='Alex Carter',
        attributes={
            'Phone Number': '(555) 010-0123',
            'Address': '142 Maple Ave, Springfield',
            'Active': True,
        },
        cards=[
            Card(summary='Initial sighting',
                 date='2026-02-10', time='09:00:00',
                 description='Subject observed entering Acme Holdings.',
                 source_ref='RPT-001', source_type='Officer',
                 grade_one=1, grade_two=0),
            Card(summary='Phone activity spike',
                 date='2026-02-14', time='09:30:00',
                 source_ref='TEL-002', source_type='Intelligence',
                 grade_one=0, grade_two=1),
        ],
    )
    chart.add_icon(
        id='jamie_rivera', type='Person', label='Jamie Rivera',
        attributes={
            'Phone Number': '(555) 010-0145',
            'Address': '88 Oak St, Springfield',
            'Active': True,
        },
    )
    chart.add_icon(
        id='morgan_bennett', type='Person', label='Morgan Bennett',
        attributes={'Phone Number': '(555) 010-0167', 'Active': False},
    )

    # ── Companies ──────────────────────────────────────────────────
    chart.add_icon(
        id='acme_holdings', type='Company', label='Acme Holdings LLC',
        attributes={'Address': '500 Industrial Blvd, Springfield'},
    )
    chart.add_icon(
        id='pinecrest_logistics', type='Company',
        label='Pinecrest Logistics Inc',
    )

    # ── Vehicle ────────────────────────────────────────────────────
    chart.add_icon(
        id='vehicle_suv', type='Vehicle', label='Black SUV',
        attributes={'License Plate': 'ABC-1234'},
    )

    # ── Bank accounts ──────────────────────────────────────────────
    chart.add_icon(
        id='account_carter', type='Bank Account', label='Carter Personal',
        attributes={
            'Account ID': 'XXXX-XXXX-1234',
            'Balance': 12500.50,
        },
    )
    chart.add_icon(
        id='account_acme', type='Bank Account', label='Acme Operating',
        attributes={
            'Account ID': 'XXXX-XXXX-5678',
            'Balance': 350000.00,
        },
    )

    # ── Links ──────────────────────────────────────────────────────
    chart.add_link(
        from_id='alex_carter', to_id='jamie_rivera',
        type='Calls', label='4 calls',
        date='2026-02-14', time='09:30:00',
        strength='Confirmed',
    )
    chart.add_link(
        from_id='alex_carter', to_id='morgan_bennett',
        type='Calls', label='1 call',
        date='2026-02-15',
        strength='Possible',
    )

    # The key transfer link — fully graded with a card attached
    chart.add_link(
        from_id='account_carter', to_id='account_acme',
        type='Transfers Money', arrow='->', label='$50,000',
        date='2026-02-20', time='14:00:00',
        strength='Confirmed',
        grade_one=0, grade_two=0,
        source_ref='BANK-001', source_type='Discovery',
        link_id='transfer_001',
        cards=[
            Card(summary='Bank-flagged transfer',
                 date='2026-02-20', time='14:05:00',
                 description='Outbound wire flagged by AML system.',
                 source_ref='BANK-001', source_type='Discovery'),
        ],
    )

    chart.add_link(from_id='alex_carter', to_id='vehicle_suv',
                   type='Owns', arrow='->', strength='Confirmed')
    chart.add_link(from_id='alex_carter', to_id='account_carter',
                   type='Owns', arrow='->', strength='Confirmed')
    chart.add_link(from_id='acme_holdings', to_id='account_acme',
                   type='Owns', arrow='->', strength='Confirmed')
    chart.add_link(from_id='pinecrest_logistics', to_id='jamie_rivera',
                   type='Employs', arrow='->', label='since 2024',
                   strength='Confirmed')
    chart.add_link(from_id='acme_holdings', to_id='pinecrest_logistics',
                   type='Associated With', label='shared director',
                   strength='Probable')

    # ── Legend ─────────────────────────────────────────────────────
    chart.add_legend_item(name='Person',  item_type=LegendItemType.ICON,
                          image_name='adult')
    chart.add_legend_item(name='Company', item_type=LegendItemType.ICON,
                          image_name='building')
    chart.add_legend_item(name='Calls',   item_type=LegendItemType.LINK,
                          color=16711680, line_width=1, arrows='->')
    chart.add_legend_item(name='Transfers Money', item_type=LegendItemType.LINK,
                          color=32768, line_width=2, arrows='->')

    return chart


if __name__ == '__main__':
    out_dir = Path('output')
    out_dir.mkdir(exist_ok=True)
    chart = build()
    path = chart.to_anx(out_dir / 'investigation_chart')
    print(f'Wrote {path}')

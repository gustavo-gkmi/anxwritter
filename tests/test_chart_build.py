"""Tests for Chart → XML structure via xpath assertions."""

import xml.etree.ElementTree as ET

import pytest

from anxwritter import (
    ANXChart, Card, DotStyle, AttributeClass, AttributeType, Strength, LegendItem,
    Icon, Link, ThemeLine, EventFrame, TimeZone,
    SemanticEntity, EntityType,
    GradeCollection, StrengthCollection,
)


def _parse_xml(chart: ANXChart) -> ET.Element:
    """Build XML from chart and return root element."""
    xml_str = chart.to_xml()
    return ET.fromstring(xml_str)


class TestBasicStructure:
    def test_root_is_chart(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        root = _parse_xml(c)
        assert root.tag == 'Chart'

    def test_entity_type_not_auto_created(self):
        """EntityType is only created when explicitly pre-registered."""
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        root = _parse_xml(c)
        et_coll = root.find('.//EntityTypeCollection')
        assert et_coll is None

    def test_entity_type_created_when_preregistered(self):
        c = ANXChart()
        c.add_entity_type(name='Person', icon_file='person')
        c.add_icon(id='A', type='Person')
        root = _parse_xml(c)
        et_coll = root.find('.//EntityTypeCollection')
        assert et_coll is not None
        types = [et.get('Name') for et in et_coll.findall('EntityType')]
        assert 'Person' in types

    def test_chart_item_created(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        root = _parse_xml(c)
        ci_coll = root.find('.//ChartItemCollection')
        assert ci_coll is not None
        items = ci_coll.findall('ChartItem')
        assert len(items) >= 1

    def test_link_no_connection_by_default(self):
        """Links without connection style fields don't generate ConnectionCollection."""
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        c.add_icon(id='B', type='Person')
        c.add_link(from_id='A', to_id='B', type='Call')
        root = _parse_xml(c)
        conn_coll = root.find('.//ConnectionCollection')
        assert conn_coll is None

    def test_link_with_multiplicity_creates_connection(self):
        """Links with connection style fields generate shared Connections."""
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        c.add_icon(id='B', type='Person')
        c.add_link(from_id='A', to_id='B', type='Call', multiplicity='MultiplicityMultiple')
        root = _parse_xml(c)
        conn_coll = root.find('.//ConnectionCollection')
        assert conn_coll is not None
        conns = conn_coll.findall('Connection')
        assert len(conns) == 1


class TestEntityRepresentations:
    def test_icon_representation(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        root = _parse_xml(c)
        items = root.findall('.//ChartItem')
        assert len(items) >= 1

    def test_box_representation(self):
        c = ANXChart()
        c.add_box(id='B', type='Org', width=150, height=100)
        root = _parse_xml(c)
        items = root.findall('.//ChartItem')
        assert len(items) >= 1

    def test_multiple_representations(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        c.add_box(id='B', type='Org')
        c.add_circle(id='C', type='Event')
        root = _parse_xml(c)
        items = root.findall('.//ChartItem')
        assert len(items) >= 3


class TestAttributes:
    def test_attribute_class_created(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'phone': '555'})
        root = _parse_xml(c)
        ac_coll = root.find('.//AttributeClassCollection')
        assert ac_coll is not None
        names = [ac.get('Name') for ac in ac_coll.findall('AttributeClass')]
        assert 'phone' in names


class TestSettings:
    def test_bg_color(self):
        c = ANXChart(settings={'chart': {'bg_color': 8421504}})
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        assert root.get('BackColour') == '8421504'

    def test_time_bar_visible(self):
        c = ANXChart(settings={'view': {'time_bar': True}})
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        assert root.get('TimeBarVisible') == 'true'

    def test_snap_to_grid(self):
        c = ANXChart(settings={'grid': {'snap': True}})
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        assert root.get('SnapToGrid') == 'true'


class TestDateTimeFormatAcceptance:
    """Phase 4 (#12): validation accepts the same date/time formats the builder accepts."""

    def test_dd_mm_yyyy_date_builds(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person', date='15/01/2024')
        c.to_xml()  # validates and builds; raises if rejected

    def test_yyyymmdd_compact_date_builds(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person', date='20240115')
        c.to_xml()

    def test_us_date_format_rejected(self):
        from anxwritter.errors import ANXValidationError
        c = ANXChart()
        c.add_icon(id='A', type='Person', date='01/15/2024')
        try:
            c.to_xml()
            assert False, "should have raised ANXValidationError"
        except ANXValidationError:
            pass

    def test_hh_mm_time_builds(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person', date='2024-01-15', time='14:30')
        c.to_xml()

    def test_12_hour_time_builds(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person', date='2024-01-15', time='2:30 PM')
        c.to_xml()


class TestToAnx:
    def test_writes_file(self, tmp_path):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        out = c.to_anx(str(tmp_path / 'test'))
        assert out.endswith('.anx')
        import os
        assert os.path.isfile(out)

    def test_auto_extension(self, tmp_path):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        out = c.to_anx(str(tmp_path / 'test'))
        assert out.endswith('.anx')

    def test_explicit_extension(self, tmp_path):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        out = c.to_anx(str(tmp_path / 'test.anx'))
        assert out.endswith('.anx')
        assert not out.endswith('.anx.anx')


# ── Entity fields in XML ─────────────────────────────────────────────────────

class TestEntityFieldsInXML:
    def test_label_defaults_to_id(self):
        c = ANXChart()
        c.add_icon(id='MyId', type='T')
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('Label') == 'MyId'
        entity = root.find('.//Entity')
        assert entity.get('LabelIsIdentity') == 'true'

    def test_explicit_label(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', label='Custom')
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('Label') == 'Custom'
        entity = root.find('.//Entity')
        assert entity.get('LabelIsIdentity') == 'false'

    def test_date_time_in_xml(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', date='2024-01-15', time='14:30:00')
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('DateSet') == 'true'
        assert ci.get('TimeSet') == 'true'
        assert '2024-01-15' in ci.get('DateTime', '')

    def test_description_in_xml(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', description='Hello world')
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('Description') == 'Hello world'

    def test_manual_position(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', x=100, y=200)
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('XPosition') == '100'
        end = root.find('.//End')
        assert end.get('Y') == '200'


# ── Entity type-specific fields ──────────────────────────────────────────────

class TestEntityTypeSpecificFields:
    def test_box_width_height(self):
        c = ANXChart()
        c.add_box(id='B', type='T', width=200, height=100)
        root = _parse_xml(c)
        bs = root.find('.//BoxStyle')
        assert bs is not None
        box = root.find('.//Box')
        assert box.get('Width') == '200'
        assert box.get('Height') == '100'

    def test_box_depth(self):
        c = ANXChart()
        c.add_box(id='B', type='T', depth=10)
        root = _parse_xml(c)
        box = root.find('.//Box')
        assert box.get('Depth') == '10'

    def test_circle_diameter(self):
        c = ANXChart()
        c.add_circle(id='C', type='T', diameter=120)
        root = _parse_xml(c)
        cs = root.find('.//CircleStyle')
        assert cs is not None
        # diameter is divided by 100 for XML
        assert cs.get('Diameter') == '1.2'

    def test_circle_autosize(self):
        c = ANXChart()
        c.add_circle(id='C', type='T', autosize=True)
        root = _parse_xml(c)
        cs = root.find('.//CircleStyle')
        assert cs.get('Autosize') == 'true'

    def test_theme_line_shade_color(self):
        c = ANXChart()
        c.add_theme_line(id='TL', type='T', shade_color=16711680)
        root = _parse_xml(c)
        ts = root.find('.//ThemeStyle')
        assert ts is not None
        assert ts.get('IconShadingColour') == '16711680'

    def test_text_block_alignment(self):
        c = ANXChart()
        c.add_text_block(id='TB', type='T', alignment='TextAlignLeft', width=200, height=100)
        root = _parse_xml(c)
        tbs = root.find('.//TextBlockStyle')
        assert tbs is not None
        assert tbs.get('Alignment') == 'TextAlignLeft'
        assert tbs.get('Width') == '2.0'
        assert tbs.get('Height') == '1.0'

    def test_label_entity_uses_textblock(self):
        c = ANXChart()
        c.add_label(id='LB', type='T', alignment='TextAlignRight', width=150, height=50)
        root = _parse_xml(c)
        # Label entities use TextBlock element with TextBlockStyle
        tbs = root.find('.//TextBlockStyle')
        assert tbs is not None
        assert tbs.get('Alignment') == 'TextAlignRight'


# ── Link fields in XML ───────────────────────────────────────────────────────

class TestLinkFieldsInXML:
    def _make_linked_chart(self, **link_kwargs):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call', **link_kwargs)
        return _parse_xml(c)

    def test_arrow_on_head(self):
        root = self._make_linked_chart(arrow='ArrowOnHead')
        ls = root.find('.//LinkStyle')
        assert ls.get('ArrowStyle') == 'ArrowOnHead'

    def test_link_line_color(self):
        root = self._make_linked_chart(line_color=255)
        ls = root.find('.//LinkStyle')
        assert ls.get('LineColour') == '255'

    def test_link_line_width(self):
        root = self._make_linked_chart(line_width=3)
        ls = root.find('.//LinkStyle')
        assert ls.get('LineWidth') == '3'

    def test_link_offset(self):
        root = self._make_linked_chart(offset=20)
        link = root.find('.//Link')
        assert link.get('Offset') == '20'

    def test_link_strength(self):
        c = ANXChart()
        c.add_strength('Strong', dot_style=DotStyle.DASHED)
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call', strength='Strong')
        root = _parse_xml(c)
        ls = root.find('.//LinkStyle')
        assert ls.get('Strength') == 'Strong'

    def test_link_ordered(self):
        c = ANXChart()
        c.add_theme_line(id='TL1', type='Theme')
        c.add_theme_line(id='TL2', type='Theme')
        c.add_link(from_id='TL1', to_id='TL2', type='X', ordered=True,
                   date='2024-01-15', time='09:00:00')
        root = _parse_xml(c)
        # Find the link ChartItem (has a Link child)
        for ci in root.findall('.//ChartItem'):
            if ci.find('Link') is not None:
                assert ci.get('Ordered') == 'true'
                break
        else:
            assert False, "No link ChartItem found"


# ── Cards in XML ─────────────────────────────────────────────────────────────

class TestCardsInXML:
    def test_entity_inline_card(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', cards=[Card(summary='Note 1')])
        root = _parse_xml(c)
        cc = root.find('.//Entity/CardCollection')
        assert cc is not None
        cards = cc.findall('Card')
        assert len(cards) == 1
        assert cards[0].get('Summary') == 'Note 1'

    def test_entity_loose_card(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_card(entity_id='A', summary='Loose')
        root = _parse_xml(c)
        cc = root.find('.//Entity/CardCollection')
        assert cc is not None
        assert cc.find('Card').get('Summary') == 'Loose'

    def test_link_inline_card(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call',
                   cards=[Card(summary='Intercept')])
        root = _parse_xml(c)
        cc = root.find('.//Link/CardCollection')
        assert cc is not None
        assert cc.find('Card').get('Summary') == 'Intercept'

    def test_link_loose_card(self):
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call', link_id='L1')
        c.add_card(link_id='L1', summary='Loose link card')
        root = _parse_xml(c)
        cc = root.find('.//Link/CardCollection')
        assert cc is not None
        assert cc.find('Card').get('Summary') == 'Loose link card'

    def test_card_fields(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', cards=[Card(
            summary='Note', date='2024-01-15', time='09:00:00',
            source_ref='REF-1', source_type='Witness',
        )])
        root = _parse_xml(c)
        card = root.find('.//Card')
        assert card.get('Summary') == 'Note'
        assert card.get('DateSet') == 'true'
        assert card.get('TimeSet') == 'true'
        assert card.get('SourceReference') == 'REF-1'
        assert card.get('SourceType') == 'Witness'


# ── Grades in XML ────────────────────────────────────────────────────────────

class TestGradesInXML:
    def test_grade_collections(self):
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.grades_two = GradeCollection(items=['Confirmed'])
        c.grades_three = GradeCollection(items=['High', 'Low'])
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        g1 = root.find('.//GradeOne/StringCollection')
        assert g1 is not None
        # +1 for the '-' sentinel appended automatically
        assert len(g1.findall('String')) == 3
        assert g1.findall('String')[-1].get('Text') == '-'
        g2 = root.find('.//GradeTwo/StringCollection')
        assert g2 is not None
        assert len(g2.findall('String')) == 2  # 1 user + 1 sentinel
        g3 = root.find('.//GradeThree/StringCollection')
        assert g3 is not None
        assert len(g3.findall('String')) == 3  # 2 user + 1 sentinel

    def test_grade_index_on_entity(self):
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T', grade_one=0)
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        # User index 0 stays at 0 (no shifting)
        assert ci.get('GradeOneIndex') == '0'

    def test_grade_index_on_link(self):
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call', grade_one=1)
        root = _parse_xml(c)
        for ci in root.findall('.//ChartItem'):
            if ci.find('Link') is not None:
                # User index 1 stays at 1 (no shifting)
                assert ci.get('GradeOneIndex') == '1'
                break

    def test_sentinel_default_on_ungraded_entity(self):
        """Ungraded entities get the sentinel '-' index (last position)."""

        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T')  # no grade_one set
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('GradeOneIndex') == '2'  # last index = sentinel '-'

    def test_user_default_in_values(self):
        """When default is in values, no sentinel appended."""

        c = ANXChart()
        c.grades_one = GradeCollection(default='Reliable', items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        g1 = root.find('.//GradeOne/StringCollection')
        entries = [s.get('Text') for s in g1.findall('String')]
        assert entries == ['Reliable', 'Unreliable']  # no sentinel
        ci = root.find('.//ChartItem')
        assert ci.get('GradeOneIndex') == '0'

    def test_user_default_in_items(self):
        """Default references an item in the list — uses its index."""

        c = ANXChart()
        c.grades_one = GradeCollection(default='Unreliable', items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        g1 = root.find('.//GradeOne/StringCollection')
        entries = [s.get('Text') for s in g1.findall('String')]
        assert entries == ['Reliable', 'Unreliable']  # no sentinel
        ci = root.find('.//ChartItem')
        assert ci.get('GradeOneIndex') == '1'

    def test_grade_name_on_entity(self):
        """grade_one accepts a name string and resolves to its index."""
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T', grade_one='Unreliable')
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('GradeOneIndex') == '1'

    def test_grade_name_on_link(self):
        """grade_one on a link accepts a name string."""
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call', grade_one='Reliable')
        root = _parse_xml(c)
        for ci in root.findall('.//ChartItem'):
            if ci.find('Link') is not None:
                assert ci.get('GradeOneIndex') == '0'
                break

    def test_grade_name_on_card(self):
        """grade_one on an inline Card accepts a name string."""
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T',
                   cards=[Card(summary='s', grade_one='Unreliable')])
        root = _parse_xml(c)
        card = root.find('.//Card')
        assert card is not None
        assert card.get('GradeOneIndex') == '1'

    def test_unknown_grade_name_raises(self):
        """A grade name that's not in the collection is a validation error."""
        from anxwritter.errors import ANXValidationError, ErrorType
        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T', grade_one='Bogus')
        with pytest.raises(ANXValidationError) as exc_info:
            c.to_xml()
        assert any(e['type'] == ErrorType.UNKNOWN_GRADE.value
                   for e in exc_info.value.errors)

    def test_explicit_grade_preserved(self):
        """Explicit grade index is not overwritten by default."""

        c = ANXChart()
        c.grades_one = GradeCollection(default='Reliable', items=['Reliable', 'Unreliable'])
        c.add_icon(id='A', type='T', grade_one=1)  # explicit
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('GradeOneIndex') == '1'  # stays at 1

    def test_card_gets_grade_default(self):
        """Cards on entities also get the grade default."""

        c = ANXChart()
        c.grades_one = GradeCollection(items=['Reliable'])
        c.add_icon(id='A', type='T', cards=[Card(summary='test')])
        root = _parse_xml(c)
        card = root.find('.//Card')
        assert card is not None
        assert card.get('GradeOneIndex') == '1'  # sentinel '-' at index 1

    def test_no_grades_no_collection(self):
        """No grade collection emitted when grades not defined."""
        c = ANXChart()
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        assert root.find('.//GradeOne') is None


# ── Strength defaults in XML ────────────────────────────────────────────────

class TestStrengthDefaults:
    def test_no_custom_strengths_keeps_default(self):
        """Without custom strengths, 'Default' stays."""
        c = ANXChart()
        c.add_box(id='A', type='T')
        root = _parse_xml(c)
        names = [s.get('Name') for s in root.findall('.//StrengthCollection/Strength')]
        assert 'Default' in names

    def test_custom_strengths_sentinel(self):
        """Custom strengths + no default → '-' replaces 'Default'."""

        c = ANXChart()
        c.strengths = StrengthCollection(items=[
            Strength(name='Default', dot_style=DotStyle.SOLID),
            Strength(name='Confirmed', dot_style=DotStyle.SOLID),
        ])
        c.add_box(id='A', type='T')
        root = _parse_xml(c)
        names = [s.get('Name') for s in root.findall('.//StrengthCollection/Strength')]
        assert '-' in names
        assert 'Default' not in names

    def test_custom_strengths_user_default(self):
        """Custom strengths + explicit default → no sentinel."""

        c = ANXChart()
        c.strengths = StrengthCollection(
            default='Confirmed',
            items=[
                Strength(name='Default', dot_style=DotStyle.SOLID),
                Strength(name='Confirmed', dot_style=DotStyle.SOLID),
            ],
        )
        c.add_box(id='A', type='T')
        root = _parse_xml(c)
        names = [s.get('Name') for s in root.findall('.//StrengthCollection/Strength')]
        assert 'Confirmed' in names
        assert '-' not in names
        assert 'Default' not in names


# ── Source types in XML ──────────────────────────────────────────────────────

class TestSourceTypesInXML:
    def test_source_hints_collection(self):
        c = ANXChart()
        c.source_types = ['Witness', 'Informant']
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        sh = root.find('.//SourceHints/StringCollection')
        assert sh is not None
        strings = sh.findall('String')
        assert len(strings) == 2
        texts = {s.get('Text') for s in strings}
        assert texts == {'Witness', 'Informant'}

    def test_source_type_on_entity(self):
        c = ANXChart()
        c.source_types = ['Witness']
        c.add_icon(id='A', type='T', source_type='Witness')
        root = _parse_xml(c)
        ci = root.find('.//ChartItem')
        assert ci.get('SourceType') == 'Witness'


# ── Legend in XML ────────────────────────────────────────────────────────────

class TestLegendInXML:
    def test_legend_definition_emitted(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_icon(id='A', type='T')
        c.add_legend_item(name='Person', item_type='Icon')
        root = _parse_xml(c)
        ld = root.find('.//LegendDefinition')
        assert ld is not None
        assert ld.get('Shown') == 'true'

    def test_legend_item_structure(self):
        c = ANXChart(settings={'legend_cfg': {'show': True}})
        c.add_icon(id='A', type='T')
        c.add_legend_item(name='Call', item_type='Link', color=255, line_width=2)
        root = _parse_xml(c)
        li = root.find('.//LegendItem')
        assert li is not None
        assert li.get('Type') == 'LegendItemTypeLink'
        assert li.get('Label') == 'Call'
        assert li.get('Colour') == '255'
        assert li.get('LineWidth') == '2'


# ── Strengths in XML ─────────────────────────────────────────────────────────

class TestStrengthsInXML:
    def test_all_dot_styles(self):
        c = ANXChart()
        c.add_strength('S1', dot_style=DotStyle.SOLID)
        c.add_strength('S2', dot_style=DotStyle.DASHED)
        c.add_strength('S3', dot_style=DotStyle.DASH_DOT)
        c.add_strength('S4', dot_style=DotStyle.DASH_DOT_DOT)
        c.add_strength('S5', dot_style=DotStyle.DOTTED)
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        sc = root.find('.//StrengthCollection')
        strengths = sc.findall('Strength')
        styles = {s.get('Name'): s.get('DotStyle') for s in strengths}
        assert styles['S1'] == 'DotStyleSolid'
        assert styles['S2'] == 'DotStyleDashed'
        assert styles['S3'] == 'DotStyleDashDot'
        assert styles['S4'] == 'DotStyleDashDotDot'
        assert styles['S5'] == 'DotStyleDotted'


# ── Font styling in XML ──────────────────────────────────────────────────────

class TestFontStylingInXML:
    def test_entity_label_font(self):
        from anxwritter import Font
        c = ANXChart()
        c.add_icon(id='A', type='T', label_font=Font(color=255, bold=True))
        root = _parse_xml(c)
        font = root.find('.//CIStyle/Font')
        assert font is not None
        assert font.get('FontColour') == '255'
        assert font.get('Bold') == 'true'

    def test_link_label_font(self):
        from anxwritter import Font
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call',
                   label_font=Font(color=65280, bold=True))
        root = _parse_xml(c)
        # Find the link ChartItem's CIStyle/Font
        for ci in root.findall('.//ChartItem'):
            if ci.find('Link') is not None:
                font = ci.find('CIStyle/Font')
                assert font is not None
                assert font.get('FontColour') == '65280'
                assert font.get('Bold') == 'true'
                break

    def test_chart_font(self):
        c = ANXChart(settings={'font': {'name': 'Arial', 'size': 12}})
        c.add_icon(id='A', type='T')
        root = _parse_xml(c)
        # Chart-level font is a direct child of <Chart>
        font = root.find('Font')
        assert font is not None
        assert font.get('FaceName') == 'Arial'
        assert font.get('PointSize') == '12'


# ── Auto-color ──────────────────────────────────────────────────────────────

class TestAutoColour:
    def test_entity_auto_color_assigns(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_icon(id='A', type='Person')
        c.add_icon(id='B', type='Vehicle')
        root = _parse_xml(c)
        icons = root.findall('.//IconStyle')
        # Both should have IconShadingColour set
        for icon in icons:
            assert icon.get('IconShadingColour') is not None

    def test_explicit_color_wins(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_icon(id='A', type='Person', color='Red')
        root = _parse_xml(c)
        icon = root.find('.//IconStyle')
        assert icon.get('IconShadingColour') == '255'  # Red = 255

    def test_theme_line_gets_auto_color(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_theme_line(id='TL1', type='ThemeLine')
        c.add_theme_line(id='TL2', type='ThemeLine')
        root = _parse_xml(c)
        themes = root.findall('.//ThemeStyle')
        assert len(themes) == 2
        for theme in themes:
            # Both the end-icon tint and the horizontal band line must be colored.
            assert theme.get('IconShadingColour') is not None
            assert theme.get('LineColour') is not None

    def test_theme_line_auto_color_matches_shade(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_theme_line(id='TL1', type='ThemeLine')
        root = _parse_xml(c)
        theme = root.find('.//ThemeStyle')
        assert theme.get('IconShadingColour') == theme.get('LineColour')

    def test_theme_line_explicit_line_color_wins(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_theme_line(id='TL1', type='ThemeLine', line_color=255)
        root = _parse_xml(c)
        theme = root.find('.//ThemeStyle')
        assert theme.get('LineColour') == '255'

    def test_event_frame_gets_auto_color(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_event_frame(id='EF1', type='EventFrame')
        c.add_event_frame(id='EF2', type='EventFrame')
        root = _parse_xml(c)
        events = root.findall('.//EventStyle')
        assert len(events) == 2
        for event in events:
            # Both the icon tint and the frame border line must be colored.
            assert event.get('IconShadingColour') is not None
            assert event.get('LineColour') is not None

    def test_event_frame_auto_color_matches_shade(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        c.add_event_frame(id='EF1', type='EventFrame')
        root = _parse_xml(c)
        event = root.find('.//EventStyle')
        assert event.get('IconShadingColour') == event.get('LineColour')


class TestEntityColorNormalization:
    """Named colors, hex strings, and Color enums must work on every
    color-typed entity field, not just Icon.color."""

    def test_theme_line_named_line_color(self):
        c = ANXChart()
        c.add_theme_line(id='TL', type='ThemeLine', line_color='Red')
        root = _parse_xml(c)
        theme = root.find('.//ThemeStyle')
        assert theme.get('LineColour') == '255'  # Red = 255

    def test_theme_line_hex_line_color(self):
        c = ANXChart()
        c.add_theme_line(id='TL', type='ThemeLine', line_color='#FF0000')
        root = _parse_xml(c)
        theme = root.find('.//ThemeStyle')
        assert theme.get('LineColour') == '255'  # #FF0000 = Red

    def test_event_frame_named_bg_color(self):
        c = ANXChart()
        c.add_event_frame(id='EF', type='EventFrame', bg_color='Blue')
        root = _parse_xml(c)
        event = root.find('.//EventStyle')
        assert event.get('BackColour') == '16711680'  # Blue COLORREF

    def test_event_frame_named_line_color(self):
        c = ANXChart()
        c.add_event_frame(id='EF', type='EventFrame', line_color='Red')
        root = _parse_xml(c)
        event = root.find('.//EventStyle')
        assert event.get('LineColour') == '255'

    def test_box_named_bg_color(self):
        c = ANXChart()
        c.add_box(id='B', type='Box', bg_color='Red')
        root = _parse_xml(c)
        box = root.find('.//BoxStyle')
        assert box.get('BackColour') == '255'

    def test_textblock_named_line_color(self):
        c = ANXChart()
        c.add_text_block(id='T', type='Note', line_color='Red', bg_color='Blue')
        root = _parse_xml(c)
        tb = root.find('.//TextBlockStyle')
        assert tb.get('LineColour') == '255'
        assert tb.get('BackColour') == '16711680'

    def test_frame_named_color(self):
        from anxwritter import Frame
        c = ANXChart()
        c.add_icon(id='A', type='Person', frame=Frame(color='Red', margin=2, visible=True))
        root = _parse_xml(c)
        fs = root.find('.//FrameStyle')
        assert fs is not None
        assert fs.get('Colour') == '255'


# ── Link end color ───────────────────────────────────────────────────────────

class TestLinkEndColor:
    def test_link_match_entity_color(self):
        c = ANXChart(settings={'extra_cfg': {'link_match_entity_color': True}})
        c.add_icon(id='A', type='T', color='Red')
        c.add_icon(id='B', type='T', color='Blue')
        c.add_link(from_id='A', to_id='B', type='Call')
        root = _parse_xml(c)
        ls = root.find('.//LinkStyle')
        # link_match_entity_color uses to_id entity's color
        assert ls.get('LineColour') is not None

    def test_link_match_auto_colored_theme_line(self):
        c = ANXChart(settings={'extra_cfg': {
            'entity_auto_color': True,
            'link_match_entity_color': True,
        }})
        c.add_icon(id='A', type='Person')
        c.add_theme_line(id='TL', type='ThemeLine')
        c.add_link(from_id='A', to_id='TL', type='On')
        root = _parse_xml(c)
        ls = root.find('.//LinkStyle')
        assert ls.get('LineColour') is not None
        assert ls.get('LineColour') != '0'

    def test_link_skipped_when_target_has_no_color(self):
        c = ANXChart(settings={'extra_cfg': {'link_match_entity_color': True}})
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='Call')
        root = _parse_xml(c)
        ls = root.find('.//LinkStyle')
        # No auto-color and no explicit color on B — LineColour omitted,
        # not forced to 0 (black), so ANB falls back to the link type's default.
        assert ls.get('LineColour') is None


# ── No user-object mutation ──────────────────────────────────────────────────

class TestNoUserObjectMutation:
    def test_entity_color_not_mutated_by_auto_color(self):
        c = ANXChart(settings={'extra_cfg': {'entity_auto_color': True}})
        icon = Icon(id='A', type='Person')
        assert icon.color is None
        c.add(icon)
        c.to_xml()
        assert icon.color is None

    def test_link_color_not_mutated_by_link_match(self):
        c = ANXChart(settings={'extra_cfg': {'link_match_entity_color': True}})
        c.add_icon(id='A', type='T', color='Red')
        c.add_icon(id='B', type='T', color='Blue')
        link = Link(from_id='A', to_id='B', type='Call')
        assert link.line_color is None
        c.add(link)
        c.to_xml()
        assert link.line_color is None

    def test_card_fields_not_mutated_after_build(self):
        card = Card(summary='Original', date='2024-01-15', time='09:00:00')
        c = ANXChart()
        c.add_icon(id='A', type='T', cards=[card])
        c.to_xml()
        assert card.summary == 'Original'
        assert card.date == '2024-01-15'
        assert card.time == '09:00:00'

    def test_card_datetime_resolved_in_xml(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', cards=[Card(date='15/01/2024', time='09:30:00')])
        root = _parse_xml(c)
        card_el = root.find('.//Card')
        assert card_el.get('DateTime') == '2024-01-15T09:30:00.000'
        assert card_el.get('DateSet') == 'true'
        assert card_el.get('TimeSet') == 'true'


# ── Timezone in XML ──────────────────────────────────────────────────────────

class TestTimezoneInXML:
    def test_entity_timezone(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', date='2024-01-15', time='09:00:00',
                   timezone={'id': 1, 'name': 'UTC'})
        root = _parse_xml(c)
        tz = root.find('.//ChartItem/TimeZone')
        assert tz is not None
        assert tz.get('UniqueID') == '1'
        assert tz.get('Name') == 'UTC'

    def test_card_timezone(self):
        c = ANXChart()
        c.add_icon(id='A', type='T', cards=[Card(
            summary='Note', date='2024-01-15', time='09:00:00',
            timezone=TimeZone(id=1, name='UTC'),
        )])
        root = _parse_xml(c)
        tz = root.find('.//Card/TimeZone')
        assert tz is not None
        assert tz.get('UniqueID') == '1'


# ── AttributeClass in XML ───────────────────────────────────────────────────

class TestAttributeClassInXML:
    def test_prefix_suffix(self):
        c = ANXChart()
        c.add_attribute_class(name='Phone', type=AttributeType.TEXT, prefix='Tel: ', suffix=' ext')
        c.add_icon(id='A', type='T', attributes={'Phone': '555'})
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="Phone"]')
        assert ac is not None
        assert ac.get('Prefix') == 'Tel: '
        assert ac.get('ShowPrefix') == 'true'
        assert ac.get('Suffix') == ' ext'
        assert ac.get('ShowSuffix') == 'true'

    def test_decimal_places(self):
        c = ANXChart()
        c.add_attribute_class(name='Balance', type=AttributeType.NUMBER, decimal_places=2)
        c.add_icon(id='A', type='T', attributes={'Balance': 42.5})
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="Balance"]')
        assert ac is not None
        assert ac.get('DecimalPlaces') == '2'

    def test_merge_behaviour(self):
        c = ANXChart()
        c.add_attribute_class(name='Notes', type=AttributeType.TEXT, merge_behaviour='AttMergeAdd')
        c.add_icon(id='A', type='T', attributes={'Notes': 'hello'})
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="Notes"]')
        assert ac.get('MergeBehaviour') == 'AttMergeAdd'

    def test_font_on_attribute_class(self):
        from anxwritter import Font
        c = ANXChart()
        c.add_attribute_class(name='Phone', type=AttributeType.TEXT, font=Font(name='Courier', size=9))
        c.add_icon(id='A', type='T', attributes={'Phone': '555'})
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="Phone"]')
        font = ac.find('Font')
        assert font is not None
        assert font.get('FaceName') == 'Courier'
        assert font.get('PointSize') == '9'

    def test_attribute_type_inferred_from_python_value(self):
        """Regression: _parse_attrs returned capitalized names that missed
        the lowercase _ATT_TYPE dict keys, so every AttributeClass silently
        became Type='AttText' regardless of the actual Python value type.
        """
        from datetime import datetime
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={
            'Notes':   'hello',                    # str   → AttText
            'Count':   42,                          # int   → AttNumber
            'Balance': 12.5,                        # float → AttNumber
            'Active':  True,                        # bool  → AttFlag
            'Seen':    datetime(2024, 1, 1, 9, 0),  # datetime → AttTime
        })
        root = _parse_xml(c)
        types = {
            ac.get('Name'): ac.get('Type')
            for ac in root.findall('.//AttributeClassCollection/AttributeClass')
        }
        assert types['Notes']   == 'AttText'
        assert types['Count']   == 'AttNumber'
        assert types['Balance'] == 'AttNumber'
        assert types['Active']  == 'AttFlag'
        assert types['Seen']    == 'AttTime'

    def test_attribute_type_inferred_on_link_attributes(self):
        """Same inference must run for link attributes, not just entities."""
        c = ANXChart()
        c.add_icon(id='A', type='T')
        c.add_icon(id='B', type='T')
        c.add_link(from_id='A', to_id='B', type='X', attributes={
            'Weight': 3.14,
            'Confirmed': True,
        })
        root = _parse_xml(c)
        types = {
            ac.get('Name'): ac.get('Type')
            for ac in root.findall('.//AttributeClassCollection/AttributeClass')
        }
        assert types['Weight'] == 'AttNumber'
        assert types['Confirmed'] == 'AttFlag'

    def test_flag_attribute_emits_true_false_strings(self):
        """Bool values must serialize to 'true'/'false' strings, matching AttFlag."""
        c = ANXChart()
        c.add_icon(id='A', type='T', attributes={'Active': True})
        c.add_icon(id='B', type='T', attributes={'Active': False})
        root = _parse_xml(c)
        values = [
            a.get('Value')
            for a in root.findall('.//Attribute')
            if a.get('Name') == 'Active' or
               (a.get('AttributeClassReference') and True)
        ]
        # Simpler: just check the emitted Value strings look like 'true'/'false'
        all_attrs = root.findall('.//Attribute')
        active_values = {
            a.get('Value') for a in all_attrs if a.get('Value') in ('true', 'false')
        }
        assert active_values == {'true', 'false'}


# ── MergeBehaviour/PasteBehaviour XML casing regression ────────────────────

# Regression: _MERGE_MAP once carried 'AttMergeOr'/'AttMergeAnd'/'AttMergeXor'
# (camelCase), which the ANB schema rejects. The canonical forms are the
# all-caps suffixes 'AttMergeOR'/'AttMergeAND'/'AttMergeXOR'. The test walks
# every MergeBehaviour enum member, exercises the builder end-to-end, and
# asserts the emitted XML attribute string matches _MERGE_MAP.

import pytest
from datetime import datetime
from anxwritter import MergeBehaviour
from anxwritter.builder import _MERGE_MAP


def _sample_value_for(att_type: AttributeType):
    return {
        AttributeType.TEXT:     'sample',
        AttributeType.NUMBER:   42.0,
        AttributeType.FLAG:     True,
        AttributeType.DATETIME: datetime(2024, 1, 1, 9, 0, 0),
    }[att_type]


# (MergeBehaviour, compatible AttributeType, field name to set on the AC)
# Every enum member appears at least once; combinations cover the per-type
# validity matrix per docs/reference/attributes.md.
_CASING_CASES = [
    # assign/noop: paste-only, valid for any type
    (MergeBehaviour.ASSIGN,              AttributeType.TEXT,     'paste_behaviour'),
    (MergeBehaviour.NO_OP,               AttributeType.TEXT,     'paste_behaviour'),
    # add/add_space/add_line_break: Text (merge and paste)
    (MergeBehaviour.ADD,                 AttributeType.TEXT,     'merge_behaviour'),
    (MergeBehaviour.ADD_WITH_SPACE,      AttributeType.TEXT,     'merge_behaviour'),
    (MergeBehaviour.ADD_WITH_LINE_BREAK, AttributeType.TEXT,     'merge_behaviour'),
    # max/min: Number (both merge and paste)
    (MergeBehaviour.MAX,                 AttributeType.NUMBER,   'merge_behaviour'),
    (MergeBehaviour.MIN,                 AttributeType.NUMBER,   'merge_behaviour'),
    # subtract/subtract_swap: Number (paste only)
    (MergeBehaviour.SUBTRACT,            AttributeType.NUMBER,   'paste_behaviour'),
    (MergeBehaviour.SUBTRACT_SWAP,       AttributeType.NUMBER,   'paste_behaviour'),
    # or/and/xor: Flag (both merge and paste)
    (MergeBehaviour.OR,                  AttributeType.FLAG,     'merge_behaviour'),
    (MergeBehaviour.AND,                 AttributeType.FLAG,     'merge_behaviour'),
    (MergeBehaviour.XOR,                 AttributeType.FLAG,     'merge_behaviour'),
]


class TestMergeBehaviourCasing:
    """Assert that the emitted MergeBehaviour/PasteBehaviour XML attribute
    string exactly matches the canonical ANB enum form in ``_MERGE_MAP``.

    Ground truth is ``_MERGE_MAP`` (the library's own source of canonical
    names). If someone changes the map wrong, this test catches emitter
    drift but not map-vs-schema drift — that is a deliberate tradeoff.
    """

    @pytest.mark.parametrize("behaviour, att_type, field", _CASING_CASES)
    def test_emitted_casing_matches_merge_map(self, behaviour, att_type, field):
        c = ANXChart()
        c.add_icon(
            id='A', type='T',
            attributes={'X': _sample_value_for(att_type)},
        )
        c.add_attribute_class(
            name='X', type=att_type, **{field: behaviour},
        )
        root = _parse_xml(c)
        ac = root.find('.//AttributeClass[@Name="X"]')
        assert ac is not None

        xml_field = 'MergeBehaviour' if field == 'merge_behaviour' else 'PasteBehaviour'
        emitted = ac.get(xml_field)
        expected = _MERGE_MAP[behaviour.value]
        assert emitted == expected, (
            f"{behaviour.value!r} emitted as {emitted!r}, expected {expected!r}"
        )

    def test_all_12_enum_members_covered(self):
        """Guard: every MergeBehaviour enum member must appear in the
        parametrized case list above. Prevents silent gaps if new enum
        members are added later."""
        covered = {case[0] for case in _CASING_CASES}
        assert covered == set(MergeBehaviour)


class TestIconOverride:
    """Test OverrideTypeIcon / TypeIconName on Icon, ThemeLine, EventFrame."""

    def test_icon_override_on_icon(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person', icon='witness')
        root = _parse_xml(c)
        style = root.find('.//Icon/IconStyle')
        assert style is not None
        assert style.get('OverrideTypeIcon') == 'true'
        assert style.get('TypeIconName') == 'witness'
        assert style.get('Type') == 'Person'

    def test_icon_override_on_theme_line(self):
        c = ANXChart()
        c.add(ThemeLine(id='TL1', type='Person', icon='witness'))
        root = _parse_xml(c)
        style = root.find('.//Theme/ThemeStyle')
        assert style is not None
        assert style.get('OverrideTypeIcon') == 'true'
        assert style.get('TypeIconName') == 'witness'

    def test_icon_override_on_event_frame(self):
        c = ANXChart()
        c.add(EventFrame(id='EF1', type='Event', icon='person'))
        root = _parse_xml(c)
        style = root.find('.//Event/EventStyle')
        assert style is not None
        assert style.get('OverrideTypeIcon') == 'true'
        assert style.get('TypeIconName') == 'person'

    def test_no_override_when_icon_not_set(self):
        c = ANXChart()
        c.add_icon(id='A', type='Person')
        root = _parse_xml(c)
        style = root.find('.//Icon/IconStyle')
        assert style is not None
        assert style.get('OverrideTypeIcon') is None
        assert style.get('TypeIconName') is None

    def test_icon_translated_via_entity_type(self):
        """Icon name matching a registered EntityType is translated to its icon_file."""
        c = ANXChart()
        c.add_entity_type(name='Pessoa', icon_file='person')
        c.add_icon(id='A', type='Vehicle', icon='Pessoa')
        root = _parse_xml(c)
        style = root.find('.//Icon/IconStyle')
        assert style.get('TypeIconName') == 'person'  # translated
        assert style.get('OverrideTypeIcon') == 'true'

    def test_icon_raw_key_passes_through(self):
        """Icon name not matching any EntityType passes through unchanged."""
        c = ANXChart()
        c.add_icon(id='A', type='Person', icon='witness')
        root = _parse_xml(c)
        style = root.find('.//Icon/IconStyle')
        assert style.get('TypeIconName') == 'witness'  # no translation


class TestIdempotency:
    """Build pipeline must not mutate user objects or produce different output on repeated calls."""

    def test_to_xml_twice_identical_with_loose_cards(self):
        """Calling to_xml() twice must produce identical XML (loose cards not duplicated)."""
        c = ANXChart()
        icon = Icon(id='Alice', type='Person')
        c.add(icon)
        c.add(Link(from_id='Alice', to_id='Bob', type='Call', link_id='call1'))
        c.add(Icon(id='Bob', type='Person'))
        c.add_card(entity_id='Alice', summary='Entity card')
        c.add_card(link_id='call1', summary='Link card')

        xml1 = c.to_xml()
        xml2 = c.to_xml()
        assert xml1 == xml2

    def test_to_xml_twice_identical_with_semantic_types(self):
        """Calling to_xml() twice with semantic types must produce identical XML."""
        c = ANXChart()
        c.add_semantic_entity(name='Suspect', kind_of='Entity')
        c.add_entity_type(name='Suspect', semantic_type='Suspect')
        c.add_icon(id='Alice', type='Suspect', semantic_type='Suspect')
        c.add_icon(id='Bob', type='Suspect')
        c.add_link(from_id='Alice', to_id='Bob', type='Knows')

        xml1 = c.to_xml()
        xml2 = c.to_xml()
        assert xml1 == xml2

    def test_loose_cards_dont_mutate_user_entity(self):
        """Loose cards must not be appended to the user's entity.cards list."""
        c = ANXChart()
        icon = Icon(id='Alice', type='Person')
        assert len(icon.cards) == 0
        c.add(icon)
        c.add(Icon(id='Bob', type='Person'))
        c.add_link(from_id='Alice', to_id='Bob', type='Knows')
        c.add_card(entity_id='Alice', summary='Loose card')

        c.to_xml()
        assert len(icon.cards) == 0, "Loose card was appended to user entity object"

    def test_loose_cards_dont_mutate_user_link(self):
        """Loose cards must not be appended to the user's link.cards list."""
        c = ANXChart()
        c.add_icon(id='Alice', type='Person')
        c.add_icon(id='Bob', type='Person')
        link = Link(from_id='Alice', to_id='Bob', type='Call', link_id='call1')
        assert len(link.cards) == 0
        c.add(link)
        c.add_card(link_id='call1', summary='Loose link card')

        c.to_xml()
        assert len(link.cards) == 0, "Loose card was appended to user link object"

    def test_semantic_guid_not_set_on_user_object(self):
        """Build must not monkey-patch _resolved_semantic_guid onto user objects."""
        c = ANXChart()
        c.add_semantic_entity(name='Suspect', kind_of='Entity')
        c.add_entity_type(name='Suspect', semantic_type='Suspect')
        icon = Icon(id='Alice', type='Suspect', semantic_type='Suspect')
        link = Link(from_id='Alice', to_id='Bob', type='Knows')
        c.add(icon)
        c.add(Icon(id='Bob', type='Suspect'))
        c.add(link)

        c.to_xml()
        assert not hasattr(icon, '_resolved_semantic_guid'), \
            "_resolved_semantic_guid was set on user entity object"
        assert not hasattr(link, '_resolved_semantic_guid'), \
            "_resolved_semantic_guid was set on user link object"

    def test_loose_cards_included_in_output(self):
        """Loose cards must still appear in the generated XML."""
        c = ANXChart()
        c.add_icon(id='Alice', type='Person')
        c.add_icon(id='Bob', type='Person')
        c.add_link(from_id='Alice', to_id='Bob', type='Call', link_id='call1')
        c.add_card(entity_id='Alice', summary='Entity evidence')
        c.add_card(link_id='call1', summary='Link evidence')

        root = _parse_xml(c)
        cards = root.findall('.//Card')
        summaries = {card.get('Summary') for card in cards}
        assert 'Entity evidence' in summaries
        assert 'Link evidence' in summaries

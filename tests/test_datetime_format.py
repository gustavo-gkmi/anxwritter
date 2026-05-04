"""Tests for DateTimeFormat chart-level collection and per-item referencing."""
import xml.etree.ElementTree as ET

import pytest

from anxwritter import ANXChart, DateTimeFormat, Icon, Link


class TestDateTimeFormatModel:
    def test_create_default(self):
        dtf = DateTimeFormat()
        assert dtf.name == ''
        assert dtf.format == ''

    def test_create_with_values(self):
        dtf = DateTimeFormat(name='ISO', format='yyyy-MM-dd')
        assert dtf.name == 'ISO'
        assert dtf.format == 'yyyy-MM-dd'


class TestAddDateTimeFormat:
    def test_add_by_kwargs(self):
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        assert len(chart._datetime_formats) == 1
        assert chart._datetime_formats[0].name == 'ISO'
        assert chart._datetime_formats[0].format == 'yyyy-MM-dd'

    def test_add_by_name_shorthand(self):
        chart = ANXChart()
        chart.add_datetime_format('BR', format='dd/MM/yyyy')
        assert chart._datetime_formats[0].name == 'BR'

    def test_add_by_object(self):
        chart = ANXChart()
        dtf = DateTimeFormat(name='US', format='MM/dd/yyyy')
        chart.add_datetime_format(dtf)
        assert chart._datetime_formats[0].name == 'US'

    def test_replace_on_duplicate(self):
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd HH:mm')
        assert len(chart._datetime_formats) == 1
        assert chart._datetime_formats[0].format == 'yyyy-MM-dd HH:mm'

    def test_add_dispatch(self):
        chart = ANXChart()
        chart.add(DateTimeFormat(name='ISO', format='yyyy-MM-dd'))
        assert len(chart._datetime_formats) == 1


class TestXMLEmission:
    def _build_xml(self, chart):
        xml_str = chart.to_xml()
        return ET.fromstring(xml_str)

    def test_collection_emitted(self):
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_icon(id='A', type='T')
        root = self._build_xml(chart)

        dtfc = root.find('DateTimeFormatCollection')
        assert dtfc is not None
        formats = dtfc.findall('DateTimeFormat')
        assert len(formats) == 1
        assert formats[0].get('Name') == 'ISO'
        assert formats[0].get('Format') == 'yyyy-MM-dd'
        assert formats[0].get('Id') is not None

    def test_collection_omitted_when_empty(self):
        chart = ANXChart()
        chart.add_icon(id='A', type='T')
        root = self._build_xml(chart)
        assert root.find('DateTimeFormatCollection') is None

    def test_multiple_formats(self):
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_datetime_format(name='BR', format='dd/MM/yyyy')
        chart.add_icon(id='A', type='T')
        root = self._build_xml(chart)

        dtfc = root.find('DateTimeFormatCollection')
        formats = dtfc.findall('DateTimeFormat')
        assert len(formats) == 2
        names = {f.get('Name') for f in formats}
        assert names == {'ISO', 'BR'}

    def test_format_without_format_string(self):
        chart = ANXChart()
        chart.add_datetime_format(name='Default')
        chart.add_icon(id='A', type='T')
        root = self._build_xml(chart)

        dtfc = root.find('DateTimeFormatCollection')
        fmt = dtfc.find('DateTimeFormat')
        assert fmt.get('Name') == 'Default'
        assert fmt.get('Format') is None  # not emitted when empty

    def test_collection_position_before_chartitems(self):
        """DateTimeFormatCollection must appear before ChartItemCollection."""
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_icon(id='A', type='T')
        root = self._build_xml(chart)

        children = [child.tag for child in root]
        dtfc_idx = children.index('DateTimeFormatCollection')
        cic_idx = children.index('ChartItemCollection')
        assert dtfc_idx < cic_idx


class TestPerItemReference:
    def _build_xml(self, chart):
        xml_str = chart.to_xml()
        return ET.fromstring(xml_str)

    def test_entity_named_format_emits_name(self):
        """Registered name → DateTimeFormat attribute with the name string."""
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_icon(id='A', type='T', date='2024-01-15', datetime_format='ISO')
        root = self._build_xml(chart)

        ci = root.find('.//ChartItemCollection/ChartItem')
        ci_style = ci.find('CIStyle')
        assert ci_style is not None
        assert ci_style.get('DateTimeFormat') == 'ISO'
        assert ci_style.get('DateTimeFormatReference') is None

    def test_entity_unregistered_format_caught_by_validation(self):
        """Unregistered format name is caught by validate()."""
        chart = ANXChart()
        chart.add_icon(id='A', type='T', date='2024-01-15', datetime_format='dd/MM/yyyy')
        errors = chart.validate()
        assert any(e.get('type') == 'unregistered_datetime_format' for e in errors)

    def test_link_named_format_emits_name(self):
        """Registered name → DateTimeFormat attribute with the name string."""
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_icon(id='A', type='T')
        chart.add_icon(id='B', type='T')
        chart.add_link(from_id='A', to_id='B', type='Call',
                       date='2024-01-15', datetime_format='ISO')
        root = self._build_xml(chart)

        for ci in root.findall('.//ChartItemCollection/ChartItem'):
            if ci.find('Link') is not None:
                ci_style = ci.find('CIStyle')
                assert ci_style is not None
                assert ci_style.get('DateTimeFormat') == 'ISO'
                break
        else:
            pytest.fail("No link ChartItem found")

    def test_link_unregistered_format_caught_by_validation(self):
        """Unregistered format name is caught by validate()."""
        chart = ANXChart()
        chart.add_icon(id='A', type='T')
        chart.add_icon(id='B', type='T')
        chart.add_link(from_id='A', to_id='B', type='Call',
                       date='2024-01-15', datetime_format='HH:mm dd-MMM')
        errors = chart.validate()
        assert any(e.get('type') == 'unregistered_datetime_format' for e in errors)

    def test_no_cistyle_when_no_format(self):
        """No CIStyle emitted when datetime_format is not set and no other style fields."""
        chart = ANXChart()
        chart.add_icon(id='A', type='T')
        root = self._build_xml(chart)

        ci = root.find('.//ChartItemCollection/ChartItem')
        assert ci.find('CIStyle') is None


class TestConfigRoundTrip:
    def test_to_config_dict(self):
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_datetime_format(name='BR', format='dd/MM/yyyy')
        cfg = chart.to_config_dict()
        assert 'datetime_formats' in cfg
        assert len(cfg['datetime_formats']) == 2
        names = {d['name'] for d in cfg['datetime_formats']}
        assert names == {'ISO', 'BR'}

    def test_from_dict_with_datetime_formats(self):
        data = {
            'datetime_formats': [
                {'name': 'ISO', 'format': 'yyyy-MM-dd'},
                {'name': 'US', 'format': 'MM/dd/yyyy'},
            ],
            'entities': {
                'icons': [{'id': 'A', 'type': 'T'}],
            },
        }
        chart = ANXChart.from_dict(data)
        assert len(chart._datetime_formats) == 2

    def test_apply_config(self):
        chart = ANXChart()
        chart.apply_config({
            'datetime_formats': [
                {'name': 'ISO', 'format': 'yyyy-MM-dd'},
            ],
        })
        assert len(chart._datetime_formats) == 1
        assert chart._datetime_formats[0].name == 'ISO'


class TestValidation:
    def test_missing_name(self):
        chart = ANXChart()
        chart._datetime_formats.append(DateTimeFormat(name='', format='yyyy'))
        chart.add_icon(id='A', type='T')
        errors = chart.validate()
        assert any(e.get('type') == 'missing_required' and 'DateTimeFormat' in e.get('message', '')
                   for e in errors)

    def test_name_too_long(self):
        chart = ANXChart()
        chart._datetime_formats.append(DateTimeFormat(name='x' * 251, format='yyyy'))
        chart.add_icon(id='A', type='T')
        errors = chart.validate()
        assert any(e.get('type') == 'invalid_value' and '250' in e.get('message', '')
                   for e in errors)

    def test_format_too_long(self):
        chart = ANXChart()
        chart._datetime_formats.append(DateTimeFormat(name='X', format='y' * 260))
        chart.add_icon(id='A', type='T')
        errors = chart.validate()
        assert any(e.get('type') == 'invalid_value' and '259' in e.get('message', '')
                   for e in errors)

    def test_duplicate_name(self):
        chart = ANXChart()
        chart._datetime_formats.append(DateTimeFormat(name='ISO', format='yyyy'))
        chart._datetime_formats.append(DateTimeFormat(name='ISO', format='dd/MM'))
        chart.add_icon(id='A', type='T')
        errors = chart.validate()
        assert any(e.get('type') == 'duplicate_name' and 'DateTimeFormat' in e.get('message', '')
                   for e in errors)

    def test_valid_formats_no_errors(self):
        chart = ANXChart()
        chart.add_datetime_format(name='ISO', format='yyyy-MM-dd')
        chart.add_datetime_format(name='BR', format='dd/MM/yyyy')
        chart.add_icon(id='A', type='T')
        errors = chart.validate()
        # Filter only datetime_format related errors
        dtf_errors = [e for e in errors if 'DateTimeFormat' in e.get('message', '')]
        assert len(dtf_errors) == 0

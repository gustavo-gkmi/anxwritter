"""
Tests that exercise what ``yaml.safe_load`` and ``json.loads`` actually
produce from strings users would type into a real ``.yaml`` or ``.json``
file — not what hand-written Python dict fixtures look like.

Why these exist:

The pre-existing test suite was Python-API-centric.  YAML/JSON tests
typically built fixtures as Python dict literals using already-canonical
forms (``'date': '2024-01-15'``, ``'time': '14:30:00'``).  But
``yaml.safe_load`` of a real user file returns ``datetime.date`` /
``datetime.datetime`` / ``int`` (from sexagesimal time) / ``bool`` (from
YAML 1.1 ``yes``/``no`` sentinels).  The behaviour at those types must
match the canonical-string behaviour, and the boundaries where YAML
auto-parsing can surprise the user must produce clean validation errors
(not crashes).

Each test starts from a *string* and goes through the standard loader,
then asserts the chart builds correctly through ``validate()`` and
``to_xml()``.  This catches a class of bugs that fixture-based tests
silently miss.

Add cases here for any future "user wrote X in YAML and got bitten by
auto-parsing" scenario.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime

import pytest
import yaml

from anxwritter import ANXChart, Color, CustomProperty, Font, GeoMapCfg


# ─────────────────────────────────────────────────────────────────────────
# Date / time auto-parsing
# ─────────────────────────────────────────────────────────────────────────


class TestUnquotedDateInContainers:
    """``date: 2024-01-15`` (unquoted) parses as ``datetime.date``.  The
    loader / validator / builder must accept it everywhere a date string
    is accepted."""

    def test_unquoted_date_in_entity(self):
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      date: 2024-01-15
      time: '10:00:00'
"""))
        assert c.validate() == []
        assert 'DateTime="2024-01-15T10:00:00.000"' in c.to_xml()

    def test_unquoted_date_in_link(self):
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
    - id: B
      type: P
links:
  - from_id: A
    to_id: B
    type: Call
    date: 2024-01-15
    time: '10:00:00'
"""))
        assert c.validate() == []
        # Link ChartItem also gets a DateTime attribute
        assert 'DateTime="2024-01-15T10:00:00.000"' in c.to_xml()

    def test_unquoted_date_in_inline_card(self):
        """Was a hard crash before card-level validation was added (#1)."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      cards:
        - summary: 'evidence'
          date: 2024-01-15
          time: '10:00:00'
"""))
        assert c.validate() == []
        # Card datetime should round-trip with T separator
        m = re.search(r'<Card[^>]*DateTime="([^"]+)"', c.to_xml())
        assert m and m.group(1) == '2024-01-15T10:00:00.000'

    def test_unquoted_date_in_loose_card(self):
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: alice
      type: Person
loose_cards:
  - entity_id: alice
    summary: 'intel'
    date: 2024-03-01
    time: '09:00:00'
"""))
        assert c.validate() == []
        c.to_xml()


class TestUnquotedTimeIsSexagesimalInt:
    """YAML 1.1 parses ``time: 14:30:00`` as ``int(52200)`` (sexagesimal
    base-60 notation: 14*3600 + 30*60 + 0).  Validation must catch this
    with a clear ``invalid_time`` error, not crash the builder."""

    @pytest.mark.parametrize('container_yaml,location_marker', [
        ("""
entities:
  icons:
    - id: A
      type: P
      time: 14:30:00
""", 'entities[0]'),
        ("""
entities:
  icons:
    - id: A
      type: P
    - id: B
      type: P
links:
  - from_id: A
    to_id: B
    type: Call
    time: 14:30:00
""", 'links[0]'),
        ("""
entities:
  icons:
    - id: A
      type: P
      cards:
        - summary: 'x'
          time: 14:30:00
""", 'cards[0]'),
    ])
    def test_unquoted_time_surfaces_as_invalid_time(self, container_yaml, location_marker):
        c = ANXChart.from_dict(yaml.safe_load(container_yaml))
        errs = c.validate()
        time_errs = [e for e in errs if e['type'] == 'invalid_time']
        assert time_errs, f'expected invalid_time error; got {[e["type"] for e in errs]}'
        # Location should point at the right container
        assert any(location_marker in e['location'] for e in time_errs)
        # Message should mention the parsed integer so the user can spot the cause
        assert any('52200' in e['message'] for e in time_errs)


class TestUnquotedDatetimeInSettings:
    """YAML datetime literals in `settings.summary.*` and `settings.time.*`
    must emit ANB-canonical ISO ``T`` separator, not Python's space form."""

    def test_summary_origin_dates_emit_t_separator(self):
        c = ANXChart.from_dict(yaml.safe_load("""
settings:
  summary:
    title: X
    created: 2024-01-15T10:00:00
    last_print: 2024-02-01T08:30:00
    last_save: 2024-03-01
entities:
  icons:
    - id: A
      type: P
"""))
        xml = c.to_xml()
        assert 'CreatedDate="2024-01-15T10:00:00"' in xml
        assert 'LastPrintDate="2024-02-01T08:30:00"' in xml
        assert 'LastSaveDate="2024-03-01"' in xml
        # No space-separated ISO forms anywhere — that's ANB-rejected
        assert ' 10:00:00' not in xml
        assert ' 08:30:00' not in xml

    def test_default_datetime_emits_t_separator(self):
        c = ANXChart.from_dict(yaml.safe_load("""
settings:
  time:
    default_date: 2024-01-15
    default_datetime: 2024-01-15T10:00:00
entities:
  icons:
    - id: A
      type: P
"""))
        xml = c.to_xml()
        assert 'DefaultDate="2024-01-15"' in xml
        assert 'DefaultDateTimeForNewChart="2024-01-15T10:00:00"' in xml


# ─────────────────────────────────────────────────────────────────────────
# YAML 1.1 boolean sentinels
# ─────────────────────────────────────────────────────────────────────────


class TestYaml11BooleanSentinels:
    """``yes`` / ``no`` / ``on`` / ``off`` parse as Python ``bool`` under
    YAML 1.1 (which pyyaml's ``safe_load`` uses).  Relevant for Flag
    attributes and any field that takes a bool."""

    @pytest.mark.parametrize('sentinel,expected_bool', [
        ('yes', True),
        ('no', False),
        ('on', True),
        ('off', False),
        ('true', True),
        ('false', False),
    ])
    def test_sentinel_becomes_flag_attribute(self, sentinel, expected_bool):
        c = ANXChart.from_dict(yaml.safe_load(f"""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Active: {sentinel}
"""))
        assert c.validate() == []
        # bool → Flag attribute, value stringified as 'true'/'false'
        xml = c.to_xml()
        m_class = re.search(r'<AttributeClass[^>]*Name="Active"[^>]*Type="(\w+)"', xml)
        assert m_class and m_class.group(1) == 'AttFlag'
        m_val = re.search(r'<Attribute[^>]*AttributeClass="Active"[^>]*Value="([^"]+)"', xml)
        assert m_val and m_val.group(1) == ('true' if expected_bool else 'false')

    def test_quoted_yes_stays_text(self):
        """Quoting bypasses the sentinel — the user gets a Text attribute
        (e.g. for a literal status string ``"yes"`` from a survey)."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Status: 'yes'
"""))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Status"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttText'
        m_val = re.search(r'<Attribute[^>]*AttributeClass="Status"[^>]*Value="([^"]+)"', xml)
        assert m_val and m_val.group(1) == 'yes'


# ─────────────────────────────────────────────────────────────────────────
# Datetime literals in attribute values
# ─────────────────────────────────────────────────────────────────────────


class TestDatetimeLiteralAttributes:
    """YAML ``Joined: 2024-01-15T10:00:00`` and ``BirthDate: 1990-05-12``
    auto-parse to datetime / date.  Both must produce AttTime."""

    def test_unquoted_yaml_datetime_attribute_is_atttime(self):
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Joined: 2024-01-15T10:00:00
"""))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Joined"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttTime'
        m_val = re.search(r'<Attribute[^>]*AttributeClass="Joined"[^>]*Value="([^"]+)"', xml)
        assert m_val and m_val.group(1) == '2024-01-15T10:00:00'

    def test_unquoted_yaml_date_attribute_is_atttime(self):
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      attributes:
        BirthDate: 1990-05-12
"""))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="BirthDate"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttTime'
        m_val = re.search(r'<Attribute[^>]*AttributeClass="BirthDate"[^>]*Value="([^"]+)"', xml)
        assert m_val and m_val.group(1) == '1990-05-12T00:00:00'

    def test_json_iso_string_undeclared_stays_text(self):
        """JSON has no datetime literal; an ISO-shaped string in JSON
        without a declared ``type: datetime`` AttributeClass must stay
        Text — auto-detection would mis-type opaque IDs like
        ``OrderID: 2024-01-15-A001``."""
        c = ANXChart.from_dict(json.loads('''
        {"entities": {"icons": [
            {"id": "A", "type": "P",
             "attributes": {"Joined": "2024-01-15T10:00:00"}}
        ]}}
        '''))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Joined"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttText'

    def test_json_iso_string_declared_becomes_atttime(self):
        """The escape hatch: declare the attribute as ``type: datetime``
        in ``attribute_classes`` and the JSON loader coerces the string
        to a datetime."""
        c = ANXChart.from_dict(json.loads('''
        {"attribute_classes": [{"name": "Joined", "type": "datetime"}],
         "entities": {"icons": [
            {"id": "A", "type": "P",
             "attributes": {"Joined": "2024-01-15T10:00:00"}}
         ]}}
        '''))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Joined"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttTime'


# ─────────────────────────────────────────────────────────────────────────
# Numeric-looking strings must stay Text, not become Number
# ─────────────────────────────────────────────────────────────────────────


class TestNumericLookingStrings:
    """Phone numbers, account IDs, and other string values that *look*
    numeric must stay Text.  The user has to quote them in YAML — and
    when they do, the loader must respect that (no auto-conversion to
    int/float)."""

    @pytest.mark.parametrize('quoted_value,expected', [
        ("'555-0001'",       '555-0001'),
        ("'(555) 010-0123'", '(555) 010-0123'),
        ("'00042'",          '00042'),       # leading-zero ID — not octal
        ("'1.2.3'",          '1.2.3'),       # version string — not a number
        ("'2024-01-15-A001'", '2024-01-15-A001'),  # opaque ID — not a date
    ])
    def test_quoted_numeric_looking_string_stays_text(self, quoted_value, expected):
        c = ANXChart.from_dict(yaml.safe_load(f"""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Field: {quoted_value}
"""))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Field"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttText'
        m_val = re.search(r'<Attribute[^>]*AttributeClass="Field"[^>]*Value="([^"]+)"', xml)
        assert m_val and m_val.group(1) == expected

    def test_unquoted_int_becomes_number(self):
        """Sanity check: an unquoted integer in YAML *should* be Number."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Age: 39
"""))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Age"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttNumber'

    def test_unquoted_float_becomes_number(self):
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Balance: 12500.50
"""))
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="Balance"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttNumber'


# ─────────────────────────────────────────────────────────────────────────
# Special characters in YAML scalars
# ─────────────────────────────────────────────────────────────────────────


class TestSpecialCharacterStrings:
    """Values containing YAML-special characters (``>``, ``<``, ``#``,
    ``:``, ``&``, ``*``, …) must be quoted by the user.  The loader's
    job is just to accept the resulting string — but we also want a
    sanity check that quoted forms produce the expected XML."""

    def test_arrow_quoted(self):
        """``arrow:`` value — must be quoted in YAML."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
    - id: B
      type: P
links:
  - from_id: A
    to_id: B
    type: Call
    arrow: '->'
"""))
        assert c.validate() == []
        assert 'ArrowStyle="ArrowOnHead"' in c.to_xml()

    def test_hex_color_quoted(self):
        """``#FF0000`` — ``#`` starts a YAML comment if unquoted."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      color: '#FF0000'
"""))
        assert c.validate() == []
        # The COLORREF for #FF0000 is 0x0000FF (BGR) = 255
        assert 'IconShadingColour="255"' in c.to_xml()

    def test_unquoted_hex_color_silently_dropped(self):
        """Sanity check: unquoted ``#FF0000`` becomes a comment, so
        ``color:`` ends up null and the entity has no shading.  This
        documents the failure mode for the user."""
        # PyYAML sees `color: ` followed by the comment and gives None
        loaded = yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      color: #FF0000
""")
        assert loaded['entities']['icons'][0].get('color') is None

    def test_url_with_colon_quoted(self):
        """A URL value containing ``:`` must be quoted."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      attributes:
        Website: 'https://example.com/path'
"""))
        assert c.validate() == []
        m = re.search(r'<Attribute[^>]*AttributeClass="Website"[^>]*Value="([^"]+)"', c.to_xml())
        assert m and m.group(1) == 'https://example.com/path'

    def test_text_with_ampersand_xml_escaped(self):
        """``&`` in a text value must be XML-escaped on output (else the
        ANX file is malformed XML)."""
        c = ANXChart.from_dict(yaml.safe_load("""
entities:
  icons:
    - id: A
      type: P
      label: 'Alice & Bob'
"""))
        xml = c.to_xml()
        # Must appear escaped, not literal
        assert 'Alice &amp; Bob' in xml
        assert 'Alice & Bob"' not in xml


# ─────────────────────────────────────────────────────────────────────────
# Path symmetry — same input through every loader path produces same state
# ─────────────────────────────────────────────────────────────────────────


class TestPathSymmetry:
    """A given configuration must produce the same Python state and the
    same XML regardless of which loader path is used.  Catches bugs like
    #4 (``custom_properties`` items stayed as dicts via from_dict but
    were ``CustomProperty`` instances via the constructor)."""

    @staticmethod
    def _strip_origin(xml: str) -> str:
        """Origin's CreatedDate timestamp is auto-generated — strip it
        so XML comparison across paths isn't fooled by clock skew."""
        return re.sub(r'<Origin [^/]*/>', '<Origin/>', xml)

    def test_settings_font_identical_across_paths(self):
        """``settings.font`` (the chart-level default font) must produce
        identical output through constructor / from_dict / apply_config."""
        spec = {'font': {'name': 'Arial', 'size': 12, 'bold': True, 'color': 'Red'}}

        a = ANXChart(settings=spec)
        a.add_icon(id='X', type='Person')

        b = ANXChart.from_dict({'settings': spec, 'entities': {'icons': [{'id': 'X', 'type': 'Person'}]}})

        c = ANXChart()
        c.apply_config({'settings': spec})
        c.add_icon(id='X', type='Person')

        # All three Settings should have a Font with the same fields
        for ch in (a, b, c):
            assert isinstance(ch.settings.font, Font)
            assert ch.settings.font.name == 'Arial'
            assert ch.settings.font.size == 12
            assert ch.settings.font.bold is True

        # XML output should match (modulo auto-generated origin timestamp)
        xa, xb, xc = (self._strip_origin(ch.to_xml()) for ch in (a, b, c))
        assert xa == xb == xc

    def test_geo_map_identical_across_paths(self):
        """``settings.extra_cfg.geo_map`` must round-trip to GeoMapCfg
        through every path."""
        spec = {'extra_cfg': {'geo_map': {
            'attribute_name': 'City',
            'mode': 'both',
            'data': {'NYC': [40.7, -74.0]},
        }}}

        a = ANXChart(settings=spec)
        a.add_icon(id='X', type='Person', attributes={'City': 'NYC'})

        b = ANXChart.from_dict({
            'settings': spec,
            'entities': {'icons': [{'id': 'X', 'type': 'Person', 'attributes': {'City': 'NYC'}}]},
        })

        c = ANXChart()
        c.apply_config({'settings': spec})
        c.add_icon(id='X', type='Person', attributes={'City': 'NYC'})

        for ch in (a, b, c):
            gm = ch.settings.extra_cfg.geo_map
            assert isinstance(gm, GeoMapCfg)
            assert gm.attribute_name == 'City'
            assert gm.data == {'NYC': [40.7, -74.0]}

    def test_custom_properties_identical_across_paths(self):
        """Regression for #4 — already covered, but pin it here under
        the symmetry suite so future contributors find it."""
        spec = {'summary': {'custom_properties': [
            {'name': 'Case', 'value': 'CR-001'},
            {'name': 'Class', 'value': 'RESTRICTED'},
        ]}}

        a = ANXChart(settings=spec)
        b = ANXChart.from_dict({'settings': spec})
        c = ANXChart()
        c.apply_config({'settings': spec})
        d = ANXChart()
        d.add_custom_property('Case', 'CR-001')
        d.add_custom_property('Class', 'RESTRICTED')

        for ch in (a, b, c, d):
            cps = ch.settings.summary.custom_properties
            assert all(isinstance(cp, CustomProperty) for cp in cps), \
                f'expected CustomProperty instances, got {[type(cp).__name__ for cp in cps]}'
            assert [(cp.name, cp.value) for cp in cps] == [
                ('Case', 'CR-001'), ('Class', 'RESTRICTED'),
            ]

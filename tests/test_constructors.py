"""Tests for from_dict, from_json, from_json_file, from_yaml, from_yaml_file parsing."""

import json
import pytest
import yaml
from anxwritter import ANXChart, Card


BASIC_DICT = {
    "entities": {
        "icons": [
            {"id": "Alice", "type": "Person"},
            {"id": "Bob", "type": "Person"},
        ]
    },
    "links": [
        {"from_id": "Alice", "to_id": "Bob", "type": "Call"}
    ],
}


class TestFromDict:
    def test_basic(self):
        c = ANXChart.from_dict(BASIC_DICT)
        icons = [e for e in c._entities if type(e).__name__ == 'Icon']
        assert len(icons) == 2
        assert len(c._links) == 1

    def test_with_settings(self):
        data = {**BASIC_DICT, "settings": {"extra_cfg": {"arrange": "grid"}}}
        c = ANXChart.from_dict(data)
        assert c.settings.extra_cfg.arrange == 'grid'

    def test_with_boxes(self):
        data = {
            "entities": {
                "icons": [{"id": "A", "type": "T"}],
                "boxes": [{"id": "B", "type": "Org", "width": 150}],
            }
        }
        c = ANXChart.from_dict(data)
        from anxwritter.entities import Icon, Box
        icons = [e for e in c._entities if isinstance(e, Icon)]
        boxes = [e for e in c._entities if isinstance(e, Box)]
        assert len(icons) == 1
        assert len(boxes) == 1

    def test_with_attribute_classes(self):
        data = {
            **BASIC_DICT,
            "attribute_classes": [{"name": "phone", "type": "Text", "prefix": "Tel: "}],
        }
        c = ANXChart.from_dict(data)
        assert len(c._attribute_classes) == 1

    def test_with_strengths(self):
        data = {
            **BASIC_DICT,
            "strengths": {"items": [{"name": "Confirmed", "dot_style": "DotStyleSolid"}]},
        }
        c = ANXChart.from_dict(data)
        # Default 'Default' + 1 from data
        names = [st.name for st in c.strengths]
        assert 'Confirmed' in names

    def test_with_grades(self):
        data = {
            **BASIC_DICT,
            "grades_one": {"items": ["Reliable", "Unreliable"]},
        }
        c = ANXChart.from_dict(data)
        assert len(c.grades_one) == 2

    def test_empty_dict(self):
        c = ANXChart.from_dict({})
        assert c.validate() == []

    def test_produces_valid_xml(self):
        c = ANXChart.from_dict(BASIC_DICT)
        xml = c.to_xml()
        assert '<?xml' in xml or '<Chart' in xml


class TestFromJson:
    def test_basic(self):
        c = ANXChart.from_json(json.dumps(BASIC_DICT))
        icons = [e for e in c._entities if type(e).__name__ == 'Icon']
        assert len(icons) == 2

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            ANXChart.from_json("{bad json")


class TestFromJsonFile:
    def test_basic(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(BASIC_DICT), encoding="utf-8")
        c = ANXChart.from_json_file(str(p))
        icons = [e for e in c._entities if type(e).__name__ == 'Icon']
        assert len(icons) == 2
        assert len(c._links) == 1


# ── YAML constructors ────────────────────────────────────────────────────────

YAML_STR = """\
settings:
  extra_cfg:
    arrange: grid
entities:
  icons:
    - id: Alice
      type: Person
    - id: Bob
      type: Person
links:
  - from_id: Alice
    to_id: Bob
    type: Call
"""


class TestFromYaml:
    def test_basic(self):
        c = ANXChart.from_yaml(YAML_STR)
        icons = [e for e in c._entities if type(e).__name__ == 'Icon']
        assert len(icons) == 2
        assert len(c._links) == 1

    def test_with_settings(self):
        c = ANXChart.from_yaml(YAML_STR)
        assert c.settings.extra_cfg.arrange == 'grid'

    def test_invalid_yaml_raises(self):
        with pytest.raises(Exception):
            ANXChart.from_yaml("{{{{invalid yaml: [")


class TestFromYamlFile:
    def test_basic(self, tmp_path):
        p = tmp_path / "test.yaml"
        p.write_text(YAML_STR, encoding="utf-8")
        c = ANXChart.from_yaml_file(str(p))
        icons = [e for e in c._entities if type(e).__name__ == 'Icon']
        assert len(icons) == 2
        assert len(c._links) == 1

    def test_yml_extension(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text(YAML_STR, encoding="utf-8")
        c = ANXChart.from_yaml_file(str(p))
        assert len(c._entities) == 2


# ── from_dict completeness ────────────────────────────────────────────────────

class TestFromDictComplete:
    def test_with_entity_types(self):
        data = {
            **BASIC_DICT,
            "entity_types": [{"name": "Person", "icon_file": "person", "color": "Blue"}],
        }
        c = ANXChart.from_dict(data)
        assert len(c._entity_types) == 1
        assert c._entity_types[0].name == 'Person'

    def test_with_link_types(self):
        data = {
            **BASIC_DICT,
            "link_types": [{"name": "Call", "color": 255}],
        }
        c = ANXChart.from_dict(data)
        assert len(c._link_types) == 1
        assert c._link_types[0].name == 'Call'

    def test_with_source_types(self):
        data = {
            **BASIC_DICT,
            "source_types": ["Witness", "Informant", "Intelligence"],
        }
        c = ANXChart.from_dict(data)
        assert c.source_types == ["Witness", "Informant", "Intelligence"]

    def test_with_grades_two_three(self):
        data = {
            **BASIC_DICT,
            "grades_two": {"items": ["Confirmed", "Probably true"]},
            "grades_three": {"items": ["High", "Medium", "Low"]},
        }
        c = ANXChart.from_dict(data)
        assert len(c.grades_two) == 2
        assert len(c.grades_three) == 3

    def test_with_legend_items(self):
        data = {
            **BASIC_DICT,
            "legend_items": [
                {"name": "Person", "item_type": "Icon"},
                {"name": "Owns", "item_type": "Link", "color": 0, "line_width": 1},
            ],
        }
        c = ANXChart.from_dict(data)
        assert len(c._legend_items) == 2

    def test_with_links_and_attributes(self):
        data = {
            "entities": {"icons": [
                {"id": "A", "type": "T"},
                {"id": "B", "type": "T"},
            ]},
            "links": [{
                "from_id": "A", "to_id": "B", "type": "Call",
                "arrow": "ArrowOnHead", "date": "2024-01-15",
                "attributes": {"duration": 120},
            }],
        }
        c = ANXChart.from_dict(data)
        assert c._links[0].arrow == "ArrowOnHead"
        assert c._links[0].date == "2024-01-15"
        assert c._links[0].attributes == {"duration": 120}

    def test_with_all_entity_representations(self):
        data = {
            "entities": {
                "icons": [{"id": "I1", "type": "T"}],
                "boxes": [{"id": "B1", "type": "T", "width": 100}],
                "circles": [{"id": "C1", "type": "T", "diameter": 80}],
                "theme_lines": [{"id": "TL1", "type": "T"}],
                "event_frames": [{"id": "EF1", "type": "T"}],
                "text_blocks": [{"id": "TB1", "type": "T"}],
                "labels": [{"id": "LB1", "type": "T"}],
            },
        }
        c = ANXChart.from_dict(data)
        assert len(c._entities) == 7
        type_names = {type(e).__name__ for e in c._entities}
        assert type_names == {'Icon', 'Box', 'Circle', 'ThemeLine', 'EventFrame', 'TextBlock', 'Label'}

    def test_with_entity_cards(self):
        data = {
            "entities": {
                "icons": [{
                    "id": "A", "type": "T",
                    "cards": [{"summary": "Note 1", "date": "2024-01-15"}],
                }],
            },
        }
        c = ANXChart.from_dict(data)
        assert len(c._entities[0].cards) == 1
        assert isinstance(c._entities[0].cards[0], Card)
        assert c._entities[0].cards[0].summary == "Note 1"

    def test_full_roundtrip(self):
        """from_dict with ALL sections → to_xml produces valid XML."""
        data = {
            "settings": {"extra_cfg": {"arrange": "grid", "entity_auto_color": True}},
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person", "color": "Blue"},
                    {"id": "B", "type": "Person"},
                ],
            },
            "links": [{"from_id": "A", "to_id": "B", "type": "Call"}],
            "entity_types": [{"name": "Person", "icon_file": "person"}],
            "link_types": [{"name": "Call", "color": 255}],
            "attribute_classes": [{"name": "Phone", "type": "Text", "prefix": "Tel: "}],
            "strengths": {"items": [{"name": "Confirmed", "dot_style": "DotStyleSolid"}]},
            "grades_one": {"items": ["Reliable", "Unreliable"]},
            "grades_two": {"items": ["Confirmed"]},
            "grades_three": {"items": ["High", "Low"]},
            "source_types": ["Witness"],
            "legend_items": [{"name": "Person", "item_type": "Icon"}],
        }
        c = ANXChart.from_dict(data)
        xml = c.to_xml()
        assert '<Chart' in xml

    def test_none_values_filtered(self):
        data = {
            "entities": {
                "icons": [{"id": "A", "type": "T", "color": None, "label": None}],
            },
        }
        c = ANXChart.from_dict(data)
        assert len(c._entities) == 1
        assert c._entities[0].color is None


# ── AttributeClass type inference via the YAML path ─────────────────────────

# Regression: this mirrors the exact path the compiled CLI takes when
# invoked as `anxwritter --config config.yaml data.yaml -o out.anx`. A prior
# bug in _parse_attrs (capitalized vs lowercase type strings) made every
# attribute silently emit Type="AttText" regardless of the Python value,
# which surfaced only at ANB import time with "Invalid paste behaviour for
# classes of this type". These tests lock the behaviour down end-to-end.

import xml.etree.ElementTree as ET


DATA_YAML = """\
entities:
  icons:
    - id: alice
      type: Person
      attributes:
        Phone: "555-0001"
        Balance: 12500.50
        CallCount: 7
        Active: true
    - id: bob
      type: Person
      attributes:
        Phone: "555-0002"
        Balance: 200.00
        CallCount: 3
        Active: false
links:
  - from_id: alice
    to_id: bob
    type: Call
    attributes:
      Duration: 120
      Confirmed: true
"""

CONFIG_YAML = """\
attribute_classes:
  - name: Phone
    type: Text
    prefix: 'Tel: '
    merge_behaviour: AttMergeAddWithSpace
    paste_behaviour: AttMergeAssign
  - name: Balance
    type: Number
    decimal_places: 2
    merge_behaviour: AttMergeAdd
    paste_behaviour: AttMergeMax
  - name: CallCount
    type: Number
    merge_behaviour: AttMergeAdd
    paste_behaviour: AttMergeMax
  - name: Active
    type: Flag
    show_if_set: true
    merge_behaviour: AttMergeOR
    paste_behaviour: AttMergeXOR
  - name: Duration
    type: Number
    merge_behaviour: AttMergeAdd
    paste_behaviour: AttMergeAdd
  - name: Confirmed
    type: Flag
    merge_behaviour: AttMergeAND
    paste_behaviour: AttMergeOR
"""


def _ac_types(chart: ANXChart) -> dict:
    root = ET.fromstring(chart.to_xml())
    return {
        ac.get('Name'): ac.get('Type')
        for ac in root.findall('.//AttributeClassCollection/AttributeClass')
    }


class TestYamlAttributeTypeInference:
    """The YAML path (data + config) must produce correctly-typed AttributeClass entries."""

    def test_types_from_yaml_data_only(self):
        c = ANXChart.from_yaml(DATA_YAML)
        types = _ac_types(c)
        assert types['Phone']     == 'AttText'
        assert types['Balance']   == 'AttNumber'
        assert types['CallCount'] == 'AttNumber'
        assert types['Active']    == 'AttFlag'
        assert types['Duration']  == 'AttNumber'
        assert types['Confirmed'] == 'AttFlag'

    def test_types_from_yaml_file_plus_config_file(self, tmp_path):
        data_path = tmp_path / "data.yaml"
        cfg_path = tmp_path / "config.yaml"
        data_path.write_text(DATA_YAML, encoding="utf-8")
        cfg_path.write_text(CONFIG_YAML, encoding="utf-8")

        c = ANXChart.from_yaml_file(str(data_path))
        c.apply_config_file(str(cfg_path))
        types = _ac_types(c)

        assert types['Phone']     == 'AttText'
        assert types['Balance']   == 'AttNumber'
        assert types['CallCount'] == 'AttNumber'
        assert types['Active']    == 'AttFlag'
        assert types['Duration']  == 'AttNumber'
        assert types['Confirmed'] == 'AttFlag'

    def test_yaml_path_validates_merge_paste_per_type(self, tmp_path):
        """Full YAML round-trip + validate() must flag per-type behaviour errors."""
        data_path = tmp_path / "data.yaml"
        cfg_path = tmp_path / "bad_config.yaml"
        data_path.write_text(DATA_YAML, encoding="utf-8")
        cfg_path.write_text(
            "attribute_classes:\n"
            "  - name: Phone\n"          # Text — merge_behaviour=max is invalid
            "    type: Text\n"
            "    merge_behaviour: max\n"
            "  - name: CallCount\n"      # Number — paste_behaviour=xor is invalid
            "    type: Number\n"
            "    paste_behaviour: xor\n"
            "  - name: Active\n"         # Flag — paste_behaviour=subtract is invalid
            "    type: Flag\n"
            "    paste_behaviour: subtract\n",
            encoding="utf-8",
        )
        c = ANXChart.from_yaml_file(str(data_path))
        c.apply_config_file(str(cfg_path))
        errors = c.validate()

        by_name = {}
        for e in errors:
            if e['type'] in ('invalid_merge_behaviour', 'invalid_paste_behaviour'):
                for key in ('Phone', 'CallCount', 'Active'):
                    if key in e['message']:
                        by_name[key] = e['type']
        assert by_name == {
            'Phone':     'invalid_merge_behaviour',
            'CallCount': 'invalid_paste_behaviour',
            'Active':    'invalid_paste_behaviour',
        }

    def test_yaml_path_happy_path_no_errors(self, tmp_path):
        """The valid YAML fixture above must load, apply config, and validate clean."""
        data_path = tmp_path / "data.yaml"
        cfg_path = tmp_path / "config.yaml"
        data_path.write_text(DATA_YAML, encoding="utf-8")
        cfg_path.write_text(CONFIG_YAML, encoding="utf-8")

        c = ANXChart.from_yaml_file(str(data_path))
        c.apply_config_file(str(cfg_path))
        errors = c.validate()
        behaviour_errors = [
            e for e in errors
            if e['type'] in ('invalid_merge_behaviour', 'invalid_paste_behaviour')
        ]
        assert behaviour_errors == []


class TestNestedDataclassDictNormalization:
    """from_dict (and therefore from_yaml/from_json) must convert nested
    dict fields back into the expected dataclass types so that the YAML/JSON
    path doesn't crash when the builder later accesses ``.color``/``.bold``/
    ``.description``/etc. on what was supposed to be a Font / Show / Frame
    instance.

    Regression coverage for the silent crash documented in the YAML/JSON
    audit: previously ``label_font: {color: 'red'}`` raised
    ``AttributeError: 'dict' object has no attribute 'color'`` during
    ``validate()`` (label_font/frame) or ``to_xml()`` (show).
    """

    def test_label_font_dict_on_entity(self):
        from anxwritter import Font
        c = ANXChart.from_dict({
            'entities': {'icons': [{
                'id': 'A', 'type': 'P',
                'label_font': {'color': 'red', 'bold': True, 'size': 12},
            }]},
        })
        icon = c._entities[0]
        assert isinstance(icon.label_font, Font)
        assert icon.label_font.color == 'red'
        assert icon.label_font.bold is True
        assert icon.label_font.size == 12
        # End-to-end: validate + to_xml must not crash
        assert c.validate() == []
        c.to_xml()

    def test_show_dict_on_entity(self):
        from anxwritter import Show
        c = ANXChart.from_dict({
            'entities': {'icons': [{
                'id': 'A', 'type': 'P',
                'show': {'description': True, 'date': True, 'label': True},
            }]},
        })
        icon = c._entities[0]
        assert isinstance(icon.show, Show)
        assert icon.show.description is True
        assert icon.show.date is True
        assert c.validate() == []
        c.to_xml()

    def test_frame_dict_on_icon(self):
        from anxwritter import Frame
        c = ANXChart.from_dict({
            'entities': {'icons': [{
                'id': 'A', 'type': 'P',
                'frame': {'color': 16764057, 'visible': True, 'margin': 5},
            }]},
        })
        icon = c._entities[0]
        assert isinstance(icon.frame, Frame)
        assert icon.frame.visible is True
        assert icon.frame.margin == 5
        assert c.validate() == []
        c.to_xml()

    def test_frame_dict_dropped_on_box(self):
        # Frame is only valid on Icon and ThemeLine.  Passing it to Box used
        # to fail silently downstream; the loader now strips it on
        # construction so the YAML user gets a clean Box rather than a crash.
        c = ANXChart.from_dict({
            'entities': {'boxes': [{
                'id': 'B', 'type': 'Loc',
                'frame': {'visible': True},
            }]},
        })
        box = c._entities[0]
        assert not hasattr(box, 'frame') or getattr(box, 'frame', None) is None
        assert c.validate() == []
        c.to_xml()

    def test_frame_dict_dropped_on_link(self):
        # Link has no frame field — should be silently dropped, not raise
        # TypeError from the Link constructor.
        c = ANXChart.from_dict({
            'entities': {'icons': [
                {'id': 'A', 'type': 'P'}, {'id': 'B', 'type': 'P'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'Call',
                'frame': {'visible': True},
            }],
        })
        assert not hasattr(c._links[0], 'frame')
        assert c.validate() == []
        c.to_xml()

    def test_label_font_show_dict_on_link(self):
        from anxwritter import Font, Show
        c = ANXChart.from_dict({
            'entities': {'icons': [
                {'id': 'A', 'type': 'P'}, {'id': 'B', 'type': 'P'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'Call',
                'label_font': {'italic': True, 'color': 'blue'},
                'show': {'description': True},
            }],
        })
        link = c._links[0]
        assert isinstance(link.label_font, Font)
        assert link.label_font.italic is True
        assert isinstance(link.show, Show)
        assert link.show.description is True
        assert c.validate() == []
        c.to_xml()

    def test_attribute_class_font_dict(self):
        from anxwritter import Font
        c = ANXChart.from_dict({
            'attribute_classes': [{
                'name': 'Notes', 'type': 'text',
                'font': {'bold': True, 'color': 'red'},
            }],
            'entities': {'icons': [{'id': 'A', 'type': 'P'}]},
        })
        ac = c._attribute_classes[0]
        assert isinstance(ac.font, Font)
        assert ac.font.bold is True
        assert ac.font.color == 'red'
        assert c.validate() == []
        c.to_xml()

    def test_legend_item_font_dict(self):
        from anxwritter import Font
        c = ANXChart.from_dict({
            'legend_items': [{
                'name': 'Important', 'item_type': 'font',
                'font': {'bold': True, 'color': 'red'},
            }],
            'entities': {'icons': [{'id': 'A', 'type': 'P'}]},
        })
        li = c._legend_items[0]
        assert isinstance(li.font, Font)
        assert li.font.bold is True
        assert c.validate() == []
        c.to_xml()

    def test_mixed_dict_and_dataclass_instances(self):
        """Loader must accept dict form and dataclass instance form
        in the same chart and produce identical post-load state."""
        from anxwritter import Font
        c = ANXChart.from_dict({
            'entities': {'icons': [
                {'id': 'A', 'type': 'P', 'label_font': {'bold': True}},
                {'id': 'B', 'type': 'P', 'label_font': Font(bold=True)},
            ]},
        })
        a, b = c._entities
        assert isinstance(a.label_font, Font)
        assert isinstance(b.label_font, Font)
        assert a.label_font.bold == b.label_font.bold

    def test_via_yaml_string(self):
        """End-to-end: a realistic YAML document with nested dataclass
        fields as YAML mappings must parse and build cleanly."""
        from anxwritter import Font, Show, Frame
        text = """
entities:
  icons:
    - id: Alice
      type: Person
      label_font:
        color: red
        bold: true
      show:
        description: true
        date: true
      frame:
        color: 16764057
        visible: true
attribute_classes:
  - name: Notes
    type: text
    font:
      bold: true
links: []
"""
        c = ANXChart.from_yaml(text)
        icon = c._entities[0]
        assert isinstance(icon.label_font, Font)
        assert isinstance(icon.show, Show)
        assert isinstance(icon.frame, Frame)
        assert isinstance(c._attribute_classes[0].font, Font)
        assert c.validate() == []
        c.to_xml()


class TestDeclaredDatetimeCoercion:
    """JSON has no datetime literal, so a string value like
    ``"Joined": "2024-01-15T10:00:00"`` would otherwise become a Text
    attribute (AttText).  When the user declares the attribute as
    ``type: datetime`` in ``attribute_classes`` the loader coerces
    matching string values to ``datetime`` instances so the resulting
    chart has the same shape as the YAML or Python equivalents.
    """

    @staticmethod
    def _ac_type_in_xml(xml: str, ac_name: str) -> str:
        """Pull the Type attribute of a named <AttributeClass> out of XML."""
        import re
        m = re.search(
            r'<AttributeClass[^>]*Name="' + re.escape(ac_name) + r'"[^>]*Type="(\w+)"',
            xml,
        )
        return m.group(1) if m else ''

    def test_iso_string_coerced_to_datetime(self):
        from datetime import datetime
        import json
        data = json.loads('''{
            "attribute_classes": [{"name": "Joined", "type": "datetime"}],
            "entities": {"icons": [{
                "id": "alice", "type": "Person",
                "attributes": {"Joined": "2024-01-15T10:00:00"}
            }]}
        }''')
        c = ANXChart.from_dict(data)
        ent = c._entities[0]
        assert isinstance(ent.attributes['Joined'], datetime)
        assert ent.attributes['Joined'] == datetime(2024, 1, 15, 10, 0, 0)
        assert c.validate() == []
        xml = c.to_xml()
        # Builder maps datetime → AttTime (not AttText).
        assert self._ac_type_in_xml(xml, 'Joined') == 'AttTime'

    def test_iso_date_only_coerced(self):
        """Date-only ISO strings like ``2024-01-15`` are accepted (loader
        falls back through ``_ATTR_DATETIME_FORMATS``)."""
        from datetime import datetime
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'Joined', 'type': 'datetime'}],
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Joined': '2024-01-15'},
            }]},
        })
        assert c._entities[0].attributes['Joined'] == datetime(2024, 1, 15)
        assert c.validate() == []
        c.to_xml()

    def test_iso_with_z_suffix_coerced(self):
        """A trailing ``Z`` (UTC marker) is stripped before parsing — Python
        3.10's ``fromisoformat`` rejects ``Z`` so we have to handle it."""
        from datetime import datetime
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'Joined', 'type': 'datetime'}],
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Joined': '2024-01-15T10:00:00Z'},
            }]},
        })
        assert c._entities[0].attributes['Joined'] == datetime(2024, 1, 15, 10, 0, 0)
        c.to_xml()

    def test_iso_with_microseconds_coerced(self):
        from datetime import datetime
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'Ts', 'type': 'datetime'}],
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Ts': '2024-01-15T10:00:00.500000'},
            }]},
        })
        assert c._entities[0].attributes['Ts'] == datetime(2024, 1, 15, 10, 0, 0, 500000)

    def test_undeclared_attribute_not_coerced(self):
        """An ISO-shaped string in an attribute that isn't declared as
        ``type: datetime`` must stay as a string — no false-positive
        coercion."""
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'Joined', 'type': 'datetime'}],
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'OrderID': '2024-01-15-A001'},
            }]},
        })
        # OrderID was never declared as datetime — stays as str (Text attr)
        assert isinstance(c._entities[0].attributes['OrderID'], str)
        assert c._entities[0].attributes['OrderID'] == '2024-01-15-A001'
        assert c.validate() == []

    def test_non_iso_value_left_as_string(self):
        """A declared datetime attribute whose value can't be parsed is
        left untouched.  Validation then surfaces the inconsistency as a
        ``type_conflict`` so the user gets an actionable error rather
        than a silently-mis-typed value."""
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'Joined', 'type': 'datetime'}],
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Joined': 'unknown'},
            }]},
        })
        assert c._entities[0].attributes['Joined'] == 'unknown'
        errs = c.validate()
        # type_conflict: declared datetime but inferred text
        assert any(e['type'] == 'type_conflict' for e in errs)

    def test_python_datetime_passes_through(self):
        """Already-typed datetime instances on the Python API path are
        left unchanged (no double-conversion)."""
        from datetime import datetime
        original = datetime(2024, 1, 15, 10, 0, 0)
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'Joined', 'type': 'datetime'}],
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Joined': original},
            }]},
        })
        assert c._entities[0].attributes['Joined'] is original

    def test_no_attribute_classes_disables_coercion(self):
        """Without any AC declarations the coercion path is a no-op —
        prior behaviour preserved for callers that don't use AC."""
        c = ANXChart.from_dict({
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Joined': '2024-01-15T10:00:00'},
            }]},
        })
        # No AC declared → string stays as string (Text attribute)
        assert isinstance(c._entities[0].attributes['Joined'], str)

    def test_coercion_applies_to_links_too(self):
        from datetime import datetime
        c = ANXChart.from_dict({
            'attribute_classes': [{'name': 'CallTime', 'type': 'datetime'}],
            'entities': {'icons': [
                {'id': 'A', 'type': 'P'}, {'id': 'B', 'type': 'P'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'Call',
                'attributes': {'CallTime': '2024-01-15T10:00:00'},
            }],
        })
        assert c._links[0].attributes['CallTime'] == datetime(2024, 1, 15, 10, 0, 0)
        assert c.validate() == []
        xml = c.to_xml()
        assert self._ac_type_in_xml(xml, 'CallTime') == 'AttTime'

    def test_config_locked_datetime_declaration_drives_coercion(self):
        """An ``attribute_classes`` declaration coming from a layered
        config (not the data file) still drives coercion of values in
        the data file."""
        from datetime import datetime
        c = ANXChart()
        c.apply_config({
            'attribute_classes': [{'name': 'Joined', 'type': 'datetime'}],
        })
        c._apply_data({
            'entities': {'icons': [{
                'id': 'a', 'type': 'P',
                'attributes': {'Joined': '2024-01-15T10:00:00'},
            }]},
        })
        assert c._entities[0].attributes['Joined'] == datetime(2024, 1, 15, 10, 0, 0)
        assert c.validate() == []

    def test_via_yaml_string(self):
        """End-to-end: declared-datetime + JSON-style quoted ISO string in
        a real YAML document."""
        from datetime import datetime
        text = """
attribute_classes:
  - name: Joined
    type: datetime
entities:
  icons:
    - id: alice
      type: Person
      attributes:
        Joined: '2024-01-15T10:00:00'
"""
        c = ANXChart.from_yaml(text)
        assert c._entities[0].attributes['Joined'] == datetime(2024, 1, 15, 10, 0, 0)
        assert c.validate() == []
        c.to_xml()


class TestYamlDateLiteralAttribute:
    """Issue #7 — YAML's auto-parsed date literals as attribute values
    must produce a DateTime-typed attribute (AttTime), not Text."""

    def test_yaml_unquoted_date_attribute_becomes_atttime(self):
        import yaml, re
        text = """
entities:
  icons:
    - id: A
      type: P
      attributes:
        BirthDate: 1990-05-12
"""
        c = ANXChart.from_dict(yaml.safe_load(text))
        assert c.validate() == []
        xml = c.to_xml()
        m = re.search(r'<AttributeClass[^>]*Name="BirthDate"[^>]*Type="(\w+)"', xml)
        assert m and m.group(1) == 'AttTime'
        # Value should be ISO datetime with T separator and midnight time
        av = re.search(
            r'<Attribute[^>]*AttributeClass="BirthDate"[^>]*Value="([^"]+)"', xml,
        )
        assert av and av.group(1) == '1990-05-12T00:00:00'


class TestCustomPropertiesViaFromDict:
    """Issue #4 — ``summary.custom_properties`` items must be converted
    to ``CustomProperty`` instances regardless of which loader path is
    used (constructor, from_dict, apply_config, apply_config_file)."""

    DATA = {
        'settings': {'summary': {
            'title': 'X',
            'custom_properties': [
                {'name': 'Case', 'value': 'CR-001'},
                {'name': 'Class', 'value': 'RESTRICTED'},
            ],
        }},
        'entities': {'icons': [{'id': 'A', 'type': 'P'}]},
    }

    def _assert_typed(self, chart):
        from anxwritter import CustomProperty
        cps = chart.settings.summary.custom_properties
        assert len(cps) == 2
        assert all(isinstance(cp, CustomProperty) for cp in cps), \
            f'expected CustomProperty instances, got {[type(cp).__name__ for cp in cps]}'
        assert cps[0].name == 'Case' and cps[0].value == 'CR-001'

    def test_from_dict_path(self):
        self._assert_typed(ANXChart.from_dict(self.DATA))

    def test_constructor_path(self):
        self._assert_typed(ANXChart(settings=self.DATA['settings']))

    def test_apply_config_path(self):
        c = ANXChart()
        c.apply_config({'settings': self.DATA['settings']})
        self._assert_typed(c)

    def test_xml_round_trip_consistent(self):
        """All three paths must produce the same custom-property XML."""
        import re
        from anxwritter import CustomProperty
        chart_a = ANXChart.from_dict(self.DATA)
        chart_b = ANXChart(settings=self.DATA['settings'])
        chart_c = ANXChart()
        chart_c.add_custom_property('Case', 'CR-001')
        chart_c.add_custom_property('Class', 'RESTRICTED')
        xmls = [chart_a.to_xml(), chart_b.to_xml(), chart_c.to_xml()]
        # Extract only the <CustomProperty> elements (other XML differs)
        props = [re.findall(r'<CustomProperty [^/]+/>', x) for x in xmls]
        assert props[0] == props[1] == props[2]


class TestYamlDatetimeLiteralInSettings:
    """Issues #2 + #3 — datetime literals coming from YAML's auto-parser
    must be emitted with ISO ``T`` separator, not Python's ``str()``
    space-separated form (which ANB rejects)."""

    def test_summary_origin_dates_with_t_separator(self):
        import yaml, re
        text = """
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
"""
        c = ANXChart.from_dict(yaml.safe_load(text))
        xml = c.to_xml()
        m1 = re.search(r'CreatedDate="([^"]+)"', xml)
        m2 = re.search(r'LastPrintDate="([^"]+)"', xml)
        m3 = re.search(r'LastSaveDate="([^"]+)"', xml)
        assert m1.group(1) == '2024-01-15T10:00:00'
        assert m2.group(1) == '2024-02-01T08:30:00'
        # date-only literal stays date-only (no time component)
        assert m3.group(1) == '2024-03-01'
        # Crucially: no space-separated dates anywhere
        assert ' 10:00:00' not in xml
        assert ' 08:30:00' not in xml

    def test_default_datetime_with_t_separator(self):
        import yaml, re
        text = """
settings:
  time:
    default_date: 2024-01-15
    default_datetime: 2024-01-15T10:00:00
entities:
  icons:
    - id: A
      type: P
"""
        c = ANXChart.from_dict(yaml.safe_load(text))
        xml = c.to_xml()
        m1 = re.search(r'\bDefaultDate="([^"]+)"', xml)
        m2 = re.search(r'\bDefaultDateTimeForNewChart="([^"]+)"', xml)
        assert m1.group(1) == '2024-01-15'
        assert m2.group(1) == '2024-01-15T10:00:00'


class TestTypedDateTimeInDateField:
    """Issues #1 + #5 — ``entity.date`` / ``card.date`` accept
    ``datetime.date`` and ``datetime.datetime`` directly (not just
    strings).  The Python user no longer has to manually format an ISO
    string, and YAML users no longer crash when their unquoted card
    ``date:``/``time:`` produces a typed object."""

    def test_python_datetime_in_entity_date(self):
        from datetime import datetime
        c = ANXChart()
        c.add_icon(id='A', type='P', date=datetime(2024, 1, 15), time='10:00:00')
        assert c.validate() == []
        xml = c.to_xml()
        # ChartItem should have DateSet=true and a properly-formatted DateTime
        assert 'DateSet="true"' in xml
        assert 'DateTime="2024-01-15T10:00:00.000"' in xml

    def test_python_date_in_entity_date(self):
        from datetime import date
        c = ANXChart()
        c.add_icon(id='A', type='P', date=date(2024, 1, 15))
        assert c.validate() == []
        c.to_xml()  # no crash

    def test_yaml_unquoted_card_date_clean_validation_error(self):
        """YAML unquoted ``time: 14:30:00`` parses as int 52200 (seconds).
        Card-level validation now catches this with a clean
        ``invalid_time`` error rather than crashing the builder."""
        import yaml
        text = """
entities:
  icons:
    - id: A
      type: P
      cards:
        - summary: 'evidence'
          date: 2024-01-15
          time: 14:30:00
"""
        c = ANXChart.from_dict(yaml.safe_load(text))
        errs = c.validate()
        types = [e['type'] for e in errs]
        assert 'invalid_time' in types
        # Location should point at the inline card, not the entity
        time_err = next(e for e in errs if e['type'] == 'invalid_time')
        assert 'cards[0]' in time_err['location']

    def test_yaml_quoted_card_date_works(self):
        """The corrected YAML form (quoted) builds cleanly."""
        import yaml, re
        text = """
entities:
  icons:
    - id: A
      type: P
      cards:
        - summary: 'evidence'
          date: '2024-01-15'
          time: '14:30:00'
"""
        c = ANXChart.from_dict(yaml.safe_load(text))
        assert c.validate() == []
        xml = c.to_xml()
        m = re.search(r'<Card[^>]*DateTime="([^"]+)"', xml)
        assert m and m.group(1) == '2024-01-15T14:30:00.000'


class TestTopLevelLooseCards:
    """Issue #6 — top-level ``loose_cards: [...]`` key in YAML/JSON
    mirrors ``chart.add_card(entity_id=..., link_id=..., **fields)``
    so card data sourced separately from entities/links can be loaded
    without falling back to the Python API."""

    def test_loose_card_attached_to_entity_by_id(self):
        c = ANXChart.from_dict({
            'entities': {'icons': [{'id': 'alice', 'type': 'P'}]},
            'loose_cards': [
                {'entity_id': 'alice', 'summary': 'New intel', 'date': '2024-03-01'},
            ],
        })
        assert len(c._loose_cards) == 1
        from anxwritter import Card
        assert isinstance(c._loose_cards[0], Card)
        assert c._loose_cards[0].entity_id == 'alice'
        assert c._loose_cards[0].summary == 'New intel'
        assert c.validate() == []
        c.to_xml()  # the card is routed via _loose_entity_cards in _build_xml

    def test_loose_card_attached_to_link_by_link_id(self):
        c = ANXChart.from_dict({
            'entities': {'icons': [
                {'id': 'A', 'type': 'P'}, {'id': 'B', 'type': 'P'},
            ]},
            'links': [{
                'from_id': 'A', 'to_id': 'B', 'type': 'Call',
                'link_id': 'call_001',
            }],
            'loose_cards': [
                {'link_id': 'call_001', 'summary': 'Transcript'},
            ],
        })
        assert len(c._loose_cards) == 1
        assert c._loose_cards[0].link_id == 'call_001'
        assert c.validate() == []
        c.to_xml()

    def test_loose_card_with_unknown_target_validates_clean_error(self):
        c = ANXChart.from_dict({
            'entities': {'icons': [{'id': 'A', 'type': 'P'}]},
            'loose_cards': [
                {'entity_id': 'no_such_entity', 'summary': 'orphan'},
            ],
        })
        errs = c.validate()
        assert any(e['type'] == 'missing_target' for e in errs)

    def test_loose_card_dict_with_timezone(self):
        from anxwritter import TimeZone
        c = ANXChart.from_dict({
            'entities': {'icons': [{'id': 'A', 'type': 'P'}]},
            'loose_cards': [{
                'entity_id': 'A',
                'summary': 'evidence',
                'date': '2024-03-01',
                'time': '10:00:00',
                'timezone': {'id': 1, 'name': 'UTC'},
            }],
        })
        card = c._loose_cards[0]
        assert isinstance(card.timezone, TimeZone)
        assert card.timezone.id == 1
        assert c.validate() == []

    def test_loose_card_passes_card_instance_through(self):
        from anxwritter import Card
        original = Card(entity_id='A', summary='direct')
        c = ANXChart.from_dict({
            'entities': {'icons': [{'id': 'A', 'type': 'P'}]},
            'loose_cards': [original],
        })
        assert c._loose_cards[0] is original

    def test_loose_card_via_yaml_string(self):
        text = """
entities:
  icons:
    - id: alice
      type: Person
loose_cards:
  - entity_id: alice
    summary: 'New intel'
    date: '2024-03-01'
"""
        c = ANXChart.from_yaml(text)
        assert len(c._loose_cards) == 1
        assert c._loose_cards[0].summary == 'New intel'
        assert c.validate() == []
        c.to_xml()



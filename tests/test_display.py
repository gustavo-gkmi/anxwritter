"""Display synthesizers: extra_cfg.display_attribute / display_label.

Covers the 1.12.0 restructure of the old ``display_templates`` into two
keyed-list sections with explicit ``key`` identity and ``kind`` / ``type``
scoping, plus the overlap-conflict rule and the standalone datetime-visible
guard that survived the ``date_attribute_displays`` removal.
"""

from __future__ import annotations

from anxwritter import ANXChart, DisplayAttribute, DisplayLabel, DisplaySource
from anxwritter.errors import ErrorType


def _types(chart):
    return {e["type"] for e in chart.validate()}


def _xml_has(chart, needle):
    return needle in chart.to_xml()


# ── display_attribute: synthesized text sibling ──────────────────────────────

class TestDisplayAttribute:
    def test_basic_attribute_synthesis(self):
        c = ANXChart()
        c.add_attribute_class(name="tx", type="number", visible=False)
        c.add_attribute_class(name="val", type="number", visible=False)
        c.add_icon(id="A", type="Person", attributes={"tx": 3, "val": 100.5})
        c.add_display_attribute(
            key="act", attribute_name="Activity",
            template="{q}x R$ {amt:,.2f}",
            sources=[{"attribute": "tx", "alias": "q"},
                     {"attribute": "val", "alias": "amt"}],
        )
        assert c.validate() == []
        xml = c.to_xml()
        assert "Activity" in xml and "3x R$ 100.50" in xml

    def test_attribute_name_required(self):
        c = ANXChart()
        c.add_attribute_class(name="x", type="number", visible=False)
        c.add_icon(id="A", type="Person", attributes={"x": 1})
        c.add_display_attribute(key="k", template="{x}",
                                sources=[{"attribute": "x"}])
        assert ErrorType.DISPLAY_INVALID.value in _types(c)

    def test_key_required(self):
        c = ANXChart()
        c.add_attribute_class(name="x", type="number", visible=False)
        c.add_icon(id="A", type="Person", attributes={"x": 1})
        c.add(DisplayAttribute(attribute_name="D", template="{x}",
                               sources=[DisplaySource(attribute="x")]))
        assert ErrorType.DISPLAY_INVALID.value in _types(c)

    def test_visible_source_is_allowed(self):
        # A visible (non-datetime) source AC is accepted: the caller takes the
        # double-render. Both the raw value and the synthesized sibling appear.
        c = ANXChart()
        c.add_attribute_class(name="x", type="number")  # visible defaults True
        c.add_icon(id="A", type="Person", attributes={"x": 1})
        c.add_display_attribute(key="k", attribute_name="D", template="amt {x}",
                                sources=[{"attribute": "x"}])
        assert c.validate() == []
        assert _xml_has(c, "amt 1")

    def test_visible_datetime_source_still_rejected(self):
        # Relaxing the source-visibility check must NOT let a visible datetime
        # source through — the independent datetime guard still fires.
        from datetime import datetime
        c = ANXChart()
        c.add_attribute_class(name="d", type="datetime", visible=True)
        c.add_icon(id="A", type="Person", attributes={"d": datetime(2024, 1, 15)})
        c.add_display_attribute(key="k", attribute_name="When",
                                template="{d:%Y-%m-%d}",
                                sources=[{"attribute": "d"}])
        assert ErrorType.DATETIME_AC_FORBIDS_VISIBLE.value in _types(c)

    def test_name_collides_with_explicit_ac(self):
        c = ANXChart()
        c.add_attribute_class(name="x", type="number", visible=False)
        c.add_attribute_class(name="Activity", type="text")
        c.add_icon(id="A", type="Person", attributes={"x": 1})
        c.add_display_attribute(key="k", attribute_name="Activity",
                                template="{x}", sources=[{"attribute": "x"}])
        assert ErrorType.DISPLAY_NAME_COLLISION.value in _types(c)

    def test_datetime_source_format_spec(self):
        c = ANXChart()
        c.add_attribute_class(name="d", type="datetime", visible=False)
        from datetime import datetime
        c.add_icon(id="A", type="Person", attributes={"d": datetime(2024, 1, 15)})
        c.add_display_attribute(
            key="dd", attribute_name="When", template="{d:%d/%m/%Y}",
            sources=[{"attribute": "d"}],
        )
        assert c.validate() == []
        assert _xml_has(c, "15/01/2024")


# ── display_label: render into the entity/link label ─────────────────────────

class TestDisplayLabel:
    def test_writes_label_when_empty(self):
        c = ANXChart()
        c.add_attribute_class(name="age", type="number")
        c.add_icon(id="A", type="Person", attributes={"age": 40})
        c.add_display_label(key="lbl", template="age {age}",
                            sources=[{"attribute": "age"}])
        assert c.validate() == []
        assert _xml_has(c, "age 40")

    def test_preserves_explicit_label_by_default(self):
        c = ANXChart()
        c.add_attribute_class(name="age", type="number")
        c.add_icon(id="A", type="Person", label="Alice", attributes={"age": 40})
        c.add_display_label(key="lbl", template="age {age}",
                            sources=[{"attribute": "age"}])
        assert c.validate() == []
        assert _xml_has(c, "Alice") and not _xml_has(c, "age 40")

    def test_override_existing_stomps_label(self):
        c = ANXChart()
        c.add_attribute_class(name="age", type="number")
        c.add_icon(id="A", type="Person", label="Alice", attributes={"age": 40})
        c.add_display_label(key="lbl", template="age {age}", override_existing=True,
                            sources=[{"attribute": "age"}])
        assert c.validate() == []
        assert _xml_has(c, "age 40")

    def test_source_visible_not_required_for_label(self):
        c = ANXChart()
        c.add_attribute_class(name="age", type="number")  # visible True
        c.add_icon(id="A", type="Person", attributes={"age": 40})
        c.add_display_label(key="lbl", template="age {age}",
                            sources=[{"attribute": "age"}])
        assert c.validate() == []


# ── kind / type scoping ──────────────────────────────────────────────────────

class TestKindTypeScoping:
    def _chart(self):
        c = ANXChart()
        c.add_attribute_class(name="n", type="text")
        c.add_icon(id="P", type="Person", attributes={"n": "p"})
        c.add_icon(id="O", type="Org", attributes={"n": "o"})
        c.add_link(from_id="P", to_id="O", type="Call", attributes={"n": "c"})
        return c

    def test_kind_entity_only_touches_entities(self):
        c = self._chart()
        c.add_display_label(key="e", kind="entity", template="E:{n}",
                            sources=[{"attribute": "n"}])
        assert c.validate() == []
        xml = c.to_xml()
        assert "E:p" in xml and "E:o" in xml and "E:c" not in xml

    def test_type_filter_only_touches_matching_type(self):
        c = self._chart()
        c.add_display_label(key="p", kind="entity", type="Person",
                            template="ONLY:{n}", sources=[{"attribute": "n"}])
        assert c.validate() == []
        xml = c.to_xml()
        assert "ONLY:p" in xml and "ONLY:o" not in xml

    def test_typed_beats_untyped_no_conflict(self):
        c = self._chart()
        c.add_display_label(key="all", template="ALL:{n}",
                            sources=[{"attribute": "n"}])
        c.add_display_label(key="person", type="Person", template="P:{n}",
                            sources=[{"attribute": "n"}])
        # No overlap conflict — different specificity tiers.
        assert ErrorType.DISPLAY_OVERLAP_CONFLICT.value not in _types(c)
        xml = c.to_xml()
        # Person gets the specific one; Org falls to the untyped default.
        assert "P:p" in xml and "ALL:o" in xml

    def test_two_untyped_labels_overlap_conflict(self):
        c = self._chart()
        c.add_display_label(key="a", template="A:{n}", sources=[{"attribute": "n"}])
        c.add_display_label(key="b", template="B:{n}", sources=[{"attribute": "n"}])
        assert ErrorType.DISPLAY_OVERLAP_CONFLICT.value in _types(c)

    def test_same_type_same_attribute_overlap_conflict(self):
        c = ANXChart()
        c.add_attribute_class(name="x", type="number", visible=False)
        c.add_icon(id="A", type="Person", attributes={"x": 1})
        c.add_display_attribute(key="a", attribute_name="D", type="Person",
                                template="{x}", sources=[{"attribute": "x"}])
        c.add_display_attribute(key="b", attribute_name="D", type="Person",
                                template="{x}!", sources=[{"attribute": "x"}])
        assert ErrorType.DISPLAY_OVERLAP_CONFLICT.value in _types(c)

    def test_same_attribute_disjoint_types_ok(self):
        c = ANXChart()
        c.add_attribute_class(name="x", type="number", visible=False)
        c.add_icon(id="P", type="Person", attributes={"x": 1})
        c.add_icon(id="O", type="Org", attributes={"x": 2})
        c.add_display_attribute(key="p", attribute_name="D", type="Person",
                                template="P{x}", sources=[{"attribute": "x"}])
        c.add_display_attribute(key="o", attribute_name="D", type="Org",
                                template="O{x}", sources=[{"attribute": "x"}])
        assert ErrorType.DISPLAY_OVERLAP_CONFLICT.value not in _types(c)
        xml = c.to_xml()
        assert "P1" in xml and "O2" in xml


# ── static (placeholder-free) templates: sources are optional ────────────────

class TestStaticTemplateNoSources:
    def test_attribute_static_template_no_sources_valid(self):
        # A placeholder-free template needs no sources; it renders as a literal
        # text-sibling on every matching item.
        c = ANXChart()
        c.add_icon(id="A", type="Person")
        c.add_display_attribute(key="liq", attribute_name="Net", template="(líq.)")
        assert c.validate() == []
        assert _xml_has(c, "(líq.)")

    def test_label_static_template_no_sources_valid(self):
        c = ANXChart()
        c.add_icon(id="A", type="Person")
        c.add_display_label(key="tag", template="(líq.)")
        assert c.validate() == []
        assert _xml_has(c, "(líq.)")

    def test_attribute_placeholder_without_sources_rejected(self):
        # Referencing a placeholder still requires a matching source.
        c = ANXChart()
        c.add_icon(id="A", type="Person")
        c.add_display_attribute(key="k", attribute_name="D", template="{q}")
        assert ErrorType.DISPLAY_INVALID.value in _types(c)

    def test_label_placeholder_without_sources_rejected(self):
        c = ANXChart()
        c.add_icon(id="A", type="Person")
        c.add_display_label(key="k", template="val {q}")
        assert ErrorType.DISPLAY_INVALID.value in _types(c)

    def test_escaped_braces_are_not_placeholders(self):
        # Literal {{ }} are not placeholders, so no sources are required.
        c = ANXChart()
        c.add_icon(id="A", type="Person")
        c.add_display_attribute(key="k", attribute_name="D", template="{{static}}")
        assert c.validate() == []
        assert _xml_has(c, "{static}")

    def test_static_label_still_participates_in_overlap(self):
        # The valid sourceless entry must still take part in overlap detection
        # (it falls through instead of being skipped).
        c = ANXChart()
        c.add_icon(id="A", type="Person")
        c.add_display_label(key="a", template="(líq.)")
        c.add_display_label(key="b", template="(bruto)")
        assert ErrorType.DISPLAY_OVERLAP_CONFLICT.value in _types(c)

    def test_static_attribute_still_collides_with_explicit_ac(self):
        # Name-collision detection also runs for a sourceless static entry.
        c = ANXChart()
        c.add_attribute_class(name="Net", type="text")
        c.add_icon(id="A", type="Person")
        c.add_display_attribute(key="k", attribute_name="Net", template="(líq.)")
        assert ErrorType.DISPLAY_NAME_COLLISION.value in _types(c)

    def test_from_dict_static_no_sources_parity(self):
        def _expected():
            c = ANXChart()
            c.add_icon(id="A", type="Person")
            c.add_display_attribute(key="k", attribute_name="Net", template="(líq.)")
            return c.to_xml()

        spec = {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "settings": {"extra_cfg": {"display_attribute": [
                {"key": "k", "attribute_name": "Net", "template": "(líq.)"},
            ]}},
        }
        c = ANXChart.from_dict(spec)
        assert c.validate() == []
        assert c.to_xml() == _expected()


# ── datetime-visible guard (survived date_attribute_displays removal) ─────────

class TestDatetimeVisibleGuard:
    def test_datetime_ac_forbids_visible_true(self):
        c = ANXChart()
        c.add_attribute_class(name="d", type="datetime", visible=True)
        assert ErrorType.DATETIME_AC_FORBIDS_VISIBLE.value in _types(c)

    def test_datetime_ac_visible_false_ok(self):
        c = ANXChart()
        c.add_attribute_class(name="d", type="datetime", visible=False)
        assert ErrorType.DATETIME_AC_FORBIDS_VISIBLE.value not in _types(c)


# ── cross-path parity (Python API / dict / YAML) ─────────────────────────────

class TestCrossPathParity:
    def _expected_xml(self):
        c = ANXChart()
        c.add_attribute_class(name="x", type="number", visible=False)
        c.add_icon(id="A", type="Person", attributes={"x": 5})
        c.add_display_attribute(key="k", attribute_name="D", template="v={x}",
                                sources=[{"attribute": "x"}])
        return c.to_xml()

    def test_from_dict_matches_python_api(self):
        spec = {
            "attribute_classes": [{"name": "x", "type": "number", "visible": False}],
            "entities": {"icons": [{"id": "A", "type": "Person",
                                    "attributes": {"x": 5}}]},
            "settings": {"extra_cfg": {"display_attribute": [
                {"key": "k", "attribute_name": "D", "template": "v={x}",
                 "sources": [{"attribute": "x"}]},
            ]}},
        }
        c = ANXChart.from_dict(spec)
        assert c.to_xml() == self._expected_xml()

    def test_from_yaml_matches_python_api(self):
        yaml_src = """
attribute_classes:
  - name: x
    type: number
    visible: false
entities:
  icons:
    - id: A
      type: Person
      attributes:
        x: 5
settings:
  extra_cfg:
    display_attribute:
      - key: k
        attribute_name: D
        template: "v={x}"
        sources:
          - attribute: x
"""
        c = ANXChart.from_yaml(yaml_src)
        assert c.to_xml() == self._expected_xml()

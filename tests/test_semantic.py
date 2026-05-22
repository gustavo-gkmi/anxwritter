"""Unit tests for semantic-type resolution (anxwritter/semantic.py).

Covers the previously-thin (58%) resolver: deterministic GUID generation,
ancestor-chain walking with cycle detection, entity/link classification, and
``SemanticResolver`` name→GUID resolution + catalogue config building.
"""

from __future__ import annotations

import pytest

from anxwritter import SemanticEntity, SemanticLink, SemanticProperty
from anxwritter.semantic import (
    ROOT_ENTITY,
    ROOT_LINK,
    SemanticResolver,
    ancestor_chain,
    classify_type,
    generate_guid,
)


class TestGenerateGuid:
    def test_deterministic(self):
        assert generate_guid("entity:Foo") == generate_guid("entity:Foo")

    def test_prefixed(self):
        assert generate_guid("entity:Foo").startswith("guid")

    def test_distinct_keys_differ(self):
        assert generate_guid("entity:Foo") != generate_guid("link:Foo")


def _entity_tree():
    """A tiny Entity-rooted lookup: Entity -> Suspect."""
    lookup = {
        "Entity": {"guid": ROOT_ENTITY, "parent_guid": None},
        "Suspect": {"guid": "gSuspect", "parent_guid": ROOT_ENTITY},
    }
    guid_to_name = {ROOT_ENTITY: "Entity", "gSuspect": "Suspect"}
    return lookup, guid_to_name


class TestAncestorChain:
    def test_root_first_topological_order(self):
        lookup, g2n = _entity_tree()
        assert ancestor_chain("Suspect", lookup, g2n) == ["Entity", "Suspect"]

    def test_root_alone(self):
        lookup, g2n = _entity_tree()
        assert ancestor_chain("Entity", lookup, g2n) == ["Entity"]

    def test_missing_name_raises(self):
        lookup, g2n = _entity_tree()
        with pytest.raises(ValueError):
            ancestor_chain("Ghost", lookup, g2n)

    def test_broken_parent_guid_raises(self):
        lookup = {"Child": {"guid": "gC", "parent_guid": "gMissing"}}
        with pytest.raises(ValueError):
            ancestor_chain("Child", lookup, {"gC": "Child"})

    def test_cycle_raises(self):
        lookup = {
            "A": {"guid": "gA", "parent_guid": "gB"},
            "B": {"guid": "gB", "parent_guid": "gA"},
        }
        g2n = {"gA": "A", "gB": "B"}
        with pytest.raises(ValueError):
            ancestor_chain("A", lookup, g2n)


class TestClassifyType:
    def test_entity_tree(self):
        lookup, g2n = _entity_tree()
        assert classify_type("Suspect", lookup, g2n) == "entity"

    def test_link_tree(self):
        lookup = {
            "Link": {"guid": ROOT_LINK, "parent_guid": None},
            "Surveilled": {"guid": "gS", "parent_guid": ROOT_LINK},
        }
        g2n = {ROOT_LINK: "Link", "gS": "Surveilled"}
        assert classify_type("Surveilled", lookup, g2n) == "link"

    def test_unknown_root_is_none(self):
        lookup = {"Weird": {"guid": "gW", "parent_guid": None}}
        assert classify_type("Weird", lookup, {"gW": "Weird"}) is None

    def test_unresolvable_is_none(self):
        assert classify_type("Ghost", {}, {}) is None


class TestSemanticResolver:
    def _resolver(self):
        se = SemanticEntity(name="Suspect", kind_of="Person", guid="guidSUSPECT")
        sl = SemanticLink(name="Surveilled", kind_of="Link")  # no guid -> generated
        sp = SemanticProperty(name="CPF", base_property="Abstract Text")
        return SemanticResolver([se], [sl], [sp])

    def test_known_name_helpers(self):
        r = self._resolver()
        assert r.is_known_entity_name("Suspect")
        assert r.is_known_link_name("Surveilled")
        assert r.is_known_property_name("CPF")
        assert not r.is_known_entity_name("Nope")

    def test_resolve_custom_entity_records_reference(self):
        r = self._resolver()
        assert r.resolve_type_name("Suspect") == "guidSUSPECT"
        assert "guidSUSPECT" in r.referenced_type_guids

    def test_resolve_raw_guid_passthrough(self):
        r = self._resolver()
        assert r.resolve_type_name("guidRAW123") == "guidRAW123"
        assert "guidRAW123" in r.referenced_type_guids

    def test_resolve_unknown_returns_name(self):
        r = self._resolver()
        assert r.resolve_type_name("Unknown") == "Unknown"

    def test_resolve_none_is_none(self):
        r = self._resolver()
        assert r.resolve_type_name(None) is None
        assert r.resolve_property_name(None) is None

    def test_resolve_link_generates_guid(self):
        r = self._resolver()
        assert r.resolve_type_name("Surveilled") == generate_guid("link:Surveilled")

    def test_resolve_property_generates_guid(self):
        r = self._resolver()
        assert r.resolve_property_name("CPF") == generate_guid("property:CPF")
        assert generate_guid("property:CPF") in r.referenced_property_guids

    def test_build_config_populated(self):
        r = self._resolver()
        r.resolve_type_name("Suspect")
        cfg = r.build_config()
        assert cfg is not None
        assert "Suspect" in cfg["custom_entities"]
        assert "Surveilled" in cfg["custom_links"]
        assert "CPF" in cfg["custom_properties"]

    def test_build_config_empty_is_none(self):
        assert SemanticResolver([], [], []).build_config() is None

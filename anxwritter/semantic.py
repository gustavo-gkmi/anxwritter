"""
semantic.py — Semantic type support for lcx:LibraryCatalogue.

Provides:
- Deterministic GUID generation for custom semantic types
- Ancestor chain resolution for minimal catalogue emission
- ``SemanticResolver`` — encapsulates semantic name → GUID resolution and
  catalogue config building (extracted from ``ANXChart._resolve_semantic_types``)

The i2-derived GUIDs used by this project (the six abstract roots and the
three geo-map property GUIDs) are defined in :mod:`anxwritter.guids` — see
that module for the full inventory and the interoperability rationale.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from .models import SemanticEntity, SemanticLink, SemanticProperty

# ── LCX namespace ────────────────────────────────────────────────────────────

LCX_NS = 'http://www.i2group.com/Schemas/2001-12-07/LCXSchema'

LCX_VERSION = {
    'VersionMajor': '1',
    'VersionMinor': '18',
    'VersionRelease': '27',
    'VersionBuild': '60',
    'LocaleHex': '0809',
}

# ── i2 GUIDs ─ re-exported from ._i2_interop (single source of truth) ───────

from ._i2_interop import (
    ROOT_ENTITY, ROOT_LINK,
    ROOT_ABSTRACT_TEXT, ROOT_ABSTRACT_NUM,
    ROOT_ABSTRACT_DT, ROOT_ABSTRACT_FLAG,
    ROOTS, TYPE_ROOTS, PROPERTY_ROOTS, ROOT_NAMES,
)

# ── Deterministic GUID generation ────────────────────────────────────────────

_ANXWRITTER_NS = uuid.UUID('d1e2f3a4-b5c6-7890-abcd-ef1234567890')


def generate_guid(key: str) -> str:
    """Deterministic GUID from key. Same key always produces the same result.

    Convention:
        Entity types:  ``generate_guid('entity:Suspect')``
        Link types:    ``generate_guid('link:Surveilled')``
        Properties:    ``generate_guid('property:CPF Number')``
    """
    raw = str(uuid.uuid5(_ANXWRITTER_NS, key))
    return f'guid{raw.upper()}'


def ancestor_chain(name: str, lookup: Dict[str, Dict[str, Any]],
                   guid_to_name: Dict[str, str]) -> List[str]:
    """Walk parent chain from *name* up to the root (inclusive).

    Returns ``[root, ..., grandparent, parent, name]`` — topological order,
    ancestors first.  Raises ``ValueError`` if the chain is broken.
    """
    chain: List[str] = []
    current = name
    seen: Set[str] = set()

    while current:
        if current in seen:
            raise ValueError(f"Circular semantic type hierarchy at '{current}'")
        seen.add(current)
        chain.append(current)

        entry = lookup.get(current)
        if entry is None:
            raise ValueError(f"Semantic type '{current}' not found in catalogue")

        parent_guid = entry.get('parent_guid')
        if parent_guid is None:
            # Reached a root
            break
        parent_name = guid_to_name.get(parent_guid)
        if parent_name is None:
            raise ValueError(
                f"Parent GUID '{parent_guid}' of '{current}' not found in catalogue"
            )
        current = parent_name

    chain.reverse()
    return chain


def classify_type(name: str, lookup: Dict[str, Dict[str, Any]],
                  guid_to_name: Dict[str, str]) -> Optional[str]:
    """Determine whether a type name belongs to the Entity or Link tree.

    Returns ``'entity'``, ``'link'``, or ``None`` if unresolvable.
    """
    try:
        chain = ancestor_chain(name, lookup, guid_to_name)
    except ValueError:
        return None
    if not chain:
        return None
    root_name = chain[0]
    root_entry = lookup.get(root_name)
    if root_entry is None:
        return None
    root_guid = root_entry['guid']
    if root_guid == ROOT_ENTITY:
        return 'entity'
    if root_guid == ROOT_LINK:
        return 'link'
    return None


# ── SemanticResolver ─────────────────────────────────────────────────────────


class SemanticResolver:
    """Resolves semantic type names to GUIDs and builds the catalogue config.

    Encapsulates the logic previously inline in
    ``ANXChart._resolve_semantic_types()``. Holds:

    - Custom-type lookup dicts (entity, link, property) keyed by name —
      populated from the user's ``add_semantic_entity`` / ``add_semantic_link``
      / ``add_semantic_property`` calls
    - Referenced GUID sets (for catalogue minimization)
    - Resolution helpers for type and property names
    """

    def __init__(self,
                 semantic_entities: List['SemanticEntity'],
                 semantic_links: List['SemanticLink'],
                 semantic_properties: List['SemanticProperty']) -> None:
        # Build name → entry dicts for custom types, generating deterministic
        # GUIDs for entries that didn't supply one.
        self.custom_entity_lookup: Dict[str, Dict[str, Any]] = {}
        for se in semantic_entities:
            guid = se.guid or generate_guid(f'entity:{se.name}')
            self.custom_entity_lookup[se.name] = {
                'guid': guid, 'kind_of': se.kind_of, 'abstract': se.abstract,
                'synonyms': se.synonyms, 'description': se.description,
            }

        self.custom_link_lookup: Dict[str, Dict[str, Any]] = {}
        for sl in semantic_links:
            guid = sl.guid or generate_guid(f'link:{sl.name}')
            self.custom_link_lookup[sl.name] = {
                'guid': guid, 'kind_of': sl.kind_of, 'abstract': sl.abstract,
                'synonyms': sl.synonyms, 'description': sl.description,
            }

        self.custom_property_lookup: Dict[str, Dict[str, Any]] = {}
        for sp in semantic_properties:
            guid = sp.guid or generate_guid(f'property:{sp.name}')
            self.custom_property_lookup[sp.name] = {
                'guid': guid, 'base_property': sp.base_property, 'abstract': sp.abstract,
                'synonyms': sp.synonyms, 'description': sp.description,
            }

        self.referenced_type_guids: Set[str] = set()
        self.referenced_property_guids: Set[str] = set()

    def resolve_type_name(self, name: Optional[str]) -> Optional[str]:
        """Resolve a semantic type name to a GUID. Returns None if no semantic type."""
        if not name:
            return None
        # Raw GUID passthrough
        if name.startswith('guid'):
            self.referenced_type_guids.add(name)
            return name
        # Custom entity types
        custom = self.custom_entity_lookup.get(name)
        if custom:
            self.referenced_type_guids.add(custom['guid'])
            return custom['guid']
        # Custom link types
        custom = self.custom_link_lookup.get(name)
        if custom:
            self.referenced_type_guids.add(custom['guid'])
            return custom['guid']
        return name  # Unresolved — caller will catch this

    def resolve_property_name(self, name: Optional[str]) -> Optional[str]:
        """Resolve a property semantic type name to a GUID. Returns None if no semantic type."""
        if not name:
            return None
        if name.startswith('guid'):
            self.referenced_property_guids.add(name)
            return name
        custom = self.custom_property_lookup.get(name)
        if custom:
            self.referenced_property_guids.add(custom['guid'])
            return custom['guid']
        return name

    def build_config(self) -> Optional[Dict[str, Any]]:
        """Return the semantic_config dict, or None if no semantic types are used."""
        has_any = (self.referenced_type_guids or self.referenced_property_guids
                   or self.custom_entity_lookup or self.custom_link_lookup
                   or self.custom_property_lookup)
        if not has_any:
            return None
        return {
            'custom_entities': self.custom_entity_lookup,
            'custom_links': self.custom_link_lookup,
            'custom_properties': self.custom_property_lookup,
            'referenced_type_guids': self.referenced_type_guids,
            'referenced_property_guids': self.referenced_property_guids,
        }

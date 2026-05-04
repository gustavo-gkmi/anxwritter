"""
_i2_interop.py — Minimum interoperability constants for the ANX format.

This module contains the only i2-derived identifiers this library ships:

  * Six abstract-root GUIDs required by ANB's ``lcx:LibraryCatalogue`` schema.
    Every semantic type chain must terminate at one of these roots; they are
    structural anchors, not content.

  * Three geo-map property GUIDs required by ANB's Esri Maps subsystem to
    recognise Latitude/Longitude attributes for geographic rendering.

These nine identifiers are the absolute minimum needed to write a structurally
valid ANX file with semantic types. This library intentionally ships nothing
else from i2's type system — no standard-library types (Person, Vehicle,
Phone Call…), no icon catalog, no palette definitions. All of that content
belongs to the user's licensed ANB installation and must be supplied by the
user via config files or ``.ant``/``.anx`` reference files.

This design is intentional: it leaves organisations free to define their own
default semantic types, palettes, icon mappings, link types, and attribute
classes — either independently of i2's standard library or layered on top of
it using types extracted from their own ANB installation.

These nine identifiers are functional tokens (format anchors), not creative
works, reproduced under the interoperability doctrine
(EU Directive 2009/24/EC Art. 6).
"""
from __future__ import annotations

from typing import Dict, Set


# ── Group 1: abstract root GUIDs ─────────────────────────────────────────────

#: i2 abstract root for every entity type. Parent of any user-defined
#: ``kind_of: Entity`` chain. Required by ANB schema.
ROOT_ENTITY        = 'guid3669EC21-8E41-438A-AA1A-26B477C15BE0'

#: i2 abstract root for every link type. Parent of any user-defined
#: ``kind_of: Link`` chain. Required by ANB schema.
ROOT_LINK          = 'guidC9E54967-BBBF-494B-8348-B9D524F500FD'

#: i2 abstract root for text-typed semantic properties.
ROOT_ABSTRACT_TEXT = 'guid9A224CCF-28F7-4c55-9F14-9E820A0B1631'

#: i2 abstract root for numeric-typed semantic properties. Also the indirect
#: ancestor of the geo-map ``Grid Reference`` / ``Latitude`` / ``Longitude``
#: property tree.
ROOT_ABSTRACT_NUM  = 'guid6D676796-915D-487f-B384-73503C988ABE'

#: i2 abstract root for datetime-typed semantic properties.
ROOT_ABSTRACT_DT   = 'guid6684F871-B607-4ffb-80E8-480535CB44FC'

#: i2 abstract root for flag/boolean semantic properties.
ROOT_ABSTRACT_FLAG = 'guid74F2A516-2F49-4282-989F-F4A468656FF0'

#: All six abstract roots.
ROOTS: Set[str] = {
    ROOT_ENTITY, ROOT_LINK,
    ROOT_ABSTRACT_TEXT, ROOT_ABSTRACT_NUM,
    ROOT_ABSTRACT_DT, ROOT_ABSTRACT_FLAG,
}

#: Type-tree roots (entity + link). Used to distinguish from property roots
#: when populating the catalogue's type vs. property lookups.
TYPE_ROOTS: Set[str] = {ROOT_ENTITY, ROOT_LINK}

#: Property-tree roots (text/number/datetime/flag).
PROPERTY_ROOTS: Set[str] = {
    ROOT_ABSTRACT_TEXT, ROOT_ABSTRACT_NUM,
    ROOT_ABSTRACT_DT, ROOT_ABSTRACT_FLAG,
}

#: Display name for each root, emitted as the ``<TypeName>`` /
#: ``<PropertyName>`` of root catalogue entries.
ROOT_NAMES: Dict[str, str] = {
    ROOT_ENTITY:        'Entity',
    ROOT_LINK:          'Link',
    ROOT_ABSTRACT_TEXT: 'Abstract Text',
    ROOT_ABSTRACT_NUM:  'Abstract Number',
    ROOT_ABSTRACT_DT:   'Abstract Date & Time',
    ROOT_ABSTRACT_FLAG: 'Abstract Flag',
}


# ── Group 2: geo-map property GUIDs ──────────────────────────────────────────

#: i2 standard "Latitude" semantic property GUID. Required for ANB's Esri
#: Maps subsystem to recognise a Latitude attribute for geographic rendering.
#: Used only when ``geo_map.mode`` is ``'latlon'`` or ``'both'``.
LATITUDE_GUID       = 'guid5304A03B-FE47-4406-91E7-0D49EC8409A6'

#: i2 standard "Longitude" semantic property GUID. Paired with
#: :data:`LATITUDE_GUID`.
LONGITUDE_GUID      = 'guid14BCA0EC-D67A-4A67-BC36-CFF650FD77A9'

#: i2 standard "Grid Reference" semantic property GUID. Parent of Latitude
#: and Longitude in the property tree (chains up to ``Abstract Number``).
#: Required because Latitude/Longitude need a non-abstract parent to be
#: valid in the catalogue chain.
GRID_REFERENCE_GUID = 'guid7E0F705E-3D39-4E6E-B6C1-5E72B8C573DA'

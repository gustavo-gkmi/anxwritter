"""Helpers for comparing two ANXChart instances built via different input forms.

Used by tests/test_input_equivalence.py to assert that the same logical chart
data produces identical output regardless of how it was fed into the library.

Three public helpers:

- canonical_xml(chart)       -> str    (attribute-sorted, whitespace-normalized)
- chart_state_snapshot(chart)-> dict   (dataclasses.asdict of all collections)
- assert_charts_equivalent(c1, c2, *, strict_bytes=False)
"""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET
from typing import Any, Dict

from anxwritter import ANXChart


# ---------------------------------------------------------------------------
# Canonical XML
# ---------------------------------------------------------------------------

def canonical_xml(chart: ANXChart) -> str:
    """Return a stable, attribute-sorted serialization of chart.to_xml().

    Walks the ElementTree and rewrites each element with its attributes sorted
    alphabetically, so two charts that produce the same logical XML but with
    different attribute insertion order compare equal.
    """
    xml_str = chart.to_xml()
    root = ET.fromstring(xml_str)
    _sort_attrs(root)
    _strip_whitespace(root)
    return ET.tostring(root, encoding="unicode")


def _sort_attrs(elem: ET.Element) -> None:
    if elem.attrib:
        sorted_items = sorted(elem.attrib.items())
        elem.attrib.clear()
        for k, v in sorted_items:
            elem.set(k, v)
    for child in elem:
        _sort_attrs(child)


def _strip_whitespace(elem: ET.Element) -> None:
    if elem.text is not None and not elem.text.strip():
        elem.text = None
    if elem.tail is not None and not elem.tail.strip():
        elem.tail = None
    for child in elem:
        _strip_whitespace(child)


# ---------------------------------------------------------------------------
# Internal state snapshot
# ---------------------------------------------------------------------------

_COLLECTION_ATTRS = (
    "_entities",
    "_links",
    "_loose_cards",
    "_attribute_classes",
    "_legend_items",
    "_entity_types",
    "_link_types",
    "_palettes",
    "_datetime_formats",
    "_semantic_entities",
    "_semantic_links",
    "_semantic_properties",
    "source_types",
)


def chart_state_snapshot(chart: ANXChart) -> Dict[str, Any]:
    """Return a plain-dict snapshot of every chart collection suitable for ==.

    Uses dataclasses.asdict on every dataclass field so nested Font / Frame /
    Show / TimeZone / Card structures are fully compared. Enums are normalized
    to their .value so ``'Icon'`` and ``LegendItemType.ICON`` compare equal.
    """
    snap: Dict[str, Any] = {}

    for attr in _COLLECTION_ATTRS:
        items = getattr(chart, attr)
        snap[attr] = [_normalize(_asdict(obj)) for obj in items]

    snap["strengths"] = {
        "default": chart.strengths.default,
        "items": [_normalize(_asdict(s)) for s in chart.strengths.items],
    }
    for grade_key in ("grades_one", "grades_two", "grades_three"):
        gc = getattr(chart, grade_key)
        snap[grade_key] = {"default": gc.default, "items": list(gc.items)}

    snap["settings"] = _normalize(dataclasses.asdict(chart.settings))
    return snap


def _asdict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _normalize(value: Any) -> Any:
    """Recursively normalize enum .value and drop None-valued keys for stable ==."""
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value
    return value


# ---------------------------------------------------------------------------
# Equivalence assertion
# ---------------------------------------------------------------------------

def assert_charts_equivalent(
    c1: ANXChart,
    c2: ANXChart,
    *,
    strict_bytes: bool = False,
    label_a: str = "A",
    label_b: str = "B",
) -> None:
    """Assert two charts are equivalent across state, canonical XML, and optionally bytes.

    Runs three checks in order:
      1. chart_state_snapshot(c1) == chart_state_snapshot(c2)
      2. canonical_xml(c1) == canonical_xml(c2)
      3. if strict_bytes: c1.to_xml() == c2.to_xml()

    Each check produces a distinct, diagnostic failure message naming which
    builder produced which chart so failures in parametrized tests are readable.
    """
    s1 = chart_state_snapshot(c1)
    s2 = chart_state_snapshot(c2)
    if s1 != s2:
        diff = _first_diff(s1, s2)
        raise AssertionError(
            f"Internal state differs between {label_a} and {label_b}: {diff}"
        )

    x1 = canonical_xml(c1)
    x2 = canonical_xml(c2)
    if x1 != x2:
        raise AssertionError(
            f"Canonical XML differs between {label_a} and {label_b}.\n"
            f"{label_a}: {x1[:500]}...\n{label_b}: {x2[:500]}..."
        )

    if strict_bytes:
        b1 = c1.to_xml()
        b2 = c2.to_xml()
        if b1 != b2:
            raise AssertionError(
                f"Byte-equal XML differs between {label_a} and {label_b} "
                f"(canonical forms matched). Length {label_a}={len(b1)}, "
                f"{label_b}={len(b2)}."
            )


def validation_error_signature(chart: ANXChart) -> list:
    """Return a stable, order-insensitive signature of chart.validate() output.

    Each error becomes a ``(type, location_or_name)`` tuple, then the list is
    sorted. Messages are excluded so wording changes don't break tests.
    """
    errors = chart.validate()
    sig = []
    for e in errors:
        err_type = e.get("type", "")
        # Use location if present (entity id), else fall back to nothing.
        loc = e.get("location") or ""
        sig.append((err_type, loc))
    return sorted(sig)


def assert_validation_equivalent(
    c1: ANXChart,
    c2: ANXChart,
    *,
    label_a: str = "A",
    label_b: str = "B",
) -> None:
    """Assert two charts produce equivalent validate() error lists.

    Compares (type, location) tuples — order-insensitive, message-agnostic.
    """
    s1 = validation_error_signature(c1)
    s2 = validation_error_signature(c2)
    if s1 != s2:
        only_a = [e for e in s1 if e not in s2]
        only_b = [e for e in s2 if e not in s1]
        raise AssertionError(
            f"validate() errors differ between {label_a} and {label_b}.\n"
            f"  only in {label_a}: {only_a}\n"
            f"  only in {label_b}: {only_b}"
        )


def _first_diff(a: Any, b: Any, path: str = "") -> str:
    """Return a short description of the first differing path in two snapshots."""
    if type(a) is not type(b):
        return f"{path or '<root>'}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            if k not in a:
                return f"{path}.{k}: missing in A"
            if k not in b:
                return f"{path}.{k}: missing in B"
            if a[k] != b[k]:
                return _first_diff(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return _first_diff(x, y, f"{path}[{i}]")
    else:
        if a != b:
            return f"{path}: {a!r} != {b!r}"
    return f"{path}: (no diff located but != returned True — possible NaN or custom __eq__)"

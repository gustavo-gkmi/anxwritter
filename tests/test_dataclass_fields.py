"""Dataclass field round-trip coverage.

For every scalar field on every user-facing entity/link/card dataclass, build
a minimal spec exercising that field and assert the value round-trips
through ``ANXChart.from_dict``. Catches "we added ``Icon.new_field`` but
forgot to wire YAML parsing" drift.

Nested-dataclass fields (Font, Frame, Show, TimeZone, List[Card]) are
covered separately by hand-written tests in TestNestedDataclassFields
because the generator doesn't have a clean way to build sample values
for them.
"""

from __future__ import annotations

import dataclasses
from typing import Any, List, Optional, Union, get_args, get_origin, get_type_hints

import pytest

from anxwritter import (
    ANXChart,
    Box,
    Card,
    Circle,
    EventFrame,
    Frame,
    Font,
    Icon,
    Label,
    Link,
    Show,
    TextBlock,
    ThemeLine,
    TimeZone,
)
from anxwritter.models import Card as _CardModel  # for localns in get_type_hints


# ---------------------------------------------------------------------------
# Field discovery + sample value generation
# ---------------------------------------------------------------------------

_ENTITY_CLASSES = {
    "icons": Icon,
    "boxes": Box,
    "circles": Circle,
    "theme_lines": ThemeLine,
    "event_frames": EventFrame,
    "text_blocks": TextBlock,
    "labels": Label,
}

# Fields we deliberately skip in the scalar generator because they require
# special handling — nested dataclasses, internal routing, or complex values
# covered by TestNestedDataclassFields below.
_NESTED_DATACLASS_FIELDS = {
    "label_font",       # Font
    "frame",            # Frame
    "show",             # Show
    "timezone",         # TimeZone
    "cards",            # List[Card]
    "attributes",       # dict (hand-written coverage)
    "color",            # Union[int, str, Color, None] — ambiguous sample
}

_INTERNAL_ROUTING_FIELDS = {"link_id", "entity_id"}


def _unwrap_optional(t: Any) -> Any:
    """Return the inner type of Optional[X], otherwise return t unchanged."""
    if get_origin(t) is Union:
        args = [a for a in get_args(t) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return t


def _sample_for_type(t: Any, field_name: str) -> Any:
    """Produce a deterministic, round-trip-safe sample value for a field type.

    Returns ``None`` to signal "skip this field" (complex types we don't
    handle). Context-sensitive fields like date/time use format-valid values
    even though ``from_dict`` doesn't validate — this keeps the test robust
    if someone later calls ``to_xml`` on the generated chart.
    """
    inner = _unwrap_optional(t)

    # Field-name overrides for context-sensitive values
    if field_name == "date":
        return "2024-01-15"
    if field_name == "time":
        return "14:30:00"
    if field_name == "id":
        return "sample_id"
    if field_name == "type":
        return "SampleType"
    if field_name == "name":
        return "sample_name"

    if inner is str:
        return "sample_text"
    if inner is bool:
        return True
    if inner is int:
        return 42
    if inner is float:
        return 1.5
    if inner is dict:
        return None  # hand-written coverage below
    if get_origin(inner) is list:
        return None  # skip List[X] in the scalar generator
    return None


def _field_cases_for_entity(cls: type) -> List[tuple]:
    """Return [(field_name, sample_value)] for every supported scalar field."""
    hints = get_type_hints(cls, localns={"Card": _CardModel})
    cases: List[tuple] = []
    for f in dataclasses.fields(cls):
        if f.name in _NESTED_DATACLASS_FIELDS or f.name in _INTERNAL_ROUTING_FIELDS:
            continue
        if f.name in ("id", "type"):
            # Already set in the minimal chart; we don't round-trip these via
            # additional parametrized cases because every spec needs them.
            continue
        sample = _sample_for_type(hints[f.name], f.name)
        if sample is None:
            continue
        cases.append((f.name, sample))
    return cases


def _entity_parametrize():
    params = []
    for key, cls in _ENTITY_CLASSES.items():
        for field_name, sample in _field_cases_for_entity(cls):
            params.append(
                pytest.param(key, cls, field_name, sample, id=f"{cls.__name__}.{field_name}")
            )
    return params


# ---------------------------------------------------------------------------
# Entity scalar round-trip
# ---------------------------------------------------------------------------

class TestEntityFieldRoundtrip:
    @pytest.mark.parametrize("entity_key,entity_cls,field_name,sample", _entity_parametrize())
    def test_field_survives_from_dict(self, entity_key, entity_cls, field_name, sample):
        spec = {
            "entities": {
                entity_key: [
                    {"id": "A", "type": "T", field_name: sample}
                ]
            }
        }
        chart = ANXChart.from_dict(spec)
        assert len(chart._entities) == 1
        entity = chart._entities[0]
        assert isinstance(entity, entity_cls), (
            f"from_dict produced {type(entity).__name__} for key {entity_key!r}, "
            f"expected {entity_cls.__name__}"
        )
        got = getattr(entity, field_name)
        assert got == sample, (
            f"{entity_cls.__name__}.{field_name}: from_dict lost the value. "
            f"Expected {sample!r}, got {got!r}"
        )


# ---------------------------------------------------------------------------
# Link scalar round-trip
# ---------------------------------------------------------------------------

def _link_field_cases():
    hints = get_type_hints(Link, localns={"Card": _CardModel})
    cases = []
    for f in dataclasses.fields(Link):
        if f.name in _NESTED_DATACLASS_FIELDS or f.name in _INTERNAL_ROUTING_FIELDS:
            continue
        if f.name in ("from_id", "to_id", "type"):
            continue
        sample = _sample_for_type(hints[f.name], f.name)
        if sample is None:
            continue
        cases.append(pytest.param(f.name, sample, id=f"Link.{f.name}"))
    return cases


class TestLinkFieldRoundtrip:
    @pytest.mark.parametrize("field_name,sample", _link_field_cases())
    def test_field_survives_from_dict(self, field_name, sample):
        spec = {
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person"},
                    {"id": "B", "type": "Person"},
                ]
            },
            "links": [
                {
                    "from_id": "A",
                    "to_id": "B",
                    "type": "Call",
                    field_name: sample,
                }
            ],
        }
        chart = ANXChart.from_dict(spec)
        assert len(chart._links) == 1
        link = chart._links[0]
        got = getattr(link, field_name)
        assert got == sample, (
            f"Link.{field_name}: from_dict lost the value. "
            f"Expected {sample!r}, got {got!r}"
        )


# ---------------------------------------------------------------------------
# Nested-dataclass coverage (hand-written)
# ---------------------------------------------------------------------------

class TestNestedDataclassFields:
    def test_icon_label_font_builds_font_dataclass(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {
                            "id": "A",
                            "type": "T",
                            "label_font": Font(name="Tahoma", bold=True),
                        }
                    ]
                }
            }
        )
        icon = chart._entities[0]
        assert isinstance(icon.label_font, Font)
        assert icon.label_font.name == "Tahoma"
        assert icon.label_font.bold is True

    def test_icon_frame_builds_frame_dataclass(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {"id": "A", "type": "T", "frame": Frame(color="Red")}
                    ]
                }
            }
        )
        assert isinstance(chart._entities[0].frame, Frame)
        assert chart._entities[0].frame.color == "Red"

    def test_icon_show_builds_show_dataclass(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {"id": "A", "type": "T", "show": Show(label=True, date=True)}
                    ]
                }
            }
        )
        assert isinstance(chart._entities[0].show, Show)
        assert chart._entities[0].show.label is True
        assert chart._entities[0].show.date is True

    def test_icon_timezone_from_dict(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {
                            "id": "A",
                            "type": "T",
                            "date": "2024-01-15",
                            "time": "12:00:00",
                            "timezone": {"id": 1, "name": "UTC"},
                        }
                    ]
                }
            }
        )
        tz = chart._entities[0].timezone
        assert isinstance(tz, TimeZone)
        assert tz.id == 1
        assert tz.name == "UTC"

    def test_icon_attributes_dict_roundtrips(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {
                            "id": "A",
                            "type": "T",
                            "attributes": {"phone": "555-0001", "calls": 12},
                        }
                    ]
                }
            }
        )
        attrs = chart._entities[0].attributes
        assert attrs["phone"] == "555-0001"
        assert attrs["calls"] == 12

    def test_icon_cards_build_card_dataclasses(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {
                            "id": "A",
                            "type": "T",
                            "cards": [
                                {
                                    "summary": "Main",
                                    "date": "2024-01-15",
                                    "time": "14:30:00",
                                }
                            ],
                        }
                    ]
                }
            }
        )
        cards = chart._entities[0].cards
        assert len(cards) == 1
        assert isinstance(cards[0], Card)
        assert cards[0].summary == "Main"

    def test_link_label_font_builds_font(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {"id": "A", "type": "T"},
                        {"id": "B", "type": "T"},
                    ]
                },
                "links": [
                    {
                        "from_id": "A",
                        "to_id": "B",
                        "type": "Rel",
                        "label_font": Font(size=14),
                    }
                ],
            }
        )
        assert chart._links[0].label_font.size == 14

    def test_link_timezone_from_dict(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {"id": "A", "type": "T"},
                        {"id": "B", "type": "T"},
                    ]
                },
                "links": [
                    {
                        "from_id": "A",
                        "to_id": "B",
                        "type": "Rel",
                        "date": "2024-01-15",
                        "time": "12:00:00",
                        "timezone": {"id": 32, "name": "GMT"},
                    }
                ],
            }
        )
        assert chart._links[0].timezone.id == 32

    def test_card_timezone_inside_entity(self):
        chart = ANXChart.from_dict(
            {
                "entities": {
                    "icons": [
                        {
                            "id": "A",
                            "type": "T",
                            "cards": [
                                {
                                    "summary": "Main",
                                    "date": "2024-01-15",
                                    "time": "12:00:00",
                                    "timezone": {"id": 1, "name": "UTC"},
                                }
                            ],
                        }
                    ]
                }
            }
        )
        card_tz = chart._entities[0].cards[0].timezone
        assert isinstance(card_tz, TimeZone)
        assert card_tz.id == 1


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------

class TestMatrixSanity:
    def test_entity_matrix_is_non_trivial(self):
        """If this drops to near-zero, the generator is broken."""
        assert len(_entity_parametrize()) >= 30, (
            "Entity field matrix collapsed — _sample_for_type or field "
            "discovery is probably broken."
        )

    def test_link_matrix_is_non_trivial(self):
        assert len(_link_field_cases()) >= 5

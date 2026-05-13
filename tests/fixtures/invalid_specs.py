"""Minimal invalid spec dicts for validation-error equivalence tests.

Each entry targets one ErrorType category. The spec is the smallest possible
shape that triggers the error; everything else is a bare valid chart so the
error list contains only what we intend.

All specs are in the ``from_dict`` shape — the same specs are fed through
every supported input form in ``tests/test_validation_equivalence.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from anxwritter.errors import ErrorType


# Each entry: (name, spec, expected_error_types_set)
INVALID_SPECS: List[tuple] = [
    # ── Duplicate entity ID ─────────────────────────────────────────────────
    (
        "duplicate_icon_id",
        {
            "entities": {
                "icons": [
                    {"id": "Alice", "type": "Person"},
                    {"id": "Alice", "type": "Person"},
                ]
            }
        },
        {ErrorType.DUPLICATE_ID.value},
    ),

    # ── Link references a missing entity ────────────────────────────────────
    (
        "link_missing_endpoint",
        {
            "entities": {"icons": [{"id": "Alice", "type": "Person"}]},
            "links": [{"from_id": "Alice", "to_id": "Ghost", "type": "Call"}],
        },
        {ErrorType.MISSING_ENTITY.value},
    ),

    # ── Self-loop link ──────────────────────────────────────────────────────
    (
        "self_loop_link",
        {
            "entities": {"icons": [{"id": "Alice", "type": "Person"}]},
            "links": [{"from_id": "Alice", "to_id": "Alice", "type": "Call"}],
        },
        {ErrorType.SELF_LOOP.value},
    ),

    # ── Grade index out of range ────────────────────────────────────────────
    (
        "grade_index_out_of_range",
        {
            "entities": {
                "icons": [{"id": "A", "type": "Person", "grade_one": 99}]
            },
            "grades_one": {"items": ["Reliable", "Unreliable"]},
        },
        {ErrorType.GRADE_OUT_OF_RANGE.value},
    ),

    # ── Unknown grade name ──────────────────────────────────────────────────
    (
        "unknown_grade_name",
        {
            "entities": {
                "icons": [{"id": "A", "type": "Person", "grade_one": "Bogus"}]
            },
            "grades_one": {"items": ["Reliable", "Unreliable"]},
        },
        {ErrorType.UNKNOWN_GRADE.value},
    ),

    # ── Unknown color string ────────────────────────────────────────────────
    (
        "unknown_color_name",
        {
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person", "color": "not-a-color"}
                ]
            }
        },
        {ErrorType.UNKNOWN_COLOR.value},
    ),

    # ── Invalid date format ─────────────────────────────────────────────────
    (
        "invalid_date_format",
        {
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person", "date": "2024/01/15"}
                ]
            }
        },
        {ErrorType.INVALID_DATE.value},
    ),

    # ── Invalid time format ─────────────────────────────────────────────────
    (
        "invalid_time_format",
        {
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person", "time": "25:99:99"}
                ]
            }
        },
        {ErrorType.INVALID_TIME.value},
    ),

    # ── Attribute type conflict (phone used as str + int) ───────────────────
    (
        "attribute_type_conflict",
        {
            "entities": {
                "icons": [
                    {
                        "id": "A",
                        "type": "Person",
                        "attributes": {"phone": "555-0001"},
                    },
                    {
                        "id": "B",
                        "type": "Person",
                        "attributes": {"phone": 5550002},
                    },
                ]
            }
        },
        {ErrorType.TYPE_CONFLICT.value},
    ),

    # ── Strength reference not registered ───────────────────────────────────
    (
        "unknown_strength_name",
        {
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person", "strength": "Tentative"}
                ]
            }
        },
        {ErrorType.INVALID_STRENGTH.value},
    ),

    # ── Invalid strength default ────────────────────────────────────────────
    (
        "invalid_strength_default",
        {
            "strengths": {
                "default": "DoesNotExist",
                "items": [{"name": "Confirmed", "dot_style": "solid"}],
            },
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
        },
        {ErrorType.INVALID_STRENGTH_DEFAULT.value},
    ),

    # ── ordered=True between non-ThemeLine ends ─────────────────────────────
    (
        "invalid_ordered_link",
        {
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
                    "ordered": True,
                    "date": "2024-01-15",
                    "time": "12:00:00",
                }
            ],
        },
        {ErrorType.INVALID_ORDERED.value},
    ),

    # ── Missing required fields on entity ───────────────────────────────────
    (
        "missing_entity_type",
        {
            "entities": {
                "icons": [{"id": "A"}]
            }
        },
        {ErrorType.MISSING_REQUIRED.value},
    ),

    # ── Invalid arrow style ─────────────────────────────────────────────────
    (
        "invalid_arrow_style",
        {
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
                    "arrow": "sideways",
                }
            ],
        },
        {ErrorType.INVALID_ARROW.value},
    ),

    # ── Unknown semantic_type ──────────────────────────────────────────────
    (
        "unknown_semantic_type",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "attribute_classes": [
                {"name": "Foo", "type": "text", "semantic_type": "Not Registered"},
            ],
        },
        {ErrorType.UNKNOWN_SEMANTIC_TYPE.value},
    ),

    # ── Invalid geo_map configuration ──────────────────────────────────────
    (
        "invalid_geo_map",
        {
            "settings": {
                "extra_cfg": {
                    "geo_map": {
                        "mode": "both",
                        "data": {"Palmas/TO": [-10.18, -48.33]},
                        # attribute_name missing — required
                    }
                }
            },
            "entities": {
                "icons": [{"id": "A", "type": "Person"}]
            },
        },
        {ErrorType.INVALID_GEO_MAP.value},
    ),
]


SPEC_INDEX: Dict[str, Dict[str, Any]] = {name: spec for name, spec, _ in INVALID_SPECS}
EXPECTED: Dict[str, Set[str]] = {name: exp for name, _, exp in INVALID_SPECS}

"""Minimal invalid spec dicts for validation-error equivalence tests.

Each entry targets one ErrorType category. The spec is the smallest possible
shape that triggers the error; everything else is a bare valid chart so the
error list contains only what we intend.

All specs are in the ``from_dict`` shape — the same specs are fed through
every supported input form in ``tests/test_validation_equivalence.py``.
"""

from __future__ import annotations

from typing import Dict, List, Set

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

    # ── Invalid icon_map configuration ─────────────────────────────────────
    (
        "icon_map_invalid",
        {
            "settings": {
                "extra_cfg": {
                    "icon_map": {
                        "rules": [
                            # attribute rule missing attribute_name
                            {"match": "attribute", "mapping": {"400": "itau"}},
                        ]
                    }
                }
            },
            "entities": {
                "icons": [{"id": "A", "type": "Person"}]
            },
        },
        {ErrorType.ICON_MAP_INVALID.value},
    ),

    # ── Invalid custom_icons_include value ─────────────────────────────────
    (
        "invalid_custom_icons_include",
        {
            "settings": {
                "extra_cfg": {"custom_icons_include": "bogus"}
            },
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
        },
        {ErrorType.INVALID_CUSTOM_ICONS_INCLUDE.value},
    ),

    # ── Styling: intensity without attribute ───────────────────────────────
    (
        "intensity_missing_attribute",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"intensity": {
                        # 'attribute' missing — required (no top-level shortcut either)
                        "width": {"range": [1, 10]},
                    }}}
                }
            },
            "entities": {"icons": [
                {"id": "A", "type": "Person"},
                {"id": "B", "type": "Person"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"amount": 5}}],
        },
        {ErrorType.INVALID_INTENSITY_ATTRIBUTE.value},
    ),

    # ── Styling: intensity scale=log with non-positive value ───────────────
    (
        "intensity_log_with_zero",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"intensity": {
                        "attribute": "amount", "scale": "log",
                        "width": {"range": [1, 10]},
                    }}}
                }
            },
            "entities": {"icons": [
                {"id": "A", "type": "Person"},
                {"id": "B", "type": "Person"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"amount": 0}}],
        },
        {ErrorType.INVALID_INTENSITY_DOMAIN.value},
    ),

    # ── Styling: intensity range backwards ─────────────────────────────────
    (
        "intensity_bad_range",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"intensity": {
                        "attribute": "amount",
                        "width": {"range": [10, 1]},
                    }}}
                }
            },
            "entities": {"icons": [
                {"id": "A", "type": "Person"},
                {"id": "B", "type": "Person"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"amount": 5}}],
        },
        {ErrorType.INVALID_INTENSITY_RANGE.value},
    ),

    # ── Styling: intensity ramp with one color ─────────────────────────────
    (
        "intensity_short_ramp",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"intensity": {
                        "attribute": "amount",
                        "color": {"ramp": ["Red"]},
                    }}}
                }
            },
            "entities": {"icons": [
                {"id": "A", "type": "Person"},
                {"id": "B", "type": "Person"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"amount": 5}}],
        },
        {ErrorType.INVALID_INTENSITY_RAMP.value},
    ),

    # ── Styling: intensity scale='power' without 'power' field ─────────────
    (
        "intensity_power_without_value",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"intensity": {
                        "attribute": "amount", "scale": "power",
                        "width": {"range": [1, 10]},
                    }}}
                }
            },
            "entities": {"icons": [
                {"id": "A", "type": "Person"},
                {"id": "B", "type": "Person"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"amount": 5}}],
        },
        {ErrorType.INVALID_INTENSITY_CONFIG.value},
    ),

    # ── Styling: categorical without attribute ─────────────────────────────
    (
        "categorical_missing_attribute",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"categorical": {
                        # 'attribute' missing — required
                        "styles": {"Witness": {"line_color": "Green"}},
                    }}}
                }
            },
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
        },
        {ErrorType.INVALID_CATEGORICAL_ATTRIBUTE.value},
    ),

    # ── Styling: categorical with empty styles ─────────────────────────────
    (
        "categorical_empty_styles",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"categorical": {
                        "attribute": "source_type",
                        # 'styles' missing — required to be non-empty
                    }}}
                }
            },
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
        },
        {ErrorType.INVALID_CATEGORICAL_CONFIG.value},
    ),

    # ── Styling: categorical style with no settable fields ─────────────────
    (
        "categorical_empty_style_entry",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {"categorical": {
                        "attribute": "source_type",
                        "styles": {"Witness": {}},  # no line_color/width/strength
                    }}}
                }
            },
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
        },
        {ErrorType.INVALID_CATEGORICAL_STYLE.value},
    ),

    # ── Styling: intensity + categorical on same attribute ─────────────────
    (
        "styling_intensity_categorical_conflict",
        {
            "settings": {
                "extra_cfg": {
                    "styling": {"links": {
                        "intensity": {
                            "attribute": "risk",
                            "width": {"range": [1, 5]},
                        },
                        "categorical": {
                            "attribute": "risk",
                            "styles": {"high": {"line_color": "Red"}},
                        },
                    }}
                }
            },
            "entities": {"icons": [
                {"id": "A", "type": "Person"},
                {"id": "B", "type": "Person"},
            ]},
            "links": [{"from_id": "A", "to_id": "B", "type": "Call",
                       "attributes": {"risk": 1}}],
        },
        {ErrorType.STYLING_CONFLICT.value},
    ),

    # ── Datetime + visible=True forbidden ───────────────────────────────────
    (
        "datetime_visible_true_forbidden",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "attribute_classes": [
                {"name": "EventDate", "type": "datetime", "visible": True},
            ],
        },
        {ErrorType.DATETIME_AC_FORBIDS_VISIBLE.value},
    ),

    # ── display_attribute: placeholder template with no sources to fill it ───
    # (A static, placeholder-free template with no sources is now valid; only a
    # template that references placeholders still requires sources.)
    (
        "display_invalid_placeholder_without_sources",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "settings": {
                "extra_cfg": {
                    "display_attribute": [
                        {
                            "key": "d1",
                            "attribute_name": "Activity",
                            "template": "{q}",
                            "sources": [],
                        },
                    ],
                },
            },
        },
        {ErrorType.DISPLAY_INVALID.value},
    ),

    # ── display_attribute: synthesized name collides with explicit AC ───────
    (
        "display_name_collides_with_ac",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "attribute_classes": [
                {"name": "tx", "type": "number", "visible": False},
                {"name": "Activity", "type": "text"},  # explicit AC
            ],
            "settings": {
                "extra_cfg": {
                    "display_attribute": [
                        {
                            "key": "d1",
                            "attribute_name": "Activity",  # collision
                            "template": "{tx}",
                            "sources": [{"attribute": "tx"}],
                        },
                    ],
                },
            },
        },
        {ErrorType.DISPLAY_NAME_COLLISION.value},
    ),

    # ── display_label: two untyped entries overlap on the label slot ────────
    (
        "display_overlap_conflict",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "attribute_classes": [
                {"name": "x", "type": "text"},
            ],
            "settings": {
                "extra_cfg": {
                    "display_label": [
                        {"key": "a", "template": "{x}",
                         "sources": [{"attribute": "x"}]},
                        {"key": "b", "template": "{x}",
                         "sources": [{"attribute": "x"}]},
                    ],
                },
            },
        },
        {ErrorType.DISPLAY_OVERLAP_CONFLICT.value},
    ),

    # ── 1.17.0 value enforcement ────────────────────────────────────────────

    # EntityType.enforce.id_pattern fails against entity.id
    (
        "id_pattern_mismatch",
        {
            "entity_types": [
                {"name": "Person", "icon_file": "person",
                 "enforce": {"id_pattern": r"^\d{11}$",
                             "id_pattern_description": "11 digits"}},
            ],
            "entities": {"icons": [{"id": "abc", "type": "Person"}]},
        },
        {ErrorType.ID_PATTERN_MISMATCH.value},
    ),

    # AttributeClass.enforce.pattern fails against attribute value
    (
        "attribute_pattern_mismatch",
        {
            "attribute_classes": [
                {"name": "CPF", "type": "text",
                 "enforce": {"pattern": r"^\d{11}$",
                             "description": "digits only"}},
            ],
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person",
                     "attributes": {"CPF": "123.456.789-01"}},
                ]
            },
        },
        {ErrorType.ATTRIBUTE_PATTERN_MISMATCH.value},
    ),

    # AttributeClass.enforce.allowed_values fails against attribute value
    (
        "attribute_value_not_allowed",
        {
            "attribute_classes": [
                {"name": "Status", "type": "text",
                 "enforce": {"allowed_values": ["Active", "Inactive"]}},
            ],
            "entities": {
                "icons": [
                    {"id": "A", "type": "Person",
                     "attributes": {"Status": "active"}},
                ]
            },
        },
        {ErrorType.ATTRIBUTE_VALUE_NOT_ALLOWED.value},
    ),

    # EntityType.enforce.required_attributes — entity missing a required attr
    (
        "required_attribute_missing",
        {
            "entity_types": [
                {"name": "Person", "icon_file": "person",
                 "enforce": {"required_attributes": ["CPF"]}},
            ],
            "entities": {
                "icons": [{"id": "A", "type": "Person"}],
            },
        },
        {ErrorType.REQUIRED_ATTRIBUTE_MISSING.value},
    ),

    # validators[]: neither entity_type nor link_type set → invalid scope
    (
        "validator_invalid_scope",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "validators": [
                {"attribute": "CPF", "pattern": r"^\d{11}$",
                 "description": "digits"},
            ],
        },
        {ErrorType.VALIDATOR_INVALID_SCOPE.value},
    ),

    # validators[]: neither pattern nor allowed_values set → invalid shape
    (
        "validator_invalid_shape",
        {
            "entity_types": [{"name": "Person", "icon_file": "person"}],
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "validators": [
                {"entity_type": "Person", "attribute": "CPF"},
            ],
        },
        {ErrorType.VALIDATOR_INVALID_SHAPE.value},
    ),

    # validators[]: attribute='id' is reserved
    (
        "validator_reserved_attribute",
        {
            "entity_types": [{"name": "Person", "icon_file": "person"}],
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "validators": [
                {"entity_type": "Person", "attribute": "id",
                 "pattern": r"^\d+$", "description": "digits"},
            ],
        },
        {ErrorType.VALIDATOR_RESERVED_ATTRIBUTE.value},
    ),

    # validators[]: references an unregistered type
    (
        "validator_unknown_type",
        {
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "validators": [
                {"entity_type": "Ghost", "attribute": "CPF",
                 "pattern": r"^\d{11}$", "description": "digits"},
            ],
        },
        {ErrorType.VALIDATOR_UNKNOWN_TYPE.value},
    ),

    # validators[]: two entries with the same synthesized key
    (
        "validator_duplicate_key",
        {
            "entity_types": [{"name": "Person", "icon_file": "person"}],
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
            "validators": [
                {"entity_type": "Person", "attribute": "CPF",
                 "pattern": r"^\d{11}$", "description": "v1"},
                {"entity_type": "Person", "attribute": "CPF",
                 "allowed_values": ["x", "y"]},
            ],
        },
        # Both `validator_duplicate_key` and (since the duplicate happens via
        # field-merge in the loader → produces a merged shape with both
        # pattern AND allowed_values set) `validator_invalid_shape`. The
        # spec asserts the duplicate-key error; the equivalence runner
        # tolerates additional emitted error types.
        {ErrorType.VALIDATOR_DUPLICATE_KEY.value},
    ),

    # AttributeClass.enforce.pattern WITHOUT enforce.description
    (
        "pattern_missing_description",
        {
            "attribute_classes": [
                {"name": "CPF", "type": "text",
                 "enforce": {"pattern": r"^\d{11}$"}},
            ],
            "entities": {"icons": [{"id": "A", "type": "Person"}]},
        },
        {ErrorType.PATTERN_MISSING_DESCRIPTION.value},
    ),
]


EXPECTED: Dict[str, Set[str]] = {name: exp for name, _, exp in INVALID_SPECS}

"""Validation errors for anxwritter chart data."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class ErrorType(str, Enum):
    """Validation error type strings.

    Central registry of all error types used by validate(). Using this enum
    prevents typos and enables IDE autocomplete in tests.
    """
    # Required field errors
    MISSING_REQUIRED = 'missing_required'

    # Duplicate errors
    DUPLICATE_ID = 'duplicate_id'
    DUPLICATE_NAME = 'duplicate_name'

    # Reference errors
    MISSING_ENTITY = 'missing_entity'
    MISSING_TARGET = 'missing_target'

    # Format/value errors
    UNKNOWN_COLOR = 'unknown_color'
    INVALID_DATE = 'invalid_date'
    INVALID_TIME = 'invalid_time'
    INVALID_VALUE = 'invalid_value'
    TYPE_CONFLICT = 'type_conflict'
    INVALID_ARROW = 'invalid_arrow'
    SELF_LOOP = 'self_loop'

    # Strength errors
    INVALID_STRENGTH = 'invalid_strength'
    INVALID_STRENGTH_DEFAULT = 'invalid_strength_default'

    # Grade errors
    INVALID_GRADE_DEFAULT = 'invalid_grade_default'
    GRADE_OUT_OF_RANGE = 'grade_out_of_range'
    UNKNOWN_GRADE = 'unknown_grade'

    # Ordered link errors
    INVALID_ORDERED = 'invalid_ordered'

    # Legend errors
    INVALID_LEGEND_TYPE = 'invalid_legend_type'

    # Timezone errors
    INVALID_TIMEZONE = 'invalid_timezone'
    TIMEZONE_WITHOUT_DATETIME = 'timezone_without_datetime'

    # Connection errors
    INVALID_MULTIPLICITY = 'invalid_multiplicity'
    INVALID_THEME_WIRING = 'invalid_theme_wiring'
    CONNECTION_CONFLICT = 'connection_conflict'

    # Config errors
    CONFIG_CONFLICT = 'config_conflict'

    # Palette errors
    PALETTE_TYPE_MISMATCH = 'palette_type_mismatch'
    PALETTE_UNKNOWN_REF = 'palette_unknown_ref'
    PALETTE_INVALID_CLASS = 'palette_invalid_class'

    # Representation errors
    UNSUPPORTED_REPRESENTATION = 'unsupported_representation'

    # Datetime format errors
    UNREGISTERED_DATETIME_FORMAT = 'unregistered_datetime_format'

    # Semantic type errors
    INVALID_SEMANTIC_TYPE = 'invalid_semantic_type'
    UNKNOWN_SEMANTIC_TYPE = 'unknown_semantic_type'

    # Attribute class behaviour errors
    INVALID_MERGE_BEHAVIOUR = 'invalid_merge_behaviour'
    INVALID_PASTE_BEHAVIOUR = 'invalid_paste_behaviour'

    # Geo-map errors
    INVALID_GEO_MAP = 'invalid_geo_map'

    # Icon-map errors (extra_cfg.icon_map)
    ICON_MAP_INVALID = 'icon_map_invalid'

    # Custom-icon catalog (1.20.0)
    INVALID_CUSTOM_ICONS_INCLUDE = 'invalid_custom_icons_include'

    # Styling errors (extra_cfg.styling.links.{intensity,categorical})
    INVALID_INTENSITY_CONFIG = 'invalid_intensity_config'
    INVALID_INTENSITY_ATTRIBUTE = 'invalid_intensity_attribute'
    INVALID_INTENSITY_DOMAIN = 'invalid_intensity_domain'
    INVALID_INTENSITY_RANGE = 'invalid_intensity_range'
    INVALID_INTENSITY_RAMP = 'invalid_intensity_ramp'
    INVALID_CATEGORICAL_CONFIG = 'invalid_categorical_config'
    INVALID_CATEGORICAL_ATTRIBUTE = 'invalid_categorical_attribute'
    INVALID_CATEGORICAL_STYLE = 'invalid_categorical_style'
    STYLING_CONFLICT = 'styling_conflict'

    # Datetime AC canvas-render guard (ANB v9: datetime values never render on
    # the canvas, so a visible datetime AC is rejected — synthesize a
    # display_attribute text sibling instead). Independent of any synthesizer
    # entry point.
    DATETIME_AC_FORBIDS_VISIBLE = 'datetime_ac_forbids_visible'

    # Display synthesizer errors (extra_cfg.display_attribute / display_label)
    DISPLAY_INVALID = 'display_invalid'
    DISPLAY_NAME_COLLISION = 'display_name_collision'
    DISPLAY_OVERLAP_CONFLICT = 'display_overlap_conflict'

    # Config-layering errors (config-vs-config leaf locking + delete operation)
    LOCKED_OVERRIDE = 'locked_override'
    DELETE_CONTRACT = 'delete_contract'

    # Value enforcement (1.17.0) — id_pattern on EntityType/LinkType,
    # value_pattern / allowed_values on AttributeClass, top-level validators.
    ID_PATTERN_MISMATCH = 'id_pattern_mismatch'
    ATTRIBUTE_PATTERN_MISMATCH = 'attribute_pattern_mismatch'
    ATTRIBUTE_VALUE_NOT_ALLOWED = 'attribute_value_not_allowed'
    REQUIRED_ATTRIBUTE_MISSING = 'required_attribute_missing'
    INVALID_VALIDATOR_PATTERN = 'invalid_validator_pattern'
    VALIDATOR_UNKNOWN_TYPE = 'validator_unknown_type'
    VALIDATOR_INVALID_SCOPE = 'validator_invalid_scope'
    VALIDATOR_INVALID_SHAPE = 'validator_invalid_shape'
    VALIDATOR_DUPLICATE_KEY = 'validator_duplicate_key'
    VALIDATOR_RESERVED_ATTRIBUTE = 'validator_reserved_attribute'
    PATTERN_MISSING_DESCRIPTION = 'pattern_missing_description'


class ANXValidationError(Exception):
    """Raised when chart data contains validation errors.

    Attributes:
        errors: List of structured error dicts.

    The error dict shape — ``type``, ``location``, ``message`` — is the
    stable contract. The optional ``source`` key (and ``config_source`` on
    ``config_conflict`` errors) identifies the config layer that contributed
    the offending entry; present only when the entry was applied via
    :meth:`ANXChart.apply_config` / :meth:`ANXChart.apply_config_file` with a
    known ``source_name``. The optional ``rule_source`` key (added in 1.17.0
    on value-enforcement errors) identifies which value rule fired —
    ``attribute_class[<name>]`` or ``validator[<synthetic_key>]``.

    The string returned by ``str(exc)`` is intentionally NOT a stable contract
    — match on the dict keys, not the formatted message. The renderer
    smart-truncates rule-grouped errors (1.17.0) so a 50k-row failure produces
    a readable summary instead of 50k lines; the underlying ``errors`` list is
    kept uncapped for programmatic consumers.
    """

    def __init__(self, errors: List[Dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(_format_validation_message(errors))


def _format_error_line(err: Dict[str, Any], indent: str = '  - ') -> str:
    """Format one error dict for the ANXValidationError message body.

    Appends a ``(source: X)`` suffix when ``err`` has a ``source`` key, or a
    ``(config source: X)`` suffix for ``config_conflict`` errors carrying
    ``config_source``. Message-string format is documented as unstable —
    callers should consume the dict keys, not parse this output.
    """
    line = f"{indent}[{err['type']}] {err['message']}"
    src = err.get('source') or err.get('config_source')
    if src:
        label = 'config source' if 'config_source' in err and 'source' not in err else 'source'
        line += f" ({label}: {src})"
    return line


def _format_validation_message(
    errors: List[Dict[str, Any]],
    max_per_group: int = 5,
) -> str:
    """Build the ``str(exc)`` body for ``ANXValidationError``.

    Errors carrying a ``rule_source`` key (value-enforcement errors from
    AttributeClass.enforce / EntityType.enforce / LinkType.enforce / the
    top-level ``validators`` section) are grouped by ``(rule_source, type)``;
    groups above ``max_per_group`` are truncated with a "... N more" tail.

    Errors without ``rule_source`` render one per line (the pre-1.17.0
    behaviour), so existing error shapes are unaffected.

    The string format is explicitly unstable — consumers should match on
    the dict keys in ``ANXValidationError.errors``.
    """
    if not errors:
        return "0 validation error(s) in chart data."

    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    ungrouped: List[Dict[str, Any]] = []
    for e in errors:
        rs = e.get('rule_source')
        if rs:
            grouped.setdefault((rs, e.get('type', '?')), []).append(e)
        else:
            ungrouped.append(e)

    lines = [f"{len(errors)} validation error(s) in chart data:"]

    # Ungrouped errors first — preserves existing format and ordering.
    for e in ungrouped:
        lines.append(_format_error_line(e))

    # Grouped errors — small groups render normally, large groups truncate.
    for key in sorted(grouped.keys()):
        rs, etype = key
        group = grouped[key]
        count = len(group)
        if count <= max_per_group:
            for e in group:
                lines.append(_format_error_line(e))
        else:
            lines.append(
                f"  [{etype}] from {rs} ({count} rows — "
                f"showing first {max_per_group}):"
            )
            for e in group[:max_per_group]:
                lines.append(_format_error_line(e, indent='    - '))
            remaining = count - max_per_group
            lines.append(
                f"    ... {remaining} more "
                f"(consume chart.validate() for the full list)"
            )

    return "\n".join(lines)

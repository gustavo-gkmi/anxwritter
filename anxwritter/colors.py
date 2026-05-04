"""
Color utilities for i2 Analyst's Notebook ANX files.

ANB uses Windows COLORREF integers: ``R + G*256 + B*65536``
(little-endian BGR, upper byte always 0).
"""
from typing import Any, Dict


def rgb_to_colorref(r: int, g: int, b: int) -> int:
    """Convert an (R, G, B) triple to a Windows COLORREF integer."""
    return r + g * 256 + b * 65536


# Named color palette — matches i2 ANB's 40 shading-color names.
# Values are COLORREF integers (BGR order).
NAMED_COLORS = {
    'Black':           rgb_to_colorref(0,   0,   0),
    'Brown':           rgb_to_colorref(153, 51,  0),
    'Olive Green':     rgb_to_colorref(51,  51,  0),
    'Dark Green':      rgb_to_colorref(0,   51,  0),
    'Dark Teal':       rgb_to_colorref(0,   51,  102),
    'Dark Blue':       rgb_to_colorref(0,   0,   128),
    'Indigo':          rgb_to_colorref(51,  51,  153),
    'Dark Grey':       rgb_to_colorref(51,  51,  51),
    'Dark Red':        rgb_to_colorref(128, 0,   0),
    'Orange':          rgb_to_colorref(255, 102, 0),
    'Dark Yellow':     rgb_to_colorref(128, 128, 0),
    'Green':           rgb_to_colorref(0,   128, 0),
    'Teal':            rgb_to_colorref(0,   128, 128),
    'Blue':            rgb_to_colorref(0,   0,   255),
    'Blue-Grey':       rgb_to_colorref(102, 102, 153),
    'Grey':            rgb_to_colorref(128, 128, 128),
    'Red':             rgb_to_colorref(255, 0,   0),
    'Light Orange':    rgb_to_colorref(255, 153, 0),
    'Lime':            rgb_to_colorref(153, 204, 0),
    'Sea Green':       rgb_to_colorref(51,  153, 102),
    'Aqua':            rgb_to_colorref(51,  204, 204),
    'Light Blue':      rgb_to_colorref(51,  102, 255),
    'Violet':          rgb_to_colorref(128, 0,   128),
    'Light Grey':      rgb_to_colorref(153, 153, 153),
    'Pink':            rgb_to_colorref(255, 0,   255),
    'Gold':            rgb_to_colorref(255, 204, 0),
    'Yellow':          rgb_to_colorref(255, 255, 0),
    'Bright Green':    rgb_to_colorref(0,   255, 0),
    'Turquoise':       rgb_to_colorref(0,   255, 255),
    'Sky Blue':        rgb_to_colorref(0,   204, 255),
    'Plum':            rgb_to_colorref(153, 51,  102),
    'Silver':          rgb_to_colorref(192, 192, 192),
    'Rose':            rgb_to_colorref(255, 153, 204),
    'Tan':             rgb_to_colorref(255, 204, 153),
    'Light Yellow':    rgb_to_colorref(255, 255, 153),
    'Light Green':     rgb_to_colorref(204, 255, 204),
    'Light Turquoise': rgb_to_colorref(204, 255, 255),
    'Pale Blue':       rgb_to_colorref(153, 204, 255),
    'Lavender':        rgb_to_colorref(204, 153, 255),
    'White':           rgb_to_colorref(255, 255, 255),
}


def _normalize_name(name: str) -> str:
    """Canonical key for case/punctuation-insensitive color lookups.

    ``'Light Orange'`` / ``'light-orange'`` / ``'light_orange'`` → ``'light_orange'``.
    """
    return name.strip().lower().replace('-', '_').replace(' ', '_')


# Built once at module load — maps normalized name → COLORREF int.
_NAMED_COLORS_NORM: Dict[str, int] = {
    _normalize_name(k): v for k, v in NAMED_COLORS.items()
}


# Resolution order: enum unwrap → int passthrough → exact name → normalized name → hex → ValueError
def color_to_colorref(color: Any) -> int:
    """Return a COLORREF integer for a named, hex, int, or Color enum value.

    Accepts:
    * A ``Color`` enum instance (e.g. ``Color.BLUE``).
    * A named color from *NAMED_COLORS* (e.g. ``'Blue'``).
    * A normalized name (e.g. ``'blue'``, ``'light orange'``, ``'light-orange'``).
    * A 6-digit hex string with optional ``#`` prefix (e.g. ``'#FF0000'``).
    * An integer already formatted as COLORREF (returned as-is).

    Raises ``ValueError`` for unrecognised names.
    """
    # Unwrap Color enum (or any str-Enum) first
    if hasattr(color, 'value'):
        color = color.value
    if isinstance(color, (int, float)) and not isinstance(color, bool):
        return int(color)
    if not isinstance(color, str):
        raise ValueError(
            f"Unknown color {color!r}. "
            f"Use a name from NAMED_COLORS or a hex string like '#FF0000'."
        )
    # Fast path: exact Title Case match
    if color in NAMED_COLORS:
        return NAMED_COLORS[color]
    # Normalized lookup (case/whitespace/hyphen-insensitive)
    norm = _normalize_name(color)
    if norm in _NAMED_COLORS_NORM:
        return _NAMED_COLORS_NORM[norm]
    # Hex color
    s = color.lstrip('#')
    if len(s) == 6:
        try:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return rgb_to_colorref(r, g, b)
        except ValueError:
            pass
    raise ValueError(
        f"Unknown color {color!r}. "
        f"Use a name from NAMED_COLORS or a hex string like '#FF0000'."
    )

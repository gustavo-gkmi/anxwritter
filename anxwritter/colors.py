"""
Color utilities for i2 Analyst's Notebook ANX files.

ANB uses Windows COLORREF integers: ``R + G*256 + B*65536``
(little-endian BGR, upper byte always 0).
"""
import colorsys
import math
from typing import Any, Dict, Optional, Sequence


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


def coerce_color(val: Any) -> Optional[int]:
    """Coerce a colour value to a COLORREF int, or ``None`` for unset/blank input.

    ``None`` / ``''`` / whitespace / ``NaN`` / ``bool`` all collapse to ``None``
    (the "not set" signal shared by the resolve and emit paths). ``Color`` enums
    are unwrapped; ``int`` / ``float`` pass through as ``int``; strings resolve
    via :func:`color_to_colorref` (which raises ``ValueError`` on an unknown
    name — callers that prefer ``None`` should catch it).

    This is the permissive emission-side counterpart to :func:`is_color`, the
    range-checked validation predicate. The two intentionally accept different
    sets: emission trusts already-validated data; validation rejects out-of-range
    ints.
    """
    if val is None:
        return None
    if hasattr(val, 'value'):  # unwrap Color enum / str-Enum
        val = val.value
    if isinstance(val, bool):
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if not s:
        return None
    return color_to_colorref(s)


def is_color(val: Any) -> bool:
    """Return True if *val* is a recognisable colour (None, enum, name, hex, int).

    Range-checked validation predicate: integer / float COLORREF values must be
    within ``0..0xFFFFFF``. ``None`` is accepted (an unset colour is valid). This
    is the validation-side counterpart to :func:`coerce_color`, which trusts
    already-validated data and does no range check.
    """
    if val is None:
        return True
    if hasattr(val, 'value'):  # unwrap Color enum / str-Enum
        val = val.value
    # bool is a subclass of int — must reject before the int branch
    if isinstance(val, bool):
        return False
    if isinstance(val, int):
        return 0 <= val <= 0xFFFFFF
    if isinstance(val, float):
        if math.isnan(val):
            return False
        return 0 <= val <= 0xFFFFFF
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return False
        if _normalize_name(s) in _NAMED_COLORS_NORM:
            return True
        if s.startswith('#') and len(s) == 7:
            try:
                int(s[1:], 16)
                return True
            except ValueError:
                pass
        try:
            color_to_colorref(s)
            return True
        except (ValueError, TypeError):
            pass
    return False


# ── Component split / join helpers ──────────────────────────────────────────


def _colorref_to_rgb(c: int) -> tuple:
    """Split a Windows COLORREF int into (R, G, B) ints in 0–255."""
    r = c & 0xFF
    g = (c >> 8) & 0xFF
    b = (c >> 16) & 0xFF
    return r, g, b


# ── sRGB ↔ linear-light helpers (used by gamma-correct interpolation) ──


def _srgb_to_linear(c: float) -> float:
    """Convert one sRGB component in ``[0, 1]`` to linear light.

    Standard sRGB transfer function. Used by ``lerp_rgb_linear`` so midpoints
    aren't muddy. Endpoints are byte-identical to the naive lerp by construction
    (the function is exact at ``c=0`` and ``c=1``).
    """
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    """Inverse of ``_srgb_to_linear``. Clamps to ``[0, 1]`` for safety."""
    if c <= 0.0:
        return 0.0
    if c >= 1.0:
        return 1.0
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


# ── Color interpolation ────────────────────────────────────────────────────


def lerp_rgb(c1: int, c2: int, t: float) -> int:
    """Naive sRGB component-wise linear interpolation.

    Cheap and predictable, but produces muddy midpoints (red→green goes through
    brown). Use ``lerp_rgb_linear`` for better mid-range fidelity at the cost of
    one extra pow() round-trip.
    """
    if t <= 0.0:
        return c1
    if t >= 1.0:
        return c2
    r1, g1, b1 = _colorref_to_rgb(c1)
    r2, g2, b2 = _colorref_to_rgb(c2)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return rgb_to_colorref(r, g, b)


def lerp_rgb_linear(c1: int, c2: int, t: float) -> int:
    """Gamma-correct sRGB interpolation (round-trip through linear light).

    The mathematically-defensible default. Recommended for sequential ramps.
    """
    if t <= 0.0:
        return c1
    if t >= 1.0:
        return c2
    r1, g1, b1 = _colorref_to_rgb(c1)
    r2, g2, b2 = _colorref_to_rgb(c2)
    # Normalise to [0, 1] and linearise
    lr1, lg1, lb1 = (_srgb_to_linear(x / 255.0) for x in (r1, g1, b1))
    lr2, lg2, lb2 = (_srgb_to_linear(x / 255.0) for x in (r2, g2, b2))
    lr = lr1 + (lr2 - lr1) * t
    lg = lg1 + (lg2 - lg1) * t
    lb = lb1 + (lb2 - lb1) * t
    r = round(_linear_to_srgb(lr) * 255.0)
    g = round(_linear_to_srgb(lg) * 255.0)
    b = round(_linear_to_srgb(lb) * 255.0)
    return rgb_to_colorref(r, g, b)


def lerp_hsl(c1: int, c2: int, t: float) -> int:
    """Interpolate via HLS (a.k.a. HSL) — short way around the hue circle.

    Uses ``colorsys.rgb_to_hls`` / ``hls_to_rgb``. Hue interpolates along the
    shorter of the two arcs between the endpoints; lightness and saturation lerp
    linearly.
    """
    if t <= 0.0:
        return c1
    if t >= 1.0:
        return c2
    r1, g1, b1 = _colorref_to_rgb(c1)
    r2, g2, b2 = _colorref_to_rgb(c2)
    h1, l1, s1 = colorsys.rgb_to_hls(r1 / 255.0, g1 / 255.0, b1 / 255.0)
    h2, l2, s2 = colorsys.rgb_to_hls(r2 / 255.0, g2 / 255.0, b2 / 255.0)
    # Pick the shorter way around the hue circle
    dh = h2 - h1
    if dh > 0.5:
        dh -= 1.0
    elif dh < -0.5:
        dh += 1.0
    h = (h1 + dh * t) % 1.0
    L = l1 + (l2 - l1) * t
    s = s1 + (s2 - s1) * t
    r, g, b = colorsys.hls_to_rgb(h, L, s)
    return rgb_to_colorref(round(r * 255), round(g * 255), round(b * 255))


# Resolution order for the lerp dispatcher.  Default falls through to rgb_linear.
_LERP_BY_SPACE = {
    'rgb': lerp_rgb,
    'rgb_linear': lerp_rgb_linear,
    'hsl': lerp_hsl,
}


def interpolate_ramp(
    ramp: Sequence[int],
    t: float,
    space: str = 'rgb_linear',
) -> int:
    """Evaluate a multi-stop color ramp at ``t`` ∈ ``[0, 1]``.

    Stops are evenly spaced: a two-color ramp interpolates from index 0 to
    index 1; a three-color ramp has the second color at ``t=0.5``. Endpoints
    are exact (``t=0`` returns ``ramp[0]`` byte-identically).

    Args:
        ramp: Sequence of COLORREF integers. Must have at least two entries
            — callers should validate before calling.
        t: Position along the ramp, clamped to ``[0, 1]``.
        space: One of ``'rgb'``, ``'rgb_linear'`` (default), ``'hsl'``.

    Returns:
        A COLORREF integer.
    """
    n = len(ramp)
    if n == 0:
        raise ValueError("interpolate_ramp requires at least one color in ramp")
    if n == 1:
        return ramp[0]
    if t <= 0.0:
        return ramp[0]
    if t >= 1.0:
        return ramp[-1]
    # Locate the segment
    seg_len = 1.0 / (n - 1)
    idx = int(t / seg_len)
    if idx >= n - 1:
        idx = n - 2
    local_t = (t - idx * seg_len) / seg_len
    lerp = _LERP_BY_SPACE.get(space, lerp_rgb_linear)
    return lerp(ramp[idx], ramp[idx + 1], local_t)

"""Embedded custom icons — convert images to ANB ``<CustomImage>`` payloads.

ANB renders a custom icon embedded in an ``.anx`` when the chart carries a
``<CustomImageCollection>`` whose ``<CustomImage>`` uses the composite key
``"<name>,Screen,<Kind>"`` (``Kind`` ∈ ``Icon``/``Attribute``) and an entity
type / attribute class references it by the bare ``<name>`` via ``IconFile``.
The image bytes must be a full 24-bit BMP (magenta = transparent), zlib-
compressed and base64-encoded. ANB extracts the icon on open with no install
and no restart.

Pillow is an optional dependency (``pip install anxwritter[icons]``). It is only
needed to *convert* an arbitrary image; a caller who passes a ready BMP (raw
``bytes`` starting with ``BM``) gets it embedded verbatim using only the standard
library — see :func:`prepare_icon_bmp`.
"""

import base64
import io
import zlib
from typing import Any, Optional, Tuple

try:  # optional dependency
    from PIL import Image
    HAS_PILLOW = True
except ImportError:  # pragma: no cover - exercised via the no-Pillow error path
    HAS_PILLOW = False

#: Prefix applied to every emitted icon name so it can never collide with an
#: ANB built-in icon (numbered ``001``-``757`` or named ``person``/``car``/…),
#: which would otherwise make the embedded image silently lose.
EMITTED_PREFIX = "anxW_"

#: Default maximum icon dimension. ANB rescales to the on-screen slot; the cap
#: is really a byte budget (a too-large BMP renders as a black box).
MAX_SIZE = 128

#: ANB's 1-bit transparency key.
MAGENTA = (255, 0, 255)

# Windows-invalid filename chars plus the comma (which would break the
# ``"<name>,Screen,<Kind>"`` composite key).
_INVALID_NAME_CHARS = set('<>:"/\\|?*,')


class CustomIconError(Exception):
    """Raised when a custom icon image cannot be loaded or converted."""


def validate_icon_name(name: str) -> Optional[str]:
    """Return an error message if *name* is an invalid icon name, else ``None``.

    Checks the user-supplied portion only (the ``anxW_`` prefix is added later
    and is always safe). Rejects empty/whitespace, over-long, and any character
    that is invalid in a Windows filename or that would break the composite key.
    """
    if not name or not str(name).strip():
        return "icon name is empty"
    name = str(name)
    if len(name) > 120:
        return f"icon name too long ({len(name)} chars, max 120)"
    bad = sorted({c for c in name if c in _INVALID_NAME_CHARS or ord(c) < 32})
    if bad:
        shown = ", ".join(repr(c) for c in bad)
        return f"icon name contains invalid character(s): {shown}"
    return None


def coerce_image_source(image: Any) -> Any:
    """Resolve a ``data:...;base64,...`` URI to ``bytes``; pass anything else
    (a path, ``bytes``, or a PIL image) through unchanged.

    Lets the same image value work in Python and in YAML/JSON configs, and lets
    a server send inline image bytes with no filesystem.
    """
    if isinstance(image, str) and image.startswith("data:"):
        try:
            header, b64 = image.split(",", 1)
        except ValueError:
            raise CustomIconError("malformed data: URI (no comma)") from None
        if "base64" not in header:
            raise CustomIconError("only base64 data: URIs are supported")
        try:
            return base64.b64decode(b64)
        except Exception as e:  # noqa: BLE001
            raise CustomIconError(f"invalid base64 in data: URI: {e}") from e
    return image


def composite_key(emitted: str, kind: str = "Icon") -> str:
    """Build the ``<CustomImage>`` ``Id``: ``"<emitted>,Screen,<Kind>"``.

    *kind* is ``"Icon"`` for entity-type icons or ``"Attribute"`` for
    attribute-class icons (singular — ANB routes ``Icon``→``Icons`` and
    ``Attribute``→``Attribs`` folders).
    """
    return f"{emitted},Screen,{kind}"


def _load_image(image: Any) -> "Image.Image":
    if not HAS_PILLOW:
        raise CustomIconError(
            "custom icons require Pillow — install it with: "
            "pip install anxwritter[icons]"
        )
    if isinstance(image, Image.Image):
        return image.convert("RGBA")
    try:
        if isinstance(image, (bytes, bytearray)):
            return Image.open(io.BytesIO(bytes(image))).convert("RGBA")
        return Image.open(image).convert("RGBA")  # filesystem path / file object
    except CustomIconError:
        raise
    except Exception as e:  # noqa: BLE001 - surface any decode failure uniformly
        raise CustomIconError(f"could not read icon image ({image!r}): {e}") from e


def convert_to_bmp(image: Any, max_size: int = MAX_SIZE) -> bytes:
    """Convert any image to a full 24-bit BMP suitable for an ANB custom icon.

    Pipeline (each step handles an ANB rendering constraint):

    - **downscale-only** to fit ``max_size`` (never upscale — keeps pixel art crisp);
    - **pad to square** with magenta (ANB distorts non-square icons into the slot);
    - **hard 1-bit alpha threshold** (ANB's magenta key is 1-bit; anti-aliased edges
      otherwise leave a pink halo);
    - composite onto **magenta (255,0,255)** = ANB's transparent key;
    - emit a **full 24-bit BMP** (32-bit BMP renders as a black box).
    """
    im = _load_image(image)
    w, h = im.size
    scale = min(1.0, max_size / max(w, h))
    if scale < 1.0:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        w, h = im.size
    side = max(w, h)
    alpha = im.split()[3].point(lambda p: 255 if p >= 128 else 0)  # 1-bit mask
    canvas = Image.new("RGB", (side, side), MAGENTA)
    canvas.paste(im.convert("RGB"), ((side - w) // 2, (side - h) // 2), alpha)
    buf = io.BytesIO()
    canvas.save(buf, format="BMP")
    return buf.getvalue()


#: Max dimension for a caller-supplied (passthrough) BMP. ANB renders a too-large
#: icon as a black box; this is the safe ceiling.
MAX_PASSTHROUGH = 256


def is_bmp(image: Any) -> bool:
    """True if *image* is raw bytes that already start with a BMP header."""
    return isinstance(image, (bytes, bytearray)) and bytes(image[:2]) == b'BM'


def _bmp_header(data: bytes) -> Tuple[int, int, int]:
    """Return ``(bpp, width, height)`` from a BMP header; raise if malformed."""
    import struct
    if len(data) < 30 or data[:2] != b'BM':
        raise CustomIconError("not a BMP (missing 'BM' header)")
    bpp = struct.unpack('<H', data[28:30])[0]
    w, h = struct.unpack('<ii', data[18:26])
    return bpp, w, abs(h)


def prepare_icon_bmp(image: Any, max_size: int = MAX_SIZE) -> bytes:
    """Return full BMP bytes ready to embed as a ``<CustomImage>``.

    A caller-supplied **BMP** (``bytes`` starting with ``BM``) is taken
    **verbatim** — no Pillow needed, no conditioning — after a cheap sanity
    check (must be 8- or 24-bit and ≤ ``MAX_PASSTHROUGH`` px; 32-bit and oversize
    BMPs render as a black box in ANB). Any other input (a path, PNG/JPEG bytes,
    or a PIL image) is converted via :func:`convert_to_bmp`, which needs Pillow.
    """
    image = coerce_image_source(image)
    if is_bmp(image):
        data = bytes(image)
        bpp, w, h = _bmp_header(data)
        if bpp not in (8, 24):
            raise CustomIconError(
                f"custom icon BMP must be 8- or 24-bit (got {bpp}-bit; "
                f"32-bit renders as a black box in ANB)"
            )
        if max(w, h) > MAX_PASSTHROUGH:
            raise CustomIconError(
                f"custom icon BMP is too large ({w}x{h}; max "
                f"{MAX_PASSTHROUGH}px — larger renders as a black box)"
            )
        return data
    return convert_to_bmp(image, max_size)


def custom_image_payload(bmp: bytes) -> Tuple[str, int]:
    """Return ``(base64(zlib(bmp)), uncompressed_len)`` for ``<CustomImage Data=…>``.

    zlib level is fixed so the output is deterministic.
    """
    data = base64.b64encode(zlib.compress(bmp, 9)).decode("ascii")
    return data, len(bmp)


def packed_dib(bmp: bytes) -> bytes:
    """Strip the 14-byte ``BITMAPFILEHEADER`` → packed DIB (for ``<IconPicture>``)."""
    return bmp[14:]

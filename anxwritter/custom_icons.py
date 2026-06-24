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
import json
import zlib
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple, Union

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


def decode_payload(data: str) -> bytes:
    """Inverse of :func:`custom_image_payload`'s encoding: base64-decode then
    zlib-inflate back to the raw BMP bytes (for validation / preview / round-trip)."""
    return zlib.decompress(base64.b64decode(data))


def is_baked(image: Any) -> bool:
    """True if *image* can embed with **no Pillow** — a ready BMP, given either as
    raw ``bytes`` or a ``data:image/bmp;base64,...`` URI.

    Used by the config Pillow gate: a config layer may only carry baked icons, so
    anything that would need conversion (a path, PNG/JPEG, PIL image, or a
    ``data:image/png`` URI) returns ``False`` here.
    """
    try:
        return is_bmp(coerce_image_source(image))
    except CustomIconError:
        return False


# ── IconCatalog: a reusable library of baked icons ────────────────────────────

#: ``_meta.format`` marker written by :meth:`IconCatalog.export_catalog`.
CATALOG_FORMAT = "anxwritter-icon-catalog"
#: ``_meta.version`` — the catalog *file* schema version (not the library version).
CATALOG_VERSION = 1


def _load_catalog_doc(path: Union[str, Path]) -> dict:
    """Read a YAML or JSON catalog/config file → dict (``.json`` ⇒ JSON, else YAML)."""
    text = Path(path).read_text(encoding="utf-8")
    if str(path).lower().endswith(".json"):
        return json.loads(text) or {}
    import yaml  # mandatory dependency (pyyaml)
    return yaml.safe_load(text) or {}


def _dump_doc(doc: dict, path: Path, fmt: str) -> str:
    if fmt == "json":
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    else:
        import yaml
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


class IconCatalog:
    """A reusable library of baked custom icons (entity + attribute scopes).

    **Authoring** (Pillow is needed only to convert a non-BMP image)::

        cat = IconCatalog()
        cat.add_custom_entity_icon('suspect', 'suspect.png')
        cat.add_custom_attribute_icon('cpf', 'cpf.png')
        cat.export_catalog('org_icons.yaml')      # baked → Pillow-free thereafter

    The exported file is a plain anxwritter config — ``custom_entity_icons`` /
    ``custom_attribute_icons`` sections with compiled (``data`` / ``datalength``)
    payloads — so it drops straight into ``--config`` / ``apply_config_file`` /
    :meth:`ANXChart.apply_icon_catalog`. A config layer is **baked-only**: a
    teammate or server consuming the catalog needs no Pillow.

    **Consuming** (no Pillow)::

        cat = IconCatalog.from_file('org_icons.yaml')
        chart.apply_icon_catalog(cat, include='referenced')
    """

    def __init__(self) -> None:
        # name -> {emitted, prefix, data, datalength}
        self._entity: dict = {}
        self._attribute: dict = {}

    # ── authoring ─────────────────────────────────────────────────────────
    def add_custom_entity_icon(self, name: str, image: Any, *,
                               prefix: str = EMITTED_PREFIX, printer: bool = False) -> None:
        """Bake *image* and register it under *name* as an **entity** icon."""
        self._bake_into(self._entity, name, image, prefix, printer)

    def add_custom_attribute_icon(self, name: str, image: Any, *,
                                  prefix: str = EMITTED_PREFIX, printer: bool = False) -> None:
        """Bake *image* and register it under *name* as an **attribute** icon."""
        self._bake_into(self._attribute, name, image, prefix, printer)

    @staticmethod
    def _bake_into(registry: dict, name: str, image: Any, prefix: str, printer: bool) -> None:
        if printer:
            raise NotImplementedError(
                "printer=True (high-resolution print icons) is planned but not "
                "yet shipped; use the default screen icon for now"
            )
        if not name or not str(name).strip():
            raise ValueError("custom icon name is empty")
        emitted = f"{prefix}{name}"
        err = validate_icon_name(emitted)
        if err:
            raise ValueError(f"custom icon name {emitted!r}: {err}")
        bmp = prepare_icon_bmp(image)
        data, dlen = custom_image_payload(bmp)
        registry[str(name)] = {"emitted": emitted, "prefix": prefix,
                               "data": data, "datalength": dlen}

    # ── inspection / validation ───────────────────────────────────────────
    def validate(self) -> List[dict]:
        """Return a list of error dicts (empty == valid).

        Checks every entry's emitted name and **blob integrity** — that the
        compiled payload decodes to a sane BMP (8- or 24-bit, ≤256px). A corrupt
        or oversize blob otherwise renders as a *black box* in ANB with no
        diagnostic; this catches it before export/import.
        """
        errors: List[dict] = []
        for scope, registry in (("custom_entity_icons", self._entity),
                                ("custom_attribute_icons", self._attribute)):
            for name, e in registry.items():
                err = validate_icon_name(e["emitted"])
                if err:
                    errors.append({"type": "invalid_icon_name",
                                   "location": f"{scope}[{name}]", "message": err})
                try:
                    bpp, w, h = _bmp_header(decode_payload(e["data"]))
                    if bpp not in (8, 24):
                        errors.append({"type": "invalid_icon_blob",
                                       "location": f"{scope}[{name}]",
                                       "message": f"BMP must be 8- or 24-bit (got {bpp}-bit)"})
                    if max(w, h) > MAX_PASSTHROUGH:
                        errors.append({"type": "invalid_icon_blob",
                                       "location": f"{scope}[{name}]",
                                       "message": f"BMP too large ({w}x{h}; max {MAX_PASSTHROUGH}px)"})
                except Exception as ex:  # noqa: BLE001 - report any decode failure
                    errors.append({"type": "invalid_icon_blob",
                                   "location": f"{scope}[{name}]", "message": str(ex)})
        return errors

    # ── serialization ─────────────────────────────────────────────────────
    @staticmethod
    def _entry_dict(name: str, e: dict) -> dict:
        row = {"name": name, "datalength": e["datalength"], "data": e["data"]}
        if e["prefix"] != EMITTED_PREFIX:
            row["prefix"] = e["prefix"]
        return row

    def to_dict(self) -> dict:
        """Return the config-dict form (compiled payloads, sorted by name —
        deterministic). Shape: ``{custom_entity_icons: [...], custom_attribute_icons: [...]}``."""
        out: dict = {}
        for key, registry in (("custom_entity_icons", self._entity),
                              ("custom_attribute_icons", self._attribute)):
            if registry:
                out[key] = [self._entry_dict(n, registry[n]) for n in sorted(registry)]
        return out

    def export_catalog(self, filepath: Union[str, Path], *, format: str = "yaml",
                       cascade_mode: Optional[str] = None) -> str:
        """Write the catalog as a standalone config file (Pillow-free to consume).

        *format* is ``'yaml'`` (default) or ``'json'``. *cascade_mode* writes a
        ``cascade: {mode: ...}`` block (``merge``/``wipe``/``lock``/``delete``) so
        the file self-describes how it layers. Deterministic — no timestamp.
        """
        if format not in ("yaml", "json"):
            raise ValueError(f"format must be 'yaml' or 'json', got {format!r}")
        doc: dict = {"_meta": {"format": CATALOG_FORMAT, "version": CATALOG_VERSION}}
        if cascade_mode:
            doc["cascade"] = {"mode": cascade_mode}
        doc.update(self.to_dict())
        return _dump_doc(doc, Path(filepath), format)

    def include_in_config(self, config_path: Union[str, Path], *,
                          format: Optional[str] = None) -> str:
        """Fold this catalog's baked icons into an existing config file in place.

        Reads *config_path* (or starts empty if absent), upserts the two icon
        sections by name, and writes it back. Lets a user keep one org config
        instead of juggling a separate catalog file.
        """
        path = Path(config_path)
        doc = _load_catalog_doc(path) if path.exists() else {}
        mine = self.to_dict()
        for key in ("custom_entity_icons", "custom_attribute_icons"):
            if key in mine:
                merged = {e["name"]: e for e in (doc.get(key) or [])}
                for row in mine[key]:
                    merged[row["name"]] = row
                doc[key] = list(merged.values())
        fmt = format or ("json" if str(path).lower().endswith(".json") else "yaml")
        return _dump_doc(doc, path, fmt)

    # ── loading ───────────────────────────────────────────────────────────
    def _load_entry(self, section: str, entry: dict) -> None:
        registry = self._entity if section == "custom_entity_icons" else self._attribute
        name = entry["name"]
        prefix = entry.get("prefix", EMITTED_PREFIX)
        if "data" in entry and "datalength" in entry:   # compiled — no Pillow
            emitted = f"{prefix}{name}"
            err = validate_icon_name(emitted)
            if err:
                raise ValueError(f"custom icon name {emitted!r}: {err}")
            registry[str(name)] = {"emitted": emitted, "prefix": prefix,
                                   "data": entry["data"], "datalength": entry["datalength"]}
        elif "image" in entry:                           # source — may need Pillow
            self._bake_into(registry, name, entry["image"], prefix,
                            bool(entry.get("printer", False)))
        else:
            raise ValueError(
                f"icon catalog entry {name!r} has neither 'data' nor 'image'"
            )

    @classmethod
    def from_dict(cls, d: dict) -> "IconCatalog":
        """Build a catalog from a config-dict (compiled or ``image`` entries)."""
        cat = cls()
        for section in ("custom_entity_icons", "custom_attribute_icons"):
            for entry in (d.get(section) or []):
                cat._load_entry(section, entry)
        return cat

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "IconCatalog":
        """Load a single catalog/config file (YAML or JSON)."""
        return cls.from_dict(_load_catalog_doc(path))

    @classmethod
    def from_files(cls, paths: Iterable[Union[str, Path]]) -> "IconCatalog":
        """Load and merge several catalogs left-to-right (later wins by name)."""
        cat = cls()
        for p in paths:
            other = cls.from_file(p)
            cat._entity.update(other._entity)
            cat._attribute.update(other._attribute)
        return cat

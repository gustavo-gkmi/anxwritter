"""Streaming / compact serialization tests.

Covers the two-path serializer:
- stream-off: ``to_xml()`` → pretty (indented), unchanged, golden-digest pinned.
- stream-on:  compact (no indent, newlines kept), per-item emit-and-discard.

Every check is an exact **byte** comparison anchored to the pretty golden output
(no semantic-tolerance against ANB). ``compact`` and ``pretty`` differ only by
leading indentation, which makes ``strip_indent(pretty) == compact`` exact.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Callable, Dict

import pytest

from anxwritter import ANXChart
from tests.fixtures.equivalence_specs import ALL_SPECS, build_via_from_dict

_REPO_ROOT = Path(__file__).parent.parent


def strip_indent(xml: str) -> str:
    """Drop leading indentation from every line, preserving newlines and content.

    Mirrors compact serialization (indent table = ``_INDENT_NONE``). Safe for ANX
    because every emitted line starts with indentation followed by ``<`` (or is the
    declaration/comment with no indent); ANX emits no mixed content (text on its own
    indented line), the only case where a blanket ``lstrip(' ')`` could over-strip.
    """
    return "\n".join(line.lstrip(" ") for line in xml.split("\n"))


# ── Chart fixtures: equivalence specs + bundled examples (mirrors golden test) ──

def _example_builders() -> Dict[str, Callable[[], ANXChart]]:
    sys.path.insert(0, str(_REPO_ROOT))
    try:
        inv = importlib.import_module("examples.investigation_chart")
        ls = importlib.import_module("examples.link_styling")
        ds = importlib.import_module("examples.display_synthesizers_example")
    finally:
        sys.path.pop(0)
    builders: Dict[str, Callable[[], ANXChart]] = {
        "example:investigation_chart": inv.build,
        "example:link_styling": ls.build,
    }
    for name, builder in ds.BUILDERS.items():
        builders[f"example:display_synth:{name}"] = builder
    return builders


def _all_builders() -> Dict[str, Callable[[], ANXChart]]:
    """name -> zero-arg builder that returns a FRESH chart (so each call is
    independent, avoiding any cross-build state)."""
    builders: Dict[str, Callable[[], ANXChart]] = {
        f"spec:{name}": (lambda s=spec: build_via_from_dict(s))
        for name, spec in ALL_SPECS.items()
    }
    builders.update(_example_builders())
    return builders


_BUILDERS = _all_builders()


# ── Phase 1: compact is pretty minus indentation ──────────────────────────────

@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_compact_is_pretty_minus_indent(name: str) -> None:
    """``strip_indent(pretty) == compact`` — indentation is the only serializer
    difference between the two paths (property of ``_walk``'s ``ind`` knob)."""
    build = _BUILDERS[name]
    pretty, _ = build()._build_xml(compact=False)
    compact, _ = build()._build_xml(compact=True)
    assert strip_indent(pretty) == compact


def test_pretty_unchanged_has_indentation() -> None:
    """Guardrail: the pretty path still indents (so the test above isn't vacuously
    comparing two identical compact strings)."""
    pretty, _ = build_via_from_dict(ALL_SPECS["FULL"])._build_xml(compact=False)
    assert "\n  <" in pretty  # at least one indented child line


def test_compact_has_no_indentation() -> None:
    """Compact output has newlines but no leading indentation."""
    compact, _ = build_via_from_dict(ALL_SPECS["FULL"])._build_xml(compact=True)
    assert "\n" in compact
    assert "\n  <" not in compact  # no indented lines
    assert "\n<" in compact  # lines still newline-separated


# ── Phase 3: streaming parity — both modes byte-equal vs the pretty golden ──────

@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_stream_pretty_equals_to_xml(name: str) -> None:
    """``''.join(iter_xml(compact=False)) == to_xml()`` — the streaming restructure
    (per-item emit-and-discard, manual ChartItemCollection bracketing) reproduces the
    exact pretty golden bytes. This is the strongest correctness anchor: it ties the
    stream path directly to the ANB-accepted output, indentation included."""
    assert "".join(_BUILDERS[name]().iter_xml(compact=False)) == _BUILDERS[name]().to_xml()


@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_stream_compact_equals_strip_indent(name: str) -> None:
    """``''.join(iter_xml(compact=True)) == strip_indent(to_xml())`` — the compact
    stream equals golden-minus-indentation, byte for byte."""
    compact = "".join(_BUILDERS[name]().iter_xml(compact=True))
    assert compact == strip_indent(_BUILDERS[name]().to_xml())


def test_stream_empty_chart() -> None:
    """Empty chart: no items → self-closing <ChartItemCollection/>, identical to
    the non-stream path (regression guard for the streamed-collection special case)."""
    pretty = ANXChart().to_xml()
    assert "".join(ANXChart().iter_xml(compact=False)) == pretty
    assert "<ChartItemCollection/>" in pretty


def test_stream_entities_only_no_links() -> None:
    """Items present but no links (a header-light / footer-light shape)."""
    spec = ALL_SPECS["ENTITIES_ONLY"]
    assert "".join(build_via_from_dict(spec).iter_xml(compact=False)) == build_via_from_dict(spec).to_xml()


def test_iter_xml_yields_multiple_chunks() -> None:
    """A chart with several items yields more than one chunk (proves it actually
    streams rather than buffering one blob)."""
    chunks = list(build_via_from_dict(ALL_SPECS["FULL"]).iter_xml(compact=True))
    assert len(chunks) > 1


def test_iter_xml_validates_up_front() -> None:
    """iter_xml raises before yielding when the chart is invalid (fail fast)."""
    from anxwritter.errors import ANXValidationError

    bad = ANXChart()
    bad.add_link(from_id="ghost", to_id="phantom", type="Call")  # ends don't exist
    with pytest.raises(ANXValidationError):
        bad.iter_xml(compact=True)  # raises on call, not on first next()


# ── Phase 4: byte streaming + memory ───────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(ALL_SPECS))
def test_iter_anx_bytes_matches_to_xml_utf16(name: str) -> None:
    """``b''.join(iter_anx_bytes(compact=False))`` equals ``to_xml().encode('utf-16')``
    — BOM once + UTF-16 LE, the bytes ANB expects on disk."""
    spec = ALL_SPECS[name]
    streamed = b"".join(build_via_from_dict(spec).iter_anx_bytes(compact=False))
    direct = build_via_from_dict(spec).to_xml().encode("utf-16")
    assert streamed == direct
    assert streamed[:2] == b"\xff\xfe"  # single leading BOM


def test_to_anx_stream_matches_plain(tmp_path) -> None:
    """``to_anx(stream=True)`` writes byte-identical output to the buffered path
    (compare at the same indentation so only the stream/buffered axis varies)."""
    spec = ALL_SPECS["FULL"]
    plain = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "plain.anx"), stream=False, compact=False))
    streamed = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "stream.anx"), stream=True, compact=False))
    assert plain.read_bytes() == streamed.read_bytes()


def test_to_anx_default_is_stream_compact(tmp_path) -> None:
    """The default ``to_anx()`` is stream + compact: byte-identical to the explicit
    streamed-compact write, and not the pretty one."""
    spec = ALL_SPECS["FULL"]
    default = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "d.anx")))
    explicit_compact = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "e.anx"), stream=True, compact=True))
    pretty = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "p.anx"), compact=False))
    assert default.read_bytes() == explicit_compact.read_bytes()
    assert default.stat().st_size < pretty.stat().st_size


def test_to_anx_compact_smaller(tmp_path) -> None:
    """Compact output is smaller than pretty (indentation dropped)."""
    spec = ALL_SPECS["FULL"]
    pretty = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "p.anx"), compact=False))
    compact = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "c.anx"), compact=True))
    assert compact.stat().st_size < pretty.stat().st_size


def test_to_anx_atomic_no_partial_on_dir_only(tmp_path) -> None:
    """Atomic write leaves no stray temp files in the destination directory."""
    spec = ALL_SPECS["FULL"]
    out = Path(build_via_from_dict(spec).to_anx(str(tmp_path / "atomic.anx")))
    assert out.is_file()
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "atomic.anx"]
    assert leftovers == [], f"unexpected leftover files: {leftovers}"


@pytest.mark.perf
def test_streaming_lowers_peak_memory() -> None:
    """Streaming a large chart peaks materially below building it whole.

    Structural: the streaming path never holds the full ChartItem ET tree nor the
    full output string (one <ChartItem> at a time), so peak drops to ~the resolved
    set. Measured ~0.47× at 3k/4k; threshold 0.70 leaves generous headroom.
    """
    import tracemalloc

    def big() -> ANXChart:
        c = ANXChart(settings={"extra_cfg": {"arrange": "grid"}})
        n = 3000
        for i in range(n):
            c.add_icon(id=f"E{i}", type="Person", attributes={"idx": i, "name": f"P{i}"})
        for j in range(4000):
            a = j % n
            b = (a + 1 + (j % (n - 1))) % n
            c.add_link(from_id=f"E{a}", to_id=f"E{b}", type="Call", attributes={"dur": j})
        return c

    tracemalloc.start()
    _ = big().to_xml()
    _, peak_off = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    total = 0
    for chunk in big().iter_xml(compact=True):
        total += len(chunk)
    _, peak_on = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert total > 0
    assert peak_on < 0.70 * peak_off, (
        f"streaming peak {peak_on/1e6:.1f}MB not < 0.70 * stream-off {peak_off/1e6:.1f}MB"
    )


def test_no_mixed_content_emitted() -> None:
    """Guards the strip_indent helper: ANX must not emit mixed content (text on its
    own indented line), the only case a blanket per-line lstrip could over-strip."""
    import xml.etree.ElementTree as ET

    for name in sorted(_BUILDERS):
        xml = _BUILDERS[name]().to_xml()
        root = ET.fromstring(xml)
        for el in root.iter():
            has_children = len(el) > 0
            has_text = el.text is not None and el.text.strip() != ""
            assert not (has_children and has_text), (
                f"{name}: mixed content in <{el.tag}> breaks strip_indent assumptions"
            )

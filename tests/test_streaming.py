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


# ── Fused resolve→emit (idea #3) ──────────────────────────────────────────────
# Links resolve→emit→discard one at a time on the streaming path when the chart
# is fusable (no link styling, no display synthesizer targeting links), so the
# link set never materializes. Output stays byte-identical to the eager path.

def _fusion_chart(*, styling=False, n=40, links=120):
    from anxwritter import Card, GradeCollection, StylingCfg
    c = ANXChart(settings={"extra_cfg": {
        "arrange": "grid", "link_match_entity_color": True, "link_arc_offset": 15,
    }})
    c.grades_one = GradeCollection(items=["A", "B", "C"])
    for i in range(n):
        c.add_icon(id=f"E{i}", type="Person", color="Blue", attributes={"k": i})
    for j in range(links):
        a, b = j % n, (j + 1 + (j % (n - 1))) % n
        kw = dict(from_id=f"E{a}", to_id=f"E{b}", type="Call", attributes={"dur": float(j)})
        if j % 7 == 0:
            kw["grade_one"] = "B"
        if j % 5 == 0:
            kw["date"], kw["time"] = "2024-03-04", "10:00:00"
        if j % 11 == 0:
            kw["cards"] = [Card(summary="s", date="2024-01-01", time="09:00:00")]
        if j % 13 == 0:
            kw["multiplicity"] = "single"
        c.add_link(**kw)
    if styling:
        c.settings.extra_cfg.styling = StylingCfg(
            links={"intensity": {"attribute": "dur", "width": {"range": [1, 5]}}}
        )
    return c


@pytest.mark.parametrize("compact", [True, False])
def test_fused_stream_equals_eager_bytes(compact: bool) -> None:
    """Fused streaming output is byte-identical to the eager (non-stream) path,
    across the per-link features that run lazily (match-color, offset, grades +
    defaults, dates, cards, connections)."""
    eager = _fusion_chart().to_xml(compact=compact)
    fused = "".join(_fusion_chart().iter_xml(compact=compact))
    assert fused == eager


def test_fusion_gate_engages_and_falls_back() -> None:
    """The gate fuses a fusable streaming chart and falls back otherwise."""
    b, *_ = _fusion_chart()._assemble_build(stream=True)
    assert b._lazy_link_iter is not None, "fusable chart should fuse"

    b2, *_ = _fusion_chart(styling=True)._assemble_build(stream=True)
    assert b2._lazy_link_iter is None, "link styling must disable fusion"

    b3, *_ = _fusion_chart()._assemble_build(stream=False)
    assert b3._lazy_link_iter is None, "non-stream path never fuses"


def test_fused_styling_chart_still_byte_parity() -> None:
    """A non-fusable (styling) chart still streams byte-identically (via fallback)."""
    eager = _fusion_chart(styling=True).to_xml(compact=True)
    fused = "".join(_fusion_chart(styling=True).iter_xml(compact=True))
    assert fused == eager


@pytest.mark.perf
def test_fused_lowers_peak_memory_on_link_heavy() -> None:
    """Fusion drops streaming peak well below the non-fused streaming floor on a
    link-heavy chart (links never materialize). Measured ~0.5×; threshold 0.75."""
    import tracemalloc

    def big() -> ANXChart:
        c = ANXChart(settings={"extra_cfg": {"arrange": "grid"}})
        n = 4000
        for i in range(n):
            c.add_icon(id=f"E{i}", type="Person", attributes={"idx": i, "name": f"P{i}"})
        for j in range(20000):  # 5× links — link-heavy
            a, b = j % n, (j + 1 + (j % (n - 1))) % n
            c.add_link(from_id=f"E{a}", to_id=f"E{b}", type="Call", attributes={"dur": float(j)})
        return c

    def drain(chart) -> None:
        for _ in chart.iter_xml(compact=True):
            pass

    # Non-fused: force the gate off so only fusion differs.
    c_off = big()
    c_off._display_targets_links = lambda: True
    tracemalloc.start()
    drain(c_off)
    _, peak_off = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    c_on = big()
    tracemalloc.start()
    drain(c_on)
    _, peak_on = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak_on < 0.75 * peak_off, (
        f"fused peak {peak_on/1e6:.1f}MB not < 0.75 * non-fused {peak_off/1e6:.1f}MB"
    )


# ── Entity direct-string fast path (extends #2 to simple Icon entities) ───────

def test_entity_fast_path_engages_and_falls_back() -> None:
    """The simple-Icon fast path returns a string for a plain Icon and None
    (→ ET fallback) for other representations / icon overrides / cards."""
    from anxwritter import ANXChart, Box, Card, Frame
    from anxwritter.builder import ANXBuilder
    from anxwritter.resolved import ResolvedEntity

    b = ANXBuilder()
    # Resolve a simple icon and a box through the real path.
    from anxwritter import Icon
    re_icon = b.resolve_entity(Icon(id="A", type="Person", color="Blue"))
    re_box = b.resolve_entity(Box(id="B", type="Loc", width=120))
    re_override = b.resolve_entity(Icon(id="C", type="Person", icon="witness"))
    re_card = b.resolve_entity(Icon(id="D", type="Person",
                                    cards=[Card(summary="s", date="2024-01-01", time="09:00:00")]))
    ind = tuple("  " * i for i in range(20))
    assert b._emit_entity_str(re_icon, 2, ind) is not None, "plain Icon should use fast path"
    assert b._emit_entity_str(re_box, 2, ind) is None, "Box must fall back"
    assert b._emit_entity_str(re_override, 2, ind) is None, "icon override must fall back"
    assert b._emit_entity_str(re_card, 2, ind) is None, "cards must fall back"


@pytest.mark.parametrize("compact", [True, False])
def test_entity_fast_path_all_reps_byte_parity(compact: bool) -> None:
    """Streaming (fast Icons + ET fallback for every other shape) stays byte-equal
    to the eager path across all representation types and per-entity features."""
    from anxwritter import ANXChart, Card, TimeZone, Font, Frame

    def build():
        c = ANXChart(settings={"extra_cfg": {"arrange": "grid", "entity_auto_color": True}})
        c.add_icon(id="i1", type="Person", color="Blue", attributes={"k": 1})  # fast
        c.add_icon(id="i2", type="Ghost")                                       # fast
        c.add_icon(id="i3", type="Person", icon="witness")                      # fallback
        c.add_icon(id="i4", type="Person", frame=Frame(visible=True))           # fallback
        c.add_icon(id="i5", type="Person", label_font=Font(bold=True))          # fallback
        c.add_icon(id="i6", type="Person",
                   cards=[Card(summary="s", date="2024-01-01", time="09:00:00")])  # fallback
        c.add_icon(id="i7", type="Person", timezone=TimeZone(id=1, name="UTC"),
                   date="2024-01-01", time="09:00:00")                          # fallback
        c.add_box(id="b1", type="Loc", width=120)
        c.add_circle(id="c1", type="Ev", diameter=80)
        c.add_text_block(id="t1", type="Note", label="hi")
        c.add_label(id="l1", type="Lbl", label="cap")
        c.add_event_frame(id="ef1", type="Ev")
        c.add_theme_line(id="tl1", type="Theme")
        for j in range(8):
            c.add_link(from_id="i1", to_id="i2", type="Call", attributes={"d": j})
        return c

    assert "".join(build().iter_xml(compact=compact)) == build().to_xml(compact=compact)

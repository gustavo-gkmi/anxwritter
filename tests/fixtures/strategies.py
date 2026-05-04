"""Hypothesis strategies for generating valid anxwritter chart specs.

Used by ``tests/test_properties.py`` to do random-spec smoke testing.

Design notes
------------
- Specs are generated in the ``from_dict`` shape so they exercise the
  parser end-to-end.
- Entity IDs are unique per chart (enforced by ``st.lists(unique=True)``).
- Links reference only IDs present in the entity pool, so generated
  specs always validate cleanly (no MISSING_ENTITY errors).
- Attribute values are restricted to one type per attribute name per
  chart (enforced by a composite strategy) to avoid the TYPE_CONFLICT
  validation error.
- Labels and descriptions may contain unicode — this is intentional,
  because catching unicode round-trip bugs is half the point.
"""

from __future__ import annotations

from typing import Any, Dict, List

from hypothesis import strategies as st

from anxwritter.enums import Color


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

# ASCII identifiers — safe in XML element values without escaping concerns.
entity_id_strategy = st.text(
    alphabet=st.characters(
        min_codepoint=ord("A"),
        max_codepoint=ord("z"),
        blacklist_characters="[]\\^_`",  # keep it within [A-Za-z]
    ),
    min_size=1,
    max_size=10,
)

# Entity type name — we use a small fixed pool so from_dict doesn't have to
# handle every arbitrary unicode string. Types are referenced for matching,
# not parsed.
entity_type_strategy = st.sampled_from(
    ["Person", "Location", "Vehicle", "Event", "Document", "Custom"]
)

# Labels can be richer since they're free-text display strings.
# NOTE: We currently restrict labels to printable characters (>= 0x20 plus
# \t/\n/\r) because the library does not escape/strip XML 1.0 forbidden
# control characters (0x00-0x1F except \t\n\r) — feeding one through
# produces unparseable XML. This is a known library gap surfaced by
# property-based testing; see plans/ for follow-up.
label_strategy = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        blacklist_categories=("Cs",),  # no surrogate halves
    ),
    min_size=0,
    max_size=30,
)

color_strategy = st.sampled_from([m for m in Color])


# ---------------------------------------------------------------------------
# Attribute dict (constrained to one Python type per key for the whole chart)
# ---------------------------------------------------------------------------

# Each call to attributes_dict_strategy returns a dict whose keys are drawn
# from a small fixed pool so all entities in a chart see the same type per
# key — prevents TYPE_CONFLICT validation errors.
_ATTR_KEYS_BY_TYPE = {
    "str": ["note", "tag", "ref"],
    "int": ["count", "score", "age"],
    "float": ["ratio", "balance"],
    "bool": ["flag", "active"],
}


def _single_typed_attr() -> st.SearchStrategy[Dict[str, Any]]:
    return st.one_of(
        st.dictionaries(
            keys=st.sampled_from(_ATTR_KEYS_BY_TYPE["str"]),
            values=st.text(
                alphabet=st.characters(
                    min_codepoint=0x20,
                    blacklist_categories=("Cs",),
                ),
                max_size=15,
            ),
            max_size=2,
        ),
        st.dictionaries(
            keys=st.sampled_from(_ATTR_KEYS_BY_TYPE["int"]),
            values=st.integers(min_value=0, max_value=1000),
            max_size=2,
        ),
        st.dictionaries(
            keys=st.sampled_from(_ATTR_KEYS_BY_TYPE["float"]),
            values=st.floats(
                min_value=0.0,
                max_value=1000.0,
                allow_nan=False,
                allow_infinity=False,
                width=32,
            ),
            max_size=2,
        ),
        st.dictionaries(
            keys=st.sampled_from(_ATTR_KEYS_BY_TYPE["bool"]),
            values=st.booleans(),
            max_size=2,
        ),
    )


# ---------------------------------------------------------------------------
# Entity dict — produces a minimal icon spec
# ---------------------------------------------------------------------------

@st.composite
def icon_dict_for_id(draw, entity_id: str):
    """Build an icon spec for a specific fixed id (no sampling)."""
    d = {
        "id": entity_id,
        "type": draw(entity_type_strategy),
    }
    if draw(st.booleans()):
        d["label"] = draw(label_strategy)
    if draw(st.booleans()):
        d["color"] = draw(color_strategy).value
    if draw(st.booleans()):
        d["description"] = draw(label_strategy)
    return d


@st.composite
def link_dict_strategy(draw, id_pool: List[str]):
    """A link with from_id/to_id drawn from the provided entity pool.

    Skips self-loops because anxwritter rejects them with SELF_LOOP.
    """
    from_id = draw(st.sampled_from(id_pool))
    to_id = draw(st.sampled_from([i for i in id_pool if i != from_id]))
    d = {
        "from_id": from_id,
        "to_id": to_id,
        "type": draw(entity_type_strategy),
    }
    if draw(st.booleans()):
        d["label"] = draw(label_strategy)
    if draw(st.booleans()):
        d["arrow"] = draw(st.sampled_from(["head", "tail", "both"]))
    return d


# ---------------------------------------------------------------------------
# Full chart spec
# ---------------------------------------------------------------------------

@st.composite
def chart_spec_strategy(draw):
    """Compose a full valid chart spec.

    Generates 2-8 unique entity IDs, then generates 0-10 links that only
    reference those IDs. Result is always internally consistent.
    """
    id_pool = draw(
        st.lists(
            entity_id_strategy,
            min_size=2,
            max_size=8,
            unique=True,
        )
    )

    # One icon per id — guarantees every generated link id resolves.
    icons = [draw(icon_dict_for_id(entity_id=eid)) for eid in id_pool]

    n_links = draw(st.integers(min_value=0, max_value=10))
    links = [draw(link_dict_strategy(id_pool=id_pool)) for _ in range(n_links)]

    # All entities in the chart share one typed attribute dict so type
    # inference is consistent across entities.
    shared_attrs = draw(_single_typed_attr())
    if shared_attrs and draw(st.booleans()):
        for icon in icons:
            icon["attributes"] = dict(shared_attrs)

    return {
        "entities": {"icons": icons},
        "links": links,
    }


# ---------------------------------------------------------------------------
# Settings-only spec (for settings round-trip properties)
# ---------------------------------------------------------------------------

@st.composite
def settings_dict_strategy(draw):
    """Generate a partial settings dict exercising several groups."""
    out: Dict[str, Any] = {}
    if draw(st.booleans()):
        out["chart"] = {
            "bg_color": draw(st.integers(min_value=0, max_value=0xFFFFFF)),
        }
    if draw(st.booleans()):
        out["extra_cfg"] = {
            "entity_auto_color": draw(st.booleans()),
            "arrange": draw(st.sampled_from(["circle", "grid", "random"])),
        }
    if draw(st.booleans()):
        out["grid"] = {
            "snap": draw(st.booleans()),
            "visible": draw(st.booleans()),
        }
    if draw(st.booleans()):
        out["view"] = {"time_bar": draw(st.booleans())}
    return out

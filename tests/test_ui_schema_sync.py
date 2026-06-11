"""Verify ``ui/schema.js`` stays in sync with the library.

This test guards the hand-curated UI config-builder schema against drift.
It runs two checks:

1. **Structural sync** — every enum and dataclass referenced by the schema
   has matching value/field-name sets in the library.
2. **Round-trip via ``apply_config`` + ``validate``** — a sample config is
   generated from the schema using defaults and fed through the real
   ``ANXChart.apply_config`` + ``validate`` code paths. Any structural
   error the library raises here is a schema bug.

If this test fails:

- Open ``ui/schema.js``. The file is ``window.SCHEMA = { ... };`` — edit
  the JSON object literal between the prefix and the trailing semicolon.
- Find the section / dataclass / enum the test names.
- Add or remove the listed field names / enum values to match the library.
- Bump ``_meta.anxwritterVersion`` to the current version.
- Commit.

Generating the schema from the dataclasses is intentionally NOT done —
the schema also carries UI-only metadata (field type, select options,
display order) that codegen would clobber.
"""
from __future__ import annotations

import dataclasses
import inspect
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest

import anxwritter
from anxwritter import ANXChart


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "ui" / "schema.js"

# schema.js is a one-line wrapper around an otherwise pure-JSON object literal:
#     window.SCHEMA = { ... };
# Loading it as a <script> tag (instead of fetching schema.json) lets the page
# work from file:// too, where fetch() of local files is blocked. The test
# strips the wrapper and json.loads the body.
_SCHEMA_PREFIX = "window.SCHEMA = "
_SCHEMA_SUFFIX = ";"


# Per-dataclass fields the UI deliberately does not expose. Internal routing
# fields, cards (entity-instance state, not config), etc.
EXCLUDED_FIELDS: Dict[str, Set[str]] = {
    # The UI builds *config*; entity-level cards/timezone/etc. are data.
    # No entity dataclasses are exposed in the config UI so they're absent
    # from the schema entirely — no exclusions needed for them.
}


@pytest.fixture(scope="module")
def schema() -> dict:
    text = SCHEMA_PATH.read_text(encoding="utf-8").strip()
    if not text.startswith(_SCHEMA_PREFIX) or not text.endswith(_SCHEMA_SUFFIX):
        raise AssertionError(
            f"{SCHEMA_PATH.name} must wrap the schema as "
            f"`{_SCHEMA_PREFIX}{{ ... }}{_SCHEMA_SUFFIX}` so the page can load "
            f"it via <script> under file://."
        )
    body = text[len(_SCHEMA_PREFIX):-len(_SCHEMA_SUFFIX)]
    return json.loads(body)


# ── Helpers ─────────────────────────────────────────────────────────────

def _enum_class(name: str) -> type:
    """Resolve an enum class name to the class object via anxwritter's
    public surface."""
    cls = getattr(anxwritter, name, None)
    if cls is None or not (inspect.isclass(cls) and issubclass(cls, Enum)):
        raise AssertionError(
            f"schema references enum {name!r} which is not exported from "
            f"`anxwritter` as an Enum subclass."
        )
    return cls


def _dataclass_class(name: str) -> type:
    """Resolve a dataclass name to the class object via anxwritter's
    public surface."""
    cls = getattr(anxwritter, name, None)
    if cls is None or not dataclasses.is_dataclass(cls):
        raise AssertionError(
            f"schema references dataclass {name!r} which is not exported "
            f"from `anxwritter` as a dataclass."
        )
    return cls


# ── Check 1: structural sync ────────────────────────────────────────────

def test_every_schema_enum_matches_library(schema):
    """For each enum named in ``schema['enums']``, set-equal the listed
    values with the library's enum member values. Catches both directions:
    schema lists a value the library no longer has, OR library has a
    member the schema is missing."""
    mismatches: List[str] = []

    for enum_name, schema_values in schema["enums"].items():
        cls = _enum_class(enum_name)
        lib_values = {m.value for m in cls}
        sch_values = set(schema_values)

        only_in_schema = sch_values - lib_values
        only_in_lib = lib_values - sch_values
        if only_in_schema or only_in_lib:
            mismatches.append(
                f"  {enum_name}:"
                + (f"\n    only in schema: {sorted(only_in_schema)}" if only_in_schema else "")
                + (f"\n    only in library: {sorted(only_in_lib)}" if only_in_lib else "")
            )

    assert not mismatches, (
        "ui/schema.js enums are out of sync with anxwritter.enums:\n"
        + "\n".join(mismatches)
        + "\n\nFix: edit ui/schema.js 'enums' to match the library."
    )


def test_every_schema_dataclass_matches_library(schema):
    """For each definition named with ``dataclass: X``, set-equal the
    schema's declared field names against ``fields(X)``."""
    mismatches: List[str] = []

    for def_name, body in schema["definitions"].items():
        dc_name = body.get("dataclass")
        if dc_name is None:
            continue  # not a dataclass-backed definition

        cls = _dataclass_class(dc_name)
        lib_names = {f.name for f in dataclasses.fields(cls)}
        lib_names -= EXCLUDED_FIELDS.get(dc_name, set())

        sch_names = {f["name"] for f in body.get("fields", [])}

        only_in_schema = sch_names - lib_names
        only_in_lib = lib_names - sch_names
        if only_in_schema or only_in_lib:
            mismatches.append(
                f"  {def_name} ({dc_name}):"
                + (f"\n    only in schema: {sorted(only_in_schema)}" if only_in_schema else "")
                + (f"\n    only in library: {sorted(only_in_lib)}" if only_in_lib else "")
            )

    assert not mismatches, (
        "ui/schema.js dataclass field sets are out of sync:\n"
        + "\n".join(mismatches)
        + "\n\nFix: edit the listed definition's 'fields' in ui/schema.js,"
        " or add the field to EXCLUDED_FIELDS in this test if it's"
        " intentionally hidden from the UI."
    )


def test_all_enum_classes_referenced_by_schema(schema):
    """Every enum exported from ``anxwritter`` must appear in the schema's
    ``enums`` block — flags the opposite-direction drift (a new enum was
    added and the UI never learned about it). Excludes enums that are not
    user-facing config values (e.g. ErrorType)."""
    NON_CONFIG_ENUMS = {"ErrorType"}

    library_enums = set()
    for attr in dir(anxwritter):
        obj = getattr(anxwritter, attr)
        if inspect.isclass(obj) and issubclass(obj, Enum) and obj is not Enum:
            library_enums.add(obj.__name__)

    missing = library_enums - set(schema["enums"].keys()) - NON_CONFIG_ENUMS
    assert not missing, (
        f"anxwritter exports enum classes not in ui/schema.js 'enums': "
        f"{sorted(missing)}.\n"
        f"Either add them to the schema, or to NON_CONFIG_ENUMS in this test."
    )


# ── Check 2: round-trip via apply_config + validate ─────────────────────

# Fields the library treats as advanced free-text / passthrough we shouldn't
# stress with a dummy value at sample-generation time. They're optional in
# practice and emitting "sample" would either look weird or trip validators.
_SAMPLE_SKIP_FIELDS: Set[str] = {
    "semantic_type",      # raw GUID passthrough or registered name
    "icon_file",          # ANB icon key — arbitrary placeholder fine, but
                          # AC pre-registers conflict otherwise
    # Type-dependent — populating blindly produces invalid combinations.
    "merge_behaviour",
    "paste_behaviour",
    # CategoricalStyleCfg.strength references a registered Strength. Easier
    # to wire correctly via overrides than guess at sample time.
    "strength",
}


def _first_enum_value(enum_name: str, schema: dict) -> str:
    return schema["enums"][enum_name][0]


def _sample_for_field(field: dict, schema: dict) -> Any:
    """Produce a sensible default for one schema field."""
    name = field["name"]
    if name in _SAMPLE_SKIP_FIELDS:
        return None

    if "ref" in field:
        return _sample_for_dataclass(field["ref"], schema)
    if "list_of" in field:
        return [_sample_for_dataclass(field["list_of"], schema)]
    if field.get("type") == "dict_of":
        return {"sample_key": _sample_for_dataclass(field["value_ref"], schema)}
    if "enum" in field:
        return _first_enum_value(field["enum"], schema)

    ftype = field.get("type")
    if ftype == "text":
        return f"sample_{name}"
    if ftype == "number":
        return 1
    if ftype == "bool":
        return False
    if ftype == "color":
        return "blue"
    if ftype == "select":
        opts = field.get("options") or []
        return opts[0] if opts else None
    if ftype == "list-of-text":
        return [f"sample_{name}"]
    if ftype == "list-of-number":
        return [1, 10]
    if ftype == "list-of-color":
        return ["blue", "red"]
    if ftype == "geo_data":
        return {"sample_key": [0.0, 0.0]}
    if ftype == "any":
        return None  # leave unset — library defaults apply
    return None


def _sample_for_dataclass(def_name: str, schema: dict) -> dict:
    body = schema["definitions"][def_name]
    out: dict = {}
    for field in body.get("fields", []):
        val = _sample_for_field(field, schema)
        if val is not None:
            out[field["name"]] = val
    return out


def _sample_for_section(section_name: str, schema: dict) -> Any:
    sec = schema["sections"][section_name]
    if "ref" in sec:
        return _sample_for_dataclass(sec["ref"], schema)
    if "list_of" in sec:
        return [_sample_for_dataclass(sec["list_of"], schema)]
    if sec.get("type") == "list-of-text":
        return [f"sample_{section_name}_item"]
    return None


# Overrides applied to the generated sample to satisfy interdependencies
# the round-trip cares about. Keep this list short — only what the library
# actually enforces. Each entry: ``(dotted_path, new_value)``.
def _apply_overrides(sample: dict) -> dict:
    # Grade collections: default must reference a member of items.
    for key in ("grades_one", "grades_two", "grades_three"):
        gc = sample.get(key)
        if isinstance(gc, dict) and gc.get("items"):
            gc["default"] = gc["items"][0]

    # StrengthCollection: default must reference a strength name in items.
    strengths = sample.get("strengths")
    if isinstance(strengths, dict) and strengths.get("items"):
        first = strengths["items"][0]
        if isinstance(first, dict) and first.get("name"):
            strengths["default"] = first["name"]

    # Palettes reference entity_types/link_types/attribute_classes by name.
    palettes = sample.get("palettes") or []
    et = sample.get("entity_types") or []
    lt = sample.get("link_types") or []
    ac = sample.get("attribute_classes") or []
    if palettes:
        p = palettes[0]
        p["entity_types"] = [et[0]["name"]] if et else []
        p["link_types"] = [lt[0]["name"]] if lt else []
        p["attribute_classes"] = [ac[0]["name"]] if ac else []
        # attribute_entries.name must reference an existing AC.
        if ac and p.get("attribute_entries"):
            for entry in p["attribute_entries"]:
                if isinstance(entry, dict):
                    entry["name"] = ac[0]["name"]

    # DisplayAttribute / DisplayLabel sources reference AC names.
    extra = sample.get("settings", {}).get("extra_cfg", {})
    if ac:
        ac_name = ac[0]["name"]
        for entry in (extra.get("display_attribute") or []):
            for src in (entry.get("sources") or []):
                if isinstance(src, dict):
                    src["attribute"] = ac_name
        for entry in (extra.get("display_label") or []):
            for src in (entry.get("sources") or []):
                if isinstance(src, dict):
                    src["attribute"] = ac_name

    # DisplayAttribute / DisplayLabel `.type` filter must reference a
    # registered entity/link type name (or be omitted). The sample
    # generator emits "sample_type" which would fail the new validator;
    # drop it so the round-trip has no type filter (semantically: apply to
    # all matching items).
    for entry in (extra.get("display_attribute") or []):
        if isinstance(entry, dict):
            entry.pop("type", None)
    for entry in (extra.get("display_label") or []):
        if isinstance(entry, dict):
            entry.pop("type", None)

        # DisplayAttribute.attribute_class must NOT carry name/type (it's a
        # styling template; the synthesized AC is auto-named/typed).
        for entry in (extra.get("display_attribute") or []):
            inner = entry.get("attribute_class")
            if isinstance(inner, dict):
                inner.pop("name", None)
                inner.pop("type", None)

    # GeoMapCfg: attribute_name must match an attribute on at least one
    # entity — but the round-trip has no entities, so the geo_map block
    # would emit a warning rather than an error. Leave it alone.

    # AC with is_user=False / user_can_add=False can't appear in a palette.
    # Force both True on every AC so palette references stay valid.
    for entry in (sample.get("attribute_classes") or []):
        if isinstance(entry, dict):
            entry["is_user"] = True
            entry["user_can_add"] = True

    # Styling sub-blocks: intensity and categorical must NOT target the
    # same attribute; intensity.legend_count must be >= 2.
    styling = (
        sample.get("settings", {})
              .get("extra_cfg", {})
              .get("styling", {})
              .get("links", {})
    )
    if isinstance(styling, dict):
        intensity = styling.get("intensity")
        categorical = styling.get("categorical")
        if isinstance(intensity, dict):
            intensity["legend_count"] = 5
            intensity["attribute"] = "sample_intensity_attr"
        if isinstance(categorical, dict):
            categorical["attribute"] = "sample_categorical_attr"

    return sample


def test_round_trip_sample_config_validates(schema):
    """Generate a complete sample config from the schema, feed it through
    ANXChart.apply_config + validate(). Any structural error the library
    raises means the schema is producing YAML the library doesn't accept."""
    sample: dict = {}
    for section_name in schema["sections"]:
        val = _sample_for_section(section_name, schema)
        if val is not None:
            sample[section_name] = val

    sample = _apply_overrides(sample)

    chart = ANXChart()
    chart.apply_config(sample)
    errors = chart.validate()

    # Filter out errors that are inherent to round-tripping a synthesized
    # config without real data (e.g. type_conflict between AC and absent
    # entity attributes don't apply — we have no data). We DO want to fail
    # on structural errors that mean the schema is wrong.
    structural_errors = [
        e for e in errors
        if e.get("type") not in {
            # No data was loaded, so any data-vs-config check that's
            # vacuously satisfied or vacuously violated is irrelevant here.
        }
    ]

    assert not structural_errors, (
        "Sample config generated from ui/schema.js failed validation. "
        "This means the schema is producing YAML that the library doesn't "
        "accept.\nErrors:\n"
        + "\n".join(f"  - {e}" for e in structural_errors)
    )

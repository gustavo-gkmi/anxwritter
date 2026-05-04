"""Canonical chart specs + per-input-form builders for equivalence tests.

Each spec is a plain dict in the ``from_dict`` shape. Each ``build_via_*``
function takes a spec and returns an ``ANXChart`` constructed via a specific
supported input form (convenience methods, generic add, from_dict, from_yaml,
Settings dataclass, name_or_obj pattern, collection reassignment, config path).

Builders MUST produce identical internal state and XML from the same spec —
that's the whole point of the equivalence test suite.

Insertion order note
--------------------
``_apply_data`` iterates ``_ENTITY_MAP`` in a fixed order: icons, boxes,
circles, theme_lines, event_frames, text_blocks, labels. All non-parser
builders below reproduce that exact order so ``_entities`` lists line up.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from anxwritter import (
    ANXChart,
    AttributeClass,
    Box,
    Card,
    ChartCfg,
    Circle,
    EntityType,
    EventFrame,
    ExtraCfg,
    Font,
    GradeCollection,
    GridCfg,
    Icon,
    Label,
    LegendCfg,
    LegendItem,
    Link,
    LinkType,
    Settings,
    Strength,
    StrengthCollection,
    TextBlock,
    ThemeLine,
)
from anxwritter.enums import DotStyle


# ---------------------------------------------------------------------------
# Canonical specs
# ---------------------------------------------------------------------------

FULL_SPEC: Dict[str, Any] = {
    "settings": {
        "chart": {"bg_color": 8421504},
        "extra_cfg": {"entity_auto_color": True, "arrange": "grid"},
        "grid": {"snap": True},
        "legend_cfg": {
            "show": True,
            "x": 100,
            "y": 50,
            "font": {"name": "Segoe UI", "bold": True},
        },
    },
    "entity_types": [
        {"name": "Person", "icon_file": "person", "color": "Blue"},
        {"name": "Location", "icon_file": "office", "color": "Red"},
    ],
    "link_types": [
        {"name": "Call", "color": 255},
        {"name": "Works At"},
    ],
    "attribute_classes": [
        {"name": "phone", "type": "Text", "prefix": "Tel: "},
        {"name": "balance", "type": "Number", "prefix": "R$ ", "decimal_places": 2},
    ],
    "strengths": {
        "items": [
            {"name": "Confirmed", "dot_style": "solid"},
            {"name": "Tentative", "dot_style": "dashed"},
        ],
    },
    "grades_one": {"items": ["Reliable", "Usually reliable", "Unreliable"]},
    "grades_two": {"items": ["Confirmed", "Probable", "Possible"]},
    "source_types": ["Witness", "Informant", "Officer"],
    "legend_items": [
        {"name": "Person", "item_type": "Icon"},
    ],
    "entities": {
        "icons": [
            {
                "id": "Alice",
                "type": "Person",
                "color": "Blue",
                "attributes": {"phone": "555-0001"},
                "cards": [
                    {
                        "summary": "Main suspect",
                        "date": "2024-01-15",
                        "time": "14:30:00",
                        "source_ref": "REP-001",
                    }
                ],
            },
            {"id": "Bob", "type": "Person", "color": "Red"},
        ],
        "boxes": [
            {"id": "HQ", "type": "Location", "width": 150, "height": 100},
        ],
        "circles": [
            {"id": "C1", "type": "Event", "diameter": 80},
        ],
        "theme_lines": [
            {"id": "TL1", "type": "ThemeLine"},
        ],
        "event_frames": [
            {"id": "EF1", "type": "Event"},
        ],
        "text_blocks": [
            {"id": "TB1", "type": "Note", "label": "note text"},
        ],
        "labels": [
            {"id": "LBL1", "type": "Label", "label": "caption"},
        ],
    },
    "links": [
        {
            "from_id": "Alice",
            "to_id": "Bob",
            "type": "Call",
            "arrow": "->",
            "date": "2024-01-15",
            "attributes": {"duration": 120},
        },
    ],
}


ENTITIES_ONLY_SPEC: Dict[str, Any] = {
    "entities": {
        "icons": [
            {"id": "A", "type": "Person", "color": "Blue"},
            {"id": "B", "type": "Person"},
        ],
        "boxes": [{"id": "HQ", "type": "Location", "width": 150}],
        "circles": [{"id": "C1", "type": "Event", "diameter": 80}],
    },
    "links": [{"from_id": "A", "to_id": "B", "type": "Call", "arrow": "->"}],
}


SETTINGS_ONLY_SPEC: Dict[str, Any] = {
    "settings": {
        "chart": {"bg_color": 8421504, "rigorous": True},
        "extra_cfg": {"entity_auto_color": True, "arrange": "grid"},
        "grid": {"snap": True, "visible": True},
        "view": {"time_bar": True},
        "legend_cfg": {
            "show": True,
            "x": 100,
            "y": 50,
            "font": {"name": "Segoe UI", "bold": True, "size": 12},
        },
    },
    # need at least one entity so both paths produce non-empty charts
    "entities": {"icons": [{"id": "A", "type": "Person"}]},
}


REGISTRY_ONLY_SPEC: Dict[str, Any] = {
    "entity_types": [
        {"name": "Person", "icon_file": "person", "color": "Blue"},
    ],
    "link_types": [{"name": "Call", "color": 255}],
    "attribute_classes": [
        {"name": "phone", "type": "Text", "prefix": "Tel: "},
    ],
    "strengths": {
        "items": [{"name": "Confirmed", "dot_style": "solid"}],
    },
    "legend_items": [{"name": "Person", "item_type": "Icon"}],
    "entities": {"icons": [{"id": "A", "type": "Person"}]},
}


ALL_SPECS = {
    "FULL": FULL_SPEC,
    "ENTITIES_ONLY": ENTITIES_ONLY_SPEC,
    "SETTINGS_ONLY": SETTINGS_ONLY_SPEC,
    "REGISTRY_ONLY": REGISTRY_ONLY_SPEC,
}


# ---------------------------------------------------------------------------
# Parser builders (all funnel through from_dict)
# ---------------------------------------------------------------------------

def build_via_from_dict(spec: Dict[str, Any]) -> ANXChart:
    return ANXChart.from_dict(copy.deepcopy(spec))


def build_via_from_json(spec: Dict[str, Any]) -> ANXChart:
    return ANXChart.from_json(json.dumps(spec))


def build_via_from_yaml(spec: Dict[str, Any]) -> ANXChart:
    return ANXChart.from_yaml(yaml.safe_dump(spec, sort_keys=False))


def build_via_from_json_file(spec: Dict[str, Any], tmp_path: Path) -> ANXChart:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return ANXChart.from_json_file(str(p))


def build_via_from_yaml_file(spec: Dict[str, Any], tmp_path: Path) -> ANXChart:
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    return ANXChart.from_yaml_file(str(p))


# ---------------------------------------------------------------------------
# Python API builders
# ---------------------------------------------------------------------------

_ENTITY_ADDERS = {
    "icons": ("add_icon", Icon),
    "boxes": ("add_box", Box),
    "circles": ("add_circle", Circle),
    "theme_lines": ("add_theme_line", ThemeLine),
    "event_frames": ("add_event_frame", EventFrame),
    "text_blocks": ("add_text_block", TextBlock),
    "labels": ("add_label", Label),
}


def _make_chart_with_settings(spec: Dict[str, Any]) -> ANXChart:
    """Instantiate ANXChart with spec['settings'] (dict form)."""
    settings = spec.get("settings")
    if settings is None:
        return ANXChart()
    return ANXChart(settings=copy.deepcopy(settings))


def _apply_registries_kw(chart: ANXChart, spec: Dict[str, Any]) -> None:
    """Apply all non-entity registry sections via kwargs-style add_*."""
    for et in spec.get("entity_types", []):
        chart.add_entity_type(**et)
    for lt in spec.get("link_types", []):
        chart.add_link_type(**lt)
    for ac in spec.get("attribute_classes", []):
        chart.add_attribute_class(**ac)
    strengths = spec.get("strengths")
    if strengths:
        if strengths.get("default") is not None:
            chart.strengths.default = strengths["default"]
        for s in strengths.get("items", []):
            chart.add_strength(**s)
    for g_key in ("grades_one", "grades_two", "grades_three"):
        if g_key in spec:
            setattr(
                chart,
                g_key,
                GradeCollection(
                    default=spec[g_key].get("default"),
                    items=list(spec[g_key].get("items", [])),
                ),
            )
    if "source_types" in spec:
        chart.source_types = list(spec["source_types"])
    for li in spec.get("legend_items", []):
        chart.add_legend_item(**li)


def _apply_registries_obj(chart: ANXChart, spec: Dict[str, Any]) -> None:
    """Same as _apply_registries_kw but passes constructed dataclasses."""
    for et in spec.get("entity_types", []):
        chart.add_entity_type(EntityType(**et))
    for lt in spec.get("link_types", []):
        chart.add_link_type(LinkType(**lt))
    for ac in spec.get("attribute_classes", []):
        chart.add_attribute_class(AttributeClass(**ac))
    strengths = spec.get("strengths")
    if strengths:
        if strengths.get("default") is not None:
            chart.strengths.default = strengths["default"]
        for s in strengths.get("items", []):
            chart.add_strength(Strength(**s))
    for g_key in ("grades_one", "grades_two", "grades_three"):
        if g_key in spec:
            setattr(
                chart,
                g_key,
                GradeCollection(
                    default=spec[g_key].get("default"),
                    items=list(spec[g_key].get("items", [])),
                ),
            )
    if "source_types" in spec:
        chart.source_types = list(spec["source_types"])
    for li in spec.get("legend_items", []):
        chart.add_legend_item(LegendItem(**li))


def _norm_cards(raw_cards: List[Dict[str, Any]]) -> List[Card]:
    return [Card(**{k: v for k, v in c.items() if v is not None}) for c in raw_cards]


def _norm_entity_kwargs(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in d.items() if v is not None}
    if "cards" in out:
        out["cards"] = _norm_cards(out["cards"])
    return out


def build_via_convenience_methods(spec: Dict[str, Any]) -> ANXChart:
    """Build using add_icon(...), add_box(...), ..., add_link(...)."""
    chart = _make_chart_with_settings(spec)
    _apply_registries_kw(chart, spec)

    entities = spec.get("entities", {})
    for key, (method_name, _cls) in _ENTITY_ADDERS.items():
        method = getattr(chart, method_name)
        for d in entities.get(key, []):
            method(**_norm_entity_kwargs(d))

    for link_d in spec.get("links", []):
        chart.add_link(**{k: v for k, v in link_d.items() if v is not None})

    return chart


def build_via_generic_add(spec: Dict[str, Any]) -> ANXChart:
    """Build using chart.add(Icon(...)), chart.add(Link(...))."""
    chart = _make_chart_with_settings(spec)
    _apply_registries_obj(chart, spec)

    entities = spec.get("entities", {})
    for key, (_method_name, cls) in _ENTITY_ADDERS.items():
        for d in entities.get(key, []):
            chart.add(cls(**_norm_entity_kwargs(d)))

    for link_d in spec.get("links", []):
        chart.add(Link(**{k: v for k, v in link_d.items() if v is not None}))

    return chart


def build_via_add_all(spec: Dict[str, Any]) -> ANXChart:
    """Build using chart.add_all(iterable)."""
    chart = _make_chart_with_settings(spec)
    _apply_registries_obj(chart, spec)

    def _iter_items():
        entities = spec.get("entities", {})
        for key, (_m, cls) in _ENTITY_ADDERS.items():
            for d in entities.get(key, []):
                yield cls(**_norm_entity_kwargs(d))
        for link_d in spec.get("links", []):
            yield Link(**{k: v for k, v in link_d.items() if v is not None})

    chart.add_all(_iter_items())
    return chart


# ---------------------------------------------------------------------------
# Settings-as-dataclass builder
# ---------------------------------------------------------------------------

def build_via_settings_dataclass(spec: Dict[str, Any]) -> ANXChart:
    """Build with settings= passed as Settings(...) dataclass instead of dict.

    Uses Settings.from_dict internally to construct the dataclass (not a bypass),
    because that's the library's recommended way to build a Settings instance
    programmatically. The point of the test: a Settings instance passed to
    ``ANXChart(settings=...)`` must produce the same result as passing the
    equivalent dict — the ``__init__`` branch is what we're exercising.
    """
    s_dict = spec.get("settings")
    if s_dict is not None:
        settings_obj = Settings.from_dict(copy.deepcopy(s_dict))
        chart = ANXChart(settings=settings_obj)
    else:
        chart = ANXChart()

    _apply_registries_kw(chart, spec)

    entities = spec.get("entities", {})
    for key, (method_name, _cls) in _ENTITY_ADDERS.items():
        method = getattr(chart, method_name)
        for d in entities.get(key, []):
            method(**_norm_entity_kwargs(d))
    for link_d in spec.get("links", []):
        chart.add_link(**{k: v for k, v in link_d.items() if v is not None})
    return chart


def build_via_settings_manual_dataclass(spec: Dict[str, Any]) -> ANXChart:
    """Like build_via_settings_dataclass but hand-constructs a few Settings groups.

    This version bypasses Settings.from_dict and builds a Settings instance
    explicitly from component dataclasses for the groups it recognises, proving
    the hand-written dataclass form is also equivalent. Falls back to
    Settings.from_dict for any group we don't know how to hand-build.
    """
    s_dict = spec.get("settings", {}) or {}

    kwargs: Dict[str, Any] = {}
    if "chart" in s_dict:
        kwargs["chart"] = ChartCfg(**s_dict["chart"])
    if "extra_cfg" in s_dict:
        kwargs["extra_cfg"] = ExtraCfg(**s_dict["extra_cfg"])
    if "grid" in s_dict:
        kwargs["grid"] = GridCfg(**s_dict["grid"])
    if "legend_cfg" in s_dict:
        lc = dict(s_dict["legend_cfg"])
        if "font" in lc:
            lc["font"] = Font(**lc["font"])
        kwargs["legend_cfg"] = LegendCfg(**lc)

    # Any other groups (view, wiring, etc.) — fall back to from_dict for them
    remaining = {k: v for k, v in s_dict.items() if k not in kwargs}
    if remaining:
        partial = Settings.from_dict(remaining)
        for k, v in kwargs.items():
            setattr(partial, k, v)
        settings_obj = partial
    else:
        settings_obj = Settings(**kwargs)

    chart = ANXChart(settings=settings_obj)
    _apply_registries_kw(chart, spec)

    entities = spec.get("entities", {})
    for key, (method_name, _cls) in _ENTITY_ADDERS.items():
        method = getattr(chart, method_name)
        for d in entities.get(key, []):
            method(**_norm_entity_kwargs(d))
    for link_d in spec.get("links", []):
        chart.add_link(**{k: v for k, v in link_d.items() if v is not None})
    return chart


# ---------------------------------------------------------------------------
# Collection-reassignment builder
# ---------------------------------------------------------------------------

def build_via_collection_reassignment(spec: Dict[str, Any]) -> ANXChart:
    """Use ``chart.strengths = StrengthCollection(...)`` and ``chart.grades_X = GradeCollection(...)``
    instead of repeated ``add_strength`` / per-item construction.

    Note: wholesale-replacing ``chart.strengths`` drops the pre-populated
    ``Default`` entry. To stay equivalent with paths that preserve it (like
    ``from_dict``), we re-include ``Default`` at the front of the list.
    """
    chart = _make_chart_with_settings(spec)

    # Non-strength/grade registries: same path as before
    for et in spec.get("entity_types", []):
        chart.add_entity_type(**et)
    for lt in spec.get("link_types", []):
        chart.add_link_type(**lt)
    for ac in spec.get("attribute_classes", []):
        chart.add_attribute_class(**ac)
    for li in spec.get("legend_items", []):
        chart.add_legend_item(**li)

    strengths = spec.get("strengths")
    if strengths:
        items = [Strength(name="Default", dot_style=DotStyle.SOLID)]
        for s in strengths.get("items", []):
            items.append(Strength(**s))
        chart.strengths = StrengthCollection(
            default=strengths.get("default"),
            items=items,
        )

    for g_key in ("grades_one", "grades_two", "grades_three"):
        if g_key in spec:
            setattr(
                chart,
                g_key,
                GradeCollection(
                    default=spec[g_key].get("default"),
                    items=list(spec[g_key].get("items", [])),
                ),
            )
    if "source_types" in spec:
        chart.source_types = list(spec["source_types"])

    entities = spec.get("entities", {})
    for key, (method_name, _cls) in _ENTITY_ADDERS.items():
        method = getattr(chart, method_name)
        for d in entities.get(key, []):
            method(**_norm_entity_kwargs(d))
    for link_d in spec.get("links", []):
        chart.add_link(**{k: v for k, v in link_d.items() if v is not None})
    return chart


# ---------------------------------------------------------------------------
# Config-path builder
# ---------------------------------------------------------------------------

_CONFIG_ONLY_KEYS = {
    "settings",
    "entity_types",
    "link_types",
    "attribute_classes",
    "strengths",
    "datetime_formats",
    "semantic_entities",
    "semantic_links",
    "semantic_properties",
    "palettes",
    "legend_items",
    "grades_one",
    "grades_two",
    "grades_three",
    "source_types",
}


def _split_config_and_data(spec: Dict[str, Any]) -> tuple:
    config = {k: copy.deepcopy(v) for k, v in spec.items() if k in _CONFIG_ONLY_KEYS}
    data = {k: copy.deepcopy(v) for k, v in spec.items() if k not in _CONFIG_ONLY_KEYS}
    return config, data


def build_via_config_file_plus_data(spec: Dict[str, Any], tmp_path: Path) -> ANXChart:
    """Split spec into config + data; load config from YAML file; apply data via from_dict-style.

    Uses ANXChart(config_file=...) so the config path (apply_config) runs, then
    feeds the remaining entities/links through a second from_dict call via
    ``chart._apply_data(data)`` — matching how real users layer a shared org
    config with per-analysis data.
    """
    config, data = _split_config_and_data(spec)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    chart = ANXChart(config_file=str(cfg_path))
    chart._apply_data(data)
    return chart


def build_via_apply_config_plus_data(spec: Dict[str, Any]) -> ANXChart:
    """Same split, but uses ``chart.apply_config(dict)`` directly (no file I/O)."""
    config, data = _split_config_and_data(spec)
    chart = ANXChart()
    chart.apply_config(copy.deepcopy(config))
    chart._apply_data(data)
    return chart

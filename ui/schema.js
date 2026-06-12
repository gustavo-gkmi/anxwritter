window.SCHEMA = {
  "_meta": {
    "anxwritterVersion": "1.16.0",
    "schemaVersion": 1,
    "notes": "Hand-curated. tests/test_ui_schema_sync.py verifies sync with the library."
  },

  "enums": {
    "Representation": ["icon", "theme_line", "event_frame", "box", "circle", "text_block", "label", "ole_object"],
    "ArrowStyle": ["head", "tail", "both"],
    "AttributeType": ["text", "flag", "datetime", "number"],
    "Multiplicity": ["multiple", "single", "directed"],
    "ThemeWiring": ["keep_event", "return_theme", "next_event", "no_diversion"],
    "MergeBehaviour": ["assign", "noop", "add", "add_space", "add_line_break", "max", "min", "subtract", "subtract_swap", "or", "and", "xor"],
    "Enlargement": ["half", "single", "double", "triple", "quadruple"],
    "DotStyle": ["solid", "dashed", "dash_dot", "dash_dot_dot", "dotted"],
    "LegendItemType": ["font", "text", "icon", "attribute", "line", "link", "timezone", "icon_frame"],
    "IntensityScale": ["linear", "log", "sqrt", "power", "quantile", "threshold"],
    "ColorSpace": ["rgb", "rgb_linear", "hsl"],
    "MissingPolicy": ["fallback", "skip", "error"],
    "Color": [
      "black", "brown", "olive_green", "dark_green", "dark_teal", "dark_blue",
      "indigo", "dark_grey", "dark_red", "orange", "dark_yellow", "green",
      "teal", "blue", "blue_grey", "grey", "red", "light_orange", "lime",
      "sea_green", "aqua", "light_blue", "violet", "light_grey", "pink",
      "gold", "yellow", "bright_green", "turquoise", "sky_blue", "plum",
      "silver", "rose", "tan", "light_yellow", "light_green",
      "light_turquoise", "pale_blue", "lavender", "white"
    ]
  },

  "definitions": {
    "Font": {
      "dataclass": "Font",
      "fields": [
        {"name": "name", "type": "text"},
        {"name": "size", "type": "number"},
        {"name": "color", "type": "color"},
        {"name": "bg_color", "type": "color"},
        {"name": "bold", "type": "bool"},
        {"name": "italic", "type": "bool"},
        {"name": "strikeout", "type": "bool"},
        {"name": "underline", "type": "bool"}
      ]
    },
    "Frame": {
      "dataclass": "Frame",
      "fields": [
        {"name": "color", "type": "color"},
        {"name": "margin", "type": "number"},
        {"name": "visible", "type": "bool"}
      ]
    },
    "Show": {
      "dataclass": "Show",
      "fields": [
        {"name": "description", "type": "bool"},
        {"name": "grades", "type": "bool"},
        {"name": "label", "type": "bool"},
        {"name": "date", "type": "bool"},
        {"name": "source_ref", "type": "bool"},
        {"name": "source_type", "type": "bool"},
        {"name": "pin", "type": "bool"}
      ]
    },
    "TimeZone": {
      "dataclass": "TimeZone",
      "fields": [
        {"name": "id", "type": "number", "required": true},
        {"name": "name", "type": "text", "required": true}
      ]
    },
    "CustomProperty": {
      "dataclass": "CustomProperty",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "value", "type": "text", "required": true}
      ]
    },

    "ChartCfg": {
      "dataclass": "ChartCfg",
      "fields": [
        {"name": "bg_color", "type": "color"},
        {"name": "bg_filled", "type": "bool"},
        {"name": "label_merge_rule", "type": "select", "options": ["merge", "append", "discard"]},
        {"name": "icon_quality", "type": "select", "options": ["HighQuality", "Legacy"]},
        {"name": "rigorous", "type": "bool"},
        {"name": "id_reference_linking", "type": "bool"}
      ]
    },
    "ViewCfg": {
      "dataclass": "ViewCfg",
      "fields": [
        {"name": "show_pages_boundaries", "type": "bool"},
        {"name": "show_all", "type": "bool"},
        {"name": "hidden_items", "type": "select", "options": ["hidden", "normal", "grayed"]},
        {"name": "cover_sheet_on_open", "type": "bool"},
        {"name": "time_bar", "type": "bool"}
      ]
    },
    "GridCfg": {
      "dataclass": "GridCfg",
      "fields": [
        {"name": "width", "type": "number"},
        {"name": "height", "type": "number"},
        {"name": "snap", "type": "bool"},
        {"name": "visible", "type": "bool"}
      ]
    },
    "WiringCfg": {
      "dataclass": "WiringCfg",
      "fields": [
        {"name": "distance_far", "type": "number"},
        {"name": "distance_near", "type": "number"},
        {"name": "height", "type": "number"},
        {"name": "spacing", "type": "number"},
        {"name": "use_height_for_theme_icon", "type": "bool"}
      ]
    },
    "LinksCfg": {
      "dataclass": "LinksCfg",
      "fields": [
        {"name": "spacing", "type": "number"},
        {"name": "use_default_spacing_when_dragging", "type": "bool"},
        {"name": "blank_labels", "type": "bool"},
        {"name": "sum_numeric_labels", "type": "bool"}
      ]
    },
    "TimeCfg": {
      "dataclass": "TimeCfg",
      "fields": [
        {"name": "default_date", "type": "text"},
        {"name": "default_datetime", "type": "text"},
        {"name": "tick_rate", "type": "number"},
        {"name": "local_tz", "type": "bool"},
        {"name": "hide_matching_tz_format", "type": "bool"}
      ]
    },
    "SummaryCfg": {
      "dataclass": "SummaryCfg",
      "fields": [
        {"name": "title", "type": "text"},
        {"name": "subject", "type": "text"},
        {"name": "author", "type": "text"},
        {"name": "keywords", "type": "text"},
        {"name": "category", "type": "text"},
        {"name": "comments", "type": "text"},
        {"name": "template", "type": "text"},
        {"name": "created", "type": "text"},
        {"name": "revision", "type": "number"},
        {"name": "edit_time", "type": "number"},
        {"name": "last_print", "type": "text"},
        {"name": "last_save", "type": "text"},
        {"name": "custom_properties", "list_of": "CustomProperty"}
      ]
    },
    "LegendCfg": {
      "dataclass": "LegendCfg",
      "fields": [
        {"name": "show", "type": "bool"},
        {"name": "x", "type": "number"},
        {"name": "y", "type": "number"},
        {"name": "arrange", "type": "select", "options": ["wide", "tall", "square"]},
        {"name": "valign", "type": "select", "options": ["free", "top", "bottom"]},
        {"name": "halign", "type": "select", "options": ["free", "left", "right"]},
        {"name": "font", "ref": "Font"}
      ]
    },

    "GeoMapCfg": {
      "dataclass": "GeoMapCfg",
      "fields": [
        {"name": "attribute_name", "type": "text", "required": true},
        {"name": "mode", "type": "select", "options": ["position", "latlon", "both"]},
        {"name": "width", "type": "number"},
        {"name": "height", "type": "number"},
        {"name": "spread_radius", "type": "number"},
        {"name": "data", "type": "geo_data"},
        {"name": "data_file", "type": "text"},
        {"name": "accent_insensitive", "type": "bool"}
      ]
    },

    "CategoricalStyleCfg": {
      "dataclass": "CategoricalStyleCfg",
      "fields": [
        {"name": "line_color", "type": "color"},
        {"name": "line_width", "type": "number"},
        {"name": "strength", "type": "text"}
      ]
    },
    "IntensityWidthCfg": {
      "dataclass": "IntensityWidthCfg",
      "fields": [
        {"name": "attribute", "type": "text"},
        {"name": "scale", "type": "enum", "enum": "IntensityScale"},
        {"name": "domain", "type": "any"},
        {"name": "clip", "type": "bool"},
        {"name": "power", "type": "number"},
        {"name": "range", "type": "list-of-number"}
      ]
    },
    "IntensityColorCfg": {
      "dataclass": "IntensityColorCfg",
      "fields": [
        {"name": "attribute", "type": "text"},
        {"name": "scale", "type": "enum", "enum": "IntensityScale"},
        {"name": "domain", "type": "any"},
        {"name": "clip", "type": "bool"},
        {"name": "power", "type": "number"},
        {"name": "ramp", "type": "list-of-color"},
        {"name": "space", "type": "enum", "enum": "ColorSpace"},
        {"name": "diverging", "type": "bool"},
        {"name": "midpoint", "type": "number"}
      ]
    },
    "IntensityCfg": {
      "dataclass": "IntensityCfg",
      "fields": [
        {"name": "attribute", "type": "text"},
        {"name": "scale", "type": "enum", "enum": "IntensityScale"},
        {"name": "domain", "type": "any"},
        {"name": "clip", "type": "bool"},
        {"name": "missing", "type": "enum", "enum": "MissingPolicy"},
        {"name": "legend", "type": "bool"},
        {"name": "legend_count", "type": "number"},
        {"name": "decimal_separator", "type": "text"},
        {"name": "thousand_separator", "type": "text"},
        {"name": "width", "ref": "IntensityWidthCfg"},
        {"name": "color", "ref": "IntensityColorCfg"}
      ]
    },
    "CategoricalCfg": {
      "dataclass": "CategoricalCfg",
      "fields": [
        {"name": "attribute", "type": "text"},
        {"name": "styles", "type": "dict_of", "value_ref": "CategoricalStyleCfg"},
        {"name": "default", "ref": "CategoricalStyleCfg"},
        {"name": "missing", "type": "enum", "enum": "MissingPolicy"},
        {"name": "case_sensitive", "type": "bool"},
        {"name": "accent_insensitive", "type": "bool"},
        {"name": "legend", "type": "bool"}
      ]
    },
    "LinkStylingCfg": {
      "dataclass": "LinkStylingCfg",
      "fields": [
        {"name": "intensity", "ref": "IntensityCfg"},
        {"name": "categorical", "ref": "CategoricalCfg"}
      ]
    },
    "StylingCfg": {
      "dataclass": "StylingCfg",
      "fields": [
        {"name": "links", "ref": "LinkStylingCfg"}
      ]
    },

    "DisplaySource": {
      "dataclass": "DisplaySource",
      "fields": [
        {"name": "attribute", "type": "text", "required": true},
        {"name": "alias", "type": "text"},
        {"name": "missing", "type": "select", "options": ["skip", "substitute", "error"]},
        {"name": "placeholder", "type": "text"}
      ]
    },
    "DisplayAttribute": {
      "dataclass": "DisplayAttribute",
      "fields": [
        {"name": "key", "type": "text", "required": true},
        {"name": "attribute_name", "type": "text", "required": true},
        {"name": "kind", "type": "select", "options": ["entity", "link", "both"]},
        {"name": "type", "type": "text"},
        {"name": "template", "type": "text", "required": true},
        {"name": "decimal_separator", "type": "text"},
        {"name": "thousand_separator", "type": "text"},
        {"name": "sources", "list_of": "DisplaySource"},
        {"name": "attribute_class", "ref": "AttributeClass"}
      ]
    },
    "DisplayLabel": {
      "dataclass": "DisplayLabel",
      "fields": [
        {"name": "key", "type": "text", "required": true},
        {"name": "kind", "type": "select", "options": ["entity", "link", "both"]},
        {"name": "type", "type": "text"},
        {"name": "template", "type": "text", "required": true},
        {"name": "decimal_separator", "type": "text"},
        {"name": "thousand_separator", "type": "text"},
        {"name": "sources", "list_of": "DisplaySource"},
        {"name": "override_existing", "type": "bool"}
      ]
    },

    "ExtraCfg": {
      "dataclass": "ExtraCfg",
      "fields": [
        {"name": "entity_auto_color", "type": "bool"},
        {"name": "link_match_entity_color", "type": "bool"},
        {"name": "arrange", "type": "select", "options": ["radial", "circle", "grid", "random", "fr", "forceatlas2", "tree"]},
        {"name": "layout_scale", "type": "number"},
        {"name": "link_arc_offset", "type": "number"},
        {"name": "geo_map", "ref": "GeoMapCfg"},
        {"name": "styling", "ref": "StylingCfg"},
        {"name": "display_attribute", "list_of": "DisplayAttribute"},
        {"name": "display_label", "list_of": "DisplayLabel"}
      ]
    },

    "Settings": {
      "dataclass": "Settings",
      "fields": [
        {"name": "chart", "ref": "ChartCfg"},
        {"name": "font", "ref": "Font"},
        {"name": "view", "ref": "ViewCfg"},
        {"name": "grid", "ref": "GridCfg"},
        {"name": "wiring", "ref": "WiringCfg"},
        {"name": "links_cfg", "ref": "LinksCfg"},
        {"name": "time", "ref": "TimeCfg"},
        {"name": "summary", "ref": "SummaryCfg"},
        {"name": "legend_cfg", "ref": "LegendCfg"},
        {"name": "extra_cfg", "ref": "ExtraCfg"}
      ]
    },

    "EntityType": {
      "dataclass": "EntityType",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "icon_file", "type": "text"},
        {"name": "color", "type": "color"},
        {"name": "shade_color", "type": "color"},
        {"name": "representation", "type": "enum", "enum": "Representation"},
        {"name": "semantic_type", "type": "text"}
      ]
    },
    "LinkType": {
      "dataclass": "LinkType",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "color", "type": "color"},
        {"name": "semantic_type", "type": "text"}
      ]
    },

    "AttributeClass": {
      "dataclass": "AttributeClass",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "type", "type": "enum", "enum": "AttributeType", "required": true},
        {"name": "prefix", "type": "text"},
        {"name": "suffix", "type": "text"},
        {"name": "decimal_places", "type": "number"},
        {"name": "show_value", "type": "bool"},
        {"name": "show_date", "type": "bool"},
        {"name": "show_time", "type": "bool"},
        {"name": "show_seconds", "type": "bool"},
        {"name": "show_if_set", "type": "bool"},
        {"name": "show_class_name", "type": "bool"},
        {"name": "show_symbol", "type": "bool"},
        {"name": "visible", "type": "bool"},
        {"name": "is_user", "type": "bool"},
        {"name": "user_can_add", "type": "bool"},
        {"name": "user_can_remove", "type": "bool"},
        {"name": "icon_file", "type": "text"},
        {"name": "semantic_type", "type": "text"},
        {"name": "merge_behaviour", "type": "enum", "enum": "MergeBehaviour"},
        {"name": "paste_behaviour", "type": "enum", "enum": "MergeBehaviour"},
        {"name": "font", "ref": "Font"}
      ]
    },

    "Strength": {
      "dataclass": "Strength",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "dot_style", "type": "enum", "enum": "DotStyle"}
      ]
    },
    "StrengthCollection": {
      "dataclass": "StrengthCollection",
      "fields": [
        {"name": "default", "type": "text"},
        {"name": "items", "list_of": "Strength"}
      ]
    },

    "GradeCollection": {
      "dataclass": "GradeCollection",
      "fields": [
        {"name": "default", "type": "text"},
        {"name": "items", "type": "list-of-text"}
      ]
    },

    "DateTimeFormat": {
      "dataclass": "DateTimeFormat",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "format", "type": "text"}
      ]
    },

    "PaletteAttributeEntry": {
      "dataclass": "PaletteAttributeEntry",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "value", "type": "text"}
      ]
    },
    "Palette": {
      "dataclass": "Palette",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "locked", "type": "bool"},
        {"name": "entity_types", "type": "list-of-text"},
        {"name": "link_types", "type": "list-of-text"},
        {"name": "attribute_classes", "type": "list-of-text"},
        {"name": "attribute_entries", "list_of": "PaletteAttributeEntry"}
      ]
    },

    "LegendItem": {
      "dataclass": "LegendItem",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "item_type", "type": "enum", "enum": "LegendItemType"},
        {"name": "color", "type": "color"},
        {"name": "line_width", "type": "number"},
        {"name": "dash_style", "type": "enum", "enum": "DotStyle"},
        {"name": "arrows", "type": "enum", "enum": "ArrowStyle"},
        {"name": "image_name", "type": "text"},
        {"name": "shade_color", "type": "color"},
        {"name": "font", "ref": "Font"}
      ]
    },

    "SemanticEntity": {
      "dataclass": "SemanticEntity",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "kind_of", "type": "text", "required": true},
        {"name": "guid", "type": "text"},
        {"name": "abstract", "type": "bool"},
        {"name": "synonyms", "type": "list-of-text"},
        {"name": "description", "type": "text"}
      ]
    },
    "SemanticLink": {
      "dataclass": "SemanticLink",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "kind_of", "type": "text", "required": true},
        {"name": "guid", "type": "text"},
        {"name": "abstract", "type": "bool"},
        {"name": "synonyms", "type": "list-of-text"},
        {"name": "description", "type": "text"}
      ]
    },
    "SemanticProperty": {
      "dataclass": "SemanticProperty",
      "fields": [
        {"name": "name", "type": "text", "required": true},
        {"name": "base_property", "type": "text", "required": true},
        {"name": "guid", "type": "text"},
        {"name": "abstract", "type": "bool"},
        {"name": "synonyms", "type": "list-of-text"},
        {"name": "description", "type": "text"}
      ]
    }
  },

  "sections": {
    "settings":            {"ref": "Settings"},
    "entity_types":        {"list_of": "EntityType"},
    "link_types":          {"list_of": "LinkType"},
    "attribute_classes":   {"list_of": "AttributeClass"},
    "strengths":           {"ref": "StrengthCollection"},
    "datetime_formats":    {"list_of": "DateTimeFormat"},
    "palettes":            {"list_of": "Palette"},
    "grades_one":          {"ref": "GradeCollection"},
    "grades_two":          {"ref": "GradeCollection"},
    "grades_three":        {"ref": "GradeCollection"},
    "source_types":        {"type": "list-of-text"},
    "legend_items":        {"list_of": "LegendItem"},
    "semantic_entities":   {"list_of": "SemanticEntity"},
    "semantic_links":      {"list_of": "SemanticLink"},
    "semantic_properties": {"list_of": "SemanticProperty"}
  }
}
;

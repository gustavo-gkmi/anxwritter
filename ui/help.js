// Per-field help text for the config builder.
//
// Keyed as "DefinitionName.fieldName". Used by app.js to populate the
// help modal opened by the "(?)" button next to each field label.
// Sourced from docs/reference/*.md and CLAUDE.md.
//
// To add or amend help: edit this file. No test enforces coverage —
// fields without an entry simply show no (?) button.

window.HELP = {
  // ── Font (shared across chart/legend/AttributeClass/label_font) ─────
  "Font.name":      "Typeface name. ANB default: 'Tahoma'. XML: FaceName.",
  "Font.size":      "Font size in points. ANB default: 10. XML: PointSize.",
  "Font.color":     "Text color. ANB default: 0 (black). Accepts named color, '#RRGGBB', or COLORREF int. XML: FontColour.",
  "Font.bg_color":  "Text background color. ANB default: 16777215 (white). XML: BackColour.",
  "Font.bold":      "Bold weight. ANB default: false. XML: Bold.",
  "Font.italic":    "Italic style. ANB default: false. XML: Italic.",
  "Font.strikeout": "Strikethrough. ANB default: false. XML: Strikeout.",
  "Font.underline": "Underline. ANB default: false. XML: Underline.",

  // ── Frame (icon frame border) ───────────────────────────────────────
  "Frame.color":   "Frame highlight border color. Default 16764057 (light yellow). Accepts named color, '#RRGGBB', or COLORREF int.",
  "Frame.margin":  "Pixel margin between the icon and the frame border. Default 2.",
  "Frame.visible": "Whether the frame is rendered. Default false.",

  // ── Show (sub-item visibility flags on a ChartItem) ─────────────────
  "Show.description": "Show the entity/link description sub-item. ANB default: false.",
  "Show.grades":      "Show the grade indicators. ANB default: false.",
  "Show.label":       "Show the display label. ANB default: true (this is the only sub-item shown by default).",
  "Show.date":        "Show date/time on the item. ANB default: false.",
  "Show.source_ref":  "Show source reference. ANB default: false.",
  "Show.source_type": "Show source type label. ANB default: false.",
  "Show.pin":         "Show the pin marker (graphical pin icon). ANB default: false.",

  // ── TimeZone ────────────────────────────────────────────────────────
  "TimeZone.id":   "ANB internal timezone UniqueID integer (1–122). NOT the Windows registry Index. Key values: 1=UTC, 32=GMT, 27=EST(-5), 17=CET(+1), 52=PST(-8), 65=Japan(+9). Full map in anxwritter/timezones.json.",
  "TimeZone.name": "Cosmetic display string (e.g. 'UTC', 'Brasília'). ANB resolves the timezone from id alone, but name is required by the schema.",

  // ── CustomProperty ──────────────────────────────────────────────────
  "CustomProperty.name":  "Custom property name (shown in ANB's document properties dialog).",
  "CustomProperty.value": "Custom property value. Always emitted as Type=\"String\" in XML.",

  // ── ChartCfg — <Chart> attributes ──────────────────────────────────
  "ChartCfg.bg_color":             "Chart background color. ANB default: 16777215 (white). Accepts named color, '#RRGGBB', or COLORREF int. XML: BackColour.",
  "ChartCfg.bg_filled":            "Whether the background color is filled. ANB default: true. XML: IsBackColourFilled.",
  "ChartCfg.label_merge_rule":     "How labels are combined when entities merge. Values: 'merge', 'append', 'discard'. ANB default: 'merge'.",
  "ChartCfg.icon_quality":         "Icon rendering quality mode. 'HighQuality' uses vector / anti-aliased rendering; 'Legacy' uses the older rendering engine. ANB default: 'HighQuality'. XML: TypeIconDrawingMode.",
  "ChartCfg.rigorous":             "Enables rigorous validation mode in ANB. ANB default: true. XML: Rigorous.",
  "ChartCfg.id_reference_linking": "Enables ID-based reference linking. ANB default: true. XML: IdReferenceLinking.",

  // ── ViewCfg — display toggles ──────────────────────────────────────
  "ViewCfg.show_pages_boundaries": "Show page boundary lines on the canvas. ANB default: false. XML: ShowPages.",
  "ViewCfg.show_all":              "Show all items including hidden ones. ANB default: false. XML: ShowAllFlag.",
  "ViewCfg.hidden_items":          "How hidden items appear: 'hidden', 'normal', or 'grayed'. ANB default: 'hidden'.",
  "ViewCfg.cover_sheet_on_open":   "Display the cover sheet when the chart is opened. ANB default: false.",
  "ViewCfg.time_bar":              "Show the time bar at the bottom of the chart. ANB default: false. XML: TimeBarVisible.",

  // ── GridCfg ────────────────────────────────────────────────────────
  "GridCfg.width":   "Grid cell width in inches. ANB default: ~0.295 (≈ 7.5mm).",
  "GridCfg.height":  "Grid cell height in inches. ANB default: ~0.295.",
  "GridCfg.snap":    "Snap entities to grid positions when dragging. ANB default: false.",
  "GridCfg.visible": "Display the grid on all chart views. ANB default: false.",

  // ── WiringCfg — theme/event wiring rendering ───────────────────────
  "WiringCfg.distance_far":              "Far wiring distance in inches. ANB default: ~0.394.",
  "WiringCfg.distance_near":             "Near wiring distance in inches. ANB default: ~0.079.",
  "WiringCfg.height":                    "Wiring height in inches. ANB default: ~0.118.",
  "WiringCfg.spacing":                   "Wiring spacing in inches. ANB default: ~0.197.",
  "WiringCfg.use_height_for_theme_icon": "Use the wiring height for theme icon sizing. ANB default: true.",

  // ── LinksCfg — chart-level link defaults ───────────────────────────
  "LinksCfg.spacing":                          "Default spacing between parallel link lines in inches. ANB default: ~0.295.",
  "LinksCfg.use_default_spacing_when_dragging": "Apply default spacing when dragging links. ANB default: true.",
  "LinksCfg.blank_labels":                     "Suppress link label display globally. ANB default: false.",
  "LinksCfg.sum_numeric_labels":               "Automatically sum numeric link labels. ANB default: false.",

  // ── TimeCfg — date/time/timezone defaults ──────────────────────────
  "TimeCfg.default_date":            "Default date for items lacking one. ANB default: '2000-01-01T00:00:00.000'.",
  "TimeCfg.default_datetime":        "Default datetime for new charts. ANB default: '2000-01-01T00:00:00.000'.",
  "TimeCfg.tick_rate":               "Timeline tick rate. ANB default: 0.0031.",
  "TimeCfg.local_tz":                "Whether ANB uses the local time zone for display. ANB default: true.",
  "TimeCfg.hide_matching_tz_format": "Hide the timezone format when it matches the chart timezone. ANB default: false.",

  // ── SummaryCfg — document metadata ─────────────────────────────────
  "SummaryCfg.title":             "Document title. Maps to <Field Type=\"SummaryFieldTitle\">.",
  "SummaryCfg.subject":           "Document subject.",
  "SummaryCfg.author":            "Document author.",
  "SummaryCfg.keywords":          "Comma-separated keywords for indexing.",
  "SummaryCfg.category":          "Document category.",
  "SummaryCfg.comments":          "Free-text comments / description.",
  "SummaryCfg.template":          "Template identifier.",
  "SummaryCfg.created":           "Creation timestamp. ANB auto-populates with the current datetime when any summary field is set.",
  "SummaryCfg.revision":          "Revision number integer. ANB default: 1.",
  "SummaryCfg.edit_time":         "Total edit time in ticks. ANB default: 0.",
  "SummaryCfg.last_print":        "Last print date (ISO string). Omitted by default.",
  "SummaryCfg.last_save":         "Last save date (ISO string). Omitted by default.",
  "SummaryCfg.custom_properties": "List of name/value custom properties shown in ANB's document properties dialog. Always Type=\"String\" in XML.",

  // ── LegendCfg ──────────────────────────────────────────────────────
  "LegendCfg.show":    "Whether the legend panel is visible. Legend items are still generated when false. ANB default: false.",
  "LegendCfg.x":       "Legend panel X position on the canvas. ANB default: 0.",
  "LegendCfg.y":       "Legend panel Y position on the canvas. ANB default: 0.",
  "LegendCfg.arrange": "Legend layout: 'wide', 'tall', or 'square'. ANB default: 'wide'.",
  "LegendCfg.valign":  "Vertical alignment: 'free', 'top', or 'bottom'. ANB default: 'free'.",
  "LegendCfg.halign":  "Horizontal alignment: 'free', 'left', or 'right'. ANB default: 'free'.",
  "LegendCfg.font":    "Legend font (shared Font dataclass). Only emitted when at least one field is set.",

  // ── GeoMapCfg — geographic positioning ─────────────────────────────
  "GeoMapCfg.attribute_name":     "Entity attribute name to match against geo data keys (e.g. 'Cidade/UF'). Required.",
  "GeoMapCfg.mode":               "'position' = canvas x,y only; 'latlon' = inject Latitude/Longitude attributes only (with semantic types) for ANB Esri Maps; 'both' = canvas positioning + ANB mapping. Default: 'both'.",
  "GeoMapCfg.width":              "Canvas projection area width in chart units. Default: 3000.",
  "GeoMapCfg.height":             "Canvas projection area height in chart units. Default: 2000.",
  "GeoMapCfg.spread_radius":      "Circle radius (px) for distributing multiple entities sharing the same geo key around the center point. Lat/lon attributes always use exact coordinates. Default: 0 (no spread).",
  "GeoMapCfg.data":               "Inline lookup of place name → [lat, lon]. Provide either data or data_file.",
  "GeoMapCfg.data_file":          "Path to an external JSON or YAML file with the same {key: [lat, lon]} shape. Relative paths resolve against the config file's directory.",
  "GeoMapCfg.accent_insensitive": "Fold Unicode diacritics during matching — 'São Paulo', 'SAO PAULO', and 'sao paulo' all match the same key. Default: true. Set false for strict matching.",

  // ── CategoricalStyleCfg ────────────────────────────────────────────
  "CategoricalStyleCfg.line_color": "Link line color for this category value.",
  "CategoricalStyleCfg.line_width": "Link line thickness (integer) for this category value.",
  "CategoricalStyleCfg.strength":   "Named strength for this category value. Must be registered via the Strengths section.",

  // ── IntensityWidthCfg ──────────────────────────────────────────────
  "IntensityWidthCfg.attribute": "(Optional) Per-block override of the driving numeric attribute. Falls back to the parent IntensityCfg.attribute.",
  "IntensityWidthCfg.scale":     "(Optional) Per-block scale: linear / log / sqrt / power / quantile. Falls back to the parent.",
  "IntensityWidthCfg.domain":    "(Optional) Domain bounds: [min, max], or 'robust' (5/95 percentile), or omit for auto.",
  "IntensityWidthCfg.clip":      "Clip values outside the domain to the endpoints instead of extrapolating.",
  "IntensityWidthCfg.power":     "Exponent for scale=power.",
  "IntensityWidthCfg.range":     "Required: [min_width, max_width] for the resulting line thickness.",

  // ── IntensityColorCfg ──────────────────────────────────────────────
  "IntensityColorCfg.attribute": "(Optional) Per-block override of the driving numeric attribute.",
  "IntensityColorCfg.scale":     "(Optional) Per-block scale (overrides parent).",
  "IntensityColorCfg.domain":    "(Optional) [min, max], 'robust', or omit for auto.",
  "IntensityColorCfg.clip":      "Clip out-of-domain values to the endpoints.",
  "IntensityColorCfg.power":     "Exponent for scale=power.",
  "IntensityColorCfg.ramp":      "Required: list of ≥2 colors. Evenly-spaced stops along the scale.",
  "IntensityColorCfg.space":     "Interpolation color space: rgb / rgb_linear (default, gamma-correct) / hsl.",
  "IntensityColorCfg.diverging": "Diverging ramp centered on midpoint. Requires midpoint to be set.",
  "IntensityColorCfg.midpoint":  "Center point for diverging ramp (e.g. 0 for a zero-centered ramp).",

  // ── IntensityCfg (numeric attribute → width and/or color) ──────────
  "IntensityCfg.attribute":          "Driving numeric link attribute. Top-level shortcut inherited by both width and color sub-blocks.",
  "IntensityCfg.scale":              "Scale: linear / log / sqrt (default) / power / quantile. log requires every value > 0.",
  "IntensityCfg.domain":             "Domain bounds: [min, max], 'robust' (5/95 percentile), or omit for auto.",
  "IntensityCfg.clip":               "Clip values outside the domain to the endpoints instead of extrapolating.",
  "IntensityCfg.missing":            "Policy for links missing the attribute: 'fallback' (default), 'skip', or 'error'.",
  "IntensityCfg.legend":             "Auto-emit LegendItem rows sampled along the scale.",
  "IntensityCfg.legend_count":       "Number of legend rows to emit when legend=true. Default 5.",
  "IntensityCfg.decimal_separator":  "Decimal mark for legend labels (e.g. ',' for Brazilian Portuguese). Default '.'.",
  "IntensityCfg.thousand_separator": "Thousands grouping mark for legend labels (e.g. '.' for Brazilian Portuguese). Default ','.",
  "IntensityCfg.width":              "Width sub-block — IntensityWidthCfg with required 'range: [min, max]'.",
  "IntensityCfg.color":              "Color sub-block — IntensityColorCfg with required 'ramp: [colors...]'.",

  // ── CategoricalCfg ─────────────────────────────────────────────────
  "CategoricalCfg.attribute":          "Driving string link attribute (e.g. 'source_type').",
  "CategoricalCfg.styles":             "Map of attribute value → CategoricalStyleCfg.",
  "CategoricalCfg.default":            "Style applied to values not found in 'styles' (when missing='fallback').",
  "CategoricalCfg.missing":            "Policy for links missing or unmatched: 'fallback' (default), 'skip', or 'error'.",
  "CategoricalCfg.case_sensitive":     "Match case-sensitively. Default false.",
  "CategoricalCfg.accent_insensitive": "Fold Unicode diacritics when matching. Default true.",
  "CategoricalCfg.legend":             "Auto-emit one LegendItem row per styles entry in insertion order.",

  // ── LinkStylingCfg / StylingCfg ────────────────────────────────────
  "LinkStylingCfg.intensity":   "Continuous numeric styling (width and/or color from a numeric attribute).",
  "LinkStylingCfg.categorical": "Discrete styling (look up style by attribute value).",
  "StylingCfg.links":           "Data-driven link styling. Two modes: intensity (numeric) and categorical (string). Pure functions of a single attribute.",

  // ── DisplaySource ──────────────────────────────────────────────────
  "DisplaySource.attribute":   "Source AttributeClass name to read from (required).",
  "DisplaySource.alias":       "Alias used in the template (required when the attribute name isn't a valid Python identifier — spaces, accents, etc).",
  "DisplaySource.missing":     "Per-source policy when the value is missing: 'skip' (default — drop the whole rendered output for this item), 'substitute' (use placeholder), or 'error'.",
  "DisplaySource.placeholder": "Used when missing='substitute' (e.g. '?').",

  // ── DisplayAttribute (synthesizes a text-sibling AC) ───────────────
  "DisplayAttribute.key":                "Stable identity for config layering / lock / delete (required).",
  "DisplayAttribute.attribute_name":     "Name of the synthesized sibling AttributeClass (required).",
  "DisplayAttribute.kind":               "Scope: 'entity', 'link', or 'both' (default).",
  "DisplayAttribute.type":               "Optional type-name filter (e.g. only Person entities or only Call links).",
  "DisplayAttribute.template":           "str.format_map template body (no f prefix, no code). Supports {alias:format_spec} like {x:,.2f} or {d:%d/%m/%Y}. May be a static literal when sources is empty.",
  "DisplayAttribute.decimal_separator":  "Decimal mark for numeric format-spec output (e.g. ',').",
  "DisplayAttribute.thousand_separator": "Thousands grouping mark for numeric format-spec output (e.g. '.').",
  "DisplayAttribute.sources":            "List of DisplaySource entries. Optional when the template has no {alias} placeholders (a static literal); required when it does.",
  "DisplayAttribute.attribute_class":    "Styling template for the synthesized sibling AC (font, prefix, suffix, etc). Inner .name and .type must be None — the sibling is auto-named and auto-typed text.",

  // ── DisplayLabel (renders into the entity/link label) ──────────────
  "DisplayLabel.key":                "Stable identity for config layering / lock / delete (required).",
  "DisplayLabel.kind":               "Scope: 'entity', 'link', or 'both' (default).",
  "DisplayLabel.type":               "Optional type-name filter.",
  "DisplayLabel.template":           "str.format_map template body. Supports {alias:format_spec}. May be a static literal when sources is empty.",
  "DisplayLabel.decimal_separator":  "Decimal mark for numeric format-spec output.",
  "DisplayLabel.thousand_separator": "Thousands grouping mark for numeric format-spec output.",
  "DisplayLabel.sources":            "List of DisplaySource entries. Optional for static templates.",
  "DisplayLabel.override_existing":  "When true, replace an already-set label. Default false — manual labels are preserved (an entity label defaulting to its id, or an empty link label, count as unset).",

  // ── ExtraCfg — anxwritter-only knobs (NOT written to ANX XML) ──────
  "ExtraCfg.entity_auto_color":       "Distribute evenly-spaced HSV hues across entities that have no explicit color. Also sets label_font.color/.bg_color for contrast. Explicit field values always win.",
  "ExtraCfg.link_match_entity_color": "Set each link's LineColour to match its to_id entity's resolved color. Only affects the line color, not the label font. Explicit line_color on a Link always overrides.",
  "ExtraCfg.arrange":                 "Auto-layout algorithm for entities without explicit x/y. Geometric: radial (default), circle, grid, random. Topology-aware: fr (Fruchterman-Reingold), forceatlas2 (recommended for cluster reveal), tree (Reingold-Tilford). Pinned entities act as anchors.",
  "ExtraCfg.layout_scale":            "Uniform spread multiplier applied to every layout algorithm. 2.0 doubles entity-to-entity distance; 0.5 halves it. Pinned positions are absolute and ignore this. Default 1.0.",
  "ExtraCfg.link_arc_offset":         "Default pixel offset between parallel links sharing the same entity pair. 0 disables auto-spacing. Explicit Link.offset always wins. Default 20.",
  "ExtraCfg.geo_map":                 "Geographic positioning — maps an entity attribute (e.g. 'City') through a {place: [lat, lon]} lookup to canvas x/y and/or Latitude/Longitude ANB attributes.",
  "ExtraCfg.styling":                 "Data-driven link styling. Two modes under styling.links: intensity (numeric attribute → width/color) and categorical (string attribute → style lookup).",
  "ExtraCfg.display_attribute":       "Chart-level synthesizer that renders source attributes through a template into a synthesized text-sibling AttributeClass. Use with datetime sources + {d:%Y-%m-%d} for the ANB v9 datetime canvas-render workaround.",
  "ExtraCfg.display_label":           "Chart-level synthesizer that renders source attributes through a template into the entity/link label. Honors override_existing.",

  // ── Settings (top level — composes the 10 sub-groups) ──────────────
  "Settings.chart":      "Core <Chart> attributes — background color, label merge rule, validation flags.",
  "Settings.font":       "Chart-level default <Font>. Only emitted when at least one field is set; otherwise ANB uses Tahoma 10pt.",
  "Settings.view":       "Display toggles — page boundaries, hidden-item visibility, time bar.",
  "Settings.grid":       "Grid size, snap, visibility.",
  "Settings.wiring":     "Theme/event wiring rendering distances.",
  "Settings.links_cfg":  "Chart-level link defaults — spacing, label suppression.",
  "Settings.time":       "Default date/time and timezone behaviour.",
  "Settings.summary":    "Document metadata (title, author, keywords, etc.) and custom properties.",
  "Settings.legend_cfg": "Legend appearance and position. Set show=true to make the panel visible.",
  "Settings.extra_cfg":  "anxwritter-only knobs (NOT written to ANX XML) — auto-color, layout algorithm, geo_map, styling, display synthesizers.",

  // ── EntityType ─────────────────────────────────────────────────────
  "EntityType.name":           "Entity type name (required). Referenced from data by name.",
  "EntityType.icon_file":      "ANB icon key (e.g. 'person'). Omitted when unset — ANB looks up the type name in the loaded catalogue.",
  "EntityType.color":          "LINE color (not icon shading). Accepts named color, '#RRGGBB', or COLORREF int.",
  "EntityType.shade_color":    "Icon tint/shading color. Per-entity IconShadingColour overrides this.",
  "EntityType.representation": "Preferred representation: Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label.",
  "EntityType.semantic_type":  "Semantic type name (resolved from semantic_entities) or raw guid… string. Used to populate the embedded lcx:LibraryCatalogue.",

  // ── LinkType ───────────────────────────────────────────────────────
  "LinkType.name":          "Link type name (required). Referenced from data by name.",
  "LinkType.color":         "Line color. Accepts named color, '#RRGGBB', or COLORREF int.",
  "LinkType.semantic_type": "Semantic type name (resolved from semantic_links) or raw guid… string.",

  // ── AttributeClass ─────────────────────────────────────────────────
  "AttributeClass.name":            "Attribute class name (required, primary key).",
  "AttributeClass.type":            "Data type (required): text, number, flag, or datetime. Never inferred — validation rejects omission with missing_required.",
  "AttributeClass.prefix":          "Prefix string displayed before the value (e.g. 'R$ '). Sets ShowPrefix=true automatically when non-empty.",
  "AttributeClass.suffix":          "Suffix string displayed after the value (e.g. ' kg'). Sets ShowSuffix=true automatically.",
  "AttributeClass.decimal_places":  "Number of decimal places (Number type only). ANB default: 0.",
  "AttributeClass.show_value":      "Display the attribute value. anxwritter forces true by default (ANB's silent default is false). Set false to hide.",
  "AttributeClass.show_date":       "Show the date part (DateTime type). ANB default: true.",
  "AttributeClass.show_time":       "Show the time part (DateTime type). ANB default: true.",
  "AttributeClass.show_seconds":    "Show seconds (DateTime type). ANB default: false.",
  "AttributeClass.show_if_set":     "Show the Flag attribute only when value is true (Flag type). ANB default: false.",
  "AttributeClass.show_class_name": "Display the attribute class name alongside the value. ANB default: false.",
  "AttributeClass.show_symbol":     "Display the attribute symbol/icon. ANB default: true.",
  "AttributeClass.visible":         "Visible in the ANB UI. ANB default: true. NOTE: datetime ACs cannot have visible=true (ANB v9 doesn't render datetimes on canvas) — use display_attribute as a workaround.",
  "AttributeClass.is_user":         "Whether the attribute was defined by the user (vs system). Always emitted. ACs with is_user=false CANNOT appear in palettes.",
  "AttributeClass.user_can_add":    "Whether users can add this attribute to items in ANB UI. Always emitted. ACs with user_can_add=false CANNOT appear in palettes.",
  "AttributeClass.user_can_remove": "Whether users can remove this attribute from items in ANB UI. Always emitted.",
  "AttributeClass.icon_file":       "ANB icon key for the attribute symbol (e.g. 'phone'). First registration wins.",
  "AttributeClass.semantic_type":   "NCName from i2 Semantic Type Library — name resolved from semantic_properties, or raw guid… passthrough. Must be unique across all attribute classes.",
  "AttributeClass.merge_behaviour": "How values combine when two items merge. Omitted by default. Valid per type: Text — add/add_space/add_line_break; Number — add/max/min; DateTime — min/max; Flag — or/and/xor.",
  "AttributeClass.paste_behaviour": "How values combine on paste. Omitted by default. Same per-type set as merge, plus assign / noop (all types), and subtract / subtract_swap (Number only).",
  "AttributeClass.font":            "Font for the attribute display (shared Font dataclass).",

  // ── Strength / StrengthCollection ──────────────────────────────────
  "Strength.name":                "Strength name (required). Referenced by the 'strength' field on entities and links.",
  "Strength.dot_style":           "Line dash pattern: solid (-), dashed (---), dash_dot (-.), dash_dot_dot (-..), dotted (...).",
  "StrengthCollection.default":   "Strength name used as fallback for items that omit 'strength'. Must reference an entry in items.",
  "StrengthCollection.items":     "List of named Strength entries.",

  // ── GradeCollection (used by grades_one/two/three) ─────────────────
  "GradeCollection.default": "Grade name assigned to ungraded items. Must exist in items. When None and items is non-empty, a '-' sentinel is appended at build time.",
  "GradeCollection.items":   "List of grade label strings. Referenced by 0-based index OR by name on grade_one/two/three.",

  // ── DateTimeFormat ─────────────────────────────────────────────────
  "DateTimeFormat.name":   "Format name (required, max 250 chars). Referenced by entities/links via datetime_format field.",
  "DateTimeFormat.format": "Format string (optional, max 259 chars). e.g. 'dd/MM/yyyy', 'yyyy-MM-dd HH:mm'.",

  // ── Palette / PaletteAttributeEntry ────────────────────────────────
  "Palette.name":              "Palette name shown in ANB's 'Insert from Palette' UI.",
  "Palette.locked":            "Lock the order of entity types within the palette. Default false.",
  "Palette.entity_types":      "List of EntityType names to include in this palette.",
  "Palette.link_types":        "List of LinkType names to include.",
  "Palette.attribute_classes": "List of AttributeClass names (no pre-filled values). Cannot include ACs with is_user=false or user_can_add=false.",
  "Palette.attribute_entries": "AttributeClass entries with pre-filled values.",
  "PaletteAttributeEntry.name":  "AttributeClass name (required).",
  "PaletteAttributeEntry.value": "Pre-filled value. Unset = class only, no default value.",

  // ── LegendItem ─────────────────────────────────────────────────────
  "LegendItem.name":        "Text label for the legend item (required). Maps to Label XML attribute.",
  "LegendItem.item_type":   "Legend item type: font (default) / text / icon / attribute / line / link / timezone / icon_frame.",
  "LegendItem.color":       "Line/frame color for Line, Link, and IconFrame items.",
  "LegendItem.line_width":  "Line thickness 1–20 for Line/Link items.",
  "LegendItem.dash_style":  "Dash pattern for Line/Link items: solid / dashed / dash_dot / dash_dot_dot / dotted. Default solid.",
  "LegendItem.arrows":      "Arrow style for Link items only: head ('->'), tail ('<-'), both ('<->').",
  "LegendItem.image_name":  "Icon key for Icon/Attribute rows (e.g. 'reddot', 'phone'). For Attribute rows this is a free-form icon picker — it does NOT link to any AttributeClass.",
  "LegendItem.shade_color": "Icon tint color for Icon/Attribute rows.",
  "LegendItem.font":        "Font (shared Font dataclass). Font/Text/TimeZone item types always emit a <Font> child; Icon/Attribute/IconFrame only when fields are set; Line/Link never.",

  // ── SemanticEntity / Link / Property ───────────────────────────────
  "SemanticEntity.name":        "Type name (required). Maps to <TypeName>.",
  "SemanticEntity.kind_of":     "Parent entity type name (required). Must exist in catalogue or earlier semantic_entities entries. Use 'Entity' for top-level custom types.",
  "SemanticEntity.guid":        "Override GUID. When unset, a deterministic UUID5 is auto-generated from the name. Standard library types need the explicit i2 GUID.",
  "SemanticEntity.abstract":    "Whether this is an abstract (non-instantiable) type. Default false.",
  "SemanticEntity.synonyms":    "List of synonym strings, used for the ANB semantic picker search.",
  "SemanticEntity.description": "Description text shown in ANB's documentation panel.",

  "SemanticLink.name":        "Link type name (required).",
  "SemanticLink.kind_of":     "Parent link type name (required). Use 'Link' for top-level custom types.",
  "SemanticLink.guid":        "Override GUID. Auto-generated from name when unset.",
  "SemanticLink.abstract":    "Whether this is an abstract type. Default false.",
  "SemanticLink.synonyms":    "List of synonym strings.",
  "SemanticLink.description": "Description text.",

  "SemanticProperty.name":          "Property name (required).",
  "SemanticProperty.base_property": "Parent property name (required). Use one of the 4 abstract roots: 'Abstract Text', 'Abstract Number', 'Abstract Date & Time', or 'Abstract Flag'.",
  "SemanticProperty.guid":          "Override GUID. Auto-generated from name when unset.",
  "SemanticProperty.abstract":      "Whether this is an abstract type. Default false.",
  "SemanticProperty.synonyms":      "List of synonym strings.",
  "SemanticProperty.description":   "Description text.",
};

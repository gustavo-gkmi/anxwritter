// Client-side cross-field validation. Mirrors a useful subset of the library's
// validate() rules so the UI can flag broken configs while the user is still
// editing instead of waiting for the YAML download to fail.
//
// Each rule returns zero or more {path, message} entries; `path` is a dotted
// path that matches the configPath threaded through app.js's render functions
// (e.g. "settings.summary.title", "entity_types[2].name").
//
// This is intentionally a SUBSET — not a re-implementation. The library
// catches everything else at apply_config / validate / to_anx time.

window.validateConfig = function validateConfig(CONFIG) {
  const errors = [];
  const push = (path, message) => errors.push({ path, message });

  // ── 1. Grade collections: default must exist in items ────────────────
  for (const key of ['grades_one', 'grades_two', 'grades_three']) {
    const gc = CONFIG[key];
    if (!gc || typeof gc !== 'object') continue;
    if (gc.default && Array.isArray(gc.items) && !gc.items.includes(gc.default)) {
      push(`${key}.default`,
        `Default "${gc.default}" is not in items.`);
    }
  }

  // ── 2. StrengthCollection: default must exist in items[].name ────────
  const sc = CONFIG.strengths;
  if (sc && typeof sc === 'object' && sc.default) {
    const items = Array.isArray(sc.items) ? sc.items : [];
    const names = items.map(s => s && s.name).filter(Boolean);
    if (!names.includes(sc.default)) {
      push('strengths.default',
        `Default "${sc.default}" doesn't match any strength name.`);
    }
  }

  // ── 3. Duplicate name within named registries ────────────────────────
  const namedSections = [
    'entity_types', 'link_types', 'attribute_classes', 'datetime_formats',
    'palettes', 'legend_items',
    'semantic_entities', 'semantic_links', 'semantic_properties',
  ];
  for (const sec of namedSections) {
    const list = CONFIG[sec];
    if (!Array.isArray(list)) continue;
    const seen = new Map();
    list.forEach((row, idx) => {
      const n = row && row.name;
      if (!n) return;
      if (seen.has(n)) {
        push(`${sec}[${idx}].name`,
          `Duplicate name "${n}" (first used at #${seen.get(n) + 1}).`);
      } else {
        seen.set(n, idx);
      }
    });
  }
  // strengths.items[].name duplicates
  if (sc && Array.isArray(sc.items)) {
    const seen = new Map();
    sc.items.forEach((row, idx) => {
      const n = row && row.name;
      if (!n) return;
      if (seen.has(n)) {
        push(`strengths.items[${idx}].name`,
          `Duplicate name "${n}" (first used at #${seen.get(n) + 1}).`);
      } else {
        seen.set(n, idx);
      }
    });
  }

  // ── 4. AttributeClass type=datetime + visible=true → forbidden ────────
  const acs = Array.isArray(CONFIG.attribute_classes) ? CONFIG.attribute_classes : [];
  acs.forEach((ac, idx) => {
    if (!ac) return;
    if (ac.type === 'datetime' && ac.visible === true) {
      push(`attribute_classes[${idx}].visible`,
        `Datetime AC cannot be visible (ANB v9 doesn't render datetimes on canvas). Use extra_cfg.display_attribute as workaround.`);
    }
  });

  // ── 5. Palettes: reference names must resolve ────────────────────────
  const entityTypeNames = new Set(acs.length ? [] : []);  // placeholder
  const etNames = new Set((CONFIG.entity_types || []).map(e => e && e.name).filter(Boolean));
  const ltNames = new Set((CONFIG.link_types || []).map(l => l && l.name).filter(Boolean));
  const acByName = new Map(acs.map(ac => [ac && ac.name, ac]).filter(([k]) => k));

  const palettes = Array.isArray(CONFIG.palettes) ? CONFIG.palettes : [];
  palettes.forEach((p, pIdx) => {
    if (!p) return;
    (p.entity_types || []).forEach((n, i) => {
      if (n && !etNames.has(n)) {
        push(`palettes[${pIdx}].entity_types[${i}]`,
          `Entity type "${n}" is not registered.`);
      }
    });
    (p.link_types || []).forEach((n, i) => {
      if (n && !ltNames.has(n)) {
        push(`palettes[${pIdx}].link_types[${i}]`,
          `Link type "${n}" is not registered.`);
      }
    });
    (p.attribute_classes || []).forEach((n, i) => {
      if (!n) return;
      const ac = acByName.get(n);
      if (!ac) {
        push(`palettes[${pIdx}].attribute_classes[${i}]`,
          `AttributeClass "${n}" is not registered.`);
        return;
      }
      if (ac.is_user === false) {
        push(`palettes[${pIdx}].attribute_classes[${i}]`,
          `AttributeClass "${n}" has is_user=false; ANB rejects it in palettes.`);
      }
      if (ac.user_can_add === false) {
        push(`palettes[${pIdx}].attribute_classes[${i}]`,
          `AttributeClass "${n}" has user_can_add=false; ANB rejects it in palettes.`);
      }
    });
    (p.attribute_entries || []).forEach((entry, i) => {
      if (entry && entry.name && !acByName.has(entry.name)) {
        push(`palettes[${pIdx}].attribute_entries[${i}].name`,
          `AttributeClass "${entry.name}" is not registered.`);
      }
    });
  });

  // ── 6. Styling: intensity and categorical can't target same attribute ─
  const styling = CONFIG.settings &&
                  CONFIG.settings.extra_cfg &&
                  CONFIG.settings.extra_cfg.styling &&
                  CONFIG.settings.extra_cfg.styling.links;
  if (styling && styling.intensity && styling.categorical) {
    const iAttr = styling.intensity.attribute;
    const cAttr = styling.categorical.attribute;
    if (iAttr && cAttr && iAttr === cAttr) {
      push('settings.extra_cfg.styling.links.categorical.attribute',
        `Conflicts with intensity.attribute — both target "${iAttr}".`);
    }
  }

  // ── 7. DisplayAttribute.attribute_class — inner name/type must be unset ─
  const das = (CONFIG.settings && CONFIG.settings.extra_cfg && CONFIG.settings.extra_cfg.display_attribute) || [];
  das.forEach((da, idx) => {
    if (!da || !da.attribute_class) return;
    if (da.attribute_class.name) {
      push(`settings.extra_cfg.display_attribute[${idx}].attribute_class.name`,
        `Inner attribute_class.name must be unset; the sibling AC is auto-named from attribute_name.`);
    }
    if (da.attribute_class.type) {
      push(`settings.extra_cfg.display_attribute[${idx}].attribute_class.type`,
        `Inner attribute_class.type must be unset; the sibling AC is auto-typed text.`);
    }
  });

  // ── 8. Display sources must reference a registered AC name ────────────
  for (const sec of ['display_attribute', 'display_label']) {
    const entries = (CONFIG.settings && CONFIG.settings.extra_cfg && CONFIG.settings.extra_cfg[sec]) || [];
    entries.forEach((entry, eIdx) => {
      if (!entry || !Array.isArray(entry.sources)) return;
      entry.sources.forEach((src, sIdx) => {
        if (src && src.attribute && acByName.size && !acByName.has(src.attribute)) {
          push(`settings.extra_cfg.${sec}[${eIdx}].sources[${sIdx}].attribute`,
            `AttributeClass "${src.attribute}" is not registered.`);
        }
      });
    });
  }

  // ── 9. display_attribute / display_label `.type` must reference a
  // registered entity_type / link_type name. When kind is 'entity', check
  // entity_types only; 'link' → link_types only; 'both' (default) → either.
  for (const sec of ['display_attribute', 'display_label']) {
    const entries = (CONFIG.settings && CONFIG.settings.extra_cfg && CONFIG.settings.extra_cfg[sec]) || [];
    entries.forEach((entry, eIdx) => {
      if (!entry || !entry.type) return;
      const kind = entry.kind || 'both';
      let ok = false;
      let where = '';
      if (kind === 'entity') { ok = etNames.has(entry.type); where = 'entity_types'; }
      else if (kind === 'link') { ok = ltNames.has(entry.type); where = 'link_types'; }
      else { ok = etNames.has(entry.type) || ltNames.has(entry.type); where = 'entity_types or link_types'; }
      if (!ok) {
        push(`settings.extra_cfg.${sec}[${eIdx}].type`,
          `Type "${entry.type}" is not registered in ${where}.`);
      }
    });
  }

  // ── 10. Value enforcement (1.17.0) ─────────────────────────────────────

  // 10a. AttributeClass.enforce — pattern XOR allowed_values; description
  // required when pattern is set; pattern must be a valid regex.
  acs.forEach((ac, idx) => {
    if (!ac || !ac.enforce) return;
    const enf = ac.enforce;
    const hasPattern = enf.pattern != null && enf.pattern !== '';
    const hasAllowed = Array.isArray(enf.allowed_values) && enf.allowed_values.length > 0;
    if (hasPattern && hasAllowed) {
      push(`attribute_classes[${idx}].enforce`,
        `enforce: set exactly one of 'pattern' or 'allowed_values', not both.`);
    }
    if (hasPattern && !enf.description) {
      push(`attribute_classes[${idx}].enforce.description`,
        `enforce.description is required when pattern is set.`);
    }
    if (hasPattern) {
      try { new RegExp(enf.pattern); }
      catch (e) {
        push(`attribute_classes[${idx}].enforce.pattern`,
          `Invalid regex: ${e.message}`);
      }
    }
  });

  // 10b. EntityType.enforce — id_pattern needs id_pattern_description; regex valid.
  (CONFIG.entity_types || []).forEach((et, idx) => {
    if (!et || !et.enforce) return;
    const enf = et.enforce;
    if (enf.id_pattern) {
      if (!enf.id_pattern_description) {
        push(`entity_types[${idx}].enforce.id_pattern_description`,
          `id_pattern_description is required when id_pattern is set.`);
      }
      try { new RegExp(enf.id_pattern); }
      catch (e) {
        push(`entity_types[${idx}].enforce.id_pattern`,
          `Invalid regex: ${e.message}`);
      }
    }
  });

  // 10c. LinkType.enforce — same id_pattern/description coupling.
  (CONFIG.link_types || []).forEach((lt, idx) => {
    if (!lt || !lt.enforce) return;
    const enf = lt.enforce;
    if (enf.id_pattern) {
      if (!enf.id_pattern_description) {
        push(`link_types[${idx}].enforce.id_pattern_description`,
          `id_pattern_description is required when id_pattern is set.`);
      }
      try { new RegExp(enf.id_pattern); }
      catch (e) {
        push(`link_types[${idx}].enforce.id_pattern`,
          `Invalid regex: ${e.message}`);
      }
    }
  });

  // 10d. Top-level validators[]. Exactly one of entity_type/link_type;
  // exactly one of pattern/allowed_values; description required for pattern;
  // attribute='id' reserved; referenced types must be registered;
  // no duplicate synthesized keys; pattern must compile.
  const validators = Array.isArray(CONFIG.validators) ? CONFIG.validators : [];
  const seenKeys = new Map();
  validators.forEach((v, idx) => {
    if (!v) return;
    const hasET = !!v.entity_type;
    const hasLT = !!v.link_type;
    if (hasET === hasLT) {
      push(`validators[${idx}]`,
        `Set exactly one of 'entity_type' or 'link_type'.`);
      return;
    }
    if (!v.attribute) {
      push(`validators[${idx}].attribute`, `attribute is required.`);
      return;
    }
    if (v.attribute === 'id') {
      push(`validators[${idx}].attribute`,
        `'id' is reserved — use EntityType.enforce.id_pattern (or LinkType.enforce.id_pattern) for identity rules.`);
      return;
    }
    const hasPattern = v.pattern != null && v.pattern !== '';
    const hasAllowed = Array.isArray(v.allowed_values) && v.allowed_values.length > 0;
    if (hasPattern === hasAllowed) {
      push(`validators[${idx}]`,
        `Set exactly one of 'pattern' or 'allowed_values'.`);
    }
    if (hasPattern && !v.description) {
      push(`validators[${idx}].description`,
        `description is required when pattern is set.`);
    }
    if (hasPattern) {
      try { new RegExp(v.pattern); }
      catch (e) {
        push(`validators[${idx}].pattern`, `Invalid regex: ${e.message}`);
      }
    }
    const targetName = v.entity_type || v.link_type;
    const targetRegistry = hasET ? etNames : ltNames;
    if (targetName && !targetRegistry.has(targetName)) {
      push(`validators[${idx}].${hasET ? 'entity_type' : 'link_type'}`,
        `${hasET ? 'Entity' : 'Link'} type "${targetName}" is not registered.`);
    }
    const key = `${hasET ? 'E' : 'L'}::${targetName}::${v.attribute}`;
    if (seenKeys.has(key)) {
      push(`validators[${idx}]`,
        `Duplicate validator scope "${key}" (first at #${seenKeys.get(key) + 1}).`);
    } else {
      seenKeys.set(key, idx);
    }
  });

  // ── Custom icons: a config must carry baked icons only ───────────────
  // Mirrors the library's config Pillow gate. An in-browser-baked icon is a
  // data:image/bmp URI (or a compiled data/datalength entry); anything else
  // (a path, PNG, data:image/png) must be baked first.
  for (const section of ['custom_entity_icons', 'custom_attribute_icons']) {
    const list = CONFIG[section];
    if (!Array.isArray(list)) continue;
    list.forEach((entry, idx) => {
      if (!entry || typeof entry !== 'object') return;
      if (!entry.name) push(`${section}[${idx}].name`, 'Icon name is required.');
      const baked = (entry.data !== undefined && entry.datalength !== undefined) ||
        (typeof entry.image === 'string' && entry.image.startsWith('data:image/bmp'));
      if (!baked) {
        push(`${section}[${idx}].image`,
          'Icon must be baked (a data:image/bmp URI). Pick the image again to bake it in-browser.');
      }
    });
  }

  return errors;
};

// anxwritter config builder — single-page form driven by schema.js.
//
// Source of truth: schema.js (loaded via <script> so the page works from
// file:// too — fetch() is blocked on local files). This file knows how to
// render forms from it but does NOT hard-code field lists.
// tests/test_ui_schema_sync.py keeps the schema in sync with the library.

'use strict';

// Single source of truth for "which sections belong to which macro group".
// Both the sidebar buildNav and the main-panel renderAll iterate this so the
// two stay in lock-step automatically.
const MACRO_GROUPS = [
  { label: 'Chart',
    sections: ['settings', 'extra_cfg'] },
  { label: 'Types & schema',
    sections: ['entity_types', 'link_types', 'attribute_classes', 'datetime_formats'] },
  { label: 'Reliability',
    sections: ['strengths', 'grades_one', 'grades_two', 'grades_three', 'source_types'] },
  { label: 'UI panels',
    sections: ['palettes', 'legend_items'] },
  { label: 'Semantic catalogue',
    sections: ['semantic_entities', 'semantic_links', 'semantic_properties'] },
];

// Flat order — derived from MACRO_GROUPS so it can't drift.
const SECTION_ORDER = MACRO_GROUPS.flatMap(g => g.sections);

const SECTION_LABEL = {
  settings: 'Settings',
  extra_cfg: 'Extra cfg',
  entity_types: 'Entity types',
  link_types: 'Link types',
  attribute_classes: 'Attribute classes',
  strengths: 'Strengths',
  datetime_formats: 'Date/time formats',
  palettes: 'Palettes',
  grades_one: 'Grades (one)',
  grades_two: 'Grades (two)',
  grades_three: 'Grades (three)',
  source_types: 'Source types',
  legend_items: 'Legend items',
  semantic_entities: 'Semantic entities',
  semantic_links: 'Semantic links',
  semantic_properties: 'Semantic properties',
};

const SECTION_HINT = {
  settings: 'Chart-wide ANB settings: appearance, fonts, view, grid, wiring, links, time, summary metadata, legend.',
  extra_cfg: 'anxwritter-only knobs (NOT written to ANX XML): auto-color, layout algorithm, geo_map, data-driven link styling, display synthesizers.',
  entity_types: 'Pre-defined entity types with icon, color, and representation. Referenced from data by name.',
  link_types: 'Pre-defined link types with color. Referenced from data by name.',
  attribute_classes: 'Named attribute schema (type, prefix/suffix, formatting). Referenced by data attributes by name.',
  strengths: 'Named line dash/dot styles for entity borders and links. The default applies when an item omits its strength.',
  datetime_formats: 'Named date/time display formats referenced by the datetime_format field on entities/links.',
  palettes: 'ANB "Insert from Palette" panel entries.',
  grades_one: 'Source-reliability grade labels (e.g. Always reliable…Unreliable). Items are referenced by index or name.',
  grades_two: 'Information-reliability grade labels (e.g. Confirmed…Doubtful).',
  grades_three: 'Third grading dimension (optional).',
  source_types: 'Free-text labels for the SourceType field dropdown.',
  legend_items: 'Custom rows shown in the legend (requires settings.legend_cfg.show=true).',
  semantic_entities: 'Custom entity semantic types for the embedded i2 LibraryCatalogue.',
  semantic_links: 'Custom link semantic types.',
  semantic_properties: 'Custom property semantic types (attribute schema).',
};

// Virtual sections: UI-only top-level entries that don't exist in the schema's
// `sections` map. They re-target a different slice of CONFIG than the section
// name implies. Currently only `extra_cfg` — promoted from `settings.extra_cfg`
// to a sibling of `settings` in the UI, while the YAML still writes/reads
// `settings.extra_cfg` correctly.
const VIRTUAL_SECTIONS = {
  extra_cfg: { ref: 'ExtraCfg', virtual: true },
};

// Fields a section's dataclass should NOT render at its top level — used to
// hoist the extra_cfg field out of Settings so it becomes its own section.
const SECTION_FIELD_EXCLUDES = {
  settings: ['extra_cfg'],
};

function getSectionSpec(id) {
  return (SCHEMA && SCHEMA.sections && SCHEMA.sections[id]) || VIRTUAL_SECTIONS[id] || null;
}

let SCHEMA = null;
let CONFIG = {};  // in-memory state — gets serialized to YAML

// ── Auto-save (localStorage) ───────────────────────────────────────────
// Key is suffixed with the schema version so a future schema bump
// invalidates stale stored configs automatically instead of mis-rendering.
const AUTOSAVE_KEY_BASE = 'anxwritter.config';
let AUTOSAVE_AVAILABLE = true;
let AUTOSAVE_DEBOUNCE = null;
let LAST_SAVED_AT = null;

function autosaveKey() {
  const v = (SCHEMA && SCHEMA._meta && SCHEMA._meta.schemaVersion) || 'v0';
  return `${AUTOSAVE_KEY_BASE}.v${v}`;
}

function loadFromAutosave() {
  try {
    const raw = localStorage.getItem(autosaveKey());
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
  } catch (e) {
    AUTOSAVE_AVAILABLE = false;
  }
  return null;
}

function scheduleAutosave() {
  if (!AUTOSAVE_AVAILABLE) return;
  if (AUTOSAVE_DEBOUNCE) clearTimeout(AUTOSAVE_DEBOUNCE);
  updateAutosavePill('saving');
  AUTOSAVE_DEBOUNCE = setTimeout(() => {
    AUTOSAVE_DEBOUNCE = null;
    try {
      const cleaned = pruneEmpty(CONFIG);
      if (cleaned === undefined) {
        localStorage.removeItem(autosaveKey());
      } else {
        localStorage.setItem(autosaveKey(), JSON.stringify(cleaned));
      }
      LAST_SAVED_AT = Date.now();
      updateAutosavePill('saved');
    } catch (e) {
      AUTOSAVE_AVAILABLE = false;
      updateAutosavePill('off');
    }
  }, 300);
}

function clearAutosave() {
  try { localStorage.removeItem(autosaveKey()); } catch (e) { /* ignore */ }
  LAST_SAVED_AT = null;
  updateAutosavePill('empty');
}

function updateAutosavePill(state) {
  const pill = document.getElementById('autosave-pill');
  if (!pill) return;
  if (!AUTOSAVE_AVAILABLE) { pill.textContent = 'Auto-save off'; pill.className = 'pill autosave off'; return; }
  if (state === 'saving') { pill.textContent = 'Saving…'; pill.className = 'pill autosave saving'; return; }
  if (state === 'empty')  { pill.textContent = 'Auto-save ready'; pill.className = 'pill autosave'; return; }
  // 'saved' or periodic tick — show "Saved Xs ago"
  if (LAST_SAVED_AT === null) { pill.textContent = 'Auto-save ready'; pill.className = 'pill autosave'; return; }
  const sec = Math.max(0, Math.floor((Date.now() - LAST_SAVED_AT) / 1000));
  pill.textContent = sec < 5 ? 'Saved' : sec < 60 ? `Saved ${sec}s ago` : `Saved ${Math.floor(sec / 60)}m ago`;
  pill.className = 'pill autosave saved';
}

// ── Boot ────────────────────────────────────────────────────────────────

(function init() {
  SCHEMA = window.SCHEMA;
  if (!SCHEMA) {
    document.body.innerHTML =
      '<p style="padding:20px;color:#c53030">' +
      'schema.js failed to load (window.SCHEMA is undefined). ' +
      'Make sure schema.js sits next to index.html.</p>';
    return;
  }
  document.getElementById('meta-version').textContent =
    `anxwritter ${SCHEMA._meta.anxwritterVersion}`;

  // Restore from auto-save before first render so the form paints with data.
  const restored = loadFromAutosave();
  if (restored) {
    CONFIG = restored;
    LAST_SAVED_AT = Date.now();  // pretend we just saved; user sees "Saved"
  }
  updateAutosavePill(restored ? 'saved' : 'empty');
  // Keep the "Saved Xs ago" label ticking. Cheap (every 5s, one textContent write).
  setInterval(() => { if (LAST_SAVED_AT !== null) updateAutosavePill('saved'); }, 5000);

  buildNav();
  renderAll();

  // Any input/change anywhere in the form refreshes the dots AND re-applies
  // hide-unset if it's on. Click events too — adding/removing list rows
  // fires `click`, not `input`.
  const root = document.getElementById('form-root');
  root.addEventListener('input', refreshUI);
  root.addEventListener('change', refreshUI);
  root.addEventListener('click', refreshUI);

  const hideBtn = document.getElementById('btn-hide-unset');
  hideBtn.addEventListener('click', () => {
    const on = document.body.classList.toggle('hide-unset');
    hideBtn.textContent = on ? 'Show all' : 'Hide unset';
    hideBtn.classList.toggle('primary', on);
    refreshUI();
  });

  // Bulk open/close everything that can collapse — main-panel macro groups,
  // sections, nested blocks, rows, and the sidebar's nav groups + sub-navs.
  // The `<details>` selector covers macro-group, section, nested-details, row,
  // and nav-group. The `.sub-nav` is a <div> with an .expanded class so it
  // needs its own toggle.
  const setAll = (open) => {
    document.querySelectorAll('details').forEach(d => { d.open = open; });
    document.querySelectorAll('.sub-nav').forEach(s => s.classList.toggle('expanded', open));
    document.querySelectorAll('.sidebar a.has-sub').forEach(a => a.classList.toggle('expanded', open));
  };
  document.getElementById('btn-collapse-all').addEventListener('click', () => setAll(false));
  document.getElementById('btn-expand-all').addEventListener('click', () => setAll(true));

  const filterInput = document.getElementById('form-filter');
  filterInput.addEventListener('input', () => {
    if (FILTER_DEBOUNCE) clearTimeout(FILTER_DEBOUNCE);
    FILTER_DEBOUNCE = setTimeout(() => applyFilter(filterInput.value), 100);
  });
  filterInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { filterInput.value = ''; applyFilter(''); }
  });

  document.getElementById('btn-download').addEventListener('click', downloadYaml);
  document.getElementById('btn-reset').addEventListener('click', () => {
    if (!confirm('Reset all fields to empty? (this also wipes the saved copy in your browser)')) return;
    CONFIG = {};
    clearAutosave();
    renderAll();
  });

  const importBtn = document.getElementById('btn-import');
  const importInput = document.getElementById('import-file');
  importBtn.addEventListener('click', () => importInput.click());
  importInput.addEventListener('change', () => {
    const file = importInput.files && importInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      importInput.value = '';  // allow re-importing the same filename
      importYamlText(e.target.result, file.name);
    };
    reader.onerror = () => {
      importInput.value = '';
      alert(`Could not read ${file.name}`);
    };
    reader.readAsText(file);
  });
})();

// ── Navigation sidebar ──────────────────────────────────────────────────

function buildNav() {
  const nav = document.getElementById('section-nav');

  // Each macro group ("CHART", "TYPES & SCHEMA", …) is its own collapsible
  // <details> with the label as the summary. Default closed.
  const group = (label, items) => {
    const det = document.createElement('details');
    det.className = 'nav-group';
    const sum = document.createElement('summary');
    sum.className = 'group-label';
    sum.textContent = label;
    det.appendChild(sum);
    for (const el of items) det.appendChild(el);
    return det;
  };

  const link = (id, label) => {
    const a = document.createElement('a');
    a.href = `#sec-${id}`;
    a.textContent = label;
    a.addEventListener('click', (e) => {
      // Auto-open the target section AND its containing macro group so
      // the click reveals content even when everything's collapsed.
      const sec = document.getElementById(`sec-${id}`);
      if (sec) {
        const macro = sec.closest('details.macro-group');
        if (macro) macro.open = true;
        if (sec.tagName === 'DETAILS') sec.open = true;
      }
      // smooth scroll handled by browser; just update active state
      setTimeout(() => updateActiveNav(id), 50);
    });
    return a;
  };

  // For sections whose ref-def has ref-typed sub-fields (currently just
  // `settings`), build an indented sub-list under the parent link.
  // Clicking the parent toggles the sub-list AND still navigates.
  // Clicking a sub-link opens both the section and the specific nested
  // block, then the native anchor scroll lands on it.
  const linkWithSubs = (id, label) => {
    const sectionSpec = getSectionSpec(id);
    const def = sectionSpec && sectionSpec.ref ? SCHEMA.definitions[sectionSpec.ref] : null;
    const excludes = SECTION_FIELD_EXCLUDES[id] || [];
    const subFields = def
      ? def.fields.filter(f => f.ref && !excludes.includes(f.name))
      : [];
    const parentA = link(id, label);
    if (subFields.length === 0) return [parentA];

    parentA.classList.add('has-sub');
    const subList = document.createElement('div');
    subList.className = 'sub-nav';

    for (const field of subFields) {
      const targetId = `sec-${id}-${field.name}`;
      const subA = document.createElement('a');
      subA.className = 'sub-link';
      subA.href = `#${targetId}`;
      subA.textContent = field.name;
      subA.addEventListener('click', () => {
        // Open the containing macro group, the section, and the nested block.
        const sec = document.getElementById(`sec-${id}`);
        if (sec) {
          const macro = sec.closest('details.macro-group');
          if (macro) macro.open = true;
          if (sec.tagName === 'DETAILS') sec.open = true;
        }
        const sub = document.getElementById(targetId);
        if (sub && sub.tagName === 'DETAILS') sub.open = true;
        document.querySelectorAll('.sub-nav a').forEach(a => a.classList.remove('active'));
        subA.classList.add('active');
      });
      subList.appendChild(subA);
    }

    parentA.addEventListener('click', () => {
      const expanded = subList.classList.toggle('expanded');
      parentA.classList.toggle('expanded', expanded);
    });
    return [parentA, subList];
  };

  for (const g of MACRO_GROUPS) {
    const items = [];
    for (const id of g.sections) {
      // linkWithSubs returns [link] when the section has no ref sub-fields,
      // or [link, subList] when it does (currently only `settings`).
      items.push(...linkWithSubs(id, SECTION_LABEL[id]));
    }
    nav.appendChild(group(g.label, items));
  }
}

function updateActiveNav(activeId) {
  document.querySelectorAll('.sidebar a').forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === `#sec-${activeId}`);
  });
}

// ── Top-level render ────────────────────────────────────────────────────

function renderAll() {
  const root = document.getElementById('form-root');
  root.innerHTML = '';

  for (const g of MACRO_GROUPS) {
    const macro = document.createElement('details');
    macro.className = 'macro-group';
    macro.id = `macro-${g.label.toLowerCase().replace(/[\s&]+/g, '-')}`;

    const summary = document.createElement('summary');
    const h = document.createElement('h2');
    h.textContent = g.label;
    const issues = document.createElement('span');
    issues.className = 'issue-count';
    h.appendChild(issues);
    const count = document.createElement('span');
    count.className = 'field-count';
    h.appendChild(count);
    const hidden = document.createElement('span');
    hidden.className = 'hidden-count';
    h.appendChild(hidden);
    const marker = document.createElement('span');
    marker.className = 'set-marker';
    marker.title = 'this group has values set';
    h.appendChild(marker);
    summary.appendChild(h);
    macro.appendChild(summary);

    for (const sectionName of g.sections) {
      const sec = getSectionSpec(sectionName);
      if (!sec) continue;
      macro.appendChild(renderSection(sectionName, sec));
    }

    // _configRef returns a synthetic object of every section slice; pruneEmpty
    // will collapse it to undefined iff every contained section is empty.
    macro._configRef = () => {
      const out = {};
      for (const s of g.sections) out[s] = CONFIG[s];
      return out;
    };
    macro._countFn = () => {
      let set = 0, total = 0;
      for (const s of g.sections) {
        const c = countSection(s);
        set += c.set; total += c.total;
      }
      return { set, total };
    };
    macro._issueCountFn = () => {
      let n = 0;
      for (const s of g.sections) {
        const p = (s === 'extra_cfg') ? 'settings.extra_cfg' : s;
        n += (VALIDATION_PATH_COUNTS.get(p) || 0);
        const exact = VALIDATION_ERRORS_BY_PATH.get(p);
        if (exact) n += exact.length;
      }
      return n;
    };

    root.appendChild(macro);
  }

  // Placeholder shown when hide-unset is on AND the chart is fully empty.
  const empty = document.createElement('div');
  empty.id = 'empty-state';
  empty.className = 'empty-state';
  empty.textContent = 'Nothing is set. Toggle "Show all" to start filling in fields.';
  root.appendChild(empty);
  applyHideUnset();
}

function renderSection(name, spec) {
  // Top-level sections are <details> so they collapse. Default closed; the
  // dot in the summary signals "has content" without needing to expand.
  const wrap = document.createElement('details');
  wrap.className = 'section';
  wrap.id = `sec-${name}`;
  const parentPath = `sec-${name}`;

  const summary = document.createElement('summary');
  const h = document.createElement('h2');
  h.textContent = SECTION_LABEL[name] || name;
  const issues = document.createElement('span');
  issues.className = 'issue-count';
  h.appendChild(issues);
  const count = document.createElement('span');
  count.className = 'field-count';
  h.appendChild(count);
  const hidden = document.createElement('span');
  hidden.className = 'hidden-count';
  h.appendChild(hidden);
  const marker = document.createElement('span');
  marker.className = 'set-marker';
  marker.title = 'this section has values set';
  h.appendChild(marker);
  summary.appendChild(h);
  wrap.appendChild(summary);
  wrap._countFn = () => countSection(name);

  if (SECTION_HINT[name]) {
    const p = document.createElement('p');
    p.className = 'section-desc';
    p.textContent = SECTION_HINT[name];
    wrap.appendChild(p);
  }

  // Stash a getter the marker code uses to introspect this slice of CONFIG.
  // Virtual sections (currently just `extra_cfg`) point at a different slice
  // than `CONFIG[name]` so the YAML still emits the canonical structure.
  // Sections with EXCLUDED fields strip those keys from their slice so the
  // set-marker / hide-unset logic doesn't count content the section doesn't
  // even render (e.g. Settings without extra_cfg).
  if (spec.virtual && name === 'extra_cfg') {
    wrap._configRef = () => (CONFIG.settings && CONFIG.settings.extra_cfg) || undefined;
  } else if (SECTION_FIELD_EXCLUDES[name]) {
    const excl = SECTION_FIELD_EXCLUDES[name];
    wrap._configRef = () => {
      const src = CONFIG[name] || {};
      const out = {};
      for (const k of Object.keys(src)) if (!excl.includes(k)) out[k] = src[k];
      return out;
    };
  } else {
    wrap._configRef = () => CONFIG[name];
  }

  // Validation path prefix for fields rendered inside this section. For
  // virtual extra_cfg this is "settings.extra_cfg" so paths from validate.js
  // line up with the canonical YAML shape.
  const dataPath = (spec.virtual && name === 'extra_cfg') ? 'settings.extra_cfg' : name;
  wrap._configPath = dataPath;

  if (spec.virtual && name === 'extra_cfg') {
    // Virtual section: backs onto CONFIG.settings.extra_cfg so the YAML
    // download still emits the canonical `settings.extra_cfg` shape.
    ensureObject(CONFIG, 'settings');
    ensureObject(CONFIG.settings, 'extra_cfg');
    wrap.appendChild(renderDataclass(spec.ref, CONFIG.settings.extra_cfg,
      (v) => { CONFIG.settings.extra_cfg = v; }, parentPath, [], dataPath));
  } else if (spec.ref) {
    // Single nested dataclass (e.g. settings, strengths, grades_*)
    ensureObject(CONFIG, name);
    wrap.appendChild(renderDataclass(spec.ref, CONFIG[name],
      (v) => { CONFIG[name] = v; }, parentPath,
      SECTION_FIELD_EXCLUDES[name] || [], dataPath));
  } else if (spec.list_of) {
    // List of dataclasses (entity_types, link_types, …)
    if (!Array.isArray(CONFIG[name])) CONFIG[name] = [];
    wrap.appendChild(renderListOfDataclass(spec.list_of, CONFIG[name], dataPath));
  } else if (spec.type === 'list-of-text') {
    if (!Array.isArray(CONFIG[name])) CONFIG[name] = [];
    wrap.appendChild(renderListOfPrimitive(CONFIG[name], 'text'));
  } else {
    const p = document.createElement('p');
    p.textContent = `(unsupported section shape: ${JSON.stringify(spec)})`;
    wrap.appendChild(p);
  }

  updateSetMarker(wrap);
  return wrap;
}

// ── Dataclass renderer ─────────────────────────────────────────────────

function renderDataclass(defName, obj, setter, parentPath, excludeFields, dataPath) {
  const wrap = document.createElement('div');
  wrap.className = 'fields';
  const def = SCHEMA.definitions[defName];
  if (!def) {
    wrap.textContent = `(missing definition: ${defName})`;
    return wrap;
  }

  const excludes = excludeFields || [];
  for (const field of def.fields) {
    if (excludes.includes(field.name)) continue;
    wrap.appendChild(renderField(field, obj, setter, defName, parentPath, dataPath));
  }
  return wrap;
}

function renderField(field, obj, parentSetter, defName, parentPath, dataPath) {
  // ``obj`` is the dict this field lives on. The setter exists so empty
  // nested objects can be promoted to non-null on first edit.
  const wrap = document.createElement('div');
  wrap.className = 'field';
  // Used by hide-unset mode to know what slice this field owns.
  wrap._configRef = () => obj[field.name];
  // Dotted/indexed path to this field's slot in CONFIG (e.g.
  // "settings.summary.title", "entity_types[2].name"). Matches the paths
  // emitted by validate.js so the validation pass can paint badges.
  wrap._configPath = dataPath ? `${dataPath}.${field.name}` : field.name;
  // Cached substring-match haystack for the quick filter. Built once at
  // render so each keystroke doesn't re-stringify the help text.
  const helpText = (window.HELP && window.HELP[`${defName}.${field.name}`]) || '';
  wrap._searchHaystack = (field.name + ' ' + helpText).toLowerCase();

  // Nested dataclass (ref) — render inline as a collapsible block (default closed).
  if (field.ref) {
    wrap.classList.add('full');

    const det = document.createElement('details');
    det.className = 'nested-details';
    if (parentPath) det.id = `${parentPath}-${field.name}`;
    const childPath = parentPath ? `${parentPath}-${field.name}` : null;

    const summary = document.createElement('summary');
    const label = document.createElement('label');
    label.textContent = field.name + (field.required ? '' : ' (optional)');
    if (field.required) {
      const r = document.createElement('span'); r.className = 'req'; r.textContent = '*'; label.appendChild(r);
    }
    attachHelpButton(label, defName, field);
    const issues = document.createElement('span');
    issues.className = 'issue-count';
    label.appendChild(issues);
    const count = document.createElement('span');
    count.className = 'field-count';
    label.appendChild(count);
    const hidden = document.createElement('span');
    hidden.className = 'hidden-count';
    label.appendChild(hidden);
    const marker = document.createElement('span');
    marker.className = 'set-marker';
    marker.title = 'has values set';
    label.appendChild(marker);
    summary.appendChild(label);
    det.appendChild(summary);

    const nest = document.createElement('div');
    nest.className = 'nested';
    ensureObject(obj, field.name);
    const childDataPath = dataPath ? `${dataPath}.${field.name}` : field.name;
    nest.appendChild(renderDataclass(field.ref, obj[field.name], (v) => { obj[field.name] = v; }, childPath, [], childDataPath));
    det.appendChild(nest);

    det._configRef = () => obj[field.name];
    det._configPath = childDataPath;
    det._countFn = () => countDataclass(field.ref, obj[field.name] || {});
    updateSetMarker(det);

    wrap.appendChild(det);
    return wrap;
  }

  // List of nested dataclass
  if (field.list_of) {
    wrap.classList.add('full');
    const label = document.createElement('label');
    label.textContent = field.name;
    attachHelpButton(label, defName, field);
    wrap.appendChild(label);
    if (!Array.isArray(obj[field.name])) obj[field.name] = [];
    const childDataPath = dataPath ? `${dataPath}.${field.name}` : field.name;
    wrap.appendChild(renderListOfDataclass(field.list_of, obj[field.name], childDataPath));
    return wrap;
  }

  // Dict of nested dataclass (CategoricalCfg.styles)
  if (field.type === 'dict_of') {
    wrap.classList.add('full');
    const label = document.createElement('label');
    label.textContent = `${field.name} (key → ${field.value_ref})`;
    attachHelpButton(label, defName, field);
    wrap.appendChild(label);
    if (typeof obj[field.name] !== 'object' || obj[field.name] === null || Array.isArray(obj[field.name])) {
      obj[field.name] = {};
    }
    wrap.appendChild(renderDictOfDataclass(field.value_ref, obj[field.name]));
    return wrap;
  }

  // Geo data — Dict<str, [lat, lon]>
  if (field.type === 'geo_data') {
    wrap.classList.add('full');
    const label = document.createElement('label');
    label.textContent = `${field.name} (place → [lat, lon])`;
    attachHelpButton(label, defName, field);
    wrap.appendChild(label);
    if (typeof obj[field.name] !== 'object' || obj[field.name] === null || Array.isArray(obj[field.name])) {
      obj[field.name] = {};
    }
    wrap.appendChild(renderGeoData(obj[field.name]));
    return wrap;
  }

  // Lists of primitives
  if (field.type === 'list-of-text' || field.type === 'list-of-number' || field.type === 'list-of-color') {
    wrap.classList.add('full');
    const label = document.createElement('label');
    label.textContent = field.name;
    attachHelpButton(label, defName, field);
    wrap.appendChild(label);
    if (!Array.isArray(obj[field.name])) obj[field.name] = [];
    const primKind = field.type === 'list-of-number' ? 'number' : 'text';
    wrap.appendChild(renderListOfPrimitive(obj[field.name], primKind));
    return wrap;
  }

  // Standard label
  const label = document.createElement('label');
  label.textContent = field.name;
  if (field.required) {
    const r = document.createElement('span'); r.className = 'req'; r.textContent = '*'; label.appendChild(r);
  }
  attachHelpButton(label, defName, field);
  wrap.appendChild(label);

  // Enum (datalist for typeahead, but accept any value)
  if (field.enum) {
    const inp = renderEnumInput(field, obj);
    appendInputWithClear(wrap, obj, field, inp);
    return wrap;
  }

  if (field.type === 'select') {
    const sel = document.createElement('select');
    const blank = document.createElement('option');
    blank.value = ''; blank.textContent = '— unset —';
    sel.appendChild(blank);
    for (const opt of (field.options || [])) {
      const o = document.createElement('option');
      o.value = opt; o.textContent = opt;
      sel.appendChild(o);
    }
    sel.value = obj[field.name] ?? '';
    sel.addEventListener('input', () => {
      obj[field.name] = sel.value === '' ? null : sel.value;
      markUnset(sel);
    });
    markUnset(sel);
    appendInputWithClear(wrap, obj, field, sel);
    return wrap;
  }

  if (field.type === 'bool') {
    wrap.appendChild(renderTriStateBool(field, obj));
    return wrap;
  }

  if (field.type === 'color') {
    const inp = renderColorInput(field, obj);
    appendInputWithClear(wrap, obj, field, inp);
    return wrap;
  }

  if (field.type === 'number') {
    const inp = document.createElement('input');
    inp.type = 'number';
    inp.step = 'any';
    if (obj[field.name] !== undefined && obj[field.name] !== null) inp.value = obj[field.name];
    inp.addEventListener('input', () => {
      const v = inp.value;
      obj[field.name] = v === '' ? null : Number(v);
      markUnset(inp);
    });
    markUnset(inp);
    appendInputWithClear(wrap, obj, field, inp);
    return wrap;
  }

  if (field.type === 'any') {
    // Free-form — accept JSON-ish input
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.placeholder = 'e.g. robust, [0, 100], or leave blank';
    if (obj[field.name] !== undefined && obj[field.name] !== null) {
      inp.value = typeof obj[field.name] === 'string' ? obj[field.name] : JSON.stringify(obj[field.name]);
    }
    inp.addEventListener('input', () => {
      const v = inp.value.trim();
      if (v === '') { obj[field.name] = null; markUnset(inp); return; }
      try { obj[field.name] = JSON.parse(v); }
      catch { obj[field.name] = v; }
      markUnset(inp);
    });
    markUnset(inp);
    appendInputWithClear(wrap, obj, field, inp);
    return wrap;
  }

  // default: text
  const inp = document.createElement('input');
  inp.type = 'text';
  if (obj[field.name] !== undefined && obj[field.name] !== null) inp.value = obj[field.name];
  inp.addEventListener('input', () => {
    obj[field.name] = inp.value === '' ? null : inp.value;
    markUnset(inp);
  });
  markUnset(inp);
  appendInputWithClear(wrap, obj, field, inp);
  return wrap;
}

function renderEnumInput(field, obj) {
  const inp = document.createElement('input');
  inp.type = 'text';
  inp.setAttribute('list', `enum-${field.enum}`);
  if (obj[field.name] !== undefined && obj[field.name] !== null) inp.value = obj[field.name];
  inp.placeholder = `${field.enum} — type or pick`;
  inp.addEventListener('input', () => {
    obj[field.name] = inp.value === '' ? null : inp.value;
    markUnset(inp);
  });
  markUnset(inp);
  // datalist (one per enum, dedup via id)
  if (!document.getElementById(`enum-${field.enum}`)) {
    const dl = document.createElement('datalist');
    dl.id = `enum-${field.enum}`;
    for (const v of (SCHEMA.enums[field.enum] || [])) {
      const o = document.createElement('option');
      o.value = v;
      dl.appendChild(o);
    }
    document.body.appendChild(dl);
  }
  return inp;
}

function renderColorInput(field, obj) {
  const inp = document.createElement('input');
  inp.type = 'text';
  inp.setAttribute('list', 'enum-Color');
  if (obj[field.name] !== undefined && obj[field.name] !== null) inp.value = obj[field.name];
  inp.placeholder = 'name / #RRGGBB / COLORREF int';
  inp.addEventListener('input', () => {
    const v = inp.value.trim();
    if (v === '') { obj[field.name] = null; markUnset(inp); syncColorSwatch(swatch, null); return; }
    // COLORREF integer
    if (/^\d+$/.test(v)) obj[field.name] = parseInt(v, 10);
    else obj[field.name] = v;
    markUnset(inp);
    syncColorSwatch(swatch, obj[field.name]);
  });
  markUnset(inp);
  // re-use the Color datalist if not already created
  if (!document.getElementById('enum-Color')) {
    const dl = document.createElement('datalist');
    dl.id = 'enum-Color';
    for (const v of (SCHEMA.enums.Color || [])) {
      const o = document.createElement('option');
      o.value = v;
      dl.appendChild(o);
    }
    document.body.appendChild(dl);
  }
  // Swatch lives in .input-row next to the input; appendInputWithClear sees
  // inp._extraEl and threads it in. Initial state reflects the loaded value.
  const swatch = document.createElement('span');
  swatch.className = 'color-swatch';
  syncColorSwatch(swatch, obj[field.name]);
  inp._extraEl = swatch;
  return inp;
}

// Paint a swatch from any color value the library accepts. When the value is
// unset or unparseable, the swatch shows a checker pattern so the user sees
// "no valid color" instead of an invisible white square.
function syncColorSwatch(swatch, value) {
  const hex = (window.resolveColorToHex && window.resolveColorToHex(value)) || null;
  if (hex) {
    swatch.style.setProperty('--swatch-color', hex);
    swatch.classList.add('has-color');
    swatch.title = `Resolved: ${hex}`;
  } else {
    swatch.style.removeProperty('--swatch-color');
    swatch.classList.remove('has-color');
    swatch.title = value ? 'Unrecognised color' : 'No color set';
  }
}

// ── List of dataclasses (repeated rows) ────────────────────────────────

function renderListOfDataclass(defName, list, dataPath) {
  const wrap = document.createElement('div');
  const rowContainer = document.createElement('div');
  wrap.appendChild(rowContainer);

  // openIdx: index of a row to auto-expand on rebuild (newly added or
  // just-duplicated). Existing rows stay in their default-collapsed state.
  const rebuild = (openIdx) => {
    rowContainer.innerHTML = '';
    list.forEach((item, idx) => {
      const row = renderRow(defName, item, idx, list, rebuild, dataPath);
      if (idx === openIdx) row.open = true;
      rowContainer.appendChild(row);
    });
  };
  rebuild();

  const addBtn = document.createElement('button');
  addBtn.className = 'ghost add-row';
  addBtn.type = 'button';
  addBtn.textContent = `+ Add ${defName}`;
  addBtn.addEventListener('click', () => {
    list.push({});
    rebuild(list.length - 1);
  });
  wrap.appendChild(addBtn);
  return wrap;
}

function renderRow(defName, obj, idx, parentList, rebuild, dataPath) {
  const row = document.createElement('details');
  row.className = 'row';
  row._configRef = () => obj;  // for hide-unset visibility AND has-content dot
  const rowPath = dataPath ? `${dataPath}[${idx}]` : `[${idx}]`;
  row._configPath = rowPath;

  const head = document.createElement('summary');
  head.className = 'row-head';

  const titleText = () =>
    `${defName} #${idx + 1}` +
    (obj.name ? ` — ${obj.name}` : (obj.key ? ` — ${obj.key}` : ''));

  const title = document.createElement('div');
  title.className = 'row-title';
  const titleLabel = document.createElement('span');
  titleLabel.className = 'row-title-label';
  titleLabel.textContent = titleText();
  title.appendChild(titleLabel);
  const issues = document.createElement('span');
  issues.className = 'issue-count';
  title.appendChild(issues);
  const count = document.createElement('span');
  count.className = 'field-count';
  title.appendChild(count);
  const hidden = document.createElement('span');
  hidden.className = 'hidden-count';
  title.appendChild(hidden);
  const marker = document.createElement('span');
  marker.className = 'set-marker';
  marker.title = 'this row has values set';
  title.appendChild(marker);
  head.appendChild(title);
  row._countFn = () => countDataclass(defName, obj);

  const actions = document.createElement('div');
  actions.className = 'row-actions';

  // Action buttons inside <summary> shouldn't toggle the details on click.
  // Most browsers do the right thing for <button>, but stopPropagation is
  // the bullet-proof guard.
  const dup = document.createElement('button');
  dup.type = 'button';
  dup.textContent = 'Duplicate';
  dup.addEventListener('click', (e) => {
    e.stopPropagation();
    parentList.splice(idx + 1, 0, JSON.parse(JSON.stringify(obj)));
    rebuild(idx + 1);  // auto-expand the duplicate
  });

  const del = document.createElement('button');
  del.className = 'danger';
  del.type = 'button';
  del.textContent = 'Remove';
  del.addEventListener('click', (e) => {
    e.stopPropagation();
    parentList.splice(idx, 1);
    rebuild();
  });

  actions.appendChild(dup);
  actions.appendChild(del);
  head.appendChild(actions);
  row.appendChild(head);

  // body
  const body = renderDataclass(defName, obj, () => {}, null, [], rowPath);
  row.appendChild(body);

  // Live-update the title when name/key changes; the marker dot is untouched.
  body.addEventListener('input', () => {
    titleLabel.textContent = titleText();
  });

  return row;
}

// ── Dict<str, Dataclass> (CategoricalCfg.styles) ───────────────────────

function renderDictOfDataclass(valueDefName, dict) {
  const wrap = document.createElement('div');
  const inner = document.createElement('div');
  wrap.appendChild(inner);

  const rebuild = () => {
    inner.innerHTML = '';
    for (const key of Object.keys(dict)) {
      const row = document.createElement('div');
      row.className = 'row';

      const head = document.createElement('div');
      head.className = 'row-head';

      const keyInput = document.createElement('input');
      keyInput.type = 'text';
      keyInput.value = key;
      keyInput.placeholder = 'attribute value (e.g. Witness)';
      keyInput.style.width = '60%';

      keyInput.addEventListener('blur', () => {
        const newKey = keyInput.value.trim();
        if (newKey && newKey !== key && !(newKey in dict)) {
          dict[newKey] = dict[key];
          delete dict[key];
          rebuild();
        } else if (!newKey) {
          keyInput.value = key;
        }
      });

      const actions = document.createElement('div');
      actions.className = 'row-actions';
      const del = document.createElement('button');
      del.className = 'danger';
      del.type = 'button';
      del.textContent = 'Remove';
      del.addEventListener('click', () => {
        delete dict[key];
        rebuild();
      });
      actions.appendChild(del);

      head.appendChild(keyInput);
      head.appendChild(actions);
      row.appendChild(head);

      row.appendChild(renderDataclass(valueDefName, dict[key], () => {}));
      inner.appendChild(row);
    }
  };
  rebuild();

  const add = document.createElement('button');
  add.type = 'button';
  add.className = 'ghost add-row';
  add.textContent = '+ Add entry';
  add.addEventListener('click', () => {
    let n = 1;
    while ((`entry_${n}`) in dict) n++;
    dict[`entry_${n}`] = {};
    rebuild();
  });
  wrap.appendChild(add);
  return wrap;
}

// ── Geo data (Dict<str, [lat, lon]>) ───────────────────────────────────

function renderGeoData(dict) {
  const wrap = document.createElement('div');
  const inner = document.createElement('div');
  wrap.appendChild(inner);

  const rebuild = () => {
    inner.innerHTML = '';
    for (const key of Object.keys(dict)) {
      const row = document.createElement('div');
      row.style.display = 'flex'; row.style.gap = '4px'; row.style.marginBottom = '4px';

      const keyInput = document.createElement('input');
      keyInput.type = 'text';
      keyInput.value = key;
      keyInput.placeholder = 'place name';
      keyInput.style.flex = '2';

      const latInput = document.createElement('input');
      latInput.type = 'number'; latInput.step = 'any';
      latInput.placeholder = 'lat';
      latInput.value = (dict[key] || [])[0] ?? '';
      latInput.style.flex = '1';

      const lonInput = document.createElement('input');
      lonInput.type = 'number'; lonInput.step = 'any';
      lonInput.placeholder = 'lon';
      lonInput.value = (dict[key] || [])[1] ?? '';
      lonInput.style.flex = '1';

      const del = document.createElement('button');
      del.type = 'button'; del.className = 'danger';
      del.textContent = '×';
      del.addEventListener('click', () => { delete dict[key]; rebuild(); });

      const sync = () => {
        const lat = latInput.value === '' ? null : Number(latInput.value);
        const lon = lonInput.value === '' ? null : Number(lonInput.value);
        dict[key] = [lat, lon];
      };
      latInput.addEventListener('input', sync);
      lonInput.addEventListener('input', sync);

      keyInput.addEventListener('blur', () => {
        const newKey = keyInput.value.trim();
        if (newKey && newKey !== key && !(newKey in dict)) {
          dict[newKey] = dict[key];
          delete dict[key];
          rebuild();
        } else if (!newKey) { keyInput.value = key; }
      });

      row.appendChild(keyInput);
      row.appendChild(latInput);
      row.appendChild(lonInput);
      row.appendChild(del);
      inner.appendChild(row);
    }
  };
  rebuild();

  const add = document.createElement('button');
  add.type = 'button'; add.className = 'ghost add-row';
  add.textContent = '+ Add place';
  add.addEventListener('click', () => {
    let n = 1;
    while ((`place_${n}`) in dict) n++;
    dict[`place_${n}`] = [null, null];
    rebuild();
  });
  wrap.appendChild(add);
  return wrap;
}

// ── List of primitives ──────────────────────────────────────────────────

function renderListOfPrimitive(list, kind) {
  const wrap = document.createElement('div');
  wrap.className = 'list-prim';
  const inner = document.createElement('div');
  wrap.appendChild(inner);

  const rebuild = () => {
    inner.innerHTML = '';
    list.forEach((val, idx) => {
      const item = document.createElement('div');
      item.className = 'item';
      const inp = document.createElement('input');
      inp.type = kind === 'number' ? 'number' : 'text';
      if (kind === 'number') inp.step = 'any';
      if (val !== undefined && val !== null) inp.value = val;
      inp.addEventListener('input', () => {
        list[idx] = (kind === 'number')
          ? (inp.value === '' ? null : Number(inp.value))
          : inp.value;
        markUnset(inp);
      });
      markUnset(inp);
      const del = document.createElement('button');
      del.type = 'button'; del.className = 'danger';
      del.textContent = '×';
      del.addEventListener('click', () => { list.splice(idx, 1); rebuild(); });
      item.appendChild(inp);
      item.appendChild(del);
      inner.appendChild(item);
    });
  };
  rebuild();

  const add = document.createElement('button');
  add.type = 'button'; add.className = 'ghost add-row';
  add.textContent = '+ Add';
  add.addEventListener('click', () => {
    list.push(kind === 'number' ? 0 : '');
    rebuild();
  });
  wrap.appendChild(add);
  return wrap;
}

// ── Quick filter ───────────────────────────────────────────────────────
// Substring match on field name + help text. Non-matching fields dim;
// containers dim only when no descendant field matches (so a section with
// one hit stays at full opacity while irrelevant fields fade out).

let FILTER_DEBOUNCE = null;

function applyFilter(rawQuery) {
  const query = (rawQuery || '').trim().toLowerCase();
  if (!query) {
    document.body.classList.remove('is-filtering');
    document.querySelectorAll('.filter-dim').forEach(el => el.classList.remove('filter-dim'));
    return;
  }
  document.body.classList.add('is-filtering');

  const ancestorsOfMatches = new Set();
  document.querySelectorAll('.field').forEach(f => {
    const hit = (f._searchHaystack || '').includes(query);
    f.classList.toggle('filter-dim', !hit);
    if (hit) {
      // Bubble up — any ancestor that contains a hit stays bright.
      let p = f.parentElement;
      while (p && p !== document.body) {
        ancestorsOfMatches.add(p);
        p = p.parentElement;
      }
    }
  });
  document.querySelectorAll('details.macro-group, details.section, details.nested-details, details.row')
    .forEach(c => c.classList.toggle('filter-dim', !ancestorsOfMatches.has(c)));
}

// ── Field counts ───────────────────────────────────────────────────────
// `set / total` badge in every collapsible summary. Counts primitive leaves
// only: skips list_of / dict_of / geo_data / list-of-primitives so the
// numerator/denominator stay stable across "you haven't added any rows yet."
// List-of-dataclass *sections* (entity_types etc.) instead count rows.

function countDataclass(defName, slice, excludes) {
  const def = SCHEMA && SCHEMA.definitions && SCHEMA.definitions[defName];
  if (!def) return { set: 0, total: 0 };
  const excl = excludes || [];
  let set = 0, total = 0;
  const obj = (slice && typeof slice === 'object' && !Array.isArray(slice)) ? slice : {};

  for (const field of def.fields) {
    if (excl.includes(field.name)) continue;
    const val = obj[field.name];

    if (field.ref) {
      const sub = countDataclass(field.ref, val);
      set += sub.set; total += sub.total;
    } else if (field.list_of || field.type === 'dict_of' || field.type === 'geo_data' ||
               field.type === 'list-of-text' || field.type === 'list-of-number' || field.type === 'list-of-color') {
      // Not a primitive leaf — skip per spec.
    } else {
      total++;
      if (val !== null && val !== undefined && val !== '') set++;
    }
  }
  return { set, total };
}

function countSection(name) {
  const spec = getSectionSpec(name);
  if (!spec) return { set: 0, total: 0 };
  let slice;
  if (spec.virtual && name === 'extra_cfg') {
    slice = (CONFIG.settings && CONFIG.settings.extra_cfg) || {};
  } else {
    slice = CONFIG[name];
  }
  if (spec.ref) {
    return countDataclass(spec.ref, slice || {}, SECTION_FIELD_EXCLUDES[name]);
  }
  if (spec.list_of) {
    const list = Array.isArray(slice) ? slice : [];
    return { set: list.filter(r => pruneEmpty(r) !== undefined).length, total: list.length };
  }
  if (spec.type === 'list-of-text') {
    const list = Array.isArray(slice) ? slice : [];
    return { set: list.filter(v => v !== null && v !== undefined && v !== '').length, total: list.length };
  }
  return { set: 0, total: 0 };
}

function refreshAllFieldCounts() {
  document.querySelectorAll('details.macro-group, details.section, details.nested-details, details.row')
    .forEach(updateFieldCount);
}

function updateFieldCount(detailsEl) {
  if (!detailsEl._countFn) return;
  const { set, total } = detailsEl._countFn();
  const badge = detailsEl.querySelector(':scope > summary .field-count');
  if (!badge) return;
  if (total === 0) {
    badge.textContent = '';
    badge.classList.remove('visible');
  } else {
    badge.textContent = `${set} / ${total}`;
    badge.classList.toggle('visible', true);
  }
}

// ── Collapsible "has content" markers ──────────────────────────────────

// Walk every <details> with a stashed _configRef getter and toggle its dot
// based on whether pruneEmpty() of that slice has any survivors.
function refreshAllSetMarkers() {
  document.querySelectorAll('details.macro-group, details.section, details.nested-details, details.row').forEach(updateSetMarker);
}

function updateSetMarker(detailsEl) {
  if (!detailsEl || !detailsEl._configRef) return;
  const cleaned = pruneEmpty(detailsEl._configRef());
  detailsEl.classList.toggle('has-content', cleaned !== undefined);
}

// Hide every field, row, sidebar entry, and nested-details whose slice of
// CONFIG would be omitted from the YAML download (i.e. pruneEmpty(slice) ===
// undefined). When the whole CONFIG is empty, the placeholder takes over.
// CSS hides via `.field-unset`, `.row-unset`, `.nav-hide`, plus selectors on
// `body.hide-unset details:not(.has-content)`.
function applyHideUnset() {
  const hideOn = document.body.classList.contains('hide-unset');

  document.querySelectorAll('.field').forEach(f => {
    if (!hideOn || !f._configRef) { f.classList.remove('field-unset'); return; }
    f.classList.toggle('field-unset', pruneEmpty(f._configRef()) === undefined);
  });

  document.querySelectorAll('.row').forEach(r => {
    if (!hideOn || !r._configRef) { r.classList.remove('row-unset'); return; }
    r.classList.toggle('row-unset', pruneEmpty(r._configRef()) === undefined);
  });

  // Sidebar links/sub-links that point at a section/nested-details with no
  // content get hidden. Walks the href back to its target.
  document.querySelectorAll('.sidebar a').forEach(a => {
    if (!hideOn) { a.classList.remove('nav-hide'); return; }
    const href = a.getAttribute('href');
    if (!href || !href.startsWith('#')) return;
    const target = document.getElementById(href.slice(1));
    if (!target) return;
    a.classList.toggle('nav-hide', !target.classList.contains('has-content'));
  });
  // Sub-nav and macro group: if every child link is hidden, hide the group too.
  const hideEmptyContainer = (sel) => document.querySelectorAll(sel).forEach(c => {
    if (!hideOn) { c.classList.remove('nav-hide'); return; }
    const visible = c.querySelectorAll('a:not(.nav-hide)').length;
    c.classList.toggle('nav-hide', visible === 0);
  });
  hideEmptyContainer('.sub-nav');
  hideEmptyContainer('.nav-group');

  // Placeholder shows when hide-mode is on AND the whole chart is empty.
  const empty = document.getElementById('empty-state');
  if (empty) {
    const chartEmpty = pruneEmpty(CONFIG) === undefined;
    empty.classList.toggle('visible', hideOn && chartEmpty);
  }

  // "(+N hidden)" badge in each collapsible summary. Only renders when
  // hide-mode is on; otherwise the span stays empty so nothing shows.
  refreshHiddenCounts(hideOn);
}

// Walk each collapsible and count how many .field-unset descendants it
// contains. Macro groups subsume the section sums automatically because
// querySelectorAll('.field-unset') descends into everything.
function refreshHiddenCounts(hideOn) {
  document.querySelectorAll('details.macro-group, details.section, details.nested-details, details.row')
    .forEach(d => {
      const span = d.querySelector(':scope > summary .hidden-count');
      if (!span) return;
      if (!hideOn) { span.textContent = ''; span.classList.remove('visible'); return; }
      const n = d.querySelectorAll('.field-unset').length;
      if (n === 0) { span.textContent = ''; span.classList.remove('visible'); }
      else { span.textContent = `+${n} hidden`; span.classList.add('visible'); }
    });
}

function refreshUI() {
  refreshAllSetMarkers();
  refreshAllFieldCounts();
  refreshValidation();
  applyHideUnset();
  scheduleAutosave();
}

// ── Cross-field validation badges ──────────────────────────────────────
// Calls window.validateConfig() and paints .has-error / "(N issues)" badges
// on every container whose path tree intersects an error path.

let VALIDATION_ERRORS_BY_PATH = new Map();  // exact path → [messages]
let VALIDATION_PATH_COUNTS = new Map();     // ancestor path prefix → count

function refreshValidation() {
  const errors = (typeof window.validateConfig === 'function')
    ? window.validateConfig(CONFIG) : [];

  VALIDATION_ERRORS_BY_PATH = new Map();
  VALIDATION_PATH_COUNTS = new Map();
  for (const e of errors) {
    if (!VALIDATION_ERRORS_BY_PATH.has(e.path)) VALIDATION_ERRORS_BY_PATH.set(e.path, []);
    VALIDATION_ERRORS_BY_PATH.get(e.path).push(e.message);
    // Record the count for every ancestor prefix so containers show a count too.
    // Path like "palettes[2].entity_types[0]" — ancestors: palettes, palettes[2],
    // palettes[2].entity_types.
    const segs = e.path.match(/[^.[\]]+|\[\d+\]/g) || [];
    let prefix = '';
    for (const seg of segs.slice(0, -1)) {
      prefix = prefix ? (seg.startsWith('[') ? prefix + seg : prefix + '.' + seg) : seg;
      VALIDATION_PATH_COUNTS.set(prefix, (VALIDATION_PATH_COUNTS.get(prefix) || 0) + 1);
    }
  }

  // Paint field-level badges
  document.querySelectorAll('.field').forEach(f => {
    const path = f._configPath;
    if (!path) return;
    const msgs = VALIDATION_ERRORS_BY_PATH.get(path);
    if (msgs && msgs.length) {
      f.classList.add('has-error');
      f.title = msgs.join('\n');
    } else {
      f.classList.remove('has-error');
      f.removeAttribute('title');
    }
  });

  // Paint container "(N issues)" badges
  document.querySelectorAll('details.macro-group, details.section, details.nested-details, details.row')
    .forEach(d => {
      let n = 0;
      if (d._issueCountFn) {
        n = d._issueCountFn();
      } else if (d._configPath) {
        const path = d._configPath;
        n = (VALIDATION_PATH_COUNTS.get(path) || 0)
          + (VALIDATION_ERRORS_BY_PATH.get(path) ? VALIDATION_ERRORS_BY_PATH.get(path).length : 0);
      }
      const badge = d.querySelector(':scope > summary .issue-count');
      if (!badge) return;
      if (n === 0) { badge.textContent = ''; badge.classList.remove('visible'); }
      else { badge.textContent = `${n} ${n === 1 ? 'issue' : 'issues'}`; badge.classList.add('visible'); }
    });
}

// ── Help "(?)" button + modal ──────────────────────────────────────────

function attachHelpButton(label, defName, field) {
  const key = `${defName}.${field.name}`;
  if (!window.HELP || !window.HELP[key]) return;
  const hb = document.createElement('button');
  hb.type = 'button';
  hb.className = 'help-btn';
  hb.textContent = '?';
  hb.title = `What is ${field.name}?`;
  hb.setAttribute('aria-label', `Help for ${field.name}`);
  hb.addEventListener('click', (e) => {
    e.preventDefault();
    openHelp(defName, field);
  });
  label.appendChild(hb);
}

function describeFieldType(field) {
  if (field.ref) return `nested ${field.ref}`;
  if (field.list_of) return `list of ${field.list_of}`;
  if (field.type === 'dict_of') return `dict<string, ${field.value_ref}>`;
  if (field.type === 'enum') return `enum ${field.enum}`;
  if (field.type === 'geo_data') return 'dict<place, [lat, lon]>';
  if (field.type === 'select') return `select (${(field.options || []).join(' / ')})`;
  if (field.type === 'list-of-text') return 'list of text';
  if (field.type === 'list-of-number') return 'list of number';
  if (field.type === 'list-of-color') return 'list of color';
  if (field.type) return field.type;
  return '';
}

function openHelp(defName, field) {
  const dlg = document.getElementById('help-dialog');
  document.getElementById('help-title').textContent = field.name + (field.required ? ' *' : '');
  document.getElementById('help-type').textContent =
    `${defName}.${field.name} — ${describeFieldType(field)}`;
  const raw = window.HELP[`${defName}.${field.name}`] || '(no description available)';
  document.getElementById('help-body').textContent = formatHelpText(raw);
  if (typeof dlg.showModal === 'function') dlg.showModal();
  else dlg.setAttribute('open', '');  // <dialog> polyfill fallback
}

// Break a help string into one sentence per line for readability.
// Splits on ". " only when followed by an uppercase letter — that way "e.g.
// 'phone'", "i.e. foo", decimal numbers, and other intra-sentence dots aren't
// turned into breaks. The CSS on .help-body uses white-space: pre-wrap.
function formatHelpText(text) {
  return text.replace(/\. (?=[A-Z])/g, '.\n');
}

// ── Tri-state bool widget (true / false / unset → omitted from YAML) ───

// Cycle order matches the legend's reading order: unset → true → false → unset.
function renderTriStateBool(field, obj) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'tri-state';

  const stateOf = (v) => v === true ? 'true' : v === false ? 'false' : 'unset';
  const symbolOf = (s) => s === 'true' ? '✓' : s === 'false' ? '✗' : '–';

  const refresh = () => {
    const s = stateOf(obj[field.name]);
    btn.classList.remove('is-true', 'is-false', 'is-unset');
    btn.classList.add(`is-${s}`);
    btn.textContent = symbolOf(s);
    btn.title = `${field.name}: ${s === 'unset' ? 'unset (will be omitted)' : s}`;
    btn.setAttribute('aria-label', btn.title);
    btn.setAttribute('aria-pressed', s === 'true' ? 'true' : s === 'false' ? 'false' : 'mixed');
  };

  btn.addEventListener('click', () => {
    const cur = obj[field.name];
    if (cur === undefined || cur === null) obj[field.name] = true;
    else if (cur === true) obj[field.name] = false;
    else obj[field.name] = null;
    refresh();
  });

  refresh();
  return btn;
}

// Toggle the .is-unset CSS class so an empty input renders greyed,
// signalling that the field will be omitted from the downloaded YAML.
// Wired into every primitive input/select at creation AND on input.
function markUnset(el) {
  const v = el.value;
  const isEmpty = (v === '' || v === null || v === undefined);
  el.classList.toggle('is-unset', isEmpty);
}

// Append (input + small "×" clear button) wrapped in an .input-row so the
// button can absolutely-position against the input row only. Replaces the
// previous `wrap.appendChild(inp)` so callers do this in one step.
// Clicking × resets the field to null, clears the visible value, re-runs
// markUnset, and triggers refreshUI. CSS hides × when input is .is-unset.
function appendInputWithClear(wrap, obj, field, inp) {
  const row = document.createElement('div');
  row.className = 'input-row';
  row.appendChild(inp);
  // Color (and any future input type that wants to sit next to its main
  // input) stashes a sibling element on the input. We insert it here so the
  // swatch sits between the input and the × button.
  if (inp._extraEl) row.appendChild(inp._extraEl);

  const x = document.createElement('button');
  x.type = 'button';
  x.className = 'field-clear';
  x.textContent = '×';
  x.title = 'Clear (set to unset)';
  x.setAttribute('aria-label', `Clear ${field.name}`);
  x.addEventListener('click', (e) => {
    e.preventDefault();
    obj[field.name] = null;
    inp.value = '';
    markUnset(inp);
    // Fire input so any sibling listeners (e.g. color swatch) reset too.
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    refreshUI();
  });
  row.appendChild(x);
  wrap.appendChild(row);
}

// ── Utilities ───────────────────────────────────────────────────────────

function ensureObject(parent, key) {
  if (typeof parent[key] !== 'object' || parent[key] === null || Array.isArray(parent[key])) {
    parent[key] = {};
  }
}

// Recursively prune null / "" / empty arrays / empty objects from a clone
// of the in-memory config. The library treats null/empty as "unset" for
// most fields, so this keeps the emitted YAML clean.
function pruneEmpty(val) {
  if (val === null || val === undefined) return undefined;
  if (Array.isArray(val)) {
    const out = val.map(pruneEmpty).filter(v => v !== undefined);
    return out.length ? out : undefined;
  }
  if (typeof val === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(val)) {
      const pv = pruneEmpty(v);
      if (pv !== undefined) out[k] = pv;
    }
    return Object.keys(out).length ? out : undefined;
  }
  if (val === '') return undefined;
  return val;
}

function importYamlText(text, fileName) {
  let parsed;
  try {
    parsed = jsyaml.load(text);
  } catch (e) {
    alert(`Could not parse ${fileName}: ${e.message}`);
    return;
  }
  if (parsed === null || parsed === undefined) {
    alert(`${fileName} is empty.`);
    return;
  }
  if (typeof parsed !== 'object' || Array.isArray(parsed)) {
    alert(`${fileName} doesn't look like a config file — expected a top-level mapping.`);
    return;
  }

  const cleaned = pruneEmpty(CONFIG);
  const hasContent = cleaned && Object.keys(cleaned).length > 0;
  if (hasContent && !confirm('Replace the current form contents with the imported file?')) {
    return;
  }

  CONFIG = parsed;
  renderAll();
  scheduleAutosave();
  toast(`imported ${fileName}`);
}

function downloadYaml() {
  const cleaned = pruneEmpty(CONFIG) || {};
  let yamlText;
  try {
    yamlText = jsyaml.dump(cleaned, { noRefs: true, sortKeys: false, lineWidth: 100 });
  } catch (e) {
    alert('Could not generate YAML: ' + e.message);
    return;
  }
  const header =
    `# Generated by anxwritter config builder (schema v${SCHEMA._meta.schemaVersion}, anxwritter ${SCHEMA._meta.anxwritterVersion}).\n` +
    `# Apply with:  anxwritter --config <this-file> <data.yaml> -o out.anx\n\n`;
  const blob = new Blob([header + yamlText], { type: 'application/x-yaml;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'config.yaml';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);

  toast('config.yaml downloaded');
}

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

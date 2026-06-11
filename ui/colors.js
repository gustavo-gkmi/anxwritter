// 40 named ANB shading colors → '#RRGGBB'.
// Lifted from docs/reference/visual-styling.md (the single source of truth in
// the library). Names are stored in normalized form (lowercase, underscores
// as separators) so app.js can look them up after the same normalization the
// library uses in colors.NAMED_COLORS / _normalize_name.

window.NAMED_COLORS = {
  black:           '#000000',
  brown:           '#993300',
  olive_green:     '#333300',
  dark_green:      '#003300',
  dark_teal:       '#003366',
  dark_blue:       '#000080',
  indigo:          '#333399',
  dark_grey:       '#333333',
  dark_red:        '#800000',
  orange:          '#FF6600',
  dark_yellow:     '#808000',
  green:           '#008000',
  teal:            '#008080',
  blue:            '#0000FF',
  blue_grey:       '#666699',
  grey:            '#808080',
  red:             '#FF0000',
  light_orange:    '#FF9900',
  lime:            '#99CC00',
  sea_green:       '#339966',
  aqua:            '#33CCCC',
  light_blue:      '#3366FF',
  violet:          '#800080',
  light_grey:      '#999999',
  pink:            '#FF00FF',
  gold:            '#FFCC00',
  yellow:          '#FFFF00',
  bright_green:    '#00FF00',
  turquoise:       '#00FFFF',
  sky_blue:        '#00CCFF',
  plum:            '#993366',
  silver:          '#C0C0C0',
  rose:            '#FF99CC',
  tan:             '#FFCC99',
  light_yellow:    '#FFFF99',
  light_green:     '#CCFFCC',
  light_turquoise: '#CCFFFF',
  pale_blue:       '#99CCFF',
  lavender:        '#CC99FF',
  white:           '#FFFFFF',
};

// Normalize a user-typed name to the canonical lookup key:
// 'Light Orange' / 'light-orange' / 'LIGHT_ORANGE' → 'light_orange'.
window.normalizeColorName = function normalizeColorName(s) {
  return String(s).trim().toLowerCase().replace(/[\s-]+/g, '_');
};

// Parse any of: Color enum string, named color (any case/separator), '#RRGGBB',
// bare 6-char hex, or COLORREF int. Returns '#RRGGBB' or null on failure.
//
// COLORREF byte order: R + G*256 + B*65536 — low byte is R (Windows convention,
// opposite of standard hex which is RGB high-to-low).
window.resolveColorToHex = function resolveColorToHex(v) {
  if (v === null || v === undefined || v === '') return null;

  if (typeof v === 'number' && Number.isFinite(v) && v >= 0) {
    const r = v & 0xFF;
    const g = (v >> 8) & 0xFF;
    const b = (v >> 16) & 0xFF;
    return '#' + [r, g, b].map(n => n.toString(16).padStart(2, '0').toUpperCase()).join('');
  }

  if (typeof v !== 'string') return null;
  const s = v.trim();

  // #RRGGBB or RRGGBB
  let m = s.match(/^#?([0-9a-fA-F]{6})$/);
  if (m) return '#' + m[1].toUpperCase();

  // All-digit string → treat as COLORREF int
  if (/^\d+$/.test(s)) return window.resolveColorToHex(parseInt(s, 10));

  // Named (with any separator / case)
  const key = window.normalizeColorName(s);
  if (key in window.NAMED_COLORS) return window.NAMED_COLORS[key];

  return null;
};

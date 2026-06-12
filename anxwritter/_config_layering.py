"""
Config-layering engine for ANXChart — field-merge / lock / delete / wipe.

Extracted from ``chart.py`` as a mixin: ``ANXChart`` inherits these methods,
which operate on the chart's own ``_config_*`` lock/source maps and section
collections (created in ``ANXChart.__init__``). Ownership of that state stays
on ANXChart — this is a file-split, not a state-ownership redesign.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional

from .errors import ErrorType
from .models import (
    AttributeClass, DateTimeFormat, DisplayAttribute, DisplayLabel,
    EntityType, Font, GradeCollection, LegendItem, LinkType, Palette,
    PaletteAttributeEntry, SemanticEntity, SemanticLink, SemanticProperty,
    Settings, Strength, StrengthCollection,
)


# Sentinel for "key absent" (distinct from an explicit None value) in the
# config-layering engine — a delete layer uses ``key: null`` to mean "remove",
# so None and absent must be distinguishable.
_UNSET = object()


# ── `cascade.mode` (in-file layering policy) ──────────────────────────────
#
# A config file may carry a top-level ``cascade`` block whose ``mode`` field
# tells the loader which layering operation to apply by default. Values match
# the CLI flag vocabulary one-to-one. When present and the caller didn't pass
# an explicit operation/wipe_previous/lock, the meta wins; explicit kwargs
# (from CLI flags or Python callers) override.
#
#     cascade:
#       mode: lock           # one of: merge (default), wipe, delete, lock
#
# The meta is purely an apply-time concern; ``from_dict`` / ``from_yaml`` /
# ``from_json`` strip it silently because chart construction has no layering.

_CASCADE_MODE_TO_TRIPLE = {
    'merge':  ('merge', False, False),
    'wipe':   ('merge', True, False),
    'delete': ('delete', False, False),
    'lock':   ('merge', False, True),
}


def _extract_cascade_meta(data: dict) -> tuple:
    """Pop the top-level ``cascade`` block (if any), validate, return its mode.

    Returns ``(cleaned_data, mode | None)``. ``cleaned_data`` is the same dict
    as ``data`` with the ``cascade`` key removed (a copy — we don't mutate the
    caller's dict). Raises ``ValueError`` on malformed cascade metadata.
    """
    if not isinstance(data, dict) or 'cascade' not in data:
        return data, None

    cleaned = {k: v for k, v in data.items() if k != 'cascade'}
    meta = data['cascade']
    if meta is None:
        return cleaned, None
    if not isinstance(meta, dict):
        raise ValueError(
            f"`cascade` must be a mapping, got {type(meta).__name__}."
        )
    extra = set(meta.keys()) - {'mode'}
    if extra:
        raise ValueError(
            f"Unknown keys under `cascade`: {sorted(extra)} "
            f"(only `mode` is supported)."
        )
    mode = meta.get('mode')
    if mode is None:
        return cleaned, None
    if mode not in _CASCADE_MODE_TO_TRIPLE:
        raise ValueError(
            f"`cascade.mode` must be one of "
            f"{sorted(_CASCADE_MODE_TO_TRIPLE)}, got {mode!r}."
        )
    return cleaned, mode


class _ConfigLayeringMixin:
    """Field-merge / lock / delete / wipe config-layering engine for ANXChart.

    Mixed into ``ANXChart``; every method operates on attributes the chart owns
    (``self.settings``, ``self.strengths``, ``self._entity_types``, the
    ``self._config_*`` maps, ...), all set up in ``ANXChart.__init__``.
    """

    # ------------------------------------------------------------------
    # Source provenance helpers (used by validators)
    # ------------------------------------------------------------------

    def _source_for(self, section: str, name: Optional[str] = None) -> Optional[str]:
        """Look up the source layer that contributed an entry.

        For named-upsert sections, falls back to the section-level source
        when no per-name entry exists (e.g. when source_name was not set
        for the layer that added the entry but a later layer touched the
        section).
        """
        if name is not None:
            src = self._config_sources.get((section, name))
            if src is not None:
                return src
        return self._config_section_sources.get(section)

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def _dc_to_clean_dict(obj) -> dict:
        """Convert a dataclass to a dict with None values removed."""
        return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}

    # ------------------------------------------------------------------
    # Config-layering engine: field-merge / lock / delete / wipe_previous
    # ------------------------------------------------------------------

    @staticmethod
    def _walk_leaves(d: dict, prefix: str = ''):
        """Yield ``(dotted_path, value)`` for every non-dict leaf of ``d``.

        Dict-valued entries are recursed; list- and scalar-valued entries are
        leaves. Used to enumerate the leaves a config layer explicitly
        declared (lock recording / checking, settings-leaf delete).
        """
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                yield from _ConfigLayeringMixin._walk_leaves(v, path)
            else:
                yield path, v

    @staticmethod
    def _deep_merge_dicts(base: dict, incoming: dict) -> dict:
        """Return a new dict: ``incoming`` merged onto ``base``; dict-valued
        keys merge recursively, scalars/lists replace wholesale."""
        out = dict(base)
        for k, v in incoming.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _ConfigLayeringMixin._deep_merge_dicts(out[k], v)
            else:
                out[k] = v
        return out

    @staticmethod
    def _deep_delete(d: dict, dotted: str) -> None:
        """Remove the leaf at ``dotted`` from nested dict ``d`` in place."""
        parts = dotted.split('.')
        cur = d
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                return
            cur = nxt
        cur.pop(parts[-1], None)

    @staticmethod
    def _strip_none_deep(obj):
        """Recursively drop ``None`` values from dicts (and dict items inside
        lists). Used to turn ``dataclasses.asdict`` output into a 'declared
        leaves only' view for Settings-instance config layers."""
        if isinstance(obj, dict):
            return {
                k: _ConfigLayeringMixin._strip_none_deep(v)
                for k, v in obj.items() if v is not None
            }
        if isinstance(obj, list):
            return [_ConfigLayeringMixin._strip_none_deep(v) for v in obj]
        return obj

    @staticmethod
    def _field_default(obj, fname):
        """Return the declared default for field ``fname`` of dataclass ``obj``."""
        for f in dataclasses.fields(obj):
            if f.name == fname:
                if f.default is not dataclasses.MISSING:
                    return f.default
                if f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                    return f.default_factory()  # type: ignore[misc]
                return None
        return None

    def _check_leaf_lock(self, section, idv, leaf, value, source_name) -> bool:
        """Return True (and record a ``locked_override`` conflict) when writing
        ``value`` to ``(section, idv, leaf)`` is blocked by a config-vs-config
        lock. The locked value is left in place by the caller (fail-safe)."""
        key = (section, idv, leaf)
        locked = self._config_locked_leaves.get(key, _UNSET)
        if locked is not _UNSET and locked != value:
            where = f"{section}{('.' + idv) if idv else ''}.{leaf}"
            err = {
                'type': ErrorType.LOCKED_OVERRIDE.value,
                'section': section,
                'name': idv,
                'field': leaf,
                'message': (
                    f"config layer{(' ' + repr(source_name)) if source_name else ''} "
                    f"tried to change locked {where} from {locked!r} to "
                    f"{value!r}; the locked value is kept."
                ),
                'locked_value': locked,
                'attempted_value': value,
            }
            csrc = self._source_for(section, idv)
            if csrc is not None:
                err['config_source'] = csrc
            self._config_conflicts.append(err)
            return True
        return False

    def _drop_entry_leaf_locks(self, section, idv) -> None:
        """Forget every leaf lock recorded for one ``(section, idv)`` entry."""
        self._config_locked_leaves = {
            k: v for k, v in self._config_locked_leaves.items()
            if not (k[0] == section and k[1] == idv)
        }

    def _entry_is_locked(self, section, idv) -> bool:
        """True when any leaf lock exists for ``(section, idv)``."""
        return any(
            k[0] == section and k[1] == idv
            for k in self._config_locked_leaves
        )

    def _merge_keyed_section(self, *, section, backing, cls, identity, incoming,
                             operation, lock, wipe_previous, source_name,
                             coerce_nested=None) -> None:
        """Field-merge / delete / lock one keyed list (named registries +
        the two ``extra_cfg`` synthesizer lists). ``backing`` is mutated in
        place; ``identity`` is ``'name'`` or ``'key'``."""
        if operation == 'merge' and wipe_previous:
            backing.clear()
            self._config_locked.pop(section, None)
            self._drop_section_state(section)

        by_id = {
            getattr(e, identity): i
            for i, e in enumerate(backing) if getattr(e, identity, None)
        }
        locked_data = self._config_locked.get(section, {})

        for raw in incoming:
            is_obj = dataclasses.is_dataclass(raw) and not isinstance(raw, type)
            if is_obj:
                idv = getattr(raw, identity, None)
            elif isinstance(raw, dict):
                idv = raw.get(identity)
            else:
                continue

            if operation == 'delete':
                self._delete_keyed_entry(
                    section, backing, by_id, identity, raw, idv, source_name,
                )
                continue

            # ── merge ──
            if is_obj:
                clean = self._dc_to_clean_dict(raw)
            else:
                clean = {k: v for k, v in raw.items() if v is not None}

            if not idv:
                # No identity — append as-is; validate() flags it later.
                obj = raw if is_obj else cls(**(coerce_nested(clean) if coerce_nested else clean))
                backing.append(obj)
                continue

            # Lock-check each declared non-identity leaf; drop blocked ones.
            blocked = []
            for leaf, value in self._walk_leaves(clean):
                if leaf == identity:
                    continue
                if self._check_leaf_lock(section, idv, leaf, value, source_name):
                    blocked.append(leaf)
            for leaf in blocked:
                self._deep_delete(clean, leaf)

            if idv in by_id:
                existing = backing[by_id[idv]]
                merged = self._deep_merge_dicts(self._dc_to_clean_dict(existing), clean)
                backing[by_id[idv]] = cls(**(coerce_nested(merged) if coerce_nested else merged))
            else:
                backing.append(cls(**(coerce_nested(clean) if coerce_nested else clean)))
                by_id[idv] = len(backing) - 1

            if lock:
                for leaf, value in self._walk_leaves(clean):
                    self._config_locked_leaves[(section, idv, leaf)] = value

            # Snapshot for the config-vs-data conflict path + source tag.
            locked_data[idv] = self._dc_to_clean_dict(backing[by_id[idv]])
            if source_name is not None:
                self._config_sources[(section, idv)] = source_name

        if locked_data:
            self._config_locked[section] = locked_data

    def _delete_keyed_entry(self, section, backing, by_id, identity, raw, idv,
                            source_name) -> None:
        """Apply a delete-layer entry to one keyed section (subtract by shape)."""
        if not idv:
            return  # nothing to address
        # Determine which non-identity fields the layer mentioned, and whether
        # any carry a (forbidden) non-null value.
        if isinstance(raw, dict):
            mentioned = {k: v for k, v in raw.items() if k != identity}
        else:
            mentioned = {}  # dataclass instance → whole-entry delete only
        non_null = [k for k, v in mentioned.items() if v is not None]
        if non_null:
            self._config_conflicts.append({
                'type': ErrorType.DELETE_CONTRACT.value,
                'section': section,
                'name': idv,
                'message': (
                    f"delete layer entry {section}.{idv} carries a non-null "
                    f"value on non-identity field(s) {non_null}; write "
                    f"'field:' (null) to remove a field, or list only the "
                    f"identity to remove the whole entry."
                ),
            })
            return

        if mentioned:
            # Field-unset delete — revert each mentioned field to its default.
            if idv not in by_id:
                return  # absent → idempotent no-op
            existing = backing[by_id[idv]]
            for fname in mentioned:
                locked_here = any(
                    k[0] == section and k[1] == idv
                    and (k[2] == fname or k[2].startswith(fname + '.'))
                    for k in self._config_locked_leaves
                )
                if locked_here:
                    self._check_leaf_lock(section, idv, fname, None, source_name)
                    continue
                if hasattr(existing, fname):
                    setattr(existing, fname, self._field_default(existing, fname))
            if idv in self._config_locked.get(section, {}):
                self._config_locked[section][idv] = self._dc_to_clean_dict(existing)
            return

        # Whole-entry delete.
        if idv not in by_id:
            return  # absent → idempotent no-op
        if self._entry_is_locked(section, idv):
            self._config_conflicts.append({
                'type': ErrorType.LOCKED_OVERRIDE.value,
                'section': section,
                'name': idv,
                'message': (
                    f"cannot delete {section}.{idv}: it has locked leaves "
                    f"(set by a lock=True layer)."
                ),
            })
            return
        del backing[by_id[idv]]
        by_id.clear()
        by_id.update({
            getattr(e, identity): i
            for i, e in enumerate(backing) if getattr(e, identity, None)
        })
        self._config_locked.get(section, {}).pop(idv, None)
        self._config_sources.pop((section, idv), None)

    def _drop_section_state(self, section) -> None:
        """Drop per-name sources + leaf locks for a section (wipe_previous)."""
        self._config_sources = {
            k: v for k, v in self._config_sources.items() if k[0] != section
        }
        self._config_locked_leaves = {
            k: v for k, v in self._config_locked_leaves.items() if k[0] != section
        }

    def _apply_settings_layer(self, incoming, *, operation, lock, wipe_previous,
                              source_name) -> None:
        """Apply a config layer's ``settings`` block (config mode).

        Extracts the two ``extra_cfg`` synthesizer keyed-lists and routes them
        through :meth:`_merge_keyed_section`; the remaining settings deep-merge
        (with per-leaf lock recording / checking) or, in delete mode, revert
        mentioned leaves to their defaults.
        """
        if isinstance(incoming, Settings):
            sdict = self._strip_none_deep(dataclasses.asdict(incoming))
        elif isinstance(incoming, dict):
            sdict = dict(incoming)
        else:
            raise TypeError(
                f"config['settings'] must be a Settings instance or dict, "
                f"got {type(incoming).__name__}"
            )

        # wipe_previous (merge only): reset settings to this layer's values.
        if operation == 'merge' and wipe_previous:
            self.settings = Settings.from_dict(sdict)
            self._drop_section_state('settings')
            self._config_section_sources.pop('settings', None)
            if lock:
                for dotted, value in self._walk_leaves(sdict):
                    self._config_locked_leaves[('settings', None, dotted)] = value
                if source_name is not None:
                    self._config_section_sources['settings'] = source_name
            return

        # Extract the synthesizer keyed-lists before the generic settings step.
        extra = sdict.get('extra_cfg')
        da = dl = _UNSET
        if isinstance(extra, dict):
            extra = dict(extra)
            da = extra.pop('display_attribute', _UNSET)
            dl = extra.pop('display_label', _UNSET)
            sdict = dict(sdict)
            sdict['extra_cfg'] = extra
        if da is not _UNSET:
            self._merge_keyed_section(
                section='extra_cfg.display_attribute',
                backing=self.settings.extra_cfg.display_attribute,
                cls=DisplayAttribute, identity='key', incoming=(da or []),
                operation=operation, lock=lock, wipe_previous=wipe_previous,
                source_name=source_name,
            )
        if dl is not _UNSET:
            self._merge_keyed_section(
                section='extra_cfg.display_label',
                backing=self.settings.extra_cfg.display_label,
                cls=DisplayLabel, identity='key', incoming=(dl or []),
                operation=operation, lock=lock, wipe_previous=wipe_previous,
                source_name=source_name,
            )

        if operation == 'delete':
            for dotted, value in self._walk_leaves(sdict):
                if value is not None:
                    self._config_conflicts.append({
                        'type': ErrorType.DELETE_CONTRACT.value,
                        'section': 'settings',
                        'name': None,
                        'message': (
                            f"delete layer settings.{dotted} carries a "
                            f"non-null value; write '{dotted.split('.')[-1]}:' "
                            f"(null) to reset a setting to its default."
                        ),
                    })
                    continue
                if self._check_leaf_lock('settings', None, dotted, None, source_name):
                    continue
                self._set_settings_leaf_default(dotted)
                self._config_locked_leaves.pop(('settings', None, dotted), None)
            return

        # merge mode: lock-check, prune blocked leaves, then deep-merge.
        declared = sdict
        blocked = []
        for dotted, value in self._walk_leaves(declared):
            if self._check_leaf_lock('settings', None, dotted, value, source_name):
                blocked.append(dotted)
        for dotted in blocked:
            self._deep_delete(declared, dotted)
        self.settings.merge_from_dict(declared)
        if lock:
            for dotted, value in self._walk_leaves(declared):
                self._config_locked_leaves[('settings', None, dotted)] = value
            if source_name is not None:
                self._config_section_sources['settings'] = source_name

    def _set_settings_leaf_default(self, dotted: str) -> None:
        """Reset a ``settings`` leaf (dotted path) to its dataclass default."""
        parts = dotted.split('.')
        obj = self.settings
        for p in parts[:-1]:
            obj = getattr(obj, p, None)
            if obj is None:
                return
        last = parts[-1]
        if hasattr(obj, last) and dataclasses.is_dataclass(obj):
            setattr(obj, last, self._field_default(obj, last))

    def _apply_config(
        self,
        data: dict,
        *,
        is_config: bool = True,
        operation: str = 'merge',
        wipe_previous: bool = False,
        lock: bool = False,
        source_name: Optional[str] = None,
    ) -> None:
        """Apply config sections from a dict to this chart.

        Config mode (*is_config* True) supports three orthogonal knobs:

        - ``operation``: ``'merge'`` (default, field-merge per identity) or
          ``'delete'`` (subtract by shape).
        - ``wipe_previous``: clear each mentioned section before merging
          (merge only).
        - ``lock``: freeze exactly the leaves this layer declares; a later
          layer changing one yields a ``locked_override`` error (merge only).

        Data mode (*is_config* False) ignores those knobs and runs the
        config-vs-data conflict checks (unchanged).

        *source_name* tags this layer's entries so ``validate()`` surfaces an
        optional ``source`` key. ``entities`` / ``links`` keys are ignored.
        """
        if operation not in ('merge', 'delete'):
            raise ValueError(
                f"operation must be 'merge' or 'delete', got {operation!r}"
            )
        if operation == 'delete' and lock:
            raise ValueError(
                "operation='delete' cannot be combined with lock=True"
            )
        if operation == 'delete' and wipe_previous:
            raise ValueError(
                "operation='delete' cannot be combined with wipe_previous=True"
            )

        if is_config:
            self._apply_config_layer(
                data, operation=operation, wipe_previous=wipe_previous,
                lock=lock, source_name=source_name,
            )
            self._has_config = True
        else:
            self._apply_data_layer(data)

    # Named registry sections: (dataclass, backing-attr, coerce-callback).
    _NAMED_SECTIONS = {
        'entity_types': (EntityType, '_entity_types', None),
        'link_types': (LinkType, '_link_types', None),
        'attribute_classes': (AttributeClass, '_attribute_classes', '_coerce_ac'),
        'datetime_formats': (DateTimeFormat, '_datetime_formats', None),
        'semantic_entities': (SemanticEntity, '_semantic_entities', None),
        'semantic_links': (SemanticLink, '_semantic_links', None),
        'semantic_properties': (SemanticProperty, '_semantic_properties', None),
    }

    @staticmethod
    def _coerce_ac(d: dict) -> dict:
        """Convert a nested ``font`` dict to a ``Font`` before AttributeClass()."""
        if isinstance(d.get('font'), dict):
            d = dict(d)
            d['font'] = Font(**{k: v for k, v in d['font'].items() if v is not None})
        return d

    def _apply_config_layer(self, data, *, operation, wipe_previous, lock,
                            source_name) -> None:
        """Apply one config layer (is_config=True path)."""
        # ── settings (+ extra_cfg synthesizer keyed-lists) ──
        if data.get('settings') is not None:
            self._apply_settings_layer(
                data['settings'], operation=operation, lock=lock,
                wipe_previous=wipe_previous, source_name=source_name,
            )

        # ── strengths (default + named items) ──
        if data.get('strengths') is not None:
            self._apply_strengths_layer(
                data['strengths'], operation=operation, lock=lock,
                wipe_previous=wipe_previous, source_name=source_name,
            )

        # ── named registry sections ──
        for section, (cls, attr_name, coerce_name) in self._NAMED_SECTIONS.items():
            if section not in data:
                continue
            coerce = getattr(self, coerce_name) if coerce_name else None
            self._merge_keyed_section(
                section=section, backing=getattr(self, attr_name), cls=cls,
                identity='name', incoming=(data.get(section) or []),
                operation=operation, lock=lock, wipe_previous=wipe_previous,
                source_name=source_name, coerce_nested=coerce,
            )

        # ── palettes / legend_items: append-only (whole-section ops only) ──
        if 'palettes' in data:
            self._apply_appendonly_layer(
                'palettes', self._palettes, data.get('palettes'),
                operation=operation, wipe_previous=wipe_previous,
                build=self._build_palette,
            )
        if 'legend_items' in data:
            self._apply_appendonly_layer(
                'legend_items', self._legend_items, data.get('legend_items'),
                operation=operation, wipe_previous=wipe_previous,
                build=self._build_legend_item,
            )

        # ── grades ──
        for key in ('grades_one', 'grades_two', 'grades_three'):
            if key not in data:
                continue
            self._apply_grade_layer(
                key, data.get(key), operation=operation, lock=lock,
                wipe_previous=wipe_previous, source_name=source_name,
            )

        # ── source_types ──
        if 'source_types' in data:
            self._apply_source_types_layer(
                data.get('source_types'), operation=operation, lock=lock,
                wipe_previous=wipe_previous, source_name=source_name,
            )

    # -- per-section config-layer helpers -------------------------------------

    def _apply_strengths_layer(self, raw_strengths, *, operation, lock,
                               wipe_previous, source_name) -> None:
        if isinstance(raw_strengths, StrengthCollection):
            incoming_default = raw_strengths.default
            items = raw_strengths.items
            default_mentioned_null = False
        elif isinstance(raw_strengths, dict):
            incoming_default = raw_strengths.get('default')
            items = raw_strengths.get('items', []) or []
            default_mentioned_null = (
                'default' in raw_strengths and raw_strengths['default'] is None
            )
        else:
            return

        if operation == 'delete':
            self._merge_keyed_section(
                section='strengths', backing=self.strengths.items, cls=Strength,
                identity='name', incoming=items, operation='delete', lock=False,
                wipe_previous=False, source_name=source_name,
            )
            if default_mentioned_null and not self._check_leaf_lock(
                'strengths', None, 'default', None, source_name,
            ):
                self.strengths.default = None
                self._config_locked_leaves.pop(('strengths', None, 'default'), None)
            return

        if wipe_previous:
            self.strengths = StrengthCollection()
            self._config_locked.pop('strengths', None)
            self._drop_section_state('strengths')
            self._config_section_sources.pop('strengths', None)

        if incoming_default is not None and not self._check_leaf_lock(
            'strengths', None, 'default', incoming_default, source_name,
        ):
            self.strengths.default = incoming_default
            if lock:
                self._config_locked_leaves[('strengths', None, 'default')] = incoming_default
                if source_name is not None:
                    self._config_section_sources['strengths'] = source_name

        self._merge_keyed_section(
            section='strengths', backing=self.strengths.items, cls=Strength,
            identity='name', incoming=items, operation='merge', lock=lock,
            wipe_previous=False, source_name=source_name,
        )

    @staticmethod
    def _build_palette(raw):
        if isinstance(raw, Palette):
            return raw
        if isinstance(raw, dict):
            d = {k: v for k, v in raw.items() if v is not None}
            ae = d.get('attribute_entries')
            if ae and isinstance(ae, list):
                d['attribute_entries'] = [
                    PaletteAttributeEntry(**e) if isinstance(e, dict) else e
                    for e in ae
                ]
            return Palette(**d)
        return None

    @staticmethod
    def _palette_to_dict(pal, *, full: bool) -> dict:
        """Serialize a Palette to a plain dict.

        ``full=True`` (build path) always emits ``locked`` and keeps ``None``
        entry values; ``full=False`` (config export) drops a falsy ``locked``
        and strips ``None`` from attribute-entry dicts.
        """
        d: Dict[str, Any] = {'name': pal.name}
        if full:
            d['locked'] = pal.locked
        elif pal.locked:
            d['locked'] = True
        if pal.entity_types:
            d['entity_types'] = list(pal.entity_types)
        if pal.link_types:
            d['link_types'] = list(pal.link_types)
        if pal.attribute_classes:
            d['attribute_classes'] = list(pal.attribute_classes)
        if pal.attribute_entries:
            if full:
                d['attribute_entries'] = [
                    {'name': ae.name, 'value': ae.value}
                    for ae in pal.attribute_entries
                ]
            else:
                d['attribute_entries'] = [
                    _ConfigLayeringMixin._dc_to_clean_dict(ae) for ae in pal.attribute_entries
                ]
        return d

    @staticmethod
    def _build_legend_item(raw):
        if isinstance(raw, LegendItem):
            return raw
        if isinstance(raw, dict):
            li = {k: v for k, v in raw.items() if v is not None}
            if 'label' in li and 'name' not in li:
                li['name'] = li.pop('label')
            if 'font' in li and isinstance(li['font'], dict):
                li['font'] = Font(**{k: v for k, v in li['font'].items() if v is not None})
            return LegendItem(**li)
        return None

    def _apply_appendonly_layer(self, section, backing, raw, *, operation,
                                wipe_previous, build) -> None:
        """palettes / legend_items: append (merge), clear (wipe), or
        clear-on-null (delete). No per-row identity, so per-row delete and
        per-leaf lock are not supported (documented)."""
        if operation == 'delete':
            if raw is None:
                backing.clear()
            return
        if wipe_previous:
            backing.clear()
        for item in (raw or []):
            obj = build(item)
            if obj is not None:
                backing.append(obj)

    def _apply_grade_layer(self, key, val, *, operation, lock, wipe_previous,
                           source_name) -> None:
        current: GradeCollection = getattr(self, key)
        if operation == 'delete':
            if val is None:
                if self._entry_is_locked(key, None):
                    self._config_conflicts.append({
                        'type': ErrorType.LOCKED_OVERRIDE.value,
                        'section': key, 'name': None,
                        'message': f"cannot delete {key}: it has locked leaves.",
                    })
                    return
                setattr(self, key, GradeCollection())
                self._config_locked_grades.pop(key, None)
                self._config_section_sources.pop(key, None)
                self._drop_section_state(key)
                return
            if isinstance(val, GradeCollection):
                items = list(val.items); default_null = val.default is None
            elif isinstance(val, dict):
                items = list(val.get('items', []) or [])
                default_null = 'default' in val and val['default'] is None
            else:
                return
            for item in items:
                if self._check_leaf_lock(key, None, 'item:' + item, None, source_name):
                    continue
                if item in current.items:
                    current.items.remove(item)
            if default_null and not self._check_leaf_lock(key, None, 'default', None, source_name):
                current.default = None
            self._config_locked_grades[key] = GradeCollection(
                default=current.default, items=list(current.items),
            )
            return

        if val is None:
            return
        if isinstance(val, GradeCollection):
            incoming_default = val.default; incoming_items = list(val.items)
        elif isinstance(val, dict):
            incoming_default = val.get('default')
            incoming_items = list(val.get('items', []) or [])
        else:
            return

        if wipe_previous:
            setattr(self, key, GradeCollection())
            self._config_locked_grades.pop(key, None)
            self._config_section_sources.pop(key, None)
            self._drop_section_state(key)
            current = getattr(self, key)

        existing = set(current.items)
        for item in incoming_items:
            if item not in existing:
                current.items.append(item)
                existing.add(item)
            if lock:
                self._config_locked_leaves[(key, None, 'item:' + item)] = item
        if incoming_default is not None and not self._check_leaf_lock(
            key, None, 'default', incoming_default, source_name,
        ):
            current.default = incoming_default
            if lock:
                self._config_locked_leaves[(key, None, 'default')] = incoming_default
        self._config_locked_grades[key] = GradeCollection(
            default=current.default, items=list(current.items),
        )
        if source_name is not None:
            self._config_section_sources[key] = source_name

    def _apply_source_types_layer(self, val, *, operation, lock, wipe_previous,
                                  source_name) -> None:
        if operation == 'delete':
            if val is None:
                if self._entry_is_locked('source_types', None):
                    self._config_conflicts.append({
                        'type': ErrorType.LOCKED_OVERRIDE.value,
                        'section': 'source_types', 'name': None,
                        'message': "cannot delete source_types: it has locked leaves.",
                    })
                    return
                self.source_types = []
                self._config_locked_source_types = None
                self._config_section_sources.pop('source_types', None)
                self._drop_section_state('source_types')
                return
            for item in list(val):
                if self._check_leaf_lock('source_types', None, 'item:' + item, None, source_name):
                    continue
                if item in self.source_types:
                    self.source_types.remove(item)
            self._config_locked_source_types = list(self.source_types)
            return

        if val is None:
            return
        val = list(val)
        if wipe_previous:
            self.source_types = []
            self._config_section_sources.pop('source_types', None)
            self._drop_section_state('source_types')
        existing = set(self.source_types)
        for item in val:
            if item not in existing:
                self.source_types.append(item)
                existing.add(item)
            if lock:
                self._config_locked_leaves[('source_types', None, 'item:' + item)] = item
        self._config_locked_source_types = list(self.source_types)
        if source_name is not None:
            self._config_section_sources['source_types'] = source_name

    def _apply_data_layer(self, data) -> None:
        """Apply config sections from a DATA file (is_config=False).

        Runs the config-vs-data conflict checks against locked config entries;
        unchanged from the pre-1.12 behaviour.
        """
        # ── settings: deep merge (data wins) ──
        incoming_settings = data.get('settings')
        if incoming_settings is not None:
            if isinstance(incoming_settings, Settings):
                self.settings.merge_from_dict(dataclasses.asdict(incoming_settings))
            elif isinstance(incoming_settings, dict):
                self.settings.merge_from_dict(incoming_settings)
            else:
                raise TypeError(
                    f"config['settings'] must be a Settings instance or dict, "
                    f"got {type(incoming_settings).__name__}"
                )

        # ── strengths ──
        raw_strengths = data.get('strengths')
        if raw_strengths is not None:
            if isinstance(raw_strengths, StrengthCollection):
                if raw_strengths.default is not None:
                    self.strengths.default = raw_strengths.default
                strength_items = raw_strengths.items
            elif isinstance(raw_strengths, dict):
                if raw_strengths.get('default') is not None:
                    self.strengths.default = raw_strengths['default']
                strength_items = raw_strengths.get('items', []) or []
            else:
                strength_items = []
            locked = self._config_locked.get('strengths', {})
            for raw in strength_items:
                if isinstance(raw, dict):
                    obj = Strength(**{k: v for k, v in raw.items() if v is not None})
                elif isinstance(raw, Strength):
                    obj = raw
                else:
                    continue
                name = obj.name
                clean = self._dc_to_clean_dict(obj)
                if self._has_config and name and name in locked:
                    if clean != locked[name]:
                        self._append_data_conflict('strengths', name, locked[name], clean)
                else:
                    self.add_strength(obj)

        # ── named registry sections ──
        for section, (cls, attr_name, coerce_name) in self._NAMED_SECTIONS.items():
            if section not in data:
                continue
            coerce = getattr(self, coerce_name) if coerce_name else None
            locked = self._config_locked.get(section, {})
            for raw in (data.get(section) or []):
                if isinstance(raw, dict):
                    cleaned = {k: v for k, v in raw.items() if v is not None}
                    if coerce:
                        cleaned = coerce(cleaned)
                    obj = cls(**cleaned)
                elif isinstance(raw, cls):
                    obj = raw
                else:
                    continue
                name = obj.name
                if not name:
                    getattr(self, attr_name).append(obj)
                    continue
                clean = self._dc_to_clean_dict(obj)
                if self._has_config and name in locked:
                    if clean != locked[name]:
                        self._append_data_conflict(section, name, locked[name], clean)
                else:
                    self._upsert_by_name(getattr(self, attr_name), obj)

        # ── palettes / legend_items: append ──
        for raw in (data.get('palettes') or []):
            obj = self._build_palette(raw)
            if obj is not None:
                self._palettes.append(obj)
        for raw in (data.get('legend_items') or []):
            obj = self._build_legend_item(raw)
            if obj is not None:
                self._legend_items.append(obj)

        # ── grades ──
        for key in ('grades_one', 'grades_two', 'grades_three'):
            if key not in data:
                continue
            val = data.get(key)
            if val is None:
                continue
            if isinstance(val, GradeCollection):
                gc = GradeCollection(default=val.default, items=list(val.items))
            elif isinstance(val, dict):
                gc = GradeCollection(
                    default=val.get('default'), items=list(val.get('items', []) or []),
                )
            else:
                continue
            if self._has_config and key in self._config_locked_grades:
                locked_gc = self._config_locked_grades[key]
                if gc.items != locked_gc.items or gc.default != locked_gc.default:
                    err = {
                        'type': 'config_conflict', 'section': key, 'name': key,
                        'message': (
                            f"Data redefines '{key}' with different values than "
                            f"config. Remove from data file or match config."
                        ),
                        'config_value': {'default': locked_gc.default, 'items': locked_gc.items},
                        'data_value': {'default': gc.default, 'items': gc.items},
                    }
                    src = self._config_section_sources.get(key)
                    if src is not None:
                        err['config_source'] = src
                    self._config_conflicts.append(err)
            else:
                setattr(self, key, gc)

        # ── source_types ──
        if 'source_types' in data:
            val = data.get('source_types')
            if val is not None:
                val = list(val)
                if self._has_config and self._config_locked_source_types is not None:
                    if val != self._config_locked_source_types:
                        err = {
                            'type': 'config_conflict', 'section': 'source_types',
                            'name': 'source_types',
                            'message': (
                                "Data redefines 'source_types' with different "
                                "values than config. Remove from data file or "
                                "match config."
                            ),
                            'config_value': self._config_locked_source_types,
                            'data_value': val,
                        }
                        src = self._config_section_sources.get('source_types')
                        if src is not None:
                            err['config_source'] = src
                        self._config_conflicts.append(err)
                else:
                    self.source_types = val

    def _append_data_conflict(self, section, name, config_value, data_value) -> None:
        """Record a config-vs-data ``config_conflict`` for a named section."""
        err = {
            'type': 'config_conflict',
            'section': section,
            'name': name,
            'message': (
                f"Data redefines '{name}' in {section} with different specs "
                f"than config. Remove from data file or match config."
            ),
            'config_value': config_value,
            'data_value': data_value,
        }
        src = self._source_for(section, name)
        if src is not None:
            err['config_source'] = src
        self._config_conflicts.append(err)

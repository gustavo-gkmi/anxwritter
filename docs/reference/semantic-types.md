# Semantic Types

Semantic type definitions for the `lcx:LibraryCatalogue` embedded in ANX files. Used by ANB v9 to map entity types, link types, and attribute classes to i2's standard library hierarchy.

---

## Overview

ANB v9 uses `SemanticTypeGuid` attributes on `EntityType`, `LinkType`, `AttributeClass`, and per-instance `Entity`/`Link` elements to reference semantic types. These GUIDs must match entries in an embedded `<lcx:LibraryCatalogue>`. Without the catalogue, keyref validation fails.

**Identifier note:** anxwritter embeds nine i2 GUIDs in total: six abstract root GUIDs (Entity, Link, Abstract Text/Number/DateTime/Flag) and three standard-library property GUIDs used by the geo-map feature (`Latitude`, `Longitude`, `Grid Reference`). The latter are required because ANB's Esri Maps subsystem keys mapping recognition off those specific identifiers — faithfully reproducing them is the only way to interoperate. Their inclusion is solely for interoperability; they are factual identifiers, not creative content. All other standard-library types must be provided by the user via config files or `.ant`/`.anx` reference files.

---

## Three separate hierarchies

Semantic types are organized into three independent trees. The same name can exist in different trees without conflict. Uniqueness is enforced per super-root, not globally.

| Tree | Root type | XML element | Parent attribute | API method |
|------|-----------|-------------|------------------|------------|
| Entity | `Entity` | `lcx:Type` | `kindOf` | `add_semantic_entity()` |
| Link | `Link` | `lcx:Type` | `kindOf` | `add_semantic_link()` |
| Property | 4 abstract roots | `lcx:Property` | `baseProperty` | `add_semantic_property()` |

The 4 abstract property roots are: `Abstract Text`, `Abstract Number`, `Abstract Date & Time`, and `Abstract Flag`.

---

## Where types come from

anxwritter does not ship i2's standard semantic-type library. To populate the `lcx:LibraryCatalogue` you have two options.

### Option A -- define your own taxonomy in config

Use the abstract roots anxwritter ships (`Entity`, `Link`, `Abstract Text`, `Abstract Number`, `Abstract Date & Time`, `Abstract Flag`) as parents and build whatever hierarchy fits your domain. The builder processes entries sequentially -- earlier entries are available as `kind_of`/`base_property` targets for later entries.

```yaml
semantic_entities:
  - name: Pessoa
    kind_of: Entity
  - name: Suspeito
    kind_of: Pessoa

semantic_links:
  - name: Surveilled
    kind_of: Link

semantic_properties:
  - name: CPF
    base_property: Abstract Text
```

GUIDs are generated deterministically from the name when omitted.

### Option B -- skip semantic types

Leave `semantic_*` and `semantic_type=` unset. The chart still builds and opens in ANB; you only lose the library-aware features (palette filtering, type-aware search, Esri Maps).

---

## Custom semantic types

Custom types extend the standard library hierarchy. They are embedded in the `lcx:LibraryCatalogue` section of the ANX file.

### Prerequisites

If a custom type's `kind_of` / `base_property` references a standard i2 type (e.g. `Person`, `Phone Call To`), that standard type must first be made known to the chart via an explicit `semantic_entities` / `semantic_links` / `semantic_properties` entry in your config.

If your custom types only extend the abstract roots anxwritter ships (`Entity`, `Link`, `Abstract Text`/`Number`/`Date & Time`/`Flag`), no prerequisite is needed.

### Defining custom types

```python
from anxwritter import ANXChart, SemanticEntity, SemanticLink, SemanticProperty

chart = ANXChart(config_file='your-config.yaml')

# Custom entity semantic type
chart.add_semantic_entity(
    name='Suspect',
    kind_of='Person',
    synonyms=['Suspeito', 'POI'],
    description='Person under investigation',
)

# Custom link semantic type
chart.add_semantic_link(
    name='Intercepted Call',
    kind_of='Phone Call To',
    description='Lawfully intercepted phone call',
)

# Custom property semantic type
chart.add_semantic_property(
    name='CPF Number',
    base_property='Abstract Text',
    synonyms=['CPF', 'Cadastro de Pessoa Fisica'],
    description='Brazilian taxpayer ID',
)
```

---

## `SemanticEntity` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `''` | Type name (required). Maps to `<TypeName>` in XML. |
| `kind_of` | `str` | `''` | Parent entity type name (required). Must exist in catalogue or custom definitions. |
| `guid` | `str` | `None` | Override GUID. When `None`, a deterministic UUID5 is auto-generated. |
| `abstract` | `bool` | `False` | Whether this is an abstract type (non-instantiable). |
| `synonyms` | `List[str]` | `None` | Synonym entries in `Documentation > lcx:Synonym`. Used for the semantic picker search. |
| `description` | `str` | `None` | Description text in `Documentation > Description`. |

---

## `SemanticLink` fields

Same structure as `SemanticEntity`. The `kind_of` field references a parent link type name.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `''` | Type name (required). |
| `kind_of` | `str` | `''` | Parent link type name (required). |
| `guid` | `str` | `None` | Override GUID. Auto-generated if `None`. |
| `abstract` | `bool` | `False` | Whether this is an abstract type. |
| `synonyms` | `List[str]` | `None` | Synonym entries. |
| `description` | `str` | `None` | Description text. |

---

## `SemanticProperty` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `''` | Property name (required). Maps to `<PropertyName>` in XML. |
| `base_property` | `str` | `''` | Parent property name (required). Must exist in catalogue or custom definitions. |
| `guid` | `str` | `None` | Override GUID. Auto-generated if `None`. |
| `abstract` | `bool` | `False` | Whether this is an abstract type. |
| `synonyms` | `List[str]` | `None` | Synonym entries. |
| `description` | `str` | `None` | Description text. |

---

## Per-instance semantic override

Entity and link instances can override the type-level semantic type definition via their `semantic_type` field. Property (attribute class) semantic types cannot be overridden per-instance.

| Item | Per-instance override | How |
|------|----------------------|-----|
| Entity | Yes | `semantic_type` field on `Icon`, `Box`, `Circle`, etc. |
| Link | Yes | `semantic_type` field on `Link` |
| Property (AttributeClass) | **No** | `SemanticTypeGuid` on `<AttributeClass>` is locked at the class level. |

```python
# Type-level definition
chart.add_entity_type(name='Person', semantic_type='Person')

# Per-instance override
chart.add_icon(id='Alice', type='Person', semantic_type='Suspect')
chart.add_link(from_id='Alice', to_id='Bob', type='Call', semantic_type='Intercepted Call')
```

---

## Referencing semantic types

The `semantic_type` field on `EntityType`, `LinkType`, and `AttributeClass` is resolved at build time.

```python
chart.add_entity_type(name='Person', semantic_type='Person')
chart.add_link_type(name='Call', semantic_type='Phone Call To')
chart.add_attribute_class(name='Phone', type='text', semantic_type='Phone Number')
```

---

## Name resolution order

When a `semantic_type` string is resolved to a GUID, the following lookup order is used:

1. **Raw GUID passthrough** -- if the string starts with `'guid'`, it is used as-is (for advanced users and manual GUID assignment).
2. **Definitions from `add_semantic_entity`/`add_semantic_link`/`add_semantic_property`** -- standard types defined with explicit `guid` values or custom types with auto-generated GUIDs.

**`LNEntityPerson`-style names are INVALID.** ANB keyref validation rejects them. Use the standard type name (e.g. `'Person'`) or a raw GUID.

---

## Catalogue emission rules

- The `<lcx:LibraryCatalogue>` is emitted whenever (a) `semantic_type` is set on at least one `EntityType`, `LinkType`, `AttributeClass`, or entity/link instance, **or** (b) any custom semantic type is defined via `add_semantic_entity` / `add_semantic_link` / `add_semantic_property` (even if nothing references it).
- The catalogue contains the **full ancestor chain** for every referenced type (root -> ... -> referenced type).
- Custom types with `synonyms` or `description` emit a `<Documentation>` container.
- `<Description>` is **mandatory** inside `<Documentation>`. ANB rejects `<Documentation>` without it.
- `<ImageFile>` inside `lcx:Type` does **not** set the entity icon. It only affects the semantic picker UI. Not supported by the API.

### XML structure

```xml
<Chart xmlns:lcx="http://www.i2group.com/Schemas/2001-12-07/LCXSchema">
  <ApplicationVersion .../>
  <lcx:LibraryCatalogue VersionMajor="1" VersionMinor="18" ...>
    <lcx:Type tGUID="guid..." kindOf="guidPARENT..." abstract="true">
      <TypeName>Entity</TypeName>
    </lcx:Type>
    <lcx:Type tGUID="guidCUSTOM..." kindOf="guidPERSON...">
      <TypeName>Suspect</TypeName>
      <Documentation>
        <lcx:Synonym>Suspeito</lcx:Synonym>
        <Description>Person under investigation</Description>
      </Documentation>
    </lcx:Type>
    <lcx:Property pGUID="guid..." baseProperty="guidPARENT...">
      <PropertyName>CPF Number</PropertyName>
    </lcx:Property>
  </lcx:LibraryCatalogue>
  ...
```

---

## Known multi-tab rendering issue in ANB v9

Observed quirk: when opening any chart with `lcx:LibraryCatalogue` in a second ANB tab, a ghost link type with a GUID name appears in the palette. This is an ANB multi-tab rendering issue, not an XML problem with the chart. It occurs even when the same chart is opened twice.

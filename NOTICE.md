# NOTICE

anxwritter is an independent, MIT-licensed Python library for writing
i2 Analyst's Notebook Exchange (`.anx`) files. It is not affiliated
with, endorsed by, or sponsored by the makers of i2 Analyst's Notebook
(past or present: IBM, i2 Group Limited, i2 Limited, N.Harris Computer
Corporation, Harris Computer Corporation, Constellation Software Inc.)
or by Esri, Microsoft, or Google.

## Format identifiers reproduced for interoperability

To produce structurally valid `.anx` files, this library embeds nine
functional identifiers required by ANB:

- 6 abstract-root GUIDs required by the `lcx:LibraryCatalogue` schema
- 3 geo-map property GUIDs (Latitude, Longitude, Grid Reference)
  required by ANB's Esri Maps subsystem
- the LCX XML namespace string `http://www.i2group.com/Schemas/2001-12-07/LCXSchema`

These are functional format anchors, not creative content, reproduced
solely for interoperability.

## What is *not* included

anxwritter ships **none** of the following from i2/N.Harris/IBM ANB:
XML schemas (XSDs/XSLs), icon catalogues or image files,
standard-library semantic-type definitions, palette definitions,
compiled binaries, DLLs, `.ant` files, help text, or error messages.

All such content must be supplied by the user via their own `entity_types`,
`link_types`, `attribute_classes`, and `semantic_*` declarations.

## Trademarks

"i2", "i2 Analyst's Notebook", "ANB", "Esri", "Esri Maps",
"Microsoft", and "Google" are trademarks of their respective owners.
Referenced for nominative use only.

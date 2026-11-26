# OMG language artifact relational ingestion

This package registers every entry in `data/manifest.json`, parses XMI into shared relational tables, and preserves other formats in the artifact registry until a format-specific parser is added. It extracts mapping-rule definitions from `SysMLv1Tov2.xmi` into a separate rule table.

## Run with SQLite

```powershell
python -m pip install -r db/requirements.txt
python db/ingest.py --manifest data/manifest.json --database-url sqlite:///language_artifacts.sqlite
```

## Run with PostgreSQL

The importer loads `PG_CONN` from the repository `.env` by default and creates/uses the PostgreSQL `sysml` schema:

```powershell
python db/ingest.py --manifest data/manifest.json
```

To override the connection or schema, pass `--database-url` and `--schema` explicitly.

The same tables are used in both engines. PostgreSQL creates and uses the `sysml` schema by default; table names also use a `lang_` prefix so the table set remains distinct in SQLite, which has no PostgreSQL-style named schemas. UUIDs and timestamps are stored as text, and manifest/property JSON is stored as text for portability.

## Tables

- `lang_artifact`: immutable source identity, manifest provenance, local path, optional S3-compatible `object_uri`, checksum, parse status, and model namespace URI.
- `lang_ingestion_run`: ingestion run history and summary.
- `lang_element`: every XML node in a parsed XMI document, including its XMI ID (when present), metaclass, XML tag, name, parent, ordinal, and source path.
- `lang_element_property`: every XML attribute and non-empty text value, preserving the original property name, value, and location.
- `lang_relationship`: XMI `href`, `idref`, and common shorthand reference attributes, with raw target, target fragment/URI, resolution result, and relationship kind. Local XMI IDs resolve within the artifact; external targets resolve only when an imported model URI matches exactly.
- `lang_element_mapping`: reviewed or extractor-produced cross-language/version mappings with source, target, evidence artifact/element, method, confidence, and status.
- `lang_mapping_rule`: mapping classes extracted from the SysML v1-to-v2 transformation model, including their declared `from` base type and a target type hint derived from the rule name. A hint is not treated as a resolved element mapping.

SysML and UML artifact metadata are both registered. XMI artifacts in either specification are parsed. In particular, the SysML v1 to v2 transformation XMI is flagged as a `CROSSWALK` evidence artifact; its elements and relationships are preserved, and its 783 mapping-rule class definitions are indexed. The mapping table remains for links between concrete language elements; the extracted rule hints are not asserted as those links.

The raw artifact bytes remain in the landing directory. `object_uri` is available for an S3-compatible object-store pointer; this script does not upload files to a bucket.

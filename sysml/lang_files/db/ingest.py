from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from sqlalchemy import delete, insert, select, text, update

try:
    from .schema import artifacts, create_schema, make_engine, mapping_rules, mappings, nodes, properties, references, runs
except ImportError:  # direct script execution
    from schema import artifacts, create_schema, make_engine, mapping_rules, mappings, nodes, properties, references, runs

PARSER_VERSION = "0.1.0"
XMI_NAMESPACES = {
    "http://www.omg.org/spec/XMI/20131001",
    "http://www.omg.org/spec/XMI/20161101",
    "http://www.omg.org/spec/XMI/20090901",
    "http://www.omg.org/spec/XMI/20071001",
    "http://www.omg.org/spec/XMI/20050501",
}
REFERENCE_ATTRIBUTE_NAMES = {
    "idref", "href", "general", "memberend", "client", "supplier",
    "annotatedelement", "constrainedelement", "subsettedproperty",
    "redefinedproperty", "redefinedoperation", "importedpackage",
    "association", "opposite", "ownedend", "type",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_name(qname: str) -> str:
    return qname.rsplit("}", 1)[-1] if "}" in qname else qname.split(":", 1)[-1]


def namespace_uri(qname: str) -> str | None:
    return qname[1:].split("}", 1)[0] if qname.startswith("{") else None


def xmi_attribute(element: ET.Element, wanted: str) -> str | None:
    for key, value in element.attrib.items():
        ns = namespace_uri(key)
        if local_name(key) == wanted and ns and "xmi" in ns.lower():
            return value
    # Older XMI commonly uses a prefix; ElementTree retains expanded names when bound.
    return None


def stable_id(namespace: uuid.UUID, key: str) -> str:
    return str(uuid.uuid5(namespace, key))


def parse_reference(raw: str) -> tuple[str | None, str | None, str | None]:
    """Return URI, fragment, and a likely local XMI id from an href/idref value."""
    value = raw.strip()
    if not value:
        return None, None, None
    if value.startswith("#"):
        return None, value[1:], value[1:]
    if "#" in value:
        uri, fragment = value.rsplit("#", 1)
        return uri or None, fragment or None, fragment or None
    if "://" in value or value.startswith("urn:"):
        return value, None, None
    return None, None, value


def load_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in manifest: {path}")
    return data


def resolve_local_path(manifest_dir: Path, entry: dict) -> Path | None:
    value = entry.get("local_path")
    candidates: list[Path] = []
    if value:
        path = Path(value)
        if path.is_absolute():
            candidates.append(path)
        else:
            # Support legacy paths relative to either the manifest or its parent.
            candidates.extend([manifest_dir / path, manifest_dir.parent / path])

    # The current manifest-backed landing tree is data/<spec>/<version>/<file>.
    filename = entry.get("filename")
    specification = entry.get("specification")
    version = entry.get("version")
    if filename and specification and version:
        candidates.append(manifest_dir / str(specification) / str(version) / str(filename))

    found = next((candidate for candidate in candidates if candidate.is_file()), None)
    return found if found is not None else (candidates[0] if candidates else None)


def artifact_id_for(entry: dict) -> str:
    identity = "|".join(str(entry.get(k) or "") for k in ("specification", "version", "url", "sha256"))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "OMG-artifact:" + identity))


def artifact_record(entry: dict, path: Path | None) -> dict:
    return {
        "artifact_id": artifact_id_for(entry),
        "source": entry.get("source") or "OMG",
        "specification": entry.get("specification") or "UNKNOWN",
        "version": entry.get("version"),
        "omg_file_id": entry.get("omg_file_id"),
        "filename": entry.get("filename") or (path.name if path else "unknown"),
        "format": (entry.get("format") or Path(entry.get("filename") or "").suffix.lstrip(".") or "UNKNOWN").upper(),
        "artifact_role": "CROSSWALK" if "v1tov2" in str(entry.get("filename", "")).lower() else "MODEL",
        "description": entry.get("description"),
        "normative_status": entry.get("normative_status"),
        "url": entry.get("url") or "",
        "sha256": entry.get("sha256"),
        "local_path": str(path.resolve()) if path else entry.get("local_path"),
        "object_uri": entry.get("object_uri"),
        "model_uri": None,
        "retrieved_at": entry.get("retrieved_at"),
        "http_status": entry.get("http_status"),
        "download_status": entry.get("download_status"),
        "parse_status": "REGISTERED",
        "parse_error": None,
        "manifest_json": json.dumps(entry, ensure_ascii=False, sort_keys=True),
    }


def _insert_batches(conn, table, rows: list[dict], batch_size: int = 1000) -> None:
    for start in range(0, len(rows), batch_size):
        conn.execute(insert(table), rows[start : start + batch_size])


def parse_xmi(conn, artifact: dict, path: Path, batch_size: int = 1000) -> tuple[int, int, str | None]:
    """Parse plain XMI or the XMI member of a ZIP-based catalog artifact."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            xmi_members = [name for name in archive.namelist() if name.lower().endswith(".xmi")]
            if not xmi_members:
                raise ValueError("Archive contains no .xmi member")
            preferred = Path(artifact["filename"]).name.lower()
            member = next((name for name in xmi_members if Path(name).name.lower() == preferred), xmi_members[0])
            with archive.open(member) as stream:
                return _parse_xmi_stream(conn, artifact, stream, batch_size)
    return _parse_xmi_stream(conn, artifact, path, batch_size)


def _parse_xmi_stream(conn, artifact: dict, source, batch_size: int = 1000) -> tuple[int, int, str | None]:
    """Stream an XMI document into nodes, scalar properties, and reference edges."""
    artifact_uuid = uuid.UUID(artifact["artifact_id"])
    node_count = property_count = 0
    node_batch: list[dict] = []
    prop_batch: list[dict] = []
    ref_batch: list[dict] = []
    id_to_node: dict[str, str] = {}
    stack: list[dict] = []
    first_model_uri = None
    ordinal = 0
    sibling_counts: list[dict[str, int]] = []

    for event, elem in ET.iterparse(source, events=("start", "end")):
        tag = local_name(elem.tag)
        if event == "start":
            ordinal += 1
            parent_id = stack[-1]["element_id"] if stack else None
            parent_path = stack[-1]["xml_path"] if stack else ""
            if sibling_counts:
                counts = sibling_counts[-1]
                counts[tag] = counts.get(tag, 0) + 1
                position = counts[tag]
            else:
                position = 1
            xml_path = f"{parent_path}/{tag}[{position}]"
            element_id = stable_id(artifact_uuid, f"node:{ordinal}")
            xmi_id = xmi_attribute(elem, "id")
            metaclass = xmi_attribute(elem, "type")
            name = next((v for k, v in elem.attrib.items() if local_name(k) == "name"), None)
            if xmi_id:
                id_to_node.setdefault(xmi_id, element_id)
            if first_model_uri is None:
                first_model_uri = next((v for k, v in elem.attrib.items() if local_name(k) in {"URI", "nsURI"}), None)

            node_batch.append({
                "element_id": element_id, "artifact_id": artifact["artifact_id"],
                "parent_element_id": parent_id, "ordinal": ordinal, "xmi_id": xmi_id,
                "metaclass": metaclass, "xml_tag": tag, "namespace_uri": namespace_uri(elem.tag),
                "name": name, "xml_path": xml_path,
            })
            for attr_index, (key, value) in enumerate(elem.attrib.items(), start=1):
                attr_name = "@" + local_name(key)
                prop_batch.append({
                    "property_id": stable_id(artifact_uuid, f"property:{ordinal}:attr:{attr_index}"),
                    "element_id": element_id, "property_name": attr_name, "value_text": value,
                    "value_kind": "ATTRIBUTE", "ordinal": attr_index, "xml_path": xml_path,
                    "attributes_json": json.dumps({"qualified_name": key, "namespace_uri": namespace_uri(key)}, ensure_ascii=False),
                })
                attr_local = local_name(key).lower()
                attr_ns = namespace_uri(key)
                # Namespaced xmi:type describes a metaclass; unqualified `type`
                # and known relationship attributes can carry XMI ID references.
                is_xmi_type = attr_local == "type" and attr_ns and "xmi" in attr_ns.lower()
                if attr_local in REFERENCE_ATTRIBUTE_NAMES and not is_xmi_type:
                    targets = value.split() if attr_local in {"memberend", "client", "supplier", "annotatedelement", "constrainedelement"} else [value]
                    for target_index, target in enumerate(targets, start=1):
                        if attr_local == "type" and ":" in target and "://" not in target:
                            continue
                        target_uri, target_fragment, target_xmi_id = parse_reference(target)
                        ref_key = f"reference:{ordinal}:attr:{attr_index}:target:{target_index}"
                        ref_batch.append({
                            "reference_id": stable_id(artifact_uuid, ref_key),
                            "artifact_id": artifact["artifact_id"], "source_element_id": element_id,
                            "reference_kind": attr_local.upper(), "relationship_kind": tag,
                            "target_raw": target, "target_uri": target_uri,
                            "target_fragment": target_fragment, "target_xmi_id": target_xmi_id,
                            "target_element_id": None,
                            "resolution_status": "PENDING", "xml_path": xml_path,
                        })
            if len(node_batch) >= batch_size:
                _insert_batches(conn, nodes, node_batch, batch_size)
                node_count += len(node_batch)
                node_batch.clear()
            if len(prop_batch) >= batch_size:
                if node_batch:
                    _insert_batches(conn, nodes, node_batch, batch_size)
                    node_count += len(node_batch)
                    node_batch.clear()
                _insert_batches(conn, properties, prop_batch, batch_size)
                property_count += len(prop_batch)
                prop_batch.clear()
            if len(ref_batch) >= batch_size:
                if node_batch:
                    _insert_batches(conn, nodes, node_batch, batch_size)
                    node_count += len(node_batch)
                    node_batch.clear()
                _insert_batches(conn, references, ref_batch, batch_size)
                ref_batch.clear()
            stack.append({"element_id": element_id, "xml_path": xml_path, "ordinal": ordinal})
            sibling_counts.append({})
        else:
            current = stack[-1]
            if elem.text and elem.text.strip():
                prop_batch.append({
                    "property_id": stable_id(artifact_uuid, f"property:{current['ordinal']}:text"),
                    "element_id": current["element_id"], "property_name": "#text",
                    "value_text": elem.text.strip(), "value_kind": "TEXT", "ordinal": 0,
                    "xml_path": current["xml_path"], "attributes_json": None,
                })
                if len(prop_batch) >= batch_size:
                    if node_batch:
                        _insert_batches(conn, nodes, node_batch, batch_size)
                        node_count += len(node_batch)
                        node_batch.clear()
                    _insert_batches(conn, properties, prop_batch, batch_size)
                    property_count += len(prop_batch)
                    prop_batch.clear()
            stack.pop()
            sibling_counts.pop()
            elem.clear()

    if node_batch:
        _insert_batches(conn, nodes, node_batch, batch_size)
        node_count += len(node_batch)
    if prop_batch:
        _insert_batches(conn, properties, prop_batch, batch_size)
        property_count += len(prop_batch)
    if ref_batch:
        _insert_batches(conn, references, ref_batch, batch_size)

    # Resolve local XMI ids after the complete artifact has been indexed.
    for xmi_id, target_id in id_to_node.items():
        conn.execute(
            update(references)
            .where(references.c.artifact_id == artifact["artifact_id"])
            .where(references.c.target_xmi_id == xmi_id)
            .values(target_element_id=target_id, resolution_status="RESOLVED_LOCAL")
        )
    conn.execute(
        update(references)
        .where(references.c.artifact_id == artifact["artifact_id"])
        .where(references.c.resolution_status == "PENDING")
        .values(resolution_status="UNRESOLVED")
    )
    return node_count, property_count, first_model_uri


def _delete_parsed_artifact(conn, artifact_id: str) -> None:
    # Delete explicit children first for portable FK behavior.
    element_ids = select(nodes.c.element_id).where(nodes.c.artifact_id == artifact_id)
    conn.execute(delete(mappings).where(mappings.c.evidence_artifact_id == artifact_id))
    conn.execute(delete(references).where(references.c.artifact_id == artifact_id))
    conn.execute(delete(properties).where(properties.c.element_id.in_(element_ids)))
    conn.execute(delete(nodes).where(nodes.c.artifact_id == artifact_id))


def resolve_external_references(engine, schema_name: str = "sysml") -> int:
    """Resolve URI#fragment references using exact model or artifact URI paths."""
    with engine.begin() as conn:
        parsed_artifacts = conn.execute(
            select(artifacts.c.artifact_id, artifacts.c.url, artifacts.c.model_uri, artifacts.c.filename)
            .where(artifacts.c.parse_status == "PARSED")
        ).mappings().all()
        artifact_by_path: dict[str, str] = {}

        def uri_path(value: str | None) -> str | None:
            if not value:
                return None
            path = urlsplit(value).path.rstrip("/")
            return path or None

        for model in parsed_artifacts:
            candidates = [uri_path(model["url"]), uri_path(model["model_uri"])]
            base_path = uri_path(model["model_uri"])
            if base_path:
                candidates.append(base_path + "/" + model["filename"])
            for candidate in candidates:
                if candidate:
                    artifact_by_path.setdefault(candidate, model["artifact_id"])

        pending = conn.execute(
            select(references.c.target_uri, references.c.target_fragment)
            .where(references.c.resolution_status == "UNRESOLVED")
            .where(references.c.target_uri.is_not(None))
            .where(references.c.target_fragment.is_not(None))
            .distinct()
        ).all()
        target_pairs: list[tuple[str, str, str]] = []
        wanted_fragments: dict[str, set[str]] = {}
        for ref in pending:
            target_artifact_id = artifact_by_path.get(uri_path(ref[0]) or "")
            if not target_artifact_id:
                continue
            wanted_fragments.setdefault(target_artifact_id, set()).add(ref[1])
            target_pairs.append((ref[0], ref[1], target_artifact_id))

        elements_by_artifact: dict[str, dict[str, str]] = {}
        for target_artifact_id, fragments in wanted_fragments.items():
            rows = conn.execute(
                select(nodes.c.xmi_id, nodes.c.element_id)
                .where(nodes.c.artifact_id == target_artifact_id)
                .where(nodes.c.xmi_id.is_not(None))
            )
            elements_by_artifact[target_artifact_id] = {
                row.xmi_id: row.element_id for row in rows if row.xmi_id in fragments
            }

        resolution_rows = []
        for target_uri, fragment, target_artifact_id in target_pairs:
            target_element_id = elements_by_artifact[target_artifact_id].get(fragment)
            if target_element_id:
                resolution_rows.append({
                    "target_uri": target_uri,
                    "target_fragment": fragment,
                    "target_element_id": target_element_id,
                })
        if not resolution_rows:
            return 0

        # A temporary lookup table allows one set-based update instead of one
        # table scan per reference, on both SQLite and PostgreSQL.
        conn.exec_driver_sql(
            "CREATE TEMPORARY TABLE _lang_target_resolution "
            "(target_uri TEXT NOT NULL, target_fragment TEXT NOT NULL, "
            "target_element_id TEXT NOT NULL, PRIMARY KEY (target_uri, target_fragment))"
        )
        conn.execute(text(
            "INSERT INTO _lang_target_resolution "
            "(target_uri, target_fragment, target_element_id) "
            "VALUES (:target_uri, :target_fragment, :target_element_id)"
        ), resolution_rows)
        relationship_table = f'"{schema_name}"."lang_relationship"' if engine.dialect.name == "postgresql" else '"lang_relationship"'
        result = conn.exec_driver_sql(
            f"UPDATE {relationship_table} AS r "
            "SET target_element_id = (SELECT m.target_element_id "
            "FROM _lang_target_resolution m "
            "WHERE m.target_uri = r.target_uri "
            "AND m.target_fragment = r.target_fragment), "
            "resolution_status = 'RESOLVED_EXTERNAL' "
            "WHERE r.resolution_status = 'UNRESOLVED' "
            "AND EXISTS (SELECT 1 FROM _lang_target_resolution m "
            "WHERE m.target_uri = r.target_uri "
            "AND m.target_fragment = r.target_fragment)"
        )
        resolved = max(result.rowcount or 0, 0)
        conn.exec_driver_sql("DROP TABLE _lang_target_resolution")
        return resolved


def extract_crosswalk_rules(engine) -> int:
    """Index explicit mapping-rule classes from the SysML v1-to-v2 XMI.

    This records rule definitions and their declared `from` base type. The
    rule name is retained only as a target type hint; it is not asserted to be
    an element-to-element mapping.
    """
    total = 0
    with engine.begin() as conn:
        crosswalks = conn.execute(
            select(artifacts.c.artifact_id)
            .where(artifacts.c.artifact_role == "CROSSWALK")
            .where(artifacts.c.parse_status == "PARSED")
        ).scalars().all()
        for artifact_id in crosswalks:
            conn.execute(delete(mapping_rules).where(mapping_rules.c.artifact_id == artifact_id))
            class_rows = conn.execute(
                select(nodes.c.element_id, nodes.c.xmi_id, nodes.c.name)
                .where(nodes.c.artifact_id == artifact_id)
                .where(nodes.c.metaclass == "uml:Class")
                .where(nodes.c.name.is_not(None))
            ).mappings().all()
            rules = [row for row in class_rows if row["name"].endswith("_Mapping")]
            if not rules:
                continue
            rule_ids = [row["element_id"] for row in rules]
            from_attributes = conn.execute(
                select(nodes.c.element_id, nodes.c.parent_element_id)
                .where(nodes.c.parent_element_id.in_(rule_ids))
                .where(nodes.c.xml_tag == "ownedAttribute")
                .where(nodes.c.name == "from")
            ).all()
            from_to_rule = {attr_id: rule_id for attr_id, rule_id in from_attributes}
            type_nodes = conn.execute(
                select(nodes.c.element_id, nodes.c.parent_element_id)
                .where(nodes.c.parent_element_id.in_(list(from_to_rule)))
                .where(nodes.c.xml_tag == "type")
            ).all() if from_to_rule else []
            type_to_rule = {type_id: from_to_rule[parent_id] for type_id, parent_id in type_nodes}
            type_refs = conn.execute(
                select(references.c.source_element_id, references.c.reference_id,
                       references.c.target_uri, references.c.target_fragment)
                .where(references.c.source_element_id.in_(list(type_to_rule)))
                .where(references.c.reference_kind == "HREF")
            ).mappings().all() if type_to_rule else []
            source_type_by_rule = {
                type_to_rule[row["source_element_id"]]: row for row in type_refs
            }
            rows = []
            for rule in rules:
                source_type = source_type_by_rule.get(rule["element_id"])
                rule_name = rule["name"]
                rows.append({
                    "mapping_rule_id": stable_id(uuid.UUID(artifact_id), f"mapping-rule:{rule['element_id']}"),
                    "artifact_id": artifact_id,
                    "mapping_element_id": rule["element_id"],
                    "rule_name": rule_name,
                    "source_type_uri": source_type["target_uri"] if source_type else None,
                    "source_type_fragment": source_type["target_fragment"] if source_type else None,
                    "target_type_hint": rule_name[:-8],
                    "extraction_method": "TRANSFORMATION_MAPPING_CLASS_AND_FROM_TYPE",
                    "rule_status": "RULE_DEFINITION",
                    "evidence_json": json.dumps({
                        "xmi_id": rule["xmi_id"],
                        "from_type_reference_id": source_type["reference_id"] if source_type else None,
                    }, sort_keys=True),
                })
            _insert_batches(conn, mapping_rules, rows)
            total += len(rows)
    return total


def ingest_manifest(
    manifest_path: Path,
    database_url: str,
    only_formats: set[str] | None = None,
    schema_name: str = "sysml",
) -> dict:
    entries = load_manifest(manifest_path)
    engine = make_engine(database_url, schema_name=schema_name)
    create_schema(engine)
    run_id = str(uuid.uuid4())
    started = utc_now()
    counts = {"artifacts": 0, "parsed": 0, "skipped_unchanged": 0, "registered_only": 0, "failed": 0, "elements": 0, "properties": 0}

    with engine.begin() as conn:
        conn.execute(insert(runs).values(
            run_id=run_id, started_at=started, status="RUNNING", parser_version=PARSER_VERSION,
            database_dialect=engine.dialect.name,
        ))

    for entry in entries:
        path = resolve_local_path(manifest_path.parent, entry)
        artifact = artifact_record(entry, path)
        counts["artifacts"] += 1
        fmt = artifact["format"].upper()
        is_xmi = fmt == "XMI" or (path is not None and path.suffix.lower() == ".xmi")
        should_parse = is_xmi and (only_formats is None or fmt in only_formats)
        with engine.begin() as conn:
            existing = conn.execute(
                select(artifacts.c.parse_status, artifacts.c.sha256)
                .where(artifacts.c.artifact_id == artifact["artifact_id"])
            ).first()
            if existing:
                conn.execute(artifacts.update().where(artifacts.c.artifact_id == artifact["artifact_id"]).values(
                    **{k: v for k, v in artifact.items() if k not in {"artifact_id", "parse_status", "parse_error", "model_uri"}}
                ))
            else:
                conn.execute(insert(artifacts).values(**artifact))
            if not should_parse:
                conn.execute(artifacts.update().where(artifacts.c.artifact_id == artifact["artifact_id"]).values(parse_status="REGISTERED" if path and path.is_file() else "MISSING_FILE"))
                counts["registered_only"] += 1
                continue
            if path is None or not path.is_file():
                conn.execute(artifacts.update().where(artifacts.c.artifact_id == artifact["artifact_id"]).values(parse_status="MISSING_FILE", parse_error="Local artifact path not found"))
                counts["failed"] += 1
                continue
            digest = hashlib.sha256()
            with path.open("rb") as source_file:
                for block in iter(lambda: source_file.read(1024 * 1024), b""):
                    digest.update(block)
            actual_hash = digest.hexdigest()
            if artifact["sha256"] and actual_hash.lower() != artifact["sha256"].lower():
                conn.execute(artifacts.update().where(artifacts.c.artifact_id == artifact["artifact_id"]).values(parse_status="FAILED", parse_error="SHA-256 does not match manifest"))
                counts["failed"] += 1
                continue
            if existing and existing[0] == "PARSED" and existing[1] == artifact["sha256"]:
                counts["skipped_unchanged"] += 1
                continue
            try:
                with conn.begin_nested():
                    _delete_parsed_artifact(conn, artifact["artifact_id"])
                    n_nodes, n_props, model_uri = parse_xmi(conn, artifact, path)
            except (ET.ParseError, OSError, ValueError) as exc:
                conn.execute(artifacts.update().where(artifacts.c.artifact_id == artifact["artifact_id"]).values(
                    parse_status="FAILED", parse_error=f"{type(exc).__name__}: {exc}",
                ))
                counts["failed"] += 1
                continue
            conn.execute(artifacts.update().where(artifacts.c.artifact_id == artifact["artifact_id"]).values(
                parse_status="PARSED", parse_error=None, model_uri=model_uri,
            ))
            counts["parsed"] += 1
            counts["elements"] += n_nodes
            counts["properties"] += n_props

    completed = utc_now()
    counts["external_references_resolved"] = resolve_external_references(engine, schema_name=schema_name)
    counts["crosswalk_rules_extracted"] = extract_crosswalk_rules(engine)
    status = "COMPLETED_WITH_ERRORS" if counts["failed"] else "COMPLETED"
    with engine.begin() as conn:
        conn.execute(runs.update().where(runs.c.run_id == run_id).values(
            completed_at=completed, status=status, summary_json=json.dumps(counts, sort_keys=True),
        ))
    engine.dispose()
    return {"run_id": run_id, "status": status, **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Register OMG manifest artifacts and parse XMI into portable relational tables.")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "manifest.json")
    parser.add_argument("--database-url", help="Defaults to PG_CONN from the repo .env, then local SQLite.")
    parser.add_argument("--schema", default="sysml", help="PostgreSQL schema name (default: sysml).")
    parser.add_argument("--formats", nargs="*", help="Restrict parsing to these formats (default: XMI). Other artifacts remain registered.")
    args = parser.parse_args()
    from dotenv import load_dotenv
    repo_env = Path(__file__).resolve().parents[3] / ".env"
    if repo_env.is_file():
        load_dotenv(repo_env, override=False)
    database_url = args.database_url or os.environ.get("PG_CONN") or "sqlite:///language_artifacts.sqlite"
    manifest_path = args.manifest
    if not manifest_path.is_absolute() and not manifest_path.is_file():
        lang_files_relative = Path(__file__).resolve().parents[1] / manifest_path
        if lang_files_relative.is_file():
            manifest_path = lang_files_relative
    try:
        result = ingest_manifest(
            manifest_path,
            database_url,
            set(x.upper() for x in args.formats) if args.formats else None,
            schema_name=args.schema,
        )
    except FileNotFoundError as exc:
        missing_path = getattr(exc, "filename", None)
        print(f"Ingestion failed (FileNotFoundError): {missing_path or 'the manifest or an input file was not found'}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Ingestion failed ({type(exc).__name__}). Check database connectivity and permissions.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

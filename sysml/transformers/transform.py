from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

XMI_NS = "http://www.omg.org/spec/XMI/20131001"
UML_NS = "http://www.omg.org/spec/UML/20161101"
SYSML_NS = "http://www.omg.org/spec/SysML/20181001/SysML"
ET.register_namespace("xmi", XMI_NS)
ET.register_namespace("uml", UML_NS)
ET.register_namespace("sysml", SYSML_NS)

def qname(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"

def safe_id(prefix: str, label: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(label)).strip("_")
    if not token:
        token = "element"
    if token[0].isdigit():
        token = "e_" + token
    return f"{prefix}_{token}"

def validate_input(data: dict[str, Any]) -> tuple[list[tuple[str, str, str]], dict, dict, dict]:
    if "triples" not in data:
        raise ValueError("Input JSON must contain a 'triples' list.")
    triples = []
    for i, triple in enumerate(data["triples"]):
        if not isinstance(triple, (list, tuple)) or len(triple) != 3:
            raise ValueError(f"Triple at index {i} must contain exactly [subject, predicate, object].")
        s, p, o = (str(part).strip() for part in triple)
        if not s or not p or not o:
            raise ValueError(f"Triple at index {i} contains an empty subject, predicate, or object.")
        triples.append((s, p, o))
    return (
        triples, 
        data.get("object_definitions") or {}, 
        data.get("predicate_definitions") or {}, 
        data.get("predicate_definitions_mapping") or {},
        )

def build_model(
    triples: list[tuple[str, str, str]],
    object_definitions: dict[str, str],
    predicate_definitions: dict[str, str],
    predicate_mapping: dict[str, dict[str, str]],
    target: str,
) -> ET.ElementTree:
    """Build a UML XMI model or a SysML 1.6-oriented UML XMI model."""
    is_sysml = target.lower() == "sysml"
    root = ET.Element(qname(XMI_NS, "XMI"), {qname(XMI_NS, "version"): "2.5.1"})
    model_id = "model_AutomotiveKnowledgeGraph_SysML16" if is_sysml else "model_AutomotiveKnowledgeGraph_UML"
    model_name = "AutomotiveKnowledgeGraph_SysML16" if is_sysml else "AutomotiveKnowledgeGraph_UML"
    model = ET.SubElement(root, qname(UML_NS, "Model"), {
        qname(XMI_NS, "id"): model_id,
        "name": model_name,
    })

    domain_pkg = ET.SubElement(model, "packagedElement", {qname(XMI_NS, "type"): "uml:Package", qname(XMI_NS, "id"): "pkg_DomainObjects", "name": "DomainObjects",})
    rel_pkg = ET.SubElement(model, "packagedElement", {qname(XMI_NS, "type"): "uml:Package", qname(XMI_NS, "id"): "pkg_Relationships", "name": "Relationships",})
    metadata_pkg = ET.SubElement(model, "packagedElement", {qname(XMI_NS, "type"): "uml:Package", qname(XMI_NS, "id"): "pkg_SemanticMetadata", "name": "SemanticMetadata",})

    objects = sorted(set(object_definitions) | {x for s, _, o in triples for x in (s, o)})
    object_ids: dict[str, str] = {}
    for name in objects:
        element_id = safe_id("class", name)
        object_ids[name] = element_id
        cls = ET.SubElement(domain_pkg, "packagedElement", {qname(XMI_NS, "type"): "uml:Class", qname(XMI_NS, "id"): element_id, "name": name,})
        comment = ET.SubElement(cls, "ownedComment", {qname(XMI_NS, "type"): "uml:Comment", qname(XMI_NS, "id"): safe_id("comment_obj", name),})
        ET.SubElement(comment, "body").text = str(object_definitions.get(name, "No object definition supplied."))

    # Every triple receives a distinct association ID, even if triples repeat.
    for index, (subject, predicate, obj) in enumerate(triples, start=1):
        assoc_id = f"assoc_{index:04d}_{safe_id('', predicate).strip('_') or 'relation'}"
        assoc = ET.SubElement(
            rel_pkg, 
            "packagedElement", 
            {qname(XMI_NS, "type"): "uml:Association", qname(XMI_NS, "id"): assoc_id, "name": predicate, "memberEnd": f"{assoc_id}_source {assoc_id}_target",}
            )
        source_end = {
            qname(XMI_NS, "type"): "uml:Property", 
            qname(XMI_NS, "id"): f"{assoc_id}_source", 
            "name": "source", 
            "type": object_ids[subject], 
            "association": assoc_id,
            }
        # This is an explicit modeling choice, not inferred from RDF alone.
        if predicate == "hasEngine":
            source_end["aggregation"] = "composite"
        ET.SubElement(assoc, "ownedEnd", source_end)
        ET.SubElement(assoc, "ownedEnd", {
            qname(XMI_NS, "type"): "uml:Property",
            qname(XMI_NS, "id"): f"{assoc_id}_target",
            "name": "target",
            "type": object_ids[obj],
            "association": assoc_id,
        })
        comment = ET.SubElement(assoc, "ownedComment", {qname(XMI_NS, "type"): "uml:Comment", qname(XMI_NS, "id"): f"{assoc_id}_comment",})
        mapping = predicate_mapping.get(predicate, {})
        target_mapping = mapping.get("sysml_equivalent" if is_sysml else "uml_equivalent", "")
        definition = predicate_definitions.get(predicate, mapping.get("definition", "No predicate definition supplied."))
        ET.SubElement(comment, "body").text = (
            f"Predicate: {predicate}\n"
            f"Definition: {definition}\n"
            f"Source: {subject}\nTarget: {obj}\n"
            f"Proposed {'SysML' if is_sysml else 'UML'} mapping: {target_mapping}\n"
            "Mapping note: retained as semantic metadata; validate suitability for the target metamodel."
        )

    # Predicate concepts are represented as documented metadata classes to retain definitions/mappings.
    predicates = sorted(set(predicate_definitions) | {p for _, p, _ in triples} | set(predicate_mapping))
    for predicate in predicates:
        pc = ET.SubElement(
            metadata_pkg, 
            "packagedElement", 
            {qname(XMI_NS, "type"): "uml:Class", qname(XMI_NS, "id"): safe_id("predicate", predicate), "name": predicate,}
            )
        pcomment = ET.SubElement(pc, "ownedComment", {qname(XMI_NS, "type"): "uml:Comment", qname(XMI_NS, "id"): safe_id("predicate_comment", predicate),})
        mapping = predicate_mapping.get(predicate, {})
        definition = predicate_definitions.get(predicate, mapping.get("definition", ""))
        ET.SubElement(pcomment, "body").text = (
            f"Definition: {definition}\n"
            f"UML equivalent: {mapping.get('uml_equivalent', '')}\n"
            f"SysML equivalent: {mapping.get('sysml_equivalent', '')}"
        )

    if is_sysml:
        # SysML 1.6 Block stereotype applications. Profile URI resolution may need
        # adjustment for the exact Cameo version / profile package used by the project.
        for name, class_id in object_ids.items():
            ET.SubElement(root, qname(SYSML_NS, "Block"), {qname(XMI_NS, "id"): safe_id("block_stereo", name), "base_Class": class_id,})
        profile_app = ET.SubElement(model, "profileApplication", {qname(XMI_NS, "id"): "profileApplication_SysML16",})
        annotation = ET.SubElement(profile_app, "eAnnotations", {"source": "http://www.eclipse.org/uml2/2.0.0/UML",})
        ET.SubElement(annotation, "details", {"key": "documentation", "value":
            "SysML 1.6 profile application; verify href/profile resolution in target Cameo release."})
        ET.SubElement(profile_app, "appliedProfile", {
            qname(XMI_NS, "type"): "uml:Profile",
            qname(XMI_NS, "href"): "http://www.omg.org/spec/SysML/20181001/SysML.xmi#_0",
        })

    return ET.ElementTree(root)

def validate_xmi(path: Path) -> dict[str, int]:
    tree = ET.parse(path)  # Raises ParseError if not well-formed XML.
    root = tree.getroot()
    ids = [el.attrib.get(qname(XMI_NS, "id")) for el in root.iter()
           if el.attrib.get(qname(XMI_NS, "id"))]
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    if duplicates:
        raise ValueError(f"Duplicate xmi:id values in {path.name}: {duplicates[:10]}")
    class_count = sum(
        1 for el in root.iter("packagedElement")
        if el.attrib.get(qname(XMI_NS, "type")) == "uml:Class"
    )
    assoc_count = sum(
        1 for el in root.iter("packagedElement")
        if el.attrib.get(qname(XMI_NS, "type")) == "uml:Association"
    )
    # Check every association end points to an existing class ID.
    class_ids = {
        el.attrib.get(qname(XMI_NS, "id"))
        for el in root.iter("packagedElement")
        if el.attrib.get(qname(XMI_NS, "type")) == "uml:Class"
    }
    for el in root.iter("ownedEnd"):
        type_id = el.attrib.get("type")
        if type_id and type_id not in class_ids:
            raise ValueError(f"Association end references unknown class ID: {type_id}")
    return {"classes_including_predicate_metadata": class_count,
            "associations": assoc_count, "unique_xmi_ids": len(ids)}

def convert_file(input_json: Path, out_dir: Path) -> dict[str, Any]:
    data = json.loads(input_json.read_text(encoding="utf-8"))
    triples, object_defs, predicate_defs, predicate_mapping = validate_input(data)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for target, filename in (
        ("uml", "AutomotiveKnowledgeGraph_UML.xmi"),
        ("sysml", "AutomotiveKnowledgeGraph_SysML16.xmi"),
    ):
        path = out_dir / filename
        tree = build_model(triples, object_defs, predicate_defs, predicate_mapping, target)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="UTF-8", xml_declaration=True)
        outputs[filename] = {"path": str(path), **validate_xmi(path)}
    return {"triples": len(triples), "outputs": outputs}

def main() -> int:
    parser = argparse.ArgumentParser(description="Convert RDF-style triples to UML and SysML XMI.")
    parser.add_argument("input_json", type=Path, help="JSON file containing triples and optional definitions.")
    parser.add_argument("--out-dir", type=Path, default=Path("cameo_xmi_output"),
                        help="Output directory (default: ./cameo_xmi_output)")
    args = parser.parse_args()
    try:
        result = convert_file(args.input_json, args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    print("\nNote: XML validation does not prove Cameo import compatibility.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
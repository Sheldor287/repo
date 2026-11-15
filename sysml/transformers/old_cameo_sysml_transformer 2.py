from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Optional, Union, get_args, get_origin, get_type_hints
import inspect
import json
import types
import uuid
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import networkx as nx


# ============================================================================
# XML namespaces
# ============================================================================

XMI = "http://www.omg.org/XMI"
UML = "http://www.omg.org/spec/UML/20131001"

ET.register_namespace("xmi", XMI)
ET.register_namespace("uml", UML)

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def annotation_name(annotation: Any) -> str:
    """Return a readable representation of a Python type annotation."""
    if annotation is inspect.Parameter.empty:
        return "Any"

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        return " | ".join(annotation_name(a) for a in args)

    if origin in (list, set, tuple, dict):
        name = getattr(origin, "__name__", str(origin).split(".")[-1])
        if args:
            return f"{name}[{', '.join(annotation_name(a) for a in args)}]"
        return name

    if isinstance(annotation, type):
        return annotation.__name__

    return str(annotation).replace("typing.", "")

def concrete_types(annotation: Any) -> list[type]:
    """
    Extract concrete Python classes from:
        Foo
        list[Foo]
        Optional[Foo]
        Foo | None
        dict[str, Foo]
    """
    if annotation is inspect.Parameter.empty:
        return []

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        result = []
        for arg in args:
            result.extend(concrete_types(arg))
        return result

    if origin in (list, set, tuple, dict):
        result = []
        for arg in args:
            result.extend(concrete_types(arg))
        return result

    if isinstance(annotation, type):
        return [annotation]

    return []

# ============================================================================
# Intermediate model
# ============================================================================

@dataclass
class Element:
    id: str
    name: str
    kind: str
    owner: Optional[str] = None
    documentation: str = ""

@dataclass
class TypeElement(Element):
    python_type: Optional[type] = None

@dataclass
class PropertyElement(Element):
    type_id: Optional[str] = None
    python_annotation: str = "Any"
    lower: int = 1
    upper: str = "1"
    aggregation: Optional[str] = None
    stereotype: Optional[str] = None

@dataclass
class ParameterElement(Element):
    type_id: Optional[str] = None
    direction: str = "in"
    default: Optional[str] = None

@dataclass
class OperationElement(Element):
    parameter_ids: list[str] = field(default_factory=list)
    return_type_id: Optional[str] = None

@dataclass
class ClassElement(Element):
    property_ids: list[str] = field(default_factory=list)
    operation_ids: list[str] = field(default_factory=list)
    general_ids: list[str] = field(default_factory=list)
    stereotype: str = "block"
    abstract: bool = False
    python_type: Optional[type] = None

@dataclass
class RelationshipElement(Element):
    source: str = ""
    target: str = ""
    relationship: str = "dependency"
    source_role: Optional[str] = None
    target_role: Optional[str] = None
    inferred: bool = False

@dataclass
class ConstraintElement(Element):
    specification: str = ""
    constrained_ids: list[str] = field(default_factory=list)

class ModelGraph:
    """
    Semantic representation between Python and XMI.

    This is deliberately independent of any particular Python class hierarchy.
    """

    def __init__(self, name: str):
        self.name = name
        self.elements: dict[str, Element] = {}

        self.classes: dict[str, ClassElement] = {}
        self.types: dict[str, TypeElement] = {}
        self.properties: dict[str, PropertyElement] = {}
        self.operations: dict[str, OperationElement] = {}
        self.parameters: dict[str, ParameterElement] = {}
        self.relationships: dict[str, RelationshipElement] = {}
        self.constraints: dict[str, ConstraintElement] = {}

        self.class_by_python: dict[type, str] = {}
        self.type_by_python: dict[type, str] = {}

    def add(self, element: Element):
        self.elements[element.id] = element

        if isinstance(element, ClassElement):
            self.classes[element.id] = element
        elif isinstance(element, TypeElement):
            self.types[element.id] = element
        elif isinstance(element, PropertyElement):
            self.properties[element.id] = element
        elif isinstance(element, OperationElement):
            self.operations[element.id] = element
        elif isinstance(element, ParameterElement):
            self.parameters[element.id] = element
        elif isinstance(element, RelationshipElement):
            self.relationships[element.id] = element
        elif isinstance(element, ConstraintElement):
            self.constraints[element.id] = element

        return element

    def add_relationship(
        self,
        name: str,
        source: str,
        target: str,
        relationship: str,
        source_role: Optional[str] = None,
        target_role: Optional[str] = None,
        inferred: bool = False,
    ):
        return self.add(RelationshipElement(
            id=new_id("rel"),
            name=name,
            kind=f"uml:{relationship}",
            source=source,
            target=target,
            relationship=relationship,
            source_role=source_role,
            target_role=target_role,
            inferred=inferred,
        ))

    def inherited_properties(self, class_id: str) -> list[PropertyElement]:
        result = []
        seen = set()

        def visit(cid):
            if cid in seen:
                return
            seen.add(cid)

            cls = self.classes[cid]
            for parent in cls.general_ids:
                if parent in self.classes:
                    visit(parent)

            result.extend(
                self.properties[pid]
                for pid in cls.property_ids
            )

        visit(class_id)
        return result

    def summary(self) -> dict[str, int]:
        return {
            "elements": len(self.elements),
            "classes": len(self.classes),
            "types": len(self.types),
            "properties": len(self.properties),
            "operations": len(self.operations),
            "parameters": len(self.parameters),
            "relationships": len(self.relationships),
            "constraints": len(self.constraints),
        }

class SysMLTransformer:
    """General Python-class -> UML/SysML-oriented model transformer."""

    PRIMITIVES = {str: "String",int: "Integer",float: "Real",bool: "Boolean",bytes: "Binary",}

    def __init__(
        self,
        classes,
        *,
        name: str = "PythonSysMLModel",
        infer_relationships: bool = True,
        include_methods: bool = True,
        include_private: bool = False,
        include_external_types: bool = False,
    ):
        self.classes = self._normalize_classes(classes)
        self.name = name
        self.infer_relationships = infer_relationships
        self.include_methods = include_methods
        self.include_private = include_private
        self.include_external_types = include_external_types

        self.model = ModelGraph(name)
        self.package_id = new_id("package")
        self.profile_id = new_id("profile")

        self._build()

    @classmethod
    def from_classes(cls, *classes, **kwargs):
        return cls(classes, **kwargs)

    @classmethod
    def from_module(cls, module, **kwargs):
        classes = [
            obj for _, obj in inspect.getmembers(module, inspect.isclass)
            if obj.__module__ == module.__name__
        ]
        return cls(classes, **kwargs)

    @staticmethod
    def _normalize_classes(classes):
        result = []
        seen = set()

        def add(cls):
            if not inspect.isclass(cls) or cls is object or cls in seen:
                return

            seen.add(cls)
            result.append(cls)

            # Include base classes so supplied subclasses retain their
            # complete inheritance context.
            for base in cls.__bases__:
                add(base)

        for cls in classes:
            add(cls)

        return result

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _build(self):
        self._create_package()
        self._discover_classes()
        self._discover_types()
        self._discover_properties()
        if self.include_methods:
            self._discover_operations()
        self._discover_inheritance()
        if self.infer_relationships:
            self._discover_property_relationships()
        self._discover_constraints()

    def _create_package(self):
        self.model.add(Element(
            id=self.package_id,
            name=self.name,
            kind="uml:Package",
            documentation="Generated from Python class introspection.",
        ))

        self.model.add(Element(
            id=self.profile_id,
            name="PythonSysMLFacade",
            kind="uml:Profile",
            documentation=(
                "Local interoperability facade. "
                "Native SysML stereotypes may be applied in Cameo."
            ),
        ))

    def _discover_classes(self):
        for cls in self.classes:
            cid = new_id("class")

            element = self.model.add(ClassElement(
                id=cid,
                name=cls.__name__,
                kind="uml:Class",
                owner=self.package_id,
                stereotype="block",
                abstract=inspect.isabstract(cls),
                python_type=cls,
                documentation=inspect.getdoc(cls) or "",
            ))

            self.model.class_by_python[cls] = element.id

    def _get_hints(self, cls):
        try:
            return get_type_hints(cls)
        except Exception:
            # Fall back to raw annotations when forward references cannot
            # be resolved.
            result = {}
            for base in reversed(cls.__mro__):
                result.update(getattr(base, "__annotations__", {}))
            return result

    def _ensure_type(self, annotation: Any) -> Optional[str]:
        candidates = concrete_types(annotation)

        # Prefer a class that is actually part of this model.
        for cls in candidates:
            if cls in self.model.class_by_python:
                return self.model.class_by_python[cls]

        # Primitive types.
        for cls in candidates:
            if cls in self.PRIMITIVES:
                existing = self.model.type_by_python.get(cls)
                if existing:
                    return existing

                element = self.model.add(TypeElement(
                    id=new_id("type"),
                    name=self.PRIMITIVES[cls],
                    kind="uml:PrimitiveType",
                    owner=self.package_id,
                    python_type=cls,
                ))
                self.model.type_by_python[cls] = element.id
                return element.id

        # External concrete types.
        for cls in candidates:
            if inspect.isclass(cls):
                if not self.include_external_types:
                    return None

                existing = self.model.type_by_python.get(cls)
                if existing:
                    return existing

                element = self.model.add(TypeElement(
                    id=new_id("type"),
                    name=cls.__name__,
                    kind="uml:DataType",
                    owner=self.package_id,
                    python_type=cls,
                ))
                self.model.type_by_python[cls] = element.id
                return element.id

        # Generic aliases such as list[int] that do not resolve to a model
        # class are still represented as datatypes.
        readable = annotation_name(annotation)
        existing = next(
            (tid for tid, t in self.model.types.items() if t.name == readable),
            None,
        )
        if existing:
            return existing

        return self.model.add(TypeElement(
            id=new_id("type"),
            name=readable,
            kind="uml:DataType",
            owner=self.package_id,
        )).id

    def _discover_types(self):
        for cls in self.classes:
            for annotation in self._get_hints(cls).values():
                self._ensure_type(annotation)

    def _discover_properties(self):
        for cls in self.classes:
            cid = self.model.class_by_python[cls]
            declared = getattr(cls, "__annotations__", {})

            # Dataclass fields can carry useful metadata/defaults.
            dataclass_map = {}
            if is_dataclass(cls):
                dataclass_map = {f.name: f for f in fields(cls)}

            for name, raw_annotation in declared.items():
                if not self.include_private and name.startswith("_"):
                    continue

                annotation = self._get_hints(cls).get(name, raw_annotation)
                type_id = self._ensure_type(annotation)

                p = self.model.add(PropertyElement(
                    id=new_id("property"),
                    name=name,
                    kind="uml:Property",
                    owner=cid,
                    type_id=type_id,
                    python_annotation=annotation_name(annotation),
                    lower=1,
                    upper="1",
                    stereotype="valueProperty",
                ))

                origin = get_origin(annotation)
                if origin in (list, set, tuple):
                    p.lower = 0
                    p.upper = "*"

                if name in dataclass_map:
                    metadata = dict(dataclass_map[name].metadata)
                    if metadata.get("aggregation"):
                        p.aggregation = metadata["aggregation"]
                    if metadata.get("stereotype"):
                        p.stereotype = metadata["stereotype"]

                self.model.classes[cid].property_ids.append(p.id)

    def _discover_operations(self):
        for cls in self.classes:
            cid = self.model.class_by_python[cls]

            # inspect.getmembers sees inherited methods too. Only serialize
            # methods actually declared on this class.
            declared = cls.__dict__

            for name, member in declared.items():
                if not inspect.isfunction(member):
                    continue
                if not self.include_private and name.startswith("_"):
                    continue

                try:
                    sig = inspect.signature(member)
                except (TypeError, ValueError):
                    continue

                op = self.model.add(OperationElement(
                    id=new_id("operation"),
                    name=name,
                    kind="uml:Operation",
                    owner=cid,
                    documentation=inspect.getdoc(member) or "",
                ))

                for pname, param in sig.parameters.items():
                    if pname == "self":
                        continue

                    annotation = (
                        self._get_hints(cls).get(
                            pname,
                            param.annotation,
                        )
                    )

                    type_id = self._ensure_type(annotation)

                    default = None
                    if param.default is not inspect.Parameter.empty:
                        default = repr(param.default)

                    pe = self.model.add(ParameterElement(
                        id=new_id("parameter"),
                        name=pname,
                        kind="uml:Parameter",
                        owner=op.id,
                        type_id=type_id,
                        direction="in",
                        default=default,
                    ))

                    op.parameter_ids.append(pe.id)

                return_annotation = sig.return_annotation
                if return_annotation is not inspect.Signature.empty:
                    op.return_type_id = self._ensure_type(
                        return_annotation
                    )

                self.model.classes[cid].operation_ids.append(op.id)

    def _discover_inheritance(self):
        for cls in self.classes:
            child_id = self.model.class_by_python[cls]
            child = self.model.classes[child_id]

            for base in cls.__bases__:
                if base is object:
                    continue

                parent_id = self.model.class_by_python.get(base)
                if parent_id is None:
                    continue

                child.general_ids.append(parent_id)

                self.model.add_relationship(
                    name=f"{cls.__name__} specializes {base.__name__}",
                    source=child_id,
                    target=parent_id,
                    relationship="generalization",
                )

    def _discover_property_relationships(self):
        for cls in self.classes:
            source_id = self.model.class_by_python[cls]
            hints = self._get_hints(cls)

            for pid in self.model.classes[source_id].property_ids:
                p = self.model.properties[pid]
                annotation = hints.get(p.name)

                if annotation is None:
                    continue

                targets = [
                    t for t in concrete_types(annotation)
                    if t in self.model.class_by_python
                ]

                for target_cls in targets:
                    target_id = self.model.class_by_python[target_cls]
                    origin = get_origin(annotation)

                    if origin in (list, set, tuple):
                        relationship = "composition"
                        p.aggregation = "composite"
                        p.stereotype = "part"
                    else:
                        relationship = "association"
                        p.stereotype = "referenceProperty"

                    self.model.add_relationship(
                        name=f"{cls.__name__}.{p.name}",
                        source=source_id,
                        target=target_id,
                        relationship=relationship,
                        target_role=p.name,
                        inferred=True,
                    )

    def _discover_constraints(self):
        for cls in self.classes:
            cid = self.model.class_by_python[cls]
            count = len(self.model.classes[cid].property_ids)

            self.model.add(ConstraintElement(
                id=new_id("constraint"),
                name=f"{cls.__name__}AttributeCount",
                kind="uml:Constraint",
                owner=self.package_id,
                specification=(
                    f"declaredAttributeCount({cls.__name__}) = {count}"
                ),
                constrained_ids=[cid],
            ))

    # ------------------------------------------------------------------
    # XMI
    # ------------------------------------------------------------------

    @staticmethod
    def _xmi_tag(name):
        return f"{{{XMI}}}{name}"

    @staticmethod
    def _uml_tag(name):
        return f"{{{UML}}}{name}"

    def _comment(self, parent, text):
        if not text:
            return

        ET.SubElement(
            parent,
            self._uml_tag("ownedComment"),
            {
                self._xmi_tag("type"): "uml:Comment",
                self._xmi_tag("id"): new_id("comment"),
                "body": text,
            },
        )

    def export_xmi(self, path):
        """
        Export UML 2.5-oriented XMI.

        The generated file intentionally uses public UML/XMI constructs rather
        than Cameo-private serialization details. This provides a stable
        interchange layer; native Cameo SysML profile application can be added
        as a target-specific backend later.
        """
        path = Path(path)

        root = ET.Element(
            self._xmi_tag("XMI"),
            {self._xmi_tag("version"): "2.5"},
        )

        model = ET.SubElement(
            root,
            self._uml_tag("Model"),
            {
                self._xmi_tag("id"): new_id("umlmodel"),
                "name": self.name,
            },
        )

        # Local facade profile.
        profile = ET.SubElement(
            model,
            self._uml_tag("packagedElement"),
            {
                self._xmi_tag("type"): "uml:Profile",
                self._xmi_tag("id"): self.profile_id,
                "name": "PythonSysMLFacade",
            },
        )

        for stereotype_name in (
            "Block",
            "PartProperty",
            "ValueProperty",
            "ReferenceProperty",
            "Interface",
        ):
            ET.SubElement(
                profile,
                self._uml_tag("packagedElement"),
                {
                    self._xmi_tag("type"): "uml:Stereotype",
                    self._xmi_tag("id"): new_id("stereo"),
                    "name": stereotype_name,
                },
            )

        package = ET.SubElement(
            model,
            self._uml_tag("packagedElement"),
            {
                self._xmi_tag("type"): "uml:Package",
                self._xmi_tag("id"): self.package_id,
                "name": self.name,
            },
        )

        # Types.
        for t in self.model.types.values():
            ET.SubElement(
                package,
                self._uml_tag("packagedElement"),
                {
                    self._xmi_tag("type"): t.kind,
                    self._xmi_tag("id"): t.id,
                    "name": t.name,
                },
            )

        # Classes.
        for cls in self.model.classes.values():
            attrs = {
                self._xmi_tag("type"): "uml:Class",
                self._xmi_tag("id"): cls.id,
                "name": cls.name,
            }

            if cls.abstract:
                attrs["isAbstract"] = "true"

            ce = ET.SubElement(
                package,
                self._uml_tag("packagedElement"),
                attrs,
            )

            self._comment(ce, cls.documentation)

            for pid in cls.property_ids:
                p = self.model.properties[pid]
                attrs = {
                    self._xmi_tag("type"): "uml:Property",
                    self._xmi_tag("id"): p.id,
                    "name": p.name,
                    "lower": str(p.lower),
                    "upper": p.upper,
                }

                if p.type_id:
                    attrs["type"] = p.type_id
                if p.aggregation:
                    attrs["aggregation"] = p.aggregation

                pe = ET.SubElement(
                    ce,
                    self._uml_tag("ownedAttribute"),
                    attrs,
                )

                self._comment(
                    pe,
                    f"Python annotation: {p.python_annotation}",
                )

            for oid in cls.operation_ids:
                op = self.model.operations[oid]

                oe = ET.SubElement(
                    ce,
                    self._uml_tag("ownedOperation"),
                    {
                        self._xmi_tag("type"): "uml:Operation",
                        self._xmi_tag("id"): op.id,
                        "name": op.name,
                    },
                )

                self._comment(oe, op.documentation)

                for parameter_id in op.parameter_ids:
                    p = self.model.parameters[parameter_id]

                    attrs = {
                        self._xmi_tag("type"): "uml:Parameter",
                        self._xmi_tag("id"): p.id,
                        "name": p.name,
                        "direction": p.direction,
                    }

                    if p.type_id:
                        attrs["type"] = p.type_id
                    if p.default is not None:
                        attrs["defaultValue"] = p.default

                    ET.SubElement(
                        oe,
                        self._uml_tag("ownedParameter"),
                        attrs,
                    )

                if op.return_type_id:
                    ET.SubElement(
                        oe,
                        self._uml_tag("ownedParameter"),
                        {
                            self._xmi_tag("type"): "uml:Parameter",
                            self._xmi_tag("id"): new_id("return"),
                            "name": "return",
                            "direction": "return",
                            "type": op.return_type_id,
                        },
                    )

        # Generalizations.
        for r in self.model.relationships.values():
            if r.relationship != "generalization":
                continue

            ET.SubElement(
                package,
                self._uml_tag("packagedElement"),
                {
                    self._xmi_tag("type"): "uml:Generalization",
                    self._xmi_tag("id"): r.id,
                    "specific": r.source,
                    "general": r.target,
                },
            )

        # Associations/compositions.
        for r in self.model.relationships.values():
            if r.relationship not in ("association", "composition"):
                continue

            assoc = ET.SubElement(
                package,
                self._uml_tag("packagedElement"),
                {
                    self._xmi_tag("type"): "uml:Association",
                    self._xmi_tag("id"): r.id,
                    "name": r.name,
                },
            )

            ET.SubElement(
                assoc,
                self._uml_tag("ownedEnd"),
                {
                    self._xmi_tag("type"): "uml:Property",
                    self._xmi_tag("id"): new_id("end"),
                    "name": "source",
                    "type": r.source,
                    "association": r.id,
                },
            )

            target_attrs = {
                self._xmi_tag("type"): "uml:Property",
                self._xmi_tag("id"): new_id("end"),
                "name": r.target_role or "target",
                "type": r.target,
                "association": r.id,
            }

            if r.relationship == "composition":
                target_attrs["aggregation"] = "composite"

            ET.SubElement(
                assoc,
                self._uml_tag("ownedEnd"),
                target_attrs,
            )

        # Constraints.
        for c in self.model.constraints.values():
            ce = ET.SubElement(
                package,
                self._uml_tag("packagedElement"),
                {
                    self._xmi_tag("type"): "uml:Constraint",
                    self._xmi_tag("id"): c.id,
                    "name": c.name,
                },
            )

            ET.SubElement(
                ce,
                self._uml_tag("specification"),
                {
                    self._xmi_tag("type"): "uml:LiteralString",
                    self._xmi_tag("id"): new_id("literal"),
                    "value": c.specification,
                },
            )

        ET.indent(root, space="  ")
        ET.ElementTree(root).write(
            path,
            encoding="utf-8",
            xml_declaration=True,
        )

        return path

    # ------------------------------------------------------------------
    # JSON manifest
    # ------------------------------------------------------------------

    def export_json(self, path):
        path = Path(path)

        data = {
            "name": self.name,
            "summary": self.model.summary(),
            "classes": [],
            "types": [],
            "properties": [],
            "operations": [],
            "parameters": [],
            "relationships": [],
            "constraints": [],
        }

        for c in self.model.classes.values():
            data["classes"].append({
                "id": c.id,
                "name": c.name,
                "python_type": (
                    f"{c.python_type.__module__}."
                    f"{c.python_type.__qualname__}"
                    if c.python_type else None
                ),
                "stereotype": c.stereotype,
                "abstract": c.abstract,
                "generalizations": c.general_ids,
                "properties": c.property_ids,
                "operations": c.operation_ids,
            })

        for t in self.model.types.values():
            data["types"].append({
                "id": t.id,
                "name": t.name,
                "kind": t.kind,
            })

        for p in self.model.properties.values():
            data["properties"].append({
                "id": p.id,
                "name": p.name,
                "owner": p.owner,
                "type": p.type_id,
                "annotation": p.python_annotation,
                "multiplicity": [p.lower, p.upper],
                "aggregation": p.aggregation,
                "stereotype": p.stereotype,
            })

        for o in self.model.operations.values():
            data["operations"].append({
                "id": o.id,
                "name": o.name,
                "owner": o.owner,
                "parameters": o.parameter_ids,
                "return_type": o.return_type_id,
            })

        for p in self.model.parameters.values():
            data["parameters"].append({
                "id": p.id,
                "name": p.name,
                "owner": p.owner,
                "type": p.type_id,
                "direction": p.direction,
                "default": p.default,
            })

        for r in self.model.relationships.values():
            data["relationships"].append({
                "id": r.id,
                "name": r.name,
                "relationship": r.relationship,
                "source": r.source,
                "target": r.target,
                "source_role": r.source_role,
                "target_role": r.target_role,
                "inferred": r.inferred,
            })

        for c in self.model.constraints.values():
            data["constraints"].append({
                "id": c.id,
                "name": c.name,
                "specification": c.specification,
                "constrained": c.constrained_ids,
            })

        path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        return path

    # ------------------------------------------------------------------
    # NetworkX
    # ------------------------------------------------------------------

    def to_networkx(self, include_properties=True):
        G = nx.MultiDiGraph()

        for element in self.model.elements.values():
            if (
                not include_properties
                and isinstance(element, PropertyElement)
            ):
                continue

            G.add_node(
                element.id,
                name=element.name,
                kind=element.kind,
                owner=element.owner,
                stereotype=getattr(element, "stereotype", None),
            )

        for r in self.model.relationships.values():
            if r.source in G and r.target in G:
                G.add_edge(
                    r.source,
                    r.target,
                    relationship=r.relationship,
                    name=r.name,
                    inferred=r.inferred,
                )

        return G

    # ------------------------------------------------------------------
    # Collision-aware plot
    # ------------------------------------------------------------------

    def plot(self, path=None, show=True):
        classes = list(self.model.classes.values())
        if not classes:
            raise ValueError("No classes discovered.")

        # Inheritance graph.
        H = nx.DiGraph()
        H.add_nodes_from(c.id for c in classes)

        for c in classes:
            for parent in c.general_ids:
                H.add_edge(parent, c.id)

        roots = [n for n in H if H.in_degree(n) == 0]

        level = {}

        def visit(node, depth=0):
            level[node] = max(level.get(node, 0), depth)
            for child in H.successors(node):
                visit(child, depth + 1)

        for root in roots:
            visit(root)

        # Put disconnected classes at level 0.
        for node in H:
            level.setdefault(node, 0)

        by_level = {}
        for node, depth in level.items():
            by_level.setdefault(depth, []).append(node)

        pos = {}
        x_spacing = 7.0
        y_spacing = 6.0

        for depth, nodes in by_level.items():
            nodes = sorted(
                nodes,
                key=lambda n: self.model.classes[n].name,
            )
            for i, node in enumerate(nodes):
                pos[node] = (
                    (i - (len(nodes) - 1) / 2) * x_spacing,
                    -depth * y_spacing,
                )

        fig, ax = plt.subplots(
            figsize=(
                max(10, 5 * max(len(v) for v in by_level.values())),
                max(7, 4 * (max(level.values()) + 1)),
            )
        )

        # Draw edges behind boxes.
        for r in self.model.relationships.values():
            if r.source not in pos or r.target not in pos:
                continue

            if r.relationship == "generalization":
                style = "-|>"
            else:
                style = "->"

            ax.annotate(
                "",
                xy=pos[r.target],
                xytext=pos[r.source],
                arrowprops={
                    "arrowstyle": style,
                    "shrinkA": 35,
                    "shrinkB": 35,
                    "connectionstyle": "arc3,rad=0.0",
                },
            )

            # Relationship label midway between nodes.
            x1, y1 = pos[r.source]
            x2, y2 = pos[r.target]
            ax.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                r.relationship,
                fontsize=7,
                ha="center",
                va="center",
            )

        # Draw class boxes.
        for cid, (x, y) in pos.items():
            cls = self.model.classes[cid]
            properties = self.model.inherited_properties(cid)

            lines = [
                f"«{cls.stereotype}»",
                cls.name,
                "─" * 28,
            ]

            for p in properties:
                lines.append(
                    f"+ {p.name} : {p.python_annotation}"
                )

            if cls.operation_ids:
                lines.append("─" * 28)
                for oid in cls.operation_ids:
                    op = self.model.operations[oid]
                    lines.append(f"+ {op.name}(...)")

            # Box dimensions depend on the actual text, so long class names
            # and large attribute sets do not collide with neighboring boxes.
            max_len = max(len(line) for line in lines)
            width = max(5.5, min(13.0, max_len * 0.11))
            height = max(2.0, 0.38 * len(lines) + 0.65)

            patch = FancyBboxPatch(
                (x - width / 2, y - height / 2),
                width,
                height,
                boxstyle="round,pad=0.05",
                fill=False,
                linewidth=1.5,
            )
            ax.add_patch(patch)

            ax.text(
                x,
                y,
                "\n".join(lines),
                ha="center",
                va="center",
                fontsize=8.5,
                family="DejaVu Sans Mono",
            )

        ax.axis("off")
        ax.margins(0.25)
        fig.tight_layout()

        if path:
            fig.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
            )

        if show:
            plt.show()
        else:
            plt.close(fig)

        return fig, ax


class ModelPlotter:
    """
    Presentation and visualization layer for ModelGraph.

    ModelPlotter is intentionally independent of the Python classes that
    originally produced the ModelGraph. It operates on the semantic model.

    Main views
    ----------
    plot_class_diagram()
        Rich UML/SysML-style class diagram.

    plot_model()
        Full semantic model graph.

    plot_inheritance()
        Inheritance-only hierarchy.

    plot_dependencies()
        Class-to-class relationship graph.
    """

    # ------------------------------------------------------------------
    # Visual configuration
    # ------------------------------------------------------------------

    RELATIONSHIP_STYLES = {
        "generalization": {
            "arrowstyle": "-|>",
            "linestyle": "-",
            "rad": 0.0,
            "label": True,
        },
        "generalizes": {
            "arrowstyle": "-|>",
            "linestyle": "-",
            "rad": 0.0,
            "label": True,
        },
        "association": {
            "arrowstyle": "-",
            "linestyle": "-",
            "rad": 0.10,
            "label": True,
        },
        "composition": {
            "arrowstyle": "-",
            "linestyle": "-",
            "rad": 0.15,
            "label": True,
        },
        "dependency": {
            "arrowstyle": "->",
            "linestyle": "--",
            "rad": 0.10,
            "label": True,
        },
        "dependsOn": {
            "arrowstyle": "->",
            "linestyle": "--",
            "rad": 0.10,
            "label": True,
        },
    }

    DEFAULT_STEREOTYPE = "block"

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(self, model):
        """
        Parameters
        ----------
        model : ModelGraph
            Semantic model generated by SysMLTransformer.
        """

        # Avoid importing ModelGraph just for isinstance checking. This also
        # keeps ModelPlotter usable with compatible ModelGraph implementations.
        required = (
            "elements",
            "classes",
            "properties",
            "operations",
            "parameters",
            "relationships",
        )

        missing = [
            name
            for name in required
            if not hasattr(model, name)
        ]

        if missing:
            raise TypeError(
                "ModelPlotter received an incompatible model. "
                f"Missing attributes: {missing}"
            )

        self.model = model

    # ==================================================================
    # MODEL ACCESS
    # ==================================================================

    def get_classes(
        self,
        classes=None,
    ) -> list[str]:
        """
        Resolve a class selection to ModelGraph class IDs.

        Parameters
        ----------
        classes :
            None
                All classes.

            list[str]
                Class names or ModelGraph IDs.

            list[type]
                Original Python classes.
        """

        if classes is None:
            return list(self.model.classes.keys())

        if isinstance(classes, (str, type)):
            classes = [classes]

        result = []

        for item in classes:

            # ModelGraph ID
            if isinstance(item, str) and item in self.model.classes:
                result.append(item)
                continue

            # Python class
            if (
                isinstance(item, type)
                and item in self.model.class_by_python
            ):
                result.append(
                    self.model.class_by_python[item]
                )
                continue

            # Class name
            if isinstance(item, str):

                matches = [
                    cid
                    for cid, cls in self.model.classes.items()
                    if cls.name == item
                ]

                if len(matches) == 1:
                    result.append(matches[0])
                    continue

                if len(matches) > 1:
                    raise ValueError(
                        f"Class name is ambiguous: {item!r}"
                    )

            raise ValueError(
                f"Unable to resolve class: {item!r}"
            )

        return result

    def get_properties(
        self,
        class_id,
        inherited=True,
        include_composite=False,
    ):
        """
        Return PropertyElement objects associated with a class.
        """

        if inherited:
            properties = (
                self.model.inherited_properties(
                    class_id
                )
            )
        else:
            properties = [
                self.model.properties[pid]
                for pid in self.model.classes[
                    class_id
                ].property_ids
            ]

        if not include_composite:
            properties = [
                p
                for p in properties
                if p.aggregation != "composite"
            ]

        return properties

    def get_operations(self, class_id):
        """Return operations declared by a class."""

        return [
            self.model.operations[oid]
            for oid in self.model.classes[
                class_id
            ].operation_ids
        ]

    def get_relationships(
        self,
        classes=None,
        relationship_types=None,
    ):
        """Return relationships relevant to a selected set of classes."""

        if classes is None:
            relationships = list(
                self.model.relationships.values()
            )
        else:
            class_set = set(classes)

            relationships = [
                r
                for r in self.model.relationships.values()
                if r.source in class_set
                and r.target in class_set
            ]

        if relationship_types is not None:
            relationship_types = set(
                relationship_types
            )

            relationships = [
                r
                for r in relationships
                if r.relationship
                in relationship_types
            ]

        return relationships

    # ==================================================================
    # TEXT FORMATTING
    # ==================================================================

    def _type_name(self, type_id):
        """Resolve a type ID into a display name."""

        if not type_id:
            return "Any"

        element = self.model.elements.get(type_id)

        if element is None:
            return "Any"

        return element.name

    def _property_label(self, prop):
        """Format a UML/SysML property."""

        multiplicity = ""

        if prop.lower != 1 or prop.upper != "1":
            multiplicity = (
                f" [{prop.lower}..{prop.upper}]"
            )

        return (
            f"+ {prop.name} : "
            f"{prop.python_annotation}"
            f"{multiplicity}"
        )

    def _parameter_label(self, parameter):
        """Format an operation parameter."""

        type_name = self._type_name(
            parameter.type_id
        )

        return (
            f"{parameter.name}: "
            f"{type_name}"
        )

    def _operation_label(self, operation):
        """Format a UML/SysML operation."""

        parameters = [
            self._parameter_label(
                self.model.parameters[pid]
            )
            for pid in operation.parameter_ids
        ]

        label = (
            f"+ {operation.name}"
            f"({', '.join(parameters)})"
        )

        if operation.return_type_id:
            label += (
                f" : "
                f"{self._type_name(operation.return_type_id)}"
            )

        return label

    def _class_stereotype(self, class_id):
        """Return the class stereotype."""

        cls = self.model.classes[class_id]

        return (
            cls.stereotype
            or self.DEFAULT_STEREOTYPE
        )

    def _class_lines(
        self,
        class_id,
        inherited=True,
        show_operations=True,
    ):
        """
        Build the contents of a class box.
        """

        cls = self.model.classes[class_id]

        lines = [
            f"«{self._class_stereotype(class_id)}»",
            cls.name,
        ]

        # --------------------------------------------------------------
        # Attributes
        # --------------------------------------------------------------

        lines.append("─" * 30)

        properties = self.get_properties(
            class_id,
            inherited=inherited,
        )

        if properties:
            for prop in properties:
                lines.append(
                    self._property_label(prop)
                )
        else:
            lines.append(" ")

        # --------------------------------------------------------------
        # Operations
        # --------------------------------------------------------------

        operations = self.get_operations(
            class_id
        )

        if show_operations and operations:

            lines.append("─" * 30)

            for operation in operations:
                lines.append(
                    self._operation_label(
                        operation
                    )
                )

        return lines

    # ==================================================================
    # CLASS BOX DIMENSIONS
    # ==================================================================

    def _class_dimensions(
        self,
        class_id,
        inherited=True,
        show_operations=True,
    ):
        """
        Determine box dimensions from its actual contents.

        This is important because arbitrary models may contain very long
        names, many attributes, or long operation signatures.
        """

        lines = self._class_lines(
            class_id,
            inherited=inherited,
            show_operations=show_operations,
        )

        max_chars = max(
            len(line)
            for line in lines
        )

        width = max(
            5.0,
            min(
                14.0,
                0.105 * max_chars + 1.0,
            ),
        )

        height = max(
            1.8,
            0.38 * len(lines) + 0.55,
        )

        return width, height, lines

    # ==================================================================
    # CLASS GRAPH
    # ==================================================================

    def _inheritance_graph(self, classes):
        """
        Create a parent -> child inheritance graph.
        """

        G = nx.DiGraph()

        G.add_nodes_from(classes)

        for relationship in self.get_relationships(
            classes,
            {
                "generalization",
                "generalizes",
            },
        ):

            # ModelGraph stores:
            # source = specific/child
            # target = general/parent
            G.add_edge(
                relationship.target,
                relationship.source,
            )

        return G

    # ==================================================================
    # LAYOUT
    # ==================================================================

    def _hierarchical_layout(
        self,
        classes,
        spacing_x=8.0,
        spacing_y=7.0,
    ):
        """
        Create an inheritance-aware hierarchical layout.

        Multiple inheritance and disconnected hierarchies are supported.
        """

        G = self._inheritance_graph(
            classes
        )

        if not G:
            return {}

        # --------------------------------------------------------------
        # Calculate hierarchy levels
        # --------------------------------------------------------------

        roots = [
            node
            for node in G.nodes
            if G.in_degree(node) == 0
        ]

        if not roots:
            roots = list(G.nodes)

        levels = {}

        def visit(
            node,
            depth=0,
            ancestors=None,
        ):

            ancestors = (
                set()
                if ancestors is None
                else ancestors
            )

            # Protect against accidental cyclic structures.
            if node in ancestors:
                return

            levels[node] = max(
                levels.get(node, 0),
                depth,
            )

            next_ancestors = (
                ancestors | {node}
            )

            for child in G.successors(node):

                visit(
                    child,
                    depth + 1,
                    next_ancestors,
                )

        for root in roots:
            visit(root)

        for node in G.nodes:
            levels.setdefault(node, 0)

        # --------------------------------------------------------------
        # Group nodes by hierarchy
        # --------------------------------------------------------------

        by_level = {}

        for node, level in levels.items():
            by_level.setdefault(
                level,
                [],
            ).append(node)

        pos = {}

        for level, nodes in by_level.items():

            nodes.sort(
                key=lambda n:
                self.model.classes[n].name
            )

            total_width = (
                len(nodes) - 1
            ) * spacing_x

            for index, node in enumerate(nodes):

                x = (
                    index * spacing_x
                    - total_width / 2
                )

                y = -level * spacing_y

                pos[node] = (x, y)

        return pos

    # ==================================================================
    # COLLISION DETECTION
    # ==================================================================

    @staticmethod
    def _boxes_overlap(a, b, padding=0.4):
        """
        Test whether two rectangular boxes overlap.
        """

        return not (
            a["right"] + padding < b["left"]
            or b["right"] + padding < a["left"]
            or a["top"] + padding < b["bottom"]
            or b["top"] + padding < a["bottom"]
        )

    def _make_boxes(
        self,
        classes,
        pos,
        inherited=True,
        show_operations=True,
    ):
        """Build geometric box information."""

        boxes = {}

        for class_id in classes:

            width, height, lines = (
                self._class_dimensions(
                    class_id,
                    inherited=inherited,
                    show_operations=show_operations,
                )
            )

            x, y = pos[class_id]

            boxes[class_id] = {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "left": x - width / 2,
                "right": x + width / 2,
                "bottom": y - height / 2,
                "top": y + height / 2,
            }

        return boxes

    def _resolve_collisions(
        self,
        classes,
        pos,
        inherited=True,
        show_operations=True,
        padding=1.0,
        iterations=50,
    ):
        """
        Iteratively separate overlapping class boxes.

        The hierarchy remains approximately intact while nodes on the same
        level are pushed apart when their actual box dimensions overlap.
        """

        for _ in range(iterations):

            boxes = self._make_boxes(
                classes,
                pos,
                inherited=inherited,
                show_operations=show_operations,
            )

            moved = False

            for i, first in enumerate(classes):

                for second in classes[i + 1:]:

                    a = boxes[first]
                    b = boxes[second]

                    if not self._boxes_overlap(
                        a,
                        b,
                        padding=padding,
                    ):
                        continue

                    # Prefer horizontal separation when nodes share
                    # approximately the same hierarchy level.
                    if abs(
                        a["y"] - b["y"]
                    ) < min(
                        a["height"],
                        b["height"],
                    ):

                        shift = (
                            a["width"]
                            + b["width"]
                        ) / 2 + padding

                        if a["x"] <= b["x"]:
                            delta = (
                                shift
                                - abs(
                                    b["x"]
                                    - a["x"]
                                )
                            )

                            pos[second] = (
                                pos[second][0]
                                + delta,
                                pos[second][1],
                            )
                        else:
                            delta = (
                                shift
                                - abs(
                                    a["x"]
                                    - b["x"]
                                )
                            )

                            pos[first] = (
                                pos[first][0]
                                + delta,
                                pos[first][1],
                            )

                    else:

                        # Vertically separate unrelated boxes.
                        shift = (
                            a["height"]
                            + b["height"]
                        ) / 2 + padding

                        if a["y"] >= b["y"]:
                            delta = (
                                shift
                                - abs(
                                    a["y"]
                                    - b["y"]
                                )
                            )

                            pos[first] = (
                                pos[first][0],
                                pos[first][1]
                                + delta,
                            )
                        else:
                            delta = (
                                shift
                                - abs(
                                    a["y"]
                                    - b["y"]
                                )
                            )

                            pos[second] = (
                                pos[second][0],
                                pos[second][1]
                                + delta,
                            )

                    moved = True

            if not moved:
                break

        return pos

    # ==================================================================
    # RELATIONSHIP RENDERING
    # ==================================================================

    def _draw_relationship(
        self,
        ax,
        relationship,
        pos,
        boxes,
    ):
        """
        Draw a single relationship using the semantic relationship type.
        """

        style = self.RELATIONSHIP_STYLES.get(
            relationship.relationship
        )

        if style is None:
            return

        source = relationship.source
        target = relationship.target

        if (
            source not in pos
            or target not in pos
        ):
            return

        x1, y1 = pos[source]
        x2, y2 = pos[target]

        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops={
                "arrowstyle":
                    style["arrowstyle"],
                "linestyle":
                    style["linestyle"],
                "shrinkA": 35,
                "shrinkB": 35,
                "connectionstyle":
                    (
                        f"arc3,"
                        f"rad={style['rad']}"
                    ),
            },
        )

        if not style["label"]:
            return

        # Relationship label.
        label = relationship.relationship

        if relationship.target_role:
            label += (
                f" : "
                f"{relationship.target_role}"
            )

        # Slightly offset from line center.
        dx = x2 - x1
        dy = y2 - y1

        length = max(
            (dx * dx + dy * dy) ** 0.5,
            1e-6,
        )

        offset_x = -dy / length * 0.25
        offset_y = dx / length * 0.25

        ax.text(
            (x1 + x2) / 2 + offset_x,
            (y1 + y2) / 2 + offset_y,
            label,
            fontsize=7,
            ha="center",
            va="center",
        )

    def _draw_relationships(
        self,
        ax,
        classes,
        pos,
    ):
        """Draw all class-to-class relationships."""

        relationships = self.get_relationships(
            classes
        )

        boxes = self._make_boxes(
            classes,
            pos,
        )

        for relationship in relationships:
            self._draw_relationship(
                ax,
                relationship,
                pos,
                boxes,
            )

    # ==================================================================
    # CLASS BOX RENDERING
    # ==================================================================

    def _draw_class_box(
        self,
        ax,
        class_id,
        pos,
        inherited=True,
        show_operations=True,
    ):
        """Render one UML/SysML class box."""

        width, height, lines = (
            self._class_dimensions(
                class_id,
                inherited=inherited,
                show_operations=show_operations,
            )
        )

        x, y = pos[class_id]

        box = FancyBboxPatch(
            (
                x - width / 2,
                y - height / 2,
            ),
            width,
            height,
            boxstyle="round,pad=0.05",
            linewidth=1.5,
            fill=False,
        )

        ax.add_patch(box)

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------

        title = lines[:2]

        ax.text(
            x,
            y + height / 2 - 0.30,
            "\n".join(title),
            ha="center",
            va="top",
            fontsize=11,
            fontweight="bold",
        )

        # --------------------------------------------------------------
        # Attribute divider
        # --------------------------------------------------------------

        divider_y = (
            y
            + height / 2
            - 1.00
        )

        ax.plot(
            [
                x - width / 2,
                x + width / 2,
            ],
            [
                divider_y,
                divider_y,
            ],
            linewidth=1.0,
        )

        # --------------------------------------------------------------
        # Body
        # --------------------------------------------------------------

        body_lines = lines[3:]

        ax.text(
            x - width / 2 + 0.20,
            divider_y - 0.22,
            "\n".join(body_lines),
            ha="left",
            va="top",
            fontsize=8.5,
            family="DejaVu Sans Mono",
        )

    # ==================================================================
    # CLASS DIAGRAM
    # ==================================================================

    def plot_class_diagram(
        self,
        path=None,
        show=True,
        classes=None,
        spacing_x=8.0,
        spacing_y=7.0,
        inherited=True,
        show_operations=True,
        collision_padding=1.0,
        collision_iterations=50,
        figsize=None,
    ):
        """
        Rich UML/SysML-style class diagram.

        Unlike the original implementation, no class names are hard-coded.
        Any ModelGraph class hierarchy can be rendered.
        """

        classes = self.get_classes(
            classes
        )

        if not classes:
            raise ValueError(
                "No classes available for plotting."
            )

        # --------------------------------------------------------------
        # Initial layout
        # --------------------------------------------------------------

        pos = self._hierarchical_layout(
            classes,
            spacing_x=spacing_x,
            spacing_y=spacing_y,
        )

        # --------------------------------------------------------------
        # Collision resolution
        # --------------------------------------------------------------

        pos = self._resolve_collisions(
            classes,
            pos,
            inherited=inherited,
            show_operations=show_operations,
            padding=collision_padding,
            iterations=collision_iterations,
        )

        # --------------------------------------------------------------
        # Figure dimensions
        # --------------------------------------------------------------

        boxes = self._make_boxes(
            classes,
            pos,
            inherited=inherited,
            show_operations=show_operations,
        )

        if figsize is None:

            min_x = min(
                box["left"]
                for box in boxes.values()
            )

            max_x = max(
                box["right"]
                for box in boxes.values()
            )

            min_y = min(
                box["bottom"]
                for box in boxes.values()
            )

            max_y = max(
                box["top"]
                for box in boxes.values()
            )

            width = max_x - min_x
            height = max_y - min_y

            figsize = (
                max(10, width * 1.15),
                max(7, height * 0.95),
            )

        fig, ax = plt.subplots(
            figsize=figsize
        )

        # --------------------------------------------------------------
        # Relationships first
        # --------------------------------------------------------------

        relationships = self.get_relationships(
            classes
        )

        for relationship in relationships:
            self._draw_relationship(
                ax,
                relationship,
                pos,
                boxes,
            )

        # --------------------------------------------------------------
        # Class boxes
        # --------------------------------------------------------------

        for class_id in classes:

            self._draw_class_box(
                ax,
                class_id,
                pos,
                inherited=inherited,
                show_operations=show_operations,
            )

        # --------------------------------------------------------------
        # Limits
        # --------------------------------------------------------------

        padding = 2.0

        ax.set_xlim(
            min(
                box["left"]
                for box in boxes.values()
            ) - padding,
            max(
                box["right"]
                for box in boxes.values()
            ) + padding,
        )

        ax.set_ylim(
            min(
                box["bottom"]
                for box in boxes.values()
            ) - padding,
            max(
                box["top"]
                for box in boxes.values()
            ) + padding,
        )

        ax.set_aspect(
            "equal",
            adjustable="box",
        )

        ax.axis("off")

        fig.tight_layout()

        if path:
            fig.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
            )

        if show:
            plt.show()
        else:
            plt.close(fig)

        return fig, ax

    # ==================================================================
    # INHERITANCE VIEW
    # ==================================================================

    def plot_inheritance(
        self,
        path=None,
        show=True,
        classes=None,
        spacing_x=8.0,
        spacing_y=7.0,
        figsize=None,
    ):
        """
        Plot only the inheritance hierarchy.
        """

        classes = self.get_classes(
            classes
        )

        relationships = self.get_relationships(
            classes,
            {
                "generalization",
                "generalizes",
            },
        )

        G = nx.DiGraph()

        G.add_nodes_from(classes)

        for r in relationships:
            G.add_edge(
                r.target,
                r.source,
            )

        pos = self._hierarchical_layout(
            classes,
            spacing_x=spacing_x,
            spacing_y=spacing_y,
        )

        if figsize is None:
            figsize = (
                12,
                max(
                    7,
                    len(classes) * 1.5,
                ),
            )

        fig, ax = plt.subplots(
            figsize=figsize
        )

        # Draw hierarchy.
        for r in relationships:

            x1, y1 = pos[r.target]
            x2, y2 = pos[r.source]

            ax.annotate(
                "",
                xy=(x2, y2),
                xytext=(x1, y1),
                arrowprops={
                    "arrowstyle": "-|>",
                    "shrinkA": 30,
                    "shrinkB": 30,
                },
            )

        # Draw nodes.
        for class_id in classes:

            x, y = pos[class_id]

            ax.text(
                x,
                y,
                self.model.classes[
                    class_id
                ].name,
                ha="center",
                va="center",
                bbox={
                    "boxstyle":
                        "round,pad=0.5",
                },
                fontsize=10,
            )

        ax.axis("off")
        ax.set_aspect(
            "equal",
            adjustable="box",
        )

        fig.tight_layout()

        if path:
            fig.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
            )

        if show:
            plt.show()
        else:
            plt.close(fig)

        return fig, ax

    # ==================================================================
    # DEPENDENCY VIEW
    # ==================================================================

    def plot_dependencies(
        self,
        path=None,
        show=True,
        classes=None,
        figsize=(14, 10),
    ):
        """
        Plot class-level associations, compositions, and dependencies.
        """

        classes = self.get_classes(
            classes
        )

        relationships = self.get_relationships(
            classes,
            {
                "association",
                "composition",
                "dependency",
                "dependsOn",
            },
        )

        G = nx.MultiDiGraph()

        G.add_nodes_from(classes)

        for r in relationships:
            G.add_edge(
                r.source,
                r.target,
                relationship=r.relationship,
            )

        pos = nx.spring_layout(
            G,
            seed=42,
            k=2.5,
        )

        fig, ax = plt.subplots(
            figsize=figsize
        )

        nx.draw_networkx_nodes(
            G,
            pos,
            node_size=1800,
            ax=ax,
        )

        nx.draw_networkx_labels(
            G,
            pos,
            labels={
                cid:
                    self.model.classes[
                        cid
                    ].name
                for cid in classes
            },
            ax=ax,
            font_size=9,
        )

        for r in relationships:

            style = self.RELATIONSHIP_STYLES.get(
                r.relationship,
                {
                    "arrowstyle": "->",
                    "linestyle": "-",
                    "rad": 0.0,
                },
            )

            ax.annotate(
                "",
                xy=pos[r.target],
                xytext=pos[r.source],
                arrowprops={
                    "arrowstyle":
                        style["arrowstyle"],
                    "linestyle":
                        style["linestyle"],
                    "connectionstyle":
                        (
                            f"arc3,"
                            f"rad={style['rad']}"
                        ),
                    "shrinkA": 20,
                    "shrinkB": 20,
                },
            )

            x1, y1 = pos[r.source]
            x2, y2 = pos[r.target]

            ax.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                r.relationship,
                fontsize=7,
                ha="center",
                va="center",
            )

        ax.axis("off")
        fig.tight_layout()

        if path:
            fig.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
            )

        if show:
            plt.show()
        else:
            plt.close(fig)

        return fig, ax

    # ==================================================================
    # COMPLETE MODEL VIEW
    # ==================================================================

    def _model_networkx(self):
        """Create a NetworkX representation of the entire ModelGraph."""

        G = nx.MultiDiGraph()

        for element in self.model.elements.values():

            G.add_node(
                element.id,
                name=element.name,
                kind=element.kind,
            )

        for relationship in (
            self.model.relationships.values()
        ):

            if (
                relationship.source in G
                and relationship.target in G
            ):

                G.add_edge(
                    relationship.source,
                    relationship.target,
                    relationship=(
                        relationship.relationship
                    ),
                )

        return G

    def plot_model(
        self,
        path=None,
        show=True,
        figsize=(18, 14),
    ):
        """
        Plot the complete semantic ModelGraph.

        This view exposes the internal model structure rather than only
        the presentation-level class diagram.
        """

        G = self._model_networkx()

        pos = nx.spring_layout(
            G,
            seed=42,
            k=2.0,
            iterations=100,
        )

        fig, ax = plt.subplots(
            figsize=figsize
        )

        nx.draw_networkx_nodes(
            G,
            pos,
            node_size=900,
            ax=ax,
        )

        nx.draw_networkx_labels(
            G,
            pos,
            labels={
                node:
                    data.get(
                        "name",
                        node,
                    )
                for node, data
                in G.nodes(data=True)
            },
            ax=ax,
            font_size=7,
        )

        nx.draw_networkx_edges(
            G,
            pos,
            arrows=True,
            arrowsize=10,
            alpha=0.4,
            connectionstyle="arc3,rad=0.05",
            ax=ax,
        )

        edge_labels = {}

        for u, v, data in G.edges(
            data=True
        ):

            relationship = data.get(
                "relationship"
            )

            if relationship:
                edge_labels[
                    (u, v)
                ] = relationship

        nx.draw_networkx_edge_labels(
            G,
            pos,
            edge_labels=edge_labels,
            font_size=6,
            rotate=False,
            ax=ax,
        )

        ax.axis("off")
        fig.tight_layout()

        if path:
            fig.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
            )

        if show:
            plt.show()
        else:
            plt.close(fig)

        return fig, ax

if __name__ == '__main__':
    from sysml.transformers.old_cameo_sysml_transformer import SysMLTransformer, ModelPlotter
    from dataclasses import dataclass

    @dataclass
    class Vehicle:
        """Base vehicle."""
        mass: float
        name: str

    @dataclass
    class Battery:
        capacity: float
        voltage: float

    @dataclass
    class ElectricVehicle(Vehicle):
        battery: Battery
        range_km: float = 0.0

        def estimate_range(self, efficiency: float) -> float:
            return self.battery.capacity * efficiency

    class Fleet:
        vehicles: list[ElectricVehicle]
        def add_vehicle(self, vehicle: ElectricVehicle) -> None:
            pass

    transformer = SysMLTransformer.from_classes(
        Vehicle,
        Battery,
        ElectricVehicle,
        Fleet,
        name="ArbitraryPythonArchitecture",
    )

    xmi = transformer.export_xmi("C:/Users/Drew/Documents/MyFiles/work/sysml/PythonSysML_Cameo_Interoperability.xmi")
    manifest = transformer.export_json("C:/Users/Drew/Documents/MyFiles/work/sysml/PythonSysML_Cameo_Interoperability.json")

    plotter = ModelPlotter(transformer.model)

    fig, ax = plotter.plot_class_diagram()
    fig, ax = plotter.plot_dependencies()
    fix, ax = plotter.plot_model()
#!/usr/bin/env python
# coding: utf-8

# # MBSE Mapping:
# ## Overview:
# ### High-Level Class Objects:

# In[ ]:


from dataclasses import dataclass, field
from typing import Optional
from collections import Counter, defaultdict
from urllib.parse import urlsplit, unquote

@dataclass
class ElementRecord:
    resource: str
    xmi_id: str
    tag: str
    metaclass: Optional[str] = None
    name: Optional[str] = None
    attributes: dict = field(default_factory=dict)
    parent: Optional[tuple] = None
    children: list = field(default_factory=list)
    registry_key: Optional[tuple] = field(default=None, init=False)

    # Normalized metadata
    element_category: Optional[str] = None
    qualified_name: Optional[str] = None
    namespace: Optional[str] = None

    @property
    def key(self):
        if self.registry_key is None:
            raise RuntimeError("Element has not been registered.")
        return self.registry_key

@dataclass
class ReferenceRecord:
    source: tuple
    element_tag: str
    attribute: str
    value: str
    target: Optional[tuple] = None
    resolved: bool = False
    resolution_status: str = "unprocessed"

@dataclass
class TransformationRule:
    rule_id: str
    name: Optional[str]

    rule_type: str

    source_elements: list = field(default_factory=list)
    target_initializers: list = field(default_factory=list)

    conditions: list = field(default_factory=list)
    inherited_rules: list = field(default_factory=list)

    source_disposition: str = "unclassified"
    target_cardinality: Optional[str] = None

@dataclass
class CrosswalkRecord:
    source: tuple
    target: tuple

    mapping_type: str

    transformation_rule: Optional[tuple] = None
    condition: Optional[str] = None

    confidence: str = "explicit"
    evidence: list = field(default_factory=list)

class MetamodelRegistry:

    def __init__(self):
        # Internal registry key -> ElementRecord
        self.elements = {}
        # Original XMI ID -> list of internal registry keys
        self.elements_by_xmi_id = defaultdict(list)
        self.references = []
        self.resources = {}
        self.uri_aliases = {}

    # Resources
    def add_resource(self, name, path):
        self.resources[name] = str(path)

    # Elements
    def add_element(self, element):
        """
        Register an element without requiring its XMI ID
        to be unique within the resource.

        Internal key:
            (resource, xmi_id, occurrence)

        Occurrence is a 1-based index for that XMI ID
        within the resource.
        """
        occurrence = (len(self.elements_by_xmi_id[(element.resource, element.xmi_id)]) + 1)
        key = (element.resource, element.xmi_id, occurrence)
        element.registry_key = key
        self.elements[key] = element
        self.elements_by_xmi_id[(element.resource, element.xmi_id)].append(key)
        # Maintain parent-child relationships.
        if element.parent is not None:
            parent = self.elements.get(element.parent)
            if parent is None:
                raise KeyError(f"Parent element not found: {element.parent}")
            parent.children.append(key)
        return key

    def get_element(self, resource, xmi_id, occurrence=None):
        """
        Retrieve an element by its original XMI ID.
        If the ID is duplicated, an occurrence must be
        specified to avoid silently selecting an element.
        """

        keys = self.elements_by_xmi_id.get((resource, xmi_id), [])
        if not keys:
            return None
        if occurrence is not None:
            if occurrence < 1 or occurrence > len(keys):
                return None
            return self.elements[keys[occurrence - 1]]
        if len(keys) > 1:
            raise ValueError(
                f"Ambiguous XMI ID '{xmi_id}' in '{resource}'. "
                f"Found {len(keys)} elements. "
                f"Specify occurrence=1 through {len(keys)}."
            )
        return self.elements[keys[0]]

    def get_element_by_key(self, key):
        return self.elements.get(key)

    def get_elements_by_xmi_id(self, resource, xmi_id):
        keys = self.elements_by_xmi_id.get((resource, xmi_id), [])
        return [self.elements[key] for key in keys]

    def get_elements(self, resource=None):
        if resource is None:
            return list(self.elements.values())
        return [element for element in self.elements.values() if element.resource == resource]


    # References
    def get_references(self, source=None):
        if source is None:
            return self.references
        return [ref for ref in self.references if ref.source == source]


    # Queries
    def get_by_name(self, name, resource=None):
        return [element for element in self.elements.values() if element.name == name and (resource is None or element.resource == resource)]

    def get_by_metaclass(self, metaclass, resource=None):
        return [element for element in self.elements.values() if element.metaclass == metaclass and (resource is None or element.resource == resource)]

    # Duplicate ID diagnostics
    def get_duplicate_ids(self, resource=None):
        duplicates = {}
        for (res, xmi_id), keys in self.elements_by_xmi_id.items():
            if len(keys) > 1 and (resource is None or resource == res):
                duplicates[(res, xmi_id)] = [self.elements[key] for key in keys]
        return duplicates

    def build_qualified_names(self):
        """Build qualified names from named containment ancestors."""
        for element in self.elements.values():
            components = []
            ancestors = []
            current = element
            visited = set()
            while current is not None:
                if current.key in visited:
                    raise ValueError(f"Containment cycle detected at {current.key}")

                visited.add(current.key)
                ancestors.append(current)
                current = (self.elements.get(current.parent) if current.parent is not None else None)
            # Reverse so names run from outermost package to element.
            ancestors.reverse()
            for ancestor in ancestors:
                if ancestor.name:
                    components.append(ancestor.name)
            element.qualified_name = "::".join(components)
            # Namespace is the qualified name of named ancestors excluding the element itself.
            parent_components = [ancestor.name for ancestor in ancestors[:-1] if ancestor.name]
            element.namespace = "::".join(parent_components) or None

    def _set_reference_result(self, ref, target=None, status="unresolved"):
        ref.target = target
        ref.resolved = target is not None
        ref.resolution_status = status

    def _resolve_idref(self, ref):
        """Resolve an idref within the source resource."""
        source_resource = ref.source[0]
        candidates = self.elements_by_xmi_id.get((source_resource, ref.value), [])
        if len(candidates) == 1:
            self._set_reference_result(ref, target=candidates[0], status="resolved_local")
        elif len(candidates) > 1:
            self._set_reference_result(ref, status="ambiguous_target")
        else:
            self._set_reference_result(ref, status="missing_local_target")

    def _resolve_href(self, ref):
        """Resolve an href using explicitly registered URI aliases."""
        parsed = urlsplit(ref.value)
        fragment = unquote(parsed.fragment)
        base_uri = parsed._replace(fragment="").geturl()
        if not fragment:
            self._set_reference_result(ref, status="href_missing_fragment") 
            return

        # A fragment-only href refers to the source resource.
        if not base_uri:
            target_resource = ref.source[0]
        else:
            target_resource = self.uri_aliases.get(base_uri)
        if target_resource is None:
            self._set_reference_result(ref, status="external_resource_unregistered")
            return
        candidates = self.elements_by_xmi_id.get((target_resource, fragment), [])
        if len(candidates) == 1:
            self._set_reference_result(ref, target=candidates[0], status="resolved_external")
        elif len(candidates) > 1:
            self._set_reference_result(ref, status="ambiguous_external_target")
        else:
            self._set_reference_result(ref, status="missing_external_target")

    def resolve_references(self):
        """Resolve all idref and href references."""
        for ref in self.references:
            if ref.attribute == "idref":
                self._resolve_idref(ref)
            elif ref.attribute == "href":
                self._resolve_href(ref)
            else:
                self._set_reference_result(ref, status="unsupported_reference_attribute")

    def reference_summary(self):
        """Summarize reference-resolution outcomes by resource."""
        summary = defaultdict(Counter)
        for ref in self.references:
            resource = ref.source[0]
            summary[resource][ref.resolution_status] += 1
        return dict(summary)

    def href_uri_inventory(self):
        """Count href base URIs by source resource."""
        inventory = defaultdict(Counter)
        for ref in self.references:
            if ref.attribute != "href":
                continue
            parsed = urlsplit(ref.value)
            base_uri = parsed._replace(fragment="").geturl()
            inventory[ref.source[0]][base_uri] += 1
        return {resource: dict(counts) for resource, counts in inventory.items()}


# ## XMI Extraction Function:

# In[ ]:


import xml.etree.ElementTree as ET

def local_name(value):
    """Remove an XML namespace from a tag or attribute name."""
    return value.split("}", 1)[-1]

def get_xmi_attribute(element, attribute_name):
    """Retrieve an attribute from the XMI namespace."""
    for key, value in element.attrib.items():
        if (key.startswith("{") and "XMI" in key.split("}", 1)[0].upper() and local_name(key) == attribute_name):
            return value
    return None

class XMIExtractor:

    def __init__(self, registry):
        self.registry = registry

    def extract(self, resource, path):
        root = ET.parse(path).getroot()
        self.registry.add_resource(resource, path)
        self._visit(root, resource)
        return root

    def _visit(self, element, resource, parent_key=None):
        xmi_id = get_xmi_attribute(element, "id")
        current_key = parent_key
        if xmi_id is not None:
            record = ElementRecord(
                resource=resource,
                xmi_id=xmi_id,
                tag=local_name(element.tag),
                metaclass=get_xmi_attribute(element, "type"),
                name=element.attrib.get("name"),
                attributes=dict(element.attrib),
                parent=parent_key
            )
            current_key = self.registry.add_element(record)
        # Capture references.
        for attr, value in element.attrib.items():
            attr_name = local_name(attr)
            if attr_name in {"idref", "href"}:
                if current_key is None:
                    continue
                self.registry.references.append(
                    ReferenceRecord(source=current_key, element_tag=local_name(element.tag), attribute=attr_name, value=value)
                )
        # Recursively traverse children.
        for child in element:
            self._visit(child, resource, current_key)


# ## Population and Counting Function:

# In[ ]:


from pathlib import Path

parent = Path(
    "C:/Users/Drew/Documents/MyFiles/repo/sysml/lang_files/"
)

processed = parent / "processed"

paths = {
    # UML resources
    "UML_Metamodel": processed / "uml_metamodel.xmi",
    "UML_PrimitiveTypes": processed / "uml_primativetypes.xmi",
    "UML_StandardProfile": processed / "uml_standardprofile.xmi",
    "UML_DiagramInterchange": processed / "uml_diagraminterchange.xmi",

    # SysML and KerML resources
    "SysML_v1": processed / "sysml_1.xmi",
    "KerML": processed / "kerml.xmi",
    "SysML_v2": processed / "sysml_2.xmi",

    # Transformation resource
    "SysML_v1_to_v2": processed / "sysml_1_to_2.xmi",
}

registry = MetamodelRegistry()
extractor = XMIExtractor(registry)

for resource, path in paths.items():

    if not path.is_file():
        raise FileNotFoundError(path)

    extractor.extract(resource, path)

    print(
        f"{resource}: "
        f"{len(registry.get_elements(resource))} elements"
    )

print("Total elements:", len(registry.elements))
print("Total references:", len(registry.references))

registry.build_qualified_names()

# Resolve local idrefs and any hrefs with currently registered aliases.
registry.resolve_references()

print("REFERENCE SUMMARY")
for resource, counts in registry.reference_summary().items():
    print(f"\n{resource}: {dict(counts)}")


# In[ ]:


from collections import defaultdict
from lxml import etree


def find_duplicate_xmi_ids(path):
    root = etree.parse(str(path)).getroot()

    xmi_id_attr = "{http://www.omg.org/spec/XMI/20131001}id"

    occurrences = defaultdict(list)

    for element in root.iter():
        xmi_id = element.get(xmi_id_attr)

        if xmi_id is None:
            continue

        parent = element.getparent()

        occurrences[xmi_id].append({
            "tag": etree.QName(element).localname,
            "name": element.get("name"),
            "parent": (
                parent.get("name")
                if parent is not None
                else None
            ),
            "line": element.sourceline,
        })

    return {
        xmi_id: records
        for xmi_id, records in occurrences.items()
        if len(records) > 1
    }
for resource, path in paths.items():
    duplicates = find_duplicate_xmi_ids(path)

    print(
        f"{resource}: "
        f"{len(duplicates)} duplicated XMI IDs"
    )

    for xmi_id, records in duplicates.items():
        print(f"  {xmi_id}: {records}")


# ## Qualified Names, Resolution, URI Inventory:

# In[ ]:


# 1. Qualified-name examples
for resource in registry.resources:
    print(f"\n{'=' * 70}")
    print(resource)
    elements = registry.get_elements(resource)
    named = [e for e in elements if e.name and e.qualified_name]
    for element in named[:20]:
        print(f"{element.qualified_name:<65}", f"[{element.tag}]")

# 2. Reference resolution summary
for resource, counts in registry.reference_summary().items():
    print(f"\n{resource}")
    for status, count in counts.most_common():
        print(f"  {status:<40} {count:>6}")

# 3. External URI inventory
for resource, uris in registry.href_uri_inventory().items():
    print(f"\n{resource}")

    for uri, count in sorted(uris.items()):
        print(f"  {count:>6}  {uri}")


# ## Alias Validation:

# In[ ]:


from collections import defaultdict, Counter
from urllib.parse import urlsplit, unquote


def audit_uri_aliases(registry, candidate_aliases):
    """ Test candidate URI -> resource aliases against extracted XMI IDs. Does not modify registry.uri_aliases or resolve references. """
    results = defaultdict(lambda: {"unique": [], "missing": [], "ambiguous": [],})
    for ref in registry.references:
        if ref.attribute != "href":
            continue
        parsed = urlsplit(ref.value)
        base_uri = parsed._replace(fragment="").geturl()
        fragment = unquote(parsed.fragment)
        target_resource = candidate_aliases.get(base_uri)
        if target_resource is None:
            continue
        if not fragment:
            results[base_uri]["missing"].append((ref.value, "Missing fragment"))
            continue
        candidates = registry.elements_by_xmi_id.get((target_resource, fragment), [])
        if len(candidates) == 1:
            results[base_uri]["unique"].append(ref.value)
        elif len(candidates) > 1:
            results[base_uri]["ambiguous"].append((ref.value, candidates))
        else:
            results[base_uri]["missing"].append(ref.value)
    for uri, result in results.items():
        counts = {key: len(value) for key, value in result.items()}
        total = sum(counts.values())
        print(f"\n{uri}")
        print(f"  Candidate resource: {candidate_aliases[uri]}")
        print(f"  Total references:   {total}")
        print(f"  Unique matches:     {counts['unique']}")
        print(f"  Missing:            {counts['missing']}")
        print(f"  Ambiguous:          {counts['ambiguous']}")

        if result["missing"]:
            print("  Missing examples:")
            for value in result["missing"][:5]:
                print(f"    {value}")

        if result["ambiguous"]:
            print("  Ambiguous examples:")
            for value in result["ambiguous"][:5]:
                print(f"    {value}")

    return dict(results)


# In[ ]:


candidate_aliases = {
    "http://www.omg.org/spec/UML/20131001/UML.xmi": "UML_Metamodel",
    "http://www.omg.org/spec/UML/20131001/PrimitiveTypes.xmi": "UML_PrimitiveTypes",
    "http://www.omg.org/spec/UML/20131001/StandardProfile.xmi": "UML_StandardProfile",
    "http://www.omg.org/spec/UML/20161101/UML.xmi": "UML_Metamodel",
    "http://www.omg.org/spec/UML/20161101/PrimitiveTypes.xmi": "UML_PrimitiveTypes",
    "https://www.omg.org/spec/UML/20161101/PrimitiveTypes.xmi": "UML_PrimitiveTypes",
    "http://www.omg.org/spec/DD/20131001/DI.xmi": "UML_DiagramInterchange",
    "https://www.omg.org/spec/KerML/20250201/KerML.xmi": "KerML",
    "https://www.omg.org/spec/SysML/20250201/SysML.xmi": "SysML_v2",
}

alias_audit = audit_uri_aliases(registry, candidate_aliases)


# ### Alias Writing:

# In[ ]:


registry.uri_aliases.update({
    "http://www.omg.org/spec/UML/20131001/PrimitiveTypes.xmi": "UML_PrimitiveTypes",
    "http://www.omg.org/spec/UML/20161101/UML.xmi": "UML_Metamodel",
    "http://www.omg.org/spec/UML/20131001/UML.xmi": "UML_Metamodel",
    "http://www.omg.org/spec/UML/20131001/StandardProfile.xmi": "UML_StandardProfile",
    "https://www.omg.org/spec/UML/20161101/PrimitiveTypes.xmi": "UML_PrimitiveTypes",
    "https://www.omg.org/spec/KerML/20250201/KerML.xmi": "KerML",
    "https://www.omg.org/spec/SysML/20250201/SysML.xmi": "SysML_v2",
})


# In[ ]:


registry.resolve_references()
for resource, counts in registry.reference_summary().items():
    print(f"\n{resource}: {dict(counts)}")


# ## Transformation ID:

# In[ ]:


from collections import Counter
transformation_classes = [element for element in registry.get_elements("SysML_v1_to_v2") if element.metaclass == "uml:Class"]
class_packages = Counter(element.namespace for element in transformation_classes)
for package, count in class_packages.most_common():
    print(f"{count:5}  {package}")


# ### Evaluate Inheritance Structure:

# In[ ]:


# Id transformation base classes
resource = "SysML_v1_to_v2"
classes = [e for e in registry.get_elements(resource) if e.metaclass == "uml:Class"]
base_names = {"Mapping", "Initializer", "Factory", "MainMapping"}
for element in sorted(classes, key=lambda e: e.qualified_name or ""):
    if element.name in base_names:
        print(f"{element.name:<20}", element.qualified_name, element.key)

def extract_inheritance(registry, resource):
    """Extract class inheritance from resolved XMI generalizations."""
    edges = []
    unresolved = []
    for gen in registry.get_elements(resource):
        if gen.tag != "generalization":
            continue
        child = registry.elements.get(gen.parent)
        if child is None:
            continue
        refs = [ref for ref in registry.get_references(gen.key) if ref.attribute in {"idref", "href"}]
        general_refs = [ref for ref in refs if ref.resolved and ref.target is not None]
        if not general_refs:
            unresolved.append(gen)
            continue
        for ref in general_refs:
            parent = registry.elements.get(ref.target)
            if parent is None:
                unresolved.append(gen)
                continue
            edges.append({"child": child, "parent": parent, "generalization": gen,})
    return edges, unresolved

inheritance_edges, unresolved_generalizations = (extract_inheritance(registry, "SysML_v1_to_v2"))
print("Inheritance relationships:", len(inheritance_edges))
print("Unresolved generalizations:", len(unresolved_generalizations))


# ### Verify edges and targets, inspect inheritance:

# In[ ]:


from collections import Counter
print("Extracted inheritance edges:", len(inheritance_edges))
print("Generalization elements:", sum(e.tag == "generalization" for e in registry.get_elements("SysML_v1_to_v2")))
print("Target metaclasses:", Counter(edge["parent"].metaclass for edge in inheritance_edges))
print("Child metaclasses:", Counter(edge["child"].metaclass for edge in inheritance_edges))

base_names = {"Mapping", "Initializer", "Factory", "MainMapping"}
base_classes = {e.name: e for e in registry.get_elements("SysML_v1_to_v2") if e.metaclass == "uml:Class" and e.name in base_names}
for edge in inheritance_edges:
    if edge["child"].key in {element.key for element in base_classes.values()}:
        print(
            f"{edge['child'].qualified_name}"
            f"  ->  {edge['parent'].qualified_name}"
        )


# ## Goals:
# 
# - Which classes in the transformation file specify "to" and "from"
# - Is initializer for inputs?
# - Mapping vs initializer?
# - What is factory doing?
# - How do unique mapping and main mapping interact?

# In[ ]:


from collections import defaultdict, deque

def build_inheritance_index(inheritance_edges):
    parents = defaultdict(list)
    children = defaultdict(list)
    for edge in inheritance_edges:
        child = edge["child"]
        parent = edge["parent"]
        parents[child.key].append(parent)
        children[parent.key].append(child)
    return parents, children

def get_ancestors(element, parents):
    """Return all transitive ancestors, preserving their defining records."""
    ancestors = {}
    queue = deque(parents[element.key])
    while queue:
        current = queue.popleft()
        if current.key in ancestors:
            continue
        ancestors[current.key] = current
        queue.extend(parents[current.key])
    return list(ancestors.values())

def get_direct_members(element, registry):
    """Return elements directly contained by a class."""
    return [member for member in registry.get_elements(element.resource) if member.parent == element.key and member.tag != "generalization"]

def inspect_inherited_members(element, registry, parents):
    """List direct and inherited members, retaining their defining class."""
    classes = [element] + sorted(get_ancestors(element, parents), key=lambda e: e.qualified_name or "")
    rows = []
    for defining_class in classes:
        for member in get_direct_members(defining_class, registry):
            rows.append({
                "requested_class": element.qualified_name,
                "defined_in": defining_class.qualified_name,
                "inherited": defining_class.key != element.key,
                "member_name": member.name,
                "member_tag": member.tag,
                "member_metaclass": member.metaclass,
                "member_qualified_name": member.qualified_name,
                "member_key": member.key,
            })
    return rows

parents, children = build_inheritance_index(inheritance_edges)
for name in ["Mapping", "Initializer", "Factory", "MainMapping"]:
    element = base_classes[name]
    print(f"\n{'=' * 80}")
    print(element.qualified_name)
    rows = inspect_inherited_members(element, registry, parents)
    for row in rows:
        status = "inherited" if row["inherited"] else "direct"
        print(
            f"{status:10} | "
            f"{row['defined_in']} | "
            f"{row['member_tag']:20} | "
            f"{row['member_name']}"
        )


# In[ ]:


def inspect_attribute(attribute, registry):
    print(f"\n{attribute.qualified_name}")
    print("  XMI ID:", attribute.xmi_id)
    print("  Attributes:", attribute.attributes)

    for child_key in attribute.children:
        child = registry.elements.get(child_key)
        if child is not None:
            print(" Child:", child.tag, child.metaclass, child.name, child.attributes)

def inspect_property_references(attribute, registry):
    print(f"\n{attribute.qualified_name}")
    refs = registry.get_references(attribute.key)
    if not refs:
        print("  No references recorded directly on property.")
        return
    for ref in refs:
        target = registry.elements.get(ref.target) if ref.target else None
        print(f" attribute={ref.attribute}, " f"value={ref.value}, " f"status={ref.resolution_status}")
        if target:
            print(f" target={target.qualified_name}, " f"metaclass={target.metaclass}")
"""
for class_name in ["Mapping", "Initializer"]:
    cls = base_classes[class_name]
    print(f"\n{'=' * 70}")
    print(cls.qualified_name)

    for member in get_direct_members(cls, registry):
        if member.tag == "ownedAttribute":
            inspect_attribute(member, registry)
"""
for class_name in ["Mapping", "Initializer"]:
    cls = base_classes[class_name]

    for member in get_direct_members(cls, registry):
        if member.tag == "ownedAttribute":
            inspect_property_references(member, registry)


# In[ ]:


# There is one missing reference
uml_element_candidates = registry.elements_by_xmi_id.get(
    ("UML_Metamodel", "Element"), []
)

print("UML Element candidates:", uml_element_candidates)

for key in uml_element_candidates:
    element = registry.elements[key]
    print(element.qualified_name, element.metaclass)

registry.uri_aliases["https://www.omg.org/spec/UML/20161101/UML.xmi"] = "UML_Metamodel"
registry.resolve_references()


# ## Initializer:

# In[ ]:


def inspect_class_members(cls, registry):
    members = get_direct_members(cls, registry)
    print(f"\n{'=' * 80}")
    print(f"CLASS: {cls.qualified_name}")
    print(f"{'=' * 80}")
    for member in members:
        print(f"\n{member.name or '<unnamed>'}")
        print(f"  Tag: {member.tag}")
        print(f"  Metaclass: {member.metaclass}")
        print(f"  XMI ID: {member.xmi_id}")
        print(f"  Attributes: {member.attributes}")
        # Directly contained elements
        children = [element for element in registry.get_elements(member.resource) if element.parent == member.key]
        for child in children:
            print(
                f"    Child: {child.tag} "
                f"| metaclass={child.metaclass} "
                f"| name={child.name} "
                f"| attributes={child.attributes}"
            )

        # References originating from this member
        refs = registry.get_references(member.key)

        for ref in refs:
            target = registry.elements.get(ref.target) if ref.target else None

            print(
                f"    Reference: {ref.element_tag} "
                f"| value={ref.value} "
                f"| status={ref.resolution_status} "
                f"| target={target.qualified_name if target else None}"
            )

matches = registry.get_by_name("Initializer")
initializer = next(element for element in matches if element.qualified_name == "SysMLv1Tov2::Mappings::Foundations::Initializer")
inspect_class_members(initializer, registry)


# In[ ]:


mapping_matches = [
    e for e in registry.get_elements()
    if e.qualified_name ==
    "SysMLv1Tov2::Mappings::Foundations::Mapping"
]
mapping = next(
    e for e in registry.get_elements()
    if e.qualified_name ==
       "SysMLv1Tov2::Mappings::Foundations::Mapping"
    and e.metaclass == "uml:Class"
)

print("Matches:", len(mapping_matches))

for e in mapping_matches:
    print(
        "Resource:", e.resource,
        "| Name:", e.qualified_name,
        "| Metaclass:", e.metaclass,
        "| XMI ID:", e.xmi_id
    )


# In[ ]:


def get_class(registry, qualified_name):
    matches = [e for e in registry.get_elements() if e.qualified_name == qualified_name and e.metaclass == "uml:Class"]
    if len(matches) != 1:
        raise ValueError(f"Expected one class for {qualified_name}; " f"found {len(matches)}")
    return matches[0]

mapping = get_class(registry, "SysMLv1Tov2::Mappings::Foundations::Mapping")
initializer = get_class(registry, "SysMLv1Tov2::Mappings::Foundations::Initializer")


# # Mapping Takeaways:
# 
# - Initializer: Defines the mapping through inputs and to 
# - Mapping: Adds source filterand and general mapping
# - Concrete mapping subclasses: Can specialize filtering

# # Inspections:

# In[ ]:


parents_index, children_index = build_inheritance_index(inheritance_edges)
class_names = ["MainMapping", "UniqueMapping", "Factory"]
for name in class_names:
    cls = get_class(registry, f"SysMLv1Tov2::Mappings::Foundations::{name}")
    print(f"\n{'=' * 70}")
    print(cls.qualified_name)
    print("Direct parents:")
    for parent in parents_index[cls.key]:
        print("  ", parent.qualified_name)
    print("Direct children:")
    for child in children_index[cls.key]:
        print("  ", child.qualified_name)



# In[ ]:


sample_classes = [
    "SysMLv1Tov2::Mappings::UML4SysML::CommonStructure::ElementMain_Mapping",
    "SysMLv1Tov2::Mappings::Factories::ReturnParameterFeature_Factory",
    "SysMLv1Tov2::Mappings::Factories::LiteralString_Factory",
]

for qualified_name in sample_classes:
    cls = get_class(registry, qualified_name)
    print(f"\n{'=' * 75}")
    print(cls.qualified_name)
    print("Direct parents:")
    for parent in parents_index[cls.key]:
        print("  ", parent.qualified_name)
    print("Direct members:")
    for member in get_direct_members(cls, registry):
        print(f" {member.tag}: {member.name or '<unnamed>'}" f" | {member.metaclass}")


# In[ ]:


initializer_names = [
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToElement_Init",
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToFeature_Init",
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToExpression_Init",
]

for qualified_name in initializer_names:
    cls = get_class(registry, qualified_name)

    print(f"\n{'=' * 75}")
    print(cls.qualified_name)

    print("Direct parents:")
    for parent in parents_index[cls.key]:
        print("  ", parent.qualified_name)

    print("Direct members:")
    for member in get_direct_members(cls, registry):
        print(f" {member.tag}: {member.name or '<unnamed>'}" f" | {member.metaclass}")


# # OCL Extraction:

# In[ ]:


def get_descendants(element, registry):
    """Return all descendants of an element using registry parent links."""
    descendants = []
    stack = [element.key]
    while stack:
        current_key = stack.pop()
        children = [e for e in registry.get_elements(element.resource) if e.parent == current_key]
        descendants.extend(children)
        stack.extend(child.key for child in children)
    return descendants

cls = get_class(registry, "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToElement_Init")
for member in get_direct_members(cls, registry):
    if member.metaclass not in {"uml:Operation", "uml:Constraint"}:
        continue
    print(f"\n{'=' * 70}")
    print(f"{member.name} ({member.metaclass})")
    for descendant in get_descendants(member, registry):
        if descendant.metaclass == "uml:OpaqueExpression":
            print("Language:", descendant.attributes.get("language"))
            print("Body:", descendant.attributes.get("body"))


# In[ ]:


cls = get_class(registry, "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToType_Init")
print(cls.qualified_name)
for member in get_direct_members(cls, registry):
    print(member.tag, member.name, member.metaclass, member.attributes)


# In[ ]:


# OCL expressions in ToType_Init operations
cls = get_class(registry, "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToType_Init")
for member in get_direct_members(cls, registry):
    if member.metaclass != "uml:Operation":
        continue

    print(f"\n{'=' * 70}")
    print(f"Operation: {member.name}")

    for descendant in get_descendants(member, registry):
        if descendant.metaclass == "uml:OpaqueExpression":
            print("Language:", descendant.attributes.get("language"))
            print("Body:", descendant.attributes.get("body"))


# In[ ]:


cls = get_class(
    registry,
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToExpression_Init"
)

for member in get_direct_members(cls, registry):
    print(
        member.tag,
        member.name,
        member.metaclass,
        member.attributes
    )


# In[ ]:


from collections import defaultdict, deque

def get_descendants(root, inheritance_edges):
    """Return all transitive subclasses of a class."""
    children = defaultdict(list)
    for edge in inheritance_edges:
        children[edge["parent"].key].append(edge["child"])
    descendants = {}
    queue = deque([root.key])
    while queue:
        current = queue.popleft()
        for child in children[current]:
            if child.key == root.key:
                continue
            if child.key in descendants:
                continue
            descendants[child.key] = child
            queue.append(child.key)
    return list(descendants.values())
for root in classes:
    if root.name not in base_names:
        continue
    descendants = get_descendants(root, inheritance_edges)
    print(f"\n{'=' * 90}")
    print(root.qualified_name)
    print("Descendants:", len(descendants))
    for descendant in sorted(descendants, key=lambda e: e.qualified_name or ""):
        print("  ", descendant.qualified_name)

get_descendants(root, inheritance_edges)


# # Build Initializer Inventory:

# In[ ]:


import pandas as pd
from collections import defaultdict

INITIALIZER_PREFIX = "SysMLv1Tov2::Mappings::Initializers"

def direct_members(element):
    return [member for member in members_by_parent[element.key] if member.tag != "generalization"]

# Index directly contained elements by parent.
members_by_parent = defaultdict(list)

for element in registry.get_elements("SysML_v1_to_v2"):
    if element.parent is not None:
        members_by_parent[element.parent].append(element)

# Find initializer classes.
initializer_classes = [
    element
    for element in registry.get_elements("SysML_v1_to_v2")
    if element.metaclass == "uml:Class"
    and element.qualified_name
    and element.qualified_name.startswith(INITIALIZER_PREFIX + "::")
]

initializer_classes.sort(key=lambda e: e.qualified_name)

# Build inventory.
initializer_inventory = []

for cls in initializer_classes:
    members = direct_members(cls)
    attributes = [m.name or "<unnamed>" for m in members if m.metaclass == "uml:Property"]
    operations = [m.name or "<unnamed>" for m in members if m.metaclass == "uml:Operation"]
    constraints = [m.name or "<unnamed>" for m in members if m.metaclass == "uml:Constraint"]
    initializer_inventory.append({
        "qualified_name": cls.qualified_name,
        "parents": [p.qualified_name for p in parents_index[cls.key]],
        "attributes": attributes,
        "operations": operations,
        "constraints": constraints,
        "num_attributes": len(attributes),
        "num_operations": len(operations),
        "num_constraints": len(constraints),
    })


initializer_df = pd.DataFrame(initializer_inventory)

print("Initializer classes:", len(initializer_df))
print("Total properties:", initializer_df["num_attributes"].sum())
print("Total operations:", initializer_df["num_operations"].sum())
print("Total constraints:", initializer_df["num_constraints"].sum())


# In[ ]:


for _, row in initializer_df.iterrows():
    print(f"\n{row['qualified_name']}")

    for parent in row["parents"]:
        print(f"  Parent: {parent}")

    print(f"  Properties:  {row['attributes']}")
    print(f"  Operations:  {row['operations']}")
    print(f"  Constraints: {row['constraints']}")


# In[ ]:


ocl_candidates = initializer_df.loc[(initializer_df["num_operations"] > 0) | (initializer_df["num_constraints"] > 0)].copy()
ocl_candidates = ocl_candidates.sort_values(["num_constraints", "num_operations"], ascending=False)


# ## Extract Operation Specifications Across the Whole Framework:

# ## Look at Operation Specification:

# In[ ]:


from collections import defaultdict

def get_containment_children(element, registry):
    resource = element.key[0]
    return [candidate for candidate in registry.get_elements(resource) if candidate.parent == element.key]

def get_containment_descendants(element, registry):
    resource = element.key[0]
    children_by_parent = defaultdict(list)
    for candidate in registry.get_elements(resource):
        if candidate.parent is not None:
            children_by_parent[candidate.parent].append(candidate)
    descendants = []
    stack = list(children_by_parent[element.key])
    while stack:
        current = stack.pop()
        descendants.append(current)
        stack.extend(children_by_parent[current.key])
    return descendants

def get_operation_parameters(operation):
    parameters = []
    for member in direct_members(operation):
        if member.metaclass != "uml:Parameter":
            continue
        refs = registry.get_references(member.key)
        parameters.append({
            "name": member.name,
            "direction": member.attributes.get("direction"),
            "type_references": [
                {
                    "value": ref.value,
                    "target": (registry.elements[ref.target].qualified_name if ref.resolved and ref.target in registry.elements else None),
                    "status": ref.resolution_status,
                }
                for ref in refs
            ],
        })
    return parameters

operation_audit = []
for cls in initializer_classes:
    for operation in direct_members(cls):
        if operation.metaclass != "uml:Operation":
            continue
        expressions = [d for d in get_containment_descendants(operation, registry) if d.metaclass == "uml:OpaqueExpression"]
        specifications = []
        for expr in expressions:
            body = expr.attributes.get("body")
            language = expr.attributes.get("language")
            if body is None:
                status = "body_attribute_missing"
            elif not body.strip():
                status = "body_empty"
            elif body.strip().rstrip().endswith("="):
                status = "incomplete_assignment"
            else:
                status = "body_present"
            specifications.append({"language": language, "body": body, "status": status, "expression_id": expr.xmi_id,})
        operation_audit.append({
            "class": cls.qualified_name,
            "operation": operation.name,
            "operation_id": operation.xmi_id,
            "parameters": get_operation_parameters(operation),
            "specifications": specifications,
            "specification_count": len(expressions),
            "has_specification": bool(expressions),
        })
operation_audit_df = pd.DataFrame(operation_audit)


# In[ ]:


def get_descendant_classes(element, children_index):
    descendants = {}
    stack = list(children_index[element.key])
    while stack:
        current = stack.pop()
        if current.key in descendants:
            continue
        descendants[current.key] = current
        stack.extend(children_index[current.key])
    return list(descendants.values())

def find_operation_overrides(class_name, operation_name, children_index,):
    base = get_class(registry, class_name)
    results = []
    for descendant in get_descendant_classes(base, children_index):
        operations = [member for member in direct_members(descendant) if member.metaclass == "uml:Operation" and member.name == operation_name]
        for operation in operations:
            results.append({"class": descendant.qualified_name, "operation": operation,})
    return results

base_name = ("SysMLv1Tov2::Mappings::Initializers::KerMLInitializers" "::ToAnnotation_Init")
overrides = find_operation_overrides(base_name, "annotatingElement", children_index,)
for item in overrides:
    print(item["class"], item["operation"].xmi_id, item["operation"].attributes,)


# In[ ]:


for item in overrides:
    cls = get_class(registry, item["class"])
    operation = item["operation"]

    print(f"\n{'=' * 80}")
    print(cls.qualified_name)
    print("Operation:", operation.xmi_id)
    print("Attributes:", operation.attributes)

    print("\nReferences:")
    for ref in registry.get_references(operation.key):
        print({
            "element_tag": ref.element_tag,
            "attribute": ref.attribute,
            "value": ref.value,
            "target": (registry.elements[ref.target].qualified_name if ref.target else None),
            "status": ref.resolution_status,
        })

    print("\nParameters:")
    for parameter in direct_members(operation):
        if parameter.metaclass == "uml:Parameter":
            print(parameter.name, parameter.attributes)

            for ref in registry.get_references(parameter.key):
                print("  Reference:", ref.value, ref.resolution_status)

    print("\nSpecifications:")
    for descendant in get_containment_descendants(operation, registry):
        if descendant.metaclass == "uml:OpaqueExpression":
            print(descendant.attributes)


# In[ ]:


def extract_redefinitions(registry, resource):
    redefinitions = []
    for operation in registry.get_elements(resource):
        if operation.metaclass != "uml:Operation":
            continue
        for ref in registry.get_references(operation.key):
            if ref.element_tag != "redefinedOperation":
                continue
            redefinitions.append({
                "operation": operation,
                "redefined_operation": (registry.elements.get(ref.target) if ref.resolved else None),
                "reference": ref,
                "resolution_status": ref.resolution_status,
            })
    return redefinitions

delegation_targets = [
    ("SysMLv1Tov2::Mappings::UML4SysML::CommonStructure", "Comment_Mapping",),
    ("SysMLv1Tov2::Mappings::SysMLv1::Requirements", "RefineMetadataUsage_Mapping",),
    ("SysMLv1Tov2::Mappings::SysMLv1::Requirements", "TraceMetadataUsage_Mapping",),
]



# # Workflow:
# 
# - Deligated mapping inspect
# - Mapping property extraction
# - Operation redefinition 
# - OCL extraction / dependencies
# - Crosswalk Validation 
# - Graph Reconstruction 

# ### Deligated mapping:

# In[ ]:


def inspect_property(prop):
    print(f"\nProperty: {prop.qualified_name}")
    print("XMI ID:", prop.xmi_id)
    print("Attributes:", prop.attributes)
    print("References:")
    for ref in registry.get_references(prop.key):
        target = (registry.elements[ref.target].qualified_name if ref.resolved else None)
        print({"element_tag": ref.element_tag, "value": ref.value, "target": target, "status": ref.resolution_status,})
    print("Multiplicity:")
    for child in direct_members(prop):
        if child.tag in {"lowerValue", "upperValue"}:
            print(child.tag, child.attributes)

property_ids = [
    "Mappings-UML4SysML-CommonStructure-Comment_Mapping-from",
    "Mappings-UML4SysML-CommonStructure-Comment_Mapping-to",
    "Mappings-SysMLv1-Requirements-RefineMetadataUsage_Mapping-from",
    "Mappings-SysMLv1-Requirements-TraceMetadataUsage_Mapping-from",
]

for xmi_id in property_ids:
    prop = registry.get_element("SysML_v1_to_v2", xmi_id)

    if prop is None:
        print(f"Not found: {xmi_id}")
        continue

    inspect_property(prop)


# In[ ]:


initializer_classes = [
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToAnnotatingElement_Init",
    "SysMLv1Tov2::Mappings::Initializers::SystemInitializers::ToMetadataUsage_Init",
]

for class_name in initializer_classes:
    cls = get_class(registry, class_name)

    for prop in direct_members(cls):
        if prop.name == "to" and prop.metaclass == "uml:Property":
            inspect_property(prop)


# ### Transformation:
# UML Comment --> Comment_Mapping --> KerML Comment --> Annotation --> Comment_Annotation_Mapping
# Abstraction --> MetadataUsage --> FeatureTyping + FeatureMembership

# ## Property Mapping and Validation:

# In[ ]:


import pandas as pd
# Identify mapping classes
mapping_base = get_class(registry, "SysMLv1Tov2::Mappings::Foundations::Mapping")
mapping_classes = []
for element in registry.get_elements("SysML_v1_to_v2"):
    if element.metaclass != "uml:Class":
        continue
    ancestor_keys = {ancestor.key for ancestor in get_ancestors(element, parents_index)}
    if mapping_base.key in ancestor_keys:
        mapping_classes.append(element)
print("Mapping classes identified:", len(mapping_classes))

# Extract property metadata
def get_property_metadata(prop, defining_class, mapping_class):
    refs = registry.get_references(prop.key)
    type_refs = [ref for ref in refs if ref.element_tag == "type"]
    redefined_refs = [ref for ref in refs if ref.element_tag == "redefinedProperty"]
    type_targets = [registry.elements.get(ref.target) if ref.resolved else None for ref in type_refs]
    redefined_targets = [registry.elements.get(ref.target) if ref.resolved else None for ref in redefined_refs]
    children = direct_members(prop)
    lower = next((child.attributes.get("value") for child in children if child.tag == "lowerValue"), None,)
    upper = next((child.attributes.get("value") for child in children if child.tag == "upperValue"), None,)
    return {
        "mapping_class": mapping_class.qualified_name,
        "mapping_class_xmi_id": mapping_class.xmi_id,
        "role": prop.name,
        "property": prop.qualified_name,
        "property_xmi_id": prop.xmi_id,
        "declared_by": defining_class.qualified_name,
        "is_direct": prop.parent == mapping_class.key,
        "property_type": [target.qualified_name if target else None for target in type_targets],
        "property_type_xmi_id": [target.xmi_id if target else None for target in type_targets],
        "type_reference_values": [ref.value for ref in type_refs],
        "type_resolution_status": [ref.resolution_status for ref in type_refs],
        "redefined_property": [target.qualified_name if target else None for target in redefined_targets],
        "redefined_property_xmi_id": [target.xmi_id if target else None for target in redefined_targets],
        "redefinition_resolution_status": [ref.resolution_status for ref in redefined_refs],
        "lower": lower,
        "upper": upper,
    }


# Resolve effective properties through inheritance

property_rows = []
audit_rows = []
for mapping_class in mapping_classes:
    lineage = [mapping_class] + get_ancestors(mapping_class, parents_index,)
    for role in ("from", "to"):

        # Gather declarations of this property throughout the mapping class's inheritance hierarchy.
        declarations = []
        for defining_class in lineage:
            for member in direct_members(defining_class):
                if(member.metaclass == "uml:Property" and member.name == role):
                    declarations.append((member, defining_class))
        candidate_keys = {prop.key for prop, _ in declarations}

        # Identify properties overridden by another declaration in this inheritance hierarchy.
        redefined_keys = set()
        for prop, _ in declarations:
            for ref in registry.get_references(prop.key):
                if (ref.element_tag == "redefinedProperty" and ref.resolved and ref.target in candidate_keys):
                    redefined_keys.add(ref.target)
        # Effective declarations are those not redefined by a morespecific declaration.
        effective = [(prop, defining_class) for prop, defining_class in declarations if prop.key not in redefined_keys]
        if len(effective) == 0:
            status = "missing"
        elif len(effective) == 1:
            status = "unique"
        else:
            status = "ambiguous"
        audit_rows.append({
            "mapping_class": mapping_class.qualified_name,
            "role": role,
            "status": status,
            "declaration_count": len(declarations),
            "effective_property_count": len(effective),
            "effective_properties": [prop.qualified_name for prop, _ in effective],
        })
        for prop, defining_class in effective:
            property_rows.append(get_property_metadata(prop, defining_class, mapping_class,))

# Create DataFrames
mapping_properties = pd.DataFrame(property_rows)
mapping_property_audit = pd.DataFrame(audit_rows)

# Summarize extraction
print("\nEffective property records:", len(mapping_properties))
print("\nProperty audit:")
print(mapping_property_audit["status"] .value_counts(dropna=False))

print("\nProperty records by role:")
print(mapping_properties["role"] .value_counts(dropna=False))

print("\nAmbiguous or missing properties:")
print(mapping_property_audit.loc[mapping_property_audit["status"] != "unique"].to_string(index=False))


# In[ ]:


# Saving mapping CSVs
mapping_properties.to_csv("C:/Users/Drew/Documents/MyFiles/repo/sysml/data/mapping_properties.csv", index=False)
mapping_property_audit.to_csv("C:/Users/Drew/Documents/MyFiles/repo/sysml/data/mapping_property_audit.csv", index=False)


# ## Crosswalk:

# In[ ]:


# Pivot effective properties into one row per mapping class.
property_crosswalk = (mapping_properties .pivot(
        index=["mapping_class", "mapping_class_xmi_id"],
        columns="role",
        values=["property", "property_xmi_id", "declared_by", "property_type",],
    )
)
property_crosswalk.columns = [f"{field}_{role}" for field, role in property_crosswalk.columns]
property_crosswalk = property_crosswalk.reset_index()
# Convenient source/target labels.
property_crosswalk["source_type"] = property_crosswalk["property_type_from"].str[0]
property_crosswalk["target_type"] = property_crosswalk["property_type_to"].str[0]
property_crosswalk.head()


# In[ ]:


operation_rows = []

for mapping_class in mapping_classes:
    for operation in direct_members(mapping_class):
        if operation.metaclass != "uml:Operation":
            continue

        refs = registry.get_references(operation.key)

        redefined = [ref for ref in refs if ref.element_tag == "redefinedOperation"]

        specifications = [
            element
            for element in registry.get_elements("SysML_v1_to_v2")
            if element.parent == operation.key
            and element.metaclass == "uml:OpaqueExpression"
        ]

        # Include nested OpaqueExpressions as well.
        descendants = []
        queue = list(direct_members(operation))

        while queue:
            child = queue.pop()
            descendants.append(child)
            queue.extend(direct_members(child))

        specifications = [element for element in descendants if element.metaclass == "uml:OpaqueExpression"]

        operation_rows.append({
            "mapping_class": mapping_class.qualified_name,
            "operation": operation.qualified_name,
            "operation_name": operation.name,
            "operation_xmi_id": operation.xmi_id,
            "redefined_operations": [registry.elements[ref.target].qualified_name if ref.resolved else None for ref in redefined],
            "ocl": [element.attributes.get("body") for element in specifications],
        })

mapping_operations = pd.DataFrame(operation_rows)

print("Direct mapping operations:", len(mapping_operations))
mapping_operations.head()


# In[ ]:


redefined_operations = mapping_operations[
    mapping_operations["redefined_operations"].map(bool)
]

redefined_operations[
    [
        "mapping_class",
        "operation_name",
        "redefined_operations",
        "ocl",
    ]
].head(30)


# In[ ]:


def classify_mapping_operation(row):
    name = row["operation_name"]
    redefined = row["redefined_operations"]

    if name == "filter":
        return "mapping_filter"

    if name in {"getMapped", "getMappedColl"}:
        return "mapping_dispatch"

    if name in {"ownedRelationship", "ownedMemberFeature",
                "ownedMemberElement", "ownedMemberParameter"}:
        return "relationship_construction"

    if redefined:
        return "property_population_candidate"

    return "other"


mapping_operations["operation_category"] = (mapping_operations.apply(classify_mapping_operation, axis=1,))

print(mapping_operations["operation_category"] .value_counts())


# In[ ]:


pd.set_option("display.max_colwidth", None)
pd.set_option("display.max_columns", None)

mapping_operations[
    mapping_operations["operation_category"]
    == "property_population_candidate"
][
    ["mapping_class", "operation_name", "redefined_operations", "ocl",]
].head(20).to_string(index=False)


# In[ ]:


# Index initializer classes and their directly declared properties.
initializer_base = get_class(registry, "SysMLv1Tov2::Mappings::Foundations::Initializer")
initializer_classes = []
for element in registry.get_elements("SysML_v1_to_v2"):
    if element.metaclass != "uml:Class":
        continue
    ancestor_keys = {ancestor.key for ancestor in get_ancestors(element, parents_index)}
    if initializer_base.key in ancestor_keys:
        initializer_classes.append(element)

initializer_property_rows = []
for cls in initializer_classes:
    for prop in direct_members(cls):
        if prop.metaclass != "uml:Property":
            continue
        initializer_property_rows.append(get_property_metadata(prop, cls, cls))

initializer_properties = pd.DataFrame(initializer_property_rows)

print("Initializer classes:", len(initializer_classes))
print("Initializer properties:", len(initializer_properties))
initializer_properties[["mapping_class", "role", "property_type", "lower", "upper",]].head(20)


# In[ ]:


# Extract the initializeroperation referenced by each property-population candidate.
property_operation_rows = []

for _, row in mapping_operations[mapping_operations["operation_category"] == "property_population_candidate"].iterrows():

    for initializer_operation in row["redefined_operations"]:
        if initializer_operation is None:
            continue

        initializer_class, operation_name = (initializer_operation.rsplit("::", 1))

        property_operation_rows.append({
            "mapping_class": row["mapping_class"],
            "operation": row["operation"],
            "operation_name": row["operation_name"],
            "initializer_operation": initializer_operation,
            "initializer_class": initializer_class,
            "target_property_name": operation_name,
            "ocl": row["ocl"],
        })

property_operation_crosswalk = pd.DataFrame(property_operation_rows)
property_operation_crosswalk.head().to_string()


# In[ ]:


# Map each mapping class to its effective target type.
target_type_by_mapping = (property_crosswalk.set_index("mapping_class")["target_type"].to_dict())
target_property_rows = []
for _, operation_row in property_operation_crosswalk.iterrows():
    mapping_class = operation_row["mapping_class"]
    operation_name = operation_row["operation_name"]
    target_type = target_type_by_mapping.get(mapping_class)
    if not target_type:
        continue
    try:
        target_class = get_class(registry, target_type)
    except ValueError:
        target_property_rows.append({
            "mapping_class": mapping_class,
            "operation": operation_row["operation"],
            "operation_name": operation_name,
            "target_type": target_type,
            "target_property": None,
            "declared_by": None,
            "match_status": "target_class_not_found",
        })
        continue
    hierarchy = [target_class] + get_ancestors(target_class, parents_index,)
    matches = []
    for defining_class in hierarchy:
        for member in direct_members(defining_class):
            if (member.metaclass == "uml:Property" and member.name == operation_name):
                matches.append((member, defining_class))
    if not matches:
        target_property_rows.append({
            "mapping_class": mapping_class,
            "operation": operation_row["operation"],
            "operation_name": operation_name,
            "target_type": target_type,
            "target_property": None,
            "declared_by": None,
            "match_status": "no_name_match",
        })
    for prop, defining_class in matches:
        target_property_rows.append({
            "mapping_class": mapping_class,
            "operation": operation_row["operation"],
            "operation_name": operation_name,
            "initializer_operation": operation_row["initializer_operation"],
            "target_type": target_type,
            "target_property": prop.qualified_name,
            "target_property_xmi_id": prop.xmi_id,
            "declared_by": defining_class.qualified_name,
            "match_status": ("unique_name_match" if len(matches) == 1 else "multiple_name_matches"),
        })


target_property_matches = pd.DataFrame(target_property_rows)
print(target_property_matches["match_status"].value_counts())


# In[ ]:


target_examples = [
    "SysML::Systems::DefinitionAndUsage::ReferenceUsage",
    "KerML::Core::Features::Feature",
    "KerML::Core::Features::FeatureTyping",
    "KerML::Root::Namespaces::Membership",
]

for qualified_name in target_examples:
    cls = get_class(registry, qualified_name)

    print(f"\n{'=' * 90}")
    print(qualified_name)

    hierarchy = [cls] + get_ancestors(cls, parents_index)

    for defining_class in hierarchy:
        properties = [
            member
            for member in direct_members(defining_class)
            if member.metaclass == "uml:Property"
        ]

        if properties:
            print(f"\n  {defining_class.qualified_name}")

            for prop in properties:
                print(
                    f"    {prop.name!r}: "
                    f"{prop.metaclass}, "
                    f"xmi_id={prop.xmi_id}"
                )


# In[ ]:


initializer_examples = [
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToFeature_Init",
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToElement_Init",
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToFeatureTyping_Init",
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToMembership_Init",
]

for qualified_name in initializer_examples:
    cls = get_class(registry, qualified_name)

    print(f"\n{qualified_name}")

    for member in direct_members(cls):
        if member.metaclass == "uml:Operation":
            print("  Operation:", member.name)
        elif member.metaclass == "uml:Property":
            inspect_property(member)


# ## Properties:

# In[ ]:


target_resources = ["KerML", "SysML_v2",]
target_inheritance_edges = []
target_unresolved = {}
for resource in target_resources:
    edges, unresolved = extract_inheritance(registry, resource)
    target_inheritance_edges.extend(edges)
    target_unresolved[resource] = len(unresolved)
    print(resource, "inheritance relationships:", len(edges), "unresolved:", len(unresolved),)

target_parents_index, target_children_index = (build_inheritance_index(target_inheritance_edges))



# In[ ]:


feature = get_class(registry, "KerML::Core::Features::Feature")

print("Resource:", feature.resource)
print("Class:", feature.qualified_name)

hierarchy = [feature] + get_ancestors(feature, target_parents_index,)

for cls in hierarchy:
    print("\n", cls.qualified_name)

    for member in direct_members(cls):
        if member.metaclass == "uml:Property":
            print("  Property:", member.name)


# In[ ]:


feature = get_class(registry, "KerML::Core::Features::Feature")
children = [element for element in registry.get_elements("KerML") if element.parent == feature.key]
print("Direct children:", len(children))
for child in children:
    print(f"tag={child.tag:<25}", f"metaclass={child.metaclass:<20}", f"name={child.name!r}", f"xmi_id={child.xmi_id}")

for cls in get_ancestors(feature, target_parents_index):
    children = [element for element in registry.get_elements("KerML") if element.parent == cls.key]
    print(f"\n{cls.qualified_name} ({len(children)} children)")
    for child in children:
        print(child.tag, child.metaclass, repr(child.name))


# In[ ]:


property_operation_crosswalk.columns


# In[ ]:


def get_class_in_resource(registry, resource, qualified_name):
    matches = [element for element in registry.get_elements(resource) if element.metaclass == "uml:Class" and element.qualified_name == qualified_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one class for {qualified_name} in {resource}; " f"found {len(matches)}")
    return matches[0]

def get_inherited_properties(target_class, registry, parents_index):
    hierarchy = [target_class, *get_ancestors(target_class, parents_index),]
    properties = []
    for cls in hierarchy:
        for member in registry.get_elements(cls.resource):
            if (member.parent == cls.key and member.metaclass == "uml:Property"):
                properties.append({
                    "property": member,
                    "property_name": member.name,
                    "property_qualified_name": member.qualified_name,
                    "declared_by": cls.qualified_name,
                    "declaring_class": cls,
                })
    return properties

property_operation_crosswalk = property_operation_crosswalk.merge(
    property_crosswalk[["mapping_class", "target_type"]].drop_duplicates(), on="mapping_class", how="left", validate="many_to_one",
    )

target_property_matches = []
for _, row in property_operation_crosswalk.iterrows():
    target_type = row["target_type"]
    resource = "KerML" if target_type.startswith("KerML::") else "SysML_v2"
    target_class = get_class_in_resource(registry, resource, target_type,)
    properties = get_inherited_properties(target_class, registry, target_parents_index,)
    matches = [prop for prop in properties if prop["property_name"] == row["operation_name"]]
    target_property_matches.append({
        **row.to_dict(),
        "target_property_matches": [
            {"qualified_name": prop["property_qualified_name"], "declared_by": prop["declared_by"], "xmi_id": prop["property"].xmi_id,} 
            for prop in matches],
        "match_count": len(matches),
        "match_status": ("unique_match" if len(matches) == 1 else "multiple_matches" if len(matches) > 1 else "no_match"),
    })

target_property_matches = pd.DataFrame(target_property_matches)


# In[ ]:


target_property_matches[target_property_matches['match_status'] == 'no_match']


# In[ ]:


examples = [
    ("KerML::Core::Features::Feature", "StructuralFeature_Mapping",),
    ("KerML::Root::Namespaces::MembershipImport", "ElementImport_Mapping",),
]

for target_type, mapping_name in examples:
    target_class = get_class_in_resource(registry, "KerML", target_type)
    print(f"\n{'=' * 80}")
    print(target_type)
    properties = get_inherited_properties(target_class, registry, target_parents_index)
    print("\nTarget properties:")
    for prop in properties:
        print(prop["property_name"], "<-", prop["declared_by"],)
    mapping_class = get_class(
        registry,
        next(row["mapping_class"] for _, row in property_operation_crosswalk.iterrows() if row["mapping_class"].endswith(mapping_name))
    )
    print("\nMapping operations:")
    for member in direct_members(mapping_class):
        if member.metaclass == "uml:Operation":
            print(member.name)


# In[ ]:


mapping_names = ["StructuralFeature_Mapping", "ElementImport_Mapping",]

selected = mapping_operations[mapping_operations["mapping_class"].str.endswith(tuple(mapping_names))]

display(
    selected[["mapping_class", "operation_name", "redefined_operations", "operation_category", "ocl",]].sort_values(
        ["mapping_class", "operation_name"]
    )
)


# In[ ]:


def classify_ocl_operation(row):
    name = row["operation_name"]
    ocl = " ".join(row["ocl"]) if isinstance(row["ocl"], list) else str(row["ocl"])

    if name == "filter":
        return "mapping_filter"

    if name in {"ownedRelationship", "ownedMemberFeature", "ownedMemberElement", "ownedMemberParameter",}:
        return "relationship_construction"

    if "getMapped(" in ocl or "getMappedColl(" in ocl:
        return "delegated_mapping"

    if "Helper." in ocl:
        return "transformed_value"

    if "result = from." in ocl:
        return "direct_value_transfer"

    if "result = false" in ocl or "result = true" in ocl:
        return "constant_value"

    return "other"


# ## Mapping Dependencies:

# In[ ]:


import re
import pandas as pd

MAPPING_CALL_PATTERN = re.compile(
    r"(?P<callee>(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)"
    r"\s*\.\s*"
    r"(?P<method>getMappedColl|getMapped)"
    r"\s*\("
)

def normalize_ocl(value):
    if isinstance(value, (list, tuple)):
        return "\n".join(str(x) for x in value if x is not None)
    if value is None:
        return ""
    return str(value)

def extract_mapping_calls(ocl):
    text = normalize_ocl(ocl)
    calls = []
    for match in MAPPING_CALL_PATTERN.finditer(text):
        open_pos = match.end() - 1
        depth = 0
        close_pos = None
        for i in range(open_pos, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    close_pos = i
                    break
        if close_pos is None:
            continue
        calls.append({
            "callee": match.group("callee"),
            "method": match.group("method"),
            "arguments": text[open_pos + 1:close_pos].strip(),
            "call_expression": text[match.start():close_pos + 1],
        })
    return calls

def resolve_mapping_class(name):
    exact = [cls for cls in known_mapping_classes if cls == name]
    if exact:
        return exact, "resolved"
    matches = [cls for cls in known_mapping_classes if cls.endswith(f"::{name}")]
    if len(matches) == 1:
        return matches, "resolved"
    if len(matches) > 1:
        return matches, "ambiguous"
    return [], "unresolved"

known_mapping_classes = (mapping_operations["mapping_class"] .dropna() .unique() .tolist())

mapping_call_records = []
for _, row in mapping_operations.iterrows():
    calls = extract_mapping_calls(row["ocl"])
    for call in calls:
        candidates, status = resolve_mapping_class(call["callee"])
        mapping_call_records.append({
            "source_mapping": row["mapping_class"],
            "source_operation": row["operation"],
            "source_operation_name": row["operation_name"],
            "target_mapping_name": call["callee"],
            "target_mapping_candidates": candidates,
            "target_mapping": (candidates[0] if status == "resolved" else None),
            "method": call["method"],
            "arguments": call["arguments"],
            "call_expression": call["call_expression"],
            "resolution_status": status,
        })

mapping_calls = pd.DataFrame(mapping_call_records)
print(mapping_calls["resolution_status"].value_counts())


# In[ ]:


mapping_base = get_class_in_resource(registry, "SysML_v1_to_v2", "SysMLv1Tov2::Mappings::Foundations::Mapping",)
mapping_class_records = [
    element
    for element in registry.get_elements("SysML_v1_to_v2")
    if element.metaclass == "uml:Class"
    and (
        element.key == mapping_base.key
        or any(ancestor.key == mapping_base.key for ancestor in get_ancestors(element, parents_index))
    )
]
mapping_class_names = [element.qualified_name for element in mapping_class_records]



# In[ ]:


test_names = ["StructuralFeatureToFeatureTyping_Mapping", "Property_Mapping", "ElementOwningMembership_Mapping",]
for name in test_names:
    matches = [cls for cls in mapping_class_names if cls.endswith(f"::{name}")]
    print(name, matches)


# In[ ]:


def resolve_mapping_class(name):
    exact = [cls for cls in mapping_class_names if cls == name]
    if exact:
        return exact, "resolved"
    matches = [cls for cls in mapping_class_names if cls.endswith(f"::{name}")]
    if len(matches) == 1:
        return matches, "resolved"
    if len(matches) > 1:
        return matches, "ambiguous"
    return [], "unresolved"

resolved_records = mapping_calls["target_mapping_name"].apply(resolve_mapping_class)
mapping_calls["target_mapping_candidates"] = resolved_records.apply(lambda result: result[0])
mapping_calls["resolution_status"] = resolved_records.apply(lambda result: result[1])
mapping_calls["target_mapping"] = mapping_calls["target_mapping_candidates"].apply(lambda candidates: candidates[0] if len(candidates) == 1 else None)
print(mapping_calls["resolution_status"].value_counts())


# In[ ]:


unresolved_calls = mapping_calls.loc[
    mapping_calls["resolution_status"] == "unresolved"
].copy()
display(
    unresolved_calls["target_mapping_name"]
    .value_counts()
    .rename_axis("target_mapping_name")
    .reset_index(name="occurrences")
)


# In[ ]:


def find_classes_by_name(registry, name, resource="SysML_v1_to_v2"):
    return [
        element
        for element in registry.get_elements(resource)
        if element.metaclass == "uml:Class"
        and element.name == name
    ]

for name in sorted(unresolved_calls["target_mapping_name"].unique()):
    matches = find_classes_by_name(registry, name)

    print(f"\n{name}: {len(matches)} match(es)")
    for match in matches:
        print(" ", match.qualified_name)


# In[ ]:


def find_named_elements(registry, name):
    return [element for element in registry.get_elements() if element.name == name]


unresolved_name_audit = []

for name in sorted(unresolved_calls["target_mapping_name"].unique()):
    matches = find_named_elements(registry, name)

    for match in matches:
        unresolved_name_audit.append({
            "requested_name": name,
            "found_name": match.name,
            "resource": match.resource,
            "metaclass": match.metaclass,
            "qualified_name": match.qualified_name,
            "xmi_id": match.xmi_id,
        })

unresolved_name_audit = pd.DataFrame(unresolved_name_audit)

display(unresolved_name_audit)


# In[ ]:


found_but_unresolved = [
    "AllocationSourceReferenceUsageRedefinition_Mapping",
    "AllocationTargetFeatureMembership_Mapping",
    "AllocationTargetReferenceUsageRedefinition_Mapping",
    "AllocationUsageTargetEndFeatureMembership_Mapping",
    "MessageMembership_Mapping",
    "ObjectFlowItemFeatureUntyped_Mapping",
    "ObjectFlowItemFeature_Mapping",
]

for name in found_but_unresolved:
    matches = find_named_elements(registry, name)

    for cls in matches:
        ancestors = get_ancestors(cls, parents_index)

        print(f"\n{cls.qualified_name}")
        print("Metaclass:", cls.metaclass)
        print("Is in mapping_class_names:", cls.qualified_name in mapping_class_names)
        print("Mapping ancestor:", any(
            ancestor.key == mapping_base.key
            for ancestor in ancestors
        ))
        print("Parents:", [a.qualified_name for a in parents_index[cls.key]])


# In[ ]:


mapping_class_records = [
    element
    for element in registry.get_elements("SysML_v1_to_v2")
    if element.metaclass == "uml:Class"
    and (
        element.key == mapping_base.key
        or any(
            ancestor.key == mapping_base.key
            for ancestor in get_ancestors(element, parents_index)
        )
        or (element.name or "").endswith("_Mapping")
    )
]

mapping_class_names = [
    element.qualified_name
    for element in mapping_class_records
]

mapping_class_audit = []

for cls in mapping_class_records:
    has_mapping_ancestor = (
        cls.key == mapping_base.key
        or any(
            ancestor.key == mapping_base.key
            for ancestor in get_ancestors(cls, parents_index)
        )
    )

    mapping_class_audit.append({
        "mapping_class": cls.qualified_name,
        "xmi_id": cls.xmi_id,
        "identified_by": (
            "mapping_inheritance"
            if has_mapping_ancestor
            else "mapping_name_suffix"
        ),
        "direct_parents": [
            parent.qualified_name
            for parent in parents_index[cls.key]
        ],
    })

mapping_class_audit = pd.DataFrame(mapping_class_audit)

print(mapping_class_audit["identified_by"].value_counts())


# In[ ]:


resolved_records = mapping_calls["target_mapping_name"].apply(resolve_mapping_class)
mapping_calls["target_mapping_candidates"] = resolved_records.apply(lambda result: result[0])
mapping_calls["resolution_status"] = resolved_records.apply(lambda result: result[1])
mapping_calls["target_mapping"] = mapping_calls["target_mapping_candidates"].apply(lambda candidates: candidates[0] if len(candidates) == 1 else None)
print(mapping_calls["resolution_status"].value_counts())


# In[ ]:


unresolved_calls = mapping_calls.loc[
    mapping_calls["resolution_status"] == "unresolved"
].copy()

display(
    unresolved_calls[
        [
            "source_mapping",
            "source_operation_name",
            "target_mapping_name",
            "call_expression",
        ]
    ].sort_values(
        ["target_mapping_name", "source_mapping"]
    )
)

display(
    unresolved_calls["target_mapping_name"]
    .value_counts()
    .rename_axis("target_mapping_name")
    .reset_index(name="occurrences")
)


# In[ ]:


resolved_calls = mapping_calls.loc[mapping_calls["resolution_status"] == "resolved"].copy()
dependency_edges = (
    resolved_calls
    .groupby(["source_mapping", "target_mapping"], as_index=False)
    .agg(
        call_count=("call_expression", "size"),
        source_operations=("source_operation_name", lambda x: sorted(set(x))),
        methods=("method", lambda x: sorted(set(x))),
        call_expressions=("call_expression", list),
    )
)
dependency_edges= dependency_edges.sort_values(["source_mapping", "target_mapping"]).reset_index(drop=True)
display(dependency_edges.head(20))


# In[ ]:


assert dependency_edges["call_count"].sum() == len(resolved_calls)

print("Resolved call occurrences:", len(resolved_calls))
print("Unique dependency edges:", len(dependency_edges))
print("Mappings calling other mappings:", dependency_edges["source_mapping"].nunique())
print("Mappings being called:", dependency_edges["target_mapping"].nunique())


# In[ ]:


dependency_edges_all = (
    mapping_calls
    .groupby(["source_mapping", "target_mapping_name", "resolution_status",], as_index=False, dropna=False,)
    .agg(
        target_mapping=("target_mapping", "first"),
        call_count=("call_expression", "size"),
        source_operations=("source_operation_name", lambda x: sorted(set(x)),),
        methods=("method", lambda x: sorted(set(x))),
        call_expressions=("call_expression", list),
    )
)
dependency_edges_all = dependency_edges_all.rename(columns={"target_mapping_name": "target_mapping_label",})
dependency_edges_all = dependency_edges_all.sort_values(["resolution_status", "source_mapping", "target_mapping_label"]).reset_index(drop=True)

assert dependency_edges_all["call_count"].sum() == len(mapping_calls)

print(dependency_edges_all.groupby("resolution_status")["call_count"] .sum())
print("Total dependency pairs:", len(dependency_edges_all))


# In[ ]:


from pathlib import Path

xmi_text = Path("C:/Users/Drew/Documents/MyFiles/repo/sysml/lang_files/processed/sysml_1_to_2.xmi").read_text(encoding="utf-8")

unresolved_name_audit = []

for name in sorted(unresolved_calls["target_mapping_name"].unique()):
    unresolved_name_audit.append({
        "name": name,
        "in_raw_xmi": name in xmi_text,
        "registry_matches": len(find_named_elements(registry, name)),
    })

display(pd.DataFrame(unresolved_name_audit))


# In[ ]:


import re

def find_xmi_occurrences(text, term, context=250):
    matches = []
    for match in re.finditer(re.escape(term), text):
        start = max(0, match.start() - context)
        end = min(len(text), match.end() + context)
        matches.append({"position": match.start(), "context": text[start:end],})
    return matches

for name in sorted(unresolved_calls["target_mapping_name"].unique()):
    occurrences = find_xmi_occurrences(xmi_text, name)
    print(f"\n{'=' * 80}")
    print(f"{name}: {len(occurrences)} occurrence(s)")
    for occurrence in occurrences[:3]:
        print(f"\nPosition: {occurrence['position']}")
        print(occurrence["context"])


# In[ ]:


import re

property_calls = re.findall(r"(?<![\w])Property_Mapping\s*\.\s*getMapped(?:Coll)?\s*\(", xmi_text,)
print("Exact Property_Mapping calls:", len(property_calls))

def audit_mapping_name(name, text):
    # Exact mapping invocation
    call_pattern = re.compile(rf"(?<![\w]){re.escape(name)}" rf"\s*\.\s*getMapped(?:Coll)?\s*\(")
    # Exact occurrence in a UML class declaration
    class_pattern = re.compile(rf'xmi:type="uml:Class"[^>]*\bname="{re.escape(name)}"' rf'|name="{re.escape(name)}"[^>]*xmi:type="uml:Class"')
    return {
        "name": name,
        "exact_mapping_calls": len(call_pattern.findall(text)),
        "class_declaration_matches": len(class_pattern.findall(text)),
        "registry_matches": len(find_named_elements(registry, name)),
    }

mapping_name_audit = pd.DataFrame([
    audit_mapping_name(name, xmi_text)
    for name in sorted(unresolved_calls["target_mapping_name"].unique())
])

display(mapping_name_audit)


# In[ ]:


raw_call_counts = (
    mapping_name_audit[["name", "exact_mapping_calls"]]
    .rename(columns={"name": "target_mapping_name", "exact_mapping_calls": "raw_call_count",})
)

extracted_call_counts = (
    mapping_calls.loc[
        mapping_calls["resolution_status"] == "unresolved"
    ]
    .groupby("target_mapping_name")
    .size()
    .rename("extracted_call_count")
    .reset_index()
)

call_count_audit = raw_call_counts.merge(
    extracted_call_counts,
    on="target_mapping_name",
    how="outer",
).fillna(0)

call_count_audit["difference"] = (
    call_count_audit["raw_call_count"]
    - call_count_audit["extracted_call_count"]
)

display(
    call_count_audit.sort_values(
        "difference", ascending=False
    )
)


# In[ ]:


# Show all three raw occurrences with their surrounding OCL text.
for occurrence in find_xmi_occurrences(xmi_text, "InitialStateMembership_Mapping", context=500,):
    print("\n", "=" * 80)
    print(occurrence["context"])


# In[ ]:


mapping_calls.loc[mapping_calls["target_mapping_name"] == "InitialStateMembership_Mapping", ["source_mapping", "source_operation_name", "call_expression",],]


# In[ ]:


helper_operation = next(e for e in registry.get_elements("SysML_v1_to_v2") if e.metaclass == "uml:Operation" and e.qualified_name.endswith("::Helper::stateOwnedRelationship"))
print(helper_operation.qualified_name)


# In[ ]:


initializer_properties.to_csv("C:/Users/Drew/Documents/MyFiles/repo/sysml/data/initializer_properties.csv", index=False)
property_operation_crosswalk.to_csv("C:/Users/Drew/Documents/MyFiles/repo/sysml/data/property_operation_crosswalk.csv", index=False)


# # Getting a Solid Dependency Map:
# 
# - OCL: defining pre/post conditions
# - Mappings calls to expected behavior
# - Property references
# - Conditonal expr
# - Implimentation classifications 

# In[ ]:


ocl_operations = []
for operation in registry.get_elements("SysML_v1_to_v2"):
    if operation.metaclass != "uml:Operation":
        continue
    owner = registry.elements.get(operation.parent)
    if owner is None:
        continue
    # Retrieve OCL expressions nested under this operation.
    specifications = [
        element
        for element in registry.get_elements("SysML_v1_to_v2")
        if element.tag == "specification"
        and any(
            ancestor.key == operation.key
            for ancestor in get_ancestors(element, parents_index)
        )
    ]
    ocl_bodies = []
    for specification in specifications:
        ocl_bodies.extend(
            element
            for element in registry.get_elements("SysML_v1_to_v2")
            if element.metaclass == "uml:OpaqueExpression"
            and element.parent == specification.key
        )
    ocl_operations.append({
        "operation_id": operation.key,
        "operation_xmi_id": operation.xmi_id,
        "operation": operation.qualified_name,
        "operation_name": operation.name,
        "owner_id": owner.key,
        "owner": owner.qualified_name,
        "owner_metaclass": owner.metaclass,
        "ocl_bodies": [
            body for body in ocl_bodies
        ],
        "ocl_body_count": len(ocl_bodies),
    })
ocl_operations = pd.DataFrame(ocl_operations)


# In[ ]:


print("Total operations:", len(ocl_operations))
print("\nOperations by owner metaclass:")
display(ocl_operations["owner_metaclass"] .value_counts(dropna=False))
print("\nOperations by owner package:")
display(ocl_operations.assign(package=ocl_operations["owner"].str.rsplit("::", n=1).str[0])["package"] .value_counts() .head(20))
print("\nOCL body counts:")
display(ocl_operations["ocl_body_count"].value_counts())


# In[ ]:


from collections import defaultdict

operation_ocl_bodies = defaultdict(list)

for element in registry.get_elements("SysML_v1_to_v2"):

    if element.metaclass != "uml:OpaqueExpression":
        continue

    current = element

    while current.parent is not None:
        parent = registry.elements.get(current.parent)

        if parent is None:
            break

        if parent.metaclass == "uml:Operation":
            operation_ocl_bodies[parent.key].append(element)
            break

        current = parent

ocl_operations["ocl_bodies"] = (ocl_operations["operation_id"] .map(operation_ocl_bodies) .apply(lambda x: x if isinstance(x, list) else []))
ocl_operations["ocl_body_count"] = (ocl_operations["ocl_bodies"].str.len())

print("Total operations:", len(ocl_operations))

print("\nOCL body counts:")
display(ocl_operations["ocl_body_count"].value_counts())
print("\nOperations with OCL bodies:")
display(ocl_operations.loc[ocl_operations["ocl_body_count"] > 0, ["operation", "ocl_body_count"],].head(20))


# In[ ]:


sample_operation = ocl_operations.loc[ocl_operations["ocl_body_count"] > 0].iloc[0]

sample_expression = sample_operation["ocl_bodies"][0]

print("Expression record:")
print(vars(sample_expression))

print("\nContainment ancestry:")
current = sample_expression
while current is not None:
    print(current.metaclass, current.tag, current.name, current.xmi_id,)
    current = (registry.elements.get(current.parent) if current.parent is not None else None)


# ### Adjustment:

# In[ ]:


ocl_specifications = []
for operation in registry.get_elements("SysML_v1_to_v2"):
    if operation.metaclass != "uml:Operation":
        continue
    for constraint in registry.get_elements("SysML_v1_to_v2"):
        if (constraint.metaclass != "uml:Constraint" or constraint.parent != operation.key):
            continue
        expressions = [
            element
            for element in registry.get_elements("SysML_v1_to_v2")
            if (element.metaclass == "uml:OpaqueExpression" and element.parent == constraint.key)
        ]

        if not expressions:
            ocl_specifications.append({
                "operation_id": operation.key,
                "operation": operation.qualified_name,
                "constraint_id": constraint.key,
                "constraint_name": constraint.name,
                "expression_id": None,
                "language": None,
                "body": None,
            })
            continue
        for expression in expressions:
            ocl_specifications.append({
                "operation_id": operation.key,
                "operation": operation.qualified_name,
                "constraint_id": constraint.key,
                "constraint_name": constraint.name,
                "expression_id": expression.key,
                "language": expression.attributes.get("language"),
                "body": expression.attributes.get("body"),
            })

ocl_specifications = pd.DataFrame(ocl_specifications)

def classify_specification(row):
    operation = row["operation"]
    constraint = row["constraint_name"]
    language = row["language"]
    body = row["body"]

    if constraint == "postcondition":
        return "framework_contract"

    if language == "English":
        if pd.isna(body) or not str(body).strip():
            return "incomplete_english_specification"
        return "english_specification"

    if language == "OCL2.0" and constraint == "bodyCondition":
        return "ocl_body_condition"

    return "other_specification"


ocl_specifications["specification_category"] = (ocl_specifications.apply(classify_specification, axis=1,))


# In[ ]:


print("Constraint records:", len(ocl_specifications))

print("\nConstraint names:")
display(ocl_specifications["constraint_name"].value_counts(dropna=False))

print("\nExpression languages:")
display(ocl_specifications["language"].value_counts(dropna=False))

print("\nExpressions per operation:")
display(
    ocl_specifications.groupby("operation")["expression_id"]
    .count()
    .value_counts()
)


# In[ ]:


ocl_specifications.loc[
    ocl_specifications["operation"].str.endswith("::filter"),
    ["operation", "constraint_name", "language", "body"],
].head(10)


# In[ ]:


# Three postconditions
postconditions = ocl_specifications.loc[
    ocl_specifications["constraint_name"] == "postcondition"
].copy()

display(
    postconditions[
        ["operation", "constraint_name", "language", "body"]
    ].to_string(index=False)
)

# Fourteen English expressions
english_expressions = ocl_specifications.loc[
    ocl_specifications["language"] == "English"
].copy()

display(
    english_expressions[
        ["operation", "constraint_name", "language", "body"]
    ].to_string(index=False)
)

constraints_per_operation = (
    ocl_specifications
    .groupby("operation")
    .size()
)

multiple_constraints = constraints_per_operation[
    constraints_per_operation > 1
]

display(
    ocl_specifications.loc[
        ocl_specifications["operation"].isin(
            multiple_constraints.index
        ),
        ["operation", "constraint_name", "language", "body"],
    ]
)


# In[ ]:


display(
    ocl_specifications["specification_category"]
    .value_counts(dropna=False)
)


# In[ ]:


ocl_mapping_calls = []

for _, row in ocl_specifications.iterrows():

    if pd.isna(row["body"]) or not str(row["body"]).strip():
        continue

    calls = extract_mapping_calls(row["body"])

    for call in calls:
        ocl_mapping_calls.append({
            "operation_id": row["operation_id"],
            "operation": row["operation"],
            "constraint_id": row["constraint_id"],
            "constraint_name": row["constraint_name"],
            "language": row["language"],
            "specification_category": row["specification_category"],
            **call,
        })

ocl_mapping_calls = pd.DataFrame(ocl_mapping_calls)
print("Mapping-call occurrences:", len(ocl_mapping_calls))
display(ocl_mapping_calls.groupby(["method", "language"]).size().rename("count").reset_index())
display(ocl_mapping_calls.loc[ocl_mapping_calls["operation"].str.contains("Helper::", na=False), ["operation", "callee", "method", "arguments"],].head(20))


# In[ ]:


def resolve_mapping_class(name):
    # Exact qualified-name match
    exact = [cls for cls in mapping_class_records if cls.qualified_name == name]
    if exact:
        return exact, "resolved_exact"
    # Match an unqualified or partially qualified name
    matches = [cls for cls in mapping_class_records if cls.qualified_name.endswith(f"::{name}")]
    if len(matches) == 1:
        return matches, "resolved_suffix"
    if len(matches) > 1:
        return matches, "ambiguous"
    return [], "unresolved"

resolved_calls = []
for _, row in ocl_mapping_calls.iterrows():
    candidates, status = resolve_mapping_class(row["callee"])
    resolved_calls.append({
        **row.to_dict(),
        "target_class": (candidates[0].qualified_name if len(candidates) == 1 else None),
        "target_class_id": (candidates[0].key if len(candidates) == 1 else None),
        "resolution_status": status,
        "candidate_classes": [cls.qualified_name for cls in candidates],
    })
ocl_mapping_calls_resolved = pd.DataFrame(resolved_calls)


print("Resolution status:")
display(ocl_mapping_calls_resolved["resolution_status"] .value_counts())

print("\nUnresolved calls:")
display(ocl_mapping_calls_resolved.loc[ocl_mapping_calls_resolved["resolution_status"] == "unresolved", ["operation", "callee", "method", "arguments"],])

print("\nAmbiguous calls:")
display(ocl_mapping_calls_resolved.loc[ocl_mapping_calls_resolved["resolution_status"] == "ambiguous", ["operation", "callee", "candidate_classes"],]
)


# In[ ]:


def classify_mapping_call_receiver(row):
    if row["callee"] == "self":
        return "self_dispatch"

    return "mapping_class_reference"


ocl_mapping_calls_resolved["receiver_kind"] = (
    ocl_mapping_calls_resolved.apply(
        classify_mapping_call_receiver,
        axis=1,
    )
)

display(
    ocl_mapping_calls_resolved
    .groupby(["receiver_kind", "resolution_status"])
    .size()
    .rename("count")
    .reset_index()
)


# In[ ]:


unresolved_mapping_calls = (
    ocl_mapping_calls_resolved.loc[
        (ocl_mapping_calls_resolved["receiver_kind"]
         == "mapping_class_reference")
        & (ocl_mapping_calls_resolved["resolution_status"]
           == "unresolved")
    ]
)

unresolved_mapping_targets = (
    unresolved_mapping_calls
    .groupby("callee")
    .agg(
        call_count=("callee", "size"),
        calling_operations=("operation", list),
    )
    .reset_index()
    .sort_values("callee")
)

display(unresolved_mapping_targets)


# In[ ]:


unresolved


# In[ ]:


unresolved_names = unresolved_mapping_targets["callee"].drop_duplicates().tolist()

class_name_audit = []

all_classes = [element for element in registry.get_elements("SysML_v1_to_v2") if element.metaclass == "uml:Class"]

for name in unresolved_names:

    matches = [cls for cls in all_classes if cls.name == name or (cls.qualified_name or "").endswith(f"::{name}")]

    class_name_audit.append({
        "callee": name,
        "class_matches": len(matches),
        "qualified_matches": [cls.qualified_name for cls in matches],
        "xmi_ids": [cls.xmi_id for cls in matches],
    })

class_name_audit = pd.DataFrame(class_name_audit)

display(class_name_audit)


# ### Resolution: 
# 
# All missing mapping elements are confirmed to be meta-metamodel artifacts and not issues in the translation and relationship process

# # Building Normalized Dependencies Table:

# In[ ]:


def add_mapping_resolution(df):
    df = df.copy()

    df["reference_type"] = df["callee"].apply(
        lambda name: "self_dispatch" if name == "self"
        else "mapping_class_reference"
    )

    results = df["callee"].apply(
        lambda name: ([], "not_applicable")
        if name == "self"
        else resolve_mapping_class(name)
    )

    df["candidate_classes"] = results.apply(
        lambda result: [cls.qualified_name for cls in result[0]]
    )

    df["resolution_status"] = results.apply(
        lambda result: result[1]
    )

    df["target_class"] = results.apply(
        lambda result: (
            result[0][0].qualified_name
            if result[1].startswith("resolved") else None
        )
    )

    df["target_class_id"] = results.apply(
        lambda result: (
            result[0][0].xmi_id
            if result[1].startswith("resolved") else None
        )
    )

    return df


ocl_mapping_calls = add_mapping_resolution(ocl_mapping_calls)


# In[ ]:


display(
    ocl_mapping_calls.groupby(
        ["reference_type", "resolution_status"],
        dropna=False
    ).size().rename("count").reset_index()
)


# In[ ]:


dependency_edges = ocl_mapping_calls.copy().reset_index(drop=True)
dependency_edges.insert(0, "call_id", [f"CALL_{i:05d}" for i in range(len(dependency_edges))])
dependency_edges["source_class"] = (dependency_edges["operation"] .str.rsplit("::", n=1) .str[0])
dependency_edges["dependency_type"] = (
    dependency_edges["reference_type"].map({"mapping_class_reference": "mapping_dependency", "self_dispatch": "self_dispatch",})
)
dependency_edges["dependency_status"] = (
    dependency_edges["resolution_status"].map({"resolved_suffix": "resolved", "unresolved": "unresolved_mapping_target", "not_applicable": "not_applicable",})
)

unresolved_mapping_targets = (
    dependency_edges.loc[dependency_edges["dependency_status"].eq("unresolved_mapping_target")]
    .groupby("callee")
    .agg(
        call_count=("call_id", "count"),
        calling_operations=("operation", lambda x: sorted(set(x))),
        calling_classes=("source_class", lambda x: sorted(set(x))),
    )
    .reset_index()
    .rename(columns={"callee": "target_name"})
    .sort_values("target_name")
    .reset_index(drop=True)
)

assert len(dependency_edges) == 855
assert dependency_edges["call_id"].is_unique
assert (
    dependency_edges["dependency_status"]
    .value_counts()
    .to_dict()
    == {"resolved": 830, "unresolved_mapping_target": 24, "not_applicable": 1,}
)
assert len(unresolved_mapping_targets) == 15
assert unresolved_mapping_targets["call_count"].sum() == 24

display(unresolved_mapping_targets)


# In[ ]:


def classify_source_owner(qualified_name):
    matches = [e for e in registry.get_elements("SysML_v1_to_v2") if e.metaclass == "uml:Class" and e.qualified_name == qualified_name]

    if len(matches) != 1:
        return "unresolved_source_owner"

    owner = matches[0]

    if owner.name == "Helper":
        return "helper"

    if owner.name.endswith("_Mapping"):
        return "mapping_class"

    if owner.name.endswith("_Init"):
        return "initializer"

    if owner.name.endswith("_Factory"):
        return "factory"

    return "other_class"

dependency_edges["source_owner_type"] = (dependency_edges["source_class"].apply(classify_source_owner))
display(dependency_edges.groupby("source_owner_type", dropna=False).size().rename("call_count").reset_index())


# In[ ]:


display(
    dependency_edges.loc[
        dependency_edges["dependency_status"].eq("unresolved_mapping_target"),
        ["source_class", "source_owner_type", "operation", "callee", "method", "arguments", "call_expression",],
    ].sort_values(["source_owner_type", "callee", "operation"])
)


# In[ ]:


mapping_dependencies = dependency_edges.loc[dependency_edges["source_owner_type"].eq("mapping_class")].copy()
helper_dependencies = dependency_edges.loc[dependency_edges["source_owner_type"].eq("helper")].copy()

print("Mapping dependencies:",
      len(mapping_dependencies))

print("Helper dependencies:",
      len(helper_dependencies))

print("\nUnresolved mapping dependencies:",
      mapping_dependencies["dependency_status"]
      .eq("unresolved_mapping_target").sum())

print("\nUnresolved helper dependencies:",
      helper_dependencies["dependency_status"]
      .eq("unresolved_mapping_target").sum())


# In[ ]:


mapping_dependency_edges = mapping_dependencies[
    ["call_id", "source_class", "operation", "operation_id", "constraint_id", 
     "language", "specification_category", "callee", "target_class", "target_class_id", 
     "arguments", "call_expression", "dependency_status",]
].copy()

mapping_dependency_edges = mapping_dependency_edges.rename(
    columns={"source_class": "source_node", "callee": "target_name",}
)


# ## After Re-validation:

# In[ ]:


import pandas as pd

# Build mapping crosswalk from the property crosswalk
mapping_table = property_crosswalk.copy()
mapping_table = mapping_table.rename(
    columns={
        "mapping_class": "mapping_name",
        "mapping_class_xmi_id": "mapping_xmi_id",
        "property_from": "source_property",
        "property_xmi_id_from": "source_property_xmi_id",
        "declared_by_from": "source_property_declared_by",
        "property_type_from": "source_property_type",
        "property_to": "target_property",
        "property_xmi_id_to": "target_property_xmi_id",
        "declared_by_to": "target_property_declared_by",
        "property_type_to": "target_property_type",
    }
)

# Add inheritance ancestry
def get_mapping_ancestors(mapping_name):
    cls = get_class(registry, mapping_name)
    return [ancestor.qualified_name for ancestor in get_ancestors(cls, parents_index)]

mapping_table["ancestors"] = (mapping_table["mapping_name"].apply(get_mapping_ancestors))

# Summarize mapping operations
operation_summary = (
    mapping_operations
    .groupby("mapping_class")
    .agg(
        operation_count=("operation", "count"),
        operations=("operation_name", lambda x: sorted(set(x))),
        operation_categories=("operation_category", lambda x: sorted(set(x))),)
    .reset_index()
    .rename(columns={"mapping_class": "mapping_name"})
)
# Summarize mapping dependencies
dependency_summary = (
    dependency_edges.loc[dependency_edges["source_owner_type"].eq("mapping_class")]
    .groupby("source_class")
    .agg(
        dependency_count=("call_id", "count"),
        resolved_dependency_count=("dependency_status", lambda x: x.eq("resolved").sum()),
        unresolved_dependency_count=("dependency_status", lambda x: x.eq("unresolved_mapping_target").sum()),
        dependencies=("callee", lambda x: sorted(set(x))),
    )
    .reset_index()
    .rename(columns={"source_class": "mapping_name"})
)
# Merge operation and dependency summaries
mapping_table = mapping_table.merge(operation_summary, on="mapping_name", how="left", validate="one_to_one",)
mapping_table = mapping_table.merge(dependency_summary, on="mapping_name", how="left", validate="one_to_one",)
count_columns = ["operation_count", "dependency_count", "resolved_dependency_count", "unresolved_dependency_count",]
mapping_table[count_columns] = (mapping_table[count_columns] .fillna(0) .astype(int))
# Represent missing operation/dependency collections as empty lists.
list_columns = ["operations", "operation_categories", "dependencies",]
for column in list_columns:
    mapping_table[column] = mapping_table[column].apply(lambda x: x if isinstance(x, list) else [])

# Remove duplicate columns and validate identities
mapping_table = mapping_table.loc[:, ~mapping_table.columns.duplicated()].copy()
assert mapping_table["mapping_name"].is_unique
assert mapping_table["mapping_name"].notna().all()

# Identify mapping classes missing from the crosswalk
crosswalk_names = set(mapping_table["mapping_name"])
mapping_class_inventory = pd.DataFrame([
    {
        "mapping_name": cls.qualified_name,
        "xmi_id": cls.xmi_id,
        "registry_key": cls.key,
        "identified_by": (
            "mapping_inheritance" if cls.key == mapping_base.key 
            or any(ancestor.key == mapping_base.key 
                   for ancestor in get_ancestors(cls, parents_index)) 
                   else "mapping_name_suffix"),
    }
    for cls in mapping_class_records
])
mapping_class_inventory["has_crosswalk"] = (mapping_class_inventory["mapping_name"].isin(crosswalk_names))
missing_crosswalk_df = mapping_class_inventory.loc[~mapping_class_inventory["has_crosswalk"]].copy()
# Record crosswalk coverage in the complete inventory.
mapping_class_inventory["has_crosswalk"] = (mapping_class_inventory["mapping_name"].isin(crosswalk_names))
# Final validation
print("Mapping crosswalk rows:", len(mapping_table))
print("Unique crosswalk mappings:", mapping_table["mapping_name"].nunique())
print("\nComplete mapping-class inventory:", len(mapping_class_inventory))

print("Classes missing crosswalk:", len(missing_crosswalk_df))
print("\nDependency summary:")
print(mapping_table[["dependency_count", "resolved_dependency_count", "unresolved_dependency_count",]].sum())

assert mapping_table["mapping_name"].is_unique
assert mapping_class_inventory["mapping_name"].is_unique
assert (len(mapping_table) + len(missing_crosswalk_df) == len(mapping_class_inventory))

display(mapping_table.head())
display(missing_crosswalk_df)


# In[ ]:


# Dependencies originating from the 14 excluded classes
excluded_names = set(missing_crosswalk_df["mapping_name"])
excluded_dependencies = dependency_edges.loc[dependency_edges["source_class"].isin(excluded_names)].copy()
print("Dependency calls from excluded classes:", len(excluded_dependencies))
display(excluded_dependencies.groupby(["source_class", "dependency_status"], dropna=False).size().rename("call_count").reset_index())


# In[ ]:


supplemental_classes = missing_crosswalk_df.loc[missing_crosswalk_df["identified_by"].eq("mapping_name_suffix")]
supplemental_property_audit = []
for mapping_name in supplemental_classes["mapping_name"]:
    cls = get_class(registry, mapping_name)
    hierarchy = [cls] + get_ancestors(cls, parents_index)
    for owner in hierarchy:
        for prop in direct_members(owner):
            if (prop.metaclass == "uml:Property" and prop.name in {"from", "to"}):
                redefinitions = [ref for ref in registry.get_references(prop.key) if ref.element_tag == "redefinedProperty"]
                supplemental_property_audit.append({
                    "mapping_name": mapping_name,
                    "declared_by": owner.qualified_name,
                    "property": prop.name,
                    "property_xmi_id": prop.xmi_id,
                    "redefined_property_ids": [ref.value for ref in redefinitions],
                })

supplemental_property_audit = pd.DataFrame(supplemental_property_audit)

display(supplemental_property_audit.sort_values(["mapping_name", "property", "declared_by"]))


# In[ ]:


mapping_table['unresolved_dependency_count'].unique()


# # SysML1 --> SysML2 Translation:

# In[ ]:


operation_columns = ["mapping_class", "operation", "operation_name", "operation_xmi_id", "redefined_operations", "operation_category",]
mapping_operation_base = (mapping_operations[operation_columns] .rename(columns={"mapping_class": "mapping_name"}) .copy())
mapping_operation_specs = mapping_operation_base.merge(
    ocl_specifications[["operation", "constraint_id", "constraint_name", "expression_id", "language", "body", "specification_category",]],
    on="operation",
    how="left",
    validate="one_to_many",
)
mapping_operation_table = mapping_operation_specs.merge(
    mapping_table[["mapping_name", "mapping_xmi_id", "source_type", "target_type",]],
    on="mapping_name",
    how="left",
    validate="many_to_one",
)
mapping_operation_table = mapping_operation_table.sort_values(["mapping_name", "operation_name"]).reset_index(drop=True)


# In[ ]:


print("Mapping operation rows:", len(mapping_operation_table))
print("Unique operations:", mapping_operation_table["operation_xmi_id"].nunique())
print("Operations without specifications:", mapping_operation_table["body"].isna().sum())
print("Operations without crosswalk:", mapping_operation_table["source_type"].isna().sum())


# ## Test:

# In[ ]:


def get_effective_operations(mapping_name):
    try:
        cls = get_class(registry, mapping_name)
    except ValueError as exc:
        print(f"Skipping {mapping_name}: {exc}")
        return []
    hierarchy = [cls] + get_ancestors(cls, parents_index)
    operations = []
    for owner in hierarchy:
        for operation in get_containment_children(owner, registry):
            if operation.metaclass != "uml:Operation":
                continue
            operations.append({
                "mapping_name": mapping_name,
                "declared_by": owner.qualified_name,
                "operation": operation.qualified_name,
                "operation_name": operation.name,
                "operation_xmi_id": operation.xmi_id,
                "is_direct": owner.key == cls.key,
            })
    return operations

test_mappings = [
    "SysMLv1Tov2::Mappings::CommonMappings::CommonMembership_Mapping",
    "SysMLv1Tov2::Mappings::UML4SysML::Classification::StructuralFeature_Mapping",
]

# Find an additional mapping with a Comment source type, if present.
comment_candidates = mapping_table.loc[
    mapping_table["source_type"].astype(str).str.contains(
        "Comment", case=False, na=False
    ),
    "mapping_name",
].tolist()

if comment_candidates:
    test_mappings.append(comment_candidates[0])

# Verify every name before extraction.
for name in test_mappings:
    print(name, "->", len([
        e for e in registry.get_elements("SysML_v1_to_v2")
        if e.qualified_name == name and e.metaclass == "uml:Class"
    ]))


# In[ ]:


test_operations = pd.DataFrame([
    operation
    for mapping_name in test_mappings
    for operation in get_effective_operations(mapping_name)
])


# In[ ]:


display(
    test_operations.groupby(
        ["mapping_name", "is_direct"]
    ).size().unstack(fill_value=0)
)
display(
    test_operations.loc[
        ~test_operations["is_direct"]
    ].groupby(
        ["mapping_name", "declared_by"]
    )["operation_name"]
    .agg(list)
    .reset_index()
)
duplicates = test_operations.loc[
    test_operations.duplicated(
        ["mapping_name", "operation_xmi_id"],
        keep=False
    )
].sort_values(["mapping_name", "operation_xmi_id"])

display(duplicates)
display(
    test_operations[
        [
            "mapping_name",
            "operation_name",
            "declared_by",
            "is_direct",
        ]
    ].sort_values(
        ["mapping_name", "is_direct", "operation_name"],
        ascending=[True, False, True],
    )
)


# ## Scaled Implimentation:

# In[ ]:


def get_effective_operations(mapping_name):
    cls = get_class(registry, mapping_name)
    hierarchy = [cls] + get_ancestors(cls, parents_index)
    operations = []
    for owner in hierarchy:
        for operation in direct_members(owner):
            if operation.metaclass != "uml:Operation":
                continue
            redefinitions = []
            for ref in registry.get_references(operation.key):
                if ref.element_tag != "redefinedOperation":
                    continue
                target = (registry.elements.get(ref.target) if ref.resolved else None)
                redefinitions.append({
                    "operation": (target.qualified_name if target else None),
                    "operation_xmi_id": (target.xmi_id if target else None),
                    "resolution_status": ref.resolution_status,
                })
            operations.append({
                "mapping_name": mapping_name,
                "declared_by": owner.qualified_name,
                "operation": operation.qualified_name,
                "operation_name": operation.name,
                "operation_xmi_id": operation.xmi_id,
                "is_direct": owner.key == cls.key,
                "redefined_operations": redefinitions,
            })
    return operations

mapping_operation_declarations = pd.DataFrame([operation for mapping_name in mapping_table["mapping_name"] for operation in get_effective_operations(mapping_name)])
print("Declaration rows:", len(mapping_operation_declarations))
print("Unique mapping-operation pairs:", mapping_operation_declarations[["mapping_name", "operation_xmi_id"]].drop_duplicates().shape[0])
print("\nDirect vs inherited:")
display(mapping_operation_declarations.groupby("is_direct").size())
print("\nRedefined operation declarations:")
display(
    mapping_operation_declarations.loc[
        mapping_operation_declarations["redefined_operations"].map(bool),
        ["mapping_name", "operation_name", "declared_by", "redefined_operations",],
    ].head(15)
)


# ### Verification / Debugging

# In[ ]:


print("Declaration columns:")
print(mapping_operation_declarations.columns.tolist())

print("\nSpecification columns:")
print(ocl_specifications.columns.tolist())

print("\nSpecification operation ID uniqueness:")
print(ocl_specifications["operation_id"].nunique(), "unique IDs across", len(ocl_specifications), "specification rows")

print("\nOperation ID overlap:")
declaration_ids = set(mapping_operation_declarations["operation_xmi_id"].dropna())
specification_ids = set(ocl_specifications["operation_id"].dropna())

print("Declaration IDs:", len(declaration_ids))
print("Specification IDs:", len(specification_ids))
print("Matching IDs:", len(declaration_ids & specification_ids))
print("Unmatched declaration IDs:", len(declaration_ids - specification_ids))


# In[ ]:


print("Declaration operation IDs:")
display(mapping_operation_declarations[["operation", "operation_xmi_id"]].drop_duplicates("operation_xmi_id").head(10))
print("\nSpecification operation IDs:")
display(ocl_specifications[["operation", "operation_id"]].drop_duplicates("operation_id").head(10))


# In[ ]:


for _, row in ocl_specifications.head(5).iterrows():
    print({"operation_id": row["operation_id"], "operation": row["operation"],})


for _, row in mapping_operation_declarations[
    ["operation", "operation_xmi_id"]
].drop_duplicates("operation_xmi_id").head(5).iterrows():

    print({"operation": row["operation"], "operation_xmi_id": row["operation_xmi_id"],})


# #### Debugging Fixes:

# In[ ]:


# Normalize specification ID
ocl_specifications = ocl_specifications.copy()
ocl_specifications["operation_resource"] = (ocl_specifications["operation_id"].str[0])
ocl_specifications["operation_xmi_id"] = (ocl_specifications["operation_id"].str[1])
ocl_specifications["operation_occurrence"] = (ocl_specifications["operation_id"].str[2])

# Validate Normalized
print("Matching XMI IDs:", len(set(mapping_operation_declarations["operation_xmi_id"]) & set(ocl_specifications["operation_xmi_id"])))
print("\nDuplicate specification XMI IDs:")
display(
    ocl_specifications.loc[ocl_specifications["operation_xmi_id"].duplicated(keep=False), ["operation", "operation_xmi_id", "operation_occurrence"],]
)
print("\nSpecification resources:")
display(ocl_specifications["operation_resource"].value_counts())


# In[ ]:


# Determine if unmatched declarations are from helpers/factories/initializers/other
declaration_ids = set(mapping_operation_declarations["operation_xmi_id"].dropna())
specification_ids = set(ocl_specifications["operation_xmi_id"].dropna())
unmatched_declaration_ids = declaration_ids - specification_ids

display(
    mapping_operation_declarations.loc[
        mapping_operation_declarations["operation_xmi_id"].isin(
            unmatched_declaration_ids
        ),
        ["mapping_name", "declared_by", "operation", "operation_xmi_id", "is_direct",],
    ].drop_duplicates()
)


# In[ ]:


mapping_operation_specifications = (
    mapping_operation_declarations.merge(
        ocl_specifications[
            ["operation_xmi_id", "operation_id", "constraint_id", "constraint_name", "expression_id", "language", "body", "specification_category",]
        ],
        on="operation_xmi_id",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
)

print("Rows:", len(mapping_operation_specifications))

print("\nSpecification match status:")
display(
    mapping_operation_specifications["_merge"].value_counts()
)

print("\nDeclarations without specifications:")
display(
    mapping_operation_specifications.loc[
        mapping_operation_specifications["_merge"].eq("left_only"),
        ["mapping_name", "declared_by", "operation", "operation_xmi_id"],
    ].drop_duplicates()
)


# In[ ]:


unmatched_operations = (
    mapping_operation_declarations.loc[
        mapping_operation_declarations["operation_xmi_id"].isin(
            unmatched_declaration_ids
        ),
        ["operation", "operation_xmi_id"],
    ]
    .drop_duplicates()
)

for _, row in unmatched_operations.iterrows():
    operation = registry.get_element(
        "SysML_v1_to_v2",
        row["operation_xmi_id"],
    )

    print(f"\n{row['operation']}")
    print("Record attributes:")
    print(vars(operation))

    print("\nDirect children:")
    for child in direct_members(operation):
        print(
            child.metaclass,
            child.tag,
            child.name,
            child.xmi_id,
        )


# In[ ]:


descendants = [
    cls
    for cls in registry.get_elements("SysML_v1_to_v2")
    if cls.metaclass == "uml:Class"
    and any(
        ancestor.key == initializer.key
        for ancestor in get_ancestors(cls, parents_index)
    )
]

display(pd.DataFrame([
    {
        "class": cls.qualified_name,
        "is_abstract": cls.attributes.get(
            "isAbstract", "false"
        ).lower() == "true",
    }
    for cls in descendants
]).groupby("is_abstract").size().rename("class_count"))


# In[ ]:


descendant_operations = []

for cls in descendants:
    for op in direct_members(cls):
        if op.metaclass != "uml:Operation":
            continue

        descendant_operations.append({
            "class": cls.qualified_name,
            "class_is_abstract": (
                cls.attributes.get("isAbstract", "false").lower()
                == "true"
            ),
            "operation": op.qualified_name,
            "operation_name": op.name,
            "operation_xmi_id": op.xmi_id,
            "operation_is_abstract": (
                op.attributes.get("isAbstract", "false").lower()
                == "true"
            ),
        })

descendant_operations = pd.DataFrame(descendant_operations)

display(
    descendant_operations.loc[
        descendant_operations["operation_name"].isin(
            ["featureOfType", "featuringType"]
        )
    ].sort_values(["operation_name", "class"])
)

print(
    "Descendants declaring operations:",
    descendant_operations["class"].nunique()
)

print(
    "Total direct operation declarations:",
    len(descendant_operations)
)


# In[ ]:


initializer_operation_metadata = pd.DataFrame([
    {
        "operation": (
            "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers"
            "::ToTypeFeaturing_Init::featureOfType"
        ),
        "is_abstract": True,
        "return_type": "KerML::Core::Features::Feature",
        "has_ocl_specification": False,
        "formal_redefinition_count": 0,
    },
    {
        "operation": (
            "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers"
            "::ToTypeFeaturing_Init::featuringType"
        ),
        "is_abstract": True,
        "return_type": "KerML::Core::Types::Type",
        "has_ocl_specification": False,
        "formal_redefinition_count": 0,
    },
])


target_names = [
    "KerML::Core::Features::Feature",
    "KerML::Core::Types::Type",
    "KerML::Core::Features::TypeFeaturing",
]

for name in target_names:
    matches = [
        e for e in registry.get_elements("KerML")
        if e.qualified_name == name
        and e.metaclass == "uml:Class"
    ]

    print(f"\n{name}: {len(matches)} matches")

    if matches:
        cls = matches[0]
        for member in direct_members(cls):
            print(member.metaclass, member.tag, member.name, member.xmi_id,)


# In[ ]:


feature = get_class_in_resource(
    registry, "KerML", "KerML::Core::Features::Feature"
)

relevant_names = {"featuringType", "ownedTypeFeaturing"}

for prop in registry.get_elements("KerML"):
    if prop.parent != feature.key or prop.name not in relevant_names:
        continue

    print(f"\n{prop.name}")
    print("Attributes:", prop.attributes)

    for ref in registry.get_references(prop.key):
        print({
            "element_tag": ref.element_tag,
            "value": ref.value,
            "target": (
                registry.elements[ref.target].qualified_name
                if ref.resolved else None
            ),
            "status": ref.resolution_status,
        })


# In[ ]:


association_ids = [
    "Core-Features-A_featuringType_featureOfType",
    "Core-Features-A_ownedTypeFeaturing_owningFeatureOfType",
    "Core-Features-A_featureOfType_typeFeaturing",
]

for xmi_id in association_ids:
    association_key = registry.elements_by_xmi_id[("KerML", xmi_id)][0]
    association = registry.elements[association_key]
    print(f"\n{association.qualified_name}")

    for ref in registry.get_references(association.key):
        if ref.element_tag != "memberEnd" or not ref.resolved:
            continue
        end = registry.elements[ref.target]

        print({
            "end": end.qualified_name,
            "attributes": end.attributes,
            "references": [
                {
                    "element_tag": r.element_tag,
                    "value": r.value,
                    "target": (registry.elements[r.target].qualified_name if r.resolved else None),
                }
                for r in registry.get_references(end.key)
            ],
        })


# In[ ]:


base = get_class_in_resource(
    registry,
    "SysML_v1_to_v2",
    "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToTypeFeaturing_Init",
)

for child in children_index.get(base.key, []):
    print(f"\n{'=' * 70}")
    print("Subclass:", child.qualified_name)
    print("Metaclass:", child.metaclass)
    print("Attributes:", child.attributes)

    operations = [
        element
        for element in registry.get_elements("SysML_v1_to_v2")
        if element.parent == child.key
        and element.metaclass == "uml:Operation"
    ]

    print("Direct operations:")
    for operation in operations:
        print({
            "name": operation.name,
            "attributes": operation.attributes,
            "redefinitions": [
                {
                    "target": (
                        registry.elements[ref.target].qualified_name
                        if ref.resolved else ref.value
                    ),
                    "status": ref.resolution_status,
                }
                for ref in registry.get_references(operation.key)
                if ref.element_tag == "redefinedOperation"
            ],
        })


# In[ ]:


child = get_class_in_resource(registry, "SysML_v1_to_v2", "SysMLv1Tov2::Mappings::Initializers::KerMLInitializers::ToFeatureMembership_Init",)

print("Class:", child.qualified_name)

print("\nDirect parents:")
for parent in parents_index.get(child.key, []):
    print(parent.qualified_name)

print("\nDirect properties:")
for element in registry.get_elements("SysML_v1_to_v2"):
    if element.parent == child.key and element.metaclass == "uml:Property":
        print({
            "name": element.name,
            "attributes": element.attributes,
            "references": [
                {
                    "reference": ref.element_tag,
                    "target": (
                        registry.elements[ref.target].qualified_name
                        if ref.resolved else ref.value
                    ),
                }
                for ref in registry.get_references(element.key)
            ],
        })


# In[ ]:


ancestors = get_ancestors(child, parents_index)

hierarchy = [child] + [
    registry.elements[ancestor.key]
    for ancestor in ancestors
]

print("Inheritance hierarchy:")
for element in hierarchy:
    print(element.qualified_name)

print("\nOperation declarations:")
for owner in hierarchy:
    operations = [
        element
        for element in registry.get_elements("SysML_v1_to_v2")
        if element.parent == owner.key
        and element.metaclass == "uml:Operation"
    ]

    for operation in operations:
        redefinitions = [
            registry.elements[ref.target].qualified_name
            if ref.resolved else ref.value
            for ref in registry.get_references(operation.key)
            if ref.element_tag == "redefinedOperation"
        ]

        print({
            "declared_by": owner.qualified_name,
            "operation": operation.name,
            "abstract": operation.attributes.get("isAbstract"),
            "redefines": redefinitions,
        })


# In[ ]:


base = child  # ToFeatureMembership_Init

descendants = get_ancestors(base, children_index)

concrete_descendants = [
    element for element in descendants
    if element.metaclass == "uml:Class"
    and element.attributes.get("isAbstract") != "true"
]

print("Total descendants:", len(descendants))
print("Concrete descendants:", len(concrete_descendants))

for cls in concrete_descendants:
    operations = [
        element
        for element in registry.get_elements("SysML_v1_to_v2")
        if element.parent == cls.key
        and element.metaclass == "uml:Operation"
    ]

    print({
        "class": cls.qualified_name,
        "direct_operations": [op.name for op in operations],
    })


# In[ ]:


from collections import Counter, defaultdict

operation_counts = Counter()
override_classes = defaultdict(list)
direct_operation_records = []

abstract_endpoint_operations = {
    "featureOfType",
    "featuringType",
}

for cls in concrete_descendants:
    operations = [
        element
        for element in registry.get_elements("SysML_v1_to_v2")
        if element.parent == cls.key
        and element.metaclass == "uml:Operation"
    ]

    for operation in operations:
        operation_counts[operation.name] += 1

        direct_operation_records.append({
            "class": cls.qualified_name,
            "operation": operation.name,
            "abstract": operation.attributes.get("isAbstract"),
        })

        if operation.name in abstract_endpoint_operations:
            override_classes[operation.name].append(
                cls.qualified_name
            )

print("Direct operation declaration counts:")
for name, count in operation_counts.most_common():
    print(f"{name}: {count}")

print("\nDirect declarations of abstract endpoint operations:")
for name in sorted(abstract_endpoint_operations):
    print(name, override_classes[name])

print("\nConcrete descendants:", len(concrete_descendants))


# In[ ]:


for cls in concrete_descendants:
    if "::Factories::" not in cls.qualified_name:
        continue

    operations = [
        element
        for element in registry.get_elements("SysML_v1_to_v2")
        if element.parent == cls.key
        and element.metaclass == "uml:Operation"
        and element.name == "create"
    ]

    for operation in operations:
        specs = ocl_specifications[
            ocl_specifications["operation_id"] == operation.key
        ]

        print(f"\n{'=' * 80}")
        print("Factory:", cls.qualified_name)

        for _, spec in specs.iterrows():
            print({
                "language": spec["language"],
                "body": spec["body"],
            })


# In[ ]:


direct_ops = []

for cls in concrete_descendants:
    for operation in registry.get_elements("SysML_v1_to_v2"):
        if (
            operation.parent == cls.key
            and operation.metaclass == "uml:Operation"
        ):
            direct_ops.append({
                "class": cls.qualified_name,
                "operation": operation,
                "operation_name": operation.name,
            })

owned_member_feature = [
    record for record in direct_ops
    if record["operation_name"] == "ownedMemberFeature"
]

print("ownedMemberFeature declarations:", len(owned_member_feature))

for record in owned_member_feature[:5]:
    operation = record["operation"]

    specs = ocl_specifications[
        ocl_specifications["operation_id"] == operation.key
    ]

    print(f"\n{'=' * 80}")
    print("Class:", record["class"])
    print("Operation:", operation.name)

    for _, spec in specs.iterrows():
        print({
            "language": spec["language"],
            "body": spec["body"],
        })


# In[ ]:


non_factory_owned_member_feature = [
    record for record in owned_member_feature
    if "::Mappings::Factories::" not in record["class"]
]

print(
    "Non-factory declarations:",
    len(non_factory_owned_member_feature),
)

for record in non_factory_owned_member_feature[:10]:
    operation = record["operation"]

    specs = ocl_specifications[
        ocl_specifications["operation_id"] == operation.key
    ]

    print(f"\n{'=' * 80}")
    print("Class:", record["class"])

    for _, spec in specs.iterrows():
        print({
            "language": spec["language"],
            "body": spec["body"],
        })


# In[ ]:


delegation_records = []

for record in non_factory_owned_member_feature:
    operation = record["operation"]

    specs = ocl_specifications[
        ocl_specifications["operation_id"] == operation.key
    ]

    for _, spec in specs.iterrows():
        body = spec["body"]

        callees = re.findall(
            r"\b([A-Za-z_]\w*)\.getMapped\s*\(",
            body,
        )

        for callee in callees:
            resolved_records, resolution_status = (
                resolve_mapping_class(callee)
            )

            resolved_class = (
                resolved_records[0].qualified_name
                if len(resolved_records) == 1
                else None
            )

            delegation_records.append({
                "caller_class": record["class"],
                "callee_name": callee,
                "resolved_class": resolved_class,
                "resolution_status": resolution_status,
                "body": body,
            })

delegation_table = pd.DataFrame(delegation_records)

print("Delegation calls:", len(delegation_table))
print("Unique callees:", delegation_table["callee_name"].nunique())
print(
    "Unresolved or ambiguous:",
    delegation_table["resolved_class"].isna().sum(),
)

display(
    delegation_table[
        [
            "caller_class",
            "callee_name",
            "resolved_class",
            "resolution_status",
        ]
    ].drop_duplicates()
)


# In[ ]:


unresolved_delegations = delegation_table[
    delegation_table["resolved_class"].isna()
]

display(
    unresolved_delegations[
        ["caller_class", "callee_name", "resolution_status", "body",]
    ].to_string(index=False)
)


# In[ ]:


callee_crosswalk = delegation_table.merge(
    mapping_table[
        ["mapping_name", "source_type", "target_type"]
    ],
    left_on="resolved_class",
    right_on="mapping_name",
    how="left",
    validate="many_to_one",
)

display(
    callee_crosswalk[
        [
            "caller_class",
            "callee_name",
            "source_type",
            "target_type",
        ]
    ].drop_duplicates()
)

print("Delegation calls:", len(callee_crosswalk))

print("\nMissing crosswalk entries:")
print(callee_crosswalk["source_type"].isna().sum())

print("\nDistinct source types:")
print(callee_crosswalk["source_type"].nunique())

print("\nDistinct target types:")
print(callee_crosswalk["target_type"].nunique())

display(
    callee_crosswalk
    .groupby(
        ["source_type", "target_type"],
        dropna=False
    )
    .size()
    .rename("call_count")
    .reset_index()
    .sort_values("call_count", ascending=False)
)


# In[ ]:


missing_crosswalk = callee_crosswalk[callee_crosswalk["source_type"].isna() | callee_crosswalk["target_type"].isna()]
display(missing_crosswalk[["caller_class", "callee_name", "resolved_class", "resolution_status", "source_type", "target_type", "body",]].drop_duplicates())

target_summary = (
    callee_crosswalk
    .groupby("target_type", dropna=False)
    .agg(
        call_count=("callee_name", "size"),
        distinct_mappings=("callee_name", "nunique"),
        distinct_callers=("caller_class", "nunique"),
        source_types=("source_type", "nunique"),
    )
    .reset_index()
    .sort_values(["call_count", "distinct_mappings"], ascending=False,)
)

display(target_summary)


# In[ ]:


feature_class = get_class_in_resource(registry, "KerML", "KerML::Core::Features::Feature",)
feature_descendants = get_ancestors(feature_class, target_children_index,)
feature_family = {feature_class.qualified_name, *(element.qualified_name for element in feature_descendants),}
callee_crosswalk["target_is_feature_or_subtype"] = (callee_crosswalk["target_type"].isin(feature_family))
print(callee_crosswalk["target_is_feature_or_subtype"] .value_counts(dropna=False))
display(callee_crosswalk[["callee_name", "target_type", "target_is_feature_or_subtype",]].drop_duplicates())


# In[ ]:


known_non_feature_targets = callee_crosswalk[callee_crosswalk["target_type"].notna() & ~callee_crosswalk["target_is_feature_or_subtype"]]

print("Known non-Feature targets:")
display(known_non_feature_targets[["callee_name", "source_type", "target_type"]].drop_duplicates())

print("\nMissing crosswalks:")
display(callee_crosswalk[
    callee_crosswalk["source_type"].isna() | callee_crosswalk["target_type"].isna()
    ][["callee_name", "resolved_class", "resolution_status"]].drop_duplicates())


# In[ ]:


missing_mapping_names = ["ObjectFlowItemFeatureUntyped_Mapping", "ObjectFlowItemFeature_Mapping", "AllocationUsageTargetFeature_Mapping",]

for name in missing_mapping_names:
    rows = mapping_table[mapping_table["mapping_name"] == name]

    print(f"\n{name}")
    print("Crosswalk rows:", len(rows))

    if not rows.empty:
        display(rows)


# In[ ]:


candidate_names = ["ObjectFlowItemFeatureUntyped_Mapping", "ObjectFlowItemFeature_Mapping", "AllocationUsageTargetFeature_Mapping",]

base_mapping_name = ("SysMLv1Tov2::Mappings::Foundations::Mapping")

for name in candidate_names:
    records, status = resolve_mapping_class(name)

    print(f"\n{'=' * 80}")
    print(name, "|", status)

    if len(records) != 1:
        print("Expected one class; found:", len(records))
        continue

    cls = records[0]
    ancestors = get_ancestors(cls, parents_index)

    formally_inherits_mapping = any(
        ancestor.qualified_name == base_mapping_name
        for ancestor in ancestors
    )

    print("Qualified name:", cls.qualified_name)
    print("Abstract:", cls.attributes.get("isAbstract"))
    print("Formally inherits Mapping:", formally_inherits_mapping)

    print("Direct from/to properties:")
    for element in registry.get_elements("SysML_v1_to_v2"):
        if (
            element.parent == cls.key
            and element.metaclass == "uml:Property"
            and element.name in {"from", "to"}
        ):
            print(
                element.name,
                element.xmi_id,
            )

    print("Ancestors:")
    for ancestor in ancestors:
        print(" ", ancestor.qualified_name)


# In[ ]:


candidate_names = [
    "ObjectFlowItemFeatureUntyped_Mapping",
    "ObjectFlowItemFeature_Mapping",
    "AllocationUsageTargetFeature_Mapping",
]

for name in candidate_names:
    records, status = resolve_mapping_class(name)

    if len(records) != 1:
        continue

    cls = records[0]
    hierarchy = [cls] + get_ancestors(cls, parents_index)

    print(f"\n{'=' * 80}")
    print(cls.qualified_name)

    for property_name in ("from", "to"):
        declarations = []

        for owner in hierarchy:
            for element in registry.get_elements("SysML_v1_to_v2"):
                if (
                    element.parent == owner.key
                    and element.metaclass == "uml:Property"
                    and element.name == property_name
                ):
                    declarations.append({
                        "property": property_name,
                        "declared_by": owner.qualified_name,
                        "property_id": element.xmi_id,
                        "type": [
                            registry.elements[ref.target].qualified_name
                            for ref in registry.get_references(element.key)
                            if ref.attribute == "type"
                            and ref.resolved
                            and ref.target in registry.elements
                        ],
                    })

        print(property_name, declarations)


# In[ ]:


cls = records[0]  # ObjectFlowItemFeatureUntyped_Mapping
prop = next(
    element
    for element in registry.get_elements("SysML_v1_to_v2")
    if element.parent == cls.key
    and element.metaclass == "uml:Property"
    and element.name == "from"
)

print("Attributes:")
for key, value in prop.attributes.items():
    print(key, "=", value)

print("\nReferences:")
for ref in registry.get_references(prop.key):
    print({
        "element_tag": ref.element_tag,
        "attribute": ref.attribute,
        "value": ref.value,
        "target": ref.target,
        "resolved": ref.resolved,
        "resolution_status": ref.resolution_status,
    })



for property_name in ("from", "to"):
    print(f"\n{property_name} declarations:")

    for owner in hierarchy:
        for element in registry.get_elements("SysML_v1_to_v2"):
            if (
                element.parent == owner.key
                and element.metaclass == "uml:Property"
                and element.name == property_name
            ):
                print("\n", owner.qualified_name)

                for ref in registry.get_references(element.key):
                    if ref.attribute == "redefinedProperty":
                        print({
                            "value": ref.value,
                            "target": ref.target,
                            "resolved": ref.resolved,
                        })


# In[ ]:


def get_property_references(prop, registry, element_tag):
    results = []

    for ref in registry.get_references(prop.key):
        if ref.element_tag != element_tag:
            continue

        target = (registry.elements.get(ref.target) if ref.resolved else None)

        results.append({
            "value": ref.value,
            "target": target.qualified_name if target else None,
            "resolved": ref.resolved,
            "resolution_status": ref.resolution_status,
        })

    return results

for name in candidate_names:
    records, status = resolve_mapping_class(name)

    if len(records) != 1:
        continue

    cls = records[0]
    hierarchy = [cls] + get_ancestors(cls, parents_index)

    print(f"\n{'=' * 80}")
    print(cls.qualified_name)

    for property_name in ("from", "to"):
        declarations = []

        for owner in hierarchy:
            for prop in registry.get_elements("SysML_v1_to_v2"):
                if (
                    prop.parent == owner.key
                    and prop.metaclass == "uml:Property"
                    and prop.name == property_name
                ):
                    declarations.append({
                        "declared_by": owner.qualified_name,
                        "property_id": prop.xmi_id,
                        "type": get_property_references(
                            prop, registry, "type"
                        ),
                        "redefines": get_property_references(
                            prop, registry, "redefinedProperty"
                        ),
                    })

        print(f"\n{property_name}:")
        for declaration in declarations:
            print(declaration)


# ### Resolution:

# In[ ]:


terms = ("LiteralUnlimited", "UnlimitedNatural", "Unbounded", "upperValue",)

for resource in ("SysML_v1_to_v2", "UML_Metamodel", "UML_PrimitiveTypes", "KerML", "SysML_v2",):
    print(f"\n{'=' * 70}\n{resource}")

    matches = []

    for element in registry.get_elements(resource):
        name = element.name or ""
        attributes = str(element.attributes)

        if any(term in name or term in attributes for term in terms):
            matches.append(element)

    for element in matches:
        print(element.metaclass, element.qualified_name, element.xmi_id,)


# In[ ]:


print(ocl_mapping_calls.columns.tolist())
print(ocl_mapping_calls.head(2).to_string())


# In[ ]:


literal_names = {
    "LiteralUnlimitedToInteger_Mapping",
    "LiteralUnlimitedToUnbounded_Mapping",
}

literal_calls = ocl_mapping_calls.loc[
    ocl_mapping_calls["callee"].isin(literal_names), 
    ["operation", "constraint_name", "language", "callee", "method", "arguments", 
     "call_expression", "candidate_classes", "target_class", "resolution_status", "reference_type",],
     ].copy()

print(literal_calls.to_string(index=False))


# In[ ]:


operation_names = literal_calls["operation"].unique()

literal_specs = ocl_specifications.loc[ocl_specifications["operation"].isin(operation_names)].copy()

print(
    literal_specs[
        ["operation", "constraint_name", "language", "body"]
    ].to_string(index=False)
)


# In[ ]:


source_names = {"MultiplicityElement", "LiteralUnlimitedNatural", "LiteralInteger", "ValueSpecification",}

for element in registry.get_elements("UML_Metamodel"):
    if element.name in source_names:
        print(
            element.metaclass,
            element.qualified_name,
            element.xmi_id,
        )


# In[ ]:


multiplicity = get_class_in_resource(registry, "UML_Metamodel", "UML::CommonStructure::MultiplicityElement",)

for prop in registry.get_elements("UML_Metamodel"):
    if (prop.parent == multiplicity.key and prop.metaclass == "uml:Property" and prop.name in {"upper", "upperValue"}):
        print("\nProperty:", prop.name)
        print("Attributes:", prop.attributes)

        for ref in registry.get_references(prop.key):
            print({
                "element_tag": ref.element_tag,
                "value": ref.value,
                "target": (registry.elements[ref.target].qualified_name if ref.resolved and ref.target in registry.elements else None),
                "resolved": ref.resolved,
            })


# In[ ]:


target_names = {"LiteralInteger", "LiteralInfinity", "LiteralUnlimitedNatural", "Unbounded", "Multiplicity", "MultiplicityRange",}

for resource in ("KerML", "SysML_v2"):
    print(f"\n{'=' * 70}\n{resource}")

    for element in registry.get_elements(resource):
        if element.name in target_names:
            print(element.metaclass, element.qualified_name, element.xmi_id,)


# In[ ]:


mapping_name = ("SysMLv1Tov2::Mappings::UML4SysML::Classification::" "UpperBoundValueFeatureMembership_Mapping")

records, status = resolve_mapping_class(mapping_name)

print("Resolution:", status)

if len(records) == 1:
    cls = records[0]

    print("Class:", cls.qualified_name)

    for prop in registry.get_elements("SysML_v1_to_v2"):
        if (
            prop.parent == cls.key
            and prop.metaclass == "uml:Property"
            and prop.name in {"from", "to"}
        ):
            print(
                prop.name,
                get_property_references(prop, registry, "type"),
            )


# In[ ]:


def inspect_class_structure(registry, resource, qualified_name):
    cls = get_class_in_resource(registry, resource, qualified_name)

    print(f"\n{'=' * 80}")
    print(cls.qualified_name)

    print("\nGeneralizations:")
    for ref in registry.get_references(cls.key):
        if ref.element_tag == "general":
            target = (
                registry.elements.get(ref.target)
                if ref.resolved else None
            )
            print(target.qualified_name if target else ref.value)

    print("\nDirect properties:")
    for element in registry.get_elements(resource):
        if (
            element.parent == cls.key
            and element.metaclass == "uml:Property"
        ):
            print({
                "name": element.name,
                "id": element.xmi_id,
                "attributes": element.attributes,
                "type": get_property_references(
                    element, registry, "type"
                ),
            })


inspect_class_structure(
    registry, "UML_Metamodel",
    "UML::Values::LiteralUnlimitedNatural",
)

inspect_class_structure(
    registry, "UML_Metamodel",
    "UML::Values::LiteralInteger",
)

inspect_class_structure(
    registry, "KerML",
    "KerML::Kernel::Expressions::LiteralInteger",
)

inspect_class_structure(
    registry, "KerML",
    "KerML::Kernel::Expressions::LiteralInfinity",
)


# In[ ]:


mapping_name = (
    "SysMLv1Tov2::Mappings::UML4SysML::Classification::"
    "UpperBoundValueFeatureMembership_Mapping"
)

records, status = resolve_mapping_class(mapping_name)
assert len(records) == 1

cls = records[0]
hierarchy = [cls] + get_ancestors(cls, parents_index)

print("Class:", cls.qualified_name)
print("\nTarget declarations:")

for owner in hierarchy:
    for prop in registry.get_elements("SysML_v1_to_v2"):
        if (
            prop.parent == owner.key
            and prop.metaclass == "uml:Property"
            and prop.name == "to"
        ):
            print({
                "declared_by": owner.qualified_name,
                "type": get_property_references(
                    prop, registry, "type"
                ),
                "redefines": get_property_references(
                    prop, registry, "redefinedProperty"
                ),
            })


# In[ ]:


for qualified_name in ["KerML::Kernel::Expressions::LiteralInteger", "KerML::Kernel::Expressions::LiteralInfinity",]:
    cls= get_class_in_resource(registry, "KerML", qualified_name)

    ancestors = get_ancestors(cls, target_parents_index)

    print(f"\n{qualified_name}")
    print("Ancestors:")

    for ancestor in ancestors:
        print(" ", ancestor.qualified_name)

    print("Inherited properties:")

    hierarchy = [cls] + ancestors

    for owner in hierarchy:
        for prop in registry.get_elements("KerML"):
            if (prop.parent == owner.key and prop.metaclass == "uml:Property"):
                print(owner.qualified_name, prop.name, get_property_references(prop, registry, "type"),)


literal_infinity = get_class_in_resource(registry, "KerML", "KerML::Kernel::Expressions::LiteralInfinity",)
for resource in ("KerML", "SysML_v2", "SysML_v1_to_v2"):
    print(f"\n{'=' * 70}\n{resource}")
    for ref in registry.get_references():
        if (ref.resolved and ref.target == literal_infinity.key and ref.element_tag == "type"):
            source = registry.elements.get(ref.source)
            if source is not None:
                print(source.qualified_name, source.metaclass, source.name,)


# In[ ]:


def resolve_reference_target(ref):
    if not ref.resolved or ref.target is None:
        return None

    return registry.elements.get(ref.target)


def reference_target_name(ref):
    target = resolve_reference_target(ref)
    return target.qualified_name if target is not None else None

search_terms = ("LiteralUnlimited", "LiteralInteger", "LiteralInfinity",)

literal_classes = [
    e for e in registry.get_elements("SysML_v1_to_v2")
    if e.metaclass == "uml:Class"
    and any(term.lower() in (e.name or "").lower()
            for term in search_terms)
]

for cls in literal_classes:
    print("\n" + "=" * 90)
    print(cls.qualified_name)
    print("XMI ID:", cls.xmi_id)
    print("Abstract:", cls.attributes.get("isAbstract"))

    hierarchy = [cls] + get_ancestors(cls, parents_index)

    for property_name in ("from", "to"):
        print(f"\n{property_name} declarations:")

        for owner in hierarchy:
            for prop in registry.get_elements("SysML_v1_to_v2"):
                if (
                    prop.parent == owner.key
                    and prop.metaclass == "uml:Property"
                    and prop.name == property_name
                ):
                    refs = registry.get_references(source=prop.key)
                    print({
                        "declared_by": owner.qualified_name,
                        "property_id": prop.xmi_id,
                        "redefines": [
                            reference_target_name(ref)
                            for ref in refs
                            if ref.element_tag == "redefinedProperty"
                        ],

                        "type": [
                            reference_target_name(ref)
                            for ref in refs
                            if ref.element_tag == "type"
                        ],
                    })


candidate_names = {cls.qualified_name for cls in literal_classes}

for cls in literal_classes:
    print("\n" + "=" * 90)
    print(cls.qualified_name)

    hierarchy = [cls] + get_ancestors(cls, parents_index)

    for owner in hierarchy:
        operations = [
            e for e in registry.get_elements("SysML_v1_to_v2")
            if e.parent == owner.key
            and e.metaclass == "uml:Operation"
        ]

        for op in operations:
            specs = ocl_specifications[
                ocl_specifications["operation_id"].apply(
                    lambda x: x[1] == op.xmi_id
                )
            ]

            print("\nOperation:", owner.qualified_name + "::" + op.name)
            print("Abstract:", op.attributes.get("isAbstract"))

            if specs.empty:
                print("No extracted specification")
            else:
                for _, spec in specs.iterrows():
                    print("Language:", spec["language"])
                    print("Body:", spec["body"])


# In[ ]:


ref = next(
    ref for ref in refs
    if ref.element_tag == "redefinedProperty"
)

print(ref.target)
print(type(ref.target))
print(registry.elements.get(ref.target))



# #### Literal Mapping Root Cause Diff:
# 
# Finite conversion
# - The actual class declares from as UML LiteralUnlimitedNatural.
# - Its to property is KerML LiteralInteger.
# - Its value() operation returns from.value.
# - The target's value property is an integer.
# 
# Unlimited conversion
# - LiteralUnlimitedUnbounded_Mapping inherits the source declaration from LiteralUnlimitedInteger_Mapping.
# - It redefines the target property to KerML LiteralInfinity.
# - Its filter() operation explicitly requires from.value = -1.
# - LiteralInfinity has no direct value property, so the inherited value() operation is not needed to populate a target value property.
# 
# OCL call identity: LiteralUnlimitedToInteger_Mapping and LiteralUnlimitedToUnbounded_Mapping.
# Semantically corresponding class identities: LiteralUnlimitedInteger_Mapping and LiteralUnlimitedUnbounded_Mapping.

# In[ ]:


literal_aliases = {
    "LiteralUnlimitedToInteger_Mapping":
        "SysMLv1Tov2::Mappings::UML4SysML::Values::LiteralUnlimitedInteger_Mapping",

    "LiteralUnlimitedToUnbounded_Mapping":
        "SysMLv1Tov2::Mappings::UML4SysML::Values::LiteralUnlimitedUnbounded_Mapping",
}

literal_calls = ocl_mapping_calls.loc[ocl_mapping_calls["callee"].isin(literal_aliases)].copy()
literal_calls[["operation", "callee", "method", "arguments", "call_expression", "resolution_status",]]

for _, row in literal_calls.iterrows():
    print("\nCaller:", row["operation"])
    print("Call:", row["call_expression"])
    print("Alias target:", literal_aliases[row["callee"]])

literal_calls["semantic_target_class"] = (literal_calls["callee"].map(literal_aliases))
literal_calls["semantic_resolution_status"] = ("resolved_semantic_alias")


# In[ ]:


print("dependency_edges:")
print(dependency_edges.columns.tolist())
print(dependency_edges.head())

print("\nocl_mapping_calls:")
print(ocl_mapping_calls.columns.tolist())
print(ocl_mapping_calls[["callee", "call_expression"]].head())


# In[ ]:


dependency_edges = dependency_edges.copy()

# Preserve the semantic alias separately from the original OCL callee.
dependency_edges["semantic_target_class"] = (
    dependency_edges["callee"].map(literal_aliases)
)

# Preserve the original resolution status unless an alias resolves the call.
alias_mask = dependency_edges["semantic_target_class"].notna()

dependency_edges["effective_target_class"] = (
    dependency_edges["target_class"].where(
        ~alias_mask,
        dependency_edges["semantic_target_class"],
    )
)

dependency_edges["effective_resolution_status"] = (
    dependency_edges["resolution_status"].where(
        ~alias_mask,
        "resolved_semantic_alias",
    )
)


# In[ ]:


literal_dependency_check = dependency_edges.loc[
    dependency_edges["semantic_target_class"].notna(),
    [
        "call_id",
        "source_class",
        "callee",
        "call_expression",
        "target_class",
        "semantic_target_class",
        "effective_target_class",  # Added
        "resolution_status",
        "effective_resolution_status",
    ],
]

print(literal_dependency_check.to_string(index=False))

assert len(literal_dependency_check) == 2
assert literal_dependency_check["call_id"].is_unique
assert literal_dependency_check["effective_target_class"].notna().all()


# In[ ]:


print(
    dependency_edges.groupby(
        "effective_resolution_status",
        dropna=False,
    ).agg(
        calls=("call_id", "size"),
        unique_callers=("source_class", "nunique"),
        unique_targets=("effective_target_class", "nunique"),
    ).sort_values("calls", ascending=False)
)

print("\nUnresolved calls:")
print(
    dependency_edges.loc[
        dependency_edges["effective_resolution_status"].eq("unresolved"),
        ["call_id", "source_class", "callee", "call_expression"],
    ].to_string(index=False)
)

print("\nValidation:")
print({
    "total_calls": len(dependency_edges),
    "unique_call_ids": dependency_edges["call_id"].nunique(),
    "resolved_calls": dependency_edges["effective_target_class"].notna().sum(),
    "unresolved_calls": dependency_edges["effective_resolution_status"].eq("unresolved").sum(),
})


# In[ ]:


unresolved_summary = (
    dependency_edges.loc[
        dependency_edges["effective_resolution_status"].eq("unresolved")
    ]
    .groupby("callee", dropna=False)
    .agg(
        call_count=("call_id", "size"),
        callers=("source_class", lambda x: sorted(set(x))),
        call_ids=("call_id", list),
    )
    .sort_values("call_count", ascending=False)
    .reset_index()
)

print(unresolved_summary.to_string(index=False))

unresolved_names = unresolved_summary["callee"].dropna().tolist()

unresolved_class_check = []

for callee in unresolved_names:
    records, status = resolve_mapping_class(callee)

    unresolved_class_check.append({
        "callee": callee,
        "resolution_status": status,
        "candidate_count": len(records),
        "candidate_classes": [
            record.qualified_name for record in records
        ],
    })

unresolved_class_check = pd.DataFrame(unresolved_class_check)

print(unresolved_class_check.to_string(index=False))


# In[ ]:


import difflib
import pandas as pd

all_transformation_classes = [e for e in registry.get_elements("SysML_v1_to_v2") if e.metaclass == "uml:Class"]
declared_class_names = {e.name: e.qualified_name for e in all_transformation_classes if e.name}
unresolved_candidates = []
for callee in unresolved_names:
    matches = difflib.get_close_matches(callee, declared_class_names.keys(), n=10, cutoff=0.45,)

    unresolved_candidates.append({
        "callee": callee,
        "similar_names": matches,
        "qualified_candidates": [declared_class_names[name] for name in matches],
    })

unresolved_candidate_table = pd.DataFrame(unresolved_candidates)
print(unresolved_candidate_table.to_string(index=False))


for callee in unresolved_names:
    matches = [e for e in registry.get_elements("SysML_v1_to_v2") if e.name == callee]
    print(f"\n{callee}: {len(matches)} exact-name matches")
    for e in matches:
        print(e.metaclass, e.qualified_name, e.xmi_id,)


# #### Difflib Candidate Mapping:

# In[ ]:


from difflib import SequenceMatcher

candidate_rows = []

for _, row in unresolved_candidate_table.iterrows():
    callee = row["callee"]

    for candidate in row["similar_names"]:
        qualified_name = declared_class_names[candidate]

        candidate_rows.append({
            "unresolved_callee": callee,
            "candidate_name": candidate,
            "candidate_class": qualified_name,
            "name_similarity": SequenceMatcher(
                None, callee, candidate
            ).ratio(),
        })

candidate_crosswalk = pd.DataFrame(candidate_rows)

candidate_crosswalk = candidate_crosswalk.merge(
    mapping_table[
        [
            "mapping_name",
            "source_type",
            "target_type",
            "operation_count",
            "operation_categories",
        ]
    ],
    left_on="candidate_class",
    right_on="mapping_name",
    how="left",
    validate="many_to_one",
    indicator=True,
)

candidate_crosswalk = candidate_crosswalk.sort_values(
    ["unresolved_callee", "name_similarity"],
    ascending=[True, False],
)

print(
    candidate_crosswalk[
        [
            "unresolved_callee",
            "candidate_name",
            "name_similarity",
            "source_type",
            "target_type",
            "operation_count",
            "_merge",
        ]
    ].to_string(index=False)
)


# In[ ]:


unresolved_context = dependency_edges.loc[
    dependency_edges["effective_resolution_status"].eq("unresolved"),
    [
        "call_id",
        "source_class",
        "operation",
        "callee",
        "arguments",
        "call_expression",
        "constraint_id",
    ],
].merge(
    ocl_specifications[
        ["constraint_id", "body"]
    ],
    on="constraint_id",
    how="left",
    validate="many_to_one",
)

for callee, group in unresolved_context.groupby("callee"):
    print(f"\n{'=' * 90}")
    print(callee)

    for _, row in group.iterrows():
        print(f"\nCall: {row['call_id']}")
        print(f"Caller: {row['operation']}")
        print(f"Expression: {row['call_expression']}")
        print(f"Body: {row['body']}")


# In[ ]:


candidate_names = [
    "InitialStateSubactionMembership_Mapping",
    "LiteralSpecificationFeatureTyping_Mapping",
    "ElementImport_Mapping",
    "DefaultValue_Mapping",
    "StereotypeMetadataDefinition_Mapping",
    "ChangeTriggerConstraintUsage_Mapping",
    "TimeTriggerCalculationUsage_Mapping",
    "PropertyCommon_Mapping",
]

candidate_classes = [
    e.qualified_name
    for e in all_transformation_classes
    if e.name in candidate_names
]

candidate_definitions = mapping_table.loc[
    mapping_table["mapping_name"].isin(candidate_classes),
    [
        "mapping_name",
        "source_type",
        "target_type",
        "operation_count",
        "operation_categories",
        "ancestors",
    ],
].copy()

print(candidate_definitions.to_string(index=False))

candidate_operation_specs = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(candidate_classes),
    [
        "mapping_name",
        "operation_name",
        "declared_by",
        "is_direct",
        "language",
        "body",
    ],
].copy()

print(candidate_operation_specs.to_string(index=False))

ambiguous_callers = [
    "SysMLv1Tov2::Mappings::UML4SysML::StructuredClassifiers::AssociationMetadataUsage_Mapping",
    "SysMLv1Tov2::Mappings::UML4SysML::SimpleClassifiers::AttributeRedefined_Mapping",
    "SysMLv1Tov2::Mappings::UML4SysML::Actions::Actions::ValuePin_Mapping",
    "SysMLv1Tov2::Mappings::UML4SysML::Actions::ObjectActions::COAPin_Mapping",
    "SysMLv1Tov2::Mappings::UML4SysML::Classification::PropertySubsetting_Mapping",
    "SysMLv1Tov2::Mappings::UML4SysML::Classification::InstanceSpecification_Mapping",
]

print(
    mapping_table.loc[
        mapping_table["mapping_name"].isin(ambiguous_callers),
        [
            "mapping_name",
            "source_type",
            "target_type",
            "ancestors",
        ],
    ].to_string(index=False)
)


# In[ ]:


candidate_short_names = {
    "ChangeTriggerConstraintUsage_Mapping",
    "TimeTriggerCalculationUsage_Mapping",
    "ElementImport_Mapping",
    "InitialStateSubactionMembership_Mapping",
    "LiteralSpecificationFeatureTyping_Mapping",
    "StereotypeMetadataDefinition_Mapping",
    "DefaultValue_Mapping",
    "PropertyCommon_Mapping",
}

candidate_rows = mapping_table.loc[
    mapping_table["mapping_name"]
        .str.rsplit("::", n=1)
        .str[-1]
        .isin(candidate_short_names)
]

candidate_names = set(candidate_rows["mapping_name"])

candidate_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(candidate_names),
    [
        "mapping_name",
        "operation_name",
        "declared_by",
        "is_direct",
        "language",
        "body",
    ],
].sort_values(
    ["mapping_name", "is_direct", "operation_name"],
    ascending=[True, False, True],
)

display(candidate_rows[
    ["mapping_name", "source_type", "target_type", "operation_count"]
])

display(candidate_ops)


# In[ ]:


unresolved_callers = set(dependency_edges.loc[dependency_edges["dependency_status"] == "unresolved", "source_class",])

caller_rows = mapping_table.loc[
    mapping_table["mapping_name"].isin(unresolved_callers),
    ["mapping_name", "source_type", "target_type"],
].sort_values("mapping_name")

display(caller_rows)


# In[ ]:


inspect_names = {
    "ChangeTriggerConstraintUsage_Mapping",
    "TimeTriggerCalculationUsage_Mapping",
    "ElementImport_Mapping",
    "InitialStateSubactionMembership_Mapping",
    "PropertyCommon_Mapping",
}

inspect_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"]
        .str.rsplit("::", n=1)
        .str[-1]
        .isin(inspect_names)
    & mapping_operation_specifications["is_direct"],
    [
        "mapping_name",
        "operation_name",
        "language",
        "body",
    ],
].sort_values(["mapping_name", "operation_name"])

for row in inspect_ops.itertuples(index=False):
    print(f"\n{row.mapping_name}::{row.operation_name}")
    print(f"Language: {row.language}")
    print(row.body)


# In[ ]:


caller_short_names = {"PropertySubsetting_Mapping", "AssociationMetadataUsage_Mapping", "AttributeRedefined_Mapping", "UseCase_Mapping", "Behavior_Mapping", "OpaqueBehavior_Mapping",}

caller_rows = mapping_table.loc[
    mapping_table["mapping_name"]
        .str.rsplit("::", n=1)
        .str[-1]
        .isin(caller_short_names),
    ["mapping_name", "source_type", "target_type"],
].sort_values("mapping_name")

caller_names = set(caller_rows["mapping_name"])

caller_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(caller_names)
    & mapping_operation_specifications["is_direct"],
    ["mapping_name", "operation_name", "language", "body",],
].sort_values(["mapping_name", "operation_name"])

display(caller_rows)

for row in caller_ops.itertuples(index=False):
    print(f"\n{row.mapping_name}::{row.operation_name}")
    print(f"Language: {row.language}")
    print(row.body)


# In[ ]:


property_membership_candidates = mapping_table.loc[
    mapping_table["source_type"].str.contains(
        r"UML::Classification::Property",
        na=False,
    )
    & mapping_table["target_type"].str.contains(
        r"Membership",
        na=False,
    ),
    [
        "mapping_name",
        "source_type",
        "target_type",
        "operation_count",
        "operation_categories",
        "ancestors",
    ],
].sort_values(["target_type", "mapping_name"])

display(property_membership_candidates)


# In[ ]:


association_typing_candidates = mapping_table.loc[
    mapping_table["target_type"].str.endswith(
        "FeatureTyping",
        na=False,
    )
    & mapping_table["source_type"].str.contains(
        r"Association|Property|StructuralFeature",
        na=False,
    ),
    [
        "mapping_name",
        "source_type",
        "target_type",
        "operation_count",
        "operation_categories",
        "ancestors",
    ],
].sort_values(["source_type", "mapping_name"])

display(association_typing_candidates)


# In[ ]:


membership_candidates = mapping_table.loc[
    mapping_table["target_type"].str.endswith(("FeatureMembership", "EndFeatureMembership"), na=False,)
    & mapping_table["source_type"].str.contains(r"UML::.*(Property|StructuralFeature)", na=False,),
    ["mapping_name", "source_type", "target_type", "operation_count", "operation_categories", "ancestors",],
].sort_values(["source_type", "target_type", "mapping_name"])

display(membership_candidates.to_string(index=False))

typing_candidate_names = {
    "AssociationMetadataUsageFeatureTyping_Mapping", 
    "AttributeRedefinedFeatureTyping_Mapping", 
    "NonOwnedEndFeatureTyping_Mapping", 
    "StructuralFeatureToFeatureTyping_Mapping",
    }

typing_candidates = mapping_table.loc[mapping_table["mapping_name"] .str.rsplit("::", n=1) .str[-1] .isin(typing_candidate_names)]
display(typing_candidates[["mapping_name", "source_type", "target_type", "operation_count"]].to_string(index=False))

typing_names = set(typing_candidates["mapping_name"])

typing_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(typing_names)
    & mapping_operation_specifications["is_direct"],
    ["mapping_name", "operation_name", "language", "body"],
]

for row in typing_ops.itertuples(index=False):
    print(f"\n{row.mapping_name}::{row.operation_name}")
    print(row.body)


property_candidate_names = {"PropertyCommon_Mapping", "PropertySubsetting_Mapping", "StructuralFeatureMembership_Mapping",}
property_candidates = mapping_table.loc[mapping_table["mapping_name"] .str.rsplit("::", n=1) .str[-1] .isin(property_candidate_names)]
display(property_candidates[
    ["mapping_name", "source_type", "target_type", "operation_count"]
].to_string(index=False))


# In[ ]:


inspect_short_names = {
    "StructuralFeatureMembership_Mapping",
    "EndMembership_Mapping",
    "OwnedEndMembership_Mapping",
    "NonOwnedEndMembership_Mapping",
    "ConnectionDefEndMembership_Mapping",
    "NonOwnedEndToSubsettedFeatureMembership_Mapping",
    "StructuralFeatureToFeatureTyping_Mapping",
    "AttributeRedefinedFeatureTyping_Mapping",
    "AssociationMetadataUsageFeatureTyping_Mapping",
    "PropertyCommon_Mapping",
}

inspect_rows = mapping_table.loc[
    mapping_table["mapping_name"]
        .str.rsplit("::", n=1)
        .str[-1]
        .isin(inspect_short_names)
]

display(inspect_rows[
    [
        "mapping_name",
        "source_type",
        "target_type",
        "source_property_declared_by",
        "target_property_declared_by",
    ]
].to_string(index=False))


# In[ ]:


inspect_names = set(inspect_rows["mapping_name"])

inspect_declarations = mapping_operation_declarations.loc[
    mapping_operation_declarations["mapping_name"].isin(inspect_names),
    [
        "mapping_name",
        "operation_name",
        "declared_by",
        "is_direct",
        "redefined_operations",
    ],
].sort_values(["mapping_name", "operation_name", "is_direct"])

display(inspect_declarations.to_string(index=False))


# In[ ]:


initializer_names = {
    "ToFeatureMembership_Init",
    "ToOwningMembership_Init",
    "ToMembership_Init",
    "ToFeatureTyping_Init",
    "ToSpecialization_Init",
}

initializer_records = [
    e for e in registry.get_elements("SysML_v1_to_v2")
    if e.qualified_name
    and e.qualified_name.rsplit("::", 1)[-1] in initializer_names
]

for cls in initializer_records:
    print(f"\n{cls.qualified_name}")

    members = [
        e for e in registry.get_elements("SysML_v1_to_v2")
        if e.parent == cls.key
        and e.tag in {"ownedAttribute", "ownedOperation"}
    ]

    for member in members:
        print(
            member.tag,
            member.name,
            member.xmi_id,
        )


# In[ ]:


membership_short_names = {
    "StructuralFeatureMembership_Mapping",
    "EndMembership_Mapping",
    "OwnedEndMembership_Mapping",
    "NonOwnedEndMembership_Mapping",
    "ConnectionDefEndMembership_Mapping",
    "NonOwnedEndToSubsettedFeatureMembership_Mapping",
}

membership_names = set(
    mapping_table.loc[
        mapping_table["mapping_name"]
            .str.rsplit("::", n=1)
            .str[-1]
            .isin(membership_short_names),
        "mapping_name",
    ]
)

membership_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(membership_names)
    & mapping_operation_specifications["is_direct"],
    ["mapping_name", "operation_name", "language", "body"],
]

for row in membership_ops.itertuples(index=False):
    print(f"\n{row.mapping_name}::{row.operation_name}")
    print(row.body)


# In[ ]:


candidate_short_names = {
    "StructuralFeatureMembership_Mapping",
    "PropertyCommon_Mapping",
    "AssociationMetadataUsageFeatureTyping_Mapping",
    "AttributeRedefinedFeatureTyping_Mapping",
}

candidate_names = set(
    mapping_table.loc[
        mapping_table["mapping_name"]
            .str.rsplit("::", n=1)
            .str[-1]
            .isin(candidate_short_names),
        "mapping_name",
    ]
)

relevant_operations = {
    "type",
    "typedFeature",
    "specific",
    "general",
    "ownedMemberFeature",
    "ownedRelatedElement",
    "visibility",
    "memberElement",
    "membershipOwningNamespace",
}

ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(candidate_names)
    & mapping_operation_specifications["operation_name"].isin(
        relevant_operations
    ),
    [
        "mapping_name",
        "operation_name",
        "declared_by",
        "is_direct",
        "language",
        "body",
    ],
].sort_values(["mapping_name", "operation_name", "is_direct"])

for row in ops.itertuples(index=False):
    print(f"\n{row.mapping_name}::{row.operation_name}")
    print(f"Declared by: {row.declared_by}")
    print(f"Direct: {row.is_direct}")
    print(f"Language: {row.language}")
    print(row.body)


# In[ ]:


initializer_names = {
    "ToFeatureMembership_Init",
    "ToMembership_Init",
    "ToFeatureTyping_Init",
}

initializer_classes = {
    e.qualified_name
    for e in registry.get_elements("SysML_v1_to_v2")
    if e.qualified_name
    and e.qualified_name.rsplit("::", 1)[-1] in initializer_names
}

initializer_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["declared_by"].isin(initializer_classes),
    [
        "mapping_name",
        "operation_name",
        "declared_by",
        "language",
        "body",
    ],
].drop_duplicates(subset=["declared_by", "operation_name"])

for row in initializer_ops.itertuples(index=False):
    print(f"\n{row.declared_by}::{row.operation_name}")
    print(row.body)


# In[ ]:


short_names = {
    "StructuralFeatureMembership_Mapping",
    "AssociationMetadataUsageFeatureTyping_Mapping",
    "AttributeRedefinedFeatureTyping_Mapping",
}

candidate_names = set(
    mapping_table.loc[
        mapping_table["mapping_name"]
            .str.rsplit("::", n=1)
            .str[-1]
            .isin(short_names),
        "mapping_name",
    ]
)

candidate_ops = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].isin(candidate_names)
    & mapping_operation_specifications["is_direct"],
    [
        "mapping_name",
        "operation_name",
        "language",
        "body",
    ],
].sort_values(["mapping_name", "operation_name"])

for row in candidate_ops.itertuples(index=False):
    print(f"\n{row.mapping_name}::{row.operation_name}")
    print(row.body)


# In[ ]:


association_name = next(
    name for name in candidate_names
    if name.endswith("AssociationMetadataUsageFeatureTyping_Mapping")
)

association_row = mapping_table.loc[
    mapping_table["mapping_name"] == association_name
].iloc[0]

print("Ancestors:")
for ancestor in association_row["ancestors"]:
    print(" ", ancestor)

print("\nDirect operations:")
print(
    candidate_ops.loc[
        candidate_ops["mapping_name"] == association_name
    ].to_string(index=False)
)


# ### Final Validation and Refactor:

# In[ ]:


import pandas as pd
import time
print(time.time())

semantic_alias_rules = pd.DataFrame([
    {
        "caller_suffix": "PropertySubsetting_Mapping",
        "callee": "Property_Mapping",
        "semantic_target_class": ("SysMLv1Tov2::Mappings::UML4SysML::Classification" "::PropertyCommon_Mapping"),
        "semantic_alias_rule": "property_to_common_property",
        "semantic_alias_evidence": (
            "Both call arguments are UML Property; candidate source is "
            "UML Property and target is KerML Feature; target property "
            "is inherited from ToFeature_Init."
        ),
        "semantic_alias_confidence": "high",
    },
    {
        "caller_suffix": "Behavior_Mapping",
        "callee": "PropertyMembership_Mapping",
        "semantic_target_class": (
            "SysMLv1Tov2::Mappings::UML4SysML::Classification"
            "::StructuralFeatureMembership_Mapping"
        ),
        "semantic_alias_rule": "property_to_structural_feature_membership",
        "semantic_alias_evidence": (
            "Caller maps UML Properties into owned relationships; "
            "Property specializes StructuralFeature; candidate maps "
            "StructuralFeature to FeatureMembership and supplies "
            "ownedMemberFeature and visibility."
        ),
        "semantic_alias_confidence": "high",
    },
    {
        "caller_suffix": "OpaqueBehavior_Mapping",
        "callee": "PropertyMembership_Mapping",
        "semantic_target_class": (
            "SysMLv1Tov2::Mappings::UML4SysML::Classification"
            "::StructuralFeatureMembership_Mapping"
        ),
        "semantic_alias_rule": "property_to_structural_feature_membership",
        "semantic_alias_evidence": (
            "Caller maps UML Properties into owned relationships; "
            "Property specializes StructuralFeature; candidate maps "
            "StructuralFeature to FeatureMembership and supplies "
            "ownedMemberFeature and visibility."
        ),
        "semantic_alias_confidence": "high",
    },
    {
        "caller_suffix": "UseCase_Mapping",
        "callee": "PropertyMembership_Mapping",
        "semantic_target_class": (
            "SysMLv1Tov2::Mappings::UML4SysML::Classification"
            "::StructuralFeatureMembership_Mapping"
        ),
        "semantic_alias_rule": "property_to_structural_feature_membership",
        "semantic_alias_evidence": (
            "Caller maps owned UML Properties into memberships; "
            "the caller's property selection excludes association "
            "properties; candidate maps StructuralFeature to "
            "FeatureMembership."
        ),
        "semantic_alias_confidence": "high",
    },
    {
        "caller_suffix": "AssociationMetadataUsage_Mapping",
        "callee": "AssociationToFeatureTyping_Mapping",
        "semantic_target_class": (
            "SysMLv1Tov2::Mappings::UML4SysML::StructuredClassifiers"
            "::AssociationMetadataUsageFeatureTyping_Mapping"
        ),
        "semantic_alias_rule": "association_metadata_feature_typing",
        "semantic_alias_evidence": (
            "Caller supplies UML Association; candidate source is "
            "UML Association and target is KerML FeatureTyping; "
            "direct type operation selects SysMLv1Library::AssociationData."
        ),
        "semantic_alias_confidence": "high",
    },
    {
        "caller_suffix": "AttributeRedefined_Mapping",
        "callee": "AssociationToFeatureTyping_Mapping",
        "semantic_target_class": (
            "SysMLv1Tov2::Mappings::UML4SysML::SimpleClassifiers"
            "::AttributeRedefinedFeatureTyping_Mapping"
        ),
        "semantic_alias_rule": "redefined_attribute_feature_typing",
        "semantic_alias_evidence": (
            "Caller supplies UML StructuralFeature; candidate source "
            "is UML StructuralFeature and target is KerML FeatureTyping; "
            "candidate inherits StructuralFeatureToFeatureTyping_Mapping."
        ),
        "semantic_alias_confidence": "high",
    },
    {
    "caller_suffix": "ValuePin_Mapping",
    "callee": "PinFeatureTyping_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::Actions::VariableActions"
        "::RVAReferenceUsageFeatureTyping_Mapping"
    ),
    "semantic_alias_rule": "pin_feature_typing",
    "semantic_alias_evidence": (
        "Caller maps UML ValuePin to ReferenceUsage and invokes "
        "PinFeatureTyping_Mapping. Candidate source is UML Pin and "
        "target is KerML FeatureTyping. It inherits the typed-element "
        "filter and type mapping, which maps the pin's UML type to "
        "the corresponding KerML typing relationship."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "COAPin_Mapping",
    "callee": "PinFeatureTyping_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::Actions::VariableActions"
        "::RVAReferenceUsageFeatureTyping_Mapping"
    ),
    "semantic_alias_rule": "pin_feature_typing",
    "semantic_alias_evidence": (
        "Caller maps UML OutputPin to ReferenceUsage and invokes "
        "PinFeatureTyping_Mapping. Candidate source is UML Pin and "
        "target is KerML FeatureTyping. Its inherited typed-element "
        "mapping uses the pin's UML type to construct the typing "
        "relationship."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "LiteralSpecificationCommon_Mapping",
    "callee": "LiteralSpecificationTyping_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::Values"
        "::LiteralSpecificationFeatureTyping_Mapping"
    ),
    "semantic_alias_rule": "literal_specification_feature_typing",
    "semantic_alias_evidence": (
        "Caller maps UML LiteralSpecification to KerML "
        "LiteralExpression and invokes LiteralSpecificationTyping_Mapping "
        "when the source has a defined type. Candidate maps UML "
        "LiteralSpecification to KerML FeatureTyping. It inherits the "
        "typed-element filter and type mapping, which maps the source "
        "element's UML type to the corresponding KerML typing relationship."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "TimeExpression_Mapping",
    "callee": "LiteralSpecificationTyping_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::Values"
        "::LiteralSpecificationFeatureTyping_Mapping"
    ),
    "semantic_alias_rule": "literal_specification_feature_typing",
    "semantic_alias_evidence": (
        "Caller maps UML TimeExpression to KerML Expression and invokes "
        "LiteralSpecificationTyping_Mapping when the source has a "
        "defined type. Candidate maps UML LiteralSpecification to KerML "
        "FeatureTyping and inherits the typed-element filter and type "
        "mapping. The candidate's source type is compatible with the "
        "literal-specification typing operation, although the concrete "
        "implementation of its inherited typedFeature operation has not "
        "been independently verified."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "ValueSpecification_Mapping",
    "callee": "LiteralSpecificationTyping_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::Values"
        "::LiteralSpecificationFeatureTyping_Mapping"
    ),
    "semantic_alias_rule": "literal_specification_feature_typing",
    "semantic_alias_evidence": (
        "Caller maps UML ValueSpecification to KerML Expression and "
        "invokes LiteralSpecificationTyping_Mapping when the source has "
        "a defined type. Candidate maps UML LiteralSpecification to "
        "KerML FeatureTyping and inherits the typed-element filter and "
        "type mapping, which maps the source element's UML type to the "
        "corresponding KerML typing relationship. The concrete "
        "implementation of its inherited typedFeature operation has not "
        "been independently verified."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "Helper",
    "callee": "InitialStateMembership_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::StateMachines"
        "::InitialStateSubactionMembership_Mapping"
    ),
    "semantic_alias_rule": "initial_state_subaction_membership",
    "semantic_alias_evidence": (
        "The caller selects UML initial pseudostates and requests "
        "InitialStateMembership_Mapping.getMapped(e). The candidate "
        "inherits ToStateSubactionMembership_Init and "
        "ToFeatureMembership_Init, defines kind() as "
        "SysMLv2::SubactionKind::entry, and defines "
        "ownedMemberFeature() as InitialState_Mapping.getMapped(from)."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "Region_Mapping",
    "callee": "InitialStateMembership_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::StateMachines"
        "::InitialStateSubactionMembership_Mapping"
    ),
    "semantic_alias_rule": "initial_state_subaction_membership",
    "semantic_alias_evidence": (
        "Region_Mapping::ownedRelationship selects UML initial "
        "pseudostates and requests InitialStateMembership_Mapping."
        " The candidate inherits ToStateSubactionMembership_Init "
        "and ToFeatureMembership_Init, defines kind() as "
        "SysMLv2::SubactionKind::entry, and maps its member feature "
        "through InitialState_Mapping.getMapped(from)."
    ),
    "semantic_alias_confidence": "high",
},
{
    "caller_suffix": "StateDefinition_Mapping",
    "callee": "InitialStateMembership_Mapping",
    "semantic_target_class": (
        "SysMLv1Tov2::Mappings::UML4SysML::StateMachines"
        "::InitialStateSubactionMembership_Mapping"
    ),
    "semantic_alias_rule": "initial_state_subaction_membership",
    "semantic_alias_evidence": (
        "StateDefinition_Mapping::ownedRelationship selects UML "
        "initial pseudostates and requests InitialStateMembership_Mapping."
        " The candidate inherits ToStateSubactionMembership_Init "
        "and ToFeatureMembership_Init, defines kind() as "
        "SysMLv2::SubactionKind::entry, and maps its member feature "
        "through InitialState_Mapping.getMapped(from)."
    ),
    "semantic_alias_confidence": "high",
},
])

placeholder_mappings = pd.DataFrame([
    {
        "call_id": "CALL_00214",
        "original_target": "CommonElementImport_Mapping",
        "placeholder_name": "UNRESOLVED_CommonElementImport",
        "caller": "ElementGroup_Mapping",
        "operation": "getMapped",
        "arguments": ["e"],
        "expected_target_role": "Import-like relationship",
        "resolution_status": "placeholder",
    },
    {
        "call_id": "CALL_00380",
        "original_target": "DefaultValueOpaqueExpression_Mapping",
        "placeholder_name": "UNRESOLVED_DefaultValueOpaqueExpression",
        "caller": "OwnedEnd_Mapping",
        "operation": "getMapped",
        "arguments": ["from.defaultValue"],
        "expected_target_role": "Relationship",
        "resolution_status": "placeholder",
    },
    {
        "call_id": "CALL_00309",
        "original_target": "InstanceSpecificationToGeneralization_Mapping",
        "placeholder_name": "UNRESOLVED_InstanceSpecificationToGeneralization",
        "caller": "InstanceSpecification_Mapping",
        "operation": "getMapped",
        "arguments": ["from", "c"],
        "expected_target_role": "Feature membership",
        "resolution_status": "placeholder",
    },
])

def apply_semantic_aliases(dependency_edges, semantic_alias_rules, mapping_table,):
    edges = dependency_edges.copy()
    required = {"call_id", "source_class", "callee", "target_class", "resolution_status",}
    missing = required - set(edges.columns)
    if missing:
        raise ValueError(f"dependency_edges is missing columns: {sorted(missing)}")
    if edges["call_id"].duplicated().any():
        raise ValueError("call_id must uniquely identify call occurrences.")
    # Preserve the original exact-resolution fields.
    original_target = edges["target_class"].copy()
    original_status = edges["resolution_status"].copy()
    edges["caller_suffix"] = (edges["source_class"].str.rsplit("::", n=1).str[-1])
    edges["callee_short"] = (edges["callee"].str.rsplit("::", n=1).str[-1])
    # Semantic-resolution fields.
    edges["semantic_target_class"] = pd.NA
    edges["semantic_alias_rule"] = pd.NA
    edges["semantic_alias_evidence"] = pd.NA
    edges["semantic_alias_confidence"] = pd.NA
    # Only unresolved exact references can receive a semantic alias.
    unresolved = (edges["target_class"].isna() | edges["resolution_status"].eq("unresolved"))
    for rule in semantic_alias_rules.itertuples(index=False):
        mask = (unresolved & edges["caller_suffix"].eq(rule.caller_suffix) & edges["callee_short"].eq(rule.callee))
        # Do not silently assign multiple rules to one call.
        already_assigned = edges["semantic_target_class"].notna()
        if (mask & already_assigned).any():
            raise ValueError(f"Overlapping semantic alias rules for {rule.callee} from {rule.caller_suffix}")
        edges.loc[mask, "semantic_target_class"] = (rule.semantic_target_class)
        edges.loc[mask, "semantic_alias_rule"] = (rule.semantic_alias_rule)
        edges.loc[mask, "semantic_alias_evidence"] = (rule.semantic_alias_evidence)
        edges.loc[mask, "semantic_alias_confidence"] = (rule.semantic_alias_confidence)

    # Effective resolution is a derived view. It does not overwrite the original XMI/OCL resolution.
    edges["effective_target_class"] = (edges["target_class"].combine_first(edges["semantic_target_class"]))
    edges["effective_resolution_status"] = (edges["resolution_status"].copy())
    semantic_resolved = edges["semantic_target_class"].notna()
    edges.loc[semantic_resolved, "effective_resolution_status",] = "resolved_semantic_alias"

    # Verify that the original exact-resolution data was preserved.
    pd.testing.assert_series_equal(edges["target_class"], original_target, check_names=False,)
    pd.testing.assert_series_equal(edges["resolution_status"], original_status, check_names=False,)

    # Every semantic target must exist in the mapping inventory.
    known_mappings = set(mapping_table["mapping_name"])
    assigned_targets = set(edges["semantic_target_class"].dropna())
    unknown_targets = assigned_targets - known_mappings
    if unknown_targets:
        raise ValueError(f"Semantic targets absent from mapping_table: {sorted(unknown_targets)}")

    return edges


# In[ ]:


mapping_dependency_summary = (
    dependency_edges.groupby("source_class")
    .agg(
        dependency_count=("call_id", "size"),
        resolved_dependency_count=("effective_target_class", "count",),
        unresolved_dependency_count=("effective_target_class", lambda x: x.isna().sum(),),
        dependencies=("effective_target_class", lambda x: sorted(x.dropna().unique().tolist()),),
    )
    .reset_index()
    .rename(columns={"source_class": "mapping_name"})
)


# In[ ]:


mapping_analysis = mapping_table.merge(mapping_dependency_summary, on="mapping_name", how="left", validate="one_to_one",)


# In[ ]:


print(dependency_edges["effective_resolution_status"] .value_counts(dropna=False))

print(
    dependency_edges.groupby(["resolution_status", "effective_resolution_status"], dropna=False,)
    .size()
    .rename("count")
)


# In[ ]:


remaining_unresolved = dependency_edges.loc[dependency_edges["effective_target_class"].isna()].copy()

remaining_unresolved_summary = (
    remaining_unresolved.groupby(["source_class", "callee"], dropna=False,)
    .agg(call_count=("call_id", "size"), call_ids=("call_id", list), call_expressions=("call_expression", list),)
    .reset_index()
    .sort_values(["call_count", "source_class"], ascending=[False, True],)
)

print(remaining_unresolved_summary.to_string(index=False))


# In[ ]:


def mapping_name_by_suffix(mapping_table, suffix):
    matches = mapping_table.loc[mapping_table["mapping_name"].str.endswith(f"::{suffix}"), "mapping_name",].unique()

    if len(matches) != 1:
        raise ValueError(f"Expected one mapping ending in {suffix!r}; found {len(matches)}: {matches.tolist()}")
    return matches[0]


previously_validated_rules = [
    # Literal aliases: caller-independent.
    ("UpperBoundValueFeatureMembership_Mapping",
     "LiteralUnlimitedToInteger_Mapping",
     "LiteralUnlimitedInteger_Mapping"),

    ("UpperBoundValueFeatureMembership_Mapping",
     "LiteralUnlimitedToUnbounded_Mapping",
     "LiteralUnlimitedUnbounded_Mapping"),

    # Previously validated contextual aliases.
    ("ChangeTriggerExpressionFeatureTyping_Mapping",
     "TransitionChangeTriggerConstraintUsage_Mapping",
     "ChangeTriggerConstraintUsage_Mapping"),

    ("TimeTriggerExpressionFeatureTyping_Mapping",
     "TransitionTimeTriggerCalculationUsage_Mapping",
     "TimeTriggerCalculationUsage_Mapping"),

    ("AttributeRedefined_Mapping",
     "PropertyDefaultValue_Mapping",
     "DefaultValue_Mapping"),

    ("Region_Mapping",
     "InitialStateMembership_Mapping",
     "InitialStateSubactionMembership_Mapping"),

    ("StateDefinition_Mapping",
     "InitialStateMembership_Mapping",
     "InitialStateSubactionMembership_Mapping"),

    ("StereotypeOccurenceUsageFeatureTyping_Mapping",
     "StereotypeOccurenceDefinition_Mapping",
     "StereotypeMetadataDefinition_Mapping"),
]

previously_validated_rules = pd.DataFrame([
    {
        "caller_suffix": caller,
        "callee": callee,
        "semantic_target_class": mapping_name_by_suffix(mapping_table, target),
        "semantic_alias_rule": f"previously_validated_{target}",
        "semantic_alias_evidence": ("Previously investigated and accepted semantic mapping; " "original call identity is preserved."),
        "semantic_alias_confidence": "high",
    }
    for caller, callee, target in previously_validated_rules
])


# In[ ]:


# Preserve historical rules only for keys not already defined in the current semantic alias definition.
current_keys = set(zip(semantic_alias_rules["caller_suffix"], semantic_alias_rules["callee"],))
previously_validated_rules_filtered = previously_validated_rules.loc[
    ~previously_validated_rules.apply(
        lambda row: (row["caller_suffix"], row["callee"],) in current_keys,
        axis=1,
    )
].copy()
semantic_alias_rules = pd.concat([semantic_alias_rules, previously_validated_rules_filtered,], ignore_index=True,)


# In[ ]:


remaining_unresolved = dependency_edges.loc[
    dependency_edges["effective_target_class"].isna()
].copy()

remaining_unresolved_summary = (
    remaining_unresolved.groupby(
        ["source_class", "callee"],
        dropna=False,
    )
    .agg(
        call_count=("call_id", "size"),
        call_ids=("call_id", list),
        call_expressions=("call_expression", list),
    )
    .reset_index()
    .sort_values(
        ["callee", "source_class"],
    )
)

print(remaining_unresolved_summary.to_string(index=False))


# In[ ]:


previous_alias_specs = [
    ("UpperBoundValueFeatureMembership_Mapping", "LiteralUnlimitedToInteger_Mapping", "LiteralUnlimitedInteger_Mapping",),
    ("UpperBoundValueFeatureMembership_Mapping", "LiteralUnlimitedToUnbounded_Mapping", "LiteralUnlimitedUnbounded_Mapping",),
    ("ChangeTriggerExpressionFeatureTyping_Mapping", "TransitionChangeTriggerConstraintUsage_Mapping", "ChangeTriggerConstraintUsage_Mapping",),
    ("TimeTriggerExpressionFeatureTyping_Mapping", "TransitionTimeTriggerCalculationUsage_Mapping", "TimeTriggerCalculationUsage_Mapping",),
    ("AttributeRedefined_Mapping", "PropertyDefaultValue_Mapping", "DefaultValue_Mapping",),
    ("StereotypeOccurenceUsageFeatureTyping_Mapping", "StereotypeOccurenceDefinition_Mapping", "StereotypeMetadataDefinition_Mapping",),
]

previous_alias_rules = pd.DataFrame([
    {
        "caller_suffix": caller,
        "callee": callee,
        "semantic_target_class": mapping_name_by_suffix(mapping_table, target),
        "semantic_alias_rule": f"previously_validated_{target}",
        "semantic_alias_evidence": ("Previously investigated and accepted semantic correspondence."),
        "semantic_alias_confidence": "high",
    }
    for caller, callee, target in previous_alias_specs
])

# Add only historical rules not already represented.
current_keys = set(zip(semantic_alias_rules["caller_suffix"], semantic_alias_rules["callee"],))
previous_alias_rules_filtered = previous_alias_rules.loc[~previous_alias_rules.apply(lambda row: (row["caller_suffix"], row["callee"],) in current_keys, axis=1,)].copy()
semantic_alias_rules = pd.concat([semantic_alias_rules, previous_alias_rules_filtered,], ignore_index=True,)

dependency_edges = apply_semantic_aliases(
    dependency_edges=dependency_edges, 
    semantic_alias_rules=semantic_alias_rules, 
    mapping_table=mapping_table,
    )


# In[ ]:


semantic_resolved = dependency_edges.loc[
    dependency_edges["semantic_target_class"].notna()
].copy()

alias_validation = (
    semantic_resolved.groupby(["caller_suffix", "callee_short", "semantic_target_class", "effective_resolution_status",], dropna=False,)
    .agg(call_count=("call_id", "size"), call_ids=("call_id", list),)
    .reset_index()
)
print(alias_validation.to_string(index=False))


# In[ ]:


# 1. Inspect the caller's OCL specification.
caller_spec = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].str.endswith(
        "::ElementGroup_Mapping"
    )
    & mapping_operation_specifications["operation_name"].eq(
        "ownedRelationship"
    ),
    [
        "mapping_name",
        "operation_name",
        "language",
        "body",
    ],
]

print("CALLER SPECIFICATION")
print(caller_spec.to_string(index=False))
print("CALLER SPECIFICATION")
print(caller_spec.to_string(index=False))


# 2. Inspect the proposed target mapping's source/target crosswalk.
candidate = mapping_table.loc[
    mapping_table["mapping_name"].str.endswith(
        "::ElementImport_Mapping"
    )
]

print("\nCANDIDATE CROSSWALK")
print(candidate.to_string(index=False))


# 3. Inspect its direct and inherited operation declarations.
candidate_name = candidate.iloc[0]["mapping_name"]

candidate_declarations = mapping_operation_declarations.loc[
    mapping_operation_declarations["mapping_name"].eq(candidate_name),
    [
        "mapping_name",
        "declared_by",
        "operation_name",
        "operation_xmi_id",
        "is_direct",
        "redefined_operations",
    ],
].sort_values(
    ["is_direct", "declared_by", "operation_name"],
    ascending=[False, True, True],
)

print("\nCANDIDATE OPERATION DECLARATIONS")
print(candidate_declarations.to_string(index=False))


# 4. Inspect specifications for the candidate's declared operations.
candidate_specs = mapping_operation_specifications.loc[
    mapping_operation_specifications["mapping_name"].eq(candidate_name),
    [
        "declared_by",
        "operation_name",
        "is_direct",
        "language",
        "body",
    ],
]

print("\nCANDIDATE OPERATION SPECIFICATIONS")
print(candidate_specs.to_string(index=False))


# In[ ]:


# Locate Helper.getTagValueAsElementColl
helper_operations = [e for e in registry.get_elements("SysML_v1_to_v2") if e.tag == "ownedOperation" and e.name == "getTagValueAsElementColl"]
for op in helper_operations:
    print(op.qualified_name, op.xmi_id)

# Inspect the ElementGroup stereotype and its member property.
element_group = [e for e in registry.get_elements("SysML_v1") if e.name == "ElementGroup"]

for e in element_group:
    print(e.tag, e.qualified_name, e.xmi_id)

    members = [
        child for child in registry.get_elements("SysML_v1")
        if child.parent == e.key
    ]

    for child in members:
        print(" ", child.tag, child.name, child.xmi_id, child.attributes,)


# In[ ]:


member_op = next(e for e in registry.get_elements("SysML_v1") if e.xmi_id == "SysML.ElementGroup.member_")
print("MEMBER OPERATION")
print(member_op.qualified_name, member_op.xmi_id)
# Find all contained specifications and constraints.
member_descendants = [e for e in registry.get_elements("SysML_v1") if e.parent == member_op.key]
for e in member_descendants:
    print(e.tag, e.name, e.xmi_id, e.attributes,)

helper_op = next(e for e in registry.get_elements("SysML_v1_to_v2") if e.xmi_id == "Mappings-Helper-getTagValueAsElementColl_Element_String_String")
print("HELPER OPERATION")
print(helper_op.qualified_name)
for e in registry.get_elements("SysMLv1_to_v2"):
    if e.parent == helper_op.key:
        print(e.tag, e.name, e.xmi_id, e.attributes)


# In[ ]:


result_param = next(
    e for e in registry.get_elements("SysML_v1")
    if e.xmi_id == "SysML.ElementGroup.member_.result"
)

print("RETURN PARAMETER")
print(result_param.attributes)

print("\nREFERENCES")
for ref in registry.get_references(source=result_param.key):
    print(
        ref.attribute,
        ref.value,
        ref.target,
        ref.resolution_status,
    )


# In[ ]:


helper_matches = [
    e for e in registry.get_elements("SysML_v1_to_v2")
    if e.xmi_id ==
    "Mappings-Helper-getTagValueAsElementColl_Element_String_String"
]

print("HELPER MATCHES:", len(helper_matches))

for helper_op in helper_matches:
    print(helper_op.qualified_name, helper_op.xmi_id)

    print("\nCONTAINED ELEMENTS")
    for e in registry.get_elements("SysML_v1_to_v2"):
        if e.parent == helper_op.key:
            print(e.tag, e.name, e.xmi_id, e.attributes)

    print("\nREFERENCES")
    for ref in registry.get_references(source=helper_op.key):
        print(
            ref.attribute,
            ref.value,
            ref.target,
            ref.resolution_status,
        )


# In[ ]:


member_property = next(
    e for e in registry.get_elements("SysML_v1")
    if e.xmi_id == "SysML.ElementGroup.member"
)

print("MEMBER PROPERTY REFERENCES")
for ref in registry.get_references(source=member_property.key):
    print(
        ref.attribute,
        ref.value,
        ref.target,
        ref.resolution_status,
    )

print("\nMEMBER PROPERTY CONTAINED ELEMENTS")
for e in registry.get_elements("SysML_v1"):
    if e.parent == member_property.key:
        print(e.tag, e.name, e.xmi_id, e.attributes)


print("\nMEMBER OPERATION REFERENCES")
for ref in registry.get_references(source=member_op.key):
    print(
        ref.attribute,
        ref.value,
        ref.target,
        ref.resolution_status,
    )


# In[ ]:


patterns = ["SysML::ModelElements::ElementGroup", "ElementGroup", "getTagValueAsElementColl",]

for pattern in patterns:
    matches = ocl_specifications.loc[
        ocl_specifications["body"].str.contains(pattern, case=False, na=False, regex=False,), ["operation", "language", "body"],]

    print(f"\n--- {pattern}: {len(matches)} matches ---")
    print(matches.to_string(index=False))


# In[ ]:


pin_callers = [
    "ValuePin_Mapping",
    "COAPin_Mapping",
]

for caller in pin_callers:
    print(f"\n{'=' * 80}")
    print(caller)

    specs = mapping_operation_specifications.loc[
        mapping_operation_specifications["mapping_name"].str.endswith(
            f"::{caller}"
        ),
        [
            "mapping_name",
            "operation_name",
            "language",
            "body",
        ],
    ]

    print(specs.to_string(index=False))


# In[ ]:


feature_typing_candidates = mapping_table.loc[
    mapping_table["target_type"].str.endswith("::FeatureTyping"),
    [
        "mapping_name",
        "source_type",
        "target_type",
        "ancestors",
        "operation_count",
        "operations",
    ],
].copy()

print(
    feature_typing_candidates.to_string(index=False)
)


# In[ ]:


inspect_names = [
    "RVAReferenceUsageFeatureTyping_Mapping",
    "REAFeatureValueOperatorExpressionFeatureTyping_Mapping",
    "COAInvocationExpessionFeatureTyping_Mapping",
    "ValuePin_Mapping",
    "COAPin_Mapping",
    "ElementGroup_Mapping",
]

def inspect_mapping_details(mapping_suffix):
    matches = mapping_table.loc[
        mapping_table["mapping_name"].str.endswith(
            f"::{mapping_suffix}"
        )
    ]

    print(f"\n{'=' * 100}")
    print(mapping_suffix)

    if matches.empty:
        print("No mapping_table crosswalk found.")
        return

    for _, row in matches.iterrows():
        mapping_name = row["mapping_name"]

        print("\nCROSSWALK")
        print("Mapping:", mapping_name)
        print("Source:", row["source_type"])
        print("Target:", row["target_type"])
        print("Ancestors:", row["ancestors"])

        # Direct operation declarations and their specifications
        direct = mapping_operation_specifications.loc[
            mapping_operation_specifications["mapping_name"].eq(
                mapping_name
            ),
            [
                "operation_name",
                "language",
                "body",
            ],
        ]

        print("\nDIRECT OPERATION SPECIFICATIONS")
        print(direct.to_string(index=False))

        # Direct and inherited operation declarations
        declarations = mapping_operation_declarations.loc[
            mapping_operation_declarations["mapping_name"].eq(
                mapping_name
            )
        ].copy()

        print("\nRELEVANT INHERITED DECLARATIONS")
        relevant = declarations.loc[
            declarations["operation_name"].isin(
                ["filter", "type", "typedFeature",
                 "ownedRelationship", "source", "target"]
            ),
            [
                "declared_by",
                "operation_name",
                "operation_xmi_id",
                "is_direct",
                "redefined_operations",
            ],
        ]

        print(relevant.to_string(index=False))

        # Inspect the UML operation parameters in the raw registry.
        print("\nOPERATION PARAMETERS")

        for _, declaration in relevant.iterrows():
            op_id = declaration["operation_xmi_id"]

            operations = [
                e for e in registry.get_elements("SysML_v1_to_v2")
                if e.xmi_id == op_id
                and e.tag == "uml:Operation"
            ]

            for op in operations:
                parameters = [
                    e for e in registry.get_elements("SysML_v1_to_v2")
                    if e.parent == op.key
                    and e.tag == "ownedParameter"
                ]

                print(
                    declaration["declared_by"],
                    declaration["operation_name"],
                )

                for parameter in parameters:
                    print("  ", parameter.attributes)


# Pin mappings and candidate relationships
for name in [
    "ValuePin_Mapping",
    "COAPin_Mapping",
    "RVAReferenceUsageFeatureTyping_Mapping",
    "REAFeatureValueOperatorExpressionFeatureTyping_Mapping",
    "COAInvocationExpessionFeatureTyping_Mapping",
]:
    inspect_mapping_details(name)

# ElementGroup mapping
inspect_mapping_details("ElementGroup_Mapping")


# In[ ]:


from urllib.parse import urldefrag, unquote

class ReferenceResolver:
    """ 
    Between the language files, common references are used. This class traverses the self-made references within the file
    to create the comprehensive existing map based on KerML and the SysML1-SysML2 conversion file. 
    """
    def __init__(self, registry):
        self.registry = registry

    def resolve(self, reference):
        source_resource = reference.source[0]
        value = reference.value
        target = None
        resource = None
        fragment = None
        if reference.attribute == "idref":
            resource = source_resource
            fragment = value
        elif reference.attribute == "href":
            uri, fragment = urldefrag(value)
            fragment = unquote(fragment)

            if not fragment:
                return None

            if not uri:
                resource = source_resource
            else:
                resource = self.registry.uri_aliases.get(uri)
        else:
            return None
        if resource is None:
            return None
        key = (resource, fragment)
        target = self.registry.elements.get(key)
        if target is not None:
            reference.target = key
            reference.resolved = True
        return target

    def resolve_all(self):
        for reference in self.registry.references:
            self.resolve(reference)
        total = len(self.registry.references)
        resolved = sum(reference.resolved for reference in self.registry.references)
        return {"total": total, "resolved": resolved, "unresolved": total - resolved, "resolution_rate": (resolved / total if total else 1.0)}


# In[ ]:


RESOURCE_MANIFEST = {
    "UML_Profile": {"path": "processed/uml.xmi", "uri": None, "dependencies": [],},
    "SysML_v1": {"path": "processed/sysml_1.xmi", "uri": None, "dependencies": ["UML_20131001", "UML_PrimitiveTypes_20131001", "UML_StandardProfile_20131001",],},
    "KerML": {"path": "processed/kerml.xmi", "uri": None, "dependencies": ["UML_PrimitiveTypes_20161101",],},
    "SysML_v2": {"path": "processed/sysml_2.xmi", "uri": "https://www.omg.org/spec/SysML/20250201/SysML.xmi", "dependencies": ["KerML", "UML_PrimitiveTypes_20161101",],},
    "SysML_v1_to_v2": {"path": "processed/sysml_v1_to_v2.xmi", "uri": None, "dependencies": ["UML_20161101", "UML_PrimitiveTypes_20161101", "SysML_v2",],},
}

registry.uri_aliases = {
    # UML 2.5.1 / 2016-11-01
    "http://www.omg.org/spec/UML/20161101/UML.xmi": "UML_20161101",
    "https://www.omg.org/spec/UML/20161101/UML.xmi": "UML_20161101",
    "https://www.omg.org/spec/UML/20161101/PrimitiveTypes.xmi": "UML_PrimitiveTypes_20161101",
    # UML 2013-10-01
    "http://www.omg.org/spec/UML/20131001/UML.xmi": "UML_20131001",
    "http://www.omg.org/spec/UML/20131001/PrimitiveTypes.xmi": "UML_PrimitiveTypes_20131001",
    "http://www.omg.org/spec/UML/20131001/StandardProfile.xmi": "UML_StandardProfile_20131001",
    # KerML 2025-02-01
    "https://www.omg.org/spec/KerML/20250201/KerML.xmi": "KerML",
}


# In[ ]:


resolver = ReferenceResolver(registry)
resolution_results = resolver.resolve_all()
print(resolution_results)

def inspect_unresolved_references(registry):
    for resource in registry.resources:
        unresolved = [ref for ref in registry.references if ref.source[0] == resource and not ref.resolved]
        print(f"\n{resource}")
        print("Unresolved:", len(unresolved))
        print("Reference attributes:", Counter(ref.attribute for ref in unresolved))
        print("Reference tags:", Counter(ref.element_tag for ref in unresolved))
        print("Examples:")
        for ref in unresolved[:10]:
            print(f" {ref.source} | " f"{ref.element_tag} | " f"{ref.attribute} | " f"{ref.value}")

inspect_unresolved_references(registry)


# # Current Status:
# 
# ## Completed:
# A. Metamodel registry and XMI extraction
# B. Mapping-class inventory and source/target crosswalk
# C. Inheritance and operation extraction
# D. OCL and English specifications
# E. Mapping dependency extraction
# 
# ## Progressing:
# A. Semantic aliases
# B. Remaining unresolved dependencies
# 
# ## Transformation Approach:
# MetaModel Registry --> Mapping class inventory and translation layer --> Inheritance/Redefinition/Specification/Dependencies --> Unified Representation 
# 
# 

# In[ ]:


audit_inputs = {
    "mapping_class_records": mapping_class_records,
    "mapping_table": mapping_table,
    "mapping_operation_declarations": mapping_operation_declarations,
    "ocl_specifications": ocl_specifications,
    "dependency_edges": dependency_edges,
    "semantic_alias_rules": semantic_alias_rules,
}

for name, obj in audit_inputs.items():
    print(f"\n{'=' * 80}")
    print(f"{name}: {type(obj).__name__}")
    print(f"{'=' * 80}")

    if isinstance(obj, pd.DataFrame):
        print("Shape:", obj.shape)
        print("Columns:", obj.columns.tolist())
        print("\nDtypes:")
        print(obj.dtypes.to_string())
        print("\nSample:")
        print(obj.head(2))

    elif isinstance(obj, list):
        print("Length:", len(obj))

        if obj:
            print("First element type:", type(obj[0]).__name__)
            print("First element:")
            display(obj[0])

    else:
        print("Value:", obj)


# In[ ]:


print("\nRegistry elements:", len(registry.elements))
print("Inheritance edges:", len(inheritance_edges))

print("\nRegistry resources:")
print(
    pd.Series([
        element.key[0]
        for element in registry.elements.values()
    ]).value_counts().to_string()
)


# In[ ]:


import pandas as pd


# 1. Validate operation identity uniqueness
assert mapping_operation_declarations["operation_xmi_id"].notna().all()
assert ocl_specifications["operation_xmi_id"].notna().all()
duplicate_spec_ids = (
    ocl_specifications.loc[ocl_specifications["operation_xmi_id"].duplicated(keep=False), ["operation_xmi_id", "operation", "constraint_id"],]
    .sort_values("operation_xmi_id")
)
print("Duplicate specification operation IDs:", len(duplicate_spec_ids))
if not duplicate_spec_ids.empty:
    display(duplicate_spec_ids)

# 2. Join inherited/direct operation declarations to specs
operation_specification_audit = mapping_operation_declarations.merge(
    ocl_specifications[["operation_xmi_id", "operation_id", "constraint_id", "constraint_name", "expression_id", "language", "body", "specification_category",]],
    on="operation_xmi_id",
    how="left",
    validate="many_to_one",
    indicator=True,
)

operation_specification_audit["has_specification"] = (operation_specification_audit["_merge"].eq("both"))

print("\nOperation specification join:")
print(operation_specification_audit["_merge"].value_counts())

print("Unique declared operations:", mapping_operation_declarations["operation_xmi_id"].nunique(),)
print("Unique operations with specifications:", ocl_specifications["operation_xmi_id"].nunique(),)


# 3. Normalize formal operation redefinitions
redefinition_rows = []
for row in mapping_operation_declarations.itertuples(index=False):
    for ref in row.redefined_operations or []:
        redefinition_rows.append({
            "mapping_name": row.mapping_name,
            "declared_by": row.declared_by,
            "operation": row.operation,
            "operation_xmi_id": row.operation_xmi_id,
            "redefined_operation": ref.get("operation"),
            "redefined_operation_xmi_id": ref.get("operation_xmi_id"),
            "resolution_status": ref.get("resolution_status"),
        })
operation_redefinitions = pd.DataFrame(redefinition_rows)
print("\nFormal operation redefinitions:", len(operation_redefinitions))
if not operation_redefinitions.empty:
    print(operation_redefinitions["resolution_status"] .value_counts(dropna=False))


# 4. Audit semantic alias rule coverage
alias_rule_audit = semantic_alias_rules.copy()
alias_rule_audit["matched_call_count"] = alias_rule_audit.apply(
    lambda rule: (dependency_edges["caller_suffix"].eq(rule["caller_suffix"]) & dependency_edges["callee_short"].eq(rule["callee"])).sum(),
    axis=1,
)

alias_rule_audit["matched_unresolved_count"] = alias_rule_audit.apply(
    lambda rule: (
        dependency_edges["caller_suffix"].eq(rule["caller_suffix"])
        & dependency_edges["callee_short"].eq(rule["callee"])
        & (dependency_edges["target_class"].isna() | dependency_edges["resolution_status"].eq("unresolved"))
    ).sum(),
    axis=1,
)

print("\nSemantic alias rule coverage:")
print(alias_rule_audit[
    ["caller_suffix", "callee", "semantic_target_class", "semantic_alias_confidence", "matched_call_count", "matched_unresolved_count",]
    ].to_string(index=False))

# 5. Current dependency resolution status
print("\nOriginal dependency resolution:")
print(dependency_edges["resolution_status"].value_counts(dropna=False))
print("\nEffective dependency resolution:")
print(dependency_edges["effective_resolution_status"] .value_counts(dropna=False))
print("\nEffective dependency target coverage:")
print("Calls with effective target:", dependency_edges["effective_target_class"].notna().sum(),)



# 6. Identify unresolved calls for candidate discovery
unresolved_dependency_calls = dependency_edges.loc[dependency_edges["effective_resolution_status"].eq("unresolved")].copy()
print("\nUnresolved dependency calls:", len(unresolved_dependency_calls))
if not unresolved_dependency_calls.empty:
    unresolved_summary = (
        unresolved_dependency_calls
        .groupby(["source_class", "callee", "resolution_status"], dropna=False,)
        .agg(call_count=("call_id", "size"), call_ids=("call_id", list), operations=("operation", lambda x: sorted(set(x))),)
        .reset_index()
        .sort_values(["call_count", "source_class"], ascending=[False, True])
    )
    display(unresolved_summary)


# 7. Per-mapping operation coverage
mapping_operation_audit = (
    operation_specification_audit
    .groupby("mapping_name")
    .agg(
        declaration_count=("operation_xmi_id", "size"),
        direct_declaration_count=("is_direct", "sum"),
        inherited_declaration_count=("is_direct", lambda x: (~x).sum(),),
        declarations_with_specs=("has_specification", "sum"),
        unique_operation_count=("operation_xmi_id", "nunique"),
    )
    .reset_index()
)

mapping_operation_audit["declarations_without_specs"] = (mapping_operation_audit["declaration_count"] - mapping_operation_audit["declarations_with_specs"])

print("\nMapping operation audit:")
print("Mappings represented:", len(mapping_operation_audit))
print("Declarations without specifications:", mapping_operation_audit["declarations_without_specs"].sum(),)
display(mapping_operation_audit.sort_values(["declarations_without_specs", "declaration_count"], ascending=[False, False],).head(20))


# In[ ]:


# ============================================================
# STAGE 2: UNRESOLVED DEPENDENCY REVIEW
# ============================================================

# 1. Individual unresolved calls
unresolved_calls = dependency_edges.loc[
    dependency_edges["effective_resolution_status"].eq("unresolved")
].copy()

unresolved_detail = unresolved_calls[
    [
        "call_id",
        "source_class",
        "operation",
        "callee",
        "method",
        "arguments",
        "call_expression",
        "candidate_classes",
        "resolution_status",
        "dependency_type",
    ]
].sort_values(["source_class", "callee", "call_id"])

print("Unresolved call occurrences:", len(unresolved_detail))
display(unresolved_detail)

# 2. Group calls by caller and callee
unresolved_groups = (
    unresolved_calls
    .groupby(
        ["source_class", "callee", "resolution_status"],
        dropna=False,
    )
    .agg(
        call_count=("call_id", "size"),
        call_ids=("call_id", list),
        operations=("operation", lambda x: sorted(set(x))),
        arguments=("arguments", lambda x: list(x)),
        candidate_classes=(
            "candidate_classes",
            lambda x: list(x),
        ),
    )
    .reset_index()
    .sort_values(["callee", "source_class"])
)

print("\nUnresolved caller/callee groups:", len(unresolved_groups))
display(unresolved_groups)

# 3. Alias rules that did not match unresolved calls
unmatched_alias_rules = alias_rule_audit.loc[
    alias_rule_audit["matched_unresolved_count"].eq(0)
].copy()

print("\nAlias rules without an unresolved call match:",
      len(unmatched_alias_rules))

display(
    unmatched_alias_rules[
        [
            "caller_suffix",
            "callee",
            "semantic_target_class",
            "semantic_alias_confidence",
            "matched_call_count",
            "matched_unresolved_count",
        ]
    ]
)

# 4. Check the operation declarations without specifications
missing_specifications = operation_specification_audit.loc[
    ~operation_specification_audit["has_specification"]
].copy()

print("Missing-specification declaration rows:", len(missing_specifications))
print(
    "Unique missing-specification operation IDs:",
    missing_specifications["operation_xmi_id"].nunique()
)

missing_specification_operations = (
    missing_specifications[
        [
            "mapping_name",
            "declared_by",
            "operation",
            "operation_name",
            "operation_xmi_id",
            "is_direct",
        ]
    ]
    .drop_duplicates("operation_xmi_id")
    .sort_values(["declared_by", "operation_name"])
    .drop(columns="operation_name")
)

display(missing_specification_operations)


# In[ ]:


# STAGE 3: EFFECTIVE RESOLUTION AND ALIAS DIAGNOSTIC

# First, inspect the actual columns available.
print("Dependency columns:")
print(unresolved_calls.columns.tolist())

print("\nAlias-rule columns:")
print(semantic_alias_rules.columns.tolist())

# Keep only the fields needed from the alias-rule table and rename them.
alias_rules_for_join = semantic_alias_rules[
    [
        "caller_suffix",
        "callee",
        "semantic_target_class",
        "semantic_alias_rule",
        "semantic_alias_confidence",
    ]
].rename(
    columns={
        "callee": "rule_callee",
        "semantic_target_class": "rule_target_class",
        "semantic_alias_rule": "rule_description",
        "semantic_alias_confidence": "rule_confidence",
    }
)

unresolved_alias_matches = unresolved_calls.merge(
    alias_rules_for_join,
    left_on=["caller_suffix", "callee_short"],
    right_on=["caller_suffix", "rule_callee"],
    how="left",
    indicator=True,
)

print("Alias-rule matches among currently unresolved calls:")
display(
    unresolved_alias_matches[
        [
            "call_id",
            "caller_suffix",
            "callee_short",
            "rule_target_class",
            "rule_description",
            "rule_confidence",
            "_merge",
        ]
    ].sort_values(["callee_short", "caller_suffix"])
)

print("Unresolved calls grouped by callee:")
display(
    unresolved_alias_matches.groupby(
        ["callee_short", "_merge"], dropna=False
    )
    .agg(
        call_count=("call_id", "size"),
        callers=("caller_suffix", lambda x: sorted(set(x))),
        call_ids=("call_id", list),
    )
    .reset_index()
    .sort_values(["callee_short", "_merge"])
)


# In[ ]:


print("unresolved_calls shape:", unresolved_calls.shape)
print("semantic_alias_rules shape:", semantic_alias_rules.shape)
print("unresolved_alias_matches shape:", unresolved_alias_matches.shape)

print("\nUnresolved caller/callee keys:")
print(
    unresolved_calls[["caller_suffix", "callee_short"]]
    .drop_duplicates()
    .to_string(index=False)
)

print("\nAlias-rule caller/callee keys:")
print(
    semantic_alias_rules[["caller_suffix", "callee"]]
    .drop_duplicates()
    .to_string(index=False)
)

print("\nUnresolved calls (first 20):")
print(
    unresolved_calls[
        ["call_id", "caller_suffix", "callee_short",
         "effective_resolution_status"]
    ].to_string(index=False)
)

print("\nMerge indicator counts:")
print(unresolved_alias_matches["_merge"].value_counts(dropna=False))


# In[ ]:


# STAGE 3A: CHECK ALIAS KEY UNIQUENESS AND MATCH QUALITY

# 1. Check whether the alias table has duplicate caller/callee keys.
duplicate_alias_keys = (
    semantic_alias_rules.groupby(
        ["caller_suffix", "callee"],
        observed=True,
        dropna=False,
    )
    .size()
    .reset_index(name="rule_count")
    .query("rule_count > 1")
)

print("Duplicate alias keys:", len(duplicate_alias_keys))
display(duplicate_alias_keys)

# 2. Count unique calls matched, rather than merged rows.
matched_call_ids = unresolved_alias_matches.loc[
    unresolved_alias_matches["_merge"].eq("both"), "call_id"
].unique()

unmatched_call_ids = unresolved_alias_matches.loc[
    unresolved_alias_matches["_merge"].eq("left_only"), "call_id"
].unique()

print("Unique unresolved calls:", unresolved_calls["call_id"].nunique())
print("Unique calls with an alias match:", len(matched_call_ids))
print("Unique calls without an alias match:", len(unmatched_call_ids))

# 3. Show every matching rule alongside the call's current resolution.
matched_alias_detail = unresolved_alias_matches.loc[
    unresolved_alias_matches["_merge"].eq("both"),
    [
        "call_id",
        "caller_suffix",
        "callee_short",
        "rule_target_class",
        "rule_description",
        "rule_confidence",
        "semantic_target_class",
        "effective_target_class",
        "effective_resolution_status",
    ],
].copy()

display(
    matched_alias_detail.sort_values(
        ["callee_short", "caller_suffix", "rule_target_class"]
    )
)

# 4. Compare the rule's proposed target with the call's applied target.
print("Matched calls with no effective target:")
display(
    matched_alias_detail.loc[
        matched_alias_detail["effective_target_class"].isna()
    ]
)


# In[ ]:


# STAGE 3B: AUDIT ALIAS RULE DUPLICATION AND APPLICATION

# 1. Inspect all records associated with duplicated keys.
duplicate_rule_detail = semantic_alias_rules.merge(
    duplicate_alias_keys[["caller_suffix", "callee"]],
    on=["caller_suffix", "callee"],
    how="inner",
)

print("Duplicated alias-rule records:")
display(
    duplicate_rule_detail.sort_values(
        ["caller_suffix", "callee", "semantic_target_class"]
    )
)

# 2. Determine whether the duplicated rows are exact duplicates.
print(
    "Exact duplicate rows:",
    semantic_alias_rules.duplicated().sum()
)

print(
    "Unique caller/callee/target combinations:",
    semantic_alias_rules[
        ["caller_suffix", "callee", "semantic_target_class"]
    ].drop_duplicates().shape[0],
)

# 3. Inspect the alias fields currently stored in dependency_edges.
alias_application_audit = dependency_edges[
    [
        "call_id",
        "caller_suffix",
        "callee_short",
        "semantic_target_class",
        "semantic_alias_rule",
        "semantic_alias_evidence",
        "semantic_alias_confidence",
        "effective_target_class",
        "effective_resolution_status",
    ]
].copy()

print("Dependency alias application counts:")
display(
    alias_application_audit.groupby(
        ["effective_resolution_status", "semantic_alias_confidence"],
        dropna=False,
        observed=True,
    )
    .size()
    .reset_index(name="count")
)

# 4. Compare matching alias rules with dependency records.
alias_rule_lookup = semantic_alias_rules[
    [
        "caller_suffix",
        "callee",
        "semantic_target_class",
        "semantic_alias_rule",
    ]
].drop_duplicates()

alias_application_audit = alias_application_audit.merge(
    alias_rule_lookup,
    left_on=["caller_suffix", "callee_short"],
    right_on=["caller_suffix", "callee"],
    how="left",
    suffixes=("_applied", "_rule"),
)

# Matching rule exists, but no alias was applied.
unapplied_aliases = alias_application_audit.loc[
    alias_application_audit["semantic_target_class_rule"].notna()
    & alias_application_audit["semantic_target_class_applied"].isna()
]

print("Matching rules without an applied alias:")
display(
    unapplied_aliases.sort_values(
        ["caller_suffix", "callee_short"]
    )
)

# Applied alias differs from the rule's target.
target_mismatches = alias_application_audit.loc[
    alias_application_audit["semantic_target_class_rule"].notna()
    & alias_application_audit["semantic_target_class_applied"].notna()
    & (
        alias_application_audit["semantic_target_class_applied"]
        != alias_application_audit["semantic_target_class_rule"]
    )
]

print("Applied aliases with target mismatches:")
display(
    target_mismatches.sort_values(
        ["caller_suffix", "callee_short"]
    )
)


# In[ ]:


import inspect

print("Function signature:")
print(inspect.signature(apply_semantic_aliases))

print("\nFunction implementation:")
print(inspect.getsource(apply_semantic_aliases))


# In[ ]:


# STAGE 3C: CONSOLIDATE AND REAPPLY SEMANTIC ALIASES

# 1. Preserve the currently applied semantic aliases for regression testing.
previously_resolved_aliases = (
    dependency_edges.loc[
        dependency_edges["effective_resolution_status"].eq(
            "resolved_semantic_alias"
        ),
        ["call_id", "effective_target_class"],
    ]
    .copy()
    .set_index("call_id")
    .sort_index()
)

# 2. Verify each caller/callee key has only one semantic target.
target_counts = (
    semantic_alias_rules.groupby(
        ["caller_suffix", "callee"],
        observed=True,
    )["semantic_target_class"]
    .nunique()
)

conflicting_keys = target_counts[target_counts > 1]

if not conflicting_keys.empty:
    raise ValueError(
        "Some caller/callee keys have conflicting semantic targets:\n"
        f"{conflicting_keys}"
    )

# 3. Consolidate repeated rules while preserving all distinct evidence.
def combine_unique_evidence(values):
    unique_values = list(dict.fromkeys(
        str(value) for value in values if pd.notna(value)
    ))
    return " | ".join(unique_values)

semantic_alias_rules_clean = (
    semantic_alias_rules.groupby(
        ["caller_suffix", "callee"],
        as_index=False,
        observed=True,
    )
    .agg(
        semantic_target_class=("semantic_target_class", "first"),
        semantic_alias_rule=("semantic_alias_rule", "first"),
        semantic_alias_evidence=(
            "semantic_alias_evidence",
            combine_unique_evidence,
        ),
        semantic_alias_confidence=("semantic_alias_confidence", "first"),
    )
)

# 4. Verify that consolidation did not combine conflicting metadata.
metadata_counts = (
    semantic_alias_rules.groupby(
        ["caller_suffix", "callee"],
        observed=True,
    )
    .agg(
        target_count=("semantic_target_class", "nunique"),
        rule_count=("semantic_alias_rule", "nunique"),
        confidence_count=("semantic_alias_confidence", "nunique"),
    )
)

if (
    metadata_counts[["target_count", "rule_count", "confidence_count"]]
    .gt(1)
    .any()
    .any()
):
    raise ValueError(
        "Conflicting alias metadata exists. Inspect metadata_counts."
    )

print("Original alias rules:", len(semantic_alias_rules))
print("Consolidated alias rules:", len(semantic_alias_rules_clean))
print("Evidence statements preserved through consolidation.")

# 5. Apply the consolidated rules.
dependency_edges_updated = apply_semantic_aliases(
    dependency_edges,
    semantic_alias_rules_clean,
    mapping_table,
)

# 6. Confirm previously resolved aliases remain unchanged.
updated_previous_aliases = (
    dependency_edges_updated.loc[
        dependency_edges_updated["call_id"].isin(
            previously_resolved_aliases.index
        ),
        ["call_id", "effective_target_class"],
    ]
    .copy()
    .set_index("call_id")
    .sort_index()
)

pd.testing.assert_frame_equal(
    previously_resolved_aliases,
    updated_previous_aliases,
)

print("Previously resolved aliases preserved:",
      len(previously_resolved_aliases))

# 7. Validate final resolution counts.
print("\nEffective resolution counts:")
display(
    dependency_edges_updated["effective_resolution_status"]
    .value_counts(dropna=False)
    .rename_axis("status")
    .reset_index(name="count")
)

print("\nSemantic alias assignments:")
display(
    dependency_edges_updated.loc[
        dependency_edges_updated["semantic_target_class"].notna(),
        [
            "call_id",
            "caller_suffix",
            "callee_short",
            "semantic_target_class",
            "semantic_alias_confidence",
        ],
    ].sort_values(["caller_suffix", "callee_short"])
)

# 8. Inspect the remaining unresolved calls.
remaining_unresolved = dependency_edges_updated.loc[
    dependency_edges_updated["effective_resolution_status"].eq("unresolved")
].copy()

print("\nRemaining unresolved calls:", len(remaining_unresolved))
display(
    remaining_unresolved[
        [
            "call_id",
            "source_class",
            "callee",
            "method",
            "arguments",
            "call_expression",
        ]
    ].sort_values(["callee", "source_class"])
)

# 9. Commit only after all checks have passed.
dependency_edges = dependency_edges_updated
semantic_alias_rules = semantic_alias_rules_clean


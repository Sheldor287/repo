
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from uuid import UUID, uuid5
from faker import Faker

# Fixed namespace makes UUID5 identifiers reproducible across runs.
NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

RELATIONSHIPS = {
    "OwningMembership": ("A membership in which an owning element owns another element."),
    "FeatureMembership": ("A membership that relates an element to a feature."),
    "FeatureTyping": ("A relationship that specifies the type of a feature."),
    "Subsetting": ("A relationship in which one feature is a subset of another."),
    "Redefinition": ("A relationship in which one feature redefines another feature."),
}

# A small automotive vocabulary used to give the generated model some domain structure.
COMPONENT_TYPES = {
    "VehicleDefinition": ["Vehicle", "Automobile", "TransportPlatform",],
    "PowertrainDefinition": ["Powertrain", "PropulsionSystem", "DriveSystem",],
    "EngineDefinition": ["Engine", "ElectricMotor", "HybridMotor",],
    "TransmissionDefinition": ["Transmission", "Gearbox", "DriveUnit",],
    "EnergyStorageDefinition": ["Battery", "FuelTank", "EnergyStorageUnit",],
    "ControlSystemDefinition": ["Controller", "ControlModule", "ElectronicControlUnit",],
    "ChassisDefinition": ["Chassis", "Frame", "SuspensionAssembly",],
    "WheelDefinition": ["Wheel", "TireAssembly", "WheelAssembly",],
}

TYPE_DESCRIPTIONS = {
    "VehicleDefinition": "Defines a vehicle-level system.",
    "PowertrainDefinition": "Defines a system responsible for propulsion.",
    "EngineDefinition": "Defines a component that produces mechanical power.",
    "TransmissionDefinition": "Defines a component that transfers mechanical power.",
    "EnergyStorageDefinition": "Defines a component that stores usable energy.",
    "ControlSystemDefinition": "Defines a component responsible for system control.",
    "ChassisDefinition": "Defines the structural support system.",
    "WheelDefinition": "Defines a component used for vehicle movement.",
}

class TestModelGenerator:
    def __init__(self, n_elements: int = 100, seed: int = 123, output_dir: str | Path = "prod/data/initialization",):
        if n_elements < 1:
            raise ValueError("n_elements must be at least 1.")
        # Validate the number of elements.
        self.n_elements = n_elements
        self.seed = seed
        self.output_dir = Path(output_dir)
        # Initialize random number generators for reproducibility.
        self.rng = random.Random(seed)
        self.fake = Faker()
        self.fake.seed_instance(seed)
        # Initialize model data structures.
        self.elements: list[dict] = []
        self.semantics: list[dict] = []
        self.relationships: list[dict] = []
        # Initialize identifier tracking structures.
        self.element_ids: set[str] = set()
        self.semantic_triples: set[tuple] = set()
        # Initialize relationship identifier tracking.
        self.relationship_ids: dict[str, str] = {}

    # Identifier helpers
    @staticmethod
    def make_uuid(value: str) -> str:
        return str(uuid5(NAMESPACE, value))

    def element_uuid(self, name: str) -> str:
        return self.make_uuid(f"element:{name}")

    def relationship_uuid(self, name: str) -> str:
        return self.make_uuid(f"relationship:{name}")

    def semantic_uuid(self, source_id: str, relationship_id: str, target_id: str,) -> str:
        value = f"semantic:{source_id}:{relationship_id}:{target_id}"
        return self.make_uuid(value)

    # Element generation
    def add_element(self, name: str, definition: str,) -> str:
        element_id = self.element_uuid(name)
        if element_id in self.element_ids:
            return element_id
        self.element_ids.add(element_id)
        self.elements.append({"element_uuid": element_id, "name": name, "definition": definition,})
        return element_id

    def generate_type_elements(self) -> dict[str, str]:
        """Create the reusable type-definition elements."""
        type_ids = {}
        for type_name, description in TYPE_DESCRIPTIONS.items():
            type_ids[type_name] = self.add_element(name=type_name, definition=description,)
        return type_ids

    def generate_component_name(self, type_name: str, index: int,) -> str:
        """Generate a domain-specific component name."""
        options = COMPONENT_TYPES[type_name]
        base_name = self.rng.choice(options)
        # Include an index when a name has already been used.
        candidate = base_name
        if candidate in {element["name"] for element in self.elements}:
            candidate = f"{base_name}_{index}"
        return candidate

    def generate_component_definition(self, name: str, type_name: str,) -> str:
        """Generate a plausible component definition."""
        descriptions = {
            "VehicleDefinition": (f"{name} provides the overall vehicle platform. "),
            "PowertrainDefinition": (f"{name} provides mechanical power for vehicle movement. "),
            "EngineDefinition": (f"{name} converts stored energy into mechanical power. "),
            "TransmissionDefinition": (f"{name} transfers power to the drivetrain. "),
            "EnergyStorageDefinition": (f"{name} stores energy for vehicle operation. "),
            "ControlSystemDefinition": (f"{name} monitors and controls vehicle functions. "),
            "ChassisDefinition": (f"{name} provides structural support for vehicle components. "),
            "WheelDefinition": (f"{name} supports vehicle movement and road contact. "),}
        base = descriptions[type_name]
        additional = self.fake.sentence(nb_words=10, variable_nb_words=True,)
        return base + additional

    def generate_components(self, type_ids: dict[str, str],) -> list[dict]:
        """Generate component elements and their type assignments."""
        components = []
        type_names = list(COMPONENT_TYPES.keys())
        # The first element is always the vehicle root.
        for i in range(self.n_elements):
            if i == 0:
                type_name = "VehicleDefinition"
                name = "Vehicle"
            else:
                type_name = self.rng.choice(type_names[1:])
                name = self.generate_component_name(type_name, i)
            definition = self.generate_component_definition(name, type_name,)
            element_id = self.add_element(name, definition)
            component = {"element_uuid": element_id, "name": name, "type_name": type_name,}
            components.append(component)
            # Each component is typed by a type-definition element.
            self.add_semantic(source_id=element_id, relationship_name="FeatureTyping", target_id=type_ids[type_name],)
        return components

    # Relationship catalog
    def generate_relationship_catalog(self) -> None:
        """Generate the reusable relationship-type catalog."""
        for name, definition in RELATIONSHIPS.items():
            relationship_id = self.relationship_uuid(name)
            self.relationship_ids[name] = relationship_id
            self.relationships.append({
                "relationship_uuid": relationship_id,
                "name": name,
                "definition": definition,
            })

    # Semantic generation
    def add_semantic(self, source_id: str, relationship_name: str, target_id: str,) -> None:
        relationship_id = self.relationship_ids[relationship_name]
        triple = (source_id, relationship_id, target_id,)
        if triple in self.semantic_triples:
            return
        self.semantic_triples.add(triple)
        self.semantics.append({
            "semantic_uuid": self.semantic_uuid(*triple),
            "source_element_uuid": source_id,
            "relationship_uuid": relationship_id,
            "target_element_uuid": target_id,
        })

    def generate_ownership_relationships(self, components: list[dict],) -> None:
        """
        Construct a hierarchical ownership graph.
        Select a previously generated component as the parent.
        This guarantees that every component is reachable
        from the root through ownership relationships.
        """
        if len(components) < 2:
            return
        root_id = components[0]["element_uuid"]
        for i in range(1, len(components)):
            parent = self.rng.choice(components[:i])
            self.add_semantic(
                source_id=parent["element_uuid"],
                relationship_name="OwningMembership",
                target_id=components[i]["element_uuid"],
            )

    # Validation
    def validate(self) -> None:
        element_ids = {row["element_uuid"] for row in self.elements}
        relationship_ids = {row["relationship_uuid"] for row in self.relationships}
        for semantic in self.semantics:
            assert semantic["source_element_uuid"] in element_ids
            assert semantic["target_element_uuid"] in element_ids
            assert semantic["relationship_uuid"] in relationship_ids
        assert len(element_ids) == len(self.elements)
        assert len(relationship_ids) == len(self.relationships)
        assert len(self.semantic_triples) == len(self.semantics)

    # CSV export
    def write_csv(self, filename: str, rows: list[dict], columns: list[str],) -> None:
        filepath = self.output_dir / filename
        with filepath.open("w", newline="", encoding="utf-8",) as file:
            writer = csv.DictWriter(file, fieldnames=columns,)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Created: {filepath} ({len(rows)} records)")

    def export(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True,)
        self.write_csv(
            "relationships.csv",
            self.relationships,
            ["relationship_uuid", "name", "definition",],
        )
        self.write_csv(
            "elements.csv",
            self.elements,
            ["element_uuid", "name", "definition",],
        )
        self.write_csv(
            "semantic_relationships.csv",
            self.semantics,
            ["semantic_uuid", "source_element_uuid", "relationship_uuid", "target_element_uuid",],
        )

    # Main execution
    def generate(self) -> None:
        print("Generating test model...")
        self.generate_relationship_catalog()
        type_ids = self.generate_type_elements()
        components = self.generate_components(type_ids)
        self.generate_ownership_relationships(components)
        self.validate()
        self.export()
        print("\nGeneration complete.")
        print(f"Component elements: {self.n_elements}")
        print(f"Total elements: {len(self.elements)}")
        print(f"Relationship types: {len(self.relationships)}")
        print(f"Semantic assertions: {len(self.semantics)}")

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic MBSE graph CSV files.")
    parser.add_argument("--n-elements", type=int, default=100, help="Number of generated component elements.",)
    parser.add_argument("--seed", type=int, default=123, help="Random seed for reproducible generation.",)
    parser.add_argument("--output-dir", type=str, default="prod/tests/test_data", help="Directory for generated CSV files.",)
    args = parser.parse_args()
    generator = TestModelGenerator(n_elements=args.n_elements, seed=args.seed, output_dir=args.output_dir,)
    generator.generate()

if __name__ == "__main__":
    main()

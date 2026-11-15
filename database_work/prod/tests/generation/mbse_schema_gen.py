from __future__ import annotations
import os, sys
from pathlib import Path
import random
from uuid import uuid4
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema
from database_work.prod.app.models.database import MBSE
from database_work.prod.app.models.enum_objects import GovernanceStatus, RecordType
from database_work.prod.app.models.mbse.engineering_model import EngineeringModel
from database_work.prod.app.models.mbse.model_version import ModelVersion
from database_work.prod.app.models.mbse.object_definition import ObjectDefinition
from database_work.prod.app.models.mbse.relationship_definition import RelationshipDefinition
from database_work.prod.app.models.mbse.instance_definition import InstanceDefinition
from database_work.prod.app.models.mbse.object_relationship import ObjectRelationship
from database_work.prod.app.models.mbse.relationship_endpoint import RelationshipEndpoint
from database_work.prod.app.models.mbse.object_instance_property import ObjectInstanceProperty
from database_work.prod.app.models.mbse.relationship_instance_property import RelationshipInstanceProperty
from database_work.prod.app.models.mbse.stereotype import Stereotype
from database_work.prod.app.models.mbse.applied_stereotype import AppliedStereotype
from database_work.prod.app.models.mbse.class_taxonomy import ClassTaxonomy
"""
Generate synthetic records for the MBSE SQLAlchemy models in PostgreSQL.

Run from the backend directory (the directory containing app/):
    python scripts/generate_mbse_data.py

Connection:
    PowerShell:
        $env:DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/dbname"

The script creates tables in mbse_test if they do not already exist. It does not
drop existing tables or records. Each run creates a uniquely named engineering
model so it can be run repeatedly.
"""
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_SCHEMA = "mbse_test"
SEED = 123
INSTANCES_PER_VERSION = 5

# Unique name prevents collisions when the script is run more than once.
RUN_TAG = uuid4().hex[:8]
MODEL_NAME = f"Synthetic MBSE Model {RUN_TAG}"


def make_engine():
    database_url = os.environ.get("PG_CONN")
    if not database_url:
        raise RuntimeError("Set DATABASE_URL before running this script.")

    engine = create_engine(database_url, pool_pre_ping=True, echo=False,)

    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise RuntimeError(f"Expected PostgreSQL; got {engine.dialect.name!r}.")

    return engine


def create_test_schema(engine):
    """Create the destination schema and all registered MBSE tables."""
    translated_engine = engine.execution_options(
        schema_translate_map={"mbse": TARGET_SCHEMA}
    )

    with engine.begin() as connection:
        connection.execute(CreateSchema(TARGET_SCHEMA, if_not_exists=True))

    MBSE.metadata.create_all(translated_engine)
    return translated_engine


def add_endpoint(session, relationship, instance, role, ordinal=1):
    session.add(
        RelationshipEndpoint(
            relationship=relationship,
            instance=instance,
            endpoint_role=role,
            ordinal=ordinal,
            multiplicity_lower=1,
            multiplicity_upper="1",
            role_name=role.title(),
        )
    )


def generate_data(session, seed=SEED):
    rng = random.Random(seed)

    # 1. Engineering model and three linked versions.
    model = EngineeringModel(
        name=MODEL_NAME,
        description=(
            "Synthetic engineering model generated for MBSE schema "
            "and append-only history testing."
        ),
        source_tool="SyntheticDataGenerator",
        source_format="SQLAlchemy ORM",
        classification="TEST",
        record_type=RecordType.INSERT,
    )
    session.add(model)
    session.flush()

    versions = []
    parent = None

    for index in range(1, 4):
        version = ModelVersion(
            model=model,
            version_label=f"V{index}",
            parent_version=parent,
            source_filename=f"synthetic_model_v{index}.xmi",
            source_hash=f"synthetic-sha256-v{index}-{seed}",
            classification="TEST",
            record_type=RecordType.INSERT,
        )
        session.add(version)
        session.flush()
        versions.append(version)
        parent = version

    # 2. Object definitions.
    object_specs = [
        ("System", "An engineered system.", "Block"),
        ("Subsystem", "A functional subsystem.", "Block"),
        ("Component", "A physical or logical component.", "Block"),
        ("Sensor", "A sensing component.", "Part"),
        ("Controller", "A control component.", "Part"),
    ]

    object_definitions = {}
    for name, definition, metaclass in object_specs:
        obj = ObjectDefinition(
            object=name,
            definition=definition,
            metaclass=metaclass,
            classification="TEST",
            record_type=RecordType.INSERT,
        )
        session.add(obj)
        object_definitions[name] = obj

    # 3. Relationship definitions.
    relationship_specs = [
        ("connectsTo", "Connects one model element to another.", True),
        ("dependsOn", "Indicates a dependency.", True),
        ("satisfies", "Indicates requirement satisfaction.", True),
    ]

    relationship_definitions = {}
    for name, definition, directional in relationship_specs:
        rel_def = RelationshipDefinition(
            relationship=name,
            definition=definition,
            is_directional=directional,
            classification="TEST",
            record_type=RecordType.INSERT,
            governance_status=GovernanceStatus.DRAFT,
        )
        session.add(rel_def)
        relationship_definitions[name] = rel_def

    # 4. Stereotype definitions.
    stereotype_specs = [
        ("critical", "Identifies a critical model element.", "TestProfile", "Block"),
        ("verified", "Identifies a verified model element.", "TestProfile", "Block"),
        ("external", "Identifies an externally supplied element.", "TestProfile", "Block"),
    ]

    stereotypes = {}
    for name, definition, profile, metaclass in stereotype_specs:
        stereotype = Stereotype(
            stereotype=name,
            definition=definition,
            profile_name=profile,
            base_metaclass=metaclass,
            classification="TEST",
            record_type=RecordType.INSERT,
        )
        session.add(stereotype)
        stereotypes[name] = stereotype

    session.flush()

    # 5. Taxonomy. Each pair is distinct and no self-reference is created.
    taxonomy_pairs = [
        ("System", "Subsystem"),
        ("Subsystem", "Component"),
        ("Component", "Sensor"),
        ("Component", "Controller"),
    ]
    for parent_name, child_name in taxonomy_pairs:
        session.add(
            ClassTaxonomy(
                class_definition=object_definitions[parent_name],
                subclass=object_definitions[child_name],
                classification="TEST",
                record_type=RecordType.INSERT,
            )
        )

    # 6. Instances: each version gets its own set of instances.
    instances_by_version = {}

    instance_types = ["System", "Subsystem", "Component", "Sensor", "Controller"]

    for version_index, version in enumerate(versions, start=1):
        version_instances = []

        for instance_index in range(INSTANCES_PER_VERSION):
            object_type = instance_types[instance_index % len(instance_types)]
            source_identifier = f"V{version_index}-OBJ-{instance_index + 1:03d}"

            instance = InstanceDefinition(
                model_version=version,
                object_definition=object_definitions[object_type],
                object=object_type,
                definition=(
                    f"{object_type} instance {instance_index + 1} "
                    f"in model version V{version_index}."
                ),
                source_identifier=source_identifier,
                source_path=(
                    f"/Model/V{version_index}/{object_type}/"
                    f"{instance_index + 1}"
                ),
                source_payload={
                    "generated": True,
                    "seed": seed,
                    "version": version_index,
                    "instance_index": instance_index,
                },
                is_deleted=False,
                classification="TEST",
                record_type=RecordType.INSERT,
            )
            session.add(instance)
            version_instances.append(instance)

        instances_by_version[version_index] = version_instances

    session.flush()

    # 7. Instance properties and instance-targeted stereotypes.
    for version_index, instances in instances_by_version.items():
        for instance_index, instance in enumerate(instances):
            session.add_all(
                [
                    ObjectInstanceProperty(
                        instance=instance,
                        property_name="serialNumber",
                        property_value=f"SN-{version_index}-{instance_index + 1:03d}",
                        value_type="string",
                        classification="TEST",
                        record_type=RecordType.INSERT,
                    ),
                    ObjectInstanceProperty(
                        instance=instance,
                        property_name="availability",
                        property_value=str(round(rng.uniform(0.90, 0.999), 4)),
                        value_type="float",
                        value_json={
                            "value": round(rng.uniform(0.90, 0.999), 4),
                            "unit": "probability",
                        },
                        classification="TEST",
                        record_type=RecordType.INSERT,
                    ),
                ]
            )

            if instance_index % 2 == 0:
                session.add(
                    AppliedStereotype(
                        stereotype=stereotypes["critical"],
                        target_type="instance",
                        instance=instance,
                        source_identifier=f"ST-INSTANCE-{version_index}-{instance_index}",
                        tagged_values={"priority": "high", "generated": True},
                        classification="TEST",
                        record_type=RecordType.INSERT,
                    )
                )

    # 8. Within-version relationships.
    relationships = []

    for version_index, version in enumerate(versions, start=1):
        instances = instances_by_version[version_index]

        # Create two relationships per version.
        for relationship_index, (source, target) in enumerate(
            [(instances[0], instances[1]), (instances[2], instances[3])],
            start=1,
        ):
            relationship = ObjectRelationship(
                model_version=version,
                relationship_definition=relationship_definitions[
                    "connectsTo" if relationship_index == 1 else "dependsOn"
                ],
                source_instance=source,
                target_instance=target,
                source_identifier=f"V{version_index}-REL-{relationship_index:03d}",
                relationship_name=f"{source.object}_to_{target.object}",
                definition="Synthetic binary relationship.",
                source_payload={
                    "generated": True,
                    "version": version_index,
                    "relationship_index": relationship_index,
                },
                is_deleted=False,
                classification="TEST",
                record_type=RecordType.INSERT,
            )
            session.add(relationship)
            relationships.append(relationship)

    session.flush()

    # 9. Cross-version relationship:
    #    owned by V3, source instance from V1, target instance from V2.
    cross_version_relationship = ObjectRelationship(
        model_version=versions[2],
        relationship_definition=relationship_definitions["satisfies"],
        source_instance=instances_by_version[1][3],
        target_instance=instances_by_version[2][4],
        source_identifier="V3-CROSS-001",
        relationship_name="V1_Sensor_satisfies_V2_Controller",
        definition=(
            "Cross-version relationship: owned by V3, connecting "
            "an instance in V1 to an instance in V2."
        ),
        source_payload={
            "generated": True,
            "cross_version": True,
            "owner_version": "V3",
            "source_version": "V1",
            "target_version": "V2",
        },
        is_deleted=False,
        classification="TEST",
        record_type=RecordType.INSERT,
    )
    session.add(cross_version_relationship)
    relationships.append(cross_version_relationship)
    session.flush()

    # 10. Explicit endpoint records for every relationship.
    for relationship in relationships:
        add_endpoint(
            session,
            relationship,
            relationship.source_instance,
            "source",
        )
        add_endpoint(
            session,
            relationship,
            relationship.target_instance,
            "target",
        )

    # 11. Relationship properties and relationship-targeted stereotypes.
    for index, relationship in enumerate(relationships, start=1):
        session.add(
            RelationshipInstanceProperty(
                relationship=relationship,
                property_name="confidence",
                property_value=str(round(rng.uniform(0.70, 1.00), 3)),
                value_type="float",
                value_json={"scale": "0-1", "generated": True},
                classification="TEST",
                record_type=RecordType.INSERT,
            )
        )

        if index % 2 == 0:
            session.add(
                AppliedStereotype(
                    stereotype=stereotypes["verified"],
                    target_type="relationship",
                    relationship=relationship,
                    source_identifier=f"ST-RELATIONSHIP-{index:03d}",
                    tagged_values={"verificationMethod": "synthetic"},
                    classification="TEST",
                    record_type=RecordType.INSERT,
                )
            )

    session.flush()

    return {
        "model": model,
        "versions": versions,
        "instances_by_version": instances_by_version,
        "relationships": relationships,
        "cross_version_relationship": cross_version_relationship,
    }


def validate_data(session, generated):
    """Basic integrity and scenario checks within the current transaction."""
    model = generated["model"]
    versions = generated["versions"]
    cross = generated["cross_version_relationship"]

    assert len(versions) == 3
    assert versions[0].parent_version is None
    assert versions[1].parent_version is versions[0]
    assert versions[2].parent_version is versions[1]

    assert cross.model_version is versions[2]
    assert cross.source_instance.model_version is versions[0]
    assert cross.target_instance.model_version is versions[1]

    expected_tables = [
        EngineeringModel,
        ModelVersion,
        ObjectDefinition,
        RelationshipDefinition,
        InstanceDefinition,
        ClassTaxonomy,
        ObjectRelationship,
        RelationshipEndpoint,
        Stereotype,
        AppliedStereotype,
        ObjectInstanceProperty,
        RelationshipInstanceProperty,
    ]

    counts = {}
    for model_class in expected_tables:
        counts[model_class.__tablename__] = session.scalar(
            select(func.count()).select_from(model_class)
        )

    # Confirm the generated model itself has three versions.
    model_version_count = session.scalar(
        select(func.count())
        .select_from(ModelVersion)
        .where(ModelVersion.model_uuid == model.uuid)
    )
    assert model_version_count == 3

    print("\nValidation passed.")
    print(f"Engineering model: {model.name}")
    print(f"Cross-version relationship: {cross.relationship_name}")
    print(
        "  owner version:",
        cross.model_version.version_label,
    )
    print(
        "  source version:",
        cross.source_instance.model_version.version_label,
    )
    print(
        "  target version:",
        cross.target_instance.model_version.version_label,
    )

    print("\nTable counts in the target schema (including any earlier runs):")
    for table_name, count in sorted(counts.items()):
        print(f"  {table_name:38s} {count:>6d}")


def main():
    engine = make_engine()
    translated_engine = create_test_schema(engine)

    try:
        # The whole dataset is one transaction. Any exception rolls it back.
        with Session(translated_engine) as session:
            with session.begin():
                generated = generate_data(session)
                validate_data(session, generated)

        print(f"\nCommitted synthetic data to schema: {TARGET_SCHEMA}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

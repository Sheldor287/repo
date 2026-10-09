
from uuid import UUID
import pytest
from pipeline import RDF_Model, SQL_Model


@pytest.fixture
def triples():
    return [("Engine", "connectedTo", "Pump"), ("Pump", "connectedTo", "Valve"), ("Engine", "hasType", "Diesel"),]

@pytest.fixture
def rdf_model(triples):
    return RDF_Model(triples)

@pytest.fixture
def sql_model(triples):
    return SQL_Model(triples)



# Input validation
@pytest.mark.parametrize(
    "invalid_triples",
    [
        [],
        [("Engine", "connectedTo")],
        [("Engine", "connectedTo", "Pump", "extra")],
        [("Engine", "", "Pump")],
        [("Engine", "connectedTo", None)],
        ["not a triple"],
        [(1, "connectedTo", "Pump")],
        [( "Engine", "connectedTo", "   ")],
    ],
)
def test_validate_relationships_rejects_invalid_input(invalid_triples):
    model = SQL_Model(invalid_triples)

    with pytest.raises(ValueError):
        model.validate_relationships()

def test_validate_relationships_accepts_valid_triples(sql_model):
    sql_model.validate_relationships()



# Table-name generation
@pytest.mark.parametrize(
    ("predicate", "expected"),
    [
        ("connectedTo", "connectedto"),
        ("has type", "has_type"),
        ("http://example.org/connectedTo", "http_example_org_connectedto"),
        ("123relation", "rel_123relation"),
    ],
)
def test_to_table_name(predicate, expected):
    model = RDF_Model([])

    assert model.to_table_name(predicate) == expected


def test_to_table_name_rejects_empty_or_invalid_name():
    model = RDF_Model([])

    with pytest.raises(ValueError):
        model.to_table_name("///")


def test_model_rejects_predicate_table_name_collisions():
    model = RDF_Model([
        ("A", "has-type", "B"),
        ("A", "has type", "C"),
    ])

    with pytest.raises(ValueError, match="map to the same table"):
        model.build_rdf_relational_model()



# Relational model construction
def test_model_contains_unique_objects_predicates_and_relationships(rdf_model):
    result = rdf_model.build_rdf_relational_model()

    assert {r["object"] for r in result["objects"]} == {"Engine", "Pump", "Valve", "Diesel"}

    assert {r["predicate"] for r in result["predicates"]} == {"connectedTo", "hasType"}

    assert set(result["relationships"]) == {"connectedTo", "hasType"}


def test_object_and_predicate_records_have_valid_uuids(rdf_model):
    result = rdf_model.build_rdf_relational_model()

    for record in result["objects"]:
        UUID(str(record["object_uuid"]))

    for record in result["predicates"]:
        UUID(str(record["predicate_uuid"]))


def test_predicate_table_name_is_only_in_model(rdf_model):
    result = rdf_model.build_rdf_relational_model()

    for record in result["predicates"]:
        assert record["table_name"] == rdf_model.to_table_name(record["predicate"])


def test_definitions_are_attached_to_records():
    model = RDF_Model(
        triples=[("Engine", "connectedTo", "Pump")],
        object_definitions={"Engine": "Power source"},
        predicate_definitions={"connectedTo": "Physical connection"},
    )

    result = model.build_rdf_relational_model()
    objects = {r["object"]: r for r in result["objects"]}
    predicates = {r["predicate"]: r for r in result["predicates"]}

    assert objects["Engine"]["definition"] == "Power source"
    assert predicates["connectedTo"]["definition"] == "Physical connection"


# -------------------------------------------------------------------
# Persistent UUID reuse
# -------------------------------------------------------------------

def test_existing_object_uuids_are_reused(rdf_model):
    existing = {"Engine": "11111111-1111-4111-8111-111111111111", "Pump": "22222222-2222-4222-8222-222222222222",}
    result = rdf_model.build_rdf_relational_model(existing_object_uuids=existing)
    objects = {r["object"]: r for r in result["objects"]}

    assert objects["Engine"]["object_uuid"] == existing["Engine"]
    assert objects["Pump"]["object_uuid"] == existing["Pump"]


def test_existing_predicate_uuids_are_reused(rdf_model):
    existing = {"connectedTo": "33333333-3333-4333-8333-333333333333",}
    result = rdf_model.build_rdf_relational_model(existing_predicate_uuids=existing)
    predicates = {r["predicate"]: r for r in result["predicates"]}

    assert predicates["connectedTo"]["predicate_uuid"] == existing["connectedTo"]


def test_existing_semantic_uuid_is_reused(rdf_model):
    triple = ("Engine", "connectedTo", "Pump")
    existing_uuid = "44444444-4444-4444-8444-444444444444"
    result = rdf_model.build_rdf_relational_model(existing_semantic_uuids={triple: existing_uuid})
    rows = result["relationships"]["connectedTo"]
    matching = [r for r in rows if (r["subject"], r["predicate"], r["object"]) == triple]

    assert len(matching) == 1
    assert matching[0]["semantic_uuid"] == existing_uuid


def test_duplicate_triples_reuse_same_semantic_uuid():
    model = RDF_Model([("Engine", "connectedTo", "Pump"), ("Engine", "connectedTo", "Pump"),])
    result = model.build_rdf_relational_model()
    rows = result["relationships"]["connectedTo"]

    assert rows[0]["semantic_uuid"] == rows[1]["semantic_uuid"]
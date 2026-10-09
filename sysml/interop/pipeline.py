from collections import defaultdict
import psycopg
from psycopg import sql
from uuid import uuid4
import re
import os 

class RDF_Model:
    def __init__(self,triples:list, object_definitions:dict=None, predicate_definitions:dict=None):
        self.triples = triples
        self.object_definitions = object_definitions or {}
        self.predicate_definitions = predicate_definitions or {}

    @staticmethod
    def make_uuid():
        return str(uuid4())

    def to_table_name(self, predicate: str):
        name = re.sub(r'[^a-zA-Z0-9_]+', '_', predicate).strip('_').lower()
        if not name:
            raise ValueError(f"Invalid table name for predicate: {predicate}")
        if name[0].isdigit():
            name = f"rel_{name}"
        return name

    def load_existing_uuids(self, conn):
        with conn.cursor() as cur:
            cur.execute("SELECT object, object_uuid FROM objects")
            object_uuids = dict(cur.fetchall())

            cur.execute("SELECT predicate, predicate_uuid FROM predicates")
            predicate_uuids = dict(cur.fetchall())

            cur.execute("""
                SELECT subject, predicate, object, semantic_uuid
                FROM semantics
            """)
            semantic_uuids = {
                (subject, predicate, obj): semantic_uuid for subject, predicate, obj, semantic_uuid in cur.fetchall()
                }
        return object_uuids, predicate_uuids, semantic_uuids

    def build_rdf_relational_model(self, existing_object_uuids=None, existing_predicate_uuids=None, existing_semantic_uuids=None,):
        existing_object_uuids = existing_object_uuids or {}
        existing_predicate_uuids = existing_predicate_uuids or {}
        existing_semantic_uuids = existing_semantic_uuids or {}

        objects = {}
        predicates = {}
        relationships = defaultdict(list)
        table_names = {}

        for subject, predicate, obj in self.triples:
            for term in (subject, obj):
                if term not in objects:
                    objects[term] = {
                        "object": term,
                        "definition": self.object_definitions.get(term),
                        "object_uuid": (existing_object_uuids[term] if term in existing_object_uuids else self.make_uuid()),
                    }

            if predicate not in predicates:
                table_name = self.to_table_name(predicate)

                # Different predicates must not map to the same SQL table.
                if table_name in table_names and table_names[table_name] != predicate:
                    raise ValueError(f"Predicates {table_names[table_name]!r} and " f"{predicate!r} map to the same table {table_name!r}.")

                table_names[table_name] = predicate

                predicates[predicate] = {
                    "predicate": predicate,
                    "definition": self.predicate_definitions.get(predicate),
                    "predicate_uuid": (existing_predicate_uuids[predicate] if predicate in existing_predicate_uuids else self.make_uuid()),
                    "table_name": table_name,
                }

        semantic_uuids = {}

        for subject, predicate, obj in self.triples:
            triple_key = (subject, predicate, obj)

            if triple_key not in semantic_uuids:
                semantic_uuids[triple_key] = existing_semantic_uuids.get(triple_key) or self.make_uuid()

            relationships[predicate].append({
                "subject": objects[subject]["object"],
                "predicate": predicates[predicate]["predicate"],
                "object": objects[obj]["object"],
                "semantic_uuid": semantic_uuids[triple_key],
            })

        self.model = {
            "objects": list(objects.values()),
            "predicates": list(predicates.values()),
            "relationships": dict(relationships),
        }

        return self.model


class SQL_Model(RDF_Model):
    def __init__(self, triples: list, object_definitions: dict = None, predicate_definitions: dict = None,):
        super().__init__(triples, object_definitions, predicate_definitions)
        self.model = None

    def validate_relationships(self):
        if not self.triples:
            raise ValueError("At least one RDF triple is required.")

        for i, triple in enumerate(self.triples):
            if not isinstance(triple, (tuple, list)) or len(triple) != 3:
                raise ValueError(f"Triple at index {i} must contain (subject, predicate, object).")

            subject, predicate, obj = triple
            if not all(isinstance(term, str) and term.strip()
                       for term in (subject, predicate, obj)):
                raise ValueError(f"Triple at index {i} must contain three non-empty strings.")


    def generate_sql_schema(self):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS objects (
                object TEXT NOT NULL UNIQUE,
                definition TEXT,
                definition_conflict BOOLEAN NOT NULL DEFAULT FALSE,
                proposed_definition TEXT,
                governance_status TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK (governance_status IN ('DRAFT', 'ACCEPTED')),
                object_uuid UUID PRIMARY KEY
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS predicates (
                predicate TEXT NOT NULL UNIQUE,
                definition TEXT,
                definition_conflict BOOLEAN NOT NULL DEFAULT FALSE,
                proposed_definition TEXT,
                governance_status TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK (governance_status IN ('DRAFT', 'ACCEPTED')),
                predicate_uuid UUID PRIMARY KEY
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS semantics (
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                governance_status TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK (governance_status IN ('DRAFT', 'ACCEPTED')),
                semantic_uuid UUID PRIMARY KEY,
                UNIQUE (subject, predicate, object)
            )
            """,
        ]

        self.validate_relationships()

        if self.model is None:
            raise ValueError("Build the relational model before generating the schema.")

        for predicate in self.model["predicates"]:
            table_name = predicate["table_name"]

            statements.append(
                sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {} (
                        subject TEXT NOT NULL,
                        object TEXT NOT NULL,
                        semantic_uuid UUID NOT NULL UNIQUE
                            REFERENCES semantics(semantic_uuid),
                        PRIMARY KEY (subject, object)
                    )
                """).format(sql.Identifier(table_name))
            )

        return statements

    def load_sql_schema(self, conninfo: str = None):
        conninfo = conninfo or os.getenv("PG_CONN")
        if not conninfo:
            raise ValueError("Provide conninfo or set the PG_CONN environment variable.")

        self.validate_relationships()

        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                # Create prerequisite registry tables first.
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS objects (
                        object TEXT NOT NULL UNIQUE,
                        definition TEXT,
                        definition_conflict BOOLEAN NOT NULL DEFAULT FALSE,
                        proposed_definition TEXT,
                        governance_status TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK (governance_status IN ('DRAFT', 'ACCEPTED')),
                        object_uuid UUID PRIMARY KEY
                        )
                    """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS predicates (
                        predicate TEXT NOT NULL UNIQUE,
                        definition TEXT,
                        definition_conflict BOOLEAN NOT NULL DEFAULT FALSE,
                        proposed_definition TEXT,
                        governance_status TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK (governance_status IN ('DRAFT', 'ACCEPTED')),
                        predicate_uuid UUID PRIMARY KEY
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS semantics (
                        subject TEXT NOT NULL,
                        predicate TEXT NOT NULL,
                        object TEXT NOT NULL,
                        governance_status TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK (governance_status IN ('DRAFT', 'ACCEPTED')),
                        semantic_uuid UUID PRIMARY KEY,
                        UNIQUE (subject, predicate, object)
                        )
                    """)

            # Resolve persistent IDs before constructing new records.
            (existing_object_uuids, existing_predicate_uuids, existing_semantic_uuids,) = self.load_existing_uuids(conn)

            self.model = self.build_rdf_relational_model(
                existing_object_uuids=existing_object_uuids,
                existing_predicate_uuids=existing_predicate_uuids,
                existing_semantic_uuids=existing_semantic_uuids,
            )

            with conn.cursor() as cur:
                # Create predicate-specific relationship tables.
                # generate_sql_schema() must not rebuild self.model.
                for statement in self.generate_sql_schema():
                    cur.execute(statement)

                cur.executemany("""
                    INSERT INTO objects (object, definition, object_uuid)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (object) DO NOTHING
                """, [(r["object"], r["definition"], r["object_uuid"],) for r in self.model["objects"]])

                cur.executemany("""
                    INSERT INTO predicates (predicate, definition, predicate_uuid)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (predicate) DO NOTHING
                """, [
                    (r["predicate"], r["definition"], r["predicate_uuid"])
                    for r in self.model["predicates"]
                ])

                semantic_rows = [
                    (r["subject"], r["predicate"], r["object"], r["semantic_uuid"])
                    for rows in self.model["relationships"].values()
                    for r in rows
                ]
                
                cur.executemany("""
                    INSERT INTO semantics (subject, predicate, object, semantic_uuid)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (subject, predicate, object) DO NOTHING
                """, semantic_rows)

                for predicate, rows in self.model["relationships"].items():
                    table_name = next(p["table_name"] for p in self.model["predicates"] if p["predicate"] == predicate)
                    query = sql.SQL("""
                        INSERT INTO {} (subject, object, semantic_uuid)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (subject, object) DO NOTHING
                    """).format(sql.Identifier(table_name))
                    cur.executemany(query, [(r["subject"], r["object"], r["semantic_uuid"]) for r in rows])

    def _reset_schema(self, conn):
        """Drop predicate-specific relationship tables and shared RDF tables."""
        with conn.cursor() as cur:
            cur.execute("SELECT predicate FROM predicates ORDER BY predicate")
            predicates = [row[0] for row in cur.fetchall()]

            for predicate in predicates:
                table_name = self.to_table_name(predicate)
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))

            cur.execute("DROP TABLE IF EXISTS semantics CASCADE")
            cur.execute("DROP TABLE IF EXISTS predicates CASCADE")
            cur.execute("DROP TABLE IF EXISTS objects CASCADE")



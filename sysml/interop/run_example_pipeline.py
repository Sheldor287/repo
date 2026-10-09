from triples import object_definitions, predicate_definitions, triples
from pipeline import SQL_Model

rdf_sql = SQL_Model(triples, object_definitions, predicate_definitions)
model = rdf_sql.build_rdf_relational_model()




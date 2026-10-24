import json, sys
from pathlib import Path
sys.path.insert(0, "sysml")
from transformers.transform import convert_file
from interop.triples import triples, object_definitions, predicate_definitions, predicate_definitions_mapping

data = {
    "triples": triples,
    "object_definitions": object_definitions,
    "predicate_definitions": predicate_definitions,
    "predicate_definitions_mapping": predicate_definitions_mapping,
}

input_path = Path("sysml/data/automotive_data.json")
input_path.write_text(json.dumps(data, indent=4), encoding="utf-8")

result = convert_file(input_path, Path("sysml/data/cameo_xmi_output"))
print(json.dumps(result, indent=4))
"""Notional domain contracts for the ERP prototype.

These contracts describe useful starter payloads, not finalized business schemas.
They deliberately keep external authority as provenance metadata rather than
assuming the ERP is authoritative for every domain.
"""
from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any


def _entity(required: tuple[str, ...], **fields: str) -> dict[str, Any]:
    return {"required": list(required), "fields": fields}


DOMAIN_CATALOG: dict[str, dict[str, dict[str, Any]]] = {
    "organization_program": {
        "organization": _entity(("name", "organization_code"), name="string", organization_code="string", description="string", status="string"),
        "person": _entity(("name",), name="string", organization_code="string", email="string", status="string", classification="string"),
        "user_identity": _entity(("identity_provider", "external_subject", "status"), identity_provider="string", external_subject="string", person_source_system="string", person_source_record_id="string", status="string"),
        "program": _entity(("name", "program_code", "organization_code"), name="string", program_code="string", organization_code="string", lifecycle_stage="string", status="string", start_date="date", end_date="date"),
        "project": _entity(("name", "project_code", "program_code"), name="string", project_code="string", program_code="string", status="string", start_date="date", end_date="date", owner="string"),
        "product": _entity(("name", "product_code", "program_code"), name="string", product_code="string", program_code="string", description="string", lifecycle_status="string"),
        "asset": _entity(("name", "asset_tag", "product_code", "program_code"), name="string", asset_tag="string", product_code="string", program_code="string", serial_number="string", lifecycle_status="string", location="string"),
        "workforce_assignment": _entity(("person_source_id", "person_source_system", "role", "program_code"), person_source_id="string", person_source_system="string", role="string", program_code="string", project_code="string", allocation_percent="number", start_date="date", end_date="date"),
    },
    "contracts_commercial": {
        "proposal": _entity(("proposal_number", "program_code", "supplier_code", "status"), proposal_number="string", program_code="string", supplier_code="string", status="string", value="number", currency="string", submitted_date="date"),
        "supplier": _entity(("supplier_code", "name", "organization_code"), supplier_code="string", name="string", organization_code="string", country="string", status="string", contact_email="string"),
        "contract": _entity(("contract_number", "program_code", "supplier_code", "status"), contract_number="string", program_code="string", supplier_code="string", status="string", currency="string", ceiling_value="number", start_date="date", end_date="date"),
        "contract_revision": _entity(("contract_number", "revision", "effective_date"), contract_number="string", revision="string", effective_date="date", change_summary="string", value="number", status="string"),
    },
    "engineering": {
        "part": _entity(("part_number", "name"), part_number="string", name="string", revision="string", product_code="string", unit_of_measure="string", status="string"),
        "engineering_configuration": _entity(("configuration_code", "program_code", "product_code", "revision"), configuration_code="string", program_code="string", product_code="string", revision="string", status="string", baseline_date="date"),
        "engineering_artifact": _entity(("artifact_name", "program_code", "artifact_format", "content_hash"), artifact_name="string", program_code="string", artifact_format="string", content_hash="string", source_model_id="string", configuration_code="string", revision="string"),
        "requirement": _entity(("requirement_id", "program_code", "text", "status"), requirement_id="string", program_code="string", text="string", status="string", verification_method="string", source_document_id="string"),
        "engineering_change": _entity(("change_id", "program_code", "summary", "status"), change_id="string", program_code="string", summary="string", status="string", configuration_code="string", requested_date="date", approval_date="date"),
    },
    "supply_chain": {
        "purchase_order": _entity(("po_number", "program_code", "supplier_code", "status"), po_number="string", program_code="string", supplier_code="string", status="string", currency="string", total_value="number", order_date="date", expected_date="date"),
        "purchase_order_line": _entity(("po_number", "line_number", "item_code", "quantity"), po_number="string", line_number="integer", item_code="string", quantity="number", unit_price="number", currency="string"),
        "receipt": _entity(("receipt_number", "po_number", "received_date"), receipt_number="string", po_number="string", received_date="date", item_code="string", quantity_received="number", disposition="string"),
        "inventory_item": _entity(("item_code", "name", "program_code"), item_code="string", name="string", program_code="string", unit_of_measure="string", quantity_on_hand="number", location="string", lot_number="string"),
        "inventory_transaction": _entity(("transaction_id", "item_code", "transaction_type", "quantity"), transaction_id="string", item_code="string", transaction_type="string", quantity="number", occurred_at="datetime", program_code="string", location="string", reference="string"),
    },
    "delivery_operations": {
        "work_order": _entity(("work_order_number", "program_code", "description", "status"), work_order_number="string", program_code="string", description="string", status="string", project_code="string", product_code="string", planned_start="date", planned_finish="date"),
        "resource": _entity(("resource_code", "name", "resource_type"), resource_code="string", name="string", resource_type="string", capacity="number", unit="string", status="string"),
        "schedule_activity": _entity(("activity_id", "program_code", "name", "start_date", "finish_date"), activity_id="string", program_code="string", name="string", start_date="date", finish_date="date", project_code="string", percent_complete="number", predecessor_ids="array"),
        "manufacturing_order": _entity(("order_number", "program_code", "product_code", "quantity"), order_number="string", program_code="string", product_code="string", quantity="number", status="string", planned_start="date", planned_finish="date"),
        "delivery": _entity(("delivery_id", "program_code", "asset_tag", "status"), delivery_id="string", program_code="string", asset_tag="string", status="string", shipped_date="date", delivered_date="date", destination="string"),
        "deployment": _entity(("deployment_id", "program_code", "asset_tag", "status"), deployment_id="string", program_code="string", asset_tag="string", status="string", site="string", deployed_date="date"),
        "sustainment_event": _entity(("event_id", "program_code", "asset_tag", "event_type"), event_id="string", program_code="string", asset_tag="string", event_type="string", occurred_at="datetime", description="string", work_order_number="string"),
    },
    "finance": {
        "financial_account": _entity(("account_code", "name", "program_code"), account_code="string", name="string", program_code="string", account_type="string", currency="string", status="string"),
        "financial_transaction": _entity(("transaction_id", "program_code", "transaction_type", "amount", "currency", "occurred_at"), transaction_id="string", program_code="string", transaction_type="string", amount="number", currency="string", occurred_at="datetime", account_code="string", contract_number="string", description="string"),
        "invoice": _entity(("invoice_number", "supplier_code", "program_code", "amount", "status"), invoice_number="string", supplier_code="string", program_code="string", amount="number", status="string", currency="string", invoice_date="date", due_date="date", contract_number="string"),
        "payment": _entity(("payment_id", "invoice_number", "amount", "currency", "payment_date"), payment_id="string", invoice_number="string", amount="number", currency="string", payment_date="date", status="string"),
        "cost_forecast": _entity(("forecast_id", "program_code", "period", "amount", "currency"), forecast_id="string", program_code="string", period="string", amount="number", currency="string", cost_category="string", basis="string"),
    },
    "documents_knowledge": {
        "document": _entity(("document_id", "title", "program_code", "document_type"), document_id="string", title="string", program_code="string", document_type="string", revision="string", status="string", content_hash="string", source_uri="string"),
        "inbound_artifact": _entity(("artifact_id", "source_system", "file_name", "content_hash", "received_at"), artifact_id="string", source_system="string", file_name="string", media_type="string", content_hash="string", received_at="datetime", storage_uri="string", file_format="string"),
    },
    "integration_governance": {
        "source_system": _entity(("system_code", "name", "data_domain"), system_code="string", name="string", data_domain="string", integration_type="string", owner="string", status="string"),
        "data_authority": _entity(("data_domain", "authoritative_system", "governance_authority"), data_domain="string", authoritative_system="string", governance_authority="string", effective_date="date", end_date="date", rationale="string"),
        "domain_relationship": _entity(("source_domain", "source_entity_type", "source_system", "source_record_id", "relationship_type", "target_domain", "target_entity_type", "target_system", "target_record_id"), source_domain="string", source_entity_type="string", source_system="string", source_record_id="string", relationship_type="string", target_domain="string", target_entity_type="string", target_system="string", target_record_id="string", program_code="string", effective_date="date", status="string"),
        "external_identifier": _entity(("erp_entity_type", "erp_record_uuid", "external_system", "external_id"), erp_entity_type="string", erp_record_uuid="string", external_system="string", external_id="string"),
    },
}
CURRENT_CONTRACT_VERSION = "1.0"

# First-pass references for stable business keys. These are validation aids for
# the mock contracts; unresolved cross-domain cardinality remains open.
REFERENCE_RULES: dict[str, dict[str, tuple[str, str]]] = {
    "program": {"organization_code": ("organization", "organization_code")},
    "person": {"organization_code": ("organization", "organization_code")},
    "project": {"program_code": ("program", "program_code")},
    "product": {"program_code": ("program", "program_code")},
    "part": {"product_code": ("product", "product_code")},
    "asset": {"program_code": ("program", "program_code"), "product_code": ("product", "product_code")},
    "workforce_assignment": {"program_code": ("program", "program_code"), "project_code": ("project", "project_code")},
    "supplier": {"organization_code": ("organization", "organization_code")},
    "proposal": {"program_code": ("program", "program_code"), "supplier_code": ("supplier", "supplier_code")},
    "contract": {"program_code": ("program", "program_code"), "supplier_code": ("supplier", "supplier_code")},
    "engineering_configuration": {"program_code": ("program", "program_code"), "product_code": ("product", "product_code")},
    "engineering_artifact": {"program_code": ("program", "program_code"), "configuration_code": ("engineering_configuration", "configuration_code")},
    "requirement": {"program_code": ("program", "program_code"), "source_document_id": ("document", "document_id")},
    "engineering_change": {"program_code": ("program", "program_code"), "configuration_code": ("engineering_configuration", "configuration_code")},
    "purchase_order": {"program_code": ("program", "program_code"), "supplier_code": ("supplier", "supplier_code")},
    "purchase_order_line": {"po_number": ("purchase_order", "po_number"), "item_code": ("part", "part_number")},
    "receipt": {"po_number": ("purchase_order", "po_number")},
    "inventory_item": {"program_code": ("program", "program_code"), "item_code": ("part", "part_number")},
    "inventory_transaction": {"item_code": ("inventory_item", "item_code"), "program_code": ("program", "program_code")},
    "work_order": {"program_code": ("program", "program_code"), "project_code": ("project", "project_code"), "product_code": ("product", "product_code")},
    "schedule_activity": {"program_code": ("program", "program_code"), "project_code": ("project", "project_code")},
    "manufacturing_order": {"program_code": ("program", "program_code"), "product_code": ("product", "product_code")},
    "delivery": {"program_code": ("program", "program_code"), "asset_tag": ("asset", "asset_tag")},
    "deployment": {"program_code": ("program", "program_code"), "asset_tag": ("asset", "asset_tag")},
    "sustainment_event": {"program_code": ("program", "program_code"), "asset_tag": ("asset", "asset_tag"), "work_order_number": ("work_order", "work_order_number")},
    "financial_account": {"program_code": ("program", "program_code")},
    "financial_transaction": {"program_code": ("program", "program_code"), "account_code": ("financial_account", "account_code")},
    "invoice": {"program_code": ("program", "program_code"), "supplier_code": ("supplier", "supplier_code"), "contract_number": ("contract", "contract_number")},
    "payment": {"invoice_number": ("invoice", "invoice_number")},
    "cost_forecast": {"program_code": ("program", "program_code")},
    "contract_revision": {"contract_number": ("contract", "contract_number")},
}

DOMAIN_LABELS = {
    "organization_program": "Organization, programs and products",
    "contracts_commercial": "Proposals, suppliers and contracts",
    "engineering": "Engineering, configuration and requirements",
    "supply_chain": "Procurement, receiving and inventory",
    "delivery_operations": "Projects, work, manufacturing and sustainment",
    "finance": "Financial tracking",
    "documents_knowledge": "Documents and knowledge",
    "integration_governance": "Integration and data authority",
}


def _matches(value: Any, kind: str) -> bool:
    if kind == "string":
        return isinstance(value, str) and bool(value.strip())
    if kind == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value))
        )
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "date":
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False
    if kind == "datetime":
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
    return False


def validate_record(entity_type: str, record: Any) -> list[str]:
    """Return field-level errors for one entity contract."""
    contract = next(
        (entities[entity_type] for entities in DOMAIN_CATALOG.values() if entity_type in entities),
        None,
    )
    if contract is None:
        return [f"Unknown entity type: {entity_type}"]
    if not isinstance(record, dict):
        return ["Record must be a JSON object"]
    errors: list[str] = []
    fields = contract["fields"]
    for field in contract["required"]:
        if field not in record or record[field] is None or record[field] == "":
            errors.append(f"{field}: required field is missing")
    for field, value in record.items():
        expected = fields.get(field)
        if expected is None:
            errors.append(f"{field}: field is not in the {entity_type} contract")
        elif value is not None and not _matches(value, expected):
            errors.append(f"{field}: expected {expected}")
    for start_field, end_field in (
        ("start_date", "end_date"),
        ("planned_start", "planned_finish"),
        ("start_date", "finish_date"),
        ("effective_date", "end_date"),
    ):
        start_value, end_value = record.get(start_field), record.get(end_field)
        if start_value and end_value and _matches(start_value, "date") and _matches(end_value, "date"):
            if date.fromisoformat(start_value) > date.fromisoformat(end_value):
                errors.append(f"{start_field}: must be on or before {end_field}")
    for field in ("allocation_percent", "percent_complete"):
        value = record.get(field)
        if value is not None and _matches(value, "number") and not 0 <= value <= 100:
            errors.append(f"{field}: must be between 0 and 100")
    return errors


def entity_domain(entity_type: str) -> str | None:
    return next((domain for domain, entities in DOMAIN_CATALOG.items() if entity_type in entities), None)


def catalog_response() -> list[dict[str, Any]]:
    return [
        {
            "key": domain,
            "label": DOMAIN_LABELS[domain],
            "entities": [
                {
                    "key": entity,
                    "contract_version": CURRENT_CONTRACT_VERSION,
                    "required": spec["required"],
                    "fields": spec["fields"],
                }
                for entity, spec in entities.items()
            ],
        }
        for domain, entities in DOMAIN_CATALOG.items()
    ]

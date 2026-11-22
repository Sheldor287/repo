# Mock ERP domains

This is the first notional domain catalog for the ERP prototype. It turns the
functional areas in the vision and artifact updates into concrete payload
contracts that can be staged, validated, reviewed, and displayed. It is a
working mock, not a finalized enterprise data model.

## Functional coverage

| Functional area | Mock entity types |
| --- | --- |
| Organization, identity and program lifecycle | organization, person, user identity, program, project, product, part, asset, workforce assignment |
| Proposals, suppliers, and contracts | proposal, supplier, contract, contract revision |
| Engineering and configuration | engineering configuration, engineering artifact, requirement, engineering change |
| Procurement and logistics | purchase order, purchase order line, receipt, inventory item, inventory transaction |
| Work and delivery | work order, resource, schedule activity, manufacturing order, delivery, deployment, sustainment event |
| Finance | financial account, financial transaction, invoice, payment, cost forecast |
| Documents and knowledge | document, inbound artifact |
| Integration, authority and relationships | source system, data authority, domain relationship, external identifier |

The existing MBSE tables remain available for structured model data. The
`engineering_artifact` mock record represents delivered artifacts and their
provenance; it does not replace the MBSE model tables or parse MDZIP/XMI files.

## Batch request

Submit JSON to `POST /api/ingest/domain/{entity_type}`. Each record has a source
identifier and a `data` object matching the entity contract. Source identity is
kept separate from the record's business fields.

```json
{
  "source_system": "ERP Mock UI",
  "contract_version": "1.0",
  "records": [
    {
      "source_record_id": "ORG-001",
      "data": {
        "name": "Demo Organization",
        "organization_code": "ORG-001",
        "status": "active"
      }
    }
  ]
}
```

Use `GET /api/domains` to inspect the entities, required fields, and field types.
The first validator checks record shape, required and declared fields, types,
duplicate source identifiers, simple date/percentage rules, and selected
references to previously promoted records. For example, promote an Organization
before a Program, and a Program before its Projects. Domain relationships
resolve both endpoints by domain, entity type, source system, and source record
ID. Date and datetime fields use ISO strings. Broader domain rules, configured
enumerations, physical foreign keys, and authorization remain future work.

## Staging, review, and history

1. A request becomes one staging batch. The system stores the parsed source
   records, source system, contract version, and a SHA-256 hash of canonicalized
   request JSON.
2. Validation, governance, and promotion have separate status fields. Validation
   status is `VALIDATED` or `INVALID`; governance status is `PENDING`,
   `APPROVED`, or `REJECTED`; promotion status is `NOT_PROMOTED`, `PROMOTED`, or
   `FAILED`. The entity's own operational status remains inside its domain data.
3. If any row fails validation, the batch is `INVALID`. The errors remain
   visible from `GET /api/ingest/uploads`; invalid batches cannot be approved.
4. A fully valid batch is `VALIDATED` and appears in the dashboard review queue.
   Its validation run records contract and validator versions, result counts,
   errors, and execution time.
5. Approval records reviewer, reason, and time, then atomically appends a new
   revision of every record to `domain_record`. Rejection records the decision
   and does not write domain records.
6. Repeated `source_record_id` values from the same source system create
   subsequent revisions. Earlier promoted versions remain available; the
   default records API returns the highest revision, while
   `GET /api/records?history=true` returns version history.

The mock catalog is a bounded, code-defined set of contracts; records cannot
add arbitrary fields. The prototype stores their payloads in a shared JSON
record table to exercise ingestion and governance while the conceptual model
and relationships evolve. This is not the target normalized relational model
for authoritative ERP data. The catalog preserves Program codes where
supplied, so records can be viewed for a single Program or across the
organization. Program is an aggregation context, not an access-isolation
boundary.

## Governance and authority boundaries

The current workflow implements batch/file-level governance. An approved
`data_authority` record can identify the authoritative system for an entity or
domain. Each promoted representation records `ERP_AUTHORITATIVE`,
`EXTERNAL_AUTHORITATIVE`, `UNASSIGNED`, or `CONFLICT` based on those explicit
governance records; source system alone never establishes authority. Reviewer
names are supplied in the request because authentication is not implemented.
Authority mappings may be scoped to an entity type or domain and include
effective and end dates. `ERP_SYSTEM_CODE` controls which system code counts as
the ERP; its default is `ERP`.
Fine-grained record review, correction authority, landing/data-lake storage,
original binary retention, notifications, and reprocessing are not implemented
yet.

The shared record store uses revisions for ordinary mock domain records.
Repeated inventory transaction source identities are rejected because those
records represent immutable events. This is a prototype policy, not a complete
correction workflow. Contract revisions remain explicit domain records, and
derived KPIs should retain calculation lineage when that capability is added.

Person and User identity are distinct contracts. `person` does not assert
employment; `user_identity` is only an external identity mapping and does not
authenticate or authorize a user.

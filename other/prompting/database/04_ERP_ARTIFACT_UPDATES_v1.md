# ERP Artifact Updates

This document records architectural decisions and clarifications made after the initial ERP Vision, Architecture, Domain Model, and Data Principles artifacts.

It is a **delta document**. It does not replace the earlier artifacts. Where this document conflicts with an earlier statement, this document represents the more recent decision.

---

## 1. Purpose

The ERP architecture is being refined through explicit decisions rather than by repeatedly rewriting the foundational artifacts.

The current foundational artifacts are:

- `00_ERP_VISION.md`
- `01_ERP_ARCHITECTURE.md`
- `02_ERP_DOMAIN_MODEL.md`
- `03_ERP_DATA_PRINCIPLES.md`

This document captures decisions that should be incorporated into future interpretations of those artifacts and future implementation prompts.

The primary purpose is to prevent Codex or future developers from interpreting unresolved language in the earlier documents more broadly than intended.

---

# 2. Configuration and Engineering

## Decision

In the current ERP context, **configuration primarily refers to the engineering configuration of the product or capability produced by a Program**.

This is closely aligned with the Engineering domain.

The expected engineering configuration artifacts include:

- MDZIP
- XMI
- JSON

These artifacts originate from engineering/model-authoring environments and are expected to be ingested, validated, governed, versioned, and stored by the ERP.

The ERP is therefore not being designed as a generic low-code configuration platform.

### Conceptual relationship

```text
Organization
    │
    └── Program
          │
          └── Engineering
                │
                └── Engineering Configuration
                      │
                      ├── MDZIP
                      ├── XMI
                      └── JSON
```

The engineering configuration represents the engineering definition of the product or capability associated with the Program.

### Architectural implication

The architecture should distinguish between:

1. **Engineering configuration**
   - Product/capability engineering representation.
   - Primarily associated with MBSE and related engineering artifacts.

2. **ERP/application configuration**
   - Ordinary system settings such as workflow configuration, permissions, validation settings, and operational parameters.

These are different concepts and should not be conflated.

### Update to earlier artifacts

Where the earlier architecture or domain model describes "configuration" as a potentially general mechanism for dynamically defining ERP domains, that interpretation should be narrowed.

The ERP should not be treated as a generic low-code platform.

---

# 3. Data Authority and System of Record

## Decision

The ERP does not independently determine which system is authoritative for a particular data domain.

**Authority is determined by organizational governance.**

The governance board determines the authoritative system or source for relevant categories of organizational data.

### Example: Engineering

Engineering models are authored in PLM/engineering environments.

The expected flow is:

```text
PLM / Engineering Tool
        │
        │ authors
        ▼
Engineering Model
        │
        │ delivered as
        │ MDZIP / XMI / JSON
        ▼
ERP Ingestion
        │
        ▼
Validation
        │
        ▼
Governance
        │
        ▼
ERP
        │
        └── authoritative organizational storage
```

The ERP is not the engineering authoring environment.

The ERP stores the delivered engineering information as an authoritative organizational record where governance establishes ERP as the applicable system of record.

### Example: Employee Data

The ERP may obtain employee information from HR.

Employee information may be maintained externally while the ERP stores an organizationally useful representation.

For example:

```text
HR
 │
 │ employee data
 ▼
ERP
 │
 ├── required employee information
 └── optional additional employee information
```

The ERP should not assume that every field maintained by HR must be replicated.

### Architectural principle

The relevant distinction is:

> **Authoring authority, organizational system of record, and integration source are distinct concepts.**

A system may author data without being the ERP's source of record for organizational purposes.

### Governance metadata

The architecture should support the ability to identify, for relevant data domains:

- authoritative system
- source system
- source identifier
- ERP identifier
- ownership
- governance authority
- synchronization/integration relationship
- provenance

The specific authority remains an organizational governance decision.

---

# 4. Program as the Primary Operational Boundary

## Decision

The following hierarchy is accepted as a core organizational structure:

```text
Organization
    │
    └── Program
          │
          └── Project
                │
                └── Product
                      │
                      └── Asset
```

The hierarchy should not be interpreted as preventing other relationships between these entities.

The critical decision is the role of **Program**.

> **The Program is the primary boundary that aggregates everything associated with delivering a product or capability.**

### Program responsibilities

A Program may:

- generate and manage contracts
- establish and manage engineering activity
- generate and manage engineering models
- control or consume inventory
- generate and process work orders
- track financial activity
- contain projects
- produce products
- result in assets
- support sustainment activity

Conceptually:

```text
                         Organization
                              │
                              ▼
                           Program
                              │
       ┌──────────┬───────────┼───────────┬───────────┐
       ▼          ▼           ▼           ▼           ▼
   Contracts  Engineering  Projects    Inventory    Finance
                              │
                              ▼
                           Product
                              │
                              ▼
                             Asset
```

### Organization-level visibility

The Organization must also be able to aggregate and analyze these same categories **across Programs**.

Therefore, Program is a primary operational boundary, but it is not an isolation boundary.

The organization needs both:

```text
Program-level view
```

and:

```text
Organization-wide view
```

### Common operating picture

This Program-centered structure supports the ERP's common operating picture:

```text
Organization
    │
    ├── Program A
    │     ├── Contracts
    │     ├── Engineering
    │     ├── Projects
    │     ├── Inventory
    │     ├── Work Orders
    │     └── Finance
    │
    ├── Program B
    │     └── ...
    │
    └── Program C
          └── ...
```

This should be treated as a central organizing principle for future domain modeling.

---

# 5. History and Versioning

## Decision

The ERP should not use a single universal interpretation of "history" or "append-only."

Different data types require different historical semantics.

The following patterns are established:

| Domain/Data Type | Historical Semantics |
|---|---|
| Contract | Versioned revisions |
| Inventory transaction | Immutable transaction history |
| Engineering model | Imported model versions |
| Governance decision | Immutable decision/audit record |
| Supplier address | Current state + historical changes |
| Derived KPI | Reproducible calculation/history |

### Important distinction

**Append-only is an implementation/data-preservation technique.**

**History is a business requirement.**

Therefore, future design decisions should begin by asking:

> What historical fact must be preserved?

and then select the appropriate mechanism.

Possible mechanisms include:

- immutable transactions
- versioned records
- revisions
- snapshots
- audit records
- event/history records
- derived-data lineage

These mechanisms should not be treated as interchangeable.

### Historical state

Where appropriate, the system should support reconstructing the relevant state of organizational data at a prior point in time.

The exact implementation mechanism may vary by domain.

---

# 6. Inbound Data Lifecycle

## Decision

The inbound data lifecycle is now substantially defined.

```text
External/User Source
        │
        ▼
Inbound Artifact
        │
        ▼
Data Lake / Landing
        │
        ▼
Staging
        │
        ▼
Parsing / Transformation
        │
        ▼
Validation
        │
        ▼
Governance
        │
        ▼
Promotion
        │
        ▼
Authoritative ERP Data
        │
        ▼
Operational Use
```

---

## 6.1 Original artifacts

Original submitted artifacts should be retained in the data lake.

This provides preservation of:

- original source representation
- provenance
- reprocessing capability
- audit evidence
- source-to-record traceability

The authoritative relational representation does not replace the original inbound artifact.

---

## 6.2 Staging

Once an artifact has been staged, that staging representation should not simply be overwritten.

If a changed submission is received:

```text
Submission V1
    ↓
Staging V1

Submission V2
    ↓
Staging V2
```

The new version should be tracked separately.

This supports provenance and historical reconstruction.

---

## 6.3 Invalid submissions

A submission containing invalid records should be identified as invalid and logged accordingly.

The submitter should be notified of the reason for rejection/invalidity.

The system should preserve sufficient validation information to explain:

- what failed
- where it failed
- why it failed
- which submission/version was affected

The exact treatment of mixed-validity files remains an implementation detail to be defined by the applicable ingestion workflow, but invalid data must not silently become authoritative data.

---

## 6.4 Validation results

Validation results are versioned.

Conceptually:

```text
Artifact V1
    │
    ├── Validation Result V1
    │
    └── Validation Result V2
```

This allows validation to remain historically traceable as schemas and validation rules evolve.

---

## 6.5 Human modification of staged data

Humans may modify staged data where the applicable workflow permits it.

Any such modification must remain traceable.

At minimum, the architecture should be capable of preserving:

- original staged representation
- modified representation
- identity of modifier
- timestamp
- reason/context for modification
- resulting version

The exact workflow for human modification remains an open implementation/design decision.

---

## 6.6 Governance and approval

Initially, governance approval is expected to operate primarily at the **batch/file level**.

The architecture should nevertheless support future approval at finer granularity, including:

- batch
- file
- record

Therefore:

```text
Governance
    │
    ├── Batch approval
    ├── File approval
    └── Record approval
```

The first implementation may focus on batch-level approval without preventing future expansion.

---

## 6.7 Governance approval equals promotion

Governance approval is the promotion event.

Conceptually:

```text
Validated
    │
    ▼
Governance Approval
    │
    ▼
Promotion
    │
    ▼
Authoritative Data
```

There should not be an ambiguous second "promotion approval" step after governance approval unless a future requirement explicitly introduces one.

---

# 7. Updates to Existing Authoritative Data

When approved data corresponds to an existing authoritative record, the ERP should preserve the historical change rather than silently overwrite the prior organizational state.

Conceptually:

```text
Authoritative Record V1
        │
        │ approved change
        ▼
Authoritative Record V2
```

The governance process provides the organizational control and evidence surrounding the change.

This is one of the principal use cases for the ERP's append/history architecture.

The exact database representation may vary by entity and should follow the historical semantics established for that entity.

---

# 8. Corrections

Corrections are expected to use tiered processes.

Potential correction mechanisms include:

1. automated or scripted correction
2. data-engineering correction
3. governance/data-management correction
4. user/submitting-party correction

The appropriate level depends on the nature and authority of the correction.

Corrections must preserve appropriate provenance and history rather than silently destroying the prior state.

The detailed correction authority matrix remains to be defined.

---

# 9. Reprocessing

Imported artifacts may eventually be reprocessed against newer schemas or validation rules.

This is an intended capability but is a **later priority**.

The architecture should avoid making future reprocessing impossible by:

- retaining original artifacts
- preserving source identifiers
- preserving submission/version information
- versioning validation results
- preserving provenance

Full reprocessing workflows do not need to be implemented in the initial vertical slices unless required by the immediate use case.

---

# 10. External Source Changes and Retractions

When an external authoritative or integrated source changes or retracts information, the change in status should be visible to the appropriate organizational authorities.

At minimum, this involves notification to:

- data engineers
- governance board

The system should preserve the fact that the external source changed or retracted the information.

The precise response workflow—automatic suspension, quarantine, supersession, review, or other state transition—remains to be defined for individual domains.

---

# 11. MBSE / Engineering Implications

The above decisions reinforce the role of MBSE as an important ERP domain without making MBSE synonymous with the ERP.

The ERP should support engineering artifacts such as:

- MDZIP
- XMI
- JSON

while preserving their source identity and provenance.

The expected relationship is:

```text
Engineering Authoring Environment
            │
            ▼
      Engineering Artifact
            │
            ▼
       ERP Ingestion
            │
            ▼
         Validation
            │
            ▼
        Governance
            │
            ▼
         Promotion
            │
            ▼
  Authoritative ERP Record
```

The ERP is therefore an organizational repository and integration point for engineering information, not a replacement for engineering authoring tools.

---

# 12. Architectural Consequences

These decisions establish several principles that should guide future implementation.

### 12.1 Program-centered organization

Program should be treated as a major cross-domain aggregation boundary.

### 12.2 Governance determines authority

The ERP should represent authority decisions rather than assuming authority based solely on system ownership.

### 12.3 Engineering is tightly coupled to configuration

In this ERP context, configuration primarily means engineering configuration of the product/capability produced by a Program.

### 12.4 Source artifacts are preserved

The original inbound representation remains available in the data lake.

### 12.5 Staging is versioned

New submissions or changed staging representations create new versions rather than silently overwriting previous staging state.

### 12.6 Validation is historical

Validation results are versioned and traceable.

### 12.7 Governance controls promotion

Governance approval is the authoritative transition from validated data into authoritative organizational data.

### 12.8 Historical semantics are domain-specific

The system uses the appropriate history mechanism for each class of data rather than forcing every entity into a single append-only pattern.

### 12.9 External authority is explicit

The ERP must be able to distinguish between:

- authoring system
- source system
- authoritative system
- integrated system
- ERP representation

---

# 13. Remaining Architectural Decisions

The five major clarification areas are now substantially resolved.

The following items remain open and should be treated as explicit architectural decisions rather than assumptions.

### 13.1 Staged-data modification

Define the exact workflow and permissions for human modification of staged data.

Specifically:

- Can users directly edit staged records?
- Does every edit create a new staging version?
- Is the original staged representation immutable?
- Who may modify staged data?
- Does modification require revalidation?
- Does modification invalidate an existing validation result?

### 13.2 Correction authority

Define which correction mechanisms may be used by:

- scripts
- data engineers
- data managers
- governance board
- submitting users

### 13.3 External retraction behavior

Define the state transition resulting from an external source changing or retracting information.

### 13.4 Fine-grained governance

Define when governance moves from:

```text
Batch
```

to:

```text
File
```

or:

```text
Record
```

approval.

### 13.5 Reprocessing

Define the future workflow for reprocessing retained artifacts against:

- newer schemas
- newer validation rules
- corrected parsers
- updated domain models

This is explicitly lower priority than establishing the initial ingestion/governance path.

---

# 14. Guidance for Future Codex Prompts

Future implementation prompts should treat the decisions in this document as architectural constraints.

Codex should not:

- reinterpret Program as merely another project-management object
- treat engineering configuration as a generic low-code configuration system
- assume ERP is authoritative for all organizational data
- overwrite staged or authoritative historical information without an explicit historical policy
- discard original inbound artifacts
- bypass validation or governance when promoting inbound data
- silently overwrite existing authoritative records
- assume all entities use identical versioning/history mechanisms
- assume batch-only governance is the permanent architectural limit

Codex should:

- preserve provenance
- preserve source artifacts
- preserve version history
- distinguish source identity from ERP identity
- treat governance as an explicit control boundary
- treat Program as a primary cross-domain aggregation boundary
- distinguish authoring authority from organizational system-of-record authority
- implement domain-appropriate historical semantics
- keep unresolved architectural decisions explicit

---

# 15. Current Architectural Position

The ERP can now be characterized as:

> **An organizational operating system and governed data platform centered on Programs, connecting engineering, projects, products, assets, contracts, supply chain, work, and financial activity while preserving provenance, authority, governance, and historical state.**

The Program provides the primary operational context.

Engineering configuration provides the engineering representation of the product or capability.

External systems remain important sources and authoring environments.

Governance determines authority and controls promotion.

The data lake preserves original inbound artifacts.

The relational ERP preserves authoritative organizational representations and their required history.

Together, these mechanisms provide the foundation for the organization's common operating picture.
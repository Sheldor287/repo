# ERP Architecture

## Purpose

This document defines the architectural structure of the ERP described in `00_ERP_VISION.md`.

The ERP is not intended to be a collection of independent business applications loosely sharing a database. It is intended to be an **organizational operating system** built around a common, governed record of organizational data and events.

The architecture must support multiple business domains while allowing the detailed configuration of those domains to evolve over time.

The architecture therefore separates:

1. **Platform capabilities**
2. **Business/domain models**
3. **Business-specific extensions**
4. **Applications and workflows**
5. **Inbound data and external integrations**
6. **Authoritative organizational data**

---

## 1. Architectural Goals

The architecture must support the following goals from the ERP Vision:

- Maintain a central organizational record.
- Track the lifecycle of programs and their associated activities.
- Preserve historical information required to understand how a program evolved.
- Accept data from non-technical users through controlled file-based workflows.
- Accept data from external systems and authoring tools.
- Validate inbound data before it becomes authoritative.
- Apply governance and approval processes before promotion.
- Support multiple business domains.
- Allow business configuration to evolve without rebuilding the platform.
- Support MBSE and other engineering data without making MBSE the definition of the entire ERP.
- Integrate with PLM, CAD, CRM, and other systems.
- Remain auditable, versioned, containerizable, interoperable, and cloud-ready.
- Support incremental development through working vertical slices.

---

# 2. Architectural Model

The ERP should be understood as several interacting architectural layers.

```text
                    USERS / EXTERNAL SYSTEMS
                              |
                              v
                  +-------------------------+
                  |     Applications        |
                  | UI / API / Workflows    |
                  +------------+------------+
                               |
                               v
                  +-------------------------+
                  |    Domain Capabilities  |
                  | Program / Engineering   |
                  | Logistics / Finance     |
                  | Contracts / etc.        |
                  +------------+------------+
                               |
                               v
                  +-------------------------+
                  |   ERP Platform Layer    |
                  | Identity / Governance    |
                  | Validation / Workflow   |
                  | Files / Audit / Search  |
                  | Configuration / Events  |
                  +------------+------------+
                               |
                +--------------+--------------+
                |                             |
                v                             v
      +-------------------+         +---------------------+
      | Authoritative     |         | External / Inbound  |
      | Relational Data   |         | Data Sources        |
      | PostgreSQL        |         | Files / PLM / CAD   |
      +-------------------+         | CRM / MBSE / etc.   |
                                    +---------------------+
```

This diagram represents an architectural relationship, not necessarily a final deployment topology.

---

# 3. Platform vs. Domain vs. Extension

One of the most important architectural distinctions is between what the ERP **is** and what a particular business **configures it to be**.

## 3.1 Platform

The platform provides capabilities that should be reusable across businesses and domains.

Potential platform capabilities include:

- identity;
- authorization;
- organizations;
- users;
- file ingestion;
- staging;
- validation;
- governance;
- approval workflows;
- audit;
- versioning;
- event/history tracking;
- document management;
- configuration;
- API infrastructure;
- search;
- notifications;
- background processing;
- integration infrastructure;
- observability.

These capabilities should not contain business-specific rules unless those rules are explicitly part of the platform.

## 3.2 Domain Models

Domain models define the concepts and relationships needed by a particular business capability.

Examples include:

- Program;
- Project;
- Contract;
- Product;
- Part;
- Supplier;
- Inventory Item;
- Work Order;
- Asset;
- Engineering Model;
- Requirement;
- Configuration;
- Financial Transaction.

The existing `prod/app/models` structure is an important part of the current prototype and should be evaluated as a possible mechanism for representing these domain models.

However, the architecture must not assume that every SQLAlchemy model is automatically a platform concept.

## 3.3 Business Configuration

The ERP should eventually allow the represented business to determine aspects of the domain configuration.

Configuration may determine things such as:

- available domains;
- available entity types;
- relationships;
- workflows;
- validation rules;
- organizational structures;
- required metadata;
- classifications;
- approval requirements;
- integrations.

The exact boundary between static code-defined models and dynamically configurable models remains an open architectural decision.

The architecture should therefore preserve the possibility without prematurely requiring every business concept to become dynamically configurable.

## 3.4 Business-Specific Extensions

Some organizations will require capabilities that are not appropriate for the core platform.

Extensions should allow organization-specific functionality without forcing those requirements into the platform itself.

Extensions may include:

- domain-specific models;
- custom validation;
- custom workflows;
- integration adapters;
- reports;
- UI components;
- specialized data transformations.

The extension mechanism must be designed so that extensions do not silently bypass platform controls such as validation, governance, authorization, or audit.

---

# 4. Applications

Applications should provide user-facing capabilities built on top of the platform and domain layers.

Examples may include:

- Program Management
- Engineering
- Logistics
- Procurement
- Contracts
- Finance
- Manufacturing
- Asset Management
- Configuration Management
- Document Management
- Reporting
- Data Administration

An application should not necessarily correspond one-to-one with a database schema or SQLAlchemy model package.

Applications represent **capabilities and workflows**, while domain models represent the underlying business concepts.

---

# 5. Central Organizational Record

The ERP's central database is intended to provide a common operating picture of the organization.

This means that the architecture should favor a coherent organizational data model over isolated application-specific databases.

However, "central database" does not mean every piece of data must be stored in one undifferentiated structure.

The architecture should distinguish:

- platform data;
- master data;
- transactional data;
- historical data;
- engineering data;
- documents;
- inbound artifacts;
- staging data;
- audit data;
- derived/reporting data.

The central database should provide relationships between these categories where those relationships have business meaning.

---

# 6. Inbound Data Architecture

Inbound data is not automatically authoritative.

The intended data lifecycle is:

```text
External / User Source
        |
        v
Inbound Artifact
        |
        v
Staging
        |
        v
Parsing / Transformation
        |
        v
Validation
        |
        v
Governance / Approval
        |
        v
Authoritative Organizational Data
```

This distinction is fundamental to the architecture.

## 6.1 Inbound Artifacts

Examples include:

- CSV files;
- spreadsheets;
- XML;
- JSON;
- MBSE packages;
- PLM exports;
- CAD metadata;
- CRM exports;
- vendor data;
- employee-submitted files.

The original artifact should be preserved when necessary to support auditability, validation, troubleshooting, or reconstruction.

## 6.2 Staging

Staging represents data that has entered the ERP ecosystem but has not yet become authoritative organizational data.

Staging should preserve sufficient information to determine:

- where the data came from;
- when it arrived;
- which artifact produced it;
- what schema/version was used;
- what validation occurred;
- what errors were identified;
- what governance decisions occurred.

## 6.3 Validation

Validation determines whether inbound data satisfies the structural and semantic requirements necessary for promotion.

Validation may include:

- file/schema validation;
- type validation;
- referential validation;
- domain validation;
- cross-record validation;
- business-rule validation;
- integrity validation.

## 6.4 Governance

Governance determines whether validated data may become authoritative.

Governance may involve:

- automated approval;
- manual approval;
- rejection;
- dispute;
- supersession;
- controlled correction.

The exact workflow varies by data domain.

## 6.5 Promotion

Promotion creates or updates authoritative organizational records.

Promotion must be traceable back to the originating data and governance decision where required.

---

# 7. Authoritative Data vs. External Systems

The ERP will integrate with systems such as:

- PLM;
- CAD;
- CRM;
- MBSE tools;
- vendor systems;
- other organizational systems.

Integration does not automatically imply ownership.

For every significant data concept, the architecture should identify:

- authoritative system;
- source system(s);
- ERP representation;
- identifier mapping;
- synchronization direction;
- synchronization frequency;
- conflict resolution;
- historical requirements.

The ERP should not duplicate authoritative external data merely because duplication is technically convenient.

Conversely, data required for the ERP's organizational operating picture should not remain inaccessible merely because another system originally authored it.

---

# 8. MBSE Architecture

MBSE is a major capability but is not the architectural definition of the ERP.

The MBSE domain should therefore remain internally coherent while integrating with the broader ERP.

The current MBSE work provides a concrete example of the kind of domain the architecture must support.

The existing MBSE model includes concepts such as:

- engineering models;
- model versions;
- object definitions;
- relationships;
- semantics;
- taxonomies;
- stereotypes;
- properties;
- source identifiers.

The MBSE schema also distinguishes repository UUIDs from source identifiers such as XMI identifiers.

These characteristics should remain domain-specific unless a broader ERP requirement justifies generalization.

## 8.1 MBSE Authoring

The ERP is not intended to replace MBSE authoring tools.

Instead:

```text
MBSE Authoring Tool
        |
        v
Export / Package
        |
        v
ERP Ingestion
        |
        v
Validation
        |
        v
Governance
        |
        v
MBSE Repository / Organizational Record
```

The architecture must support preservation of authored information while still allowing the ERP to establish relationships between engineering data and other organizational data.

## 8.2 Complex Artifacts

Simple files such as CSVs can often be validated through straightforward tabular schema validation.

Complex artifacts such as `.mpzip` packages may require:

- artifact inspection;
- package-level validation;
- extraction;
- internal schema validation;
- relationship validation;
- source-identifier preservation;
- version tracking;
- provenance tracking.

The architecture should therefore treat file ingestion as a general capability rather than designing exclusively around CSV.

---

# 9. Data Model Architecture

The database should use a structured relational model for authoritative organizational records.

PostgreSQL is the intended system of record.

The relational model should provide:

- stable identifiers;
- explicit relationships;
- referential integrity;
- uniqueness constraints;
- appropriate indexes;
- appropriate lifecycle constraints;
- historical traceability.

SQLAlchemy should represent the persistent domain model.

However, SQLAlchemy models should not become the sole architectural definition of the ERP.

The conceptual domain model, business rules, database schema, and API contracts should remain distinguishable.

---

# 10. History and Versioning

The ERP must be capable of understanding not only current state but how that state came to exist.

History may be implemented differently depending on the business meaning of the data.

Potential mechanisms include:

- immutable transactions;
- append-only records;
- versioned records;
- snapshots;
- audit records;
- event/history records.

Append-only storage is desirable where practical but is not an unconditional requirement for every table.

The correct mechanism should be determined by:

- business requirements;
- reconstruction requirements;
- performance;
- storage requirements;
- regulatory/audit requirements;
- lifecycle semantics.

---

# 11. Configuration Architecture

The ERP should eventually support configuration at multiple levels.

```text
ERP Platform
      |
      +-- Organization Configuration
      |
      +-- Domain Configuration
      |
      +-- Program Configuration
      |
      +-- User / Role Configuration
      |
      +-- Integration Configuration
```

The exact representation of configuration remains an architectural decision.

The architecture should avoid two extremes:

### Fully hard-coded ERP

Every organization requires source-code changes to represent its business.

### Fully dynamic low-code ERP

All behavior becomes metadata-driven and the system becomes a generic low-code platform.

The vision explicitly rejects the second approach.

The desired architecture is expected to lie between these extremes:

**stable platform + explicit domain models + controlled configuration + extensibility.**

---

# 12. Program as an Architectural Boundary

A Program is currently defined as a "sub-business" with its own lifecycle whose objective is to produce an item from procurement through sustainment.

This makes Program a potentially important organizing concept.

A Program may connect:

- contracts;
- projects;
- engineering;
- procurement;
- suppliers;
- manufacturing;
- inventory;
- assets;
- delivery;
- deployment;
- sustainment;
- financial information.

However, the exact relationship between:

- Organization;
- Program;
- Project;
- Product;
- Contract;
- Asset

has not yet been finalized.

The architecture should therefore treat Program as an important domain concept without prematurely fixing its complete relational structure.

---

# 13. API Architecture

APIs should expose business capabilities and platform capabilities rather than arbitrary database operations.

Examples might include:

- submit artifact;
- validate artifact;
- approve dataset;
- create program;
- update configuration;
- retrieve engineering model;
- create purchase order;
- receive material;
- associate an asset with a program.

API design should preserve domain boundaries.

The UI should consume the same underlying capabilities rather than implementing independent business logic.

---

# 14. UI Architecture

The UI should provide comprehensive visualization and interaction with organizational data.

The initial users are primarily non-technical.

Therefore the UI must make complex workflows understandable without requiring users to understand:

- database schemas;
- SQL;
- internal identifiers;
- validation engines;
- API implementation details.

However, technical users should have appropriate administrative interfaces for:

- data validation;
- governance;
- configuration;
- troubleshooting;
- integration;
- audit;
- system administration.

The UI must not become the location of core business rules.

---

# 15. Background Processing

The architecture should support asynchronous processing for operations such as:

- large file ingestion;
- artifact extraction;
- validation;
- data transformation;
- integration synchronization;
- reporting;
- scheduled processing.

Background operations must have observable states and appropriate failure handling.

A user should be able to determine whether a submitted operation is:

- received;
- processing;
- awaiting approval;
- completed;
- rejected;
- failed.

---

# 16. Integration Architecture

Integrations should be treated as explicit architectural boundaries.

Potential integration categories include:

- PLM;
- CAD;
- MBSE;
- CRM;
- vendor systems;
- financial systems;
- document systems;
- identity providers;
- data-lake systems.

Each integration should define:

- source;
- destination;
- ownership;
- identifier mapping;
- data contract;
- synchronization behavior;
- failure behavior;
- retry behavior;
- reconciliation;
- audit requirements.

Integration adapters should not bypass domain validation or governance.

---

# 17. Deployment Architecture

The system must be containerizable and on a path toward cloud readiness.

The initial architecture should therefore favor:

- containerized services;
- externalized configuration;
- persistent storage separated from application containers;
- reproducible deployments;
- migration-controlled database changes;
- observable background processing;
- explicit environment configuration.

Cloud deployment should be possible without requiring the domain model to be redesigned.

The architecture should not introduce distributed infrastructure merely for the appearance of cloud readiness.

---

# 18. Modularity

The ERP should be modular at the domain and capability level.

Modularity should provide:

- clear ownership;
- bounded dependencies;
- independently testable capabilities;
- controlled interfaces;
- ability to add capabilities without rewriting unrelated domains.

Modularity does **not** currently imply microservices.

The initial architectural preference is a modular monolith unless a concrete requirement demonstrates that a separate service is warranted.

---

# 19. Security and Governance

Security and governance are cross-cutting platform capabilities.

The architecture should distinguish:

- authentication;
- authorization;
- data ownership;
- workflow authority;
- governance;
- audit;
- classification.

Authorization should be enforced at the API/application boundary rather than relying on UI visibility.

Governance decisions must be traceable.

The existing MBSE concept of organization-governed classification should not automatically be generalized into a complete security-marking system without an explicit requirement.

---

# 20. Architectural Rules

The following rules should guide implementation.

1. The ERP is an organizational operating system, not merely a collection of CRUD applications.
2. PostgreSQL is the authoritative relational system of record for ERP-owned data.
3. Inbound artifacts are not automatically authoritative records.
4. Validation and governance occur before promotion where the data lifecycle requires them.
5. Original inbound artifacts should be preserved when required for provenance, audit, or reconstruction.
6. Business ownership must be distinguishable from technical storage.
7. Platform capabilities must not absorb arbitrary domain logic.
8. Domain models must not silently become platform-wide abstractions.
9. External-system integration does not automatically transfer ownership.
10. APIs expose capabilities rather than arbitrary persistence operations.
11. UI code must not contain core business rules.
12. Database constraints should enforce important invariants where practical.
13. Historical requirements must be considered when designing persistent entities.
14. Append-only storage should be used where business meaning justifies it.
15. Schema migrations must preserve existing data unless destructive behavior is explicitly approved.
16. Extensions must not bypass platform controls.
17. New domains should be developed through working vertical slices.
18. Architectural decisions should not be forced by incomplete domain requirements.
19. MBSE should remain a coherent domain without becoming the definition of the ERP.
20. The architecture should remain interoperable with external authoring and business systems.

---

# 21. Development Strategy

The architecture should be developed through vertical slices rather than attempting to completely specify every ERP domain first.

A representative progression may be:

```text
Platform Foundation
        |
        v
Inbound Artifact
        |
        v
Validation
        |
        v
Governance
        |
        v
Promotion
        |
        v
Authoritative Record
        |
        v
Domain Workflow
        |
        v
External Integration
        |
        v
Reporting / Analysis
```

MBSE can provide an early, relatively well-understood domain for proving these capabilities.

Other domains should initially be treated as architectural test cases rather than fully specified business models.

---

# 22. Architectural Decisions Still Required

The following decisions remain open and should be resolved through subsequent design work:

- How should business configuration be represented?
- How much should `prod/app/models` determine ERP configuration?
- Which model definitions are static and which may be dynamic?
- What is the exact boundary between platform models and domain models?
- What is the extension mechanism?
- What is the exact relationship between Organization, Program, Project, Product, Contract, and Asset?
- What data belongs in the data lake versus PostgreSQL?
- What is the exact promotion mechanism from staging to authoritative data?
- How should complex artifacts such as `.mpzip` packages be validated?
- How should external identifiers map to ERP identifiers?
- How should synchronization conflicts be resolved?
- Which records require append-only history?
- Which records require versioning?
- Which records are immutable transactions?
- What constitutes an auditable event?
- What is the initial cloud deployment target?
- Which capabilities should remain within the modular monolith and which, if any, eventually warrant independent services?

These decisions should be made incrementally as vertical slices expose concrete architectural requirements.

---

# 23. Architectural Boundary

This document defines the architectural shape of the ERP.

It does not define the final:

- domain schema;
- business configuration model;
- application UX;
- API contract;
- data-lake implementation;
- MBSE ingestion implementation;
- integration protocols;
- financial model;
- logistics model;
- program-management model.

Those belong to subsequent domain and implementation artifacts.

The purpose of this architecture is to establish the boundaries within which those future decisions can be made.
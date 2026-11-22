# ERP Domain Model

## 1. Purpose

This document defines the conceptual domain model for the ERP system.

The ERP is intended to function as an organizational operating system connecting:

- people
- organizations
- programs
- projects
- engineering
- products
- parts
- suppliers
- contracts
- resources
- transactions
- documents
- assets
- knowledge
- external systems

The domain model provides the conceptual vocabulary needed to reason about these areas without prematurely prescribing a particular database schema, API structure, UI, or implementation.

The model must support multiple organizations and business domains while allowing individual businesses to configure and extend the system.

The ERP should therefore distinguish between:

1. **Platform concepts**
2. **Organizational concepts**
3. **Business/domain concepts**
4. **Business-specific extensions**
5. **External and authored data**
6. **Operational transactions**
7. **Historical and audit information**

The domain model is expected to evolve as individual business domains become better understood.

---

# 2. Domain Modeling Principles

## 2.1 Domain concepts are not automatically database tables

A domain concept describes something meaningful to the organization.

It does not imply:

- one SQL table
- one API resource
- one UI page
- one Python class
- one workflow

The implementation may represent a concept using multiple relational entities, value objects, relationships, events, documents, or other structures.

Conversely, a database table should not automatically be treated as a business concept.

---

## 2.2 Stable concepts should be distinguished from configurable concepts

Some concepts are expected to be fundamental to the ERP platform.

Examples include:

- Organization
- User
- Role
- Program
- Project
- Document
- File
- Workflow
- Approval
- Version
- Audit record
- External identifier
- Integration
- Record provenance

Other concepts may vary significantly by business.

Examples include:

- Product
- Part
- Work Order
- Asset
- Requirement
- Configuration
- Purchase Order
- Inventory Item
- Engineering Model
- Financial Transaction

The system should provide stable platform mechanisms while allowing domain concepts and relationships to be configured or extended where appropriate.

---

# 3. Domain Layers

The conceptual domain is divided into several layers.

```text
ERP Platform
│
├── Identity & Organization
│
├── Governance & Workflow
│
├── Data & Provenance
│
├── Documents & Artifacts
│
├── Programs & Projects
│
├── Commercial & Contracts
│
├── Engineering
│
├── Products & Assets
│
├── Supply Chain & Logistics
│
├── Manufacturing & Work
│
├── Finance
│
└── External Integrations
```

These are conceptual boundaries rather than a mandatory module structure.

A domain may eventually span several of these boundaries.

---

# 4. Core Organizational Concepts

## 4.1 Organization

An **Organization** represents an organizational entity participating in the ERP.

An organization may represent:

- the ERP-owning organization
- a business unit
- a subsidiary
- a customer
- a supplier
- a partner
- another external organization

The exact organizational hierarchy remains an architectural decision.

An organization may participate in multiple programs, projects, contracts, transactions, and engineering activities.

---

## 4.2 Person

A **Person** represents an individual participating in organizational activities.

A person may:

- contribute data
- approve records
- manage programs
- perform engineering work
- perform logistics activities
- create documents
- participate in projects
- interact with external systems

A Person should not automatically imply an employee record.

Employment and workforce-management concepts may be added if required by the business.

---

## 4.3 User

A **User** represents an authenticated system identity.

A User may be associated with a Person and may possess:

- roles
- permissions
- organizational scope
- workflow authority
- data access

The domain model should distinguish:

```text
Person
   │
   └── User
```

because not every Person necessarily needs a system account.

---

# 5. Program

## 5.1 Definition

A **Program** is a major operational boundary within the organization.

A program represents a sub-business or coordinated organizational effort with a lifecycle whose objective is to produce, procure, deploy, operate, or sustain an item or capability.

The program concept is particularly important to this ERP because it provides an operational context around:

- contracts
- projects
- engineering
- procurement
- manufacturing
- logistics
- assets
- financial activity
- sustainment

---

## 5.2 Program is not necessarily a legal organization

A Program should not be assumed to be equivalent to:

- an Organization
- a legal entity
- a business unit
- a Project
- a Product

A program may involve several organizations and several projects.

The exact relationships among:

```text
Organization
Program
Project
Product
Contract
Asset
```

remain an architectural/domain decision.

---

# 6. Project

A **Project** represents a bounded body of work performed to accomplish a defined objective.

Projects may exist within programs and may support activities such as:

- engineering
- manufacturing
- procurement
- deployment
- testing
- sustainment
- infrastructure
- internal organizational work

A Project may consume:

- people
- materials
- money
- equipment
- facilities
- engineering resources
- supplier services

A Project may produce:

- products
- configurations
- documents
- engineering artifacts
- work results
- assets
- deliverables

---

# 7. Product

A **Product** represents something the organization produces, procures, manages, delivers, or sustains.

A product may be:

- physical
- software-based
- engineered
- configured
- assembled
- procured
- delivered as a capability

Products may be composed of Parts or other Products.

A Product may have:

- configurations
- revisions
- requirements
- engineering models
- suppliers
- contracts
- inventory
- manufacturing information
- lifecycle states
- associated assets

The exact product/part/configuration hierarchy remains open.

---

# 8. Part

A **Part** represents a component or reusable item associated with a Product or engineering/manufacturing process.

A Part may be:

- manufactured
- purchased
- stocked
- installed
- consumed
- replaced
- tracked through its lifecycle

Parts may have:

- part numbers
- revisions
- suppliers
- specifications
- inventory records
- engineering relationships
- configuration relationships

The distinction between Product, Part, Item, and Asset should be refined as the supply-chain and engineering domains are developed.

---

# 9. Asset

An **Asset** represents a managed instance of something that exists or is deployed in the operational world.

Examples may include:

- delivered equipment
- vehicles
- systems
- facilities
- serialized products
- installed components

A useful conceptual distinction is:

```text
Product
   │
   └── defines / describes a class of thing

Asset
   │
   └── represents an operational instance of that thing
```

The exact relationship between Product, Part, Configuration, and Asset requires further domain definition.

---

# 10. Configuration

A **Configuration** represents a defined combination or state of products, parts, engineering information, software, or other controlled items.

Configurations may be used to establish:

- what constitutes a product
- what revision is deployed
- what components are installed
- what engineering baseline applies
- what configuration was delivered
- what configuration is currently active

Configuration management is expected to overlap strongly with engineering and asset management.

---

# 11. Engineering Domain

Engineering is a major ERP capability but does not define the ERP as a whole.

The ERP should integrate engineering information with organizational and operational information.

Engineering data may include:

- requirements
- architecture
- models
- interfaces
- configurations
- baselines
- change records
- verification information
- technical documents
- engineering relationships

The ERP is **not intended to replace engineering authoring tools**.

Instead, it provides a governed organizational integration point for engineering information.

---

# 12. Engineering Model

An **Engineering Model** represents an externally authored or ERP-managed engineering model.

Examples include models originating from:

- MBSE tools
- SysML tools
- UML tools
- CAD/CAE tools
- PLM systems
- other engineering environments

The ERP should preserve the identity and provenance of externally authored model information.

An engineering model may contain:

- model elements
- relationships
- definitions
- instances
- configurations
- versions
- metadata
- source identifiers

---

# 13. Engineering Model Version

A **Model Version** represents a specific version or state of an Engineering Model.

Versioning is important because engineering information may change independently of ERP transactions.

The ERP should distinguish:

```text
Engineering Model
        │
        ├── Version 1
        ├── Version 2
        ├── Version 3
        └── ...
```

The relationship between engineering model versions and other ERP objects must preserve historical meaning.

For example, a relationship may legitimately connect objects belonging to different model versions when the domain requires it.

---

# 14. Requirements

A **Requirement** represents a condition, capability, constraint, or obligation that must be satisfied.

Requirements may originate from:

- customers
- contracts
- regulations
- engineering processes
- internal organizational decisions
- other systems

Requirements may be related to:

- products
- systems
- components
- configurations
- engineering models
- verification activities
- contracts
- programs

Requirements should retain provenance and lifecycle information.

---

# 15. Engineering Change

An **Engineering Change** represents a controlled modification to engineering or product information.

Changes may affect:

- requirements
- models
- configurations
- products
- parts
- documents
- assets

Changes may require:

- review
- approval
- impact analysis
- implementation
- verification

The exact change-management workflow remains to be defined.

---

# 16. Commercial and Contract Domain

## 16.1 Contract

A **Contract** represents a formal commercial or organizational agreement.

Contracts may relate organizations, programs, projects, suppliers, customers, products, services, and financial obligations.

A contract may contain or reference:

- clauses
- deliverables
- requirements
- milestones
- funding
- pricing
- obligations
- amendments
- supporting documents

---

## 16.2 Quote / Proposal

A **Quote** or **Proposal** represents a commercial offer or pre-contractual commitment.

A proposal may contain:

- products
- services
- quantities
- prices
- schedules
- assumptions
- terms
- supporting documents

The lifecycle may progress conceptually toward:

```text
Proposal
   ↓
Negotiation
   ↓
Contract
   ↓
Execution
```

The exact business workflow remains configurable.

---

# 17. Supplier

A **Supplier** represents an organization providing goods or services.

Suppliers may participate in:

- quotes
- contracts
- purchase orders
- manufacturing
- logistics
- inventory
- engineering
- sustainment

Supplier information should be reusable across programs and projects where appropriate.

---

# 18. Procurement

Procurement represents the acquisition of goods and services.

Relevant concepts may include:

- purchase request
- purchase order
- supplier
- item
- quantity
- price
- delivery requirement
- receipt
- inspection
- contract
- invoice

The procurement domain should connect commercial activity to logistics, inventory, projects, programs, and finance.

---

# 19. Supply Chain and Logistics

The supply-chain domain represents the movement and management of physical goods.

Concepts may include:

- supplier
- purchase order
- shipment
- receipt
- inventory
- warehouse
- location
- stock item
- serialized item
- lot
- transfer
- delivery
- return

The model should support traceability from procurement through receipt, inventory, deployment, and sustainment.

---

# 20. Inventory Item

An **Inventory Item** represents something managed within an inventory system.

Inventory may track:

- quantity
- location
- ownership
- status
- lot
- serial number
- source
- destination
- associated product or part

Inventory records should be distinguishable from the underlying Product or Part definition.

---

# 21. Work Order

A **Work Order** represents an authorized unit of operational work.

Work orders may support:

- manufacturing
- repair
- inspection
- maintenance
- engineering
- logistics
- deployment
- sustainment

A work order may consume or produce:

- labor
- materials
- equipment
- products
- parts
- documents
- financial resources

---

# 22. Manufacturing

Manufacturing represents the transformation of materials, components, labor, and engineering definitions into products or assemblies.

Manufacturing may depend on:

- Products
- Parts
- Configurations
- Work Orders
- Bills of Material
- Processes
- Resources
- Inventory
- Engineering changes

The manufacturing domain is intentionally not fully defined at this stage.

---

# 23. Finance

The ERP should track organizational financial activity relevant to programs and operations.

Potential concepts include:

- account
- budget
- funding
- expense
- revenue
- invoice
- payment
- cost
- forecast
- commitment
- financial transaction

The ERP is **not intended to replace a general-purpose accounting system**.

Instead, the ERP should provide financial information necessary to understand program and organizational activity and integrate with appropriate financial systems where required.

---

# 24. Document

A **Document** represents a managed information artifact.

Documents may include:

- contracts
- engineering documents
- specifications
- procedures
- reports
- invoices
- drawings
- exported models
- approvals
- other business records

A Document may have:

- versions
- owners
- classifications
- provenance
- associated domain objects
- approval status

---

# 25. File and External Artifact

A **File** represents the physical or logical artifact received by the ERP.

This distinction is important because the file itself may be different from the normalized organizational records derived from it.

For example:

```text
Vendor CSV
    ↓
Inbound File
    ↓
Staging Records
    ↓
Validated Records
    ↓
Authoritative ERP Records
```

The original file may need to be preserved for:

- audit
- traceability
- reprocessing
- dispute resolution
- provenance
- regulatory requirements

---

# 26. External Identifier

An **External Identifier** represents an identifier assigned by another system.

Examples include:

- vendor IDs
- XMI IDs
- PLM identifiers
- CAD identifiers
- CRM IDs
- accounting-system IDs
- source-system record IDs

External identifiers must not automatically replace ERP-native identifiers.

Conceptually:

```text
ERP UUID
    │
    ├── External ID: System A
    ├── External ID: System B
    └── External ID: System C
```

This allows ERP records to maintain stable internal identity while remaining interoperable with external systems.

---

# 27. Provenance

Every significant externally sourced or transformed record should be capable of retaining provenance appropriate to its domain.

Provenance may identify:

- source system
- source organization
- source file
- source record
- ingestion batch
- transformation
- validation
- approving authority
- timestamp
- originating version

Provenance is particularly important for engineering and externally authored information.

---

# 28. Data Lifecycle

The conceptual lifecycle of inbound organizational data is:

```text
External / User Source
        ↓
Inbound Artifact
        ↓
Staging
        ↓
Parsing / Transformation
        ↓
Validation
        ↓
Governance
        ↓
Approval
        ↓
Authoritative Organizational Data
        ↓
Operational Use
        ↓
History / Audit
```

Not every data type must follow exactly the same lifecycle.

However, externally sourced data should not silently become authoritative organizational data without appropriate controls.

---

# 29. Governance

Governance determines whether data is acceptable for organizational use.

Governance may include:

- validation
- review
- approval
- dispute
- rejection
- supersession
- authorization
- classification

Governance status should be distinguishable from ordinary operational status.

For example:

```text
Validation Status
Governance Status
Operational Status
Version Status
```

These concepts should not automatically be collapsed into a single generic `status` field.

---

# 30. Workflow

A **Workflow** represents an organizational process through which information or work progresses.

Examples include:

- data ingestion
- contract approval
- engineering change
- procurement
- manufacturing
- inspection
- asset deployment
- financial approval

Workflows should operate on domain objects rather than becoming the definition of the domain objects themselves.

---

# 31. Relationship Model

Relationships are first-class domain concepts.

Examples include:

```text
Organization ── participates in ── Program

Program ── contains ── Project

Program ── governed by ── Contract

Project ── produces ── Product

Product ── contains ── Part

Product ── instantiated as ── Asset

Product ── described by ── Engineering Model

Engineering Model ── has ── Model Version

Requirement ── applies to ── Product

Supplier ── provides ── Part

Purchase Order ── acquires ── Part

Inventory Item ── represents ── Part

Work Order ── produces ── Product

Document ── documents ── Domain Object
```

These are conceptual relationships and should not be interpreted as the final relational schema.

---

# 32. Cross-Domain Relationships

The ERP's value depends heavily on relationships crossing traditional business boundaries.

For example:

```text
Program
   │
   ├── Contract
   │      └── Supplier
   │
   ├── Project
   │      └── Work Order
   │              └── Product
   │                      └── Part
   │
   ├── Engineering Model
   │      └── Requirement
   │
   ├── Procurement
   │      └── Purchase Order
   │
   ├── Inventory
   │      └── Asset
   │
   └── Financial Activity
```

The domain model should make these relationships possible without requiring every domain to duplicate the concepts owned by another domain.

---

# 33. Domain Ownership

Each major concept should eventually have a clearly defined domain owner.

Ownership should identify:

- which domain defines the concept
- which domain may modify it
- which systems may contribute to it
- which system is authoritative
- which workflows govern it
- which relationships are valid
- which history must be preserved

For example, an engineering tool may be authoritative for engineering authoring while the ERP is authoritative for organizational associations and governance.

Authority must therefore be defined per data concept rather than assuming that the ERP owns every piece of information it stores.

---

# 34. External Systems

The ERP should integrate with systems such as:

- PLM
- CAD
- MBSE tools
- CRM
- accounting systems
- supplier systems
- manufacturing systems
- logistics systems
- scheduling systems
- data platforms

Integration should distinguish:

```text
Authoritative Source
        ↓
Integration
        ↓
ERP Representation
        ↓
ERP Governance / Use
```

Integration does not automatically imply that the ERP becomes the authoritative source for the originating data.

---

# 35. Business-Specific Extensions

The core domain model should support extensions for individual businesses.

An extension may introduce:

- domain entities
- attributes
- relationships
- validation rules
- workflows
- classifications
- reports
- integrations
- UI components

Extensions must operate through the ERP platform's:

- identity
- authorization
- validation
- governance
- audit
- versioning
- provenance
- integration

mechanisms.

A business-specific extension should not bypass platform controls merely because it introduces new domain concepts.

---

# 36. Configuration vs Extension

The ERP should distinguish between configuration and extension.

### Configuration

Configuration changes how an existing capability behaves.

Examples:

- workflow states
- approval requirements
- organizational classifications
- validation thresholds
- required metadata
- business-specific terminology

### Extension

An extension introduces capabilities or domain concepts that do not already exist.

Examples:

- new domain entities
- new relationship types
- specialized workflows
- external-system adapters
- specialized business logic

The boundary between configuration and extension remains an architectural decision.

---

# 37. Domain Model and `prod/app/models`

The existing implementation uses `prod/app/models` as the primary location for persistent domain models.

The architectural goal is not necessarily that every domain concept be dynamically generated from this directory.

Instead, the implementation should evolve toward:

```text
ERP Platform Concepts
        +
Explicit Domain Models
        +
Controlled Business Configuration
        +
Business-Specific Extensions
```

The exact degree to which `prod/app/models` determines runtime ERP configuration remains an open architectural question.

The domain model should therefore not assume that all business behavior is dynamically derived from ORM metadata.

---

# 38. MBSE as a Domain Example

MBSE currently provides the most developed domain model in the ERP prototype.

It should therefore be treated as:

1. a real ERP domain capability,
2. an example of external authored data integration,
3. an example of versioned domain information,
4. an example of complex source artifacts,
5. an example of cross-domain relationships.

It should **not** be treated as proof that the ERP is fundamentally an MBSE system.

The architecture must allow MBSE to coexist with:

- logistics
- procurement
- finance
- program management
- manufacturing
- contracts
- assets
- other future domains.

---

# 39. MBSE Data Boundary

The conceptual MBSE flow is:

```text
MBSE Authoring Tool
        ↓
Export / Package
        ↓
ERP Inbound Artifact
        ↓
Parsing / Extraction
        ↓
Validation
        ↓
Governance
        ↓
Engineering Model
        ↓
Model Version
        ↓
Engineering Objects / Relationships
```

The ERP should preserve externally authored information rather than silently altering its meaning.

Where transformation is necessary, the transformation should be explicit and traceable.

---

# 40. Complex Engineering Artifacts

Some engineering sources may arrive as simple files such as CSV.

Others may arrive as complex packages such as `.mpzip`.

The domain/integration model must therefore support artifacts that contain:

- multiple files
- internal relationships
- identifiers
- metadata
- version information
- model definitions
- references
- tool-specific information

Package ingestion should be treated as a domain integration problem rather than assuming that every inbound source is a flat table.

---

# 41. History and Versioning

The domain model must distinguish different meanings of historical information.

Potential mechanisms include:

### Versioned business records

Used when multiple meaningful versions of an object exist.

### Immutable transactions

Used when a business event must remain unchanged after recording.

### Audit history

Used to answer who changed what and when.

### Snapshots

Used to reconstruct a state at a particular point in time.

### Events

Used when the occurrence of an action itself has business significance.

These mechanisms should not be treated as interchangeable.

---

# 42. Common Operating Picture

The ERP's domain model should enable users to trace relationships across organizational activity.

For example:

```text
Customer
   ↓
Contract
   ↓
Program
   ↓
Project
   ↓
Engineering Change
   ↓
Product Configuration
   ↓
Procurement
   ↓
Supplier
   ↓
Inventory
   ↓
Asset
   ↓
Sustainment
   ↓
Financial Activity
```

The objective is not merely to store each record.

The objective is to preserve the relationships necessary to understand how organizational activity evolved over time.

---

# 43. Domain Boundaries

The following boundaries are currently proposed:

| Domain | Primary Responsibility |
|---|---|
| Organization | Organizational structure and participants |
| Identity | Users, roles, permissions |
| Programs | Program-level operational coordination |
| Projects | Bounded bodies of work |
| Commercial | Quotes, contracts, commercial obligations |
| Engineering | Engineering information and models |
| Products | Product and part definitions |
| Configuration | Controlled product/configuration states |
| Supply Chain | Suppliers, purchasing, inventory, logistics |
| Manufacturing | Production and work execution |
| Assets | Operational instances and lifecycle |
| Finance | Program/organizational financial information |
| Documents | Managed information artifacts |
| Governance | Approval and organizational authority |
| Integration | External system connectivity |
| Data | Inbound, staging, provenance, validation, history |

These are working boundaries, not finalized module definitions.

---

# 44. Open Domain Decisions

The following decisions remain intentionally unresolved.

## Organization and hierarchy

- What is the exact Organization hierarchy?
- How do organizations relate to business units?
- Can a Program cross organizational boundaries?
- How are customers and suppliers represented?

## Program structure

- What exactly distinguishes Program from Project?
- Can a Project exist outside a Program?
- How do Programs relate to Contracts?
- How do Programs relate to Products and Assets?

## Product structure

- What is the precise distinction between Product, Part, Item, and Asset?
- How are assemblies represented?
- How are revisions and configurations related?

## Engineering

- Which engineering concepts belong in the ERP core?
- Which should remain external?
- How should MBSE models relate to Products and Configurations?
- How should externally authored model versions interact with ERP versions?

## Configuration

- What constitutes a Configuration?
- Is configuration management a platform capability or an engineering/domain capability?
- How are configurations associated with Assets?

## Finance

- Which financial concepts should be represented natively?
- Which should remain in an external accounting system?
- What is the ERP's authoritative boundary for financial data?

## Data governance

- When does staged data become authoritative?
- Which data requires manual approval?
- Which data can be automatically promoted?
- How should disputed records be represented?

## Extensions

- Which concepts are configurable?
- Which require code-level extensions?
- How are extensions versioned?
- How are extension dependencies governed?

## External systems

- How is authoritative ownership assigned?
- How are conflicts resolved?
- How are external IDs mapped?
- How is synchronization history preserved?

---

# 45. Domain Modeling Rules for Future Development

Future domain modeling should follow these rules:

1. Do not create a domain entity solely because a UI screen needs it.
2. Do not create a database table solely because an external file contains a column.
3. Do not duplicate an existing platform concept inside a domain.
4. Do not assume an external system's data model is the ERP's domain model.
5. Preserve external identifiers separately from ERP-native identifiers.
6. Preserve provenance for externally sourced information.
7. Define authoritative ownership explicitly.
8. Keep domain relationships explicit.
9. Separate business status from governance status.
10. Separate operational state from historical state.
11. Prefer explicit domain models over unrestricted dynamic schemas.
12. Allow controlled configuration where business variation is expected.
13. Allow extensions where configuration is insufficient.
14. Do not let extensions bypass platform governance.
15. Do not prematurely finalize domains whose requirements are not yet understood.
16. Use working vertical slices to validate domain boundaries.
17. Treat MBSE as a developed domain example rather than the definition of the ERP.
18. Preserve enough history to reconstruct meaningful organizational state.
19. Favor interoperability over proprietary representations.
20. Keep the conceptual domain model independent of any single UI or implementation technology.

---

# 46. Current Domain Model Maturity

The domains are not equally mature.

### Relatively developed

- MBSE / Engineering
- Engineering Model
- Model Version
- Engineering objects and relationships
- Inbound data
- Validation
- Governance
- Provenance

### Partially defined

- Programs
- Projects
- Products
- Parts
- Contracts
- Suppliers
- Assets
- Inventory
- Procurement
- Documents
- Configurations
- Financial information

### Future refinement

- Manufacturing
- Detailed logistics
- Detailed accounting integration
- Workforce management
- Advanced scheduling
- Customer relationship management
- Additional business-specific domains

The implementation should reflect this maturity rather than pretending that every domain has already been fully specified.

---

# 47. Domain Model Objective

The final objective of the domain model is to provide a coherent representation of organizational activity across business boundaries.

The ERP should make it possible to answer questions such as:

- What program does this asset support?
- Which contract funded or authorized this activity?
- Which project produced this product?
- Which engineering configuration defines this asset?
- Which supplier provided this part?
- Where did this inventory originate?
- Which requirements apply to this configuration?
- Which changes affected this product?
- Who approved the relevant information?
- What was the state of the organization at a previous point in time?
- Which external system supplied the original information?
- What organizational events led to the current state?

The domain model therefore exists to support the ERP's broader purpose:

> **Provide a common operating picture of organizational activity by connecting people, programs, engineering, products, resources, transactions, and knowledge while preserving provenance, governance, and history.**
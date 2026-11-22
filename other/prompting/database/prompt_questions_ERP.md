# 1. What does “configuration” actually control?

Configuration controls the engineering diagrams of the product that the program within the organization produces. The main file type that is expected to come from configuration/mbse are mdzip, xmi, and jsons. 

This is almost one-to-one with engineering in this case.

# 2. What is the authoritative ownership model for data?

That is decided by the governance board. Typically, there is only going to be one model delivered. Engineering models are build in PLM, but are expected to be stored as ASOT in the ERP. The ERP draws from HR to get employee data. It should be optional to include all employee data (let's say that it's ASOT in the ERP to for sake of agrument)

# 3. What exactly is the “program” boundary?

```Organization → Program → Project → Product → Asset``` is a correct "heirarchy". Programs generate contracts, engineering models, control inventory, generate/process workorders, track finances. The organization also needs to track these things across programs. 

**The program is the primary boundary that aggregates everything associated with delivering a product or capability.**

# 4. History:

Contract
    └── versioned revisions

Inventory transaction
    └── immutable transaction history

Engineering model
    └── imported model versions

Governance decision
    └── immutable decision/audit record

Supplier address
    └── current state + historical changes

Derived KPI
    └── reproducible calculation/history

# 5. Data Lifecycle

- Is the original file always retained?: That should be retained in the data lake.
- Is staging mutable?: Once a file is staged, it's staged. If there needs to be a change, then it should be staged again and tracked as a different version.
- Can invalid records coexist with valid records from the same batch?: Files with invalid records should be logged as invalid, and then the submitter of the invalid record should be notified as to why their submission was invalid. 
- Does validation produce a versioned validation result?: Yes
- Can humans modify staged data?: Yes
- Can governance approve individual records or only batches?: At first batches, but have the capability to approve files and records if needed. 
- Does approval promote the exact validated representation?: Goverance approval = promotion.
- What happens when an authoritative record already exists?: This is where append-only comes in. We can track that authoritative records are updated. This is why the governance prorcess exists, to flag that these events occur. 
- How are corrections handled?: In the final state, there are tiered correction processes handled by scripting, governance, data mangagers, and then the users that submitted the changes. 
- Can an imported artifact be reprocessed using a newer schema?: Yes, but that's a later priority.
- What happens when an external source changes or retracts information?: Data engineers and the governance board need to be notified of the change in status. 
# Inventory System
## Question List
### Question 1: What is an inventoriable item?
- Can multiple items exist?
- Indexed by location in the garage?

All of these factors influence the structure.

### Question 2: Where are barcodes going to be used?
- Barcode: Visual scannable image
- SKU: Internal company code to track inventory
- UPC: A global standard, 12-digit number used by all retailers to ID a product (GS1 Standardized)
- Internal Labels

This directly influences how items are labeled. Scanners transfer a barcode/label to a computer as a set of numbers,for example: 1234567890913. Therefore, the look-up system needs to be known.

### Question 3: What device to use:
Answer: Wireless Barcode Scanner. Additionally, label makers may exist. 

### Question 4: What are the additional outputs of the inventory?
#### Projections:
- Should there be just-in-time scheduling?
- Phone notification system?
- Analysis of inventory levels (trending items, regular patterns)?
- What is the inventory used for?
- Report price changes to items (if looked up via UPC)
#### Status:
- Should there notifications for movement, reception/consumption, low stock?
- Track total cost?
    - By item
    - By date-range
    - All sortable?
- Report movement history?

### Question 5: What should the database look like?
Suggestion:
| product name | category | brand | description | date entered  | company | barcode id | product id | 
| - | - | - | - | - | - |- | - | 
|tomato|produce|brand 1|it's red and food| 28/06/2026 1450:59:30.123 EST | my company| 1234567890913|000000123|
| - | - | - | - | - | - | - |- | - | 
| - | - | - | - | - | - | - |- | - | 
| - | - | - | - | - | - | - |- | - | 
| - | - | - | - | - | - | - |- | - | 

**IMPORTANT:** Work that will be required by me to you will be the cataloging of every item in the system. They will not inherently exist (potentially, but certainly for printed labels). In my research, the standard way to address this is my looking at the all available barcode databases first, and then relying on the user to specify a barcode if needed. This means that we'll have our own separate database of items. *We will have to construct our own database of household items*.
### Question 6: What inventory options do you want available?

| Option | Action | 
|------- | ------ |
|Receive | Add  | 
|Consume  | Remove |
|Move    | A -> B|
|Audit   | Start/Add to count|
|Adjust  | Correct levels |

### Question 7: What permissions exist?

- Does everyone in the family get to use this?
- Parent vs child user differences?
- Everyone has the same level of access? 
- Guests use inventory system?

### Question 8: What technology do you already have?
- Mac vs Windows vs Linux?
- iPhone vs Android?
- Home alerting systems?
- Existing automated devices/home manager?

## Logging Design
Scan --> Local Lookup --> Miss? --> API Lookup (e.g., OpenFoodFacts) --> Store Result

The inventory is not updated directly, it's updated through capturing the events associated with the barcode scanning. 

## Project Meta-Design:
### Step 1: Enumerate Potential Materials / Understand the Depth of the Project
Q: What do you want? (What is the whole wishlist/vision)  
This allows me to get a complete list of items that are required, i.e., are there multiple types of scanners that are required? Should there be a scanner that allows for multiple settings, or just a barcode transfer system? 
### Step 2: Backend Creation 
This is where most of the solo work comes in. 
- Develop concept: Scanner --> database --> source code --> public database --> webpage/application --> inventory --> webpage/application 
- Ops system: SQLite (database) --> transaction ledger --> user --> location --> reporting/database
- Scale: Application --> Integration with label printing? --> Analysis/Forecasting --> Reordering
### Step 3: Testing/Reconfiguration 
There will be bugs for the first deployment. The key will be to start small, prove that it works and begin to scale. 
### Step 4: Feature Incorporation  
We don't need a full-blown mega system right out of the box. We need to create the basic design, implement it, and improve on it overtime with continuous updates. 
### Improvement Plan:
1) **Create the initial product** on a small set of test items. This will be locally tested and verified on my own equipment to ensure that a working model exist. I may ask for some barcoded items, ask for printed labels, and/or use my own to determine that a working model can exist and be tracked.  
At this stage, the "product" is a glorified database, tracking barcode scanned events, and logging them into a table. Iteration of this looks like:  
    Version 0.1.0) Logging barcode scans: Thing $x$ was scanned at time $t \rightarrow$ Table entry  
    Version 0.2.0) Multiple types of entries: Add/Remove/Correct --> accurately account for items in the house and their movement in and out of inventory  
    Version 0.3.0) Return a displayable event table  
    Version 1.0.0) Return a dynamic inventory document --> ***USER GET THE version 0 PRODUCT HERE*** 
2) **Create the user interface** so that there can be front-end interaction, i.e. manipulation of the inventory without having to go through code/documentation.  
Version 1.1.0) Transition from xlsx to SQLite  --> version 0.1.0  
Version 1.2.0) Create an application framework (Streamlit, React, Vue) to move to software  
Version 1.3.0) Enable user inputs (to manually add/change entries to the inventory or catalog)  
Version 1.4.0) Enable changes/bug-reports/update requests  
Version 2.0.0) Allow easy access to all information, including to solve system problems 
3) **Create** the application from the user interface. This is the "full" deployment of the application --> Version 3.0.0


## Andrew's Self Question List:

- How should the database be constructed? 
    - SQLite? PostgreSQL? accessability concerns?
- What should the software stack look like?
    - Languages, dependencies?
    - Frontend: Streamlit, React, Vue?
        - Application vs xlsx vs .exe
- How should events be captured?
    - What distinguishes an "source" event from a "sink" event?
    - How are the inventory actions initiated? 

### Barcode DBs:
- [Open Food Facts](https://world.openfoodfacts.org/)
- [UPCitemdb](https://www.upcitemdb.com/)
- [Barcode Lookup](https://www.barcodelookup.com/)
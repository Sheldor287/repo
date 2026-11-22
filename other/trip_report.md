# NAVWAR TRIP NOTES:
## BLUF:

Multiple stakeholders across the joint force have come together to unify our data, models, and analytics. The large initiative will meet monthly online, and quarterly in person. A smaller, concentrated group will create unified data schema for models, analytics, and our PMOs. _This trip is strongly categorized as a successful trip._ Future success depends on the level of future engagement at the joint level. 


## Overview:
NLCC (NMCS is a part of NLCC), NEC, MITRE (w/ NEC), JHU (w/ NEC), Navy, and AFNWC held a three day meeting group to discuss data alignment. The majority of stakeholders were MBSE focused, but there were overlapping regions of interest that included database work and analysis. To discuss how each of the services operate with each other, the NEC "introduced" Garth's enterprise Tier List:

- Tier 5: The enterprise level (NLCC)
- Tier 4: The joint level (NEC)
- Tier 3: The service level (AFNWC, NAVWAR)
- Tier 2: The platform level (latitude/longitude/SWaPC: Size, Weight, Power, and Cost)
- Tier 1: The system level (the top-level devices within a platform)

### Takeaways:

All groups within the community left united on the following points:

0. The stated goal of the data group is to provide a highly unified data schema so that we can conduct high-fidelity war-gaming and simulation on our architecture with the same model, data, and simulation framework. 
    - COA: A joint, cross service data modernization working group is being stood up to align our technical efforts. 

1. It is irrational for each service and level to conduct the same modeling and data work independently.
    - COA: All groups are going to build a single, unified database to house our data. 

2. All of the service models needed to be integratable.
    - COA: All the service's models (AF, NAVY, DISA) are going to be mapped to a canonical hierarchy. (i.e. common terminology for CE, CEV, CS)

3. Between all services, it makes no sense to have siloed data or analysis. Modernization and unity analysis is also important.
    - COA: We are standing up a cross-service repository. A subset of that repo will cover analysis.
    - FYSA: JHU-APL, NAVY, and ASEMIT/NCW all concur that the existing analysis frameworks need maturity. JHU is requesting $1.2M in funds to provide a complete analysis framework. Enabling JHU with those funds would be a waste of dollars. ASEMIT/NCW, NAVY/FUTURES, and NLCC have the capability to collaborate to get a mature methodology together, without the trade-off of additional man-hours. All three "branches", with verbal-okays from the NEC architecture group, are in alignment for the framework of the methodology. 

## Service Component Strengths and Weaknesses:

| Category | NLCC | NEC | NAVY | AF |
|-|-|-|-|-|
| Data Model Depth| Router | Comm system | Circuit | CI |
| Main Data Authoring Tool | Cameo | Cameo  | Cameo | Cameo|
| Data Storage Scheme| Neo4j| NEAR | WDP | Neo4j |
| Lead Capability Intigrator| No | No | Yes| No |
| Modernization 'Rank'| 2 | 3 | 1| 4 |
| Biggest Gap(s) | Data Disipline | Taxonomy Alignment | Scalability, PMO Support| Model Depth, Staff to Modernize |

### Rank Justification:
The Navy has systems in place, tools, and staff that can utilize those tools to get a comprehensive picture of their systems. Their models are the most advanced, have a unified and firm grasp on how data operations need to progress, and are delivering at the highest rate. 

The NLCC has a well developed tech stack and developers to move forward and increase the level of capability. To contrast, in NCW, we utilize our devs to meet requirements that non-technical stakeholders set. At the NLCC, the technical portions of the workforce are setting their requirements for their tech stack. 

The NEC is a large organization that's only looking at things from the top down. Even though there is a large staff, they are still consolidating their toolset and the databases together. 

The AF does have a set of developers and has a grasp of how we want to modernize. Our biggest hurdles are the lack of existing PMO support, the lack of utilization of a database outside the GRM, and the modernization gap between the PMOs and NCW. We have made consistent progress in modernizing our processes through new hires, gaining additional skillsets, learning how to code (as a division). There is still dispersion on where modernization is and where it is occuring. All said, we are on the right path and need to lean into the fact that we're in a different information and skillset paradigm.

### Methodology Details:

The NAVY in day 1 of the event proposed a set of recommendations to the MWA process for it to reach maturity. In simple language, the current methodology is taking a roll-up of measurements and trying to use the architecture to "un-roll" the measurements. For example, monthly Ao is a roll-up of the state of systems, and therefore omits context of the architecture-wide status at any particular point in time. The new approach seeks to look at the complete architecture at all points in time, and then perform analysis at the scale the analysis requires. If Tier1 models need to be analyzed, we have all of the measurements, so that analysis can be done. If Tier2 models need to be analyzed, we have all of the measurements, so that analysis can be done. If Tier 3,4, or 5 need to be analyzed, because we have all of the measurements at all points in time, instead of rolling them up, we get a fully accurate picture of the weapon system. This is the rationale and justification for the changes. 

#### Recommended Plan for a Path Forward (Methodology):
The existing analyst team should function and deliver their products without interruption. The new joint IPT begins formalizing and testing the methodology as we integrate data; the two efforts align together tightly enough for it to function as a single LOE, with minimal added time. As the IPT refines what data is needed and how it should be applied, changes can be integrated into the existing analysis. By this point in time, ASEMIT/NCW should have access to the top-level production stack on NECTAR to be able to make those changes. The digital ACQ team is back-filled on the changes, and then the joint IPT can test how the methodology impacts past results. 

# Overall Path Forward:

- Integrate with joint NC3 at the technical level in small groups.
    - Work in the same space.
    - Large groups and a large number of stakeholders involved leads to diminishing returns. 
    - Meet for a short period of time (15-30minutes) per week to ensure alignment.

- Each Service contributes their strengths to ensure robust digital products.
- All services work together to create a joint canonical meta-model. 
- NEC provides dispute resolution between the NAVY and AF. 
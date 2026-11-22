# ERP Vision

## Purpose

This ERP is intended to be a central database for all records of an organization. It should help manage the lifecycle of engineering, logistics, contracts, financials, and programmatics across multiple programs.

The system should support the lifecycle from proposal and contracting through project execution, engineering, procurement, manufacturing, delivery, deployment, and sustainment.

The intent is to modernize and track actions that are critical to the organization so that the history of any program can be tracked and analyzed because there is a common operating picture of the events that occur.

## Primary Users

Primary users include:

- Finance
- Program Managers
- Engineers
- Logistics Managers
- System Administrators
- Executives

Other users include:

- IT administrators
- Data engineers and analysts
- Developers
- Other technical users

The initial target is users who are, strictly speaking, non-technical. These users should be able to contribute to the ERP through their files while following a strict validation and governance process for which they will be trained.

The system therefore needs to provide a controlled path from user-authored files to validated, governed organizational data.

## The Business

The ERP should allow controls/configuration to specify the specific business being represented.

The main configuration of the ERP is expected to be determined, in large part, by the models within `prod/app/models`.

Additional extensions will likely be required to generalize the ERP so that different businesses can adopt the system without requiring the core architecture to be rebuilt.

The ERP should therefore distinguish between:

- core platform capabilities;
- business/domain configuration;
- business-specific extensions;
- organization-specific data.

## Definitions

### Program

A **Program** can be thought of as a "sub-business" with its own lifecycle whose objective is to produce an item from procurement through sustainment.

A Program is therefore an important organizational and operational boundary, but it is not necessarily the same thing as the overall business or legal organization.

## Capabilities

The ERP should provide capabilities for the following areas.

### Commercial and Financial

- Track quotations.
- Track contracts.
- Track spending and other monetary functions.
- Track accounts.
- Track billing.
- Track payments.
- Track cost accounting.
- Track projections and related financial information.

The ERP is not intended to be a general-purpose accounting platform, but it must be capable of tracking the financial information required to understand the lifecycle of organizational programs.

### Projects and Operations

- Track projects.
- Track work orders.
- Track resources.
- Track manufacturing.
- Create and display scheduling information such that the schedule is integratable with a database.

### Supply Chain and Logistics

- Track suppliers.
- Track purchasing.
- Track reception/receiving.
- Track inventory.
- Track other logistics functions.
- Track the supply chain throughout the lifecycle of a program.

### Engineering

- Hold MBSE engineering models.
- Hold engineering configurations.
- Track engineering change management.
- Support integration of different types of engineering models into a unified framework.

The ERP is **not** intended to be an engineering modeling/authoring environment. Engineering authoring tools remain important sources of data.

The database must provide a controlled means of storing and integrating the data produced by those tools.

## Scope and Role of MBSE

MBSE is important to the ERP, but it is not absolutely the most important element.

The relationship between the broader ERP and MBSE is currently an architectural unknown. The existing ERP prototype therefore revolves heavily around MBSE because the requirements for that capability are currently the most specific and developed.

MBSE authoring tools are expected to be one of the primary ways data is authored.

Integration between those authoring tools and the database is therefore critical. Data authored within MBSE tools should be preserved rather than silently changed by the ERP.

A CSV file is relatively straightforward to validate. An MBSE package such as an `.mpzip` file is less obvious to validate. The ERP architecture therefore needs to support increasingly complex inbound artifacts while maintaining controlled validation and governance.

The current MBSE work is more scoped than the other ERP domains because its data requirements are better understood.

## What the ERP Owns

The ERP owns the organizational data required to facilitate the development and procurement of assets from external vendors.

The system therefore needs to track:

- vendors;
- suppliers;
- products;
- parts;
- contracts;
- configurations;
- inventory;
- financial information;
- documents;
- requirements;
- assets.

Employees within the organization will contribute data to the system. The architecture should therefore support the relationship between data authors and the data they contribute, including appropriate validation and governance.

The ERP is expected to integrate with external systems including:

- PLM;
- CAD;
- CRM;
- other organizational data sources.

The overall vision is:

> **ERP = an organizational operating system
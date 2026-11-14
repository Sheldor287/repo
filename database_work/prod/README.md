# Production Stack:

| Component | Software/Tool | 
| - | - |
| API | FastAPI|
|UI | Jinja2/HTMX|
|Database|PostgreSQL|
|Schema Validation|Pydantic/JSON|
|CSV|Pandas|
|Object Relational Mapping | SQLAlchemy|
|Database Migration|Alembic|
|Background Processes|Celery/RQ/Arq|
|File Storage|Local Volume --> S3|
|Container|Docker|
|Reverse Proxy|Nginx/Caddy|
|Auth|TBD|

## Schema:
Defined up front via contract\JSON schema. 

## Process:
Schema --> (JSON/CSV) --> Validation 
- IF Valid: Staging
- ELSE: Quarantine

## Metadata:
### Logs:
- batch_id
- source
- filename
- filetype
- received_at
- schema_version
- record_count
- valid_count
- invalid_count
- status

### Record:
- record_id
- batch_id
- source_record_id
- raw_data
- validation_status
- validation_errors

### Goverance Process:
PENDING --> APPROVED/DISPUTED
- IF DISPUTED: --> PENDING/REJECTED
- ELSE: APPROVED --> SUPERSEDED

### Goverance Records:
- decision_id
- element_id
- status
- decision
- decision_by
- decision_datetime
- reason_code
- comments

## SysML:

Element: 
    - Source
        - File/batch
        - Timestamp
    - Schema 
        - Version
    - Governance
        - Decision --> User --> Reason


## Notes:
### Potential Frontend:
React --> FastAPI --> PostgreSQL

### Initial:
Browser --> FastAPI --> Jinja2, HTMX, PostgreSQL

### Considerations:
- Quarantine S3 instead of DB
- S3 file archive

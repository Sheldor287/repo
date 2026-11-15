import enum

class GovernanceStatus(str, enum.Enum):

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class RecordType(str, enum.Enum):

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ValidationStatus(str, enum.Enum):

    DRAFT = "DRAFT"
    UPLOADED = "UPLOADED"
    PARSED = "PARSED"
    VALIDATED = "VALIDATED"
    INVALID = "INVALID"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

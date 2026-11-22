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
    # Retained for reading legacy CSV rows; new domain batches keep governance
    # and promotion state in their own columns.
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PromotionStatus(str, enum.Enum):

    NOT_PROMOTED = "NOT_PROMOTED"
    PROMOTED = "PROMOTED"
    FAILED = "FAILED"

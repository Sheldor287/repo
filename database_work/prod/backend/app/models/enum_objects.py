import enum

class GovernanceStatus(str, enum.Enum):

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class RecordType(str, enum.Enum):

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData, Uuid, Text, Enum, DateTime
from uuid import UUID, uuid4
from datetime import datetime, timezone
import enum


class Base(DeclarativeBase):

    uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    classification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class GovernanceStatus(str, enum.Enum):

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class GovernanceBase(Base):
    __abstract__ = True

    governance_status: Mapped[GovernanceStatus] = mapped_column(
        Enum(GovernanceStatus, native_enum=False),
        default=GovernanceStatus.DRAFT,
        nullable=False,
    )

    last_update_for_governance: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    last_governance_review: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )


class MBSE(Base):
    __abstract__ = True
    metadata = MetaData(schema="mbse")


class Logistics(Base):
    __abstract__ = True
    pass


class Finance(Base):
    __abstract__ = True
    pass


class Programmatics(Base):
    __abstract__ = True
    pass


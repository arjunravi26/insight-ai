from datetime import datetime, timezone
from database.database import Base
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    JSON,
    UniqueConstraint,
    Index
)
import uuid


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    status = Column(
        String(30),
        nullable=False,
        default="QUEUED"
    )
    created_at = Column(DateTime(timezone=True),
                        default=utc_now, nullable=False)


class Job(Base):

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Internal documents.id, not the public UUID document_id.
    document_record_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=True
    )

    job_type = Column(String(30), nullable=False)

    status = Column(
        String(30),
        nullable=False,
        default="PENDING"
    )

    attempts = Column(Integer, nullable=False, default=0)

    max_attempts = Column(Integer, nullable=False, default=3)

    payload = Column(JSON, nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    started_at = Column(DateTime(timezone=True), nullable=True)

    completed_at = Column(DateTime(timezone=True), nullable=True)

    available_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    locked_until = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_jobs_status_available", "status", "available_at"),
        Index("ix_jobs_user_created", "user_id", "created_at"),
    )


class IdempotencyKey(Base):

    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    operation = Column(
        String(50),
        nullable=False
    )

    idempotency_key = Column(
        String(128),
        nullable=False
    )

    request_hash = Column(
        String(64),
        nullable=False
    )

    status = Column(
        String(30),
        nullable=False,
        default="IN_PROGRESS"
    )

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=True
    )

    response_status = Column(Integer, nullable=True)

    response_body = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    __table_args__ = (

        UniqueConstraint(
            "user_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_user_operation_key"
        ),

        Index(
            "ix_idempotency_expires_at",
            "expires_at"
        ),

    )

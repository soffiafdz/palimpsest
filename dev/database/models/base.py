"""
Base Classes and Mixins
------------------------

Foundational ORM classes for the Palimpsest database.

Classes:
    - Base: Declarative base for all SQLAlchemy models
    - SoftDeleteMixin: Mixin providing soft delete functionality

This module provides the core infrastructure that other model modules build upon.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import datetime, timezone
from typing import Optional

# --- Third party ---
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# --- Base ORM class ---
class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Serves as the declarative base for SQLAlchemy models and provides
    access to the metadata object for table creation and migrations.
    """

    pass


# --- Soft Delete ---
class SoftDeleteMixin:
    """
    Mixin providing soft delete functionality for models.

    Soft delete allows records to be marked as deleted without actually
    removing them from the database, preserving historical data and
    enabling recovery if needed.

    Attributes:
        deleted_at: Timestamp when the record was soft deleted
        deleted_by: Identifier of who deleted the record
        deletion_reason: Optional explanation for the deletion
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Timestamp of soft deletion"
    )
    deleted_by: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="User or process that deleted the record"
    )
    deletion_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Reason for deletion"
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(
        self, deleted_by: Optional[str] = None, reason: Optional[str] = None
    ) -> None:
        """
        Mark record as soft deleted.

        Args:
            deleted_by: Identifier of who is deleting the record
            reason: Explanation for the deletion
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by
        self.deletion_reason = reason

    def restore(self) -> None:
        """Restore a soft deleted record."""
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None

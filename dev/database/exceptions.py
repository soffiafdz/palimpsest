#!/usr/bin/env python3
"""
exceptions.py
--------------------
Custom exception classes for the Palimpsest database system.
"""


class DatabaseError(Exception):
    """Base exception for database-related errors."""

    pass


class BackupError(DatabaseError):
    """Exception for backup-related errors."""

    pass


class HealthCheckError(DatabaseError):
    """Exception for health check failures."""

    pass


class ExportError(DatabaseError):
    """Exception for export operations."""

    pass

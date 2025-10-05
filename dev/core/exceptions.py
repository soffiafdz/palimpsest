#!/usr/bin/env python3
"""
exceptions.py
--------------------
Custom exception classes for the Palimpsest project.
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


class TemporalFileError(Exception):
    """Exception for temporal file operations."""

    pass


class ValidationError(Exception):
    """Exception for validation errors."""

    pass


class Sql2YamlError(Exception):
    """Exception for SQL to YAML conversion errors."""

    pass


class Yaml2SqlError(Exception):
    """Exception for YAML to SQL conversion errors."""

    pass


class PdfBuildError(Exception):
    """Exception for Md to PDF conversion errors."""

    pass

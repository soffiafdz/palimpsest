#!/usr/bin/env python3
"""
exceptions.py
--------------------
Custom exception classes for the Palimpsest project.

Exception Hierarchy:
    PalimpsestError (root)
    ├── DatabaseError
    │   ├── BackupError
    │   ├── HealthCheckError
    │   └── ExportError
    ├── ConversionError
    │   ├── Txt2MdError
    │   ├── Yaml2SqlError
    │   └── Sql2YamlError
    ├── BuildError
    │   ├── PdfBuildError
    │   └── TxtBuildError
    ├── ValidationError
    ├── TemporalFileError
    └── EntryError
        ├── EntryValidationError
        └── EntryParseError
"""


# ----- Root Exception -----


class PalimpsestError(Exception):
    """
    Base exception for all Palimpsest errors.

    All custom exceptions in the project inherit from this base class,
    allowing code to catch any Palimpsest-specific error with a single
    except clause if needed.
    """

    pass


# ----- Database Exceptions -----


class DatabaseError(PalimpsestError):
    """Base exception for database-related errors."""

    pass


class BackupError(DatabaseError):
    """Exception for backup and restore operations."""

    pass


class HealthCheckError(DatabaseError):
    """Exception for health check failures."""

    pass


class ExportError(DatabaseError):
    """Exception for database export operations."""

    pass


# ----- Conversion Exceptions -----


class ConversionError(PalimpsestError):
    """Base exception for conversion pipeline errors."""

    pass


class Txt2MdError(ConversionError):
    """Exception for txt-to-markdown conversion errors."""

    pass


class Yaml2SqlError(ConversionError):
    """Exception for YAML-to-SQL (markdown to database) conversion errors."""

    pass


class Sql2YamlError(ConversionError):
    """Exception for SQL-to-YAML (database to markdown) conversion errors."""

    pass


# ----- Build Exceptions -----


class BuildError(PalimpsestError):
    """Base exception for build operation errors."""

    pass


class TxtBuildError(BuildError):
    """Exception for source-to-txt build errors."""

    pass


class PdfBuildError(BuildError):
    """Exception for markdown-to-PDF build errors."""

    pass


# ----- Validation Exceptions -----


class ValidationError(PalimpsestError):
    """Exception for data validation errors."""

    pass


# ----- File Management Exceptions -----


class TemporalFileError(PalimpsestError):
    """Exception for temporal file operations."""

    pass


# ----- Entry Processing Exceptions -----


class EntryError(PalimpsestError):
    """Base exception for entry processing operations."""

    pass


class EntryValidationError(EntryError):
    """Exception for entry validation failures (invalid format, missing required fields, etc.)."""

    pass


class EntryParseError(EntryError):
    """Exception for entry parsing failures (cannot extract metadata, malformed content, etc.)."""

    pass

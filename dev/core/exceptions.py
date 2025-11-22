#!/usr/bin/env python3
"""
exceptions.py
--------------------
Custom exception classes for the Palimpsest project.

This module defines a hierarchy of exceptions used throughout the project
to handle specific error conditions in different subsystems.

Exception Hierarchy:
    Exception (built-in)
    ├── DatabaseError - Base for all database-related errors
    │   ├── BackupError - Backup creation/restoration failures
    │   ├── HealthCheckError - Database health check failures
    │   └── ExportError - Data export operation failures
    ├── ValidationError - Data validation failures
    ├── TemporalFileError - Temporary file management errors
    ├── TxtBuildError - Raw export to text conversion errors
    ├── Txt2MdError - Text to Markdown conversion errors
    ├── Yaml2SqlError - Markdown to database sync errors
    ├── Sql2YamlError - Database to Markdown export errors
    └── PdfBuildError - PDF generation errors

Usage:
    from dev.core.exceptions import DatabaseError, ValidationError

    try:
        db.create_entry(...)
    except ValidationError as e:
        logger.error(f"Invalid data: {e}")
    except DatabaseError as e:
        logger.error(f"Database operation failed: {e}")
"""


class DatabaseError(Exception):
    """
    Base exception for database-related errors.

    Raised when database operations fail due to connection issues,
    query errors, integrity violations, or other database problems.

    This is the parent class for all database-specific exceptions.
    Catch this to handle any database error, or catch specific
    subclasses for more granular error handling.

    Attributes:
        message: Error description

    Examples:
        >>> raise DatabaseError("Connection to database failed")
        >>> raise DatabaseError("Integrity constraint violation: duplicate entry")

    See Also:
        BackupError, HealthCheckError, ExportError
    """

    pass


class BackupError(DatabaseError):
    """
    Exception for backup creation and restoration failures.

    Raised when backup operations fail, including:
    - Creating new backups
    - Restoring from backups
    - Backup file corruption
    - Insufficient disk space
    - Permission issues

    Examples:
        >>> raise BackupError("Failed to create backup: disk full")
        >>> raise BackupError("Backup file corrupted: checksum mismatch")
        >>> raise BackupError("Cannot restore from backup: file not found")
    """

    pass


class HealthCheckError(DatabaseError):
    """
    Exception for database health check failures.

    Raised when database health monitoring detects issues:
    - Integrity constraint violations
    - Orphaned records
    - Missing foreign key relationships
    - Index corruption
    - Schema inconsistencies

    Examples:
        >>> raise HealthCheckError("Found 5 orphaned location records")
        >>> raise HealthCheckError("Foreign key constraint violated in entry_people")
    """

    pass


class ExportError(DatabaseError):
    """
    Exception for data export operation failures.

    Raised when exporting database data to external formats fails:
    - CSV/JSON export failures
    - Markdown export failures
    - File writing errors
    - Format conversion issues

    Examples:
        >>> raise ExportError("Failed to export entries to CSV: permission denied")
        >>> raise ExportError("Cannot serialize reference data to JSON")
    """

    pass


class TemporalFileError(Exception):
    """
    Exception for temporary file management errors.

    Raised when temporary file operations fail:
    - Unable to create temp files
    - Cleanup failures
    - Permission issues
    - Disk space issues

    Examples:
        >>> raise TemporalFileError("Cannot create temp file: /tmp not writable")
        >>> raise TemporalFileError("Failed to cleanup temp files: permission denied")
    """

    pass


class ValidationError(Exception):
    """
    Exception for data validation failures.

    Raised when input data fails validation checks:
    - Invalid date formats
    - Missing required fields
    - Type mismatches
    - Constraint violations
    - Malformed metadata

    Examples:
        >>> raise ValidationError("Invalid date format: expected YYYY-MM-DD")
        >>> raise ValidationError("Missing required field: 'date'")
        >>> raise ValidationError("Word count must be non-negative")
    """

    pass


class EntryValidationError(ValidationError):
    """
    Exception for entry-specific validation failures.

    Raised when journal entry data fails validation:
    - Missing required entry fields
    - Invalid entry metadata
    - Malformed entry structure

    Examples:
        >>> raise EntryValidationError("Entry missing required date field")
        >>> raise EntryValidationError("Invalid people metadata format")
    """

    pass


class EntryParseError(Exception):
    """
    Exception for entry parsing failures.

    Raised when parsing journal entries from files or text fails:
    - YAML parsing errors
    - File reading errors
    - Malformed entry format
    - Encoding issues

    Examples:
        >>> raise EntryParseError("Cannot parse YAML frontmatter: invalid syntax")
        >>> raise EntryParseError("File not found or not readable")
        >>> raise EntryParseError("Invalid entry format: missing frontmatter")
    """

    pass


class TxtBuildError(Exception):
    """
    Exception for raw export to text conversion errors.

    Raised during the inbox processing stage (src2txt) when converting
    raw 750words exports to formatted text files fails:
    - File encoding issues
    - Malformed source files
    - Date parsing errors
    - I/O errors

    Pipeline Stage: inbox → txt (Step 1)

    Examples:
        >>> raise TxtBuildError("Cannot parse date from filename: invalid format")
        >>> raise TxtBuildError("Source file encoding not UTF-8")
    """

    pass


class Txt2MdError(Exception):
    """
    Exception for text to Markdown conversion errors.

    Raised during txt2md conversion when transforming formatted text
    files into Markdown entries with YAML frontmatter fails:
    - Text parsing errors
    - YAML generation issues
    - File I/O problems
    - Date extraction failures

    Pipeline Stage: txt → md (Step 2)

    Examples:
        >>> raise Txt2MdError("Cannot extract date from text file")
        >>> raise Txt2MdError("Failed to generate YAML frontmatter")
        >>> raise Txt2MdError("Invalid text file format: missing header")
    """

    pass


class Sql2YamlError(Exception):
    """
    Exception for database to Markdown export errors.

    Raised during sql2yaml when exporting database entries back to
    Markdown files with updated YAML frontmatter fails:
    - Database query failures
    - YAML serialization errors
    - File writing issues
    - Data conversion problems

    Pipeline Stage: database → md (Step 4)

    Examples:
        >>> raise Sql2YamlError("Cannot serialize relationship data to YAML")
        >>> raise Sql2YamlError("Entry not found in database: 2024-01-15")
        >>> raise Sql2YamlError("Failed to write Markdown file")
    """

    pass


class Yaml2SqlError(Exception):
    """
    Exception for Markdown to database sync errors.

    Raised during yaml2sql when parsing Markdown YAML frontmatter and
    syncing to database fails:
    - YAML parsing errors
    - Database constraint violations
    - Invalid metadata format
    - Relationship resolution failures

    Pipeline Stage: md → database (Step 3)

    Examples:
        >>> raise Yaml2SqlError("Invalid YAML frontmatter: malformed syntax")
        >>> raise Yaml2SqlError("Cannot resolve person reference: 'Unknown Person'")
        >>> raise Yaml2SqlError("Database integrity error: duplicate entry")
    """

    pass


class Sql2WikiError(Exception):
    """
    Exception for database to vimwiki export errors.

    Raised during sql2wiki when exporting database entities (people, themes,
    tags, etc.) to vimwiki pages fails:
    - Database query failures
    - Wiki page generation errors
    - File writing issues
    - Entity serialization problems

    Pipeline Stage: database → wiki (Step 6)

    Examples:
        >>> raise Sql2WikiError("Cannot generate wiki page for person: 'Alice'")
        >>> raise Sql2WikiError("Failed to build people index")
        >>> raise Sql2WikiError("Database connection lost during export")
    """

    pass


class Wiki2SqlError(Exception):
    """
    Exception for vimwiki to database sync errors.

    Raised during wiki2sql when parsing manually edited vimwiki entity
    pages and syncing changes back to database fails:
    - Wiki page parsing errors
    - Database update conflicts
    - Invalid wiki structure
    - Field ownership violations

    Pipeline Stage: wiki → database (Step 7)

    Examples:
        >>> raise Wiki2SqlError("Cannot parse person wiki page: malformed structure")
        >>> raise Wiki2SqlError("Conflict: wiki edited computed field 'mentions'")
        >>> raise Wiki2SqlError("Person not found in database: 'Unknown'")
    """

    pass


class PdfBuildError(Exception):
    """
    Exception for PDF generation errors.

    Raised during md2pdf when building yearly journal PDFs from
    Markdown files fails:
    - Pandoc conversion failures
    - LaTeX preamble errors
    - Missing font issues
    - File concatenation problems
    - Tectonic/XeLaTeX errors

    Pipeline Stage: md → pdf (Step 5)

    Examples:
        >>> raise PdfBuildError("Pandoc conversion failed: LaTeX error")
        >>> raise PdfBuildError("Missing preamble file: preamble.tex")
        >>> raise PdfBuildError("Font not found: Cormorant Garamond")
        >>> raise PdfBuildError("No Markdown files found for year: 2025")
    """

    pass


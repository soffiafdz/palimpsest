#!/usr/bin/env python3
"""
Palimpsest Database Package
---------------------------
Refactored database management system with modular architecture.

This package provides a comprehensive database management system for the
Palimpsest personal journal archive system, with specialized modules for:
- Core database operations
- Backup and recovery
- Health monitoring
- Data export
- Query analytics
- Relationship management
- Temporal file handling
"""

from .manager import PalimpsestDB
from dev.core.exceptions import (
    DatabaseError,
    ValidationError,
    BackupError,
    HealthCheckError,
    ExportError,
)
from .health_monitor import HealthMonitor
from .export_manager import ExportManager
from .query_analytics import QueryAnalytics
from .relationship_manager import RelationshipManager, HasId
from .decorators import (
    log_database_operation,
    handle_db_errors,
    validate_metadata,
)

__version__ = "2.0.0"
__author__ = "Palimpsest Development Team"

__all__ = [
    # Main manager
    "PalimpsestDB",
    # Exceptions
    "DatabaseError",
    "ValidationError",
    "BackupError",
    "HealthCheckError",
    "ExportError",
    # Core modules
    "HealthMonitor",
    "ExportManager",
    "QueryAnalytics",
    "RelationshipManager",
    # Decorators
    "log_database_operation",
    "handle_db_errors",
    "validate_metadata",
    # Protocols
    "HasId",
]

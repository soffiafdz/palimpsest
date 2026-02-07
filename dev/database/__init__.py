#!/usr/bin/env python3
"""
Palimpsest Database Package
---------------------------
Database management system with modular architecture.

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

from dev.core.exceptions import (
    DatabaseError,
    ValidationError,
    BackupError,
    HealthCheckError,
)
from .manager import PalimpsestDB
from .health_monitor import HealthMonitor
from .query_analytics import QueryAnalytics
from .decorators import DatabaseOperation

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
    # Core modules
    "HealthMonitor",
    "QueryAnalytics",
    # Context managers
    "DatabaseOperation",
]

#!/usr/bin/env python3
"""
validators
----------
Validation tools for Palimpsest data integrity and quality checks.

This package contains validators for different aspects of the Palimpsest system:
- Wiki link integrity and orphan detection
- Database schema drift, migrations, and referential integrity
- Markdown link validation (planned)
- Cross-system consistency checks (planned)

Each validator is a module with validation logic that can be run independently
or through the unified `validate` CLI command.

Architecture:
    - Each validator module (e.g., wiki.py, db.py) contains:
        1. Validation logic functions
        2. Result dataclasses
        3. Error/exception classes
    - The cli.py module provides unified entry point with subcommands
    - Simple validators stay in their respective CLIs (plm, metadb)

Usage:
    # Through CLI
    validate wiki check
    validate wiki orphans
    validate db schema
    validate db migrations
    validate db all

    # Direct import for programmatic use
    from dev.validators.wiki import validate_wiki
    from dev.validators.db import DatabaseValidator
"""

__all__ = [
    # Validators will be exported as they're implemented
]

#!/usr/bin/env python3
"""
Palimpsest Database CLI Helpers
--------------------------------

Shared helpers for database CLI commands. All commands are registered
under ``plm db`` in the pipeline CLI.

Key Features:
    - get_db(): Create PalimpsestDB from Click context
    - Command modules: setup, migration, backup, query, maintenance, prune
"""
from pathlib import Path

from dev.database import PalimpsestDB


def get_db(ctx) -> PalimpsestDB:
    """Get or create database instance from context."""
    if "db" not in ctx.obj:
        ctx.obj["db"] = PalimpsestDB(
            db_path=ctx.obj["db_path"],
            alembic_dir=ctx.obj["alembic_dir"],
            log_dir=ctx.obj["log_dir"],
            backup_dir=ctx.obj["backup_dir"],
            enable_auto_backup=False,
        )
    return ctx.obj["db"]

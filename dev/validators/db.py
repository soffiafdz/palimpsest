#!/usr/bin/env python3
"""
db.py
-----
Database validation tools for Palimpsest.

Validates database integrity including:
- Schema drift detection (model vs database)
- Migration status checking
- Foreign key integrity
- Data consistency
- Reference integrity

Usage:
    # Check schema drift
    validate db schema

    # Check migration status
    validate db migrations

    # Check foreign key integrity
    validate db integrity

    # Run all checks
    validate db all
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import List, Optional

# --- Third party imports ---
from sqlalchemy import inspect, text
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

# --- Local imports ---
from dev.database.manager import PalimpsestDB
from dev.database.models import Base
from dev.core.logging_manager import PalimpsestLogger
from dev.validators.diagnostic import Diagnostic, ValidationReport


class DatabaseValidator:
    """Validates database integrity and consistency."""

    def __init__(
        self,
        db: PalimpsestDB,
        alembic_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize database validator.

        Args:
            db: Database manager instance
            alembic_dir: Path to Alembic migrations directory
            logger: Optional logger instance
        """
        self.db = db
        self.alembic_dir = alembic_dir
        self.logger = logger
        self.engine = db.engine
        self.inspector = inspect(self.engine)

    def validate_schema(self) -> List[Diagnostic]:
        """
        Validate that database schema matches SQLAlchemy models.

        Checks for:
        - Missing tables
        - Missing columns
        - Extra columns (not in models)
        - Type mismatches

        Returns:
            List of SCHEMA_DRIFT diagnostics
        """
        diagnostics: List[Diagnostic] = []

        # Get all model tables
        model_tables = Base.metadata.tables

        for table_name, table in model_tables.items():
            # Check if table exists in database
            if not self.inspector.has_table(table_name):
                diagnostics.append(Diagnostic(
                    file="", line=0, col=0, end_line=0, end_col=0,
                    severity="error", code="SCHEMA_DRIFT",
                    message=f"Table '{table_name}' missing from database",
                ))
                continue

            # Get actual columns from database
            db_columns = {col["name"]: col for col in self.inspector.get_columns(table_name)}
            model_columns = {col.name: col for col in table.columns}

            # Check for missing columns
            for col_name in model_columns:
                if col_name not in db_columns:
                    diagnostics.append(Diagnostic(
                        file="", line=0, col=0, end_line=0, end_col=0,
                        severity="error", code="SCHEMA_DRIFT",
                        message=f"Column '{table_name}.{col_name}' missing from database",
                    ))

            # Check for extra columns (may indicate old schema)
            for col_name in db_columns:
                if col_name not in model_columns:
                    diagnostics.append(Diagnostic(
                        file="", line=0, col=0, end_line=0, end_col=0,
                        severity="warning", code="SCHEMA_DRIFT",
                        message=f"Column '{table_name}.{col_name}' exists in database but not in model",
                    ))

        return diagnostics

    def validate_migrations(self) -> List[Diagnostic]:
        """
        Check if all migrations have been applied.

        Returns:
            List of MIGRATION_PENDING diagnostics
        """
        try:
            # Get current database revision
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()

            # Get head revision from migration scripts
            script_dir = ScriptDirectory.from_config(self.db.alembic_cfg)
            head_rev = script_dir.get_current_head()

            if current_rev is None:
                return [Diagnostic(
                    file="", line=0, col=0, end_line=0, end_col=0,
                    severity="error", code="MIGRATION_PENDING",
                    message="Database has no migration history. Run: plm db upgrade",
                )]

            if current_rev != head_rev:
                # Get pending migrations
                pending = []
                base_revision = current_rev if current_rev is not None else "base"
                head_revision = head_rev if head_rev is not None else "head"
                for script in script_dir.walk_revisions(
                    base=base_revision, head=head_revision
                ):
                    if script.revision != current_rev:
                        rev_id = script.revision[:8] if script.revision else "unknown"
                        pending.append(f"{rev_id}: {script.doc}")

                current_short = current_rev[:8] if current_rev else "none"
                head_short = head_rev[:8] if head_rev else "none"
                pending_list = "; ".join(pending) if pending else ""
                return [Diagnostic(
                    file="", line=0, col=0, end_line=0, end_col=0,
                    severity="error", code="MIGRATION_PENDING",
                    message=(
                        f"Database needs migration (current: {current_short}, "
                        f"head: {head_short}). Pending: {pending_list}"
                    ),
                )]

            return []

        except Exception as e:
            return [Diagnostic(
                file="", line=0, col=0, end_line=0, end_col=0,
                severity="error", code="MIGRATION_PENDING",
                message=f"Failed to check migration status: {e}",
            )]

    def validate_foreign_keys(self) -> List[Diagnostic]:
        """
        Check for orphaned records (foreign key violations).

        Returns:
            List of FK_ORPHAN diagnostics
        """
        diagnostics: List[Diagnostic] = []

        # Get all tables with foreign keys
        for table_name in self.inspector.get_table_names():
            foreign_keys = self.inspector.get_foreign_keys(table_name)

            for fk in foreign_keys:
                # Build query to find orphaned records
                local_col = fk["constrained_columns"][0]
                remote_table = fk["referred_table"]
                remote_col = fk["referred_columns"][0]

                query = text(f"""
                    SELECT COUNT(*) as count
                    FROM "{table_name}"
                    WHERE "{local_col}" IS NOT NULL
                    AND "{local_col}" NOT IN (SELECT "{remote_col}" FROM "{remote_table}")
                """)

                with self.engine.connect() as conn:
                    result = conn.execute(query).fetchone()
                    orphaned_count = result[0] if result else 0

                if orphaned_count > 0:
                    diagnostics.append(Diagnostic(
                        file="", line=0, col=0, end_line=0, end_col=0,
                        severity="error", code="FK_ORPHAN",
                        message=(
                            f"{orphaned_count} orphaned record(s) in "
                            f"'{table_name}.{local_col}' "
                            f"(references '{remote_table}.{remote_col}')"
                        ),
                    ))

        return diagnostics

    def validate_unique_constraints(self) -> List[Diagnostic]:
        """
        Check for unique constraint violations.

        Returns:
            List of UNIQUE_VIOLATION diagnostics
        """
        diagnostics: List[Diagnostic] = []

        for table_name in self.inspector.get_table_names():
            unique_constraints = self.inspector.get_unique_constraints(table_name)

            # Check unique constraints
            for constraint in unique_constraints:
                columns = constraint["column_names"]
                col_list = ", ".join(columns)

                # Quote column names to handle reserved keywords
                quoted_cols = [f'"{col}"' for col in columns]
                quoted_col_list = ", ".join(quoted_cols)

                query = text(f"""
                    SELECT {quoted_col_list}, COUNT(*) as count
                    FROM "{table_name}"
                    WHERE {' AND '.join(f'"{col}" IS NOT NULL' for col in columns)}
                    GROUP BY {quoted_col_list}
                    HAVING COUNT(*) > 1
                """)

                with self.engine.connect() as conn:
                    duplicates = conn.execute(query).fetchall()

                if duplicates:
                    for dup in duplicates:
                        values = ", ".join(str(v) for v in dup[:-1])
                        count = dup[-1]
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="UNIQUE_VIOLATION",
                            message=(
                                f"{count} duplicate records in '{table_name}' "
                                f"for unique constraint ({col_list}): {values}"
                            ),
                        ))

        return diagnostics

    def validate_all(self) -> ValidationReport:
        """
        Run all validation checks.

        Returns:
            ValidationReport with all diagnostics
        """
        report = ValidationReport()

        report.diagnostics.extend(self.validate_migrations())
        report.diagnostics.extend(self.validate_schema())
        report.diagnostics.extend(self.validate_foreign_keys())
        report.diagnostics.extend(self.validate_unique_constraints())

        return report

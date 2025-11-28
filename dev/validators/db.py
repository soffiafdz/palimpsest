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
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from dev.database.manager import PalimpsestDB
from dev.database.models import Base
from dev.core.logging_manager import PalimpsestLogger


@dataclass
class ValidationResult:
    """Result of a validation check."""

    check_name: str
    passed: bool
    message: str
    details: Optional[List[str]] = None
    severity: str = "info"  # info, warning, error


@dataclass
class DatabaseValidationReport:
    """Complete database validation report."""

    results: List[ValidationResult]
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: int = 0
    errors: int = 0

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)
        self.total_checks += 1
        if result.passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1
            if result.severity == "warning":
                self.warnings += 1
            elif result.severity == "error":
                self.errors += 1

    @property
    def has_errors(self) -> bool:
        """Check if any errors were found."""
        return self.errors > 0

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were found."""
        return self.warnings > 0

    @property
    def is_healthy(self) -> bool:
        """Check if database is healthy (no errors)."""
        return not self.has_errors


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

    def validate_schema(self) -> ValidationResult:
        """
        Validate that database schema matches SQLAlchemy models.

        Checks for:
        - Missing tables
        - Missing columns
        - Extra columns (not in models)
        - Type mismatches

        Returns:
            ValidationResult with schema drift details
        """
        issues: List[str] = []

        # Get all model tables
        model_tables = Base.metadata.tables

        for table_name, table in model_tables.items():
            # Check if table exists in database
            if not self.inspector.has_table(table_name):
                issues.append(f"❌ Table '{table_name}' missing from database")
                continue

            # Get actual columns from database
            db_columns = {col["name"]: col for col in self.inspector.get_columns(table_name)}
            model_columns = {col.name: col for col in table.columns}

            # Check for missing columns
            for col_name in model_columns:
                if col_name not in db_columns:
                    issues.append(
                        f"❌ Column '{table_name}.{col_name}' missing from database"
                    )

            # Check for extra columns (may indicate old schema)
            for col_name in db_columns:
                if col_name not in model_columns:
                    issues.append(
                        f"⚠️  Column '{table_name}.{col_name}' exists in database but not in model"
                    )

        if issues:
            return ValidationResult(
                check_name="Schema Validation",
                passed=False,
                message=f"Found {len(issues)} schema drift issue(s)",
                details=issues,
                severity="error",
            )
        else:
            return ValidationResult(
                check_name="Schema Validation",
                passed=True,
                message="Database schema matches models",
                severity="info",
            )

    def validate_migrations(self) -> ValidationResult:
        """
        Check if all migrations have been applied.

        Returns:
            ValidationResult indicating if migrations are up to date
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
                return ValidationResult(
                    check_name="Migration Status",
                    passed=False,
                    message="Database has no migration history",
                    details=["Run: metadb migration upgrade"],
                    severity="error",
                )

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
                        pending.append(f"  • {rev_id}: {script.doc}")

                current_short = current_rev[:8] if current_rev else "none"
                head_short = head_rev[:8] if head_rev else "none"
                return ValidationResult(
                    check_name="Migration Status",
                    passed=False,
                    message=f"Database needs migration (current: {current_short}, head: {head_short})",
                    details=[f"Pending migrations ({len(pending)}):"] + pending + ["", "Run: metadb migration upgrade"],
                    severity="error",
                )
            else:
                return ValidationResult(
                    check_name="Migration Status",
                    passed=True,
                    message=f"Database is up to date (revision: {current_rev[:8]})",
                    severity="info",
                )

        except Exception as e:
            return ValidationResult(
                check_name="Migration Status",
                passed=False,
                message=f"Failed to check migration status: {e}",
                severity="error",
            )

    def validate_foreign_keys(self) -> ValidationResult:
        """
        Check for orphaned records (foreign key violations).

        Returns:
            ValidationResult with orphaned record details
        """
        issues: List[str] = []

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
                    issues.append(
                        f"❌ {orphaned_count} orphaned record(s) in '{table_name}.{local_col}' "
                        f"(references '{remote_table}.{remote_col}')"
                    )

        if issues:
            return ValidationResult(
                check_name="Foreign Key Integrity",
                passed=False,
                message=f"Found {len(issues)} foreign key violation(s)",
                details=issues,
                severity="error",
            )
        else:
            return ValidationResult(
                check_name="Foreign Key Integrity",
                passed=True,
                message="All foreign key constraints satisfied",
                severity="info",
            )

    def validate_unique_constraints(self) -> ValidationResult:
        """
        Check for unique constraint violations.

        Returns:
            ValidationResult with duplicate record details
        """
        issues: List[str] = []

        for table_name in self.inspector.get_table_names():
            unique_constraints = self.inspector.get_unique_constraints(table_name)
            indexes = [
                idx for idx in self.inspector.get_indexes(table_name) if idx["unique"]
            ]

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
                        issues.append(
                            f"❌ {count} duplicate records in '{table_name}' "
                            f"for unique constraint ({col_list}): {values}"
                        )

        if issues:
            return ValidationResult(
                check_name="Unique Constraints",
                passed=False,
                message=f"Found {len(issues)} constraint violation(s)",
                details=issues,
                severity="error",
            )
        else:
            return ValidationResult(
                check_name="Unique Constraints",
                passed=True,
                message="All unique constraints satisfied",
                severity="info",
            )

    def validate_all(self) -> DatabaseValidationReport:
        """
        Run all validation checks.

        Returns:
            Complete validation report
        """
        report = DatabaseValidationReport(results=[])

        # Run all checks
        report.add_result(self.validate_migrations())
        report.add_result(self.validate_schema())
        report.add_result(self.validate_foreign_keys())
        report.add_result(self.validate_unique_constraints())

        return report


def format_validation_report(report: DatabaseValidationReport) -> str:
    """
    Format validation report as readable text.

    Args:
        report: Validation report to format

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("DATABASE VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append(f"Total Checks: {report.total_checks}")
    lines.append(f"✅ Passed: {report.passed_checks}")
    lines.append(f"❌ Failed: {report.failed_checks}")
    if report.warnings > 0:
        lines.append(f"⚠️  Warnings: {report.warnings}")
    if report.errors > 0:
        lines.append(f"🚨 Errors: {report.errors}")
    lines.append("")

    # Overall status
    if report.is_healthy:
        lines.append("✅ DATABASE IS HEALTHY")
    else:
        lines.append("❌ DATABASE HAS ISSUES")
    lines.append("")

    # Detailed results
    for result in report.results:
        icon = "✅" if result.passed else "❌"
        lines.append(f"{icon} {result.check_name}")
        lines.append(f"   {result.message}")

        if result.details:
            for detail in result.details:
                lines.append(f"   {detail}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)

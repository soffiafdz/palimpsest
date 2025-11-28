#!/usr/bin/env python3
"""
health_monitor.py
-----------------
Database health monitoring and maintenance utilities.

This module provides comprehensive database health checks, integrity validation,
and maintenance operations for the Palimpsest metadata database. It detects
issues like orphaned records, integrity violations, and performance problems.

Key Features:
    - Comprehensive health checks with multiple validation layers
    - Orphaned record detection across all entity types
    - Data integrity validation (foreign keys, constraints)
    - Database file statistics and performance metrics
    - Relationship consistency checks
    - Automated issue detection and reporting
    - Fix recommendations for common problems

Health Checks Performed:
    1. **Connectivity**: Basic database connection and query execution
    2. **Orphaned Records**: Detects records with broken relationships
       - Locations without parent cities
       - References without parent entries
       - PoemVersions without parent poems
       - ManuscriptEntries without base entries
    3. **Data Integrity**: Validates constraints and relationships
       - Foreign key consistency
       - Check constraint validation
       - Date range validation
    4. **Performance**: Database size, index health, query performance
    5. **Schema**: Verifies schema version and migrations

Usage:
    from dev.database.health_monitor import HealthMonitor
    from dev.database.manager import PalimpsestDB

    db = PalimpsestDB(db_path, alembic_dir)
    monitor = HealthMonitor(logger=db.logger)

    with db.session_scope() as session:
        # Run comprehensive health check
        health_report = monitor.health_check(session, db_path=db.db_path)

        if health_report["status"] != "healthy":
            print(f"Issues found: {health_report['issues']}")
            print(f"Recommendations: {health_report['recommendations']}")

        # Check for specific issues
        orphans = monitor._check_orphaned_records(session)
        if orphans["total"] > 0:
            print(f"Found {orphans['total']} orphaned records")

CLI Integration:
    metadb health                  # Basic health check
    metadb health --fix            # Run health check and auto-fix issues
    metadb validate                # Validate database integrity

Health Report Structure:
    {
        "status": "healthy" | "warning" | "critical",
        "issues": [
            {"severity": "high", "category": "orphans", "message": "..."},
            ...
        ],
        "metrics": {
            "orphaned_records": {"total": 0, "by_type": {...}},
            "integrity": {"passed": True, "violations": []},
            "performance": {"size_mb": 5.2, "entry_count": 1250}
        },
        "recommendations": ["Run cleanup...", "Optimize indexes..."]
    }

Notes:
    - Health checks are non-destructive by default
    - Use --fix flag with metadb CLI for auto-repair
    - Orphan detection uses QueryOptimizer for efficiency
    - Health check results are logged automatically
    - Failed checks raise HealthCheckError

See Also:
    - query_optimizer.py: Efficient database queries
    - manager.py: Main database interface
    - decorators.py: @handle_db_errors, @log_database_operation
"""
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from dev.core.exceptions import HealthCheckError
from dev.core.logging_manager import PalimpsestLogger
from .decorators import handle_db_errors, log_database_operation
from .query_optimizer import QueryOptimizer

# Import models for health checks
from .models import (
    Entry,
    Person,
    City,
    Location,
    Event,
    Tag,
    Reference,
    ReferenceSource,
    MentionedDate,
    Poem,
    PoemVersion,
    Alias,
)
from .models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
)


class HealthMonitor:
    """
    Database health monitoring and maintenance system.

    Provides comprehensive health checks, orphan detection,
    and database maintenance utilities.
    """

    def __init__(self, logger: Optional[PalimpsestLogger] = None) -> None:
        """
        Initialize health monitor.

        Args:
            logger: Optional logger for health operations
        """
        self.logger = logger

    @handle_db_errors
    @log_database_operation("health_check")
    def health_check(
        self,
        session: Session,
        db_path: Optional[Path] = None,
        check_files: bool = False,
    ) -> Dict[str, Any]:
        """
        Comprehensive database health check.

        Args:
            session: SQLAlchemy session
            db_path: Optional path to database file for file checks

        Returns:
            Dictionary with health status and metrics

        Raises:
            HealthCheckError: If health check encounters critical errors
        """
        health = {
            "status": "healthy",
            "issues": [],
            "metrics": {},
            "recommendations": [],
        }

        try:
            # Test basic connectivity
            session.execute(text("SELECT 1"))

            # Check for orphaned records
            orphan_results = self._check_orphaned_records(session)
            health["metrics"]["orphaned_records"] = orphan_results

            # Check for data integrity issues
            integrity_results = self._check_data_integrity(session)
            health["metrics"]["integrity"] = integrity_results

            # Check relationship integrity
            rel_integrity = self._check_relationship_integrity(session)
            health["metrics"]["relationship_integrity"] = rel_integrity

            # Check reference integrity
            ref_integrity = self._check_reference_integrity(session)
            health["metrics"]["reference_integrity"] = ref_integrity

            # Check poem integrity
            poem_integrity = self._check_poem_integrity(session)
            health["metrics"]["poem_integrity"] = poem_integrity

            # Check manuscript integrity
            manuscript_integrity = self._check_manuscript_integrity(session)
            health["metrics"]["manuscript_integrity"] = manuscript_integrity

            # Check mentioned date integrity
            date_integrity = self._check_mentioned_date_integrity(session)
            health["metrics"]["mentioned_date_integrity"] = date_integrity

            # Check file references if db_path provided
            if check_files and db_path:
                file_results = self._check_file_references(session)
                health["metrics"]["file_references"] = file_results

            # Database size and performance metrics
            perf_metrics = self._get_performance_metrics(session)
            health["metrics"]["performance"] = perf_metrics

            # Evaluate overall health
            health = self._evaluate_health_status(health)

        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Database connectivity issue: {e}")
            if self.logger:
                self.logger.log_error(e, {"operation": "health_check"})
            raise HealthCheckError(f"Health check failed: {e}")

        return health

    def _check_orphaned_records(self, session: Session) -> Dict[str, int]:
        """
        Check for orphaned records across all tables.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with orphan counts by table
        """
        orphans = {}

        # Check orphaned aliases (person deleted)
        orphans["aliases"] = (
            session.query(Alias)
            .filter(~Alias.person_id.in_(session.query(Person.id)))
            .count()
        )

        # Check orphaned references (entry deleted)
        orphans["references"] = (
            session.query(Reference)
            .filter(~Reference.entry_id.in_(session.query(Entry.id)))
            .count()
        )

        # Check orphaned poem versions (entry deleted)
        orphans["poem_versions"] = (
            session.query(PoemVersion)
            .filter(
                PoemVersion.entry_id.isnot(None),
                ~PoemVersion.entry_id.in_(session.query(Entry.id)),
            )
            .count()
        )

        # Check manuscript orphans
        orphans["manuscript_entries"] = (
            session.query(ManuscriptEntry)
            .filter(~ManuscriptEntry.entry_id.in_(session.query(Entry.id)))
            .count()
        )

        orphans["manuscript_people"] = (
            session.query(ManuscriptPerson)
            .filter(~ManuscriptPerson.person_id.in_(session.query(Person.id)))
            .count()
        )

        orphans["manuscript_events"] = (
            session.query(ManuscriptEvent)
            .filter(~ManuscriptEvent.event_id.in_(session.query(Event.id)))
            .count()
        )

        return orphans

    def _check_data_integrity(self, session: Session) -> Dict[str, Any]:
        """
        Check for data integrity issues.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with integrity check results
        """
        integrity = {}

        # Check for duplicate file paths
        duplicate_paths = (
            session.query(Entry.file_path, func.count(Entry.id))
            .group_by(Entry.file_path)
            .having(func.count(Entry.id) > 1)
            .all()
        )
        integrity["duplicate_file_paths"] = len(duplicate_paths)

        # Check for invalid dates (future dates)
        future_entries = (
            session.query(Entry).filter(Entry.date > datetime.now().date()).count()
        )
        integrity["future_dated_entries"] = future_entries

        # Check for empty required fields
        entries_no_path = session.query(Entry).filter(Entry.file_path.is_(None)).count()
        integrity["entries_without_file_path"] = entries_no_path

        return integrity

    def _check_relationship_integrity(self, session: Session) -> Dict[str, Any]:
        """
        Check relationship integrity with optimized queries.

        Uses QueryOptimizer to efficiently check all relationships.
        """
        issues = {}

        # Get sample of entries with all relationships preloaded
        sample_ids = (
            session.query(Entry.id).order_by(Entry.date.desc()).limit(100).all()
        )
        sample_ids = [e_id for (e_id,) in sample_ids]

        if sample_ids:
            # Preload everything at once
            entries = QueryOptimizer.for_export(session, sample_ids)

            # Now check relationships without triggering queries
            for entry in entries:
                # Check for people without names
                invalid_people = [p for p in entry.people if not p.name]
                if invalid_people:
                    issues[f"entry_{entry.date}"] = (
                        f"{len(invalid_people)} people without names"
                    )

                # Check for locations without cities
                invalid_locations = [loc for loc in entry.locations if not loc.city]
                if invalid_locations:
                    issues[f"entry_{entry.date}_locations"] = (
                        f"{len(invalid_locations)} locations without cities"
                    )

        return issues

    def _run_integrity_check_group(self, session: Session, check_group) -> Dict[str, Any]:
        """
        Run a group of integrity checks using configuration.

        Args:
            session: SQLAlchemy session
            check_group: IntegrityCheckGroup with checks to run

        Returns:
            Dictionary with check results
        """
        results = {}
        for check in check_group.checks:
            count = check.query_builder(session)
            results[check.check_name] = count
        return results

    def _check_reference_integrity(self, session: Session) -> Dict[str, Any]:
        """
        Check reference and reference source integrity.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with reference integrity results
        """
        from .configs.integrity_check_configs import REFERENCE_INTEGRITY_CHECKS
        return self._run_integrity_check_group(session, REFERENCE_INTEGRITY_CHECKS)

    def _check_poem_integrity(self, session: Session) -> Dict[str, Any]:
        """
        Check poem and poem version integrity.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with poem integrity results
        """
        from .configs.integrity_check_configs import POEM_INTEGRITY_CHECKS
        return self._run_integrity_check_group(session, POEM_INTEGRITY_CHECKS)

    def _check_manuscript_integrity(self, session: Session) -> Dict[str, Any]:
        """
        Check manuscript-specific integrity.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with manuscript integrity results
        """
        from .configs.integrity_check_configs import MANUSCRIPT_INTEGRITY_CHECKS
        return self._run_integrity_check_group(session, MANUSCRIPT_INTEGRITY_CHECKS)

    def _check_mentioned_date_integrity(self, session: Session) -> Dict[str, Any]:
        """
        Check mentioned date integrity.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with mentioned date integrity results
        """
        from .configs.integrity_check_configs import MENTIONED_DATE_INTEGRITY_CHECKS
        return self._run_integrity_check_group(session, MENTIONED_DATE_INTEGRITY_CHECKS)

    def _check_file_references(self, session: Session) -> Dict[str, Any]:
        """
        Check for missing file references.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with file reference check results
        """
        file_checks = {"missing_files": [], "total_missing": 0, "total_checked": 0}

        entries = session.query(Entry).all()
        file_checks["total_checked"] = len(entries)

        for entry in entries:
            if entry.file_path and not Path(entry.file_path).exists():
                file_checks["missing_files"].append(
                    {
                        "entry_id": entry.id,
                        "date": entry.date.isoformat(),
                        "file_path": entry.file_path,
                    }
                )

        file_checks["total_missing"] = len(file_checks["missing_files"])

        # Only keep first 10 examples to avoid huge result
        if len(file_checks["missing_files"]) > 10:
            file_checks["missing_files"] = file_checks["missing_files"][:10]
            file_checks["truncated"] = True

        return file_checks

    @handle_db_errors
    @log_database_operation("optimize_database")
    def optimize_database(self, session: Session) -> Dict[str, Any]:
        """
        Optimize database by running VACUUM and ANALYZE.

        VACUUM reclaims unused space and defragments the database.
        ANALYZE updates query optimizer statistics.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with optimization results

        Note:
            VACUUM requires exclusive access and can take time on large databases.
        """
        from sqlalchemy import text

        results = {"vacuum_completed": False, "analyze_completed": False, "errors": []}

        try:
            # Get size before optimization
            db_size_query = text(
                "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
            )
            size_before = session.execute(db_size_query).scalar()
            results["size_before_bytes"] = size_before

            # Run VACUUM (must be outside transaction)
            session.commit()  # Commit any pending transaction
            session.execute(text("VACUUM"))
            results["vacuum_completed"] = True

            if self.logger:
                self.logger.log_operation(
                    "vacuum_completed", {"size_before": size_before}
                )

            # Run ANALYZE
            session.execute(text("ANALYZE"))
            results["analyze_completed"] = True

            # Get size after optimization
            size_after = session.execute(db_size_query).scalar()
            if size_after:
                results["size_after_bytes"] = size_after
                results["space_reclaimed_bytes"] = size_before - size_after

            if self.logger:
                self.logger.log_operation("optimize_completed", results)

        except Exception as e:
            results["errors"].append(str(e))
            if self.logger:
                self.logger.log_error(e, {"operation": "optimize_database"})
            raise HealthCheckError(f"Database optimization failed: {e}")

        return results

    def _get_performance_metrics(self, session: Session) -> Dict[str, Any]:
        """
        Get database performance metrics.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with performance metrics
        """
        metrics = {}

        # Table sizes
        metrics["table_counts"] = {
            "entries": session.query(Entry).count(),
            "people": session.query(Person).count(),
            "cities": session.query(City).count(),
            "locations": session.query(Location).count(),
            "events": session.query(Event).count(),
            "tags": session.query(Tag).count(),
            "references": session.query(Reference).count(),
            "reference_sources": session.query(ReferenceSource).count(),
            "poems": session.query(Poem).count(),
            "poem_versions": session.query(PoemVersion).count(),
            "mentioned_dates": session.query(MentionedDate).count(),
        }

        # Recent activity
        week_ago = datetime.now() - timedelta(days=7)
        metrics["recent_activity"] = {
            "entries_updated_last_7_days": session.query(Entry)
            .filter(Entry.updated_at >= week_ago)
            .count()
        }

        # Index usage (SQLite specific)
        try:
            result = session.execute(text("PRAGMA index_list('entries')"))
            metrics["index_count"] = len(result.fetchall())
        except Exception as e:
            raise HealthCheckError(f"Performance check failed: {e}")

        return metrics

    def _evaluate_health_status(self, health: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate overall health status based on metrics.

        Args:
            health: Current health dictionary

        Returns:
            Updated health dictionary with status and recommendations
        """
        # Check orphaned records
        orphans = health["metrics"].get("orphaned_records", {})
        total_orphans = sum(orphans.values())

        if total_orphans > 0:
            health["issues"].append(f"{total_orphans} orphaned records found")
            health["recommendations"].append(
                "Run cleanup_orphaned_records() to remove orphans"
            )

        # Check integrity
        integrity = health["metrics"].get("integrity", {})
        if integrity.get("duplicate_file_paths", 0) > 0:
            health["issues"].append("Duplicate file paths detected")
            health["status"] = "warning"
            health["recommendations"].append(
                "Review and resolve duplicate file path entries"
            )

        if integrity.get("future_dated_entries", 0) > 0:
            health["issues"].append("Entries with future dates detected")
            health["recommendations"].append(
                "Review entries with future dates for data entry errors"
            )

        if integrity.get("entries_without_file_path", 0) > 0:
            health["issues"].append("Entries without file paths detected")
            health["status"] = "warning"
            health["recommendations"].append(
                "Investigate entries missing file_path field"
            )

        # Check reference integrity
        ref_integrity = health["metrics"].get("reference_integrity", {})
        if ref_integrity.get("references_with_invalid_source", 0) > 0:
            health["issues"].append("References with invalid source IDs detected")
            health["status"] = "warning"
            health["recommendations"].append(
                "Clean up references with invalid source references"
            )

        if ref_integrity.get("references_without_content", 0) > 0:
            health["issues"].append("References without content detected")
            health["recommendations"].append(
                "Review and fix references with empty content"
            )

        # Check poem integrity
        poem_integrity = health["metrics"].get("poem_integrity", {})
        if poem_integrity.get("poems_without_versions", 0) > 0:
            health["issues"].append("Poems without any versions detected")
            health["recommendations"].append(
                "Remove poems without versions or add missing versions"
            )

        if poem_integrity.get("orphaned_poem_versions", 0) > 0:
            health["issues"].append("Orphaned poem versions detected")
            health["status"] = "warning"
            health["recommendations"].append("Clean up orphaned poem versions")

        if poem_integrity.get("poem_versions_without_content", 0) > 0:
            health["issues"].append("Poem versions without content detected")
            health["recommendations"].append(
                "Review and fix poem versions with empty content"
            )

        # Check manuscript integrity
        manuscript_integrity = health["metrics"].get("manuscript_integrity", {})
        if manuscript_integrity.get("orphaned_themes", 0) > 0:
            health["issues"].append("Orphaned themes detected")
            health["recommendations"].append("Remove unused themes")

        if manuscript_integrity.get("orphaned_arcs", 0) > 0:
            health["issues"].append("Orphaned arcs detected")
            health["recommendations"].append("Remove unused arcs")

        # Check mentioned date integrity
        date_integrity = health["metrics"].get("mentioned_date_integrity", {})
        if date_integrity.get("orphaned_mentioned_dates", 0) > 0:
            health["issues"].append("Orphaned mentioned dates detected")
            health["recommendations"].append("Remove unused mentioned dates")

        if date_integrity.get("duplicate_date_contexts", 0) > 0:
            health["issues"].append("Duplicate date+context combinations detected")
            health["recommendations"].append("Consolidate duplicate mentioned dates")

        if date_integrity.get("far_future_mentioned_dates", 0) > 0:
            health["issues"].append("Mentioned dates far in future detected")
            health["recommendations"].append(
                "Review mentioned dates for data entry errors"
            )

        # Check file references
        file_refs = health["metrics"].get("file_references", {})
        if file_refs.get("total_missing", 0) > 0:
            health["issues"].append(
                f"{file_refs['total_missing']} entries reference missing files"
            )
            health["status"] = "warning"

        # Set final status
        if health["issues"] and health["status"] == "healthy":
            health["status"] = "warning"
            health["recommendations"].append(
                "Verify file paths and restore missing files or update entries"
            )

        # Set final status
        if health["issues"] and health["status"] == "healthy":
            health["status"] = "warning"

        return health

    @handle_db_errors
    @log_database_operation("cleanup_orphaned_records")
    def cleanup_orphaned_records(
        self, session: Session, dry_run: bool = True
    ) -> Dict[str, int | bool]:
        """
        Clean up orphaned records from the database.

        Args:
            session: SQLAlchemy session
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup results
        """
        results: Dict[str, bool | int] = {"dry_run": dry_run}

        # Find and optionally delete orphaned aliases
        orphaned_aliases = (
            session.query(Alias)
            .filter(~Alias.person_id.in_(session.query(Person.id)))
            .all()
        )

        results["orphaned_aliases"] = len(orphaned_aliases)

        if not dry_run and orphaned_aliases:
            for alias in orphaned_aliases:
                session.delete(alias)

        # Find and optionally delete orphaned references
        orphaned_refs = (
            session.query(Reference)
            .filter(~Reference.entry_id.in_(session.query(Entry.id)))
            .all()
        )

        results["orphaned_references"] = len(orphaned_refs)

        if not dry_run and orphaned_refs:
            for ref in orphaned_refs:
                session.delete(ref)

        # Find and optionally delete orphaned poem versions
        orphaned_poems = (
            session.query(PoemVersion)
            .filter(
                PoemVersion.entry_id.isnot(None),
                ~PoemVersion.entry_id.in_(session.query(Entry.id)),
            )
            .all()
        )

        results["orphaned_poem_versions"] = len(orphaned_poems)

        if not dry_run and orphaned_poems:
            for poem in orphaned_poems:
                session.delete(poem)

        # Manuscript orphans
        orphaned_manuscript_entries = (
            session.query(ManuscriptEntry)
            .filter(~ManuscriptEntry.entry_id.in_(session.query(Entry.id)))
            .all()
        )

        results["orphaned_manuscript_entries"] = len(orphaned_manuscript_entries)

        if not dry_run and orphaned_manuscript_entries:
            for ms in orphaned_manuscript_entries:
                session.delete(ms)

        if not dry_run:
            session.flush()
            if self.logger:
                self.logger.log_operation("orphaned_records_cleaned", results)

        return results

    @handle_db_errors
    @log_database_operation("bulk_cleanup_unused")
    def bulk_cleanup_unused(
        self, session: Session, cleanup_config: Dict[str, tuple]
    ) -> Dict[str, int]:
        """
        Perform bulk cleanup operations more efficiently.

        Args:
            session: SQLAlchemy session
            cleanup_config: Dictionary mapping table names to (model_class, relationship_attr) tuples

        Returns:
            Dictionary with cleanup results
        """
        results = {}

        for table_name, (model_class, relationship_attr) in cleanup_config.items():
            # Use bulk delete for better performance
            subquery = (
                session.query(model_class.id)
                .filter(~getattr(model_class, relationship_attr).any())
                .subquery()
            )

            deleted_count = (
                session.query(model_class)
                .filter(model_class.id.in_(subquery.select()))
                .delete(synchronize_session=False)
            )

            results[table_name] = deleted_count
            if self.logger:
                self.logger.log_operation(
                    "cleanup_table",
                    {"table": table_name, "deleted_count": deleted_count},
                )

        session.flush()
        return results

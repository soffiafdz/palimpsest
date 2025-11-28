#!/usr/bin/env python3
"""
consistency.py
-------------
Cross-system consistency validation for Palimpsest.

Validates consistency between:
- Markdown files (MD)
- Database (DB)
- Wiki pages (Wiki)

Checks for:
- Entry existence across systems (MD ↔ DB ↔ Wiki)
- Metadata synchronization
- Referential integrity
- File hash consistency
- Date reasonableness

Usage:
    validate consistency all         # Run all checks
    validate consistency existence   # Check entry existence
    validate consistency metadata    # Check metadata sync
    validate consistency references  # Check referential integrity
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import date, timedelta
from collections import defaultdict

from dev.database.manager import PalimpsestDB
from dev.dataclasses.md_entry import MdEntry
from dev.database.models import Entry, Person, Location, City, Event, Tag, Poem, PoemVersion
from dev.core.validators import DataValidator
from dev.core.logging_manager import PalimpsestLogger


@dataclass
class ConsistencyIssue:
    """Represents a consistency validation issue."""

    check_type: str  # existence, metadata, references, integrity
    severity: str  # error, warning
    system: str  # md, db, wiki, md-db, db-wiki, md-db-wiki
    entity_type: str  # entry, person, location, etc.
    entity_id: str  # date, name, etc.
    message: str
    suggestion: Optional[str] = None


@dataclass
class ConsistencyValidationReport:
    """Complete consistency validation report."""

    checks_performed: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    issues: List[ConsistencyIssue] = field(default_factory=list)

    def add_issue(self, issue: ConsistencyIssue) -> None:
        """Add an issue to the report."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.total_errors += 1
        elif issue.severity == "warning":
            self.total_warnings += 1

    @property
    def has_errors(self) -> bool:
        """Check if any errors were found."""
        return self.total_errors > 0

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were found."""
        return self.total_warnings > 0

    @property
    def is_healthy(self) -> bool:
        """Check if all systems are healthy (no errors)."""
        return not self.has_errors


class ConsistencyValidator:
    """Validates consistency across MD, DB, and Wiki systems."""

    def __init__(
        self,
        db: PalimpsestDB,
        md_dir: Path,
        wiki_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize consistency validator.

        Args:
            db: Database manager instance
            md_dir: Directory containing markdown files
            wiki_dir: Directory containing wiki files
            logger: Optional logger instance
        """
        self.db = db
        self.md_dir = md_dir
        self.wiki_dir = wiki_dir
        self.logger = logger
        self.report = ConsistencyValidationReport()

    def validate_all(self) -> ConsistencyValidationReport:
        """
        Run all consistency checks.

        Returns:
            Complete validation report
        """
        self.report = ConsistencyValidationReport()

        # Run all checks
        self.check_entry_existence()
        self.check_entry_metadata()
        self.check_referential_integrity()
        self.check_file_integrity()

        return self.report

    def check_entry_existence(self) -> List[ConsistencyIssue]:
        """
        Check entry existence across MD ↔ DB ↔ Wiki.

        Returns:
            List of existence issues
        """
        issues = []
        self.report.checks_performed += 1

        if self.logger:
            self.logger.log_info("Checking entry existence across systems...")

        # Get entry dates from each system
        md_dates = self._get_md_dates()
        db_dates = self._get_db_dates()
        wiki_dates = self._get_wiki_dates()

        # MD but not DB (parsing failed or sync not run)
        md_only = md_dates - db_dates
        for date_str in md_only:
            issue = ConsistencyIssue(
                check_type="existence",
                severity="error",
                system="md-db",
                entity_type="entry",
                entity_id=date_str,
                message=f"Entry exists in markdown but not in database",
                suggestion="Run: python -m dev.pipeline.cli yaml2sql",
            )
            issues.append(issue)
            self.report.add_issue(issue)

        # DB but not MD (file deleted or moved)
        with self.db.session_scope() as session:
            for entry in session.query(Entry).all():
                if entry.file_path:
                    file_path = Path(entry.file_path)
                    if not file_path.exists():
                        issue = ConsistencyIssue(
                            check_type="existence",
                            severity="error",
                            system="db-md",
                            entity_type="entry",
                            entity_id=entry.date.isoformat(),
                            message=f"Entry in database but file missing: {entry.file_path}",
                            suggestion="Restore file or remove entry from database",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

        # DB but not Wiki (export not run)
        db_not_wiki = db_dates - wiki_dates
        for date_str in db_not_wiki:
            issue = ConsistencyIssue(
                check_type="existence",
                severity="warning",
                system="db-wiki",
                entity_type="entry",
                entity_id=date_str,
                message=f"Entry in database but not exported to wiki",
                suggestion="Run: python -m dev.pipeline.cli sql2wiki",
            )
            issues.append(issue)
            self.report.add_issue(issue)

        # Wiki but not DB (orphaned wiki file)
        wiki_only = wiki_dates - db_dates
        for date_str in wiki_only:
            issue = ConsistencyIssue(
                check_type="existence",
                severity="error",
                system="wiki-db",
                entity_type="entry",
                entity_id=date_str,
                message=f"Entry in wiki but not in database",
                suggestion="Import entry or remove wiki file",
            )
            issues.append(issue)
            self.report.add_issue(issue)

        if self.logger:
            self.logger.log_info(f"Found {len(issues)} entry existence issues")

        return issues

    def check_entry_metadata(self) -> List[ConsistencyIssue]:
        """
        Check metadata synchronization between MD and DB.

        Returns:
            List of metadata consistency issues
        """
        issues = []
        self.report.checks_performed += 1

        if self.logger:
            self.logger.log_info("Checking entry metadata consistency...")

        with self.db.session_scope() as session:
            for entry_db in session.query(Entry).all():
                if not entry_db.file_path or not Path(entry_db.file_path).exists():
                    continue

                try:
                    entry_md = MdEntry.from_file(Path(entry_db.file_path))

                    # Check core fields
                    if entry_md.date != entry_db.date:
                        issue = ConsistencyIssue(
                            check_type="metadata",
                            severity="error",
                            system="md-db",
                            entity_type="entry",
                            entity_id=entry_db.date.isoformat(),
                            message=f"Date mismatch: MD={entry_md.date}, DB={entry_db.date}",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

                    # Check word count
                    md_word_count = entry_md.metadata.get("word_count", 0)
                    if md_word_count and int(md_word_count) != entry_db.word_count:
                        issue = ConsistencyIssue(
                            check_type="metadata",
                            severity="warning",
                            system="md-db",
                            entity_type="entry",
                            entity_id=entry_db.date.isoformat(),
                            message=f"Word count mismatch: MD={md_word_count}, DB={entry_db.word_count}",
                            suggestion="Run: python -m dev.pipeline.cli yaml2sql --force",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

                    # Check relationship counts
                    issues.extend(
                        self._check_people_consistency(entry_md, entry_db, session)
                    )
                    issues.extend(
                        self._check_locations_consistency(entry_md, entry_db, session)
                    )
                    issues.extend(
                        self._check_tags_consistency(entry_md, entry_db, session)
                    )

                except Exception as e:
                    issue = ConsistencyIssue(
                        check_type="metadata",
                        severity="error",
                        system="md",
                        entity_type="entry",
                        entity_id=entry_db.date.isoformat(),
                        message=f"Error parsing markdown file: {e}",
                        suggestion=f"Check file: {entry_db.file_path}",
                    )
                    issues.append(issue)
                    self.report.add_issue(issue)

        if self.logger:
            self.logger.log_info(f"Found {len(issues)} metadata consistency issues")

        return issues

    def check_referential_integrity(self) -> List[ConsistencyIssue]:
        """
        Check referential integrity constraints.

        Returns:
            List of referential integrity issues
        """
        issues = []
        self.report.checks_performed += 1

        if self.logger:
            self.logger.log_info("Checking referential integrity...")

        with self.db.session_scope() as session:
            for entry in session.query(Entry).all():
                # Check location-city integrity
                for location in entry.locations:
                    if location.city is None:
                        issue = ConsistencyIssue(
                            check_type="references",
                            severity="error",
                            system="db",
                            entity_type="location",
                            entity_id=location.name,
                            message=f"Location '{location.name}' has no parent city (entry: {entry.date})",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

                # Check related entries exist
                for related in entry.related_entries:
                    if related is None:
                        issue = ConsistencyIssue(
                            check_type="references",
                            severity="error",
                            system="db",
                            entity_type="entry",
                            entity_id=entry.date.isoformat(),
                            message=f"Entry has null related_entry reference",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

                # Check poem version integrity
                for poem_version in entry.poems:
                    if poem_version.poem is None:
                        issue = ConsistencyIssue(
                            check_type="references",
                            severity="error",
                            system="db",
                            entity_type="poem_version",
                            entity_id=str(poem_version.id),
                            message=f"PoemVersion references deleted poem (entry: {entry.date})",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

        if self.logger:
            self.logger.log_info(f"Found {len(issues)} referential integrity issues")

        return issues

    def check_file_integrity(self) -> List[ConsistencyIssue]:
        """
        Check file hash integrity.

        Returns:
            List of file integrity issues
        """
        issues = []
        self.report.checks_performed += 1

        if self.logger:
            self.logger.log_info("Checking file integrity...")

        with self.db.session_scope() as session:
            for entry in session.query(Entry).all():
                if not entry.file_path:
                    continue

                file_path = Path(entry.file_path)
                if not file_path.exists():
                    # Already caught by existence check
                    continue

                # Check file hash if available
                if entry.file_hash:
                    try:
                        from dev.utils import fs

                        current_hash = fs.get_file_hash(file_path)
                        if current_hash != entry.file_hash:
                            issue = ConsistencyIssue(
                                check_type="integrity",
                                severity="warning",
                                system="md-db",
                                entity_type="entry",
                                entity_id=entry.date.isoformat(),
                                message=f"File hash mismatch (file modified since last sync)",
                                suggestion="Run: python -m dev.pipeline.cli yaml2sql --force",
                            )
                            issues.append(issue)
                            self.report.add_issue(issue)
                    except Exception as e:
                        issue = ConsistencyIssue(
                            check_type="integrity",
                            severity="error",
                            system="md",
                            entity_type="entry",
                            entity_id=entry.date.isoformat(),
                            message=f"Error computing file hash: {e}",
                        )
                        issues.append(issue)
                        self.report.add_issue(issue)

        if self.logger:
            self.logger.log_info(f"Found {len(issues)} file integrity issues")

        return issues

    # Helper methods

    def _get_md_dates(self) -> Set[str]:
        """Get all date strings from markdown files."""
        dates = set()
        for md_file in self.md_dir.glob("**/*.md"):
            try:
                date_str = md_file.stem
                if DataValidator.validate_date_string(date_str):
                    dates.add(date_str)
            except Exception:
                pass
        return dates

    def _get_db_dates(self) -> Set[str]:
        """Get all date strings from database."""
        with self.db.session_scope() as session:
            return {e.date.isoformat() for e in session.query(Entry).all()}

    def _get_wiki_dates(self) -> Set[str]:
        """Get all date strings from wiki entries."""
        dates = set()
        entries_dir = self.wiki_dir / "entries"
        if entries_dir.exists():
            for wiki_file in entries_dir.glob("**/*.md"):
                try:
                    date_str = wiki_file.stem
                    if DataValidator.validate_date_string(date_str):
                        dates.add(date_str)
                except Exception:
                    pass
        return dates

    def _check_people_consistency(
        self, entry_md: MdEntry, entry_db: Entry, session
    ) -> List[ConsistencyIssue]:
        """Check people field consistency between MD and DB."""
        issues = []

        # Get MD people count
        md_people = entry_md.metadata.get("people", [])
        md_people_count = len(md_people) if isinstance(md_people, list) else 0

        # Get DB people + aliases count
        db_people_count = len(entry_db.people)
        db_aliases_count = len(entry_db.aliases_used)

        # Compare counts (approximate check)
        if md_people_count > 0 and db_people_count == 0:
            issue = ConsistencyIssue(
                check_type="metadata",
                severity="warning",
                system="md-db",
                entity_type="entry",
                entity_id=entry_db.date.isoformat(),
                message=f"People in MD ({md_people_count}) but none in DB",
                suggestion="Run: python -m dev.pipeline.cli yaml2sql --force",
            )
            issues.append(issue)
            self.report.add_issue(issue)

        return issues

    def _check_locations_consistency(
        self, entry_md: MdEntry, entry_db: Entry, session
    ) -> List[ConsistencyIssue]:
        """Check locations field consistency between MD and DB."""
        issues = []

        # Get MD locations count
        md_locations = entry_md.metadata.get("locations", [])
        if isinstance(md_locations, list):
            md_loc_count = len(md_locations)
        elif isinstance(md_locations, dict):
            md_loc_count = sum(len(locs) for locs in md_locations.values())
        else:
            md_loc_count = 0

        # Get DB locations count
        db_loc_count = len(entry_db.locations)

        # Compare counts
        if md_loc_count > 0 and db_loc_count == 0:
            issue = ConsistencyIssue(
                check_type="metadata",
                severity="warning",
                system="md-db",
                entity_type="entry",
                entity_id=entry_db.date.isoformat(),
                message=f"Locations in MD ({md_loc_count}) but none in DB",
                suggestion="Run: python -m dev.pipeline.cli yaml2sql --force",
            )
            issues.append(issue)
            self.report.add_issue(issue)

        return issues

    def _check_tags_consistency(
        self, entry_md: MdEntry, entry_db: Entry, session
    ) -> List[ConsistencyIssue]:
        """Check tags field consistency between MD and DB."""
        issues = []

        # Get MD tags
        md_tags = set(entry_md.metadata.get("tags", []))

        # Get DB tags
        db_tags = {tag.tag for tag in entry_db.tags}

        # Check for missing tags
        missing_in_db = md_tags - db_tags
        if missing_in_db:
            issue = ConsistencyIssue(
                check_type="metadata",
                severity="warning",
                system="md-db",
                entity_type="entry",
                entity_id=entry_db.date.isoformat(),
                message=f"Tags in MD but not DB: {', '.join(missing_in_db)}",
                suggestion="Run: python -m dev.pipeline.cli yaml2sql --force",
            )
            issues.append(issue)
            self.report.add_issue(issue)

        return issues


def format_consistency_report(report: ConsistencyValidationReport) -> str:
    """
    Format consistency validation report as readable text.

    Args:
        report: Validation report to format

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("CONSISTENCY VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append(f"Checks Performed: {report.checks_performed}")
    lines.append(f"Total Warnings: {report.total_warnings}")
    lines.append(f"Total Errors: {report.total_errors}")
    lines.append("")

    # Overall status
    if report.is_healthy:
        lines.append("✅ ALL SYSTEMS CONSISTENT")
    else:
        lines.append("❌ CONSISTENCY ISSUES FOUND")
    lines.append("")

    # Group issues by system and type
    if report.issues:
        issues_by_system: Dict[str, List[ConsistencyIssue]] = defaultdict(list)
        for issue in report.issues:
            issues_by_system[issue.system].append(issue)

        lines.append("ISSUES BY SYSTEM:")
        lines.append("")

        for system in sorted(issues_by_system.keys()):
            system_issues = issues_by_system[system]
            errors = [i for i in system_issues if i.severity == "error"]
            warnings = [i for i in system_issues if i.severity == "warning"]

            icon = "❌" if errors else "⚠️"
            lines.append(f"{icon} {system.upper()} ({len(errors)} errors, {len(warnings)} warnings)")

            # Group by check type
            by_type: Dict[str, List[ConsistencyIssue]] = defaultdict(list)
            for issue in system_issues:
                by_type[issue.check_type].append(issue)

            for check_type in sorted(by_type.keys()):
                type_issues = by_type[check_type]
                lines.append(f"\n   {check_type.upper()}:")

                for issue in type_issues[:5]:  # Limit to 5 per type
                    severity_icon = "❌" if issue.severity == "error" else "⚠️"
                    lines.append(
                        f"   {severity_icon} [{issue.entity_type}:{issue.entity_id}] {issue.message}"
                    )
                    if issue.suggestion:
                        lines.append(f"      💡 {issue.suggestion}")

                if len(type_issues) > 5:
                    lines.append(f"      ... and {len(type_issues) - 5} more")

            lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)

#!/usr/bin/env python3
"""
consistency.py
-------------
Cross-system consistency validation for Palimpsest.

Validates consistency between:
- Markdown files (MD)
- Metadata YAML files
- Database (DB)

Checks for:
- Entry existence across systems (MD <-> DB)
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
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry
from dev.core.paths import JOURNAL_DIR
from dev.core.validators import DataValidator
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.validators.diagnostic import Diagnostic, ValidationReport


class ConsistencyValidator:
    """Validates consistency across MD and DB systems."""

    def __init__(
        self,
        db: PalimpsestDB,
        md_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize consistency validator.

        Args:
            db: Database manager instance
            md_dir: Directory containing markdown files
            logger: Optional logger instance
        """
        self.db = db
        self.md_dir = md_dir
        self.logger = logger

    def validate_all(self) -> ValidationReport:
        """
        Run all consistency checks.

        Returns:
            ValidationReport with all diagnostics
        """
        report = ValidationReport()

        report.diagnostics.extend(self.check_entry_existence())
        report.diagnostics.extend(self.check_entry_metadata())
        report.diagnostics.extend(self.check_referential_integrity())
        report.diagnostics.extend(self.check_file_integrity())

        return report

    def check_entry_existence(self) -> List[Diagnostic]:
        """
        Check entry existence across MD <-> DB.

        Returns:
            List of ENTRY_EXISTENCE diagnostics
        """
        diagnostics: List[Diagnostic] = []

        safe_logger(self.logger).log_info("Checking entry existence across systems...")

        # Get entry dates from each system
        md_dates = self._get_md_dates()
        db_dates = self._get_db_dates()

        # MD but not DB (parsing failed or sync not run)
        md_only = md_dates - db_dates
        for date_str in md_only:
            diagnostics.append(Diagnostic(
                file="", line=0, col=0, end_line=0, end_col=0,
                severity="error", code="ENTRY_EXISTENCE",
                message=(
                    f"[md-db] Entry {date_str}: "
                    f"Entry exists in markdown but not in database"
                ),
            ))

        # DB but not MD (file deleted or moved)
        with self.db.session_scope() as session:
            for entry in session.query(Entry).all():
                if entry.file_path:
                    file_path = JOURNAL_DIR / entry.file_path
                    if not file_path.exists():
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="ENTRY_EXISTENCE",
                            message=(
                                f"[db-md] Entry {entry.date.isoformat()}: "
                                f"Entry in database but file missing: {entry.file_path}"
                            ),
                        ))

        safe_logger(self.logger).log_info(f"Found {len(diagnostics)} entry existence issues")

        return diagnostics

    def check_entry_metadata(self) -> List[Diagnostic]:
        """
        Check metadata synchronization between MD and DB.

        Returns:
            List of METADATA_MISMATCH diagnostics
        """
        diagnostics: List[Diagnostic] = []

        safe_logger(self.logger).log_info("Checking entry metadata consistency...")

        with self.db.session_scope() as session:
            for entry_db in session.query(Entry).all():
                if not entry_db.file_path or not (JOURNAL_DIR / entry_db.file_path).exists():
                    continue

                try:
                    # Parse frontmatter directly from MD file
                    content = (JOURNAL_DIR / entry_db.file_path).read_text(encoding="utf-8")
                    if not content.startswith("---"):
                        continue
                    parts = content.split("---", 2)
                    if len(parts) < 3:
                        continue
                    frontmatter = yaml.safe_load(parts[1]) or {}

                    # Check core fields
                    md_date = DataValidator.normalize_date(frontmatter.get("date"))
                    if md_date and md_date != entry_db.date:
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="METADATA_MISMATCH",
                            message=(
                                f"[md-db] Entry {entry_db.date.isoformat()}: "
                                f"Date mismatch: MD={md_date}, DB={entry_db.date}"
                            ),
                        ))

                    # Check word count
                    md_word_count = frontmatter.get("word_count", 0)
                    if md_word_count and int(md_word_count) != entry_db.word_count:
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="warning", code="METADATA_MISMATCH",
                            message=(
                                f"[md-db] Entry {entry_db.date.isoformat()}: "
                                f"Word count mismatch: MD={md_word_count}, DB={entry_db.word_count}"
                            ),
                        ))

                    # Check relationship counts
                    diagnostics.extend(
                        self._check_people_consistency(frontmatter, entry_db, session)
                    )
                    diagnostics.extend(
                        self._check_locations_consistency(frontmatter, entry_db, session)
                    )
                    diagnostics.extend(
                        self._check_tags_consistency(frontmatter, entry_db, session)
                    )

                except Exception as e:
                    diagnostics.append(Diagnostic(
                        file="", line=0, col=0, end_line=0, end_col=0,
                        severity="error", code="METADATA_MISMATCH",
                        message=(
                            f"[md] Entry {entry_db.date.isoformat()}: "
                            f"Error parsing markdown file: {e}"
                        ),
                    ))

        safe_logger(self.logger).log_info(f"Found {len(diagnostics)} metadata consistency issues")

        return diagnostics

    def check_referential_integrity(self) -> List[Diagnostic]:
        """
        Check referential integrity constraints.

        Returns:
            List of FK_VIOLATION diagnostics
        """
        diagnostics: List[Diagnostic] = []

        safe_logger(self.logger).log_info("Checking referential integrity...")

        with self.db.session_scope() as session:
            for entry in session.query(Entry).all():
                # Check location-city integrity
                for location in entry.locations:
                    if location.city is None:
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="FK_VIOLATION",
                            message=(
                                f"[db] Location '{location.name}': "
                                f"has no parent city (entry: {entry.date})"
                            ),
                        ))

                # Check related entries exist
                for related in entry.related_entries:
                    if related is None:
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="FK_VIOLATION",
                            message=(
                                f"[db] Entry {entry.date.isoformat()}: "
                                f"has null related_entry reference"
                            ),
                        ))

                # Check poem version integrity
                for poem_version in entry.poems:
                    if poem_version.poem is None:
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="FK_VIOLATION",
                            message=(
                                f"[db] PoemVersion {poem_version.id}: "
                                f"references deleted poem (entry: {entry.date})"
                            ),
                        ))

        safe_logger(self.logger).log_info(f"Found {len(diagnostics)} referential integrity issues")

        return diagnostics

    def check_file_integrity(self) -> List[Diagnostic]:
        """
        Check file hash integrity.

        Returns:
            List of FILE_HASH_MISMATCH diagnostics
        """
        diagnostics: List[Diagnostic] = []

        safe_logger(self.logger).log_info("Checking file integrity...")

        with self.db.session_scope() as session:
            for entry in session.query(Entry).all():
                if not entry.file_path:
                    continue

                file_path = JOURNAL_DIR / entry.file_path
                if not file_path.exists():
                    # Already caught by existence check
                    continue

                # Check file hash if available
                if entry.file_hash:
                    try:
                        from dev.utils import fs

                        current_hash = fs.get_file_hash(file_path)
                        if current_hash != entry.file_hash:
                            diagnostics.append(Diagnostic(
                                file="", line=0, col=0, end_line=0, end_col=0,
                                severity="warning", code="FILE_HASH_MISMATCH",
                                message=(
                                    f"[md-db] Entry {entry.date.isoformat()}: "
                                    f"File hash mismatch (file modified since last sync)"
                                ),
                            ))
                    except Exception as e:
                        diagnostics.append(Diagnostic(
                            file="", line=0, col=0, end_line=0, end_col=0,
                            severity="error", code="FILE_HASH_MISMATCH",
                            message=(
                                f"[md] Entry {entry.date.isoformat()}: "
                                f"Error computing file hash: {e}"
                            ),
                        ))

        safe_logger(self.logger).log_info(f"Found {len(diagnostics)} file integrity issues")

        return diagnostics

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

    def _check_people_consistency(
        self, frontmatter: Dict[str, Any], entry_db: Entry, session: Any
    ) -> List[Diagnostic]:
        """Check people field consistency between MD and DB."""
        diagnostics: List[Diagnostic] = []

        # Get MD people count
        md_people = frontmatter.get("people", [])
        md_people_count = len(md_people) if isinstance(md_people, list) else 0

        # Get DB people count
        db_people_count = len(entry_db.people)

        # Compare counts (approximate check)
        if md_people_count > 0 and db_people_count == 0:
            diagnostics.append(Diagnostic(
                file="", line=0, col=0, end_line=0, end_col=0,
                severity="warning", code="METADATA_MISMATCH",
                message=(
                    f"[md-db] Entry {entry_db.date.isoformat()}: "
                    f"People in MD ({md_people_count}) but none in DB"
                ),
            ))

        return diagnostics

    def _check_locations_consistency(
        self, frontmatter: Dict[str, Any], entry_db: Entry, session: Any
    ) -> List[Diagnostic]:
        """Check locations field consistency between MD and DB."""
        diagnostics: List[Diagnostic] = []

        # Get MD locations count
        md_locations = frontmatter.get("locations", [])
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
            diagnostics.append(Diagnostic(
                file="", line=0, col=0, end_line=0, end_col=0,
                severity="warning", code="METADATA_MISMATCH",
                message=(
                    f"[md-db] Entry {entry_db.date.isoformat()}: "
                    f"Locations in MD ({md_loc_count}) but none in DB"
                ),
            ))

        return diagnostics

    def _check_tags_consistency(
        self, frontmatter: Dict[str, Any], entry_db: Entry, session: Any
    ) -> List[Diagnostic]:
        """Check tags field consistency between MD and DB."""
        diagnostics: List[Diagnostic] = []

        # Get MD tags
        md_tags = set(frontmatter.get("tags", []))

        # Get DB tags
        db_tags = {tag.name for tag in entry_db.tags}

        # Check for missing tags
        missing_in_db = md_tags - db_tags
        if missing_in_db:
            diagnostics.append(Diagnostic(
                file="", line=0, col=0, end_line=0, end_col=0,
                severity="warning", code="METADATA_MISMATCH",
                message=(
                    f"[md-db] Entry {entry_db.date.isoformat()}: "
                    f"Tags in MD but not DB: {', '.join(missing_in_db)}"
                ),
            ))

        return diagnostics

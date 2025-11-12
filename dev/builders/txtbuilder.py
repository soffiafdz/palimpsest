#!/usr/bin/env python3
"""
txtbuilder.py
-------------------
Process raw 750words exports from inbox directory.

Handles:
- File validation and renaming to standard format
- Year-based grouping and organization
- Running format script on each file
- Archiving processed originals

This module provides the TxtBuilder class used by src2txt.py
for converting raw exports into formatted text files.

Usage:
    builder = TxtBuilder(
        inbox_dir=Path("journal/inbox"),
        output_dir=Path("journal/txt"),
        format_script=Path("dev/bin/init_format"),
        logger=logger
    )
    stats = builder.build()
"""
from __future__ import annotations

import os
import re
import subprocess
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from dev.core.exceptions import TxtBuildError
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import FORMATTING_SCRIPT


# ----- Entry Processing Constants -----
ENTRY_MARKERS = {"------ ENTRY ------", "===== ENTRY ====="}
DATE_PATTERN = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


class ProcessingStats:
    """Track inbox processing statistics."""

    def __init__(self) -> None:
        self.files_found: int = 0
        self.files_processed: int = 0
        self.files_skipped: int = 0
        self.years_updated: int = 0
        self.errors: int = 0
        self.start_time: datetime = datetime.now()

    def duration(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def summary(self) -> str:
        """Get formatted summary."""
        return (
            f"{self.files_found} found, "
            f"{self.files_processed} processed, "
            f"{self.files_skipped} skipped, "
            f"{self.errors} errors in {self.duration():.2f}s"
        )


class TxtBuilder:
    """
    Process raw 750words exports into formatted text files.

    Validates, renames, formats, and archives journal export files
    from an inbox directory, organizing them by year.

    Attributes:
        inbox_dir: Directory containing raw exports
        output_dir: Base output directory for formatted files
        archive_dir: Directory for archived originals
        format_script: Path to formatting script
        logger: Optional logger for operations
    """

    # Expected filename patterns
    FILENAME_PATTERN = re.compile(r"(\d{4})[_-](\d{2})")
    STANDARD_FORMAT = "journal_{year}_{month}.txt"

    def __init__(
        self,
        inbox_dir: Path,
        output_dir: Path,
        archive_dir: Optional[Path] = None,
        format_script: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize TxtBuilder.

        Args:
            inbox_dir: Directory with raw export files
            output_dir: Base output directory (creates YYYY subdirs)
            archive_dir: Archive directory (defaults to inbox_dir/../archive)
            format_script: Format script path (defaults to dev/bin/init_format)
            logger: Optional logger
        """
        self.inbox_dir = inbox_dir
        self.output_dir = output_dir
        self.archive_dir = (
            archive_dir if archive_dir is not None else (inbox_dir.parent / "archive")
        )
        self.format_script = (
            format_script if format_script is not None else FORMATTING_SCRIPT
        )
        self.logger = logger

    def _parse_filename(self, filename: str) -> Optional[tuple[str, str]]:
        """
        Extract year and month from filename.

        Supports: YYYY_MM.txt, YYYY-MM.txt, journal_YYYY_MM.txt

        Args:
            filename: Name of file to parse

        Returns:
            Tuple of (year, month) or None if invalid
        """
        match = self.FILENAME_PATTERN.search(filename)
        if match:
            return match.group(1), match.group(2)
        return None

    def _rename_to_standard(self, file_path: Path) -> Optional[Path]:
        """
        Rename file to standard format: journal_YYYY_MM.txt

        Args:
            file_path: Path to file

        Returns:
            New path if renamed, original if already standard, None if invalid
        """
        filename = file_path.name
        parsed = self._parse_filename(filename)

        if not parsed:
            if self.logger:
                self.logger.log_warning(f"Cannot parse filename: {filename}")
            return None

        year, month = parsed
        standard_name = self.STANDARD_FORMAT.format(year=year, month=month)

        if filename == standard_name:
            return file_path

        new_path = file_path.parent / standard_name

        try:
            file_path.rename(new_path)
            if self.logger:
                self.logger.log_debug(f"Renamed: {filename} → {standard_name}")
            return new_path
        except FileExistsError:
            if self.logger:
                self.logger.log_warning(
                    f"Target exists, skipping rename: {standard_name}"
                )
            return file_path
        except OSError as e:
            if self.logger:
                self.logger.log_error(
                    e, {"operation": "rename", "file": str(file_path)}
                )
            return None

    def _get_existing_dates(self, file_path: Path) -> Set[str]:
        """
        Extract dates from an existing output file without modifying content.

        Args:
            file_path: Path to existing output file

        Returns:
            Set of date strings (YYYY-MM-DD) found in the file
        """
        if not file_path.exists():
            return set()

        try:
            content = file_path.read_text(encoding="utf-8")
            # Match "Date: YYYY-MM-DD" pattern
            dates = {match.group(1) for match in DATE_PATTERN.finditer(content)}

            if self.logger:
                self.logger.log_debug(
                    f"Found {len(dates)} existing dates in {file_path.name}"
                )

            return dates

        except (OSError, UnicodeDecodeError) as e:
            if self.logger:
                self.logger.log_warning(
                    f"Could not read existing file {file_path.name}: {e}"
                )
            return set()

    def _filter_new_entries(self, content: str, existing_dates: set) -> str:
        """
        Filter formatted content to only include entries with new dates.

        Args:
            content: Formatted content from format script
            existing_dates: Set of dates already in output file

        Returns:
            Filtered content with only new entries
        """
        if not existing_dates:
            return content

        # Split content into entries
        entries = []
        current_entry = []
        entry_date = None

        for line in content.splitlines():
            # Check if this is a new entry marker
            if line.strip() in ENTRY_MARKERS:
                # Save previous entry if it's new
                if current_entry and (entry_date is None or entry_date not in existing_dates):
                    entries.append("\n".join(current_entry))
                # Start new entry
                current_entry = [line]
                entry_date = None
            else:
                # Check if this line contains a date
                date_match = DATE_PATTERN.match(line)
                if date_match:
                    entry_date = date_match.group(1)
                current_entry.append(line)

        # Don't forget the last entry
        if current_entry and (entry_date is None or entry_date not in existing_dates):
            entries.append("\n".join(current_entry))

        if self.logger:
            self.logger.log_debug(
                f"Filtered to {len(entries)} new entries "
                f"(skipped {len(existing_dates)} existing)"
            )

        return "\n\n".join(entries)

    def _format_file(self, input_file: Path, output_file: Path) -> bool:
        """
        Run format script on input file and merge with existing output.

        If output_file exists, only appends entries with dates not already present.
        If output_file doesn't exist, creates new file with all entries.

        Args:
            input_file: Input file path
            output_file: Output file path

        Returns:
            True if successful, False otherwise
        """
        if not self.format_script.exists():
            raise TxtBuildError(f"Format script not found: {self.format_script}")
        if not os.access(self.format_script, os.X_OK):
            raise TxtBuildError(f"Format script not executable: {self.format_script}")

        try:
            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Check for existing dates if file exists
            existing_dates = self._get_existing_dates(output_file)

            # Run format script
            result = subprocess.run(
                [str(self.format_script), str(input_file)],
                capture_output=True,
                text=True,
                check=True,
            )

            # Filter to only new entries if file exists
            formatted_content = result.stdout
            if existing_dates:
                filtered_content = self._filter_new_entries(formatted_content, existing_dates)

                if not filtered_content.strip():
                    if self.logger:
                        self.logger.log_info(
                            f"No new entries to add to {output_file.name}"
                        )
                    return True

                # Read existing content
                existing_content = output_file.read_text(encoding="utf-8")

                # Ensure proper separation
                if existing_content and not existing_content.endswith("\n\n"):
                    if existing_content.endswith("\n"):
                        filtered_content = "\n" + filtered_content
                    else:
                        filtered_content = "\n\n" + filtered_content

                # Append new entries
                output_file.write_text(existing_content + filtered_content, encoding="utf-8")

                if self.logger:
                    self.logger.log_debug(
                        f"Merged: {input_file.name} → {output_file.name} (appended new entries)"
                    )
            else:
                # No existing file, write all content
                output_file.write_text(formatted_content, encoding="utf-8")

                if self.logger:
                    self.logger.log_debug(
                        f"Formatted: {input_file.name} → {output_file.name}"
                    )

            return True

        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.log_error(
                    e,
                    {
                        "operation": "format",
                        "input": str(input_file),
                        "stderr": e.stderr,
                    },
                )
            return False
        except OSError as e:
            if self.logger:
                self.logger.log_error(
                    e, {"operation": "write_output", "file": str(output_file)}
                )
            return False

    def _archive_files(self, files: List[Path], archive_path: Path) -> bool:
        """
        Archive processed files to zip.

        Args:
            files: List of files to archive
            archive_path: Path to archive file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure archive directory exists
            archive_path.parent.mkdir(parents=True, exist_ok=True)

            # Create or update archive
            mode = "a" if archive_path.exists() else "w"
            action = "updating" if archive_path.exists() else "creating"

            with zipfile.ZipFile(archive_path, mode, zipfile.ZIP_DEFLATED) as zf:
                for file_path in files:
                    if file_path.exists():
                        zf.write(file_path, file_path.name)

            if self.logger:
                self.logger.log_operation(
                    "archive_created",
                    {
                        "action": action,
                        "archive": str(archive_path),
                        "count": len(files),
                    },
                )

            # Remove original files after successful archiving
            for file_path in files:
                if file_path.exists():
                    file_path.unlink()

            return True

        except (OSError, zipfile.BadZipFile) as e:
            if self.logger:
                self.logger.log_error(
                    e, {"operation": "archive", "archive": str(archive_path)}
                )
            return False

    def build(self) -> ProcessingStats:
        """
        Execute complete inbox processing.

        Processes all files in inbox:
        1. Validates and renames files
        2. Groups by year
        3. Formats each file
        4. Archives originals

        Returns:
            ProcessingStats with results

        Raises:
            TxtBuildError: If critical failure occurs
        """
        stats = ProcessingStats()

        if self.logger:
            self.logger.log_operation(
                "inbox_build_start",
                {"inbox": str(self.inbox_dir), "output": str(self.output_dir)},
            )

        # Validate directories
        if not self.inbox_dir.exists():
            raise TxtBuildError(f"Inbox directory not found: {self.inbox_dir}")

        # Find all text files
        txt_files = list(self.inbox_dir.glob("*.txt"))
        stats.files_found = len(txt_files)

        if stats.files_found == 0:
            if self.logger:
                self.logger.log_info(f"No files found in inbox: {self.inbox_dir}")
            return stats

        if self.logger:
            self.logger.log_debug(f"Found {stats.files_found} files in inbox")

        # Group files by year
        year_files: Dict[str, List[Path]] = defaultdict(list)

        for file_path in txt_files:
            # Rename to standard format
            renamed = self._rename_to_standard(file_path)

            if not renamed:
                stats.files_skipped += 1
                continue

            # Parse year/month
            parsed = self._parse_filename(renamed.name)
            if not parsed:
                stats.files_skipped += 1
                continue

            year, _ = parsed
            year_files[year].append(renamed)

        # Process each year
        for year, files in sorted(year_files.items()):
            if self.logger:
                self.logger.log_debug(f"Processing {len(files)} files for year {year}")

            year_dir = self.output_dir / year
            year_archive = self.archive_dir / f"{year}.zip"

            processed_files = []

            for file_path in files:
                parsed = self._parse_filename(file_path.name)
                if not parsed:
                    continue

                _, month = parsed

                # Format file
                output_file = year_dir / f"{year}-{month}.txt"

                if self._format_file(file_path, output_file):
                    stats.files_processed += 1
                    processed_files.append(file_path)
                else:
                    stats.errors += 1

            # Archive processed files
            if processed_files:
                if self._archive_files(processed_files, year_archive):
                    stats.years_updated += 1
                else:
                    stats.errors += 1

        if self.logger:
            self.logger.log_operation(
                "inbox_build_complete", {"stats": stats.summary()}
            )

        return stats

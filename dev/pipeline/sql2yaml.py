#!/usr/bin/env python3
"""
sql2yaml.py
-----------
Export database entries to Markdown files with rich YAML frontmatter.

This pipeline converts structured database records into human-editable
Markdown files with comprehensive YAML metadata. It's the inverse of
yaml2sql, enabling bidirectional data flow.

Features:
- Export entries with complete relationship metadata
- Generate human-readable YAML frontmatter
- Preserve existing body content (or regenerate from database)
- Handle manuscript metadata
- Batch export with filtering
- Update existing files or create new ones

Usage:
    # Export single entry
    sql2yaml export 2024-01-15 -o output/

    # Export date range
    sql2yaml range 2024-01-01 2024-01-31 -o output/

    # Export all entries
    sql2yaml all -o output/
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from dev.dataclasses.md_entry import MdEntry
from dev.database.models import Entry
from dev.core.exceptions import Sql2YamlError
from dev.core.logging_manager import PalimpsestLogger

from dev.utils import md


def export_entry_to_markdown(
    entry: Entry,
    output_dir: Path,
    force_overwrite: bool = False,
    preserve_body: bool = True,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single database entry to Markdown file with complete YAML frontmatter.

    Implementation Logic:
    ---------------------
    Core function for sql2yaml pipeline. Reads a database Entry ORM object,
    converts all relationships to YAML frontmatter, and generates a human-editable
    Markdown file. Handles content preservation to avoid losing text.

    Processing Flow:
    1. Determine output file path (output_dir/YYYY/YYYY-MM-DD.md)
    2. Check for existing file (skip if exists unless force_overwrite)
    3. Retrieve/preserve body content (three strategies)
    4. Convert database Entry to MdEntry dataclass
    5. Generate complete Markdown with YAML frontmatter
    6. Write to file with UTF-8 encoding
    7. Return status for statistics tracking

    Content Preservation Strategies:
    Three strategies in priority order:

    1. preserve_body=True + file exists:
       - Reads existing .md file
       - Extracts body content (everything after frontmatter)
       - Combines with NEW frontmatter from database
       - Use case: Database edits while preserving text

    2. entry.file_path exists:
       - Reads body from original source file
       - Uses entry.file_path from database
       - Use case: Initial export from database

    3. No existing content:
       - Generates placeholder body with date
       - Minimal fallback for missing content
       - Use case: New entries without source files

    YAML Generation from Database:
    - Loads all relationships via SQLAlchemy ORM
    - People: Formats names with hyphens/aliases
    - Locations: Organizes by city hierarchy
    - Events: List of event identifiers
    - Tags: List of tag names
    - References: Includes sources and context
    - Poems: Includes versions and revisions
    - Manuscript: Editorial metadata if present

    File Organization:
    - Creates year-based directories automatically
    - Filename format: YYYY-MM-DD.md
    - Example: md/2024/2024-01-15.md

    Status Return Values:
    - "created": New file written (didn't exist)
    - "updated": Existing file overwritten
    - "skipped": File exists and not force_overwrite

    Database Read Operations:
    - Entry loaded with all relationships (eager loading)
    - No database modifications (export is read-only)
    - Relationship data accessed via ORM navigation
    - Example: entry.people, entry.locations, entry.tags

    Error Handling:
    - MdEntry creation failures logged with context
    - Markdown generation failures logged with context
    - File write failures logged with context
    - All failures raise Sql2YamlError with original exception

    Use Cases:
    - Restore .md files from database backup
    - Propagate database edits back to files
    - Generate fresh Markdown from imported data
    - Bidirectional synchronization with yaml2sql

    Args:
        entry: SQLAlchemy Entry ORM instance with relationships loaded
        output_dir: Base output directory (typically MD_DIR)
        force_overwrite: If True, overwrite existing files
        preserve_body: If True, preserve existing body content
        logger: Optional logger for operation tracking

    Returns:
        Status string: "created", "updated", or "skipped"

    Raises:
        Sql2YamlError: If export fails (MdEntry creation, markdown generation, file write)
    """
    if logger:
        logger.log_debug(f"Exporting entry {entry.date}")

    # Determine output path
    year_dir: Path = output_dir / str(entry.date.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    filename: str = f"{entry.date.isoformat()}.md"
    output_path: Path = year_dir / filename

    # Check if file exists
    file_existed: bool = output_path.exists()

    if file_existed and not force_overwrite:
        if logger:
            logger.log_debug(f"File exists, skipping: {output_path.name}")
        return "skipped"

    # Get body content
    body_lines: List[str]
    if preserve_body and file_existed:
        # Preserve existing body
        body_lines = md.read_entry_body(output_path)
        if logger:
            logger.log_debug(f"Preserved body: {len(body_lines)} lines")
    elif entry.file_path and Path(entry.file_path).exists():
        # Read from original file
        body_lines = md.read_entry_body(Path(entry.file_path))
        if logger:
            logger.log_debug(f"Loaded body from: {entry.file_path}")
    else:
        body_lines = md.generate_placeholder_body(entry.date)
        if logger:
            logger.log_debug("Generated placeholder body")

    # Create MdEntry from database
    try:
        md_entry: MdEntry = MdEntry.from_database(entry, body_lines, output_path)
    except Exception as e:
        if logger:
            logger.log_error(
                e, {"operation": "create_mdentry", "date": str(entry.date)}
            )
        raise Sql2YamlError(f"Failed to create MdEntry: {e}") from e

    # Generate markdown
    try:
        markdown_content: str = md_entry.to_markdown()
    except Exception as e:
        if logger:
            logger.log_error(
                e, {"operation": "generate_markdown", "date": str(entry.date)}
            )
        raise Sql2YamlError(f"Failed to generate markdown: {e}") from e

    # Write file
    try:
        output_path.write_text(markdown_content, encoding="utf-8")

        if logger:
            action: str = "updated" if file_existed else "created"
            logger.log_operation(
                f"entry_{action}", {"date": str(entry.date), "file": str(output_path)}
            )

        return "updated" if file_existed else "created"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "write_file", "file": str(output_path)})
        raise Sql2YamlError(f"Failed to write file: {e}") from e

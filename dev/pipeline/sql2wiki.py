#!/usr/bin/env python3
"""
sql2wiki.py
-----------
Export database entities to Vimwiki pages.

This pipeline converts structured database records into human-readable
vimwiki entity pages (people, themes, tags, etc.). It's the inverse of
wiki2sql, enabling bidirectional data flow for wiki entities.

Features:
- Export people with complete relationship metadata
- Generate human-readable wiki markdown
- Preserve existing manual edits (notes, vignettes, categories)
- Handle all entity types (people, themes, tags, poems, references)
- Batch export with filtering
- Update existing files or create new ones

Usage:
    # Export all people
    python -m dev.pipeline.sql2wiki export people

    # Export specific entity types
    python -m dev.pipeline.sql2wiki export themes
    python -m dev.pipeline.sql2wiki export tags

    # Export all entities
    python -m dev.pipeline.sql2wiki export all

    # Force regeneration even if files exist
    python -m dev.pipeline.sql2wiki export people --force
"""
from __future__ import annotations

import sys
import click
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.dataclasses.wiki_tag import Tag as WikiTag
from dev.dataclasses.wiki_poem import Poem as WikiPoem
from dev.dataclasses.wiki_reference import Reference as WikiReference
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.wiki_location import Location as WikiLocation
from dev.dataclasses.wiki_city import City as WikiCity
from dev.dataclasses.wiki_event import Event as WikiEvent
from dev.database.models import (
    Person as DBPerson,
    Entry as DBEntry,
    Tag as DBTag,
    Poem as DBPoem,
    ReferenceSource as DBReferenceSource,
    Location as DBLocation,
    City as DBCity,
    Event as DBEvent,
)
from dev.database.models_manuscript import Theme as DBTheme
from dev.database.manager import PalimpsestDB

from dev.core.paths import (
    LOG_DIR, DB_PATH, ALEMBIC_DIR, BACKUP_DIR, ROOT,
    WIKI_DIR, MD_DIR
)
from dev.core.exceptions import Sql2WikiError
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.cli_utils import setup_logger
from dev.core.cli_stats import ConversionStats

# Category ordering for people index
CATEGORY_ORDER = ["Family", "Friend", "Romantic", "Colleague",
                  "Professional", "Acquaintance", "Public", "Main",
                  "Secondary", "Archive", "Unsorted", "Unknown"]


def _write_if_changed(path: Path, new_lines: List[str], verbose: bool = False) -> bool:
    """
    Write file only if content has changed.

    Args:
        path: Path to file
        new_lines: New content lines
        verbose: Print diff if changed

    Returns:
        True if file was written, False if skipped
    """
    old_lines: List[str] = path.read_text().splitlines() if path.exists() else []

    if old_lines == new_lines:
        return False  # no change

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    if verbose:
        from difflib import unified_diff
        diff = unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            lineterm="",
        )
        print(f"Updated {path.relative_to(ROOT)}")
        for line in diff:
            print(line)

    return True


def export_person(
    db_person: DBPerson,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single person from database to wiki page.

    Args:
        db_person: Database Person model with relationships loaded
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug(f"Exporting person: {db_person.display_name}")

    # Create WikiPerson from database
    try:
        wiki_person = WikiPerson.from_database(db_person, wiki_dir, journal_dir)
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "create_wiki_person",
                "person": db_person.display_name
            })
        raise Sql2WikiError(f"Failed to create WikiPerson: {e}") from e

    # Generate markdown
    try:
        lines = wiki_person.to_wiki()
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "generate_wiki_markdown",
                "person": db_person.display_name
            })
        raise Sql2WikiError(f"Failed to generate wiki markdown: {e}") from e

    # Write to file
    file_existed = wiki_person.path.exists()

    if force or _write_if_changed(wiki_person.path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"person_{status}",
                {"person": db_person.display_name, "file": str(wiki_person.path)}
            )
        return status
    else:
        if logger:
            logger.log_debug(f"Person unchanged: {db_person.display_name}")
        return "skipped"


def build_people_index(
    people: List[WikiPerson],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build the main people index page (vimwiki/people.md).

    Groups people by category and sorts by mention frequency.

    Args:
        people: List of WikiPerson objects
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building people index")

    # Group by category
    by_category: Dict[str, List[WikiPerson]] = defaultdict(list)
    for person in people:
        category = person.category or "Unknown"
        by_category[category].append(person)

    # Build index lines
    lines = [
        "# Palimpsest — People",
        "",
        "Index of all people mentioned in the journal, organized by relationship category.",
        "",
    ]

    # Add each category in order
    for category in CATEGORY_ORDER:
        if category not in by_category:
            continue

        category_people = by_category[category]
        # Sort by mention count (descending), then alphabetically
        category_people.sort(key=lambda p: (-p.mentions, p.name.lower()))

        lines.extend(["", f"## {category}", ""])

        for person in category_people:
            # Format: → [[people/name.md|Name]] (N mentions)
            rel_path = person.path.relative_to(wiki_dir)
            mention_str = f"{person.mentions} mention" + ("s" if person.mentions != 1 else "")
            lines.append(f"- [[{rel_path}|{person.name}]] ({mention_str})")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- Total people: {len(people)}",
        f"- Categories: {len(by_category)}",
    ])

    # Write to file
    index_path = wiki_dir / "people.md"
    file_existed = index_path.exists()

    if force or _write_if_changed(index_path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"people_index_{status}",
                {"file": str(index_path), "people_count": len(people)}
            )
        return status
    else:
        if logger:
            logger.log_debug("People index unchanged")
        return "skipped"


def export_people(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all people from database to wiki pages.

    Creates:
    - vimwiki/people.md (index)
    - vimwiki/people/{name}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_people_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all people with eager loading of relationships
        query = (
            select(DBPerson)
            .options(
                joinedload(DBPerson.aliases),
                joinedload(DBPerson.dates),
                joinedload(DBPerson.entries),
            )
            .where(DBPerson.deleted_at.is_(None))  # Exclude soft-deleted
        )

        db_people = session.execute(query).scalars().unique().all()

        if not db_people:
            if logger:
                logger.log_warning("No people found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_people)} people in database")

        # Export each person
        wiki_people: List[WikiPerson] = []
        for db_person in db_people:
            stats.files_processed += 1

            try:
                status = export_person(db_person, wiki_dir, journal_dir, force, logger)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiPerson for index building
                wiki_person = WikiPerson.from_database(db_person, wiki_dir, journal_dir)
                wiki_people.append(wiki_person)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_person",
                        "person": db_person.display_name
                    })

        # Build index
        try:
            index_status = build_people_index(wiki_people, wiki_dir, force, logger)
            # Don't increment stats for index (counted separately)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_people_index"})

    if logger:
        logger.log_operation("export_people_complete", {"stats": stats.summary()})

    return stats


# ===== THEMES EXPORT =====

def export_theme(
    db_theme: DBTheme,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single theme from database to wiki page.

    Args:
        db_theme: Database Theme model with relationships loaded
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug(f"Exporting theme: {db_theme.theme}")

    # Create WikiTheme from database
    try:
        wiki_theme = WikiTheme.from_database(db_theme, wiki_dir, journal_dir)
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "create_wiki_theme",
                "theme": db_theme.theme
            })
        raise Sql2WikiError(f"Failed to create WikiTheme: {e}") from e

    # Generate markdown
    try:
        lines = wiki_theme.to_wiki()
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "generate_wiki_markdown",
                "theme": db_theme.theme
            })
        raise Sql2WikiError(f"Failed to generate wiki markdown: {e}") from e

    # Write to file
    file_existed = wiki_theme.path.exists()

    if force or _write_if_changed(wiki_theme.path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"theme_{status}",
                {"theme": db_theme.theme, "file": str(wiki_theme.path)}
            )
        return status
    else:
        if logger:
            logger.log_debug(f"Theme unchanged: {db_theme.theme}")
        return "skipped"


def build_themes_index(
    themes: List[WikiTheme],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build the main themes index page (vimwiki/themes.md).

    Lists themes sorted by usage frequency.

    Args:
        themes: List of WikiTheme objects
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building themes index")

    # Sort by usage count (descending), then alphabetically
    sorted_themes = sorted(themes, key=lambda t: (-t.usage_count, t.name.lower()))

    # Build index lines
    lines = [
        "# Palimpsest — Themes",
        "",
        "Recurring conceptual and emotional threads throughout the journal.",
        "",
        "## All Themes",
        "",
    ]

    for theme in sorted_themes:
        # Format: - [[themes/name.md|Name]] (N appearances)
        rel_path = theme.path.relative_to(wiki_dir)
        appearance_str = f"{theme.usage_count} appearance" + ("s" if theme.usage_count != 1 else "")

        # Add date range if available
        date_range = ""
        if theme.first_appearance and theme.last_appearance:
            if theme.first_appearance == theme.last_appearance:
                date_range = f" — {theme.first_appearance}"
            else:
                date_range = f" — {theme.first_appearance} to {theme.last_appearance}"

        lines.append(f"- [[{rel_path}|{theme.name}]] ({appearance_str}){date_range}")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- Total themes: {len(themes)}",
        f"- Total appearances: {sum(t.usage_count for t in themes)}",
    ])

    # Write to file
    index_path = wiki_dir / "themes.md"
    file_existed = index_path.exists()

    if force or _write_if_changed(index_path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"themes_index_{status}",
                {"file": str(index_path), "themes_count": len(themes)}
            )
        return status
    else:
        if logger:
            logger.log_debug("Themes index unchanged")
        return "skipped"


def export_themes(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all themes from database to wiki pages.

    Creates:
    - vimwiki/themes.md (index)
    - vimwiki/themes/{name}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_themes_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all themes with eager loading of relationships
        query = (
            select(DBTheme)
            .options(
                joinedload(DBTheme.entries),
            )
            .where(DBTheme.deleted_at.is_(None))  # Exclude soft-deleted
        )

        db_themes = session.execute(query).scalars().unique().all()

        if not db_themes:
            if logger:
                logger.log_warning("No themes found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_themes)} themes in database")

        # Export each theme
        wiki_themes: List[WikiTheme] = []
        for db_theme in db_themes:
            stats.files_processed += 1

            try:
                status = export_theme(db_theme, wiki_dir, journal_dir, force, logger)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiTheme for index building
                wiki_theme = WikiTheme.from_database(db_theme, wiki_dir, journal_dir)
                wiki_themes.append(wiki_theme)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_theme",
                        "theme": db_theme.theme
                    })

        # Build index
        try:
            index_status = build_themes_index(wiki_themes, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_themes_index"})

    if logger:
        logger.log_operation("export_themes_complete", {"stats": stats.summary()})

    return stats


# ===== TAGS EXPORT =====

def export_tag(
    db_tag: DBTag,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single tag from database to wiki page.

    Args:
        db_tag: Database Tag model with relationships loaded
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug(f"Exporting tag: {db_tag.tag}")

    # Create WikiTag from database
    try:
        wiki_tag = WikiTag.from_database(db_tag, wiki_dir, journal_dir)
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "create_wiki_tag",
                "tag": db_tag.tag
            })
        raise Sql2WikiError(f"Failed to create WikiTag: {e}") from e

    # Generate markdown
    try:
        lines = wiki_tag.to_wiki()
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "generate_wiki_markdown",
                "tag": db_tag.tag
            })
        raise Sql2WikiError(f"Failed to generate wiki markdown: {e}") from e

    # Write to file
    file_existed = wiki_tag.path.exists()

    if force or _write_if_changed(wiki_tag.path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"tag_{status}",
                {"tag": db_tag.tag, "file": str(wiki_tag.path)}
            )
        return status
    else:
        if logger:
            logger.log_debug(f"Tag unchanged: {db_tag.tag}")
        return "skipped"


def build_tags_index(
    tags: List[WikiTag],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build the main tags index page (vimwiki/tags.md).

    Lists tags sorted by usage frequency.

    Args:
        tags: List of WikiTag objects
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building tags index")

    # Sort by usage count (descending), then alphabetically
    sorted_tags = sorted(tags, key=lambda t: (-t.usage_count, t.name.lower()))

    # Build index lines
    lines = [
        "# Palimpsest — Tags",
        "",
        "Keyword tags used throughout the journal for categorization and search.",
        "",
        "## All Tags",
        "",
    ]

    for tag in sorted_tags:
        # Format: - [[tags/name.md|name]] (N entries)
        rel_path = tag.path.relative_to(wiki_dir)
        entry_str = f"{tag.usage_count} entr" + ("ies" if tag.usage_count != 1 else "y")

        # Add date range if available
        date_range = ""
        if tag.first_used and tag.last_used:
            if tag.first_used == tag.last_used:
                date_range = f" — {tag.first_used}"
            else:
                date_range = f" — {tag.first_used} to {tag.last_used}"

        lines.append(f"- [[{rel_path}|{tag.name}]] ({entry_str}){date_range}")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- Total tags: {len(tags)}",
        f"- Total usage: {sum(t.usage_count for t in tags)}",
    ])

    # Write to file
    index_path = wiki_dir / "tags.md"
    file_existed = index_path.exists()

    if force or _write_if_changed(index_path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"tags_index_{status}",
                {"file": str(index_path), "tags_count": len(tags)}
            )
        return status
    else:
        if logger:
            logger.log_debug("Tags index unchanged")
        return "skipped"


def export_tags(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all tags from database to wiki pages.

    Creates:
    - vimwiki/tags.md (index)
    - vimwiki/tags/{name}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_tags_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all tags with eager loading of relationships
        query = (
            select(DBTag)
            .options(
                joinedload(DBTag.entries),
            )
        )

        db_tags = session.execute(query).scalars().unique().all()

        if not db_tags:
            if logger:
                logger.log_warning("No tags found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_tags)} tags in database")

        # Export each tag
        wiki_tags: List[WikiTag] = []
        for db_tag in db_tags:
            stats.files_processed += 1

            try:
                status = export_tag(db_tag, wiki_dir, journal_dir, force, logger)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiTag for index building
                wiki_tag = WikiTag.from_database(db_tag, wiki_dir, journal_dir)
                wiki_tags.append(wiki_tag)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_tag",
                        "tag": db_tag.tag
                    })

        # Build index
        try:
            index_status = build_tags_index(wiki_tags, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_tags_index"})

    if logger:
        logger.log_operation("export_tags_complete", {"stats": stats.summary()})

    return stats


# ===== POEMS EXPORT =====

def export_poem(
    db_poem: DBPoem,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single poem from database to wiki page.

    Args:
        db_poem: Database Poem model with relationships loaded
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug(f"Exporting poem: {db_poem.title}")

    # Create WikiPoem from database
    try:
        wiki_poem = WikiPoem.from_database(db_poem, wiki_dir, journal_dir)
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "create_wiki_poem",
                "poem": db_poem.title
            })
        raise Sql2WikiError(f"Failed to create WikiPoem: {e}") from e

    # Generate markdown
    try:
        lines = wiki_poem.to_wiki()
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "generate_wiki_markdown",
                "poem": db_poem.title
            })
        raise Sql2WikiError(f"Failed to generate wiki markdown: {e}") from e

    # Write to file
    file_existed = wiki_poem.path.exists()

    if force or _write_if_changed(wiki_poem.path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"poem_{status}",
                {"poem": db_poem.title, "file": str(wiki_poem.path)}
            )
        return status
    else:
        if logger:
            logger.log_debug(f"Poem unchanged: {db_poem.title}")
        return "skipped"


def build_poems_index(
    poems: List[WikiPoem],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build the main poems index page (vimwiki/poems.md).

    Lists poems sorted by most recent version date.

    Args:
        poems: List of WikiPoem objects
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building poems index")

    # Sort by most recent version (descending), then alphabetically
    sorted_poems = sorted(poems, key=lambda p: (
        -(p.latest_version.get("revision_date") or date.min).toordinal() if p.latest_version else 0,
        p.title.lower()
    ))

    # Build index lines
    lines = [
        "# Palimpsest — Poems",
        "",
        "Original poems written throughout the journal, with version history.",
        "",
        "## All Poems",
        "",
    ]

    for poem in sorted_poems:
        # Format: - [[poems/title.md|Title]] (N versions)
        rel_path = poem.path.relative_to(wiki_dir)
        version_str = f"{poem.version_count} version" + ("s" if poem.version_count != 1 else "")

        # Add latest revision date if available
        date_str = ""
        if poem.latest_version and poem.latest_version.get("revision_date"):
            date_str = f" — {poem.latest_version['revision_date']}"

        lines.append(f"- [[{rel_path}|{poem.title}]] ({version_str}){date_str}")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- Total poems: {len(poems)}",
        f"- Total versions: {sum(p.version_count for p in poems)}",
    ])

    # Write to file
    index_path = wiki_dir / "poems.md"
    file_existed = index_path.exists()

    if force or _write_if_changed(index_path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"poems_index_{status}",
                {"file": str(index_path), "poems_count": len(poems)}
            )
        return status
    else:
        if logger:
            logger.log_debug("Poems index unchanged")
        return "skipped"


def export_poems(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all poems from database to wiki pages.

    Creates:
    - vimwiki/poems.md (index)
    - vimwiki/poems/{title}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_poems_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all poems with eager loading of relationships
        query = (
            select(DBPoem)
            .options(
                joinedload(DBPoem.versions),
            )
        )

        db_poems = session.execute(query).scalars().unique().all()

        if not db_poems:
            if logger:
                logger.log_warning("No poems found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_poems)} poems in database")

        # Export each poem
        wiki_poems: List[WikiPoem] = []
        for db_poem in db_poems:
            stats.files_processed += 1

            try:
                status = export_poem(db_poem, wiki_dir, journal_dir, force, logger)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiPoem for index building
                wiki_poem = WikiPoem.from_database(db_poem, wiki_dir, journal_dir)
                wiki_poems.append(wiki_poem)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_poem",
                        "poem": db_poem.title
                    })

        # Build index
        try:
            index_status = build_poems_index(wiki_poems, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_poems_index"})

    if logger:
        logger.log_operation("export_poems_complete", {"stats": stats.summary()})

    return stats


# ===== REFERENCES EXPORT =====

def export_reference(
    db_source: DBReferenceSource,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single reference source from database to wiki page.

    Args:
        db_source: Database ReferenceSource model with relationships loaded
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug(f"Exporting reference source: {db_source.title}")

    # Create WikiReference from database
    try:
        wiki_reference = WikiReference.from_database(db_source, wiki_dir, journal_dir)
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "create_wiki_reference",
                "source": db_source.title
            })
        raise Sql2WikiError(f"Failed to create WikiReference: {e}") from e

    # Generate markdown
    try:
        lines = wiki_reference.to_wiki()
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "generate_wiki_markdown",
                "source": db_source.title
            })
        raise Sql2WikiError(f"Failed to generate wiki markdown: {e}") from e

    # Write to file
    file_existed = wiki_reference.path.exists()

    if force or _write_if_changed(wiki_reference.path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"reference_{status}",
                {"source": db_source.title, "file": str(wiki_reference.path)}
            )
        return status
    else:
        if logger:
            logger.log_debug(f"Reference source unchanged: {db_source.title}")
        return "skipped"


def build_references_index(
    references: List[WikiReference],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build the main references index page (vimwiki/references.md).

    Lists reference sources sorted by citation count.

    Args:
        references: List of WikiReference objects
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building references index")

    # Sort by citation count (descending), then alphabetically
    sorted_refs = sorted(references, key=lambda r: (-r.citation_count, r.source_name.lower()))

    # Build index lines
    lines = [
        "# Palimpsest — References",
        "",
        "External sources cited throughout the journal (books, articles, films, etc.).",
        "",
        "## All Sources",
        "",
    ]

    for ref in sorted_refs:
        # Format: - [[references/source.md|Source Title]] by Author (N citations)
        rel_path = ref.path.relative_to(wiki_dir)
        citation_str = f"{ref.citation_count} citation" + ("s" if ref.citation_count != 1 else "")

        # Add author if available
        author_str = f" by {ref.author}" if ref.author else ""

        # Add date range if available
        date_range = ""
        if ref.first_cited and ref.last_cited:
            if ref.first_cited == ref.last_cited:
                date_range = f" — {ref.first_cited}"
            else:
                date_range = f" — {ref.first_cited} to {ref.last_cited}"

        lines.append(f"- [[{rel_path}|{ref.source_name}]]{author_str} ({citation_str}){date_range}")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- Total sources: {len(references)}",
        f"- Total citations: {sum(r.citation_count for r in references)}",
    ])

    # Write to file
    index_path = wiki_dir / "references.md"
    file_existed = index_path.exists()

    if force or _write_if_changed(index_path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"references_index_{status}",
                {"file": str(index_path), "references_count": len(references)}
            )
        return status
    else:
        if logger:
            logger.log_debug("References index unchanged")
        return "skipped"


def export_references(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all reference sources from database to wiki pages.

    Creates:
    - vimwiki/references.md (index)
    - vimwiki/references/{source}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_references_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all reference sources with eager loading of relationships
        query = (
            select(DBReferenceSource)
            .options(
                joinedload(DBReferenceSource.references),
            )
        )

        db_sources = session.execute(query).scalars().unique().all()

        if not db_sources:
            if logger:
                logger.log_warning("No reference sources found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_sources)} reference sources in database")

        # Export each reference source
        wiki_references: List[WikiReference] = []
        for db_source in db_sources:
            stats.files_processed += 1

            try:
                status = export_reference(db_source, wiki_dir, journal_dir, force, logger)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiReference for index building
                wiki_reference = WikiReference.from_database(db_source, wiki_dir, journal_dir)
                wiki_references.append(wiki_reference)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_reference",
                        "source": db_source.title
                    })

        # Build index
        try:
            index_status = build_references_index(wiki_references, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_references_index"})

    if logger:
        logger.log_operation("export_references_complete", {"stats": stats.summary()})

    return stats


# ===== ENTRIES EXPORT =====

def export_entry(
    db_entry: DBEntry,
    wiki_dir: Path,
    journal_dir: Path,
    prev_entry: Optional[DBEntry] = None,
    next_entry: Optional[DBEntry] = None,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single entry from database to wiki page.

    Args:
        db_entry: Database Entry model with relationships loaded
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        prev_entry: Previous entry (chronological) for navigation
        next_entry: Next entry (chronological) for navigation
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug(f"Exporting entry: {db_entry.date}")

    # Create WikiEntry from database
    try:
        wiki_entry = WikiEntry.from_database(
            db_entry, wiki_dir, journal_dir, prev_entry, next_entry
        )
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "create_wiki_entry",
                "date": db_entry.date
            })
        raise Sql2WikiError(f"Failed to create WikiEntry: {e}") from e

    # Generate markdown
    try:
        lines = wiki_entry.to_wiki()
    except Exception as e:
        if logger:
            logger.log_error(e, {
                "operation": "generate_wiki_markdown",
                "date": db_entry.date
            })
        raise Sql2WikiError(f"Failed to generate wiki markdown: {e}") from e

    # Write to file
    file_existed = wiki_entry.path.exists()

    if force or _write_if_changed(wiki_entry.path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"entry_{status}",
                {"date": db_entry.date, "file": str(wiki_entry.path)}
            )
        return status
    else:
        if logger:
            logger.log_debug(f"Entry unchanged: {db_entry.date}")
        return "skipped"


def build_entries_index(
    entries: List[WikiEntry],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build the main entries index page (vimwiki/entries.md).

    Lists entries chronologically by year and month.

    Args:
        entries: List of WikiEntry objects
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building entries index")

    # Sort by date (descending - most recent first)
    sorted_entries = sorted(entries, key=lambda e: e.date, reverse=True)

    # Build index lines
    lines = [
        "# Palimpsest — Entries",
        "",
        "Chronological index of all journal entries.",
        "",
    ]

    # Group by year
    from itertools import groupby

    for year, year_entries in groupby(sorted_entries, key=lambda e: e.date.year):
        year_entries_list = list(year_entries)
        lines.extend([
            f"## {year}",
            "",
            f"**Total entries:** {len(year_entries_list)}",
            "",
        ])

        # Group by month within year
        for month, month_entries in groupby(year_entries_list, key=lambda e: e.date.month):
            month_entries_list = list(month_entries)
            month_name = month_entries_list[0].date.strftime("%B")

            lines.extend([f"### {month_name}", ""])

            for entry in month_entries_list:
                rel_path = entry.path.relative_to(wiki_dir)
                word_count_str = f"{entry.word_count} words" if entry.word_count else "no content"

                # Add entity count indicator
                entity_indicator = ""
                if entry.entity_count > 0:
                    entity_indicator = f" ({entry.entity_count} entities)"

                lines.append(
                    f"- [[{rel_path}|{entry.date.isoformat()}]] "
                    f"— {word_count_str}{entity_indicator}"
                )

            lines.append("")

    # Add statistics
    total_words = sum(e.word_count for e in sorted_entries)
    total_reading_time = sum(e.reading_time for e in sorted_entries)

    lines.extend([
        "---",
        "",
        "## Statistics",
        "",
        f"- Total entries: {len(sorted_entries)}",
        f"- Total words: {total_words:,}",
        f"- Total reading time: {total_reading_time:.1f} minutes ({total_reading_time/60:.1f} hours)",
        f"- Average words per entry: {total_words/len(sorted_entries):.0f}" if sorted_entries else "- Average words per entry: 0",
    ])

    # Write to file
    index_path = wiki_dir / "entries.md"
    file_existed = index_path.exists()

    if force or _write_if_changed(index_path, lines):
        status = "updated" if file_existed else "created"
        if logger:
            logger.log_operation(
                f"entries_index_{status}",
                {"file": str(index_path), "entries_count": len(sorted_entries)}
            )
        return status
    else:
        if logger:
            logger.log_debug("Entries index unchanged")
        return "skipped"


def export_entries(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all entries from database to wiki pages.

    Creates:
    - vimwiki/entries.md (index)
    - vimwiki/entries/YYYY/YYYY-MM-DD.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_entries_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all entries with eager loading of ALL relationships
        query = (
            select(DBEntry)
            .options(
                joinedload(DBEntry.dates),
                joinedload(DBEntry.cities),
                joinedload(DBEntry.locations).joinedload(DBLocation.city),
                joinedload(DBEntry.people),
                joinedload(DBEntry.events),
                joinedload(DBEntry.tags),
                joinedload(DBEntry.poems),
                joinedload(DBEntry.references),
                joinedload(DBEntry.manuscript),
                joinedload(DBEntry.related_entries),
            )
            .order_by(DBEntry.date)  # Chronological order for prev/next
        )

        db_entries = session.execute(query).scalars().unique().all()

        if not db_entries:
            if logger:
                logger.log_warning("No entries found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_entries)} entries in database")

        # Export each entry with prev/next navigation
        wiki_entries: List[WikiEntry] = []
        for i, db_entry in enumerate(db_entries):
            stats.files_processed += 1

            # Determine prev/next entries
            prev_entry = db_entries[i - 1] if i > 0 else None
            next_entry = db_entries[i + 1] if i < len(db_entries) - 1 else None

            try:
                status = export_entry(
                    db_entry, wiki_dir, journal_dir, prev_entry, next_entry, force, logger
                )

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiEntry for index building
                wiki_entry = WikiEntry.from_database(
                    db_entry, wiki_dir, journal_dir, prev_entry, next_entry
                )
                wiki_entries.append(wiki_entry)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_entry",
                        "date": db_entry.date
                    })

        # Build index
        try:
            index_status = build_entries_index(wiki_entries, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_entries_index"})

    if logger:
        logger.log_operation("export_entries_complete", {"stats": stats.summary()})

    return stats


# ===== LOCATIONS =====


def export_location(
    db_location: DBLocation,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single location to wiki page.

    Args:
        db_location: Database Location model
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    wiki_location = WikiLocation.from_database(db_location, wiki_dir, journal_dir)

    # Ensure directory exists
    wiki_location.path.parent.mkdir(parents=True, exist_ok=True)

    # Generate content
    content = "\n".join(wiki_location.to_wiki())

    # Write if changed
    status = write_if_changed(wiki_location.path, content, force)

    if logger:
        logger.log_debug(f"Location {wiki_location.name}: {status}")

    return status


def build_locations_index(
    locations: List[WikiLocation],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build index page for all locations.

    Creates vimwiki/locations.md with organized location listings.

    Args:
        locations: List of WikiLocation instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    index_path = wiki_dir / "locations.md"

    # Group locations by city
    locations_by_city = defaultdict(list)
    for loc in locations:
        locations_by_city[loc.city].append(loc)

    lines = [
        "# Palimpsest — Locations",
        "",
        "Geographic locations and venues visited.",
        "",
    ]

    # Statistics
    total_locations = len(locations)
    total_visits = sum(loc.visit_count for loc in locations)
    total_cities = len(locations_by_city)

    lines.extend([
        "## Statistics",
        "",
        f"- **Total Locations:** {total_locations}",
        f"- **Total Cities:** {total_cities}",
        f"- **Total Visits:** {total_visits}",
        "",
    ])

    # Locations by city
    lines.extend(["## Locations by City", ""])

    # Sort cities by total visits
    sorted_cities = sorted(
        locations_by_city.keys(),
        key=lambda city: sum(loc.visit_count for loc in locations_by_city[city]),
        reverse=True
    )

    for city in sorted_cities:
        city_locations = sorted(locations_by_city[city], key=lambda l: (-l.visit_count, l.name))
        total_city_visits = sum(loc.visit_count for loc in city_locations)

        lines.append(f"### {city} ({total_city_visits} visits)")
        lines.append("")

        for loc in city_locations:
            link = relative_link(index_path, loc.path)
            visit_str = f"{loc.visit_count} visit" + ("s" if loc.visit_count != 1 else "")
            lines.append(f"- [[{link}|{loc.name}]] ({visit_str})")

        lines.append("")

    # Most visited locations (top 20)
    lines.extend(["## Most Visited", ""])
    sorted_locations = sorted(locations, key=lambda l: (-l.visit_count, l.name))
    for loc in sorted_locations[:20]:
        link = relative_link(index_path, loc.path)
        visit_str = f"{loc.visit_count} visit" + ("s" if loc.visit_count != 1 else "")
        lines.append(f"- [[{link}|{loc.name}]] ({loc.city}) — {visit_str}")

    if len(sorted_locations) > 20:
        lines.append(f"- ... and {len(sorted_locations) - 20} more")

    lines.append("")

    # Write
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Locations index {status}")
        else:
            logger.log_debug("Locations index unchanged")

    return status


def export_locations(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all locations from database to wiki pages.

    Creates:
    - vimwiki/locations.md (index)
    - vimwiki/locations/{city}/{location}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_locations_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all locations with eager loading
        query = (
            select(DBLocation)
            .options(
                joinedload(DBLocation.city),
                joinedload(DBLocation.entries).joinedload(DBEntry.people),
                joinedload(DBLocation.dates),
            )
            .order_by(DBLocation.name)
        )

        db_locations = session.execute(query).scalars().unique().all()

        if not db_locations:
            if logger:
                logger.log_warning("No locations found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_locations)} locations in database")

        # Export each location
        wiki_locations: List[WikiLocation] = []
        for db_location in db_locations:
            stats.files_processed += 1

            try:
                status = export_location(
                    db_location, wiki_dir, journal_dir, force, logger
                )

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiLocation for index building
                wiki_location = WikiLocation.from_database(
                    db_location, wiki_dir, journal_dir
                )
                wiki_locations.append(wiki_location)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_location",
                        "location": db_location.name
                    })

        # Build index
        try:
            index_status = build_locations_index(wiki_locations, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_locations_index"})

    if logger:
        logger.log_operation("export_locations_complete", {"stats": stats.summary()})

    return stats


# ===== CITIES =====


def export_city(
    db_city: DBCity,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single city to wiki page.

    Args:
        db_city: Database City model
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    wiki_city = WikiCity.from_database(db_city, wiki_dir, journal_dir)

    # Ensure directory exists
    wiki_city.path.parent.mkdir(parents=True, exist_ok=True)

    # Generate content
    content = "\n".join(wiki_city.to_wiki())

    # Write if changed
    status = write_if_changed(wiki_city.path, content, force)

    if logger:
        logger.log_debug(f"City {wiki_city.name}: {status}")

    return status


def build_cities_index(
    cities: List[WikiCity],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build index page for all cities.

    Creates vimwiki/cities.md with organized city listings.

    Args:
        cities: List of WikiCity instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    index_path = wiki_dir / "cities.md"

    lines = [
        "# Palimpsest — Cities",
        "",
        "Geographic regions where journal entries take place.",
        "",
    ]

    # Statistics
    total_cities = len(cities)
    total_entries = sum(city.entry_count for city in cities)
    total_locations = sum(city.location_count for city in cities)

    lines.extend([
        "## Statistics",
        "",
        f"- **Total Cities:** {total_cities}",
        f"- **Total Entries:** {total_entries}",
        f"- **Total Locations:** {total_locations}",
        "",
    ])

    # Group by country
    cities_by_country = defaultdict(list)
    for city in cities:
        country = city.country or "Unknown"
        cities_by_country[country].append(city)

    lines.extend(["## Cities by Country", ""])

    # Sort countries by total entries
    sorted_countries = sorted(
        cities_by_country.keys(),
        key=lambda country: sum(c.entry_count for c in cities_by_country[country]),
        reverse=True
    )

    for country in sorted_countries:
        country_cities = sorted(cities_by_country[country], key=lambda c: (-c.entry_count, c.name))
        total_country_entries = sum(c.entry_count for c in country_cities)

        lines.append(f"### {country} ({total_country_entries} entries)")
        lines.append("")

        for city in country_cities:
            link = relative_link(index_path, city.path)
            entry_str = f"{city.entry_count} entr" + ("ies" if city.entry_count != 1 else "y")
            loc_str = f"{city.location_count} location" + ("s" if city.location_count != 1 else "")
            lines.append(f"- [[{link}|{city.name}]] ({entry_str}, {loc_str})")

        lines.append("")

    # Most visited cities (top 20)
    lines.extend(["## Most Visited", ""])
    sorted_cities = sorted(cities, key=lambda c: (-c.entry_count, c.name))
    for city in sorted_cities[:20]:
        link = relative_link(index_path, city.path)
        entry_str = f"{city.entry_count} entr" + ("ies" if city.entry_count != 1 else "y")
        lines.append(f"- [[{link}|{city.name}]] ({city.country}) — {entry_str}")

    if len(sorted_cities) > 20:
        lines.append(f"- ... and {len(sorted_cities) - 20} more")

    lines.append("")

    # Write
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Cities index {status}")
        else:
            logger.log_debug("Cities index unchanged")

    return status


def export_cities(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all cities from database to wiki pages.

    Creates:
    - vimwiki/cities.md (index)
    - vimwiki/cities/{city}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_cities_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all cities with eager loading
        query = (
            select(DBCity)
            .options(
                joinedload(DBCity.entries),
                joinedload(DBCity.locations),
            )
            .order_by(DBCity.city)
        )

        db_cities = session.execute(query).scalars().unique().all()

        if not db_cities:
            if logger:
                logger.log_warning("No cities found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_cities)} cities in database")

        # Export each city
        wiki_cities: List[WikiCity] = []
        for db_city in db_cities:
            stats.files_processed += 1

            try:
                status = export_city(
                    db_city, wiki_dir, journal_dir, force, logger
                )

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiCity for index building
                wiki_city = WikiCity.from_database(
                    db_city, wiki_dir, journal_dir
                )
                wiki_cities.append(wiki_city)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_city",
                        "city": db_city.city
                    })

        # Build index
        try:
            index_status = build_cities_index(wiki_cities, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_cities_index"})

    if logger:
        logger.log_operation("export_cities_complete", {"stats": stats.summary()})

    return stats


# ===== EVENTS =====


def export_event(
    db_event: DBEvent,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single event to wiki page.

    Args:
        db_event: Database Event model
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    wiki_event = WikiEvent.from_database(db_event, wiki_dir, journal_dir)

    # Ensure directory exists
    wiki_event.path.parent.mkdir(parents=True, exist_ok=True)

    # Generate content
    content = "\n".join(wiki_event.to_wiki())

    # Write if changed
    status = write_if_changed(wiki_event.path, content, force)

    if logger:
        logger.log_debug(f"Event {wiki_event.display_name}: {status}")

    return status


def build_events_index(
    events: List[WikiEvent],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Build index page for all events.

    Creates vimwiki/events.md with organized event listings.

    Args:
        events: List of WikiEvent instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    index_path = wiki_dir / "events.md"

    lines = [
        "# Palimpsest — Events",
        "",
        "Narrative events and periods spanning multiple journal entries.",
        "",
    ]

    # Statistics
    total_events = len(events)
    total_entries = sum(event.entry_count for event in events)

    lines.extend([
        "## Statistics",
        "",
        f"- **Total Events:** {total_events}",
        f"- **Total Entries:** {total_entries}",
        "",
    ])

    # Events by manuscript status
    events_with_manuscript = [e for e in events if e.has_manuscript_metadata]
    events_without_manuscript = [e for e in events if not e.has_manuscript_metadata]

    if events_with_manuscript:
        lines.extend(["## Events with Manuscript Metadata", ""])

        # Group by status
        by_status = defaultdict(list)
        for event in events_with_manuscript:
            status = event.manuscript_status or "No Status"
            by_status[status].append(event)

        for status in sorted(by_status.keys()):
            status_events = sorted(by_status[status], key=lambda e: (-e.entry_count, e.display_name))
            lines.append(f"### {status}")
            lines.append("")

            for event in status_events:
                link = relative_link(index_path, event.path)
                entry_str = f"{event.entry_count} entr" + ("ies" if event.entry_count != 1 else "y")
                date_range = ""
                if event.start_date and event.end_date:
                    date_range = f" ({event.start_date.isoformat()} to {event.end_date.isoformat()})"
                lines.append(f"- [[{link}|{event.display_name}]] ({entry_str}){date_range}")

            lines.append("")

    # All events chronologically
    lines.extend(["## All Events", ""])
    sorted_events = sorted(
        [e for e in events if e.start_date],
        key=lambda e: e.start_date,
        reverse=True
    )

    for event in sorted_events:
        link = relative_link(index_path, event.path)
        entry_str = f"{event.entry_count} entr" + ("ies" if event.entry_count != 1 else "y")
        date_range = ""
        if event.start_date and event.end_date:
            if event.start_date == event.end_date:
                date_range = f" ({event.start_date.isoformat()})"
            else:
                date_range = f" ({event.start_date.isoformat()} to {event.end_date.isoformat()})"
        lines.append(f"- [[{link}|{event.display_name}]] ({entry_str}){date_range}")

    # Events without dates
    events_no_dates = [e for e in events if not e.start_date]
    if events_no_dates:
        lines.append("")
        lines.append("### Events without dates")
        lines.append("")
        for event in sorted(events_no_dates, key=lambda e: e.display_name):
            link = relative_link(index_path, event.path)
            entry_str = f"{event.entry_count} entr" + ("ies" if event.entry_count != 1 else "y")
            lines.append(f"- [[{link}|{event.display_name}]] ({entry_str})")

    lines.append("")

    # Write
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Events index {status}")
        else:
            logger.log_debug("Events index unchanged")

    return status


def export_events(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export all events from database to wiki pages.

    Creates:
    - vimwiki/events.md (index)
    - vimwiki/events/{event}.md (individual pages)

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_events_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all events with eager loading
        query = (
            select(DBEvent)
            .options(
                joinedload(DBEvent.entries),
                joinedload(DBEvent.people),
                joinedload(DBEvent.manuscript),
            )
            .order_by(DBEvent.event)
        )

        db_events = session.execute(query).scalars().unique().all()

        if not db_events:
            if logger:
                logger.log_warning("No events found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_events)} events in database")

        # Export each event
        wiki_events: List[WikiEvent] = []
        for db_event in db_events:
            stats.files_processed += 1

            try:
                status = export_event(
                    db_event, wiki_dir, journal_dir, force, logger
                )

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                # Create WikiEvent for index building
                wiki_event = WikiEvent.from_database(
                    db_event, wiki_dir, journal_dir
                )
                wiki_events.append(wiki_event)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_event",
                        "event": db_event.event
                    })

        # Build index
        try:
            index_status = build_events_index(wiki_events, wiki_dir, force, logger)
        except Exception as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "build_events_index"})

    if logger:
        logger.log_operation("export_events_complete", {"stats": stats.summary()})

    return stats


# ===== TIMELINE =====


def export_timeline(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export timeline/calendar view of all journal entries.

    Creates vimwiki/timeline.md with year-by-year and month-by-month
    breakdown of all entries.

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_operation("export_timeline_start", {"wiki_dir": str(wiki_dir)})

    timeline_path = wiki_dir / "timeline.md"

    with db.session_scope() as session:
        # Query all entries (no need for relationships, just dates)
        query = select(DBEntry).order_by(DBEntry.date)
        db_entries = session.execute(query).scalars().all()

        if not db_entries:
            if logger:
                logger.log_warning("No entries found for timeline")
            return "skipped"

        # Group entries by year and month
        entries_by_year = defaultdict(lambda: defaultdict(list))
        for entry in db_entries:
            year = entry.date.year
            month = entry.date.month
            entries_by_year[year][month].append(entry)

        lines = [
            "# Palimpsest — Timeline",
            "",
            "Chronological calendar view of all journal entries.",
            "",
        ]

        # Statistics
        total_entries = len(db_entries)
        total_years = len(entries_by_year)
        first_entry = db_entries[0].date
        last_entry = db_entries[-1].date
        span_days = (last_entry - first_entry).days

        lines.extend([
            "## Statistics",
            "",
            f"- **Total Entries:** {total_entries}",
            f"- **Time Span:** {total_years} years ({span_days} days)",
            f"- **First Entry:** {first_entry.isoformat()}",
            f"- **Last Entry:** {last_entry.isoformat()}",
            f"- **Average per Year:** {total_entries / total_years:.1f} entries",
            "",
        ])

        # Year-by-year timeline (most recent first)
        lines.extend(["## Timeline by Year", ""])

        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        for year in sorted(entries_by_year.keys(), reverse=True):
            year_entries = sum(len(entries) for entries in entries_by_year[year].values())
            lines.append(f"### {year} ({year_entries} entries)")
            lines.append("")

            # Month-by-month breakdown
            for month in range(1, 13):
                if month in entries_by_year[year]:
                    month_entries = entries_by_year[year][month]
                    month_name = month_names[month - 1]

                    lines.append(f"#### {month_name} {year} ({len(month_entries)} entries)")
                    lines.append("")

                    # List entries (most recent first)
                    for entry in reversed(month_entries):
                        entry_year = entry.date.year
                        entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
                        entry_link = relative_link(timeline_path, entry_path)

                        word_str = f"{entry.word_count} words" if entry.word_count else "no content"
                        lines.append(f"- [[{entry_link}|{entry.date.isoformat()}]] — {word_str}")

                    lines.append("")

        # Write
        content = "\n".join(lines)
        status = write_if_changed(timeline_path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"Timeline {status}")
            else:
                logger.log_debug("Timeline unchanged")
            logger.log_operation("export_timeline_complete", {"status": status})

        return status


# ----- CLI -----
@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file",
)
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Vimwiki root directory",
)
@click.option(
    "--journal-dir",
    type=click.Path(),
    default=str(MD_DIR),
    help="Journal entries directory",
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(
    ctx: click.Context,
    db_path: str,
    wiki_dir: str,
    journal_dir: str,
    log_dir: str,
    verbose: bool
) -> None:
    """sql2wiki - Export database entities to Vimwiki pages"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["journal_dir"] = Path(journal_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "sql2wiki")

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=ALEMBIC_DIR,
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@cli.command()
@click.argument(
    "entity_type",
    type=click.Choice([
        "entries", "locations", "cities", "events", "timeline",
        "people", "themes", "tags", "poems", "references",
        "all"
    ]),
)
@click.option("-f", "--force", is_flag=True, help="Force regenerate all files")
@click.pass_context
def export(ctx: click.Context, entity_type: str, force: bool) -> None:
    """Export database entities to vimwiki pages."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]
    wiki_dir: Path = ctx.obj["wiki_dir"]
    journal_dir: Path = ctx.obj["journal_dir"]

    try:
        if entity_type == "entries":
            click.echo(f"📤 Exporting entries to {wiki_dir}/entries/")

            stats = export_entries(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Entries export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "locations":
            click.echo(f"📤 Exporting locations to {wiki_dir}/locations/")

            stats = export_locations(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Locations export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "cities":
            click.echo(f"📤 Exporting cities to {wiki_dir}/cities/")

            stats = export_cities(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Cities export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "events":
            click.echo(f"📤 Exporting events to {wiki_dir}/events/")

            stats = export_events(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Events export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "timeline":
            click.echo(f"📤 Exporting timeline to {wiki_dir}/timeline.md")

            status = export_timeline(db, wiki_dir, journal_dir, force, logger)

            if status in ("created", "updated"):
                click.echo(f"\n✅ Timeline {status}")
            else:
                click.echo(f"\n⏭️  Timeline {status}")

        elif entity_type == "people":
            click.echo(f"📤 Exporting people to {wiki_dir}/people/")

            stats = export_people(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ People export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "themes":
            click.echo(f"📤 Exporting themes to {wiki_dir}/themes/")

            stats = export_themes(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Themes export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "tags":
            click.echo(f"📤 Exporting tags to {wiki_dir}/tags/")

            stats = export_tags(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Tags export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "poems":
            click.echo(f"📤 Exporting poems to {wiki_dir}/poems/")

            stats = export_poems(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ Poems export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "references":
            click.echo(f"📤 Exporting references to {wiki_dir}/references/")

            stats = export_references(db, wiki_dir, journal_dir, force, logger)

            click.echo("\n✅ References export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

        elif entity_type == "all":
            click.echo(f"📤 Exporting all entities to {wiki_dir}/")

            # Export all entity types
            entries_stats = export_entries(db, wiki_dir, journal_dir, force, logger)
            locations_stats = export_locations(db, wiki_dir, journal_dir, force, logger)
            cities_stats = export_cities(db, wiki_dir, journal_dir, force, logger)
            events_stats = export_events(db, wiki_dir, journal_dir, force, logger)
            people_stats = export_people(db, wiki_dir, journal_dir, force, logger)
            themes_stats = export_themes(db, wiki_dir, journal_dir, force, logger)
            tags_stats = export_tags(db, wiki_dir, journal_dir, force, logger)
            poems_stats = export_poems(db, wiki_dir, journal_dir, force, logger)
            references_stats = export_references(db, wiki_dir, journal_dir, force, logger)

            # Export timeline (returns status string, not ConversionStats)
            timeline_status = export_timeline(db, wiki_dir, journal_dir, force, logger)

            # Combined stats
            all_stats = [
                entries_stats, locations_stats, cities_stats, events_stats,
                people_stats, themes_stats, tags_stats, poems_stats, references_stats
            ]
            total_files = sum(s.files_processed for s in all_stats)
            total_created = sum(s.entries_created for s in all_stats)
            total_updated = sum(s.entries_updated for s in all_stats)
            total_skipped = sum(s.entries_skipped for s in all_stats)
            total_errors = sum(s.errors for s in all_stats)
            total_duration = sum(s.duration() for s in all_stats)

            click.echo("\n✅ All exports complete:")
            click.echo(f"  Total files: {total_files}")
            click.echo(f"  Created: {total_created}")
            click.echo(f"  Updated: {total_updated}")
            click.echo(f"  Skipped: {total_skipped}")
            if total_errors > 0:
                click.echo(f"  ⚠️  Errors: {total_errors}")
            click.echo(f"  Duration: {total_duration:.2f}s")

    except (Sql2WikiError, Exception) as e:
        handle_cli_error(ctx, e, "export", {"entity_type": entity_type})


if __name__ == "__main__":
    cli(obj={})

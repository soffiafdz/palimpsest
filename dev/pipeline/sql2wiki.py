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
from dev.database.models import Person as DBPerson, Entry
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
    type=click.Choice(["people", "themes", "tags", "poems", "references", "all"]),
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
        if entity_type == "people":
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

        elif entity_type == "all":
            click.echo(f"📤 Exporting all entities to {wiki_dir}/")

            # Export all entity types
            people_stats = export_people(db, wiki_dir, journal_dir, force, logger)
            themes_stats = export_themes(db, wiki_dir, journal_dir, force, logger)

            # Combined stats
            total_files = people_stats.files_processed + themes_stats.files_processed
            total_created = people_stats.entries_created + themes_stats.entries_created
            total_updated = people_stats.entries_updated + themes_stats.entries_updated
            total_skipped = people_stats.entries_skipped + themes_stats.entries_skipped
            total_errors = people_stats.errors + themes_stats.errors
            total_duration = people_stats.duration() + themes_stats.duration()

            click.echo("\n✅ Export complete:")
            click.echo(f"  Total files: {total_files}")
            click.echo(f"  Created: {total_created}")
            click.echo(f"  Updated: {total_updated}")
            click.echo(f"  Skipped: {total_skipped}")
            if total_errors > 0:
                click.echo(f"  ⚠️  Errors: {total_errors}")
            click.echo(f"  Duration: {total_duration:.2f}s")

        else:
            click.echo(f"⚠️  {entity_type.title()} export not yet implemented")
            click.echo("   Coming in Phase 2 of implementation")
            sys.exit(1)

    except (Sql2WikiError, Exception) as e:
        handle_cli_error(ctx, e, "export", {"entity_type": entity_type})


if __name__ == "__main__":
    cli(obj={})

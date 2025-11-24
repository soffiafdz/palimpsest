#!/usr/bin/env python3
"""
search_cli.py
-------------
Standalone CLI for full-text search and filtering of journal entries.

This provides a dedicated search interface using SQLite's FTS5 engine
for fast full-text queries with filters.

Commands:
    plm-search query "search text" [options]
    plm-search index create
    plm-search index rebuild
    plm-search index status

Examples:
    # Simple text search
    plm-search query "alice therapy"

    # With filters
    plm-search query "reflection" person:alice in:2024

    # Complex query
    plm-search query "therapy" city:montreal words:500-1000 has:manuscript

    # Manage index
    plm-search index create
    plm-search index rebuild
    plm-search index status
"""
import sys
import click
from pathlib import Path
from typing import Optional

from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import setup_logger


@click.group()
@click.option("--log-dir", type=click.Path(), default=str(LOG_DIR), help="Directory for log files")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, log_dir: str, verbose: bool) -> None:
    """
    Full-text search and filtering of journal entries.

    This command provides powerful search capabilities for querying
    journal entries using SQLite's FTS5 (Full-Text Search) engine. Supports
    complex queries with filters for people, dates, locations, word counts,
    and more.

    Examples:
        plm-search query "therapy sessions"
        plm-search query "alice" person:bob in:2024
        plm-search index rebuild
    """
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "search")


@cli.command("query")
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", type=int, help="Maximum results (default: 50)")
@click.option(
    "--sort",
    type=click.Choice(["relevance", "date", "word_count"]),
    help="Sort order (default: relevance)"
)
@click.option("-v", "--verbose", is_flag=True, help="Show detailed metadata")
@click.pass_context
def search_query(ctx: click.Context, query: tuple, limit: Optional[int], sort: Optional[str], verbose: bool) -> None:
    """
    Search journal entries with full-text search and filters.

    Query Syntax:
    - Free text: Any words to search for
    - person:NAME: Filter by person mentioned
    - city:CITY: Filter by city/location
    - in:YEAR or in:YYYY-MM: Filter by date
    - words:MIN-MAX: Filter by word count range
    - has:manuscript: Only entries with manuscript metadata
    - tag:TAG: Filter by tag

    Examples:
        # Simple text search
        plm-search query "alice therapy"

        # With filters
        plm-search query "reflection" person:alice in:2024

        # Complex query with multiple filters
        plm-search query "therapy" city:montreal words:500-1000 has:manuscript

        # Verbose output with metadata
        plm-search query "creative writing" --verbose --limit 20
    """
    from dev.database.manager import PalimpsestDB
    from dev.search.search_engine import SearchQueryParser, SearchEngine

    logger: PalimpsestLogger = ctx.obj["logger"]

    # Parse query
    query_string = " ".join(query)
    parsed_query = SearchQueryParser.parse(query_string)

    # Override with CLI options
    if limit:
        parsed_query.limit = limit
    if sort:
        parsed_query.sort_by = sort

    # Initialize database
    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    # Execute search
    engine = SearchEngine(db.session)
    results = engine.search(parsed_query)

    # Display results
    if not results:
        click.echo("No results found.")
        return

    click.echo(f"Found {len(results)} results:\n")

    for result in results:
        entry = result['entry']
        score = result['score']
        snippet = result['snippet']

        # Date and score
        date_str = entry.date.isoformat()
        if score > 0:
            click.echo(f"📅 {date_str} (score: {score:.2f})")
        else:
            click.echo(f"📅 {date_str}")

        # Snippet
        if snippet:
            clean_snippet = snippet.replace('\n', ' ').strip()
            click.echo(f"   {clean_snippet}")

        # Metadata (verbose mode)
        if verbose:
            click.echo(f"   Words: {entry.word_count}, Time: {entry.reading_time}m")

            if entry.people:
                people_str = ", ".join(p.name for p in entry.people)
                click.echo(f"   People: {people_str}")

            if entry.tags:
                tags_str = ", ".join(t.tag for t in entry.tags)
                click.echo(f"   Tags: {tags_str}")

        click.echo()  # Blank line between results

    # Summary
    if len(results) == parsed_query.limit:
        click.echo(f"(Showing first {parsed_query.limit} results. Use --limit to see more)")


@cli.group("index")
@click.pass_context
def index_group(ctx: click.Context) -> None:
    """
    Manage full-text search index.

    The FTS5 search index must be created before running queries. This
    command group provides operations for creating, rebuilding, and
    checking the status of the search index.

    Commands:
        create   - Create new FTS5 index
        rebuild  - Rebuild existing index
        status   - Check if index exists and entry count
    """
    pass


@index_group.command("create")
@click.pass_context
def index_create(ctx: click.Context) -> None:
    """
    Create full-text search index.

    Creates a new SQLite FTS5 (Full-Text Search) virtual table and populates
    it with all journal entry content. This index enables fast full-text
    queries across the entire corpus.

    The index includes:
    - Entry content field
    - Entry ID for joining to main entries table
    - FTS5 tokenizer with Unicode support
    - Position information for snippet generation

    Triggers are also created to automatically keep the index in sync when
    entries are inserted, updated, or deleted.

    Performance:
    - Initial indexing takes ~1-2 seconds per 1000 entries
    - Index size approximately 30% of original text size
    - Queries after indexing are typically <100ms

    Use Cases:
    - Initial setup after database creation
    - First-time search functionality setup
    - After database restore without index
    """
    from dev.database.manager import PalimpsestDB
    from dev.search.search_index import SearchIndexManager

    logger: PalimpsestLogger = ctx.obj["logger"]

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    mgr = SearchIndexManager(db.engine, logger)

    if mgr.index_exists():
        click.echo("⚠ Search index already exists. Use 'plm-search index rebuild' to recreate.")
        return

    mgr.create_index()
    count = mgr.populate_index(db.session)
    mgr.setup_triggers()

    click.echo(f"✓ Created search index: {count} entries indexed")


@index_group.command("rebuild")
@click.pass_context
def index_rebuild(ctx: click.Context) -> None:
    """
    Rebuild full-text search index.

    Completely rebuilds the FTS5 search index from scratch. This operation
    drops the existing index, recreates it, and repopulates with all current
    entry content. Used to fix corruption or update after bulk changes.

    When to Rebuild:
    - After bulk entry updates bypassing triggers
    - Search results seem incomplete or wrong
    - Database corruption suspected
    - Major database schema changes
    - Periodic maintenance (e.g., monthly)

    Performance:
    - Rebuilding takes ~1-2 seconds per 1000 entries
    - Database locked during rebuild (brief)
    - No data loss (read-only on entries table)

    Use Cases:
    - Fix search inconsistencies
    - After bulk data imports
    - Regular maintenance schedule
    - Troubleshooting search issues
    """
    from dev.database.manager import PalimpsestDB
    from dev.search.search_index import SearchIndexManager

    logger: PalimpsestLogger = ctx.obj["logger"]

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    mgr = SearchIndexManager(db.engine, logger)
    count = mgr.rebuild_index(db.session)

    click.echo(f"✓ Rebuilt search index: {count} entries indexed")


@index_group.command("status")
@click.pass_context
def index_status(ctx: click.Context) -> None:
    """
    Check full-text search index status.

    Queries the database to check if the FTS5 search index exists and
    reports the number of entries currently indexed. Used for diagnostics
    and verification after index operations.

    Output Information:
    - Index existence (✓ exists or ⚠ missing)
    - Number of indexed entries
    - Suggestion to create if missing

    Use Cases:
    - Verify index after creation
    - Troubleshooting search issues
    - Check index before running queries
    - Pipeline validation checks
    """
    from dev.database.manager import PalimpsestDB
    from dev.search.search_index import SearchIndexManager
    from sqlalchemy import text

    logger: PalimpsestLogger = ctx.obj["logger"]

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    mgr = SearchIndexManager(db.engine, logger)

    if mgr.index_exists():
        click.echo("✓ Search index exists")

        # Count entries
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM entries_fts"))
            count = result.scalar()

        click.echo(f"  Indexed entries: {count}")
    else:
        click.echo("⚠ Search index does not exist. Run: plm-search index create")


if __name__ == "__main__":
    cli(obj={})

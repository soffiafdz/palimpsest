#!/usr/bin/env python3
"""
search.py
---------
CLI interface for full-text search and filtering.

Commands:
    palimpsest search "query string" [options]
    palimpsest search index --rebuild
    palimpsest search index --create

Examples:
    # Text search
    palimpsest search "alice therapy"

    # With filters
    palimpsest search "reflection" person:alice in:2024

    # Complex query
    palimpsest search "therapy" city:montreal words:500-1000 has:manuscript

    # Rebuild FTS index
    palimpsest search index --rebuild
"""
import sys
import argparse
from pathlib import Path
from datetime import date as Date
from typing import Optional

from dev.database.manager import PalimpsestDB
from dev.database.search import SearchQueryParser, SearchEngine
from dev.database.search_index import SearchIndexManager
from dev.core.logging_manager import PalimpsestLogger


def format_result(result: dict, verbose: bool = False) -> str:
    """Format search result for display."""
    entry = result['entry']
    score = result['score']
    snippet = result['snippet']

    lines = []

    # Date and score
    date_str = entry.date.isoformat()
    if score > 0:
        lines.append(f"📅 {date_str} (score: {score:.2f})")
    else:
        lines.append(f"📅 {date_str}")

    # Snippet
    if snippet:
        # Clean snippet
        clean_snippet = snippet.replace('\n', ' ').strip()
        lines.append(f"   {clean_snippet}")

    # Metadata (verbose mode)
    if verbose:
        lines.append(f"   Words: {entry.word_count}, Time: {entry.reading_time}m")

        if entry.people:
            people_str = ", ".join(p.name for p in entry.people)
            lines.append(f"   People: {people_str}")

        if entry.tags:
            tags_str = ", ".join(t.tag for t in entry.tags)
            lines.append(f"   Tags: {tags_str}")

    lines.append("")  # Blank line between results

    return "\n".join(lines)


def search_command(args):
    """Execute search query."""
    # Parse query
    query_string = " ".join(args.query)
    query = SearchQueryParser.parse(query_string)

    # Override limit if provided
    if args.limit:
        query.limit = args.limit

    # Override sort if provided
    if args.sort:
        query.sort_by = args.sort

    # Initialize database
    db = PalimpsestDB()

    # Execute search
    engine = SearchEngine(db.session)
    results = engine.search(query)

    # Display results
    if not results:
        print("No results found.")
        return

    print(f"Found {len(results)} results:\n")

    for result in results:
        print(format_result(result, verbose=args.verbose))

    # Summary
    if len(results) == query.limit:
        print(f"(Showing first {query.limit} results. Use --limit to see more)")


def index_rebuild_command(args):
    """Rebuild FTS search index."""
    logger = PalimpsestLogger()

    # Initialize database
    db = PalimpsestDB()

    # Rebuild index
    mgr = SearchIndexManager(db.engine, logger)
    count = mgr.rebuild_index(db.session)

    print(f"✓ Rebuilt search index: {count} entries indexed")


def index_create_command(args):
    """Create FTS search index."""
    logger = PalimpsestLogger()

    # Initialize database
    db = PalimpsestDB()

    # Create index
    mgr = SearchIndexManager(db.engine, logger)

    if mgr.index_exists():
        print("⚠ Search index already exists. Use --rebuild to recreate.")
        return

    mgr.create_index()
    count = mgr.populate_index(db.session)
    mgr.setup_triggers()

    print(f"✓ Created search index: {count} entries indexed")


def index_status_command(args):
    """Check FTS index status."""
    logger = PalimpsestLogger()

    # Initialize database
    db = PalimpsestDB()

    # Check status
    mgr = SearchIndexManager(db.engine, logger)

    if mgr.index_exists():
        print("✓ Search index exists")

        # Count entries
        from sqlalchemy import text
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM entries_fts"))
            count = result.scalar()

        print(f"  Indexed entries: {count}")
    else:
        print("⚠ Search index does not exist. Run: palimpsest search index --create")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Search journal entries with full-text search and filters"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search entries')
    search_parser.add_argument(
        'query',
        nargs='+',
        help='Search query with optional filters (e.g., "alice person:bob in:2024")'
    )
    search_parser.add_argument(
        '--limit',
        type=int,
        help='Maximum results (default: 50)'
    )
    search_parser.add_argument(
        '--sort',
        choices=['relevance', 'date', 'word_count'],
        help='Sort order (default: relevance)'
    )
    search_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed metadata for each result'
    )
    search_parser.set_defaults(func=search_command)

    # Index management
    index_parser = subparsers.add_parser('index', help='Manage search index')
    index_subparsers = index_parser.add_subparsers(dest='index_command')

    # index create
    create_parser = index_subparsers.add_parser('create', help='Create search index')
    create_parser.set_defaults(func=index_create_command)

    # index rebuild
    rebuild_parser = index_subparsers.add_parser('rebuild', help='Rebuild search index')
    rebuild_parser.set_defaults(func=index_rebuild_command)

    # index status
    status_parser = index_subparsers.add_parser('status', help='Check index status')
    status_parser.set_defaults(func=index_status_command)

    # Parse and execute
    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()

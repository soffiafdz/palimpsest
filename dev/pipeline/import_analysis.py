#!/usr/bin/env python3
"""
import_analysis.py
------------------
CLI for importing narrative analysis data into the database.

Parses narrative analysis markdown files and propagates the extracted
data to ManuscriptEntry records, including:
- narrative_rating and rating_justification
- summary
- themes (entry-specific)
- motifs (thematic patterns)
- tag_categories (for future tag categorization)

Key Features:
    - Parses all *_analysis.md files from narrative analysis directory
    - Creates or updates ManuscriptEntry records with analysis data
    - Creates Theme entities from parsed themes
    - Creates Motif entities from parsed thematic arcs
    - Tracks TagCategory mappings for future tag categorization
    - Dry-run mode for previewing changes

Usage:
    # Preview changes (dry-run)
    python -m dev.pipeline.import_analysis --dry-run

    # Import analysis data
    python -m dev.pipeline.import_analysis

    # Import with verbose output
    python -m dev.pipeline.import_analysis --verbose

    # Import specific date range
    python -m dev.pipeline.import_analysis --start 2024-11-01 --end 2025-01-31
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.paths import DB_PATH, JOURNAL_DIR
from dev.core.cli import OperationStats
from dev.database.manager import PalimpsestDB
from dev.dataclasses.parsers.narrative_analysis import (
    AnalysisData,
    parse_all_analyses,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default paths
ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"


@dataclass
class ImportStats(OperationStats):
    """
    Statistics for analysis import operations.

    Attributes:
        entries_updated: Number of entries updated with analysis data
        entries_created: Number of new manuscript entries created
        entries_skipped: Number of entries skipped (no matching entry)
        themes_created: Number of new themes created
        motifs_created: Number of new motifs created
        categories_found: Number of unique tag categories found
    """
    entries_updated: int = 0
    entries_created: int = 0
    entries_skipped: int = 0
    themes_created: int = 0
    motifs_created: int = 0
    categories_found: int = 0

    def summary(self) -> str:
        """Get formatted summary."""
        return (
            f"{self.files_processed} analyses processed, "
            f"{self.entries_created} created, "
            f"{self.entries_updated} updated, "
            f"{self.entries_skipped} skipped, "
            f"{self.themes_created} themes, "
            f"{self.motifs_created} motifs, "
            f"{self.errors} errors, "
            f"{self.duration():.2f}s"
        )


def import_analysis_to_db(
    analysis: AnalysisData,
    db: PalimpsestDB,
    stats: ImportStats,
    verbose: bool = False,
) -> bool:
    """
    Import a single analysis into the database.

    Args:
        analysis: Parsed analysis data
        db: PalimpsestDB instance
        stats: Stats tracker
        verbose: Whether to log verbose output

    Returns:
        True if successful, False otherwise
    """
    # Find the matching journal entry by date
    entry = db.entries.get_by_date(analysis.entry_date)

    if not entry:
        if verbose:
            logger.warning(f"No entry found for date: {analysis.entry_date}")
        stats.entries_skipped += 1
        return False

    # Prepare manuscript data
    manuscript_data = {}

    if analysis.rating is not None:
        manuscript_data["narrative_rating"] = analysis.rating

    if analysis.rating_justification:
        manuscript_data["rating_justification"] = analysis.rating_justification

    if analysis.summary:
        manuscript_data["summary"] = analysis.summary

    # Extract theme names from ThemeData objects
    if analysis.themes:
        manuscript_data["themes"] = [t.name for t in analysis.themes]

    # Motifs are already strings
    if analysis.motifs:
        manuscript_data["motifs"] = analysis.motifs

    # Check if manuscript entry exists
    existing = entry.manuscript

    # Create or update manuscript entry
    ms_entry = db.manuscripts.create_or_update_entry(entry, manuscript_data)

    if ms_entry:
        if existing:
            stats.entries_updated += 1
            if verbose:
                logger.info(f"Updated: {analysis.entry_date}")
        else:
            stats.entries_created += 1
            if verbose:
                logger.info(f"Created: {analysis.entry_date}")
        return True
    else:
        stats.errors += 1
        logger.error(f"Failed to create/update manuscript entry: {analysis.entry_date}")
        return False


def run_import(
    analysis_dir: Path,
    db_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ImportStats:
    """
    Run the analysis import process.

    Args:
        analysis_dir: Directory containing analysis files
        db_path: Path to database
        dry_run: If True, don't commit changes
        verbose: Whether to log verbose output
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        Import statistics
    """
    stats = ImportStats()

    # Parse all analyses
    logger.info(f"Parsing analysis files from: {analysis_dir}")
    analyses = parse_all_analyses(analysis_dir)
    stats.files_processed = len(analyses)

    if not analyses:
        logger.warning("No analysis files found")
        return stats

    # Filter by date range if specified
    if start_date:
        analyses = {d: a for d, a in analyses.items() if d >= start_date}
    if end_date:
        analyses = {d: a for d, a in analyses.items() if d <= end_date}

    logger.info(f"Processing {len(analyses)} analyses")

    if dry_run:
        logger.info("DRY RUN - no changes will be committed")

    # Collect unique items for stats
    all_themes = set()
    all_motifs = set()
    all_categories = set()

    for analysis in analyses.values():
        all_themes.update(t.name for t in analysis.themes)
        all_motifs.update(analysis.motifs)
        all_categories.update(analysis.tag_categories)

    stats.themes_created = len(all_themes)
    stats.motifs_created = len(all_motifs)
    stats.categories_found = len(all_categories)

    if dry_run:
        # Preview without database changes
        for entry_date, analysis in sorted(analyses.items()):
            if verbose:
                logger.info(
                    f"Would process: {entry_date} "
                    f"(rating={analysis.rating}, "
                    f"{len(analysis.themes)} themes, "
                    f"{len(analysis.motifs)} motifs)"
                )
            stats.entries_created += 1
        return stats

    # Import to database
    db = PalimpsestDB(db_path)

    with db.session_scope():
        for entry_date, analysis in sorted(analyses.items()):
            try:
                import_analysis_to_db(
                    analysis,
                    db,
                    stats,
                    verbose,
                )
            except Exception as e:
                logger.error(f"Error processing {entry_date}: {e}")
                stats.errors += 1

    logger.info("Changes committed to database")
    return stats


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import narrative analysis data into the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        help="Start date filter (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        help="End date filter (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=ANALYSIS_DIR,
        help=f"Analysis files directory (default: {ANALYSIS_DIR})",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DB_PATH,
        help=f"Database path (default: {DB_PATH})",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        stats = run_import(
            analysis_dir=args.analysis_dir,
            db_path=args.database,
            dry_run=args.dry_run,
            verbose=args.verbose,
            start_date=args.start,
            end_date=args.end,
        )

        print(f"\nImport complete: {stats.summary()}")

        if args.dry_run:
            print("\n(Dry run - no changes were made)")

        return 0 if stats.errors == 0 else 1

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

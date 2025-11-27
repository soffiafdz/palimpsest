"""
Wiki Pages Module
------------------

Special wiki page builders for Palimpsest metadata wiki.

This module provides functions to generate special wiki pages that aggregate
data across multiple entity types for navigation, statistics, and analysis.

Pages:
    - entries: Journal entries with chronological navigation
    - index: Wiki homepage with navigation and quick stats
    - stats: Comprehensive statistics dashboard
    - timeline: Chronological timeline view
    - analysis: Analytical report with patterns and insights

Usage:
    from dev.builders.wiki_pages import (
        export_index,
        export_entries_with_navigation,
        export_stats,
        export_timeline,
        export_analysis_report,
    )

    # Export homepage
    status = export_index(db, wiki_dir, journal_dir, force=False)

    # Export entries with navigation
    stats = export_entries_with_navigation(exporter, db, wiki_dir, journal_dir)

    # Export statistics dashboard
    status = export_stats(db, wiki_dir, journal_dir, force=False)

    # Export timeline
    status = export_timeline(db, wiki_dir, journal_dir, force=False)

    # Export analysis report
    status = export_analysis_report(db, wiki_dir, journal_dir, force=False)
"""
from .entries import export_entries_with_navigation
from .index import export_index
from .stats import export_stats
from .timeline import export_timeline
from .analysis import export_analysis_report

__all__ = [
    "export_entries_with_navigation",
    "export_index",
    "export_stats",
    "export_timeline",
    "export_analysis_report",
]

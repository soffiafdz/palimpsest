"""
Builders package for Palimpsest project.

Provides builder classes for generating various output formats from
journal source files:
- PdfBuilder: Generate annotated PDF compilations
- TxtBuilder: Process and format raw text exports
- Wiki builders: Export database entities to vimwiki pages

All builders follow a common interface defined by the base classes.

Wiki builders are organized in three modules:
- wiki.py: GenericEntityExporter and EntityConfig registry
- wiki_indexes.py: Custom index builders for entity types
- wiki_pages.py: Special page exports (index, stats, timeline, analysis)
"""

from dev.builders.base import BaseBuilder, BuilderStats
from dev.builders.pdfbuilder import BuildStats, PdfBuilder
from dev.builders.txtbuilder import ProcessingStats, TxtBuilder
from dev.builders.wiki import EntityConfig, GenericEntityExporter, write_if_changed
from dev.builders.wiki_indexes import (
    build_cities_index,
    build_entries_index,
    build_events_index,
    build_locations_index,
    build_people_index,
)
from dev.builders.wiki_pages import (
    export_analysis_report,
    export_index,
    export_stats,
    export_timeline,
)

__all__ = [
    # Base classes
    "BaseBuilder",
    "BuilderStats",
    # PDF builder
    "PdfBuilder",
    "BuildStats",
    # Text builder
    "TxtBuilder",
    "ProcessingStats",
    # Wiki builders - core
    "EntityConfig",
    "GenericEntityExporter",
    "write_if_changed",
    # Wiki builders - custom indexes
    "build_people_index",
    "build_entries_index",
    "build_locations_index",
    "build_cities_index",
    "build_events_index",
    # Wiki builders - special pages
    "export_index",
    "export_stats",
    "export_timeline",
    "export_analysis_report",
]

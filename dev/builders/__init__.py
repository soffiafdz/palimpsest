#!/usr/bin/env python3
"""
Builders package for Palimpsest project.

Provides builder classes for generating various output formats from
journal source files:
- PdfBuilder: Generate annotated PDF compilations
- TxtBuilder: Process and format raw text exports
- Narrative: Review document builders for scene/event/arc analysis

All builders follow a common interface defined by the base classes.

Note: Wiki export functionality has been migrated to dev/wiki/exporter.py
using Jinja2 templates for all entity pages, indexes, and special pages
(stats, timeline, analysis).
"""

from dev.builders.base import BaseBuilder, BuilderStats
from dev.builders.pdfbuilder import BuildStats, PdfBuilder
from dev.builders.txtbuilder import ProcessingStats, TxtBuilder
from dev.builders.narrative import (
    compile_review,
    compile_source_review,
    compile_timeline,
    extract_unmapped_scenes,
    compile_events_view,
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
    # Narrative review builders
    "compile_review",
    "compile_source_review",
    "compile_timeline",
    "extract_unmapped_scenes",
    "compile_events_view",
]

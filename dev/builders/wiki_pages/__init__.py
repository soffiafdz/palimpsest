#!/usr/bin/env python3
"""
__init__.py
-----------
Special wiki page builders for Palimpsest metadata wiki.

Provides functions to generate special wiki pages that aggregate
data across multiple entity types.

Pages:
    - index: Wiki homepage with navigation and quick stats
    - stats: Comprehensive statistics dashboard
    - timeline: Chronological timeline view
    - analysis: Analytical report with patterns and insights
"""
from .index import export_index
from .stats import export_stats
from .timeline import export_timeline
from .analysis import export_analysis_report

__all__ = [
    "export_index",
    "export_stats",
    "export_timeline",
    "export_analysis_report",
]

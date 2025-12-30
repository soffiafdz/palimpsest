#!/usr/bin/env python3
"""
Pipeline configuration modules.

This package contains declarative configurations for data pipeline operations:
- propagation_mappings: Tag/arc mappings for narrative analysis
"""

from dev.pipeline.configs.propagation_mappings import (
    PEOPLE_NAMES,
    LOCATIONS,
    TAG_CATEGORIES,
    THEMATIC_ARCS,
    clean_tags,
    get_tag_categories,
    get_thematic_arcs,
)

__all__ = [
    "PEOPLE_NAMES",
    "LOCATIONS",
    "TAG_CATEGORIES",
    "THEMATIC_ARCS",
    "clean_tags",
    "get_tag_categories",
    "get_thematic_arcs",
]

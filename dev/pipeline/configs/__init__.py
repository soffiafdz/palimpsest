#!/usr/bin/env python3
"""
Pipeline configuration modules.

This package contains declarative configurations for data pipeline operations:
- vocabulary: Consolidated vocabulary definitions for narrative analysis
"""

from dev.pipeline.configs.vocabulary import (
    MOTIFS,
    TAGS,
    THEMATIC_ARC_TO_MOTIF,
    TAG_CATEGORY_TO_TAG,
    PEOPLE_ALIASES,
    LOCATION_ALIASES,
    get_motifs_for_entry,
    get_tags_for_entry,
    normalize_person,
    normalize_location,
)

__all__ = [
    "MOTIFS",
    "TAGS",
    "THEMATIC_ARC_TO_MOTIF",
    "TAG_CATEGORY_TO_TAG",
    "PEOPLE_ALIASES",
    "LOCATION_ALIASES",
    "get_motifs_for_entry",
    "get_tags_for_entry",
    "normalize_person",
    "normalize_location",
]

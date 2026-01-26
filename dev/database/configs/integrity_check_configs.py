#!/usr/bin/env python3
"""
integrity_check_configs.py
---------------------------

Configuration-driven integrity checks for database health monitoring.

This module defines declarative integrity check configurations, eliminating
duplication in health_monitor.py's _check_*_integrity methods.
"""
from dataclasses import dataclass
from typing import Callable, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    Chapter,
    Character,
    Entry,
    NarratedDate,
    Person,
    PersonCharacterMap,
    Poem,
    PoemVersion,
    Reference,
    ReferenceSource,
)


@dataclass
class IntegrityCheck:
    """
    Configuration for a single integrity check.

    Attributes:
        check_name: Descriptive key for the result (e.g., "orphaned_poem_versions")
        query_builder: Function that takes a session and returns a count query
        description: Human-readable description of what this checks
    """
    check_name: str
    query_builder: Callable[[Session], int]
    description: str


@dataclass
class IntegrityCheckGroup:
    """
    Group of related integrity checks.

    Attributes:
        group_name: Name of the check group (e.g., "reference_integrity")
        checks: List of IntegrityCheck instances
    """
    group_name: str
    checks: List[IntegrityCheck]


# ========================================
# Reference Integrity Checks
# ========================================

def _count_refs_invalid_source(session: Session) -> int:
    """Count references with invalid source IDs."""
    return (
        session.query(Reference)
        .filter(Reference.source_id.isnot(None))
        .filter(~Reference.source_id.in_(session.query(ReferenceSource.id)))
        .count()
    )


def _count_refs_no_content(session: Session) -> int:
    """Count references without content."""
    return (
        session.query(Reference)
        .filter((Reference.content.is_(None)) | (Reference.content == ""))
        .count()
    )


REFERENCE_INTEGRITY_CHECKS = IntegrityCheckGroup(
    group_name="reference_integrity",
    checks=[
        IntegrityCheck(
            "references_with_invalid_source",
            _count_refs_invalid_source,
            "References pointing to non-existent sources"
        ),
        IntegrityCheck(
            "references_without_content",
            _count_refs_no_content,
            "References missing content field"
        ),
    ]
)


# ========================================
# Poem Integrity Checks
# ========================================

def _count_poems_no_versions(session: Session) -> int:
    """Count poems without any versions."""
    return (
        session.query(Poem)
        .filter(~Poem.id.in_(session.query(PoemVersion.poem_id)))
        .count()
    )


def _count_duplicate_hashes(session: Session) -> int:
    """Count duplicate poem version hashes."""
    return (
        session.query(PoemVersion.version_hash, func.count(PoemVersion.id))
        .filter(PoemVersion.version_hash.isnot(None))
        .group_by(PoemVersion.version_hash)
        .having(func.count(PoemVersion.id) > 1)
        .count()
    )


def _count_versions_no_content(session: Session) -> int:
    """Count poem versions without content."""
    return (
        session.query(PoemVersion)
        .filter((PoemVersion.content.is_(None)) | (PoemVersion.content == ""))
        .count()
    )


def _count_orphaned_versions(session: Session) -> int:
    """Count orphaned poem versions (poem deleted)."""
    return (
        session.query(PoemVersion)
        .filter(~PoemVersion.poem_id.in_(session.query(Poem.id)))
        .count()
    )


POEM_INTEGRITY_CHECKS = IntegrityCheckGroup(
    group_name="poem_integrity",
    checks=[
        IntegrityCheck(
            "poems_without_versions",
            _count_poems_no_versions,
            "Poems with no versions stored"
        ),
        IntegrityCheck(
            "duplicate_poem_versions",
            _count_duplicate_hashes,
            "Poem versions with duplicate content hashes"
        ),
        IntegrityCheck(
            "poem_versions_without_content",
            _count_versions_no_content,
            "Poem versions missing content"
        ),
        IntegrityCheck(
            "orphaned_poem_versions",
            _count_orphaned_versions,
            "Poem versions whose parent poem was deleted"
        ),
    ]
)


# ========================================
# Manuscript Integrity Checks
# ========================================

def _count_orphaned_chapters(session: Session) -> int:
    """Count chapters with invalid part reference."""
    from ..models import Part
    return (
        session.query(Chapter)
        .filter(Chapter.part_id.isnot(None))
        .filter(~Chapter.part_id.in_(session.query(Part.id)))
        .count()
    )


def _count_orphaned_character_mappings(session: Session) -> int:
    """Count character mappings with invalid person reference."""
    return (
        session.query(PersonCharacterMap)
        .filter(~PersonCharacterMap.person_id.in_(session.query(Person.id)))
        .count()
    )


def _count_characters_no_name(session: Session) -> int:
    """Count characters without name."""
    return (
        session.query(Character)
        .filter((Character.name.is_(None)) | (Character.name == ""))
        .count()
    )


MANUSCRIPT_INTEGRITY_CHECKS = IntegrityCheckGroup(
    group_name="manuscript_integrity",
    checks=[
        IntegrityCheck(
            "orphaned_chapters",
            _count_orphaned_chapters,
            "Chapters whose part reference is invalid"
        ),
        IntegrityCheck(
            "orphaned_character_mappings",
            _count_orphaned_character_mappings,
            "Character mappings whose person was deleted"
        ),
        IntegrityCheck(
            "characters_without_name",
            _count_characters_no_name,
            "Characters missing name"
        ),
    ]
)


# ========================================
# Narrated Date Integrity Checks
# ========================================

def _count_orphaned_narrated_dates(session: Session) -> int:
    """Count narrated dates without parent entry."""
    return (
        session.query(NarratedDate)
        .filter(~NarratedDate.entry_id.in_(session.query(Entry.id)))
        .count()
    )


def _count_narrated_dates_no_date(session: Session) -> int:
    """Count narrated dates without actual date value."""
    return (
        session.query(NarratedDate)
        .filter(NarratedDate.date.is_(None))
        .count()
    )


NARRATED_DATE_INTEGRITY_CHECKS = IntegrityCheckGroup(
    group_name="narrated_date_integrity",
    checks=[
        IntegrityCheck(
            "orphaned_narrated_dates",
            _count_orphaned_narrated_dates,
            "Narrated dates whose parent entry was deleted"
        ),
        IntegrityCheck(
            "narrated_dates_without_date",
            _count_narrated_dates_no_date,
            "Narrated dates missing date value"
        ),
    ]
)


# ========================================
# All Integrity Check Groups
# ========================================

ALL_INTEGRITY_CHECK_GROUPS = [
    REFERENCE_INTEGRITY_CHECKS,
    POEM_INTEGRITY_CHECKS,
    MANUSCRIPT_INTEGRITY_CHECKS,
    NARRATED_DATE_INTEGRITY_CHECKS,
]

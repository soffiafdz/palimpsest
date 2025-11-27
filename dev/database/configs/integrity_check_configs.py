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
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    Entry,
    Person,
    Location,
    City,
    Reference,
    ReferenceSource,
    Poem,
    PoemVersion,
    Tag,
    MentionedDate,
)
from ..models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    Theme,
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

def _count_orphaned_ms_entries(session: Session) -> int:
    """Count manuscript entries without base entry."""
    return (
        session.query(ManuscriptEntry)
        .filter(~ManuscriptEntry.entry_id.in_(session.query(Entry.id)))
        .count()
    )


def _count_orphaned_ms_people(session: Session) -> int:
    """Count manuscript people without base person."""
    return (
        session.query(ManuscriptPerson)
        .filter(~ManuscriptPerson.person_id.in_(session.query(Person.id)))
        .count()
    )


def _count_ms_people_no_character(session: Session) -> int:
    """Count manuscript people without character name."""
    return (
        session.query(ManuscriptPerson)
        .filter((ManuscriptPerson.character.is_(None)) | (ManuscriptPerson.character == ""))
        .count()
    )


MANUSCRIPT_INTEGRITY_CHECKS = IntegrityCheckGroup(
    group_name="manuscript_integrity",
    checks=[
        IntegrityCheck(
            "orphaned_manuscript_entries",
            _count_orphaned_ms_entries,
            "Manuscript entries whose base entry was deleted"
        ),
        IntegrityCheck(
            "orphaned_manuscript_people",
            _count_orphaned_ms_people,
            "Manuscript characters whose base person was deleted"
        ),
        IntegrityCheck(
            "manuscript_people_without_character_name",
            _count_ms_people_no_character,
            "Manuscript people missing character name"
        ),
    ]
)


# ========================================
# Mentioned Date Integrity Checks
# ========================================

def _count_orphaned_mentioned_dates(session: Session) -> int:
    """Count mentioned dates without parent entry."""
    return (
        session.query(MentionedDate)
        .filter(~MentionedDate.entry_id.in_(session.query(Entry.id)))
        .count()
    )


def _count_mentioned_dates_no_date(session: Session) -> int:
    """Count mentioned dates without actual date."""
    return (
        session.query(MentionedDate)
        .filter(MentionedDate.date.is_(None))
        .count()
    )


def _count_mentioned_dates_no_context(session: Session) -> int:
    """Count mentioned dates without context."""
    return (
        session.query(MentionedDate)
        .filter((MentionedDate.context.is_(None)) | (MentionedDate.context == ""))
        .count()
    )


MENTIONED_DATE_INTEGRITY_CHECKS = IntegrityCheckGroup(
    group_name="mentioned_date_integrity",
    checks=[
        IntegrityCheck(
            "orphaned_mentioned_dates",
            _count_orphaned_mentioned_dates,
            "Mentioned dates whose parent entry was deleted"
        ),
        IntegrityCheck(
            "mentioned_dates_without_date",
            _count_mentioned_dates_no_date,
            "Mentioned dates missing date value"
        ),
        IntegrityCheck(
            "mentioned_dates_without_context",
            _count_mentioned_dates_no_context,
            "Mentioned dates missing context"
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
    MENTIONED_DATE_INTEGRITY_CHECKS,
]

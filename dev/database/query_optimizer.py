#!/usr/bin/env python3
"""
query_optimizer.py
------------------
Optimized query strategies to eliminate N+1 query problems.

This module provides utilities for efficient relationship loading in SQLAlchemy,
preventing performance issues when accessing related objects in loops.

Classes:
    - QueryOptimizer: Optimized query builders for common operations
    - RelationshipLoader: Preload relationships for existing objects
    - HierarchicalBatcher: Batch entries by natural date hierarchy

The Problem:
    # Naive approach - triggers thousands of queries
    entries = session.query(Entry).all()  # 1 query
    for entry in entries:  # 1000 iterations
        people = entry.people  # 1 query each = 1000 queries
        for person in people:
            aliases = person.aliases  # 5000 more queries

The Solution:
    # Optimized approach - uses ~10 queries total
    entries = QueryOptimizer.for_export(session, entry_ids)
    for entry in entries:  # 1000 iterations
        people = entry.people  # FREE - already loaded
        for person in people:
            aliases = person.aliases  # FREE - already loaded

Usage:
    from dev.database.query_optimizer import QueryOptimizer, HierarchicalBatcher

    # Export with optimized loading
    batches = HierarchicalBatcher.create_batches(session, threshold=500)
    for batch in batches:
        for entry in batch.entries:
            # All relationships already loaded
            export_entry(entry)
"""

from __future__ import annotations

from dataclasses import dataclass

# from datetime import date
from typing import List, Optional

from sqlalchemy import extract  # , func
from sqlalchemy.orm import Session, selectinload

from .models import (
    Entry,
    Person,
    # Alias,
    Location,
    # City,
    Event,
    # Tag,
    # MentionedDate,
    Reference,
    # ReferenceSource,
    PoemVersion,
    # Poem,
)
from .models_manuscript import ManuscriptEntry


class QueryOptimizer:
    """
    Optimized query builders for common operations.

    Provides static methods that return queries with relationships
    preloaded using selectinload, preventing N+1 query problems.

    Each method is optimized for a specific use case, loading only
    the relationships needed for that operation.
    """

    @staticmethod
    def for_export(session: Session, entry_ids: List[int]) -> List[Entry]:
        """
        Load entries optimized for export operations.

        Use this when exporting entries to Markdown/YAML, where you need
        to access all metadata and relationships.

        Loads:
            - People with aliases and manuscript info
            - Locations with parent cities
            - Cities
            - Events with manuscript info
            - Tags, dates, references, poems
            - Manuscript metadata with themes

        Args:
            session: Active SQLAlchemy session
            entry_ids: List of entry IDs to load

        Returns:
            List of Entry objects with all relationships preloaded

        Examples:
            >>> entry_ids = [e.id for e in session.query(Entry.id).all()]
            >>> entries = QueryOptimizer.for_export(session, entry_ids)
            >>> for entry in entries:
            ...     # All these are FREE (no queries):
            ...     people = entry.people
            ...     locations = entry.locations
            ...     tags = entry.tags
        """
        return (
            session.query(Entry)
            .filter(Entry.id.in_(entry_ids))
            .options(
                # People with their details
                selectinload(Entry.people).selectinload(Person.aliases),
                selectinload(Entry.people).selectinload(Person.manuscript),
                # Locations with parent cities
                selectinload(Entry.locations).selectinload(Location.city),
                # Cities
                selectinload(Entry.cities),
                # Events with manuscript info
                selectinload(Entry.events).selectinload(Event.manuscript),
                # Simple collections
                selectinload(Entry.tags),
                selectinload(Entry.dates),
                # References with sources
                selectinload(Entry.references).selectinload(Reference.source),
                # Poems with parent poem
                selectinload(Entry.poems).selectinload(PoemVersion.poem),
                # Manuscript with themes
                selectinload(Entry.manuscript).selectinload(ManuscriptEntry.themes),
            )
            .all()
        )

    @staticmethod
    def for_display(session: Session, entry_id: int) -> Optional[Entry]:
        """
        Load single entry for display operations.

        Use this when showing entry details in CLI or UI, where you
        need basic metadata but not everything.

        Loads:
            - People (names only)
            - Locations (names only)
            - Tags
            - Events

        Skips:
            - Aliases, manuscript details, references, poems

        Args:
            session: Active SQLAlchemy session
            entry_id: Entry ID to load

        Returns:
            Entry object with display relationships preloaded

        Examples:
            >>> entry = QueryOptimizer.for_display(session, entry_id)
            >>> print(f"People: {', '.join(p.name for p in entry.people)}")
            >>> print(f"Location: {entry.locations[0].name if entry.locations else 'None'}")
        """
        return (
            session.query(Entry)
            .filter(Entry.id == entry_id)
            .options(
                selectinload(Entry.people),
                selectinload(Entry.locations),
                selectinload(Entry.tags),
                selectinload(Entry.events),
            )
            .first()
        )

    @staticmethod
    def for_year(session: Session, year: int) -> List[Entry]:
        """
        Load all entries for a specific year with relationships.

        Args:
            session: Active SQLAlchemy session
            year: Year to query

        Returns:
            List of Entry objects sorted by date

        Examples:
            >>> entries_2024 = QueryOptimizer.for_year(session, 2024)
        """
        return (
            session.query(Entry)
            .filter(extract("year", Entry.date) == year)
            .order_by(Entry.date)
            .options(
                selectinload(Entry.people).selectinload(Person.aliases),
                selectinload(Entry.locations).selectinload(Location.city),
                selectinload(Entry.cities),
                selectinload(Entry.events),
                selectinload(Entry.tags),
                selectinload(Entry.dates),
                selectinload(Entry.references).selectinload(Reference.source),
                selectinload(Entry.poems).selectinload(PoemVersion.poem),
            )
            .all()
        )

    @staticmethod
    def for_month(session: Session, year: int, month: int) -> List[Entry]:
        """
        Load all entries for a specific month with relationships.

        Args:
            session: Active SQLAlchemy session
            year: Year to query
            month: Month to query (1-12)

        Returns:
            List of Entry objects sorted by date

        Examples:
            >>> entries_jan = QueryOptimizer.for_month(session, 2024, 1)
        """
        return (
            session.query(Entry)
            .filter(
                extract("year", Entry.date) == year,
                extract("month", Entry.date) == month,
            )
            .order_by(Entry.date)
            .options(
                selectinload(Entry.people).selectinload(Person.aliases),
                selectinload(Entry.locations).selectinload(Location.city),
                selectinload(Entry.cities),
                selectinload(Entry.events),
                selectinload(Entry.tags),
                selectinload(Entry.dates),
                selectinload(Entry.references).selectinload(Reference.source),
                selectinload(Entry.poems).selectinload(PoemVersion.poem),
            )
            .all()
        )


class RelationshipLoader:
    """
    Preload relationships for existing entry collections.

    Use this when you already have Entry objects and need to access
    their relationships in a loop. Call preload() before iteration
    to load everything at once.
    """

    @staticmethod
    def preload_for_entries(session: Session, entries: List[Entry]) -> None:
        """
        Preload all relationships for a list of entries.

        This modifies the entries in-place by triggering SQLAlchemy
        to load their relationships. After calling this, accessing
        entry.people, entry.locations, etc. is free (no queries).

        Args:
            session: Active SQLAlchemy session
            entries: List of Entry objects to preload

        Examples:
            >>> # Get entries from some query
            >>> entries = session.query(Entry).filter(...).all()
            >>>
            >>> # Before iteration, preload relationships
            >>> RelationshipLoader.preload_for_entries(session, entries)
            >>>
            >>> # Now iterate freely - no queries triggered
            >>> for entry in entries:
            ...     people = entry.people  # FREE
            ...     locations = entry.locations  # FREE
        """
        if not entries:
            return

        entry_ids = [e.id for e in entries]

        # Execute one query per relationship type
        # SQLAlchemy matches results back to our existing entry objects
        session.query(Entry).filter(Entry.id.in_(entry_ids)).options(
            selectinload(Entry.people).selectinload(Person.aliases),
            selectinload(Entry.locations).selectinload(Location.city),
            selectinload(Entry.cities),
            selectinload(Entry.events),
            selectinload(Entry.tags),
            selectinload(Entry.dates),
            selectinload(Entry.references).selectinload(Reference.source),
            selectinload(Entry.poems).selectinload(PoemVersion.poem),
        ).all()


@dataclass
class DateBatch:
    """
    Container for a batch of entries grouped by date hierarchy.

    Represents either a full year or a specific month, depending on
    how many entries exist in that period.

    Attributes:
        year: Year number
        month: Month number (1-12) or None for full year
        entries: List of Entry objects in this period
    """

    year: int
    month: Optional[int]
    entries: List[Entry]

    @property
    def entry_count(self) -> int:
        """Number of entries in this batch."""
        return len(self.entries)

    @property
    def period_label(self) -> str:
        """Human-readable period label."""
        if self.month:
            return f"{self.year}-{self.month:02d}"
        return str(self.year)

    @property
    def is_monthly(self) -> bool:
        """Whether this batch represents a single month."""
        return self.month is not None

    @property
    def is_yearly(self) -> bool:
        """Whether this batch represents a full year."""
        return self.month is None

    def __repr__(self) -> str:
        return f"<DateBatch {self.period_label}: {self.entry_count} entries>"

    def __str__(self) -> str:
        return f"{self.period_label} ({self.entry_count} entries)"


class HierarchicalBatcher:
    """
    Batch entries by natural date hierarchy (years and months).

    Instead of arbitrary pagination (page 1, page 2), this batches
    entries by their natural structure: years and months.

    Logic:
        - If year has <= threshold entries: load entire year
        - If year has > threshold entries: split into months

    This provides natural, meaningful batches for processing.
    """

    @staticmethod
    def get_years(session: Session) -> List[int]:
        """
        Get all years that have entries.

        Returns:
            Sorted list of years: [2020, 2021, 2022, 2023, 2024]

        Examples:
            >>> years = HierarchicalBatcher.get_years(session)
            >>> print(years)
            [2020, 2021, 2022, 2023, 2024]
        """
        years = (
            session.query(extract("year", Entry.date).label("year"))
            .distinct()
            .order_by("year")
            .all()
        )

        return [int(row.year) for row in years]

    @staticmethod
    def get_months_for_year(session: Session, year: int) -> List[int]:
        """
        Get all months in a year that have entries.

        Args:
            year: Year to query

        Returns:
            Sorted list of months: [1, 2, 5, 8, 10, 12]

        Examples:
            >>> months = HierarchicalBatcher.get_months_for_year(session, 2024)
            >>> print(months)
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        """
        months = (
            session.query(extract("month", Entry.date).label("month"))
            .filter(extract("year", Entry.date) == year)
            .distinct()
            .order_by("month")
            .all()
        )

        return [int(row.month) for row in months]

    @staticmethod
    def count_year_entries(session: Session, year: int) -> int:
        """
        Count entries in a specific year.

        Args:
            session: Active SQLAlchemy session
            year: Year to count

        Returns:
            Number of entries in the year

        Examples:
            >>> count = HierarchicalBatcher.count_year_entries(session, 2024)
            >>> print(f"2024 has {count} entries")
        """
        return session.query(Entry).filter(extract("year", Entry.date) == year).count()

    @staticmethod
    def count_month_entries(session: Session, year: int, month: int) -> int:
        """
        Count entries in a specific month.

        Args:
            session: Active SQLAlchemy session
            year: Year to count
            month: Month to count (1-12)

        Returns:
            Number of entries in the month

        Examples:
            >>> count = HierarchicalBatcher.count_month_entries(session, 2024, 6)
            >>> print(f"June 2024 has {count} entries")
        """
        return (
            session.query(Entry)
            .filter(
                extract("year", Entry.date) == year,
                extract("month", Entry.date) == month,
            )
            .count()
        )

    @staticmethod
    def create_batches(session: Session, threshold: int = 500) -> List[DateBatch]:
        """
        Create hierarchical batches based on entry volume.

        This is the main method to use. It intelligently creates batches
        based on how many entries exist in each period:

        - Small years (≤ threshold): One batch for entire year
        - Large years (> threshold): Split into monthly batches

        Args:
            session: Active SQLAlchemy session
            threshold: Max entries per batch (default: 500)

        Returns:
            List of DateBatch objects ready to process

        Examples:
            >>> # Create batches with default threshold
            >>> batches = HierarchicalBatcher.create_batches(session)
            >>>
            >>> for batch in batches:
            ...     print(f"Processing {batch.period_label}: {batch.entry_count} entries")
            ...     for entry in batch.entries:
            ...         # All relationships already loaded
            ...         process_entry(entry)

            >>> # Create batches with custom threshold
            >>> batches = HierarchicalBatcher.create_batches(session, threshold=300)

            >>> # Typical output:
            >>> # Processing 2020: 234 entries (full year, under threshold)
            >>> # Processing 2021-01: 87 entries (monthly, year over threshold)
            >>> # Processing 2021-02: 93 entries
            >>> # ...
            >>> # Processing 2024: 456 entries (full year, under threshold)
        """
        batches: List[DateBatch] = []
        years = HierarchicalBatcher.get_years(session)

        for year in years:
            year_count = HierarchicalBatcher.count_year_entries(session, year)

            if year_count <= threshold:
                # Load entire year as one batch
                entries = QueryOptimizer.for_year(session, year)
                batches.append(DateBatch(year=year, month=None, entries=entries))
            else:
                # Split into monthly batches
                months = HierarchicalBatcher.get_months_for_year(session, year)

                for month in months:
                    entries = QueryOptimizer.for_month(session, year, month)
                    batches.append(DateBatch(year=year, month=month, entries=entries))

        return batches

    @staticmethod
    def create_yearly_batch(session: Session, year: int) -> DateBatch:
        """
        Create a batch for a specific year.

        Args:
            session: Active SQLAlchemy session
            year: Year to batch

        Returns:
            DateBatch for the year

        Examples:
            >>> batch = HierarchicalBatcher.create_yearly_batch(session, 2024)
            >>> print(f"2024 has {batch.entry_count} entries")
        """
        entries = QueryOptimizer.for_year(session, year)
        return DateBatch(year=year, month=None, entries=entries)

    @staticmethod
    def create_monthly_batch(session: Session, year: int, month: int) -> DateBatch:
        """
        Create a batch for a specific month.

        Args:
            session: Active SQLAlchemy session
            year: Year to batch
            month: Month to batch (1-12)

        Returns:
            DateBatch for the month

        Examples:
            >>> batch = HierarchicalBatcher.create_monthly_batch(session, 2024, 6)
            >>> print(f"June 2024 has {batch.entry_count} entries")
        """
        entries = QueryOptimizer.for_month(session, year, month)
        return DateBatch(year=year, month=month, entries=entries)


# ==================== USAGE EXAMPLES ====================

"""
EXAMPLE 1: Export all entries efficiently
------------------------------------------

from dev.database.query_optimizer import HierarchicalBatcher

with db.session_scope() as session:
    # Create hierarchical batches
    batches = HierarchicalBatcher.create_batches(session, threshold=500)
    
    for batch in batches:
        print(f"📦 Processing {batch.period_label} ({batch.entry_count} entries)")
        
        for entry in batch.entries:
            # All relationships already loaded - no queries!
            export_entry_to_markdown(entry)

# Output:
# 📦 Processing 2020 (234 entries)
# 📦 Processing 2021-01 (458 entries)
# 📦 Processing 2021-02 (502 entries)
# 📦 Processing 2022 (389 entries)


EXAMPLE 2: Export specific year
--------------------------------

with db.session_scope() as session:
    batch = HierarchicalBatcher.create_yearly_batch(session, 2024)
    
    print(f"Exporting {batch.entry_count} entries from 2024")
    
    for entry in batch.entries:
        export_entry_to_markdown(entry)


EXAMPLE 3: Preload relationships for existing entries
-----------------------------------------------------

from dev.database.query_optimizer import RelationshipLoader

with db.session_scope() as session:
    # Get entries from some query
    entries = session.query(Entry).filter(
        Entry.word_count > 1000
    ).all()
    
    # Preload relationships before iterating
    RelationshipLoader.preload_for_entries(session, entries)
    
    # Now iterate freely - no queries triggered
    for entry in entries:
        people = entry.people  # FREE
        locations = entry.locations  # FREE
        process_entry(entry)


EXAMPLE 4: Get years and months for navigation
----------------------------------------------

with db.session_scope() as session:
    years = HierarchicalBatcher.get_years(session)
    print(f"Available years: {years}")
    
    for year in years:
        count = HierarchicalBatcher.count_year_entries(session, year)
        print(f"  {year}: {count} entries")
        
        months = HierarchicalBatcher.get_months_for_year(session, year)
        for month in months:
            count = HierarchicalBatcher.count_month_entries(session, year, month)
            print(f"    {year}-{month:02d}: {count} entries")
"""

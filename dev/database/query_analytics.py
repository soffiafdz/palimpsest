#!/usr/bin/env python3
"""
query_analytics.py
------------------
Complex queries and analytics for the database.

Provides comprehensive analytical queries and statistics generation
for the Palimpsest database, including:
    - Database statistics and counts
    - Entry summaries with optimized loading
    - Date range queries
    - Full-text search across entries
    - Filtering by people, locations, cities, events, tags
    - Year and month analytics with breakdowns
    - Timeline overviews
    - Manuscript analytics

Features:
    - Optimized queries using QueryOptimizer
    - Hierarchical batching for large datasets
    - Monthly and yearly aggregations
    - Top mentions and frequency analysis
    - Migration status tracking
    - Comprehensive error handling

Key Methods:
    Statistics:
        - get_database_stats: Overall database counts and metrics
        - get_entry_summary: Quick summary of single entry
        - get_timeline_overview: Full journal timeline
        - get_manuscript_analytics: Manuscript-specific metrics

    Queries:
        - get_entries_by_date_range: Filter by date range
        - search_entries: Full-text search
        - get_entries_by_person: Filter by person mentions
        - get_entries_by_city: Filter by city
        - get_entries_by_location: Filter by specific venue
        - get_entries_by_tag: Filter by tag

    Analytics:
        - get_year_analytics: Comprehensive year statistics
        - get_month_analytics: Detailed month statistics
        - _get_top_people: Most mentioned people
        - _get_top_locations: Most visited locations

Usage:
    >>> analytics = QueryAnalytics(logger)
    >>>
    >>> # Get overall stats
    >>> stats = analytics.get_database_stats(session)
    >>>
    >>> # Get year breakdown
    >>> year_stats = analytics.get_year_analytics(session, 2024)
    >>>
    >>> # Search entries
    >>> results = analytics.search_entries(session, "dream", limit=10)
    >>>
    >>> # Get timeline
    >>> timeline = analytics.get_timeline_overview(session)

Notes:
    - Uses QueryOptimizer for efficient relationship loading
    - Supports hierarchical batching via HierarchicalBatcher
    - Returns comprehensive dictionaries with computed metrics
    - All date fields returned as ISO format strings
"""
from datetime import datetime, timedelta, date
from sqlite3 import DatabaseError
from typing import Dict, Any, List, Optional, Union

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from dev.core.logging_manager import PalimpsestLogger, safe_logger

from .decorators import DatabaseOperation
from .query_optimizer import QueryOptimizer, HierarchicalBatcher
from .models import (
    Arc,
    Chapter,
    ChapterStatus,
    City,
    Entry,
    Event,
    Location,
    Person,
    Poem,
    PoemVersion,
    Reference,
    ReferenceSource,
    Scene,
    Tag,
    Theme,
    Thread,
)


class QueryAnalytics:
    """
    Handles complex queries and database analytics.

    Provides advanced querying capabilities, statistics generation,
    and data analysis functions.
    """

    def __init__(self, logger: Optional[PalimpsestLogger] = None) -> None:
        """
        Initialize query analytics.

        Args:
            logger: Optional logger for query operations
        """
        self.logger = logger

    def get_database_stats(self, session: Session) -> Dict[str, Any]:
        """
        Get comprehensive database statistics.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with database statistics
        """
        with DatabaseOperation(self.logger, "get_database_stats"):
            stats = {}

            # Basic counts
            stats["entries"] = session.query(Entry).count()
            stats["people"] = session.query(Person).count()
            stats["cities"] = session.query(City).count()
            stats["locations"] = session.query(Location).count()
            stats["scenes"] = session.query(Scene).count()
            stats["events"] = session.query(Event).count()
            stats["arcs"] = session.query(Arc).count()
            stats["threads"] = session.query(Thread).count()
            stats["tags"] = session.query(Tag).count()
            stats["themes"] = session.query(Theme).count()
            stats["references"] = session.query(Reference).count()
            stats["reference_sources"] = session.query(ReferenceSource).count()
            stats["poems"] = session.query(Poem).count()
            stats["poem_versions"] = session.query(PoemVersion).count()

            # Date range
            first_entry = session.query(Entry).order_by(Entry.date).first()
            last_entry = session.query(Entry).order_by(Entry.date.desc()).first()

            if first_entry and last_entry:
                stats["date_range"] = {
                    "first_entry": first_entry.date.isoformat(),
                    "last_entry": last_entry.date.isoformat(),
                    "total_days": (last_entry.date - first_entry.date).days + 1,
                }

            # Word count stats
            total_words = session.query(func.sum(Entry.word_count)).scalar() or 0
            stats["total_words"] = total_words

            if stats["entries"] > 0:
                avg_words = total_words / stats["entries"]
                stats["average_words_per_entry"] = round(avg_words, 2)

            # Recent activity
            week_ago = datetime.now() - timedelta(days=7)
            stats["entries_updated_last_7_days"] = (
                session.query(Entry).filter(Entry.updated_at >= week_ago).count()
            )

            # Get migration status if possible
            try:
                stats["migration_status"] = self._get_migration_status(session)
            except DatabaseError as e:
                stats["migration_status"] = {"status": "error", "error": str(e)}
                safe_logger(self.logger).log_error(e, {"operation": "get_migration_status"})

            return stats

    def _get_migration_status(self, session: Session) -> Dict[str, Optional[str]]:
        """
        Get the current migration status of the database.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with migration status information

        Raises:
            DatabaseError: If unable to determine migration status
        """
        try:
            from alembic.runtime.migration import MigrationContext

            connection = session.connection()
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

            return {
                "current_revision": current_rev,
                "status": "up_to_date" if current_rev else "needs_migration",
            }
        except ImportError as e:
            raise DatabaseError(f"Alembic not available: {e}")
        except Exception as e:
            raise DatabaseError(f"Failed to get migration status: {e}")

    def get_entry_summary(
        self, session: Session, entry_date: Union[str, date]
    ) -> Dict[str, Any]:
        """
        Get quick summary of an entry with optimized loading.

        Args:
            session: SQLAlchemy session
            entry_date: Date to query

        Returns:
            Dictionary with entry summary
        """
        with DatabaseOperation(self.logger, "get_entry_summary"):
            if isinstance(entry_date, str):
                entry_date = date.fromisoformat(entry_date)

            entry = session.query(Entry).filter_by(date=entry_date).first()
            if not entry:
                return {"error": "Entry not found"}

            # Use display-optimized query
            entry = QueryOptimizer.for_display(session, entry.id)

            summary = {}
            if entry is not None:
                summary = {
                    "date": entry.date.isoformat(),
                    "word_count": entry.word_count,
                    "reading_time": entry.reading_time,
                    "people_count": len(entry.people),
                    "people": [p.display_name for p in entry.people],
                    "locations_count": len(entry.locations),
                    "locations": [loc.name for loc in entry.locations],
                    "events_count": len(entry.events),
                    "events": [evt.display_name for evt in entry.events],
                    "tags": [tag.tag for tag in entry.tags],
                }

            return summary

    def get_entries_by_date_range(
        self, session: Session, start_date: Union[str, date], end_date: Union[str, date]
    ) -> List[Entry]:
        """
        Get entries within a date range.

        Args:
            session: SQLAlchemy session
            start_date: Start date
            end_date: End date

        Returns:
            List of Entry instances
        """
        with DatabaseOperation(self.logger, "get_entries_by_date_range"):
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)

            return (
                session.query(Entry)
                .filter(Entry.date >= start_date, Entry.date <= end_date)
                .order_by(Entry.date)
                .all()
            )

    def search_entries(
        self, session: Session, query: str, limit: Optional[int] = None
    ) -> List[Entry]:
        """
        Search entries by content.

        Args:
            session: SQLAlchemy session
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching Entry instances
        """
        with DatabaseOperation(self.logger, "search_entries"):
            search_filter = or_(
                Entry.notes.ilike(f"%{query}%"), Entry.epigraph.ilike(f"%{query}%")
            )

            query_obj = (
                session.query(Entry).filter(search_filter).order_by(Entry.date.desc())
            )

            if limit:
                query_obj = query_obj.limit(limit)

            return query_obj.all()

    def get_entries_by_person(self, session: Session, person_name: str) -> List[Entry]:
        """Get all entries mentioning a specific person."""
        with DatabaseOperation(self.logger, "get_entries_by_person"):
            person = (
                session.query(Person)
                .filter(
                    or_(
                        Person.name.ilike(f"%{person_name}%"),
                        Person.full_name.ilike(f"%{person_name}%"),
                    )
                )
                .first()
            )

            return person.entries if person else []

    def get_entries_by_city(self, session: Session, city_name: str) -> List[Entry]:
        """Get all entries at a specific city."""
        with DatabaseOperation(self.logger, "get_entries_by_city"):
            city = (
                session.query(City).filter(City.name.ilike(f"%{city_name}%")).first()
            )

            return city.entries if city else []

    def get_entries_by_location(
        self, session: Session, location_name: str
    ) -> List[Entry]:
        """Get all entries at a specific location."""
        with DatabaseOperation(self.logger, "get_entries_by_location"):
            location = (
                session.query(Location)
                .filter(Location.name.ilike(f"%{location_name}%"))
                .first()
            )

            return location.entries if location else []

    def get_entries_by_tag(self, session: Session, tag_name: str) -> List[Entry]:
        """Get all entries with a specific tag."""
        with DatabaseOperation(self.logger, "get_entries_by_tag"):
            tag = session.query(Tag).filter(Tag.tag.ilike(f"%{tag_name}%")).first()

            return tag.entries if tag else []

    def _compute_entry_analytics(self, entries: List[Entry]) -> Dict[str, Any]:
        """
        Compute analytics from a list of entries.

        Args:
            entries: List of Entry objects with relationships loaded

        Returns:
            Dictionary with computed analytics
        """
        total_words = sum(e.word_count for e in entries)
        return {
            "total_entries": len(entries),
            "total_words": total_words,
            "avg_words": total_words / len(entries) if entries else 0,
            "unique_people": len({p.id for e in entries for p in e.people}),
            "top_people": self._get_top_people(entries, limit=5),
            "unique_locations": len({loc.id for e in entries for loc in e.locations}),
            "top_locations": self._get_top_locations(entries, limit=5),
            "unique_cities": len({city.id for e in entries for city in e.cities}),
            "unique_events": len({evt.id for e in entries for evt in e.events}),
            "total_references": sum(len(e.references) for e in entries),
            "total_poems": sum(len(e.poems) for e in entries),
        }

    def get_year_analytics(self, session: Session, year: int) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a specific year with optimized loading.

        Args:
            session: SQLAlchemy session
            year: Year to analyze

        Returns:
            Dictionary with year analytics including monthly breakdown
        """
        with DatabaseOperation(self.logger, "get_year_analytics"):
            entries = QueryOptimizer.for_year(session, year)
            analytics = {"year": year, **self._compute_entry_analytics(entries)}

            # Monthly breakdown
            monthly = {}
            for entry in entries:
                month_key = entry.date.strftime("%Y-%m")
                if month_key not in monthly:
                    monthly[month_key] = {"entries": 0, "words": 0}
                monthly[month_key]["entries"] += 1
                monthly[month_key]["words"] += entry.word_count
            analytics["monthly_breakdown"] = monthly

            return analytics

    def get_month_analytics(self, session: Session, year: int, month: int) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a specific month with optimized loading.

        Args:
            session: SQLAlchemy session
            year: Year to analyze
            month: Month to analyze (1-12)

        Returns:
            Dictionary with month analytics
        """
        with DatabaseOperation(self.logger, "get_month_analytics"):
            entries = QueryOptimizer.for_month(session, year, month)
            return {"year": year, "month": month, **self._compute_entry_analytics(entries)}

    def _get_top_people(
        self, entries: List[Entry], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get most mentioned people in entries."""
        from collections import Counter

        people_count = Counter()
        for entry in entries:
            for person in entry.people:
                people_count[person.display_name] += 1

        return [
            {"name": name, "mentions": count}
            for name, count in people_count.most_common(limit)
        ]

    def _get_top_locations(
        self, entries: List[Entry], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get most visited locations in entries."""
        from collections import Counter

        location_count = Counter()
        for entry in entries:
            for location in entry.locations:
                location_count[location.name] += 1

        return [
            {"name": name, "visits": count}
            for name, count in location_count.most_common(limit)
        ]

    def get_timeline_overview(self, session: Session) -> Dict[str, Any]:
        """
        Get overview of entire journal timeline.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with timeline analytics
        """
        with DatabaseOperation(self.logger, "get_timeline_overview"):
            years = HierarchicalBatcher.get_years(session)

            overview = {
                "total_years": len(years),
                "year_range": {
                    "start": min(years) if years else None,
                    "end": max(years) if years else None,
                },
                "years": [],
            }

            for year in years:
                year_count = HierarchicalBatcher.count_year_entries(session, year)
                months = HierarchicalBatcher.get_months_for_year(session, year)

                year_data = {
                    "year": year,
                    "total_entries": year_count,
                    "months_active": len(months),
                    "months": [],
                }

                for month in months:
                    month_count = HierarchicalBatcher.count_month_entries(
                        session, year, month
                    )
                    year_data["months"].append(
                        {
                            "month": month,
                            "entries": month_count,
                        }
                    )

                overview["years"].append(year_data)

            return overview

    def get_manuscript_analytics(self, session: Session) -> Dict[str, Any]:
        """
        Get manuscript-specific analytics.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with manuscript analytics
        """
        with DatabaseOperation(self.logger, "get_manuscript_analytics"):
            analytics = {
                "by_status": {},
                "by_theme": {},
                "by_arc": {},
                "chapter_count": 0,
            }

            # Count chapters by status
            for status in ChapterStatus:
                count = (
                    session.query(Chapter)
                    .filter(Chapter.status == status)
                    .count()
                )
                analytics["by_status"][status.value] = count

            # Total chapters
            analytics["chapter_count"] = session.query(Chapter).count()

            # Count entries by theme
            themes = session.query(Theme).all()
            for theme in themes:
                count = len(theme.entries)
                analytics["by_theme"][theme.name] = count

            # Count entries by arc
            arcs = session.query(Arc).all()
            for arc in arcs:
                count = len(arc.entries)
                analytics["by_arc"][arc.name] = count

            return analytics

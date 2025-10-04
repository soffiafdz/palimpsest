#!/usr/bin/env python3
"""
query_analytics.py
------------------
Complex queries and analytics for the database.
"""
from datetime import datetime, timedelta, date
from sqlite3 import DatabaseError
from typing import Dict, Any, List, Optional, Union

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from dev.core.logging_manager import PalimpsestLogger
from .decorators import handle_db_errors, log_database_operation

# Import models
from dev.database.models import (
    Entry,
    Person,
    City,
    Location,
    Event,
    Tag,
    Reference,
    ReferenceSource,
    MentionedDate,
    Poem,
    PoemVersion,
    Alias,
)
from dev.database.models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    Theme,
    Arc,
    ManuscriptStatus,
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

    @handle_db_errors
    @log_database_operation("get_database_stats")
    def get_database_stats(self, session: Session) -> Dict[str, Any]:
        """
        Get comprehensive database statistics.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with database statistics
        """
        stats = {}

        # Basic counts
        stats["entries"] = session.query(Entry).count()
        stats["people"] = session.query(Person).count()
        stats["cities"] = session.query(City).count()
        stats["locations"] = session.query(Location).count()
        stats["events"] = session.query(Event).count()
        stats["tags"] = session.query(Tag).count()
        stats["references"] = session.query(Reference).count()
        stats["reference_sources"] = session.query(ReferenceSource).count()
        stats["poems"] = session.query(Poem).count()
        stats["poem_versions"] = session.query(PoemVersion).count()
        stats["mentioned_dates"] = session.query(MentionedDate).count()
        stats["aliases"] = session.query(Alias).count()

        # Manuscript stats
        stats["manuscript_entries"] = session.query(ManuscriptEntry).count()
        stats["manuscript_people"] = session.query(ManuscriptPerson).count()
        stats["manuscript_events"] = session.query(ManuscriptEvent).count()
        stats["themes"] = session.query(Theme).count()
        stats["arcs"] = session.query(Arc).count()

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
            if self.logger:
                self.logger.log_error(e, {"operation": "get_migration_status"})

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

    @handle_db_errors
    @log_database_operation("get_entries_by_date_range")
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

    @handle_db_errors
    @log_database_operation("search_entries")
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
        search_filter = or_(
            Entry.notes.ilike(f"%{query}%"), Entry.epigraph.ilike(f"%{query}%")
        )

        query_obj = (
            session.query(Entry).filter(search_filter).order_by(Entry.date.desc())
        )

        if limit:
            query_obj = query_obj.limit(limit)

        return query_obj.all()

    @handle_db_errors
    @log_database_operation("get_entries_by_person")
    def get_entries_by_person(self, session: Session, person_name: str) -> List[Entry]:
        """Get all entries mentioning a specific person."""
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

    @handle_db_errors
    @log_database_operation("get_entries_by_city")
    def get_entries_by_city(self, session: Session, city_name: str) -> List[Entry]:
        """Get all entries at a specific city."""
        location = (
            session.query(City).filter(Location.name.ilike(f"%{city_name}%")).first()
        )

        return location.entries if location else []

    @handle_db_errors
    @log_database_operation("get_entries_by_location")
    def get_entries_by_location(
        self, session: Session, location_name: str
    ) -> List[Entry]:
        """Get all entries at a specific location."""
        location = (
            session.query(Location)
            .filter(Location.name.ilike(f"%{location_name}%"))
            .first()
        )

        return location.entries if location else []

    @handle_db_errors
    @log_database_operation("get_entries_by_tag")
    def get_entries_by_tag(self, session: Session, tag_name: str) -> List[Entry]:
        """Get all entries with a specific tag."""
        tag = session.query(Tag).filter(Tag.tag.ilike(f"%{tag_name}%")).first()

        return tag.entries if tag else []

    @handle_db_errors
    def get_manuscript_analytics(self, session: Session) -> Dict[str, Any]:
        """
        Get manuscript-specific analytics.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with manuscript analytics
        """
        analytics = {
            "by_status": {},
            "by_theme": {},
            "by_arc": {},
            "edited_count": 0,
            "unedited_count": 0,
        }

        # Count by status
        for status in ManuscriptStatus:
            count = (
                session.query(ManuscriptEntry)
                .filter(ManuscriptEntry.status == status)
                .count()
            )
            analytics["by_status"][status.value] = count

        # Count by theme
        themes = session.query(Theme).all()
        for theme in themes:
            count = len(theme.entries)
            analytics["by_theme"][theme.theme] = count

        # Count by arc
        arcs = session.query(Arc).all()
        for arc in arcs:
            count = len(arc.events)
            analytics["by_arc"][arc.arc] = count

        # Edited vs unedited
        analytics["edited_count"] = (
            session.query(ManuscriptEntry)
            .filter(ManuscriptEntry.edited.is_(True))
            .count()
        )

        analytics["unedited_count"] = (
            session.query(ManuscriptEntry)
            .filter(ManuscriptEntry.edited.is_(False))
            .count()
        )

        return analytics

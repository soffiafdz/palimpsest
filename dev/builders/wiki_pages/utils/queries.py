"""
Database Query Utilities
-------------------------

Centralized database queries for wiki page builders.

Functions:
    - get_all_entries: Get all entries sorted by date
    - get_entry_statistics: Get comprehensive entry statistics
    - get_people_statistics: Get people mention statistics
    - get_location_statistics: Get location statistics
    - get_tag_statistics: Get tag statistics
"""
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from collections import Counter

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from dev.database.models import (
    Entry as DBEntry,
    Person as DBPerson,
    Tag as DBTag,
    Location as DBLocation,
    City as DBCity,
    Event as DBEvent,
)
from dev.database.models_manuscript import Theme as DBTheme


def get_all_entries(session: Session) -> List[DBEntry]:
    """
    Get all entries sorted by date.

    Args:
        session: Database session

    Returns:
        List of all entries ordered by date
    """
    query = select(DBEntry).order_by(DBEntry.date)
    return session.execute(query).scalars().all()


def get_entry_statistics(session: Session) -> Dict:
    """
    Get comprehensive entry statistics.

    Args:
        session: Database session

    Returns:
        Dictionary with entry statistics including:
        - total_entries, total_words, avg_words
        - first_date, last_date, span_days
        - entries_by_year, entries_by_month, word_count_by_year
    """
    all_entries = get_all_entries(session)
    total_entries = len(all_entries)

    if total_entries == 0:
        return {
            "total_entries": 0,
            "total_words": 0,
            "avg_words": 0,
            "first_date": None,
            "last_date": None,
            "span_days": 0,
            "entries_by_year": {},
            "entries_by_month": {},
            "word_count_by_year": {},
        }

    total_words = sum(e.word_count for e in all_entries)
    avg_words = total_words // total_entries if total_entries > 0 else 0

    first_date = all_entries[0].date
    last_date = all_entries[-1].date
    span_days = (last_date - first_date).days

    # Count by year
    entries_by_year = Counter(e.date.year for e in all_entries)
    word_count_by_year = {}
    for year in entries_by_year.keys():
        word_count_by_year[year] = sum(
            e.word_count for e in all_entries if e.date.year == year
        )

    # Count by month
    entries_by_month = Counter(f"{e.date.year}-{e.date.month:02d}" for e in all_entries)

    return {
        "total_entries": total_entries,
        "total_words": total_words,
        "avg_words": avg_words,
        "first_date": first_date,
        "last_date": last_date,
        "span_days": span_days,
        "entries_by_year": dict(entries_by_year),
        "entries_by_month": dict(entries_by_month),
        "word_count_by_year": word_count_by_year,
        "all_entries": all_entries,
    }


def get_people_statistics(session: Session) -> Dict:
    """
    Get people mention statistics.

    Args:
        session: Database session

    Returns:
        Dictionary with people statistics
    """
    all_people = session.execute(select(DBPerson)).scalars().all()
    total_people = len(all_people)

    # Get top mentioned people
    people_with_counts = [(p, len(p.entries)) for p in all_people]
    people_with_counts.sort(key=lambda x: (-x[1], x[0].name))
    top_people = people_with_counts[:10]

    # Count by relation
    relation_counts = Counter()
    for person in all_people:
        if person.relation:
            relation_counts[person.relation] += 1

    return {
        "total_people": total_people,
        "all_people": all_people,
        "top_people": top_people,
        "relation_counts": relation_counts,
    }


def get_location_statistics(session: Session) -> Dict:
    """
    Get location and city statistics.

    Args:
        session: Database session

    Returns:
        Dictionary with location statistics
    """
    total_locations = session.execute(select(func.count(DBLocation.id))).scalar()
    total_cities = session.execute(select(func.count(DBCity.id))).scalar()

    all_cities = session.execute(select(DBCity)).scalars().all()
    cities_with_counts = [(c, len(c.entries)) for c in all_cities]
    cities_with_counts.sort(key=lambda x: (-x[1], x[0].name))
    top_cities = cities_with_counts[:10]

    return {
        "total_locations": total_locations,
        "total_cities": total_cities,
        "all_cities": all_cities,
        "top_cities": top_cities,
    }


def get_tag_statistics(session: Session) -> Dict:
    """
    Get tag statistics.

    Args:
        session: Database session

    Returns:
        Dictionary with tag statistics
    """
    all_tags = session.execute(select(DBTag)).scalars().all()
    total_tags = len(all_tags)

    tags_with_counts = [(t, len(t.entries)) for t in all_tags]
    tags_with_counts.sort(key=lambda x: (-x[1], x[0].name))
    top_tags = tags_with_counts[:20]

    return {
        "total_tags": total_tags,
        "all_tags": all_tags,
        "top_tags": top_tags,
    }


def get_event_count(session: Session) -> int:
    """Get total event count."""
    return session.execute(select(func.count(DBEvent.id))).scalar()


def get_theme_count(session: Session) -> int:
    """Get total theme count."""
    return session.execute(select(func.count(DBTheme.id))).scalar()


def get_top_entities(
    entities: List,
    count_attr: str = "entries",
    name_attr: str = "name",
    limit: int = 10,
) -> List[Tuple]:
    """
    Get top N entities by count.

    Args:
        entities: List of entity objects
        count_attr: Attribute name for counting (default: "entries")
        name_attr: Attribute name for sorting (default: "name")
        limit: Number of top entities to return

    Returns:
        List of (entity, count) tuples sorted by count descending
    """
    entities_with_counts = [
        (e, len(getattr(e, count_attr))) for e in entities
    ]
    entities_with_counts.sort(
        key=lambda x: (-x[1], getattr(x[0], name_attr))
    )
    return entities_with_counts[:limit]

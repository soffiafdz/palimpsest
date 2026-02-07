#!/usr/bin/env python3
"""
search.py
---------
Full-text search with advanced metadata filtering.

Combines SQLite FTS5 for text search with SQL filters for metadata.

Query Syntax Examples:
    "alice therapy"                    # Text search
    "alice AND therapy"                # Boolean AND
    "person:alice tag:reflection"      # With filters
    "therapy in:2024 words:100-500"    # Year and word count
    "alice city:montreal"                 # Complex filters

Usage:
    # Parse query
    query = SearchQueryParser.parse("alice therapy in:2024")

    # Execute search
    engine = SearchEngine(session)
    results = engine.search(query)

    # Results include entry objects, scores, snippets
    for result in results:
        print(result['entry'].date, result['score'])
"""
# --- Standard library imports ---
from dataclasses import dataclass, field
from datetime import date as Date
from typing import List, Optional, Dict, Any
from calendar import monthrange

# --- Third party imports ---
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload

# --- Local imports ---
from dev.database.models import Entry, Person, Tag, Event, City, Theme
from dev.search.search_index import SearchIndexManager


@dataclass
class SearchQuery:
    """Represents a parsed search query with text and filters."""

    # Full-text search
    text: Optional[str] = None

    # Entity filters
    people: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    cities: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)

    # Date filters
    date_from: Optional[Date] = None
    date_to: Optional[Date] = None
    year: Optional[int] = None
    month: Optional[int] = None

    # Numeric filters
    min_words: Optional[int] = None
    max_words: Optional[int] = None
    min_reading_time: Optional[float] = None
    max_reading_time: Optional[float] = None

    # Sorting
    sort_by: str = "relevance"  # relevance, date, word_count
    sort_order: str = "desc"

    # Pagination
    limit: int = 50
    offset: int = 0


class SearchQueryParser:
    """Parse search query strings into SearchQuery objects."""

    @staticmethod
    def parse(query_string: str) -> SearchQuery:
        """
        Parse search query string.

        Examples:
            "alice therapy" → text search
            "person:alice tag:reflection" → filters
            "alice in:2024 words:100-500" → mixed
            "therapy year:2024 month:11" → date filters
            "alice city:montreal" → complex

        Returns:
            SearchQuery object
        """
        query = SearchQuery()
        tokens = query_string.split()
        text_parts = []

        for token in tokens:
            if ':' not in token:
                # Regular text search token
                text_parts.append(token)
                continue

            # Parse filter
            key, value = token.split(':', 1)
            key = key.lower()

            # Person filter
            if key in ('person', 'people'):
                query.people.append(value)

            # Tag filter
            elif key == 'tag':
                query.tags.append(value)

            # Event filter
            elif key == 'event':
                query.events.append(value)

            # City filter
            elif key == 'city':
                query.cities.append(value)

            # Theme filter
            elif key == 'theme':
                query.themes.append(value)

            # Year filter
            elif key in ('in', 'year'):
                try:
                    query.year = int(value)
                except ValueError:
                    pass

            # Month filter
            elif key == 'month':
                try:
                    query.month = int(value)
                except ValueError:
                    pass

            # Date range filters
            elif key == 'from':
                try:
                    query.date_from = Date.fromisoformat(value)
                except ValueError:
                    pass

            elif key == 'to':
                try:
                    query.date_to = Date.fromisoformat(value)
                except ValueError:
                    pass

            # Word count filter
            elif key == 'words':
                if '-' in value:
                    min_w, max_w = value.split('-', 1)
                    try:
                        query.min_words = int(min_w) if min_w else None
                        query.max_words = int(max_w) if max_w else None
                    except ValueError:
                        pass
                else:
                    try:
                        query.min_words = int(value)
                    except ValueError:
                        pass

            # Reading time filter
            elif key == 'time':
                if '-' in value:
                    min_t, max_t = value.split('-', 1)
                    try:
                        query.min_reading_time = float(min_t) if min_t else None
                        query.max_reading_time = float(max_t) if max_t else None
                    except ValueError:
                        pass
                else:
                    try:
                        query.min_reading_time = float(value)
                    except ValueError:
                        pass

            # Sort filter
            elif key == 'sort':
                query.sort_by = value

            # Limit filter
            elif key == 'limit':
                try:
                    query.limit = int(value)
                except ValueError:
                    pass

        # Combine text parts
        if text_parts:
            query.text = ' '.join(text_parts)

        return query


class SearchEngine:
    """Execute searches against database with FTS and filters."""

    def __init__(self, session: Session):
        self.session = session

    def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """
        Execute search query and return results.

        Args:
            query: SearchQuery object

        Returns:
            List of result dicts with:
                - entry: Entry object
                - score: Relevance score (if text search)
                - snippet: Highlighted snippet (if text search)
        """
        # Start with FTS query if text search
        fts_results = None
        entry_ids = None

        if query.text:
            # Execute FTS search
            bind = self.session.bind
            if bind is None:
                raise ValueError("Database session has no bind (engine)")
            from sqlalchemy import Connection
            if isinstance(bind, Connection):
                engine = bind.engine
            else:
                engine = bind
            search_mgr = SearchIndexManager(engine)

            try:
                fts_results = search_mgr.search(
                    query.text,
                    limit=1000,  # Get large set, filter later
                    highlight=True
                )

                entry_ids = [r['entry_id'] for r in fts_results]

                if not entry_ids:
                    # No FTS matches
                    return []

            except Exception:
                # FTS index might not exist
                fts_results = None
                entry_ids = None

        # Build SQL query
        stmt = select(Entry).options(
            joinedload(Entry.people),
            joinedload(Entry.tags),
            joinedload(Entry.events),
            joinedload(Entry.cities),
        )

        # Apply FTS filter if applicable
        if entry_ids is not None:
            stmt = stmt.where(Entry.id.in_(entry_ids))

        # Apply metadata filters
        conditions = []

        # Date filters
        if query.date_from:
            conditions.append(Entry.date >= query.date_from)

        if query.date_to:
            conditions.append(Entry.date <= query.date_to)

        if query.year:
            conditions.append(
                and_(
                    Entry.date >= Date(query.year, 1, 1),
                    Entry.date <= Date(query.year, 12, 31)
                )
            )

        if query.month and query.year:
            _, last_day = monthrange(query.year, query.month)
            conditions.append(
                and_(
                    Entry.date >= Date(query.year, query.month, 1),
                    Entry.date <= Date(query.year, query.month, last_day)
                )
            )

        # Word count filters
        if query.min_words:
            conditions.append(Entry.word_count >= query.min_words)

        if query.max_words:
            conditions.append(Entry.word_count <= query.max_words)

        # Reading time filters
        if query.min_reading_time:
            conditions.append(Entry.reading_time >= query.min_reading_time)

        if query.max_reading_time:
            conditions.append(Entry.reading_time <= query.max_reading_time)

        # Apply basic conditions
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Relationship filters (require joins)
        if query.people:
            stmt = stmt.join(Entry.people)
            stmt = stmt.where(Person.name.in_(query.people))

        if query.tags:
            stmt = stmt.join(Entry.tags)
            stmt = stmt.where(Tag.name.in_(query.tags))

        if query.events:
            stmt = stmt.join(Entry.events)
            stmt = stmt.where(Event.name.in_(query.events))

        if query.cities:
            stmt = stmt.join(Entry.cities)
            stmt = stmt.where(City.name.in_(query.cities))

        if query.themes:
            # Themes are M2M with entries
            stmt = stmt.join(Entry.themes)
            stmt = stmt.where(Theme.name.in_(query.themes))

        # Execute query
        entries = self.session.execute(stmt).unique().scalars().all()

        # Combine with FTS results
        if fts_results:
            # Create score map
            score_map = {r['entry_id']: r for r in fts_results}

            results = []
            for entry in entries:
                fts_data = score_map.get(entry.id, {})
                results.append({
                    'entry': entry,
                    'score': abs(fts_data.get('rank', 0)),  # BM25 returns negative scores
                    'snippet': fts_data.get('snippet', ''),
                })

            # Sort by relevance
            if query.sort_by == 'relevance':
                results.sort(key=lambda x: x['score'], reverse=(query.sort_order == 'desc'))

        else:
            # No FTS, just metadata filters
            results = [
                {
                    'entry': entry,
                    'score': 0,
                    'snippet': '',
                }
                for entry in entries
            ]

        # Apply sorting (if not relevance)
        if query.sort_by == 'date':
            results.sort(
                key=lambda x: x['entry'].date,
                reverse=(query.sort_order == 'desc')
            )
        elif query.sort_by == 'word_count':
            results.sort(
                key=lambda x: x['entry'].word_count,
                reverse=(query.sort_order == 'desc')
            )

        # Apply pagination
        start = query.offset
        end = start + query.limit

        return results[start:end]

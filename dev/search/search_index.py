#!/usr/bin/env python3
"""
search_index.py
---------------
Manages full-text search index for journal entries using SQLite FTS5.

Features:
- FTS5 virtual table for fast full-text search
- Automatic triggers to keep index in sync
- Porter stemming for word variations
- Unicode support for international text
- Snippet generation with highlighting

Usage:
    # Initialize index (one-time setup)
    manager = SearchIndexManager(engine)
    manager.create_index()
    manager.setup_triggers()

    # Update index for specific entry
    manager.update_entry_body(entry_id, body_text)

    # Rebuild entire index
    manager.rebuild_index(session)
"""
# --- Standard library imports ---
from typing import Optional, List, Dict, Any
from pathlib import Path

# --- Third party imports ---
from sqlalchemy import text, Engine
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger


class SearchIndexManager:
    """Manages FTS5 full-text search index."""

    def __init__(self, engine: Engine, logger: Optional[PalimpsestLogger] = None):
        self.engine = engine
        self.logger = logger

    def create_index(self) -> None:
        """
        Create FTS5 virtual table for full-text search.

        The table indexes:
        - entry_id: Reference to entries.id (not indexed)
        - date: Entry date (not indexed)
        - body: Full entry text
        - summary: Entry summary

        Uses Porter stemming and Unicode tokenization.
        """
        with self.engine.connect() as conn:
            # Drop existing table if present
            conn.execute(text("DROP TABLE IF EXISTS entries_fts"))

            # Create FTS5 virtual table
            conn.execute(text("""
                CREATE VIRTUAL TABLE entries_fts USING fts5(
                    entry_id UNINDEXED,
                    date UNINDEXED,
                    body,
                    summary,
                    tokenize='porter unicode61'
                )
            """))

            conn.commit()

            safe_logger(self.logger).log_info("Created FTS5 search index")

    def populate_index(self, session: Session) -> int:
        """
        Populate FTS index from existing entries.

        Args:
            session: Database session

        Returns:
            Number of entries indexed
        """
        from dev.database.models import Entry

        # Get all entries
        entries = session.query(Entry).all()

        indexed_count = 0

        with self.engine.connect() as conn:
            for entry in entries:
                # Read body text from file
                body_text = ""
                if entry.file_path:
                    try:
                        file_path = Path(entry.file_path)
                        if file_path.exists():
                            # Read markdown content
                            content = file_path.read_text(encoding='utf-8')

                            # Extract body (skip YAML frontmatter)
                            if content.startswith('---'):
                                parts = content.split('---', 2)
                                if len(parts) >= 3:
                                    body_text = parts[2].strip()
                                else:
                                    body_text = content
                            else:
                                body_text = content
                    except Exception as e:
                        safe_logger(self.logger).log_warning(f"Could not read {entry.file_path}: {e}")

                # Insert into FTS index
                conn.execute(
                    text("""
                        INSERT INTO entries_fts (entry_id, date, body, summary)
                        VALUES (:entry_id, :date, :body, :summary)
                    """),
                    {
                        'entry_id': entry.id,
                        'date': entry.date.isoformat(),
                        'body': body_text,
                        'summary': entry.summary or '',
                    }
                )

                indexed_count += 1

            conn.commit()

        safe_logger(self.logger).log_info(f"Indexed {indexed_count} entries")

        return indexed_count

    def setup_triggers(self) -> None:
        """
        Set up database triggers to keep FTS index in sync.

        Triggers:
        - INSERT: Add new entry to index
        - UPDATE: Update entry in index
        - DELETE: Remove entry from index
        """
        with self.engine.connect() as conn:
            # Drop existing triggers
            conn.execute(text("DROP TRIGGER IF EXISTS entries_ai"))
            conn.execute(text("DROP TRIGGER IF EXISTS entries_au"))
            conn.execute(text("DROP TRIGGER IF EXISTS entries_ad"))

            # Trigger on INSERT
            conn.execute(text("""
                CREATE TRIGGER entries_ai AFTER INSERT ON entries BEGIN
                    INSERT INTO entries_fts(entry_id, date, body, summary)
                    VALUES (
                        new.id,
                        new.date,
                        '',  -- Body populated separately
                        COALESCE(new.summary, '')
                    );
                END
            """))

            # Trigger on UPDATE
            conn.execute(text("""
                CREATE TRIGGER entries_au AFTER UPDATE ON entries BEGIN
                    UPDATE entries_fts
                    SET
                        date = new.date,
                        summary = COALESCE(new.summary, '')
                    WHERE entry_id = new.id;
                END
            """))

            # Trigger on DELETE
            conn.execute(text("""
                CREATE TRIGGER entries_ad AFTER DELETE ON entries BEGIN
                    DELETE FROM entries_fts WHERE entry_id = old.id;
                END
            """))

            conn.commit()

            safe_logger(self.logger).log_info("Created FTS sync triggers")

    def update_entry_body(self, entry_id: int, body_text: str) -> None:
        """
        Update body text for specific entry in FTS index.

        Args:
            entry_id: Entry ID
            body_text: Full body text to index
        """
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE entries_fts
                    SET body = :body
                    WHERE entry_id = :entry_id
                """),
                {'entry_id': entry_id, 'body': body_text}
            )
            conn.commit()

    def rebuild_index(self, session: Session) -> int:
        """
        Rebuild entire search index from scratch.

        Args:
            session: Database session

        Returns:
            Number of entries indexed
        """
        safe_logger(self.logger).log_info("Rebuilding search index...")

        # Recreate table
        self.create_index()

        # Populate
        count = self.populate_index(session)

        # Setup triggers
        self.setup_triggers()

        safe_logger(self.logger).log_info(f"Index rebuild complete: {count} entries")

        return count

    def search(
        self,
        query: str,
        limit: int = 50,
        highlight: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Execute full-text search query.

        Args:
            query: Search query string (FTS5 syntax)
            limit: Maximum results
            highlight: Include highlighted snippets

        Returns:
            List of result dicts with entry_id, date, snippet, rank
        """
        with self.engine.connect() as conn:
            if highlight:
                # Query with snippet and highlighting
                sql = text("""
                    SELECT
                        entry_id,
                        date,
                        snippet(entries_fts, 2, '<mark>', '</mark>', '...', 30) as snippet,
                        bm25(entries_fts) as rank
                    FROM entries_fts
                    WHERE entries_fts MATCH :query
                    ORDER BY rank
                    LIMIT :limit
                """)
            else:
                # Query without snippet
                sql = text("""
                    SELECT
                        entry_id,
                        date,
                        bm25(entries_fts) as rank
                    FROM entries_fts
                    WHERE entries_fts MATCH :query
                    ORDER BY rank
                    LIMIT :limit
                """)

            result = conn.execute(sql, {'query': query, 'limit': limit})

            results = []
            for row in result:
                result_dict = {
                    'entry_id': row[0],
                    'date': row[1],
                    'rank': row[3] if highlight else row[2],
                }

                if highlight:
                    result_dict['snippet'] = row[2]

                results.append(result_dict)

            return results

    def index_exists(self) -> bool:
        """Check if FTS index exists."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='entries_fts'
            """))

            return result.fetchone() is not None

#!/usr/bin/env python3
"""
poem_manager.py
--------------------
Manages Poem and PoemVersion entities with version tracking and deduplication.

Poems represent poem titles that may have multiple versions/revisions across
different entries. Version deduplication uses MD5 hashing to avoid storing
duplicate content.

Key Features:
    - CRUD operations for poems and poem versions
    - Parent-child relationship (Poem → PoemVersions)
    - Hash-based version deduplication
    - Automatic hash generation and regeneration
    - Version timeline and comparison

Usage:
    poem_mgr = PoemManager(session, logger)

    # Create a poem with initial version
    version = poem_mgr.create_version({
        "title": "Autumn Reverie",
        "content": "Leaves fall softly...",
        "revision_date": date(2024, 1, 15),
        "entry": entry
    })

    # Add another version of the same poem
    version2 = poem_mgr.create_version({
        "title": "Autumn Reverie",
        "content": "Leaves fall gently...",  # Different content
        "revision_date": date(2024, 2, 1),
        "entry": entry2,
        "poem": version.poem  # Link to same poem
    })

    # Deduplication: identical content won't create duplicate
    version3 = poem_mgr.create_version({
        "title": "Autumn Reverie",
        "content": "Leaves fall softly...",  # Same as version
        "poem": version.poem
    })  # Returns existing version, not created

    # Query versions
    versions = poem_mgr.get_versions_for_poem(version.poem)
"""
from typing import Dict, List, Optional, Any
from datetime import date

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from dev.database.models import Poem, PoemVersion, Entry
from dev.database.relationship_manager import RelationshipManager
from dev.utils import md
from .base_manager import BaseManager


class PoemManager(BaseManager):
    """
    Manages Poem and PoemVersion table operations.

    This manager handles both entities since they have a tight parent-child
    relationship: every PoemVersion belongs to a Poem.
    """

    # =========================================================================
    # POEM OPERATIONS (Parent)
    # =========================================================================

    @handle_db_errors
    @log_database_operation("poem_exists")
    def poem_exists(self, title: str) -> bool:
        """
        Check if a poem with title exists.

        Args:
            title: The poem title to check

        Returns:
            True if poem exists, False otherwise

        Notes:
            - Poem titles are NOT unique, multiple poems can have same title
            - This checks if ANY poem with this title exists
        """
        normalized = DataValidator.normalize_string(title)
        if not normalized:
            return False

        return self.session.query(Poem).filter_by(title=normalized).first() is not None

    @handle_db_errors
    @log_database_operation("get_poem")
    def get_poem(
        self, title: str = None, poem_id: int = None
    ) -> Optional[Poem]:
        """
        Retrieve a poem by title or ID.

        Args:
            title: The poem title (returns first match if multiple exist)
            poem_id: The poem ID

        Returns:
            Poem object if found, None otherwise

        Notes:
            - If both provided, ID takes precedence
            - Title lookup returns first match (titles are not unique)
        """
        if poem_id is not None:
            return self.session.get(Poem, poem_id)

        if title is not None:
            normalized = DataValidator.normalize_string(title)
            if not normalized:
                return None
            return self.session.query(Poem).filter_by(title=normalized).first()

        return None

    @handle_db_errors
    @log_database_operation("get_all_poems")
    def get_all_poems(self) -> List[Poem]:
        """
        Retrieve all poems.

        Returns:
            List of all Poem objects, ordered by title
        """
        return self.session.query(Poem).order_by(Poem.title).all()

    @handle_db_errors
    @log_database_operation("create_poem")
    @validate_metadata(["title"])
    def create_poem(self, metadata: Dict[str, Any]) -> Poem:
        """
        Create a new poem (without versions).

        Args:
            metadata: Dictionary with required key:
                - title: Poem title (required, not unique)
                Optional keys:
                - versions: List of PoemVersion objects or IDs

        Returns:
            Created Poem object

        Raises:
            ValidationError: If title is missing or invalid

        Notes:
            - Poem titles are not unique, duplicates are allowed
            - Usually prefer create_version() which creates both poem and version
        """
        title = DataValidator.normalize_string(metadata.get("title"))
        if not title:
            raise ValidationError(f"Invalid poem title: {metadata.get('title')}")

        # Create poem
        poem = Poem(title=title)
        self.session.add(poem)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(f"Created poem: {title}", {"poem_id": poem.id})

        # Update relationships
        if "versions" in metadata:
            items = metadata["versions"]

            # Non-incremental mode: clear and add all
            poem.versions.clear()
            for item in items:
                resolved_item = self._resolve_object(item, PoemVersion)
                if resolved_item:
                    poem.versions.append(resolved_item)
            self.session.flush()

        return poem

    @handle_db_errors
    @log_database_operation("update_poem")
    def update_poem(self, poem: Poem, metadata: Dict[str, Any]) -> Poem:
        """
        Update an existing poem.

        Args:
            poem: Poem object to update
            metadata: Dictionary with optional keys:
                - title: Updated poem title
                - versions: List of versions (incremental by default)
                - remove_versions: Versions to remove

        Returns:
            Updated Poem object
        """
        # Ensure exists
        db_poem = self.session.get(Poem, poem.id)
        if db_poem is None:
            raise DatabaseError(f"Poem with id={poem.id} not found")

        # Attach to session
        poem = self.session.merge(db_poem)

        # Update title
        if "title" in metadata:
            title = DataValidator.normalize_string(metadata["title"])
            if title:
                poem.title = title

        # Update versions (one-to-many)
        if "versions" in metadata:
            items = metadata["versions"]
            remove_items = metadata.get("remove_versions", [])

            # Get existing IDs for comparison
            existing_ids = {version.id for version in poem.versions}

            # Incremental mode: add new items
            for item in items:
                resolved_item = self._resolve_object(item, PoemVersion)
                if resolved_item and resolved_item.id not in existing_ids:
                    poem.versions.append(resolved_item)

            # Remove specified items
            for item in remove_items:
                resolved_item = self._resolve_object(item, PoemVersion)
                if resolved_item and resolved_item.id in existing_ids:
                    poem.versions.remove(resolved_item)

        self.session.flush()

        return poem

    @handle_db_errors
    @log_database_operation("delete_poem")
    def delete_poem(self, poem: Poem) -> None:
        """
        Delete a poem.

        Args:
            poem: Poem object or ID to delete

        Notes:
            - This is a hard delete
            - All versions are cascade deleted
            - Use with caution if versions exist
        """
        if isinstance(poem, int):
            poem = self.session.get(Poem, poem)
            if not poem:
                raise DatabaseError(f"Poem not found with id: {poem}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting poem: {poem.title}",
                {"poem_id": poem.id, "version_count": poem.version_count},
            )

        self.session.delete(poem)
        self.session.flush()

    @handle_db_errors
    @log_database_operation("get_or_create_poem")
    def get_or_create_poem(self, title: str) -> Poem:
        """
        Get an existing poem or create it if needed.

        Args:
            title: The poem title

        Returns:
            Poem object (existing or newly created)

        Notes:
            - Returns first poem with matching title if multiple exist
            - Consider using create_version() instead for full poem+version creation
        """
        normalized = DataValidator.normalize_string(title)
        if not normalized:
            raise ValidationError("Poem title cannot be empty")

        # Try to get existing
        existing = self.get_poem(title=normalized)
        if existing:
            return existing

        # Create new
        return self._get_or_create(Poem, {"title": normalized})

    # =========================================================================
    # POEM VERSION OPERATIONS (Child)
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_version")
    def get_version(self, version_id: int) -> Optional[PoemVersion]:
        """
        Retrieve a poem version by ID.

        Args:
            version_id: The version ID

        Returns:
            PoemVersion object if found, None otherwise
        """
        return self.session.get(PoemVersion, version_id)

    @handle_db_errors
    @log_database_operation("get_all_versions")
    def get_all_versions(self) -> List[PoemVersion]:
        """
        Retrieve all poem versions.

        Returns:
            List of all PoemVersion objects
        """
        return self.session.query(PoemVersion).all()

    @handle_db_errors
    @log_database_operation("create_version")
    @validate_metadata(["title", "content"])
    def create_version(self, metadata: Dict[str, Any]) -> PoemVersion:
        """
        Create a new poem version (and parent poem if needed).

        This is the recommended way to create poems with content.

        Args:
            metadata: Dictionary with required keys:
                - title: Poem title (required)
                - content: Poem content (required)
                Optional keys:
                - revision_date: Date of this version (defaults to today)
                - notes: Notes about this version
                - entry: Entry object or ID to link to
                - poem: Poem object or ID (creates new if not provided)
                - version_hash: MD5 hash (auto-generated if not provided)

        Returns:
            Created PoemVersion object, or existing version if duplicate detected

        Raises:
            ValidationError: If title/content missing or invalid

        Notes:
            - Automatically generates version_hash from content
            - Deduplication: if same poem+hash exists, returns existing version
        """
        # Validate required fields
        title = DataValidator.normalize_string(metadata.get("title"))
        if not title:
            raise ValidationError(f"Invalid poem title: {metadata.get('title')}")

        content = DataValidator.normalize_string(metadata.get("content"))
        if not content:
            raise ValidationError("Poem content cannot be empty")

        # Resolve or create parent poem
        poem_spec = metadata.get("poem")
        if poem_spec is None:
            # Create new poem
            poem = self.get_or_create_poem(title)
        elif isinstance(poem_spec, Poem):
            poem = poem_spec
        elif isinstance(poem_spec, int):
            poem = self.get_poem(poem_id=poem_spec)
            if not poem:
                raise ValidationError(f"Poem not found with id: {poem_spec}")
        else:
            raise ValidationError(f"Invalid poem specification: {poem_spec}")

        # Generate version hash
        version_hash = metadata.get("version_hash")
        if not version_hash:
            version_hash = md.get_text_hash(content)

        # Check for duplicate version (deduplication)
        existing_version = (
            self.session.query(PoemVersion)
            .filter_by(poem_id=poem.id, version_hash=version_hash)
            .first()
        )

        if existing_version:
            if self.logger:
                self.logger.log_debug(
                    f"Duplicate poem version found, returning existing",
                    {
                        "poem": poem.title,
                        "version_id": existing_version.id,
                        "version_hash": version_hash,
                    },
                )
            return existing_version

        # Resolve revision date
        revision_date = metadata.get("revision_date")
        if revision_date:
            if isinstance(revision_date, str):
                try:
                    revision_date = date.fromisoformat(revision_date)
                except ValueError as e:
                    raise ValidationError(f"Invalid revision date: {revision_date}") from e
        else:
            # Try to get from entry, otherwise use today
            entry_spec = metadata.get("entry")
            if isinstance(entry_spec, Entry):
                revision_date = entry_spec.date
            elif isinstance(entry_spec, int):
                entry = self.session.get(Entry, entry_spec)
                revision_date = entry.date if entry else date.today()
            else:
                revision_date = date.today()

        # Resolve entry (optional)
        entry = None
        entry_spec = metadata.get("entry")
        if entry_spec is not None:
            if isinstance(entry_spec, Entry):
                entry = entry_spec
            elif isinstance(entry_spec, int):
                entry = self.session.get(Entry, entry_spec)
                if not entry:
                    if self.logger:
                        self.logger.log_warning(
                            f"Entry not found with id: {entry_spec}",
                            {"poem": poem.title},
                        )

        # Create version
        version = PoemVersion(
            poem=poem,
            content=content,
            revision_date=revision_date,
            version_hash=version_hash,
            notes=DataValidator.normalize_string(metadata.get("notes")),
            entry=entry,
        )
        self.session.add(version)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created poem version: {poem.title}",
                {
                    "version_id": version.id,
                    "poem_id": poem.id,
                    "revision_date": revision_date.isoformat(),
                },
            )

        return version

    @handle_db_errors
    @log_database_operation("update_version")
    def update_version(
        self, version: PoemVersion, metadata: Dict[str, Any]
    ) -> PoemVersion:
        """
        Update an existing poem version.

        Args:
            version: PoemVersion object to update
            metadata: Dictionary with optional keys:
                - content: Updated content (auto-regenerates version_hash)
                - revision_date: Updated revision date
                - notes: Updated notes
                - poem: Updated parent Poem object or ID
                - entry: Updated Entry object or ID

        Returns:
            Updated PoemVersion object

        Notes:
            - Automatically regenerates version_hash if content changes
        """
        # Ensure exists
        db_version = self.session.get(PoemVersion, version.id)
        if db_version is None:
            raise DatabaseError(f"PoemVersion with id={version.id} not found")

        # Attach to session
        version = self.session.merge(db_version)

        # Update content (and auto-regenerate hash)
        if "content" in metadata:
            content = DataValidator.normalize_string(metadata["content"])
            if content:
                version.content = content
                # Regenerate hash
                version.version_hash = md.get_text_hash(content)

        # Update revision date
        if "revision_date" in metadata:
            rev_date = metadata["revision_date"]
            if isinstance(rev_date, str):
                try:
                    rev_date = date.fromisoformat(rev_date)
                except ValueError:
                    pass
            if isinstance(rev_date, date):
                version.revision_date = rev_date

        # Update notes
        if "notes" in metadata:
            version.notes = DataValidator.normalize_string(metadata["notes"])

        # Update poem
        if "poem" in metadata:
            poem_spec = metadata["poem"]
            if isinstance(poem_spec, Poem):
                version.poem = poem_spec
            elif isinstance(poem_spec, int):
                poem = self.get_poem(poem_id=poem_spec)
                if poem:
                    version.poem = poem

        # Update entry
        if "entry" in metadata:
            entry_spec = metadata["entry"]
            if entry_spec is None:
                version.entry = None
            elif isinstance(entry_spec, Entry):
                version.entry = entry_spec
            elif isinstance(entry_spec, int):
                entry = self.session.get(Entry, entry_spec)
                if entry:
                    version.entry = entry

        self.session.flush()

        return version

    @handle_db_errors
    @log_database_operation("delete_version")
    def delete_version(self, version: PoemVersion) -> None:
        """
        Delete a poem version.

        Args:
            version: PoemVersion object or ID to delete

        Notes:
            - This is a hard delete
            - Does not affect the parent Poem
        """
        if isinstance(version, int):
            version = self.session.get(PoemVersion, version)
            if not version:
                raise DatabaseError(f"PoemVersion not found with id: {version}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting poem version",
                {"version_id": version.id, "poem": version.poem.title},
            )

        self.session.delete(version)
        self.session.flush()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_versions_for_poem")
    def get_versions_for_poem(self, poem: Poem) -> List[PoemVersion]:
        """
        Get all versions of a poem, ordered chronologically.

        Args:
            poem: Poem object

        Returns:
            List of PoemVersion objects, ordered by revision_date
        """
        return sorted(poem.versions, key=lambda v: v.revision_date)

    @handle_db_errors
    @log_database_operation("get_versions_for_entry")
    def get_versions_for_entry(self, entry: Entry) -> List[PoemVersion]:
        """
        Get all poem versions linked to an entry.

        Args:
            entry: Entry object

        Returns:
            List of PoemVersion objects
        """
        return entry.poems

    @handle_db_errors
    @log_database_operation("get_latest_version")
    def get_latest_version(self, poem: Poem) -> Optional[PoemVersion]:
        """
        Get the most recent version of a poem.

        Args:
            poem: Poem object

        Returns:
            Latest PoemVersion object by revision_date, or None if no versions
        """
        return poem.latest_version

    @handle_db_errors
    @log_database_operation("get_poems_by_title")
    def get_poems_by_title(self, title: str) -> List[Poem]:
        """
        Get all poems with a specific title.

        Args:
            title: Poem title to search for

        Returns:
            List of Poem objects with matching title

        Notes:
            - Poem titles are not unique, so this may return multiple poems
        """
        normalized = DataValidator.normalize_string(title)
        if not normalized:
            return []

        return self.session.query(Poem).filter_by(title=normalized).all()

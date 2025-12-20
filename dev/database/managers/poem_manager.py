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
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger
from dev.core.validators import DataValidator
from dev.database.decorators import handle_db_errors, log_database_operation
from dev.database.models import Entry, Poem, PoemVersion
from dev.utils import md

from .entity_manager import EntityManager, EntityManagerConfig

# Configuration for Poem entity
POEM_CONFIG = EntityManagerConfig(
    model_class=Poem,
    name_field="title",
    display_name="poem",
    supports_soft_delete=False,
    order_by="title",
    scalar_fields=[
        ("title", DataValidator.normalize_string),
    ],
    relationships=[],
)


class PoemManager(EntityManager):
    """
    Manages Poem and PoemVersion table operations.

    Inherits EntityManager for Poem CRUD and adds
    PoemVersion-specific operations for the child entity.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the poem manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger, POEM_CONFIG)

    # =========================================================================
    # POEM OPERATIONS (via EntityManager)
    # =========================================================================

    # Inherited from EntityManager:
    # - exists(name, entity_id) -> bool
    # - get(name, entity_id) -> Optional[Poem]
    # - get_all() -> List[Poem]
    # - get_or_create(name, extra_metadata) -> Poem
    # - create(metadata) -> Poem
    # - update(entity, metadata) -> Poem
    # - delete(entity) -> None

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
        return self.exists(name=title)

    @handle_db_errors
    @log_database_operation("get_poem")
    def get_poem(
        self, title: Optional[str] = None, poem_id: Optional[int] = None
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
        return self.get(name=title, entity_id=poem_id)

    @handle_db_errors
    @log_database_operation("get_all_poems")
    def get_all_poems(self) -> List[Poem]:
        """
        Retrieve all poems.

        Returns:
            List of all Poem objects, ordered by title
        """
        return self.get_all()

    @handle_db_errors
    @log_database_operation("create_poem")
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
        # Poems allow duplicate titles, so we override to skip duplicate check
        title = DataValidator.normalize_string(metadata.get("title"))
        if not title:
            raise ValidationError(f"Invalid poem title: {metadata.get('title')}")

        # Create poem directly (no duplicate check)
        poem = Poem(title=title)
        self.session.add(poem)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(f"Created poem: {title}", {"poem_id": poem.id})

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
        return self.update(poem, metadata)

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
        self.delete(poem)

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
        return self.get_or_create(title)

    # =========================================================================
    # POEM VERSION OPERATIONS (Child entity)
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
        return self._get_by_id(PoemVersion, version_id)

    @handle_db_errors
    @log_database_operation("get_all_versions")
    def get_all_versions(self) -> List[PoemVersion]:
        """
        Retrieve all poem versions.

        Returns:
            List of all PoemVersion objects
        """
        return self._get_all(PoemVersion)

    @handle_db_errors
    @log_database_operation("create_version")
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
                    "Duplicate poem version found, returning existing",
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
                    raise ValidationError(
                        f"Invalid revision date: {revision_date}"
                    ) from e
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
                if not entry and self.logger:
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
        """
        db_version = self.session.get(PoemVersion, version.id)
        if db_version is None:
            raise DatabaseError(f"PoemVersion with id={version.id} not found")

        version = self.session.merge(db_version)

        # Update content (special: auto-regenerate hash)
        if "content" in metadata:
            content = DataValidator.normalize_string(metadata["content"])
            if content:
                version.content = content
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
        self._update_scalar_fields(
            version,
            metadata,
            [("notes", DataValidator.normalize_string, True)],
        )

        # Update poem
        if "poem" in metadata:
            poem = self._resolve_parent(
                metadata["poem"],
                Poem,
                lambda **kw: self.get_poem(poem_id=kw.get("id")),
                None,
                "id",
            )
            if poem:
                version.poem = poem

        # Update entry (allows None to clear)
        if "entry" in metadata:
            if metadata["entry"] is None:
                version.entry = None
            else:
                entry = self._resolve_parent(
                    metadata["entry"],
                    Entry,
                    lambda **kw: self.session.get(Entry, kw.get("id")),
                    None,
                    "id",
                )
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
        """
        if isinstance(version, int):
            version = self.session.get(PoemVersion, version)  # type: ignore[assignment]
            if not version:
                raise DatabaseError(f"PoemVersion not found with id: {version}")

        if self.logger:
            self.logger.log_debug(
                "Deleting poem version",
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
        """Get all versions of a poem, ordered chronologically."""
        return sorted(
            poem.versions, key=lambda v: v.revision_date or date.min
        )  # type: ignore[arg-type]

    @handle_db_errors
    @log_database_operation("get_versions_for_entry")
    def get_versions_for_entry(self, entry: Entry) -> List[PoemVersion]:
        """Get all poem versions linked to an entry."""
        return entry.poems

    @handle_db_errors
    @log_database_operation("get_latest_version")
    def get_latest_version(self, poem: Poem) -> Optional[PoemVersion]:
        """Get the most recent version of a poem."""
        return poem.latest_version

    @handle_db_errors
    @log_database_operation("get_poems_by_title")
    def get_poems_by_title(self, title: str) -> List[Poem]:
        """Get all poems with a specific title."""
        normalized = DataValidator.normalize_string(title)
        if not normalized:
            return []
        return self.session.query(Poem).filter_by(title=normalized).all()

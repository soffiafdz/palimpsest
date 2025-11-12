#!/usr/bin/env python3
"""
tag_manager.py
--------------------
Manages Tag entities and their relationships with entries.

Tag is the simplest entity in the system - just a string value with
a many-to-many relationship to entries. This manager serves as a proof
of concept for the modular manager architecture.

Key Features:
    - CRUD operations for tags
    - Link/unlink tags to/from entries
    - Get usage statistics
    - Automatic tag normalization
    - Get-or-create semantics for tag lookup

Usage:
    tag_mgr = TagManager(session, logger)

    # Create or get a tag
    tag = tag_mgr.get_or_create("python")

    # Link tag to entry
    tag_mgr.link_to_entry(entry, "python")

    # Update entry tags (incremental or replacement)
    tag_mgr.update_entry_tags(entry, ["python", "coding"], incremental=True)

    # Get all tags
    all_tags = tag_mgr.get_all()

    # Get usage statistics
    popular_tags = tag_mgr.get_by_usage(min_count=5)
"""
from typing import Dict, List, Optional, Any

from dev.core.validators import DataValidator
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from dev.database.models import Tag, Entry
from .base_manager import BaseManager


class TagManager(BaseManager):
    """
    Manages Tag table operations and relationships.

    Tags are simple keyword labels for categorizing entries. Each tag
    is a unique string that can be associated with multiple entries.
    """

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("tag_exists")
    def exists(self, tag_name: str) -> bool:
        """
        Check if a tag exists without raising exceptions.

        Args:
            tag_name: The tag text to check

        Returns:
            True if tag exists, False otherwise
        """
        normalized = DataValidator.normalize_string(tag_name)
        if not normalized:
            return False

        return self.session.query(Tag).filter_by(tag=normalized).first() is not None

    @handle_db_errors
    @log_database_operation("get_tag")
    def get(self, tag_name: str) -> Optional[Tag]:
        """
        Retrieve a tag by name.

        Args:
            tag_name: The tag text to retrieve

        Returns:
            Tag object if found, None otherwise
        """
        normalized = DataValidator.normalize_string(tag_name)
        if not normalized:
            return None

        return self.session.query(Tag).filter_by(tag=normalized).first()

    @handle_db_errors
    @log_database_operation("get_tag_by_id")
    def get_by_id(self, tag_id: int) -> Optional[Tag]:
        """
        Retrieve a tag by ID.

        Args:
            tag_id: The tag ID

        Returns:
            Tag object if found, None otherwise
        """
        return self.session.get(Tag, tag_id)

    @handle_db_errors
    @log_database_operation("get_all_tags")
    def get_all(self, order_by: str = "tag") -> List[Tag]:
        """
        Retrieve all tags.

        Args:
            order_by: Field to order by ("tag", "usage_count")
                Note: "usage_count" is a computed property, so ordering
                will be done in Python, not SQL

        Returns:
            List of all Tag objects
        """
        tags = self.session.query(Tag).order_by(Tag.tag).all()

        if order_by == "usage_count":
            # Sort by usage count (computed property)
            tags = sorted(tags, key=lambda t: t.usage_count, reverse=True)

        return tags

    @handle_db_errors
    @log_database_operation("create_tag")
    @validate_metadata(["tag"])
    def create(self, metadata: Dict[str, Any]) -> Tag:
        """
        Create a new tag.

        Args:
            metadata: Dictionary with required key:
                - tag: The tag text

        Returns:
            Created Tag object

        Raises:
            ValidationError: If tag is missing or empty
            DatabaseError: If tag already exists

        Notes:
            - Tag text is automatically normalized (stripped, lowercased)
            - Usually prefer get_or_create() to avoid duplicate errors
        """
        tag_text = DataValidator.normalize_string(metadata["tag"])
        if not tag_text:
            from dev.core.exceptions import ValidationError

            raise ValidationError("Tag cannot be empty")

        # Check for existing
        existing = self.get(tag_text)
        if existing:
            from dev.core.exceptions import DatabaseError

            raise DatabaseError(f"Tag already exists: {tag_text}")

        tag = Tag(tag=tag_text)
        self.session.add(tag)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(f"Created tag: {tag_text}", {"tag_id": tag.id})

        return tag

    @handle_db_errors
    @log_database_operation("get_or_create_tag")
    def get_or_create(self, tag_name: str) -> Tag:
        """
        Get an existing tag or create it if it doesn't exist.

        This is the recommended way to work with tags, as it handles
        both lookup and creation seamlessly.

        Args:
            tag_name: The tag text

        Returns:
            Tag object (existing or newly created)

        Raises:
            ValidationError: If tag_name is empty after normalization
        """
        normalized = DataValidator.normalize_string(tag_name)
        if not normalized:
            from dev.core.exceptions import ValidationError

            raise ValidationError("Tag cannot be empty")

        # Use base class helper which handles race conditions
        return self._get_or_create(Tag, {"tag": normalized})

    @handle_db_errors
    @log_database_operation("delete_tag")
    def delete(self, tag: Tag) -> None:
        """
        Delete a tag.

        Args:
            tag: Tag object or ID to delete

        Notes:
            - Cascade delete removes all entry-tag associations
            - This is a hard delete (tags don't support soft delete)
        """
        if isinstance(tag, int):
            tag = self.get_by_id(tag)
            if not tag:
                from dev.core.exceptions import DatabaseError

                raise DatabaseError(f"Tag not found with id: {tag}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting tag: {tag.tag}",
                {"tag_id": tag.id, "usage_count": tag.usage_count},
            )

        self.session.delete(tag)
        self.session.flush()

    # -------------------------------------------------------------------------
    # Relationship Management
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("link_tag_to_entry")
    def link_to_entry(self, entry: Entry, tag_name: str) -> Tag:
        """
        Link a tag to an entry (get-or-create the tag first).

        Args:
            entry: Entry object to link to
            tag_name: Tag text (will be normalized and created if needed)

        Returns:
            The Tag object that was linked

        Raises:
            ValueError: If entry is not persisted
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking tags")

        tag = self.get_or_create(tag_name)

        if tag not in entry.tags:
            entry.tags.append(tag)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Linked tag to entry",
                    {"tag": tag.tag, "entry_date": entry.date},
                )

        return tag

    @handle_db_errors
    @log_database_operation("unlink_tag_from_entry")
    def unlink_from_entry(self, entry: Entry, tag_name: str) -> bool:
        """
        Unlink a tag from an entry.

        Args:
            entry: Entry object to unlink from
            tag_name: Tag text to unlink

        Returns:
            True if tag was unlinked, False if it wasn't linked

        Raises:
            ValueError: If entry is not persisted
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before unlinking tags")

        tag = self.get(tag_name)
        if not tag or tag not in entry.tags:
            return False

        entry.tags.remove(tag)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Unlinked tag from entry",
                {"tag": tag.tag, "entry_date": entry.date},
            )

        return True

    @handle_db_errors
    @log_database_operation("update_entry_tags")
    def update_entry_tags(
        self,
        entry: Entry,
        tags: List[str],
        incremental: bool = True,
    ) -> None:
        """
        Update all tags for an entry.

        Args:
            entry: Entry object whose tags are to be updated
            tags: List of tag names (strings)
            incremental: Whether to add incrementally (True) or replace all (False)

        Behavior:
            - Incremental mode: Adds new tags, keeps existing ones
            - Replacement mode: Clears all tags, then adds specified ones
            - All tag names are normalized before processing
            - Empty/whitespace-only tag names are skipped

        Raises:
            ValueError: If entry is not persisted
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before updating tags")

        # Normalize incoming tags
        norm_tags = {
            DataValidator.normalize_string(t) for t in tags if t
        }  # Filter empty
        norm_tags.discard(None)  # Remove None from normalization failures

        # Replacement mode: clear all existing
        if not incremental:
            entry.tags.clear()
            self.session.flush()

        # Get existing tags
        existing_tags = {tag.tag for tag in entry.tags}

        # Add new tags
        new_tags = norm_tags - existing_tags
        for tag_name in new_tags:
            tag_obj = self.get_or_create(tag_name)
            entry.tags.append(tag_obj)

        if new_tags:
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Updated entry tags",
                    {
                        "entry_date": entry.date,
                        "added_count": len(new_tags),
                        "total_count": len(entry.tags),
                        "incremental": incremental,
                    },
                )

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("get_tags_by_usage")
    def get_by_usage(
        self, min_count: int = 1, max_count: Optional[int] = None
    ) -> List[Tag]:
        """
        Get tags filtered by usage count.

        Args:
            min_count: Minimum number of entries using the tag
            max_count: Maximum number of entries using the tag (optional)

        Returns:
            List of Tag objects sorted by usage count (descending)

        Notes:
            - This uses the computed usage_count property
            - Filtering happens in Python after loading all tags
        """
        all_tags = self.get_all()

        # Filter by usage count
        filtered = [
            tag
            for tag in all_tags
            if tag.usage_count >= min_count
            and (max_count is None or tag.usage_count <= max_count)
        ]

        # Sort by usage count descending
        return sorted(filtered, key=lambda t: t.usage_count, reverse=True)

    @handle_db_errors
    @log_database_operation("get_unused_tags")
    def get_unused(self) -> List[Tag]:
        """
        Get all tags that are not linked to any entries.

        Returns:
            List of unused Tag objects

        Notes:
            - Useful for cleanup operations
            - Tags are automatically created on first use
        """
        return self.get_by_usage(min_count=0, max_count=0)

    @handle_db_errors
    @log_database_operation("get_entry_tags")
    def get_for_entry(self, entry: Entry) -> List[Tag]:
        """
        Get all tags for a specific entry.

        Args:
            entry: Entry object

        Returns:
            List of Tag objects associated with the entry

        Notes:
            - This is just a convenience wrapper around entry.tags
            - Results are sorted alphabetically by tag name
        """
        return sorted(entry.tags, key=lambda t: t.tag)

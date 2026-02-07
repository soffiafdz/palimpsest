#!/usr/bin/env python3
"""
chapter_manager.py
------------------
Manages Chapter, Part, ManuscriptScene, ManuscriptSource, and ManuscriptReference entities.

Chapters are the primary manuscript units. Each chapter has a type (prose, vignette, poem),
a status (draft, revised, final), optional part assignment, and relationships to poems,
characters, and arcs. ManuscriptScenes are narrative units within chapters, sourced from
journal material. ManuscriptReferences track intertextual references per chapter.

Key Features:
    - CRUD for Chapter with type/status validation
    - Part management (assign/clear)
    - M2M management: poems, characters, arcs
    - ManuscriptScene CRUD within chapters
    - ManuscriptSource linking (journal scene/entry/thread/external)
    - ManuscriptReference CRUD within chapters
    - Part CRUD (lightweight, no config)

Usage:
    mgr = ChapterManager(session, logger)

    # Create chapter
    ch = mgr.create({"title": "The Gray Fence", "type": "prose"})

    # Assign to part
    mgr.assign_part(ch, part_id=1)

    # Add manuscript scene
    scene = mgr.create_manuscript_scene(ch, {
        "name": "Morning at the Fence",
        "origin": "journaled",
    })

    # Link source material
    mgr.add_scene_source(scene, {
        "source_type": "scene",
        "scene_id": 42,
    })
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Any, Dict, List, Optional

# --- Third party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from dev.database.models import (
    Arc,
    Chapter,
    Character,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    Part,
    ReferenceSource,
)
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ReferenceMode,
    SceneOrigin,
    SceneStatus,
    SourceType,
)

from .entity_manager import EntityManager, EntityManagerConfig


# Configuration for Chapter entity
CHAPTER_CONFIG = EntityManagerConfig(
    model_class=Chapter,
    name_field="title",
    display_name="chapter",
    supports_soft_delete=False,
    order_by="number",
    scalar_fields=[
        ("title", DataValidator.normalize_string),
        ("number", lambda x: x, True),
        ("content", lambda x: x, True),
        ("draft_path", lambda x: x, True),
    ],
    relationships=[
        ("poems", "poems", None),
        ("characters", "characters", Character),
        ("arcs", "arcs", Arc),
    ],
)


class ChapterManager(EntityManager):
    """
    Manages Chapter and related manuscript entities.

    Inherits EntityManager for Chapter CRUD and adds operations for
    ManuscriptScene, ManuscriptSource, ManuscriptReference, and Part.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the chapter manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger, CHAPTER_CONFIG)

    # =========================================================================
    # Chapter Hooks
    # =========================================================================

    def _validate_create(self, metadata: Dict[str, Any]) -> None:
        """
        Validate chapter creation metadata.

        Args:
            metadata: Must include 'title'

        Raises:
            ValidationError: If title is missing
        """
        DataValidator.validate_required_fields(metadata, ["title"])

    def _create_entity(self, metadata: Dict[str, Any], name: str) -> Chapter:
        """
        Create a Chapter with type and status enum resolution.

        Args:
            metadata: Chapter creation data
            name: Normalized title

        Returns:
            New Chapter instance
        """
        chapter_type = self._resolve_enum(
            metadata.get("type"), ChapterType, ChapterType.PROSE
        )
        chapter_status = self._resolve_enum(
            metadata.get("status"), ChapterStatus, ChapterStatus.DRAFT
        )

        return Chapter(
            title=name,
            number=metadata.get("number"),
            type=chapter_type,
            status=chapter_status,
            content=metadata.get("content"),
            draft_path=metadata.get("draft_path"),
        )

    def _post_create(self, entity: Any, metadata: Dict[str, Any]) -> None:
        """
        Handle post-creation relationships for chapter.

        Args:
            entity: Created chapter
            metadata: Creation metadata with optional relationship IDs
        """
        # Link characters by ID
        character_ids = metadata.get("character_ids", [])
        for cid in character_ids:
            character = self._get_by_id(Character, cid)
            if character:
                entity.characters.append(character)

        # Link arcs by ID
        arc_ids = metadata.get("arc_ids", [])
        for aid in arc_ids:
            arc = self._get_by_id(Arc, aid)
            if arc:
                entity.arcs.append(arc)

        if character_ids or arc_ids:
            self.session.flush()

    # =========================================================================
    # Chapter Operations
    # =========================================================================

    def update_status(self, chapter: Chapter, status: str) -> Chapter:
        """
        Update chapter status.

        Args:
            chapter: Chapter to update
            status: New status string (draft, revised, final)

        Returns:
            Updated chapter

        Raises:
            ValidationError: If status is invalid
        """
        with DatabaseOperation(self.logger, "update_chapter_status"):
            new_status = self._resolve_enum(status, ChapterStatus, None)
            if new_status is None:
                raise ValidationError(f"Invalid chapter status: {status}")
            chapter.status = new_status
            self.session.flush()
            return chapter

    def assign_part(self, chapter: Chapter, part_id: int) -> Chapter:
        """
        Assign chapter to a part.

        Args:
            chapter: Chapter to assign
            part_id: Part ID to assign to

        Returns:
            Updated chapter

        Raises:
            DatabaseError: If part not found
        """
        with DatabaseOperation(self.logger, "assign_chapter_part"):
            part = self._get_by_id(Part, part_id)
            if not part:
                raise DatabaseError(f"Part with id={part_id} not found")
            chapter.part_id = part_id
            self.session.flush()
            return chapter

    def clear_part(self, chapter: Chapter) -> Chapter:
        """
        Remove chapter from its part.

        Args:
            chapter: Chapter to unassign

        Returns:
            Updated chapter
        """
        with DatabaseOperation(self.logger, "clear_chapter_part"):
            chapter.part_id = None
            self.session.flush()
            return chapter

    def link_character(self, chapter: Chapter, character_id: int) -> None:
        """
        Link a character to a chapter.

        Args:
            chapter: Target chapter
            character_id: Character to link

        Raises:
            DatabaseError: If character not found
        """
        with DatabaseOperation(self.logger, "link_chapter_character"):
            character = self._get_by_id(Character, character_id)
            if not character:
                raise DatabaseError(f"Character with id={character_id} not found")
            if character not in chapter.characters:
                chapter.characters.append(character)
                self.session.flush()

    def unlink_character(self, chapter: Chapter, character_id: int) -> None:
        """
        Unlink a character from a chapter.

        Args:
            chapter: Target chapter
            character_id: Character to unlink
        """
        with DatabaseOperation(self.logger, "unlink_chapter_character"):
            character = self._get_by_id(Character, character_id)
            if character and character in chapter.characters:
                chapter.characters.remove(character)
                self.session.flush()

    def link_arc(self, chapter: Chapter, arc_id: int) -> None:
        """
        Link an arc to a chapter.

        Args:
            chapter: Target chapter
            arc_id: Arc to link

        Raises:
            DatabaseError: If arc not found
        """
        with DatabaseOperation(self.logger, "link_chapter_arc"):
            arc = self._get_by_id(Arc, arc_id)
            if not arc:
                raise DatabaseError(f"Arc with id={arc_id} not found")
            if arc not in chapter.arcs:
                chapter.arcs.append(arc)
                self.session.flush()

    def unlink_arc(self, chapter: Chapter, arc_id: int) -> None:
        """
        Unlink an arc from a chapter.

        Args:
            chapter: Target chapter
            arc_id: Arc to unlink
        """
        with DatabaseOperation(self.logger, "unlink_chapter_arc"):
            arc = self._get_by_id(Arc, arc_id)
            if arc and arc in chapter.arcs:
                chapter.arcs.remove(arc)
                self.session.flush()

    # =========================================================================
    # ManuscriptScene Operations
    # =========================================================================

    def create_manuscript_scene(
        self, chapter: Chapter, metadata: Dict[str, Any]
    ) -> ManuscriptScene:
        """
        Create a manuscript scene within a chapter.

        Args:
            chapter: Parent chapter
            metadata: Scene data (name required, origin/status optional)

        Returns:
            Created ManuscriptScene

        Raises:
            ValidationError: If name is missing
        """
        with DatabaseOperation(self.logger, "create_manuscript_scene"):
            DataValidator.validate_required_fields(metadata, ["name"])

            name = DataValidator.normalize_string(metadata["name"])
            if not name:
                raise ValidationError("Invalid manuscript scene name")

            origin = self._resolve_enum(
                metadata.get("origin"), SceneOrigin, SceneOrigin.JOURNALED
            )
            status = self._resolve_enum(
                metadata.get("status"), SceneStatus, SceneStatus.FRAGMENT
            )

            scene = ManuscriptScene(
                name=name,
                description=metadata.get("description"),
                chapter_id=chapter.id,
                origin=origin,
                status=status,
                notes=metadata.get("notes"),
            )
            self.session.add(scene)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Created manuscript scene: {name}",
                {"scene_id": scene.id, "chapter_id": chapter.id},
            )
            return scene

    def update_manuscript_scene(
        self, scene: ManuscriptScene, metadata: Dict[str, Any]
    ) -> ManuscriptScene:
        """
        Update a manuscript scene.

        Args:
            scene: Scene to update
            metadata: Fields to update

        Returns:
            Updated ManuscriptScene
        """
        with DatabaseOperation(self.logger, "update_manuscript_scene"):
            if "name" in metadata:
                name = DataValidator.normalize_string(metadata["name"])
                if name:
                    scene.name = name

            if "description" in metadata:
                scene.description = metadata["description"]

            if "origin" in metadata:
                origin = self._resolve_enum(metadata["origin"], SceneOrigin, None)
                if origin:
                    scene.origin = origin

            if "status" in metadata:
                status = self._resolve_enum(metadata["status"], SceneStatus, None)
                if status:
                    scene.status = status

            if "notes" in metadata:
                scene.notes = metadata["notes"]

            self.session.flush()
            return scene

    def delete_manuscript_scene(self, scene: ManuscriptScene) -> None:
        """
        Delete a manuscript scene and its sources.

        Args:
            scene: Scene to delete
        """
        with DatabaseOperation(self.logger, "delete_manuscript_scene"):
            self.session.delete(scene)
            self.session.flush()

    def get_manuscript_scenes(self, chapter: Chapter) -> List[ManuscriptScene]:
        """
        Get all manuscript scenes for a chapter.

        Args:
            chapter: Chapter to query

        Returns:
            List of ManuscriptScene instances
        """
        with DatabaseOperation(self.logger, "get_manuscript_scenes"):
            return (
                self.session.query(ManuscriptScene)
                .filter(ManuscriptScene.chapter_id == chapter.id)
                .all()
            )

    # =========================================================================
    # ManuscriptSource Operations
    # =========================================================================

    def add_scene_source(
        self, scene: ManuscriptScene, metadata: Dict[str, Any]
    ) -> ManuscriptSource:
        """
        Link source material to a manuscript scene.

        Args:
            scene: Target manuscript scene
            metadata: Source data (source_type required, plus type-specific FK)

        Returns:
            Created ManuscriptSource

        Raises:
            ValidationError: If source_type is missing or invalid
        """
        with DatabaseOperation(self.logger, "add_scene_source"):
            DataValidator.validate_required_fields(metadata, ["source_type"])

            source_type = self._resolve_enum(
                metadata["source_type"], SourceType, None
            )
            if source_type is None:
                raise ValidationError(
                    f"Invalid source type: {metadata['source_type']}"
                )

            source = ManuscriptSource(
                manuscript_scene_id=scene.id,
                source_type=source_type,
                scene_id=metadata.get("scene_id"),
                entry_id=metadata.get("entry_id"),
                thread_id=metadata.get("thread_id"),
                external_note=metadata.get("external_note"),
                notes=metadata.get("notes"),
            )
            self.session.add(source)
            self.session.flush()
            return source

    def remove_scene_source(self, source: ManuscriptSource) -> None:
        """
        Remove a source from a manuscript scene.

        Args:
            source: Source to remove
        """
        with DatabaseOperation(self.logger, "remove_scene_source"):
            self.session.delete(source)
            self.session.flush()

    # =========================================================================
    # ManuscriptReference Operations
    # =========================================================================

    def create_manuscript_reference(
        self, chapter: Chapter, metadata: Dict[str, Any]
    ) -> ManuscriptReference:
        """
        Create a manuscript reference within a chapter.

        Args:
            chapter: Parent chapter
            metadata: Reference data (source_id required, mode optional)

        Returns:
            Created ManuscriptReference

        Raises:
            ValidationError: If source_id is missing
            DatabaseError: If reference source not found
        """
        with DatabaseOperation(self.logger, "create_manuscript_reference"):
            DataValidator.validate_required_fields(metadata, ["source_id"])

            source = self._get_by_id(ReferenceSource, metadata["source_id"])
            if not source:
                raise DatabaseError(
                    f"ReferenceSource with id={metadata['source_id']} not found"
                )

            mode = self._resolve_enum(
                metadata.get("mode"), ReferenceMode, ReferenceMode.THEMATIC
            )

            ref = ManuscriptReference(
                chapter_id=chapter.id,
                source_id=metadata["source_id"],
                mode=mode,
                content=metadata.get("content"),
                notes=metadata.get("notes"),
            )
            self.session.add(ref)
            self.session.flush()
            return ref

    def delete_manuscript_reference(self, ref: ManuscriptReference) -> None:
        """
        Delete a manuscript reference.

        Args:
            ref: Reference to delete
        """
        with DatabaseOperation(self.logger, "delete_manuscript_reference"):
            self.session.delete(ref)
            self.session.flush()

    # =========================================================================
    # Part Operations
    # =========================================================================

    def create_part(self, metadata: Dict[str, Any]) -> Part:
        """
        Create a new part.

        Args:
            metadata: Part data (title and/or number)

        Returns:
            Created Part
        """
        with DatabaseOperation(self.logger, "create_part"):
            part = Part(
                number=metadata.get("number"),
                title=metadata.get("title"),
            )
            self.session.add(part)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Created part: {part.display_name}",
                {"part_id": part.id},
            )
            return part

    def get_part(self, part_id: int) -> Optional[Part]:
        """
        Get a part by ID.

        Args:
            part_id: Part ID

        Returns:
            Part if found, None otherwise
        """
        with DatabaseOperation(self.logger, "get_part"):
            return self._get_by_id(Part, part_id)

    def get_all_parts(self) -> List[Part]:
        """
        Get all parts ordered by number.

        Returns:
            List of Part instances
        """
        with DatabaseOperation(self.logger, "get_all_parts"):
            return self._get_all(Part, order_by="number")

    def update_part(self, part: Part, metadata: Dict[str, Any]) -> Part:
        """
        Update a part.

        Args:
            part: Part to update
            metadata: Fields to update

        Returns:
            Updated Part
        """
        with DatabaseOperation(self.logger, "update_part"):
            if "number" in metadata:
                part.number = metadata["number"]
            if "title" in metadata:
                part.title = metadata["title"]
            self.session.flush()
            return part

    def delete_part(self, part: Part) -> None:
        """
        Delete a part (chapters become unassigned).

        Args:
            part: Part to delete
        """
        with DatabaseOperation(self.logger, "delete_part"):
            self.session.delete(part)
            self.session.flush()

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _resolve_enum(value: Any, enum_class: type, default: Any) -> Any:
        """
        Resolve a string or enum to its enum value.

        Args:
            value: String value or enum instance
            enum_class: Target enum class
            default: Default if value is None or invalid

        Returns:
            Enum value or default
        """
        if value is None:
            return default
        if isinstance(value, enum_class):
            return value
        try:
            return enum_class(value)
        except (ValueError, KeyError):
            try:
                return enum_class[value.upper()]
            except (KeyError, AttributeError):
                return default

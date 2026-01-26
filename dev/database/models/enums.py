#!/usr/bin/env python3
"""
enums.py
--------
Enumeration types for the Palimpsest database schema.

This module defines all enum classes used across the database models:

Journal Domain:
    - ReferenceMode: How a reference is used (direct, indirect, paraphrase, visual)
    - ReferenceType: Type of reference source (book, article, film, etc.)
    - RelationType: Type of relationship with a person (family, friend, etc.)

Manuscript Domain:
    - ChapterType: Type of manuscript chapter (prose, vignette, poem)
    - ChapterStatus: Status of manuscript chapter (draft, revised, final)
    - SceneOrigin: Origin of manuscript scene (journaled, inferred, invented, composite)
    - SceneStatus: Status of manuscript scene (fragment, draft, included, cut)
    - SourceType: Type of source for manuscript scene (scene, entry, thread, external)
    - ContributionType: Person-character contribution type (primary, composite, inspiration)

These enums provide type safety and consistent categorization across the database.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from enum import Enum
from typing import List


# =============================================================================
# JOURNAL DOMAIN ENUMS
# =============================================================================


class ReferenceMode(str, Enum):
    """
    Enumeration of reference modes.

    Defines how a reference is used in an entry:
        - DIRECT: Direct quotation
        - INDIRECT: Indirect reference or allusion
        - PARAPHRASE: Paraphrased content
        - VISUAL: Visual/image reference
        - THEMATIC: Conceptual/mood reference (manuscript only)
    """

    DIRECT = "direct"
    INDIRECT = "indirect"
    PARAPHRASE = "paraphrase"
    VISUAL = "visual"
    THEMATIC = "thematic"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available reference mode choices."""
        return [ref_mode.value for ref_mode in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        display_map = {
            self.DIRECT: "Direct",
            self.INDIRECT: "Indirect",
            self.PARAPHRASE: "Paraphrase",
            self.VISUAL: "Visual",
            self.THEMATIC: "Thematic",
        }
        return display_map.get(self, self.value.title())


class ReferenceType(str, Enum):
    """
    Enumeration of reference source types.

    Categories of sources that can be referenced in journal entries:
        - BOOK: Published books
        - POEM: Poem
        - ARTICLE: Articles, essays, papers
        - FILM: Movies and documentaries
        - SONG: Music and songs
        - PODCAST: Podcast episodes
        - INTERVIEW: Interviews
        - SPEECH: Speeches and talks
        - TV_SHOW: Television programs
        - VIDEO: Online videos, YouTube content
        - WEBSITE: Web pages, blog posts, online articles
        - OTHER: Miscellaneous sources
    """

    BOOK = "book"
    POEM = "poem"
    ARTICLE = "article"
    FILM = "film"
    SONG = "song"
    PODCAST = "podcast"
    INTERVIEW = "interview"
    SPEECH = "speech"
    TV_SHOW = "tv_show"
    VIDEO = "video"
    WEBSITE = "website"
    OTHER = "other"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available reference type choices."""
        return [ref_type.value for ref_type in cls]

    @classmethod
    def written_types(cls) -> List["ReferenceType"]:
        """Get types that are primarily written/text-based."""
        return [cls.BOOK, cls.POEM, cls.ARTICLE, cls.WEBSITE]

    @classmethod
    def audiovisual_types(cls) -> List["ReferenceType"]:
        """Get types that are audiovisual media."""
        return [cls.FILM, cls.PODCAST, cls.TV_SHOW, cls.VIDEO]

    @classmethod
    def performance_types(cls) -> List["ReferenceType"]:
        """Get types that are performances or spoken word."""
        return [cls.SONG, cls.INTERVIEW, cls.SPEECH]

    @property
    def is_written(self) -> bool:
        """Check if this is a written/text-based source."""
        return self in self.written_types()

    @property
    def is_audiovisual(self) -> bool:
        """Check if this is an audiovisual source."""
        return self in self.audiovisual_types()

    @property
    def requires_author(self) -> bool:
        """Check if this source type typically has an author field."""
        return self in [self.BOOK, self.ARTICLE]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        display_map = {
            self.BOOK: "Book",
            self.POEM: "Poem",
            self.ARTICLE: "Article",
            self.FILM: "Film",
            self.SONG: "Song",
            self.PODCAST: "Podcast",
            self.INTERVIEW: "Interview",
            self.SPEECH: "Speech",
            self.TV_SHOW: "TV Show",
            self.VIDEO: "Video",
            self.WEBSITE: "Website",
            self.OTHER: "Other",
        }
        return display_map.get(self, self.value.title())


class RelationType(str, Enum):
    """
    Enumeration of personal relationship types.

    Categories of relationships with people mentioned in journal:
        - FAMILY: Family members
        - FRIEND: Friends
        - ROMANTIC: Romantic partners
        - COLLEAGUE: Work colleagues
        - ACQUAINTANCE: Casual acquaintances
        - PROFESSIONAL: Professional relationships (therapist, doctor, etc.)
        - PUBLIC: Public figures, celebrities
        - OTHER: Uncategorized relationships
    """

    FAMILY = "family"
    FRIEND = "friend"
    ROMANTIC = "romantic"
    COLLEAGUE = "colleague"
    ACQUAINTANCE = "acquaintance"
    PROFESSIONAL = "professional"
    PUBLIC = "public"
    OTHER = "other"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available relation type choices."""
        return [rel_type.value for rel_type in cls]

    @classmethod
    def personal_types(cls) -> List["RelationType"]:
        """Get types that represent personal relationships."""
        return [cls.FAMILY, cls.FRIEND, cls.ROMANTIC]

    @classmethod
    def professional_types(cls) -> List["RelationType"]:
        """Get types that represent professional relationships."""
        return [cls.COLLEAGUE, cls.PROFESSIONAL]

    @property
    def is_personal(self) -> bool:
        """Check if this is a personal relationship."""
        return self in self.personal_types()

    @property
    def is_professional(self) -> bool:
        """Check if this is a professional relationship."""
        return self in self.professional_types()

    @property
    def is_close(self) -> bool:
        """Check if this typically represents a close relationship."""
        return self in [self.FAMILY, self.FRIEND, self.ROMANTIC]

    @property
    def privacy_level(self) -> int:
        """
        Get privacy sensitivity level (higher = more sensitive).

        Used for manuscript adaptation decisions:
            - 5: Romantic (highest privacy)
            - 4: Family
            - 3: Friend
            - 2: Professional, Colleague
            - 1: Acquaintance, Public (lowest privacy)
        """
        privacy_map = {
            self.ROMANTIC: 5,
            self.FAMILY: 4,
            self.FRIEND: 3,
            self.PROFESSIONAL: 2,
            self.COLLEAGUE: 2,
            self.ACQUAINTANCE: 1,
            self.PUBLIC: 1,
            self.OTHER: 2,
        }
        return privacy_map.get(self, 0)

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


# =============================================================================
# MANUSCRIPT DOMAIN ENUMS
# =============================================================================


class ChapterType(str, Enum):
    """
    Enumeration of manuscript chapter types.

    Defines the narrative form a chapter takes:
        - PROSE: Full narrative chapters
        - VIGNETTE: Correspondence, drafted messages, lists, fragments
        - POEM: Verse
    """

    PROSE = "prose"
    VIGNETTE = "vignette"
    POEM = "poem"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available chapter type choices."""
        return [chapter_type.value for chapter_type in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


class ChapterStatus(str, Enum):
    """
    Enumeration of manuscript chapter statuses.

    Defines the revision state of a chapter:
        - DRAFT: Initial draft
        - REVISED: Under revision
        - FINAL: Finalized
    """

    DRAFT = "draft"
    REVISED = "revised"
    FINAL = "final"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available chapter status choices."""
        return [status.value for status in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


class SceneOrigin(str, Enum):
    """
    Enumeration of manuscript scene origins.

    Defines how a scene was created:
        - JOURNALED: From journal scene
        - INFERRED: Reconstructed from gaps/references
        - INVENTED: Created for narrative
        - COMPOSITE: Merged from multiple sources
    """

    JOURNALED = "journaled"
    INFERRED = "inferred"
    INVENTED = "invented"
    COMPOSITE = "composite"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available scene origin choices."""
        return [origin.value for origin in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


class SceneStatus(str, Enum):
    """
    Enumeration of manuscript scene statuses.

    Defines the inclusion state of a scene:
        - FRAGMENT: Unassigned piece
        - DRAFT: In a chapter, being worked
        - INCLUDED: Final inclusion
        - CUT: Removed from manuscript
    """

    FRAGMENT = "fragment"
    DRAFT = "draft"
    INCLUDED = "included"
    CUT = "cut"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available scene status choices."""
        return [status.value for status in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


class SourceType(str, Enum):
    """
    Enumeration of manuscript source types.

    Defines what type of source material a manuscript scene uses:
        - SCENE: From journal scene
        - ENTRY: From journal entry
        - THREAD: From thread connection
        - EXTERNAL: External source (texts, memory, etc.)
    """

    SCENE = "scene"
    ENTRY = "entry"
    THREAD = "thread"
    EXTERNAL = "external"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available source type choices."""
        return [source_type.value for source_type in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


class ContributionType(str, Enum):
    """
    Enumeration of person-character contribution types.

    Defines how a real person contributes to a fictional character:
        - PRIMARY: Main basis for character
        - COMPOSITE: One of several people merged
        - INSPIRATION: Loose influence
    """

    PRIMARY = "primary"
    COMPOSITE = "composite"
    INSPIRATION = "inspiration"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available contribution type choices."""
        return [contribution.value for contribution in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()

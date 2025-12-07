"""
Enumeration Types
------------------

Enum classes for the Palimpsest database models.

Enums:
    - ReferenceMode: How a reference is used (direct, indirect, paraphrase, visual)
    - ReferenceType: Type of reference source (book, article, film, etc.)
    - RelationType: Type of relationship with a person (family, friend, etc.)

These enums provide type safety and consistent categorization across the database.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from enum import Enum
from typing import List


class ReferenceMode(str, Enum):
    """
    Enumeration of reference modes.
    - DIRECT: Direct quotation
    - INDIRECT: Indirect reference or allusion
    - PARAPHRASE: Paraphrased content
    - VISUAL: Visual/image reference
    """

    DIRECT = "direct"
    INDIRECT = "indirect"
    PARAPHRASE = "paraphrase"
    VISUAL = "visual"

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

#!/usr/bin/env python3
"""
configs.py
----------
Entity export configurations for wiki generation.

Maps each entity type to its template name, output directory,
filename generator, and context builder method. Used by WikiExporter
to iterate over all entity types uniformly.

Key Features:
    - Centralized configuration for all wiki page types
    - Filename generation using slugify utilities
    - Tier-based visibility filtering (tags with 1 entry get no page)
    - Overflow page configuration for high-frequency entities

Usage:
    from dev.wiki.configs import JOURNAL_CONFIGS, INDEX_CONFIGS

    for config in JOURNAL_CONFIGS:
        entities = session.query(config.model).all()
        for entity in entities:
            if config.should_generate(entity):
                ctx = config.build_context(builder, entity)
                renderer.render(config.template, ctx)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Type

# --- Local imports ---
from dev.database.models import (
    Arc,
    City,
    Event,
    Location,
    Motif,
    Person,
    Poem,
    ReferenceSource,
    Tag,
    Theme,
)
from dev.database.models.manuscript import Chapter, Character, ManuscriptScene, Part
from dev.utils.slugify import slugify


# ==================== Dataclasses ====================

@dataclass
class EntityConfig:
    """
    Configuration for generating wiki pages of a specific entity type.

    Attributes:
        name: Human-readable entity type name (for logging)
        model: SQLAlchemy model class
        template: Template path relative to templates root
        output_subdir: Subdirectory under wiki root for output files
        filename_fn: Function to generate filename from entity
        context_method: Name of WikiContextBuilder method to call
        should_generate_fn: Optional filter (returns False to skip entity)
    """

    name: str
    model: Type[Any]
    template: str
    output_subdir: str
    filename_fn: Callable[[Any], str]
    context_method: str
    should_generate_fn: Optional[Callable[[Any], bool]] = None

    def should_generate(self, entity: Any) -> bool:
        """
        Check if a wiki page should be generated for this entity.

        Args:
            entity: Entity model instance

        Returns:
            True if page should be generated
        """
        if self.should_generate_fn:
            return self.should_generate_fn(entity)
        return True


@dataclass
class IndexConfig:
    """
    Configuration for generating an index page.

    Attributes:
        name: Human-readable index name (for logging)
        template: Template path relative to templates root
        output_path: Output file path relative to wiki root
        context_method: Name of WikiExporter method that builds context
    """

    name: str
    template: str
    output_path: str
    context_method: str


# ==================== Filename Generators ====================

def _person_filename(person: Any) -> str:
    """Generate wiki page filename for a Person."""
    return f"{person.slug}.md"


def _location_filename(location: Any) -> str:
    """Generate wiki page filename for a Location."""
    city_slug = slugify(location.city.name)
    loc_slug = slugify(location.name)
    return f"{city_slug}/{loc_slug}.md"


def _city_filename(city: Any) -> str:
    """Generate wiki page filename for a City."""
    return f"{slugify(city.name)}.md"


def _named_entity_filename(entity: Any) -> str:
    """Generate wiki page filename for a named entity (Event, Arc, etc.)."""
    return f"{slugify(entity.name)}.md"


def _poem_filename(poem: Any) -> str:
    """Generate wiki page filename for a Poem."""
    return f"{slugify(poem.title)}.md"


def _reference_source_filename(source: Any) -> str:
    """Generate wiki page filename for a ReferenceSource."""
    return f"{slugify(source.title)}.md"


def _chapter_filename(chapter: Any) -> str:
    """Generate wiki page filename for a Chapter."""
    return f"{slugify(chapter.title)}.md"


def _character_filename(character: Any) -> str:
    """Generate wiki page filename for a Character."""
    return f"{slugify(character.name)}.md"


def _part_filename(part: Any) -> str:
    """Generate wiki page filename for a Part."""
    if part.title:
        return f"{slugify(part.title)}.md"
    return f"part-{part.number}.md"


# ==================== Visibility Filters ====================

def _tag_should_generate(tag: Any) -> bool:
    """Tags with only 1 entry get no page."""
    return tag.usage_count >= 2


def _theme_should_generate(theme: Any) -> bool:
    """Themes with only 1 entry get no page."""
    return theme.usage_count >= 2


# ==================== Configurations ====================

JOURNAL_CONFIGS: List[EntityConfig] = [
    EntityConfig(
        name="people",
        model=Person,
        template="journal/person.jinja2",
        output_subdir="journal/people",
        filename_fn=_person_filename,
        context_method="build_person_context",
    ),
    EntityConfig(
        name="locations",
        model=Location,
        template="journal/location.jinja2",
        output_subdir="journal/locations",
        filename_fn=_location_filename,
        context_method="build_location_context",
    ),
    EntityConfig(
        name="cities",
        model=City,
        template="journal/city.jinja2",
        output_subdir="journal/cities",
        filename_fn=_city_filename,
        context_method="build_city_context",
    ),
    EntityConfig(
        name="events",
        model=Event,
        template="journal/event.jinja2",
        output_subdir="journal/events",
        filename_fn=_named_entity_filename,
        context_method="build_event_context",
    ),
    EntityConfig(
        name="arcs",
        model=Arc,
        template="journal/arc.jinja2",
        output_subdir="journal/arcs",
        filename_fn=_named_entity_filename,
        context_method="build_arc_context",
    ),
    EntityConfig(
        name="tags",
        model=Tag,
        template="journal/tag.jinja2",
        output_subdir="journal/tags",
        filename_fn=_named_entity_filename,
        context_method="build_tag_context",
        should_generate_fn=_tag_should_generate,
    ),
    EntityConfig(
        name="themes",
        model=Theme,
        template="journal/theme.jinja2",
        output_subdir="journal/themes",
        filename_fn=_named_entity_filename,
        context_method="build_theme_context",
        should_generate_fn=_theme_should_generate,
    ),
    EntityConfig(
        name="poems",
        model=Poem,
        template="journal/poem.jinja2",
        output_subdir="journal/poems",
        filename_fn=_poem_filename,
        context_method="build_poem_context",
    ),
    EntityConfig(
        name="reference_sources",
        model=ReferenceSource,
        template="journal/reference_source.jinja2",
        output_subdir="journal/references",
        filename_fn=_reference_source_filename,
        context_method="build_reference_source_context",
    ),
    EntityConfig(
        name="motifs",
        model=Motif,
        template="journal/motif.jinja2",
        output_subdir="journal/motifs",
        filename_fn=_named_entity_filename,
        context_method="build_motif_context",
    ),
]


MANUSCRIPT_CONFIGS: List[EntityConfig] = [
    EntityConfig(
        name="chapters",
        model=Chapter,
        template="manuscript/chapter.jinja2",
        output_subdir="manuscript/chapters",
        filename_fn=_chapter_filename,
        context_method="build_chapter_context",
    ),
    EntityConfig(
        name="characters",
        model=Character,
        template="manuscript/character.jinja2",
        output_subdir="manuscript/characters",
        filename_fn=_character_filename,
        context_method="build_character_context",
    ),
    EntityConfig(
        name="manuscript_scenes",
        model=ManuscriptScene,
        template="manuscript/manuscript_scene.jinja2",
        output_subdir="manuscript/scenes",
        filename_fn=_named_entity_filename,
        context_method="build_manuscript_scene_context",
    ),
    EntityConfig(
        name="parts",
        model=Part,
        template="manuscript/part.jinja2",
        output_subdir="manuscript/parts",
        filename_fn=_part_filename,
        context_method="build_part_context",
    ),
]


INDEX_CONFIGS: List[IndexConfig] = [
    IndexConfig(
        name="main",
        template="indexes/main.jinja2",
        output_path="index.md",
        context_method="_build_main_index_context",
    ),
    IndexConfig(
        name="people",
        template="indexes/people.jinja2",
        output_path="indexes/people-index.md",
        context_method="_build_people_index_context",
    ),
    IndexConfig(
        name="places",
        template="indexes/places.jinja2",
        output_path="indexes/places-index.md",
        context_method="_build_places_index_context",
    ),
    IndexConfig(
        name="entries",
        template="indexes/entries.jinja2",
        output_path="indexes/entry-index.md",
        context_method="_build_entries_index_context",
    ),
    IndexConfig(
        name="events",
        template="indexes/events.jinja2",
        output_path="indexes/event-index.md",
        context_method="_build_events_index_context",
    ),
    IndexConfig(
        name="arcs",
        template="indexes/arcs.jinja2",
        output_path="indexes/arc-index.md",
        context_method="_build_arcs_index_context",
    ),
    IndexConfig(
        name="tags",
        template="indexes/tags.jinja2",
        output_path="indexes/tags-index.md",
        context_method="_build_tags_index_context",
    ),
    IndexConfig(
        name="themes",
        template="indexes/themes.jinja2",
        output_path="indexes/themes-index.md",
        context_method="_build_themes_index_context",
    ),
    IndexConfig(
        name="poems",
        template="indexes/poems.jinja2",
        output_path="indexes/poems-index.md",
        context_method="_build_poems_index_context",
    ),
    IndexConfig(
        name="references",
        template="indexes/references.jinja2",
        output_path="indexes/references-index.md",
        context_method="_build_references_index_context",
    ),
    IndexConfig(
        name="manuscript",
        template="indexes/manuscript.jinja2",
        output_path="indexes/manuscript-index.md",
        context_method="_build_manuscript_index_context",
    ),
]

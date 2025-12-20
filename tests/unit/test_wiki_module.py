#!/usr/bin/env python3
"""
test_wiki_module.py
-------------------
Unit tests for the dev/wiki/ module.

Tests cover:
    - WikiRenderer: Template loading and rendering
    - WikiExporter: Entity export functionality
    - Filters: Custom Jinja2 filters
    - Configs: Entity configuration objects
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

# --- Third party imports ---
import pytest

# --- Local imports ---
from dev.wiki.renderer import WikiRenderer
from dev.wiki.filters import entity_link, format_date, pluralize, slugify
from dev.wiki.configs import (
    EntityConfig,
    PERSON_CONFIG,
    LOCATION_CONFIG,
    CITY_CONFIG,
    ENTRY_CONFIG,
    EVENT_CONFIG,
    TAG_CONFIG,
    THEME_CONFIG,
    REFERENCE_CONFIG,
    POEM_CONFIG,
    ALL_CONFIGS,
)


class TestWikiRenderer:
    """Tests for WikiRenderer class."""

    def test_init_default_template_dir(self):
        """Renderer initializes with default template directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            renderer = WikiRenderer(wiki_dir)
            assert renderer.wiki_dir == wiki_dir
            assert renderer.env is not None

    def test_init_custom_template_dir(self):
        """Renderer accepts custom template directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            template_dir = Path(tmpdir) / "templates"
            template_dir.mkdir()
            renderer = WikiRenderer(wiki_dir, template_dir)
            assert renderer.wiki_dir == wiki_dir

    def test_templates_load(self):
        """All entity templates load without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            renderer = WikiRenderer(wiki_dir)

            templates = [
                "person", "entry", "location", "city",
                "event", "tag", "theme", "reference", "poem"
            ]

            for template_name in templates:
                template = renderer.env.get_template(f"{template_name}.jinja2")
                assert template is not None

    def test_filters_registered(self):
        """Custom filters are registered with environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            renderer = WikiRenderer(wiki_dir)

            # Check filters
            assert "slugify" in renderer.env.filters
            assert "format_date" in renderer.env.filters
            assert "pluralize" in renderer.env.filters

            # Check globals
            assert "entity_link" in renderer.env.globals
            assert "wikilink" in renderer.env.globals
            assert "wiki_dir" in renderer.env.globals


class TestFilters:
    """Tests for custom Jinja2 filters."""

    def test_format_date_default(self):
        """format_date returns ISO format by default."""
        d = date(2024, 7, 15)
        assert format_date(d) == "2024-07-15"

    def test_format_date_custom_format(self):
        """format_date accepts custom format string."""
        d = date(2024, 7, 15)
        assert format_date(d, "%B %d, %Y") == "July 15, 2024"

    def test_format_date_none(self):
        """format_date returns empty string for None."""
        assert format_date(None) == ""

    def test_pluralize_singular(self):
        """pluralize returns singular for count 1."""
        assert pluralize(1, "entry", "entries") == "1 entry"

    def test_pluralize_plural(self):
        """pluralize returns plural for count > 1."""
        assert pluralize(5, "entry", "entries") == "5 entries"

    def test_pluralize_zero(self):
        """pluralize returns plural for count 0."""
        assert pluralize(0, "entry", "entries") == "0 entries"

    def test_pluralize_default_plural(self):
        """pluralize adds 's' as default plural."""
        assert pluralize(3, "file") == "3 files"


class TestEntityLink:
    """Tests for entity_link filter."""

    def test_entity_link_person(self):
        """entity_link generates correct link for Person."""
        person = MagicMock()
        person.display_name = "John Doe"

        wiki_dir = Path("/wiki")
        from_path = Path("/wiki/entries/2024/2024-01-01.md")

        link = entity_link(person, "people", wiki_dir, from_path)
        assert "[[" in link
        assert "John Doe" in link
        assert "john_doe.md" in link  # slugify uses underscores

    def test_entity_link_entry(self):
        """entity_link generates correct link for Entry."""
        entry = MagicMock()
        entry.date = date(2024, 7, 15)

        wiki_dir = Path("/wiki")
        from_path = Path("/wiki/people/john-doe.md")

        link = entity_link(entry, "entries", wiki_dir, from_path)
        assert "[[" in link
        assert "2024-07-15" in link

    def test_entity_link_tag(self):
        """entity_link generates correct link for Tag."""
        tag = MagicMock()
        tag.tag = "reflection"

        wiki_dir = Path("/wiki")
        from_path = Path("/wiki/entries/2024/2024-01-01.md")

        link = entity_link(tag, "tags", wiki_dir, from_path)
        assert "[[" in link
        assert "reflection" in link


class TestEntityConfigs:
    """Tests for entity configuration objects."""

    def test_all_configs_present(self):
        """ALL_CONFIGS contains all 9 entity types."""
        assert len(ALL_CONFIGS) == 9
        names = [c.name for c in ALL_CONFIGS]
        assert "person" in names
        assert "location" in names
        assert "city" in names
        assert "entry" in names
        assert "event" in names
        assert "tag" in names
        assert "theme" in names
        assert "reference" in names
        assert "poem" in names

    def test_person_config(self):
        """PERSON_CONFIG has correct attributes."""
        assert PERSON_CONFIG.name == "person"
        assert PERSON_CONFIG.plural == "people"
        assert PERSON_CONFIG.template == "person"
        assert PERSON_CONFIG.folder == "people"
        assert PERSON_CONFIG.query is not None
        assert PERSON_CONFIG.get_name is not None
        assert PERSON_CONFIG.get_slug is not None

    def test_entry_config(self):
        """ENTRY_CONFIG has correct attributes."""
        assert ENTRY_CONFIG.name == "entry"
        assert ENTRY_CONFIG.plural == "entries"
        assert ENTRY_CONFIG.template == "entry"
        assert ENTRY_CONFIG.folder == "entries"

    def test_config_get_slug(self):
        """get_slug functions produce valid slugs."""
        # Test person slug (slugify uses underscores)
        person = MagicMock()
        person.display_name = "John Doe"
        slug = PERSON_CONFIG.get_slug(person)
        assert slug == "john_doe"

        # Test tag slug
        tag = MagicMock()
        tag.tag = "Personal Reflection"
        slug = TAG_CONFIG.get_slug(tag)
        assert slug == "personal_reflection"


class TestSlugify:
    """Tests for slugify utility."""

    def test_slugify_basic(self):
        """slugify converts basic text to slug with underscores."""
        assert slugify("Hello World") == "hello_world"

    def test_slugify_preserves_unicode(self):
        """slugify preserves unicode characters."""
        assert slugify("María José") == "maría_josé"

    def test_slugify_slashes_to_hyphens(self):
        """slugify converts slashes to hyphens."""
        assert slugify("2024/01/15") == "2024-01-15"

    def test_slugify_lowercase(self):
        """slugify lowercases text."""
        assert slugify("HELLO WORLD") == "hello_world"

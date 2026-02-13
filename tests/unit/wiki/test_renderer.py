#!/usr/bin/env python3
"""
test_renderer.py
----------------
Tests for the WikiRenderer class.

Covers Jinja2 environment setup, filter registration, template
rendering, and file-based rendering with change detection.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.wiki.renderer import WikiRenderer


# ==================== Initialization ====================

class TestRendererInit:
    """Tests for WikiRenderer initialization."""

    def test_dict_loader(self) -> None:
        """Renderer initializes with DictLoader from templates dict."""
        renderer = WikiRenderer(templates={"test.jinja2": "Hello"})
        assert renderer.env is not None

    def test_filesystem_loader(self, tmp_path: Path) -> None:
        """Renderer initializes with FileSystemLoader from directory."""
        (tmp_path / "test.jinja2").write_text("Hello")
        renderer = WikiRenderer(templates_dir=tmp_path)
        assert renderer.env is not None

    def test_both_loaders_raises(self, tmp_path: Path) -> None:
        """Providing both templates_dir and templates raises ValueError."""
        with pytest.raises(ValueError, match="not both"):
            WikiRenderer(
                templates_dir=tmp_path,
                templates={"test.jinja2": "Hello"},
            )


# ==================== Filter Registration ====================

class TestFilterRegistration:
    """Tests that all custom filters are registered on the env."""

    def setup_method(self) -> None:
        """Create renderer with minimal template."""
        self.renderer = WikiRenderer(templates={"t.jinja2": ""})

    def test_wikilink_registered(self) -> None:
        """wikilink filter is available."""
        assert "wikilink" in self.renderer.env.filters

    def test_date_long_registered(self) -> None:
        """date_long filter is available."""
        assert "date_long" in self.renderer.env.filters

    def test_date_range_registered(self) -> None:
        """date_range filter is available."""
        assert "date_range" in self.renderer.env.filters

    def test_mid_dot_join_registered(self) -> None:
        """mid_dot_join filter is available."""
        assert "mid_dot_join" in self.renderer.env.filters

    def test_adaptive_list_registered(self) -> None:
        """adaptive_list filter is available."""
        assert "adaptive_list" in self.renderer.env.filters

    def test_timeline_table_registered(self) -> None:
        """timeline_table filter is available."""
        assert "timeline_table" in self.renderer.env.filters

    def test_source_path_registered(self) -> None:
        """source_path filter is available."""
        assert "source_path" in self.renderer.env.filters

    def test_flexible_date_registered(self) -> None:
        """flexible_date filter is available."""
        assert "flexible_date" in self.renderer.env.filters

    def test_thread_dates_registered(self) -> None:
        """thread_dates filter is available."""
        assert "thread_dates" in self.renderer.env.filters

    def test_chunked_registered(self) -> None:
        """chunked filter is available."""
        assert "chunked" in self.renderer.env.filters


# ==================== Rendering ====================

class TestRender:
    """Tests for in-memory template rendering."""

    def test_simple_render(self) -> None:
        """Render a simple variable substitution."""
        renderer = WikiRenderer(templates={"t.jinja2": "Hello {{ name }}"})
        result = renderer.render("t.jinja2", {"name": "World"})
        assert result == "Hello World"

    def test_render_with_filter(self) -> None:
        """Render using a custom filter."""
        renderer = WikiRenderer(
            templates={"t.jinja2": "{{ name | wikilink }}"}
        )
        result = renderer.render("t.jinja2", {"name": "Clara"})
        assert result == "[[Clara]]"

    def test_render_with_date_filter(self) -> None:
        """Render using date_long filter."""
        renderer = WikiRenderer(
            templates={"t.jinja2": "{{ d | date_long }}"}
        )
        result = renderer.render("t.jinja2", {"d": date(2024, 11, 8)})
        assert result == "Friday, November 8, 2024"

    def test_render_with_list_filter(self) -> None:
        """Render using mid_dot_join filter."""
        renderer = WikiRenderer(
            templates={"t.jinja2": "{{ items | mid_dot_join }}"}
        )
        result = renderer.render("t.jinja2", {"items": ["A", "B", "C"]})
        assert result == "A · B · C"

    def test_render_conditional(self) -> None:
        """Render with Jinja2 conditional blocks."""
        template = "{% if show %}Visible{% endif %}"
        renderer = WikiRenderer(templates={"t.jinja2": template})
        assert renderer.render("t.jinja2", {"show": True}) == "Visible"
        assert renderer.render("t.jinja2", {"show": False}) == ""

    def test_render_loop(self) -> None:
        """Render with Jinja2 for loop."""
        template = "{% for i in items %}{{ i }}\n{% endfor %}"
        renderer = WikiRenderer(templates={"t.jinja2": template})
        result = renderer.render("t.jinja2", {"items": ["A", "B"]})
        assert "A" in result
        assert "B" in result

    def test_trim_blocks(self) -> None:
        """Block tags don't add extra newlines (trim_blocks=True)."""
        template = "before\n{% if true %}inside\n{% endif %}after"
        renderer = WikiRenderer(templates={"t.jinja2": template})
        result = renderer.render("t.jinja2", {})
        assert result == "before\ninside\nafter"

    def test_lstrip_blocks(self) -> None:
        """Indented block tags don't add whitespace (lstrip_blocks=True)."""
        template = "  {% if true %}content{% endif %}"
        renderer = WikiRenderer(templates={"t.jinja2": template})
        result = renderer.render("t.jinja2", {})
        assert result == "content"


# ==================== File Rendering ====================

class TestRenderToFile:
    """Tests for file-based rendering with change detection."""

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """Creates file and returns True for new output."""
        renderer = WikiRenderer(templates={"t.jinja2": "content"})
        output = tmp_path / "out.md"

        changed = renderer.render_to_file("t.jinja2", {}, output)

        assert changed is True
        assert output.read_text() == "content"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates parent directories if they don't exist."""
        renderer = WikiRenderer(templates={"t.jinja2": "content"})
        output = tmp_path / "sub" / "dir" / "out.md"

        renderer.render_to_file("t.jinja2", {}, output)

        assert output.exists()
        assert output.read_text() == "content"

    def test_no_change_returns_false(self, tmp_path: Path) -> None:
        """Returns False when file content is identical."""
        renderer = WikiRenderer(templates={"t.jinja2": "content"})
        output = tmp_path / "out.md"

        # First write
        renderer.render_to_file("t.jinja2", {}, output)
        # Second write with same content
        changed = renderer.render_to_file("t.jinja2", {}, output)

        assert changed is False

    def test_change_returns_true(self, tmp_path: Path) -> None:
        """Returns True when content differs from existing file."""
        renderer = WikiRenderer(
            templates={
                "t1.jinja2": "old content",
                "t2.jinja2": "new content",
            }
        )
        output = tmp_path / "out.md"

        renderer.render_to_file("t1.jinja2", {}, output)
        changed = renderer.render_to_file("t2.jinja2", {}, output)

        assert changed is True
        assert output.read_text() == "new content"

    def test_preserves_unchanged_file(self, tmp_path: Path) -> None:
        """Unchanged files keep their original mtime."""
        import time

        renderer = WikiRenderer(templates={"t.jinja2": "content"})
        output = tmp_path / "out.md"

        renderer.render_to_file("t.jinja2", {}, output)
        first_mtime = output.stat().st_mtime

        time.sleep(0.05)  # Ensure time passes

        renderer.render_to_file("t.jinja2", {}, output)
        second_mtime = output.stat().st_mtime

        assert first_mtime == second_mtime

    def test_render_with_context(self, tmp_path: Path) -> None:
        """File rendering uses context variables."""
        renderer = WikiRenderer(
            templates={"t.jinja2": "# {{ title }}"}
        )
        output = tmp_path / "out.md"

        renderer.render_to_file("t.jinja2", {"title": "Hello"}, output)

        assert output.read_text() == "# Hello"

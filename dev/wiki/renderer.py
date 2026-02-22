#!/usr/bin/env python3
"""
renderer.py
-----------
Jinja2 template engine for wiki page generation.

Configures the Jinja2 environment with custom filters, template
loading, and rendering utilities. Supports both filesystem-based
templates (production) and dict-based templates (testing).

Key Features:
    - Custom filter registration for all wiki formatting needs
    - Change detection: only writes files when content differs
    - Support for DictLoader (tests) and FileSystemLoader (production)
    - Consistent markdown output with trailing newline

Usage:
    from dev.wiki.renderer import WikiRenderer

    # Production: loads from dev/wiki/templates/
    renderer = WikiRenderer()
    content = renderer.render("journal/entry.jinja2", context)
    changed = renderer.render_to_file("journal/entry.jinja2", context, path)

    # Testing: supply templates as dict
    renderer = WikiRenderer(templates={"test.jinja2": "Hello {{ name }}"})
    content = renderer.render("test.jinja2", {"name": "World"})

Dependencies:
    - jinja2>=3.1.0
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Any, Dict, Optional

# --- Third-party imports ---
from jinja2 import Environment, FileSystemLoader, DictLoader, BaseLoader

# --- Local imports ---
from dev.wiki import filters as wiki_filters
from dev.core.paths import WIKI_TEMPLATES_DIR


class WikiRenderer:
    """
    Jinja2-based wiki page renderer.

    Manages the Jinja2 environment with custom filters and provides
    rendering methods for both in-memory and file-based output.

    Attributes:
        env: Configured Jinja2 Environment instance
    """

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        templates: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize the wiki renderer.

        Provide either a filesystem templates directory or a dict of
        template strings. If neither is provided, defaults to the
        project's wiki templates directory.

        Args:
            templates_dir: Path to templates directory (FileSystemLoader)
            templates: Dict of template_name → template_string (DictLoader)

        Raises:
            ValueError: If both templates_dir and templates are provided
        """
        if templates_dir and templates:
            raise ValueError(
                "Provide either templates_dir or templates, not both"
            )

        loader: BaseLoader
        if templates is not None:
            loader = DictLoader(templates)
        elif templates_dir is not None:
            loader = FileSystemLoader(str(templates_dir))
        else:
            loader = FileSystemLoader(str(WIKI_TEMPLATES_DIR))

        self.env = Environment(
            loader=loader,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._register_filters()

    def _register_filters(self) -> None:
        """
        Register all custom wiki filters on the Jinja2 environment.

        Filters are pure functions defined in dev.wiki.filters and
        registered here for use in templates as ``{{ value | filter_name }}``.
        """
        self.env.filters["entry_date_short"] = wiki_filters.entry_date_short
        self.env.filters["entry_date_display"] = wiki_filters.entry_date_display
        self.env.filters["wikilink"] = wiki_filters.wikilink
        self.env.filters["date_long"] = wiki_filters.date_long
        self.env.filters["date_range"] = wiki_filters.date_range
        self.env.filters["mid_dot_join"] = wiki_filters.mid_dot_join
        self.env.filters["adaptive_list"] = wiki_filters.adaptive_list
        self.env.filters["timeline_table"] = wiki_filters.timeline_table
        self.env.filters["source_path"] = wiki_filters.source_path
        self.env.filters["flexible_date"] = wiki_filters.flexible_date_display
        self.env.filters["thread_dates"] = wiki_filters.thread_date_range
        self.env.filters["chunked"] = wiki_filters.chunked_list
        self.env.filters["month_display"] = wiki_filters.month_display
        self.env.filters["zpad"] = wiki_filters.zpad

    def render(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Template path relative to templates root
            context: Template variables

        Returns:
            Rendered markdown string
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_to_file(
        self,
        template_name: str,
        context: Dict[str, Any],
        output_path: Path,
    ) -> bool:
        """
        Render a template and write to file, with change detection.

        Compares rendered output against existing file content. Only
        writes if the content has changed, preserving file timestamps
        for unchanged pages.

        Args:
            template_name: Template path relative to templates root
            context: Template variables
            output_path: Destination file path

        Returns:
            True if the file was written (content changed or new file),
            False if the existing file already had identical content
        """
        content = self.render(template_name, context)

        # Check if file exists with same content
        if output_path.exists():
            existing = output_path.read_text(encoding="utf-8")
            if existing == content:
                return False

        # Write new or changed content
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return True

#!/usr/bin/env python3
"""
renderer.py
-----------
Jinja2-based wiki renderer.

Provides a simple interface for rendering database entities
to wiki markdown using Jinja2 templates.

Usage:
    renderer = WikiRenderer(wiki_dir)
    content = renderer.render("person", person=db_person, output_path=path)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Any, Optional

# --- Third party imports ---
from jinja2 import Environment, FileSystemLoader, select_autoescape

# --- Local imports ---
from .filters import register_filters


class WikiRenderer:
    """
    Renders database entities to wiki markdown using Jinja2 templates.

    This class manages the Jinja2 environment and provides methods for
    rendering entity pages and index pages from templates.

    Attributes:
        wiki_dir: Root wiki directory (for generating relative links)
        env: Jinja2 Environment with custom filters registered
    """

    def __init__(
        self,
        wiki_dir: Path,
        template_dir: Optional[Path] = None,
    ):
        """
        Initialize the wiki renderer.

        Args:
            wiki_dir: Root wiki directory (for generating relative links)
            template_dir: Directory containing Jinja2 templates
                         (defaults to dev/wiki/templates)
        """
        self.wiki_dir = wiki_dir

        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(disabled_extensions=('jinja2', 'md')),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters and globals
        register_filters(self.env)

        # Add wiki_dir to globals for link generation
        self.env.globals['wiki_dir'] = wiki_dir

    def render(
        self,
        template_name: str,
        output_path: Path,
        **context: Any,
    ) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Template name (e.g., "person" for person.jinja2)
            output_path: Path where the rendered file will be written
                        (used for generating relative links)
            **context: Template context variables

        Returns:
            Rendered markdown content
        """
        template = self.env.get_template(f"{template_name}.jinja2")
        return template.render(
            output_path=output_path,
            **context,
        )

    def render_index(
        self,
        index_name: str,
        output_path: Path,
        **context: Any,
    ) -> str:
        """
        Render an index page template.

        Args:
            index_name: Index template name (e.g., "people" for indexes/people.jinja2)
            output_path: Path where the index will be written
            **context: Template context variables

        Returns:
            Rendered markdown content
        """
        template = self.env.get_template(f"indexes/{index_name}.jinja2")
        return template.render(
            output_path=output_path,
            **context,
        )

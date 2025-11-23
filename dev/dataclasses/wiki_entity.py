#!/usr/bin/env python3
"""
wiki_entity.py
-------------------

Defines the abstract base class `WikiEntity`,
which serves as a common interface for all Markdown-based entities
used in the Palimpsest vimwiki system.

Each subclass must implement methods to:
- construct itself from a source file (`from_file`)
- serialize itself back to Markdown (`to_wiki`)
- optionally write itself to disk (`write_to_file`)

This allows uniform handling of entries, people, vignettes,
and other wiki types, regardless of their structure or source.

Shared typing logic (e.g., TypeVar `T`) is also defined here.
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar, Optional, Type, List

T = TypeVar("T", bound="WikiEntity")

class WikiEntity(ABC):
    # TODO: Add the other new classes to docstring
    """
    Abstract base class for all Markdown-based wiki entities.

    Provides a common interface requiring:
    - a classmethod `from_file(cls, path)` to construct an instance from a file
    - an instance method `to_wiki()` to serialize the object to Markdown lines
    - a `write_to_file()` helper to write the Markdown to the associated path

    Subclasses include Entry, Person, Theme, and Vignette.
    """
    @classmethod
    @abstractmethod
    def from_file(cls: Type[T], path: Path) -> Optional[T]:
        pass

    @abstractmethod
    def to_wiki(self) -> List[str]:
        pass

    def write_to_file(self) -> None:
        """Writes the wiki entry to its associated file."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("\n".join(self.to_wiki()), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"Error writing wiki file for {self.path}: {e}\n")
            raise

    def generate_breadcrumbs(self, wiki_dir: Path) -> str:
        """
        Generate breadcrumb navigation from wiki root to this entity.

        Args:
            wiki_dir: Wiki root directory

        Returns:
            Breadcrumb string with wiki links (e.g., "[[index.md|Home]] > [[entries.md|Entries]] > 2024-11-01")
        """
        from dev.utils.md import relative_link

        # Get path relative to wiki root
        try:
            rel_path = self.path.relative_to(wiki_dir)
        except ValueError:
            # Path is not under wiki_dir
            return ""

        # Build breadcrumb parts
        parts = []
        current_path = wiki_dir

        # Add Home link (always include, even if index.md doesn't exist yet)
        home_path = wiki_dir / "index.md"
        home_link = relative_link(self.path, home_path)
        parts.append(f"[[{home_link}|Home]]")

        # Add intermediate directories
        for part in rel_path.parts[:-1]:
            current_path = current_path / part

            # Check for index file in this directory
            index_path = current_path / f"{part}.md"
            if not index_path.exists():
                # Try looking in parent for category index
                index_path = current_path.parent / f"{part}.md"

            if index_path.exists():
                link = relative_link(self.path, index_path)
                # Capitalize first letter of part for display
                display = part.capitalize()
                parts.append(f"[[{link}|{display}]]")
            else:
                # No index file, just show text
                parts.append(part.capitalize())

        # Add current page name (no link)
        parts.append(self.path.stem.replace("_", " ").replace("-", "/"))

        return " > ".join(parts)

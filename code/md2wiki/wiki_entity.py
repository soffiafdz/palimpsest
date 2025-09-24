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

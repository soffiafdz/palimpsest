#!/usr/bin/env python3
"""
tag.py
-------------------

Defines the Tag class representing a metadata tag used in the Palimpsest vimwiki system.

Tags are simple textual labels applied to entries, people, or themes to aid categorization,
search, and filtering within the wiki.

This module handles parsing, serialization, and management of tags associated with wiki entities.
"""

@dataclass
class Tag(WikiEntity):
    """
    Represents a single metadata tag in the wiki system.

    Fields:
    - name (str): The tag label, typically a single word or short phrase.
    - description (Optional[str]): An optional description or notes about the tag.
    - related_entries (List[Entry]): Optional list of entries tagged with this label.
    # Add other fields as needed (e.g., popularity, synonyms).

    Tags are used to classify and group content across entries, people, and themes.
    """

#!/usr/bin/env python3
"""
entry.py
-------------------

Defines the `Entry` class, representing a journal entry parsed from Markdown.

Each Entry includes:
- header text (e.g. title or date)
- body lines (content of the entry)
- associated metadata (e.g. date, tags, themes, reading metrics)
- ...

Entries can be parsed from Markdown files and used to update other wiki entities
such as people or themes via mentions and references.
"""


@dataclass
class Entry(WikiEntity):
    """
    Represents a journal entry parsed from a Markdown file.

    Fields:
    - path: the original file path
    - header: human-readable title or formatted date
    - body: list of Markdown lines (the main content)
    - date: parsed ISO date of the entry
    - word_count: number of words in the entry
    - reading_time_min: estimated reading time in minutes

    Used to compute presence, extract themes, and feed into wiki population logic.
    """
@dataclass
class Entry(WikiEntity):
    """
    - path:   Path to md file
    - stem:   Stem (basename)
    - year:   <YYYY>
    - month:  Name of the month
    - status: <unreviewed/discard|reference|fragments|source|quote|curated>
    - people: People involved/mentioned (besides narrator)
    - tags:   Tags
    - themes: Themes
    - notes:  Reviewing notes
    """
    path:    Path
    stem:    str
    year:    str
    month:   str
    status:  str
    people:  Set[str] = field(default_factory=set)
    tags:    Set[str] = field(default_factory=set)
    themes:  Set[str] = field(default_factory=set)
    notes:   str      = ""
    done:    bool     = False


    # --- helper to fold YAML lists into the sets ---
    def merge_meta(self, meta: Dict[str, Any]) -> None:
        """Update this Entry with list-like fields from YAML front-matter."""
        self.people.update(meta.get("people", []))
        self.tags.update(meta.get("tags", []))
        self.themes.update(meta.get("themes", []))
        self.done = False if self.status == 'unreviewed' else True
        if "notes" in meta:
            self.notes = str(meta["notes"]).strip()



#!/usr/bin/env python3
"""
reference.py
-------------------

Defines the Reference class used to track appearing throughout the journal:
- meaningful quotations
- fragments
- citations
- poems

References may come from external sources (books, poems, lyrics)
or internal ones (original lines, self-poems, recurring phrases).

Some references appear as epigraphs, others are embedded within entries.
All are tracked with source, context.
Optionally there is a shared identifier linking versions or repetitions.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import datetime

from .wiki_entity import WikiEntity

@dataclass
class Reference(WikiEntity):
    """
    Represents a meaningful external or internal reference in the journal.

    Attributes:
        path: Path to the wiki file where the reference is recorded.
        date: Date the reference appeared or was written down.
        type: "quote", "poem", "lyric", "dialogue", "original", etc.
        source: Author, speaker, or source material; "original" if self-written.
        text: The referenced content.
        entry_link: Relative path to the journal entry where it appears.
        position: Where it appears in the entry: "epigraph", "body".
        related_id: Shared identifier used to group variants or repetitions.
        version: Integer version number for evolving or rewritten quotes.
        final: Whether the quote is considered finalized in its form or usage.
        notes: Optional editorial or interpretive notes.
    """
    # TODO: Review these
    path: Path
    date: datetime.date
    type: str
    source: str
    text: str
    entry_link: str
    position: str  # "epigraph", "body", "footnote"
    related_id: Optional[str] = None
    version: int = 1
    final: bool = False
    notes: Optional[str] = None

    # TODO: Change this
    def to_wiki(self) -> List[str]:
        lines = [
            f"### {self.date.isoformat()} — {self.source}",
            f"*Type*: {self.type}",
            f"*Position*: {self.position}",
            f"*Entry*: {self.entry_link}",
            f"*Version*: {self.version}",
            f"*Final*: {'yes' if self.final else 'no'}",
        ]
        if self.related_id:
            lines.append(f"*Related*: {self.related_id}")
        lines.append("")
        lines.append("> " + self.text.replace("\n", "\n> "))
        if self.notes:
            lines.extend(["", "*Notes*:", self.notes])
        lines.append("")
        return lines

#!/usr/bin/env python3
"""
poem.py
-------------------

Defines the Poem class.
To track original poems written during or alongside the journal.
Each poem has a finalized version. It may have been quoted or referenced in
prior entries, and can optionally link to its initial draft or source moments.

Poems can be related to-, but are distinct from References
in that they represent self-contained authored works,
often stored in dedicated wiki pages.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import datetime

from .wiki_entity import WikiEntity

@dataclass
class Poem(WikiEntity):
    """
    Represents a finalized poem authored within or adjacent to the journal.

    Attributes:
        path: Path to the poem's wiki file.
        title: Title of the poem.
        body: Final text of the poem.
        date_written: Date the poem was completed or solidified.
        date_first_referenced: Date the poem first appeared in draft or partial form.
        draft_link: Link to a journal entry or draft version, if applicable.
        related_refs: List of dates or links where this poem was referenced or quoted.
        notes: Commentary on influences, revision history, or contextual notes.
    """
    # TODO: review these
    path: Path
    title: str
    body: str
    date_written: datetime.date
    date_first_referenced: Optional[datetime.date] = None
    draft_link: Optional[str] = None
    related_refs: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    # TODO: Check/change this
    def to_wiki(self) -> List[str]:
        lines = [
            f"# {self.title}",
            "",
            f"**Date written**: {self.date_written.isoformat()}",
        ]
        if self.date_first_referenced:
            lines.append(f"**First draft referenced**: [{self.date_first_referenced}](../journal/md/{self.date_first_referenced.year}/{self.date_first_referenced.isoformat()}.md)")
        if self.draft_link:
            lines.append(f"**Draft link**: {self.draft_link}")
        if self.related_refs:
            joined = ", ".join(f"[{d}](../journal/md/{d[:4]}/{d}.md)" for d in self.related_refs)
            lines.append(f"**Related entries**: {joined}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(self.body.strip())
        lines.append("")
        if self.notes:
            lines.append("---\n")
            lines.append("*Notes*:")
            lines.append(self.notes.strip())
            lines.append("")
        return lines


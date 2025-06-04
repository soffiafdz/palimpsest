#!/usr/bin/env python3
"""
theme.py
-------------------

Defines the `Theme` class, which represents a conceptual or emotional thread
that recurs across entries in the journal.

Each theme may be linked to:
- a list of entries where it appears
- associated people or vignettes
- a description or annotation

Themes are compiled into `wiki/themes.md` and help structure the emotional or narrative logic of the project.
"""

@dataclass
class Theme(WikiEntity):
    """
    Represents a recurring conceptual thread in the journal and wiki.

    Fields:
    - name: name of the theme (e.g., solitude, memory, desire)
    - path: Markdown file for the theme entry
    - entries: references to journal entries where the theme appears
    - people: optional set of associated people
    - vignettes: optional curated vignettes that express the theme
    - notes: optional description or prose expansion

    Themes help organize the emotional and narrative arcs of the Palimpsest project.
    """


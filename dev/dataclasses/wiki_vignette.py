#!/usr/bin/env python3
"""
vignette.py
-------------------

Defines the `Vignette` class, representing a short narrative or excerpt associated
with a person or theme in the wiki.

Each vignette includes:
- a title
- a source Markdown file and relative link
- an optional note or annotation

Used primarily to enrich `Person` or `Theme` entries by attaching curated textual fragments.
"""
from dataclasses import dataclass
from dev.dataclasses.wiki_entity import WikiEntity

@dataclass
class Vignette(WikiEntity):
    """
    Represents a narrative fragment or excerpt in the vimwiki.

    Fields:
    - path: location of the vignette Markdown file
    - title: heading or short label
    - source_md: source entry file (optional)
    - link: relative link to the source from the vignette's context
    - note: optional annotation or reason for inclusion

    Vignettes are referenced in person and theme pages as curated narrative fragments.
    """

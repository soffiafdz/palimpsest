#!/usr/bin/env python3
"""
wiki
----
Wiki generation system for Palimpsest.

Generates navigable markdown wiki pages from the SQLAlchemy database,
with bidirectional sync for manuscript pages and Quartz static site
publishing. The wiki serves as both a Vimwiki navigation interface
and a source-of-truth editing surface for manuscript content.

Key Components:
    - WikiRenderer: Jinja2 template engine with custom filters
    - WikiContextBuilder: DB queries → template context dicts
    - WikiExporter: Orchestrates generation of all wiki pages
    - WikiValidator: Structured diagnostics for wiki linting
    - WikiParser: Markdown → DB ingestion for manuscript pages
    - WikiSync: Validate → ingest → regenerate cycle
    - WikiPublisher: Copy wiki to Quartz with frontmatter injection

Usage:
    from dev.wiki.renderer import WikiRenderer
    from dev.wiki.filters import wikilink, date_long

    renderer = WikiRenderer()
    html = renderer.render("journal/entry.jinja2", context)
"""

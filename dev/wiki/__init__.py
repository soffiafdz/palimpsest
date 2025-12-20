#!/usr/bin/env python3
"""
__init__.py
-----------
Wiki generation system using Jinja2 templates.

This module replaces the wiki dataclass system with a simpler
template-based approach that passes ORM objects directly to Jinja2.

Components:
    - WikiRenderer: Jinja2-based template renderer
    - WikiExporter: Database to wiki export functionality
    - Entity configs: Query and output configurations per entity type
"""
from .renderer import WikiRenderer
from .exporter import WikiExporter

__all__ = ["WikiRenderer", "WikiExporter"]

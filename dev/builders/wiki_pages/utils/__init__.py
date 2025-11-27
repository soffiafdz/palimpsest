"""
Wiki Pages Utilities
---------------------

Shared utilities for wiki page builders.

Modules:
    - charts: ASCII visualization generators
    - queries: Database query helpers
    - formatters: Text and link formatting utilities
"""
from .charts import (
    ascii_bar_chart,
    ascii_bar_chart_sorted,
    intensity_indicator,
    monthly_heatmap,
    yearly_bar_chart,
)
from .queries import (
    get_all_entries,
    get_entry_statistics,
    get_people_statistics,
    get_location_statistics,
    get_tag_statistics,
    get_event_count,
    get_theme_count,
    get_top_entities,
)
from .formatters import (
    format_entity_link,
    format_date_link,
    format_count,
    format_percentage,
    format_word_count,
    format_date_range,
    format_days_span,
)

__all__ = [
    # Charts
    "ascii_bar_chart",
    "ascii_bar_chart_sorted",
    "intensity_indicator",
    "monthly_heatmap",
    "yearly_bar_chart",
    # Queries
    "get_all_entries",
    "get_entry_statistics",
    "get_people_statistics",
    "get_location_statistics",
    "get_tag_statistics",
    "get_event_count",
    "get_theme_count",
    "get_top_entities",
    # Formatters
    "format_entity_link",
    "format_date_link",
    "format_count",
    "format_percentage",
    "format_word_count",
    "format_date_range",
    "format_days_span",
]

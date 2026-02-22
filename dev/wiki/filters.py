#!/usr/bin/env python3
"""
filters.py
----------
Custom Jinja2 filters for wiki template rendering.

Pure, stateless functions that transform data for markdown output.
No database access, no side effects. Each filter handles a specific
formatting concern used across multiple wiki page templates.

Key Features:
    - Wikilink generation with optional display text
    - Date formatting (long form, ranges, flexible dates)
    - List formatting (mid-dot join, adaptive inline/bulleted)
    - Timeline table generation for monthly entry distributions
    - Source path computation for journal/metadata file links

Usage:
    from dev.wiki.filters import wikilink, date_long, mid_dot_join

    # wikilink uses @pass_environment; env is injected by Jinja2.
    # When called from templates: {{ "Clara Dupont" | wikilink }}
    # Resolves via _wikilink_targets dict in env.globals.
    date_long(date(2024, 11, 8))      # "Friday, November 8, 2024"
    mid_dot_join(["A", "B", "C"])     # "A · B · C"
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import calendar
from datetime import date
from typing import Any, Dict, List, Optional

# --- Third-party imports ---
from jinja2 import Environment, pass_environment

# --- Local imports ---
from dev.core.paths import (
    MD_DIR,
    JOURNAL_YAML_DIR,
    PEOPLE_YAML_DIR,
    LOCATIONS_YAML_DIR,
    CITIES_YAML_PATH,
    ARCS_YAML_PATH,
    MANUSCRIPT_CHAPTERS_DIR,
    MANUSCRIPT_CHARACTERS_DIR,
    MANUSCRIPT_SCENES_DIR,
)


@pass_environment
def entry_date_short(env: Environment, date_str: str) -> str:
    """
    Generate a wikilink for an entry date with short display text.

    Produces ``[Mar 13][/journal/entries/2025/2025-03-13]`` instead of
    ``[2025-03-13][/journal/entries/2025/2025-03-13]``. Used inside
    the entry_listing macro where year context is already established
    by the heading, so the full ISO date would be redundant.

    Args:
        env: Jinja2 Environment (injected by ``@pass_environment``)
        date_str: ISO date string in YYYY-MM-DD format

    Returns:
        WikiLink1 string with abbreviated month-day display,
        or ``[date_str][]`` as fallback when target is not resolved
    """
    targets = env.globals.get("_wikilink_targets", {})
    target = targets.get(date_str)
    parts = date_str.split("-")
    if len(parts) == 3:
        month_abbr = calendar.month_abbr[int(parts[1])]
        display = f"{month_abbr} {int(parts[2])}"
    else:
        display = date_str
    if target:
        return f"[{display}][{target}]"
    return f"[{date_str}][]"


@pass_environment
def entry_date_display(env: Environment, date_str: str) -> str:
    """
    Generate a wikilink for an entry date with full human-readable display.

    Produces ``[Jun 30, 2025][/journal/entries/2025/2025-06-30]`` instead
    of raw ISO. Used on pages without year-heading context (poems index,
    standalone references) where the year must be visible.

    Args:
        env: Jinja2 Environment (injected by ``@pass_environment``)
        date_str: ISO date string in YYYY-MM-DD format

    Returns:
        WikiLink1 string with full human-readable date display,
        or ``[date_str][]`` as fallback when target is not resolved
    """
    targets = env.globals.get("_wikilink_targets", {})
    target = targets.get(date_str)
    display = flexible_date_display(date_str)
    if target:
        return f"[{display}][{target}]"
    return f"[{date_str}][]"


@pass_environment
def wikilink(
    env: Environment, name: str, display: Optional[str] = None,
) -> str:
    """
    Generate a markdown-style wikilink with absolute path resolution.

    Vimwiki in markdown mode uses WikiLink1 format
    (``[Description][URL]``) for proper syntax concealment. The
    ``[[URL|Description]]`` format (WikiLink0) is not concealed
    in markdown syntax, making pages unreadable.

    Looks up the target name in a global ``_wikilink_targets`` dict
    injected into the Jinja2 environment. If found, produces
    ``[Display Name][/path/to/slug]``. Falls back to ``[name][]``
    when the name is not in the lookup table.

    Note:
        Wikilinks must NOT be wrapped in ``**...**`` bold markers.
        Bold around ``[Display][URL]`` breaks vimwiki concealment,
        and bold inside ``[**Display**][URL]`` renders literal
        asterisks. Use heading syntax for emphasis instead.

    Args:
        env: Jinja2 Environment (injected by ``@pass_environment``)
        name: Target page name / display name to resolve
        display: Optional alternate display text

    Returns:
        WikiLink1 string ``[display][target]`` if resolved,
        or ``[name][]`` as fallback
    """
    targets = env.globals.get("_wikilink_targets", {})
    target = targets.get(name)
    display_text = display or name
    if target:
        return f"[{display_text}][{target}]"
    return f"[{name}][]"


def date_long(d: date) -> str:
    """
    Format a date in long human-readable form.

    Args:
        d: Date to format

    Returns:
        Formatted string like "Friday, November 8, 2024"
    """
    return d.strftime("%A, %B %-d, %Y")


def date_range(start: date, end: date) -> str:
    """
    Format a date range as abbreviated month-year span.

    If both dates are in the same month and year, returns a single
    month-year. Otherwise returns "Mon YYYY – Mon YYYY".

    Args:
        start: Range start date
        end: Range end date

    Returns:
        Formatted range like "Nov 2024 – Jan 2025" or "Nov 2024"
    """
    start_str = start.strftime("%b %Y")
    end_str = end.strftime("%b %Y")
    if start_str == end_str:
        return start_str
    return f"{start_str} – {end_str}"


def mid_dot_join(items: List[str]) -> str:
    """
    Join items with middle dot separator.

    Args:
        items: Strings to join

    Returns:
        Items joined with " · " separator, or empty string if no items
    """
    return " · ".join(items)


def adaptive_list(items: List[str], threshold: int = 4) -> str:
    """
    Format a list inline or bulleted based on item count.

    Short lists (at or below threshold) render inline with mid-dot
    separators. Longer lists render as markdown bulleted list.

    Args:
        items: Strings to format
        threshold: Maximum items for inline rendering (default 4)

    Returns:
        Inline mid-dot string or bulleted markdown list
    """
    if not items:
        return ""
    if len(items) <= threshold:
        return mid_dot_join(items)
    return "\n".join(f"- {item}" for item in items)


def month_display(months: List[Dict[str, Any]], chunk_size: int = 6) -> str:
    """
    Format month counts inline, split into rows for readability.

    Takes a list of month dicts (name + count) and renders them
    inline with mid-dot separators, splitting into rows of
    ``chunk_size`` months for years with many active months.

    Args:
        months: List of dicts with ``name`` (str) and ``count`` (int)
        chunk_size: Maximum months per row (default 6, i.e. semesters)

    Returns:
        One or more lines of inline month counts, e.g.::

            **Jan** 6 · **Feb** 11 · **Mar** 24
            **Apr** 25 · **May** 23 · **Jun** 12
    """
    if not months:
        return ""
    chunks = [months[i:i + chunk_size]
              for i in range(0, len(months), chunk_size)]
    lines = []
    for chunk in chunks:
        items = [f"**{m['name']}** {m['count']:02d}" for m in chunk]
        lines.append(" · ".join(items))
    return "\n".join(lines)


def timeline_table(monthly_counts: Dict[str, int]) -> str:
    """
    Generate a markdown table showing monthly entry distribution.

    Expects keys in "YYYY-MM" format. Produces a table with years as
    rows, months as columns, and yearly totals. Months with zero entries
    show "—".

    Args:
        monthly_counts: Mapping of "YYYY-MM" → entry count

    Returns:
        Complete markdown table string, or empty string if no data

    Notes:
        - Future months in the current year show empty cells
        - No bold formatting (breaks vimwiki concealment alignment)
    """
    if not monthly_counts:
        return ""

    # Determine year range
    years = sorted({int(k[:4]) for k in monthly_counts})
    if not years:
        return ""

    month_abbrs = [calendar.month_abbr[m] for m in range(1, 13)]
    cw = 4  # cell width — fits 2-digit counts, keeps table compact

    # Header
    lines = []
    header = "| Year |" + "|".join(
        m.center(cw) for m in month_abbrs
    ) + "| Total |"
    separator = "|-----:|" + "|".join(
        ":" + "-" * (cw - 2) + ":" for _ in range(12)
    ) + "|------:|"
    lines.append(header)
    lines.append(separator)

    today = date.today()

    for year in years:
        row_counts = []
        for month in range(1, 13):
            key = f"{year}-{month:02d}"
            count = monthly_counts.get(key, 0)
            row_counts.append(count)

        year_total = sum(row_counts)

        cells = []
        for month_idx, count in enumerate(row_counts):
            month_num = month_idx + 1
            if count == 0:
                if year == today.year and month_num > today.month:
                    cells.append(" " * cw)
                else:
                    cells.append("—".center(cw))
            else:
                cells.append(f"{count:02d}".center(cw))

        row = f"| {year} |" + "|".join(cells) + f"|  {year_total:03d}  |"
        lines.append(row)

    return "\n".join(lines)


def source_path(entity_type: str, identifier: str) -> str:
    """
    Compute path to source file for a given entity.

    Uses absolute filesystem paths with ``file:`` scheme so vimwiki
    opens the file directly without appending ``.md`` or resolving
    relative to the wiki root.

    Args:
        entity_type: One of "journal_md", "metadata_yaml",
            "person_yaml", "location_yaml", "city_yaml", "arc_yaml",
            "chapter_yaml", "character_yaml", "scene_yaml"
        identifier: Entity-specific identifier (date string, slug,
            or city_slug/loc_slug for locations)

    Returns:
        ``file:`` URI with absolute filesystem path, or empty string
        for unknown entity types
    """
    if entity_type == "journal_md":
        year = identifier[:4]
        return f"file:{MD_DIR / year / f'{identifier}.md'}"
    elif entity_type == "metadata_yaml":
        year = identifier[:4]
        return f"file:{JOURNAL_YAML_DIR / year / f'{identifier}.yaml'}"
    elif entity_type == "person_yaml":
        return f"file:{PEOPLE_YAML_DIR / f'{identifier}.yaml'}"
    elif entity_type == "location_yaml":
        return f"file:{LOCATIONS_YAML_DIR / f'{identifier}.yaml'}"
    elif entity_type == "city_yaml":
        return f"file:{CITIES_YAML_PATH}"
    elif entity_type == "arc_yaml":
        return f"file:{ARCS_YAML_PATH}"
    elif entity_type == "chapter_yaml":
        return f"file:{MANUSCRIPT_CHAPTERS_DIR / f'{identifier}.yaml'}"
    elif entity_type == "character_yaml":
        return f"file:{MANUSCRIPT_CHARACTERS_DIR / f'{identifier}.yaml'}"
    elif entity_type == "scene_yaml":
        return f"file:{MANUSCRIPT_SCENES_DIR / f'{identifier}.yaml'}"
    return ""


def flexible_date_display(date_str: str) -> str:
    """
    Format a flexible date string (YYYY, YYYY-MM, or YYYY-MM-DD)
    into a human-readable display.

    Handles approximate dates prefixed with "~".

    Args:
        date_str: Flexible date string

    Returns:
        Human-readable date like "Nov 8, 2024", "Nov 2024",
        "2024", or "~Nov 2024"
    """
    is_approx = date_str.startswith("~")
    clean = date_str.lstrip("~")
    prefix = "~" if is_approx else ""

    parts = clean.split("-")
    if len(parts) == 3:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        d = date(year, month, day)
        return f"{prefix}{d.strftime('%b %-d, %Y')}"
    elif len(parts) == 2:
        year, month = int(parts[0]), int(parts[1])
        month_name = calendar.month_abbr[month]
        return f"{prefix}{month_name} {year}"
    else:
        return f"{prefix}{clean}"


def thread_date_range(from_date: str, to_date: str) -> str:
    """
    Format a thread's from→to date range for display.

    Uses flexible_date_display for each endpoint.

    Args:
        from_date: Thread proximate moment (flexible format)
        to_date: Thread distant moment (flexible format)

    Returns:
        Formatted range like "Nov 8, 2024 → Dec 2024"
    """
    from_display = flexible_date_display(from_date)
    to_display = flexible_date_display(to_date)
    return f"{from_display} → {to_display}"


def chunked_list(items: List[str], chunk_size: int = 3) -> List[List[str]]:
    """
    Split a list into chunks for bulleted sub-grouping.

    Used for scenes with many people (5+), where people are displayed
    in bulleted groups of 3-4 per line.

    Args:
        items: Items to chunk
        chunk_size: Items per chunk (default 3)

    Returns:
        List of lists, each containing up to chunk_size items
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def zpad(value: int) -> str:
    """
    Zero-pad an integer to at least two digits.

    Produces uniform-width counts for inline displays:
    1 → "01", 9 → "09", 12 → "12", 100 → "100".

    Args:
        value: Integer count to format

    Returns:
        Zero-padded string, minimum two characters wide
    """
    return f"{value:02d}"

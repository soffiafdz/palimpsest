"""
Formatting Utilities
--------------------

Helper functions for formatting links, dates, and text.

Functions:
    - format_entity_link: Format wikilink to entity
    - format_date_link: Format wikilink to date
    - format_count: Format count with label
    - format_percentage: Format percentage
"""

from typing import Optional
from datetime import date
from dev.utils.md import relative_link


def format_entity_link(
    name: str,
    entity_type: str,
    wiki_dir,
    journal_dir,
) -> str:
    """
    Format a wikilink to an entity.

    Args:
        name: Entity name
        entity_type: Type of entity (person, tag, location, etc.)
        wiki_dir: Wiki root directory
        journal_dir: Journal directory

    Returns:
        Formatted wikilink string
    """
    # Map entity type to subdirectory
    type_map = {
        "person": "people",
        "people": "people",
        "tag": "tags",
        "tags": "tags",
        "location": "locations",
        "locations": "locations",
        "city": "cities",
        "cities": "cities",
        "event": "events",
        "events": "events",
        "theme": "themes",
        "themes": "themes",
    }

    subdir = type_map.get(entity_type.lower(), entity_type)
    return relative_link(wiki_dir / subdir / f"{name}.md", wiki_dir, journal_dir)


def format_date_link(
    entry_date: date,
    wiki_dir,
    journal_dir,
) -> str:
    """
    Format a wikilink to a date-based entry.

    Args:
        entry_date: Entry date
        wiki_dir: Wiki root directory
        journal_dir: Journal directory

    Returns:
        Formatted wikilink string
    """
    year = entry_date.year
    month = f"{entry_date.month:02d}"
    day_file = f"{entry_date.isoformat()}.md"

    return relative_link(
        wiki_dir / str(year) / month / day_file,
        wiki_dir,
        journal_dir,
    )


def format_count(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    Format count with label.

    Args:
        count: The count value
        singular: Singular form of label
        plural: Plural form of label (default: singular + 's')

    Returns:
        Formatted count string

    Example:
        >>> format_count(1, "entry")
        '1 entry'
        >>> format_count(5, "entry")
        '5 entries'
        >>> format_count(1, "person", "people")
        '1 person'
    """
    if plural is None:
        plural = f"{singular}s"

    label = singular if count == 1 else plural
    return f"{count} {label}"


def format_percentage(value: float, total: float, decimals: int = 1) -> str:
    """
    Format percentage.

    Args:
        value: Numerator value
        total: Denominator value
        decimals: Number of decimal places

    Returns:
        Formatted percentage string

    Example:
        >>> format_percentage(25, 100)
        '25.0%'
        >>> format_percentage(1, 3, 2)
        '33.33%'
    """
    if total == 0:
        return "0.0%"

    pct = (value / total) * 100
    return f"{pct:.{decimals}f}%"


def format_word_count(words: int) -> str:
    """
    Format word count with commas.

    Args:
        words: Word count

    Returns:
        Formatted word count string

    Example:
        >>> format_word_count(1000)
        '1,000'
        >>> format_word_count(1500000)
        '1,500,000'
    """
    return f"{words:,}"


def format_date_range(start_date: date, end_date: date) -> str:
    """
    Format date range.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Formatted date range string

    Example:
        >>> from datetime import date
        >>> format_date_range(date(2020, 1, 1), date(2024, 12, 31))
        '2020-01-01 to 2024-12-31'
    """
    return f"{start_date.isoformat()} to {end_date.isoformat()}"


def format_days_span(start_date: date, end_date: date) -> str:
    """
    Format days span between two dates.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Formatted days span string

    Example:
        >>> from datetime import date
        >>> format_days_span(date(2020, 1, 1), date(2020, 1, 31))
        '30 days'
    """
    days = (end_date - start_date).days
    return format_count(days, "day")

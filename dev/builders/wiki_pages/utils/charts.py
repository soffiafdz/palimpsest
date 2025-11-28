"""
ASCII Chart Utilities
----------------------

Reusable functions for generating ASCII-based visualizations.

Functions:
    - ascii_bar_chart: Generate horizontal bar chart
    - monthly_heatmap: Generate monthly activity heatmap
    - intensity_indicator: Get intensity indicator for counts
"""

from typing import Dict, List, Optional
import calendar


def ascii_bar_chart(
    data: Dict[str, int],
    max_width: int = 20,
    empty_char: str = "░",
    fill_char: str = "█",
    show_percentage: bool = False,
) -> List[str]:
    """
    Generate ASCII bar chart lines from data.

    Args:
        data: Dictionary of label -> count
        max_width: Maximum bar width in characters
        empty_char: Character for empty/zero values
        fill_char: Character for filled space
        show_percentage: Include percentage in output

    Returns:
        List of formatted chart lines

    Example:
        >>> data = {"Jan": 10, "Feb": 5, "Mar": 15}
        >>> lines = ascii_bar_chart(data)
        >>> for line in lines:
        ...     print(line)
        Jan          ████████████        (10)
        Feb          ██████              (5)
        Mar          ████████████████████ (15)
    """
    if not data:
        return []

    max_count = max(data.values()) if data else 1
    total = sum(data.values())
    lines = []

    for label, count in data.items():
        if max_count > 0:
            bar_length = int((count / max_count) * max_width)
            bar = fill_char * bar_length if bar_length > 0 else empty_char
        else:
            bar = empty_char

        if show_percentage and total > 0:
            pct = (count / total) * 100
            lines.append(f"{label:12s} {bar:{max_width}s} {count:3d} ({pct:.1f}%)")
        else:
            lines.append(f"{label:12s} {bar:{max_width}s} ({count})")

    return lines


def ascii_bar_chart_sorted(
    data: Dict[str, int],
    max_width: int = 20,
    fill_char: str = "█",
    sort_by: str = "value",
    reverse: bool = True,
) -> List[str]:
    """
    Generate sorted ASCII bar chart.

    Args:
        data: Dictionary of label -> count
        max_width: Maximum bar width in characters
        fill_char: Character for filled space
        sort_by: Sort by 'key' or 'value'
        reverse: Reverse sort order

    Returns:
        List of formatted chart lines sorted by key or value
    """
    if not data:
        return []

    if sort_by == "key":
        sorted_items = sorted(data.items(), key=lambda x: x[0], reverse=reverse)
    else:
        sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=reverse)

    sorted_data = dict(sorted_items)
    return ascii_bar_chart(sorted_data, max_width=max_width, fill_char=fill_char)


def intensity_indicator(count: int, thresholds: Optional[List[int]] = None) -> str:
    """
    Get intensity indicator based on count.

    Args:
        count: Value to categorize
        thresholds: List of thresholds [low, medium, high]. Default: [0, 2, 5]

    Returns:
        Intensity indicator string

    Example:
        >>> intensity_indicator(0)
        '░░░'
        >>> intensity_indicator(3)
        '▒▒▒'
        >>> intensity_indicator(6)
        '▓▓▓'
        >>> intensity_indicator(10)
        '███'
    """
    if thresholds is None:
        thresholds = [0, 2, 5]

    if count == 0:
        return "░░░"
    elif count <= thresholds[1]:
        return "▒▒▒"
    elif count <= thresholds[2]:
        return "▓▓▓"
    else:
        return "███"


def monthly_heatmap(
    entries_by_month: Dict[str, int],
    start_year: int,
    end_year: int,
    entries_per_row: int = 12,
) -> List[str]:
    """
    Generate monthly activity heatmap.

    Args:
        entries_by_month: Dictionary of "YYYY-MM" -> count
        start_year: First year to display
        end_year: Last year to display
        entries_per_row: Number of months per row (default: 12)

    Returns:
        List of heatmap lines

    Example:
        >>> data = {"2024-01": 5, "2024-02": 10, "2024-03": 2}
        >>> lines = monthly_heatmap(data, 2024, 2024)
    """
    lines = []

    for year in range(start_year, end_year + 1):
        year_lines = []
        months_list = []

        for month in range(1, 13):
            month_key = f"{year}-{month:02d}"
            months_list.append((month_key, year, month))

        # Process in rows
        for i in range(0, len(months_list), entries_per_row):
            row_months = months_list[i : i + entries_per_row]

            # Month abbreviations row
            month_names = [calendar.month_abbr[m[2]] for m in row_months]
            year_lines.append(
                f"{year}: " + " ".join(f"{name:>3s}" for name in month_names)
            )

            # Intensity indicators row
            intensities = [
                intensity_indicator(entries_by_month.get(m[0], 0)) for m in row_months
            ]
            year_lines.append("      " + " ".join(intensities))

        lines.extend(year_lines)
        lines.append("")  # Blank line between years

    return lines


def yearly_bar_chart(
    entries_by_year: Dict[int, int],
    max_width: int = 50,
    fill_char: str = "█",
    show_words: bool = False,
    word_count_by_year: Optional[Dict[int, int]] = None,
) -> List[str]:
    """
    Generate yearly bar chart with optional word counts.

    Args:
        entries_by_year: Dictionary of year -> entry count
        max_width: Maximum bar width
        fill_char: Character for filled space
        show_words: Whether to show word counts
        word_count_by_year: Optional dictionary of year -> word count

    Returns:
        List of formatted chart lines
    """
    if not entries_by_year:
        return []

    lines = []
    max_count = max(entries_by_year.values())

    for year in sorted(entries_by_year.keys()):
        count = entries_by_year[year]
        bar_length = int((count / max_count) * max_width) if max_count > 0 else 0
        bar = fill_char * bar_length

        if show_words and word_count_by_year:
            words = word_count_by_year.get(year, 0)
            lines.append(f"{year}: {bar} {count} entries ({words:,} words)")
        else:
            lines.append(f"{year}: {bar} ({count} entries)")

    return lines

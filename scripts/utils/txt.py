"""
txt_utils.py
-------------------
Set of utilities for parsing, formatting, and modifying text documents.

It is designed to work with the txt compilation documents
exported by the 750words website and used in the Palimpsest project.

Intended to be imported by the txt2md workflow.
"""

from __future__ import annotations

# --- Standard library imports ---
from textwrap import TextWrapper
from typing import List, Tuple

# --- Third-party library imports ---
from textstat import lexicon_count  # type: ignore


# ----- Ordinal dates -----
def ordinal(n: int) -> str:
    """
    input: n, an integer day of month
    output: the number with its ordinal suffix ("st", "nd", "rd", "th")
    process: handles English ordinal rules
    """
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    if n % 10 == 1:
        return f"{n}st"
    if n % 10 == 2:
        return f"{n}nd"
    if n % 10 == 3:
        return f"{n}rd"
    return f"{n}th"


# ----- Format body of text -----
def format_body(lines: List[str]) -> List[Tuple[str, bool]]:
    """
    input: lines, list of raw body lines (strings)
    output: list of (line_text, is_soft_break) tuples.
      - leading/trailing whitespace stripped
      - soft-break lines (ending in '\\') preserved verbatim
      - blank lines preserved
    process:
      * For each line, strip newline; detect if it ends with backslash
      * If so, append it unchanged (soft-hard break in Markdown)
      * Otherwise, trim spaces/tabs on both ends
      * Pass through blank lines and content lines for later paragraphing
    """
    out: List[Tuple[str, bool]] = []
    prev_blank: bool = False

    for raw in lines:
        ln: str = raw.rstrip("\n")

        # soft-break marker (single backslash)
        soft_break: bool = ln.rstrip().endswith("\\")
        if soft_break:
            ln = ln.rstrip()[:-1].rstrip()

        # trim whitespace
        ln = ln.strip()

        # blank line
        if ln == "":
            if not prev_blank:
                out.append(("", False))
                prev_blank = True
        else:
            out.append((ln, soft_break))
            prev_blank = False
    return out


# ----- Wrap entry -> <80 chars -----
def reflow_paragraph(paragraph: List[str], width: int = 80) -> List[str]:
    """
    input: paragraph, a list of lines (strings) without blank lines
    output: list of wrapped lines at most `width` characters
    process: joins the lines with spaces, then uses textwrap
    """
    text: str = " ".join(paragraph)
    wrapper = TextWrapper(
        width=width,
        replace_whitespace=False,
        drop_whitespace=True,
    )
    return wrapper.wrap(text)


# ----- Word-count & ~reading time -----
def compute_metrics(lines: List[str]) -> Tuple[int, float]:
    """
    input: str, complete text for the entry
    output: EntryMetrics
        - word_count: int, number of words
        - reading_time_min: float, minutes to read
    """
    text = " ".join(line.strip() for line in lines)
    wc: int = lexicon_count(text, removepunct=True)
    # texstat.reading_time gives inflated result.
    # Calculate manually with 260 WPM
    rt: float = wc / 260
    return (wc, rt)

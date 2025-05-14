#!/usr/bin/env python3
"""
journal_txt_to_md.py

Convert pre-cleaned 750words .txt exports (monthly) into per-entry Markdown
files under source/<year>/ with rich metadata front-matter.
"""
import argparse
import re
import datetime
import textwrap
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

import ftfy
import textstat

ENTRY_MARKER_1 = "------ ENTRY ------"
ENTRY_MARKER_2 = "===== ENTRY ====="


@dataclass
class ParsedEntry:
    """
    header: human-readable title or formatted date
    body: list of lines after the metadata
    date: datetime.date parsed from metadata, or None
    """
    header: str
    body: List[str]
    date: Optional[datetime.date]


@dataclass
class EntryMetrics:
    """
    word_count: count of words in the entry
    reading_time_min: estimated reading time in minutes
    flesch_reading_ease: Flesch Reading Ease score (Easy: >80; Diff: <49)
    """
    word_count: int
    reading_time_min: float
    flesch_reading_ease: float


def ordinal(n: int) -> str:
    """
    input: n, an integer day of month
    output: the ordinal suffix for n ("st", "nd", "rd", "th")
    process: handles English ordinal rules
    """
    if 10 <= n % 100 <= 20:
        return "th"
    if n % 10 == 1:
        return "st"
    if n % 10 == 2:
        return "nd"
    if n % 10 == 3:
        return "rd"
    return "th"


def split_entries(lines: List[str]) -> List[List[str]]:
    """
    input: lines, a list of strings (each raw line from the .txt)
    output: a list of entries, where each entry is itself a list of lines
    process: splits on any line matching the two different ENTRY markers,
             discarding the marker lines and grouping surrounding lines
    """
    entries: List[List[str]] = []
    cur: List[str] = []
    marker = re.compile(
        rf"^(?:{re.escape(ENTRY_MARKER_1)}|{re.escape(ENTRY_MARKER_2)})\s*$"
    )
    for ln in lines:
        if marker.match(ln):
            if cur:
                entries.append(cur)
            cur = []
        else:
            cur.append(ln)
    if cur:
        entries.append(cur)
    return entries


def extract_date_and_body(entry: List[str]) -> ParsedEntry:
    """
    input: entry, a list of lines belonging to one journal entry
    output: ParsedEntry
        - header: a string, either TITLE or formatted DATE
        - body: list of lines after the metadata
        - date: (optional) datetime.date parsed from metadata
    Supports both:
        - === DATE: YYYY-MM-DD === / === TITLE: ... ===
        - Date: YYYY-MM-DD / Title : ...
    process:
        * Recognizes both Date & Title, in any order
        * If “=== BODY ===” marker exists, body starts after it
        * Otherwise, body starts after the first blank line following metadata
        * Formats header_text: TITLE if present, else “Day, DDth Month, YYYY”
    """
    title: Optional[str] = None
    date_obj: Optional[datetime.date] = None
    date_idx: Optional[int] = None
    body_start: Optional[int] = None

    for i, ln in enumerate(entry):
        # `= TITLE =` marker
        m: str = re.match(r"^===\s*TITLE:\s*(.+?)\s*===", ln)
        if m and title is None:
            title: str = m.group(1).strip()
            continue

        # `Title:` marker
        m: str = re.match(r"^Title:\s*(.+)$", ln)
        if m and title is None:
            title: str = m.group(1).strip()
            continue

        #  `= DATE =` marker
        m: str = re.match(r"^===\s*DATE:\s*(\d{4}-\d{2}-\d{2})\s*===", ln)
        if m and date_obj is None:
            date_obj: datetime.date = datetime.date.fromisoformat(m.group(1))
            date_idx: int = i
            continue

        # `Date:` marker
        m: str = re.match(r"^Date:\s*(\d{4}-\d{2}-\d{2})$", ln)
        if m and date_obj is None:
            date_obj: datetime.date = datetime.date.fromisoformat(m.group(1))
            date_idx: int = i
            continue

        # explicit BODY marker
        if ln.strip() == "=== BODY ===":
            body_start: int = i + 1
            break

    # if no BODY marker, find first blanl line after medatada block
    if body_start is None and date_idx is not None:
        for j in range(date_idx + 1, len(entry)):
            if entry[j].strip() == "":
                body_start: int = j + 1
                break

    # FALLBACK:
    # If no blankline, both legacy and new --- format ---:
    # have only `Words:` and `Minutes:` after the `Date:`
    if body_start is None:
        body_start: int = (date_idx + 3) if date_idx is not None else 0

    # build header
    if title:
        header_text: str = title
    elif date_obj:
        header_text: str = (
            f"{date_obj.strftime('%A')}, "
            f"{date_obj.day}{ordinal(date_obj.day)} "
            f"{date_obj.strftime('%B')}, {date_obj.year}"
        )
    else:
        header_text: str = "Unknown Date"

    body_lines: List[str] = entry[body_start:]
    return ParsedEntry(header_text, body_lines, date_obj)


def format_body(lines: List[str]) -> List[str]:
    """
    input: lines, list of raw body lines (strings)
    output: list of formatted lines with:
      - leading/trailing whitespace stripped
      - soft-break lines (ending in '\\') preserved verbatim
      - blank lines preserved
    process:
      * For each line, strip newline; detect if it ends with backslash
      * If so, append it unchanged (soft-hard break in Markdown)
      * Otherwise, trim spaces/tabs on both ends
      * Pass through blank lines and content lines for later paragraphing
    """
    out: List[str] = []
    for raw in lines:
        ln: str = raw.rstrip("\n")

        # soft-break marker (single backslash)
        if ln.endswith("\\"):
            out.append(ln)
            continue

        # trim whitespace
        ln: str = re.sub(r"^[ \t]+", "", ln)
        ln: str = re.sub(r"[ \t]+$", "", ln)

        # blank line
        if ln == "":
            out.append("")
        else:
            out.append(ln)
    return out


def reflow_para(paragraph: List[str], width: int = 80) -> List[str]:
    """
    input: paragraph, a list of lines (strings) without blank lines
    output: list of wrapped lines at most `width` characters
    process: joins the lines with spaces, then uses textwrap
    """
    text: str = " ".join(paragraph)
    wrapper = textwrap.TextWrapper(
        width=width,
        replace_whitespace=False,
        drop_whitespace=True,
    )
    return wrapper.wrap(text)


def compute_metrics(text: str) -> EntryMetrics:
    """
    input: str, complete text for the entry
    output: EntryMetrics
        - word_count: int, number of words
        - reading_time_min: float, minutes to read
        - flesch_reading_ease: float, reading difficulty
    """
    wc: int = textstat.lexicon_count(text, removepunct=True)
    rt: float = textstat.reading_time(text, ms_per_char=14.69)
    fe: float = textstat.flesch_reading_ease(text)
    return EntryMetrics(wc, rt, fe)


def main() -> None:
    """
    CLI entrypoint:
      - parses --input and --output arguments
      - reads and ftfy-cleans the input file
      - splits into entries, extracts headers & bodies
      - formats bodies, groups into paragraphs
      - reflows prose paras, preserves soft-break paras
      - calculates metadata
      - writes the resulting Markdown to output
    """
    # --- ARGUMENTS ---
    p = argparse.ArgumentParser(
        description="Convert pre-cleaned .txt into per-entry Markdown files"
    )
    p.add_argument(
        "-i", "--input", required=True,
        help="path to pre-cleaned .txt file"
    )
    p.add_argument(
        "-o", "--output", required=True,
        help="root directory under which to write <year>/YYYY-MM-DD.md"
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="print progress messages"
    )
    p.add_argument(
        "-f", "--clobber", action="store_true",
        help="overwrite existing markdown files (default: error if file exists)"
    )
    args = p.parse_args()

    in_path = Path(args.input)
    out_root = Path(args.output)
    if args.verbose:
        print(f"Reading input file: {in_path}")
        print(f"Output root directory: {out_root}")


    # --- FAILSAFES ---
    if not in_path.exists():
        sys.stderr.write(f"Error: input not found: {in_path}\n")
        sys.exit(1)
    if not in_path.is_file() or not os.access(in_path, os.R_OK):
        sys.stderr.write(f"Error: cannot read input file: {in_path}\n")
        sys.exit(1)
    try:
        out_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        sys.stderr.write(f"Error creating output dir {out_root}: {e}\n")
        sys.exit(1)
    if not out_root.is_dir() or not os.access(out_root, os.W_OK):
        sys.stderr.write(f"Error: cannot write to {out_root}\n")
        sys.exit(1)

    # --- PROCESS ---
    if args.verbose:
        print("Cleaning text and splitting into entries...")

    raw: str = ftfy.fix_text(in_path.read_text(encoding="utf-8"))
    entries: List[List[str]] = split_entries(raw.splitlines())
    if args.verbose:
        print(f"Found {len(entries)} entries")

    for entry_block in entries:
        parsed: ParsedEntry = extract_date_and_body(entry_block)
        if args.verbose:
            print(f"Processing entry dated {parsed.date.isoformat()}")

        if parsed.date is None:
            sys.stderr.write("Warning: skipping entry with no date\n")
            continue

        # Compute metrics
        blob: str = "\n".join(parsed.body)
        metrics: EntryMetrics = compute_metrics(blob)

        # Build YAML front-matter
        iso: str = parsed.date.isoformat()
        weekday: str = parsed.date.strftime("%A")
        fm: str = textwrap.dedent(f"""\
        ---
        date: {iso}
        day_of_week: {weekday}
        word_count: {metrics.word_count}
        reading_time: {metrics.reading_time_min:.1f}
        reading_ease: {metrics.flesch_reading_ease:.1f}
        status: source
        people:
        tags:
        ---
        """).rstrip()

        # Format and reflow body
        formatted: List[str] = format_body(parsed.body)
        paras: List[List[str]] = []
        buf: List[str] = []
        for ln in formatted + [""]:
            if ln == "":
                if buf:
                    paras.append(buf)
                    buf = []
            else:
                buf.append(ln)

        md_lines: List[str] = []
        md_lines.append(fm)
        md_lines.append("")
        md_lines.append(f"## {parsed.header}")
        md_lines.append("")

        for para in paras:
            # if any line ends with '\' → emit raw for hard-breaks
            if any(l.endswith("\\") for l in para):
                for l in para:
                    md_lines.extend(para)
            else:
                # normal prose → wrap to 80 cols
                md_lines.extend(reflow_para(para))
            md_lines.append("")  # blank line after each paragraph

        # --- OUTPUT ---
        # Write to {}out_root}/<year>/YYYY-MM-DD.md
        year_dir: Path = out_root / str(parsed.date.year)
        year_dir.mkdir(exist_ok=True)
        out_file: Path = year_dir / f"{iso}.md"

        if out_file.exists() and not args.clobber:
            sys.stderr.write(f"Warning: {out_file} already exists, skipping\n")
            continue

        if args.verbose:
            action = "Overwriting" if out_file.exists() else "Writing"
            print(f"{action} file: {out_file}")

        try:
            out_file.write_text("\n".join(md_lines), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"Error writing to {out_file}: {e}\n")
            sys.exit(1)


if __name__ == "__main__":
    main()

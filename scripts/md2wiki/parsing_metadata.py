#!/usr/bin/env python3
"""
parsing_metadata.py
-------------------
Scan Markdown diary entries with YAML front‑matter
Generate Vimwiki dashboards:

    vimwiki/
    ├── inventory.md           (2024 & 2025 inline, archive links)
    ├── inventory/YYYY.md
    ├── people.md
    ├── people/person.md
    ├── tags.md
    ├── themes.md
    ├── notes.md
    └── notes/YYYY.md

Notes
==============
- Compares scanned metadata with existing Vimwiki pages.
- Rewrites only when content has changed.
- 2024 & 2025 entries are shown inline;
- Older entries (arhive) are on inventory/YYYY.md
"""
from __future__ import annotations

# --- Standard Library ---
import argparse
import os
import re
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import unified_diff
from pathlib import Path
from typing import (
    Any, Dict, List, Optional, Pattern, Sequence, Set, Type, TypeVar
)

# --- Third-party ---
import yaml

# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------
@dataclass
class Person(WikiEntity):
    """
    - path:           Path to vimwiki file
    - name:           Person's real name
    - category:       Grouping
    - alias:          Person's alias(es)
    - mentions:       Number of entries they are mentioned
    - appearance(s):  Dictionary of appearances
        - date:       Date of entry
        - md:         Path to entry.md
        - link:       Relative path to md from person.md
        - note:       Note added to entry
    - themes:         themes they are included in
    - vignette(s):    Dictionary of vignettes
        - title:      Title of the vignette
        - md:         Path to entry.md
        - link:       Relative path to md from person.md
        - note:       Note added to the vignette
    - notes:          Notes for the person
    -
    """
    path:         Path
    name:         str
    category:     Optional[str]        = None
    alias:        List[str]            = field(default_factory = list)
    mentions:     int                  = 1
    appearances:  List[Dict[str, Any]] = field(default_factory = list)
    themes:       Set[str]             = field(default_factory = set)
    vignettes:    List[Dict[str, Any]] = field(default_factory = list)
    notes:        Optional[str]        = None


    # ---- Public constructors ----
    @classmethod
    def from_file(cls, path: Path) -> Optional["Person"]:
        """Parse a people/person.md file to create a Person object."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            sys.stderr.write(f"Error reading {path}: {e}\n")
            return None

        # --- Fallback ---
        name = path.stem.title()
        category = None
        themes = set()
        freq = 1
        first_date = last_date = None

        # --- Themes ---
        in_themes = False
        for ln in lines:
            if ln.startswith("## ") and not ln.startswith("###"):
                name = ln[3:].strip()
            elif ln.strip() == "### Category":
                idx = lines.index(ln)
                if idx + 1 < len(lines):
                    category = lines[idx + 1].strip()
            elif ln.strip() == "### Themes":
                in_themes = True
                continue
            elif in_themes:
                if ln.startswith("### "):
                    in_themes = False
                    continue
                if ln.strip().startswith("-"):
                    theme = ln.strip()[1:].strip()
                    if theme:
                        themes.add(theme)
            elif ln.strip().startswith("- Mentions:"):
                freq_str = ln.strip().split(":")[1].split()[0]
                try:
                    freq = int(freq_str)
                except ValueError:
                    freq = 1
            elif ln.strip().startswith("- Appearance:") or ln.strip().startswith("- Range:"):
                # Basic date parsing
                dates = [d.strip() for d in ln.split(":")[1].replace("->", "→").split("→")]
                try:
                    first_date = datetime.strptime(dates[0], "%Y-%m-%d").date()
                    if len(dates) > 1 and dates[1]:
                        last_date = datetime.strptime(dates[1], "%Y-%m-%d").date()
                    else:
                        last_date = first_date
                except Exception:
                    first_date = last_date = None

        return cls(
            path=path,
            name=name,
            freq=freq,
            category=category,
            themes=themes,
            first_date=first_date,
            last_date=last_date,
        )

    # ---- Serialization ----
    def to_wiki(self) -> List[str]:
        lines = [
            "# Palimpsest — People",
            "",
            f"## {self.name}",
            "",
            "### Category",
            f"{self.category or 'Unsorted'}",
            "",
            "### Themes"
        ]
        if self.themes:
            lines += [f"- {t}" for t in sorted(self.themes)]
        else:
            lines.append("- ")
        lines += [
            "",
            "### Presence"
        ]
        if self.first_date:
            if self.first_date == self.last_date or not self.last_date:
                lines.append(f"- Appearance: {self.first_date}")
            else:
                lines.append(f"- Range: {self.first_date} -> {self.last_date}")
        lines.append(f"- Mentions: {self.freq} {'entry' if self.freq == 1 else 'entries'}")
        lines.append("")
        lines.append("### Notes")
        lines.append(self.notes or "")
        lines.append("")
        return lines

    # ---- Static helper ----
    @staticmethod
    def parse_yaml_front_matter(path: Path) -> Dict[str, Any]:
        """Extract YAML front matter from a markdown file."""
        try:
            with path.open(encoding="utf-8") as fh:
                if fh.readline().rstrip() != "---":
                    return {}
                lines: List[str] = []
                for line in fh:
                    if line.rstrip() == "---":
                        break
                    lines.append(line)
                yaml_text: str = "".join(lines)
            return yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as exc:
            sys.stderr.write(f"[WARN] YAML error in {path.name}: {exc}\n")
            return {}
        except Exception as exc:
            sys.stderr.write(f"[WARN] Error reading YAML front matter in {path.name}: {exc}\n")
            return {}

    # ---- Private helper (for this class) ----
    def _parse_theme_block(self, lines: List[str]) -> Set[str]:
        """Extract themes from a section of lines."""
        themes = set()
        in_themes = False
        for ln in lines:
            if ln.strip() == "### Themes":
                in_themes = True
                continue
            if in_themes:
                if ln.startswith("### "):
                    break
                if ln.strip().startswith("-"):
                    theme = ln.strip()[1:].strip()
                    if theme:
                        themes.add(theme)
        return themes

# Usage Example:
# person = Person.from_file(Path("vimwiki/people/someone.md"))
# if person:
#     person.write_to_file()


    # # --- helper to fold YAML lists into the sets ---
    # def merge_meta(self, themes: Set, date: date, md: Path) -> None:
        # """Update this Person with Entry metadata."""

        # # --- themes ---
        # if bool(themes):
            # self.themes.update(themes)

        # # --- appearances ---
        # if self.first_date is None or self.last_date is None:
            # self.first_md   = md
            # self.last_md    = md
            # self.first_date = date
            # self.last_date  = date
        # else:
            # if date < self.first_date:
                # self.first_md   = md
                # self.first_date = date
            # if date > self.last_date:
                # self.last_md   = md
                # self.last_date = date


    # --- populate empty people/person.md ---
    def populate_wiki(self) -> None:
        """Write a new people/person.md from current Person metadata."""
        lines: List[str] = ["# Palimpsest — People", ""]
        # --- title ---
        lines.extend([f"## {self.name}", ""])
        # --- category ---
        lines.extend(["### Category", f"{self.category}", ""])
        # --- alias ---
        lines.extend(["### Alias(es)", "- ", ""])
        # --- presence ---
        lines.extend(["### Presence"])
        if self.freq == 1:
            lines.extend([
                f"- Appearance: {self.first_date}",
                f"- Mentions: {self.freq} entry",
                f"- Entry: [[{self.first_md}]] - {self.first_note or ''}",
                ""
            ])
        else:
            lines.extend([
                f"- Range: {self.first_date} -> {self.last_date}"
                f"- Mentions: {self.freq} entries",
                f"- First: [[{self.first_md}]] - {self.first_note or ''}",
                f"- Last: [[{self.last_md}]] - {self.last_note or ''}",
                ""
            ])
        # --- themes ---
        lines.extend(["### Themes"])
        if bool(self.themes):
            lines.extend([f"- {t}" for t in self.themes])
        else:
            lines.extend(["- "])
        # --- vignettes ---
        lines.extend(["### Vignettes", "- ", ""])
        # --- notes ---
        lines.extend(["### Notes"])

        # Create directory if necessary
        people_dir: Path = self.path.parent
        try:
            people_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            sys.stderr.write(
                f"Error creating People wiki directory {people_dir}: {e}\n"
            )
            sys.exit(1)

        # Populate file
        try:
            self.path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(
                f"Error writing {self.name} wiki entry: {e}\n"
            )
            sys.exit(1)


    # --- obtain category ---
    def get_category(self) -> None:
        """Look into people/person.md to extract person's category."""
        if not self.path.is_file():
            self.category = "Unsorted"

        CATEGORY_RE: Pattern[str] = re.compile(r"^### Category")
        lines: List[str] = self.path.read_text(encoding="utf-8").splitlines()
        cat: str | None = None
        found: bool = False

        for ln in lines:
            if found:
                self.category = ln.strip()
                break

            if m := CATEGORY_RE.match(ln):
                found = True

        if self.category is None:
            self.category = "Unsorted"


    # --- obtain themes ---
    def get_themes(path: Path) -> Optional[Set[str]]:
        """Look into people/person.md to extract person's themes data."""
        themes: Set[str] = set()
        lines: List[str] = path.read_text(encoding="utf-8").splitlines()
        in_themes: bool = False

        for ln in lines:
            if ln.strip() == "### Themes":
                in_themes = True
                continue
            if in_themes:
                if ln.startswith("### "):
                    break
                if ln.strip().startswith("-"):
                    theme = ln.strip()[1:].strip()
                    if theme:
                        themes.add(theme)

        return themes if themes else None


    # --- update themes ---
    def update_themes(self) -> None:
        """Update Mentions section if changed."""
        if not self.path.is_file():
            return

        if self.themes != self.get_themes():
            # TODO: Figure out how to update themes lines
            pass


    # --- obtain mentions ---
    def get_mentions(self) -> int:
        """Look into people/person.md; obtain Mentions value."""
        if not self.path.is_file():
            return 0

        MENTIONS_RE: Pattern[str] = re.compile(r"^- Mentions:\s*(\d+)")

        lines: List[str] = self.path.read_text(encoding="utf-8").splitlines()
        for ln in lines:
            if m := MENTIONS_RE.match(ln):
                return int(m.group(1))

        return 0


    # --- update mentions ---
    def update_mentions(self) -> None:
        """Update Mentions section if changed."""
        if not self.path.is_file():
            self.populate_wiki()
            return

        if self.freq != self.get_mentions():
            # TODO: Figure out how to update mentions line
            pass


    # --- obtain first/last metadata ---
    def get_first_last_dates(self) -> Optional[Dict[str, date]]:
        """Look into people/person.md; obtain First/Last appearances."""
        if not self.path.is_file():
            return None

        RANGE_RE: Pattern[str] = re.compile(
            r"^- (?:Appearance|Range):\s*"
            r"(?P<first>[0-9]{4}-[0-9]{2}-[0-9]{2})"    # first date
            r"(?:\s*(?:→|->)\s*"
            r"(?P<last>[0-9]{4}-[0-9]{2}-[0-9]{2}))?"   # optional second date
            r"$"
        )

        lines: List[str] = self.path.read_text(encoding="utf-8").splitlines()
        dates: Dict[str, date] = {}
        for ln in lines:
            if m := RANGE_RE.match(ln):
                fdate = datetime.strptime(m.group("first"), "%Y-%m-%d").date()
                ldate = datetime.strptime(m.group("last"), "%Y-%m-%d").date() \
                        if m.group("last") else fdate

                dates["first"] = fdate
                dates["last"] = ldate
                break

        return dates if dates else None


    def update_appearance(self, first_or_last: str, new_date: date) -> None:
        """Update either first or last appearance."""
        pass


# ------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------
# TODO: Check that these are correct
ROOT: Path = Path(__file__).resolve().parents[2]
SRC_DIR: Path = ROOT / "journal" / "md"
WIKI_DIR: Path = ROOT / "vimwiki"
INV_IDX: Path = WIKI_DIR / "inventory.md"
INV_DIR: Path = WIKI_DIR / "inventory"
PPL_IDX: Path = WIKI_DIR / "people.md"
PPL_DIR: Path = WIKI_DIR / "people"

INLINE_RULES: Dict[str, Set[str] | None] = {
    "2025": None,                       # whole current year
    "2024": {"November", "December"},   # init of winter
}

MONTH_ORDER = {
    m: i for i, m in enumerate(
        [
            "January","February","March","April","May","June","July",
            "August","September","October","November","December"
        ],
        1
    )
}

CATEGORY_ORDER = ["Main", "Secondary", "Archive", "Unsorted"]



# -------------------------------------------------------------------------
# Inventory
# -------------------------------------------------------------------------

# ----------  Inventory: read & parse  ------------------------------------
def parse_current_inventory() -> Dict[str, List[str]]:
    """
    Return {'top': lines_for_inventory_md, 'year': lines_for_year_md}.
    Missing files → empty lists.
    """
    out: Dict[str, List[str]] = {}
    main_file = WIKI_DIR / "inventory.md"
    out["top"] = main_file.read_text(encoding="utf-8").splitlines() \
            if main_file.exists() else []
    inv_dir = WIKI_DIR / "inventory"
    for y_path in (inv_dir.glob("20??.md") if inv_dir.exists() else []):
        out[y_path.stem] = y_path.read_text(encoding="utf-8").splitlines()
    return out


# ----------  Inline vs Archive  ------------------------------------------
def _show_inline(year: str, month: str) -> bool:
    """Filter main entries (2024-Nov -> Now) from archive."""
    rule = INLINE_RULES.get(year)
    if rule is None:        # 2025
        return True
    return month in rule    # 2024: Nov & Dec


# ----------  Create lines for inventory  ---------------------------------
def _inv_line(e: Entry) -> str:
    """Markdown bullet for one entry."""
    check: str = "x" if e.done else " "
    # TODO: Change link to have a pretty name
    return f"- [{check}] [[{e.path.name}]] — {e.status}"


# ----------  Inventory: read & parse  ------------------------------------
def render_month_blocks(
        items: Sequence[Entry],
        year: str,
        year_month: bool,
) -> List[str]:
    # TODO: Figure out if changing this
    """
    Return a list of markdown lines:
        ## Year: Month\n | ## Month\n
        - [] [[YYYY-MM-DD.md]] — status
    with months shown in reverse calendar order.
    """
    out: List[str] = []
    by_month: Dict[str, List[Entry]] = defaultdict(list)

    for e in items:
        by_month[e.month].append(e)

    for month in sorted(by_month, key=lambda m: MONTH_ORDER[m], reverse=True):
        if year_month:
            out.append(f"\n## {year}: {month}")
        else:
            out.append(f"\n### {month}")
        out.extend(_inv_line(e) for e in by_month[month])

    return out


# ----------  Inventory: render fresh  ------------------------------------
def render_inventory(entries: Sequence[Entry]) -> Dict[str, List[str]]:
    """Return a dict {filename_key: list_of_lines} ready to write."""
    inv_out: Dict[str, List[str]] = {}

    # --- archive vs main Years ---
    inline_years = INLINE_RULES.keys()  # 2024 & 2025
    older_years: Set[str] = {e.year for e in entries} - set(inline_years)

    # --- inventory.md ---
    main: List[str] = ["# Palimpsest — Inventory", ""]
    for y in sorted(inline_years, reverse=True):
        subset = [
            e for e in entries
            if e.year == y
            and _show_inline(e.year, e.month)
        ]

        if not subset:
            continue

        main += render_month_blocks(subset)
        main.append("")

    # --- archive links ---
    main += ["\n---\n", "## Archive"]
    for y in sorted(older_years, reverse=True):
        main.append(f"→ [[inventory/{y}.md]]")
    inv_out["top"] = main

    # --- yearly pages ---
    for y in older_years | {"2024"}:
        year_entries = [
            e for e in entries
            if e.year == y
            and not _show_inline(e.year, e.month)
        ]

        if not year_entries:
            continue

        header: List[str] = [
            "# Palimpsest — Inventory (Archive)", "",
            f"## : {y}", "",
        ]

        inv_out[y] = header + render_month_blocks(year_entries)

    return inv_out


# -------------------------------------------------------------------------
# People
# -------------------------------------------------------------------------

    # for person in people.values():
        # person.category = get_category(person.path) or "Unsorted"
        # categories[person.category].add(person.name)

    # for cat in CATEGORY_ORDER:
        # if not categories.get(cat):
            # continue

        # main.extend(["", f"## {cat}"])

        # # Sort people by presence
        # people = sorted(categories[cat], key=lambda p: p.freq, reverse=True)
        # for person in people:
            # main.append(f"→ [[people/{person.name.lower()}.md]]")


# ----------------------------------------------------------------------
# Only write if there is something to update
# ----------------------------------------------------------------------
def _write_if_changed(path: Path, new_lines: List[str], verbose: bool) -> None:
    old_lines: List[str] = path.read_text().splitlines() \
            if path.exists() else []
    if old_lines == new_lines:
        return  # no change
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines), encoding="utf-8")
    # Diff:
    if verbose:
        diff = unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            lineterm="",
        )
        # TODO: Remove emoji. Look for other scripts format.
        print(f"✎ updated {path.relative_to(ROOT)}")
        for line in diff:
            print(line)

# ----------------------------------------------------------------------
# Build dashboards
# ----------------------------------------------------------------------
def build_dashboards(entries: Sequence[Entry]) -> None:
    """
    Input:
        - Entries: Sequence of entries to be parsed
    Render & write:
        - Inventory
        - People
        - Themes
        - Tags
        - Notes
    """


    current = parse_current_inventory()
    fresh   = render_inventory(entries)

    # inventory.md
    _write_if_changed(WIKI_DIR / "inventory.md", fresh["top"])

    # yearly pages
    inv_dir = WIKI_DIR / "inventory"
    for y, lines in fresh.items():
        if y == "top":
            continue
        _write_if_changed(inv_dir / f"{y}.md", lines)

    # ---- TODO: repeat pattern for people/tags/themes/notes ----
    # parse_current_xx(), render_xx(), write_if_changed()
    # -----------------------------------------------------------


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync Vimwiki dashboards")
    # TODO: Arguments for specific things: inventory, people, etc.
    # TODO: Arguments for verbosity
    p.add_argument("--year", help="only process one year (e.g. 2025)")
    return p.parse_args()

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    args = parse_args()

    entries:  List[Entry]  = []
    people:   Dict[str, Person] = {}

    # Parse all Markdown files
    for md in sorted(SRC_DIR.rglob("20??-??-??.md")):

        # Date from filename as a backup
        md_date = datetime.strptime(md.stem, "%Y-%m-%d").date()

        # Parse YAML metadata
        meta = read_front_matter(md)

        # Date parsing
        raw_date = meta.get("date")
        meta_date: date

        meta_date_valid = False
        if isinstance(raw_date, date):
            meta_date = raw_date
            meta_date_valid = True
        elif: isinstance(raw, str):
            try:
                meta_date = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                meta_date = md_date
        else:
            meta_date = md_date

        if meta_date != md_date:
            sys.stderr.write(
                f"[WARN] {md.name}: "
                "YAML date {yaml_date} ≠ filename date {md_date}\n"
            )

        # Parse entry
        entry = Entry(
            path=md,
            stem=md.stem,
            # TODO: Consider changing date to integer: md_date.year
            year=meta_date.strftime("%Y"),
            month=meta_date.strftime("%B"),
            status=meta.get("status", "unreviewed"),
        )
        entry.merge_meta(meta)
        entries.append(entry)

        # Parse people
        for pname in entry.people:
            key = pname.lower()
            person = people.get(key)

            if person is None:
                # first appearance -> create record
                person = Person(
                    path      = PPL_DIR / f"{key}.md",
                    name      = pname.title(),
                    freq      = 1,
                )
            else:
                # appearances
                person.freq += 1

            person.merge_meta(themes=entry.themes, date=meta_date, md=md)
            people[key] = person


    WIKI_DIR.mkdir(exist_ok=True)
    build_dashboards(entries)
    print("✓ Vimwiki in sync")

if __name__ == "__main__":
    main()

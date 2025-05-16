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

import argparse
import datetime as dt
import difflib
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

# ------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------
# TODO: Check that these are correct
ROOT: Path = Path(__file__).resolve().parents[2]
SRC_DIR: Path = ROOT / "journal" / "md"
VIMWIKI_DIR: Path = ROOT / "vimwiki"
INLINE_YEARS: set[str] = {"2025", "2024"}

# ------------------------------------------------------------------------
# YAML loader
# ------------------------------------------------------------------------
def read_front_matter(path: Path) -> Dict[str, Any]:
    """
    Return YAML front‑matter as a dict; ({} if none).
    Gracefully handles:
      • files without front‑matter
      • front‑matter not at file start
      • extra '---' delimiters later in the file
    """
    with path.open(encoding="utf-8") as fh:
        if fh.readline().rstrip() != "---":
            return {}
        lines: List[str] = []
        for line in fh:
            if line.rstrip() == "---":
                break
            lines.append(line)
        yaml_text: str = "".join(lines)
    try:
        data: Dict[str, Any] | None = yaml.safe_load(yaml_text)
        return data or {}
    except yaml.YAMLError as exc:
        print(f"[WARN] YAML parse error in {path}: {exc}", file=sys.stderr)
        return {}

# ----------------------------------------------------------------------
# Entry structure
# ----------------------------------------------------------------------
class Entry(Dict[str, Any]):  # simple typed mapping
    path: Path
    stem: str
    year: str
    month: str
    status: str
    people: List[str]
    tags: List[str]
    themes: List[str]
    notes: str

# ----------------------------------------------------------------------
# Dashboard generators
# ----------------------------------------------------------------------
def _inv_line(e: Entry) -> str:
    """Markdown bullet for one entry."""
    check: str = "x" if e["done"] else " "
    # TODO: Change link to have a pretty name
    return f"- [{check}] [[{e['path'].name}]] — {e['status']}"

# ----------  inventory: parse current  ---------------------------------
def parse_current_inventory() -> Dict[str, List[str]]:
    """
    Return {'top': lines_for_inventory_md, 'year': lines_for_year_md}.
    Missing files →  empty lists.
    """
    out: Dict[str, List[str]] = {}
    main_file = VIMWIKI_DIR / "inventory.md"
    out["top"] = main_file.read_text().splitlines() \
        if main_file.exists() else []
    inv_dir = VIMWIKI_DIR / "inventory"
    for y_path in (inv_dir.glob("20??.md") if inv_dir.exists() else []):
        out[y_path.stem] = y_path.read_text().splitlines()
    return out

# ----------  inventory: render fresh  ----------------------------------
def render_inventory(entries: Sequence[Entry]) -> Dict[str, List[str]]:
    """Return a dict {filename_key: list_of_lines} ready to write."""
    inv_out: Dict[str, List[str]] = {}
    older_years: set[str] = {e["year"] for e in entries} - INLINE_YEARS

    # --- inventory.md ---
    main: List[str] = ["# Inventory", ""]
    for y in sorted(INLINE_YEARS, reverse=True):
        subset = [e for e in entries if e["year"] == y]
        if not subset:
            continue
        main.append(f"## 🕯️ {y}")
        by_month: Dict[str, List[Entry]] = defaultdict(list)
        for e in subset:
            by_month[e["month"]].append(e)
        for m in sorted(by_month,
                        key=lambda name: dt.datetime.strptime(name, "%B").month,
                        reverse=True):
            main.append(f"\n### {m}")
            main += [_inv_line(e) for e in by_month[m]]
        main.append("")
    # archive links
    main += ["\n---\n", "## 📦 Archive"]
    for y in sorted(older_years, reverse=True):
        main.append(f"→ [[inventory/{y}.md]]")
    inv_out["top"] = main

    # --- yearly pages ---
    for y in older_years:
        lines = [f"# {y}", ""]
        lines += [_inv_line(e) for e in entries if e["year"] == y]
        inv_out[y] = lines
    return inv_out

# ----------  write‑if‑changed helper  ----------------------------------
def _write_if_changed(path: Path, new_lines: List[str]) -> None:
    old_lines: List[str] = path.read_text().splitlines() if path.exists() else []
    if old_lines == new_lines:
        return  # no change
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines), encoding="utf-8")
    diff = difflib.unified_diff(old_lines, new_lines,
                                fromfile="old", tofile="new", lineterm="")
    print(f"✎ updated {path.relative_to(ROOT)}")
    # Uncomment to see diff:
    # for line in diff: print(line)


# ----------------------------------------------------------------------
# Build dashboards
# ----------------------------------------------------------------------
def build_dashboards(entries: Sequence[Entry]) -> None:
    """Render + write inventory (others can follow same pattern)."""
    current = parse_current_inventory()
    fresh   = render_inventory(entries)

    # inventory.md
    _write_if_changed(VIMWIKI_DIR / "inventory.md", fresh["top"])

    # yearly pages
    inv_dir = VIMWIKI_DIR / "inventory"
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
    p.add_argument("--year", help="only process one year (e.g. 2025)")
    return p.parse_args()

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    target_years: set[str] | None = {args.year} if args.year else None

    entries: List[Entry] = []
    for md in sorted(SRC_DIR.rglob("20??-??-??.md")):
        year = md.stem[:4]
        if target_years and year not in target_years:
            continue
        meta = read_front_matter(md)
        date_obj = dt.datetime.strptime(md.stem, "%Y-%m-%d")
        entries.append(Entry(
            path=md,
            stem=md.stem,
            year=year,
            month=date_obj.strftime("%B"),
            status=meta.get("status", "unreviewed"),
            people=meta.get("people", []),
            tags=meta.get("tags", []),
            themes=meta.get("themes", []),
            notes=str(meta.get("notes", "")).strip(),
        ))

    VIMWIKI_DIR.mkdir(exist_ok=True)
    build_dashboards(entries)
    print("✓ Vimwiki in sync")

if __name__ == "__main__":
    main()

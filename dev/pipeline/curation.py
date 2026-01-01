#!/usr/bin/env python3
"""
curation.py
-----------
Narrative analysis curation tool for auditing and consolidating vocabulary.

This module provides tools for:
- Scanning all 972 analysis files
- Extracting all unique tags/themes/thematic arcs with frequencies
- Parsing scenes and people/locations
- Proposing consolidated vocabulary (Motifs ~20, Tags ~30)
- Generating review documents (summary and full versions)

The goal is to prepare all data for a single review pass by the novelist,
after which corrections can be applied and propagated to the database/wiki.

Usage:
    # Audit all files and generate frequency reports
    python -m dev.pipeline.curation audit

    # Generate consolidated vocabulary proposal
    python -m dev.pipeline.curation propose-vocabulary

    # Generate review PDFs
    python -m dev.pipeline.curation generate-review --summary
    python -m dev.pipeline.curation generate-review --full
"""
from __future__ import annotations

# --- Standard library imports ---
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# --- Local imports ---
from dev.core.paths import NARRATIVE_ANALYSIS_DIR
from dev.utils.md import extract_section, split_frontmatter
from dev.utils.narrative import build_scene_event_mapping, fuzzy_match_scene


@dataclass
class AnalysisEntry:
    """Parsed content from a single narrative analysis file."""

    date: date
    path: Path
    summary: str = ""
    rating: float = 0.0
    rating_justification: str = ""
    tags: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    themes: Dict[str, str] = field(default_factory=dict)  # name -> description
    thematic_arcs: List[str] = field(default_factory=list)
    tag_categories: List[str] = field(default_factory=list)
    cleaned_tags: List[str] = field(default_factory=list)
    scenes: List[Dict[str, str]] = field(default_factory=list)  # title, description
    additional_motifs: Dict[str, str] = field(default_factory=dict)  # name -> desc


@dataclass
class AuditResults:
    """Aggregated results from auditing all analysis files."""

    total_files: int = 0
    files_by_year: Dict[int, int] = field(default_factory=dict)

    # Frequency counts
    tags: Counter = field(default_factory=Counter)
    thematic_arcs: Counter = field(default_factory=Counter)
    tag_categories: Counter = field(default_factory=Counter)
    cleaned_tags: Counter = field(default_factory=Counter)
    people: Counter = field(default_factory=Counter)
    locations: Counter = field(default_factory=Counter)
    themes: Counter = field(default_factory=Counter)
    additional_motifs: Counter = field(default_factory=Counter)

    # All entries
    entries: List[AnalysisEntry] = field(default_factory=list)


def parse_analysis_file(path: Path) -> Optional[AnalysisEntry]:
    """
    Parse a single narrative analysis markdown file.

    Args:
        path: Path to the analysis file

    Returns:
        AnalysisEntry with parsed content, or None if parsing fails
    """
    try:
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Extract date from filename
        date_str = path.stem.replace("_analysis", "")
        entry_date = date.fromisoformat(date_str)

        entry = AnalysisEntry(date=entry_date, path=path)

        # Parse summary
        summary_lines = extract_section(lines, "Summary")
        entry.summary = "\n".join(summary_lines).strip()

        # Parse rating
        for line in lines:
            if match := re.match(r"##\s*Narrative Rating:\s*([\d.]+)/5", line):
                entry.rating = float(match.group(1))
                break

        # Parse rating justification (text after rating, before next section)
        rating_idx = None
        for i, line in enumerate(lines):
            if "Narrative Rating:" in line:
                rating_idx = i
                break
        if rating_idx is not None:
            justification_lines = []
            for line in lines[rating_idx + 1 :]:
                if line.startswith("##"):
                    break
                if line.strip() and not line.startswith("###"):
                    justification_lines.append(line.strip())
            entry.rating_justification = "\n".join(justification_lines).strip()

        # Parse Tags (comma-separated line)
        tags_lines = extract_section(lines, "Tags")
        if tags_lines:
            tag_text = " ".join(tags_lines)
            entry.tags = [t.strip() for t in tag_text.split(",") if t.strip()]

        # Parse People (comma-separated or bullet list)
        people_lines = extract_section(lines, "People")
        if people_lines:
            people_text = " ".join(people_lines)
            if "," in people_text:
                entry.people = [p.strip() for p in people_text.split(",") if p.strip()]
            else:
                entry.people = [
                    p.strip().lstrip("-").strip()
                    for p in people_lines
                    if p.strip() and p.strip() != "-"
                ]

        # Parse Locations
        loc_lines = extract_section(lines, "Locations")
        if loc_lines:
            loc_text = " ".join(loc_lines)
            if "," in loc_text:
                entry.locations = [loc.strip() for loc in loc_text.split(",") if loc.strip()]
            else:
                entry.locations = [
                    loc.strip().lstrip("-").strip()
                    for loc in loc_lines
                    if loc.strip() and loc.strip() != "-"
                ]

        # Parse Themes (bullet list with **name**: description)
        themes_lines = extract_section(lines, "Themes")
        for line in themes_lines:
            if match := re.match(r"-\s*\*\*(.+?)\*\*[:\s]*(.+)?", line):
                theme_name = match.group(1).strip()
                theme_desc = match.group(2).strip() if match.group(2) else ""
                entry.themes[theme_name] = theme_desc

        # Parse Motifs (try new "Motifs" section first, fall back to "Thematic Arcs")
        motifs_lines = extract_section(lines, "Motifs")
        if not motifs_lines:
            motifs_lines = extract_section(lines, "Thematic Arcs")
        if motifs_lines:
            # First line(s) may be comma-separated motif names
            for line in motifs_lines:
                line = line.strip()
                if not line:
                    continue
                # Check if it's a descriptive bullet point (- MOTIF_NAME: description)
                if match := re.match(r"-\s*([A-Z_/&\s]+):\s*(.+)", line):
                    motif_name = match.group(1).strip()
                    motif_desc = match.group(2).strip()
                    entry.additional_motifs[motif_name] = motif_desc
                elif "," in line and not line.startswith("-"):
                    # Comma-separated motif names
                    entry.thematic_arcs.extend([a.strip() for a in line.split(",") if a.strip()])
                elif line.isupper() or (line.replace(" ", "").replace("&", "").replace("/", "").isalpha() and line == line.upper()):
                    # Single motif name (all caps)
                    entry.thematic_arcs.append(line)

        # Parse Tag Categories (for backwards compatibility, will be removed after cleanup)
        cat_lines = extract_section(lines, "Tag Categories")
        if cat_lines:
            cat_text = " ".join(cat_lines)
            entry.tag_categories = [c.strip() for c in cat_text.split(",") if c.strip()]

        # Parse Cleaned Tags (for backwards compatibility, will be removed after cleanup)
        cleaned_lines = extract_section(lines, "Cleaned Tags")
        if cleaned_lines:
            cleaned_text = " ".join(cleaned_lines)
            entry.cleaned_tags = [c.strip() for c in cleaned_text.split(",") if c.strip()]

        # Parse Scenes (numbered list with **title** - description)
        scenes_lines = extract_section(lines, "Scenes")
        for line in scenes_lines:
            if match := re.match(r"\d+\.\s*\*\*(.+?)\*\*\s*-\s*(.+)", line):
                entry.scenes.append({
                    "title": match.group(1).strip(),
                    "description": match.group(2).strip(),
                })

        # Parse Additional Motifs (for backwards compatibility, will be merged after cleanup)
        add_motifs_lines = extract_section(lines, "Additional Motifs")
        for line in add_motifs_lines:
            if match := re.match(r"-\s*([A-Z_/&\s]+):\s*(.+)", line):
                motif_name = match.group(1).strip()
                motif_desc = match.group(2).strip()
                entry.additional_motifs[motif_name] = motif_desc

        return entry

    except Exception as e:
        print(f"Error parsing {path}: {e}")
        return None


def audit_all_files(base_dir: Optional[Path] = None) -> AuditResults:
    """
    Scan all analysis files and extract frequency data.

    Args:
        base_dir: Base directory for analysis files (defaults to NARRATIVE_ANALYSIS_DIR)

    Returns:
        AuditResults with all frequency counts and parsed entries
    """
    if base_dir is None:
        base_dir = NARRATIVE_ANALYSIS_DIR

    results = AuditResults()

    # Find all analysis files
    analysis_files = sorted(base_dir.glob("20*/*_analysis.md"))
    results.total_files = len(analysis_files)

    for path in analysis_files:
        # Count by year
        year = int(path.parent.name)
        results.files_by_year[year] = results.files_by_year.get(year, 0) + 1

        # Parse file
        entry = parse_analysis_file(path)
        if entry is None:
            continue

        results.entries.append(entry)

        # Aggregate frequencies
        results.tags.update(entry.tags)
        results.thematic_arcs.update(entry.thematic_arcs)
        results.tag_categories.update(entry.tag_categories)
        results.cleaned_tags.update(entry.cleaned_tags)
        results.people.update(entry.people)
        results.locations.update(entry.locations)
        results.themes.update(entry.themes.keys())
        results.additional_motifs.update(entry.additional_motifs.keys())

    return results


def print_audit_report(results: AuditResults) -> None:
    """Print a summary report of the audit results."""
    print("=" * 70)
    print("NARRATIVE ANALYSIS AUDIT REPORT")
    print("=" * 70)

    print(f"\nTotal files: {results.total_files}")
    print("\nFiles by year:")
    for year in sorted(results.files_by_year.keys()):
        print(f"  {year}: {results.files_by_year[year]}")

    print(f"\n{'=' * 70}")
    print("THEMATIC ARCS (what will become Motifs)")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.thematic_arcs)}")
    print("\nTop 30 by frequency:")
    for arc, count in results.thematic_arcs.most_common(30):
        print(f"  {count:4d}  {arc}")

    print(f"\n{'=' * 70}")
    print("TAGS (raw)")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.tags)}")
    print("\nTop 50 by frequency:")
    for tag, count in results.tags.most_common(50):
        print(f"  {count:4d}  {tag}")

    print(f"\n{'=' * 70}")
    print("TAG CATEGORIES")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.tag_categories)}")
    for cat, count in results.tag_categories.most_common():
        print(f"  {count:4d}  {cat}")

    print(f"\n{'=' * 70}")
    print("CLEANED TAGS")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.cleaned_tags)}")
    print("\nTop 50 by frequency:")
    for tag, count in results.cleaned_tags.most_common(50):
        print(f"  {count:4d}  {tag}")

    print(f"\n{'=' * 70}")
    print("THEMES (unique names)")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.themes)}")
    print("\nTop 50 by frequency:")
    for theme, count in results.themes.most_common(50):
        print(f"  {count:4d}  {theme}")

    print(f"\n{'=' * 70}")
    print("ADDITIONAL MOTIFS")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.additional_motifs)}")
    for motif, count in results.additional_motifs.most_common():
        print(f"  {count:4d}  {motif}")

    print(f"\n{'=' * 70}")
    print("PEOPLE")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.people)}")
    print("\nTop 50 by frequency:")
    for person, count in results.people.most_common(50):
        print(f"  {count:4d}  {person}")

    print(f"\n{'=' * 70}")
    print("LOCATIONS")
    print(f"{'=' * 70}")
    print(f"Unique values: {len(results.locations)}")
    print("\nTop 50 by frequency:")
    for loc, count in results.locations.most_common(50):
        print(f"  {count:4d}  {loc}")


@dataclass
class CuratedEntry:
    """An entry with proposed consolidated vocabulary assignments."""

    original: AnalysisEntry
    proposed_motifs: Set[str] = field(default_factory=set)
    proposed_tags: Set[str] = field(default_factory=set)
    normalized_people: List[str] = field(default_factory=list)
    normalized_locations: List[str] = field(default_factory=list)


def curate_entry(entry: AnalysisEntry) -> CuratedEntry:
    """
    Apply vocabulary mappings to create curated entry.

    Args:
        entry: Parsed analysis entry

    Returns:
        CuratedEntry with proposed consolidated vocabulary
    """
    from dev.pipeline.configs.vocabulary import (
        get_motifs_for_entry,
        get_tags_for_entry,
        normalize_person,
        normalize_location,
    )

    curated = CuratedEntry(original=entry)

    # Map thematic arcs to motifs
    curated.proposed_motifs = get_motifs_for_entry(entry.thematic_arcs)

    # Map tag categories to tags
    curated.proposed_tags = get_tags_for_entry(entry.tag_categories)

    # Normalize people
    curated.normalized_people = [
        normalize_person(p) for p in entry.people
    ]

    # Normalize locations
    curated.normalized_locations = [
        loc for loc in (normalize_location(loc) for loc in entry.locations) if loc
    ]

    return curated


def curate_all_entries(results: AuditResults) -> List[CuratedEntry]:
    """
    Apply vocabulary mappings to all entries.

    Args:
        results: Audit results with all parsed entries

    Returns:
        List of curated entries with proposed vocabulary
    """
    return [curate_entry(entry) for entry in results.entries]


def generate_summary_markdown(
    curated_entries: List[CuratedEntry],
    period: Optional[str] = None,
) -> str:
    """
    Generate summary review markdown document.

    Args:
        curated_entries: List of curated entries
        period: Period key ("core", "early_mtl", "mexico") for format adjustments

    Returns:
        Markdown content for summary review
    """
    is_core = period == "core"

    # Load event mappings for core period
    scene_event_mapping: Dict[str, Dict] = {}
    if is_core:
        events_dir = NARRATIVE_ANALYSIS_DIR / "_events"
        from dev.utils.narrative import CORE_RANGE
        scene_event_mapping = build_scene_event_mapping(events_dir, CORE_RANGE)

    lines = [
        "# Narrative Analysis Curation Review (Summary)",
        "",
        "Review each entry and mark corrections.",
        "- Use `[X]` to reject, `[✓]` to approve",
        "- Use the Full Review document for source context.",
        "",
        "---",
        "",
    ]

    current_year = None
    current_month = None

    for curated in sorted(curated_entries, key=lambda c: c.original.date):
        entry = curated.original

        # Year header
        if entry.date.year != current_year:
            current_year = entry.date.year
            current_month = None
            lines.append(f"# {current_year}")
            lines.append("")

        # Month header
        if entry.date.month != current_month:
            current_month = entry.date.month
            month_name = entry.date.strftime("%B")
            lines.append(f"## {month_name} {current_year}")
            lines.append("")

        # Entry
        lines.append(f"### {entry.date.isoformat()} (Rating: {entry.rating}/5)")
        lines.append("")

        # Summary
        if entry.summary:
            # Truncate long summaries for review
            summary = entry.summary[:500] + "..." if len(entry.summary) > 500 else entry.summary
            lines.append(f"**Summary:** {summary}")
            lines.append("")

        # Proposed Motifs with checkboxes
        lines.append("**Motifs:**")
        if curated.proposed_motifs:
            for motif in sorted(curated.proposed_motifs):
                lines.append(f"- [ ] {motif}")
        else:
            lines.append("- _(none proposed)_")
        lines.append("")

        # Proposed Tags (no checkboxes per user request)
        if curated.proposed_tags:
            tags = ", ".join(sorted(curated.proposed_tags))
            lines.append(f"**Tags:** {tags}")
        else:
            lines.append("**Tags:** _(none proposed)_")
        lines.append("")

        # Themes with checkboxes
        if entry.themes:
            lines.append("**Themes:**")
            for theme_name, theme_desc in entry.themes.items():
                if theme_desc:
                    lines.append(f"- [ ] **{theme_name}:** {theme_desc}")
                else:
                    lines.append(f"- [ ] **{theme_name}**")
            lines.append("")

        # Scenes grouped by events (for core) with checkboxes
        if entry.scenes:
            month_key = f"{entry.date.year}-{entry.date.month:02d}"
            month_mapping = scene_event_mapping.get(month_key, {})

            if is_core and month_mapping:
                # Group scenes by event
                events_scenes: Dict[str, List[Dict]] = {}
                unmapped_scenes: List[Dict] = []

                for scene in entry.scenes:
                    event_info = fuzzy_match_scene(scene["title"], month_mapping)
                    if event_info:
                        event_name = event_info["event_name"]
                        if event_name not in events_scenes:
                            events_scenes[event_name] = []
                        events_scenes[event_name].append(scene)
                    else:
                        unmapped_scenes.append(scene)

                lines.append("**Scenes:**")
                for event_name in sorted(events_scenes.keys()):
                    lines.append(f"- [ ] *{event_name}*")
                    for scene in events_scenes[event_name]:
                        lines.append(f"  - [ ] **{scene['title']}**")
                if unmapped_scenes:
                    lines.append("- *(Unmapped)*")
                    for scene in unmapped_scenes:
                        lines.append(f"  - [ ] **{scene['title']}**")
                lines.append("")
            else:
                # Simple list for non-core
                lines.append("**Scenes:**")
                for scene in entry.scenes:
                    lines.append(f"- [ ] **{scene['title']}**")
                lines.append("")

        # People and Locations only for non-core periods
        if not is_core:
            if curated.normalized_people:
                people = ", ".join(curated.normalized_people)
                lines.append(f"**People:** {people}")
                lines.append("")

            if curated.normalized_locations:
                locations = ", ".join(curated.normalized_locations)
                lines.append(f"**Locations:** {locations}")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_full_markdown(
    curated_entries: List[CuratedEntry],
    journal_dir: Optional[Path] = None,
    period: Optional[str] = None,
) -> str:
    """
    Generate full review markdown document with journal text.

    Args:
        curated_entries: List of curated entries
        journal_dir: Directory containing journal markdown files
        period: Period key ("core", "early_mtl", "mexico") for format adjustments

    Returns:
        Markdown content for full review
    """
    from dev.core.paths import MD_DIR

    if journal_dir is None:
        journal_dir = MD_DIR

    is_core = period == "core"

    # Load event mappings for core period
    scene_event_mapping: Dict[str, Dict] = {}
    if is_core:
        events_dir = NARRATIVE_ANALYSIS_DIR / "_events"
        from dev.utils.narrative import CORE_RANGE
        scene_event_mapping = build_scene_event_mapping(events_dir, CORE_RANGE)

    lines = [
        "# Narrative Analysis Curation Review (Full)",
        "",
        "Complete review with journal source text, themes, and scenes.",
        "- Use `[X]` to reject, `[✓]` to approve",
        "",
        "---",
        "",
    ]

    current_year = None
    current_month = None

    for curated in sorted(curated_entries, key=lambda c: c.original.date):
        entry = curated.original

        # Year header
        if entry.date.year != current_year:
            current_year = entry.date.year
            current_month = None
            lines.append(f"# {current_year}")
            lines.append("")

        # Month header
        if entry.date.month != current_month:
            current_month = entry.date.month
            month_name = entry.date.strftime("%B")
            lines.append(f"## {month_name} {current_year}")
            lines.append("")

        # Entry header
        lines.append(f"### {entry.date.isoformat()} (Rating: {entry.rating}/5)")
        lines.append("")

        # Summary
        if entry.summary:
            lines.append(f"**Summary:** {entry.summary}")
            lines.append("")

        # Rating justification
        if entry.rating_justification:
            lines.append(f"**Rating Justification:** {entry.rating_justification}")
            lines.append("")

        # Proposed Motifs with checkboxes
        lines.append("**Proposed Motifs:**")
        if curated.proposed_motifs:
            for motif in sorted(curated.proposed_motifs):
                lines.append(f"- [ ] {motif}")
        else:
            lines.append("- _(none)_")
        lines.append("")

        # Proposed Tags (no checkboxes per user request)
        if curated.proposed_tags:
            tags = ", ".join(sorted(curated.proposed_tags))
            lines.append(f"**Proposed Tags:** {tags}")
        else:
            lines.append("**Proposed Tags:** _(none)_")
        lines.append("")

        # People
        if curated.normalized_people:
            people = ", ".join(curated.normalized_people)
            lines.append(f"**People:** {people}")
            lines.append("")

        # Locations
        if curated.normalized_locations:
            locations = ", ".join(curated.normalized_locations)
            lines.append(f"**Locations:** {locations}")
            lines.append("")

        # Themes with descriptions and checkboxes (proper list formatting)
        if entry.themes:
            lines.append("**Themes:**")
            lines.append("")  # Blank line to ensure proper list rendering
            for theme_name, theme_desc in entry.themes.items():
                if theme_desc:
                    lines.append(f"- [ ] **{theme_name}:** {theme_desc}")
                else:
                    lines.append(f"- [ ] **{theme_name}**")
            lines.append("")

        # Scenes grouped by events (for core) with checkboxes
        if entry.scenes:
            month_key = f"{entry.date.year}-{entry.date.month:02d}"
            month_mapping = scene_event_mapping.get(month_key, {})

            lines.append("**Scenes:**")
            lines.append("")  # Blank line to ensure proper list rendering

            if is_core and month_mapping:
                # Group scenes by event
                events_scenes: Dict[str, List[Dict]] = {}
                unmapped_scenes: List[Dict] = []

                for scene in entry.scenes:
                    event_info = fuzzy_match_scene(scene["title"], month_mapping)
                    if event_info:
                        event_name = event_info["event_name"]
                        if event_name not in events_scenes:
                            events_scenes[event_name] = []
                        events_scenes[event_name].append(scene)
                    else:
                        unmapped_scenes.append(scene)

                for event_name in sorted(events_scenes.keys()):
                    lines.append(f"- [ ] *{event_name}*")
                    for scene in events_scenes[event_name]:
                        lines.append(f"  - [ ] **{scene['title']}** — {scene['description']}")

                if unmapped_scenes:
                    lines.append("- *(Unmapped)*")
                    for scene in unmapped_scenes:
                        lines.append(f"  - [ ] **{scene['title']}** — {scene['description']}")
            else:
                # Simple list for non-core
                for scene in entry.scenes:
                    lines.append(f"- [ ] **{scene['title']}** — {scene['description']}")

            lines.append("")

        # Journal text
        year_str = str(entry.date.year)
        journal_file = journal_dir / year_str / f"{entry.date.isoformat()}.md"
        if journal_file.exists():
            lines.append("**Journal Entry:**")
            lines.append("")
            lines.append("```")
            journal_content = journal_file.read_text(encoding="utf-8")
            # Skip frontmatter
            _, body_lines = split_frontmatter(journal_content)
            # Add line numbers
            for i, line in enumerate(body_lines[:100], 1):  # Limit to 100 lines
                lines.append(f"{i:3d} | {line}")
            if len(body_lines) > 100:
                lines.append(f"... ({len(body_lines) - 100} more lines)")
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_review_pdf(
    curated_entries: List[CuratedEntry],
    output_dir: Path,
    summary: bool = True,
) -> Path:
    """
    Generate review PDF document.

    Args:
        curated_entries: List of curated entries
        output_dir: Output directory for PDF
        summary: If True, generate summary; if False, generate full review

    Returns:
        Path to generated PDF
    """
    from dev.builders.narrative import build_pdf

    output_dir.mkdir(parents=True, exist_ok=True)

    if summary:
        content = generate_summary_markdown(curated_entries)
        filename = "curation_summary"
    else:
        content = generate_full_markdown(curated_entries)
        filename = "curation_full"

    # Write markdown first
    md_path = output_dir / f"{filename}.md"
    md_path.write_text(content, encoding="utf-8")

    # Convert to PDF
    pdf_path = output_dir / f"{filename}.pdf"
    build_pdf(md_path, pdf_path)

    # Clean up markdown
    md_path.unlink()

    return pdf_path


def main():
    """Run the audit and print results."""
    print("Scanning analysis files...")
    results = audit_all_files()
    print_audit_report(results)


def generate_review_documents(output_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    """
    Generate both summary and full review PDFs.

    Args:
        output_dir: Output directory (defaults to _curation/)

    Returns:
        Tuple of (summary_path, full_path)
    """
    if output_dir is None:
        output_dir = NARRATIVE_ANALYSIS_DIR / "_curation"

    print("Scanning analysis files...")
    results = audit_all_files()

    print(f"Curating {len(results.entries)} entries...")
    curated = curate_all_entries(results)

    print("Generating summary review PDF...")
    summary_path = generate_review_pdf(curated, output_dir, summary=True)
    print(f"  Created: {summary_path}")

    print("Generating full review PDF...")
    full_path = generate_review_pdf(curated, output_dir, summary=False)
    print(f"  Created: {full_path}")

    return summary_path, full_path


# Period definitions
PERIODS = {
    "core": {
        "name": "Core Story",
        "description": "Nov 2024 - Dec 2025",
        "filter": lambda d: (d.year == 2024 and d.month >= 11) or d.year >= 2025,
    },
    "early_mtl": {
        "name": "Early Montreal",
        "description": "2021 - Oct 2024",
        "filter": lambda d: (d.year >= 2021 and d.year <= 2023) or (d.year == 2024 and d.month <= 10),
    },
    "mexico": {
        "name": "Mexico Years",
        "description": "2015 - 2019",
        "filter": lambda d: d.year <= 2019,
    },
}


def filter_entries_by_period(
    curated_entries: List[CuratedEntry],
    period: str,
) -> List[CuratedEntry]:
    """
    Filter curated entries by time period.

    Args:
        curated_entries: List of all curated entries
        period: Period key ("core", "early_mtl", "mexico")

    Returns:
        Filtered list of entries for the period
    """
    if period not in PERIODS:
        raise ValueError(f"Unknown period: {period}. Valid: {list(PERIODS.keys())}")

    period_filter = PERIODS[period]["filter"]
    return [c for c in curated_entries if period_filter(c.original.date)]


def generate_period_documents(
    period: str,
    output_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """
    Generate summary and full review PDFs for a specific period.

    Args:
        period: Period key ("core", "early_mtl", "mexico")
        output_dir: Output directory (defaults to _curation/)

    Returns:
        Tuple of (summary_path, full_path)
    """
    from dev.builders.narrative import build_pdf

    if output_dir is None:
        output_dir = NARRATIVE_ANALYSIS_DIR / "_curation"

    output_dir.mkdir(parents=True, exist_ok=True)

    period_info = PERIODS[period]
    print(f"Generating {period_info['name']} ({period_info['description']})...")

    print("  Scanning analysis files...")
    results = audit_all_files()

    print("  Curating entries...")
    curated = curate_all_entries(results)

    print("  Filtering by period...")
    filtered = filter_entries_by_period(curated, period)
    print(f"  Found {len(filtered)} entries")

    # Generate summary
    print("  Generating summary PDF...")
    summary_content = generate_summary_markdown(filtered, period=period)
    summary_md = output_dir / f"curation_{period}_summary.md"
    summary_md.write_text(summary_content, encoding="utf-8")
    summary_pdf = output_dir / f"curation_{period}_summary.pdf"
    build_pdf(summary_md, summary_pdf)
    summary_md.unlink()
    print(f"    Created: {summary_pdf.name}")

    # Generate full
    print("  Generating full PDF...")
    full_content = generate_full_markdown(filtered, period=period)
    full_md = output_dir / f"curation_{period}_full.md"
    full_md.write_text(full_content, encoding="utf-8")
    full_pdf = output_dir / f"curation_{period}_full.pdf"
    build_pdf(full_md, full_pdf)
    full_md.unlink()
    print(f"    Created: {full_pdf.name}")

    return summary_pdf, full_pdf


def generate_all_period_documents(output_dir: Optional[Path] = None) -> None:
    """
    Generate summary and full review PDFs for all periods.

    Args:
        output_dir: Output directory (defaults to _curation/)
    """
    for period in PERIODS:
        generate_period_documents(period, output_dir)
    print("\nDone!")


# Sections to remove during cleanup (redundant with vocabulary mapping)
SECTIONS_TO_REMOVE = {"Tag Categories", "Cleaned Tags", "Thematic Arcs", "Additional Motifs"}

# Standard section order for consistent formatting
SECTION_ORDER = [
    "Summary",
    "Narrative Rating",
    "Tags",
    "People",
    "Locations",
    "Themes",
    "Motifs",  # Consolidated from "Thematic Arcs" + "Additional Motifs"
    "Scenes",
]


def clean_analysis_file(path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Clean a single narrative analysis markdown file.

    - Removes redundant sections (Tag Categories, Cleaned Tags)
    - Renames "Thematic Arcs" to "Motifs"
    - Merges "Additional Motifs" into "Motifs"
    - Standardizes formatting while preserving all qualitative content

    Args:
        path: Path to the analysis file
        dry_run: If True, only report what would be changed

    Returns:
        Tuple of (was_modified, description)
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Parse into sections
    sections: Dict[str, List[str]] = {}
    current_section: Optional[str] = None

    for line in lines:
        # Check for section header (## Section Name or ## Section Name: value)
        if line.startswith("## "):
            # Extract section name (handle "## Narrative Rating: 4/5" format)
            header_text = line[3:].strip()
            section_name = header_text.split(":")[0].strip()

            current_section = section_name
            sections[current_section] = [line]
        elif line.startswith("# ") and "Narrative Analysis" in line:
            # Title line
            if "title" not in sections:
                sections["title"] = []
            sections["title"].append(line)
            current_section = "title"
        elif current_section:
            sections[current_section].append(line)

    # Determine changes
    changes = []
    has_thematic_arcs = "Thematic Arcs" in sections
    has_additional_motifs = "Additional Motifs" in sections
    has_tag_categories = "Tag Categories" in sections
    has_cleaned_tags = "Cleaned Tags" in sections

    if has_tag_categories:
        changes.append("remove Tag Categories")
    if has_cleaned_tags:
        changes.append("remove Cleaned Tags")
    if has_thematic_arcs:
        changes.append("rename Thematic Arcs → Motifs")
    if has_additional_motifs:
        changes.append("merge Additional Motifs")

    if not changes:
        return False, "No changes needed"

    if dry_run:
        return True, "; ".join(changes)

    # Build merged Motifs section
    motifs_lines: List[str] = ["## Motifs"]

    # Add thematic arcs as comma-separated list (the core motifs)
    if has_thematic_arcs:
        arc_content = sections["Thematic Arcs"][1:]
        # Remove leading/trailing blanks
        while arc_content and not arc_content[0].strip():
            arc_content.pop(0)
        while arc_content and not arc_content[-1].strip():
            arc_content.pop()
        if arc_content:
            motifs_lines.extend(arc_content)

    # Add additional motifs with descriptions (as bullet list)
    if has_additional_motifs:
        add_content = sections["Additional Motifs"][1:]
        # Remove leading/trailing blanks
        while add_content and not add_content[0].strip():
            add_content.pop(0)
        while add_content and not add_content[-1].strip():
            add_content.pop()
        if add_content:
            # Add blank line separator if we had thematic arcs
            if has_thematic_arcs and any(ln.strip() for ln in motifs_lines[1:]):
                motifs_lines.append("")
            motifs_lines.extend(add_content)

    # Store merged motifs
    sections["Motifs"] = motifs_lines

    # Rebuild the file
    new_lines: List[str] = []

    # Add title
    if "title" in sections:
        new_lines.extend(sections["title"])
        if new_lines and new_lines[-1].strip():
            new_lines.append("")

    # Add sections in order
    for section_name in SECTION_ORDER:
        if section_name in sections:
            section_lines = sections[section_name]

            # Ensure blank line before section
            if new_lines and new_lines[-1].strip():
                new_lines.append("")

            # Add section header
            new_lines.append(section_lines[0])

            # Add section content
            content_lines = section_lines[1:]

            # Remove leading blank lines from content
            while content_lines and not content_lines[0].strip():
                content_lines.pop(0)

            # Remove trailing blank lines from content
            while content_lines and not content_lines[-1].strip():
                content_lines.pop()

            # Add content with proper spacing
            if content_lines:
                # For list sections, ensure blank line after header
                if section_name in {"Themes", "Scenes", "Motifs"}:
                    new_lines.append("")
                new_lines.extend(content_lines)

    # Ensure file ends with newline
    new_lines.append("")

    # Write back
    path.write_text("\n".join(new_lines), encoding="utf-8")

    return True, "; ".join(changes)


def clean_all_analysis_files(
    base_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Clean all narrative analysis files in the directory.

    Args:
        base_dir: Base directory for analysis files (defaults to NARRATIVE_ANALYSIS_DIR)
        dry_run: If True, only report what would be changed

    Returns:
        Dict with counts: {"modified": N, "unchanged": N, "errors": N}
    """
    if base_dir is None:
        base_dir = NARRATIVE_ANALYSIS_DIR

    analysis_files = sorted(base_dir.glob("20*/*_analysis.md"))

    stats = {"modified": 0, "unchanged": 0, "errors": 0}

    action = "Would modify" if dry_run else "Modified"

    for path in analysis_files:
        try:
            modified, description = clean_analysis_file(path, dry_run=dry_run)
            if modified:
                stats["modified"] += 1
                print(f"  {action}: {path.name} - {description}")
            else:
                stats["unchanged"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"  Error: {path.name} - {e}")

    print(f"\nSummary: {stats['modified']} modified, {stats['unchanged']} unchanged, {stats['errors']} errors")

    return stats


if __name__ == "__main__":
    main()

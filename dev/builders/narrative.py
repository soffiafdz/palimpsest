#!/usr/bin/env python3
"""
narrative.py
------------
Builders for narrative analysis review documents.

Provides document compilation for the narrative analysis review workflow:
- compile_review: Entry → Scene → Event → Arc hierarchy
- compile_source_review: Analysis metadata + original journal text
- compile_timeline: Pure analysis compilation by time period
- extract_unmapped_scenes: Generate unmapped scenes checklists
- compile_events_view: Create event-centric validation view

These builders generate markdown and PDF documents for reviewing and
curating scene/event/arc assignments.

Key Features:
    - Hierarchical review documents showing Entry→Scene→Event→Arc structure
    - Source review documents combining analysis with original journal text
    - Timeline compilations for reading analysis in chronological order
    - Unmapped scene extraction for curation checklists
    - Event-centric views for validation

Usage:
    from dev.builders.narrative import compile_review, compile_source_review
    from dev.core.paths import NARRATIVE_ANALYSIS_DIR

    # Generate core story review
    compile_review("core", NARRATIVE_ANALYSIS_DIR, pdf=True)

    # Generate source review
    compile_source_review("flashback", NARRATIVE_ANALYSIS_DIR, pdf=True)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import calendar
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Third party imports ---
from pypandoc import convert_file

# --- Local imports ---
from dev.core.paths import (
    EVENTS_DIR,
    JOURNAL_DIR,
    NARRATIVE_ANALYSIS_DIR,
    TEX_DIR,
    TMP_DIR,
)

# Default output directories
REVIEW_DIR = NARRATIVE_ANALYSIS_DIR / "_review"
"""Directory for review PDFs and working documents."""
from dev.utils.narrative import (
    CORE_MONTHS,
    CORE_RANGE,
    FLASHBACK_MONTHS,
    FLASHBACK_RANGE,
    build_scene_event_mapping,
    format_arc,
    fuzzy_match_scene,
    parse_events_file_full,
    parse_scenes,
)
from dev.utils.md import extract_section_text, split_frontmatter


# ============================================================================
# PDF Building
# ============================================================================

def build_pdf(md_path: Path, pdf_path: Path, use_notes_preamble: bool = False) -> None:
    """
    Convert markdown to PDF using pandoc with tectonic engine.

    Args:
        md_path: Source markdown file
        pdf_path: Output PDF file
        use_notes_preamble: If True, use preamble_notes.tex for wide margins
                            and line numbers (for annotation)
    """
    preamble_name = "preamble_notes.tex" if use_notes_preamble else "preamble.tex"
    preamble = TEX_DIR / preamble_name

    if not preamble.exists():
        raise FileNotFoundError(f"Preamble not found: {preamble}")

    args = [
        "--from", "markdown",
        "--pdf-engine", "tectonic",
        "--include-in-header", str(preamble),
        "--variable", "documentclass:extarticle",
        "--variable", "fontsize:10pt",
    ]

    # Notes preamble has its own margins; standard needs explicit
    if not use_notes_preamble:
        args.extend(["--variable", "geometry:margin=0.75in"])

    convert_file(str(md_path), to="pdf", outputfile=str(pdf_path), extra_args=args)


# ============================================================================
# Review Document Compiler
# ============================================================================

def _extract_thematic_arcs(content: str) -> List[str]:
    """Extract thematic arcs from an analysis file."""
    arcs_section = extract_section_text(content, "Thematic Arcs")
    if not arcs_section:
        return []
    return [a.strip() for a in arcs_section.split(",") if a.strip()]


def _format_entry_review(
    date_str: str,
    summary: str,
    scenes: List[Tuple[str, str]],
    entry_arcs: List[str],
    scene_event_map: Dict[str, Dict[str, Any]]
) -> str:
    """Format a single entry with full hierarchy for review."""
    parts = []
    parts.append(f"## {date_str}")
    parts.append("")

    # Summary
    parts.append("### Summary")
    parts.append("")
    parts.append(summary)
    parts.append("")

    # Entry-level arcs
    if entry_arcs:
        formatted_arcs = [f"**{format_arc(a)}**" for a in entry_arcs]
        parts.append(f"**Entry Arcs**: {', '.join(formatted_arcs)}")
        parts.append("")

    # Scenes with event mapping
    parts.append("### Scenes")
    parts.append("")

    for i, (title, description) in enumerate(scenes, 1):
        parts.append(f"{i}. **{title}** — {description}")

        # Look up event for this scene
        event_info = fuzzy_match_scene(title, scene_event_map)

        if event_info:
            parts.append(f"   - *Event*: {event_info['event_name']}")
            if event_info['arcs']:
                arc_str = ", ".join(format_arc(a) for a in event_info['arcs'])
                parts.append(f"   - *Arcs*: {arc_str}")
        else:
            parts.append("   - *Event*: [!] **NOT MAPPED**")

        parts.append("")

    return "\n".join(parts)


def compile_review(
    period: str,
    output_dir: Optional[Path] = None,
    pdf: bool = False
) -> Path:
    """
    Compile consolidated review document showing Entry→Scene→Event→Arc hierarchy.

    Creates a PDF for reviewing the narrative analysis structure. Each entry
    shows its summary, scenes with event assignments, and thematic arc mappings.

    Args:
        period: Either "core" or "flashback"
        output_dir: Output directory for PDF (default: REVIEW_DIR)
        pdf: If True, generate PDF (default behavior outputs to review dir)

    Returns:
        Path to the generated PDF file (or markdown if pdf=False)
    """
    output_dir = output_dir or REVIEW_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if period == "core":
        date_range = CORE_RANGE
        title = "Scenes/Events/Arcs Review: Core Story"
        subtitle = "November 2024 – December 2025"
        output_name = "core_review"
    elif period == "flashback":
        date_range = FLASHBACK_RANGE
        title = "Scenes/Events/Arcs Review: Flashback Material"
        subtitle = "2015 – October 2024"
        output_name = "flashback_review"
    else:
        raise ValueError(f"Invalid period: {period}. Must be 'core' or 'flashback'")

    parts = []

    # YAML frontmatter
    parts.append("---")
    parts.append(f"title: '{title}'")
    parts.append(f"subtitle: '{subtitle}'")
    parts.append("author: 'Palimpsest Project'")
    parts.append("---")
    parts.append("")

    # Build scene-to-event mapping
    scene_event_mapping = build_scene_event_mapping(EVENTS_DIR, date_range)

    entry_count = 0
    current_year = None
    current_month = None
    first_month = True

    for year in sorted(date_range.keys()):
        year_dir = NARRATIVE_ANALYSIS_DIR / year
        if not year_dir.exists():
            continue

        for month in date_range[year]:
            month_key = f"{year}-{month}"
            month_events = scene_event_mapping.get(month_key, {})

            # Find analysis files
            pattern = f"{year}-{month}-*_analysis.md"
            files = sorted(year_dir.glob(pattern))

            if not files:
                continue

            # Year header
            if year != current_year:
                parts.append(f"""
\\newpage
\\thispagestyle{{empty}}
\\vspace*{{\\fill}}
\\begin{{center}}
{{\\Huge\\bfseries {year}}}
\\end{{center}}
\\vspace*{{\\fill}}
\\newpage

""")
                current_year = year
                current_month = None
                first_month = True

            # Month header
            if month != current_month:
                month_name = calendar.month_name[int(month)]
                if first_month:
                    parts.append(f"# {month_name} {year}\n\n")
                else:
                    parts.append(f"\n\\newpage\n\n# {month_name} {year}\n\n")
                current_month = month
                first_month = False

            # Process entries
            for file_path in files:
                date_str = file_path.stem.replace("_analysis", "")
                content = file_path.read_text(encoding="utf-8")

                summary = extract_section_text(content, "Summary") or "*No summary*"
                scenes_text = extract_section_text(content, "Scenes") or ""
                entry_arcs = _extract_thematic_arcs(content)
                scenes = parse_scenes(scenes_text)

                if not scenes:
                    continue

                parts.append(_format_entry_review(
                    date_str, summary, scenes, entry_arcs, month_events
                ))
                parts.append("---\n")
                entry_count += 1

    # Table of contents
    parts.append("\n\\newpage\n")
    parts.append("\\setcounter{tocdepth}{2}")
    parts.append("\\tableofcontents")

    content = "\n".join(parts)

    if pdf:
        # Use temp file for intermediate markdown
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        pdf_path = output_dir / f"{output_name}.pdf"
        build_pdf(tmp_path, pdf_path)
        tmp_path.unlink()  # Delete temp file
        return pdf_path
    else:
        # Only save markdown if explicitly not generating PDF
        output_path = output_dir / f"{output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path


# ============================================================================
# Source Review Document Compiler
# ============================================================================

def _format_analysis_block(
    summary: str,
    scenes: List[Tuple[str, str]],
    entry_arcs: List[str],
    scene_event_map: Dict[str, Dict[str, Any]]
) -> str:
    """Format analysis metadata block for source review."""
    parts = []

    parts.append(":::{.analysis-block}")
    parts.append("**NARRATIVE ANALYSIS**")
    parts.append("")

    # Summary (truncated)
    if summary and len(summary) > 300:
        summary = summary[:297] + "..."
    parts.append(f"*Summary*: {summary}")
    parts.append("")

    # Entry arcs
    if entry_arcs:
        formatted_arcs = [format_arc(a) for a in entry_arcs]
        parts.append(f"*Entry Arcs*: {', '.join(formatted_arcs)}")
        parts.append("")

    # Scenes with events
    parts.append("**Scenes:**")
    parts.append("")

    for i, (title, description) in enumerate(scenes, 1):
        event_info = fuzzy_match_scene(title, scene_event_map)

        if event_info:
            event_name = event_info['event_name']
            arcs_str = ""
            if event_info['arcs']:
                arcs_str = " | " + ", ".join(format_arc(a) for a in event_info['arcs'][:3])
            parts.append(f"{i}. **{title}** → _{event_name}_{arcs_str}")
        else:
            parts.append(f"{i}. **{title}** → [NOT MAPPED]")

    parts.append("")
    parts.append(":::")
    parts.append("")
    parts.append("---")
    parts.append("")

    return "\n".join(parts)


def compile_source_review(
    period: str,
    output_dir: Optional[Path] = None,
    pdf: bool = False
) -> Path:
    """
    Compile source review document with analysis metadata + journal text.

    Creates a PDF for validating scene accuracy against source text.
    Each entry shows the narrative analysis block followed by the original
    journal entry text. Uses wide margins and line numbers for annotation.

    Args:
        period: Either "core" or "flashback"
        output_dir: Output directory for PDF (default: REVIEW_DIR)
        pdf: If True, generate PDF (default behavior outputs to review dir)

    Returns:
        Path to the generated PDF file (or markdown if pdf=False)
    """
    output_dir = output_dir or REVIEW_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    journal_md_dir = JOURNAL_DIR / "content" / "md"

    if period == "core":
        date_range = CORE_RANGE
        title = "Source Review: Core Story"
        subtitle = "November 2024 – December 2025"
        output_name = "core_source_review"
    elif period == "flashback":
        date_range = FLASHBACK_RANGE
        title = "Source Review: Flashback Material"
        subtitle = "2015 – October 2024"
        output_name = "flashback_source_review"
    else:
        raise ValueError(f"Invalid period: {period}. Must be 'core' or 'flashback'")

    parts = []

    # YAML frontmatter
    parts.append("---")
    parts.append(f"title: '{title}'")
    parts.append(f"date: '{subtitle}'")
    parts.append("author: 'Palimpsest Project'")
    parts.append("---")
    parts.append("")

    # Build scene-to-event mapping
    scene_event_mapping = build_scene_event_mapping(EVENTS_DIR, date_range)

    entry_count = 0
    current_year = None
    current_month = None
    first_month = True

    for year in sorted(date_range.keys()):
        analysis_year_dir = NARRATIVE_ANALYSIS_DIR / year
        journal_year_dir = journal_md_dir / year

        if not analysis_year_dir.exists() or not journal_year_dir.exists():
            continue

        for month in date_range[year]:
            month_key = f"{year}-{month}"
            month_events = scene_event_mapping.get(month_key, {})

            # Find analysis files
            pattern = f"{year}-{month}-*_analysis.md"
            analysis_files = sorted(analysis_year_dir.glob(pattern))

            if not analysis_files:
                continue

            # Year header
            if year != current_year:
                parts.append(f"""
\\newpage
\\nolinenumbers
\\thispagestyle{{empty}}
\\vspace*{{\\fill}}
\\begin{{center}}
{{\\Huge\\bfseries {year}}}
\\end{{center}}
\\vspace*{{\\fill}}
\\newpage
\\linenumbers

""")
                current_year = year
                current_month = None
                first_month = True

            # Month header
            if month != current_month:
                month_name = calendar.month_name[int(month)]
                if first_month:
                    parts.append(f"# {month_name} {year}\n\n")
                else:
                    parts.append(f"\n\\newpage\n\n# {month_name} {year}\n\n")
                current_month = month
                first_month = False

            # Process entries
            for analysis_path in analysis_files:
                date_str = analysis_path.stem.replace("_analysis", "")
                journal_path = journal_year_dir / f"{date_str}.md"

                if not journal_path.exists():
                    continue

                # Read analysis
                analysis_content = analysis_path.read_text(encoding="utf-8")
                summary = extract_section_text(analysis_content, "Summary") or ""
                scenes_text = extract_section_text(analysis_content, "Scenes") or ""
                entry_arcs = _extract_thematic_arcs(analysis_content)
                scenes = parse_scenes(scenes_text)

                if not scenes:
                    continue

                # Read journal entry
                journal_content = journal_path.read_text(encoding="utf-8")
                _, journal_body_lines = split_frontmatter(journal_content)
                journal_body = "\n".join(journal_body_lines)

                # Reset line counter
                parts.append("\\setcounter{linenumber}{1}\n")

                # Entry header
                parts.append(f"## {date_str}\n\n")

                # Analysis block
                parts.append(_format_analysis_block(
                    summary, scenes, entry_arcs, month_events
                ))

                # Journal source text
                parts.append("**SOURCE TEXT:**\n\n")
                parts.append(journal_body.strip())
                parts.append("\n\n---\n\n")

                entry_count += 1

    # TOC at end
    parts.append("\n\\newpage\n\\nolinenumbers\n")
    parts.append("\\setcounter{tocdepth}{2}")
    parts.append("\\tableofcontents")

    content = "\n".join(parts)

    if pdf:
        # Use temp file for intermediate markdown
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        pdf_path = output_dir / f"{output_name}.pdf"
        build_pdf(tmp_path, pdf_path, use_notes_preamble=True)
        tmp_path.unlink()  # Delete temp file
        return pdf_path
    else:
        # Only save markdown if explicitly not generating PDF
        output_path = output_dir / f"{output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path


# ============================================================================
# Timeline Document Compiler
# ============================================================================

def _format_timeline_entry(file_path: Path, first_in_month: bool = False) -> str:
    """Format a single analysis entry for timeline compilation."""
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Parse sections
    sections: Dict[str, List[str]] = {}
    current_section = None
    current_lines: List[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_section:
                sections[current_section] = current_lines
            current_section = line[3:].strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)

    if current_section:
        sections[current_section] = current_lines

    # Build output with transformations
    output_lines = []
    skip_sections = {"Cleaned Tags", "Thematic Arcs", "Tag Categories", "Tags", "Themes"}
    current_in_section: Optional[str] = None

    for line in lines:
        if line.startswith("# "):
            # Main title - demote
            current_in_section = None
            output_lines.append("##" + line[1:])

        elif line.startswith("## "):
            section_name = line[3:].strip()
            current_in_section = section_name

            if section_name == "Tags":
                # Replace with Cleaned Tags content
                output_lines.append("### Tags")
                output_lines.append("")
                if "Cleaned Tags" in sections:
                    output_lines.extend(sections["Cleaned Tags"])
                elif "Tags" in sections:
                    output_lines.extend(sections["Tags"])

            elif section_name == "Themes":
                # Combine Thematic Arcs + original Themes
                output_lines.append("### Themes")
                output_lines.append("")

                if "Thematic Arcs" in sections:
                    arcs_text = "\n".join(sections["Thematic Arcs"]).strip()
                    if arcs_text:
                        arcs = [a.strip() for a in arcs_text.split(",")]
                        formatted_arcs = [f"**{a.title().replace('_', ' ')}**" for a in arcs if a]
                        output_lines.append(", ".join(formatted_arcs))
                        output_lines.append("")

                if "Themes" in sections:
                    output_lines.extend(sections["Themes"])

            elif section_name in ["Cleaned Tags", "Thematic Arcs", "Tag Categories"]:
                pass  # Skip

            else:
                output_lines.append("###" + line[2:])

        elif line.startswith("### "):
            current_in_section = None
            output_lines.append("####" + line[3:])

        else:
            if current_in_section in skip_sections:
                continue
            output_lines.append(line)

    if first_in_month:
        return "\n".join(output_lines)
    return "\\newpage\n\n" + "\n".join(output_lines)


def compile_timeline(
    period: str,
    output_dir: Optional[Path] = None,
    pdf: bool = False
) -> Path:
    """
    Compile timeline document with pure analysis content.

    Creates a chronologically ordered compilation of narrative analyses
    for reading through. Transforms sections for readability.

    These are for reading, not for review, so they output to TMP_DIR by default.

    Args:
        period: "core", "early_transition", or "montreal_life"
        output_dir: Output directory for PDF (default: TMP_DIR)
        pdf: If True, generate PDF

    Returns:
        Path to the generated PDF file (or markdown if pdf=False)
    """
    output_dir = output_dir or TMP_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define date ranges for different periods
    if period == "core":
        date_range = {
            "2024": ["11", "12"],
            "2025": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"],
        }
        coda_range = {"2025": ["11", "12"]}
        title = "Narrative Analyses: Core Story"
        output_name = "core_analyses_compiled"
        include_coda = True
    elif period == "early_transition":
        date_range = {
            "2015": ["08", "09", "10", "11", "12"],
            "2016": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
            "2017": ["01", "02", "06"],
            "2018": ["12"],
            "2019": ["01", "02"],
        }
        coda_range = {}
        title = "Narrative Analyses: Early Transition"
        output_name = "early_transition_compiled"
        include_coda = False
    elif period == "montreal_life":
        date_range = {
            "2021": ["08", "09", "10", "11", "12"],
            "2022": ["01", "02", "03", "04", "06", "07", "11"],
            "2023": ["06"],
            "2024": ["01", "02", "03", "04", "05", "06", "07"],
        }
        coda_range = {}
        title = "Narrative Analyses: Montreal Life"
        output_name = "montreal_life_compiled"
        include_coda = False
    else:
        raise ValueError(f"Invalid period: {period}")

    parts = []

    # Document header
    parts.append("---")
    parts.append(f"title: '{title}'")
    parts.append("author: 'Palimpsest Project'")
    parts.append("---")
    parts.append("")

    # Part I: Main content
    if include_coda:
        parts.append(f"""
\\newpage
\\thispagestyle{{empty}}
\\vspace*{{\\fill}}
\\begin{{center}}
{{\\Huge\\bfseries Part I\\\\[0.5em]Core Story\\\\[0.3em]{{\\large November 2024 – October 2025}}}}
\\end{{center}}
\\vspace*{{\\fill}}
\\newpage

""")

    entry_count = 0
    first_month_in_part = True

    for year in sorted(date_range.keys()):
        year_dir = NARRATIVE_ANALYSIS_DIR / year
        if not year_dir.exists():
            continue

        for month in date_range[year]:
            pattern = f"{year}-{month}-*_analysis.md"
            files = sorted(year_dir.glob(pattern))

            if not files:
                continue

            month_name = calendar.month_name[int(month)]
            if first_month_in_part:
                parts.append(f"# {month_name} {year}\n\n")
            else:
                parts.append(f"\n\\newpage\n\n# {month_name} {year}\n\n")
            first_month_in_part = False

            first_entry_in_month = True
            for file_path in files:
                parts.append(_format_timeline_entry(file_path, first_in_month=first_entry_in_month))
                first_entry_in_month = False
                entry_count += 1

    # Part II: Coda (if applicable)
    if include_coda and coda_range:
        parts.append(f"""
\\newpage
\\thispagestyle{{empty}}
\\vspace*{{\\fill}}
\\begin{{center}}
{{\\Huge\\bfseries Part II\\\\[0.5em]Coda / Epilogue\\\\[0.3em]{{\\large November – December 2025}}}}
\\end{{center}}
\\vspace*{{\\fill}}
\\newpage

""")
        first_month_in_part = True

        for year in sorted(coda_range.keys()):
            year_dir = NARRATIVE_ANALYSIS_DIR / year
            if not year_dir.exists():
                continue

            for month in coda_range[year]:
                pattern = f"{year}-{month}-*_analysis.md"
                files = sorted(year_dir.glob(pattern))

                if not files:
                    continue

                month_name = calendar.month_name[int(month)]
                if first_month_in_part:
                    parts.append(f"# {month_name} {year}\n\n")
                else:
                    parts.append(f"\n\\newpage\n\n# {month_name} {year}\n\n")
                first_month_in_part = False

                first_entry_in_month = True
                for file_path in files:
                    parts.append(_format_timeline_entry(file_path, first_in_month=first_entry_in_month))
                    first_entry_in_month = False
                    entry_count += 1

    # Table of contents
    parts.append("\n\\newpage\n")
    parts.append("\\setcounter{tocdepth}{1}")
    parts.append("\\tableofcontents")

    content = "\n".join(parts)

    if pdf:
        # Use temp file for intermediate markdown
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        pdf_path = output_dir / f"{output_name}.pdf"
        build_pdf(tmp_path, pdf_path)
        tmp_path.unlink()  # Delete temp file
        return pdf_path
    else:
        # Only save markdown if explicitly not generating PDF
        output_path = output_dir / f"{output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path


# ============================================================================
# Unmapped Scenes Extractor
# ============================================================================

def extract_unmapped_scenes(
    review_file: Path,
    output_dir: Path,
    title: str,
    output_name: str,
    pdf: bool = False
) -> Tuple[int, Path]:
    """
    Extract unmapped scenes from a review document into a checklist.

    Parses a review document and extracts all scenes marked as "NOT MAPPED",
    organizing them by month for easy curation.

    Args:
        review_file: Path to review document (e.g., core_review.md)
        output_dir: Directory for output file
        title: Title for the checklist document
        output_name: Base name for output file (without extension)
        pdf: If True, generate PDF instead of markdown

    Returns:
        Tuple of (unmapped_count, output_path)
    """
    source_content = review_file.read_text(encoding="utf-8")

    current_date = None
    unmapped: List[Tuple[str, str]] = []

    lines = source_content.split('\n')
    for i, line in enumerate(lines):
        # Match date headers
        if line.startswith('## 20'):
            current_date = line[3:].strip()
        # Match unmapped scenes
        elif '[!] **NOT MAPPED**' in line or '[NOT MAPPED]' in line:
            # Look back for the scene line
            for j in range(i-1, max(0, i-5), -1):
                scene_match = re.match(r'\d+\.\s*\*\*(.+?)\*\*', lines[j])
                if scene_match:
                    scene_title = scene_match.group(1)
                    unmapped.append((current_date or "Unknown", scene_title))
                    break

    # Group by month
    by_month: Dict[str, List[Tuple[str, str]]] = {}
    for date, scene in unmapped:
        month = date[:7]  # YYYY-MM
        if month not in by_month:
            by_month[month] = []
        by_month[month].append((date, scene))

    # Build content
    parts = []
    parts.append(f"# {title}")
    parts.append("")
    parts.append(f"**Total unmapped scenes: {len(unmapped)}**")
    parts.append("")
    parts.append("Use this checklist to assign scenes to events.")
    parts.append("Mark with [x] when resolved.")
    parts.append("")
    parts.append("---")
    parts.append("")

    for month in sorted(by_month.keys()):
        parts.append(f"## {month}")
        parts.append("")
        for date, scene in by_month[month]:
            parts.append(f"- [ ] **{date}**: {scene}")
        parts.append("")

    content = "\n".join(parts)

    if pdf:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        pdf_path = output_dir / f"{output_name}.pdf"
        build_pdf(tmp_path, pdf_path)
        tmp_path.unlink()
        return len(unmapped), pdf_path
    else:
        output_path = output_dir / f"{output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        return len(unmapped), output_path


# ============================================================================
# Events View Compiler
# ============================================================================

def compile_events_view(
    period: str,
    output_dir: Path,
    title: str,
    output_name: str,
    pdf: bool = False
) -> Tuple[int, Path]:
    """
    Compile event-centric validation view.

    Creates a document showing each event with all its contributing scenes
    for easy validation of event groupings.

    Args:
        period: Either "core" or "flashback"
        output_dir: Directory for output file
        title: Title for the document
        output_name: Base name for output file (without extension)
        pdf: If True, generate PDF instead of markdown

    Returns:
        Tuple of (event_count, output_path)
    """
    months = CORE_MONTHS if period == "core" else FLASHBACK_MONTHS
    all_events: List[Dict[str, Any]] = []

    for month in months:
        events_file = EVENTS_DIR / f"events_{month}.md"
        if events_file.exists():
            events = parse_events_file_full(events_file)
            for e in events:
                e['month'] = month
            all_events.extend(events)

    # Build content
    parts = []
    parts.append(f"# {title}")
    parts.append("")
    parts.append(f"**Total events: {len(all_events)}**")
    parts.append("")
    parts.append("Use this view to validate event groupings.")
    parts.append("Check: Are all scenes correctly assigned to this event?")
    parts.append("")
    parts.append("---")
    parts.append("")

    current_month = None
    for event in all_events:
        if event['month'] != current_month:
            current_month = event['month']
            parts.append(f"## {current_month}")
            parts.append("")

        parts.append(f"### {event['name']}")
        parts.append("")
        parts.append(f"**Entries**: {', '.join(event['entries'])}")
        parts.append("")

        if event['arcs']:
            arcs_formatted = [format_arc(a) for a in event['arcs']]
            parts.append(f"**Arcs**: {', '.join(arcs_formatted)}")
            parts.append("")

        parts.append("**Scenes**:")
        parts.append("")
        for scene in event['scenes']:
            parts.append(f"- {scene}")
        parts.append("")
        parts.append("---")
        parts.append("")

    content = "\n".join(parts)

    if pdf:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        pdf_path = output_dir / f"{output_name}.pdf"
        build_pdf(tmp_path, pdf_path)
        tmp_path.unlink()
        return len(all_events), pdf_path
    else:
        output_path = output_dir / f"{output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        return len(all_events), output_path

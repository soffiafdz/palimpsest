#!/usr/bin/env python3
"""
metadata_pdfbuilder.py
----------------------
Builder for metadata curation PDF generation.

Orchestrates the process of formatting YAML metadata into readable two-column
PDFs for manuscript curation decisions. Handles arc tracking, formatting, and
Pandoc compilation.

Key Components:
    - MetadataPdfBuilder: Main orchestrator
    - Formatting helpers: format_rating, format_scene, format_thread, etc.
    - Arc tracking: Detects arc changes and injects markers
    - Monthly organization: Groups entries by month

Usage:
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=JOURNAL_YAML_DIR,
        pdf_dir=PDF_DIR,
        preamble=TEX_DIR / "preamble_metadata.tex",
        logger=logger
    )
    stats = builder.build()

Dependencies:
    - MetadataEntry: YAML parsing
    - TemporalFileManager: Temp file cleanup
    - pypandoc: PDF generation
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import calendar
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

# --- Third party imports ---
from pypandoc import convert_file

# --- Local imports ---
from dev.builders.base import BuilderStats as BaseStats
from dev.core.exceptions import PdfBuildError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.temporal_files import TemporalFileManager
from dev.dataclasses.metadata_entry import MetadataEntry, SceneSpec, ThreadSpec


# --- LaTeX Command Constants ---

LATEX_NEWPAGE = "\\newpage\n\n"
"""LaTeX command to insert a page break."""

LATEX_MULTICOLS_BEGIN = "\\begin{multicols}{2}\n\n"
"""LaTeX command to start two-column layout."""

LATEX_MULTICOLS_END = "\\end{multicols}\n\n"
"""LaTeX command to end two-column layout."""

LATEX_COLUMN_BREAK = "\\columnbreak\n\n"
"""LaTeX command to force column break."""

LATEX_TOC = "\\tableofcontents\n"
"""LaTeX command to generate table of contents."""

PANDOC_ENGINE = "tectonic"
"""Pandoc PDF engine (tectonic is self-contained)."""

PANDOC_DOCUMENT_CLASS = "extarticle"
"""LaTeX document class for PDF generation."""

PDF_TITLE = "Palimpsest"
"""Default title for generated PDFs."""

PDF_SUBTITLE = "Manuscript Curation"
"""Subtitle for metadata PDFs."""

PDF_AUTHOR = "Sofía F."
"""Default author name for generated PDFs."""


# --- Formatting Helpers ---


def escape_latex(text: str) -> str:
    """
    Escape special LaTeX characters in text.

    Args:
        text: Text containing potential LaTeX special characters

    Returns:
        Text with special characters properly escaped
    """
    if not text:
        return text

    # Convert to string if not already
    if not isinstance(text, str):
        text = str(text)

    # Order matters - backslash must be first
    replacements = [
        ("\\", "\\textbackslash{}"),
        ("&", "\\&"),
        ("%", "\\%"),
        ("$", "\\$"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
    ]

    result = text
    for char, replacement in replacements:
        result = result.replace(char, replacement)

    return result


def format_rating(rating: Optional[float]) -> str:
    """
    Format numeric rating as star symbols.

    Converts rating to star display: ⭐⭐⭐⭐½

    Args:
        rating: Numeric rating (0-5) or None

    Returns:
        Formatted star string or empty string if None

    Examples:
        >>> format_rating(4.5)
        '⭐⭐⭐⭐½'
        >>> format_rating(3.0)
        '⭐⭐⭐'
        >>> format_rating(None)
        ''
    """
    if rating is None:
        return ""

    full_stars = int(rating)
    half_star = (rating - full_stars) >= 0.5

    stars = "⭐" * full_stars
    if half_star:
        stars += "½"

    return stars


def format_scene(scene: SceneSpec, index: int) -> str:
    """
    Format a single scene for display.

    Creates numbered list item with metadata bullets.

    Args:
        scene: Scene specification dictionary
        index: Scene number (1-indexed)

    Returns:
        Formatted markdown string

    Example:
        1. **Scene Name**
           - Date: 2025-02-25
           - People: Sarah
           - Location: Tandoori Palace
           - Description text...
    """
    lines = []
    lines.append(f"{index}. **{scene.get('name', 'Unnamed Scene')}**")

    # Date
    scene_date = scene.get("date")
    if scene_date:
        if isinstance(scene_date, list):
            date_str = ", ".join(str(d) for d in scene_date)
        else:
            date_str = str(scene_date)
        lines.append(f"   - Date: {date_str}")

    # People
    people = scene.get("people", [])
    if people:
        lines.append(f"   - People: {', '.join(people)}")

    # Locations
    locations = scene.get("locations", [])
    if locations:
        lines.append(f"   - Location: {', '.join(locations)}")

    # Description
    description = scene.get("description", "")
    if description:
        # Indent description paragraphs
        desc_lines = description.split("\n")
        for desc_line in desc_lines:
            if desc_line.strip():
                lines.append(f"   - {desc_line.strip()}")

    return "\n".join(lines)


def format_thread(thread: ThreadSpec) -> str:
    """
    Format a single thread for display.

    Creates clean paragraph with name, date range, and connection.

    Args:
        thread: Thread specification dictionary

    Returns:
        Formatted markdown string
    """
    lines = []

    # Thread name (bold, uppercase for prominence)
    name = thread.get("name", "Unnamed Thread")
    lines.append(f"**{name.upper()}**")

    # Date range (italic, compact)
    from_date = thread.get("from_", "")
    to_date = thread.get("to", "")
    lines.append(f"*{from_date} → {to_date}*")

    # People and locations (if present)
    people = thread.get("people", [])
    locations = thread.get("locations", [])
    if people or locations:
        meta_parts = []
        if people:
            meta_parts.append(", ".join(people))
        if locations:
            meta_parts.append(f"at {', '.join(locations)}")
        lines.append(f"{' — '.join(meta_parts)}")

    # Connection content
    content = thread.get("content", "")
    if content:
        lines.append(content)

    # Entry reference (if present)
    entry = thread.get("entry")
    if entry:
        lines.append(f"*→ Entry: {entry}*")

    return "\n".join(lines)


def format_entry_metadata(entry: MetadataEntry) -> str:
    """
    Format complete entry metadata with professional layout design.

    Layout structure:
    - Date header with arc tags
    - Two-column: Summary (left) | Rating + Justification (right)
    - Full-width: Events & Scenes with proper punctuation
    - Multi-column: Themes, Motifs, Threads
    - Single-line: Tags

    Args:
        entry: MetadataEntry instance

    Returns:
        Formatted markdown string
    """
    lines = []

    # === HEADER: Date (largest) ===
    date_str = entry.date.isoformat()
    lines.append("```{=latex}")
    lines.append(f"{{\\Huge\\bfseries {date_str}}}")
    lines.append("")
    lines.append("\\vspace{0.5em}")
    lines.append("```")
    lines.append("")

    # Arc tags (bold and prominent)
    if entry.arcs:
        arc_str = " • ".join(entry.arcs)
        lines.append("```{=latex}")
        lines.append(f"{{\\large\\bfseries {escape_latex(arc_str)}}}")
        lines.append("")
        lines.append("\\vspace{0.8em}")
        lines.append("```")
        lines.append("")

    # === SECTION 1: Summary + Rating (60/40 split using minipage) ===
    lines.append("```{=latex}")
    lines.append("\\begin{minipage}[t]{0.58\\textwidth}")
    lines.append("```")
    lines.append("")

    # Left column: Summary (keep markdown so Pandoc processes it)
    if entry.summary:
        lines.append(entry.summary)
    else:
        lines.append("*No summary*")

    lines.append("")
    lines.append("```{=latex}")
    lines.append("\\end{minipage}")
    lines.append("\\hfill")
    lines.append("\\begin{minipage}[t]{0.38\\textwidth}")
    lines.append("```")
    lines.append("")

    # Right column: Rating stars (centered and large) + Justification
    if entry.rating:
        rating_str = format_rating(entry.rating)
        lines.append("```{=latex}")
        lines.append("\\begin{center}")
        lines.append(f"{{\\LARGE {rating_str}}}")
        lines.append("\\end{center}")
        lines.append("\\vspace{0.5em}")
        lines.append("```")
        lines.append("")

    if entry.rating_justification:
        lines.append("```{=latex}")
        lines.append(f"{{\\normalsize\\itshape {escape_latex(entry.rating_justification)}}}")
        lines.append("")
        lines.append("```")
        lines.append("")

    lines.append("```{=latex}")
    lines.append("\\end{minipage}")
    lines.append("\\vspace{1.5em}")
    lines.append("```")
    lines.append("")

    # === SECTION 2: Events & Scenes (Full width) ===
    if entry.events and entry.scenes:
        lines.append("```{=latex}")
        lines.append("{\\LARGE\\bfseries Events \\& Scenes}")
        lines.append("")
        lines.append("\\vspace{0.5em}")
        lines.append("```")
        lines.append("")

        # Create scene lookup
        scene_map = {s.get("name", ""): s for s in entry.scenes}

        for event in entry.events:
            event_name = event.get("name", "")
            event_scenes = event.get("scenes", [])

            if event_name:
                # Event name (bold, smaller than section header)
                lines.append("```{=latex}")
                lines.append(f"{{\\large\\bfseries {escape_latex(event_name)}}}")
                lines.append("")
                lines.append("\\vspace{0.4em}")
                lines.append("```")
                lines.append("")

                # List scenes under this event
                for scene_name in event_scenes:
                    scene = scene_map.get(scene_name)
                    if scene:
                        # Scene title (italic and larger)
                        lines.append("```{=latex}")
                        lines.append(f"{{\\large\\itshape {escape_latex(scene_name)}}}")
                        lines.append("")
                        lines.append("```")

                        # Scene metadata line (no labels, just values)
                        meta_parts = []

                        scene_date = scene.get("date")
                        if scene_date:
                            if isinstance(scene_date, list):
                                date_str_compact = ", ".join(str(d) for d in scene_date)
                            else:
                                date_str_compact = str(scene_date)
                            meta_parts.append(date_str_compact)

                        people = scene.get("people", [])
                        if people:
                            people_escaped = [escape_latex(p) for p in people]
                            meta_parts.append(", ".join(people_escaped))

                        locations = scene.get("locations", [])
                        if locations:
                            locations_escaped = [escape_latex(loc) for loc in locations]
                            meta_parts.append(", ".join(locations_escaped))

                        if meta_parts:
                            lines.append("```{=latex}")
                            lines.append(f"{{\\small\\itshape {' | '.join(meta_parts)}}}")
                            lines.append("```")

                        # Description (separate paragraph with spacing)
                        description = scene.get("description", "")
                        if description:
                            lines.append("")
                            lines.append(escape_latex(description))

                        lines.append("")
                        lines.append("```{=latex}")
                        lines.append("\\vspace{0.8em}")
                        lines.append("```")
                        lines.append("")

                # Space between events
                lines.append("```{=latex}")
                lines.append("\\vspace{0.5em}")
                lines.append("```")
                lines.append("")

    elif entry.scenes:
        # No events, just list scenes
        lines.append("```{=latex}")
        lines.append("{\\LARGE\\bfseries Scenes}")
        lines.append("")
        lines.append("\\vspace{0.5em}")
        lines.append("```")
        lines.append("")

        for scene in entry.scenes:
            scene_name = scene.get("name", "Unnamed Scene")
            lines.append("```{=latex}")
            lines.append(f"{{\\large\\itshape {escape_latex(scene_name)}}}")
            lines.append("")
            lines.append("```")

            # Scene metadata (no labels)
            meta_parts = []

            scene_date = scene.get("date")
            if scene_date:
                if isinstance(scene_date, list):
                    date_str_compact = ", ".join(str(d) for d in scene_date)
                else:
                    date_str_compact = str(scene_date)
                meta_parts.append(date_str_compact)

            people = scene.get("people", [])
            if people:
                people_escaped = [escape_latex(p) for p in people]
                meta_parts.append(", ".join(people_escaped))

            locations = scene.get("locations", [])
            if locations:
                locations_escaped = [escape_latex(loc) for loc in locations]
                meta_parts.append(", ".join(locations_escaped))

            if meta_parts:
                lines.append("```{=latex}")
                lines.append(f"{{\\small\\itshape {' | '.join(meta_parts)}}}")
                lines.append("```")

            description = scene.get("description", "")
            if description:
                lines.append("")
                lines.append(escape_latex(description))

            lines.append("")
            lines.append("```{=latex}")
            lines.append("\\vspace{0.8em}")
            lines.append("```")
            lines.append("")

    # === SECTION 3: Motifs, Threads, Themes+Tags (Multi-column, conditional page break) ===
    has_themes = bool(entry.themes)
    has_motifs = bool(entry.motifs)
    has_threads = bool(entry.threads)
    has_tags = bool(entry.tags)

    if has_themes or has_motifs or has_threads:
        # Conditional page break - only break if there isn't enough space (8cm minimum)
        lines.append("```{=latex}")
        lines.append("\\vspace{2em}")
        lines.append("\\Needspace{8cm}")
        lines.append("```")
        lines.append("")

        # Determine column count (3 if threads exist, 2 otherwise)
        num_cols = 3 if has_threads else 2

        # Use raggedcolumns to prevent stretching and balancing
        lines.append("```{=latex}")
        lines.append("\\raggedcolumns")
        lines.append(f"\\begin{{multicols}}{{{num_cols}}}")
        lines.append("```")
        lines.append("")

        # Column 1: Motifs
        if has_motifs:
            lines.append("```{=latex}")
            lines.append("{\\bfseries\\large Motifs}")
            lines.append("")
            lines.append("\\vspace{0.3em}")
            lines.append("```")
            lines.append("")
            for motif in entry.motifs:
                name = motif.get("name", "")
                desc = motif.get("description", "")
                if name:
                    lines.append("```{=latex}")
                    lines.append(f"\\textbf{{{escape_latex(name)}}}")
                    lines.append("```")
                    lines.append("")
                    if desc:
                        lines.append(escape_latex(desc))
                        lines.append("")
                    lines.append("```{=latex}")
                    lines.append("\\vspace{0.5em}")
                    lines.append("```")
                    lines.append("")

        # Column break
        lines.append("```{=latex}")
        lines.append("\\columnbreak")
        lines.append("```")
        lines.append("")

        # Column 2: Threads (if they exist)
        if has_threads:
            lines.append("```{=latex}")
            lines.append("{\\bfseries\\large Threads}")
            lines.append("")
            lines.append("\\vspace{0.3em}")
            lines.append("```")
            lines.append("")
            for thread in entry.threads:
                name = thread.get("name", "")
                from_date = thread.get("from_", "")
                to_date = thread.get("to", "")
                content = thread.get("content", "")

                if name:
                    lines.append("```{=latex}")
                    lines.append(f"\\textbf{{{escape_latex(name)}}}")
                    lines.append("```")
                    lines.append("")

                    lines.append("```{=latex}")
                    lines.append(f"\\textit{{{escape_latex(from_date)} $\\rightarrow$ {escape_latex(to_date)}}}")
                    lines.append("```")
                    lines.append("")

                    if content:
                        lines.append(escape_latex(content))
                        lines.append("")

                    # Entry reference if present
                    entry_ref = thread.get("entry")
                    if entry_ref:
                        lines.append("```{=latex}")
                        lines.append(f"\\textit{{(Entry: {escape_latex(entry_ref)})}}")
                        lines.append("```")
                        lines.append("")

                    # Space between threads
                    lines.append("```{=latex}")
                    lines.append("\\vspace{0.5em}")
                    lines.append("```")
                    lines.append("")

            # Column break after threads
            lines.append("```{=latex}")
            lines.append("\\columnbreak")
            lines.append("```")
            lines.append("")

        # Column 3 (or 2 if no threads): Themes + Tags
        if has_themes:
            lines.append("```{=latex}")
            lines.append("{\\bfseries\\large Themes}")
            lines.append("")
            lines.append("\\vspace{0.3em}")
            lines.append("```")
            lines.append("")
            for theme in entry.themes:
                lines.append(f"• {escape_latex(theme)}")
                lines.append("")

        # Tags in same column as themes
        if has_tags:
            if has_themes:
                lines.append("```{=latex}")
                lines.append("\\vspace{1em}")
                lines.append("```")
                lines.append("")

            lines.append("```{=latex}")
            lines.append("{\\bfseries\\large Tags}")
            lines.append("")
            lines.append("\\vspace{0.3em}")
            lines.append("```")
            lines.append("")

            tags_escaped = [escape_latex(tag) for tag in entry.tags]
            tag_str = " · ".join(tags_escaped)
            lines.append(tag_str)
            lines.append("")

        lines.append("```{=latex}")
        lines.append("\\end{multicols}")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def format_arc_marker(arc_name: str) -> str:
    """
    Format arc marker for prominent display.

    Args:
        arc_name: Name of the arc

    Returns:
        Formatted LaTeX arc marker using raw LaTeX block
    """
    # Use raw LaTeX block so Pandoc passes it through
    return f"```{{=latex}}\n\\arcmarker{{{arc_name}}}\n```\n\n"


# --- Build Statistics ---


class BuildStats(BaseStats):
    """
    Track metadata PDF build statistics.

    Extends BuilderStats base class with PDF-specific metrics.
    """

    def __init__(self) -> None:
        """Initialize metadata PDF build statistics."""
        super().__init__()
        self.files_processed: int = 0
        self.pdfs_created: int = 0
        self.errors: int = 0

    def summary(self) -> str:
        """
        Get formatted summary of metadata PDF build.

        Returns:
            Summary string with file count, PDFs created, errors, and duration
        """
        return (
            f"{self.files_processed} metadata files, "
            f"{self.pdfs_created} PDFs created, "
            f"{self.errors} errors in {self.duration():.2f}s"
        )


# --- Builder Class ---


class MetadataPdfBuilder:
    """
    Build metadata curation PDFs from YAML files.

    Orchestrates the complete process:
    1. Gather YAML metadata files for year
    2. Parse with MetadataEntry
    3. Format with two-column layout
    4. Track arc changes and inject markers
    5. Generate PDF with Pandoc

    Attributes:
        year: Target year (e.g. '2025')
        yaml_dir: Directory containing YYYY/ subdirectories with YAML files
        pdf_dir: Output directory for PDF
        preamble: LaTeX preamble for formatting
        force_overwrite: If True, overwrite existing PDF
        keep_temp_on_error: If True, preserve temp files on error
        logger: Optional logger for operations
    """

    def __init__(
        self,
        year: str,
        yaml_dir: Path,
        pdf_dir: Path,
        preamble: Path,
        force_overwrite: bool = False,
        keep_temp_on_error: bool = True,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize MetadataPdfBuilder.

        Args:
            year: Four-digit year (e.g., '2025')
            yaml_dir: Directory with YYYY/ subdirectories containing YAML files
            pdf_dir: Output directory for PDF
            preamble: Path to LaTeX preamble
            force_overwrite: Overwrite existing PDF
            keep_temp_on_error: Preserve temp files on error for debugging
            logger: Optional logger
        """
        self.year = year
        self.yaml_dir = yaml_dir
        self.pdf_dir = pdf_dir
        self.preamble = preamble
        self.force_overwrite = force_overwrite
        self.keep_temp_on_error = keep_temp_on_error
        self.logger = logger

    def gather_yaml(self) -> List[Path]:
        """
        Collect all YAML metadata files for the specified year.

        Returns:
            Sorted list of YAML file paths

        Raises:
            PdfBuildError: If directory not found or no files found
        """
        yaml_year = self.yaml_dir / self.year

        safe_logger(self.logger).log_debug(f"Looking for YAML files in: {yaml_year}")

        if not yaml_year.exists() or not yaml_year.is_dir():
            raise PdfBuildError(f"YAML directory not found: {yaml_year}")

        files = sorted(yaml_year.glob(f"{self.year}-*.yaml"))

        if not files:
            raise PdfBuildError(f"No YAML files found in {yaml_year}")

        safe_logger(self.logger).log_debug(f"Found {len(files)} YAML metadata files")

        return files

    def _track_arc_changes(
        self, current_arcs: List[str], previous_arcs: Set[str]
    ) -> List[str]:
        """
        Detect new arcs that need markers.

        Args:
            current_arcs: Arcs in current entry
            previous_arcs: Set of arcs seen in previous entry

        Returns:
            List of new arc names to mark
        """
        current_set = set(current_arcs)
        new_arcs = current_set - previous_arcs
        return sorted(new_arcs)

    def _write_temp_md(self, files: List[Path], tmp_path: Path) -> None:
        """
        Format and concatenate YAML metadata into temporary Markdown file.

        Processes each YAML file, formats metadata, tracks arc changes,
        and injects arc markers when arcs change.

        Args:
            files: List of YAML metadata files
            tmp_path: Path to temporary output file

        Raises:
            PdfBuildError: If file writing or parsing fails
        """
        safe_logger(self.logger).log_debug(
            f"Creating formatted metadata markdown: {tmp_path.name}"
        )

        # Group files by month
        months: Dict[str, List[Path]] = defaultdict(list)
        for yaml_file in sorted(files):
            parts = yaml_file.stem.split("-")
            if len(parts) < 2:
                safe_logger(self.logger).log_warning(
                    f"Skipping malformed filename: {yaml_file.stem}"
                )
                continue
            _, month_str, *_ = parts
            months[month_str].append(yaml_file)

        safe_logger(self.logger).log_debug(
            f"Grouped into {len(months)} months for year {self.year}"
        )

        try:
            with tmp_path.open("w", encoding="utf-8") as tmp:
                # Process each month
                for month_str in sorted(months.keys(), key=lambda m: int(m)):
                    month_name = calendar.month_name[int(month_str)]

                    # Month subtitle page (centered, on its own page)
                    tmp.write("```{=latex}\n\\newpage\n```\n\n")
                    tmp.write("```{=latex}\n")
                    tmp.write("\\vspace*{\\fill}\n")
                    tmp.write("\\begin{center}\n")
                    tmp.write(f"{{\\fontsize{{36pt}}{{40pt}}\\selectfont\\bfseries {month_name}, {self.year}\\par}}\n")
                    tmp.write("\\end{center}\n")
                    tmp.write("\\vspace*{\\fill}\n")
                    tmp.write("```\n\n")

                    # Process daily entries
                    for yaml_file in months[month_str]:
                        try:
                            entry = MetadataEntry.from_file(yaml_file)

                            # Start each entry on a new page
                            tmp.write("```{=latex}\n\\newpage\n```\n\n")

                            # Write entry metadata
                            tmp.write(format_entry_metadata(entry))
                            tmp.write("\n")

                        except Exception as e:
                            safe_logger(self.logger).log_warning(
                                f"Failed to parse {yaml_file.name}: {e}"
                            )
                            continue

                # Add table of contents at end
                tmp.write("```{=latex}\n\\newpage\n```\n\n")
                tmp.write("```{=latex}\n\\tableofcontents\n```\n")

        except OSError as e:
            raise PdfBuildError(
                f"Failed to write temporary file {tmp_path}: {e}"
            ) from e

    def _run_pandoc(
        self,
        in_md: Path,
        out_pdf: Path,
        preamble: Path,
        metadata: Dict[str, str],
        extra_vars: Dict[str, str],
    ) -> None:
        """
        Convert Markdown to PDF using Pandoc.

        Args:
            in_md: Source Markdown file
            out_pdf: Output PDF file
            preamble: LaTeX preamble file
            metadata: Pandoc metadata key-value pairs
            extra_vars: Additional LaTeX variables

        Raises:
            PdfBuildError: If conversion fails
        """
        if not in_md.is_file():
            raise PdfBuildError(f"Markdown file not found: {in_md}")

        if not preamble.is_file():
            raise PdfBuildError(f"Preamble file not found: {preamble}")

        # Build Pandoc arguments
        args = [
            "--from",
            "markdown",
            "--pdf-engine",
            PANDOC_ENGINE,
            "--include-in-header",
            str(preamble),
            "--variable",
            f"documentclass:{PANDOC_DOCUMENT_CLASS}",
        ]

        # Add metadata
        for key, value in metadata.items():
            args.extend(["--metadata", f"{key}: {value}"])

        # Add extra variables
        for key, value in extra_vars.items():
            args.extend(["--variable", f"{key}:{value}"])

        safe_logger(self.logger).log_debug(
            f"Running Pandoc: {in_md.name} → {out_pdf.name}"
        )
        safe_logger(self.logger).log_debug(f"Temp file location: {in_md}")

        try:
            convert_file(str(in_md), to="pdf", outputfile=str(out_pdf), extra_args=args)
        except (OSError, RuntimeError) as e:
            raise PdfBuildError(
                f"Pandoc conversion failed: {in_md} → {out_pdf}: {e}"
            ) from e

    def build(self) -> BuildStats:
        """
        Execute complete metadata PDF build process.

        Returns:
            BuildStats with build results

        Raises:
            PdfBuildError: If build fails
        """
        stats = BuildStats()

        safe_logger(self.logger).log_operation(
            "metadata_pdf_build_start",
            {
                "year": self.year,
                "yaml_dir": str(self.yaml_dir),
                "pdf_dir": str(self.pdf_dir),
            },
        )

        # Validate preamble
        if not self.preamble.is_file():
            raise PdfBuildError(f"Preamble not found: {self.preamble}")

        # Ensure output directory exists
        try:
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise PdfBuildError(
                f"Cannot create PDF directory {self.pdf_dir}: {e}"
            ) from e

        # Pandoc metadata
        metadata = {
            "title": PDF_TITLE,
            "subtitle": PDF_SUBTITLE,
            "date": self.year,
            "author": PDF_AUTHOR,
        }

        # LaTeX variables
        vars = {"fontsize": "10pt"}  # Smaller font for dense metadata

        # Output path
        pdf_path = self.pdf_dir / f"{self.year}-metadata.pdf"

        # Check if exists
        if pdf_path.exists() and not self.force_overwrite:
            safe_logger(self.logger).log_info(
                f"Metadata PDF exists, skipping: {pdf_path.name}"
            )
            return stats

        if pdf_path.exists():
            safe_logger(self.logger).log_debug(
                f"Metadata PDF exists, overwriting: {pdf_path.name}"
            )
            pdf_path.unlink()

        # Gather files
        files = self.gather_yaml()
        stats.files_processed = len(files)

        # Use TemporalFileManager for proper cleanup
        temp_manager = TemporalFileManager()
        error_occurred = False

        try:
            # Create temporary markdown file
            tmp_file = temp_manager.create_temp_file(
                suffix=".md", prefix=f"palimpsest_metadata_{self.year}_"
            )

            # Format and write
            self._write_temp_md(files, tmp_file)

            # Run Pandoc
            self._run_pandoc(tmp_file, pdf_path, self.preamble, metadata, vars)

            stats.pdfs_created = 1

            safe_logger(self.logger).log_operation(
                "metadata_pdf_created", {"file": str(pdf_path)}
            )

        except PdfBuildError:
            stats.errors += 1
            error_occurred = True
            raise

        finally:
            # Clean up with option to preserve on error
            if error_occurred and self.keep_temp_on_error:
                safe_logger(self.logger).log_warning(
                    f"Error occurred - preserving temp files for debugging: "
                    f"{[str(f) for f in temp_manager.active_files]}"
                )
            else:
                cleanup_stats = temp_manager.cleanup()
                if cleanup_stats["files_removed"] > 0:
                    safe_logger(self.logger).log_debug(
                        f"Cleaned up {cleanup_stats['files_removed']} temporary files"
                    )

        safe_logger(self.logger).log_operation(
            "metadata_pdf_build_complete", {"stats": stats.summary()}
        )

        return stats

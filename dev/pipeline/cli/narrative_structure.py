#!/usr/bin/env python3
"""
Narrative Structure Commands
-----------------------------
Commands for compiling scene/event/arc review documents.

Commands:
    compile-review: Entry→Scene→Event→Arc hierarchy documents
    compile-source: Analysis + journal source text documents
    compile-timeline: Pure analysis compilation PDFs
    extract-unmapped: Generate unmapped scenes checklists
    events-view: Create event-centric validation view

Usage:
    plm narrative compile-review --all --pdf
    plm narrative compile-source --core --pdf
    plm narrative compile-timeline core --pdf
    plm narrative extract-unmapped
    plm narrative events-view
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path

# --- Third party imports ---
import click

# --- Local imports ---
from dev.builders.narrative import (
    compile_events_view,
    compile_review,
    compile_source_review,
    compile_timeline,
    extract_unmapped_scenes,
    REVIEW_DIR,
)
from dev.core.paths import NARRATIVE_ANALYSIS_DIR, TMP_DIR


@click.group("narrative")
def narrative() -> None:
    """Scene/event/arc compilation tools for narrative analysis review."""
    pass


@narrative.command("compile-review")
@click.option("--core", "-c", is_flag=True, help="Compile core story (Nov 2024 - Dec 2025)")
@click.option("--flashback", "-f", is_flag=True, help="Compile flashback material (2015 - Oct 2024)")
@click.option("--all", "-a", "do_all", is_flag=True, help="Compile both core and flashback")
@click.option("--pdf", "-p", is_flag=True, help="Generate PDF (default outputs to _review/)")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output directory (default: _review/ for PDF, narrative_analysis/ for markdown)",
)
def compile_review_cmd(
    core: bool,
    flashback: bool,
    do_all: bool,
    pdf: bool,
    output: str | None,
) -> None:
    """
    Create Entry→Scene→Event→Arc hierarchy documents.

    Generates consolidated review documents showing the full narrative
    structure hierarchy. Each entry displays its summary, scenes with
    event assignments, and thematic arc mappings.

    PDFs are generated directly to _review/ by default (no intermediate markdown).
    """
    output_dir = Path(output) if output else None
    do_core = core or do_all
    do_flashback = flashback or do_all

    if not do_core and not do_flashback:
        raise click.UsageError("Must specify --core, --flashback, or --all")

    if do_core:
        click.echo("Compiling core story review...")
        output_path = compile_review("core", output_dir, pdf=pdf)
        click.echo(f"  Created: {output_path}")

    if do_flashback:
        click.echo("Compiling flashback review...")
        output_path = compile_review("flashback", output_dir, pdf=pdf)
        click.echo(f"  Created: {output_path}")

    click.echo("Done!")


@narrative.command("compile-source")
@click.option("--core", "-c", is_flag=True, help="Compile core story")
@click.option("--flashback", "-f", is_flag=True, help="Compile flashback material")
@click.option("--all", "-a", "do_all", is_flag=True, help="Compile both")
@click.option("--pdf", "-p", is_flag=True, help="Generate PDF with line numbers (default outputs to _review/)")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output directory (default: _review/ for PDF, narrative_analysis/ for markdown)",
)
def compile_source_cmd(
    core: bool,
    flashback: bool,
    do_all: bool,
    pdf: bool,
    output: str | None,
) -> None:
    """
    Create analysis + journal source text documents.

    Generates review documents combining narrative analysis metadata
    with original journal text. Useful for validating scene accuracy
    against source material.

    PDFs are generated directly to _review/ by default (no intermediate markdown).
    """
    output_dir = Path(output) if output else None
    do_core = core or do_all
    do_flashback = flashback or do_all

    if not do_core and not do_flashback:
        raise click.UsageError("Must specify --core, --flashback, or --all")

    if do_core:
        click.echo("Compiling core source review...")
        output_path = compile_source_review("core", output_dir, pdf=pdf)
        click.echo(f"  Created: {output_path}")

    if do_flashback:
        click.echo("Compiling flashback source review...")
        output_path = compile_source_review("flashback", output_dir, pdf=pdf)
        click.echo(f"  Created: {output_path}")

    click.echo("Done!")


@narrative.command("compile-timeline")
@click.argument("period", type=click.Choice(["core", "early_transition", "montreal_life"]))
@click.option("--pdf", "-p", is_flag=True, help="Generate PDF (default outputs to tmp/)")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output directory (default: tmp/)",
)
def compile_timeline_cmd(
    period: str,
    pdf: bool,
    output: str | None,
) -> None:
    """
    Compile pure analysis PDFs by time period.

    Creates chronologically ordered compilations of narrative analyses
    for reading through. These are for reading, not review, so output
    defaults to tmp/ directory.

    \b
    Available periods:
    - core: Nov 2024 - Dec 2025 (main story + coda)
    - early_transition: 2015-2019 (early flashbacks)
    - montreal_life: 2021-2024 (Montreal flashbacks)
    """
    output_dir = Path(output) if output else None

    click.echo(f"Compiling {period} timeline...")
    output_path = compile_timeline(period, output_dir, pdf=pdf)
    click.echo(f"  Created: {output_path}")

    click.echo("Done!")


@narrative.command("extract-unmapped")
@click.option("--pdf", "-p", is_flag=True, help="Generate PDF instead of markdown")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=str(REVIEW_DIR),
    help="Output directory for checklists",
)
def extract_unmapped_cmd(pdf: bool, output: str) -> None:
    """
    Generate unmapped scenes checklists.

    Extracts scenes marked as NOT MAPPED from review documents
    and creates actionable checklists organized by month.
    """
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Core - generate review markdown to temp, then extract
    click.echo("Generating core review for analysis...")
    core_review = compile_review("core", output_dir, pdf=False)
    count, out_path = extract_unmapped_scenes(
        core_review,
        output_dir,
        "Unmapped Scenes: Core Story",
        "unmapped_core",
        pdf=pdf
    )
    click.echo(f"Core: {count} unmapped scenes → {out_path.name}")
    core_review.unlink()  # Clean up temp markdown

    # Flashback
    click.echo("Generating flashback review for analysis...")
    flashback_review = compile_review("flashback", output_dir, pdf=False)
    count, out_path = extract_unmapped_scenes(
        flashback_review,
        output_dir,
        "Unmapped Scenes: Flashback Material",
        "unmapped_flashback",
        pdf=pdf
    )
    click.echo(f"Flashback: {count} unmapped scenes → {out_path.name}")
    flashback_review.unlink()  # Clean up temp markdown

    click.echo("Done!")


@narrative.command("events-view")
@click.option("--pdf", "-p", is_flag=True, help="Generate PDF instead of markdown")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=str(REVIEW_DIR),
    help="Output directory (default: _review/)",
)
def events_view_cmd(pdf: bool, output: str) -> None:
    """
    Create event-centric validation view.

    Generates documents showing each event with all its contributing
    scenes for easy validation of event groupings.
    """
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Core
    core_count, out_path = compile_events_view(
        "core",
        output_dir,
        "Events View: Core Story",
        "events_view_core",
        pdf=pdf
    )
    click.echo(f"Core: {core_count} events → {out_path.name}")

    # Flashback
    flashback_count, out_path = compile_events_view(
        "flashback",
        output_dir,
        "Events View: Flashback Material",
        "events_view_flashback",
        pdf=pdf
    )
    click.echo(f"Flashback: {flashback_count} events → {out_path.name}")

    click.echo("Done!")


__all__ = ["narrative"]

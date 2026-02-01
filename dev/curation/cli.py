#!/usr/bin/env python3
"""
cli.py
------
Click CLI commands for the curation module.

This module provides CLI commands for the entity curation workflow:
- extract: Extract entities from source files
- validate: Validate curation files
- consolidate: Merge per-year curation files
- import: Import curated entities to database
- summary: Generate entity frequency reports

Usage:
    plm curation extract [--dry-run]
    plm curation validate [--year YYYY] [--type people|locations]
    plm curation consolidate --years 2023 2024 2025 [--type people|locations]
    plm curation import [--dry-run] [--failed-only]
    plm curation summary [--type people|locations] [--alphabetical]

All commands follow the pipeline CLI pattern with proper logging
and error handling.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional, Tuple

# --- Third-party imports ---
import click
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Local imports ---
from dev.core.cli import setup_logger
from dev.core.paths import CURATION_DIR, DB_PATH, JOURNAL_YAML_DIR, LOG_DIR


# =============================================================================
# Command Group
# =============================================================================

@click.group("curation")
@click.pass_context
def curation(ctx: click.Context) -> None:
    """Entity curation tools for managing people and locations."""
    ctx.ensure_object(dict)
    if "logger" not in ctx.obj:
        ctx.obj["logger"] = setup_logger(LOG_DIR, "curation")


# =============================================================================
# Extract Command
# =============================================================================

@curation.command("extract")
@click.option("--dry-run", is_flag=True, help="Don't write output files")
@click.pass_context
def extract_cmd(ctx: click.Context, dry_run: bool) -> None:
    """
    Extract entities from source files for curation.

    Scans MD frontmatter and narrative_analysis YAML files to extract
    people and locations, then generates per-year curation files.

    Output:
        data/curation/{YYYY}_people_curation.yaml
        data/curation/{YYYY}_locations_curation.yaml
    """
    from dev.curation.extract import extract_all

    logger = ctx.obj.get("logger")

    click.echo("Extracting entities from source files...")
    if dry_run:
        click.echo("[DRY RUN] No files will be written.")

    stats = extract_all(dry_run=dry_run, logger=logger)

    click.echo("")
    click.echo(stats.summary())
    click.echo(f"\nPeople by year:")
    for year, count in sorted(stats.people_by_year.items()):
        click.echo(f"  {year}: {count} names")
    click.echo(f"\nLocations by year:")
    for year, count in sorted(stats.locations_by_year.items()):
        click.echo(f"  {year}: {count} locations")

    if not dry_run:
        click.echo(f"\nFiles saved to: {CURATION_DIR}")


# =============================================================================
# Validate Command
# =============================================================================

@curation.command("validate")
@click.option("--year", "-y", type=str, help="Specific year to validate")
@click.option(
    "--type", "-t",
    "entity_type",
    type=click.Choice(["people", "locations"]),
    help="Entity type to validate",
)
@click.option(
    "--check-consistency", "-c",
    is_flag=True,
    help="Run cross-year consistency checks",
)
@click.pass_context
def validate_cmd(
    ctx: click.Context,
    year: Optional[str],
    entity_type: Optional[str],
    check_consistency: bool,
) -> None:
    """
    Validate curation files.

    By default, validates all curation files for format and required fields.
    Use --check-consistency to also check for cross-year conflicts.
    """
    from dev.curation.validate import check_consistency as check_consistency_fn
    from dev.curation.validate import validate_all

    logger = ctx.obj.get("logger")

    if check_consistency:
        click.echo("Running cross-year consistency checks...")
        results = check_consistency_fn(entity_type=entity_type, logger=logger)

        has_conflicts = False
        for result in results:
            click.echo(f"\n{result.entity_type.upper()}")
            click.echo("=" * 40)

            if result.conflicts:
                has_conflicts = True
                click.echo(f"\nCONFLICTS ({len(result.conflicts)}):")
                for conflict in result.conflicts:
                    click.echo(f"  ✗ {conflict}")

            if result.suggestions:
                click.echo(f"\nSUGGESTIONS ({len(result.suggestions)}):")
                for suggestion in result.suggestions[:10]:
                    click.echo(f"  ? {suggestion}")
                if len(result.suggestions) > 10:
                    click.echo(f"  ... and {len(result.suggestions) - 10} more")

            if not result.conflicts and not result.suggestions:
                click.echo("  ✓ No conflicts or suggestions")

        if has_conflicts:
            raise SystemExit(1)
    else:
        click.echo("Validating curation files...")
        results = validate_all(year=year, entity_type=entity_type, logger=logger)

        all_valid = True
        for result in results:
            click.echo(f"\n{Path(result.file_path).name}")
            click.echo("-" * 40)

            if result.errors:
                all_valid = False
                click.echo(f"ERRORS ({len(result.errors)}):")
                for err in result.errors[:10]:
                    click.echo(f"  ✗ {err}")
                if len(result.errors) > 10:
                    click.echo(f"  ... and {len(result.errors) - 10} more")

            if result.warnings:
                click.echo(f"WARNINGS ({len(result.warnings)}):")
                for warn in result.warnings[:5]:
                    click.echo(f"  ⚠ {warn}")
                if len(result.warnings) > 5:
                    click.echo(f"  ... and {len(result.warnings) - 5} more")

            if result.is_valid:
                click.echo(f"  ✓ {result.summary()}")

        click.echo("")
        if all_valid:
            click.echo("✓ All files valid")
        else:
            click.echo("✗ Validation failed")
            raise SystemExit(1)


# =============================================================================
# Consolidate Command
# =============================================================================

@curation.command("consolidate")
@click.option(
    "--years", "-y",
    multiple=True,
    required=True,
    help="Years to consolidate (can specify multiple)",
)
@click.option(
    "--type", "-t",
    "entity_type",
    type=click.Choice(["people", "locations"]),
    default="people",
    help="Entity type to consolidate (default: people)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file path (default: auto-generated)",
)
@click.pass_context
def consolidate_cmd(
    ctx: click.Context,
    years: Tuple[str, ...],
    entity_type: str,
    output: Optional[str],
) -> None:
    """
    Consolidate per-year curation files into a merged file.

    Merges multiple years of curation data, resolving same_as chains
    and combining canonical information.

    Example:
        plm curation consolidate --years 2023 --years 2024 --years 2025
    """
    from dev.curation.consolidate import consolidate_and_write

    logger = ctx.obj.get("logger")
    years_list = list(years)
    output_path = Path(output) if output else None

    click.echo(f"Consolidating {entity_type} for years: {', '.join(years_list)}")

    result = consolidate_and_write(
        years=years_list,
        entity_type=entity_type,
        output_path=output_path,
        logger=logger,
    )

    click.echo("")
    click.echo(result.summary())

    if result.conflicts:
        click.echo(f"\nCONFLICTS ({len(result.conflicts)}):")
        for conflict in result.conflicts:
            click.echo(f"  ✗ {conflict}")

    click.echo(f"\nOutput: {result.output_path}")


# =============================================================================
# Import Command
# =============================================================================

@curation.command("import")
@click.option("--dry-run", is_flag=True, help="Don't commit changes")
@click.option("--failed-only", is_flag=True, help="Only retry failed imports")
@click.option("--skip-validation", is_flag=True, help="Skip pre-import validation")
@click.option("--year", "-y", type=str, help="Import only specific year (e.g., 2024)")
@click.option(
    "--years",
    type=str,
    help="Import year range (e.g., 2021-2025)",
)
@click.pass_context
def import_cmd(
    ctx: click.Context,
    dry_run: bool,
    failed_only: bool,
    skip_validation: bool,
    year: Optional[str],
    years: Optional[str],
) -> None:
    """
    Import metadata YAMLs to database.

    Uses curated entity files for consistent person/location resolution.
    Each YAML file is imported in a single transaction.

    Data sources:
    - MD Frontmatter: entry-level people, locations, narrated_dates
    - Metadata YAML: summary, rating, scenes, events, threads, etc.

    The import will stop if:
    - 5 consecutive failures occur
    - Failure rate exceeds 5%
    """
    from dev.curation.importer import CurationImporter
    from dev.curation.resolve import EntityResolver
    from dev.curation.validate import validate_all as validate_curation
    from dev.validators.metadata_yaml import validate_for_import

    logger = ctx.obj.get("logger")

    # Pre-validation: curation files
    if not skip_validation:
        click.echo("Running pre-import validation...")

        # 1. Validate curation files
        click.echo("  Checking curation files...")
        curation_results = validate_curation(logger=logger)
        if any(not r.is_valid for r in curation_results):
            click.echo("  ✗ Curation validation failed. Fix errors first.")
            raise SystemExit(1)
        click.echo("  ✓ Curation files OK")

        # 2. Validate metadata YAML files
        click.echo("  Checking metadata YAML files...")
        # Determine year filter
        year_filter = year if year else None
        if years and "-" in years:
            # For ranges, validate all (we'll filter later)
            year_filter = None

        passed, summary = validate_for_import(year=year_filter)
        if not passed:
            click.echo("  ✗ Metadata validation failed:")
            for line in summary.split("\n"):
                click.echo(f"    {line}")
            click.echo("\n  Run: python -c \"from dev.validators.metadata_yaml import print_validation_report; print_validation_report()\"")
            click.echo("  Or check: validation_errors.txt")
            raise SystemExit(1)
        click.echo("  ✓ Metadata YAML files OK")
        click.echo("✓ All validations passed\n")

    # Determine which years to import
    years_to_import: Optional[set] = None
    if year:
        years_to_import = {year}
    elif years:
        # Parse year range like "2021-2025"
        if "-" in years:
            start_year, end_year = years.split("-")
            years_to_import = {
                str(y) for y in range(int(start_year), int(end_year) + 1)
            }
        else:
            years_to_import = {years}

    # Get YAML files from metadata/journal
    yaml_files = sorted(JOURNAL_YAML_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    # Filter by year if specified
    if years_to_import:
        yaml_files = [
            f for f in yaml_files if f.parent.name in years_to_import
        ]

    click.echo(f"Found {len(yaml_files)} YAML files to import")

    # Load entity resolver
    try:
        resolver = EntityResolver.load()
        click.echo(
            f"Loaded entity resolver: "
            f"{len(resolver.people_map)} people, "
            f"{len(resolver.locations_map)} locations"
        )
    except FileNotFoundError as e:
        click.echo(f"Error: {e}")
        raise SystemExit(1)

    # Create database session
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Run import
        importer = CurationImporter(
            session=session,
            resolver=resolver,
            dry_run=dry_run,
            logger=logger,
        )
        stats = importer.import_all(yaml_files, failed_only=failed_only)

        # Print results
        click.echo("")
        click.echo("=" * 60)
        click.echo("IMPORT RESULTS")
        click.echo("=" * 60)
        click.echo(stats.summary())
        click.echo("")
        click.echo(stats.entity_summary())
        click.echo("=" * 60)

        if stats.failed > 0:
            raise SystemExit(1)

    finally:
        session.close()


# =============================================================================
# Summary Command
# =============================================================================

@curation.command("summary")
@click.option(
    "--type", "-t",
    "entity_type",
    type=click.Choice(["people", "locations"]),
    help="Entity type to summarize (default: both)",
)
@click.option(
    "--alphabetical", "-a",
    is_flag=True,
    help="Sort alphabetically instead of by frequency",
)
@click.pass_context
def summary_cmd(
    ctx: click.Context,
    entity_type: Optional[str],
    alphabetical: bool,
) -> None:
    """
    Generate entity frequency summary report.

    Shows entity counts across all years with per-year breakdowns.
    """
    from dev.curation.summary import generate_summary

    logger = ctx.obj.get("logger")

    _, _, report_lines = generate_summary(
        entity_type=entity_type,
        alphabetical=alphabetical,
        logger=logger,
    )

    for line in report_lines:
        click.echo(line)


# =============================================================================
# Module Export
# =============================================================================

__all__ = ["curation"]

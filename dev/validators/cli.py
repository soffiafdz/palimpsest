#!/usr/bin/env python3
"""
cli.py
------
Unified CLI for Palimpsest validators.

Provides a single entry point for running various validation checks across
the Palimpsest system. Each validator checks a specific aspect of data
integrity or quality.

Available validators:
    - wiki: Wiki link integrity, orphan detection, broken links

Planned validators:
    - db: Database referential integrity, constraint violations
    - md: Markdown file validation, broken links, malformed frontmatter
    - consistency: Cross-system consistency (wiki ↔ db, md ↔ db)

Architecture:
    This CLI aggregates validators from individual modules (wiki.py, db.py, etc.)
    Each validator module has its own command group and subcommands.

Usage:
    validate wiki check         # Check all wiki links
    validate wiki orphans       # Find orphaned wiki pages
    validate wiki stats         # Show wiki statistics

    # Future validators:
    validate db integrity       # Check database integrity
    validate md links           # Check markdown links
    validate consistency wiki-db # Check wiki ↔ database consistency

Note: Simple validators remain in their respective CLIs:
    - `plm validate` - Pipeline structure validation
    - `metadb health` - Database health check
"""
import click
from typing import Optional

from dev.core.paths import WIKI_DIR, LOG_DIR, DB_PATH, ALEMBIC_DIR, BACKUP_DIR, MD_DIR


@click.group()
def cli():
    """
    Palimpsest Validation Suite.

    Run comprehensive validation checks on wiki links, database integrity,
    markdown files, and cross-system consistency.
    """
    pass


# ═══════════════════════════════════════════════════════════════════════════
# WIKI VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
@click.option(
    "--wiki-dir",
    type=click.Path(exists=True),
    default=str(WIKI_DIR),
    help="Wiki directory to validate"
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files"
)
@click.pass_context
def wiki(ctx: click.Context, wiki_dir: str, log_dir: str) -> None:
    """
    Validate wiki link integrity.

    Check for broken links, orphaned pages, and generate statistics
    about wiki link structure.
    """
    # Import here to avoid circular dependencies and load only when needed
    from pathlib import Path
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")


@wiki.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """
    Check all wiki links for broken references.

    Parses all wiki files, extracts [[link]] references, and validates
    that target files exist. Reports broken links with file locations.
    """
    from pathlib import Path
    from dev.validators.wiki import validate_wiki, print_validation_report

    wiki_dir = ctx.obj["wiki_dir"]

    click.echo(f"🔍 Validating wiki links in {wiki_dir}\n")

    result = validate_wiki(wiki_dir)
    print_validation_report(result, wiki_dir)

    if result.broken_links:
        raise click.ClickException(f"Found {len(result.broken_links)} broken links")


@wiki.command()
@click.pass_context
def orphans(ctx: click.Context) -> None:
    """
    Find orphaned wiki pages with no incoming links.

    Analyzes the wiki link graph to find pages that have no other pages
    linking to them. These may be dead content that should be removed
    or linked from somewhere.
    """
    from pathlib import Path
    from dev.validators.wiki import validate_wiki, print_orphans_report

    wiki_dir = ctx.obj["wiki_dir"]

    click.echo(f"🔍 Finding orphaned pages in {wiki_dir}\n")

    result = validate_wiki(wiki_dir)
    print_orphans_report(result, wiki_dir)


@wiki.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """
    Show wiki link statistics.

    Display summary statistics about wiki structure: total files,
    total links, broken links, orphans, and link density.
    """
    from pathlib import Path
    from dev.validators.wiki import validate_wiki, print_stats_report

    wiki_dir = ctx.obj["wiki_dir"]

    click.echo(f"📊 Wiki statistics for {wiki_dir}\n")

    result = validate_wiki(wiki_dir)
    print_stats_report(result, wiki_dir)


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file"
)
@click.option(
    "--alembic-dir",
    type=click.Path(),
    default=str(ALEMBIC_DIR),
    help="Path to Alembic migrations directory"
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files"
)
@click.pass_context
def db(ctx: click.Context, db_path: str, alembic_dir: str, log_dir: str) -> None:
    """
    Validate database integrity and constraints.

    Check for schema drift, pending migrations, foreign key violations,
    and unique constraint violations.
    """
    from pathlib import Path
    from dev.core.cli import setup_logger
    from dev.database.manager import PalimpsestDB

    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["alembic_dir"] = Path(alembic_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=Path(alembic_dir),
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@db.command()
@click.pass_context
def schema(ctx: click.Context) -> None:
    """
    Check for schema drift between models and database.

    Validates that all model tables and columns exist in the database
    and reports any mismatches. This helps catch cases where model
    changes haven't been migrated.
    """
    from dev.validators.db import DatabaseValidator

    db = ctx.obj["db"]
    alembic_dir = ctx.obj["alembic_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking database schema...\n")

    validator = DatabaseValidator(db, alembic_dir, logger)
    result = validator.validate_schema()

    icon = "✅" if result.passed else "❌"
    click.echo(f"{icon} {result.check_name}")
    click.echo(f"   {result.message}\n")

    if result.details:
        for detail in result.details:
            click.echo(f"   {detail}")
        click.echo()

    if not result.passed:
        raise click.ClickException("Schema validation failed")


@db.command()
@click.pass_context
def migrations(ctx: click.Context) -> None:
    """
    Check if all migrations have been applied.

    Compares the current database revision with the latest migration
    script to ensure the database is up to date.
    """
    from dev.validators.db import DatabaseValidator

    db = ctx.obj["db"]
    alembic_dir = ctx.obj["alembic_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking migration status...\n")

    validator = DatabaseValidator(db, alembic_dir, logger)
    result = validator.validate_migrations()

    icon = "✅" if result.passed else "❌"
    click.echo(f"{icon} {result.check_name}")
    click.echo(f"   {result.message}\n")

    if result.details:
        for detail in result.details:
            click.echo(f"   {detail}")
        click.echo()

    if not result.passed:
        raise click.ClickException("Migration check failed")


@db.command()
@click.pass_context
def integrity(ctx: click.Context) -> None:
    """
    Check for orphaned records and foreign key violations.

    Scans all tables for records that reference non-existent parent
    records, which indicates data integrity issues.
    """
    from dev.validators.db import DatabaseValidator

    db = ctx.obj["db"]
    alembic_dir = ctx.obj["alembic_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking foreign key integrity...\n")

    validator = DatabaseValidator(db, alembic_dir, logger)
    result = validator.validate_foreign_keys()

    icon = "✅" if result.passed else "❌"
    click.echo(f"{icon} {result.check_name}")
    click.echo(f"   {result.message}\n")

    if result.details:
        for detail in result.details:
            click.echo(f"   {detail}")
        click.echo()

    if not result.passed:
        raise click.ClickException("Foreign key validation failed")


@db.command()
@click.pass_context
def constraints(ctx: click.Context) -> None:
    """
    Check for unique constraint violations.

    Finds duplicate records that violate unique constraints or indexes.
    """
    from dev.validators.db import DatabaseValidator

    db = ctx.obj["db"]
    alembic_dir = ctx.obj["alembic_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking unique constraints...\n")

    validator = DatabaseValidator(db, alembic_dir, logger)
    result = validator.validate_unique_constraints()

    icon = "✅" if result.passed else "❌"
    click.echo(f"{icon} {result.check_name}")
    click.echo(f"   {result.message}\n")

    if result.details:
        for detail in result.details:
            click.echo(f"   {detail}")
        click.echo()

    if not result.passed:
        raise click.ClickException("Constraint validation failed")


@db.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all database validation checks.

    Comprehensive validation including schema, migrations, foreign keys,
    and constraints. Provides a complete health report.
    """
    from dev.validators.db import DatabaseValidator, format_validation_report

    db = ctx.obj["db"]
    alembic_dir = ctx.obj["alembic_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Running comprehensive database validation...\n")

    validator = DatabaseValidator(db, alembic_dir, logger)
    report = validator.validate_all()

    # Print formatted report
    click.echo(format_validation_report(report))

    if not report.is_healthy:
        raise click.ClickException(f"Database validation failed with {report.errors} error(s)")


# ═══════════════════════════════════════════════════════════════════════════
# MARKDOWN VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
@click.option(
    "--md-dir",
    type=click.Path(exists=True),
    default=str(MD_DIR),
    help="Markdown directory to validate"
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files"
)
@click.pass_context
def md(ctx: click.Context, md_dir: str, log_dir: str) -> None:
    """
    Validate markdown journal entry files.

    Check for YAML frontmatter issues, broken links, malformed structure,
    and content problems.
    """
    from pathlib import Path
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")


@md.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def frontmatter(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate YAML frontmatter in markdown files.

    Checks for:
    - Valid YAML syntax
    - Required fields (date)
    - Field types and formats
    - Valid enum values (manuscript status, reference modes/types)
    - Unknown fields
    """
    from pathlib import Path
    from dev.validators.md import MarkdownValidator, format_markdown_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating markdown frontmatter in {md_dir}\n")

    validator = MarkdownValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        if issues:
            for issue in issues:
                if issue.category == "frontmatter":
                    icon = "❌" if issue.severity == "error" else "⚠️"
                    click.echo(f"{icon} {issue.message}")
                    if issue.suggestion:
                        click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No frontmatter issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only frontmatter issues
        frontmatter_issues = [i for i in report.issues if i.category == "frontmatter"]
        report.issues = frontmatter_issues
        report.total_errors = sum(1 for i in frontmatter_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in frontmatter_issues if i.severity == "warning")

        click.echo(format_markdown_report(report))

        if report.has_errors:
            raise click.ClickException(f"Found {report.total_errors} frontmatter error(s)")


@md.command()
@click.pass_context
def links(ctx: click.Context) -> None:
    """
    Check for broken internal markdown links.

    Validates that all relative markdown links point to existing files.
    External links (http://, https://) are skipped.
    """
    from dev.validators.md import MarkdownValidator

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Checking markdown links in {md_dir}\n")

    validator = MarkdownValidator(md_dir, logger)
    issues = validator.validate_links()

    if issues:
        for issue in issues:
            click.echo(f"❌ {issue.file_path.name}:{issue.line_number}")
            click.echo(f"   {issue.message}")
            if issue.suggestion:
                click.echo(f"   💡 {issue.suggestion}")
            click.echo()

        raise click.ClickException(f"Found {len(issues)} broken link(s)")
    else:
        click.echo("✅ All markdown links are valid")


@md.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all markdown validation checks.

    Comprehensive validation including frontmatter, links, structure,
    and content. Provides a complete health report.
    """
    from dev.validators.md import MarkdownValidator, format_markdown_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Running comprehensive markdown validation on {md_dir}\n")

    validator = MarkdownValidator(md_dir, logger)
    report = validator.validate_all()

    # Also check links
    link_issues = validator.validate_links()
    for issue in link_issues:
        report.add_issue(issue)

    # Print formatted report
    click.echo(format_markdown_report(report))

    if not report.is_healthy:
        raise click.ClickException(f"Markdown validation failed with {report.total_errors} error(s)")


# ═══════════════════════════════════════════════════════════════════════════
# METADATA VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
@click.option(
    "--md-dir",
    type=click.Path(exists=True),
    default=str(MD_DIR),
    help="Markdown directory to validate"
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files"
)
@click.pass_context
def metadata(ctx: click.Context, md_dir: str, log_dir: str) -> None:
    """
    Validate metadata parser compatibility.

    Check that frontmatter structures match parser expectations, including
    special character usage, cross-field dependencies, and structural rules.
    """
    from pathlib import Path
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")


@metadata.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def people(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate people field structures.

    Checks for:
    - Proper alias format (@prefix)
    - Parentheses spacing and format
    - Hyphenated name handling
    - Dict structure (name/full_name/alias fields)
    """
    from pathlib import Path
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating people metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        people_issues = [i for i in issues if i.field_name.startswith("people")]
        if people_issues:
            for issue in people_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No people metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only people issues
        people_issues = [i for i in report.issues if i.field_name.startswith("people")]
        report.issues = people_issues
        report.total_errors = sum(1 for i in people_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in people_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(f"Found {report.total_errors} people metadata error(s)")


@metadata.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def locations(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate locations-city dependency.

    Checks for:
    - Flat list requires exactly 1 city
    - Nested dict allows multiple cities
    - Dict keys match city list
    - Location name references (#prefix in context)
    """
    from pathlib import Path
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating locations metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        location_issues = [i for i in issues if i.field_name.startswith("locations") or i.field_name.startswith("city")]
        if location_issues:
            for issue in location_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No locations metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only locations issues
        location_issues = [i for i in report.issues if i.field_name.startswith("locations") or i.field_name.startswith("city")]
        report.issues = location_issues
        report.total_errors = sum(1 for i in location_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in location_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(f"Found {report.total_errors} locations metadata error(s)")


@metadata.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def dates(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate dates field structures.

    Checks for:
    - ISO date format (YYYY-MM-DD)
    - Inline context with @people and #locations refs
    - Dict structure (date, context, people, locations)
    - Opt-out marker (~)
    - Parentheses balance in context
    """
    from pathlib import Path
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating dates metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        date_issues = [i for i in issues if i.field_name.startswith("dates")]
        if date_issues:
            for issue in date_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No dates metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only dates issues
        date_issues = [i for i in report.issues if i.field_name.startswith("dates")]
        report.issues = date_issues
        report.total_errors = sum(1 for i in date_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in date_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(f"Found {report.total_errors} dates metadata error(s)")


@metadata.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def references(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate references field structures.

    Checks for:
    - Required content or description field
    - Valid mode enum (direct, indirect, paraphrase, visual)
    - Valid source type enum (book, article, film, etc.)
    - Source structure
    """
    from pathlib import Path
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating references metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        ref_issues = [i for i in issues if i.field_name.startswith("references")]
        if ref_issues:
            for issue in ref_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No references metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only references issues
        ref_issues = [i for i in report.issues if i.field_name.startswith("references")]
        report.issues = ref_issues
        report.total_errors = sum(1 for i in ref_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in ref_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(f"Found {report.total_errors} references metadata error(s)")


@metadata.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def poems(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate poems field structures.

    Checks for:
    - Required title field
    - Required content field
    - Optional revision_date in ISO format
    """
    from pathlib import Path
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating poems metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        poem_issues = [i for i in issues if i.field_name.startswith("poems")]
        if poem_issues:
            for issue in poem_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No poems metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only poems issues
        poem_issues = [i for i in report.issues if i.field_name.startswith("poems")]
        report.issues = poem_issues
        report.total_errors = sum(1 for i in poem_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in poem_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(f"Found {report.total_errors} poems metadata error(s)")


@metadata.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all metadata validation checks.

    Comprehensive validation of all metadata fields for parser compatibility.
    Checks people, locations, dates, references, poems, and manuscript structures.
    """
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Running comprehensive metadata validation on {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)
    report = validator.validate_all()

    # Print formatted report
    click.echo(format_metadata_report(report))

    if not report.is_healthy:
        raise click.ClickException(f"Metadata validation failed with {report.total_errors} error(s)")


# ═══════════════════════════════════════════════════════════════════════════
# CONSISTENCY VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
@click.option(
    "--md-dir",
    type=click.Path(exists=True),
    default=str(MD_DIR),
    help="Markdown directory"
)
@click.option(
    "--wiki-dir",
    type=click.Path(exists=True),
    default=str(WIKI_DIR),
    help="Wiki directory"
)
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file"
)
@click.option(
    "--alembic-dir",
    type=click.Path(),
    default=str(ALEMBIC_DIR),
    help="Path to Alembic migrations directory"
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files"
)
@click.pass_context
def consistency(
    ctx: click.Context,
    md_dir: str,
    wiki_dir: str,
    db_path: str,
    alembic_dir: str,
    log_dir: str,
) -> None:
    """
    Validate cross-system consistency.

    Check consistency between markdown files, database, and wiki pages.
    Detects orphaned entries, metadata mismatches, and referential integrity issues.
    """
    from pathlib import Path
    from dev.core.cli import setup_logger
    from dev.database.manager import PalimpsestDB

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["alembic_dir"] = Path(alembic_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=Path(alembic_dir),
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@consistency.command()
@click.pass_context
def existence(ctx: click.Context) -> None:
    """
    Check entry existence across MD ↔ DB ↔ Wiki.

    Validates that entries exist consistently across all three systems.
    Detects orphaned entries and missing files.
    """
    from dev.validators.consistency import ConsistencyValidator

    db = ctx.obj["db"]
    md_dir = ctx.obj["md_dir"]
    wiki_dir = ctx.obj["wiki_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking entry existence across systems...\n")

    validator = ConsistencyValidator(db, md_dir, wiki_dir, logger)
    issues = validator.check_entry_existence()

    if issues:
        for issue in issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            click.echo(f"{icon} [{issue.system}] {issue.entity_id}: {issue.message}")
            if issue.suggestion:
                click.echo(f"   💡 {issue.suggestion}")
        click.echo()

        error_count = sum(1 for i in issues if i.severity == "error")
        if error_count > 0:
            raise click.ClickException(f"Found {error_count} existence error(s)")
    else:
        click.echo("✅ All entries exist consistently across systems")


@consistency.command()
@click.pass_context
def metadata(ctx: click.Context) -> None:
    """
    Check metadata synchronization between MD and DB.

    Validates that metadata fields match between markdown files and database.
    Detects word count mismatches, missing relationships, and field inconsistencies.
    """
    from dev.validators.consistency import ConsistencyValidator

    db = ctx.obj["db"]
    md_dir = ctx.obj["md_dir"]
    wiki_dir = ctx.obj["wiki_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking metadata consistency...\n")

    validator = ConsistencyValidator(db, md_dir, wiki_dir, logger)
    issues = validator.check_entry_metadata()

    if issues:
        for issue in issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            click.echo(f"{icon} [{issue.system}] {issue.entity_id}: {issue.message}")
            if issue.suggestion:
                click.echo(f"   💡 {issue.suggestion}")
        click.echo()

        error_count = sum(1 for i in issues if i.severity == "error")
        if error_count > 0:
            raise click.ClickException(f"Found {error_count} metadata error(s)")
    else:
        click.echo("✅ All metadata is synchronized")


@consistency.command()
@click.pass_context
def references(ctx: click.Context) -> None:
    """
    Check referential integrity constraints.

    Validates that all foreign key references are valid and entities exist.
    Detects orphaned records and broken relationships.
    """
    from dev.validators.consistency import ConsistencyValidator

    db = ctx.obj["db"]
    md_dir = ctx.obj["md_dir"]
    wiki_dir = ctx.obj["wiki_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking referential integrity...\n")

    validator = ConsistencyValidator(db, md_dir, wiki_dir, logger)
    issues = validator.check_referential_integrity()

    if issues:
        for issue in issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            click.echo(f"{icon} [{issue.system}] {issue.entity_id}: {issue.message}")
            if issue.suggestion:
                click.echo(f"   💡 {issue.suggestion}")
        click.echo()

        error_count = sum(1 for i in issues if i.severity == "error")
        if error_count > 0:
            raise click.ClickException(f"Found {error_count} referential integrity error(s)")
    else:
        click.echo("✅ All references are valid")


@consistency.command()
@click.pass_context
def integrity(ctx: click.Context) -> None:
    """
    Check file hash integrity.

    Validates that markdown files haven't been modified since last sync.
    Detects out-of-sync files that need re-import.
    """
    from dev.validators.consistency import ConsistencyValidator

    db = ctx.obj["db"]
    md_dir = ctx.obj["md_dir"]
    wiki_dir = ctx.obj["wiki_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking file integrity...\n")

    validator = ConsistencyValidator(db, md_dir, wiki_dir, logger)
    issues = validator.check_file_integrity()

    if issues:
        for issue in issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            click.echo(f"{icon} [{issue.system}] {issue.entity_id}: {issue.message}")
            if issue.suggestion:
                click.echo(f"   💡 {issue.suggestion}")
        click.echo()

        error_count = sum(1 for i in issues if i.severity == "error")
        if error_count > 0:
            raise click.ClickException(f"Found {error_count} file integrity error(s)")
    else:
        click.echo("✅ All files are synchronized")


@consistency.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all consistency validation checks.

    Comprehensive validation including existence, metadata, references,
    and file integrity. Provides a complete health report across all systems.
    """
    from dev.validators.consistency import ConsistencyValidator, format_consistency_report

    db = ctx.obj["db"]
    md_dir = ctx.obj["md_dir"]
    wiki_dir = ctx.obj["wiki_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Running comprehensive consistency validation...\n")

    validator = ConsistencyValidator(db, md_dir, wiki_dir, logger)
    report = validator.validate_all()

    # Print formatted report
    click.echo(format_consistency_report(report))

    if not report.is_healthy:
        raise click.ClickException(f"Consistency validation failed with {report.total_errors} error(s)")


# ═══════════════════════════════════════════════════════════════════════════
# FUTURE VALIDATORS (Placeholder groups)
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    cli()

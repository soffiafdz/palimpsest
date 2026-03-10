"""
Maintenance & Utility Commands
--------------------------------

Commands for pipeline maintenance and status.

Commands:
    - run: Run complete pipeline (under pipeline group)
    - status: Show pipeline status
    - validate: Validate pipeline integrity

This handles operational and maintenance tasks.
"""
from __future__ import annotations

import sys
import click
from datetime import datetime
from typing import Optional

from dev.core.paths import (
    INBOX_DIR,
    TXT_DIR,
    MD_DIR,
    PDF_DIR,
    TEX_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB
from dev.database.query_analytics import QueryAnalytics
from dev.validators.cli.database import db as validate_db
from dev.validators.cli.markdown import md as validate_md
from dev.validators.cli.frontmatter import frontmatter as validate_frontmatter
from dev.validators.cli.consistency import consistency as validate_consistency


@click.command("run")
@click.option("--year", help="Specific year to process (optional)")
@click.option("--skip-inbox", is_flag=True, help="Skip inbox processing")
@click.option("--skip-import", is_flag=True, help="Skip entry import")
@click.option("--skip-pdf", is_flag=True, help="Skip PDF generation")
@click.option("--skip-export", is_flag=True, help="Skip JSON export")
@click.option("--skip-wiki", is_flag=True, help="Skip wiki generation")
@click.option("--backup", is_flag=True, help="Create DB backup after completion")
@click.confirmation_option(prompt="Run complete pipeline?")
@click.pass_context
def run_pipeline(
    ctx: click.Context,
    year: Optional[str],
    skip_inbox: bool,
    skip_import: bool,
    skip_pdf: bool,
    skip_export: bool,
    skip_wiki: bool,
    backup: bool,
) -> None:
    """
    Run the complete processing pipeline end-to-end.

    Orchestrates the entire journal processing pipeline in the correct order:
    inbox → convert → entries import → build pdf → json export → wiki generate → backup
    """
    from .sources import inbox
    from .text import convert
    from .database import import_entries
    from .pdf import build_pdf
    from .export import export_json
    from .wiki import wiki

    click.echo("🚀 Starting complete pipeline...\n")

    start_time = datetime.now()

    try:
        # Step 1: Process inbox
        if not skip_inbox:
            click.echo("=" * 60)
            ctx.invoke(inbox)
            click.echo()

        # Step 2: Convert to Markdown
        click.echo("=" * 60)
        ctx.invoke(convert, force=False)
        click.echo()

        # Step 3: Import entry metadata
        if not skip_import:
            click.echo("=" * 60)
            years_arg = f"{year}-{year}" if year else "2021-2025"
            ctx.invoke(import_entries, dry_run=False, year=None, years=years_arg)
            click.echo()

        # Step 4: Build PDFs (if year specified)
        if not skip_pdf and year:
            click.echo("=" * 60)
            ctx.invoke(build_pdf, year=year, input=str(MD_DIR), output=str(PDF_DIR), force=False, debug=False)
            click.echo()

        # Step 5: Export JSON
        if not skip_export:
            click.echo("=" * 60)
            ctx.invoke(export_json, no_commit=True)
            click.echo()

        # Step 6: Generate wiki
        if not skip_wiki:
            click.echo("=" * 60)
            from dev.wiki.exporter import WikiExporter
            from dev.core.paths import DB_PATH as _DB_PATH
            from dev.database.manager import PalimpsestDB as _PalimpsestDB
            _db = _PalimpsestDB(_DB_PATH)
            wiki_exporter = WikiExporter(_db, logger=ctx.obj.get("logger"))
            wiki_exporter.generate_all()
            click.echo("Wiki pages generated.")
            click.echo()

        # Step 7: DB backup (if requested)
        if backup:
            click.echo("=" * 60)
            db = PalimpsestDB(
                db_path=DB_PATH,
                alembic_dir=ALEMBIC_DIR,
                log_dir=LOG_DIR,
                backup_dir=BACKUP_DIR,
                enable_auto_backup=False,
            )
            backup_path = db.create_backup(backup_type="manual", suffix="pipeline")
            click.echo(f"Backup created: {backup_path}")
            click.echo()

        duration = (datetime.now() - start_time).total_seconds()

        click.echo("=" * 60)
        click.echo(f"\n✅ Pipeline complete! ({duration:.2f}s)")

    except Exception as e:
        handle_cli_error(ctx, e, "run_pipeline")


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show pipeline and wiki status."""
    from dev.core.paths import DATA_DIR

    logger: PalimpsestLogger = ctx.obj["logger"]
    click.echo("📊 Pipeline Status\n")

    # Check directories
    click.echo("Directories:")
    for name, path in [
        ("Inbox", INBOX_DIR),
        ("Text", TXT_DIR),
        ("Markdown", MD_DIR),
        ("PDF", PDF_DIR),
    ]:
        exists = "✓" if path.exists() else "✗"
        click.echo(f"  {exists} {name}: {path}")

    click.echo()

    # Database stats
    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )

        with db.session_scope() as session:
            analytics = QueryAnalytics(logger)
            stats = analytics.get_database_stats(session)

        click.echo("Database:")
        click.echo(f"  Entries: {stats.get('entries', 0)}")
        click.echo(f"  People: {stats.get('people', 0)}")
        click.echo(f"  Locations: {stats.get('locations', 0)}")
        click.echo(f"  Total words: {stats.get('total_words', 0):,}")

    except Exception as e:
        handle_cli_error(ctx, e, "status")
        return

    click.echo()

    # Wiki status
    wiki_dir = DATA_DIR / "wiki"
    click.echo("Wiki:")
    if wiki_dir.exists():
        wiki_pages = list(wiki_dir.rglob("*.md"))
        click.echo(f"  Pages: {len(wiki_pages)}")
        if wiki_pages:
            latest = max(p.stat().st_mtime for p in wiki_pages)
            latest_dt = datetime.fromtimestamp(latest)
            click.echo(f"  Last generated: {latest_dt.strftime('%Y-%m-%d %H:%M:%S')}")

        sync_pending = wiki_dir / ".sync-pending"
        if sync_pending.exists():
            click.echo(f"  Sync pending: {sync_pending.read_text().strip() or 'yes'}")
        else:
            click.echo("  Sync pending: no")
    else:
        click.echo("  Not generated yet")


@click.group()
def validate() -> None:
    """Validate pipeline, entries, database, markdown, frontmatter, and consistency."""
    pass


@validate.command("pipeline")
def validate_pipeline() -> None:
    """Validate pipeline directory structure and dependencies."""
    click.echo("🔍 Validating pipeline...\n")

    issues = []

    # Check required directories
    for name, path in [
        ("Inbox", INBOX_DIR),
        ("Markdown", MD_DIR),
    ]:
        if not path.exists():
            issues.append(f"Missing directory: {name} ({path})")

    # Check database
    if not DB_PATH.exists():
        issues.append(f"Database not found: {DB_PATH}")

    # Check preambles
    for name, path in [
        ("Clean preamble", TEX_DIR / "preamble.tex"),
        ("Notes preamble", TEX_DIR / "preamble_notes.tex"),
    ]:
        if not path.exists():
            issues.append(f"Missing preamble: {name} ({path})")

    if issues:
        click.echo("⚠️  Issues found:")
        for issue in issues:
            click.echo(f"  • {issue}")
        sys.exit(1)
    else:
        click.echo("✅ Pipeline validation passed!")


@validate.command("entry")
@click.argument("date", required=False)
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Validate specific file")
@click.option("--year", "-y", help="Validate all entries in year (e.g., 2024)")
@click.option("--years", help="Validate year range (e.g., 2021-2025)")
@click.option("--all", "validate_all", is_flag=True, help="Validate all entries")
@click.option("--quickfix", "-q", is_flag=True, help="Output in quickfix format for nvim")
def validate_entry(
    date: Optional[str],
    file_path: Optional[str],
    year: Optional[str],
    years: Optional[str],
    validate_all: bool,
    quickfix: bool,
) -> None:
    """
    Validate journal entries (MD + YAML).

    Validates MD frontmatter, metadata YAML structure, and consistency
    between them. Output is suitable for nvim quickfix integration.

    Examples:

        plm validate entry 2024-12-03

        plm validate entry --file data/metadata/journal/2024/2024-12-03.yaml

        plm validate entry --year 2024

        plm validate entry --quickfix 2024-12-03
    """
    from pathlib import Path
    from dev.core.paths import JOURNAL_YAML_DIR
    from dev.validators.entry import (
        validate_entry as do_validate_entry,
        validate_file as do_validate_file,
        validate_directory,
    )
    from dev.validators.diagnostic import ValidationReport

    def print_result(result: ValidationReport, quickfix: bool = False) -> int:
        """Print validation result and return exit code."""
        if quickfix:
            click.echo(result.quickfix_output())
        else:
            if result.errors:
                click.secho(f"\nErrors ({result.error_count}):", fg="red", bold=True)
                for error in result.errors:
                    click.echo(f"  {error.message}")

            if result.warnings:
                click.secho(f"\nWarnings ({result.warning_count}):", fg="yellow")
                for warning in result.warnings:
                    click.echo(f"  {warning.message}")

            if result.is_valid:
                click.secho("\n✓ Valid", fg="green")
            else:
                click.secho(f"\n✗ {result.error_count} error(s)", fg="red")

        return 0 if result.is_valid else 1

    exit_code = 0

    if file_path:
        result = do_validate_file(Path(file_path))
        exit_code = print_result(result, quickfix)

    elif date:
        result = do_validate_entry(date)
        exit_code = print_result(result, quickfix)

    elif year:
        year_dir = JOURNAL_YAML_DIR / year
        if not year_dir.exists():
            click.secho(f"Year directory not found: {year_dir}", fg="red")
            raise SystemExit(1)

        results = validate_directory(year_dir)
        total_errors = 0
        total_warnings = 0

        for path, result in results.items():
            if result.errors or result.warnings:
                if not quickfix:
                    click.echo(f"\n{Path(path).stem}:")
                exit_code = max(exit_code, print_result(result, quickfix))
            total_errors += len(result.errors)
            total_warnings += len(result.warnings)

        if not quickfix:
            click.echo(f"\n{'='*50}")
            click.echo(f"Total: {len(results)} files, {total_errors} errors, {total_warnings} warnings")

    elif years:
        if "-" in years:
            start, end = years.split("-")
            year_list = [str(y) for y in range(int(start), int(end) + 1)]
        else:
            year_list = [years]

        total_errors = 0
        total_warnings = 0
        total_files = 0

        for yr in year_list:
            year_dir = JOURNAL_YAML_DIR / yr
            if not year_dir.exists():
                continue

            if not quickfix:
                click.echo(f"\n{yr}:")

            results = validate_directory(year_dir)
            total_files += len(results)

            for path, result in results.items():
                if result.errors or result.warnings:
                    if not quickfix:
                        click.echo(f"  {Path(path).stem}:")
                    exit_code = max(exit_code, print_result(result, quickfix))
                total_errors += len(result.errors)
                total_warnings += len(result.warnings)

        if not quickfix:
            click.echo(f"\n{'='*50}")
            click.echo(f"Total: {total_files} files, {total_errors} errors, {total_warnings} warnings")

    elif validate_all:
        total_errors = 0
        total_warnings = 0
        total_files = 0

        for year_dir in sorted(JOURNAL_YAML_DIR.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            if not quickfix:
                click.echo(f"\n{year_dir.name}:")

            results = validate_directory(year_dir)
            total_files += len(results)

            for path, result in results.items():
                if result.errors or result.warnings:
                    if not quickfix:
                        click.echo(f"  {Path(path).stem}:")
                    exit_code = max(exit_code, print_result(result, quickfix))
                total_errors += len(result.errors)
                total_warnings += len(result.warnings)

        if not quickfix:
            click.echo(f"\n{'='*50}")
            click.echo(f"Total: {total_files} files, {total_errors} errors, {total_warnings} warnings")

    else:
        click.echo("Please specify: DATE, --file, --year, --years, or --all")
        raise SystemExit(1)

    raise SystemExit(exit_code)


# Register validator command groups from dev.validators.cli
validate.add_command(validate_db, "db")
validate.add_command(validate_md, "md")
validate.add_command(validate_frontmatter, "frontmatter")
validate.add_command(validate_consistency, "consistency")


__all__ = ["run_pipeline", "status", "validate"]

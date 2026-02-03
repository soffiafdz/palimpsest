"""
Maintenance & Utility Commands
--------------------------------

Commands for pipeline maintenance, backups, and status.

Commands:
    - backup-full: Create full backup
    - backup-list-full: List all backups
    - run-all: Run complete pipeline
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
    DATA_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.backup_manager import BackupManager
from dev.core.exceptions import BackupError
from dev.database.manager import PalimpsestDB
from dev.database.query_analytics import QueryAnalytics


@click.command("backup-full")
@click.option("--suffix", default=None, help="Optional backup suffix")
@click.pass_context
def backup_full(ctx: click.Context, suffix: Optional[str]) -> None:
    """
    Create full compressed backup of entire data directory.

    Creates a timestamped, compressed archive of the complete data directory
    including all files: md/, pdf/, txt/, database, etc.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📦 Creating full data backup...")
    click.echo("   (This may take a while for large archives)")

    try:
        backup_mgr = BackupManager(
            db_path=DB_PATH,
            backup_dir=BACKUP_DIR,
            data_dir=DATA_DIR,
            logger=logger,
        )

        backup_path = backup_mgr.create_full_backup(suffix=suffix)
        backup_size = backup_path.stat().st_size
        backup_size_mb = backup_size / (1024 * 1024)

        click.echo("\n✅ Full backup created:")
        click.echo(f"  Location: {backup_path}")
        click.echo(f"  Size: {backup_size_mb:.2f} MB ({backup_size:,} bytes)")
        click.echo("\n💡 Backup saved outside git repository")

    except BackupError as e:
        handle_cli_error(ctx, e, "backup_full")


@click.command("backup-list-full")
@click.pass_context
def backup_list_full(ctx: click.Context) -> None:
    """
    List all available full data backups.

    Scans the backup directory for full data backups and displays metadata
    for each backup file (creation date, size, age).
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        backup_mgr = BackupManager(
            db_path=DB_PATH,
            backup_dir=BACKUP_DIR,
            data_dir=DATA_DIR,
            logger=logger,
        )

        if (
            not hasattr(backup_mgr, "full_backup_dir")
            or not backup_mgr.full_backup_dir.exists()
        ):
            click.echo("📦 No full backups directory found")
            return

        backups = sorted(backup_mgr.full_backup_dir.glob("*.tar.gz"))

        if not backups:
            click.echo("📦 No full backups found")
            return

        click.echo("\n📦 Full Data Backups")
        click.echo("=" * 70)

        for backup in backups:
            stat = backup.stat()
            size_mb = stat.st_size / (1024 * 1024)
            created = datetime.fromtimestamp(stat.st_mtime)
            age_days = (datetime.now() - created).days

            click.echo(f"\n  • {backup.name}")
            click.echo(f"    Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"    Size: {size_mb:.2f} MB ({stat.st_size:,} bytes)")
            click.echo(f"    Age: {age_days} days")

        click.echo(f"\nTotal backups: {len(backups)}")
        click.echo(f"Location: {backup_mgr.full_backup_dir}")

    except Exception as e:
        handle_cli_error(ctx, e, "backup_list_full")


@click.command("run-all")
@click.option("--year", help="Specific year to process (optional)")
@click.option("--skip-inbox", is_flag=True, help="Skip inbox processing")
@click.option("--skip-pdf", is_flag=True, help="Skip PDF generation")
@click.option("--backup", is_flag=True, help="Create full data backup after completion")
@click.confirmation_option(prompt="Run complete pipeline?")
@click.pass_context
def run_all(
    ctx: click.Context,
    year: Optional[str],
    skip_inbox: bool,
    skip_pdf: bool,
    backup: bool,
) -> None:
    """
    Run the complete processing pipeline end-to-end.

    Orchestrates the entire journal processing pipeline in the correct order,
    ensuring data flows correctly from raw exports to final PDFs.
    """
    from .yaml2sql import inbox, convert, sync_db
    from .sql2wiki import build_pdf

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

        # Step 3: Sync database
        click.echo("=" * 60)
        ctx.invoke(sync_db, input=str(MD_DIR), force=False)
        click.echo()

        # Step 4: Build PDFs (if year specified)
        if not skip_pdf and year:
            click.echo("=" * 60)
            ctx.invoke(build_pdf, year=year, input=str(MD_DIR), output=str(PDF_DIR), force=False, debug=False)
            click.echo()

        # Step 5: Full backup (if requested)
        if backup:
            click.echo("=" * 60)
            ctx.invoke(backup_full, suffix="pipeline")
            click.echo()

        duration = (datetime.now() - start_time).total_seconds()

        click.echo("=" * 60)
        click.echo(f"\n✅ Pipeline complete! ({duration:.2f}s)")

    except Exception as e:
        handle_cli_error(ctx, e, "run_all")


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show pipeline status and statistics."""
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


@click.group()
def validate() -> None:
    """Validate pipeline and journal entries."""
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
        ValidationResult,
    )

    def print_result(result: ValidationResult, quickfix: bool = False) -> int:
        """Print validation result and return exit code."""
        if quickfix:
            for issue in result.all_issues:
                click.echo(issue.quickfix_line())
        else:
            if result.errors:
                click.secho(f"\nErrors ({len(result.errors)}):", fg="red", bold=True)
                for error in result.errors:
                    click.echo(f"  {error.message}")
                    if error.field:
                        click.echo(f"    Field: {error.field}")

            if result.warnings:
                click.secho(f"\nWarnings ({len(result.warnings)}):", fg="yellow")
                for warning in result.warnings:
                    click.echo(f"  {warning.message}")

            if result.is_valid:
                click.secho("\n✓ Valid", fg="green")
            else:
                click.secho(f"\n✗ {len(result.errors)} error(s)", fg="red")

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


__all__ = ["backup_full", "backup_list_full", "run_all", "status", "validate"]

"""
Consistency Validation Commands
--------------------------------

Commands for validating cross-system consistency.

Check consistency between markdown files and the database.
Detects orphaned entries, metadata mismatches, and referential integrity issues.

Commands:
    - existence: Check entry existence across MD ↔ DB
    - metadata: Check metadata synchronization between MD and DB
    - references: Check referential integrity constraints
    - integrity: Check file hash integrity
    - all: Run all consistency validation checks
"""
import click
from pathlib import Path

from dev.core.paths import MD_DIR, DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR


@click.group()
@click.option(
    "--md-dir",
    type=click.Path(exists=True),
    default=str(MD_DIR),
    help="Markdown directory",
)
@click.option(
    "--db-path", type=click.Path(), default=str(DB_PATH), help="Path to database file"
)
@click.option(
    "--alembic-dir",
    type=click.Path(),
    default=str(ALEMBIC_DIR),
    help="Path to Alembic migrations directory",
)
@click.option(
    "--log-dir", type=click.Path(), default=str(LOG_DIR), help="Directory for log files"
)
@click.pass_context
def consistency(
    ctx: click.Context,
    md_dir: str,
    db_path: str,
    alembic_dir: str,
    log_dir: str,
) -> None:
    """
    Validate cross-system consistency.

    Check consistency between markdown files and the database.
    Detects orphaned entries, metadata mismatches, and referential integrity issues.
    """
    from dev.core.cli import setup_logger
    from dev.database.manager import PalimpsestDB

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
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
    Check entry existence across MD ↔ DB.

    Validates that entries exist consistently across both systems.
    Detects orphaned entries and missing files.
    """
    from dev.validators.consistency import ConsistencyValidator

    db = ctx.obj["db"]
    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking entry existence across systems...\n")

    validator = ConsistencyValidator(db, md_dir, logger)
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
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking metadata consistency...\n")

    validator = ConsistencyValidator(db, md_dir, logger)
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
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking referential integrity...\n")

    validator = ConsistencyValidator(db, md_dir, logger)
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
            raise click.ClickException(
                f"Found {error_count} referential integrity error(s)"
            )
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
    logger = ctx.obj["logger"]

    click.echo("🔍 Checking file integrity...\n")

    validator = ConsistencyValidator(db, md_dir, logger)
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
    logger = ctx.obj["logger"]

    click.echo("🔍 Running comprehensive consistency validation...\n")

    validator = ConsistencyValidator(db, md_dir, logger)
    report = validator.validate_all()

    # Print formatted report
    click.echo(format_consistency_report(report))

    if not report.is_healthy:
        raise click.ClickException(
            f"Consistency validation failed with {report.total_errors} error(s)"
        )

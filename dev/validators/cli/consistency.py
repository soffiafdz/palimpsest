"""
Consistency Validation Commands
--------------------------------

Commands for validating cross-system consistency.

Check consistency between markdown files and the database.
Detects orphaned entries, metadata mismatches, and referential integrity issues.

Commands:
    - existence: Check entry existence across MD <-> DB
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
@click.option(
    "--format", "output_format", type=click.Choice(["text", "json"]),
    default="text", help="Output format",
)
@click.pass_context
def consistency(
    ctx: click.Context,
    md_dir: str,
    db_path: str,
    alembic_dir: str,
    log_dir: str,
    output_format: str,
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
    ctx.obj["output_format"] = output_format

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=Path(alembic_dir),
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


def _print_diagnostics(ctx: click.Context, diagnostics: list, check_name: str) -> None:
    """Print diagnostics using the configured output format."""
    from dev.validators.diagnostic import format_diagnostics

    fmt = ctx.obj.get("output_format", "text")
    if diagnostics:
        click.echo(format_diagnostics(diagnostics, fmt))
    elif fmt != "json":
        click.echo(f"[OK]{check_name}: passed")


@consistency.command()
@click.pass_context
def existence(ctx: click.Context) -> None:
    """
    Check entry existence across MD <-> DB.

    Validates that entries exist consistently across both systems.
    Detects orphaned entries and missing files.
    """
    from dev.validators.consistency import ConsistencyValidator

    validator = ConsistencyValidator(ctx.obj["db"], ctx.obj["md_dir"], ctx.obj["logger"])
    diagnostics = validator.check_entry_existence()

    _print_diagnostics(ctx, diagnostics, "Entry existence")

    if any(d.severity == "error" for d in diagnostics):
        error_count = sum(1 for d in diagnostics if d.severity == "error")
        raise click.ClickException(f"Found {error_count} existence error(s)")


@consistency.command()
@click.pass_context
def metadata(ctx: click.Context) -> None:
    """
    Check metadata synchronization between MD and DB.

    Validates that metadata fields match between markdown files and database.
    Detects word count mismatches, missing relationships, and field inconsistencies.
    """
    from dev.validators.consistency import ConsistencyValidator

    validator = ConsistencyValidator(ctx.obj["db"], ctx.obj["md_dir"], ctx.obj["logger"])
    diagnostics = validator.check_entry_metadata()

    _print_diagnostics(ctx, diagnostics, "Metadata consistency")

    if any(d.severity == "error" for d in diagnostics):
        error_count = sum(1 for d in diagnostics if d.severity == "error")
        raise click.ClickException(f"Found {error_count} metadata error(s)")


@consistency.command()
@click.pass_context
def references(ctx: click.Context) -> None:
    """
    Check referential integrity constraints.

    Validates that all foreign key references are valid and entities exist.
    Detects orphaned records and broken relationships.
    """
    from dev.validators.consistency import ConsistencyValidator

    validator = ConsistencyValidator(ctx.obj["db"], ctx.obj["md_dir"], ctx.obj["logger"])
    diagnostics = validator.check_referential_integrity()

    _print_diagnostics(ctx, diagnostics, "Referential integrity")

    if any(d.severity == "error" for d in diagnostics):
        error_count = sum(1 for d in diagnostics if d.severity == "error")
        raise click.ClickException(
            f"Found {error_count} referential integrity error(s)"
        )


@consistency.command()
@click.pass_context
def integrity(ctx: click.Context) -> None:
    """
    Check file hash integrity.

    Validates that markdown files haven't been modified since last sync.
    Detects out-of-sync files that need re-import.
    """
    from dev.validators.consistency import ConsistencyValidator

    validator = ConsistencyValidator(ctx.obj["db"], ctx.obj["md_dir"], ctx.obj["logger"])
    diagnostics = validator.check_file_integrity()

    _print_diagnostics(ctx, diagnostics, "File integrity")

    if any(d.severity == "error" for d in diagnostics):
        error_count = sum(1 for d in diagnostics if d.severity == "error")
        raise click.ClickException(f"Found {error_count} file integrity error(s)")


@consistency.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all consistency validation checks.

    Comprehensive validation including existence, metadata, references,
    and file integrity. Provides a complete health report across all systems.
    """
    from dev.validators.consistency import ConsistencyValidator
    from dev.validators.diagnostic import format_diagnostics

    validator = ConsistencyValidator(ctx.obj["db"], ctx.obj["md_dir"], ctx.obj["logger"])
    report = validator.validate_all()

    fmt = ctx.obj.get("output_format", "text")
    if report.diagnostics:
        click.echo(format_diagnostics(report.diagnostics, fmt))
    elif fmt != "json":
        click.echo("[OK]ALL SYSTEMS CONSISTENT")

    if not report.is_valid:
        raise click.ClickException(
            f"Consistency validation failed with {report.error_count} error(s)"
        )

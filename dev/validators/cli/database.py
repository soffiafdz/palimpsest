"""
Database Validation Commands
-----------------------------

Commands for validating database integrity, schema, and constraints.

Commands:
    - schema: Check for schema drift between models and database
    - migrations: Check if all migrations have been applied
    - integrity: Check for orphaned records and foreign key violations
    - constraints: Check for unique constraint violations
    - all: Run all database validation checks
"""
import click
from pathlib import Path

from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR


@click.group()
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
def db(ctx: click.Context, db_path: str, alembic_dir: str, log_dir: str, output_format: str) -> None:
    """
    Validate database integrity and constraints.

    Check for schema drift, pending migrations, foreign key violations,
    and unique constraint violations.
    """
    from dev.core.cli import setup_logger
    from dev.database.manager import PalimpsestDB

    ctx.ensure_object(dict)
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
        click.echo(f"✅ {check_name}: passed")


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

    validator = DatabaseValidator(ctx.obj["db"], ctx.obj["alembic_dir"], ctx.obj["logger"])
    diagnostics = validator.validate_schema()

    _print_diagnostics(ctx, diagnostics, "Schema Validation")

    if any(d.severity == "error" for d in diagnostics):
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

    validator = DatabaseValidator(ctx.obj["db"], ctx.obj["alembic_dir"], ctx.obj["logger"])
    diagnostics = validator.validate_migrations()

    _print_diagnostics(ctx, diagnostics, "Migration Status")

    if any(d.severity == "error" for d in diagnostics):
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

    validator = DatabaseValidator(ctx.obj["db"], ctx.obj["alembic_dir"], ctx.obj["logger"])
    diagnostics = validator.validate_foreign_keys()

    _print_diagnostics(ctx, diagnostics, "Foreign Key Integrity")

    if any(d.severity == "error" for d in diagnostics):
        raise click.ClickException("Foreign key validation failed")


@db.command()
@click.pass_context
def constraints(ctx: click.Context) -> None:
    """
    Check for unique constraint violations.

    Finds duplicate records that violate unique constraints or indexes.
    """
    from dev.validators.db import DatabaseValidator

    validator = DatabaseValidator(ctx.obj["db"], ctx.obj["alembic_dir"], ctx.obj["logger"])
    diagnostics = validator.validate_unique_constraints()

    _print_diagnostics(ctx, diagnostics, "Unique Constraints")

    if any(d.severity == "error" for d in diagnostics):
        raise click.ClickException("Constraint validation failed")


@db.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all database validation checks.

    Comprehensive validation including schema, migrations, foreign keys,
    and constraints. Provides a complete health report.
    """
    from dev.validators.db import DatabaseValidator
    from dev.validators.diagnostic import format_diagnostics

    validator = DatabaseValidator(ctx.obj["db"], ctx.obj["alembic_dir"], ctx.obj["logger"])
    report = validator.validate_all()

    fmt = ctx.obj.get("output_format", "text")
    if report.diagnostics:
        click.echo(format_diagnostics(report.diagnostics, fmt))
    elif fmt != "json":
        click.echo("✅ DATABASE IS HEALTHY")

    if not report.is_valid:
        raise click.ClickException(
            f"Database validation failed with {report.error_count} error(s)"
        )

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
@click.pass_context
def db(ctx: click.Context, db_path: str, alembic_dir: str, log_dir: str) -> None:
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
        raise click.ClickException(
            f"Database validation failed with {report.errors} error(s)"
        )

#!/usr/bin/env python3
"""
cli_decorators.py
-------------------
Custom Click decorators for Palimpsest CLIs.

Provides decorator factories that automatically set up consistent CLI interfaces
with logging, context management, and standard options.

Usage:
    from dev.core.cli_decorators import palimpsest_cli_group

    @palimpsest_cli_group("txt2md")
    def cli(ctx):
        '''txt2md - Convert text to Markdown'''
        pass  # Setup handled automatically
"""
from functools import wraps
from pathlib import Path
from typing import Callable
import click

from dev.core.cli_utils import setup_logger
from dev.core.paths import LOG_DIR


def palimpsest_cli_group(component_name: str) -> Callable:
    """
    Decorator factory for creating consistent CLI groups.

    Automatically adds:
    - Click group() decorator
    - --log-dir option
    - --verbose option
    - Context object setup with logger

    Args:
        component_name: Component identifier for logging (e.g., "txt2md", "yaml2sql")

    Returns:
        Decorator function

    Usage:
        @palimpsest_cli_group("txt2md")
        def cli(ctx):
            '''txt2md - Convert text to Markdown'''
            pass

    Provides context with:
        ctx.obj["log_dir"]: Path - Log directory
        ctx.obj["verbose"]: bool - Verbose flag
        ctx.obj["logger"]: PalimpsestLogger - Configured logger instance
    """
    def decorator(f: Callable) -> Callable:
        @click.group()
        @click.option(
            "--log-dir",
            type=click.Path(),
            default=str(LOG_DIR),
            help="Directory for log files"
        )
        @click.option(
            "-v", "--verbose",
            is_flag=True,
            help="Enable verbose logging"
        )
        @click.pass_context
        @wraps(f)
        def wrapper(ctx: click.Context, log_dir: str, verbose: bool):
            # Initialize context object
            ctx.ensure_object(dict)
            ctx.obj["log_dir"] = Path(log_dir)
            ctx.obj["verbose"] = verbose
            ctx.obj["logger"] = setup_logger(Path(log_dir), component_name)

            # Call original function
            return f(ctx)

        return wrapper
    return decorator


def palimpsest_command(
    requires_db: bool = False,
    confirmation: bool = False
) -> Callable:
    """
    Decorator factory for creating consistent CLI commands.

    Automatically adds common patterns like database initialization or
    confirmation prompts for destructive operations.

    Args:
        requires_db: If True, initializes database and adds to context
        confirmation: If True, adds confirmation prompt for destructive operation

    Returns:
        Decorator function

    Usage:
        @cli.command()
        @palimpsest_command(requires_db=True, confirmation=True)
        def reset(ctx):
            '''Reset database'''
            db = ctx.obj["db"]
            db.reset()

    Provides context with:
        ctx.obj["db"]: PalimpsestDB - Database instance (if requires_db=True)
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(ctx: click.Context, *args, **kwargs):
            # Add database if required
            if requires_db:
                from dev.database.manager import PalimpsestDB
                from dev.core.paths import DB_PATH, ALEMBIC_DIR, BACKUP_DIR

                if "db" not in ctx.obj:
                    ctx.obj["db"] = PalimpsestDB(
                        db_path=DB_PATH,
                        alembic_dir=ALEMBIC_DIR,
                        log_dir=ctx.obj.get("log_dir", LOG_DIR),
                        backup_dir=BACKUP_DIR,
                        enable_auto_backup=False,
                    )

            # Add confirmation if required
            if confirmation:
                if not ctx.obj.get("yes", False):
                    click.confirm(
                        "This operation will modify data. Continue?",
                        abort=True
                    )

            # Call original function
            return f(ctx, *args, **kwargs)

        # Add confirmation decorator if needed
        if confirmation:
            wrapper = click.confirmation_option(
                prompt="Are you sure?"
            )(wrapper)

        return wrapper
    return decorator

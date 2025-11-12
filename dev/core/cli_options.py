#!/usr/bin/env python3
"""
cli_options.py
-------------------
Reusable Click option decorators for consistent CLI interfaces.

Provides standardized Click options that can be reused across all CLI scripts
to ensure consistency in flag names, help text, and behavior.

Usage:
    from dev.core.cli_options import verbose_option, force_option, input_option

    @cli.command()
    @input_option()
    @verbose_option
    @force_option
    def my_command(input, verbose, force):
        pass
"""
import click
from dev.core.paths import LOG_DIR


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING OPTIONS
# ═══════════════════════════════════════════════════════════════════════════

verbose_option = click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Enable verbose logging with detailed output"
)

log_dir_option = click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files"
)


# ═══════════════════════════════════════════════════════════════════════════
# FILE OPERATION OPTIONS
# ═══════════════════════════════════════════════════════════════════════════

force_option = click.option(
    "-f", "--force",
    is_flag=True,
    help="Force overwrite existing files"
)

dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without executing (no files modified)"
)

quiet_option = click.option(
    "-q", "--quiet",
    is_flag=True,
    help="Suppress all non-error output"
)


# ═══════════════════════════════════════════════════════════════════════════
# PATH OPTIONS (FACTORIES)
# ═══════════════════════════════════════════════════════════════════════════

def input_option(default=None, required=False, help_text="Input directory or file"):
    """
    Factory function for input path option with validation.

    Creates a Click option that validates the path exists.
    Using a factory function allows customization of defaults and help text
    while maintaining consistent validation behavior.

    Args:
        default: Default path value (optional)
        required: Whether the option is required (default: False)
        help_text: Custom help text (default: "Input directory or file")

    Returns:
        Click option decorator
    """
    return click.option(
        "-i", "--input",
        type=click.Path(exists=True),
        default=default,
        required=required,
        help=help_text
    )


def output_option(default=None, required=False, help_text="Output directory or file"):
    """
    Factory function for output path option.

    Creates a Click option for output paths. Unlike input_option,
    this does NOT validate existence (output paths may not exist yet).
    Using a factory function allows customization while maintaining
    consistent behavior across commands.

    Args:
        default: Default path value (optional)
        required: Whether the option is required (default: False)
        help_text: Custom help text (default: "Output directory or file")

    Returns:
        Click option decorator
    """
    return click.option(
        "-o", "--output",
        type=click.Path(),
        default=default,
        required=required,
        help=help_text
    )


def db_path_option(default=None):
    """
    Factory function for database path option with validation.

    Creates a Click option that validates the database path exists.
    Consistent with input_option validation behavior.

    Args:
        default: Default database path (typically from paths.DB_PATH)

    Returns:
        Click option decorator
    """
    # Convert Path to string, but avoid converting None to "None"
    default_str = str(default) if default is not None else None

    return click.option(
        "--db-path",
        type=click.Path(exists=True),
        default=default_str,
        help="Path to database file"
    )


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN/FILTER OPTIONS
# ═══════════════════════════════════════════════════════════════════════════

pattern_option = click.option(
    "-p", "--pattern",
    default="**/*.md",
    help="File pattern to match using glob syntax (default: **/*.md - all Markdown files)"
)

year_option = click.option(
    "--year",
    type=int,
    help="Filter by specific year"
)


# ═══════════════════════════════════════════════════════════════════════════
# CONFIRMATION OPTIONS
# ═══════════════════════════════════════════════════════════════════════════

yes_option = click.option(
    "-y", "--yes",
    is_flag=True,
    help="Skip confirmation prompts"
)


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT FORMAT OPTIONS
# ═══════════════════════════════════════════════════════════════════════════

json_option = click.option(
    "--json",
    is_flag=True,
    help="Output in JSON format"
)

format_option = click.option(
    "--format",
    type=click.Choice(["text", "json", "csv"], case_sensitive=False),
    default="text",
    help="Output format"
)


# ═══════════════════════════════════════════════════════════════════════════
# BACKUP/SNAPSHOT OPTIONS
# ═══════════════════════════════════════════════════════════════════════════

backup_suffix_option = click.option(
    "--suffix",
    default=None,
    help="Optional suffix for backup filename"
)

backup_type_option = click.option(
    "--type",
    type=click.Choice(["manual", "daily", "weekly"], case_sensitive=False),
    default="manual",
    help="Backup type"
)

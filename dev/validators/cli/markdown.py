"""
Markdown Validation Commands
-----------------------------

Commands for validating markdown journal entry files.

Commands:
    - frontmatter: Validate YAML frontmatter in markdown files
    - links: Check for broken internal markdown links
    - all: Run all markdown validation checks
"""
import click
from pathlib import Path
from typing import Optional

from dev.core.paths import MD_DIR, LOG_DIR


@click.group()
@click.option(
    "--md-dir",
    type=click.Path(exists=True),
    default=str(MD_DIR),
    help="Markdown directory to validate",
)
@click.option(
    "--log-dir", type=click.Path(), default=str(LOG_DIR), help="Directory for log files"
)
@click.option(
    "--format", "output_format", type=click.Choice(["text", "json"]),
    default="text", help="Output format",
)
@click.pass_context
def md(ctx: click.Context, md_dir: str, log_dir: str, output_format: str) -> None:
    """
    Validate markdown journal entry files.

    Check for YAML frontmatter issues, broken links, malformed structure,
    and content problems.
    """
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")
    ctx.obj["output_format"] = output_format


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
    from dev.validators.md import MarkdownValidator
    from dev.validators.diagnostic import format_diagnostics

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]
    fmt = ctx.obj.get("output_format", "text")

    validator = MarkdownValidator(md_dir, logger)

    if file_path:
        diagnostics = validator.validate_file(Path(file_path))
        fm_diagnostics = [d for d in diagnostics if d.code.startswith("FRONTMATTER")]
        if fm_diagnostics:
            click.echo(format_diagnostics(fm_diagnostics, fmt))
            error_count = sum(1 for d in fm_diagnostics if d.severity == "error")
            if error_count > 0:
                raise click.ClickException(f"Found {error_count} frontmatter error(s)")
        elif fmt != "json":
            click.echo("[OK]No frontmatter issues found")
    else:
        report = validator.validate_all()
        fm_diagnostics = [d for d in report.diagnostics if d.code.startswith("FRONTMATTER")]

        if fm_diagnostics:
            click.echo(format_diagnostics(fm_diagnostics, fmt))
            error_count = sum(1 for d in fm_diagnostics if d.severity == "error")
            if error_count > 0:
                raise click.ClickException(f"Found {error_count} frontmatter error(s)")
        elif fmt != "json":
            click.echo("[OK]No frontmatter issues found")


@md.command()
@click.pass_context
def links(ctx: click.Context) -> None:
    """
    Check for broken internal markdown links.

    Validates that all relative markdown links point to existing files.
    External links (http://, https://) are skipped.
    """
    from dev.validators.md import MarkdownValidator
    from dev.validators.diagnostic import format_diagnostics

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]
    fmt = ctx.obj.get("output_format", "text")

    validator = MarkdownValidator(md_dir, logger)
    diagnostics = validator.validate_links()

    if diagnostics:
        click.echo(format_diagnostics(diagnostics, fmt))
        raise click.ClickException(f"Found {len(diagnostics)} broken link(s)")
    elif fmt != "json":
        click.echo("[OK]All markdown links are valid")


@md.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all markdown validation checks.

    Comprehensive validation including frontmatter, links, structure,
    and content. Provides a complete health report.
    """
    from dev.validators.md import MarkdownValidator
    from dev.validators.diagnostic import format_diagnostics

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]
    fmt = ctx.obj.get("output_format", "text")

    validator = MarkdownValidator(md_dir, logger)
    report = validator.validate_all()

    # Also check links
    link_diagnostics = validator.validate_links()
    report.diagnostics.extend(link_diagnostics)

    if report.diagnostics:
        click.echo(format_diagnostics(report.diagnostics, fmt))
    elif fmt != "json":
        click.echo("[OK]ALL FILES VALID")

    if not report.is_valid:
        raise click.ClickException(
            f"Markdown validation failed with {report.error_count} error(s)"
        )

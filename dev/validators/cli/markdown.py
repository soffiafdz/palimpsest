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
@click.pass_context
def md(ctx: click.Context, md_dir: str, log_dir: str) -> None:
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
        frontmatter_issues = [i for i in (report.issues or []) if i.category == "frontmatter"]
        report.issues = frontmatter_issues
        report.total_errors = sum(1 for i in frontmatter_issues if i.severity == "error")
        report.total_warnings = sum(
            1 for i in frontmatter_issues if i.severity == "warning"
        )

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
        raise click.ClickException(
            f"Markdown validation failed with {report.total_errors} error(s)"
        )

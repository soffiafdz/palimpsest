"""
Frontmatter Validation Commands
--------------------------------

Commands for validating YAML frontmatter structure and compatibility.

Check that frontmatter structures match parser expectations, including
YAML syntax, field types, special character usage, cross-field
dependencies, and structural rules.

Commands:
    - people: Validate people field structures
    - locations: Validate locations-city dependency
    - dates: Validate dates field structures
    - references: Validate references field structures
    - poems: Validate poems field structures
    - all: Run all frontmatter validation checks
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
def frontmatter(ctx: click.Context, md_dir: str, log_dir: str, output_format: str) -> None:
    """
    Validate YAML frontmatter structure and compatibility.

    Comprehensive validation of frontmatter including YAML syntax, field types,
    special character usage, cross-field dependencies, and structural rules.
    """
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")
    ctx.obj["output_format"] = output_format


def _filter_by_code_prefix(diagnostics: list, prefix: str) -> list:
    """Filter diagnostics by code prefix."""
    return [d for d in diagnostics if d.code.startswith(prefix)]


def _print_filtered(ctx: click.Context, diagnostics: list, label: str) -> None:
    """Print filtered diagnostics using configured format."""
    from dev.validators.diagnostic import format_diagnostics

    fmt = ctx.obj.get("output_format", "text")
    if diagnostics:
        click.echo(format_diagnostics(diagnostics, fmt))
        error_count = sum(1 for d in diagnostics if d.severity == "error")
        if error_count > 0:
            raise click.ClickException(f"Found {error_count} {label} error(s)")
    elif fmt != "json":
        click.echo(f"✅ No {label} issues found")


@frontmatter.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def people(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate people field structures.

    Checks for:
    - Proper alias format (@prefix)
    - Parentheses spacing and format
    - Hyphenated name handling
    - Dict structure (name/full_name/alias fields)
    """
    from dev.validators.frontmatter import FrontmatterValidator

    validator = FrontmatterValidator(ctx.obj["md_dir"], ctx.obj["logger"])

    if file_path:
        issues = validator.validate_file(Path(file_path))
    else:
        report = validator.validate_all()
        issues = report.diagnostics

    people_issues = _filter_by_code_prefix(issues, "PEOPLE")
    _print_filtered(ctx, people_issues, "people metadata")


@frontmatter.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def locations(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate locations-city dependency.

    Checks for:
    - Flat list requires exactly 1 city
    - Nested dict allows multiple cities
    - Dict keys match city list
    - Location name references (#prefix in context)
    """
    from dev.validators.frontmatter import FrontmatterValidator

    validator = FrontmatterValidator(ctx.obj["md_dir"], ctx.obj["logger"])

    if file_path:
        issues = validator.validate_file(Path(file_path))
    else:
        report = validator.validate_all()
        issues = report.diagnostics

    location_issues = _filter_by_code_prefix(issues, "LOCATION")
    _print_filtered(ctx, location_issues, "locations metadata")


@frontmatter.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def dates(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate dates field structures.

    Checks for:
    - ISO date format (YYYY-MM-DD)
    - Inline context with @people and #locations refs
    - Dict structure (date, context, people, locations)
    - Opt-out marker (~)
    - Parentheses balance in context
    """
    from dev.validators.frontmatter import FrontmatterValidator

    validator = FrontmatterValidator(ctx.obj["md_dir"], ctx.obj["logger"])

    if file_path:
        issues = validator.validate_file(Path(file_path))
    else:
        report = validator.validate_all()
        issues = report.diagnostics

    date_issues = _filter_by_code_prefix(issues, "DATE")
    _print_filtered(ctx, date_issues, "dates metadata")


@frontmatter.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def references(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate references field structures.

    Checks for:
    - Required content or description field
    - Valid mode enum (direct, indirect, paraphrase, visual)
    - Valid source type enum (book, article, film, etc.)
    - Source structure
    """
    from dev.validators.frontmatter import FrontmatterValidator

    validator = FrontmatterValidator(ctx.obj["md_dir"], ctx.obj["logger"])

    if file_path:
        issues = validator.validate_file(Path(file_path))
    else:
        report = validator.validate_all()
        issues = report.diagnostics

    ref_issues = _filter_by_code_prefix(issues, "REFERENCE")
    _print_filtered(ctx, ref_issues, "references metadata")


@frontmatter.command()
@click.argument("file_path", type=click.Path(exists=True), required=False)
@click.pass_context
def poems(ctx: click.Context, file_path: Optional[str]) -> None:
    """
    Validate poems field structures.

    Checks for:
    - Required title field
    - Required content field
    - Optional revision_date in ISO format
    """
    from dev.validators.frontmatter import FrontmatterValidator

    validator = FrontmatterValidator(ctx.obj["md_dir"], ctx.obj["logger"])

    if file_path:
        issues = validator.validate_file(Path(file_path))
    else:
        report = validator.validate_all()
        issues = report.diagnostics

    poem_issues = _filter_by_code_prefix(issues, "POEM")
    _print_filtered(ctx, poem_issues, "poems metadata")


@frontmatter.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all metadata validation checks.

    Comprehensive validation of all metadata fields for parser compatibility.
    Checks people, locations, dates, references, poems, and manuscript structures.
    """
    from dev.validators.frontmatter import FrontmatterValidator
    from dev.validators.diagnostic import format_diagnostics

    validator = FrontmatterValidator(ctx.obj["md_dir"], ctx.obj["logger"])
    report = validator.validate_all()

    fmt = ctx.obj.get("output_format", "text")
    if report.diagnostics:
        click.echo(format_diagnostics(report.diagnostics, fmt))
    elif fmt != "json":
        click.echo("✅ ALL FRONTMATTER VALID")

    if not report.is_valid:
        raise click.ClickException(
            f"Metadata validation failed with {report.error_count} error(s)"
        )

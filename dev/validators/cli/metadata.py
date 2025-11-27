"""
Metadata Validation Commands
-----------------------------

Commands for validating metadata parser compatibility.

Check that frontmatter structures match parser expectations, including
special character usage, cross-field dependencies, and structural rules.

Commands:
    - people: Validate people field structures
    - locations: Validate locations-city dependency
    - dates: Validate dates field structures
    - references: Validate references field structures
    - poems: Validate poems field structures
    - all: Run all metadata validation checks
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
def metadata(ctx: click.Context, md_dir: str, log_dir: str) -> None:
    """
    Validate metadata parser compatibility.

    Check that frontmatter structures match parser expectations, including
    special character usage, cross-field dependencies, and structural rules.
    """
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["md_dir"] = Path(md_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")


@metadata.command()
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
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating people metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        people_issues = [i for i in issues if i.field_name.startswith("people")]
        if people_issues:
            for issue in people_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No people metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only people issues
        people_issues = [i for i in report.issues if i.field_name.startswith("people")]
        report.issues = people_issues
        report.total_errors = sum(1 for i in people_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in people_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(
                f"Found {report.total_errors} people metadata error(s)"
            )


@metadata.command()
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
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating locations metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        location_issues = [
            i
            for i in issues
            if i.field_name.startswith("locations") or i.field_name.startswith("city")
        ]
        if location_issues:
            for issue in location_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No locations metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only locations issues
        location_issues = [
            i
            for i in report.issues
            if i.field_name.startswith("locations") or i.field_name.startswith("city")
        ]
        report.issues = location_issues
        report.total_errors = sum(1 for i in location_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in location_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(
                f"Found {report.total_errors} locations metadata error(s)"
            )


@metadata.command()
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
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating dates metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        date_issues = [i for i in issues if i.field_name.startswith("dates")]
        if date_issues:
            for issue in date_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No dates metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only dates issues
        date_issues = [i for i in report.issues if i.field_name.startswith("dates")]
        report.issues = date_issues
        report.total_errors = sum(1 for i in date_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in date_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(
                f"Found {report.total_errors} dates metadata error(s)"
            )


@metadata.command()
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
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating references metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        ref_issues = [i for i in issues if i.field_name.startswith("references")]
        if ref_issues:
            for issue in ref_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No references metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only references issues
        ref_issues = [i for i in report.issues if i.field_name.startswith("references")]
        report.issues = ref_issues
        report.total_errors = sum(1 for i in ref_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in ref_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(
                f"Found {report.total_errors} references metadata error(s)"
            )


@metadata.command()
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
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Validating poems metadata in {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)

    if file_path:
        # Validate single file
        issues = validator.validate_file(Path(file_path))
        poem_issues = [i for i in issues if i.field_name.startswith("poems")]
        if poem_issues:
            for issue in poem_issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                click.echo(f"{icon} {issue.message}")
                if issue.suggestion:
                    click.echo(f"   💡 {issue.suggestion}")
        else:
            click.echo("✅ No poems metadata issues found")
    else:
        # Validate all files
        report = validator.validate_all()

        # Filter to only poems issues
        poem_issues = [i for i in report.issues if i.field_name.startswith("poems")]
        report.issues = poem_issues
        report.total_errors = sum(1 for i in poem_issues if i.severity == "error")
        report.total_warnings = sum(1 for i in poem_issues if i.severity == "warning")

        click.echo(format_metadata_report(report))

        if report.has_errors:
            raise click.ClickException(
                f"Found {report.total_errors} poems metadata error(s)"
            )


@metadata.command()
@click.pass_context
def all(ctx: click.Context) -> None:
    """
    Run all metadata validation checks.

    Comprehensive validation of all metadata fields for parser compatibility.
    Checks people, locations, dates, references, poems, and manuscript structures.
    """
    from dev.validators.metadata import MetadataValidator, format_metadata_report

    md_dir = ctx.obj["md_dir"]
    logger = ctx.obj["logger"]

    click.echo(f"🔍 Running comprehensive metadata validation on {md_dir}\n")

    validator = MetadataValidator(md_dir, logger)
    report = validator.validate_all()

    # Print formatted report
    click.echo(format_metadata_report(report))

    if not report.is_healthy:
        raise click.ClickException(
            f"Metadata validation failed with {report.total_errors} error(s)"
        )

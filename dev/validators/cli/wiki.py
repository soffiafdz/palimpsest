"""
Wiki Validation Commands
-------------------------

Commands for validating wiki link integrity, finding orphans, and statistics.

Commands:
    - check: Check all wiki links for broken references
    - orphans: Find orphaned wiki pages with no incoming links
    - stats: Show wiki link statistics
"""
import click
from pathlib import Path

from dev.core.paths import WIKI_DIR, LOG_DIR


@click.group()
@click.option(
    "--wiki-dir",
    type=click.Path(exists=True),
    default=str(WIKI_DIR),
    help="Wiki directory to validate",
)
@click.option(
    "--log-dir", type=click.Path(), default=str(LOG_DIR), help="Directory for log files"
)
@click.pass_context
def wiki(ctx: click.Context, wiki_dir: str, log_dir: str) -> None:
    """
    Validate wiki link integrity.

    Check for broken links, orphaned pages, and generate statistics
    about wiki link structure.
    """
    # Import here to avoid circular dependencies and load only when needed
    from dev.core.cli import setup_logger

    ctx.ensure_object(dict)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validators")


@wiki.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """
    Check all wiki links for broken references.

    Parses all wiki files, extracts [[link]] references, and validates
    that target files exist. Reports broken links with file locations.
    """
    from dev.validators.wiki import validate_wiki, print_validation_report

    wiki_dir = ctx.obj["wiki_dir"]

    click.echo(f"🔍 Validating wiki links in {wiki_dir}\n")

    result = validate_wiki(wiki_dir)
    print_validation_report(result, wiki_dir)

    if result.broken_links:
        raise click.ClickException(f"Found {len(result.broken_links)} broken links")


@wiki.command()
@click.pass_context
def orphans(ctx: click.Context) -> None:
    """
    Find orphaned wiki pages with no incoming links.

    Analyzes the wiki link graph to find pages that have no other pages
    linking to them. These may be dead content that should be removed
    or linked from somewhere.
    """
    from dev.validators.wiki import validate_wiki, print_orphans_report

    wiki_dir = ctx.obj["wiki_dir"]

    click.echo(f"🔍 Finding orphaned pages in {wiki_dir}\n")

    result = validate_wiki(wiki_dir)
    print_orphans_report(result, wiki_dir)


@wiki.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """
    Show wiki link statistics.

    Display summary statistics about wiki structure: total files,
    total links, broken links, orphans, and link density.
    """
    from dev.validators.wiki import validate_wiki, print_stats_report

    wiki_dir = ctx.obj["wiki_dir"]

    click.echo(f"📊 Wiki statistics for {wiki_dir}\n")

    result = validate_wiki(wiki_dir)
    print_stats_report(result, wiki_dir)

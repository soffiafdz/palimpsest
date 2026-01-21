"""
Validators CLI Package
----------------------

Unified CLI for Palimpsest validators.

Provides a single entry point for running various validation checks across
the Palimpsest system. Each validator checks a specific aspect of data
integrity or quality.

Available validators:
    - wiki: Wiki link integrity, orphan detection, broken links
    - db: Database referential integrity, constraint violations
    - md: Markdown file validation, broken links, malformed frontmatter
    - frontmatter: YAML frontmatter structure and parser compatibility
    - consistency: Cross-system consistency (wiki ↔ db, md ↔ db)

Note: The 'metadata' command has been renamed to 'frontmatter' for clarity.

Architecture:
    This CLI aggregates validators from individual modules (wiki.py, db.py, etc.)
    Each validator module has its own command group and subcommands.

Usage:
    validate wiki check         # Check all wiki links
    validate wiki orphans       # Find orphaned wiki pages
    validate wiki stats         # Show wiki statistics

    validate db schema          # Check database schema
    validate db migrations      # Check migration status
    validate db all             # Run all database checks

    validate md frontmatter     # Validate YAML frontmatter
    validate md links           # Check markdown links
    validate md all             # Run all markdown checks

    validate frontmatter people # Validate people metadata
    validate frontmatter all    # Run all frontmatter checks

    validate consistency existence   # Check entry existence
    validate consistency all         # Run all consistency checks

Note: Simple validators remain in their respective CLIs:
    - `plm validate` - Pipeline structure validation
    - `metadb health` - Database health check
"""
import click

# Import command groups from submodules
from .wiki import wiki
from .database import db
from .markdown import md
from .frontmatter import frontmatter
from .consistency import consistency


@click.group()
def cli():
    """
    Palimpsest Validation Suite.

    Run comprehensive validation checks on wiki links, database integrity,
    markdown files, and YAML frontmatter.
    """
    pass


# Register all command groups
cli.add_command(wiki)
cli.add_command(db)
cli.add_command(md)
cli.add_command(frontmatter)
cli.add_command(consistency)


if __name__ == "__main__":
    cli()

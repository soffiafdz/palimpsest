"""
Validators CLI Package
----------------------

Unified CLI for Palimpsest validators.

Provides a single entry point for running various validation checks across
the Palimpsest system. Each validator checks a specific aspect of data
integrity or quality.

Available validators:
    - db: Database referential integrity, constraint violations
    - md: Markdown file validation, broken links, malformed frontmatter
    - frontmatter: YAML frontmatter structure and parser compatibility
    - consistency: Cross-system consistency (md ↔ db)

Note: The 'metadata' command has been renamed to 'frontmatter' for clarity.

Architecture:
    This CLI aggregates validators from individual modules (db.py, etc.)
    Each validator module has its own command group and subcommands.

Usage:
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
from .consistency import consistency
from .database import db
from .frontmatter import frontmatter
from .markdown import md


@click.group()
def cli():
    """
    Palimpsest Validation Suite.

    Run comprehensive validation checks on database integrity,
    markdown files, and YAML frontmatter.
    """
    pass


# Register all command groups
cli.add_command(consistency)
cli.add_command(db)
cli.add_command(frontmatter)
cli.add_command(md)


if __name__ == "__main__":
    cli()

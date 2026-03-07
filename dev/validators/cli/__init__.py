"""
Validators CLI Package
----------------------

Command groups for Palimpsest validation, registered under ``plm validate``.

Each validator checks a specific aspect of data integrity or quality.
The command groups defined here are imported and registered on the
``plm validate`` command group in ``dev.pipeline.cli.maintenance``.

Available validators:
    - db: Database referential integrity, constraint violations
    - md: Markdown file validation, broken links, malformed frontmatter
    - frontmatter: YAML frontmatter structure and parser compatibility
    - consistency: Cross-system consistency (md <-> db)

Usage:
    plm validate db schema          # Check database schema
    plm validate db migrations      # Check migration status
    plm validate db all             # Run all database checks

    plm validate md frontmatter     # Validate YAML frontmatter
    plm validate md links           # Check markdown links
    plm validate md all             # Run all markdown checks

    plm validate frontmatter people # Validate people metadata
    plm validate frontmatter all    # Run all frontmatter checks

    plm validate consistency existence   # Check entry existence
    plm validate consistency all         # Run all consistency checks
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

#!/usr/bin/env python3
"""
wiki.py
-------
Wiki link integrity validator.

Validates that all wiki links point to existing files and detects
orphaned pages with no incoming links.

Features:
- Parse all wiki files for [[link]] references
- Check if target files exist
- Report broken links
- Find orphaned pages
- Suggest fixes for common issues

This validator is part of the validators package and can be run through
the unified `validate` CLI or imported for programmatic use.

Usage (through CLI):
    validate wiki check
    validate wiki orphans
    validate wiki stats

Usage (programmatic):
    from dev.validators.wiki import validate_wiki, ValidationResult
"""
from __future__ import annotations

import re
import sys
import click
from pathlib import Path
from typing import List, Set, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from dev.core.paths import WIKI_DIR, LOG_DIR
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.cli import setup_logger


class WikiValidationError(Exception):
    """Raised when wiki validation encounters an error."""
    pass


@dataclass
class WikiLink:
    """Represents a wiki link found in a file."""
    source_file: Path
    target_path: str  # As written in the wiki link
    display_text: str
    line_number: int

    @property
    def resolved_target(self) -> Path:
        """Resolve the target path relative to source file's directory."""
        # Wiki links are relative to the source file's directory
        source_dir = self.source_file.parent
        return (source_dir / self.target_path).resolve()


@dataclass
class ValidationResult:
    """Results from wiki validation."""
    total_files: int = 0
    total_links: int = 0
    broken_links: List[WikiLink] = field(default_factory=list)
    orphaned_files: List[Path] = field(default_factory=list)
    valid_links: int = 0

    # Link graph for orphan detection
    all_files: Set[Path] = field(default_factory=set)
    files_with_incoming_links: Set[Path] = field(default_factory=set)

    def add_link(self, link: WikiLink, exists: bool) -> None:
        """Add a link to the validation results."""
        self.total_links += 1
        if exists:
            self.valid_links += 1
            self.files_with_incoming_links.add(link.resolved_target)
        else:
            self.broken_links.append(link)

    def calculate_orphans(self) -> None:
        """Calculate orphaned files (no incoming links)."""
        # Exclude index files and special files from orphan detection
        excluded_names = {"index.md", "timeline.md"}

        for file in self.all_files:
            if file.name in excluded_names:
                continue
            if file not in self.files_with_incoming_links:
                self.orphaned_files.append(file)


def parse_wiki_links(file_path: Path) -> List[WikiLink]:
    """
    Parse all wiki links from a file.

    Vimwiki link format: [[path/to/file.md|Display Text]]

    Args:
        file_path: Path to wiki markdown file

    Returns:
        List of WikiLink objects
    """
    if not file_path.exists():
        return []

    links = []
    content = file_path.read_text(encoding="utf-8")

    # Pattern: [[path|text]] or [[path]]
    pattern = r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'

    for line_num, line in enumerate(content.split('\n'), start=1):
        for match in re.finditer(pattern, line):
            target_path = match.group(1).strip()
            display_text = match.group(2).strip() if match.group(2) else target_path

            links.append(WikiLink(
                source_file=file_path,
                target_path=target_path,
                display_text=display_text,
                line_number=line_num
            ))

    return links


def find_all_wiki_files(wiki_dir: Path) -> List[Path]:
    """
    Find all markdown files in wiki directory.

    Args:
        wiki_dir: Root wiki directory

    Returns:
        List of Path objects for all .md files
    """
    if not wiki_dir.exists():
        return []

    return sorted(wiki_dir.rglob("*.md"))


def validate_wiki(
    wiki_dir: Path,
    logger: Optional[PalimpsestLogger] = None,
) -> ValidationResult:
    """
    Validate all wiki links.

    Args:
        wiki_dir: Root wiki directory
        logger: Optional logger

    Returns:
        ValidationResult with findings
    """
    if logger:
        logger.log_operation("validate_wiki_start", {"wiki_dir": str(wiki_dir)})

    result = ValidationResult()

    # Find all wiki files
    all_files = find_all_wiki_files(wiki_dir)
    result.total_files = len(all_files)
    result.all_files = set(all_files)

    if logger:
        logger.log_info(f"Found {len(all_files)} wiki files")

    # Parse links from each file
    for wiki_file in all_files:
        links = parse_wiki_links(wiki_file)

        for link in links:
            # Check if target exists
            target_exists = link.resolved_target.exists()
            result.add_link(link, target_exists)

            if logger and not target_exists:
                logger.log_warning(
                    f"Broken link: {wiki_file.relative_to(wiki_dir)} → "
                    f"{link.target_path} (line {link.line_number})"
                )

    # Calculate orphaned files
    result.calculate_orphans()

    if logger:
        logger.log_operation("validate_wiki_complete", {
            "total_files": result.total_files,
            "total_links": result.total_links,
            "broken_links": len(result.broken_links),
            "orphaned_files": len(result.orphaned_files),
        })

    return result


def print_validation_report(result: ValidationResult, wiki_dir: Path) -> None:
    """
    Print validation report to stdout.

    Args:
        result: ValidationResult to report
        wiki_dir: Wiki directory for relative paths
    """
    click.echo("\n" + "=" * 70)
    click.echo("WIKI VALIDATION REPORT")
    click.echo("=" * 70)

    # Summary
    click.echo("\n📊 Summary:")
    click.echo(f"  Total wiki files: {result.total_files}")
    click.echo(f"  Total links: {result.total_links}")
    click.echo(f"  Valid links: {result.valid_links} ✅")
    click.echo(f"  Broken links: {len(result.broken_links)} ❌")
    click.echo(f"  Orphaned files: {len(result.orphaned_files)} 🔗")

    # Broken links
    if result.broken_links:
        click.echo(f"\n❌ Broken Links ({len(result.broken_links)}):")
        click.echo("-" * 70)

        # Group by source file
        by_source = defaultdict(list)
        for link in result.broken_links:
            by_source[link.source_file].append(link)

        for source_file in sorted(by_source.keys()):
            rel_path = source_file.relative_to(wiki_dir)
            click.echo(f"\n  {rel_path}:")
            for link in by_source[source_file]:
                click.echo(f"    Line {link.line_number}: [[{link.target_path}|{link.display_text}]]")
                click.echo(f"      → {link.resolved_target} (missing)")
    else:
        click.echo("\n✅ No broken links found!")

    # Orphaned files
    if result.orphaned_files:
        click.echo(f"\n🔗 Orphaned Files ({len(result.orphaned_files)}):")
        click.echo("-" * 70)
        click.echo("  Files with no incoming links:\n")

        for orphan in sorted(result.orphaned_files):
            rel_path = orphan.relative_to(wiki_dir)
            click.echo(f"    - {rel_path}")
    else:
        click.echo("\n✅ No orphaned files found!")

    click.echo("\n" + "=" * 70 + "\n")


def print_orphans_report(result: ValidationResult, wiki_dir: Path) -> None:
    """
    Print orphaned files report.

    Args:
        result: ValidationResult with orphans
        wiki_dir: Wiki directory for relative paths
    """
    click.echo("\n" + "=" * 70)
    click.echo("ORPHANED FILES REPORT")
    click.echo("=" * 70)

    if not result.orphaned_files:
        click.echo("\n✅ No orphaned files found!")
        click.echo("\n" + "=" * 70 + "\n")
        return

    click.echo(f"\n🔗 Found {len(result.orphaned_files)} orphaned files")
    click.echo("   (files with no incoming links)\n")

    # Group by directory
    by_dir = defaultdict(list)
    for orphan in result.orphaned_files:
        parent = orphan.parent.relative_to(wiki_dir)
        by_dir[parent].append(orphan.name)

    for directory in sorted(by_dir.keys()):
        click.echo(f"  {directory}/")
        for filename in sorted(by_dir[directory]):
            click.echo(f"    - {filename}")
        click.echo()

    click.echo("=" * 70 + "\n")


def print_stats_report(result: ValidationResult, wiki_dir: Path) -> None:
    """
    Print statistics report.

    Args:
        result: ValidationResult with stats
        wiki_dir: Wiki directory
    """
    click.echo("\n" + "=" * 70)
    click.echo("WIKI STATISTICS")
    click.echo("=" * 70)

    click.echo("\n📁 Files:")
    click.echo(f"  Total wiki files: {result.total_files}")
    click.echo(f"  Files with incoming links: {len(result.files_with_incoming_links)}")
    click.echo(f"  Orphaned files: {len(result.orphaned_files)}")

    click.echo("\n🔗 Links:")
    click.echo(f"  Total links: {result.total_links}")
    click.echo(f"  Valid links: {result.valid_links}")
    click.echo(f"  Broken links: {len(result.broken_links)}")

    if result.total_links > 0:
        valid_pct = (result.valid_links / result.total_links) * 100
        click.echo(f"  Link validity: {valid_pct:.1f}%")

    if result.total_files > 0:
        avg_links = result.total_links / result.total_files
        click.echo(f"  Average links per file: {avg_links:.1f}")

    click.echo("\n" + "=" * 70 + "\n")


# ===== CLI =====


@click.group()
@click.option(
    "--wiki-dir",
    type=click.Path(exists=True),
    default=str(WIKI_DIR),
    help="Wiki root directory",
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Logging directory",
)
@click.pass_context
def cli(ctx: click.Context, wiki_dir: str, log_dir: str) -> None:
    """Validate vimwiki cross-references and detect issues."""
    ctx.ensure_object(dict)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "validate_wiki")


@cli.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Check all wiki links for broken references."""
    wiki_dir: Path = ctx.obj["wiki_dir"]
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        click.echo(f"🔍 Validating wiki links in {wiki_dir}...")
        result = validate_wiki(wiki_dir, logger)
        print_validation_report(result, wiki_dir)

        # Exit with error if issues found
        if result.broken_links or result.orphaned_files:
            sys.exit(1)

    except WikiValidationError as e:
        handle_cli_error(ctx, e, "check")


@cli.command()
@click.pass_context
def orphans(ctx: click.Context) -> None:
    """Find orphaned pages (no incoming links)."""
    wiki_dir: Path = ctx.obj["wiki_dir"]
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        click.echo(f"🔍 Finding orphaned files in {wiki_dir}...")
        result = validate_wiki(wiki_dir, logger)
        print_orphans_report(result, wiki_dir)

    except WikiValidationError as e:
        handle_cli_error(ctx, e, "orphans")


@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show wiki statistics."""
    wiki_dir: Path = ctx.obj["wiki_dir"]
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        click.echo(f"📊 Calculating wiki statistics for {wiki_dir}...")
        result = validate_wiki(wiki_dir, logger)
        print_stats_report(result, wiki_dir)

    except WikiValidationError as e:
        handle_cli_error(ctx, e, "stats")


if __name__ == "__main__":
    cli(obj={})

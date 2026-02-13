#!/usr/bin/env python3
"""
wiki.py
-------
CLI commands for wiki generation, linting, sync, and publishing.

Provides the ``plm wiki`` command group for generating wiki pages
from the database, linting wiki files, syncing manuscript edits
bidirectionally, and publishing to Quartz.

Commands:
    plm wiki generate              - Generate all wiki pages
    plm wiki generate --section journal  - Journal pages only
    plm wiki generate --type people      - Specific entity type
    plm wiki lint <path>              - Lint file or directory
    plm wiki lint <path> --format json - JSON output
    plm wiki sync                     - Full manuscript sync cycle
    plm wiki sync --ingest            - Wiki → DB only
    plm wiki sync --generate          - DB → Wiki only
    plm wiki publish                  - Publish to Quartz

Usage:
    plm wiki generate
    plm wiki generate --section journal --type people
    plm wiki lint data/wiki/
    plm wiki sync
    plm wiki publish
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from dev.core.paths import DB_PATH


@click.group()
@click.pass_context
def wiki(ctx: click.Context) -> None:
    """Wiki generation and management commands."""
    pass


@wiki.command()
@click.option(
    "--section",
    type=click.Choice(["journal", "manuscript", "indexes"]),
    default=None,
    help="Generate only a specific section",
)
@click.option(
    "--type",
    "entity_type",
    type=str,
    default=None,
    help="Generate only a specific entity type (e.g., people, locations)",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Output directory (defaults to data/wiki)",
)
@click.pass_context
def generate(
    ctx: click.Context,
    section: Optional[str],
    entity_type: Optional[str],
    output_dir: Optional[str],
) -> None:
    """Generate wiki pages from database."""
    from dev.database.manager import PalimpsestDB
    from dev.wiki.exporter import WikiExporter

    logger = ctx.obj.get("logger")

    try:
        db = PalimpsestDB(DB_PATH)
        exporter = WikiExporter(
            db,
            output_dir=Path(output_dir) if output_dir else None,
            logger=logger,
        )
        exporter.generate_all(
            section=section,
            entity_type=entity_type,
        )

        click.echo("Wiki generation complete.")
        for key, value in exporter.stats.items():
            click.echo(f"  {key}: {value}")

    except Exception as e:
        handle_cli_error(ctx, e, "wiki_generate")
        raise


@wiki.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default=None,
    help="Output format (auto-detects: json for piped, text for TTY)",
)
@click.pass_context
def lint(
    ctx: click.Context,
    path: str,
    output_format: Optional[str],
) -> None:
    """Lint wiki files for structural issues and broken wikilinks."""
    import json
    import sys

    from dev.database.manager import PalimpsestDB
    from dev.wiki.validator import WikiValidator

    # Auto-detect format
    if output_format is None:
        output_format = "text" if sys.stdout.isatty() else "json"

    try:
        db = PalimpsestDB(DB_PATH)
        validator = WikiValidator(db)
        target = Path(path)

        if target.is_file():
            diagnostics = validator.validate_file(target)
            results = {str(target): [d.to_dict() for d in diagnostics]}
        else:
            raw = validator.validate_directory(target)
            results = {
                k: [d.to_dict() for d in v]
                for k, v in raw.items()
                if v  # only include files with diagnostics
            }

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            # Text output with colors
            total = sum(len(v) for v in results.values())
            for file_path, diags in sorted(results.items()):
                click.echo(click.style(file_path, bold=True))
                for d in diags:
                    color = {
                        "error": "red",
                        "warning": "yellow",
                        "info": "blue",
                    }.get(d["severity"], "white")
                    click.echo(
                        f"  {d['line']}:{d['col']} "
                        f"{click.style(d['severity'], fg=color)} "
                        f"[{d['code']}] {d['message']}"
                    )
            click.echo(f"\n{total} diagnostic(s) in {len(results)} file(s)")

    except Exception as e:
        handle_cli_error(ctx, e, "wiki_lint")
        raise


@wiki.command()
@click.option(
    "--ingest",
    "ingest_only",
    is_flag=True,
    default=False,
    help="Only ingest wiki → DB (skip regeneration)",
)
@click.option(
    "--generate",
    "generate_only",
    is_flag=True,
    default=False,
    help="Only regenerate DB → wiki (skip ingestion)",
)
@click.pass_context
def sync(
    ctx: click.Context,
    ingest_only: bool,
    generate_only: bool,
) -> None:
    """Sync manuscript wiki pages with database."""
    from dev.database.manager import PalimpsestDB
    from dev.wiki.sync import WikiSync

    logger = ctx.obj.get("logger")

    if ingest_only and generate_only:
        raise click.UsageError(
            "Cannot use --ingest and --generate together"
        )

    try:
        db = PalimpsestDB(DB_PATH)
        wiki_sync = WikiSync(db, logger=logger)
        result = wiki_sync.sync_manuscript(
            ingest_only=ingest_only,
            generate_only=generate_only,
        )

        click.echo(result.summary())
        if not result.success:
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "wiki_sync")
        raise


@wiki.command()
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Quartz content directory (defaults to quartz/content)",
)
@click.pass_context
def publish(
    ctx: click.Context,
    output_dir: Optional[str],
) -> None:
    """Publish wiki to Quartz with frontmatter injection."""
    from dev.database.manager import PalimpsestDB
    from dev.wiki.publisher import WikiPublisher

    logger = ctx.obj.get("logger")

    try:
        db = PalimpsestDB(DB_PATH)
        publisher = WikiPublisher(
            db,
            output_dir=Path(output_dir) if output_dir else None,
            logger=logger,
        )
        publisher.publish_all()

        click.echo("Publishing complete.")
        for key, value in publisher.stats.items():
            click.echo(f"  {key}: {value}")

    except Exception as e:
        handle_cli_error(ctx, e, "wiki_publish")
        raise

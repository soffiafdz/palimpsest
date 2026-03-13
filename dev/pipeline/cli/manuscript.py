#!/usr/bin/env python3
"""
manuscript.py
-------------
CLI commands for manuscript structural operations.

Provides chapter reordering commands that operate on YAML metadata
files with per-part numbering and automatic gap management.

Commands:
    - plm manuscript renumber: Move chapter to new position within its part
    - plm manuscript move: Move chapter to a different part
    - plm manuscript remove-number: Remove chapter number, close gap

Usage:
    # Preview renumber (dry-run by default)
    plm manuscript renumber "Noche de muertos" 3

    # Apply the change
    plm manuscript renumber "Noche de muertos" 3 --apply

    # Move chapter to Part 2 at position 5
    plm manuscript move "Cigarro" "Part 2" --at 5 --apply

    # Remove a chapter's number
    plm manuscript remove-number "Cigarro" --apply
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Optional

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from dev.core.paths import METADATA_DIR


@click.group()
@click.pass_context
def manuscript(ctx: click.Context) -> None:
    """Manuscript structural operations."""
    pass


@manuscript.command()
@click.argument("chapter_title")
@click.argument("new_number", type=int)
@click.option(
    "--apply",
    "execute",
    is_flag=True,
    help="Execute the renumber (default: dry-run)",
)
@click.pass_context
def renumber(
    ctx: click.Context,
    chapter_title: str,
    new_number: int,
    execute: bool,
) -> None:
    """Move a chapter to a new number within its part.

    Shifts neighboring chapters to fill gaps and make room.
    Dry-run by default — use --apply to write changes.
    """
    from dev.wiki.chapter_ops import ChapterReorder

    try:
        reorder = ChapterReorder(METADATA_DIR)
        report = reorder.renumber(
            chapter_title, new_number, dry_run=not execute
        )
        click.echo(report.summary())

        if not report.ok:
            raise SystemExit(1)
        if not execute and report.changes:
            click.echo("Run with --apply to execute.")

    except (FileNotFoundError, SystemExit):
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "manuscript_renumber")
        raise


@manuscript.command("move")
@click.argument("chapter_title")
@click.argument("part_name")
@click.option(
    "--at",
    type=int,
    default=None,
    help="Position in the new part (default: append at end)",
)
@click.option(
    "--apply",
    "execute",
    is_flag=True,
    help="Execute the move (default: dry-run)",
)
@click.pass_context
def move_part(
    ctx: click.Context,
    chapter_title: str,
    part_name: str,
    at: Optional[int],
    execute: bool,
) -> None:
    """Move a chapter to a different part.

    Closes the gap in the old part and inserts at the given
    position (or end) in the new part. Dry-run by default.
    """
    from dev.wiki.chapter_ops import ChapterReorder

    try:
        reorder = ChapterReorder(METADATA_DIR)
        report = reorder.move_part(
            chapter_title, part_name, at=at, dry_run=not execute
        )
        click.echo(report.summary())

        if not report.ok:
            raise SystemExit(1)
        if not execute and report.changes:
            click.echo("Run with --apply to execute.")

    except (FileNotFoundError, SystemExit):
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "manuscript_move")
        raise


@manuscript.command("remove-number")
@click.argument("chapter_title")
@click.option(
    "--apply",
    "execute",
    is_flag=True,
    help="Execute the removal (default: dry-run)",
)
@click.pass_context
def remove_number(
    ctx: click.Context,
    chapter_title: str,
    execute: bool,
) -> None:
    """Remove a chapter's number and close the gap in its part.

    Dry-run by default — use --apply to write changes.
    """
    from dev.wiki.chapter_ops import ChapterReorder

    try:
        reorder = ChapterReorder(METADATA_DIR)
        report = reorder.remove_number(
            chapter_title, dry_run=not execute
        )
        click.echo(report.summary())

        if not report.ok:
            raise SystemExit(1)
        if not execute and report.changes:
            click.echo("Run with --apply to execute.")

    except (FileNotFoundError, SystemExit):
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "manuscript_remove_number")
        raise


@manuscript.command("reorder-scene")
@click.argument("scene_name")
@click.argument("new_order", type=int)
@click.option(
    "--apply",
    "execute",
    is_flag=True,
    help="Execute the reorder (default: dry-run)",
)
@click.pass_context
def reorder_scene(
    ctx: click.Context,
    scene_name: str,
    new_order: int,
    execute: bool,
) -> None:
    """Move a scene to a new order within its chapter.

    Shifts neighboring scenes to fill gaps and make room.
    Dry-run by default — use --apply to write changes.
    """
    from dev.wiki.scene_ops import SceneReorder

    try:
        reorder = SceneReorder(METADATA_DIR)
        report = reorder.reorder(
            scene_name, new_order, dry_run=not execute
        )
        click.echo(report.summary())

        if not report.ok:
            raise SystemExit(1)
        if not execute and report.changes:
            click.echo("Run with --apply to execute.")

    except (FileNotFoundError, SystemExit):
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "manuscript_reorder_scene")
        raise


@manuscript.command("remove-scene-order")
@click.argument("scene_name")
@click.option(
    "--apply",
    "execute",
    is_flag=True,
    help="Execute the removal (default: dry-run)",
)
@click.pass_context
def remove_scene_order(
    ctx: click.Context,
    scene_name: str,
    execute: bool,
) -> None:
    """Remove a scene's order and close the gap in its chapter.

    Dry-run by default — use --apply to write changes.
    """
    from dev.wiki.scene_ops import SceneReorder

    try:
        reorder = SceneReorder(METADATA_DIR)
        report = reorder.remove_order(
            scene_name, dry_run=not execute
        )
        click.echo(report.summary())

        if not report.ok:
            raise SystemExit(1)
        if not execute and report.changes:
            click.echo("Run with --apply to execute.")

    except (FileNotFoundError, SystemExit):
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "manuscript_remove_scene_order")
        raise

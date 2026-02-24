#!/usr/bin/env python3
"""
prune.py
--------
Orphan entity detection and pruning commands.

Provides commands for identifying and removing database entities that have
no relationships to other entities. Orphaned entities typically occur after
removing people/locations from metadata YAML files and re-importing to database.

Key Features:
    - Detect orphaned entities across all relationship types
    - List-only mode for inspection before deletion
    - Dry-run mode to preview what would be deleted
    - Type-specific or bulk orphan removal
    - Relationship verification (entries, scenes, threads)

Commands:
    - prune-orphans: Remove orphaned entities from database

Usage:
    # List orphaned people
    metadb prune-orphans --type people --list

    # Remove orphaned people (dry run)
    metadb prune-orphans --type people --dry-run

    # Actually remove orphaned people
    metadb prune-orphans --type people

    # Remove all types of orphans
    metadb prune-orphans --type all

    # Use via pipeline CLI
    plm prune-orphans --type locations --dry-run
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import TYPE_CHECKING

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from . import get_db

if TYPE_CHECKING:
    from dev.database.manager import PalimpsestDB


@click.command("prune-orphans")
@click.option(
    "--type",
    "entity_type",
    type=click.Choice(["people", "locations", "cities", "tags", "themes", "arcs", "events", "reference_sources", "all"]),
    default="all",
    help="Type of entity to prune",
)
@click.option("--list", "list_only", is_flag=True, help="Only list orphans, don't delete")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without actually deleting")
@click.pass_context
def prune_orphans(ctx: click.Context, entity_type: str, list_only: bool, dry_run: bool) -> None:
    """
    Detect and remove orphaned entities from the database.

    Orphaned entities are database records with no relationships to other
    entities. They typically occur after removing people/locations from
    metadata YAML files and re-importing.

    The command scans for orphans and provides three modes:
    - List mode (--list): Display orphans without deleting
    - Dry-run mode (--dry-run): Show what would be deleted
    - Delete mode (default): Actually remove orphans

    Examples:
        # List orphaned people
        metadb prune-orphans --type people --list

        # Preview deletion of all orphans
        metadb prune-orphans --dry-run

        # Actually delete orphaned locations
        metadb prune-orphans --type locations

    Args:
        ctx: Click context with database configuration
        entity_type: Type of entity to check (or "all" for all types)
        list_only: If True, only list orphans without deleting
        dry_run: If True, show what would be deleted without deleting

    Notes:
        - Safe to run multiple times (idempotent)
        - Displays summary of orphans found and deleted
        - Transaction-based (all-or-nothing per entity type)
    """
    try:
        db = get_db(ctx)

        types_to_check = []
        if entity_type == "all":
            types_to_check = [
            "people", "locations", "cities", "tags", "themes", "arcs",
            "events", "reference_sources",
        ]
        else:
            types_to_check = [entity_type]

        total_orphans = 0
        total_deleted = 0

        for etype in types_to_check:
            orphans, deleted = _prune_entity_type(db, etype, list_only, dry_run)
            total_orphans += orphans
            total_deleted += deleted

        # Summary
        click.echo("\n" + "=" * 60)
        if list_only:
            click.echo(f"Total orphaned entities: {total_orphans}")
        elif dry_run:
            click.echo(f"Would delete {total_orphans} orphaned entities")
        else:
            click.echo(f"✅ Deleted {total_deleted} orphaned entities")
        click.echo("=" * 60)

    except Exception as e:
        handle_cli_error(ctx, e, "prune_orphans")


def _prune_entity_type(
    db: "PalimpsestDB", entity_type: str, list_only: bool, dry_run: bool
) -> tuple[int, int]:
    """
    Detect and optionally remove orphaned entities of a specific type.

    Scans all entities of the given type and identifies those with no
    relationships to other entities. Displays results and optionally
    deletes orphans based on mode flags.

    Args:
        db: Database manager instance
        entity_type: Type of entity to check (people, locations, etc.)
        list_only: If True, only list orphans without deleting
        dry_run: If True, show what would be deleted without deleting

    Returns:
        Tuple of (orphans_found, deleted_count)

    Notes:
        - Checks all configured relationships for the entity type
        - Displays up to 10 example orphans for inspection
        - Only deletes when both list_only and dry_run are False
    """
    from dev.database.models import (
        Person, Location, City, Tag, Theme, Arc, Event, ReferenceSource,
    )

    entity_map = {
        "people": (Person, ["entries", "scenes", "threads"]),
        "locations": (Location, ["entries", "scenes", "threads"]),
        "cities": (City, ["entries", "locations"]),
        "tags": (Tag, ["entries"]),
        "themes": (Theme, ["entries"]),
        "arcs": (Arc, ["entries", "chapters"]),
        "events": (Event, ["entries", "scenes"]),
        "reference_sources": (ReferenceSource, ["references"]),
    }

    if entity_type not in entity_map:
        return (0, 0)

    model, relationship_names = entity_map[entity_type]

    with db.session_scope() as session:
        # Find orphaned entities (no relationships)
        orphans = []
        all_entities = session.query(model).all()

        for entity in all_entities:
            has_relationships = False
            for rel_name in relationship_names:
                if hasattr(entity, rel_name):
                    rel_list = getattr(entity, rel_name)
                    if len(rel_list) > 0:
                        has_relationships = True
                        break

            if not has_relationships:
                orphans.append(entity)

        if not orphans:
            return (0, 0)

        # Display results
        click.echo(f"\n{entity_type.upper()}: {len(orphans)} orphaned")

        if list_only:
            for entity in orphans[:10]:
                name = getattr(entity, "name", str(entity.id))
                click.echo(f"  - {name}")
            if len(orphans) > 10:
                click.echo(f"  ... and {len(orphans) - 10} more")
            return (len(orphans), 0)

        if dry_run:
            for entity in orphans[:10]:
                name = getattr(entity, "name", str(entity.id))
                click.echo(f"  Would delete: {name}")
            if len(orphans) > 10:
                click.echo(f"  ... and {len(orphans) - 10} more")
            return (len(orphans), 0)

        # Actually delete
        for entity in orphans:
            session.delete(entity)
        session.commit()

        return (len(orphans), len(orphans))

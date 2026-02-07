"""
Manuscript Commands
--------------------

Commands for browsing and managing manuscript data.

Commands:
    - chapters: List all chapters
    - chapter: Show chapter details
    - characters: List all characters
    - character: Show character details with person mappings
    - parts: List parts with chapter counts
    - stats: Manuscript statistics

Usage:
    metadb manuscript chapters
    metadb manuscript chapter "The Gray Fence"
    metadb manuscript characters
    metadb manuscript character "Sofia"
    metadb manuscript parts
    metadb manuscript stats
"""
import sys
import click

from dev.core.logging_manager import handle_cli_error
from . import get_db


@click.group()
@click.pass_context
def manuscript(ctx: click.Context) -> None:
    """Browse and manage manuscript data."""
    pass


@manuscript.command("chapters")
@click.option("--status", help="Filter by status (draft, revised, final)")
@click.option("--type", "chapter_type", help="Filter by type (prose, vignette, poem)")
@click.pass_context
def list_chapters(ctx, status, chapter_type):
    """List all chapters with status and type."""
    try:
        db = get_db(ctx)

        with db.session_scope() as _:
            chapters = db.chapters.get_all()

            if status:
                chapters = [c for c in chapters if c.status.value == status]
            if chapter_type:
                chapters = [c for c in chapters if c.type.value == chapter_type]

            if not chapters:
                click.echo("No chapters found.")
                return

            click.echo(f"\nChapters ({len(chapters)}):\n")
            for ch in chapters:
                part_info = f" [{ch.part.display_name}]" if ch.part else ""
                num = f"{ch.number}. " if ch.number else "  "
                click.echo(
                    f"  {num}{ch.title}{part_info} "
                    f"({ch.type.value}, {ch.status.value})"
                )

    except Exception as e:
        handle_cli_error(e, verbose=ctx.obj.get("verbose", False))
        sys.exit(1)


@manuscript.command("chapter")
@click.argument("title")
@click.pass_context
def show_chapter(ctx, title):
    """Show details for a specific chapter."""
    try:
        db = get_db(ctx)

        with db.session_scope() as _:
            chapter = db.chapters.get(name=title)
            if not chapter:
                click.echo(f"Chapter not found: {title}", err=True)
                sys.exit(1)

            click.echo(f"\nChapter: {chapter.title}")
            if chapter.number:
                click.echo(f"  Number: {chapter.number}")
            click.echo(f"  Type: {chapter.type.value}")
            click.echo(f"  Status: {chapter.status.value}")

            if chapter.part:
                click.echo(f"  Part: {chapter.part.display_name}")

            if chapter.has_content:
                preview = chapter.content[:100] + "..." if len(chapter.content) > 100 else chapter.content
                click.echo(f"  Content: {preview}")

            if chapter.has_draft:
                click.echo(f"  Draft: {chapter.draft_path}")

            if chapter.characters:
                names = [c.name for c in chapter.characters]
                click.echo(f"  Characters: {', '.join(names)}")

            if chapter.arcs:
                arc_names = [a.name for a in chapter.arcs]
                click.echo(f"  Arcs: {', '.join(arc_names)}")

            if chapter.scenes:
                click.echo(f"\n  Scenes ({len(chapter.scenes)}):")
                for scene in chapter.scenes:
                    click.echo(
                        f"    - {scene.name} "
                        f"({scene.origin.value}, {scene.status.value})"
                    )

            if chapter.references:
                click.echo(f"\n  References ({len(chapter.references)}):")
                for ref in chapter.references:
                    click.echo(
                        f"    - {ref.source.title} ({ref.mode.value})"
                    )

    except Exception as e:
        handle_cli_error(e, verbose=ctx.obj.get("verbose", False))
        sys.exit(1)


@manuscript.command("characters")
@click.pass_context
def list_characters(ctx):
    """List all characters."""
    try:
        db = get_db(ctx)

        with db.session_scope() as _:
            characters = db.characters.get_all()

            if not characters:
                click.echo("No characters found.")
                return

            click.echo(f"\nCharacters ({len(characters)}):\n")
            for char in characters:
                role = f" ({char.role})" if char.role else ""
                narrator = " [narrator]" if char.is_narrator else ""
                chapters_count = char.chapter_count
                click.echo(
                    f"  {char.name}{role}{narrator} "
                    f"- {chapters_count} chapter(s)"
                )

    except Exception as e:
        handle_cli_error(e, verbose=ctx.obj.get("verbose", False))
        sys.exit(1)


@manuscript.command("character")
@click.argument("name")
@click.pass_context
def show_character(ctx, name):
    """Show details for a specific character."""
    try:
        db = get_db(ctx)

        with db.session_scope() as _:
            character = db.characters.get(name=name)
            if not character:
                click.echo(f"Character not found: {name}", err=True)
                sys.exit(1)

            click.echo(f"\nCharacter: {character.name}")
            if character.role:
                click.echo(f"  Role: {character.role}")
            if character.is_narrator:
                click.echo("  Narrator: yes")
            if character.description:
                click.echo(f"  Description: {character.description}")

            if character.person_mappings:
                click.echo("\n  Based on:")
                for mapping in character.person_mappings:
                    click.echo(
                        f"    - {mapping.person.display_name} "
                        f"({mapping.contribution.value})"
                    )

            if character.chapters:
                click.echo(f"\n  Chapters ({character.chapter_count}):")
                for ch in character.chapters:
                    click.echo(f"    - {ch.title}")

    except Exception as e:
        handle_cli_error(e, verbose=ctx.obj.get("verbose", False))
        sys.exit(1)


@manuscript.command("parts")
@click.pass_context
def list_parts(ctx):
    """List parts with chapter counts."""
    try:
        db = get_db(ctx)

        with db.session_scope() as _:
            parts = db.chapters.get_all_parts()

            if not parts:
                click.echo("No parts found.")
                return

            click.echo(f"\nParts ({len(parts)}):\n")
            for part in parts:
                click.echo(
                    f"  {part.display_name} "
                    f"- {part.chapter_count} chapter(s)"
                )

    except Exception as e:
        handle_cli_error(e, verbose=ctx.obj.get("verbose", False))
        sys.exit(1)


@manuscript.command("stats")
@click.pass_context
def stats(ctx):
    """Show manuscript statistics."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            analytics = db.query_analytics.get_manuscript_analytics(session)

            click.echo("\nManuscript Statistics:\n")
            for key, value in analytics.items():
                label = key.replace("_", " ").title()
                click.echo(f"  {label}: {value}")

    except Exception as e:
        handle_cli_error(e, verbose=ctx.obj.get("verbose", False))
        sys.exit(1)

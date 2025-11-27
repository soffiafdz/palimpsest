"""
SQL→Wiki Pipeline Commands
---------------------------

Commands for exporting database to wiki pages and PDFs.

Commands:
    - export-db: Export database entries to Markdown files
    - export-wiki: Export entities to vimwiki pages
    - build-pdf: Build yearly PDFs from Markdown

This is the SQL→presentation pathway.
"""
from __future__ import annotations

import click
from pathlib import Path
from typing import Optional

from dev.core.paths import (
    MD_DIR,
    PDF_DIR,
    TEX_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
    WIKI_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB
from dev.pipeline.sql2yaml import export_entry_to_markdown
from dev.pipeline import md2pdf


@click.command("export-db")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help="Output directory for Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing files")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing files")
@click.pass_context
def export_db(ctx: click.Context, output: str, force: bool, dry_run: bool) -> None:
    """
    Export database to Markdown files.

    This is the INVERSE of sync-db - reads database records and generates
    human-editable Markdown files with complete YAML frontmatter.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("📤 Exporting database to Markdown (DRY RUN - no files will be written)...")
        click.echo()

        try:
            db = PalimpsestDB(
                db_path=DB_PATH,
                alembic_dir=ALEMBIC_DIR,
                log_dir=LOG_DIR,
                backup_dir=BACKUP_DIR,
                enable_auto_backup=False,
            )

            with db.session_scope() as session:
                from dev.database.models import Entry
                entry_count = session.query(Entry).count()

                click.echo(f"Would export {entry_count} database entries")
                click.echo(f"Output directory: {output}")
                click.echo(f"Force overwrite: {force}")
                click.echo(f"Preserve body content: True")

                sample_entries = session.query(Entry).order_by(Entry.date.desc()).limit(5).all()
                click.echo("\nSample entries that would be exported:")
                for entry in sample_entries:
                    year = entry.date.year
                    filename = f"{entry.date.isoformat()}.md"
                    click.echo(f"  • {output}/{year}/{filename}")

                click.echo(f"\n  ... and {max(0, entry_count - 5)} more entries")
                click.echo("\n💡 Run without --dry-run to execute export")
                return

        except Exception as e:
            handle_cli_error(ctx, e, "export_db_dry_run")
            return

    click.echo("📤 Exporting database to Markdown...")

    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )

        with db.session_scope() as session:
            stats = db.export_manager.export_hierarchical(
                session,
                export_entry_to_markdown,
                threshold=500,
                output_dir=Path(output),
                force_overwrite=force,
                preserve_body=True,
                logger=logger,
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Total entries: {stats['total_entries']}")
        click.echo(f"  Processed: {stats['processed']}")
        if stats.get("errors", 0) > 0:
            click.echo(f"  Errors: {stats['errors']}")
        click.echo(f"  Duration: {stats['duration']:.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "export_db",
            additional_context={"output": output},
        )


@click.command("export-wiki")
@click.argument(
    "entity_type",
    type=click.Choice([
        "entries", "locations", "cities", "events", "timeline", "index", "stats", "analysis",
        "people", "themes", "tags", "poems", "references", "all"
    ]),
)
@click.option("-f", "--force", is_flag=True, help="Force regenerate all files")
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Vimwiki root directory",
)
@click.pass_context
def export_wiki(ctx: click.Context, entity_type: str, force: bool, wiki_dir: str) -> None:
    """Export database entities to vimwiki pages."""
    from dev.pipeline.sql2wiki import (
        export_index,
        export_stats,
        export_timeline,
        export_analysis_report,
        get_exporter,
    )

    logger: PalimpsestLogger = ctx.obj["logger"]
    wiki_path = Path(wiki_dir)
    journal_dir = MD_DIR

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    try:
        if entity_type == "index":
            click.echo(f"📤 Exporting wiki homepage to {wiki_path}/index.md")
            status = export_index(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Index {status}")
        elif entity_type == "stats":
            click.echo(f"📤 Exporting statistics dashboard to {wiki_path}/stats.md")
            status = export_stats(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Statistics {status}")
        elif entity_type == "timeline":
            click.echo(f"📤 Exporting timeline to {wiki_path}/timeline.md")
            status = export_timeline(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Timeline {status}")
        elif entity_type == "analysis":
            click.echo(f"📤 Exporting analysis report to {wiki_path}/analysis.md")
            status = export_analysis_report(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Analysis report {status}")
        elif entity_type == "all":
            click.echo(f"📤 Exporting all entities to {wiki_path}/")
            all_stats = []
            for entity_name in ["entries", "locations", "cities", "events", "people", "themes", "tags", "poems", "references"]:
                exporter = get_exporter(entity_name)
                stats = exporter.export_all(db, wiki_path, journal_dir, force, logger)
                all_stats.append(stats)

            export_index(db, wiki_path, journal_dir, force, logger)
            export_stats(db, wiki_path, journal_dir, force, logger)
            export_timeline(db, wiki_path, journal_dir, force, logger)
            export_analysis_report(db, wiki_path, journal_dir, force, logger)

            total_files = sum(s.files_processed for s in all_stats)
            total_created = sum(s.entries_created for s in all_stats)
            total_updated = sum(s.entries_updated for s in all_stats)
            total_skipped = sum(s.entries_skipped for s in all_stats)
            total_errors = sum(s.errors for s in all_stats)
            total_duration = sum(s.duration() for s in all_stats)

            click.echo("\n✅ All exports complete:")
            click.echo(f"  Total files: {total_files}")
            click.echo(f"  Created: {total_created}")
            click.echo(f"  Updated: {total_updated}")
            click.echo(f"  Skipped: {total_skipped}")
            if total_errors > 0:
                click.echo(f"  ⚠️  Errors: {total_errors}")
            click.echo(f"  Duration: {total_duration:.2f}s")
        else:
            exporter = get_exporter(entity_type)
            click.echo(f"📤 Exporting {exporter.config.plural} to {wiki_path}/{exporter.config.output_subdir}/")
            stats = exporter.export_all(db, wiki_path, journal_dir, force, logger)

            click.echo(f"\n✅ {exporter.config.plural.title()} export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(ctx, e, "export_wiki", {"entity_type": entity_type})


@click.command("build-pdf")
@click.argument("year")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help="Input directory with Markdown files",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(PDF_DIR),
    help="Output directory for PDFs",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing PDFs")
@click.option("--debug", is_flag=True, help="Keep temp files on error for debugging")
@click.pass_context
def build_pdf(
    ctx: click.Context,
    year: str,
    input: str,
    output: str,
    force: bool,
    debug: bool,
) -> None:
    """
    Build clean and notes PDFs for a year.

    Generates professional typeset PDF documents from Markdown entries
    using Pandoc + LaTeX. Creates two versions: clean and notes.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo(f"📚 Building PDFs for {year}...")

    try:
        stats = md2pdf.build_pdf(
            year=year,
            md_dir=Path(input),
            pdf_dir=Path(output),
            preamble=TEX_DIR / "preamble.tex",
            preamble_notes=TEX_DIR / "preamble_notes.tex",
            force_overwrite=force,
            keep_temp_on_error=debug,
            logger=logger,
        )

        click.echo("\n✅ PDF build complete:")
        click.echo(f"  Markdown entries: {stats.files_processed}")
        click.echo(f"  PDFs created: {stats.pdfs_created}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "build_pdf",
            additional_context={"year": year},
        )


__all__ = ["export_db", "export_wiki", "build_pdf"]

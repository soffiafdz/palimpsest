"""
Query & Browse Commands
------------------------

Database browsing and query commands.

Commands:
    - show: Display entry details
    - years: List all years with entry counts
    - months: List months in a year with entry counts
    - batches: Show hierarchical export batches
"""
import sys
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError
from . import get_db


@click.group()
@click.pass_context
def query(ctx: click.Context) -> None:
    """Browse and query database content."""
    pass


@query.command("show")
@click.argument("entry_date")
@click.option(
    "--full", is_flag=True, help="Show all details including references/poems"
)
@click.pass_context
def show(ctx, entry_date, full):
    """Display a single entry with optimized loading."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            if full:
                summary = db.query_analytics.get_entry_summary(session, entry_date)
                if "error" in summary:
                    click.echo(f"❌ {summary['error']}", err=True)
                    sys.exit(1)

                # Display full summary
                click.echo(f"\n📅 {summary['date']}")
                click.echo(
                    f"📊 {summary['word_count']} words, "
                    f"{summary['reading_time']:.1f} min read"
                )

                if (n_people := summary["people_count"]) > 1:
                    click.echo(f"\n👥 People ({n_people}):\n")
                    for person in summary["people"]:
                        click.echo(f"  • {person}\n")
                elif n_people == 1:
                    click.echo(f"\n👥 Person: {summary['people']}\n")

                if (n_locations := summary["locations_count"]) > 1:
                    click.echo(f"\n📍 Locations ({n_locations}):\n")
                    for loc in summary["locations"]:
                        click.echo(f"  • {loc}\n")
                elif n_locations == 1:
                    click.echo(f"\n📍 Location: {summary['locations']}\n")

                if (n_events := summary["events_count"]) > 1:
                    click.echo(f"\n🎯 Events ({n_events}):")
                    for event in summary["events"]:
                        click.echo(f"  • {event}\n")
                elif n_events == 1:
                    click.echo(f"\n🎯 Event: {summary['events']}\n")

                if summary["tags"]:
                    click.echo(f"\n🏷️  Tags: {summary['tags']}")
            else:
                entry = db.entries.get_for_display(entry_date)
                if not entry:
                    click.echo(f"❌ No entry found for {entry_date}", err=True)
                    sys.exit(1)

                # Display basic info
                click.echo(f"\n📅 {entry.date.isoformat()}")
                click.echo(
                    f"📊 {entry.word_count} words, "
                    f"{entry.reading_time:.1f} min read"
                )

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "show",
            additional_context={"entry_date": entry_date},
        )


@query.command("years")
@click.pass_context
def years(ctx):
    """List all years with entry counts."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            timeline = db.query_analytics.get_timeline_overview(session)

            click.echo("\n📅 Available Years:\n")

            for year_data in timeline["years"]:
                year = year_data["year"]
                count = year_data["total_entries"]
                click.echo(f"  {year}: {count:4d} entries")

            click.echo(f"\nTotal: {timeline['total_years']} years")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "years")


@query.command("months")
@click.argument("year", type=int)
@click.pass_context
def months(ctx, year):
    """List all months in a year with entry counts."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            year_analytics = db.query_analytics.get_year_analytics(session, year)

            if year_analytics["total_entries"] == 0:
                click.echo(f"⚠️  No entries found for {year}")
                return

            month_names = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]

            click.echo(f"\n📅 Entries in {year}:\n")

            monthly = year_analytics["monthly_breakdown"]
            total = 0

            for month in range(1, 13):
                month_key = f"{year}-{month:02d}"
                if month_key in monthly:
                    count = monthly[month_key]["entries"]
                    total += count
                    click.echo(
                        f"  {month_names[month-1]} ({month:02d}): {count:3d} entries"
                    )

            click.echo(f"\nTotal: {total} entries")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "months",
            additional_context={"year": year},
        )


@query.command("batches")
@click.option("--threshold", type=int, default=500, help="Batch threshold")
@click.pass_context
def batches(ctx, threshold):
    """Show how entries would be batched for export."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            batches = db.export_manager.get_export_batches(session, threshold)

            click.echo(f"\n📦 Hierarchical Batches (threshold={threshold}):\n")

            yearly_batches = [b for b in batches if b.is_yearly]
            monthly_batches = [b for b in batches if b.is_monthly]

            if yearly_batches:
                click.echo("Full Year Batches:")
                for batch in yearly_batches:
                    click.echo(f"  • {batch.year}: {batch.entry_count} entries")

            if monthly_batches:
                click.echo("\nMonthly Batches:")
                current_year = None
                for batch in monthly_batches:
                    if batch.year != current_year:
                        click.echo(f"\n  {batch.year}:")
                        current_year = batch.year
                    click.echo(
                        f"    • {batch.period_label}: {batch.entry_count} entries"
                    )

            total_entries = sum(b.entry_count for b in batches)
            click.echo(f"\nTotal: {len(batches)} batches, {total_entries} entries")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "batches",
            additional_context={"threshold": threshold},
        )

"""
Maintenance & Monitoring Commands
----------------------------------

Database maintenance, optimization, and monitoring commands.

Commands:
    - optimize: Optimize database (VACUUM + ANALYZE)
    - analyze: Generate detailed analytics report
    - stats: Display database statistics
    - health: Run comprehensive health check

Usage:
    plm db optimize
    plm db analyze
    plm db stats --verbose
    plm db health --fix
"""
import json
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError, HealthCheckError
from . import get_db


@click.command()
@click.confirmation_option(
    prompt="Optimization can take time and requires exclusive access. Continue?"
)
@click.pass_context
def optimize(ctx):
    """Optimize database performance (VACUUM + ANALYZE)."""
    try:
        db = get_db(ctx)
        click.echo("Optimizing database...")

        with db.session_scope() as session:
            results = db.health_monitor.optimize_database(session)

        if results:
            click.echo("\n[OK] Optimization Complete:")
            if "space_reclaimed_bytes" in results:
                reclaimed = results["space_reclaimed_bytes"]
                mb_reclaimed = reclaimed / 1024 / 1024
                click.echo(
                    f"  Space reclaimed: {reclaimed:,} bytes ({mb_reclaimed:.2f} MB)"
                )
            if "vacuum_completed" in results:
                status = "[OK]" if results["vacuum_completed"] else "[FAIL]"
                click.echo(f"  VACUUM: {status}")
            if "analyze_completed" in results:
                status = "[OK]" if results["analyze_completed"] else "[FAIL]"
                click.echo(f"  ANALYZE: {status}")
        else:
            click.echo("[WARN] No optimization performed")

    except (HealthCheckError, DatabaseError) as e:
        handle_cli_error(ctx, e, "optimize")


@click.command()
@click.pass_context
def analyze(ctx):
    """Generate detailed analytics report."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            stats = db.query_analytics.get_database_stats(session)
            manuscript = db.query_analytics.get_manuscript_analytics(session)

        click.echo("\nAnalytics Report")
        click.echo("=" * 70)

        click.echo("\nDatabase Overview:")
        click.echo(json.dumps(stats, indent=2, default=str))

        click.echo("\nManuscript Analytics:")
        click.echo(json.dumps(manuscript, indent=2, default=str))

    except DatabaseError as e:
        handle_cli_error(ctx, e, "analyze")


@click.command()
@click.option("--verbose", is_flag=True, help="Show detailed statistics")
@click.pass_context
def stats(ctx, verbose):
    """Display database statistics."""
    try:
        db = get_db(ctx)
        with db.session_scope() as session:
            stats_data = db.query_analytics.get_database_stats(session)

        click.echo("\nDatabase Statistics")
        click.echo("=" * 50)

        # Core tables
        click.echo("\nCore Tables:")
        click.echo(f"  Entries: {stats_data.get('entries', 0)}")
        click.echo(f"  People: {stats_data.get('people', 0)}")
        click.echo(f"  Cities: {stats_data.get('cities', 0)}")
        click.echo(f"  Locations: {stats_data.get('locations', 0)}")
        click.echo(f"  Events: {stats_data.get('events', 0)}")
        click.echo(f"  Tags: {stats_data.get('tags', 0)}")

        # Manuscript tables
        if verbose:
            click.echo("\nManuscript:")
            click.echo(f"  Entries: {stats_data.get('manuscript_entries', 0)}")
            click.echo(f"  People: {stats_data.get('manuscript_people', 0)}")
            click.echo(f"  Events: {stats_data.get('manuscript_events', 0)}")
            click.echo(f"  Themes: {stats_data.get('themes', 0)}")
            click.echo(f"  Arcs: {stats_data.get('arcs', 0)}")

        # Content stats
        click.echo("\nContent:")
        click.echo(f"  Total Words: {stats_data.get('total_words', 0):,}")
        if "average_words_per_entry" in stats_data:
            click.echo(
                f"  Average Words/Entry: {stats_data['average_words_per_entry']:.1f}"
            )

        # Date range
        if "date_range" in stats_data:
            dr = stats_data["date_range"]
            click.echo("\nDate Range:")
            click.echo(f"  First Entry: {dr['first_entry']}")
            click.echo(f"  Last Entry: {dr['last_entry']}")
            click.echo(f"  Total Days: {dr['total_days']}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "stats")


@click.command()
@click.option("--fix", is_flag=True, help="Attempt to fix issues")
@click.pass_context
def health(ctx, fix):
    """Run comprehensive health check."""
    try:
        db = get_db(ctx)
        with db.session_scope() as session:
            health_data = db.health_monitor.health_check(session, db.db_path)

        click.echo("\nDatabase Health Check")
        click.echo("=" * 50)
        click.echo(f"Status: {health_data['status'].upper()}")

        if health_data["issues"]:
            click.echo(f"\n[WARN] Issues Found ({len(health_data['issues'])}):")
            for issue in health_data["issues"]:
                click.echo(f"  • {issue}")
        else:
            click.echo("\n[OK] No issues found!")

        if health_data["recommendations"]:
            click.echo(f"\n[TIP] Recommendations ({len(health_data['recommendations'])}):")
            for rec in health_data["recommendations"]:
                click.echo(f"  • {rec}")

        if fix and health_data["issues"]:
            click.echo("\nAttempting fixes...")
            with db.session_scope() as session:
                results = db.health_monitor.cleanup_orphaned_records(
                    session, dry_run=False
                )
                click.echo("\nCleanup Results:")
                total_cleaned = 0
                for key, value in results.items():
                    if isinstance(value, int) and value > 0:
                        click.echo(f"  • {key}: {value}")
                        total_cleaned += value

                if total_cleaned == 0:
                    click.echo("  No orphaned records found")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "health",
            additional_context={"fix": fix},
        )

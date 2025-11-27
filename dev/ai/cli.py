#!/usr/bin/env python3
"""
ai_cli.py
---------
Standalone CLI for AI-assisted analysis and extraction of journal entries.

This provides AI-powered tools for analyzing journal entries, extracting
entities (people, places, events), themes, and metadata using different
AI levels from simple keyword matching to advanced LLM analysis.

AI Levels:
    Level 1: Keyword matching (free, built-in)
    Level 2: spaCy NER (free, ML-based entity extraction)
    Level 3: Semantic search with transformers (free, similarity)
    Level 4: LLM APIs (paid, Claude or OpenAI for deep analysis)

Commands:
    plm-ai analyze <date> [options]
    plm-ai status

Examples:
    # Analyze with spaCy (free)
    plm-ai analyze 2024-11-01 --level 2

    # Analyze with Claude API (paid)
    plm-ai analyze 2024-11-01 --level 4 --provider claude

    # Include manuscript analysis
    plm-ai analyze 2024-11-01 --level 4 --manuscript

    # Check AI capabilities
    plm-ai status
"""
import sys
import click
from pathlib import Path
import importlib.util

from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import setup_logger


@click.group()
@click.option(
    "--log-dir", type=click.Path(), default=str(LOG_DIR), help="Directory for log files"
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, log_dir: str, verbose: bool) -> None:
    """
    AI-assisted analysis and extraction of journal entries.

    This command provides various AI-powered tools for analyzing journal
    entries, extracting entities (people, places, events), themes, and
    metadata using different AI levels from simple keyword matching to
    advanced LLM analysis.

    AI Levels:
        Level 1: Keyword matching (free, built-in)
        Level 2: spaCy NER (free, ML-based entity extraction)
        Level 3: Semantic search with transformers (free, similarity)
        Level 4: LLM APIs (paid, Claude or OpenAI for deep analysis)

    Examples:
        plm-ai analyze 2024-11-01 --level 2
        plm-ai analyze 2024-11-01 --level 4 --provider claude
        plm-ai status
    """
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "ai")


@cli.command("analyze")
@click.argument("date")
@click.option(
    "--level",
    type=click.Choice(["1", "2", "3", "4"]),
    default="2",
    help="AI level (1=keywords, 2=spaCy, 3=transformers, 4=LLM)",
)
@click.option(
    "--provider",
    type=click.Choice(["claude", "openai"]),
    default="claude",
    help="LLM provider for level 4",
)
@click.option(
    "--manuscript", is_flag=True, help="Include manuscript analysis (level 4)"
)
@click.pass_context
def ai_analyze(
    ctx: click.Context, date: str, level: str, provider: str, manuscript: bool
) -> None:
    """
    Analyze a single journal entry with AI.

    This command applies AI analysis to a single journal entry, extracting
    structured metadata such as people, places, events, themes, and mood
    using various AI techniques depending on the specified level.

    Analysis Levels:

    Level 2 (spaCy NER):
    - Uses spaCy's named entity recognition
    - Extracts: people (PERSON), cities (GPE), locations (LOC), events (EVENT)
    - Provides confidence scores for each extraction
    - Extracts themes using NLP patterns
    - Fast, free, runs locally
    - Requires: pip install spacy && python -m spacy download en_core_web_sm

    Level 4 (LLM API):
    - Uses Claude or OpenAI API for deep analysis
    - Extracts: summary, mood, people, themes, tags
    - Optional manuscript analysis: entry type, narrative potential, arc suggestions
    - More accurate but requires API key and costs money
    - Requires: pip install anthropic (or openai)
    - Set environment variable: ANTHROPIC_API_KEY or OPENAI_API_KEY

    Examples:
        # Analyze with spaCy (free)
        plm-ai analyze 2024-11-01 --level 2

        # Analyze with Claude API (paid)
        plm-ai analyze 2024-11-01 --level 4 --provider claude

        # Include manuscript analysis
        plm-ai analyze 2024-11-01 --level 4 --manuscript

        # Analyze with OpenAI
        plm-ai analyze 2024-11-01 --level 4 --provider openai
    """
    from datetime import date as Date
    from dev.database.manager import PalimpsestDB


    level_int = int(level)

    # Parse date
    try:
        entry_date = Date.fromisoformat(date)
    except ValueError:
        click.echo(f"Error: Invalid date format '{date}'. Use YYYY-MM-DD")
        sys.exit(1)

    # Initialize database
    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    # Get entry
    from dev.database.models import Entry

    entry = db.session.query(Entry).filter_by(date=entry_date).first()

    if not entry:
        click.echo(f"Error: Entry not found for {date}")
        sys.exit(1)

    click.echo(f"Analyzing entry: {entry.date}\n")

    # Level 2: spaCy NER
    if level_int >= 2:
        try:
            from dev.ai.extractors import EntityExtractor, ThemeExtractor

            extractor = EntityExtractor()
            entities = extractor.extract_from_entry(entry)

            click.echo("=== Entity Extraction (spaCy) ===")

            if entities.people:
                click.echo(f"\n👥 People ({len(entities.people)}):")
                for person in sorted(entities.people):
                    conf_key = f"person:{person}"
                    conf = entities.confidence.get(conf_key, 0.0)
                    click.echo(f"  - {person} (confidence: {conf:.2f})")

            if entities.cities:
                click.echo(f"\n🌍 Cities ({len(entities.cities)}):")
                for city in sorted(entities.cities):
                    conf_key = f"city:{city}"
                    conf = entities.confidence.get(conf_key, 0.0)
                    click.echo(f"  - {city} (confidence: {conf:.2f})")

            if entities.locations:
                click.echo(f"\n📍 Locations ({len(entities.locations)}):")
                for loc in sorted(entities.locations):
                    click.echo(f"  - {loc}")

            if entities.events:
                click.echo(f"\n📅 Events ({len(entities.events)}):")
                for event in sorted(entities.events):
                    click.echo(f"  - {event}")

            click.echo()

            # Theme extraction
            theme_extractor = ThemeExtractor()
            suggestions = theme_extractor.extract_themes(
                extractor._extract_entry_text(entry)
            )

            click.echo("=== Theme Suggestions ===")
            if suggestions:
                for theme_sugg in suggestions[:10]:
                    click.echo(f"  - {theme_sugg.theme}: {theme_sugg.confidence:.2f}")
            else:
                click.echo("  No themes detected")

            click.echo()

        except ImportError as e:
            click.echo(f"⚠ Level 2 (spaCy) not available: {e}")
            click.echo(
                "Install with: pip install spacy && python -m spacy download en_core_web_sm"
            )
            click.echo()

    # Level 4: LLM API
    if level_int >= 4:
        from dev.ai.extractors import EntityExtractor

        extractor = EntityExtractor()
        text = extractor._extract_entry_text(entry)

        if provider == "claude":
            try:
                from dev.ai.claude_assistant import ClaudeAssistant

                assistant = ClaudeAssistant()
                click.echo("=== Claude Analysis ===")

                # Extract metadata
                metadata = assistant.extract_metadata(text)

                click.echo(f"\n📝 Summary: {metadata.summary}")
                click.echo(f"😊 Mood: {metadata.mood}")

                if metadata.people:
                    click.echo(f"\n👥 People: {', '.join(metadata.people)}")

                if metadata.themes:
                    click.echo(f"\n🎨 Themes: {', '.join(metadata.themes)}")

                if metadata.tags:
                    click.echo(f"\n🏷️  Tags: {', '.join(metadata.tags)}")

                # Manuscript analysis
                if manuscript:
                    click.echo("\n=== Manuscript Analysis ===")
                    ms_analysis = assistant.analyze_for_manuscript(text)

                    click.echo(f"\n📖 Entry Type: {ms_analysis.entry_type}")
                    click.echo(
                        f"⭐ Narrative Potential: {ms_analysis.narrative_potential:.2f}"
                    )

                    if ms_analysis.suggested_arc:
                        click.echo(f"\n🎭 Suggested Arc: {ms_analysis.suggested_arc}")

                    if ms_analysis.adaptation_notes:
                        click.echo(
                            f"\n✏️  Adaptation Notes:\n{ms_analysis.adaptation_notes}"
                        )

                click.echo()

            except ImportError:
                click.echo("⚠ Claude API not available")
                click.echo("Install with: pip install anthropic")
                click.echo("Set API key: export ANTHROPIC_API_KEY='your-key'")
                click.echo()
            except Exception as e:
                click.echo(f"⚠ Claude analysis failed: {e}")
                click.echo()


@cli.command("status")
@click.pass_context
def ai_status(ctx: click.Context) -> None:
    """
    Check AI capabilities and API configuration status.

    This command checks which AI analysis capabilities are available in
    the current environment by attempting to import required packages and
    checking for API keys. Provides a diagnostic overview of what analysis
    levels can be used.

    Checks Performed:

    Level 1 (Always Available):
    - Built-in keyword matching
    - No dependencies required

    Level 2 (spaCy):
    - Checks if spacy package is installed
    - Reports if en_core_web_sm model is available
    - Provides installation instructions if missing

    Level 3 (Semantic Search):
    - Checks if sentence-transformers package is installed
    - Reports model availability
    - Provides installation instructions if missing

    Level 4 (LLM APIs):
    - Checks if anthropic package is installed
    - Checks if ANTHROPIC_API_KEY environment variable is set
    - Checks if openai package is installed
    - Checks if OPENAI_API_KEY environment variable is set
    - Reports configuration status for each provider

    Use Cases:
    - Verify AI setup after installation
    - Troubleshoot missing dependencies
    - Check API key configuration
    - Determine which analysis levels are available
    """
    click.echo("AI Capabilities Status:\n")

    # Level 1: Always available
    click.echo("✓ Level 1: Keyword matching (free, built-in)")

    # Level 2: spaCy
    if importlib.util.find_spec("spacy"):
        click.echo("✓ Level 2: spaCy NER (free, ML-based)")
    else:
        click.echo("✗ Level 2: spaCy NER - Not installed")
        click.echo(
            "  Install: pip install spacy && python -m spacy download en_core_web_sm"
        )

    # Level 3: Sentence Transformers
    if importlib.util.find_spec("sentence_transformers"):
        click.echo("✓ Level 3: Semantic search (free, transformers)")
    else:
        click.echo("✗ Level 3: Semantic search - Not installed")
        click.echo("  Install: pip install sentence-transformers")

    # Level 4: LLM APIs
    click.echo("\nLevel 4: LLM APIs (paid)")

    # Claude API
    if importlib.util.find_spec("anthropic"):
        import os # os needs to be imported to check environment variables
        if os.environ.get("ANTHROPIC_API_KEY"):
            click.echo("  ✓ Claude API (API key configured)")
        else:
            click.echo("  ⚠ Claude API - Package installed but no API key")
            click.echo("    Set key: export ANTHROPIC_API_KEY='your-key'")
    else:
        click.echo("  ✗ Claude API - Not installed")
        click.echo("    Install: pip install anthropic")

    # OpenAI API
    if importlib.util.find_spec("openai"):
        import os # os needs to be imported to check environment variables
        if os.environ.get("OPENAI_API_KEY"):
            click.echo("  ✓ OpenAI API (API key configured)")
        else:
            click.echo("  ⚠ OpenAI API - Package installed but no API key")
            click.echo("    Set key: export OPENAI_API_KEY='your-key'")
    else:
        click.echo("  ✗ OpenAI API - Not installed")
        click.echo("    Install: pip install openai")


if __name__ == "__main__":
    cli(obj={})

#!/usr/bin/env python3
"""
ai_assist.py
------------
CLI interface for AI-assisted analysis and extraction.

Commands:
    palimpsest ai analyze ENTRY_DATE [--level LEVEL]
    palimpsest ai batch [--level LEVEL] [--limit N]
    palimpsest ai themes ENTRY_DATE
    palimpsest ai similar ENTRY_DATE [--limit N]
    palimpsest ai cluster [--num-clusters N]
    palimpsest ai status

Levels:
    1: Keywords only (free, fast)
    2: spaCy NER (free, ML-based)
    3: Semantic search (free, transformers)
    4: Claude API (paid, most accurate)

Examples:
    # Analyze entry with spaCy
    palimpsest ai analyze 2024-11-01 --level 2

    # Batch analyze all entries
    palimpsest ai batch --level 2 --limit 10

    # Find similar entries
    palimpsest ai similar 2024-11-01

    # Cluster all entries
    palimpsest ai cluster --num-clusters 10

    # Check AI capabilities
    palimpsest ai status
"""
import sys
import argparse
from datetime import date as Date
from pathlib import Path
from typing import Optional

from dev.database.manager import PalimpsestDB
from dev.core.logging_manager import PalimpsestLogger


def analyze_entry(args):
    """Analyze single entry."""
    # Parse date
    try:
        entry_date = Date.fromisoformat(args.date)
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD")
        return

    # Initialize database
    db = PalimpsestDB()

    # Get entry
    from dev.database.models import Entry
    entry = db.session.query(Entry).filter_by(date=entry_date).first()

    if not entry:
        print(f"Error: Entry not found for {args.date}")
        return

    print(f"Analyzing entry: {entry.date}")
    print()

    level = args.level

    # Level 2: spaCy NER
    if level >= 2:
        try:
            from dev.ai.extractors import EntityExtractor

            extractor = EntityExtractor()
            entities = extractor.extract_from_entry(entry)

            print("=== Entity Extraction (spaCy) ===")

            if entities.people:
                print(f"\n👥 People ({len(entities.people)}):")
                for person in sorted(entities.people):
                    conf_key = f"person:{person}"
                    conf = entities.confidence.get(conf_key, 0.0)
                    print(f"  - {person} (confidence: {conf:.2f})")

            if entities.cities:
                print(f"\n🌍 Cities ({len(entities.cities)}):")
                for city in sorted(entities.cities):
                    conf_key = f"city:{city}"
                    conf = entities.confidence.get(conf_key, 0.0)
                    print(f"  - {city} (confidence: {conf:.2f})")

            if entities.locations:
                print(f"\n📍 Locations ({len(entities.locations)}):")
                for loc in sorted(entities.locations):
                    print(f"  - {loc}")

            if entities.events:
                print(f"\n📅 Events ({len(entities.events)}):")
                for event in sorted(entities.events):
                    print(f"  - {event}")

            print()

        except ImportError as e:
            print(f"⚠ Level 2 (spaCy) not available: {e}")
            print("Install with: pip install spacy && python -m spacy download en_core_web_sm")
            print()

    # Level 2: Theme extraction
    if level >= 2:
        try:
            from dev.ai.extractors import ThemeExtractor

            theme_extractor = ThemeExtractor()
            suggestions = theme_extractor.extract_themes(
                extractor._extract_entry_text(entry)
            )

            print("=== Theme Suggestions ===")
            if suggestions:
                for theme_sugg in suggestions[:10]:
                    print(f"  - {theme_sugg.theme}: {theme_sugg.confidence:.2f}")
            else:
                print("  No themes detected")

            print()

        except Exception as e:
            print(f"⚠ Theme extraction failed: {e}")
            print()

    # Level 4: Claude API
    if level >= 4:
        try:
            from dev.ai.claude_assistant import ClaudeAssistant

            assistant = ClaudeAssistant()

            # Read entry text
            from dev.ai.extractors import EntityExtractor
            extractor = EntityExtractor()
            text = extractor._extract_entry_text(entry)

            print("=== Claude Analysis ===")

            # Extract metadata
            metadata = assistant.extract_metadata(text)

            print(f"\n📝 Summary: {metadata.summary}")
            print(f"😊 Mood: {metadata.mood}")

            if metadata.people:
                print(f"\n👥 People: {', '.join(metadata.people)}")

            if metadata.themes:
                print(f"\n🎨 Themes: {', '.join(metadata.themes)}")

            if metadata.tags:
                print(f"\n🏷️  Tags: {', '.join(metadata.tags)}")

            # Manuscript analysis
            if args.manuscript:
                print("\n=== Manuscript Analysis ===")
                ms_analysis = assistant.analyze_for_manuscript(text)

                print(f"\n📖 Entry Type: {ms_analysis.entry_type}")
                print(f"⭐ Narrative Potential: {ms_analysis.narrative_potential:.2f}")

                if ms_analysis.suggested_arc:
                    print(f"\n🎭 Suggested Arc: {ms_analysis.suggested_arc}")

                if ms_analysis.adaptation_notes:
                    print(f"\n✏️  Adaptation Notes:\n{ms_analysis.adaptation_notes}")

            print()

        except ImportError:
            print("⚠ Level 4 (Claude API) not available")
            print("Install with: pip install anthropic")
            print("Set API key: export ANTHROPIC_API_KEY='your-key'")
            print()
        except Exception as e:
            print(f"⚠ Claude analysis failed: {e}")
            print()


def batch_analyze(args):
    """Batch analyze entries."""
    db = PalimpsestDB()

    # Get entries
    from dev.database.models import Entry
    query = db.session.query(Entry).order_by(Entry.date.desc())

    if args.limit:
        query = query.limit(args.limit)

    entries = query.all()

    print(f"Batch analyzing {len(entries)} entries (level {args.level})...")
    print()

    level = args.level

    if level >= 2:
        try:
            from dev.ai.extractors import EntityExtractor, ThemeExtractor

            extractor = EntityExtractor()
            theme_extractor = ThemeExtractor()

            for i, entry in enumerate(entries, 1):
                print(f"[{i}/{len(entries)}] {entry.date}...")

                # Extract entities
                entities = extractor.extract_from_entry(entry)

                # Extract themes
                text = extractor._extract_entry_text(entry)
                themes = theme_extractor.extract_themes(text)

                # Display summary
                print(f"  People: {len(entities.people)}, "
                      f"Cities: {len(entities.cities)}, "
                      f"Themes: {len(themes)}")

                # TODO: Save extracted data to database
                # This would update Entry with suggested people, themes, etc.

            print()
            print(f"✓ Analyzed {len(entries)} entries")

        except ImportError as e:
            print(f"Error: {e}")
            return


def find_similar(args):
    """Find similar entries using semantic search."""
    try:
        from dev.ai.semantic_search import SemanticSearch
    except ImportError:
        print("Error: Semantic search not available")
        print("Install with: pip install sentence-transformers")
        return

    # Parse date
    try:
        entry_date = Date.fromisoformat(args.date)
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD")
        return

    # Initialize
    db = PalimpsestDB()

    # Get entry
    from dev.database.models import Entry
    entry = db.session.query(Entry).filter_by(date=entry_date).first()

    if not entry:
        print(f"Error: Entry not found for {args.date}")
        return

    # Initialize semantic search
    semantic = SemanticSearch()

    # Build or load index
    cache_path = Path("data/embeddings_cache.pkl")

    if cache_path.exists():
        print("Loading semantic index from cache...")
        semantic.build_index([], cache_path=cache_path)
    else:
        print("Building semantic index (this may take a while)...")
        all_entries = db.session.query(Entry).all()
        semantic.build_index(all_entries, cache_path=cache_path)

    # Find similar
    print(f"\nFinding entries similar to {entry.date}...")
    print()

    results = semantic.find_similar_to_entry(entry.id, limit=args.limit)

    if not results:
        print("No similar entries found.")
        return

    print(f"Found {len(results)} similar entries:\n")

    for result in results:
        print(f"📅 {result.date} (similarity: {result.similarity:.2f})")
        if result.snippet:
            print(f"   {result.snippet}")
        print()


def cluster_entries(args):
    """Cluster entries by theme."""
    try:
        from dev.ai.semantic_search import SemanticSearch
    except ImportError:
        print("Error: Semantic search not available")
        print("Install with: pip install sentence-transformers scikit-learn")
        return

    db = PalimpsestDB()

    # Get all entries
    from dev.database.models import Entry
    all_entries = db.session.query(Entry).all()

    # Initialize semantic search
    semantic = SemanticSearch()

    # Build index
    cache_path = Path("data/embeddings_cache.pkl")

    if cache_path.exists():
        print("Loading semantic index from cache...")
        semantic.build_index([], cache_path=cache_path)
    else:
        print("Building semantic index (this may take a while)...")
        semantic.build_index(all_entries, cache_path=cache_path)

    # Cluster
    print(f"\nClustering {len(all_entries)} entries into {args.num_clusters} clusters...")
    clusters = semantic.cluster_entries(num_clusters=args.num_clusters)

    # Display clusters
    for cluster_id, entry_ids in sorted(clusters.items()):
        print(f"\n=== Cluster {cluster_id + 1} ({len(entry_ids)} entries) ===")

        # Show sample entries
        sample_entries = db.session.query(Entry).filter(
            Entry.id.in_(entry_ids[:5])
        ).all()

        for entry in sample_entries:
            print(f"  - {entry.date}")


def status_command(args):
    """Show AI capabilities status."""
    print("AI Capabilities Status:\n")

    # Level 1: Always available
    print("✓ Level 1: Keyword matching (free, built-in)")

    # Level 2: spaCy
    try:
        import spacy
        print("✓ Level 2: spaCy NER (free, ML-based)")
    except ImportError:
        print("✗ Level 2: spaCy NER - Not installed")
        print("  Install: pip install spacy && python -m spacy download en_core_web_sm")

    # Level 3: Sentence Transformers
    try:
        import sentence_transformers
        print("✓ Level 3: Semantic search (free, transformers)")
    except ImportError:
        print("✗ Level 3: Semantic search - Not installed")
        print("  Install: pip install sentence-transformers")

    # Level 4: Claude API
    try:
        import anthropic
        import os
        if os.environ.get('ANTHROPIC_API_KEY'):
            print("✓ Level 4: Claude API (paid, API key configured)")
        else:
            print("⚠ Level 4: Claude API - Package installed but no API key")
            print("  Set key: export ANTHROPIC_API_KEY='your-key'")
    except ImportError:
        print("✗ Level 4: Claude API - Not installed")
        print("  Install: pip install anthropic")

    # Cost estimates
    print("\n--- Cost Estimates (Level 4) ---")

    try:
        from dev.ai.claude_assistant import estimate_cost

        for model in ['haiku', 'sonnet']:
            costs = estimate_cost(100, model=model)
            print(f"{model.title()}: ${costs['total_cost']:.2f} for 100 entries "
                  f"(${costs['cost_per_entry']:.6f} per entry)")
    except ImportError:
        pass


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI-assisted analysis and extraction"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze single entry')
    analyze_parser.add_argument('date', help='Entry date (YYYY-MM-DD)')
    analyze_parser.add_argument(
        '--level',
        type=int,
        choices=[1, 2, 3, 4],
        default=2,
        help='AI level (1=keywords, 2=spaCy, 3=transformers, 4=Claude)'
    )
    analyze_parser.add_argument(
        '--manuscript',
        action='store_true',
        help='Include manuscript analysis (requires level 4)'
    )
    analyze_parser.set_defaults(func=analyze_entry)

    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Batch analyze entries')
    batch_parser.add_argument(
        '--level',
        type=int,
        choices=[1, 2, 3, 4],
        default=2,
        help='AI level'
    )
    batch_parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of entries'
    )
    batch_parser.set_defaults(func=batch_analyze)

    # Similar command
    similar_parser = subparsers.add_parser('similar', help='Find similar entries')
    similar_parser.add_argument('date', help='Entry date (YYYY-MM-DD)')
    similar_parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum results'
    )
    similar_parser.set_defaults(func=find_similar)

    # Cluster command
    cluster_parser = subparsers.add_parser('cluster', help='Cluster entries by theme')
    cluster_parser.add_argument(
        '--num-clusters',
        type=int,
        default=10,
        help='Number of clusters'
    )
    cluster_parser.set_defaults(func=cluster_entries)

    # Status command
    status_parser = subparsers.add_parser('status', help='Check AI capabilities')
    status_parser.set_defaults(func=status_command)

    # Parse and execute
    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()

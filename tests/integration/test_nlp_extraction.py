#!/usr/bin/env python3
"""
Integration tests for AI extraction functionality.

Tests:
- Entity extraction with spaCy (Level 2)
- Theme extraction (Level 2-3)
- Semantic search (Level 3)
- Claude API integration (Level 4)

Note: Some tests require optional dependencies and will be skipped if not installed.
"""
import pytest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry


# Check dependencies
import importlib.util
import os

SPACY_AVAILABLE = importlib.util.find_spec("spacy") is not None
TRANSFORMERS_AVAILABLE = importlib.util.find_spec("sentence_transformers") is not None
CLAUDE_AVAILABLE = importlib.util.find_spec("anthropic") is not None and bool(os.environ.get('ANTHROPIC_API_KEY'))


@pytest.fixture
def test_db():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
class TestEntityExtraction:
    """Test spaCy-based entity extraction (Level 2)."""

    def test_extract_people(self):
        """Test extracting person names."""
        from dev.nlp.extractors import EntityExtractor

        text = """
        Today I met with Alice Johnson for coffee.
        We discussed her upcoming trip with Bob Smith.
        """

        extractor = EntityExtractor()
        entities = extractor.extract_from_text(text)

        # Should detect Alice Johnson and Bob Smith
        assert len(entities.people) >= 1
        # spaCy might detect "Alice Johnson" or just "Alice"

    def test_extract_locations(self):
        """Test extracting locations."""
        from dev.nlp.extractors import EntityExtractor

        text = """
        I visited Montreal last weekend.
        We went to Parc Jarry and then to New York.
        """

        extractor = EntityExtractor()
        entities = extractor.extract_from_text(text)

        # Should detect cities
        assert len(entities.cities) >= 1

    def test_extract_from_entry(self, test_db, tmp_path):
        """Test extracting entities from Entry object."""
        from dev.nlp.extractors import EntityExtractor

        # Create entry file
        file_path = tmp_path / "entry.md"
        file_path.write_text("""---
title: Test
---

Today I had therapy with Dr. Sarah Miller in Montreal.
We discussed my anxiety and relationship with Alice.
""")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
            epigraph="A quote from Shakespeare",
        )

        test_db.add(entry)
        test_db.commit()

        # Extract
        extractor = EntityExtractor()
        entities = extractor.extract_from_entry(entry)

        # Should detect people and cities
        assert len(entities.people) >= 1 or len(entities.cities) >= 1

    def test_confidence_scores(self):
        """Test that confidence scores are assigned."""
        from dev.nlp.extractors import EntityExtractor

        text = """
        Alice is a very important person in my life.
        Alice helped me through difficult times.
        We've known each other for years.
        """

        extractor = EntityExtractor()
        entities = extractor.extract_from_text(text)

        # Should have confidence scores
        assert len(entities.confidence) > 0

        # Repeated mentions should have higher confidence
        # (This is heuristic-based in our implementation)


@pytest.mark.skipif(not TRANSFORMERS_AVAILABLE, reason="Transformers not installed")
class TestThemeExtraction:
    """Test semantic theme extraction (Level 3)."""

    def test_semantic_theme_extraction(self):
        """Test semantic theme extraction with transformers."""
        from dev.nlp.extractors import ThemeExtractor

        text = """
        I keep questioning my sense of self.
        Worrying about connections with others.
        Feeling like I'm not progressing.
        """

        extractor = ThemeExtractor()
        suggestions = extractor.extract_themes(text)

        # Should detect themes even without exact keywords
        assert len(suggestions) > 0

        # Should have confidence scores
        for suggestion in suggestions:
            assert 0.0 <= suggestion.confidence <= 1.0

    def test_theme_extraction_with_keywords(self):
        """Test that semantic extraction works even with direct keyword mentions."""
        from dev.nlp.extractors import ThemeExtractor

        text = """
        I've been feeling a lot of anxiety lately about my identity.
        Who am I really? This question keeps me up at night.
        I'm worried about my relationships and whether I'm growing as a person.
        """

        extractor = ThemeExtractor()
        suggestions = extractor.extract_themes(text)

        # Should detect anxiety, identity, relationships, growth
        themes = [s.theme for s in suggestions]
        assert len(themes) > 0
        # At least some of the expected themes should be detected
        expected_themes = {'anxiety', 'identity', 'relationships', 'growth'}
        detected = set(themes) & expected_themes
        assert len(detected) > 0

    def test_min_confidence_threshold(self):
        """Test minimum confidence filtering."""
        from dev.nlp.extractors import ThemeExtractor

        text = "Just a normal day, nothing special happened."

        extractor = ThemeExtractor()

        # Low threshold: should get some matches
        suggestions_low = extractor.extract_themes(text, min_confidence=0.1)

        # High threshold: should get fewer matches
        suggestions_high = extractor.extract_themes(text, min_confidence=0.8)

        assert len(suggestions_low) >= len(suggestions_high)


@pytest.mark.skipif(not TRANSFORMERS_AVAILABLE, reason="Transformers not installed")
class TestSemanticSearch:
    """Test semantic search with sentence transformers (Level 3)."""

    def test_build_index(self, test_db, tmp_path):
        """Test building semantic search index."""
        from dev.nlp.semantic_search import SemanticSearch

        # Create entries
        file1 = tmp_path / "entry1.md"
        file1.write_text("I'm feeling anxious about work")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Had a great time at the beach")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        test_db.add_all([entry1, entry2])
        test_db.commit()

        # Build index
        semantic = SemanticSearch()
        semantic.build_index([entry1, entry2])

        assert semantic.embeddings is not None
        assert len(semantic.entry_ids) == 2

    def test_find_similar(self, test_db, tmp_path):
        """Test finding semantically similar entries."""
        from dev.nlp.semantic_search import SemanticSearch

        # Create entries with related content
        file1 = tmp_path / "entry1.md"
        file1.write_text("I'm worried about my job performance")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Feeling stressed about work deadlines")

        file3 = tmp_path / "entry3.md"
        file3.write_text("Had a wonderful vacation in Paris")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        entry3 = Entry(
            date=date(2024, 11, 3),
            file_path=str(file3),
            word_count=100,
            reading_time=0.5,
        )

        test_db.add_all([entry1, entry2, entry3])
        test_db.commit()

        # Build index
        semantic = SemanticSearch()
        semantic.build_index([entry1, entry2, entry3])

        # Search for work-related anxiety
        results = semantic.find_similar("anxious about my career", limit=2)

        # Should prioritize entry1 and entry2 over entry3
        assert len(results) >= 1
        assert results[0].entry_id in [entry1.id, entry2.id]

    def test_find_similar_to_entry(self, test_db, tmp_path):
        """Test finding entries similar to a specific entry."""
        from dev.nlp.semantic_search import SemanticSearch

        # Create entries
        file1 = tmp_path / "entry1.md"
        file1.write_text("Therapy session about anxiety")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Discussed stress management techniques")

        file3 = tmp_path / "entry3.md"
        file3.write_text("Beautiful sunset at the beach")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        entry3 = Entry(
            date=date(2024, 11, 3),
            file_path=str(file3),
            word_count=100,
            reading_time=0.5,
        )

        test_db.add_all([entry1, entry2, entry3])
        test_db.commit()

        # Build index
        semantic = SemanticSearch()
        semantic.build_index([entry1, entry2, entry3])

        # Find similar to entry1
        results = semantic.find_similar_to_entry(entry1.id, limit=2)

        # Should find entry2 as more similar than entry3
        assert len(results) >= 1
        assert results[0].entry_id == entry2.id

    def test_cache_embeddings(self, test_db, tmp_path):
        """Test caching and loading embeddings."""
        from dev.nlp.semantic_search import SemanticSearch

        # Create entry
        file1 = tmp_path / "entry1.md"
        file1.write_text("Test content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        test_db.add(entry1)
        test_db.commit()

        cache_path = tmp_path / "embeddings.pkl"

        # Build and save
        semantic1 = SemanticSearch()
        semantic1.build_index([entry1], cache_path=cache_path)

        assert cache_path.exists()

        # Load from cache
        semantic2 = SemanticSearch()
        semantic2.build_index([], cache_path=cache_path)

        assert semantic2.embeddings is not None
        assert len(semantic2.entry_ids) == 1


@pytest.mark.skipif(not CLAUDE_AVAILABLE, reason="Claude API not configured")
class TestClaudeIntegration:
    """Test Claude API integration (Level 4)."""

    def test_extract_metadata(self):
        """Test extracting metadata with Claude."""
        from dev.nlp.claude_assistant import ClaudeAssistant

        text = """
        Today I had therapy with Dr. Sarah in Montreal.
        We discussed my anxiety about my relationship with Alice.
        I'm worried about losing connection as we both grow.
        """

        assistant = ClaudeAssistant()
        metadata = assistant.extract_metadata(text)

        # Should detect entities
        assert len(metadata.people) > 0 or len(metadata.cities) > 0

        # Should have summary
        assert len(metadata.summary) > 0

        # Should detect themes
        assert len(metadata.themes) > 0

    def test_analyze_for_manuscript(self):
        """Test manuscript analysis with Claude."""
        from dev.nlp.claude_assistant import ClaudeAssistant

        text = """
        She sat at the café, watching rain trace patterns on the window.
        Every drop seemed to carry a memory, a moment she'd tried to forget.
        The barista called her name, but she didn't move.
        Not yet. Not until she'd decided whether to answer the text.
        """

        assistant = ClaudeAssistant()
        analysis = assistant.analyze_for_manuscript(text)

        # Should assess narrative potential
        assert 0.0 <= analysis.narrative_potential <= 1.0

        # Should suggest entry type
        assert len(analysis.entry_type) > 0

    def test_suggest_themes(self):
        """Test theme suggestions with Claude."""
        from dev.nlp.claude_assistant import ClaudeAssistant

        text = """
        I keep questioning who I am and what I want.
        My relationships feel strained, and I'm worried
        about whether I'm growing or just staying stuck.
        """

        assistant = ClaudeAssistant()
        themes = assistant.suggest_themes(text)

        # Should return list of themes
        assert isinstance(themes, list)
        assert len(themes) > 0


class TestDependencyChecks:
    """Test dependency checking utilities."""

    def test_check_extractor_dependencies(self):
        """Test checking extractor dependencies."""
        from dev.nlp.extractors import check_dependencies

        deps = check_dependencies()

        assert 'spacy' in deps
        assert 'sentence_transformers' in deps
        assert isinstance(deps['spacy'], bool)
        assert isinstance(deps['sentence_transformers'], bool)

    def test_check_semantic_dependencies(self):
        """Test checking semantic search dependencies."""
        from dev.nlp.semantic_search import check_dependencies

        deps = check_dependencies()

        assert 'sentence_transformers' in deps
        assert isinstance(deps['sentence_transformers'], bool)

    def test_installation_instructions(self):
        """Test getting installation instructions."""
        from dev.nlp.extractors import get_installation_instructions

        instructions = get_installation_instructions()

        assert isinstance(instructions, str)
        assert len(instructions) > 0


class TestCostEstimation:
    """Test Claude API cost estimation."""

    def test_estimate_cost_haiku(self):
        """Test cost estimation for Haiku model."""
        from dev.nlp.claude_assistant import estimate_cost

        costs = estimate_cost(num_entries=100, model='haiku')

        assert costs['model'] == 'haiku'
        assert costs['num_entries'] == 100
        assert costs['total_cost'] > 0
        assert costs['cost_per_entry'] > 0

    def test_estimate_cost_sonnet(self):
        """Test cost estimation for Sonnet model."""
        from dev.nlp.claude_assistant import estimate_cost

        costs_haiku = estimate_cost(num_entries=100, model='haiku')
        costs_sonnet = estimate_cost(num_entries=100, model='sonnet')

        # Sonnet should be more expensive
        assert costs_sonnet['total_cost'] > costs_haiku['total_cost']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

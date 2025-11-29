#!/usr/bin/env python3
"""
extractors.py
-------------
NLP-powered entity and theme extraction using local ML models.

Level 2: spaCy NER for entity extraction
Level 3: Sentence Transformers for semantic analysis

Features:
- Person name extraction
- Location/city detection
- Theme identification
- Event detection
- Relationship inference

Usage:
    # Initialize extractor
    extractor = EntityExtractor()

    # Extract from entry
    entities = extractor.extract_from_text(entry_text)

    # Extract themes
    theme_extractor = ThemeExtractor()
    themes = theme_extractor.extract_themes(entry_text)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import List, Dict, Set, Any
from pathlib import Path
from dataclasses import dataclass, field

# --- Third party imports ---
try:
    import spacy
    from spacy.language import Language

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    Language = None

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    np = None


@dataclass
class ExtractedEntities:
    """Container for extracted entities."""

    people: Set[str] = field(default_factory=set)
    locations: Set[str] = field(default_factory=set)
    cities: Set[str] = field(default_factory=set)
    organizations: Set[str] = field(default_factory=set)
    events: Set[str] = field(default_factory=set)
    themes: Set[str] = field(default_factory=set)
    confidence: Dict[str, float] = field(default_factory=dict)


@dataclass
class ThemeSuggestion:
    """Theme suggestion with confidence score."""

    theme: str
    confidence: float
    evidence: List[str] = field(default_factory=list)


class EntityExtractor:
    """
    Extract entities using spaCy NER (Named Entity Recognition).

    Intelligence Level: ⭐⭐⭐⭐☆

    Uses pre-trained ML models to identify:
    - PERSON: People names
    - GPE: Geo-political entities (cities, countries)
    - LOC: Locations
    - ORG: Organizations
    - EVENT: Named events
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize spaCy extractor.

        Args:
            model_name: spaCy model to use
                - en_core_web_sm: Small, fast (11 MB)
                - en_core_web_md: Medium, more accurate (40 MB)
                - en_core_web_lg: Large, most accurate (560 MB)

        Raises:
            ImportError: If spaCy not installed
            OSError: If model not downloaded
        """
        if not SPACY_AVAILABLE:
            raise ImportError(
                "spaCy not installed. Install with: pip install spacy && "
                "python -m spacy download en_core_web_sm"
            )

        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            raise OSError(
                f"spaCy model '{model_name}' not found. "
                f"Download with: python -m spacy download {model_name}"
            )

    def extract_from_text(self, text: str) -> ExtractedEntities:
        """
        Extract entities from text using NER.

        Args:
            text: Text to analyze

        Returns:
            ExtractedEntities with detected people, locations, etc.
        """
        entities = ExtractedEntities()

        # Process text
        doc = self.nlp(text)

        # Extract named entities
        for ent in doc.ents:
            entity_text = ent.text.strip()
            entity_label = ent.label_

            # Confidence score (0-1)
            # spaCy doesn't provide scores, so we use heuristics
            confidence = self._calculate_confidence(ent, doc)

            if entity_label == "PERSON":
                entities.people.add(entity_text)
                entities.confidence[f"person:{entity_text}"] = confidence

            elif entity_label == "GPE":
                # Geo-political entity (city, country, state)
                entities.cities.add(entity_text)
                entities.confidence[f"city:{entity_text}"] = confidence

            elif entity_label == "LOC":
                # Non-GPE location
                entities.locations.add(entity_text)
                entities.confidence[f"location:{entity_text}"] = confidence

            elif entity_label == "ORG":
                entities.organizations.add(entity_text)
                entities.confidence[f"org:{entity_text}"] = confidence

            elif entity_label == "EVENT":
                entities.events.add(entity_text)
                entities.confidence[f"event:{entity_text}"] = confidence

        return entities

    def _calculate_confidence(self, ent, doc) -> float:
        """
        Calculate confidence score for entity.

        Heuristics:
        - Longer entities: higher confidence
        - Capitalized: higher confidence
        - Multiple occurrences: higher confidence
        """
        score = 0.5  # Base score

        # Length heuristic
        if len(ent.text) > 10:
            score += 0.2
        elif len(ent.text) > 5:
            score += 0.1

        # Capitalization heuristic
        if ent.text[0].isupper():
            score += 0.1

        # Frequency heuristic
        count = sum(1 for token in doc if token.text == ent.text)
        if count > 2:
            score += 0.2
        elif count > 1:
            score += 0.1

        return min(score, 1.0)

    def get_entry_text(self, entry) -> str:
        """
        Extract all text content from an Entry object.

        Args:
            entry: Entry database object

        Returns:
            Combined text from entry body, epigraph, and notes
        """
        # Combine all text fields
        text_parts = []

        # Read body from file
        if entry.file_path:
            file_path = Path(entry.file_path)
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")

                # Extract body (skip YAML frontmatter)
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        text_parts.append(parts[2].strip())
                    else:
                        text_parts.append(content)
                else:
                    text_parts.append(content)

        # Add epigraph and notes
        if entry.epigraph:
            text_parts.append(entry.epigraph)

        if entry.notes:
            text_parts.append(entry.notes)

        return "\n\n".join(text_parts)

    def extract_from_entry(self, entry) -> ExtractedEntities:
        """
        Extract entities from Entry object.

        Args:
            entry: Entry database object

        Returns:
            ExtractedEntities
        """
        full_text = self.get_entry_text(entry)
        return self.extract_from_text(full_text)


class ThemeExtractor:
    """
    Extract themes using semantic similarity with sentence transformers.

    Intelligence Level: ⭐⭐⭐⭐☆

    Uses ML-based semantic similarity to identify themes without relying on
    keyword patterns. Understands context and meaning.

    Requires sentence-transformers: pip install sentence-transformers
    """

    def __init__(self):
        """
        Initialize theme extractor.

        Raises:
            ImportError: If sentence-transformers not installed
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "Sentence transformers required for theme extraction. "
                "Install with: pip install sentence-transformers"
            )

        # Load sentence transformer model
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # Pre-compute theme embeddings
        self.theme_embeddings = self._compute_theme_embeddings()

    def _compute_theme_embeddings(self) -> Dict[str, Any]:
        """Pre-compute embeddings for theme descriptions."""
        theme_descriptions = {
            "identity": "sense of self, personal identity, who I am, self-concept",
            "relationships": "connections with others, friendships, family, love, trust",
            "growth": "personal development, learning, progress, change, evolution",
            "anxiety": "worry, stress, nervousness, fear, panic, anxious feelings",
            "creativity": "creative work, art, writing, imagination, inspiration",
            "work": "professional life, career, job, projects, work environment",
            "memory": "memories, remembering, nostalgia, past experiences",
            "home": "living space, house, apartment, domestic life",
            "travel": "journeys, trips, exploration, adventure, places visited",
            "health": "physical health, wellness, illness, exercise, fitness",
            "reflection": "thinking deeply, contemplation, self-reflection",
            "loss": "grief, mourning, loss, missing someone or something",
        }

        embeddings = {}
        for theme, description in theme_descriptions.items():
            embeddings[theme] = self.model.encode(description)

        return embeddings

    def extract_themes(
        self, text: str, min_confidence: float = 0.3
    ) -> List[ThemeSuggestion]:
        """
        Extract themes from text using semantic similarity.

        Args:
            text: Text to analyze
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            List of ThemeSuggestion objects sorted by confidence
        """
        # Encode text
        text_embedding = self.model.encode(text)

        # Compute similarity with each theme
        suggestions = []

        for theme, theme_embedding in self.theme_embeddings.items():
            # Cosine similarity
            similarity = np.dot(text_embedding, theme_embedding) / (
                np.linalg.norm(text_embedding) * np.linalg.norm(theme_embedding)
            )

            # Normalize to 0-1
            confidence = (similarity + 1) / 2

            if confidence >= min_confidence:
                suggestions.append(
                    ThemeSuggestion(
                        theme=theme, confidence=float(confidence), evidence=[]
                    )
                )

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        return suggestions


def check_dependencies() -> Dict[str, bool]:
    """Check which NLP dependencies are available."""
    return {
        "spacy": SPACY_AVAILABLE,
        "sentence_transformers": TRANSFORMERS_AVAILABLE,
    }


def get_installation_instructions() -> str:
    """Get installation instructions for missing dependencies."""
    deps = check_dependencies()

    instructions = []

    if not deps["spacy"]:
        instructions.append(
            "spaCy (Level 2 - Entity Extraction):\n"
            "  pip install spacy\n"
            "  python -m spacy download en_core_web_sm"
        )

    if not deps["sentence_transformers"]:
        instructions.append(
            "Sentence Transformers (Level 3 - Semantic Search):\n"
            "  pip install sentence-transformers"
        )

    if not instructions:
        return "✓ All NLP dependencies installed!"

    return "Missing dependencies:\n\n" + "\n\n".join(instructions)


if __name__ == "__main__":
    # Print dependency status
    print(get_installation_instructions())

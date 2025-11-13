#!/usr/bin/env python3
"""
extractors.py
-------------
AI-powered entity and theme extraction using local ML models.

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
from typing import List, Dict, Set, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
import re

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

    def extract_from_entry(self, entry) -> ExtractedEntities:
        """
        Extract entities from Entry object.

        Args:
            entry: Entry database object

        Returns:
            ExtractedEntities
        """
        # Combine all text fields
        text_parts = []

        # Read body from file
        if entry.file_path:
            file_path = Path(entry.file_path)
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')

                # Extract body (skip YAML frontmatter)
                if content.startswith('---'):
                    parts = content.split('---', 2)
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

        full_text = "\n\n".join(text_parts)

        return self.extract_from_text(full_text)


class ThemeExtractor:
    """
    Extract themes using keyword patterns and semantic similarity.

    Intelligence Level: ⭐⭐⭐⭐☆

    Combines:
    - Keyword pattern matching
    - Semantic similarity with sentence transformers
    - Context analysis
    """

    # Theme patterns (Level 1: Keyword-based)
    THEME_PATTERNS = {
        'identity': [
            r'\bidentity\b', r'\bself\b', r'\bwho (I|i) am\b',
            r'\bpersonality\b', r'\bcharacter\b'
        ],
        'relationships': [
            r'\brelationship\b', r'\bfriend\b', r'\bfamily\b',
            r'\blove\b', r'\bconnection\b', r'\btrust\b'
        ],
        'growth': [
            r'\bgrowth\b', r'\bdevelop\b', r'\blearn\b',
            r'\bprogress\b', r'\bevolve\b', r'\bchange\b'
        ],
        'anxiety': [
            r'\banxiety\b', r'\bworry\b', r'\bstress\b',
            r'\bnervous\b', r'\bfear\b', r'\bpanic\b'
        ],
        'creativity': [
            r'\bcreativity\b', r'\bcreative\b', r'\bart\b',
            r'\bwriting\b', r'\bimagination\b', r'\binspiration\b'
        ],
        'work': [
            r'\bwork\b', r'\bjob\b', r'\bcareer\b',
            r'\bproject\b', r'\bprofessional\b'
        ],
        'memory': [
            r'\bmemory\b', r'\bremember\b', r'\brecall\b',
            r'\bnostalgia\b', r'\bpast\b'
        ],
        'home': [
            r'\bhome\b', r'\bhouse\b', r'\bapartment\b',
            r'\bliving space\b', r'\bdomestic\b'
        ],
        'travel': [
            r'\btravel\b', r'\bjourney\b', r'\btrip\b',
            r'\bexplore\b', r'\badventure\b'
        ],
        'health': [
            r'\bhealth\b', r'\bsick\b', r'\bwellness\b',
            r'\bexercise\b', r'\bfitness\b'
        ],
        'reflection': [
            r'\breflect\b', r'\bcontemplat\b', r'\bponder\b',
            r'\bthink about\b', r'\bconsider\b'
        ],
        'loss': [
            r'\bloss\b', r'\bgrief\b', r'\bmourn\b',
            r'\bmissing\b', r'\bgone\b', r'\bdeath\b'
        ],
    }

    def __init__(self, use_transformers: bool = True):
        """
        Initialize theme extractor.

        Args:
            use_transformers: Use sentence transformers for semantic analysis
        """
        self.use_transformers = use_transformers and TRANSFORMERS_AVAILABLE

        if self.use_transformers:
            # Load sentence transformer model
            self.model = SentenceTransformer('all-MiniLM-L6-v2')

            # Pre-compute theme embeddings
            self.theme_embeddings = self._compute_theme_embeddings()

    def _compute_theme_embeddings(self) -> Dict[str, Any]:
        """Pre-compute embeddings for theme descriptions."""
        theme_descriptions = {
            'identity': "sense of self, personal identity, who I am, self-concept",
            'relationships': "connections with others, friendships, family, love, trust",
            'growth': "personal development, learning, progress, change, evolution",
            'anxiety': "worry, stress, nervousness, fear, panic, anxious feelings",
            'creativity': "creative work, art, writing, imagination, inspiration",
            'work': "professional life, career, job, projects, work environment",
            'memory': "memories, remembering, nostalgia, past experiences",
            'home': "living space, house, apartment, domestic life",
            'travel': "journeys, trips, exploration, adventure, places visited",
            'health': "physical health, wellness, illness, exercise, fitness",
            'reflection': "thinking deeply, contemplation, self-reflection",
            'loss': "grief, mourning, loss, missing someone or something",
        }

        embeddings = {}
        for theme, description in theme_descriptions.items():
            embeddings[theme] = self.model.encode(description)

        return embeddings

    def extract_themes(
        self,
        text: str,
        min_confidence: float = 0.3
    ) -> List[ThemeSuggestion]:
        """
        Extract themes from text.

        Args:
            text: Text to analyze
            min_confidence: Minimum confidence threshold

        Returns:
            List of ThemeSuggestion objects
        """
        suggestions = []

        # Method 1: Keyword pattern matching
        keyword_matches = self._extract_themes_keywords(text)

        # Method 2: Semantic similarity (if transformers available)
        if self.use_transformers:
            semantic_matches = self._extract_themes_semantic(text)

            # Combine scores
            all_themes = set(keyword_matches.keys()) | set(semantic_matches.keys())

            for theme in all_themes:
                keyword_score = keyword_matches.get(theme, 0.0)
                semantic_score = semantic_matches.get(theme, 0.0)

                # Weighted combination
                combined_score = (keyword_score * 0.4) + (semantic_score * 0.6)

                if combined_score >= min_confidence:
                    suggestions.append(ThemeSuggestion(
                        theme=theme,
                        confidence=combined_score,
                        evidence=[]
                    ))
        else:
            # Only keyword matching
            for theme, score in keyword_matches.items():
                if score >= min_confidence:
                    suggestions.append(ThemeSuggestion(
                        theme=theme,
                        confidence=score,
                        evidence=[]
                    ))

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        return suggestions

    def _extract_themes_keywords(self, text: str) -> Dict[str, float]:
        """Extract themes using keyword patterns."""
        text_lower = text.lower()
        scores = {}

        for theme, patterns in self.THEME_PATTERNS.items():
            match_count = 0

            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                match_count += len(matches)

            if match_count > 0:
                # Normalize score (cap at 1.0)
                score = min(match_count * 0.2, 1.0)
                scores[theme] = score

        return scores

    def _extract_themes_semantic(self, text: str) -> Dict[str, float]:
        """Extract themes using semantic similarity."""
        if not self.use_transformers:
            return {}

        # Encode text
        text_embedding = self.model.encode(text)

        # Compute similarity with each theme
        scores = {}

        for theme, theme_embedding in self.theme_embeddings.items():
            # Cosine similarity
            similarity = np.dot(text_embedding, theme_embedding) / (
                np.linalg.norm(text_embedding) * np.linalg.norm(theme_embedding)
            )

            # Normalize to 0-1
            normalized_score = (similarity + 1) / 2

            scores[theme] = float(normalized_score)

        return scores


def check_dependencies() -> Dict[str, bool]:
    """Check which AI dependencies are available."""
    return {
        'spacy': SPACY_AVAILABLE,
        'sentence_transformers': TRANSFORMERS_AVAILABLE,
    }


def get_installation_instructions() -> str:
    """Get installation instructions for missing dependencies."""
    deps = check_dependencies()

    instructions = []

    if not deps['spacy']:
        instructions.append(
            "spaCy (Level 2 - Entity Extraction):\n"
            "  pip install spacy\n"
            "  python -m spacy download en_core_web_sm"
        )

    if not deps['sentence_transformers']:
        instructions.append(
            "Sentence Transformers (Level 3 - Semantic Search):\n"
            "  pip install sentence-transformers"
        )

    if not instructions:
        return "✓ All AI dependencies installed!"

    return "Missing dependencies:\n\n" + "\n\n".join(instructions)


if __name__ == '__main__':
    # Print dependency status
    print(get_installation_instructions())

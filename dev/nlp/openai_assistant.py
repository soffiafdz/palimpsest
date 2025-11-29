#!/usr/bin/env python3
"""
openai_assistant.py
-------------------
OpenLLM API integration for advanced text analysis.

Level 4: OpenLLM API (Optional, Paid)

Features:
- Intelligent entity extraction
- Theme identification
- Relationship inference
- Entry summarization
- Character voice analysis
- Narrative arc suggestions

Cost: ~$0.003/entry (GPT-4o mini), ~$0.025/entry (GPT-4o)

Setup:
    export OPENAI_API_KEY="your-api-key"

Usage:
    # Initialize assistant
    assistant = OpenAIAssistant()

    # Extract metadata from entry
    metadata = assistant.extract_metadata(entry_text)

    # Analyze entry for manuscript
    analysis = assistant.analyze_for_manuscript(entry_text)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import json

# --- Third party imports ---
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None


@dataclass
class OpenAIMetadata:
    """Metadata extracted by OpenAI."""

    people: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    cities: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    summary: str = ""
    mood: str = ""
    confidence: Dict[str, float] = field(default_factory=dict)


@dataclass
class OpenAIManuscriptAnalysis:
    """Manuscript analysis from OpenAI."""

    entry_type: str = ""  # vignette, scene, reflection, etc.
    narrative_potential: float = 0.0  # 0-1 score
    suggested_arc: str = ""
    character_notes: str = ""
    adaptation_notes: str = ""
    themes: List[str] = field(default_factory=list)
    voice_notes: str = ""


class OpenAIAssistant:
    """
    OpenLLM API assistant for advanced text analysis.

    Intelligence Level: ⭐⭐⭐⭐⭐

    Accurate entity extraction and theme identification.
    Understands context, nuance, and narrative structure.

    Cost: ~$0.003 per entry (GPT-4o mini) - cheapest option
          ~$0.025 per entry (GPT-4o) - most capable
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI assistant.

        Args:
            api_key: OpenLLM API key (or set OPENAI_API_KEY env var)
            model: OpenAI model to use
                - gpt-4o-mini: Fast, cheap ($0.15/$0.60 per MTok)
                - gpt-4o: Most capable ($2.50/$10 per MTok)
                - gpt-4-turbo: Previous generation ($10/$30 per MTok)

        Raises:
            ImportError: If openai package not installed
            ValueError: If API key not provided
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI package not installed. " "Install with: pip install openai"
            )

        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def extract_metadata(self, text: str) -> OpenAIMetadata:
        """
        Extract metadata from journal entry.

        Args:
            text: Entry text

        Returns:
            OpenAIMetadata with extracted entities, themes, summary
        """
        prompt = f"""Analyze this journal entry and extract metadata.

Journal Entry:
{text}

Extract and return as JSON:
{{
  "people": ["list of person names mentioned"],
  "locations": ["list of specific locations mentioned"],
  "cities": ["list of cities/places mentioned"],
  "events": ["list of notable events mentioned"],
  "themes": ["list of themes (e.g., identity, relationships, anxiety, growth)"],
  "tags": ["list of descriptive tags"],
  "summary": "one-sentence summary of the entry",
  "mood": "overall mood/emotional tone"
}}

Be thoughtful and accurate. Only include entities and themes that are clearly present.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        # Parse response
        content = response.choices[0].message.content

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to empty metadata
            data = {}

        return OpenAIMetadata(
            people=data.get("people", []),
            locations=data.get("locations", []),
            cities=data.get("cities", []),
            events=data.get("events", []),
            themes=data.get("themes", []),
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
            mood=data.get("mood", ""),
        )

    def analyze_for_manuscript(self, text: str) -> OpenAIManuscriptAnalysis:
        """
        Analyze entry for manuscript potential.

        Args:
            text: Entry text

        Returns:
            OpenAIManuscriptAnalysis with narrative assessment
        """
        prompt = f"""Analyze this journal entry for its potential as source material for a literary manuscript.

Journal Entry:
{text}

Assess and return as JSON:
{{
  "entry_type": "vignette|scene|reflection|dialogue|description",
  "narrative_potential": 0.0-1.0 (how strong is the narrative/literary quality),
  "suggested_arc": "which narrative arc this could fit into",
  "character_notes": "observations about people/characters mentioned",
  "adaptation_notes": "suggestions for how to adapt this into fiction",
  "themes": ["literary themes present"],
  "voice_notes": "notes on narrative voice and style"
}}

Be thoughtful about narrative potential and literary quality.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        # Parse response
        content = response.choices[0].message.content

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        return OpenAIManuscriptAnalysis(
            entry_type=data.get("entry_type", ""),
            narrative_potential=data.get("narrative_potential", 0.0),
            suggested_arc=data.get("suggested_arc", ""),
            character_notes=data.get("character_notes", ""),
            adaptation_notes=data.get("adaptation_notes", ""),
            themes=data.get("themes", []),
            voice_notes=data.get("voice_notes", ""),
        )

    def suggest_themes(self, text: str) -> List[str]:
        """
        Suggest themes for an entry.

        Args:
            text: Entry text

        Returns:
            List of theme suggestions
        """
        prompt = f"""Identify the main themes in this journal entry. Return only a JSON array of theme keywords.

Journal Entry:
{text}

Return format: {{"themes": ["theme1", "theme2", "theme3"]}}

Common themes: identity, relationships, growth, anxiety, creativity, work, memory, home, travel, health, reflection, loss, joy, solitude, connection
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            data = json.loads(content)
            themes = data.get("themes", [])
            if isinstance(themes, list):
                return themes
        except json.JSONDecodeError:
            pass

        return []

    def batch_extract_metadata(
        self, texts: List[str], batch_size: int = 5
    ) -> List[OpenAIMetadata]:
        """
        Extract metadata for multiple entries (with batching).

        Args:
            texts: List of entry texts
            batch_size: Number of entries per batch

        Returns:
            List of OpenAIMetadata
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            for text in batch:
                metadata = self.extract_metadata(text)
                results.append(metadata)

        return results


def estimate_cost(
    num_entries: int, avg_entry_length: int = 500, model: str = "gpt-4o-mini"
) -> Dict[str, str | int | float]:
    """
    Estimate API costs.

    Args:
        num_entries: Number of entries to analyze
        avg_entry_length: Average entry length in words
        model: "gpt-4o-mini" or "gpt-4o"

    Returns:
        Dict with cost breakdown
    """
    # Estimate tokens (rough: 1 word ≈ 1.3 tokens)
    avg_input_tokens = avg_entry_length * 1.3 + 200  # + prompt overhead
    avg_output_tokens = 300  # Metadata response

    total_input_tokens = num_entries * avg_input_tokens
    total_output_tokens = num_entries * avg_output_tokens

    # Pricing (per million tokens)
    if model == "gpt-4o-mini":
        input_price = 0.150  # $0.15 per MTok
        output_price = 0.600  # $0.60 per MTok
    elif model == "gpt-4o":
        input_price = 2.50  # $2.50 per MTok
        output_price = 10.00  # $10.00 per MTok
    else:  # gpt-4-turbo
        input_price = 10.00
        output_price = 30.00

    input_cost = (total_input_tokens / 1_000_000) * input_price
    output_cost = (total_output_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost

    return {
        "model": model,
        "num_entries": num_entries,
        "total_input_tokens": int(total_input_tokens),
        "total_output_tokens": int(total_output_tokens),
        "input_cost": round(input_cost, 4),
        "output_cost": round(output_cost, 4),
        "total_cost": round(total_cost, 4),
        "cost_per_entry": round(total_cost / num_entries, 6),
    }


def check_api_key() -> bool:
    """Check if API key is configured."""
    return bool(os.environ.get("OPENAI_API_KEY"))


if __name__ == "__main__":
    print("OpenAI Assistant Status:")
    print(f"  OpenAI package: {'✓' if OPENAI_AVAILABLE else '✗'}")
    print(f"  API key configured: {'✓' if check_api_key() else '✗'}")

    if not OPENAI_AVAILABLE:
        print("\nInstall with: pip install openai")

    if not check_api_key():
        print("\nSet API key: export OPENAI_API_KEY='your-key'")

    print("\nCost estimates:")
    for model in ["gpt-4o-mini", "gpt-4o"]:
        costs = estimate_cost(100, model=model)
        print(
            f"  {model}: ${costs['total_cost']:.2f} for 100 entries (${costs['cost_per_entry']:.6f}/entry)"
        )

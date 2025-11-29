#!/usr/bin/env python3
"""
claude_assistant.py
-------------------
Claude API integration for advanced text analysis.

Level 4: Claude API (Optional, Paid)

Features:
- Intelligent entity extraction
- Theme identification
- Relationship inference
- Entry summarization
- Character voice analysis
- Narrative arc suggestions

Cost: ~$0.007 per entry (Claude 3.5 Haiku)

Setup:
    export ANTHROPIC_API_KEY="your-api-key"

Usage:
    # Initialize assistant
    assistant = ClaudeAssistant()

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
import importlib.util

# --- Third party imports ---
_anthropic_spec = importlib.util.find_spec("anthropic")
if _anthropic_spec is not None and _anthropic_spec.loader is not None:
    ANTHROPIC_AVAILABLE = True
    anthropic = importlib.util.module_from_spec(_anthropic_spec)
    _anthropic_spec.loader.exec_module(anthropic)
else:
    ANTHROPIC_AVAILABLE = False
    anthropic = None


@dataclass
class ClaudeMetadata:
    """Metadata extracted by Claude."""

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
class ManuscriptAnalysis:
    """Manuscript analysis from Claude."""

    entry_type: str = ""  # vignette, scene, reflection, etc.
    narrative_potential: float = 0.0  # 0-1 score
    suggested_arc: str = ""
    character_notes: str = ""
    adaptation_notes: str = ""
    themes: List[str] = field(default_factory=list)
    voice_notes: str = ""


class ClaudeAssistant:
    """
    Claude API assistant for advanced text analysis.

    Intelligence Level: ⭐⭐⭐⭐⭐

    Most accurate entity extraction and theme identification.
    Understands context, nuance, and narrative structure.

    Cost: ~$0.007 per entry (Claude 3.5 Haiku)
          ~$0.075 per entry (Claude 3.5 Sonnet) - more accurate
    """

    def __init__(
        self, api_key: Optional[str] = None, model: str = "claude-3-5-haiku-20241022"
    ):
        """
        Initialize Claude assistant.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use
                - claude-3-5-haiku-20241022: Fast, cheap ($0.80/$4 per MTok)
                - claude-3-5-sonnet-20241022: More accurate ($3/$15 per MTok)

        Raises:
            ImportError: If anthropic package not installed
            ValueError: If API key not provided
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "Anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        if anthropic is not None:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            # This branch should ideally not be reached due to the ImportError check above
            # but is added for explicit type safety and linter satisfaction.
            raise ImportError("Anthropic client could not be initialized.")
        self.model = model

    def extract_metadata(self, text: str) -> ClaudeMetadata:
        """
        Extract metadata from journal entry.

        Args:
            text: Entry text

        Returns:
            ClaudeMetadata with extracted entities, themes, summary
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

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        content = response.content[0].text

        # Extract JSON (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to empty metadata
            data = {}

        return ClaudeMetadata(
            people=data.get("people", []),
            locations=data.get("locations", []),
            cities=data.get("cities", []),
            events=data.get("events", []),
            themes=data.get("themes", []),
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
            mood=data.get("mood", ""),
        )

    def analyze_for_manuscript(self, text: str) -> ManuscriptAnalysis:
        """
        Analyze entry for manuscript potential.

        Args:
            text: Entry text

        Returns:
            ManuscriptAnalysis with narrative assessment
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

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1536,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        content = response.content[0].text

        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        return ManuscriptAnalysis(
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

Return format: ["theme1", "theme2", "theme3"]

Common themes: identity, relationships, growth, anxiety, creativity, work, memory, home, travel, health, reflection, loss, joy, solitude, connection
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text

        # Extract JSON array
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        elif "[" in content and "]" in content:
            # Extract array from text
            start = content.index("[")
            end = content.rindex("]") + 1
            content = content[start:end]

        try:
            themes = json.loads(content)
            if isinstance(themes, list):
                return themes
        except json.JSONDecodeError:
            pass

        return []

    def batch_extract_metadata(
        self, texts: List[str], batch_size: int = 5
    ) -> List[ClaudeMetadata]:
        """
        Extract metadata for multiple entries (with batching).

        Args:
            texts: List of entry texts
            batch_size: Number of entries per batch

        Returns:
            List of ClaudeMetadata
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            for text in batch:
                metadata = self.extract_metadata(text)
                results.append(metadata)

        return results


def estimate_cost(
    num_entries: int, avg_entry_length: int = 500, model: str = "haiku"
) -> Dict[str, str | float]:
    """
    Estimate API costs.

    Args:
        num_entries: Number of entries to analyze
        avg_entry_length: Average entry length in words
        model: "haiku" or "sonnet"

    Returns:
        Dict with cost breakdown
    """
    # Estimate tokens (rough: 1 word ≈ 1.3 tokens)
    avg_input_tokens = avg_entry_length * 1.3 + 200  # + prompt overhead
    avg_output_tokens = 300  # Metadata response

    total_input_tokens = num_entries * avg_input_tokens
    total_output_tokens = num_entries * avg_output_tokens

    # Pricing (per million tokens)
    if model == "haiku":
        input_price = 0.80  # $0.80 per MTok
        output_price = 4.00  # $4.00 per MTok
    else:  # sonnet
        input_price = 3.00
        output_price = 15.00

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
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


if __name__ == "__main__":
    print("Claude Assistant Status:")
    print(f"  Anthropic package: {'✓' if ANTHROPIC_AVAILABLE else '✗'}")
    print(f"  API key configured: {'✓' if check_api_key() else '✗'}")

    if not ANTHROPIC_AVAILABLE:
        print("\nInstall with: pip install anthropic")

    if not check_api_key():
        print("\nSet API key: export ANTHROPIC_API_KEY='your-key'")

    print("\nCost estimates:")
    for model in ["haiku", "sonnet"]:
        costs = estimate_cost(100, model=model)
        print(
            f"  {model.title()}: ${costs['total_cost']:.2f} for 100 entries (${costs['cost_per_entry']:.6f}/entry)"
        )

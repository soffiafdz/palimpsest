"""
AI-assisted analysis and extraction module.

Provides progressive levels of AI intelligence:
- Level 1: Keyword pattern matching (free, built-in)
- Level 2: spaCy NER (free, ML-based entity extraction)
- Level 3: Sentence Transformers (free, semantic search)
- Level 4: Claude API (paid, most accurate)
"""
from dev.ai.extractors import (
    EntityExtractor,
    ThemeExtractor,
    ExtractedEntities,
    ThemeSuggestion,
    check_dependencies as check_extractor_deps,
)

try:
    from dev.ai.semantic_search import SemanticSearch, SemanticResult
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    SemanticSearch = None
    SemanticResult = None

try:
    from dev.ai.claude_assistant import (
        ClaudeAssistant,
        ClaudeMetadata,
        ManuscriptAnalysis,
        estimate_cost,
    )
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    ClaudeAssistant = None
    ClaudeMetadata = None
    ManuscriptAnalysis = None
    estimate_cost = None


__all__ = [
    'EntityExtractor',
    'ThemeExtractor',
    'ExtractedEntities',
    'ThemeSuggestion',
    'SemanticSearch',
    'SemanticResult',
    'ClaudeAssistant',
    'ClaudeMetadata',
    'ManuscriptAnalysis',
    'estimate_cost',
    'check_extractor_deps',
    'SEMANTIC_AVAILABLE',
    'CLAUDE_AVAILABLE',
]

"""
NLP-based analysis and extraction module.

Provides progressive levels of analysis capabilities:
- Level 1: Keyword pattern matching (free, built-in)
- Level 2: spaCy NER (free, ML-based entity extraction)
- Level 3: Sentence Transformers (free, semantic search)
- Level 4: LLM APIs (paid, most accurate) - Claude or OpenAI
"""
from dev.nlp.extractors import (
    EntityExtractor,
    ThemeExtractor,
    ExtractedEntities,
    ThemeSuggestion,
    check_dependencies as check_extractor_deps,
)

try:
    from dev.nlp.semantic_search import SemanticSearch, SemanticResult
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    SemanticSearch = None
    SemanticResult = None

try:
    from dev.nlp.claude_assistant import (
        ClaudeAssistant,
        ClaudeMetadata,
        ManuscriptAnalysis,
        estimate_cost as estimate_claude_cost,
    )
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    ClaudeAssistant = None
    ClaudeMetadata = None
    ManuscriptAnalysis = None
    estimate_claude_cost = None

try:
    from dev.nlp.openai_assistant import (
        OpenAIAssistant,
        OpenAIMetadata,
        OpenAIManuscriptAnalysis,
        estimate_cost as estimate_openai_cost,
    )
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAIAssistant = None
    OpenAIMetadata = None
    OpenAIManuscriptAnalysis = None
    estimate_openai_cost = None


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
    'OpenAIAssistant',
    'OpenAIMetadata',
    'OpenAIManuscriptAnalysis',
    'estimate_claude_cost',
    'estimate_openai_cost',
    'check_extractor_deps',
    'SEMANTIC_AVAILABLE',
    'CLAUDE_AVAILABLE',
    'OPENAI_AVAILABLE',
]

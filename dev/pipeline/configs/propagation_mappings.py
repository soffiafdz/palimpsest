#!/usr/bin/env python3
"""
propagation_mappings.py
-----------------------
Propagation mappings for narrative analysis consolidation.

This module defines the mappings used to propagate consolidated tags and
thematic arcs back to individual analysis files. Contains:

- PEOPLE_NAMES: Names to exclude from cleaned tags
- LOCATIONS: Location names to exclude from cleaned tags
- TAG_CATEGORIES: Keyword mappings for tag categorization
- THEMATIC_ARCS: Keyword mappings for thematic arc assignment

Functions:
    clean_tags: Remove people/location names from tags
    get_tag_categories: Map tags to semantic categories
    get_thematic_arcs: Map themes to overarching arcs

Usage:
    from dev.pipeline.configs.propagation_mappings import (
        clean_tags,
        get_tag_categories,
        get_thematic_arcs,
    )

    tags = clean_tags("clara, depression, insomnia")
    categories = get_tag_categories(tags)
    arcs = get_thematic_arcs(themes)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import List, Set


# ============================================================================
# Exclusion Sets
# ============================================================================

PEOPLE_NAMES: Set[str] = {
    "clara", "clarizard", "sofibug", "majo", "alda", "aliza", "sonny", "paty",
    "fabiola", "dr. franck", "dr. perera", "louis", "walter", "florence", "sarah",
    "miriam", "myriam", "renzo", "didier", "sophie", "alex", "nicola", "hilary",
    "melissa", "bea", "catherine", "helena", "reza", "yuval", "gaelle", "jana",
    "emily", "houssain", "héloise", "shubhendra", "neda", "misael", "zahra",
    "veronica", "ela", "meagan", "méléda", "amanda", "aurélie", "sasha", "steph",
    "amélie", "sylvia", "rachel", "poncho", "beri", "yara", "johnathan", "miguel",
    "lavi", "jessica", "laura", "nick long", "seunghwa", "katherine", "emma",
    "calli", "alexia", "monica", "les", "jonathan", "nymeria"
}
"""People names to exclude from cleaned tags."""

LOCATIONS: Set[str] = {
    "beaubien", "chez ernest", "falafel yoni", "café velours", "lola rosa",
    "thomson house", "the neuro", "jarry", "station jarry", "oui mais non",
    "cinéma moderne", "cinéma du parc", "banq", "café aunja", "greenspot",
    "la banquise", "taverne atlantic", "la taverne atlantic", "dieu du ciel!",
    "yokato yokabai ramen", "ramen kinton", "larry's", "café safran", "café pista",
    "else's", "la arepera", "le toasteur", "complexe desjardins", "shawarmaz",
    "pinocchio café", "joie de livres", "froidôchaud", "pizza no 900", "stella pizzeria",
    "verdun", "rosemont", "mont-royal", "guy-concordia", "saint-henri", "jean-talon",
    "lionel-groulx", "papineau", "bonaventure", "sherbrooke", "gare centrale",
    "old port", "parc jarry", "parc lafontaine", "mount royal", "canal lachine",
    "marché atwater", "place ville marie", "eaton centre", "mile end", "hochelaga",
    "coyoacán", "tijuana", "mexico city", "blend station", "san diego", "toronto",
    "montreal", "québec city", "montmorency falls", "gault nature reserve",
    "oh my deer café", "velora café", "tsikinis", "photo st-denis", "indigo",
    "urban outfitters", "ardene", "jean coutu", "iga", "baristello", "pistik",
    "mtelus", "cinéma l'amour", "pizza del perro negro", "chez gaston", "las palmas",
    "cusm", "biron", "wellness hub", "hygea", "parents' house", "san josé",
    "medellín", "costa rica", "salamanca", "cancun", "alberta", "banff", "jasper",
    "boulder", "france", "rouen"
}
"""Location names to exclude from cleaned tags."""


# ============================================================================
# Tag Category Mappings
# ============================================================================

TAG_CATEGORIES: dict[str, List[str]] = {
    "Digital Surveillance": [
        "instagram", "story", "close friends", "viewer", "views", "swipe trick",
        "algorithm", "notification", "reel", "archive", "muting", "blocking",
        "unfollowing", "removing follower", "stalking", "cyber-stalking",
        "developer tools", "filenames", "polarsteps", "green circle"
    ],
    "Photography": [
        "photography", "photo", "double exposure", "self-portrait", "darkroom",
        "negatives", "contact sheet", "harman phoenix", "pentax", "yashicaflex",
        "canon", "half-frame", "120mm", "medium format", "kodak", "santacolour",
        "film", "camera", "voyeurism"
    ],
    "AI/Technology": [
        "chatgpt", "gpt", "ai", "claude", "gemini", "meta-analysis", "clinical note",
        "telegram", "whatsapp", "imessage"
    ],
    "Writing/Poetry": [
        "poem", "poetry", "haiku", "writing", "journal", "manuscript", "two white spaces",
        "rock & ocean", "drafting", "letter", "a softer world"
    ],
    "Medication": [
        "medication", "seroquel", "clonazepam", "dayvigo", "estrogen", "hrt",
        "quetiapine", "prescription", "pharmacy", "dose", "skipped dose",
        "sleeping pills", "injection"
    ],
    "Crisis/Suicidality": [
        "suicidal", "suicide", "self-harm", "hospitalization", "crisis",
        "razor blade", "overdose", "intervention", "institutionalization",
        "breaking point", "rock bottom", "syncope", "seizure"
    ],
    "Food/Diet": [
        "vegetarian", "vegan", "food", "eating", "ramen", "poutine", "pizza",
        "gnocchi", "falafel", "dumplings", "lentils", "chickpeas", "oysters",
        "starvation", "eating disorder", "meat disgust"
    ],
    "Academia": [
        "thesis", "phd", "lab", "research", "paper", "seminar", "postdoc",
        "grant", "cihr", "hbhl", "conference", "aaic", "poster", "candidacy",
        "defense"
    ],
    "Sleep/Insomnia": [
        "insomnia", "sleep", "nightmare", "dream", "sleepless", "night sweats",
        "4am", "lethargy"
    ],
    "Depression/Grief": [
        "depression", "grief", "mourning", "crying", "tears", "sobbing",
        "fog", "numbness", "apagada", "demacrada", "darkness"
    ],
    "Literature": [
        "barthes", "despentes", "leduc", "maggie nelson", "reading", "bechdel",
        "darrieussecq", "camus", "proust", "bluets", "argonauts", "fun home",
        "fragments d'un discours amoureux", "la chambre claire", "king kong theory",
        "thérèse et isabelle", "truismes"
    ],
    "Identity": [
        "identity", "self", "mirror", "shadow self", "fragmented", "dissolution",
        "impostor", "integration"
    ],
    "Therapy": [
        "therapy", "therapist", "psychiatr", "session", "confidentiality"
    ],
    "Dysphoria/Body": [
        "dysphoria", "body image", "chest", "breast", "passing", "testosterone",
        "body horror", "weight", "aging", "physical decline", "demacrada"
    ],
    "Obsession/Control": [
        "obsession", "control", "dependency", "addiction", "compulsion",
        "clinical behavior", "rigid", "loop"
    ],
    "Meta-narrative": [
        "meta-narrative", "clarizard", "palimpsest", "future self", "past self",
        "curatorial", "2040", "2034", "anonymous reader", "m.e.r."
    ],
    "Mania/Bipolar": [
        "mania", "hypomania", "bipolar", "mixed episode", "mood swing",
        "manic", "euphoria"
    ],
    "Music": [
        "tamino", "concert", "music", "singing", "song", "ukulele", "playlist",
        "bad bunny", "mon laferte", "juan gabriel", "luis miguel", "tragédie",
        "hey oh", "lonely shade of blue", "baile inolvidable"
    ],
    "Rejection/Ghosting": [
        "ghosting", "rejection", "breakup", "abandoned", "ignored", "breadcrumb",
        "stood up", "muting", "seen status", "vu"
    ],
    "Intimacy": [
        "first kiss", "last kiss", "kiss", "touch", "cuddle", "hug",
        "physical intimacy", "hand-holding", "cuddling"
    ],
    "Alcohol": [
        "alcohol", "drinking", "wine", "beer", "vodka", "whisky", "raki",
        "absinthe", "fireball", "kraken", "binge"
    ],
    "Messaging": [
        "text", "texting", "message", "voice message", "voice note", "draft",
        "unopened message", "unread", "lowercase", "typing"
    ],
    "Anxiety/Panic": [
        "anxiety", "panic", "dread", "nervous", "paranoia", "fear"
    ],
    "Film/TV": [
        "princess mononoke", "waking life", "the last of us", "linklater",
        "movie", "cinema", "in the mood for love", "before trilogy",
        "before sunset", "before midnight", "nosferatu", "anora",
        "y tu mamá también", "the pitt", "the leftovers", "the room next door",
        "kiki's delivery service", "tú me abrasas", "almodóvar"
    ],
    "Dating Apps": [
        "tinder", "hinge", "bumble", "dating app", "match", "swipe"
    ],
    "Romance/Dating": [
        "date", "first date", "second date", "third date", "fourth date",
        "flirtation", "flirting", "romance", "courtship"
    ],
    "Sexual": [
        "masturbation", "sex", "orgasm", "celibacy", "virginity", "sexual",
        "sexting", "nude", "erotic"
    ],
    "Smoking/Drugs": [
        "smoking", "cigarette", "vape", "weed", "cannabis"
    ],
    "Tarot/Divination": [
        "tarot", "chariot", "fool", "cards", "divination", "spread",
        "high priestess", "the lovers", "death & rebirth"
    ],
    "Transition": [
        "transition", "trans", "coming out", "disclosure", "gender",
        "passing", "deadname", "old name"
    ],
    "Relics/Objects": [
        "receipt", "anklet", "sweater", "gift", "artifact", "relic",
        "magnet", "note", "drawer", "talisman"
    ],
    "Physical Health": [
        "seizure", "weight", "illness", "sickness", "fatigue", "injury",
        "pneumonia", "hospitalization", "bloodwork"
    ],
    "Isolation": [
        "isolation", "loneliness", "alone", "solitude", "withdrawal"
    ],
    "Hygiene": [
        "hygiene", "shower", "laundry", "dishes", "dirty", "unwashed"
    ],
    "Mental Health": [
        "depression", "suicidal", "self-harm", "bipolar", "mania", "manic",
        "anxiety", "panic", "breakdown", "mental health", "psychiatr"
    ]
}
"""Tag to category mappings (keywords that map to each category)."""


# ============================================================================
# Thematic Arc Mappings
# ============================================================================

THEMATIC_ARCS: dict[str, List[str]] = {
    "THE BODY": [
        "body", "flesh", "physical", "dysphoria", "appetite", "hunger", "touch",
        "skin", "biological", "hormone", "hrt", "weight", "illness", "sick",
        "fatigue", "injury", "pain", "sensation", "intimate", "sexual",
        "consumption", "nourishment", "eating", "starvation", "control and the body"
    ],
    "DIGITAL SURVEILLANCE": [
        "digital", "instagram", "viewer", "algorithm", "story", "panopticon",
        "surveillance", "stalking", "watching", "archive", "screenshot", "online",
        "notification", "app", "follower", "following", "blocking", "muting",
        "seen", "read", "check"
    ],
    "WRITING AS SURVIVAL": [
        "writing", "art", "poetry", "poem", "manuscript", "journal", "creative",
        "literature", "text", "narrative", "expression", "survival", "coping",
        "language as", "art as", "artistic"
    ],
    "CLOSURE & ENDINGS": [
        "closure", "ending", "goodbye", "farewell", "final", "last", "end",
        "severance", "moving on", "acceptance", "letting go", "finished",
        "over", "termination", "resolution"
    ],
    "WAITING & TIME": [
        "waiting", "time", "anticipation", "countdown", "suspended", "liminal",
        "threshold", "patience", "delay", "postpone", "temporal", "clock",
        "hour", "day", "week", "month", "timer", "deadline"
    ],
    "THE OBSESSIVE LOOP": [
        "obsess", "cycle", "loop", "spiral", "return", "repeat", "pattern",
        "compulsion", "addiction", "fixation", "recurring", "relapse",
        "ritual", "habit", "circular"
    ],
    "LANGUAGE & SILENCE": [
        "silence", "voice", "word", "speak", "unsaid", "unspoken", "linguistic",
        "language", "communication", "grammar", "translation", "french", "spanish",
        "bilingual", "vowel", "consonant"
    ],
    "HAUNTED GEOGRAPHY": [
        "geography", "place", "location", "city", "metro", "station", "street",
        "café", "apartment", "room", "space", "territory", "map", "route",
        "displacement", "haunted"
    ],
    "MASKS & PERFORMANCE": [
        "mask", "performance", "perform", "public", "private", "visible",
        "visibility", "shame", "hiding", "facade", "pretend", "act",
        "high-functioning", "curated", "image"
    ],
    "VALIDATION & REJECTION": [
        "validation", "rejection", "accept", "reject", "approval", "worth",
        "value", "inadequa", "enough", "ghost", "breadcrumb", "soft no"
    ],
    "SUBSTITUTION & REPLACEMENT": [
        "substitut", "replace", "surrogate", "backup", "instead", "alternative",
        "crumb", "inadequate", "fill the void", "transfer"
    ],
    "THE UNRELIABLE NARRATOR": [
        "unreliable", "memory", "forget", "fog", "confusion", "perception",
        "truth", "reality", "deceive", "self-deception", "interpretation",
        "misread", "misinterpret"
    ],
    "GHOSTS & PALIMPSESTS": [
        "ghost", "palimpsest", "haunt", "past", "history", "ex-", "former",
        "layer", "overlay", "underneath", "trace", "remnant", "echo",
        "archaeology"
    ],
    "THE CAVALRY": [
        "friend", "support", "care", "help", "council", "group", "collective",
        "intervention", "rally", "anchor", "lifeline", "network", "community"
    ],
    "MEDICALIZATION": [
        "medic", "clinical", "prescription", "dose", "pharmacy", "psychiatr",
        "therap", "treatment", "symptom", "diagnosis", "doctor", "hospital",
        "pill", "drug"
    ],
    "MENTAL HEALTH": [
        "depression", "suicidal", "self-harm", "bipolar", "mania", "manic",
        "anxiety", "panic", "breakdown", "crisis", "episode", "mood"
    ],
    "BUREAUCRATIC TRAUMA": [
        "visa", "passport", "gender marker", "permit", "immigration",
        "ramq", "insurance", "healthcare system", "pharmacy mix-up"
    ],
    "MOTHERHOOD/CHILDLESSNESS": [
        "motherhood", "childless", "fertility", "womb", "parenthood",
        "period dream", "biological clock", "pregnancy"
    ],
    "SEX & DESIRE": [
        "sex scene", "sexual", "first kiss", "nude", "erotic",
        "desire", "attraction", "intimacy"
    ],
    "SUPPORT NETWORK": [
        "vulnerability", "drinking", "we're not really strangers",
        "support", "care", "help"
    ],
    "LANGUAGE & IDENTITY": [
        "french date", "french anxiety", "bilingual", "accent",
        "linguistic", "immigrant"
    ]
}
"""Thematic arc mappings (keywords in theme names/descriptions that map to each arc)."""


# ============================================================================
# Functions
# ============================================================================

def clean_tags(tags_str: str) -> List[str]:
    """
    Remove people names and locations from tags list.

    Args:
        tags_str: Comma-separated string of tags

    Returns:
        List of cleaned tags (without people/location names)
    """
    tags = [t.strip() for t in tags_str.split(",")]
    cleaned = []
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in PEOPLE_NAMES and tag_lower not in LOCATIONS:
            cleaned.append(tag)
    return cleaned


def get_tag_categories(tags: List[str]) -> List[str]:
    """
    Map tags to their semantic categories.

    Args:
        tags: List of tag strings

    Returns:
        Sorted list of category names that match the tags
    """
    categories: Set[str] = set()
    for tag in tags:
        tag_lower = tag.lower()
        for category, keywords in TAG_CATEGORIES.items():
            for keyword in keywords:
                if keyword in tag_lower:
                    categories.add(category)
                    break
    return sorted(categories)


def get_thematic_arcs(themes: List[str]) -> List[str]:
    """
    Map themes to their overarching thematic arcs.

    Args:
        themes: List of theme strings

    Returns:
        Sorted list of arc names that match the themes
    """
    arcs: Set[str] = set()
    for theme in themes:
        theme_lower = theme.lower()
        for arc, keywords in THEMATIC_ARCS.items():
            for keyword in keywords:
                if keyword in theme_lower:
                    arcs.add(arc)
                    break
    return sorted(arcs)

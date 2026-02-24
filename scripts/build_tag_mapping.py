#!/usr/bin/env python3
"""
build_tag_mapping.py
--------------------
Generate the tag_mapping.json file for tag consolidation.

Encodes:
1. Semantic merge rules (30 clusters from the consolidation plan)
2. Title-case conversion rules for all remaining tags

Title Case Rules:
    - Replace structural hyphens with spaces: dating-app → Dating App
    - Preserve meaningful hyphens (compound words): self-harm → Self-Harm
    - Meaningful prefixes: self-, pre-, anti-, co-, post-, non-, ex-,
      half-, one-, mid-, over-, under-, cross-, long-, short-, multi-, inter-
    - Meaningful suffixes: -bound, -like, -based, -driven, -free, -night, -related
    - Acronyms stay uppercase: HRT, AAIC, CIHR, SSRI, etc.
    - Capitalize each word; preserve apostrophes

Usage:
    python scripts/build_tag_mapping.py
    # Writes scripts/tag_mapping.json
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import glob
import json
from pathlib import Path
from typing import Dict, Set

# --- Third-party imports ---
import yaml


# --- Constants ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = PROJECT_ROOT / "data" / "metadata" / "journal"
OUTPUT_FILE = PROJECT_ROOT / "scripts" / "tag_mapping.json"

# Acronyms that should stay all-uppercase
ACRONYMS: Set[str] = {
    "hrt", "aaic", "cihr", "ssri", "srs", "adpd", "egel", "ivf",
    "mmpi", "dna", "ngo", "terf", "lgbtq", "ai", "diy", "4am",
    "a&w", "adhd", "phd", "ta", "ptsd", "bdsm", "bpd", "cbt",
    "dbt", "ocd", "snri", "udem", "iq", "ffs", "covid", "id",
    "lgbt", "nb", "ed", "ig", "dm", "grs",
}

# Words with special casing (not all-caps, not standard capitalize)
SPECIAL_CASE: Dict[str, str] = {
    "chatgpt": "ChatGPT",
    "mcgill": "McGill",
    "iphone": "iPhone",
    "vs": "vs",
}

# Prefixes where the hyphen is meaningful (compound words)
MEANINGFUL_PREFIXES = (
    "self-", "pre-", "anti-", "co-", "post-", "non-", "ex-",
    "half-", "one-", "mid-", "over-", "under-", "cross-",
    "long-", "short-", "multi-", "inter-", "re-", "two-",
    "hyper-", "meta-", "neo-", "semi-", "sub-", "super-",
    "trans-", "bi-", "tri-", "counter-",
)

# Suffixes where the hyphen is meaningful
MEANINGFUL_SUFFIXES = (
    "-bound", "-like", "-based", "-driven", "-free", "-night",
    "-related", "-affirming", "-specific",
)

# ===========================================================================
# Semantic merge rules — old_tag → canonical
# ===========================================================================

SEMANTIC_MERGES: Dict[str, str] = {}


def _add_merges(canonical: str, old_tags: list[str]) -> None:
    """Register a list of old tags that should map to a canonical tag."""
    for tag in old_tags:
        SEMANTIC_MERGES[tag] = canonical


# --- 1. Alcohol/Drinking ---
_add_merges("Alcohol", [
    "alcohol", "drinking", "drunk", "wine", "beer", "vodka",
    "intoxication", "hungover", "bar-crawl", "Bar-Hopping",
    "bar-night", "drinking-alone", "solo-drinking",
    "daytime-drinking", "drunk-alone", "drunk-at-work",
    "drinking-game", "botellones", "brewery", "brewery-outing",
    "beer-festival", "drinks", "bar-hopping",
])
_add_merges("Alcoholism", [
    "alcoholism", "Alcoholism", "binge-drinking", "Binge-Drinking",
    "Binge-drinking", "alcoholism-question", "alcohol-craving",
    "alcohol-resistance", "alcohol-avoidance",
])
_add_merges("Blackout", [
    "blackout", "blackout-drunk", "blackout-reconstruction",
])
_add_merges("Hangover", ["hangover", "Hangover"])
_add_merges("Drunk Texting", ["drunk-texting", "Drunken Text"])
_add_merges("Drunk Writing", ["drunk-writing"])
_add_merges("Drunk Confession", ["drunk-confession", "drunk-confessions"])

# --- 2. Dating App ---
_add_merges("Dating App", [
    "dating-app", "dating app", "tinder", "hinge", "bumble",
    "app", "dating-app-paralysis", "dating-apps-relapse",
    "Tinder", "Hinge", "Bumble",
])

# --- 3. Instagram ---
_add_merges("Instagram", [
    "instagram", "Instagram Addiction", "Instagram Algorithm",
    "Instagram Deactivation", "Instagram Muting",
    "Instagram Obsession", "Instagram Poll", "Instagram Stories",
    "instagram-bait", "instagram-oversharing", "instagram-story",
    "Refollowing",
])
_add_merges("Instagram Surveillance", [
    "instagram-surveillance", "Instagram Surveillance",
    "instagram-stalking", "Instagram stalking",
    "Instagram-stalking",
])

# --- 4. Self-Harm ---
_add_merges("Self-Harm", [
    "self-harm", "Self-Harm Aftermath", "Self-Harm Scars",
    "self-harm-admission", "self-harm-disclosure",
    "self-harm-echo", "self-harm-history", "self-harm-memories",
    "self-harm-memory", "cutting",
])
_add_merges("Self-Harm Ideation", [
    "self-harm-ideation", "Self-Harm Ideation",
])

# --- 5. Body Image ---
_add_merges("Body Image", [
    "body-image", "body", "body-anxiety", "body-checking",
    "body-comparison", "body-discomfort", "body-comfort",
    "body-contentment", "body-nostalgia", "body-reduction",
    "body-shape", "body-weight", "body hatred", "body-hatred",
])
_add_merges("Body Dysphoria", [
    "body-dysphoria", "body dysphoria", "body-dysmorphia",
])
_add_merges("Body Change", [
    "body-change", "body-memory", "body-hair",
])
_add_merges("Body Horror", ["body-horror", "Body Horror"])
_add_merges("Body Betrayal", ["body-betrayal", "Body Betrayal"])

# --- 6. Academic ---
_add_merges("Academia", [
    "academia", "Academia", "academic-achievement",
    "academic-pressure", "academic-stress", "academic-work",
    "academic-ambition", "academic-doubt", "academic-failure",
    "academic-frustration", "academic-meetings",
    "academic-milestone", "academic-milestones", "academic-shame",
    "academic-struggle", "academic-writing", "academic-awards",
    "academic conference", "Academic Publishing",
    "Academic Submission", "Academic Jealousy",
    "Academic Rejection", "Academic Life",
])
_add_merges("Academic Anxiety", [
    "academic-anxiety", "Academic Anxiety", "academic avoidance",
    "Academic Avoidance", "academic paralysis",
])

# --- 7. Family ---
_add_merges("Family", [
    "family", "family anxiety", "family avoidance", "family chaos",
    "family contrast", "family crisis", "family dinner",
    "family encounter", "family estrangement",
    "family expectations", "family frustration", "family guilt",
    "family illness", "family love", "family obligations",
    "family outing", "family patterns", "family processing",
    "family rejection", "family reunion", "family silence",
    "family threat", "family witness", "family-acceptance",
    "family-blindness", "family-care", "family-concern",
    "family-cruelty", "family-death", "family-dinner",
    "family-disapproval", "family-disclosure", "family-distance",
    "family-dynamics", "family-event", "family-gathering",
    "family-household", "family-news", "family-obligation",
    "family-outing", "family-pain", "family-party",
    "family-perception", "family-pressure", "family-reactions",
    "family-secret", "family-secrets", "family-sexuality",
    "family-shopping", "family-silence", "family-warmth",
    "family-worry",
])
_add_merges("Family Conflict", [
    "family conflict", "family-conflict", "family tension",
    "family-tension",
])
_add_merges("Family Support", [
    "family support", "family-support", "family-therapy",
])
_add_merges("Family Visit", [
    "family-visit", "Family Visit",
])
_add_merges("Extended Family", [
    "extended-family", "Extended Family",
])

# --- 8. Disclosure ---
_add_merges("Disclosure", [
    "disclosure", "disclosure-accepted", "disclosure-aftermath",
    "disclosure-avoided", "disclosure-avoidance",
    "disclosure-contemplation", "disclosure-desire",
    "disclosure-draft", "disclosure-posted",
    "disclosure-postponed", "disclosure-practice",
    "disclosure-rehearsal", "disclosure-vs-stealth",
    "disclosure-weapon", "disclosure fear",
    "disclosure strategy", "disclosure threshold",
    "disclosure withheld", "non-disclosure", "not-disclosed",
    "partial-disclosure", "selective-coming-out",
    "Strategic Disclosure", "passive disclosure",
])
_add_merges("Disclosure Anxiety", [
    "disclosure-anxiety", "disclosure-fear",
    "disclosure-consideration", "disclosure-paralysis",
    "disclosure-planning",
])
_add_merges("Disclosure Fantasy", [
    "disclosure-fantasy",
])

# --- 9. HRT ---
_add_merges("HRT", [
    "HRT", "hrt", "HRT Access", "HRT dosage", "HRT evaluation",
    "HRT Failure", "HRT pause", "HRT progress",
    "hrt-anxiety", "hrt-countdown", "hrt-dosage", "HRT-dosage",
    "HRT-doses", "hrt-effect", "HRT-forgotten",
    "hrt-milestone", "HRT-milestone", "HRT-monitoring",
    "hrt-monitoring", "HRT-pharmacy", "HRT-report",
    "hrt-shortage", "HRT-supply", "change-without-HRT",
    "DIY HRT", "pre-HRT",
])
_add_merges("HRT Crisis", [
    "HRT Crisis", "HRT crisis",
])

# --- 10. Medication ---
_add_merges("Medication", [
    "medication", "medications", "medication effects",
    "Medication Side Effects", "medication-adjustment",
    "medication-anxiety", "medication-change",
    "medication-disclosure", "medication-disruption",
    "medication-doubt", "medication-mixing",
    "medication-refusal", "medication-side-effect",
    "medication-timing",
])
_add_merges("Medication Fog", [
    "medication-fog", "Medication Fog",
])

# --- 11. Sleep Issues ---
_add_merges("Insomnia", [
    "insomnia", "sleeplessness", "sleep-deprivation",
    "Sleep Deprivation", "sleepless-night", "staying-awake",
])
_add_merges("Sleep", [
    "sleep", "sleep-escape", "sleep-hygiene", "sleep-paralysis",
    "excessive sleep", "hypersomnia", "avoidance sleeping",
])
_add_merges("Sleeping Pills", ["sleeping-pills", "Sleeping Pills"])

# --- 12. Surveillance/Stalking ---
_add_merges("Surveillance", [
    "surveillance", "digital-surveillance",
    "social-media-surveillance", "surveillance loop",
    "border-surveillance",
])
_add_merges("Stalking", [
    "stalking", "digital-stalking", "facebook-stalking",
    "social media stalking", "geographic-stalking",
    "Cyber-stalking",
])

# --- 13. Crying ---
_add_merges("Crying", [
    "crying", "Crying", "tears", "sobbing",
    "Crying in Public", "crying-spot",
])

# --- 14. Departure ---
_add_merges("Departure", [
    "departure", "Departure", "farewell", "Farewell",
    "goodbye", "Goodbye", "leaving", "Airport Goodbye",
    "airport-goodbye", "Farewell Gift", "birthday-departure",
])

# --- 15. Rejection ---
_add_merges("Rejection", [
    "rejection", "Rejection", "rejection-anxiety",
    "rejection-fear", "rejection-guilt", "rejection-pattern",
    "rejection-processing", "rejection-sensitivity",
    "rejection-theory", "deliberate-rejection",
    "explicit-rejection", "multiple-rejections",
    "long-distance-rejection", "Soft Rejection",
    "polite-rejection", "digital-rejection",
])

# --- 16. Validation ---
_add_merges("Validation", [
    "validation", "AI Validation", "Digital Validation",
    "medical validation", "stranger validation",
    "stranger-validation", "gender validation",
    "private-validation", "social media validation",
    "validation-uncertainty", "validation-void",
])
_add_merges("Validation Seeking", [
    "validation-seeking", "Validation Seeking",
    "attention-seeking",
])

# --- 17. Anxiety ---
_add_merges("Anxiety", [
    "anxiety", "anxiety-metaphor", "anxiety-relief-cycle",
])

# --- 18. Depression ---
_add_merges("Depression", [
    "depression", "depression symptoms", "depression-history",
    "depression-mirroring", "depression-origin",
    "depressive-episode",
])

# --- 19. Avoidance ---
_add_merges("Avoidance", [
    "avoidance", "work-avoidance", "social-avoidance",
    "Digital Avoidance", "Emotional avoidance",
    "homework-avoidance", "writing-avoidance",
    "closure-avoidance",
])

# --- 20. Social Media ---
_add_merges("Social Media", [
    "social-media", "social-media-boundaries",
    "social-media-ritual", "social-media-stalking",
    "social media deletion", "social media obsession",
])

# --- 21. Photography ---
_add_merges("Photography", [
    "photography", "photograph", "photographs", "photos", "photo",
    "photo-archive", "photo-editing", "photo-shame", "pictures",
    "photography-failure", "Film Camera", "film-photography",
    "Film Scanning", "Film Scans", "Undeveloped Film",
    "Ruined Film", "medium-format", "Half-Frame",
    "Half-Frame Camera", "120mm camera", "Yashicaflex",
    "Kodak Gold", "Purple Film",
])
_add_merges("Self-Portrait", [
    "self-portrait", "Self-Portrait Series",
])

# --- 22. Passing ---
_add_merges("Passing", [
    "passing", "Passing", "passing-ambiguity", "passing-anxiety",
    "passing-comparison", "passing-guilt", "passing-loneliness",
    "passing-uncertainty",
])

# --- 23. Coming Out ---
_add_merges("Coming Out", [
    "coming-out", "coming out aftermath", "coming out plan",
    "coming out speech", "coming-out-aftermath",
    "coming-out-fantasy", "coming-out-fear",
    "coming-out-planning", "coming-out-script",
    "coming-out-speech", "near-coming-out",
])

# --- 24. Loneliness ---
_add_merges("Loneliness", [
    "loneliness", "alone", "deserved-isolation", "never-alone",
])

# --- 25. Obsession ---
_add_merges("Obsession", [
    "obsession", "Obsession vs Love", "obsession-awareness",
    "obsession-management", "obsessive-attachment",
    "obsessive-checking", "obsessive-cycling",
    "obsessive-fixation", "obsessive-patterns",
    "obsessive-search", "obsessive-texting",
    "obsessive-thinking", "obsessive interpretation",
    "Cycle of Obsession", "digital-obsession", "fixation",
    "fixation-awareness", "fixation-genealogy",
])

# --- 26. Ghosting ---
_add_merges("Ghosting", [
    "ghosting", "Ghosted by Therapist", "ghosted",
    "ghosting-aftermath", "ghosting-anxiety",
])

# --- 27. Isolation ---
_add_merges("Isolation", [
    "isolation", "pre-emptive isolation", "weekend-isolation",
])

# --- 28. Therapy ---
_add_merges("Therapy", [
    "therapy", "therapy doubt", "therapy need", "Therapy Speak",
    "therapy-booked", "therapy-countdown", "therapy-dread",
    "therapy-end", "therapy-ending", "therapy-memory",
    "therapy-prep", "therapy-preparation", "therapy-referral",
    "therapy-scheduled", "therapy-seeking", "therapy-session",
    "therapy-support", "therapy-waiting", "missed-therapy",
    "therapist affirmation", "therapist-session",
])

# --- 29. Dissociation ---
_add_merges("Dissociation", [
    "dissociation", "depersonalization", "numbness", "Numbness",
    "emotional-numbness",
])

# --- 30. Procrastination ---
_add_merges("Procrastination", [
    "procrastination", "unproductivity", "inactivity",
])

# ===========================================================================
# Additional merges — broader audit pass
# ===========================================================================

# --- 31. Abandonment ---
_add_merges("Abandonment", [
    "abandonment", "abandonment patterns", "abandonment-fear",
])

# --- 32. Acceptance ---
_add_merges("Acceptance", [
    "acceptance", "acceptance anxiety", "acceptance-numbness",
])

# --- 33. AI ---
_add_merges("AI", [
    "ai-generated", "AI dialogue", "ai-advice", "ai-consultation",
    "AI-Assisted Introspection",
])

# --- 34. App (dating-adjacent) ---
_add_merges("Dating App", [
    "app-deletion", "App Deletion", "app-addiction", "app-checking",
    "app-cycling", "app-deleted", "app-fatigue", "app-reinstall",
])

# --- 35. Application ---
_add_merges("Application", [
    "application", "application anxiety", "application deadline",
])

# --- 36. Archive ---
_add_merges("Archive", [
    "archive-completion", "archive-purge", "archive-review",
    "archive-work",
])

# --- 37. Attachment ---
_add_merges("Attachment", [
    "attachment anxiety", "attachment wounds", "attachment-anxiety",
    "attachment-paradox", "attachment-patterns", "attachment-styles",
    "attachment-wounds",
])

# --- 38. Bathroom ---
_add_merges("Bathroom", [
    "bathroom", "bathroom anxiety", "bathroom-dilemma",
    "bathroom-dreams", "bathroom-law", "bathroom-trauma",
])

# --- 39. Birthday ---
_add_merges("Birthday", [
    "birthday", "Birthday Dinner", "Birthday Party",
    "birthday-forgotten",
])

# --- 40. Blood Test ---
_add_merges("Blood Test", [
    "blood-test", "blood-draw", "blood-work",
])

# --- 41. Border ---
_add_merges("Border", [
    "border", "border anxiety", "border-ambivalence",
    "border-crossing", "border-opening", "border-region",
    "cross-border", "cross-border-trip",
])

# --- 42. Boundary ---
_add_merges("Boundary", [
    "boundary-violation", "boundary-crossing", "boundary-setting",
    "boundary-anxiety",
])

# --- 43. Breakup ---
_add_merges("Breakup", [
    "breakup", "Breakup Text", "breakup thoughts",
    "breakup-adjacent", "breakup-aftermath", "breakup-fear",
    "breakup-grief",
])

# --- 44. Breast ---
_add_merges("Breast", [
    "breast-development", "breast growth", "breast pain",
    "breast sensitivity", "breast-dysphoria",
])

# --- 45. Broken Promises ---
_add_merges("Broken Promises", [
    "broken-promises", "broken",
    "broken promise", "broken-commitment",
])

# --- 46. Cancelled Plans ---
_add_merges("Cancelled Plans", [
    "cancelled-plans", "Cancelled Plans", "cancelled",
    "cancelled plans",
])

# --- 47. Childhood ---
_add_merges("Childhood", [
    "childhood", "Childhood Trauma", "childhood confusion",
    "childhood dreams", "childhood fears", "childhood infatuation",
    "childhood patterns", "childhood-abandonment", "childhood-fear",
    "childhood-grief", "childhood-memories", "childhood-memory",
    "childhood-nostalgia", "childhood-photos", "childhood-trauma",
])

# --- 48. Christmas ---
_add_merges("Christmas", [
    "christmas", "Christmas shopping", "Christmas-party",
    "christmas-metaphor", "christmas-party", "christmas-trip",
])

# --- 49. Clothes ---
_add_merges("Clothes", [
    "clothes", "Clothes", "Clothes Swap", "clothes as memory",
    "clothes crisis", "clothes-fitting", "clothing",
    "clothing choice", "clothing choices",
])

# --- 50. Closure ---
_add_merges("Closure", [
    "closure", "Closure Fantasy", "closure-fantasy",
])

# --- 51. Conference ---
_add_merges("Conference", [
    "conference", "Conference Funding", "conference abstract",
    "conference-networking",
])

# --- 52. Confession ---
_add_merges("Confession", [
    "Confession", "confession", "confession drafts",
    "confession-booth",
])

# --- 53. Costume ---
_add_merges("Costume", [
    "costume", "costume anxiety", "costume-anxiety",
    "costume-crisis", "costume-party",
])

# --- 54. COVID ---
_add_merges("COVID", [
    "covid-scare", "COVID-test", "covid-anxiety", "covid-era",
])

# --- 55. Date ---
_add_merges("Date", [
    "date", "Date", "date night", "date-planning", "date-success",
])

# --- 56. Dating ---
_add_merges("Dating", [
    "dating", "dating-anxiety", "dating-exhaustion",
    "dating-failure", "dating-games", "dating-marathon",
    "dating-multiple", "dating-multiplicity", "dating-numbness",
    "dating-patterns", "dating-surveillance", "dating-uncertainty",
])

# --- 57. Deadline ---
_add_merges("Deadline", [
    "deadline", "Deadline", "deadline anxiety",
])

# --- 58. Death ---
_add_merges("Death", [
    "death", "Death", "Death & Rebirth", "death-ideation",
    "death-meditation",
])

# --- 59. Departure (extend) ---
_add_merges("Departure", [
    "departure-countdown", "departure date",
    "departure-preparation",
])

# --- 60. Digital ---
_add_merges("Digital", [
    "digital identity", "Digital Archive", "Digital Archiving",
    "Digital Breadcrumb", "Digital Deletion", "Digital Flirtation",
    "Digital Graveyard", "Digital Haunting", "Digital Intimacy",
    "Digital Obsession", "Digital Severance", "digital absence",
    "digital blocking", "digital communication", "digital exorcism",
    "digital-compulsion", "digital-courtship", "digital-deletion",
    "digital-erasure", "digital-overwhelm", "digital-presence",
])

# --- 61. Dog ---
_add_merges("Dog", [
    "dog", "Dog Reunion", "dog-care", "Aging Dog",
])

# --- 62. Domestic ---
_add_merges("Domestic", [
    "Domestic Anxiety", "Domestic Decay", "Domestic Intimacy",
    "Domestic Routine", "domestic partnership", "domestic-comfort",
    "domestic-fantasy", "domestic-intimacy", "domestic-joy",
    "domestic-routine", "domestic-tension",
])

# --- 63. Double Exposure ---
_add_merges("Double Exposure", [
    "Double Exposure", "double-exposure",
])

# --- 64. Double Text ---
_add_merges("Double Text", [
    "Double Text", "Double-text", "double-texting",
])

# --- 65. Dream ---
_add_merges("Dream", [
    "dream", "dream-anxiety", "dream-interpretation",
    "dream-reality",
])

# --- 66. Dress ---
_add_merges("Dress", [
    "dress", "Dress", "dress-code", "dress-photo",
])

# --- 67. Eating Disorder ---
_add_merges("Eating Disorder", [
    "eating-disorder", "Eating Disorder", "eating guilt",
    "eating-anxiety", "eating-patterns", "eating-to-feel",
    "binge-eating", "binge-fantasy",
])

# --- 68. Facebook ---
_add_merges("Facebook", [
    "facebook", "Facebook deletion", "facebook coming out",
    "facebook-stalking",
])

# --- 69. Father ---
_add_merges("Father", [
    "father", "father disclosure", "father distance",
    "father-engagement", "father-paralysis", "father-silence",
])

# --- 70. Fear ---
_add_merges("Fear", [
    "fear", "Fear of dissolution", "fear of rejection",
    "fear-of-acceptance", "fear-of-asking", "fear-of-failure",
    "fear-of-hope", "fear-of-rejection",
])

# --- 71. Feminine ---
_add_merges("Feminine", [
    "feminine-presentation", "feminine-pronoun",
    "feminine-language", "feminine-clothes", "feminine address",
    "feminine clothing", "feminine partner", "feminine skills",
    "feminine-clothing", "feminine-face", "feminine-feelings",
    "feminine-identity", "feminine-markers", "feminine-plural",
    "feminine-recognition", "feminine-underwear",
])

# --- 72. Financial Anxiety ---
_add_merges("Financial Anxiety", [
    "financial-anxiety", "financial anxiety",
    "financial dependence", "financial-crisis",
    "financial-dependence", "financial-stress",
])

# --- 73. First (keep meaningful sub-groups) ---
_add_merges("First Kiss", [
    "first-kiss",
])
_add_merges("First Date", [
    "first-date", "First Date Echo", "First Date Site",
    "first-date-memory", "first-dates",
])
_add_merges("First Time", [
    "first-time", "First Sex", "First Time", "first time",
    "first time femme",
])

# --- 74. Friends ---
_add_merges("Friends", [
    "friends", "Friends Confrontation", "friends-intervening",
    "friend advice", "friend group", "friend group dynamics",
    "friend requests", "friend-gathering",
    "friend-group", "friend-group-dynamics",
    "friend-intervention", "friend-request",
])

# --- 75. Friendship ---
_add_merges("Friendship", [
    "friendship", "Friendship Breakup", "Friendship Conflict",
    "Friendship vs Romance", "Friendship-zone",
    "friendship ending", "friendship intervention",
    "friendship loyalty", "friendship-dissolution",
    "friendship-dynamics", "friendship-end", "friendship-ending",
    "friendship-loss", "friendship-origin", "friendship-rupture",
])

# --- 76. Future ---
_add_merges("Future", [
    "future", "Future Anonymous Reader", "Future Retrospective",
    "Future Wife", "Future self", "future anxiety",
    "future plans", "future-anxiety", "future-lost",
    "future-planning", "future-plans", "future-self",
])

# --- 77. Gendered ---
_add_merges("Gendered", [
    "gendered-female", "gendered-correctly", "gendered-language",
    "Gendered Spaces", "gendered condescension",
    "gendered-failure", "gendered-friendships",
    "gendered-plurals", "gendered-reading", "gendered-spaces",
])

# --- 78. Gendering ---
_add_merges("Gendering", [
    "gendering", "gendering-slips", "gendering-surprise",
    "conditional-gendering",
])

# --- 79. Graduation ---
_add_merges("Graduation", [
    "graduation", "graduation limbo", "graduation party",
    "graduation-anxiety", "graduation-party", "graduation-ring",
    "graduation-speech", "graduation-trip",
])

# --- 80. Hormone ---
_add_merges("Hormone", [
    "hormone-level", "hormone dosage increase", "hormone rest",
    "hormone speculation", "hormone-effects", "hormone-levels",
])

# --- 81. Housing ---
_add_merges("Housing", [
    "housing", "housing-discrimination", "housing-instability",
    "housing-search",
])

# --- 82. Identity ---
_add_merges("Identity", [
    "identity", "identity claim", "identity crisis",
    "identity documents", "identity fragmentation",
    "identity limbo", "identity-constancy", "identity-crisis",
    "identity-distance", "identity-doubt", "identity-fracture",
    "identity-limbo", "identity-paradox", "identity-question",
    "identity-reversal", "identity-split",
])

# --- 83. Intimacy ---
_add_merges("Intimacy", [
    "intimacy", "intimacy-craving", "intimacy-longing",
])

# --- 84. Laser ---
_add_merges("Laser", [
    "laser", "laser-hair-removal", "laser-removal",
    "laser session", "laser-patches", "laser-sessions",
    "laser-treatment",
])

# --- 85. Manuscript ---
_add_merges("Manuscript", [
    "manuscript", "Manuscript Acceptance", "Manuscript Critique",
    "Manuscript Fragments", "manuscript-deadline",
    "manuscript-rejection", "manuscript-submission",
])

# --- 86. Memory ---
_add_merges("Memory", [
    "memory", "Memory Loss", "Memory Decay", "Memory Fog",
    "memory doubt", "memory-confusion", "memory-fog",
    "memory-loss",
])

# --- 87. Mirror ---
_add_merges("Mirror", [
    "mirror", "Mirror Spread", "mirror-hatred",
])

# --- 88. Name ---
_add_merges("Name", [
    "name", "Name Pronunciation", "name change", "name disclosure",
    "name dysphoria", "name mismatch", "name recognition",
    "name validation", "name-anxiety", "name-change",
    "name-claiming", "name-conflict", "name-defense",
    "name-dilemma", "name-origin", "name-reveal",
    "name-signing", "name-slippage", "name-spoken-aloud",
    "name-use", "name-without-body",
])

# --- 89. Party ---
_add_merges("Party", [
    "party", "party anxiety", "party dread", "party planning",
    "party preparation", "party revelation", "party-anxiety",
    "party-avoidance", "party-memory", "party-prep",
])

# --- 90. Pattern Recognition ---
_add_merges("Pattern Recognition", [
    "pattern-recognition", "pattern-catalog", "pattern-echo",
    "pattern-mirror", "pattern-origin", "pattern-seeking",
])

# --- 91. Pride ---
_add_merges("Pride", [
    "pride", "pride-parade", "pride-anniversary", "pride-photos",
])

# --- 92. Public Presentation ---
_add_merges("Public Presentation", [
    "public-presentation", "public presentation",
    "public-exposure", "Public Solitude", "public declaration",
    "public gendering", "public recognition", "public shame",
    "public-breakdown", "public-confession", "public-erasure",
    "public-gendering", "public-humiliation",
    "public-misgendering", "public-perception", "public-space",
    "public-vulnerability",
])

# --- 93. Queer ---
_add_merges("Queer", [
    "queer-community", "queer-recognition", "Queer Motherhood",
    "queer motherhood", "queer visibility", "queer-bar",
    "queer-cinema", "queer-club", "queer-friendship",
    "queer-party", "queer-spaces",
])

# --- 94. Romantic ---
_add_merges("Romantic", [
    "romantic-obsession", "romantic aftermath", "romantic failure",
    "romantic holiday", "romantic-ambivalence",
    "romantic-anticipation", "romantic-choice", "romantic-dread",
    "romantic-dream", "romantic-tension",
])

# --- 95. Sex ---
_add_merges("Sex", [
    "sex", "sex-dream", "Sex Dreams", "sex dream",
])

# --- 96. Sibling ---
_add_merges("Sibling", [
    "sibling", "sibling bond", "sibling distance",
    "sibling identity", "sibling parallel", "sibling rivalry",
    "sibling transition", "sibling worry", "sibling-awareness",
    "sibling-comparison", "sibling-discovery", "sibling-gender",
    "sibling-mirroring", "sibling-naming", "sibling-trans",
    "sibling-transition", "sibling-worry",
])

# --- 97. Social Anxiety ---
_add_merges("Social Anxiety", [
    "social-anxiety", "social anxiety", "social alienation",
    "social-acceptance", "social-anticipation",
    "social-code", "social-comfort", "social-correction",
    "social-death", "social-exclusion", "social-exhaustion",
    "social-exposure", "social-invisibility",
    "social-performance",
])

# --- 98. Spanish ---
_add_merges("Spanish", [
    "spanish", "Spanish song", "Spanish-grammar",
    "spanish-grammar",
])

# --- 99. Texting ---
_add_merges("Texting Anxiety", [
    "Texting Anxiety", "texting-anxiety",
])
_add_merges("Texting", [
    "texting", "texting regret",
])

# --- 100. Trans ---
_add_merges("Trans", [
    "trans", "trans child", "trans community", "trans disclosure",
    "trans hate media", "trans identification", "trans identity",
    "trans in youth", "trans jokes", "trans memory",
    "trans mortality", "trans murders", "trans news",
    "trans patient", "trans recognition", "trans rights",
    "trans terminology", "trans visibility", "trans vulnerability",
    "trans webcomics", "trans-acceptance-moment",
    "trans-anxiety", "trans-as-checklist", "trans-cinema",
    "trans-clinic", "trans-clocking", "trans-coding",
    "trans-comedy-awkwardness", "trans-community",
    "trans-dating", "trans-disclosure",
    "trans-disclosure-burden", "trans-discrimination",
    "trans-doubt", "trans-flag", "trans-forum",
    "trans-healthcare", "trans-identity",
    "trans-joy-rejection", "trans-lit", "trans-literature",
    "trans-media", "trans-mirror", "trans-mortality",
    "trans-narrative", "trans-pity-fear", "trans-rejection",
    "trans-representation", "trans-self-consciousness",
    "trans-self-disgust", "trans-sexuality", "trans-timelines",
    "trans-visibility", "trans-womanhood", "trans-academia",
])

# --- 101. Transition ---
_add_merges("Transition", [
    "transition", "transition judgment", "transition timeline",
    "transition-anniversary", "transition-as-death",
    "transition-blame", "transition-body",
    "transition-bureaucracy", "transition-complete",
    "transition-contemplation", "transition-fears",
    "transition-grief", "transition-milestone",
    "transition-progress", "transition-timeline",
    "transition-visibility",
])

# --- 102. Unsent ---
_add_merges("Unsent Message", [
    "unsent-letter", "Unsent Message", "unsent-confession",
    "unsent-message",
])

# --- 103. Visibility ---
_add_merges("Visibility", [
    "visibility", "visibility-paradox", "visibility-hunger",
    "visibility anxiety", "visibility-paranoia",
])

# --- 104. Voice ---
_add_merges("Voice", [
    "voice", "voice-dysphoria", "voice-passing",
    "voice anxiety", "voice modulation", "voice-betrayal",
    "voice-clocking", "voice-materialization", "voice-test",
])

# --- 105. Waiting ---
_add_merges("Waiting", [
    "waiting", "waiting-for-messages", "waiting-for-reply",
    "waiting-for-text", "waiting-to-be-offered",
])

# --- 106. Wedding ---
_add_merges("Wedding", [
    "wedding", "wedding anxiety", "wedding-anxiety",
    "wedding-envy", "wedding-invitations", "wedding-memory",
    "wedding-prep", "wedding-preparation",
])

# --- 107. Weight ---
_add_merges("Weight", [
    "weight", "weight-loss", "weight-gain", "weight-anxiety",
    "weight-bet", "weight-cycling", "weight-disgust",
    "weight-tracking",
])

# --- 108. Work ---
_add_merges("Work", [
    "work", "Work Email", "work-break", "work-guilt",
    "work-meeting", "work-paralysis", "work-stress",
])

# --- 109. Workshop ---
_add_merges("Workshop", [
    "workshop", "workshop anxiety", "workshop planning",
    "workshop-cancellation",
])

# --- 110. Writing ---
_add_merges("Writing", [
    "writing", "Writing as Coping", "Writing as Survival",
    "writing block", "writing-as-coping", "writing-challenge",
    "writing-contest", "writing-milestone", "writing-practice",
    "writing-resistance", "writing-streak", "writers-block",
    "writer-block",
])

# --- 111. Self-* consolidation (beyond Self-Harm) ---
_add_merges("Self-Doubt", [
    "self-doubt", "self-questioning",
])
_add_merges("Self-Loathing", [
    "self-loathing", "self-hatred", "Self-Blame", "self-blame",
    "self-disgust", "self-reproach", "self-accusation",
    "self-condemnation", "self-attack", "self-criticism",
    "self-judgment",
])
_add_merges("Self-Sabotage", [
    "self-sabotage", "Self-sabotage", "Self-Destruction",
    "self-destruction", "Self-destruction", "self-destructive",
    "Self-Punishment", "self-punishment", "self-neglect",
    "self-starvation",
])
_add_merges("Self-Awareness", [
    "self-awareness", "self-perception", "self-recognition",
    "self-reflection", "self-scrutiny", "self-inventory",
])
_add_merges("Self-Image", [
    "self-image", "Self-Worth", "self-worth",
    "self-worth-crisis",
])
_add_merges("Self-Medication", [
    "self-medication", "Self-Medication",
])
_add_merges("Self-Acceptance", [
    "self-acceptance", "Self-Acceptance", "self-compassion",
    "Self-compassion", "self-forgiveness", "self-affirmation",
])
_add_merges("Self-Deception", [
    "Self-Deception", "self-denial", "self-censorship",
    "self-bargaining",
])

# --- 112. Deadnaming ---
_add_merges("Deadnaming", [
    "deadnaming", "deadname", "dead name", "dead-name",
    "Old Name", "old-name",
])

# --- 113. Misgendering ---
_add_merges("Misgendering", [
    "misgendering", "misgendered", "misgendering-anxiety",
    "misgendering-pain", "misgendering-reaction",
])

# --- 114. Pronoun ---
_add_merges("Pronoun", [
    "pronoun avoidance", "pronoun correction",
    "pronoun dysphoria", "pronoun-moment",
])

# --- 115. Sexual ---
_add_merges("Sexual", [
    "Sexual Assault", "Sexual Dysfunction", "Sexual Fantasy",
    "Sexual History", "Sexual aggression", "sexual changes",
    "sexual dysfunction", "sexual intimacy",
    "sexual-anticipation", "sexual-identity-questioning",
    "sexual-intimacy", "sexual-trauma",
])

# --- 116. Year End ---
_add_merges("Year End", [
    "year end", "year-end", "year-ending", "year review",
])


# ===========================================================================
# Additional merges from agent semantic analysis (1-2 use tags)
# ===========================================================================

# Load decisions from tag_decisions.json
import json
DECISIONS_FILE = PROJECT_ROOT / "scripts" / "tag_decisions.json"
if DECISIONS_FILE.exists():
    with open(DECISIONS_FILE, encoding="utf-8") as f:
        TAG_DECISIONS = json.load(f)

    # Add all MERGE decisions to SEMANTIC_MERGES
    for tag, decision in TAG_DECISIONS.items():
        if decision["action"] == "MERGE":
            SEMANTIC_MERGES[tag] = decision["target"]

    # Track DELETE decisions for reporting
    DELETED_TAGS = {tag for tag, decision in TAG_DECISIONS.items() if decision["action"] == "DELETE"}
else:
    TAG_DECISIONS = {}
    DELETED_TAGS = set()


# ===========================================================================
# Title-case conversion
# ===========================================================================

def has_meaningful_hyphen(word_lower: str) -> bool:
    """
    Check if a lowercased word contains a meaningful hyphen.

    Meaningful hyphens are those in compound words where the hyphen
    is part of the word's identity (e.g., self-harm, pre-transition).

    Args:
        word_lower: Lowercased word to check

    Returns:
        True if the word has a meaningful hyphen
    """
    for prefix in MEANINGFUL_PREFIXES:
        if word_lower.startswith(prefix) and len(word_lower) > len(prefix):
            return True
    for suffix in MEANINGFUL_SUFFIXES:
        if word_lower.endswith(suffix) and len(word_lower) > len(suffix):
            return True
    return False


def title_case_word(word: str) -> str:
    """
    Apply title case to a single word, respecting acronyms and special cases.

    Args:
        word: Word to capitalize

    Returns:
        Title-cased word, uppercase for acronyms, or special casing
    """
    lower = word.lower()

    if lower in ACRONYMS:
        return word.upper()

    if lower in SPECIAL_CASE:
        return SPECIAL_CASE[lower]

    # Handle apostrophes: Father's → Father's
    if "'" in word:
        parts = word.split("'")
        return "'".join(p.capitalize() for p in parts)

    return word.capitalize()


def title_case_tag(tag: str) -> str:
    """
    Convert a tag to Title Case following project rules.

    Rules:
        - Split on spaces first (already-spaced tags)
        - For hyphenated parts, check if hyphens are meaningful
        - Structural hyphens become spaces
        - Meaningful hyphens are preserved

    Args:
        tag: Raw tag string

    Returns:
        Title-cased tag string
    """
    # Already has spaces — just title-case each word
    if " " in tag and "-" not in tag:
        return " ".join(title_case_word(w) for w in tag.split())

    # Process each space-separated token
    tokens = tag.split()
    result_tokens = []

    for token in tokens:
        if "-" not in token:
            result_tokens.append(title_case_word(token))
            continue

        # Token has hyphens — decide: meaningful or structural?
        token_lower = token.lower()

        if has_meaningful_hyphen(token_lower):
            # Preserve hyphens, title-case each part
            parts = token.split("-")
            result_tokens.append("-".join(title_case_word(p) for p in parts if p))
        else:
            # Structural hyphens → spaces, title-case each part
            parts = token.split("-")
            for p in parts:
                if p:
                    result_tokens.append(title_case_word(p))

    return " ".join(result_tokens)


def collect_all_tags() -> list[str]:
    """
    Collect all unique tags from YAML metadata files.

    Returns:
        Sorted list of unique tag strings
    """
    tags: Set[str] = set()
    for filepath in glob.glob(str(METADATA_DIR / "**" / "*.yaml"), recursive=True):
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and isinstance(data.get("tags"), list):
            tags.update(data["tags"])
    return sorted(tags)


def build_mapping(all_tags: list[str]) -> Dict[str, str]:
    """
    Build the complete old→new tag mapping.

    For each tag:
    1. If it's in DELETED_TAGS, map to empty string (will be filtered out)
    2. If it's in SEMANTIC_MERGES, use the canonical tag
    3. Otherwise, apply title_case_tag

    Only includes entries where old != new (actual changes).

    Args:
        all_tags: List of all unique tags

    Returns:
        Dictionary mapping old tag strings to new tag strings
    """
    mapping: Dict[str, str] = {}

    for tag in all_tags:
        # Handle deletions - map to empty string for filtering
        if tag in DELETED_TAGS:
            mapping[tag] = ""
        elif tag in SEMANTIC_MERGES:
            new_tag = SEMANTIC_MERGES[tag]
            if new_tag != tag:
                mapping[tag] = new_tag
        else:
            new_tag = title_case_tag(tag)
            # Only include if there's an actual change
            if new_tag != tag:
                mapping[tag] = new_tag

    return mapping


def main() -> None:
    """Build and write the tag mapping file."""
    print("Collecting all tags from YAML files...")
    all_tags = collect_all_tags()
    print(f"  Found {len(all_tags)} unique tags")

    print("Building mapping...")
    mapping = build_mapping(all_tags)
    print(f"  {len(mapping)} tags will be transformed")

    # Count semantic merges vs deletions vs title-case only
    deletion_count = sum(1 for v in mapping.values() if v == "")
    semantic_count = sum(1 for t, v in mapping.items() if v != "" and t in SEMANTIC_MERGES)
    titlecase_count = len(mapping) - deletion_count - semantic_count
    print(f"    Deletions: {deletion_count}")
    print(f"    Semantic merges: {semantic_count}")
    print(f"    Title-case only: {titlecase_count}")

    # Show how many unique canonical tags result
    all_new = set()
    for tag in all_tags:
        if tag in mapping:
            new_tag = mapping[tag]
            if new_tag != "":  # Skip deletions
                all_new.add(new_tag)
        else:
            all_new.add(tag)
    print(f"  Result: {len(all_new)} unique tags after consolidation")
    print(f"  Reduction: {len(all_tags)} → {len(all_new)} ({len(all_tags) - len(all_new)} eliminated, {(len(all_tags) - len(all_new)) / len(all_tags) * 100:.1f}%)")

    # Write mapping
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    print(f"  Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

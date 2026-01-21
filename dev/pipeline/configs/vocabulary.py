#!/usr/bin/env python3
"""
vocabulary.py
-------------
Consolidated vocabulary definitions for narrative analysis curation.

This module defines:
- MOTIFS: ~20 recurring narrative patterns for arc tracking
- TAGS: ~30 cross-entry categories for search/dashboards
- Mapping tables from raw data to consolidated vocabulary

These definitions are used by:
- dev/pipeline/curation.py for auto-assignment
- dev/wiki/ for rendering wiki pages
"""
from __future__ import annotations

from typing import Dict, List, Set


# =============================================================================
# MOTIFS (~20 recurring narrative patterns)
# =============================================================================

MOTIFS: Dict[str, str] = {
    "The Body": "Physical embodiment, dysphoria, transition changes, medical procedures",
    "Validation & Rejection": "Seeking/receiving approval, rejection experiences, ghosting",
    "Masks & Performance": "Presenting different selves, authenticity vs. facade, passing",
    "Waiting & Time": "Anticipation, time distortion, waiting for messages/events",
    "The Obsessive Loop": "Repetitive thoughts, checking behaviors, fixation patterns",
    "Ghosts & Palimpsests": "Past selves, layered memories, haunting presence of history",
    "Isolation": "Loneliness, social withdrawal, disconnection",
    "The Unreliable Narrator": "Self-deception, memory distortion, narrative uncertainty",
    "Digital Surveillance": "Social media monitoring, online stalking, digital traces",
    "Resurrection & Return": "Reconnecting with past people/places, revival of relationships",
    "Closure & Endings": "Finality, goodbyes, completing chapters",
    "Medicalization": "Medical system, prescriptions, clinical encounters",
    "Haunted Geography": "Places carrying emotional weight, location-based memories",
    "Threshold & Liminal Space": "In-between states, transitions, neither-here-nor-there",
    "Writing as Survival": "Journal as lifeline, documenting to exist",
    "Language & Silence": "Communication failures, things unsaid, linguistic barriers",
    "The Cavalry": "Support arriving, rescue figures, external help",
    "Substitution": "Replacement dynamics, transferring feelings to new people",
    "The Double": "Mirror images, doppelgangers, seeing self in others",
    "Disclosure & The Secret": "Coming out, revealing hidden truths, vulnerability",
    "Sex & Desire": "Sexual experiences, fantasy, physical intimacy",
}

# Mapping from raw "Thematic Arc" values to consolidated motifs
THEMATIC_ARC_TO_MOTIF: Dict[str, str] = {
    # Direct mappings
    "THE BODY": "The Body",
    "VALIDATION & REJECTION": "Validation & Rejection",
    "MASKS & PERFORMANCE": "Masks & Performance",
    "WAITING & TIME": "Waiting & Time",
    "THE OBSESSIVE LOOP": "The Obsessive Loop",
    "OBSESSIVE LOOP": "The Obsessive Loop",
    "GHOSTS & PALIMPSESTS": "Ghosts & Palimpsests",
    "ISOLATION": "Isolation",
    "THE UNRELIABLE NARRATOR": "The Unreliable Narrator",
    "DIGITAL SURVEILLANCE": "Digital Surveillance",
    "RESURRECTION & RETURN": "Resurrection & Return",
    "CLOSURE & ENDINGS": "Closure & Endings",
    "MEDICALIZATION": "Medicalization",
    "PASSING & VISIBILITY": "Masks & Performance",  # merge with MASKS
    "HAUNTED GEOGRAPHY": "Haunted Geography",
    "THRESHOLD & LIMINAL SPACE": "Threshold & Liminal Space",
    "WRITING AS SURVIVAL": "Writing as Survival",
    "LANGUAGE & SILENCE": "Language & Silence",
    "LANGUAGE & IDENTITY": "Language & Silence",
    "THE CAVALRY": "The Cavalry",
    "SUPPORT NETWORK": "The Cavalry",
    "SUBSTITUTION & REPLACEMENT": "Substitution",
    "THE DOUBLE/MIRRORING": "The Double",
    "DISCLOSURE & THE SECRET": "Disclosure & The Secret",
    "THE ARCHIVE/DOCUMENTATION": "Writing as Survival",  # merge
    "SEX & DESIRE": "Sex & Desire",
    "MOTHERHOOD/CHILDLESSNESS": "The Body",  # merge with body
    "BUREAUCRATIC TRAUMA": "Medicalization",  # merge
    # Tag categories that leaked into thematic arcs - ignore (return None)
    "DEPRESSION/GRIEF": None,
    "MENTAL HEALTH": None,
    "DYSPHORIA/BODY": None,
    "CRISIS/SUICIDALITY": None,
    "INTIMACY": None,
    "ANXIETY/PANIC": None,
    "OBSESSION/CONTROL": None,
    "ALCOHOL": None,
}


# =============================================================================
# TAGS (~30 cross-entry categories)
# =============================================================================

TAGS: Dict[str, str] = {
    "transition": "Gender transition process, milestones, changes",
    "identity": "Self-concept, who am I questions, becoming",
    "anxiety": "Anxiety experiences, panic, worry",
    "depression": "Depression, sadness, grief, loss",
    "romance": "Dating, relationships, love",
    "family": "Family relationships, dynamics",
    "dysphoria": "Body/gender dysphoria",
    "mental-health": "General mental health, wellbeing",
    "obsession": "Obsessive thoughts, fixation",
    "therapy": "Therapy sessions, therapeutic relationship",
    "academia": "Academic life, studies, research",
    "intimacy": "Emotional/physical closeness",
    "technology": "AI, apps, digital tools",
    "rejection": "Being rejected, ghosted, ignored",
    "messaging": "Texts, DMs, communication",
    "medication": "Prescriptions, dosing, side effects",
    "dating-apps": "Hinge, Tinder, app experiences",
    "isolation": "Loneliness, being alone",
    "physical-health": "Body health, illness, symptoms",
    "alcohol": "Drinking, sobriety, bars",
    "photography": "Photos, selfies, images",
    "crisis": "Suicidal ideation, emergency states",
    "sleep": "Insomnia, dreams, sleep patterns",
    "writing": "Journal, poetry, creative writing",
    "food": "Eating, diet, cooking",
    "sexuality": "Sexual experiences, desires",
    "media": "Film, TV, music consumption",
    "work": "Job, productivity, professional",
    "substances": "Smoking, drugs, cannabis",
    "immigration": "Visa, borders, legal status",
}

# Mapping from raw "Tag Category" values to consolidated tags
TAG_CATEGORY_TO_TAG: Dict[str, str] = {
    "Transition": "transition",
    "Identity": "identity",
    "Anxiety/Panic": "anxiety",
    "Depression/Grief": "depression",
    "Romance/Dating": "romance",
    "Family": "family",
    "Dysphoria/Body": "dysphoria",
    "Mental Health": "mental-health",
    "Obsession/Control": "obsession",
    "Therapy": "therapy",
    "Academia": "academia",
    "Intimacy": "intimacy",
    "AI/Technology": "technology",
    "Rejection/Ghosting": "rejection",
    "Messaging": "messaging",
    "Medication": "medication",
    "Dating Apps": "dating-apps",
    "Isolation": "isolation",
    "Physical Health": "physical-health",
    "Alcohol": "alcohol",
    "Photography": "photography",
    "Crisis/Suicidality": "crisis",
    "Sleep/Insomnia": "sleep",
    "Writing/Poetry": "writing",
    "Food/Diet": "food",
    "Sexual": "sexuality",
    "Film/TV": "media",
    "Work/Productivity": "work",
    "Smoking/Drugs": "substances",
    "Immigration/Visa": "immigration",
    # Merges
    "Literature": "media",
    "Music": "media",
    "Dreams/Dreaming": "sleep",
    "Mania/Bipolar": "mental-health",
    "Meta-narrative": "writing",
    "Friendship/Platonic": "romance",
    # Drops (low frequency, not useful)
    "Digital Surveillance": None,  # This is a motif, not a tag
    "Hygiene": None,
    "Shopping": None,
    "Tarot/Divination": None,
    "Relics/Objects": None,
    "Childhood": None,
    # Mistakes (these shouldn't be in tag categories)
    "Validation & Rejection": None,
    "Validation": None,
    "Closure & Endings": None,
    "Language & Silence": None,
    "Self-hatred": None,
    "Voice": None,
    "None applicable": None,
}


# =============================================================================
# PEOPLE NORMALIZATION
# =============================================================================

PEOPLE_ALIASES: Dict[str, str] = {
    "father": "Father",
    "mother": "Mother",
    "grandmother": "Grandmother",
    "Majo (Maria-Jose)": "Majo",
    "Majo (Maria)": "Majo",
    "M (Monica)": "Monica",
}


# =============================================================================
# LOCATIONS NORMALIZATION
# =============================================================================

LOCATION_ALIASES: Dict[str, str] = {
    "home": "Home",
    "Ciudad de Mexico": "Mexico City",
    "None": None,  # Drop
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def map_thematic_arc_to_motif(arc: str) -> str | None:
    """
    Map a raw thematic arc value to consolidated motif.

    Args:
        arc: Raw thematic arc string from analysis file

    Returns:
        Consolidated motif name, or None if should be dropped
    """
    return THEMATIC_ARC_TO_MOTIF.get(arc, arc.title())


def map_tag_category_to_tag(category: str) -> str | None:
    """
    Map a raw tag category value to consolidated tag.

    Args:
        category: Raw tag category string from analysis file

    Returns:
        Consolidated tag name, or None if should be dropped
    """
    return TAG_CATEGORY_TO_TAG.get(category)


def normalize_person(name: str) -> str:
    """
    Normalize a person name to canonical form.

    Args:
        name: Raw person name from analysis file

    Returns:
        Normalized person name
    """
    return PEOPLE_ALIASES.get(name, name)


def normalize_location(location: str) -> str | None:
    """
    Normalize a location name to canonical form.

    Args:
        location: Raw location name from analysis file

    Returns:
        Normalized location name, or None if should be dropped
    """
    return LOCATION_ALIASES.get(location, location)


def get_motifs_for_entry(thematic_arcs: List[str]) -> Set[str]:
    """
    Convert list of thematic arcs to set of consolidated motifs.

    Args:
        thematic_arcs: List of raw thematic arc strings

    Returns:
        Set of consolidated motif names
    """
    motifs = set()
    for arc in thematic_arcs:
        motif = map_thematic_arc_to_motif(arc)
        if motif:
            motifs.add(motif)
    return motifs


def get_tags_for_entry(tag_categories: List[str]) -> Set[str]:
    """
    Convert list of tag categories to set of consolidated tags.

    Args:
        tag_categories: List of raw tag category strings

    Returns:
        Set of consolidated tag names
    """
    tags = set()
    for cat in tag_categories:
        tag = map_tag_category_to_tag(cat)
        if tag:
            tags.add(tag)
    return tags

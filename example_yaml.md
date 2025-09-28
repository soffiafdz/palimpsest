---
# EXTREME CASE: Maximum complexity YAML header
# This represents the absolute fullest entry with every possible field populated
# Most entries will use <10% of these fields

date: 2024-03-15
word_count: 2847
reading_time: 11.2

# Core narrative metadata
epigraph: "In the depth of winter, I finally learned that within me there lay an invincible summer"
notes: |
  Breakthrough session with Dr. Martinez. Mom opened up about grandmother's
  death for the first time. Alice's wedding planning stress becoming major
  theme. This entry contains the poem I've been working on for months.

  Cross-reference: therapy notes 2024-03-12, Alice's email thread about venue.
  Technical note: Fixed encoding issues in original .txt export.

# People (mix of single names and hyphenated compound names)
people:
  - Mom
  - Alice
  - Dr-Martinez # Will become "Dr Martinez" in DB
  - María-José # Will become "María José" in DB
  - Anna-Lucia # Will become "Anna Lucia" in DB
  - "Sarah Thompson" # Full name preserved as-is
  - Jim # Single name
  - "Fr. O'Brien" # Complex name requiring quotes

# Geographic locations - intelligent hierarchical parsing
# Quoted = venues/specific places, Unquoted = cities/regions/countries
# Parser builds hierarchy context from left-to-right ordering
locations:
  - "Café Central" # Venue (will inherit city context)
  - "Retiro Park"
  - Madrid # City (establishes context for previous venues)
  - Spain # Country (establishes context for Madrid)
  - "Mom's kitchen" # Venue (will inherit next city context)
  - "Dr Martinez office"
  - Barcelona # New city context
  - "UCSD Campus" # Cross-border example starts here
  - "Las Americas Outlet"
  - San-Diego # City (hyphen converts to space)
  - CA # State/Province abbreviation
  - United-States # Country (hyphen converts to space)
  - "Mercado Hidalgo" # Venue in new country context
  - "Tía Rosa's house"
  - Tijuana # City
  - BC # State/Province (Baja California)
  - México # Country

# Referenced dates in the text (not the entry date)
dates:
  - date: "2024-03-12"
    context: "therapy session"
  - date: "2024-03-10"
    context: "Mom's phone call"
  - date: "2024-02-28"
    context: "grandmother's death anniversary"
  - date: "2024-06-15"
    context: "Alice's wedding date"
  - "1987-11-23" # Simple format (no context)

# Cross-references to other journal entries
related_entries: ["2024-03-10", "2024-02-28", "2024-01-15"]

# Major narrative events/themes
events:
  - therapy-breakthrough
  - alice-wedding-planning
  - madrid-trip-2024
  - family-grief-processing
  - mom-opening-up

# Simple tags for categorization
tags:
  - family
  - therapy
  - breakthrough
  - grief
  - travel
  - poetry
  - healing
  - mother-daughter
  - wedding-stress
  - madrid

# External references (books, movies, therapy concepts, etc.)
references:
  # Simple quote with speaker
  - content: "Grief is the price we pay for love"
    speaker: "Dr Martinez"

  # Book reference with full source info
  - content: "The wound is the place where the Light enters you"
    source:
      title: "The Essential Rumi"
      author: "Rumi"
      type: book

  # Therapy session reference
  - content: "Your mother's silence was her way of protecting you"
    speaker: "Dr Martinez"
    context: "Session on family dynamics"

  # Movie/cultural reference
  - content: "Nobody puts Baby in a corner"
    source:
      title: "Dirty Dancing"
      type: movie

  # Article/web reference
  - content: "Wedding planning is the second most stressful life event"
    source:
      title: "Psychology Today Wedding Stress Article"
      type: article
      url: "https://psychologytoday.com/..."

# Original poems written in this entry
poems:
  # First poem - complete
  - title: "Letter to Grandmother"
    notes: "Final version - ready to submit to literary magazine"
    content: |
      Your silence taught me
      that some sorrows are too deep
      for words—

      but today Mom spoke your name
      and the room filled
      with your jasmine perfume,

      twenty years after
      we buried you
      in the Madrid clay.

  # Second poem - work in progress
  - title: "Wedding Dress Blues"
    notes: "Draft only - needs work, maybe too dark for Alice's big day"
    content: |
      Alice tries on white
      while I count the ways
      I've failed at love—

      (unfinished)

# Manuscript metadata (only for entries being considered for book)
manuscript:
  status: reviewed # draft|reviewed|included|excluded|final
  edited: true # Content has been edited for publication

  # Thematic categorization for book organization
  themes:
    - family-healing
    - mother-daughter-relationship
    - grief-processing
    - therapy-breakthroughs
    - cultural-identity
    - madrid-memories

  # Editorial notes for manuscript development
  notes: |
    STRONG piece for Chapter 4: "Unlocking Family Secrets"

    The therapy breakthrough combined with Madrid setting creates perfect
    bridge between grief chapter and healing chapter. Poem "Letter to 
    Grandmother" is publication-ready.

    EDITING NOTES:
    - Anonymize Dr Martinez → "my therapist" 
    - Check with Alice about wedding details (sensitivity)
    - Consider splitting into two entries? Very long.
    - Poem #2 either finish or remove - doesn't add value as-is

    LEGAL REVIEW:
    - Mom gave verbal consent for inclusion
    - Alice consent pending
    - Dr Martinez: therapy content OK if anonymized

    STATUS: Ready for final edit pass, pending family consents.
---

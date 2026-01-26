# Entity Curation Workflow for Phase 14b Jumpstart

## Overview

Before importing 972 narrative_analysis YAML files into the database, we need to extract and curate all people and locations to:
- Resolve typos and spelling variations
- Deduplicate entities (e.g., "María", "Maria", "@Majo" → one person)
- Handle ambiguous cases (multiple people with same name)
- Expand shorthand (e.g., "Alda's" → "Alda's apartment")
- Add missing metadata (lastnames, city assignments, date ranges)

This is a **one-time process** for the jumpstart. Once the database is populated and the ongoing pipeline is active, curation happens through the wiki interface.

---

## Workflow Stages

### Stage 1: Auto-Extraction

```bash
python -m dev.bin.extract_entities
```

**What it does:**
- Scans `data/narrative_analysis/**/*.yaml` for all people and location mentions
- Parses using existing heuristics (see below)
- Groups similar names automatically
- Generates draft curation files with context for review

**Output:**
- `data/curation/people_curation_draft.yaml`
- `data/curation/locations_curation_draft.yaml`

---

### Stage 2: Manual Curation

You edit the draft files to:
- Confirm or split auto-detected groups
- Fill in canonical forms (names, lastnames, aliases)
- Handle ambiguous cases (same name, different people)
- Assign cities to locations
- Add date ranges for context-dependent mappings

**Output:**
- `data/curation/people_curation.yaml` (final)
- `data/curation/locations_curation.yaml` (final)

---

### Stage 3: Validation

```bash
python -m dev.bin.validate_curation
```

**What it checks:**
- No duplicate canonical entries
- Required fields present (name for people, name+city for locations)
- Date ranges don't overlap for same name
- All members map to exactly one canonical

---

### Stage 4: Jumpstart Import

```bash
python -m dev.bin.jumpstart
```

**What it does:**
- Loads curated people → creates Person records in DB
- Loads curated locations → creates City + Location records
- Imports narrative_analysis YAMLs → creates Entry, Scene, Thread, etc.
- Resolves people/locations by matching against curation mappings

---

## People Extraction Logic

### Parsing Heuristics

When extracting a person mention like `"@Dr-Franck (Robert Franck)"`:

1. **@ prefix** → extract as `alias`
   - `"@Majo"` → `alias: "Majo"`

2. **Parenthetical (Full Name)** → parse as `name` + `lastname`
   - `"(Robert Franck)"` → `name: "Robert", lastname: "Franck"`

3. **Hyphen in first position** → dehyphenate multi-word first name
   - `"María-José"` → `name: "María José"`

4. **Everything after first word block** → `lastname`
   - `"Sofia Fajardo"` → `name: "Sofia", lastname: "Fajardo"`

**Example parsing:**

| Input | Parsed |
|-------|--------|
| `"@Majo"` | `{alias: "Majo", name: null, lastname: null}` |
| `"@Dr-Franck (Robert Franck)"` | `{alias: "Dr-Franck", name: "Robert", lastname: "Franck"}` |
| `"María-José"` | `{name: "María José", lastname: null}` |
| `"Sofia Fajardo Zuñiga"` | `{name: "Sofia", lastname: "Fajardo Zuñiga"}` |
| `"Fabiola"` | `{name: "Fabiola", lastname: null}` |

### Auto-Grouping Algorithm

The extraction script groups similar names to reduce manual work:

```python
def should_group(name1: str, name2: str) -> bool:
    """Two names should be grouped if ANY condition matches."""
    n1 = normalize(name1)  # lowercase, strip @, remove punctuation
    n2 = normalize(name2)

    # Exact match after normalization
    if n1 == n2:
        return True

    # Levenshtein distance ≤ 2 (handles typos)
    if levenshtein_distance(n1, n2) <= 2:
        return True

    # Substring match
    if n1 in n2 or n2 in n1:
        return True

    # Same first 3 characters (nicknames)
    if len(n1) >= 3 and len(n2) >= 3 and n1[:3] == n2[:3]:
        return True

    return False
```

**Example groups:**
- `["@Majo", "Maria", "María", "María-José"]` → Levenshtein + first-3-chars
- `["Dr-Franck", "Dr. Franck", "Dr Franck"]` → substring match
- `["Fabiola"]` → no similar names, single member

---

## People Draft File Format

```yaml
# data/curation/people_curation_draft.yaml

groups:
  # Group with multiple variations (needs review)
  - id: 1
    members:
      - name: "@Majo"
        occurrences:
          - {date: "2024-11-08", scene: "First Date at Kafé"}
          - {date: "2024-11-15", scene: "Texting After Dark"}
          - {date: "2024-12-03", scene: "The Money Fight"}
        total_count: 45
      - name: "Maria"
        occurrences:
          - {date: "2024-11-12", scene: "Coffee Thoughts"}
        total_count: 3
      - name: "María"
        occurrences:
          - {date: "2024-11-10", scene: "Morning Text"}
          - {date: "2024-11-20", scene: "The Kiss at Jarry"}
        total_count: 8
      - name: "María-José"
        occurrences:
          - {date: "2024-11-09", scene: "Remembering Childhood"}
        total_count: 12
    # MANUAL: Confirm this is one person, or split if multiple
    canonical: null

  # Unambiguous single name (pre-filled)
  - id: 2
    members:
      - name: "Fabiola"
        occurrences:
          - {date: "2024-08-15", scene: "Lunch at Work"}
          - {date: "2024-09-22", scene: "Weekend Coffee"}
        total_count: 67
    # MANUAL: Review and confirm
    canonical:
      name: Fabiola
      lastname: null
      alias: null

  # Ambiguous case: same name, potentially different people
  - id: 3
    members:
      - name: "Melissa"
        occurrences:
          - {date: "2024-11-08", scene: "Coffee at Starbucks"}
          - {date: "2024-11-15", scene: "Family Dinner"}
          - {date: "2024-11-20", scene: "The Apartment Tour"}
          - {date: "2024-12-01", scene: "Christmas Shopping"}
        total_count: 100
    # MANUAL: Review occurrences - might be multiple people
    canonical: null
```

---

## Manual Curation Operations

### Operation 1: Confirm a Group

If the auto-grouping is correct (all variations refer to one person):

```yaml
# Before:
- id: 1
  members:
    - name: "@Majo"
      occurrences: [...]
      total_count: 45
    - name: "Maria"
      occurrences: [...]
      total_count: 3
  canonical: null

# After:
- id: 1
  members: ["@Majo", "Maria", "María", "María-José"]
  canonical:
    name: María José
    lastname: null
    alias: Majo
```

**Actions:**
1. Simplify `members` to just name strings (remove occurrences/count)
2. Fill `canonical` with correct form
3. Choose most common spelling or preferred form

---

### Operation 2: Split a Group

If the auto-grouping merged different people:

```yaml
# Before:
- id: 3
  members:
    - name: "Melissa"
      occurrences:
        - {date: "2024-11-08", scene: "Coffee at Starbucks"}
        - {date: "2024-11-15", scene: "Family Dinner"}
        - {date: "2024-11-20", scene: "The Apartment Tour"}
        - {date: "2024-12-01", scene: "Christmas Shopping"}
      total_count: 100
  canonical: null

# After: Split into two people
- id: 3a
  members: ["Melissa"]
  canonical:
    name: Melissa
    lastname: null  # Sister
    alias: null
  date_ranges: ["2024-11-15", "2024-12-01"]  # Family contexts

- id: 3b
  members: ["Melissa"]
  canonical:
    name: Melissa
    lastname: Díaz  # Friend
    alias: null
  date_ranges: ["2024-11-08", "2024-11-20"]  # Non-family contexts
```

**Actions:**
1. Create new group IDs (3a, 3b)
2. Add `date_ranges` listing which dates map to which person
3. Use lastname or alias to distinguish in canonical form

**Importer behavior:**
- Scene dated 2024-11-15 with "Melissa" → links to Person(name="Melissa", lastname=null)
- Scene dated 2024-11-08 with "Melissa" → links to Person(name="Melissa", lastname="Díaz")

---

### Operation 3: Merge Groups

If the auto-grouping split what should be one person:

```yaml
# Before: Two separate groups
- id: 5
  members: ["Dr-Franck"]
  canonical: null

- id: 6
  members: ["Robert"]
  canonical: null

# After: Merged into one
- id: 5
  members: ["Dr-Franck", "Robert", "Dr. Franck"]
  canonical:
    name: Robert
    lastname: Franck
    alias: Dr-Franck
```

**Actions:**
1. Delete one group
2. Add its members to the other group
3. Fill canonical form

---

## People Final Format

After curation, simplify to this format:

```yaml
# data/curation/people_curation.yaml

- members: ["@Majo", "Maria", "María", "María-José"]
  canonical:
    name: María José
    lastname: null
    alias: Majo

- members: ["Fabiola"]
  canonical:
    name: Fabiola
    lastname: null
    alias: null

- members: ["@Dr-Franck (Robert Franck)", "Dr. Franck", "Robert"]
  canonical:
    name: Robert
    lastname: Franck
    alias: Dr-Franck

# Disambiguated entries (same name, different people)
- members: ["Melissa"]
  canonical:
    name: Melissa
    lastname: null
    alias: null
  date_ranges: ["2024-11-15", "2024-12-01"]

- members: ["Melissa"]
  canonical:
    name: Melissa
    lastname: Díaz
    alias: null
  date_ranges: ["2024-11-08", "2024-11-20"]
```

**Field rules:**
- `members`: List of ALL variations/spellings from source files
- `canonical.name`: Required, preferred spelling
- `canonical.lastname`: Optional, defaults to "Doe" in DB if null
- `canonical.alias`: Optional, nickname/short form
- `date_ranges`: Optional, only for disambiguation (same name, different people)

---

## Locations Extraction Logic

### Auto-Extraction

For each location mention in narrative_analysis YAMLs:
1. Extract raw location string
2. Attempt to infer city from entry's MD frontmatter `city:` field
3. Group by city

### Hierarchical City Structure

```yaml
# data/curation/locations_curation_draft.yaml

cities:
  Montréal:
    locations:
      - name: "Home"
        occurrences:
          - {date: "2015-08-18"}
          - {date: "2024-12-03"}
        total_count: 156
        # NEEDS REVIEW: Spans 2015-2024, likely multiple residences

      - name: "Alda's"
        occurrences:
          - {date: "2024-11-10"}
          - {date: "2024-11-15"}
        total_count: 12
        # MANUAL: Expand to "Alda's apartment"?

      - name: "The Neuro"
        occurrences:
          - {date: "2024-09-15"}
          - {date: "2024-12-03"}
        total_count: 28

  Tijuana:
    locations:
      - name: "Home"
        occurrences:
          - {date: "2018-12-24"}
          - {date: "2019-01-05"}
        total_count: 15
```

---

## Location Curation Operations

### Operation 1: Expand Shorthand

```yaml
# Before:
Montréal:
  locations:
    - name: "Alda's"
      occurrences: [...]
      total_count: 12

# After:
Montréal:
  - name: "Alda's apartment"
    variations: ["Alda's", "Aldas"]
```

---

### Operation 2: Date-Based Resolution

For ambiguous locations like "Home" that span multiple residences:

```yaml
# Before:
Montréal:
  locations:
    - name: "Home"
      occurrences:
        - {date: "2015-08-18"}
        - {date: "2023-05-30"}
        - {date: "2024-12-03"}
      total_count: 156

# After: Split by date range
Montréal:
  - name: "Jarry's apartment"
    variations: ["Home", "home", "apartment"]
    date_range: ["2023-06-01", null]  # Summer 2023 onwards

  - name: "De Pins' apartment"
    variations: ["Home", "home", "apartment"]
    date_range: [null, "2023-05-31"]  # Before Summer 2023
```

**Importer behavior:**
- Scene dated 2024-12-03 with "Home" in Montréal → "Jarry's apartment"
- Scene dated 2022-10-15 with "Home" in Montréal → "De Pins' apartment"

---

### Operation 3: City-Specific Disambiguation

```yaml
Montréal:
  - name: "Parents' house"
    variations: ["Home"]
    # No date_range needed, city differentiates

Tijuana:
  - name: "Parents' house"
    variations: ["Home", "casa"]
    # Same canonical name, different city
```

---

## Locations Final Format

```yaml
# data/curation/locations_curation.yaml

cities:
  Montréal:
    - name: The Neuro
      variations: ["Neuro", "the neuro", "The Neuro"]

    - name: Jarry's apartment
      variations: ["Home", "home", "apartment"]
      date_range: ["2023-06-01", null]

    - name: De Pins' apartment
      variations: ["Home", "home", "apartment"]
      date_range: [null, "2023-05-31"]

    - name: Station Jarry
      variations: ["Jarry station", "station Jarry", "Station Jarry"]

    - name: Alda's apartment
      variations: ["Alda's", "Aldas"]

  Tijuana:
    - name: Parents' house
      variations: ["Home", "home", "casa"]

  México:
    - name: Sonny's house
      variations: ["Sonny's", "Sonnys"]
```

**Field rules:**
- `name`: Required, canonical form
- `variations`: List of ALL spellings from source files
- `date_range`: Optional, `[start, end]` where `null` = unbounded
  - `[null, "2023-05-31"]` = before/until May 31, 2023
  - `["2023-06-01", null]` = from June 1, 2023 onwards

---

## Validation Script

```bash
python -m dev.bin.validate_curation
```

**Checks performed:**

### People validation:
- ✓ All members map to exactly one canonical
- ✓ No duplicate canonical entries (same name+lastname+alias)
- ✓ Date ranges don't overlap for same name
- ✓ Required field `name` present in all canonical entries
- ✓ `date_ranges` only used when needed (multiple people, same name)

### Locations validation:
- ✓ All locations have city assigned
- ✓ All variations map to exactly one canonical
- ✓ Date ranges don't overlap for same variations in same city
- ✓ Required field `name` present in all locations

---

## Jumpstart Import Behavior

Once curation is validated, the jumpstart script:

### People Import:
1. Read `people_curation.yaml`
2. Create Person records:
   ```python
   Person(
       name=canonical.name,
       lastname=canonical.lastname or "Doe",  # Default
       alias=canonical.alias
   )
   ```
3. Build reverse mapping: `{"@Majo": person_id, "Maria": person_id, ...}`

### Locations Import:
1. Read `locations_curation.yaml`
2. Create City records for each city
3. Create Location records:
   ```python
   Location(
       name=canonical.name,
       city_id=city.id
   )
   ```
4. Build reverse mapping: `{"Home": [(location_id, date_range), ...]}`

### Entry Import:
1. Read narrative_analysis YAML
2. For each scene with people:
   ```python
   for person_str in scene.people:
       person_id = resolve_person(person_str, entry.date)
       scene.people.append(person_id)
   ```
3. For each scene with locations:
   ```python
   for loc_str in scene.locations:
       location_id = resolve_location(loc_str, entry.city, entry.date)
       scene.locations.append(location_id)
   ```

**Resolution logic:**
- Check curation mapping for variation → canonical
- If `date_ranges` exist, verify entry date falls within range
- Link to matching Person/Location record

---

## Curation Tips

### For People:
- **Start with high-count groups** (100+ mentions) - highest impact
- **Check family names** - often have no lastname, easy to confuse
- **Look for nickname patterns** - "@" prefix usually indicates nickname/alias
- **Date context helps** - family events vs friend events differ

### For Locations:
- **"Home" always needs splitting** - residences change over time
- **Possessives need expansion** - "Alda's" → "Alda's apartment"
- **Generic names need specificity** - "Coffee shop" → actual name if known
- **City inference usually correct** - review, but rarely wrong

### Time estimates:
- **Extraction**: ~2 minutes (automated)
- **People curation**: ~2-4 hours (reviewing ~200-300 unique people)
- **Locations curation**: ~30-60 minutes (reviewing ~100-150 locations)
- **Validation**: ~30 seconds (automated)
- **Import**: ~5-10 minutes (972 entries)

**Total: ~3-5 hours of manual work for one-time jumpstart**

---

## Troubleshooting

### "Multiple canonicals match"
**Problem:** Two entries have same name+lastname+alias
**Solution:** One must have different lastname or alias to distinguish

### "Date ranges overlap"
**Problem:** Two entries for "Melissa" have overlapping date_ranges
**Solution:** Adjust ranges so they don't overlap, or merge into one person

### "Variation maps to multiple canonicals"
**Problem:** "María" appears in two different groups
**Solution:** Remove from one group (typo), or split properly with date_ranges

### "Missing city for location"
**Problem:** Location extracted but no city assigned
**Solution:** Add location to appropriate city block in locations_curation.yaml

---

## Next Steps After Curation

1. Validate curation files
2. Run jumpstart import
3. Verify database populated correctly (count checks)
4. Export to new YAML format for git backup
5. Delete `data/narrative_analysis/` and `data/legacy/` (no longer needed)
6. Begin using wiki interface for ongoing curation

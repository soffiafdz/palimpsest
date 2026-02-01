# Import Logic Audit - Comprehensive Review

**Date:** 2026-02-01
**Issue:** Import creates duplicate Person records instead of using metadata YAML definitions

## Design Requirements

### Data Sources (Correct Architecture)

**Metadata YAML** (`data/metadata/journal/YYYY/YYYY-MM-DD.yaml`):
- **Ground truth for people definitions** (with lastname, disambiguator, aliases)
- Ground truth for narrative analysis (scenes, events, threads, arcs, etc.)
- Scene-level people/locations/dates (subsets of entry-level)

**MD Frontmatter** (`data/journal/content/md/YYYY/YYYY-MM-DD.md`):
- Entry-level people list (full set, names only for convenience)
- Entry-level locations dict (full set, organized by city)
- Entry-level narrated_dates (full set)
- Basic metadata (date, word_count, reading_time)

### Subset Logic Requirements

1. **Scene people ⊆ Entry people** - All people in scenes must be in entry people list
2. **Scene locations ⊆ Entry locations** - All locations in scenes must be in entry locations
3. **Scene dates ⊆ Entry narrated_dates** - All scene dates must be in entry narrated_dates

### Person Resolution Priority

1. **Primary source**: Metadata YAML `people:` section (has lastname/disambiguator/alias)
2. **Secondary source**: MD frontmatter `people:` list (names only, for matching)
3. **Resolution**: Match MD frontmatter names against metadata YAML person definitions

## Current Implementation Analysis

### File: `dev/pipeline/metadata_importer.py`

#### Import Flow (Lines 200-320)

```python
def _import_file(self, yaml_path: Path) -> None:
    # 1. Load metadata YAML
    metadata = self._load_yaml(yaml_path)

    # 2. Load MD frontmatter
    md_path = self._get_md_path(yaml_path)
    md_frontmatter = self._load_md_frontmatter(md_path)

    # 3. Create/update Entry
    entry = self._create_or_update_entry(metadata, md_frontmatter)

    # 4. Link entry-level people FROM MD FRONTMATTER ❌ BUG
    self._link_entry_people(entry, md_frontmatter)

    # 5. Link entry-level locations FROM MD FRONTMATTER ✓
    self._link_entry_locations(entry, md_frontmatter)

    # 6. Create scenes with people FROM METADATA YAML ✓
    self._create_scenes(entry, metadata)
```

**Issue**: Step 4 uses MD frontmatter for people (names only), not metadata YAML (full data).

#### Line 404-423: `_link_entry_people()`

```python
def _link_entry_people(self, entry: Entry, md_frontmatter: Dict[str, Any]) -> None:
    people_list = md_frontmatter.get("people", [])  # ❌ Names only, no lastname!

    for person_name in people_list:
        for person in self.resolver.resolve_people(str(person_name), self.session):
            if person not in entry.people:
                entry.people.append(person)
```

**Problem**:
- Uses `md_frontmatter.get("people")` which is `["Mónica", "Catherine", ...]`
- No lastname/disambiguator data
- Resolver can't match correctly

**Should be**:
- Use `metadata.get("people")` which is:
  ```yaml
  people:
    - name: Mónica
      lastname: González
    - name: Catherine
      alias: Calli
  ```

### File: `dev/pipeline/entity_resolver.py`

#### Lines 651-677: `resolve_people()`

```python
def resolve_people(self, raw_name: str, session: Session) -> List[Person]:
    lookup_key = raw_name.lower()
    canonicals = self.people_map.get(lookup_key)  # ❌ Uses curation map, not YAML

    if not canonicals:
        return []

    people = []
    for canonical in canonicals:
        person = self._resolve_single_person(canonical, session)
        if person:
            people.append(person)
    return people
```

**Problem**:
- Uses `self.people_map` which comes from curation files (consolidated_people.yaml)
- Doesn't use the person definition from metadata YAML
- Curation was only for jumpstart migration - shouldn't be used for ongoing imports

#### Lines 594-649: `_resolve_single_person()`

```python
# Lines 610-627: BUG - Matching logic
if lastname:
    person = session.query(Person).filter_by(name=name, lastname=lastname).first()
elif disambiguator:
    person = session.query(Person).filter_by(name=name, disambiguator=disambiguator).first()
else:
    # ❌ BUG: Only matches people with NULL lastname
    person = session.query(Person).filter_by(name=name, lastname=None).first()
```

**Problem**:
- When no lastname provided (from MD frontmatter), queries for `lastname=None`
- Won't match existing "Mónica González"
- Creates duplicate "Mónica" with NULL lastname

## Critical Bugs Identified

### Bug 1: Wrong Data Source for Entry People

**Location**: `metadata_importer.py` line 415
**Current**: `people_list = md_frontmatter.get("people", [])`
**Should be**: `people_list = metadata.get("people", [])`

**Impact**: All person definitions lost, creates duplicates

### Bug 2: Curation Resolver Used Instead of YAML Data

**Location**: `entity_resolver.py` lines 666-667
**Current**: Uses `self.people_map` from curation files
**Should be**: Use person definitions directly from metadata YAML

**Impact**: Import depends on external curation files instead of metadata YAML ground truth

### Bug 3: Incorrect Matching When No Lastname

**Location**: `entity_resolver.py` lines 623-627
**Current**: `filter_by(name=name, lastname=None)`
**Should be**: Try to match ANY person with that name, or require lastname

**Impact**: Creates duplicates when MD frontmatter lacks lastname

### Bug 4: No Validation of Scene Subsets

**Location**: `metadata_importer.py` - missing validation
**Current**: No validation that scene people ⊆ entry people
**Should be**: Validate subsets before creating scenes

**Impact**: Can create scenes with people not in entry, violating design

## Architecture Issues

### Issue 1: Dual Data Sources Confusion

The import tries to use BOTH:
- Curation files (consolidated_people.yaml) - old jumpstart artifact
- Metadata YAML people sections - actual ground truth

This creates confusion and bugs. **Curation should not be used for ongoing imports.**

### Issue 2: MD Frontmatter as Person Source

MD frontmatter `people: [...]` is meant for convenience (quick reference) but became the import source.

**Correct flow**:
1. Parse metadata YAML people section (ground truth)
2. Validate MD frontmatter people list matches metadata YAML people
3. Use metadata YAML definitions for all person creation/matching

### Issue 3: EntityResolver Design

EntityResolver was designed for curation (jumpstart migration), not for ongoing imports.

**Should be**:
- Metadata YAML is self-contained
- No external resolver needed for person definitions
- Resolver only needed for backward compatibility or migrations

## Required Fixes

### Fix 1: Use Metadata YAML for People Definitions

**File**: `metadata_importer.py`

```python
def _link_entry_people(self, entry: Entry, metadata: Dict[str, Any]) -> None:
    """Link entry-level people from METADATA YAML, not MD frontmatter."""
    people_list = metadata.get("people", [])  # Changed from md_frontmatter

    for person_data in people_list:
        if isinstance(person_data, str):
            # Legacy format: just name
            name = person_data
            person = self._get_or_create_person(name, None, None, [])
        else:
            # Full format with lastname/disambiguator
            name = person_data.get("name")
            lastname = person_data.get("lastname")
            disambiguator = person_data.get("disambiguator")
            alias = person_data.get("alias")

            person = self._get_or_create_person(name, lastname, disambiguator, [alias] if alias else [])

        if person and person not in entry.people:
            entry.people.append(person)
```

### Fix 2: Direct Person Matching (No Resolver)

**New method** in `metadata_importer.py`:

```python
def _get_or_create_person(
    self,
    name: str,
    lastname: Optional[str],
    disambiguator: Optional[str],
    aliases: List[str]
) -> Optional[Person]:
    """
    Get or create a person using metadata YAML data.

    Matching priority:
    1. By alias (if provided)
    2. By name + lastname
    3. By name + disambiguator
    4. Fail if ambiguous (multiple people with same name)
    """
    # Try alias first
    for alias in aliases:
        person = (
            self.session.query(Person)
            .join(PersonAlias)
            .filter(PersonAlias.alias == alias)
            .first()
        )
        if person:
            return person

    # Try name + lastname
    if lastname:
        person = (
            self.session.query(Person)
            .filter_by(name=name, lastname=lastname)
            .first()
        )
        if person:
            return person

    # Try name + disambiguator
    if disambiguator:
        person = (
            self.session.query(Person)
            .filter_by(name=name, disambiguator=disambiguator)
            .first()
        )
        if person:
            return person

    # Check if name is ambiguous
    existing = self.session.query(Person).filter_by(name=name).all()
    if len(existing) > 1 and not (lastname or disambiguator):
        raise ValueError(
            f"Ambiguous person '{name}': {len(existing)} people with this name exist. "
            f"Must provide lastname or disambiguator."
        )
    elif len(existing) == 1 and not (lastname or disambiguator):
        # Single match, use it
        return existing[0]

    # Create new person
    person = Person(
        name=name,
        lastname=lastname,
        disambiguator=disambiguator,
    )
    self.session.add(person)
    self.session.flush()

    # Add aliases
    for alias in aliases:
        person_alias = PersonAlias(person_id=person.id, alias=alias)
        self.session.add(person_alias)

    return person
```

### Fix 3: Validate Subset Logic

**New method** in `metadata_importer.py`:

```python
def _validate_scene_subsets(
    self,
    entry: Entry,
    scene_data: Dict[str, Any],
    scene_name: str
) -> None:
    """
    Validate that scene people/locations/dates are subsets of entry-level.

    Raises:
        ValueError: If scene references people/locations/dates not in entry
    """
    # Validate scene people
    scene_people = scene_data.get("people", [])
    entry_people_names = {p.name for p in entry.people}

    for person_name in scene_people:
        if person_name not in entry_people_names:
            raise ValueError(
                f"Scene '{scene_name}' references person '{person_name}' "
                f"not in entry people list"
            )

    # Validate scene locations
    scene_locations = scene_data.get("locations", [])
    entry_location_names = {loc.name for loc in entry.locations}

    for loc_name in scene_locations:
        if loc_name not in entry_location_names:
            raise ValueError(
                f"Scene '{scene_name}' references location '{loc_name}' "
                f"not in entry locations list"
            )

    # Validate scene dates
    scene_dates = scene_data.get("date") or scene_data.get("dates", [])
    if not isinstance(scene_dates, list):
        scene_dates = [scene_dates]

    entry_dates = {nd.date for nd in entry.narrated_dates}

    for scene_date in scene_dates:
        if isinstance(scene_date, str):
            scene_date = date.fromisoformat(scene_date)
        if scene_date not in entry_dates:
            raise ValueError(
                f"Scene '{scene_name}' references date {scene_date} "
                f"not in entry narrated_dates"
            )
```

### Fix 4: Remove Curation Dependency

**File**: `cli/database.py` lines 244-254

```python
# REMOVE this section - no curation needed for imports
try:
    resolver = EntityResolver.load()
    click.echo(...)
except FileNotFoundError as e:
    click.echo(...)
    resolver = None

# Change to:
resolver = None  # Not needed - metadata YAML is self-contained
```

## Testing Plan

### Test 1: Duplicate Person Prevention

1. Database has: Mónica González (ID 2)
2. Import entry with metadata YAML:
   ```yaml
   people:
     - name: Mónica
       lastname: González
   ```
3. Verify: No new Mónica created, entry links to ID 2

### Test 2: Person with Disambiguator

1. Import entry with:
   ```yaml
   people:
     - name: Mónica
       disambiguator: "work colleague"
   ```
2. Verify: Creates new person with disambiguator (different from Mónica González)

### Test 3: Scene Subset Validation

1. Import entry with:
   - MD frontmatter: `people: [Alda, Clara]`
   - Metadata YAML scene: `people: [Mónica]` (not in entry!)
2. Verify: Import fails with validation error

### Test 4: Full Import Without Curation

1. Remove consolidated_people.yaml
2. Run import
3. Verify: Works correctly using only metadata YAML

## Migration Path

### Phase 1: Fix Person Source

1. Update `_link_entry_people()` to use metadata YAML
2. Add `_get_or_create_person()` method
3. Test with 2021 entries

### Phase 2: Add Subset Validation

1. Add `_validate_scene_subsets()` method
2. Call before creating scenes
3. Test with entries that have scenes

### Phase 3: Remove Curation Dependency

1. Make EntityResolver optional
2. Remove from import_metadata command
3. Test full import without curation files

### Phase 4: Clean Database

1. Identify and delete all duplicate people (those with NULL lastname who shouldn't exist)
2. Re-import all entries to fix references
3. Verify export works correctly

## Files to Modify

1. `dev/pipeline/metadata_importer.py` - Main import logic
2. `dev/pipeline/cli/database.py` - Remove curation loading
3. `dev/dataclasses/metadata_entry.py` - May need updates for person format
4. `dev/validators/metadata.py` - Add subset validation

## Expected Outcomes

After fixes:
- ✅ No duplicate Person records created
- ✅ All people have lastname OR disambiguator (design requirement)
- ✅ Scene people/locations/dates are validated as subsets
- ✅ Import works without curation files (self-contained)
- ✅ Export succeeds for all 320 people (not just 230)

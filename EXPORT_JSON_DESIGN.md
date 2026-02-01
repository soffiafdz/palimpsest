# Export JSON Architecture Design
**Date:** 2024-02-01
**Phase:** 14b-3 (Export Canonical Files)
**Status:** Design Complete - Ready for Implementation

## Overview

Two distinct sets of files for journal metadata:

1. **Metadata YAML** (human-authored, per entry)
   - Location: `data/metadata/journal/YYYY/YYYY-MM-DD.yaml`
   - Ground truth for each entry
   - Created during jumpstart, edited by humans
   - Imported to database via `import-metadata`

2. **Export JSON** (machine-generated, per entity)
   - Location: `data/exports/journal/{entity-type}/{filename}.json`
   - Exported from database for version control
   - Machine-focused (fast parsing, IDs not names)
   - Used to recreate database across machines

## Directory Structure

```
data/exports/
├── README.md                              # Human-readable change log
├── journal/
│   ├── entries/
│   │   └── YYYY/
│   │       └── YYYY-MM-DD.json
│   ├── people/
│   │   └── {firstname}_{lastname|disambiguator}.json
│   ├── locations/
│   │   └── {city}/
│   │       └── {location-name}.json
│   ├── scenes/
│   │   └── YYYY-MM-DD/
│   │       └── {scene-name}.json
│   ├── events/
│   │   └── {event-name}.json             # Globally unique
│   ├── threads/
│   │   └── {thread-name}.json            # Globally unique
│   ├── arcs/
│   │   └── {arc-name}.json
│   ├── poems/
│   │   └── {poem-title}.json
│   ├── references/
│   │   └── {source-title}.json
│   ├── tags/
│   │   └── {tag-name}.json
│   ├── themes/
│   │   └── {theme-name}.json
│   └── motifs/
│       └── {motif-name}.json
└── manuscript/                            # Future: chapters, characters, etc.
```

## Filename Generation Rules

### People
**Format:** `{first}_{last|disambig}.json`

**Slugification:**
- Lowercase everything
- Strip accents (maría → maria)
- Spaces → hyphens within field
- Apostrophes removed (maria's → marias)
- Underscores separate fields
- Special characters stripped

**Examples:**
- Name: "María José", Lastname: "Castro Lopez" → `maria-jose_castro-lopez.json`
- Name: "Clara", Disambiguator: "maria's friend" → `clara_marias-friend.json`
- Name: "Robert", Lastname: "Franck" → `robert_franck.json`

**Validation:** Every person MUST have lastname OR disambiguator (enforced at creation)

**Fallback:** If filename > 250 chars → `person-{id}.json`

### Locations
**Format:** `{city}/{location-slug}.json`

Same slugification rules as people.

### Scenes
**Format:** `{YYYY-MM-DD}/{scene-slug}.json`

Entry-specific, namespaced by entry date to avoid collisions.

### Events, Threads, Arcs, Poems, References, Tags, Themes, Motifs
**Format:** `{name-slug}.json`

Globally unique, flat structure.

## JSON Format (Machine-Focused)

**Key Decision:** Use IDs for relationships, NOT slugs

### Rationale
- No slug field needed in DB schema
- No slug generation during import
- Direct foreign key references
- Smaller file size
- Zero ambiguity

### Trade-off
- Git diffs less readable (IDs instead of names)
- **Mitigation:** README.md provides human-readable change mapping

### Example Entry JSON
```json
{
  "id": 1523,
  "date": "2024-12-03",
  "word_count": 749,
  "reading_time": 2.9,
  "summary": "Sofia increases her antidepressant dose...",
  "rating": 4.5,
  "rating_justification": "Raw vulnerability...",
  "people_ids": [42, 17, 89],
  "location_ids": [5, 12],
  "city_ids": [1],
  "arc_ids": [3],
  "tag_ids": [8, 15],
  "theme_ids": [2],
  "scene_ids": [301, 302],
  "event_ids": [45],
  "thread_ids": [87],
  "poem_ids": [12],
  "reference_ids": [34],
  "motif_instance_ids": [156, 157]
}
```

### Example Person JSON
```json
{
  "id": 42,
  "name": "Clara",
  "lastname": "Dubois",
  "disambiguator": null,
  "relation_type": "romantic"
}
```

**Note:** Person does NOT store `entry_ids` - relationships are unidirectional (entry owns people, not vice versa)

## Relationship Storage Strategy

**Principle:** Unidirectional - stored only in owning entity

**What owns what:**
- **Entry owns:** people, locations, cities, tags, themes, arcs, scenes, events, threads, poems, references, motifs
- **Scene owns:** people, locations, dates (scene is owned by entry)
- **Event owns:** scenes (event is owned by entry)
- **Thread owns:** people, locations, referenced_entry (thread is owned by entry)
- **Poem/Reference owns:** nothing (owned by entry)

**Benefits:**
- Zero redundancy (each fact stored once)
- Git diffs show actual source of change
- DB recreation: load entities first, then load entries and build relationships

**Trade-off:**
- Can't see "what entries mention Clara" without parsing all entries
- This is acceptable - that's a DB query, not a file-browsing task

## README.md Format

**Purpose:** Human-readable change log with ID→name mapping

**Structure:**
```markdown
# Database Export Log

**Last Export:** 2024-02-01 15:23:45
**Entries:** 384 | **People:** 156 | **Locations:** 89 | **Scenes:** 247

## Latest Changes

### Entries
- ~ 2024-12-03 (id=1523):
    + person clara_dubois (42)
    + arc the-long-wanting (3)
    ~ summary [changed]
    ~ rating 4.0 → 4.5

- + 2024-12-05 (id=1524): [new entry]

### People
- ~ clara_dubois (id=42): relation_type friend → romantic
- + new-person (id=157): [new person]

### Scenes
- ~ 2024-12-03/psychiatric-session (id=301):
    ~ description [changed]
    + location montreal/home (5)
```

### Entity Identifier Format
Use **filename slug** (matches file path):
- People: `clara_dubois`
- Locations: `montreal/home`
- Scenes: `2024-12-03/psychiatric-session`
- Events/Arcs/Threads: `the-long-wanting`
- Entries: `2024-12-03`

### Change Description Detail Levels
1. **Text fields** (summary, description, content): `[changed]`
2. **Names/titles**: Show old→new if renamed
3. **Primitive fields**: Show old→new (e.g., `rating 4.0 → 4.5`)
4. **Relationships**: Show +/- with slug and ID (e.g., `+ person clara_dubois (42)`)

### Prefixes
- `+` = added
- `-` = removed
- `~` = modified

## Git Workflow

**Export Process:**
1. Export all entities to in-memory JSON structures
2. Load existing JSON files from disk (previous state)
3. Diff old vs new, build change descriptions
4. Generate README.md with timestamp + human-readable changes
5. Write all files (JSONs + README)
6. Single git commit: `git commit -m "DB export - 2024-02-01 15:23:45"`

**Viewing History:**
- See all exports: `git log --oneline data/exports/README.md`
- See specific export changes: `git show <commit>:data/exports/README.md`
- See JSON diff: `git show <commit>:data/exports/journal/people/clara_dubois.json`

**Benefits:**
- Single commit per export (not 384 separate commits)
- Human-readable change summary in README
- Detailed ID-based diffs in JSON files
- Clean git history

## Export Metadata Fields

JSON files can include export-specific fields (underscore prefix):

```json
{
  "_exported_at": "2024-02-01T15:23:45Z",
  "_db_version": "1.2.3",
  "_exporter_version": "14b-3",
  "id": 42,
  "name": "Clara",
  ...
}
```

## Implementation Notes

### Algorithm: README Generation
```python
def export_and_generate_readme(db):
    # 1. Export all entities to in-memory JSON
    new_exports = export_all_entities(db)

    # 2. Load existing files from disk
    old_exports = load_existing_exports()

    # 3. Diff and build change descriptions
    changes = []
    for entity_type, entities in new_exports.items():
        for entity_id, new_data in entities.items():
            old_data = old_exports.get(entity_type, {}).get(entity_id)

            if old_data is None:
                changes.append(f"+ {entity_type} {slug}: [new]")
            elif old_data != new_data:
                diff = describe_diff(old_data, new_data)
                changes.append(f"~ {entity_type} {slug}: {diff}")

    # 4. Generate README
    readme = generate_readme(changes, timestamp=now())

    # 5. Write everything
    write_exports(new_exports)
    write_readme(readme)

    # 6. Git commit
    git_commit_all(f"DB export - {timestamp}")
```

### describe_diff() Implementation
- Compare JSON objects field by field
- For lists: set diff (detect additions/removals)
- For primitives: show old→new
- For text fields: just "[changed]"
- Example: `{"people_ids": [42]} → {"people_ids": [42, 17]}` becomes `"+ person_id 17"`

## Why JSON Instead of YAML?

**Decision:** Use JSON for machine-generated exports, keep YAML for human-authored metadata

**Rationale:**
- **Speed:** JSON parsing is faster (stdlib vs PyYAML)
- **Simplicity:** Simpler spec, fewer edge cases
- **Security:** No code execution risks
- **Distinction:** Different file type signals "machine-only, don't edit"
- **Git diffs:** Pretty-printed JSON diffs are adequate for debugging

**Trade-off:**
- No comment support (workaround: use `_comment` fields in JSON)
- Slightly less readable than YAML (but readability not a goal for these files)

## Future: Manuscript Exports

Structure prepared but not yet implemented:
```
data/exports/manuscript/
├── chapters/{chapter-slug}.json
├── characters/{character-slug}.json
├── scenes/{scene-slug}.json          # Different from journal scenes
└── ...
```

## Validation Requirements

When creating new people (enforced by validator):
- MUST have lastname OR disambiguator (at least one)
- MUST NOT have duplicate (name, lastname) or (name, disambiguator) combination
- Ensures filename uniqueness without collision detection

## Design Decisions Summary

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Format | JSON not YAML | Speed, simplicity, machine-focused |
| References | IDs not slugs | No extra DB field, direct FKs, smaller files |
| Relationships | Unidirectional | Zero redundancy, single source of truth |
| Filenames | Slugified names | Human-readable paths, git-friendly |
| People naming | first_last or first_disambig | Deterministic, collision-free |
| Change tracking | README.md | Human-readable, single commit per export |
| Git commits | Single commit with timestamp | Clean history, README has details |
| Directory structure | Hierarchical by entity type | Clear organization, matches DB schema |

---

**Status:** Design finalized, ready for implementation in Phase 14b-3

**Next Steps:**
1. Implement JSON exporter (`dev/pipeline/export_json.py`)
2. Implement README generator
3. Implement git commit automation
4. Create CLI commands (`plm export-json`)
5. Test with full database export
6. Update documentation

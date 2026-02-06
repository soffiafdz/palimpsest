# Pickup Prompt for EntryManager Rebuild

Copy everything below the line into a new Claude Code session to resume this work.

---

Read `SESSION_CONTEXT.md` at the project root for full context on what was done and what remains.

## Summary

The codebase audit (WP-1 through WP-5) is committed. The main pending task is **rebuilding EntryManager's missing relationship processors**.

`EntryManager.update_relationships()` in `dev/database/managers/entry_manager.py` currently handles only 4 of 14 relationship types (cities, people, events, tags). The other 10 are commented out as TODOs. Working reference implementations for all 14 exist in `dev/pipeline/metadata_importer.py` (the bulk import pipeline that bypasses managers).

## Task

Rebuild the 10 missing relationship processors in `EntryManager.update_relationships()`. For each one:
1. Read the reference implementation in `metadata_importer.py`
2. Implement the processor in `entry_manager.py` using existing managers where possible
3. Write unit tests in `tests/unit/database/managers/test_entry_manager.py`

## Files to Read First

1. `SESSION_CONTEXT.md` — Full audit results, architecture decisions, detailed specs for each processor
2. `dev/database/managers/entry_manager.py` — The file to modify (see lines 699-737 for the TODOs)
3. `dev/pipeline/metadata_importer.py` — Reference implementations:
   - Lines 811-841: `_link_entry_locations()` → Locations processor
   - Lines 843-871: `_create_narrated_dates_from_frontmatter()` → NarratedDates processor
   - Lines 1010-1062: `_create_scenes()` → Scenes processor
   - Lines 1090-1142: `_create_events()` → Events processor (scene linking)
   - Lines 1144-1210: `_create_threads()` → Threads processor
   - Lines 1212-1247: `_link_arcs()` → Arcs processor
   - Lines 1286-1321: `_link_themes()` → Themes processor
   - Lines 1323-1371: `_create_motif_instances()` → Motifs processor
   - Lines 1373-1448: `_create_references()` → References processor
   - Lines 1450-1497: `_create_poems()` → Poems processor

## Existing Managers to Delegate To

- `dev/database/managers/location_manager.py` — `get_or_create_city()`, `get_or_create_location()`
- `dev/database/managers/poem_manager.py` — `create_version()` for poem+version creation
- `dev/database/managers/event_manager.py` — `get_or_create()` for events
- `dev/database/managers/person_manager.py` — `get_or_create()` for people

## Models

- `dev/database/models/core.py` — Entry, NarratedDate
- `dev/database/models/analysis.py` — Scene, SceneDate, Thread, Arc
- `dev/database/models/creative.py` — ReferenceSource, Reference, Poem, PoemVersion
- `dev/database/models/metadata.py` — Motif, MotifInstance
- `dev/database/models/entities.py` — Person, Event, Tag, Theme
- `dev/database/models/geography.py` — City, Location
- `dev/database/models/enums.py` — ReferenceMode, ReferenceType, SceneOrigin, SceneStatus

## Architecture Decision

Build processors directly in EntryManager (Option A from SESSION_CONTEXT.md). Use existing managers (PersonManager, LocationManager, EventManager, PoemManager) where possible. Don't refactor metadata_importer.py — it stays as the bulk import path.

## Running Tests

```bash
python -m pytest tests/ -q                    # Full suite (expect 101 pre-existing errors)
python -m pytest tests/unit/database/ -q      # Database tests only
pyright dev/database/managers/entry_manager.py # Type check
```

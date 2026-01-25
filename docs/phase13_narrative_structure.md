# Phase 13: Codebase Updates for Narrative Analysis

## Overview

Two sub-phases:
- **Phase 13a**: Legacy code cleanup (remove dead code first)
- **Phase 13b**: Add support for new narrative structure (scenes, threads, events, arcs)

---

## Phase 13a: Legacy Code Cleanup

### Files to Delete (confirmed safe)

| File | Size | Reason |
|------|------|--------|
| `dev/builders/wiki.py` | 13,127 lines | Deprecated, replaced by `dev/wiki/`. Exports not used. |
| `dev/pipeline/scene_identification.py` | 9,469 bytes | Standalone, not imported |
| `dev/pipeline/event_grouping.py` | 8,803 bytes | Standalone, not imported |
| `dev/pipeline/arc_grouping.py` | 8,244 bytes | Standalone, not imported |
| `templates/wiki/` directory | 108 bytes | Only contains unused `log.template` |
| `docs/wiki-redesign-proposal.md` | - | Pre-P26 design doc, now implemented |
| `process_events_arcs.py` (root) | 10,122 bytes | One-off script |
| `process_events_arcs_v2.py` (root) | 13,088 bytes | One-off script |
| `process_events_arcs_final.py` (root) | 14,047 bytes | One-off script |
| `create_events_arcs_v3.py` (root) | 12,860 bytes | One-off script |

### Files to Update

1. **`dev/builders/__init__.py`** — Remove wiki.py exports:
   ```python
   # Remove these lines:
   from dev.builders.wiki import EntityConfig, GenericEntityExporter, write_if_changed
   # And from __all__:
   "EntityConfig", "GenericEntityExporter", "write_if_changed",
   ```

2. **`dev/wiki/narrative_parser.py`** — Delete or mark for rewrite (references non-existent `_events/` and `_arcs/` directories)

3. **`dev/dataclasses/parsers/narrative_analysis.py`** — Will be replaced in Phase 13b

### Execution Order
1. Run test suite baseline: `python -m pytest tests/ -q`
2. Delete root-level scripts
3. Delete pipeline standalone scripts
4. Delete `templates/wiki/` directory
5. Update `dev/builders/__init__.py`
6. Delete `dev/builders/wiki.py`
7. Delete `docs/wiki-redesign-proposal.md`
8. Run test suite again to verify

---

## Phase 13b: New Narrative Structure Support

### Database Changes

**New Models** in `dev/database/models_manuscript.py`:

```python
# Scene - granular narrative moment
class Scene(Base):
    __tablename__ = "scenes"
    id, name, description, start_date, end_date
    manuscript_entry_id (FK)
    people (M2M), locations (M2M)

# Thread - temporal echo/connection
class Thread(Base):
    __tablename__ = "threads"
    id, name, from_date, to_date, referenced_entry_date, content
    manuscript_entry_id (FK)
    people (M2M), locations (M2M)

# NarrativeEvent - groups scenes within an entry
class NarrativeEvent(Base):
    __tablename__ = "narrative_events"
    id, name
    manuscript_entry_id (FK)
    scenes (M2M)
```

**Association Tables** to add:
- `scene_people`, `scene_locations`
- `thread_people`, `thread_locations`
- `narrative_event_scenes`
- `entry_arcs` (ManuscriptEntry ↔ Arc)

**Update ManuscriptEntry**:
- Add `arcs` relationship (M2M with Arc)
- Add `scenes`, `threads`, `narrative_events` relationships

### Parser Changes

**Create** `dev/dataclasses/parsers/narrative_yaml.py`:
- Parse YAML structure (not markdown)
- Handle: scenes, threads, events, arcs, themes (flat), motifs (with descriptions)
- Return `NarrativeAnalysisData` dataclass

### Manager Changes

**Update** `dev/database/managers/manuscript_manager.py`:
- Add `create_scene()`, `get_scenes_for_entry()`
- Add `create_thread()`, `get_threads_for_entry()`
- Add `create_narrative_event()`
- Add `link_entry_to_arcs()`

### Import Pipeline Changes

**Update** `dev/pipeline/import_analysis.py`:
- Use new YAML parser instead of markdown parser
- Add `import_scenes()`, `import_threads()`, `import_narrative_events()`, `import_arcs()`

### Wiki Template Changes

**Update** `dev/wiki/templates/entry.jinja2`:
- Add Scenes section
- Add Threads section

**Create** `dev/wiki/templates/indexes/scenes.jinja2`

### Execution Order
1. Add models and association tables
2. Create Alembic migration
3. Run migration
4. Create new YAML parser
5. Add manager methods
6. Update import pipeline
7. Update wiki templates
8. Run full test suite

---

## Critical Files

### Phase 13a
- `dev/builders/__init__.py` — update exports
- `dev/builders/wiki.py` — delete (13,127 lines)
- `dev/wiki/narrative_parser.py` — delete or rewrite

### Phase 13b
- `dev/database/models_manuscript.py` — add Scene, Thread, NarrativeEvent
- `dev/dataclasses/parsers/narrative_yaml.py` — create new parser
- `dev/database/managers/manuscript_manager.py` — add operations
- `dev/pipeline/import_analysis.py` — update to use new parser
- `dev/wiki/templates/entry.jinja2` — add scene/thread rendering

---

## Verification

### After Phase 13a
```bash
python -m pytest tests/ -q
python -c "import dev.builders; import dev.pipeline; import dev.wiki"
```

### After Phase 13b
```bash
# Run migrations
alembic upgrade head

# Test import
python -m dev.pipeline.cli import-analysis --dry-run

# Verify wiki export
python -m dev.wiki.cli export --entity entries

# Run full test suite
python -m pytest tests/ -q
```

---

## Estimated Scope
- **Phase 13a**: ~15,000 lines removed
- **Phase 13b**: ~500-700 lines added (models, parser, manager, templates)

---

## Status

- [x] Phase 13a: Legacy Code Cleanup
  - [x] Run baseline tests
  - [x] Delete root-level scripts
  - [x] Delete pipeline standalone scripts
  - [x] Delete templates/wiki/ directory
  - [x] Update dev/builders/__init__.py
  - [x] Delete dev/builders/wiki.py
  - [x] Delete docs/wiki-redesign-proposal.md
  - [x] Delete dev/wiki/narrative_parser.py
  - [x] Verify tests pass (1126 passed, 57.10% coverage)
- [ ] Phase 13b: New Narrative Structure Support
  - [ ] Add database models
  - [ ] Create Alembic migration
  - [ ] Create YAML parser
  - [ ] Add manager methods
  - [ ] Update import pipeline
  - [ ] Update wiki templates
  - [ ] Full test verification

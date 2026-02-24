# Test Writing Prompt for Sonnet Agents

## Context

The Palimpsest project has undergone a database schema redesign. The following changes were made:

### Model Renames and Field Changes

| Old | New |
|-----|-----|
| `Moment` model | Split into `Scene` (narrative moment) and `NarratedDate` (simple date) |
| `MomentType` enum | Removed |
| `ManuscriptEntry` | `Chapter` |
| `ManuscriptPerson` | `Character` + `PersonCharacterMap` |
| `City.city` | `City.name` |
| `Tag.tag` | `Tag.name` |
| `Theme.theme` | `Theme.name` |
| `Event.event` | `Event.name` |
| `entry.moments` | `entry.scenes` + `entry.narrated_dates` + `entry.threads` |
| `person.moments` | `person.scenes` |
| `Alias` model | Removed - `Person.alias` is now a field on Person |

### Files That Need Tests

The following files were modified and need test coverage:

1. **dev/database/manager.py** - Main PalimpsestDB class
   - Test session_scope with new manager set (without MomentManager/ManuscriptManager)
   - Test cleanup_all_metadata with Scene instead of Moment

2. **dev/database/managers/entry_manager.py** - Entry CRUD operations
   - Test Entry create/update/delete
   - Test tag processing with `Tag.name` field
   - Test relationship processing (cities, people, events)
   - Note: Alias processing and Moment processing are deprecated/commented out

3. **dev/database/export_manager.py** - Export functionality
   - Test `_serialize_entry()` with new model structure (narrated_dates, scenes, threads)
   - Test `_serialize_person()` with new fields

4. **dev/database/query_analytics.py** - Analytics queries
   - Test queries using `City.name` instead of `City.city`

5. **dev/wiki/exporter.py** - Wiki generation
   - Test `_export_threads_index()` (replaced `_export_moments_index()`)
   - Test manuscript export methods with Chapter/Character models

6. **dev/wiki/filters.py** - Jinja2 filters
   - Test `entity_link()` with new field names

7. **dev/dataclasses/parsers/db_to_yaml.py** - DB to YAML export
   - Test `build_narrated_dates_metadata()` (replaced `build_dates_metadata()`)
   - Test `build_cities_metadata()` with `city.name`

### Test Structure

Place tests in:
- `tests/unit/database/` for database managers
- `tests/unit/wiki/` for wiki exporter and filters
- `tests/unit/dataclasses/` for parsers

### Key Models to Import

```python
from dev.database.models import (
    Entry,
    Person,
    City,
    Location,
    Tag,
    Theme,
    Event,
    Arc,
    Scene,
    SceneDate,
    NarratedDate,
    Thread,
    Chapter,
    Character,
    PersonCharacterMap,
    ManuscriptScene,
    ManuscriptSource,
)
```

### Example Test Pattern

```python
import pytest
from datetime import date
from dev.database.models import Entry, Scene, NarratedDate, City, Tag

class TestEntryManager:
    def test_create_entry_with_scenes(self, db_session):
        """Test creating entry with scene relationships."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/path/to/entry.md",
        )
        db_session.add(entry)
        db_session.flush()

        scene = Scene(
            name="Test Scene",
            description="A test scene",
            entry_id=entry.id,
        )
        db_session.add(scene)
        db_session.commit()

        assert len(entry.scenes) == 1
        assert entry.scenes[0].name == "Test Scene"

    def test_city_name_field(self, db_session):
        """Test City model uses 'name' field."""
        city = City(name="Montreal")
        db_session.add(city)
        db_session.commit()

        assert city.name == "Montreal"

    def test_tag_name_field(self, db_session):
        """Test Tag model uses 'name' field."""
        tag = Tag(name="depression")
        db_session.add(tag)
        db_session.commit()

        assert tag.name == "depression"
```

### Fixtures Available

Check `tests/conftest.py` for available fixtures:
- `db_session` - SQLAlchemy session
- `db_manager` - PalimpsestDB instance
- `sample_entry` - Pre-created entry for testing

### Running Tests

```bash
python -m pytest tests/ -q
```

### Coverage Target

Minimum 15% coverage (enforced by CI).

## Instructions

1. Pick a file from the list above
2. Create corresponding test file in the appropriate `tests/` directory
3. Write tests that cover:
   - Happy path scenarios
   - Edge cases
   - Error conditions
4. Ensure tests use the NEW model field names (not the old ones)
5. Run tests to verify they pass

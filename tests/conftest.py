"""
conftest.py
-----------
Shared pytest fixtures for Palimpsest tests.

Provides fixtures for:
- Database setup and teardown
- Sample markdown files
- Test data factories
"""
import pytest
from pathlib import Path
from datetime import date
from tempfile import TemporaryDirectory


# ----- Path Fixtures -----

@pytest.fixture
def test_data_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_entries_dir(test_data_dir):
    """Path to sample entry files."""
    return test_data_dir / "sample_entries"


@pytest.fixture
def txt_exports_dir(test_data_dir):
    """Path to 750words txt export files."""
    return test_data_dir / "txt_exports"


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test file operations."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ----- Sample Markdown Content Fixtures -----

@pytest.fixture
def minimal_entry_content():
    """Minimal valid entry with only required fields."""
    return """---
date: 2024-01-15
---

# Monday, January 15, 2024

This is a minimal test entry with only the required date field.
"""


@pytest.fixture
def complex_entry_content():
    """Complex entry with all metadata fields populated."""
    return """---
date: 2024-01-15
word_count: 850
reading_time: 4.2

city: Montreal
locations:
  - Cafe X
  - Library (McGill Library)

people:
  - Alice
  - "@Bob (Robert Smith)"
  - Charlie

tags:
  - writing
  - research
  - python

events:
  - thesis-defense
  - conference-2024

dates:
  - 2024-06-01 (thesis exam)
  - 2024-08-15 (conference talk)

references:
  - content: "Quote from book"
    speaker: Famous Author
    source:
      title: Important Book
      type: book
      author: Author Name
  - content: "Another quote"
    source:
      title: Research Paper
      type: article
      author: Researcher

poems:
  - title: Test Poem
    content: |
      Roses are red
      Violets are blue
      Testing is great
      And so are you
    revision_date: 2024-01-15

epigraph: "Opening quote for the day"
epigraph_attribution: Philosopher Name

manuscript:
  status: draft
  edited: false
  themes:
    - identity
    - memory
  arcs:
    - arc-1
---

# Monday, January 15, 2024

Complex entry content here with multiple paragraphs.

This entry has all the metadata fields filled out for comprehensive testing.

## Section 1

Some content here.

## Section 2

More content here.
"""


@pytest.fixture
def entry_with_special_chars():
    """Entry with special characters, unicode, accents."""
    return """---
date: 2024-01-15
city: Montréal
locations:
  - Café de l'Époque
people:
  - María-José (María José García)
  - François
  - 李明 (Li Ming)
tags:
  - français
  - español
---

# Monday, January 15, 2024

Testing special characters: é, ñ, ü, 中文

Names with accents and hyphens.
"""


@pytest.fixture
def entry_with_poem_no_revision():
    """Entry with poem missing revision_date (regression test)."""
    return """---
date: 2024-01-15
poems:
  - title: Poem Without Revision Date
    content: |
      This poem has no revision date
      It should default to entry date
---

# Monday, January 15, 2024

Testing poem without explicit revision_date.
"""


@pytest.fixture
def minimal_entry_file(tmp_dir, minimal_entry_content):
    """Create a minimal entry markdown file."""
    file_path = tmp_dir / "2024-01-15.md"
    file_path.write_text(minimal_entry_content)
    return file_path


@pytest.fixture
def complex_entry_file(tmp_dir, complex_entry_content):
    """Create a complex entry markdown file."""
    file_path = tmp_dir / "2024-01-15-complex.md"
    file_path.write_text(complex_entry_content)
    return file_path


# ----- Sample Data Factory Functions -----

def create_sample_date():
    """Factory for consistent test dates."""
    return date(2024, 1, 15)


def create_minimal_person():
    """Factory for minimal person data."""
    return {"name": "Alice"}


def create_complex_person():
    """Factory for complex person data with all fields."""
    return {
        "name": "Bob",
        "full_name": "Robert Smith",
        "aliases": ["Bobby", "Rob"],
    }


def create_minimal_location():
    """Factory for minimal location data."""
    return {"name": "Montreal"}


def create_complex_location():
    """Factory for complex location data with city."""
    return {
        "name": "Cafe X",
        "expansion": "Cafe Experience",
        "city": "Montreal"
    }


# ----- Test Database Fixtures (Phase 3) -----

@pytest.fixture
def test_db_path(tmp_dir):
    """Create temporary test database path."""
    return tmp_dir / "test.db"


@pytest.fixture
def test_alembic_dir():
    """Path to Alembic directory."""
    return Path(__file__).parent.parent / "alembic"


@pytest.fixture
def test_db(test_db_path, test_alembic_dir):
    """
    Create test database instance with schema.

    Returns a PalimpsestDB instance with an initialized schema.
    Database is torn down after the test.
    """
    from dev.database.manager import PalimpsestDB
    from dev.database.models import Base
    from sqlalchemy import create_engine

    # Create engine and initialize schema
    engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(engine)

    # Create DB instance (without auto-backup for tests)
    db = PalimpsestDB(
        db_path=test_db_path,
        alembic_dir=test_alembic_dir,
        enable_auto_backup=False
    )

    yield db

    # Cleanup
    engine.dispose()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def db_session(test_db):
    """
    Create a database session for tests.

    Provides a session with automatic rollback after test.
    """
    with test_db.session_scope() as session:
        yield session
        session.rollback()


@pytest.fixture
def entry_manager(db_session):
    """Create EntryManager instance for testing."""
    from dev.database.managers.entry_manager import EntryManager
    return EntryManager(db_session)


@pytest.fixture
def person_manager(db_session):
    """Create PersonManager instance for testing."""
    from dev.database.managers.person_manager import PersonManager
    return PersonManager(db_session)


@pytest.fixture
def location_manager(db_session):
    """Create LocationManager instance for testing."""
    from dev.database.managers.location_manager import LocationManager
    return LocationManager(db_session)


@pytest.fixture
def tag_manager(db_session):
    """Create TagManager instance for testing."""
    from dev.database.managers.tag_manager import TagManager
    return TagManager(db_session)


@pytest.fixture
def poem_manager(db_session):
    """Create PoemManager instance for testing."""
    from dev.database.managers.poem_manager import PoemManager
    return PoemManager(db_session)


@pytest.fixture
def reference_manager(db_session):
    """Create ReferenceManager instance for testing."""
    from dev.database.managers.reference_manager import ReferenceManager
    return ReferenceManager(db_session)

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


# ----- Test Database Fixtures (for Phase 3+) -----
# These will be expanded in Phase 3 when testing database managers

@pytest.fixture
def test_db_path(tmp_dir):
    """Create temporary test database path."""
    return tmp_dir / "test.db"


# Note: Database fixtures will be added in Phase 3
# when we start testing database managers

import pytest
from unittest.mock import MagicMock
from datetime import date

from dev.validators.consistency import ConsistencyValidator
from dev.database.manager import PalimpsestDB

class MockEntry:
    def __init__(self, date_obj, file_path=None, word_count=0, people=None, locations=None, tags=None, related_entries=None, poems=None, file_hash=None):
        self.date = date_obj
        self.file_path = file_path
        self.word_count = word_count
        self.people = people or []
        self.locations = locations or []
        self.tags = tags or []
        self.related_entries = related_entries or []
        self.poems = poems or []
        self.file_hash = file_hash

    def isoformat(self):
        return self.date.isoformat()

class TestConsistencyValidator:
    """Tests for the ConsistencyValidator class."""

    @pytest.fixture
    def mock_db(self):
        """Mock PalimpsestDB."""
        db = MagicMock(spec=PalimpsestDB)
        # Setup session context manager
        session = MagicMock()
        db.session_scope.return_value.__enter__.return_value = session
        return db

    @pytest.fixture
    def validator(self, mock_db, tmp_path):
        """Create a ConsistencyValidator instance with temp dirs."""
        md_dir = tmp_path / "journal"
        md_dir.mkdir()

        return ConsistencyValidator(db=mock_db, md_dir=md_dir)

    def test_check_entry_existence_md_only(self, validator):
        """Test detecting entry in MD but not DB."""
        # Create MD file
        (validator.md_dir / "2024-01-01.md").touch()

        # Mock DB returning empty list
        session = validator.db.session_scope.return_value.__enter__.return_value
        session.query.return_value.all.return_value = []

        issues = validator.check_entry_existence()

        assert len(issues) >= 1
        md_db_issue = next((i for i in issues if i.system == "md-db" and i.entity_id == "2024-01-01"), None)
        assert md_db_issue
        assert md_db_issue.severity == "error"
        assert "Entry exists in markdown but not in database" in md_db_issue.message

    def test_check_entry_existence_db_only_file_missing(self, validator):
        """Test detecting entry in DB but MD file missing."""
        # Mock DB entry with non-existent path
        entry = MockEntry(date(2024, 1, 1), file_path=str(validator.md_dir / "2024-01-01.md"))
        session = validator.db.session_scope.return_value.__enter__.return_value
        session.query.return_value.all.return_value = [entry]

        issues = validator.check_entry_existence()

        db_md_issue = next((i for i in issues if i.system == "db-md" and i.entity_id == "2024-01-01"), None)
        assert db_md_issue
        assert db_md_issue.severity == "error"
        assert "Entry in database but file missing" in db_md_issue.message

    def test_check_referential_integrity_location_no_city(self, validator):
        """Test detecting location without city."""
        # Mock Location
        location = MagicMock()
        location.name = "Orphan Location"
        location.city = None # The issue

        entry = MockEntry(date(2024, 1, 1))
        entry.locations = [location]

        session = validator.db.session_scope.return_value.__enter__.return_value
        session.query.return_value.all.return_value = [entry]

        issues = validator.check_referential_integrity()

        assert len(issues) == 1
        assert issues[0].check_type == "references"
        assert "has no parent city" in issues[0].message

    def test_check_entry_metadata_date_mismatch(self, validator):
        """Test detecting mismatch between frontmatter date and DB date."""
        file_path = validator.md_dir / "2024-01-01.md"
        # Create MD file with DIFFERENT date in frontmatter
        file_path.write_text("---\ndate: 2024-01-02\n---\nContent", encoding="utf-8")

        entry = MockEntry(date(2024, 1, 1), file_path=str(file_path))

        session = validator.db.session_scope.return_value.__enter__.return_value
        session.query.return_value.all.return_value = [entry]

        issues = validator.check_entry_metadata()

        # Should find date mismatch: MD (2024-01-02) != DB (2024-01-01)
        issue = next((i for i in issues if "Date mismatch" in i.message), None)
        assert issue
        assert issue.severity == "error"

    def test_check_entry_metadata_word_count_mismatch(self, validator):
        """Test detecting word count mismatch."""
        file_path = validator.md_dir / "2024-01-01.md"
        file_path.write_text("---\ndate: 2024-01-01\nword_count: 100\n---\nContent", encoding="utf-8")

        # Mock DB entry with different word count
        entry = MockEntry(date(2024, 1, 1), file_path=str(file_path), word_count=200)

        session = validator.db.session_scope.return_value.__enter__.return_value
        session.query.return_value.all.return_value = [entry]

        issues = validator.check_entry_metadata()

        issue = next((i for i in issues if "Word count mismatch" in i.message), None)
        assert issue
        assert issue.severity == "warning"

import pytest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from datetime import date

from dev.pipeline.yaml2sql import process_entry_file, process_directory, sync_directory
from dev.database.manager import PalimpsestDB
from dev.core.exceptions import Yaml2SqlError
from dev.dataclasses.md_entry import MdEntry

class TestYaml2SqlPipeline:
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=PalimpsestDB)
        session = MagicMock()
        db.session_scope.return_value.__enter__.return_value = session
        return db

    @pytest.fixture
    def mock_logger(self):
        return MagicMock()

    @pytest.fixture
    def mock_md_entry(self):
        entry = MagicMock(spec=MdEntry)
        entry.date = date(2024, 1, 1)
        entry.validate.return_value = []
        entry.to_database_metadata.return_value = {"date": date(2024, 1, 1), "content": "test"}
        return entry

    @patch("dev.pipeline.yaml2sql.MdEntry")
    @patch("dev.pipeline.yaml2sql.fs")
    @patch("dev.pipeline.yaml2sql.SyncStateManager")
    def test_process_entry_file_create_new(
        self, mock_sync_mgr_cls, mock_fs, mock_md_entry_cls, mock_db, mock_logger, mock_md_entry
    ):
        """Test processing a new file creates an entry."""
        # Setup mocks
        file_path = Path("test.md")
        mock_md_entry_cls.from_file.return_value = mock_md_entry
        mock_fs.get_file_hash.return_value = "hash123"
        
        # DB setup: existing entry not found
        mock_db.entries.get.return_value = None
        
        # New entry creation mock
        created_entry = MagicMock()
        created_entry.id = 1
        mock_db.entries.create.return_value = created_entry

        result = process_entry_file(file_path, mock_db, logger=mock_logger)

        assert result == "created"
        mock_md_entry_cls.from_file.assert_called_once_with(file_path, verbose=False)
        mock_db.entries.get.assert_called_once_with(entry_date=mock_md_entry.date)
        mock_db.entries.create.assert_called_once()
        
        # Verify SyncStateManager interaction
        mock_sync_mgr = mock_sync_mgr_cls.return_value
        mock_sync_mgr.update_or_create.assert_called_once_with(
            entity_type="Entry",
            entity_id=1,
            last_synced_at=ANY,
            sync_source="yaml",
            sync_hash="hash123",
            machine_id=ANY
        )

    @patch("dev.pipeline.yaml2sql.MdEntry")
    @patch("dev.pipeline.yaml2sql.fs")
    @patch("dev.pipeline.yaml2sql.SyncStateManager")
    def test_process_entry_file_update_existing(
        self, mock_sync_mgr_cls, mock_fs, mock_md_entry_cls, mock_db, mock_logger, mock_md_entry
    ):
        """Test processing an existing file updates the entry."""
        file_path = Path("test.md")
        mock_md_entry_cls.from_file.return_value = mock_md_entry
        mock_fs.get_file_hash.return_value = "new_hash"
        
        # DB setup: existing entry found
        existing_entry = MagicMock()
        existing_entry.id = 1
        existing_entry.file_hash = "old_hash"
        mock_db.entries.get.return_value = existing_entry
        
        # FS setup: should not skip
        mock_fs.should_skip_file.return_value = False

        result = process_entry_file(file_path, mock_db, logger=mock_logger)

        assert result == "updated"
        mock_db.entries.update.assert_called_once()
        
        mock_sync_mgr = mock_sync_mgr_cls.return_value
        mock_sync_mgr.update_or_create.assert_called_once()

    @patch("dev.pipeline.yaml2sql.MdEntry")
    @patch("dev.pipeline.yaml2sql.fs")
    @patch("dev.pipeline.yaml2sql.SyncStateManager")
    def test_process_entry_file_skip_unchanged(
        self, mock_sync_mgr_cls, mock_fs, mock_md_entry_cls, mock_db, mock_logger, mock_md_entry
    ):
        """Test processing skips unchanged file."""
        file_path = Path("test.md")
        mock_md_entry_cls.from_file.return_value = mock_md_entry
        mock_fs.get_file_hash.return_value = "hash123"
        
        existing_entry = MagicMock()
        existing_entry.id = 1
        existing_entry.file_hash = "hash123"
        mock_db.entries.get.return_value = existing_entry
        
        # FS setup: should skip
        mock_fs.should_skip_file.return_value = True

        result = process_entry_file(file_path, mock_db, logger=mock_logger)

        assert result == "skipped"
        mock_db.entries.update.assert_not_called()
        mock_db.entries.create.assert_not_called()

    @patch("dev.pipeline.yaml2sql.MdEntry")
    def test_process_entry_file_parse_error(self, mock_md_entry_cls, mock_db, mock_logger):
        """Test handling of parse errors."""
        file_path = Path("bad.md")
        mock_md_entry_cls.from_file.side_effect = ValueError("Parse error")

        with pytest.raises(Yaml2SqlError, match="Failed to parse"):
            process_entry_file(file_path, mock_db, logger=mock_logger)

        # Test with raise_on_error=False
        result = process_entry_file(file_path, mock_db, logger=mock_logger, raise_on_error=False)
        assert result == "error"

    @patch("dev.pipeline.yaml2sql.MdEntry")
    def test_process_entry_file_validation_error(self, mock_md_entry_cls, mock_db, mock_logger, mock_md_entry):
        """Test handling of validation errors."""
        file_path = Path("invalid.md")
        mock_md_entry_cls.from_file.return_value = mock_md_entry
        mock_md_entry.validate.return_value = ["Missing required field"]

        with pytest.raises(Yaml2SqlError, match="Validation failed"):
            process_entry_file(file_path, mock_db, logger=mock_logger)

    @patch("dev.pipeline.yaml2sql.process_entry_file")
    @patch("dev.pipeline.yaml2sql.fs")
    def test_process_directory(self, mock_fs, mock_process_file, mock_db, mock_logger):
        """Test batch processing of directory."""
        input_dir = Path("journal")
        mock_fs.find_markdown_files.return_value = [Path("1.md"), Path("2.md")]
        mock_process_file.side_effect = ["created", "updated"]

        # Mock directory existence (pathlib.Path.exists)
        with patch("pathlib.Path.exists", return_value=True):
            stats = process_directory(input_dir, mock_db, logger=mock_logger)

        assert stats.files_processed == 2
        assert stats.entries_created == 1
        assert stats.entries_updated == 1
        assert mock_process_file.call_count == 2

    @patch("dev.pipeline.yaml2sql.process_entry_file")
    @patch("dev.pipeline.yaml2sql.fs")
    def test_process_directory_with_errors(self, mock_fs, mock_process_file, mock_db, mock_logger):
        """Test batch processing handles errors gracefully."""
        input_dir = Path("journal")
        mock_fs.find_markdown_files.return_value = [Path("1.md"), Path("2.md")]
        mock_process_file.side_effect = [Yaml2SqlError("Fail"), "created"]

        with patch("pathlib.Path.exists", return_value=True):
            stats = process_directory(input_dir, mock_db, logger=mock_logger)

        assert stats.files_processed == 2
        assert stats.errors == 1
        assert stats.entries_created == 1

    @patch("dev.pipeline.yaml2sql.process_directory")
    @patch("dev.pipeline.yaml2sql.fs")
    def test_sync_directory_delete_missing(self, mock_fs, mock_process_dir, mock_db, mock_logger):
        """Test sync with deletion of missing files."""
        input_dir = Path("journal")
        
        # Mock process_directory stats
        mock_stats = MagicMock()
        mock_stats.files_processed = 1
        mock_stats.entries_created = 0
        mock_stats.entries_updated = 1
        mock_stats.errors = 0
        mock_process_dir.return_value = mock_stats

        # Mock existing files
        mock_fs.find_markdown_files.return_value = [Path("journal/existing.md")]
        
        # Mock DB entries: one existing, one missing from disk
        existing_entry = MagicMock()
        existing_entry.file_path = str(Path("journal/existing.md").resolve())
        
        missing_entry = MagicMock()
        missing_entry.file_path = str(Path("journal/missing.md").resolve())
        
        session = mock_db.session_scope.return_value.__enter__.return_value
        session.query.return_value.all.return_value = [existing_entry, missing_entry]

        stats = sync_directory(input_dir, mock_db, delete_missing=True, logger=mock_logger)

        assert stats.entries_skipped == 1 # Reused for deleted count in sync
        mock_db.entries.delete.assert_called_once_with(
            missing_entry, deleted_by="yaml2sql", reason="removed_from_source"
        )

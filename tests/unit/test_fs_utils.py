"""
test_fs_utils.py
----------------
Unit tests for dev.utils.fs module.

Tests filesystem utilities for finding files, hashing, and date parsing.

Target Coverage: 95%+
"""
import pytest
from pathlib import Path
from datetime import date
from dev.utils.fs import (
    find_markdown_files,
    should_skip_file,
    get_file_hash,
    parse_date_from_filename,
    date_to_filename,
)


class TestFindMarkdownFiles:
    """Test find_markdown_files function."""

    def test_find_markdown_files_in_directory(self, tmp_dir):
        """Test finding markdown files."""
        # Create test files
        (tmp_dir / "file1.md").write_text("content")
        (tmp_dir / "file2.md").write_text("content")
        (tmp_dir / "file.txt").write_text("content")

        files = find_markdown_files(tmp_dir)
        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)

    def test_find_files_with_pattern(self, tmp_dir):
        """Test finding files with custom pattern."""
        # Create nested structure
        subdir = tmp_dir / "2024"
        subdir.mkdir()
        (tmp_dir / "root.md").write_text("content")
        (subdir / "nested.md").write_text("content")

        files = find_markdown_files(tmp_dir, "**/*.md")
        assert len(files) == 2

    def test_nonexistent_directory(self, tmp_dir):
        """Test finding files in non-existent directory."""
        files = find_markdown_files(tmp_dir / "nonexistent")
        assert files == []

    def test_empty_directory(self, tmp_dir):
        """Test finding files in empty directory."""
        files = find_markdown_files(tmp_dir)
        assert files == []

    def test_single_level_pattern(self, tmp_dir):
        """Test single-level pattern."""
        (tmp_dir / "file.md").write_text("content")
        subdir = tmp_dir / "sub"
        subdir.mkdir()
        (subdir / "nested.md").write_text("content")

        files = find_markdown_files(tmp_dir, "*.md")
        assert len(files) == 1  # Only root level


class TestShouldSkipFile:
    """Test should_skip_file function."""

    def test_force_never_skips(self, tmp_dir):
        """Test force=True never skips."""
        file_path = tmp_dir / "test.md"
        file_path.write_text("content")
        hash_val = get_file_hash(file_path)

        assert should_skip_file(file_path, hash_val, force=True) is False

    def test_no_existing_hash_not_skipped(self, tmp_dir):
        """Test file without existing hash is not skipped."""
        file_path = tmp_dir / "test.md"
        file_path.write_text("content")

        assert should_skip_file(file_path, None) is False

    def test_matching_hash_skips(self, tmp_dir):
        """Test file with matching hash is skipped."""
        file_path = tmp_dir / "test.md"
        file_path.write_text("content")
        hash_val = get_file_hash(file_path)

        assert should_skip_file(file_path, hash_val, force=False) is True

    def test_different_hash_not_skipped(self, tmp_dir):
        """Test file with different hash is not skipped."""
        file_path = tmp_dir / "test.md"
        file_path.write_text("content")
        old_hash = "different_hash_value"

        assert should_skip_file(file_path, old_hash, force=False) is False


class TestGetFileHash:
    """Test get_file_hash function."""

    def test_hash_consistency(self, tmp_dir):
        """Test same file produces same hash."""
        file_path = tmp_dir / "test.md"
        file_path.write_text("content")

        hash1 = get_file_hash(file_path)
        hash2 = get_file_hash(file_path)
        assert hash1 == hash2

    def test_different_content_different_hash(self, tmp_dir):
        """Test different content produces different hash."""
        file1 = tmp_dir / "test1.md"
        file2 = tmp_dir / "test2.md"
        file1.write_text("content 1")
        file2.write_text("content 2")

        hash1 = get_file_hash(file1)
        hash2 = get_file_hash(file2)
        assert hash1 != hash2

    def test_hash_length(self, tmp_dir):
        """Test hash is MD5 format (32 hex chars)."""
        file_path = tmp_dir / "test.md"
        file_path.write_text("content")

        hash_result = get_file_hash(file_path)
        assert len(hash_result) == 32
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_nonexistent_file_raises(self, tmp_dir):
        """Test non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_file_hash(tmp_dir / "nonexistent.md")

    def test_directory_raises(self, tmp_dir):
        """Test directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_file_hash(tmp_dir)

    def test_empty_file_hash(self, tmp_dir):
        """Test empty file produces valid hash."""
        file_path = tmp_dir / "empty.md"
        file_path.write_text("")

        hash_result = get_file_hash(file_path)
        assert len(hash_result) == 32

    def test_unicode_content(self, tmp_dir):
        """Test file with unicode content."""
        file_path = tmp_dir / "unicode.md"
        file_path.write_text("Café 日本語")

        hash_result = get_file_hash(file_path)
        assert len(hash_result) == 32


class TestParseDateFromFilename:
    """Test parse_date_from_filename function."""

    def test_parse_full_date(self):
        """Test parsing YYYY-MM-DD format."""
        path = Path("2024-01-15.md")
        result = parse_date_from_filename(path)
        assert result == date(2024, 1, 15)

    def test_parse_year_month(self):
        """Test parsing YYYY-MM format."""
        path = Path("2024-01.md")
        result = parse_date_from_filename(path)
        assert result == date(2024, 1, 1)  # Defaults to 1st day

    def test_parse_year_only(self):
        """Test parsing YYYY format."""
        path = Path("2024.md")
        result = parse_date_from_filename(path)
        assert result == date(2024, 1, 1)  # Defaults to Jan 1st

    def test_invalid_format_raises(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_date_from_filename(Path("invalid.md"))

    def test_invalid_date_raises(self):
        """Test invalid date values raise ValueError."""
        with pytest.raises(ValueError):
            parse_date_from_filename(Path("2024-13-01.md"))  # Invalid month

    def test_path_object(self):
        """Test function works with Path object."""
        result = parse_date_from_filename(Path("2024-01-15.md"))
        assert result == date(2024, 1, 15)

    def test_leap_year_date(self):
        """Test leap year date."""
        result = parse_date_from_filename(Path("2024-02-29.md"))
        assert result == date(2024, 2, 29)

    def test_december_date(self):
        """Test December date."""
        result = parse_date_from_filename(Path("2024-12-31.md"))
        assert result == date(2024, 12, 31)


class TestDateToFilename:
    """Test date_to_filename function."""

    def test_day_precision(self):
        """Test day precision returns full ISO format."""
        test_date = date(2024, 1, 15)
        assert date_to_filename(test_date, "day") == "2024-01-15"

    def test_month_precision(self):
        """Test month precision returns YYYY-MM."""
        test_date = date(2024, 1, 15)
        assert date_to_filename(test_date, "month") == "2024-01"

    def test_year_precision(self):
        """Test year precision returns YYYY."""
        test_date = date(2024, 1, 15)
        assert date_to_filename(test_date, "year") == "2024"

    def test_default_precision_is_day(self):
        """Test default precision is day."""
        test_date = date(2024, 1, 15)
        assert date_to_filename(test_date) == "2024-01-15"

    def test_invalid_precision_raises(self):
        """Test invalid precision raises ValueError."""
        test_date = date(2024, 1, 15)
        with pytest.raises(ValueError):
            date_to_filename(test_date, "invalid")

    def test_single_digit_month_padded(self):
        """Test single digit month is zero-padded."""
        test_date = date(2024, 3, 5)
        assert date_to_filename(test_date, "day") == "2024-03-05"
        assert date_to_filename(test_date, "month") == "2024-03"

    def test_december_date(self):
        """Test December date formatting."""
        test_date = date(2024, 12, 31)
        assert date_to_filename(test_date, "day") == "2024-12-31"

    def test_round_trip_with_parser(self):
        """Test round-trip conversion with parse_date_from_filename."""
        original_date = date(2024, 1, 15)
        filename = date_to_filename(original_date, "day")
        parsed_date = parse_date_from_filename(Path(f"{filename}.md"))
        assert parsed_date == original_date

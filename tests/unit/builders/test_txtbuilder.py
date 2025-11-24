#!/usr/bin/env python3
"""
Tests for TxtBuilder - inbox file processing.

Tests basic functionality of processing raw 750words exports:
- Filename parsing and validation
- File organization by year
- Processing statistics
"""
import pytest
from pathlib import Path
from dev.builders.txtbuilder import TxtBuilder, ProcessingStats


class TestProcessingStats:
    """Test ProcessingStats tracking."""

    def test_stats_initialization(self):
        """Test stats are initialized to zero."""
        stats = ProcessingStats()
        assert stats.files_found == 0
        assert stats.files_processed == 0
        assert stats.files_skipped == 0
        assert stats.years_updated == 0
        assert stats.errors == 0

    def test_stats_summary(self):
        """Test summary string formatting."""
        stats = ProcessingStats()
        stats.files_found = 5
        stats.files_processed = 3
        stats.files_skipped = 2
        stats.errors = 0

        summary = stats.summary()
        assert "5 found" in summary
        assert "3 processed" in summary
        assert "2 skipped" in summary
        assert "0 errors" in summary


class TestTxtBuilder:
    """Test TxtBuilder file processing."""

    def test_filename_parsing_valid(self):
        """Test parsing valid filename formats."""
        builder = TxtBuilder(
            inbox_dir=Path("/tmp/inbox"),
            output_dir=Path("/tmp/output"),
        )

        # Test YYYY-MM format
        result = builder._parse_filename("2024-11.txt")
        assert result == ("2024", "11")

        # Test YYYY_MM format
        result = builder._parse_filename("2024_11.txt")
        assert result == ("2024", "11")

    def test_filename_parsing_invalid(self):
        """Test parsing invalid filename formats."""
        builder = TxtBuilder(
            inbox_dir=Path("/tmp/inbox"),
            output_dir=Path("/tmp/output"),
        )

        # Invalid formats should return None
        assert builder._parse_filename("invalid.txt") is None
        assert builder._parse_filename("202411.txt") is None
        assert builder._parse_filename("24-11.txt") is None  # Year too short

    def test_builder_initialization(self):
        """Test TxtBuilder initialization with defaults."""
        inbox_dir = Path("/tmp/inbox")
        output_dir = Path("/tmp/output")

        builder = TxtBuilder(
            inbox_dir=inbox_dir,
            output_dir=output_dir,
        )

        assert builder.inbox_dir == inbox_dir
        assert builder.output_dir == output_dir
        assert builder.format_script is not None  # Should use default

    def test_builder_with_custom_paths(self):
        """Test TxtBuilder initialization with custom paths."""
        inbox_dir = Path("/custom/inbox")
        output_dir = Path("/custom/output")
        archive_dir = Path("/custom/archive")
        format_script = Path("/custom/script.py")

        builder = TxtBuilder(
            inbox_dir=inbox_dir,
            output_dir=output_dir,
            archive_dir=archive_dir,
            format_script=format_script,
        )

        assert builder.inbox_dir == inbox_dir
        assert builder.output_dir == output_dir
        assert builder.archive_dir == archive_dir
        assert builder.format_script == format_script


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

#!/usr/bin/env python3
"""
test_publisher.py
-----------------
Tests for the WikiPublisher module.

Covers frontmatter construction, YAML injection, single-file
publishing, full-tree publishing, and draft chapter detection.

Key Features:
    - TestBuildFrontmatter: title extraction, path-based tagging
    - TestInjectFrontmatter: YAML prepending and format validation
    - TestPublishFile: output creation, structure, change detection, stats
    - TestPublishAll: full directory walk, clearing, stats tracking
    - TestDraftDetection: database-driven draft status in frontmatter

Dependencies:
    - pytest (tmp_path fixture for filesystem isolation)
    - unittest.mock for PalimpsestDB mocking
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.wiki.publisher import WikiPublisher


# ==================== Fixtures ====================

@pytest.fixture
def wiki_tree(tmp_path: Path) -> Tuple[Path, Path]:
    """
    Create a minimal wiki directory tree with sample files.

    Returns:
        Tuple of (wiki_dir, output_dir) paths
    """
    wiki_dir = tmp_path / "wiki"
    output_dir = tmp_path / "quartz"

    # Create journal/people
    people_dir = wiki_dir / "journal" / "people"
    people_dir.mkdir(parents=True)
    (people_dir / "clara.md").write_text(
        "# Clara Dupont\n\n**Role:** love interest\n"
    )

    # Create manuscript/chapters
    chapters_dir = wiki_dir / "manuscript" / "chapters"
    chapters_dir.mkdir(parents=True)
    (chapters_dir / "the-gray-fence.md").write_text(
        "# The Gray Fence\n\n**Type:** Prose\n"
    )

    # Create indexes
    indexes_dir = wiki_dir / "indexes"
    indexes_dir.mkdir(parents=True)
    (indexes_dir / "main.md").write_text(
        "# Palimpsest Wiki\n\nWelcome.\n"
    )

    return wiki_dir, output_dir


@pytest.fixture
def mock_db() -> MagicMock:
    """
    Create a mock PalimpsestDB instance.

    Returns:
        MagicMock configured for basic session_scope usage
    """
    return MagicMock()


@pytest.fixture
def mock_logger() -> MagicMock:
    """
    Create a mock logger with all methods used by WikiPublisher.

    Returns:
        MagicMock that accepts any method call silently
    """
    return MagicMock()


@pytest.fixture
def publisher(
    wiki_tree: Tuple[Path, Path],
    mock_db: MagicMock,
    mock_logger: MagicMock,
) -> WikiPublisher:
    """
    Create a WikiPublisher with temporary directories and mock DB.

    Args:
        wiki_tree: Tuple of (wiki_dir, output_dir)
        mock_db: Mock database instance
        mock_logger: Mock logger instance

    Returns:
        Configured WikiPublisher instance
    """
    wiki_dir, output_dir = wiki_tree
    return WikiPublisher(
        db=mock_db,
        wiki_dir=wiki_dir,
        output_dir=output_dir,
        logger=mock_logger,
    )


# ==================== TestBuildFrontmatter ====================

class TestBuildFrontmatter:
    """Tests for _build_frontmatter title extraction and path tagging."""

    def test_extracts_title_from_h1(
        self, publisher: WikiPublisher
    ) -> None:
        """Title is extracted from the first H1 heading in content."""
        content = "# Clara Dupont\n\nSome text."
        rel_path = Path("journal/people/clara.md")
        fm = publisher._build_frontmatter(rel_path, content)
        assert fm["title"] == "Clara Dupont"

    def test_tag_for_journal_people(
        self, publisher: WikiPublisher
    ) -> None:
        """Files under journal/people receive the 'person' tag."""
        content = "# Clara Dupont\n"
        rel_path = Path("journal/people/clara.md")
        fm = publisher._build_frontmatter(rel_path, content)
        assert fm["tags"] == ["person"]

    def test_tag_for_manuscript_chapters(
        self, publisher: WikiPublisher
    ) -> None:
        """Files under manuscript/chapters receive the 'chapter' tag."""
        content = "# The Gray Fence\n"
        rel_path = Path("manuscript/chapters/the-gray-fence.md")
        fm = publisher._build_frontmatter(rel_path, content)
        assert fm["tags"] == ["chapter"]

    def test_tag_for_indexes(self, publisher: WikiPublisher) -> None:
        """Files under indexes receive the 'index' tag."""
        content = "# Palimpsest Wiki\n"
        rel_path = Path("indexes/main.md")
        fm = publisher._build_frontmatter(rel_path, content)
        assert fm["tags"] == ["index"]

    def test_no_h1_omits_title(self, publisher: WikiPublisher) -> None:
        """Files with no H1 heading produce frontmatter without title."""
        content = "Some text without a heading.\n"
        rel_path = Path("journal/people/mystery.md")
        fm = publisher._build_frontmatter(rel_path, content)
        assert "title" not in fm
        assert fm["tags"] == ["person"]


# ==================== TestInjectFrontmatter ====================

class TestInjectFrontmatter:
    """Tests for _inject_frontmatter YAML prepending."""

    def test_prepends_frontmatter_to_content(
        self, publisher: WikiPublisher
    ) -> None:
        """Frontmatter is inserted before the original content."""
        frontmatter = {"title": "Clara Dupont", "tags": ["person"]}
        content = "# Clara Dupont\n\nSome text.\n"
        result = publisher._inject_frontmatter(frontmatter, content)
        assert result.startswith("---\n")
        assert result.endswith(content)
        assert "# Clara Dupont" in result

    def test_empty_frontmatter_returns_content_unchanged(
        self, publisher: WikiPublisher
    ) -> None:
        """Empty frontmatter dict returns original content as-is."""
        content = "# Clara Dupont\n\nSome text.\n"
        result = publisher._inject_frontmatter({}, content)
        assert result == content

    def test_correct_yaml_format(
        self, publisher: WikiPublisher
    ) -> None:
        """Injected frontmatter is valid YAML between --- delimiters."""
        frontmatter = {
            "title": "Clara Dupont",
            "tags": ["person"],
            "draft": False,
        }
        content = "# Clara Dupont\n"
        result = publisher._inject_frontmatter(frontmatter, content)

        # Extract YAML block between --- delimiters
        parts = result.split("---")
        # parts[0] is empty string before first ---
        # parts[1] is the YAML block
        # parts[2] is everything after closing ---
        assert len(parts) >= 3
        yaml_block = parts[1].strip()
        parsed = yaml.safe_load(yaml_block)
        assert parsed["title"] == "Clara Dupont"
        assert parsed["tags"] == ["person"]
        assert parsed["draft"] is False


# ==================== TestPublishFile ====================

class TestPublishFile:
    """Tests for _publish_file single-file publishing."""

    def test_creates_output_file_with_frontmatter(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Publishing a file creates it in output dir with frontmatter."""
        wiki_dir, output_dir = wiki_tree
        source = wiki_dir / "journal" / "people" / "clara.md"
        publisher._publish_file(source)

        output = output_dir / "journal" / "people" / "clara.md"
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "Clara Dupont" in content

    def test_preserves_directory_structure(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Output file mirrors the source subdirectory structure."""
        wiki_dir, output_dir = wiki_tree
        source = wiki_dir / "manuscript" / "chapters" / "the-gray-fence.md"
        publisher._publish_file(source)

        output = output_dir / "manuscript" / "chapters" / "the-gray-fence.md"
        assert output.exists()
        assert output.parent.name == "chapters"
        assert output.parent.parent.name == "manuscript"

    def test_change_detection_skips_unchanged(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Unchanged files are skipped on second publish."""
        wiki_dir, _ = wiki_tree
        source = wiki_dir / "journal" / "people" / "clara.md"

        # First publish
        publisher._publish_file(source)
        assert publisher.stats["files_copied"] == 1
        assert publisher.stats["files_skipped"] == 0

        # Second publish of same content
        publisher._publish_file(source)
        assert publisher.stats["files_copied"] == 1
        assert publisher.stats["files_skipped"] == 1

    def test_updates_stats_correctly(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Stats are updated for each published file."""
        wiki_dir, _ = wiki_tree

        # Publish two distinct files
        publisher._publish_file(
            wiki_dir / "journal" / "people" / "clara.md"
        )
        publisher._publish_file(
            wiki_dir / "indexes" / "main.md"
        )

        assert publisher.stats["files_copied"] == 2
        assert publisher.stats["files_changed"] == 2
        assert publisher.stats["files_skipped"] == 0


# ==================== TestPublishAll ====================

class TestPublishAll:
    """Tests for publish_all full-tree publishing."""

    def test_copies_all_md_files(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """All .md files from the wiki directory are published."""
        _, output_dir = wiki_tree
        publisher.publish_all()

        output_files = list(output_dir.rglob("*.md"))
        assert len(output_files) == 3

    def test_clears_output_dir_before_copy(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Existing content in output dir is cleared before publishing."""
        _, output_dir = wiki_tree

        # Pre-populate output with a stale file
        stale_dir = output_dir / "journal" / "people"
        stale_dir.mkdir(parents=True)
        stale_file = stale_dir / "ghost.md"
        stale_file.write_text("# Ghost\n\nStale content.\n")

        publisher.publish_all()

        # The ghost file should be gone (directory was cleared)
        assert not stale_file.exists()

    def test_preserves_subdirectory_structure(
        self,
        publisher: WikiPublisher,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Output mirrors the wiki subdirectory hierarchy."""
        _, output_dir = wiki_tree
        publisher.publish_all()

        assert (output_dir / "journal" / "people" / "clara.md").exists()
        assert (
            output_dir / "manuscript" / "chapters" / "the-gray-fence.md"
        ).exists()
        assert (output_dir / "indexes" / "main.md").exists()

    def test_stats_reflect_total_files(
        self,
        publisher: WikiPublisher,
    ) -> None:
        """Stats count all files processed during publish_all."""
        publisher.publish_all()

        assert publisher.stats["files_copied"] == 3
        assert publisher.stats["files_changed"] == 3
        assert publisher.stats["files_skipped"] == 0


# ==================== TestDraftDetection ====================

class TestDraftDetection:
    """Tests for _is_draft_chapter and draft field in frontmatter."""

    def test_draft_chapter_returns_true(
        self,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Draft chapter produces draft=true in frontmatter."""
        wiki_dir, output_dir = wiki_tree
        mock_db = MagicMock()

        # Configure mock: session_scope returns a context manager
        # whose session.query(...).filter(...).first() returns a
        # chapter with status.value == "draft"
        mock_chapter = MagicMock()
        mock_chapter.status.value = "draft"
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_chapter
        )
        mock_db.session_scope.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_db.session_scope.return_value.__exit__ = MagicMock(
            return_value=False
        )

        pub = WikiPublisher(
            db=mock_db, wiki_dir=wiki_dir, output_dir=output_dir
        )
        result = pub._is_draft_chapter("The Gray Fence")
        assert result is True

        # Also verify frontmatter includes draft=true
        content = "# The Gray Fence\n"
        rel_path = Path("manuscript/chapters/the-gray-fence.md")
        fm = pub._build_frontmatter(rel_path, content)
        assert fm["draft"] is True

    def test_non_draft_chapter_returns_false(
        self,
        wiki_tree: Tuple[Path, Path],
    ) -> None:
        """Non-draft chapter produces draft=false in frontmatter."""
        wiki_dir, output_dir = wiki_tree
        mock_db = MagicMock()

        # Configure mock: chapter with status "final"
        mock_chapter = MagicMock()
        mock_chapter.status.value = "final"
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_chapter
        )
        mock_db.session_scope.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_db.session_scope.return_value.__exit__ = MagicMock(
            return_value=False
        )

        pub = WikiPublisher(
            db=mock_db, wiki_dir=wiki_dir, output_dir=output_dir
        )
        result = pub._is_draft_chapter("The Gray Fence")
        assert result is False

        # Also verify frontmatter includes draft=false
        content = "# The Gray Fence\n"
        rel_path = Path("manuscript/chapters/the-gray-fence.md")
        fm = pub._build_frontmatter(rel_path, content)
        assert fm["draft"] is False

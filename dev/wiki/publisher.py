#!/usr/bin/env python3
"""
publisher.py
------------
Quartz publishing pipeline for wiki content.

Copies wiki markdown files to the Quartz content directory with
YAML frontmatter injection. Source wiki files are never modified;
frontmatter is added only to the Quartz copies.

Key Features:
    - Copies wiki tree to Quartz content directory
    - Injects YAML frontmatter (title, tags, aliases, date, draft)
    - Entity type detection from file path for graph coloring
    - Change detection (only writes if content differs)

Usage:
    from dev.wiki.publisher import WikiPublisher

    publisher = WikiPublisher(db)
    publisher.publish_all()

Dependencies:
    - PalimpsestDB for entity metadata lookup
    - PyYAML for frontmatter serialization
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import ROOT, WIKI_DIR
from dev.database.manager import PalimpsestDB
from dev.database.models.manuscript import Chapter


# ==================== Constants ====================

QUARTZ_CONTENT_DIR = ROOT / "quartz" / "content"

H1_RE = re.compile(r'^# (.+)$', re.MULTILINE)

# Map wiki subdirectory to entity type tag for Quartz graph coloring
PATH_TO_TAG: Dict[str, str] = {
    "journal/people": "person",
    "journal/locations": "location",
    "journal/cities": "city",
    "journal/events": "event",
    "journal/arcs": "arc",
    "journal/tags": "tag",
    "journal/themes": "theme",
    "journal/poems": "poem",
    "journal/references": "reference",
    "journal/motifs": "motif",
    "journal/entries": "entry",
    "manuscript/chapters": "chapter",
    "manuscript/characters": "character",
    "manuscript/scenes": "manuscript-scene",
    "indexes": "index",
}


# ==================== WikiPublisher ====================

class WikiPublisher:
    """
    Publishes wiki content to Quartz static site directory.

    Copies all wiki markdown files to the Quartz content directory,
    injecting YAML frontmatter for title, tags (entity type), aliases,
    date, and draft status. The source wiki files are never modified.

    Attributes:
        db: PalimpsestDB instance for entity metadata
        wiki_dir: Source wiki directory
        output_dir: Quartz content output directory
        logger: Optional logger instance
        stats: Publishing statistics
    """

    def __init__(
        self,
        db: PalimpsestDB,
        wiki_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize the wiki publisher.

        Args:
            db: PalimpsestDB instance
            wiki_dir: Source wiki directory (defaults to WIKI_DIR)
            output_dir: Quartz content dir (defaults to QUARTZ_CONTENT_DIR)
            logger: Optional logger for progress reporting
        """
        self.db = db
        self.wiki_dir = wiki_dir or WIKI_DIR
        self.output_dir = output_dir or QUARTZ_CONTENT_DIR
        self.logger = safe_logger(logger)
        self.stats: Dict[str, int] = {
            "files_copied": 0,
            "files_changed": 0,
            "files_skipped": 0,
        }

    def publish_all(self) -> None:
        """
        Publish all wiki files to Quartz content directory.

        Clears the output directory and copies all .md files with
        frontmatter injection. Directory structure is preserved.
        """
        self.logger.info(
            f"Publishing wiki to {self.output_dir}..."
        )

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Clear existing content (regenerate from scratch)
        for item in self.output_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            elif item.suffix == ".md":
                item.unlink()

        # Walk source wiki and copy with frontmatter
        for md_file in sorted(self.wiki_dir.rglob("*.md")):
            self._publish_file(md_file)

        self.logger.info(
            f"Published {self.stats['files_copied']} files "
            f"({self.stats['files_changed']} changed)"
        )

    def _publish_file(self, source_path: Path) -> None:
        """
        Copy a single wiki file to output with frontmatter injection.

        Args:
            source_path: Path to source markdown file
        """
        # Compute relative path and output path
        rel_path = source_path.relative_to(self.wiki_dir)
        output_path = self.output_dir / rel_path

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read source content
        content = source_path.read_text(encoding="utf-8")

        # Build frontmatter
        frontmatter = self._build_frontmatter(rel_path, content)

        # Inject frontmatter
        published_content = self._inject_frontmatter(frontmatter, content)

        # Change detection
        if output_path.exists():
            existing = output_path.read_text(encoding="utf-8")
            if existing == published_content:
                self.stats["files_skipped"] += 1
                return

        output_path.write_text(published_content, encoding="utf-8")
        self.stats["files_copied"] += 1
        self.stats["files_changed"] += 1

    def _build_frontmatter(
        self, rel_path: Path, content: str
    ) -> Dict[str, Any]:
        """
        Build YAML frontmatter dict for a wiki file.

        Extracts title from H1 heading. Determines entity type
        from file path for graph coloring tags.

        Args:
            rel_path: Path relative to wiki root
            content: File content

        Returns:
            Dict with frontmatter fields
        """
        frontmatter: Dict[str, Any] = {}

        # Title from H1
        title_match = H1_RE.search(content)
        if title_match:
            frontmatter["title"] = title_match.group(1).strip()

        # Entity type tag from path
        path_str = str(rel_path.parent).replace("\\", "/")
        for prefix, tag in PATH_TO_TAG.items():
            if path_str.startswith(prefix):
                frontmatter["tags"] = [tag]
                break

        # Draft status for manuscript chapters
        if path_str.startswith("manuscript/chapters"):
            frontmatter["draft"] = self._is_draft_chapter(
                frontmatter.get("title", "")
            )

        return frontmatter

    def _is_draft_chapter(self, title: str) -> bool:
        """
        Check if a chapter is in draft status.

        Args:
            title: Chapter title to look up

        Returns:
            True if chapter status is draft, False otherwise
        """
        try:
            with self.db.session_scope() as session:
                chapter = session.query(Chapter).filter(
                    Chapter.title == title
                ).first()
                if chapter:
                    return chapter.status.value == "draft"
        except Exception:
            pass
        return False

    def _inject_frontmatter(
        self,
        frontmatter: Dict[str, Any],
        content: str,
    ) -> str:
        """
        Prepend YAML frontmatter to markdown content.

        If frontmatter is empty, returns content unchanged.

        Args:
            frontmatter: Dict of frontmatter fields
            content: Original markdown content

        Returns:
            Content with YAML frontmatter prepended
        """
        if not frontmatter:
            return content

        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()

        return f"---\n{yaml_str}\n---\n{content}"

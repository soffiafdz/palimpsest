#!/usr/bin/env python3
"""
test_validator.py
-----------------
Tests for WikiValidator and Diagnostic dataclass.

Validates structural checks (H1 title, empty sections) and
wikilink resolution against a test database.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.wiki.validator import Diagnostic, WikiValidator


# ==================== Diagnostic Tests ====================

class TestDiagnostic:
    """Tests for the Diagnostic dataclass."""

    def test_to_dict(self):
        """to_dict returns all fields as a dict."""
        d = Diagnostic(
            file="test.md",
            line=1,
            col=1,
            end_line=1,
            end_col=10,
            severity="error",
            code="TEST",
            message="test msg",
        )
        result = d.to_dict()
        assert result["file"] == "test.md"
        assert result["line"] == 1
        assert result["col"] == 1
        assert result["end_line"] == 1
        assert result["end_col"] == 10
        assert result["severity"] == "error"
        assert result["code"] == "TEST"
        assert result["message"] == "test msg"
        assert result["source"] == "palimpsest"

    def test_default_source(self):
        """Default source is 'palimpsest'."""
        d = Diagnostic(
            file="f.md", line=1, col=1, end_line=1, end_col=1,
            severity="warning", code="X", message="m",
        )
        assert d.source == "palimpsest"

    def test_custom_source(self):
        """Source can be overridden."""
        d = Diagnostic(
            file="f.md", line=1, col=1, end_line=1, end_col=1,
            severity="info", code="X", message="m", source="custom",
        )
        assert d.source == "custom"
        assert d.to_dict()["source"] == "custom"


# ==================== WikiValidator Tests ====================

class TestWikiValidatorTitle:
    """Tests for H1 title checking."""

    def test_missing_title(self, test_db, tmp_path):
        """File without H1 heading gets MISSING_TITLE error."""
        f = tmp_path / "test.md"
        f.write_text("No heading here\n\nJust content.")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert any(d.code == "MISSING_TITLE" for d in diags)
        title_diag = next(d for d in diags if d.code == "MISSING_TITLE")
        assert title_diag.severity == "error"
        assert title_diag.line == 1

    def test_valid_title(self, test_db, tmp_path):
        """File with H1 heading passes title check."""
        f = tmp_path / "test.md"
        f.write_text("# Valid Title\n\nContent here.")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "MISSING_TITLE" for d in diags)

    def test_h2_not_h1(self, test_db, tmp_path):
        """H2 heading does not satisfy H1 requirement."""
        f = tmp_path / "test.md"
        f.write_text("## Not An H1\n\nContent here.")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert any(d.code == "MISSING_TITLE" for d in diags)


class TestWikiValidatorEmptySections:
    """Tests for empty section detection."""

    def test_empty_section(self, test_db, tmp_path):
        """Empty H2 section gets EMPTY_SECTION warning."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Title\n\n## Empty Section\n\n## Another Section\n\nContent here."
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        empty_diags = [d for d in diags if d.code == "EMPTY_SECTION"]
        assert len(empty_diags) == 1
        assert empty_diags[0].severity == "warning"
        assert "Empty Section" in empty_diags[0].message

    def test_no_empty_sections(self, test_db, tmp_path):
        """File with content in all sections has no EMPTY_SECTION diagnostics."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Title\n\n## Section One\n\nContent.\n\n## Section Two\n\nMore content."
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "EMPTY_SECTION" for d in diags)

    def test_multiple_empty_sections(self, test_db, tmp_path):
        """Multiple empty sections each get a diagnostic."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Title\n\n## Empty One\n\n## Empty Two\n\n## Has Content\n\nOK."
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        empty_diags = [d for d in diags if d.code == "EMPTY_SECTION"]
        assert len(empty_diags) == 2

    def test_h3_empty_section(self, test_db, tmp_path):
        """Empty H3 section also gets EMPTY_SECTION warning."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Title\n\n## Section\n\nContent.\n\n### Empty Sub\n\n## Next\n\nOK."
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        empty_diags = [d for d in diags if d.code == "EMPTY_SECTION"]
        assert len(empty_diags) == 1
        assert "Empty Sub" in empty_diags[0].message


class TestWikiValidatorWikilinks:
    """Tests for wikilink resolution."""

    def test_unresolved_wikilink(self, test_db, tmp_path):
        """Wikilink to non-existent entity gets UNRESOLVED_WIKILINK error."""
        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[Nonexistent Person]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        unresolved = [d for d in diags if d.code == "UNRESOLVED_WIKILINK"]
        assert len(unresolved) == 1
        assert unresolved[0].severity == "error"
        assert "Nonexistent Person" in unresolved[0].message

    def test_resolved_wikilink_person(self, test_db, db_session, tmp_path):
        """Wikilink to existing person's display_name passes."""
        from dev.database.models.entities import Person
        from dev.database.models.enums import RelationType

        person = Person(
            name="Clara", lastname="Dupont",
            slug="clara_dupont", relation_type=RelationType.ROMANTIC,
        )
        db_session.add(person)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[Clara Dupont]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags)

    def test_wikilink_case_insensitive(self, test_db, db_session, tmp_path):
        """Wikilink resolution is case-insensitive."""
        from dev.database.models.entities import Person
        from dev.database.models.enums import RelationType

        person = Person(
            name="Clara", lastname="Dupont",
            slug="clara_dupont", relation_type=RelationType.ROMANTIC,
        )
        db_session.add(person)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[clara dupont]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags)

    def test_wikilink_with_display_text(self, test_db, db_session, tmp_path):
        """Wikilink with display text resolves the target part only."""
        from dev.database.models.entities import Person
        from dev.database.models.enums import RelationType

        person = Person(
            name="Clara", lastname="Dupont",
            slug="clara_dupont", relation_type=RelationType.ROMANTIC,
        )
        db_session.add(person)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[Clara Dupont|Clara]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags)

    def test_entry_date_wikilink(self, test_db, db_session, tmp_path):
        """Wikilink to entry date (YYYY-MM-DD) resolves."""
        from dev.database.models.core import Entry

        entry = Entry(
            date=date(2024, 11, 8),
            file_path="2024/2024-11-08.md",
            word_count=100,
        )
        db_session.add(entry)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[2024-11-08]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags)

    def test_tag_wikilink(self, test_db, db_session, tmp_path):
        """Wikilink to tag name resolves."""
        from dev.database.models.entities import Tag

        tag = Tag(name="loneliness")
        db_session.add(tag)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[loneliness]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags)

    def test_location_wikilink(self, test_db, db_session, tmp_path):
        """Wikilink to location name resolves."""
        from dev.database.models.geography import City, Location

        city = City(name="Montreal", country="Canada")
        db_session.add(city)
        db_session.flush()

        loc = Location(name="Cafe Olimpico", city_id=city.id)
        db_session.add(loc)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[Cafe Olimpico]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags)

    def test_multiple_wikilinks_mixed(self, test_db, db_session, tmp_path):
        """File with both resolved and unresolved wikilinks."""
        from dev.database.models.entities import Tag

        tag = Tag(name="solitude")
        db_session.add(tag)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[solitude]] and [[does not exist]]")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        unresolved = [d for d in diags if d.code == "UNRESOLVED_WIKILINK"]
        assert len(unresolved) == 1
        assert "does not exist" in unresolved[0].message

    def test_wikilink_column_position(self, test_db, tmp_path):
        """Diagnostic column accurately points to the wikilink."""
        f = tmp_path / "test.md"
        f.write_text("# Title\n\nSome text [[broken link]] more text")
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        unresolved = [d for d in diags if d.code == "UNRESOLVED_WIKILINK"]
        assert len(unresolved) == 1
        # [[broken link]] starts at column 11 (0-indexed: 10, 1-indexed: 11)
        assert unresolved[0].col == 11


class TestWikiValidatorDirectory:
    """Tests for directory validation."""

    def test_validate_directory(self, test_db, tmp_path):
        """Validates all .md files in directory."""
        (tmp_path / "good.md").write_text("# Good\n\nContent.")
        (tmp_path / "bad.md").write_text("No heading.")
        validator = WikiValidator(test_db)
        results = validator.validate_directory(tmp_path)
        assert len(results) == 2
        # good.md should have no MISSING_TITLE
        good_key = str(tmp_path / "good.md")
        assert not any(d.code == "MISSING_TITLE" for d in results[good_key])
        # bad.md should have MISSING_TITLE
        bad_key = str(tmp_path / "bad.md")
        assert any(d.code == "MISSING_TITLE" for d in results[bad_key])

    def test_non_md_files_skipped(self, test_db, tmp_path):
        """Non-markdown files are not validated."""
        (tmp_path / "notes.txt").write_text("not markdown")
        (tmp_path / "test.md").write_text("# Title\n\nOK")
        validator = WikiValidator(test_db)
        results = validator.validate_directory(tmp_path)
        assert str(tmp_path / "notes.txt") not in results
        assert str(tmp_path / "test.md") in results

    def test_recursive_directory(self, test_db, tmp_path):
        """Validates .md files in subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("No title here.")
        (tmp_path / "top.md").write_text("# Top\n\nOK")
        validator = WikiValidator(test_db)
        results = validator.validate_directory(tmp_path)
        assert len(results) == 2
        nested_key = str(sub / "nested.md")
        assert any(d.code == "MISSING_TITLE" for d in results[nested_key])

    def test_empty_directory(self, test_db, tmp_path):
        """Empty directory returns empty results."""
        validator = WikiValidator(test_db)
        results = validator.validate_directory(tmp_path)
        assert len(results) == 0


class TestWikiValidatorCaching:
    """Tests for known targets caching."""

    def test_targets_cached(self, test_db, db_session, tmp_path):
        """Known targets are loaded once and cached."""
        from dev.database.models.entities import Tag

        tag = Tag(name="cached_tag")
        db_session.add(tag)
        db_session.commit()

        validator = WikiValidator(test_db)

        f = tmp_path / "test.md"
        f.write_text("# Title\n\n[[cached_tag]]")

        # First call loads targets
        diags1 = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags1)

        # Verify cache is populated
        assert validator._known_targets is not None
        assert "cached_tag" in validator._known_targets

        # Second call uses cache (same instance)
        diags2 = validator.validate_file(f)
        assert not any(d.code == "UNRESOLVED_WIKILINK" for d in diags2)


class TestWikiValidatorIntegration:
    """Integration tests with multiple check types."""

    def test_file_with_multiple_issues(self, test_db, tmp_path):
        """File with multiple issue types returns all diagnostics."""
        f = tmp_path / "test.md"
        f.write_text(
            "## No H1 Title\n\nContent.\n\n"
            "## Empty Section\n\n"
            "## Has Content\n\n"
            "[[broken link]] here."
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)

        codes = {d.code for d in diags}
        assert "MISSING_TITLE" in codes
        assert "EMPTY_SECTION" in codes
        assert "UNRESOLVED_WIKILINK" in codes

    def test_clean_file_no_diagnostics(self, test_db, db_session, tmp_path):
        """Well-formed file with valid links returns no diagnostics."""
        from dev.database.models.entities import Tag

        tag = Tag(name="valid_tag")
        db_session.add(tag)
        db_session.commit()

        f = tmp_path / "test.md"
        f.write_text(
            "# Clean Page\n\n"
            "## Section One\n\nSome content with [[valid_tag]].\n\n"
            "## Section Two\n\nMore content."
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        assert len(diags) == 0

    def test_diagnostics_sorted_by_line(self, test_db, tmp_path):
        """Diagnostics are returned sorted by line number."""
        f = tmp_path / "test.md"
        f.write_text(
            "No title\n\n"
            "## Empty\n\n"
            "## Content\n\n"
            "[[broken1]]\n"
            "[[broken2]]"
        )
        validator = WikiValidator(test_db)
        diags = validator.validate_file(f)
        lines = [d.line for d in diags]
        assert lines == sorted(lines)

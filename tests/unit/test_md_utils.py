"""
test_md_utils.py
----------------
Unit tests for dev.utils.md module.

Tests markdown-specific utilities for parsing frontmatter, formatting YAML,
and content hashing.

Target Coverage: 95%+
"""
from dev.utils.md import (
    split_frontmatter,
    yaml_escape,
    yaml_list,
    yaml_multiline,
    get_text_hash,
    read_entry_body,
)


class TestSplitFrontmatter:
    """Test split_frontmatter function."""

    def test_basic_frontmatter(self):
        """Test parsing basic YAML frontmatter."""
        content = """---
date: 2024-01-15
tags: test
---

Body content here"""
        frontmatter, body = split_frontmatter(content)
        assert frontmatter == "date: 2024-01-15\ntags: test"
        assert body == ["Body content here"]

    def test_multiline_frontmatter(self):
        """Test parsing multi-line frontmatter."""
        content = """---
date: 2024-01-15
people:
  - Alice
  - Bob
tags:
  - test
---

Body content"""
        frontmatter, body = split_frontmatter(content)
        assert "date: 2024-01-15" in frontmatter
        assert "people:" in frontmatter
        assert "Alice" in frontmatter

    def test_no_frontmatter(self):
        """Test content without frontmatter."""
        content = "Just body content\nNo frontmatter here"
        frontmatter, body = split_frontmatter(content)
        assert frontmatter == ""
        assert body == ["Just body content", "No frontmatter here"]

    def test_empty_frontmatter(self):
        """Test empty frontmatter section."""
        content = """---
---

Body content"""
        frontmatter, body = split_frontmatter(content)
        assert frontmatter == ""
        assert body == ["Body content"]

    def test_no_closing_delimiter(self):
        """Test frontmatter without closing ---."""
        content = """---
date: 2024-01-15

Body content"""
        frontmatter, body = split_frontmatter(content)
        assert frontmatter == ""
        # Returns all lines as body when no closing delimiter
        assert len(body) > 0

    def test_empty_lines_after_frontmatter_removed(self):
        """Test empty lines after frontmatter are removed."""
        content = """---
date: 2024-01-15
---


Body content"""
        frontmatter, body = split_frontmatter(content)
        assert body == ["Body content"]

    def test_whitespace_in_delimiters(self):
        """Test delimiters with surrounding whitespace."""
        content = """  ---
date: 2024-01-15
  ---

Body"""
        frontmatter, body = split_frontmatter(content)
        # Should handle whitespace around delimiters
        assert "date: 2024-01-15" in frontmatter

    def test_empty_content(self):
        """Test completely empty content."""
        frontmatter, body = split_frontmatter("")
        assert frontmatter == ""
        assert body == []

    def test_multiline_body(self):
        """Test body with multiple lines."""
        content = """---
date: 2024-01-15
---

# Title

Paragraph 1

Paragraph 2"""
        frontmatter, body = split_frontmatter(content)
        assert len(body) == 5
        assert body[0] == "# Title"


class TestYamlEscape:
    """Test yaml_escape function."""

    def test_escape_quotes(self):
        """Test escaping double quotes."""
        assert yaml_escape('He said "hello"') == 'He said \\"hello\\"'

    def test_escape_newlines(self):
        """Test escaping newlines."""
        assert yaml_escape("Line 1\nLine 2") == "Line 1\\nLine 2"

    def test_both_quotes_and_newlines(self):
        """Test escaping both quotes and newlines."""
        result = yaml_escape('He said "hello"\nAnd then left')
        assert '\\"' in result
        assert '\\n' in result

    def test_no_special_chars(self):
        """Test string without special characters."""
        assert yaml_escape("Simple text") == "Simple text"

    def test_empty_string(self):
        """Test empty string."""
        assert yaml_escape("") == ""

    def test_unicode_preserved(self):
        """Test unicode characters are preserved."""
        assert yaml_escape("Café") == "Café"
        assert yaml_escape("日本語") == "日本語"


class TestYamlList:
    """Test yaml_list function."""

    def test_simple_list(self):
        """Test formatting simple list."""
        assert yaml_list(["simple", "list"]) == "[simple, list]"

    def test_empty_list(self):
        """Test empty list returns []."""
        assert yaml_list([]) == "[]"

    def test_items_with_spaces(self):
        """Test items with spaces are quoted."""
        result = yaml_list(["Has spaces", "No"])
        assert result == '["Has spaces", No]'

    def test_items_with_colons(self):
        """Test items with colons are quoted."""
        result = yaml_list(["Has: colon", "Simple"])
        assert result == '["Has: colon", Simple]'

    def test_items_with_quotes(self):
        """Test items with quotes are escaped and quoted."""
        result = yaml_list(['Has "quotes"'])
        assert '\\"' in result  # Escaped quotes

    def test_hyphenated_mode(self):
        """Test hyphenated=True converts spaces to hyphens."""
        result = yaml_list(["Has spaces", "Another one"], hyphenated=True)
        assert "Has-spaces" in result
        assert "Another-one" in result

    def test_numeric_items(self):
        """Test list with numbers."""
        assert yaml_list([1, 2, 3]) == "[1, 2, 3]"

    def test_mixed_types(self):
        """Test list with mixed types."""
        result = yaml_list(["text", 42, "more text"])
        assert "text" in result
        assert "42" in result

    def test_single_item(self):
        """Test list with single item."""
        assert yaml_list(["only"]) == "[only]"


class TestYamlMultiline:
    """Test yaml_multiline function."""

    def test_single_line(self):
        """Test single line is quoted."""
        assert yaml_multiline("Single line") == '"Single line"'

    def test_multiline_with_pipe(self):
        """Test multiline uses pipe notation."""
        result = yaml_multiline("Line 1\nLine 2")
        assert result.startswith("|\n")
        assert "  Line 1\n" in result
        assert "  Line 2" in result

    def test_empty_string(self):
        """Test empty string."""
        assert yaml_multiline("") == '""'

    def test_string_with_quotes(self):
        """Test single line with quotes is escaped."""
        result = yaml_multiline('Has "quotes"')
        assert '\\"' in result

    def test_three_line_text(self):
        """Test text with three lines."""
        text = "Line 1\nLine 2\nLine 3"
        result = yaml_multiline(text)
        assert result.startswith("|\n")
        assert result.count("\n") == 3  # Pipe line + 3 content lines

    def test_preserves_empty_lines(self):
        """Test empty lines in multiline text."""
        text = "Line 1\n\nLine 3"
        result = yaml_multiline(text)
        assert "  \n" in result  # Empty line preserved


class TestGetTextHash:
    """Test get_text_hash function."""

    def test_consistent_hash(self):
        """Test same text produces same hash."""
        text = "Hello, world!"
        hash1 = get_text_hash(text)
        hash2 = get_text_hash(text)
        assert hash1 == hash2

    def test_different_text_different_hash(self):
        """Test different text produces different hash."""
        hash1 = get_text_hash("Text 1")
        hash2 = get_text_hash("Text 2")
        assert hash1 != hash2

    def test_empty_string_hash(self):
        """Test empty string produces valid hash."""
        hash_result = get_text_hash("")
        assert len(hash_result) == 32  # MD5 hex length

    def test_unicode_text_hash(self):
        """Test unicode text produces valid hash."""
        hash_result = get_text_hash("Café 日本語")
        assert len(hash_result) == 32

    def test_newlines_affect_hash(self):
        """Test newlines affect hash value."""
        hash1 = get_text_hash("Line 1\nLine 2")
        hash2 = get_text_hash("Line 1Line 2")
        assert hash1 != hash2

    def test_whitespace_affects_hash(self):
        """Test whitespace affects hash value."""
        hash1 = get_text_hash("text")
        hash2 = get_text_hash("text ")
        assert hash1 != hash2


class TestReadEntryBody:
    """Test read_entry_body function."""

    def test_read_body_from_file(self, tmp_dir):
        """Test reading body content from file."""
        file_path = tmp_dir / "test.md"
        content = """---
date: 2024-01-15
---

# Title

Body content here"""
        file_path.write_text(content)

        body = read_entry_body(file_path)
        assert len(body) > 0
        assert "# Title" in body

    def test_nonexistent_file(self, tmp_dir):
        """Test reading from non-existent file."""
        file_path = tmp_dir / "nonexistent.md"
        body = read_entry_body(file_path)
        assert body == []

    def test_file_without_frontmatter(self, tmp_dir):
        """Test reading file without frontmatter."""
        file_path = tmp_dir / "test.md"
        content = "# Title\n\nBody content"
        file_path.write_text(content)

        body = read_entry_body(file_path)
        assert "# Title" in body
        assert "Body content" in body

    def test_empty_file(self, tmp_dir):
        """Test reading empty file."""
        file_path = tmp_dir / "empty.md"
        file_path.write_text("")

        body = read_entry_body(file_path)
        assert body == []

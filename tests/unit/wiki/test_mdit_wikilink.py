#!/usr/bin/env python3
"""
test_mdit_wikilink.py
---------------------
Tests for the markdown-it-py wikilink inline rule plugin.

Covers basic wikilink parsing, display text extraction, code block
protection, edge cases, and the extract_wikilinks helper.
"""
# --- Annotations ---
from __future__ import annotations

# --- Third-party imports ---
from markdown_it import MarkdownIt

# --- Local imports ---
from dev.wiki.mdit_wikilink import extract_wikilinks, wikilink_plugin


# ==================== Helpers ====================

def parse_inline(text: str) -> list:
    """
    Parse text and return flat list of inline token types and content.

    Args:
        text: Markdown text to parse

    Returns:
        List of (type, content) tuples for all inline children
    """
    md = MarkdownIt().use(wikilink_plugin)
    tokens = md.parse(text)
    result = []
    for token in tokens:
        if token.children:
            for child in token.children:
                result.append((child.type, child.content))
    return result


def get_wikilink_tokens(text: str) -> list:
    """
    Parse text and return only wikilink tokens with their meta.

    Args:
        text: Markdown text to parse

    Returns:
        List of token meta dicts for wikilink tokens
    """
    md = MarkdownIt().use(wikilink_plugin)
    tokens = md.parse(text)
    wikilinks = []
    for token in tokens:
        if token.children:
            for child in token.children:
                if child.type == "wikilink":
                    wikilinks.append(child.meta)
    return wikilinks


# ==================== Basic Parsing ====================

class TestBasicWikilinks:
    """Tests for basic [[target]] wikilink parsing."""

    def test_simple_wikilink(self):
        """[[target]] is parsed as wikilink token."""
        tokens = get_wikilink_tokens("Visit [[Clara Dupont]] today")
        assert len(tokens) == 1
        assert tokens[0]["target"] == "Clara Dupont"
        assert tokens[0]["display"] == "Clara Dupont"

    def test_wikilink_at_start(self):
        """Wikilink at start of line."""
        tokens = get_wikilink_tokens("[[Clara]] is here")
        assert len(tokens) == 1
        assert tokens[0]["target"] == "Clara"

    def test_wikilink_at_end(self):
        """Wikilink at end of line."""
        tokens = get_wikilink_tokens("See [[Clara]]")
        assert len(tokens) == 1

    def test_wikilink_only(self):
        """Line with only a wikilink."""
        tokens = get_wikilink_tokens("[[Clara Dupont]]")
        assert len(tokens) == 1

    def test_multiple_wikilinks(self):
        """Multiple wikilinks in one line."""
        tokens = get_wikilink_tokens("[[Clara]] and [[Majo]] met")
        assert len(tokens) == 2
        assert tokens[0]["target"] == "Clara"
        assert tokens[1]["target"] == "Majo"


class TestDisplayText:
    """Tests for [[target|display]] syntax."""

    def test_display_text(self):
        """[[target|display]] splits into target and display."""
        tokens = get_wikilink_tokens("See [[Clara Dupont|Clara]]")
        assert len(tokens) == 1
        assert tokens[0]["target"] == "Clara Dupont"
        assert tokens[0]["display"] == "Clara"

    def test_display_text_with_spaces(self):
        """Display text can contain spaces."""
        tokens = get_wikilink_tokens("[[2024-11-08|November 8th]]")
        assert tokens[0]["target"] == "2024-11-08"
        assert tokens[0]["display"] == "November 8th"

    def test_multiple_pipes_uses_first(self):
        """Only first pipe is used as separator."""
        tokens = get_wikilink_tokens("[[a|b|c]]")
        assert tokens[0]["target"] == "a"
        assert tokens[0]["display"] == "b|c"


class TestCodeBlockProtection:
    """Tests that wikilinks inside code are not parsed."""

    def test_inline_code_protection(self):
        """Wikilinks inside backticks are not parsed."""
        tokens = get_wikilink_tokens("Use `[[not a link]]` here")
        assert len(tokens) == 0

    def test_fenced_code_block_protection(self):
        """Wikilinks inside fenced code blocks are not parsed."""
        text = "```\n[[not a link]]\n```"
        tokens = get_wikilink_tokens(text)
        assert len(tokens) == 0

    def test_mixed_code_and_wikilink(self):
        """Only non-code wikilinks are parsed."""
        text = "See [[Clara]] but not `[[Code]]`"
        tokens = get_wikilink_tokens(text)
        assert len(tokens) == 1
        assert tokens[0]["target"] == "Clara"


class TestEdgeCases:
    """Tests for edge cases and invalid input."""

    def test_empty_wikilink(self):
        """[[]] is not parsed as wikilink."""
        tokens = get_wikilink_tokens("See [[]] here")
        assert len(tokens) == 0

    def test_whitespace_only_wikilink(self):
        """[[   ]] is not parsed as wikilink."""
        tokens = get_wikilink_tokens("See [[   ]] here")
        assert len(tokens) == 0

    def test_unclosed_wikilink(self):
        """Unclosed [[ is not parsed as wikilink."""
        tokens = get_wikilink_tokens("See [[ Clara here")
        assert len(tokens) == 0

    def test_single_bracket(self):
        """Single [ is not parsed."""
        tokens = get_wikilink_tokens("[not a link]")
        assert len(tokens) == 0

    def test_nested_brackets(self):
        """Nested [[ inside wikilink parses innermost match."""
        tokens = get_wikilink_tokens("See [[a [[b]] c]]")
        # The parser finds the first valid [[...]] which is [[b]]
        assert len(tokens) == 1
        assert tokens[0]["target"] == "b"

    def test_wikilink_target_trimmed(self):
        """Whitespace around target is trimmed."""
        tokens = get_wikilink_tokens("[[  Clara Dupont  ]]")
        assert tokens[0]["target"] == "Clara Dupont"

    def test_wikilink_with_special_chars(self):
        """Target can contain hyphens, dots, accents."""
        tokens = get_wikilink_tokens("[[María José]] and [[2024-11-08]]")
        assert len(tokens) == 2
        assert tokens[0]["target"] == "María José"
        assert tokens[1]["target"] == "2024-11-08"


class TestHTMLRendering:
    """Tests for default HTML rendering of wikilinks."""

    def test_renders_as_anchor(self):
        """Wikilinks render as <a> tags with data-wikilink attribute."""
        md = MarkdownIt().use(wikilink_plugin)
        html = md.render("See [[Clara Dupont]]")
        assert 'data-wikilink="true"' in html
        assert 'href="Clara Dupont"' in html
        assert ">Clara Dupont</a>" in html

    def test_display_text_in_render(self):
        """Display text appears as anchor text."""
        md = MarkdownIt().use(wikilink_plugin)
        html = md.render("[[Clara Dupont|Clara]]")
        assert 'href="Clara Dupont"' in html
        assert ">Clara</a>" in html


class TestExtractWikilinks:
    """Tests for the extract_wikilinks helper function."""

    def test_extract_simple(self):
        """Extract returns structured dicts."""
        md = MarkdownIt().use(wikilink_plugin)
        links = extract_wikilinks(md, "See [[Clara]] and [[Majo]]")
        assert len(links) == 2
        assert links[0]["target"] == "Clara"
        assert links[0]["display"] == "Clara"
        assert links[1]["target"] == "Majo"

    def test_extract_with_display_text(self):
        """Extract preserves display text."""
        md = MarkdownIt().use(wikilink_plugin)
        links = extract_wikilinks(md, "[[Clara Dupont|Clara]]")
        assert links[0]["target"] == "Clara Dupont"
        assert links[0]["display"] == "Clara"

    def test_extract_from_multiline(self):
        """Extract handles multiline text."""
        md = MarkdownIt().use(wikilink_plugin)
        text = "Line 1 [[Clara]]\n\nLine 3 [[Majo]]"
        links = extract_wikilinks(md, text)
        assert len(links) == 2

    def test_extract_ignores_code(self):
        """Extract skips wikilinks in code blocks."""
        md = MarkdownIt().use(wikilink_plugin)
        text = "Real [[Clara]] and `fake [[Majo]]`"
        links = extract_wikilinks(md, text)
        assert len(links) == 1
        assert links[0]["target"] == "Clara"

    def test_extract_empty_text(self):
        """Extract returns empty list for empty input."""
        md = MarkdownIt().use(wikilink_plugin)
        links = extract_wikilinks(md, "")
        assert links == []

    def test_extract_no_wikilinks(self):
        """Extract returns empty list when no wikilinks present."""
        md = MarkdownIt().use(wikilink_plugin)
        links = extract_wikilinks(md, "Just plain text here.")
        assert links == []

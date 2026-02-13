#!/usr/bin/env python3
"""
mdit_wikilink.py
----------------
Custom markdown-it-py inline rule for wikilink syntax.

Tokenizes ``[[target]]`` and ``[[target|display]]`` patterns as proper
AST nodes instead of relying on regex post-processing. This enables
accurate wikilink detection that respects code blocks, inline code,
and other markdown constructs.

Key Features:
    - Parses ``[[target]]`` as wikilink token with target attribute
    - Parses ``[[target|display]]`` with separate target and display
    - Integrates as standard markdown-it-py inline rule
    - Escaped brackets ``\\[[`` are not treated as wikilinks
    - Wikilinks inside code spans/blocks are naturally ignored by
      markdown-it-py's parsing order

Usage:
    from markdown_it import MarkdownIt
    from dev.wiki.mdit_wikilink import wikilink_plugin

    md = MarkdownIt().use(wikilink_plugin)
    tokens = md.parse("Visit [[Clara Dupont]] today")

    # Access wikilink data via token meta
    for token in tokens[0].children:
        if token.type == "wikilink":
            target = token.meta["target"]
            display = token.meta.get("display", target)

Dependencies:
    - markdown-it-py >= 3.0.0
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Any, List, Optional, Sequence

# --- Third-party imports ---
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline


def wikilink_plugin(md: MarkdownIt) -> None:
    """
    Register the wikilink inline rule with a MarkdownIt instance.

    Adds parsing for ``[[target]]`` and ``[[target|display]]`` syntax.
    The rule runs at the inline level, so wikilinks inside code spans
    or code blocks are automatically excluded by markdown-it-py's
    built-in parsing order.

    Args:
        md: MarkdownIt instance to extend
    """
    md.inline.ruler.push("wikilink", _wikilink_rule)
    md.add_render_rule("wikilink", _wikilink_render)


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    """
    Inline rule that matches ``[[target]]`` and ``[[target|display]]``.

    Scans from the current position for opening ``[[``, finds the
    matching ``]]``, and optionally splits on ``|`` for display text.
    Creates a ``wikilink`` token with ``meta`` containing ``target``
    and optionally ``display``.

    Args:
        state: Current inline parser state
        silent: If True, only check for match without creating tokens

    Returns:
        True if a wikilink was matched, False otherwise
    """
    pos = state.pos
    maximum = state.posMax
    src = state.src

    # Need at least [[ + 1 char + ]]
    if pos + 4 > maximum:
        return False

    # Must start with [[
    if src[pos] != "[" or src[pos + 1] != "[":
        return False

    # Check for escaped opening bracket
    if pos > 0 and src[pos - 1] == "\\":
        return False

    # Find closing ]]
    start = pos + 2
    close_pos = src.find("]]", start)

    if close_pos == -1 or close_pos > maximum:
        return False

    # Extract inner content
    inner = src[start:close_pos]

    # Must have content
    if not inner.strip():
        return False

    # Must not contain newlines
    if "\n" in inner:
        return False

    # Must not contain nested [[
    if "[[" in inner:
        return False

    if silent:
        return True

    # Parse target and optional display text
    if "|" in inner:
        parts = inner.split("|", 1)
        target = parts[0].strip()
        display = parts[1].strip()
    else:
        target = inner.strip()
        display = target

    # Create token
    token = state.push("wikilink", "", 0)
    token.content = display
    token.meta = {"target": target, "display": display}
    token.markup = "[["

    # Advance position past ]]
    state.pos = close_pos + 2

    return True


def _wikilink_render(
    self: Any,
    tokens: Sequence[Any],
    idx: int,
    options: Any,
    env: Any,
) -> str:
    """
    Default HTML render rule for wikilink tokens.

    Renders wikilinks as ``<a>`` tags with a ``data-wikilink`` attribute.
    In practice, wiki pages use custom renderers, but this provides a
    reasonable default for testing and HTML preview.

    Args:
        self: Renderer instance
        tokens: Token sequence
        idx: Index of current token
        options: Render options
        env: Environment dict

    Returns:
        HTML string for the wikilink
    """
    token = tokens[idx]
    target = token.meta["target"]
    display = token.meta["display"]
    return f'<a href="{target}" data-wikilink="true">{display}</a>'


def extract_wikilinks(md: MarkdownIt, text: str) -> List[dict]:
    """
    Extract all wikilinks from markdown text as structured dicts.

    Parses the text with the wikilink plugin and collects all wikilink
    tokens into a list of dicts with ``target``, ``display``, and
    ``line`` keys.

    Args:
        md: MarkdownIt instance with wikilink_plugin enabled
        text: Markdown text to parse

    Returns:
        List of dicts with keys: target, display, line

    Usage:
        md = MarkdownIt().use(wikilink_plugin)
        links = extract_wikilinks(md, "See [[Clara|Clara D.]] and [[Majo]]")
        # [{"target": "Clara", "display": "Clara D.", "line": 0},
        #  {"target": "Majo", "display": "Majo", "line": 0}]
    """
    tokens = md.parse(text)
    wikilinks: List[dict] = []

    for token in tokens:
        if token.children:
            for child in token.children:
                if child.type == "wikilink":
                    wikilinks.append({
                        "target": child.meta["target"],
                        "display": child.meta["display"],
                        "line": token.map[0] if token.map else 0,
                    })

    return wikilinks

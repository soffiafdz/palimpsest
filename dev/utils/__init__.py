"""
Utilities package for Palimpsest project.

This package provides commonly-used utilities organized by domain:
- md: Markdown manipulation (sections, links, YAML, frontmatter)
- fs: Filesystem operations and date parsing
- parsers: Name, location, and context extraction
- wiki: Wiki file parsing for database import
- txt: Text formatting and metrics

Import commonly-used utilities directly from this package:
    from dev.utils import split_frontmatter, get_file_hash, extract_context_refs

Or import specific modules:
    from dev.utils import md, fs, parsers, wiki, txt
"""

# Markdown and YAML utilities
from .md import (
    split_frontmatter,
    yaml_escape,
    yaml_list,
    yaml_multiline,
    get_text_hash,
    read_entry_body,
    generate_placeholder_body,
    extract_section,
    get_all_headers,
    parse_bullets,
    extract_yaml_front_matter,
    relative_link,
    resolve_relative_link,
    find_section_line_indexes,
    update_section,
)

# Filesystem utilities
from .fs import (
    find_markdown_files,
    should_skip_file,
    get_file_hash,
    parse_date_from_filename,
    date_to_filename,
)

# Parser utilities
from .parsers import (
    extract_name_and_expansion,
    extract_context_refs,
    format_person_ref,
    format_location_ref,
    parse_date_context,
    split_hyphenated_to_spaces,
    spaces_to_hyphenated,
)

# Wiki parsing utilities (for wiki→database import)
# Note: Section extraction functions moved to md.py

# Text processing utilities
from .txt import (
    ordinal,
    format_body,
    reflow_paragraph,
    compute_metrics,
)

__all__ = [
    # Markdown/YAML
    "split_frontmatter",
    "yaml_escape",
    "yaml_list",
    "yaml_multiline",
    "get_text_hash",
    "read_entry_body",
    "generate_placeholder_body",
    # Filesystem
    "find_markdown_files",
    "should_skip_file",
    "get_file_hash",
    "parse_date_from_filename",
    "date_to_filename",
    # Parsers
    "extract_name_and_expansion",
    "extract_context_refs",
    "format_person_ref",
    "format_location_ref",
    "parse_date_context",
    "split_hyphenated_to_spaces",
    "spaces_to_hyphenated",
    # Wiki
    "extract_section",
    "get_all_headers",
    "parse_bullets",
    "extract_yaml_front_matter",
    "relative_link",
    "resolve_relative_link",
    "find_section_line_indexes",
    "update_section",
    # Text
    "ordinal",
    "format_body",
    "reflow_paragraph",
    "compute_metrics",
]

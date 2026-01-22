#!/usr/bin/env python3
"""
format_yaml.py
--------------
Automated formatter for narrative analysis YAML files.

Applies consistent formatting rules:
- Quote date field (when necessary)
- Remove unnecessary quotes from strings
- Use >- block scalars for long content (>80 chars per line)
- Auto-wrap long lines at natural boundaries (periods, commas)
- Convert md_frontmatter arrays to block style
- Remove empty arrays/lists
- Fix arc quote consistency

Custom YAML writer to format >- blocks without extra blank lines.

Usage:
    python format_yaml.py <file_or_directory>
    python format_yaml.py narrative_analysis/2025/  # format all files
    python format_yaml.py narrative_analysis/2025/2025-01-11_analysis.yaml  # single file
"""

import sys
from pathlib import Path
from textwrap import TextWrapper
from typing import Any, Dict, List

import yaml


class YAMLFormatter:
    """Formats narrative analysis YAML files according to project standards."""

    def __init__(self):
        """Initialize formatter with text wrapper."""
        self.wrapper = TextWrapper(
            width=80,
            break_long_words=False,
            break_on_hyphens=False,
        )

    def clean_list_item(self, item: str) -> str:
        """
        Clean stray quotes and commas from list items.

        Args:
            item: List item string

        Returns:
            Cleaned string
        """
        # Remove trailing comma
        if item.endswith(","):
            item = item[:-1].strip()

        # Remove stray trailing quote (not matching opening quote)
        if item.endswith('"') and not item.startswith('"'):
            item = item[:-1].strip()
        elif item.endswith("'") and not item.startswith("'"):
            item = item[:-1].strip()

        return item

    def clean_list(self, items: List[Any]) -> List[Any]:
        """
        Clean all items in a list.

        Args:
            items: List of items

        Returns:
            Cleaned list
        """
        if not items:
            return items

        return [self.clean_list_item(item) for item in items]

    def remove_empty_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove empty arrays and None values from dictionary.

        Args:
            data: Dictionary to clean

        Returns:
            Cleaned dictionary
        """
        cleaned = {}
        for key, value in data.items():
            # Skip empty lists/arrays
            if isinstance(value, list) and len(value) == 0:
                continue

            # Skip None values
            if value is None:
                continue

            # Recurse into nested dicts
            if isinstance(value, dict):
                value = self.remove_empty_fields(value)
                if value:
                    cleaned[key] = value

            # Recurse into lists of dicts
            elif isinstance(value, list):
                cleaned_list = []
                for item in value:
                    if isinstance(item, dict):
                        item = self.remove_empty_fields(item)
                        if item:
                            cleaned_list.append(item)
                    else:
                        cleaned_list.append(item)
                if cleaned_list:
                    cleaned[key] = cleaned_list
            else:
                cleaned[key] = value

        return cleaned

    def wrap_text(self, text: str) -> str:
        """
        Wrap long text at natural boundaries for YAML readability.

        Preserves paragraph breaks (double newlines) while wrapping long lines.

        Args:
            text: Original text

        Returns:
            Wrapped text with single newlines between wrapped lines,
            double newlines between paragraphs
        """
        # Split into paragraphs
        paragraphs = text.split("\n\n")
        wrapped_pars = []

        for par in paragraphs:
            # Remove existing single newlines within paragraph
            par = " ".join(par.split())

            # Wrap if needed
            if len(par) > 80:
                wrapped = self.wrapper.wrap(par)
                wrapped_pars.append("\n".join(wrapped))
            else:
                wrapped_pars.append(par)

        # Join paragraphs with double newlines
        return "\n\n".join(wrapped_pars)

    def should_use_block_scalar(self, text: str) -> bool:
        """
        Determine if text should use block scalar format.

        Args:
            text: Text to check

        Returns:
            True if should use >- format
        """
        # Use block scalar if long or has paragraph breaks
        return len(text) > 80 or "\n\n" in text or '"' in text

    def format_block_scalar_inline(
        self, text: str, base_indent: int, key_indent: int
    ) -> str:
        """
        Format text as >- block scalar inline with a key.

        For use in "key: >-\n  content" format.

        Args:
            text: Text to format
            base_indent: Base indentation level (where the key starts)
            key_indent: Additional indent for content (usually 2)

        Returns:
            Formatted block scalar string starting with >-
        """
        wrapped = self.wrap_text(text)
        lines = wrapped.split("\n")

        # Content should be indented relative to the key
        content_indent_str = " " * (base_indent + key_indent)
        formatted_lines = [">-"]

        for line in lines:
            formatted_lines.append(f"{content_indent_str}{line}")

        return "\n".join(formatted_lines)

    def format_value(self, value: Any, indent: int = 2) -> str:
        """
        Format a value for YAML output.

        Args:
            value: Value to format
            indent: Current indentation level

        Returns:
            Formatted value string
        """
        if value is None:
            return ""
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Check if needs block scalar
            if self.should_use_block_scalar(value):
                return self.format_block_scalar_inline(value, indent, indent)
            # Check if needs quotes (add quotes check and dash-space combo)
            elif (
                '"' in value
                or ":" in value
                or "#" in value
                or " - " in value
                or value.startswith(("*", "&", "!", "|", ">", "@", "`", "-", "[", "{"))
            ):
                # Escape internal quotes and backslashes
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            else:
                return value
        elif isinstance(value, list):
            return self.format_list(value, indent)
        elif isinstance(value, dict):
            return self.format_dict(value, indent)
        else:
            return str(value)

    def format_list(self, items: List[Any], indent: int = 0) -> str:
        """
        Format a list for YAML output.

        Args:
            items: List to format
            indent: Current indentation level

        Returns:
            Formatted list string
        """
        if not items:
            return "[]"

        indent_str = " " * indent
        lines = []

        for item in items:
            if isinstance(item, dict):
                # Format dict item - first key on same line as dash
                dict_lines = []
                first = True
                for key, value in item.items():
                    if isinstance(value, str) and self.should_use_block_scalar(value):
                        # Block scalar value
                        if first:
                            # First key on same line as dash: "- key: >-"
                            # Content indented from the indent position
                            block_str = self.format_block_scalar_inline(
                                value, indent + 2, 2
                            )
                            dict_lines.append(f"{indent_str}- {key}: {block_str}")
                            first = False
                        else:
                            # Subsequent keys: "  key: >-"
                            # Content indented from the key position
                            block_str = self.format_block_scalar_inline(
                                value, indent + 2, 2
                            )
                            dict_lines.append(f"{indent_str}  {key}: {block_str}")
                    elif isinstance(value, list):
                        # List value
                        list_str = self.format_list(value, indent + 4)
                        if first:
                            dict_lines.append(f"{indent_str}- {key}:{list_str}")
                            first = False
                        else:
                            dict_lines.append(f"{indent_str}  {key}:{list_str}")
                    elif isinstance(value, dict):
                        # Nested dict value
                        nested_dict_str = self.format_dict(value, indent + 4)
                        if first:
                            dict_lines.append(
                                f"{indent_str}- {key}:\n{nested_dict_str}"
                            )
                            first = False
                        else:
                            dict_lines.append(
                                f"{indent_str}  {key}:\n{nested_dict_str}"
                            )
                    else:
                        # Simple value
                        formatted_val = self.format_value(value, indent + 4)
                        if first:
                            dict_lines.append(f"{indent_str}- {key}: {formatted_val}")
                            first = False
                        else:
                            dict_lines.append(f"{indent_str}  {key}: {formatted_val}")
                lines.extend(dict_lines)
            elif isinstance(item, str):
                # Simple string item
                if ":" in item or item.startswith("-"):
                    lines.append(f'{indent_str}- "{item}"')
                else:
                    lines.append(f"{indent_str}- {item}")
            else:
                lines.append(f"{indent_str}- {item}")

        return "\n" + "\n".join(lines)

    def format_dict(self, data: Dict[str, Any], indent: int = 0) -> str:
        """
        Format a dictionary for YAML output.

        Args:
            data: Dictionary to format
            indent: Current indentation level

        Returns:
            Formatted dictionary string
        """
        if not data:
            return "{}"

        indent_str = " " * indent
        lines = []

        for key, value in data.items():
            if isinstance(value, str) and self.should_use_block_scalar(value):
                # Block scalar on next line
                block_str = self.format_block_scalar_inline(value, indent, 2)
                lines.append(f"{indent_str}{key}: {block_str}")
            elif isinstance(value, list):
                if not value:
                    continue  # Skip empty lists
                list_str = self.format_list(value, indent + 2)
                lines.append(f"{indent_str}{key}:{list_str}")
            elif isinstance(value, dict):
                if not value:
                    continue  # Skip empty dicts
                dict_str = self.format_dict(value, indent + 2)
                lines.append(f"{indent_str}{key}:\n{dict_str}")
            else:
                formatted_val = self.format_value(value, indent + 2)
                lines.append(f"{indent_str}{key}: {formatted_val}")

        return "\n".join(lines)

    def format_scenes(self, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format scene entries."""
        if not scenes:
            return scenes

        formatted = []
        for scene in scenes:
            scene = self.remove_empty_fields(scene)
            # Ensure date is string
            if "date" in scene:
                if isinstance(scene["date"], list):
                    scene["date"] = [str(d) for d in scene["date"]]
                else:
                    scene["date"] = str(scene["date"])
            formatted.append(scene)

        return formatted

    def format_threads(self, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format thread entries."""
        if not threads:
            return threads

        formatted = []
        for thread in threads:
            thread = self.remove_empty_fields(thread)
            # Convert dates to strings
            for date_field in ["from", "to", "entry"]:
                if date_field in thread:
                    thread[date_field] = str(thread[date_field])
            formatted.append(thread)

        return formatted

    def format_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format event entries (only name and scenes fields)."""
        if not events:
            return events

        formatted = []
        for event in events:
            cleaned = {}
            if "name" in event:
                cleaned["name"] = event["name"]
            if "scenes" in event:
                cleaned["scenes"] = event["scenes"]
            formatted.append(cleaned)

        return formatted

    def format_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply all formatting rules to a document.

        Args:
            data: Parsed YAML document

        Returns:
            Formatted document
        """
        # Convert date to string
        if "date" in data:
            data["date"] = str(data["date"])

        # Clean arcs (remove stray quotes/commas)
        if "arcs" in data and isinstance(data["arcs"], list):
            data["arcs"] = self.clean_list(data["arcs"])

        # Clean tags
        if "tags" in data and isinstance(data["tags"], list):
            data["tags"] = self.clean_list(data["tags"])

        # Format scenes
        if "scenes" in data:
            data["scenes"] = self.format_scenes(data["scenes"])

        # Format threads
        if "threads" in data:
            data["threads"] = self.format_threads(data["threads"])

        # Format events
        if "events" in data:
            data["events"] = self.format_events(data["events"])

        # Clean md_frontmatter lists
        if "md_frontmatter" in data:
            for key in [
                "arcs",
                "tags",
                "themes",
                "motifs",
                "scenes",
                "events",
                "threads",
            ]:
                if key in data["md_frontmatter"] and isinstance(
                    data["md_frontmatter"][key], list
                ):
                    data["md_frontmatter"][key] = self.clean_list(
                        data["md_frontmatter"][key]
                    )

        # Remove empty fields
        data = self.remove_empty_fields(data)

        return data

    def format_file(self, file_path: Path) -> bool:
        """
        Format a single YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read file
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                print(f"⚠️  Skipping empty file: {file_path}")
                return False

            # Apply formatting
            formatted_data = self.format_document(data)

            # Write with custom formatter
            with open(file_path, "w", encoding="utf-8") as f:
                formatted_yaml = self.format_dict(formatted_data)
                f.write(formatted_yaml)
                f.write("\n")

            print(f"✓ Formatted: {file_path}")
            return True

        except Exception as e:
            print(f"✗ Error formatting {file_path}: {e}")
            import traceback

            traceback.print_exc()
            return False

    def format_directory(
        self, dir_path: Path, pattern: str = "**/*.yaml"
    ) -> tuple[int, int]:
        """
        Format all YAML files in a directory (recursively).

        Args:
            dir_path: Directory path
            pattern: File pattern to match (default: **/*.yaml for recursive)

        Returns:
            Tuple of (success_count, failure_count)
        """
        success = 0
        failure = 0

        for file_path in sorted(dir_path.glob(pattern)):
            if file_path.is_file():
                if self.format_file(file_path):
                    success += 1
                else:
                    failure += 1

        return success, failure


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python format_yaml.py <file_or_directory>")
        print("Example: python format_yaml.py narrative_analysis/2025/")
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        sys.exit(1)

    formatter = YAMLFormatter()

    if path.is_file():
        # Format single file
        success = formatter.format_file(path)
        sys.exit(0 if success else 1)
    elif path.is_dir():
        # Format directory
        print(f"Formatting YAML files in: {path}")
        success, failure = formatter.format_directory(path)
        print(f"\n{'='*50}")
        print(f"✓ Success: {success}")
        print(f"✗ Failure: {failure}")
        print(f"{'='*50}")
        sys.exit(0 if failure == 0 else 1)
    else:
        print(f"Error: Not a file or directory: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

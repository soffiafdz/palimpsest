#!/usr/bin/env python3
"""
format_yaml.py
--------------
CLI wrapper for the YAML formatter utility.

Applies consistent formatting to narrative analysis YAML files using
the YAMLFormatter class from dev.utils.yaml_formatter.

Usage:
    python format_yaml.py <file_or_directory>
    python format_yaml.py narrative_analysis/2025/  # format all files
    python format_yaml.py narrative_analysis/2025/2025-01-11_analysis.yaml  # single file
"""

import sys
from pathlib import Path

from dev.utils.yaml_formatter import YAMLFormatter


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

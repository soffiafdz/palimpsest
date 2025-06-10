#!/usr/bin/env python3
"""
txt2md.py
-------------------
Scan pre-cleaned 750words .txt (monthly) exports.
Generate daily Markdown files for Vimwiki reference and PDF generation.

    journal/
    ├── txt/
    │   └── <YYYY>
    │       └── <YYYY-MM>.md
    └── md/
        └── <YYYY>
            └── <YYYY-MM-DD>.md
Notes
==============
- Manages two types of 750w metadata entry formats.
- Adds YAML front-matter metadata entries to be filled after review.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import List

# --- Local imports ---
from scripts.paths import ROOT, MD_DIR
from scripts.txt2md.txt_entry import TxtEntry


# ----- Argument parser -----
def parse_args() -> argparse.Namespace:
    """
    Arguments:
        - input: Pre-cleaned monthly .txt export.
        - outdir: Directory to save the yearly directory with Markdown entries.
        - clobber: Overwrite existing files.
        - verbose: Logging.
    """
    p = argparse.ArgumentParser(
        description="Convert pre-cleaned .txt into per-entry Markdown files"
    )

    # --- ARGUMENTS ---
    p.add_argument(
        "-i", "--input", required=True,
        help="Path to pre-cleaned .txt file"
    )
    p.add_argument(
        "-o", "--outdir",
        default=str(MD_DIR),
        help=f"Root dir for output (default: {str(MD_DIR)})"
    )
    p.add_argument(
        "-f", "--force", "--clobber",
        action="store_true",
        help="Overwrite existing markdown files (quiet skip otherwise)"
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    return p.parse_args()


# ----- Main -----
def main() -> None:
    """
    CLI entrypoint:
      - parses --input and --output arguments
      - reads and ftfy-cleans the input file
      - splits into entries, extracts headers & bodies
      - formats bodies, groups into paragraphs
      - reflows prose paras, preserves soft-break paras
      - calculates metadata
      - writes the resulting Markdown to output
    """
    try:
        args = parse_args()
        input  = Path(args.input)
        outdir = Path(args.outdir)
        verbose  = args.verbose
        if verbose:
            print(f"→  Project root:    {str(ROOT)}")
            print(f"→  Reading from:    {str(input)}")
            print(f"→  Writing to root: {str(outdir)}")


        # --- Failsafes ---
        if not input.exists():
            raise FileNotFoundError(f"Input not found: {str(input)}")
        if not input.is_file() or not os.access(str(input), os.R_OK):
            raise OSError(f"Cannot read input file: {str(input)}")
        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise OSError(f"Error creating output dir {str(outdir)}: {e}")
        if not outdir.is_dir() or not os.access(outdir, os.W_OK):
            raise OSError(f"Cannot write to {str(outdir)}")

        # --- Process ---
        if verbose:
            print("→  Cleaning text and splitting into entries...")

        txt_entries: List[TxtEntry] = TxtEntry.from_file(input, verbose=verbose)
        if verbose:
            print(f"→  Found {len(txt_entries)} entries in {input.name}")

        for txt_entry in txt_entries:
            if txt_entry.date is None:
                warnings.warn(
                    "Warning: skipping entry with no date",
                    UserWarning
                )
                continue

            if verbose:
                print(f"→  Processing entry dated {txt_entry.date.isoformat()}")

            # --- OUTPUT ---
            # Write to {outdir}/<year>/YYYY-MM-DD.md
            year_dir: Path = outdir / str(txt_entry.date.year)
            year_dir.mkdir(parents=True, exist_ok=True)
            out_file: Path = year_dir / f"{txt_entry.date.isoformat()}.md"

            if out_file.exists() and not args.force:
                warnings.warn(
                    f"Warning: {out_file.name} exists, skipping",
                    UserWarning
                )
                continue

            if verbose:
                action = "Overwriting" if out_file.exists() else "Writing"
                print(f"→  {action} file: {out_file.name}")

            try:
                out_file.write_text(txt_entry.to_markdown(), encoding="utf-8")
            except Exception as e:
                raise OSError(f"Error writing to {str(out_file)}: {e}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"OS error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()

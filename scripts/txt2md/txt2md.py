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
    ├── md/
    │   └── <YYYY>
    │       └── <YYYY-MM-DD>.md
    └── md/
Notes
==============
- Manages two types of 750w metadata entry formats.
- Loads metadata from a JSON registry.
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
    p.add_argument("-i", "--input", required=True, help="Path to pre-cleaned .txt file")
    p.add_argument(
        "-o",
        "--outdir",
        default=str(MD_DIR),
        help=f"Root dir for output (default: {str(MD_DIR)})",
    )
    # p.add_argument(
    #     "-m",
    #     "--metadata",
    # default=str(METADATA_JSON),
    #     help=f"Path for metadata JSON file (default: {str(METADATA_JSON)})",
    # )
    p.add_argument(
        "-f",
        "--force",
        "--clobber",
        action="store_true",
        help="Overwrite existing markdown files (quiet skip otherwise)",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
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
      - calculates word count & reading time
      - loads metadata from registry
      - writes the resulting Markdown to output
    """
    try:
        args = parse_args()
        input = Path(args.input)
        # meta = Path(args.metadata)
        outdir = Path(args.outdir)
        verbose = args.verbose
        if verbose:
            print(f"[TxtEntry] →  Project root:    {str(ROOT)}")
            print(f"[TxtEntry] →  Reading from:    {str(input)}")
            # print(f"[TxtEntry] →  Metadata from:   {str(meta)}")
            print(f"[TxtEntry] →  Writing to root: {str(outdir)}")

        # --- Failsafes ---
        if not input.exists():
            raise FileNotFoundError(f"Input not found: {str(input)}")
        if not input.is_file() or not os.access(str(input), os.R_OK):
            raise OSError(f"Cannot read input file: {str(input)}")
        # if not meta.is_file() or not os.access(str(meta), os.R_OK):
        #     warnings.warn("Warning: metadata file not found", UserWarning)
        #     meta = None
        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise OSError(f"Error creating output dir {str(outdir)}: {e}")
        if not outdir.is_dir() or not os.access(outdir, os.W_OK):
            raise OSError(f"Cannot write to {str(outdir)}")

        # --- Process ---
        if verbose:
            print("[TxtEntry] → Cleaning text and splitting into entries...")

        # registry: MetadataRegistry | None = None
        # if meta is not None:
        #     registry = MetadataRegistry(meta)
        #     if registry and verbose:
        #         print(f"[TxtEntry] →  Metadata file loaded from {str(meta)}")

        txt_entries: List[TxtEntry] = TxtEntry.from_file(
            # input, metadata_registry=registry, verbose=verbose
            input,
            metadata_registry=None,
            verbose=verbose,
        )

        if verbose:
            print(f"[TxtEntry] →  Found {len(txt_entries)} entries in {input.name}")

        for txt_entry in txt_entries:
            if txt_entry.date is None:
                warnings.warn("Warning: skipping entry with no date", UserWarning)
                continue

            if verbose:
                print(
                    f"[TxtEntry] →  Processing entry dated {txt_entry.date.isoformat()}"
                )

            # Load metadata from JSON registry
            # if registry:
            #     txt_entry.load_metadata(registry, verbose=verbose)

            # --- OUTPUT ---
            # Write to {outdir}/<year>/YYYY-MM-DD.md
            try:
                year_dir: Path = outdir / str(txt_entry.date.year)
                year_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise OSError(f"Error writing {str(year_dir)}: {e}")

            out_file: Path = year_dir / f"{txt_entry.date.isoformat()}.md"

            if out_file.exists() and not args.force:
                warnings.warn(f"Warning: {out_file.name} exists, skipping", UserWarning)
                continue

            if verbose:
                action = "Overwriting" if out_file.exists() else "Writing"
                print(f"[TxtEntry] →  {action} file: {out_file.name}")

            try:
                out_file.write_text(txt_entry.to_markdown(), encoding="utf-8")
            except Exception as e:
                raise OSError(f"Error writing to {str(out_file)}: {e}")

    # --- Exceptions ---
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

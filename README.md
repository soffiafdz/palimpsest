# Palimpsest

**Private writing archive and manuscript workspace.**

This repository contains the archival, curatorial, and editorial infrastructure
for an ongoing hybrid memoir project currently titled _What wasn't said_.
It is built atop more than a decade of daily journals (2015–present)
and is being shaped into a book-length manuscript that blends autobiographical
fragments, personal essay, and autofiction.

---

## What this is

- A structured **journal archive**:
originally exported from [750words.com](https://750words.com), now converted to
yearly Markdown files and tablet-ready PDFs for annotation.
- A **curation and revision workspace**:
fragments are extracted, rewritten, and developed into vignettes inside
a standalone `vignettes/` directory.
- A **manuscript scaffolding system**:
including thematic cross-referencing, character mapping, section/chapter
outlines, and a tracked inventory of what is kept, cut, or rewritten.

The project uses a Vim-native writing workflow and custom scripts for managing
format conversions and editorial tracking.

---

## Directory Structure

- `bin/` - Standalone scripts/utilities
- `journal/` - Source material (personal journal)
  - `annotations/` - Marked PDFs
  - `archive/` - Compressed original 750words daily text exports
  - `inbox/` - Where to download 750words exports to be processed
  - `latex/` - Preamble style LaTeX files for compiling PDFs
  - `md/` – Markdown files generated via `txt2md.py` containing Metadata.
  - `pdf/` – Printable/annotatable PDFs
  - `txt/` – Pre-cleaned text exports by year
- `Makefile` – Custom build system for txt→md→pdf, plus tagging and cleaning
- `scripts/` – Conversion and inventory scaffolding tools
- `vignettes/` – Curated, rewritten excerpts for potential manuscript inclusion
- `wiki/` – Internal documentation and planning:
  - `index.md` – Dashboard hub
  - `inventory.md` – Checklist of reviewed entries
  - `log\{YYYY-MM-DD.md}` - Log entries
  - `structure.md` – Book outline (sections → chapters → vignettes)
  - `themes.md`, `tags.md`, `people.md`, `timeline.md` – Supporting documents

---

## Toolchain

**Core plugins:**
- `vimwiki/vimwiki`
- `nvim-telescope/telescope.nvim` (+ `fzf-native`, `telescope-vimwiki`)
- `nvim-lua/plenary.nvim`

**Utility plugins:**
- `tpope/vim-fugitive`
- `junegunn/goyo.vim`

**External tools:**
- `ripgrep`, `fd`, `make`, `pandoc`, `xelatex`, `python3`

---

## Keyboard Shortcuts (Vim)

- `<Leader>ww` → Open main page `wiki/index.md`
- `<Leader>wi` → Open log index `wiki/log/index.md`
- `<Leader>w<Leader>w` → Open current day log entry
- `<Leader>f` → Telescope picker for any wiki file
- `<Leader>v` → Telescope picker for `vignettes/`
- `<Leader>g` → Live-grep inside wiki
- `<Leader>zz` → Toggle distraction-free mode (`goyo.vim`)
- `<Leader>gs` → Git status in root (via `vim-fugitive`)

---

## Usage Overview

1. `make {YEAR}` → Convert raw text to Markdown/PDF.
2. Annotate on tablet or desktop; update `inventory.md`.
3. Curate fragments into `vignettes/`, tag and outline structure.
4. Iterate on narrative arc, rewrite vignettes, typeset manuscript.

Optional tasks: create final Typst file, build CI integration, select image inserts.

---

## About the name

A *palimpsest* is a manuscript that has been scraped or washed clean so it can
be reused—yet beneath the surface, traces of the original text remain. This
project carries that spirit: overwritten memory, persistent ghosts, rewritten
selves.

---

## License

The contents of this repository are licensed under the **Creative Commons
Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)**
license.

[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-nd/4.0/)
This means you may not use, share, or build upon this work without explicit
permission.

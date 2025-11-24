# Palimpsest Command Reference

Complete reference for all available commands in the Palimpsest system.

## Available Commands

Palimpsest provides **5 command-line entry points**:

1. **`plm`** - Main pipeline commands (inbox, convert, sync-db, export-db, export-wiki, import-wiki, build-pdf, etc.)
2. **`metadb`** - Database management (init, backup, health, migrations, etc.)
3. **`jsearch`** - Full-text search with advanced filtering
4. **`jai`** - AI-assisted analysis (optional, requires AI dependencies)
5. **`validate`** - Validation tools for wiki, database, and entries

Plus **`make`** commands for high-level batch operations.

---

## Installation

All commands are installed via pip as entry points:

```bash
# Install package with all entry points
pip install -e .

# Or use make
make install

# Development mode
make install-dev
```

This installs these executables in `~/.local/bin/`:
- `plm`
- `metadb`
- `jsearch`
- `jai`
- `validate`

Ensure `~/.local/bin` is in your PATH.

---

## Quick Reference

| Task | Command |
|------|---------|
| Process new entries | `plm inbox && plm convert && plm sync-db` |
| Build PDFs | `plm build-pdf 2024` |
| Search entries | `jsearch "query" person:alice in:2024` |
| AI analysis | `jai analyze 2024-11-01 --level 2` |
| Export to wiki | `plm export-wiki` |
| Import from wiki | `plm import-wiki` |
| Database backup | `metadb backup` |
| Full pipeline | `plm run-all --year 2024` or `make 2024` |
| Check status | `plm status` or `metadb health` |
| Validate wiki | `validate wiki stats` |

---

## See Full Documentation

Run `--help` on any command for complete options:

```bash
plm --help
plm convert --help
plm export-wiki --help
plm import-wiki --help
metadb --help
metadb backup --help
jsearch --help
jai --help
validate --help
```

---

## Environment Variables

```bash
# For AI Level 4 (optional)
export ANTHROPIC_API_KEY='your-claude-api-key'  # For Claude
export OPENAI_API_KEY='your-openai-api-key'     # For OpenAI
```

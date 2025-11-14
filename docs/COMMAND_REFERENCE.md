# Palimpsest Command Reference

Complete reference for all available commands in the Palimpsest system.

## Available Commands

Palimpsest provides **6 command-line entry points**:

1. **`plm`** - Main pipeline commands (inbox, convert, sync, build PDFs, etc.)
2. **`metadb`** - Database management (init, backup, health, migrations, etc.)
3. **`plm-search`** - Full-text search with advanced filtering
4. **`plm-ai`** - AI-assisted analysis (optional, requires AI dependencies)
5. **`plm-wiki-export`** - Export database to wiki pages
6. **`plm-wiki-import`** - Import wiki edits back to database

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
- `plm-search`
- `plm-ai`
- `plm-wiki-export`
- `plm-wiki-import`

Ensure `~/.local/bin` is in your PATH.

---

## Quick Reference

| Task | Command |
|------|---------|
| Process new entries | `plm inbox && plm convert && plm sync-db` |
| Build PDFs | `plm build-pdf 2024` |
| Search entries | `plm-search "query" person:alice in:2024` |
| AI analysis | `plm-ai analyze 2024-11-01 --level 2` |
| Export to wiki | `plm-wiki-export export all` |
| Import from wiki | `plm-wiki-import import all` |
| Database backup | `metadb backup` |
| Full pipeline | `plm run-all --year 2024` or `make 2024` |
| Check status | `plm status` or `metadb health` |

---

## See Full Documentation

Run `--help` on any command for complete options:

```bash
plm --help
plm convert --help
metadb --help
metadb backup --help
plm-search --help
plm-ai --help
plm-wiki-export --help
plm-wiki-import --help
```

---

## Environment Variables

```bash
# For AI Level 4 (optional)
export ANTHROPIC_API_KEY='your-claude-api-key'  # For Claude
export OPENAI_API_KEY='your-openai-api-key'     # For OpenAI
```

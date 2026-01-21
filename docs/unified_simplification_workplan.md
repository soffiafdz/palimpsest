# Unified Simplification Workplan

**Goal:** Reduce codebase complexity while preserving all features

---

## Development Guidelines

- **Commits:** Single-line messages, no AI attribution
- **Testing:** Write tests for new functionality, run `pytest` before committing
- **Docstrings:** Google-style with Args/Returns sections
- **Imports:** Organized sections (Annotations, Standard library, Third party, Local)

---

## What NOT to Remove

1. Multi-machine sync capabilities (tombstones, sync state)
2. Manuscript subsystem
3. Bidirectional wiki sync (notes/vignettes)
4. Any files in `data/` directory

---

## Completed Tasks

| Priority | Task | Lines Saved |
|----------|------|-------------|
| P0 | Delete NLP module | ~2,500 |
| P0.5 | Fix spaces_to_hyphenated data corruption | ~30 |
| P1 | Remove duplicate CLI in validators/wiki.py | ~84 |
| P2 | Add slugify() utility + consolidate parsers | ~65 |
| P3 | Consolidate entity managers (EntityManager base) | ~500 |
| P3.1 | Consolidate CRUD patterns | -550 |
| P3.2 | Generic relationship updater | -150 |
| P3.3 | Delete wrapper methods | ~100 |
| P4 | Simplify health/analytics (data-driven configs) | -114 |
| P4.1 | Consolidate integrity check methods | (in P4) |
| P8 | Generic wiki index builder | -280 |
| P13 | Use safe_logger() codebase-wide | ~140 |
| P25 | Moment model schema | ~50 |
| P26 | Template-based wiki renderer (Jinja2) | -2,750 |
| P27 | Main wiki dashboards | +173 |
| P10 | Replace decorators with DatabaseOperation context manager | ~300 |
| P11 | Utils module consolidation (rename extract_section collision) | ~10 |
| P22 | Remove unused specialized enum normalizers | ~50 |
| P29 | Manuscript wiki configs + export infrastructure | +200 |
| P30 | Manuscript wiki templates (arc, character, entry, event) | +350 |
| P31 | Manuscript CLI integration (export-wiki/import-wiki) | +50 |

**Obsolete (replaced by P26):** P5, P5.1, P5.2, P7.2, P18, P19, P20, P24
**Skipped (marginal gain):** P23 (Database model mixins - common properties only 2 lines each)
**Obsolete (no longer applicable):** P7, P7.1 (no meta-programming found, all import functions used)
**Skipped (marginal gain):** P12, P15, P16 (sync patterns straightforward, ~5 occurrences)
**Obsolete (codebase already clean):** P17 (only 1 unused function found - removed), P21 (search modules logically separate)
**Already done:** P6 (CLI well-organized), P9 (validators domain-specific), P14 (PDF builder uses shared `_build_single_pdf`)

---

## Pending Tasks by Tier

### Tier 6: Manuscript System

✅ **Complete** - All Tier 6 tasks implemented:
- P28: Database schema (ManuscriptEntry, ManuscriptPerson, ManuscriptEvent, Arc, Theme)
- P29: Wiki export configs + EntityConfig for manuscript entities
- P30: Jinja2 templates (arc, character, manuscript_entry, manuscript_event) + index templates
- P31: CLI commands (export-wiki manuscript, import-wiki manuscript-*)

### Tier 7: Manuscript Integration

✅ **Complete** - All Tier 7 tasks resolved:
- P32: Neovim commands updated (export/import/browse manuscript, fzf integration)
- P33: Stats views reconsidered - SQLite doesn't support materialized views, QueryAnalytics already provides comprehensive manuscript analytics

### Tier 9: Final Cleanup

✅ **Complete** - All Tier 9 tasks resolved:
- P34: Neovim plugin enhanced (manuscript browse/search keymaps added)
- P35: Code reorganization reviewed - structure already clean and well-organized

---

## Quick Reference: What to Do Next

**ALL TIERS COMPLETE**

Summary:
- **Simplification**: All high-impact tasks done (~3,500 lines reduced)
- **Tier 6**: Manuscript wiki infrastructure implemented
- **Tier 7**: Neovim integration and analytics reviewed
- **Tier 9**: Final cleanup complete

The workplan is now complete. The codebase is simplified and manuscript features are fully integrated.

---

## Critical Path

```
✅ ALL TIERS COMPLETE
```

All simplification and manuscript integration work is done.

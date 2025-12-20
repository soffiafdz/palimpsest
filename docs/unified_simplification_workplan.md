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

**Obsolete (replaced by P26):** P5, P5.1, P5.2, P7.2, P18, P19, P20, P24

---

## Pending Tasks by Tier

### Tier 3: Core Utilities (Do Next)

| Priority | Task | Lines | Risk | Description |
|----------|------|-------|------|-------------|
| **P22** | Core module cleanup | ~90 | Low | Remove redundant exception helpers |
| **P23** | Database model mixins | ~100 | Very Low | Extract common model properties into mixins |

### Tier 5: Pipeline & Sync

| Priority | Task | Lines | Risk | Description |
|----------|------|-------|------|-------------|
| **P7** | Remove meta-programming in pipeline | ~300 | Medium | Simplify import/export configuration |
| **P7.1** | Delete unused import_* wrappers | ~250 | Low | Remove never-called import functions |
| **P12** | Pipeline file writing helpers | ~40 | Low | Extract common write-if-changed pattern |
| **P15** | Extract sync state helper | ~125 | Medium | Consolidate sync state update patterns |
| **P16** | Extract field update helper | ~100 | Medium | Consolidate field comparison logic |

### Tier 6: Manuscript System

| Priority | Task | Lines | Risk | Description |
|----------|------|-------|------|-------------|
| **P28** | Manuscript database schema | +150 | Medium | ✅ Already implemented |
| **P29** | Manuscript YAML parsing | +100 | Low | Parse manuscript.yaml into database |
| **P30** | Manuscript wiki structure | +300 | Medium | Wiki templates for arcs/characters/themes |
| **P31** | Bidirectional sync config | +150 | Medium | Wiki-to-DB sync for manuscript entities |

### Tier 7: Manuscript Integration

| Priority | Task | Lines | Risk | Depends On |
|----------|------|-------|------|------------|
| **P32** | Neovim manuscript commands | +200 Lua | Low | P28-P31 |
| **P33** | Stats materialized views | +100 SQL | Low | P25, P28 |

### Tier 8: Validators & CLI

| Priority | Task | Lines | Risk | Description |
|----------|------|-------|------|-------------|
| **P6** | Consolidate backup/stats CLI | ~100 | Low | Merge similar CLI commands |
| **P9** | Validator method consolidation | ~160 | Low | Generic validation helpers |
| **P14** | PDF builder consolidation | ~98 | Medium | Merge clean/notes PDF builders |
| **P17** | Delete unused single-entity imports | ~230 | Low | Remove never-called import functions |
| **P21** | Search module consolidation | ~160 | Low | Merge search_engine and search_index |

### Tier 9: Final Cleanup

| Priority | Task | Lines | Risk | Depends On |
|----------|------|-------|------|------------|
| **P34** | Neovim plugin enhancements | +300 Lua | Low | All Python work |
| **P35** | Code reorganization | ~0 | Medium | All above |

---

## Quick Reference: What to Do Next

**Current Focus:** Tier 3 (Core Utilities)

1. **P22** - Low risk: Core cleanup
2. **P23** - Very low risk: Model mixins

After Tier 3, proceed to Tier 5 (Pipeline), then Tier 6-7 (Manuscript), then Tier 8 (Validators), then Tier 9 (Final).

---

## Critical Path

```
Tier 3 (Utilities) → Tier 5 (Pipeline) → Tier 6-7 (Manuscript) → Tier 8 (Validators) → Tier 9 (Final)
```

Each tier can be worked on independently, but completing earlier tiers first avoids rework.

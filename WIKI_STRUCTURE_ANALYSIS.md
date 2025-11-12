# Wiki Directory Structure Analysis

**Project**: Palimpsest — Hybrid Memoir Manuscript Development System
**Analysis Date**: 2025-11-12
**Subject**: `wiki/` directory structural intentions and design philosophy

---

## Executive Summary

The `wiki/` directory functions as a **centralized editorial command center** for transforming a decade-long personal journal archive (2015–2025) into a structured hybrid memoir manuscript titled *"What wasn't said"*. It implements a sophisticated knowledge management system that bridges raw autobiographical material with finished literary work through systematic curation, cross-referencing, and iterative development.

**Core Function**: Transform 380+ raw journal entries into a curated narrative through multi-layered indexing, tracking, and editorial annotation.

---

## Directory Architecture

### Current Structure

```
wiki/
├── index.md              # Central dashboard and navigation hub
├── log/                  # Development diary (meta-journal)
│   ├── index.md          # Chronological log index
│   └── YYYY-MM-DD.md     # Daily work session notes (10 entries)
├── timeline/             # Chronological event mapping
│   └── index.md          # Year-by-year biographical outline
│
├── inventory.md          # Entry-by-entry review tracking
├── structure.md          # Manuscript architecture (Parts/Chapters/Vignettes)
├── vignettes.md          # Vignette development tracker
├── snippets.md           # Loose fragments repository
├── notes.md              # Extracted editorial notes
├── people.md             # Character/person index
├── themes.md             # Thematic cross-reference
└── tags.md               # Tag-based navigation
```

### Status: **Early Stage Development**

**Evidence**:
- Most files contain only headers and placeholder ellipses (`...`)
- Only 10 log entries spanning May-September 2025
- Timeline shows outline structure but lacks detail
- Core tracking files (inventory, people, themes) are empty shells

**Interpretation**: The wiki represents an **intentional scaffolding** — a pre-built knowledge infrastructure awaiting population through systematic journal review.

---

## Design Philosophy & Intentions

### 1. **Multi-Dimensional Navigation System**

The wiki implements **six distinct access pathways** into the journal archive:

#### A. **Chronological Access** (Timeline)
- **Purpose**: Biographical coherence and temporal context
- **Structure**: Year-by-year outline with thematic period labels
- **Example**: `2021 - Move to Montréal`, `2025 - Last year of PhD`
- **Intention**: Understand life events in sequential order; identify narrative arcs across time

#### B. **Structural Access** (Structure/Vignettes)
- **Purpose**: Manuscript architecture and narrative flow
- **Hierarchy**: Parts → Chapters → Vignettes
- **Intention**: Map raw entries to finished book structure; track editorial progress from fragment to chapter

#### C. **Thematic Access** (Themes/Tags)
- **Purpose**: Cross-temporal pattern recognition
- **Examples from journal**: `Dating-Clara`, `HRT-crisis`, `Depression`, `Trans`, `Therapy`
- **Intention**: Identify recurring motifs that transcend chronology; build thematic coherence

#### D. **Relational Access** (People)
- **Purpose**: Character tracking and relationship mapping
- **Convention**: `@Name` notation for tagged individuals
- **Intention**: Track recurring characters; understand relationship arcs; maintain name/alias consistency

#### E. **Fragmentary Access** (Snippets/Notes)
- **Purpose**: Capture resonant moments before structure emerges
- **Intention**: Honor the pre-rational editorial instinct; collect without premature categorization

#### F. **Linear Review Access** (Inventory)
- **Purpose**: Systematic coverage of all source material
- **Intention**: Ensure nothing is overlooked; track "keep/cut/extract" decisions for every entry

### 2. **Meta-Journaling Through Work Logs**

The `log/` directory implements a **recursive documentation pattern**: journaling about journaling.

**Key Features**:
- Task tracking for technical/editorial work
- Mood and focus state documentation
- Decision rationale preservation
- Technical troubleshooting notes

**Sample Entry Structure** (`2025-05-16.md`):
```markdown
Started: 12:00
Finished:

Tasks:
- [X] Make pdfbuild executable on Linux laptops
- [o] Implement Inventory.md fillout
- [ ] Implement YAML metadata extraction from Markdown files.

Worked on:
-
```

**Intentions**:
1. **Process Transparency**: Document the transformation journey, not just the product
2. **Decision Archaeology**: Future self can understand why certain choices were made
3. **Workflow Refinement**: Identify bottlenecks and iterate on editorial process
4. **Emotional Record**: Capture the lived experience of manuscript development

**Meta-Pattern Recognition**: The log entries from May 2025 focus heavily on:
- Metadata extraction and parsing (the YAML work we just completed)
- PDF compilation systems
- Vimwiki integration
- Infrastructure before content — building tools to handle complexity

### 3. **Graduated Curation Pipeline**

The wiki embodies a **four-stage transformation process**:

```
Raw Journal Entry
       ↓
[INVENTORY] ← Review & decision: Keep/Cut/Extract
       ↓
[SNIPPETS/NOTES] ← Promising fragments extracted but unplaced
       ↓
[VIGNETTES] ← Developed scenes with narrative shape
       ↓
[STRUCTURE] ← Positioned within manuscript architecture
       ↓
Final Manuscript
```

Each file serves a specific phase:
- **inventory.md**: Gate-keeping (what enters the manuscript consideration set?)
- **snippets.md**: Holding space (resonant but unstructured)
- **notes.md**: Analytical extraction (what does this mean?)
- **vignettes.md**: Narrative development (how does this work as story?)
- **structure.md**: Architectural integration (where does this belong?)

### 4. **Separation of Concerns**

The wiki deliberately separates:

| Concern | Location | Purpose |
|---------|----------|---------|
| **Source Material** | `journal/content/md/` | Immutable archive |
| **Editorial Tracking** | `wiki/*.md` | Mutable curation decisions |
| **Work Process** | `wiki/log/` | Meta-documentation |
| **Final Output** | `manuscript/` | Finished writing |
| **Metadata** | `metadata/palimpsest.db` | Relational data |

**Intention**: Protect source material integrity while enabling aggressive editorial iteration.

### 5. **Vimwiki Integration for Editorial Flow**

The wiki is designed for **Vim/Neovim** native editing with specific keybindings:

```vim
<Leader>ww           # Open wiki index (dashboard)
<Leader>wi           # Open work log index
<Leader>w<Leader>w   # Today's work log (instant meta-journaling)
<Leader>f            # Telescope wiki files (fuzzy find)
<Leader>g            # Live-grep wiki (full-text search)
```

**Intentions**:
1. **Minimal Friction**: Instant access to editorial tools without leaving editor
2. **Rapid Cross-Referencing**: Wiki-style `[[linking]]` between related content
3. **Keyboard-Driven Workflow**: No context switching to external apps
4. **Plain Text Philosophy**: Future-proof, version-controllable, grep-able

---

## Strategic Intentions Revealed Through Design

### Intention #1: **Manage Overwhelming Scale**

**Problem**: 380 journal entries spanning 10 years (~400,000+ words estimated)

**Solution**: Multi-axis indexing system enables:
- **Vertical slicing** (chronological timeline)
- **Horizontal slicing** (thematic/character-based)
- **Functional slicing** (inventory tracking)
- **Narrative slicing** (vignette development)

**Insight**: No single organizational scheme suffices; must support multiple simultaneous views.

### Intention #2: **Transform Self-Documentation Into Art**

**Problem**: Raw journal entries are unprocessed experience, not narrative

**Solution**: Graduated pipeline that progressively adds:
- **Selection** (inventory)
- **Interpretation** (notes)
- **Shape** (vignettes)
- **Context** (structure)
- **Resonance** (themes)

**Insight**: The wiki scaffolds the alchemical process of turning lived experience into literature.

### Intention #3: **Preserve Emergence Over Predetermined Structure**

**Evidence**:
- Timeline years marked with `??` (2022, 2023, 2024 themes not yet defined)
- Empty tracking files ready to be filled
- Snippets file for pre-categorized fragments
- Log entries show iterative discovery of process itself

**Insight**: The system accommodates **discovered structure** rather than imposed structure. The manuscript architecture will reveal itself through repeated engagement with material.

### Intention #4: **Create Accountability Through Visibility**

**Mechanisms**:
- Work logs with timestamps and task completion
- Inventory checkbox system
- Explicit "Started/Finished" times in log entries
- Progress tracking across multiple files

**Psychological Function**: Combat the paralysis of overwhelming creative projects by:
- Making progress visible
- Breaking into discrete tasks
- Documenting small wins
- Creating obligation to "future self"

### Intention #5: **Separate Technical Infrastructure from Creative Work**

**Timeline Evidence** (`wiki/log/`):
- May 2025: Heavy focus on build systems, parsing, PDF generation
- Later entries presumably shift toward content curation

**Pattern**: Build robust technical foundation FIRST, then focus creative energy on editorial decisions rather than tooling problems.

**Intention**: Eliminate technical friction from creative process; make infrastructure invisible.

### Intention #6: **Honor the Palimpsest Metaphor**

The wiki structure itself embodies layering:

1. **Layer 1**: Raw journal entries (original inscription)
2. **Layer 2**: YAML metadata (first annotation layer)
3. **Layer 3**: Wiki tracking files (editorial decision layer)
4. **Layer 4**: Work logs (meta-commentary layer)
5. **Layer 5**: Manuscript vignettes (artistic transformation layer)

**Insight**: Each layer doesn't erase the previous; all remain accessible and interconnected.

---

## Relationship to Journal YAML Metadata

### Complementary Systems

The wiki and journal YAML headers work in **symbiotic relationship**:

| Function | YAML Headers | Wiki Files |
|----------|--------------|------------|
| **Scope** | Entry-level metadata | Cross-entry patterns |
| **Granularity** | Individual dates/people/events | Aggregated themes/arcs |
| **Automation** | Parsed by scripts | Human-curated |
| **Purpose** | Enable search/filter | Enable interpretation |
| **Location** | Embedded in source | External tracking |

### Integration Points

1. **People Tracking**:
   - YAML: `people: [Clara, @Majo, Aliza]` (who appears in this entry)
   - Wiki: `people.md` (who are they? how do they relate? where else do they appear?)

2. **Event Arcs**:
   - YAML: `events: [Dating-Clara, HRT-crisis]` (tags this entry as part of arc)
   - Wiki: `themes.md` or `structure.md` (traces full arc across entries; narrative function)

3. **Timeline Construction**:
   - YAML: `dates:` field with nested contexts (micro-chronology within entry)
   - Wiki: `timeline/index.md` (macro-chronology across years)

4. **Vignette Development**:
   - YAML: `notes:` field (editorial flags during review)
   - Wiki: `vignettes.md` (tracking transformation from entry → scene)

### Evidence of Intentional Design

The YAML fields were clearly designed **with the wiki system in mind**:

**From YAML analysis**:
- `events` field uses named arcs: `Dating-Clara`, `Fading-Clara`, `Stormy-Valentine`
- `people` uses consistent `@Name` notation matching wiki convention
- `notes` field often contains meta-commentary suitable for wiki extraction
- `epigraph` + `poems` suggest literary transformation already beginning

**Conclusion**: The extended YAML metadata (appearing in 33 files from Nov 2024 - Mar 2025) represents **Phase 1 of the curation process** — enriching source material with semantic markers that will feed wiki-based analysis.

---

## Current Development Status

### Completed Infrastructure

✅ **Technical Foundation**:
- Vimwiki integration configured
- Log template system established
- Directory structure created
- Keybindings implemented
- PDF build system functional
- YAML metadata extraction (as of today's work)

✅ **Conceptual Framework**:
- Multi-axis navigation system designed
- Graduated curation pipeline defined
- Timeline structure outlined
- Naming conventions established

### Pending Population

⏳ **Content Curation**:
- Inventory.md awaiting systematic entry review
- People.md awaiting character mapping
- Themes.md awaiting pattern extraction
- Vignettes.md awaiting scene development
- Timeline awaiting detail population

### Inferred Next Steps

Based on log entries and system design:

1. **Systematic Inventory** (`2025-05-16` task: "Implement Inventory.md fillout")
   - Review all 380 entries
   - Mark as Keep/Cut/Extract
   - Flag promising vignettes

2. **People Mapping**
   - Extract all `@Name` references from YAML
   - Build character index with aliases
   - Track relationship timelines

3. **Theme Extraction**
   - Aggregate all `tags` and `events` from YAML
   - Identify cross-entry patterns
   - Map thematic arcs

4. **Vignette Development**
   - Extract flagged entries from inventory
   - Develop into narrative scenes
   - Iterate toward finished prose

---

## Design Patterns & Best Practices Observed

### 1. **Progressive Disclosure**

The wiki supports **iterative deepening**:
- Start with high-level timeline
- Drill into specific years/themes as needed
- Bottom-out at individual entries
- Maintain multiple zoom levels simultaneously

### 2. **Separation of Process and Product**

**Process** (`wiki/log/`):
- Experimental
- Messy
- Exploratory
- Time-stamped

**Product** (`wiki/*.md` tracking files):
- Structured
- Curated
- Cross-referenced
- Persistent

### 3. **Graceful Degradation**

Each wiki file remains useful **even if others are incomplete**:
- Timeline works without themes
- Inventory works without people
- Snippets work without structure

**Intention**: Avoid all-or-nothing paralysis; partial progress is valuable.

### 4. **Link-First Architecture**

Pervasive use of `[[wiki-links]]` creates:
- Bidirectional discovery
- Emergent connections
- Low-cost cross-referencing
- Future-proof navigation

### 5. **Metadata Before Content**

The wiki filled with empty files is **intentionally premature**:
- Creates psychological scaffolding
- Establishes naming conventions early
- Prevents decision paralysis later
- Makes implicit structure explicit

---

## Comparative Analysis: Similar Systems

The wiki structure shows influence from:

### 1. **Zettelkasten Method** (Niklas Luhmann)
- Permanent notes vs. literature notes distinction → snippets vs. vignettes
- Unique identifiers (date-based filenames)
- Emergent structure through linking

### 2. **GTD (Getting Things Done)** (David Allen)
- Inbox processing → inventory review
- Next actions → log task lists
- Someday/maybe → snippets holding area

### 3. **Scrivener Workflow** (Literature & Latte)
- Binder structure → wiki navigation
- Cork board → vignettes.md tracking
- Research folder → notes/snippets

### 4. **Field Notes Method** (Writers/Researchers)
- Daily logs capturing process
- Indexing system for retrieval
- Separation of raw notes from synthesis

### 5. **Commonplace Book Tradition** (Renaissance scholars)
- Thematic extraction from reading → themes.md
- Index of persons → people.md
- Collected fragments → snippets.md

**Innovation**: Integrates these disparate methods into unified plain-text system optimized for literary memoir development.

---

## Psychological & Artistic Intentions

### 1. **Combat Creative Overwhelm**

**Problem**: The prospect of writing a memoir from a decade of journals is paralyzing.

**Solution**: The wiki breaks the project into **dozens of micro-tasks**:
- Review entry #1, mark keep/cut
- Extract one snippet
- Map one person's timeline
- Write one log entry

**Each achievable in a single session.**

### 2. **Externalize Working Memory**

**Recognition**: You cannot hold 10 years of material in your head.

**Solution**: The wiki becomes **external cognition**:
- Timeline = external chronology
- People = external relationship graph
- Themes = external pattern recognition
- Inventory = external decision log

**Frees mental bandwidth for creative work.**

### 3. **Build Intimacy Through Repetition**

**Insight**: Great memoir requires deep familiarity with source material.

**Mechanism**: The multi-pass system ensures repeated engagement:
- Pass 1: Initial inventory review
- Pass 2: Theme/people extraction
- Pass 3: Snippet selection
- Pass 4: Vignette development
- Pass 5: Structural integration

**Each pass deepens understanding.**

### 4. **Preserve Discovery Process**

The work logs document **how the manuscript emerged**, not just the finished product.

**Value**:
- Future writing projects can learn from this process
- Shows evolution of thinking
- Honors the messiness of creative work
- Provides material for potential meta-narrative (introduction/afterword)

### 5. **Ritualize the Writing Practice**

The daily log keybinding (`<Leader>w<Leader>w` → today's log) creates:
- Low-friction entry ritual
- Accountability through documentation
- Momentum through visible progress
- Container for uncertainty/frustration

**Function**: Transform sporadic effort into sustainable practice.

---

## Conclusion: The Wiki as Editorial Scaffolding

The `wiki/` directory represents a **highly intentional, multi-layered knowledge management system** designed to solve the specific challenge of transforming a massive personal journal archive into a coherent literary memoir.

### Core Intentions Summary

1. **Enable multi-dimensional navigation** through chronological, thematic, structural, and relational axes
2. **Scaffold iterative transformation** from raw experience to finished narrative
3. **Externalize complexity** to free creative bandwidth
4. **Document the process** as well as the product
5. **Maintain source integrity** while enabling aggressive editorial iteration
6. **Support emergence** over predetermined structure
7. **Minimize friction** through editor integration and plain-text philosophy
8. **Create accountability** through visible progress tracking

### Philosophical Stance

The wiki embodies a belief that:
- **Structure enables freedom** (scaffolding liberates rather than constrains)
- **Process is content** (the meta-journal is part of the story)
- **Multiplicity enriches** (many views better than one true organization)
- **Tools shape thinking** (Vim integration reflects values of control, permanence, transparency)

### Status & Trajectory

Currently in **infrastructure-building phase**, with technical systems nearing completion and content curation about to begin in earnest. The empty tracking files represent **potential energy** — a carefully designed container awaiting the transformative work of repeated, systematic engagement with a decade of lived experience.

The wiki is not just **documentation of a project**; it is the **instrument through which the project becomes possible**.

---

*Analysis conducted: 2025-11-12*
*Based on: Directory structure, file contents, README documentation, and inferred intentions*
*Analyst: Claude (Sonnet 4.5) in collaboration with repository author*

# Documentation Rewrite Plan

**Scope**: 49 markdown source files across `docs/re/` (33), `docs/plan/` (11), `docs/seminar/` (5)
**Total**: ~59,000 lines of source markdown
**Build system**: `docs/site/build.py` converts markdown → HTML site

---

## Glossary of Domain Terms

These terms are used inconsistently across the docs. The rewrite will standardize on the **preferred term** and define it on first use per page.

| Preferred Term | Aliases Found | Definition |
|---|---|---|
| physics tick | game tick, simulation step, timestep | One 10ms fixed-timestep physics iteration |
| NSceneDyna | rigid body dynamics engine, dynamics engine | The rigid body simulation namespace |
| NSceneVehiclePhy | vehicle physics layer | The vehicle-specific force computation namespace |
| NHmsCollision | collision system | The collision detection namespace |
| GBX | GameBox | Nadeo's binary serialization format for all game assets |
| CMwNod | Nod, node | The root base class of the engine's object hierarchy |
| force model | force case, switch case | One of 7 vehicle physics computation paths (cases 0–6, 0xB) |
| sub-step | substep, sub step | One velocity-adaptive subdivision within a physics tick |
| class ID | chunk ID, ClassId | The 32-bit identifier for a GBX-serialized class |
| CarSport | StadiumCar, M6 | The primary vehicle model in TM2020 Stadium |
| VERIFIED | — | Claim confirmed against decompiled code |
| PLAUSIBLE | — | Claim supported by converging evidence but not directly confirmed |
| SPECULATIVE | — | Claim based on inference or analogy |

---

## Concept Dependency Graph

Pages should be read (and cross-referenced) in this order. Arrows mean "assumes knowledge from."

```
Binary Analysis
  ↓
Class System ← Architecture
  ↓               ↓
File Formats → Game Files
  ↓
Physics & Vehicle → Competitive Mechanics
  ↓
Rendering & Graphics → Shader Catalog
  ↓
Networking
  ↓
Audio System

Openplanet Intelligence → Openplanet Deep Mining
Community Knowledge → all RE pages (validates claims)
Visual Reference & Glossary → all pages (lookup)

TMNF Comparison → Physics, Rendering, Architecture
Ghidra Research → all deep dives
Validation Review → all RE pages (corrections)
Ghidra Gap Research → identifies future work

Map Structure Encyclopedia → File Formats, Game Files
Ghost & Replay Format → File Formats, Competitive Mechanics
ManiaScript Reference → Architecture
UI & ManiaLink → ManiaScript, Rendering
DLL Intelligence → Binary Analysis, Architecture
Real File Analysis → File Formats, Game Files
Browser Recreation Guide → all RE pages (synthesis)
```

---

## Page-by-Page Rewrite Plan

### Section 1: Reverse Engineering (28 HTML pages from 33 source files)

| # | Source File(s) | Output Page | Current Type | Target Type | Lines | Main Problem |
|---|---|---|---|---|---|---|
| 1 | `00-master-overview.md` | index.html | Dense overview | **Landing page / overview** | 641 | Metadata header buries the lede; statistics table dominates; no quick orientation for new readers |
| 2 | `01-binary-overview.md` | binary.html | Reference table dump | **Conceptual + reference** | 291 | Raw PE header tables with no context; no explanation of why any of this matters for the project |
| 3 | `02-class-hierarchy.md` + `13-subsystem-class-map.md` | class-hierarchy.html | Reference catalog | **Conceptual + reference** | 3701 | Two files merged into one massive page; no overview of the class system's design; just lists |
| 4 | `04-physics-vehicle.md` + `10-physics-deep-dive.md` | physics.html | Technical analysis | **Conceptual + reference** | 2754 | Two files merged; call chain dumps with no progressive disclosure; 4-velocity section is fascinating but buried |
| 5 | `05-rendering-graphics.md` + `11-rendering-deep-dive.md` | rendering.html | Technical analysis | **Conceptual + reference** | 2634 | Two files merged; G-buffer layout and pipeline stages are valuable but presented as walls of detail |
| 6 | `08-game-architecture.md` + `12-architecture-deep-dive.md` | architecture.html | Technical analysis | **Conceptual + reference** | 2990 | Two files merged; the state machine section is key but drowned in address tables |
| 7 | `06-file-formats.md` + `16-fileformat-deep-dive.md` | file-formats.html | Technical analysis | **Reference + conceptual** | 3596 | Two files merged; GBX format description is critical for implementation but needs inverted pyramid |
| 8 | `07-networking.md` + `17-networking-deep-dive.md` | networking.html | Technical analysis | **Conceptual + reference** | 4290 | Two files merged; longest combined page; protocol details valuable but no high-level overview first |
| 9 | `09-game-files-analysis.md` | game-files.html | Data analysis | **Reference** | 1369 | Hex dumps and directory listings need framing; useful as a reference but needs context |
| 10 | `14-tmnf-crossref.md` | tmnf-crossref.html | Comparison | **Comparison** | 734 | Good structure already; needs shorter paragraphs and front-loaded differences |
| 11 | `15-ghidra-research-findings.md` | ghidra-findings.html | Research notes | **Reference (findings catalog)** | 416 | Good per-topic structure; needs clearer headings and confidence-level summary |
| 12 | `18-validation-review.md` | validation.html | Meta-review | **Errata / corrections list** | 477 | Useful but buried as "validation review"; should be framed as errata that readers check |
| 13 | `19-openplanet-intelligence.md` | openplanet.html | Data extraction | **Reference** | 657 | Struct offset tables are the core value; needs better framing and less boilerplate |
| 14 | `20-browser-recreation-guide.md` | recreation.html | Implementation guide | **How-to guide** | 3422 | The most implementation-focused doc; needs progressive disclosure badly — 19 sections is too many |
| 15 | `21-competitive-mechanics.md` | competitive.html | Analysis | **Conceptual + reference** | 943 | Audience-specific (speedrunners); good focus but dense paragraphs |
| 16 | `22-ghidra-gap-findings.md` | ghidra-gaps.html | Research notes | **Reference (gap catalog)** | 1061 | Good catalog structure; needs summary table at top showing gap severity |
| 17 | `23-visual-reference.md` | visual-reference.html | Diagrams + glossary | **Visual reference** | 1673 | ASCII diagrams are valuable; glossary is essential; needs better sectioning |
| 18 | `24-audio-deep-dive.md` | audio.html | Technical analysis | **Conceptual + reference** | 1059 | Standalone deep dive; good structure but dense |
| 19 | `25-openplanet-deep-mining.md` | openplanet-mining.html | Data extraction | **Reference** | 1237 | Extension of #13; consider whether to merge or keep separate |
| 20 | `26-real-file-analysis.md` | real-files.html | Hex analysis | **Reference** | 993 | Raw hex with annotations; needs framing of what each finding means |
| 21 | `27-dll-intelligence.md` | dll-intelligence.html | Analysis | **Reference** | 1169 | DLL catalog is useful; needs summary table first |
| 22 | `28-map-structure-encyclopedia.md` | map-structure.html | Encyclopedia | **Reference** | 1227 | Well-structured already; needs inverted pyramid per section |
| 23 | `29-community-knowledge.md` | community.html | Catalog | **Reference** | 729 | Community project tables are good; comparison sections need tightening |
| 24 | `30-ghost-replay-format.md` | ghost-replay.html | Technical analysis | **Reference** | 1051 | Good format doc; needs high-level diagram before byte-level detail |
| 25 | `31-maniascript-reference.md` | maniascript.html | API reference | **API reference** | 1727 | Good reference structure; 25 sections is too many for one page |
| 26 | `34-ui-manialink-reference.md` | ui-manialink.html | API reference | **API reference** | 1521 | Similar to #25; needs better progressive disclosure |
| 27 | `32-shader-catalog.md` | shaders.html | Catalog | **Reference catalog** | 1410 | Category tables are the value; needs filtering/prioritization guidance |

### Section 2: Planning (11 pages)

| # | Source File | Output Page | Current Type | Target Type | Lines | Main Problem |
|---|---|---|---|---|---|---|
| 28 | `plan:00-executive-summary.md` | plan-overview.html | Executive summary | **Overview** | 245 | Good but could be tighter; architecture diagram is ASCII and hard to parse |
| 29 | `plan:01-system-architecture.md` | plan-architecture.html | Architecture doc | **Architecture** | 1770 | Long; code structure listings dominate |
| 30 | `plan:02-physics-engine.md` | plan-physics.html | Design spec | **Design spec** | 1899 | Dense Rust code; needs "what problem does each module solve" framing |
| 31 | `plan:03-renderer-design.md` | plan-renderer.html | Design spec | **Design spec** | 1492 | WGSL shader code dominates; needs pipeline overview first |
| 32 | `plan:04-asset-pipeline.md` | plan-assets.html | Design spec | **Design spec** | 1483 | Good structure; dense implementation detail |
| 33 | `plan:05-block-mesh-research.md` | plan-blockmesh.html | Research | **Research findings** | 542 | Findings need prioritization |
| 34 | `plan:06-determinism-analysis.md` | plan-determinism.html | Analysis | **Conceptual** | 579 | Good topic; needs clearer conclusion up front |
| 35 | `plan:07-physics-constants.md` | plan-constants.html | Reference table | **Reference** | 355 | Tables are the value; needs context about where constants come from |
| 36 | `plan:08-mvp-tasks.md` | plan-mvp.html | Task breakdown | **Task list / roadmap** | 933 | Checklist format is good; needs status/priority columns |
| 37 | `plan:09-tuning-data-extraction.md` | plan-tuning.html | Analysis | **How-to + reference** | 516 | Extraction methodology is the value; needs step-by-step framing |
| 38 | `plan:10-tuning-loading-analysis.md` | plan-tuning-loading.html | Analysis | **Conceptual** | 442 | Good focused topic; dense paragraphs |

### Section 3: Seminar (5 pages)

| # | Source File | Output Page | Current Type | Target Type | Lines | Main Problem |
|---|---|---|---|---|---|---|
| 39 | `seminar:alex-physics-notes.md` | seminar-alex.html | Study notes | **Tutorial/learning** | 856 | Best-written docs in the set — conversational, source-cited; just needs paragraph tightening |
| 40 | `seminar:maya-rendering-notes.md` | seminar-maya.html | Study notes | **Tutorial/learning** | 1169 | Good learning structure; long |
| 41 | `seminar:jordan-systems-notes.md` | seminar-jordan.html | Study notes | **Tutorial/learning** | 1088 | Good; needs tighter paragraphs |
| 42 | `seminar:prof-chen-physics-lectures.md` | seminar-chen.html | Lecture notes | **Tutorial/conceptual** | 962 | Excellent verification-first approach; verification table is highly valuable |
| 43 | `seminar:prof-kovac-graphics-lectures.md` | seminar-kovac.html | Lecture notes | **Tutorial/conceptual** | 1057 | Good teaching structure; long |

---

## Cross-Cutting Problems to Fix on Every Page

### 1. Kill the metadata headers
Every file starts with a block like:
```
**Binary**: `Trackmania.exe` (Trackmania 2020)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
```
This pushes the actual content below the fold. **Move to a collapsed details block or footer.** The reader doesn't need this before the content.

### 2. Remove manual TOC blocks
The site's JS generates navigation from headings. The hand-written TOC at the top of every file duplicates this and adds maintenance burden. **Remove all manual TOCs.**

### 3. Fix heading style: labels → actions
Change `## 1. Executive Summary` to `## How the engine is structured`. Headings describe what the reader learns, not what the section is called. Drop the numbering.

### 4. Apply inverted pyramid to every section
Every H2 gets: (1) what and why in 1-2 sentences, (2) quick version (diagram/code/summary), (3) details. A reader who stops after step 2 should have an 80% understanding.

### 5. Tighten paragraphs
Max 3 sentences per paragraph. Max 25 words per sentence. One idea per paragraph. Split aggressively.

### 6. Front-load key information
Subject and verb first. "Use `--force` to skip validation" not "To skip the validation step..."

### 7. Active voice
"The server validates the token" not "The token is validated by the server."

### 8. Standardize terminology per glossary
Use the preferred term from the glossary above. Define on first use per page.

### 9. Add cross-references
Every page ends with "Related pages" linking to conceptually adjacent docs per the dependency graph.

### 10. Frame confidence levels consistently
Use inline badges (the build system already styles VERIFIED/PLAUSIBLE/SPECULATIVE). Add a brief "Confidence" line under each major claim instead of mixing into prose.

---

## Structural Changes

### Split oversized merged pages
The build system merges some source files into single pages. These merged pages are too long:

| Current Page | Source Files | Combined Lines | Action |
|---|---|---|---|
| physics.html | 04 + 10 | 2,754 | Keep merged but add clear "Overview" vs "Deep Dive" separation with H2 |
| rendering.html | 05 + 11 | 2,634 | Same treatment |
| architecture.html | 08 + 12 | 2,990 | Same treatment |
| file-formats.html | 06 + 16 | 3,596 | Same treatment |
| networking.html | 07 + 17 | 4,290 | Same treatment — longest page |
| class-hierarchy.html | 02 + 13 | 3,701 | Same treatment |

For each: the first source file becomes the "understand how it works" conceptual section. The deep-dive becomes the "complete technical reference" section. The page opens with a brief overview that covers both.

### Navigation reorganization
Current sidebar has 28 RE items — too many for scanning. Group into sub-sections:

```
Reverse Engineering
  Core Systems
    Overview (index)
    Architecture
    Class System
    Binary Analysis
  Physics & Driving
    Physics & Vehicle
    Competitive Mechanics
  Rendering
    Rendering & Graphics
    Shader Catalog
  File Formats & Data
    File Formats (GBX)
    Game Files
    Map Structure Encyclopedia
    Ghost & Replay Format
    Real File Analysis
  Networking & Audio
    Networking
    Audio System
  Scripting & UI
    ManiaScript Reference
    UI & ManiaLink
  External Intelligence
    Openplanet Intelligence
    Openplanet Deep Mining
    DLL Intelligence
    Community Knowledge
    TMNF Comparison
  Research & Validation
    Ghidra Research
    Ghidra Gap Research
    Validation Review
    Visual Reference & Glossary
    Browser Recreation Guide
```

This brings each sub-group under 7 items (the working memory limit).

---

## Rewrite Order

Process pages in dependency order (prerequisites before dependents):

1. **index.html** (00-master-overview) — the landing page sets the tone
2. **architecture.html** (08 + 12) — foundational for everything
3. **binary.html** (01) — binary basics
4. **class-hierarchy.html** (02 + 13) — class system
5. **file-formats.html** (06 + 16) — GBX format (needed by many pages)
6. **physics.html** (04 + 10) — core simulation
7. **rendering.html** (05 + 11) — rendering pipeline
8. **networking.html** (07 + 17) — network protocol
9. **game-files.html** (09) — file analysis
10. **audio.html** (24) — audio system
11. **competitive.html** (21) — competitive mechanics
12. **map-structure.html** (28) — map encyclopedia
13. **ghost-replay.html** (30) — ghost format
14. **maniascript.html** (31) — script reference
15. **ui-manialink.html** (34) — UI reference
16. **shaders.html** (32) — shader catalog
17. **tmnf-crossref.html** (14) — comparison
18. **openplanet.html** (19) — openplanet intel
19. **openplanet-mining.html** (25) — openplanet deep mining
20. **dll-intelligence.html** (27) — DLL analysis
21. **real-files.html** (26) — hex analysis
22. **community.html** (29) — community knowledge
23. **ghidra-findings.html** (15) — ghidra research
24. **ghidra-gaps.html** (22) — gap research
25. **validation.html** (18) — errata
26. **visual-reference.html** (23) — diagrams & glossary
27. **recreation.html** (20) — browser recreation guide (synthesis of everything)
28–38. **plan-*.html** — planning docs (11 pages)
39–43. **seminar-*.html** — seminar notes (5 pages)

---

## Build System Changes Needed

1. **Update `build.py` PAGES list** to reflect nav sub-grouping (add sub-section separators)
2. **Update sidebar CSS** to support nested nav groups (collapsible)
3. **Add `<details>` support** to the markdown parser for collapsed metadata blocks
4. **Verify link map** after any file renames or structural changes

---

## What NOT to Change

- **Confidence badge system** (VERIFIED/PLAUSIBLE/SPECULATIVE) — this is excellent and well-implemented in the build system
- **Address styling** — the build system already badges hex addresses
- **Code blocks** — keep all decompiled code exactly as-is (it's primary source material)
- **Seminar character voices** — Alex, Maya, Jordan, Prof. Chen, Prof. Kovac have distinct educational voices that work well; preserve the personality while tightening structure
- **Technical accuracy** — never change a factual claim, address, offset, or code reference; only restructure how they're presented

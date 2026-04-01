# Documentation Rewrite Log

**Date**: 2026-03-30
**Scope**: 49 markdown source files + build system
**Net change**: -9,610 lines (11,306 added, 20,916 removed)

---

## Global Changes Applied to All Pages

1. **Metadata headers moved to bottom** — "Binary/Date/Tools" blocks relocated to collapsible `<details>` sections at the end of each file
2. **Manual TOCs removed** — The site's JS generates navigation from headings; hand-written TOCs were redundant
3. **Headings rewritten** — Numbered labels (`## 1. Executive Summary`) replaced with descriptive action headings (`## How the engine is structured`)
4. **Inverted pyramid applied** — Each H2 opens with what/why (1-2 sentences), quick version, then details
5. **Prose tightened** — Max 25 words/sentence, max 3 sentences/paragraph, active voice, front-loaded key info
6. **Hedge words removed** — "basically", "simply", "just", "obviously", "note that" stripped throughout
7. **Terminology standardized** — Consistent use of "physics tick", "NSceneDyna", "force model", "sub-step", "GBX", "CMwNod", "CarSport"
8. **Related Pages added** — Cross-reference links at the bottom of every page
9. **"You" not "the user"** — Direct address throughout

## Build System Changes (build.py)

- **Nav restructured**: 28 RE pages grouped into 8 sub-sections (Core Systems, Physics & Driving, Rendering, File Formats & Data, Networking & Audio, Scripting & UI, External Intelligence, Research & Validation)
- **`nav-subsection` CSS added**: Smaller group labels for sub-sections within the sidebar
- **HTML passthrough**: Markdown parser now passes through `<details>`, `<summary>`, `<div>` tags from source files
- **`sub:` page type**: New entry type in PAGES list for subsection labels, filtered from build loop and prev/next nav
- **Validation page renamed**: "Validation Review" → "Errata & Corrections"

## Per-File Changes

### Reverse Engineering (33 files)

| File | Before | After | Key Change |
|---|---|---|---|
| 00-master-overview.md | 641 | ~400 | Landing page rewritten with inviting intro; stats table kept prominent |
| 01-binary-overview.md | 291 | ~250 | Added framing for why binary analysis matters |
| 02-class-hierarchy.md | 693 | ~550 | Added class system design overview before diving into hierarchy |
| 04-physics-vehicle.md | 840 | ~1200 | Expanded with better progressive disclosure; call chains kept |
| 05-rendering-graphics.md | 811 | ~350 | Heavily condensed; deferred to deep-dive for details |
| 06-file-formats.md | 698 | ~550 | GBX format explanation front-loaded |
| 07-networking.md | 1149 | ~1500 | Restructured with high-level overview first |
| 08-game-architecture.md | 821 | ~550 | State machine section elevated |
| 09-game-files-analysis.md | 1369 | ~700 | Hex dumps framed with context |
| 10-physics-deep-dive.md | 1914 | ~1650 | Descriptive headings; inverted pyramid per section |
| 11-rendering-deep-dive.md | 1823 | ~1200 | G-buffer and pass descriptions restructured |
| 12-architecture-deep-dive.md | 2169 | ~2180 | All 20 sections renamed; intro rewritten |
| 13-subsystem-class-map.md | 3008 | ~2996 | All 23 sections renamed; numbering stripped |
| 14-tmnf-crossref.md | 734 | ~585 | Side-by-side comparison tables added |
| 15-ghidra-research-findings.md | 416 | ~350 | Key findings front-loaded per topic |
| 16-fileformat-deep-dive.md | 2898 | ~2870 | 32 headings renamed to descriptive |
| 17-networking-deep-dive.md | 3141 | ~3130 | 18 H2 + 11 H3 headings renamed |
| 18-validation-review.md | 477 | ~280 | Reframed as "Errata & Corrections"; MAJOR issues first |
| 19-openplanet-intelligence.md | 657 | ~560 | Opened with why Openplanet data is trustworthy |
| 20-browser-recreation-guide.md | 3422 | ~2800 | Grouped under Assessment/Core/Supporting/Implementation H2s |
| 21-competitive-mechanics.md | 943 | ~656 | Competitive framing preserved; paragraphs tightened |
| 22-ghidra-gap-findings.md | 1061 | ~650 | Severity-ranked summary table added |
| 23-visual-reference.md | 1673 | ~900 | Diagrams kept; glossary preserved; prose cut |
| 24-audio-deep-dive.md | 1059 | ~565 | 3-layer stack overview added; Q&A format removed |
| 25-openplanet-deep-mining.md | 1237 | ~750 | Opened with what additional data was extracted |
| 26-real-file-analysis.md | 993 | ~550 | Each hex dump annotated with what it reveals |
| 27-dll-intelligence.md | 1169 | ~600 | Summary DLL table added at top |
| 28-map-structure-encyclopedia.md | 1227 | ~700 | Inverted pyramid per section; coordinate system kept early |
| 29-community-knowledge.md | 729 | ~450 | Opened with what community has figured out |
| 30-ghost-replay-format.md | 1051 | ~600 | High-level data flow before byte-level detail |
| 31-maniascript-reference.md | 1727 | ~1500 | "ManiaScript in 30 seconds" added; 25 sections grouped under 4 H2s |
| 32-shader-catalog.md | 1410 | ~1000 | MVP shader guidance added; category tables kept |
| 34-ui-manialink-reference.md | 1521 | ~1400 | Opened with what ManiaLink is and why |

### Planning (11 files)

| File | Before | After | Key Change |
|---|---|---|---|
| 00-executive-summary.md | 245 | ~200 | Vision in 2 sentences; architecture diagram kept prominent |
| 01-system-architecture.md | 1770 | ~1700 | Key decisions table front-loaded |
| 02-physics-engine.md | 1899 | ~1800 | Goal (bit-for-bit reproduction) opens the doc |
| 03-renderer-design.md | 1492 | ~1470 | Pipeline overview before shader code |
| 04-asset-pipeline.md | 1483 | ~1200 | Opened with the core challenge (encrypted pack files) |
| 05-block-mesh-research.md | 542 | ~400 | Key findings front-loaded |
| 06-determinism-analysis.md | 579 | ~430 | Conclusion (what guarantees/threatens determinism) moved to top |
| 07-physics-constants.md | 355 | ~310 | Context added about where constants come from |
| 08-mvp-tasks.md | 933 | ~800 | Critical path and highest-risk tasks flagged |
| 09-tuning-data-extraction.md | 516 | ~400 | Framed as how-to |
| 10-tuning-loading-analysis.md | 442 | ~350 | Opened with what the tuning system does |

### Seminar (5 files)

| File | Before | After | Key Change |
|---|---|---|---|
| alex-physics-notes.md | 856 | ~700 | Light touch — paragraphs tightened; voice preserved |
| maya-rendering-notes.md | 1169 | ~800 | Paragraphs tightened; visual/practical framing kept |
| jordan-systems-notes.md | 1088 | ~950 | Architectural thinking preserved; prose tightened |
| prof-chen-physics-lectures.md | 962 | ~800 | Verification audit table kept intact and prominent |
| prof-kovac-graphics-lectures.md | 1057 | ~900 | Build-from-fundamentals approach preserved |

## What Was NOT Changed

- All code blocks (decompiled C, Rust, TypeScript, WGSL) — preserved exactly
- All hex addresses, offsets, and function references
- Confidence badge system (VERIFIED/PLAUSIBLE/SPECULATIVE)
- All ASCII diagrams
- All technical claims, measurements, and struct layouts
- Seminar character voices (Alex, Maya, Jordan, Prof. Chen, Prof. Kovac)

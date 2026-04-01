# Errata & Corrections

This page lists corrections to claims made elsewhere in the documentation. Check here if a number or structure seems wrong.

Every specific address, offset, and structural claim in documents 09, 10, 11, 12, 13, 14, 16, and 17 was cross-referenced against decompiled source files. Of 106 claims reviewed: 72 correct, 4 wrong, 9 unverifiable, 6 misleading, and 15 need confidence downgrades.

## Critical and Major Issues

These errors affect implementation correctness. Fix these first.

### Turbo Boost Ramps UP, Not Down (CRITICAL)

**Affects**: Doc 10 Section 4.3, Doc 14 Section 6.4

Doc 10 correctly describes the force formula as `(elapsed/duration) * strength * modelScale` -- a linear ramp from 0 to max. Doc 14 incorrectly says "Decay: linear over duration" for TM2020. The decompiled code definitively shows ramp-up: the car accelerates MORE as the boost nears expiration.

```c
local_b8 = ((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) *
           *(float *)(lVar6 + 0x16e4) * *(float *)(*(longlong *)(lVar6 + 0x1bb0) + 0xe0);
```

At elapsed=0, force=0. At elapsed=duration, force=strength*modelScale. This is the opposite of TMNF's documented decay behavior. Using the wrong direction produces completely wrong boost behavior in a recreation.

**Fix**: Doc 14 must note TM2020's turbo force increases linearly, not decreases.

### Sleep Threshold Is Linear, Not Pre-Squared (MAJOR)

**Affects**: Doc 10 Section 7.2

Doc 10 says "DAT_141ebcd04: Sleep velocity threshold (compared squared)" -- implying the value is already in squared units. The code squares it before comparison:

```c
fVar12 = DAT_141ebcd04 * DAT_141ebcd04;
// ...
if (fVar10 * fVar10 + fVar1 * fVar1 + fVar11 * fVar11 < fVar12) {
```

`DAT_141ebcd04` is a linear velocity threshold (m/s). The comparison is `speed_sq < DAT_141ebcd04^2`. Getting this wrong makes sleep detection activate at the wrong speed.

**Fix**: Change description to "Sleep velocity threshold (linear, squared by code before comparison)."

### Fragile Check Passes for Nibble Values 0 and 1 Too (MAJOR)

**Affects**: Doc 10 Section 6.4

Doc 10 claims the fragile check passes for "nibble values 4+ only." The code does unsigned subtraction:

```c
(1 < (*(uint *)(lVar9 + 0x128c) & 0xf) - 2)
```

For nibble=0: 0-2 = 0xFFFFFFFE (unsigned), and `1 < 0xFFFFFFFE` is TRUE. For nibble=1: 1-2 = 0xFFFFFFFF, and `1 < 0xFFFFFFFF` is TRUE. Only nibble values 2 and 3 fail. Missing this breaks fragile surface behavior for common vehicle states.

**Fix**: Correct to "nibble values 0, 1, and 4+ pass the check. Only nibble values 2 and 3 are excluded."

### Inferred API Endpoints Lack Confidence Labels (MAJOR)

**Affects**: Doc 17 Section 4

The "Inferred API Endpoint Map" presents URL paths like `/maps/{mapId}` and `/accounts/{id}/map-favorites` as definitive. These are guesses based on naming conventions. They have NOT been observed in network traffic or decompiled code.

**Fix**: Add SPECULATIVE labels to all inferred endpoints. Add a warning that URL paths are guesses from class names.

### Block Geometry Stride Is 56, Not 52 (MAJOR)

**Affects**: Doc 09 Section 6.4

The 7-attribute format with vertex color totals 12+8+4+8+8+8+8 = 56 bytes, not the stated 52. Using stride 52 corrupts vertex data parsing.

**Fix**: The 52-byte format has 6 attributes (no vertex color). The 56-byte format has 7 attributes (with vertex color).

### 100 Hz Tick Rate Should Be PLAUSIBLE, Not VERIFIED (MAJOR)

**Affects**: Doc 10 Section 10.1, Doc 14 Section 3.2

Doc 10 calls the 100 Hz tick rate VERIFIED. Doc 14 calls it UNKNOWN. No decompiled constant "100" or "0.01" exists in the physics code. The inference comes from community knowledge and the `*1000000` microsecond pattern.

**Fix**: Both documents should say PLAUSIBLE.

## Minor Issues

These are documentation clarity problems. They do not break implementations but may confuse you.

### Vertex Format B Location Numbers Are Non-Sequential (MINOR)

**Affects**: Doc 09 Section 6.4

Attribute locations skip: 0, 1, 4, 2, 3. This is correct D3D11/Vulkan behavior -- the engine uses fixed attribute mapping across all vertex formats. The document does not explain why.

**Fix**: Add a note that attribute locations are fixed across all vertex format variants (position=0, normal=1, tangent=2, binormal=3, UV0=4).

### NadeoPak Header Should Be PLAUSIBLE (MINOR)

**Affects**: Doc 09 Section 3.1

The pack header structure is derived from xxd hex analysis, not decompiled code. No decompiled pak parsing code exists.

**Fix**: Mark as PLAUSIBLE rather than VERIFIED.

### Steam App IDs Are Legacy ManiaPlanet (MINOR)

**Affects**: Doc 09 Section 8.2

IDs 232910 and 233070 are TrackMania Canyon and its demo (legacy ManiaPlanet-era). The actual TM2020 Steam App ID is 2225070.

**Fix**: Note these are legacy IDs preserved in the updater system.

### HBAO+ Registration Order Differs from Struct Order (MINOR)

**Affects**: Doc 11 Section 5

`DelayGrassFences` at offset 0x08 is registered after `BlurTexelCount` at 0x18. Registration order does not need to match struct order. Offsets match decompiled code.

**Verdict**: CORRECT. No fix needed.

### Shader Variant 14 Tessellation Claim Is Speculative (MINOR)

**Affects**: Doc 11 Section 6

The claim that variant index 0xe handles tessellation/LOD is inferred, not proven by a string or constant.

**Fix**: Mark "Tessellation/LOD shader" as SPECULATIVE.

### Web Services Class Count Discrepancy (MINOR)

**Affects**: Doc 13 Section header, Doc 17 Section 5

Doc 13 claims 713 Web Services classes. Doc 17 counts 562 across three prefixes (CNet 262 + CWebServices 297 + CGameNetwork 3). The 713 number may include additional related classes.

**Fix**: Reconcile the counts or explain inclusion criteria.

### FACADE01 Function Is a Class ID Checker (MINOR)

**Affects**: Doc 16 Section 7

The document conflates two uses of 0xFACADE01. Function `FUN_1402d0c40` checks class IDs (returns 1 for end-class, non-1 otherwise). The 0xFACADE01 sentinel in the actual file stream should be cited from community documentation or a different code path.

**Fix**: Clarify the function's role and cite the sentinel separately.

### LookbackString Flags Are Community-Sourced (MINOR)

**Affects**: Doc 16 Section 13

No decompiled code for the LookbackString system exists. Flag values come from community knowledge (gbx-net, wiki).

**Fix**: Mark as PLAUSIBLE (community-sourced) rather than implying decompilation verification.

### Vehicle Model Pointer Offset Inconsistency (MINOR)

**Affects**: Doc 10 Section 4.6

The force model type is at `*(vehicle+0x88) + 0x1790`, not `*(vehicle+0x1BB0) + 0x1790`. The pointer at vehicle+0x1BB0 serves a different purpose (likely visual model vs physics model).

**Fix**: Consistently document vehicle+0x88 as the physics model pointer.

## Summary Statistics

### Per-Document Results

| Document | Claims | Correct | Wrong | Unverifiable | Misleading | Need Downgrade |
|----------|--------|---------|-------|-------------|------------|----------------|
| 09-game-files | 12 | 8 | 1 | 2 | 1 | 0 |
| 10-physics | 25 | 18 | 2 | 0 | 1 | 4 |
| 11-rendering | 15 | 12 | 0 | 1 | 0 | 2 |
| 12-architecture | 10 | 5 | 0 | 3 | 0 | 2 |
| 13-subsystem | 5 | 3 | 0 | 1 | 1 | 0 |
| 14-tmnf-crossref | 12 | 8 | 1 | 0 | 1 | 2 |
| 16-fileformat | 15 | 10 | 0 | 2 | 1 | 2 |
| 17-networking | 12 | 8 | 0 | 0 | 1 | 3 |
| **TOTAL** | **106** | **72** | **4** | **9** | **6** | **15** |

### Claims Needing Confidence Downgrade

| Claim | Current | Should Be | Reason |
|-------|---------|-----------|--------|
| 100 Hz tick rate (doc 10) | VERIFIED | PLAUSIBLE | No constant found; inferred from community |
| NadeoPak header structure (doc 09) | VERIFIED | PLAUSIBLE | From hex analysis, no decompiled parser |
| G-buffer normal usage purposes (doc 11) | PLAUSIBLE | SPECULATIVE | Standard practices assumed, no code evidence |
| Shader variant 14 = tessellation (doc 11) | Stated as fact | SPECULATIVE | No direct evidence |
| LookbackString flag values (doc 16) | Implied verified | PLAUSIBLE | Community-sourced, no decompiled parser |
| TMNF curve shapes applicable to TM2020 (doc 14) | PLAUSIBLE | UNCERTAIN | 12 years of tuning changes |
| All inferred API endpoints (doc 17) | Unstated | SPECULATIVE | URL paths are guesses from class names |

## Related Pages

- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- Primary source for physics claims reviewed here
- [14-tmnf-crossref.md](14-tmnf-crossref.md) -- TMNF comparison containing the turbo boost contradiction
- [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) -- File format claims reviewed here
- [17-networking-deep-dive.md](17-networking-deep-dive.md) -- Networking claims reviewed here

<details><summary>Analysis metadata</summary>

- **Reviewer**: Technical Review Agent
- **Date**: 2026-03-27
- **Scope**: Documents 09, 10, 11, 12, 13, 14, 16, 17
- **Method**: Every specific address, offset, and structural claim cross-referenced against decompiled source files

</details>

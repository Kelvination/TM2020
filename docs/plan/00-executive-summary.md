# OpenTM Executive Summary

**READ THIS FIRST** -- This document synthesizes all 8 plan documents into a single starting point.

**Date**: 2026-03-27
**Status**: Pre-implementation design review complete

---

## 1. Project Vision

OpenTM is a browser-based recreation of Trackmania 2020's core gameplay: load official TM2020 map files, render them in 3D with WebGPU, and drive on them with physics that approximate the original game. The physics engine runs as Rust compiled to WASM for determinism and performance. Ghost recording/replay uses input-based deterministic simulation, matching TM2020's architecture. The project targets a 12-week MVP (load map, render, drive, checkpoints, finish) with a 6-month path to full feature parity including multiplayer, editor, and audio.

---

## 2. Architecture Overview

```
                        @opentm/core (TS, math types, constants)
                                |
        +-------+-------+------+------+-------+-------+
        |       |       |      |      |       |       |
     gbx-parser physics renderer audio input  camera  network
     (TS)      (Rust/  (TS+WGSL) (TS)  (TS)   (TS)    (TS)
               WASM)
        |       |       |                      |
        +---+---+---+---+                      |
            |       |                          |
           map    assets                       |
           (TS)    (TS)                        |
            |       |                          |
          ghost   editor  -------- ui (Svelte) +
           (TS)    (TS)
```

**Key architectural decisions**:

| Decision | Rationale |
|----------|-----------|
| Rust/WASM for physics | Determinism (IEEE 754 guaranteed by WASM spec) + performance (up to 1000 sub-steps/tick) |
| WebGPU deferred renderer | Matches TM2020's 19-pass deferred pipeline; 4-tier progressive quality (forward -> full deferred) |
| TypeScript GBX parser | Runs in browser; loads official .Map.Gbx files directly from user's disk |
| SharedArrayBuffer for physics<->render | Zero-copy 100Hz physics communication; avoids postMessage overhead |
| Pre-extracted block meshes served from CDN | PAK files are encrypted; runtime extraction is infeasible |
| Svelte for UI, HTML/CSS overlay | Do NOT replicate ManiaLink; leverage browser's native UI strength |
| pnpm monorepo + Turborepo | 14 packages with clear dependency boundaries |

---

## 3. Implementation Timeline

### 12-Week MVP

| Weeks | Focus | Key Deliverables |
|-------|-------|-----------------|
| 1 | Project setup + math | Monorepo, WASM toolchain, Vec3/Mat4/Iso4/Quat in Rust + TS |
| 2-4 | GBX parser + block system | BinaryReader, LZO, LookbackString, map header+body parsing, block mesh extraction pipeline |
| 4-7 | Renderer | Forward pipeline -> deferred G-buffer (4 MRT), PBR materials, shadows, tone mapping |
| 5-8 | Physics | VehicleState, 100Hz fixed timestep, Euler integration, collision mesh, CarSport force model |
| 6-8 | Input + Camera | Keyboard/gamepad, chase camera, free camera |
| 8-10 | Integration | Map load pipeline end-to-end, vehicle driving on map, HUD, checkpoints, finish |
| 10-12 | Polish | Bloom, FXAA, sky, car model, loading screen, settings, performance optimization |

**Critical path**: 23 working days through physics chain (monorepo -> WASM -> math -> VehicleState -> timestep -> integration -> collision -> force model -> integration with renderer). Block mesh extraction (MVP-021) is the highest-risk item on the critical path.

### 6-Month Full

Post-MVP additions: audio engine, Nadeo API integration, ghost import/export, map editor, ManiaScript interpreter, multiplayer (WebSocket + WebRTC), Tier 2-3 rendering (SSAO, SSR, volumetric fog, TAA), official ghost loading.

---

## 4. Key Risks

### Risk 1: Block Mesh Extraction (CRITICAL)
**Problem**: Block geometry lives in encrypted .pak files (Blowfish CBC, server-derived keys).
**Mitigation**: GBX.NET + PAK extraction pipeline (doc 05 recommends this as primary approach, 1-2 week effort). Fallback chain: Openplanet Fid extraction -> Ninja Ripper capture -> procedural placeholder geometry.
**Status from doc 05**: GBX.NET.PAK already implements decryption. Nations Converter 2 proves the pipeline works. Keys obtainable from Profile.Gbx.

### Risk 2: CarSport Physics Feel (HIGH probability)
**Problem**: Force model is decompiled structurally (500+ lines, 9 sub-functions) but tuning curve data comes from .Gbx files we cannot read. Steering, suspension, anti-roll, and drift sub-functions are referenced but not fully decompiled.
**Mitigation**: Use TMInterface to capture reference trajectories. Build tuning workflow comparing position divergence. Accept "approximately right" for MVP.

### Risk 3: Tuning Data is Entirely Data-Driven (HIGH impact)
**Problem**: Doc 07 proves NO physics constants (gravity, friction, engine curves) are hardcoded in the binary. Everything is loaded from GBX at runtime. Without extracting CPlugSpawnModel, CPlugVehiclePhyModel, and related GBX files, we have zero ground-truth values.
**Mitigation**: Extract tuning GBX files via the same PAK pipeline as block meshes. Use TMInterface recordings to reverse-engineer approximate values. This risk compounds Risk 1 -- if PAK extraction fails, both meshes AND physics tuning are blocked.

### Risk 4: GBX Parser Completeness (MEDIUM)
**Problem**: Complex community maps may use chunk versions or features not handled. Non-skippable unknown chunks halt parsing entirely.
**Mitigation**: Use gbx-net source as authoritative reference. Target 80%+ map compatibility for MVP.

### Risk 5: WASM Transcendental Function Divergence (LOW for cross-browser, MEDIUM for TM2020 match)
**Problem**: Compiled libm sin/cos/atan2 will be deterministic across browsers but will NOT match TM2020's MSVC implementation. Over many ticks, trajectories will diverge from official replays.
**Mitigation**: Accept divergence for v1. Future: extract TM2020's exact libm or use lookup tables tuned to match.

---

## 5. Technology Stack

| Layer | Technology | Version/Notes |
|-------|-----------|---------------|
| Language (physics) | Rust | Compiled to wasm32-unknown-unknown via wasm-pack |
| Language (everything else) | TypeScript | Strict mode |
| UI framework | Svelte | Minimal bundle, reactive |
| Graphics API | WebGPU | WGSL shaders, 4-tier quality |
| Physics communication | SharedArrayBuffer + Atomics | Requires COOP/COEP headers |
| Build tool | Vite 6+ | vite-plugin-wasm, vite-plugin-top-level-await |
| Monorepo | pnpm workspaces + Turborepo | |
| Testing | Vitest (TS) + cargo test (Rust) | Playwright for visual regression |
| CI | GitHub Actions | Nightly physics validation against TMInterface |
| Compression (GBX body) | LZO1X | NOT zlib (corrected from initial assumption) |
| Compression (ghosts) | LZ4 | For custom ghost format |
| Collision (initial) | Custom BVH + GJK/EPA | rapier3d as optional backend |
| Math (WASM) | Custom f32 (no external lib) | Full control for determinism |
| Transcendentals | libm crate | Compiled to WASM, never import JS Math |

---

## 6. Getting Started -- First 5 Tasks on Day 1

1. **MVP-001**: Initialize pnpm monorepo with `@opentm/app`, `@opentm/gbx`, `@opentm/renderer`, `@opentm/physics` packages. Configure TypeScript strict, ESLint, Prettier.

2. **MVP-002**: Set up Rust WASM toolchain. Create `crates/physics` with a `ping()` function. Verify browser can call Rust from TypeScript.

3. **MVP-003**: WebGPU canvas setup. Request adapter/device, clear to sky-blue. Handle "WebGPU not supported" fallback.

4. **MVP-010**: BinaryReader class wrapping DataView with little-endian cursor. This unblocks all GBX parsing work.

5. **MVP-021**: Start block mesh extraction pipeline (parallel track, highest risk). Set up GBX.NET + PAK project. Attempt to decrypt and list Stadium.pak contents.

Tasks 1-4 are zero-risk setup. Task 5 is the highest-risk item in the entire project and benefits from early investigation.

---

## 7. Open Questions

### Must Answer Before Implementation

| # | Question | Blocking | Source |
|---|----------|----------|--------|
| 1 | Can we obtain PAK encryption keys from Profile.Gbx or Trackmania.exe? | Block mesh extraction + physics tuning data | Doc 05 Section "Key Challenge" |
| 2 | What are the actual gravity, friction, and engine curve values for CarSport? | Physics accuracy | Doc 07 (all values are data-driven) |
| 3 | Which GBX file(s) contain CPlugSpawnModel.DefaultGravitySpawn? | Gravity vector | Doc 07 Section 11 |
| 4 | What is the exact behavior of FUN_14195dd00 (safe_sqrt for negative inputs)? | Determinism edge case | Doc 02 Section 3.2 |
| 5 | Do steering, suspension, anti-roll, and drift sub-functions need full Ghidra decompilation? | CarSport physics fidelity | Doc 02 Section 4.5 |

### Should Answer During Implementation

| # | Question | Impact | Source |
|---|----------|--------|--------|
| 6 | Does turbo force ramp UP or DOWN over duration? | Feel of turbo pads | Doc 08 Risk 6; decompilation says UP |
| 7 | What is the format of VehicleCameraRace2Model.gbx? | Chase camera tuning | Doc 01 (camera section) |
| 8 | Which TM2020 vehicle types use force model cases 3, 4, and 0xB? | Scope of physics work | Doc 02 Section 4 |
| 9 | What exact chunks appear in community maps that are non-skippable? | Parser robustness | Doc 08 Risk 3 |
| 10 | Is the WASM deterministic profile (canonical NaN) supported in browsers yet? | Belt-and-suspenders for determinism | Doc 06 Section 1.5 |
| 11 | What is the exact wire format for block variant selection (ground vs air, color variant)? | Correct block rendering | Doc 04 Section 4 |
| 12 | How does TM2020's block connectivity validation work? | Map editor | Doc 01 (editor section) |

### Nice to Know

| # | Question | Source |
|---|----------|--------|
| 13 | Can we match TM2020's exact MSVC transcendental implementations for replay compatibility? | Doc 06 Section 5.4 |
| 14 | What are the 7 contact buffers in ProcessContactPoints? | Doc 02 Section 6.4 |
| 15 | How does the tire icing/grip state machine transition between states? | Doc 07 Section 4 |

---

## 8. Cross-Document Issues

### Contradictions Found

**C1: Module naming inconsistency between doc 01 and doc 08.**
Doc 01 defines `@opentm/gbx-parser` as the GBX parsing module. Doc 08 (MVP tasks) refers to it as module `gbx` in task descriptions (e.g., MVP-010 through MVP-019 list "Module: gbx"). The Cargo crate is named `opentm-physics` in doc 01 but the npm package is `@opentm/physics`. This is cosmetic but should be standardized before implementation. The monorepo directory in doc 01 Section 5.1 uses `gbx-parser/` which is correct.

**C2: rapier3d vs custom collision.**
Doc 01 (Section 1.1, `@opentm/physics`) declares `collision: CollisionWorld, // wraps rapier3d` and lists rapier3d in Cargo.toml dependencies. Doc 02 (Section 6) designs a fully custom collision system (broadphase grid, GJK/EPA narrowphase, custom contact merging, custom friction solver) with no mention of rapier3d. Doc 08 (MVP-040 through MVP-042) describes building custom BVH, SAT/GJK narrowphase, and impulse-based solver. These are contradictory approaches. **Resolution needed**: Either use rapier3d (simpler, faster to ship) or build custom (more control, matches TM2020's internal solver). The custom approach in docs 02 and 08 is more aligned with the project's goal of matching TM2020 behavior.

**C3: G-buffer normal format inconsistency.**
Doc 03 Section 2 specifies RT2 Normal as `rg16float` with octahedral encoding (2 channels). Doc 01 Section 2.3 (render frame trace) says `RT2: normal (rgba16float) -- camera-space normal from TBN * normal map`. Doc 08 MVP-032 says `world-space normal (rgba16float)`. Three different specifications: `rg16float` vs `rgba16float`, and camera-space vs world-space. **Doc 03 is authoritative** (it provides the detailed justification): `rg16float`, camera-space, octahedral encoded. Docs 01 and 08 should be corrected.

**C4: Gravity constant handling.**
Doc 08 MVP-036 says "Apply gravity as a constant downward acceleration (9.81 m/s^2 in -Y direction)." Doc 07 explicitly states "TM2020 uses NO hardcoded gravity constant" -- it is data-driven from CPlugSpawnModel.DefaultGravitySpawn. Doc 08 acknowledges this ("TM2020 uses parameterized gravity with GravityCoef, but start with hardcoded 9.81 for now"), so this is an intentional simplification for MVP, not a true contradiction. However, the actual TM2020 gravity magnitude is UNKNOWN (not necessarily 9.81). This should be flagged as a tuning risk.

**C5: SharedArrayBuffer layout discrepancy.**
Doc 01 Section 3.2 defines a detailed SAB layout with INPUT REGION starting at offset 0x0040 and OUTPUT REGION at 0x0100. Doc 02 Section 9 is titled "WASM Interface (SharedArrayBuffer)" but was not fully readable. The physics Rust struct in doc 02 uses `#[wasm_bindgen]` with `pub fn step(&mut self, input_buffer: &[u8]) -> Box<[u8]>` which is a byte-buffer interface, NOT a SharedArrayBuffer interface. These are two different communication patterns. **Resolution needed**: The SAB approach (doc 01) is superior for performance. The byte-buffer approach (doc 02) is simpler but involves copying. Pick one.

**C6: Tick microsecond constant.**
Doc 01 defines `TICK_DT_MICROS = 10_000_000` (10 million, which would be 10 seconds, not 10ms). The correct value for 10ms is 10,000 microseconds. Doc 02 correctly uses `TICK_US: i64 = 10_000` (10,000 microseconds). Doc 01's value appears to be a bug -- it should be `10_000` not `10_000_000`.

### Gaps Found

**G1: No specification for extracting physics tuning data.**
Doc 05 covers block mesh extraction in detail (7 approaches evaluated). Doc 07 proves all physics constants are data-driven from GBX. But NO document specifies how to extract the GBX files containing CPlugSpawnModel, CPlugVehiclePhyModel, NPlugDyna::SConstraintModel, or SSolverParams. The mesh extraction pipeline (doc 05) should also extract these files, but this is not called out. A developer would not know which specific GBX files to target or how to parse the tuning curve format (CFuncKeysReal).

**G2: No asset manifest specification.**
Doc 01 mentions an "asset manifest JSON" and doc 04 references "asset manifest management," but no document defines the manifest schema (what fields, what URLs, how blocks map to meshes and materials). A developer starting MVP-022 (block mesh registry) would need to invent this format.

**G3: No specification for block variant selection.**
Maps contain blocks with ground/air variants, color variants (flags bits 12-14), and free-placement variants. Doc 04 Section 4 titles "The Block Mesh Problem" but focuses on extraction, not on runtime variant resolution. Which mesh file corresponds to "StadiumRoadMainStraight" ground variant vs air variant? How are the ~200 block types mapped to mesh files? This is a gap between doc 04 (asset pipeline) and doc 08 (MVP-020, block data model).

**G4: No multiplayer protocol specification.**
Doc 01 mentions "WebSocket + WebRTC" for future multiplayer and explicitly defers it, which is fine for MVP. But there is no placeholder design or even a list of what would need to change in the architecture to support multiplayer (e.g., authoritative server, client prediction, state sync frequency).

**G5: Collision mesh vs visual mesh separation.**
Doc 08 MVP-040 acknowledges that "TM2020 separates visual and collision meshes internally" and flags "block meshes may have decorative geometry mixed with collision geometry." No document specifies how to separate collision geometry from visual geometry during extraction. The CPlugSolid2Model contains both visual LODs and a collision shape (CPlugSurface/Shape.Gbx), but the extraction pipeline in doc 05 focuses only on visual meshes. The collision shapes need separate extraction.

**G6: No error recovery or graceful degradation strategy.**
What happens when a block mesh is missing? Doc 08 MVP-022 says "substitute a colored wireframe cube," but there is no systematic strategy for: missing textures, unsupported GBX chunk versions, physics solver divergence, WebGPU feature gaps on specific hardware. A resilience/fallback matrix would help.

**G7: Map coordinate system offset ambiguity.**
Doc 01 Section 2.1 says `world_y = (gridY - 8) * 8m` with a note about "Y has a -8 offset for maps with grid origin at y=8". Doc 08 MVP-020 says `world_y = grid_y * 8.0` with NO offset. These produce different results. The actual offset depends on the map's `MapCoordOrigin` field (chunk 0x03043003). This needs to be resolved with a definitive rule.

**G8: Wheel order discrepancy.**
Doc 02 Section 2.1 states wheel order as "FL(0), FR(1), RR(2), RL(3) -- clockwise from front-left." Doc 07 Section 7 shows wheel stride offsets but does not confirm this order. The "clockwise from front-left" labeling gives FL, FR, RR, RL which skips the rear-left before rear-right, suggesting it might actually be FL, FR, RL, RR (as in standard automotive convention). This should be verified.

### Things That Would Surprise a Developer

1. **GBX body uses LZO, not zlib.** Multiple docs emphasize this correction from the initial assumption. The binary contains zlib strings but those are for lightmaps and ghosts, not the main body.

2. **The turbo force ramps UP, not down.** Decompilation shows `(elapsed / duration) * strength`, meaning the boost gets stronger over time, not weaker. This is counterintuitive and contradicts TMNF behavior.

3. **All physics tuning is data-driven.** There is no hardcoded 9.81. No hardcoded friction. No hardcoded engine curves. Everything comes from GBX files. If you cannot extract those files, you have zero ground-truth physics values.

4. **The TICK_DT_MICROS constant in doc 01 is wrong.** It says 10,000,000 (10 seconds) instead of 10,000 (10ms). Do not copy this value.

5. **The `@opentm/physics` Rust crate has two conflicting interfaces** described across docs: SharedArrayBuffer (doc 01) vs byte-buffer via wasm_bindgen (doc 02). These need to be reconciled.

6. **208 stock materials all have `DGameplayId(None)`.** Gameplay effects (turbo, ice, etc.) come from block trigger zones, NOT from material surfaces. The two-ID system (material physics ID vs gameplay ID) is non-obvious.

7. **Block mesh extraction is prerequisite for BOTH rendering AND physics.** Without it, you have neither visual meshes nor collision geometry nor physics tuning curves. This single dependency gates three major subsystems.

---

## Document Index

| Doc | Title | Key Content |
|-----|-------|-------------|
| 01 | System Architecture | Module graph, data flow traces, threading model, SAB layout, state machine, build system, performance budget |
| 02 | Physics Engine | Rust module structure, VehicleState (7328 bytes), PhysicsStep algorithm, force model dispatch (7 cases), collision system, surface effects |
| 03 | Renderer Design | 4-tier pipeline (forward -> ultra), G-buffer format, 38 uber-shaders replacing 1112 TM2020 shaders, WGSL code |
| 04 | Asset Pipeline | GBX parser architecture (TypeScript), map loading pipeline, material system, texture pipeline, caching |
| 05 | Block Mesh Research | 7 extraction approaches evaluated; GBX.NET + PAK recommended; PAK encryption details; mesh data format |
| 06 | Determinism Analysis | WASM float guarantees, NaN prevention, compiled libm strategy, fixed-point rejected, cross-browser test plan |
| 07 | Physics Constants | All values data-driven from GBX; hardcoded math constants listed; VehiclePhyModel offsets; CSceneVehicleVisState layout (0x360 bytes); 22 surface gameplay IDs |
| 08 | MVP Tasks | 68 tasks across 10 groups; critical path (23 days); 10 risks ranked; block extraction is highest-risk critical-path item |

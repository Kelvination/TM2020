# OpenTM Executive Summary

OpenTM recreates Trackmania 2020's core gameplay in the browser. Load official TM2020 map files, render them with WebGPU, and drive on them with physics that approximate the original game. The physics engine compiles Rust to WASM for determinism and performance. Ghost recording uses input-based deterministic simulation, matching TM2020's architecture.

The project targets a 12-week MVP (load map, render, drive, checkpoints, finish). A 6-month path covers full feature parity including multiplayer, editor, and audio.

---

## Architecture Overview

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

| Decision | Rationale |
|----------|-----------|
| Rust/WASM for physics | Determinism (IEEE 754 guaranteed by WASM spec) + performance (up to 1000 sub-steps/tick) |
| WebGPU deferred renderer | Matches TM2020's 19-pass deferred pipeline; 4-tier progressive quality (forward to full deferred) |
| TypeScript GBX parser | Runs in browser; loads official .Map.Gbx files directly from disk |
| SharedArrayBuffer for physics-render | Zero-copy 100Hz physics communication; avoids postMessage overhead |
| Pre-extracted block meshes from CDN | PAK files are encrypted; runtime extraction is infeasible |
| Svelte for UI, HTML/CSS overlay | Leverage the browser's native UI strength; do NOT replicate ManiaLink |
| pnpm monorepo + Turborepo | 14 packages with clear dependency boundaries |

---

## Implementation Timeline

### 12-Week MVP

| Weeks | Focus | Key Deliverables |
|-------|-------|-----------------|
| 1 | Project setup + math | Monorepo, WASM toolchain, Vec3/Mat4/Iso4/Quat in Rust + TS |
| 2-4 | GBX parser + block system | BinaryReader, LZO, LookbackString, map header+body parsing, block mesh extraction pipeline |
| 4-7 | Renderer | Forward pipeline to deferred G-buffer (4 MRT), PBR materials, shadows, tone mapping |
| 5-8 | Physics | VehicleState, 100Hz fixed timestep, Euler integration, collision mesh, CarSport force model |
| 6-8 | Input + Camera | Keyboard/gamepad, chase camera, free camera |
| 8-10 | Integration | Map load pipeline end-to-end, vehicle driving on map, HUD, checkpoints, finish |
| 10-12 | Polish | Bloom, FXAA, sky, car model, loading screen, settings, performance optimization |

The critical path runs 23 working days through the physics chain (monorepo to WASM to math to VehicleState to timestep to integration to collision to force model to renderer integration). Block mesh extraction (MVP-021) is the highest-risk item on the critical path.

### 6-Month Full

Post-MVP adds: audio engine, Nadeo API integration, ghost import/export, map editor, ManiaScript interpreter, multiplayer (WebSocket + WebRTC), Tier 2-3 rendering (SSAO, SSR, volumetric fog, TAA), official ghost loading.

---

## Key Risks

### Block Mesh Extraction (CRITICAL)

Block geometry lives in encrypted .pak files (Blowfish CBC, server-derived keys). GBX.NET + PAK extraction pipeline is the primary approach (1-2 week effort). GBX.NET.PAK already implements decryption. Nations Converter 2 proves the pipeline works. Keys are obtainable from Profile.Gbx.

Fallback chain: Openplanet Fid extraction, Ninja Ripper capture, procedural placeholder geometry.

### CarSport Physics Feel (HIGH probability)

The force model is decompiled structurally (500+ lines, 9 sub-functions), but tuning curve data comes from .Gbx files we cannot read. Steering, suspension, anti-roll, and drift sub-functions are referenced but not fully decompiled. TMInterface captures reference trajectories for comparison. Accept "approximately right" for MVP.

### Tuning Data is Entirely Data-Driven (HIGH impact)

Doc 07 proves NO physics constants (gravity, friction, engine curves) are hardcoded in the binary. Everything loads from GBX at runtime. Without extracting CPlugSpawnModel, CPlugVehiclePhyModel, and related GBX files, we have zero ground-truth values. This risk compounds the block mesh risk -- if PAK extraction fails, both meshes AND physics tuning are blocked.

### GBX Parser Completeness (MEDIUM)

Complex community maps may use chunk versions or features not handled. Non-skippable unknown chunks halt parsing entirely. Use gbx-net source as authoritative reference. Target 80%+ map compatibility for MVP.

### WASM Transcendental Function Divergence (LOW cross-browser, MEDIUM TM2020 match)

Compiled libm sin/cos/atan2 produces deterministic results across browsers but does NOT match TM2020's MSVC implementation. Over many ticks, trajectories diverge from official replays. Accept divergence for v1.

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
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

## Getting Started -- First 5 Tasks on Day 1

1. **MVP-001**: Initialize pnpm monorepo with `@opentm/app`, `@opentm/gbx`, `@opentm/renderer`, `@opentm/physics` packages. Configure TypeScript strict, ESLint, Prettier.

2. **MVP-002**: Set up Rust WASM toolchain. Create `crates/physics` with a `ping()` function. Verify browser can call Rust from TypeScript.

3. **MVP-003**: WebGPU canvas setup. Request adapter/device, clear to sky-blue. Handle "WebGPU not supported" fallback.

4. **MVP-010**: BinaryReader class wrapping DataView with little-endian cursor. This unblocks all GBX parsing work.

5. **MVP-021**: Start block mesh extraction pipeline (parallel track, highest risk). Set up GBX.NET + PAK project. Attempt to decrypt and list Stadium.pak contents.

Tasks 1-4 are zero-risk setup. Task 5 is the highest-risk item in the entire project and benefits from early investigation.

---

## Open Questions

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

## Cross-Document Issues

### Contradictions Found

**C1: Module naming inconsistency between doc 01 and doc 08.** Doc 01 defines `@opentm/gbx-parser` as the GBX parsing module. Doc 08 refers to it as module `gbx` in task descriptions. The Cargo crate is named `opentm-physics` in doc 01 but the npm package is `@opentm/physics`. Standardize before implementation.

**C2: rapier3d vs custom collision.** Doc 01 declares `collision: CollisionWorld, // wraps rapier3d` and lists rapier3d in Cargo.toml dependencies. Doc 02 designs a fully custom collision system (broadphase grid, GJK/EPA narrowphase, custom contact merging, custom friction solver). Doc 08 describes building custom BVH, SAT/GJK narrowphase, and impulse-based solver. **Resolution needed**: Either use rapier3d (simpler, faster to ship) or build custom (more control, matches TM2020's internal solver). The custom approach in docs 02 and 08 aligns better with the project's goal.

**C3: G-buffer normal format inconsistency.** Doc 03 specifies RT2 Normal as `rg16float` with octahedral encoding (2 channels). Doc 01 says `rgba16float` camera-space normal. Doc 08 says `world-space normal (rgba16float)`. Three different specifications. **Doc 03 is authoritative**: `rg16float`, camera-space, octahedral encoded.

**C4: Gravity constant handling.** Doc 08 MVP-036 says "Apply gravity as a constant downward acceleration (9.81 m/s^2)." Doc 07 states "TM2020 uses NO hardcoded gravity constant" -- it is data-driven from CPlugSpawnModel.DefaultGravitySpawn. Doc 08 acknowledges this as an intentional MVP simplification. The actual TM2020 gravity magnitude is UNKNOWN (not necessarily 9.81).

**C5: SharedArrayBuffer layout discrepancy.** Doc 01 defines a detailed SAB layout with INPUT REGION at offset 0x0040 and OUTPUT REGION at 0x0100. Doc 02's physics Rust struct uses `#[wasm_bindgen]` with `pub fn step(&mut self, input_buffer: &[u8]) -> Box<[u8]>` -- a byte-buffer interface, NOT a SharedArrayBuffer interface. **Resolution needed**: The SAB approach (doc 01) is superior for performance.

**C6: Tick microsecond constant.** Doc 01 defines `TICK_DT_MICROS = 10_000_000` (10 million, which equals 10 seconds, not 10ms). The correct value for 10ms is 10,000 microseconds. Doc 02 correctly uses `TICK_US: i64 = 10_000`. Doc 01's value is a bug.

### Gaps Found

**G1: No specification for extracting physics tuning data.** Doc 05 covers block mesh extraction. Doc 07 proves all physics constants are data-driven from GBX. But NO document specifies how to extract the GBX files containing CPlugSpawnModel, CPlugVehiclePhyModel, NPlugDyna::SConstraintModel, or SSolverParams.

**G2: No asset manifest specification.** Doc 01 mentions an "asset manifest JSON" and doc 04 references "asset manifest management," but no document defines the manifest schema.

**G3: No specification for block variant selection.** Maps contain blocks with ground/air variants, color variants, and free-placement variants. No document specifies how to map block names to mesh files at runtime.

**G4: No multiplayer protocol specification.** Doc 01 mentions "WebSocket + WebRTC" for future multiplayer and explicitly defers it.

**G5: Collision mesh vs visual mesh separation.** Doc 08 acknowledges TM2020 separates visual and collision meshes internally. No document specifies how to separate collision geometry from visual geometry during extraction.

**G6: No error recovery or graceful degradation strategy.** No systematic strategy for missing textures, unsupported GBX chunk versions, physics solver divergence, or WebGPU feature gaps.

**G7: Map coordinate system offset ambiguity.** Doc 01 says `world_y = (gridY - 8) * 8m`. Doc 08 says `world_y = grid_y * 8.0` with NO offset. The actual offset depends on the map's `MapCoordOrigin` field.

**G8: Wheel order discrepancy.** Doc 02 states wheel order as "FL(0), FR(1), RR(2), RL(3) -- clockwise from front-left." The "clockwise" labeling suggests it might actually be FL, FR, RL, RR (standard automotive convention). Verify.

### Things That Would Surprise a Developer

1. **GBX body uses LZO, not zlib.** The binary contains zlib strings but those are for lightmaps and ghosts, not the main body.

2. **The turbo force ramps UP, not down.** Decompilation shows `(elapsed / duration) * strength`. The boost gets stronger over time. This contradicts TMNF behavior.

3. **All physics tuning is data-driven.** No hardcoded 9.81. No hardcoded friction. No hardcoded engine curves. Everything comes from GBX files. Without extracting those files, you have zero ground-truth physics values.

4. **The TICK_DT_MICROS constant in doc 01 is wrong.** It says 10,000,000 (10 seconds) instead of 10,000 (10ms). Do not copy this value.

5. **The `@opentm/physics` Rust crate has two conflicting interfaces** described across docs: SharedArrayBuffer (doc 01) vs byte-buffer via wasm_bindgen (doc 02). Reconcile before implementation.

6. **208 stock materials all have `DGameplayId(None)`.** Gameplay effects (turbo, ice, etc.) come from block trigger zones, NOT from material surfaces. The two-ID system (material physics ID vs gameplay ID) is non-obvious.

7. **Block mesh extraction gates THREE major subsystems.** Without it, you have neither visual meshes nor collision geometry nor physics tuning curves.

---

## Document Index

| Doc | Title | Key Content |
|-----|-------|-------------|
| 01 | System Architecture | Module graph, data flow traces, threading model, SAB layout, state machine, build system, performance budget |
| 02 | Physics Engine | Rust module structure, VehicleState (7328 bytes), PhysicsStep algorithm, force model dispatch (7 cases), collision system, surface effects |
| 03 | Renderer Design | 4-tier pipeline (forward to ultra), G-buffer format, 38 uber-shaders replacing 1112 TM2020 shaders, WGSL code |
| 04 | Asset Pipeline | GBX parser architecture (TypeScript), map loading pipeline, material system, texture pipeline, caching |
| 05 | Block Mesh Research | 7 extraction approaches evaluated; GBX.NET + PAK recommended; PAK encryption details; mesh data format |
| 06 | Determinism Analysis | WASM float guarantees, NaN prevention, compiled libm strategy, fixed-point rejected, cross-browser test plan |
| 07 | Physics Constants | All values data-driven from GBX; hardcoded math constants listed; VehiclePhyModel offsets; CSceneVehicleVisState layout (0x360 bytes); 22 surface gameplay IDs |
| 08 | MVP Tasks | 68 tasks across 10 groups; critical path (23 days); 10 risks ranked; block extraction is highest-risk critical-path item |

---

## Related Pages

- [System Architecture](01-system-architecture.md) -- Full module dependency graph and data flow traces
- [Physics Engine](02-physics-engine.md) -- VehicleState struct and force model implementation
- [Block Mesh Research](05-block-mesh-research.md) -- Detailed extraction approach comparison
- [MVP Tasks](08-mvp-tasks.md) -- Complete task breakdown and critical path

<details><summary>Document metadata</summary>

- **Date**: 2026-03-27
- **Status**: Pre-implementation design review complete

</details>

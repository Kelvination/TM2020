# OpenTM System Architecture

This document specifies the complete technical architecture for OpenTM, a browser-based Trackmania 2020 recreation using WASM. It covers every module, data flow trace, threading model, state machine, build system, and performance budget.

---

## Module Dependency Graph

### Module Definitions

Every module is an npm workspace package under `packages/`. Rust/WASM modules are compiled via wasm-pack and published as npm packages within the monorepo.

#### `@opentm/core`
- **Language**: TypeScript
- **Purpose**: Foundational math types (Vec3, Quat, Mat4, Iso4), time utilities, constants, event bus, typed IDs
- **Depends on**: Nothing (zero dependencies -- this is the leaf)
- **Depended on by**: Every other module
- **Approximate size**: ~2,500 LOC
- **Reason**: TM2020 uses a left-handed Y-up coordinate system with Iso4 (3x3 rotation + vec3 position, 48 bytes) as the fundamental transform [doc 19 Section 9, VERIFIED]. Every module needs these types. Centralizing them avoids circular dependencies and ensures consistent coordinate conventions.

**Key types**:
```typescript
// Iso4: 3x3 rotation matrix (row-major) + position. 48 bytes.
// Source: doc 19 Section 9. CERTAIN.
export interface Iso4 {
  xx: number; xy: number; xz: number;
  yx: number; yy: number; yz: number;
  zx: number; zy: number; zz: number;
  tx: number; ty: number; tz: number;
}

export interface Vec3 { x: number; y: number; z: number; }
export interface Vec2 { x: number; y: number; }
export interface Quat { x: number; y: number; z: number; w: number; }

// Mat4: 4x4 column-major matrix (WebGPU convention).
export type Mat4 = Float32Array; // 16 elements

// Time: microsecond internal units. Source: doc 10 Section 1.3. CERTAIN.
export const TICK_RATE = 100;       // Hz. PLAUSIBLE (community-established).
export const TICK_DT = 0.01;        // 10ms
export const TICK_DT_MICROS = 10_000_000;
export const BLOCK_SIZE = 32.0;     // meters per block unit. CERTAIN (doc 19 Section 8).
```

#### `@opentm/gbx-parser`
- **Language**: TypeScript
- **Purpose**: GBX file reading, LZO decompression, class registry, chunk dispatch, LookbackString handling
- **Depends on**: `@opentm/core`
- **Depended on by**: `@opentm/map`, `@opentm/ghost`, `@opentm/assets`, `@opentm/editor`
- **Approximate size**: ~8,000 LOC
- **Reason**: GBX is the universal container format for maps, items, ghosts, replays, materials, and meshes [doc 16, VERIFIED from 5 real files in doc 26]. Everything loads through GBX. The parser must handle: magic/version/flags header, header chunks with index table, LookbackString system (4 flag modes), reference table (max 49,999 external refs), LZO1X body decompression (confirmed from real files in doc 26, NOT zlib for body), 0xFACADE01 sentinel, 200+ class ID remappings [doc 16 Section 11], and a chunk handler registry dispatching by (classId | chunkIndex).

**Key interfaces**:
```typescript
export interface GbxFile {
  version: number;              // 3-6, TM2020 = 6. CERTAIN.
  formatFlags: GbxFormatFlags;  // BUCR/BUCE. CERTAIN.
  classId: number;              // MwClassId of root node
  headerChunks: HeaderChunk[];
  references: ExternalReference[];
  bodyChunks: BodyChunk[];
}

export interface ChunkRegistry {
  register(chunkId: number, handler: ChunkHandler): void;
  parse(chunkId: number, reader: BinaryReader, lookback: LookbackStringTable): unknown;
}
```

**Critical correction from doc 26**: GBX body compression uses **LZO1X**, not zlib. The original doc 15 said zlib but real file analysis (doc 26 Section 2) confirmed LZO. The parser must bundle an LZO decompressor (lzo1x.js or WASM port). zlib IS used for other data (lightmaps, ghosts).

#### `@opentm/physics`
- **Language**: Rust compiled to WASM via wasm-pack
- **Purpose**: Vehicle simulation, collision detection, force models, integration, surface effects
- **Depends on**: `@opentm/core` (type definitions shared via a generated TypeScript interface layer)
- **Depended on by**: `@opentm/ghost` (for deterministic replay), `@opentm/camera` (for vehicle state)
- **Approximate size**: ~12,000 LOC Rust + ~1,500 LOC TypeScript bindings
- **Reason**: Physics MUST run in WASM for two reasons: (1) performance -- adaptive sub-stepping with up to 1000 sub-steps per 10ms tick [doc 10, CERTAIN] requires tight loops that JIT-compiled JS cannot reliably optimize; (2) determinism -- replay validation requires bit-exact floating-point results, and Rust WASM with `#[deny(clippy::float_arithmetic)]` guards plus explicit f32 operations gives predictable IEEE 754 behavior that JS's JIT-optimized doubles cannot guarantee.

**Pipeline** (from doc 10 Section 1, VERIFIED):
```
physicsStep(vehicles, tick, collisionWorld)
  for each vehicle:
    computeSubstepCount(velocity)    // velocity-dependent, cap 1000
    for substep in 0..count:
      detectContacts()               // broadphase BVH + narrowphase GJK
      computeForces(model_type)      // switch on vehicle_model+0x1790 (7 cases)
      applyTurboForce()              // linear ramp: (elapsed/duration) * strength
      clampSpeed()                   // vehicle_model+0x2F0 max speed
      integrateEuler(dt)             // Forward Euler. CERTAIN (doc 14 cross-ref).
      resolveCollisions()            // iterative friction solver
    copyTransformToPrevious()
```

**Force model dispatch** (doc 10 Section 2.1, doc 22, VERIFIED):
| Case | Model | Vehicle(s) | Status |
|------|-------|-----------|--------|
| 0/1/2 | Base 4-wheel (300+ LOC decompiled) | Legacy | DECOMPILED (doc 22) |
| 3 | 2-wheel bicycle (250+ LOC, Pacejka-like) | Unknown legacy | DECOMPILED (doc 22) |
| 4 | TMNF-era | Unknown | NOT decompiled |
| 5 | CarSport/Stadium (350+ LOC, 9 sub-functions) | CarSport | DECOMPILED (doc 22) |
| 6 | Snow/Rally | CarSnow, CarRally | NOT decompiled |
| 0xB/11 | Desert | CarDesert | NOT decompiled |

**Rust WASM interface**:
```rust
#[wasm_bindgen]
pub struct PhysicsWorld {
    vehicles: Vec<VehicleState>,
    collision: CollisionWorld,  // wraps rapier3d
    tick: u64,
}

#[wasm_bindgen]
impl PhysicsWorld {
    pub fn step(&mut self, input_buffer: &[u8]) -> Box<[u8]>;
    pub fn add_collision_mesh(&mut self, vertices: &[f32], indices: &[u32], surface_id: u16);
    pub fn reset_vehicle(&mut self, id: u32, position: &[f32], rotation: &[f32]);
    pub fn get_vehicle_state(&self, id: u32) -> Box<[u8]>;
}
```

The `step()` and `get_vehicle_state()` functions communicate via serialized byte buffers to avoid WASM/JS boundary overhead on the hot path. The exact layout is defined in Section 3 (Threading Model).

#### `@opentm/renderer`
- **Language**: TypeScript + WGSL
- **Purpose**: WebGPU deferred rendering pipeline, G-buffer management, shadow mapping, post-processing, mesh/material/texture GPU resource management
- **Depends on**: `@opentm/core`, `@opentm/assets` (for loaded textures/meshes)
- **Depended on by**: `@opentm/ui` (for overlay compositing), `@opentm/editor` (for editor viewport)
- **Approximate size**: ~15,000 LOC TypeScript + ~3,000 LOC WGSL
- **Reason**: TM2020 uses a 19-pass deferred pipeline [doc 15 Section 7, doc 11, VERIFIED]. The browser recreation starts with a simplified pipeline and progressively adds passes.

**MVP pipeline** (4 passes):
1. Shadow pass (PSSM, 2 cascades initially, upgrade to 4)
2. G-buffer fill (DeferredWrite -- 4 MRT: diffuse, specular, normal, lightMask + depth24plus-stencil8)
3. Deferred lighting (full-screen triangle, PBR GGX, directional sun + ambient)
4. Post-process (tone mapping + FXAA)

**Full pipeline** target (matches doc 11 Section 3, 19 passes):
DipCulling -> DeferredWrite -> DeferredWriteFNormal -> DeferredWriteVNormal -> DeferredDecals -> DeferredBurn -> DeferredShadow (PSSM 4-cascade) -> DeferredAmbientOcc (SSAO) -> DeferredFakeOcc -> CameraMotion -> DeferredRead -> DeferredReadFull -> Reflects_CullObjects -> DeferredLighting -> CustomEnding -> DeferredFogVolumes -> DeferredFog -> LensFlares -> FxTXAA

**Vertex formats** (doc 11 Section 1, VERIFIED from DXVK log):
- Block: stride 56, 7 attributes (pos float32x3, normal snorm16x4, color unorm8x4-bgra, uv0 float32x2, uv1 float32x2, tangent snorm16x4, bitangent snorm16x4)
- Simple: stride 28, 3 attributes
- Lightmapped: stride 52, 6 attributes

#### `@opentm/audio`
- **Language**: TypeScript
- **Purpose**: Engine sound synthesis (RPM-based crossfade), spatial 3D SFX, music playback, surface sounds
- **Depends on**: `@opentm/core`
- **Depended on by**: Nothing directly (event-driven; listens to game events)
- **Approximate size**: ~3,000 LOC
- **Reason**: TM2020 uses OpenAL with a 3-layer stack (CAudioManager -> CAudioPort -> COalAudioPort) [doc 15 Section 1, doc 24, VERIFIED]. Web Audio API maps directly: AudioContext = alcCreateContext, PannerNode = AL source with 3D position, GainNode = AL gain. Engine sound uses CPlugSoundEngine2 with layered throttle/release/idle/limiter samples crossfaded by RPM [doc 22, doc 24 Section 4].

**Architecture**:
```
AudioManager
  ├── EngineSound (AudioWorklet for low-latency synthesis)
  │     └── 4 sample layers: idle, low, mid, high RPM
  │     └── playbackRate + crossfade gains driven by RPM (0-11000)
  ├── SoundPool (32 spatial sources, PannerNode HRTF)
  │     └── tire screech, impacts, checkpoint, turbo
  ├── MusicPlayer (streaming via fetch + decodeAudioData)
  │     └── crossfade between tracks
  └── MasterGain -> AudioContext.destination
```

#### `@opentm/input`
- **Language**: TypeScript
- **Purpose**: Keyboard and gamepad handling, input recording for ghosts, action mapping
- **Depends on**: `@opentm/core`
- **Depended on by**: `@opentm/physics` (receives input per tick), `@opentm/ghost` (records input history), `@opentm/ui` (menu navigation)
- **Approximate size**: ~1,500 LOC
- **Reason**: TM2020 uses DirectInput 8 for keyboard/mouse and XInput 9.1.0 for gamepads [doc 15 Section 2, VERIFIED]. Input values are: steer (-1 to 1), gas (0-1), brake (0-1), isBraking (bool), vertical (float) [doc 19 Section 1, CERTAIN]. The Gamepad API polling model matches XInput's design. Input must be recorded per-tick for ghost replay.

**Interface**:
```typescript
export interface InputState {
  steer: number;       // -1.0 to 1.0
  gas: number;         // 0.0 to 1.0
  brake: number;       // 0.0 to 1.0
  isBraking: boolean;
  vertical: number;    // reactor input
  respawn: boolean;
  horn: boolean;
}

export interface InputManager {
  sampleForTick(tick: number): InputState;
  getHistory(): InputSample[];
  resetHistory(): void;
}
```

#### `@opentm/camera`
- **Language**: TypeScript
- **Purpose**: Camera controllers (race chase, orbital, free-fly, first-person, replay)
- **Depends on**: `@opentm/core`, `@opentm/physics` (reads vehicle state for chase cam target)
- **Depended on by**: `@opentm/renderer` (provides view/projection matrices)
- **Approximate size**: ~2,500 LOC
- **Reason**: TM2020 has 12 camera controller classes [doc 15 Section 3, VERIFIED]. The orbital camera math is fully documented [doc 19 Section 7]: `h = (HAngle + PI/2) * -1; v = VAngle; axis = vec4(1,0,0,0) rotated by v around Z then h around Y; cameraPos = targetPos + axis.xyz * distance`. Chase camera parameters (follow distance, height, spring stiffness) are stored in VehicleCameraRace2Model.gbx / Race3Model.gbx files -- format unknown, so these will need tuning.

**Controllers**:
| Controller | TM2020 Equivalent | Priority |
|-----------|-------------------|----------|
| ChaseCamera | Race2/Race3 | MVP |
| OrbitalCamera | EditorOrbital | MVP (editor) |
| FreeCamera | Free | MVP (debug) |
| FirstPersonCamera | VehicleInternal | Post-MVP |
| ReplayCamera | Replay (spectator type 0) | Post-MVP |

#### `@opentm/network`
- **Language**: TypeScript
- **Purpose**: Nadeo API client (auth, map download, leaderboards, ghost download), WebSocket/WebRTC for future multiplayer
- **Depends on**: `@opentm/core`
- **Depended on by**: `@opentm/ghost` (ghost download), `@opentm/map` (map download), `@opentm/ui` (leaderboard display)
- **Approximate size**: ~4,000 LOC
- **Reason**: TM2020 authentication is a 3-step flow: UPC ticket -> UbiServices session -> Nadeo token exchange [doc 17 Section 2, doc 19 Section 6, VERIFIED]. API uses `Authorization: nadeo_v1 t=<token>` header format [CERTAIN]. Three API domains: Core (prod.trackmania.core.nadeo.online), Live (live-services.trackmania.nadeo.live), Meet (meet.trackmania.nadeo.club) [CERTAIN]. 80+ endpoints documented from community sources [doc 29 Section 4].

**Browser auth limitation**: UPC SDK is a Windows DLL. The browser client needs a backend proxy server for the initial auth step, or uses the community "dedicated server" credential approach. Post-auth, all API calls work via standard `fetch()`.

**Future multiplayer**: NOT replicating Nadeo's proprietary UDP protocol (undocumented). Instead: custom protocol over WebSocket (reliable channel for game state) + WebRTC DataChannel (unreliable channel for real-time position updates). Deterministic physics means clients only send inputs and verify periodically.

#### `@opentm/scripting`
- **Language**: TypeScript
- **Purpose**: ManiaScript interpreter (lexer, parser, tree-walking evaluator, coroutine scheduler, engine bindings)
- **Depends on**: `@opentm/core`
- **Depended on by**: `@opentm/ui` (ManiaLink event handlers), `@opentm/map` (game mode rules)
- **Approximate size**: ~10,000 LOC (if built)
- **Reason**: ManiaScript drives game mode rules, custom HUD, and ManiaLink interactivity. The lexer token table is fully documented: 12 data types, 7 directives, 50+ tokens [doc 15 Section 10, VERIFIED]. Runtime semantics (sleep/yield/wait/meanwhile scheduling model) are UNKNOWN. For MVP, this module is **SKIPPED** -- standard race mode is hardcoded. When needed, the coroutine model maps to JavaScript async generators.

**MVP strategy**: Skip entirely. Hardcode TimeAttack race rules (start timer on first input, record checkpoints, stop on finish). This covers 90% of single-player use.

#### `@opentm/ui`
- **Language**: TypeScript + Svelte
- **Purpose**: HUD (speedometer, race timer, checkpoint splits), menus (main menu, map select, settings, results), ManiaLink renderer (post-MVP)
- **Depends on**: `@opentm/core`, `@opentm/network` (for leaderboard data)
- **Depended on by**: Nothing (leaf node; renders HTML/CSS overlay)
- **Approximate size**: ~6,000 LOC
- **Reason**: TM2020 uses CControlEngine with ManiaLink XML markup [doc 13 Section 4]. The browser has a massive advantage: HTML/CSS is the most mature UI technology available [doc 20 Section 12 recommendation]. DO NOT replicate ManiaLink for the UI layer. Build native web UI with Svelte for minimal bundle size and fast reactivity. ManiaLink rendering (for loading community content) is a separate post-MVP concern.

#### `@opentm/editor`
- **Language**: TypeScript + Svelte
- **Purpose**: Map editor (block palette, grid placement, orbital camera, undo/redo, map validation, save/export)
- **Depends on**: `@opentm/core`, `@opentm/map`, `@opentm/renderer`, `@opentm/camera`, `@opentm/gbx-parser`
- **Depended on by**: Nothing
- **Approximate size**: ~8,000 LOC
- **Reason**: TM2020 has 15+ editor types with the map editor at state 0xDE5 calling FUN_140b827b0 [doc 12 Section 1.3]. Block placement uses a 32m grid on X/Z with 8m Y sub-unit; items use free Vec3 [doc 28 Section 1, VERIFIED]. Block placement validation rules (connectivity, adjacency) are NOT documented and represent the hardest unknow for this module.

**MVP scope**: Basic block placement on grid. No validation. Orbital camera with documented math. Command-pattern undo/redo. Export as .Map.Gbx via gbx-ts serialization (if supported) or custom JSON format.

#### `@opentm/ghost`
- **Language**: TypeScript
- **Purpose**: Ghost recording (input state per tick), ghost playback (feed inputs to physics), ghost interpolation for rendering, ghost serialization/compression, official ghost import (post-MVP)
- **Depends on**: `@opentm/core`, `@opentm/physics` (deterministic replay), `@opentm/input` (input history), `@opentm/network` (ghost download)
- **Depended on by**: `@opentm/renderer` (semi-transparent ghost car rendering)
- **Approximate size**: ~3,000 LOC
- **Reason**: Ghosts are the core competitive feature. TM2020 records inputs and replays them through deterministic physics [doc 19 Section 1]. The binary ghost format uses int16/int8 encoding for position/rotation/speed [doc 29 Section 6.2], but for OpenTM we use our own format: JSON array of `{tick, steer, gas, brake, vertical}` compressed with LZ4 for storage. Official TM2020 ghost loading requires further RE of the binary format.

**Custom ghost format**:
```typescript
interface GhostFile {
  version: 1;
  mapUid: string;
  playerName: string;
  vehicleType: number;
  finishTime: number;          // ms
  checkpointTimes: number[];   // ms per CP
  samples: GhostSample[];     // one per physics tick
}

interface GhostSample {
  tick: number;
  steer: number;   // quantized to int16 (-32768..32767) for compression
  gas: number;     // quantized to uint8 (0..255)
  brake: number;   // quantized to uint8 (0..255)
  vertical: number; // quantized to int8 (-128..127)
}
```

#### `@opentm/map`
- **Language**: TypeScript
- **Purpose**: Map data model (block grid, item placements, waypoint graph, surface table), map loading orchestration (GBX parse -> block instantiation -> collision mesh generation -> scene graph), block/item management
- **Depends on**: `@opentm/core`, `@opentm/gbx-parser`, `@opentm/assets`
- **Depended on by**: `@opentm/physics` (collision meshes), `@opentm/renderer` (scene graph), `@opentm/editor`, `@opentm/ghost` (map validation)
- **Approximate size**: ~6,000 LOC
- **Reason**: Maps are CGameCtnChallenge (class 0x03043000) with a 23-stage loading pipeline [doc 22, doc 28]. The block system uses 32m units with blocks identified by name + variant + position + rotation [doc 19 Section 8]. Materials map to 19 surface types that determine physics friction [doc 19 Section 10, 208 materials catalogued]. Waypoint blocks (start, finish, checkpoint) must be identified for race logic.

**Loading pipeline** (browser version of TM2020's 23-stage pipeline):
```
1. fetch(mapUrl) -> ArrayBuffer
2. GbxParser.parse(buffer) -> GbxFile
3. Extract header chunks: map info, common header, thumbnail
4. Parse body chunks: block list, item list, embedded objects
5. For each block:
   a. Resolve block name -> mesh asset (from pre-extracted block library)
   b. Compute world transform: gridPos * 32m + rotation
   c. Tag waypoint blocks (start/finish/checkpoint)
   d. Look up surface IDs from block materials
6. For each item:
   a. Resolve item name -> mesh asset
   b. Use embedded position/rotation (free Vec3, not grid-snapped)
7. Generate collision mesh (aggregate all block collision geometry)
8. Build scene graph (spatial hierarchy for frustum culling)
9. Build waypoint graph (ordered checkpoint sequence)
```

#### `@opentm/assets`
- **Language**: TypeScript
- **Purpose**: Asset loading and caching (HTTP fetch with IndexedDB cache), texture decoding (DDS, WebP, PNG), mesh loading (pre-extracted glTF/GLB block meshes), material creation, asset manifest management
- **Depends on**: `@opentm/core`
- **Depended on by**: `@opentm/map`, `@opentm/renderer`, `@opentm/editor`
- **Approximate size**: ~4,000 LOC
- **Reason**: Block meshes live inside NadeoPak files (.pak) which use a proprietary "NadeoPak" header format [doc 26 Section 10] -- NOT GBX format. Parsing these at runtime in the browser is not feasible (encrypted with per-account keys [doc 22]). Instead, meshes are **pre-extracted offline** using NadeoImporter or community tools and served as static glTF/GLB assets from a CDN. The asset module manages fetching, caching (IndexedDB for offline capability), and GPU upload.

**Asset pipeline** (offline, runs during build):
```
1. NadeoImporter or gbx-net: extract block meshes from .pak files
2. Convert to glTF 2.0 (preserving UVs, normals, tangents, material refs)
3. Extract textures (DDS -> PNG/WebP transcoding, or KTX2 for GPU compression)
4. Generate asset manifest JSON (block_name -> mesh_url, texture_url)
5. Upload to CDN / serve from static directory
```

**Runtime asset loading**:
```typescript
interface AssetManager {
  loadBlockMesh(blockName: string): Promise<MeshData>;
  loadTexture(texturePath: string): Promise<GPUTexture>;
  loadMaterial(materialName: string): Promise<MaterialData>;
  getManifest(): AssetManifest;
  getCacheStats(): { cached: number; total: number; sizeBytes: number };
}
```

### Dependency Graph

```
                           @opentm/core
                               |
          +----+----+----+----+----+----+----+----+
          |    |    |    |    |    |    |    |    |
        gbx  phy  ren  aud  inp  cam  net  scr  ui
        par  sics der  io   ut   era  wrk  ipt  (svelte)
        ser             |         |         ing
          |    |    |   |    |    |    |         |
          +----+----+--assets    |    |         |
          |              |       |    |         |
         map----------+  |       |    |         |
          |            |  |       |    |         |
        ghost---------+  +-------+    |         |
          |                           |         |
        editor-----------------------+----------+

Legend:
  phy = @opentm/physics (Rust/WASM)
  scr = @opentm/scripting (deferred)
  All others = TypeScript
```

**Arrows indicate "depends on"**. Reading top-to-bottom:
- `core` has zero dependencies
- `gbx-parser`, `physics`, `renderer`, `audio`, `input`, `camera`, `network`, `scripting`, `ui` all depend on `core`
- `assets` depends on `core` only
- `map` depends on `core`, `gbx-parser`, `assets`
- `ghost` depends on `core`, `physics`, `input`, `network`
- `camera` depends on `core`, reads vehicle state from `physics` (via shared state, not npm dependency)
- `renderer` depends on `core`, `assets`
- `editor` depends on `core`, `map`, `renderer`, `camera`, `gbx-parser`
- `ui` depends on `core`, `network`

### Module Size Summary

| Module | Language | Est. LOC | MVP? | Build Phase |
|--------|----------|----------|------|-------------|
| core | TS | 2,500 | Yes | 1 |
| gbx-parser | TS | 8,000 | Yes | 1 |
| physics | Rust/WASM + TS bindings | 13,500 | Yes (TS prototype first) | 2-3 |
| renderer | TS + WGSL | 18,000 | Yes (forward first) | 1-2 |
| audio | TS | 3,000 | No | 4 |
| input | TS | 1,500 | Yes | 2 |
| camera | TS | 2,500 | Yes | 2 |
| network | TS | 4,000 | No (MVP is offline) | 5 |
| scripting | TS | 10,000 | No (skipped for MVP) | 5+ |
| ui | TS + Svelte | 6,000 | Yes (minimal HUD) | 3 |
| editor | TS + Svelte | 8,000 | No | 5+ |
| ghost | TS | 3,000 | Yes (recording only) | 3 |
| map | TS | 6,000 | Yes | 1-2 |
| assets | TS | 4,000 | Yes | 1 |
| **Total** | | **~90,000** | | |

---

## Data Flow Architecture

### Load a Map

Trace from URL to rendered scene:

```
User provides URL or selects map
         |
         v
[1] fetch(url) -> ArrayBuffer
    Module: @opentm/network or browser fetch
    Format: Raw bytes (typically 50KB-2MB compressed)
         |
         v
[2] GbxParser.parse(buffer) -> GbxFile
    Module: @opentm/gbx-parser
    Steps:
      a. Validate magic "GBX" (3 bytes)
      b. Read version (uint16, expect 6 for TM2020)
      c. Read format flags (BUCR = Binary, Uncompressed header, Compressed body, References)
      d. Read classId (uint32), expect 0x03043000 for CGameCtnChallenge
      e. Parse header chunk index table (chunkId uint32, size uint32 with bit31 = heavy flag)
      f. Parse header chunk data (concatenated payloads)
      g. Read node count, parse reference table (external .Gbx dependencies)
      h. Read compressed body: uncompressed_size (uint32), compressed_size (uint32),
         LZO1X decompress -> body bytes
      i. Parse body chunk stream until 0xFACADE01 sentinel
      j. For each chunk: check SKIP marker, dispatch to registered ChunkHandler
    Output: Structured GbxFile with typed chunk data
         |
         v
[3] MapLoader.load(gbxFile) -> MapData
    Module: @opentm/map
    Steps:
      a. Extract metadata from header chunk 0x03043003 (mapUid, environment, author, name)
      b. Parse block list from body chunks:
         - Each block: blockName (string), coord (Nat3: gridX, gridY, gridZ),
           direction (0-3 = N/E/S/W), flags (bit 0 = ground, bit 12-14 = color variant)
         - Grid position -> world position: x = gridX * 32m, y = (gridY-8) * 8m, z = gridZ * 32m
           [doc 28 Section 1, VERIFIED; Y has a -8 offset for maps with grid origin at y=8]
      c. Parse free item placements from body chunks:
         - Each item: itemPath (string), position (Vec3), rotation (Vec3 euler or Quat),
           pivotPosition (Vec3)
      d. Build block instances: for each block in list,
         - Resolve blockName -> BlockDefinition from block library
         - Compute world transform (Iso4) from grid coord + direction
         - Tag waypoint type: Start, Finish, Checkpoint, StartFinish, None
         - Record surface IDs from block materials
      e. Build waypoint sequence (ordered list of checkpoint blocks for race logic)
    Output: MapData { blocks[], items[], waypoints[], metadata }
         |
         v
[4] AssetManager.loadBlockMeshes(mapData.blocks) -> MeshData[]
    Module: @opentm/assets
    Steps:
      a. Collect unique block names from map
      b. For each unique block: check IndexedDB cache
      c. Cache miss: fetch glTF/GLB from CDN (e.g., /assets/blocks/StadiumRoadMainStraight.glb)
      d. Parse glTF: extract vertex buffers (stride 56 for blocks), index buffers,
         material references, bounding boxes
      e. Cache in IndexedDB for future loads
    Output: Map<blockName, MeshData> (CPU-side mesh data)
         |
         v
[5] Renderer.uploadMeshes(meshDataMap) -> GPUMeshes
    Module: @opentm/renderer
    Steps:
      a. For each unique mesh: create GPUBuffer for vertices (vertex layout stride 56)
      b. Create GPUBuffer for indices (uint16 or uint32)
      c. Load and upload textures: diffuse (rgba8unorm-srgb), normal map (rgba8unorm)
      d. Create GPUBindGroups for materials
    Output: GPU resources ready for drawing
         |
         v
[6] SceneGraph.build(mapData, gpuMeshes) -> SceneGraph
    Module: @opentm/renderer
    Steps:
      a. For each block instance: create SceneNode { worldTransform: Mat4, meshRef, materialRef }
      b. For each item instance: same
      c. Build BVH spatial index for frustum culling
      d. Identify shadow-casting geometry (all opaque blocks)
    Output: SceneGraph ready for render loop
         |
         v
[7] CollisionMeshGenerator.build(mapData, meshDataMap) -> CollisionMesh
    Module: @opentm/map -> @opentm/physics
    Steps:
      a. For each block: transform mesh vertices to world space
      b. Tag each triangle with surface ID (from material -> surface lookup table)
      c. Aggregate into single collision mesh
      d. Upload to physics world: PhysicsWorld.add_collision_mesh(vertices, indices, surfaceIds)
    Output: rapier3d collision world with trimesh colliders
         |
         v
[8] Renderer begins rendering scene each frame
    Module: @opentm/renderer
    Per frame: cull visible nodes, draw shadow pass, draw G-buffer, deferred lighting, post-process
```

**Total latency budget for map load**: Target < 5 seconds on 100 Mbps connection with warm cache, < 15 seconds cold. The bottleneck is asset fetching (step 4). Mitigate with: (a) aggressive IndexedDB caching, (b) parallel fetch of block meshes, (c) progressive loading (render blocks as they arrive), (d) texture streaming (load low-res first, swap to high-res).

### One Physics Frame

Trace from input to vehicle state output:

```
requestAnimationFrame callback fires
         |
         v
[1] FixedTimestepAccumulator: accumulate elapsed wall-clock time
    If accumulated >= TICK_DT (10ms):
      consume one tick, decrement accumulator
      (Multiple ticks possible if frame took > 10ms)
         |
         v
[2] InputManager.sampleForTick(tickNumber) -> InputState
    Module: @opentm/input (main thread)
    Steps:
      a. Poll gamepad (navigator.getGamepads()[0])
      b. Read keyboard key set
      c. Merge: gamepad analog overrides keyboard digital if gamepad connected
      d. Clamp: steer [-1,1], gas [0,1], brake [0,1]
      e. Record to input history: { tick, steer, gas, brake, vertical }
    Output: InputState { steer, gas, brake, isBraking, vertical, respawn }
         |
         v
[3] Serialize InputState to SharedArrayBuffer input region
    (See Section 3 for SAB layout)
    Write: steer(f32), gas(f32), brake(f32), vertical(f32), flags(u32)
    Signal physics worker via Atomics.notify()
         |
         v
[4] Physics Worker receives input, runs PhysicsWorld.step()
    Module: @opentm/physics (Web Worker, WASM)
    Steps (inside Rust WASM):

      a. Read input from shared buffer
      b. For the active vehicle:
         i.   Compute substep count from velocity magnitude:
              substeps = max(1, ceil(|velocity| * TICK_DT / COLLISION_MARGIN))
              capped at 1000. [doc 10 Section 7, CERTAIN]
         ii.  sub_dt = TICK_DT / substeps
         iii. For each substep:
              - Collision broadphase: query BVH for nearby trimesh triangles
                (rapier3d handles this internally)
              - Collision narrowphase: compute contact points, normals, depths
              - Per-wheel ground contact: 4 raycasts downward from wheel positions
                Length = suspension rest length (0.15m APPROXIMATE)
                Hit: record surface ID, contact normal, penetration depth
                Miss: wheel is airborne
              - Compute forces via force model dispatch:
                switch(vehicle.force_model_type):
                  case 5 (CarSport): [doc 22, DECOMPILED]
                    - Per-wheel suspension: spring_force = K * compression + C * velocity
                    - Per-wheel lateral grip: Pacejka-like model
                      lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef
                    - Engine torque: throttle * max_torque * gear_ratio
                    - Brake torque: brake * max_brake
                    - Anti-roll bar: transfers load between left/right wheels
                    - Aerodynamic drag: drag_coef * |v|^2 * v_hat
                    - Downforce: downforce_coef * |v|^2 (added to Y force)
                    - Drift state machine: none(0) -> building(1) -> committed(2)
                      Drift accumulates: lateral_slip * drift_rate * dt
                    - Steering: steer_angle = input_steer * max_steer_angle * speed_factor
              - Apply turbo force if active:
                t = elapsed_ticks / duration_ticks
                force = t * strength * model_scale * forward_direction
                [doc 10 Section 4.3: linear ramp UP, CERTAIN but counterintuitive]
              - Apply gravity: force.y += mass * GRAVITY * gravity_coef
              - Clamp speed: if |vel| > max_speed, normalize and scale
              - Forward Euler integration:
                vel += (total_force / mass) * sub_dt
                pos += vel * sub_dt
                angular_vel += (total_torque / inertia) * sub_dt
                rotation = update_rotation(rotation, angular_vel, sub_dt)
                orthogonalize rotation (Gram-Schmidt) for numeric stability
              - Collision response:
                For each contact with depth > 0:
                  Push out along normal * depth
                  Reflect velocity: v -= (1 + restitution) * (v . n) * n
                  Apply friction impulse (iterative solver,
                    separate static/dynamic iteration counts [doc 10 Section 5])

      c. Update derived state:
         frontSpeed = dot(worldVel, forwardDir)    // m/s
         sideSpeed = dot(worldVel, rightDir)       // m/s
         isGroundContact = any wheel has contact
         Update RPM from wheel rotation speed + gear ratio
         Update turbo timer (decrement)
         Copy current transform to previousTransform

      d. Write output vehicle state to SharedArrayBuffer output region:
         position (3 x f32), rotation (9 x f32, iso4 rotation part),
         velocity (3 x f32), frontSpeed (f32), rpm (f32),
         wheel states (4 x {damperLen, steerAngle, wheelRot} = 4 x 3 x f32),
         turbo flags (u32), gear (u32)

      e. Atomics.notify() main thread that output is ready
         |
         v
[5] Main thread reads vehicle state from SAB output region
    Interpolate between previous and current state for smooth rendering:
      alpha = accumulator / TICK_DT  (fractional tick remaining)
      renderPosition = lerp(prevPos, currPos, alpha)
      renderRotation = slerp(prevRot, currRot, alpha)
         |
         v
[6] Camera updates target to interpolated vehicle position
    Chase camera: spring-damper tracks vehicle with lag
         |
         v
[7] Renderer draws vehicle at interpolated position
```

### One Render Frame

Trace from scene graph to presented pixels:

```
requestAnimationFrame fires
         |
         v
[1] Read interpolated vehicle state (from physics, Section 2.2 step 5)
    Update camera matrices (view + projection)
    Compute sun direction from map mood/time-of-day
         |
         v
[2] Frustum Culling (DipCulling equivalent)
    Module: @opentm/renderer
    Steps:
      a. Extract 6 frustum planes from viewProjection matrix
      b. Walk BVH: test each node's AABB against frustum
      c. Output: visible SceneNode[] (typically 30-60% of total nodes)
      d. Sort opaques front-to-back (minimizes overdraw in G-buffer fill)
      e. Sort transparents back-to-front (correct alpha blending)
    Budget: < 0.5ms for 5000 nodes
         |
         v
[3] Shadow Pass (DeferredShadow equivalent, PSSM)
    Module: @opentm/renderer
    Steps:
      a. Compute cascade split distances:
         splits = logarithmic distribution over [near, far] with 4 cascades
         [doc 11 Section 4: MapShadowSplit0-3, CERTAIN]
      b. For each cascade (0..3):
         - Compute tight light-space frustum enclosing the cascade slice
         - Render all shadow-casting geometry into depth-only pass
         - Output: depth texture layer in shadow map array
      c. Shadow map: 2048x2048 per cascade (configurable), depth32float format
    Budget: < 2ms for 4 cascades
         |
         v
[4] G-Buffer Fill (DeferredWrite)
    Module: @opentm/renderer
    Steps:
      a. Begin render pass with 4 color attachments + depth:
         RT0: diffuse (rgba8unorm-srgb) -- albedo * vertex color
         RT1: specular (rgba8unorm) -- F0, roughness, metallic
         RT2: normal (rgba16float) -- camera-space normal from TBN * normal map
         RT3: lightMask (rgba8unorm) -- lighting flags
         Depth: depth24plus-stencil8
      b. For each visible opaque SceneNode:
         - Bind model uniform (world transform, normal matrix)
         - Bind material textures (diffuse, normal map)
         - Draw indexed (vertex buffer stride 56)
      c. End render pass
    Budget: < 3ms for 2000 draw calls (batched by material)
         |
         v
[5] Deferred Lighting (DeferredRead + DeferredLighting)
    Module: @opentm/renderer
    Steps:
      a. Bind G-buffer textures + shadow map as inputs
      b. Full-screen triangle (3 vertices, no VB needed)
      c. Fragment shader:
         - Read albedo, specular params, normal, depth from G-buffer
         - Reconstruct world position from depth + inverse view-projection
         - For directional sun light:
           PBR GGX BRDF: diffuse (Lambert) + specular (Cook-Torrance)
           NdotL attenuation, shadow lookup (PSSM cascade selection + PCF)
         - Ambient: hemisphere ambient (sky color top, ground color bottom)
         - For each point/spot light (if any):
           Same BRDF, distance attenuation, shadow (optional)
      d. Output: HDR color (rgba16float intermediate)
    Budget: < 1.5ms
         |
         v
[6] Forward Transparent Pass (Alpha01 + AlphaBlend)
    Module: @opentm/renderer
    Steps:
      a. Render alpha-tested geometry (glass, grates) with depth test, no depth write
      b. Render alpha-blended geometry (particles, ghost car) back-to-front
      c. Uses the same depth buffer from G-buffer pass for depth testing
    Budget: < 1ms
         |
         v
[7] Post-Processing Pipeline
    Module: @opentm/renderer
    Steps (compute shader passes):
      a. SSAO (optional): screen-space ambient occlusion
         Input: depth + normals. Output: AO texture.
         Budget: 0.5ms (half-resolution)
      b. Bloom: downsample chain (6 levels, 13-tap filter) + upsample chain (additive blend)
         Input: HDR color. Output: bloom texture.
         Budget: 0.5ms
      c. Composite: combine HDR color + bloom + AO
      d. Tone mapping: filmic curve (Uncharted 2 or ACES)
         Input: HDR composite. Output: LDR sRGB.
      e. FXAA (MVP) or TAA (full):
         Input: LDR color. Output: anti-aliased final color.
         Budget: 0.3ms (FXAA)
    Total post-process budget: < 1.5ms
         |
         v
[8] Present
    Module: @opentm/renderer
    Steps:
      a. Copy final color to swap chain texture
      b. device.queue.submit()
      c. Browser composites with HTML overlay (HUD, menus)
```

### Record a Ghost

```
Race begins (first gas input detected)
         |
         v
[1] InputManager starts recording
    Module: @opentm/input
    Every physics tick: push { tick, steer, gas, brake, vertical } to inputHistory[]
    Memory: ~20 bytes per tick * 100 ticks/s * 300s race = ~600KB uncompressed
         |
         v
[2] Race state tracks checkpoints
    Module: @opentm/map (waypoint detection)
    On checkpoint hit: record { cpIndex, tick, raceTimeMs }
    On finish: record finishTimeMs, stop recording
         |
         v
[3] Serialize ghost
    Module: @opentm/ghost
    Steps:
      a. Build GhostFile header: { version, mapUid, playerName, vehicleType, finishTime, cpTimes }
      b. Quantize input samples:
         steer: f32 -> int16 (* 32767)
         gas: f32 -> uint8 (* 255)
         brake: f32 -> uint8 (* 255)
         vertical: f32 -> int8 (* 127)
      c. Delta-encode: store difference from previous sample (most frames have no input change)
      d. Output: Uint8Array (header + samples)
    Output size: ~100-200KB for a 3-minute run
         |
         v
[4] Compress
    Module: @opentm/ghost
    Algorithm: LZ4 (fast compression, good for delta-encoded data with many zeros)
    Compressed size: ~20-50KB typical
         |
         v
[5] Upload (post-MVP)
    Module: @opentm/network
    Steps:
      a. Authenticate with Nadeo API (or custom OpenTM backend)
      b. POST compressed ghost to leaderboard endpoint
      c. Server validates: re-runs physics simulation with recorded inputs,
         checks that finish time matches claimed time (anti-cheat)
```

### Play a Ghost

```
User requests ghost playback (own ghost or downloaded)
         |
         v
[1] Fetch ghost data
    Module: @opentm/network (for remote) or local storage
    If remote: GET from API endpoint or CDN
    If local: read from in-memory buffer or IndexedDB
    Output: compressed Uint8Array
         |
         v
[2] Decompress
    Module: @opentm/ghost
    Algorithm: LZ4 decompress
    Output: raw Uint8Array
         |
         v
[3] Deserialize
    Module: @opentm/ghost
    Steps:
      a. Read header: version, mapUid, playerName, vehicleType, finishTime, cpTimes
      b. Validate mapUid matches currently loaded map (reject if mismatch)
      c. Reverse delta encoding: accumulate deltas to reconstruct absolute values
      d. Dequantize: int16/uint8/int8 -> f32
      e. Build GhostSample[] array indexed by tick number
    Output: GhostPlayback { header, samples: Map<tick, InputState> }
         |
         v
[4] Feed to physics simulation each tick
    Module: @opentm/physics
    Steps:
      a. Create a "ghost vehicle" in the physics world (separate from player vehicle)
      b. Each tick: look up GhostPlayback.samples[currentTick]
         If sample exists: use those inputs
         If gap: hold last known input (rare with per-tick recording)
      c. Run physics step for ghost vehicle with those inputs
         (Same force model, same collision world, same timestep)
      d. Ghost vehicle follows deterministic path
         (If physics is perfectly deterministic, ghost reaches finish at exactly finishTime)
    Output: ghost vehicle state per tick (position, rotation, speed)
         |
         v
[5] Interpolate for rendering
    Module: @opentm/ghost
    Steps:
      a. Same alpha-interpolation as player vehicle (Section 2.2 step 5)
      b. Smooth between physics ticks for 60fps rendering from 100Hz simulation
    Output: interpolated ghost transform
         |
         v
[6] Render ghost
    Module: @opentm/renderer
    Steps:
      a. Draw ghost car mesh at interpolated position/rotation
      b. Apply semi-transparent material (alpha = 0.5)
      c. Draw in forward transparent pass (after G-buffer, before post-process)
      d. Optional: tint by relative speed (green = faster, red = slower)
    Visual: translucent car visible alongside player's car
```

---

## Threading Model

### Thread Allocation

```
┌─────────────────────────────────────────────────────────┐
│ Main Thread                                              │
│                                                          │
│  requestAnimationFrame loop:                             │
│    1. Input sampling (keyboard/gamepad poll)              │
│    2. Write input to SAB, notify physics worker           │
│    3. Read physics output from SAB (if ready)             │
│    4. Camera update                                       │
│    5. Frustum culling                                     │
│    6. WebGPU command encoding + submit                    │
│    7. UI update (Svelte reactive updates)                 │
│    8. Audio parameter updates (rpm, position)             │
│                                                          │
│  NOT on main thread: physics simulation, GBX parsing,    │
│    texture decoding, LZO decompression                   │
└──────────────────────────┬──────────────────────────────┘
                           │ SharedArrayBuffer
                           │ Atomics.wait/notify
┌──────────────────────────┴──────────────────────────────┐
│ Physics Worker (dedicated Web Worker)                     │
│                                                          │
│  Tight loop:                                              │
│    1. Atomics.wait() for input signal from main thread    │
│    2. Read input from SAB                                 │
│    3. PhysicsWorld.step() (WASM)                          │
│    4. Write output vehicle state to SAB                   │
│    5. Atomics.store() output-ready flag                   │
│    6. Atomics.notify() main thread                        │
│                                                          │
│  Runs at 100Hz (one step per notify, accumulator on main) │
│  WASM module loaded once at worker init                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Asset Worker(s) (1-2 dedicated Web Workers)               │
│                                                          │
│  Message-passing (postMessage, NOT SharedArrayBuffer):    │
│    1. Receive: { type: 'parse-gbx', buffer: ArrayBuffer } │
│    2. Run GBX header + body parsing                       │
│    3. Run LZO decompression                               │
│    4. Parse chunk stream, extract block lists              │
│    5. Respond: { type: 'gbx-result', mapData: ... }       │
│                                                          │
│    1. Receive: { type: 'decode-texture', buffer, format }  │
│    2. Decode DDS/KTX2 to raw RGBA pixels                  │
│    3. Respond: { type: 'texture-result', pixels, w, h }   │
│                                                          │
│  These are fire-and-forget tasks, no shared state needed  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Audio Worklet (AudioWorkletProcessor)                     │
│                                                          │
│  Runs on audio rendering thread (128 samples @ 44.1kHz):  │
│    - Engine sound synthesis if needed                     │
│    - Low-latency audio generation                         │
│    - Reads RPM/throttle from SharedArrayBuffer             │
│                                                          │
│  For MVP: skip worklet, use standard AudioBufferSource    │
│  with playbackRate modulation (higher latency, simpler)   │
└─────────────────────────────────────────────────────────┘
```

### SharedArrayBuffer Layout for Physics-Main Thread Communication

The SAB is the critical shared memory between the main thread and physics worker. It must be allocated once at startup with `new SharedArrayBuffer(TOTAL_SIZE)`. Both threads access it through typed array views.

**Why SharedArrayBuffer instead of postMessage**: At 100Hz physics, postMessage would need to copy vehicle state (hundreds of bytes) every 10ms. The structured clone overhead (~0.1ms) plus GC pressure would consume ~10% of the frame budget. SAB with Atomics has near-zero overhead: the main thread writes input and reads output in-place.

**Requirement**: `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers must be set for SharedArrayBuffer to be available.

```
SharedArrayBuffer total size: 4096 bytes (generous, supports up to 4 vehicles)

Offset (bytes)  | Size  | Name                  | Type      | Direction
─────────────────────────────────────────────────────────────────────────
CONTROL REGION (64 bytes)
0x0000          | 4     | inputReady            | Int32     | main -> physics (Atomics.notify)
0x0004          | 4     | outputReady           | Int32     | physics -> main (Atomics.notify)
0x0008          | 4     | currentTick           | Uint32    | main -> physics
0x000C          | 4     | vehicleCount          | Uint32    | main -> physics
0x0010          | 4     | resetFlag             | Uint32    | main -> physics (1 = reset to CP)
0x0014          | 12    | resetPosition         | 3xFloat32 | main -> physics
0x0020          | 36    | resetRotation         | 9xFloat32 | main -> physics (Iso4 rotation)
0x0044          | 28    | [padding to 64]       | -         | -

INPUT REGION (per vehicle, 32 bytes each, max 4 vehicles = 128 bytes)
0x0040          | 4     | steer                 | Float32   | main -> physics
0x0044          | 4     | gas                   | Float32   | main -> physics
0x0048          | 4     | brake                 | Float32   | main -> physics
0x004C          | 4     | vertical              | Float32   | main -> physics
0x0050          | 4     | flags                 | Uint32    | main -> physics (bit0=braking, bit1=respawn)
0x0054          | 12    | [padding to 32]       | -         | -
(Vehicle 1 at 0x0060, Vehicle 2 at 0x0080, Vehicle 3 at 0x00A0)

OUTPUT REGION (per vehicle, 256 bytes each, max 4 vehicles = 1024 bytes)
0x0100          | 12    | position              | 3xFloat32 | physics -> main
0x010C          | 12    | prevPosition          | 3xFloat32 | physics -> main (for interpolation)
0x0118          | 36    | rotation              | 9xFloat32 | physics -> main (Iso4 rotation)
0x013C          | 36    | prevRotation          | 9xFloat32 | physics -> main
0x0160          | 12    | velocity              | 3xFloat32 | physics -> main
0x016C          | 4     | frontSpeed            | Float32   | physics -> main (m/s)
0x0170          | 4     | sideSpeed             | Float32   | physics -> main
0x0174          | 4     | rpm                   | Float32   | physics -> main (0-11000)
0x0178          | 4     | gear                  | Uint32    | physics -> main (0-7)
0x017C          | 4     | turboFlags            | Uint32    | physics -> main
0x0180          | 4     | turboTime             | Float32   | physics -> main (0-1 normalized)
0x0184          | 4     | isGroundContact       | Uint32    | physics -> main (bool)
0x0188          | 4     | groundDist            | Float32   | physics -> main
0x018C          | 48    | wheelStates           | 4x{damperLen f32, steerAngle f32, wheelRot f32} | physics -> main
0x01BC          | 16    | wheelContact          | 4xUint32  | physics -> main (surfaceId per wheel)
0x01CC          | 4     | discontinuityCount    | Uint32    | physics -> main
0x01D0          | 48    | [padding to 256]      | -         | -
(Vehicle 1 at 0x0200, Vehicle 2 at 0x0300, Vehicle 3 at 0x0400)

COLLISION EVENT REGION (512 bytes, circular buffer)
0x0500          | 4     | eventWriteIndex       | Uint32    | physics -> main (Atomics)
0x0504          | 4     | eventReadIndex        | Uint32    | main -> physics (Atomics)
0x0508          | 504   | events[63]            | 8 bytes each | physics -> main
                                                  Format: { type: u8, surfaceId: u8, speed: f16, padding: u32 }
                                                  Types: 0=checkpoint, 1=finish, 2=turbo_pad, 3=wall_hit, 4=respawn_trigger

TOTAL: 0x0700 = 1792 bytes (fits in 4096 allocation with room for expansion)
```

**Synchronization protocol**:
```
Main thread (per frame, possibly multiple ticks):
  1. Write input values to INPUT REGION
  2. Write currentTick to CONTROL REGION
  3. Atomics.store(sab_i32, INPUT_READY_OFFSET/4, 1)
  4. Atomics.notify(sab_i32, INPUT_READY_OFFSET/4, 1)
  5. Continue rendering using PREVIOUS frame's output (no blocking)
  6. On next frame: check Atomics.load(sab_i32, OUTPUT_READY_OFFSET/4)
     If 1: read output, Atomics.store(..., 0) to acknowledge

Physics worker (loop):
  1. Atomics.wait(sab_i32, INPUT_READY_OFFSET/4, 0)  // blocks until != 0
  2. Atomics.store(sab_i32, INPUT_READY_OFFSET/4, 0)  // acknowledge
  3. Read input + tick from SAB
  4. Run physics step
  5. Write output to OUTPUT REGION
  6. Atomics.store(sab_i32, OUTPUT_READY_OFFSET/4, 1)
  7. Atomics.notify(sab_i32, OUTPUT_READY_OFFSET/4, 1)
  8. goto 1
```

**Critical design decision**: The main thread NEVER blocks waiting for physics output. It always renders using the most recently available physics state, interpolated with the fractional tick alpha. This means rendering can run at 60fps even if physics runs at 100Hz -- the two loops are decoupled. If physics falls behind (> 10ms for a step), the main thread continues rendering the stale state and catches up next frame.

### Worker Initialization

```typescript
// main.ts
const sab = new SharedArrayBuffer(4096);

// Physics worker
const physicsWorker = new Worker(new URL('./workers/physics.ts', import.meta.url), { type: 'module' });
physicsWorker.postMessage({ type: 'init', sab, mapCollisionData: collisionMeshArrayBuffer });
// Worker loads WASM module, initializes rapier, builds collision world
// Subsequent communication is ONLY through SAB + Atomics

// Asset workers (2, for parallel GBX parsing + texture decoding)
const assetWorker1 = new Worker(new URL('./workers/asset.ts', import.meta.url), { type: 'module' });
const assetWorker2 = new Worker(new URL('./workers/asset.ts', import.meta.url), { type: 'module' });
// These use postMessage (Transferable ArrayBuffers for zero-copy)
```

---

## State Machine

### Browser State Machine

TM2020 has 60+ states in a coroutine-based state machine within `CGameCtnApp::UpdateGame` (216KB function) [doc 12 Section 1, VERIFIED]. The browser recreation maps these to a simplified state machine using TypeScript async generators (matching the fiber/coroutine pattern documented in doc 12 Section 4.3).

```
States (browser):

┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  [Boot] ──> [Loading] ──> [MainMenu] ──┬──> [MapLoading]   │
│               │                        │       │            │
│               │                        │       v            │
│               │                        │  [Countdown]       │
│               │                        │       │            │
│               │                        │       v            │
│               │                        │   [Racing]         │
│               │                        │       │            │
│               │                        │    ┌──┴──┐         │
│               │                        │    │     │         │
│               │                        │    v     v         │
│               │                        │ [Paused] [Finished]│
│               │                        │    │     │         │
│               │                        │    │     v         │
│               │                        │    │  [Results]    │
│               │                        │    │     │         │
│               │                        │    └──┬──┘         │
│               │                        │       │            │
│               │                        │       v            │
│               │                        ├── [Replay]         │
│               │                        │       │            │
│               │                        │<──────┘            │
│               │                        │                    │
│               │                        ├──> [Editor]        │
│               │                        │       │            │
│               │                        │<──────┘            │
│               │                        │                    │
│               │                        └──> [Settings]      │
│               │                               │             │
│               │                        <──────┘             │
└─────────────────────────────────────────────────────────────┘
```

### State Definitions

#### Boot
- **TM2020 equivalent**: States 0x000 (Game Init) through 0x3E7 (Init Complete) [doc 12 Section 1.3]
- **Trigger**: Application start
- **Initializes**:
  - WebGPU device + adapter negotiation
  - SharedArrayBuffer allocation
  - Physics worker spawn + WASM load
  - Asset worker(s) spawn
  - AudioContext creation (suspended, awaiting user gesture)
  - Input manager construction (keyboard + gamepad listeners)
  - Asset manifest fetch
- **Destroys**: Nothing (first state)
- **Transitions**: -> Loading (all subsystems initialized) | -> Error (WebGPU not supported)
- **Duration**: < 2s target

#### Loading
- **TM2020 equivalent**: States 0x402-0x4F9 (Startup Sequence, Login, Network Validation) [doc 12 Section 1.3]
- **Trigger**: Boot complete
- **Initializes**:
  - Core block mesh library (pre-fetch most common 50 blocks)
  - Authentication (if online mode): proxy to Nadeo API
  - Block definition registry (name -> mesh URL, material, surface ID)
  - Car model mesh load
- **Destroys**: Boot loading screen
- **Transitions**: -> MainMenu (essential assets loaded) | -> Error (network failure, asset fetch failure)
- **Duration**: < 5s warm cache, < 15s cold
- **Shows**: Progress bar with asset counts

#### MainMenu
- **TM2020 equivalent**: Phase 5 state (0xCDCC label, game phase = 2) [doc 12 Section 1.3, `FUN_140b54b90(param_1, 2)`]
- **Trigger**: Loading complete, or exit from any gameplay state
- **Initializes**:
  - Menu UI (Svelte components mounted to DOM overlay)
  - Background scene (if desired: slowly rotating map render)
  - Resume AudioContext on first user interaction
- **Destroys**: Any active race/editor/replay state, physics collision world (but keep worker alive)
- **Transitions**:
  - -> MapLoading (user selects "Play" with map) -- equivalent to TM2020 menu result 0x09 [doc 12]
  - -> Editor (user selects "Editor") -- equivalent to menu result 0x11 [doc 12]
  - -> Settings (user opens settings)
- **UI elements**: Play button, Map browser, Editor button, Settings, Quit

#### MapLoading
- **TM2020 equivalent**: States 0xBF6-0xC22 (Load Map for Gameplay, Map Load for Play, Wait for Play Ready) [doc 12 Section 1.3]
- **Trigger**: Map selected from menu or direct URL
- **Initializes**:
  - Execute full map loading pipeline (Section 2.1, steps 1-7)
  - Send collision mesh to physics worker
  - Build scene graph
  - Spawn player vehicle in physics world at start block position
  - Initialize ghost vehicle(s) if ghost data available
  - Set up race state (timer, checkpoint tracker)
- **Destroys**: Previous map data (if any), previous collision world in physics
- **Transitions**: -> Countdown (map fully loaded) | -> MainMenu (cancel/error)
- **Duration**: < 5s for standard map
- **Shows**: Loading screen with map thumbnail (from GBX header chunk 0x03043007)

#### Countdown
- **TM2020 equivalent**: Part of gameplay preparation (state 0xB43) [doc 12 Section 1.3]
- **Trigger**: Map loading complete
- **Initializes**:
  - Place vehicle at start position (facing correct direction)
  - Lock input (ignore gas/steer during countdown)
  - Start countdown animation (3, 2, 1, GO)
  - Start ghost playback (ghost begins from tick 0)
- **Destroys**: Loading screen
- **Transitions**: -> Racing (countdown reaches 0) | -> MainMenu (user presses Escape)
- **Duration**: 3 seconds (fixed)

#### Racing
- **TM2020 equivalent**: States 0xD2D-0xD45 (Gameplay Start, Gameplay Active) [doc 12 Section 1.3]
- **Trigger**: Countdown complete
- **Initializes**:
  - Unlock input
  - Start race timer (from tick 0)
  - Begin input recording for ghost
  - Enable HUD (speedometer, timer, checkpoint splits)
- **Destroys**: Countdown overlay
- **Transitions**:
  - -> Finished (vehicle crosses finish line -- detected by waypoint intersection in physics)
  - -> Paused (user presses Escape)
  - -> Racing (respawn: user presses respawn key, vehicle teleports to last checkpoint,
    discontinuityCount++ [doc 19 Section 1])
- **Per-tick actions**:
  - Sample input
  - Physics step
  - Check waypoint intersections (checkpoint/finish)
  - Update HUD
  - Record ghost sample

#### Paused
- **TM2020 equivalent**: Menu result 0x1F (Pause Menu) [doc 12 Section 1.3]
- **Trigger**: Escape key during Racing
- **Initializes**:
  - Pause overlay (resume, restart, quit to menu)
  - Pause physics (stop sending ticks to physics worker)
  - Pause race timer
  - Pause ghost playback
- **Destroys**: Nothing (race state preserved)
- **Transitions**:
  - -> Racing (resume)
  - -> Countdown (restart: reset vehicle, timer, ghost, input history)
  - -> MainMenu (quit)

#### Finished
- **TM2020 equivalent**: Part of gameplay state flow leading to podium/replay states [doc 12 Section 1.3]
- **Trigger**: Vehicle crosses finish line
- **Initializes**:
  - Stop race timer, record finish time
  - Stop input recording
  - Finalize ghost data
  - Calculate medal (if thresholds known)
  - Show results overlay
- **Destroys**: Nothing (keep race state for replay)
- **Transitions**:
  - -> Results (immediate, overlaid)
  - -> Replay (user clicks "Watch Replay")
  - -> Racing (user clicks "Retry" -> resets to Countdown)
  - -> MainMenu (user clicks "Menu")

#### Results
- **TM2020 equivalent**: Post-race state with score display
- **Trigger**: Race finished
- **Initializes**:
  - Results overlay: finish time, checkpoint splits, comparison to best/ghost
  - Ghost save prompt (save locally or upload)
  - Medal display
- **Destroys**: Racing HUD
- **Transitions**:
  - -> Replay (watch replay)
  - -> Countdown (retry)
  - -> MainMenu (quit)

#### Replay
- **TM2020 equivalent**: States 0xC74 (Replay Validation), 0xCEF-0xCF0 (Load Replay), 0xE14 (Replay Playback) [doc 12 Section 1.3]
- **Trigger**: User selects replay from results or menu
- **Initializes**:
  - Load ghost data (just-recorded or from file)
  - Create replay vehicle in physics
  - Switch camera to replay mode (can orbit, free-fly, follow)
  - Timeline scrubber UI
  - Playback controls (play, pause, speed up, slow down, seek)
- **Destroys**: Racing state input recording
- **Transitions**:
  - -> MainMenu (exit)
  - -> Countdown (retry the map)

#### Editor
- **TM2020 equivalent**: State 0xDE5 (Editor Session) calling FUN_140b827b0 [doc 12 Section 1.3]
- **Trigger**: User selects Editor from menu
- **Initializes**:
  - Editor state machine (block palette, grid cursor, orbital camera)
  - Block library browser (HTML panel)
  - Editor toolbar (place, erase, select, rotate)
  - Empty map or load existing
  - Undo/redo history (command pattern)
- **Destroys**: Previous map/race state
- **Transitions**:
  - -> MapLoading (test play the map being edited)
  - -> MainMenu (exit editor)

#### Settings
- **TM2020 equivalent**: Menu result 0x27 (Settings) [doc 12]
- **Trigger**: Settings button from menu
- **Initializes**: Settings panels (graphics quality, keybinds, audio volume, account)
- **Destroys**: Nothing
- **Transitions**: -> MainMenu (back)

### State Machine Implementation

```typescript
type GameState =
  | 'boot' | 'loading' | 'mainMenu' | 'mapLoading' | 'countdown'
  | 'racing' | 'paused' | 'finished' | 'results' | 'replay'
  | 'editor' | 'settings' | 'error';

interface StateTransition {
  from: GameState;
  to: GameState;
  condition: string;  // human-readable trigger
}

// Implemented as an async generator matching TM2020's fiber pattern (doc 12 Section 4):
async function* gameStateMachine(ctx: GameContext): AsyncGenerator<GameState> {
  yield 'boot';
  await initializeSubsystems(ctx);

  yield 'loading';
  await loadCoreAssets(ctx);

  while (true) {
    yield 'mainMenu';
    const action = await waitForMenuAction(ctx);

    switch (action.type) {
      case 'play':
        yield 'mapLoading';
        await loadMap(ctx, action.mapUrl);

        let playing = true;
        while (playing) {
          yield 'countdown';
          await runCountdown(ctx);

          yield 'racing';
          const raceResult = await runRace(ctx);

          if (raceResult === 'finished') {
            yield 'finished';
            yield 'results';
            const resultAction = await waitForResultAction(ctx);
            if (resultAction === 'retry') continue;
            if (resultAction === 'replay') {
              yield 'replay';
              await runReplay(ctx);
            }
            playing = false;
          } else if (raceResult === 'quit') {
            playing = false;
          }
        }
        break;

      case 'editor':
        yield 'editor';
        await runEditor(ctx);
        break;

      case 'settings':
        yield 'settings';
        await runSettings(ctx);
        break;
    }
  }
}
```

---

## Build System

### Monorepo Structure

**Tool**: Turborepo (chosen over Nx for simplicity and speed)

**Reason**: Turborepo provides task-level caching and parallel execution with minimal configuration. The project has ~14 packages with clear dependency boundaries. Nx would be overkill for this size. pnpm workspaces provide the package linking.

```
opentm/
  package.json              # Root: pnpm workspace + turborepo
  pnpm-workspace.yaml       # Workspace definition
  turbo.json                # Pipeline configuration
  tsconfig.base.json        # Shared TS config
  .github/
    workflows/
      ci.yml                # GitHub Actions: lint, test, build, deploy
      physics-validation.yml # Nightly: run physics against TMInterface data

  packages/
    core/                   # @opentm/core
      src/
      package.json
      tsconfig.json
      vitest.config.ts

    gbx-parser/             # @opentm/gbx-parser
      src/
      tests/
        fixtures/           # Real .Gbx files for integration tests
      package.json

    physics/                # @opentm/physics (Rust + TS)
      rust/
        src/
          lib.rs
          vehicle.rs
          forces/
            car_sport.rs    # Decompiled CarSport model (doc 22)
            car_base.rs     # Base 4-wheel model (doc 22)
          collision.rs
          integration.rs
        Cargo.toml
        wasm-pack.toml
      ts/
        src/
          index.ts          # TS bindings for WASM
          worker.ts         # Physics Web Worker entry point
      package.json

    renderer/               # @opentm/renderer
      src/
        shaders/            # .wgsl files
      package.json

    audio/                  # @opentm/audio
    input/                  # @opentm/input
    camera/                 # @opentm/camera
    network/                # @opentm/network
    scripting/              # @opentm/scripting (placeholder)
    ui/                     # @opentm/ui (Svelte)
    editor/                 # @opentm/editor
    ghost/                  # @opentm/ghost
    map/                    # @opentm/map
    assets/                 # @opentm/assets

  apps/
    web/                    # Main web application
      src/
        main.ts             # Entry point: state machine, game loop
        workers/
          physics.ts        # Physics worker entry
          asset.ts          # Asset worker entry
      index.html
      vite.config.ts
      package.json

    tools/                  # Offline tooling (Node.js scripts)
      extract-blocks/       # Extract block meshes from .pak files
      convert-textures/     # DDS -> WebP/PNG conversion
      generate-manifest/    # Build asset manifest JSON
      validate-physics/     # Run physics against TMInterface replay data
      package.json
```

### Rust WASM Compilation

```toml
# packages/physics/rust/Cargo.toml
[package]
name = "opentm-physics"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
wasm-bindgen = "0.2"
rapier3d = { version = "0.22", features = ["wasm-bindgen"] }
# No serde -- manual byte serialization for SAB interop

[profile.release]
opt-level = 3
lto = true
codegen-units = 1     # Max optimization
strip = true          # Minimize WASM size
```

**Build command** (in turbo pipeline):
```bash
cd packages/physics/rust && wasm-pack build --target web --release --out-dir ../ts/src/wasm
```

**WASM size budget**: < 500KB gzipped (rapier3d contributes ~300KB, custom physics ~100KB, overhead ~100KB). Total page load budget: < 2MB gzipped including all JS + WASM.

**Determinism**: Rust on WASM uses IEEE 754 single-precision for `f32` operations. The WASM spec mandates deterministic floating-point for non-NaN values. We use `f32` exclusively (never `f64`) in the physics module and avoid non-deterministic operations (`f32::sqrt` is deterministic in WASM, but `f32::sin`/`cos` may vary -- use a lookup table or Taylor series for trigonometric functions in the physics path).

### TypeScript Bundling

**Tool**: Vite 6+ with the following plugins:
- `vite-plugin-wasm`: load .wasm files as ES modules
- `@sveltejs/vite-plugin-svelte`: Svelte component compilation
- `vite-plugin-top-level-await`: for WASM async initialization

```typescript
// apps/web/vite.config.ts
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';

export default defineConfig({
  plugins: [svelte(), wasm(), topLevelAwait()],
  build: {
    target: 'esnext',         // WebGPU requires modern browsers
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: {
          physics: ['@opentm/physics'],
          renderer: ['@opentm/renderer'],
          gbx: ['@opentm/gbx-parser'],
        },
      },
    },
  },
  server: {
    headers: {
      // Required for SharedArrayBuffer
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
  worker: {
    format: 'es',
    plugins: () => [wasm(), topLevelAwait()],
  },
});
```

### Turborepo Pipeline

```jsonc
// turbo.json
{
  "$schema": "https://turbo.build/schema.json",
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", "ts/src/wasm/**"]
    },
    "build:wasm": {
      "cache": true,
      "outputs": ["ts/src/wasm/**"],
      "inputs": ["rust/src/**", "rust/Cargo.toml"]
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": []
    },
    "test:physics-validation": {
      "dependsOn": ["build"],
      "outputs": ["test-results/**"],
      "cache": false  // always run fresh against latest TMInterface data
    },
    "lint": {
      "outputs": []
    },
    "typecheck": {
      "dependsOn": ["^build"],
      "outputs": []
    }
  }
}
```

### Testing Strategy Per Module

| Module | Test Type | Tool | What is Tested | Data Source |
|--------|-----------|------|---------------|-------------|
| core | Unit | Vitest | Math operations (Vec3 dot/cross, Iso4 multiply, Quat slerp) | Hand-computed values |
| gbx-parser | Unit + Integration | Vitest | Header parsing, LookbackString, chunk dispatch. Integration: parse real .Gbx files and verify extracted data | 10+ real .Map.Gbx files as fixtures (doc 26 validated 5 files byte-exact) |
| physics | Unit + Validation | Vitest (TS) + cargo test (Rust) | Unit: force model outputs for known inputs. Validation: replay TMInterface recordings and compare positions at each tick | TMInterface replay data: 20+ replays with input+position pairs |
| renderer | Visual regression | Playwright screenshot comparison | Render known scenes, compare against reference screenshots. Catch shader regressions. | Reference screenshots from known camera positions |
| audio | Manual | - | Audio is subjective; manual testing only | - |
| input | Unit | Vitest | Mock keyboard/gamepad events, verify InputState output | Synthetic events |
| camera | Unit | Vitest | Camera matrix computation for known inputs. Chase camera tracking. | Known vehicle positions -> expected camera matrices |
| network | Integration | Vitest + MSW | Mock Nadeo API responses, verify auth flow, token refresh, error handling | Mock HTTP responses matching documented API format |
| map | Integration | Vitest | Load real .Map.Gbx, verify block counts, positions, waypoint detection | Real map files with known block layouts |
| ghost | Unit + Roundtrip | Vitest | Record inputs, serialize, compress, decompress, deserialize, compare to original | Generated input sequences |
| assets | Integration | Vitest | Asset manifest loading, cache hit/miss behavior | Mock manifest + mock HTTP responses |

**CI pipeline** (GitHub Actions):
1. `pnpm install` (frozen lockfile)
2. `turbo run lint typecheck` (parallel)
3. `turbo run build` (respects dependency order)
4. `turbo run test` (all unit + integration tests)
5. **Nightly** (separate workflow): `turbo run test:physics-validation` (30-minute run comparing against TMInterface data)

---

## Performance Budget

### Frame Budget Allocation (60 FPS Target)

Total budget: **16.67ms** per frame.

```
┌──────────────────────────────────────────────────────────────┐
│ Budget Allocation (16.67ms total for 60 FPS)                  │
│                                                              │
│ ┌─────────┐ ┌──────────────────────┐ ┌────────┐ ┌─────────┐ │
│ │ Input   │ │ Rendering (GPU)       │ │ Audio  │ │ UI +    │ │
│ │ + Logic │ │                       │ │        │ │ Other   │ │
│ │         │ │                       │ │        │ │         │ │
│ │ 1.5ms   │ │ 8ms                   │ │ 0.5ms  │ │ 2.67ms  │ │
│ └─────────┘ └──────────────────────┘ └────────┘ └─────────┘ │
│                                                              │
│ Physics runs on SEPARATE THREAD: up to 10ms per tick,         │
│ does NOT consume main thread budget.                          │
│                                                              │
│ Physics Worker Budget: 4ms target, 10ms hard max per tick     │
└──────────────────────────────────────────────────────────────┘
```

**Detailed breakdown (main thread)**:

| Phase | Budget | Description |
|-------|--------|-------------|
| Input sampling | 0.1ms | Poll gamepad, read keyboard state, write to SAB |
| Read physics output | 0.1ms | Read vehicle state from SAB, interpolate |
| Camera update | 0.2ms | Spring-damper computation, matrix generation |
| Frustum culling | 0.5ms | BVH traversal, AABB-frustum test for ~5000 nodes |
| Scene sorting | 0.3ms | Sort opaques front-to-back, transparents back-to-front |
| Command encoding | 0.3ms | Build WebGPU command buffers |
| **GPU: Shadow pass** | **2.0ms** | 4 cascades x 500 draw calls each (instanced) |
| **GPU: G-buffer fill** | **3.0ms** | ~2000 draw calls, 4 MRT output |
| **GPU: Deferred lighting** | **1.5ms** | Full-screen pass, PBR computation |
| **GPU: Forward transparent** | **0.5ms** | Ghost car, glass, particles |
| **GPU: Post-process** | **1.0ms** | Bloom (0.5ms) + tone map (0.2ms) + FXAA (0.3ms) |
| UI update | 0.5ms | Svelte reactive updates, DOM reconciliation |
| Audio parameter update | 0.2ms | Set RPM, position, play/stop sounds |
| WebGPU submit + present | 0.5ms | Submit command buffer, browser compositing |
| **Headroom** | **5.97ms** | Buffer for GC pauses, OS interrupts, variance |

**Physics worker budget** (separate thread, per tick):

| Phase | Budget | Description |
|-------|--------|-------------|
| Input read from SAB | 0.01ms | Atomic read |
| Substep loop (1-10 typical) | 2.5ms | Force computation + integration per substep |
| Collision broadphase | 0.5ms | rapier BVH query |
| Collision narrowphase | 0.5ms | GJK/EPA for contacts |
| Collision response | 0.3ms | Iterative friction solver |
| Output write to SAB | 0.01ms | Atomic write |
| **Total typical** | **~3.8ms** | Well within 10ms tick budget |
| **Worst case (max substeps ~50)** | **~8ms** | High speed, many contacts |

### What Happens When Budget is Exceeded

**Scenario 1: Main thread rendering exceeds 16.67ms** (dropped to < 60 FPS)

Adaptive quality system:
```typescript
class AdaptiveQuality {
  private frameTimeHistory: number[] = [];  // rolling window of 30 frames
  private currentLevel: QualityLevel = 'high';

  onFrameEnd(frameTimeMs: number): void {
    this.frameTimeHistory.push(frameTimeMs);
    if (this.frameTimeHistory.length > 30) this.frameTimeHistory.shift();

    const avgFrameTime = average(this.frameTimeHistory);

    // Downgrade if consistently over budget
    if (avgFrameTime > 18.0 && this.currentLevel === 'high') {
      this.currentLevel = 'medium';
      this.applySetting('medium');
    } else if (avgFrameTime > 20.0 && this.currentLevel === 'medium') {
      this.currentLevel = 'low';
      this.applySetting('low');
    }
    // Upgrade if consistently under budget (with headroom)
    else if (avgFrameTime < 12.0 && this.currentLevel !== 'high') {
      this.currentLevel = this.currentLevel === 'low' ? 'medium' : 'high';
      this.applySetting(this.currentLevel);
    }
  }
}
```

| Setting | High | Medium | Low |
|---------|------|--------|-----|
| Shadow cascades | 4 | 2 | 1 |
| Shadow resolution | 2048 | 1024 | 512 |
| SSAO | Enabled | Half-res | Disabled |
| Bloom | Enabled | Enabled | Disabled |
| AA | TAA | FXAA | None |
| Draw distance | 1000m | 500m | 300m |
| Render resolution | 100% | 85% | 70% |

**Scenario 2: Physics worker exceeds 10ms tick budget**

This is critical because physics must maintain 100Hz for determinism. If a tick takes > 10ms:

1. The physics worker simply takes longer. The main thread does NOT wait -- it renders with the last known state.
2. On the next frame, the main thread sends 2 (or more) ticks to catch up. The physics worker processes them sequentially.
3. If physics falls behind by > 3 ticks (30ms), log a warning and cap the catch-up to 3 ticks per frame. This prevents death spirals where trying to catch up causes more missed deadlines.
4. For the player, this manifests as brief physics jitter -- the car appears to teleport slightly. Acceptable at < 1% of frames.

```typescript
// Main thread tick accumulation with catch-up cap
const MAX_TICKS_PER_FRAME = 3;
let tickAccumulator = 0;

function onFrame(deltaMs: number) {
  tickAccumulator += deltaMs;
  let ticksThisFrame = 0;

  while (tickAccumulator >= TICK_DT_MS && ticksThisFrame < MAX_TICKS_PER_FRAME) {
    sendTickToPhysicsWorker(currentTick);
    currentTick++;
    tickAccumulator -= TICK_DT_MS;
    ticksThisFrame++;
  }

  // If we hit the cap, discard excess accumulated time (prevents spiral)
  if (ticksThisFrame === MAX_TICKS_PER_FRAME && tickAccumulator > TICK_DT_MS) {
    console.warn(`Physics falling behind: ${tickAccumulator.toFixed(1)}ms excess discarded`);
    tickAccumulator = 0; // Reset to prevent growing debt
  }
}
```

**Scenario 3: Complex maps with 10,000+ blocks**

- Frustum culling with BVH should handle 50,000 nodes in < 1ms
- Draw call batching: group blocks by material (same mesh + texture = one instanced draw call). Target < 200 unique draw calls after batching.
- LOD: blocks beyond 500m use simplified meshes (50% triangle count). Beyond 1000m, use impostor billboards or skip.

### Memory Budget

| Resource | Budget | Notes |
|----------|--------|-------|
| WASM heap (physics) | 32MB | rapier collision world + vehicle states |
| GPU VRAM (textures) | 256MB | Block textures, shadow maps, G-buffer |
| GPU VRAM (geometry) | 64MB | Vertex + index buffers for all loaded blocks |
| JS heap | 128MB | GBX parse results, scene graph, UI state, ghost data |
| Audio buffers | 16MB | Decoded engine samples, SFX, music |
| **Total** | **~500MB** | Fits comfortably on mid-range hardware (4GB+ GPU, 8GB+ RAM) |

---

## Critical Unknowns That Block Architecture

### Block Mesh Extraction Pipeline

- **What we assume**: Block meshes can be extracted from .pak files using NadeoImporter or community tools and served as pre-converted glTF assets from a CDN.
- **Evidence**: NadeoImporter is an official Nadeo tool that exports meshes. gbx-net has partial .pak parsing. Community has extracted individual blocks manually. NadeoPak files confirmed to use "NadeoPak" magic header, not GBX [doc 26 Section 10].
- **What breaks if wrong**: If pack files are encrypted per-account with no offline extraction path, we cannot get block meshes AT ALL. The entire renderer has nothing to display.
- **Likelihood of being wrong**: LOW. The community HAS extracted blocks; the question is whether it can be automated for ALL ~500 block types.
- **Validation**: Before any code: write a Node.js script that extracts 10 Stadium road blocks to glTF using gbx-net. If this works, the pipeline is viable. Estimated effort: 2-3 days.

### GBX Body Compression is LZO, Not zlib

- **What we assume**: GBX body compression uses LZO1X (confirmed by doc 26), and we need an LZO decompressor in the browser.
- **Evidence**: Doc 26 (real file analysis) byte-matched 5 GBX files and confirmed LZO body compression. Doc 15 found zlib strings in the binary, but doc 26 proved LZO is used for GBX bodies. zlib is used elsewhere (lightmaps, possibly ghosts).
- **What breaks if wrong**: If some files use zlib and others use LZO (or if there is a third compression), the parser will fail on certain files.
- **Likelihood of being wrong**: LOW for body compression being LZO. Medium for there being mixed compression across different file types.
- **Validation**: Parse 100 diverse .Gbx files (maps, items, ghosts) and verify each decompresses successfully with LZO. Test zlib fallback for any that fail. Effort: 1 day.

### Physics Force Model Accuracy

- **What we assume**: The decompiled CarSport force model (doc 22, case 5, 350+ LOC) can be ported to Rust and will produce physics that "feel right" after parameter tuning against TMInterface data.
- **Evidence**: Three force models are decompiled with actual code: cases 0/1/2 (base 4-wheel), case 3 (2-wheel bicycle), case 5 (CarSport with 9 sub-functions) [doc 22]. Pacejka-like tire model documented. Drift state machine documented (3 states). However, the per-wheel sub-function FUN_1408570e0 is NOT decompiled, nor are the airborne control model (FUN_14085c1b0) or boost model (FUN_140857b20).
- **What breaks if wrong**: If the decompiled code has critical errors (decompiler artifacts, wrong register assignments, missing functions), the physics will feel fundamentally wrong. Iterative tuning can only compensate for parameter errors, not structural errors.
- **Likelihood of being wrong**: MEDIUM. Ghidra decompilation of complex math code frequently has errors in operator precedence, sign handling, and type casting. The Pacejka-like formula `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef` is plausible but could be subtly wrong.
- **Validation**: CRITICAL FIRST STEP. Before porting to Rust:
  1. Record 20 TMInterface replays (simple straight, turns, jumps, turbo, drift) with input + position at every tick.
  2. Implement the decompiled CarSport model in TypeScript (faster iteration).
  3. Feed the same inputs and compare positions. If position divergence exceeds 1m after 100 ticks, there is a structural error that needs re-decompilation.
  4. Effort: 2 weeks (this is the single most important validation).

### WebGPU Availability and Capability

- **What we assume**: WebGPU is available in all target browsers (Chrome, Firefox, Safari) with support for: 4+ MRT (color attachments), compute shaders, depth textures as shader input, 2D array textures (for shadow cascades).
- **Evidence**: WebGPU is production-ready in Chrome (since 113), Firefox (since 132), and Safari (since 18). The spec mandates up to 8 color attachments (we need 4). Compute shaders, depth texture binding, and array textures are all in the core spec.
- **What breaks if wrong**: If a target browser has a bug or limitation in MRT or compute shaders, the deferred pipeline fails. Fallback to forward rendering loses the ability to handle many lights efficiently.
- **Likelihood of being wrong**: LOW for the features listed. WebGPU has been stable for years by 2026.
- **Validation**: Run the WebGPU conformance tests (webgpu:*) in Chrome, Firefox, and Safari. Create a minimal test that renders to 4 MRT + depth and reads back results. Effort: 1 day.

### SharedArrayBuffer Availability

- **What we assume**: SharedArrayBuffer is available with correct COOP/COEP headers, enabling zero-copy physics-to-render communication.
- **Evidence**: SAB has been available since Chrome 68, Firefox 79, Safari 15 -- with the COOP/COEP header requirement since the Spectre mitigations. This is a mature API.
- **What breaks if wrong**: If SAB is unavailable (e.g., iframe embedding without proper headers, or mobile browser limitations), the physics-render pipeline falls back to postMessage, consuming ~0.1-0.2ms per tick in serialization overhead.
- **Likelihood of being wrong**: LOW if we control the hosting environment. HIGH if embedded in third-party iframes.
- **Validation**: Set COOP/COEP headers in Vite dev server config (already specified in Section 5.3). Test SAB allocation in all target browsers. Effort: 1 hour.

### Deterministic Physics Across Browsers

- **What we assume**: Rust compiled to WASM produces bit-exact floating-point results across Chrome, Firefox, and Safari, enabling cross-browser ghost validation.
- **Evidence**: The WASM spec (IEEE 754-2019 compliance) guarantees deterministic results for basic arithmetic (+, -, *, /) and `sqrt`. However, `sin`, `cos`, `tan`, `exp`, `log` are NOT required to be deterministic across implementations. TM2020 likely achieves determinism by using only basic arithmetic in the physics hot path (Forward Euler with no trig in the integration loop).
- **What breaks if wrong**: If any trig or transcendental function produces different results across browsers, ghost replays will diverge. A ghost recorded in Chrome will not validate in Firefox.
- **Likelihood of being wrong**: MEDIUM. The force model likely uses `atan2` for slip angle computation and `sin`/`cos` for rotation updates. If these differ by even 1 ULP, the error will compound over thousands of ticks.
- **Validation**: Create a WASM test module that runs 10,000 iterations of the physics step with known inputs. Compare output across Chrome, Firefox, Safari byte-by-byte. If any difference: replace non-deterministic operations with lookup tables or Taylor series polynomial approximations compiled into the WASM. Effort: 3 days.

### Turbo Ramp Direction

- **What we assume**: Turbo boost force ramps linearly from 0 to max over its duration (i.e., ramp UP), as decompiled in doc 10 Section 4.3: `force = (elapsed/duration) * strength * modelScale`.
- **Evidence**: Decompiled code clearly shows `elapsed/duration` which starts at 0 and increases to 1. However, doc 18 (validation review) Issue 6 flagged this as counterintuitive and potentially a decompilation error, because TMNF turbo decays (ramp DOWN) per doc 14.
- **What breaks if wrong**: If turbo actually decays (ramp DOWN), the acceleration curve at turbo pads will feel completely wrong -- players will get a burst at the start instead of at the end.
- **Likelihood of being wrong**: MEDIUM. Ramp-UP makes sense physically (the surface continues to push the car while on it) but contradicts TMNF community documentation.
- **Validation**: Use TMInterface to capture speed data while driving over a turbo pad. Plot speed vs time. The curve shape will unambiguously show ramp-up vs ramp-down. Effort: 2 hours.

### Surface Friction Coefficients

- **What we assume**: Each of the 19 surface types has distinct friction coefficients that affect vehicle handling. We approximate these values (Section 19.2 of doc 20) because the actual values are not decompiled.
- **Evidence**: 208 materials are catalogued with surface IDs [doc 19 Section 10]. The surface ID determines physics behavior, confirmed by distinct handling on ice vs asphalt in gameplay. The decompiled force models reference surface ID per wheel contact [doc 22].
- **What breaks if wrong**: If friction values are significantly off, driving on grass/ice/dirt will feel wrong. Players will notice immediately because surface feel is a core TM mechanic.
- **Likelihood of being wrong**: HIGH for exact values (we have no decompiled coefficients). Low for relative ordering (ice < grass < dirt < asphalt is obvious from gameplay).
- **Validation**: Use Openplanet to measure deceleration rate on each surface type (drive at known speed, release throttle, measure time to stop). Derive friction coefficient from deceleration. Effort: 4 hours for all 19 surface types.

### Tick Rate Confirmation

- **What we assume**: Physics tick rate is 100Hz (10ms per tick).
- **Evidence**: 100Hz is community-established across TMNF and TM2020. TMInterface operates at this rate. However, doc 18 (validation review) Issue 25 notes this was never confirmed from a decompiled constant.
- **What breaks if wrong**: If the tick rate is 200Hz or 50Hz, all physics tuning will be wrong by a factor of 2-4x. Ghost replays will not validate.
- **Likelihood of being wrong**: VERY LOW. The entire TM community, TMInterface, and all replay tools assume 100Hz. If it were different, the community would have noticed.
- **Validation**: Use TMInterface to record a replay at maximum resolution. Count the number of state samples per second of game time. Effort: 30 minutes.

### Ghost Binary Format for Official Ghosts

- **What we assume**: We use our own ghost format (JSON + LZ4) for the MVP. Loading official TM2020 ghosts is deferred.
- **Evidence**: The ghost binary format uses int16/int8 encoding for position/rotation/speed [doc 29 Section 6.2] but the full format is not documented. gbx-net has partial ghost parsing.
- **What breaks if wrong**: If users expect to load their existing TM2020 ghosts, they cannot. This limits the competitive value of the tool.
- **Likelihood of being wrong**: N/A -- this is a scope decision, not an assumption. We explicitly defer official ghost loading.
- **Validation**: When ready to implement: use gbx-net's ghost parser as reference. Test with 50+ downloaded ghosts from TMX. Effort: 2-3 weeks.

### Map Block Naming Convention Stability

- **What we assume**: Block names in .Map.Gbx files (e.g., "StadiumRoadMainStraight") are stable across game versions and can be used as lookup keys into our pre-extracted mesh library.
- **Evidence**: gbx-net and gbx-ts use block names for identification. The community map editor (tm-editor-route) relies on block names. Block names appear in GBX body chunks as LookbackStrings.
- **What breaks if wrong**: If Nadeo changes block names in an update, maps using old names will fail to load. Our mesh library keys become invalid.
- **Likelihood of being wrong**: LOW. Block names have been stable across 6+ years of TM2020 updates. New blocks are added, old blocks are not renamed.
- **Validation**: Parse 100 maps from different TM2020 versions (2020-2026). Verify block names are consistent. Effort: 2 hours.

---

## Related Pages

- [Executive Summary](00-executive-summary.md) -- Project overview and risk register
- [Physics Engine](02-physics-engine.md) -- Detailed physics design referenced by the threading model
- [Renderer Design](03-renderer-design.md) -- WebGPU pipeline feeding from this architecture
- [Asset Pipeline](04-asset-pipeline.md) -- GBX parser and asset loading details
- [MVP Tasks](08-mvp-tasks.md) -- Task breakdown implementing this architecture

<details><summary>Document metadata</summary>

- **Version**: 1.0
- **Date**: 2026-03-27
- **Status**: Design (pre-implementation)
- **Scope**: Complete technical architecture for a browser-based Trackmania 2020 recreation using WASM
- **Source Evidence**: All references cite RE documents 00-20 plus community tools analysis

</details>

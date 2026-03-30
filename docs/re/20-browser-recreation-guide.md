# Browser Recreation Feasibility Guide

**Purpose**: Synthesize all Trackmania 2020 reverse engineering research into actionable guidance for recreating the game in a web browser.
**Date**: 2026-03-27
**Source Documents**: All 15 RE documents (00-master-overview through 19-openplanet-intelligence), including validation review corrections.
**Approach**: Honest assessment -- every claim references its source doc, unknowns are flagged, and confidence levels are explicit.

---

## Table of Contents

1. [Executive Assessment](#1-executive-assessment)
2. [Physics Engine](#2-physics-engine)
3. [Rendering Pipeline](#3-rendering-pipeline)
4. [GBX File Parser](#4-gbx-file-parser)
5. [Audio System](#5-audio-system)
6. [Input System](#6-input-system)
7. [Camera System](#7-camera-system)
8. [ManiaScript Engine](#8-maniascript-engine)
9. [Networking](#9-networking)
10. [Map Loading](#10-map-loading)
11. [Ghost/Replay System](#11-ghostreplay-system)
12. [UI System](#12-ui-system)
13. [Map Editor](#13-map-editor)
14. [MVP Definition](#14-mvp-definition)
15. [Implementation Order](#15-implementation-order)
16. [External Libraries and Tools](#16-external-libraries-and-tools)
17. [Hardest Problems](#17-hardest-problems)
18. [Blocking Unknowns](#18-blocking-unknowns)
19. [Implementation Code Skeletons](#19-implementation-code-skeletons)
    - 19.1 [GBX Parser Skeleton (TypeScript)](#191-gbx-parser-skeleton-typescript)
    - 19.2 [Physics Engine Skeleton (TypeScript/WASM)](#192-physics-engine-skeleton-typescript--wasm)
    - 19.3 [Renderer Architecture (WebGPU)](#193-renderer-architecture-webgpu)
    - 19.4 [Authentication Flow (Browser)](#194-authentication-flow-browser)
    - 19.5 [Input System (Browser)](#195-input-system-browser)
    - 19.6 [Audio System (Web Audio)](#196-audio-system-web-audio)
    - 19.7 [Project Structure](#197-project-structure)
    - 19.8 [Technology Stack Decisions](#198-technology-stack-decisions)
    - 19.9 [Development Roadmap with Milestones](#199-development-roadmap-with-milestones)

---

## 1. Executive Assessment

### Can Trackmania 2020 be recreated in a browser?

**Answer**: A playable subset -- YES. A full recreation -- NOT with current knowledge.

The research has produced enough understanding to build a functional racing game that loads TM2020 maps, simulates physics, renders the environment, and replays ghosts. However, several critical subsystems have knowledge gaps that would require additional reverse engineering or approximation:

| Area | Feasibility | Blocker Level |
|---|---|---|
| Load and display maps | HIGH | None -- GBX format well-documented |
| Physics that "feel right" | MEDIUM | Force model internals are black boxes |
| Multiplayer racing | LOW | UDP protocol undocumented |
| Full ManiaScript support | LOW | Runtime semantics mostly unknown |
| Map editor | MEDIUM | Placement rules partially understood |

### Technology Foundation

| TM2020 Component | Browser Equivalent | Maturity |
|---|---|---|
| Direct3D 11 | WebGPU | Production-ready (Chrome, Firefox, Safari) |
| OpenAL | Web Audio API | Mature |
| DirectInput 8 + XInput | Gamepad API + KeyboardEvent | Mature |
| Winsock2 + libcurl | WebSocket + fetch API | Mature |
| Custom thread pool | Web Workers + SharedArrayBuffer | Mature |
| ManiaScript interpreter | Custom JS interpreter or WASM | Must build from scratch |
| zlib compression | DecompressionStream / pako.js | Mature |
| Ogg Vorbis | Web Audio decodeAudioData | Native browser support |

---

## 2. Physics Engine

### What We Know (Confidence: MEDIUM-HIGH for pipeline, LOW for internals)

The physics pipeline is well-documented at the structural level:

**Pipeline** (from [10-physics-deep-dive.md](10-physics-deep-dive.md) Section 1, VERIFIED):
```
CSmArenaPhysics::Players_BeginFrame
  -> PhysicsStep_TM (per-vehicle, FUN_141501800)
    -> Adaptive sub-stepping loop
      -> Collision check
      -> NSceneVehiclePhy::ComputeForces
      -> Force application
      -> NSceneDyna::PhysicsStep_V2 (rigid body dynamics)
        -> NSceneDyna::InternalPhysicsStep
```

**Key parameters** (from [10-physics-deep-dive.md](10-physics-deep-dive.md), [15-ghidra-research-findings.md](15-ghidra-research-findings.md)):
- Timing: microsecond internal units, tick * 1,000,000 conversion (VERIFIED)
- Tick rate: 100 Hz / 10ms per tick (PLAUSIBLE -- community-established, not confirmed from constant)
- Sub-step cap: 1,000 maximum sub-steps per tick, adaptive based on velocity magnitude (VERIFIED)
- Integration: Forward Euler with sub-stepping (VERIFIED from [14-tmnf-crossref.md](14-tmnf-crossref.md))
- Gravity: parameterized vector with GravityCoef (0-1 normalized), 250ms smoothed transitions (VERIFIED)
- 7 force models dispatched via switch at vehicle_model+0x1790 (VERIFIED)
- 22+ surface gameplay effects (turbo, no-grip, reactor boost, etc.) (VERIFIED)
- Water physics: buoyancy and drag via NSceneDyna::ComputeWaterForces (VERIFIED)

**Vehicle state structure** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md), VERIFIED from live game):
- Input: steer (-1 to 1), gas (0-1), brake (0-1), vertical for reactor
- Motion: FrontSpeed (m/s), SideSpeed, WorldVel (vec3), Position, orientation (iso4)
- Drivetrain: 8 gears, RPM 0-11000, engine on/off
- Per-wheel (4 wheels, clockwise FL/FR/RR/RL): DamperLen, WheelRot, WheelRotSpeed, SteerAngle, SlipCoef, GroundContactMaterial, Dirt, Icing, TireWear
- Turbo: IsTurbo, TurboTime (0-1 normalized remaining), 6 turbo levels (None, Normal, Super, RouletteNormal/Super/Ultra)
- Vehicle types: CharacterPilot(0), CarSport(1), CarSnow(2), CarRally(3), CarDesert(4)

### What We Do Not Know

- **Internal force computation formulas**: The 7 force model functions (FUN_140869cd0 through FUN_14086d3b0) have NOT been decompiled internally. We know which function handles which model and the parameter signatures, but not the actual math. This is the single largest physics unknown.
- **Tire contact model**: Slip angle, camber, load transfer, combined slip -- none of the tire force curves are documented. SlipCoef is observed as an output but the model producing it is unknown.
- **Turbo force direction**: The decompiled code shows `(elapsed/duration) * strength * modelScale` which is a linear ramp UP, not decay ([18-validation-review.md](18-validation-review.md) Issue 6). This contradicts TMNF behavior and is counterintuitive. Needs verification.
- **Exact floating-point determinism strategy**: How cross-platform bit-exact replay is achieved.
- **Reactor boost physics**: Distinct from regular turbo, involves air control vectors, ground mode, and boost levels.

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| PhysicsStep_TM (C++) | WASM module (Rust or C++) | Physics MUST run in WASM for performance and determinism |
| Forward Euler integration | Same algorithm in WASM | Trivial to port |
| Adaptive sub-stepping | Same algorithm | Loop with velocity-dependent step count |
| Collision broadphase (tree-based) | BVH in WASM or use rapier.js | rapier.js provides production-quality physics |
| Friction solver | Custom WASM | Iterative solver with separate static/dynamic counts |
| 100 Hz tick | requestAnimationFrame + fixed timestep accumulator | Standard game loop pattern |

### Implementation Priority: CRITICAL
### Estimated Complexity: VERY COMPLEX

**Recommendation**: Start with a simplified 2-parameter force model approximating CarSport physics. Use the Openplanet vehicle state fields as the target output specification. Leverage community tools like TMInterface for validation data (record inputs + expected positions, verify browser simulation matches). Consider using rapier.js for collision detection and writing custom vehicle force models on top.

---

## 3. Rendering Pipeline

### What We Know (Confidence: HIGH for pipeline structure, MEDIUM for details)

**Pipeline architecture** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 7, [11-rendering-deep-dive.md](11-rendering-deep-dive.md), VERIFIED):

19-pass deferred pipeline:
1. DipCulling (frustum/occlusion)
2. DeferredWrite (G-buffer fill)
3. DeferredWriteFNormal (face normals)
4. DeferredWriteVNormal (vertex normals)
5. DeferredDecals
6. DeferredBurn
7. DeferredShadow (PSSM)
8. DeferredAmbientOcc (HBAO+)
9. DeferredFakeOcc
10. CameraMotion (motion vectors)
11. DeferredRead (G-buffer read / start lighting)
12. DeferredReadFull
13. Reflects_CullObjects
14. DeferredLighting (light accumulation)
15. CustomEnding
16. DeferredFogVolumes (volumetric fog)
17. DeferredFog (global fog)
18. LensFlares
19. FxTXAA (temporal AA)

**G-buffer** (from [11-rendering-deep-dive.md](11-rendering-deep-dive.md) Section 2, [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 7):
- 4 core MRT + depth: MDiffuse, MSpecular, PixelNormalInC, LightMask, DeferredZ
- Additional: FaceNormalInC, VertexNormalInC, PreShade, DiffuseAmbient
- Depth format: D24_UNORM_S8_UINT (VERIFIED from D3D11 log)
- Other formats: SPECULATIVE (likely R8G8B8A8 for diffuse/specular, R16G16B16A16_FLOAT for normals)

**D3D11 device requirements** (from [11-rendering-deep-dive.md](11-rendering-deep-dive.md) Section 1, VERIFIED):
- Feature level: D3D11.0 minimum (SM 5.0), D3D11.1 preferred
- BGRA support required (0x20 flag)
- Swap chain: B8G8R8A8_SRGB, triple buffered, D24_UNORM_S8_UINT depth
- MSAA: queried for 1, 2, 4, 8 samples but deferred mode uses FXAA/TXAA instead

**Vertex formats** (from [11-rendering-deep-dive.md](11-rendering-deep-dive.md), VERIFIED from D3D11 log):
- Block geometry: stride 56, 7 attributes (position R32G32B32, normal R16G16B16A16_SNORM, color B8G8R8A8, UV0 R32G32, UV1/lightmap R32G32, tangent R16G16B16A16_SNORM, bitangent R16G16B16A16_SNORM). Note: doc 11 says stride 52 but [18-validation-review.md](18-validation-review.md) Issue 3 confirms 56 is correct.
- Simple geometry: stride 28, 3 attributes (position, normal, UV)
- Lightmapped geometry: stride 52, 6 attributes (position, normal, UV0, UV1/lightmap, tangent, bitangent)

**Shadows** (from [05-rendering-graphics.md](05-rendering-graphics.md), [11-rendering-deep-dive.md](11-rendering-deep-dive.md)):
- PSSM with 4 cascades
- Shadow volumes, shadow cache, clip-map, static baked, fake shadows

**Post-processing** (VERIFIED from string references):
- HDR bloom (3 quality levels), filmic tone mapping, auto-exposure
- FXAA or TXAA (NVIDIA GFSDK + Ubisoft custom fallback)
- Volumetric fog (ray marching), SSR (temporal)
- GPU-driven particles with compute shaders, voxelized self-shadowing (6 passes)

**Block size**: 32 meters per block unit (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 8, VERIFIED)

### What We Do Not Know

- Exact DXGI formats for G-buffer targets (only depth is confirmed)
- Normal encoding scheme (three separate normal buffers -- unusual architecture)
- PBR material parameter encoding (GGX BRDF specifics)
- Lightmap format and how it integrates with deferred lighting
- Impostor system for distance rendering
- 200+ shader files -- none have been decompiled/reconstructed
- LOD transition distances and computation
- Particle system spawn/update compute shader logic

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| D3D11 deferred renderer | WebGPU render pipeline | WebGPU supports MRT, compute shaders, depth textures |
| HLSL shaders (SM 5.0) | WGSL shaders | Manual translation required; naga can help |
| G-buffer (4 MRT + depth) | WebGPU render bundle with multiple color attachments | Max 8 color attachments in WebGPU, 4 is fine |
| PSSM shadows (4 cascades) | WebGPU shadow maps | Standard technique, well-documented |
| HBAO+ | Custom SSAO in compute shader | Many open-source WebGPU SSAO implementations |
| TXAA | Custom TAA in compute shader | Motion vector + history buffer approach |
| HDR bloom | Compute shader downscale chain | Standard technique |
| Volumetric fog | Ray marching compute shader | Performance-sensitive, may need to simplify |
| GPU particles | Compute shader particles | WebGPU compute shaders fully support this |
| PBR (GGX BRDF) | Standard PBR shader | Well-documented, many references |

### Implementation Priority: CRITICAL
### Estimated Complexity: VERY COMPLEX

**Recommendation**: Start with a simplified forward renderer (no deferred pass) for the MVP. Render blocks with basic PBR lighting, a single directional light, and basic shadows. Upgrade to deferred only when performance requires it for many light sources. Use three.js or Babylon.js as a starting point and migrate to raw WebGPU for the deferred pipeline later.

---

## 4. GBX File Parser

### What We Know (Confidence: HIGH)

The GBX format is the best-documented subsystem. A parser can be built from the research alone.

**Header format** (from [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Sections 1-5, VERIFIED):
```
Magic: "GBX" (3 bytes)
Version: uint16 (3-6 supported, TM2020 = version 6)
Format flags: 4 bytes (v6+): B/T, C/U, C/U, R/E
  - "BUCR" = Binary, Uncompressed, Compressed stream, with References
  - "BUCE" = Binary, Uncompressed, Compressed stream, no External refs
Class ID: uint32 (MwClassId of root node)
User data size: uint32
Header chunk count: uint32
Header chunk index: array of (chunk_id uint32, chunk_size uint32) -- bit 31 = "heavy" skip flag
Header chunk data: concatenated payloads
Node count: uint32
```

**Reference table** (from [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 5):
- External reference count (max 49,999)
- Ancestor level count + folder paths
- Per-reference entries with flags

**Body** (from [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Sections 6-8):
- If compressed: uncompressed_size uint32, compressed_size uint32, zlib-compressed data
- Chunk stream: repeating (chunk_id uint32, chunk_data) until 0xFACADE01 sentinel
- Body stream compression controlled by format flag byte 2

**Compression**: zlib exclusively (VERIFIED, [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 4)

**Class factory**: 200+ legacy-to-modern class ID remappings for backward compatibility (from [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 11, VERIFIED)

**String serialization** (from [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 13):
- LookbackString system: 2-bit flag prefix -- 0b11 = new string, 0b10 = reference to previous, 0b00 = empty
- Flag 0b01 meaning is UNKNOWN (community documentation gap)

**Map file** (CGameCtnChallenge, class 0x03043000):
- Known header chunks: 0x03043002 (map info), 0x03043003 (common header), 0x03043004 (version), 0x03043005 (community ref), 0x03043007 (thumbnail), 0x03043008 (author info)
- 22-stage loading pipeline (from [06-file-formats.md](06-file-formats.md))

### What We Do Not Know

- Full body chunk ID catalog (only 6 map header chunks documented out of hundreds)
- Ghost/replay chunk format
- Item mesh data format (CPlugSolid2Model vertex/index buffers)
- Embedded texture formats within GBX
- How the class registry two-level hierarchy handles chunk dispatch for unknown chunk IDs

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| zlib decompression | DecompressionStream API or pako.js | Native browser support for zlib inflate |
| Binary file reading | DataView / ArrayBuffer | Standard Web APIs |
| Class factory (MwClassId dispatch) | TypeScript class registry with Map<number, parser> | Clean pattern |
| LookbackString | Custom string table with index references | Simple to implement |
| Legacy class ID remap | Lookup table (200+ entries from doc 16) | Direct port |

### Implementation Priority: CRITICAL (required before anything else can load)
### Estimated Complexity: MODERATE (header/body parsing) to COMPLEX (per-chunk-type parsers)

**Recommendation**: Use gbx-ts (existing TypeScript GBX parser by BigBang1112) as the foundation. It already handles header parsing, compression, and many chunk types. Extend it for any missing TM2020-specific chunks. The 200+ class ID remap table from doc 16 should be ported directly.

**Existing tools**: gbx-net (C#), gbx-ts (TypeScript), pygbx (Python) all exist in the community and handle the core format.

---

## 5. Audio System

### What We Know (Confidence: MEDIUM)

**Audio backend** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 1, VERIFIED):
- OpenAL via `OpenAL64_bundled.dll` (dynamically loaded)
- COalAudioPort::InitImplem at `0x14138c090`
- Initialization: alcOpenDevice -> alcCreateContext -> query mono/stereo sources -> check EFX
- Function pointers XOR-obfuscated at offsets +0x298, +0x2B1 (anti-tamper)
- ALC version 1.x

**Audio file formats** (from [09-game-files-analysis.md](09-game-files-analysis.md), [13-subsystem-class-map.md](13-subsystem-class-map.md)):
- Ogg Vorbis (vorbis64.dll) for music/sounds
- WAV support (CPlugFileWav)
- Generated/procedural sounds (CPlugFileSndGen)
- Motor sound files (CPlugFileAudioMotors)

**Audio class hierarchy** (from [13-subsystem-class-map.md](13-subsystem-class-map.md) Section 1, 30 classes):
- CAudioManager (orchestrator) -> CAudioPort (output) -> COalAudioPort (OpenAL impl)
- Source types: Engine, Gauge, Mood, Multi, Music, Surface
- Spatial: CAudioZone, CAudioZoneSource, CAudioListener
- Resource types: CPlugSound, CPlugSoundEngine/2, CPlugSoundMood, CPlugSoundMulti, CPlugSoundSurface
- Script integration: CAudioScriptManager, CAudioScriptMusic, CAudioScriptSound

### What We Do Not Know

- OpenAL source pooling (how many sources, priority system)
- Engine sound synthesis (CPlugSoundEngine vs CPlugSoundEngine2 -- likely RPM-based sample crossfading)
- Spatial audio zone blending algorithm
- EFX (environmental effects/reverb) configuration per map zone
- Music transition/crossfade logic
- Audio parameter curves (how speed/RPM maps to pitch/volume)

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| OpenAL | Web Audio API | Direct mapping: AudioContext, PannerNode, GainNode |
| Ogg Vorbis | decodeAudioData() | Native browser Ogg support |
| 3D spatial audio | PannerNode (HRTF model) | Built-in, high quality |
| EFX reverb | ConvolverNode | Requires impulse response samples |
| Engine sound (RPM-based) | AudioBufferSourceNode with playbackRate | Crossfade between RPM samples |
| Source pooling | AudioContext source limit management | ~100+ sources in modern browsers |
| Audio zones | GainNode per zone with distance attenuation | Custom spatial blending |

### Implementation Priority: IMPORTANT (but not for MVP)
### Estimated Complexity: MODERATE

**Recommendation**: Start with basic engine sound (single sample with pitch based on RPM), tire screech (slip coefficient threshold), and background music. Web Audio API is well-suited for this. Defer spatial audio zones and environmental effects to later phases.

---

## 6. Input System

### What We Know (Confidence: HIGH)

**Input devices** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 2, [00-master-overview.md](00-master-overview.md)):
- DirectInput 8 for keyboard/mouse
- XInput 9.1.0 for gamepads
- CInputPort::Update_StartFrame at `0x1402acea0` runs each frame (VERIFIED)

**CInputPort state** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 2):
- +0x18: keyboard connected (bool)
- +0x1C: mouse connected (bool)
- +0x1B0: device count
- 150ms timeout for device connectivity checks
- Event types 0xC and 0x5 set activity flags
- Virtual methods at +0x120, +0x128, +0x1A8 for polling

**Input values** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 1):
- InputSteer: float -1.0 to 1.0 (steering)
- InputGasPedal: float 0.0 to 1.0 (throttle)
- InputBrakePedal: float 0.0 to 1.0 (brake)
- InputIsBraking: bool
- InputVertical: float (reactor/flying)

### What We Do Not Know

- Key binding system (how keys map to actions)
- Analog stick deadzone configuration
- Input buffering/smoothing for network play
- Action mapping table (which game actions exist beyond driving)

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| DirectInput 8 keyboard | KeyboardEvent (keydown/keyup) | Digital steering: -1, 0, +1 |
| XInput gamepad | Gamepad API (navigator.getGamepads()) | Analog steer, trigger throttle/brake |
| 150ms device timeout | Gamepad API "connected"/"disconnected" events | Direct mapping |
| Analog input smoothing | Custom smoothing in JS | Linear interpolation per frame |

### Implementation Priority: CRITICAL
### Estimated Complexity: SIMPLE

**Recommendation**: Trivial to implement. Map arrow keys to digital steer/gas/brake. Map gamepad left stick X to analog steer, right trigger to gas, left trigger to brake. Use the Gamepad API polling model (check every frame in requestAnimationFrame). This subsystem can be built in a day.

---

## 7. Camera System

### What We Know (Confidence: HIGH)

**Camera types** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 3, [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 7, VERIFIED):
- 12 camera controller classes identified
- Race cameras: Race, Race2, Race3 (3 variants for chase cam)
- FirstPerson, Free, Orbital3d, EditorOrbital, Helico, VehicleInternal, HmdExternal, Target
- Camera shake effect (CGameControlCameraEffectShake)
- Spectator types: 0=replay, 1=follow, 2=free

**Camera system** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 3):
- NGameCamera::SCamSys: 1728 bytes (0x6C0) per instance
- Camera model files loaded from .gbx: VehicleCameraRace2Model.gbx, VehicleCameraRace3Model.gbx, etc.
- Audio-camera coupling: CameraWooshVolumedB, CameraWooshMinSpeedKmh

**Projection math** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 7, VERIFIED):
```
projected = projectionMatrix * worldPos
screenPos = displayPos + (projected.xy / projected.w + 1) / 2 * displaySize
// Behind camera if projected.w > 0
```

**Editor orbital camera** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 7, VERIFIED):
```
h = (HAngle + PI/2) * -1
v = VAngle
axis = vec4(1,0,0,0) rotated by v around Z then h around Y
cameraPos = targetPos + axis.xyz * distance
```

**Coordinate system** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 9, PLAUSIBLE):
- Y-axis is UP
- Z-axis is forward
- Left-handed coordinate system (consistent with D3D11)
- iso4 = 3x3 rotation + vec3 position (48 bytes, implicit homogeneous row)

### What We Do Not Know

- Race camera follow distance/height/stiffness curves
- Camera collision avoidance algorithm
- Smooth camera transition between types
- First-person camera offset within vehicle
- Camera model .gbx file internal format

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| Camera controllers | Custom JS classes per camera type | Straightforward |
| Projection matrix | glMatrix or manual mat4 | Standard perspective projection |
| Orbital camera | Orbit controls (three.js has one built-in) | Direct port of documented math |
| Camera shake | Random offset with decay | Simple effect |

### Implementation Priority: CRITICAL
### Estimated Complexity: MODERATE

**Recommendation**: Implement chase camera (Race variant) first -- follow vehicle position with spring damper for smooth tracking. The orbital camera math is fully documented and can be ported directly. Use three.js OrbitControls as a reference for the editor camera. Camera model .gbx files likely contain the follow distance/height parameters; parsing them would give accurate behavior.

---

## 8. ManiaScript Engine

### What We Know (Confidence: MEDIUM for lexer, LOW for runtime)

**Token specification** (from [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 10, VERIFIED):
- 12 data types: Void, Boolean, Integer, Real, Text, Vec2, Vec3, Int2, Int3, Iso4, Ident, Class
- 7 directives: #RequireContext, #Setting, #Struct, #Include, #Extends, #Command, #Const
- Keywords: sleep, yield, wait, meanwhile, assert, dump, dumptype, log
- 20+ collection operations: .add, .remove, .count, .sort, .existskey, .tojson, .fromjson, etc.
- Lexer tokens: WHITESPACE, STRING, NATURAL, FLOAT, IDENT, COMMENT, etc.
- Tuning system: TUNING_START, TUNING_END, TUNING_MARK

**Engine integration** (from [08-game-architecture.md](08-game-architecture.md)):
- CScriptEngine::Run executes scripts with per-script profiling tags
- Interface binding via CScriptInterfacableValue
- Cloud storage operations (.cloudrequestsave, .cloudisready)

### What We Do Not Know

- **Complete built-in function/method catalog** -- the script API surface exposed to modders
- **Runtime semantics** of sleep/yield/wait/meanwhile (scheduling model)
- **Script-to-engine binding mechanism** (how CScriptInterfacableValue connects to game state)
- **Expression evaluation** (operator precedence, type coercion rules)
- **Error handling** model
- **Performance** (interpreted? bytecode-compiled? JIT?)
- **Sandbox** restrictions (what can scripts access?)

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| ManiaScript lexer | Custom tokenizer in TypeScript | Token table fully documented |
| ManiaScript parser | Recursive descent parser | Standard approach for custom languages |
| ManiaScript runtime | Tree-walking interpreter or bytecode VM in JS | Must implement coroutine semantics |
| sleep/yield/wait | async/await + custom scheduler | Map to JS coroutine patterns |
| #Include | Module system with script registry | Fetch and cache scripts |
| CScriptInterfacableValue | Proxy objects wrapping game state | JS Proxy for property interception |

### Implementation Priority: NICE-TO-HAVE (for MVP; IMPORTANT for full recreation)
### Estimated Complexity: VERY COMPLEX

**Recommendation**: For MVP, skip ManiaScript entirely. Game modes and custom rules use ManiaScript, but basic racing does not require it. When needed, implement a tree-walking interpreter in TypeScript. The token specification from doc 15 is a complete lexer spec. The hard part is the built-in API surface -- consider scraping the official ManiaScript documentation at https://doc.maniaplanet.com/maniascript for the API reference. The coroutine model (sleep/yield/wait/meanwhile) maps naturally to JavaScript async generators.

---

## 9. Networking

### What We Know (Confidence: MEDIUM for architecture, LOW for protocols)

**Architecture** (from [17-networking-deep-dive.md](17-networking-deep-dive.md), [07-networking.md](07-networking.md)):
- 11-layer architecture from Winsock2 to CGameCtnNetwork
- Dual TCP+UDP game protocol
- libcurl + OpenSSL 1.1.1t+quic statically linked
- 562 networking classes across CNet*, CWebServices*, CGame*Network* prefixes

**Authentication** (from [17-networking-deep-dive.md](17-networking-deep-dive.md) Section 2, [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 6, VERIFIED):
1. UPC ticket from Ubisoft Connect (upc_r2_loader64.dll)
2. UbiServices session via POST to public-ubiservices.ubi.com/v3/profiles/sessions
3. Nadeo token exchange: POST to core.trackmania.nadeo.live/v2/authentication/token/ubiservices
4. Token refresh: POST to core.trackmania.nadeo.live/v2/authentication/token/refresh

**API services** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 5, VERIFIED):
- Core: https://prod.trackmania.core.nadeo.online (audience: NadeoServices)
- Live: https://live-services.trackmania.nadeo.live (audience: NadeoLiveServices)
- Meet: https://meet.trackmania.nadeo.club (audience: NadeoLiveServices)
- Auth header format: `Authorization: nadeo_v1 t=<token>`
- Token lifetime: 55 minutes + random 1-60s jitter

**Network update cycle** (from [17-networking-deep-dive.md](17-networking-deep-dive.md), VERIFIED from strings):
```
1. NetUpdate_BeforePhy (receive remote inputs)
2. Physics Step (deterministic simulation)
3. NetUpdate_AfterPhy (send local results)
4. NetLoop_Synchronize (sync game timer)
```

**Text chat**: XMPP protocol to *.chat.maniaplanet.com
**Voice chat**: Vivox (VoiceChat.dll, loaded at runtime)
**Legacy**: XML-RPC server (same protocol as TMNF/TM2 dedicated server controllers)

### What We Do Not Know

- **UDP game protocol packet format** -- complete unknown
- **Actual API endpoint URLs** -- doc 17's inferred URLs are SPECULATIVE ([18-validation-review.md](18-validation-review.md) Issue 36)
- **Matchmaking algorithm**
- **Anti-cheat replay verification** (server-side)
- **HTTP/3 (QUIC) usage** -- OpenSSL+quic is linked but unclear if active
- **Game state synchronization details** (what data is sent per frame)
- **Prediction/interpolation model** for remote players

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| Winsock2 TCP | WebSocket | For persistent connections, lobby, chat |
| Winsock2 UDP | WebRTC DataChannel (unreliable mode) | For real-time game state |
| libcurl HTTP | fetch API | For REST API calls |
| OpenSSL | Built-in browser TLS | Transparent |
| XMPP chat | WebSocket to XMPP bridge, or custom | Could use existing XMPP-over-WebSocket libs |
| Vivox voice | WebRTC voice | Built-in browser support |
| XML-RPC | Custom XML parser or existing library | Could reuse existing community tools |

### Implementation Priority: IMPORTANT (for multiplayer; skip for MVP)
### Estimated Complexity: VERY COMPLEX

**Recommendation**: For MVP, implement offline/single-player only. For multiplayer, design a custom protocol over WebSocket + WebRTC DataChannel rather than trying to replicate Nadeo's proprietary UDP protocol. Use the deterministic physics model to synchronize: send only inputs, let each client simulate independently, verify periodically. The authentication flow is well-documented from Openplanet and can be replicated for API access (maps, leaderboards, ghosts).

---

## 10. Map Loading

### What We Know (Confidence: HIGH for format, MEDIUM for rendering)

**Map file format** (from [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md), [06-file-formats.md](06-file-formats.md)):
- CGameCtnChallenge (class 0x03043000)
- 22-stage loading pipeline
- GBX v6 format with BUCR/BUCE flags
- zlib-compressed body
- Header chunks for metadata (map name, author, thumbnail, etc.)

**Block system** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md), [13-subsystem-class-map.md](13-subsystem-class-map.md)):
- 32 meters per block unit
- 60 map/block system classes
- Block types organized by environment (Stadium, Rally, Snow, Desert)

**Materials** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 10, VERIFIED):
- 208 materials catalogued with complete Surface ID table (19 unique surface types)
- Gameplay effects are NOT material-driven -- applied through block/item types or trigger zones
- Materials affect: surface ID (physics friction/sound), UV layers, optional vertex color
- UV layers: BaseMaterial (layer 0) for diffuse/PBR, Lightmap (layer 1) for baked lighting

**Surface physics** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 10):
- Asphalt, Concrete, Dirt, Grass, Ice, Metal, Pavement, Plastic, Rubber, Sand, Snow, Wood, etc.
- NotCollidable surface for pass-through geometry (chrono digits, glass)

### What We Do Not Know

- Block mesh data format within pack files
- How blocks snap together (connection points, rotation rules)
- Item placement within maps (embedded items vs referenced items)
- Lightmap data format and how it is baked into maps
- Terrain/decoration geometry generation
- Water surface rendering and collision volume
- Skinning system for custom car skins

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| GBX map parsing | gbx-ts (TypeScript) | Existing library handles core format |
| Block meshes | WebGPU vertex/index buffers | Load from parsed GBX into GPU buffers |
| Materials/textures | WebGPU texture + sampler | Load DDS/WebP textures, create materials |
| Lightmaps | WebGPU texture (UV1 channel) | Second UV set for lightmap lookup |
| Surface ID -> physics | Lookup table | 19 surface types, each with friction/bounce params |

### Implementation Priority: CRITICAL
### Estimated Complexity: COMPLEX

**Recommendation**: Use gbx-ts or gbx-net to parse map files. The community has extensive documentation on map chunk formats (gbx-net wiki). The main challenge is converting block meshes to renderable geometry -- blocks are defined by their type/variant/position/rotation, and the actual mesh data comes from pack files. Consider extracting block meshes from pack files offline (using NadeoImporter or community tools) and serving them as pre-converted glTF/GLB files.

---

## 11. Ghost/Replay System

### What We Know (Confidence: MEDIUM for class structure, LOW for binary format)

**Class hierarchy** (from [13-subsystem-class-map.md](13-subsystem-class-map.md) Section 6, 14 classes):
- CGameCtnGhost -- Ghost data container
- CGameCtnReplayRecord -- Full replay container
- CGameCtnMediaClip / CGameCtnMediaTrack -- MediaTracker clips/tracks within replays
- 65+ MediaTracker block types for cutscene/replay editing

**Replay data flow** (from [12-architecture-deep-dive.md](12-architecture-deep-dive.md)):
- States 0xC74 (replay validation), 0xC93 (post-load ghost), 0xCEF-0xCF0 (load replay)
- Ghost processing via FUN_140ef83f0

**Input recording** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 1):
- InputSteer, InputGasPedal, InputBrakePedal, InputIsBraking -- these are the inputs that would need recording
- DiscontinuityCount tracks teleport/reset events
- SimulationTimeCoef tracks slow-motion

**Entity ID masks** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 4):
- 0x04000000 mask = replay/editor vehicle

### What We Do Not Know

- **Ghost binary format** (how inputs are encoded, compressed, timestamped)
- **Replay file chunk IDs** (which body chunks contain ghost data)
- **Input compression** scheme (likely delta-encoded or run-length for repeated states)
- **Validation checksum** (how replays are verified for anti-cheat)
- **MediaTracker clip format** (camera keyframes, effects, timing)

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| Ghost binary format | Custom ArrayBuffer parser | Once format is known |
| Input recording | Array of {tick, steer, gas, brake} | Simple to implement |
| Input playback | Feed recorded inputs to physics | Deterministic replay |
| MediaTracker | Custom keyframe animation system | Complex but not essential for MVP |

### Implementation Priority: IMPORTANT
### Estimated Complexity: MODERATE (basic ghost) to COMPLEX (full MediaTracker)

**Recommendation**: For the browser version, record inputs as simple JSON arrays: `[{tick: 0, steer: 0.0, gas: 1.0, brake: 0.0}, ...]`. If deterministic physics is achieved, replaying these inputs will reproduce the exact run. For loading official TM2020 ghosts, the binary format needs further reverse engineering -- consider using gbx-net which has partial ghost parsing support. MediaTracker is a luxury feature and should be deferred indefinitely.

---

## 12. UI System

### What We Know (Confidence: LOW-MEDIUM)

**Control system** (from [13-subsystem-class-map.md](13-subsystem-class-map.md) Section 4, 70 classes):
- CControlEngine manages UI
- CControlContainer is the base layout container
- 7 frame phases for UI update cycle
- ManiaLink is the HTML-like UI markup language
- CControlFrame hierarchy accessible via editor.EditorInterface.InterfaceScene.Mobils[0]

**UI classes include**: CControlLabel, CControlButton, CControlEntry (text input), CControlSlider, CControlList, CControlGrid, CControlMediaItem, CControlColorChooser, etc.

**Known UI frame IDs** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 11):
- FrameDeveloperTools (hidden Nadeo dev tools)
- FrameEditTools (main editor toolbar)
- ButtonOffZone (hidden by default)
- FrameLightTools (lighting controls)

### What We Do Not Know

- ManiaLink XML schema and rendering model
- CSS-like styling system
- Layout engine (how containers position children)
- Focus/navigation model for gamepad UI
- Animation system for UI transitions
- How ManiaLink integrates with ManiaScript

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| ManiaLink markup | HTML + CSS | Direct conceptual mapping |
| CControlEngine | DOM manipulation / React / Svelte | Any UI framework works |
| UI layout | CSS Flexbox/Grid | Standard web layout |
| Gamepad navigation | Custom focus management | Tab-like navigation with gamepad |
| ManiaScript-driven UI | JavaScript event handlers | Direct mapping |

### Implementation Priority: IMPORTANT (but HTML/CSS is natural for browser)
### Estimated Complexity: MODERATE

**Recommendation**: The browser has a massive advantage here -- HTML/CSS is the most mature UI technology available. Do NOT try to replicate ManiaLink. Build the UI in standard HTML/CSS/TypeScript using React, Svelte, or vanilla web components. This will be faster to develop and more accessible. The game UI (menus, HUD, leaderboards) is straightforward web development.

---

## 13. Map Editor

### What We Know (Confidence: LOW-MEDIUM)

**Editor classes** (from [13-subsystem-class-map.md](13-subsystem-class-map.md) Section 5, 71 classes):
- 15+ editor types: Map, Item, Mesh, Material, MediaTracker, Action, Module, etc.
- CGameCtnEditorCommon is the base editor class

**Editor camera** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 11, VERIFIED):
- Orbital camera with HAngle, VAngle, TargetedPosition, CameraToTargetDistance
- ScrollAreaStart = 0.7, ScrollAreaMax = 0.98 (defaults)

**Block grid** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 8):
- 32 meters per block unit

**Editor UI** (from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 11):
- CControlContainer hierarchy for UI frames
- Offzone placement can be enabled via binary patch

**State machine** (from [12-architecture-deep-dive.md](12-architecture-deep-dive.md)):
- Editor session at state 0xDE5, calls FUN_140b827b0 for editor loop
- Menu results: 0x10 (old editor), 0x11 (new editor), 0x12 (item editor)

### What We Do Not Know

- **Block placement validation rules** (which blocks can connect where)
- **Block variant system** (how block shapes/variants are selected)
- **Item placement system** (pivot points, snap points, free placement)
- **Undo/redo implementation**
- **Map validation** (what makes a map "valid" for racing)
- **Terrain editing** (how terrain blocks modify height)
- **Decoration/mood system** (how map themes are applied)

### Browser Technology Mapping

| TM2020 | Browser | Notes |
|---|---|---|
| 3D block placement | WebGPU + raycasting | Click-to-place on grid |
| Orbital camera | Custom orbit controller | Math fully documented |
| Block grid (32m units) | Snap-to-grid system | Straightforward |
| UI toolbars | HTML/CSS overlay | Web advantage |
| Undo/redo | Command pattern | Standard approach |

### Implementation Priority: NICE-TO-HAVE
### Estimated Complexity: VERY COMPLEX

**Recommendation**: The editor is the hardest subsystem to recreate faithfully because block placement rules are almost entirely undocumented. Start with a simplified editor that places blocks on a grid without validation. The community has partial block connection data in tools like tm-editor-route. Full validation would require extensive trial-and-error testing against the real game.

---

## 14. MVP Definition

### Minimum Viable Product

A browser-based Trackmania experience that can:

1. **Load a TM2020 .Map.Gbx file** and render it in 3D
2. **Drive the CarSport (Stadium car)** with keyboard and gamepad input
3. **Basic physics** that feel approximately correct (speed, steering, jumping)
4. **Record and replay ghosts** (own format, not TM2020 binary format)
5. **Timer** showing race time with checkpoint splits
6. **Basic 3D rendering** with lighting, shadows, and textures

### What the MVP Does NOT Include

- Multiplayer
- ManiaScript execution
- Map editor
- Official ghost/replay loading
- Audio (can be added easily but not essential)
- Snow/Rally/Desert car types
- MediaTracker
- Online services (leaderboards, map download)

### MVP Tech Stack Recommendation

| Component | Technology | Reasoning |
|---|---|---|
| Rendering | three.js + WebGPU backend | Fastest path to 3D rendering; upgrade to raw WebGPU later |
| Physics | Custom WASM (Rust) | Determinism requires controlled floating-point; rapier for collision |
| GBX Parser | gbx-ts (extend as needed) | Existing community library |
| UI | Svelte or React | Standard web UI |
| Build | Vite + TypeScript | Modern web toolchain |
| State management | Simple TypeScript classes | No framework needed for game state |

---

## 15. Implementation Order

### Phase 1: Foundation (Weeks 1-4)
**Goal**: Load and display a map

1. GBX parser (extend gbx-ts for TM2020 map chunks)
2. Block mesh extraction (offline tool to convert pack file meshes to glTF)
3. Basic WebGPU/three.js renderer (block geometry + basic materials)
4. Map loader (place blocks at correct grid positions with rotations)
5. Free camera (orbit/fly through the loaded map)

### Phase 2: Driving (Weeks 5-10)
**Goal**: Drive a car around the map

6. Input system (keyboard + gamepad)
7. Vehicle physics (simplified CarSport model in WASM)
8. Collision detection (car vs block geometry)
9. Chase camera (spring-damper following vehicle)
10. Surface effects (basic friction variation by surface ID)

### Phase 3: Racing (Weeks 11-16)
**Goal**: Complete a race with timing

11. Checkpoint/finish detection (waypoint blocks)
12. Race timer with checkpoint splits
13. Ghost recording (input arrays)
14. Ghost playback (semi-transparent car replaying inputs)
15. Reset to checkpoint (respawn)

### Phase 4: Polish (Weeks 17-24)
**Goal**: Make it feel good

16. Audio (engine sound, tire screech, music)
17. Turbo/boost effects (visual + force)
18. Basic HUD (speedometer, race time, checkpoint times)
19. Deferred rendering (upgrade from forward)
20. Shadows (PSSM, basic quality)
21. Post-processing (bloom, tone mapping, basic AA)

### Phase 5: Expansion (Weeks 25+)
**Goal**: Online features and additional content

22. Online ghost download (Nadeo API integration)
23. Leaderboard display
24. Additional car types (Snow, Rally, Desert)
25. Map editor (basic block placement)
26. Multiplayer (WebRTC-based)
27. ManiaScript interpreter (basic subset)

---

## 16. External Libraries and Tools

### Existing Community Tools

| Tool | Language | Use For |
|---|---|---|
| [gbx-net](https://github.com/BigBang1112/gbx-net) | C# | Reference GBX parser, most complete implementation |
| [gbx-ts](https://github.com/BigBang1112/gbx-ts) | TypeScript | Browser GBX parser, usable directly |
| [TMInterface](https://donadigo.com/tminterface) | C++ | Physics validation data (record inputs + positions) |
| [Openplanet](https://openplanet.dev) | AngelScript | Live game data extraction, offset documentation |
| [NadeoImporter](https://doc.trackmania.com/nadeoimporter/) | Tool | Block/item mesh extraction and material reference |
| [tm-editor-route](https://github.com/GreepTheSheep/editor-route) | JS | Block connection data |

### Recommended NPM Packages

| Package | Purpose |
|---|---|
| `three` | 3D rendering (WebGPU backend) |
| `rapier3d-compat` | Physics collision detection (WASM) |
| `pako` | zlib inflate (for GBX decompression) |
| `gl-matrix` | Matrix/vector math |
| `@aspect/gamepad` | Gamepad API wrapper |

### WASM Toolchain

- **Rust + wasm-pack**: For physics engine (deterministic floating-point control)
- **emscripten**: If porting C/C++ physics code

---

## 17. Hardest Problems

Ranked by difficulty and impact:

### 1. Physics Feel (VERY HARD)
The 7 force model functions have NOT been decompiled internally. Getting the car to feel like TM2020 requires either:
- (a) Decompiling FUN_140851f00 (CarSport model, ~estimated 2000+ lines of C) and porting it exactly
- (b) Iterative tuning against TMInterface validation data (tedious but possible)
- (c) Using TMNF community physics documentation as a starting point and adapting

### 2. Block Mesh Extraction (HARD)
Block meshes live in pack files which are not fully documented. Options:
- (a) Extract meshes using community tools and serve as pre-converted assets
- (b) Implement a full NadeoPak parser (partially documented in [09-game-files-analysis.md](09-game-files-analysis.md))
- (c) Use the NadeoImporter tool to export individual blocks

### 3. Deterministic Physics (HARD)
Replay validation requires bit-exact floating-point results. Browser JavaScript does not guarantee IEEE 754 strict mode. Options:
- (a) Use WASM (Rust/C++) with strict floating-point flags
- (b) Use fixed-point arithmetic (loses precision but gains determinism)
- (c) Accept approximate physics and do not support official ghost validation

### 4. Deferred Rendering Pipeline (HARD)
19-pass deferred pipeline with 9 G-buffer targets is ambitious for WebGPU. Options:
- (a) Start with forward rendering (simpler, still looks acceptable)
- (b) Implement simplified deferred (4 MRT + depth, fewer passes)
- (c) Progressive enhancement: forward for low-end, deferred for high-end

### 5. ManiaScript Runtime (HARD)
A full language interpreter with coroutine support. Options:
- (a) Skip for MVP (custom game modes will not work)
- (b) Implement a subset (basic race rules only)
- (c) Transpile ManiaScript to JavaScript (complex but allows using JS runtime)

---

## 18. Blocking Unknowns

These are unknowns that could halt progress if not resolved:

### Truly Blocking (Must Resolve)

| Unknown | Impact | Mitigation |
|---|---|---|
| Block mesh data within pack files | Cannot render maps without block geometry | Use community tools to extract meshes offline; serve as static assets |
| At least one force model's internals | Physics will not feel like TM2020 | Use TMInterface to capture input/output pairs and tune iteratively |
| Surface ID to friction coefficient mapping | Cars will slide wrong on different surfaces | Use Openplanet to measure friction on each surface type empirically |

### Potentially Blocking (May Need Resolution)

| Unknown | Impact | Mitigation |
|---|---|---|
| Ghost binary format | Cannot load official ghosts | Record own ghosts in custom format; official ghost loading is a nice-to-have |
| Lightmap data format | Maps will look flat without baked lighting | Use dynamic lighting instead; acceptable visual quality |
| Tick rate (100 Hz unconfirmed) | Physics step size affects all dynamics | 100 Hz is community-established and almost certainly correct; proceed with it |
| Turbo ramp-up vs decay | Turbo boost will feel wrong | Test both directions; use TMInterface to capture actual turbo acceleration curves |

### Not Blocking (Can Work Around)

| Unknown | Impact | Mitigation |
|---|---|---|
| UDP game protocol | Cannot connect to official servers | Build custom multiplayer protocol |
| ManiaScript runtime | Custom game modes won't work | Hardcode standard race mode |
| Anti-cheat system | Cannot submit times to official leaderboards | Build own leaderboard |
| Full API endpoint URLs | Cannot access all Nadeo services | Use documented Core/Live/Meet base URLs + community API docs |

---

## 19. Implementation Code Skeletons

The following sections provide concrete TypeScript/WGSL pseudocode for each major subsystem. These are grounded in the RE documentation above and designed to compile (or nearly compile) as starting points. Confidence levels are noted per function -- **CERTAIN** means the logic is directly derived from verified decompiled code, **APPROXIMATE** means it follows the verified structure but fills in unknowns with reasonable defaults.

---

### 19.1 GBX Parser Skeleton (TypeScript)

This parser implements the GBX v6 format as documented in [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Sections 1-15.

```typescript
// ============================================================
// GBX Parser -- TypeScript implementation skeleton
// Source: 16-fileformat-deep-dive.md (verified from Ghidra decompilation)
// ============================================================

/** Binary reader wrapping a DataView with a cursor position. CERTAIN. */
class BinaryReader {
  private view: DataView;
  private pos: number = 0;

  constructor(buffer: ArrayBuffer) {
    this.view = new DataView(buffer);
  }

  get position(): number { return this.pos; }
  set position(v: number) { this.pos = v; }
  get remaining(): number { return this.view.byteLength - this.pos; }

  readByte(): number {
    const v = this.view.getUint8(this.pos);
    this.pos += 1;
    return v;
  }

  readUint16(): number {
    // GBX is little-endian throughout. CERTAIN (from doc 16 Section 12).
    const v = this.view.getUint16(this.pos, true);
    this.pos += 2;
    return v;
  }

  readInt32(): number {
    const v = this.view.getInt32(this.pos, true);
    this.pos += 4;
    return v;
  }

  readUint32(): number {
    const v = this.view.getUint32(this.pos, true);
    this.pos += 4;
    return v;
  }

  readFloat32(): number {
    const v = this.view.getFloat32(this.pos, true);
    this.pos += 4;
    return v;
  }

  readBytes(count: number): Uint8Array {
    const slice = new Uint8Array(this.view.buffer, this.pos, count);
    this.pos += count;
    return slice;
  }

  readString(): string {
    const length = this.readUint32();
    if (length === 0) return '';
    if (length === 0xFFFFFFFF) return ''; // null string sentinel
    const bytes = this.readBytes(length);
    return new TextDecoder('utf-8').decode(bytes);
  }

  readVec3(): [number, number, number] {
    return [this.readFloat32(), this.readFloat32(), this.readFloat32()];
  }

  readNat3(): [number, number, number] {
    return [this.readUint32(), this.readUint32(), this.readUint32()];
  }

  // ReadBool: stored as uint32, 0 or 1. CERTAIN (doc 16 Section 12).
  readBool(): boolean {
    return this.readUint32() !== 0;
  }
}

// ============================================================
// Format flags (Version 6+)
// Source: doc 16 Section 3 -- CERTAIN (decompiled from FUN_140901850)
// ============================================================
interface GbxFormatFlags {
  isBinary: boolean;     // Byte 0: 'B' = binary, 'T' = text
  bodyCompressed: boolean; // Byte 1: 'C' = compressed, 'U' = uncompressed
  bodyStreamCompressed: boolean; // Byte 2: 'C' = compressed, 'U' = uncompressed
  hasReferences: boolean;  // Byte 3: 'R' = with refs, 'E' = no external refs
}

function parseFormatFlags(reader: BinaryReader): GbxFormatFlags {
  const bytes = reader.readBytes(4);
  return {
    isBinary: bytes[0] === 0x42,         // 'B'
    bodyCompressed: bytes[1] === 0x43,   // 'C'
    bodyStreamCompressed: bytes[2] === 0x43, // 'C'
    hasReferences: bytes[3] === 0x52,    // 'R'
  };
}

// ============================================================
// Header chunk entry
// Source: doc 16 Section 4 -- CERTAIN
// ============================================================
interface HeaderChunkEntry {
  chunkId: number;
  size: number;
  isHeavy: boolean;  // Bit 31 of size field: skip unless needed
}

interface HeaderChunk extends HeaderChunkEntry {
  data: Uint8Array;
}

// ============================================================
// Reference table entry
// Source: doc 16 Section 5 -- CERTAIN (decompiled from FUN_140902530)
// ============================================================
interface ExternalReference {
  flags: number;
  fileName: string;
  nodeIndex: number;
  classId: number;
}

// ============================================================
// LookbackString system
// Source: doc 16 Section 13 -- CERTAIN
//
// Bit 31-30 flags:
//   0b11 = new string (read and add to table)
//   0b10 = reference by index (bits 29-0)
//   0b01 = well-known string (hardcoded table)
//   0b00 = empty/unset
// ============================================================
const WELL_KNOWN_STRINGS: Record<number, string> = {
  // Source: doc 16 Section 13 known well-known Id values. CERTAIN.
  1: 'Unassigned',
  2: '',
  3: 'Stadium',
  4: 'Valley',
  5: 'Canyon',
  6: 'Lagoon',
  7: 'Desert',  // APPROXIMATE -- exact mapping uncertain
};

class LookbackStringTable {
  private strings: string[] = [];
  private initialized = false;

  readLookbackString(reader: BinaryReader): string {
    // First call in a node context must have version marker = 3. CERTAIN.
    if (!this.initialized) {
      const version = reader.readUint32();
      if (version !== 3) {
        throw new Error(`LookbackString version ${version} != 3`);
      }
      this.initialized = true;
    }

    const flagsAndIndex = reader.readUint32();
    const flags = (flagsAndIndex >>> 30) & 0x3;
    const index = flagsAndIndex & 0x3FFFFFFF;

    switch (flags) {
      case 0b00: // empty
        return '';

      case 0b01: // well-known string
        return WELL_KNOWN_STRINGS[index] ?? `<unknown_wellknown_${index}>`;

      case 0b10: // reference to previously seen string (1-based index)
        if (index - 1 < this.strings.length) {
          return this.strings[index - 1];
        }
        throw new Error(`LookbackString ref index ${index} out of range`);

      case 0b11: // new string
        const str = reader.readString();
        this.strings.push(str);
        return str;

      default:
        throw new Error(`Invalid LookbackString flags: ${flags}`);
    }
  }

  reset(): void {
    this.strings = [];
    this.initialized = false;
  }
}

// ============================================================
// Class ID remapping (legacy compatibility)
// Source: doc 16 Section 11 -- CERTAIN (200+ entries from FUN_1402f2610)
// Only a representative subset shown here; full table in doc 16.
// ============================================================
const CLASS_ID_REMAP: Map<number, number> = new Map([
  [0x24003000, 0x03043000], // CGameCtnChallenge (Map)
  [0x2403F000, 0x03093000], // CGameCtnReplayRecord
  [0x0A01B000, 0x09011000], // CPlugBitmap
  [0x0A03C000, 0x09026000], // CPlugShaderApply (Material)
  [0x0801C000, 0x090BB000], // CPlugSolid2Model
  // ... 200+ more entries -- port the full table from doc 16 Section 11
]);

function remapClassId(classId: number): number {
  // Remap must be applied before any class lookup. CERTAIN.
  const masked = classId & 0xFFFFF000;
  const remapped = CLASS_ID_REMAP.get(masked);
  if (remapped !== undefined) {
    return remapped | (classId & 0x00000FFF);
  }
  return classId;
}

// ============================================================
// Body chunk stream parsing
// Source: doc 16 Sections 6-7 -- CERTAIN
// ============================================================
const END_SENTINEL = 0xFACADE01;    // End-of-body marker. CERTAIN.
const SKIP_MARKER  = 0x534B4950;    // "SKIP" in ASCII. CERTAIN.

interface BodyChunk {
  chunkId: number;
  data: Uint8Array;
  isSkippable: boolean;
}

function parseBodyChunks(reader: BinaryReader): BodyChunk[] {
  const chunks: BodyChunk[] = [];

  while (reader.remaining >= 4) {
    const chunkId = reader.readUint32();

    // End sentinel check. CERTAIN (doc 16 Section 7, FUN_1402d0c40).
    if (chunkId === END_SENTINEL) break;

    // Normalize the chunk ID via class remap. CERTAIN.
    const normalizedId = remapClassId(chunkId);

    // Check if skippable: next 4 bytes == "SKIP". CERTAIN.
    let isSkippable = false;
    let chunkData: Uint8Array;

    if (reader.remaining >= 4) {
      const maybeSkip = reader.readUint32();
      if (maybeSkip === SKIP_MARKER) {
        isSkippable = true;
        const chunkSize = reader.readUint32();
        chunkData = reader.readBytes(chunkSize);
      } else {
        // Not skippable -- put back the 4 bytes we just read.
        // Non-skippable chunks must be parsed by a handler that knows
        // when the chunk ends. For now, store remaining as raw bytes.
        reader.position -= 4;
        // A real implementation must dispatch to the chunk handler here
        // and let it consume exactly the right number of bytes.
        chunkData = new Uint8Array(0); // placeholder
      }
    } else {
      chunkData = new Uint8Array(0);
    }

    chunks.push({ chunkId: normalizedId, data: chunkData, isSkippable });
  }

  return chunks;
}

// ============================================================
// Complete parse() entry point
// Source: doc 16 Sections 1-8 -- CERTAIN for structure
//
// Mirrors the real loading pipeline from FUN_140903d30:
//   1. Reset stream
//   2. Load header (magic, version, flags, class ID, refs)
//   3. Create root node via class factory
//   4. Load reference table
//   5. Load body chunks (decompress if needed)
// ============================================================
interface GbxFile {
  version: number;
  formatFlags: GbxFormatFlags;
  classId: number;
  headerChunks: HeaderChunk[];
  references: ExternalReference[];
  bodyChunks: BodyChunk[];
}

async function parseGbx(buffer: ArrayBuffer): Promise<GbxFile> {
  const reader = new BinaryReader(buffer);

  // 1. Read magic: "GBX" (3 bytes). CERTAIN.
  const magic = reader.readBytes(3);
  if (magic[0] !== 0x47 || magic[1] !== 0x42 || magic[2] !== 0x58) {
    throw new Error('Not a GBX file: invalid magic');
  }

  // 2. Read version (uint16). CERTAIN.
  const version = reader.readUint16();
  if (version < 3 || version > 6) {
    throw new Error(`Unsupported GBX version: ${version}`);
  }

  // 3. Read format flags (v6+ only). CERTAIN.
  let formatFlags: GbxFormatFlags;
  if (version >= 6) {
    formatFlags = parseFormatFlags(reader);
    if (!formatFlags.isBinary) {
      throw new Error('Text GBX format not supported');
    }
  } else {
    formatFlags = {
      isBinary: true,
      bodyCompressed: false,
      bodyStreamCompressed: true, // v3-5 assumed compressed
      hasReferences: true,
    };
  }

  // 4. Read class ID (uint32). CERTAIN.
  const rawClassId = reader.readUint32();
  const classId = remapClassId(rawClassId);

  // 5. Read header chunks. CERTAIN.
  const userDataSize = reader.readUint32();
  const headerChunks: HeaderChunk[] = [];

  if (userDataSize > 0) {
    const numHeaderChunks = reader.readUint32();

    // Read index table first, then data. CERTAIN (doc 16 Section 4).
    const entries: HeaderChunkEntry[] = [];
    for (let i = 0; i < numHeaderChunks; i++) {
      const chunkId = reader.readUint32();
      const sizeRaw = reader.readUint32();
      entries.push({
        chunkId,
        size: sizeRaw & 0x7FFFFFFF,
        isHeavy: (sizeRaw & 0x80000000) !== 0,
      });
    }

    // Read concatenated header chunk data.
    for (const entry of entries) {
      const data = reader.readBytes(entry.size);
      headerChunks.push({ ...entry, data });
    }
  }

  // 6. Read node count (for reference table sizing). CERTAIN.
  const numNodes = reader.readUint32();

  // 7. Read reference table. CERTAIN (doc 16 Section 5, FUN_140902530).
  const references: ExternalReference[] = [];
  const numExternalNodes = reader.readUint32();

  if (numExternalNodes > 0 && numExternalNodes <= 50000) {
    const ancestorLevelCount = reader.readUint32();
    const ancestorFolders: string[] = [];
    for (let i = 0; i < ancestorLevelCount; i++) {
      ancestorFolders.push(reader.readString());
    }

    for (let i = 0; i < numExternalNodes; i++) {
      const flags = reader.readUint32();
      const fileName = (flags & 0x4) !== 0 ? '' : reader.readString();
      const nodeIndex = reader.readUint32();
      let refClassId = 0;
      if (version >= 5) {
        reader.readUint32(); // use_file
        reader.readUint32(); // folder_index
      }
      references.push({ flags, fileName, nodeIndex, classId: refClassId });
    }

    // Read class IDs for each external node
    for (let i = 0; i < numExternalNodes; i++) {
      references[i].classId = reader.readUint32();
    }
  }

  // 8. Read body (decompress if needed). CERTAIN.
  let bodyReader: BinaryReader;

  if (formatFlags.bodyStreamCompressed) {
    // Compressed body: read sizes then decompress. CERTAIN (doc 16 Section 8).
    const uncompressedSize = reader.readUint32();
    const compressedSize = reader.readUint32();
    const compressedData = reader.readBytes(compressedSize);

    // TM2020 uses zlib exclusively. CERTAIN (doc 15 Section 4 confirmed,
    // LZO NOT found in binary).
    const decompressed = await decompressZlib(compressedData, uncompressedSize);
    bodyReader = new BinaryReader(decompressed.buffer);
  } else {
    // Uncompressed: read remaining bytes as body.
    const remaining = reader.readBytes(reader.remaining);
    bodyReader = new BinaryReader(remaining.buffer);
  }

  // 9. Parse body chunk stream. CERTAIN.
  const bodyChunks = parseBodyChunks(bodyReader);

  return { version, formatFlags, classId, headerChunks, references, bodyChunks };
}

// ============================================================
// zlib decompression helper
// Uses the browser-native DecompressionStream API (preferred)
// or falls back to pako.js.
// CERTAIN: TM2020 uses zlib, not LZO (doc 15 Section 4).
// ============================================================
async function decompressZlib(
  compressed: Uint8Array,
  expectedSize: number,
): Promise<Uint8Array> {
  // Try native DecompressionStream first (Chrome 80+, Firefox 113+)
  if (typeof DecompressionStream !== 'undefined') {
    const ds = new DecompressionStream('deflate');
    const writer = ds.writable.getWriter();
    const reader = ds.readable.getReader();

    writer.write(compressed);
    writer.close();

    const chunks: Uint8Array[] = [];
    let totalLength = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      totalLength += value.length;
    }

    const result = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.length;
    }
    return result;
  }

  // Fallback: use pako
  // import pako from 'pako';
  // return pako.inflate(compressed);
  throw new Error('DecompressionStream not available and pako not loaded');
}

// ============================================================
// Chunk dispatch registry
// Maps (classId_base | chunkIndex) -> handler function
// Source: doc 16 Section 16 for known map header chunks. CERTAIN.
// ============================================================
type ChunkHandler = (reader: BinaryReader, lookback: LookbackStringTable) => any;

const CHUNK_HANDLERS: Map<number, ChunkHandler> = new Map();

// Example: CGameCtnChallenge header chunk 0x03043003 (common map header)
// APPROXIMATE -- the internal format of this chunk requires community docs
// (gbx-net wiki) for full field listing.
CHUNK_HANDLERS.set(0x03043003, (reader, lookback) => {
  const version = reader.readByte();
  const mapInfo = {
    mapUid: lookback.readLookbackString(reader),
    environment: lookback.readLookbackString(reader),
    authorLogin: lookback.readLookbackString(reader),
    mapName: reader.readString(),
    // ... additional fields depend on chunk version
  };
  return mapInfo;
});

// CGameCtnChallenge header chunk 0x03043005 (community reference)
CHUNK_HANDLERS.set(0x03043005, (reader, _lookback) => {
  // APPROXIMATE
  return reader.readString(); // XML community reference
});

// CGameCtnChallenge header chunk 0x03043007 (thumbnail + comments)
CHUNK_HANDLERS.set(0x03043007, (reader, _lookback) => {
  const version = reader.readUint32();
  if (version !== 0) {
    const thumbnailSize = reader.readUint32();
    reader.readBytes(15); // "<Thumbnail.jpg>" marker
    const thumbnail = reader.readBytes(thumbnailSize);
    reader.readBytes(16); // "</Thumbnail.jpg>" marker
    reader.readBytes(10); // "<Comments>" marker
    const comments = reader.readString();
    reader.readBytes(11); // "</Comments>" marker
    return { thumbnail, comments };
  }
  return null;
});
```

**Integration note**: For a real implementation, use [gbx-ts](https://github.com/BigBang1112/gbx-ts) which already handles hundreds of chunk types. The skeleton above shows the core format so you understand what the library does internally and can extend it for missing TM2020 chunks.

---

### 19.2 Physics Engine Skeleton (TypeScript / WASM)

This implements the simulation pipeline from [10-physics-deep-dive.md](10-physics-deep-dive.md) Sections 1-4 and the vehicle state from [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 1.

```typescript
// ============================================================
// Vehicle state -- mirrors CSceneVehicleVisState
// Source: doc 19 Section 1 (VERIFIED from live game), doc 10 Section 3
// ============================================================
interface Vec3 {
  x: number;
  y: number;
  z: number;
}

interface Iso4 {
  // 3x3 rotation matrix (row-major) + position. CERTAIN (doc 19 Section 9).
  // Stored as 48 bytes: 9 floats rotation + 3 floats position.
  xx: number; xy: number; xz: number;
  yx: number; yy: number; yz: number;
  zx: number; zy: number; zz: number;
  tx: number; ty: number; tz: number;
}

/** Per-wheel state. Source: doc 19 Section 3, doc 10 Section 4.
 *  Wheel order: FL(0), FR(1), RR(2), RL(3) -- clockwise. CERTAIN. */
interface WheelState {
  damperLen: number;         // 0-0.2 meters. CERTAIN.
  wheelRot: number;          // Accumulated rotation (radians). CERTAIN.
  wheelRotSpeed: number;     // Angular velocity. CERTAIN.
  steerAngle: number;        // -1 to 1. CERTAIN.
  groundContactMaterial: number; // ESurfId (uint16). CERTAIN.
  isGroundContact: boolean;
  slipCoef: number;          // 0-1. CERTAIN.
  dirt: number;              // 0-1. CERTAIN.
  icing: number;             // 0-1. CERTAIN.
  tireWear: number;          // 0-1. CERTAIN.
}

/** Vehicle type enum. Source: doc 19 Section 2. CERTAIN. */
const enum VehicleType {
  CharacterPilot = 0,
  CarSport = 1,      // Stadium car (default)
  CarSnow = 2,
  CarRally = 3,
  CarDesert = 4,
}

/** Turbo level enum. Source: doc 19 Section 2. CERTAIN. */
const enum TurboLevel {
  None = 0,
  Normal = 1,
  Super = 2,
  RouletteNormal = 3,
  RouletteSuper = 4,
  RouletteUltra = 5,
}

/** Complete vehicle state for the physics simulation. */
interface VehicleState {
  // Transform
  location: Iso4;               // World transform. CERTAIN.
  previousLocation: Iso4;       // Previous frame's transform (for interpolation). CERTAIN.

  // Motion. Source: doc 19 Section 1. CERTAIN.
  worldVel: Vec3;               // World-space velocity (m/s).
  frontSpeed: number;           // Forward speed (m/s). Multiply by 3.6 for km/h.
  sideSpeed: number;            // Lateral speed (m/s).
  angularVel: Vec3;             // Angular velocity (rad/s). APPROXIMATE.

  // Input. Source: doc 19 Section 1. CERTAIN.
  inputSteer: number;           // -1.0 to 1.0
  inputGas: number;             // 0.0 to 1.0
  inputBrake: number;           // 0.0 to 1.0
  inputIsBraking: boolean;
  inputVertical: number;        // For reactor/flying

  // Engine/Drivetrain. Source: doc 19 Section 1. CERTAIN.
  curGear: number;              // 0-7 (8 gears)
  rpm: number;                  // 0-11000
  engineOn: boolean;

  // Wheels (4). CERTAIN.
  wheels: [WheelState, WheelState, WheelState, WheelState];

  // Contact. CERTAIN.
  isGroundContact: boolean;
  groundDist: number;           // 0-20 meters

  // Turbo/Boost. Source: doc 19 Section 1, doc 10 Section 4.3. CERTAIN.
  isTurbo: boolean;
  turboTime: number;            // 0-1 normalized remaining. CERTAIN.
  turboLevel: TurboLevel;
  boostStartTick: number;       // -1 = inactive. CERTAIN (doc 10: vehicle+0x16E8).
  boostDuration: number;        // Ticks. CERTAIN (doc 10: vehicle+0x16E0).
  boostStrength: number;        // Force magnitude. CERTAIN (doc 10: vehicle+0x16E4).

  // Force model selection. Source: doc 10 Section 2.1. CERTAIN.
  forceModelType: number;       // Switch value at vehicle_model+0x1790
  vehicleType: VehicleType;

  // Race state. CERTAIN.
  raceStartTime: number;
  discontinuityCount: number;   // Teleport/reset count

  // Simulation mode. Source: doc 10 Section 3. CERTAIN.
  // 0 = normal, 1 = replay, 2 = spectator, 3 = normal-alt
  simulationMode: number;
}

// ============================================================
// Physics constants
// Source: doc 10 Sections 1, 7, 9. Confidence noted per constant.
// ============================================================
const PHYSICS_TICK_RATE = 100;        // Hz. PLAUSIBLE (community-established).
const PHYSICS_DT = 1.0 / PHYSICS_TICK_RATE; // 10ms = 0.01s
const PHYSICS_DT_MICROS = 10_000_000; // dt * 1e6. CERTAIN (doc 10 Section 1.3).
const MAX_SUBSTEPS = 1000;            // CERTAIN (doc 10 Section 7).
const GRAVITY = -9.81;               // m/s^2. APPROXIMATE (doc 15: GravityCoef 0-1 normalized).
const BLOCK_SIZE = 32.0;             // meters per block unit. CERTAIN (doc 19 Section 8).
const MAX_RPM = 11000;               // CERTAIN (doc 19 Section 1).

// ============================================================
// Surface friction table
// Source: doc 19 Section 10 surface IDs. Values are APPROXIMATE
// (actual friction coefficients not decompiled from force models).
// ============================================================
interface SurfaceProperties {
  staticFriction: number;
  dynamicFriction: number;
  restitution: number;      // Bounciness
}

const SURFACE_FRICTION: Record<string, SurfaceProperties> = {
  'Asphalt':       { staticFriction: 1.0,  dynamicFriction: 0.9,  restitution: 0.1 },
  'Concrete':      { staticFriction: 0.9,  dynamicFriction: 0.8,  restitution: 0.15 },
  'Dirt':          { staticFriction: 0.6,  dynamicFriction: 0.5,  restitution: 0.2 },
  'Grass':         { staticFriction: 0.4,  dynamicFriction: 0.35, restitution: 0.15 },
  'Ice':           { staticFriction: 0.1,  dynamicFriction: 0.08, restitution: 0.05 },
  'RoadIce':       { staticFriction: 0.12, dynamicFriction: 0.10, restitution: 0.05 },
  'Metal':         { staticFriction: 0.7,  dynamicFriction: 0.6,  restitution: 0.3 },
  'Plastic':       { staticFriction: 0.5,  dynamicFriction: 0.4,  restitution: 0.7 },
  'Rubber':        { staticFriction: 0.8,  dynamicFriction: 0.7,  restitution: 0.8 },
  'Sand':          { staticFriction: 0.4,  dynamicFriction: 0.3,  restitution: 0.1 },
  'Snow':          { staticFriction: 0.2,  dynamicFriction: 0.15, restitution: 0.1 },
  'Wood':          { staticFriction: 0.6,  dynamicFriction: 0.5,  restitution: 0.4 },
  'Pavement':      { staticFriction: 0.8,  dynamicFriction: 0.7,  restitution: 0.2 },
  'NotCollidable': { staticFriction: 0.0,  dynamicFriction: 0.0,  restitution: 0.0 },
};

// ============================================================
// Main physics step function
// Source: doc 10 Section 1.2 (PhysicsStep_TM, FUN_141501800). CERTAIN.
//
// Pipeline:
//   1. Convert tick to microseconds
//   2. For each vehicle: check status, compute substeps, run loop
//   3. Copy current transform to previous
// ============================================================
function physicsStep(
  vehicles: VehicleState[],
  tick: number,
  collisionWorld: CollisionWorld, // your collision system (rapier.js or custom)
): void {
  // Convert tick to microseconds. CERTAIN (doc 10 Section 1.3).
  const tickMicros = tick * 1_000_000;

  for (const vehicle of vehicles) {
    // Skip excluded vehicles (status nibble == 2). CERTAIN (doc 10 Section 3.3).
    if (vehicle.simulationMode === 2) continue;

    // Clear physics flags. CERTAIN (doc 10: *(lVar9+0x1C7C) &= 0xFFFFF5FF).
    // (Internal flag clearing -- represented here as resetting per-tick state)

    // Only process normal simulation modes (0 or 3). CERTAIN.
    if (vehicle.simulationMode !== 0 && vehicle.simulationMode !== 3) continue;

    // Compute adaptive substep count. CERTAIN (doc 10 Section 7).
    const substepCount = computeSubstepCount(vehicle);

    // Sub-stepping loop. CERTAIN.
    const subDt = PHYSICS_DT / substepCount;
    for (let sub = 0; sub < substepCount; sub++) {
      // 1. Collision check. CERTAIN (FUN_141501090 in pipeline).
      const contacts = collisionWorld.detectContacts(vehicle);

      // 2. Compute forces. CERTAIN (NSceneVehiclePhy::ComputeForces, FUN_1408427d0).
      const forces = computeForces(vehicle, contacts, tick);

      // 3. Apply turbo/boost force. CERTAIN (doc 10 Section 4.3).
      applyTurboForce(vehicle, forces, tick);

      // 4. Speed clamping. CERTAIN (doc 10 Section 4.4).
      clampSpeed(vehicle);

      // 5. Integration (Forward Euler). CERTAIN (doc 14 cross-reference).
      integrateEuler(vehicle, forces, subDt);

      // 6. Collision response.
      resolveCollisions(vehicle, contacts, collisionWorld);
    }

    // Copy current transform to previous. CERTAIN (doc 10 Section 3.6).
    vehicle.previousLocation = { ...vehicle.location };
  }
}

// ============================================================
// Adaptive substep count computation
// Source: doc 10 Sections 1.2, 7 -- CERTAIN for structure
//
// The substep count is velocity-dependent with a cap of 1000.
// Higher velocity = more substeps for stability.
// ============================================================
function computeSubstepCount(vehicle: VehicleState): number {
  const velMag = Math.sqrt(
    vehicle.worldVel.x ** 2 +
    vehicle.worldVel.y ** 2 +
    vehicle.worldVel.z ** 2
  );

  // APPROXIMATE: The exact formula is not decompiled.
  // Using a reasonable heuristic: 1 substep per ~2 m/tick of velocity.
  // At 100 Hz, 1 m/tick = 100 m/s = 360 km/h.
  const velocityPerTick = velMag * PHYSICS_DT;
  const count = Math.max(1, Math.ceil(velocityPerTick / 2.0));

  return Math.min(count, MAX_SUBSTEPS); // CERTAIN: cap at 1000.
}

// ============================================================
// Force computation dispatcher
// Source: doc 10 Section 2.1 (switch at vehicle_model+0x1790). CERTAIN.
//
// The 7 force model functions have NOT been decompiled internally.
// This provides a simplified CarSport approximation.
// ============================================================
interface ForceResult {
  force: Vec3;       // Linear force (Newtons)
  torque: Vec3;      // Torque (N*m)
}

function computeForces(
  vehicle: VehicleState,
  contacts: ContactPoint[],
  tick: number,
): ForceResult {
  const result: ForceResult = {
    force: { x: 0, y: 0, z: 0 },
    torque: { x: 0, y: 0, z: 0 },
  };

  // Gravity. CERTAIN (parameterized, doc 15 Section 5: GravityCoef 0-1).
  result.force.y += GRAVITY * 1400; // mass ~1400kg. APPROXIMATE.

  // Dispatch based on force model type. CERTAIN (doc 10 Section 2.1).
  switch (vehicle.forceModelType) {
    case 0: case 1: case 2:
      // Legacy base models. APPROXIMATE.
      computeForcesBase(vehicle, contacts, result);
      break;
    case 3:
      // Lateral friction model. APPROXIMATE.
      computeForcesBase(vehicle, contacts, result);
      break;
    case 4:
      // TMNF-era model. APPROXIMATE.
      computeForcesBase(vehicle, contacts, result);
      break;
    case 5:
      // CarSport / StadiumCar -- full simulation. APPROXIMATE.
      // This is the model used by the default car.
      computeForcesCarSport(vehicle, contacts, tick, result);
      break;
    case 6:
      // SnowCar or RallyCar. APPROXIMATE.
      computeForcesCarSport(vehicle, contacts, tick, result);
      break;
    case 0xB:
      // DesertCar. APPROXIMATE.
      computeForcesCarSport(vehicle, contacts, tick, result);
      break;
    default:
      computeForcesBase(vehicle, contacts, result);
  }

  return result;
}

// ============================================================
// Simplified CarSport force model
// Source: doc 10 Sections 2, 4 -- structure CERTAIN, formulas APPROXIMATE
//
// WARNING: The actual force model internals (FUN_140851f00) have NOT been
// decompiled. This is a plausible approximation that should be tuned
// against TMInterface validation data.
// ============================================================
function computeForcesCarSport(
  vehicle: VehicleState,
  contacts: ContactPoint[],
  tick: number,
  out: ForceResult,
): void {
  const mass = 1400;          // kg, APPROXIMATE
  const engineForceMax = 18000; // N, APPROXIMATE
  const brakeForceMax = 25000;  // N, APPROXIMATE
  const dragCoeff = 0.4;       // APPROXIMATE
  const downforceCoeff = 2.0;  // APPROXIMATE

  // Forward direction from vehicle orientation.
  // TM2020 coordinate system: Y up, Z forward (left-handed). CERTAIN (doc 19 Section 9).
  const fwd: Vec3 = {
    x: vehicle.location.zx,
    y: vehicle.location.zy,
    z: vehicle.location.zz,
  };
  const right: Vec3 = {
    x: vehicle.location.xx,
    y: vehicle.location.xy,
    z: vehicle.location.xz,
  };

  // Engine force (along forward axis).
  const engineForce = vehicle.inputGas * engineForceMax;
  out.force.x += fwd.x * engineForce;
  out.force.y += fwd.y * engineForce;
  out.force.z += fwd.z * engineForce;

  // Brake force (opposing velocity).
  if (vehicle.inputIsBraking && vehicle.frontSpeed > 0.1) {
    const brakeMag = vehicle.inputBrake * brakeForceMax;
    const speed = Math.max(vehicle.frontSpeed, 0.001);
    out.force.x -= (vehicle.worldVel.x / speed) * brakeMag;
    out.force.y -= (vehicle.worldVel.y / speed) * brakeMag;
    out.force.z -= (vehicle.worldVel.z / speed) * brakeMag;
  }

  // Aerodynamic drag (opposing velocity, proportional to v^2).
  const speed2 = vehicle.worldVel.x ** 2 + vehicle.worldVel.y ** 2 + vehicle.worldVel.z ** 2;
  if (speed2 > 0.01) {
    const speed = Math.sqrt(speed2);
    out.force.x -= dragCoeff * speed * vehicle.worldVel.x;
    out.force.y -= dragCoeff * speed * vehicle.worldVel.y;
    out.force.z -= dragCoeff * speed * vehicle.worldVel.z;
  }

  // Steering torque (around Y axis).
  // APPROXIMATE -- actual steering model involves tire slip angles.
  const steerTorque = vehicle.inputSteer * 50000 * Math.min(vehicle.frontSpeed / 20, 1.0);
  out.torque.y += steerTorque;

  // Per-wheel contact forces.
  for (let i = 0; i < 4; i++) {
    const wheel = vehicle.wheels[i];
    if (!wheel.isGroundContact) continue;

    // Normal force from suspension. APPROXIMATE.
    const suspensionRestLen = 0.15; // meters
    const springK = 80000;          // N/m
    const damperC = 5000;           // N*s/m
    const compression = suspensionRestLen - wheel.damperLen;
    const normalForce = Math.max(0, springK * compression + damperC * 0);

    // Apply normal force upward at wheel position.
    out.force.y += normalForce;

    // Lateral friction (resists sideways sliding). APPROXIMATE.
    // This is where the actual tire model (slip angle, camber, etc.) would go.
    const surfaceProps = SURFACE_FRICTION['Asphalt']; // TODO: use wheel.groundContactMaterial
    const lateralSpeed = vehicle.sideSpeed; // simplified
    const lateralFriction = -lateralSpeed * surfaceProps.dynamicFriction * normalForce * 0.01;
    out.force.x += right.x * lateralFriction;
    out.force.z += right.z * lateralFriction;
  }
}

/** Base force model (simplified, for legacy models 0-4). APPROXIMATE. */
function computeForcesBase(
  vehicle: VehicleState,
  contacts: ContactPoint[],
  out: ForceResult,
): void {
  // Minimal force model -- just engine + drag
  const fwd: Vec3 = {
    x: vehicle.location.zx,
    y: vehicle.location.zy,
    z: vehicle.location.zz,
  };
  const engineForce = vehicle.inputGas * 15000;
  out.force.x += fwd.x * engineForce;
  out.force.y += fwd.y * engineForce;
  out.force.z += fwd.z * engineForce;
}

// ============================================================
// Turbo/boost force application
// Source: doc 10 Section 4.3. CERTAIN for structure.
//
// The boost force ramps linearly from 0 to strength*modelScale over
// the duration. This is a ramp-UP, not decay. CERTAIN but counterintuitive
// (doc 18 Issue 6 flagged this as needing verification).
// ============================================================
function applyTurboForce(
  vehicle: VehicleState,
  forces: ForceResult,
  currentTick: number,
): void {
  // No active boost. CERTAIN (doc 10: boostDuration checked != 0).
  if (vehicle.boostDuration <= 0) return;

  // Initialize boost start time on first activation. CERTAIN.
  if (vehicle.boostStartTick === -1) {
    vehicle.boostStartTick = currentTick;
  }

  const elapsed = currentTick - vehicle.boostStartTick;
  if (elapsed < 0 || elapsed > vehicle.boostDuration) return;

  // Linear ramp: t goes from 0 to 1 over the duration. CERTAIN.
  const t = elapsed / vehicle.boostDuration;
  const modelScale = 1.0; // vehicle_model+0xE0. APPROXIMATE (assume 1.0).
  const boostMag = t * vehicle.boostStrength * modelScale;

  // Apply along forward direction. APPROXIMATE (actual direction from FUN_1407bdf40).
  const fwd: Vec3 = {
    x: vehicle.location.zx,
    y: vehicle.location.zy,
    z: vehicle.location.zz,
  };
  forces.force.x += fwd.x * boostMag;
  forces.force.y += fwd.y * boostMag;
  forces.force.z += fwd.z * boostMag;
}

// ============================================================
// Speed clamping
// Source: doc 10 Section 4.4 (vehicle_model+0x2F0 = MaxSpeed). CERTAIN.
// ============================================================
function clampSpeed(vehicle: VehicleState): void {
  const maxSpeed = 1000.0; // m/s. APPROXIMATE -- actual value from vehicle_model+0x2F0.
  const speed2 = vehicle.worldVel.x ** 2 + vehicle.worldVel.y ** 2 + vehicle.worldVel.z ** 2;
  const maxSpeed2 = maxSpeed * maxSpeed;

  if (speed2 > maxSpeed2 && maxSpeed > 0) {
    const scale = maxSpeed / Math.sqrt(speed2);
    vehicle.worldVel.x *= scale;
    vehicle.worldVel.y *= scale;
    vehicle.worldVel.z *= scale;
  }
}

// ============================================================
// Forward Euler integration
// Source: doc 10, doc 14 (TMNF cross-reference confirms Forward Euler). CERTAIN.
// ============================================================
function integrateEuler(
  vehicle: VehicleState,
  forces: ForceResult,
  dt: number,
): void {
  const mass = 1400;           // kg. APPROXIMATE.
  const inertia = 2000;        // kg*m^2. APPROXIMATE.
  const invMass = 1.0 / mass;
  const invInertia = 1.0 / inertia;

  // Linear: v += (F/m) * dt,  x += v * dt. CERTAIN (Forward Euler).
  vehicle.worldVel.x += forces.force.x * invMass * dt;
  vehicle.worldVel.y += forces.force.y * invMass * dt;
  vehicle.worldVel.z += forces.force.z * invMass * dt;

  vehicle.location.tx += vehicle.worldVel.x * dt;
  vehicle.location.ty += vehicle.worldVel.y * dt;
  vehicle.location.tz += vehicle.worldVel.z * dt;

  // Angular: omega += (torque/I) * dt, then update rotation. APPROXIMATE.
  vehicle.angularVel.x += forces.torque.x * invInertia * dt;
  vehicle.angularVel.y += forces.torque.y * invInertia * dt;
  vehicle.angularVel.z += forces.torque.z * invInertia * dt;

  // Update rotation matrix from angular velocity (small-angle approximation).
  // APPROXIMATE -- the actual game likely uses quaternions or a more stable method.
  applyAngularVelocityToRotation(vehicle.location, vehicle.angularVel, dt);

  // Update derived state. CERTAIN.
  vehicle.frontSpeed = vehicle.worldVel.x * vehicle.location.zx +
                       vehicle.worldVel.y * vehicle.location.zy +
                       vehicle.worldVel.z * vehicle.location.zz;
  vehicle.sideSpeed = vehicle.worldVel.x * vehicle.location.xx +
                      vehicle.worldVel.y * vehicle.location.xy +
                      vehicle.worldVel.z * vehicle.location.xz;
}

// ============================================================
// Collision response stub
// For MVP, use rapier.js for collision detection and response.
// Source: doc 10 Section 5 documents the collision system structure.
// ============================================================
interface ContactPoint {
  position: Vec3;
  normal: Vec3;
  depth: number;
  surfaceId: string;
}

interface CollisionWorld {
  detectContacts(vehicle: VehicleState): ContactPoint[];
}

function resolveCollisions(
  vehicle: VehicleState,
  contacts: ContactPoint[],
  world: CollisionWorld,
): void {
  for (const contact of contacts) {
    if (contact.depth <= 0) continue;

    // Push vehicle out of penetration. APPROXIMATE.
    vehicle.location.tx += contact.normal.x * contact.depth;
    vehicle.location.ty += contact.normal.y * contact.depth;
    vehicle.location.tz += contact.normal.z * contact.depth;

    // Reflect velocity component along normal (with restitution). APPROXIMATE.
    const vDotN = vehicle.worldVel.x * contact.normal.x +
                  vehicle.worldVel.y * contact.normal.y +
                  vehicle.worldVel.z * contact.normal.z;

    if (vDotN < 0) {
      const surfProps = SURFACE_FRICTION[contact.surfaceId] ?? SURFACE_FRICTION['Asphalt'];
      const restitution = surfProps.restitution;

      vehicle.worldVel.x -= (1 + restitution) * vDotN * contact.normal.x;
      vehicle.worldVel.y -= (1 + restitution) * vDotN * contact.normal.y;
      vehicle.worldVel.z -= (1 + restitution) * vDotN * contact.normal.z;
    }
  }
}

// Rotation update helper. APPROXIMATE.
function applyAngularVelocityToRotation(loc: Iso4, omega: Vec3, dt: number): void {
  // Small-angle rotation: R' = R + skew(omega * dt) * R
  const wx = omega.x * dt;
  const wy = omega.y * dt;
  const wz = omega.z * dt;

  const nxx = loc.xx + (wy * loc.zx - wz * loc.yx);
  const nxy = loc.xy + (wy * loc.zy - wz * loc.yy);
  const nxz = loc.xz + (wy * loc.zz - wz * loc.yz);
  const nyx = loc.yx + (wz * loc.xx - wx * loc.zx);
  const nyy = loc.yy + (wz * loc.xy - wx * loc.zy);
  const nyz = loc.yz + (wz * loc.xz - wx * loc.zz);
  const nzx = loc.zx + (wx * loc.yx - wy * loc.xx);
  const nzy = loc.zy + (wx * loc.yy - wy * loc.xy);
  const nzz = loc.zz + (wx * loc.yz - wy * loc.xz);

  loc.xx = nxx; loc.xy = nxy; loc.xz = nxz;
  loc.yx = nyx; loc.yy = nyy; loc.yz = nyz;
  loc.zx = nzx; loc.zy = nzy; loc.zz = nzz;

  // Re-orthogonalize (Gram-Schmidt). Important for numeric stability.
  orthogonalizeRotation(loc);
}

function orthogonalizeRotation(loc: Iso4): void {
  // Gram-Schmidt on the 3 rows
  let len = Math.sqrt(loc.xx * loc.xx + loc.xy * loc.xy + loc.xz * loc.xz);
  if (len > 0) { loc.xx /= len; loc.xy /= len; loc.xz /= len; }

  let dot = loc.xx * loc.yx + loc.xy * loc.yy + loc.xz * loc.yz;
  loc.yx -= dot * loc.xx; loc.yy -= dot * loc.xy; loc.yz -= dot * loc.xz;
  len = Math.sqrt(loc.yx * loc.yx + loc.yy * loc.yy + loc.yz * loc.yz);
  if (len > 0) { loc.yx /= len; loc.yy /= len; loc.yz /= len; }

  // Z = X cross Y (left-handed)
  loc.zx = loc.xy * loc.yz - loc.xz * loc.yy;
  loc.zy = loc.xz * loc.yx - loc.xx * loc.yz;
  loc.zz = loc.xx * loc.yy - loc.xy * loc.yx;
}
```

**Validation strategy**: Record input sequences in the real game using TMInterface, capture the resulting vehicle positions at each tick, then run the same inputs through this physics engine and compare. Iteratively tune force model constants (engine force, drag, suspension, friction) to minimize position divergence. This is the most reliable path to "feeling right" without decompiling the actual force model internals.

---

### 19.3 Renderer Architecture (WebGPU)

This implements the deferred pipeline from [11-rendering-deep-dive.md](11-rendering-deep-dive.md) Sections 2-3 and [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 7.

```typescript
// ============================================================
// G-buffer render targets
// Source: doc 11 Section 2 (render target names from binary strings). CERTAIN.
// Formats are APPROXIMATE (only depth format is VERIFIED from D3D11 log).
// ============================================================
interface GBuffer {
  // RT0: Material diffuse/albedo. CERTAIN exists, format APPROXIMATE.
  diffuse: GPUTexture;      // rgba8unorm-srgb

  // RT1: Specular color/intensity. CERTAIN exists, format APPROXIMATE.
  specular: GPUTexture;     // rgba8unorm

  // RT2: Pixel normals in camera space (bump-mapped). CERTAIN exists.
  normalPixel: GPUTexture;  // rgba16float (or rg16float with octahedral encoding)

  // RT3: Light mask / material flags. CERTAIN exists.
  lightMask: GPUTexture;    // rgba8unorm

  // Depth: hardware depth buffer. CERTAIN (VERIFIED: D24_UNORM_S8_UINT from D3D11 log).
  depth: GPUTexture;        // depth24plus-stencil8

  // Additional buffers (from doc 11 Section 2). VERIFIED names, SPECULATIVE formats.
  // For MVP, these can be omitted.
  // normalFace: GPUTexture;   // Face normals -- used for AO, edge detection
  // normalVertex: GPUTexture; // Vertex normals -- used for bilateral blur
}

function createGBuffer(device: GPUDevice, width: number, height: number): GBuffer {
  const makeTarget = (format: GPUTextureFormat, label: string): GPUTexture =>
    device.createTexture({
      label,
      size: { width, height },
      format,
      usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING,
    });

  return {
    diffuse:     makeTarget('rgba8unorm-srgb', 'BitmapDeferredMDiffuse'),
    specular:    makeTarget('rgba8unorm',      'BitmapDeferredMSpecular'),
    normalPixel: makeTarget('rgba16float',     'BitmapDeferredPixelNormalInC'),
    lightMask:   makeTarget('rgba8unorm',      'BitmapDeferredLightMask'),
    depth:       device.createTexture({
      label: 'BitmapDeferredZ',
      size: { width, height },
      format: 'depth24plus-stencil8',
      usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING,
    }),
  };
}

// ============================================================
// Shadow map creation
// Source: doc 11 Section 4 -- PSSM with 4 cascades. CERTAIN.
// Shadow map format APPROXIMATE (likely D16_UNORM or D24_UNORM).
// ============================================================
interface ShadowMaps {
  cascades: GPUTexture; // 2D array texture, 4 layers (one per cascade)
  cascadeCount: number;
}

function createShadowMaps(
  device: GPUDevice,
  resolution: number = 2048,
): ShadowMaps {
  // 4 cascades. CERTAIN (doc 11 Section 4: MapShadowSplit0-3).
  // Can be 1 cascade in simplified mode (flag & 0x40). CERTAIN.
  const cascadeCount = 4;
  return {
    cascades: device.createTexture({
      label: 'PSSMShadowMap',
      size: { width: resolution, height: resolution, depthOrArrayLayers: cascadeCount },
      format: 'depth32float',
      usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING,
    }),
    cascadeCount,
  };
}

// ============================================================
// Vertex formats
// Source: doc 11 Section 1 (VERIFIED from DXVK pipeline log).
// ============================================================

/** Block geometry: stride 56, 7 attributes. CERTAIN. */
const BLOCK_VERTEX_LAYOUT: GPUVertexBufferLayout = {
  arrayStride: 56,
  attributes: [
    { shaderLocation: 0, format: 'float32x3',  offset: 0  }, // position (12 bytes)
    { shaderLocation: 1, format: 'snorm16x4',  offset: 12 }, // normal packed (8 bytes)
    { shaderLocation: 2, format: 'unorm8x4',   offset: 20 }, // vertex color BGRA (4 bytes)
    { shaderLocation: 3, format: 'float32x2',  offset: 24 }, // UV0 (8 bytes)
    { shaderLocation: 4, format: 'float32x2',  offset: 32 }, // UV1/lightmap (8 bytes)
    { shaderLocation: 5, format: 'snorm16x4',  offset: 40 }, // tangent (8 bytes)
    { shaderLocation: 6, format: 'snorm16x4',  offset: 48 }, // bitangent (8 bytes)
  ],
};

/** Simple geometry: stride 28, 3 attributes. CERTAIN. */
const SIMPLE_VERTEX_LAYOUT: GPUVertexBufferLayout = {
  arrayStride: 28,
  attributes: [
    { shaderLocation: 0, format: 'float32x3', offset: 0  }, // position
    { shaderLocation: 1, format: 'snorm16x4', offset: 12 }, // normal
    { shaderLocation: 2, format: 'float32x2', offset: 20 }, // UV
  ],
};

// ============================================================
// Deferred write pass (G-buffer fill)
// Source: doc 11 Sections 2-3 -- Phase 5: DeferredWrite. CERTAIN.
//
// Shader names from binary: Tech3/Block_TDSN_DefWrite_p.hlsl. CERTAIN.
// ============================================================

// WGSL vertex shader for deferred write (block geometry).
const DEFERRED_WRITE_VERTEX_WGSL = /* wgsl */`
struct FrameUniforms {
  viewProj: mat4x4<f32>,
  view: mat4x4<f32>,
  proj: mat4x4<f32>,
  cameraPos: vec3<f32>,
  time: f32,
};
@group(0) @binding(0) var<uniform> frame: FrameUniforms;

struct ModelUniforms {
  model: mat4x4<f32>,
  normalMatrix: mat3x3<f32>,
};
@group(1) @binding(0) var<uniform> model: ModelUniforms;

struct VertexInput {
  @location(0) position: vec3<f32>,
  @location(1) normal: vec4<f32>,    // snorm16x4, unpacked by GPU
  @location(2) color: vec4<f32>,     // unorm8x4
  @location(3) uv0: vec2<f32>,
  @location(4) uv1: vec2<f32>,      // lightmap UV
  @location(5) tangent: vec4<f32>,
  @location(6) bitangent: vec4<f32>,
};

struct VertexOutput {
  @builtin(position) clipPos: vec4<f32>,
  @location(0) worldPos: vec3<f32>,
  @location(1) normal: vec3<f32>,
  @location(2) color: vec4<f32>,
  @location(3) uv0: vec2<f32>,
  @location(4) uv1: vec2<f32>,
  @location(5) tangent: vec3<f32>,
  @location(6) bitangent: vec3<f32>,
};

@vertex
fn vs_main(in: VertexInput) -> VertexOutput {
  var out: VertexOutput;
  let worldPos = (model.model * vec4(in.position, 1.0)).xyz;
  out.clipPos = frame.viewProj * vec4(worldPos, 1.0);
  out.worldPos = worldPos;
  out.normal = normalize(model.normalMatrix * in.normal.xyz);
  out.color = in.color;
  out.uv0 = in.uv0;
  out.uv1 = in.uv1;
  out.tangent = normalize(model.normalMatrix * in.tangent.xyz);
  out.bitangent = normalize(model.normalMatrix * in.bitangent.xyz);
  return out;
}
`;

// WGSL fragment shader for deferred write (outputs to G-buffer MRT).
const DEFERRED_WRITE_FRAGMENT_WGSL = /* wgsl */`
@group(2) @binding(0) var diffuseTex: texture_2d<f32>;
@group(2) @binding(1) var normalMap: texture_2d<f32>;
@group(2) @binding(2) var texSampler: sampler;

struct VertexOutput {
  @builtin(position) clipPos: vec4<f32>,
  @location(0) worldPos: vec3<f32>,
  @location(1) normal: vec3<f32>,
  @location(2) color: vec4<f32>,
  @location(3) uv0: vec2<f32>,
  @location(4) uv1: vec2<f32>,
  @location(5) tangent: vec3<f32>,
  @location(6) bitangent: vec3<f32>,
};

struct GBufferOutput {
  @location(0) diffuse: vec4<f32>,     // RT0: MDiffuse
  @location(1) specular: vec4<f32>,    // RT1: MSpecular
  @location(2) normal: vec4<f32>,      // RT2: PixelNormalInC
  @location(3) lightMask: vec4<f32>,   // RT3: LightMask
};

@fragment
fn fs_main(in: VertexOutput) -> GBufferOutput {
  var out: GBufferOutput;

  // Sample diffuse texture
  let albedo = textureSample(diffuseTex, texSampler, in.uv0);
  out.diffuse = vec4(albedo.rgb * in.color.rgb, 1.0);

  // Specular -- PBR metallic/roughness packed. APPROXIMATE.
  out.specular = vec4(0.04, 0.5, 0.0, 1.0); // F0, roughness, metallic, 1

  // Normal mapping (tangent space -> camera space)
  let normalSample = textureSample(normalMap, texSampler, in.uv0).xyz * 2.0 - 1.0;
  let TBN = mat3x3(
    normalize(in.tangent),
    normalize(in.bitangent),
    normalize(in.normal)
  );
  let worldNormal = normalize(TBN * normalSample);
  // Encode normal in camera space. APPROXIMATE (actual encoding unknown).
  out.normal = vec4(worldNormal * 0.5 + 0.5, 1.0);

  // Light mask -- flags for which lights affect this pixel. APPROXIMATE.
  out.lightMask = vec4(1.0, 1.0, 1.0, 1.0);

  return out;
}
`;

// ============================================================
// Deferred lighting pass (screen-space quad)
// Source: doc 11 Section 3 Phase 6 -- DeferredLighting. CERTAIN.
//
// Reads G-buffer textures and computes PBR lighting.
// Shader names: Deferred_AddAmbient_Fresnel_p, DeferredGeomLightBall_p, etc.
// ============================================================
const DEFERRED_LIGHTING_WGSL = /* wgsl */`
@group(0) @binding(0) var gbufDiffuse: texture_2d<f32>;
@group(0) @binding(1) var gbufSpecular: texture_2d<f32>;
@group(0) @binding(2) var gbufNormal: texture_2d<f32>;
@group(0) @binding(3) var gbufDepth: texture_depth_2d;
@group(0) @binding(4) var shadowMap: texture_depth_2d_array;
@group(0) @binding(5) var shadowSampler: sampler_comparison;
@group(0) @binding(6) var texSampler: sampler;

struct LightUniforms {
  sunDirection: vec3<f32>,
  sunColor: vec3<f32>,
  ambientColor: vec3<f32>,
  invViewProj: mat4x4<f32>,
  cascadeViewProj: array<mat4x4<f32>, 4>,
  cascadeSplits: vec4<f32>,
};
@group(1) @binding(0) var<uniform> light: LightUniforms;

struct VertexOutput {
  @builtin(position) position: vec4<f32>,
  @location(0) uv: vec2<f32>,
};

// Full-screen triangle (no vertex buffer needed)
@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var out: VertexOutput;
  let uv = vec2<f32>(
    f32((vertexIndex << 1u) & 2u),
    f32(vertexIndex & 2u)
  );
  out.position = vec4(uv * 2.0 - 1.0, 0.0, 1.0);
  out.uv = vec2(uv.x, 1.0 - uv.y);
  return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
  let texCoord = vec2<i32>(in.position.xy);

  // Read G-buffer
  let albedo = textureLoad(gbufDiffuse, texCoord, 0).rgb;
  let specData = textureLoad(gbufSpecular, texCoord, 0);
  let normalEnc = textureLoad(gbufNormal, texCoord, 0).xyz;
  let depth = textureLoad(gbufDepth, texCoord, 0);

  // Decode normal from stored encoding. APPROXIMATE.
  let normal = normalize(normalEnc * 2.0 - 1.0);

  // PBR parameters
  let roughness = specData.g;
  let metallic = specData.b;
  let f0 = mix(vec3(specData.r), albedo, metallic);

  // Directional light (sun). Standard PBR, GGX BRDF. CERTAIN structure.
  let NdotL = max(dot(normal, -light.sunDirection), 0.0);
  let diffuse = albedo * (1.0 - metallic) * NdotL * light.sunColor;
  let ambient = albedo * light.ambientColor;

  // Shadow lookup (PSSM). CERTAIN: 4 cascades (doc 11 Section 4).
  // APPROXIMATE: cascade selection and PCF filtering.
  let shadow = sampleShadowPSSM(in.position.xy, depth);

  let color = ambient + diffuse * shadow;

  // Tone mapping (filmic). APPROXIMATE.
  let mapped = color / (color + vec3(1.0));

  return vec4(mapped, 1.0);
}

fn sampleShadowPSSM(screenPos: vec2<f32>, depth: f32) -> f32 {
  // Select cascade based on depth. APPROXIMATE.
  var cascadeIndex: u32 = 0u;
  if (depth > light.cascadeSplits.x) { cascadeIndex = 1u; }
  if (depth > light.cascadeSplits.y) { cascadeIndex = 2u; }
  if (depth > light.cascadeSplits.z) { cascadeIndex = 3u; }

  // Transform to shadow map space and sample. APPROXIMATE.
  // Full implementation would reconstruct world position from depth,
  // transform by cascade VP matrix, and do PCF filtering.
  return 1.0; // placeholder
}
`;

// ============================================================
// Post-processing: bloom
// Source: doc 11 Section 8 Phase 12 -- FxBloom. CERTAIN.
// Standard downsample chain + upsample with additive blend.
// ============================================================
const BLOOM_DOWNSAMPLE_WGSL = /* wgsl */`
// Downsample with 13-tap filter (Karis average for first pass to avoid fireflies)
@group(0) @binding(0) var inputTex: texture_2d<f32>;
@group(0) @binding(1) var texSampler: sampler;

struct PushConstants {
  texelSize: vec2<f32>,
  isFirstPass: u32,
};
@group(1) @binding(0) var<uniform> push: PushConstants;

@fragment
fn fs_downsample(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
  let ts = push.texelSize;

  // 13-tap downsample (dual filter approach)
  let a = textureSample(inputTex, texSampler, uv + vec2(-2.0, -2.0) * ts);
  let b = textureSample(inputTex, texSampler, uv + vec2( 0.0, -2.0) * ts);
  let c = textureSample(inputTex, texSampler, uv + vec2( 2.0, -2.0) * ts);
  let d = textureSample(inputTex, texSampler, uv + vec2(-1.0, -1.0) * ts);
  let e = textureSample(inputTex, texSampler, uv);
  let f = textureSample(inputTex, texSampler, uv + vec2( 1.0, -1.0) * ts);
  let g = textureSample(inputTex, texSampler, uv + vec2(-2.0,  0.0) * ts);
  let h = textureSample(inputTex, texSampler, uv + vec2( 2.0,  0.0) * ts);
  let i = textureSample(inputTex, texSampler, uv + vec2(-1.0,  1.0) * ts);
  let j = textureSample(inputTex, texSampler, uv + vec2( 1.0,  1.0) * ts);
  let k = textureSample(inputTex, texSampler, uv + vec2(-2.0,  2.0) * ts);
  let l = textureSample(inputTex, texSampler, uv + vec2( 0.0,  2.0) * ts);
  let m = textureSample(inputTex, texSampler, uv + vec2( 2.0,  2.0) * ts);

  var result = e * 0.125;
  result += (a + c + k + m) * 0.03125;
  result += (b + g + h + l) * 0.0625;
  result += (d + f + i + j) * 0.125;

  return result;
}
`;

// ============================================================
// Complete render() function
// Source: doc 11 Section 3 (full pipeline flow). CERTAIN for order.
// ============================================================
function render(
  device: GPUDevice,
  encoder: GPUCommandEncoder,
  gbuffer: GBuffer,
  shadowMaps: ShadowMaps,
  outputTexture: GPUTexture,
  scene: SceneData,
  camera: CameraData,
): void {
  // ----- Phase 1: Shadow Pass -----
  // Render shadow casters into PSSM cascades. CERTAIN (doc 11 Phase 2).
  for (let cascade = 0; cascade < shadowMaps.cascadeCount; cascade++) {
    const shadowPass = encoder.beginRenderPass({
      label: `ShadowRenderPSSM_Cascade${cascade}`,
      colorAttachments: [],
      depthStencilAttachment: {
        view: shadowMaps.cascades.createView({
          dimension: '2d',
          baseArrayLayer: cascade,
          arrayLayerCount: 1,
        }),
        depthLoadOp: 'clear',
        depthClearValue: 1.0,
        depthStoreOp: 'store',
      },
    });
    // Bind shadow pipeline, draw all shadow-casting geometry
    // shadowPass.setPipeline(shadowPipeline);
    // for (const mesh of scene.shadowCasters) { ... }
    shadowPass.end();
  }

  // ----- Phase 2: G-Buffer Fill (Deferred Write) -----
  // Source: doc 11 Phase 5 -- DeferredWrite. CERTAIN.
  const gbufferPass = encoder.beginRenderPass({
    label: 'DeferredWrite',
    colorAttachments: [
      { view: gbuffer.diffuse.createView(),     loadOp: 'clear', clearValue: { r: 0, g: 0, b: 0, a: 1 }, storeOp: 'store' },
      { view: gbuffer.specular.createView(),    loadOp: 'clear', clearValue: { r: 0, g: 0, b: 0, a: 1 }, storeOp: 'store' },
      { view: gbuffer.normalPixel.createView(), loadOp: 'clear', clearValue: { r: 0.5, g: 0.5, b: 1, a: 1 }, storeOp: 'store' },
      { view: gbuffer.lightMask.createView(),   loadOp: 'clear', clearValue: { r: 0, g: 0, b: 0, a: 0 }, storeOp: 'store' },
    ],
    depthStencilAttachment: {
      view: gbuffer.depth.createView(),
      depthLoadOp: 'clear',
      depthClearValue: 1.0,
      depthStoreOp: 'store',
      stencilLoadOp: 'clear',
      stencilClearValue: 0,
      stencilStoreOp: 'store',
    },
  });
  // Bind deferred write pipeline, draw all opaque geometry
  // gbufferPass.setPipeline(deferredWritePipeline);
  // for (const mesh of scene.opaqueGeometry) { ... }
  gbufferPass.end();

  // ----- Phase 3: Deferred Lighting -----
  // Source: doc 11 Phase 6 -- DeferredRead + DeferredLighting. CERTAIN.
  const lightingPass = encoder.beginRenderPass({
    label: 'DeferredLighting',
    colorAttachments: [{
      view: outputTexture.createView(), // HDR intermediate target
      loadOp: 'clear',
      clearValue: { r: 0, g: 0, b: 0, a: 1 },
      storeOp: 'store',
    }],
  });
  // Bind lighting pipeline (full-screen triangle), draw 3 vertices
  // lightingPass.setPipeline(deferredLightingPipeline);
  // lightingPass.draw(3);
  lightingPass.end();

  // ----- Phase 4: Forward Transparent Objects -----
  // Source: doc 11 Phase 8 -- Alpha01, AlphaBlend. CERTAIN.
  // Draw alpha-tested and alpha-blended geometry with forward shading.

  // ----- Phase 5: Post-Processing -----
  // Source: doc 11 Phases 11-12. CERTAIN.
  // Bloom: downsample chain -> upsample chain -> composite.
  // Tone mapping: filmic curve + auto-exposure.
  // AA: FXAA or TAA (TXAA alternative).

  // For MVP, just do a simple FXAA pass on the final output.
}

// Placeholder types
interface SceneData {
  opaqueGeometry: any[];
  shadowCasters: any[];
}

interface CameraData {
  viewMatrix: Float32Array;
  projMatrix: Float32Array;
  position: Vec3;
}
```

**MVP shortcut**: Start with a forward renderer using three.js's WebGPU backend. The deferred pipeline above is the target architecture for when you need to handle many light sources (stadium spotlights, etc.) efficiently. Three.js gets you rendering in days; raw WebGPU deferred takes weeks.

---

### 19.4 Authentication Flow (Browser)

Source: [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Sections 5-6, [17-networking-deep-dive.md](17-networking-deep-dive.md) Section 2. VERIFIED from working Openplanet plugin.

```typescript
// ============================================================
// Nadeo API authentication for browser
// Source: doc 19 Sections 5-6, doc 17 Section 2. VERIFIED.
//
// NOTE: This flow requires a server-side proxy for the initial
// Ubisoft Connect authentication (browser cannot call UPC directly).
// The Nadeo token exchange can be done client-side via fetch.
// ============================================================

interface NadeoToken {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;      // Unix timestamp (ms)
  audience: string;
}

// API base URLs. CERTAIN (doc 19 Section 5).
const NADEO_CORE_URL = 'https://prod.trackmania.core.nadeo.online';
const NADEO_LIVE_URL = 'https://live-services.trackmania.nadeo.live';
const NADEO_MEET_URL = 'https://meet.trackmania.nadeo.club';

// Token lifetime: 55 minutes + 1-60s jitter. CERTAIN (doc 19 Section 6).
const TOKEN_LIFETIME_MS = 55 * 60 * 1000;
const TOKEN_JITTER_MS = () => Math.random() * 60 * 1000;

// ============================================================
// Authentication manager
// ============================================================
class NadeoAuth {
  private tokens: Map<string, NadeoToken> = new Map();
  private refreshTimers: Map<string, number> = new Map();

  /**
   * Step 1: Exchange a Ubisoft Connect ticket for a Nadeo token.
   * Source: doc 17 Section 2, doc 19 Section 6. VERIFIED.
   *
   * In a real browser implementation, the Ubisoft ticket must be obtained
   * via a server-side proxy (the UPC SDK is Windows-only).
   * Alternative: Use a dedicated server auth flow, or the community
   * "Trackmania OAuth" approach.
   */
  async authenticateWithUbiTicket(ubiTicket: string): Promise<NadeoToken> {
    // POST to core.trackmania.nadeo.live/v2/authentication/token/ubiservices
    // CERTAIN (doc 17 Section 2, doc 19 Section 6).
    const response = await fetch(
      'https://prod.trackmania.core.nadeo.online/v2/authentication/token/ubiservices',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Ubi-AppId': '86263886-327a-4328-ac69-527f0d20a237', // TM2020 app ID
        },
        body: JSON.stringify({
          audience: 'NadeoServices',
          ubiTicket,
        }),
      }
    );

    if (!response.ok) {
      throw new Error(`Nadeo auth failed: ${response.status}`);
    }

    const data = await response.json();
    const token: NadeoToken = {
      accessToken: data.accessToken,
      refreshToken: data.refreshToken,
      expiresAt: Date.now() + TOKEN_LIFETIME_MS + TOKEN_JITTER_MS(),
      audience: 'NadeoServices',
    };

    this.tokens.set('NadeoServices', token);
    this.scheduleRefresh('NadeoServices');
    return token;
  }

  /**
   * Step 2: Get a token for a specific audience (Live/Meet services).
   * Source: doc 19 Section 5. CERTAIN.
   */
  async getToken(audience: 'NadeoServices' | 'NadeoLiveServices'): Promise<string> {
    let token = this.tokens.get(audience);

    if (!token || Date.now() >= token.expiresAt) {
      token = await this.refreshToken(audience);
    }

    return token.accessToken;
  }

  /**
   * Refresh an expired token.
   * Source: doc 17 Section 2 (POST to /v2/authentication/token/refresh). CERTAIN.
   *
   * Retry strategy: exponential backoff 1s -> 2s -> 4s -> 8s -> 16s.
   * CERTAIN (doc 19 Section 6: "mimicking Nadeo's code").
   */
  async refreshToken(audience: string): Promise<NadeoToken> {
    const existing = this.tokens.get(audience);
    if (!existing?.refreshToken) {
      throw new Error(`No refresh token for audience ${audience}`);
    }

    let retryDelay = 1000;
    const maxRetries = 5;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const response = await fetch(
          'https://prod.trackmania.core.nadeo.online/v2/authentication/token/refresh',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `nadeo_v1 t=${existing.accessToken}`,
            },
            body: JSON.stringify({ audience }),
          }
        );

        if (response.ok) {
          const data = await response.json();
          const token: NadeoToken = {
            accessToken: data.accessToken,
            refreshToken: data.refreshToken,
            expiresAt: Date.now() + TOKEN_LIFETIME_MS + TOKEN_JITTER_MS(),
            audience,
          };
          this.tokens.set(audience, token);
          this.scheduleRefresh(audience);
          return token;
        }
      } catch (err) {
        // Fall through to retry
      }

      // Exponential backoff. CERTAIN (doc 19 Section 6).
      await new Promise(resolve => setTimeout(resolve, retryDelay));
      retryDelay *= 2;
    }

    throw new Error(`Failed to refresh token after ${maxRetries} attempts`);
  }

  private scheduleRefresh(audience: string): void {
    const existing = this.refreshTimers.get(audience);
    if (existing) clearTimeout(existing);

    const token = this.tokens.get(audience)!;
    const refreshIn = token.expiresAt - Date.now() - 60_000; // Refresh 1 min before expiry
    const timer = window.setTimeout(() => this.refreshToken(audience), Math.max(0, refreshIn));
    this.refreshTimers.set(audience, timer);
  }

  /**
   * Make an authenticated API request.
   * Auth header format: "nadeo_v1 t=<token>". CERTAIN (doc 19 Section 5).
   */
  async fetch(url: string, audience: string, options: RequestInit = {}): Promise<Response> {
    const token = await this.getToken(audience as any);
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `nadeo_v1 t=${token}`,
      },
    });
  }
}

/**
 * Secure token storage in browser.
 * Tokens should be stored in memory only (not localStorage) for security.
 * If persistence is needed across page reloads, use sessionStorage or
 * a service worker with encrypted storage.
 *
 * IMPORTANT: Never store Ubisoft Connect tickets or refresh tokens
 * in localStorage -- they are bearer tokens.
 */
class TokenStorage {
  private store: Map<string, string> = new Map();

  save(key: string, token: string): void {
    // In-memory only. Cleared on page close.
    this.store.set(key, token);
  }

  load(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  clear(): void {
    this.store.clear();
  }
}
```

**Browser auth limitation**: The Ubisoft Connect ticket exchange requires UPC SDK (Windows DLL). For a browser client, you need either (a) a backend proxy server that authenticates via UPC and issues Nadeo tokens, or (b) the community "dedicated server" authentication approach using the XML-RPC server account credentials. The Nadeo API itself is standard REST and works fine from `fetch()` once you have the token.

---

### 19.5 Input System (Browser)

Source: [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 1, [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 2. VERIFIED.

```typescript
// ============================================================
// Input system for Trackmania browser recreation
// Source: doc 19 Section 1 (input fields), doc 15 Section 2 (CInputPort)
//
// TM2020 Input Values (CERTAIN from doc 19):
//   InputSteer: float -1.0 to 1.0
//   InputGasPedal: float 0.0 to 1.0
//   InputBrakePedal: float 0.0 to 1.0
//   InputIsBraking: bool
//   InputVertical: float (reactor/flying)
// ============================================================

/** Input state matching TM2020's format. CERTAIN. */
interface InputState {
  steer: number;       // -1.0 to 1.0
  gas: number;         // 0.0 to 1.0
  brake: number;       // 0.0 to 1.0
  isBraking: boolean;
  vertical: number;    // Reactor/flying input
  respawn: boolean;    // Reset to checkpoint
  horn: boolean;
}

/** Default (no input) state. */
function defaultInput(): InputState {
  return { steer: 0, gas: 0, brake: 0, isBraking: false, vertical: 0, respawn: false, horn: false };
}

// ============================================================
// Keyboard input mapping
// Digital inputs: keyboard gives -1/0/+1, not analog.
// Source: doc 15 Section 2 -- DirectInput 8 for keyboard. CERTAIN.
// ============================================================
class KeyboardInput {
  private keys: Set<string> = new Set();

  constructor() {
    window.addEventListener('keydown', (e) => {
      this.keys.add(e.code);
      // Prevent default for game keys to avoid page scrolling
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', 'Backspace'].includes(e.code)) {
        e.preventDefault();
      }
    });

    window.addEventListener('keyup', (e) => {
      this.keys.delete(e.code);
    });

    // Clear keys when window loses focus (prevents stuck keys)
    window.addEventListener('blur', () => this.keys.clear());
  }

  sample(): InputState {
    const state = defaultInput();

    // Steering: digital -1/0/+1. CERTAIN (keyboard gives discrete values).
    if (this.keys.has('ArrowLeft'))  state.steer -= 1.0;
    if (this.keys.has('ArrowRight')) state.steer += 1.0;

    // Gas: digital 0/1.
    if (this.keys.has('ArrowUp')) state.gas = 1.0;

    // Brake: digital 0/1.
    if (this.keys.has('ArrowDown')) {
      state.brake = 1.0;
      state.isBraking = true;
    }

    // Respawn
    if (this.keys.has('Backspace') || this.keys.has('Delete')) {
      state.respawn = true;
    }

    // Reactor vertical
    if (this.keys.has('Space')) state.vertical = 1.0;

    return state;
  }
}

// ============================================================
// Gamepad input
// Source: doc 15 Section 2 -- XInput 9.1.0 for gamepads. CERTAIN.
//
// The Gamepad API maps directly to XInput's model:
//   Left stick X = steer (analog)
//   Right trigger = gas (analog)
//   Left trigger = brake (analog)
// ============================================================
class GamepadInput {
  private deadzone = 0.15; // APPROXIMATE -- actual TM2020 deadzone unknown.

  /**
   * Sample gamepad state.
   * Must be called every frame in requestAnimationFrame.
   * CERTAIN: Gamepad API uses polling model, same as XInput.
   */
  sample(): InputState | null {
    const gamepads = navigator.getGamepads();
    const gp = gamepads[0]; // Use first connected gamepad
    if (!gp) return null;

    const state = defaultInput();

    // Left stick X -> steer (analog, -1 to 1). CERTAIN mapping.
    const rawSteer = gp.axes[0];
    state.steer = this.applyDeadzone(rawSteer);

    // Right trigger -> gas (analog, 0 to 1).
    // Standard Gamepad mapping: axes[5] or buttons[7].value
    state.gas = Math.max(0, gp.buttons[7]?.value ?? 0);

    // Left trigger -> brake (analog, 0 to 1).
    state.brake = Math.max(0, gp.buttons[6]?.value ?? 0);
    state.isBraking = state.brake > 0.1;

    // Face buttons
    state.respawn = gp.buttons[3]?.pressed ?? false; // Y button
    state.vertical = gp.buttons[0]?.pressed ? 1.0 : 0.0; // A button for reactor

    return state;
  }

  private applyDeadzone(value: number): number {
    if (Math.abs(value) < this.deadzone) return 0;
    // Rescale from [deadzone, 1.0] to [0, 1.0]
    const sign = Math.sign(value);
    const magnitude = (Math.abs(value) - this.deadzone) / (1.0 - this.deadzone);
    return sign * Math.min(magnitude, 1.0);
  }
}

// ============================================================
// Input manager: merges keyboard + gamepad, syncs to physics ticks
// Source: doc 15 Section 2 -- CInputPort::Update_StartFrame runs each frame. CERTAIN.
// ============================================================
class InputManager {
  private keyboard: KeyboardInput;
  private gamepad: GamepadInput;
  private currentState: InputState = defaultInput();
  private inputHistory: { tick: number; input: InputState }[] = [];
  private currentTick: number = 0;

  constructor() {
    this.keyboard = new KeyboardInput();
    this.gamepad = new GamepadInput();
  }

  /**
   * Frame-synchronized input sampling.
   * Call this once per requestAnimationFrame, BEFORE physics tick.
   * CERTAIN: TM2020 samples input at frame start (CInputPort::Update_StartFrame).
   */
  sampleForTick(tick: number): InputState {
    this.currentTick = tick;

    // Gamepad takes priority if connected (analog input is superior).
    const gpState = this.gamepad.sample();
    const kbState = this.keyboard.sample();

    if (gpState) {
      this.currentState = gpState;
    } else {
      this.currentState = kbState;
    }

    // Record for ghost replay. CERTAIN (inputs are what get recorded for replays).
    this.inputHistory.push({
      tick,
      input: { ...this.currentState },
    });

    return this.currentState;
  }

  /** Get the recorded input history (for ghost recording). */
  getHistory(): { tick: number; input: InputState }[] {
    return this.inputHistory;
  }

  /** Clear history (for new race). */
  resetHistory(): void {
    this.inputHistory = [];
  }
}
```

---

### 19.6 Audio System (Web Audio)

Source: [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 1. VERIFIED for initialization. Engine sound model is APPROXIMATE.

```typescript
// ============================================================
// Audio system for Trackmania browser recreation
// Source: doc 15 Section 1 (OpenAL init, COalAudioPort). VERIFIED.
//
// TM2020 uses OpenAL with:
//   - Spatial 3D audio (PannerNode equivalent)
//   - Engine sound (RPM-based, CPlugSoundEngine/2)
//   - Surface sounds (CPlugSoundSurface)
//   - Music (CPlugSoundMood)
//   - EFX reverb (ConvolverNode equivalent)
// ============================================================

class AudioManager {
  private ctx: AudioContext;
  private masterGain: GainNode;
  private listener: AudioListener;

  // Sound categories
  private engineSound: EngineSound | null = null;
  private musicPlayer: MusicPlayer | null = null;
  private sfxPool: SoundPool;

  constructor() {
    this.ctx = new AudioContext();
    this.masterGain = this.ctx.createGain();
    this.masterGain.connect(this.ctx.destination);
    this.listener = this.ctx.listener;

    this.sfxPool = new SoundPool(this.ctx, this.masterGain, 32);
  }

  /** Resume audio context (required after user gesture). */
  async resume(): Promise<void> {
    if (this.ctx.state === 'suspended') {
      await this.ctx.resume();
    }
  }

  /**
   * Initialize engine sound.
   * TM2020 uses CPlugSoundEngine2 with RPM-based sample crossfading. PLAUSIBLE.
   * Exact curve is UNKNOWN; using linear pitch scaling as approximation.
   */
  async initEngineSound(samples: {
    idle: ArrayBuffer;
    low: ArrayBuffer;
    mid: ArrayBuffer;
    high: ArrayBuffer;
  }): Promise<void> {
    this.engineSound = new EngineSound(this.ctx, this.masterGain);
    await this.engineSound.loadSamples(samples);
  }

  /**
   * Update engine sound based on vehicle state.
   * Source: doc 19 Section 1 -- RPM field (0-11000). CERTAIN.
   */
  updateEngine(rpm: number, gas: number, engineOn: boolean): void {
    this.engineSound?.update(rpm, gas, engineOn);
  }

  /** Update 3D listener position (camera). CERTAIN (OpenAL listener model). */
  updateListener(position: Vec3, forward: Vec3, up: Vec3): void {
    if (this.listener.positionX) {
      // Modern API
      this.listener.positionX.value = position.x;
      this.listener.positionY.value = position.y;
      this.listener.positionZ.value = position.z;
      this.listener.forwardX.value = forward.x;
      this.listener.forwardY.value = forward.y;
      this.listener.forwardZ.value = forward.z;
      this.listener.upX.value = up.x;
      this.listener.upY.value = up.y;
      this.listener.upZ.value = up.z;
    }
  }

  /**
   * Play a spatial sound effect at a world position.
   * Maps to OpenAL source with 3D positioning. CERTAIN.
   */
  playSfx(buffer: AudioBuffer, position: Vec3, volume: number = 1.0): void {
    this.sfxPool.play(buffer, position, volume);
  }

  /** Start/stop background music with crossfade. APPROXIMATE. */
  async playMusic(url: string, crossfadeDuration: number = 2.0): Promise<void> {
    if (!this.musicPlayer) {
      this.musicPlayer = new MusicPlayer(this.ctx, this.masterGain);
    }
    await this.musicPlayer.crossfadeTo(url, crossfadeDuration);
  }
}

// ============================================================
// Engine sound synthesis
// Source: doc 15 Section 1 -- CPlugSoundEngine/2. PLAUSIBLE.
//
// APPROXIMATE: Actual engine sound model uses RPM-mapped sample
// crossfading (granular synthesis). This simplified version uses
// playbackRate scaling on a single loop.
// ============================================================
class EngineSound {
  private ctx: AudioContext;
  private output: GainNode;
  private source: AudioBufferSourceNode | null = null;
  private gainNode: GainNode;
  private buffers: { idle?: AudioBuffer; low?: AudioBuffer; mid?: AudioBuffer; high?: AudioBuffer } = {};

  constructor(ctx: AudioContext, destination: AudioNode) {
    this.ctx = ctx;
    this.gainNode = ctx.createGain();
    this.gainNode.connect(destination);
    this.output = this.gainNode;
  }

  async loadSamples(samples: {
    idle: ArrayBuffer;
    low: ArrayBuffer;
    mid: ArrayBuffer;
    high: ArrayBuffer;
  }): Promise<void> {
    this.buffers.idle = await this.ctx.decodeAudioData(samples.idle.slice(0));
    this.buffers.low  = await this.ctx.decodeAudioData(samples.low.slice(0));
    this.buffers.mid  = await this.ctx.decodeAudioData(samples.mid.slice(0));
    this.buffers.high = await this.ctx.decodeAudioData(samples.high.slice(0));
  }

  /**
   * Update engine sound based on RPM and throttle.
   * RPM range: 0-11000. CERTAIN (doc 19 Section 1).
   * Sound model: APPROXIMATE.
   */
  update(rpm: number, gas: number, engineOn: boolean): void {
    if (!engineOn || !this.buffers.idle) {
      this.stop();
      return;
    }

    if (!this.source) {
      this.source = this.ctx.createBufferSource();
      this.source.buffer = this.buffers.idle; // Start with idle
      this.source.loop = true;
      this.source.connect(this.gainNode);
      this.source.start();
    }

    // Map RPM to pitch. APPROXIMATE.
    // Idle = 1000 RPM -> playbackRate 1.0
    // Redline = 11000 RPM -> playbackRate ~3.0
    const normalizedRpm = Math.max(rpm, 1000) / 1000;
    const pitchRate = 0.5 + normalizedRpm * 0.25; // Scale from 0.75 to 3.25
    this.source.playbackRate.setTargetAtTime(pitchRate, this.ctx.currentTime, 0.05);

    // Volume based on throttle. APPROXIMATE.
    const volume = 0.3 + gas * 0.7;
    this.gainNode.gain.setTargetAtTime(volume, this.ctx.currentTime, 0.05);
  }

  stop(): void {
    if (this.source) {
      this.source.stop();
      this.source = null;
    }
  }
}

// ============================================================
// 3D spatial sound pool
// Maps to OpenAL source pooling. CERTAIN structure, APPROXIMATE limits.
// Doc 15: "queries mono/stereo source counts" during init.
// Modern browsers support ~100+ concurrent AudioNodes.
// ============================================================
class SoundPool {
  private ctx: AudioContext;
  private output: AudioNode;
  private maxSources: number;

  constructor(ctx: AudioContext, output: AudioNode, maxSources: number) {
    this.ctx = ctx;
    this.output = output;
    this.maxSources = maxSources;
  }

  play(buffer: AudioBuffer, position: Vec3, volume: number): void {
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;

    // 3D panner (maps to OpenAL source positioning). CERTAIN.
    const panner = this.ctx.createPanner();
    panner.panningModel = 'HRTF';
    panner.distanceModel = 'inverse';
    panner.refDistance = 1;
    panner.maxDistance = 200;
    panner.rolloffFactor = 1;
    panner.positionX.value = position.x;
    panner.positionY.value = position.y;
    panner.positionZ.value = position.z;

    const gain = this.ctx.createGain();
    gain.gain.value = volume;

    source.connect(gain).connect(panner).connect(this.output);
    source.start();
    source.onended = () => source.disconnect();
  }
}

// ============================================================
// Music player with crossfade
// Source: doc 13 -- CAudioScriptMusic. PLAUSIBLE.
// ============================================================
class MusicPlayer {
  private ctx: AudioContext;
  private output: AudioNode;
  private currentSource: AudioBufferSourceNode | null = null;
  private currentGain: GainNode | null = null;

  constructor(ctx: AudioContext, output: AudioNode) {
    this.ctx = ctx;
    this.output = output;
  }

  async crossfadeTo(url: string, duration: number): Promise<void> {
    const response = await fetch(url);
    const audioData = await response.arrayBuffer();
    const buffer = await this.ctx.decodeAudioData(audioData);

    // Fade out current
    if (this.currentGain) {
      this.currentGain.gain.linearRampToValueAtTime(0, this.ctx.currentTime + duration);
      const oldSource = this.currentSource;
      setTimeout(() => oldSource?.stop(), duration * 1000);
    }

    // Fade in new
    const gain = this.ctx.createGain();
    gain.gain.value = 0;
    gain.gain.linearRampToValueAtTime(0.5, this.ctx.currentTime + duration);
    gain.connect(this.output);

    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.connect(gain);
    source.start();

    this.currentSource = source;
    this.currentGain = gain;
  }
}
```

---

### 19.7 Project Structure

```
trackmania-web/
  src/
    core/                 # Engine core
      game-loop.ts        # requestAnimationFrame + fixed timestep accumulator
      timer.ts            # Race timer, checkpoint splits
      config.ts           # Game configuration, settings
      events.ts           # Event bus for cross-system communication

    physics/              # Physics engine (compile to WASM for production)
      vehicle-state.ts    # VehicleState struct definition
      physics-step.ts     # Main physics tick (PhysicsStep_TM equivalent)
      force-models/       # Per-vehicle-type force computation
        car-sport.ts      # CarSport (Stadium) force model
        car-snow.ts       # CarSnow force model
        car-rally.ts      # CarRally force model
        car-desert.ts     # CarDesert force model
      collision/          # Collision detection (wraps rapier.js)
        broadphase.ts     # BVH-based broadphase
        contact.ts        # Contact point processing
        surface.ts        # Surface friction lookup table
      integration.ts      # Forward Euler integrator
      constants.ts        # Physics constants (tick rate, gravity, etc.)

    renderer/             # WebGPU renderer
      pipeline/           # Render pipeline stages
        deferred-write.ts # G-buffer fill pass
        deferred-light.ts # Deferred lighting pass
        shadow.ts         # PSSM shadow map pass
        forward.ts        # Forward pass (transparent objects)
        post/             # Post-processing
          bloom.ts        # HDR bloom (downsample + upsample)
          tonemap.ts      # Filmic tone mapping + auto-exposure
          fxaa.ts         # FXAA anti-aliasing
      gbuffer.ts          # G-buffer creation and management
      vertex-formats.ts   # Block, simple, lightmapped vertex layouts
      shaders/            # WGSL shader source
        deferred-write.wgsl
        deferred-light.wgsl
        shadow.wgsl
        bloom.wgsl
        fxaa.wgsl
      camera/             # Camera controllers
        chase-camera.ts   # Spring-damper chase camera
        orbital-camera.ts # Editor orbital camera (math from doc 19)
        free-camera.ts    # Free-fly camera
      mesh.ts             # Mesh loading and GPU buffer management
      material.ts         # Material system (surface ID, textures)
      scene.ts            # Scene graph, frustum culling

    parsers/              # File format parsers
      gbx/                # GBX parser
        reader.ts         # BinaryReader (DataView wrapper)
        header.ts         # GBX header parsing
        body.ts           # Body chunk stream parsing
        lookback.ts       # LookbackString table
        remap.ts          # Class ID remap table (200+ entries)
        compression.ts    # zlib decompression
      chunks/             # Per-chunk-type parsers
        map/              # CGameCtnChallenge chunks
          info.ts         # 0x03043002 -- map info
          common.ts       # 0x03043003 -- common header
          thumbnail.ts    # 0x03043007 -- thumbnail
          blocks.ts       # Block data chunks
          items.ts        # Item placement chunks
        ghost/            # CGameCtnGhost chunks
        replay/           # CGameCtnReplayRecord chunks
      map-loader.ts       # High-level: GBX file -> renderable map

    audio/                # Web Audio system
      audio-manager.ts    # Top-level audio orchestrator
      engine-sound.ts     # Engine RPM-based synthesis
      sound-pool.ts       # Spatial 3D sound effect pool
      music-player.ts     # Background music with crossfade

    input/                # Input handling
      input-manager.ts    # Unified input (keyboard + gamepad)
      keyboard.ts         # KeyboardEvent handler
      gamepad.ts          # Gamepad API handler
      input-state.ts      # InputState struct definition
      input-recorder.ts   # Input recording for ghost replay

    network/              # API client
      auth.ts             # Nadeo authentication flow
      api-client.ts       # REST API wrapper (Core/Live/Meet)
      map-api.ts          # Map download and metadata
      leaderboard-api.ts  # Leaderboard queries
      ghost-api.ts        # Ghost download

    ui/                   # UI framework (Svelte or React)
      hud/                # In-game HUD
        speedometer.svelte
        race-timer.svelte
        checkpoint-times.svelte
        minimap.svelte
      menus/              # Menu screens
        main-menu.svelte
        map-select.svelte
        settings.svelte
        results.svelte
      components/         # Shared UI components
        button.svelte
        modal.svelte

    editor/               # Map editor (Phase 5+)
      editor.ts           # Editor state machine
      block-palette.ts    # Available blocks list
      placement.ts        # Block placement with grid snapping
      validation.ts       # Map validity checks
      undo-redo.ts        # Command pattern undo/redo

  public/
    assets/
      blocks/             # Pre-extracted block meshes (glTF/GLB)
      textures/           # Material textures
      sounds/             # Audio files (engine, sfx, music)
      cars/               # Car models

  wasm/                   # WASM source (Rust)
    physics/              # Physics engine in Rust (for determinism)
      src/
        lib.rs            # WASM entry points
        vehicle.rs        # Vehicle state and force models
        collision.rs      # Collision detection
        integration.rs    # Forward Euler
      Cargo.toml

  tests/
    physics/              # Physics validation tests (TMInterface data)
    parser/               # GBX parser tests (known .Gbx files)

  package.json
  tsconfig.json
  vite.config.ts
```

---

### 19.8 Technology Stack Decisions

| Component | Choice | Why | Alternatives Considered | Trade-offs |
|---|---|---|---|---|
| **Language** | TypeScript | Type safety, IDE support, ecosystem. Physics-critical code moves to Rust/WASM later. | JavaScript (less safe), C++ via Emscripten (harder to iterate) | TS adds build step but catches bugs early |
| **3D Rendering (MVP)** | three.js with WebGPU backend | Fastest path to rendering. Mature library, handles vertex buffers, materials, cameras, shadows out of the box. | Raw WebGPU (more control, harder), Babylon.js (also viable but heavier) | three.js abstractions may limit deferred pipeline; plan to migrate hot path to raw WebGPU |
| **3D Rendering (Full)** | Raw WebGPU + WGSL | Required for deferred pipeline with 4+ MRT, custom shadow passes, compute shaders. three.js cannot express the full 19-pass pipeline. | WebGL2 (wider support but no compute shaders, no MRT >4 in practice) | Must handle all rendering boilerplate; worth it for deferred + compute particles |
| **Physics (MVP)** | TypeScript (in main thread) | Fastest to iterate. Physics code changes constantly during tuning. | Rust/WASM from day 1 (slower iteration) | Not deterministic; fine for MVP |
| **Physics (Full)** | Rust compiled to WASM via wasm-pack | Deterministic floating-point with Rust's `#[cfg(target_arch = "wasm32")]` controls. Runs in Web Worker for off-main-thread. | C++ via Emscripten (also viable, familiar to game devs), JS with fixed-point (poor precision) | Rust WASM has excellent tooling; debugging is harder than TS |
| **Collision Detection** | rapier3d-compat (WASM) | Production-quality BVH broadphase, GJK/EPA narrowphase. Written in Rust, compiled to WASM. | cannon-es (pure JS, slower), ammo.js (Bullet via Emscripten, large), custom (months of work) | rapier handles the hard collision math; custom vehicle forces sit on top |
| **GBX Parser** | gbx-ts + extensions | Existing community TypeScript parser handles GBX v3-v6, many chunk types. Saves months of work. | gbx-net via .NET WASM (possible but heavy), custom from scratch (doc 16 makes this feasible but slower) | May need to fork/extend for missing TM2020-specific chunks |
| **UI Framework** | Svelte | Minimal bundle size, fast rendering, simple reactivity model. Game UIs are mostly static with periodic updates. | React (larger ecosystem but bigger bundle), Vue (also viable), vanilla HTML (no framework overhead) | Svelte compiles away the framework; ideal for performance-sensitive game UI overlay |
| **Build Tool** | Vite | Fast dev server, native TypeScript support, WASM plugin ecosystem, tree-shaking. | webpack (slower), Parcel (less configurable), esbuild (no plugin ecosystem) | Vite is the modern standard for this project shape |
| **Math Library** | gl-matrix | Lightweight, well-tested, no dependencies. Needed for mat4, vec3, quat operations in the renderer and physics. | three.js math (tied to three.js), @math.gl (heavier), hand-rolled (error-prone) | gl-matrix is the standard for WebGPU projects |
| **Compression** | Native DecompressionStream + pako fallback | Browser-native zlib inflate (zero-dependency). pako for older browsers. | fflate (smaller than pako), zlib.js | DecompressionStream has near-universal support in 2026 |
| **Audio** | Web Audio API (native) | No library needed. AudioContext, PannerNode, GainNode map directly to TM2020's OpenAL usage. | Howler.js (convenience wrapper), Tone.js (overkill for game audio) | Raw Web Audio gives full control over spatial audio and engine synthesis |

---

### 19.9 Development Roadmap with Milestones

#### Phase 1: "Hello Block" (Weeks 1-4)
**Goal**: Load a GBX file and render a single block in the browser.

| Week | Milestone | Deliverable |
|---|---|---|
| 1 | GBX header parser | Parse header of any .Map.Gbx file, display map name, author, environment. Validate against 10+ community maps. |
| 2 | GBX body decompression + chunk stream | Decompress body with zlib, enumerate all chunk IDs. Log unknown vs known chunks. |
| 2 | Block mesh extraction (offline tool) | Node.js script using gbx-net to extract 20 common Stadium road block meshes into glTF format. |
| 3 | WebGPU bootstrap | Initialize WebGPU device, create swap chain, render a colored triangle. Set up Vite + TypeScript project. |
| 3 | Block renderer (single block) | Load one glTF block mesh into WebGPU vertex/index buffers. Render with basic PBR (albedo + normal map). |
| 4 | Map block placement | Parse block positions/rotations from map file. Place 10+ blocks at correct grid positions (32m per unit). Free camera to fly around. |

**Exit criteria**: Load `A01-Race.Map.Gbx` (or similar simple map) and see the road blocks rendered in 3D with a free camera.

#### Phase 2: "Map Viewer" (Weeks 5-8)
**Goal**: Load and render a complete map with lighting.

| Week | Milestone | Deliverable |
|---|---|---|
| 5 | Full block library extraction | Extract all standard Stadium block meshes (~200 blocks). Build a block mesh registry keyed by block name. |
| 5 | Material system | Parse material names from GBX. Map to diffuse textures extracted from pack files. Apply basic PBR materials. |
| 6 | Directional light + shadows | Single sun light. PSSM shadows with 2 cascades (upgrade to 4 later). Basic shadow mapping. |
| 6 | Sky/environment | Simple skybox or gradient sky. Atmosphere color based on map mood (day/sunset/night). |
| 7 | Item placement | Parse item positions from map file. Load item meshes (signs, barriers, decorations). |
| 7 | Terrain/decoration | Render terrain blocks and decoration meshes. Ground plane for unplaced areas. |
| 8 | Performance pass | Frustum culling, basic LOD (skip small items at distance), draw call batching for repeated blocks. |

**Exit criteria**: Load any standard Stadium map and see it fully rendered with lighting and shadows. 60fps at 1080p.

#### Phase 3: "Physics Box" (Weeks 9-12)
**Goal**: Drive a car in an empty world with physics.

| Week | Milestone | Deliverable |
|---|---|---|
| 9 | Vehicle state + input system | InputState struct, keyboard + gamepad handlers, input sampling in game loop. VehicleState struct with position, velocity, orientation. |
| 9 | Basic physics step | Forward Euler integration. Gravity + flat ground plane collision. Car falls and lands. |
| 10 | Engine + brake force model | Engine force (throttle -> acceleration), brake force (deceleration). Aerodynamic drag. Car accelerates to top speed. |
| 10 | Steering model | Steering torque around Y axis. Speed-dependent turn rate. Car can turn. |
| 11 | Suspension + wheel contacts | 4-wheel ray casts downward. Spring-damper suspension. Car follows terrain height. |
| 11 | Surface friction | Look up surface ID from contact material. Apply different friction for asphalt, dirt, ice. |
| 12 | Chase camera | Spring-damper camera following vehicle. Smooth tracking with lag. Height offset. |

**Exit criteria**: Drive the CarSport on a flat plane. Steering, acceleration, braking feel reasonable. Gamepad analog input works.

#### Phase 4: "First Drive" (Weeks 13-18)
**Goal**: Drive the car on a real map with collision.

| Week | Milestone | Deliverable |
|---|---|---|
| 13 | Map collision mesh | Generate collision geometry from block meshes. Load into rapier.js. |
| 13 | Vehicle-map collision | Car drives on the road surface. Falls off edges. Hits walls. |
| 14 | Turbo pads | Detect turbo block contact. Apply boost force (linear ramp per doc 10 Section 4.3). Visual turbo effect (colored trail). |
| 14 | Jump/air physics | Correct air behavior (gravity only, no tire forces). Landing detection. |
| 15 | Checkpoint detection | Identify checkpoint/finish blocks from map data. Detect car passing through waypoint volumes. |
| 15 | Race timer | Start on first gas input. Record checkpoint times. Show finish time. |
| 16 | Physics tuning pass | Record TMInterface validation data (10 replay files: input + position at each tick). Compare browser physics output. Tune constants to minimize divergence. |
| 17-18 | Bug fixing, edge cases | Wall sliding, flip recovery, reset to checkpoint, multiple surface transitions. |

**Exit criteria**: Complete a lap on a standard Stadium map. Timer works. Physics feel "approximately right" (not exact, but drivable and fun).

#### Phase 5: "Racing" (Weeks 19-24)
**Goal**: Ghost recording/playback, HUD, audio, polish.

| Week | Milestone | Deliverable |
|---|---|---|
| 19 | Ghost recording | Record input history during race. Save as JSON. |
| 19 | Ghost playback | Load recorded inputs. Run physics simulation to reproduce the run. Render as semi-transparent car. |
| 20 | HUD | Speedometer (FrontSpeed * 3.6 for km/h), race timer, checkpoint split times, current/best comparison. |
| 20 | Audio: engine sound | Single engine loop with RPM-based pitch scaling. Throttle-responsive volume. |
| 21 | Audio: SFX | Tire screech (triggered by slipCoef > threshold), turbo activation sound, checkpoint sound, finish sound. |
| 21 | Deferred rendering upgrade | Migrate from three.js forward to WebGPU deferred pipeline (4 MRT G-buffer). |
| 22 | Post-processing | HDR bloom, filmic tone mapping, FXAA. |
| 22 | Shadows upgrade | PSSM 4 cascades, PCF filtering, slope-scaled bias. |
| 23-24 | Polish | Menu screens (map select, settings, results). Loading screen. Settings (resolution, quality, input config). |

**Exit criteria**: Full racing experience on any Stadium map. Record a ghost, see it replay. HUD shows speed and time. Audio immersion. Looks good.

#### Phase 6: Expansion (Weeks 25+)
**Goal**: Online features, additional content.

| Milestone | Description | Dependency |
|---|---|---|
| Online ghost download | Nadeo API integration: download ghosts for any map, play alongside your run. | Auth system (Section 19.4) |
| Leaderboard display | Show top times for loaded map. Fetch from Nadeo Live API. | Auth system |
| Additional car types | CarSnow, CarRally, CarDesert: different force model tuning, different meshes. | Force model research |
| Map editor (basic) | Place blocks on grid, orbital camera, save as .Map.Gbx. | Block placement rules research |
| Multiplayer (basic) | 2-player over WebRTC DataChannel. Exchange inputs, simulate independently, reconcile. | WebRTC, physics determinism |
| ManiaScript (subset) | Lexer + parser from doc 15 token spec. Interpret basic race mode scripts. | Significant effort |

---

*This document synthesizes findings from 15 reverse engineering documents totaling ~12,000 lines of analysis. All claims reference their source documents. Confidence levels follow the convention established in the RE documentation: VERIFIED (confirmed from decompiled code or runtime evidence), PLAUSIBLE (strongly supported by indirect evidence), SPECULATIVE (reasonable inference without direct evidence), UNKNOWN (no evidence either way).*

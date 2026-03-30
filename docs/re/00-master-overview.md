# Trackmania 2020 Reverse Engineering - Master Overview

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**File size**: 45,467,720 bytes (43.4 MB)
**Format**: PE32+ x86-64, Windows GUI
**Image base**: `0x140000000`
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra headless bridge
**Analyst**: Automated multi-agent analysis with manual oversight

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Binary Protection](#2-binary-protection)
3. [Engine Architecture](#3-engine-architecture)
4. [Class System](#4-class-system)
5. [Subsystem Map](#5-subsystem-map)
6. [Key Findings by Domain](#6-key-findings-by-domain)
7. [Critical Addresses](#7-critical-addresses)
8. [Open Questions](#8-open-questions)
9. [Detailed Reports](#9-detailed-reports)
10. [Decompiled Code Index](#10-decompiled-code-index)

---

## 1. Executive Summary

Trackmania 2020 is built on Nadeo's proprietary **ManiaPlanet/GameBox engine**, a mature C++ game engine with roots going back to the original TrackMania (2003). The binary contains **131,311 functions** (all symbol-stripped), **52,890 defined strings**, and **2,027 identified Nadeo engine classes**.

Despite being fully stripped of debug symbols, the binary is exceptionally rich in embedded debug/profiling strings. Nearly every function begins with a profiling scope tag like `FUN_140117690(buf, "ClassName::MethodName")`, which allowed identification of hundreds of functions by cross-referencing these strings.

### Key Statistics

| Metric | Value |
|---|---|
| Total functions | 131,311 |
| Defined strings | 52,890 |
| Raw ASCII strings (>= 8 chars) | 73,071 |
| Identified Nadeo classes | 2,027 |
| Classes with known methods | 276 |
| MSVC RTTI classes | 55 |
| Imported DLLs | 29 (many resolved at runtime due to packing) |
| PE sections | 11 (3 non-standard) |
| Decompiled functions (this analysis) | 63 |
| Lines of documentation | 37,684 |

### Technology Stack

| Component | Technology |
|---|---|
| Graphics API | Direct3D 11 (exclusive at runtime) |
| Rendering | Deferred shading with G-buffer, "Tech3" engine |
| Audio | OpenAL Soft 1.23.99 (OpenAL64_bundled.dll), Ogg Vorbis (vorbis64.dll), 3-layer audio stack |
| Input | DirectInput 8 + XInput 9.1.0 |
| Networking | Winsock2 + libcurl + OpenSSL 1.1.1t+quic (static) |
| DRM | Ubisoft Connect (upc_r2_loader64.dll) |
| Voice Chat | Vivox (VoiceChat.dll, loaded at runtime) |
| Text Chat | XMPP (*.chat.maniaplanet.com) |
| Image Format | libwebp (libwebp64.dll) |
| Scripting | ManiaScript (custom, interpreted) |
| Video | AVI (AVIFIL32.dll) |
| Crypto | bcrypt.dll + OpenSSL (SHA256, HMAC, CRC32/64) |
| Debug | dbghelp.dll (crash dumps, stack traces) |

---

## 2. Binary Protection

The binary employs code protection/packing:

- **Entry point** (`0x14291e317`) is in non-standard `.D."` section, not `.text`
- **3 TLS callbacks** execute before main entry (anti-debug/unpacking)
- **Minimal IAT**: only 35 imported symbols across 23 DLLs (most resolved at runtime via LoadLibrary/GetProcAddress)
- **3 non-standard sections**: `.A2U` (6.0 MB, RX), `.9Bv` (6 KB, RW), `.D."` (4.2 MB, RX) - randomly-named, suggesting a packer
- **~10 MB of executable code** in these non-standard sections

Despite protection, the `.text` section (25.4 MB) and `.rdata` (5.0 MB) contain unobfuscated code and data, enabling extensive analysis.

See: [01-binary-overview.md](01-binary-overview.md)

---

## 3. Engine Architecture

### Application Class Hierarchy

```
CGbxApp                         -- GameBox application base
  └─> CGameApp                  -- Game application layer
        └─> CGameCtnApp         -- Creation (Ctn) application
              └─> CGameManiaPlanet  -- ManiaPlanet platform layer
                    └─> CTrackMania     -- TrackMania-specific game
```

### Startup Sequence

```
entry (0x14291e317)             -- Obfuscated entry in .D." section
  -> WinMainCRTStartup          -- MSVC CRT bootstrap (VS2019)
    -> WinMain (0x140aa7470)     -- 640x480 default, profiling init
      -> CGbxGame::InitApp       -- Engine subsystem creation
        -> CGbxApp::Init1        -- First-phase init (80KB function!)
          -> CSystemEngine::InitForGbxGame  -- File system, config
          -> CVisionEngine init  -- Graphics subsystem
          -> CInputEngine init   -- Input subsystem
          -> CAudioEngine init   -- Audio subsystem
        -> CGbxApp::Init2        -- Second-phase init
          -> CGameManiaPlanet::Start  -- Game-specific startup
            -> CGameCtnApp::Start     -- Menu/network startup
```

### Main Game Loop

There is no function named "GameLoop". The game loop is driven by **`CGameCtnApp::UpdateGame`** at `0x140b78f10` - a **216 KB function** implementing a massive state machine.

Three nested state machine tiers:
1. **Game states**: `GameState_LocalLoopPlaying`, `GameState_NetPlaying`, `GameState_Menus`, etc.
2. **Network states**: `CGameCtnNetwork::MainLoop_Menus`, `MainLoop_PlaygroundPlay`, `MainLoop_SetUp`
3. **Arena states**: `CSmArenaClient::MainLoop_*` for gameplay

### Engine Subsystems (12 Singletons)

| Engine | Role |
|---|---|
| `CSystemEngine` | File system, config, platform |
| `CVisionEngine` | Rendering, shaders, viewports |
| `CInputEngine` | Input devices, bindings |
| `CAudioEngine` | Spatial audio, music |
| `CNetEngine` | Networking, connections |
| `CScriptEngine` | ManiaScript runtime |
| `CControlEngine` | UI layout, effects, focus |
| `CSceneEngine` | 3D scene, entities, physics |
| `CGameEngine` | [UNKNOWN - presumed] |
| `CPlugEngine` | [UNKNOWN - presumed] |
| `CMwEngine` | [UNKNOWN - presumed] |
| `CHmsEngine` | [UNKNOWN - presumed] |

### Fiber/Coroutine System

`CMwCmdFiber` (88 bytes per instance) provides cooperative multitasking for:
- Dialog workflows
- Network operations
- Editor save/load
- Script execution

Includes render-thread collision detection safety checks.

See: [08-game-architecture.md](08-game-architecture.md)

---

## 4. Class System

### CMwNod: The Universal Base Class

All Nadeo engine objects inherit from `CMwNod`. Evidence:
- Factory pattern: `CreateByMwClassId` function at `0x1402cf380`
- Type assertion: `"Parameter is not a CMwNod."`
- Static init: `CMwNod::StaticInit` string reference

### Custom RTTI (Not MSVC)

Nadeo uses its own class registration system with **numeric MwClassIds** (not MSVC RTTI):
- Two-level hierarchical class registry at global `DAT_141ff9d58`
- TLS-cached class lookups for performance
- **200+ legacy-to-modern class ID remappings** for backward compatibility (`FUN_1402f2610`)
- No Nadeo vtable symbols exist in the binary (0 out of 83 vtable symbols are Nadeo classes)

### Class Distribution (2,027 classes)

| Prefix | Count | Domain |
|---|---:|---|
| CGame* | 728 | Game logic, UI, editors, maps, players |
| CPlug* | 391 | Assets, materials, meshes, animation |
| CWebServices* | 297 | Online service tasks and results |
| CNet* | 262 | Networking, protocols, services |
| CScene* | 52 | Scene graph, vehicles, effects |
| CHms* | 41 | Hierarchical Managed Scene (renderer) |
| CControl* | 39 | UI controls |
| CSystem* | 24 | System layer (files, config) |
| CMap* | 23 | Map editor scripting API |
| CAudio* | 19 | Audio engine |
| CInput* | 17 | Input devices |
| CMw* | 17 | Engine core |
| Others | 117 | Script, XML, Block, Media, etc. |

### Architectural Patterns

- **Task/Result async pairs**: ~406 task classes + ~168 result classes for async web service operations
- **Model/Physics/Visual decomposition**: Entities split into data model, physics simulation, and visual representation
- **Editor class hierarchy**: 15+ editor types (Map, Item, Mesh, Material, MediaTracker, Action, Module, etc.)
- **MediaTracker blocks**: 65+ block types for replay/cutscene editing

See: [02-class-hierarchy.md](02-class-hierarchy.md)

---

## 5. Subsystem Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        CTrackMania                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Editors  │ │ Menus    │ │ Gameplay │ │ Online Services   │  │
│  │ (15+)    │ │ CGameCtn │ │ CSm*     │ │ CWebServices*     │  │
│  │          │ │ Menus*   │ │ Arena*   │ │ CNetNadeoServices │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬──────────────┘  │
│       │             │            │             │                  │
│  ┌────┴─────────────┴────────────┴─────────────┴──────────────┐  │
│  │              CGameCtnApp (State Machine)                    │  │
│  │              216 KB UpdateGame function                      │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────┴───────────────────────────────────┐  │
│  │                    Engine Layer                              │  │
│  │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────┐ │  │
│  │  │CScene   │ │CVision   │ │CSystem │ │CNet  │ │CScript │ │  │
│  │  │Engine   │ │Engine    │ │Engine  │ │Engine│ │Engine  │ │  │
│  │  │         │ │D3D11     │ │Fid/Pak │ │TCP/  │ │Mania   │ │  │
│  │  │Physics  │ │Deferred  │ │GBX     │ │UDP   │ │Script  │ │  │
│  │  │NScene   │ │HBAO+     │ │Archive │ │curl  │ │        │ │  │
│  │  │Dyna     │ │Shadows   │ │        │ │      │ │        │ │  │
│  │  └─────────┘ └──────────┘ └────────┘ └──────┘ └────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    CMwNod Base Layer                         │  │
│  │  Class registry, MwClassIds, Serialization, Fiber system    │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

External:
  ├── Ubisoft Connect (upc_r2_loader64.dll) -- DRM, auth, achievements
  ├── Vivox (VoiceChat.dll) -- Voice chat
  ├── XMPP (*.chat.maniaplanet.com) -- Text chat
  └── Nadeo Services (core.trackmania.nadeo.live) -- API
```

---

## 6. Key Findings by Domain

### 6.1 Physics & Vehicle Simulation

The physics system is a multi-layer pipeline:
`CSmArenaPhysics` -> `PhysicsStep_TM` -> `NSceneDyna::PhysicsStep_V2` -> `NSceneDyna::InternalPhysicsStep`

Key discoveries:
- **7 force models** via switch at vehicle state offset `+0x1790` -- 3 now fully decompiled:
  - Cases 0/1/2: Base 4-wheel model (300+ lines, per-wheel surface lookup, anti-roll bar, air resistance)
  - Case 3: 2-wheel bicycle model (250+ lines, Pacejka-like tire model, 3-state drift machine)
  - Case 6: CarSport/Stadium full model (350+ lines, 9 sub-functions, launched checkpoint boost)
- **Adaptive sub-stepping**: velocity-dependent, capped at 1000 sub-steps per tick
- **22 surface gameplay effects** fully enumerated (`EPlugSurfaceGameplayId`): Turbo, Turbo2, NoGrip, NoSteering, NoBrakes, Fragile, Bouncy, FreeWheeling, SlowMotion, ReactorBoost, VehicleTransform (Rally/Snow/Desert), Cruise
- **Drift state machine**: 3 states (none -> building -> committed), slip accumulation proportional to `lateral_slip * drift_rate * dt`
- **Pacejka-like tire model**: `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`
- **Turbo system**: time-limited with linear decay (offsets `+0x16E0/E4/E8`)
- **Gravity**: parameterized vector (not hardcoded), supports GravityCoef modifier
- **Collision**: tree-based broadphase with iterative friction solver (separate static/dynamic iteration counts)
- **Water physics**: buoyancy and drag forces in `NSceneDyna::ComputeWaterForces`
- **Checkpoint boost**: launched checkpoints apply directional forces with speed-dependent curves; post-respawn force fades over 2x duration

See: [04-physics-vehicle.md](04-physics-vehicle.md) | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) | Decompiled: `decompiled/physics/` (26 files)

### 6.2 Rendering & Graphics

- **D3D11 only** at runtime (Vulkan/D3D12 strings exist but unused)
- **Deferred shading** primary path with G-buffer; forward path for transparents
- **"Tech3"** is Nadeo's 3rd-generation rendering technology
- **NVIDIA HBAO+** (20-field configuration struct documented)
- **HDR Bloom** (3 quality levels), filmic tone mapping with auto-exposure
- **PSSM shadows** (4 cascades) + shadow volumes + shadow cache + clip-map + static baked + fake shadows
- **GPU-driven particles** with compute shaders, self-shadowing via voxelization (6 passes)
- **Volumetric fog** (ray marching), SSR (temporal), PBR (GGX BRDF), lightmapping
- **200+ HLSL shader files** organized under Tech3/, Effects/, Engines/, Lightmap/

See: [05-rendering-graphics.md](05-rendering-graphics.md) | Decompiled: `decompiled/rendering/` (5 files)

### 6.3 File Formats (GBX)

- **GBX header**: Magic "GBX" (3 bytes), version uint16 (3-6 supported), format flags "BUCE"/"BUCR"
- **5 files validated byte-exact**: Map, Profile, Block, FuncShader, ImageGen -- all confirmed against spec
- **LZO1X body compression** confirmed from real files (not zlib -- see doc 26). zlib present for other uses.
- **Chunk-based body** with `0xFACADE01` end-of-chunks sentinel
- **CClassicArchive** serialization system with 30+ documented offsets
- **Two-level class registry** at `DAT_141ff9d58` with TLS-cached lookups
- **200+ legacy class ID remappings** for backward compatibility across engine versions
- **431 `.Gbx` file extensions** catalogued (maps, items, ghosts, meshes, textures, audio, etc.)
- **NadeoPak header format**: .pak files use "NadeoPak" magic, NOT GBX format
- **1,112 shader files** in GPU cache (GpuCache_D3D11_SM5.zip)
- **Fid system** hierarchy: `CSystemFidsDrive` -> `CSystemFidsFolder` -> `CSystemFidFile` -> `CSystemFidContainer`
- **6 pack types**: .pack.gbx, .skin.pack.gbx, .Title.Pack.Gbx, .Media.Pack.Gbx, Model.Pack.Gbx, -wip.pack.gbx
- **23-stage map loading pipeline** in CGameCtnChallenge
- **32-meter block grid** with 8m Y sub-unit, items use free-floating Vec3

See: [06-file-formats.md](06-file-formats.md) | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) | [26-real-file-analysis.md](26-real-file-analysis.md) | [28-map-structure-encyclopedia.md](28-map-structure-encyclopedia.md) | Decompiled: `decompiled/fileformats/` (9 files)

### 6.4 Networking & Online Services

- **10-layer architecture** from Winsock2 to CGameCtnNetwork
- **Dual TCP+UDP** game protocol
- **libcurl + OpenSSL 1.1.1t+quic** statically linked (possible HTTP/3 support)
- **Three-step authentication**: Ubisoft Connect ticket -> UbiServices session -> Nadeo Services token exchange
- **API domains**: `core.trackmania.nadeo.live`, `.nadeo.club`, `.maniaplanet.com`
- **Full XML-RPC server** (same protocol as TMNF/TM2 dedicated server controllers)
- **200+ API task types** across NadeoServices and UbiServices
- **Voice chat**: Vivox (VoiceChat.dll)
- **Text chat**: XMPP to `*.chat.maniaplanet.com`
- **Anti-cheat**: server-side replay verification with chunked upload
- **Leaked source paths**: `C:\Nadeo\CodeBase_tm-retail\` and `D:\CodeBase_Ext\externallibs\ubiservices\`

See: [07-networking.md](07-networking.md) | Decompiled: `decompiled/networking/` (4 files)

### 6.5 ManiaScript Engine

- `CScriptEngine::Run` executes scripts with per-script profiling tags
- Complete lexer token table: 50+ token types, 12 built-in types, 7 directives, 20+ collection operations
- Script interface is deeply integrated with the class system via `CScriptInterfacableValue`

See: [08-game-architecture.md](08-game-architecture.md) (Section 9)

---

## 7. Critical Addresses

### Entry & Startup
| Address | Function |
|---|---|
| `0x14291e317` | `entry` (obfuscated, in .D." section) |
| `0x141521c28` | `WinMainCRTStartup` (MSVC CRT) |
| `0x140aa7470` | `WinMain` (actual) |
| `0x1400a6ec0` | `CGbxGame::InitApp` |
| `0x140aaac00` | `CGbxApp::Init1` (80 KB) |
| `0x140ab00a0` | `CGbxApp::Init2` |
| `0x140b78f10` | `CGameCtnApp::UpdateGame` (216 KB, main loop) |

### Physics
| Address | Function |
|---|---|
| `0x141312870` | `CSmArenaClient::UpdatePhysics` |
| `0x1412c2cc0` | `CSmArenaPhysics::Players_BeginFrame` |
| `0x141501800` | `PhysicsStep_TM` (per-vehicle) |
| `0x140803920` | `NSceneDyna::PhysicsStep_V2` |
| `0x1408025a0` | `NSceneDyna::InternalPhysicsStep` |
| `0x1408427d0` | `NSceneVehiclePhy::ComputeForces` |

### Rendering
| Address | Function |
|---|---|
| `0x1409aa750` | `CDx11Viewport::DeviceCreate` |
| `0x140936810` | `CSystemConfigDisplay` settings registration |
| `0x14095d430` | `CVisionViewport::PrepareShadowAndProjectors` |
| `0x14097cfb0` | `VisionShader::GetOrCreate` (shader cache) |
| `0x140a811a0` | `Dxgi_Present_HookCallback` |

### File Formats
| Address | Function |
|---|---|
| `0x140904730` | `CSystemArchiveNod::LoadGbx` (main entry) |
| `0x140900e60` | GBX header magic/version validation |
| `0x140901850` | GBX version 6 format flag parsing |
| `0x1402cf380` | `CreateByMwClassId` (class factory) |
| `0x1402f2610` | Class ID backward-compatibility remap |
| `0x141ff9d58` | Global class registry (data) |

### Profiling
| Address | Function |
|---|---|
| `0x140117690` | Profile tag begin (called at start of most functions) |
| `0x1401176a0` | Profile tag end |

---

## 8. Open Questions

Status tracking for all documented unknowns. Updated 2026-03-27 after full gap analysis across all 29 research documents (waves 1-3).

### 8.1 Resolved Questions

These questions from the original analysis have been answered by subsequent research:

| Original Question | Resolution | Source |
|---|---|---|
| What are the 7 force model cases (switch at +0x1790)? | 7 cases identified: 0/1/2 (base/legacy), 3 (M4), 4 (M5/TMNF-era), 5 (CarSport/Stadium), 6 (Snow/Rally), 0xB/11 (Desert). Vehicle-to-model mapping remains SPECULATIVE. | [10-physics-deep-dive.md](10-physics-deep-dive.md) Section 2 |
| Where is gravity 9.81 stored? | GravityCoef is a normalized 0-1 value (not m/s^2). Base gravity likely in .Gbx resource files. `DefaultGravitySpawn` provides initial config. GravityCoef API is deprecated in favor of `SetPlayer_Delayed_AccelCoef`. | [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 5 |
| Is Vulkan/D3D12 reachable or dead code? | D3D12 shader infrastructure exists (root signatures, parameter types) but D3D11 is the sole active renderer. Vulkan has 1 string reference, no API calls. Both are effectively dead code in TM2020. | [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 9 |
| Complete G-buffer layout | 9 named render targets identified: MDiffuse, MSpecular, PixelNormalInC, FaceNormalInC, VertexNormalInC, DeferredZ, LightMask, PreShade, DiffuseAmbient. Core MRT is 4 targets + depth. Exact DXGI formats remain SPECULATIVE. | [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 7, [11-rendering-deep-dive.md](11-rendering-deep-dive.md) Section 2 |
| TXAA implementation details | Dual implementation: NVIDIA GFSDK TXAA (hardware path) + Ubisoft custom UBI_TXAA (fallback). Uses motion vector-based temporal reprojection via CameraMotion pass. | [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 8 |
| Compression algorithm for GBX body chunks | **LZO1X** confirmed for GBX body compression from real file analysis. zlib strings exist in the binary but are used for other data (lightmap/ghost). Both are present. | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 8, [26-real-file-analysis.md](26-real-file-analysis.md) Section 2, [29-community-knowledge.md](29-community-knowledge.md) Section 2 |
| Force model cases 0/1/2 internals | 4-wheel base model fully decompiled (300+ lines). Per-wheel surface lookup, anti-roll bar, speed-dependent coefficients from curves, engine braking torque. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 1 |
| Force model case 3 (2-wheel) | Bicycle-model physics with 3-state drift state machine (none/building/committed), Pacejka-like lateral grip, yaw damping. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 1 |
| Force model case 6 (CarSport) | Full CarSport/Stadium force model decompiled (350+ lines). 9 sub-functions: per-wheel, steering, suspension, anti-roll, damping, drift, boost, airborne, integration. Launched checkpoint boost and post-respawn force systems. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 1 |
| All 22 surface gameplay effects | Full `EPlugSurfaceGameplayId` enum resolved: Turbo, Turbo2, NoGrip, NoSteering, NoBrakes, Fragile, Bouncy, FreeWheeling, SlowMotion, ReactorBoost, VehicleTransform (Rally/Snow/Desert), Cruise, etc. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 2 |
| Tire contact model | Pacejka-like model decompiled for 2-wheel case: `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 1 |
| Drift state machine | 3-state machine: 0=none, 1=building (slip accumulation), 2=committed (stored angle). Drift builds proportional to `lateral_slip * drift_rate * dt`. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 1 |
| Audio engine architecture | OpenAL Soft via `OpenAL64_bundled.dll`, 3-layer stack (CAudioManager -> CAudioPort -> OpenAL), 7 audio source types, Vivox 5.19.2 voice chat, XOR/ADD obfuscated function pointers. | [24-audio-deep-dive.md](24-audio-deep-dive.md) Section 1-2 |
| Ghost/replay system API | 27 ghost API functions documented. Full ManiaScript ghost interface. XML format replay header extracted. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 3 |
| Map loading pipeline | 23-stage pipeline documented from CGameCtnChallenge. Items via CGameCtnAnchoredObject. 12+ block info types. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 4, [28-map-structure-encyclopedia.md](28-map-structure-encyclopedia.md) Section 6 |
| Pack file system | Full lifecycle: install, setup, teardown. Encrypted packages with per-account keys. GBX body dispatch for 7 data types. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 7 |
| NadeoPak header format | "NadeoPak" magic confirmed (not GBX). .pak files are NOT .pack.gbx files. | [26-real-file-analysis.md](26-real-file-analysis.md) Section 10 |
| GBX format byte-exact validation | 5 files verified byte-exact against spec: Map, Profile, Block, FuncShader, ImageGen. All TM2020 files use version 6. | [26-real-file-analysis.md](26-real-file-analysis.md) Sections 2-9 |
| Checkpoint/respawn physics | Launched checkpoints apply directional boost forces with speed-dependent curves. Respawn forces fade out over 2x stored duration. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 6 |
| Reference table format details | Full specification documented: num_external_nodes, ancestor_level, folder paths, per-reference entries with flags. Max 49,999 external references. | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 5 |
| JSON/XML GBX variant details | XML GBX loaded via `FUN_140925fa0`, JSON via `FUN_140934b80`. Binary format (byte 0 = 'B') is primary; text format ('T') is recognized syntactically but functional support is UNKNOWN. | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 1 |
| Complete game state enumeration | 60+ states documented across 9 phases: Bootstrap (0x000-0x3FF), Startup (0x484-0x4F9), Connection (0x501-0x61D), Online (0x636-0x6D7), Dialog (0x733-0x852), Menu Result (0x9A5-0xAFF), Gameplay (0xB43-0xCC6), Map Loading (0xCD1-0xDE5), Replay/Podium (0xE14-0xF3D). | [12-architecture-deep-dive.md](12-architecture-deep-dive.md) Section 1 |
| Memory management strategy | Reference counting at CMwNod+0x10, SSO strings (16 bytes, up to 11 inline), fiber-based coroutine system (88 bytes per CMwCmdFiber). | [12-architecture-deep-dive.md](12-architecture-deep-dive.md) Section 7 |
| Thread model | Dual thread pool: Windows ThreadPool API (timers, waits, work items) + custom NClassicThreadPool (AddJobs/TaskWaitComplete fork-join pattern). | [15-ghidra-research-findings.md](15-ghidra-research-findings.md) Section 6 |

### 8.2 Partially Resolved Questions

These have been investigated but not fully answered:

| Original Question | Current Status | What Remains | Source |
|---|---|---|---|
| Full wheel/tire contact model | Per-wheel fields documented. Wheel order: FL(0), FR(1), RR(2), RL(3). Base 4-wheel model (FUN_140869cd0) and CarSport model (FUN_14085c9e0) now decompiled. Pacejka-like lateral grip formula for 2-wheel model. | CarSport per-wheel sub-function FUN_1408570e0 not yet decompiled. Exact camber formulas unknown. | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 1, [19-openplanet-intelligence.md](19-openplanet-intelligence.md) Section 3 |
| Complete chunk ID table | 6 map header chunk IDs documented (0x03043002-0x03043008). 200+ legacy class ID remappings documented. | Full body chunk ID catalog for all 431 .Gbx file types not yet built. | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Sections 4, 11 |
| How deterministic physics works across platforms | Forward Euler integration with adaptive sub-stepping confirmed. Fixed-order network update cycle (BeforePhy/AfterPhy/Synchronize). Input lockstep model. | Exact floating-point determinism guarantees unknown. Whether IEEE 754 strict mode is enforced unknown. Cross-platform bit-exactness mechanism not confirmed. | [10-physics-deep-dive.md](10-physics-deep-dive.md) Section 10, [17-networking-deep-dive.md](17-networking-deep-dive.md) Section 7 |

### 8.3 Still Open Questions

These remain unanswered:

#### Binary Protection
- [ ] What packer/protector is used? (.A2U, .9Bv, .D." sections with random names)
- [ ] What do the 3 TLS callbacks do? (anti-debug? unpacking? integrity check?)
- [ ] How are the remaining imports resolved at runtime? (only 35 imported symbols visible)

#### Physics
- [ ] Exact vehicle type to force model mapping (CarSport=6 likely based on doc 22, but not VERIFIED from a dispatch table)
- [ ] Force model cases 4 (FUN_14086bc50), 5 (FUN_140851f00), and 0xB/11 (FUN_14086d3b0) -- not yet decompiled
- [ ] Per-wheel sub-function FUN_1408570e0 (CarSport model) -- not yet decompiled
- [ ] Airborne control model FUN_14085c1b0 -- not yet decompiled
- [ ] Boost/reactor force model FUN_140857b20 -- not yet decompiled
- [ ] Whether the turbo force truly ramps UP linearly (doc 10 says yes, but this is counterintuitive and contradicts TMNF behavior per doc 14) -- needs independent verification
- [ ] Exact tick rate: 100 Hz is PLAUSIBLE but never confirmed from a decompiled constant (see [18-validation-review.md](18-validation-review.md) Issue 25)
- [ ] Vehicle transform transition physics (Stadium -> Rally -> Snow -> Desert surface changes)

#### Rendering
- [ ] Exact DXGI formats for each G-buffer render target (only depth format VERIFIED from D3D11 log)
- [ ] Normal buffer encoding scheme (three separate normal buffers is unusual -- exact packing/encoding unknown)
- [ ] Lightmap format and baking pipeline
- [ ] LOD system details (GeomLodScaleZ parameter exists but LOD computation unknown)
- [ ] Impostor system for distant objects (DeferredOutput_ImpostorConvert_c.hlsl exists)
- [ ] PBR material parameter mapping (GGX BRDF constants, roughness/metallic encoding)

#### File Formats
- [ ] Full body chunk ID catalog across all 431 .Gbx extensions
- [x] LookbackString flag 0b01 meaning -- RESOLVED: both 0b01 and 0b11 mean "new inline string"; TM2020 uses 0b01 (0x40000000) exclusively ([26-real-file-analysis.md](26-real-file-analysis.md), [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) Section 29)
- [ ] Ghost/replay binary serialization format details (chunk IDs, field layout) -- API documented (27 functions) but binary format not fully parsed
- [ ] Ghost sample encoding -- community documents int16/int8 encoding for position/rotation/speed, needs integration ([29-community-knowledge.md](29-community-knowledge.md) Section 6.2)
- [ ] Item mesh vertex format in .Item.Gbx (CPlugSolid2Model internal layout)
- [ ] Embedded lightmap data format within map files
- [ ] Pack file binary body format (header documented via NadeoPak magic, body structure unknown)

#### Networking
- [ ] Is HTTP/3 (QUIC) actively used or just linked? (OpenSSL 1.1.1t+quic is statically linked)
- [ ] Full packet format for the UDP game protocol
- [ ] Matchmaking algorithm details
- [ ] Anti-cheat replay verification server-side logic
- [x] API endpoint catalog -- 80+ endpoints documented across Core/Live/Meet APIs from community sources ([29-community-knowledge.md](29-community-knowledge.md) Section 4)
- [ ] WebSocket vs raw TCP for real-time game protocol

#### Audio
- [x] OpenAL initialization -- fully documented: dynamic loading, device opening, context creation, EFX check, source counting ([24-audio-deep-dive.md](24-audio-deep-dive.md) Section 2)
- [x] Engine sound model -- layered throttle/release/idle/limiter system with CPlugSoundEngine and CPlugSoundEngine2 ([22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) Priority 5, [24-audio-deep-dive.md](24-audio-deep-dive.md) Section 4)
- [ ] OpenAL source pooling strategy and runtime limit handling
- [ ] Spatial audio zone blending algorithm (zones documented, blending unknown)
- [ ] Music crossfade/transition system

#### ManiaScript
- [ ] Complete built-in function/method catalog
- [ ] Script-to-engine binding mechanism (how CScriptInterfacableValue resolves)
- [ ] Coroutine scheduling order (sleep/yield/wait/meanwhile semantics beyond token names)
- [ ] Script sandboxing and security model
- [ ] Performance characteristics (interpreted vs JIT?)

#### Editor
- [x] Block placement coordinate system -- 32m grid on X/Z, 8m Y sub-unit, items use free Vec3 ([28-map-structure-encyclopedia.md](28-map-structure-encyclopedia.md) Section 1)
- [x] Map validation constraints -- waypoint connectivity, start/finish/checkpoint rules documented ([28-map-structure-encyclopedia.md](28-map-structure-encyclopedia.md) Section 8)
- [ ] Block placement validation rules (connectivity and adjacency constraints)
- [ ] Item pivot/placement offset system
- [ ] Undo/redo implementation

### 8.4 New Questions Discovered During Research

These are questions that were NOT in the original open questions list but emerged from the deep-dive analyses:

#### From Validation Review (doc 18)
- [ ] Why does the turbo boost ramp UP instead of decaying? Is this intentional or a decompilation misread? (CRITICAL for recreation -- see [18-validation-review.md](18-validation-review.md) Issue 6)
- [ ] Fragile surface check: unsigned underflow means nibble values 0 and 1 ALSO trigger fragile, not just 4+. Is this intentional game behavior or a bug? (Issue 12)
- [ ] Sleep threshold DAT_141ebcd04: what is the actual numeric value stored there? (Issue 10)
- [ ] The physics model pointer discrepancy: vehicle+0x88 vs vehicle+0x1BB0 serve different purposes -- which is the physics model vs the visual model? (Issue 39)

#### From Openplanet Intelligence (doc 19)
- [ ] Vehicle VisState manager index has shifted 5 times since 2022. How stable are these offsets between game patches?
- [ ] Entity ID masks (0x02000000 = local, 0x04000000 = replay) -- are there other masks?
- [ ] CamGrpStates bytes change during vehicle transform -- what do they encode?
- [ ] ReactorFinalTimer counts 0-1 in final second -- what triggers the "final second" determination?

#### From Architecture Deep Dive (doc 12)
- [ ] The 0x380-byte coroutine context object: what are all fields beyond the documented ones?
- [ ] Virtual method dispatch table layout for CGameCtnApp (30+ virtual calls identified by offset)
- [ ] The `/smoketest` and `/validatepath` command-line arguments -- what do they do exactly?

#### From Cross-Reference Analysis (doc 14)
- [ ] Sub-step cap changed from 10,000 (TMNF) to 1,000 (TM2020) -- why? Performance? Stability?
- [ ] TMNF had 4 force models, TM2020 has 7+. Which new models correspond to which new vehicle types?
- [ ] CGameManiaPlanet abstraction layer: what platform-specific behavior does it encapsulate?

#### From File Format Deep Dive (doc 16)
- [ ] The FACADE01 sentinel dual usage: as a chunk end marker in the file stream AND as a return value in class ID checking. Are these related or coincidental? (see [18-validation-review.md](18-validation-review.md) Issue 29)
- [ ] Pack file internal structure beyond the header (NadeoPak body format)
- [ ] How does the two-level class registry at DAT_141ff9d58 handle collisions or versioning?

#### From Wave 2+3 Research (docs 22-29)
- [ ] Per-wheel CarSport sub-function FUN_1408570e0 -- called 4 times but not yet decompiled
- [ ] Harbour SDK integration in VoiceChat.dll -- Nadeo's voice wrapper around Vivox
- [ ] Anzu in-game advertising DLL -- what ad formats and when are ads shown?
- [ ] 103 UPC (Ubisoft Connect) exported functions -- full API surface ([27-dll-intelligence.md](27-dll-intelligence.md) Section 3)
- [ ] 10 vehicle-related file paths in DLLs ([27-dll-intelligence.md](27-dll-intelligence.md))
- [ ] OpenAL function pointer XOR/ADD obfuscation purpose -- anti-tamper or anti-cheat? ([24-audio-deep-dive.md](24-audio-deep-dive.md) Section 2)
- [ ] 1,112 shader files in GpuCache -- shader variant system and compilation pipeline ([26-real-file-analysis.md](26-real-file-analysis.md) Section 11)
- [ ] Ghost sample encoding: precise int16/int8 to float mappings for replay data need integration from community docs ([29-community-knowledge.md](29-community-knowledge.md) Section 6.2)

### 8.5 What We Still Do Not Know -- Summary by Subsystem

| Subsystem | Knowledge Level | Critical Gaps |
|---|---|---|
| **Physics core pipeline** | ~85% | 3 of 7 force models decompiled, Pacejka-like tire model known, 3 models + sub-functions remain |
| **Vehicle state structure** | ~70% | Reflection-based offsets from 81 Openplanet plugins, ~30% unmapped |
| **Rendering pipeline** | ~65% | G-buffer exact formats, PBR parameters, lightmap pipeline, 1112 shaders catalogued but not analyzed |
| **GBX file format** | ~85% | 5 files byte-exact validated, LZO1X confirmed, body chunk catalog incomplete, ghost binary format partial |
| **Networking** | ~55% | 80+ API endpoints from community, UDP game protocol still unknown, matchmaking unknown |
| **Audio** | ~70% | Full 3-layer architecture documented, OpenAL init decompiled, 7 source types, spatial zone blending unknown |
| **ManiaScript** | ~35% | Token table complete but runtime semantics, built-in API, scheduling unknown |
| **Input** | ~60% | Frame update documented but binding system, action mapping incomplete |
| **Camera** | ~70% | All camera types enumerated, orbital math documented, race cam internals unknown |
| **Editor** | ~40% | Block grid (32m), waypoint system, validation rules, 23-stage map loading documented |
| **Map structure** | ~75% | 32m grid, block types, waypoint system, item placement, surface materials documented |
| **UI/ManiaLink** | ~20% | CControl class hierarchy mapped but layout engine, rendering pipeline unknown |
| **Replay/Ghost** | ~50% | 27 ghost API functions, XML header format, community sample encoding; binary serialization format partial |
| **DLL ecosystem** | ~80% | All 13 DLLs analyzed, SDK versions catalogued, dependency map built |
| **Community tools** | ~75% | GBX.NET confirmed, 80+ API endpoints, TMInterface TAS tools, Openplanet ecosystem mapped |

---

## 9. Detailed Reports

| # | Report | Lines | Focus |
|---|---|---:|---|
| 01 | [Binary Overview](01-binary-overview.md) | 291 | PE headers, sections, imports, exports, protection |
| 02 | [Class Hierarchy](02-class-hierarchy.md) | 693 | 2,027 classes, RTTI system, subsystem mapping |
| 04 | [Physics & Vehicle](04-physics-vehicle.md) | 840 | Simulation pipeline, forces, collision, surfaces |
| 05 | [Rendering & Graphics](05-rendering-graphics.md) | 811 | D3D11, deferred pipeline, shaders, post-FX |
| 06 | [File Formats](06-file-formats.md) | 698 | GBX parsing, serialization, map loading |
| 07 | [Networking](07-networking.md) | 1,149 | Protocol layers, auth, API, voice/text chat |
| 08 | [Game Architecture](08-game-architecture.md) | 821 | Entry point, game loop, state machine, fibers |
| 09 | [Game Files Analysis](09-game-files-analysis.md) | 1,369 | .pak files, shader cache, config files |
| 10 | [Physics Deep Dive](10-physics-deep-dive.md) | 1,914 | Force models, sub-stepping, surface effects |
| 11 | [Rendering Deep Dive](11-rendering-deep-dive.md) | 1,823 | G-buffer, shadows, post-processing, HBAO+ |
| 12 | [Architecture Deep Dive](12-architecture-deep-dive.md) | 2,169 | State machine, 60+ states, coroutines, memory |
| 13 | [Subsystem Class Map](13-subsystem-class-map.md) | 3,008 | Complete class-to-subsystem mapping |
| 14 | [TMNF Cross-Reference](14-tmnf-crossref.md) | 734 | TM2020 vs TMNF differences |
| 15 | [Ghidra Research Findings](15-ghidra-research-findings.md) | 410 | Audio, input, camera, compression, gravity, threads |
| 16 | [File Format Deep Dive](16-fileformat-deep-dive.md) | 2,898 | GBX byte-level spec, LZO1X, chunk parsing, TypeScript parser |
| 17 | [Networking Deep Dive](17-networking-deep-dive.md) | 3,141 | 10-layer stack, auth flow, API tasks, XML-RPC |
| 18 | [Validation Review](18-validation-review.md) | 477 | Cross-doc consistency, 40 issues tracked |
| 19 | [Openplanet Intelligence](19-openplanet-intelligence.md) | 657 | Memory offsets, VehicleState, entity IDs |
| 20 | [Browser Recreation Guide](20-browser-recreation-guide.md) | 3,422 | WebGL/Web Audio implementation guide |
| 21 | [Competitive Mechanics](21-competitive-mechanics.md) | 943 | Matchmaking, rankings, anti-cheat |
| 22 | [Ghidra Gap Findings](22-ghidra-gap-findings.md) | 761 | Force models 0/1/2/3/6, surface effects, drift, Pacejka |
| 23 | [Visual Reference](23-visual-reference.md) | 1,673 | Diagrams, architecture charts, data flow |
| 24 | [Audio Deep Dive](24-audio-deep-dive.md) | 1,059 | OpenAL Soft, 3-layer stack, Vivox 5.19.2, Web Audio mapping |
| 25 | [Openplanet Deep Mining](25-openplanet-deep-mining.md) | 1,237 | 81 plugins, reflection offsets, memory layouts |
| 26 | [Real File Analysis](26-real-file-analysis.md) | 993 | 5 files byte-exact, NadeoPak header, 1112 shaders |
| 27 | [DLL Intelligence](27-dll-intelligence.md) | 1,169 | 13 DLLs, 103 UPC functions, SDK versions, Harbour |
| 28 | [Map Structure Encyclopedia](28-map-structure-encyclopedia.md) | 1,227 | 32m grid, waypoints, 23-stage loading, block types |
| 29 | [Community Knowledge](29-community-knowledge.md) | 729 | GBX.NET, 80+ API endpoints, ghost encoding, TMInterface |

---

## 10. Decompiled Code Index

### Architecture (23 files, ~380 KB)
- `entry.c` - Obfuscated entry point
- `WinMainCRTStartup.c` / `WinMain_thunk.c` - CRT bootstrap
- `CGbxGame__InitApp.c` - Engine init
- `CGbxApp__Init1.c` (80 KB) - First-phase initialization
- `CGameCtnApp__UpdateGame.c` (216 KB) - Main game loop state machine
- `CGameCtnApp__Start.c` - Game start sequence
- `CGameManiaPlanet__Start.c` - ManiaPlanet startup
- `CGameCtnNetwork__MainLoop_*.c` - Network state handlers
- `CScriptEngine__Run.c` - ManiaScript execution
- `CSystemEngine__InitForGbxGame.c` - System engine init
- Plus profiling, fiber, and startup helpers

### Physics (26 files, ~95 KB)
- `PhysicsStep_TM.c` - Per-vehicle physics step
- `NSceneDyna__PhysicsStep_V2.c` - Rigid body dynamics
- `NSceneVehiclePhy__ComputeForces.c` - Vehicle force computation
- `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c` - Pre-dynamics update
- `NHmsCollision__StartPhyFrame.c` / `MergeContacts.c` - Collision system
- `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c` - Gravity/sleep
- `NSceneDyna__ComputeWaterForces.c` - Water physics
- `force_model_4wheel_FUN_140869cd0.c` - Base 4-wheel force model (cases 0/1/2)
- `force_model_2wheel_FUN_14086b060.c` - 2-wheel bicycle model (case 3)
- `force_model_carsport_FUN_14085c9e0.c` - CarSport/Stadium full model (case 6)
- `lateral_grip_2wheel_FUN_14086af20.c` - Pacejka-like lateral grip
- `curve_sampler_FUN_14042bcb0.c` - Speed-dependent coefficient sampling
- `surface_type_FUN_140845b60.c` - Surface material lookup
- `slope_factor_FUN_1408456b0.c` - Slope angle physics factor
- Plus friction config, contact processing, visual state extraction

### Rendering (5 files, ~53 KB)
- `CDx11Viewport_DeviceCreate_*.c` - D3D11 device creation
- `CSystemConfigDisplay_*.c` - Display settings registration
- `CVisionViewport_PrepareShadowAndProjectors_*.c` - Shadow setup
- `NSysCfgVision_SSSAmbOcc_HBAO_*.c` - HBAO+ configuration
- `Vision_VisionShader_GetOrCreate_*.c` - Shader cache

### File Formats (9 files, ~19 KB)
- `FUN_140904730_LoadGbx.c` - Main GBX load entry
- `FUN_140900e60_LoadHeader.c` - Magic/version validation
- `FUN_140901850_ParseVersionHeader.c` - Version 6 format flags
- `FUN_1402cf380_CreateByMwClassId.c` - Class factory
- `FUN_1402f2610_ClassIdRemap.c` - Legacy compatibility
- `FUN_1402d0c40_ChunkEndMarker.c` - FACADE01 sentinel

### Audio (1 file, ~4 KB)
- `COalAudioPort_InitImplem.c` - OpenAL Soft initialization (dynamic loading, device, context, EFX)

### Networking (4 files, ~5 KB)
- `CGameCtnNetwork_ConnectToInternet.c` - Internet connection init
- `CNetHttpClient_CreateRequest.c` / `InternalConnect.c` - HTTP client
- `nadeoservices_token_create_from_ubiservices.c` - Auth token exchange

---

*This document was generated by automated parallel Ghidra analysis across 29 research documents. All function identifications are based on embedded debug/profiling strings, not debug symbols (the binary is fully stripped). Items marked [UNKNOWN] require further investigation and should not be assumed. Last updated 2026-03-27.*

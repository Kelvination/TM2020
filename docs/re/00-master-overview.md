# Trackmania 2020 Reverse Engineering

Trackmania 2020 is an arcade racing game built on Nadeo's proprietary ManiaPlanet/GameBox engine -- a mature C++ engine dating back to the original TrackMania (2003). This documentation covers a comprehensive reverse engineering analysis of the fully symbol-stripped binary, recovering architecture, physics, rendering, file formats, and networking details.

## What you will find here

This project documents the internals of `Trackmania.exe` through static analysis using Ghidra. Despite having no debug symbols, the binary embeds profiling strings in nearly every function (e.g., `"ClassName::MethodName"`), which enabled identification of hundreds of functions by name.

The documentation spans 29 detailed reports organized by subsystem. Start with this page for the big picture, then follow links to the topics you need.

**If you want to understand...**

| Topic | Start here |
|---|---|
| How the binary is structured | [01-binary-overview.md](01-binary-overview.md) |
| The class system and 2,027 engine classes | [02-class-hierarchy.md](02-class-hierarchy.md) |
| Engine architecture and game loop | [08-game-architecture.md](08-game-architecture.md) |
| Vehicle physics and simulation | [04-physics-vehicle.md](04-physics-vehicle.md), [10-physics-deep-dive.md](10-physics-deep-dive.md) |
| Rendering and graphics pipeline | [05-rendering-graphics.md](05-rendering-graphics.md), [11-rendering-deep-dive.md](11-rendering-deep-dive.md) |
| GBX file formats | [06-file-formats.md](06-file-formats.md), [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) |
| Networking and online services | [07-networking.md](07-networking.md), [17-networking-deep-dive.md](17-networking-deep-dive.md) |
| Map structure and blocks | [28-map-structure-encyclopedia.md](28-map-structure-encyclopedia.md) |

## Key statistics

| Metric | Value |
|---|---|
| Total functions | 131,311 |
| Defined strings | 52,890 |
| Identified Nadeo classes | 2,027 |
| Classes with known methods | 276 |
| Decompiled functions (this analysis) | 63 |
| PE sections | 11 (3 non-standard) |
| Imported DLLs | 29 (many resolved at runtime) |

## Technology stack

| Component | Technology |
|---|---|
| Graphics API | Direct3D 11 (exclusive at runtime) |
| Rendering | Deferred shading with G-buffer, "Tech3" engine |
| Audio | OpenAL Soft 1.23.99, Ogg Vorbis, 3-layer audio stack |
| Input | DirectInput 8 + XInput 9.1.0 |
| Networking | Winsock2 + libcurl + OpenSSL 1.1.1t+quic (static) |
| DRM | Ubisoft Connect (upc_r2_loader64.dll) |
| Voice Chat | Vivox (VoiceChat.dll, loaded at runtime) |
| Text Chat | XMPP (*.chat.maniaplanet.com) |
| Image Format | libwebp (libwebp64.dll) |
| Scripting | ManiaScript (custom, interpreted) |
| Crypto | bcrypt.dll + OpenSSL (SHA256, HMAC, CRC32/64) |

## How the binary is protected

The binary employs code protection/packing that hides most of its real imports.

- The entry point (`0x14291e317`) lives in a non-standard `.D."` section, not `.text`.
- Three TLS callbacks execute before the main entry point (anti-debug/unpacking).
- Only 35 imported symbols exist across 23 DLLs. Most real imports resolve at runtime via `LoadLibrary`/`GetProcAddress`.
- Three randomly-named sections (`.A2U`, `.9Bv`, `.D."`) contain ~10 MB of executable code.

The `.text` section (25.4 MB) and `.rdata` (5.0 MB) remain unobfuscated, enabling extensive analysis.

See: [01-binary-overview.md](01-binary-overview.md)

## How the engine is structured

The engine follows a layered architecture with singleton subsystems and a deep application class hierarchy.

```
CGbxApp                         -- GameBox application base
  └─> CGameApp                  -- Game application layer
        └─> CGameCtnApp         -- Creation (Ctn) application
              └─> CGameManiaPlanet  -- ManiaPlanet platform layer
                    └─> CTrackMania     -- TrackMania-specific game
```

### Engine subsystems (12 singletons)

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

### Main game loop

No function is named "GameLoop." The game loop lives in `CGameCtnApp::UpdateGame` at `0x140b78f10` -- a 216 KB function implementing a massive state machine. Three nested tiers of state machines drive the game:

1. **Game states**: `GameState_LocalLoopPlaying`, `GameState_NetPlaying`, `GameState_Menus`, etc.
2. **Network states**: `CGameCtnNetwork::MainLoop_Menus`, `MainLoop_PlaygroundPlay`, `MainLoop_SetUp`
3. **Arena states**: `CSmArenaClient::MainLoop_*` for gameplay

### Fiber/coroutine system

`CMwCmdFiber` (88 bytes per instance) provides cooperative multitasking for dialog workflows, network operations, editor save/load, and script execution. The engine includes render-thread collision detection safety checks.

See: [08-game-architecture.md](08-game-architecture.md)

## How the subsystems connect

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

## What the class system looks like

All Nadeo engine objects inherit from CMwNod (the root base class, similar to `NSObject` or `UObject`). Nadeo uses its own class registration system with numeric class IDs (not MSVC RTTI).

| Prefix | Count | Domain |
|---|---:|---|
| `CGame*` | 728 | Game logic, UI, editors, maps, players |
| `CPlug*` | 391 | Assets, materials, meshes, animation |
| `CWebServices*` | 297 | Online service tasks and results |
| `CNet*` | 262 | Networking, protocols, services |
| `CScene*` | 52 | Scene graph, vehicles, effects |
| `CHms*` | 41 | Hierarchical Managed Scene (renderer) |
| `CControl*` | 39 | UI controls |
| `CSystem*` | 24 | System layer (files, config) |
| Others | 193 | Script, XML, Block, Media, etc. |

See: [02-class-hierarchy.md](02-class-hierarchy.md)

## Key findings by domain

### Physics and vehicle simulation

The physics system runs a multi-layer pipeline:
`CSmArenaPhysics` -> `PhysicsStep_TM` -> `NSceneDyna::PhysicsStep_V2` -> `NSceneDyna::InternalPhysicsStep`

Key discoveries:

- **7 force models** selected via switch at vehicle state offset `+0x1790`. Three are fully decompiled: the base 4-wheel model (cases 0/1/2), the 2-wheel bicycle model (case 3), and the CarSport/Stadium model (case 6).
- **Adaptive sub-stepping** divides each physics tick based on velocity, capped at 1000 sub-steps per tick.
- **22 surface gameplay effects** fully enumerated (`EPlugSurfaceGameplayId`): Turbo, Turbo2, NoGrip, NoSteering, NoBrakes, Fragile, Bouncy, FreeWheeling, SlowMotion, ReactorBoost, VehicleTransform variants, and Cruise.
- **Pacejka-like tire model**: `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`
- **3-state drift machine**: none -> building -> committed. Drift builds proportional to `lateral_slip * drift_rate * dt`.

See: [04-physics-vehicle.md](04-physics-vehicle.md) | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) | Decompiled: `decompiled/physics/` (26 files)

### Rendering and graphics

- **D3D11 only** at runtime. Vulkan/D3D12 strings exist but are unused.
- **Deferred shading** with G-buffer as the primary path. Forward rendering handles transparents.
- **NVIDIA HBAO+** for ambient occlusion (20-field configuration struct documented).
- **HDR Bloom** (3 quality levels), filmic tone mapping with auto-exposure.
- **PSSM shadows** (4 cascades) + shadow volumes + shadow cache.
- **GPU-driven particles** with compute shaders and self-shadowing via voxelization.
- **200+ HLSL shader files** organized under Tech3/, Effects/, Engines/, Lightmap/.

See: [05-rendering-graphics.md](05-rendering-graphics.md)

### GBX file formats

- **GBX header** uses magic "GBX" (3 bytes), version uint16 (3-6 supported), and format flags "BUCE"/"BUCR".
- **5 files validated byte-exact** against spec: Map, Profile, Block, FuncShader, ImageGen.
- **LZO1X body compression** confirmed from real files (not zlib).
- **Chunk-based body** with `0xFACADE01` end-of-chunks sentinel.
- **Two-level class registry** at `DAT_141ff9d58` with TLS-cached lookups.
- **200+ legacy class ID remappings** for backward compatibility across engine versions.
- **431 `.Gbx` file extensions** catalogued.

See: [06-file-formats.md](06-file-formats.md) | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) | [26-real-file-analysis.md](26-real-file-analysis.md)

### Networking and online services

- **10-layer architecture** from Winsock2 up to CGameCtnNetwork.
- **Dual TCP+UDP** game protocol.
- **Three-step authentication**: Ubisoft Connect ticket -> UbiServices session -> Nadeo Services token exchange.
- **Full XML-RPC server** (same protocol as TMNF/TM2 dedicated server controllers).
- **200+ API task types** across NadeoServices and UbiServices.
- **Anti-cheat** uses server-side replay verification with chunked upload.

See: [07-networking.md](07-networking.md) | [17-networking-deep-dive.md](17-networking-deep-dive.md)

### ManiaScript engine

- `CScriptEngine::Run` executes scripts with per-script profiling tags.
- The lexer includes 50+ token types, 12 built-in types, 7 directives, and 20+ collection operations.
- The script interface integrates deeply with the class system via `CScriptInterfacableValue`.

## Critical addresses

### Entry and startup

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

### File formats

| Address | Function |
|---|---|
| `0x140904730` | `CSystemArchiveNod::LoadGbx` (main entry) |
| `0x140900e60` | GBX header magic/version validation |
| `0x140901850` | GBX version 6 format flag parsing |
| `0x1402cf380` | `CreateByMwClassId` (class factory) |
| `0x1402f2610` | Class ID backward-compatibility remap |
| `0x141ff9d58` | Global class registry (data) |

## What we still do not know

The table below summarizes knowledge level and critical gaps for each subsystem.

| Subsystem | Knowledge Level | Critical Gaps |
|---|---|---|
| **Physics core pipeline** | ~85% | 3 of 7 force models decompiled; 3 models + sub-functions remain |
| **Vehicle state structure** | ~70% | ~30% of reflection-based offsets unmapped |
| **Rendering pipeline** | ~65% | G-buffer exact formats, PBR parameters, lightmap pipeline |
| **GBX file format** | ~85% | Body chunk catalog incomplete, ghost binary format partial |
| **Networking** | ~55% | UDP game protocol unknown, matchmaking unknown |
| **Audio** | ~70% | Spatial zone blending algorithm unknown |
| **ManiaScript** | ~35% | Runtime semantics, built-in API, scheduling unknown |
| **Editor** | ~40% | Block placement validation, undo/redo implementation |
| **UI/ManiaLink** | ~20% | Layout engine and rendering pipeline unknown |

For a detailed list of every open question, see the full open questions section further down.

## Detailed reports

| # | Report | Focus |
|---|---|---|
| 01 | [Binary Overview](01-binary-overview.md) | PE headers, sections, imports, exports, protection |
| 02 | [Class Hierarchy](02-class-hierarchy.md) | 2,027 classes, RTTI system, subsystem mapping |
| 04 | [Physics & Vehicle](04-physics-vehicle.md) | Simulation pipeline, forces, collision, surfaces |
| 05 | [Rendering & Graphics](05-rendering-graphics.md) | D3D11, deferred pipeline, shaders, post-FX |
| 06 | [File Formats](06-file-formats.md) | GBX parsing, serialization, map loading |
| 07 | [Networking](07-networking.md) | Protocol layers, auth, API, voice/text chat |
| 08 | [Game Architecture](08-game-architecture.md) | Entry point, game loop, state machine, fibers, deep dive |
| 09 | [Game Files Analysis](09-game-files-analysis.md) | .pak files, shader cache, config files |
| 10 | [Physics Deep Dive](10-physics-deep-dive.md) | Force models, sub-stepping, surface effects |
| 11 | [Rendering Deep Dive](11-rendering-deep-dive.md) | G-buffer, shadows, post-processing, HBAO+ |
| 14 | [TMNF Cross-Reference](14-tmnf-crossref.md) | TM2020 vs TMNF differences |
| 15 | [Ghidra Research Findings](15-ghidra-research-findings.md) | Audio, input, camera, compression, gravity, threads |
| 16 | [File Format Deep Dive](16-fileformat-deep-dive.md) | GBX byte-level spec, LZO1X, chunk parsing |
| 17 | [Networking Deep Dive](17-networking-deep-dive.md) | 10-layer stack, auth flow, API tasks, XML-RPC |
| 18 | [Validation Review](18-validation-review.md) | Cross-doc consistency, 40 issues tracked |
| 19 | [Openplanet Intelligence](19-openplanet-intelligence.md) | Memory offsets, VehicleState, entity IDs |
| 20 | [Browser Recreation Guide](20-browser-recreation-guide.md) | WebGL/Web Audio implementation guide |
| 21 | [Competitive Mechanics](21-competitive-mechanics.md) | Matchmaking, rankings, anti-cheat |
| 22 | [Ghidra Gap Findings](22-ghidra-gap-findings.md) | Force models 0/1/2/3/6, surface effects, drift |
| 23 | [Visual Reference](23-visual-reference.md) | Diagrams, architecture charts, data flow |
| 24 | [Audio Deep Dive](24-audio-deep-dive.md) | OpenAL Soft, 3-layer stack, Vivox |
| 25 | [Openplanet Deep Mining](25-openplanet-deep-mining.md) | 81 plugins, reflection offsets |
| 26 | [Real File Analysis](26-real-file-analysis.md) | 5 files byte-exact, NadeoPak header |
| 27 | [DLL Intelligence](27-dll-intelligence.md) | 13 DLLs, 103 UPC functions, SDK versions |
| 28 | [Map Structure Encyclopedia](28-map-structure-encyclopedia.md) | 32m grid, waypoints, 23-stage loading |
| 29 | [Community Knowledge](29-community-knowledge.md) | GBX.NET, 80+ API endpoints, TMInterface |

## Decompiled code index

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
- `force_model_4wheel_FUN_140869cd0.c` - Base 4-wheel force model (cases 0/1/2)
- `force_model_2wheel_FUN_14086b060.c` - 2-wheel bicycle model (case 3)
- `force_model_carsport_FUN_14085c9e0.c` - CarSport/Stadium full model (case 6)
- Plus collision, water forces, curve sampling, surface lookup

### Rendering (5 files, ~53 KB)
- `CDx11Viewport_DeviceCreate_*.c` - D3D11 device creation
- `CSystemConfigDisplay_*.c` - Display settings registration
- `CVisionViewport_PrepareShadowAndProjectors_*.c` - Shadow setup
- `NSysCfgVision_SSSAmbOcc_HBAO_*.c` - HBAO+ configuration
- `Vision_VisionShader_GetOrCreate_*.c` - Shader cache

### File formats (9 files, ~19 KB)
- `FUN_140904730_LoadGbx.c` - Main GBX load entry
- `FUN_140900e60_LoadHeader.c` - Magic/version validation
- `FUN_1402cf380_CreateByMwClassId.c` - Class factory
- `FUN_1402f2610_ClassIdRemap.c` - Legacy compatibility

### Networking (4 files, ~5 KB)
- `CGameCtnNetwork_ConnectToInternet.c` - Internet connection init
- `CNetHttpClient_CreateRequest.c` / `InternalConnect.c` - HTTP client
- `nadeoservices_token_create_from_ubiservices.c` - Auth token exchange

## Related Pages

- [01-binary-overview.md](01-binary-overview.md) -- PE structure and binary protection
- [02-class-hierarchy.md](02-class-hierarchy.md) -- Complete class system and subsystem map
- [08-game-architecture.md](08-game-architecture.md) -- Engine architecture and deep dive

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**File size**: 45,467,720 bytes (43.4 MB)
**Format**: PE32+ x86-64, Windows GUI
**Image base**: `0x140000000`
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra headless bridge
**Analyst**: Automated multi-agent analysis with manual oversight

</details>

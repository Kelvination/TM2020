# Class Hierarchy and Namespace Structure

Trackmania 2020 runs on Nadeo's ManiaPlanet/GameBox (GBX) engine. The engine registers 2,027 Nadeo classes and 55 MSVC RTTI classes. Every Nadeo class inherits from a single root: CMwNod.

This page maps the class hierarchy, naming conventions, subsystem prefixes, and inheritance patterns extracted from the binary.

---

## How Nadeo names its classes

Every Nadeo class follows the C-prefix naming convention. The general pattern is:

```
C<Subsystem><SubFamily><SpecificName>[_Suffix]
```

- **C**: Mandatory prefix on every Nadeo class.
- **Subsystem**: Top-level engine module (e.g., `Game`, `Plug`, `Mw`, `Hms`, `Net`).
- **SubFamily**: Functional group within the subsystem (e.g., `Ctn`, `Editor`, `Script`).
- **SpecificName**: The concrete class name.
- **_Suffix**: Optional variant/specialization (e.g., `_Deprecated`, `_ReadOnly`, `_Script`).

### Subsystem prefix inventory

| Prefix          | Count | Role                                                          |
|-----------------|------:|---------------------------------------------------------------|
| `CGame*`        |   728 | Game logic, UI, editors, maps, players, scoring               |
| `CPlug*`        |   391 | Plugin/resource system (assets, materials, visuals, animation)|
| `CWebServices*` |   297 | Web services tasks and result types (Nadeo/Ubisoft online)    |
| `CNet*`         |   262 | Networking, online services, Ubisoft Connect, XMPP            |
| `CScene*`       |    52 | Scene graph, rendering, vehicles, effects                     |
| `CHms*`         |    41 | Hierarchical Managed Scene (zone/portal renderer)             |
| `CControl*`     |    39 | UI controls (buttons, labels, frames, grids)                  |
| `CSystem*`      |    24 | System layer (files, config, platform, memory)                |
| `CMap*`         |    23 | Map editor scripting API wrappers                             |
| `CAudio*`       |    19 | Audio engine, sources, zones, scripting                       |
| `CInput*`       |    17 | Input devices, pads, keyboard, DirectInput                    |
| `CMw*`          |    17 | ManiaPlanet core/base (Nod, Cmd, Engine, Id)                  |
| `CSm*`          |    11 | ShootMania game mode classes (arena, players)                 |
| `CXml*`         |    10 | XML/JSON parsing and XmlRpc                                   |
| `CScript*`      |     9 | Script engine, events, traits                                 |
| `CBlock*`       |     9 | Block model system (clips, units, variants)                   |
| `CVision*`      |     9 | Vision rendering backend (viewports, shaders, resources)      |
| `CInteraction*` |     5 | Editor interaction modes                                      |
| `CTrackMania*`  |     4 | TrackMania-specific top-level classes                         |
| `CFast*`        |     4 | Fast utility algorithms (CRC, hash, strings)                  |
| `CHttp*`        |     4 | HTTP client                                                   |
| `CManager*`     |     4 | Abstract manager pattern (client/server)                      |
| `CMedia*`       |     4 | MediaTracker scripting API wrappers                           |
| `CServer*`      |     4 | Dedicated server plugin system                                |
| `CUser*`        |     4 | User profiles and prestige                                    |
| `CDx*`          |     3 | DirectX 11 rendering (context, texture, viewport)             |
| `CTitle*`       |     3 | Title/game pack management                                    |
| `CGbx*`         |     2 | GBX application bootstrap                                     |
| Other C*        |    25 | Miscellaneous (Crystal, Dialogs, Ghost, Hud, Replay, etc.)   |

### Non-C-prefix classes

Four classes break the C-prefix convention:

- `Clouds` -- [UNKNOWN] purpose, possibly internal scene element
- `Cluster` -- [UNKNOWN] purpose, possibly spatial partitioning
- `ConnectionClient` -- Likely a network connection abstraction
- `ConsoleClient` -- Likely a debug console client

These appear to be internal/helper types still registered in the engine class system.

---

## CMwNod: the universal base class

CMwNod sits at the root of the entire class hierarchy. The engine's custom RTTI system and object factory revolve around it.

### Evidence from the binary

| Address          | String                                              | Significance                           |
|------------------|-----------------------------------------------------|----------------------------------------|
| `0x141b71fc8`    | `"CMwNod"`                                          | Class name registration string         |
| `0x141b71fd0`    | `"CMwNod::MwNod_StaticInit"`                        | Static initialization function name    |
| `0x141b71f60`    | `"[MwNod] Trying to CreateByMwClassId('"`           | Factory method error string            |
| `0x141b71fa0`    | `"[MwNod] Trying to CreateByMwClassId("`            | Factory method error string (variant)  |
| `0x141b58728`    | `"Parameter is not a CMwNod."`                      | Type-check assertion                   |
| `0x141c0cab0`    | `" CMwNod"`                                         | Possibly used in class info display    |

### Class registration / RTTI system

The Nadeo engine implements its own RTTI system separate from MSVC RTTI.

**Class ID (MwClassId)**: Each class has a numeric class ID used for serialization and factory creation. Error messages referencing `"CreateByMwClassId"` confirm a factory pattern where objects are instantiated by integer class ID. These IDs are 32-bit integers (e.g., `0x03043000` for `CGameCtnChallenge`).

**StaticInit pattern**: Classes register themselves via static initialization functions. Three `StaticInit` strings appear in the binary:
- `CMwNod::MwNod_StaticInit` -- Base class registration
- `CMwId::StaticInit` -- String/identifier interning system initialization
- `CSystemEngine::StaticInit` -- System engine bootstrapping

**No `::ClassId` strings found**: Class IDs are compile-time constants embedded in registration tables rather than string-based RTTI labels.

**CMwNod vtable**: CMwNod was not found in the MSVC vtable symbol table. Only 83 vtable symbols were resolved, all for std:: or MSVC internal classes. Nadeo classes use their own vtable layout without MSVC RTTI metadata.

### Likely CMwNod interface

Based on factory strings and known ManiaPlanet engine behavior, CMwNod likely provides:

- Virtual destructor
- `GetMwClassId()` -- returns the numeric class ID
- `Archive(CClassicArchive*)` -- serialization/deserialization for GBX format
- Reference counting (`MwAddRef()`, `MwRelease()`)
- Class info introspection (`CMwClassInfoViewer` exists)
- Command/property binding (`CMwCmd*` family)

[UNKNOWN]: The exact vtable layout, field offsets, and number of virtual functions in CMwNod have not been determined.

---

## How the engine boots

The engine follows a modular design with singleton "Engine" classes and a layered application bootstrap chain.

### Engine singletons

Twelve engine singletons form the backbone of the engine:

| Class                  | Subsystem  | Role                                          |
|------------------------|------------|-----------------------------------------------|
| `CMwEngine`            | Core       | Base engine, class registration [UNKNOWN]     |
| `CMwEngineMain`        | Core       | Main engine loop / application frame          |
| `CGameEngine`          | Game       | Game logic orchestration                      |
| `CPlugEngine`          | Plug       | Resource/asset management engine              |
| `CSceneEngine`         | Scene      | Scene graph and rendering management          |
| `CVisionEngine`        | Vision     | Low-level rendering backend                   |
| `CNetEngine`           | Net        | Network stack management                      |
| `CInputEngine`         | Input      | Input device management                       |
| `CSystemEngine`        | System     | OS/file system abstraction                    |
| `CScriptEngine`        | Script     | ManiaScript VM                                |
| `CControlEngine`       | Control    | UI control hierarchy management               |
| `CAudioSourceEngine`   | Audio      | Audio source management (name suggests it may be a source type rather than a true engine singleton) |

Additional quasi-engine singletons: `CPlugSoundEngine` / `CPlugSoundEngine2` handle sound resource management.

### Application bootstrap chain

The likely bootstrap order based on class naming patterns:

```
CGbxApp (base application)
  -> CGbxGame (game-specific application)
    -> CGameApp (game application logic)
      -> CGameCtnApp (CTN = "Creation TrackMania Nations" context)
        -> CGameManiaPlanet (ManiaPlanet platform layer)
          -> CTrackMania (TrackMania-specific top-level)
```

`CGbxApp` and `CGbxGame` exist as minimal bootstrap classes. `CGameCtnApp` contains methods like `AskConnectionType`, `BuddyAdd`, `QuitGame`. `CTrackMania`, `CTrackManiaMenus`, `CTrackManiaNetwork`, and `CTrackManiaIntro` are the game-specific specializations.

---

## Major class families

### CGame* (728 classes) -- Game Logic

The largest family covers game logic, editors, maps, players, and scoring.

| Sub-Family                | Count | Purpose                                           |
|---------------------------|------:|---------------------------------------------------|
| `CGameCtn*`               |   162 | "Creation TrackMania Nations" -- maps, blocks, editors, media, replays |
| `CGameEditor*`            |    54 | Editor modes (map, mesh, item, skin, vehicle, etc.) |
| `CGameDataFileTask_*`     |    44 | Async file/data loading tasks (ghosts, maps, skins) |
| `CGameScript*`            |    42 | ManiaScript API bindings (entities, maps, vehicles) |
| `CGamePlayground*`        |    39 | Gameplay session management (client/server modules) |
| `CGameControl*`           |    33 | Game-specific UI controls and camera controllers    |
| `CGameModule*`            |    31 | HUD modules (chrono, scores, speedmeter, store)     |
| `CGameManialink*`         |    28 | Manialink UI framework controls                     |
| `CGameUser*`              |    25 | User management, privileges, voice chat, squads     |
| `CGameMasterServer*`      |    24 | Legacy master server communication                  |
| `CGameScore*`             |    24 | Score management, leaderboards, trophies            |
| `CGameMania*`             |    21 | ManiaApp/ManiaPlanet/ManiaTitle framework           |
| `CGamePlayer*`            |    19 | Player profiles, settings, chunks                   |
| `CGameDirectLinkScript_*` |    14 | Deep link handlers (Garage, Ranked, Royal, etc.)    |
| `CGameNet*`               |    14 | Game-level networking (forms, file transfer)        |
| `CGameObject*`            |     7 | Dynamic objects in playground (physics, visuals)    |
| `CGameBlock*`             |     4 | Block info and placement helpers                    |
| `CGameVehicle*`           |     3 | Vehicle model and physics wrappers                  |

#### Key CGameCtn* classes

The `CGameCtn*` family is the heart of the map/track system:

- **Maps**: `CGameCtnChallenge` (the map class, legacy name "Challenge"), `CGameCtnChallengeParameters`
- **Blocks**: `CGameCtnBlock`, `CGameCtnBlockInfo`, `CGameCtnBlockInfoClassic/Clip/Flat/Frontier/Road/Slope/Transition`
- **Items**: `CGameCtnAnchoredObject` (placed items), `CGameCtnCollector` (collectible resources)
- **Editor**: `CGameCtnEditor`, `CGameCtnEditorCommon`, `CGameCtnEditorFree`, `CGameCtnEditorPuzzle`, `CGameCtnEditorSimple`
- **MediaTracker**: `CGameCtnMediaBlock*` (65+ block types for camera, effects, transitions)
- **Replay**: `CGameCtnReplayRecord`, `CGameCtnGhost`
- **Zones**: `CGameCtnZone`, `CGameCtnZoneFlat`, `CGameCtnZoneFrontier`, `CGameCtnZoneTransition`
- **Network**: `CGameCtnNetwork`, `CGameCtnNetServerInfo`

### CPlug* (391 classes) -- Resources and Assets

The plugin/resource system handles all loadable assets.

| Sub-Family            | Count | Purpose                                              |
|-----------------------|------:|------------------------------------------------------|
| `CPlugAnim*`          |    77 | Animation system (clips, graphs, nodes, skeletal)    |
| `CPlugFile*`          |    36 | File format handlers (DDS, PNG, JPG, WAV, FBX, etc.)|
| `CPlugBitmap*`        |    28 | Texture/bitmap management and rendering              |
| `CPlugVehicle*`       |    18 | Vehicle physics, visuals, cameras, wheels            |
| `CPlugVisual*`        |    15 | Visual primitives (2D, 3D, indexed, triangles, quads)|
| `CPlugFx*`            |    15 | Visual effects system (particles, lightning, wind)   |
| `CPlugMaterial*`      |    12 | Material definitions and shader bindings             |
| `CPlugAdn*`           |    11 | ADN animation system (Nadeo's motion framework)      |
| `CPlugParticle*`      |     9 | Particle emitters and GPU particles                  |
| `CPlugChar*`          |     8 | Character physics and visuals models                 |
| `CPlugSound*`         |     8 | Sound resources (engine, mood, surface, multi)       |
| `CPlugModel*`         |     7 | 3D model management (mesh, LOD, shading, fences)     |
| `CPlugDyna*`          |     5 | Dynamic physics (constraints, objects, water)        |
| `CPlugTree*`          |     5 | Scene tree nodes (lights, generators, visual mip)    |
| `CPlugShader*`        |     4 | Shader programs and passes                           |
| `CPlugMood*`          |     4 | Mood/atmosphere settings                             |
| `CPlugVFXNode_*`      |     7 | VFX node graph system                                |

Key classes: `CPlugSolid2Model` (primary 3D model format), `CPlugStaticObjectModel` (static items/scenery), `CPlugDynaObjectModel` (dynamic/kinematic objects), `CPlugSkel` (skeleton), `CPlugEntRecordData` (ghost replay data), `CPlugTree` (scene graph node), `CPlugPrefab` (reusable compositions), `CPlugSurface` (collision surfaces).

### CWebServices* (297 classes) -- Online Services

All communication with Nadeo/Ubisoft web APIs uses the async Task/Result pattern.

| Sub-Family                    | Count | Purpose                                    |
|-------------------------------|------:|--------------------------------------------|
| `CWebServicesTaskResult_*`    |   168 | Typed result containers for async tasks     |
| `CWebServicesTask_*`          |   108 | Async task definitions (connect, upload, etc.) |
| `CWebServices*Service`        |    15 | Service facades (Achievement, Friend, Map, etc.) |
| `CWebServicesUserManager`     |     1 | User session management                     |
| `CWebServicesTaskScheduler`   |     1 | Task scheduling infrastructure              |
| Other                         |     4 | Base classes and sequences                  |

The `_NS*` prefix indicates Nadeo Services-specific result types. The `_WS*` prefix indicates general web services results.

### CNet* (262 classes) -- Networking

| Sub-Family                    | Count | Purpose                                       |
|-------------------------------|------:|-----------------------------------------------|
| `CNetNadeoServicesTask_*`     |   157 | NadeoServices API call tasks                  |
| `CNetUbiServicesTask_*`       |    38 | Ubisoft Connect / UPC API tasks               |
| `CNetMasterServer*`           |    24 | Legacy master server protocol                 |
| `CNetUplayPC*`                |    11 | Uplay PC integration (achievements, friends)  |
| `CNetForm*`                   |     7 | Network form types (ping, RPC, sessions)      |
| `CNetFileTransfer*`           |     5 | File upload/download over network             |
| `CNetScriptHttp*`             |     3 | HTTP scripting API                            |
| Core networking               |    17 | CNetClient, CNetServer, CNetConnection, etc.  |

### CHms* (41 classes) -- Hierarchical Managed Scene

The HMS system manages the 3D scene graph with portal-based visibility:

- **Zone management**: `CHmsZone`, `CHmsZoneElem`, `CHmsZoneOverlay`, `CHmsZoneVPacker`
- **Rendering**: `CHmsViewport`, `CHmsPrecalcRender`, `CHmsShadowGroup`, `CHmsVolumeShadow`
- **Lighting**: `CHmsLight`, `CHmsLightArray`, `CHmsLightMap`, `CHmsLightMapCache`, `CHmsLightMapCacheSH`, `CHmsLightMapMood`, `CHmsLightProbeGrid`
- **Scene elements**: `CHmsItem`, `CHmsItemShadow`, `CHmsCorpus`, `CHmsCorpus2d`, `CHmsSolid2`
- **Atmosphere**: `CHmsAmbientOcc`, `CHmsFogPlane`, `CHmsMoodBlender`
- **Portals**: `CHmsPortal`, `CHmsPortalProperty`
- **Managers**: `CHmsMgrVisDyna`, `CHmsMgrVisDynaDecal2d`, `CHmsMgrVisEnvMap`, `CHmsMgrVisParticle`, `CHmsMgrVisVolume`
- **Car-specific**: `CHmsSolidVisCst_TmCar` -- TrackMania car-specific rendering constants

### CScene* (52 classes) -- Scene Objects

Higher-level scene object management:

- **Vehicles**: `CSceneVehicleVis`, `CSceneVehicleVisState`, `CSceneVehicleVisParams`, `CSceneVehicleCarMarksModel`
- **Characters**: `CSceneCharVis`, `CSceneCharVisState`
- **Effects**: `CSceneFx*` (14 classes: Bloom, Blur, CameraBlend, Colors, DOF, Flares, etc.)
- **Physics managers**: `CSceneMgrPhy`, `CSceneGunPhy`, `CSceneBulletPhy`, `CSceneTrafficPhy`
- **Visual managers**: `CSceneMgrGUI`, `CScenePickerManager`
- **Spatial**: `CSceneSector`, `CSceneLayout`, `CSceneLocation`, `CSceneLocationCamera`

### CControl* (39 classes) -- UI Controls

Standard UI widget system: `CControlBase` (base), buttons, labels, text fields, sliders, grids, graphs, frames, style sheets, and effects. Specialized controls include `CControlMediaPlayer`, `CControlMiniMap`, `CControlScriptEditor`, and `CControlScriptConsole`.

### CSystem* (24 classes) -- System Layer

File system (`CSystemFidFile`, `CSystemFidsFolder`), configuration (`CSystemConfig`), platform abstraction (`CSystemPlatform`, `CSystemWindow`), package management (`CSystemPackManager`), platform integration (`CSystemSteam`, `CSystemUplayPC`), and serialization (`CSystemArchiveNod`).

### CMw* (17 classes) -- ManiaPlanet Core

The foundational layer: `CMwNod` (universal base), engines (`CMwEngine`, `CMwEngineMain`), command system (`CMwCmd*` family with fast calls and fibers), identity (`CMwId` interned strings), introspection (`CMwClassInfoViewer`), and networked entity replication (`CMwNetworkEntitiesManager`).

---

## Observed inheritance patterns

The following inheritance trees are inferred from naming conventions, method presence, and structural evidence. Naming alone does not confirm inheritance, but the consistency provides strong circumstantial evidence.

### Engine hierarchy (high confidence)

```
CMwNod
  +-- CMwEngine
  |     +-- CMwEngineMain
  |     +-- CGameEngine
  |     +-- CPlugEngine
  |     +-- CSceneEngine
  |     +-- CNetEngine
  |     +-- CInputEngine
  |     +-- CSystemEngine
  |     +-- CScriptEngine
  |     +-- CVisionEngine
  |     +-- CControlEngine [UNCERTAIN -- may not inherit CMwEngine]
  +-- CMwCmd
  |     +-- CMwCmdFastCall
  |     +-- CMwCmdFastCallStatic
  |     +-- CMwCmdFastCallStaticParam
  |     +-- CMwCmdFastCallUser
  |     +-- CMwCmdFiber
  +-- CMwCmdBuffer
  |     +-- CMwCmdBufferCore
  |     +-- CMwCmdContainer
  +-- CMwId
```

### Application hierarchy (high confidence)

```
CMwNod
  +-- CGbxApp
        +-- CGbxGame
              +-- CGameApp
                    +-- CGameCtnApp
                          +-- CGameManiaPlanet
                                +-- CTrackMania
```

### Block info hierarchy (high confidence)

```
CMwNod
  +-- CGameCtnBlockInfo
        +-- CGameCtnBlockInfoClassic
        +-- CGameCtnBlockInfoClip
        |     +-- CGameCtnBlockInfoClipHorizontal
        |     +-- CGameCtnBlockInfoClipVertical
        +-- CGameCtnBlockInfoFlat
        +-- CGameCtnBlockInfoFrontier
        +-- CGameCtnBlockInfoPylon
        +-- CGameCtnBlockInfoRectAsym
        +-- CGameCtnBlockInfoRoad
        +-- CGameCtnBlockInfoSlope
        +-- CGameCtnBlockInfoTransition
```

### Visual hierarchy (high confidence)

```
CMwNod
  +-- CPlugVisual
        +-- CPlugVisual2D
        |     +-- CPlugVisualLines2D
        |     +-- CPlugVisualQuads2D
        +-- CPlugVisual3D
              +-- CPlugVisualIndexed
              |     +-- CPlugVisualIndexedLines
              |     +-- CPlugVisualIndexedStrip
              |     +-- CPlugVisualIndexedTriangles
              +-- CPlugVisualLines
              +-- CPlugVisualQuads
              +-- CPlugVisualSprite
              +-- CPlugVisualStrip
              +-- CPlugVisualTriangles
              +-- CPlugVisualVertexs
              +-- CPlugVisualGrid
              +-- CPlugVisualOctree
              +-- CPlugVisualCelEdge
```

### MediaTracker block hierarchy (high confidence)

```
CMwNod
  +-- CGameCtnMediaBlock
        +-- CGameCtnMediaBlockCamera
        |     +-- CGameCtnMediaBlockCameraCustom
        |     +-- CGameCtnMediaBlockCameraGame
        |     +-- CGameCtnMediaBlockCameraOrbital
        |     +-- CGameCtnMediaBlockCameraPath
        |     +-- CGameCtnMediaBlockCameraSimple
        +-- CGameCtnMediaBlockCameraEffect
        |     +-- CGameCtnMediaBlockCameraEffectInertialTracking
        |     +-- CGameCtnMediaBlockCameraEffectScript
        |     +-- CGameCtnMediaBlockCameraEffectShake
        +-- CGameCtnMediaBlockFx
        |     +-- CGameCtnMediaBlockFxBloom
        |     +-- CGameCtnMediaBlockFxBlur
        |     +-- CGameCtnMediaBlockFxBlurDepth
        |     +-- CGameCtnMediaBlockFxBlurMotion
        |     +-- CGameCtnMediaBlockFxCameraBlend
        |     +-- CGameCtnMediaBlockFxCameraMap
        |     +-- CGameCtnMediaBlockFxColors
        +-- CGameCtnMediaBlockText
        +-- CGameCtnMediaBlockSound
        +-- CGameCtnMediaBlockImage
        +-- CGameCtnMediaBlockTriangles
        |     +-- CGameCtnMediaBlockTriangles2D
        |     +-- CGameCtnMediaBlockTriangles3D
        +-- CGameCtnMediaBlockTransition
        |     +-- CGameCtnMediaBlockTransitionFade
        +-- ... (65+ block types total)
```

### Additional hierarchies

**Zone hierarchy** (high confidence): `CGameCtnZone` -> `CGameCtnZoneFlat`, `CGameCtnZoneFrontier`, `CGameCtnZoneTransition`

**Editor hierarchy** (moderate confidence): `CGameEditorBase` [UNCERTAIN parent] -> `CGameEditorAction`, `CGameEditorItem`, `CGameEditorMesh`, `CGameEditorMediaTracker`, `CGameEditorSkin`, `CGameEditorVehicle`, and 9 others.

**Bitmap render hierarchy** (high confidence): `CPlugBitmapRender` -> 13 specializations (Camera, CubeMap, Shadow, Water, etc.)

**Animation graph node hierarchy** (high confidence): `CPlugAnimGraphNode` [UNKNOWN if base exists as named] -> 41 node types (Blend, ClipPlay, StateMachine, JointIK2, etc.)

**Scene FX hierarchy** (high confidence): `CSceneFx` [UNCERTAIN base] -> 14 specializations (Bloom, Blur, DOF, Flares, etc.)

---

## Cross-cutting architectural patterns

### Task/Result pattern

A recurring pattern pairs an async task class with a typed result class:

- `CNetNadeoServicesTask_*` (157 task classes)
- `CWebServicesTask_*` (108 task classes)
- `CWebServicesTaskResult_*` (168 result classes)
- `CGameDataFileTask_*` (44 task classes)
- `CGameScoreTask_*` (24 task classes)
- `CGameUserTask_*` (11 task classes)
- `CNetMasterServerTask_*` (24 task classes)
- `CNetUbiServicesTask_*` (38 task classes)

### Model/Physics/Visual decomposition

Many game entities split into Model, Physics (Phy), and Visual (Vis) components:

| Domain        | Model                     | Physics              | Visual              |
|---------------|---------------------------|----------------------|---------------------|
| Game Object   | `CGameObjectModel`        | `CGameObjectPhy`     | `CGameObjectVis`    |
| Vehicle       | `CGameVehicleModel`       | `CGameVehiclePhy`    | --                  |
| Gate          | `CGameGateModel`          | `CGameGatePhy`       | `CGameGateVis`      |
| Turret        | --                        | `CGameTurretPhy`     | `CGameTurretVis`    |
| Bullet        | `CPlugBulletModel`        | `CSceneBulletPhy`    | `CSceneBulletVis`   |
| Character     | `CPlugCharPhyModel`       | --                   | `CPlugCharVisModel` |
| Slot          | --                        | `CGameSlotPhy`       | `CGameSlotVis`      |
| Scene Vehicle | --                        | --                   | `CSceneVehicleVis`  |

---

## VTable scan results

The vtable scan found 83 vtable symbols, all belonging to MSVC standard library or internal types. No Nadeo class vtables were resolved because the binary is stripped of Nadeo-specific RTTI metadata.

Notable entries:

| Address          | Class                                      |
|------------------|--------------------------------------------|
| `0x14197e908`    | `std::exception::vftable`                  |
| `0x14197e938`    | `std::bad_alloc::vftable`                  |
| `0x14197e960`    | `std::bad_function_call::vftable`          |
| `0x141980280`    | `type_info::vftable`                       |
| `0x141a3a0a0`    | `CSingletonCriticalSection::vftable`       |

Vtable-based inheritance reconstruction requires manual analysis of vtable pointer patterns. This is a future analysis step.

---

## GPU and shader namespace structure

The binary contains extensive GPU shader constant buffer types organized by namespace.

### Top-level GPU namespaces

- `NGpu::` -- GPU shader programs and constant buffers (50+ sub-namespaces)
- `NGpuP::` -- Pixel shader variants
- `NGpuV::` -- Vertex shader variants
- `NVis::` -- Vision engine GPU operations
- `NVisionResourceFile::` -- Vision resource file GPU helpers

### Buffer naming convention

```
N<ShaderFamily>::SCBuffer[V|P][_Variant]
```

- `SCBuffer` -- Shader Constant Buffer
- `V` suffix -- Vertex shader buffer
- `P` suffix -- Pixel shader buffer
- `_Draw` suffix -- Draw-time buffer
- `_Shader` suffix -- Shader-specific buffer

Examples:
- `NGpu::NBilateralBlur_p::SCBuffer` -- Bilateral blur pixel shader constants
- `NGpuP::NTmCar::SCBuffer_Draw` -- TrackMania car pixel shader draw constants
- `NGpu::NTM_GlobalFilmCurve_p::SCBuffer_ACES_LUT` -- ACES tone mapping LUT constants

### Notable rendering families

- `NBlock_*` -- Block rendering (tree sprites, etc.)
- `NCharAnimSkel*` -- Character animation skeletal rendering
- `NDecal*` -- Decal rendering
- `NDeferred*` -- Deferred rendering pipeline
- `NGPU_HBAO*` -- HBAO (Horizon-Based Ambient Occlusion) -- uses NVIDIA GFSDK
- `NGpu::NTM_*` -- TrackMania-specific rendering (film curve, tone mapping)
- `NGpu::NSea_*` / `SCBufferP_Sea` -- Water/sea rendering
- `NGeomILighting*` -- Geometry instanced lighting
- `NLmRaster*` -- Lightmap rasterization
- `TemporalAA_Constants` -- TAA post-processing

---

## RTTI and non-Nadeo classes

### MSVC RTTI classes (55 types)

Standard C++ types with MSVC RTTI metadata: exceptions (`std::exception`, `std::bad_alloc`, etc.), I/O (`std::basic_streambuf`, `std::basic_filebuf`), locale facets, concurrency primitives, COM (`_com_error`), MSVC internals (`type_info`, `DNameNode`), and 55 `SCBuffer*` GPU constant buffer structs.

### Third-party libraries

- **NVIDIA GFSDK**: `GFSDK::SSAO::PerPassConstantStruct` -- HBAO+ ambient occlusion
- **Gm math library**: `Gm::GmVec2`, `Gm::GmVec4`, `GmMat4` -- custom math types (likely Nadeo's own)
- **libwebp**: `LIBWEBP64.DLL` -- WebP image format support
- **Vorbis**: `VORBIS64.DLL` -- OGG Vorbis audio
- **DirectX**: `D3D11.DLL`, `DXGI.DLL`, `DINPUT8.DLL` -- DirectX 11 rendering and input
- **Ubisoft**: `UPC_R2_LOADER64.DLL` -- Ubisoft Connect (UPC) integration

---

## Summary statistics

| Metric                                | Value    |
|---------------------------------------|----------|
| Total Nadeo classes                   | 2,027    |
| Total MSVC RTTI classes               | 55       |
| Major subsystem prefixes              | 32       |
| Engine singleton classes              | 12       |
| CGame* classes                        | 728      |
| CPlug* classes                        | 391      |
| CWebServices* classes                 | 297      |
| CNet* classes                         | 262      |
| CScene* classes                       | 52       |
| CHms* classes                         | 41       |
| CControl* classes                     | 39       |
| CSystem* classes                      | 24       |
| CMw* classes (core)                   | 17       |
| Async task classes (all families)     | ~406     |
| Async task result classes             | ~168     |
| MediaTracker block types              | 65+      |
| Animation graph node types            | 41       |
| Bitmap render specializations         | 14       |
| Scene FX types                        | 14       |
| GPU shader buffer namespaces          | 50+      |
| MSVC vtable symbols resolved          | 83       |
| Nadeo vtable symbols resolved         | 0        |

---

## Open questions and future work

1. **[UNKNOWN]** CMwNod vtable layout -- the exact virtual function table structure needs manual reconstruction from vtable pointer patterns.

2. **[UNKNOWN]** MwClassId values -- the numeric class IDs for each class need extraction from registration tables. These are critical for GBX file format parsing.

3. **[UNKNOWN]** Exact inheritance chains -- naming patterns strongly suggest parent-child relationships, but vtable inheritance has not been verified through pointer chain analysis.

4. **[UNKNOWN]** CMwNod field layout -- base class fields (reference count, class info pointer, flags) need determination through constructor analysis.

5. **[UNKNOWN]** Engine initialization order -- the full bootstrap sequence and class registration order is not established beyond three `StaticInit` strings.

6. **[UNKNOWN]** The relationship between `Gm::` math types and the engine -- whether `GmVec2/GmVec4/GmMat4` are standalone structs or inherit from CMwNod.

7. **Non-C-prefix classes** (Clouds, Cluster, ConnectionClient, ConsoleClient) -- their role in the hierarchy and whether they inherit from CMwNod is unconfirmed.

---

## Related Pages

- [13-subsystem-class-map.md](13-subsystem-class-map.md) -- Every class mapped to a subsystem with detailed analysis
- [12-architecture-deep-dive.md](12-architecture-deep-dive.md) -- State machine, fiber system, and frame loop
- [08-game-architecture.md](08-game-architecture.md) -- High-level game architecture overview
- [15-ghidra-research-findings.md](15-ghidra-research-findings.md) -- Ghidra string and function analysis
- [00-master-overview.md](00-master-overview.md) -- Master index of all reverse engineering docs

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**Data sources**: RTTI string extraction, vtable scan, namespace enumeration, pre-extracted `class_hierarchy.json`

</details>

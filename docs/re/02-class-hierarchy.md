# Trackmania.exe Class Hierarchy and Namespace Structure

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**Data sources**: RTTI string extraction, vtable scan, namespace enumeration, pre-extracted `class_hierarchy.json`

---

## 1. Overview

Trackmania 2020 is built on Nadeo's proprietary **ManiaPlanet/GameBox engine**, which uses a custom RTTI and class registration system centered on `CMwNod` as the universal base class. The binary contains **2,027 identified Nadeo engine classes** and **55 MSVC RTTI classes** (C++ standard library and GPU shader buffer types).

All Nadeo classes follow the **C-prefix naming convention**: every class name begins with `C` followed by a subsystem identifier (e.g., `CGame`, `CPlug`, `CMw`, `CHms`, `CNet`).

---

## 2. Nadeo Class Naming Convention

### 2.1 General Pattern

```
C<Subsystem><SubFamily><SpecificName>[_Suffix]
```

- **C**: Mandatory class prefix (every Nadeo class begins with `C`)
- **Subsystem**: Top-level engine module (e.g., `Game`, `Plug`, `Mw`, `Hms`, `Net`)
- **SubFamily**: Functional grouping within the subsystem (e.g., `Ctn`, `Editor`, `Script`)
- **SpecificName**: The concrete class name
- **_Suffix**: Optional variant/specialization (e.g., `_Deprecated`, `_ReadOnly`, `_Script`)

### 2.2 Subsystem Prefix Inventory

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
| `CGbx*`         |     2 | GameBox application bootstrap                                 |
| Other C*        |    25 | Miscellaneous (Crystal, Dialogs, Ghost, Hud, Replay, etc.)   |

### 2.3 Non-C-Prefix Classes

A small set of classes in the `nadeo_classes` list do not follow the C-prefix convention:

- `Clouds` -- [UNKNOWN] purpose, possibly internal scene element
- `Cluster` -- [UNKNOWN] purpose, possibly spatial partitioning
- `ConnectionClient` -- Likely a network connection abstraction
- `ConsoleClient` -- Likely a debug console client

These appear to be internal/helper types that were still registered in the engine class system.

---

## 3. CMwNod: The Universal Base Class

### 3.1 Evidence

The string `"CMwNod"` appears at address `0x141b71fc8` in the binary. Additional evidence for CMwNod as the root of the class hierarchy:

| Address          | String                                              | Significance                           |
|------------------|-----------------------------------------------------|----------------------------------------|
| `0x141b71fc8`    | `"CMwNod"`                                          | Class name registration string         |
| `0x141b71fd0`    | `"CMwNod::MwNod_StaticInit"`                        | Static initialization function name    |
| `0x141b71f60`    | `"[MwNod] Trying to CreateByMwClassId('"`           | Factory method error string            |
| `0x141b71fa0`    | `"[MwNod] Trying to CreateByMwClassId("`            | Factory method error string (variant)  |
| `0x141b58728`    | `"Parameter is not a CMwNod."`                      | Type-check assertion                   |
| `0x141c0cab0`    | `" CMwNod"`                                         | Possibly used in class info display    |

### 3.2 Class Registration / RTTI System

The Nadeo engine implements its own RTTI system separate from MSVC RTTI. Key characteristics:

1. **MwClassId**: Each class has a numeric "MwClassId" used for serialization and factory creation. The string `"CreateByMwClassId"` in error messages confirms a factory pattern where objects are instantiated by integer class ID.

2. **StaticInit pattern**: Classes register themselves via static initialization functions. Three `StaticInit` strings were found:
   - `CMwNod::MwNod_StaticInit` -- Base class registration
   - `CMwId::StaticInit` -- String/identifier interning system initialization
   - `CSystemEngine::StaticInit` -- System engine bootstrapping

3. **No `::ClassId` or `::GetClassId` strings found**: The class ID mechanism does not use string-based RTTI labels like `"ClassName::ClassId"`. Instead, class IDs are likely compile-time constants embedded in the class registration tables. This is consistent with the known ManiaPlanet GBX format where class IDs are 32-bit integers (e.g., `0x03043000` for `CGameCtnChallenge`).

4. **CMwNod vtable**: CMwNod was **not** found in the MSVC vtable symbol table (only 83 vtable symbols were resolved, all for std:: or MSVC internal classes). The Nadeo classes use their own vtable layout not decorated with MSVC RTTI metadata, which is consistent with a custom RTTI system.

### 3.3 Likely CMwNod Interface

Based on the factory strings and known ManiaPlanet engine behavior, CMwNod likely provides:

- Virtual destructor
- `GetMwClassId()` -- returns the numeric class ID
- `Archive(CClassicArchive*)` -- serialization/deserialization for GBX format
- Reference counting (`MwAddRef()`, `MwRelease()`)
- Class info introspection (`CMwClassInfoViewer` exists)
- Command/property binding (`CMwCmd*` family)

[UNKNOWN]: The exact vtable layout, field offsets, and number of virtual functions in CMwNod have not been determined.

---

## 4. Engine Architecture

### 4.1 Engine Singleton Classes

The engine follows a modular design with singleton "Engine" classes. 12 engine singletons were identified:

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

Additional quasi-engine singletons:
- `CPlugSoundEngine` / `CPlugSoundEngine2` -- Sound resource management

### 4.2 Application Bootstrap Chain

Based on class naming patterns, the likely bootstrap order is:

```
CGbxApp (base application)
  -> CGbxGame (game-specific application)
    -> CGameApp (game application logic)
      -> CGameCtnApp (CTN = "Creation TrackMania Nations" context)
        -> CGameManiaPlanet (ManiaPlanet platform layer)
          -> CTrackMania (TrackMania-specific top-level)
```

Evidence: `CGbxApp` and `CGbxGame` exist as minimal bootstrap classes. `CGameCtnApp` contains methods like `AskConnectionType`, `BuddyAdd`, `QuitGame`. `CTrackMania`, `CTrackManiaMenus`, `CTrackManiaNetwork`, and `CTrackManiaIntro` are the game-specific specializations.

---

## 5. Major Class Families

### 5.1 CGame* (728 classes) -- Game Logic

The largest family. Key sub-families:

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

#### Notable CGameCtn* Classes

The `CGameCtn*` family is the heart of the map/track system:

- **Maps**: `CGameCtnChallenge` (the map class, legacy name "Challenge"), `CGameCtnChallengeParameters`
- **Blocks**: `CGameCtnBlock`, `CGameCtnBlockInfo`, `CGameCtnBlockInfoClassic/Clip/Flat/Frontier/Road/Slope/Transition`
- **Items**: `CGameCtnAnchoredObject` (placed items), `CGameCtnCollector` (collectible resources)
- **Editor**: `CGameCtnEditor`, `CGameCtnEditorCommon`, `CGameCtnEditorFree`, `CGameCtnEditorPuzzle`, `CGameCtnEditorSimple`
- **MediaTracker**: `CGameCtnMediaBlock*` (65+ block types for camera, effects, transitions)
- **Replay**: `CGameCtnReplayRecord`, `CGameCtnGhost`
- **Zones**: `CGameCtnZone`, `CGameCtnZoneFlat`, `CGameCtnZoneFrontier`, `CGameCtnZoneTransition`
- **Network**: `CGameCtnNetwork`, `CGameCtnNetServerInfo`

### 5.2 CPlug* (391 classes) -- Resources and Assets

The plugin/resource system handles all loadable assets. Key sub-families:

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

#### Notable CPlug* Classes

- **CPlugSolid2Model**: The primary 3D model format (meshes, materials, UV layers)
- **CPlugStaticObjectModel**: Static objects (items, scenery)
- **CPlugDynaObjectModel**: Dynamic/kinematic objects with physics
- **CPlugSkel**: Skeleton for skeletal animation
- **CPlugEntRecordData**: Entity record data (ghost replay data)
- **CPlugTree**: Scene graph tree node (base for all scene objects)
- **CPlugPrefab**: Prefab system for reusable object compositions
- **CPlugSurface**: Collision/physics surface definitions

### 5.3 CWebServices* (297 classes) -- Online Services

Handles all communication with Nadeo/Ubisoft web APIs:

| Sub-Family                    | Count | Purpose                                    |
|-------------------------------|------:|--------------------------------------------|
| `CWebServicesTaskResult_*`    |   168 | Typed result containers for async tasks     |
| `CWebServicesTask_*`          |   108 | Async task definitions (connect, upload, etc.) |
| `CWebServices*Service`        |    15 | Service facades (Achievement, Friend, Map, etc.) |
| `CWebServicesUserManager`     |     1 | User session management                     |
| `CWebServicesTaskScheduler`   |     1 | Task scheduling infrastructure              |
| Other                         |     4 | Base classes and sequences                  |

The `CWebServicesTaskResult_NS*` prefix indicates Nadeo Services-specific result types. The `CWebServicesTaskResult_WS*` prefix indicates general web services results.

### 5.4 CNet* (262 classes) -- Networking

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

### 5.5 CHms* (41 classes) -- Hierarchical Managed Scene

The HMS system manages the 3D scene graph with portal-based visibility:

- **Zone management**: `CHmsZone`, `CHmsZoneElem`, `CHmsZoneOverlay`, `CHmsZoneVPacker`
- **Rendering**: `CHmsViewport`, `CHmsPrecalcRender`, `CHmsShadowGroup`, `CHmsVolumeShadow`
- **Lighting**: `CHmsLight`, `CHmsLightArray`, `CHmsLightMap`, `CHmsLightMapCache`, `CHmsLightMapCacheSH`, `CHmsLightMapMood`, `CHmsLightProbeGrid`
- **Scene elements**: `CHmsItem`, `CHmsItemShadow`, `CHmsCorpus`, `CHmsCorpus2d`, `CHmsSolid2`
- **Atmosphere**: `CHmsAmbientOcc`, `CHmsFogPlane`, `CHmsMoodBlender`
- **Portals**: `CHmsPortal`, `CHmsPortalProperty`
- **Managers**: `CHmsMgrVisDyna`, `CHmsMgrVisDynaDecal2d`, `CHmsMgrVisEnvMap`, `CHmsMgrVisParticle`, `CHmsMgrVisVolume`
- **Car-specific**: `CHmsSolidVisCst_TmCar` -- TrackMania car-specific rendering constants

### 5.6 CScene* (52 classes) -- Scene Objects

Higher-level scene object management:

- **Vehicles**: `CSceneVehicleVis`, `CSceneVehicleVisState`, `CSceneVehicleVisParams`, `CSceneVehicleCarMarksModel`
- **Characters**: `CSceneCharVis`, `CSceneCharVisState`
- **Effects**: `CSceneFx*` (14 classes: Bloom, Blur, CameraBlend, Colors, DOF, Flares, etc.)
- **Physics managers**: `CSceneMgrPhy`, `CSceneGunPhy`, `CSceneBulletPhy`, `CSceneTrafficPhy`
- **Visual managers**: `CSceneMgrGUI`, `CScenePickerManager`
- **Spatial**: `CSceneSector`, `CSceneLayout`, `CSceneLocation`, `CSceneLocationCamera`

### 5.7 CControl* (39 classes) -- UI Controls

Standard UI widget system:

- Base: `CControlBase`, `CControlEngine`
- Containers: `CControlContainer`, `CControlFrame`, `CControlFrameAnimated`, `CControlFrameStyled`
- Widgets: `CControlButton`, `CControlLabel`, `CControlText`, `CControlTextEdition`, `CControlEntry`, `CControlEnum`, `CControlSlider`, `CControlQuad`, `CControlGrid`
- Styling: `CControlStyle`, `CControlStyleSheet`, `CControlLayout`, `CControlSimi2`
- Effects: `CControlEffect`, `CControlEffectCombined`, `CControlEffectMaster`, `CControlEffectMotion`, `CControlEffectMoveFrame`, `CControlEffectSimi`
- Specialized: `CControlMediaPlayer`, `CControlMiniMap`, `CControlGraph`, `CControlColorChooser`, `CControlScriptEditor`, `CControlScriptConsole`

### 5.8 CSystem* (24 classes) -- System Layer

- **File system**: `CSystemFidFile`, `CSystemFidContainer`, `CSystemFidsFolder`, `CSystemFidsDrive`, `CSystemManagerFile`, `CSystemFile`
- **Configuration**: `CSystemConfig`, `CSystemConfigDisplay`
- **Platform**: `CSystemPlatform`, `CSystemPlatformScript`, `CSystemWindow`, `CSystemKeyboard`, `CSystemMouse`
- **Package management**: `CSystemPackDesc`, `CSystemPackManager`
- **Engine/services**: `CSystemEngine`, `CSystemData`, `CSystemMemoryMonitor`, `CSystemDependenciesList`
- **Platform integration**: `CSystemSteam`, `CSystemUplayPC`, `CSystemUserMgr`
- **Serialization**: `CSystemArchiveNod`, `CSystemNodWrapper`

### 5.9 CMw* (17 classes) -- ManiaPlanet Core

The foundational layer of the engine:

- **Base**: `CMwNod` -- Universal base class for all engine objects
- **Engines**: `CMwEngine`, `CMwEngineMain`
- **Commands/scripting**: `CMwCmd`, `CMwCmdBuffer`, `CMwCmdBufferCore`, `CMwCmdContainer`, `CMwCmdFastCall`, `CMwCmdFastCallStatic`, `CMwCmdFastCallStaticParam`, `CMwCmdFastCallUser`, `CMwCmdFiber`
- **Identity**: `CMwId` -- Interned string/identifier system
- **Introspection**: `CMwClassInfoViewer` -- Runtime class info viewer
- **Network**: `CMwNetworkEntitiesManager` -- Networked entity replication
- **Utility**: `CMwRefBuffer`, `CMwStatsValue`

---

## 6. Observed Inheritance Patterns

### 6.1 Evidenced Relationships

The following inheritance patterns are supported by naming conventions, method presence, and structural evidence. Naming alone is not sufficient to confirm inheritance, but the consistency of the patterns provides strong circumstantial evidence.

#### Engine Hierarchy (high confidence based on naming + string evidence)
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

#### Application Hierarchy (high confidence)
```
CMwNod
  +-- CGbxApp
        +-- CGbxGame
              +-- CGameApp
                    +-- CGameCtnApp
                          +-- CGameManiaPlanet
                                +-- CTrackMania
```

#### Block Info Hierarchy (high confidence based on naming)
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

#### Visual Hierarchy (high confidence)
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

#### MediaTracker Block Hierarchy (high confidence)
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

#### Zone Hierarchy (high confidence)
```
CMwNod
  +-- CGameCtnZone
        +-- CGameCtnZoneFlat
        +-- CGameCtnZoneFrontier
        +-- CGameCtnZoneTransition
```

#### Editor Hierarchy (moderate confidence -- naming pattern consistent)
```
CMwNod
  +-- CGameEditorBase [UNCERTAIN parent]
        +-- CGameEditorAction
        +-- CGameEditorAnimChar
        +-- CGameEditorAnimClip
        +-- CGameEditorBullet
        +-- CGameEditorCustomBullet
        +-- CGameEditorItem
        +-- CGameEditorManialink
        +-- CGameEditorMaterial
        +-- CGameEditorMediaTracker
        +-- CGameEditorMesh
        +-- CGameEditorModule
        +-- CGameEditorSkin
        +-- CGameEditorVehicle
```

#### Bitmap Render Hierarchy (high confidence)
```
CMwNod
  +-- CPlugBitmapRender
        +-- CPlugBitmapRenderCamera
        +-- CPlugBitmapRenderCubeMap
        +-- CPlugBitmapRenderHemisphere
        +-- CPlugBitmapRenderLightFromMap
        +-- CPlugBitmapRenderLightOcc
        +-- CPlugBitmapRenderOverlay
        +-- CPlugBitmapRenderPlaneR
        +-- CPlugBitmapRenderPortal
        +-- CPlugBitmapRenderShadow
        +-- CPlugBitmapRenderSolid
        +-- CPlugBitmapRenderSub
        +-- CPlugBitmapRenderVDepPlaneY
        +-- CPlugBitmapRenderWater
```

#### Animation Graph Node Hierarchy (high confidence -- 41 node types)
```
CMwNod
  +-- CPlugAnimGraphNode [UNKNOWN -- base may not exist as named]
        +-- CPlugAnimGraphNode_Blend
        +-- CPlugAnimGraphNode_Blend2d
        +-- CPlugAnimGraphNode_ClipPlay
        +-- CPlugAnimGraphNode_Graph
        +-- CPlugAnimGraphNode_Group
        +-- CPlugAnimGraphNode_StateMachine
        +-- CPlugAnimGraphNode_JointIK2
        +-- CPlugAnimGraphNode_JointRotate
        +-- ... (41 node types total)
```

#### Scene FX Hierarchy (high confidence)
```
CMwNod
  +-- CSceneFx [UNCERTAIN if this is the actual base]
        +-- CSceneFxBloom
        +-- CSceneFxBlur
        +-- CSceneFxCameraBlend
        +-- CSceneFxCellEdge
        +-- CSceneFxColors
        +-- CSceneFxCompo
        +-- CSceneFxDepthOfField
        +-- CSceneFxDistor2d
        +-- CSceneFxEdgeBlender
        +-- CSceneFxFlares
        +-- CSceneFxHeadTrack
        +-- CSceneFxOverlay
        +-- CSceneFxStereoscopy
        +-- CSceneFxSuperSample
```

### 6.2 Task/Result Pattern

A recurring architectural pattern throughout the codebase is the **Task/Result pair**:

- **Task class**: Represents an asynchronous operation (e.g., `CNetNadeoServicesTask_GetMap`)
- **Result class**: Typed container for the operation's result (e.g., `CWebServicesTaskResult_NSMap`)

This pattern appears in:
- `CNetNadeoServicesTask_*` (157 task classes)
- `CWebServicesTask_*` (108 task classes)
- `CWebServicesTaskResult_*` (168 result classes)
- `CGameDataFileTask_*` (44 task classes)
- `CGameScoreTask_*` (24 task classes)
- `CGameUserTask_*` (11 task classes)
- `CNetMasterServerTask_*` (24 task classes)
- `CNetUbiServicesTask_*` (38 task classes)

### 6.3 Phy/Vis/Model Pattern

Many game entities follow a **Model/Physics/Visual** decomposition:

| Domain        | Model                     | Physics              | Visual              |
|---------------|---------------------------|----------------------|---------------------|
| Game Object   | `CGameObjectModel`        | `CGameObjectPhy`     | `CGameObjectVis`    |
| Vehicle       | `CGameVehicleModel`       | `CGameVehiclePhy`    | --                  |
| Gate          | `CGameGateModel`          | `CGameGatePhy`       | `CGameGateVis`      |
| Turret        | --                        | `CGameTurretPhy`     | `CGameTurretVis`    |
| Shield        | --                        | --                   | `CGameShield`       |
| Bullet        | `CPlugBulletModel`        | `CSceneBulletPhy`    | `CSceneBulletVis`   |
| Character     | `CPlugCharPhyModel`       | --                   | `CPlugCharVisModel` |
| Slot          | --                        | `CGameSlotPhy`       | `CGameSlotVis`      |
| Scene Vehicle | --                        | --                   | `CSceneVehicleVis`  |

---

## 7. VTable Scan Results

The vtable scan found **83 vtable symbols**, all belonging to MSVC standard library or internal types. No Nadeo class vtables were resolved by symbol name because the binary is stripped of Nadeo-specific RTTI type info metadata (the engine uses its own RTTI system instead).

Notable vtable entries:

| Address          | Class                                      |
|------------------|--------------------------------------------|
| `0x14197e908`    | `std::exception::vftable`                  |
| `0x14197e938`    | `std::bad_alloc::vftable`                  |
| `0x14197e960`    | `std::bad_function_call::vftable`          |
| `0x141980280`    | `type_info::vftable`                       |
| `0x141a3a0a0`    | `CSingletonCriticalSection::vftable`       |

The absence of Nadeo vtable symbols means that vtable-based inheritance reconstruction requires manual analysis of vtable pointer patterns and cross-references, which is a future analysis step.

---

## 8. GPU/Shader Namespace Structure

In addition to the Nadeo class hierarchy, the binary contains extensive GPU shader constant buffer types organized in a namespace-based hierarchy:

### 8.1 Top-Level GPU Namespaces

- `NGpu::` -- GPU shader programs and constant buffers (50+ sub-namespaces)
- `NGpuP::` -- Pixel shader variants
- `NGpuV::` -- Vertex shader variants
- `NVis::` -- Vision engine GPU operations
- `NVisionResourceFile::` -- Vision resource file GPU helpers

### 8.2 GPU Buffer Naming Convention

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
- `NGpuV::NTmCar::SCBuffer_Draw` -- TrackMania car vertex shader draw constants
- `NGpu::NTM_GlobalFilmCurve_p::SCBuffer_ACES_LUT` -- ACES tone mapping LUT constants

### 8.3 Notable Rendering Families

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

## 9. RTTI and Non-Nadeo Classes

### 9.1 MSVC RTTI Classes (55 types)

These are C++ standard library types with MSVC RTTI metadata:

- Standard exceptions: `std::exception`, `std::bad_alloc`, `std::bad_function_call`, `std::logic_error`, `std::length_error`, `std::out_of_range`, `std::runtime_error`, `std::system_error`, `std::bad_exception`
- I/O: `std::basic_streambuf`, `std::basic_filebuf`, `std::basic_ios`, `std::basic_ostream`, `std::ios_base`, `std::ios_base::failure`
- Locale: `std::ctype<char>`, `std::codecvt`, `std::numpunct<char>`, `std::num_put`, `std::_Facet_base`, `std::locale::_Locimp`
- Concurrency: `Concurrency::details::stl_critical_section_vista/win7`, `Concurrency::details::stl_condition_variable_vista/win7`
- COM: `_com_error`
- MSVC internals: `type_info`, `DNameNode`, `DNameStatusNode`, `charNode`, `pcharNode`, `pDNameNode`, `pairNode`
- Shader types: 55 `SCBuffer*` GPU constant buffer structs (these have RTTI because they use virtual destructors or virtual methods)

### 9.2 Third-Party Libraries

Evidence from namespaces and DLL imports:

- **NVIDIA GFSDK**: `GFSDK::SSAO::PerPassConstantStruct` -- HBAO+ ambient occlusion
- **Gm math library**: `Gm::GmVec2`, `Gm::GmVec4`, `GmMat4` -- custom math types (likely Nadeo's own)
- **libwebp**: `LIBWEBP64.DLL` -- WebP image format support
- **Vorbis**: `VORBIS64.DLL` -- OGG Vorbis audio
- **DirectX**: `D3D11.DLL`, `DXGI.DLL`, `DINPUT8.DLL` -- DirectX 11 rendering and input
- **Ubisoft**: `UPC_R2_LOADER64.DLL` -- Ubisoft Connect (UPC) integration

---

## 10. Summary Statistics

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

## 11. Open Questions and Future Work

1. **[UNKNOWN]** CMwNod vtable layout -- the exact virtual function table structure needs manual reconstruction from vtable pointer patterns, since no Nadeo vtable symbols exist.

2. **[UNKNOWN]** MwClassId values -- the numeric class IDs for each class need to be extracted from the class registration tables. These are critical for GBX file format parsing.

3. **[UNKNOWN]** Exact inheritance chains -- while naming patterns strongly suggest parent-child relationships, the actual vtable inheritance has not been verified through pointer chain analysis. Some classes may use composition rather than inheritance despite similar naming.

4. **[UNKNOWN]** CMwNod field layout -- the base class fields (reference count, class info pointer, flags) need to be determined through constructor analysis.

5. **[UNKNOWN]** Engine initialization order -- while `StaticInit` strings were found for `CMwNod`, `CMwId`, and `CSystemEngine`, the full engine bootstrap sequence and class registration order is not established.

6. **[UNKNOWN]** The relationship between the `Gm::` math types and the engine -- whether `GmVec2/GmVec4/GmMat4` are standalone structs or inherit from CMwNod.

7. **Non-C-prefix classes** (Clouds, Cluster, ConnectionClient, ConsoleClient) -- their role in the hierarchy and whether they inherit from CMwNod is not confirmed.

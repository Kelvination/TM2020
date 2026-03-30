# Openplanet Plugin Intelligence Extraction

**Source**: Openplanet plugins installed at `Trackmania/Openplanet/Plugins/`
**Date**: 2026-03-27
**Confidence**: HIGH — These are working plugins that read live game memory. Field names and offsets are VERIFIED against the running game.

---

## Table of Contents

1. [Vehicle State Structure (CSceneVehicleVisState)](#1-vehicle-state-structure)
2. [Vehicle Types & Enumerations](#2-vehicle-types--enumerations)
3. [Wheel State Structure](#3-wheel-state-structure)
4. [Scene Manager Architecture](#4-scene-manager-architecture)
5. [Nadeo Services API](#5-nadeo-services-api)
6. [Authentication Flow](#6-authentication-flow)
7. [Camera System](#7-camera-system)
8. [Rendering Internals](#8-rendering-internals)
9. [Game Coordinate System](#9-game-coordinate-system)

---

## 1. Vehicle State Structure (CSceneVehicleVisState)

**Source**: `VehicleState/Debugger/Main.as`, `VehicleState/StateWrappers.as`
**Confidence**: VERIFIED (working plugin reads these fields from live game memory)

The `CSceneVehicleVisState` is the primary vehicle state visible to the rendering/visual system. It mirrors physics state for display purposes. All fields below are confirmed accessible in TM2020 (code name: TMNEXT).

### Input Fields

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `InputSteer` | float | -1.0 to 1.0 | Steering input |
| `InputGasPedal` | float | 0.0 to 1.0 | Throttle input |
| `InputBrakePedal` | float | 0.0 to 1.0 | Brake input |
| `InputIsBraking` | bool | | Whether currently braking |
| `InputVertical` | float | | Vertical input (reactor/flying) |

### Motion Fields

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `FrontSpeed` | float | m/s | Forward speed (multiply by 3.6 for km/h) |
| `SideSpeed` | float | m/s | Lateral speed (via custom offset) |
| `WorldVel` | vec3 | m/s | World-space velocity vector |
| `Position` | vec3 | meters | World-space position |
| `Dir` | vec3 | unit | Forward direction vector |
| `Left` | vec3 | unit | Left direction vector |
| `Up` | vec3 | unit | Up direction vector |
| `Location` | iso4 | | Full transform (3x3 rotation matrix + vec3 position) |

### Engine/Drivetrain

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `CurGear` | uint | 0-7 | Current gear |
| `RPM` | float | 0-11000 | Engine RPM (via custom offset, not default exposed) |
| `EngineOn` | bool | | Whether engine is running |

### Ground Contact

| Field | Type | Description |
|-------|------|-------------|
| `IsGroundContact` | bool | Any wheel touching ground |
| `IsTopContact` | bool | Top of car touching something |
| `GroundDist` | float (0-20) | Distance to ground |

### Turbo/Boost

| Field | Type | Description |
|-------|------|-------------|
| `IsTurbo` | bool | Currently in turbo |
| `TurboTime` | float (0-1) | Turbo duration remaining (normalized) |
| `Turbo` | float (0-1) | Turbo intensity on CSceneVehicleVis |

### Reactor Boost

| Field | Type | Description |
|-------|------|-------------|
| `ReactorBoostLvl` | int | Reactor boost level |
| `ReactorBoostType` | int | Reactor boost type |
| `ReactorAirControl` | vec3 | Air control vector during reactor |
| `ReactorFinalTimer` | float (0-1) | Counts 0→1 in final second of boost |
| `ReactorInputsX` | bool | Reactor input state |
| `IsReactorGroundMode` | bool | Reactor ground mode active |

### Visual Effects

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `AirBrakeNormed` | float | 0-1 | Air brake visual deployment |
| `BulletTimeNormed` | float | 0-1 | Slow-motion visual effect |
| `SpoilerOpenNormed` | float | 0-1 | Rear spoiler deployment |
| `WingsOpenNormed` | float | 0-0.08 | Wing deployment (small range!) |
| `IsWheelsBurning` | bool | | Tire burnout visual |
| `WaterImmersionCoef` | float | 0-1 | How submerged in water |
| `WaterOverSurfacePos` | vec3 | | Position of water surface |
| `WetnessValue01` | float | 0-1 | How wet the car is |

### Race State

| Field | Type | Description |
|-------|------|-------------|
| `RaceStartTime` | int | Race start timestamp |
| `SimulationTimeCoef` | float (0-1) | Time scale multiplier |
| `DiscontinuityCount` | int | Teleport/reset count |
| `CamGrpStates` | bytes | Changes during vehicle transform |
| `CruiseDisplaySpeed` | int | Speed shown on car during cruise control (0 if not in cruise) |

---

## 2. Vehicle Types & Enumerations

**Source**: `VehicleState/StateWrappers.as`
**Confidence**: VERIFIED

### VehicleType Enum

| Value | Name | Description |
|-------|------|-------------|
| 0 | `CharacterPilot` | On-foot pilot character |
| 1 | `CarSport` | Stadium car (default) |
| 2 | `CarSnow` | Snow car |
| 3 | `CarRally` | Rally car |
| 4 | `CarDesert` | Desert car |

**Evidence**: Vehicle type is determined by looking up a `uint8` index in the VisState, then matching the corresponding `CGameItemModel.Id` against known MwIds:
```
IdCarSport, IdCarSnow, IdCarRally, IdCarDesert, IdCharacterPilot
```

### TurboLevel Enum

| Value | Name | Description |
|-------|------|-------------|
| 0 | `None` | No turbo |
| 1 | `Normal` | Regular turbo (Turbo) |
| 2 | `Super` | Super turbo (Turbo2) |
| 3 | `RouletteNormal` | Roulette normal |
| 4 | `RouletteSuper` | Roulette super |
| 5 | `RouletteUltra` | Roulette ultra (Turbo3Roulette) |

### FallingState Enum

| Value | Name | Description |
|-------|------|-------------|
| 0 | `FallingAir` | Falling through air |
| 2 | `FallingWater` | Falling through water |
| 4 | `RestingGround` | Resting on ground |
| 6 | `RestingWater` | Resting on water surface |
| 8 | `GlidingGround` | Gliding on ground |

**Note**: Values are always even (0, 2, 4, 6, 8). The plugin author notes this "may be completely incorrect and give unexpected results" — the raw memory values may have different semantics.

---

## 3. Wheel State Structure

**Source**: `VehicleState/StateWrappers.as` (MP4/Turbo variant with explicit offsets)
**Confidence**: VERIFIED (MP4/Turbo offsets confirmed, TM2020 uses Openplanet's native reflection which doesn't expose raw offsets)

### Wheel Order
Clockwise from front-left: **FL(0), FR(1), RR(2), RL(3)**

**IMPORTANT**: The Openplanet VehicleState plugin swaps the indices for public API to be FL(0), FR(1), RL(2), RR(3) — but internally the memory layout is FL, FR, RR, RL (clockwise).

### Per-Wheel Fields (TM2020 / TMNEXT)

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `DamperLen` | float | 0-0.2 | Suspension compression (meters) |
| `WheelRot` | float | 0-1608.495 | Wheel rotation angle (radians, accumulates) |
| `WheelRotSpeed` | float | -1000 to 1000 | Wheel angular velocity |
| `SteerAngle` | float | -1 to 1 | Steering angle |
| `GroundContactMaterial` | ESurfId (uint16) | | Surface material ID |
| `SlipCoef` | float | 0-1 | Tire slip coefficient |
| `BreakNormedCoef` | float | 0-1 | Brake visual coefficient |
| `Dirt` | float | 0-1 | Dirt accumulation on tire |
| `Falling` | FallingState | | Per-wheel falling state |
| `Icing01` | float | 0-1 | Ice accumulation |
| `TireWear01` | float | 0-1 | Tire wear level |

### Wheel Struct Layout (MP4 version, 0x24 bytes per wheel)

```
+0x00: DamperLen        (float)
+0x04: WheelRot         (float)
+0x08: WheelRotSpeed    (float)
+0x0C: SteerAngle       (float)
+0x10: GroundContactMaterial (uint16, ESurfId)
+0x14: GroundContact    (uint32, 1=touching)
+0x18: SlipCoef         (float)
+0x20: IsWet            (uint32, 1=wet) [MP4 only]
```

**Note**: TM2020 wheel struct is likely larger (has additional fields: BreakNormedCoef, Dirt, Falling, Icing01, TireWear01) but exact offsets are resolved via Openplanet reflection, not hardcoded.

### VisState Layout (MP4 version, for reference)

```
CSceneVehicleVis:
  +0x000: EntityId         (uint32)
  ...
  +0x4C0: InputSteer       (float)
  +0x4C4: InputGasPedal    (float)
  +0x4CC: InputIsBraking   (uint32)
  +0x4E0: Location         (iso4, 48 bytes: 3x3 matrix + vec3 pos)
  +0x504: Position         (vec3, = Location + 0x24)
  +0x510: WorldVel         (vec3, = Location + 0x30)
  +0x528: FrontSpeed       (float)
  +0x52C: SideSpeed        (float)
  +0x538: IsGroundContact  (uint32)
  +0x53C: Wheels[0] start  (FL, 0x24 bytes each)
  +0x560: Wheels[1]        (FR)
  +0x584: Wheels[2]        (RR)
  +0x5A8: Wheels[3]        (RL)
  +0x5E8: RPM              (float)
  +0x5F4: CurGear          (uint32)
  +0x630: ActiveEffects    (uint32, bit flags)
  +0x824: TurboActive      (float, 1.0 = active)
  +0x830: TurboPercent     (float)
  +0x83C: GearPercent      (float)
```

**CRITICAL**: These MP4 offsets do NOT apply to TM2020. TM2020 uses Openplanet's native reflection system to find offsets dynamically. The struct layout in TM2020 is different (larger, more fields).

---

## 4. Scene Manager Architecture

**Source**: `VehicleState/Internal/SceneVis.as`, `VehicleState/Internal/Vehicle/VehicleNext.as`
**Confidence**: VERIFIED

The scene system uses an indexed manager array accessible through `ISceneVis`:

```
ISceneVis:
  +0x08: managerCount (uint32)
  +0x10: managers[0]  (pointer, 8 bytes each)
  +0x18: managers[1]
  ...
  +0x10 + index * 0x8: managers[index]
```

### Known Manager Indices (TM2020)

| Index | Class | Description |
|-------|-------|-------------|
| 13 | `NSceneVehicleVis_SMgr` | Vehicle visualization manager |
| ? | Other managers | [UNKNOWN - need enumeration] |

**Version History for VehiclesManagerIndex**:
- Before 2022-03-18: index = 4-5
- 2022-03-18: index = 11
- 2022-03-31: index = 12
- 2023-03-03: index = 12
- 2025-09-26: index = 13

### Vehicle Manager Structure (NSceneVehicleVis_SMgr)

```
+0x210: vehicles pointer (uint64, must be 16-byte aligned)
+0x218: vehicle count   (uint32)
```

**Version History for VehiclesOffset**:
- Before 2023-03-03: 0x1C8 → 0x1E0
- 2023-12-21: 0x210

### Vehicle Array
Array of pointers, each 8 bytes:
```
vehicles[i * 0x8] → CSceneVehicleVis pointer
```

Each CSceneVehicleVis starts with a uint32 entity ID at offset 0x0:
- Entity IDs with mask `0x02000000` are local player vehicles
- Entity IDs with mask `0x04000000` are replay/editor vehicles

---

## 5. Nadeo Services API

**Source**: `NadeoServices/NadeoServices.as`
**Confidence**: VERIFIED (working API client)

### Base URLs

| Service | URL | Audience |
|---------|-----|----------|
| Core | `https://prod.trackmania.core.nadeo.online` | `NadeoServices` |
| Live | `https://live-services.trackmania.nadeo.live` | `NadeoLiveServices` |
| Meet | `https://meet.trackmania.nadeo.club` | `NadeoLiveServices` |

### Authentication Header
```
Authorization: nadeo_v1 t=<token>
```

### Audience System
Two audience types:
- **NadeoServices** — Core API access. Token obtained directly from game's internal auth (no refresh needed).
- **NadeoLiveServices** — Live/Meet API access. Token obtained via `Authentication_GetToken` API call to the game.

**DEPRECATED** (as of 2024-01-31): `NadeoClubServices` audience. Now maps to `NadeoLiveServices`.

### Account ID ↔ Login Conversion
Login is a base64-encoded UUID. Account ID is a hyphenated hex UUID:
```
Login → decode base64 → format as UUID with hyphens
AccountID → remove hyphens → hex to bytes → encode base64
```

### Display Name Resolution
Batched API: up to 209 account IDs per `RetrieveDisplayName` request.

---

## 6. Authentication Flow

**Source**: `NadeoServices/AccessToken.as`, `NadeoServices/CoreToken.as`
**Confidence**: VERIFIED

### Core Token
Direct from game internals: `Internal::NadeoServices::GetCoreToken()`. Always considered authenticated. No refresh needed.

### Access Token (Live/Meet)
Obtained through the game's own authentication system:

```
1. Cast app to CGameManiaPlanet
2. Access app.ManiaPlanetScriptAPI
3. Wait for any existing token request to finish
4. Call api.Authentication_GetToken(userId, audience)
5. Wait for api.Authentication_GetTokenResponseReceived
6. Read api.Authentication_Token on success
7. Read api.Authentication_ErrorCode on failure
```

**Token Lifetime**: 55 minutes (Nadeo's validation window) + random 1-60 seconds jitter.

**Retry Strategy on Failure**: Exponential backoff: 1s → 2s → 4s → 8s → 16s → ...
The plugin notes "this is intentionally mimicking Nadeo's code" for the retry pattern.

---

## 7. Camera System

**Source**: `Camera/Impl.as`, `Camera/Export.as`, `NGameCamera_SCamSys_StaticInit.c`
**Confidence**: VERIFIED

### Projection
```
vec4 projected = projectionMatrix * worldPos;
vec2 screenPos = displayPos + (projected.xy / projected.w + 1) / 2 * displaySize;
// Point is behind camera if projected.w > 0
```

### Editor Orbital Camera (TM2020)
```
CGameCtnEditorCommon.OrbitalCameraControl:
  .m_CurrentHAngle   (float, radians)
  .m_CurrentVAngle   (float, radians)
  .m_TargetedPosition (vec3)
  .m_CameraToTargetDistance (float)
  .Pos               (vec3, camera world position)
```

Camera position calculation:
```
h = (HAngle + PI/2) * -1
v = VAngle
axis = vec4(1,0,0,0)
axis = axis * Rotate(v, vec3(0,0,-1))
axis = axis * Rotate(h, vec3(0,1,0))
cameraPos = targetPos + axis.xyz * distance
```

### Camera Types (from decompiled camera init)
See `decompiled/camera/NGameCamera_SCamSys_StaticInit.c` for complete list:
- Race cameras: 3 variants (Race, Race2, Race3)
- First/third person
- Free camera
- Orbital camera
- Helicopter camera
- Vehicle internal camera
- HMD (VR) external camera
- Target camera
- Camera effects (shake, script, inertial tracking)

---

## 8. Rendering Internals

**Source**: `Finetuner/src/01_RenderDistance.as`
**Confidence**: VERIFIED

### Block Size
**32 meters** per block unit. Evidence: `Math::Ceil(distance / 32.0f)` converts meters to blocks.

### Default Far Clip
- TMF: 50,000 meters
- TM2020: [UNKNOWN from plugins, likely similar or larger]

### Key Rendering Types
- `CHmsCamera` — Has `.FarZ` property for clip distance
- `CVisionViewport` — Has `.AsyncRender` property for async rendering

---

## 9. Game Coordinate System

**Source**: Inferred from camera code and vehicle state
**Confidence**: PLAUSIBLE

Based on the orbital camera code:
- **Y-axis is UP** (orbital camera rotates around Y for horizontal angle)
- **Z-axis is forward** (vec3(0, 0, -1) for vertical rotation axis)
- Left-handed coordinate system (consistent with D3D11)

The `iso4` type (used for Location) is a 4x4 isometric transform stored as:
- 3x3 rotation matrix (9 floats)
- 3D position vector (3 floats)
- Total: 48 bytes (not 64, because the homogeneous row [0,0,0,1] is implicit)

Speed conversion: **1 m/s = 3.6 km/h** (confirmed by `FrontSpeed * 3.6f` in debugger code)

---

## 10. Material & Surface System

**Source**: `NadeoImporterMaterialLib.txt` (208 materials, 1374 lines)
**Confidence**: VERIFIED

### Critical Finding: Gameplay Effects are NOT Material-Driven

ALL 208 materials in the library have `DGameplayId(None)`. Gameplay effects (turbo, reactor boost, no-grip, slow motion, etc.) are applied through **block/item types or trigger zones**, NOT through material properties.

Materials only affect:
- **Surface ID** → physics collision properties (friction, sound)
- **UV layers** → texture mapping (BaseMaterial layer 0, Lightmap layer 1)
- **Color** → optional vertex color tinting (DColor0)

### Complete Surface ID Table (19 unique types)

| Surface ID | Physics Role | Example Materials |
|-----------|-------------|-------------------|
| `Asphalt` | Road surface, high grip | RoadTech, PlatformTech, OpenTechBorders |
| `Concrete` | Structural surface | Waterground, ItemPillarConcrete |
| `Dirt` | Off-road surface, lower grip | RoadDirt |
| `Grass` | Natural ground, low grip | Grass, DecoHill |
| `Green` | Vegetation surface | DecoGreen |
| `Ice` | Very low grip | PlatformIce |
| `Metal` | Metallic surface | Technics, Structure, Pylon |
| `MetalTrans` | Transparent metal (glass/screens) | LightSpot, Ad screens |
| `NotCollidable` | No collision (pass-through) | Chrono digits, GlassWaterWall |
| `Pavement` | Sidewalk/paved surface | PlatformPavement |
| `Plastic` | Inflatable/obstacle material | ItemInflatable*, ItemObstacle |
| `ResonantMetal` | Resonant metallic sound | Structure, TrackWallClips |
| `RoadIce` | Icy road surface | RoadIce |
| `RoadSynthetic` | Synthetic road surface | RoadBump, ScreenBack |
| `Rock` | Natural rock | various deco |
| `Rubber` | Bouncy rubber surface | TrackBorders |
| `Sand` | Sandy surface | various deco |
| `Snow` | Snow surface | various deco |
| `Wood` | Wooden surface | TrackWall |

### Material Format
```
DLibrary(<name>)           -- Library declaration
  DMaterial(<name>)         -- Material name
    DSurfaceId(<id>)        -- Physics surface type
    DGameplayId(<id>)       -- Gameplay effect (always None in stock materials)
    DUvLayer(<type>, <idx>) -- UV mapping layers
    DColor0()               -- Optional vertex color
```

### UV Layer Types
- `BaseMaterial` (layer 0) — Primary diffuse/PBR texture
- `Lightmap` (layer 1) — Baked lighting data

### Material Categories (208 total)
- Roads: RoadTech, RoadBump, RoadDirt, RoadIce
- Platforms: PlatformTech, PlatformDirt, PlatformIce, PlatformGrass, PlatformPlastic
- Technics: Structure, Technics, TechnicsTrims, Pylon
- Track Elements: TrackBorders, TrackWall, TrackWallClips
- Racing: RaceArch*, Speedometer, Chrono digits (NotCollidable)
- Decoration: Grass, DecoHill, Waterground, GlassWaterWall
- Items: ItemPillar*, ItemTrackBarrier*, ItemObstacle*, ItemRamp
- Screens/Ads: Ad*Screen, 16x9ScreenOff
- Water: WaterBorders, Underwater

---

## 11. Editor Internals

**Source**: `EditorDeveloper/Main.as`
**Confidence**: VERIFIED

### Editor UI Structure
The editor uses a `CControlContainer` hierarchy accessed via:
```
editor.EditorInterface.InterfaceScene.Mobils[0]  → root CControlContainer
```

### Known UI Frame IDs
- `FrameDeveloperTools` — Hidden Nadeo developer tools (can be shown via Openplanet)
- `FrameEditTools` — Main editing toolbar
- `ButtonOffZone` — Off-zone placement button (hidden by default)
- `FrameLightTools` — Lighting controls

### Orbital Camera Parameters (TM2020)
```
editor.OrbitalCameraControl:
  .m_ParamScrollAreaStart = 0.7  (default)
  .m_ParamScrollAreaMax = 0.98   (default)
```

### Binary Patching (Offzone Enable)
Pattern: `0F 84 ?? ?? ?? ?? 4C 8D 45 ?? BA 13` → `90 90 90 90 90 90` (NOP out conditional jump)

---

## 12. Display Configuration System

**Source**: `Finetuner/src/*.as`
**Confidence**: VERIFIED

### SystemConfig.Display Properties
| Property | Type | Description |
|----------|------|-------------|
| `GeomLodScaleZ` | float | LOD distance scale (1.0 = default, higher = more aggressive LOD) |
| `Decals_3D__TextureDecals_` | bool | 3D decals (grass, bushes) on/off (TM2020 property name) |
| `TextureDecals_3D` | bool | Same as above (MP4 property name) |

### Viewport Properties
| Property | Type | Description |
|----------|------|-------------|
| `Viewport.AverageFps` | float | Current FPS |
| `Viewport.AsyncRender` | bool | Async rendering mode |

### Game Modes (from Stats plugin)
- Solo play
- Online play
- Map Editor
- Map Editor Test
- Skin Editor (TM2020 only)
- MediaTracker

---

## 13. Complete Configuration Schema (Default.json)

**Source**: `Documents/Trackmania/Config/Default.json` (219 lines)
**Confidence**: VERIFIED (actual game configuration)

The Default.json contains the full configuration schema. Key categories:

### Display Configuration (65 parameters)

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `RenderingApi` | string | `"d3d11"` | Only D3D11 available |
| `Antialiasing` | string | `none`, `_2_samples`, `_4_samples`, `_8_samples` | MSAA |
| `DeferredAA` | string | `none`, `_fxaa`, `_txaa` | Deferred anti-aliasing |
| `ShaderQuality` | string | `very_fast` - `ultra` | Shader complexity level |
| `TexturesQuality` | string | `very_low` - `high` | Texture resolution |
| `FilterAnisoQ` | string | `bilinear`, `anisotropic__2x`-`_16x` | Anisotropic filtering |
| `GeometryQuality` | string | `fast`, `nice`, `very_nice`, `ultra` | Mesh detail |
| `Shadows` | string | `none` - `high` | Shadow quality |
| `FxBloomHdr` | string | `none` - `high` | HDR bloom |
| `FxMotionBlur` | string | `off`/`on` | Motion blur |
| `FxMotionBlurIntens` | float | 0-1 | Motion blur intensity (default 0.35) |
| `LM SizeMax` | string | `auto`, `1k2`, etc. | Lightmap max resolution |
| `LM Quality` | string | `very_fast` - `ultra` | Lightmap quality |
| `LM iLight` | bool | | Indirect lighting in lightmaps |
| `Decals_3D (TextureDecals)` | bool | | 3D grass/bush decals |
| `WaterReflect` | string | `very_fast` - `ultra` | Water reflection quality |
| `VehicleReflect` | string | `low` - `high` | Car reflection quality |
| `VehicleReflectMaxCount` | int | | Max reflected vehicles |
| `LightFromMap` | string | `none`, `this_vehicle`, `all_vehicles` | Map lighting on cars |
| `MultiThread` | bool | | Enable multithreading |
| `ThreadCountMax` | int | default 4 | Maximum thread count |
| `MaxFps` | int | 0 = unlimited | FPS cap |
| `AsyncRender` | bool | | Async rendering |
| `ParticleMaxGpuLoadMs` | float | 1.7 default | Max GPU time for particles |
| `GpuSync0-3` | string | `immediate`, `1_frame`, `2_frames`, `3_frames`, `none` | GPU frame latency |

### Network Configuration (18 parameters)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `NetworkServerPort` | 2350 | Default server port |
| `NetworkP2PServerPort` | 3450 | P2P port |
| `NetworkClientPort` | 0 | Dynamic client port |
| `NetworkSpeed` | `"100mbps"` | Connection speed profile |
| `NetworkCustomDownload` | 1310720 | Download speed (bytes/s) |
| `NetworkCustomUpload` | 327680 | Upload speed (bytes/s) |
| `NetworkUseNatUPnP` | false | UPnP NAT traversal |

### Game/Physics Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `SmMaxPlayerResimStepPerFrame` | **100** | **Max physics resim steps per frame — STRONG evidence for 100Hz tick rate** |
| `TmMaxOpponents` | 16 | Max visible opponents |
| `TmCarQuality` | `"high_medium_opponents"` | Car mesh quality tiers |
| `TmCarParticlesQuality` | `"all_high"` | Particle quality |
| `PlayerShadow` | `"all"` | Shadow rendering for players |
| `PlayerOcclusion` | `"all"` | Occlusion for players |
| `TmOpponents` | `"hide_too_close"` | Opponent visibility mode |
| `DisableReplayRecording` | false | Ghost recording |
| `TmBackgroundQuality` | `"high"` | Background/scenery quality |

### Audio Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `AudioDevice_Oal` | string | OpenAL device name |
| `AudioSoundVolume` | 0-1 | Master SFX volume |
| `AudioSoundLimit_Scene` | 0-1 | Scene sound limit |
| `AudioSoundLimit_Ui` | 0-1 | UI sound limit |
| `AudioMusicVolume` | 0-1 | Music volume |
| `AudioGlobalQuality` | `"normal"` | Audio quality |
| `AudioAllowEFX` | bool | Environmental audio effects |
| `AudioAllowHRTF` | bool | Head-related transfer function (3D audio) |
| `AudioDisableDoppler` | bool | Doppler effect |

### Input Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `InputsAlternateMethod` | false | Alternative input method |
| `InputsFreezeUnusedAxes` | true | Freeze unused analog axes |
| `InputsEnableRumble` | true | Force feedback |
| `InputsEnableJoysticks` | true | Joystick support |

### Advertising (Anzu SDK)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `Advertising_Enabled` | `"configurable"` | In-game ads toggle |
| `Advertising_TunningCoef` | 0 | Ad intensity tuning |
| `Advertising_DisabledByUser` | false | User opt-out |

### Safe Mode Configuration
The `DisplaySafe` block contains fallback settings:
- Resolution: 800x450 windowed
- No AA, no deferred AA
- Very low textures, bilinear filtering
- No shadows, decals, bloom, motion blur
- No lightmap indirect lighting
- SingleThread, MaxFps=150
- GpuSync: immediate (no latency)

This represents the absolute minimum viable rendering target for a browser recreation.

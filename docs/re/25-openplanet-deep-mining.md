# Openplanet Plugin Deep Mining - Game Engine Intelligence

**Generated**: 2026-03-27
**Source**: 81 AngelScript (.as) files across 12 plugin directories
**Scope**: Every installed Openplanet plugin, exhaustively mined

---

## Table of Contents

1. [Memory Layout Intelligence](#1-memory-layout-intelligence)
2. [Enum Definitions](#2-enum-definitions)
3. [API Intelligence](#3-api-intelligence)
4. [Binary Patch Patterns](#4-binary-patch-patterns)
5. [Game Events and Hooks](#5-game-events-and-hooks)
6. [Class Member Catalog](#6-class-member-catalog)
7. [Version History](#7-version-history)
8. [Camera System Internals](#8-camera-system-internals)
9. [Editor System Internals](#9-editor-system-internals)
10. [Networking Internals](#10-networking-internals)
11. [Rendering and Display Settings](#11-rendering-and-display-settings)
12. [Plugin System Meta-Intelligence](#12-plugin-system-meta-intelligence)

---

## 1. Memory Layout Intelligence

### 1.1 CSceneVehicleVis (TM2020/Next) - Entity ID and Vehicle Vis Manager

**Source**: `VehicleState/Internal/Vehicle/VehicleNext.as`

The vehicle visualization system is accessed through a scene manager hierarchy:

```
ISceneVis
  +0x08: uint32 managerCount
  +0x10: CMwNod*[managerCount] managers  (stride 0x08 per entry)
```

The vehicle vis manager is at **scene manager index 13** (as of 2025-09-26):

```
NSceneVehicleVis_SMgr (vehicleVisMgr = SceneVis::GetManager(sceneVis, 13))
  +0x210: CMwNod* vehicles_ptr    (array of CSceneVehicleVis pointers)
  +0x218: uint32  vehicles_count
```

**Vehicle Vis Array Structure** (indirect pointer array):
```
vehicles_ptr[i * 0x08] -> CSceneVehicleVis*
```

**CSceneVehicleVis** (confirmed from live memory):
```
  +0x00: uint32 EntityId
```

Entity ID bit masks for vehicle identification:
- `0x02000000` mask: Player vehicle (used when vehicleEntityId == 0 to find player)
- `0x04000000` mask: Replay/editor vehicle (checked to avoid editor car placement)

### 1.2 ISceneVis Manager Array (Alternative Layout)

**Source**: `VehicleState/Internal/SceneVis.as`

```
ISceneVis (fast path):
  +0x08:  uint32 managerCount  (used by GetManager for bounds check)
  +0x10:  CMwNod*[N] managers  (stride 0x08)

ISceneVis (full managers enumeration):
  +0x290: uint32 sceneVisManagersCount
  +0x298: struct[N] {    (stride 0x10)
    +0x00: CMwNod* ptr
    +0x08: CMwNod* classNamePtr  -> +0x00: uint64 classNameString (C string ptr)
  }
```

The managers at +0x10 and +0x290 appear to be two different manager arrays. The +0x10 array is used for fast indexed access (like getting the vehicle vis manager), while the +0x290 array stores metadata including class name strings.

### 1.3 CSceneVehicleVisState (TM2020/Next) - Reflection-Based Offsets

**Source**: `VehicleState/Main.as`

These offsets are computed at runtime using Openplanet's reflection system, relative to known member offsets in `CSceneVehicleVisState`:

| Property | How Computed | Relative To |
|----------|-------------|-------------|
| EngineRPM | `CurGear.Offset - 0x0C` | CurGear |
| WheelDirt[FL] | `FLIcing01.Offset - 0x04` | FLIcing01 |
| WheelDirt[FR] | `FRIcing01.Offset - 0x04` | FRIcing01 |
| WheelDirt[RL] | `RLIcing01.Offset - 0x04` | RLIcing01 |
| WheelDirt[RR] | `RRIcing01.Offset - 0x04` | RRIcing01 |
| SideSpeed | `FrontSpeed.Offset + 0x04` | FrontSpeed |
| WheelFalling[FL] | `FLBreakNormedCoef.Offset + 0x04` | FLBreakNormedCoef |
| WheelFalling[FR] | `FRBreakNormedCoef.Offset + 0x04` | FRBreakNormedCoef |
| WheelFalling[RL] | `RLBreakNormedCoef.Offset + 0x04` | RLBreakNormedCoef |
| WheelFalling[RR] | `RRBreakNormedCoef.Offset + 0x04` | RRBreakNormedCoef |
| LastTurboLevel | `ReactorBoostLvl.Offset - 0x04` | ReactorBoostLvl |
| ReactorFinalTimer | `ReactorBoostType.Offset + 0x04` | ReactorBoostType |
| CruiseDisplaySpeed | `FrontSpeed.Offset + 0x0C` | FrontSpeed |
| VehicleType | `InputSteer.Offset - 0x08` | InputSteer |

This means the in-memory layout near `FrontSpeed` is:
```
FrontSpeed - 0x00: float FrontSpeed
FrontSpeed + 0x04: float SideSpeed
FrontSpeed + 0x08: (unknown 4 bytes)
FrontSpeed + 0x0C: int   CruiseDisplaySpeed
```

And near `CurGear`:
```
CurGear - 0x0C: float EngineRPM
CurGear - 0x08: (unknown)
CurGear - 0x04: (unknown)
CurGear + 0x00: uint  CurGear
```

And near wheel data (e.g. FL):
```
FLIcing01 - 0x04: float FLDirt
FLIcing01 + 0x00: float FLIcing01
```

```
FLBreakNormedCoef + 0x00: float FLBreakNormedCoef
FLBreakNormedCoef + 0x04: int   FLFallingState
```

**Vehicle type** is read as uint8 at `InputSteer.Offset - 0x08`, used as an index into `playground.Arena.Resources.m_AllGameItemModels[]` to look up the vehicle model's MwId.

### 1.4 CSceneVehicleVisState (ManiaPlanet 4 / MP4) - Hardcoded Offsets

**Source**: `VehicleState/StateWrappers.as`

```
CSceneVehicleVisState (MP4 - via CSceneVehicleVis internal pointer):
  +0x000: uint32 EntityId
  +0x4C0: float  InputSteer
  +0x4C4: float  InputGasPedal
  +0x4CC: uint32 InputIsBraking  (1 = true)
  +0x4E0: iso4   Location        (3x3 rotation matrix)
  +0x504: vec3   Position        (at Location + 0x24)
  +0x510: vec3   WorldVel        (at Location + 0x30)
  +0x528: float  FrontSpeed
  +0x52C: float  SideSpeed
  +0x538: uint32 IsGroundContact (1 = true)
  +0x53C: Wheel[4] wheels        (stride 0x24, order: FL=0, FR=1, RR=2, RL=3)
  +0x5E8: float  RPM
  +0x5F4: uint32 CurGear
  +0x630: uint32 ActiveEffects   (bitmask of EffectFlags)
  +0x824: float  TurboActive     (1.0 = true)
  +0x830: float  TurboPercent
  +0x83C: float  GearPercent
```

**MP4 Wheel struct** (stride 0x24):
```
  +0x00: float  DamperLen
  +0x04: float  WheelRot
  +0x08: float  WheelRotSpeed
  +0x0C: float  SteerAngle
  +0x10: uint16 GroundContactMaterial (ESurfId enum)
  +0x14: uint32 GroundContact (1 = true)
  +0x18: float  SlipCoef
  +0x20: uint32 IsWet (1 = true)
```

**MP4 wheel order in memory**: FL=0, FR=1, RR=2, RL=3 (clockwise starting from front-left)

### 1.5 CSceneVehicleVisState (Turbo) - Hardcoded Offsets

**Source**: `VehicleState/StateWrappers.as`

```
CSceneVehicleVisState (Turbo - from vehicleMobil offset):
  +0x00: uint32 EntityId
  +0x8C: float  InputSteer
  +0x94: float  InputGasPedal
  +0x98: uint32 InputIsBraking  (1 = true)
  +0xA0: iso4   Location        (rotation matrix)
  +0xC4: vec3   Position        (at Location + 0x24)
  +0xD0: vec3   WorldVel        (at Location + 0x30)
  +0xE8: float  FrontSpeed
  +0xEC: float  SideSpeed
  +0xF8: uint32 IsGroundContact (1 = true)
  +0xFC: Wheel[4] wheels        (stride 0x24, same struct as MP4 minus IsWet)
  +0x18C: float RPM
  +0x198: uint32 CurGear
  +0x1A0: uint32 TurboActive    (1 = true)
  +0x1A4: float  TurboPercent
  +0x1B8: uint32 ActiveEffects  (bitmask)
```

### 1.6 CSceneVehicleCar (TMNF/Forever) - Hardcoded Offsets

**Source**: `VehicleState/StateWrappers.as`

```
CSceneVehicleCar (Forever):
  +0x2E8: int32   WheelCount
  +0x2EC: uint32  WheelsArrayPtr  (absolute address, not relative)

  State base (m_offsetState = 0x2F8):
  +0x2F8 + 0x08: float  InputSteer
  +0x2F8 + 0x0C: float  InputGasPedal
  +0x2F8 + 0x10: float  InputBrakePedal
  +0x2F8 + 0x34: iso4   Location (rotation matrix)
  +0x2F8 + 0x58: vec3   Position
  +0x2F8 + 0x6C: vec3   WorldVel
  +0x2F8 + 0x78: float  FrontSpeed
  +0x2F8 + 0x90: uint32 IsGroundContact (1 = true)

  Engine base (m_offsetEngine = 0x59C):
  +0x59C + 0x18: float  RPM
  +0x59C + 0x2C: uint32 CurGear

  +0x5F4: float  TurboPercent (flagged as "probably wrong")
  +0x600: uint32 TurboActive (1 = true)
  +0x60C: uint32 ActiveEffects (bitmask)
```

**Forever Wheel struct** (stride 0x2FC per wheel, absolute address from WheelsArrayPtr):
```
  +0x0B4: float  DamperLen
  +0x120: float  WheelRotSpeed
  +0x124: uint32 GroundContact (1 = true)
  +0x128: uint16 GroundContactMaterial (ESurfId)
  +0x150: float  WheelRot
  +0x154: float  SteerAngle
```

### 1.7 CTrackManiaPlayer (MP4) - Vehicle Vis Pointer

**Source**: `VehicleState/Internal/Vehicle/VehicleMP4.as`

```
CTrackManiaPlayer (MP4):
  +0x2B8: CMwNod* vehicleVisPtr   (same pointer as found via VehicleVisMgr)
  +0x2C4: uint32  EntityId
```

### 1.8 CSceneMgrVehicleVisImpl (MP4) - Vehicle Array

**Source**: `VehicleState/Internal/Vehicle/VehicleMP4.as`

```
CSceneMgrVehicleVisImpl (MP4):
  +0x38: CMwNod* vehicles_ptr
  +0x40: uint32  vehicles_count
```

### 1.9 CGameMobil (Turbo) - Vehicle Vis Access

**Source**: `VehicleState/Internal/Vehicle/VehicleTurbo.as`

```
CGameMobil (Turbo):
  +0x14: CMwNod* vehicleMobilPtr
    -> +0x84: CMwNod* vehicleVisPtr
```

### 1.10 GameCamera (MP4) - Viewing Vehicle ID

**Source**: `VehicleState/Internal/Vehicle/VehicleMP4.as`

```
CGameCamera (MP4):
  +0xD4: uint32 ViewingVisId
```

Special viewing ID `0x0FF00000` is used during intro/podium scenes (when camera is null).

### 1.11 CNetClient - NetConfig TCP Limit

**Source**: `InfiniteEmbedSize/NetConfig.as`

The NetConfig struct is accessed relative to `CNetClient.TCPSendingNodTotal` reflection offset:

```
CNetClient:
  TCPSendingNodTotal.Offset + 4: IntPtr netConfigPtr  (pointer to NetConfig struct)

NetConfig (TM2020):
  +0x38: uint32 TcpMaxPacketSize
```

### 1.12 CGameCtnEditorCommon - Orbital Camera

**Source**: `Camera/Impl.as`, `EditorDeveloper/Main.as`

```
CGameCtnEditorCommon.OrbitalCameraControl (TM2020/MP4):
  .m_CurrentHAngle: float   (Turbo: .CurrentHAngle)
  .m_CurrentVAngle: float   (Turbo: .CurrentVAngle)
  .m_TargetedPosition: vec3  (Turbo: .TargetedPosition)
  .m_CameraToTargetDistance: float  (Turbo: .CameraToTargetDistance)
  .Pos: vec3  (TM2020 only)
  +0x44: vec3 cameraPos  (MP4 only, via Dev::SetOffset)
  .m_ParamScrollAreaStart: float  (default 0.7, Turbo: .ParamScrollAreaStart)
  .m_ParamScrollAreaMax: float    (default 0.98, Turbo: .ParamScrollAreaMax)
```

---

## 2. Enum Definitions

### 2.1 FallingState (TM2020 only)

**Source**: `VehicleState/StateWrappers.as`

```
enum FallingState {
    FallingAir     = 0,
    FallingWater   = 2,
    RestingGround  = 4,
    RestingWater   = 6,
    GlidingGround  = 8
}
```

Note: Values are always even (0, 2, 4, 6, 8). The plugin validates against this exact set and rejects unexpected values.

### 2.2 TurboLevel (TM2020 only)

**Source**: `VehicleState/StateWrappers.as`

```
enum TurboLevel {
    None           = 0,
    Normal         = 1,
    Super          = 2,
    RouletteNormal = 3,
    RouletteSuper  = 4,
    RouletteUltra  = 5
}
```

Valid range: 1-5. Value 0 and values > 5 are treated as None.

### 2.3 VehicleType (TM2020 only)

**Source**: `VehicleState/StateWrappers.as`

```
enum VehicleType {
    CharacterPilot = 0,
    CarSport       = 1,  // Stadium
    CarSnow        = 2,
    CarRally       = 3,
    CarDesert      = 4
}
```

Vehicle type is determined by reading a uint8 index from the vis state, looking up the corresponding `CGameItemModel` from `playground.Arena.Resources.m_AllGameItemModels[index]`, and comparing its `MwId` against known vehicle IDs. The MwIds are initialized from string names: "CharacterPilot", "CarSport", "CarSnow", "CarRally", "CarDesert".

### 2.4 EffectFlags (MP4/Turbo/Forever)

**Source**: `VehicleState/StateWrappers.as`

```
enum EffectFlags {
    FreeWheeling       = 1,    // All games
    ForcedAcceleration = 2,    // MP4 only
    NoBrakes           = 4,    // MP4 only
    NoSteering         = 8,    // MP4 only
    NoGrip             = 16    // MP4 only
}
```

### 2.5 ESurfId (Ground Contact Material)

Referenced via `CAudioSourceSurface::ESurfId` (TM2020/MP4/Turbo) or `CAudioSoundSurface::ESurfId` (Forever). These are uint16 values stored in the wheel struct. The actual enum values are not defined in the plugin source -- they come from the game's audio surface type system.

### 2.6 EHmsOverlayAdaptRatio (TM2020)

**Source**: `Finetuner/src/02_OverlayScaling.as`

Referenced as `EHmsOverlayAdaptRatio` with value `ShrinkToKeepRatio` as default. Applied to viewport overlays via `viewport.Overlays[i].m_AdaptRatio`.

### 2.7 ShortcutMode

**Source**: `Finetuner/src/99_Shortcuts.as`

```
enum ShortcutMode {
    Toggle      = 0,
    Hold        = 1,
    InverseHold = 2
}
```

---

## 3. API Intelligence

### 3.1 Nadeo Services Base URLs

**Source**: `NadeoServices/NadeoServices.as`

| Audience | Base URL |
|----------|----------|
| NadeoServices (Core) | `https://prod.trackmania.core.nadeo.online` |
| NadeoLiveServices (Live) | `https://live-services.trackmania.nadeo.live` |
| NadeoLiveServices (Meet) | `https://meet.trackmania.nadeo.club` |

**DEPRECATION**: As of 2024-01-31, `NadeoClubServices` is deprecated. All requests are redirected to `NadeoLiveServices`.

### 3.2 Authentication Pattern

**Source**: `NadeoServices/AccessToken.as`, `NadeoServices/CoreToken.as`

Two token types:
1. **CoreToken** (`NadeoServices`): Retrieved directly via `Internal::NadeoServices::GetCoreToken()` -- always authenticated, no refresh needed.
2. **AccessToken** (`NadeoLiveServices`): Obtained via `api.Authentication_GetToken(userId, audience)`.

**Token lifecycle**:
- Tokens are valid for **55 minutes** + random 1-60 seconds (intentionally slightly longer than Nadeo's internal 55-minute window to avoid conflicts with the game's own auth).
- On authentication failure: exponential backoff retry (1s, 2s, 4s, 8s, 16s, ...) -- "intentionally mimicking Nadeo's code".
- Auth header format: `Authorization: nadeo_v1 t=<token>`

**Authentication flow**:
```
CGameManiaPlanet.ManiaPlanetScriptAPI.Authentication_GetToken(MSUsers[0].Id, audience)
  -> wait for .Authentication_GetTokenResponseReceived
  -> check .Authentication_ErrorCode == 0
  -> read .Authentication_Token
```

### 3.3 Account ID / Login Conversion

**Source**: `NadeoServices/NadeoServices.as`

Login (base64url) to AccountId (UUID) conversion:
```
Login: "c5jutptORLinoaIUmVWscA"
  -> Base64url decode -> raw bytes
  -> Format as: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
Result: "7398eeb6-9b4e-44b8-a7a1-a2149955ac70"
```

This confirms the UUID format: 4-2-2-2-6 byte groups from the 16-byte decoded base64.

### 3.4 Display Name Resolution

**Source**: `NadeoServices/NadeoServices.as`

Display names are resolved via `UserManagerScript`:
```
userMgr.FindDisplayName(accountId)  // checks cache first
userMgr.RetrieveDisplayName(userId, accountIds)  // batch fetch, max 209 per batch
userMgr.TaskResult_Release(req.Id)  // cleanup
```

The batch limit of **209 account IDs per request** is enforced in the code.

### 3.5 Map Info from Services

**Source**: `Discord/Services.as`

```
maniaApp.DataFileMgr.Map_NadeoServices_GetListFromUid(0, uids)
  -> req.MapList[i].Uid
  -> req.MapList[i].ThumbnailUrl  (with ".jpg" suffix appended if missing)
```

### 3.6 Openplanet Plugin API

**Source**: `PluginManager/src/Settings.as`, `PluginManager/src/Utils/API.as`

Base URL: `https://api.openplanet.dev`

Endpoints:
- `GET /plugins?tags=Trackmania&page=0` -- list plugins (tags: "Trackmania", "Turbo", "Forever", "Maniaplanet")
- `GET /plugins?tags=Trackmania&order=f` -- featured
- `GET /plugins?tags=Trackmania&order=d` -- popular (by downloads)
- `GET /plugins?tags=Trackmania&order=u` -- last updated
- `GET /plugins?tags=Trackmania&search=query` -- search
- `GET /plugins?ids=1,2,3` -- specific plugins
- `GET /plugin/{siteID}` -- single plugin details
- `GET /plugin/{siteID}/versions` -- changelog/versions
- `GET /plugin/{siteID}/download` -- download plugin .op file
- `GET /versions?ids=1,2,3` -- batch version check for updates

Web URL: `https://openplanet.dev`

---

## 4. Binary Patch Patterns

### 4.1 Editor Offzone Enable Patch

**Source**: `EditorDeveloper/Main.as`

| Version | Pattern | Replacement |
|---------|---------|-------------|
| TM2020 (release) | `0F 84 ?? ?? ?? ?? 4C 8D 45 ?? BA 13` | `90 90 90 90 90 90` (NOP 6 bytes) |
| TM2020 (logs/debug) | `0F 84 ?? ?? ?? ?? 4C 8D 45 F0 BA ?? ?? ?? ?? 48 8B CF E8 ?? ?? ?? ?? E9 ?? ?? ?? ?? 45 85 FF 0F 84 ?? ?? ?? ?? 83 BF ?? ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? 39` | `90 90 90 90 90 90` |
| MP4.1 (64-bit) | `F6 86 ?? ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? 4C 8D 44 24 70 BA` | `90 90 90 90 90 90 90 90 90 90 90 90 90` (NOP 13 bytes) |
| MP4 (32-bit) | `0F 84 ?? ?? ?? ?? 8D ?? ?? ?? ?? ?? ?? 50 6A 12` | `90 90 90 90 90 90` |

All patches convert conditional jumps (JE/JZ) to NOPs, unconditionally enabling offzone placement in the editor.

### 4.2 Editor Edge Camera Scroll Disable

**Source**: `EditorDeveloper/Main.as`

| Version | Pattern | Replacement |
|---------|---------|-------------|
| Forever (32-bit) | `83 EC 3C D9 EE` | `C2 0C 00` (RET 0x0C -- early return) |

For TM2020/MP4/Turbo, scrolling is disabled by setting `OrbitalCameraControl.m_ParamScrollAreaStart = 1.1` and `.m_ParamScrollAreaMax = 1.1` (both values > 1.0 effectively disable edge scrolling).

### 4.3 Embed Size Limit Bypass

**Source**: `InfiniteEmbedSize/EmbedLimit.as`

| Version | Pattern | Replacement |
|---------|---------|-------------|
| TM2020 (64-bit) | `76 08 C7 00 01 00 00 00 EB 2D` | `EB` (JBE -> JMP) |
| MP4.1 (64-bit) | `81 FB 00 A0 0F 00 76` | `81 FB 00 A0 0F 00 EB` (JBE -> JMP) |
| Turbo (32-bit) | `83 C4 10 3B ?? ?? ?? ?? ?? 76` | `83 C4 10 3B ?? ?? ?? ?? ?? EB` |
| Other (32-bit) | `81 FE 00 A0 0F 00 76 08 C7` | `81 FE 00 A0 0F 00 EB` |

The `0x000FA000` value (1,024,000 bytes = ~1000 KB) appears in the MP4/32-bit patterns as the comparison threshold. All patches change conditional branches to unconditional jumps.

### 4.4 Max Challenge Size Pattern

**Source**: `InfiniteEmbedSize/MaxChallengeSize.as`

| Version | Pattern | Purpose |
|---------|---------|---------|
| TM2020 (Windows) | `3B ?? ?? ?? ?? ?? 77 0F 33 C0` | Locates the max challenge size global variable |
| TM2020 (Linux) | `48 8D 0D ?? ?? ?? ?? 3B 01 76 0B` | Linux variant, offset at +3 |

The address is resolved via RIP-relative addressing:
```
ptr = Dev::FindPattern(pattern)
ptrOffset = Dev::ReadInt32(ptr + 2)  // or +3 for Linux
globalVar = ptr + 2 + 4 + ptrOffset  // RIP-relative resolution
```

The value at this address is set to `(maxBytes - 0xC00)` where default maxBytes = 12 * 1024 * 1024. The `0xC00` (3072 byte) subtraction "matches Nadeo's amounts".

---

## 5. Game Events and Hooks

### 5.1 Openplanet Callback Functions

Every plugin can implement these standard callbacks:

| Callback | When Called | Plugins Using |
|----------|-----------|---------------|
| `void Main()` | Plugin startup (coroutine-capable) | All plugins |
| `void Render()` | Every frame, always | Finetuner, Stats |
| `void RenderEarly()` | Before main render, for camera setup | Camera |
| `void RenderInterface()` | When overlay is open | VehicleState, Discord, BigDecor, Controls, PluginManager |
| `void RenderMenu()` | Overlay menu rendering | EditorDeveloper, Finetuner, Stats, BigDecor, ClassicMenu, UsefulInformation, PluginManager, InfiniteEmbedSize |
| `void OnDestroyed()` | Plugin unload | Stats, EditorDeveloper, InfiniteEmbedSize |
| `void OnDisabled()` | Plugin disabled | Discord |
| `void OnSettingsChanged()` | Setting modified | EditorDeveloper, Discord, InfiniteEmbedSize |
| `UI::InputBlocking OnKeyPress(bool down, VirtualKey key)` | Key events | Finetuner |

### 5.2 Meta::RunContext

**Source**: `Finetuner/src/Main.as`

```
Meta::StartWithRunContext(Meta::RunContext::NetworkAfterMainLoop, callback)
```

This allows code to run in a specific point in the game's main loop -- specifically after the network processing but before the next frame. Used by Finetuner to update render distance without visual artifacts.

### 5.3 Game State Detection Patterns

**Source**: Various plugins (Stats, Discord, ClassicMenu)

```
// In a map
TM2020/MP4.1: GetApp().RootMap !is null
Turbo/Forever: GetApp().Challenge !is null

// In map editor
TM2020/MP4: cast<CGameCtnEditorFree>(GetApp().Editor) !is null
Forever:    cast<CTrackManiaEditorCatalog>(cast<CTrackMania>(GetApp()).Editor) !is null

// In MediaTracker
TM2020: cast<CGameEditorMediaTracker>(GetApp().Editor) !is null
Others: cast<CGameCtnMediaTracker>(cast<CTrackMania>(GetApp()).Editor) !is null

// In skin editor (TM2020 only)
cast<CGameEditorSkin>(app.Editor) !is null

// In server
TM2020/MP4: serverInfo.ServerLogin != ""
Forever:    serverInfo.ServerHostName != ""

// Spectating
app.Network.Spectator

// In custom menu
app.ActiveMenus[i].CurrentFrame.IdName == "FrameMenuCustom"

// In main menu
app.ActiveMenus[0].CurrentFrame.IdName == "FrameManiaPlanetMain"
```

### 5.4 Player Access Patterns

**Source**: `VehicleState/Internal/Impl.as`

| Game | Player Access |
|------|---------------|
| TM2020 | `cast<CSmPlayer>(playground.GameTerminals[0].GUIPlayer)` |
| Turbo | `cast<CTrackManiaRace>(app.CurrentPlayground).LocalPlayerMobil` |
| MP4 | `playground.GameTerminals[0].GUIPlayer` |
| Forever | `cast<CTrackManiaRace>(app.CurrentPlayground).LocalPlayerMobil` |

Player entity ID (TM2020): `player.GetCurrentEntityID()`

---

## 6. Class Member Catalog

### 6.1 CSceneVehicleVisState Members (TM2020)

Confirmed accessible via Openplanet reflection (used in VehicleState debugger):

**Core State**:
- `InputSteer` (float, -1.0 to 1.0)
- `InputGasPedal` (float, 0.0 to 1.0)
- `InputBrakePedal` (float, 0.0 to 1.0)
- `InputIsBraking` (bool)
- `InputVertical` (float)
- `FrontSpeed` (float, m/s)
- `CurGear` (uint, 0-7)
- `EngineOn` (bool)
- `GroundDist` (float)
- `IsGroundContact` (bool)
- `IsTopContact` (bool)
- `IsTurbo` (bool)
- `IsWheelsBurning` (bool)
- `IsReactorGroundMode` (bool)
- `DiscontinuityCount` (uint)
- `RaceStartTime` (uint)
- `SimulationTimeCoef` (float, 0.0 to 1.0)
- `WaterImmersionCoef` (float, 0.0 to 1.0)
- `WetnessValue01` (float, 0.0 to 1.0)

**Vectors/Matrices**:
- `Location` (iso4 -- 3x3 rotation + 3D position)
- `Position` (vec3 -- extracted from Location)
- `WorldVel` (vec3)
- `Left` (vec3 -- column from rotation)
- `Up` (vec3)
- `Dir` (vec3)
- `WaterOverSurfacePos` (vec3)
- `ReactorAirControl` (vec3)

**Turbo/Reactor**:
- `TurboTime` (float, 0.0 to 1.0)
- `ReactorBoostLvl` (uint)
- `ReactorBoostType` (uint)
- `ReactorInputsX` (bool)
- `BulletTimeNormed` (float)

**Visual**:
- `AirBrakeNormed` (float, 0.0 to 1.0)
- `SpoilerOpenNormed` (float, 0.0 to 1.0)
- `WingsOpenNormed` (float, 0.0 to 0.08)
- `CamGrpStates` (unknown type -- reading crashes game; accessible via raw offset reads as 4 bytes at 0x00, 0x04, 0x08, 0x0C relative)

**Per-Wheel** (FL, FR, RL, RR):
- `{X}DamperLen` (float, 0.0 to ~0.2)
- `{X}WheelRot` (float, 0.0 to ~1608.495)
- `{X}WheelRotSpeed` (float)
- `{X}SteerAngle` (float, -1.0 to 1.0)
- `{X}SlipCoef` (float, 0.0 to 1.0)
- `{X}GroundContactMaterial` (ESurfId)
- `{X}BreakNormedCoef` (float, 0.0 to 1.0)
- `{X}Icing01` (float, 0.0 to 1.0)
- `{X}TireWear01` (float, 0.0 to 1.0)

**Note on wheel indices**: The exported API uses FL=0, FR=1, RL=2, RR=3 but internally the memory order is FL=0, FR=1, RR=2, RL=3 (clockwise). The comment states: "These indices are inconsistent with the game's memory but must remain unchanged as to not break dependent plugins."

### 6.2 CSceneVehicleVis Members (TM2020)

- `AsyncState` (CSceneVehicleVisState@)
- `Turbo` (float, 0.0 to 1.0 -- visual turbo indicator)

### 6.3 CHmsCamera Members

**Source**: `Camera/Main.as`

- `Location` (iso4)
- `Fov` (float)
- `NearZ` (float)
- `FarZ` (float)
- `Width_Height` (float -- TM2020; aspect ratio)
- `RatioXY` (float -- other games; aspect ratio)
- `DrawRectMin` (vec2 -- normalized draw rectangle)
- `DrawRectMax` (vec2)
- `m_IsOverlay3d` (bool -- TM2020)
- `IsOverlay3d` (bool -- MP4/Turbo)
- `UseViewDependantRendering` (bool -- Forever)

Camera selection: iterate `GetApp().Viewport.Cameras` in reverse, skip overlays. Forever heuristic: skip cameras with `NearZ >= 100.0f` (menu camera).

### 6.4 CGameCtnNetServerInfo Members

**Source**: `UsefulInformation/Main.as`, `Discord/Main.as`

- `ServerName` (string)
- `ServerLogin` (string -- TM2020/MP4)
- `ServerHostName` (string -- Forever)
- `JoinLink` (string)
- `ServerVersionBuild` (string)
- `PlayerCount` (uint -- Forever)
- `MaxPlayerCount` (uint -- Forever)

### 6.5 CNetServerInfo (Connection) Members

**Source**: `UsefulInformation/Main.as`

- `RemoteIP` (string)
- `RemoteUDPPort` (uint)
- `RemoteTCPPort` (uint)

Access: `network.Client.Connections[0].Info` (only when `connection.ClientToServer == true`)

### 6.6 CTrackManiaPlayerInfo Members

**Source**: `UsefulInformation/Main.as`

- `Name` (string)
- `Login` (string)
- `WebServicesUserId` (string -- TM2020 only)
- `Language` (string)
- `Trigram` (string -- TM2020 only)
- `ClubTag` (string -- TM2020 only)

### 6.7 CGameCtnChallenge / Map Members

**Source**: `UsefulInformation/Main.as`, `Discord/Main.as`

TM2020/MP4 (via `RootMap.MapInfo`):
- `MapInfo.Name` (string)
- `MapInfo.MapUid` (string)
- `MapInfo.FileName` (string)
- `MapInfo.CopperString` (string)
- `MapInfo.AuthorNickName` (string)
- `MapInfo.AuthorLogin` (string)
- `MapInfo.TMObjective_AuthorTime` (uint)
- `MapInfo.TMObjective_GoldTime` (uint)
- `MapInfo.TMObjective_SilverTime` (uint)
- `MapInfo.TMObjective_BronzeTime` (uint)
- `MapName` (string -- direct on challenge)
- `IdName` (string -- UID)
- `Id.Value` (uint -- 0xFFFFFFFF when invalid)

Forever (via `Challenge`):
- `ChallengeName` (string)
- `Name` (string -- UID)
- `Author` (string)
- `CopperPrice` (int)
- `ChallengeParameters.AuthorTime` (uint)
- `ChallengeParameters.GoldTime` (uint)
- `ChallengeParameters.SilverTime` (uint)
- `ChallengeParameters.BronzeTime` (uint)

### 6.8 CGameCtnCollection Members

**Source**: `BigDecor/GameData.as`

- `CollectionId_Text` (string -- TM2020)
- `DisplayName` (string -- MP4/Turbo)
- `VehicleName.GetName()` (string -- all non-TM2020)
- `FolderDecoration` (CSystemFidsFolder@)
- `FolderDecoration.Leaves[i]` (CSystemFid@)

### 6.9 CGameCtnDecoration Members

**Source**: `BigDecor/Params.as`

- `IdName` (string)
- `IsInternal` (bool)
- `DecoSize` (CGameCtnDecorationSize@)
  - `.SizeX` (uint)
  - `.SizeY` (uint)
  - `.SizeZ` (uint)

### 6.10 CGameManiaPlanet / CTrackMania Members

**Source**: Various plugins

- `ManiaPlanetScriptAPI` (script API access)
- `ManiaPlanetScriptAPI.MasterServer_MSUsers[0].Id` (user ID for auth)
- `ManiaPlanetScriptAPI.Authentication_GetToken(userId, audience)`
- `ManiaPlanetScriptAPI.Authentication_GetTokenResponseReceived` (bool)
- `ManiaPlanetScriptAPI.Authentication_ErrorCode` (int)
- `ManiaPlanetScriptAPI.Authentication_Token` (string)
- `ManiaTitleFlowScriptAPI.EditNewMap(...)` (Turbo)
- `ManiaTitleControlScriptAPI.EditNewMap2(...)` (TM2020/MP4)
- `LoadedManiaTitle` (CGameManiaTitle@)
- `LoadedManiaTitle.TitleId` (string)
- `LoadedManiaTitle.BaseTitleId` (string)
- `LoadedManiaTitle.IdName` (string)
- `LoadedManiaTitle.Name` (string)
- `LoadedManiaTitle.CollectionFids` (CSystemFid@[])
- `MenuManager.MenuCustom_CurrentManiaApp.DataFileMgr` (for NadeoServices map queries)
- `ActiveMenus[i].CurrentFrame.IdName` (string)
- `Viewport` (CHmsViewport@)
- `Viewport.Cameras` (CHmsCamera@[])
- `Viewport.Overlays` (CHmsOverlay@[])
- `Viewport.AverageFps` (float)
- `GameScene` (ISceneVis@ / CGameScene@)
- `GameCamera` (camera for MP4 vis ID)
- `CurrentPlayground` (playground access)
- `CurrentPlayground.GameTerminals` (terminal/player access)
- `CurrentPlayground.Players` (player list)
- `CurrentPlayground.Interface` (UI interface)
- `CurrentPlayground.Arena.Resources.m_AllGameItemModels` (item models array)
- `Network` (CTrackManiaNetwork@)
- `Network.Client` (CNetClient@)
- `Network.Client.Connections` (connection list)
- `Network.ServerInfo` (CGameCtnNetServerInfo@)
- `Network.PlayerInfo` (local player info)
- `Network.PlayerInfos` (all player infos)
- `Network.Spectator` (bool)
- `Network.GetManialinkPages()` (manialink page list)
- `UserManagerScript` (display name resolution)
- `Editor` (current editor, various cast targets)
- `EditorBase` (CGameEditorBase@ -- MP4)
- `ChatManagerScript.CurrentServerPlayerCount` (int)
- `ChatManagerScript.CurrentServerPlayerCountMax` (int)
- `BuddiesManager.CurrentServerPlayerCount` (int -- Turbo)
- `BuddiesManager.CurrentServerPlayerCountMax` (int -- Turbo)
- `RootMap` / `Challenge` (current map)

### 6.11 Viewport / CVisionViewport Members

**Source**: `Finetuner/src/01_RenderDistance.as`

- `AsyncRender` (bool -- enables async rendering to allow render distance with UI)

### 6.12 System Configuration Members

**Source**: `Finetuner/src/*.as`

Accessed via `GetSystemConfig()`:
- `Display.GeomLodScaleZ` (float -- LOD distance scale, default 1.0)
- `Display.Decals_3D__TextureDecals_` (bool -- TM2020, 3D decals)
- `Display.TextureDecals_3D` (bool -- MP4/Turbo)
- `Display.TextureDecals_2D` (bool -- MP4)

### 6.13 Editor UI Controls

**Source**: `EditorDeveloper/Main.as`

Editor interface hierarchy:
```
editor.EditorInterface.InterfaceScene.Mobils[0]  // root CControlContainer
  -> FindControl("FrameDeveloperTools")           // developer tools panel
  -> FindControl("FrameEditTools")
     -> FindControl("ButtonOffZone")              // offzone button (hidden by default)
  -> FindControl("FrameLightTools")               // light tools bar
```

### 6.14 Race Interface Members

**Source**: `Discord/Main.as`

MP4/Turbo/Forever:
- `CTrackManiaRaceInterface.PlayerGeneralPosition` (int -- server position)
- `CTrackManiaRaceInterface.CurrentRacePositionText` (string -- Forever)
- `CTrackManiaRaceInterface.TimeCountDown` (uint -- milliseconds)

TM2020: Countdown is read from ManiaLink pages:
```
Network.GetManialinkPages()[i].MainFrame.Controls[0]
  -> Check ControlId == "Race_Countdown"
  -> GetFirstChild("label-countdown").Value  // time string
```

ShootMania:
- `CSmArenaInterfaceUI.InterfaceRoot` -> FindControl("LabelTimeLeft") -> `.Label`

### 6.15 Permissions (TM2020)

**Source**: `ClassicMenu/ClassicMenu.as`, `BigDecor/Main.as`

```
Permissions::PlayPublicClubRoom()
Permissions::PlayLocalMap()
Permissions::CreateLocalServer()
Permissions::FindLocalServer()
Permissions::OpenAdvancedMapEditor()
Permissions::CreateAndUploadMap()
Permissions::CreateLocalMap()
Permissions::PlayAgainstReplay()
Permissions::OpenSkinEditor()
```

---

## 7. Version History

### 7.1 VehiclesManagerIndex Changes (TM2020)

**Source**: `VehicleState/Internal/Vehicle/VehicleNext.as`

| Date | VehiclesManagerIndex |
|------|---------------------|
| Before 2021-06-08 | 5 |
| 2021-06-08 | 4 |
| 2022-03-18 | 11 |
| 2022-03-31 | 12 |
| 2022-07-08 | 11 |
| 2023-03-03 | 12 |
| 2025-09-26 | 13 |

### 7.2 VehiclesOffset Changes (TM2020)

**Source**: `VehicleState/Internal/Vehicle/VehicleNext.as`

| Date | VehiclesOffset |
|------|---------------|
| Before 2023-03-03 | 0x1C8 |
| 2023-03-03 | 0x1E0 |
| 2023-12-21 | 0x210 |

These track internal changes to the `NSceneVehicleVis_SMgr` struct layout across game patches.

---

## 8. Camera System Internals

**Source**: `Camera/Main.as`, `Camera/Impl.as`, `Camera/Export.as`

### 8.1 Projection Matrix Construction

The Camera plugin constructs a projection matrix from the active CHmsCamera:

```
projection = Perspective(fov, aspect, nearZ, farZ)
translation = Translate(camLoc.tx, camLoc.ty, camLoc.tz)
rotation = Inverse(Inverse(translation) * mat4(camLoc))
g_projection = projection * Inverse(translation * rotation)
```

### 8.2 World-to-Screen Projection

```
projectedPoint = g_projection * worldPos
if (projectedPoint.w == 0) -> invalid
screenPos = displayPos + (projectedPoint.xy / projectedPoint.w + 1) / 2 * displaySize
behindCamera = projectedPoint.w > 0
```

Display bounds come from the camera's `DrawRectMin`/`DrawRectMax` (normalized coordinates), mapped to actual display size via `Display::GetSize()`.

### 8.3 Camera Selection Algorithm

Cameras are iterated in reverse order from `Viewport.Cameras`. The first non-overlay camera is selected:
- TM2020: Skip if `m_IsOverlay3d == true`
- MP4/Turbo: Skip if `IsOverlay3d == true`
- Forever: Skip if `NearZ >= 100.0f` (menu camera) or `UseViewDependantRendering == false`

---

## 9. Editor System Internals

**Source**: `EditorDeveloper/Main.as`, `BigDecor/`

### 9.1 Map Creation API

**Turbo**:
```
app.ManiaTitleFlowScriptAPI.EditNewMap(
    collectionId,    // "Stadium"
    decorationName,  // "Day"
    textureModPath,  // "Skins/Stadium/Mod/MyMod.zip"
    playerModel,     // "StadiumCar"
    "RaceCE.Script.txt", "", ""
)
```

**TM2020/MP4**:
```
app.ManiaTitleControlScriptAPI.EditNewMap2(
    collectionId,    // "Stadium"
    decorationName,  // "Base48x48Day"
    textureModPath,  // "Skins/Stadium/Mod/MyMod.zip"
    playerModel,     // "CarSport"
    "", false, "", ""
)
```

### 9.2 Environment/Collection IDs

**TM2020**: Stadium, GreenCoast, RedIsland, BlueBay, WhiteShore, Stadium256
**MP4**: Stadium, Valley, Canyon, Lagoon

### 9.3 Player Model Names

**TM2020**: CarSport, CarSnow, CarRally, CarDesert, CharacterPilot
**MP4**: StadiumCar, CanyonCar, ValleyCar, LagoonCar

### 9.4 Decoration Size Manipulation

The BigDecor plugin modifies `CGameCtnDecoration.DecoSize` (SizeX/Y/Z) before calling `EditNewMap2`, then restores the original values when the editor closes. This allows creating maps larger than the standard 48x48 size. The maximum slider value is 255 per axis.

---

## 10. Networking Internals

### 10.1 Server Connection Details

**Source**: `UsefulInformation/Main.as`

Accessible via `network.Client.Connections[0]`:
- `.ClientToServer` (bool -- identifies the server connection vs other connections)
- `.Info` -> `CNetServerInfo` with RemoteIP, RemoteUDPPort, RemoteTCPPort

### 10.2 Server Join Links

**Source**: `Discord/Main.as`

Join URL format:
- **Forever**: `#join=serverHostName` or `#spectate=serverHostName`
- **MP4/TM2020**: `#qjoin=serverLogin@titleId` or `#qspectate=spec|serverLogin@titleId`

Opened via: `app.ManiaPlanetScriptAPI.OpenLink(url, CGameManiaPlanetScriptAPI::ELinkType::ManialinkBrowser)`

### 10.3 NadeoClubServices Deprecation

**Source**: `NadeoServices/NadeoServices.as`

As of 2024-01-31, `NadeoClubServices` was deprecated by Nadeo. All requests with this audience are silently redirected to `NadeoLiveServices`. The Meet API will "soon" no longer accept the old audience name.

---

## 11. Rendering and Display Settings

### 11.1 Render Distance

**Source**: `Finetuner/src/01_RenderDistance.as`

Modified via `camera.FarZ`. Default FarZ for Forever is 50000. The plugin sets this directly on the active camera each frame. Block size is 32 meters (used to display approximate block count).

### 11.2 Async Rendering

When render distance limiting is enabled with UI visible, `CVisionViewport.AsyncRender` must be set to `true` for the distance limit to take effect (only applicable when not in editor).

### 11.3 Level of Detail

Modified via `GetSystemConfig().Display.GeomLodScaleZ`. Higher values cause low-poly LODs to be used more aggressively.

### 11.4 Overlay Scaling

Applied to all viewport overlays: `viewport.Overlays[i].m_AdaptRatio = EHmsOverlayAdaptRatio::ShrinkToKeepRatio`

---

## 12. Plugin System Meta-Intelligence

### 12.1 Openplanet Dev API Functions

Confirmed functions available through `Dev::` namespace:
- `Dev::GetOffsetUint8(nod, offset)` / `GetOffsetUint16` / `GetOffsetUint32` / `GetOffsetUint64`
- `Dev::GetOffsetInt32(nod, offset)`
- `Dev::GetOffsetFloat(nod, offset)`
- `Dev::GetOffsetVec3(nod, offset)`
- `Dev::GetOffsetIso4(nod, offset)`
- `Dev::GetOffsetNod(nod, offset)`
- `Dev::SetOffset(nod, offset, value)` (used for camera position)
- `Dev::ReadCString(address)` (reads null-terminated string from absolute address)
- `Dev::ReadFloat(address)` / `ReadUint32` / `ReadUint16` / `ReadInt32`
- `Dev::Write(address, value)` (writes to absolute memory address)
- `Dev::FindPattern(pattern)` (returns address of first match)
- `Dev::ForceCast<T>(nod)` (unsafe cast between nod types)

### 12.2 Reflection System

- `Reflection::GetType("ClassName")` -> `MwClassInfo@`
- `Reflection::TypeOf(nod)` -> `MwClassInfo@`
- `MwClassInfo.GetMember("memberName")` -> `MwMemberInfo@`
- `MwMemberInfo.Offset` (uint16 -- 0xFFFF when invalid)
- `MwClassInfo.Name` (string)

### 12.3 PatternPatch System

Used for binary patching:
- `PatternPatch(searchPattern, replacePattern)` -> `IPatch@`
- `patch.Apply()` -- applies the replacement
- `patch.Revert()` -- restores original bytes
- `patch.IsApplied()` -- check if currently applied

### 12.4 Fids System (File Access)

- `Fids::Preload(fid)` -- loads a file's nod (CMwNod) from its fid
- `Fids::GetUserFolder(path)` -- gets user folder
- `Fids::GetFakeFolder(name)` -- gets virtual folder
- `Fids::GetFidsFolder(tree, path)` -- gets folder within tree
- `Fids::UpdateTree(folder)` -- refreshes folder contents
- `GetFidFromNod(nod)` -- reverse lookup from nod to fid

### 12.5 Meta Plugin System

- `Meta::AllPlugins()` -> `Meta::Plugin@[]`
- `Meta::UnloadedPlugins()` -> unloaded plugin info list
- `Meta::GetPluginFromSiteID(id)` -> `Meta::Plugin@`
- `Meta::GetPluginFromID(id)` -> `Meta::Plugin@`
- `Meta::LoadPlugin(path, source, type)` -> `Meta::Plugin@`
- `Meta::UnloadPlugin(plugin)` (queues unload, not immediate)
- `Meta::PluginIndex()` -- dependency graph builder
  - `.AddTree(plugin)` -- adds plugin and all dependents
  - `.TopologicalSort()` -- returns load order

Plugin properties: `.ID`, `.Name`, `.Version`, `.Author`, `.Category`, `.SiteID`, `.Type`, `.Enabled`, `.SourcePath`
Plugin types: `Meta::PluginType::Zip`, `Meta::PluginType::Folder`

### 12.6 Discord Integration IDs

**Source**: `Discord/Main.as`

| Game | Discord Application ID |
|------|----------------------|
| TM2020 | `689165864028864558` |
| Turbo | `500620964195991562` |
| Forever | `713505734515621939` |
| ManiaPlanet | `415975536343646208` |

### 12.7 Conditional Compilation Defines

Observed `#if` directives across all plugins:

| Define | Meaning |
|--------|---------|
| `TMNEXT` | Trackmania 2020 |
| `TURBO` | Trackmania Turbo |
| `MP4` | ManiaPlanet 4 (any) |
| `MP41` | ManiaPlanet 4.1 specifically |
| `MP40` | ManiaPlanet 4.0 specifically |
| `FOREVER` | TM United/Nations Forever |
| `UNITED_FOREVER` | TM United Forever specifically |
| `NATIONS_FOREVER` | TM Nations Forever specifically |
| `MANIA64` | 64-bit ManiaPlanet build |
| `LINUX` | Linux build |
| `LOGS` | Debug/logging build |
| `DEVELOPER` | Developer mode enabled |
| `SIG_DEVELOPER` | Signed developer mode |
| `MPD` | ManiaPlanet Dedicated? |

---

## Appendix A: Complete File Inventory

### VehicleState Plugin (11 files)
- `Internal/Impl.as` - Player/vis lookup, entity ID masks
- `Internal/SceneVis.as` - ISceneVis manager enumeration at +0x08, +0x10, +0x290
- `Internal/Vehicle/VehicleNext.as` - TM2020 vehicle vis manager (index 13, offset 0x210)
- `Internal/Vehicle/VehicleForever.as` - Forever CSceneVehicleCar wrapper
- `Internal/Vehicle/VehicleMP4.as` - MP4 offsets (player +0x2B8, +0x2C4; vehicles +0x38)
- `Internal/Vehicle/VehicleTurbo.as` - Turbo offsets (mobil +0x14, vis +0x84)
- `StateWrappers.as` - All enum definitions, complete struct layouts for MP4/Turbo/Forever
- `Export.as` - Public API exports
- `Main.as` - Reflection-based offset discovery for TM2020
- `Settings.as` - Debug settings
- `Debugger/Main.as` - Complete member access catalog for all CSceneVehicleVisState fields

### NadeoServices Plugin (6 files)
- `NadeoServices.as` - Base URLs, HTTP methods, auth header, account ID conversion
- `AccessToken.as` - Token lifecycle (55min + random), exponential backoff
- `CoreToken.as` - Core token (always valid)
- `IToken.as` - Token interface
- `Main.as` - Token refresh loop
- `Export.as` - Public API with usage example

### Camera Plugin (3 files)
- `Impl.as` - World-to-screen projection, editor orbital camera control
- `Main.as` - Camera selection algorithm, projection matrix construction
- `Export.as` - Public API exports

### EditorDeveloper Plugin (1 file)
- `Main.as` - Offzone binary patch, scroll disable, developer tools, light tools, orbital camera params

### InfiniteEmbedSize Plugin (5 files)
- `EmbedLimit.as` - Embed limit bypass patterns for all games
- `NetConfig.as` - TCP packet size limit (CNetClient -> NetConfig +0x38)
- `MaxChallengeSize.as` - Max challenge size pattern and RIP-relative address resolution
- `Main.as` - Patch application, size calculation with 0xC00 offset
- `Settings.as` - Default 12MB limit

### Finetuner Plugin (6 files)
- `src/Main.as` - NetworkAfterMainLoop run context
- `src/01_RenderDistance.as` - Camera FarZ manipulation, async rendering
- `src/02_OverlayScaling.as` - Viewport overlay adapt ratio
- `src/03_LevelOfDetail.as` - GeomLodScaleZ system config
- `src/04_Decals.as` - Texture decals system config
- `src/90_FPS.as` - Viewport.AverageFps display
- `src/99_Shortcuts.as` - Key binding system

### Stats Plugin (2 files)
- `Main.as` - Game state detection patterns, editor type detection
- `Statistics.as` - Time tracking persistence

### Discord Plugin (5 files)
- `Main.as` - Application IDs, comprehensive game state machine, ManiaLink page parsing
- `Services.as` - NadeoServices map thumbnail fetch
- `Notify.as` - Change notification helpers
- `Settings.as` - Display settings
- `Titles.as` - Title pack ID to Discord image key mapping (47 entries)

### BigDecor Plugin (6 files)
- `Main.as` - Decoration size manipulation, Fids::Preload
- `GameData.as` - Collection/decoration/texture mod enumeration
- `Params.as` - EditNewMap/EditNewMap2 API calls
- `PreloadingFid.as` - Lazy fid loading wrapper
- `Settings.as` - Size limits
- `Window.as` - Environment names, player model names

### ClassicMenu Plugin (1 file)
- `ClassicMenu.as` - MenuMultiPlayer_OnInternet, MenuMultiLocal, MenuEditors; Permissions API

### Controls Plugin (5 files)
- UI component library (Tags, Frames) -- no game engine intelligence

### UsefulInformation Plugin (1 file)
- `Main.as` - Server connection details, player info, map info access patterns

### PluginManager Plugin (21 files)
- `src/Utils/API.as` - Openplanet API base URL and endpoints
- `src/Settings.as` - API/web URLs
- Other files: Plugin management UI (no game engine intelligence)

# Openplanet Deep Mining -- Extended Game Engine Intelligence

This document extends [19-openplanet-intelligence.md](19-openplanet-intelligence.md) with additional data mined from all 81 AngelScript (.as) files across 12 Openplanet plugin directories. It covers memory layouts not in the first pass, API details, binary patch patterns, class member catalogs, and plugin system internals.

---

## Memory Layout Intelligence

### CSceneVehicleVis Entity ID and Vehicle Vis Manager (TM2020/Next)

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

### ISceneVis Manager Array (Alternative Layout)

Two different manager arrays exist within `ISceneVis`:

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

The +0x10 array provides fast indexed access. The +0x290 array stores metadata including class name strings.

### CSceneVehicleVisState Reflection-Based Offsets (TM2020/Next)

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

These imply the following in-memory layouts:

Near `FrontSpeed`:
```
FrontSpeed - 0x00: float FrontSpeed
FrontSpeed + 0x04: float SideSpeed
FrontSpeed + 0x08: (unknown 4 bytes)
FrontSpeed + 0x0C: int   CruiseDisplaySpeed
```

Near `CurGear`:
```
CurGear - 0x0C: float EngineRPM
CurGear - 0x08: (unknown)
CurGear - 0x04: (unknown)
CurGear + 0x00: uint  CurGear
```

Near wheel data (e.g. FL):
```
FLIcing01 - 0x04: float FLDirt
FLIcing01 + 0x00: float FLIcing01
```

```
FLBreakNormedCoef + 0x00: float FLBreakNormedCoef
FLBreakNormedCoef + 0x04: int   FLFallingState
```

**Vehicle type** is read as uint8 at `InputSteer.Offset - 0x08`, used as an index into `playground.Arena.Resources.m_AllGameItemModels[]` to look up the vehicle model's MwId.

### CSceneVehicleVisState Hardcoded Offsets (ManiaPlanet 4)

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

### CSceneVehicleVisState Hardcoded Offsets (Turbo)

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

### CSceneVehicleCar Hardcoded Offsets (TMNF/Forever)

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

### Additional Pointer Layouts

**CTrackManiaPlayer (MP4)**:
```
  +0x2B8: CMwNod* vehicleVisPtr   (same pointer as found via VehicleVisMgr)
  +0x2C4: uint32  EntityId
```

**CSceneMgrVehicleVisImpl (MP4)**:
```
  +0x38: CMwNod* vehicles_ptr
  +0x40: uint32  vehicles_count
```

**CGameMobil (Turbo)**:
```
  +0x14: CMwNod* vehicleMobilPtr
    -> +0x84: CMwNod* vehicleVisPtr
```

**CGameCamera (MP4)**:
```
  +0xD4: uint32 ViewingVisId
```
Special viewing ID `0x0FF00000` is used during intro/podium scenes (when camera is null).

**CNetClient NetConfig**:
```
CNetClient:
  TCPSendingNodTotal.Offset + 4: IntPtr netConfigPtr  (pointer to NetConfig struct)

NetConfig (TM2020):
  +0x38: uint32 TcpMaxPacketSize
```

**CGameCtnEditorCommon Orbital Camera**:
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

## Enum Definitions

### FallingState (TM2020 only)

```
enum FallingState {
    FallingAir     = 0,
    FallingWater   = 2,
    RestingGround  = 4,
    RestingWater   = 6,
    GlidingGround  = 8
}
```

Values are always even. The plugin validates against this exact set and rejects unexpected values.

### TurboLevel (TM2020 only)

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

### VehicleType (TM2020 only)

```
enum VehicleType {
    CharacterPilot = 0,
    CarSport       = 1,  // Stadium
    CarSnow        = 2,
    CarRally       = 3,
    CarDesert      = 4
}
```

Vehicle type is determined by reading a uint8 index from the vis state, looking up the corresponding `CGameItemModel` from `playground.Arena.Resources.m_AllGameItemModels[index]`, and comparing its `MwId` against known vehicle IDs.

### EffectFlags (MP4/Turbo/Forever)

```
enum EffectFlags {
    FreeWheeling       = 1,    // All games
    ForcedAcceleration = 2,    // MP4 only
    NoBrakes           = 4,    // MP4 only
    NoSteering         = 8,    // MP4 only
    NoGrip             = 16    // MP4 only
}
```

### ESurfId (Ground Contact Material)

Referenced via `CAudioSourceSurface::ESurfId` (TM2020/MP4/Turbo) or `CAudioSoundSurface::ESurfId` (Forever). These are uint16 values stored in the wheel struct. Actual enum values come from the game's audio surface type system.

### EHmsOverlayAdaptRatio (TM2020)

Referenced with value `ShrinkToKeepRatio` as default. Applied to viewport overlays via `viewport.Overlays[i].m_AdaptRatio`.

### ShortcutMode

```
enum ShortcutMode {
    Toggle      = 0,
    Hold        = 1,
    InverseHold = 2
}
```

---

## API Intelligence

### Nadeo Services Base URLs

| Audience | Base URL |
|----------|----------|
| NadeoServices (Core) | `https://prod.trackmania.core.nadeo.online` |
| NadeoLiveServices (Live) | `https://live-services.trackmania.nadeo.live` |
| NadeoLiveServices (Meet) | `https://meet.trackmania.nadeo.club` |

**DEPRECATION**: As of 2024-01-31, `NadeoClubServices` is deprecated. All requests redirect to `NadeoLiveServices`.

### Authentication Pattern

Two token types:
1. **CoreToken** (`NadeoServices`): Retrieved directly via `Internal::NadeoServices::GetCoreToken()` -- always authenticated, no refresh needed.
2. **AccessToken** (`NadeoLiveServices`): Obtained via `api.Authentication_GetToken(userId, audience)`.

**Token lifecycle**:
- Tokens are valid for **55 minutes** + random 1-60 seconds.
- On failure: exponential backoff retry (1s, 2s, 4s, 8s, 16s, ...) -- "intentionally mimicking Nadeo's code".
- Auth header format: `Authorization: nadeo_v1 t=<token>`

**Authentication flow**:
```
CGameManiaPlanet.ManiaPlanetScriptAPI.Authentication_GetToken(MSUsers[0].Id, audience)
  -> wait for .Authentication_GetTokenResponseReceived
  -> check .Authentication_ErrorCode == 0
  -> read .Authentication_Token
```

### Account ID / Login Conversion

Login (base64url) to AccountId (UUID) conversion:
```
Login: "c5jutptORLinoaIUmVWscA"
  -> Base64url decode -> raw bytes
  -> Format as: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
Result: "7398eeb6-9b4e-44b8-a7a1-a2149955ac70"
```

UUID format: 4-2-2-2-6 byte groups from the 16-byte decoded base64.

### Display Name Resolution

Display names are resolved via `UserManagerScript`:
```
userMgr.FindDisplayName(accountId)  // checks cache first
userMgr.RetrieveDisplayName(userId, accountIds)  // batch fetch, max 209 per batch
userMgr.TaskResult_Release(req.Id)  // cleanup
```

The batch limit of **209 account IDs per request** is enforced in the code.

### Map Info from Services

```
maniaApp.DataFileMgr.Map_NadeoServices_GetListFromUid(0, uids)
  -> req.MapList[i].Uid
  -> req.MapList[i].ThumbnailUrl  (with ".jpg" suffix appended if missing)
```

### Openplanet Plugin API

Base URL: `https://api.openplanet.dev`

Endpoints:
- `GET /plugins?tags=Trackmania&page=0` -- list plugins
- `GET /plugins?tags=Trackmania&order=f` -- featured
- `GET /plugins?tags=Trackmania&order=d` -- popular (by downloads)
- `GET /plugins?tags=Trackmania&order=u` -- last updated
- `GET /plugins?tags=Trackmania&search=query` -- search
- `GET /plugins?ids=1,2,3` -- specific plugins
- `GET /plugin/{siteID}` -- single plugin details
- `GET /plugin/{siteID}/versions` -- changelog/versions
- `GET /plugin/{siteID}/download` -- download plugin .op file
- `GET /versions?ids=1,2,3` -- batch version check for updates

---

## Binary Patch Patterns

These patches modify the game binary at runtime. All convert conditional jumps to NOPs or unconditional jumps.

### Editor Offzone Enable Patch

| Version | Pattern | Replacement |
|---------|---------|-------------|
| TM2020 (release) | `0F 84 ?? ?? ?? ?? 4C 8D 45 ?? BA 13` | `90 90 90 90 90 90` (NOP 6 bytes) |
| TM2020 (logs/debug) | `0F 84 ?? ?? ?? ?? 4C 8D 45 F0 BA ?? ?? ?? ?? 48 8B CF E8 ?? ?? ?? ?? E9 ?? ?? ?? ?? 45 85 FF 0F 84 ?? ?? ?? ?? 83 BF ?? ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? 39` | `90 90 90 90 90 90` |
| MP4.1 (64-bit) | `F6 86 ?? ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? 4C 8D 44 24 70 BA` | `90 90 90 90 90 90 90 90 90 90 90 90 90` (NOP 13 bytes) |
| MP4 (32-bit) | `0F 84 ?? ?? ?? ?? 8D ?? ?? ?? ?? ?? ?? 50 6A 12` | `90 90 90 90 90 90` |

### Editor Edge Camera Scroll Disable

| Version | Pattern | Replacement |
|---------|---------|-------------|
| Forever (32-bit) | `83 EC 3C D9 EE` | `C2 0C 00` (RET 0x0C -- early return) |

For TM2020/MP4/Turbo, scrolling is disabled by setting `OrbitalCameraControl.m_ParamScrollAreaStart = 1.1` and `.m_ParamScrollAreaMax = 1.1` (both > 1.0 disables edge scrolling).

### Embed Size Limit Bypass

| Version | Pattern | Replacement |
|---------|---------|-------------|
| TM2020 (64-bit) | `76 08 C7 00 01 00 00 00 EB 2D` | `EB` (JBE -> JMP) |
| MP4.1 (64-bit) | `81 FB 00 A0 0F 00 76` | `81 FB 00 A0 0F 00 EB` (JBE -> JMP) |
| Turbo (32-bit) | `83 C4 10 3B ?? ?? ?? ?? ?? 76` | `83 C4 10 3B ?? ?? ?? ?? ?? EB` |
| Other (32-bit) | `81 FE 00 A0 0F 00 76 08 C7` | `81 FE 00 A0 0F 00 EB` |

The `0x000FA000` value (1,024,000 bytes) appears as the comparison threshold. All patches change conditional branches to unconditional jumps.

### Max Challenge Size Pattern

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

The value at this address is set to `(maxBytes - 0xC00)` where default maxBytes = 12 * 1024 * 1024.

---

## Game Events and Hooks

### Openplanet Callback Functions

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

### Meta::RunContext

```
Meta::StartWithRunContext(Meta::RunContext::NetworkAfterMainLoop, callback)
```

This runs code after network processing but before the next frame. Finetuner uses this to update render distance without visual artifacts.

### Game State Detection Patterns

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

### Player Access Patterns

| Game | Player Access |
|------|---------------|
| TM2020 | `cast<CSmPlayer>(playground.GameTerminals[0].GUIPlayer)` |
| Turbo | `cast<CTrackManiaRace>(app.CurrentPlayground).LocalPlayerMobil` |
| MP4 | `playground.GameTerminals[0].GUIPlayer` |
| Forever | `cast<CTrackManiaRace>(app.CurrentPlayground).LocalPlayerMobil` |

Player entity ID (TM2020): `player.GetCurrentEntityID()`

---

## Class Member Catalog

### CSceneVehicleVisState Members (TM2020)

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

### CSceneVehicleVis Members (TM2020)

- `AsyncState` (CSceneVehicleVisState@)
- `Turbo` (float, 0.0 to 1.0 -- visual turbo indicator)

### CHmsCamera Members

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

### CGameCtnNetServerInfo Members

- `ServerName` (string)
- `ServerLogin` (string -- TM2020/MP4)
- `ServerHostName` (string -- Forever)
- `JoinLink` (string)
- `ServerVersionBuild` (string)
- `PlayerCount` (uint -- Forever)
- `MaxPlayerCount` (uint -- Forever)

### CNetServerInfo (Connection) Members

- `RemoteIP` (string)
- `RemoteUDPPort` (uint)
- `RemoteTCPPort` (uint)

Access: `network.Client.Connections[0].Info` (only when `connection.ClientToServer == true`)

### CTrackManiaPlayerInfo Members

- `Name` (string)
- `Login` (string)
- `WebServicesUserId` (string -- TM2020 only)
- `Language` (string)
- `Trigram` (string -- TM2020 only)
- `ClubTag` (string -- TM2020 only)

### CGameCtnChallenge / Map Members

TM2020/MP4 (via `RootMap.MapInfo`):
- `MapInfo.Name`, `MapInfo.MapUid`, `MapInfo.FileName`
- `MapInfo.CopperString`, `MapInfo.AuthorNickName`, `MapInfo.AuthorLogin`
- `MapInfo.TMObjective_AuthorTime/GoldTime/SilverTime/BronzeTime` (uint)
- `MapName` (direct on challenge)
- `IdName` (UID)
- `Id.Value` (uint -- 0xFFFFFFFF when invalid)

Forever (via `Challenge`):
- `ChallengeName`, `Name` (UID), `Author`
- `CopperPrice` (int)
- `ChallengeParameters.AuthorTime/GoldTime/SilverTime/BronzeTime` (uint)

### CGameCtnCollection Members

- `CollectionId_Text` (string -- TM2020)
- `DisplayName` (string -- MP4/Turbo)
- `VehicleName.GetName()` (string -- all non-TM2020)
- `FolderDecoration` (CSystemFidsFolder@)
- `FolderDecoration.Leaves[i]` (CSystemFid@)

### CGameCtnDecoration Members

- `IdName` (string)
- `IsInternal` (bool)
- `DecoSize` (CGameCtnDecorationSize@)
  - `.SizeX`, `.SizeY`, `.SizeZ` (uint)

### CGameManiaPlanet / CTrackMania Members

- `ManiaPlanetScriptAPI` (script API access)
- `ManiaPlanetScriptAPI.MasterServer_MSUsers[0].Id` (user ID for auth)
- `ManiaPlanetScriptAPI.Authentication_GetToken(userId, audience)`
- `ManiaPlanetScriptAPI.Authentication_GetTokenResponseReceived` (bool)
- `ManiaPlanetScriptAPI.Authentication_ErrorCode` (int)
- `ManiaPlanetScriptAPI.Authentication_Token` (string)
- `ManiaTitleFlowScriptAPI.EditNewMap(...)` (Turbo)
- `ManiaTitleControlScriptAPI.EditNewMap2(...)` (TM2020/MP4)
- `LoadedManiaTitle` (CGameManiaTitle@) with `.TitleId`, `.BaseTitleId`, `.IdName`, `.Name`
- `Viewport` (CHmsViewport@) with `.Cameras`, `.Overlays`, `.AverageFps`
- `GameScene` (ISceneVis@ / CGameScene@)
- `CurrentPlayground` (playground access) with `.GameTerminals`, `.Players`, `.Interface`, `.Arena.Resources.m_AllGameItemModels`
- `Network` (CTrackManiaNetwork@) with `.Client`, `.ServerInfo`, `.PlayerInfo`, `.PlayerInfos`, `.Spectator`
- `RootMap` / `Challenge` (current map)

### Race Interface Members

MP4/Turbo/Forever:
- `CTrackManiaRaceInterface.PlayerGeneralPosition` (int)
- `CTrackManiaRaceInterface.CurrentRacePositionText` (string -- Forever)
- `CTrackManiaRaceInterface.TimeCountDown` (uint -- milliseconds)

TM2020 countdown is read from ManiaLink pages:
```
Network.GetManialinkPages()[i].MainFrame.Controls[0]
  -> Check ControlId == "Race_Countdown"
  -> GetFirstChild("label-countdown").Value  // time string
```

### Permissions (TM2020)

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

## Version History

### VehiclesManagerIndex Changes (TM2020)

| Date | VehiclesManagerIndex |
|------|---------------------|
| Before 2021-06-08 | 5 |
| 2021-06-08 | 4 |
| 2022-03-18 | 11 |
| 2022-03-31 | 12 |
| 2022-07-08 | 11 |
| 2023-03-03 | 12 |
| 2025-09-26 | 13 |

### VehiclesOffset Changes (TM2020)

| Date | VehiclesOffset |
|------|---------------|
| Before 2023-03-03 | 0x1C8 |
| 2023-03-03 | 0x1E0 |
| 2023-12-21 | 0x210 |

These track internal changes to the `NSceneVehicleVis_SMgr` struct layout across game patches.

---

## Camera System Internals

### Projection Matrix Construction

```
projection = Perspective(fov, aspect, nearZ, farZ)
translation = Translate(camLoc.tx, camLoc.ty, camLoc.tz)
rotation = Inverse(Inverse(translation) * mat4(camLoc))
g_projection = projection * Inverse(translation * rotation)
```

### World-to-Screen Projection

```
projectedPoint = g_projection * worldPos
if (projectedPoint.w == 0) -> invalid
screenPos = displayPos + (projectedPoint.xy / projectedPoint.w + 1) / 2 * displaySize
behindCamera = projectedPoint.w > 0
```

Display bounds come from the camera's `DrawRectMin`/`DrawRectMax` (normalized coordinates), mapped to actual display size via `Display::GetSize()`.

### Camera Selection Algorithm

Cameras are iterated in reverse order from `Viewport.Cameras`. The first non-overlay camera is selected:
- TM2020: Skip if `m_IsOverlay3d == true`
- MP4/Turbo: Skip if `IsOverlay3d == true`
- Forever: Skip if `NearZ >= 100.0f` (menu camera) or `UseViewDependantRendering == false`

---

## Editor System Internals

### Map Creation API

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

### Environment/Collection IDs

**TM2020**: Stadium, GreenCoast, RedIsland, BlueBay, WhiteShore, Stadium256
**MP4**: Stadium, Valley, Canyon, Lagoon

### Player Model Names

**TM2020**: CarSport, CarSnow, CarRally, CarDesert, CharacterPilot
**MP4**: StadiumCar, CanyonCar, ValleyCar, LagoonCar

### Decoration Size Manipulation

The BigDecor plugin modifies `CGameCtnDecoration.DecoSize` (SizeX/Y/Z) before calling `EditNewMap2`, then restores original values when the editor closes. Maximum slider value is 255 per axis. This allows maps larger than the standard 48x48 size.

---

## Networking Internals

### Server Connection Details

Accessible via `network.Client.Connections[0]`:
- `.ClientToServer` (bool -- identifies the server connection)
- `.Info` -> `CNetServerInfo` with RemoteIP, RemoteUDPPort, RemoteTCPPort

### Server Join Links

Join URL format:
- **Forever**: `#join=serverHostName` or `#spectate=serverHostName`
- **MP4/TM2020**: `#qjoin=serverLogin@titleId` or `#qspectate=spec|serverLogin@titleId`

Opened via: `app.ManiaPlanetScriptAPI.OpenLink(url, CGameManiaPlanetScriptAPI::ELinkType::ManialinkBrowser)`

### NadeoClubServices Deprecation

As of 2024-01-31, `NadeoClubServices` was deprecated by Nadeo. All requests with this audience redirect to `NadeoLiveServices`.

---

## Rendering and Display Settings

### Render Distance

Modified via `camera.FarZ`. Default FarZ for Forever is 50000. Block size is 32 meters (used to display approximate block count).

### Async Rendering

When render distance limiting is enabled with UI visible, `CVisionViewport.AsyncRender` must be `true` for the limit to take effect (except in editor).

### Level of Detail

Modified via `GetSystemConfig().Display.GeomLodScaleZ`. Higher values cause low-poly LODs to appear more aggressively.

### Overlay Scaling

Applied to all viewport overlays: `viewport.Overlays[i].m_AdaptRatio = EHmsOverlayAdaptRatio::ShrinkToKeepRatio`

---

## Plugin System Meta-Intelligence

### Openplanet Dev API Functions

Confirmed functions in the `Dev::` namespace:
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

### Reflection System

- `Reflection::GetType("ClassName")` -> `MwClassInfo@`
- `Reflection::TypeOf(nod)` -> `MwClassInfo@`
- `MwClassInfo.GetMember("memberName")` -> `MwMemberInfo@`
- `MwMemberInfo.Offset` (uint16 -- 0xFFFF when invalid)
- `MwClassInfo.Name` (string)

### PatternPatch System

Used for binary patching:
- `PatternPatch(searchPattern, replacePattern)` -> `IPatch@`
- `patch.Apply()` -- applies the replacement
- `patch.Revert()` -- restores original bytes
- `patch.IsApplied()` -- check if currently applied

### Fids System (File Access)

- `Fids::Preload(fid)` -- loads a file's nod (CMwNod) from its fid
- `Fids::GetUserFolder(path)` -- gets user folder
- `Fids::GetFakeFolder(name)` -- gets virtual folder
- `Fids::GetFidsFolder(tree, path)` -- gets folder within tree
- `Fids::UpdateTree(folder)` -- refreshes folder contents
- `GetFidFromNod(nod)` -- reverse lookup from nod to fid

### Meta Plugin System

- `Meta::AllPlugins()` -> `Meta::Plugin@[]`
- `Meta::UnloadedPlugins()` -> unloaded plugin info list
- `Meta::GetPluginFromSiteID(id)` / `Meta::GetPluginFromID(id)` -> `Meta::Plugin@`
- `Meta::LoadPlugin(path, source, type)` -> `Meta::Plugin@`
- `Meta::UnloadPlugin(plugin)` (queues unload, not immediate)
- `Meta::PluginIndex()` -- dependency graph builder with `.AddTree(plugin)` and `.TopologicalSort()`

Plugin properties: `.ID`, `.Name`, `.Version`, `.Author`, `.Category`, `.SiteID`, `.Type`, `.Enabled`, `.SourcePath`
Plugin types: `Meta::PluginType::Zip`, `Meta::PluginType::Folder`

### Discord Integration IDs

| Game | Discord Application ID |
|------|----------------------|
| TM2020 | `689165864028864558` |
| Turbo | `500620964195991562` |
| Forever | `713505734515621939` |
| ManiaPlanet | `415975536343646208` |

### Conditional Compilation Defines

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

---

## Related Pages

- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- First-pass extraction this document extends
- [04-physics-vehicle.md](04-physics-vehicle.md) -- Decompiled vehicle physics code
- [29-community-knowledge.md](29-community-knowledge.md) -- Community projects cross-referencing this data
- [07-networking.md](07-networking.md) -- Networking architecture overview
- [08-game-architecture.md](08-game-architecture.md) -- Game architecture using these class members

---

<details><summary>Analysis metadata</summary>

- **Generated**: 2026-03-27
- **Source**: 81 AngelScript (.as) files across 12 plugin directories
- **Scope**: Every installed Openplanet plugin, exhaustively mined
- **Confidence**: VERIFIED -- All data from working plugins that read live game memory

</details>

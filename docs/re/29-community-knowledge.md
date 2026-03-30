# Community Knowledge Cross-Reference

**Date**: 2026-03-27
**Purpose**: Catalog publicly available community reverse engineering projects, documentation, and tools for Trackmania, and cross-reference their findings with our RE work.

---

## Table of Contents

1. [Community Projects Catalog](#1-community-projects-catalog)
2. [GBX Format - Community vs RE Comparison](#2-gbx-format---community-vs-re-comparison)
3. [Physics - Community vs RE Comparison](#3-physics---community-vs-re-comparison)
4. [API Endpoints - Community vs RE Comparison](#4-api-endpoints---community-vs-re-comparison)
5. [ManiaScript - Community Documentation](#5-maniascript---community-documentation)
6. [New Information from Community Sources](#6-new-information-from-community-sources)
7. [Contradictions to Investigate](#7-contradictions-to-investigate)
8. [Gap-Filling Opportunities](#8-gap-filling-opportunities)

---

## 1. Community Projects Catalog

### 1.1 GBX Parsing Libraries

| Project | Language | URL | Status | Scope |
|---------|----------|-----|--------|-------|
| **GBX.NET** | C#/.NET | https://github.com/BigBang1112/gbx-net | Active (Jan 2026 update) | 400+ GBX classes, full read/write |
| **pygbx** | Python | https://github.com/donadigo/pygbx | Maintained (v0.3.1) | Read-only GBX parser |
| **gbx-ts** | TypeScript | https://github.com/thaumictom/gbx-ts | Active | TypeScript GBX parser |
| **GbxDump** | C/C++ | https://github.com/Electron-x/GbxDump | Maintained | Windows header viewer |
| **gbxutils** | Various | https://github.com/realh/gbxutils | Active | Utilities for map GBX files |

### 1.2 GBX Analysis Tools

| Tool | URL | Purpose |
|------|-----|---------|
| **GBX.NET Explorer** | https://explorer.gbx.tools/ | Client-side GBX inspection and modification |
| **gbxtools** (donadigo) | https://github.com/donadigo/gbxtools | Python scripts for replay analysis |
| **GbxMapBrowser** | https://github.com/ArkadySK/GbxMapBrowser | Visual map/replay browser using GBX.NET |
| **clip-input** | https://github.com/bigbang1112-cz/clip-input | Convert replay input data to Clip.Gbx overlays |

### 1.3 Physics / TAS Tools

| Tool | URL | Purpose |
|------|-----|---------|
| **TMInterface** | https://donadigo.com/tminterface/ | TAS tool for TMNF/TMUF: DLL injection, physics access, bruteforce |
| **tmrl** | https://github.com/trackmania-rl/tmrl | Reinforcement learning framework with TM2020 Gymnasium env |
| **TMTrackNN** | https://github.com/donadigo/TMTrackNN | Neural network track generation |

### 1.4 Openplanet Ecosystem

| Resource | URL | Purpose |
|----------|-----|---------|
| **Openplanet** | https://openplanet.dev/ | Modding platform for TM2020, uses AngelScript |
| **Openplanet Docs** | https://openplanet.dev/docs | Plugin development documentation |
| **Trackmania Next API** | https://next.openplanet.dev/ | Game engine class browser |
| **VehicleState Plugin** | https://openplanet.dev/docs/reference/vehiclestate | Vehicle physics data access dependency |
| **VehicleState Source** | https://github.com/openplanet-nl/vehiclestate | Source code for VehicleState dependency |

### 1.5 API Documentation

| Resource | URL | Purpose |
|----------|-----|---------|
| **Nadeo API Docs** (Openplanet) | https://webservices.openplanet.dev/ | Unofficial but authoritative API docs |
| **ManiaExchange API** | https://api2.mania.exchange/ | TMX track exchange API (v2) |
| **codecat's Web Services Gist** | https://gist.github.com/codecat/4dfd3719e1f8d9e5ef439d639abe0de4 | Original community API documentation |
| **XML-RPC Docs** | https://wiki.trackmania.io/en/dedicated-server/XML-RPC/home | Dedicated server XML-RPC reference |

### 1.6 Wikis and References

| Resource | URL | Scope |
|----------|-----|-------|
| **Mania Tech Wiki** | https://wiki.xaseco.org/wiki/GBX | GBX format internals, class IDs |
| **Mania Tech Wiki - Class IDs** | https://wiki.xaseco.org/wiki/Class_IDs | Complete engine/class/chunk ID registry |
| **Mania Tech Wiki - Internals** | https://wiki.xaseco.org/wiki/ManiaPlanet_internals | Engine architecture docs |
| **Trackmania Wiki** | https://www.trackmania.wiki/wiki/ | Community wiki (format, mechanics) |
| **ManiaPlanet Fandom Wiki** | https://maniaplanet.fandom.com/wiki/GBX | GBX format reference |
| **Official TM Docs** | https://doc.trackmania.com/ | Nadeo's official documentation |

### 1.7 ManiaScript References

| Resource | URL | Scope |
|----------|-----|-------|
| **ManiaScript Reference** (BigBang1112) | https://github.com/BigBang1112/maniascript-reference | Auto-generated Doxygen docs for TM2020/MP/Turbo |
| **ManiaScript Reference** (boss-bravo) | https://maniascript.boss-bravo.fr/ | TM2020 ManiaScript class reference |
| **ManiaScript Book** | https://maniaplanet-community.gitbook.io/maniascript | Community documentation guide |
| **Official Script-XMLRPC** | https://github.com/maniaplanet/script-xmlrpc | Official XmlRpc callback definitions |

---

## 2. GBX Format - Community vs RE Comparison

### 2.1 Header Structure

| Field | Community (Mania Tech Wiki) | Our RE (doc 06/16) | Status |
|-------|---------------------------|---------------------|--------|
| Magic "GBX" (3 bytes) | CONFIRMED | Bytes 0-2 `0x47 0x42 0x58` at `FUN_140900e60` | MATCH |
| Version (uint16) | Versions "currently 6" | Versions 3-6 supported, 1-2 rejected | MATCH |
| Format byte | `'B'`/`'T'` (Binary/Text) | `'B'`/`'T'` at byte 0 of flags | MATCH |
| Body compression | `'U'`/`'C'` | Stored at archive offset `+0xD8` | MATCH |
| Ref table compression | `'U'`/`'C'` ("unused") | Stored at offset `+0xDC` | **COMMUNITY SAYS "UNUSED", OUR RE SAYS IT CONTROLS BODY STREAM DECOMPRESSION** |
| Edit state | `'R'`/`'E'` [version >= 4] | `'R'`/`'E'` = with/without external refs | MATCH |
| Class ID (uint32) | [version >= 4] | At offset 0x09 for version 6 | MATCH |
| User data size (uint32) | [version >= 6] | At offset 0x0D for version 6 | MATCH |

**CONTRADICTION**: The Mania Tech Wiki says byte 6 (reference table compression) is "unused". Our RE shows it is stored at `+0xDC` and controls body stream decompression (LZO/zlib). The community labels byte 7 as body compression while we label byte 5 (second format flag) as body compression at `+0xD8`. The byte ordering may differ due to different counting conventions. This needs further investigation.

### 2.2 Chunk System

| Feature | Community | Our RE | Status |
|---------|-----------|--------|--------|
| Chunk ID format (32-bit) | Engine byte + class byte + chunk byte | `0x03043007` = Engine 03, Class 043, Chunk 007 | MATCH |
| End sentinel | `0xFACADE01` | `0xFACADE01` (confirmed in chunk dispatch) | MATCH |
| Skippable flag | `0x10` flag, preceded by "SKIP" marker + size | Skippable chunks include length prefix | MATCH |
| Encapsulated chunks | Reset lookbackstring list locally | Referenced in our format docs | MATCH |
| Encapsulated chunk IDs | `03043040, 03043041, 03043043, 03043044, 0304304E, 0304304F, 03043054, 03043058` | Not exhaustively listed in our RE | **GAP** |

### 2.3 Engine IDs

The Mania Tech Wiki / ManiaPlanet Internals page documents **37 engine IDs**:

| ID | Engine Name | In Our RE? |
|----|-------------|------------|
| 0x01 | ENGINE_MWFOUNDATIONS | Yes (CMw* classes) |
| 0x02 | ENGINE_DATA | Not explicitly cataloged |
| 0x03 | ENGINE_GAME | Yes (CGame* classes, 728 found) |
| 0x04 | ENGINE_GRAPHIC | Not explicitly cataloged |
| 0x05 | ENGINE_FUNCTION | Not explicitly cataloged |
| 0x06 | ENGINE_HMS | Yes (CHms* classes, 41 found) |
| 0x07 | ENGINE_CONTROL | Yes (CControl* classes, 39 found) |
| 0x08 | ENGINE_MOTION | Not explicitly cataloged |
| 0x09 | ENGINE_PLUG | Yes (CPlug* classes, 391 found) |
| 0x0A | ENGINE_SCENE | Yes (CScene* classes, 52 found) |
| 0x0B | ENGINE_SYSTEM | Yes (CSystem* classes, 24 found) |
| 0x0C | ENGINE_VISION | Yes (CVision* classes, 9 found) |
| 0x0D | ENGINE_PSY | Not found in our binary |
| 0x0E | ENGINE_EDIT | Not explicitly cataloged |
| 0x0F | ENGINE_NODEDIT | Not explicitly cataloged |
| 0x10 | ENGINE_AUDIO | Yes (CAudio* classes, 19 found) |
| 0x11 | ENGINE_SCRIPT | Yes (CScript* classes, 9 found) |
| 0x12 | ENGINE_NET | Yes (CNet* classes, 262 found) |
| 0x13 | ENGINE_INPUT | Yes (CInput* classes, 17 found) |
| 0x14 | ENGINE_XML | Yes (CXml* classes, 10 found) |
| 0x15 | ENGINE_MOVIE | Not found |
| 0x16 | ENGINE_PTP | Not found |
| 0x20 | ENGINE_CYBERDRIVE | Not found (legacy game) |
| 0x21 | ENGINE_VIRTUALSKIPPER | Not found (different game) |
| 0x22 | ENGINE_ADVENTURE | Not found (legacy) |
| 0x23 | ENGINE_LANFEUST | Not found (legacy) |
| 0x24 | ENGINE_TRACKMANIA | Yes (CTrackMania* classes, 4 found) |
| 0x25 | ENGINE_SORCIERES | Not found (legacy) |
| 0x26 | ENGINE_MG | Not found (legacy) |
| 0x27 | ENGINE_GBXVIEWER | Not found (legacy tool) |
| 0x28 | ENGINE_GBE | Not found (legacy tool) |
| 0x29 | ENGINE_MEDIATRACKERAPP | Not found (legacy tool) |
| 0x2A | ENGINE_RENDERBOX | Not found (legacy tool) |
| 0x2B | ENGINE_FBX | Not found (legacy tool) |
| 0x2C | ENGINE_QUESTMANIA | Not found |
| 0x2D | ENGINE_SHOOTMANIA | Yes (CSm* classes, 11 found) |
| 0x2E | ENGINE_GAMEDATA | Yes (CWebServices* 297 + CGameData*) |

**FINDING**: The community documents 37 engines. Many legacy/game-specific engines (VirtualSkipper, Lanfeust, Sorcieres, etc.) are absent from TM2020 as expected. Our binary contains 2,027 Nadeo classes across the active engines. The engine ID scheme is CONFIRMED.

### 2.4 Data Types

| Type | Community | Our RE | Status |
|------|-----------|--------|--------|
| bool | 32-bit LE (0 or 1) | Confirmed | MATCH |
| string | uint32 length + UTF-8 bytes | Confirmed | MATCH |
| lookbackstring | Version + index + optional new string, bits 30-31 = type | Confirmed with deep dive in doc 16 section 29 | MATCH |
| noderef | uint32 index (-1 = null) | Confirmed | MATCH |
| fileref | Version + checksum + path + locator URL | Not deeply analyzed | **GAP** |
| vec2/vec3 | float pairs/triples | Confirmed | MATCH |
| color | float r, g, b | Not specifically validated | MINOR GAP |

### 2.5 CGameCtnChallenge (Map) Chunks

From GBX.NET source (CGameCtnChallenge.cs), compared with our RE:

| Chunk ID | Community Description | Our RE | Status |
|----------|----------------------|--------|--------|
| 0x03043002 | Map metadata (times, cost, laps, checkpoints) | Confirmed in doc 16 section 16 | MATCH |
| 0x03043003 | Environment, map type, lightmap version | Referenced | MATCH |
| 0x03043007 | Thumbnail (JPEG) + comments | Referenced | MATCH |
| 0x0304300F | Map structure (mapInfo, mapName, decoration, size, blocks) | Confirmed | MATCH |
| 0x0304301F | Full block data with rotations, coordinates, flags | Confirmed | MATCH |
| 0x03043027 | Camera thumbnail (position, FOV, clip planes) | Not analyzed | **GAP** |
| 0x03043036 | Extended thumbnail (pitch/yaw/roll) | Not analyzed | **GAP** |
| 0x03043040 | Anchored objects (items) - ENCAPSULATED | Confirmed | MATCH |
| 0x03043043 | Zone genealogy | Not analyzed | **GAP** |
| 0x03043044 | Script metadata - ENCAPSULATED | Referenced | MATCH |
| 0x03043048 | Baked blocks | Not deeply analyzed | **GAP** |
| 0x03043054 | Embedded ZIP (custom assets) | Confirmed (texture storage) | MATCH |
| 0x03043069 | Macroblock instances | Not analyzed | **GAP** |
| 0x0304305B | Lightmap cache (alternate) | Referenced | PARTIAL |

### 2.6 Compression

| Feature | Community | Our RE | Status |
|---------|-----------|--------|--------|
| LZO body compression | Confirmed | LZO via `FUN_140127aa0` | MATCH |
| Zlib for lightmap/ghost data | Confirmed | Zlib confirmed for internal compressed data | MATCH |
| Compression detection | Byte 7 ('C'/'U') | Format flags byte 1 at `+0xD8` | MATCH |

### 2.7 Class ID Remapping

| Feature | Community | Our RE | Status |
|---------|-----------|--------|--------|
| Legacy remap table exists | 100+ remappings documented | Documented in doc 16 section 11/23 | MATCH |
| Example: `24003000 -> 03043000` | Confirmed | Confirmed | MATCH |
| Purpose: backward compatibility | Engine maps old class IDs to new | Same understanding | MATCH |

---

## 3. Physics - Community vs RE Comparison

### 3.1 Simulation Architecture

| Feature | Community (donadigo/TMInterface) | Our RE | Status |
|---------|----------------------------------|--------|--------|
| Tick rate | 100 Hz (100/s) | Confirmed via `PhysicsStep_TM` profiling | MATCH |
| Deterministic | Fully deterministic simulation | Confirmed (doc 10 section 10) | MATCH |
| Time unit internal | Microseconds (tick * 1000000) | Confirmed: `(ulonglong)*param_4 * 1000000` | MATCH |
| Physics step function | `CHmsZoneDynamic::PhysicsStep2` | `PhysicsStep_TM (FUN_141501800)` calling `NSceneDyna::PhysicsStep (FUN_1407bd0e0)` | **COMPLEMENTARY** |
| Adaptive sub-stepping | TMInterface exposes sub-step count | Confirmed: velocity-dependent sub-stepping in `PhysicsStep_TM` | MATCH |
| Per-vehicle loop | Confirmed by TMInterface per-vehicle callbacks | Confirmed: loop over vehicles in `PhysicsStep_TM` | MATCH |

**NOTE**: Community references `CHmsZoneDynamic::PhysicsStep2` as the buffer-invoked function (from TMNF RE). Our TM2020 RE traces the pipeline from `CSmArenaPhysics::Players_UpdateTimed` -> `PhysicsStep_TM` -> `NSceneDyna::PhysicsStep` -> `NSceneDyna::PhysicsStep_V2`. The community's `CHmsZoneDynamic::PhysicsStep2` likely corresponds to `NSceneDyna::PhysicsStep_V2` in our analysis (or wraps it). Both paths are consistent.

### 3.2 Input System

| Feature | Community (donadigo) | Our RE | Status |
|---------|---------------------|--------|--------|
| Steering range | -65536 to 65536 (analog) | InputSteer is -1.0 to 1.0 (float) in CSceneVehicleVisState | **DIFFERENT LAYERS** |
| Input pipeline | `CTrackManiaRace::InputRace` -> `CInputPort::GatherLatestInputs` -> DirectInput -> `CInputEventsStore` | CInput* classes (17 found), DirectInput confirmed in imports | MATCH (high-level) |
| Buffered vs immediate | 32-event buffer or immediate device state | Not deeply analyzed at this level | **GAP** |

**CLARIFICATION**: The community steering range (-65536 to 65536) is the raw integer input from the device/replay file. The float -1.0 to 1.0 seen in `CSceneVehicleVisState.InputSteer` is the normalized version used by the physics/vis system. Both are correct at their respective layers.

### 3.3 Vehicle State (CSceneVehicleVisState)

| Property | Community (Openplanet) | Our RE (doc 19/25) | Status |
|----------|----------------------|---------------------|--------|
| Position (vec3) | Confirmed | Confirmed | MATCH |
| WorldVel (vec3) | Confirmed | Confirmed | MATCH |
| Dir/Left/Up (vec3) | Confirmed | Confirmed | MATCH |
| FrontSpeed (float) | Confirmed | Confirmed (m/s, *3.6 for km/h) | MATCH |
| SideSpeed (float) | Via VehicleState custom offset | Confirmed via custom offset | MATCH |
| CurGear (uint, 0-7) | Confirmed | Confirmed | MATCH |
| RPM (float, 0-11000) | Via custom offset | Confirmed via custom offset | MATCH |
| EngineOn (bool) | Confirmed | Confirmed | MATCH |
| InputSteer (float) | Confirmed | Confirmed | MATCH |
| InputGasPedal (float) | Confirmed | Confirmed | MATCH |
| InputBrakePedal (float) | Confirmed | Confirmed | MATCH |
| IsGroundContact (bool) | Confirmed | Confirmed | MATCH |
| IsTurbo (bool) | Confirmed | Confirmed | MATCH |
| TurboTime (float) | Confirmed | Confirmed | MATCH |
| ReactorBoostLvl (enum) | None, Lvl1, Lvl2 | Confirmed | MATCH |
| ReactorBoostType (enum) | None, Up, Down, UpAndDown | Confirmed | MATCH |
| SimulationTimeCoef (float) | Confirmed | Confirmed | MATCH |
| Class ID | 0x0A00C000 | Not specifically verified | **FILLS GAP** |

**NEW FROM COMMUNITY**: The Openplanet API confirms the class ID for CSceneVehicleVisState as `0x0A00C000` (Engine 0x0A = Scene, Class 00C). This can be verified in our binary.

### 3.4 Per-Wheel Data

| Property | Community (Openplanet) | Our RE | Status |
|----------|----------------------|--------|--------|
| Wheel indexing | FL=0, FR=1, RR=2, RL=3 | Not verified at this level | **FILLS GAP** |
| SteerAngle (float) | Per wheel | Not individually mapped | **FILLS GAP** |
| WheelRot (float) | Per wheel rotation | Not individually mapped | **FILLS GAP** |
| WheelRotSpeed (float) | Per wheel rotation speed | Not individually mapped | **FILLS GAP** |
| DamperLen (float) | Suspension damper length | Not individually mapped | **FILLS GAP** |
| SlipCoef (float) | Tire slip coefficient | Not individually mapped | **FILLS GAP** |
| Icing01 (float) | Ice accumulation | Not individually mapped | **FILLS GAP** |
| TireWear01 (float) | Tire wear | Not individually mapped | **FILLS GAP** |
| BreakNormedCoef (float) | Brake coefficient | Not individually mapped | **FILLS GAP** |
| GroundContactMaterial (EPlugSurfaceMaterialId) | Per wheel | Not individually mapped | **FILLS GAP** |
| FallingState (enum) | FallingAir, FallingWater, RestingGround, RestingWater, GlidingGround | Not documented | **FILLS GAP** |

### 3.5 TMInterface Physics Details

TMInterface (TMNF/TMUF only, not TM2020) exposes:

| Feature | Detail | Our RE Relevance |
|---------|--------|-----------------|
| Save state size | ~10KB per state file | Gives estimate of physics state size |
| Save/restore | Complete race state including ghost | Confirms state is fully capturable |
| Bruteforce engine | Modifies N inputs in time windows, evaluates finish time/checkpoint/position | Confirms determinism is exploitable |
| AngelScript callbacks | `OnSimulationStep`, `OnBruteforceEvaluate`, `OnGameStateChanged` | Similar callback model to Openplanet |
| Extended steering | Values beyond standard -65536..65536 range | Suggests integer overflow in input handling |
| Analog input range | 0-65535 for acceleration, -65535..65535 for steering | Raw input integer range confirmed |

### 3.6 Game Mechanics (Community Knowledge)

| Mechanic | Community Detail | Our RE Status |
|----------|-----------------|--------------|
| Drift initiation speed | Minimum 191 km/h | Not verified in physics code | **GAP** |
| Gear shift speeds | 4th gear at 235 km/h, 5th at 342 km/h (normal); 4th at 222, 5th at 314 (drift) | Not verified | **GAP** |
| Surface detection | Left front wheel determines surface | Not verified | **GAP - INTERESTING** |
| Speed drift overlap | Skid mark overlap triggers acceleration boost | Not verified in physics model | **GAP** |

### 3.7 Surface Materials (PhysicsId)

From official Nadeo documentation (doc.trackmania.com), 24 PhysicsId values:

| PhysicsId | Category | In Our RE? |
|-----------|----------|------------|
| Asphalt | Standard | Not cataloged individually |
| Concrete | Standard | Not cataloged individually |
| Dirt | Standard | Not cataloged individually |
| Grass | Standard | Not cataloged individually |
| Green | Standard (synthetic grass) | Not cataloged individually |
| Ice | Standard | Not cataloged individually |
| Metal | Standard | Not cataloged individually |
| MetalTrans | Standard | Not cataloged individually |
| Pavement | Standard | Not cataloged individually |
| Plastic | Standard | Not cataloged individually |
| ResonantMetal | Standard | Not cataloged individually |
| RoadIce | Standard | Not cataloged individually |
| RoadSynthetic | Standard | Not cataloged individually |
| Rock | Standard | Not cataloged individually |
| Rubber | Standard | Not cataloged individually |
| Sand | Standard | Not cataloged individually |
| Snow | Standard | Not cataloged individually |
| Wood | Standard | Not cataloged individually |
| NotCollidable | Special | Not cataloged |
| TechMagnetic | Special (magnetic) | Not cataloged |
| TechMagneticAccel | Special (magnetic + accel) | Not cataloged |
| TechSuperMagnetic | Special (strong magnetic) | Not cataloged |

**Plus 16 GameplayId values**: Bumper, Bumper2, Cruise, ForceAcceleration, Fragile, FreeWheeling, NoBrakes, NoGrip, None, NoSteering, ReactorBoost, ReactorBoost2, Reset, SlowMotion, Turbo, Turbo2

These map to the `EPlugSurfaceMaterialId` enum exposed by Openplanet per wheel contact.

---

## 4. API Endpoints - Community vs RE Comparison

### 4.1 Authentication

| Detail | Community (Openplanet docs) | Our RE (doc 07/17) | Status |
|--------|---------------------------|---------------------|--------|
| Ubi-AppId | `86263886-327a-4328-ac69-527f0d20a237` | Not extracted from binary | **FILLS GAP** |
| Ubisoft auth URL | `https://public-ubiservices.ubi.com/v3/profiles/sessions` | UPC SDK integration confirmed | COMPLEMENTARY |
| Nadeo auth URL | `https://prod.trackmania.core.nadeo.online/v2/authentication/token/ubiservices` | `prod.trackmania.core.nadeo.online` confirmed in binary strings | MATCH |
| Token format | `nadeo_v1 t=<access_token>` | Not extracted | **FILLS GAP** |
| Token type | JWT (signed JSON Web Tokens) | Not analyzed | **FILLS GAP** |
| Token expiry | ~1 hour access, ~1 day refresh | Not analyzed | **FILLS GAP** |
| Refresh URL | `https://prod.trackmania.core.nadeo.online/v2/authentication/token/refresh` | Not extracted | **FILLS GAP** |

### 4.2 Service Base URLs

| Service | Community URL | Our RE Status |
|---------|--------------|---------------|
| Core API | `https://prod.trackmania.core.nadeo.online/` | Confirmed in binary strings (doc 07/17) |
| Live Services | `https://live-services.trackmania.nadeo.live/` | Confirmed in binary strings |
| Meet | `https://meet.trackmania.nadeo.club` | Not specifically found |
| Club Services | `https://club.trackmania.nadeo.club` | Not specifically found |
| Competition | `https://competition.trackmania.nadeo.club` | Not specifically found |
| Matchmaking | `https://matchmaking.trackmania.nadeo.club` | Not specifically found |

### 4.3 Audience Values

| Audience | Services | Our RE |
|----------|----------|--------|
| NadeoServices | Core API | Not extracted from binary |
| NadeoLiveServices | Live API, Meet API | Not extracted from binary |
| NadeoClubServices | Club, Competition, Matchmaking | Not extracted from binary |

### 4.4 JWT Token Payload Fields

Community documents these JWT payload fields:
- `aud`: Audience identifier
- `exp`: Expiration timestamp
- `sub`: Nadeo account ID
- `rtk`: Boolean (true for refresh tokens)
- `refresh_aud`: Audience for refreshed tokens
- `usg`: Usage type ("Client" or "Server")

These are **not documented in our RE** -- they are protocol-level details visible to anyone who decodes the JWT.

### 4.5 Core API Endpoints (Community-Documented)

**Accounts**: club-tags, display-names, trophy-history, trophy-summary, webidentities, zones
**Maps**: authored, info (single/multiple by ID/UID), vote, submitted
**Records**: account-records-v2, map-records-v2 (by ID and account), record-by-id
**Meta**: routes, zones
**Skins**: equipped, favorites, info

### 4.6 Live API Endpoints (Community-Documented)

**Campaigns**: TOTDs, map-info, seasonal campaigns (v1/v2), weekly grands/shorts
**Clubs**: member, activities, campaigns, competitions, rooms, uploads
**Leaderboards**: top, medals, player records, trophies, position, surround
**Maps**: favorites, info, uploaded
**Map Review**: connect, submitted, waiting-time

### 4.7 Meet API Endpoints (Community-Documented)

**Challenges**: info, leaderboard, map records
**Competitions**: info, leaderboard, participants, rounds, teams, COTD, cups
**Matches**: info, participants, teams
**Matchmaking**: queue, IDs, divisions, rankings, progressions, ranks, status, heartbeat

### 4.8 Dedicated Server XML-RPC

| Feature | Community | Our RE |
|---------|-----------|--------|
| GBX Remote protocol | Documented at wiki.trackmania.io | CXmlRpc classes confirmed in binary |
| Scripted callbacks | `Trackmania.Event.*` namespace | Not analyzed at callback level |
| Method reference | Full list at wiki.trackmania.io | Not analyzed |

### 4.9 ManiaExchange API v2

Base URL: `https://api2.mania.exchange/`

Key capabilities:
- Map search and metadata
- Map info by UID (single and batch)
- Mappack management
- Player awards
- Track search
- Requires User-Agent header
- JSON-only responses
- UTC timestamps

---

## 5. ManiaScript - Community Documentation

### 5.1 ManiaScript Reference Sources

Three independently maintained references exist:
1. **BigBang1112/maniascript-reference**: Auto-generated via Doxygen from game header files. Covers TM2020 (2026.2.2.1751), ManiaPlanet, and Turbo.
2. **boss-bravo.fr**: Alternative reference for TM2020 ManiaScript classes.
3. **maniaplanet-community.gitbook.io**: Narrative documentation and tutorials.

### 5.2 Key ManiaScript Classes (TM2020)

From the Doxygen reference, key classes for understanding game internals:

| Class | Relevance | Our RE Equivalent |
|-------|-----------|-------------------|
| CSmMode | Game mode script entry point | CSmArena* classes |
| CSmPlayer | Player state in ManiaScript | CSmArenaPhysics player management |
| CSmPlayerDriver | Bot AI controller (detailed in section 3) | Not deeply analyzed |
| CGameCtnApp | Main application object | CGameCtnApp (confirmed in binary) |
| CMapBotPath | Bot pathfinding | Not analyzed |

### 5.3 CSmPlayerDriver Details (Bot AI)

The community ManiaScript reference reveals the bot AI system with:

**Behaviors**: Static, Turret, Scripted, IA, Patrol, Escape, Saunter, Orbit, Follow
**Path states**: Static, None, Computing, Simple, Full, Incomplete, InFlock
**Attack filters**: All, AllPlayers, AllBots, AllOpposite, OppositePlayers, OppositeBots, Nobody

**Flocking system**: cohesion, alignment, separation weights + radius + FOV -- this is a full boids implementation.

This is ShootMania-focused but the class hierarchy is shared with TM2020.

### 5.4 Openplanet Engine Namespaces

The Openplanet documentation exposes 20 engine namespaces for TM2020:

| Namespace | Purpose | Engines in Our RE |
|-----------|---------|-------------------|
| MwFoundations | Core classes | CMw* (17 classes) |
| Game | Game systems | CGame* (728 classes) |
| Graphic | Rendering | Not explicitly mapped |
| Function | Utilities | Not explicitly mapped |
| Hms | HMS renderer | CHms* (41 classes) |
| Control | UI | CControl* (39 classes) |
| Plug | Resources | CPlug* (391 classes) |
| Scene | Scene graph | CScene* (52 classes) |
| System | Platform | CSystem* (24 classes) |
| Vision | Camera/viewport | CVision* (9 classes) |
| Audio | Sound | CAudio* (19 classes) |
| Script | Scripting | CScript* (9 classes) |
| Net | Networking | CNet* (262 classes) |
| Input | Input devices | CInput* (17 classes) |
| Xml | XML/JSON | CXml* (10 classes) |
| TrackMania | TM-specific | CTrackMania* (4 classes) |
| ShootMania | SM-specific | CSm* (11 classes) |
| GameData | Game data | CWebServices* + CGameData* |
| Meta | Metadata | Not mapped |
| MetaNotPersistent | Volatile metadata | Not mapped |

### 5.5 Openplanet Global API

Key functions exposed to plugins:

| Function | Significance |
|----------|-------------|
| `GetApp()` -> `CGameCtnApp@` | Main game application access |
| `GetCmdBufferCore()` -> `CMwCmdBufferCore@` | Command buffer scheduling |
| `GetSystemConfig()` -> `CSystemConfig@` | System configuration |
| `ExploreNod()` | Nod inspector (reveals live object tree) |
| `RegisterLoadCallback(uint id)` | Hook nod loading by class ID |
| `CMwStack` | Stack for calling engine procs (late binding) |

### 5.6 NadeoServices Plugin API

| Function | Purpose |
|----------|---------|
| `AddAudience(string)` | Register API audience |
| `IsAuthenticated(string)` | Check auth status |
| `GetAccountID()` | Get current user's account ID |
| `BaseURLCore()` | Core API base URL |
| `BaseURLLive()` | Live API base URL |
| `BaseURLMeet()` | Meet API base URL |
| `Get/Post/Put/Delete/Patch(audience, url, ...)` | HTTP methods |
| `GetDisplayNameAsync(accountId)` | Resolve player names |
| `LoginToAccountId(login)` / `AccountIdToLogin(id)` | Format conversion |

---

## 6. New Information from Community Sources

### 6.1 ManiaPlanet Engine Architecture (from Mania Tech Wiki)

The community provides details about the engine internals that supplement our RE:

**CMwEngineManager**: Singleton that manages all 37+ engines. Contains `CMwEngineInfo[]` (namespaces) -> `CMwClassInfo[]` (type descriptors) -> `CMwMemberInfo[]` (properties/methods).

**Reference Counting**: Objects use `MwAddRef()`/`MwRelease()`. Zero-count triggers destruction. Optional `pDependants` child list.

**CMwStack Late Binding**: Not a LIFO stack -- it is a QUEUE. First two items stored inline (`m_ContainedItems`), rest on heap. Supports types: ITEM_MEMBER, ITEM_BOOL, ITEM_OBJECT, ITEM_ENUM, ITEM_ISO4, ITEM_VEC2, ITEM_VEC3, ITEM_INT3, ITEM_UINT3, ITEM_INT, ITEM_UINT, ITEM_FLOAT, ITEM_STRING, ITEM_WSTRING.

**Three operations**: Get property, set property, call method. Each requires CMwStack configured with member info and parameters.

**Serialization Pipeline**: `CSystemArchiveNod` handles .gbx file serialization. The loading path is: `LoadFileFrom -> DoLoadFile -> DoFidLoadFile -> DoLoadAll -> { DoLoadHeader -> DoLoadRef -> DoLoadBody }`.

**File System Drives**:
- Resource (Resource.pak)
- Personal (user folder)
- ManiaPlanet (game installation)
- Common (shared cache)
- Temp

**Stream Architecture**: `CClassicBuffer` base class with implementations:
- `CSystemFile` (4 KB buffered reading)
- `CSystemFileMemMapped` (memory-mapped files)
- `CClassicBufferZlib` (compression)
- `CClassicBufferCrypted` (encryption with Blowfish CBC/CTR)

### 6.2 Ghost/Replay Sample Data Encoding

The community documents the ghost sample data encoding:

| Field | Type | Encoding |
|-------|------|----------|
| Position | vec3 | 3x float32 |
| Angle | uint16 | 0..0xFFFF maps to 0..pi |
| AxisHeading | int16 | -0x8000..0x7FFF maps to -pi..pi |
| AxisPitch | int16 | -0x8000..0x7FFF maps to -pi/2..pi/2 |
| Speed | int16 | `exp(speed/1000)`, where 0x8000 means 0 |
| VelocityHeading | int8 | -0x80..0x7F maps to -pi..pi |
| VelocityPitch | int8 | -0x80..0x7F maps to -pi/2..pi/2 |

**Sample period**: 50ms (20 samples/second)
**Compression**: zlib deflate for sample data

This is NEW information not in our RE docs. The exact encoding of rotation angles and speed into integer types with specific range mappings is valuable for replay analysis.

### 6.3 TrackMania Engine Class IDs (from Openplanet)

New class IDs confirmed through Openplanet:

| Class | ID | Engine |
|-------|-----|--------|
| CTrackMania | 0x24001000 | TrackMania |
| CTrackManiaMenus | 0x2402E000 | TrackMania |
| CTrackManiaNetwork | 0x2402F000 | TrackMania |
| CTrackManiaNetworkServerInfo | 0x24035000 | TrackMania |
| CTrackManiaPlayerInfo | 0x24036000 | TrackMania |
| CTrackManiaMatchSettings | 0x24041000 | TrackMania |
| CTrackManiaControlCheckPointList | 0x2406E000 | TrackMania |
| CTrackManiaControlPlayerInfoCard | 0x2408C000 | TrackMania |
| CTrackManiaControlCard | 0x2408F000 | TrackMania |
| CTrackManiaControlMatchSettingsCard | 0x240C4000 | TrackMania |
| CGamePlayerProfileChunk_TrackManiaSettings | 0x240D5000 | TrackMania |
| CSceneVehicleVisState | 0x0A00C000 | Scene |

### 6.4 Vehicle Types Enum

| Value | Name | Description |
|-------|------|-------------|
| 0 | CharacterPilot | On-foot character |
| 1 | CarSport | Stadium car (default) |
| 2 | CarSnow | Snow car |
| 3 | CarRally | Rally car |
| 4 | CarDesert | Desert car |

### 6.5 Block Coordinate System

From community: block coordinates use (X, Y, Z) integers, rotation is 0-3 (90-degree increments). In GBX format version >= 6, coordinates are offset-adjusted by subtracting (1, 0, 1) from the stored values. Blocks with flags == 0xFFFFFFFF are "null" blocks and should be skipped.

### 6.6 Blowfish Encryption

The community documents `CClassicBufferCrypted` using Blowfish in CBC and CTR modes. This supplements our knowledge of the stream architecture and may be relevant for understanding encrypted game data.

---

## 7. Contradictions to Investigate

### 7.1 Format Flag Byte Ordering

**Community (Mania Tech Wiki)**: Lists format bytes as:
- Byte 5: Format type ('B'/'T')
- Byte 6: Reference table compression ('U'/'C') -- "unused"
- Byte 7: Body compression ('U'/'C')
- Byte 8: Edit state ('R'/'E')

**Our RE**: Lists 4-character format descriptor at offset 0x05:
- Byte 0: Format type ('B'/'T')
- Byte 1: Body compression -> stored at `+0xD8`
- Byte 2: [UNKNOWN] compression -> stored at `+0xDC`
- Byte 3: Reference mode ('R'/'E')

**Issue**: The community says byte 6 (ref table compression) is "unused", but our RE shows bytes 1 and 2 both control compression. The actual semantics of bytes 1 vs 2 need clarification. Common format strings `"BUCR"` and `"BUCE"` suggest the 4 characters form a single descriptor where the meaning of each position should be verified against multiple files.

**Action**: Parse several real .Map.Gbx files and check the actual byte values at positions 5-8 to determine which controls body compression vs reference table compression.

### 7.2 CHmsZoneDynamic vs NSceneDyna

**Community**: References `CHmsZoneDynamic::PhysicsStep2` as the main physics driver (from TMNF era).

**Our RE**: Traces to `NSceneDyna::PhysicsStep` -> `NSceneDyna::PhysicsStep_V2` -> `NSceneDyna::InternalPhysicsStep`.

**Assessment**: Not a true contradiction. In TM2020, the `NSceneDyna` namespace likely absorbed or replaced what was `CHmsZoneDynamic` in TMNF. The HMS (Hierarchical Managed Scene) layer still exists in TM2020 (41 CHms* classes found) but the physics simulation appears to have been refactored into the Scene engine (NSceneDyna = Engine 0x0A). The community knowledge is based on older TMNF reverse engineering.

### 7.3 Steering Range

**Community (donadigo/TMInterface)**: Steering range is -65536 to 65536 (integer).

**Our RE / Openplanet**: `InputSteer` is a float from -1.0 to 1.0.

**Assessment**: Not a contradiction. The integer range is the raw replay/input file encoding. The float range is the normalized physics/vis value. The conversion is: `float_steer = int_steer / 65536.0`. Both are correct at their respective layers.

---

## 8. Gap-Filling Opportunities

### 8.1 High-Priority Gaps Our RE Can Fill from Community

| Gap | Community Source | Action |
|-----|-----------------|--------|
| Encapsulated chunk IDs | Mania Tech Wiki lists 8 specific IDs | Verify these IDs reset lookbackstring context in our parser |
| Ghost sample encoding | Community documents exact int16/int8 encoding for position/rotation/speed | Add to doc 16 section 17 |
| CSceneVehicleVisState class ID (0x0A00C000) | Openplanet | Verify in binary class registry |
| Per-wheel property names and offsets | Openplanet VehicleState | Map to our decompiled wheel struct |
| FallingState and TurboLevel enums | Openplanet | Add to our enum catalog |
| Vehicle type enum values | Openplanet VehicleState | Verify against binary |
| Block coordinate offset (subtract 1,0,1 for v6+) | GBX.NET source | Verify in our map parsing code |
| Blocks with flags 0xFFFFFFFF are null | GBX.NET source | Verify in our parser |
| Ubi-AppId value | Community API docs | Verify in binary strings |
| JWT token payload fields | Community API docs | Protocol-level, no RE needed |

### 8.2 High-Priority Gaps Community Knowledge Fills

| Gap | Detail | Impact |
|-----|--------|--------|
| **Complete API endpoint catalog** | 80+ endpoints across Core/Live/Meet APIs | Enables comprehensive network traffic analysis |
| **All 24 PhysicsId values** | Complete surface material list with gameplay effects | Maps to `EPlugSurfaceMaterialId` enum in physics |
| **All 16 GameplayId values** | Turbo, reactor, cruise, etc. | Maps to surface effect triggers |
| **ManiaExchange API v2** | Complete external track exchange API | Understanding map download flows |
| **XML-RPC callback system** | Full dedicated server scripting API | Understanding server-client protocol |
| **Ghost sample encoding** | Precise integer-to-float mappings for replay data | Critical for replay file parsing |
| **ManiaScript class hierarchy** | Complete script API surface | Understanding what is exposed to modders |

### 8.3 What Community Does NOT Cover (Our RE Unique Value)

| Topic | Our Unique RE Contribution |
|-------|--------------------------|
| Decompiled physics functions | 18+ decompiled functions with actual C pseudocode |
| Adaptive sub-stepping algorithm | Velocity-dependent step count with exact thresholds |
| Force computation pipeline | 7 force models (engine, braking, steering, suspension, turbo, reactor, gravity) |
| Memory layout offsets | Exact struct offsets from decompiled code (e.g., vehicle state nibble at +0x128c) |
| Anti-tamper/packing | Entry point obfuscation in .D." section |
| OpenSSL+QUIC integration | `OpenSSL 1.1.1t+quic` confirmed in binary |
| 2,027 class count | Complete class registry from binary RTTI extraction |
| Collision subsystem | NHmsCollision broadphase, contact merging, continuous collision |
| Water physics model | Buoyancy, immersion, surface effects |
| Specific function addresses | Every FUN_ address mapped to subsystem and purpose |

### 8.4 Recommended Next Steps

1. **Verify community class IDs** against our binary's class registry (especially CSceneVehicleVisState = 0x0A00C000).
2. **Map the 24 PhysicsId values** to our decompiled surface effect code.
3. **Integrate ghost sample encoding** into our file format documentation.
4. **Cross-reference GBX.NET chunk implementations** with our decompiled chunk readers for CGameCtnChallenge.
5. **Extract the Ubi-AppId** from binary strings to confirm it matches `86263886-327a-4328-ac69-527f0d20a237`.
6. **Investigate the format flag byte semantics** (section 7.1) by parsing real files.
7. **Map VehicleState per-wheel offsets** to our decompiled wheel struct layout.
8. **Import the complete engine ID table** (37 engines) into our class hierarchy documentation.

---

## Sources

- [GBX.NET GitHub](https://github.com/BigBang1112/gbx-net)
- [GBX.NET Explorer](https://explorer.gbx.tools/)
- [Mania Tech Wiki - GBX](https://wiki.xaseco.org/wiki/GBX)
- [Mania Tech Wiki - Class IDs](https://wiki.xaseco.org/wiki/Class_IDs)
- [Mania Tech Wiki - ManiaPlanet Internals](https://wiki.xaseco.org/wiki/ManiaPlanet_internals)
- [Openplanet](https://openplanet.dev/)
- [Openplanet Documentation](https://openplanet.dev/docs)
- [Openplanet Trackmania Next API](https://next.openplanet.dev/)
- [VehicleState Plugin Reference](https://openplanet.dev/docs/reference/vehiclestate)
- [VehicleState Source](https://github.com/openplanet-nl/vehiclestate)
- [CSceneVehicleVisState Reference](https://next.openplanet.dev/Scene/CSceneVehicleVisState)
- [Trackmania Web Services API](https://webservices.openplanet.dev/)
- [Web Services Authentication](https://webservices.openplanet.dev/auth)
- [codecat's Web Services Gist](https://gist.github.com/codecat/4dfd3719e1f8d9e5ef439d639abe0de4)
- [ManiaExchange API](https://api2.mania.exchange/)
- [TMInterface](https://donadigo.com/tminterface/)
- [TMX Replay Investigation](https://donadigo.com/tmx1)
- [pygbx](https://github.com/donadigo/pygbx)
- [gbxtools](https://github.com/donadigo/gbxtools)
- [ManiaScript Reference (BigBang1112)](https://github.com/BigBang1112/maniascript-reference)
- [ManiaScript Reference (boss-bravo)](https://maniascript.boss-bravo.fr/)
- [ManiaScript Documentation](https://maniaplanet-community.gitbook.io/maniascript)
- [XML-RPC Documentation](https://wiki.trackmania.io/en/dedicated-server/XML-RPC/home)
- [Official Trackmania Documentation](https://doc.trackmania.com/)
- [MeshParams Documentation](https://doc.trackmania.com/create/nadeo-importer/04-how-to-create-the-meshparams-xml-file/)
- [Trackmania Wiki - Game Mechanics](https://www.trackmania.wiki/wiki/Game_Mechanics)
- [tmrl (Reinforcement Learning)](https://github.com/trackmania-rl/tmrl)

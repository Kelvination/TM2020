# Community Knowledge Cross-Reference

Community reverse engineering projects provide complementary data to our Ghidra-based analysis. This document catalogs those projects, compares findings, and identifies gaps each side fills.

Use this as a lookup when you need a community tool, want to validate an RE finding, or need to fill a knowledge gap.

---

## Community Projects Catalog

### GBX Parsing Libraries

| Project | Language | URL | Status | Scope |
|---------|----------|-----|--------|-------|
| **GBX.NET** | C#/.NET | https://github.com/BigBang1112/gbx-net | Active (Jan 2026 update) | 400+ GBX classes, full read/write |
| **pygbx** | Python | https://github.com/donadigo/pygbx | Maintained (v0.3.1) | Read-only GBX parser |
| **gbx-ts** | TypeScript | https://github.com/thaumictom/gbx-ts | Active | TypeScript GBX parser |
| **GbxDump** | C/C++ | https://github.com/Electron-x/GbxDump | Maintained | Windows header viewer |
| **gbxutils** | Various | https://github.com/realh/gbxutils | Active | Utilities for map GBX files |

### GBX Analysis Tools

| Tool | URL | Purpose |
|------|-----|---------|
| **GBX.NET Explorer** | https://explorer.gbx.tools/ | Client-side GBX inspection and modification |
| **gbxtools** (donadigo) | https://github.com/donadigo/gbxtools | Python scripts for replay analysis |
| **GbxMapBrowser** | https://github.com/ArkadySK/GbxMapBrowser | Visual map/replay browser using GBX.NET |
| **clip-input** | https://github.com/bigbang1112-cz/clip-input | Convert replay input data to Clip.Gbx overlays |

### Physics / TAS Tools

| Tool | URL | Purpose |
|------|-----|---------|
| **TMInterface** | https://donadigo.com/tminterface/ | TAS tool for TMNF/TMUF: DLL injection, physics access, bruteforce |
| **tmrl** | https://github.com/trackmania-rl/tmrl | Reinforcement learning framework with TM2020 Gymnasium env |
| **TMTrackNN** | https://github.com/donadigo/TMTrackNN | Neural network track generation |

### Openplanet Ecosystem

| Resource | URL | Purpose |
|----------|-----|---------|
| **Openplanet** | https://openplanet.dev/ | Modding platform for TM2020, uses AngelScript |
| **Openplanet Docs** | https://openplanet.dev/docs | Plugin development documentation |
| **Trackmania Next API** | https://next.openplanet.dev/ | Game engine class browser |
| **VehicleState Plugin** | https://openplanet.dev/docs/reference/vehiclestate | Vehicle physics data access dependency |
| **VehicleState Source** | https://github.com/openplanet-nl/vehiclestate | Source code for VehicleState dependency |

### API Documentation

| Resource | URL | Purpose |
|----------|-----|---------|
| **Nadeo API Docs** (Openplanet) | https://webservices.openplanet.dev/ | Unofficial but authoritative API docs |
| **ManiaExchange API** | https://api2.mania.exchange/ | TMX track exchange API (v2) |
| **codecat's Web Services Gist** | https://gist.github.com/codecat/4dfd3719e1f8d9e5ef439d639abe0de4 | Original community API documentation |
| **XML-RPC Docs** | https://wiki.trackmania.io/en/dedicated-server/XML-RPC/home | Dedicated server XML-RPC reference |

### Wikis and References

| Resource | URL | Scope |
|----------|-----|-------|
| **Mania Tech Wiki** | https://wiki.xaseco.org/wiki/GBX | GBX format internals, class IDs |
| **Mania Tech Wiki - Class IDs** | https://wiki.xaseco.org/wiki/Class_IDs | Complete engine/class/chunk ID registry |
| **Mania Tech Wiki - Internals** | https://wiki.xaseco.org/wiki/ManiaPlanet_internals | Engine architecture docs |
| **Trackmania Wiki** | https://www.trackmania.wiki/wiki/ | Community wiki (format, mechanics) |
| **ManiaPlanet Fandom Wiki** | https://maniaplanet.fandom.com/wiki/GBX | GBX format reference |
| **Official TM Docs** | https://doc.trackmania.com/ | Nadeo's official documentation |

### ManiaScript References

| Resource | URL | Scope |
|----------|-----|-------|
| **ManiaScript Reference** (BigBang1112) | https://github.com/BigBang1112/maniascript-reference | Auto-generated Doxygen docs for TM2020/MP/Turbo |
| **ManiaScript Reference** (boss-bravo) | https://maniascript.boss-bravo.fr/ | TM2020 ManiaScript class reference |
| **ManiaScript Book** | https://maniaplanet-community.gitbook.io/maniascript | Community documentation guide |
| **Official Script-XMLRPC** | https://github.com/maniaplanet/script-xmlrpc | Official XmlRpc callback definitions |

---

## GBX Format -- Community vs RE Comparison

### Header Structure

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

**CONTRADICTION**: The Mania Tech Wiki says byte 6 (reference table compression) is "unused." Our RE shows it controls body stream decompression. The byte ordering may differ due to different counting conventions. This needs further investigation.

### Chunk System

| Feature | Community | Our RE | Status |
|---------|-----------|--------|--------|
| Chunk ID format (32-bit) | Engine byte + class byte + chunk byte | `0x03043007` = Engine 03, Class 043, Chunk 007 | MATCH |
| End sentinel | `0xFACADE01` | `0xFACADE01` (confirmed in chunk dispatch) | MATCH |
| Skippable flag | `0x10` flag, preceded by "SKIP" marker + size | Skippable chunks include length prefix | MATCH |
| Encapsulated chunks | Reset lookbackstring list locally | Referenced in our format docs | MATCH |
| Encapsulated chunk IDs | `03043040, 03043041, 03043043, 03043044, 0304304E, 0304304F, 03043054, 03043058` | Not exhaustively listed in our RE | **GAP** |

### Engine IDs

The Mania Tech Wiki documents **37 engine IDs**. Many legacy/game-specific engines (VirtualSkipper, Lanfeust, Sorcieres) are absent from TM2020 as expected. Our binary contains 2,027 Nadeo classes across the active engines. The engine ID scheme is CONFIRMED.

| ID | Engine Name | In Our RE? |
|----|-------------|------------|
| 0x01 | ENGINE_MWFOUNDATIONS | Yes (CMw* classes) |
| 0x03 | ENGINE_GAME | Yes (CGame* classes, 728 found) |
| 0x06 | ENGINE_HMS | Yes (CHms* classes, 41 found) |
| 0x07 | ENGINE_CONTROL | Yes (CControl* classes, 39 found) |
| 0x09 | ENGINE_PLUG | Yes (CPlug* classes, 391 found) |
| 0x0A | ENGINE_SCENE | Yes (CScene* classes, 52 found) |
| 0x0B | ENGINE_SYSTEM | Yes (CSystem* classes, 24 found) |
| 0x0C | ENGINE_VISION | Yes (CVision* classes, 9 found) |
| 0x10 | ENGINE_AUDIO | Yes (CAudio* classes, 19 found) |
| 0x11 | ENGINE_SCRIPT | Yes (CScript* classes, 9 found) |
| 0x12 | ENGINE_NET | Yes (CNet* classes, 262 found) |
| 0x13 | ENGINE_INPUT | Yes (CInput* classes, 17 found) |
| 0x14 | ENGINE_XML | Yes (CXml* classes, 10 found) |
| 0x24 | ENGINE_TRACKMANIA | Yes (CTrackMania* classes, 4 found) |
| 0x2D | ENGINE_SHOOTMANIA | Yes (CSm* classes, 11 found) |
| 0x2E | ENGINE_GAMEDATA | Yes (CWebServices* 297 + CGameData*) |

### CGameCtnChallenge (Map) Chunks

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

### Compression

| Feature | Community | Our RE | Status |
|---------|-----------|--------|--------|
| LZO body compression | Confirmed | LZO via `FUN_140127aa0` | MATCH |
| Zlib for lightmap/ghost data | Confirmed | Zlib confirmed for internal compressed data | MATCH |

---

## Physics -- Community vs RE Comparison

### Simulation Architecture

| Feature | Community (donadigo/TMInterface) | Our RE | Status |
|---------|----------------------------------|--------|--------|
| Tick rate | 100 Hz (100/s) | Confirmed via `PhysicsStep_TM` profiling | MATCH |
| Deterministic | Fully deterministic simulation | Confirmed (doc 10 section 10) | MATCH |
| Time unit internal | Microseconds (tick * 1000000) | Confirmed: `(ulonglong)*param_4 * 1000000` | MATCH |
| Physics step function | `CHmsZoneDynamic::PhysicsStep2` | `PhysicsStep_TM (FUN_141501800)` calling `NSceneDyna::PhysicsStep (FUN_1407bd0e0)` | **COMPLEMENTARY** |
| Adaptive sub-stepping | TMInterface exposes sub-step count | Confirmed: velocity-dependent sub-stepping in `PhysicsStep_TM` | MATCH |

Community references `CHmsZoneDynamic::PhysicsStep2` from TMNF RE. Our TM2020 RE traces through `CSmArenaPhysics::Players_UpdateTimed` -> `PhysicsStep_TM` -> `NSceneDyna::PhysicsStep_V2`. The community name likely corresponds to `NSceneDyna::PhysicsStep_V2` in our analysis. Both paths are consistent.

### Input System

| Feature | Community (donadigo) | Our RE | Status |
|---------|---------------------|--------|--------|
| Steering range | -65536 to 65536 (analog) | InputSteer is -1.0 to 1.0 (float) in CSceneVehicleVisState | **DIFFERENT LAYERS** |

The integer range is the raw replay/input file encoding. The float range is the normalized physics/vis value. Conversion: `float_steer = int_steer / 65536.0`. Both are correct at their respective layers.

### Vehicle State (CSceneVehicleVisState)

All major vehicle state properties match between Openplanet and our RE: Position, WorldVel, Dir/Left/Up, FrontSpeed, SideSpeed, CurGear, RPM, EngineOn, InputSteer, InputGasPedal, InputBrakePedal, IsGroundContact, IsTurbo, TurboTime, ReactorBoostLvl, ReactorBoostType, SimulationTimeCoef.

The Openplanet API confirms the class ID as `0x0A00C000` (Engine 0x0A = Scene, Class 00C).

### Per-Wheel Data (from Openplanet)

These properties fill gaps in our RE:

| Property | Source | Status |
|----------|--------|--------|
| Wheel indexing FL=0, FR=1, RR=2, RL=3 | Openplanet | **FILLS GAP** |
| SteerAngle, WheelRot, WheelRotSpeed (float, per wheel) | Openplanet | **FILLS GAP** |
| DamperLen, SlipCoef, Icing01, TireWear01 (float, per wheel) | Openplanet | **FILLS GAP** |
| GroundContactMaterial (EPlugSurfaceMaterialId, per wheel) | Openplanet | **FILLS GAP** |
| FallingState enum (FallingAir, FallingWater, RestingGround, RestingWater, GlidingGround) | Openplanet | **FILLS GAP** |

### Game Mechanics (Community Knowledge)

| Mechanic | Community Detail | Our RE Status |
|----------|-----------------|--------------|
| Drift initiation speed | Minimum 191 km/h | Not verified in physics code |
| Gear shift speeds | 4th gear at 235 km/h, 5th at 342 km/h (normal); 4th at 222, 5th at 314 (drift) | Not verified |
| Surface detection | Left front wheel determines surface | Not verified |

### Surface Materials (PhysicsId)

From official Nadeo documentation, 24 PhysicsId values exist: Asphalt, Concrete, Dirt, Grass, Green, Ice, Metal, MetalTrans, Pavement, Plastic, ResonantMetal, RoadIce, RoadSynthetic, Rock, Rubber, Sand, Snow, Wood, NotCollidable, TechMagnetic, TechMagneticAccel, TechSuperMagnetic.

Plus 16 GameplayId values: Bumper, Bumper2, Cruise, ForceAcceleration, Fragile, FreeWheeling, NoBrakes, NoGrip, None, NoSteering, ReactorBoost, ReactorBoost2, Reset, SlowMotion, Turbo, Turbo2.

These map to the `EPlugSurfaceMaterialId` enum exposed by Openplanet per wheel contact.

---

## API Endpoints -- Community vs RE Comparison

### Authentication

| Detail | Community (Openplanet docs) | Our RE (doc 07/17) | Status |
|--------|---------------------------|---------------------|--------|
| Ubi-AppId | `86263886-327a-4328-ac69-527f0d20a237` | Not extracted from binary | **FILLS GAP** |
| Ubisoft auth URL | `https://public-ubiservices.ubi.com/v3/profiles/sessions` | UPC SDK integration confirmed | COMPLEMENTARY |
| Nadeo auth URL | `https://prod.trackmania.core.nadeo.online/v2/authentication/token/ubiservices` | `prod.trackmania.core.nadeo.online` confirmed in binary strings | MATCH |
| Token format | `nadeo_v1 t=<access_token>` | Not extracted | **FILLS GAP** |
| Token type | JWT (signed JSON Web Tokens) | Not analyzed | **FILLS GAP** |
| Token expiry | ~1 hour access, ~1 day refresh | Not analyzed | **FILLS GAP** |

### Service Base URLs

| Service | Community URL | Our RE Status |
|---------|--------------|---------------|
| Core API | `https://prod.trackmania.core.nadeo.online/` | Confirmed in binary strings |
| Live Services | `https://live-services.trackmania.nadeo.live/` | Confirmed in binary strings |
| Meet | `https://meet.trackmania.nadeo.club` | Not specifically found |
| Club Services | `https://club.trackmania.nadeo.club` | Not specifically found |

### Audience Values

| Audience | Services |
|----------|----------|
| NadeoServices | Core API |
| NadeoLiveServices | Live API, Meet API |
| NadeoClubServices | Club, Competition, Matchmaking |

### Core API Endpoints

**Accounts**: club-tags, display-names, trophy-history, trophy-summary, webidentities, zones.
**Maps**: authored, info (single/multiple by ID/UID), vote, submitted.
**Records**: account-records-v2, map-records-v2, record-by-id.
**Meta**: routes, zones.
**Skins**: equipped, favorites, info.

### Live API Endpoints

**Campaigns**: TOTDs, map-info, seasonal campaigns, weekly grands/shorts.
**Clubs**: member, activities, campaigns, competitions, rooms, uploads.
**Leaderboards**: top, medals, player records, trophies, position, surround.
**Maps**: favorites, info, uploaded.

### Meet API Endpoints

**Challenges**: info, leaderboard, map records.
**Competitions**: info, leaderboard, participants, rounds, teams, COTD, cups.
**Matches**: info, participants, teams.
**Matchmaking**: queue, IDs, divisions, rankings, progressions, ranks, status, heartbeat.

---

## ManiaScript -- Community Documentation

### Key Sources

Three independently maintained references exist:
1. **BigBang1112/maniascript-reference**: Auto-generated via Doxygen from game header files. Covers TM2020 (2026.2.2.1751), ManiaPlanet, and Turbo.
2. **boss-bravo.fr**: Alternative reference for TM2020 ManiaScript classes.
3. **maniaplanet-community.gitbook.io**: Narrative documentation and tutorials.

### Key Openplanet Global API Functions

| Function | Significance |
|----------|-------------|
| `GetApp()` -> `CGameCtnApp@` | Main game application access |
| `GetCmdBufferCore()` -> `CMwCmdBufferCore@` | Command buffer scheduling |
| `GetSystemConfig()` -> `CSystemConfig@` | System configuration |
| `ExploreNod()` | Nod inspector (reveals live object tree) |
| `RegisterLoadCallback(uint id)` | Hook nod loading by class ID |
| `CMwStack` | Stack for calling engine procs (late binding) |

### NadeoServices Plugin API

| Function | Purpose |
|----------|---------|
| `AddAudience(string)` | Register API audience |
| `IsAuthenticated(string)` | Check auth status |
| `GetAccountID()` | Get current user's account ID |
| `BaseURLCore()` / `BaseURLLive()` / `BaseURLMeet()` | API base URLs |
| `Get/Post/Put/Delete/Patch(audience, url, ...)` | HTTP methods |
| `LoginToAccountId(login)` / `AccountIdToLogin(id)` | Format conversion |

---

## New Information from Community Sources

### ManiaPlanet Engine Architecture (from Mania Tech Wiki)

**CMwEngineManager** is a singleton managing all 37+ engines. It contains `CMwEngineInfo[]` (namespaces) -> `CMwClassInfo[]` (type descriptors) -> `CMwMemberInfo[]` (properties/methods).

**Reference Counting** uses `MwAddRef()`/`MwRelease()`. Zero-count triggers destruction.

**CMwStack Late Binding** is a QUEUE, not a LIFO stack. First two items stored inline, rest on heap. Supports 14 item types including ITEM_MEMBER, ITEM_OBJECT, ITEM_ISO4, ITEM_VEC3.

**Serialization Pipeline**: `CSystemArchiveNod` handles .gbx file serialization: `LoadFileFrom -> DoLoadFile -> DoFidLoadFile -> DoLoadAll -> { DoLoadHeader -> DoLoadRef -> DoLoadBody }`.

**Stream Architecture**: `CClassicBuffer` base class with `CSystemFile` (4 KB buffered), `CSystemFileMemMapped`, `CClassicBufferZlib` (compression), `CClassicBufferCrypted` (Blowfish CBC/CTR encryption).

### Ghost/Replay Sample Data Encoding

The community documents the ghost sample encoding at 50ms intervals (20 samples/second), zlib-compressed:

| Field | Type | Encoding |
|-------|------|----------|
| Position | vec3 | 3x float32 |
| Angle | uint16 | 0..0xFFFF maps to 0..pi |
| AxisHeading | int16 | -0x8000..0x7FFF maps to -pi..pi |
| AxisPitch | int16 | -0x8000..0x7FFF maps to -pi/2..pi/2 |
| Speed | int16 | `exp(speed/1000)`, where 0x8000 means 0 |
| VelocityHeading | int8 | -0x80..0x7F maps to -pi..pi |
| VelocityPitch | int8 | -0x80..0x7F maps to -pi/2..pi/2 |

This encoding is NEW information not in our RE docs. The exact integer-to-float mappings are valuable for replay analysis.

### TrackMania Engine Class IDs (from Openplanet)

| Class | ID | Engine |
|-------|-----|--------|
| CTrackMania | 0x24001000 | TrackMania |
| CTrackManiaMenus | 0x2402E000 | TrackMania |
| CTrackManiaNetwork | 0x2402F000 | TrackMania |
| CSceneVehicleVisState | 0x0A00C000 | Scene |

### Block Coordinate System

From community: block coordinates use (X, Y, Z) integers, rotation is 0-3 (90-degree increments). In GBX format version >= 6, coordinates are offset-adjusted by subtracting (1, 0, 1). Blocks with flags == 0xFFFFFFFF are "null" blocks and should be skipped.

---

## Contradictions to Investigate

### Format Flag Byte Ordering

**Community**: Lists byte 6 (ref table compression) as "unused."

**Our RE**: Lists bytes 1 and 2 both controlling compression.

**Issue**: The 4-character format string semantics (e.g., "BUCR") need verification against multiple real files to determine which byte controls body compression vs reference table compression.

### CHmsZoneDynamic vs NSceneDyna

**Community** references `CHmsZoneDynamic::PhysicsStep2` (TMNF era). **Our RE** traces to `NSceneDyna::PhysicsStep_V2`. Not a true contradiction -- the `NSceneDyna` namespace absorbed what was `CHmsZoneDynamic` in TMNF. The HMS layer still exists in TM2020 (41 CHms* classes) but physics simulation moved to the Scene engine.

### Steering Range

**Community**: -65536 to 65536 (integer). **Our RE**: -1.0 to 1.0 (float). Not a contradiction -- the integer range is raw replay encoding, the float range is normalized physics value. Conversion: `float_steer = int_steer / 65536.0`.

---

## Gap-Filling Opportunities

### What Community Knowledge Fills for Our RE

| Gap | Detail | Impact |
|-----|--------|--------|
| Complete API endpoint catalog | 80+ endpoints across Core/Live/Meet APIs | Enables comprehensive network traffic analysis |
| All 24 PhysicsId values | Complete surface material list with gameplay effects | Maps to `EPlugSurfaceMaterialId` enum |
| All 16 GameplayId values | Turbo, reactor, cruise, etc. | Maps to surface effect triggers |
| Ghost sample encoding | Precise integer-to-float mappings for replay data | Critical for replay file parsing |
| ManiaScript class hierarchy | Complete script API surface | Understanding what is exposed to modders |

### What Our RE Uniquely Provides

| Topic | Our Unique RE Contribution |
|-------|--------------------------|
| Decompiled physics functions | 18+ decompiled functions with actual C pseudocode |
| Adaptive sub-stepping algorithm | Velocity-dependent step count with exact thresholds |
| Force computation pipeline | 7 force models (engine, braking, steering, suspension, turbo, reactor, gravity) |
| Memory layout offsets | Exact struct offsets (e.g., vehicle state nibble at +0x128c) |
| Anti-tamper/packing | Entry point obfuscation in .D." section |
| 2,027 class count | Complete class registry from binary RTTI extraction |
| Collision subsystem | NHmsCollision broadphase, contact merging, continuous collision |
| Specific function addresses | Every FUN_ address mapped to subsystem and purpose |

### Recommended Next Steps

1. Verify community class IDs against our binary's class registry (especially CSceneVehicleVisState = 0x0A00C000).
2. Map the 24 PhysicsId values to our decompiled surface effect code.
3. Integrate ghost sample encoding into our file format documentation.
4. Cross-reference GBX.NET chunk implementations with our decompiled chunk readers.
5. Extract the Ubi-AppId from binary strings to confirm `86263886-327a-4328-ac69-527f0d20a237`.
6. Investigate format flag byte semantics by parsing real files.
7. Map VehicleState per-wheel offsets to our decompiled wheel struct layout.
8. Import the complete engine ID table (37 engines) into our class hierarchy documentation.

---

## Related Pages

- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Uses community tools and API docs for browser implementation
- [26-real-file-analysis.md](26-real-file-analysis.md) -- Validates GBX spec against real files
- [30-ghost-replay-format.md](30-ghost-replay-format.md) -- Uses community ghost sample encoding
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Primary Openplanet-sourced data

## Sources

- [GBX.NET GitHub](https://github.com/BigBang1112/gbx-net)
- [Mania Tech Wiki - GBX](https://wiki.xaseco.org/wiki/GBX)
- [Mania Tech Wiki - ManiaPlanet Internals](https://wiki.xaseco.org/wiki/ManiaPlanet_internals)
- [Openplanet](https://openplanet.dev/)
- [Trackmania Web Services API](https://webservices.openplanet.dev/)
- [TMInterface](https://donadigo.com/tminterface/)
- [ManiaScript Reference (BigBang1112)](https://github.com/BigBang1112/maniascript-reference)
- [XML-RPC Documentation](https://wiki.trackmania.io/en/dedicated-server/XML-RPC/home)
- [Official Trackmania Documentation](https://doc.trackmania.com/)

<details><summary>Analysis metadata</summary>

- **Date**: 2026-03-27
- **Purpose**: Catalog publicly available community reverse engineering projects, documentation, and tools for Trackmania, and cross-reference their findings with our RE work.

</details>

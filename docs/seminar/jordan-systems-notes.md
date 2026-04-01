# Jordan's Systems Architecture Notes: TM2020 Deep Dive

This document traces TM2020's architecture end-to-end: boot sequence, state machines, file loading, networking, scripting, and UI. Every claim is sourced from decompiled code or validated RE docs. Where I recommend browser translation strategies, I explain why.

---

## Game Lifecycle

### From Double-Click to Driving

This section covers TM2020's complete boot pipeline. You'll learn the 10-phase startup sequence, the 60+ state coroutine machine, and three strategies for translating it to JavaScript.

The defining question of any game engine: what happens between `entry()` and the first rendered frame? TM2020 runs 10 phases before showing the main menu, then 5 more before you drive.

#### Anti-Tamper + CRT Bootstrap (< 1ms)

The entry point at `0x14291e317` lives in `.D."` -- an obfuscated, anti-tamper protected region. It calls `FUN_1428eb7e6()` (unpacker/decoder loop), then transfers to `FUN_14291da78()` which jumps to real code. Standard MSVC CRT initialization runs: `__scrt_common_main_seh` calls `_initterm` for C++ static constructors, then dispatches to `WinMain` at `FUN_140aa7470`.

*Source: doc 12 Section 3.1, decompiled boot chain*

#### WinMain Early Init (< 10ms)

```
FUN_140aa7470 (WinMain, 202 bytes):
  1. Default window: 640x480 (local_878=0x280, uStack_874=0x1e0)
  2. Init profiling: 75 slots, 128KB buffer, frame budget 20ms outer / 10ms inner
  3. Begin "Startup" profiling tag
  4. Frame timing init: increment DAT_141f9cfd0 (global frame counter)
  5. Begin "InitApp" profiling tag
  6. Transfer to CGbxApp::Init1
```

**Why 75 profiling slots?** The engine has ~75 distinct profiling regions. Each slot is 0x70 bytes (112 bytes). That's `75 * 112 = 8,400 bytes` for profiling metadata, plus the 128KB buffer. Nadeo takes performance instrumentation seriously.

*Source: doc 12 Section 3.1, startup_frame_begin.c*

#### Engine Subsystem Init (100-500ms)

`CGbxApp::Init1` at `FUN_140aa3220` is **7,401 bytes** of initialization code. It registers **16 engine subsystems** into a slot-based manager at `DAT_141f9f018`:

```
SUBSYSTEM SLOT MAP (DAT_141f9f018)
+------+------------------+-------+
| Slot | Subsystem        | Size  |
+------+------------------+-------+
| 0x01 | Core/Memory      | 0x20  |
| 0x03 | Game Engine      | 0x28  |
| 0x05 | Network          | 0x20  |
| 0x06 | Input            | 0x30  |
| 0x07 | Plug/Resource    | 0xA8  |  <-- largest subsystem object
| 0x09 | Audio            | 0x30  |
| 0x0A | Audio Manager    | 0x30  |
| 0x0B | System Config    | 0xE0  |  <-- second largest
| 0x0C | Vision/Render    | 0x38  |
| 0x10 | [UNKNOWN]        | 0x28  |
| 0x11 | Script Engine    | 0xD8  |
| 0x12 | [UNKNOWN]        | 0x38  |
| 0x13 | Control/UI       | 0x30  |
| 0x14 | [UNKNOWN]        | 0x20  |
| 0x2E | [UNKNOWN]        | 0x20  |
+------+------------------+-------+
```

**Architectural observation**: This is a **service locator pattern** (a design pattern where subsystems are registered into a global lookup table) with fixed numeric slots. Not dependency injection, not string-keyed -- integer slots optimized for cache-line-friendly lookups. The non-contiguous slot IDs (0x01, 0x03, 0x05... 0x2E) suggest engine ID constants defined elsewhere.

The Luna Mode accessibility check looks for UUID `41958b32-a08c-4313-a6c0-f49d4fb5a91e`. If matched, `DAT_141f9cff4 = 1` and it logs `"[Sys] Luna Mode enabled."` This accessibility feature isn't documented elsewhere.

*Source: doc 12 Section 3.1, Subsystem Slot Map*

#### Graphics + Game App Init (300-2500ms)

`CGbxApp::Init2` creates the DirectX viewport. DirectX failure produces the only fatal boot error: `"Could not start the game!\r\n  System error, initialization of DirectX failed."` Everything else has fallback paths.

Then `CGbxGame::InitApp` creates the `CSystemEngine` and installs three critical callbacks:
- `+0x70`: Frame callback (`FUN_140101a40`) -- drives per-frame input
- `+0x80`: Security callback (`_guard_check_icall`) -- MSVC Control Flow Guard
- `+0x90`: Render callback (`FUN_140aa93b0`) -- drives the rendering pipeline

These callbacks install **only when `DAT_141fbbee8 == 0`** (non-headless mode). The same binary runs both client and dedicated server by toggling this flag. That's elegant.

*Source: doc 12 Section 3.1, CGbxApp__Init2.c, CGbxGame__InitApp.c*

#### System Engine + Platform Start (150-500ms)

`CSystemEngine::InitForGbxGame` reads config strings: `"Distro"`, `"WindowTitle"`, `"DataDir"` (default: `"GameData\\"`). Then `CGameManiaPlanet::Start` registers playground types and sets the game name to `"Trackmania"`.

`CGameCtnApp::Start` (at `FUN_140b4eba0`, **3,356 bytes**) creates 7 subsystem objects:

```
CGameCtnApp::Start() subsystem allocations:
  param_1[0xF9]  = 0x20  bytes -- game state manager
  param_1[0x111] = 0x10  bytes -- display manager
  param_1[0x112] = 0x138 bytes -- render manager
  param_1[0x76]  = refcounted   -- audio object 1
  param_1[0x7E]  = refcounted   -- audio object 2
  param_1[0x79]  = 0x188 bytes -- game client
  param_1[0x74]  = 0xA0  bytes -- refcounted object
  param_1[0x116] = 0x250 bytes -- scene manager
```

I verified this in the decompiled `CGameCtnApp__Start.c`. Line 92: `FUN_140117690(local_1c8,"CGameCtnApp::Start()");` -- the profiling tag. The reference counting pattern appears throughout: `*(puVar8 + 2) = *(puVar8 + 2) + 1` for AddRef, with the refcount at offset `+0x10` from every object's base, matching the `CMwNod` base class layout: `[vtable(8)][unknown(8)][refcount(4)]`.

*Source: doc 12 Section 3.1, CGameCtnApp__Start.c lines 92-200*

#### The 60+ State Machine

`CGameCtnApp::UpdateGame` at `FUN_140b78f10` is **34,959 bytes** of decompiled C. It runs **every single frame** with `(CGameCtnApp* this, ulonglong* fiberContext)`.

The state machine has **60+ states** organized into 11 phases:

```
COMPLETE STATE MACHINE DATA FLOW
=================================

Phase 0: Bootstrap         (0x000 - 0x3E7)    2 states
Phase 1: Startup           (0x402 - 0x4F9)    8 states
Phase 2: Connection        (0x501 - 0x61D)    7 states
Phase 3: Online Flow       (0x636 - 0x6D7)    5 states
Phase 4: Dialog/Nav        (0x733 - 0x852)    12 states
Phase 5: Main Menu         (0xCDCC label)     1 entry point
Phase 6: Menu Dispatch     (0x9A5 - 0xAFF)    20+ result codes
Phase 7: Gameplay Loop     (0xB43 - 0xCC6)    10 states
Phase 8: Map Load/Editor   (0xCD1 - 0xDE5)    12 states
Phase 9: Replay/Podium     (0xE14 - 0xF3D)    3 states
Phase 10: Multiplayer      (0xF85 - 0x109A)   10 states
Phase 11: Special          (0xFFFFFFFF)        shutdown
```

**The coroutine pattern**: Every state uses the same yield mechanism. A **stackless coroutine** (a cooperative multitasking pattern where persistent state lives on the heap, not on separate OS stacks) stores the current state at `+0x08` in the fiber context, and a sub-fiber pointer at `+0x10`. When a state waits for an async operation, it sets the sub-fiber, writes its state ID back to `+0x08`, and returns. Next frame, the switch jumps back, checks if the sub-fiber is done (`+0x10 == -1`), and either waits again or proceeds.

```
THE YIELD PATTERN (appears hundreds of times):
  if (*(longlong *)(uVar16 + 0x10) - 1U < 0xfffffffffffffffe) {
      iVar12 = *(int *)(*(longlong *)(uVar16 + 0x10) + 8);
      FUN_someFunction(param_1, uVar16 + 0x10);
      if (iVar12 == -1) goto LAB_140b81895;  // yield up
  }
  if (*(longlong *)(*param_2 + 0x10) != -1) {
      *(undefined4 *)(*param_2 + 8) = CURRENT_STATE;  // stay here
      goto LAB_140b81895;                               // yield
  }
  // Sub-coroutine done, proceed to next state
```

All persistent state occupies a 0x380-byte heap-allocated context. This matters for browser translation: JavaScript `async/await` maps perfectly to this pattern.

*Source: doc 12 Sections 1.2-1.3, 4.1-4.3*

#### The Path to Main Menu: 15 States Minimum

```
0x000  [Game Init] -- allocate 0x380 context, log "[Game] starting game."
  |
0x3E7  [Init Complete] -- UpdateGame_Init sub-coroutine done
  |
0x402  [Startup Sequence] -- "[Startup]InitBeforeProfiles"
  |
0x406  [Init Before Profiles] -- profile system init
  |
0x484  [Wait for Login] -- polls *(login+0x54): <2=waiting, 2=OK, >2=error
  |       error: formats "%1 (code %2/%3)"
0x488  [Login Timeout] -- checks DAT_141ffad50 < *(ctx+0xC) + 1000
  |
0x496  [Network Probe 1] -- FUN_140b00500
  |
0x497  [User Profile Load] -- virtual(*+0x288)
  |
0x499  [Network Probe 2] -- FUN_140b00ce0
  |
0x4E3  [Smoke Test Check] -- /smoketest command line
  |
0x4F9  [Master Server] -- "Checking the connection..." dialog
  |
0x501-0x5FD  [Connection Flow] -- 2000ms timeout, dialog wait
  |
LAB_140b7cdcc  [MAIN MENU] -- FUN_140b54b90(param_1, 2), "[Game] main menu."
```

**Estimated total time**: 2-8 seconds depending on network conditions. The 1000ms login timeout at state 0x488 is the main variable.

*Source: doc 12 Section 11.1-11.3*

#### From Main Menu to Driving: 6 More States

When you click Play, the menu returns a result code at `*param_2 + 0x174`. The game logs `"[Game] exec MenuResult: {result}"`. For playing a specific map (result 0x09):

```
0x9A5  [Menu Result Dispatch] -- read *(ctx+0x174)
  |     result 0x09: Play Map -> set phase 0x0E
0xBF6  [Load Map] -- FUN_140b57d10 resolves map path
  |
0xCD1  [Load Challenge Init] -- show "Please wait..." dialog
  |
0xCD2  [Load Challenge Execute] -- FUN_140b58530 loads GBX (yields while loading)
  |
0xD2D  [Gameplay Start] -- FUN_140c0dcc0 creates arena context
  |     mode=1, type=3, flags=6
  |     camera set to type 3 (follow car) at editor_ctx+0x70
  |     FUN_140dd2f10 starts gameplay dispatch
0xD45  [Gameplay Active] -- polls FUN_140b76aa0 each frame
  |     returns 0: continue playing (stay in 0xD45)
  |     returns non-0: race complete, return to menu
```

**Key insight**: State 0xD45 is where you LIVE during gameplay. Every frame, the state machine enters 0xD45, calls `FUN_140b76aa0` to check if gameplay is over, and if not, yields. The actual gameplay (physics, input, script, rendering) runs through the engine callbacks installed at Phase 4. The state machine monitors for completion -- it does not drive gameplay frame-by-frame.

*Source: doc 12 Sections 12.1-12.5*

### Browser Translation Strategies

The coroutine-based state machine maps to JavaScript in three ways:

**Option 1: async/await** (recommended)
```javascript
async function updateGame(app) {
  await gameInit(app);           // State 0x000
  await startupSequence(app);    // States 0x402-0x4E3
  await connectToServer(app);    // States 0x4F9-0x5FD

  while (true) {
    const menuResult = await mainMenu(app);  // Menu states
    if (menuResult === 0x01) break;          // Quit

    if (menuResult === 0x09) {
      const map = await loadMap(app, menuResult);  // 0xCD1-0xCD2
      await playMap(app, map);                      // 0xD2D-0xD45
    }
  }
  await shutdown(app);  // 0xFFFFFFFF
}
```

**Option 2: JavaScript generators** (closer to the original pattern)
```javascript
function* updateGame(app) {
  yield* gameInit(app);
  yield* startupSequence(app);
  // ...
}
```

**Option 3: Explicit state machine** (closest to the decompiled code)
```javascript
class GameStateMachine {
  state = 0x000;
  context = new ArrayBuffer(0x380);

  tick() {
    switch (this.state) {
      case 0x000: /* ... */ break;
      case 0x3E7: /* ... */ break;
      // 60+ cases
    }
  }
}
```

I'd go with Option 1. The `async/await` approach loses explicit state IDs but gains readability. We're not trying to be bug-compatible -- just behaviorally equivalent.

The headless/dedicated server pattern (`DAT_141fbbee8` / `DAT_141fbbf0c`) maps to a Node.js server running the same state machine with rendering disabled. The original binary does exactly this.

*Source: doc 12 Sections 10.1-10.6*

---

## Loading a Map

### GBX File Format

This section covers the GBX binary format byte-by-byte, LZO1X compression, the LookbackString interning system, and the 22-stage map initialization pipeline.

Every piece of content in TM2020 is a GBX (GameBox) file. Maps, items, ghosts, replays, materials, meshes -- all GBX. The entry point for loading is `FUN_140904730` (`CSystemArchiveNod::LoadGbx`). It checks for three formats: `.gbx` (binary), `.gbx.xml` (XML), `.json` (JSON import), then orchestrates: header parse, class instantiation via factory, body decompress, chunk dispatch, reference resolution.

*Source: FUN_140904730_LoadGbx.c, doc 16 Section 1*

#### The Header (Bytes 0x00 - variable)

```
BYTE-LEVEL GBX HEADER (Version 6, TM2020)
==========================================
Offset  Bytes              Field               Value
------  -----              -----               -----
0x00    47 42 58           magic               "GBX"
0x03    06 00              version             6 (uint16 LE)
0x05    42 55 43 52        format_flags        "BUCR"
0x09    00 30 04 03        class_id            0x03043000 (CGameCtnChallenge)
0x0D    XX XX XX XX        user_data_size      total header chunk data bytes
0x11    XX XX XX XX        num_header_chunks   typically 6 for maps
0x15    [chunk index]      8 bytes per chunk   (chunk_id, size | heavy_flag)
var     [chunk data]       concatenated        all header chunk payloads
var     XX XX XX XX        num_nodes           node count for reference sizing
```

**Format flags "BUCR"** -- every real TM2020 file uses this:
- B = Binary (not Text)
- U = Body wrapper uncompressed
- C = Body stream compressed (LZO1X)
- R = With external references

These flags parse at `FUN_140901850`:
```c
// Byte 0: 'T' (text=1) or 'B' (binary=0)
// Byte 1: 'C' (compressed=1) or 'U' (uncompressed=0) -> stored at +0xD8
// Byte 2: 'C' (compressed=1) or 'U' (uncompressed=0) -> stored at +0xDC
// Byte 3: 'R' (with refs) or 'E' (no external refs)
```

*Source: doc 16 Sections 2-3, verified against 5+ real files in doc 26*

#### LZO1X Decompression (NOT zlib!)

Body compression uses **LZO1X**, not zlib. Evidence:
- Real file validation: compressed body data starts with bytes consistent with LZO1X encoding (0x1A in TechFlow.Map.Gbx means "initial literal run of 9 bytes")
- Both zlib and raw deflate FAIL on the compressed data
- Community tools (GBX.NET, gbx-py) all use LZO
- The decompression function `FUN_140127aa0` fires when `param_1+0xDC` is non-zero

**zlib IS used** for ghost sample data within replays. Two compression layers exist:
1. Outer: GBX body = LZO1X
2. Inner: Ghost samples within body = zlib deflate

The decompression buffer pools at `DAT_14205c280` with max size `0xFFFFF` (~1MB). Anything larger gets a fresh allocation.

*Source: doc 16 Section 8, validated in doc 26 Section 2*

#### The LookbackString System

This is the cleverest optimization in the format. **LookbackString** is a per-archive string interning table that replaces repeated strings (like `"StadiumRoadMainStraight"`) with compact back-references.

```
LOOKBACKSTRING READ ALGORITHM:
  1. First read in a context: uint32 must equal 3 (version marker)
  2. Subsequent reads: uint32 value
     Bits 31-30 = 0b11 (0xC0000000): new string follows, add to table
     Bits 31-30 = 0b01 (0x40000000): also new string (in TM2020!)
     Bits 31-30 = 0b10 (0x80000000): back-reference, index = bits 29-0
     Bits 31-30 = 0b00: empty string
```

**Critical correction**: Old documentation claimed `0b01` = "well-known string ID" (predefined like "Stadium", "Valley"). In TM2020, BOTH `0b01` and `0b11` mean "new inline string." The well-known string table exists but uses specific values like `0x40000001` = "Unassigned", `0x40000003` = "Stadium".

The table resets per header chunk but is shared across all body chunks for a single node (with exceptions for encapsulated chunks like 0x03043040, 0x03043054).

*Source: doc 16 Section 29, corrected from real file analysis in doc 26*

#### Body Chunk Stream

After decompression, the body is a sequential stream of chunks:

```
BODY CHUNK FORMAT:
  +0x00  uint32  chunk_id        (class_base | chunk_index)
                                  Special: 0xFACADE01 = END OF BODY

  If skippable chunk:
    +0x04  uint32  skip_marker   Must be 0x534B4950 ("SKIP")
    +0x08  uint32  chunk_size    Payload size in bytes
    +0x0C  bytes   chunk_data    Payload

  If non-skippable:
    +0x04  bytes   chunk_data    Must be fully understood to continue!
```

The `0xFACADE01` sentinel is confirmed in `FUN_1402d0c40`. The "SKIP" marker is ASCII `S-K-I-P` = `0x534B4950`. Skippable chunks are safe to skip. Non-skippable chunks are the parser's nightmare -- if you can't parse one, you can't find the next chunk boundary.

*Source: doc 16 Sections 6-7*

### The 22-Stage Map Loading Pipeline

After GBX deserialization, the map undergoes a 22-stage initialization pipeline. Each stage has a dedicated profiling marker:

```
STAGE  METHOD                                          COST
-----  ------                                          ----
  1    LoadDecorationAndCollection                     SLOW (loads .pak assets)
  2    InternalLoadDecorationAndCollection             Moderate
  3    UpdateBakedBlockList                            Fast
  4    AutoSetIdsForLightMap                           Fast
  5    LoadAndInstanciateBlocks                        SLOW (proportional to block count)
  6    InitChallengeData_ClassicBlocks                 Moderate
  7    InitChallengeData_Terrain                       Moderate
  8    InitChallengeData_DefaultTerrainBaked           Fast
  9    InitChallengeData_Genealogy                     Fast
 10    InitChallengeData_PylonsBaked                   Fast
 11    InitChallengeData_ClassicClipsBaked             Fast
 12    InitChallengeData_FreeClipsBaked                Fast
 13    InitChallengeData_Clips                         Moderate
 14    CreateFreeClips                                 Moderate
 15    InitPylonsList                                  Fast
 16    CreatePlayFields                                Fast
 17    TransferIdForLightMapFromBakedBlocksToBlocks    Fast
 18    InitEmbeddedItemModels                          SLOW (if many embedded items)
 19    LoadEmbededItems                                Moderate
 20    InitAllAnchoredObjects                          Moderate
 21    ConnectAdditionalDataClipsToBakedClips          Fast
 22    RemoveNonBlocksFromBlockStock                   Fast
```

**Bottlenecks**: Stages 1 (decoration/pack loading), 5 (block instantiation), and 18 (embedded items). Lightmap generation, if not pre-baked, is the slowest of all.

**Parallelization opportunities**: Stages 3-4 (lightmap IDs), 9 (genealogy), 10 (pylons), and 15 (pylon list) are independent transforms. Stages 11-14 (clip connectivity) form a dependency chain but could run on a worker. Stage 1 (decoration loading) blocks everything else.

*Source: doc 28 Section 6.2-6.5*

---

## The Block/Item System

### The 32-Meter Grid

This section covers TM2020's block coordinate system, naming conventions, waypoint connectivity, and how items differ from blocks.

TM2020 maps exist on a discrete 3D grid:

```
COORDINATE SYSTEM:
  X axis: Right (left-handed, D3D convention)
  Y axis: Up (elevation)
  Z axis: Forward

GRID UNITS:
  X, Z: 32 meters per grid unit
  Y:     8 meters per grid unit (height sub-unit)

STANDARD STADIUM MAP:
  48 x 255 x 48 grid units
  = 1536m x 2040m x 1536m world space
  Default terrain: Y=9 (72 meters)

CONVERSION:
  world_x = block_x * 32.0
  world_y = block_y * 8.0
  world_z = block_z * 32.0
```

*Source: doc 28 Section 1.2, confirmed by Openplanet Finetuner using Math::Ceil(distance/32.0f)*

### Block Naming Convention

Block names follow a strict hierarchy: `{Environment}{Category}{Shape}{Variant}{Modifier}`

```
DECODED NAMING EXAMPLES:
  StadiumRoadMainStraight           = Stadium + Road (Main) + Straight
  StadiumRoadMainCurvex2            = Stadium + Road (Main) + Curve + x2 (double width)
  StadiumPlatformSlopeMirror        = Stadium + Platform + Slope + Mirror
  StadiumDecoWallStraight           = Stadium + Decoration (Wall) + Straight
  StadiumGrassMainSlope             = Stadium + Grass (Main) + Slope

CATEGORIES:
  Road/RoadMain    -- drivable road surface
  Platform         -- flat surface, no road markings
  DecoWall/Hill    -- decorative, non-drivable
  Gate             -- start/finish/checkpoint
  Grass/Water      -- terrain elements
  Pillar/Pylon     -- support structures (often auto-generated)

SHAPES:
  Straight, Curve/Turn, Slope, Tilt, Cross, DiagLeft/DiagRight, Chicane

MODIFIERS:
  x2/x3/x4 (width), Mirror, Narrow, In/Out (curve direction)
```

*Source: doc 28 Section 9, real map exports*

### Waypoints and Connectivity

Waypoints define the race route. Four types exist, stored as `CGameWaypointSpecialProperty` on blocks:

| Type | Purpose | Validation Rule |
|------|---------|-----------------|
| Start | Race spawn | Exactly 1 per map |
| Finish | Race end | Exactly 1 per map |
| Checkpoint | Timing gate | 0 or more, all must be reachable |
| StartFinish | Multilap combined | Exactly 1 (replaces Start+Finish) |

Detection uses trigger volumes (`CSceneTriggerAction`, `CGameTriggerGate`). When the car's bounding volume intersects the gate's trigger zone, the checkpoint/finish registers.

Route validation runs via `CGameEditorPluginMapConnectResults` -- the editor simulates whether a car can drive from Start through all Checkpoints to Finish via connected road surfaces.

*Source: doc 28 Sections 3.1-3.4, binary strings `|BlockInfo|Start`, `|BlockInfo|Finish`, etc.*

### Items vs Blocks

| Aspect | Blocks | Items |
|--------|--------|-------|
| Class | `CGameCtnBlock` | `CGameCtnAnchoredObject` |
| Placement | 32m grid OR free | Always free (arbitrary Vec3) |
| Rotation | 4 cardinal (grid) or quaternion (free) | Euler angles or quaternion |
| Connectivity | Clip system (typed connection points) | None |
| Storage chunk | `0x03043011` | `0x03043040` |
| Collision | Built into block model | Defined by `CPlugStaticObjectModel` |

**"This is Minecraft with racing -- am I wrong?"**

Not entirely. Like Minecraft: discrete grid, block types with specific behaviors, automated support generation (pylons = pillar blocks auto-placed under air variants). Unlike Minecraft: the grid is 32 meters not 1 meter, blocks are complex pre-built 3D models not cubes, and the clip system enforces connectivity rules. Items are the escape hatch from the grid -- they make TM2020 maps look organic rather than blocky.

*Source: doc 28 Sections 2.1, 4.1*

---

## Ghost and Replay System

### The Recording Pipeline

This section covers ghost sample encoding, input recording, and server-side replay validation for anti-cheat.

```
DURING GAMEPLAY (per frame):
  1. CInputReplay captures raw input each simulation tick (100 Hz)
  2. CPlugEntRecordData stores entity state samples (position, rotation, speed)
  3. CGameCtnGhost / CGameGhostTMData wraps ghost-specific metadata
  4. CGhostManager manages active ghost instances
  5. CGameCtnReplayRecord bundles ghost(s) + map reference + times + metadata
```

### 50ms Samples, 22 Bytes Each

Ghost samples are visual snapshots -- NOT physics state. They record at **20 samples per second** (50ms period), much coarser than the 100Hz physics tick. Ghosts exist for visual playback, not deterministic re-simulation.

```
PER-SAMPLE ENCODING (22 bytes):
  Offset  Type     Size  Field              Encoding
  ------  ----     ----  -----              --------
  0x00    float32  4     Position X         IEEE 754 (meters)
  0x04    float32  4     Position Y         IEEE 754 (meters)
  0x08    float32  4     Position Z         IEEE 754 (meters)
  0x0C    uint16   2     Angle              value / 0xFFFF * pi       [0, pi]
  0x0E    int16    2     Axis Heading       value / 0x7FFF * pi       [-pi, pi]
  0x10    int16    2     Axis Pitch         value / 0x7FFF * (pi/2)   [-pi/2, pi/2]
  0x12    int16    2     Speed              exp(value / 1000)         special: 0x8000 = 0
  0x14    int8     1     Velocity Heading   value / 0x7F * pi         [-pi, pi]
  0x15    int8     1     Velocity Pitch     value / 0x7F * (pi/2)     [-pi/2, pi/2]
```

**The speed encoding is clever**: `exp(value/1000)` is an exponential curve. Small integer steps at low speeds map to small velocity differences; the same step at high speeds maps to larger differences. This matches perceptual importance -- you notice the difference between 10 and 15 km/h more than between 500 and 505 km/h.

**Precision analysis**:
- int16 heading/pitch: ~0.0001 rad (~0.006 deg) -- smooth visual playback
- int8 velocity direction: ~0.025 rad (~1.4 deg) -- coarser, less visually critical
- uint16 angle: ~0.00005 rad (~0.003 deg) -- very precise

**For a 38-second replay**: `38000/50 = 760 samples * 22 bytes = 16,720 bytes` uncompressed. After zlib: ~5-10 KB. This is the inner zlib layer (distinct from the outer LZO body compression).

*Source: doc 30 Section 7, community knowledge verified by GBX.NET*

### Input Recording at 100Hz

`CInputReplay` captures raw inputs at the full physics tick rate, separate from visual ghost data:

```
INPUT FIELDS (per tick):
  InputSteer:      float -1.0 to 1.0  (from raw int: -65536 to 65536)
  InputGasPedal:   float  0.0 to 1.0  (from raw int: 0 to 65535)
  InputBrakePedal: float  0.0 to 1.0  (from raw int: 0 to 65535)
  InputIsBraking:  bool   0 or 1

  Conversion: float_value = int_value / 65536.0
```

Input recording is likely **event-based** (only state changes stored). For a 38-second run, this produces ~200-500 events rather than 3,800 ticks of data.

*Source: doc 30 Section 8, community (TMInterface/donadigo)*

### Ghost Validation for Anti-Cheat

The server validates replays by re-simulation:

```
SECURE RECORD ATTEMPT FLOW:
  1. POST  CreateMapRecordSecureAttempt   -- get attempt token
  2. Player completes the map
  3. PATCH PatchMapRecordSecureAttempt    -- submit ghost + result
  4. Upload UploadSessionReplay           -- full replay for validation
  5. Server replays inputs, verifies time matches
```

Configuration parameters from the binary:
- `AntiCheatReplayChunkSize` -- size per upload chunk
- `AntiCheatReplayMaxSize` -- maximum total upload
- `UploadAntiCheatReplayForcedOnCheatReport` -- force upload on detection

The server checks: deterministic re-simulation matches claimed time, no impossible physics states (wall clipping), client file checksums match known-good hashes (`CryptedChecksumsExe`).

*Source: doc 30 Section 14, doc 17 Section 13*

### Building Your Own Replay System

**For custom replays** (recommended approach):
```typescript
interface InputFrame {
  tick: number;     // Physics tick (100 Hz)
  steer: number;    // -1.0 to 1.0
  gas: number;      // 0.0 to 1.0
  brake: number;    // 0.0 to 1.0
}

interface SimpleReplay {
  mapUid: string;
  playerName: string;
  vehicleType: string;
  finishTime: number;       // milliseconds
  checkpoints: number[];    // cumulative ms timestamps
  inputs: InputFrame[];     // only store state CHANGES
}
```

Record only when input changes. Play back by feeding into deterministic physics at 100Hz. If physics is bit-identical, the replay is exact. For visual-only ghosts (opponent display), sample position at 20Hz and interpolate -- exactly what TM2020 does.

*Source: doc 30 Section 16*

---

## Networking

### The Authentication Chain

This section covers TM2020's 4-step token exchange, the 11-layer network stack, and minimum viable browser networking.

TM2020 uses a 4-step token exchange:

```
AUTH DATA FLOW:
  UPC SDK (DLL) --ticket--> Ubisoft Services --session--> Nadeo Core --JWT--> API Access
       |                          |                           |               |
  UPC_TicketGet()        POST /v3/profiles/    POST /v2/authentication/   Authorization:
  (opaque blob)          sessions               token/ubiservices         nadeo_v1 t=<JWT>
                         Ubi-AppId: 86263886-...
                         Authorization: Basic
                         base64(email:pw)
```

**Three API domains with different audiences**:

| Audience | Domain | Purpose |
|----------|--------|---------|
| `NadeoServices` | `prod.trackmania.core.nadeo.online` | Auth, maps, records, accounts |
| `NadeoLiveServices` | `live-services.trackmania.nadeo.live` | Leaderboards, competitions, clubs |
| `NadeoLiveServices` | `meet.trackmania.nadeo.club` | Matchmaking, ranked |

JWT token lifetime: 55 minutes + random 1-60 seconds jitter before refresh (confirmed from Openplanet source). The `Ubi-AppId` for TM2020 is `86263886-327a-4328-ac69-527f0d20a237`.

*Source: doc 17 Sections 2-3, verified from Openplanet NadeoServices plugin and decompiled function at 0x140356160*

### The 11-Layer Network Stack

```
NETWORK ARCHITECTURE (from binary):
  Layer 11: Game Logic (CGameCtnNetwork, CPlaygroundClient)
  Layer 10: Wire Messages (CGameNetForm*)
  Layer  9: Web Services (297 CWebServices* classes!)
  Layer  8: Nadeo API (175+ CNetNadeoServicesTask_* classes)
  Layer  7: Ubisoft API (30+ CNetUbiServicesTask_* classes)
  Layer  6: UPC SDK (upc_r2_loader64.dll)
  Layer  5: XML-RPC (CXmlRpc, xmlrpc-c library)
  Layer  4: Master Server (CNetMasterServer, legacy)
  Layer  3: File Transfer (CNetFileTransfer)
  Layer  2: Network Engine (CNetEngine, CNetServer, CNetClient, 262 classes)
  Layer  1: Transport (WS2_32 Winsock, libcurl static, OpenSSL 1.1.1t+quic)
  Layer  0: External (UPC SDK DLL, Vivox VoiceChat.dll, XMPP)
```

**562 total networking classes**. The HTTP client uses libcurl's multi interface for non-blocking I/O. Each request is a 0x1A8-byte structure. One shared `curl_multi_handle` lives at `DAT_1420ba2f8`. The web services layer uses a dedicated background thread (`CWebServices::Update_WebServicesThread`) with results dispatched to the main thread.

*Source: doc 17 Sections 1, 4, 6*

### Real-Time Multiplayer: TCP + UDP Dual Stack

The game uses **both TCP and UDP simultaneously** per connection:

```
TCP Channel:                    UDP Channel:
  - Reliable state sync           - Player positions
  - Chat messages                 - Input data
  - Admin commands                - Time-critical sync
  - File transfers                - Ping measurements
  - Serialized objects (Nods)     - Voice chat frames
```

UDP probing happens after TCP handshake. If UDP hole-punching fails, it falls back to TCP-only. Per-frame network updates follow a strict deterministic order:
1. `NetUpdate_BeforePhy` -- receive remote inputs
2. Physics step (deterministic -- all clients simulate identically)
3. `NetUpdate_AfterPhy` -- send local results
4. `NetLoop_Synchronize` -- ensure shared game timer

*Source: doc 17 Sections 7-8, debug strings at 0x141c2b348-0x141c49c28*

### Minimum Browser Online Stack

For a browser client, the minimum viable online stack is:

1. **Auth proxy server** (Node.js): handles UPC/Ubisoft auth (can't run from browser due to CORS)
2. **Token management** (client): store JWT, refresh every 55 minutes, use `nadeo_v1 t=<token>` header
3. **Map download**: `GET /maps/{mapId}` from Core API
4. **Leaderboard read**: `GET /map-records` from Live API
5. **Ghost download**: `GET` from ghost download endpoint

Total: ~4 API endpoints. No WebSocket needed for single-player. For multiplayer, use WebSocket (reliable) + WebRTC DataChannel (unreliable) instead of TCP+UDP -- the browser can't do raw sockets.

*Source: doc 17 Section 16, plan doc 01*

---

## ManiaScript

### The Engine's Built-in Scripting Language

This section covers `CScriptEngine`, ManiaScript's type system, coroutine primitives, and whether to replicate it in a browser project.

ManiaScript is interpreted by `CScriptEngine`, a singleton at `0x140874270` (`CScriptEngine::Run`):

```c
// CScriptEngine::Run (316 bytes):
void FUN_140874270(longlong engine, longlong context, undefined4 mode) {
    *(longlong *)(engine + 0x60) = context;        // Set current script
    lVar1 = *(longlong *)(context + 0x10);          // Get bytecode
    FUN_1402d3df0(engine, 1);                       // Reset timer
    // ... dynamic profiling tag: "CScriptEngine::Run(%s)"
    *(context + 0x30) = *(engine + 0x20);           // Copy debug mode
    *(context + 0x58) = execution_mode;             // 1=normal, 0=debug
    *(context + 0x08) = mode;                       // Entry point
    *(context + 0x0C) = FUN_14018cb30(mode);        // Resolve entry
    FUN_14010be60(context + 0x100);                 // Clear output
    *(context + 0xC4) = DAT_141ffad50;              // Timestamp
    FUN_1408d1ea0(lVar1, context);                  // EXECUTE BYTECODE
    *(engine + 0x60) = 0;                           // Clear context
    if (return_value == -1)
        *(*(context + 200) + 400) = 2;              // Error code 2
}
```

*Source: CScriptEngine__Run.c (decompiled), doc 31 Section 24*

### 12 Types, 4 Coroutine Primitives

```
MANIASCRIPT TYPE SYSTEM (all 12 confirmed via binary tokens):
  Void, Boolean, Integer, Real, Text,
  Vec2, Vec3, Int2, Int3, Iso4,
  Ident, Class

COROUTINE PRIMITIVES:
  yield;            -- pause, resume next frame
  sleep(1000);      -- pause for N milliseconds
  wait(condition);  -- poll condition each frame
  meanwhile { }     -- parallel execution branch
```

The `yield` implementation: script sets return state, exits `FUN_1408d1ea0`. Engine re-enters same context next frame. `sleep` compares `*(context+0xC4)` against global tick counter `DAT_141ffad50`. `wait` is syntactic sugar for `while (!condition) yield;`.

*Source: doc 31 Sections 2, 9, confirmed at addresses 0x141c023a8, 0x141c024c8, 0x141c024b0*

### Game Mode Lifecycle

Game modes use a hierarchy of labels injected via `#Extends`:

```
SERVER LIFECYCLE:
  Server -> Match -> Map -> Round -> Turn -> PlayLoop

LABELS (each has Init/Start/End):
  ***InitServer*** -> ***StartServer***
    ***InitMatch*** -> ***StartMatch***
      ***InitMap*** -> ***StartMap***
        ***InitRound*** -> ***StartRound***
          ***InitTurn*** -> ***StartTurn***
            ***PlayLoop***  <-- main gameplay tick
          ***EndTurn***
        ***EndRound***
      ***EndMap***
    ***EndMatch***
  ***EndServer***
```

Built-in modes: `TM_TimeAttack_Online`, `TM_Rounds_Online`, `TM_Cup_Online`, `TM_Champion_Online`, `TM_Knockout_Online`, `TM_Laps_Online`, `TM_Teams_Online`.

*Source: doc 31 Sections 19.1-19.4*

### Should You Build a Scripting Language?

**For the MVP**: Skip scripting entirely. Hardcode TimeAttack rules (start timer on first input, record checkpoints, stop on finish). This covers 90% of single-player use.

**If scripting is needed**: Use JavaScript directly. ManiaScript's coroutine model (`yield`/`sleep`/`wait`) maps to async generators. The 12 types map to JS primitives. Nadeo built their own language for sandboxing user-created content -- but in a browser, you already have sandboxing (Web Workers with controlled APIs).

Building a ManiaScript interpreter (~10,000 LOC) is only necessary to run existing TM2020 game mode scripts verbatim. For a fresh project, that's a bad ROI.

*Source: plan doc 01 (@opentm/scripting section)*

---

## The UI System

### ManiaLink: XML UI in a 320x180 Coordinate Space

This section covers TM2020's three-layer UI architecture, native controls, and why HTML/CSS replaces all of it.

TM2020's UI system has three layers:

```
Layer 3: ManiaLink XML + ManiaScript    (content creators)
Layer 2: CGameManialink* classes (31)   (script-accessible wrappers)
Layer 1: CControl* classes (39)         (native C++ controls)
Layer 0: CHms* / CDx11*                 (GPU rendering)
```

**70 total UI classes** (39 native + 31 ManiaLink).

The coordinate system is remarkable:

```
MANIALINK v3 COORDINATE SPACE:
  Origin: (0, 0) = screen center
  Width:  320 units (-160 to +160)
  Height: 180 units (-90 to +90)
  Y-axis: UP (opposite of HTML/CSS!)
  Aspect: fixed 16:9

  pos="0 -10" moves an element DOWN
  pos="-100 50" is upper-left area
```

*Source: doc 34 Section 5.1*

### The CControl Hierarchy (39 Native Controls)

```
CControlBase
  +-- CControlButton, CControlLabel, CControlText
  +-- CControlTextEdition, CControlEntry, CControlEnum
  +-- CControlSlider, CControlQuad, CControlGrid
  +-- CControlGraph, CControlPager, CControlMediaPlayer
  +-- CControlMiniMap, CControlColorChooser(2)
  +-- CControlCamera, CControlScriptConsole, CControlScriptEditor
  +-- CControlTimeLine2, CControlUiRange, CControlUrlLinks
CControlContainer, CControlFrame (+Animated, +Styled)
CControlEffect (+Combined, +Master, +Motion, +MoveFrame, +Simi)
CControlLayout, CControlStyle, CControlStyleSheet
CControlSimi2, CControlEngine
```

`CControlEngine` singleton drives 7 per-frame update phases: `ContainersDoLayout`, `ContainersEffects`, `ContainersFocus`, `ContainersValues`, `ControlsEffects`, `ControlsFocus`, `ControlsValues`.

*Source: doc 34 Section 2.1-2.2*

### HUD Elements

The in-game HUD uses `CUILayer` objects attached via `UIManager.UIAll.UILayers` in ManiaScript. Each layer is a ManiaLink page. The speedometer, timer, checkpoint display -- all ManiaLink XML with ManiaScript event handlers updating `CMlLabel.Value` every frame.

Standard HUD modules load from `CGamePlaygroundModulePlaygroundScriptHandler` subclasses, with 12 module types in the binary class hierarchy.

*Source: doc 34 Section 10, doc 31 Section 19.7*

### HTML/CSS Replaces All of This

Every ManiaLink element has a direct HTML equivalent:

```
ManiaLink              HTML/CSS
---------              --------
<quad>                 <div> with background-image or <img>
<label>                <span> or <p>
<entry>                <input type="text">
<textedit>             <textarea>
<gauge>                <progress> or <div> with width %
<graph>                <canvas> with chart.js
<frame>                <div> with position: relative
<framemodel>           <template>
<frameinstance>        template.content.cloneNode(true)
<audio>                <audio>
<video>                <video>
<fileentry>            <input type="file">
<include>              fetch() + innerHTML
```

The 320x180 coordinate space with centered origin maps to CSS transforms:
```css
.manialink-viewport {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow: hidden;
}
.manialink-element {
  position: absolute;
  /* Convert ManiaLink coords to CSS: */
  /* x: (ml_x + 160) / 320 * 100vw */
  /* y: (90 - ml_y) / 180 * 100vh  -- flip Y axis! */
}
```

The 65+ built-in quad styles (Bgs1, Icons64x64_1, etc.) would need re-creation as CSS classes or sprite sheets.

**My recommendation**: Do NOT replicate ManiaLink for UI. Build native web UI. Only implement ManiaLink parsing if you need to load community-created game mode UIs.

*Source: doc 34 Section 14, plan doc 01 (@opentm/ui section)*

---

## My Architecture Plan

### What I'd Build the Same Way

This section covers my architectural recommendations: what to keep from TM2020, what to change, and the feasibility of the 68-task MVP.

1. **Coroutine-based state machine**: The fiber/yield pattern is perfect. `async/await` maps directly. The 60+ states become ~20 async functions.

2. **Slot-based subsystem manager**: Integer-keyed subsystems with O(1) lookup. In TypeScript: a `Map<number, Subsystem>` or even a plain array.

3. **Headless mode = server mode**: Same code, rendering disabled. Node.js server with the same state machine. TM2020 does this with `DAT_141fbbee8`.

4. **Deterministic physics for replay validation**: Input-based replay is the right approach. Record inputs at tick rate, re-simulate for validation. The 100Hz physics tick with adaptive sub-stepping is well-designed.

5. **Chunk-based file format**: GBX's chunk system with skippable chunks is forward-compatible and parseable. I'd use a similar design (though I'd pick a standard container like FlatBuffers or MessagePack).

6. **Ghost system with dual representation**: Visual ghosts at 20Hz for rendering, input ghosts at 100Hz for validation. Different use cases, different fidelity requirements.

### What I'd Do Differently

1. **NOT LZO for compression**: Use zstd or brotli. LZO is fast but produces larger output. Brotli is standard in browsers (built into `Accept-Encoding`). The 1MB decompression pool limit suggests LZO was chosen for memory-constrained environments (consoles).

2. **NOT a custom scripting language**: Use JavaScript/TypeScript directly. ManiaScript's 12 types and coroutine model replicate with TypeScript's type system and async generators. The ~10,000 LOC interpreter adds no value unless you need TM2020 script compatibility.

3. **NOT ManiaLink XML for UI**: Use HTML/CSS/Svelte. The 320x180 coordinate space with manual positioning is 2008-era UI technology. CSS Grid + Flexbox + media queries give better results with less effort.

4. **NOT custom binary file format**: Use standard formats (glTF for meshes, JSON for metadata, standard image formats) with optional binary packing for performance. GBX is powerful but the 200+ class ID remapping table and LookbackString complexity are self-inflicted wounds.

5. **NOT TCP+UDP dual stack**: Use WebSocket + WebRTC DataChannel. Same reliable/unreliable split, but browser-native. No UDP hole-punching or Winsock needed.

6. **NOT 22-stage map loading**: Lazy-load blocks on demand. The 22-stage pipeline is sequential because of 2004-era engine constraints. With WebGPU, block meshes stream and instantiate progressively.

### The 68-Task MVP: Is It Realistic?

The plan document breaks the MVP into 68 tasks across 12 weeks, one developer:

```
GROUP                TASKS   WEEKS   RISK LEVEL
Project Setup          5     1       Low
Math Foundation        4     1-2     Low
GBX Parser            10     2-4     MEDIUM (LookbackString edge cases)
Block System           5     3-5     HIGH (mesh extraction from .pak files!)
Renderer              10     4-7     MEDIUM (WebGPU maturity)
Physics               10     5-8     HIGH (force model decompilation incomplete)
Input                  4     6-8     Low
Camera                 4     7-8     Low
Integration            8     8-10    MEDIUM (cross-module bugs)
Polish                 8    10-12    Low
```

**Critical blockers**:
1. **Block mesh extraction** (MVP-021): Block geometry lives in encrypted `.pak` files. NadeoImporter may not export built-in blocks. Highest-risk task.
2. **Physics force model** (MVP-040+): Only the CarSport model (case 5) is decompiled. CarRally and CarSnow are NOT decompiled. You can't drive those cars without the force model.
3. **GBX non-skippable chunks**: Unknown non-skippable chunks halt parsing. Must test against many real maps.

**My verdict**: 12 weeks is **optimistic but achievable** for a stripped-down MVP (one car type, placeholder block meshes, no multiplayer). Realistic estimate with mesh extraction risk: 16-20 weeks.

*Source: plan doc 08, risk register*

### Top 10 Architecture Lessons from TM2020

1. **State machines scale to 60+ states with coroutines.** The fiber/yield pattern keeps each state's logic self-contained. Without coroutines, this would be unmaintainable spaghetti.

2. **Two compression layers is normal.** LZO for the container, zlib for inner data. Different algorithms optimize for different data patterns.

3. **String interning saves enormous space.** A map with 1000 blocks uses maybe 100 unique block names. Interning turns 23-byte strings into 4-byte indices after first occurrence.

4. **The same binary should run client and server.** TM2020's headless mode flag (`DAT_141fbbee8`) eliminates an entire class of "works on client, breaks on server" bugs.

5. **Ghost != Physics Replay.** Visual ghosts (50ms, 22 bytes) and input replays (10ms, event-based) serve different purposes. Conflating them leads to wasted bandwidth or inaccurate playback.

6. **Authentication requires a proxy for browsers.** The UPC SDK is a Windows DLL. Any browser client needs a backend for the initial auth step. Plan for this from day one.

7. **File formats should be forward-compatible.** GBX's skippable chunk marker ("SKIP") lets old parsers skip new chunks. Every binary format needs this escape hatch.

8. **Profiling is infrastructure, not afterthought.** TM2020 allocates 75 profiling slots and a 128KB buffer at the very start of `WinMain`, before any game code runs. Performance measurement is baked into the engine's DNA.

9. **UI should not be coupled to the game engine.** ManiaLink is XML parsed and rendered by the engine. In a browser, HTML/CSS already IS the UI engine.

10. **562 networking classes is not overengineered -- it's layered.** Each layer (transport, services, facade, game logic) is independently testable. The web services task/result pattern gives type-safe async operations. Good architecture, just a LOT of it.

---

## Appendix: Key Data Flow Diagrams

### Map Load Data Flow

```
.Map.Gbx file (on disk)
    |
    v
[GBX Header Parse] -- magic, version, format flags, class ID
    |
    v
[Header Chunk Table] -- 6 chunks: map info, name, version, XML, thumbnail, author
    |
    v
[Reference Table] -- external file dependencies (max 49,999)
    |
    v
[LZO1X Decompress Body] -- uncompressed_size + compressed_size + data
    |
    v
[Body Chunk Stream] -- sequential chunks terminated by 0xFACADE01
    |
    +---> Chunk 0x03043011: Block Array (name, direction, coords, flags)
    +---> Chunk 0x0304301F: Block Params (version-dependent)
    +---> Chunk 0x03043040: Item Array (model, position, rotation, waypoint)
    +---> Chunk 0x0304300D: Vehicle Reference (CarSport, CarRally, etc.)
    +---> Chunk 0x0304304B: Medal Times (author, gold, silver, bronze)
    +---> Chunk 0x03043054: Embedded Items (nested GBX files)
    |
    v
[22-Stage Initialization Pipeline]
    |
    v
[Playable Map in Memory]
```

### Frame Execution Flow (Gameplay)

```
FRAME BEGIN (FUN_140117840)
  |-- increment global frame counter (DAT_141f9cfd0)
  |-- calculate delta time
  |-- begin "Total" profiling tag
  |
  v
GAME TICK (CGameCtnApp::UpdateGame, state 0xD45)
  |
  |-- INPUT (engine callback +0x70)
  |     read hardware state, dispatch to gameplay
  |
  |-- PHYSICS (inside arena client main loop)
  |     CSmArenaClient::MainLoop_* states
  |     fixed timestep, adaptive sub-stepping (up to 1000)
  |
  |-- SCRIPT (CScriptEngine::Run)
  |     bytecode interpreter FUN_1408d1ea0
  |     runs AFTER physics
  |
  |-- NETWORK (multiplayer only)
  |     BeforePhy -> [physics] -> AfterPhy -> Synchronize
  |
  |-- UI ENGINE (CControlEngine)
  |     7 phases: Layout, Effects, Focus, Values (x containers and controls)
  |
  v
RENDERING (engine callback +0x90)
  |-- NVisionCameraResourceMgr::StartFrame
  |-- Scene rendering (CVisionEngine, 19-pass deferred pipeline)
  |-- AllocateAndUploadTextures
  |-- BloomHdr post-process
  |-- Dxgi_Present (swap buffers)
  |
  v
ASYNC UPDATES (worker threads, concurrent)
  |-- NHmsLightMap::UpdateAsync
  |-- NSceneVFX::UpdateAsync
  |-- NSceneVehicleVis::UpdateAsync_PostCamera
  |-- CSmArenaClient::UpdateAsync
  |-- CGameManialinkBrowser::UpdateAsync
  |
  v
FRAME END (FUN_1401176a0)
  |-- record frame duration
  |-- budget check: 20ms outer, 10ms inner
```

### Authentication Data Flow

```
Browser Client          Auth Proxy (Node.js)      Ubisoft APIs              Nadeo APIs
     |                        |                       |                        |
     | 1. Login(email,pw)     |                       |                        |
     |----------------------->|                       |                        |
     |                        | 2. POST /v3/profiles/sessions                  |
     |                        |   Ubi-AppId: 86263886-...                      |
     |                        |   Authorization: Basic base64(email:pw)        |
     |                        |---------------------->|                        |
     |                        | 3. {ticket, sessionId}|                        |
     |                        |<----------------------|                        |
     |                        | 4. POST /v2/authentication/token/ubiservices   |
     |                        |   Authorization: ubi_v1 t=<ticket>             |
     |                        |------------------------------------------------>|
     |                        | 5. {accessToken (JWT), refreshToken}           |
     |                        |<------------------------------------------------|
     | 6. {accessToken}       |                       |                        |
     |<-----------------------|                       |                        |
     |                                                                         |
     | 7. GET /api/endpoint                                                    |
     |   Authorization: nadeo_v1 t=<accessToken>                               |
     |------------------------------------------------------------------------>|
```

---

## Related Pages

- [Architecture Deep Dive](../re/12-architecture-deep-dive.md) -- full engine subsystem analysis
- [File Format Deep Dive](../re/16-fileformat-deep-dive.md) -- GBX format specification
- [Networking Deep Dive](../re/17-networking-deep-dive.md) -- complete network stack analysis
- [Map Structure Encyclopedia](../re/28-map-structure-encyclopedia.md) -- block/item system details
- [Ghost/Replay Format](../re/30-ghost-replay-format.md) -- replay encoding details
- [ManiaScript Reference](../re/31-maniascript-reference.md) -- scripting engine internals
- [UI/ManiaLink Reference](../re/34-ui-manialink-reference.md) -- UI system details
- [Real File Analysis](../re/26-real-file-analysis.md) -- hex-verified file structure
- [Browser Recreation Guide](../re/20-browser-recreation-guide.md) -- translation strategies

---

**Final thought**: TM2020 is a 20-year-old engine (ManiaPlanet lineage traces to TrackMania Nations circa 2006) that has been continuously evolved. The architecture shows its age in places (integer state IDs, custom binary format, bespoke scripting language) but the core patterns (coroutine state machines, deterministic physics, dual-layer ghost system) are genuinely well-engineered. The challenge for a browser recreation is not "can we match the architecture?" but "where can we skip complexity by leveraging the browser platform?"

<details>
<summary>Document metadata</summary>

**Author**: Jordan (PhD student, game engine architecture)
**Date**: 2026-03-27
**Focus**: How everything CONNECTS -- data flow, state machines, lifecycle, and browser translation
**Method**: Read every decompiled function, every RE document, every plan document. Every claim is sourced.

</details>

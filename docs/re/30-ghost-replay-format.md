# Ghost & Replay Format Reference

**Date**: 2026-03-27
**Purpose**: Comprehensive reference for Trackmania 2020 ghost and replay file formats, covering file structure, sample encoding, input recording, checkpoint data, validation, network format, and implementation guidance.

**Sources**: Ghidra decompilation (doc 22), community knowledge (doc 29, GBX.NET), Openplanet intelligence (doc 19), GBX format spec (doc 16), real file hex analysis (doc 26), class hierarchy, and hex dumps of actual `.Replay.Gbx` files from the game.

---

## Table of Contents

1. [Overview: Ghost vs Replay vs InputReplay](#1-overview-ghost-vs-replay-vs-inputreplay)
2. [Class Hierarchy](#2-class-hierarchy)
3. [Replay File Structure (.Replay.Gbx)](#3-replay-file-structure-replaygbx)
4. [Replay Header Chunks](#4-replay-header-chunks)
5. [Replay Body Structure](#5-replay-body-structure)
6. [CGameCtnGhost Format](#6-cgamectnghost-format)
7. [Ghost Sample Encoding (50ms Period)](#7-ghost-sample-encoding-50ms-period)
8. [Input Recording Format (CInputReplay)](#8-input-recording-format-cinputreplay)
9. [Entity Record Data (CPlugEntRecordData)](#9-entity-record-data-cplugentrecorddata)
10. [Checkpoint Times & Validation Data](#10-checkpoint-times--validation-data)
11. [CGameCtnGhost vs CGameCtnReplayRecord Differences](#11-cgamectnghost-vs-cgamectnreplayrecord-differences)
12. [Ghost Playback & Interpolation](#12-ghost-playback--interpolation)
13. [Network Ghost Format](#13-network-ghost-format)
14. [Anti-Cheat & Replay Validation](#14-anti-cheat--replay-validation)
15. [Real File Hex Analysis](#15-real-file-hex-analysis)
16. [Browser TypeScript Implementation Guide](#16-browser-typescript-implementation-guide)
17. [Known Unknowns](#17-known-unknowns)
18. [Cross-References](#18-cross-references)

---

## 1. Overview: Ghost vs Replay vs InputReplay

Trackmania 2020 uses three distinct but related systems for recording and playing back race data:

| Concept | File Extension | Class | Purpose |
|---------|---------------|-------|---------|
| **Ghost** | `.Ghost.Gbx` | `CGameCtnGhost` | Visual replay: position/rotation/visual state sampled at 50ms intervals |
| **Replay** | `.Replay.Gbx` | `CGameCtnReplayRecord` | Complete package: ghost(s) + embedded map + metadata |
| **Input Replay** | `.InputsReplay.Gbx` | `CInputReplay` | Deterministic replay: raw input events at 100Hz tick rate |

**Key distinction**: Ghosts store sampled visual state (position, rotation, speed) for rendering. Input replays store raw inputs (steer, gas, brake) for deterministic re-simulation. A replay file bundles one or more ghosts plus the map itself, forming a self-contained package.

**Confidence**: VERIFIED -- class names from binary RTTI, file extensions from string table, architecture from decompilation.

### Recording Pipeline

```
During gameplay:
  1. CInputReplay captures raw input each simulation tick (100 Hz)
  2. CPlugEntRecordData stores entity state samples (position, rotation, speed)
  3. CGameCtnGhost / CGameGhostTMData wraps ghost-specific metadata
  4. CGhostManager manages active ghost instances
  5. CGameCtnReplayRecord bundles ghost(s) + map reference + times + metadata
```

---

## 2. Class Hierarchy

**Source**: Binary RTTI extraction (class_hierarchy.json), Ghidra string analysis (doc 22)
**Confidence**: VERIFIED

### Core Classes

```
CMwNod
  +-- CGameCtnGhost              -- Ghost data (sampled car state)
  |     Class ID: 0x03092000 (from GBX.NET / community)
  |     String address: 0x141c5e3c8
  |
  +-- CGameCtnReplayRecord       -- Complete replay record
  |     Class ID: 0x03093000
  |     String address: 0x141c49c50
  |
  +-- CGameCtnReplayRecordInfo   -- Replay metadata
  |     String address: 0x141bf98b0
  |
  +-- CGameGhost                 -- Base ghost object
  +-- CGameGhostTMData           -- TrackMania-specific ghost data
  +-- CGameGhostMgrScript        -- Ghost manager script API
  +-- CGameGhostScript           -- Ghost script interface
  +-- CGhostManager              -- Ghost lifecycle manager
  |     String address: 0x141bfb480
  |
  +-- CReplayInfo                -- Replay file info
  +-- CGameReplayObjectVisData   -- Replay object visual data
  |     String address: 0x141c6e7e8
  |
  +-- CPlugEntRecordData         -- Entity record data (raw ghost frames)
  |     String address: 0x141bcb440
  |
  +-- CInputReplay               -- Input recording/playback
  |     String address: 0x141b6dd98
  |
  +-- CPlugSimuDump              -- Simulation state dump
  +-- CGameSaveLaunchedCheckpoints -- Checkpoint state saves during run
```

### Ghost Member Variables (from `m_Ghost*` strings)

| Member | Description |
|--------|-------------|
| `m_GhostLogin` | Player login identifier |
| `m_GhostTrigram` | 3-letter country trigram |
| `m_GhostCountryPath` | Full country/zone path |
| `m_GhostNickname` | Display name |
| `m_GhostNameLogoType` | Name logo type identifier |
| `m_GhostAvatarName` | Avatar asset identifier |

### Ghost API Functions (27 ManiaScript-exposed)

| Function | Purpose |
|----------|---------|
| `Ghost_Add` | Add ghost to scene |
| `Ghost_AddWaypointSynced` | Add ghost synchronized to waypoints |
| `Ghost_AddPhysicalized` | Add ghost with physics interaction |
| `Ghost_Remove` | Remove specific ghost |
| `Ghost_RemoveAll` | Remove all ghosts |
| `Ghost_IsVisible` | Query ghost visibility |
| `Ghost_IsReplayOver` | Check if replay playback finished |
| `Ghost_SetDossard` | Set ghost's number bib |
| `Ghost_SetMarker` | Set ghost's UI marker |
| `Ghost_GetPosition` | Get ghost's 3D position |
| `Ghost_RetrieveFromPlayer` | Capture ghost from live player |
| `Ghost_RetrieveFromPlayer2` | Capture ghost (v2 API) |
| `Ghost_GetLiveFromPlayer` | Get live ghost stream from player |
| `Ghost_GetTimeClosestToPlayer` | Find closest time comparison point |
| `Ghost_CopyToScoreBestRaceAndLap` | Transfer checkpoint/lap times to score |
| `Ghost_Upload` | Upload ghost to server |
| `Ghost_Download` | Download ghost from server |
| `Ghost_Release` | Release ghost resources |

**Confidence**: VERIFIED -- all 27 function names extracted from binary string table.

---

## 3. Replay File Structure (.Replay.Gbx)

### File Layout

Replay files follow the standard GBX format (version 6) with class ID `0x03093000` (CGameCtnReplayRecord).

```
+=======================================+
| GBX HEADER                            |
|   Magic: "GBX" (3 bytes)             |
|   Version: 6 (uint16)                |
|   Format: "BUCR" (4 bytes)           |
|   Class ID: 0x03093000               |
|   User Data Size (uint32)            |
|   3 Header Chunks                     |
+=======================================+
| NODE COUNT (uint32)                   |
+=======================================+
| REFERENCE TABLE                       |
|   External refs (usually 0)          |
+=======================================+
| BODY SECTION (compressed)             |
|   Uncompressed Size (uint32)         |
|   Compressed Size (uint32)           |
|   LZO-compressed body chunks:        |
|     Embedded map (.Map.Gbx)          |
|     Ghost data (CGameCtnGhost)       |
|     Input replay data                |
|     Checkpoint times                 |
|     Validation metadata              |
|     0xFACADE01 end sentinel          |
+=======================================+
```

**Confidence**: VERIFIED -- real file analysis confirms class ID, format flags, header structure.

### Real File Evidence

From `ReallyRally_Kelvination_1-18-2026...Replay.Gbx` (4,388,346 bytes):

```
Offset  Bytes              Field                    Value
------  -----              -----                    -----
0x00    47 42 58           magic                    "GBX"
0x03    06 00              version                  6
0x05    42 55 43 52        format_flags             "BUCR"
0x09    00 30 09 03        class_id                 0x03093000 (CGameCtnReplayRecord)
0x0D    C1 02 00 00        user_data_size           705 bytes
0x11    03 00 00 00        num_header_chunks        3
```

### Embedded Map

The replay body contains a complete embedded `.Map.Gbx` file. At offset 0x2E4 in the ReallyRally replay, a nested GBX header appears:

```
000002e0: ...  47 42 5806 00    Nested "GBX" magic + version 6
000002f0: 4255 4352 0030 0403  "BUCR" + class 0x03043000 (CGameCtnChallenge)
```

This means every replay is self-contained -- it carries its own copy of the map, so the replay can be viewed without having the original map installed.

---

## 4. Replay Header Chunks

Replay files have exactly 3 header chunks.

### Header Chunk Index

| Index | Chunk ID | Size | Heavy? | Content |
|-------|----------|------|--------|---------|
| 0 | `0x03093000` | variable | No | Replay info (version, map UID, author) |
| 1 | `0x03093001` | variable | Yes | XML metadata |
| 2 | `0x03093002` | 82 bytes | No | Author info |

**Verification**: user_data_size = 4 + 3*8 + sum(chunk_sizes). For ReallyRally: 4 + 24 + (140 + 455 + 82) = 705 = 0x02C1. **CONFIRMED**.

### Chunk 0x03093000: Replay Info

```
Offset  Type      Field
------  ----      -----
+0x00   uint32    version              (observed: 8)
+0x04   uint32    [UNKNOWN]            (observed: 3)
+0x08   uint32    [UNKNOWN]            (observed: 0)
+0x0C   uint32    lookback_version     (0x40000000 = version 3)
+0x10   string    map_uid              (length-prefixed, e.g., "gEpyZSp892q6BVU3t98ycuUugKl")
        string    map_author_login     (lookback string)
```

### Chunk 0x03093001: XML Metadata (Heavy)

Contains human-readable XML with full replay metadata:

```xml
<header type="replay" exever="3.3.0" exebuild="2025-07-04_14_15" title="TMStadium">
  <map uid="gEpyZSp892q6BVU3t98ycuUugKl" name="ReallyRally"
       author="XChwDu8FRmWH-gHqXUbBtg" authorzone="World|Africa|South Africa"/>
  <desc envir="Stadium" mood="Day (no stadium)" maptype="TrackMania\TM_Race"
        mapstyle="" displaycost="5672" mod=""/>
  <playermodel id="CarRally"/>
  <times best="38401" respawns="0" stuntscore="0" validable="1"/>
  <checkpoints cur="8"/>
</header>
```

**Key fields**:
- `best`: Race time in milliseconds (38401 = 38.401s)
- `respawns`: Number of respawns during run
- `validable`: 1 if the run is valid for leaderboards
- `checkpoints cur`: Number of checkpoint times recorded
- `playermodel id`: Vehicle type used ("CarSport", "CarRally", "CarSnow", "CarDesert")

### Chunk 0x03093002: Author Info

```
Offset  Type      Field
------  ----      -----
+0x00   uint32    version              (observed: 1)
+0x04   string    author_login         ("XChwDu8FRmWH-gHqXUbBtg")
+0x??   string    author_nickname      ("Kelvination")
+0x??   string    author_zone          ("World|Africa|South Africa")
```

**Confidence**: VERIFIED from real file hex dumps. All autosave and manual save replays share this exact structure.

---

## 5. Replay Body Structure

The replay body is LZO-compressed (format flag byte 2 = 'C'). After decompression, it contains a stream of body chunks belonging to the `CGameCtnReplayRecord` class (chunk IDs 0x0309300X).

### Known Body Chunks (from GBX.NET / Community)

| Chunk ID | Content | Skippable? |
|----------|---------|------------|
| `0x03093002` | Map embedded data / map reference | [UNKNOWN] |
| `0x03093003` | Ghost data (embedded CGameCtnGhost) | [UNKNOWN] |
| `0x03093004` | [UNKNOWN] | [UNKNOWN] |
| `0x03093005` | [UNKNOWN] | [UNKNOWN] |
| `0x03093007` | [UNKNOWN] | [UNKNOWN] |
| `0x03093008` | Title UID ("TMStadium") | [UNKNOWN] |
| `0x03093014` | Ghost(s) array | [UNKNOWN] |
| `0x03093015` | Clip / MediaTracker data | [UNKNOWN] |
| `0x0309301C` | [UNKNOWN] | [UNKNOWN] |

**Note**: Chunk ID assignment is derived from GBX.NET source code analysis. The exact semantics of each chunk require decompilation of the chunk dispatch handlers, which has not been completed. The body is compressed, making direct hex analysis of chunk boundaries difficult without decompression.

### Body Content Summary

The replay body contains:
1. **Embedded map** -- A complete `.Map.Gbx` (visible as nested "GBX" magic in hex)
2. **One or more ghosts** -- `CGameCtnGhost` instances with sampled data
3. **Checkpoint times** -- Array of millisecond timestamps
4. **Validation data** -- Race validity flags
5. **Title/environment info** -- e.g., "TMStadium"
6. **Extras** -- Plugin metadata (e.g., "Openplanet 1.28.0"), game version strings

### Evidence from File Tail

The end of the ReallyRally replay (at offset ~0x42F500) contains:

```
"ebc2b176b45 GameVersion=3.3.0"
"Openplanet 1.28.0 (next, Public, ...8-16)"
"TMStadium"
"Kelvination"
"_RaceValid"
"_Local"
```

These strings confirm that replays embed game version, plugin info, environment, player name, and validation status directly in the body.

---

## 6. CGameCtnGhost Format

### Class ID

**Community (GBX.NET)**: `0x03092000`
**Binary evidence**: String at `0x141c5e3c8`
**Confidence**: HIGH (from GBX.NET, which successfully parses these files)

### Ghost Chunk IDs (from GBX.NET)

| Chunk ID | Content | Notes |
|----------|---------|-------|
| `0x03092000` | Race time + ghost data | Core ghost data |
| `0x03092002` | [UNKNOWN - appears in older versions] | |
| `0x03092005` | Race time (uint32, milliseconds) | |
| `0x03092006` | [UNKNOWN] | |
| `0x03092008` | Ghost login | Player identifier |
| `0x0309200A` | [UNKNOWN] | |
| `0x0309200B` | Light trail color / car skin | |
| `0x0309200C` | Checkpoint times array | |
| `0x0309200E` | UID + player data | Ghost metadata |
| `0x0309200F` | Ghost nickname / display name | |
| `0x03092010` | Ghost avatar | |
| `0x03092012` | Record data (CPlugEntRecordData) | The actual sampled frames |
| `0x03092013` | [UNKNOWN] | |
| `0x03092015` | [UNKNOWN - newer version] | |
| `0x03092017` | Player model (vehicle type) | |
| `0x03092018` | Player inputs (event-based) | |
| `0x03092019` | Validation data | |
| `0x0309201C` | [UNKNOWN] | |

**Confidence**: PLAUSIBLE -- chunk IDs from GBX.NET source analysis. Not verified against Ghidra decompilation of chunk dispatch.

### Ghost Data Composition

A ghost contains:

1. **Metadata**: Player login, nickname, avatar, country zone
2. **Race result**: Total time (ms), checkpoint times, validation status
3. **Sampled visual data**: Position/rotation/speed at 50ms intervals (via `CPlugEntRecordData`)
4. **Input events**: Discrete input changes (steer/gas/brake state transitions)
5. **Vehicle model**: Which car was used (CarSport, CarRally, CarSnow, CarDesert)

---

## 7. Ghost Sample Encoding (50ms Period)

**Source**: Community knowledge (doc 29, section 6.2), GBX.NET source
**Confidence**: HIGH -- community tools successfully parse ghosts using this encoding

### Sample Period

Ghost samples are recorded at **50ms intervals** (20 samples per second). This is much lower than the physics tick rate of 100Hz (10ms), reflecting that ghosts are for visual playback, not deterministic re-simulation.

### Per-Sample Fields

Each ghost sample encodes the following state:

| Field | Type | Size | Encoding | Range |
|-------|------|------|----------|-------|
| Position X | float32 | 4 bytes | IEEE 754 | World coordinates (meters) |
| Position Y | float32 | 4 bytes | IEEE 754 | World coordinates (meters) |
| Position Z | float32 | 4 bytes | IEEE 754 | World coordinates (meters) |
| Angle | uint16 | 2 bytes | Linear: `value / 0xFFFF * pi` | 0 to pi |
| Axis Heading | int16 | 2 bytes | Linear: `value / 0x7FFF * pi` | -pi to pi |
| Axis Pitch | int16 | 2 bytes | Linear: `value / 0x7FFF * (pi/2)` | -pi/2 to pi/2 |
| Speed | int16 | 2 bytes | Exponential: `exp(value / 1000)` | Special: 0x8000 = speed 0 |
| Velocity Heading | int8 | 1 byte | Linear: `value / 0x7F * pi` | -pi to pi |
| Velocity Pitch | int8 | 1 byte | Linear: `value / 0x7F * (pi/2)` | -pi/2 to pi/2 |

### Sample Size

Per sample: 3 * 4 (position) + 2 (angle) + 2 (heading) + 2 (pitch) + 2 (speed) + 1 (vel heading) + 1 (vel pitch) = **22 bytes** uncompressed per sample.

### Compression

Ghost sample data is **zlib-compressed** (deflate), not LZO like the outer GBX body. This means there are two compression layers:

1. **Outer**: GBX body compression (LZO)
2. **Inner**: Ghost sample data compression (zlib deflate)

### Encoding Details

**Rotation representation**: The rotation uses an axis-angle representation rather than quaternion or Euler angles. The angle field gives the rotation magnitude, while heading and pitch define the rotation axis direction in spherical coordinates.

**Speed encoding**: The exponential encoding `exp(value/1000)` allows compact representation of both slow and fast speeds. When `value == 0x8000` (-32768 as signed), the speed is defined as exactly 0. The exponential curve means small integer differences at low speeds map to small velocity differences, while the same integer step at high speeds maps to larger velocity differences -- matching the perceptual importance.

**Integer precision**:
- int16 heading/pitch: ~0.0001 radian precision (~0.006 degrees) -- sufficient for smooth visual playback
- int8 velocity heading/pitch: ~0.025 radian precision (~1.4 degrees) -- coarser, since velocity direction is less visually critical
- uint16 angle: ~0.00005 radian precision (~0.003 degrees)

### Decoding Pseudocode

```typescript
function decodeSample(reader: BinaryReader): GhostSample {
  const posX = reader.readFloat32();
  const posY = reader.readFloat32();
  const posZ = reader.readFloat32();

  const angleRaw = reader.readUint16();
  const headingRaw = reader.readInt16();
  const pitchRaw = reader.readInt16();
  const speedRaw = reader.readInt16();
  const velHeadingRaw = reader.readInt8();
  const velPitchRaw = reader.readInt8();

  return {
    position: { x: posX, y: posY, z: posZ },
    angle: (angleRaw / 0xFFFF) * Math.PI,
    axisHeading: (headingRaw / 0x7FFF) * Math.PI,
    axisPitch: (pitchRaw / 0x7FFF) * (Math.PI / 2),
    speed: speedRaw === -0x8000 ? 0 : Math.exp(speedRaw / 1000),
    velocityHeading: (velHeadingRaw / 0x7F) * Math.PI,
    velocityPitch: (velPitchRaw / 0x7F) * (Math.PI / 2),
  };
}
```

### For a 38-Second Replay

At 50ms per sample: `38000 / 50 = 760 samples`. At 22 bytes each: `760 * 22 = 16,720 bytes` uncompressed. After zlib compression, this would typically reduce to ~5-10 KB, which is consistent with observed ghost data sizes within replay files.

---

## 8. Input Recording Format (CInputReplay)

**Source**: Ghidra string analysis (doc 22), class hierarchy, community knowledge
**Confidence**: PARTIAL -- architecture confirmed, exact binary format [UNKNOWN]

### Overview

`CInputReplay` (string at `0x141b6dd98`) handles deterministic input recording at the full physics tick rate of 100Hz. This is separate from the ghost visual data.

### Input Replay Operations

| Operation | Purpose |
|-----------|---------|
| `InputsReplay_Record` | Begin recording inputs |
| `InputsReplay_Replay` | Enter replay mode |
| `InputsReplay_Playback` | Play back recorded inputs |
| `InputsReplay_Pause` | Pause playback |
| `InputsReplay_Resume` | Resume playback |
| `InputsReplay_Stop` | Stop recording/playback |

### Input Fields Recorded

From the `CSceneVehicleVisState` (doc 19), the inputs that define a complete game state are:

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `InputSteer` | float | -1.0 to 1.0 | Steering (normalized from raw int range -65536 to 65536) |
| `InputGasPedal` | float | 0.0 to 1.0 | Throttle |
| `InputBrakePedal` | float | 0.0 to 1.0 | Brake |
| `InputIsBraking` | bool | 0 or 1 | Braking state |

### Raw Integer Input Range

**Community (TMInterface / donadigo)**: Raw input values are integers:
- Steering: -65536 to 65536 (signed, 17-bit effective)
- Gas: 0 to 65535 (unsigned, 16-bit)
- Brake: 0 to 65535 (unsigned, 16-bit)

The conversion from raw integer to normalized float is: `float_value = int_value / 65536.0`

### Binary Format [UNKNOWN]

The exact on-disk encoding of `CInputReplay` data has not been decompiled. Based on the architecture, it likely uses:

- **Event-based encoding**: Only state changes are stored (e.g., "at tick 150, steer changed to 0.5") rather than every tick
- **Delta encoding**: [UNKNOWN] whether consecutive input values are delta-encoded
- **Compression**: Likely zlib (consistent with ghost data compression)

The file extension `.InputsReplay.Gbx` (string at `0x141cccef0`) suggests these can be stored as standalone GBX files, though they are typically embedded within replay files.

---

## 9. Entity Record Data (CPlugEntRecordData)

**Source**: Class hierarchy, Ghidra string analysis
**Confidence**: PARTIAL -- class identified and role confirmed, internal format [UNKNOWN]

### Role

`CPlugEntRecordData` (string at `0x141bcb440`, class from the Plug engine 0x09) is the low-level container for recorded entity state frames. It is referenced by ghost chunk `0x03092012` in the GBX.NET source.

This class stores the raw sampled state data that gets encoded into the ghost sample format (Section 7). The relationship is:

```
CGameCtnGhost
  +-- metadata (login, nickname, times)
  +-- CPlugEntRecordData  (chunk 0x03092012)
      +-- sample_count
      +-- sample_period (50ms)
      +-- compressed_data (zlib)
          +-- sample[0]: {position, rotation, speed, ...}
          +-- sample[1]: ...
          +-- sample[N]: ...
```

### Duplication/Truncation

The function `NGameReplay::EntRecordDataDuplicateAndTruncate` (string at `0x141c66e28`) confirms that entity record data can be:
- **Duplicated**: Copied for sharing/upload
- **Truncated**: Cut to a specific time point (e.g., for partial replays up to a checkpoint)

---

## 10. Checkpoint Times & Validation Data

### Checkpoint Times Array

Ghost chunk `0x0309200C` stores checkpoint times as an array of uint32 values in milliseconds.

From the XML header of the ReallyRally replay:
```xml
<times best="38401" respawns="0" stuntscore="0" validable="1"/>
<checkpoints cur="8"/>
```

This indicates 8 checkpoint times for a 38.401-second run.

### Checkpoint Data Structure [PARTIAL]

```
uint32    num_checkpoints        Number of checkpoint times
uint32[]  checkpoint_times       Array of times in milliseconds (cumulative from race start)
```

For the ReallyRally replay, checkpoint times would be something like:
```
CP 1: ~4800ms
CP 2: ~9600ms
...
CP 8: 38401ms (finish)
```

The last checkpoint time equals the total race time (`best` in the XML).

### Validation Status

| Field | XML Attribute | Values | Meaning |
|-------|--------------|--------|---------|
| Validable | `validable="1"` | 0 or 1 | Whether the run counts for records |
| Respawns | `respawns="0"` | uint32 | Number of times the player respawned |
| Stunt Score | `stuntscore="0"` | uint32 | Stunt-mode score (unused in Race mode) |

### CGameSaveLaunchedCheckpoints

The class `CGameSaveLaunchedCheckpoints` handles saving checkpoint state during a run, enabling respawns. When a player triggers a checkpoint:

1. The current simulation state is captured
2. The time is recorded in the checkpoint array
3. If the player later respawns, state is restored to the last checkpoint

**Ghost recording**: Checkpoint events are embedded in the ghost data alongside position samples. The `Ghost_CopyToScoreBestRaceAndLap` API function transfers these times to the score system.

---

## 11. CGameCtnGhost vs CGameCtnReplayRecord Differences

### Structural Comparison

| Feature | CGameCtnGhost (0x03092000) | CGameCtnReplayRecord (0x03093000) |
|---------|---------------------------|-----------------------------------|
| **Purpose** | Single driver's recorded run | Complete replay package |
| **Contains map?** | No -- references map by UID | Yes -- embeds complete `.Map.Gbx` |
| **Number of ghosts** | Is a ghost (1 driver) | Contains 1+ ghosts |
| **Standalone file?** | `.Ghost.Gbx` | `.Replay.Gbx` |
| **Metadata** | Player info, times, checkpoints | All ghost metadata + map metadata |
| **Self-contained?** | No (needs map to display) | Yes (can be viewed without original map) |
| **Header chunks** | [UNKNOWN count] | 3 header chunks |
| **XML in header?** | [UNKNOWN] | Yes (chunk 0x03093001) |

### When Each Is Used

| Context | Format Used |
|---------|-------------|
| Autosave after completing a map | `.Replay.Gbx` (autosaves directory) |
| Manual save of a run | `.Replay.Gbx` (My Replays directory) |
| Downloading a leaderboard ghost | `.Ghost.Gbx` or ghost data via API |
| Multiplayer ghost display | Network ghost format (streamed) |
| Ghost upload for validation | Ghost data (embedded in replay) |
| MediaTracker replay | `.Replay.Gbx` (for camera/effects) |

### File Paths

```
Replays/
  My Replays/         -- Manual saves (*.Replay.Gbx)
  Autosaves/          -- Auto-saved PBs (*_PersonalBest_TimeAttack.Replay.Gbx)
  Downloaded/         -- Downloaded replays
```

---

## 12. Ghost Playback & Interpolation

### Rendering Ghost Cars

When displaying a ghost, the game:

1. Determines the current playback time
2. Finds the two nearest ghost samples (at 50ms intervals)
3. Interpolates between them for the current frame

### Interpolation Method [PARTIAL]

Given the 50ms sample period and typical 60+ FPS rendering, interpolation is needed for smooth display. Based on the data fields available:

**Position**: Linear interpolation between consecutive sample positions. At 50ms intervals and typical car speeds (~100-500 km/h), the maximum positional error from linear interpolation is small (< 1 meter) and visually acceptable.

**Rotation**: Likely spherical linear interpolation (slerp) of the axis-angle representation, or conversion to quaternion followed by slerp.

**Speed**: Linear interpolation of the decoded speed value.

**Velocity direction**: Linear interpolation of heading/pitch angles.

### Entity ID Masking

Ghost/replay vehicles are identified by entity ID mask:
- `0x02000000` -- Local player vehicles
- `0x04000000` -- Replay/editor vehicles

This allows the rendering system to distinguish live players from ghost playback.

### Playback API

| Function | Description |
|----------|-------------|
| `Ghost_IsReplayOver` | Returns true when playback reaches the end |
| `Ghost_GetPosition` | Returns interpolated 3D position at current time |
| `Ghost_GetTimeClosestToPlayer` | Finds the ghost time nearest to the live player's time |
| `Ghost_IsVisible` | Whether the ghost car is currently rendered |

---

## 13. Network Ghost Format

**Source**: Networking deep dive (doc 17), Ghidra string analysis (doc 22)
**Confidence**: PARTIAL

### Ghost Data Flow (Online)

```
Local Recording:
  CInputReplay captures every input frame (100 Hz)
  CGameGhostTMData stores TM-specific metadata
  CGameCtnGhost wraps with car/map context

Upload (on PB or request):
  CWebServicesTask_UploadSessionReplay      -- Full replay upload
  CGameDataFileTask_GhostDriver_Upload      -- Ghost-specific upload
  CGameDataFileTask_GhostDriver_UploadLimits -- Upload size limits

Download:
  CGameDataFileTask_GhostDriver_Download    -- Download ghost
  CGameScoreTask_GetPlayerMapRecordGhost    -- Get PB ghost for a map

Ghost Management:
  CGhostManager handles lifecycle
  CGameGhostMgrScript exposes to ManiaScript
```

### Anti-Cheat Upload

Replays for leaderboard validation are uploaded in chunks:

| Config Parameter | Address | Purpose |
|-----------------|---------|---------|
| `AntiCheatReplayChunkSize` | `0x141c2af98` | Size per upload chunk |
| `AntiCheatReplayMaxSize` | `0x141c2afe0` | Maximum total upload |
| `AntiCheatReplayMaxSizeOnCheatReport` | `0x141c2afb8` | Increased limit on cheat reports |
| `UploadAntiCheatReplayForcedOnCheatReport` | `0x141c2b118` | Force upload when cheat detected |

### Secure Record Attempt Flow

```
1. POST  CreateMapRecordSecureAttempt      -- Get attempt token
2. Player completes the map
3. PATCH PatchMapRecordSecureAttempt       -- Submit ghost + result
4. Upload UploadSessionReplay              -- Full replay for validation
5. Server replays inputs, verifies time matches
```

### Multiplayer Ghost Streaming [UNKNOWN]

During online play, ghost positions of other players are likely sent via:
- `CGameNetFormPlayground` over UDP
- `CGameNetFormPlaygroundSync` for input synchronization
- Reduced sample rate compared to 100Hz physics (likely position updates at 10-20Hz)

The exact wire format for multiplayer ghost streaming is [UNKNOWN].

---

## 14. Anti-Cheat & Replay Validation

### Server-Side Validation

**Source**: Doc 17 section on validation, doc 22 anti-cheat strings
**Confidence**: VERIFIED (string-level), binary format [UNKNOWN]

The server validates replays by:

1. **Receiving** the uploaded replay (ghost data + input recording)
2. **Re-simulating** the run using the input recording against deterministic physics
3. **Comparing** the resulting time against the client's claimed time
4. **Checking** for impossible physics states (wall clipping, etc.)
5. **Verifying** client file checksums against known-good hashes

### Encrypted Package System

Replays include cryptographic integrity data:
- Session replay with encrypted checksums
- Chunk-based upload with size limits
- Forced upload on cheat detection reports
- Game file checksum comparison (`CryptedChecksumsExe`)

### What Makes a Run "Validable"

From the XML header: `validable="1"` means the run is eligible for leaderboard submission. A run becomes non-validable if:
- The player used editor test mode
- Game modifications were detected
- The map was modified during the run
- [UNKNOWN] Other anti-cheat triggers

---

## 15. Real File Hex Analysis

### File Comparison: Two Replay Files

| Property | ReallyRally (Rally car) | Fall 2025 - 07 (Stadium car) |
|----------|------------------------|-------------------------------|
| File size | 4,388,346 bytes | Smaller (Nadeo map, less items) |
| Class ID | `0x03093000` | `0x03093000` |
| Format flags | `BUCR` | `BUCR` |
| Version | 6 | 6 |
| Header chunks | 3 | 3 |
| Player model | `CarRally` | `CarSport` |
| Best time | 38401 ms | 29646 ms |
| Checkpoints | 8 | 5 |
| Map author | `XChwDu8FRmWH-gHqXUbBtg` (user) | `Nadeo` |

### Header Layout Consistency

Both replay files show identical structural layout:

```
Byte 0x00: Magic "GBX"
Byte 0x03: Version 6
Byte 0x05: "BUCR"
Byte 0x09: Class 0x03093000
Byte 0x0D: user_data_size (varies)
Byte 0x11: num_header_chunks = 3
Byte 0x15: Chunk index [0x03093000, 0x03093001, 0x03093002]
```

### Body Region

The body starts after the reference table (typically at the offset just past the header data). For the ReallyRally replay:

```
After header + reference table:
  Uncompressed body contains embedded map starting with nested "GBX" magic
  Map class 0x03043000 (CGameCtnChallenge) visible at offset ~0x2E4

  Ghost/replay data follows the map in the body chunk stream

  File tail contains:
    Game version string: "GameVersion=3.3.0"
    Plugin info: "Openplanet 1.28.0 (next, Public, ...)"
    Environment: "TMStadium"
    Player name: "Kelvination"
    Validation marker: "_RaceValid"
    End sentinel: 0xFACADE01 (01 DE CA FA in LE)
```

### Embedded Map Evidence

At offset 0x2E4 in the ReallyRally replay:

```
000002e0: ...4742 5806 00       "GBX" version 6
000002f0: 4255 4352 0030 0403   "BUCR" class 0x03043000 (Map)
...
00000310: ...4361 7252 616c 6c   "CarRally" (vehicle model in map)
00000320: 7913 27ac ...
00000330: ...4e 6164 656f        "Nadeo" (map collection author)
```

The map embedded in the replay is the complete, playable map data.

---

## 16. Browser TypeScript Implementation Guide

### Recommended Approach

For a browser recreation, use **input-based deterministic replay** rather than parsing the complex ghost sample format.

### Strategy 1: Simple Input Recording (Recommended for Custom Replays)

```typescript
interface InputFrame {
  tick: number;           // Physics tick number (100 Hz)
  steer: number;          // -1.0 to 1.0
  gas: number;            // 0.0 to 1.0
  brake: number;          // 0.0 to 1.0
}

interface SimpleReplay {
  mapUid: string;
  playerName: string;
  vehicleType: 'CarSport' | 'CarRally' | 'CarSnow' | 'CarDesert';
  finishTime: number;     // milliseconds
  checkpoints: number[];  // cumulative ms timestamps
  inputs: InputFrame[];   // only store state changes
}
```

Recording: only store an `InputFrame` when any input value changes. For a typical 38-second run, this produces ~200-500 events (far less than 3,800 ticks).

Playback: feed recorded inputs into the deterministic physics engine at 100Hz. If the physics is bit-identical, the replay is exact.

### Strategy 2: Parsing Official TM2020 Ghosts (Advanced)

To load official `.Replay.Gbx` files, the parser must:

```typescript
class ReplayParser {
  // Step 1: Parse GBX header
  parseGbxHeader(buffer: ArrayBuffer): GbxHeader {
    const view = new DataView(buffer);
    const magic = String.fromCharCode(
      view.getUint8(0), view.getUint8(1), view.getUint8(2)
    );
    if (magic !== 'GBX') throw new Error('Not a GBX file');

    const version = view.getUint16(3, true);
    const formatFlags = String.fromCharCode(
      view.getUint8(5), view.getUint8(6), view.getUint8(7), view.getUint8(8)
    );
    const classId = view.getUint32(9, true);
    const userDataSize = view.getUint32(13, true);

    return { version, formatFlags, classId, userDataSize };
  }

  // Step 2: Parse header chunks for metadata
  parseHeaderChunks(buffer: ArrayBuffer, offset: number, count: number): HeaderChunk[] {
    const view = new DataView(buffer);
    const chunks: HeaderChunk[] = [];
    let pos = offset;

    // Read chunk index
    for (let i = 0; i < count; i++) {
      const chunkId = view.getUint32(pos, true); pos += 4;
      const rawSize = view.getUint32(pos, true); pos += 4;
      const isHeavy = (rawSize & 0x80000000) !== 0;
      const size = rawSize & 0x7FFFFFFF;
      chunks.push({ chunkId, size, isHeavy });
    }

    // Read chunk data
    for (const chunk of chunks) {
      chunk.data = new Uint8Array(buffer, pos, chunk.size);
      pos += chunk.size;
    }

    return chunks;
  }

  // Step 3: Extract XML metadata from chunk 0x03093001
  parseXmlMetadata(chunkData: Uint8Array): ReplayMetadata {
    const decoder = new TextDecoder();
    // Find XML start (after version + length prefix)
    // The XML is embedded directly in the chunk data
    const text = decoder.decode(chunkData);
    const xmlStart = text.indexOf('<header');
    const xmlEnd = text.indexOf('</header>') + '</header>'.length;
    const xml = text.substring(xmlStart, xmlEnd);
    // Parse with DOMParser
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'text/xml');
    return this.extractMetadata(doc);
  }

  // Step 4: Decompress body (LZO)
  decompressBody(buffer: ArrayBuffer, bodyOffset: number): ArrayBuffer {
    const view = new DataView(buffer);
    const uncompressedSize = view.getUint32(bodyOffset, true);
    const compressedSize = view.getUint32(bodyOffset + 4, true);
    const compressedData = new Uint8Array(buffer, bodyOffset + 8, compressedSize);
    return lzoDecompress(compressedData, uncompressedSize); // Need LZO library
  }

  // Step 5: Parse body chunks
  parseBodyChunks(bodyData: ArrayBuffer): void {
    const view = new DataView(bodyData);
    let pos = 0;

    while (pos < bodyData.byteLength) {
      const chunkId = view.getUint32(pos, true);
      pos += 4;

      if (chunkId === 0xFACADE01) break; // End sentinel

      // Check for SKIP marker
      const possibleSkip = view.getUint32(pos, true);
      if (possibleSkip === 0x534B4950) { // "SKIP"
        pos += 4;
        const chunkSize = view.getUint32(pos, true);
        pos += 4;
        // Can skip unknown chunks by advancing pos += chunkSize
        pos += chunkSize;
      } else {
        // Non-skippable chunk -- must understand format to continue
        throw new Error(`Unknown non-skippable chunk: 0x${chunkId.toString(16)}`);
      }
    }
  }

  // Step 6: Decode ghost samples (from zlib-compressed CPlugEntRecordData)
  decodeGhostSamples(compressedData: Uint8Array): GhostSample[] {
    const decompressed = pako.inflate(compressedData); // zlib decompression
    const view = new DataView(decompressed.buffer);
    const samples: GhostSample[] = [];
    let pos = 0; // [UNKNOWN]: may have header before samples

    while (pos + 22 <= decompressed.byteLength) {
      samples.push({
        position: {
          x: view.getFloat32(pos, true),
          y: view.getFloat32(pos + 4, true),
          z: view.getFloat32(pos + 8, true),
        },
        angle: (view.getUint16(pos + 12, true) / 0xFFFF) * Math.PI,
        axisHeading: (view.getInt16(pos + 14, true) / 0x7FFF) * Math.PI,
        axisPitch: (view.getInt16(pos + 16, true) / 0x7FFF) * (Math.PI / 2),
        speed: decodeSpeed(view.getInt16(pos + 18, true)),
        velHeading: (view.getInt8(pos + 20) / 0x7F) * Math.PI,
        velPitch: (view.getInt8(pos + 21) / 0x7F) * (Math.PI / 2),
      });
      pos += 22;
    }
    return samples;
  }
}

function decodeSpeed(raw: number): number {
  if (raw === -0x8000) return 0;
  return Math.exp(raw / 1000);
}
```

### Required External Libraries

| Library | Purpose | Size |
|---------|---------|------|
| **lzo1x.js** or **minilzo-js** | LZO decompression for GBX body | ~5 KB |
| **pako** | zlib decompression for ghost sample data | ~25 KB |

### Implementation Priority

1. **Phase 1**: Parse GBX header + XML metadata only (trivial, useful for displaying replay info)
2. **Phase 2**: Custom input-based replay format for browser-native recordings
3. **Phase 3**: Full GBX body decompression + chunk parsing
4. **Phase 4**: Ghost sample decoding + interpolated playback

Phase 1 requires no external libraries. Phase 2 is independent of the TM2020 format. Phase 3+ requires LZO and zlib libraries plus significant chunk-format reverse engineering.

---

## 17. Known Unknowns

These are areas where the format is not fully understood. They are listed honestly to avoid false confidence.

### Critical Unknowns

| Area | What We Do Not Know | Impact |
|------|---------------------|--------|
| **Ghost sample data header** | Exact bytes before the sample array in CPlugEntRecordData -- may include version, sample count, sample period | Cannot reliably parse ghost samples without this |
| **Input recording binary format** | How CInputReplay serializes input events on disk | Cannot replay official TM2020 input recordings |
| **Body chunk semantics** | Exact purpose and format of many 0x0309300X chunks | Cannot fully parse replay body |
| **Ghost chunk dispatch** | Decompiled handlers for each 0x03092XXX chunk | Need for reliable ghost parsing |
| **Network ghost wire format** | How ghost data is encoded for multiplayer transmission | Cannot implement multiplayer ghost display |

### Moderate Unknowns

| Area | What We Do Not Know | Impact |
|------|---------------------|--------|
| **Ghost sample additional fields** | Whether newer versions add extra per-sample fields (e.g., wheel state, turbo) | May misparse newer ghost data |
| **Validation checksum algorithm** | Exact hashing/signing for replay integrity | Cannot create valid replay files |
| **MediaTracker data** | Camera keyframe and effect format within replays | Cannot render cinematic replays |
| **Input compression scheme** | Whether delta or run-length encoding is used | Affects parser implementation |
| **Ghost chunk versioning** | How chunk versions affect field layout | May fail on older/newer replays |

### Low-Priority Unknowns

| Area | What We Do Not Know |
|------|---------------------|
| Stunt score calculation | How stunt score is computed from ghost data |
| Ghost visual effects | How turbo/boost visual state is encoded in ghost |
| Multi-ghost replays | How multiple ghosts are indexed in a single replay |
| Ghost car skin data | How car skin/color is stored in ghost chunk 0x0309200B |

---

## 18. Cross-References

| Topic | Document | Section |
|-------|----------|---------|
| GBX file format specification | [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) | Sections 1-8 |
| Ghost class hierarchy (decompiled) | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) | Priority 3 |
| Ghost sample encoding (community) | [29-community-knowledge.md](29-community-knowledge.md) | Section 6.2 |
| Vehicle state fields | [19-openplanet-intelligence.md](19-openplanet-intelligence.md) | Section 1 |
| Real replay hex analysis | [26-real-file-analysis.md](26-real-file-analysis.md) | Section 3 |
| Class hierarchy JSON | [class_hierarchy.json](class_hierarchy.json) | CGameCtnGhost, CGameCtnReplayRecord, CPlugEntRecordData |
| Replay/ghost subsystem map | [13-subsystem-class-map.md](13-subsystem-class-map.md) | Section 6 |
| Network ghost flow | [17-networking-deep-dive.md](17-networking-deep-dive.md) | Ghost System section |
| Anti-cheat validation | [17-networking-deep-dive.md](17-networking-deep-dive.md) | Validation Flow section |
| Browser recreation guidance | [20-browser-recreation-guide.md](20-browser-recreation-guide.md) | Ghost/Replay section |
| Physics tick rate (100Hz) | [10-physics-deep-dive.md](10-physics-deep-dive.md) | Tick rate section |
| Surface gameplay effects | [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) | Priority 2 |

### Community Tools for Ghost/Replay Parsing

| Tool | Language | URL | Ghost Support |
|------|----------|-----|---------------|
| **GBX.NET** | C#/.NET | https://github.com/BigBang1112/gbx-net | Full ghost parsing (400+ classes) |
| **pygbx** | Python | https://github.com/donadigo/pygbx | Basic ghost reading |
| **gbx-ts** | TypeScript | https://github.com/thaumictom/gbx-ts | TypeScript GBX parser |
| **clip-input** | C# | https://github.com/bigbang1112-cz/clip-input | Converts replay inputs to visual clips |
| **gbxtools** | Python | https://github.com/donadigo/gbxtools | Replay analysis scripts |
| **TMInterface** | C++/DLL | https://donadigo.com/tminterface/ | TMNF/TMUF input recording (not TM2020) |

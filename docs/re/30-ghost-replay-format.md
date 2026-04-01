# Ghost & Replay Format Reference

Trackmania 2020 uses three recording systems: ghosts (sampled visual state at 50ms), replays (self-contained packages with embedded map + ghosts), and input replays (raw inputs at 100Hz for deterministic re-simulation).

This document covers file structure, sample encoding, checkpoint data, and TypeScript implementation guidance for parsing and playback.

---

## Ghost vs Replay vs InputReplay

| Concept | File Extension | Class | Purpose |
|---------|---------------|-------|---------|
| **Ghost** | `.Ghost.Gbx` | `CGameCtnGhost` | Visual replay: position/rotation/visual state sampled at 50ms intervals |
| **Replay** | `.Replay.Gbx` | `CGameCtnReplayRecord` | Complete package: ghost(s) + embedded map + metadata |
| **Input Replay** | `.InputsReplay.Gbx` | `CInputReplay` | Deterministic replay: raw input events at 100Hz tick rate |

Ghosts store sampled visual state (position, rotation, speed) for rendering. Input replays store raw inputs (steer, gas, brake) for deterministic re-simulation. A replay file bundles one or more ghosts plus the map, forming a self-contained package.

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

## Class Hierarchy

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

All 27 function names extracted from binary string table (VERIFIED):

| Function | Purpose |
|----------|---------|
| `Ghost_Add` | Add ghost to scene |
| `Ghost_AddWaypointSynced` | Add ghost synchronized to waypoints |
| `Ghost_AddPhysicalized` | Add ghost with physics interaction |
| `Ghost_Remove` / `Ghost_RemoveAll` | Remove ghosts |
| `Ghost_IsVisible` / `Ghost_IsReplayOver` | Query ghost state |
| `Ghost_SetDossard` / `Ghost_SetMarker` | Set ghost UI elements |
| `Ghost_GetPosition` | Get ghost's 3D position |
| `Ghost_RetrieveFromPlayer` / `Ghost_RetrieveFromPlayer2` | Capture ghost from live player |
| `Ghost_GetLiveFromPlayer` | Get live ghost stream |
| `Ghost_GetTimeClosestToPlayer` | Find closest time comparison point |
| `Ghost_CopyToScoreBestRaceAndLap` | Transfer checkpoint/lap times to score |
| `Ghost_Upload` / `Ghost_Download` / `Ghost_Release` | Network and lifecycle |

---

## Replay File Structure (.Replay.Gbx)

Replay files follow the standard GBX format (version 6) with class ID `0x03093000`.

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

The replay body contains a complete `.Map.Gbx` file. At offset 0x2E4, a nested GBX header appears:

```
000002e0: ...  47 42 5806 00    Nested "GBX" magic + version 6
000002f0: 4255 4352 0030 0403  "BUCR" + class 0x03043000 (CGameCtnChallenge)
```

Every replay is self-contained -- it carries its own copy of the map.

---

## Replay Header Chunks

Replay files always have exactly 3 header chunks.

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

Key fields:
- `best`: Race time in milliseconds (38401 = 38.401s)
- `respawns`: Number of respawns during run
- `validable`: 1 if the run is valid for leaderboards
- `checkpoints cur`: Number of checkpoint times recorded
- `playermodel id`: Vehicle type ("CarSport", "CarRally", "CarSnow", "CarDesert")

### Chunk 0x03093002: Author Info

```
Offset  Type      Field
------  ----      -----
+0x00   uint32    version              (observed: 1)
+0x04   string    author_login         ("XChwDu8FRmWH-gHqXUbBtg")
+0x??   string    author_nickname      ("Kelvination")
+0x??   string    author_zone          ("World|Africa|South Africa")
```

---

## Replay Body Structure

The replay body is LZO-compressed (format flag byte 2 = 'C'). After decompression, it contains body chunks belonging to `CGameCtnReplayRecord`.

### Known Body Chunks (from GBX.NET)

| Chunk ID | Content | Skippable? |
|----------|---------|------------|
| `0x03093002` | Map embedded data / map reference | [UNKNOWN] |
| `0x03093003` | Ghost data (embedded CGameCtnGhost) | [UNKNOWN] |
| `0x03093008` | Title UID ("TMStadium") | [UNKNOWN] |
| `0x03093014` | Ghost(s) array | [UNKNOWN] |
| `0x03093015` | Clip / MediaTracker data | [UNKNOWN] |

### Body Content Summary

1. **Embedded map** -- A complete `.Map.Gbx` (visible as nested "GBX" magic)
2. **One or more ghosts** -- `CGameCtnGhost` instances with sampled data
3. **Checkpoint times** -- Array of millisecond timestamps
4. **Validation data** -- Race validity flags
5. **Title/environment info** -- e.g., "TMStadium"
6. **Extras** -- Plugin metadata (e.g., "Openplanet 1.28.0"), game version strings

---

## CGameCtnGhost Format

Class ID `0x03092000`. A ghost contains metadata (player login, nickname, avatar, country zone), race result (total time, checkpoint times, validation status), sampled visual data (position/rotation/speed at 50ms via CPlugEntRecordData), input events, and vehicle model.

### Ghost Chunk IDs (from GBX.NET)

| Chunk ID | Content |
|----------|---------|
| `0x03092000` | Race time + ghost data (core) |
| `0x03092005` | Race time (uint32, milliseconds) |
| `0x03092008` | Ghost login (player identifier) |
| `0x0309200B` | Light trail color / car skin |
| `0x0309200C` | Checkpoint times array |
| `0x0309200E` | UID + player data |
| `0x0309200F` | Ghost nickname / display name |
| `0x03092010` | Ghost avatar |
| `0x03092012` | Record data (CPlugEntRecordData -- the actual sampled frames) |
| `0x03092017` | Player model (vehicle type) |
| `0x03092018` | Player inputs (event-based) |
| `0x03092019` | Validation data |

**Confidence**: PLAUSIBLE -- chunk IDs from GBX.NET source analysis. Not verified against Ghidra decompilation of chunk dispatch.

---

## Ghost Sample Encoding (50ms Period)

Ghost samples are recorded at **50ms intervals** (20 samples per second). This is much lower than the 100Hz physics tick rate, reflecting that ghosts serve visual playback, not deterministic re-simulation.

**Source**: Community knowledge (doc 29, section 6.2), GBX.NET source.
**Confidence**: HIGH -- community tools successfully parse ghosts using this encoding.

### Per-Sample Fields

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

Per sample: 3 * 4 (position) + 2 + 2 + 2 + 2 + 1 + 1 = **22 bytes** uncompressed.

### Compression

Ghost sample data uses **zlib** (deflate), not LZO like the outer GBX body. Two compression layers exist:
1. **Outer**: GBX body compression (LZO)
2. **Inner**: Ghost sample data compression (zlib deflate)

### Rotation Representation

The rotation uses axis-angle representation. The angle field gives rotation magnitude. Heading and pitch define the rotation axis direction in spherical coordinates.

### Speed Encoding

The exponential encoding `exp(value/1000)` compactly represents both slow and fast speeds. When `value == 0x8000` (-32768 signed), speed is exactly 0. Small integer differences at low speeds map to small velocity differences, while the same step at high speeds maps to larger differences.

### Integer Precision

- int16 heading/pitch: ~0.0001 radian precision (~0.006 degrees) -- sufficient for smooth playback
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

### Size Estimate for a 38-Second Replay

At 50ms per sample: `38000 / 50 = 760 samples`. At 22 bytes each: `760 * 22 = 16,720 bytes` uncompressed. After zlib compression, this reduces to ~5-10 KB.

---

## Input Recording Format (CInputReplay)

`CInputReplay` (string at `0x141b6dd98`) handles deterministic input recording at 100Hz. This is separate from ghost visual data.

**Confidence**: PARTIAL -- architecture confirmed, exact binary format [UNKNOWN].

### Input Fields Recorded

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `InputSteer` | float | -1.0 to 1.0 | Steering (normalized from raw int range -65536 to 65536) |
| `InputGasPedal` | float | 0.0 to 1.0 | Throttle |
| `InputBrakePedal` | float | 0.0 to 1.0 | Brake |
| `InputIsBraking` | bool | 0 or 1 | Braking state |

Raw integer conversion: `float_value = int_value / 65536.0`.

### Binary Format [UNKNOWN]

The exact on-disk encoding has not been decompiled. It likely uses event-based encoding (only state changes stored). The file extension `.InputsReplay.Gbx` suggests standalone GBX files, though they are typically embedded in replays.

---

## Entity Record Data (CPlugEntRecordData)

`CPlugEntRecordData` (string at `0x141bcb440`) is the low-level container for recorded entity state frames, referenced by ghost chunk `0x03092012`.

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

The function `NGameReplay::EntRecordDataDuplicateAndTruncate` (string at `0x141c66e28`) confirms record data can be duplicated (for sharing/upload) and truncated (cut to a specific time point for partial replays).

---

## Checkpoint Times & Validation Data

### Checkpoint Times Array

Ghost chunk `0x0309200C` stores checkpoint times as uint32 values in milliseconds (cumulative from race start). The last checkpoint time equals the total race time.

```
uint32    num_checkpoints        Number of checkpoint times
uint32[]  checkpoint_times       Array of times in milliseconds
```

### Validation Status

| Field | XML Attribute | Values | Meaning |
|-------|--------------|--------|---------|
| Validable | `validable="1"` | 0 or 1 | Whether the run counts for records |
| Respawns | `respawns="0"` | uint32 | Number of respawns |
| Stunt Score | `stuntscore="0"` | uint32 | Stunt-mode score (unused in Race mode) |

A run becomes non-validable if: the player used editor test mode, game modifications were detected, or the map was modified during the run.

---

## CGameCtnGhost vs CGameCtnReplayRecord

| Feature | CGameCtnGhost (0x03092000) | CGameCtnReplayRecord (0x03093000) |
|---------|---------------------------|-----------------------------------|
| **Purpose** | Single driver's recorded run | Complete replay package |
| **Contains map?** | No -- references map by UID | Yes -- embeds complete `.Map.Gbx` |
| **Number of ghosts** | Is a ghost (1 driver) | Contains 1+ ghosts |
| **Standalone file?** | `.Ghost.Gbx` | `.Replay.Gbx` |
| **Self-contained?** | No (needs map to display) | Yes (viewable without original map) |
| **Header chunks** | [UNKNOWN count] | 3 header chunks |

| Context | Format Used |
|---------|-------------|
| Autosave after completing a map | `.Replay.Gbx` (autosaves directory) |
| Manual save of a run | `.Replay.Gbx` (My Replays directory) |
| Downloading a leaderboard ghost | `.Ghost.Gbx` or ghost data via API |
| Multiplayer ghost display | Network ghost format (streamed) |

---

## Ghost Playback & Interpolation

At 50ms sample intervals and 60+ FPS rendering, interpolation is needed for smooth display.

**Position**: Linear interpolation between consecutive samples. At typical car speeds (~100-500 km/h), positional error from linear interpolation is small (< 1 meter).

**Rotation**: Spherical linear interpolation (slerp) of the axis-angle representation, or conversion to quaternion followed by slerp.

**Speed and velocity direction**: Linear interpolation of decoded values.

Ghost/replay vehicles use entity ID mask `0x04000000` to distinguish them from live players (`0x02000000`).

---

## Network Ghost Format

### Ghost Data Flow (Online)

```
Local Recording:
  CInputReplay captures every input frame (100 Hz)
  CGameGhostTMData stores TM-specific metadata
  CGameCtnGhost wraps with car/map context

Upload (on PB or request):
  CWebServicesTask_UploadSessionReplay      -- Full replay upload
  CGameDataFileTask_GhostDriver_Upload      -- Ghost-specific upload

Download:
  CGameDataFileTask_GhostDriver_Download    -- Download ghost
  CGameScoreTask_GetPlayerMapRecordGhost    -- Get PB ghost for a map
```

### Secure Record Attempt Flow

```
1. POST  CreateMapRecordSecureAttempt      -- Get attempt token
2. Player completes the map
3. PATCH PatchMapRecordSecureAttempt       -- Submit ghost + result
4. Upload UploadSessionReplay              -- Full replay for validation
5. Server replays inputs, verifies time matches
```

### Anti-Cheat Upload

| Config Parameter | Address | Purpose |
|-----------------|---------|---------|
| `AntiCheatReplayChunkSize` | `0x141c2af98` | Size per upload chunk |
| `AntiCheatReplayMaxSize` | `0x141c2afe0` | Maximum total upload |
| `AntiCheatReplayMaxSizeOnCheatReport` | `0x141c2afb8` | Increased limit on cheat reports |

---

## Browser TypeScript Implementation Guide

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

Only store an `InputFrame` when any input value changes. A typical 38-second run produces ~200-500 events (far less than 3,800 ticks). Playback feeds recorded inputs into deterministic physics at 100Hz.

### Strategy 2: Parsing Official TM2020 Ghosts (Advanced)

```typescript
class ReplayParser {
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

  parseHeaderChunks(buffer: ArrayBuffer, offset: number, count: number): HeaderChunk[] {
    const view = new DataView(buffer);
    const chunks: HeaderChunk[] = [];
    let pos = offset;

    for (let i = 0; i < count; i++) {
      const chunkId = view.getUint32(pos, true); pos += 4;
      const rawSize = view.getUint32(pos, true); pos += 4;
      const isHeavy = (rawSize & 0x80000000) !== 0;
      const size = rawSize & 0x7FFFFFFF;
      chunks.push({ chunkId, size, isHeavy });
    }

    for (const chunk of chunks) {
      chunk.data = new Uint8Array(buffer, pos, chunk.size);
      pos += chunk.size;
    }

    return chunks;
  }

  parseXmlMetadata(chunkData: Uint8Array): ReplayMetadata {
    const decoder = new TextDecoder();
    const text = decoder.decode(chunkData);
    const xmlStart = text.indexOf('<header');
    const xmlEnd = text.indexOf('</header>') + '</header>'.length;
    const xml = text.substring(xmlStart, xmlEnd);
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'text/xml');
    return this.extractMetadata(doc);
  }

  decodeGhostSamples(compressedData: Uint8Array): GhostSample[] {
    const decompressed = pako.inflate(compressedData);
    const view = new DataView(decompressed.buffer);
    const samples: GhostSample[] = [];
    let pos = 0;

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

1. **Phase 1**: Parse GBX header + XML metadata only (no external libraries needed)
2. **Phase 2**: Custom input-based replay format for browser-native recordings
3. **Phase 3**: Full GBX body decompression + chunk parsing
4. **Phase 4**: Ghost sample decoding + interpolated playback

---

## Known Unknowns

### Critical

| Area | What We Do Not Know | Impact |
|------|---------------------|--------|
| Ghost sample data header | Exact bytes before the sample array in CPlugEntRecordData | Cannot reliably parse ghost samples without this |
| Input recording binary format | How CInputReplay serializes input events | Cannot replay official TM2020 input recordings |
| Body chunk semantics | Exact purpose and format of many 0x0309300X chunks | Cannot fully parse replay body |
| Ghost chunk dispatch | Decompiled handlers for each 0x03092XXX chunk | Need for reliable ghost parsing |

### Moderate

| Area | What We Do Not Know |
|------|---------------------|
| Ghost sample additional fields | Whether newer versions add extra per-sample fields |
| Validation checksum algorithm | Exact hashing/signing for replay integrity |
| MediaTracker data | Camera keyframe and effect format within replays |
| Input compression scheme | Whether delta or run-length encoding is used |

---

## Related Pages

- [26-real-file-analysis.md](26-real-file-analysis.md) -- Hex analysis of real replay files
- [29-community-knowledge.md](29-community-knowledge.md) -- Community ghost sample encoding details (section 6.2)
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Vehicle state fields used in ghost data
- [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) -- GBX file format specification
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Browser recreation ghost/replay section
- [13-subsystem-class-map.md](13-subsystem-class-map.md) -- Replay/ghost subsystem class map (section 6)
- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- Physics tick rate (100Hz) used by input replays

### Community Tools for Ghost/Replay Parsing

| Tool | Language | URL | Ghost Support |
|------|----------|-----|---------------|
| **GBX.NET** | C#/.NET | https://github.com/BigBang1112/gbx-net | Full ghost parsing (400+ classes) |
| **pygbx** | Python | https://github.com/donadigo/pygbx | Basic ghost reading |
| **gbx-ts** | TypeScript | https://github.com/thaumictom/gbx-ts | TypeScript GBX parser |
| **clip-input** | C# | https://github.com/bigbang1112-cz/clip-input | Converts replay inputs to visual clips |

<details><summary>Analysis metadata</summary>

- **Date**: 2026-03-27
- **Purpose**: Comprehensive reference for Trackmania 2020 ghost and replay file formats
- **Sources**: Ghidra decompilation (doc 22), community knowledge (doc 29, GBX.NET), Openplanet intelligence (doc 19), GBX format spec (doc 16), real file hex analysis (doc 26), class hierarchy, hex dumps of actual `.Replay.Gbx` files

</details>

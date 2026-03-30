# File Format Handling and GBX Parsing

**Binary**: `Trackmania.exe` (Trackmania 2020)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**Note**: All function symbols are stripped. Functions are named by Ghidra convention (FUN_<address>).

---

## Table of Contents

1. [GBX File Format Overview](#1-gbx-file-format-overview)
2. [GBX Header Parsing](#2-gbx-header-parsing)
3. [GBX Body and Chunk System](#3-gbx-body-and-chunk-system)
4. [The Serialization / Archive System](#4-the-serialization--archive-system)
5. [Class ID System](#5-class-id-system)
6. [File Types Supported](#6-file-types-supported)
7. [The Fid (File ID) System](#7-the-fid-file-id-system)
8. [Pack File System](#8-pack-file-system)
9. [Map Loading Pipeline (CGameCtnChallenge)](#9-map-loading-pipeline-cgamectnchallenge)
10. [Key Function Reference Table](#10-key-function-reference-table)

---

## 1. GBX File Format Overview

GBX (GameBox) is Nadeo's proprietary binary serialization format used for all game assets. Every `.Gbx` file encodes a single CMwNod-derived object tree using a chunk-based serialization protocol.

**Loading entry point**: `FUN_140904730` (CSystemArchiveNod::LoadGbx)

The loading pipeline supports three file variants:
- **Binary GBX** (`.gbx`) - primary format, chunk-based binary serialization
- **XML GBX** (`.gbx.xml`) - XML representation, loaded via `FUN_140925fa0`
- **JSON** (`.json`) - JSON import, loaded via `FUN_140934b80`

### GBX File Structure (Binary)

```
+---------------------------+
| Magic: "GBX" (3 bytes)   |  FUN_140900e60 reads this
+---------------------------+
| Version (uint16)          |  Versions 3-6 supported; 1-2 rejected
+---------------------------+
| Format flags (4 chars)    |  Only for version >= 6 (FUN_140901850)
+---------------------------+
| Class ID (uint32)         |  Identifies the main node type
+---------------------------+
| Reference count (uint32)  |  External dependency count
+---------------------------+
| Header chunks             |  Metadata chunks (optional)
+---------------------------+
| Reference table           |  External file references
+---------------------------+
| Body chunks               |  Main serialized data
+---------------------------+
```

**Error messages confirming format** (from binary strings):
- `"Wrong .Gbx format : not a < GameBox > file"` at `0x141c067a8`
- `"Wrong .Gbx format : request a GameBox version between the %s and the %s"` at `0x141c06820`
- `"[Sys] Corrupted data while reading .gbx file"` at `0x141c06ac0`

---

## 2. GBX Header Parsing

### Magic and Version (`FUN_140900e60` at `0x140900e60`)

The header loader reads:
1. **3 bytes**: Must be exactly `'G'`, `'B'`, `'X'`
2. **2 bytes (uint16)**: Version number

| Version | Status | Notes |
|---------|--------|-------|
| 1 | Rejected | "August 2000" era format |
| 2 | Rejected | "August 2000" era format |
| 3 | Supported | Legacy format |
| 4 | Supported | [UNKNOWN differences from 3] |
| 5 | Supported | [UNKNOWN differences from 4] |
| 6 | Supported | Current TM2020 format, includes format flags |

For versions 3-6, parsing continues in `FUN_140901850`.

### Format Flags - Version 6+ (`FUN_140901850` at `0x140901850`)

For version 6, a 4-character format descriptor follows the version:

| Byte | Position | Values | Meaning |
|------|----------|--------|---------|
| 0 | Format type | `'B'` / `'T'` | Binary / Text |
| 1 | Body compression | `'C'` / `'U'` | Compressed / Uncompressed |
| 2 | [UNKNOWN] compression | `'C'` / `'U'` | Compressed / Uncompressed |
| 3 | Reference mode | `'R'` / `'E'` | With references / No external refs |

- **Byte 0**: Only `'B'` (binary) proceeds to full parsing. `'T'` (text) is recognized but [UNKNOWN if fully supported in TM2020].
- **Byte 1**: Stored at archive offset `+0xD8`. Controls body decompression.
- **Byte 2**: Stored at archive offset `+0xDC`. Controls body stream decompression (LZO/zlib). When set, body data is decompressed via `FUN_140127aa0` before chunk parsing.
- **Byte 3**: `'R'` = file contains external references to other GBX files; `'E'` = self-contained.

Common format strings: `"BUCR"` (Binary, Uncompressed body, Compressed [UNKNOWN], with References) and `"BUCE"` (no external refs).

After the format flags, the header reads:
- **Class ID** (uint32): The main node's class identifier
- **Reference count** (uint32): Number of entries in the reference table (max 50,000 enforced)

The reference table is allocated as an array of 0x10-byte entries at archive offset `+0x50`.

### Decompiled code

See `decompiled/fileformats/FUN_140900e60_LoadHeader.c` and `FUN_140901850_ParseVersionHeader.c`.

---

## 3. GBX Body and Chunk System

### Reference Table Loading (`FUN_140902530` at `0x140902530`)

After the header, the reference table is loaded. This resolves external dependencies (other GBX files referenced by this one).

**Profiling marker**: `"NSys::ArLoadRef_Gbx"` (version 7) or `"NSys::ArLoadRef"` (others)

The function:
1. Reads **node count** (uint32, max 49,999)
2. Reads **ancestor level count** (uint32, max 99) -- [UNKNOWN exact purpose, likely folder/directory ancestry]
3. Reads **folder ancestry** for path resolution
4. Reads **reference entries** count (uint32, max 99)
5. For each reference entry, reads chunk ID and size information
6. For each node, reads:
   - A **chunk ID** (uint32)
   - An optional **size** field (for version >= 5)
   - Resolves the reference to an actual GBX file via the Fid system
   - Loads referenced file if needed (recursive loading)
7. The special value `0xDEADBEEF` is written as a placeholder during reference resolution (visible at address `0x140902994`)

### Body Chunk Loading (`FUN_1409031d0` at `0x1409031d0`)

The body contains the actual serialized data, organized as a sequence of chunks.

**Profiling marker**: Uses the output of `FUN_140903140` (e.g., `"ArchiveNod::LoadGbx_Body(Challenge)"`)

Flow:
1. Gets a profiling label based on class ID (see table below)
2. Records stream position and body size at archive offsets `+0x120` (body size) and `+0x124` (end position)
3. **If version == 3**: Reads body as raw blob, stores in a buffer
4. **If version > 3** and body is compressed (offset `+0xDC` != 0):
   - Decompresses body via `FUN_140127aa0` into a memory buffer
   - The decompression buffer is pooled (reused from `DAT_14205c280`)
   - Max decompressed size of 0xFFFFF (~1MB) before pool reuse
5. Resolves **internal references** - iterates the reference table connecting nodes
6. Calls `FUN_140900560` to associate the main node with the archive

### End-of-Chunks Marker (`FUN_1402d0c40` at `0x1402d0c40`)

The body chunk stream ends with a special sentinel:
- **Chunk ID `0xFACADE01`**: Signals end of chunks (returned by this function for all non-terminal chunk IDs)
- **Chunk ID `0x01001000`**: The actual end-of-chunks marker (CMwNod_End), returns 1

When an unknown chunk ID is encountered, `FUN_1402d0c80` logs:
`"Unknown ChunkId: %08X"` at `0x141b72000`

### Body Type Labels (Class ID -> Profile Label)

From `FUN_140903140` at `0x140903140`:

| Class ID | Label | Likely Class |
|----------|-------|--------------|
| `0x03043000` | `LoadGbx_Body(Challenge)` | CGameCtnChallenge (Map) |
| `0x03093000` | `LoadGbx_Body(ReplayRecord)` | CGameCtnReplayRecord |
| `0x0309A000` | `LoadGbx_Body(ControlCard)` | [UNKNOWN] |
| `0x09005000` | `LoadGbx_Body(Solid1)` | CPlugSolid (legacy mesh) |
| `0x09011000` | `LoadGbx_Body(Bitmap)` | CPlugBitmap |
| `0x09026000` | `LoadGbx_Body(ShaderApply)` | [UNKNOWN - material/shader] |
| `0x09053000` | `LoadGbx_Body(GpuCompileCache)` | [UNKNOWN] |
| `0x090BB000` | `LoadGbx_Body(Solid2)` | CPlugSolid2Model |
| All others | `LoadGbx_Body(Other)` | - |

---

## 4. The Serialization / Archive System

### CClassicArchive

The core archive reader. String evidence:
- `"CClassicArchive::ReadData() failed on \""` at `0x141b58200`
- `"[Archive] SAVING ERROR: Saving skipped datas => data may be lost !!"` at `0x141b582c0`

**ReadData function** (`FUN_14012ba00` at `0x14012ba00`):
- Reads raw bytes from the stream via vtable call at `*(*(param_1[1]) + 8)`
- Validates the number of bytes actually read matches the requested count
- On mismatch: logs the error with the archive name (obtained via vtable call at `*(*param_1 + 0x30)`)
- Sets error flag at `param_1+0x28` (offset 5 from base) on failure
- Calls `DAT_141f9d088` callback on error (if set) -- used for crash reporting

The archive object layout (partial, from decompilation):
| Offset | Type | Purpose |
|--------|------|---------|
| `+0x00` | vtable* | Virtual function table |
| `+0x08` | stream* | Underlying read/write stream |
| `+0x10` | int | [UNKNOWN - mode flags?] |
| `+0x28` | int | Error flag (0 = OK, 1 = error) |
| `+0x40` | array* | Chunk data array (0x20-byte stride per chunk entry) |
| `+0x48` | uint | Chunk count |
| `+0x50` | array* | Reference table (0x10-byte stride per entry) |
| `+0x58` | uint | Reference count |
| `+0x60` | ushort | GBX version number |
| `+0x64` | int | Format/mode byte |
| `+0x7C` | int | [UNKNOWN flag] |
| `+0x88` | int | FidFile loaded flag |
| `+0x90` | FidFile* | Associated file descriptor |
| `+0xA0` | uint32 | Main class ID |
| `+0xD8` | int | Body compression flag |
| `+0xDC` | int | Header/stream compression flag |
| `+0xE8` | array* | Ancestor/dependency array |
| `+0xF0` | uint | Ancestor count |
| `+0xF8` | ptr | [UNKNOWN - deferred load context?] |
| `+0x120` | int | Body size in bytes |
| `+0x124` | uint32 | Stream end position |
| `+0x128` | ptr | Raw body buffer (for version 3) |
| `+0x130` | longlong | [UNKNOWN - secondary archive context?] |

### CSystemArchiveNod

The system-level archive that manages loading GBX files from the file system.

String evidence:
- `"ArchiveNod::LoadGbx"` at `0x141c06b98`
- `"ArchiveNod::LoadHeader"` at `0x141c06808`
- `"ArchiveNod::LoadGbx_Body(...)"` (multiple variants)
- `"ArchiveNod::LoadMemory"` at `0x141c06bb0`
- `"ArchiveNod::ImportMedia"` at `0x141c06af0`
- `"ArchiveNod::Parametrization"` at `0x141c06b38`
- `"ArchiveNod::Duplicate"` at `0x141c06b58`
- `"ArchiveNod::LookupNod"` at `0x141c067f0`

Thread safety warnings:
- `"[Sys] Danger: CSystemArchiveNod::DoLoadFromFid(Gbx) called outside MainThread"` at `0x141c06be0`
- `"[Sys] Danger: CSystemArchiveNod::DoLoadFromFid(Media) called outside MainThread"` at `0x141c06a60`

### Archive Version System

String: `"%.*sUnknown archive version %d (> %d)"` at `0x141b72028`

Individual chunks within a GBX body have their own version numbers (independent of the GBX file version). When a chunk's version exceeds what the engine expects, this error is logged. This allows forward compatibility -- newer files can be partially read by older engines.

---

## 5. Class ID System

### Class ID Structure

Class IDs are 32-bit values with a hierarchical structure:

```
  Bits 31-24: Engine ID (top-level namespace)
  Bits 23-12: Class index within engine
  Bits 11-0:  [UNKNOWN - possibly chunk/sub-class index, always 0x000 for class IDs]
```

### Engine IDs (from string evidence and class ID remapping table)

| Engine ID | Name | Example Classes |
|-----------|------|----------------|
| `0x01` | System/MwNod | CMwNod base (end marker `0x01001000`) |
| `0x03` | Game | CGameCtnChallenge, CGameCtnReplayRecord, CGameItemModel |
| `0x06` | [UNKNOWN] | `0x06004000`, `0x06005000` |
| `0x09` | Plug | CPlugSolid, CPlugBitmap, CPlugSolid2Model, CPlugMaterial |
| `0x0A` | Scene (legacy) | Remapped to `0x09` in modern builds |
| `0x0C` | Control | `0x0C030000`, `0x0C031000`, `0x0C032000` |
| `0x11` | [UNKNOWN] | `0x11001000` |
| `0x2E` | [UNKNOWN] | Various classes remapped from old IDs |

### Class Registration and Lookup

**Global class table**: `DAT_141ff9d58`

The table is organized as a two-level hierarchy:
1. **Level 1**: Array of engine pointers, indexed by engine ID (`class_id >> 24`)
2. **Level 2**: Each engine has an array of class info pointers, indexed by class index (`(class_id >> 12) & 0xFFF`)

Each class info entry (from `FUN_1402f20a0`):
| Offset | Content |
|--------|---------|
| `+0x08` | Class name (const char*) |
| `+0x10` | [UNKNOWN - possibly parent class info] |
| `+0x18` | [UNKNOWN] |
| `+0x20` | [UNKNOWN] |
| `+0x30` | Factory function pointer (creates instance), NULL if abstract |

**Factory function** (`FUN_1402cf380` / CreateByMwClassId):
- Looks up class info via `FUN_1402f20a0`
- If factory pointer at `+0x30` exists: calls it to create a new instance
- If factory is NULL: logs `"[MwNod] Trying to CreateByMwClassId('<classname>') which is pure..."`
- If class unknown: logs `"[MwNod] Trying to CreateByMwClassId(<id>) which is unknown..."`

### Class ID Remapping (Backward Compatibility)

`FUN_1402f2610` at `0x1402f2610` is a massive lookup table that converts legacy class IDs to their modern equivalents. This enables reading GBX files from older ManiaPlanet/Trackmania versions.

Key remappings (selected from ~200+ entries):

| Old ID | New ID | Likely Class |
|--------|--------|--------------|
| `0x24003000` | `0x03043000` | CGameCtnChallenge |
| `0x24004000` | `0x03033000` | [UNKNOWN Game class] |
| `0x2403F000` | `0x03093000` | CGameCtnReplayRecord |
| `0x24099000` | `0x0309A000` | [UNKNOWN - ControlCard?] |
| `0x08010000` | `0x090B5000` | [Old Graphic -> Plug] |
| `0x0A06A000` | `0x090E5000` | [Old Scene -> Plug] |
| `0x0A03D000` | `0x0C030000` | [Old Scene -> Control] |

The bulk of remappings convert engine `0x24` (old Game namespace) to engine `0x03` (modern Game namespace), and engines `0x08`/`0x0A` (old Graphic/Scene) to engine `0x09` (modern Plug).

**TLS cache**: The lookup function uses a 2-entry Most-Recently-Used cache in Thread-Local Storage to avoid repeated table lookups for the same class ID (at TLS offsets `+0x1190` through `+0x11AC`).

### Decompiled code

See:
- `decompiled/fileformats/FUN_1402cf380_CreateByMwClassId.c`
- `decompiled/fileformats/FUN_1402f20a0_ClassIdLookup.c`
- `decompiled/fileformats/FUN_1402f2610_ClassIdRemap.c`

---

## 6. File Types Supported

### GBX File Extensions (from binary strings)

The following `.Gbx` file types were found referenced in the binary. Organized by category:

#### Map / Challenge
| Extension | Address | Notes |
|-----------|---------|-------|
| `.Map.Gbx` | `0x141c2b290` | Map files (modern name) |
| `.Challenge.Gbx` | `0x141c2dc10` | Map files (legacy name, same format) |
| `Map.Gbx` | `0x141c347d8` | Without leading dot |
| `%1%2\%3.Map.Gbx` | `0x141c34f70` | Map path template |

#### Replay / Ghost
| Extension | Address | Notes |
|-----------|---------|-------|
| `.Replay.Gbx` | `0x141c2b280` | Replay files |
| `.Ghost.Gbx` | `0x141c40868` | Ghost data (individual runs) |
| `.Ghost.gbx` | `0x141c320f8` | Ghost (lowercase variant) |
| `Replay.Gbx` | `0x141c49c68` | Without leading dot |
| `.InputsReplay.Gbx` | `0x141cccef0` | Raw input replay |

#### Items / Blocks
| Extension | Address | Notes |
|-----------|---------|-------|
| `.Item.Gbx` | `0x141c2d630` | Custom items |
| `.Block.Gbx` | `0x141c2d740` | Block definitions |
| `.Macroblock.Gbx` | `0x141c2d708` | Macroblock (multi-block groups) |
| `BlockItem.Gbx` | `0x141c284e0` | Block-item hybrid |
| `Item.Gbx` | `0x141c201a0` | Item base |
| `StaticObject.Gbx` | `0x141bc68e8` | Static 3D object |

#### Visual / Mesh
| Extension | Address | Notes |
|-----------|---------|-------|
| `.Mesh.Gbx` | `0x141bd5490` | 3D mesh |
| `.Mesh.gbx` | `0x141bd1cc0` | Mesh (lowercase) |
| `.Solid2.gbx` | `0x141bd1cd0` | Solid2 model |
| `Crystal.Gbx` | `0x141bc2168` | Crystal geometry |
| `Visual.Gbx` | `0x141ba4990` | Visual representation |
| `Model.Gbx` | `0x141bc5d90` | General model |
| `GenSolid.Gbx` | `0x141bc69c8` | Generated solid |

#### Texture / Material
| Extension | Address | Notes |
|-----------|---------|-------|
| `Texture.Gbx` | `0x141ba3768` | Texture file |
| `.Texture.Gbx` | `0x141bb8e18` | Texture with dot prefix |
| `Material.Gbx` | `0x141ba5d78` | Material definition |
| `.Material.Gbx` | `0x141c99238` | Material with dot prefix |
| `.Material.gbx` | `0x141bb8d80` | Material (lowercase) |
| `Mat.Gbx` | `0x141bbd5a0` | Short material name |
| `TexturePack.Gbx` | `0x141bbdd18` | Texture atlas pack |
| `ImageArray.Gbx` | `0x141bb9e50` | Image array |

#### Audio
| Extension | Address | Notes |
|-----------|---------|-------|
| `Sound.Gbx` | `0x141ba55f8` | Sound file |
| `Music.Gbx` | `0x141bc2f80` | Music |
| `SoundMood.Gbx` | `0x141bc2810` | Sound mood/ambience |
| `SoundEngine.Gbx` | `0x141bc2990` | Engine sound model |
| `SoundSurface.Gbx` | `0x141bc2b08` | Surface-specific sounds |
| `AudioEnvironment.Gbx` | `0x141bc31c0` | Audio environment settings |
| `AudioBalance.Gbx` | `0x141bc33a0` | Audio balance |

#### Animation / Skeleton
| Extension | Address | Notes |
|-----------|---------|-------|
| `.Anim.gbx` | `0x141bd1d08` | Animation |
| `.AnimClip.gbx` | `0x141bd1d18` | Animation clip |
| `AnimClip.Gbx` | `0x141bd0700` | Animation clip |
| `Anim.Gbx` | `0x141bd09b0` | Animation |
| `.Skel.gbx` | `0x141bd1cb0` | Skeleton |
| `Skel.Gbx` | `0x141bba2a8` | Skeleton |
| `Rig.gbx` | `0x141bd7980` | Rig file |
| `RigToSkel.gbx` | `0x141bd7b30` | Rig-to-skeleton mapping |

#### Vehicle
| Extension | Address | Notes |
|-----------|---------|-------|
| `VehicleVisModel.Gbx` | `0x141bd2510` | Vehicle visual model |
| `VehiclePhyModelCustom.Gbx` | `0x141bd5b28` | Vehicle physics model |
| `VehicleStyles.gbx` | `0x141bd3188` | Vehicle style variants |
| `VehicleCameraRace3Model.gbx` | `0x141bd3c80` | Race camera model |
| `CarMarksModel.Gbx` | `0x141becc38` | Tire mark model |

#### Lighting / Effects
| Extension | Address | Notes |
|-----------|---------|-------|
| `Light.Gbx` | `0x141babda0` | Light definition |
| `LightMapCache.Gbx` | `0x141b66db8` | Lightmap cache |
| `LightmapCustom.Gbx` | `0x141bd6670` | Custom lightmap |
| `LightMapMood.Gbx` | `0x141b6b0d8` | Lightmap mood settings |
| `ProbeGrid.Gbx` | `0x141b668b8` | Light probe grid |
| `SceneFx.Gbx` | `0x141be5ff0` | Scene effects |
| `FxSys.Gbx` | `0x141bd68a0` | FX system |
| `VFX.Gbx` | `0x141bb5280` | Visual effects |
| `ParticleModel.Gbx` | `0x141bb6d48` | Particle system |

#### UI / Control
| Extension | Address | Notes |
|-----------|---------|-------|
| `Frame.Gbx` | `0x141b5c318` | UI frame |
| `StyleSheet.Gbx` | `0x141b5c6c0` | UI stylesheet |
| `ControlStyle.Gbx` | `0x141b5afb0` | Control styling |
| `ControlLayout.Gbx` | `0x141b5ca50` | Control layout |
| `ControlEffect.Gbx` | `0x141b5d830` | Control effect |
| `Font.Gbx` | `0x141ba5490` | Font |

#### Campaign / Title
| Extension | Address | Notes |
|-----------|---------|-------|
| `.Campaign.Gbx` | `0x141c35e10` | Campaign definition |
| `Title.Gbx` | `0x141c35928` | Title pack reference |
| `TitleCore.Gbx` | `0x141cea968` | Title core data |
| `Collection.Gbx` | `0x141c5f398` | Block collection |
| `Decoration.Gbx` | `0x141c3be78` | Decoration definition |
| `DecorationMood.Gbx` | `0x141c3b8b8` | Decoration mood settings |

#### Pack Files
| Extension | Address | Notes |
|-----------|---------|-------|
| `.pack.gbx` | `0x141bbba40` | Generic pack |
| `.skin.pack.gbx` | `0x141bbba50` | Skin pack |
| `.Skin.Pack.Gbx` | `0x141c077e8` | Skin pack (capitalized) |
| `.Title.Pack.Gbx` | `0x141c2f438` | Title pack |
| `.Media.Pack.Gbx` | `0x141c2f5e0` | Media pack |
| `-Model.Pack.Gbx` | `0x141c8bf00` | Model pack |
| `Model.Pack.Gbx` | `0x141c8dbe0` | Model pack |
| `Trackmania.Title.Pack.Gbx` | `0x141bcc828` | Main game title pack |
| `Trackmania_Update.Title.Pack.Gbx` | `0x141c584b0` | Update title pack |
| `.Title.Pack.Gbx.ref` | `0x141c58c50` | Title pack reference file |
| `-wip.pack.gbx` | `0x141c2f818` | Work-in-progress pack |

#### Miscellaneous
| Extension | Address | Notes |
|-----------|---------|-------|
| `Prefab.Gbx` | `0x141bcca30` | Prefab (pre-assembled objects) |
| `World.Gbx` | `0x141cf6c88` | World definition |
| `.ScriptCache.Gbx` | `0x141c31e50` | Script cache |
| `.Profile.Gbx` | `0x141c31e68` | Player profile |
| `User.FidCache.Gbx` | `0x141c30fe0` | User file cache |
| `User.Profile.Gbx` | `0x141c82f68` | User profile |
| `GameCtnApp.Gbx` | `0x141c30710` | Application state |
| `.environment.gbx` | `0x141c29ac0` | Environment definition |
| `ManiaPlanet.ManiaPlanet.gbx` | `0x141a58bd8` | Root app GBX |
| `GpuCache.Gbx` | `0x141bbcf70` | GPU shader cache |
| `.GpuCache.Gbx` | `0x141bad7f0` | GPU cache with dot prefix |

#### JSON Config Files
| Extension | Address | Notes |
|-----------|---------|-------|
| `.gbx.json` | `0x141bd1c50` | GBX in JSON format |
| `SkelLodSetup.Gbx.json` | `0x141bba230` | Skeleton LOD setup |
| `ShootIconSetting.gbx.json` | `0x141c7b7a0` | [UNKNOWN] |
| `PreloadDesc.gbx.json` | `0x141c2fca0` | Preload descriptor |
| `Default.gbx.json` | `0x141c05468` | Default config |

**Total unique .Gbx extensions found**: 431 string matches containing ".Gbx" or ".gbx".

---

## 7. The Fid (File ID) System

The Fid system is Nadeo's virtual file system layer that abstracts file access across different storage backends (disk, packs, network).

### Class Hierarchy (from strings)

| Class | Address | Role |
|-------|---------|------|
| `CSystemFidFile` | `0x141c07380` | Represents a single file |
| `CSystemFidsFolder` | `0x141c08d68` | Represents a directory/folder |
| `CSystemFidContainer` | `0x141c08ec8` | Contains fids (e.g., a pack file) |
| `CSystemFidsDrive` | `0x141c08ff8` | Top-level drive/mount point |

### Key Operations

- **`CSystemFidsFolder::BrowsePath`** (string at `0x141c08d88`): Directory traversal
- **`CSystemFidContainer::InstallFids`** (`FUN_14092bec0` at `0x14092bec0`): Registers files from a container (pack) into the virtual file system
  - Takes a parent folder, container, and various parameters
  - Iterates entries (stride 0x20 per entry) at container offset `+0x18`
  - Creates FidFile entries for each file via `FUN_1408fa7b0`
  - Associates files with their parent container via `FUN_1402cfa80`
  - Sets up file watching if `container+0x80` is non-null
  - Updates folder indices at `container+0x38`

### FidFile Layout (partial, from decompilation)

| Offset | Type | Purpose |
|--------|------|---------|
| `+0x08` | ptr | [UNKNOWN] |
| `+0x18` | ptr | Parent folder/container |
| `+0x20` | uint | Flags (bit 0 = [UNKNOWN], bit 2 = [UNKNOWN]) |
| `+0x24` | uint | Additional flags |
| `+0x48` | uint | File state flags |
| `+0x78` | uint32 | [UNKNOWN - possibly file size or class ID] |
| `+0x80` | ptr | Loaded nod pointer (the actual object) |
| `+0xA8` | ptr | [UNKNOWN] |
| `+0xB0` | ptr* | Stream factory (vtable for creating read streams) |
| `+0xD0` | string | File path/name |
| `+0xD8` | uint32 | Path length |
| `+0xDC` | uint32 | [UNKNOWN path-related field] |

### CPlugFileFidCache

`CPlugFileFidCache` (string at `0x141bc4ec8`) and `User.FidCache.Gbx` (at `0x141c30fe0`) indicate a caching layer for file lookups. The `LoadAndRefreshFidCache` operation (string at `0x141c30e70`) suggests the cache is persisted to disk and refreshed on startup.

---

## 8. Pack File System

### Pack Types

From binary strings, these pack file types exist:

| Pack Type | Extension | Example |
|-----------|-----------|---------|
| Generic pack | `.pack.gbx` | General asset bundles |
| Skin pack | `.skin.pack.gbx` / `.Skin.Pack.Gbx` | Character/vehicle skins |
| Title pack | `.Title.Pack.Gbx` | Full game title content |
| Media pack | `.Media.Pack.Gbx` | Media assets |
| Model pack | `Model.Pack.Gbx` / `-Model.Pack.Gbx` | 3D model collections |
| WIP pack | `-wip.pack.gbx` | Work-in-progress content |

### Pack Management

**CSystemPackManager** (strings at `0x141c076d8`):
- `CSystemPackManager::UpdatePackDescsAfterLoad` (`0x141c07820`)
- `CSystemPackManager::LoadCache` (`0x141c078b0`)
- `CSystemPackManager::TrimCacheIfNeeded` (`0x141c079b0`)

**CSystemPackDesc** (string at `0x141c07270`): Describes a pack's metadata.

### Title Packs

The main game content is loaded from:
- `"Trackmania.Title.Pack.Gbx"` at `0x141bcc828` / `0x141c58368`
- `"Trackmania_Update.Title.Pack.Gbx"` at `0x141c584b0`
- `".Title.Pack.Gbx.ref"` at `0x141c58c50` (reference files that point to actual packs)

Legacy ManiaPlanet title packs are also referenced:
- `"ShootMania\ShootMania.TitleCore.Gbx"` at `0x141c35c10`
- `"TrackMania.TitleCore.Gbx"` at `0x141c35cb8`

---

## 9. Map Loading Pipeline (CGameCtnChallenge)

CGameCtnChallenge (class ID `0x03043000`) is the main map class. "Challenge" is the legacy internal name; externally these are `.Map.Gbx` files.

### Loading Stages (from string evidence)

The map loading process follows a defined sequence of stages, each identified by profiling markers:

| Stage | Function String | Address |
|-------|-----------------|---------|
| 1 | `CGameCtnChallenge::LoadDecorationAndCollection` | `0x141c34a30` |
| 2 | `CGameCtnChallenge::InternalLoadDecorationAndCollection` | `0x141c349c0` |
| 3 | `CGameCtnChallenge::UpdateBakedBlockList` | `0x141c34908` |
| 4 | `CGameCtnChallenge::AutoSetIdsForLightMap` | `0x141c34930` |
| 5 | `CGameCtnChallenge::LoadAndInstanciateBlocks` | `0x141c34d48` |
| 6 | `CGameCtnChallenge::InitChallengeData_ClassicBlocks` | `0x141c34d10` |
| 7 | `CGameCtnChallenge::InitChallengeData_Terrain` | `0x141c34e28` |
| 8 | `CGameCtnChallenge::InitChallengeData_DefaultTerrainBaked` | `0x141c34e58` |
| 9 | `CGameCtnChallenge::InitChallengeData_Genealogy` | `0x141c34df8` |
| 10 | `CGameCtnChallenge::InitChallengeData_PylonsBaked` | `0x141c34cd8` |
| 11 | `CGameCtnChallenge::InitChallengeData_ClassicClipsBaked` | `0x141c34e98` |
| 12 | `CGameCtnChallenge::InitChallengeData_FreeClipsBaked` | `0x141c34ed0` |
| 13 | `CGameCtnChallenge::InitChallengeData_Clips` | `0x141c350e0` |
| 14 | `CGameCtnChallenge::CreateFreeClips` | `0x141c98430` |
| 15 | `CGameCtnChallenge::InitPylonsList` | `0x141c98480` |
| 16 | `CGameCtnChallenge::CreatePlayFields` | `0x141c34cb0` |
| 17 | `CGameCtnChallenge::TransferIdForLightMapFromBakedBlocksToBlocks` | `0x141c34f10` |
| 18 | `CGameCtnChallenge::InitEmbeddedItemModels` | `0x141c34fb8` |
| 19 | `CGameCtnChallenge::LoadEmbededItems` | `0x141c34fe8` |
| 20 | `CGameCtnChallenge::InitAllAnchoredObjects` | `0x141c35010` |
| 21 | `CGameCtnChallenge::ConnectAdditionalDataClipsToBakedClips` | `0x141c35040` |
| 22 | `CGameCtnChallenge::RemoveNonBlocksFromBlockStock` | `0x141c35080` |

### Filtered Block Lists

Maps maintain filtered views of their block data:
- `CGameCtnChallenge::SFilteredBlockLists::UpdateFilteredBlocks` (`0x141c35110`)
- `CGameCtnChallenge::SFilteredBlockLists::GetClassicBlocks` (`0x141c35150`)
- `CGameCtnChallenge::SFilteredBlockLists::GetTerrainBlocks` (`0x141c35190`)
- `CGameCtnChallenge::SFilteredBlockLists::GetGhostBlocks` (`0x141c351d0`)

### Related Classes

| Class | String Address | Role |
|-------|----------------|------|
| `CGameCtnChallengeInfo` | `0x141bf9898` | Map metadata/info |
| `CGameCtnChallengeGroup` | `0x141bf98d0` | Group of maps |
| `CGameCtnChallengeParameters` | `0x141c64f20` | Map parameters (time limits, etc.) |
| `CGameCtnReplayRecord` | `0x141c49c50` | Replay data |
| `CGameCtnReplayRecordInfo` | `0x141bf98b0` | Replay metadata |

### Block System Classes

| Class | String Address |
|-------|----------------|
| `CGameCtnBlockInfo` | `0x141bf88d0` |
| `CGameCtnBlockInfoVariant` | `0x141bf88e8` |
| `CGameCtnBlockInfoVariantAir` | `0x141bf8890` |
| `CGameCtnBlockInfoVariantGround` | `0x141bf88b0` |
| `CGameCtnBlockInfoClip` | `0x141bf8860` |
| `CGameCtnBlockInfoFlat` | `0x141c62a28` |
| `CGameCtnBlockInfoFrontier` | `0x141c62c38` |
| `CGameCtnBlockInfoTransition` | `0x141c62e90` |
| `CGameCtnBlockInfoClassic` | `0x141c63070` |
| `CGameCtnBlockInfoRoad` | `0x141c63390` |
| `CGameCtnBlockInfoSlope` | `0x141c63f08` |
| `CGameCtnBlockInfoPylon` | `0x141c640b0` |
| `CGameCtnBlockInfoRectAsym` | `0x141c64358` |
| `CGameCtnBlockInfoClipHorizontal` | `0x141c63a08` |
| `CGameCtnBlockInfoClipVertical` | `0x141c63c30` |
| `CGameCtnBlockInfoMobil` | `0x141c79260` |
| `CGameCtnBlockInfoMobilLink` | `0x141c64db8` |

### Vehicle References in Maps

Vehicle items referenced by maps:
- `\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx` (`0x141c20b98`)
- `\Trackmania\Items\Vehicles\RallyCar.ObjectInfo.Gbx` (`0x141c20a48`)
- `\Trackmania\Items\Vehicles\SnowCar.ObjectInfo.Gbx` (`0x141c20a10`)
- `\Trackmania\Items\Vehicles\DesertCar.ObjectInfo.Gbx` (`0x141c20ab8`)
- `\Trackmania\Items\Vehicles\CanyonCar.ObjectInfo.Gbx` (`0x141c20940`)
- `\Trackmania\Items\Vehicles\LagoonCar.ObjectInfo.Gbx` (`0x141c20908`)
- `\Trackmania\Items\Vehicles\CoastCar.ObjectInfo.Gbx` (`0x141c20af0`)
- `\Trackmania\Items\Vehicles\BayCar.ObjectInfo.Gbx` (`0x141c20b28`)
- `\Trackmania\Items\Vehicles\ValleyCar.ObjectInfo.Gbx` (`0x141c20b60`)
- `\Trackmania\Items\Vehicles\IslandCar.ObjectInfo.Gbx` (`0x141c20a80`)
- `\Vehicles\Items\CarSport.Item.gbx` (`0x141c5a398`)
- `\Vehicles\Items\CarSnow.Item.gbx` (`0x141c5a3c0`)
- `\Vehicles\Items\CarRally.Item.gbx` (`0x141c5a3f0`)
- `\Vehicles\Items\CarDesert.Item.gbx` (`0x141c5a428`)

---

## 10. Key Function Reference Table

| Address | Role | Notes |
|---------|------|-------|
| `FUN_140900e60` | GBX magic + version validation | Reads "GBX", version uint16 |
| `FUN_140901850` | Version 6+ format flag parsing | Reads BUCE/BUCR flags |
| `FUN_140902530` | Reference table loading | External dependency resolution |
| `FUN_140903140` | Class ID -> body type label | Profiling/logging labels |
| `FUN_140903d30` | Load header + body orchestrator | Calls header, body, chunk loaders |
| `FUN_140904730` | CSystemArchiveNod::LoadGbx | Main GBX load entry point |
| `FUN_1402cf380` | CreateByMwClassId | Factory for CMwNod subclasses |
| `FUN_1402f20a0` | Class ID table lookup | Two-level hierarchical lookup with TLS cache |
| `FUN_1402f2610` | Class ID remapping | Legacy -> modern class ID conversion |
| `FUN_1402d0c40` | Chunk end marker check | 0xFACADE01 sentinel detection |
| `FUN_1402d0c80` | Unknown chunk ID handler | Logs "Unknown ChunkId: %08X" |
| `FUN_14012ba00` | CClassicArchive::ReadData | Core binary read with validation |
| `FUN_1409031d0` | Body chunk loader | Decompresses and processes body chunks |
| `FUN_14092bec0` | CSystemFidContainer::InstallFids | Registers pack contents in VFS |
| `FUN_140901a70` | Header chunk reader | Reads individual header chunk entries |

---

## Unknowns and Open Questions

1. **[UNKNOWN]** The exact role of byte 2 in the version 6 format flags (both bytes 1 and 2 seem compression-related, but which is body vs header is not fully confirmed from decompilation alone)
2. **[UNKNOWN]** The complete class info structure layout beyond offsets `+0x08` (name) and `+0x30` (factory)
3. **[UNKNOWN]** How header chunks are individually dispatched to class-specific handlers (the vtable mechanism at the nod level)
4. **[UNKNOWN]** The exact compression algorithm used (likely LZO based on community knowledge, but not confirmed from decompilation)
5. **[UNKNOWN]** The full archive context structure (param_1) layout -- only partial offsets documented
6. **[UNKNOWN]** The relationship between `param_1+0xF8` and deferred/lazy loading
7. **[UNKNOWN]** The full FidFile structure beyond documented offsets
8. **[UNKNOWN]** Whether text format (`'T'` in byte 0) is actually functional in TM2020
9. **[UNKNOWN]** Class IDs for engine `0x06`, `0x11`, and `0x2E` -- what actual classes these correspond to
10. **[UNKNOWN]** The internal format of pack files (`.pack.gbx`) -- how they differ from regular GBX in terms of containing multiple files

# GBX File Format and Parsing

GBX (GameBox) is Nadeo's binary serialization format for all Trackmania game assets. Every `.Gbx` file encodes a single CMwNod-derived object tree using a chunk-based protocol. Understanding GBX is the gateway to reading maps, replays, items, and every other game file.

The GBX format supports three file variants:
- **Binary GBX** (`.gbx`) -- primary format, chunk-based binary serialization
- **XML GBX** (`.gbx.xml`) -- XML representation, loaded via `FUN_140925fa0`
- **JSON** (`.json`) -- JSON import, loaded via `FUN_140934b80`

**Loading entry point**: `FUN_140904730` (CSystemArchiveNod::LoadGbx)

---

## How GBX files are structured

Every GBX file follows a header-references-body layout. The header identifies the file type and provides quick-access metadata. The reference table lists external dependencies. The body carries the serialized data.

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

## How the header is parsed

The header parser (`FUN_140900e60` at `0x140900e60`) reads the magic bytes and version, then hands off to version-specific logic.

### Magic and version

The first 5 bytes identify the file:

1. **3 bytes**: Must match `'G'`, `'B'`, `'X'`
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

### Format flags (version 6+)

`FUN_140901850` at `0x140901850` reads a 4-character format descriptor after the version field.

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

## How the body and chunk system work

The body contains all serialized data for the root node. It is organized as a sequential stream of chunks.

### Reference table loading

`FUN_140902530` at `0x140902530` loads the reference table after the header. This resolves external dependencies (other GBX files referenced by this one).

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

### Body chunk loading

`FUN_1409031d0` at `0x1409031d0` loads the main serialized data from the body.

**Profiling marker**: Uses the output of `FUN_140903140` (e.g., `"ArchiveNod::LoadGbx_Body(Challenge)"`)

Flow:
1. Gets a profiling label based on class ID (see table below)
2. Records stream position and body size at archive offsets `+0x120` (body size) and `+0x124` (end position)
3. **If version == 3**: Reads body as raw blob, stores in a buffer
4. **If version > 3** and body is compressed (offset `+0xDC` != 0):
   - Decompresses body via `FUN_140127aa0` into a memory buffer
   - The decompression buffer is pooled (reused from `DAT_14205c280`)
   - Max decompressed size of 0xFFFFF (~1MB) before pool reuse
5. Resolves **internal references** -- iterates the reference table connecting nodes
6. Calls `FUN_140900560` to associate the main node with the archive

### How chunks end

`FUN_1402d0c40` at `0x1402d0c40` detects the end-of-chunks marker.

- **Chunk ID `0xFACADE01`**: Signals end of chunks (returned by this function for all non-terminal chunk IDs)
- **Chunk ID `0x01001000`**: The actual end-of-chunks marker (CMwNod_End), returns 1

When an unknown chunk ID is encountered, `FUN_1402d0c80` logs:
`"Unknown ChunkId: %08X"` at `0x141b72000`

### Body type labels (class ID to profile label)

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

## How the serialization/archive system works

CClassicArchive is the core archive reader that handles all binary read/write operations.

### CClassicArchive

String evidence:
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

The system-level archive manages loading GBX files from the file system.

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

### Archive version system

String: `"%.*sUnknown archive version %d (> %d)"` at `0x141b72028`

Individual chunks within a GBX body have their own version numbers (independent of the GBX file version). When a chunk's version exceeds what the engine expects, this error is logged. This allows forward compatibility -- newer files can be partially read by older engines.

---

## How class IDs identify node types

Class IDs are 32-bit values encoding the engine namespace, class index, and sub-class information. The engine uses these to look up factory functions that create the correct CMwNod subclass during deserialization.

### Class ID structure

```
  Bits 31-24: Engine ID (top-level namespace)
  Bits 23-12: Class index within engine
  Bits 11-0:  [UNKNOWN - possibly chunk/sub-class index, always 0x000 for class IDs]
```

### Engine IDs

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

### Registration and lookup

**Global class table**: `DAT_141ff9d58`

The table uses a two-level hierarchy:
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

### Class ID remapping (backward compatibility)

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

## What GBX file types exist

Over 431 unique `.Gbx` extension strings appear in the binary. Here are the key categories.

### Map / Challenge

| Extension | Address | Notes |
|-----------|---------|-------|
| `.Map.Gbx` | `0x141c2b290` | Map files (modern name) |
| `.Challenge.Gbx` | `0x141c2dc10` | Map files (legacy name, same format) |

### Replay / Ghost

| Extension | Address | Notes |
|-----------|---------|-------|
| `.Replay.Gbx` | `0x141c2b280` | Replay files |
| `.Ghost.Gbx` | `0x141c40868` | Ghost data (individual runs) |
| `.InputsReplay.Gbx` | `0x141cccef0` | Raw input replay |

### Items / Blocks

| Extension | Address | Notes |
|-----------|---------|-------|
| `.Item.Gbx` | `0x141c2d630` | Custom items |
| `.Block.Gbx` | `0x141c2d740` | Block definitions |
| `.Macroblock.Gbx` | `0x141c2d708` | Macroblock (multi-block groups) |

### Visual / Mesh

| Extension | Address | Notes |
|-----------|---------|-------|
| `.Mesh.Gbx` | `0x141bd5490` | 3D mesh |
| `.Solid2.gbx` | `0x141bd1cd0` | Solid2 model |
| `Material.Gbx` | `0x141ba5d78` | Material definition |
| `Texture.Gbx` | `0x141ba3768` | Texture file |

### Audio

| Extension | Address | Notes |
|-----------|---------|-------|
| `Sound.Gbx` | `0x141ba55f8` | Sound file |
| `Music.Gbx` | `0x141bc2f80` | Music |
| `SoundEngine.Gbx` | `0x141bc2990` | Engine sound model |

### Vehicle

| Extension | Address | Notes |
|-----------|---------|-------|
| `VehicleVisModel.Gbx` | `0x141bd2510` | Vehicle visual model |
| `VehiclePhyModelCustom.Gbx` | `0x141bd5b28` | Vehicle physics model |

### Pack Files

| Extension | Address | Notes |
|-----------|---------|-------|
| `.pack.gbx` | `0x141bbba40` | Generic pack |
| `.Title.Pack.Gbx` | `0x141c2f438` | Title pack |
| `Trackmania.Title.Pack.Gbx` | `0x141bcc828` | Main game title pack |

---

## How the Fid (File ID) system works

The Fid system is Nadeo's virtual file system layer. It abstracts file access across disk, packs, and network backends.

### Class hierarchy

| Class | Address | Role |
|-------|---------|------|
| `CSystemFidFile` | `0x141c07380` | Represents a single file |
| `CSystemFidsFolder` | `0x141c08d68` | Represents a directory/folder |
| `CSystemFidContainer` | `0x141c08ec8` | Contains fids (e.g., a pack file) |
| `CSystemFidsDrive` | `0x141c08ff8` | Top-level drive/mount point |

### Key operations

- **`CSystemFidsFolder::BrowsePath`** (string at `0x141c08d88`): Directory traversal
- **`CSystemFidContainer::InstallFids`** (`FUN_14092bec0` at `0x14092bec0`): Registers files from a container (pack) into the virtual file system
  - Takes a parent folder, container, and various parameters
  - Iterates entries (stride 0x20 per entry) at container offset `+0x18`
  - Creates FidFile entries for each file via `FUN_1408fa7b0`
  - Associates files with their parent container via `FUN_1402cfa80`
  - Sets up file watching if `container+0x80` is non-null
  - Updates folder indices at `container+0x38`

### FidFile layout (partial)

| Offset | Type | Purpose |
|--------|------|---------|
| `+0x08` | ptr | [UNKNOWN] |
| `+0x18` | ptr | Parent folder/container |
| `+0x20` | uint | Flags (bit 0 = [UNKNOWN], bit 2 = [UNKNOWN]) |
| `+0x80` | ptr | Loaded nod pointer (the actual object) |
| `+0xB0` | ptr* | Stream factory (vtable for creating read streams) |
| `+0xD0` | string | File path/name |

### FidCache

`CPlugFileFidCache` (string at `0x141bc4ec8`) and `User.FidCache.Gbx` (at `0x141c30fe0`) indicate a caching layer for file lookups. The `LoadAndRefreshFidCache` operation (string at `0x141c30e70`) suggests the cache persists to disk and refreshes on startup.

---

## How the pack file system works

Pack files bundle multiple GBX files into archives for distribution.

### Pack types

| Pack Type | Extension | Example |
|-----------|-----------|---------|
| Generic pack | `.pack.gbx` | General asset bundles |
| Skin pack | `.skin.pack.gbx` / `.Skin.Pack.Gbx` | Character/vehicle skins |
| Title pack | `.Title.Pack.Gbx` | Full game title content |
| Media pack | `.Media.Pack.Gbx` | Media assets |
| Model pack | `Model.Pack.Gbx` / `-Model.Pack.Gbx` | 3D model collections |

### Pack management

**CSystemPackManager** (strings at `0x141c076d8`):
- `CSystemPackManager::UpdatePackDescsAfterLoad` (`0x141c07820`)
- `CSystemPackManager::LoadCache` (`0x141c078b0`)
- `CSystemPackManager::TrimCacheIfNeeded` (`0x141c079b0`)

### Title packs

The main game content loads from:
- `"Trackmania.Title.Pack.Gbx"` at `0x141bcc828` / `0x141c58368`
- `"Trackmania_Update.Title.Pack.Gbx"` at `0x141c584b0`
- `".Title.Pack.Gbx.ref"` at `0x141c58c50` (reference files that point to actual packs)

---

## How the map loading pipeline works

CGameCtnChallenge (class ID `0x03043000`) is the main map class. "Challenge" is the legacy internal name; externally these are `.Map.Gbx` files.

### Loading stages

The map loading process follows a 22-stage sequence, each identified by profiling markers:

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

### Filtered block lists

Maps maintain filtered views of their block data:
- `CGameCtnChallenge::SFilteredBlockLists::GetClassicBlocks` (`0x141c35150`)
- `CGameCtnChallenge::SFilteredBlockLists::GetTerrainBlocks` (`0x141c35190`)
- `CGameCtnChallenge::SFilteredBlockLists::GetGhostBlocks` (`0x141c351d0`)

### Vehicle references in maps

| Path | Vehicle |
|------|---------|
| `\Vehicles\Items\CarSport.Item.gbx` | CarSport (Stadium) |
| `\Vehicles\Items\CarSnow.Item.gbx` | CarSnow |
| `\Vehicles\Items\CarRally.Item.gbx` | CarRally |
| `\Vehicles\Items\CarDesert.Item.gbx` | CarDesert |

---

## Key function reference

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

## Unknowns and open questions

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

---

## Related Pages

- [GBX File Format Deep Dive](16-fileformat-deep-dive.md) -- byte-level specification and parser pseudocode
- [Real GBX File Analysis](26-real-file-analysis.md) -- hex-level validation against live game data
- [Game Files Analysis](09-game-files-analysis.md) -- DLL, material, and pack file inventory
- [Map Structure Encyclopedia](28-map-structure-encyclopedia.md) -- block, item, and waypoint systems
- [Ghost & Replay Format](30-ghost-replay-format.md) -- ghost sample encoding and replay structure
- [Class Hierarchy](02-class-hierarchy.md) -- complete CMwNod class tree

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**Note**: All function symbols are stripped. Functions are named by Ghidra convention (FUN_<address>).

</details>

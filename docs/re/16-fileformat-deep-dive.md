# GBX File Format Deep Dive

**Binary**: `Trackmania.exe` (Trackmania 2020)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**Purpose**: Complete GBX format specification sufficient to implement a parser

---

## Table of Contents

**Reference Sections:**
1. [GBX Binary Format Overview](#1-gbx-binary-format-overview)
2. [Complete Header Specification](#2-complete-header-specification)
3. [Format Flags (Version 6+)](#3-format-flags-version-6)
4. [Header Chunk Table](#4-header-chunk-table)
5. [Reference Table](#5-reference-table)
6. [Body Chunk System](#6-body-chunk-system)
7. [Chunk Dispatch and End Sentinel](#7-chunk-dispatch-and-end-sentinel)
8. [Compression System](#8-compression-system)
9. [Class Factory (CreateByMwClassId)](#9-class-factory-createbymwclassid)
10. [Class ID Two-Level Registry](#10-class-id-two-level-registry)
11. [Class ID Remapping (Legacy Compatibility)](#11-class-id-remapping-legacy-compatibility)
12. [Serialization System (CClassicArchive)](#12-serialization-system-cclassicarchive)
13. [String Serialization](#13-string-serialization)
14. [Array Serialization](#14-array-serialization)
15. [Object Reference Serialization](#15-object-reference-serialization)
16. [Map File Structure (CGameCtnChallenge)](#16-map-file-structure-cgamectnchallenge)
17. [Ghost / Replay Structure](#17-ghost--replay-structure)
18. [Item File Structure (CGameItemModel)](#18-item-file-structure-cgameitemmodel)
19. [Mesh / Solid2 Structure](#19-mesh--solid2-structure)
20. [Material and Texture Files](#20-material-and-texture-files)
21. [Pack File System](#21-pack-file-system)
22. [Fid (Virtual File System)](#22-fid-virtual-file-system)
23. [Complete Class ID Remap Table](#23-complete-class-id-remap-table)
24. [Complete Engine ID Table](#24-complete-engine-id-table)
25. [Parser Pseudocode](#25-parser-pseudocode)

**Parsing Tutorial (validated against real files):**
26. [Parsing Tutorial: Byte 0 to Parsed Tree](#26-parsing-tutorial-byte-0-to-parsed-tree)
27. [Hex Dump Walkthrough: Real .Map.Gbx](#27-hex-dump-walkthrough-real-mapgbx)
28. [Data Type Serialization Reference](#28-data-type-serialization-reference)
29. [LookbackString Deep Dive (Corrected)](#29-lookbackstring-deep-dive-corrected)
30. [TypeScript Parser Implementation Guide](#30-typescript-parser-implementation-guide)
31. [Quick Reference Card](#31-quick-reference-card)
32. [Cross-File Validation Results](#32-cross-file-validation-results)

---

## 1. GBX Binary Format Overview

GBX (GameBox) is Nadeo's proprietary binary serialization format. Every `.Gbx` file encodes a single `CMwNod`-derived object tree using a chunk-based serialization protocol. The format has evolved through 6 major versions; Trackmania 2020 uses version 6.

### Top-Level File Layout

```
+=======================================+
| HEADER SECTION                        |
|   Magic: "GBX" (3 bytes)             |
|   Version (uint16)                    |
|   Format Flags (4 bytes, v6+)         |
|   Class ID (uint32)                   |
|   User Data Size (uint32)             |
|   Header Chunk Count (uint32)         |
|   Header Chunk Index Table            |
|   Header Chunk Data                   |
+=======================================+
| NODE COUNT (uint32)                   |
+=======================================+
| REFERENCE TABLE SECTION               |
|   External Reference Count (uint32)   |
|   Ancestor Level Count (uint32)       |
|   Ancestor Folder Paths               |
|   Reference Entries                   |
+=======================================+
| BODY SECTION                          |
|   (If compressed):                    |
|     Uncompressed Size (uint32)        |
|     Compressed Size (uint32)          |
|     Compressed Data (bytes)           |
|   (If uncompressed):                  |
|     Body Chunk Stream                 |
+=======================================+
```

**Code evidence**: Entry point is `FUN_140904730` (`CSystemArchiveNod::LoadGbx`).
The loading pipeline supports three file variants:
- Binary GBX (`.gbx`) -- primary format
- XML GBX (`.gbx.xml`) -- loaded via `FUN_140925fa0`
- JSON (`.json`) -- loaded via `FUN_140934b80`

**Error strings confirming format**:
- `"Wrong .Gbx format : not a < GameBox > file"` at `0x141c067a8`
- `"Wrong .Gbx format : request a GameBox version between the %s and the %s"` at `0x141c06820`
- `"[Sys] Corrupted data while reading .gbx file"` at `0x141c06ac0`

---

## 2. Complete Header Specification

### Byte-by-Byte Header Format

```
Offset  Size    Type      Field                Description
------  ----    ----      -----                -----------
0x00    3       char[3]   magic                "GBX" (0x47, 0x42, 0x58)
0x03    2       uint16    version              GBX format version (3-6 supported)
0x05    4       char[4]   format_flags         Only present if version >= 6
0x09    4       uint32    class_id             MwClassId of the root node
0x0D    4       uint32    user_data_size       Total size of header chunk data (bytes)
0x11    4       uint32    num_header_chunks    Number of header chunk entries
0x15    var     ...       header_chunk_index   Array of (chunk_id, chunk_size) pairs
var     var     ...       header_chunk_data    Concatenated header chunk payloads
var     4       uint32    num_nodes            Total node count (for reference table sizing)
```

Note: For versions 3-5, `format_flags` is absent and offset shifts accordingly. Version 6 is standard for TM2020.

**Code evidence** (`FUN_140900e60`):
```c
// Read 3 bytes: expects 'G', 'B', 'X'
iVar3 = vtable_read(stream, &local_1c8, 3);
if ((iVar3 == 3) && (local_1c8 == 'G') && (local_1c7 == 'B') && (local_1c6 == 'X')) {
    // Read 2-byte version number
    FUN_14012ba00(param_1, local_1c4, 2);  // ReadData(archive, &version, 2)
    *(ushort *)(param_1 + 0x60) = local_1c4[0];  // Store version at offset 0x60
```

### Version Support Matrix

| Version | Status | Era | Notes |
|---------|--------|-----|-------|
| 1 | Rejected | "August 2000" | Ancient format |
| 2 | Rejected | "August 2000" | Ancient format |
| 3 | Supported | ManiaPlanet era | Legacy, body stored as raw blob |
| 4 | Supported | ManiaPlanet era | Adds reference table improvements |
| 5 | Supported | ManiaPlanet era | Adds chunk size fields in ref table |
| 6 | Supported | TM2020 current | Adds format flags (BUCE/BUCR) |

Version stored at archive offset `+0x60` as `uint16`.

---

## 3. Format Flags (Version 6+)

For version >= 6, a 4-byte format descriptor immediately follows the version field. This is the most critical part of header parsing for TM2020 files.

### Format Flag Bytes

```
Byte  Offset  Values       Stored At        Meaning
----  ------  ------       ---------        -------
0     +0x05   'B' / 'T'    (controls flow)  Binary / Text format
1     +0x06   'C' / 'U'    param_1+0xD8     Body compression: Compressed / Uncompressed
2     +0x07   'C' / 'U'    param_1+0xDC     Body stream compression: Compressed / Uncompressed
3     +0x08   'R' / 'E'    (controls flow)  With References / No External Refs
```

**Code evidence** (`FUN_140901850`):
```c
// Read 4-byte format descriptor
FUN_14012ba00(param_1, &local_res10, 4);

// Byte 0: 'T' (text=1) or 'B' (binary=0)
if (((char)local_res10 == 'T') || (iVar3 = 0, (char)local_res10 == 'B')) {
    // Byte 1: 'C' (compressed=1) or 'U' (uncompressed=0)
    *(int *)(param_1 + 0xd8) = iVar2;  // Store body compression flag
    // Byte 2: 'C' (compressed=1) or 'U' (uncompressed=0)
    *(int *)(param_1 + 0xdc) = iVar5;  // Store second compression flag
    // Byte 3: 'R' (with refs) or 'E' (no external refs)
```

### Common Format Strings

| String | Meaning |
|--------|---------|
| `BUCR` | Binary, Uncompressed byte 1, Compressed byte 2, with References |
| `BUCE` | Binary, Uncompressed byte 1, Compressed byte 2, no External refs |
| `BUCU` | Binary, fully Uncompressed, no refs [UNKNOWN if used in practice] |

**Important**: Only binary format (`'B'`) proceeds to full body parsing. Text format (`'T'`) is recognized syntactically but [UNKNOWN if functionally supported in TM2020]. The parser MUST check byte 0 == `'B'` before continuing.

### Interpretation of Bytes 1 and 2

Based on decompilation evidence:
- **Byte 1** (stored at `+0xD8`): Controls whether the body data region as a whole is compressed
- **Byte 2** (stored at `+0xDC`): Controls whether the body chunk stream is decompressed via `FUN_140127aa0` before chunk parsing. When the body loader (`FUN_1409031d0`) runs, it checks `param_1+0xDC` to determine if decompression is needed.

In practice, most TM2020 `.Gbx` files use `'U'` for byte 1 and `'C'` for byte 2, meaning the body itself is wrapped in a compression envelope but the individual chunks within are not further compressed.

---

## 4. Header Chunk Table

After the format flags and class ID, the header contains a chunk table that provides metadata accessible without parsing the body.

### Header Chunk Table Format

```
Offset  Size    Type      Field
------  ----    ----      -----
+0x00   4       uint32    user_data_size    Total bytes of all header chunk data combined
+0x04   4       uint32    num_chunks        Number of header chunks

Then, for each chunk (num_chunks times):
+0x00   4       uint32    chunk_id          The chunk's class+chunk identifier
+0x04   4       uint32    chunk_size        Size of this chunk's data (masked)
                                            Bit 31: "heavy" flag (1 = skip unless needed)
                                            Bits 0-30: actual size in bytes

Then, concatenated header chunk data follows (total = user_data_size bytes).
```

### Header Chunk Index Parsing Pseudocode

```
chunk_entries = []
for i in range(num_chunks):
    chunk_id = read_uint32()
    chunk_size_raw = read_uint32()
    is_heavy = (chunk_size_raw & 0x80000000) != 0
    chunk_size = chunk_size_raw & 0x7FFFFFFF
    chunk_entries.append((chunk_id, chunk_size, is_heavy))

# Then read the actual data
for (chunk_id, chunk_size, is_heavy) in chunk_entries:
    chunk_data = read_bytes(chunk_size)
    # Dispatch chunk_data based on chunk_id
```

**Code evidence**: Header chunk reading is handled by `FUN_140901a70`. The "heavy" bit (bit 31) allows a parser to skip expensive header chunks that are not immediately needed (e.g., thumbnail data in map files).

### Known Header Chunk IDs (CGameCtnChallenge / 0x03043000)

For map files, known header chunks include:

| Chunk ID | Content |
|----------|---------|
| `0x03043002` | Map info (map UID, environment, author) |
| `0x03043003` | Common map header (map name, author name, etc.) |
| `0x03043004` | Map version info |
| `0x03043005` | Community reference |
| `0x03043007` | Thumbnail + comments |
| `0x03043008` | Author info (author zone, extra info) |

Each header chunk internally starts with a version byte that allows forward compatibility.

---

## 5. Reference Table

The reference table is located between the header chunks and the body. It lists all external GBX files that this file depends on.

### Reference Table Format

```
Offset  Size    Type        Field
------  ----    ----        -----
+0x00   4       uint32      num_external_nodes     Number of external references (max 49,999)
                                                   If 0, reference section ends here.

If num_external_nodes > 0:
+0x04   4       uint32      ancestor_level_count   Number of ancestor folders (max 99)

For each ancestor level:
+0x00   var     string      folder_name            Folder path component (length-prefixed)

+0x00   4       uint32      num_ref_entries        Number of reference entries (max 99)

For each reference entry (num_ref_entries times):
+0x00   4       uint32      flags                  [UNKNOWN exact bit layout]
+0x04   var     string      file_name              Referenced file name (if not using index)
  -- OR --
+0x04   4       uint32      resource_index         Index into ancestor folder hierarchy
+0x08   4       uint32      node_index             Which node slot this reference fills
  -- version >= 5 additions: --
+0x0C   4       uint32      use_file               1 = external file, 0 = [UNKNOWN]
+0x10   4       uint32      folder_index           Index into ancestor folders

For each external node (num_external_nodes times):
+0x00   4       uint32      class_id               Class ID of the referenced node
```

**Code evidence**: Reference table is loaded by `FUN_140902530`.
- Profiling marker: `"NSys::ArLoadRef_Gbx"` (version 7) or `"NSys::ArLoadRef"` (others)
- The sentinel value `0xDEADBEEF` is written as a placeholder during reference resolution (visible at address `0x140902994`)
- Maximum 50,000 entries enforced by sanity check in `FUN_140901850`:
  ```c
  if (local_res18[0] - 1 < 50000) {
      // Initialize reference table (array of 0x10-byte entries)
  ```

### Reference Table Entry Layout (Internal)

Each reference in the archive's internal table at `param_1+0x50` is a 0x10-byte structure:

```
Offset  Size  Type      Field
------  ----  ----      -----
+0x00   8     ptr       nod_pointer    Pointer to loaded CMwNod (0 if not yet loaded)
+0x08   4     uint32    flags          State/type flags
+0x0C   4     uint32    class_id       Class ID (or 0)
```

### Path Resolution

Ancestor folders establish a hierarchy of directory prefixes. When resolving a reference:
1. Start from the file's own directory
2. Walk up `folder_index` levels using the ancestor folder chain
3. Append the `file_name` to get the full path
4. Look up the file via the Fid (virtual filesystem) system

---

## 6. Body Chunk System

The body section contains the actual serialized data for the root node and all inline sub-nodes. It is organized as a sequential stream of chunks.

### Body Loading Flow

**Code evidence** (`FUN_140903d30` / `FUN_1409031d0`):

```
1. FUN_14012b990(archive, 0)       -- Reset stream position
2. FUN_140900e60(archive)          -- Load header (magic, version, flags, class ID, refs)
3. FUN_1402cf380(class_id)         -- Create root node instance via class factory
4. FUN_1409036d0(archive, ...)     -- Set up reference tracking
5. FUN_140902530(archive)          -- Load reference table (external deps)
6. FUN_1409031d0(archive, node)    -- Load body chunks
7. FUN_140903aa0(archive, node)    -- Finalize references
```

### Compressed Body Format

When byte 2 of format flags is `'C'` (compressed), the body is wrapped:

```
Offset  Size    Type      Field
------  ----    ----      -----
+0x00   4       uint32    uncompressed_size    Size of body data after decompression
+0x04   4       uint32    compressed_size      Size of the compressed blob
+0x08   var     bytes     compressed_data      Compressed body (compressed_size bytes)
```

After decompression, the result is a flat byte stream of body chunks.

**Code evidence** (`FUN_1409031d0`):
```c
// If body is compressed (offset +0xDC != 0):
// Decompresses body via FUN_140127aa0 into a memory buffer
// The decompression buffer is pooled (reused from DAT_14205c280)
// Max decompressed size of 0xFFFFF (~1MB) before pool reuse
```

### Uncompressed Body Format

When not compressed, the body is simply a sequential stream of chunks read directly from the file stream.

### Body Chunk Stream Format

Each chunk in the body stream:

```
+0x00   4       uint32    chunk_id      Chunk identifier (class_id_base | chunk_index)
                                        Special: 0xFACADE01 = end of body

If chunk is a "skippable" chunk:
+0x04   4       uint32    skip_marker   Must be 0x534B4950 ("SKIP" in ASCII)
+0x08   4       uint32    chunk_size    Size of chunk data in bytes
+0x0C   var     bytes     chunk_data    The serialized chunk payload

If chunk is NOT skippable:
+0x04   var     bytes     chunk_data    The serialized chunk payload (read until done)
```

**Skippable chunks**: A chunk is "skippable" if the 4 bytes after the chunk ID equal `0x534B4950` ("SKIP"). This allows parsers to skip over unknown chunks by reading `chunk_size` bytes. Non-skippable chunks must be fully understood by the parser since there is no size prefix to skip over.

### Chunk ID Structure

A chunk ID encodes both the class and the specific chunk:

```
Bits 31-12:  Class ID base (same as the MwClassId with low 12 bits zeroed)
Bits 11-0:   Chunk index within the class (0x000, 0x001, 0x002, ...)
```

For example, for `CGameCtnChallenge` (class `0x03043000`):
- Chunk `0x03043002` = chunk index 0x002 (map info)
- Chunk `0x0304300D` = chunk index 0x00D (vehicle reference)
- Chunk `0x03043011` = chunk index 0x011 (block data)
- Chunk `0x0304301F` = chunk index 0x01F (item placement)

### Chunk Versioning

Individual chunks have their own internal version numbers, independent of the GBX file version:

```c
// Inside a chunk handler:
uint32 chunk_version = archive.ReadUInt32();
if (chunk_version > MAX_KNOWN_VERSION) {
    // Log: "Unknown archive version %d (> %d)"
}
```

**Code evidence**: String `"%.*sUnknown archive version %d (> %d)"` at `0x141b72028`.

---

## 7. Chunk Dispatch and End Sentinel

### End-of-Body Sentinel: 0xFACADE01

The body chunk stream terminates when the reader encounters the chunk ID `0xFACADE01`.

**Code evidence** (`FUN_1402d0c40`):
```c
undefined8 FUN_1402d0c40(int param_1)
{
    undefined8 uVar1;
    uVar1 = 1;
    if (param_1 != 0x1001000) {
        uVar1 = 0xfacade01;
    }
    return uVar1;
}
```

This function returns:
- `1` when `chunk_id == 0x01001000` (CMwNod end marker, a legitimate end-of-chunks signal)
- `0xFACADE01` for all other chunk IDs (meaning "not end, continue reading")

The sentinel `0xFACADE01` is both the return value for "not end" and the actual chunk ID value written into the file to signal end-of-body. When reading the chunk stream:

```
loop:
    chunk_id = read_uint32()
    if chunk_id == 0xFACADE01:
        break  // End of body
    dispatch_chunk(chunk_id)
```

### Unknown Chunk Handling

When an unknown chunk ID is encountered, `FUN_1402d0c80` logs:
`"Unknown ChunkId: %08X"` at `0x141b72000`

For skippable chunks, the parser can safely skip `chunk_size` bytes. For non-skippable unknown chunks, parsing fails.

---

## 8. Compression System

### Algorithm

The compression algorithm used in GBX files is **LZO1X** (Lempel-Ziv-Oberhumer). This is confirmed by multiple evidence sources:

Evidence:
- The decompression function `FUN_140127aa0` is called from the body loader when `param_1+0xDC` is non-zero
- The `CClassicBuffer` class has an `UncompressBlock` method (from class hierarchy: `"CClassicBuffer": ["UncompressBlock"]`)
- The compression buffer pool at `DAT_14205c280` with max decompressed size `0xFFFFF` (~1MB) is consistent with LZO's streaming decompression model
- **Real file validation**: Compressed body data in TechFlow.Map.Gbx starts with byte 0x1A (26), which in LZO1X means "initial literal run of 9 bytes" (26-17=9). The Item.Gbx starts with 0x34 (52), meaning "initial literal of 35 bytes" (52-17=35). Both patterns are consistent with LZO1X encoding.
- Community tools (GBX.NET, gbx-py) all use LZO for decompression
- It is NOT zlib (tested: both zlib and raw deflate fail on the compressed data)

The exact variant is likely LZO1X-1 for decompression compatibility. LZO1X-999 may be used for writing (produces smaller output, same decompression format).

### Where Compression Applies

| Location | Controlled By | Notes |
|----------|---------------|-------|
| Body section | Format flag byte 2 (`'C'`/`'U'`) | Most common compression point |
| Header chunks | [UNKNOWN] | Headers appear to be uncompressed in practice |
| Individual chunks within body | [UNKNOWN] | Some chunks may have their own compression |
| Pack files | [UNKNOWN] | Packs may use different compression |

### Compressed Body Decompression

```
// Pseudocode for body decompression:
if format_flags[2] == 'C':  // Byte at archive+0xDC
    uncompressed_size = read_uint32()
    compressed_size = read_uint32()
    compressed_data = read_bytes(compressed_size)
    body_data = lzo_decompress(compressed_data, uncompressed_size)
else:
    body_data = read_remaining()  // Read body directly
```

The decompression buffer is pooled and reused from `DAT_14205c280`. When `uncompressed_size > 0xFFFFF` (~1MB), the pool is bypassed and a fresh allocation is made.

---

## 9. Class Factory (CreateByMwClassId)

### Overview

`FUN_1402cf380` (`CMwNod::CreateByMwClassId`) is the factory function that instantiates GBX node objects during deserialization. It is called after the header is parsed to create the root object, and recursively for embedded objects.

### Factory Pipeline

```
1. Input: class_id (uint32)
2. Lookup class_info = FUN_1402f20a0(DAT_141ff9d58, class_id)
     - This normalizes legacy IDs via FUN_1402f2610
     - Uses TLS MRU cache for fast repeated lookups
     - Returns pointer to class info entry, or NULL
3. If class_info != NULL and class_info+0x30 != NULL:
     - Call factory function: node = (*(class_info+0x30))()
     - Return node
4. If class_info != NULL but class_info+0x30 == NULL:
     - Log: "[MwNod] Trying to CreateByMwClassId('<classname>') which is pure..."
     - Return NULL (abstract class, cannot instantiate)
5. If class_info == NULL:
     - Log: "[MwNod] Trying to CreateByMwClassId(<id>) which is unknown..."
     - Return NULL (unknown class)
```

**Code evidence** (`FUN_1402cf380`):
```c
lVar3 = FUN_1402f20a0(&DAT_141ff9d58, param_1);
if ((lVar3 != 0) && (*(code **)(lVar3 + 0x30) != (code *)0x0)) {
    uVar4 = (**(code **)(lVar3 + 0x30))();
    return uVar4;
}
```

### Class Info Entry Layout

Each class info structure (returned by the lookup):

```
Offset  Size  Type            Field
------  ----  ----            -----
+0x00   8     ptr             [UNKNOWN - possibly vtable or type_info pointer]
+0x08   8     const char*     class_name       Human-readable class name (e.g., "CGameCtnChallenge")
+0x10   8     ptr             [UNKNOWN - possibly parent class info pointer]
+0x18   8     ptr             [UNKNOWN]
+0x20   8     ptr             [UNKNOWN]
+0x28   8     ptr             [UNKNOWN]
+0x30   8     code*           factory_func     Constructor/factory function (NULL if abstract)
+0x38   ...   ...             [UNKNOWN additional fields]
```

---

## 10. Class ID Two-Level Registry

### Global Registry Structure

The global class table lives at `DAT_141ff9d58`. It is organized as a two-level hierarchy for efficient O(1) lookup by class ID.

**Code evidence** (`FUN_1402f20a0`):

### Registry Layout

```
DAT_141ff9d58 (Global Class Table):
  +0x00   8     ptr         [UNKNOWN]
  +0x08   8     ptr         engine_array       Pointer to array of engine pointers
  +0x10   4     uint32      engine_count       Number of engines (at least 0x30)

engine_array[engine_index]:
  Each entry is a pointer to an engine descriptor:
  +0x00   8     ptr         [UNKNOWN]
  +0x08   8     ptr         [UNKNOWN]
  +0x10   8     const char* engine_name        e.g., "Game", "Plug", "System"
  +0x18   4     uint32      class_count        Number of classes in this engine
  +0x20   8     ptr         class_array        Pointer to array of class info pointers

class_array[class_index]:
  Each entry is a pointer to a class info structure (see section 9)
```

### Class ID Decomposition

```
uint32 class_id = 0x03043000;  // CGameCtnChallenge

// After normalization via FUN_1402f2610:
uint engine_index = class_id >> 24;           // 0x03 = Game engine
uint class_index  = (class_id >> 12) & 0xFFF; // 0x043 = class #67
uint chunk_index  = class_id & 0xFFF;          // 0x000 (always 0 for class IDs)
```

Lookup:
```c
longlong engine = engine_array[engine_index];  // engine_array[0x03]
if (engine != NULL && class_index < engine->class_count) {
    longlong class_info = engine->class_array[class_index];  // class_array[0x043]
    return class_info;
}
return NULL;
```

### TLS MRU Cache

The lookup function uses a 2-entry Most-Recently-Used cache in Thread-Local Storage to avoid repeated table lookups:

```
TLS Offset  Type      Purpose
----------  ----      -------
+0x1190     ptr       Last lookup result (class_info pointer)
+0x1198     ptr       Second-to-last lookup result
+0x11A4     uint32    Cache flags
+0x11A8     uint32    Last class ID queried
+0x11AC     uint32    Second-to-last class ID queried
```

**Code evidence**:
```c
// Cache hit check:
if (param_2 == *(int *)(tls + 0x11a8))
    return *(longlong *)(tls + 0x1190);  // MRU hit
if (param_2 == *(int *)(tls + 0x11ac))
    return *(longlong *)(tls + 0x1198);  // Second MRU hit
```

### Special Class IDs

| Class ID | Special Handling |
|----------|------------------|
| `0x01001000` | CMwNod end marker (not a real class, used as chunk stream terminator) |
| `0x0C00B000` | Silently ignored on lookup miss (no error logged) |

---

## 11. Class ID Remapping (Legacy Compatibility)

### Overview

`FUN_1402f2610` is a massive switch/lookup table that converts legacy class IDs to their modern equivalents. This is the backward compatibility layer enabling TM2020 to read GBX files from all previous ManiaPlanet and Trackmania versions.

The remapping is applied during the class ID lookup in `FUN_1402f20a0`, before the two-level table lookup.

### Remapping Groups

#### Engine 0x24 (Old Game) -> Engine 0x03 (Modern Game)

The bulk of remappings convert the old `0x24xxx` Game engine namespace to the modern `0x03xxx` namespace:

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x24003000` | `0x03043000` | CGameCtnChallenge (Map) |
| `0x24004000` | `0x03033000` | [UNKNOWN Game class] |
| `0x2400C000` | `0x0303E000` | [UNKNOWN] |
| `0x2400D000` | `0x03031000` | [UNKNOWN] |
| `0x2400E000` | `0x03032000` | [UNKNOWN] |
| `0x24011000` | `0x03053000` | [UNKNOWN] |
| `0x24014000` | `0x03038000` | [UNKNOWN] |
| `0x24015000` | `0x03039000` | [UNKNOWN] |
| `0x24019000` | `0x03027000` | [UNKNOWN] |
| `0x2401B000` | `0x0301A000` | [UNKNOWN] |
| `0x2401C000` | `0x03006000` | [UNKNOWN] |
| `0x2401F000` | `0x03036000` | [UNKNOWN] |
| `0x24022000` | `0x0300C000` | [UNKNOWN] |
| `0x24025000` | `0x0300D000` | [UNKNOWN] |
| `0x2403F000` | `0x03093000` | CGameCtnReplayRecord |
| `0x24099000` | `0x0309A000` | [Control card class] |

#### Engine 0x0A (Old Scene) -> Engine 0x09 (Modern Plug)

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x0A001000` | `0x09144000` | [UNKNOWN Plug class] |
| `0x0A002000` | `0x09145000` | [UNKNOWN] |
| `0x0A003000` | `0x090F4000` | [UNKNOWN] |
| `0x0A005000` | `0x09006000` | [UNKNOWN - visual/mesh] |
| `0x0A006000` | `0x09003000` | [UNKNOWN] |
| `0x0A00A000` | `0x09004000` | [UNKNOWN] |
| `0x0A012000` | `0x09007000` | [UNKNOWN] |
| `0x0A014000` | `0x09008000` | [UNKNOWN] |
| `0x0A015000` | `0x0900C000` | [UNKNOWN] |
| `0x0A019000` | `0x0900F000` | [UNKNOWN] |
| `0x0A01A000` | `0x09010000` | [UNKNOWN] |
| `0x0A01B000` | `0x09011000` | CPlugBitmap |
| `0x0A01C000` | `0x09012000` | [UNKNOWN] |
| `0x0A020000` | `0x09015000` | [UNKNOWN] |
| `0x0A024000` | `0x09014000` | [UNKNOWN] |
| `0x0A028000` | `0x09019000` | [UNKNOWN] |
| `0x0A02B000` | `0x09018000` | [UNKNOWN] |
| `0x0A02C000` | `0x0901B000` | [UNKNOWN] |
| `0x0A030000` | `0x0901C000` | [UNKNOWN] |
| `0x0A031000` | `0x0901D000` | [UNKNOWN] |
| `0x0A032000` | `0x0901F000` | [UNKNOWN] |
| `0x0A036000` | `0x09024000` | [UNKNOWN] |
| `0x0A03B000` | `0x09025000` | [UNKNOWN - visual related] |
| `0x0A03C000` | `0x09026000` | CPlugShaderApply (Material) |
| `0x0A03D000` | `0x0C030000` | [Remapped to Control engine] |
| `0x0A040000` | `0x09080000` | [UNKNOWN] |
| `0x0A06A000` | `0x090E5000` | [UNKNOWN Plug class] |

#### Engine 0x08 (Old Graphic) -> Engine 0x09 (Modern Plug)

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x08002000` | `0x090B1000` | [UNKNOWN] |
| `0x08005000` | `0x090B2000` | [UNKNOWN] |
| `0x08008000` | `0x090B3000` | [UNKNOWN] |
| `0x08009000` | `0x090B4000` | [UNKNOWN] |
| `0x08010000` | `0x090B5000` | [UNKNOWN graphic -> plug] |
| `0x08016000` | `0x090B6000` | [UNKNOWN] |
| `0x08017000` | `0x090B7000` | [UNKNOWN] |
| `0x08019000` | `0x090B8000` | [UNKNOWN] |
| `0x0801A000` | `0x090B9000` | [UNKNOWN] |
| `0x0801B000` | `0x090BA000` | [UNKNOWN] |
| `0x0801C000` | `0x090BB000` | CPlugSolid2Model |

#### Engine 0x05 (Old Function) -> Engine 0x09 (Modern Plug)

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x05001000` | `0x09081000` | [UNKNOWN] |
| `0x05002000` | `0x09082000` | [UNKNOWN] |
| `0x05012000` | `0x09083000` | [UNKNOWN] |
| `0x05013000` | `0x09084000` | [UNKNOWN] |

#### Engine 0x07 -> Engine 0x09

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x07002000` | `0x09091000` | [UNKNOWN] |
| `0x07003000` | `0x09092000` | [UNKNOWN] |
| `0x07004000` | `0x09093000` | [UNKNOWN] |
| `0x0702B000` | `0x09093000` | [UNKNOWN - same target as 0x07004000] |

#### Engine 0x06 Remappings

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x06004000` | `0x09070000` | [UNKNOWN] |
| `0x06005000` | `0x09071000` | [UNKNOWN] |

#### Cross-Engine Remappings

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x03168000` | `0x09189000` | [Game -> Plug remap] |
| `0x2E035000` | `0x09189000` | [Engine 0x2E -> Plug, same target] |
| `0x0A03D000` | `0x0C030000` | [Scene -> Control engine] |

#### Engine 0x11 Remappings

| Old ID | New ID | Known Class |
|--------|--------|-------------|
| `0x0313C000` | `0x11001000` | [Game -> Engine 0x11] |

### Key Insight for Parser Implementors

The remapping function **MUST** be applied before any class ID lookup. When reading chunk IDs from old GBX files, the class portion of the chunk ID (bits 31-12) may use legacy engine namespaces. The correct procedure is:

```
raw_class_id = chunk_id & 0xFFFFF000
normalized_class_id = remap(raw_class_id)
chunk_index = chunk_id & 0x00000FFF
normalized_chunk_id = normalized_class_id | chunk_index
```

---

## 12. Serialization System (CClassicArchive)

### Archive Object Layout

The `CClassicArchive` (and its subclass `CSystemArchiveNod`) is the central context object for all GBX read/write operations. Every ReadXxx/WriteXxx call takes the archive as its first parameter.

| Offset | Type | Purpose | Evidence |
|--------|------|---------|----------|
| `+0x00` | vtable* | Virtual function table | Standard C++ |
| `+0x08` | stream* | Underlying read/write stream | Used by ReadData for vtable calls |
| `+0x10` | int | Mode flags | [UNKNOWN exact meaning] |
| `+0x28` | int | Error flag | 0 = OK, non-zero = error. Checked for return value. |
| `+0x40` | array* | Header chunk data array | 0x20-byte stride per chunk entry |
| `+0x48` | uint | Header chunk count | |
| `+0x50` | array* | Reference table | 0x10-byte stride per entry |
| `+0x58` | uint | Reference count | |
| `+0x60` | uint16 | GBX version number | Set by `FUN_140900e60` |
| `+0x64` | int | Format/mode byte | Version 3 = special mode |
| `+0x7C` | int | [UNKNOWN flag] | |
| `+0x88` | int | FidFile loaded flag | |
| `+0x90` | FidFile* | Associated file descriptor | Used to resolve paths |
| `+0xA0` | uint32 | Main class ID | Root node's MwClassId |
| `+0xD8` | int | Body compression flag | From format flag byte 1 |
| `+0xDC` | int | Body stream compression | From format flag byte 2 |
| `+0xE8` | array* | Ancestor/dependency array | |
| `+0xF0` | uint | Ancestor count | |
| `+0xF8` | ptr | Deferred load context | [UNKNOWN - lazy loading?] |
| `+0x120` | int | Body size in bytes | |
| `+0x124` | uint32 | Stream end position | |
| `+0x128` | ptr | Raw body buffer | Used for version 3 raw blob |
| `+0x130` | longlong | Secondary archive context | [UNKNOWN - nested loading?] |

### Core Read Functions

#### ReadData (`FUN_14012ba00`)

The fundamental binary read operation:

```c
// Reads exactly 'size' bytes from the stream into 'buffer'
// On failure, sets error flag at param_1+0x28
// Logs: "CClassicArchive::ReadData() failed on \"<filename>\""
void ReadData(archive, buffer, size) {
    int bytes_read = archive->stream->vtable->read(archive->stream, buffer, size);
    if (bytes_read != size) {
        archive->error_flag = 1;
        // Log error with archive name
    }
}
```

#### Primitive Type Reads

All primitive types are read via `ReadData` with appropriate sizes:

| Method | Size | Notes |
|--------|------|-------|
| `ReadBool` | 4 bytes | Bool is stored as uint32 (0 or 1) |
| `ReadByte` | 1 byte | |
| `ReadUInt16` | 2 bytes | Little-endian |
| `ReadInt32` / `ReadUInt32` | 4 bytes | Little-endian |
| `ReadInt64` / `ReadUInt64` | 8 bytes | Little-endian |
| `ReadFloat` | 4 bytes | IEEE 754 single |
| `ReadDouble` | 8 bytes | IEEE 754 double |
| `ReadVec2` | 8 bytes | Two floats (x, y) |
| `ReadVec3` | 12 bytes | Three floats (x, y, z) |
| `ReadVec4` / `ReadQuat` | 16 bytes | Four floats |
| `ReadColor` | 16 bytes | Four floats (r, g, b, a) |
| `ReadNat3` | 12 bytes | Three uint32 (used for block coords) |
| `ReadId` | 4 bytes | See LookbackString below |

### Archive Operation Markers

String evidence for named profiling markers:

| Marker | Address |
|--------|---------|
| `"ArchiveNod::LoadGbx"` | `0x141c06b98` |
| `"ArchiveNod::LoadHeader"` | `0x141c06808` |
| `"ArchiveNod::LoadMemory"` | `0x141c06bb0` |
| `"ArchiveNod::ImportMedia"` | `0x141c06af0` |
| `"ArchiveNod::Parametrization"` | `0x141c06b38` |
| `"ArchiveNod::Duplicate"` | `0x141c06b58` |
| `"ArchiveNod::LookupNod"` | `0x141c067f0` |

### Save System

The archive also supports writing:

```
"[Archive] SAVING ERROR: Saving skipped datas => data may be lost !!" at 0x141b582c0
```

This confirms that the same archive system handles both read and write operations. The skip mechanism for unknown chunks means that round-tripping (load + save) must preserve unknown chunk data.

---

## 13. String Serialization

### Standard String Format

Strings in GBX are length-prefixed:

```
+0x00   4       uint32    length    String length in bytes (NOT including null terminator)
+0x04   var     char[]    data      UTF-8 string data (length bytes)
```

If `length == 0`, the string is empty. If `length == 0xFFFFFFFF`, the string is null/absent.

### LookbackString (Id) System

Trackmania uses a string interning system called "LookbackString" or "Id" for frequently repeated strings (block names, material names, collection names, etc.):

```
First occurrence in a chunk context:
+0x00   4       uint32    version_marker    Must be 3 (establishes lookback table version)
+0x04   4       uint32    value             Lookback-encoded value (see below)

Subsequent reads in same chunk context:
+0x00   4       uint32    value             Lookback-encoded value
```

**Value encoding (CORRECTED based on real file analysis, see section 29 for details):**

```
Bits 31-30:  Flags
  0b11 = NEW STRING: read length-prefixed string, add to lookback table
  0b10 = BACK-REFERENCE: bits 29-0 are 1-based index into lookback table
  0b01 = NEW STRING (alternate form): same as 0b11 - read inline string, add to table
  0b00 = EMPTY: value 0 = empty string, value 0xFFFFFFFF = null/unset
```

**IMPORTANT CORRECTION**: Earlier documentation described 0b01 as "well-known string ID". Real file analysis shows 0b01 is actually another "new string" encoding -- the string data follows inline, identical to 0b11. Both 0b01 (0x40000000) and 0b11 (0xC0000000) prefix new strings. In TM2020 files, 0b01 appears to be the primary encoding used for new strings.

If flags == 0b01 or 0b11 (new string):
```
  +0x04   4     uint32    length    String length
  +0x08   var   char[]    data      String data (added to lookback table)
```

The lookback table is per-chunk context (reset for each header chunk; shared across body chunks for a node).

**Previously-documented "well-known Id values" are INCORRECT for TM2020:**

| Value | Actual Meaning |
|-------|----------------|
| `0x40000000` | flags=0b01, followed by a new string inline (NOT a well-known ID) |
| `0x40000001` | Possibly a well-known ID in older engines, but NOT observed in TM2020 files |

Note: The "Stadium"/"Valley"/"Canyon" collection names are NOT stored as LookbackStrings. They are represented as numeric collection IDs (26 = Stadium) in the CIdent structure's collection field, which is a plain uint32.

---

## 14. Array Serialization

### Standard Array Format

Arrays are serialized with a count prefix:

```
+0x00   4       uint32    count     Number of elements
+0x04   var     T[]       elements  Serialized elements (count * sizeof(T))
```

For arrays of primitives, elements are packed sequentially. For arrays of objects/nods, each element is serialized using the object reference mechanism.

### Buffer Array (Raw Bytes)

For raw byte buffers:

```
+0x00   4       uint32    size      Buffer size in bytes
+0x04   var     byte[]    data      Raw bytes
```

### Array of Nodes

```
+0x00   4       uint32    count     Number of node references
For each node:
  +0x00   4     uint32    class_id  Class ID (or 0xFFFFFFFF for null)
  If class_id != 0xFFFFFFFF:
    +0x04   var   ...     node_data  Serialized node data (chunks)
```

---

## 15. Object Reference Serialization

### Internal Node References

Within the body, nodes can reference other nodes. Each node in the file is assigned an index (starting from 0 for the root node). References use this index:

```
+0x00   4       int32     node_index    Index into the node table
                                        -1 (0xFFFFFFFF) = null reference
                                        >= 0 = index of the referenced node
```

When a new node is encountered for the first time at a given index:

```
+0x00   4       uint32    class_id      The class ID of the new node
+0x04   var     ...       chunks        The node's chunk data (serialized inline)
```

When a previously-seen node index is referenced, only the index is written (no class ID or chunk data).

### External Node References

External references point to nodes in other GBX files. These are resolved via the reference table (section 5). During deserialization:

1. The archive reads a node index
2. If the index maps to an external reference in the reference table:
   - The referenced GBX file is loaded (recursively)
   - The node from that file replaces the placeholder in the reference table

**Placeholder value**: `0xDEADBEEF` is written into the reference table slot during resolution as a sentinel to detect circular references.

---

## 16. Map File Structure (CGameCtnChallenge)

### Class ID: `0x03043000`

Map files (`.Map.Gbx`, legacy `.Challenge.Gbx`) use class `CGameCtnChallenge` and are the most complex GBX file type.

### 22-Stage Loading Pipeline

After the GBX header and body are parsed, the map undergoes a 22-stage initialization pipeline:

| # | Stage Name | Purpose |
|---|-----------|---------|
| 1 | `LoadDecorationAndCollection` | Loads the environment decoration (Stadium, etc.) |
| 2 | `InternalLoadDecorationAndCollection` | Internal implementation of decoration loading |
| 3 | `UpdateBakedBlockList` | Updates the pre-baked block list from serialized data |
| 4 | `AutoSetIdsForLightMap` | Assigns IDs for lightmap UV sets |
| 5 | `LoadAndInstanciateBlocks` | Creates block instances from serialized block data |
| 6 | `InitChallengeData_ClassicBlocks` | Initializes standard road/platform blocks |
| 7 | `InitChallengeData_Terrain` | Initializes terrain heightmap blocks |
| 8 | `InitChallengeData_DefaultTerrainBaked` | Sets up default terrain from baked data |
| 9 | `InitChallengeData_Genealogy` | Builds block parent-child relationships |
| 10 | `InitChallengeData_PylonsBaked` | Loads pre-baked pylon/support structures |
| 11 | `InitChallengeData_ClassicClipsBaked` | Loads pre-baked clip connections (standard) |
| 12 | `InitChallengeData_FreeClipsBaked` | Loads pre-baked clip connections (free placement) |
| 13 | `InitChallengeData_Clips` | Initializes all clip connection data |
| 14 | `CreateFreeClips` | Creates clip objects for free-placed blocks |
| 15 | `InitPylonsList` | Builds the list of pylon/support objects |
| 16 | `CreatePlayFields` | Creates playable field areas |
| 17 | `TransferIdForLightMapFromBakedBlocksToBlocks` | Copies lightmap IDs from baked to active blocks |
| 18 | `InitEmbeddedItemModels` | Loads embedded custom item model data |
| 19 | `LoadEmbededItems` | Instantiates embedded items |
| 20 | `InitAllAnchoredObjects` | Initializes all anchored/placed objects |
| 21 | `ConnectAdditionalDataClipsToBakedClips` | Wires up additional clip data |
| 22 | `RemoveNonBlocksFromBlockStock` | Cleans up non-block entries from block storage |

### Known Map Chunks

| Chunk ID | Version | Content |
|----------|---------|---------|
| `0x03043002` | - | Map UID, environment, map author login |
| `0x03043003` | - | Map name, mood, decoration, map type, author display name |
| `0x03043004` | - | Version info |
| `0x03043005` | - | XML community reference string |
| `0x03043007` | - | Thumbnail (JPEG) + comments |
| `0x03043008` | - | Author zone path, author extra info |
| `0x0304300D` | - | Vehicle (player model) reference |
| `0x03043011` | - | Block data (main block placement array) |
| `0x0304301F` | - | Map block parameters, block data (newer format) |
| `0x03043022` | - | [UNKNOWN] |
| `0x03043024` | - | Music reference |
| `0x03043025` | - | [UNKNOWN] |
| `0x03043026` | - | [UNKNOWN] |
| `0x03043028` | - | [UNKNOWN] |
| `0x03043029` | - | [UNKNOWN] |
| `0x03043034` | - | [UNKNOWN] |
| `0x03043036` | - | [UNKNOWN] |
| `0x03043038` | - | [UNKNOWN] |
| `0x03043040` | - | Anchor/item placement data |
| `0x03043042` | - | Author-related (newer format) |
| `0x03043043` | - | Genealogy/block relationship data |
| `0x03043044` | - | Metadata / script metadata |
| `0x03043048` | - | Baked blocks data |
| `0x03043049` | - | [UNKNOWN] |
| `0x0304304B` | - | Objectives / medal times |
| `0x03043054` | - | Embedded items |
| `0x03043056` | - | [UNKNOWN] |

### Block Data Format

Within chunk `0x03043011` (and related chunks), blocks are serialized as:

```
For each block:
  +0x00   4     Id/LookbackString   block_name      Block model name (e.g., "StadiumRoadMainStraight")
  +0x04   1     byte                direction       0=North, 1=East, 2=South, 3=West
  +0x05   12    Nat3 (3x uint32)    coord           Grid coordinates (x, y, z)
  +0x11   4     uint32              flags           Placement flags
                                                    Bit 0-14: [UNKNOWN - variant info?]
                                                    Bit 15: is_ground
                                                    Bit 20-25: [UNKNOWN]
                                                    Special: flags == 0xFFFFFFFF means "free block" (not grid-snapped)
```

### Item Placement Format

Items (anchored objects) in chunk `0x03043040`:

```
For each item:
  +0x00   4     Id/LookbackString   item_model      Item model reference name
  +0x04   4     uint32              [UNKNOWN]
  +0x08   12    Vec3 (3x float)     position         World-space position (x, y, z)
  +0x14   16    Quat (4x float)     rotation         Orientation quaternion (x, y, z, w)
  +0x24   ...   ...                 [additional fields based on chunk version]
```

### Thumbnail Data

In header chunk `0x03043007`:

```
+0x00   4       uint32    version           Chunk version
+0x04   4       uint32    thumbnail_size    Size of JPEG data
+0x08   ...     ...       [padding/markers]
+0x0F   15      bytes     "<Thumbnail.jpg>"  Marker string
+0x1E   var     bytes     jpeg_data          JPEG thumbnail image (thumbnail_size bytes)
+var    16      bytes     "</Thumbnail.jpg>"  End marker string
+var    ...     ...       comments_data      XML or text comments
```

### Filtered Block Lists

Maps maintain categorized views of their blocks:

| List | Method | Content |
|------|--------|---------|
| Classic blocks | `GetClassicBlocks` | Standard road/platform blocks |
| Terrain blocks | `GetTerrainBlocks` | Ground/terrain modification blocks |
| Ghost blocks | `GetGhostBlocks` | Non-physical overlay blocks |

### Vehicle References

Maps reference vehicle models via paths:

| Path | Vehicle |
|------|---------|
| `\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx` | Stadium car |
| `\Vehicles\Items\CarSport.Item.gbx` | Sport car (modern) |
| `\Vehicles\Items\CarSnow.Item.gbx` | Snow car |
| `\Vehicles\Items\CarRally.Item.gbx` | Rally car |
| `\Vehicles\Items\CarDesert.Item.gbx` | Desert car |

---

## 17. Ghost / Replay Structure

### CGameCtnGhost (Class ID: determined from hierarchy)

Ghost files (`.Ghost.Gbx`) store individual run data -- the recorded positions, rotations, and inputs of a car over time.

### CGameCtnReplayRecord (Class ID: `0x03093000`)

Replay files (`.Replay.Gbx`) wrap one or more ghosts along with the map reference.

**Body type label**: `"ArchiveNod::LoadGbx_Body(ReplayRecord)"`

### Related Extensions

| Extension | Address | Content |
|-----------|---------|---------|
| `.Replay.Gbx` | `0x141c2b280` | Full replay file |
| `.Ghost.Gbx` | `0x141c40868` | Individual ghost |
| `.InputsReplay.Gbx` | `0x141cccef0` | Raw input recording |

### Ghost Data Format [PARTIAL]

Ghost data includes:
- Race time (uint32, milliseconds)
- Number of checkpoints
- Checkpoint times array
- Validation status
- Player login/name
- Recorded position/rotation samples (compressed)
- Input event stream

The exact binary layout of ghost samples is class-specific and version-dependent. The `CPlugEntRecordData` class (from hierarchy) handles the actual recorded entity data.

---

## 18. Item File Structure (CGameItemModel)

### Class: CGameItemModel

Custom items (`.Item.Gbx`) are the most common user-created asset type. They reference mesh and material data.

### Related Classes (from hierarchy)

| Class | Role |
|-------|------|
| `CGameItemModel` | Root item class |
| `CGameItemModelTreeRoot` | Item placement tree root |
| `CGameItemPlacementParam` | Placement parameters |
| `CGameCommonItemEntityModel` | Item entity (behavior) model |
| `CGameCommonItemEntityModelEdition` | Editable item entity |
| `CGameBlockItem` | Block-item hybrid |
| `CGameBlockItemVariantChooser` | Variant selection for block items |

### Item File References

Items typically embed or reference:
- `CPlugStaticObjectModel` -- Static 3D geometry
- `CPlugSolid2Model` -- Modern mesh format
- `CPlugMaterial` / `CPlugMaterialUserInst` -- Materials
- `CPlugBitmap` -- Textures
- `CPlugSkel` -- Skeleton (if animated)

### File Extensions

| Extension | Address | Notes |
|-----------|---------|-------|
| `.Item.Gbx` | `0x141c2d630` | Custom items |
| `.Block.Gbx` | `0x141c2d740` | Block definitions |
| `.Macroblock.Gbx` | `0x141c2d708` | Multi-block groups |
| `BlockItem.Gbx` | `0x141c284e0` | Block-item hybrid |
| `StaticObject.Gbx` | `0x141bc68e8` | Static 3D object |

---

## 19. Mesh / Solid2 Structure

### CPlugSolid2Model (Class ID: `0x090BB000`)

The modern mesh format used in TM2020. Old meshes use `CPlugSolid` (`0x09005000`).

**Body type labels**:
- `"ArchiveNod::LoadGbx_Body(Solid2)"` for `0x090BB000`
- `"ArchiveNod::LoadGbx_Body(Solid1)"` for `0x09005000`

### Mesh-Related Classes (from hierarchy)

| Class | Role |
|-------|------|
| `CPlugSolid` | Legacy mesh container |
| `CPlugSolid2Model` | Modern mesh container |
| `CPlugSolidTools` | Mesh processing utilities |
| `CPlugModelMesh` | Mesh geometry |
| `CPlugModelLodMesh` | LOD (Level of Detail) mesh |
| `CPlugModelTree` | Scene graph tree |
| `CPlugModelShading` | Shading configuration |
| `CPlugIndexBuffer` | GPU index buffer |
| `CPlugGpuBuffer` | Generic GPU buffer |
| `CPlugCrystal` | Crystal geometry (older mesh format) |

### File Extensions

| Extension | Address | Notes |
|-----------|---------|-------|
| `.Mesh.Gbx` | `0x141bd5490` | Mesh geometry |
| `.Solid2.gbx` | `0x141bd1cd0` | Solid2 model |
| `Crystal.Gbx` | `0x141bc2168` | Crystal geometry |
| `Visual.Gbx` | `0x141ba4990` | Visual representation |
| `Model.Gbx` | `0x141bc5d90` | General model |
| `GenSolid.Gbx` | `0x141bc69c8` | Generated solid |

### Mesh Data Structure [PARTIAL]

Solid2Model files contain:
- Vertex buffers (position, normal, UV, tangent data)
- Index buffers (triangle lists)
- Material references
- LOD definitions
- Bounding box/sphere
- Visual layers and groups

The exact chunk-by-chunk format is class-specific and version-dependent.

---

## 20. Material and Texture Files

### CPlugMaterial (Class ID: `0x09026000` for ShaderApply)

Materials define surface appearance. In TM2020, materials use a shader-based system.

### Material Classes (from hierarchy)

| Class | Role |
|-------|------|
| `CPlugMaterial` | Base material |
| `CPlugMaterialCustom` | Custom material properties |
| `CPlugMaterialUserInst` | User-created material instance |
| `CPlugMaterialFx` | Material effects base |
| `CPlugMaterialFxDynaBump` | Dynamic bump mapping |
| `CPlugMaterialFxDynaMobil` | Dynamic mobile effects |
| `CPlugMaterialFxFlags` | Material effect flags |
| `CPlugMaterialFxFur` | Fur material effect |
| `CPlugMaterialFxGenCV` | Generated control vertex FX |
| `CPlugMaterialFxs` | Material effects collection |
| `CPlugMaterialPack` | Material pack |
| `CPlugMaterialWaterArray` | Water material array |
| `CPlugMaterialColorTargetTable` | Color target mapping |
| `CPlugShader` | Base shader |
| `CPlugShaderApply` | Applied shader instance |
| `CPlugShaderGeneric` | Generic programmable shader |
| `CPlugShaderPass` | Single render pass |
| `CPlugShaderCBufferStatic` | Shader constant buffer |

### CPlugBitmap (Class ID: `0x09011000`)

Textures are represented by `CPlugBitmap`.

**Body type label**: `"ArchiveNod::LoadGbx_Body(Bitmap)"`

### Texture/Bitmap Classes

| Class | Role |
|-------|------|
| `CPlugBitmap` | Base bitmap/texture |
| `CPlugBitmapBase` | Abstract bitmap base |
| `CPlugBitmapArray` | Texture array |
| `CPlugBitmapAtlas` | Texture atlas |
| `CPlugBitmapPack` | Packed textures |
| `CPlugBitmapRender` | Render-target bitmap |
| `CPlugBitmapSampler` | Texture sampler |
| `CPlugBitmapShader` | Shader-linked bitmap |
| `CPlugBitmapHighLevel` | High-level bitmap wrapper |
| `CPlugBitmapDecals` | Decal textures |

### Supported Image Formats

From the file classes in the hierarchy:

| Class | Format |
|-------|--------|
| `CPlugFileDds` | DirectDraw Surface (DDS) |
| `CPlugFileJpg` | JPEG |
| `CPlugFilePng` | PNG |
| `CPlugFileTga` | Targa |
| `CPlugFileWebP` | WebP |
| `CPlugFileSvg` | SVG (vector) |
| `CPlugFileExr` | OpenEXR (HDR) |
| `CPlugFileBink` | Bink video |
| `CPlugFileWebM` | WebM video |

### File Extensions

| Extension | Address | Notes |
|-----------|---------|-------|
| `Texture.Gbx` | `0x141ba3768` | Texture file |
| `Material.Gbx` | `0x141ba5d78` | Material definition |
| `Mat.Gbx` | `0x141bbd5a0` | Short material name |
| `TexturePack.Gbx` | `0x141bbdd18` | Texture atlas pack |
| `ImageArray.Gbx` | `0x141bb9e50` | Image array |

---

## 21. Pack File System

### Overview

Pack files (`.pack.gbx`) bundle multiple GBX files into a single archive for distribution. They are themselves GBX files with a specialized class.

### Pack Types

| Pack Type | Extension | Example |
|-----------|-----------|---------|
| Generic pack | `.pack.gbx` | General asset bundles |
| Skin pack | `.skin.pack.gbx` / `.Skin.Pack.Gbx` | Character/vehicle skins |
| Title pack | `.Title.Pack.Gbx` | Full game title content |
| Media pack | `.Media.Pack.Gbx` | Media assets |
| Model pack | `Model.Pack.Gbx` / `-Model.Pack.Gbx` | 3D model collections |
| WIP pack | `-wip.pack.gbx` | Work-in-progress content |

### Core Title Packs

| File | Address | Purpose |
|------|---------|---------|
| `Trackmania.Title.Pack.Gbx` | `0x141bcc828` | Main game content |
| `Trackmania_Update.Title.Pack.Gbx` | `0x141c584b0` | Update content |
| `.Title.Pack.Gbx.ref` | `0x141c58c50` | Reference file (points to actual pack) |

### Pack Management System

**CSystemPackManager** (string at `0x141c076d8`):

| Method | Address | Purpose |
|--------|---------|---------|
| `UpdatePackDescsAfterLoad` | `0x141c07820` | Updates pack metadata post-load |
| `LoadCache` | `0x141c078b0` | Loads the pack cache index |
| `TrimCacheIfNeeded` | `0x141c079b0` | Evicts cache entries to save space |

**CSystemPackDesc** (string at `0x141c07270`): Describes a pack's metadata.

### Pack File Internal Structure [PARTIAL]

A `.pack.gbx` file is a regular GBX file whose root class represents the pack container. The pack contains:

1. A manifest/index listing all contained files
2. Compressed or uncompressed file data blocks
3. Directory structure mirroring the virtual filesystem paths

The `CPlugFilePack` class (from hierarchy) and `CPlugFileFidContainer` handle pack file I/O.

The `CSystemFidContainer::InstallFids` function (`FUN_14092bec0`) registers files from a pack into the VFS:
- Iterates entries at stride 0x20 per entry from `container+0x18`
- Creates `CSystemFidFile` entries via `FUN_1408fa7b0`
- Associates files with their parent container via `FUN_1402cfa80`
- Updates folder indices at `container+0x38`

### Pack Loading Order [UNKNOWN]

The exact order in which packs are loaded and how conflicts are resolved (when multiple packs contain the same file path) is [UNKNOWN]. Evidence suggests title packs are loaded first, then update packs overlay them.

---

## 22. Fid (Virtual File System)

### Overview

The Fid system is Nadeo's virtual file system layer abstracting file access across disk, packs, and network sources.

### Class Hierarchy

| Class | Address | Role |
|-------|---------|------|
| `CSystemFidFile` | `0x141c07380` | Single file representation |
| `CSystemFidsFolder` | `0x141c08d68` | Directory/folder |
| `CSystemFidContainer` | `0x141c08ec8` | Container (pack file) |
| `CSystemFidsDrive` | `0x141c08ff8` | Top-level drive mount |

### FidFile Layout (Partial)

| Offset | Type | Purpose |
|--------|------|---------|
| `+0x08` | ptr | [UNKNOWN] |
| `+0x18` | ptr | Parent folder/container |
| `+0x20` | uint | Flags (bit 0, bit 2 significant) |
| `+0x24` | uint | Additional flags |
| `+0x48` | uint | File state flags |
| `+0x78` | uint32 | [UNKNOWN - possibly file size or class ID] |
| `+0x80` | ptr | Loaded nod pointer (cached object) |
| `+0xA8` | ptr | [UNKNOWN] |
| `+0xB0` | ptr* | Stream factory vtable |
| `+0xD0` | string | File path/name |
| `+0xD8` | uint32 | Path length |
| `+0xDC` | uint32 | [UNKNOWN path field] |

### Key Operations

| Operation | Evidence |
|-----------|----------|
| `CSystemFidsFolder::BrowsePath` | String at `0x141c08d88` |
| `CSystemFidContainer::InstallFids` | `FUN_14092bec0` |
| `CPlugFileFidCache::LoadAndRefreshFidCache` | String at `0x141c30e70` |

### FidCache

`CPlugFileFidCache` (string at `0x141bc4ec8`) maintains a persistent cache of file lookups in `User.FidCache.Gbx` at `0x141c30fe0`. This accelerates startup by avoiding re-scanning the entire file tree.

---

## 23. Complete Class ID Remap Table

This table contains every legacy-to-modern class ID remapping extracted from `FUN_1402f2610`. It is critical for reading GBX files from older game versions.

### Engine 0x24 -> Engine 0x03 (Old Game -> Modern Game)

| Old ID | New ID |
|--------|--------|
| `0x24003000` | `0x03043000` |
| `0x24004000` | `0x03033000` |
| `0x2400C000` | `0x0303E000` |
| `0x2400D000` | `0x03031000` |
| `0x2400E000` | `0x03032000` |
| `0x24011000` | `0x03053000` |
| `0x24014000` | `0x03038000` |
| `0x24015000` | `0x03039000` |
| `0x24019000` | `0x03027000` |
| `0x2401B000` | `0x0301A000` |
| `0x2401C000` | `0x03006000` |
| `0x2401F000` | `0x03036000` |
| `0x24022000` | `0x0300C000` |
| `0x24025000` | `0x0300D000` |
| `0x2403F000` | `0x03093000` |
| `0x24099000` | `0x0309A000` |

### Engine 0x0A -> Engine 0x09 (Old Scene -> Modern Plug)

| Old ID | New ID |
|--------|--------|
| `0x0A001000` | `0x09144000` |
| `0x0A002000` | `0x09145000` |
| `0x0A003000` | `0x090F4000` |
| `0x0A005000` | `0x09006000` |
| `0x0A006000` | `0x09003000` |
| `0x0A00A000` | `0x09004000` |
| `0x0A012000` | `0x09007000` |
| `0x0A014000` | `0x09008000` |
| `0x0A015000` | `0x0900C000` |
| `0x0A019000` | `0x0900F000` |
| `0x0A01A000` | `0x09010000` |
| `0x0A01B000` | `0x09011000` |
| `0x0A01C000` | `0x09012000` |
| `0x0A020000` | `0x09015000` |
| `0x0A024000` | `0x09014000` |
| `0x0A028000` | `0x09019000` |
| `0x0A02B000` | `0x09018000` |
| `0x0A02C000` | `0x0901B000` |
| `0x0A030000` | `0x0901C000` |
| `0x0A031000` | `0x0901D000` |
| `0x0A032000` | `0x0901F000` |
| `0x0A036000` | `0x09024000` |
| `0x0A03B000` | `0x09025000` |
| `0x0A03C000` | `0x09026000` |
| `0x0A03D000` | `0x0C030000` |
| `0x0A040000` | `0x09080000` |
| `0x0A06A000` | `0x090E5000` |

### Engine 0x08 -> Engine 0x09 (Old Graphic -> Modern Plug)

| Old ID | New ID |
|--------|--------|
| `0x08002000` | `0x090B1000` |
| `0x08005000` | `0x090B2000` |
| `0x08008000` | `0x090B3000` |
| `0x08009000` | `0x090B4000` |
| `0x08010000` | `0x090B5000` |
| `0x08016000` | `0x090B6000` |
| `0x08017000` | `0x090B7000` |
| `0x08019000` | `0x090B8000` |
| `0x0801A000` | `0x090B9000` |
| `0x0801B000` | `0x090BA000` |
| `0x0801C000` | `0x090BB000` |

### Engine 0x05 -> Engine 0x09 (Old Function -> Modern Plug)

| Old ID | New ID |
|--------|--------|
| `0x05001000` | `0x09081000` |
| `0x05002000` | `0x09082000` |
| `0x05012000` | `0x09083000` |
| `0x05013000` | `0x09084000` |

### Engine 0x07 -> Engine 0x09

| Old ID | New ID |
|--------|--------|
| `0x07002000` | `0x09091000` |
| `0x07003000` | `0x09092000` |
| `0x07004000` | `0x09093000` |
| `0x0702B000` | `0x09093000` |

### Engine 0x06 -> Engine 0x09

| Old ID | New ID |
|--------|--------|
| `0x06004000` | `0x09070000` |
| `0x06005000` | `0x09071000` |

### Cross-Engine Remappings

| Old ID | New ID |
|--------|--------|
| `0x03168000` | `0x09189000` |
| `0x2E035000` | `0x09189000` |
| `0x0313C000` | `0x11001000` |

**Note**: The decompiled function `FUN_1402f2610` contains a massive switch/if-else tree. The entries above are those explicitly identified in the annotated decompilation. The actual function likely contains additional entries (estimated 200+ total based on function size of the switch table). A complete extraction would require decompiling every branch of the switch statement.

---

## 24. Complete Engine ID Table

### Known Engine IDs

| Engine ID | Name | Era | Class Prefix | Notes |
|-----------|------|-----|--------------|-------|
| `0x01` | MwNod/System Core | All | `CMw*` | Base classes, end marker `0x01001000` |
| `0x03` | Game | Modern | `CGame*` | 728 classes, game logic |
| `0x05` | Function (legacy) | Legacy | - | Remapped to `0x09` |
| `0x06` | [UNKNOWN] | Legacy | - | Remapped to `0x09` |
| `0x07` | [UNKNOWN] | Legacy | - | Remapped to `0x09` |
| `0x08` | Graphic (legacy) | Legacy | - | Remapped to `0x09` |
| `0x09` | Plug | Modern | `CPlug*` | 391 classes, assets/visuals |
| `0x0A` | Scene (legacy) | Legacy | `CScene*` | Partially remapped to `0x09` and `0x0C` |
| `0x0C` | Control | Modern | `CControl*` | 39 classes, UI controls |
| `0x0D` | [UNKNOWN] | [UNKNOWN] | - | [UNKNOWN] |
| `0x0E` | [UNKNOWN] | [UNKNOWN] | - | [UNKNOWN] |
| `0x11` | [UNKNOWN] | Modern | - | Target of `0x0313C000` remap |
| `0x21` | [UNKNOWN] | [UNKNOWN] | - | [UNKNOWN] |
| `0x24` | Game (legacy) | Legacy | - | Bulk remapped to `0x03` |
| `0x2E` | [UNKNOWN] | Legacy | - | Remapped to `0x09` |

### Key Class IDs Quick Reference

| Class ID | Class Name | Body Label | File Extension |
|----------|-----------|------------|----------------|
| `0x03043000` | CGameCtnChallenge | Challenge | `.Map.Gbx` |
| `0x03093000` | CGameCtnReplayRecord | ReplayRecord | `.Replay.Gbx` |
| `0x0309A000` | [UNKNOWN] | ControlCard | - |
| `0x09005000` | CPlugSolid | Solid1 | - |
| `0x09011000` | CPlugBitmap | Bitmap | `Texture.Gbx` |
| `0x09026000` | CPlugShaderApply | ShaderApply | `Material.Gbx` |
| `0x09053000` | CPlugGpuCompileCache | GpuCompileCache | `GpuCache.Gbx` |
| `0x090BB000` | CPlugSolid2Model | Solid2 | `.Solid2.gbx` |

---

## 25. Parser Pseudocode

### Complete GBX Parser

```python
class GbxParser:
    def __init__(self):
        self.lookback_strings = []
        self.lookback_version = None
        self.nodes = {}       # index -> node
        self.node_count = 0

    def parse(self, stream):
        """Main entry point - parse a complete GBX file."""
        # === HEADER ===
        magic = stream.read(3)
        assert magic == b'GBX', f"Not a GBX file: {magic}"

        version = stream.read_uint16()
        assert version in (3, 4, 5, 6), f"Unsupported version: {version}"

        # Format flags (v6+)
        if version >= 6:
            format_flags = stream.read(4)
            format_type = chr(format_flags[0])      # 'B' or 'T'
            body_compress = chr(format_flags[1])     # 'C' or 'U'
            body_stream_compress = chr(format_flags[2])  # 'C' or 'U'
            ref_mode = chr(format_flags[3])          # 'R' or 'E'

            assert format_type == 'B', "Only binary format supported"
        else:
            body_compress = 'U'
            body_stream_compress = 'U'
            ref_mode = 'R'

        # Class ID
        class_id = stream.read_uint32()
        class_id = self.remap_class_id(class_id)

        # Header user data
        if version >= 6:
            user_data_size = stream.read_uint32()
            if user_data_size > 0:
                num_header_chunks = stream.read_uint32()
                header_chunks = self.parse_header_chunks(stream, num_header_chunks)
        else:
            header_chunks = []

        # === NODE COUNT ===
        self.node_count = stream.read_uint32()

        # === REFERENCE TABLE ===
        num_external = stream.read_uint32()
        references = []
        if num_external > 0:
            references = self.parse_reference_table(stream, num_external, version)

        # === BODY ===
        if body_stream_compress == 'C':
            uncompressed_size = stream.read_uint32()
            compressed_size = stream.read_uint32()
            compressed_data = stream.read(compressed_size)
            body_data = lzo_decompress(compressed_data, uncompressed_size)
            body_stream = MemoryStream(body_data)
        else:
            body_stream = stream

        # Parse body chunks
        root_node = self.create_node(class_id)
        self.parse_body_chunks(body_stream, root_node, class_id)

        return root_node

    def parse_header_chunks(self, stream, count):
        """Parse the header chunk index and data."""
        chunks = []
        for i in range(count):
            chunk_id = stream.read_uint32()
            chunk_size_raw = stream.read_uint32()
            is_heavy = bool(chunk_size_raw & 0x80000000)
            chunk_size = chunk_size_raw & 0x7FFFFFFF
            chunks.append({
                'id': chunk_id,
                'size': chunk_size,
                'is_heavy': is_heavy
            })

        # Read chunk data
        for chunk in chunks:
            chunk['data'] = stream.read(chunk['size'])

        return chunks

    def parse_reference_table(self, stream, num_external, version):
        """Parse the external reference table."""
        ancestor_level = stream.read_uint32()
        ancestor_folders = []
        for i in range(ancestor_level):
            folder = self.read_string(stream)
            ancestor_folders.append(folder)

        references = []
        for i in range(num_external):
            ref = {}
            ref['flags'] = stream.read_uint32()
            if (ref['flags'] & 4) != 0:
                ref['file_name'] = self.read_string(stream)
            else:
                ref['resource_index'] = stream.read_uint32()

            ref['node_index'] = stream.read_uint32()

            if version >= 5:
                ref['use_file'] = stream.read_uint32()
                ref['folder_index'] = stream.read_uint32()

            references.append(ref)

        return references

    def parse_body_chunks(self, stream, node, class_id):
        """Parse the body chunk stream until FACADE01."""
        while True:
            chunk_id = stream.read_uint32()

            # End sentinel
            if chunk_id == 0xFACADE01:
                break

            # Check for skippable chunk
            peek = stream.read_uint32()
            if peek == 0x534B4950:  # "SKIP"
                chunk_size = stream.read_uint32()
                chunk_data = stream.read(chunk_size)
                # Try to parse; if unknown, can safely skip
                self.dispatch_chunk(node, chunk_id, MemoryStream(chunk_data))
            else:
                # Non-skippable: must parse inline
                stream.seek(-4, SEEK_CUR)  # Put back the 4 bytes
                self.dispatch_chunk(node, chunk_id, stream)

    def dispatch_chunk(self, node, chunk_id, stream):
        """Dispatch a chunk to the appropriate handler based on class+chunk ID."""
        normalized_id = self.remap_class_id(chunk_id & 0xFFFFF000)
        chunk_index = chunk_id & 0x00000FFF
        full_id = normalized_id | chunk_index

        handler = self.get_chunk_handler(full_id)
        if handler:
            handler(node, stream)
        else:
            pass  # Unknown chunk (already skipped if skippable)

    def remap_class_id(self, class_id):
        """Apply legacy class ID remapping."""
        remap_table = {
            0x24003000: 0x03043000,  # CGameCtnChallenge
            0x2403F000: 0x03093000,  # CGameCtnReplayRecord
            0x24099000: 0x0309A000,
            0x0A01B000: 0x09011000,  # CPlugBitmap
            0x0A03C000: 0x09026000,  # CPlugShaderApply
            0x0801C000: 0x090BB000,  # CPlugSolid2Model
            # ... (all entries from section 23)
        }
        return remap_table.get(class_id, class_id)

    def read_string(self, stream):
        """Read a length-prefixed string."""
        length = stream.read_uint32()
        if length == 0:
            return ""
        if length == 0xFFFFFFFF:
            return None
        return stream.read(length).decode('utf-8')

    def read_lookback_string(self, stream):
        """Read a lookback/interned string (Id)."""
        if self.lookback_version is None:
            self.lookback_version = stream.read_uint32()
            assert self.lookback_version == 3

        value = stream.read_uint32()
        if value == 0xFFFFFFFF:
            return ""

        flags = (value >> 30) & 0x3
        index = value & 0x3FFFFFFF

        if flags == 0:
            return ""
        elif flags == 0b01:
            # Well-known string
            return self.get_well_known_string(index)
        elif flags == 0b10:
            # Reference to previously seen string
            return self.lookback_strings[index - 1]
        elif flags == 0b11:
            # New string
            s = self.read_string(stream)
            self.lookback_strings.append(s)
            return s

    def read_node_ref(self, stream):
        """Read an internal node reference."""
        index = stream.read_int32()
        if index == -1:
            return None
        if index in self.nodes:
            return self.nodes[index]

        # New node: read class ID and deserialize
        class_id = stream.read_uint32()
        class_id = self.remap_class_id(class_id)
        node = self.create_node(class_id)
        self.nodes[index] = node
        self.parse_body_chunks(stream, node, class_id)
        return node
```

### Decompression Pseudocode

```python
def decompress_gbx_body(compressed_data, expected_size):
    """
    Decompress GBX body data using LZO1X.

    Args:
        compressed_data: bytes - the compressed payload
        expected_size: int - expected decompressed size

    Returns:
        bytes - decompressed data
    """
    import lzo  # python-lzo or equivalent

    decompressed = lzo.decompress(compressed_data, False, expected_size)
    assert len(decompressed) == expected_size
    return decompressed
```

### Stream Helper Class

```python
import struct

class GbxStream:
    def __init__(self, data):
        self.data = data if isinstance(data, bytes) else data.read()
        self.pos = 0

    def read(self, n):
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def read_uint8(self):
        return struct.unpack_from('<B', self.data, self._advance(1))[0]

    def read_uint16(self):
        return struct.unpack_from('<H', self.data, self._advance(2))[0]

    def read_uint32(self):
        return struct.unpack_from('<I', self.data, self._advance(4))[0]

    def read_int32(self):
        return struct.unpack_from('<i', self.data, self._advance(4))[0]

    def read_uint64(self):
        return struct.unpack_from('<Q', self.data, self._advance(8))[0]

    def read_float(self):
        return struct.unpack_from('<f', self.data, self._advance(4))[0]

    def read_vec3(self):
        return struct.unpack_from('<fff', self.data, self._advance(12))

    def read_quat(self):
        return struct.unpack_from('<ffff', self.data, self._advance(16))

    def read_bool(self):
        return self.read_uint32() != 0

    def _advance(self, n):
        pos = self.pos
        self.pos += n
        return pos

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        elif whence == 2:
            self.pos = len(self.data) + offset
```

---

## 26. Parsing Tutorial: Byte 0 to Parsed Tree

This section walks through parsing a GBX file from the very first byte, using real hex dumps from actual TM2020 files to validate every claim.

### Step 1: Read the Magic (3 bytes)

Every GBX file starts with the ASCII bytes `G`, `B`, `X`:

```
Offset 0x0000: 47 42 58   "GBX"
```

If these 3 bytes do not match, reject the file immediately. The error string in the binary is: `"Wrong .Gbx format : not a < GameBox > file"`.

### Step 2: Read the Version (uint16, little-endian)

```
Offset 0x0003: 06 00      Version: 6
```

Only versions 3-6 are supported. Versions 1-2 are rejected with: `"Wrong .Gbx format : request a GameBox version between the %s and the %s"`.

TM2020 files always use version 6. Your parser MUST handle version 6. Supporting version 3-5 is needed only if you want to read old ManiaPlanet files.

### Step 3: Read Format Flags (4 ASCII chars, version 6+ only)

```
Offset 0x0005: 42 55 43 52   "BUCR"
```

| Byte | Value | Meaning |
|------|-------|---------|
| 0 | `B` (0x42) | Binary format. `T` = text format (not used in practice). Only proceed for `B`. |
| 1 | `U` (0x55) | Body compression envelope: `U` = uncompressed, `C` = compressed |
| 2 | `C` (0x43) | Body stream compression: `C` = LZO-compressed, `U` = raw |
| 3 | `R` (0x52) | Reference mode: `R` = has reference table, `E` = no external refs |

**Validated from real files**: Every TM2020 `.Map.Gbx`, `.Item.Gbx`, and `.Replay.Gbx` examined uses `BUCR`. The byte 2 = `C` is the one that matters for body decompression.

For versions 3-5, these 4 bytes are absent. Assume: binary format, uncompressed envelope, uncompressed stream, has references.

### Step 4: Read the Class ID (uint32, little-endian)

```
Offset 0x0009: 00 30 04 03   Class ID: 0x03043000 (CGameCtnChallenge)
```

This identifies what kind of object the file contains. The class ID is decomposed as:

```
0x03043000:
  Engine:      0x03       (Game engine)
  Class index: 0x043      (class #67 = CGameCtnChallenge)
  Sub-index:   0x000      (always 0 for class IDs)
```

**IMPORTANT**: Before using the class ID, run it through the legacy remap table (section 11). Old files from ManiaPlanet use different engine namespaces (e.g., `0x24003000` remaps to `0x03043000`).

### Step 5: Read User Data Size (uint32)

```
Offset 0x000D: FF 62 00 00   User data size: 25343 bytes
```

This is the total byte count of all header chunk data that follows. If 0, there are no header chunks.

### Step 6: Read Header Chunk Count (uint32)

```
Offset 0x0011: 06 00 00 00   Num header chunks: 6
```

### Step 7: Read the Header Chunk Index Table

The index table is `num_header_chunks * 8 bytes` (each entry: 4 bytes chunk ID + 4 bytes size).

```
Offset 0x0015: 02 30 04 03  39 00 00 00   Chunk 0x03043002, size=57
Offset 0x001D: 03 30 04 03  DD 00 00 00   Chunk 0x03043003, size=221
Offset 0x0025: 04 30 04 03  04 00 00 00   Chunk 0x03043004, size=4
Offset 0x002D: 05 30 04 03  0E 02 00 80   Chunk 0x03043005, size=526 (HEAVY)
Offset 0x0035: 07 30 04 03  51 5F 00 80   Chunk 0x03043007, size=24401 (HEAVY)
Offset 0x003D: 08 30 04 03  52 00 00 00   Chunk 0x03043008, size=82
```

The size field uses bit 31 as the "heavy" flag:
- `size & 0x80000000`: if set, chunk is "heavy" (can be skipped by lightweight parsers)
- `size & 0x7FFFFFFF`: actual byte count

**Verified**: Chunk 0x03043007 (thumbnail) is marked heavy because the JPEG thumbnail data is large (24KB) and not needed for basic map info parsing.

### Step 8: Read Header Chunk Data

After the index table, read `user_data_size` bytes total. Each chunk's data is concatenated in order, sized exactly as the index table specifies. Parse using the chunk IDs from the index.

### Step 9: Read Node Count (uint32)

The node count is at offset `0x11 + user_data_size`:

```
Offset 0x6310: 06 00 00 00   Node count: 6
```

This tells the parser how many node slots to pre-allocate for the internal node reference table. Each node encountered during body parsing gets an index from 0 to node_count-1.

### Step 10: Read External Reference Count and Reference Table (uint32)

```
Offset 0x6314: 00 00 00 00   External ref count: 0
```

If 0, there are no external references and the reference table section ends here. If > 0, see section 5 for the full reference table format.

### Step 11: Read the Compressed Body

When format flag byte 2 is `C`:

```
Offset 0x6318: 22 98 02 00   Uncompressed body size: 170018
Offset 0x631C: 6B 55 00 00   Compressed body size: 21867
Offset 0x6320: [21867 bytes of LZO-compressed data]
```

Decompress using LZO1X. The result is a flat byte stream of body chunks (170018 bytes).

### Step 12: Parse Body Chunks

The decompressed body is a sequential stream of chunks terminated by `0xFACADE01`:

```
loop:
    chunk_id = read_uint32()
    if chunk_id == 0xFACADE01: break     // End of body

    // Check for "SKIP" marker
    skip_marker = read_uint32()
    if skip_marker == 0x534B4950:        // ASCII "SKIP"
        chunk_size = read_uint32()
        chunk_data = read_bytes(chunk_size)
        // Dispatch or skip this chunk
    else:
        // Non-skippable: put back 4 bytes, parse inline
        seek_back(4)
        // MUST parse this chunk (no size to skip over)
```

---

## 27. Hex Dump Walkthrough: Real .Map.Gbx

The following is a complete annotated hex dump of the first 0x6324 bytes of `TechFlow.Map.Gbx`, verified by parsing the actual file.

### File Metadata

| Property | Value |
|----------|-------|
| File | `TechFlow.Map.Gbx` |
| Size | 47,243 bytes |
| Class | CGameCtnChallenge (0x03043000) |
| Format | BUCR (binary, LZO-compressed body, with refs) |
| Header chunks | 6 (map info, common header, version, XML, thumbnail, author) |
| Body | 170,018 bytes uncompressed, 21,867 compressed (12.9% ratio) |

### Byte Offset Table

```
Offset    Size    Content
------    ----    -------
0x0000    3       Magic: "GBX"
0x0003    2       Version: 6
0x0005    4       Format flags: "BUCR"
0x0009    4       Class ID: 0x03043000
0x000D    4       User data size: 25343
0x0011    4       Header chunk count: 6
0x0015    48      Header chunk index (6 entries x 8 bytes)
0x0045    57      Header chunk 0x03043002 data (map info)
0x007E    221     Header chunk 0x03043003 data (common header)
0x015B    4       Header chunk 0x03043004 data (version)
0x015F    526     Header chunk 0x03043005 data (XML - heavy)
0x036D    24401   Header chunk 0x03043007 data (thumbnail - heavy)
0x62BE    82      Header chunk 0x03043008 data (author info)
0x6310    4       Node count: 6
0x6314    4       External ref count: 0
0x6318    4       Uncompressed body size: 170018
0x631C    4       Compressed body size: 21867
0x6320    21867   LZO compressed body data
0xB88B    ---     EOF (47243 bytes total)
```

### Header Chunk 0x03043003 Parse (Common Map Header)

This chunk demonstrates LookbackStrings and CIdent parsing:

```
+0x00: 0B                          Version: 11
+0x01: 03 00 00 00                 Lookback version marker: 3
--- CIdent (uid, collection, author) ---
+0x05: 00 00 00 40                 LookbackString: flags=0b01 (new string)
+0x09: 1B 00 00 00                   String length: 27
+0x0D: 4B 53 33 61 50 48 47 37     "KS3aPHG7ywx7o2co6JLWHJKDjwl"
       79 77 78 37 6F 32 63 6F
       36 4A 4C 57 48 4A 4B 44
       6A 77 6C
+0x28: 1A 00 00 00                 Collection: numeric ID 26 (Stadium)
+0x2C: 00 00 00 40                 LookbackString: flags=0b01 (new string)
+0x30: 16 00 00 00                   String length: 22
+0x34: 58 43 68 77 44 75 38 46     "XChwDu8FRmWH-gHqXUbBtg"
       52 6D 57 48 2D 67 48 71
       58 55 62 42 74 67
--- End CIdent ---
+0x4A: 08 00 00 00                 Map name length: 8
+0x4E: 54 65 63 68 46 6C 6F 77     Map name: "TechFlow"
+0x56: 06                          Kind: 6 (Race)
+0x57: 00 00 00 00                 Locked: 0 (false)
+0x5B: 00 00 00 00                 Password: (empty, length=0)
--- Decoration CIdent ---
+0x5F: 00 00 00 40                 Decoration UID (new string)
+0x63: 11 00 00 00                   String length: 17
+0x67: 4E 6F 53 74 61 64 69 75     "NoStadium48x48Day"
       6D 34 38 78 34 38 44 61
       79
+0x78: 1A 00 00 00                 Decoration collection: 26 (Stadium)
+0x7C: 00 00 00 40                 Decoration author (new string)
+0x80: 05 00 00 00                   String length: 5
+0x84: 4E 61 64 65 6F               "Nadeo"
--- End Decoration CIdent ---
+0x89: [remaining fields: map style, title, lightmap UID, etc.]
```

**Key observation**: The CIdent format reads 3 values: uid (LookbackString), collection (raw numeric uint32), author (LookbackString). The collection is NOT a LookbackString -- it is a plain integer where 26 = Stadium.

### Cross-File Comparison

| File | Class ID | Format | Header Chunks | Nodes | Ext Refs | Body Compressed |
|------|----------|--------|---------------|-------|----------|-----------------|
| TechFlow.Map.Gbx | 0x03043000 | BUCR | 6 | 6 | 0 | 170018 -> 21867 |
| Mac1.Map.Gbx | 0x03043000 | BUCR | 6 | 6 | 0 | (similar) |
| GoldsValley1.Item.Gbx | 0x2E002000 | BUCR | 4 | 6 | 0 | 1557 -> 842 |
| Replay.Gbx | 0x03093000 | BUCR | 3 | 3 | 0 | (large) |
| Title.Pack.Gbx | NadeoPak* | N/A | N/A | N/A | N/A | Different format |

*The Title Pack uses `NadeoPak` magic instead of `GBX` -- it is a different container format entirely.

---

## 28. Data Type Serialization Reference

All values are little-endian. This table covers every primitive type used in GBX serialization.

### Primitive Types

| Type | Size | TypeScript Read | Notes |
|------|------|----------------|-------|
| `bool` | 4 bytes | `view.getUint32(pos, true) !== 0` | Stored as uint32: 0 = false, 1 = true |
| `byte` / `uint8` | 1 byte | `view.getUint8(pos)` | |
| `uint16` | 2 bytes | `view.getUint16(pos, true)` | |
| `int32` | 4 bytes | `view.getInt32(pos, true)` | |
| `uint32` | 4 bytes | `view.getUint32(pos, true)` | |
| `int64` | 8 bytes | `view.getBigInt64(pos, true)` | |
| `uint64` | 8 bytes | `view.getBigUint64(pos, true)` | |
| `float` | 4 bytes | `view.getFloat32(pos, true)` | IEEE 754 single precision |
| `double` | 8 bytes | `view.getFloat64(pos, true)` | IEEE 754 double precision |

### Composite Types

| Type | Size | Format | Notes |
|------|------|--------|-------|
| `Vec2` | 8 bytes | `(float x, float y)` | Two consecutive floats |
| `Vec3` | 12 bytes | `(float x, float y, float z)` | Three consecutive floats |
| `Vec4` / `Quat` | 16 bytes | `(float x, float y, float z, float w)` | Four consecutive floats |
| `Color` | 16 bytes | `(float r, float g, float b, float a)` | Four floats, 0.0-1.0 range |
| `Nat3` / `Int3` | 12 bytes | `(uint32 x, uint32 y, uint32 z)` | Three consecutive uint32s. Used for block grid coordinates. |
| `Iso4` | 48 bytes | 4x3 float matrix (column-major) | Rotation (3x3) + translation (1x3) |
| `Box` | 24 bytes | `(Vec3 min, Vec3 max)` | Axis-aligned bounding box |

### String Types

| Type | Format | Notes |
|------|--------|-------|
| `String` | `uint32 length` + `byte[length]` | UTF-8 encoded. length=0 means empty. length=0xFFFFFFFF means null/absent. |
| `LookbackString` / `Id` | See section 29 | Interned string with per-node lookup table |

### Collection Types

| Type | Format | Notes |
|------|--------|-------|
| `Array<T>` | `uint32 count` + `T[count]` | Packed array of elements |
| `Buffer` | `uint32 size` + `byte[size]` | Raw byte buffer |
| `NodeRef` | `int32 index` | -1 = null, >= 0 = node table index. If new node, followed by class_id + chunk data. |

### CIdent

The `CIdent` type is used for map UIDs, collection identifiers, author logins, and decoration names. It is NOT simply "3 LookbackStrings" -- the middle field is different:

```
CIdent:
  +0x00   LookbackString    uid           Unique identifier string
  +var    uint32            collection    Raw numeric collection ID (NOT a LookbackString)
  +var    LookbackString    author        Author identifier string
```

**Validated from real data**: In TechFlow.Map.Gbx, the collection field is the raw integer 26 (= Stadium). It does not have lookback string flags.

---

## 29. LookbackString Deep Dive (Corrected)

The LookbackString system is the most confusing part of GBX parsing. This section corrects errors in earlier documentation based on validation against real file data.

### How It Works

Each node's serialization context maintains a **per-chunk lookback string table** (an ordered list of previously-seen strings). The first time a LookbackString is read in a chunk, a version marker is read. Subsequent reads reference this table or add new entries.

### On-Wire Format

**First LookbackString read in a chunk context:**

```
+0x00   uint32    version_marker    MUST be 3 (establishes lookback table)
+0x04   uint32    value             The actual lookback-encoded value
```

**Subsequent reads (version already established):**

```
+0x00   uint32    value             The lookback-encoded value
```

### Value Encoding (CORRECTED)

The top 2 bits of `value` determine the encoding:

```
bits 31-30    Meaning
----------    -------
0b00          flags=0: If value==0, empty string. If value==0xFFFFFFFF, null/unset.
                       Other non-zero values: [UNKNOWN, possibly raw numeric ID]
0b01          flags=1: NEW STRING. Read a length-prefixed string next. Add it to the
                       lookback table. The lower 30 bits are ignored (always 0 in practice).
0b10          flags=2: BACK-REFERENCE. Lower 30 bits = 1-based index into the lookback
                       table. lookback_table[index - 1] is the string.
0b11          flags=3: NEW STRING (alternate form). Same as 0b01: read a length-prefixed
                       string, add to lookback table.
```

**CRITICAL CORRECTION**: Earlier documentation stated that 0b01 means "well-known string" and 0b11 means "new string". This is WRONG based on real file analysis. Both 0b01 and 0b11 mean "new string with inline data". The encoding for "well-known" IDs does not appear in any TM2020 file examined.

**Validated**: In TechFlow.Map.Gbx, the first LookbackString after the version marker is `0x40000000` (flags=0b01), followed by length 27 and the 27-byte UID string `"KS3aPHG7ywx7o2co6JLWHJKDjwl"`. The second new string uses the SAME 0b01 encoding for the author login.

### Back-Reference Example

After reading 4 new strings (uid, author, decoration, nadeo), the lookback table contains:
```
Index 1: "KS3aPHG7ywx7o2co6JLWHJKDjwl"
Index 2: "XChwDu8FRmWH-gHqXUbBtg"
Index 3: "NoStadium48x48Day"
Index 4: "Nadeo"
```

A later reference to `0x80000002` (flags=0b10, index=2) resolves to `"XChwDu8FRmWH-gHqXUbBtg"`.

### Scope

The lookback table is reset for each chunk's serialization context. Header chunks each get their own table. The body chunk stream shares a single table across all body chunks for the same node.

### TypeScript Implementation

```typescript
class LookbackStringReader {
  private version: number | null = null;
  private strings: string[] = [];

  read(reader: BinaryReader): string {
    if (this.version === null) {
      this.version = reader.readUint32();
      // version should be 3
    }

    const value = reader.readUint32();

    if (value === 0xFFFFFFFF) return '';  // null/unset
    if (value === 0) return '';            // empty

    const flags = (value >>> 30) & 3;

    switch (flags) {
      case 0b01:  // New string
      case 0b11:  // New string (alternate form)
        const s = reader.readString();
        this.strings.push(s);
        return s;

      case 0b10: { // Back-reference (1-based index)
        const index = (value & 0x3FFFFFFF) - 1;
        if (index >= 0 && index < this.strings.length) {
          return this.strings[index];
        }
        throw new Error(`Invalid lookback index: ${index + 1}`);
      }

      case 0b00:  // Empty or numeric
        return '';

      default:
        throw new Error(`Unknown lookback flags: ${flags}`);
    }
  }

  reset(): void {
    this.version = null;
    this.strings = [];
  }
}
```

---

## 30. TypeScript Parser Implementation Guide

### Core Parser Structure

```typescript
// === Core types ===

interface GbxHeader {
  version: number;
  formatType: 'B' | 'T';
  bodyCompress: 'C' | 'U';
  streamCompress: 'C' | 'U';
  refMode: 'R' | 'E';
  classId: number;
  userDataSize: number;
  headerChunks: HeaderChunk[];
}

interface HeaderChunk {
  id: number;
  size: number;
  isHeavy: boolean;
  data: Uint8Array;
}

interface GbxFile {
  header: GbxHeader;
  nodeCount: number;
  references: ExternalRef[];
  body: GbxNode;
}

interface GbxNode {
  classId: number;
  chunks: Map<number, unknown>;
}

interface ExternalRef {
  flags: number;
  fileName?: string;
  resourceIndex?: number;
  nodeIndex: number;
  useFile?: number;
  folderIndex?: number;
}

// === Binary Reader ===

class BinaryReader {
  private view: DataView;
  private pos: number = 0;

  constructor(buffer: ArrayBuffer) {
    this.view = new DataView(buffer);
  }

  get position(): number { return this.pos; }
  get remaining(): number { return this.view.byteLength - this.pos; }

  readUint8(): number {
    const v = this.view.getUint8(this.pos);
    this.pos += 1;
    return v;
  }

  readUint16(): number {
    const v = this.view.getUint16(this.pos, true);
    this.pos += 2;
    return v;
  }

  readUint32(): number {
    const v = this.view.getUint32(this.pos, true);
    this.pos += 4;
    return v;
  }

  readInt32(): number {
    const v = this.view.getInt32(this.pos, true);
    this.pos += 4;
    return v;
  }

  readFloat32(): number {
    const v = this.view.getFloat32(this.pos, true);
    this.pos += 4;
    return v;
  }

  readBytes(n: number): Uint8Array {
    const slice = new Uint8Array(this.view.buffer, this.pos, n);
    this.pos += n;
    return slice;
  }

  readString(): string {
    const len = this.readUint32();
    if (len === 0) return '';
    if (len === 0xFFFFFFFF) return '';
    const bytes = this.readBytes(len);
    return new TextDecoder('utf-8').decode(bytes);
  }

  readVec3(): [number, number, number] {
    return [this.readFloat32(), this.readFloat32(), this.readFloat32()];
  }

  readNat3(): [number, number, number] {
    return [this.readUint32(), this.readUint32(), this.readUint32()];
  }

  readBool(): boolean {
    return this.readUint32() !== 0;
  }

  skip(n: number): void {
    this.pos += n;
  }

  seek(pos: number): void {
    this.pos = pos;
  }
}

// === Main Parser ===

function parseGbx(buffer: ArrayBuffer): GbxFile {
  const reader = new BinaryReader(buffer);

  // Step 1-2: Magic and version
  const magic = new TextDecoder().decode(reader.readBytes(3));
  if (magic !== 'GBX') throw new Error('Not a GBX file');

  const version = reader.readUint16();
  if (version < 3 || version > 6) throw new Error(`Unsupported version: ${version}`);

  // Step 3: Format flags (v6+)
  let formatType: 'B' | 'T' = 'B';
  let bodyCompress: 'C' | 'U' = 'U';
  let streamCompress: 'C' | 'U' = 'U';
  let refMode: 'R' | 'E' = 'R';

  if (version >= 6) {
    const flags = reader.readBytes(4);
    formatType = String.fromCharCode(flags[0]) as 'B' | 'T';
    bodyCompress = String.fromCharCode(flags[1]) as 'C' | 'U';
    streamCompress = String.fromCharCode(flags[2]) as 'C' | 'U';
    refMode = String.fromCharCode(flags[3]) as 'R' | 'E';

    if (formatType !== 'B') throw new Error('Only binary format supported');
  }

  // Step 4: Class ID
  let classId = reader.readUint32();
  classId = remapClassId(classId);

  // Step 5-7: User data and header chunks
  const headerChunks: HeaderChunk[] = [];
  let userDataSize = 0;

  if (version >= 6) {
    userDataSize = reader.readUint32();
    if (userDataSize > 0) {
      const numChunks = reader.readUint32();

      // Read index table
      const entries: { id: number; size: number; isHeavy: boolean }[] = [];
      for (let i = 0; i < numChunks; i++) {
        const id = reader.readUint32();
        const rawSize = reader.readUint32();
        entries.push({
          id,
          size: rawSize & 0x7FFFFFFF,
          isHeavy: (rawSize & 0x80000000) !== 0,
        });
      }

      // Read chunk data
      for (const entry of entries) {
        const data = reader.readBytes(entry.size);
        headerChunks.push({ ...entry, data });
      }
    }
  }

  // Step 9: Node count
  const nodeCount = reader.readUint32();

  // Step 10: Reference table
  const numExternal = reader.readUint32();
  const references: ExternalRef[] = [];

  if (numExternal > 0) {
    const ancestorLevel = reader.readUint32();
    const ancestorFolders: string[] = [];
    for (let i = 0; i < ancestorLevel; i++) {
      ancestorFolders.push(reader.readString());
    }

    for (let i = 0; i < numExternal; i++) {
      const ref: ExternalRef = {
        flags: reader.readUint32(),
        nodeIndex: 0,
      };

      if (ref.flags & 4) {
        ref.fileName = reader.readString();
      } else {
        ref.resourceIndex = reader.readUint32();
      }

      ref.nodeIndex = reader.readUint32();

      if (version >= 5) {
        ref.useFile = reader.readUint32();
        ref.folderIndex = reader.readUint32();
      }

      references.push(ref);
    }
  }

  // Step 11: Body
  let bodyReader: BinaryReader;

  if (streamCompress === 'C') {
    const uncompressedSize = reader.readUint32();
    const compressedSize = reader.readUint32();
    const compressedData = reader.readBytes(compressedSize);
    // Use LZO1X decompression (requires external library)
    const decompressed = lzoDecompress(compressedData, uncompressedSize);
    bodyReader = new BinaryReader(decompressed.buffer);
  } else {
    bodyReader = reader;
  }

  // Step 12: Parse body chunks
  const lookback = new LookbackStringReader();
  const nodes = new Map<number, GbxNode>();
  const rootNode: GbxNode = { classId, chunks: new Map() };

  parseBodyChunks(bodyReader, rootNode, lookback, nodes);

  return {
    header: {
      version, formatType, bodyCompress, streamCompress,
      refMode, classId, userDataSize, headerChunks,
    },
    nodeCount,
    references,
    body: rootNode,
  };
}

function parseBodyChunks(
  reader: BinaryReader,
  node: GbxNode,
  lookback: LookbackStringReader,
  nodes: Map<number, GbxNode>,
): void {
  while (reader.remaining >= 4) {
    const chunkId = reader.readUint32();

    if (chunkId === 0xFACADE01) break; // End sentinel

    // Check for skippable chunk
    const possibleSkip = reader.readUint32();
    if (possibleSkip === 0x534B4950) { // "SKIP"
      const chunkSize = reader.readUint32();
      const chunkData = reader.readBytes(chunkSize);
      // Dispatch or store raw bytes for unknown chunks
      node.chunks.set(chunkId, chunkData);
    } else {
      // Non-skippable: seek back and parse inline
      reader.seek(reader.position - 4);
      // Must have a handler for this chunk type
      node.chunks.set(chunkId, null); // placeholder
      // Real implementation: dispatch to chunk-specific parser
    }
  }
}

// === Class ID Remapping ===

const CLASS_ID_REMAP: Record<number, number> = {
  0x24003000: 0x03043000, // CGameCtnChallenge
  0x2403F000: 0x03093000, // CGameCtnReplayRecord
  0x24099000: 0x0309A000, // ControlCard
  0x0A01B000: 0x09011000, // CPlugBitmap
  0x0A03C000: 0x09026000, // CPlugShaderApply
  0x0801C000: 0x090BB000, // CPlugSolid2Model
  // ... add all entries from section 23
};

function remapClassId(id: number): number {
  return CLASS_ID_REMAP[id] ?? id;
}

// === LZO Decompression ===
// You will need an LZO1X library. Options:
//   - lzo-decompress (npm package)
//   - lzo1x-js
//   - Compile miniLZO to WebAssembly
//
// declare function lzoDecompress(
//   compressed: Uint8Array, expectedSize: number
// ): Uint8Array;
```

### Decompression Notes

The body compression in GBX files uses **LZO1X** (not zlib). This is confirmed by:
1. The decompression function `FUN_140127aa0` in the binary
2. Community tools (GBX.NET) use LZO
3. The compressed data structure matches LZO1X (first byte 0x1A = 26, meaning initial literal of 9 bytes for the map file; first byte 0x34 = 52, meaning initial literal of 35 bytes for the item file -- both consistent with LZO1X encoding)

In TypeScript, use one of:
- `lzo-decompress` npm package
- `lzo1x.js` (pure JS implementation)
- Compile `minilzo.c` to WASM via Emscripten

---

## 31. Quick Reference Card

### File Layout (Version 6)

```
"GBX"                    3 bytes    Magic
uint16                   2 bytes    Version (6)
char[4]                  4 bytes    Format flags ("BUCR")
uint32                   4 bytes    Class ID
uint32                   4 bytes    User data size
uint32                   4 bytes    Header chunk count
[chunk_id:u32, size:u32] 8*N bytes  Header chunk index
byte[]                   var bytes  Header chunk data (total = user_data_size)
uint32                   4 bytes    Node count
uint32                   4 bytes    External ref count
[ref table]              var bytes  Reference table (if ext refs > 0)
uint32                   4 bytes    Uncompressed body size (if compressed)
uint32                   4 bytes    Compressed body size (if compressed)
byte[]                   var bytes  Body data (LZO if compressed)
```

### Body Chunk Format

```
uint32    chunk_id          0xFACADE01 = end of body
uint32    skip_marker       0x534B4950 ("SKIP") = skippable chunk
uint32    chunk_size         Only present if skip_marker == "SKIP"
byte[]    chunk_data         chunk_size bytes (or parse inline if not skippable)
```

### Class ID Decomposition

```
class_id = 0x03043000
engine    = (class_id >> 24) & 0xFF   = 0x03 (Game)
class_idx = (class_id >> 12) & 0xFFF  = 0x043 (67th class)
chunk_idx = class_id & 0xFFF          = 0x000 (for chunk IDs, this varies)
```

### Important Class IDs

| Class ID | Name | File Extension | Body Label |
|----------|------|---------------|------------|
| `0x03043000` | CGameCtnChallenge | `.Map.Gbx` | Challenge |
| `0x03093000` | CGameCtnReplayRecord | `.Replay.Gbx` | ReplayRecord |
| `0x2E002000` | CGameItemModel | `.Item.Gbx` | Other |
| `0x09005000` | CPlugSolid | (legacy mesh) | Solid1 |
| `0x090BB000` | CPlugSolid2Model | `.Solid2.gbx` | Solid2 |
| `0x09011000` | CPlugBitmap | `Texture.Gbx` | Bitmap |
| `0x09026000` | CPlugShaderApply | `Material.Gbx` | ShaderApply |

### Map Header Chunks (0x03043xxx)

| Chunk ID | Content | Heavy |
|----------|---------|-------|
| `0x03043002` | Map UID, flags (version-dependent format) | No |
| `0x03043003` | Map name, author, mood, map type, title | No |
| `0x03043004` | Version info | No |
| `0x03043005` | XML header (community metadata) | Yes |
| `0x03043007` | Thumbnail JPEG + comments | Yes |
| `0x03043008` | Author zone, extra info | No |

### LookbackString Cheat Sheet

```
First read:  [uint32 version=3] [uint32 value]
Later reads: [uint32 value]

value encoding:
  0x00000000          -> empty string
  0xFFFFFFFF          -> null/unset
  0x40000000 + string -> new string (flags=01), add to table
  0xC0000000 + string -> new string (flags=11), add to table
  0x80000001          -> back-reference to table[0] (1-based)
  0x80000002          -> back-reference to table[1]
  etc.
```

### Sentinel Values

| Value | Context | Meaning |
|-------|---------|---------|
| `0xFACADE01` | Body chunk stream | End of body chunks |
| `0x534B4950` | After chunk ID | "SKIP" -- chunk is skippable (has size prefix) |
| `0x01001000` | Internal | CMwNod end marker (class ID) |
| `0xDEADBEEF` | Reference table | Placeholder during recursive resolution |
| `0xFFFFFFFF` | Node reference | Null node reference |
| `0xFFFFFFFF` | String length | Null/absent string |

---

## 32. Cross-File Validation Results

### Files Examined

| File | Type | Size | Parse Result |
|------|------|------|--------------|
| `TechFlow.Map.Gbx` | Map | 47,243 | Full header parsed, 6 chunks decoded |
| `Mac1.Map.Gbx` | Map | ~50KB | Header structure matches TechFlow |
| `GoldsValley1.Item.Gbx` | Item | 1,005 | Full header parsed, class 0x2E002000 |
| `ReallyRally.Replay.Gbx` | Replay | 4,388,346 | Header parsed, class 0x03093000 |
| `Trackmania.Title.Pack.Gbx` | Pack | ~large | NOT a GBX file -- uses `NadeoPak` magic |

### Key Findings from Validation

1. **All TM2020 GBX files use version 6 with "BUCR" format flags**. No exceptions found in user files.

2. **The body is always LZO-compressed** (byte 2 = 'C'). No uncompressed body files found in TM2020.

3. **External reference counts are 0 in all user-generated files examined**. This suggests embedded items and references are resolved at save time. Game data files (from packs) may have external references.

4. **Item files use class ID 0x2E002000** (CGameItemModel in engine 0x2E), NOT a remapped modern ID. This means engine 0x2E is a live engine in TM2020, not just a legacy namespace.

5. **The Title Pack file is NOT a GBX file**. It starts with `NadeoPak` magic (8 bytes: `4E 61 64 65 6F 50 61 6B`) and uses an entirely different container format. This is different from what the binary strings suggested.

6. **LookbackString flags 0b01 and 0b11 are both "new string"**. The distinction between them is [UNKNOWN] but both result in reading an inline length-prefixed string and adding it to the lookup table. Real files use 0b01 (0x40000000) exclusively for new strings.

7. **CIdent collection field is a raw numeric uint32**, NOT a LookbackString. The value 26 corresponds to "Stadium" as a collection/environment identifier.

8. **LZO1X compression is confirmed** by checking the compressed data byte patterns against the LZO1X specification (initial byte encoding for literal runs matches expected format).

### Format Claims Verification Status

| Claim | Status | Evidence |
|-------|--------|----------|
| Magic bytes "GBX" at offset 0 | VERIFIED | All files start with 0x47 0x42 0x58 |
| Version is uint16 at offset 3 | VERIFIED | All files show 0x06 0x00 |
| Format flags at offset 5 | VERIFIED | "BUCR" in all examined files |
| Class ID at offset 9 | VERIFIED | 0x03043000 for maps, 0x2E002000 for items, 0x03093000 for replays |
| User data size at offset 0x0D | VERIFIED | Correct total matches sum of chunk sizes |
| Chunk count at offset 0x11 | VERIFIED | Index table entries match |
| Heavy flag is bit 31 of chunk size | VERIFIED | Chunks 0x03043005 and 0x03043007 have bit 31 set |
| Node count follows header data | VERIFIED | At offset 0x11 + user_data_size |
| Body has uncomp/comp size prefix | VERIFIED | Sizes consistent with file length |
| LookbackString version marker = 3 | VERIFIED | First uint32 in chunk 0x03043003 data (after version byte) |
| FACADE01 ends body | CONFIRMED | From decompiled code (real body not decompressed due to missing LZO library) |
| SKIP marker = 0x534B4950 | CONFIRMED | From decompiled code |
| Pack files use NadeoPak magic | VERIFIED | Title.Pack.Gbx starts with "NadeoPak" not "GBX" |

---

## Appendix A: Thread Safety

GBX loading includes thread safety checks:

```
"[Sys] Danger: CSystemArchiveNod::DoLoadFromFid(Gbx) called outside MainThread" at 0x141c06be0
"[Sys] Danger: CSystemArchiveNod::DoLoadFromFid(Media) called outside MainThread" at 0x141c06a60
```

This means the GBX loader is NOT thread-safe. Loading must occur on the main thread (or with proper synchronization). The TLS cache used by the class ID lookup further confirms this -- each thread has its own cache.

---

## Appendix B: IsA Checks During Loading

After loading, the GBX loader checks if the loaded object is of certain expected types (via vtable calls at offset `+0x20`):

| Class ID | Likely Class |
|----------|-------------|
| `0x09025000` | CPlug visual class |
| `0x09030000` | CPlug visual class |
| `0x09040000` | CPlug visual class |
| `0x0902D000` | CPlug class |
| `0x09098000` | CPlug class |
| `0x09020000` | CPlugFile base class |

These checks appear to be type validation ensuring the loaded GBX contains the expected asset type.

---

## Appendix C: Complete File Extension Catalog

### Map / Challenge
| Extension | Address |
|-----------|---------|
| `.Map.Gbx` | `0x141c2b290` |
| `.Challenge.Gbx` | `0x141c2dc10` |

### Replay / Ghost
| Extension | Address |
|-----------|---------|
| `.Replay.Gbx` | `0x141c2b280` |
| `.Ghost.Gbx` | `0x141c40868` |
| `.InputsReplay.Gbx` | `0x141cccef0` |

### Items / Blocks
| Extension | Address |
|-----------|---------|
| `.Item.Gbx` | `0x141c2d630` |
| `.Block.Gbx` | `0x141c2d740` |
| `.Macroblock.Gbx` | `0x141c2d708` |

### Visual / Mesh
| Extension | Address |
|-----------|---------|
| `.Mesh.Gbx` | `0x141bd5490` |
| `.Solid2.gbx` | `0x141bd1cd0` |
| `.Skel.gbx` | `0x141bd1cb0` |
| `.Anim.gbx` | `0x141bd1d08` |

### Texture / Material
| Extension | Address |
|-----------|---------|
| `Texture.Gbx` | `0x141ba3768` |
| `Material.Gbx` | `0x141ba5d78` |

### Audio
| Extension | Address |
|-----------|---------|
| `Sound.Gbx` | `0x141ba55f8` |
| `Music.Gbx` | `0x141bc2f80` |

### Pack Files
| Extension | Address |
|-----------|---------|
| `.pack.gbx` | `0x141bbba40` |
| `.Title.Pack.Gbx` | `0x141c2f438` |
| `.Media.Pack.Gbx` | `0x141c2f5e0` |

### UI / Control
| Extension | Address |
|-----------|---------|
| `Frame.Gbx` | `0x141b5c318` |
| `StyleSheet.Gbx` | `0x141b5c6c0` |

### Vehicle
| Extension | Address |
|-----------|---------|
| `VehicleVisModel.Gbx` | `0x141bd2510` |
| `VehiclePhyModelCustom.Gbx` | `0x141bd5b28` |

---

## Appendix D: Unknowns and Open Questions

### Resolved (from real file validation)

1. **[RESOLVED]** The compression algorithm is confirmed as **LZO1X** (not zlib). Verified by: (a) compressed data byte patterns match LZO1X encoding, (b) zlib/deflate both fail on the data, (c) community tools confirm LZO. The exact sub-variant is likely LZO1X-1 for decompression.

2. **[RESOLVED]** LookbackString flags 0b01 are NOT "well-known strings" as previously documented. Both 0b01 and 0b11 mean "new inline string". Real TM2020 files use 0b01 (0x40000000) exclusively for new strings. See section 29.

3. **[RESOLVED]** CIdent collection field is a raw numeric uint32, NOT a LookbackString. Value 26 = Stadium. See section 28.

4. **[RESOLVED]** Pack files (.Title.Pack.Gbx) use `NadeoPak` magic (8 bytes), NOT the standard GBX format. They are a separate container format entirely.

5. **[RESOLVED]** Engine 0x2E is a LIVE modern engine, not just a legacy namespace. CGameItemModel uses class ID 0x2E002000 in current TM2020 item files.

6. **[PARTIALLY RESOLVED]** Byte 1 vs byte 2 of format flags: all TM2020 files examined use `'U'` for byte 1 and `'C'` for byte 2. Byte 2 controls the LZO body compression (confirmed). Byte 1's exact role when `'C'` is still [UNKNOWN] but may control a secondary compression envelope.

### Remaining Unknowns

7. **[UNKNOWN]** The complete class info structure beyond offsets `+0x08` (name) and `+0x30` (factory). Offsets `+0x10`, `+0x18`, `+0x20`, `+0x28` likely contain parent class pointer, chunk handler table, and property descriptors.

8. **[UNKNOWN]** How header chunks are individually dispatched to class-specific handlers. Likely via a vtable mechanism on the node class that routes `(class_id, chunk_id)` pairs to specific deserialization methods.

9. **[UNKNOWN]** The full CClassicArchive struct layout. Only ~20 of potentially 40+ fields are documented.

10. **[UNKNOWN]** Whether text format (`'T'` in byte 0) is functional in TM2020. No evidence of text-mode body parsing found in decompilation.

11. **[UNKNOWN]** The exact format of NadeoPak container files (how files within `.pack.gbx` are indexed and accessed). These use a completely different magic and format from standard GBX files.

12. **[UNKNOWN]** The internal binary format of ghost/replay sample data (position/rotation keyframes, input events).

13. **[UNKNOWN]** The difference between LookbackString flags 0b01 and 0b11. Both produce new strings in practice. One theory: 0b01 = "collected" (string from a shared collection namespace), 0b11 = "free" (arbitrary string). In practice both work identically.

14. **[UNKNOWN]** Engine IDs `0x06`, `0x07`, `0x0D`, `0x0E`, `0x11` -- what class families these represent in the modern engine. Engine `0x2E` is confirmed to be CGameItemModel's engine.

15. **[UNKNOWN]** The exact CPlugSolid2Model chunk format (vertex/index buffer layout, material binding).

16. **[UNKNOWN]** The relationship between `param_1+0xF8` (archive offset) and deferred/lazy loading of large assets.

17. **[UNKNOWN]** The complete set of numeric collection IDs used in CIdent (26 = Stadium, others not confirmed).

---

## Appendix E: Code Evidence Index

Every structural claim in this document traces back to one of these decompiled sources:

| File | Function | Key Contribution |
|------|----------|-----------------|
| `FUN_140904730_LoadGbx.c` | CSystemArchiveNod::LoadGbx | Loading pipeline, format dispatch |
| `FUN_140900e60_LoadHeader.c` | Header magic/version | Magic bytes, version switch |
| `FUN_140901850_ParseVersionHeader.c` | Format flags v6 | BUCE/BUCR parsing, compression flags |
| `FUN_140903140_BodyTypeLabel.c` | Body type labels | Class ID to profiling label mapping |
| `FUN_140903d30_LoadHeaderAndBody.c` | Load orchestrator | Header+body+ref coordination |
| `FUN_1402cf380_CreateByMwClassId.c` | Class factory | Object instantiation from class IDs |
| `FUN_1402f20a0_ClassIdLookup.c` | Two-level lookup | Registry structure, TLS cache |
| `FUN_1402f2610_ClassIdRemap.c` | Legacy ID remap | Complete remap table |
| `FUN_1402d0c40_ChunkEndMarker.c` | End sentinel | FACADE01 and 01001000 handling |

# OpenTM Asset Pipeline

**Date**: 2026-03-27
**Status**: Design document
**Scope**: Complete asset pipeline from .Gbx files on disk to runtime-ready data in the browser

---

## Table of Contents

1. [Asset Type Inventory](#1-asset-type-inventory)
2. [GBX Parser Architecture (TypeScript)](#2-gbx-parser-architecture-typescript)
3. [Map Loading Pipeline (Exact Steps)](#3-map-loading-pipeline-exact-steps)
4. [The Block Mesh Problem (Detailed Analysis)](#4-the-block-mesh-problem-detailed-analysis)
5. [Material System](#5-material-system)
6. [Texture Pipeline](#6-texture-pipeline)
7. [Ghost/Replay Asset Pipeline](#7-ghostreplay-asset-pipeline)
8. [Caching Strategy](#8-caching-strategy)
9. [Pre-processing Pipeline](#9-pre-processing-pipeline)
10. [Dependency on Community Tools](#10-dependency-on-community-tools)

---

## 1. Asset Type Inventory

Every asset type the game uses, with parsing complexity assessment and priority for OpenTM.

### 1.1 Primary GBX File Types

| File Extension | GBX Class ID | Class Name | Data Contents | Source | Parser Complexity | Priority |
|----------------|-------------|------------|---------------|--------|-------------------|----------|
| `.Map.Gbx` | `0x03043000` | CGameCtnChallenge | Block placements, item placements, embedded items, thumbnail, metadata, MediaTracker clips, lightmap data | User files, TMX API, Nadeo API | **Hard** -- 20+ body chunks, encapsulated chunks, lookback strings, complex version branching | **MVP-critical** |
| `.Replay.Gbx` | `0x03093000` | CGameCtnReplayRecord | Embedded map, ghost(s), checkpoint times, validation data, input replay | User files, Nadeo API | **Hard** -- contains nested GBX (embedded map), ghost data with zlib inner compression | **MVP-critical** |
| `.Ghost.Gbx` | `0x03092000` | CGameCtnGhost | Position/rotation samples at 50ms, checkpoint times, player info, input events | Extracted from replays, Nadeo API ghost download | **Medium** -- 16+ chunks, zlib-compressed sample data, axis-angle rotation encoding | **MVP-critical** |
| `.Item.Gbx` | varies | CGameItemModel | Item definition referencing mesh, material, collision, waypoint type | Embedded in maps, user Items/ folder, pack files | **Medium** -- references sub-objects (CPlugStaticObjectModel, CPlugSolid2Model) | **Important** |
| `.Block.Gbx` | `0x2E002000` | CGameCtnBlockInfo variant | Custom block definition with variant info, clip connections | User Blocks/ folder, pack files | **Medium** -- 4 header chunks, block-specific chunk IDs in engine 0x2E | **Important** |
| `.Solid2.gbx` | `0x090BB000` | CPlugSolid2Model | Vertex buffers (position, normal, UV, tangent), index buffers, material refs, LODs, bounding volumes | Pack files, embedded in items | **Hard** -- proprietary vertex/index buffer encoding, multiple LOD levels, material references | **Important** |
| `.Macroblock.Gbx` | varies | CGameCtnMacroBlockInfo | Group of blocks as a reusable template | User Blocks/ folder | **Medium** | **Nice-to-have** |
| `.Profile.Gbx` | `0x031CC000` | Profile class | User preferences, garage state, campaign progress | User documents | **Easy** -- no header chunks, just key-value body chunks | **Nice-to-have** |

### 1.2 Internal/Engine GBX Types

| File Extension | GBX Class ID | Class Name | Data Contents | Source | Parser Complexity | Priority |
|----------------|-------------|------------|---------------|--------|-------------------|----------|
| `Material.Gbx` | `0x09026000` | CPlugShaderApply | Shader parameters, texture references, blend modes, surface properties | Pack files | **Hard** -- deep shader parameter trees | **Important** |
| `Texture.Gbx` | `0x09011000` | CPlugBitmap | Texture metadata, mipmap chain, DDS/WebP/PNG data | Pack files | **Medium** -- image format detection and extraction | **Important** |
| `.Mesh.Gbx` | varies | CPlugModelMesh | Mesh geometry subset | Pack files | **Hard** -- tied to Solid2 parsing | **Important** |
| `GpuCache.Gbx` | `0x09053000` | CPlugGpuCompileCache | Compiled DXBC shader bytecode, resource bindings, entry point names | Pack files (GpuCache_D3D11_SM5.zip) | **Medium** -- DXBC extraction is straightforward | **Nice-to-have** (we write our own shaders) |
| `.FuncShader.Gbx` | `0x05015000` | CPlugFuncShader | Shader function parameters (e.g., cloud rendering params) | Pack files | **Easy** -- tiny files (103 bytes), simple float parameters | **Nice-to-have** |
| `FuncCloudsParam.Gbx` | `0x09182000` | FuncCloudsParam | Cloud rendering parameters (altitude, density) | Pack files | **Easy** -- 93 bytes, float values | **Nice-to-have** |
| `ImageGen.Gbx` | `0x0902F000` | FuncImage | Procedural image generation parameters | Pack files | **Easy** -- small parameter files | **Nice-to-have** |

### 1.3 Pack File Types (Non-GBX)

| File Type | Format | Contents | Source | Complexity | Priority |
|-----------|--------|----------|--------|------------|----------|
| `.pak` | NadeoPak v18 | Compressed archive of GBX files (blocks, items, textures, materials) | Game installation | **Unknown/Hard** -- encrypted, proprietary format, 32-byte hash keys per file | **Critical blocker** (see Section 4) |
| `.Title.Pack.Gbx` | GBX wrapping NadeoPak | Master game content definition | Game installation | **Hard** -- GBX outer shell + NadeoPak inner content | **Critical blocker** |
| `.zip` | Standard ZIP | Shaders, skins, translations, flags, extras | Game installation | **Easy** -- standard ZIP extraction | **Important** |

### 1.4 Image/Texture Formats (within packs or embedded)

| Format | Usage | Browser Support | Priority |
|--------|-------|-----------------|----------|
| DDS (BC1-BC7) | Primary texture format, shader cache textures, skin channels (_D, _N, _R, _D_HueMask) | Requires transcoding (basis-universal) or WebGL compressed texture extensions | **MVP-critical** |
| JPEG | Map thumbnails (embedded in header chunk 0x03043007) | Native browser support | **MVP-critical** |
| WebP | Some textures (libwebp64.dll in game) | Native browser support | **Important** |
| PNG | Flags, UI elements | Native browser support | **Nice-to-have** |
| TGA | Stencil brushes, some legacy textures | Requires custom loader | **Nice-to-have** |
| EXR | HDR environment maps | Requires decoder library | **Nice-to-have** |

### 1.5 Audio Formats

| Format | Usage | Browser Support | Priority |
|--------|-------|-----------------|----------|
| Ogg Vorbis | Game music, sound effects (vorbis64.dll) | Native browser support via `<audio>` or Web Audio API | **Nice-to-have** (MVP can skip audio) |
| Bink Video | Cutscenes/intros (CPlugFileBink) | Requires transcoding | **Not needed** |
| WebM | Video textures | Native browser support | **Nice-to-have** |

---

## 2. GBX Parser Architecture (TypeScript)

### 2.1 Module Structure

```
@opentm/gbx-parser/
  src/
    reader.ts           -- BinaryReader: ArrayBuffer wrapper with LE primitives
    lzo.ts              -- LZO1X decompression (WASM or pure TS port)
    gbx.ts              -- Main GBX file parser (header, refs, body dispatch)
    lookback.ts         -- LookbackString table (per-chunk-context interning)
    class-registry.ts   -- Class ID -> parser mapping + legacy ID remap table
    node-ref.ts         -- Internal/external node reference resolution
    types.ts            -- All GBX data types (Vec2, Vec3, Nat3, Iso4, Quat, Color, Id, FileRef)
    chunks/
      map.ts            -- CGameCtnChallenge chunks (0x030430XX)
      ghost.ts          -- CGameCtnGhost chunks (0x030920XX)
      replay.ts         -- CGameCtnReplayRecord chunks (0x030930XX)
      item.ts           -- CGameItemModel chunks
      block-info.ts     -- CGameCtnBlockInfo chunks (0x2E00XXXX)
      solid2.ts         -- CPlugSolid2Model chunks (0x090BB0XX)
      material.ts       -- CPlugMaterial / CPlugShaderApply chunks
      bitmap.ts         -- CPlugBitmap chunks (0x090110XX)
      static-object.ts  -- CPlugStaticObjectModel chunks
    output/
      map-data.ts       -- Parsed map output types (blocks, items, metadata)
      ghost-data.ts     -- Parsed ghost output types (samples, checkpoints)
      mesh-data.ts      -- Parsed mesh output types (vertices, indices, materials)
  tests/
    fixtures/           -- Real .Gbx files for integration testing
    reader.test.ts
    gbx.test.ts
    map.test.ts
    ghost.test.ts
```

### 2.2 Core: BinaryReader (`reader.ts`)

The BinaryReader wraps an `ArrayBuffer` with little-endian read methods matching the exact GBX type system documented in doc 16, section 28.

```typescript
export class BinaryReader {
  private view: DataView;
  private pos: number = 0;

  constructor(buffer: ArrayBuffer, offset?: number) { ... }

  // Primitives (all little-endian per GBX spec)
  readUint8(): number;
  readUint16(): number;
  readUint32(): number;
  readInt32(): number;
  readInt16(): number;
  readInt8(): number;
  readFloat32(): number;
  readFloat64(): number;
  readBool(): boolean;          // uint32, 0 or 1 (doc 16 section 12)

  // Compound types
  readVec2(): Vec2;             // 2x float32
  readVec3(): Vec3;             // 3x float32
  readVec4(): Vec4;             // 4x float32
  readQuat(): Quat;             // 4x float32 (x, y, z, w)
  readNat3(): Nat3;             // 3x uint32 (block grid coords)
  readColor(): Color;           // 4x float32 (r, g, b, a)
  readIso4(): Iso4;             // 3x3 rotation matrix + vec3 position (48 bytes)

  // String types
  readString(): string | null;  // uint32 length + UTF-8 bytes; 0=empty, 0xFFFFFFFF=null
  readBytes(count: number): Uint8Array;

  // Navigation
  get position(): number;
  seek(pos: number): void;
  skip(count: number): void;
  get remaining(): number;
}
```

### 2.3 LZO Decompression (`lzo.ts`)

LZO1X is confirmed as the body compression algorithm (doc 16 section 8, validated against real files in doc 26). Options for browser implementation:

1. **WASM port of minilzo** (recommended) -- ~8KB WASM module, fastest execution
2. **Pure TypeScript port of lzo1x-decompress** -- ~300 lines, no WASM dependency, ~3x slower
3. **Existing npm packages**: `lzo-ts`, `minilzo-js` -- verify they handle LZO1X-1 correctly

The decompression interface:

```typescript
export function lzoDecompress(
  compressed: Uint8Array,
  uncompressedSize: number
): Uint8Array;
```

Validation: test against TechFlow.Map.Gbx body (21,867 compressed -> 170,018 uncompressed).

### 2.4 LookbackString System (`lookback.ts`)

The lookback string system is the most error-prone part of GBX parsing. Based on corrected analysis from doc 16 section 29 and validated against real files in doc 26:

```typescript
export class LookbackStringTable {
  private strings: string[] = [];
  private versionRead: boolean = false;

  read(reader: BinaryReader): string {
    // First call in a context: read version marker (must be 3)
    if (!this.versionRead) {
      const version = reader.readUint32();
      assert(version === 3, `Unexpected lookback version: ${version}`);
      this.versionRead = true;
    }

    const value = reader.readUint32();
    if (value === 0xFFFFFFFF) return '';

    const flags = (value >>> 30) & 0x3;
    const index = value & 0x3FFFFFFF;

    switch (flags) {
      case 0b00: return '';                                   // Empty
      case 0b01:                                              // New string (0x40000000 prefix)
        const s1 = reader.readString()!;                      // Inline string follows
        this.strings.push(s1);
        return s1;
      case 0b10: return this.strings[index - 1];              // Back-reference (1-based)
      case 0b11:                                              // New string (0xC0000000 prefix)
        const s2 = reader.readString()!;
        this.strings.push(s2);
        return s2;
    }
  }

  reset(): void {
    this.strings = [];
    this.versionRead = false;
  }
}
```

**Critical**: Both `0b01` and `0b11` flags indicate new inline strings in TM2020 files. The old documentation claiming `0b01` = "well-known string ID" is INCORRECT for TM2020 (corrected in doc 16 section 29, verified in doc 26 hex walkthrough).

**Scope rules**: The lookback table is reset for each header chunk, but shared across all body chunks for a single node. Encapsulated chunks (0x03043040, 0x03043043, 0x03043044, 0x0304304E, 0x0304304F, 0x03043054, 0x03043058) reset the lookback table locally.

### 2.5 Class Registry (`class-registry.ts`)

Maps class IDs to chunk parsers, with legacy ID remapping (doc 16 sections 11, 23):

```typescript
type ChunkParser = (reader: BinaryReader, context: ParseContext) => void;

interface ClassDefinition {
  name: string;
  chunks: Map<number, ChunkParser>;  // chunk_id -> parser
}

export class ClassRegistry {
  private classes: Map<number, ClassDefinition> = new Map();
  private remapTable: Map<number, number> = new Map();

  constructor() {
    this.initRemapTable();   // All entries from doc 16 section 23
    this.registerMap();      // CGameCtnChallenge chunks
    this.registerGhost();    // CGameCtnGhost chunks
    this.registerReplay();   // CGameCtnReplayRecord chunks
    this.registerItem();     // CGameItemModel chunks
    this.registerSolid2();   // CPlugSolid2Model chunks
    this.registerMaterial(); // Material chunks
  }

  remap(classId: number): number {
    return this.remapTable.get(classId) ?? classId;
  }

  getChunkParser(chunkId: number): ChunkParser | undefined {
    const classBase = this.remap(chunkId & 0xFFFFF000);
    const chunkIndex = chunkId & 0x00000FFF;
    const normalizedId = classBase | chunkIndex;
    const classDef = this.classes.get(classBase);
    return classDef?.chunks.get(normalizedId);
  }
}
```

The complete remap table includes 80+ entries from doc 16 section 23 (engines 0x24->0x03, 0x0A->0x09, 0x08->0x09, 0x05->0x09, 0x07->0x09, 0x06->0x09, plus cross-engine remaps).

### 2.6 Main GBX Parser (`gbx.ts`)

Follows the exact 12-step parsing tutorial from doc 16 section 26, validated against real files in doc 26:

```typescript
export interface GbxFile<T = unknown> {
  version: number;
  classId: number;
  className: string;
  formatFlags: { binary: boolean; bodyCompressed: boolean; streamCompressed: boolean; hasRefs: boolean };
  headerChunks: HeaderChunk[];
  nodeCount: number;
  references: ExternalRef[];
  body: T;
}

export class GbxParser {
  private registry: ClassRegistry;
  private nodes: Map<number, unknown> = new Map();

  parse(buffer: ArrayBuffer): GbxFile {
    const reader = new BinaryReader(buffer);

    // Step 1: Magic "GBX" (3 bytes)
    const magic = String.fromCharCode(reader.readUint8(), reader.readUint8(), reader.readUint8());
    if (magic !== 'GBX') throw new Error('Not a GBX file');

    // Step 2: Version (uint16 LE)
    const version = reader.readUint16();
    if (version < 3 || version > 6) throw new Error(`Unsupported GBX version: ${version}`);

    // Step 3: Format flags (4 chars, v6+ only)
    let formatFlags = { binary: true, bodyCompressed: false, streamCompressed: false, hasRefs: true };
    if (version >= 6) {
      const b0 = reader.readUint8(); // 'B' or 'T'
      const b1 = reader.readUint8(); // 'U' or 'C'
      const b2 = reader.readUint8(); // 'U' or 'C'
      const b3 = reader.readUint8(); // 'R' or 'E'
      formatFlags = {
        binary: b0 === 0x42,
        bodyCompressed: b1 === 0x43,
        streamCompressed: b2 === 0x43,
        hasRefs: b3 === 0x52,
      };
      if (!formatFlags.binary) throw new Error('Text GBX format not supported');
    }

    // Step 4: Class ID (uint32)
    const rawClassId = reader.readUint32();
    const classId = this.registry.remap(rawClassId);

    // Step 5-8: Header chunks
    let headerChunks: HeaderChunk[] = [];
    if (version >= 6) {
      const userDataSize = reader.readUint32();
      if (userDataSize > 0) {
        const numChunks = reader.readUint32();
        headerChunks = this.parseHeaderChunks(reader, numChunks);
      }
    }

    // Step 9: Node count
    const nodeCount = reader.readUint32();

    // Step 10: Reference table
    const numExternal = reader.readUint32();
    const references = numExternal > 0
      ? this.parseReferenceTable(reader, numExternal, version)
      : [];

    // Step 11: Body decompression
    let bodyReader: BinaryReader;
    if (formatFlags.streamCompressed) {
      const uncompressedSize = reader.readUint32();
      const compressedSize = reader.readUint32();
      const compressed = reader.readBytes(compressedSize);
      const decompressed = lzoDecompress(compressed, uncompressedSize);
      bodyReader = new BinaryReader(decompressed.buffer);
    } else {
      bodyReader = reader; // Read body directly
    }

    // Step 12: Parse body chunks until 0xFACADE01
    const body = this.parseBodyChunks(bodyReader, classId);

    return { version, classId, className: '...', formatFlags, headerChunks, nodeCount, references, body };
  }
}
```

### 2.7 Map Chunk Parsers (`chunks/map.ts`)

Priority chunks for CGameCtnChallenge (class 0x03043000):

| Chunk ID | Priority | Content | Notes |
|----------|----------|---------|-------|
| `0x03043002` | MVP | Map UID, environment, author login | Header chunk |
| `0x03043003` | MVP | Map name, mood, decoration, map type | Header chunk, contains CIdent with lookback strings |
| `0x03043004` | MVP | Version info | Header chunk, 4 bytes |
| `0x03043005` | MVP | XML metadata string | Header chunk, heavy |
| `0x03043007` | MVP | Thumbnail JPEG + comments | Header chunk, heavy, JPEG extraction |
| `0x03043008` | MVP | Author zone path | Header chunk |
| `0x0304300D` | MVP | Vehicle reference (car type) | Body chunk |
| `0x03043011` | MVP | Block data array (main) | Body chunk, lookback block names + grid coords |
| `0x0304301F` | MVP | Block data (newer format) | Body chunk, extended block fields |
| `0x03043040` | MVP | Anchored objects (items) | Body chunk, **encapsulated** (resets lookback) |
| `0x03043043` | Important | Zone genealogy | Body chunk, encapsulated |
| `0x03043044` | Important | Script metadata | Body chunk, encapsulated |
| `0x03043048` | Important | Baked blocks | Body chunk |
| `0x0304304B` | Important | Medal times / objectives | Body chunk |
| `0x03043054` | Important | Embedded items ZIP | Body chunk, encapsulated, contains custom item GBX files |

### 2.8 Types (`types.ts`)

```typescript
export interface Vec2 { x: number; y: number }
export interface Vec3 { x: number; y: number; z: number }
export interface Vec4 { x: number; y: number; z: number; w: number }
export type Quat = Vec4;
export interface Nat3 { x: number; y: number; z: number }  // uint32 triple
export interface Color { r: number; g: number; b: number; a: number }
export interface Iso4 {
  rotation: [number, number, number, number, number, number, number, number, number]; // 3x3 matrix
  position: Vec3;
}

export interface CIdent { uid: string; collection: number; author: string }

export interface MapBlock {
  name: string;
  direction: 0 | 1 | 2 | 3;  // N, E, S, W
  coord: Nat3;
  flags: number;
  isFree: boolean;            // flags === 0xFFFFFFFF
  isGround: boolean;          // bit 15
  // Free block additional data:
  freePosition?: Vec3;
  freeRotation?: Vec3;        // Euler angles (pitch, yaw, roll)
}

export interface MapItem {
  model: string;
  position: Vec3;
  rotation: Quat | Vec3;      // Quaternion or Euler depending on version
  pivot: Vec3;
  animPhaseOffset: number;
  color: number;
  lightmapQuality: number;
}

export interface ParsedMap {
  uid: string;
  name: string;
  author: string;
  authorZone: string;
  decoration: CIdent;         // e.g. "NoStadium48x48Day"
  mapType: string;            // "TrackMania\TM_Race"
  vehicle: string;            // "CarSport" etc.
  thumbnail: Uint8Array;      // Raw JPEG bytes
  xml: string;                // XML metadata from chunk 0x03043005
  size: Nat3;                 // Map grid dimensions (48, 255, 48 typical)
  blocks: MapBlock[];
  items: MapItem[];
  medalTimes: { bronze: number; silver: number; gold: number; author: number };
  embeddedItems: Map<string, ArrayBuffer>;  // name -> raw GBX data
}
```

---

## 3. Map Loading Pipeline (Exact Steps)

### Overview

From URL to renderable scene, the pipeline has 10 major phases. Each phase is described with its inputs, outputs, failure modes, and estimated timing.

### Step 1: Fetch .Map.Gbx

**Input**: URL (from TMX API, Nadeo API, or direct file upload)
**Output**: `ArrayBuffer` containing the complete .Map.Gbx file
**Failure modes**: Network error, 404, CORS rejection, file too large
**Timing**: 50-500ms (typical map = 20-200 KB, depends on embedded items)

```
Sources:
  - TMX API: https://trackmania.exchange/mapsearch2/search?api=on
  - Nadeo Core API: /maps/info?mapUid=...
  - User upload: File API -> ArrayBuffer
  - Server cache: CDN-served pre-fetched maps
```

### Step 2: Parse GBX Header

**Input**: `ArrayBuffer` from step 1
**Output**: Magic validated, version (6), format flags ("BUCR"), class ID (`0x03043000`), header chunk index table
**Failure modes**: Not a GBX file, unsupported version, not a map (wrong class ID)
**Timing**: <1ms (first ~100 bytes)

All TM2020 maps use version 6, format "BUCR", class `0x03043000`. The `user_data_size` field encompasses `4 (num_chunks) + 8*num_chunks (index) + sum(chunk_data_sizes)` (correction from doc 26).

### Step 3: Parse Header Chunks (metadata without decompression)

**Input**: Header chunk index + data from step 2
**Output**: Map name, author, UID, thumbnail JPEG, XML metadata, decoration name, medal times
**Failure modes**: Corrupt lookback strings, unexpected chunk version
**Timing**: <5ms (parse 6 header chunks, ~25 KB of data)

This step does NOT require body decompression and can provide immediate UI feedback (map name, thumbnail) while the body loads.

Key header chunks parsed:
- `0x03043002`: UID, environment (lookback string), author login
- `0x03043003`: CIdent (uid/collection/author), map name, decoration CIdent (e.g. "NoStadium48x48Day", collection 26 = Stadium, author "Nadeo"), map kind
- `0x03043005`: XML string with full metadata
- `0x03043007`: JPEG thumbnail (24 KB typical, marked "heavy")
- `0x03043008`: Author zone ("World|Africa|South Africa")

### Step 4: Decompress Body (LZO1X)

**Input**: Compressed body section (starts after reference table)
**Output**: Decompressed body byte stream
**Failure modes**: LZO decompression error, size mismatch
**Timing**: 2-10ms (typical: 22 KB compressed -> 170 KB decompressed, 12.9% ratio)

Read `uncompressed_size` (uint32) and `compressed_size` (uint32), then decompress `compressed_size` bytes using LZO1X. Validate output length equals `uncompressed_size`.

For TechFlow.Map.Gbx: 21,867 bytes -> 170,018 bytes. For complex maps with many embedded items: can be 500 KB compressed -> 5 MB decompressed.

### Step 5: Parse Body Chunks (blocks, items, MediaTracker)

**Input**: Decompressed body byte stream from step 4
**Output**: Arrays of `MapBlock[]`, `MapItem[]`, vehicle reference, medal times, embedded item data
**Failure modes**: Unknown non-skippable chunk, corrupt chunk data, lookback table overflow
**Timing**: 5-50ms (proportional to block/item count)

The body is a sequential chunk stream terminated by `0xFACADE01`. Each chunk either has a "SKIP" marker (0x534B4950) + size (safe to skip if unknown) or is non-skippable (must parse or fail).

Critical body chunks:
- `0x03043011` / `0x0304301F`: Block array -- for each block: lookback name, direction (byte), Nat3 grid coord, flags (uint32). If `flags == 0xFFFFFFFF`, read additional free-block position/rotation.
- `0x03043040` (encapsulated): Item array -- for each: lookback model name, Vec3 position, rotation, metadata.
- `0x03043054` (encapsulated): Embedded items -- ZIP archive of custom .Item.Gbx files.

### Step 6: Resolve Block Definitions (Geometry Lookup)

**Input**: `MapBlock[]` array with block names (e.g., "StadiumRoadMainStraight")
**Output**: For each block: geometry data (vertices, indices), material assignments, collision mesh
**Failure modes**: **Unknown block name** (no geometry available), missing variant
**Timing**: 1-10ms (lookup from pre-loaded block library)

**THIS IS THE PRIMARY BLOCKER. See Section 4 for detailed analysis.**

Block names follow the pattern `Stadium{Category}{Shape}{Variant}`. Each block occupies a 32m x 8m x 32m grid cell (some span multiple cells). The engine looks up block definitions from pack files (Stadium.pak) which contain CGameCtnBlockInfo -> CPlugStaticObjectModel -> CPlugSolid2Model mesh data.

For OpenTM MVP, this step maps block names to our block mesh library (see Section 4 for how we build it).

### Step 7: Resolve Item Models (Geometry Lookup)

**Input**: `MapItem[]` array with item model references
**Output**: For each item: mesh data, material assignments
**Failure modes**: Missing item model (custom item not embedded, pack file not available)
**Timing**: 5-50ms per item (embedded items require nested GBX parse)

Items fall into three categories:
1. **Built-in items**: Referenced by well-known paths (e.g., `\Vehicles\Items\CarSport.Item.gbx`). Must be pre-extracted from pack files.
2. **Embedded items**: Custom items stored in chunk `0x03043054` as a ZIP. Each entry is a complete .Item.Gbx that must be recursively parsed.
3. **External items**: Referenced by path in user's Items/ folder. Not available in browser context; must be pre-uploaded.

### Step 8: Build Collision Mesh

**Input**: Block geometries + item geometries from steps 6-7
**Output**: Combined physics collision mesh for the entire map
**Failure modes**: Missing collision data for blocks/items
**Timing**: 10-50ms (merge all collision primitives)

Each block has a physics surface type (from NadeoImporterMaterialLib.txt -- 18 surface types). The collision mesh maps each triangle to a surface ID for physics behavior (Asphalt, Dirt, Ice, Grass, etc.).

For MVP: can use simplified box/cylinder collision matching the 32m x 8m x 32m grid, with surface type based on block name pattern matching.

### Step 9: Build Render Scene Graph

**Input**: All block/item geometries + materials + textures
**Output**: WebGPU/Three.js scene with draw calls organized by material
**Failure modes**: Unsupported material type, texture loading failure
**Timing**: 20-100ms (batch geometry, create GPU buffers)

Organization:
1. Group blocks by material for batched rendering
2. Create instanced draw calls for repeated block types
3. Assign material/shader to each draw group
4. Position items with their world-space transforms
5. Set up lighting (ambient + directional for MVP)

### Step 10: Load/Generate Lightmaps

**Input**: Map lightmap data (if pre-baked) or scene geometry
**Output**: Lightmap textures for indirect lighting
**Failure modes**: Missing lightmap data, computation too slow
**Timing**: 0ms (skip for MVP) to 5-30 seconds (full bake)

Real TM2020 maps have lightmaps pre-baked (stored in body chunks). For MVP, use flat ambient lighting. For quality rendering, either:
- Extract pre-baked lightmaps from the .Map.Gbx body (if present -- `lightmap="0"` in XML means none)
- Compute lightmaps server-side as a pre-processing step
- Use real-time ambient occlusion approximation (SSAO)

### Step-by-Step Timing Summary

| Step | MVP Time | Full Time | Can Parallelize? |
|------|----------|-----------|-----------------|
| 1. Fetch | 100ms | 500ms | -- |
| 2. Header parse | <1ms | <1ms | -- |
| 3. Header chunks | <5ms | <5ms | Show thumbnail immediately |
| 4. LZO decompress | 5ms | 10ms | -- |
| 5. Body parse | 10ms | 50ms | -- |
| 6. Block resolve | 5ms | 50ms | Parallel with step 7 |
| 7. Item resolve | 10ms | 200ms | Parallel with step 6 |
| 8. Collision mesh | 10ms | 50ms | After 6+7 |
| 9. Scene build | 20ms | 100ms | After 8 |
| 10. Lightmaps | 0ms (skip) | 10s | Background |
| **Total** | **~160ms** | **~11s** | -- |

---

## 4. The Block Mesh Problem (Detailed Analysis)

This is THE make-or-break problem for OpenTM. Block geometry -- the 3D meshes for every road piece, platform, decoration, and structure in Trackmania -- is stored inside encrypted `.pak` files that ship with the game. Without these meshes, we cannot render maps.

### 4.1 The Scale of the Problem

From NadeoImporterMaterialLib.txt and block naming analysis (doc 28 section 9):

- **~200-300 unique block types** in the Stadium environment
- Each block type has **2 variants** (ground and air) with different mesh geometry
- Some blocks have **width multipliers** (x2, x3, x4) and **mirror variants**
- Total unique meshes: estimated **500-1000**
- All meshes are inside **Stadium.pak** (1.63 GB, NadeoPak v18 format, encrypted)

### 4.2 Approach A: Extract from .pak Files

#### Technical Assessment

NadeoPak v18 format (doc 26 section 10):
- Magic: "NadeoPak" (8 bytes)
- Version: 18 (uint32)
- Two 16-byte hash/key fields at offsets 0x0C and 0x1C
- Flags at 0x2C (observed values: 0x00000007)
- Alignment field at 0x30 (0x00003000 or 0x00004000)
- String table follows the header

The SHA-256 checksums at offset 0x0C match those in `updater_files.txt`, confirming these are integrity verification hashes, not encryption keys themselves.

#### Encryption Status

**The pack files are encrypted.** Evidence:
- No community tool can read TM2020 .pak files directly without the game's decryption keys
- GBX.NET does NOT support reading .pak files -- it only reads individual .Gbx files
- The game binary contains the decryption logic but extracting and using those keys would constitute circumventing copy protection

#### Existing Tools

- **GBX.NET**: Can read .Gbx files but NOT .pak archives
- **NadeoImporter.exe**: The official tool converts FROM external formats (FBX) TO .Gbx -- it does not extract FROM packs
- **No known public tool** extracts files from TM2020 NadeoPak v18 archives

#### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| Technical feasibility | **Uncertain** -- would require reverse-engineering the NadeoPak decryption from Trackmania.exe, which is achievable but laborious |
| Legal risk | **HIGH** -- circumventing encryption of game assets likely violates the DMCA (US) and EU Copyright Directive, plus Nadeo/Ubisoft EULA |
| Effort | **Very high** -- weeks of RE work on the decryption subsystem, then building an extractor |
| Quality | **Perfect** -- original game meshes, textures, and materials |
| Maintenance | **Poor** -- game updates could change encryption, requiring re-extraction |

**Recommendation: DO NOT PURSUE.** The legal risk alone makes this untenable for an open-source project. Even if technically possible, distributing extracted game assets would expose the project to takedown.

### 4.3 Approach B: Use GBX.NET to Pre-Extract

#### Technical Assessment

GBX.NET (C#/.NET, 400+ class parsers, actively maintained) can parse many GBX formats including:
- CGameCtnChallenge (maps)
- CGameCtnGhost (ghosts)
- CGameCtnReplayRecord (replays)
- CPlugSolid2Model (mesh geometry)
- CGameItemModel (items)
- CGameCtnBlockInfo (block definitions)

#### What GBX.NET CAN Do

GBX.NET can parse **individual .Gbx files** that have been extracted from packs. If we had the raw .Gbx files for each block, GBX.NET could parse CPlugSolid2Model to extract:
- Vertex positions (R32G32B32_SFLOAT)
- Normals (R16G16B16A16_SNORM)
- UV coordinates (R32G32_SFLOAT, dual UV for lightmap)
- Tangent frames (R16G16B16A16_SNORM)
- Index buffers (triangle lists)
- Material references
- LOD levels

#### What GBX.NET CANNOT Do

- **Read .pak files** -- GBX.NET has no NadeoPak parser
- **Decrypt game assets** -- no decryption support
- **Extract block meshes from the running game** -- it is a file parser, not a runtime tool

#### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| Technical feasibility | **Only if we have extracted .Gbx files** -- which circles back to the pak extraction problem |
| Legal risk | **Same as Approach A** if the files were extracted from packs |
| Effort | **Low** once files are available -- GBX.NET is mature and well-tested |
| Quality | **Perfect** -- faithful parsing of Nadeo's mesh format |

**Recommendation: USE FOR CUSTOM ITEM PARSING.** GBX.NET (or our own TypeScript parser) is the right tool for parsing embedded items and user-created .Item.Gbx files. But it does not solve the built-in block mesh problem.

### 4.4 Approach C: Procedural Generation

#### Concept

Generate block geometry algorithmically from block metadata:
- Block name encodes shape (Straight, Curve, Slope, Turn, etc.)
- Grid dimensions are known (32m x 8m x 32m)
- Road width and curve radius can be inferred from name
- Direction and variant are stored in the map data

#### What Can Be Generated

**Road blocks** (highest visual impact):

| Block Pattern | Geometry Generation Strategy |
|---------------|------------------------------|
| `StadiumRoadMainStraight` | Flat rectangle, 32x32m, road texture on top, support walls on sides |
| `StadiumRoadMainCurve` | 90-degree curved surface, inner/outer radius from grid snap |
| `StadiumRoadMainSlope` | Angled rectangle, 8m rise over 32m run |
| `StadiumRoadMainSlopeBase` / `SlopeEnd` | Transition curves (quarter-circle profile) |
| `StadiumRoadMainTilt` | Banked surface, tilted perpendicular to road |
| `StadiumRoadMainChicane` | S-curve surface |
| `StadiumRoadMainDiagLeft/Right` | 45-degree diagonal surface |
| `StadiumRoadMainCross` | Intersection (+shaped road) |
| Width variants (`x2`, `x3`, `x4`) | Multiply road width by factor |
| Mirror variants | Mirror geometry on appropriate axis |

**Platform blocks**: Same shapes as road blocks, different texture (no road markings).

**Decoration blocks**: Simpler geometry -- rectangular prisms, hillside wedges.

**Support structures**: Pylons as cylinders/boxes, pillars as extruded rectangles.

#### Quality Assessment

| Quality Level | Description | Effort | Visual Result |
|---------------|-------------|--------|---------------|
| **Minecraft-style** | Pure rectangular prisms, solid colors | 1-2 weeks | Functional but ugly. Recognizable as TM maps but aesthetically poor. |
| **Shaped blocks** | Correct shapes (curves, slopes) with flat-shaded materials | 3-4 weeks | Good enough for gameplay. Road surfaces match driving feel. |
| **Textured blocks** | Shaped blocks + procedural textures or community textures | 4-6 weeks | Acceptable quality. Looks like a TM-inspired game. |
| **High fidelity** | Detailed meshes matching TM2020's visual complexity (railings, road markings, surface detail) | 3-6 months | Very close to original. Would require per-block hand-modeling. |

#### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| Technical feasibility | **HIGH** -- all shape information is derivable from block names and grid system |
| Legal risk | **NONE** -- we are creating original geometry, not copying Nadeo's |
| Effort | **Medium** (shaped blocks) to **Very high** (high fidelity) |
| Quality | **Acceptable for MVP** at shaped-block level, **not competitive** with original game |
| Maintenance | **Excellent** -- no dependency on game files, no encryption to break |

**Recommendation: USE FOR MVP.** This is the safest and most maintainable approach. Start with shaped blocks (correct geometry, simple materials), then improve quality over time.

### 4.5 Approach D: Community Asset Creation

#### Concept

Engage the Trackmania modding community to create open-source block meshes in Blender that match TM2020's block dimensions and visual style.

#### Implementation

1. Define a block specification document: grid dimensions, connection points, naming conventions
2. Create a Blender template with the 32m x 8m x 32m grid reference
3. Community contributors model blocks using Blender
4. Export as glTF 2.0 (browser-native format)
5. Build an open-source block asset library
6. Host the library as an npm package or CDN resource

#### Block Count Estimate

To match TM2020's Stadium environment, we need approximately:
- ~20 road shape templates x 4 rotations x 2 variants (ground/air) = ~160 road blocks
- ~20 platform shape templates x 4 rotations x 2 variants = ~160 platform blocks
- ~30 decoration/terrain blocks = ~30
- ~10 special blocks (gates, checkpoints, finish) = ~10
- Support structures (pylons, pillars) = ~10
- **Total: ~370 unique meshes**

This is achievable for a motivated community over several months, but is a significant art pipeline.

#### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| Technical feasibility | **HIGH** -- Blender to glTF is a well-established pipeline |
| Legal risk | **NONE** -- original community-created assets |
| Effort | **Very high** -- 370+ meshes is a large art project, requires coordination |
| Quality | **Variable** -- depends on contributor skill; can exceed game quality for individual blocks |
| Maintenance | **Good** -- community can iterate and improve |

**Recommendation: USE FOR POST-MVP QUALITY IMPROVEMENT.** Start a community asset project in parallel with procedural generation. As community meshes become available, swap them in to replace procedural geometry.

### 4.6 Approach E: Runtime Capture via Openplanet

#### Concept

Write an Openplanet plugin that runs inside TM2020 and intercepts D3D11 draw calls to capture the vertex/index buffers for each block type, then exports them as a mesh library.

#### Technical Analysis

Openplanet provides these relevant capabilities:
- AngelScript scripting engine with access to game objects
- Plugin render hooks (`Plugin render early`, `Plugin render interface`, `Plugin render`)
- Access to `ISceneVis` scene manager and `NSceneVehicleVis_SMgr` vehicle manager
- ImGui overlay for UI
- Game hooks for physics, rendering, and script execution

However, Openplanet does **NOT** provide:
- Direct access to D3D11 device/context
- Ability to intercept draw calls or read GPU buffers
- Access to CPlugSolid2Model vertex data through its public API
- Raw mesh extraction functionality

#### Would a Custom D3D11 Wrapper Work?

A separate DLL (not through Openplanet) could proxy d3d11.dll to intercept:
- `ID3D11DeviceContext::DrawIndexed()` -- capture vertex/index buffers
- `ID3D11DeviceContext::Map()` -- read buffer contents
- `ID3D11Device::CreateBuffer()` -- track buffer creation with vertex/index data

This is technically how tools like RenderDoc and PIX work. However:
- The game renders many objects per frame; correlating draw calls to specific blocks requires understanding the render pipeline
- Block meshes are instanced -- a single draw call may render many instances of the same block
- Material/texture binding would need to be captured alongside geometry
- This would need to run on a Windows machine with the actual game

#### Can Openplanet Access Block Meshes via Game Objects?

Openplanet can access game objects through reflection. In theory:
1. Get a `CGameCtnBlock` instance from the map
2. Navigate to its `CGameCtnBlockInfo` definition
3. Navigate to its `CPlugStaticObjectModel` mesh
4. Navigate to its `CPlugSolid2Model` vertex/index data

The obstacle is that Openplanet's reflection exposes ManiaScript-level properties, not raw C++ memory. The mesh data fields (vertex buffers, index buffers) are not exposed through ManiaScript and would require accessing memory at known offsets -- which changes between game versions.

The VehicleState plugin demonstrates that raw memory access IS possible (it reads CSceneVehicleVisState at specific offsets), but:
- Offsets break with every game update
- Reading vertex buffer data requires knowing the exact memory layout of CPlugSolid2Model
- The data may be GPU-resident (not in system memory)

#### Feasibility Assessment

| Criterion | Assessment |
|-----------|------------|
| Technical feasibility | **Low-Medium** -- theoretically possible via D3D11 interception or raw memory access, but extremely fragile |
| Legal risk | **Medium** -- capturing rendered geometry is a gray area; Openplanet's ToS may restrict this use |
| Effort | **Very high** -- custom D3D11 proxy DLL + block identification + export pipeline |
| Quality | **Perfect** -- exact game geometry if successfully captured |
| Maintenance | **Very poor** -- breaks with every game update, memory offsets change |

**Recommendation: DO NOT PURSUE FOR MVP.** Could be explored as a one-time capture tool to bootstrap the community asset library, but not reliable enough for ongoing use.

### 4.7 Recommended Strategy (Phased)

```
Phase 1 (MVP): Procedural Generation
  - Generate shaped block geometry from block names
  - Correct dimensions (32m x 8m x 32m grid)
  - Correct shapes (curves, slopes, tilts, chicanes)
  - Simple materials (solid colors per surface type)
  - Result: Maps are recognizable and playable, but visually basic

Phase 2 (Post-MVP): Community Asset Library + Procedural Textures
  - Launch community block modeling project
  - Add procedural textures (road markings, grass, barriers)
  - Replace procedural blocks with community meshes as available
  - Priority: road blocks first (highest visual impact)
  - Result: Much improved visual quality for common blocks

Phase 3 (Long-term): Complete Asset Library
  - Full community mesh library for all block types
  - PBR materials matching TM2020's visual style
  - LOD system for performance
  - Result: Visually competitive with TM2020 at medium settings
```

### 4.8 Procedural Block Generation Specification

For Phase 1, every procedurally generated block needs:

```typescript
interface ProceduralBlock {
  name: string;                    // Block name pattern match
  gridSize: Nat3;                  // Grid cells occupied (usually 1,1,1)
  geometry: {
    positions: Float32Array;       // Vec3 vertices
    normals: Float32Array;         // Vec3 normals
    uvs: Float32Array;             // Vec2 texture coordinates
    indices: Uint32Array;          // Triangle list
  };
  collisionSurface: SurfaceType;   // From NadeoImporterMaterialLib.txt
  materialSlots: string[];         // Material names for each face
  clipPoints: ClipPoint[];         // Connection points on faces (for route validation)
}
```

The `SurfaceType` enum (18 values from doc 09 section 2.2):
```
Asphalt, RoadSynthetic, Dirt, RoadIce, Plastic, Rubber, Metal,
ResonantMetal, MetalTrans, Wood, Concrete, Grass, Green, Pavement,
Ice, Rock, Sand, Snow, NotCollidable
```

Block name -> surface type mapping examples:
- `StadiumRoadMain*` -> `Asphalt` (top face), `Metal` (sides)
- `StadiumPlatform*` -> `Asphalt`
- `StadiumGrass*` -> `Grass`
- `StadiumWater*` -> `Plastic` (water borders)
- `StadiumPillar*` -> `Metal`
- `StadiumDecoHill*` -> `Grass`

---

## 5. Material System

### 5.1 Material Database (NadeoImporterMaterialLib.txt)

The complete material database from doc 09 section 2 defines **208 materials** in the Stadium library. Each material specifies:
- **SurfaceId**: Physics behavior (18 types)
- **GameplayId**: Gameplay modifier (always "None" in the material library -- gameplay effects are block-level)
- **UV Layers**: Texture channel mapping (BaseMaterial UV0, Lightmap UV1, or DColor0)

### 5.2 Material Categories

| Category | Count | Surface Types | UV Pattern |
|----------|-------|--------------|------------|
| Roads | 9 | Asphalt, RoadSynthetic, Dirt, RoadIce, Plastic, Metal | Standard (Base + Lightmap) |
| Technics | 16 | Rubber, Plastic, Concrete, Wood, ResonantMetal, Metal, RoadSynthetic, MetalTrans | Standard |
| Ad Screens | 6 | MetalTrans | Standard |
| Racing | 28 | Metal, MetalTrans, NotCollidable | Standard + DColor0 for chronos |
| Decoration | 4 | Grass, NotCollidable | Lightmap only |
| Item Obstacles | 13 | Metal, Plastic | Mixed |
| Item Deco | 10 | Metal, Concrete | Standard |
| Decals | 20 | NotCollidable | Base + DColor0 |
| Special/Turbo | 5 | NotCollidable, MetalTrans | Base + DColor0 |
| Custom | 14 | Various (all 18 types) | Lightmap only |
| Modable | 14 | Various | Mixed |
| Modifier Materials | ~70 | NotCollidable, MetalTrans | With DLinkFull references |

### 5.3 Material -> Shader Variant Selection

For the browser renderer, materials map to shader variants:

```typescript
type ShaderVariant =
  | 'opaque-lightmapped'      // Standard: BaseMaterial UV0 + Lightmap UV1
  | 'opaque-unlit'            // Lightmap only: single UV channel
  | 'transparent'             // MetalTrans materials
  | 'decal'                   // NotCollidable + DColor0 (projected)
  | 'emissive'                // Self-illuminating materials
  | 'water'                   // Water surface shader
  | 'glass'                   // GlassWaterWall
  | 'grass'                   // Grass with wind animation;

function selectShader(material: MaterialDef): ShaderVariant {
  if (material.surfaceId === 'NotCollidable') {
    return material.hasColor0 ? 'decal' : 'transparent';
  }
  if (material.surfaceId === 'MetalTrans') return 'transparent';
  if (material.name.startsWith('Grass')) return 'grass';
  if (material.name.includes('Water')) return 'water';
  if (material.name.includes('Glass')) return 'glass';
  if (material.name.includes('SelfIllum')) return 'emissive';
  if (material.uvLayers.length === 1 && material.uvLayers[0].type === 'Lightmap') {
    return 'opaque-unlit';
  }
  return 'opaque-lightmapped';
}
```

### 5.4 PBR Parameter Mapping

TM2020 uses PBR materials with texture channels visible in the skin system (doc 09 section 3.4):
- `_D`: Diffuse / Albedo
- `_N`: Normal map
- `_R`: Roughness
- `_D_HueMask`: Color customization mask (for car paint / colorizable materials)

For the browser renderer, map to standard PBR:

| TM2020 Channel | PBR Parameter | WebGPU Binding |
|----------------|---------------|----------------|
| `_D` (diffuse) | `baseColor` | Texture slot 0 |
| `_N` (normal) | `normalMap` | Texture slot 1 |
| `_R` (roughness) | `roughness` | Texture slot 2 |
| `_D_HueMask` | Custom: hue shift mask | Texture slot 3 (optional) |
| Lightmap UV1 | `lightMap` | Texture slot 4 |

### 5.5 Surface Type -> Physics Behavior

Each of the 18 surface types maps to a physics behavior coefficient set:

| Surface | Grip | Rolling Resistance | Sound | Visual |
|---------|------|--------------------|-------|--------|
| Asphalt | High | Low | Road tire noise | Dark gray, road markings |
| Dirt | Medium | High | Loose surface | Brown, dust particles |
| Grass | Low | Medium | Grass swish | Green, foliage |
| Ice/RoadIce | Very Low | Very Low | Ice scrape | White/blue, reflective |
| Plastic | Low | Low | Squeak | Bright colors |
| Metal | Medium | Low | Metallic clang | Gray, reflective |
| Wood | Medium | Medium | Wood thud | Brown, grain pattern |
| Rubber | High | Medium | Rubber squeak | Dark, matte |

For MVP physics, use a simplified grip coefficient table. Full physics matching is a separate effort.

---

## 6. Texture Pipeline

### 6.1 Texture Formats in TM2020

From the DLL analysis (doc 09) and DXVK log analysis:

**Primary format**: DDS (DirectDraw Surface) with BC (Block Compression):
- BC1 (DXT1): RGB, 4:1 compression -- diffuse textures without alpha
- BC3 (DXT5): RGBA, 4:1 compression -- diffuse textures with alpha
- BC5 (ATI2): RG, 4:1 compression -- normal maps (two-channel)
- BC7: RGBA, variable -- high-quality textures

The DXVK log confirms `textureCompressionBC = YES` is required.

**Secondary formats**: WebP (via libwebp64.dll), JPEG (thumbnails), PNG (flags/UI).

### 6.2 Browser Texture Loading Strategy

BC-compressed DDS textures cannot be used directly in WebGL2/WebGPU on all platforms. Strategy:

**Option A: Basis Universal Transcoding (Recommended)**

Pre-process textures to Basis Universal (.basis or .ktx2) format. At runtime, the basis_universal transcoder converts to the platform's native compressed format:
- Desktop Chrome/Firefox: BC7/BC1 (native, zero-cost transcode)
- Mobile/Apple: ASTC or ETC2 (transcoded)
- Fallback: RGBA8 (uncompressed)

| Metric | Value |
|--------|-------|
| Transcoder size | ~200KB (WASM) |
| Transcode time | 1-5ms per texture |
| Compression ratio | ~6:1 vs RGBA8 |

**Option B: Runtime DDS Decoding**

Decompress BC textures to RGBA8 in JavaScript/WASM, upload as uncompressed. Simple but uses 4x more GPU memory.

**Option C: WebGPU Compressed Textures**

WebGPU supports `texture-compression-bc` as an optional feature. If available, upload DDS BC data directly. Requires feature detection and fallback.

**Recommended pipeline**:
1. Pre-process all textures to KTX2 with Basis Universal (server-side)
2. At runtime: detect GPU capabilities
3. If `texture-compression-bc`: use BC path (fastest, smallest)
4. Else: transcode from Basis Universal to platform-native format
5. Fallback: decompress to RGBA8

### 6.3 Texture Atlas Strategy

For block textures, atlasing reduces draw calls:

```
Block Texture Atlas Layout:
  - Road textures: 2048x2048 atlas (all road surface variants)
  - Platform textures: 2048x2048 atlas
  - Decoration textures: 1024x1024 atlas (grass, hills, water)
  - Structure textures: 1024x1024 atlas (metal, pylons, walls)
  - Special textures: 512x512 atlas (turbo, checkpoint effects)

Total GPU memory: ~20 MB compressed (BC7), ~80 MB uncompressed
```

UV coordinates in block meshes reference atlas sub-regions. The atlas is generated at build time.

### 6.4 Mipmap Generation

For procedural block textures (Phase 1), generate mipmaps at build time:
- Use `generateMipmap()` in WebGPU
- For pre-processed textures (KTX2/Basis), include mip chain in the file
- Minimum mip level: 4x4 (prevents texture swimming at distance)

For imported DDS textures, the mip chain is already present in the file.

### 6.5 Texture Sources for MVP

Since we cannot extract game textures from pak files:

1. **Procedural textures**: Generate simple road, grass, metal, etc. textures programmatically
2. **CC0 texture libraries**: Ambientcg.com, Polyhaven.com for PBR materials (asphalt, grass, concrete, metal, etc.)
3. **Community-created textures**: As part of the community asset project
4. **Minimal texture set**: For MVP, 10-15 base textures cover all material categories

---

## 7. Ghost/Replay Asset Pipeline

### 7.1 Replay Parsing Pipeline

```
1. Fetch .Replay.Gbx (typical: 1-5 MB)
2. Parse GBX header: class 0x03093000, format BUCR
3. Parse 3 header chunks:
   - 0x03093000: Replay info (map UID, author)
   - 0x03093001: XML metadata (heavy, best time, checkpoints, vehicle)
   - 0x03093002: Author info (name, zone)
4. Decompress body (LZO)
5. Parse body chunks:
   - Extract embedded .Map.Gbx (nested GBX with full map data)
   - Extract CGameCtnGhost instance(s)
   - Extract checkpoint times
   - Extract validation data
```

The embedded map means replays are self-contained -- no separate map download needed.

### 7.2 Ghost Sample Decoding

Ghost samples are stored in chunk `0x03092012` (CPlugEntRecordData), zlib-compressed within the LZO-decompressed body. Two compression layers:

```
File on disk
  -> LZO decompress (outer, GBX body)
    -> Parse ghost chunks
      -> zlib decompress (inner, sample data)
        -> Raw sample frames (22 bytes each, 50ms period)
```

Per-sample decoding (doc 30 section 7):

```typescript
interface GhostSample {
  position: Vec3;         // 3x float32 (12 bytes)
  angle: number;          // uint16 -> value / 0xFFFF * PI
  axisHeading: number;    // int16 -> value / 0x7FFF * PI
  axisPitch: number;      // int16 -> value / 0x7FFF * PI/2
  speed: number;          // int16 -> exp(value / 1000); 0x8000 = speed 0
  velHeading: number;     // int8 -> value / 0x7F * PI
  velPitch: number;       // int8 -> value / 0x7F * PI/2
}

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
    velHeading: (velHeadingRaw / 0x7F) * Math.PI,
    velPitch: (velPitchRaw / 0x7F) * (Math.PI / 2),
  };
}
```

### 7.3 Sample Interpolation

Ghost samples at 50ms intervals (20 Hz) must be interpolated to smooth 60 Hz rendering:

```typescript
function interpolateGhost(
  samples: GhostSample[],
  timeMs: number,
  samplePeriodMs: number = 50
): InterpolatedState {
  const sampleIndex = timeMs / samplePeriodMs;
  const i0 = Math.floor(sampleIndex);
  const i1 = Math.min(i0 + 1, samples.length - 1);
  const t = sampleIndex - i0;

  // Linear interpolation for position
  const position = lerpVec3(samples[i0].position, samples[i1].position, t);

  // Convert axis-angle to quaternion, then SLERP for rotation
  const q0 = axisAngleToQuat(samples[i0]);
  const q1 = axisAngleToQuat(samples[i1]);
  const rotation = slerp(q0, q1, t);

  // Exponential interpolation for speed (matches exponential encoding)
  const speed = samples[i0].speed * Math.pow(samples[i1].speed / samples[i0].speed, t);

  return { position, rotation, speed };
}
```

The axis-angle to quaternion conversion:
```typescript
function axisAngleToQuat(sample: GhostSample): Quat {
  // Axis direction from heading + pitch (spherical coordinates)
  const cosP = Math.cos(sample.axisPitch);
  const axis = {
    x: cosP * Math.sin(sample.axisHeading),
    y: Math.sin(sample.axisPitch),
    z: cosP * Math.cos(sample.axisHeading),
  };
  const halfAngle = sample.angle / 2;
  const sinHalf = Math.sin(halfAngle);
  return {
    x: axis.x * sinHalf,
    y: axis.y * sinHalf,
    z: axis.z * sinHalf,
    w: Math.cos(halfAngle),
  };
}
```

### 7.4 Ghost Car Rendering

Ghost cars are rendered as semi-transparent tinted versions of the car model:

```
Car model: Use the same car mesh as the player vehicle
Material: Modified shader with:
  - Alpha: 0.4-0.6 (semi-transparent)
  - Color tint: Blue/cyan for fastest ghost, green for second, etc.
  - No shadow casting
  - Additive or alpha-blended
Visual effects:
  - Ghost trail: Fading copies of car mesh at previous positions
  - Checkpoint flash: Glow effect when ghost crosses checkpoint
  - Dossard (number bib): Text overlay with ghost player name
```

### 7.5 Data Size Estimates

For a typical 38-second replay:
- Ghost samples: 760 samples x 22 bytes = 16.7 KB (uncompressed), ~5-10 KB (zlib compressed)
- Checkpoint times: 8 checkpoints x 4 bytes = 32 bytes
- Metadata: ~500 bytes
- Embedded map: 20-200 KB
- **Total replay: 100 KB - 5 MB** (depending on map complexity and embedded items)

---

## 8. Caching Strategy

### 8.1 Cache Layers

```
Layer 1: Browser HTTP Cache (automatic)
  - CDN-served assets with Cache-Control headers
  - Map files, texture atlases, block meshes
  - Invalidation: URL versioning (content hash in filename)

Layer 2: IndexedDB (parsed assets)
  - Parsed map data (blocks, items, metadata)
  - Decoded ghost samples
  - Converted textures (KTX2 -> GPU-ready format)
  - Key: content hash of source file
  - Invalidation: version-based (parser version + content hash)

Layer 3: Service Worker (offline support)
  - Cache-first strategy for static assets (block meshes, textures)
  - Network-first strategy for dynamic content (maps, replays)
  - Stale-while-revalidate for API responses
  - Storage quota management (limit to ~500 MB)

Layer 4: GPU Resource Cache (in-memory)
  - WebGPU buffer/texture handles
  - Eviction: LRU based on scene needs
  - Re-created from IndexedDB on cache miss
```

### 8.2 IndexedDB Schema

```typescript
// Database: opentm-assets, version 1
interface AssetDB {
  // Object store: maps
  maps: {
    key: string;           // Map UID
    value: {
      uid: string;
      name: string;
      author: string;
      thumbnail: Blob;     // JPEG
      parsedData: ParsedMap;
      rawGbx: ArrayBuffer; // Original file for re-parsing if parser version changes
      parserVersion: number;
      fetchedAt: number;
    };
  };

  // Object store: ghosts
  ghosts: {
    key: string;           // Ghost UID or replay UID + ghost index
    value: {
      samples: Float32Array;   // Flattened decoded samples
      checkpoints: Uint32Array;
      metadata: GhostMetadata;
      parserVersion: number;
    };
  };

  // Object store: block-meshes
  blockMeshes: {
    key: string;           // Block name
    value: {
      vertices: Float32Array;
      normals: Float32Array;
      uvs: Float32Array;
      indices: Uint32Array;
      materials: string[];
      version: number;     // Asset library version
    };
  };

  // Object store: textures
  textures: {
    key: string;           // Texture name/hash
    value: {
      format: 'ktx2' | 'rgba8' | 'bc7';
      width: number;
      height: number;
      data: ArrayBuffer;
      version: number;
    };
  };
}
```

### 8.3 Cache Invalidation

| Asset Type | Invalidation Trigger | Strategy |
|-----------|---------------------|----------|
| Map data | Parser version change | Re-parse from rawGbx in IndexedDB |
| Ghost data | Parser version change | Re-parse from replay file |
| Block meshes | Asset library version change | Download new asset package |
| Textures | Asset library version change | Download new texture package |
| API responses | TTL expiration | Stale-while-revalidate |

### 8.4 Progressive Loading

Show content as it becomes available:

```
T+0ms:     Show loading screen
T+100ms:   Map header parsed -> show map name, author, thumbnail
T+150ms:   Body parsed -> show wireframe block layout (block positions known)
T+200ms:   Procedural geometry generated -> show untextured blocks
T+300ms:   Textures loaded from cache -> show textured blocks
T+500ms:   Lighting computed -> show final quality
T+1000ms:  Ghost data loaded -> ghost cars appear
```

For maps visited previously, IndexedDB cache hits make steps 2-5 near-instant (~50ms total).

---

## 9. Pre-processing Pipeline

### 9.1 Build-Time vs Runtime Processing

| Operation | Where | Why |
|-----------|-------|-----|
| Block mesh generation | **Build time** | Meshes are static; ship as pre-built assets |
| Texture atlas creation | **Build time** | Atlas layout is deterministic |
| Basis Universal texture compression | **Build time** | CPU-intensive compression |
| Block name -> mesh mapping table | **Build time** | Static lookup table |
| Material parameter database | **Build time** | Parse NadeoImporterMaterialLib.txt once |
| GBX map parsing | **Runtime** | Maps are user-selected, cannot pre-parse all |
| LZO decompression | **Runtime** | Part of map parsing |
| Ghost sample decoding | **Runtime** | Replays loaded on demand |
| Scene graph construction | **Runtime** | Depends on parsed map data |
| Lightmap computation | **Server-side** (optional) | Too slow for browser; can pre-compute for popular maps |

### 9.2 Server-Side Pre-Processing Service

For popular maps (top 1000 from TMX/Nadeo), a server-side pipeline can pre-process:

```
Input: .Map.Gbx file
  1. Parse GBX -> extract block/item placement
  2. Generate scene description (JSON)
  3. Pre-compute lightmaps (if not pre-baked)
  4. Pre-generate optimized mesh batches
  5. Package as .opentm scene bundle

Output: .opentm bundle
  - scene.json: Block positions, item positions, metadata
  - meshes.glb: Batched geometry in glTF binary
  - lightmap.ktx2: Pre-computed lightmap atlas
  - thumbnail.jpg: Map preview
```

The `.opentm` bundle format would be CDN-hosted and fetched instead of the raw .Map.Gbx when available. This bypasses all runtime parsing.

### 9.3 Content Delivery Strategy

```
CDN Structure:
  /assets/
    /blocks/v{version}/
      block-library.glb         -- All block meshes in one glTF file (~5-10 MB)
      block-manifest.json       -- Block name -> mesh index mapping
    /textures/v{version}/
      road-atlas.ktx2           -- Road texture atlas
      platform-atlas.ktx2       -- Platform texture atlas
      deco-atlas.ktx2           -- Decoration texture atlas
      structure-atlas.ktx2      -- Structure texture atlas
    /materials/v{version}/
      materials.json            -- Material definitions
  /maps/
    /{mapUid}/
      scene.opentm              -- Pre-processed scene (if available)
      map.gbx                   -- Raw GBX file (fallback)
  /ghosts/
    /{ghostId}.ghost            -- Pre-decoded ghost samples
```

CDN headers:
- `Cache-Control: public, max-age=31536000, immutable` for versioned assets
- `Cache-Control: public, max-age=3600, stale-while-revalidate=86400` for map files

### 9.4 Streaming Strategy

For large maps with many embedded items, stream the scene:

1. **Immediate**: Load block placements (tiny, <10 KB parsed)
2. **Priority 1**: Load road block meshes (most visually important)
3. **Priority 2**: Load platform and structure meshes
4. **Priority 3**: Load decoration meshes (grass, hills)
5. **Priority 4**: Load item meshes (embedded custom items)
6. **Priority 5**: Load high-resolution textures (replace placeholder)
7. **Background**: Compute lightmaps, load ghost data

Each priority level renders progressively. The player can start driving as soon as road meshes are loaded (priority 1).

---

## 10. Dependency on Community Tools

### 10.1 What We CANNOT Build Ourselves

| Capability | Why We Need External Help | Source |
|-----------|---------------------------|--------|
| **GBX format knowledge** | 10+ years of community RE, 400+ class parsers | GBX.NET, Mania Tech Wiki, pygbx |
| **Block mesh geometry** | Locked in encrypted .pak files | Must create ourselves (procedural or community art) |
| **Game textures** | Locked in encrypted .pak files | Must create ourselves (procedural or CC0 sources) |
| **Material parameter values** | Only NadeoImporterMaterialLib.txt is available (surface IDs, UV layers); actual shader parameter values (roughness, metalness, emission) are in pack files | Approximate from visual reference |
| **Lightmap baking algorithm** | Nadeo's proprietary radiosity implementation | Approximate with standard GI solutions |
| **Physics coefficient tables** | Exact grip/friction/drag values per surface type | Community has empirical data; TMInterface provides TMNF values |

### 10.2 What We CAN Build Ourselves

| Capability | Approach | Effort |
|-----------|----------|--------|
| **GBX parser (TypeScript)** | Port from spec (doc 16) + GBX.NET reference | 4-6 weeks |
| **Map body chunk parsers** | Implement from spec, validate against real files | 2-3 weeks |
| **Ghost sample decoder** | Spec is well-documented (doc 30 section 7) | 1 week |
| **LZO decompression** | Port minilzo to WASM or use existing npm package | 1-2 days |
| **Procedural block geometry** | Derive from block name patterns and grid system | 3-4 weeks |
| **Material system** | Parse NadeoImporterMaterialLib.txt, map to PBR shaders | 2 weeks |
| **Scene graph renderer** | Standard WebGPU/Three.js rendering pipeline | 4-6 weeks |
| **IndexedDB caching** | Standard browser API usage | 1 week |

### 10.3 Critical Community Resources

**GBX.NET** (https://github.com/BigBang1112/gbx-net)
- **What we use it for**: Reference implementation for chunk parsers, class ID registry, data type encoding
- **Risk if unavailable**: We have our own Ghidra-based spec (doc 16) as backup, but GBX.NET provides tested, working code for 400+ chunk types
- **Mitigation**: Our parser is TypeScript, independent of GBX.NET's C# code; we reference their logic but don't depend on their runtime

**gbx-ts** (https://github.com/thaumictom/gbx-ts)
- **What we use it for**: TypeScript GBX parser reference, potentially fork/adapt
- **Risk**: Smaller project, less maintained than GBX.NET
- **Mitigation**: Write our own parser from spec, use gbx-ts only as validation reference

**Mania Tech Wiki** (https://wiki.xaseco.org/wiki/GBX)
- **What we use it for**: Class ID tables, chunk ID reference, format documentation
- **Risk**: Wiki content could go offline
- **Mitigation**: We have comprehensive local documentation (doc 16, 26, 28, 29, 30)

**Community Block Meshes** (to be created)
- **What we use it for**: Post-MVP visual quality improvement
- **Risk**: Community may not produce enough assets
- **Mitigation**: Procedural generation provides the baseline; community meshes are additive improvements

### 10.4 Honest Feasibility Summary

| Component | Feasibility | Confidence | Biggest Risk |
|-----------|------------|------------|--------------|
| GBX parser | **High** | 95% | Undocumented chunk versions in newer maps |
| Map loading (structure) | **High** | 90% | Complex version branching in block chunks |
| Ghost playback | **High** | 90% | zlib inner compression adds complexity |
| Block mesh rendering | **Medium** | 60% | Procedural geometry may look too different from TM2020 |
| Material system | **Medium** | 70% | Actual shader parameters are unknown; must approximate |
| Texture quality | **Low-Medium** | 50% | Without game textures, visual fidelity is limited |
| Full visual parity | **Low** | 20% | Would require encrypted asset extraction or years of community art |
| Physics accuracy | **Out of scope** | -- | Separate effort; not part of asset pipeline |

The asset pipeline can produce a **functional, recognizable recreation** of TM2020 maps. It will NOT achieve visual parity with the actual game without either extracting game assets (legally risky) or a massive community art effort (years of work). The phased approach -- procedural MVP, then community improvement -- is the realistic path forward.

# Map Structure Encyclopedia

This reference covers everything inside a Trackmania 2020 map: blocks, items, waypoints, decorations, coordinates, materials, and how they connect. Use it when building a map loader, editor, or renderer.

---

## Map Coordinate System

### World Space

Trackmania 2020 uses a **left-handed coordinate system** (left-handed means the cross product of +X and +Y points in +Z) consistent with Direct3D 11:

| Axis | Direction | Role |
|------|-----------|------|
| X | Right | Horizontal |
| Y | Up | Vertical (elevation) |
| Z | Forward | Depth |

**Evidence**: Orbital camera code rotates around Y for horizontal angle and uses `vec3(0, 0, -1)` for vertical rotation axis. The projection matrix follows D3D conventions where `projected.w > 0` means the point is behind the camera.

### The 32-Meter Block Grid

The map world sits on a discrete 3D grid. Each cell is **32 meters** on X and Z:

```
Grid unit (X, Z) = 32 meters
Grid unit (Y)    = 8 meters (height sub-unit)
Block height     = 1 grid Y unit = 8 meters
                   (some blocks span multiple Y units)
```

**Evidence**: Openplanet Finetuner plugin uses `Math::Ceil(distance / 32.0f)` to convert world meters to block units.

### Block Coordinates vs World Position

Blocks are placed at integer grid coordinates `(x, y, z)` stored as `Nat3` (three uint32 values):

```
world_x = block_x * 32.0
world_y = block_y * 8.0
world_z = block_z * 32.0
```

Items (anchored objects) use free-floating `Vec3` world coordinates with no grid snapping. Their positions are three IEEE 754 floats in meters.

### Map Origin and Size

Standard Stadium maps use a **48x48** block grid on X/Z:

```
MapSizeX: 48
MapSizeY: 255    (maximum possible height levels)
MapSizeZ: 48
```

World span:
- X: 0 to 1536 meters (48 * 32)
- Y: 0 to 2040 meters (255 * 8)
- Z: 0 to 1536 meters (48 * 32)

Default terrain (grass) sits at approximately Y=9 in grid units (72 meters world space).

### Speed and Unit Conversions

| Conversion | Factor |
|-----------|--------|
| 1 block unit (X/Z) | 32 meters |
| 1 block unit (Y) | 8 meters |
| 1 m/s to km/h | multiply by 3.6 |
| Vehicle `FrontSpeed` | meters per second |

---

## Block Types and Categories

### Block Class Hierarchy

Every placed block is a `CGameCtnBlock` instance. Block definitions (templates) are `CGameCtnBlockInfo` subclasses:

```
CGameCtnBlockInfo                        -- Base block definition
  +-- CGameCtnBlockInfoClassic           -- Standard grid-snapped block
  +-- CGameCtnBlockInfoClip              -- Clip connection block
  |     +-- CGameCtnBlockInfoClipHorizontal  -- Horizontal clip
  |     +-- CGameCtnBlockInfoClipVertical    -- Vertical clip
  +-- CGameCtnBlockInfoFlat              -- Flat terrain block
  +-- CGameCtnBlockInfoFrontier          -- Zone boundary block
  +-- CGameCtnBlockInfoMobil             -- Moving/animated block
  +-- CGameCtnBlockInfoMobilLink         -- Mobile block link
  +-- CGameCtnBlockInfoPylon             -- Auto-generated support pillar
  +-- CGameCtnBlockInfoRectAsym          -- Rectangular asymmetric block
  +-- CGameCtnBlockInfoRoad              -- Road block
  +-- CGameCtnBlockInfoSlope             -- Sloped surface block
  +-- CGameCtnBlockInfoTransition        -- Terrain transition block
```

Each block type has **two variant classes** for elevation context:

```
CGameCtnBlockInfoVariant                 -- Base variant
  +-- CGameCtnBlockInfoVariantGround     -- Placed at ground level (no supports needed)
  +-- CGameCtnBlockInfoVariantAir        -- Placed elevated (auto-generates pylons)
```

### Block Categories

**Road Blocks** -- Named `Stadium{Road|RoadMain}{Shape}{Variant}`: Straight, Curve, Turn, Slope, SlopeBase, SlopeEnd, Tilt, Cross, Chicane, DiagLeft, DiagRight. Width variants: `x2`, `x3`, `x4`. Mirror variants: `Mirror` suffix.

**Platform Blocks** -- Named `StadiumPlatform{Shape}{Variant}`. Same shapes as roads but without road markings.

**Decoration Blocks** -- `StadiumDecoWall*`, `StadiumDecoHill*`, `StadiumGrass*`, `StadiumWater*`.

**Waypoint Blocks** -- `StadiumGate*` for Start, Finish, Checkpoint gates. Identified by `|BlockInfo|Start`, `|BlockInfo|Finish`, `|BlockInfo|Checkpoint`, `|BlockInfo|Start/Finish` string tags.

**Support Structures** -- `StadiumPillar*`, `StadiumPylon*`. Created automatically when air-variant blocks are placed.

**Custom Blocks** -- User-created, referenced by file path: `Z_Backdrop\GrassRemover.Block.Gbx_CustomBlock`.

### Grid Blocks vs Free Blocks

| Mode | Storage | Coordinates | Snapping |
|------|---------|-------------|----------|
| Grid block | `CGameCtnBlock` with integer coords | Nat3 (x, y, z) | 32m grid |
| Free block | `CGameCtnBlock` with `flags == 0xFFFFFFFF` | Vec3 (float x, y, z) + rotation | No grid |
| Ghost block | Grid block with ghost flag | Nat3 (x, y, z) | 32m grid, overlapping allowed |
| Macroblock | Template group of blocks | Template-relative positions | 32m grid |

A block with `flags == 0xFFFFFFFF` is a **free block** and uses additional fields for arbitrary position and rotation.

### Block Data Format (Binary)

Within body chunk `0x03043011`, each block is serialized as:

```
Offset  Size    Type                Field
------  ----    ----                -----
+0x00   4       LookbackString/Id   block_name       Block model name
+0x04   1       byte                direction        0=North(+Z), 1=East(+X), 2=South(-Z), 3=West(-X)
+0x05   12      Nat3 (3x uint32)    coord            Grid coordinates (x, y, z)
+0x11   4       uint32              flags            Placement flags
                                                     Bit 15: is_ground
                                                     0xFFFFFFFF: free block (additional data follows)
```

### Block Rotation

Grid blocks support 4 cardinal orientations:

| Direction Value | Facing | Angle |
|----------------|--------|-------|
| 0 (North) | +Z | 0 degrees |
| 1 (East) | +X | 90 degrees |
| 2 (South) | -Z | 180 degrees |
| 3 (West) | -X | 270 degrees |

Free blocks and items use full quaternion rotation.

---

## The Waypoint System

Waypoints define the race route. They are stored as properties on blocks and anchored objects via `CGameWaypointSpecialProperty` and `CAnchorData.EWaypointType`.

| Waypoint Type | Purpose | Count in Valid Map |
|---------------|---------|-------------------|
| **Start** | Race spawn position | Exactly 1 (point-to-point maps) |
| **Finish** | Race end line | Exactly 1 (point-to-point maps) |
| **Checkpoint** | Intermediate timing gate | 0 or more |
| **StartFinish** | Combined start/finish for multilap | Exactly 1 (multilap maps only) |

### Waypoint Connectivity

Route validation determines whether a car can drive from Start to Finish through all Checkpoints. The system uses clip connections (block-to-block), checkpoint ordering verification via `CGameEditorPluginMapConnectResults`, and trigger volumes (`CSceneTriggerAction`, `CGameTriggerGate`) placed at gate positions.

### The Clip System (Block Connectivity)

Blocks connect via **clips** (typed connection points on block faces):

```
CGameCtnBlockInfoClip                    -- Base clip connection type
  +-- CGameCtnBlockInfoClipHorizontal    -- Connects blocks side-by-side (X/Z plane)
  +-- CGameCtnBlockInfoClipVertical      -- Connects blocks vertically (Y-axis stacking)
```

Each block face has zero or more clip points. Clips have a **type** -- only matching types connect. The editor validates adjacent blocks have compatible clips on shared faces. Invalid connections produce the "red placement" indicator.

The map loading pipeline has 5 dedicated stages for clip initialization (stages 11-14 and 21).

---

## Item Placement System

### Items vs Blocks

| Aspect | Blocks | Items |
|--------|--------|-------|
| Placement | Grid-snapped (32m) or free | Always free (arbitrary position) |
| Class | `CGameCtnBlock` | `CGameCtnAnchoredObject` |
| Definition | `CGameCtnBlockInfo` subclass | `CGameItemModel` |
| Rotation | 4 cardinal directions (grid) or quaternion (free) | Euler angles or quaternion |
| Connectivity | Clip system | None (items do not connect) |
| Source | Built-in game content | Built-in OR user-created `.Item.Gbx` |

### Item Placement Binary Format

Items are stored in body chunk `0x03043040` as `CGameCtnAnchoredObject` instances:

```
Offset  Size    Type                Field
------  ----    ----                -----
+0x00   4       LookbackString/Id   item_model       Item model reference name
+0x04   4       uint32              [version/flags]
+0x08   12      Vec3 (3x float)     position         World-space position (x, y, z) in meters
+0x14   16      Quat (4x float)     rotation         Orientation quaternion (x, y, z, w)
+0x24   ...     ...                 [additional version-dependent fields]
```

### Item Coordinates

From real map-export.json data:

```json
{
  "Name": "PillarWorld/Pillar_Color6.Item.Gbx",
  "Position": { "X": -116.60, "Y": 273.88, "Z": -171.23 },
  "Rotation": { "X": -1.5707963, "Y": 0.0, "Z": 0.0 },
  "Pivot": { "X": 0, "Y": 0, "Z": 0 },
  "AnimPhaseOffset": "None",
  "DifficultyColor": "Default",
  "LightmapQuality": "Normal"
}
```

Positions are in world meters and can be negative (items extend beyond the standard grid). Rotation uses Euler angles (radians) with X=pitch, Y=yaw, Z=roll.

### Embedded vs Referenced Items

1. **Built-in**: Referenced by well-known name resolved against game asset packs.
2. **Embedded**: Custom `.Item.Gbx` data stored inside the map file (body chunk `0x03043054`). Increases file size but makes the map self-contained.
3. **Referenced externally**: Items from the user's `Items/` folder, referenced by relative path.

### Item Model Pipeline

```
CGameCtnAnchoredObject              -- Instance on map (position + rotation)
  -> CGameItemModel                 -- Item definition
       -> CPlugStaticObjectModel    -- Static 3D geometry + collision
            -> CPlugSolid2Model     -- Modern mesh (vertices, indices, materials, LODs)
       -> CGameWaypointSpecialProperty  -- If item is a waypoint
```

---

## Map Environments and Decorations

### The Decoration System

Every map references a **decoration** that defines its visual theme, skybox, lighting mood, and grid size. The decoration loads in stage 1 of the map pipeline.

```
CGameCtnDecoration                       -- Base decoration definition
CGameCtnDecorationSize                   -- Grid dimensions (SizeX, SizeY, SizeZ)
CGameCtnDecorationMood                   -- Time-of-day / lighting mood
CGameCtnDecorationMaterialModifiers      -- Material appearance adjustments
```

### Decoration Names

Decoration name format: `{StructureType}{GridSize}{Mood}`

| Map | Decoration String | Meaning |
|-----|-------------------|---------|
| CraterWorld | `NoStadium48x48Day` | No skybox, 48x48 grid, daytime |
| Kacky394 | `48x48Screen155Sunrise` | Screen arena, 48x48, sunrise |
| TechFlow | `NoStadium48x48Day` | No skybox, 48x48, daytime |
| Mac1 | `48x48Screen155Day` | Screen arena, 48x48, daytime |

**Structure types**: `NoStadium` (void/clean background), `48x48Screen155` (LED wall arena).

**Moods**: `Day`, `Sunrise`, `Night`, `Sunset`.

### Environment Theme Packs (.pak Files)

| Pack File | Size | Visual Theme |
|-----------|------|-------------|
| **Stadium.pak** | 1.63 GB | Main stadium -- all block models, textures, materials |
| **GreenCoast.pak** | 569 MB | Lush green coastal theme |
| **BlueBay.pak** | 530 MB | Blue bay/ocean theme |
| **RedIsland.pak** | 776 MB | Red desert/volcanic island theme |
| **WhiteShore.pak** | 411 MB | White/snowy shore theme |

Theme packs provide alternative 3D models, textures, and skybox assets. The same block names work across all themes -- only the visual appearance changes.

### Vehicle Models

| Path | Vehicle | Default For |
|------|---------|-------------|
| `\Vehicles\Items\CarSport.Item.gbx` | Stadium/Sport car | Stadium |
| `\Vehicles\Items\CarSnow.Item.gbx` | Snow car | Snow surfaces |
| `\Vehicles\Items\CarRally.Item.gbx` | Rally car | Rally surfaces |
| `\Vehicles\Items\CarDesert.Item.gbx` | Desert car | Desert surfaces |

Vehicle type is stored in body chunk `0x0304300D`.

---

## Map Loading Pipeline

Loading a .Map.Gbx into a playable map follows a **22-stage pipeline**. Each stage has a dedicated profiling marker.

### Phase 1: GBX Deserialization

```
1. Read GBX header (magic "GBX", version 6, format flags "BUCR")
2. Parse header chunk table (map info, thumbnail, author data)
3. Read node count
4. Parse reference table (external file dependencies)
5. Decompress body (LZO decompression of compressed body data)
6. Parse body chunk stream (dispatch to CGameCtnChallenge chunk handlers)
7. Read 0xFACADE01 end sentinel
```

### Phase 2: Map Initialization (22 Stages)

| Stage | Method | Purpose | Speed |
|-------|--------|---------|-------|
| 1 | `LoadDecorationAndCollection` | Load decoration theme + block collection | SLOW |
| 2 | `InternalLoadDecorationAndCollection` | Internal decoration setup | Moderate |
| 3 | `UpdateBakedBlockList` | Sync baked block data | Fast |
| 4 | `AutoSetIdsForLightMap` | Assign lightmap UV set IDs | Fast |
| 5 | `LoadAndInstanciateBlocks` | Create block objects from serialized data | SLOW |
| 6 | `InitChallengeData_ClassicBlocks` | Initialize standard road/platform blocks | Moderate |
| 7 | `InitChallengeData_Terrain` | Initialize terrain heightmap | Moderate |
| 8 | `InitChallengeData_DefaultTerrainBaked` | Set up default terrain | Fast |
| 9 | `InitChallengeData_Genealogy` | Build block parent-child relationships | Fast |
| 10 | `InitChallengeData_PylonsBaked` | Load pre-baked pylon structures | Fast |
| 11 | `InitChallengeData_ClassicClipsBaked` | Grid block clip connections | Fast |
| 12 | `InitChallengeData_FreeClipsBaked` | Free block clip connections | Fast |
| 13 | `InitChallengeData_Clips` | All clip connections | Moderate |
| 14 | `CreateFreeClips` | Create free-block clip objects | Moderate |
| 15 | `InitPylonsList` | Build pylon/support list | Fast |
| 16 | `CreatePlayFields` | Create playable field areas | Fast |
| 17 | `TransferIdForLightMapFromBakedBlocksToBlocks` | Copy lightmap IDs | Fast |
| 18 | `InitEmbeddedItemModels` | Load embedded custom item data | SLOW |
| 19 | `LoadEmbededItems` | Instantiate embedded items | Moderate |
| 20 | `InitAllAnchoredObjects` | Initialize all placed items | Moderate |
| 21 | `ConnectAdditionalDataClipsToBakedClips` | Final clip wiring | Fast |
| 22 | `RemoveNonBlocksFromBlockStock` | Clean up non-block entries | Fast |

### Bottleneck Summary

| Operation | Cost | Why |
|-----------|------|-----|
| LZO decompression | Fast | Simple algorithm, small data |
| Block instantiation | Moderate | Proportional to block count |
| Decoration/pack loading | SLOW | Megabytes of 3D assets |
| Embedded item parsing | SLOW | Each embedded item is a full GBX sub-file |
| Lightmap generation | VERY SLOW | Full radiosity if not pre-baked |

---

## Map Metadata

### Header Chunk Data

| Chunk ID | Content |
|----------|---------|
| `0x03043002` | Map UID, environment name, map author login |
| `0x03043003` | Map name, mood, decoration name, map type, author display name |
| `0x03043004` | Version info |
| `0x03043005` | XML community reference string |
| `0x03043007` | Thumbnail (JPEG) + comments |
| `0x03043008` | Author zone path, author extra info |

### The XML Header (Chunk 0x03043005)

```xml
<header type="map" exever="3.3.0" exebuild="2026-02-02_17_51"
        title="TMStadium" lightmap="0">
  <ident uid="KS3aPHG7ywx7o2co6JLWHJKDjwl"
         name="TechFlow"
         author="XChwDu8FRmWH-gHqXUbBtg"/>
  <desc envir="TMStadium" .../>
  <times .../>
</header>
```

### Medal Times

Stored in body chunk `0x0304304B` as uint32 milliseconds. A value of `0xFFFFFFFF` means "not set."

| Medal | Color |
|-------|-------|
| Author | Blue/Developer |
| Gold | Gold |
| Silver | Silver |
| Bronze | Bronze |

---

## Map Validation Rules

### Route Validation

For a valid racing map:
1. Exactly one Start waypoint (or one StartFinish for multilap)
2. Exactly one Finish waypoint (or StartFinish serves as both)
3. A drivable path from Start to Finish through all Checkpoints
4. Author time set (validation drive completed)
5. All checkpoints reachable during the validation drive

### Ghost Block Rules

Ghost blocks occupy the grid but do **not** contribute to collision or route validation. They serve as visual decoration that can overlap other blocks.

---

## Block Naming Convention

TM2020 Stadium block names follow: `{Environment}{Category}{Shape}{Variant}{Modifier}`

### Category Tokens

| Token | Description |
|-------|-------------|
| `Road` / `RoadMain` | Drivable road surface |
| `Platform` | Flat platform surface |
| `DecoWall` / `DecoHill` | Decorative wall/hill |
| `Gate` | Start/Finish/Checkpoint gate |
| `Water` | Water element |
| `Grass` | Grass terrain |

### Shape Tokens

| Token | Geometry |
|-------|----------|
| `Straight` | Straight segment |
| `Curve` / `Turn` | Curved segment |
| `Slope` / `Tilt` | Inclined surface |
| `Cross` | Intersection |
| `DiagLeft` / `DiagRight` | Diagonal pieces |
| `Chicane` | S-curve |

### Examples

```
StadiumRoadMainStraight           -- Basic straight road
StadiumRoadMainCurvex2            -- Double-width curve
StadiumPlatformSlopeMirror        -- Mirrored platform slope
StadiumDecoWallStraight           -- Decorative wall, straight
```

---

## Surface and Material System

### Gameplay Effects Are NOT Material-Driven

All 208 stock materials have `DGameplayId(None)`. Gameplay effects (turbo, reactor boost, no-grip, slow motion) come from **block/item types and trigger zones**, not materials.

Materials control:
- **Surface physics** (friction, tire sound) via `DSurfaceId`
- **Texture mapping** (UV layers: BaseMaterial + Lightmap)
- **Visual appearance** (vertex color via `DColor0`)

### Surface ID Table (19 unique types)

| Surface ID | Physics Behavior | Friction | Example Materials |
|-----------|-----------------|----------|-------------------|
| `Asphalt` | High-grip road | High | RoadTech, PlatformTech |
| `Concrete` | Structural surface | Medium-High | Waterground, ItemPillarConcrete |
| `Dirt` | Off-road | Medium | RoadDirt |
| `Grass` | Natural ground | Low | Grass, DecoHill |
| `Ice` | Ice surface | Very Low | PlatformIce |
| `Metal` | Metallic | Medium | Technics, Structure, Pylon |
| `NotCollidable` | No collision | N/A | Chrono digits, GlassWaterWall |
| `Plastic` | Bouncy | Medium | ItemInflatable*, ItemObstacle |
| `Rubber` | Bouncy rubber | Medium-High | TrackBorders |
| `Sand` | Sandy | Low | Various deco |
| `Snow` | Snow | Low | Various deco |
| `Wood` | Wooden | Medium | TrackWall |

### UV Layer Requirements

| Material Type | UV0 | UV1 | Notes |
|---------------|-----|-----|-------|
| Standard (roads, platforms) | BaseMaterial | Lightmap | Both required |
| Grass | Lightmap | -- | Lightmap on channel 0 (unusual) |
| Dynamic items | BaseMaterial | -- | No lightmap |
| Custom* materials | Lightmap | -- | Engine-provided textures |

Every drivable surface mesh MUST have a Lightmap UV layer. Without it, NadeoImporter aborts with `"Mesh has no LM UVs => abort"`.

---

## GBX Map File Binary Layout

### File Structure

```
+=========================================+
| HEADER                                  |
|   "GBX" (3 bytes)                       |
|   Version: 6 (uint16)                   |
|   Format: "BUCR" (4 bytes)              |
|   Class ID: 0x03043000 (uint32)         |
|   User data size (uint32)               |
|   Header chunk count (uint32)           |
|   Header chunk index (chunk_id + size)  |
|   Header chunk data (concatenated)      |
+=========================================+
| NODE COUNT (uint32)                     |
+=========================================+
| REFERENCE TABLE                         |
+=========================================+
| BODY (compressed)                       |
|   Uncompressed size (uint32)            |
|   Compressed size (uint32)              |
|   LZO-compressed body chunk stream      |
+=========================================+
```

### Body Chunks

| Chunk ID | Skippable | Content |
|----------|-----------|---------|
| `0x0304300D` | Yes | Vehicle/player model reference |
| `0x03043011` | No | Block data array (primary block storage) |
| `0x0304301F` | Yes | Block parameters + additional data |
| `0x03043040` | Yes | Anchored object (item) placement |
| `0x03043042` | Yes | Author data (newer format) |
| `0x03043044` | Yes | Script metadata |
| `0x03043048` | Yes | Baked blocks |
| `0x0304304B` | Yes | Objectives / medal times |
| `0x03043054` | Yes | Embedded items |
| `0xFACADE01` | -- | End sentinel |

### LookbackString System

Block and item names use string interning:

```
First Id read:    uint32 = 3 (version marker)
Subsequent reads: uint32 flags_and_index
  Bits 31-30 = 0b11: New string follows (read and add to table)
  Bits 31-30 = 0b10: Reference at index (bits 29-0)
  Bits 31-30 = 0b01: Well-known string:
    0x40000001 = "Unassigned"
    0x40000003 = "Stadium"
    0x40000004 = "Valley"
    0x40000005 = "Canyon"
    0x40000006 = "Lagoon"
```

---

## Real File Hex Analysis

### File Header Pattern

Every .Map.Gbx starts with:
```
0x0000  47 42 58                        Magic: "GBX"
0x0003  06 00                           Version: 6
0x0005  42 55 43 52                     Format: "BUCR"
0x0009  00 30 04 03                     Class ID: 0x03043000
```

### Comparing Multiple Maps

| Field | CraterWorld | Kacky394 | TechFlow | PillarWorld |
|-------|-------------|----------|----------|-------------|
| Version | 6 | 6 | 6 | 6 |
| Format | BUCR | BUCR | BUCR | BUCR |
| Class ID | 0x03043000 | 0x03043000 | 0x03043000 | 0x03043000 |
| Header chunks | 6 | 6 | 6 | 6 |
| Decoration | NoStadium48x48Day | 48x48Screen155Sunrise | NoStadium48x48Day | NoStadium48x48Day |

All maps share version 6, BUCR format, 6 header chunks, same class ID, and same map type (`TrackMania\TM_Race`).

---

## Class Reference

### Map Structure Classes

`CGameCtnChallenge` is the root map class (class ID `0x03043000`). Known methods:
```
AutoSetIdsForLightMap, ConnectAdditionalDataClipsToBakedClips, CreateFreeClips,
CreatePlayFields, InitAllAnchoredObjects, InitChallengeData_ClassicBlocks,
InitChallengeData_Clips, InitChallengeData_Terrain, InitEmbeddedItemModels,
LoadAndInstanciateBlocks, LoadDecorationAndCollection, LoadEmbededItems,
RemoveNonBlocksFromBlockStock, UpdateBakedBlockList
```

### Key Class ID Quick Reference

| Class ID | Class | File Extension |
|----------|-------|---------------|
| `0x03043000` | CGameCtnChallenge | `.Map.Gbx` |
| `0x03093000` | CGameCtnReplayRecord | `.Replay.Gbx` |
| `0x09011000` | CPlugBitmap | `Texture.Gbx` |
| `0x09026000` | CPlugShaderApply | `Material.Gbx` |
| `0x090BB000` | CPlugSolid2Model | `.Solid2.gbx` |

Legacy class ID `0x24003000` remaps to `0x03043000` for backward compatibility.

---

## Quick Reference for Map Loader Implementors

### Minimum Viable Parser

1. Parse GBX header (magic, version, format flags, class ID)
2. Read header chunks (name, author, UID, thumbnail)
3. Skip or parse the reference table
4. Decompress the body (LZO)
5. Parse body chunks: `0x03043011` (blocks), `0x03043040` (items), `0x0304304B` (medal times), `0x03043054` (embedded items)
6. Handle LookbackString for block/item name resolution
7. Apply class ID remapping for legacy files

### Data Per Block

```
block_name:  string    (e.g., "StadiumRoadMainStraight")
direction:   0-3       (North/East/South/West)
coord_x:     uint32    (grid X position)
coord_y:     uint32    (grid Y position -- multiply by 8 for meters)
coord_z:     uint32    (grid Z position)
flags:       uint32    (bit 15 = is_ground, 0xFFFFFFFF = free block)
```

### Data Per Item

```
item_name:   string    (e.g., "PillarWorld/Pillar_Color6.Item.Gbx")
position:    vec3      (world meters: x, y, z)
rotation:    quat/euler (orientation)
pivot:       vec3      (rotation center offset)
```

### Coordinate Conversion

```
world_position.x = block.coord_x * 32.0
world_position.y = block.coord_y * 8.0
world_position.z = block.coord_z * 32.0
```

The body chunk stream ends with `0xFACADE01`. Stop parsing when you read this as a chunk ID.

---

## Related Pages

- [26-real-file-analysis.md](26-real-file-analysis.md) -- Byte-by-byte hex analysis of real .Map.Gbx files
- [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) -- GBX format specification
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Map loading for browser recreation
- [30-ghost-replay-format.md](30-ghost-replay-format.md) -- Replay files that embed maps
- [29-community-knowledge.md](29-community-knowledge.md) -- Community GBX parsing tools

<details><summary>Analysis metadata</summary>

- **Purpose**: Comprehensive reference for the internal structure of Trackmania 2020 maps
- **Sources**: Ghidra decompilation of Trackmania.exe, Openplanet plugin analysis, NadeoImporterMaterialLib.txt, class_hierarchy.json RTTI extraction, hex analysis of real .Map.Gbx files
- **Date**: 2026-03-27

</details>

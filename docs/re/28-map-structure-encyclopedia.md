# Map Structure Encyclopedia

**Purpose**: Comprehensive reference for the internal structure of Trackmania 2020 maps -- blocks, items, waypoints, decorations, and how they all connect. Written for someone building a map loader or editor.

**Sources**: Ghidra decompilation of Trackmania.exe, Openplanet plugin analysis, NadeoImporterMaterialLib.txt, class_hierarchy.json RTTI extraction, hex analysis of real .Map.Gbx files.

**Date**: 2026-03-27

---

## Table of Contents

1. [Map Coordinate System](#1-map-coordinate-system)
2. [Block Types and Categories](#2-block-types-and-categories)
3. [The Waypoint System](#3-the-waypoint-system)
4. [Item Placement System](#4-item-placement-system)
5. [Map Environments and Decorations](#5-map-environments-and-decorations)
6. [Map Loading Pipeline](#6-map-loading-pipeline)
7. [Map Metadata](#7-map-metadata)
8. [Map Validation Rules](#8-map-validation-rules)
9. [Block Naming Convention](#9-block-naming-convention)
10. [Surface and Material System](#10-surface-and-material-system)
11. [GBX Map File Binary Layout](#11-gbx-map-file-binary-layout)
12. [Real File Hex Analysis](#12-real-file-hex-analysis)
13. [Class Reference](#13-class-reference)

---

## 1. Map Coordinate System

### 1.1 World Space

Trackmania 2020 uses a **left-handed coordinate system** consistent with Direct3D 11:

| Axis | Direction | Role |
|------|-----------|------|
| X | Right | Horizontal |
| Y | Up | Vertical (elevation) |
| Z | Forward | Depth |

**Evidence**: Orbital camera code rotates around Y for horizontal angle, uses `vec3(0, 0, -1)` for vertical rotation axis. The projection matrix follows D3D conventions where `projected.w > 0` means the point is behind the camera.

### 1.2 The 32-Meter Block Grid

The map world is organized on a discrete 3D grid. Each grid cell is **32 meters** on the X and Z axes:

```
Grid unit (X, Z) = 32 meters
Grid unit (Y)    = 8 meters (height sub-unit)
Block height     = 1 grid Y unit = 8 meters
                   (some blocks span multiple Y units)
```

**Evidence**: Openplanet Finetuner plugin uses `Math::Ceil(distance / 32.0f)` to convert world meters to block units for render distance calculations.

### 1.3 Block Coordinates vs World Position

Blocks are placed at integer grid coordinates `(x, y, z)` stored as `Nat3` (three uint32 values). The mapping to world position:

```
world_x = block_x * 32.0
world_y = block_y * 8.0
world_z = block_z * 32.0
```

Items (anchored objects) use free-floating `Vec3` world coordinates with no grid snapping. Their positions are stored as three IEEE 754 floats representing meters directly.

### 1.4 Map Origin and Size

Maps have a fixed grid size defined by the decoration. The standard Stadium decoration is **48x48** blocks on X/Z. From real map-export.json data:

```
MapSizeX: 48
MapSizeY: 255    (maximum possible height levels)
MapSizeZ: 48
```

This means the standard Stadium map world spans:
- X: 0 to 1536 meters (48 * 32)
- Y: 0 to 2040 meters (255 * 8)
- Z: 0 to 1536 meters (48 * 32)

The default terrain (grass) sits at approximately Y=9 in grid units (72 meters world space), confirmed by real map data showing grass-remover blocks placed at `Y: 9`.

### 1.5 Speed and Unit Conversions

| Conversion | Factor |
|-----------|--------|
| 1 block unit (X/Z) | 32 meters |
| 1 block unit (Y) | 8 meters |
| 1 m/s to km/h | multiply by 3.6 |
| Vehicle `FrontSpeed` | meters per second |

---

## 2. Block Types and Categories

### 2.1 The Block Class Hierarchy

Every block placed on the map is an instance of `CGameCtnBlock`. Block *definitions* (templates) are `CGameCtnBlockInfo` subclasses. The complete hierarchy from RTTI:

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

### 2.2 Block Categories

Based on block naming patterns extracted from game files and map exports:

#### Road Blocks
Drivable road surfaces. Named `Stadium{Road|RoadMain}{Shape}{Variant}`:
- **Straight**: `StadiumRoadMainStraight`
- **Curve/Turn**: `StadiumRoadMainCurve`, `StadiumRoadMainTurn`
- **Slope**: `StadiumRoadMainSlope`, `StadiumRoadMainSlopeBase`, `StadiumRoadMainSlopeEnd`
- **Tilt**: `StadiumRoadMainTilt`
- **Cross**: `StadiumRoadMainCross` (intersection)
- **Chicane**: `StadiumRoadMainChicane` (S-curve)
- **Diagonal**: `StadiumRoadMainDiagLeft`, `StadiumRoadMainDiagRight`
- Width variants: `x2`, `x3`, `x4` suffixes
- Mirror variants: `Mirror` suffix

#### Platform Blocks
Flat surfaces without built-in road markings. Named `StadiumPlatform{Shape}{Variant}`:
- Same shape vocabulary as road blocks (Straight, Curve, Slope, etc.)
- Used for freestyle/creative building

#### Decoration Blocks
Non-drivable visual elements:
- `StadiumDecoWall*` -- Wall decorations
- `StadiumDecoHill*` -- Hillside decorations
- `StadiumGrass*` -- Grass terrain
- `StadiumWater*` -- Water elements

#### Special/Waypoint Blocks
Blocks with gameplay significance (see Section 3):
- `StadiumGate*` -- Start, Finish, Checkpoint gates
- Identified by `|BlockInfo|Start`, `|BlockInfo|Finish`, `|BlockInfo|Checkpoint`, `|BlockInfo|Start/Finish` string tags

#### Support Structures
- `StadiumPillar*` -- Support pillars
- `StadiumPylon*` -- Auto-generated pylons
- These are typically created automatically by the engine when air-variant blocks are placed

#### Custom Blocks
User-created blocks referenced by file path rather than built-in name:
```
Z_Backdrop\GrassRemover.Block.Gbx_CustomBlock
```
Custom blocks use the `_CustomBlock` suffix in their serialized name and reference a `.Block.Gbx` file.

### 2.3 Grid Blocks vs Free Blocks

There are two fundamental placement modes:

| Mode | Storage | Coordinates | Snapping |
|------|---------|-------------|----------|
| Grid block | `CGameCtnBlock` with integer coords | Nat3 (x, y, z) | 32m grid |
| Free block | `CGameCtnBlock` with `flags == 0xFFFFFFFF` | Vec3 (float x, y, z) + rotation | No grid |
| Ghost block | Grid block with ghost flag | Nat3 (x, y, z) | 32m grid, overlapping allowed |
| Macroblock | Template group of blocks | Template-relative positions | 32m grid |

In the binary format, a block with `flags == 0xFFFFFFFF` is a **free block** and uses additional fields for arbitrary position and rotation instead of grid coordinates.

### 2.4 Block Data Format (Binary)

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

For free blocks (`flags == 0xFFFFFFFF`), additional position/rotation data follows.

### 2.5 Block Rotation

Grid blocks support 4 cardinal orientations:

| Direction Value | Facing | Angle |
|----------------|--------|-------|
| 0 (North) | +Z | 0 degrees |
| 1 (East) | +X | 90 degrees |
| 2 (South) | -Z | 180 degrees |
| 3 (West) | -X | 270 degrees |

Free blocks and items use full quaternion rotation for arbitrary orientation.

---

## 3. The Waypoint System

### 3.1 Waypoint Types

Waypoints define the race route. They are stored as properties on blocks and anchored objects via `CGameWaypointSpecialProperty` and `CAnchorData.EWaypointType`.

| Waypoint Type | Purpose | Count in Valid Map |
|---------------|---------|-------------------|
| **Start** | Race spawn position | Exactly 1 (point-to-point maps) |
| **Finish** | Race end line | Exactly 1 (point-to-point maps) |
| **Checkpoint** | Intermediate timing gate | 0 or more |
| **StartFinish** | Combined start/finish for multilap | Exactly 1 (multilap maps only) |

**Evidence**: Binary strings `|BlockInfo|Checkpoint`, `|BlockInfo|Finish`, `|BlockInfo|Start`, `|BlockInfo|Start/Finish` in Trackmania.exe. The `CBlockModel.EWayPointType` enum and `CAnchorData.EWaypointType` enum both define these four types.

### 3.2 Waypoint Connectivity

Route validation determines whether a car can drive from Start to Finish passing through all Checkpoints. The connectivity system works through:

1. **Clip connections**: Blocks connect via the clip system (see Section 3.4). A valid route requires an unbroken chain of connected road surfaces from start to finish.

2. **Checkpoint ordering**: Checkpoints must be reachable in sequence. The map editor's validation test (`CGameEditorPluginMapConnectResults`) verifies this by simulating the route.

3. **Trigger zones**: Waypoint detection uses trigger volumes (`CSceneTriggerAction`, `CGameTriggerGate`) placed at gate positions. When the car enters the trigger volume, the checkpoint/finish is registered.

### 3.3 Multilap Configuration

For multilap maps:
- A single **StartFinish** waypoint replaces separate Start and Finish gates
- The car crosses the StartFinish line multiple times (typically 3 or 5 laps)
- Lap count is stored in the map parameters (`CGameCtnChallengeParameters`)
- Checkpoints are visited once per lap

### 3.4 The Clip System (Block Connectivity)

Blocks connect to adjacent blocks via **clips** -- typed connection points on block faces:

```
CGameCtnBlockInfoClip                    -- Base clip connection type
  +-- CGameCtnBlockInfoClipHorizontal    -- Connects blocks side-by-side (X/Z plane)
  +-- CGameCtnBlockInfoClipVertical      -- Connects blocks vertically (Y-axis stacking)
```

Supporting classes:
```
CBlockClip          -- Individual clip instance on a placed block
CBlockClipList      -- Collection of clips for a block
```

How clips work:
- Each block face has zero or more clip points
- Clips have a **type** -- only matching types connect
- The editor validates that adjacent blocks have compatible clips on shared faces
- Invalid connections produce the "red placement" indicator in the editor
- Clip validation is performed by `CGameEditorPluginMapConnectResults` / `GetConnectResults`

The map loading pipeline has dedicated stages for clip initialization:
- Stage 11: `InitChallengeData_ClassicClipsBaked` -- grid block clips
- Stage 12: `InitChallengeData_FreeClipsBaked` -- free-placed block clips
- Stage 13: `InitChallengeData_Clips` -- all clip connections
- Stage 14: `CreateFreeClips` -- free block clip objects
- Stage 21: `ConnectAdditionalDataClipsToBakedClips` -- final wiring

---

## 4. Item Placement System

### 4.1 Items vs Blocks

| Aspect | Blocks | Items |
|--------|--------|-------|
| Placement | Grid-snapped (32m) or free | Always free (arbitrary position) |
| Class | `CGameCtnBlock` | `CGameCtnAnchoredObject` |
| Definition | `CGameCtnBlockInfo` subclass | `CGameItemModel` |
| Coordinates | Integer grid OR float world | Float world (Vec3) |
| Rotation | 4 cardinal directions (grid) or quaternion (free) | Euler angles (pitch, yaw, roll) or quaternion |
| Connectivity | Clip system | None (items don't connect to each other) |
| Collision | Built into block model | Defined by item's `CPlugStaticObjectModel` |
| Source | Built-in game content | Built-in OR user-created `.Item.Gbx` files |

### 4.2 Item Placement Binary Format

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

### 4.3 Item Coordinate System

From real map-export.json data showing item placement:

```json
{
  "Name": "PillarWorld/Pillar_Color6.Item.Gbx",
  "Position": {
    "X": -116.60455322265625,
    "Y": 273.8827209472656,
    "Z": -171.2347412109375
  },
  "Rotation": {
    "X": -1.5707963267948966,
    "Y": 0.0,
    "Z": 0.0
  },
  "Pivot": { "X": 0, "Y": 0, "Z": 0 },
  "AnimPhaseOffset": "None",
  "DifficultyColor": "Default",
  "LightmapQuality": "Normal"
}
```

Key observations:
- **Position** is in world meters -- can be negative (items can extend beyond the standard grid)
- **Rotation** is in Euler angles (radians) with X=pitch, Y=yaw, Z=roll
- **Pivot** defines the rotation center offset
- **AnimPhaseOffset** controls animation timing for kinematic items
- **DifficultyColor** and **LightmapQuality** are per-item metadata

### 4.4 Embedded vs Referenced Items

Items can be:

1. **Built-in**: Referenced by a well-known name resolved against the game's asset packs. No embedding needed.

2. **Embedded**: Custom `.Item.Gbx` files whose data is stored *inside* the map file.
   - Body chunk `0x03043054` stores embedded item data
   - Loading stage 18: `InitEmbeddedItemModels` loads the embedded item model data
   - Loading stage 19: `LoadEmbededItems` instantiates the items
   - Loading stage 20: `InitAllAnchoredObjects` initializes all placed item instances

3. **Referenced externally**: Items that live in the user's `Items/` folder, referenced by relative path (e.g., `PillarWorld/Pillar_Color6.Item.Gbx`).

Embedded items increase map file size but ensure the map is self-contained and playable by anyone without requiring them to install custom items separately. There are embed size limits for online play (see Section 8).

### 4.5 Item Model Pipeline

The internal hierarchy for a placed item:

```
CGameCtnAnchoredObject              -- Instance on the map (position + rotation)
  -> CGameItemModel                 -- Item definition
       -> CPlugStaticObjectModel    -- Static 3D geometry + collision
            -> CPlugSolid2Model     -- Modern mesh (vertices, indices, materials, LODs)
       -> CGameWaypointSpecialProperty  -- If item is a waypoint (checkpoint, etc.)
```

Items can also act as waypoints. The editor has a `CbBeforeIsCheckpoint` callback for designating items as checkpoints.

---

## 5. Map Environments and Decorations

### 5.1 The Decoration System

Every map references a **decoration** that defines its visual theme, skybox, lighting mood, and grid size. The decoration is loaded in the very first stage of the map pipeline.

**Evidence**: `CGameCtnChallenge::LoadDecorationAndCollection` is stage 1, and `CGameCtnChallenge::InternalLoadDecorationAndCollection` is stage 2.

The decoration class hierarchy:

```
CGameCtnDecoration                       -- Base decoration definition
CGameCtnDecorationSize                   -- Grid dimensions
  .SizeX (uint)                          -- X extent in blocks
  .SizeY (uint)                          -- Y extent (height levels)
  .SizeZ (uint)                          -- Z extent in blocks
CGameCtnDecorationMood                   -- Time-of-day / lighting mood
CGameCtnDecorationMaterialModifiers      -- Material appearance adjustments
```

### 5.2 Decoration Names in Real Maps

From hex analysis of actual .Map.Gbx headers:

| Map | Decoration String | Meaning |
|-----|-------------------|---------|
| CraterWorld.Map.Gbx | `NoStadium48x48Day` | No skybox structure, 48x48 grid, daytime |
| Kacky394.Map.Gbx | `48x48Screen155Sunrise` | Screen-style arena, 48x48, sunrise mood |
| TechFlow.Map.Gbx | `NoStadium48x48Day` | No skybox, 48x48, daytime |
| Mac1.Map.Gbx | `48x48Screen155Day` | Screen arena, 48x48, daytime |
| PillarWorld.Map.Gbx | `NoStadium48x48Day` | No skybox, 48x48, daytime |

Decoration name format: `{StructureType}{GridSize}{Mood}`

**Structure types** observed:
- `NoStadium` -- No stadium structure visible (void/clean background)
- `48x48Screen155` -- Screen-style arena with visible LED walls

**Grid sizes**: `48x48` is the standard Stadium size.

**Moods** (time of day):
- `Day` -- Standard daytime
- `Sunrise` -- Sunrise lighting
- `Night`, `Sunset` -- Other times (from game file evidence)

### 5.3 Collections and Environment Packs

The `CGameCtnCollection` class represents a block collection -- the set of all available block types for an environment. TM2020 has one primary collection: **Stadium** (title: `TMStadium`).

From the XML header embedded in map files:
```xml
<header type="map" exever="3.3.0" exebuild="2026-02-02_17_51"
        title="TMStadium" lightmap="0">
```

All TM2020 maps use `title="TMStadium"` and the map type `TrackMania\TM_Race`.

### 5.4 Environment Theme Packs (.pak Files)

The game ships with multiple visual theme packs that change the decoration appearance without changing gameplay:

| Pack File | Size | Visual Theme |
|-----------|------|-------------|
| **Stadium.pak** | 1.63 GB | Main stadium environment -- all block models, textures, materials |
| **GreenCoast.pak** | 569 MB | Lush green coastal theme |
| **BlueBay.pak** | 530 MB | Blue bay/ocean theme |
| **RedIsland.pak** | 776 MB | Red desert/volcanic island theme |
| **WhiteShore.pak** | 411 MB | White/snowy shore theme |

Additional supporting packs:

| Pack File | Size | Purpose |
|-----------|------|---------|
| Maniaplanet.pak | 169 MB | Core ManiaPlanet engine assets |
| Maniaplanet_Core.pak | 33.7 MB | Core engine resources |
| Maniaplanet_ModelsSport.pak | 123 MB | Sport car models |
| Skins_Stadium.pak | 264 MB | Stadium car skins |
| Skins_StadiumPrestige.pak | 959 MB | Prestige car skins |
| Trackmania.Title.Pack.Gbx | 744 MB | Title pack (master game definition) |

The theme packs provide alternative 3D models, textures, and skybox assets. The same block *names* and *geometry templates* work across all themes -- only the visual appearance changes. A map created in the GreenCoast theme can be loaded in any other theme.

### 5.5 Vehicle Models per Environment

Maps reference a vehicle model:

| Path | Vehicle | Default For |
|------|---------|-------------|
| `\Vehicles\Items\CarSport.Item.gbx` | Stadium/Sport car | Stadium |
| `\Vehicles\Items\CarSnow.Item.gbx` | Snow car | Snow surfaces |
| `\Vehicles\Items\CarRally.Item.gbx` | Rally car | Rally surfaces |
| `\Vehicles\Items\CarDesert.Item.gbx` | Desert car | Desert surfaces |
| `\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx` | Legacy Stadium car | Legacy format |

Vehicle type is stored in body chunk `0x0304300D`.

---

## 6. Map Loading Pipeline

### 6.1 Overview

Loading a .Map.Gbx file into a playable map is a **22-stage pipeline**. Each stage has a dedicated profiling marker string in the binary.

### 6.2 Phase 1: GBX Deserialization

Before the 22-stage pipeline begins, the raw GBX binary must be parsed:

```
1. Read GBX header (magic "GBX", version 6, format flags "BUCR")
2. Parse header chunk table (map info, thumbnail, author data)
3. Read node count
4. Parse reference table (external file dependencies)
5. Decompress body (LZO decompression of compressed body data)
6. Parse body chunk stream (dispatch to CGameCtnChallenge chunk handlers)
7. Read 0xFACADE01 end sentinel
```

### 6.3 Phase 2: Map Initialization (22 Stages)

After deserialization, the map object undergoes initialization:

| Stage | Method | Purpose | Performance Impact |
|-------|--------|---------|-------------------|
| 1 | `LoadDecorationAndCollection` | Load decoration theme + block collection | SLOW -- loads large .pak assets |
| 2 | `InternalLoadDecorationAndCollection` | Internal decoration setup | Moderate |
| 3 | `UpdateBakedBlockList` | Sync baked block data with serialized | Fast |
| 4 | `AutoSetIdsForLightMap` | Assign lightmap UV set IDs | Fast |
| 5 | `LoadAndInstanciateBlocks` | Create block objects from serialized data | SLOW -- proportional to block count |
| 6 | `InitChallengeData_ClassicBlocks` | Initialize standard road/platform blocks | Moderate |
| 7 | `InitChallengeData_Terrain` | Initialize terrain heightmap | Moderate |
| 8 | `InitChallengeData_DefaultTerrainBaked` | Set up default terrain from baked data | Fast |
| 9 | `InitChallengeData_Genealogy` | Build block parent-child relationships | Fast |
| 10 | `InitChallengeData_PylonsBaked` | Load pre-baked pylon structures | Fast |
| 11 | `InitChallengeData_ClassicClipsBaked` | Load baked clip connections (grid blocks) | Fast |
| 12 | `InitChallengeData_FreeClipsBaked` | Load baked clip connections (free blocks) | Fast |
| 13 | `InitChallengeData_Clips` | Initialize all clip connection data | Moderate |
| 14 | `CreateFreeClips` | Create clip objects for free-placed blocks | Moderate |
| 15 | `InitPylonsList` | Build pylon/support object list | Fast |
| 16 | `CreatePlayFields` | Create playable field areas | Fast |
| 17 | `TransferIdForLightMapFromBakedBlocksToBlocks` | Copy lightmap IDs from baked to active | Fast |
| 18 | `InitEmbeddedItemModels` | Load embedded custom item model data | SLOW if many embedded items |
| 19 | `LoadEmbededItems` | Instantiate embedded items | Moderate |
| 20 | `InitAllAnchoredObjects` | Initialize all placed items | Moderate |
| 21 | `ConnectAdditionalDataClipsToBakedClips` | Wire up additional clip data | Fast |
| 22 | `RemoveNonBlocksFromBlockStock` | Clean up non-block entries | Fast |

### 6.4 Phase 3: Runtime Preparation

After the 22 stages, additional processing occurs:

1. **Lightmap generation/loading**: If the map has pre-baked lightmaps, they are loaded. If lightmap data is absent (`lightmap="0"` in the XML header), lighting is computed at runtime or uses a default.

2. **Physics mesh generation**: Collision meshes are built from the block and item geometry. Each block's `CPlugStaticObjectModel` provides its collision shape, assembled into the world collision mesh.

3. **Filtered block list construction**: The engine builds categorized views:
   - `GetClassicBlocks()` -- Standard road/platform blocks
   - `GetTerrainBlocks()` -- Ground/terrain modification blocks
   - `GetGhostBlocks()` -- Non-physical overlay blocks

4. **Zone and terrain finalization**: The auto-terrain system (`CGameCtnAutoTerrain`) fills gaps between placed blocks with appropriate terrain geometry.

### 6.5 What's Slow vs What's Fast

For a map loader implementation, the bottlenecks are:

| Operation | Cost | Why |
|-----------|------|-----|
| LZO decompression | Fast | Simple algorithm, small data |
| Lookback string resolution | Fast | In-memory table lookup |
| Block instantiation | Moderate | Proportional to block count (hundreds to thousands) |
| Decoration/pack loading | SLOW | Requires loading megabytes of 3D assets from .pak files |
| Embedded item parsing | SLOW | Each embedded item is a full GBX sub-file |
| Lightmap generation | VERY SLOW | Full radiosity computation if not pre-baked |
| Clip connectivity | Moderate | Graph traversal over all block pairs |

---

## 7. Map Metadata

### 7.1 Header Chunk Data

Map metadata is stored in the header chunks, accessible without decompressing the body:

| Chunk ID | Content |
|----------|---------|
| `0x03043002` | Map UID, environment name, map author login |
| `0x03043003` | Map name, mood, decoration name, map type, author display name |
| `0x03043004` | Version info |
| `0x03043005` | XML community reference string |
| `0x03043007` | Thumbnail (JPEG image) + comments |
| `0x03043008` | Author zone path, author extra info |

### 7.2 The XML Header (Chunk 0x03043005)

Maps embed an XML string in the header that summarizes key metadata. From a real TechFlow.Map.Gbx:

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

Fields:
- `type`: Always `"map"` for map files
- `exever`: Game version that created the map (e.g., `"3.3.0"`)
- `exebuild`: Build date of the creating game version
- `title`: Title ID (`"TMStadium"`)
- `lightmap`: Lightmap state (`"0"` = none baked)
- `uid`: 27-character unique map identifier (base64-encoded UUID)
- `name`: Display name
- `author`: Author's account ID (base64-encoded UUID)

### 7.3 Thumbnail

The thumbnail is stored in header chunk `0x03043007`:

```
+0x00   4       uint32    version           Chunk version
+0x04   4       uint32    thumbnail_size    Size of JPEG data in bytes
...     15      bytes     "<Thumbnail.jpg>"  Marker string
...     var     bytes     jpeg_data          JPEG image (thumbnail_size bytes)
...     16      bytes     "</Thumbnail.jpg>"  End marker string
...     var     bytes     comments_data      Additional comments (XML or text)
```

The chunk `0x03043007` has the "heavy" flag (bit 31 set in the size field), meaning parsers can skip it when only light metadata is needed. This is visible in the hex dumps: chunk sizes with `0x80000000` ORed.

### 7.4 Map Types

| Map Type | String | Description |
|----------|--------|-------------|
| Race | `TrackMania\TM_Race` | Standard point-to-point or multilap race |
| Platform | `TrackMania\TM_Platform` | Platform mode (minimize restarts) |

The map type string appears in body chunk data and the XML header.

### 7.5 Medal Times

Medal/objective times are stored in body chunk `0x0304304B` and in the `CGameCtnChallengeParameters` object:

| Medal | Color | Description |
|-------|-------|-------------|
| Author | Blue/Developer | Time set by the map author |
| Gold | Gold | Target time for skilled play |
| Silver | Silver | Intermediate target |
| Bronze | Bronze | Easy target |

Times are stored as `uint32` in milliseconds. A value of `0xFFFFFFFF` means "not set."

### 7.6 Author Information

| Chunk | Field | Format |
|-------|-------|--------|
| `0x03043002` | Author login | Base64-encoded UUID (27 chars) |
| `0x03043003` | Author display name | UTF-8 string |
| `0x03043008` | Author zone path | Hierarchical zone string (e.g., `World|Europe|France`) |
| `0x03043042` | Author data (newer format) | Extended author metadata |

The author login is a base64-encoded binary UUID. Converting to the standard hyphenated hex UUID format:
```
Login (base64) -> decode -> format as UUID with hyphens = AccountID
AccountID -> remove hyphens -> hex to bytes -> base64 = Login
```

---

## 8. Map Validation Rules

### 8.1 Route Validation

For a map to be considered **valid for racing** (required for online play and leaderboard submission):

1. **Exactly one start**: The map must contain exactly one Start waypoint (or one StartFinish for multilap)
2. **Exactly one finish**: The map must contain exactly one Finish waypoint (or the StartFinish serves as both)
3. **Connected route**: There must be a drivable path from Start to Finish passing through all Checkpoints
4. **Author time set**: The map author must have completed a validation drive, setting the Author medal time
5. **All checkpoints reachable**: Every Checkpoint on the map must be crossed during the validation drive

The editor validates connectivity through `CGameEditorPluginMapConnectResults`. When the map author clicks "Test" in the editor, the game enters `CGameCtnEditorCommon::Trackmania_GameState_EditorCheckStartPlaying` mode.

### 8.2 Multilap Requirements

For multilap maps:
- Must use **StartFinish** instead of separate Start + Finish
- Lap count must be set in parameters
- All checkpoints must be reachable from the StartFinish gate and loop back to it

### 8.3 Online Play Constraints

For a map to be uploaded and played online:

| Constraint | Limit | Evidence |
|-----------|-------|---------|
| Must be validated | Author time required | Editor enforces |
| Embed size | Limited (exact value varies by context) | Server-side validation |
| Block count | No hard limit documented, but very large maps cause performance issues | Practical |
| Map file size | Varies -- servers reject excessively large files | Server-side |
| Title | Must be `TMStadium` | Server validates |

### 8.4 Ghost Block Rules

Ghost blocks (`GetGhostBlocks()`) are blocks placed with the ghost mode enabled:
- They occupy the grid but do **not** contribute to collision
- They do **not** participate in route validation
- They are used for visual decoration overlapping other blocks
- They maintain grid alignment but allow overlapping placement that would otherwise be rejected

---

## 9. Block Naming Convention

### 9.1 Name Structure

TM2020 Stadium block names follow a hierarchical pattern:

```
{Environment}{Category}{Shape}{Variant}{Modifier}
```

### 9.2 Environment Prefix

Always `Stadium` for TM2020.

### 9.3 Category Tokens

| Token | Description |
|-------|-------------|
| `Road` / `RoadMain` | Drivable road surface |
| `Platform` | Flat platform surface |
| `DecoWall` / `DecoHill` | Decorative wall/hill |
| `Pillar` | Support pillar |
| `Gate` | Start/Finish/Checkpoint gate |
| `Water` | Water element |
| `Grass` | Grass terrain |

### 9.4 Shape Tokens

| Token | Geometry |
|-------|----------|
| `Straight` | Straight segment |
| `Curve` / `Turn` | Curved segment (various radii) |
| `Slope` / `Tilt` | Inclined surface |
| `SlopeBase` / `SlopeEnd` | Slope transition at start/end |
| `Cross` | Intersection / crossroad |
| `DiagLeft` / `DiagRight` | Diagonal pieces |
| `Chicane` | S-curve |

### 9.5 Variant Suffixes

| Suffix | Meaning |
|--------|---------|
| `x2` / `x3` / `x4` | Width multiplier |
| `Narrow` | Narrower variant |
| `Mirror` | Mirrored geometry |
| `In` / `Out` | Border direction (inward/outward curve) |

### 9.6 Examples

```
StadiumRoadMainStraight           -- Basic straight road
StadiumRoadMainCurvex2            -- Double-width curve
StadiumPlatformSlopeMirror        -- Mirrored platform slope
StadiumDecoWallStraight           -- Decorative wall, straight
StadiumGrassMainSlope             -- Grass slope terrain
```

---

## 10. Surface and Material System

### 10.1 Key Finding: Gameplay Effects Are NOT Material-Driven

All 208 stock materials in `NadeoImporterMaterialLib.txt` have `DGameplayId(None)`. Gameplay effects (turbo, reactor boost, no-grip, slow motion, etc.) are applied through **block/item types and trigger zones**, not through materials.

Materials only control:
- **Surface physics** (friction, tire sound) via `DSurfaceId`
- **Texture mapping** (UV layers: BaseMaterial + Lightmap)
- **Visual appearance** (vertex color via `DColor0`)

### 10.2 Complete Surface ID Table

There are 19 unique surface types that determine physics behavior:

| Surface ID | Physics Behavior | Friction | Example Materials |
|-----------|-----------------|----------|-------------------|
| `Asphalt` | High-grip road | High | RoadTech, PlatformTech, OpenTechBorders |
| `Concrete` | Structural surface | Medium-High | Waterground, ItemPillarConcrete |
| `Dirt` | Off-road surface | Medium | RoadDirt |
| `Grass` | Natural ground | Low | Grass, DecoHill |
| `Green` | Vegetation | Low | DecoGreen |
| `Ice` | Ice surface | Very Low | PlatformIce |
| `Metal` | Metallic surface | Medium | Technics, Structure, Pylon |
| `MetalTrans` | Transparent metal | N/A (pass-through or low) | LightSpot, Ad screens |
| `NotCollidable` | No collision | N/A | Chrono digits, GlassWaterWall |
| `Pavement` | Paved sidewalk | Medium-High | PlatformPavement |
| `Plastic` | Inflatable/bouncy | Medium | ItemInflatable*, ItemObstacle |
| `ResonantMetal` | Metallic with ring | Medium | Structure, TrackWallClips |
| `RoadIce` | Icy road | Very Low | RoadIce |
| `RoadSynthetic` | Synthetic road | Medium | RoadBump, ScreenBack |
| `Rock` | Natural rock | Medium | Various deco |
| `Rubber` | Bouncy rubber | Medium-High (bounce) | TrackBorders |
| `Sand` | Sandy surface | Low | Various deco |
| `Snow` | Snow surface | Low | Various deco |
| `Wood` | Wooden surface | Medium | TrackWall |

### 10.3 Material Categories (208 Total)

| Category | Count | Materials | Surface Types |
|----------|-------|-----------|--------------|
| Roads | 4 | RoadTech, RoadBump, RoadDirt, RoadIce | Asphalt, RoadSynthetic, Dirt, RoadIce |
| Platforms | 3 | PlatformTech, OpenTechBorders, ItemInflatableFloor | Asphalt, Plastic |
| Inflatables | 2 | ItemInflatableMat, ItemInflatableTube | Plastic, Metal |
| Track Elements | 6+ | TrackBorders, TrackBordersOff, TrackWall, TrackWallClips, PoolBorders, WaterBorders | Rubber, Wood, Plastic, ResonantMetal |
| Technics | 5+ | Structure, Technics, TechnicsTrims, Pylon, Waterground | Metal, Concrete, ResonantMetal |
| Decoration | 5+ | Grass, DecoHill, DecoHill2, DecoGreen, GlassWaterWall | Grass, Green, NotCollidable |
| Racing UI | 5+ | RaceArch*, Speedometer, Chrono digits | NotCollidable |
| Ad Screens | 10+ | Ad*Screen, 16x9ScreenOff | MetalTrans |
| Items | 10+ | ItemPillar*, ItemTrackBarrier*, ItemObstacle*, ItemRamp | Various |
| Custom/Mod | 20+ | Custom*, CustomMod* variants | Various |

### 10.4 Material Library Format

The `NadeoImporterMaterialLib.txt` uses this grammar:

```
DLibrary(<library_name>)
  DMaterial(<material_name>)
    DSurfaceId(<surface_id>)
    DGameplayId(<gameplay_id>)
    DUvLayer(<layer_type>, <channel_index>)
    [DColor0()]
    [DLinkFull(<media_path>)]
```

Every TM2020 material is in `DLibrary(Stadium)`.

### 10.5 UV Layer Requirements

| Material Type | UV0 | UV1 | Notes |
|---------------|-----|-----|-------|
| Standard (roads, platforms, technics) | BaseMaterial | Lightmap | Both required |
| Decals (DecalCurbs, etc.) | BaseMaterial | -- | No lightmap (projected) |
| Grass | Lightmap | -- | UNUSUAL: lightmap on channel 0 |
| Dynamic items (obstacles, lights) | BaseMaterial | -- | No lightmap (dynamic) |
| Custom* materials | Lightmap | -- | Engine-provided textures |
| CustomMod* materials | BaseMaterial | Lightmap | User-moddable |
| FX materials (Boost_SpecialFX, etc.) | BaseMaterial | -- | Visual effect only |

**Critical for item creators**: Every drivable surface mesh MUST have a Lightmap UV layer. Without it, NadeoImporter will abort with `"Mesh has no LM UVs => abort"`.

---

## 11. GBX Map File Binary Layout

### 11.1 File Structure Overview

A `.Map.Gbx` file is a GBX version 6 binary file with class ID `0x03043000` (CGameCtnChallenge):

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
|   External node count (uint32)          |
|   Ancestor folders (if > 0)             |
|   Reference entries                     |
+=========================================+
| BODY (compressed)                       |
|   Uncompressed size (uint32)            |
|   Compressed size (uint32)              |
|   LZO-compressed body chunk stream      |
+=========================================+
```

### 11.2 Format Flags

All real map files observed use `BUCR`:
- **B**: Binary format
- **U**: Body wrapper uncompressed
- **C**: Body stream compressed (LZO)
- **R**: With external references

### 11.3 Header Chunks

| Chunk ID | Heavy? | Typical Size | Content |
|----------|--------|--------------|---------|
| `0x03043002` | No | ~57 bytes | Map UID, environment, author |
| `0x03043003` | No | ~225 bytes | Map name, mood, decoration |
| `0x03043004` | No | 4 bytes | Version |
| `0x03043005` | No | ~525 bytes | XML metadata |
| `0x03043007` | **Yes** | ~24-100 KB | Thumbnail JPEG |
| `0x03043008` | No | ~82 bytes | Author info |

The heavy flag on chunk `0x03043007` means the thumbnail can be skipped for quick metadata reads.

### 11.4 Body Chunks

| Chunk ID | Skippable | Content |
|----------|-----------|---------|
| `0x0304300D` | Yes | Vehicle/player model reference |
| `0x03043011` | No | Block data array (primary block storage) |
| `0x0304301F` | Yes | Block parameters + additional block data |
| `0x03043022` | Yes | [UNKNOWN] |
| `0x03043024` | Yes | Music reference |
| `0x03043025` | Yes | [UNKNOWN] |
| `0x03043026` | Yes | [UNKNOWN] |
| `0x03043028` | Yes | [UNKNOWN] |
| `0x03043029` | Yes | [UNKNOWN] |
| `0x03043034` | Yes | [UNKNOWN] |
| `0x03043036` | Yes | [UNKNOWN] |
| `0x03043038` | Yes | [UNKNOWN] |
| `0x03043040` | Yes | Anchored object (item) placement data |
| `0x03043042` | Yes | Author data (newer format) |
| `0x03043043` | Yes | Genealogy / block relationships |
| `0x03043044` | Yes | Script metadata |
| `0x03043048` | Yes | Baked blocks data |
| `0x03043049` | Yes | [UNKNOWN] |
| `0x0304304B` | Yes | Objectives / medal times |
| `0x03043054` | Yes | Embedded items |
| `0x03043056` | Yes | [UNKNOWN] |
| `0xFACADE01` | -- | End sentinel |

### 11.5 LookbackString System

Block and item names use string interning. The first Id read in a context must establish the lookback version:

```
First Id read:    uint32 = 3 (version marker)
Subsequent reads: uint32 flags_and_index
  Bits 31-30 = 0b11: New string follows (read length-prefixed string, add to table)
  Bits 31-30 = 0b10: Reference to previously-seen string at index (bits 29-0)
  Bits 31-30 = 0b01: Well-known string (predefined):
    0x40000001 = "Unassigned"
    0x40000002 = "" (empty)
    0x40000003 = "Stadium"
    0x40000004 = "Valley"
    0x40000005 = "Canyon"
    0x40000006 = "Lagoon"
```

The lookback table is per-node -- it resets for each serialization context.

---

## 12. Real File Hex Analysis

### 12.1 File Header Pattern

Every .Map.Gbx starts with the same byte sequence. Here is the annotated hex from CraterWorld.Map.Gbx:

```
Offset  Bytes                           Interpretation
------  -----                           --------------
0x0000  47 42 58                        Magic: "GBX"
0x0003  06 00                           Version: 6 (little-endian uint16)
0x0005  42 55 43 52                     Format flags: "BUCR"
0x0009  00 30 04 03                     Class ID: 0x03043000 (CGameCtnChallenge)
                                        NOTE: stored little-endian, reads as 0x00300403 in hex dump
                                        but the value is 0x03043000
```

Wait -- let me re-examine. The bytes at offset 0x0009 are `5b fa 00 00` in the first file. Let me re-read.

Actually, looking at the CraterWorld hex dump more carefully:

```
0x0000: 47 42 58 06 00 42 55 43 52 00 30 04 03 5b fa 00

Byte-by-byte:
0x00-02: "GBX"                          Magic
0x03-04: 06 00                          Version 6
0x05-08: 42 55 43 52                    "BUCR" format flags
0x09-0C: 00 30 04 03                    Class ID = 0x03043000 (LE)
0x0D-10: 5b fa 00 00                    User data size = 0x0000FA5B = 64,091 bytes
0x11-14: 06 00 00 00                    Header chunk count = 6
```

### 12.2 Header Chunk Table

Continuing from CraterWorld.Map.Gbx:

```
Header chunk index (6 entries, 8 bytes each):
  Chunk 0: 02 30 04 03  39 00 00 00    ID=0x03043002  Size=0x39 (57 bytes)
  Chunk 1: 03 30 04 03  f1 00 00 00    ID=0x03043003  Size=0xF1 (241 bytes)
  Chunk 2: 04 30 04 03  04 00 00 00    ID=0x03043004  Size=0x04 (4 bytes)
  Chunk 3: 05 30 04 03  63 02 00 80    ID=0x03043005  Size=0x263 (611 bytes) HEAVY
  Chunk 4: 07 30 04 03  44 f6 00 80    ID=0x03043007  Size=0xF644 (63,044 bytes) HEAVY
  Chunk 5: 08 30 04 03  52 00 00 00    ID=0x03043008  Size=0x52 (82 bytes)
```

Note: Chunks 3 (0x03043005) and 4 (0x03043007) have bit 31 set in the size (`0x80000000`), marking them as "heavy" chunks. The actual size is obtained by masking: `size & 0x7FFFFFFF`.

### 12.3 Comparing Multiple Map Headers

| Field | CraterWorld | Kacky394 | TechFlow | PillarWorld |
|-------|-------------|----------|----------|-------------|
| Magic | GBX | GBX | GBX | GBX |
| Version | 6 | 6 | 6 | 6 |
| Format | BUCR | BUCR | BUCR | BUCR |
| Class ID | 0x03043000 | 0x03043000 | 0x03043000 | 0x03043000 |
| Header chunks | 6 | 6 | 6 | 6 |
| Thumbnail size | ~63 KB | ~100 KB | ~24 KB | ~22 KB |
| Decoration | NoStadium48x48Day | 48x48Screen155Sunrise | NoStadium48x48Day | NoStadium48x48Day |
| Map type | TrackMania\TM_Race | TrackMania\TM_Race | TrackMania\TM_Race | TrackMania\TM_Race |

All maps share: version 6, BUCR format, 6 header chunks, same class ID, same map type. The differences are in user data size (driven mainly by thumbnail size) and decoration name.

### 12.4 Map Name and Author Extraction

From the hex dump, these strings are visible in the header chunk data (uncompressed):

**CraterWorld.Map.Gbx** (offset ~0xCC):
```
0b 00 00 00 43 72 61 74 65 72 57 6f 72 6c 64    Length=11 "CraterWorld"
```

**Author login** (27-char base64 at ~0x8C):
```
58 43 68 77 44 75 38 46 52 6d 57 48 2d 67 48     "XChwDu8FRmWH-gH"
71 58 55 62 42 74 67                               "qXUbBtg"
```

This author login (`XChwDu8FRmWH-gHqXUbBtg`) appears in ALL the examined maps -- consistent with them all being created by the same author.

---

## 13. Class Reference

### 13.1 Map Structure Classes (CGameCtnChallenge)

`CGameCtnChallenge` is the root map class (class ID `0x03043000`). Legacy name: "Challenge" from the TMN/TMUF era.

**Known methods** (from RTTI):

```
AutoSetIdsForLightMap
ConnectAdditionalDataClipsToBakedClips
CreateFreeClips
CreatePlayFields
InitAllAnchoredObjects
InitChallengeData_ClassicBlocks
InitChallengeData_ClassicClipsBaked
InitChallengeData_Clips
InitChallengeData_DefaultTerrainBaked
InitChallengeData_FreeClipsBaked
InitChallengeData_Genealogy
InitChallengeData_PylonsBaked
InitChallengeData_Terrain
InitEmbeddedItemModels
InitPylonsList
InternalLoadDecorationAndCollection
LoadAndInstanciateBlocks
LoadDecorationAndCollection
LoadEmbededItems
RemoveNonBlocksFromBlockStock
SFilteredBlockLists
TransferIdForLightMapFromBakedBlocksToBlocks
UpdateBakedBlockList
```

**Related map classes**:

| Class | Purpose |
|-------|---------|
| `CGameCtnChallengeInfo` | Map metadata (UID, name, author) |
| `CGameCtnChallengeParameters` | Map parameters (time limits, medal times, lap count) |
| `CGameCtnChallengeGroup` | Group of maps (campaign chapters) |
| `CGameCtnCollection` | Block collection for an environment |
| `CGameCtnCatalog` | Block catalog |
| `CGameCtnCampaign` | Campaign structure |
| `CGameCtnChapter` | Campaign chapter |

### 13.2 Block Classes

| Class | Purpose |
|-------|---------|
| `CGameCtnBlock` | Placed block instance on the map |
| `CGameCtnBlockInfo` | Base block type definition |
| `CGameCtnBlockInfoClassic` | Standard grid-snapped block |
| `CGameCtnBlockInfoClip` | Clip connection block (base) |
| `CGameCtnBlockInfoClipHorizontal` | Horizontal clip block |
| `CGameCtnBlockInfoClipVertical` | Vertical clip block |
| `CGameCtnBlockInfoFlat` | Flat terrain block |
| `CGameCtnBlockInfoFrontier` | Zone boundary block |
| `CGameCtnBlockInfoMobil` | Moving/animated block |
| `CGameCtnBlockInfoMobilLink` | Mobile block link |
| `CGameCtnBlockInfoPylon` | Auto-generated support pillar |
| `CGameCtnBlockInfoRectAsym` | Rectangular asymmetric block |
| `CGameCtnBlockInfoRoad` | Road block |
| `CGameCtnBlockInfoSlope` | Sloped surface block |
| `CGameCtnBlockInfoTransition` | Terrain transition block |
| `CGameCtnBlockInfoVariant` | Base variant |
| `CGameCtnBlockInfoVariantAir` | Air (elevated) variant |
| `CGameCtnBlockInfoVariantGround` | Ground variant |
| `CGameCtnBlockSkin` | Block skin/appearance override |
| `CGameCtnBlockUnit` | Single cell of a multi-cell block |
| `CGameCtnBlockUnitInfo` | Block unit metadata |

### 13.3 Item/Anchor Classes

| Class | Purpose |
|-------|---------|
| `CGameCtnAnchoredObject` | Placed item instance on the map |
| `CGameCtnAnchorPoint` | Anchor point on a block |
| `CGameItemModel` | Item model definition (root) |
| `CGameItemModelTreeRoot` | Item model hierarchy root |
| `CGameItemPlacementParam` | Item placement parameters |
| `CItemAnchor` | Item anchor point |
| `CGameBlockItem` | Block-as-item wrapper |
| `CGameBlockItemVariantChooser` | Block item variant selection |
| `CGameBlockInfoGroups` | Block info group collection |
| `CGameBlockInfoTreeRoot` | Block info tree root |
| `CAnchorData` | Anchor/waypoint data (has `EWaypointType`) |
| `CGameWaypointSpecialProperty` | Waypoint properties (start/finish/CP) |

### 13.4 Zone/Terrain Classes

| Class | Purpose |
|-------|---------|
| `CGameCtnZone` | Base zone |
| `CGameCtnZoneFlat` | Flat terrain zone |
| `CGameCtnZoneFrontier` | Zone border |
| `CGameCtnZoneTransition` | Zone transition |
| `CGameCtnZoneFusionInfo` | Zone fusion data |
| `CGameCtnZoneGenealogy` | Zone genealogy/history |
| `CGameCtnAutoTerrain` | Auto-generated terrain fill |
| `CGameCtnPylonColumn` | Pylon column (support pillar) |

### 13.5 Decoration Classes

| Class | Purpose |
|-------|---------|
| `CGameCtnDecoration` | Map decoration definition |
| `CGameCtnDecorationSize` | Grid dimensions (SizeX, SizeY, SizeZ) |
| `CGameCtnDecorationMood` | Time-of-day / lighting mood |
| `CGameCtnDecorationMaterialModifiers` | Material appearance overrides |

### 13.6 Editor Classes

| Class | Purpose |
|-------|---------|
| `CGameCtnEditorCommon` | Common map editor logic |
| `CGameCtnEditorCommonInterface` | Editor UI / inventory system |
| `CGameCtnEditorHistory` | Undo/redo history |
| `CGameCtnEditorFree` | Main map editor mode |
| `CGameCtnEditorPuzzle` | Puzzle editor mode (limited block set) |
| `CGameEditorMapMacroBlockInstance` | Macroblock instance in editor |
| `CGameEditorPluginMapConnectResults` | Block connection validation |
| `CMapEditorInventory` | Script-accessible block inventory |
| `CMapEditorCursor` | Editor placement cursor |

### 13.7 Macroblock Classes

| Class | Purpose |
|-------|---------|
| `CGameCtnMacroBlockInfo` | Macroblock template (multi-block group) |
| `CGameCtnMacroBlockJunction` | Connection point between macroblocks |
| `CGameCtnMacroDecals` | Decals within a macroblock |

### 13.8 Script API Classes (Block/Map)

| Class | Purpose |
|-------|---------|
| `CBlockModel` | Script API: block model (exposes `EWayPointType`) |
| `CBlockModelClip` | Script API: clip model |
| `CBlockModelVariant` | Script API: variant |
| `CBlockModelVariantAir` | Script API: air variant |
| `CBlockModelVariantGround` | Script API: ground variant |
| `CBlockClip` | Script API: clip connection |
| `CBlockClipList` | Script API: clip list |
| `CBlockUnit` | Script API: block unit |
| `CBlockUnitModel` | Script API: block unit model |

### 13.9 Key Class ID Quick Reference

| Class ID | Class | File Extension |
|----------|-------|---------------|
| `0x03043000` | CGameCtnChallenge | `.Map.Gbx` |
| `0x03093000` | CGameCtnReplayRecord | `.Replay.Gbx` |
| `0x09005000` | CPlugSolid | (legacy mesh) |
| `0x09011000` | CPlugBitmap | `Texture.Gbx` |
| `0x09026000` | CPlugShaderApply | `Material.Gbx` |
| `0x090BB000` | CPlugSolid2Model | `.Solid2.gbx` |

Legacy class ID `0x24003000` remaps to `0x03043000` (CGameCtnChallenge) for backward compatibility with old ManiaPlanet files.

---

## Appendix A: Quick Reference for Map Loader Implementors

### Minimum Viable Parser

To load a map and extract block/item data, you need to:

1. Parse the GBX header (magic, version, format flags, class ID)
2. Read header chunks (extract metadata: name, author, UID, thumbnail)
3. Skip or parse the reference table
4. Decompress the body (LZO)
5. Parse body chunks, focusing on:
   - `0x03043011` -- block data array
   - `0x03043040` -- item placement array
   - `0x0304304B` -- medal times
   - `0x03043054` -- embedded items (if self-contained maps needed)
6. Handle the LookbackString system for block/item name resolution
7. Apply class ID remapping for legacy files

### Data You Get Per Block

```
block_name:  string    (e.g., "StadiumRoadMainStraight")
direction:   0-3       (North/East/South/West)
coord_x:     uint32    (grid X position)
coord_y:     uint32    (grid Y position -- multiply by 8 for meters)
coord_z:     uint32    (grid Z position)
flags:       uint32    (bit 15 = is_ground, 0xFFFFFFFF = free block)
```

### Data You Get Per Item

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

### End Sentinel

The body chunk stream always ends with `0xFACADE01`. If you read this value as a chunk ID, stop parsing.

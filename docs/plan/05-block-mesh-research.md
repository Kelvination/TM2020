# 05 - Block Mesh Extraction Research

> Comprehensive analysis of every known approach for extracting TM2020 block geometry
> for browser rendering.
>
> **Date**: 2026-03-27
> **Status**: Research complete, recommended path identified

---

## Executive Summary

There are **7 viable approaches** to obtaining TM2020 block geometry. The recommended
strategy combines **two approaches in sequence**: first use the GBX.NET + PAK extraction
pipeline (Approach 1) for exact, authoritative geometry, falling back to Ninja Ripper
(Approach 4) for validation. The Blender Gbx Tools plugin (Approach 3) can then import
the extracted meshes for inspection and conversion.

**Critical finding**: The pack files are encrypted with Blowfish CBC using keys derived
from server-sent sub-keys. GBX.NET.PAK already implements this decryption. Once
extracted, GBX.NET can parse CPlugSolid2Model (Mesh.Gbx) files to obtain exact vertex
positions, normals, UVs, and triangle indices. This is the only path that yields
pixel-perfect geometry matching the actual game.

---

## Table of Contents

1. [Approach 1: GBX.NET + PAK Extraction Pipeline](#approach-1-gbxnet--pak-extraction-pipeline)
2. [Approach 2: Openplanet Fid Extraction](#approach-2-openplanet-fid-extraction)
3. [Approach 3: Blender Gbx Tools Import](#approach-3-blender-gbx-tools-import)
4. [Approach 4: Ninja Ripper D3D11 Capture](#approach-4-ninja-ripper-d3d11-capture)
5. [Approach 5: RenderDoc Frame Capture](#approach-5-renderdoc-frame-capture)
6. [Approach 6: NadeoImporter Reverse Path](#approach-6-nadeoimporter-reverse-path)
7. [Approach 7: Procedural Geometry Generation](#approach-7-procedural-geometry-generation)
8. [Pack File Format Details](#pack-file-format-details)
9. [Mesh Data Format Details](#mesh-data-format-details)
10. [Recommended Strategy](#recommended-strategy)

---

## Approach 1: GBX.NET + PAK Extraction Pipeline

### What It Is

Use BigBang1112's GBX.NET library (C#/.NET) with the GBX.NET.PAK extension to:
1. Decrypt and decompress Stadium.pak (and other .pak files)
2. Extract individual GBX files (Solid.Gbx, Mesh.Gbx, Material.Gbx, etc.)
3. Parse CPlugSolid2Model to extract vertex positions, normals, UVs, indices
4. Export to a browser-friendly format (glTF, OBJ, or custom binary)

### Evidence

- **GBX.NET** supports 400+ GBX classes including CPlugSolid2Model (Mesh.Gbx) with
  full read/write support, CPlugSolid (Solid.Gbx), and CPlugSurface (Shape.Gbx).
  Repository: https://github.com/BigBang1112/gbx-net
- **GBX.NET.PAK** (NuGet package) implements NadeoPak decryption including the
  non-standard CBC variant with ivXor handling. It "uses a different zlib solution
  due to very specific patterns to follow during decryption + decompression."
- **Nations Converter 2** (https://nc.gbx.tools/) is a working proof-of-concept:
  it extracts "direct mesh data from Solid.Gbx files" from pack files and converts
  them into Item.Gbx files for TM2020. The project "abandoned mesh ripping" in
  favor of direct Solid.Gbx extraction since 2024.
- The Blender Gbx Tools plugin (https://3d.gbx.tools/blender) can import Mesh.Gbx,
  Solid.Gbx, Prefab.Gbx, Shape.Gbx, and Item.Gbx with collision models and
  materials, proving the data is fully parseable.

### Key Challenge: PAK Encryption Keys

TM2020's .pak files use **version 18** of the NadeoPak format (confirmed: all paks
show `0x00000012` at offset 0x08). The encryption uses Blowfish CBC with 16-byte keys.

For TM2020/ManiaPlanet era:
- Keys are **not** in packlist.dat (that file does not exist for ManiaPlanet+)
- Keys are sent from Nadeo's master server as "sub-keys" during authentication
- Sub-keys are stored in the user's Profile.Gbx for offline use
- Two paks (ManiaPlanet.pak, Resource.pak) have sub-keys hardcoded in the executable
- The final key = md5(sub-key + additional_material) (exact formula differs from legacy)
- GBX.NET.PAK already implements this key derivation

**How to obtain keys**: Run the game, authenticate, then either:
- Extract sub-keys from Profile.Gbx (GBX.NET can parse these)
- Use GBX.NET.PAK's built-in key handling
- Hook the decryption in Trackmania.exe via Ghidra RE (we have the decompiled binary)

### Feasibility: YES
### Effort: 1-2 weeks
### Quality: EXACT (pixel-perfect, authoritative game geometry)
### Recommendation: **PRIMARY APPROACH -- Use this**

The pipeline would be:
```
Stadium.pak --[GBX.NET.PAK decrypt]--> Solid.Gbx files
           --[GBX.NET parse]--> CPlugSolid2Model (vertices, indices, UVs)
           --[custom exporter]--> glTF/custom binary for browser
```

---

## Approach 2: Openplanet Fid Extraction

### What It Is

Use Openplanet's built-in Fid Explorer / Pack Explorer to browse and extract files
directly from mounted .pak files while the game is running. Alternatively, use the
Fid Loader plugin to extract specific files by path.

### Evidence

- **Already partially working on this machine**: Openplanet has extracted files to:
  ```
  .../OpenplanetNext/Extract/GameData/Stadium/Items/*.Item.Gbx  (35+ tree/scenery items)
  .../OpenplanetNext/Extract/GameData/Stadium/Media/Texture/Image/*.dds  (textures)
  ```
  These include PalmTreeSmall.Item.Gbx (3,174 bytes, class 0x2E002000, BUUR format),
  textures like RoadTech_D.dds, PlatformTech_D.dds, etc.

- **Fid Explorer** (built into Openplanet): Browse System -> Drives/Folders to see
  mounted pack file contents. Can extract individual files.

- **Fid Loader plugin** (https://openplanet.dev/plugin/fidloader): Extracts files by
  exact path. Works with hashed filenames. Supports batch extraction.

- **Pack files use hashed filenames**: Most files in .pak have their filenames replaced
  with hashes. Openplanet resolves these at runtime since the game mounts them.

### Key Challenge

Openplanet can extract individual GBX files, but:
1. You must know or discover the file paths (hashed in the pack)
2. Extraction is manual/semi-manual (need the game running)
3. Block geometry (Solid.Gbx / Mesh.Gbx for vanilla blocks) may not be directly
   accessible as separate files -- they may be embedded inside CGameCtnBlockInfo
   nodes within the pack's GBX tree
4. Need to figure out the exact file paths for each block's mesh data

### What Openplanet Exposes via API

The Openplanet AngelScript API exposes:
- `CGameCtnBlockInfo`: Has `VariantBaseGround` and `VariantBaseAir` properties
- `CGameCtnBlockInfoVariant`: Has `HelperSolidFid` (CPlugSolid@) and
  `FacultativeHelperSolidFid` (CPlugSolid@), plus `WaypointTriggerShape` (CPlugSurface@)
- `CPlugSolid`: Only exposes `IdName` and `Id` (NO mesh data accessible via API)
- `CPlugSolid2Model`: Only exposes `IdName` and `Id` (NO vertices/faces via API)

**The Openplanet API does NOT expose vertex/face data.** It can give you references to
the solid objects, but not their actual geometry. The geometry is only accessible by
extracting the raw GBX files and parsing them externally.

### Feasibility: MAYBE (for file extraction, not direct mesh access)
### Effort: Days (to extract all block files, need game running)
### Quality: EXACT (files are the real game data)
### Recommendation: **Use as supplement to Approach 1**

Use Openplanet Fid Explorer to:
- Discover file paths within the pack (then feed to GBX.NET)
- Extract individual GBX files for testing/validation
- Extract textures (.dds files)

---

## Approach 3: Blender Gbx Tools Import

### What It Is

BigBang1112's Blender plugin (https://3d.gbx.tools/blender) imports Mesh.Gbx,
Solid.Gbx, Prefab.Gbx, Shape.Gbx, and Item.Gbx files directly into Blender with
collision models and complex materials.

### Evidence

- Actively maintained (copyright 2025-2026, v0.1.1 released March 2026)
- Open source: https://github.com/BigBang1112/blender-gbx-tools
- Can resolve mesh variants from block info files (EDClassic.Gbx, etc.)
- Supports display of collision models and complex materials
- Available through Blender's extension repository

### Key Limitation

**Cannot import directly from .pak files yet.** You must first extract the GBX files
using another method (Approach 1 or 2), then import them into Blender.

### Feasibility: YES (given extracted files)
### Effort: Hours (once files are extracted)
### Quality: EXACT (reads native GBX mesh data)
### Recommendation: **Use for visual validation and manual inspection**

Use this to verify extracted meshes look correct before building the browser pipeline.
Also useful for one-off exports to glTF/OBJ from Blender.

---

## Approach 4: Ninja Ripper D3D11 Capture

### What It Is

Ninja Ripper (https://www.ninjaripper.com/) hooks D3D11 to capture all geometry
rendered in a frame. For TM2020, this captures the actual GPU vertex/index buffers
as the game renders them.

### Evidence

- Documented workflow on Trackmania Wiki:
  https://wiki.trackmania.io/en/content-creation/nadeo-importer/ninja-ripper
- Used by the community for getting vanilla blocks into Blender
- Supports D3D11 (TM2020's graphics API)
- Captures vertices, UVs, normals, and textures per draw call

### Workflow

1. Launch TM2020 through Ninja Ripper with D3D11 wrapper
2. Load a map containing the blocks you want
3. Press capture hotkey to rip the current frame
4. Import .rip files into Blender using Ninja Ripper's Blender addon

### Critical LOD Problem

Ninja Ripper captures whatever LOD is currently on screen. Distant blocks use low-poly
LODs. The community workaround:

1. Place desired vanilla blocks in a map
2. Use Mesh Modeler to convert each vanilla block to a custom item
3. Custom items lose LOD system (always render highest quality)
4. Re-place the custom items and capture with Ninja Ripper

This is tedious but produces high-quality meshes.

### Limitations

- **No material names**: Textures come as separate images, not linked to TM material names
- **Scene-at-a-time**: Must capture per-frame, one camera angle
- **LOD artifacts**: Without the Mesh Modeler workaround, meshes are mixed quality
- **Manual process**: Each block type needs to be placed, converted, and captured
- **UV mapping may differ**: Capture UVs are from the GPU, which may have been
  transformed by vertex shaders
- **Normals may be in world space**: Need to transform back to object space
- **No physics/collision data**: Only visual meshes are captured

### Feasibility: YES
### Effort: 1-2 weeks (for all ~200+ block types with the LOD workaround)
### Quality: APPROXIMATE (high visual fidelity, but UV/normal artifacts possible)
### Recommendation: **Use as validation/fallback for Approach 1**

---

## Approach 5: RenderDoc Frame Capture

### What It Is

RenderDoc (https://renderdoc.org/) is a professional GPU debugger that captures
D3D11 frames with full pipeline state inspection. Unlike Ninja Ripper, it captures
the complete pipeline state (shaders, constant buffers, render targets) not just
geometry.

### Evidence

- Supports D3D11 up to D3D11.4 on Windows
- Mesh viewer with per-draw-call vertex inspection
- Can export vertex data to CSV, which can be converted to OBJ
- Python API for programmatic mesh extraction (renderdoc.org/docs/python_api/)
- Can inspect vertex/index buffers, shader inputs/outputs at every pipeline stage

### Advantages Over Ninja Ripper

- See the exact vertex shader transformations applied
- Inspect material bindings (textures, constant buffers)
- Programmatic extraction via Python API (could automate)
- Full pipeline state (useful for understanding the rendering approach)

### Disadvantages

- Same LOD problem as Ninja Ripper
- Must run on Windows (or Wine/CrossOver -- uncertain compatibility)
- Frame capture may be blocked by anti-cheat or DRM
- Requires more technical expertise to extract mesh data

### Feasibility: MAYBE
### Effort: 1-2 weeks (similar to Ninja Ripper, plus automation work)
### Quality: APPROXIMATE (same as Ninja Ripper, but with more metadata)
### Recommendation: **Investigate further only if Approach 1 fails**

---

## Approach 6: NadeoImporter Reverse Path

### What It Is

NadeoImporter converts FBX -> Item.Gbx (one-way). The question: can we reverse it?

### Evidence

- NadeoImporter.exe strings reveal rich internal knowledge:
  `Vertex`, `Normal`, `Position`, `CPlugBitmapRenderSolid`, `Solid`, `Solids`,
  `TriggerSolid`, `VertexShader`, `VertexTextures`, `ShaderMeshPaintLayer`, etc.
- It uses libfbxsdk.dll (Autodesk FBX SDK 2018) for importing FBX files
- The conversion is definitively ONE-WAY: FBX -> GBX only
- No reverse tool exists in the Nadeo ecosystem
- NadeoImporter does not read .pak files -- it only processes user-provided FBX files

### The Real Reverse Path

The "reverse" is not NadeoImporter itself but GBX.NET:
- GBX.NET CPlugSolid2Model has full read support
- It can deserialize the exact same data NadeoImporter writes
- This IS the reverse path, just using a different tool

### Feasibility: NO (for NadeoImporter itself; YES via GBX.NET)
### Effort: N/A
### Quality: N/A
### Recommendation: **Skip -- GBX.NET (Approach 1) IS the reverse path**

---

## Approach 7: Procedural Geometry Generation

### What It Is

Instead of extracting geometry, generate it programmatically based on known block
dimensions and types. TM2020 Stadium blocks use a 32x8x32 meter grid.

### Evidence

- Block grid is well-documented: each block occupies a 32x8x32m cell
- Block types are enumerable from map files (CGameCtnChallenge)
- The Trackmania Blocks Generator Blender addon (https://github.com/frolad/Trackmania-Blocks-Generator)
  uses a template-based system with pre-built components to assemble blocks
- That addon has generated "nearly 18k blocks including all extensions"
- Road surfaces are essentially extruded paths along the grid
- Platform surfaces are flat quads with edge treatments
- Terrain is a heightmap-based system

### Critical Limitation

While simple blocks (flat road, flat platform) could be procedurally generated,
the visual detail is far more complex:

- Curved block surfaces (banked turns, slopes) have non-trivial geometry
- Deco elements (railings, barriers, pylons, lights) have intricate meshes
- Edge treatments where blocks meet grass/dirt are detailed
- Material transitions require careful UV mapping
- There are 200+ block types, many with complex visual geometry
- The Trackmania Wiki documents the full block catalog

### Feasibility: MAYBE (for physics-only; NO for visual fidelity)
### Effort: Months (for a visually complete set)
### Quality: PLACEHOLDER (physics could be exact; visuals would be approximate)
### Recommendation: **Use as Phase 1 placeholder, replace with extracted meshes later**

For an MVP, could use simple box/extruded geometry with correct dimensions and materials
while working on the real extraction pipeline. The collision/physics shapes are simpler
than the visual meshes.

---

## Pack File Format Details

### NadeoPak v18 (TM2020)

All TM2020 .pak files use NadeoPak version 18:

```
Offset  Size   Field                    All TM2020 Paks
------  ----   -----                    ---------------
0x00    8      magic                    "NadeoPak"
0x08    4      version                  18 (0x12)
0x0C    32     SHA-256 ContentsChecksum (unique per pak, plaintext)
0x2C    4      header_flags             0x07 (IsHeaderPrivate | UseDefaultHeaderKey | IsDataPrivate)
0x30    4      block_alignment          0x3000 or 0x4000
0x34    var    (zeros + title + timestamp + encrypted content tree)
```

### Key Packs and Their Contents

| Pack File | Size | Title | Likely Contents |
|-----------|------|-------|-----------------|
| Stadium.pak | 1.67 GB | TMStadium | **Block meshes, materials, shaders** |
| Maniaplanet.pak | 169 MB | ManiaPlanet | Core engine resources |
| Maniaplanet_Core.pak | 34 MB | ManiaPlanet | Core game data |
| Maniaplanet_ModelsSport.pak | 123 MB | -- | Player/car models |
| Skins_Stadium.pak | 264 MB | -- | Car skins |
| BlueBay.pak | 530 MB | TMStadium | BlueBay environment |
| GreenCoast.pak | 570 MB | TMStadium | GreenCoast environment |
| RedIsland.pak | 776 MB | TMStadium | RedIsland environment |
| WhiteShore.pak | 411 MB | TMStadium | WhiteShore environment |
| Resource.pak | 178 KB | -- | Minimal resource index |

### Strings Found in Stadium.pak

The encrypted content still leaks partial strings:
- Block names: `DecoPlatform`, `RoadEndSlope2StraightR`, `RoadSlope2UBottom_Air`,
  `GameCtnBlockInfo`, paths like `\\storage.nadeo.org\graphical_data\Stadium\3D\...`
- Material references: `Tech3 Block DecalGeom.Material.gbx`,
  `Tech3 Block PyPxz_Hue.Material.gbx`, `Tech3 Block TAdd.Material.gbx`,
  `Tech3_Block_TDSN_CubeOut.Material.gbx`, `GlassBasic.Material.gbx`
- Texture files: `EnvLayerDirt_D.dds`, `DecalSponsor1x1BigA_D.dds`,
  `WarpRace155_pz1.dds`
- File extensions: `.Material.Gbx`, `.dds`, `.Gbx`

This confirms the pack contains the actual block geometry, material definitions,
and textures we need.

### Encryption

- Algorithm: Blowfish CBC with 16-byte key
- Non-standard CBC: ivXor applied every 256 bytes and on first read
- Key source: Master server sub-keys (stored in Profile.Gbx for offline)
- ManiaPlanet.pak and Resource.pak have hardcoded sub-keys in the executable
- Compression: LZ4 with dictionary (since NadeoPak v18)
- ivXor calculation: derived from folder names and class IDs in the header

---

## Mesh Data Format Details

### CPlugSolid2Model (Mesh.Gbx)

This is the primary mesh container class. GBX.NET supports full read/write.

The NadeoImporter produces Item.Gbx files that embed CPlugSolid2Model containing:
- Vertex positions (float3)
- Vertex normals (float3)
- UV coordinates (float2, up to 2 layers: BaseMaterial + Lightmap)
- Triangle indices (uint16 or uint32)
- Material references (by name, linking to the material library)
- LOD levels (multiple mesh variants at different detail levels)
- Bounding box / bounding sphere

### Material System

Materials are defined in `NadeoImporterMaterialLib.txt` (1,375 lines) with:
- 24 surface physics types (Asphalt, Dirt, Ice, Metal, Wood, Grass, etc.)
- 3 UV layer patterns (Standard Opaque, Decal, Lightmap-only)
- Complete texture naming convention: `{Name}_D.dds` (diffuse), `_N.dds` (normal),
  `_R.dds` (roughness/specular), `_H.dds` (height), `_L.dds` (lightmap mask)
- All gameplay IDs are `None` -- gameplay effects come from the block system

### Item.Gbx Structure (Already Extracted)

The Openplanet-extracted Item.Gbx files on this machine use class ID 0x2E002000
(CGameCtnBlockInfo/CGameItemModel) with BUUR format (fully uncompressed). Example:
- PalmTreeSmall.Item.Gbx: 3,174 bytes, contains embedded RIFF data (WebP texture)
- Contains author "Nadeo", collection "Items"
- Self-contained (no external .Mesh.Gbx/.Shape.Gbx dependencies)

---

## Recommended Strategy

### Phase 1: Get the Pipeline Working (Week 1)

1. **Set up GBX.NET.PAK** in a C# project
2. **Obtain encryption keys**: Either from Profile.Gbx or by RE of Trackmania.exe
   (we already have Ghidra project with decompiled functions)
3. **Decrypt and list** Stadium.pak contents -- enumerate all files
4. **Extract a single block's Solid.Gbx** -- parse with GBX.NET CPlugSolid2Model
5. **Validate**: Export vertices to OBJ, view in Blender, compare to game

### Phase 2: Bulk Extraction (Week 2)

1. **Extract all block meshes** from Stadium.pak
2. **Extract all textures** (.dds files)
3. **Build a conversion pipeline**: CPlugSolid2Model -> glTF binary
4. **Validate with Ninja Ripper**: Capture a few blocks in-game, compare to extracted

### Phase 3: Browser Integration (Week 3+)

1. **Load glTF/custom binary** into the Three.js/WebGPU renderer
2. **Material mapping**: Link extracted materials to browser shader system
3. **LOD system**: Use the LOD data from CPlugSolid2Model
4. **Texture conversion**: DDS -> WebP/KTX2 for browser

### Fallback Plan

If PAK decryption keys cannot be obtained:
- Use **Openplanet Fid Explorer** to extract files while the game runs
- Use **Ninja Ripper** for visual meshes (approximate quality)
- Use **procedural geometry** for physics-only collision shapes
- Use **Blender Gbx Tools** to import any files Openplanet extracts

### What NOT To Do

- Do NOT try to reverse NadeoImporter (it is one-way by design)
- Do NOT try to brute-force PAK encryption keys (Blowfish with 16-byte key is infeasible)
- Do NOT try to read mesh data from Openplanet's AngelScript API (it only exposes
  IdName, not vertices/faces)
- Do NOT invest months in procedural generation when extraction tools already exist

---

## Approach Comparison Table

| # | Approach | Feasibility | Effort | Quality | Use For |
|---|----------|-------------|--------|---------|---------|
| 1 | GBX.NET + PAK | YES | 1-2 weeks | EXACT | **Primary extraction** |
| 2 | Openplanet Fid | MAYBE | Days | EXACT | File discovery, texture extraction |
| 3 | Blender Gbx Tools | YES | Hours | EXACT | Validation, visual inspection |
| 4 | Ninja Ripper | YES | 1-2 weeks | APPROXIMATE | Validation, fallback |
| 5 | RenderDoc | MAYBE | 1-2 weeks | APPROXIMATE | Only if Approach 1 fails |
| 6 | NadeoImporter Reverse | NO | N/A | N/A | Skip (GBX.NET IS the reverse) |
| 7 | Procedural Generation | MAYBE | Months | PLACEHOLDER | Phase 1 MVP placeholder only |

---

## Key Resources

- **GBX.NET**: https://github.com/BigBang1112/gbx-net (C# library, 400+ GBX classes)
- **GBX.NET.PAK**: NuGet package for NadeoPak decryption
- **Blender Gbx Tools**: https://github.com/BigBang1112/blender-gbx-tools
- **Nations Converter 2**: https://nc.gbx.tools/ (proof that Solid.Gbx extraction works)
- **Ninja Ripper**: https://www.ninjaripper.com/ (D3D11 mesh capture)
- **Fid Loader**: https://openplanet.dev/plugin/fidloader (Openplanet file extraction)
- **PAK Format Spec**: https://wiki.xaseco.org/wiki/PAK
- **GBX Format Spec**: https://wiki.xaseco.org/wiki/GBX
- **Trackmania Block Generator**: https://github.com/frolad/Trackmania-Blocks-Generator
- **Material Library**: NadeoImporterMaterialLib.txt (in game install directory)

---

## Files Already Available on This Machine

### Extracted by Openplanet
```
.../OpenplanetNext/Extract/GameData/Stadium/Items/     -- 35+ Item.Gbx (trees, scenery)
.../OpenplanetNext/Extract/GameData/Stadium/Media/Texture/Image/  -- DDS textures
    RoadTech_D.dds, RoadTech_N.dds, RoadTech_R.dds
    PlatformTech_D.dds
    LightCells3_D/H/N/R/L.dds
    TrackBorders_D.dds, TrackBorders_D_HueMask.dds
    Ad1x1Screen.dds
```

### Game Pack Files
```
.../Packs/Stadium.pak        -- 1.67 GB (block meshes, materials, shaders)
.../Packs/Maniaplanet.pak    -- 169 MB (core engine resources)
.../Packs/Resource.pak       -- 178 KB (minimal, has hardcoded key)
```

### User Block Files
```
.../OpenplanetNext/IX/zzz_ImportedItems/  -- Community items (fences, scenery, tents)
```

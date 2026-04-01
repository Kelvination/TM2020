# Block Mesh Extraction Research

Seven approaches exist for obtaining TM2020 block geometry for browser rendering. The recommended strategy combines GBX.NET + PAK extraction (Approach 1) for exact, authoritative geometry, with Ninja Ripper (Approach 4) for validation. Blender Gbx Tools (Approach 3) imports extracted meshes for inspection and conversion.

Pack files are encrypted with Blowfish CBC using keys derived from server-sent sub-keys. GBX.NET.PAK already implements this decryption. Once extracted, GBX.NET parses CPlugSolid2Model (Mesh.Gbx) files to obtain exact vertex positions, normals, UVs, and triangle indices. This is the only path yielding pixel-perfect geometry.

---

## GBX.NET + PAK Extraction Pipeline

This approach uses BigBang1112's GBX.NET library (C#/.NET) with the GBX.NET.PAK extension. It decrypts and decompresses Stadium.pak, extracts individual GBX files (Solid.Gbx, Mesh.Gbx, Material.Gbx), parses CPlugSolid2Model for vertices/normals/UVs/indices, and exports to a browser-friendly format.

**GBX.NET** supports 400+ GBX classes including CPlugSolid2Model with full read/write, CPlugSolid, and CPlugSurface. Repository: https://github.com/BigBang1112/gbx-net

**GBX.NET.PAK** implements NadeoPak decryption including the non-standard CBC variant with ivXor handling. It uses a different zlib solution due to specific patterns during decryption + decompression.

**Nations Converter 2** (https://nc.gbx.tools/) proves this pipeline works. It extracts direct mesh data from Solid.Gbx files and converts them into Item.Gbx files for TM2020.

The **Blender Gbx Tools** plugin (https://3d.gbx.tools/blender) imports Mesh.Gbx, Solid.Gbx, Prefab.Gbx, Shape.Gbx, and Item.Gbx with collision models and materials.

### PAK Encryption Keys

TM2020's .pak files use version 18 of the NadeoPak format (all paks show `0x00000012` at offset 0x08). Encryption uses Blowfish CBC with 16-byte keys.

For TM2020/ManiaPlanet era:
- Keys are NOT in packlist.dat (that file does not exist for ManiaPlanet+)
- Keys come from Nadeo's master server as "sub-keys" during authentication
- Sub-keys are stored in Profile.Gbx for offline use
- Two paks (ManiaPlanet.pak, Resource.pak) have sub-keys hardcoded in the executable
- Final key = md5(sub-key + additional_material)
- GBX.NET.PAK already implements this key derivation

Run the game, authenticate, then extract sub-keys from Profile.Gbx (GBX.NET can parse these), use GBX.NET.PAK's built-in key handling, or hook the decryption in Trackmania.exe via Ghidra RE.

- **Feasibility**: YES
- **Effort**: 1-2 weeks
- **Quality**: EXACT (pixel-perfect, authoritative game geometry)
- **Recommendation**: PRIMARY APPROACH

```
Stadium.pak --[GBX.NET.PAK decrypt]--> Solid.Gbx files
           --[GBX.NET parse]--> CPlugSolid2Model (vertices, indices, UVs)
           --[custom exporter]--> glTF/custom binary for browser
```

---

## Openplanet Fid Extraction

Openplanet's Fid Explorer and Pack Explorer browse and extract files directly from mounted .pak files while the game runs. The Fid Loader plugin extracts specific files by path.

Files already extracted on this machine include 35+ Item.Gbx tree/scenery items and DDS textures (RoadTech, PlatformTech, LightCells, TrackBorders).

The Openplanet API exposes `CGameCtnBlockInfo` with `VariantBaseGround` and `VariantBaseAir` properties, and `CGameCtnBlockInfoVariant` with `HelperSolidFid` and `WaypointTriggerShape`. However, **the API does NOT expose vertex/face data**. Geometry is only accessible by extracting the raw GBX files and parsing them externally.

- **Feasibility**: MAYBE (for file extraction, not direct mesh access)
- **Effort**: Days (requires game running)
- **Quality**: EXACT
- **Recommendation**: Use as supplement to discover file paths, extract individual GBX files for testing, and extract textures

---

## Blender Gbx Tools Import

BigBang1112's Blender plugin (https://3d.gbx.tools/blender) imports Mesh.Gbx, Solid.Gbx, Prefab.Gbx, Shape.Gbx, and Item.Gbx with collision models and materials. Actively maintained (v0.1.1, March 2026). Open source: https://github.com/BigBang1112/blender-gbx-tools

Cannot import directly from .pak files. You must first extract the GBX files using another method.

- **Feasibility**: YES (given extracted files)
- **Effort**: Hours
- **Quality**: EXACT
- **Recommendation**: Use for visual validation and manual inspection

---

## Ninja Ripper D3D11 Capture

Ninja Ripper (https://www.ninjaripper.com/) hooks D3D11 to capture all geometry rendered in a frame. Documented workflow on the Trackmania Wiki. Captures vertices, UVs, normals, and textures per draw call.

### LOD Problem and Workaround

Ninja Ripper captures whatever LOD is on screen. Distant blocks use low-poly LODs. The community workaround: place blocks in a map, use Mesh Modeler to convert each vanilla block to a custom item (which loses the LOD system and always renders highest quality), then capture with Ninja Ripper.

### Limitations

- No material names (textures come as separate images)
- Scene-at-a-time capture from one camera angle
- LOD artifacts without the Mesh Modeler workaround
- Manual process for each block type
- UV mapping may differ from the source (GPU-transformed)
- Normals may be in world space
- No physics/collision data

- **Feasibility**: YES
- **Effort**: 1-2 weeks (for all ~200+ block types)
- **Quality**: APPROXIMATE
- **Recommendation**: Use as validation/fallback

---

## RenderDoc Frame Capture

RenderDoc (https://renderdoc.org/) captures D3D11 frames with full pipeline state inspection. Unlike Ninja Ripper, it captures the complete pipeline state (shaders, constant buffers, render targets).

Advantages over Ninja Ripper: exact vertex shader transformations, material bindings, programmatic extraction via Python API. Same LOD problem. Must run on Windows. Frame capture may be blocked by anti-cheat.

- **Feasibility**: MAYBE
- **Effort**: 1-2 weeks
- **Quality**: APPROXIMATE (same as Ninja Ripper with more metadata)
- **Recommendation**: Investigate only if Approach 1 fails

---

## NadeoImporter Reverse Path

NadeoImporter converts FBX to Item.Gbx (one-way). No reverse tool exists. The "reverse" is GBX.NET: it has full CPlugSolid2Model read support and deserializes the exact same data NadeoImporter writes.

- **Feasibility**: NO (for NadeoImporter itself; YES via GBX.NET)
- **Recommendation**: Skip -- GBX.NET IS the reverse path

---

## Procedural Geometry Generation

Generate block geometry programmatically. TM2020 Stadium blocks use a 32x8x32 meter grid. Block types are enumerable from map files. The Trackmania Blocks Generator Blender addon has generated nearly 18k blocks.

Simple blocks (flat road, flat platform) are straightforward. Complex blocks (banked turns, slopes, deco elements, railings, barriers) have non-trivial geometry. There are 200+ block types.

- **Feasibility**: MAYBE (for physics-only; NO for visual fidelity)
- **Effort**: Months
- **Quality**: PLACEHOLDER
- **Recommendation**: Use as Phase 1 placeholder while working on the extraction pipeline

---

## Pack File Format Details

### NadeoPak v18 (TM2020)

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

### Key Packs

| Pack File | Size | Title | Likely Contents |
|-----------|------|-------|-----------------|
| Stadium.pak | 1.67 GB | TMStadium | Block meshes, materials, shaders |
| Maniaplanet.pak | 169 MB | ManiaPlanet | Core engine resources |
| Maniaplanet_Core.pak | 34 MB | ManiaPlanet | Core game data |
| Maniaplanet_ModelsSport.pak | 123 MB | -- | Player/car models |
| Skins_Stadium.pak | 264 MB | -- | Car skins |
| BlueBay.pak | 530 MB | TMStadium | BlueBay environment |
| GreenCoast.pak | 570 MB | TMStadium | GreenCoast environment |
| RedIsland.pak | 776 MB | TMStadium | RedIsland environment |
| WhiteShore.pak | 411 MB | TMStadium | WhiteShore environment |
| Resource.pak | 178 KB | -- | Minimal resource index |

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

GBX.NET supports full read/write. NadeoImporter produces Item.Gbx files embedding CPlugSolid2Model containing:
- Vertex positions (float3)
- Vertex normals (float3)
- UV coordinates (float2, up to 2 layers: BaseMaterial + Lightmap)
- Triangle indices (uint16 or uint32)
- Material references (by name, linking to the material library)
- LOD levels (multiple mesh variants at different detail levels)
- Bounding box / bounding sphere

### Material System

Materials defined in `NadeoImporterMaterialLib.txt` (1,375 lines) with 24 surface physics types, 3 UV layer patterns, complete texture naming convention (`{Name}_D.dds` diffuse, `_N.dds` normal, `_R.dds` roughness, `_H.dds` height, `_L.dds` lightmap mask). All gameplay IDs are `None` -- gameplay effects come from the block system.

---

## Recommended Strategy

### Phase 1: Get the Pipeline Working (Week 1)

1. Set up GBX.NET.PAK in a C# project
2. Obtain encryption keys from Profile.Gbx or by RE of Trackmania.exe
3. Decrypt and list Stadium.pak contents
4. Extract a single block's Solid.Gbx and parse with GBX.NET CPlugSolid2Model
5. Validate: export vertices to OBJ, view in Blender, compare to game

### Phase 2: Bulk Extraction (Week 2)

1. Extract all block meshes from Stadium.pak
2. Extract all textures (.dds files)
3. Build a conversion pipeline: CPlugSolid2Model to glTF binary
4. Validate with Ninja Ripper: capture blocks in-game, compare to extracted

### Phase 3: Browser Integration (Week 3+)

1. Load glTF/custom binary into the WebGPU renderer
2. Material mapping: link extracted materials to browser shader system
3. LOD system: use the LOD data from CPlugSolid2Model
4. Texture conversion: DDS to WebP/KTX2 for browser

### Fallback Plan

If PAK decryption keys cannot be obtained: use Openplanet Fid Explorer to extract files while the game runs, Ninja Ripper for visual meshes, procedural geometry for physics-only collision shapes, and Blender Gbx Tools for importing any Openplanet extracts.

### What NOT To Do

- Do NOT try to reverse NadeoImporter (it is one-way by design)
- Do NOT try to brute-force PAK encryption keys (Blowfish with 16-byte key is infeasible)
- Do NOT try to read mesh data from Openplanet's AngelScript API (it only exposes IdName, not vertices/faces)
- Do NOT invest months in procedural generation when extraction tools already exist

---

## Approach Comparison

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

---

## Related Pages

- [Asset Pipeline](04-asset-pipeline.md) -- Runtime asset loading and material system
- [Renderer Design](03-renderer-design.md) -- Mesh pipeline and vertex formats
- [Executive Summary](00-executive-summary.md) -- Risk assessment for block extraction

<details><summary>Document metadata</summary>

- **Date**: 2026-03-27
- **Status**: Research complete, recommended path identified

</details>

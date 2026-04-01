# Game Files Analysis

Trackmania 2020's install directory contains the executable, 12 DLLs, pack files totaling ~6.4 GB, shader caches, and configuration files. This page documents every file with reverse-engineering findings relevant to understanding the engine.

---

## DLL inventory

The game ships with 12 DLLs spanning rendering, audio, networking, advertising, modding, and voice chat.

### anzu.dll -- In-Game Advertising SDK (Anzu.io)

**Size**: 3.75 MB | **Version**: 5.41 | **Relevance**: LOW

Anzu.io renders programmatic ads on 3D surfaces within the game world (billboards, track-side screens). It dynamically fetches and renders real ad content onto in-game textures.

Key strings: `AnzuSDK_Init(`, `https://l1-1.anzu.io/`, `RenderScreen`, `placement`, `impression`, `ScriptableSDKObj.prototype.` (embedded JavaScript engine). Uses MQTT for real-time ad updates and downloads ad assets as zip packages.

No gameplay impact. A browser recreation would not need this.

### d3dcompiler_47.dll -- Microsoft D3D Shader Compiler

**Size**: 4.15 MB | **Version**: 47 | **Relevance**: HIGH

Official Microsoft Direct3D shader compiler. Compiles HLSL shaders at runtime when precompiled cache misses occur. Supports all shader stages: `PixelShader`, `VertexShader`, `GeometryShader`, `HullShader`, `DomainShader`, `ComputeShader`.

Confirms D3D11.1 feature requirements (`enable11_1ShaderExtensions`). WebGPU/WebGL2 must replicate SM5 shader functionality.

### dinput8.dll -- Openplanet Hook Loader

**Size**: 14 KB | **Relevance**: NONE

Not the real DirectInput8 DLL. This is a tiny proxy placed by Openplanet that intercepts the game's attempt to load dinput8.dll. It loads the real dinput8.dll from the system directory and also injects Openplanet.dll. Includes Wine/CrossOver detection.

### libfbxsdk.dll -- Autodesk FBX SDK (2018)

**Size**: 7.95 MB | **Build Date**: July 9, 2018 | **Relevance**: LOW

Autodesk FBX SDK for importing 3D model files. Used by NadeoImporter.exe to convert FBX models into Nadeo's internal GBX format. Key classes: `FbxScene`, `FbxNode`, `FbxMesh`, `FbxSkin`, `FbxGeometryConverter`, `FbxImporter`.

Only used for asset import pipeline, not runtime.

### libwebp64.dll -- WebP Image Codec

**Size**: 662 KB | **Relevance**: MEDIUM

Google WebP image format encoder/decoder for texture compression. Browsers natively support WebP.

### ntdll_o.dll -- Wine/CrossOver NTDLL Backup

**Size**: 672 KB | **Relevance**: NONE

Backup/original copy of Wine's `ntdll.dll`. The `_o` suffix indicates renaming by Openplanet or CrossOver during DLL hooking.

### OpenAL64_bundled.dll -- OpenAL Soft Audio Library

**Size**: 1.38 MB | **Relevance**: HIGH

OpenAL Soft provides cross-platform 3D audio. Bundled with the game for consistent audio behavior. Supports ambisonic (spatial) audio, loop points, and buffer streaming.

Web Audio API can replicate most OpenAL functionality.

### Openplanet.dll -- Openplanet Mod Framework (v1.29.1)

**Size**: 12.17 MB | **Version**: 1.29.1 (next, Public, 2026-01-31) | **Relevance**: LOW

Main Openplanet modding framework DLL. Uses AngelScript scripting, ImGui 1.92.1 WIP for overlay UI, TOML parsing, and cryptographic operations. Hook points reveal game architecture: `GamePhysics`, `Update_GameAppAsync`, `GamePhysics_Late`, `AllScripts_Before/After`.

### upc_r2_loader64.dll -- Ubisoft Connect (UPC) SDK

**Size**: 426 KB | **Relevance**: MEDIUM

Ubisoft Connect platform integration with 98 exported `UPC_*` functions covering authentication, achievements, friends, multiplayer sessions, cloud storage, overlay, store, streaming, and rich presence. UPlay App ID: 7015.

### vivoxsdk.dll -- Vivox Voice Chat SDK (v5.19.2)

**Size**: 11.87 MB | **Version**: 5.19.2 | **Relevance**: LOW

SIP-based real-time voice communication with 3D positional audio, text-to-speech, and speech-to-text. Supports multiple rolloff curves for 3D voice. Replaceable with WebRTC.

### VoiceChat.dll -- Nadeo Voice Chat Wrapper

**Size**: 1.24 MB | **Relevance**: LOW

Nadeo's wrapper around Vivox SDK using the "Harbour" framework. Default server: `https://hyxd.www.vivox.com/api2`. Configuration keys include `voicechat.vivox.server_url`, `voicechat.vivox.3d`, and language settings for TTS/STT.

### vorbis64.dll -- Ogg Vorbis Audio Codec

**Size**: 846 KB | **Version**: libVorbis 1.3.5 (2015-01-05) | **Relevance**: MEDIUM

Ogg Vorbis lossy audio codec for game audio. Browsers can decode Ogg Vorbis natively.

### DLL summary

| DLL | Size | Purpose | Relevance |
|-----|------|---------|-----------|
| `anzu.dll` | 3.75 MB | In-game advertising SDK | LOW |
| `d3dcompiler_47.dll` | 4.15 MB | D3D HLSL shader compiler | HIGH |
| `dinput8.dll` | 14 KB | Openplanet hook loader | NONE |
| `libfbxsdk.dll` | 7.95 MB | FBX 3D import SDK | LOW |
| `libwebp64.dll` | 662 KB | WebP image codec | MEDIUM |
| `ntdll_o.dll` | 672 KB | Wine ntdll backup | NONE |
| `OpenAL64_bundled.dll` | 1.38 MB | OpenAL Soft 3D audio | HIGH |
| `Openplanet.dll` | 12.17 MB | Mod framework | LOW |
| `upc_r2_loader64.dll` | 426 KB | Ubisoft Connect SDK | MEDIUM |
| `vivoxsdk.dll` | 11.87 MB | Vivox voice chat | LOW |
| `VoiceChat.dll` | 1.24 MB | Nadeo Vivox wrapper | LOW |
| `vorbis64.dll` | 846 KB | Ogg Vorbis codec | MEDIUM |

---

## NadeoImporterMaterialLib.txt -- Complete Material Database

**Size**: 32,786 bytes | **Lines**: 1,375 | **Confidence**: VERIFIED

This file defines all 208 materials available in the Stadium library. NadeoImporter matches Blender material names against this file during item import.

### Structure format

```
DLibrary(Stadium)                    -- Library declaration (only "Stadium")
DMaterial(MaterialName)              -- Material definition
    DSurfaceId  (SurfaceType)        -- Physics surface type
    DGameplayId (GameplayType)       -- Gameplay modifier type
    DUvLayer    (LayerType, index)   -- UV channel mapping
    DColor0     ()                   -- Color channel (for decals/non-lightmapped)
    DLinkFull   (Path\To\Resource)   -- External resource link for modifier materials
```

### Every gameplay ID is "None"

Every one of the 208 stock materials has `DGameplayId(None)`. Gameplay effects (turbo, reactor boost, no-grip, slow motion) come from block types, trigger zones, and the block/item model itself -- not from materials. Materials control only visual appearance, collision physics (via SurfaceId), and tire sounds.

### Surface ID enumeration

All 19 unique surface IDs and their physics behavior:

| Surface ID | Physics Behavior | Example Materials |
|------------|------------------|-------------------|
| `Asphalt` | Standard road grip | RoadTech, PlatformTech, OpenTechBorders |
| `RoadSynthetic` | Synthetic road surface | RoadBump, ScreenBack |
| `Dirt` | Loose dirt surface | RoadDirt, CustomDirt |
| `RoadIce` | Icy road surface | RoadIce, PlatformIce variants |
| `Plastic` | Plastic surface | ItemInflatableFloor, ItemObstacle, PoolBorders |
| `Rubber` | Rubber surface | TrackBorders, CustomPlastic |
| `Metal` | Metal surface | Technics, Pylon, ItemPillar2, ItemTrackBarrier |
| `ResonantMetal` | Resonant metal | TrackWallClips, Structure |
| `MetalTrans` | Transparent metal | LightSpot, Ad screens, SpecialSignTurbo |
| `Wood` | Wood surface | TrackWall, CustomRoughWood |
| `Concrete` | Concrete surface | Waterground, ItemCurveSign, CustomConcrete |
| `Grass` | Grass surface | Grass, DecoHill, DecoHill2 |
| `Green` | Green/vegetation | CustomGlass, CustomGrass |
| `Pavement` | Paved surface | CustomBricks |
| `Ice` | Pure ice surface | CustomIce |
| `Rock` | Rock surface | CustomRock |
| `Sand` | Sandy surface | CustomSand |
| `Snow` | Snowy surface | CustomSnow |
| `NotCollidable` | No collision (visual only) | All Decal*, Chrono*, GlassWaterWall |

### UV layer configurations

Three UV layer patterns exist:

| Pattern | UV0 | UV1 | Used By |
|---------|-----|-----|---------|
| **Standard Opaque** | `BaseMaterial, 0` | `Lightmap, 1` | Most solid materials |
| **Decal/Non-Lightmapped** | `BaseMaterial, 0` | `DColor0()` | All decals, glass, chrono displays |
| **Lightmap Only** | `Lightmap, 0` | -- | Grass, all Custom* materials |

### Material categories

**Roads** (4): RoadTech (Asphalt), RoadBump (RoadSynthetic), RoadDirt (Dirt), RoadIce (RoadIce)

**Platforms** (3): PlatformTech, OpenTechBorders (Asphalt), ItemInflatableFloor (Plastic)

**Track/Technics** (14): TrackBorders (Rubber), Technics/TechnicsSpecials/TechnicsTrims (Metal), Pylon (Metal), Structure (ResonantMetal), and others

**Ad Screens** (6): Ad1x1Screen through Ad2x3Screen (MetalTrans)

**Racing** (7): RaceArchCheckpoint, RaceArchFinish, SpeedometerLight_Dyna, etc.

**Chrono Digits** (20): Pattern `Chrono{Context}-{digit_position}` with contexts (none), Checkpoint, Finish. Position format: `{tens_min}-{ones_min}-{tens_sec}-{ones_sec}-{tenths}-{hundredths}-{thousandths}`. All use `SurfaceId(NotCollidable)` with `DColor0()`.

**Decoration** (4): Grass (Lightmap at UV0 only), DecoHill, DecoHill2 (Grass), GlassWaterWall (NotCollidable)

**Item Obstacles** (12): ItemPillar2, ItemTrackBarrier variants, ItemObstacle (no lightmap), ItemRamp, etc.

**Decals -- Markings** (6): DecalCurbs, DecalMarks, DecalMarksItems, DecalMarksRamp, DecalMarksStart, DecalPlatform. All NotCollidable + BaseMaterial + DColor0.

**Decals -- Sponsors** (14): DecalPaintLogo and DecalPaintSponsor variants in 4x1 and 8x1 ratios

**Special Turbo** (5): DecalSpecialTurbo, SpecialSignTurbo, SpecialFXTurbo, SpecialSignOff, TriggerFXTurbo

**Customizable** (14): Engine-provided textures using Lightmap at UV0 only. CustomBricks through CustomSnow, covering all major surface types.

**Moddable** (14): User-moddable materials with BaseMaterial + Lightmap. CustomModOpaque, CustomModColorize, CustomModSelfIllum, CustomModTrans, CustomModDecal (each with a v2 variant).

**Modifier Materials** (88 across 11 groups): Each modifier has 4-5 visual sub-materials (`_Decal`, `_Sign`, `_SignOff`, `_SpecialFX`, `_TriggerFX`) using `DLinkFull` to reference `Media\Modifier\{Name}\`.

| Modifier | Gameplay Effect |
|----------|-----------------|
| Boost / Boost2 | Speed boost |
| Cruise | Cruise control |
| Fragile | Break on contact |
| NoBrake | Disable braking |
| NoEngine | Disable engine |
| NoSteering | Disable steering |
| Reset | Reset car |
| SlowMotion | Slow motion |
| Turbo / Turbo2 | Turbo speed |
| TurboRoulette | Random turbo level |

**Platform Modifiers** (28 materials across 4 groups): PlatformDirt, PlatformGrass, PlatformIce, PlatformPlastic. Each overrides the platform's surface and decoration materials.

---

## Pack files

### NadeoPak format

All `.pak` files use NadeoPak v18 format:

```
Offset  Size  Description
0x00    8     Magic: "NadeoPak" (ASCII)
0x08    4     Version: 0x00000012 (18)
0x0C    32    SHA-256 checksum
0x2C    4     Flags/type field
0x30    4     Offset/alignment field (0x3000 or 0x4000)
0x40    varies String table begins
```

**Confidence**: PLAUSIBLE (from hex analysis, no decompiled parser available)

### Pack inventory

| Pack File | Size | Description |
|-----------|------|-------------|
| Stadium.pak | 1.63 GB | Main stadium environment |
| Skins_StadiumPrestige.pak | 959 MB | Prestige car skins |
| RedIsland.pak | 776 MB | Red Island theme |
| Trackmania.Title.Pack.Gbx | 744 MB | Title pack (NadeoPak in GBX container) |
| GreenCoast.pak | 569 MB | Green Coast theme |
| BlueBay.pak | 530 MB | Blue Bay theme |
| WhiteShore.pak | 411 MB | White Shore theme |
| Skins_Stadium.pak | 264 MB | Stadium car skins |
| Maniaplanet_Skins.zip | 221 MB | Cross-game skin assets |
| Maniaplanet.pak | 169 MB | Core ManiaPlanet engine assets |
| Maniaplanet_ModelsSport.pak | 123 MB | Sport car models |
| Maniaplanet_Core.pak | 33.7 MB | Core engine resources |
| GpuCache_D3D11_SM5.zip | 16.2 MB | Precompiled D3D11 SM5 shaders |
| Other zips | ~16 MB | Flags, Painter, Translations, Extras, Live, Skins |

**Total**: ~6.4 GB

### Environment themes

Four distinct themes exist: GreenCoast (569 MB), BlueBay (530 MB), RedIsland (776 MB), WhiteShore (411 MB).

### ZIP contents

- **Maniaplanet_Extras.zip**: Effect textures, ~50+ color grading LUT presets
- **Maniaplanet_Flags.zip**: Thousands of country/region flag images
- **Maniaplanet_Live.zip**: ManiaScript scripts for Auth, NadeoFunctions, browser, chat, notifications
- **Maniaplanet_Painter.zip**: Brush stencils for the skin painting tool
- **Maniaplanet_Skins.zip**: Advertisement screen skins (.webm, .dds, .tga)
- **Stadium_Skins.zip**: Canopy glass textures, seasonal flag skins. Texture channels: `_D` (diffuse), `_N` (normal), `_R` (roughness), `_D_HueMask` (color customization)
- **Translations.zip**: 14 languages via gettext `.mo` files

---

## GPU Performance Database (GfxDevicePerfs.txt)

**Size**: 82,909 bytes | **Entries**: 1,049 GPUs | **Confidence**: VERIFIED

The game auto-selects graphics quality based on pre-benchmarked GPU performance scores.

### Format

```
Vendor Device GVertexMath GPixelMath GOutputBytes GAniso1 GAniso2 GAniso4 GAniso8 GAniso16
```

| Column | Description |
|--------|-------------|
| Vendor | PCI Vendor ID (hex) |
| Device | PCI Device ID (hex) |
| GVertexMath | Vertex shader throughput score |
| GPixelMath | Pixel shader throughput score |
| GOutputBytes | Render output bandwidth score |
| GAniso1-16 | Anisotropic filtering fill rate at 1x through 16x |

### Vendor distribution

| PCI Vendor | Vendor | GPUs |
|------------|--------|------|
| `10DE` | NVIDIA | 621 |
| `1002` | AMD/ATI | 334 |
| `8086` | Intel | 92 |
| `15AD` | VMware | 1 |
| `1AB8` | [UNKNOWN] | 1 |

Coverage spans from ATI Radeon 9500 (circa 2002) to AMD RX 7900 series and NVIDIA RTX 40-series.

---

## Openplanet directory

Openplanet bundles fonts (DroidSans, Montserrat, Oswald, ManiaIcons), 13 plugins (Camera, EditorDeveloper, VehicleState, etc.), core AngelScript files with `.sig` digital signatures, an ImGui theme (`DefaultStyle.toml`), and a CA certificate bundle. Scripts include `Compatibility.as`, `Dialogs.as`, `Patch.as`, and `Plugin_MapAudioFix.as`.

---

## DXVK / D3D11 log analysis

**Confidence**: VERIFIED

### Runtime environment

- **DXVK**: cxaddon-1.10.3-1-25-g737aacd (CrossOver custom build)
- **D3D Feature Level**: D3D_FEATURE_LEVEL_11_0
- **GPU**: Apple M4 via Vulkan/MoltenVK

### Required GPU features

The game requires geometry shaders, tessellation, compute shaders, sample-rate shading, dual-source blending, multi-draw indirect, depth clamping, anisotropic filtering, BC texture compression, occlusion queries, transform feedback, and custom clip/cull distances.

### Vertex formats

Four vertex formats were identified from pipeline compilation data:

| Format | Stride | Components |
|--------|--------|------------|
| A | 28 bytes | Position (vec3), Normal (snorm16x4), UV0 (vec2) |
| B | 44 bytes | + Tangent (snorm16x4), Binormal (snorm16x4) |
| C | 52 bytes | + UV1/Lightmap (vec2) |
| D | 56 bytes | + VertexColor (B8G8R8A8_UNORM) |

### Swap chain

- **Format**: B8G8R8A8_SRGB (sRGB backbuffer)
- **Present**: Immediate (no vsync, uncapped FPS)
- **Buffering**: Triple buffered
- **Depth**: D24_UNORM_S8_UINT (mapped to D32_SFLOAT_S8_UINT by DXVK)

---

## NadeoImporter.exe -- Asset Pipeline

**Size**: 8.27 MB | **Build**: July 12, 2022 | **Version**: Tm2020 | **Confidence**: VERIFIED

### Supported file formats

| Extension | Purpose |
|-----------|---------|
| `.fbx` | Source 3D model |
| `.tga` / `.dds` | Source / compiled textures |
| `.Item.gbx` | Compiled item definition |
| `.Mesh.gbx` / `.Shape.gbx` | Compiled mesh / collision shape |
| `.Material.gbx` / `.Material.txt` | Material definition |
| `.Skel.gbx` / `.Rig.gbx` / `.Anim.gbx` | Skeleton / rig / animation |
| `.MeshParams.xml` / `.Item.xml` | Import parameters |
| `.Reduction40.Gbx` / `.Remesh.Gbx` / `.Impostor.Gbx` | LOD variants |

### Mesh processing pipeline

1. FBX import via `FbxImporter` (libfbxsdk.dll)
2. Geometry conversion: `FbxGeometryConverter`
3. Material mapping against `NadeoImporterMaterialLib.txt`
4. Collision shape generation: `CCrystal::ArchiveCrystal`
5. LOD generation: Reduction40, ReductionRetextured, Remesh, Impostor
6. Lightmap UV validation: `"Mesh has no LM UVs => abort"` (will fail if missing)
7. GBX output: Solid1/Solid2 format

### Command-line options

- `/LogMeshStats` -- Log mesh statistics during import
- `/MaterialList` -- List available materials
- `/MeshSkipPrefix` -- Skip mesh prefix during processing

### Block waypoint types

Strings confirm four types: `Start`, `Finish`, `Checkpoint`, `Start/Finish` (multilap).

---

## Update system (updater_files.txt)

XML-based updater with SHA-256 checksums. Version: 2026-01-10. Four file groups: ManiaPlanet (core), Titles, Common, TMStadium.

File attributes: `dontinstall="1"` (GpuCache), `level="CanBeNewer"`, `optional="1"` (Translations), `forcenorestart="1"`.

Steam App IDs in the updater (legacy ManiaPlanet-era): Main=232910, Demo=233070. The actual TM2020 Steam App ID is **2225070**.

---

## Configuration (Nadeo.ini)

```ini
[Trackmania]
WindowTitle=Trackmania
Updater=Steam
Distro=AZURO
UPlayAppId=7015
UserDir={userdocs}\Trackmania
CommonDir={commondata}\Trackmania
```

"AZURO" is the internal codename for the TM2020 distribution.

---

## Shader system (GpuCache)

**Source**: `GpuCache_D3D11_SM5.zip` | **Files**: 1,113 compiled shaders | **Format**: `.hlsl.GpuCache.Gbx`

### Shader categories

| Category | Description |
|----------|-------------|
| Bench/ | GPU benchmarking (Anisotropy, Geometry, PixelArithmetic) |
| Clouds/ | Volumetric clouds, god rays, edge lighting |
| Effects/ | Post-processing, particles, fog, SDF, subsurface, TAA |
| Effects/PostFx/HBAO_plus | NVIDIA HBAO+ ambient occlusion |
| Engines/ | Core rendering, normal map baking |
| Garage/ | Car viewer shaders |
| Lightmap/ | Lightmap baking/rendering |
| Sky/ | Sky dome and atmospheric scattering |
| Tech3/ / Techno3/ | Material system (grass, trees) |
| ShadowCache/ | Shadow map caching |

### Shader stage naming

`_v` = Vertex, `_p` = Pixel, `_g` = Geometry, `_c` = Compute, `_h` = Hull, `_d` = Domain

### Rendering pipeline order

Shadow Pass -> Lightmap -> Main Geometry (Tech3/Techno3) -> Sky/Atmosphere -> Clouds -> Particles -> Post-Processing (TAA, HBAO+, tone mapping) -> Effects -> UI -> Special (Garage, Painter)

---

## Key findings for browser recreation

### Graphics

- **Target**: D3D11.0 feature level, Shader Model 5.0
- **WebGPU**: Fully achievable for compute shaders, geometry processing, and required texture formats
- **Render target**: B8G8R8A8_SRGB with D24_UNORM_S8_UINT depth
- **Key features**: Geometry shaders, tessellation, compute shaders, BC texture compression, anisotropic filtering

### Vertex buffers

Four vertex formats (28-56 bytes) using vec3 position, snorm16x4 normals, vec2 UVs, optional tangent frame and vertex color.

### Materials

19 unique surface types control physics. All gameplay IDs are "None" in the material library. Skin textures use `_D` (diffuse), `_N` (normal), `_R` (roughness), `_D_HueMask` (color customization).

### Audio

OpenAL Soft with ambisonic support. Ogg Vorbis 1.3.5 codec. Web Audio API can replicate this.

### Network/Platform

Ubisoft Connect (UPC SDK) ticket-based auth. Vivox voice chat (replaceable with WebRTC). Custom XML updater with SHA-256 checksums.

### Assets

FBX source -> GBX runtime format. NadeoPak v18 archives. LOD system: full mesh, Reduction40, Remesh, Impostor. Texture formats: DDS (BC compressed), TGA, WebP, PNG.

### Localization

14 languages: cs-CZ, de-DE, en-US, es-ES, fr-FR, it-IT, ja-JP, ko-KR, nl-NL, pl-PL, pt-BR, ru-RU, tr-TR, zh-CN

---

## Related Pages

- [06-file-formats.md](06-file-formats.md) -- GBX file format details
- [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) -- Deep dive into GBX parsing
- [27-dll-intelligence.md](27-dll-intelligence.md) -- Extended DLL analysis
- [26-real-file-analysis.md](26-real-file-analysis.md) -- Additional file analysis
- [32-shader-catalog.md](32-shader-catalog.md) -- Complete shader catalog
- [13-subsystem-class-map.md](13-subsystem-class-map.md) -- Material reference and class mapping

<details><summary>Analysis metadata</summary>

**Install Path**: `/Users/kelvinnewton/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Trackmania/`
**Analysis Date**: 2026-03-27

</details>

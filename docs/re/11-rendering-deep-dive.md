# Trackmania 2020 Rendering Deep Dive

**Binary**: `Trackmania.exe` (Trackmania 2020)
**Date of analysis**: 2026-03-27
**Sources**: Decompiled functions (`decompiled/rendering/`), RTTI class hierarchy (`class_hierarchy.json`), D3D11 runtime log, string references, Openplanet plugin intelligence
**Purpose**: Exhaustive rendering pipeline documentation for WebGPU recreation

---

## Table of Contents

1. [Frame Anatomy: One Complete Frame](#1-frame-anatomy-one-complete-frame)
2. [D3D11 Device Requirements](#2-d3d11-device-requirements)
3. [G-Buffer Layout](#3-g-buffer-layout)
4. [Deferred Rendering Pipeline](#4-deferred-rendering-pipeline)
5. [Shadow System](#5-shadow-system)
6. [HBAO+ Configuration](#6-hbao-configuration)
7. [Shader System](#7-shader-system)
8. [Shader Buffer Taxonomy](#8-shader-buffer-taxonomy)
9. [Post-Processing Pipeline](#9-post-processing-pipeline)
10. [Material and PBR System](#10-material-and-pbr-system)
11. [TXAA Implementation](#11-txaa-implementation)
12. [Particle System](#12-particle-system)
13. [Water, Fog, and Special Effects](#13-water-fog-and-special-effects)
14. [LOD and Culling System](#14-lod-and-culling-system)
15. [Minimum GPU Specification](#15-minimum-gpu-specification)
16. [WebGPU Translation Guide](#16-webgpu-translation-guide)
17. [Minimum Viable Renderer Specification](#17-minimum-viable-renderer-specification)

---

## 1. Frame Anatomy: One Complete Frame

This section walks through the exact sequence of operations that produce a single rendered frame, from CPU setup through GPU submission to final present. Every pass name is a verified string reference from the binary.

### ASCII Pipeline Overview

```
 CPU WORK                          GPU WORK
 --------                          --------
 Input polling
 Physics tick (100 Hz)
 Scene graph update
 Visibility determination
         |
         v
 Upload per-frame constants -----> SetCst_Frame
                                     |
                                     v
                            +------------------+
                            | SHADOW PREP      |
                            | ShadowCreateVol  |
                            | ShadowRenderCast |
                            | ShadowRenderPSSM |   (4 cascade passes)
                            | ShadowCacheUpdate|
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | SCENE PREP       |
                            | CreateProjectors |
                            | ParticlesUpdate  |   (compute shader)
                            | CubeReflect      |
                            | WaterReflect     |
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | G-BUFFER FILL    |
                            | DipCulling       |   (compute: frustum cull + LOD)
                            | DeferredWrite    |   (MRT: MDiffuse, MSpecular,
                            | DeferredWriteFN  |    PixelNormalInC, LightMask)
                            | DeferredWriteVN  |   (FaceNormalInC, VertexNormalInC)
                            | DeferredDecals   |
                            | DeferredBurn     |
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | SCREEN-SPACE     |
                            | DeferredShadow   |   (sample PSSM cascades)
                            | DeferredAmbientOc|   (HBAO+ dual pass)
                            | DeferredFakeOcc  |
                            | CameraMotion     |   (motion vectors)
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | DEFERRED LIGHT   |
                            | DeferredRead     |   (ambient + Fresnel)
                            | DeferredReadFull |   (lightmap + indirect)
                            | DeferredLighting |   (point/spot/area lights)
                            | SSLReflects      |   (screen-space reflections)
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | FORWARD PASS     |
                            | ForestRender     |   (alpha-to-coverage)
                            | GrassRender      |
                            | AlphaBlend       |   (transparent objects)
                            | ParticlesRender  |
                            | GhostLayer       |   (ghost car overlay)
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | POST-PROCESSING  |
                            | DeferredFogVol   |   (volumetric fog boxes)
                            | DeferredFog      |   (global fog)
                            | LensFlares       |
                            | FxDepthOfField   |
                            | FxMotionBlur     |
                            | FxToneMap        |   (auto-exposure + filmic curve)
                            | FxBloom          |   (HDR bloom + streaks)
                            | FxFXAA / FxTXAA  |   (anti-aliasing)
                            | FxColorGrading   |
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | FINAL OUTPUT     |
                            | Overlays / GUI   |
                            | StretchRect      |
                            | SwapChainPresent |
                            +------------------+
```

### Phase-by-Phase Walkthrough

#### Phase 0: CPU Frame Setup (before GPU submission)

The CPU performs these tasks before any GPU work begins:

1. **Input polling**: `CInputPort::Update_StartFrame` at `0x1402acea0` reads input event queue, processes device connectivity (150ms timeout), clears events.
2. **Physics simulation**: Up to 100 physics resim steps per frame (`SmMaxPlayerResimStepPerFrame = 100` from `Default.json`), running at 100 Hz tick rate.
3. **Scene graph update**: The `CHmsZone`/`CHmsZoneElem` hierarchy updates transforms. Dynamic instances managed by `NHmsMgrInstDyna::AsyncRender_ApplyDeferredChanges`.
4. **Visibility determination**: Per-zone visible set computed. The zone element array at `param_1 + 0x1a98` with count at `param_1 + 0x1aa0` (from `CVisionViewport::VisibleZonePrepareShadowAndProjectors` at `0x14095d430`).

**Data flow**: CPU writes per-frame constant buffers (camera matrices, time, sun direction) into mapped D3D11 buffers. These are consumed by `SetCst_Frame` on GPU.

**Confidence**: VERIFIED (decompiled functions, config values)

#### Phase 1: Frame Constants and Shadow Prep (GPU begins)

```
SetCst_Frame -> SetCst_Zone -> GenAutoMipMap
  -> ShadowCreateVolumes -> ShadowRenderCaster -> ShadowRenderPSSM -> ShadowCacheUpdate
```

**CPU/GPU boundary**: `SetCst_Frame` is the first GPU pass. It uploads:
- Camera view/projection matrices
- Frame time, delta time
- Sun/light direction and color
- Wind parameters for vegetation

Shadow maps are rendered to dedicated depth textures. The PSSM system renders 4 cascades (see Section 5). Static shadow maps are cached (`ShadowCacheUpdate`) and only re-rendered when geometry changes.

**Confidence**: VERIFIED (pass names from binary strings, shadow decompilation)

#### Phase 2: Scene Preparation

```
CreateProjectors -> UpdateTexture -> Decal3dDiscard
  -> ParticlesUpdateEmitters -> ParticlesUpdate
  -> CubeReflect -> LightFromMap -> WaterReflect
```

- **ParticlesUpdate**: GPU compute shader (`MgrParticleUpdate_c.hlsl`) updates all particle positions/velocities in storage buffers.
- **CubeReflect**: Renders a 6-face cubemap for dynamic reflections.
- **WaterReflect**: Renders planar reflection for water surfaces.
- **LightFromMap**: Samples baked lightmaps to apply environment lighting to dynamic objects (cars).

**Confidence**: VERIFIED

#### Phase 3: G-Buffer Fill (Deferred Write)

```
DipCulling -> DeferredWrite -> DeferredWriteFNormal -> DeferredWriteVNormal
  -> DeferredDecals -> DeferredBurn
```

This is where the core geometry rendering happens. `DipCulling` runs a compute shader (`Instances_Cull_SetLOD_c.hlsl`) that performs GPU-side frustum culling and LOD selection, writing indirect draw arguments.

The `DeferredWrite` pass renders all opaque geometry into the G-buffer MRT:
- **Blocks/terrain**: `Block_TDSN_DefWrite_p.hlsl` (Texture+Diffuse+Specular+Normal)
- **Cars**: `CarSkin_DefWrite_p.hlsl`
- **Trees**: `Tree_SelfAO_DefWrite_p.hlsl`

Normals are written in separate sub-passes:
- `DeferredWriteFNormal`: Face normals (geometric flat normals), possibly reconstructed from depth via `DeferredFaceNormalFromDepth_p.hlsl`
- `DeferredWriteVNormal`: Vertex normals (smooth interpolated normals)

Then `DeferredDecals` projects decals onto the G-buffer using `DeferredDecalGeom_p.hlsl` (box projection) and `DeferredBurn` applies scorch/tire marks via `DeferredGeomBurnSphere_p.hlsl`.

**Data flow out**: 9 named G-buffer targets filled (see Section 3).

**Confidence**: VERIFIED (shader names, pass ordering)

#### Phase 4: Screen-Space Passes

```
DeferredShadow -> DeferredAmbientOcc -> DeferredFakeOcc -> CameraMotion
```

These passes read from the G-buffer and produce screen-space data:

- **DeferredShadow**: Samples the 4 PSSM cascade shadow maps using `DeferredShadowPssm_p.hlsl`. Outputs a shadow term per pixel.
- **DeferredAmbientOcc**: Runs NVIDIA HBAO+ (or Nadeo's custom `UseHomeMadeHBAO`) in a 6-step pipeline (linearize depth, deinterleave, compute AO, reinterleave, bilateral blur). May run twice (small-scale + big-scale) for dual-range AO.
- **DeferredFakeOcc**: Applies cheap approximate occlusion for distant objects via `DeferredGeomFakeOcc_p.hlsl`.
- **CameraMotion**: Computes per-pixel motion vectors via `DeferredCameraMotion_p.hlsl`. Used by TXAA and motion blur.

**Confidence**: VERIFIED

#### Phase 5: Deferred Lighting

```
DeferredRead -> DeferredReadFull -> DeferredLighting -> Reflects_CullObjects
```

The lighting accumulation phase reads the full G-buffer and produces the lit HDR scene:

1. **DeferredRead** runs these shaders in sequence:
   - `Deferred_SetILightDir_p.hlsl` -- Set indirect light direction from lightmap/probe data
   - `Deferred_AddAmbient_Fresnel_p.hlsl` -- Add ambient term with Fresnel reflection at grazing angles
   - `Deferred_AddLightLm_p.hlsl` -- Add baked lightmap contribution
   - `Deferred_SetLDirFromMask_p.hlsl` -- Derive light direction from the LightMask buffer

2. **DeferredReadFull** completes the ambient/indirect lighting.

3. **DeferredLighting** renders light geometry (stencil-marked light volumes):
   - `DeferredGeomLightBall_p.hlsl` -- Point lights (sphere proxy geometry)
   - `DeferredGeomLightSpot_p.hlsl` -- Spot lights (cone proxy geometry)
   - `DeferredGeomLightFxSphere_p.hlsl` -- Decorative sphere lights
   - `DeferredGeomLightFxCylinder_p.hlsl` -- Decorative cylinder lights
   - `DeferredGeomProjector_p.hlsl` -- Projected texture lights

**Data flow out**: HDR color buffer with full lighting.

**Confidence**: VERIFIED

#### Phase 6: Screen-Space Reflections

```
SSLReflects -> SSLReflects_GlobalCube -> SSLReflects_Add
```

- `SSReflect_Deferred_p.hlsl` traces rays in screen space using the depth buffer.
- `SSReflect_Deferred_LastFrames_p.hlsl` uses temporal reprojection from previous frames to fill SSR gaps.
- Misses fall back to the global cubemap (`SSLReflects_GlobalCube`).
- Results are composited onto the scene (`SSLReflects_Add`).

**Confidence**: VERIFIED

#### Phase 7: Forward/Transparent Pass

```
ForestRender -> GrassRender -> ShadowRender
  -> Alpha01 -> AlphaBlend -> AlphaBlendSoap -> BufferRefract
  -> GhostLayer -> GhostLayerBlend
```

Objects that cannot be deferred-rendered are drawn here:
- **Trees/Forests**: Alpha-to-coverage MSAA for leaf edges (`ForestRender_MSAA`)
- **Grass**: Instanced grass blades (`GrassUpdateInstances` -> `GrassRender`)
- **Alpha-tested geometry**: `Alpha01` pass for cutout materials
- **Transparent objects**: `AlphaBlend` pass, sorted back-to-front
- **Ghost cars**: Rendered to a separate layer then blended with configurable opacity
- **Refraction**: `BufferRefract` captures the scene for refractive objects

**Confidence**: VERIFIED

#### Phase 8: Particle Rendering

```
ParticleSelfShadow_ComputeBBoxes -> ... -> ParticleSelfShadow_Propagation
VortexParticle -> VortexParticle_UpScale
ParticlesRender -> ParticlesRenderRefract -> ParticlesRender_UpScale
```

Particles are rendered after the main scene. Self-shadowing uses a voxelization pipeline (geometry shader writes to 3D volume, then propagates shadow). Particles may be rendered at reduced resolution and upscaled (`ParticlesRender_UpScale`).

**Confidence**: VERIFIED

#### Phase 9: Post-Processing Chain

```
DeferredFogVolumes -> DeferredFog -> LensFlares
  -> FxDepthOfField -> FxMotionBlur -> FxBlur
    -> FxToneMap -> FxBloom
      -> FxFXAA / FxTXAA
        -> FxColors -> FxColorGrading
          -> Overlays -> GUI -> StretchRect -> SwapChainPresent
```

The exact order matters. Key observations:
- **Fog before DoF**: Fog contributes to the scene before any camera effects
- **Tone mapping before bloom**: Scene is tonemapped first, then bloom is extracted from bright areas [NEEDS INVESTIGATION -- could also be bloom-before-tonemap]
- **AA after tone mapping**: FXAA/TXAA operates on the tonemapped LDR/HDR result
- **Color grading last**: LUT-based color grading is the final image adjustment

**Confidence**: VERIFIED (pass ordering from dependency chain strings)

#### Phase 10: Final Output

```
ResolveMsaaHdr -> ResolveMsaa -> StretchRect -> BlurAA -> DownSSAA -> SwapChainPresent
```

If MSAA was used (forward path only), it resolves here. The final image is stretched/scaled to the back buffer and presented. Triple buffering is used (3 back buffers, confirmed from D3D11 log: `Image count: 3`).

**Confidence**: VERIFIED

---

## 2. D3D11 Device Requirements

### Feature Level Negotiation

**Source**: `CDx11Viewport::DeviceCreate` at `0x1409aa750`

The device creation function negotiates D3D feature levels with a tiered fallback system. Key evidence from the decompiled code:

```c
// At 0x1409aa936 - D3D11CreateDevice called with flags
FUN_1422c7c04(lVar13, 0, 0, 0x20);  // 0x20 = D3D11_CREATE_DEVICE_BGRA_SUPPORT
```
**Confidence**: VERIFIED (address `0x1409aa750`, string `"CDx11Viewport::DeviceCreate"` at line 74)

**Feature Level Tiers**:

| Feature Level | Hex Value | Shader Model | Evidence |
|--------------|-----------|-------------|----------|
| D3D11.1 | `0xb001` | SM 5.0+ | `0xafff < (int)*puVar2` check at line 303, sets `DAT_14201d2ec = 0x500` |
| D3D11.0 | `0xb000` | SM 5.0 | `(int)*puVar2 < 0xb000` at line 329 |
| D3D10.1 | `0xa100` | SM 4.1 | `(int)*puVar2 < 0xa100` at line 330-331 |
| D3D10.0 | `0xa000` | SM 4.0 | Minimum, sets `DAT_14201d2ec = 0x400` at line 300 |

**Confidence**: VERIFIED (feature level constants match D3D_FEATURE_LEVEL_* enum values)

**Shader Model Selection** (address `0x1409aad00` area):
```c
DAT_14201d2ec = 0x400;  // SM 4.0 default
if (0xafff < (int)*puVar2) {
    DAT_14201d2ec = 0x500;  // SM 5.0 if feature level >= 11.0
}
```
**Confidence**: VERIFIED

### MSAA Sample Count Detection

The device queries MSAA support and stores a bitmask of supported sample counts:

```c
// At 0x1409aaf40 - MSAA enumeration loop
// Iterates power-of-2 sample counts: 1, 2, 4, 8
uVar14 = uVar14 << 1 | (uint)((int)uVar14 < 0);
*(uint *)(uVar22 + *(longlong *)(param_1 + 0x459)) = uVar15;
```

The sample count array stores entries for each power of 2. The string `"%d samples"` (line 434) is used for sample counts that pass validation; `"N/A"` (`DAT_141b58e78`, line 423) for those that fail.

**Confidence**: VERIFIED (loop structure + string references)

**WebGPU**: WebGPU supports `sampleCount` of 1 or 4 only. For deferred rendering, MSAA is not used -- the engine uses FXAA/TXAA instead.

### D3D11.1 Optional Features Query

For feature level >= 11.1, the code queries `D3D11_FEATURE_D3D11_OPTIONS`:
```c
// At 0x1409aae22 - CheckFeatureSupport for D3D11_OPTIONS
(**(code **)(**(longlong **)(param_1 + 0x3fe9) + 0xf0))
    (*(longlong **)(param_1 + 0x3fe9), 0x13, 8, &local_4148);
// 0x13 = D3D11_FEATURE_D3D11_OPTIONS (value 19)
```

**Confidence**: VERIFIED (vtable offset `0xf0` matches `ID3D11Device::CheckFeatureSupport`, parameter `0x13` matches enum)

### Compute Shader Tier Detection

```c
// At 0x1409aac6e-0x1409aac73
if ((int)(*puVar2 & 0xfffff000) < 0xa001) {
    // Feature level < 10.1: query for D3D11_FEATURE_D3D10_X_HARDWARE_OPTIONS
    (**(code **)(*plVar1 + 0x108))(plVar1, 4, &local_4148);
    DAT_142057fd9 = (int)local_4148 != 0 | DAT_142057fd9 & 0xfe;
} else {
    DAT_142057fd9 = DAT_142057fd9 | 1;  // CS+ guaranteed at FL 10.1+
}
```

**Confidence**: VERIFIED (value 4 = `D3D11_FEATURE_D3D10_X_HARDWARE_OPTIONS`)

### Intel GPU Detection

The code checks for Intel vendor ID `0x8086` and applies a driver version threshold:
```c
// At 0x1409aaa68
if (((DAT_142057f98 != 0) && (DAT_142057f90 == 0x8086))
    && (DAT_142057f98 < 0xa0012000a1106)) {
    // Intel GPU with driver version below threshold
    // Applies workarounds / logs warning
}
```

**Confidence**: VERIFIED (`0x8086` is the Intel PCI vendor ID)

### Swap Chain Configuration

**Source**: D3D11 runtime log (`Trackmania_d3d11.log`)

| Property | Value | Evidence |
|----------|-------|----------|
| Back buffer format | `DXGI_FORMAT_B8G8R8A8_UNORM_SRGB` | Log: `VK_FORMAT_B8G8R8A8_SRGB` (DXVK translation) |
| Present mode | Immediate (no VSync) | Log: `VK_PRESENT_MODE_IMMEDIATE_KHR` |
| Buffer count | 3 (triple buffering) | Log: `Image count: 3` |
| Depth/Stencil format | `DXGI_FORMAT_D24_UNORM_S8_UINT` | Log: `VK_FORMAT_D24_UNORM_S8_UINT -> VK_FORMAT_D32_SFLOAT_S8_UINT` |
| Refresh rate | 120 Hz | Log: `1512x982@120` |

**Confidence**: VERIFIED (runtime log from actual execution via DXVK/CrossOver)

### Vertex Format Evidence

The D3D11 log captures actual vertex attribute layouts:

**Block Geometry with Vertex Color (stride 56, 7 attributes)**:
```
attr 0: R32G32B32_SFLOAT    offset 0   (position, 12 bytes)
attr 1: R16G16B16A16_SNORM  offset 12  (normal, packed, 8 bytes)
attr 2: B8G8R8A8_UNORM      offset 20  (vertex color, 4 bytes)
attr 3: R32G32_SFLOAT        offset 24  (UV0, 8 bytes)
attr 4: R32G32_SFLOAT        offset 32  (UV1 / lightmap UV, 8 bytes)
attr 5: R16G16B16A16_SNORM  offset 40  (tangent, 8 bytes)
attr 6: R16G16B16A16_SNORM  offset 48  (bitangent/binormal, 8 bytes)
Total: 12+8+4+8+8+8+8 = 56 bytes
```

**Lightmapped Geometry (stride 52, 6 attributes)**:
```
attr 0: R32G32B32_SFLOAT    offset 0   (position)
attr 1: R16G16B16A16_SNORM  offset 12  (normal)
attr 2: R32G32_SFLOAT        offset 20  (UV0)
attr 3: R32G32_SFLOAT        offset 28  (UV1 / lightmap)
attr 4: R16G16B16A16_SNORM  offset 36  (tangent)
attr 5: R16G16B16A16_SNORM  offset 44  (bitangent)
```

**Simple Geometry (stride 28, 3 attributes)**:
```
attr 0: R32G32B32_SFLOAT    offset 0   (position)
attr 1: R16G16B16A16_SNORM  offset 12  (normal)
attr 2: R32G32_SFLOAT        offset 20  (UV)
```

**Confidence**: VERIFIED (captured from DXVK pipeline compilation in runtime log)

---

## 3. G-Buffer Layout

### Complete G-Buffer Channel Table

The engine uses 9 named render targets. Not all are bound simultaneously as MRT outputs -- the core MRT during `DeferredWrite` is 4 targets + depth. Additional targets are written in separate sub-passes.

```
G-BUFFER MEMORY LAYOUT
===========================================================================================
 Target              | Channels      | Likely Format            | Written In         | Read By
===========================================================================================
 MDiffuse            | RGB: albedo   | R8G8B8A8_UNORM_SRGB     | DeferredWrite      | DeferredRead
 (RT0)               | A: [UNKNOWN]  | [PLAUSIBLE]              |                    | DeferredLighting
-------------------------------------------------------------------------------------------
 MSpecular           | RGB: F0       | R8G8B8A8_UNORM           | DeferredWrite      | DeferredRead
 (RT1)               | A: roughness  | [PLAUSIBLE]              |                    | DeferredLighting
                     |    or gloss   |                          |                    |
-------------------------------------------------------------------------------------------
 PixelNormalInC      | RG: normal XY | R16G16B16A16_FLOAT       | DeferredWrite      | DeferredLighting
 (RT2)               | B: normal Z   | or R10G10B10A2_UNORM     |                    | SSLReflects
                     | A: [UNKNOWN]  | [SPECULATIVE]            |                    | HBAO+
-------------------------------------------------------------------------------------------
 LightMask           | RGBA: flags   | R8G8B8A8_UNORM           | DeferredWrite      | DeferredRead
 (RT3)               | per-channel   | [SPECULATIVE]            |                    | SetLDirFromMask
                     | light flags   |                          |                    |
-------------------------------------------------------------------------------------------
 DeferredZ           | D24S8         | D24_UNORM_S8_UINT        | DeferredWrite      | All screen-space
 (Depth)             |               | [VERIFIED from D3D11 log]|                    | passes
===========================================================================================

 ADDITIONAL TARGETS (written in separate sub-passes, not MRT-simultaneous with above)
===========================================================================================
 FaceNormalInC       | RG: flat      | R16G16_FLOAT             | DeferredWriteFN    | HBAO+, FXAA
                     | normal XY     | or R8G8_SNORM            | (or reconstructed  | edge detection,
                     |               | [SPECULATIVE]            |  from depth)       | shadow bias
-------------------------------------------------------------------------------------------
 VertexNormalInC     | RG: smooth    | R16G16_FLOAT             | DeferredWriteVN    | Bilateral blur
                     | normal XY     | or R8G8_SNORM            |                    | SSS direction
                     |               | [SPECULATIVE]            |                    |
-------------------------------------------------------------------------------------------
 PreShade            | [UNKNOWN]     | [UNKNOWN]                | [UNKNOWN]          | [UNKNOWN]
                     | Possibly pre- |                          | Possibly during    | Possibly during
                     | computed BRDF |                          | DeferredRead       | lighting
                     | response      |                          |                    |
-------------------------------------------------------------------------------------------
 DiffuseAmbient      | RGB: diffuse  | R16G16B16A16_FLOAT       | DeferredRead       | Forward pass
                     | + ambient     | or R11G11B10_FLOAT       | DeferredReadFull   | compositing
                     | A: [UNKNOWN]  | [SPECULATIVE]            |                    |
===========================================================================================
```

### Why Three Normal Buffers?

The presence of THREE separate normal buffers (face, vertex, pixel) is unusual but has clear purpose:

1. **PixelNormalInC** -- Final bump-mapped normal in camera space. This is the primary normal used for lighting calculations. Written during `DeferredWrite` from tangent-space normal maps transformed to camera space.

2. **FaceNormalInC** -- Geometric (flat) face normal. Uses:
   - **HBAO+**: Geometric normals give more stable AO than bump-mapped normals
   - **FXAA/TXAA edge detection**: Geometric discontinuities indicate silhouette edges
   - **Shadow bias computation**: Slope-scaled bias needs the geometric surface angle
   - Evidence: `DeferredFaceNormalFromDepth_p.hlsl` can reconstruct face normals from the depth buffer via cross products of screen-space derivatives, rather than requiring a separate geometry pass

3. **VertexNormalInC** -- Smooth vertex-interpolated normal. Uses:
   - **Bilateral blur edge awareness**: Smooth normals help blur filters detect surface boundaries without being confused by bump map detail
   - **Subsurface scattering direction**: SSS needs the smooth surface normal, not the bump-mapped one
   - **Normal decompression**: `DeferredDeCompFaceNormal_p.hlsl` suggests normals may be stored compressed

**Confidence**: VERIFIED for existence (string references), PLAUSIBLE for per-buffer usage (inferred from standard deferred rendering practices)

### Normal Encoding Analysis

The shader `DeferredDeCompFaceNormal_p.hlsl` ("decompress face normal") confirms normals are stored in a compressed format. Likely encodings:

| Encoding | Bits | Quality | WebGPU Format |
|----------|------|---------|---------------|
| Octahedral (2-channel) | 2x16 = 32 bits | High | `rg16float` |
| Spheremap transform | 2x16 = 32 bits | Medium | `rg16snorm` |
| 3-channel uncompressed | 3x16 = 48 bits | Best | `rgba16float` (wastes A) |
| R10G10B10A2 | 32 bits | Medium | `rgb10a2uint` (WebGPU limited) |

Given the separate decompression shader, **octahedral encoding** is most likely -- it is the standard approach for deferred renderers since 2014.

**Confidence**: SPECULATIVE (decompression shader exists, exact encoding unknown)

### What "PreShade" Means

The `BitmapDeferredPreShade` buffer's purpose is [NEEDS INVESTIGATION]. Based on the name and position in the pipeline, the most likely candidates are:

1. **Pre-computed diffuse shading**: A pre-lit diffuse term computed during the G-buffer fill, using baked or simplified lighting, so that the deferred read phase can skip redundant work for static geometry.
2. **Material response LUT index**: An index or parameter that maps into a pre-computed material response (e.g., subsurface scattering profile, BRDF variation).
3. **Self-illumination / emissive**: The `_SI_` (self-illumination) shader variant suggests some materials emit light. PreShade could store emissive intensity.

**Confidence**: SPECULATIVE

### "DiffuseAmbient" vs "MDiffuse"

- **MDiffuse** (`BitmapDeferredMDiffuse`): The **material** diffuse color -- this is the albedo/base color written during the G-buffer fill. The "M" prefix means "Material."
- **DiffuseAmbient** (`Bitmap_DeferredDiffuseAmbient`): The **lighting result** -- accumulated diffuse irradiance + ambient term. This is computed during `DeferredRead`/`DeferredReadFull` and contains the product of `MDiffuse * (ambient + lightmap + indirect)`.

In other words: `MDiffuse` is an input (texture data), `DiffuseAmbient` is an output (lighting result).

**Confidence**: PLAUSIBLE (naming convention strongly supports this interpretation)

---

## 4. Deferred Rendering Pipeline

### Complete Pipeline Flow

**Source**: Render pass ordering from string references in binary, decompiled `CVisionViewport::VisibleZonePrepareShadowAndProjectors`

The pipeline is organized into phases, each consisting of named render passes:

#### Phase 1: Frame Setup
```
SetCst_Frame              -- Upload per-frame constant buffers (camera, time, etc.)
  -> SetCst_Zone          -- Upload per-zone constants
    -> GenAutoMipMap       -- Generate auto mipmaps for dynamic textures
```
**Confidence**: VERIFIED (pass names from strings)

#### Phase 2: Shadow Preparation
```
ShadowCreateVolumes       -- Build shadow volumes for volume shadow geometry
  -> ShadowRenderCaster   -- Render shadow casters into shadow maps
    -> ShadowRenderPSSM   -- Render PSSM cascade shadow maps
      -> ShadowCacheUpdate -- Update cached shadow maps for static geometry
```
**Confidence**: VERIFIED (pass names from strings, shadow decompilation confirms flow)

#### Phase 3: Scene Preparation
```
CreateProjectors          -- Set up projector textures (spotlights, etc.)
  -> UpdateTexture        -- Update dynamic textures
    -> Decal3dDiscard     -- Cull/discard 3D decals
      -> ParticlesUpdateEmitters  -- CPU: update particle emitter states
        -> ParticlesUpdate        -- GPU: compute shader particle update
```
**Confidence**: VERIFIED

#### Phase 4: Environment Pre-Passes
```
CubeReflect               -- Render cube map reflections
  -> TexOverlay            -- Apply texture overlays
    -> LightFromMap        -- Sample lighting from lightmaps
      -> VertexAnim        -- Process vertex animation
        -> Hemisphere      -- Render hemisphere maps
          -> LightOcc      -- Light occlusion calculation
            -> WaterReflect -- Render water reflection maps
              -> Underlays  -- Render underlay geometry
```
**Confidence**: VERIFIED

#### Phase 5: G-Buffer Fill (Deferred Write)
```
DipCulling                -- GPU frustum culling via compute (Instances_Cull_SetLOD_c.hlsl)
  -> DeferredWrite        -- Main G-buffer fill (Block_TDSN_DefWrite, CarSkin_DefWrite, etc.)
    -> DeferredWriteFNormal  -- Write face normals
      -> DeferredWriteVNormal -- Write vertex normals
        -> DeferredDecals     -- Apply deferred decals (DeferredDecalGeom_p.hlsl)
          -> DeferredBurn     -- Apply burn/scorch marks
            -> DeferredShadow -- Write shadow information
              -> DeferredAmbientOcc -- Compute ambient occlusion (HBAO+)
```
**Confidence**: VERIFIED

#### Phase 6: Deferred Read / Lighting
```
DeferredFakeOcc           -- Apply fake occlusion for distant objects
  -> CameraMotion         -- Compute camera motion vectors
    -> DeferredRead       -- Read G-buffer, start lighting accumulation
      -> DeferredReadFull -- Full deferred lighting resolution
        -> DeferredLighting -- Final light accumulation
          -> Reflects_CullObjects -- Cull objects for reflections
```

During deferred read, these shader passes execute:
- `Deferred_SetILightDir_p.hlsl` -- Set indirect light direction
- `Deferred_AddAmbient_Fresnel_p.hlsl` -- Add ambient with Fresnel
- `Deferred_AddLightLm_p.hlsl` -- Add lightmap contribution
- `Deferred_SetLDirFromMask_p.hlsl` -- Set light direction from mask buffer
- `DeferredGeomLightBall_p.hlsl` -- Point light geometry pass
- `DeferredGeomLightSpot_p.hlsl` -- Spot light geometry pass
- `DeferredGeomLightFxSphere_p.hlsl` -- Sphere FX light
- `DeferredGeomLightFxCylinder_p.hlsl` -- Cylinder FX light
- `DeferredShadowPssm_p.hlsl` -- PSSM shadow application

**Confidence**: VERIFIED

#### Phase 7: Screen-Space Reflections
```
SSLReflects               -- Screen-space reflections (SSReflect_Deferred_p.hlsl)
  -> SSLReflects_GlobalCube -- Fall back to global cubemap for SSR misses
    -> SSLReflects_Add    -- Composite reflections onto scene
```
**Confidence**: VERIFIED

#### Phase 8: Forward / Transparent Objects
```
ForestRender              -- Forest/vegetation rendering
  -> ForestRender_MSAA    -- Forest with MSAA (alpha-to-coverage)
    -> GrassUpdateInstances -- Update grass instance positions
      -> GrassRender      -- Render grass
        -> ShadowRender   -- Render remaining shadows
          -> Alpha01      -- Alpha-tested geometry
            -> AlphaBlend -- Alpha-blended geometry
              -> AlphaBlendSoap -- [UNKNOWN] soap-like transparent material
                -> BufferRefract -- Refraction buffer capture
```
**Confidence**: VERIFIED

#### Phase 9: Particle Rendering
```
ParticleSelfShadow_ComputeBBoxes -> ... -> ParticleSelfShadow_Propagation
VortexParticle -> VortexParticle_UpScale
ParticlesRender -> ParticlesRenderRefract -> ParticlesRender_UpScale
```
**Confidence**: VERIFIED

#### Phase 10: Ghost/Overlay
```
GhostLayer                -- Render ghost cars to separate layer
  -> GhostLayerBlend      -- Blend ghost layer with scene
```
**Confidence**: VERIFIED

#### Phase 11: Post-Processing
```
DeferredFogVolumes        -- Volumetric fog boxes/shapes
  -> DeferredFog          -- Apply deferred fog
    -> LensFlares         -- Lens flare occlusion + compositing
      -> FxDepthOfField   -- Depth of field
        -> FxMotionBlur   -- Motion blur
          -> FxBlur       -- General blur
            -> FxColors   -- Color adjustment
              -> FxColorGrading -- LUT color grading
                -> FxExtraOutput  -- Extra outputs (e.g. separate UI render)
```
**Confidence**: VERIFIED

#### Phase 12: Tone Mapping / Bloom / AA
```
FxFXAA                    -- FXAA pass
  -> FxToneMap            -- Tone mapping (filmic curve + auto-exposure)
    -> FxBloom            -- HDR bloom
      -> CustomEnding     -- Custom post-effects
```
**Confidence**: VERIFIED

#### Phase 13: Final Output
```
ResolveMsaaHdr            -- Resolve MSAA HDR buffer
  -> ResolveMsaa          -- Resolve MSAA
    -> StretchRect        -- Stretch/blit to back buffer
      -> BlurAA           -- [UNKNOWN] blur-based AA
        -> DownSSAA       -- Downsample SSAA
          -> SwapChainPresent -- Present to display
```
**Confidence**: VERIFIED

### Pipeline Configuration

The pipeline can switch between deferred and forward:
- **String**: `"Current shading pipeline, if true Antialias_Deferred setting is used, otherwise it is Antialias_Forward."`
- **Setting**: `"IsDeferred"` at `0x141cc3e88`
- **Deferred AA options**: `"DeferredAntialiasing| FXAA"`, `"DeferredAntialiasing| TXAA"`
- **Forward AA options**: MSAA 2/4/6/8/16 samples

---

## 5. Shadow System

### Architecture Overview

```
SHADOW SYSTEM ARCHITECTURE
======================================================================
  DIRECTIONAL LIGHT (Sun)
  +--> PSSM (4 cascades)
  |      +--> Cascade 0: Near (highest detail)    "MapShadowSplit0"
  |      +--> Cascade 1: Mid-near                 "MapShadowSplit1"
  |      +--> Cascade 2: Mid-far                  "MapShadowSplit2"
  |      +--> Cascade 3: Far (lowest detail)      "MapShadowSplit3"
  |
  +--> Shadow Cache (static geometry)
  |      +--> ShadowCache/UpdateShadowIndex_c.hlsl (compute)
  |
  +--> Shadow Clip Maps (large-scale terrain)
         +--> "ShadowClipMap_Grp%u"
         +--> "P3ClipMapShadowLDir0"

  POINT/SPOT LIGHTS
  +--> Shadow Volumes
  |      +--> DeferredGeomShadowVol_p/v.hlsl
  |
  +--> Projector Shadows
         +--> DeferredGeomProjector_p/v.hlsl

  PERFORMANCE FALLBACKS
  +--> Fake Shadows (distant objects)
  |      +--> "ShaderGeomFakeShadows"
  |      +--> "ShaderShadowFakeQuad"
  |      +--> "FlatCubeShadow"
  |
  +--> Static Shadows (baked)
         +--> "StaticShadow0", "CastStaticShadow"
======================================================================
```

### Shadow Preparation (Decompiled)

**Source**: `CVisionViewport::VisibleZonePrepareShadowAndProjectors` at `0x14095d430`

#### Cascade Count Determination

```c
// At 0x14095d5b0-0x14095d5df
if (*(int *)(param_1 + 0x680) < 2) {
    uVar12 = 4;  // Default: 4 cascades
} else {
    if (*(uint *)(param_1 + 0x588) < 3) {
        if (1 < *(uint *)(param_1 + 0x588)) goto LAB_14095d5d3;
        uVar12 = 4;  // Still 4 cascades
    }
    if ((*(byte *)(param_1 + 0x5d0) & 0x40) == 0) {
        if ((*(byte *)(param_1 + 0x5d0) & 8) == 0) {
            uVar12 = 4;  // 4 cascades
        }
    } else {
        uVar12 = 1;  // 1 cascade (simplified mode)
    }
}
```

The cascade count is either **4** (standard) or **1** (simplified, when `flag & 0x40` set at offset `0x5d0`). The simplified mode is likely triggered by the "Minimum" shadow quality setting.

**Confidence**: VERIFIED (decompiled code at `0x14095d430`)

#### Shadow Group Processing Per Zone

Each visible zone allocates a shadow data structure of `0x4f0 = 1264` bytes and iterates through shadow casters:

```c
// Caster mask computation at 0x14095d620-0x14095d640
do {
    lVar7 = *plVar15;
    plVar15 = plVar15 + 0x18;
    uVar13 = uVar13 | 1 << (*(byte *)(lVar7 + 0x22c) & 0x1f);
    uVar8 = uVar8 - 1;
} while (uVar8 != 0);
```

Each shadow caster has a group index at offset `0x22c` (5-bit value, 0-31). The bitmask tracks which shadow groups are present in each zone.

**Confidence**: VERIFIED

### PSSM Configuration

| Property | Value | Evidence |
|----------|-------|----------|
| Number of cascades | 4 (default), 1 (simplified) | Decompiled cascade count logic; strings `"MapShadowSplit0"` - `"MapShadowSplit3"` |
| Shadow map format | [UNKNOWN] Likely `DXGI_FORMAT_D16_UNORM` or `D24_UNORM` | Standard practice for shadow maps |
| Shadow resolution | Configurable via `"ShadowMapTexelSize"` | String reference |
| Split scheme | [UNKNOWN] Likely logarithmic or practical split | Standard PSSM practice |
| Filtering | PCF baseline + `"HqSoftShadows"` toggle for higher quality | String references: `"ShadowSoftCorners"`, `"HqSoftShadows"` |
| Bias | `"ShadowBiasConstSlope"` -- slope-scaled depth bias | String reference |
| Alpha test | `"ShadowCasterAlphaRef"` / `"ShadowCasterAlphaCut"` | String references |

**Confidence**: VERIFIED for structure, SPECULATIVE for exact formats and split distances

### Shadow Quality Tiers

| Quality | Setting | Likely Behavior |
|---------|---------|-----------------|
| None | No shadows | All shadow passes skipped |
| Minimum | Reduced resolution, 1 cascade | `flag & 0x40` triggers single cascade |
| Medium | Standard resolution, 4 cascades | Default |
| High | Higher resolution, 4 cascades | Larger shadow maps |
| Very High | Maximum resolution, 4 cascades + HqSoftShadows | Maximum quality |

**Player-specific shadow settings** (`CSystemConfig::EPlayerShadow`): None / Me (own car only) / All (all players)

Per-category shadow counts: `"ShadowCountCarHuman"`, `"ShadowCountCarOpponent"`

**Confidence**: VERIFIED

### Shadow Cache System

The engine caches static shadow maps to avoid re-rendering:
- `"ShadowCacheMgr"` / `"SVisShadowCacheMgr"` -- Manager class
- `"ShadowCache_Enable"` -- Toggle
- `"ShadowCache/UpdateShadowIndex_c.hlsl"` -- Compute shader for incremental updates
- `"ShadowCacheUpdate"` render pass

**Confidence**: VERIFIED

### Shadow Clip Maps

For large-scale terrain shadows: `"ShadowClipMap_Grp%u"`, `"P3ClipMapShadowLDir0"`. This is a cascaded clip-map approach where the shadow map resolution stays constant but the covered world-space area grows at each level -- similar to how terrain clip maps work for geometry LOD.

**Confidence**: PLAUSIBLE (string evidence only)

### Fake Shadow System

For distant or low-priority objects, the engine uses projected shapes instead of real shadow maps:
- `"ShaderGeomFakeShadows"` -- Geometry-based fake shadow (project mesh silhouette as flat quad)
- `"ShaderShadowFakeQuad"` -- Simple darkened quad projected below object
- `"FlatCubeShadow"` -- Cube-shaped shadow projection

These cost virtually nothing compared to real shadow maps and are applied during `DeferredFakeOcc`.

**Confidence**: VERIFIED (string references)

---

## 6. HBAO+ Configuration

### Full Configuration Structure

**Source**: `NSysCfgVision::SSSAmbOcc` registration at `0x14091f4e0`

The HBAO+ configuration structure is registered as `"NSysCfgVision::SSSAmbOcc"` with size `0x4c` (76 bytes).

#### Homemade AO Parameters (offsets 0x00-0x18)

| Field | Offset | Type | Description | Evidence |
|-------|--------|------|-------------|----------|
| `IsEnabled` | `0x00` | bool | Master AO enable/disable | Line 30: `FUN_1402eb040("IsEnabled",0,&local_58)` |
| `UseHomeMadeHBAO` | `0x04` | bool | Use Nadeo's custom AO instead of NVIDIA HBAO+ | Line 37 |
| `DelayGrassFences` | `0x08` | bool | Delays AO computation past grass/fence rendering to avoid artifacts [PLAUSIBLE] | Line 73 |
| `ImageSize` | `0x0C` | float | AO render resolution scale factor | Line 45 |
| `WorldSize` | `0x10` | float | AO world-space radius (meters) | Line 52 |
| `Exponent` | `0x14` | float | AO falloff exponent | Line 59 |
| `BlurTexelCount` | `0x18` | int | Bilateral blur kernel radius in texels | Line 66 |

**Confidence**: VERIFIED (all offsets and names from decompiled registration function)

#### NVIDIA HBAO+ Parameters (offsets 0x1C-0x30)

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `NvHBAO.Enabled` | `0x1C` | bool | NVIDIA HBAO+ enable |
| `NvHBAO.Radius` | `0x20` | float | World-space AO sampling radius |
| `NvHBAO.Bias` | `0x24` | float | Depth bias to prevent self-occlusion |
| `NvHBAO.LargeScaleAO` | `0x28` | float | Large-scale AO contribution multiplier |
| `NvHBAO.SmallScaleAO` | `0x2C` | float | Small-scale AO contribution multiplier |
| `NvHBAO.PowerExponent` | `0x30` | float | Power exponent for AO curve |

**Confidence**: VERIFIED

#### Big Scale HBAO+ Pass (offsets 0x34-0x48)

A second HBAO+ pass at larger scale for global ambient occlusion:

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `NvHBAO_BigScale.Enabled` | `0x34` | bool | Enable big-scale AO pass |
| `NvHBAO_BigScale.Radius` | `0x38` | float | Larger sampling radius |
| `NvHBAO_BigScale.Bias` | `0x3C` | float | Depth bias |
| `NvHBAO_BigScale.LargeScaleAO` | `0x40` | float | Large-scale factor |
| `NvHBAO_BigScale.SmallScaleAO` | `0x44` | float | Small-scale factor |
| `NvHBAO_BigScale.PowerExponent` | `0x48` | float | Power exponent |

**Confidence**: VERIFIED

### HBAO+ Shader Pipeline

```
1. LinearizeDepth_p.hlsl       -- Convert hardware depth to linear eye-space Z
2. DeinterleaveDepth_p.hlsl    -- Split depth into 4x4 interleaved layers (16 quarter-res)
3. ReconstructNormal_p.hlsl    -- Reconstruct normals from depth derivatives
4. CoarseAO_p.hlsl / _g.hlsl  -- Main AO computation at quarter resolution
5. ReinterleaveAO_p.hlsl       -- Recombine 4x4 layers back to full resolution
6. BlurX_p.hlsl / BlurY_p.hlsl -- Separable bilateral blur (edge-preserving)
```

The `_g.hlsl` suffix on `CoarseAO` indicates a geometry shader variant for multi-layer rendering in a single pass.

### Dual-Pass AO

The `NvHBAO_BigScale` parameters confirm the engine runs HBAO+ **twice**:
1. **Small-scale pass**: Tighter radius for contact shadows and fine detail
2. **Big-scale pass**: Wider radius for room-scale ambient occlusion

The results are combined (likely multiplied) to produce the final AO term.

**Confidence**: PLAUSIBLE (dual parameter sets strongly suggest dual pass)

---

## 7. Shader System

### Shader Cache Architecture

**Source**: `Vision::VisionShader_GetOrCreate` at `0x14097cfb0`

```c
// Cache lookup
plVar4 = *(longlong **)(param_2 + 0x18);  // Check if shader already cached
if (plVar4 == (longlong *)0x0) {
    // Cache miss - compile
    FUN_140117690(local_f8, "Vision::VisionShader_GetOrCreate");
    local_118[0] = 0x3108;             // Shader format identifier

    // Lock shader cache mutex
    FUN_14013c560(param_1 + 0x214, local_148);

    // Create shader via virtual call (vtable offset 0x770)
    plVar4 = (**(code **)(*param_1 + 0x770))(param_1, param_2, 0);

    // Store in cache at offset 0x18
    *(longlong **)(param_2 + 0x18) = plVar4;

    // Unlock
    FUN_1401560e0(param_1 + 0x216, local_148);
}
return plVar4;
```

Key observations:
- Shader descriptors stored at `param_2`, compiled shader pointer at offset `0x18`
- Thread-safe: uses mutex locking (lock at `param_1 + 0x214`, unlock at `param_1 + 0x216`)
- Virtual dispatch at vtable offset `0x770` handles actual D3D11 shader creation
- Constant `0x3108` is a shader format/version identifier

**Confidence**: VERIFIED (decompiled at `0x14097cfb0`)

### Shader Variant System

The function recursively creates shader variants when `param_3 > 13`:

| Variant Index | When Created | Likely Purpose |
|---------------|-------------|----------------|
| 0 | Base shader | Default rendering |
| 1 | Always | Depth-only / Z-prepass |
| 2 | Material bit 8 set | [UNKNOWN] possibly tessellation |
| 3 | Always | Shadow caster variant |
| 4 | Always | [UNKNOWN] |
| 7 | Viewport flag `0x8000` | Advanced feature (SSR? TXAA?) |
| 9 | Viewport flag `0x8000` | Advanced feature companion |
| 12 | Always | [UNKNOWN] |
| 13 | Material bit 7 set | [UNKNOWN] possibly alpha test |
| 14 (0xe) | Separate | Tessellation/LOD shader |

Variants are stored at slots `plVar4[0x22]` through `plVar4[0x2f]` (up to 14 slots).

**Confidence**: VERIFIED (decompiled variant enumeration logic)

### "Tech3" Naming Convention

```
Tech3/<ObjectType>_<Passes>_<Pipeline>_<Stage>.hlsl

Examples:
  Tech3/Block_TDSN_DefWrite_p.hlsl
  |     |     |    |        |
  |     |     |    |        +-- Stage: p=pixel, v=vertex, g=geometry, c=compute
  |     |     |    +-- Pipeline: DefWrite=G-buffer fill, DefRead=lighting
  |     |     +-- Passes: T=Texture, D=Diffuse, S=Specular, N=Normal
  |     +-- Object type: Block, CarSkin, Tree, Sea, etc.
  +-- Framework version (3rd generation)
```

Additional naming tokens:
- `Py` / `Pxz` -- Projection modes (Y-axis / XZ-plane for triplanar mapping)
- `COut` / `CIn` -- Color output / Color input
- `SI` -- Self-illumination (emissive)
- `LM0` / `LM1` / `LM2` -- Lightmap variant indices

**Confidence**: VERIFIED (pattern analysis of 200+ shader filenames)

### Shader Binary Distribution

Shaders are distributed as pre-compiled binaries, not source:
- `"Shaders\\"` -- Shader binary directory
- `"Shaders binary loaded from \"%s\""` -- Load log
- `"Shader binary is not up to date (GitHash): %016I64x != %016I64x"` -- Git hash versioning
- `"Shader binary is not up to date (GitVersion): %u < %u"` -- Numeric version check

**Confidence**: VERIFIED

---

## 8. Shader Buffer Taxonomy

### Overview

**Source**: RTTI class names from `class_hierarchy.json` (42 SCBuffer classes identified)

All `SCBuffer*` classes represent D3D11 constant buffer (cbuffer) structures. Naming convention:

- **`SCBufferP_*`** -- Pixel shader constant buffers
- **`SCBufferV_*`** -- Vertex shader constant buffers
- **`SCBufferDraw*`** -- Per-draw-call constant buffers (highest update frequency)
- **`SCBufferShader*`** -- Per-shader constant buffers (bound once per shader change)
- **`SCBuffer_*`** -- Shared/generic constant buffers

### Complete Taxonomy Table

```
+------------------------------------------------------------------+
| BUFFER UPDATE FREQUENCY HIERARCHY                                 |
+==================================================================+
| PER-FRAME (bind group 0 in WebGPU)                               |
|   SCBufferP_PixelConst          Generic pixel constants           |
|   TemporalAA_Constants          TAA jitter/blend params           |
+------------------------------------------------------------------+
| PER-PASS (bind group 1 in WebGPU)                                |
|   -- Deferred Lighting --                                        |
|   SCBufferP_Deferred_AddAmbient_Fresnel   Ambient + Fresnel      |
|   SCBufferP_Deferred_AddLightLm           Lightmap contribution  |
|   SCBufferP_Deferred_SetILightDir         Indirect light dir     |
|   SCBufferP_Deferred_SetLDirFromMask      Light dir from mask    |
|   SCBufferP_DeferredFog                   Global fog params      |
|   SCBufferP_DeferredWaterFog              Underwater fog          |
|                                                                   |
|   -- Lightmapping --                                             |
|   SCBufferP_LmILightDir_Set              LM indirect light setup |
|   SCBufferP_LmLBumpILighting_Inst        LM bumped indirect      |
|   SCBufferP_LmLightAddDir                LM dir light addition   |
|   SCBufferP_ReProjectLm                  LM reprojection         |
|   SCBufferV_LmLBumpILighting_Inst        LM vertex transform     |
|                                                                   |
|   -- Water/Fog --                                                |
|   SCBufferP_WaterFogFromDepthH           Height-based water fog  |
|   SCBufferP_WaterFog_WGeomUnder          Underwater geom fog     |
|   SCBufferV_Sea                          Sea vertex/wave params  |
|   SCBufferV_DeferredWaterFog_FullTri     Fullscreen water fog    |
|                                                                   |
|   -- Decals --                                                   |
|   SCBufferP_Decal_Boxs                   Box decal projection    |
|   SCBufferP_Decal_FullTri                Full-tri decal          |
|   SCBufferV_Decal_Boxs_SRView            Decal box SRV transform |
|                                                                   |
|   -- Environment --                                              |
|   SCBufferP_CubeFilterDown4x4_Cube3x2   Cube filter downsample  |
|   SCBufferP_CubeMap_EyeInWorld_HdrAlpha2 Cubemap + HDR alpha     |
|   SCBufferV_CubeMap_EyeInWorld           Cubemap vertex          |
|   SEquiRectFromCubeFaceP                 Equirect conversion     |
|   SGpuFilterDown4x4                      GPU downsample filter   |
|                                                                   |
|   -- Utility --                                                  |
|   SCBufferV_PixelMinOrMax_Down4x4        Depth min/max downsample|
|   SCBuffer_PixelGetTexture               Texture sampling params |
+------------------------------------------------------------------+
| PER-SHADER (bind group 2 in WebGPU)                              |
|   SCBufferShaderP_Tree                   Tree pixel material     |
|   SCBufferShaderP_TreeDefWrite           Tree G-buffer write     |
|   SCBufferShaderP_TreeForward            Tree forward pass       |
|   SCBufferShaderV_Tree                   Tree vertex (wind, LOD) |
|   SCBufferImpostorShaderP                Impostor pixel          |
+------------------------------------------------------------------+
| PER-DRAW (bind group 3 in WebGPU)                                |
|   SCBufferDrawP_TreeForward              Tree per-draw pixel     |
|   SCBufferDrawV_Tree                     Tree per-draw (xform)   |
|   SCBufferDrawV_TreeImpostor             Billboard transform     |
|   SCBufferDraw_ParticleStatic            Particle per-draw       |
|   SCBufferDraw_ParticleStaticFakeOcc     Particle + fake occ     |
|   SCBufferImpostorDrawP                  Impostor per-draw       |
|   SCBufferP_WaterFogFromDepthH_Draw      Water fog per-draw      |
|   SCBufferV_Decal_Boxs_SRView_Draw       Decal per-draw          |
|   SCBufferV_DeferredWaterFog_Draw        Water fog per-draw vtx  |
|                                                                   |
|   -- Shared --                                                   |
|   SCBuffer_ParticleStatic               Particle globals         |
|   SCBufferP_TreeVertex_AddLight         Tree per-vtx light       |
|   SCBufferP_GeomDynaVertex_AddLight     Dynamic geom per-vtx    |
|   SCBufferV_CameraWaterDroplets_*       Screen water droplets    |
+------------------------------------------------------------------+
```

### Functional Grouping Summary

| Subsystem | Buffer Count | Key Buffers |
|-----------|-------------|-------------|
| Deferred Lighting | 6 | `Deferred_AddAmbient_Fresnel`, `Deferred_SetILightDir`, `DeferredFog` |
| Tree/Vegetation | 9 | `TreeDefWrite`, `TreeForward`, `TreeImpostor`, `TreeVertex_AddLight` |
| Water/Fog | 6 | `WaterFogFromDepthH`, `WaterFog_WGeomUnder`, `Sea` |
| Decals | 4 | `Decal_Boxs`, `Decal_FullTri` |
| Lightmapping | 5 | `LmILightDir_Set`, `LmLBumpILighting_Inst`, `ReProjectLm` |
| Particles | 3 | `ParticleStatic`, `ParticleStaticFakeOcc` |
| Environment Maps | 3 | `CubeMap_EyeInWorld`, `CubeFilterDown4x4` |
| Temporal AA | 1 | `TemporalAA_Constants` |

**Confidence**: VERIFIED (all 42 names from RTTI `class_hierarchy.json`)

---

## 9. Post-Processing Pipeline

### Bloom HDR

**Source**: `CVisPostFx_BloomHdr` (class ID `0xC032000`, size `0x168`, constructor at `0x1409a45a0`)

**Pipeline**:
```
1. BloomSelectFilterDown2_p.hlsl   -- Threshold + 2x downsample
2. BloomSelectFilterDown4_p.hlsl   -- 4x downsample
3. Bloom_HorizonBlur_p.hlsl       -- Horizontal Gaussian blur per mip
4. Bloom_StreaksWorkDir_p.hlsl     -- Directional light streaks (anamorphic)
5. Bloom_StreaksSelectSrc_p.hlsl   -- Select streak source intensity
6. Bloom_Final_p.hlsl             -- Composite bloom back to HDR buffer
```

Configuration: `"BloomIntensUseCurve"`, `"MinIntensInBloomSrc"` (threshold), `"Bloom_Down%d"` (multi-level targets)

**Confidence**: VERIFIED

### Tone Mapping

**Source**: `CVisPostFx_ToneMapping` (class ID `0xC030000`, size `0x6F0`, constructor at `0x14099dce0`)

**Luminance computation** (auto-exposure):
```
1. TM_GetLumi_p.hlsl              -- Extract luminance from HDR
2. TM_GetLog2LumiDown1_p.hlsl     -- Log2 luminance + progressive downsample
3. TM_GetAvgLumiCurr_p.hlsl       -- Average luminance (current frame)
```

**Tone map operators** (selectable):
```
4. TM_GlobalOp_p.hlsl             -- Global Reinhard-style
5. TM_GlobalOpAutoExp_p.hlsl      -- Global with auto-exposure
6. TM_GlobalFilmCurve_p.hlsl      -- Filmic curve (piecewise power: shoulder+linear+toe)
7. TM_LocalOp_p.hlsl              -- Local per-pixel adaptive
```

The filmic curve uses `"NFilmicTone_PowerSegments::SCurveParamsUser"` -- a piecewise power function model similar to Hable/Uncharted 2 but parameterized as power segments rather than rational functions.

**Confidence**: VERIFIED

### Motion Blur

- **Shader**: `Effects/MotionBlur2d_p.hlsl` -- 2D per-pixel velocity-based blur
- **Intensity**: `"MotionBlur2d.Intensity01"` (0.0 to 1.0), default 0.35
- **Settings**: `"m_FxMotionBlur"` (offset `0xD0`), `"m_FxMotionBlurIntens"` (offset `0xD8`)

**Confidence**: VERIFIED

### Depth of Field

- **Shader**: `Effects/PostFx/DoF_T3_BlurAtDepth_p.hlsl`
- **Parameters**: `"FxDOF_FocalBlur_InvZ_MAD"` (focal blur as multiply-add on inverse Z), `"DofLensSize"`, `"DofFocusZ"`, `"DofSampleCount"`
- **High quality**: `"VideoHqDOF"` for video recording mode

**Confidence**: VERIFIED

### Color Grading

- `Effects/PostFx/ColorGrading_p.hlsl` -- LUT-based 3D texture lookup
- `Effects/PostFx/Colors_p.hlsl` -- Brightness, contrast, saturation
- `Effects/PostFx/ColorBlindnessCorrection_p.hlsl` -- Accessibility filter

**Confidence**: VERIFIED

### Lens Effects

- **Lens Flares**: `Engines/LensFlareOccQuery_v.hlsl` (occlusion query), `Effects/2dFlareAdd_Hdr_p.hlsl` (HDR composite)
- **Lens Dirt**: `Effects/2dLensDirtAdd_p.hlsl` (lens dirt modulated by bloom)
- **HDR Scales**: `"T3HdrScales_Block_Particle_Player"` -- separate HDR normalization per category

**Confidence**: VERIFIED

---

## 10. Material and PBR System

### Material Class Hierarchy

```
CPlugMaterial (base)
  +-- CPlugMaterialCustom       -- User-customizable
  +-- CPlugMaterialUserInst     -- Instance override
  +-- CPlugMaterialPack         -- Packed collection
  +-- CPlugMaterial_VertexIndex  -- Vertex-indexed
  +-- CPlugMaterialFx           -- Single FX
  +-- CPlugMaterialFxs          -- Multiple FX
  +-- CPlugMaterialFxDynaBump   -- Dynamic bump (water ripples)
  +-- CPlugMaterialFxDynaMobil  -- Animated material (conveyor, scroll)
  +-- CPlugMaterialFxFlags      -- Flag overrides
  +-- CPlugMaterialFxFur        -- Fur/grass shell rendering
  +-- CPlugMaterialFxGenCV      -- Generic control vertex FX
  +-- CPlugMaterialColorTargetTable -- Color target mapping
  +-- CPlugMaterialWaterArray   -- Water collection
```

**Confidence**: VERIFIED (RTTI)

### Material Texture Slots

From shader naming (`TDSN`) and G-buffer target names:

| Slot | Name | G-Buffer Target | Description |
|------|------|-----------------|-------------|
| T | Texture/Albedo | -- | Base color texture (sampled in shader) |
| D | Diffuse | `MDiffuse` | Diffuse color written to G-buffer |
| S | Specular | `MSpecular` | Specular F0 reflectance + roughness |
| N | Normal | `PixelNormalInC` | Tangent-space normal map |
| SI | Self-Illumination | `PreShade` [SPECULATIVE] | Emissive texture |
| LM | Lightmap | via `Deferred_AddLightLm` | Pre-baked lighting (UV1) |

**Confidence**: VERIFIED for TDSN, SPECULATIVE for SI -> PreShade mapping

### PBR Workflow: Specular/Glossiness

The engine uses a **specular/glossiness** PBR workflow (NOT metallic/roughness):

**Evidence**:
- `Engines/Pbr_Spec_to_Roughness_c.hlsl` -- Converts specular to roughness (specular workflow input)
- `Engines/Pbr_IntegrateBRDF_GGX_c.hlsl` -- GGX BRDF integration LUT (Cook-Torrance)
- `Engines/Pbr_PreFilterEnvMap_GGX_c.hlsl` -- Split-sum IBL pre-filtered environment map
- `Engines/Pbr_FastFilterEnvMap_GGX_c.hlsl` -- Fast pre-filter variant
- `Engines/Pbr_RoughnessFilterNormalInMips_c.hlsl` -- Normal mip filtering by roughness
- Separate `MDiffuse` and `MSpecular` G-buffer targets (specular workflow stores F0 color in specular)

**BRDF**: GGX/Cook-Torrance specular with Smith GGX height-correlated visibility term (standard). The GGX BRDF integration LUT is pre-computed via compute shader and stored as a 2D texture (indexed by NdotV and roughness).

**Material properties** (inferred channel mapping):

| G-Buffer Target | Channel R | Channel G | Channel B | Channel A |
|----------------|-----------|-----------|-----------|-----------|
| MDiffuse | Albedo R | Albedo G | Albedo B | [UNKNOWN -- possibly AO or material ID] |
| MSpecular | F0 R | F0 G | F0 B | Roughness (or glossiness) |

**Confidence**: PLAUSIBLE (shader names strongly indicate specular/gloss, exact channel mapping unconfirmed)

### Lightmap Integration

The lightmap system uses **H-basis** (half-life basis) encoding with **YCbCr compression**:

- `CHmsLightMap` class with methods: `Compute_MDiffuse`, `ImageRealAddRGBA`, `SH_UpdateMapping`
- `CHmsLightMapCacheSH` -- Spherical harmonics lightmap cache
- `Lightmap/LmCompress_HBasis_YCbCr4_c.hlsl` -- Compressed H-basis in YCbCr4 color space
- `Lightmap/LmLBumpILighting_Inst_p.hlsl` -- Bumped indirect lighting from lightmaps
- `Lightmap/LmLHBasisILighting_Inst_p.hlsl` -- H-basis indirect lighting
- `Lightmap/ProbeGrid_Sample_c.hlsl` -- Light probe grid sampling for dynamic objects
- `NHmsLightMap::YCbCr_to_RGB` -- Confirmed YCbCr decode

**How lightmaps integrate**: Block geometry has two UV channels (UV0 = material, UV1 = lightmap). During `Deferred_AddLightLm`, the lightmap is sampled at UV1 and multiplied with the diffuse albedo from `MDiffuse` to produce `DiffuseAmbient`. For bumped surfaces, the H-basis encoding allows per-pixel directional lighting from the lightmap rather than flat irradiance.

**Confidence**: VERIFIED (shader names, RTTI methods, UV layer evidence from NadeoImporter materials)

---

## 11. TXAA Implementation

### Two Implementations

**Source**: Ghidra string search for "TXAA" (verified)

```
NVIDIA GFSDK TXAA (hardware vendor SDK):
  GFSDK_TXAA_DX11_InitializeContext         (0x141c0f120)
  GFSDK_TXAA_DX11_ResolveFromMotionVectors  (0x141c0f178)
  GFSDK_TXAA_DX11_ReleaseContext            (0x141c0f638)

Ubisoft Custom TXAA (software fallback):
  "UBI_TXAA" / "UBI TXAA" string references
  Effects/TemporalAA/TemporalAA_p.hlsl
```

The NVIDIA version is likely used on NVIDIA GPUs (hardware-optimized path), while the Ubisoft version serves as a cross-vendor fallback.

**Confidence**: VERIFIED

### Motion Vector Generation

The `CameraMotion` pass generates per-pixel motion vectors:
- **Shader**: `DeferredCameraMotion_p.hlsl` / `_v.hlsl`
- **Method**: Reprojects current pixel position using the previous frame's view-projection matrix. The difference gives a 2D screen-space velocity vector.
- **Output**: A motion vector texture consumed by both TXAA and motion blur.

**Confidence**: VERIFIED

### Jitter Pattern

- `"PosOffsetAA"` -- Per-frame sub-pixel jitter offset applied to the projection matrix
- `"PosOffsetAAInW"` -- Same jitter in clip-space W
- **Constant buffer**: `TemporalAA_Constants` (RTTI class) holds jitter offsets and blend parameters

The jitter pattern is [NEEDS INVESTIGATION] -- could be Halton(2,3), or the 8-sample rotated grid pattern common in TAA implementations.

**Confidence**: VERIFIED for mechanism, SPECULATIVE for exact pattern

### History Buffer Management

The function `GFSDK_TXAA_DX11_ResolveFromMotionVectors` takes the current frame, motion vectors, and the history buffer, and outputs the resolved anti-aliased result. The history buffer is then updated with the new result for the next frame.

`SSReflect_Deferred_LastFrames_p.hlsl` (temporal SSR) confirms the engine maintains a previous-frame color buffer, which the TXAA system also reads.

**Confidence**: PLAUSIBLE

### Ghost/Blur Handling

Standard TAA ghost rejection techniques likely include:
- **Neighborhood clamping**: Clamp the reprojected history sample to the min/max of the current frame's 3x3 neighborhood to reject ghosting from disoccluded regions
- **Motion rejection**: Discard history when motion vectors indicate high-velocity regions (where temporal blending produces obvious blur)
- The `TemporalAA_Constants` buffer likely contains the blend weight (typically 0.9-0.95 for history, 0.05-0.1 for current) and a motion rejection threshold

**Confidence**: SPECULATIVE (standard TAA practices, no direct code evidence for specific rejection method)

---

## 12. Particle System

### GPU Particle Architecture

#### Core Compute Pipeline

```
CPU:
  CPlugParticleEmitterModel     -- Emitter definition (rates, shapes)
  CPlugParticleEmitterSubModel  -- Sub-emitter chains
  ParticlesUpdateEmitters       -- CPU updates emitter states
      |
      v
GPU Compute:
  MgrParticleSpawn_p/v.hlsl           -- Spawn new particles
  MgrParticleUpdateFromCPU_c.hlsl     -- CPU-driven parameter update
  MgrParticleUpdate_c.hlsl            -- Main particle simulation
  Particles_ComputeDepth_c.hlsl       -- Compute depth for sorting
      |
      v
GPU Render:
  MgrParticleRender_p/v.hlsl          -- Alpha-blended particles
  MgrParticleRenderOpaques_p/v.hlsl   -- Opaque particles
  MgrParticleRenderStatic_p/v.hlsl    -- Static (non-animated)
  MgrParticleShadow_p/v.hlsl          -- Shadow casting
```

#### Self-Shadowing via Voxelization

```
1. ParticleSelfShadow_ComputeBBoxes    -- Compute bounding boxes
2. ParticleSelfShadow_Voxelization     -- Voxelize via geometry shader
   (SelfShadow/ParticleVoxelization_g.hlsl)
3. ParticleSelfShadow_Propagation      -- Propagate shadow through volume
4. ParticleSelfShadow_OpaqueShadow     -- Apply opaque occluder shadows
5. ParticleSelfShadow_Render           -- Render self-shadow
6. ParticleSelfShadow_Merge            -- Merge with scene
```

#### GPU Load Management

- `"ParticleMaxGpuLoadMs"` (offset `0xB4` in `CSystemConfigDisplay`) -- GPU time budget (default: 1.7ms)
- `"TimeGpuMs_Particles"` -- Runtime GPU time measurement
- System dynamically reduces particle count to stay within budget

**Confidence**: VERIFIED

---

## 13. Water, Fog, and Special Effects

### Water Rendering

Water is rendered through multiple systems:

**Reflection**: `WaterReflect` pass renders a planar reflection (the scene mirrored across the water plane) into a render target (`CPlugBitmapRenderWater`). Quality levels: `"WaterReflect"` setting with `very_fast` through `ultra`.

**Refraction**: `BufferRefract` captures the scene behind refractive surfaces. Used for underwater distortion.

**Water fog**: Three shader variants handle underwater fog:
- `DeferredWaterFog_p.hlsl` -- Full-screen water fog
- `DeferredWaterFog_FullTri_p.hlsl` -- Full-triangle variant
- `SCBufferP_WaterFog_WGeomUnder` -- Underwater geometry fog parameters
- Height-based: `SCBufferP_WaterFogFromDepthH` (fog density based on water depth)

**Water surface**: `Sea_*` shaders render the water surface mesh:
- `SCBufferV_Sea` -- Wave parameters (frequency, amplitude, speed)
- `CPlugMaterialWaterArray` -- Water material collection

**Water particles**:
- `WaterSplash_IntersectTriangles_p.hlsl` -- GPU triangle intersection for splash spawning
- `WaterSplash_SpawnParticles_p/v.hlsl` -- Spawn splash particles at collision points
- `CameraWaterDroplets_Spawn_c.hlsl` / `_Update_c.hlsl` / `_Render_p.hlsl` -- Screen-space water droplets on camera lens

**Wetness**: `WetnessValue01` on `CSceneVehicleVisState` (0-1) drives wet car material appearance.

**Confidence**: VERIFIED

### Volumetric Fog

Full 3D volumetric fog with ray marching:

```
Render passes:
  VolumetricFog_ComputeScattering -> VolumetricFog_IntegrateScattering -> VolumetricFog_ApplyFog

Shaders:
  Effects/Fog/3DFog_RayMarching_c.hlsl              -- Ray march compute
  Effects/Fog/3DFog_ComputeInScatteringAndDensity_c.hlsl -- In-scattering + density
  Effects/Fog/3DFog_BlendInCamera_p.hlsl             -- Camera-space blend
  Effects/Fog/3DFog_UpdateNoiseTexture_c.hlsl        -- Animated noise
  Effects/Fog/FogInC_Propagate_WithLuminance_c.hlsl  -- Fog propagation
  Effects/Fog/ComputeFogSpaceInfo_c.hlsl             -- Fog space setup
```

**Fog box volumes**: Artistic fog placed by map editors as box shapes:
- `DeferredGeomFogBoxOutside_p.hlsl` / `_v.hlsl` -- Fog when camera is outside box
- `DeferredGeomFogBoxInside_p.hlsl` / `_v.hlsl` -- Fog when camera is inside box
- Render pass: `DeferredFogVolumes`

**Global fog**: `DeferredFogGlobal_p.hlsl` applied during `DeferredFog` pass.

**Confidence**: VERIFIED

### Lens Flares

- Occlusion test: `Engines/LensFlareOccQuery_v.hlsl` renders a small quad at the light position and uses an occlusion query to determine visibility percentage.
- Rendering: `Effects/2dFlareAdd_Hdr_p.hlsl` composites lens flare sprites in HDR.
- Lens dirt: `Effects/2dLensDirtAdd_p.hlsl` -- full-screen lens dirt texture modulated by bloom brightness.
- Class: `CPlugFxLensFlareArray`, `CPlugFxLensDirtGen`

**Confidence**: VERIFIED

### Screen-Space Reflections

- `SSReflect_Deferred_p.hlsl` -- Ray marching in screen space using depth buffer
- `SSReflect_Deferred_LastFrames_p.hlsl` -- Temporal accumulation from previous frames
- `SSReflect_Forward_p.hlsl` -- Forward path variant
- `SSReflect_UpSample_p.hlsl` -- Half-res SSR upsampled to full res
- Render pass: `SSLReflects` -> `SSLReflects_GlobalCube` -> `SSLReflects_Add`

**Confidence**: VERIFIED

### Subsurface Scattering

- `Effects/SubSurface/SeparableSSS_p.hlsl` -- Jorge Jimenez's separable SSS technique
- Used for car paint, skin, and translucent materials

**Confidence**: VERIFIED

### Signed Distance Fields

- `Effects/SignedDistanceField/SignedDistanceField_Render_p.hlsl` -- SDF rendering
- `Effects/SignedDistanceField/SignedDistanceField_BruteForce_c.hlsl` -- Brute force SDF generation
- `Effects/SignedDistanceField/SignedDistanceField_Analytic_c.hlsl` -- Analytic SDF

**Confidence**: VERIFIED

---

## 14. LOD and Culling System

### GPU Frustum Culling

The `DipCulling` render pass runs a compute shader for GPU-side culling:
- `Engines/Instances_Cull_SetLOD_c.hlsl` -- Frustum culling + LOD level selection in one compute pass
- `Engines/Instances_Merge_c.hlsl` -- Merge culled instance lists
- `Engines/IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl` -- Set up indirect draw arguments per LOD level and shadow group

This is an indirect rendering pipeline: the compute shader writes `DrawIndexedInstancedIndirect` arguments that the GPU consumes without CPU readback.

**Confidence**: VERIFIED (shader names, render pass name)

### Forward+ Tile Culling

- `Engines/ForwardTileCull_c.hlsl` -- Tile-based light culling for the forward pass
- Divides the screen into tiles, assigns lights per tile
- Used for transparent objects rendered in the forward pass

**Confidence**: VERIFIED

### GeomLodScaleZ

**Source**: `CSystemConfigDisplay` field `m_GeomLodScaleZ` at offset `0xEC`

This float controls LOD transition distances. From the Openplanet `Finetuner` plugin:
```
GeomLodScaleZ = 1.0  (default -- normal LOD distances)
GeomLodScaleZ > 1.0  (more aggressive LOD -- objects simplify at closer range)
GeomLodScaleZ < 1.0  (less aggressive LOD -- objects stay detailed longer)
```

The block distance for culling is computed as: `Math::Ceil(distance / 32.0f)` (32m per block unit, from Openplanet evidence). The `m_ZClipNbBlock` setting at offset `0xE4` controls how many 32m blocks away the far clip is.

**Confidence**: VERIFIED (offset from decompiled `CSystemConfigDisplay`, block size from Openplanet)

### Impostor System

For distant objects (trees especially), the engine uses billboard impostors:
- `SCBufferDrawV_TreeImpostor` -- Per-draw vertex transform (billboard orientation)
- `SCBufferImpostorDrawP` -- Per-draw pixel constants
- `SCBufferImpostorShaderP` -- Per-shader pixel constants
- `DeferredOutput_ImpostorConvert_c.hlsl` -- Compute shader converts 3D objects to impostor textures

The impostor system renders a simplified 2D representation of distant 3D objects, capturing their appearance from the current viewpoint. This dramatically reduces vertex count for forests.

**Confidence**: VERIFIED (RTTI class names, shader name)

### Block Culling (32m Grid)

The world is divided into a grid of 32-meter blocks. Culling operates at this granularity:
- `m_ZClipNbBlock` controls how many blocks are visible
- `m_ZClip` and `m_ZClipAuto` control the far clip distance
- Default far clip for TMF was 50,000m; TM2020 likely similar or larger

**Confidence**: VERIFIED (config fields), PLAUSIBLE (exact far clip for TM2020)

---

## 15. Minimum GPU Specification

### Required D3D11 Feature Level

From `CDx11Viewport::DeviceCreate` at `0x1409aa750`:

| Requirement | Value | Evidence |
|-------------|-------|----------|
| Minimum Feature Level | D3D10.0 (`0xa000`) | Lowest tier in fallback chain sets SM 4.0 |
| Recommended Feature Level | D3D11.0 (`0xb000`) | Required for SM 5.0, compute shaders |
| Minimum Shader Model | SM 4.0 (`0x400`) | `DAT_14201d2ec = 0x400` at minimum |
| Recommended Shader Model | SM 5.0 (`0x500`) | Required for compute shaders, UAVs |
| Compute Shader | Required for full features | HBAO+, GPU particles, volumetric fog, GPU culling |
| BGRA Support | Required | `D3D11_CREATE_DEVICE_BGRA_SUPPORT` flag (`0x20`) |

### Required Texture Formats

| Format | Usage | Evidence |
|--------|-------|----------|
| `B8G8R8A8_UNORM_SRGB` | Back buffer | D3D11 log |
| `D24_UNORM_S8_UINT` | Depth/stencil | D3D11 log |
| `R16G16B16A16_FLOAT` | HDR render targets, normals | Standard for deferred + HDR |
| `R8G8B8A8_UNORM` | G-buffer (diffuse, specular, mask) | Standard 8-bit channels |
| `R8G8B8A8_UNORM_SRGB` | Albedo textures | sRGB color space |
| `BC1/BC3/BC7` | Compressed textures | Standard DXT/BCn |
| 3D textures | Volumetric fog grid | `3DFog_RayMarching_c.hlsl` |

### Safe Mode Configuration

From `Default.json` `DisplaySafe` block -- the absolute minimum the engine can run at:

| Setting | Safe Mode Value |
|---------|----------------|
| Resolution | 800x450 windowed |
| AA | None |
| Deferred AA | None |
| Textures | Very Low |
| Filtering | Bilinear |
| Shadows | None |
| Bloom | None |
| Motion Blur | Off |
| Lightmap Indirect | Off |
| Threading | Single thread |
| Max FPS | 150 |
| GPU Sync | Immediate |

This represents the **absolute minimum viable rendering target** for a browser recreation.

**Confidence**: VERIFIED (actual game config values)

---

## 16. WebGPU Translation Guide

### D3D11 to WebGPU Feature Mapping

| D3D11 Feature | WebGPU Equivalent | Notes |
|---------------|------------------|-------|
| `ID3D11Device` | `GPUDevice` | Request with required features/limits |
| `ID3D11DeviceContext` | `GPUCommandEncoder` + `GPURenderPassEncoder` | Explicit command recording |
| `ID3D11RenderTargetView` (MRT) | `GPURenderPassDescriptor.colorAttachments[]` | Max 8 attachments |
| `ID3D11DepthStencilView` | `GPURenderPassDescriptor.depthStencilAttachment` | `depth24plus-stencil8` |
| `ID3D11Buffer` (cbuffer) | `GPUBuffer` (uniform) | `GPUBufferUsage.UNIFORM` |
| `ID3D11Buffer` (structured) | `GPUBuffer` (storage) | `GPUBufferUsage.STORAGE` |
| `ID3D11ComputeShader` + Dispatch | `GPUComputePassEncoder.dispatchWorkgroups()` | Full support |
| `ID3D11ShaderResourceView` | `GPUTextureView` + `GPUSampler` | Bind via bind groups |
| `ID3D11UnorderedAccessView` | Storage texture / storage buffer | `GPUStorageTextureAccess` |
| `DrawIndexedInstancedIndirect` | `GPURenderPassEncoder.drawIndexedIndirect()` | Full support |
| DXGI Swap Chain | `GPUCanvasContext.getCurrentTexture()` | `canvas.getContext('webgpu')` |
| Vertex Input Layout | `GPUVertexBufferLayout` | Per-pipeline, not global |
| HLSL | WGSL | Must be transpiled or rewritten |
| Tessellation (Hull/Domain) | NOT AVAILABLE | Must use alternative (geometry subdivision or compute) |
| Geometry Shader | NOT AVAILABLE | Must use compute alternatives |
| Occlusion Query | `GPUQuerySet` type `'occlusion'` | Available |

### Per-Pass WebGPU Implementation

| TM2020 Pass | WebGPU Implementation |
|-------------|----------------------|
| `SetCst_Frame` | `device.queue.writeBuffer()` for uniform buffers |
| `ShadowRenderPSSM` | 4 render passes to `depth32float` texture array layers |
| `DipCulling` | Compute pass writing to storage buffer (indirect args) |
| `DeferredWrite` | Render pass with 4 color attachments (MRT) + depth |
| `DeferredAmbientOcc` | Multiple compute passes (SSAO) or render passes |
| `CameraMotion` | Full-screen render pass outputting `rg16float` motion vectors |
| `DeferredLighting` | Full-screen render pass reading G-buffer via bind groups |
| `DeferredGeomLight*` | Stencil-marked light volume render passes |
| `SSLReflects` | Full-screen render pass with depth buffer + color as input |
| `ParticlesUpdate` | Compute pass on storage buffers |
| `FxToneMap` | Compute pass for luminance reduction + render pass for tone map |
| `FxBloom` | Chain of render passes at decreasing resolutions |
| `FxTXAA` | Render pass with history buffer + motion vectors as input |

### Required WebGPU Features and Limits

```javascript
const requiredFeatures = [
    'float32-filterable',         // HDR texture filtering
    'rg11b10ufloat-renderable',  // Compact HDR render targets
];

const requiredLimits = {
    maxColorAttachments: 4,               // G-buffer MRT
    maxBindGroups: 4,                     // Frame/Pass/Shader/Draw
    maxUniformBufferBindingSize: 65536,   // Large constant buffers
    maxStorageBufferBindingSize: 134217728, // GPU particle buffers (128MB)
    maxComputeWorkgroupSizeX: 256,        // Compute dispatches
    maxTextureDimension2D: 8192,          // Shadow map resolution
    maxTextureDimension3D: 256,           // Volumetric fog grid
    maxTextureArrayLayers: 256,           // Shadow cascade array
};
```

### Constant Buffer Mapping

D3D11 `cbuffer` to WebGPU bind group layout:

```
Bind Group 0 (per-frame, update 1x/frame):
  - Camera matrices (view, projection, viewProjection, prevViewProjection)
  - Time, delta time, wind parameters
  - Sun direction, ambient color
  - TAA jitter offset

Bind Group 1 (per-pass, update 1x/pass):
  - Shadow cascade matrices (4x VP)
  - Fog parameters (color, density, height)
  - AO parameters
  - Deferred lighting params

Bind Group 2 (per-material, update per material change):
  - Albedo, specular, normal texture bindings + samplers
  - Material constants (roughness, emissive factor)
  - Lightmap binding

Bind Group 3 (per-draw, update per draw call):
  - World matrix / instance transforms
  - Per-object constants (LOD level, wind influence)
```

---

## 17. Minimum Viable Renderer Specification

### Goal

A browser-based renderer that captures the essential visual character of Trackmania 2020 at the quality level of the game's "safe mode" settings, progressively enhanced.

### Tier 0: Absolute Minimum (WebGL2 compatible)

Renders the track with basic lighting. No compute shaders required.

| Feature | Implementation |
|---------|---------------|
| Geometry | Forward rendering, single pass |
| Lighting | 1 directional light (sun) + ambient |
| Shadows | None |
| AA | None |
| Textures | Albedo only |
| Resolution | 800x450 |
| Post-FX | None |

**Required formats**: `RGBA8`, `DEPTH24_STENCIL8`

### Tier 1: Basic Deferred (WebGPU required)

Deferred rendering with the core pipeline.

| Feature | Implementation |
|---------|---------------|
| G-Buffer | 4 MRT: albedo (`rgba8unorm-srgb`), specular (`rgba8unorm`), normal (`rg16float` octahedral), mask (`rgba8unorm`) + `depth24plus-stencil8` |
| Lighting | Deferred: 1 directional + point/spot lights |
| Shadows | 2-cascade PSSM (`depth32float` texture array) |
| AA | FXAA |
| Materials | Diffuse + specular + normal maps |
| Lightmaps | Sampled at UV1, multiplied with diffuse |
| Post-FX | Tone mapping (ACES or Khronos PBR Neutral) |

**Required features**: `float32-filterable`

### Tier 2: Full Quality (WebGPU with compute)

Matches the game's "High" quality preset.

| Feature | Implementation |
|---------|---------------|
| G-Buffer | Full 4 MRT + face normal reconstruction from depth |
| Lighting | Deferred with PBR (GGX BRDF LUT) |
| Shadows | 4-cascade PSSM with PCF + shadow cache |
| AA | TAA with motion vectors + history buffer |
| AO | SSAO (Scalable Ambient Obscurance -- simpler than HBAO+) |
| Fog | Analytical height fog + distance fog |
| Bloom | 4-level downsample chain |
| Particles | Compute shader update + billboard render |
| SSR | Half-res screen-space reflections |
| Post-FX | Full chain: tone map -> bloom -> TAA -> color grading |

**Required features**: `float32-filterable`, `rg11b10ufloat-renderable`

### Tier 3: Maximum (stretch goal)

Matches the game's "Ultra" quality.

| Feature | Implementation |
|---------|---------------|
| Full pipeline | All of Tier 2 plus: |
| AO | Dual-pass HBAO (small + big scale) |
| Fog | Ray-marched volumetric fog with 3D noise |
| Particles | Self-shadowing via compute voxelization |
| Water | Planar reflection + refraction + screen droplets |
| DoF | Physical camera DoF |
| Motion blur | Per-pixel velocity blur |

### Key Simplifications for Browser

1. **No tessellation**: WebGPU has no hull/domain shaders. Use mesh subdivision at load time or compute-based displacement.
2. **No geometry shaders**: Particle voxelization must use compute. Grass/forest instancing via vertex pulling from storage buffers.
3. **Simpler AO**: SAO instead of HBAO+ (no deinterleaving required, single compute pass).
4. **Simpler fog**: Analytical fog formula instead of ray marching (saves 3D texture + compute).
5. **Shadow atlas**: Pack 4 PSSM cascades into one large texture instead of texture arrays (wider compatibility).
6. **Fewer normal buffers**: Reconstruct face normals from depth derivatives in-shader instead of separate pass.

---

## Key Addresses Reference

| Address | Function | Section |
|---------|----------|---------|
| `0x1409aa750` | `CDx11Viewport::DeviceCreate` | Section 2 |
| `0x14095d430` | `CVisionViewport::VisibleZonePrepareShadowAndProjectors` | Section 5 |
| `0x14091f4e0` | `NSysCfgVision::SSSAmbOcc` registration | Section 6 |
| `0x14097cfb0` | `Vision::VisionShader_GetOrCreate` | Section 7 |
| `0x140936810` | `CSystemConfigDisplay` registration | Section 2 |
| `0x1409a45a0` | `CVisPostFx_BloomHdr` constructor | Section 9 |
| `0x14099dce0` | `CVisPostFx_ToneMapping` constructor | Section 9 |
| `0x142057f90` | Vendor ID global (Intel = `0x8086`) | Section 2 |
| `0x142057f98` | DXGI adapter info global | Section 2 |
| `0x14201d2ec` | Shader model version global (`0x400`/`0x500`) | Section 2 |

---

## Unknowns and Future Investigation

| Unknown | Priority | Where to Look |
|---------|----------|---------------|
| Exact G-buffer DXGI formats | HIGH | Decompile texture creation calls near `DeferredWrite` setup |
| G-buffer MRT count (4 vs 5 vs 6 simultaneous) | HIGH | Trace MRT setup in `CDx11RenderContext` |
| Shadow map resolution per quality tier | MEDIUM | Decompile shadow map allocation at `0x1409536f0` |
| PSSM split distances (logarithmic vs practical) | MEDIUM | Decompile `FUN_140a45310` (cascade setup) |
| Filmic tone curve exact parameters | MEDIUM | Decompile `NFilmicTone_PowerSegments` struct |
| Lightmap YCbCr compression exact format | MEDIUM | Analyze `LmCompress_HBasis_YCbCr4_c.hlsl` |
| TAA jitter pattern (Halton? rotated grid?) | MEDIUM | Trace `PosOffsetAA` generation |
| Normal encoding method (octahedral vs spheremap) | MEDIUM | Decompile `DeferredDeCompFaceNormal_p.hlsl` |
| `DeferredPreShade` buffer purpose | LOW | Trace write/read references to `"BitmapDeferredPreShade"` |
| `DelayGrassFences` in HBAO config | LOW | Trace flag usage in rendering |
| Exact shader variant meanings (indices 0-14) | LOW | Decompile `FUN_1403de0d0` (variant descriptor resolver) |
| `AlphaBlendSoap` material type | LOW | Trace string reference to rendering code |
| Shadow filtering method (PCF kernel size, PCSS?) | LOW | Decompile `DeferredShadowPssm_p.hlsl` logic |

---

*Document generated from decompiled code analysis. All findings are evidence-based with confidence levels marked. Code citations reference specific addresses and decompiled files in `decompiled/rendering/`.*

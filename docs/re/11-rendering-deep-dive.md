# Trackmania 2020 Rendering Pipeline

Trackmania 2020 renders each frame through a deferred shading pipeline built on Direct3D 11. The engine fills a G-buffer with material data, then accumulates lighting in screen space before compositing forward-rendered transparent objects and post-processing effects. This document covers every stage of that pipeline, from D3D11 device creation through final present.

## At a glance

The full frame breaks down into these stages:

1. **Shadow prep** -- Render 4-cascade PSSM shadow maps and cache static shadows.
2. **Scene prep** -- Update particles (compute), render cubemap reflections, sample lightmaps.
3. **G-buffer fill** -- GPU-cull geometry, then write albedo, specular, normals, and light mask to 4 render targets + depth.
4. **Screen-space passes** -- Sample shadows, compute HBAO+ ambient occlusion, generate motion vectors.
5. **Deferred lighting** -- Accumulate ambient, lightmap, point/spot/area lights into an HDR color buffer.
6. **Screen-space reflections** -- Ray-march the depth buffer with temporal reprojection.
7. **Forward/transparent** -- Trees (alpha-to-coverage), grass, alpha-blended objects, ghost cars, particles.
8. **Post-processing** -- Fog, lens flares, DoF, motion blur, tone mapping, bloom, FXAA/TXAA, color grading.
9. **Final output** -- MSAA resolve (if forward), stretch to back buffer, present.

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

---

## How the graphics API works

Trackmania 2020 uses Direct3D 11 exclusively. The engine defines structures for D3D12 root signatures (`NPlugGpuHlsl_D3D12::*`) and contains a single `"Vulkan"` string, but neither API is active at runtime.

### D3D11 imports

| Import | DLL | Address |
|--------|-----|---------|
| `D3D11CreateDevice` | `D3D11.DLL` | `EXTERNAL:0000000e` |
| `CreateDXGIFactory1` | `DXGI.DLL` | `EXTERNAL:0000000f` |

The `"RenderingApi"` configuration field (`m_RenderingApi` at offset `0xb0` in `CSystemConfigDisplay`) suggests the architecture supports multiple backends. Only D3D11 is wired up.

### Device creation

The D3D11 device is created in `CDx11Viewport::DeviceCreate` at `0x1409aa750`. This function:

1. Creates a DXGI factory via `CreateDXGIFactory1`.
2. Enumerates adapters.
3. Calls `D3D11CreateDevice` with `D3D11_CREATE_DEVICE_BGRA_SUPPORT` (`0x20`).
4. Negotiates feature levels and sets the shader model.
5. Queries MSAA support (1, 2, 4, 8 samples).
6. Handles device lost gracefully.

**Feature level tiers**:

| Feature Level | Hex Value | Shader Model | Evidence |
|--------------|-----------|-------------|----------|
| D3D11.1 | `0xb001` | SM 5.0+ | `0xafff < (int)*puVar2` check, sets `DAT_14201d2ec = 0x500` |
| D3D11.0 | `0xb000` | SM 5.0 | `(int)*puVar2 < 0xb000` |
| D3D10.1 | `0xa100` | SM 4.1 | `(int)*puVar2 < 0xa100` |
| D3D10.0 | `0xa000` | SM 4.0 | Minimum, sets `DAT_14201d2ec = 0x400` |

**Confidence**: VERIFIED

```c
// Shader model selection at 0x1409aad00
DAT_14201d2ec = 0x400;  // SM 4.0 default
if (0xafff < (int)*puVar2) {
    DAT_14201d2ec = 0x500;  // SM 5.0 if feature level >= 11.0
}
```

For feature level >= 11.1, the code queries `D3D11_FEATURE_D3D11_OPTIONS`:

```c
// At 0x1409aae22 -- CheckFeatureSupport
(**(code **)(**(longlong **)(param_1 + 0x3fe9) + 0xf0))
    (*(longlong **)(param_1 + 0x3fe9), 0x13, 8, &local_4148);
// 0x13 = D3D11_FEATURE_D3D11_OPTIONS (value 19)
```

**Confidence**: VERIFIED

The code checks for Intel vendor ID `0x8086` and applies driver version workarounds:

```c
// At 0x1409aaa68
if (((DAT_142057f98 != 0) && (DAT_142057f90 == 0x8086))
    && (DAT_142057f98 < 0xa0012000a1106)) {
    // Intel GPU with driver version below threshold
}
```

**Confidence**: VERIFIED

### Swap chain configuration

| Property | Value | Evidence |
|----------|-------|----------|
| Back buffer format | `DXGI_FORMAT_B8G8R8A8_UNORM_SRGB` | D3D11 log |
| Present mode | Immediate (no VSync) | D3D11 log |
| Buffer count | 3 (triple buffering) | D3D11 log: `Image count: 3` |
| Depth/Stencil format | `DXGI_FORMAT_D24_UNORM_S8_UINT` | D3D11 log |

**Confidence**: VERIFIED (runtime log from DXVK/CrossOver)

### Vertex formats

Captured from the D3D11 runtime log:

**Block geometry with vertex color (stride 56, 7 attributes)**:
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

**Lightmapped geometry (stride 52, 6 attributes)**:
```
attr 0: R32G32B32_SFLOAT    offset 0   (position)
attr 1: R16G16B16A16_SNORM  offset 12  (normal)
attr 2: R32G32_SFLOAT        offset 20  (UV0)
attr 3: R32G32_SFLOAT        offset 28  (UV1 / lightmap)
attr 4: R16G16B16A16_SNORM  offset 36  (tangent)
attr 5: R16G16B16A16_SNORM  offset 44  (bitangent)
```

**Simple geometry (stride 28, 3 attributes)**:
```
attr 0: R32G32B32_SFLOAT    offset 0   (position)
attr 1: R16G16B16A16_SNORM  offset 12  (normal)
attr 2: R32G32_SFLOAT        offset 20  (UV)
```

**Confidence**: VERIFIED (DXVK pipeline compilation log)

---

## How the G-buffer is organized

The engine uses 9 named render targets (RT). The core MRT during `DeferredWrite` binds 4 color targets + depth. Additional targets are written in separate sub-passes.

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

### Why three normal buffers?

Three separate normal buffers (face, vertex, pixel) serve distinct purposes.

**PixelNormalInC** is the final bump-mapped normal in camera space. Lighting calculations use this as the primary normal. It comes from tangent-space normal maps transformed to camera space during `DeferredWrite`.

**FaceNormalInC** is the geometric (flat) face normal. HBAO+ uses geometric normals for stable AO. FXAA/TXAA use geometric discontinuities for silhouette edge detection. Shadow bias computation needs the geometric surface angle. The shader `DeferredFaceNormalFromDepth_p.hlsl` can reconstruct face normals from depth via screen-space derivatives.

**VertexNormalInC** is the smooth vertex-interpolated normal. Bilateral blur filters use smooth normals to detect surface boundaries without bump map noise. Subsurface scattering needs the smooth normal, not the bump-mapped one.

**Confidence**: VERIFIED for existence (string references), PLAUSIBLE for per-buffer usage

### Normal encoding

The shader `DeferredDeCompFaceNormal_p.hlsl` confirms normals are stored compressed. **Octahedral encoding** (2x16 bits) is the most likely format -- standard practice for deferred renderers since 2014.

| Encoding | Bits | Quality | WebGPU Format |
|----------|------|---------|---------------|
| Octahedral (2-channel) | 2x16 = 32 bits | High | `rg16float` |
| Spheremap transform | 2x16 = 32 bits | Medium | `rg16snorm` |
| 3-channel uncompressed | 3x16 = 48 bits | Best | `rgba16float` (wastes A) |
| R10G10B10A2 | 32 bits | Medium | `rgb10a2uint` (WebGPU limited) |

**Confidence**: SPECULATIVE

### MDiffuse vs DiffuseAmbient

**MDiffuse** (`BitmapDeferredMDiffuse`) stores the **material** albedo/base color. The "M" prefix means "Material." Written during G-buffer fill.

**DiffuseAmbient** (`Bitmap_DeferredDiffuseAmbient`) stores the **lighting result** -- accumulated diffuse irradiance + ambient. Computed during `DeferredRead`/`DeferredReadFull` as `MDiffuse * (ambient + lightmap + indirect)`.

MDiffuse is an input (texture data). DiffuseAmbient is an output (lighting result).

**Confidence**: PLAUSIBLE

---

## How the deferred rendering pipeline works

The pipeline switches between deferred and forward paths. Deferred is the default. The string `"Current shading pipeline, if true Antialias_Deferred setting is used, otherwise it is Antialias_Forward."` confirms both paths exist.

- `"IsDeferred"` at `0x141cc3e88` controls the pipeline selection.
- Deferred AA options: FXAA, TXAA.
- Forward AA options: MSAA 2/4/6/8/16 samples.

### Pass-by-pass breakdown

Every pass name below is a verified string reference from the binary.

#### Phase 0: CPU frame setup

The CPU performs these tasks before GPU work begins:

1. **Input polling**: `CInputPort::Update_StartFrame` at `0x1402acea0`.
2. **Physics simulation**: Up to 100 resim steps per frame at 100 Hz tick rate.
3. **Scene graph update**: The `CHmsZone`/`CHmsZoneElem` hierarchy updates transforms. `NHmsMgrInstDyna::AsyncRender_ApplyDeferredChanges` manages dynamic instances.
4. **Visibility determination**: Per-zone visible set computed. Zone element array at `param_1 + 0x1a98` with count at `param_1 + 0x1aa0`.

The CPU writes per-frame constant buffers (camera matrices, time, sun direction) into mapped D3D11 buffers.

**Confidence**: VERIFIED

#### Phase 1: Frame constants and shadow prep

```
SetCst_Frame -> SetCst_Zone -> GenAutoMipMap
  -> ShadowCreateVolumes -> ShadowRenderCaster -> ShadowRenderPSSM -> ShadowCacheUpdate
```

`SetCst_Frame` is the first GPU pass. It uploads camera view/projection matrices, frame time, sun/light direction, and wind parameters. Shadow maps render to dedicated depth textures. The PSSM system renders 4 cascades. Static shadow maps are cached and only re-rendered when geometry changes.

**Confidence**: VERIFIED

#### Phase 2: Scene preparation

```
CreateProjectors -> UpdateTexture -> Decal3dDiscard
  -> ParticlesUpdateEmitters -> ParticlesUpdate
  -> CubeReflect -> LightFromMap -> WaterReflect
```

- **ParticlesUpdate**: GPU compute shader (`MgrParticleUpdate_c.hlsl`) updates all particle positions/velocities.
- **CubeReflect**: Renders a 6-face cubemap for dynamic reflections.
- **WaterReflect**: Renders planar reflection for water surfaces.
- **LightFromMap**: Samples baked lightmaps to apply environment lighting to dynamic objects (cars).

**Confidence**: VERIFIED

#### Phase 3: Environment pre-passes

```
CubeReflect -> TexOverlay -> LightFromMap -> VertexAnim
  -> Hemisphere -> LightOcc -> WaterReflect -> Underlays
```

**Confidence**: VERIFIED

#### Phase 4: G-buffer fill (deferred write)

```
DipCulling -> DeferredWrite -> DeferredWriteFNormal -> DeferredWriteVNormal
  -> DeferredDecals -> DeferredBurn
```

`DipCulling` runs a compute shader (`Instances_Cull_SetLOD_c.hlsl`) that performs GPU-side frustum culling and LOD selection, writing indirect draw arguments.

`DeferredWrite` renders all opaque geometry into the G-buffer MRT:

- **Blocks/terrain**: `Block_TDSN_DefWrite_p.hlsl` (Texture+Diffuse+Specular+Normal)
- **Cars**: `CarSkin_DefWrite_p.hlsl`
- **Trees**: `Tree_SelfAO_DefWrite_p.hlsl`

Normals are written in separate sub-passes:

- `DeferredWriteFNormal`: Face normals, reconstructed from depth via `DeferredFaceNormalFromDepth_p.hlsl`.
- `DeferredWriteVNormal`: Smooth vertex-interpolated normals.

`DeferredDecals` projects decals onto the G-buffer using `DeferredDecalGeom_p.hlsl`. `DeferredBurn` applies scorch/tire marks via `DeferredGeomBurnSphere_p.hlsl`.

**Confidence**: VERIFIED

#### Phase 5: Screen-space passes

```
DeferredShadow -> DeferredAmbientOcc -> DeferredFakeOcc -> CameraMotion
```

These passes read from the G-buffer and produce screen-space data:

- **DeferredShadow**: Samples 4 PSSM cascade shadow maps via `DeferredShadowPssm_p.hlsl`. Outputs a per-pixel shadow term.
- **DeferredAmbientOcc**: Runs NVIDIA HBAO+ (or Nadeo's custom `UseHomeMadeHBAO`) in a 6-step pipeline. May run twice (small-scale + big-scale) for dual-range AO.
- **DeferredFakeOcc**: Cheap approximate occlusion for distant objects via `DeferredGeomFakeOcc_p.hlsl`.
- **CameraMotion**: Per-pixel motion vectors via `DeferredCameraMotion_p.hlsl`. Used by TXAA and motion blur.

**Confidence**: VERIFIED

#### Phase 6: Deferred lighting

```
DeferredRead -> DeferredReadFull -> DeferredLighting -> Reflects_CullObjects
```

The lighting accumulation phase reads the full G-buffer and produces the lit HDR scene.

**DeferredRead** runs these shaders in sequence:

- `Deferred_SetILightDir_p.hlsl` -- Set indirect light direction from lightmap/probe data.
- `Deferred_AddAmbient_Fresnel_p.hlsl` -- Add ambient term with Fresnel at grazing angles.
- `Deferred_AddLightLm_p.hlsl` -- Add baked lightmap contribution.
- `Deferred_SetLDirFromMask_p.hlsl` -- Derive light direction from the LightMask buffer.

**DeferredReadFull** completes ambient/indirect lighting.

**DeferredLighting** renders light geometry (stencil-marked light volumes):

- `DeferredGeomLightBall_p.hlsl` -- Point lights (sphere proxy geometry).
- `DeferredGeomLightSpot_p.hlsl` -- Spot lights (cone proxy geometry).
- `DeferredGeomLightFxSphere_p.hlsl` -- Decorative sphere lights.
- `DeferredGeomLightFxCylinder_p.hlsl` -- Decorative cylinder lights.
- `DeferredGeomProjector_p.hlsl` -- Projected texture lights.

**Confidence**: VERIFIED

#### Phase 7: Screen-space reflections

```
SSLReflects -> SSLReflects_GlobalCube -> SSLReflects_Add
```

`SSReflect_Deferred_p.hlsl` traces rays in screen space using the depth buffer. `SSReflect_Deferred_LastFrames_p.hlsl` uses temporal reprojection from previous frames to fill gaps. Misses fall back to the global cubemap. Results are composited onto the scene.

**Confidence**: VERIFIED

#### Phase 8: Forward/transparent pass

```
ForestRender -> ForestRender_MSAA -> GrassUpdateInstances -> GrassRender
  -> ShadowRender -> Alpha01 -> AlphaBlend -> AlphaBlendSoap
  -> BufferRefract -> GhostLayer -> GhostLayerBlend
```

Objects that cannot be deferred-rendered are drawn here:

- **Trees/Forests**: Alpha-to-coverage MSAA for leaf edges.
- **Grass**: Instanced grass blades.
- **Alpha-tested geometry**: `Alpha01` pass for cutout materials.
- **Transparent objects**: `AlphaBlend` pass, sorted back-to-front.
- **Ghost cars**: Rendered to a separate layer then blended with configurable opacity.
- **Refraction**: `BufferRefract` captures the scene for refractive objects.

**Confidence**: VERIFIED

#### Phase 9: Particle rendering

```
ParticleSelfShadow_ComputeBBoxes -> ... -> ParticleSelfShadow_Propagation
VortexParticle -> VortexParticle_UpScale
ParticlesRender -> ParticlesRenderRefract -> ParticlesRender_UpScale
```

Self-shadowing uses a voxelization pipeline (geometry shader writes to 3D volume, then propagates shadow). Particles may render at reduced resolution and upscale.

**Confidence**: VERIFIED

#### Phase 10: Post-processing chain

```
DeferredFogVolumes -> DeferredFog -> LensFlares
  -> FxDepthOfField -> FxMotionBlur -> FxBlur
    -> FxColors -> FxColorGrading -> FxExtraOutput
```

Key ordering constraints:

- Fog applies before camera effects.
- Color grading is the final image adjustment.

**Confidence**: VERIFIED

#### Phase 11: Tone mapping, bloom, and AA

```
FxFXAA -> FxToneMap -> FxBloom -> CustomEnding
```

**Confidence**: VERIFIED

#### Phase 12: Final output

```
ResolveMsaaHdr -> ResolveMsaa -> StretchRect -> BlurAA -> DownSSAA -> SwapChainPresent
```

If MSAA was used (forward path only), it resolves here. Triple buffering uses 3 back buffers.

**Confidence**: VERIFIED

---

## How the shadow system works

The engine layers multiple shadow techniques for quality and performance. The primary technique is PSSM (Parallel-Split Shadow Maps) with 4 cascades for the directional sun light.

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

### PSSM cascade count

The cascade count is either 4 (standard) or 1 (simplified). Simplified mode triggers when `flag & 0x40` is set at offset `0x5d0`, likely the "Minimum" shadow quality setting.

```c
// At 0x14095d5b0 -- CVisionViewport::VisibleZonePrepareShadowAndProjectors
if ((*(byte *)(param_1 + 0x5d0) & 0x40) == 0) {
    uVar12 = 4;  // 4 cascades
} else {
    uVar12 = 1;  // 1 cascade (simplified mode)
}
```

**Confidence**: VERIFIED

### Shadow quality tiers

| Quality | Cascades | Behavior |
|---------|----------|----------|
| None | 0 | All shadow passes skipped |
| Minimum | 1 | Reduced resolution, single cascade |
| Medium | 4 | Standard resolution |
| High | 4 | Higher resolution |
| Very High | 4 | Maximum resolution + `HqSoftShadows` |

Player-specific shadow settings (`CSystemConfig::EPlayerShadow`): None / Me (own car only) / All.

**Confidence**: VERIFIED

### Shadow cache

The engine caches static shadow maps to avoid re-rendering. `ShadowCache/UpdateShadowIndex_c.hlsl` incrementally updates the cache via compute shader.

### Shadow groups

Each zone iterates shadow casters. Each caster has a group index (5-bit value at offset `0x22c`). A bitmask tracks which of up to 32 shadow groups are present per zone.

```c
// Caster mask computation at 0x14095d620
uVar13 = uVar13 | 1 << (*(byte *)(lVar7 + 0x22c) & 0x1f);
```

**Confidence**: VERIFIED

### PSSM configuration

| Property | Value | Evidence |
|----------|-------|----------|
| Cascades | 4 (default), 1 (simplified) | Decompiled logic + strings `"MapShadowSplit0"` - `"MapShadowSplit3"` |
| Filtering | PCF baseline + `"HqSoftShadows"` toggle | String references |
| Bias | `"ShadowBiasConstSlope"` -- slope-scaled depth bias | String reference |
| Alpha test | `"ShadowCasterAlphaRef"` / `"ShadowCasterAlphaCut"` | String references |

**Confidence**: VERIFIED for structure, SPECULATIVE for exact formats

---

## How HBAO+ ambient occlusion works

NVIDIA HBAO+ (Horizon-Based Ambient Occlusion) runs as a full post-processing pass. Nadeo also ships a custom fallback (`UseHomeMadeHBAO`). The engine runs HBAO+ twice at different scales: a small-scale pass for contact shadows and a big-scale pass for room-scale occlusion. The results are combined (likely multiplied).

### Configuration structure

`NSysCfgVision::SSSAmbOcc` registered at `0x14091f4e0`, size `0x4c` (76 bytes).

**Homemade AO parameters (offsets 0x00-0x18)**:

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `IsEnabled` | `0x00` | bool | Master AO enable/disable |
| `UseHomeMadeHBAO` | `0x04` | bool | Use Nadeo's custom AO instead of NVIDIA |
| `DelayGrassFences` | `0x08` | bool | Delays AO past grass/fence rendering |
| `ImageSize` | `0x0C` | float | AO render resolution scale |
| `WorldSize` | `0x10` | float | AO world-space radius (meters) |
| `Exponent` | `0x14` | float | AO falloff exponent |
| `BlurTexelCount` | `0x18` | int | Bilateral blur kernel radius |

**NVIDIA HBAO+ parameters (offsets 0x1C-0x30)**:

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `NvHBAO.Enabled` | `0x1C` | bool | NVIDIA HBAO+ enable |
| `NvHBAO.Radius` | `0x20` | float | World-space AO sampling radius |
| `NvHBAO.Bias` | `0x24` | float | Depth bias to prevent self-occlusion |
| `NvHBAO.LargeScaleAO` | `0x28` | float | Large-scale AO multiplier |
| `NvHBAO.SmallScaleAO` | `0x2C` | float | Small-scale AO multiplier |
| `NvHBAO.PowerExponent` | `0x30` | float | AO curve exponent |

**Big-scale pass (offsets 0x34-0x48)**: Same field layout as above, with wider sampling radius.

**Confidence**: VERIFIED

### HBAO+ shader pipeline

```
1. LinearizeDepth_p.hlsl       -- Convert hardware depth to linear eye-space Z
2. DeinterleaveDepth_p.hlsl    -- Split depth into 4x4 interleaved layers (16 quarter-res)
3. ReconstructNormal_p.hlsl    -- Reconstruct normals from depth derivatives
4. CoarseAO_p.hlsl / _g.hlsl  -- Main AO computation at quarter resolution
5. ReinterleaveAO_p.hlsl       -- Recombine 4x4 layers back to full resolution
6. BlurX_p.hlsl / BlurY_p.hlsl -- Separable bilateral blur (edge-preserving)
```

The `_g.hlsl` suffix on `CoarseAO` indicates a geometry shader variant for multi-layer rendering in a single pass.

**Confidence**: PLAUSIBLE (dual parameter sets strongly suggest dual pass)

---

## How the shader system works

Shaders are pre-compiled into binary packages and loaded at runtime. Version validation uses git hashes: `"Shader binary is not up to date (GitHash): %016I64x != %016I64x"`.

### Shader cache

`Vision::VisionShader_GetOrCreate` at `0x14097cfb0` implements thread-safe shader caching:

```c
plVar4 = *(longlong **)(param_2 + 0x18);  // Check if cached
if (plVar4 == (longlong *)0x0) {
    // Cache miss -- lock mutex, create via vtable offset 0x770, store at offset 0x18
    FUN_14013c560(param_1 + 0x214, local_148);
    plVar4 = (**(code **)(*param_1 + 0x770))(param_1, param_2, 0);
    *(longlong **)(param_2 + 0x18) = plVar4;
    FUN_1401560e0(param_1 + 0x216, local_148);
}
return plVar4;
```

Constant `0x3108` is a shader format/version identifier.

**Confidence**: VERIFIED

### Shader variant system

The function creates up to 14 shader variants per material:

| Variant | Purpose |
|---------|---------|
| 0 | Default rendering |
| 1 | Depth-only / Z-prepass |
| 2 | [UNKNOWN] possibly tessellation |
| 3 | Shadow caster |
| 7 | Advanced feature (SSR? TXAA?) -- requires viewport flag `0x8000` |
| 13 | [UNKNOWN] possibly alpha test |
| 14 | Tessellation/LOD shader |

**Confidence**: VERIFIED

### Tech3 naming convention

```
Tech3/<ObjectType>_<TextureSlots>_<Pipeline>_<Stage>.hlsl

Examples:
  Tech3/Block_TDSN_DefWrite_p.hlsl
  |     |     |    |        |
  |     |     |    |        +-- Stage: p=pixel, v=vertex, g=geometry, c=compute
  |     |     |    +-- Pipeline: DefWrite=G-buffer fill, DefRead=lighting
  |     |     +-- Passes: T=Texture, D=Diffuse, S=Specular, N=Normal
  |     +-- Object type: Block, CarSkin, Tree, Sea, etc.
  +-- Framework version (3rd generation)
```

Additional tokens: `Py`/`Pxz` = triplanar projection modes, `COut`/`CIn` = color output/input, `SI` = self-illumination, `LM0`/`LM1`/`LM2` = lightmap variants.

**Confidence**: VERIFIED

### Shader quality levels

`CSystemConfigDisplay::EShaderQ`: `"Very Fast"`, `"Fast"`, `"Nice"`, `"Very Nice"`.

### CPlugShader class hierarchy

| Class | Purpose |
|-------|---------|
| `CPlugShader` | Base shader class |
| `CPlugShaderApply` | Applied shader instance |
| `CPlugShaderPass` | Single render pass within a shader |
| `CPlugShaderGeneric` | Generic/configurable shader |
| `CPlugShaderCBufferStatic` | Static constant buffer |
| `CPlugBitmapShader` | Bitmap/texture shader |

---

## How shader constant buffers are organized

All `SCBuffer*` classes represent D3D11 cbuffer structures. The naming convention maps directly to WebGPU bind group frequency.

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
+------------------------------------------------------------------+
```

**Confidence**: VERIFIED (all 42 names from RTTI `class_hierarchy.json`)

---

## How post-processing works

### Bloom HDR

`CVisPostFx_BloomHdr` (class ID `0xC032000`, size `0x168`). Pipeline:

```
1. BloomSelectFilterDown2_p.hlsl   -- Threshold + 2x downsample
2. BloomSelectFilterDown4_p.hlsl   -- 4x downsample
3. Bloom_HorizonBlur_p.hlsl       -- Horizontal Gaussian blur per mip
4. Bloom_StreaksWorkDir_p.hlsl     -- Directional light streaks (anamorphic)
5. Bloom_StreaksSelectSrc_p.hlsl   -- Select streak source intensity
6. Bloom_Final_p.hlsl             -- Composite bloom back to HDR buffer
```

Configuration: `"BloomIntensUseCurve"`, `"MinIntensInBloomSrc"` (threshold), `"Bloom_Down%d"` (multi-level targets). Quality levels: None, Medium, High.

**Confidence**: VERIFIED

### Tone mapping

`CVisPostFx_ToneMapping` (class ID `0xC030000`, size `0x6F0`).

Luminance computation (auto-exposure):

```
1. TM_GetLumi_p.hlsl              -- Extract luminance from HDR
2. TM_GetLog2LumiDown1_p.hlsl     -- Log2 luminance + progressive downsample
3. TM_GetAvgLumiCurr_p.hlsl       -- Average luminance (current frame)
```

Tone map operators (selectable):

```
4. TM_GlobalOp_p.hlsl             -- Global Reinhard-style
5. TM_GlobalOpAutoExp_p.hlsl      -- Global with auto-exposure
6. TM_GlobalFilmCurve_p.hlsl      -- Filmic curve (piecewise power segments)
7. TM_LocalOp_p.hlsl              -- Local per-pixel adaptive
```

The filmic curve uses `"NFilmicTone_PowerSegments::SCurveParamsUser"` -- a piecewise power function model similar to Hable/Uncharted 2 but parameterized as power segments.

**Confidence**: VERIFIED

### Motion blur

- **Shader**: `Effects/MotionBlur2d_p.hlsl` -- 2D per-pixel velocity-based blur.
- **Intensity**: `"MotionBlur2d.Intensity01"` (0.0 to 1.0).
- **Quality**: On / Off.

**Confidence**: VERIFIED

### Depth of field

- **Shader**: `Effects/PostFx/DoF_T3_BlurAtDepth_p.hlsl`.
- **Parameters**: `"FxDOF_FocalBlur_InvZ_MAD"`, `"DofLensSize"`, `"DofFocusZ"`, `"DofSampleCount"`.
- **High quality**: `"VideoHqDOF"` for video recording.

### Anti-aliasing

**FXAA**: `Effects/PostFx/FXAA_p.hlsl`, referenced as `"DeferredAntialiasing| FXAA"`.

**TXAA**: Two implementations exist:

- **NVIDIA GFSDK TXAA** (hardware path): `GFSDK_TXAA_DX11_InitializeContext` at `0x141c0f120`, `GFSDK_TXAA_DX11_ResolveFromMotionVectors` at `0x141c0f178`.
- **Ubisoft custom TXAA** (software fallback): `Effects/TemporalAA/TemporalAA_p.hlsl`, referenced as `"UBI_TXAA"`.

The `CameraMotion` pass generates per-pixel motion vectors via `DeferredCameraMotion_p.hlsl`. Each frame applies a sub-pixel jitter (`"PosOffsetAA"`) to the projection matrix.

**Confidence**: VERIFIED

### Color grading

- `Effects/PostFx/ColorGrading_p.hlsl` -- LUT-based 3D color grading.
- `Effects/PostFx/Colors_p.hlsl` -- Brightness, contrast, saturation.
- `Effects/PostFx/ColorBlindnessCorrection_p.hlsl` -- Accessibility filter.

---

## How materials and PBR work

### Material class hierarchy

```
CPlugMaterial (base)
  +-- CPlugMaterialCustom       -- User-customizable
  +-- CPlugMaterialUserInst     -- Instance override
  +-- CPlugMaterialPack         -- Packed collection
  +-- CPlugMaterialFx           -- Single FX
  +-- CPlugMaterialFxs          -- Multiple FX
  +-- CPlugMaterialFxDynaBump   -- Dynamic bump (water ripples)
  +-- CPlugMaterialFxDynaMobil  -- Animated material (conveyor, scroll)
  +-- CPlugMaterialFxFur        -- Fur/grass shell rendering
  +-- CPlugMaterialWaterArray   -- Water collection
```

**Confidence**: VERIFIED (RTTI)

### PBR workflow: specular/glossiness

The engine uses a **specular/glossiness** PBR workflow (not metallic/roughness). Evidence:

- `Pbr_Spec_to_Roughness_c.hlsl` converts specular to roughness.
- Separate `MDiffuse` and `MSpecular` G-buffer targets (specular workflow stores F0 color in specular).
- GGX/Cook-Torrance BRDF with a pre-computed integration LUT (`Pbr_IntegrateBRDF_GGX_c.hlsl`), indexed by NdotV and roughness.

**Material texture slots**:

| Slot | Name | G-Buffer Target | Description |
|------|------|-----------------|-------------|
| T | Texture/Albedo | -- | Base color texture |
| D | Diffuse | `MDiffuse` | Diffuse color to G-buffer |
| S | Specular | `MSpecular` | Specular F0 + roughness |
| N | Normal | `PixelNormalInC` | Tangent-space normal map |
| SI | Self-Illumination | `PreShade` [SPECULATIVE] | Emissive texture |
| LM | Lightmap | via `Deferred_AddLightLm` | Pre-baked lighting (UV1) |

**Confidence**: PLAUSIBLE

### Lightmap integration

The lightmap system uses **H-basis** encoding with **YCbCr compression**:

- `LmCompress_HBasis_YCbCr4_c.hlsl` compresses lightmaps.
- `LmLBumpILighting_Inst_p.hlsl` samples bumped indirect lighting.
- `ProbeGrid_Sample_c.hlsl` samples light probe grids for dynamic objects.
- `NHmsLightMap::YCbCr_to_RGB` decodes YCbCr.

Block geometry has two UV channels: UV0 for material textures and UV1 for lightmap. During `Deferred_AddLightLm`, the lightmap at UV1 is multiplied with `MDiffuse` to produce `DiffuseAmbient`. H-basis encoding enables per-pixel directional lighting from the lightmap.

**Confidence**: VERIFIED

---

## How the particle system works

The particle system is GPU-driven with compute shaders for simulation and vertex/pixel shaders for rendering.

### Core pipeline

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

### Self-shadowing via voxelization

```
1. ParticleSelfShadow_ComputeBBoxes    -- Compute bounding boxes
2. ParticleSelfShadow_Voxelization     -- Voxelize via geometry shader
3. ParticleSelfShadow_Propagation      -- Propagate shadow through volume
4. ParticleSelfShadow_OpaqueShadow     -- Apply opaque occluder shadows
5. ParticleSelfShadow_Render           -- Render self-shadow
6. ParticleSelfShadow_Merge            -- Merge with scene
```

### GPU load management

`"ParticleMaxGpuLoadMs"` (offset `0xB4` in `CSystemConfigDisplay`) sets the GPU time budget. The system dynamically reduces particle count to stay within budget. Quality levels: `"All Low"`, `"All Medium"`, `"All High"`, `"High,Medium Opponents"`.

**Confidence**: VERIFIED

---

## How water, fog, and special effects work

### Water rendering

Water combines reflection, refraction, surface shading, and particle effects.

- **Reflection**: `WaterReflect` pass renders planar reflection. Quality: `"WaterReflect"` from `very_fast` through `ultra`.
- **Refraction**: `BufferRefract` captures the scene for underwater distortion.
- **Surface**: `Sea_*` shaders render the water mesh. `SCBufferV_Sea` holds wave parameters.
- **Water fog**: `DeferredWaterFog_p.hlsl` for full-screen, `WaterFogFromDepthH_p.hlsl` for height-based density.
- **Splashes**: `WaterSplash_IntersectTriangles_p.hlsl` performs GPU triangle intersection for splash spawning.
- **Camera droplets**: `CameraWaterDroplets_Spawn_c.hlsl` / `_Update_c.hlsl` / `_Render_p.hlsl` for screen-space lens droplets.
- **Wetness**: `WetnessValue01` on `CSceneVehicleVisState` (0-1) drives wet car appearance.

**Confidence**: VERIFIED

### Volumetric fog

Full 3D volumetric fog with ray marching through a froxel grid:

```
VolumetricFog_ComputeScattering -> VolumetricFog_IntegrateScattering -> VolumetricFog_ApplyFog
```

Shaders: `3DFog_RayMarching_c.hlsl`, `3DFog_ComputeInScatteringAndDensity_c.hlsl`, `3DFog_BlendInCamera_p.hlsl`, `3DFog_UpdateNoiseTexture_c.hlsl`.

**Fog box volumes** (`DeferredFogVolumes` pass) are artistic fog shapes placed by map editors: `DeferredGeomFogBoxOutside_p.hlsl` / `DeferredGeomFogBoxInside_p.hlsl`.

**Global fog**: `DeferredFogGlobal_p.hlsl` during `DeferredFog` pass.

**Confidence**: VERIFIED

### Lens flares

- **Occlusion test**: `LensFlareOccQuery_v.hlsl` renders a small quad at the light position.
- **Rendering**: `2dFlareAdd_Hdr_p.hlsl` composites flare sprites in HDR.
- **Lens dirt**: `2dLensDirtAdd_p.hlsl` overlays dirt modulated by bloom brightness.

### Screen-space reflections

- `SSReflect_Deferred_p.hlsl` -- Ray marching in screen space.
- `SSReflect_Deferred_LastFrames_p.hlsl` -- Temporal accumulation from previous frames.
- `SSReflect_UpSample_p.hlsl` -- Half-res upsampled to full res.

### Subsurface scattering

`Effects/SubSurface/SeparableSSS_p.hlsl` implements Jorge Jimenez's separable SSS technique. Applied to car paint and translucent materials.

**Confidence**: VERIFIED

---

## How LOD and culling work

### GPU frustum culling

The `DipCulling` pass runs `Instances_Cull_SetLOD_c.hlsl` for GPU-side frustum culling + LOD selection. This writes `DrawIndexedInstancedIndirect` arguments consumed by the GPU without CPU readback.

- `Instances_Merge_c.hlsl` merges culled instance lists.
- `IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl` sets up indirect draw arguments per LOD and shadow group.

### Forward+ tile culling

`ForwardTileCull_c.hlsl` divides the screen into tiles and assigns lights per tile. Used for transparent objects in the forward pass.

### LOD distance control

`m_GeomLodScaleZ` at offset `0xEC` in `CSystemConfigDisplay` controls LOD transition distances. Values > 1.0 make objects simplify at closer range. The block culling grid uses 32m units: `Math::Ceil(distance / 32.0f)`.

### Impostor system

Distant trees render as billboard impostors. `DeferredOutput_ImpostorConvert_c.hlsl` converts 3D objects to impostor textures via compute shader. The `SCBufferDrawV_TreeImpostor` holds billboard transforms.

**Confidence**: VERIFIED

---

## How the CDx11 wrapper layer works

The engine wraps D3D11 through a `CDx11*` class hierarchy identified from string references:

| Class | Evidence | Purpose |
|-------|----------|---------|
| `CDx11Viewport` | `"CDx11Viewport::DeviceCreate"` | Manages device, swap chain, fullscreen |
| `CDx11RenderContext` | `"CDx11RenderContext::CopyFromStagingBuffer"` | Wraps `ID3D11DeviceContext`, draw calls |
| `CDx11Texture` | `"[Dx11] Failed to create Texture..."` | Texture creation/management |
| [UNKNOWN] CDx11Shader | `"[Dx11] ComputeShaders_Plus_RawAndStructuredBuffers_Via_Shader_4_x"` | Shader compilation |

Key D3D11 operations logged: `"D3D11DeviceContext::Flush"`, `"D3D11::UpdateSubresource"`, `"D3D11::Map"` / `"D3D11::Unmap"`, `"GpuCache_D3D11"`.

---

## How the Vision engine subsystem works

The rendering engine is called **Vision** (Nadeo's custom engine). `CVisionViewport` is the central orchestrator.

| Method | Address | Purpose |
|--------|---------|---------|
| `VisibleZonePrepareShadowAndProjectors` | `0x14095d430` | Shadow preparation per visible zone |
| `Shadow_UpdateGroups` | `0x140a43610` | Shadow group management |
| `AllShaderBindTextures` | `0x14097ed30` | Bind all shader textures |
| `OnDebugValueChanged_ReCompileShaders` | referenced | Runtime shader recompilation |

Low-level utilities in the `NVis` namespace handle MSAA resolve, GPU triangle intersection, and vertex transforms at SM3/SM4 levels.

---

## How the scene graph works

The scene graph uses a hierarchical system prefixed `CHms` (Hierarchical Management System).

| Class | Purpose |
|-------|---------|
| `CHmsShadowGroup` | Shadow group management |
| `CHmsLightMap` | Lightmap management |
| `CHmsMgrVisParticle` | Visual particle manager |
| `NHmsMgrInstDyna` | Dynamic instance manager |

The `SHms*` structs define render state: `"SHmsFxBloomHdr"`, `"SHmsFxToneMap"`, `"SHmsPostFxState"`. The Hms system logs configuration at startup: `"[Hms] Shadows="`, `"[Hms] ShaderQuality="`.

---

## Display configuration (CSystemConfigDisplay)

`CSystemConfigDisplay` registered at `0x140936810`, class ID `0xB013000`, size `0x160` bytes.

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `m_AdapterDesc` | `0x20` | string | GPU adapter description |
| `m_ScreenSizeFS` | `0x40` | int2 | Fullscreen resolution |
| `m_ScreenSizeWin` | `0x48` | int2 | Windowed resolution |
| `m_Antialiasing` | `0x4C` | enum | Forward AA (MSAA samples) |
| `m_DeferredAA` | `0x50` | enum | Deferred AA (None/FXAA/TXAA) |
| `m_RefreshRate` | `0x54` | int | Refresh rate |
| `m_DisplaySync` | `0x58` | enum | VSync mode |
| `m_TripleBuffer` | `0x68` | enum | Triple buffering |
| `m_AllowVRR` | `0x74` | bool | Variable refresh rate |
| `TexturesQuality` | `0x84` | enum | Texture quality |
| `m_ShaderQuality` | `0x88` | enum | Shader quality |
| `m_FilterAnisoQ` | `0x8C` | enum | Anisotropic filtering |
| `m_Shadows` | `0x90` | enum | Shadow quality |
| `m_RenderingApi` | `0xB0` | enum | Rendering API selection |
| `m_ParticleMaxGpuLoadMs` | `0xB4` | float | Particle GPU budget (ms) |
| `m_FxBloomHdr` | `0xCC` | enum | Bloom HDR quality |
| `m_ZClip` | `0xDC` | float | Z-clip distance |
| `m_ZClipAuto` | `0xE0` | bool | Auto Z-clip |
| `m_ZClipNbBlock` | `0xE4` | int | Z-clip block count |
| `m_GeomLodScaleZ` | `0xEC` | float | Geometry LOD scale |

---

## Minimum GPU specification

| Requirement | Value | Evidence |
|-------------|-------|----------|
| Minimum Feature Level | D3D10.0 (`0xa000`) | Lowest tier sets SM 4.0 |
| Recommended Feature Level | D3D11.0 (`0xb000`) | Required for SM 5.0, compute shaders |
| Minimum Shader Model | SM 4.0 (`0x400`) | `DAT_14201d2ec = 0x400` at minimum |
| Recommended Shader Model | SM 5.0 (`0x500`) | Required for compute, UAVs |
| BGRA Support | Required | `D3D11_CREATE_DEVICE_BGRA_SUPPORT` flag |

### Required texture formats

| Format | Usage |
|--------|-------|
| `B8G8R8A8_UNORM_SRGB` | Back buffer |
| `D24_UNORM_S8_UINT` | Depth/stencil |
| `R16G16B16A16_FLOAT` | HDR render targets, normals |
| `R8G8B8A8_UNORM` | G-buffer (diffuse, specular, mask) |
| `BC1/BC3/BC7` | Compressed textures |
| 3D textures | Volumetric fog grid |

### Safe mode configuration

The absolute minimum the engine runs at (from `Default.json` `DisplaySafe`):

| Setting | Safe Mode Value |
|---------|----------------|
| Resolution | 800x450 windowed |
| AA | None |
| Textures | Very Low |
| Filtering | Bilinear |
| Shadows | None |
| Bloom | None |
| Motion Blur | Off |
| Threading | Single thread |
| Max FPS | 150 |

**Confidence**: VERIFIED

---

## WebGPU translation guide

### D3D11 to WebGPU feature mapping

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
| HLSL | WGSL | Must be transpiled or rewritten |
| Tessellation (Hull/Domain) | NOT AVAILABLE | Pre-tessellate or use compute |
| Geometry Shader | NOT AVAILABLE | Use compute alternatives |
| Occlusion Query | `GPUQuerySet` type `'occlusion'` | Available |

### Per-pass WebGPU implementation

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
| `SSLReflects` | Full-screen render pass with depth + color as input |
| `ParticlesUpdate` | Compute pass on storage buffers |
| `FxToneMap` | Compute pass for luminance reduction + render pass for tone map |
| `FxBloom` | Chain of render passes at decreasing resolutions |
| `FxTXAA` | Render pass with history buffer + motion vectors as input |

### Required WebGPU features and limits

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

### Constant buffer mapping to bind groups

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

## Minimum viable renderer specification

### Tier 0: Absolute minimum (WebGL2 compatible)

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

### Tier 1: Basic deferred (WebGPU required)

| Feature | Implementation |
|---------|---------------|
| G-Buffer | 4 MRT: albedo, specular, normal (octahedral), mask + depth |
| Lighting | Deferred: 1 directional + point/spot lights |
| Shadows | 2-cascade PSSM |
| AA | FXAA |
| Materials | Diffuse + specular + normal maps |
| Lightmaps | Sampled at UV1, multiplied with diffuse |
| Post-FX | Tone mapping (ACES or Khronos PBR Neutral) |

### Tier 2: Full quality (WebGPU with compute)

| Feature | Implementation |
|---------|---------------|
| Lighting | Deferred with PBR (GGX BRDF LUT) |
| Shadows | 4-cascade PSSM with PCF + shadow cache |
| AA | TAA with motion vectors + history buffer |
| AO | SSAO (Scalable Ambient Obscurance) |
| Fog | Analytical height fog + distance fog |
| Bloom | 4-level downsample chain |
| Particles | Compute shader update + billboard render |
| SSR | Half-res screen-space reflections |
| Post-FX | Full chain: tone map, bloom, TAA, color grading |

### Tier 3: Maximum (stretch goal)

| Feature | Implementation |
|---------|---------------|
| AO | Dual-pass HBAO (small + big scale) |
| Fog | Ray-marched volumetric fog with 3D noise |
| Particles | Self-shadowing via compute voxelization |
| Water | Planar reflection + refraction + screen droplets |
| DoF | Physical camera DoF |
| Motion blur | Per-pixel velocity blur |

### Key simplifications for browser

1. **No tessellation**: Use mesh subdivision at load time or compute displacement.
2. **No geometry shaders**: Use compute for particle voxelization. Use vertex pulling for grass/forest instancing.
3. **Simpler AO**: SAO instead of HBAO+ (single compute pass, no deinterleaving).
4. **Simpler fog**: Analytical fog formula instead of ray marching.
5. **Shadow atlas**: Pack 4 PSSM cascades into one texture instead of arrays.
6. **Fewer normal buffers**: Reconstruct face normals from depth derivatives in-shader.

---

## Unknowns and open questions

- The exact CDx11Device class -- whether it exists separately from CDx11Viewport.
- Full G-buffer DXGI formats (buffer names known, pixel formats require tracing texture creation).
- The `"PreShade"` deferred buffer purpose.
- Whether forward rendering is used for main scene geometry or only UI/transparent objects.
- The `"UseHomeMadeHBAO"` implementation details.
- Complete `CVisionViewport` struct layout and vtable.
- The `"Dxgi_Present_HookCallback"` export at `0x140a811a0`.
- Which D3D 11.1+ features (`"11_1_SHADER_EXTENSIONS"`, `"VIEWPORT_AND_RT_ARRAY_INDEX_FROM_ANY_SHADER_FEEDING_RASTERIZER"`) are actually used.
- The exact TXAA jitter pattern (Halton(2,3) or rotated grid).

---

## Key addresses reference

| Address | Function | Section |
|---------|----------|---------|
| `0x1409aa750` | `CDx11Viewport::DeviceCreate` | Graphics API |
| `0x14095d430` | `CVisionViewport::VisibleZonePrepareShadowAndProjectors` | Shadow system |
| `0x14091f4e0` | `NSysCfgVision::SSSAmbOcc` registration | HBAO+ |
| `0x14097cfb0` | `Vision::VisionShader_GetOrCreate` | Shader system |
| `0x140936810` | `CSystemConfigDisplay` registration | Display config |
| `0x140053470` | `CVisPostFx_BloomHdr` class registration | Post-processing |
| `0x140053250` | `CVisPostFx_ToneMapping` class registration | Post-processing |
| `0x1400532f0` | `CVisPostFx_MotionBlur` class registration | Post-processing |
| `0x14097ed30` | `CVisionViewport::AllShaderBindTextures` | Shader system |
| `0x140a24ac0` | `MgrParticle_Update` | Particle system |

---

## Related Pages

- [00-master-overview.md](00-master-overview.md) -- Master index of all RE documentation.
- [02-class-hierarchy.md](02-class-hierarchy.md) -- Full RTTI class hierarchy including rendering classes.
- [15-ghidra-research-findings.md](15-ghidra-research-findings.md) -- Ghidra decompilation findings.
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Browser recreation architecture.
- [23-visual-reference.md](23-visual-reference.md) -- Visual reference for rendering effects.
- [32-shader-catalog.md](32-shader-catalog.md) -- Complete shader inventory (1,112 shaders).

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
**Sources**: Decompiled functions (`decompiled/rendering/`), RTTI class hierarchy (`class_hierarchy.json`), D3D11 runtime log, string references, Openplanet plugin intelligence
**Purpose**: Exhaustive rendering pipeline documentation for WebGPU recreation
**Related decompiled code**: `decompiled/rendering/`

</details>

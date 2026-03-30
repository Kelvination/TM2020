# OpenTM Renderer Design

**Purpose**: Exact WebGPU rendering pipeline specification for reproducing TM2020's visual quality at interactive frame rates in a browser.

**Date**: 2026-03-27

**Sources**: All reverse-engineering documents (11, 15, 19, 28, 32) cross-referenced for every design decision.

---

## Table of Contents

1. [Pipeline Architecture (4 Tiers)](#1-pipeline-architecture-4-tiers)
2. [G-Buffer Design](#2-g-buffer-design)
3. [Shader Architecture](#3-shader-architecture)
4. [Mesh Pipeline](#4-mesh-pipeline)
5. [Shadow System](#5-shadow-system)
6. [Post-Processing Chain](#6-post-processing-chain)
7. [Asset Loading Pipeline](#7-asset-loading-pipeline)
8. [The Block Mesh Problem (CRITICAL)](#8-the-block-mesh-problem-critical)
9. [Performance Optimization Strategy](#9-performance-optimization-strategy)
10. [WebGPU Feature Requirements](#10-webgpu-feature-requirements)
11. [Unknown Analysis](#11-unknown-analysis)

---

## 1. Pipeline Architecture (4 Tiers)

The renderer is designed as four progressive tiers. Each tier adds rendering features and GPU requirements. A browser client probes device capabilities at startup and selects the highest supported tier.

### Tier 0: Absolute Minimum (Forward Rendering)

**Goal**: Render a visible track with basic lighting. Fallback for low-end devices or WebGL2 polyfill.

**Passes that run**:

| Pass | Description |
|------|-------------|
| DepthPrepass | Z-only pass for all opaque geometry |
| ForwardLit | Single-pass forward shading: 1 directional light (sun) + hemisphere ambient |
| SkyDome | Fullscreen sky gradient or cubemap |
| UIOverlay | 2D HUD composited on top |

**Render targets**:

| Target | Format | Resolution | Purpose |
|--------|--------|------------|---------|
| Color | `bgra8unorm` | Native | Final output (no HDR) |
| Depth | `depth24plus` | Native | Depth buffer |

**Resolution strategy**: Fixed 800x450 or native resolution capped at 1280x720. No dynamic scaling.

**GPU feature requirements**: None beyond baseline WebGPU. No compute shaders. No storage buffers. No MRT.

**Expected performance**: 60 fps on integrated Intel UHD 620 class. Draw call budget: ~500.

---

### Tier 1: Basic Deferred (Core Pipeline)

**Goal**: Deferred rendering with the core TM2020 pipeline structure. Achieves the game's "Medium" quality appearance.

**Passes that run**:

| Pass | Description | TM2020 Equivalent |
|------|-------------|-------------------|
| ShadowCascades | 2-cascade PSSM shadow maps | ShadowRenderPSSM (reduced) |
| GBufferFill | 4 MRT G-buffer write for all opaque geometry | DeferredWrite |
| FaceNormalReconstruct | Reconstruct geometric normals from depth derivatives | DeferredWriteFNormal |
| DeferredShadow | Sample shadow cascades per pixel | DeferredShadow |
| DeferredAmbient | Ambient + Fresnel + lightmap contribution | DeferredRead |
| DeferredLighting | Point/spot light accumulation via light volumes | DeferredLighting |
| ForwardTransparent | Alpha-blended objects (glass, particles) | AlphaBlend |
| SkyDome | Sky rendering | Sky |
| FogGlobal | Analytical distance + height fog | DeferredFog |
| ToneMap | Filmic tone mapping + auto-exposure | FxToneMap |
| FXAA | Fast approximate AA | FxFXAA |
| UIOverlay | HUD | Overlays |

**Render targets**:

| Target | Format | Resolution | Purpose |
|--------|--------|------------|---------|
| GBuffer RT0 (Albedo) | `rgba8unorm-srgb` | Native | Diffuse color + material flags |
| GBuffer RT1 (Specular) | `rgba8unorm` | Native | F0 reflectance RGB + roughness A |
| GBuffer RT2 (Normal) | `rg16float` | Native | Octahedral-encoded pixel normal XY |
| GBuffer RT3 (LightMask) | `rgba8unorm` | Native | Per-channel light mask flags |
| Depth | `depth24plus-stencil8` | Native | Depth + stencil for light volumes |
| HDR Accumulation | `rgba16float` | Native | Lit scene accumulation |
| Shadow Cascade 0 | `depth32float` | 2048x2048 | Near shadow map |
| Shadow Cascade 1 | `depth32float` | 2048x2048 | Far shadow map |

**Resolution strategy**: Native resolution up to 1920x1080. No dynamic scaling.

**GPU feature requirements**: `float32-filterable` for shadow map comparison sampling. 4 color attachments (MRT). Stencil for light volumes.

**Expected performance**: 60 fps on NVIDIA GTX 1060 / Apple M1 class. Draw call budget: ~2000.

---

### Tier 2: Full Quality (Compute-Enhanced)

**Goal**: Match TM2020 "High" quality. Full deferred pipeline with PBR, SSAO, TAA, bloom.

**Passes that run**:

All of Tier 1 plus:

| Pass | Description | TM2020 Equivalent |
|------|-------------|-------------------|
| GPUCull | Compute: frustum cull + LOD selection, write indirect args | DipCulling |
| ShadowCascades | 4-cascade PSSM (upgraded from 2) | ShadowRenderPSSM (full) |
| SSAO | Scalable Ambient Obscurance (single compute pass) | DeferredAmbientOcc (simplified) |
| MotionVectors | Per-pixel camera motion vectors | CameraMotion |
| SSR | Half-resolution screen-space reflections | SSLReflects |
| Bloom | 4-level downsample/blur chain | FxBloom |
| TAA | Temporal AA with history buffer + motion rejection | FxTXAA |
| ColorGrading | LUT-based 3D color grading | FxColorGrading |
| DeferredDecals | Box-projected decals onto G-buffer | DeferredDecals |
| ParticleUpdate | Compute: GPU particle simulation | ParticlesUpdate |
| ParticleRender | Billboard particle rendering | ParticlesRender |

**Render targets** (in addition to Tier 1):

| Target | Format | Resolution | Purpose |
|--------|--------|------------|---------|
| Motion Vectors | `rg16float` | Native | Screen-space velocity XY |
| SSAO Buffer | `r8unorm` | Half | Ambient occlusion term |
| SSR Buffer | `rgba16float` | Half | Screen-space reflection color |
| Bloom Chain 0-3 | `rg11b10ufloat` | 1/2, 1/4, 1/8, 1/16 | Bloom mip chain |
| TAA History | `rgba16float` | Native | Previous frame for temporal blend |
| Shadow Cascades 0-3 | `depth32float` | 2048x2048 each | 4 PSSM cascades |
| Indirect Draw Args | Storage buffer | N/A | GPU-driven draw arguments |

**Resolution strategy**: Native resolution with render scale option (0.5x to 2.0x). TAA provides temporal upscaling at lower render scales.

**GPU feature requirements**: `float32-filterable`, `rg11b10ufloat-renderable`. Compute shaders. Storage buffers. Indirect draw. 4+ color attachments.

**Expected performance**: 60 fps on NVIDIA RTX 2060 / Apple M1 Pro class at 1080p. Draw call budget: ~5000 (indirect).

---

### Tier 3: Maximum Quality (Ultra)

**Goal**: Match TM2020 "Ultra" quality. Every visual feature recreated.

**Passes that run**:

All of Tier 2 plus:

| Pass | Description | TM2020 Equivalent |
|------|-------------|-------------------|
| DualPassHBAO | Two-pass HBAO (small-scale + big-scale) | DeferredAmbientOcc (full HBAO+ dual) |
| VolumetricFog | Compute: ray-marched 3D fog with noise | DeferredFogVolumes + 3DFog_* |
| WaterReflection | Planar reflection render + refraction capture | WaterReflect + BufferRefract |
| ScreenDroplets | Screen-space water droplets on camera lens | CameraWaterDroplets_* |
| DepthOfField | Physical camera depth-of-field blur | FxDepthOfField |
| MotionBlur | Per-pixel velocity-based motion blur | FxMotionBlur |
| LensFlares | Occlusion-queried lens flare sprites + dirt | LensFlares |
| BurnMarks | Tire scorch marks projected onto G-buffer | DeferredBurn |
| GhostLayer | Translucent ghost car overlay | GhostLayer + GhostLayerBlend |
| CloudsGodRays | Cloud rendering with god ray light shafts | CloudsGodLight |

**Additional render targets**:

| Target | Format | Resolution | Purpose |
|--------|--------|------------|---------|
| Volumetric Fog 3D | `rgba16float` | 160x90x128 | Froxel-based fog volume |
| Water Reflection | `rgba8unorm-srgb` | Half | Planar reflection capture |
| Water Refraction | `rgba8unorm-srgb` | Native | Scene behind water |
| DoF CoC | `r16float` | Native | Circle of confusion radius |

**Resolution strategy**: Native resolution with optional supersampling (SSAA 2x via oversized render target + downsample, matching TM2020's `DownSSAA` pass).

**GPU feature requirements**: All Tier 2 features plus `texture-compression-bc` (optional, for DDS texture support), 3D texture support (`maxTextureDimension3D >= 128`), occlusion queries.

**Expected performance**: 60 fps on NVIDIA RTX 3070 / Apple M2 Pro class at 1440p. 30 fps target for 4K.

---

## 2. G-Buffer Design

### Format Justification

Every format choice is justified against the TM2020 reverse-engineering evidence.

#### RT0: Albedo + Material Flags

**Format**: `rgba8unorm-srgb`

**Justification**: TM2020's `BitmapDeferredMDiffuse` stores material diffuse color. The "M" prefix means "Material" -- this is albedo, not lit color (doc 11, Section 3). The engine uses a specular/glossiness PBR workflow where diffuse albedo is a simple sRGB color (doc 11, Section 10: "Separate `MDiffuse` and `MSpecular` G-buffer targets"). 8 bits per channel is sufficient for albedo since perceptual sRGB encoding matches human color perception. The alpha channel stores a material ID or ambient occlusion term (doc 11: "A: [UNKNOWN -- possibly AO or material ID]"). We use it for material category ID (0=terrain, 1=road, 2=car, 3=vegetation, etc.) to enable per-material deferred read behavior matching TM2020's separate `Block_DefReadP1_LM0/LM1/LM2` shader variants.

**Memory**: 4 bytes/pixel. At 1920x1080 = 7.9 MB.

#### RT1: Specular Properties

**Format**: `rgba8unorm`

**Justification**: TM2020's `BitmapDeferredMSpecular` stores specular F0 reflectance in RGB and roughness (or glossiness) in alpha (doc 11, Section 10: "F0 R, F0 G, F0 B, Roughness (or glossiness)"). The engine uses specular/glossiness PBR confirmed by `Engines/Pbr_Spec_to_Roughness_c.hlsl` converting specular to roughness, and separate `MDiffuse`/`MSpecular` targets. For dielectric materials, F0 is typically 0.02-0.05 (4% reflectance), which maps cleanly to 8-bit [5-13]. For metals, F0 is the metal color itself. 8 bits per channel provides 256 levels of roughness -- sufficient given that roughness perception is non-linear. NOT `rgba16float` because the extra precision is wasted on material properties that originate from 8-bit textures.

**Memory**: 4 bytes/pixel. At 1920x1080 = 7.9 MB.

#### RT2: Pixel Normal (Camera Space)

**Format**: `rg16float`

**Justification**: TM2020's `BitmapDeferredPixelNormalInC` stores per-pixel bump-mapped normals in camera space (doc 11, Section 3). The existence of `DeferredDeCompFaceNormal_p.hlsl` ("decompress face normal") confirms normals are stored compressed (doc 11, Section 3: "Octahedral encoding is most likely -- it is the standard approach for deferred renderers since 2014"). Octahedral encoding maps a unit-sphere normal to 2 channels, giving full hemisphere coverage with uniform error distribution. `rg16float` (2x16-bit float) provides 10 bits of mantissa per channel -- approximately 0.001 angular precision, far exceeding human perception of surface orientation.

Why not `rgba8snorm`? Octahedral decoding with 8-bit quantization produces visible banding on smooth surfaces under specular highlights. The specular lobe of GGX (doc 11 Section 10: "GGX/Cook-Torrance specular with Smith GGX height-correlated visibility term") is highly sensitive to normal direction at low roughness.

Why not `rgba16float`? The Z component is reconstructable from XY (`z = sqrt(1 - x*x - y*y)` after octahedral decode), so storing it wastes 4 bytes/pixel. The two unused channels would waste bandwidth on every G-buffer read.

**Memory**: 4 bytes/pixel. At 1920x1080 = 7.9 MB.

#### RT3: Light Mask

**Format**: `rgba8unorm`

**Justification**: TM2020's `BitmapDeferredLightMask` stores per-channel light flags consumed by `Deferred_SetLDirFromMask_p.hlsl` to derive light direction from the mask buffer (doc 15, Section 7: "LightMask, RGBA: flags, per-channel light flags"). This is a bitmask/flag buffer, not a color. 8 bits per channel provides 4 independent flag channels. Channel assignments:
- R: Lightmap tier index (0=LM0, 1=LM1, 2=LM2) -- maps to TM2020's `Block_DefReadP1_LM0/LM1/LM2` variants
- G: Self-illumination flag (maps to `_SI_` shader variants)
- B: Receives dynamic shadows flag (from `ShadowCasterAlphaCut`)
- A: Receives lightmap indirect lighting flag (from `LM iLight` config)

**Memory**: 4 bytes/pixel. At 1920x1080 = 7.9 MB.

#### Depth/Stencil

**Format**: `depth24plus-stencil8`

**Justification**: TM2020 uses `D24_UNORM_S8_UINT` confirmed from the D3D11 runtime log (doc 11, Section 2: "Depth/Stencil format: `DXGI_FORMAT_D24_UNORM_S8_UINT`"). `depth24plus-stencil8` is the WebGPU equivalent. 24-bit depth provides sufficient precision for the game's view range (up to 50,000m far clip from TMF, doc 19 Section 8). Stencil is required for deferred light volume rendering: light geometry (sphere for point lights, cone for spot lights) is stencil-marked to avoid shading pixels outside the light's influence, matching TM2020's `DeferredGeomLightBall_p.hlsl` and `DeferredGeomLightSpot_p.hlsl` (doc 11, Section 4 Phase 5).

**Memory**: 4 bytes/pixel. At 1920x1080 = 7.9 MB.

#### HDR Accumulation Buffer

**Format**: `rgba16float` (Tier 1) or `rg11b10ufloat` (Tier 2+ where supported)

**Justification**: TM2020 operates in HDR throughout the deferred lighting pipeline. The `DiffuseAmbient` target accumulates `MDiffuse * (ambient + lightmap + indirect)` (doc 11, Section 3), which can exceed [0,1] range from bright lights and emissive surfaces. Tone mapping (`TM_GlobalFilmCurve_p.hlsl`) runs late in the pipeline, requiring HDR throughout. `rgba16float` provides the full range. Where `rg11b10ufloat-renderable` is available, we use the more compact format (6 bytes vs 8 bytes per pixel) for intermediate buffers that do not need alpha, matching TM2020's bloom chain.

**Memory**: `rgba16float` = 8 bytes/pixel = 15.8 MB at 1080p. `rg11b10ufloat` = 4 bytes/pixel = 7.9 MB.

### G-Buffer Memory Budget (Tier 2, 1920x1080)

| Target | Format | Size |
|--------|--------|------|
| Albedo | `rgba8unorm-srgb` | 7.9 MB |
| Specular | `rgba8unorm` | 7.9 MB |
| Normal | `rg16float` | 7.9 MB |
| LightMask | `rgba8unorm` | 7.9 MB |
| Depth/Stencil | `depth24plus-stencil8` | 7.9 MB |
| HDR Accumulation | `rgba16float` | 15.8 MB |
| Motion Vectors | `rg16float` | 7.9 MB |
| SSAO | `r8unorm` (half res) | 0.5 MB |
| **Total G-Buffer** | | **63.7 MB** |

Plus shadow maps (4 x 2048x2048 x 4 bytes = 64 MB), bloom chain (~4 MB), TAA history (15.8 MB). Total GPU memory for render targets: approximately **148 MB** at 1080p.

---

## 3. Shader Architecture

### Strategy: 1,112 TM2020 Shaders to ~35 WebGPU Uber-Shaders

The TM2020 shader catalog (doc 32) contains 1,112 compiled DXBC stages. However, analysis reveals massive combinatorial explosion from a small number of core programs. The block shader family alone accounts for 180 entries derived from 6 core programs with 8 pipeline variants and multiple modifiers (doc 32, Section 5: "180 block shaders derive from approximately 6 core shader programs").

Our approach: **preprocessor-style pipeline overrides** in WGSL. Each uber-shader uses `override` constants to select code paths at pipeline compilation time, producing specialized GPU code without runtime branching.

### Core Uber-Shader List

| # | Shader Module | Replaces (TM2020) | Override Dimensions |
|---|---------------|-------------------|-------------------|
| 1 | `block_material.wgsl` | 180 Block_* shaders | PROJECTION_MODE(5), PIPELINE(4), SELF_ILLUM, COLOR_OUT, LM_TIER(3) |
| 2 | `car_body.wgsl` | 31 Car* shaders | PART(skin/details/gems/glass), PIPELINE(3) |
| 3 | `tree_vegetation.wgsl` | 30 Tree_* shaders | INSTANCED, IMPOSTOR, PIPELINE(3) |
| 4 | `grass.wgsl` | 10 Grass_* shaders | FENCE, PIPELINE(2) |
| 5 | `dynamic_object.wgsl` | 55 Dyna*/Body*/Char* | SKELETAL, TWEEN, FACING, PIPELINE(3) |
| 6 | `water_surface.wgsl` | 18 Ocean/Sea/Water* | QUALITY(simple/full) |
| 7 | `deferred_write_black.wgsl` | DeferredWrite_BlackNoSpec | (no variants) |
| 8 | `deferred_ambient.wgsl` | 4 Deferred_* read shaders | (no variants) |
| 9 | `deferred_light_point.wgsl` | DeferredGeomLightBall | (no variants) |
| 10 | `deferred_light_spot.wgsl` | DeferredGeomLightSpot | (no variants) |
| 11 | `deferred_light_fx.wgsl` | LightFxSphere + LightFxCylinder | SHAPE(sphere/cylinder) |
| 12 | `deferred_projector.wgsl` | DeferredGeomProjector | (no variants) |
| 13 | `deferred_shadow_pssm.wgsl` | DeferredShadowPssm | CASCADE_COUNT(2/4) |
| 14 | `deferred_decal.wgsl` | 8 DeferredDecal* shaders | MODE(box/geom/fulltri) |
| 15 | `deferred_burn.wgsl` | DeferredGeomBurnSphere | (no variants) |
| 16 | `face_normal.wgsl` | DeferredFaceNormalFromDepth | (no variants) |
| 17 | `linear_depth.wgsl` | DeferredZBufferToDist01 | (no variants) |
| 18 | `motion_vectors.wgsl` | DeferredCameraMotion | (no variants) |
| 19 | `fog_global.wgsl` | DeferredFogGlobal + DeferredFog | (no variants) |
| 20 | `fog_box.wgsl` | FogBoxOutside + FogBoxInside | CAMERA_INSIDE |
| 21 | `fog_volumetric.wgsl` | 3DFog_* (5 compute shaders) | PHASE(scatter/march/blend) |
| 22 | `ssao.wgsl` | HBAO+ pipeline (9 shaders) | PASS(linearize/compute/blur) |
| 23 | `ssr.wgsl` | SSReflect_* (5 shaders) | TEMPORAL, UPSAMPLE |
| 24 | `bloom.wgsl` | Bloom* (6 shaders) | PASS(threshold/blur/streak/final) |
| 25 | `tonemap.wgsl` | TM_* (8 shaders) | PASS(lumi/avg/curve) |
| 26 | `fxaa.wgsl` | FXAA_p | (no variants) |
| 27 | `temporal_aa.wgsl` | TemporalAA_p | (no variants) |
| 28 | `color_grading.wgsl` | ColorGrading + Colors + ColorBlind | MODE(lut/adjust/blind) |
| 29 | `sky.wgsl` | Sky_p/v | (no variants) |
| 30 | `clouds.wgsl` | Clouds* (9 shaders) | GOD_RAYS |
| 31 | `particles.wgsl` | MgrParticle* (14 shaders) | PHASE(spawn/update/render), OPAQUE |
| 32 | `gpu_cull.wgsl` | Instances_* (7 compute) | PHASE(cull/merge/args) |
| 33 | `depth_only.wgsl` | ZOnly_* (15 shaders) | ALPHA_TEST, INSTANCED |
| 34 | `fullscreen_tri.wgsl` | FullTriangle_* (5 shaders) | HAS_TEXCOORD |
| 35 | `ghost_car.wgsl` | CarGhost | (no variants) |
| 36 | `pbr_precompute.wgsl` | Pbr_* (6 compute) | PHASE(brdf/envmap/roughness) |
| 37 | `impostor.wgsl` | Tree_Impostor_* + ImpostorConvert | PIPELINE(2) |
| 38 | `warp_material.wgsl` | 31 Warp_* shaders | WARP_TYPE(4), PIPELINE(2) |

**Total: 38 uber-shader modules** producing approximately 120-150 pipeline specializations through override constants.

### Core WGSL Shader Code

#### G-Buffer Write (Deferred Material Shader)

This is the core shader that replaces TM2020's `Block_TDSN_DefWrite_p/v.hlsl` and all block deferred-write variants. It writes to 4 MRT outputs + depth.

```wgsl
// block_material.wgsl -- Core deferred G-buffer write shader
// Replaces: Block_TDSN_DefWrite, Block_PyPxz_DefWrite, Block_PxzDSN_DefWrite,
//           Block_PTDSN_DefWrite, Block_PyPxzTLayered_DefWrite, and all
//           block DefWrite variants (180 TM2020 shaders -> 1 uber-shader)

// Pipeline overrides (set at pipeline creation time)
override PROJECTION_MODE: u32 = 0u; // 0=TDSN, 1=PyPxz, 2=PxzDSN, 3=PTDSN, 4=Layered
override HAS_SELF_ILLUM: bool = false;
override HAS_VERTEX_COLOR: bool = false;
override HAS_LIGHTMAP: bool = true;
override MATERIAL_ID: u32 = 1u; // 0=terrain, 1=road, 2=structure, 3=vegetation

// Bind group 0: Per-frame constants
struct FrameUniforms {
    view_matrix: mat4x4<f32>,
    proj_matrix: mat4x4<f32>,
    view_proj: mat4x4<f32>,
    prev_view_proj: mat4x4<f32>,
    camera_pos_ws: vec3<f32>,
    time: f32,
    sun_direction: vec3<f32>,
    delta_time: f32,
    sun_color: vec3<f32>,
    taa_jitter_x: f32,
    ambient_color: vec3<f32>,
    taa_jitter_y: f32,
    wind_direction: vec2<f32>,
    wind_speed: f32,
    wind_time: f32,
}
@group(0) @binding(0) var<uniform> frame: FrameUniforms;

// Bind group 1: Per-pass constants (empty for G-buffer write)

// Bind group 2: Per-material textures + constants
@group(2) @binding(0) var albedo_texture: texture_2d<f32>;
@group(2) @binding(1) var specular_texture: texture_2d<f32>;
@group(2) @binding(2) var normal_texture: texture_2d<f32>;
@group(2) @binding(3) var self_illum_texture: texture_2d<f32>;
@group(2) @binding(4) var material_sampler: sampler;

struct MaterialUniforms {
    diffuse_tint: vec4<f32>,
    specular_scale: f32,
    roughness_scale: f32,
    emissive_intensity: f32,
    uv_scale: vec2<f32>,
    uv_offset: vec2<f32>,
}
@group(2) @binding(5) var<uniform> material: MaterialUniforms;

// Bind group 3: Per-draw instance data
struct InstanceData {
    world_matrix: mat4x4<f32>,
    normal_matrix: mat3x3<f32>,
    lightmap_uv_offset: vec2<f32>,
    lightmap_uv_scale: vec2<f32>,
}
@group(3) @binding(0) var<uniform> instance: InstanceData;

// Vertex input -- matches TM2020 stride-56 block format (doc 11, Section 2)
struct VertexInput {
    @location(0) position: vec3<f32>,     // R32G32B32_SFLOAT, offset 0
    @location(1) normal: vec4<i16>,       // R16G16B16A16_SNORM, offset 12 (packed)
    @location(2) color: vec4<f32>,        // B8G8R8A8_UNORM, offset 20
    @location(3) uv0: vec2<f32>,          // R32G32_SFLOAT, offset 24
    @location(4) uv1: vec2<f32>,          // R32G32_SFLOAT, offset 32 (lightmap UV)
    @location(5) tangent: vec4<i16>,      // R16G16B16A16_SNORM, offset 40
    @location(6) bitangent: vec4<i16>,    // R16G16B16A16_SNORM, offset 48
}

struct VertexOutput {
    @builtin(position) clip_pos: vec4<f32>,
    @location(0) uv0: vec2<f32>,
    @location(1) uv1: vec2<f32>,
    @location(2) normal_cs: vec3<f32>,
    @location(3) tangent_cs: vec3<f32>,
    @location(4) bitangent_cs: vec3<f32>,
    @location(5) vertex_color: vec4<f32>,
    @location(6) world_pos: vec3<f32>,
}

// Unpack SNORM i16 to float [-1, 1]
fn unpack_snorm4(v: vec4<i16>) -> vec4<f32> {
    return vec4<f32>(v) / 32767.0;
}

@vertex
fn vs_main(in: VertexInput) -> VertexOutput {
    var out: VertexOutput;

    let world_pos = (instance.world_matrix * vec4<f32>(in.position, 1.0)).xyz;
    out.world_pos = world_pos;

    // Apply TAA jitter to projection
    var jittered_proj = frame.proj_matrix;
    jittered_proj[2][0] += frame.taa_jitter_x;
    jittered_proj[2][1] += frame.taa_jitter_y;

    out.clip_pos = jittered_proj * frame.view_matrix * vec4<f32>(world_pos, 1.0);

    // Transform TBN to camera space for deferred normal output
    let n = unpack_snorm4(in.normal).xyz;
    let t = unpack_snorm4(in.tangent).xyz;
    let b = unpack_snorm4(in.bitangent).xyz;

    let view3x3 = mat3x3<f32>(
        frame.view_matrix[0].xyz,
        frame.view_matrix[1].xyz,
        frame.view_matrix[2].xyz
    );
    let normal_ws = instance.normal_matrix * n;
    let tangent_ws = instance.normal_matrix * t;
    let bitangent_ws = instance.normal_matrix * b;

    out.normal_cs = view3x3 * normal_ws;
    out.tangent_cs = view3x3 * tangent_ws;
    out.bitangent_cs = view3x3 * bitangent_ws;

    // UV coordinates
    if (PROJECTION_MODE == 0u) {
        // TDSN: standard UV mapping
        out.uv0 = in.uv0 * material.uv_scale + material.uv_offset;
    } else if (PROJECTION_MODE == 1u) {
        // PyPxz: triplanar -- compute UVs from world position
        // Y-projection uses world XZ, XZ-projection uses world XY and ZY
        // Actual blending happens in fragment shader
        out.uv0 = world_pos.xz * material.uv_scale;
    } else {
        out.uv0 = in.uv0 * material.uv_scale + material.uv_offset;
    }

    // Lightmap UVs
    out.uv1 = in.uv1 * instance.lightmap_uv_scale + instance.lightmap_uv_offset;

    out.vertex_color = in.color;

    return out;
}

// G-Buffer output structure -- 4 MRT
struct GBufferOutput {
    @location(0) albedo: vec4<f32>,      // RT0: rgba8unorm-srgb (albedo RGB + material ID)
    @location(1) specular: vec4<f32>,    // RT1: rgba8unorm (F0 RGB + roughness)
    @location(2) normal: vec2<f32>,      // RT2: rg16float (octahedral normal XY)
    @location(3) light_mask: vec4<f32>,  // RT3: rgba8unorm (light flags)
}

// Octahedral normal encoding (Cigolle et al. 2014)
// Maps unit sphere normal to [-1,1]^2
fn encode_octahedral(n: vec3<f32>) -> vec2<f32> {
    var n_norm = n / (abs(n.x) + abs(n.y) + abs(n.z));
    if (n_norm.z < 0.0) {
        let signs = sign(n_norm.xy);
        let s = select(vec2<f32>(-1.0), vec2<f32>(1.0), n_norm.xy >= vec2<f32>(0.0));
        n_norm = vec2<f32>((1.0 - abs(n_norm.yx)) * s);
    }
    return n_norm.xy;
}

// Sample normal map and transform from tangent space to camera space
fn get_pixel_normal_cs(
    uv: vec2<f32>,
    normal_cs: vec3<f32>,
    tangent_cs: vec3<f32>,
    bitangent_cs: vec3<f32>
) -> vec3<f32> {
    let ts_normal = textureSample(normal_texture, material_sampler, uv).xyz * 2.0 - 1.0;
    let tbn = mat3x3<f32>(
        normalize(tangent_cs),
        normalize(bitangent_cs),
        normalize(normal_cs)
    );
    return normalize(tbn * ts_normal);
}

// Triplanar sampling for PyPxz projection mode
fn sample_triplanar(
    tex: texture_2d<f32>,
    samp: sampler,
    world_pos: vec3<f32>,
    normal_ws: vec3<f32>
) -> vec4<f32> {
    let blend = abs(normal_ws);
    let blend_norm = blend / (blend.x + blend.y + blend.z);

    let sample_y = textureSample(tex, samp, world_pos.xz * material.uv_scale);
    let sample_x = textureSample(tex, samp, world_pos.zy * material.uv_scale);
    let sample_z = textureSample(tex, samp, world_pos.xy * material.uv_scale);

    return sample_y * blend_norm.y + sample_x * blend_norm.x + sample_z * blend_norm.z;
}

@fragment
fn fs_main(in: VertexOutput) -> GBufferOutput {
    var out: GBufferOutput;

    // --- Albedo ---
    var albedo: vec4<f32>;
    if (PROJECTION_MODE == 1u || PROJECTION_MODE == 2u) {
        // Triplanar projection
        let inv_view3x3 = mat3x3<f32>(
            frame.view_matrix[0].xyz,
            frame.view_matrix[1].xyz,
            frame.view_matrix[2].xyz
        );
        let normal_ws = transpose(inv_view3x3) * normalize(in.normal_cs);
        albedo = sample_triplanar(albedo_texture, material_sampler, in.world_pos, normal_ws);
    } else {
        albedo = textureSample(albedo_texture, material_sampler, in.uv0);
    }

    // Apply vertex color tint if present (doc 19, Section 10: "DColor0")
    if (HAS_VERTEX_COLOR) {
        albedo = vec4<f32>(albedo.rgb * in.vertex_color.rgb * material.diffuse_tint.rgb, albedo.a);
    } else {
        albedo = vec4<f32>(albedo.rgb * material.diffuse_tint.rgb, albedo.a);
    }

    out.albedo = vec4<f32>(albedo.rgb, f32(MATERIAL_ID) / 255.0);

    // --- Specular ---
    let spec_sample = textureSample(specular_texture, material_sampler, in.uv0);
    out.specular = vec4<f32>(
        spec_sample.rgb * material.specular_scale,
        spec_sample.a * material.roughness_scale
    );

    // --- Normal (camera space, octahedral encoded) ---
    let pixel_normal = get_pixel_normal_cs(in.uv0, in.normal_cs, in.tangent_cs, in.bitangent_cs);
    out.normal = encode_octahedral(pixel_normal);

    // --- Light Mask ---
    var lm_tier: f32 = 0.0;
    if (HAS_LIGHTMAP) { lm_tier = 1.0 / 255.0; }
    var self_illum_flag: f32 = 0.0;
    if (HAS_SELF_ILLUM) {
        let si = textureSample(self_illum_texture, material_sampler, in.uv0).r;
        self_illum_flag = si * material.emissive_intensity;
    }
    out.light_mask = vec4<f32>(lm_tier, self_illum_flag, 1.0, 1.0);

    return out;
}
```

#### Deferred Lighting Shader

This replaces TM2020's `DeferredRead` phase (ambient/Fresnel/lightmap) and `DeferredLighting` phase (light accumulation). It reads the full G-buffer and outputs lit HDR color.

```wgsl
// deferred_lighting.wgsl -- Core deferred read + lighting shader
// Replaces: Deferred_SetILightDir_p, Deferred_AddAmbient_Fresnel_p,
//           Deferred_AddLightLm_p, Deferred_SetLDirFromMask_p,
//           Block_DefReadP1_* (23 variants)

// Bind group 0: Per-frame
@group(0) @binding(0) var<uniform> frame: FrameUniforms;

// Bind group 1: G-buffer textures
@group(1) @binding(0) var gbuffer_albedo: texture_2d<f32>;
@group(1) @binding(1) var gbuffer_specular: texture_2d<f32>;
@group(1) @binding(2) var gbuffer_normal: texture_2d<f32>;
@group(1) @binding(3) var gbuffer_light_mask: texture_2d<f32>;
@group(1) @binding(4) var gbuffer_depth: texture_depth_2d;
@group(1) @binding(5) var shadow_map: texture_depth_2d_array;
@group(1) @binding(6) var ssao_texture: texture_2d<f32>;
@group(1) @binding(7) var brdf_lut: texture_2d<f32>;
@group(1) @binding(8) var env_cubemap: texture_cube<f32>;
@group(1) @binding(9) var lightmap_texture: texture_2d<f32>;
@group(1) @binding(10) var gbuffer_sampler: sampler;
@group(1) @binding(11) var shadow_sampler: sampler_comparison;
@group(1) @binding(12) var env_sampler: sampler;

// Bind group 2: Lighting constants
struct LightingUniforms {
    inv_view_proj: mat4x4<f32>,
    inv_view: mat4x4<f32>,
    shadow_vp: array<mat4x4<f32>, 4>,   // 4 cascade view-proj matrices
    cascade_splits: vec4<f32>,            // Z distances for each cascade
    shadow_map_size: f32,
    ambient_intensity: f32,
    sun_intensity: f32,
    ssao_intensity: f32,
    fog_color: vec3<f32>,
    fog_density: f32,
    fog_height_falloff: f32,
    fog_start: f32,
    _padding: vec2<f32>,
}
@group(2) @binding(0) var<uniform> lighting: LightingUniforms;

// Octahedral decode -- inverse of encode in gbuffer_fill
fn decode_octahedral(enc: vec2<f32>) -> vec3<f32> {
    var n = vec3<f32>(enc.x, enc.y, 1.0 - abs(enc.x) - abs(enc.y));
    if (n.z < 0.0) {
        let s = select(vec2<f32>(-1.0), vec2<f32>(1.0), n.xy >= vec2<f32>(0.0));
        n = vec3<f32>((1.0 - abs(n.yx)) * s, n.z);
    }
    return normalize(n);
}

// Reconstruct world position from depth + screen UV
fn reconstruct_world_pos(uv: vec2<f32>, depth: f32) -> vec3<f32> {
    let ndc = vec4<f32>(uv * 2.0 - 1.0, depth, 1.0);
    let world_h = lighting.inv_view_proj * ndc;
    return world_h.xyz / world_h.w;
}

// GGX specular BRDF (Cook-Torrance with Smith GGX visibility)
// Matches TM2020's Pbr_IntegrateBRDF_GGX_c.hlsl (doc 11, Section 10)
fn distribution_ggx(n_dot_h: f32, roughness: f32) -> f32 {
    let a = roughness * roughness;
    let a2 = a * a;
    let denom = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0;
    return a2 / (3.14159265 * denom * denom);
}

fn geometry_smith_ggx(n_dot_v: f32, n_dot_l: f32, roughness: f32) -> f32 {
    let r = roughness + 1.0;
    let k = (r * r) / 8.0;
    let g1_v = n_dot_v / (n_dot_v * (1.0 - k) + k);
    let g1_l = n_dot_l / (n_dot_l * (1.0 - k) + k);
    return g1_v * g1_l;
}

fn fresnel_schlick(cos_theta: f32, f0: vec3<f32>) -> vec3<f32> {
    return f0 + (1.0 - f0) * pow(1.0 - cos_theta, 5.0);
}

fn fresnel_schlick_roughness(cos_theta: f32, f0: vec3<f32>, roughness: f32) -> vec3<f32> {
    return f0 + (max(vec3<f32>(1.0 - roughness), f0) - f0) * pow(1.0 - cos_theta, 5.0);
}

// PCF shadow sampling for PSSM cascades
fn sample_shadow_pcf(world_pos: vec3<f32>, view_z: f32) -> f32 {
    // Select cascade based on view-space Z (doc 11, Section 5: 4 cascades)
    var cascade_idx: u32 = 0u;
    if (view_z > lighting.cascade_splits.x) { cascade_idx = 1u; }
    if (view_z > lighting.cascade_splits.y) { cascade_idx = 2u; }
    if (view_z > lighting.cascade_splits.z) { cascade_idx = 3u; }

    let shadow_coord = lighting.shadow_vp[cascade_idx] * vec4<f32>(world_pos, 1.0);
    let proj = shadow_coord.xyz / shadow_coord.w;
    let uv = proj.xy * 0.5 + 0.5;
    let compare_depth = proj.z;

    // 4-tap PCF (matching TM2020's PCF baseline from doc 11, Section 5)
    let texel_size = 1.0 / lighting.shadow_map_size;
    var shadow: f32 = 0.0;
    shadow += textureSampleCompare(shadow_map, shadow_sampler, uv + vec2<f32>(-texel_size, -texel_size), cascade_idx, compare_depth);
    shadow += textureSampleCompare(shadow_map, shadow_sampler, uv + vec2<f32>( texel_size, -texel_size), cascade_idx, compare_depth);
    shadow += textureSampleCompare(shadow_map, shadow_sampler, uv + vec2<f32>(-texel_size,  texel_size), cascade_idx, compare_depth);
    shadow += textureSampleCompare(shadow_map, shadow_sampler, uv + vec2<f32>( texel_size,  texel_size), cascade_idx, compare_depth);
    shadow *= 0.25;

    return shadow;
}

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

// Fullscreen triangle vertex shader (replaces TM2020's FullTriangle_TexCoord_v.hlsl)
@vertex
fn vs_fullscreen(@builtin(vertex_index) vertex_id: u32) -> VertexOutput {
    var out: VertexOutput;
    // Generate fullscreen triangle from vertex index (0,1,2)
    let uv = vec2<f32>(f32((vertex_id << 1u) & 2u), f32(vertex_id & 2u));
    out.position = vec4<f32>(uv * 2.0 - 1.0, 0.0, 1.0);
    out.uv = vec2<f32>(uv.x, 1.0 - uv.y); // Flip Y for texture coordinates
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let tex_coord = in.uv;
    let tex_size = textureDimensions(gbuffer_albedo);
    let pixel = vec2<u32>(tex_coord * vec2<f32>(tex_size));

    // Read G-buffer
    let albedo_sample = textureLoad(gbuffer_albedo, pixel, 0);
    let specular_sample = textureLoad(gbuffer_specular, pixel, 0);
    let normal_enc = textureLoad(gbuffer_normal, pixel, 0).rg;
    let light_mask = textureLoad(gbuffer_light_mask, pixel, 0);
    let depth = textureLoad(gbuffer_depth, pixel, 0);

    // Early out for sky pixels (depth == 1.0)
    if (depth >= 1.0) {
        return vec4<f32>(0.0, 0.0, 0.0, 0.0);
    }

    // Decode G-buffer
    let albedo = albedo_sample.rgb;
    let material_id = u32(albedo_sample.a * 255.0);
    let f0 = specular_sample.rgb;
    let roughness = max(specular_sample.a, 0.04); // Clamp minimum roughness
    let normal_cs = decode_octahedral(normal_enc);
    let self_illum = light_mask.g;

    // Reconstruct world position
    let world_pos = reconstruct_world_pos(tex_coord, depth);
    let view_pos = (frame.view_matrix * vec4<f32>(world_pos, 1.0)).xyz;

    // Vectors
    let V = normalize(frame.camera_pos_ws - world_pos);
    // Normal is in camera space; transform to world space for lighting
    let inv_view3x3 = mat3x3<f32>(
        lighting.inv_view[0].xyz,
        lighting.inv_view[1].xyz,
        lighting.inv_view[2].xyz
    );
    let N = normalize(inv_view3x3 * normal_cs);
    let L = normalize(-frame.sun_direction);
    let H = normalize(V + L);

    let n_dot_v = max(dot(N, V), 0.001);
    let n_dot_l = max(dot(N, L), 0.0);
    let n_dot_h = max(dot(N, H), 0.0);
    let v_dot_h = max(dot(V, H), 0.0);

    // === Ambient + Fresnel ===
    // Matches Deferred_AddAmbient_Fresnel_p.hlsl (doc 15, Section 7)
    let F_ambient = fresnel_schlick_roughness(n_dot_v, f0, roughness);
    let kS_ambient = F_ambient;
    let kD_ambient = (1.0 - kS_ambient) * 1.0; // Assumes non-metallic; metals have kD=0

    // Diffuse IBL: sample environment cubemap at normal direction, highest mip (blurry)
    let irradiance = textureSampleLevel(env_cubemap, env_sampler, N, 6.0).rgb;
    let diffuse_ambient = kD_ambient * albedo * irradiance;

    // Specular IBL via split-sum approximation
    // (Matches Pbr_IntegrateBRDF_GGX_c.hlsl and Pbr_PreFilterEnvMap_GGX_c.hlsl)
    let R = reflect(-V, N);
    let max_lod = 8.0;
    let prefiltered = textureSampleLevel(env_cubemap, env_sampler, R, roughness * max_lod).rgb;
    let brdf = textureSample(brdf_lut, gbuffer_sampler, vec2<f32>(n_dot_v, roughness)).rg;
    let specular_ambient = prefiltered * (F_ambient * brdf.x + brdf.y);

    var ambient = (diffuse_ambient + specular_ambient) * lighting.ambient_intensity;

    // === SSAO ===
    let ao = textureSample(ssao_texture, gbuffer_sampler, tex_coord).r;
    ambient *= ao;

    // === Directional Light (Sun) ===
    // GGX Cook-Torrance BRDF (doc 11, Section 10)
    let D = distribution_ggx(n_dot_h, roughness);
    let G = geometry_smith_ggx(n_dot_v, n_dot_l, roughness);
    let F = fresnel_schlick(v_dot_h, f0);

    let numerator = D * G * F;
    let denominator = 4.0 * n_dot_v * n_dot_l + 0.001;
    let specular_brdf = numerator / denominator;

    let kS = F;
    let kD = (1.0 - kS) * 1.0;
    let direct_diffuse = kD * albedo / 3.14159265;
    let direct = (direct_diffuse + specular_brdf) * frame.sun_color * n_dot_l * lighting.sun_intensity;

    // === Shadows ===
    let shadow = sample_shadow_pcf(world_pos, -view_pos.z);
    let lit_direct = direct * shadow;

    // === Self-Illumination ===
    let emissive = albedo * self_illum;

    // === Combine ===
    let final_color = ambient + lit_direct + emissive;

    return vec4<f32>(final_color, 1.0);
}
```

#### Point Light Volume Shader

Renders stencil-marked sphere proxies for point lights, matching TM2020's `DeferredGeomLightBall_p.hlsl`.

```wgsl
// deferred_light_point.wgsl
// Replaces: DeferredGeomLightBall_p.hlsl (doc 32, Section 4 pass 14)

struct PointLight {
    position_ws: vec3<f32>,
    radius: f32,
    color: vec3<f32>,
    intensity: f32,
}

@group(0) @binding(0) var<uniform> frame: FrameUniforms;

@group(1) @binding(0) var gbuffer_albedo: texture_2d<f32>;
@group(1) @binding(1) var gbuffer_specular: texture_2d<f32>;
@group(1) @binding(2) var gbuffer_normal: texture_2d<f32>;
@group(1) @binding(3) var gbuffer_depth: texture_depth_2d;
@group(1) @binding(4) var gbuffer_sampler: sampler;

@group(2) @binding(0) var<uniform> light: PointLight;
@group(2) @binding(1) var<uniform> inv_view_proj: mat4x4<f32>;

@fragment
fn fs_main(@builtin(position) frag_coord: vec4<f32>) -> @location(0) vec4<f32> {
    let tex_size = vec2<f32>(textureDimensions(gbuffer_albedo));
    let uv = frag_coord.xy / tex_size;
    let pixel = vec2<u32>(frag_coord.xy);

    // Read G-buffer
    let albedo = textureLoad(gbuffer_albedo, pixel, 0).rgb;
    let spec_sample = textureLoad(gbuffer_specular, pixel, 0);
    let f0 = spec_sample.rgb;
    let roughness = max(spec_sample.a, 0.04);
    let normal_enc = textureLoad(gbuffer_normal, pixel, 0).rg;
    let depth = textureLoad(gbuffer_depth, pixel, 0);

    let N = decode_octahedral(normal_enc);
    let world_pos = reconstruct_world_pos(uv, depth);

    // Light vector
    let light_vec = light.position_ws - world_pos;
    let dist = length(light_vec);
    if (dist > light.radius) { discard; }

    let L = light_vec / dist;
    let V = normalize(frame.camera_pos_ws - world_pos);
    let H = normalize(V + L);

    let n_dot_l = max(dot(N, L), 0.0);
    let n_dot_v = max(dot(N, V), 0.001);
    let n_dot_h = max(dot(N, H), 0.0);
    let v_dot_h = max(dot(V, H), 0.0);

    // Attenuation (inverse-square with radius falloff)
    let attenuation = pow(saturate(1.0 - pow(dist / light.radius, 4.0)), 2.0)
                    / (dist * dist + 1.0);

    // GGX BRDF (same as directional light)
    let D = distribution_ggx(n_dot_h, roughness);
    let G = geometry_smith_ggx(n_dot_v, n_dot_l, roughness);
    let F = fresnel_schlick(v_dot_h, f0);
    let spec = (D * G * F) / (4.0 * n_dot_v * n_dot_l + 0.001);
    let kD = (1.0 - F) * 1.0;
    let diffuse = kD * albedo / 3.14159265;

    let radiance = light.color * light.intensity * attenuation;
    let result = (diffuse + spec) * radiance * n_dot_l;

    return vec4<f32>(result, 0.0); // Additive blend
}
```

---

## 4. Mesh Pipeline

### Vertex Formats

From the D3D11 runtime log captured from TM2020 (doc 11, Section 2):

#### Block Geometry (Stride 56, 7 attributes)

This is the primary vertex format for all track blocks -- roads, platforms, terrain.

```
WebGPU VertexBufferLayout:
{
  arrayStride: 56,
  attributes: [
    { shaderLocation: 0, offset:  0, format: 'float32x3'  },  // position (12 bytes)
    { shaderLocation: 1, offset: 12, format: 'snorm16x4'  },  // normal (8 bytes)
    { shaderLocation: 2, offset: 20, format: 'unorm8x4'   },  // vertex color BGRA (4 bytes)
    { shaderLocation: 3, offset: 24, format: 'float32x2'  },  // UV0 material (8 bytes)
    { shaderLocation: 4, offset: 32, format: 'float32x2'  },  // UV1 lightmap (8 bytes)
    { shaderLocation: 5, offset: 40, format: 'snorm16x4'  },  // tangent (8 bytes)
    { shaderLocation: 6, offset: 48, format: 'snorm16x4'  },  // bitangent (8 bytes)
  ]
}
```

**Note on BGRA vertex color**: TM2020 uses `B8G8R8A8_UNORM` for vertex color (swizzled blue-first). WebGPU's `unorm8x4` reads as RGBA, so we must swizzle `.bgra` in the shader, or pre-swizzle during mesh loading.

#### Lightmapped Geometry (Stride 52, 6 attributes)

Same as block geometry without vertex color. Used for simpler lightmapped objects.

```
arrayStride: 52
// Same as above, minus vertex color. UV0 at offset 20, UV1 at 28, etc.
```

#### Simple Geometry (Stride 28, 3 attributes)

Used for shadow-only, depth-only, and simple objects.

```
arrayStride: 28
attributes: [
  { shaderLocation: 0, offset:  0, format: 'float32x3'  },  // position
  { shaderLocation: 1, offset: 12, format: 'snorm16x4'  },  // normal
  { shaderLocation: 2, offset: 20, format: 'float32x2'  },  // UV0
]
```

### Index Buffer Format

`uint16` for meshes under 65536 vertices, `uint32` for larger meshes. TM2020 blocks typically fit in `uint16` since individual block meshes are small (a single road piece has ~200-500 triangles). The index format is stored per-mesh in the GBX file.

### Instancing Strategy for Repeated Blocks

TM2020 maps are built on a 32-meter grid (doc 28, Section 1.2). A typical map contains hundreds of instances of the same block type (e.g., `StadiumRoadMainStraight` might appear 50+ times). The engine uses GPU instancing confirmed by shader names like `ZOnly_InstancingStatic_v`, `GeomILightIn0_Inst_v`, and the `Instances_Cull_SetLOD_c.hlsl` compute culling shader (doc 32, Section 7).

**Our instancing approach**:

1. **Instance buffer**: One `GPUBuffer` per unique block type containing per-instance data:
   - World transform matrix (48 bytes: 3x4 float matrix, omitting homogeneous row)
   - Lightmap UV offset + scale (16 bytes)
   - LOD level (4 bytes)
   - Total: 68 bytes per instance

2. **Indirect draw**: For Tier 2+, the GPU cull compute shader writes `DrawIndexedIndirect` arguments per (mesh, LOD) pair. Instances that fail the frustum test have their count set to 0.

3. **Mesh grouping**: All instances of the same block type + material share one `drawIndexedIndirect` call. With ~200 unique block types and ~3 material variants each, this produces ~600 indirect draw calls for all block geometry -- well within WebGPU budgets.

4. **Block-to-instance mapping**: When loading a map, for each placed block (doc 28, Section 2.4):
   - Look up the block name in the mesh registry
   - Compute the world transform from grid coordinates: `world_x = block_x * 32.0, world_y = block_y * 8.0, world_z = block_z * 32.0` plus rotation from the 4-cardinal direction value
   - Append to the instance buffer for that block type

### Meshes Inside .pak Files

This is addressed in detail in Section 8. The critical point for the mesh pipeline is that block geometry definitions -- the actual vertex/index data -- are stored inside encrypted `.pak` files (NadeoPak format), not inside `.Map.Gbx` files. The map file contains only block placement data (name + position + rotation). The mesh data must come from somewhere else.

---

## 5. Shadow System

### Architecture

Parallel Split Shadow Maps (PSSM), matching TM2020's verified 4-cascade system (doc 11, Section 5: strings `"MapShadowSplit0"` through `"MapShadowSplit3"`).

### Cascade Configuration

| Property | Tier 1 | Tier 2/3 | Evidence |
|----------|--------|----------|----------|
| Cascade count | 2 | 4 | Doc 11: "4 cascades (default), 1 (simplified)" |
| Resolution per cascade | 2048x2048 | 2048x2048 | Standard for current-gen; TM2020's `ShadowMapTexelSize` is configurable |
| Shadow format | `depth32float` | `depth32float` | Doc 11: "Likely `D16_UNORM` or `D24_UNORM`" -- we use `depth32float` for WebGPU comparison sampling |
| Filtering | 4-tap PCF | 9-tap PCF (Tier 2), 16-tap (Tier 3) | Doc 11: "PCF baseline + `HqSoftShadows` toggle" |
| Bias | Slope-scaled constant | Slope-scaled constant | Doc 11: `"ShadowBiasConstSlope"` string |
| Alpha cutout | 0.5 threshold | 0.5 threshold | Doc 11: `"ShadowCasterAlphaRef"` / `"ShadowCasterAlphaCut"` |

### Split Distances

TM2020's exact split scheme is unknown (doc 11: "SPECULATIVE for exact formats and split distances"). We use practical split distances (Engel's formula: blend of logarithmic and linear) tuned for a 32-meter block world:

| Cascade | Near | Far | World Coverage | Purpose |
|---------|------|-----|----------------|---------|
| 0 | 0.5m | 15m | Car + immediate road | Detailed car shadow, road markings |
| 1 | 15m | 60m | ~2 block radius | Near track geometry |
| 2 | 60m | 200m | ~6 block radius | Medium distance |
| 3 | 200m | 800m | ~25 block radius | Distant terrain silhouettes |

The near cascade covers the player's car and the road directly under it. The 32m block grid means cascade 1 covers about 2 blocks, cascade 2 covers 6, and cascade 3 covers 25 -- enough for the visible play area in most maps.

### Shadow Atlas vs Individual Maps

**Decision: Texture array** (one layer per cascade).

TM2020 uses `DeferredShadowPssm_p.hlsl` which samples 4 cascade maps. In WebGPU, a `texture_depth_2d_array` with 4 layers is the natural mapping. This avoids the UV packing math of a shadow atlas and allows `textureSampleCompareLevel` with the cascade index as the array layer. Each cascade render pass writes to its own layer via `depthStencilAttachment.view` created with `baseArrayLayer: cascadeIndex`.

### Shadow Cache

TM2020 caches static shadow maps (doc 11: `"ShadowCache_Enable"`, `ShadowCacheUpdate` render pass). For our implementation:
- Static blocks (terrain, platforms) that don't move are rendered to shadow maps once and cached
- Only dynamic objects (cars, kinematic items) and the near cascade are re-rendered each frame
- The cache is invalidated when the sun angle changes (time-of-day shift)

---

## 6. Post-Processing Chain

The exact execution order is reconstructed from TM2020's verified pass ordering (doc 11, Section 4 Phase 9-12; doc 32, Section 6):

### Pass Order

| # | Pass | Input | Output | Shader | Tier |
|---|------|-------|--------|--------|------|
| 1 | SSAO | Depth, face normals | `r8unorm` half-res AO | `ssao.wgsl` | 2+ |
| 2 | Deferred Lighting | G-buffer (4 RT), depth, shadow maps, SSAO, BRDF LUT, env cubemap | `rgba16float` HDR lit scene | `deferred_lighting.wgsl` | 1+ |
| 3 | Screen-Space Reflections | HDR scene, depth, normals | `rgba16float` half-res SSR | `ssr.wgsl` | 2+ |
| 4 | SSR Composite | HDR scene + SSR | HDR scene (modified) | (blend pass) | 2+ |
| 5 | Forward Transparent | HDR scene (read), depth | HDR scene (write) | `block_material.wgsl` (forward mode) | 1+ |
| 6 | Volumetric Fog | 3D fog volume, depth | `rgba16float` fog accumulation | `fog_volumetric.wgsl` | 3 |
| 7 | Global Fog | HDR scene, depth | HDR scene (fogged) | `fog_global.wgsl` | 1+ |
| 8 | Lens Flares | HDR scene, occlusion query | HDR scene + flares | `lens_flare.wgsl` | 3 |
| 9 | Depth of Field | HDR scene, depth | HDR scene (blurred) | `dof.wgsl` | 3 |
| 10 | Motion Blur | HDR scene, motion vectors | HDR scene (blurred) | `motion_blur.wgsl` | 3 |
| 11 | Luminance Extraction | HDR scene | 1x1 average luminance | `tonemap.wgsl` (lumi pass) | 1+ |
| 12 | Tone Mapping | HDR scene, average luminance | LDR scene | `tonemap.wgsl` (curve pass) | 1+ |
| 13 | Bloom Threshold + Downsample | LDR/HDR scene | Bloom mip chain (4 levels) | `bloom.wgsl` (threshold+down) | 2+ |
| 14 | Bloom Blur | Bloom mips | Blurred bloom mips | `bloom.wgsl` (blur) | 2+ |
| 15 | Bloom Composite | LDR scene + bloom | LDR scene + bloom | `bloom.wgsl` (final) | 2+ |
| 16 | FXAA or TAA | Scene (+ motion vectors for TAA) | Anti-aliased scene | `fxaa.wgsl` or `temporal_aa.wgsl` | 1+ |
| 17 | Color Grading | Scene | Final graded scene | `color_grading.wgsl` | 2+ |
| 18 | Final Output | Graded scene | Swap chain `bgra8unorm` | Copy/blit | 0+ |

### Key Ordering Notes

- **SSAO before lighting** (pass 1 before 2): AO modulates ambient term during deferred read, matching TM2020's `DeferredAmbientOcc` occurring before `DeferredRead` (doc 11, Phase 3-5)
- **Fog after lighting, before lens effects**: Fog contributes to the scene before camera effects, matching TM2020's `DeferredFogVolumes -> DeferredFog -> LensFlares` ordering (doc 11, Phase 9)
- **Tone mapping before bloom**: TM2020's pass order shows `FxToneMap -> FxBloom` (doc 11, Phase 12). Bloom is extracted from the tone-mapped scene, preventing extremely bright highlights from dominating the bloom. This matches doc 11's note: "Scene is tonemapped first, then bloom is extracted from bright areas"
- **AA after tone mapping**: FXAA/TAA operate on the tone-mapped result (doc 11: "FXAA/TXAA operates on the tonemapped LDR/HDR result")
- **Color grading last**: LUT-based grading is the final creative adjustment (doc 11: "LUT-based color grading is the final image adjustment")

### Tone Mapping Implementation

TM2020 uses a filmic curve with piecewise power segments (`NFilmicTone_PowerSegments::SCurveParamsUser`), similar to Hable/Uncharted 2 (doc 11, Section 9). We implement the Khronos PBR Neutral tone mapper as a close match that is well-documented:

```
// Simplified filmic curve matching TM2020's shoulder+linear+toe segments
fn filmic_tonemap(x: vec3<f32>) -> vec3<f32> {
    // ACES-inspired filmic curve with adjustable parameters
    let a = 2.51;
    let b = 0.03;
    let c = 2.43;
    let d = 0.59;
    let e = 0.14;
    return saturate((x * (a * x + b)) / (x * (c * x + d) + e));
}
```

---

## 7. Asset Loading Pipeline

### DDS Texture Loading

TM2020 textures are stored in DDS format (DirectDraw Surface) inside .pak files. The DDS files use BCn block compression:

| DDS Format | WebGPU Format | Usage | Support |
|-----------|---------------|-------|---------|
| DXT1 / BC1 | `bc1-rgba-unorm-srgb` | Albedo (no alpha), terrain | Requires `texture-compression-bc` |
| DXT5 / BC3 | `bc3-rgba-unorm-srgb` | Albedo with alpha (foliage, fences) | Requires `texture-compression-bc` |
| BC5 | `bc5-rg-unorm` | Normal maps (RG channels) | Requires `texture-compression-bc` |
| BC7 | `bc7-rgba-unorm-srgb` | High-quality albedo | Requires `texture-compression-bc` |

**Fallback when `texture-compression-bc` is unavailable** (mobile browsers, some Android):

1. Decompress BCn to RGBA8 on the CPU during loading using a JavaScript BC decoder
2. Upload as `rgba8unorm` textures
3. Cost: ~4x more GPU memory, slower initial load, but identical visual quality

### Texture Format Conversion Pipeline

```
.pak file -> extract DDS -> parse DDS header -> determine BCn format
  |
  +--> [BC supported] -> createTexture(bcN format) -> writeTexture(DDS data)
  |
  +--> [BC not supported] -> CPU decompress BCn to RGBA8 -> createTexture(rgba8unorm) -> writeTexture
  |
  +--> Generate mipmaps if DDS has < full mip chain
```

### Streaming vs All-at-Once

**Decision: Progressive streaming with priority queue.**

A TM2020 Stadium map references the Stadium.pak (1.63 GB of assets). Loading everything at once is infeasible for a browser. Instead:

1. **Priority 0 (immediate)**: Load block meshes for blocks visible in the starting camera position. Load 1x1 placeholder textures (mid-gray albedo, flat normal, default specular).

2. **Priority 1 (first 2 seconds)**: Load albedo textures for visible blocks at lowest mip level (128x128 or 256x256). Render becomes recognizable.

3. **Priority 2 (next 5 seconds)**: Load full-resolution textures for near blocks. Load normal and specular maps. Start loading car model.

4. **Priority 3 (background)**: Load remaining textures, distant block meshes, vegetation, decoration.

5. **On-demand**: Textures for blocks that become visible as the camera moves. Use the LOD system to determine which mip levels to load first.

### GPU Memory Budget Management

| Budget Category | Tier 1 | Tier 2 | Tier 3 |
|-----------------|--------|--------|--------|
| Render targets | 80 MB | 148 MB | 200 MB |
| Shadow maps | 32 MB | 64 MB | 64 MB |
| Textures | 256 MB | 512 MB | 768 MB |
| Mesh buffers | 64 MB | 128 MB | 128 MB |
| Misc (uniforms, staging) | 16 MB | 32 MB | 32 MB |
| **Total** | **448 MB** | **884 MB** | **1192 MB** |

The browser's WebGPU implementation will enforce adapter limits. We query `adapter.limits.maxBufferSize` and `adapter.requestAdapterInfo()` to estimate available VRAM and adjust texture quality accordingly.

**Texture eviction policy**: When approaching the texture budget, evict the lowest-priority texture (farthest from camera, lowest visual impact) by replacing it with a lower mip level. Track last-used frame per texture for LRU eviction.

---

## 8. The Block Mesh Problem (CRITICAL)

This is the single biggest blocker for the entire OpenTM renderer. The visual appearance of a Trackmania map depends on block geometry, and that geometry is locked inside encrypted pack files.

### What We Know

#### NadeoPak Format

The game ships with `.pak` files that contain all block models, textures, and materials. From analysis (doc 28, Section 5.4):

| Pack File | Size | Content |
|-----------|------|---------|
| Stadium.pak | 1.63 GB | All block models, textures, materials for Stadium |
| GreenCoast.pak | 569 MB | Green coast theme variant |
| BlueBay.pak | 530 MB | Blue bay theme variant |
| RedIsland.pak | 776 MB | Red island theme variant |
| WhiteShore.pak | 411 MB | White shore theme variant |

The NadeoPak format uses a header with version 18. The file table is encrypted (Blowfish or similar symmetric cipher). Nadeo has not published the encryption key or documented the format publicly. Community tools (notably the GBX.NET library) have partial support for reading NadeoPak headers but cannot decrypt the file table without the game's key material.

#### What Map Files Contain

Map files (`.Map.Gbx`) contain block placement data only (doc 28, Section 2.4):
- Block name (e.g., `"StadiumRoadMainStraight"`)
- Grid coordinates (x, y, z as uint32)
- Direction (0-3 cardinal)
- Flags (ground, free, ghost)

They do NOT contain block geometry. The game resolves block names to meshes by looking them up in the loaded .pak environment.

#### Custom Items DO Contain Geometry

Custom items embedded in maps (doc 28, Section 4.4) carry their own `CPlugSolid2Model` mesh data inside the `.Item.Gbx` file, which is itself embedded in the map. These can be parsed -- the GBX.NET library reads `CPlugSolid2Model` vertices, indices, and materials.

### Approaches to Solving the Block Mesh Problem

#### Approach 1: Decrypt NadeoPak Files

**Feasibility**: LOW. The encryption key is embedded in the game binary, potentially obfuscated with XOR/ADD operations (doc 15, Section 1 shows XOR obfuscation on function pointers). Extracting and distributing the key would likely violate Nadeo's EULA and potentially DMCA. This approach is legally risky and ethically questionable.

**Verdict**: Not pursued.

#### Approach 2: Runtime Geometry Capture via Openplanet

**Feasibility**: MEDIUM. Openplanet has access to the game's scene graph at runtime (doc 19, Section 4: `ISceneVis` manager architecture with indexed managers). An Openplanet plugin could:

1. Enumerate all `CSceneVehicleVis` and scene objects via the manager array
2. Hook into the D3D11 draw calls to capture vertex/index buffers as they are submitted
3. Export the captured geometry to a file

**Challenges**:
- Openplanet provides memory access but not direct D3D11 hook capability out of the box
- Vertex data in GPU buffers may not be easily readable from CPU-side Openplanet
- Would need to capture geometry for every unique block type (estimated ~200+), every LOD level, and every theme
- One-time capture effort, but needs to be repeated when game updates add new blocks

**Verdict**: Worth investigating as a semi-automated tool. Create an Openplanet plugin that dumps visible geometry per-frame, then post-process the dumps to extract unique block meshes.

#### Approach 3: Generate Procedural Block Geometry from Metadata

**Feasibility**: MEDIUM-HIGH. We know:
- Block names encode their shape: `StadiumRoadMainStraight`, `StadiumRoadMainCurve`, `StadiumRoadMainSlope` (doc 28, Section 2.2)
- Grid coordinates give exact placement: 32m XZ, 8m Y (doc 28, Section 1.2)
- Block types have known categories: Road, Platform, Decoration, Pillar (doc 28, Section 2.2)
- Material surface IDs are known for all 208 materials (doc 19, Section 10)
- Road blocks have standard widths (x1, x2, x3, x4 variants)

A procedural generator could:
1. Parse the block name to determine shape (straight, curve, slope, tilt, etc.)
2. Generate a parametric mesh matching the 32m grid dimensions
3. Apply appropriate UV mapping for the road/platform/dirt/ice material
4. Texture with extracted or recreated material textures

**Challenges**:
- Decorative details (guard rails, lane markings, surface texturing) would be approximate
- Complex blocks (chicanes, diagonal pieces, intersections) have non-trivial geometry
- Would not match TM2020's exact visual appearance pixel-for-pixel
- Significant engineering effort for the geometry generation library

**Verdict**: This is the most legally clean approach. Produces a "spiritual recreation" rather than an exact copy. Should be pursued as the primary strategy for MVP.

#### Approach 4: Community-Created Block Meshes

**Feasibility**: HIGH (with community effort). The Trackmania community has active modding tools:
- **Blendermania** (the blender addon in this project) exports .Item.Gbx files with CPlugSolid2Model geometry
- Community members could recreate stock block geometry in Blender and export as .Item.Gbx
- The GBX.NET library can then read these files to extract vertex/index data

**Workflow**:
1. Document the exact dimensions and shape of each stock block type (from in-game measurements or the procedural approach)
2. Community volunteers model each block in Blender using Blendermania's material system
3. Export as .Item.Gbx
4. Build a community block mesh library that OpenTM loads instead of .pak data

**Challenges**:
- Requires significant community effort (~200+ unique block types)
- Quality depends on volunteer modelers
- Must match exact dimensions for gameplay accuracy (collision detection)
- Ongoing maintenance as Nadeo adds new blocks

**Verdict**: Best long-term solution. Start with the most common blocks (straight road, curves, slopes) and expand.

#### Approach 5: Hybrid Procedural + Capture

**Feasibility**: HIGHEST. Combine approaches:

1. **Phase 1**: Procedural geometry for all block types. Simple box/extrusion meshes with correct dimensions. Apply flat-color materials matching the surface type. This gets maps renderable immediately.

2. **Phase 2**: Openplanet geometry capture tool to extract reference meshes for the most important block types. Use these as ground truth to improve the procedural generator.

3. **Phase 3**: Community modeling to replace procedural blocks with high-quality recreations.

### The Minimum Viable Approach

**For MVP, use procedural geometry (Approach 3/5 Phase 1)**:

1. Parse map block placements from `.Map.Gbx`
2. For each block, generate a simple mesh:
   - Road blocks: Flat quad (32m x 32m) elevated to correct Y, with road-colored material
   - Slope blocks: Angled quad connecting two Y levels
   - Curve blocks: Arc-shaped mesh following the standard 32m turn radius
   - Platform blocks: Flat surface with platform material
   - Pillar/Pylon blocks: Vertical box from ground to block Y level
3. Apply basic materials (solid colors matching surface type: gray for road, green for grass, white for ice, brown for dirt)
4. No decorative details in MVP

This produces a playable-looking map with correct geometry for driving, even if it lacks TM2020's visual richness. Textures and detail are added incrementally.

---

## 9. Performance Optimization Strategy

### Frustum Culling (GPU Compute Shader)

Matches TM2020's `DipCulling` pass using `Instances_Cull_SetLOD_c.hlsl` (doc 32, Section 7).

**Implementation** (Tier 2+):

```
Input:
  - Instance buffer: N instances with (world transform, bounding sphere)
  - Frustum planes: 6 planes extracted from view-projection matrix

Compute pass:
  - Workgroup size: 64 threads
  - Each thread tests one instance against 6 frustum planes
  - If visible: atomically increment visible count, write instance index to output
  - Also select LOD based on screen-space projected size

Output:
  - Compacted visible instance buffer
  - DrawIndexedIndirect arguments per (mesh, LOD) pair
```

At Tier 0-1, frustum culling runs on the CPU. The 32m block grid makes this efficient: precompute which grid cells intersect the frustum, then only submit instances in visible cells.

### Occlusion Culling (Hierarchical Z-Buffer)

For Tier 2+, build a depth pyramid (Hi-Z) after the depth prepass:

1. Render all opaque geometry depth-only
2. Downsample depth buffer: 4 levels (full, 1/2, 1/4, 1/8), taking the max depth at each level (matching TM2020's `DepthDown2x2_Max_p.hlsl` and `DepthDown3x3_Max_p.hlsl` from doc 32)
3. In the GPU cull compute shader, project each instance's bounding box to screen space and sample the Hi-Z at the appropriate mip level
4. If the object's nearest depth is behind the Hi-Z value, cull it

### LOD System

Matches TM2020's `GeomLodScaleZ` system (doc 19, Section 12; doc 11, Section 14):

| LOD Level | Screen Coverage | Description |
|-----------|----------------|-------------|
| 0 | > 10% screen | Full detail mesh |
| 1 | 5-10% screen | Simplified mesh (~50% triangles) |
| 2 | 2-5% screen | Low-poly mesh (~25% triangles) |
| 3 | < 2% screen | Billboard impostor (trees) or skip (small objects) |

LOD selection happens in the GPU cull compute shader (Tier 2+) or on the CPU (Tier 0-1). The `GeomLodScaleZ` multiplier adjusts all LOD transition distances uniformly.

For trees at LOD 3, we use billboard impostors matching TM2020's `Tree_Impostor_DefWrite_p/v.hlsl` and `DeferredOutput_ImpostorConvert_c.hlsl` (doc 32, Section 2.1).

### Draw Call Batching (Indirect Rendering)

Tier 2+ uses `drawIndexedIndirect` for all block geometry:

1. **Group by material**: All instances sharing a (mesh, material) pair are in one indirect draw
2. **GPU cull writes args**: The compute shader outputs `DrawIndexedIndirectArgs` structs directly to a storage buffer
3. **Single dispatch**: One `drawIndexedIndirect` call per unique (mesh, material, LOD) combination
4. **Multi-draw indirect**: When `multi-draw-indirect` WebGPU extension becomes available, collapse further

Expected draw call count at Tier 2: ~200 indirect draws for blocks + ~50 for cars/items + ~20 for post-processing = ~270 total draw calls. This is orders of magnitude better than naive per-block draws.

### Texture Atlasing

Block materials reuse a small number of texture sets (Road, Platform, Dirt, Ice, Grass, etc.). Instead of binding individual textures per block:

1. Atlas albedo textures for each surface type into 2048x2048 or 4096x4096 texture arrays
2. Store atlas UV offset/scale per material in a uniform buffer
3. Bind the entire atlas array once per frame, index by material ID in the shader

This eliminates texture bind changes between draw calls, enabling the full instancing pipeline.

---

## 10. WebGPU Feature Requirements

### Required Features

| Feature | Purpose | Browser Support (as of 2026-03) |
|---------|---------|-------------------------------|
| `float32-filterable` | Shadow map comparison sampling, HDR texture filtering | Chrome 121+, Firefox 129+, Safari 18.2+ |
| `rg11b10ufloat-renderable` | Compact HDR render targets for bloom chain | Chrome 121+, Firefox 131+, Safari 18.2+ |
| `depth-clip-control` | Prevent far-plane clipping artifacts in shadow maps | Chrome 121+, Firefox 129+, Safari 18.2+ |

### Optional Features

| Feature | Purpose | Fallback | Browser Support |
|---------|---------|----------|----------------|
| `texture-compression-bc` | Native DDS/BCn texture support (no CPU decompress) | CPU decompress to RGBA8 (4x memory) | Chrome (desktop only), Firefox (desktop only). NOT Safari/mobile |
| `texture-compression-etc2` | Compressed textures on mobile/Apple | CPU decompress to RGBA8 | Safari, Android Chrome |
| `indirect-first-instance` | Base instance offset in indirect draws | Separate buffer per instance group | Chrome 121+, partial Safari |
| `timestamp-query` | GPU performance profiling | Software timers | Chrome 121+, Firefox 131+ |

### Required Limits

```javascript
const requiredLimits = {
    maxColorAttachments: 4,                 // G-buffer MRT (4 render targets)
    maxBindGroups: 4,                       // Frame / Pass / Material / Draw
    maxBindingsPerBindGroup: 16,            // Deferred lighting reads many textures
    maxUniformBufferBindingSize: 65536,     // 64KB uniform buffers
    maxStorageBufferBindingSize: 134217728, // 128MB storage (instance data, particles)
    maxComputeWorkgroupSizeX: 256,          // GPU cull workgroup
    maxComputeInvocationsPerWorkgroup: 256, // GPU cull
    maxTextureDimension2D: 8192,            // Shadow map + texture atlas
    maxTextureDimension3D: 256,             // Volumetric fog froxel grid
    maxTextureArrayLayers: 256,             // Shadow cascade array + texture arrays
    maxSampledTexturesPerShaderStage: 16,   // G-buffer read binds many textures
    maxSamplersPerShaderStage: 8,           // Various sampler types
};
```

### Browser Compatibility Matrix

| Browser | Min Version | Tier 0 | Tier 1 | Tier 2 | Tier 3 | Notes |
|---------|-------------|--------|--------|--------|--------|-------|
| Chrome (desktop) | 113 | Yes | Yes | Yes | Yes | Full support including BC textures |
| Chrome (Android) | 121 | Yes | Yes | Partial | No | No BC textures, limited VRAM |
| Firefox (desktop) | 129 | Yes | Yes | Yes | Partial | No `indirect-first-instance` until 134 |
| Safari (macOS) | 18.2 | Yes | Yes | Yes | Partial | No BC textures; use ETC2 instead |
| Safari (iOS/iPadOS) | 18.2 | Yes | Partial | No | No | Limited VRAM, no compute-heavy tiers |
| Edge (desktop) | 113 | Yes | Yes | Yes | Yes | Same as Chrome (Chromium) |

### Mobile Browser Compatibility Notes

Mobile browsers present significant limitations for Tier 2+:
- **GPU memory**: Typically 1-2 GB shared with system. Our Tier 2 budget of 884 MB may exceed available memory. Downscale textures and render resolution.
- **No BC textures**: Mobile GPUs (Adreno, Mali, Apple GPU) do not support BCn. Must decompress to RGBA8 or use ETC2/ASTC.
- **Thermal throttling**: Sustained GPU compute workloads (SSAO, GPU cull, particles) will trigger thermal throttling on mobile. Tier 1 is the practical maximum for phones.
- **`maxTextureDimension2D`**: Some mobile GPUs cap at 4096. Shadow maps must be 2048 or lower.

---

## 11. Unknown Analysis

### Critical Unknowns

#### Unknown 1: Exact G-Buffer DXGI Formats

**What we don't know**: The exact `DXGI_FORMAT` of each MRT target (doc 11: "Exact G-buffer DXGI formats: HIGH priority").

**Impact on visual quality**: MEDIUM. If the format is wrong (e.g., we use `rgba8unorm` for normals when TM2020 uses `rgba16float`), specular highlights will show banding artifacts on smooth surfaces. If the format is too large, we waste GPU memory.

**Workaround**: Our format choices (`rgba8unorm-srgb` for albedo, `rgba8unorm` for specular, `rg16float` for normals, `rgba8unorm` for light mask) are standard deferred renderer choices that match the evidence. The `DeferredDeCompFaceNormal_p.hlsl` shader confirms compressed normal storage, which aligns with our `rg16float` octahedral choice.

**Research to resolve**: Decompile the texture creation calls near the `DeferredWrite` setup code. Specifically, trace the `CDx11Viewport` calls that create the G-buffer render targets and extract the DXGI format parameters. Address range: near `0x1409aa750` (device creation) and `0x14095d430` (viewport setup).

---

#### Unknown 2: G-Buffer MRT Count (Simultaneous)

**What we don't know**: Whether TM2020 binds 4, 5, or 6 MRT outputs simultaneously during `DeferredWrite`, or uses multiple sub-passes.

**Impact on visual quality**: LOW. The visual result is the same whether normals are written in the main MRT or a separate pass. But it affects performance -- more simultaneous MRTs means fewer render passes but higher bandwidth per pixel.

**Workaround**: We bind 4 color attachments in `DeferredWrite` (albedo, specular, normal, light mask) + depth. Face normals are reconstructed from depth in a separate pass (`DeferredFaceNormalFromDepth_p.hlsl`), which TM2020 appears to do as well (doc 11, Section 3: "Face normals possibly reconstructed from depth"). Vertex normals are written during the main MRT pass as part of the normal output. This matches the documented pass structure.

**Research to resolve**: Trace the MRT setup in `CDx11RenderContext` to see how many render target views are bound simultaneously during the `DeferredWrite` pass.

---

#### Unknown 3: PSSM Split Distances

**What we don't know**: The exact cascade split formula and distances (doc 11: "SPECULATIVE for exact split distances").

**Impact on visual quality**: MEDIUM. Wrong split distances produce either shadow resolution wasted on distant terrain (splits too uniform) or shadow gaps near the camera (splits too logarithmic). The visual artifact is shadow aliasing -- stairstepping at cascade boundaries.

**Workaround**: Use the practical split scheme (Engel's blend of logarithmic and linear) with our tuned values from Section 5. These can be adjusted at runtime via a debug UI.

**Research to resolve**: Decompile `FUN_140a45310` (cascade setup function referenced in doc 11). Extract the split distance computation. Alternatively, use an Openplanet plugin to read the shadow cascade matrices at runtime and reverse-engineer the split from the projection bounds.

---

#### Unknown 4: Normal Encoding Method

**What we don't know**: Whether TM2020 uses octahedral, spheremap, or another normal encoding (doc 11: "SPECULATIVE -- decompression shader exists, exact encoding unknown").

**Impact on visual quality**: LOW-MEDIUM. Different encodings produce slightly different reconstruction error patterns. Octahedral has the most uniform error distribution. Spheremap has higher error at the equator. If TM2020 uses spheremap and we use octahedral, lighting will differ subtly at grazing angles.

**Workaround**: Octahedral encoding is the industry standard for deferred renderers since 2014. It provides the best quality-to-memory ratio for 2-channel storage. Even if TM2020 uses a different encoding, our visual quality will be comparable or better.

**Research to resolve**: Decompile `DeferredDeCompFaceNormal_p.hlsl` shader bytecode. The decompression function will reveal the encoding method directly.

---

#### Unknown 5: Filmic Tone Curve Parameters

**What we don't know**: The exact `NFilmicTone_PowerSegments::SCurveParamsUser` values (toe, linear, shoulder parameters).

**Impact on visual quality**: MEDIUM. The tone curve defines the overall "look" of the game -- how bright scenes appear, how shadows crush, how highlights roll off. Wrong parameters will make the game look too washed out or too contrasty.

**Workaround**: Use ACES or Khronos PBR Neutral tone mapping as a starting point. Expose curve parameters in a debug UI. Compare screenshots with TM2020 and adjust until the look matches.

**Research to resolve**: Decompile `NFilmicTone_PowerSegments` struct and extract the default parameter values. Alternatively, capture a TM2020 frame with known HDR values (e.g., a scene with a white surface lit by the sun at known intensity) and fit the tone curve to match the LDR output.

---

#### Unknown 6: TAA Jitter Pattern

**What we don't know**: Whether TM2020 uses Halton(2,3), rotated grid, or another jitter sequence (doc 11: "SPECULATIVE for exact pattern").

**Impact on visual quality**: LOW. All standard jitter patterns produce acceptable TAA results. The main difference is convergence speed -- Halton converges slightly faster than random but is also slightly more prone to structured aliasing.

**Workaround**: Use Halton(2,3) with 8 samples per cycle. This is the most common TAA jitter pattern and produces well-distributed sub-pixel offsets.

**Research to resolve**: Trace the `PosOffsetAA` generation code. Read the per-frame jitter values from the `TemporalAA_Constants` buffer via an Openplanet plugin.

---

#### Unknown 7: PreShade Buffer Purpose

**What we don't know**: What `BitmapDeferredPreShade` contains (doc 11: "NEEDS INVESTIGATION").

**Impact on visual quality**: LOW-MEDIUM. If it stores emissive data, we already handle that via `light_mask.g` (self-illumination flag). If it stores pre-computed BRDF response, omitting it may slightly affect the efficiency of our deferred read but not the final quality.

**Workaround**: Omit PreShade entirely. Handle emissive via the light mask channel. If visual comparison reveals missing effects, investigate and add a PreShade equivalent.

**Research to resolve**: Trace write/read references to `"BitmapDeferredPreShade"` in the binary. Identify which shaders write to it and which read from it. The write shader will reveal the data format and content.

---

#### Unknown 8: Shadow Filtering Quality (PCF Kernel)

**What we don't know**: The exact PCF kernel size and whether TM2020 uses PCSS (percentage-closer soft shadows) for the `HqSoftShadows` mode.

**Impact on visual quality**: MEDIUM. PCF kernel size directly affects shadow softness. Too small (2x2) gives hard pixelated shadows. Too large (7x7+) gives uniformly blurry shadows. PCSS provides contact-hardening shadows that are soft at distance and sharp near the caster -- a significant visual quality upgrade.

**Workaround**: Start with 4-tap PCF for Tier 1-2 (matches the 4-sample pattern used in most deferred renderers). Upgrade to 9-tap Poisson disk for Tier 3. Add optional PCSS in Tier 3 using the blocker search technique.

**Research to resolve**: Decompile `DeferredShadowPssm_p.hlsl` shader bytecode. The sampling pattern will be visible as a loop with offset constants.

---

#### Unknown 9: Lightmap H-Basis Encoding Details

**What we don't know**: The exact H-basis coefficient layout and YCbCr4 compression format used for lightmaps.

**Impact on visual quality**: MEDIUM-HIGH. Lightmaps provide the ambient lighting foundation for the entire scene. Incorrect decode produces wrong ambient colors and intensities. TM2020 uses H-basis (half-life basis) -- a directional irradiance encoding that allows bump-mapped surfaces to receive directional baked lighting (doc 11, Section 10: "H-basis encoding allows per-pixel directional lighting from the lightmap").

**Workaround**: For MVP, sample lightmaps as flat irradiance (ignore H-basis directionality). This produces acceptable but less detailed lighting on bumped surfaces. Upgrade to full H-basis decode once the format is reverse-engineered.

**Research to resolve**: Analyze `LmCompress_HBasis_YCbCr4_c.hlsl` shader bytecode. The H-basis decode will reveal coefficient order, and the YCbCr conversion will reveal the color space transform. Community tools (GBX.NET) may already decode lightmap data -- check their source.

---

*Document produced from cross-referencing docs 11, 15, 19, 28, and 32. All format choices and architecture decisions cite specific evidence from the reverse engineering. Confidence levels are inherited from the source documents.*

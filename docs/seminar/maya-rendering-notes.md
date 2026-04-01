# Maya's Rendering Notes: Trackmania 2020 Deep Dive

## The Deferred Pipeline

This chapter covers deferred rendering fundamentals, the 19-pass pipeline, and the full frame structure. You will understand how TM2020 decouples geometry complexity from lighting complexity.

### What IS Deferred Rendering?

Let me make sure I really understand this before writing it down.

In **forward rendering**, you draw each object and light it on the spot. 100 objects and 50 lights means 5000 shader invocations (multi-pass) or one uber-shader cramming all 50 lights. Either way, you pay for lights even when they do not touch a pixel.

In **deferred rendering**, you split the work:
1. **G-Buffer Fill**: Draw all geometry ONCE, writing material properties (albedo, normal, roughness) into multiple render targets. No lighting.
2. **Lighting Pass**: Read the G-buffer. For each light, shade only the pixels it actually reaches.

```
FORWARD:
  For each object:
    For each light affecting object:
      shade(object, light) -> framebuffer

DEFERRED:
  For each object:
    write_material(object) -> G-buffer    (NO lighting!)

  For each pixel on screen:
    read_material(G-buffer)
    For each light affecting THIS pixel:
      shade(material, light) -> HDR buffer
```

**Why is this good for a racing game?** TM2020 tracks have LOTS of lights -- checkpoint gates, lamp posts, neon signs, dynamic car headlights. Deferred lets you decouple geometry from lighting. Whether you have 5 or 500 lights, G-buffer fill costs the same.

The downside? Transparent objects cannot be deferred. TM2020 uses a hybrid: deferred for opaques, forward for transparents. Standard practice.
(Source: doc 05, Section 2; doc 11, Section 4; doc 15, Section 7)

### The 19 Deferred Passes

Verified pass ordering from doc 15, Section 7 and doc 11, Section 4:

```
THE FULL DEFERRED PIPELINE (19 PASSES)
========================================

 Pass #   Name                    What It Does
 ------   ----                    ------------
  1       DipCulling              GPU frustum culling + LOD select (compute)
  2       DeferredWrite           G-buffer fill -- ALL opaque geometry
  3       DeferredWriteFNormal    Face normal generation (flat geometric normals)
  4       DeferredWriteVNormal    Vertex normal pass (smooth interpolated)
  5       DeferredDecals          Project decals onto G-buffer (road markings, etc.)
  6       DeferredBurn            Tire scorch marks and burn effects
  7       DeferredShadow          Sample the 4 PSSM cascade shadow maps
  8       DeferredAmbientOcc      HBAO+ ambient occlusion (6-step pipeline, runs TWICE)
  9       DeferredFakeOcc         Cheap AO for distant objects
 10       CameraMotion            Per-pixel motion vectors for TAA / motion blur
 11       DeferredRead            Start lighting -- ambient + Fresnel + lightmap
 12       DeferredReadFull        Complete ambient/indirect resolution
 13       Reflects_CullObjects    Cull objects for reflection probes (CPU-side)
 14       DeferredLighting        Point/spot/area light accumulation
 15       CustomEnding            Custom post-lighting effects
 16       DeferredFogVolumes      Box-shaped volumetric fog volumes
 17       DeferredFog             Global distance + height fog
 18       LensFlares              Occlusion-queried lens flare sprites
 19       FxTXAA                  Temporal anti-aliasing resolve
```

(Source: doc 15, Section 7; doc 11, Section 4 Phases 1-12)

### The Full Frame -- Beyond the 19 Passes

The 19 passes are just the deferred core. A complete frame is much bigger:

```
 CPU WORK                          GPU WORK
 --------                          --------
 Input polling (100 Hz physics)
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
                            | CubeReflect      |   (6-face cubemap)
                            | WaterReflect     |   (planar reflection)
                            +------------------+
                                     |
                                     v
                            +==================+
                            | G-BUFFER FILL    |   <-- THE 19 PASSES
                            | (passes 1-19)    |       HAPPEN IN HERE
                            +==================+
                                     |
                                     v
                            +------------------+
                            | FORWARD PASS     |
                            | ForestRender     |   (alpha-to-coverage trees)
                            | GrassRender      |   (instanced grass)
                            | AlphaBlend       |   (transparent objects)
                            | ParticlesRender  |
                            | GhostLayer       |   (ghost car overlay)
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | POST-PROCESSING  |
                            | Fog, DoF, Blur   |
                            | ToneMap, Bloom   |
                            | FXAA/TXAA        |
                            | ColorGrading     |
                            +------------------+
                                     |
                                     v
                            +------------------+
                            | FINAL OUTPUT     |
                            | GUI / Overlays   |
                            | SwapChainPresent |
                            +------------------+
```

(Source: doc 11, Section 1, verified against pass ordering in Section 4)

### G-Buffer Data Flow

```
                     +--------+
                     | INPUTS |
                     +--------+
                         |
   Vertex data ----+    |
   (pos, normal,   |    |
   uv, tangent)    |    |
                   v    v
               +-------------+
               | DeferredWrite|  <-- Block_TDSN_DefWrite_p/v.hlsl
               | (Pass #2)   |      CarSkin_DefWrite_p/v.hlsl
               +------+------+      Tree_SelfAO_DefWrite_p/v.hlsl
                      |
            +---------+---------+---------+---------+
            v         v         v         v         v
        +-------+ +-------+ +-------+ +-------+ +-------+
        |MDiff  | |MSpec  | |PxlNrm| |LtMask | |Depth  |
        |RT0    | |RT1    | |RT2   | |RT3    | |D24S8  |
        +---+---+ +---+---+ +---+---+ +---+---+ +---+---+
            |         |         |         |         |
            +---------+---------+---------+---------+
                              |
                              v
               +-------------------------------+
               | DeferredRead / DeferredLighting|
               | (Passes #11-14)                |
               +---------------+---------------+
                               |
                               v
                     +---------+---------+
                     |  HDR Color Buffer |
                     |  (lit scene)      |
                     +-------------------+
```

**Inputs**: Geometry with material textures (albedo, specular, normal maps), lightmap UVs.
**Outputs**: 9 named render targets (see next chapter), consumed by lighting to produce HDR.
(Source: doc 11, Sections 3-4)

### Three Normal Buffers -- Why?

This threw me. Most engines store ONE normal in the G-buffer. TM2020 stores THREE:

1. **PixelNormalInC** -- Bump-mapped per-pixel normal in camera space. The "real" normal for lighting. Written during DeferredWrite from tangent-space normal maps.

2. **FaceNormalInC** -- Flat geometric face normal. HBAO+ needs it for stable AO (bump maps cause flickering). FXAA uses it for silhouette edge detection. Shadow bias needs the true surface angle. Can be reconstructed from depth via `DeferredFaceNormalFromDepth_p.hlsl`.

3. **VertexNormalInC** -- Smooth vertex-interpolated normal. Bilateral blur edge detection uses it. Subsurface scattering direction needs the smooth surface normal.

**My thought**: For WebGPU, I would reconstruct face normals from depth derivatives in-shader instead of a separate buffer. Saves a full RT at 4 bytes/pixel. The vertex normal buffer is harder to skip if you want SSS.

(Source: doc 11, Section 3 "Why Three Normal Buffers?"; doc 15, Section 7)

---

## G-Buffer Anatomy

This chapter covers the 9 named render targets, format choices, and memory budget. You will understand what data flows through each G-buffer channel.

### 9 Named Render Targets

```
G-BUFFER MEMORY LAYOUT
===========================================================================================
 #  Target              | Channels           | Format (likely)          | Written In
===========================================================================================
 0  MDiffuse            | RGB: albedo color  | R8G8B8A8_UNORM_SRGB     | DeferredWrite
    (Material Diffuse)  | A: [unknown-AO?    |                          |
                        |     or mat ID]     |                          |
-------------------------------------------------------------------------------------------
 1  MSpecular           | RGB: F0 reflectance| R8G8B8A8_UNORM           | DeferredWrite
    (Material Specular) | A: roughness       |                          |
                        |    (or glossiness) |                          |
-------------------------------------------------------------------------------------------
 2  PixelNormalInC      | RG: octahedral XY  | R16G16_FLOAT             | DeferredWrite
    (Pixel Normal,      | (Z reconstructed)  | (or R16G16B16A16_FLOAT)  |
     Camera Space)      |                    |                          |
-------------------------------------------------------------------------------------------
 3  LightMask           | R: LM tier index   | R8G8B8A8_UNORM           | DeferredWrite
                        | G: self-illumination|                          |
                        | B: receives shadows|                          |
                        | A: receives LM     |                          |
-------------------------------------------------------------------------------------------
 4  DeferredZ (Depth)   | D24 + S8 stencil   | D24_UNORM_S8_UINT        | DeferredWrite
                        |                    | (VERIFIED from D3D11 log)|
-------------------------------------------------------------------------------------------
 5  FaceNormalInC       | RG: flat normal XY | R16G16_FLOAT             | DeferredWriteFN
    (Face Normal)       |                    | (or R8G8_SNORM)          | (or from depth)
-------------------------------------------------------------------------------------------
 6  VertexNormalInC     | RG: smooth norm XY | R16G16_FLOAT             | DeferredWriteVN
    (Vertex Normal)     |                    | (or R8G8_SNORM)          |
-------------------------------------------------------------------------------------------
 7  PreShade            | [UNKNOWN]          | [UNKNOWN]                | [UNKNOWN]
                        | Possibly pre-      |                          |
                        | computed BRDF      |                          |
                        | or emissive term   |                          |
-------------------------------------------------------------------------------------------
 8  DiffuseAmbient      | RGB: diffuse color | R16G16B16A16_FLOAT       | DeferredRead
    (Lighting Result)   | * (ambient+LM)     | (HDR output!)            | DeferredReadFull
                        | A: [unknown]       |                          |
===========================================================================================
```

(Source: doc 15, Section 7; doc 11, Section 3; doc 05, Section 2)

Not all 9 are bound simultaneously as MRT outputs. The core MRT during DeferredWrite is **4 targets + depth** (RT0-RT3 + depth). Face normal, vertex normal, PreShade, and DiffuseAmbient are written in separate sub-passes.

### Format Choices (from doc 03)

| Target | WebGPU Format | Memory/pixel | Justification |
|--------|---------------|-------------|---------------|
| Albedo (RT0) | `rgba8unorm-srgb` | 4 bytes | sRGB matches perceptual color; 8-bit sufficient for albedo |
| Specular (RT1) | `rgba8unorm` | 4 bytes | F0 ranges 0.02-0.05 for dielectrics, maps to 8-bit [5-13] |
| Normal (RT2) | `rg16float` | 4 bytes | Octahedral encoding needs 2 channels; 16-bit gives ~0.001 angular precision |
| LightMask (RT3) | `rgba8unorm` | 4 bytes | Flag buffer, 4 independent channels |
| Depth | `depth24plus-stencil8` | 4 bytes | Verified from D3D11 log; stencil needed for deferred light volumes |
| HDR Accumulation | `rgba16float` | 8 bytes | Must exceed [0,1] for bright lights before tone mapping |

(Source: doc 03, Section 2)

### Memory Cost at Different Resolutions

```
                  1280x720    1920x1080   2560x1440   3840x2160
                  --------    ---------   ---------   ---------
Albedo (4B)       3.5 MB      7.9 MB      14.1 MB     31.6 MB
Specular (4B)     3.5 MB      7.9 MB      14.1 MB     31.6 MB
Normal (4B)       3.5 MB      7.9 MB      14.1 MB     31.6 MB
LightMask (4B)    3.5 MB      7.9 MB      14.1 MB     31.6 MB
Depth (4B)        3.5 MB      7.9 MB      14.1 MB     31.6 MB
HDR Accum (8B)    7.0 MB      15.8 MB     28.1 MB     63.3 MB
MotionVec (4B)    3.5 MB      7.9 MB      14.1 MB     31.6 MB
SSAO (1B half)    0.2 MB      0.5 MB      0.9 MB      2.0 MB
                  --------    ---------   ---------   ---------
G-Buffer Total:   28.2 MB     63.7 MB     113.7 MB    255.0 MB

Plus shadows:     16 MB       64 MB       64 MB       64 MB
Plus bloom:       ~2 MB       ~4 MB       ~7 MB       ~16 MB
Plus TAA history: 7.0 MB      15.8 MB     28.1 MB     63.3 MB
                  --------    ---------   ---------   ---------
TOTAL RT memory:  ~53 MB      ~148 MB     ~213 MB     ~398 MB
```

That 148 MB at 1080p is significant. On a phone browser, I would need to cut this hard.
(Source: doc 03, Section 2 "G-Buffer Memory Budget")

### PreShade vs DiffuseAmbient vs MDiffuse

```
TIMELINE OF A PIXEL'S COLOR:

1. MDiffuse        = raw albedo from texture. "M" means "Material."
                     BASE COLOR. Written during G-buffer fill. Input data, not lit.

2. PreShade        = [UNKNOWN] -- possibly pre-computed BRDF response,
                     emissive term, or simplified pre-lit diffuse.

3. DiffuseAmbient  = MDiffuse * (ambient + lightmap + indirect lighting).
                     LIGHTING RESULT -- accumulated diffuse irradiance. HDR output.

In equation form:
   MDiffuse         = texture_sample(albedo_map, uv)
   DiffuseAmbient   = MDiffuse * (Ambient + Lightmap + IndirectLight)
```

MDiffuse is an INPUT (material property). DiffuseAmbient is an OUTPUT (lighting result). PreShade is somewhere in between.
(Source: doc 11, Section 3)

### Comparison to Other Engines

| Feature | TM2020 | UE5 | Unity HDRP |
|---------|--------|-----|------------|
| Normal count | 3 (pixel, face, vertex) | 1 (GBufferB) | 1 (NormalBuffer) |
| PBR workflow | Specular/Glossiness | Metallic/Roughness | Metallic/Roughness |
| G-buffer MRT count | 4 + depth (core) | 6 + depth | 4 + depth |
| Normal encoding | Octahedral 2-ch (likely) | Octahedral 2-ch | Octahedral 2-ch |
| Light mask | Dedicated RT3 | Uses stencil bits | Material flags in GBuffer |

TM2020's specular/glossiness workflow is less common but has a real advantage: metals have colored F0 reflectance (copper is orange, gold is yellow), stored directly in RGB. Metallic/roughness reconstructs this from albedo when metallic=1.

(Source: doc 11, Section 10; doc 03, Section 2)

---

## Shaders

This chapter covers the 1,112-shader inventory, the Tech3 naming convention, and the uber-shader collapse. You will understand how 6 core block programs produce 180 shader permutations.

### 1,112 Shaders Collapse to ~38 Uber-Shaders

The shader cache (`GpuCache_D3D11_SM5.zip`) contains 1,112 compiled DXBC shader stages. Naming pattern analysis reveals massive combinatorial explosion from a small core:

```
SHADER STAGE BREAKDOWN:
  515 Pixel (Fragment) shaders    (_p.hlsl)
  388 Vertex shaders              (_v.hlsl)
  105 Compute shaders             (_c.hlsl)
   51 Pixel via text reference    (.PHlsl)
   40 Vertex via text reference   (.VHlsl)
    5 Geometry shaders            (_g.hlsl)
    4 Domain (tessellation eval)  (_d.hlsl)
    4 Hull (tessellation ctrl)    (_h.hlsl)
  ----
  1,112 total
```

The block shader family ALONE accounts for 180 entries from ~6 core programs:

```
6 CORE BLOCK SHADER PROGRAMS:
  1. Block_TDSN          -- Standard PBR (single UV mapping)
  2. Block_PyPxz         -- Triplanar Y + XZ projection
  3. Block_PyDSNX2       -- High-res Y-projected
  4. Block_PxzDSN        -- XZ-projected walls
  5. Block_PTDSN         -- Extra projection layer + TDSN
  6. Block_PyPxzTLayered -- Layered triplanar terrain blend

x 8 PIPELINE VARIANTS each:
  - Forward (_p/_v)
  - G-buffer fill (_DefWrite_p/_v)
  - Deferred lighting (_DefReadP1_* with LM0/LM1/LM2/COut/SI sub-variants)
  - Lightmap bake (_PeelDiff_p/_v)
  - Animated UVs (_Anim_v)
  - Shadow caster (_Shadow_v)
  - Depth-only (_ZOnly_p/_v)
  - Decal-modulated (_DecalMod_*)

x MODIFIERS (COut, CIn, DispIn, Hue, X2H2, ids, SI, OpBlend...)

= 180 block shaders!
```

(Source: doc 32, Section 5; doc 11, Section 7)

### The Tech3 Naming Convention

```
Tech3/Block_TDSN_Py_Pxz_DefWrite_p.hlsl
|     |     |    |   |   |        |
|     |     |    |   |   |        +-- Stage: p = pixel (fragment) shader
|     |     |    |   |   +-- Pipeline: DefWrite = G-buffer fill
|     |     |    |   +-- Pxz = XZ-plane triplanar projection
|     |     |    +-- Py = Y-axis triplanar projection (top-down)
|     |     +-- TDSN = Texture + Diffuse + Specular + Normal
|     +-- Block = track block geometry
+-- Tech3 = Nadeo's 3rd-gen shader framework
```

Full convention:
```
Tech3/<ObjectType>_<TextureSlots>_<Projection>_<Modifier>_<Pipeline>_<Stage>.hlsl

Object Types:    Block, CarSkin, CarDetails, CarGems, CarGlass, CarGhost,
                 BodyAnim, CharAnimSkel, Dyna, DynaFacing, DynaSpriteDiffuse,
                 Tree, Sea, Ocean, Grass, GrassFence, Voxel, VoxelIce,
                 Decal, DecalSprite, MenuBox, Ice, IceWall, Warp, Sky, Stars

Texture Slots:   T=Texture(albedo), D=Diffuse, S=Specular, N=Normal,
                 I=Illumination, E=Emissive, O=Occlusion, EM=EnvironmentMap

Projection:      Py=Y-axis, Pxz=XZ-plane, P=generic projection

Modifiers:       COut=ColorOutput, CIn=ColorInput, SI=SelfIllum,
                 LM0/LM1/LM2=Lightmap tier, X2=DoubleRes, H2=HalfRes,
                 Hue=HueShift, Op=Opacity, TDecalMod=Decal-modulated,
                 Layered=multi-layer blend

Pipeline:        DefWrite=G-buffer, DefRead/DefReadP1=deferred lighting,
                 PeelDiff=lightmap bake, Shadow=shadow caster, ZOnly=depth only

Stage:           _p=pixel, _v=vertex, _c=compute, _g=geometry, _h=hull, _d=domain
```

(Source: doc 32, Section 5; doc 05, Section 6; doc 11, Section 7)

### Minimum Shader Set for a Playable Game

From doc 32, Section 3:

**Tier 1 -- Required** (renders a visible scene): 12 shaders
- G-buffer fill, depth-only, deferred lighting, PSSM shadows, fullscreen utility, face normal, linear depth, tone mapping, sky, motion vectors

**Tier 2 -- Visual Quality**: +12 = 24 total
- Car skin/details/glass, decals, fog, bloom, FXAA, color grading, SSAO, GPU culling, trees, grass

**Tier 3 -- Full Feature Set**: +14 = 38 total
- SSR, TAA, particles, volumetric fog, water, clouds, DoF, motion blur, lens flares, ghost car, burn marks, impostors, PBR precompute

1,112 collapses because most shaders are permutations of the same logic with different texture slot configurations.
(Source: doc 32, Section 3)

---

## Lighting and Shadows

This chapter covers the PBR model, PSSM shadow cascades, and lightmap integration. You will understand why TM2020 uses specular/glossiness instead of metallic/roughness.

### PBR Model: Specular/Glossiness (NOT Metallic/Roughness!)

Most modern engines use metallic/roughness. TM2020 uses **specular/glossiness**.

Evidence:
- `Engines/Pbr_Spec_to_Roughness_c.hlsl` converts specular to roughness (specular workflow INPUT)
- Separate `MDiffuse` and `MSpecular` G-buffer targets
- `Pbr_IntegrateBRDF_GGX_c.hlsl` -- GGX BRDF LUT

**Why spec/gloss for a racing game?** Metal surfaces (chrome, railings, checkpoint gates) have COLORED reflections. In spec/gloss, store directly: copper F0 = (0.95, 0.64, 0.54). In metallic/roughness, you need the albedo for metal color, requiring shader branching on metallic=1.

```
SPECULAR/GLOSSINESS:
  MDiffuse  = RGB albedo (for dielectrics AND metals)
  MSpecular = RGB F0 reflectance + A glossiness

METALLIC/ROUGHNESS:
  Albedo    = RGB base color
  MetalRough = R metallic (0/1), G roughness
```

(Source: doc 11, Section 10; doc 32, Section 2.2)

### GGX BRDF

GGX (Trowbridge-Reitz) is the microfacet distribution function for specular BRDF:

```
INCOMING LIGHT               CAMERA
       \                      /
        \     HIGHLIGHT      /
         \   /=========\   /
          \ / microfacets\ /
    =============================
           ROUGH SURFACE

The highlight shape depends on:
  D (Distribution): How many microfacets point toward the half-vector?
     GGX gives a longer "tail" than Beckmann -> more realistic bright spots

  G (Geometry): How many microfacets are blocked by neighbors?
     Smith GGX height-correlated visibility term

  F (Fresnel): How much light reflects vs refracts at each angle?
     Schlick approximation: F = F0 + (1-F0)(1-cos(theta))^5
     At grazing angles, EVERYTHING becomes a mirror (even asphalt!)
```

The specular BRDF is:
```
specular = (D * G * F) / (4 * NdotV * NdotL)
```

TM2020 pre-computes a **BRDF integration LUT** via `Pbr_IntegrateBRDF_GGX_c.hlsl` -- a 2D texture indexed by (NdotV, roughness). This is the "split-sum" approximation for image-based lighting.
(Source: doc 11, Section 10; doc 03, Section 3; doc 32, Section 2.2)

### PSSM Shadow Cascades

PSSM (Parallel Split Shadow Maps) gives close objects high-resolution shadows and distant objects lower resolution:

```
PSSM CASCADE LAYOUT (from camera):

Camera  Cascade 0   Cascade 1    Cascade 2      Cascade 3
  |     (near)      (mid-near)   (mid-far)      (far)
  |<--->|<--------->|<---------->|<------------>|
  |  highest res    medium res    lower res       lowest res
```

Configuration from decompiled code (`CVisionViewport::VisibleZonePrepareShadowAndProjectors` at `0x14095d430`):
- Default: **4 cascades**
- Simplified: **1 cascade** (when `flag & 0x40` -- "Minimum" shadow quality)
- Filtering: PCF baseline + `"HqSoftShadows"` toggle
- Shadow cache: Static geometry cached via `ShadowCacheUpdate` compute shader

| Quality | Cascades | Behavior |
|---------|----------|----------|
| None | 0 | All shadow passes skipped |
| Minimum | 1 | Single cascade |
| Medium | 4 | Default |
| High | 4 | Larger shadow maps |
| Very High | 4 | Maximum resolution + HqSoftShadows |

Fake shadows (`ShaderGeomFakeShadows`, `FlatCubeShadow`) project simple darkened shapes for distant objects. Virtually free compared to real shadow maps.
(Source: doc 11, Section 5; decompiled `CVisionViewport_PrepareShadowAndProjectors_14095d430.c`)

### Lightmap Integration: Baked + Dynamic

```
LIGHTMAP PIPELINE:

BAKED (offline):
  CHmsLightMap computes per-texel lighting
  -> H-basis encoding (directional, not flat)
  -> YCbCr4 compression (LmCompress_HBasis_YCbCr4_c.hlsl)
  -> Stored as UV1 texture on block geometry

RUNTIME (DeferredRead phase):
  1. Deferred_SetILightDir_p.hlsl   -- Set indirect light direction from LM/probes
  2. Deferred_AddAmbient_Fresnel_p.hlsl -- Add ambient + Fresnel
  3. Deferred_AddLightLm_p.hlsl     -- Sample lightmap at UV1, multiply with MDiffuse
  4. Deferred_SetLDirFromMask_p.hlsl -- Derive light direction from LightMask buffer

  RESULT: DiffuseAmbient = MDiffuse * (ambient + lightmap + indirect)
```

**H-basis encoding** stores directional information, not flat irradiance. This enables per-pixel directional lighting from baked data when combined with bump-mapped normals.

For dynamic objects (cars): `LightFromMap` samples the baked lightmap AT the car's position. Light probe grid (`ProbeGrid_Sample_c.hlsl`) provides SH-based indirect lighting.
(Source: doc 11, Section 10; doc 32, Section 2.4)

---

## Post-Processing

This chapter covers the 14-step post-processing chain, TXAA, bloom, and tone mapping. You will understand the ordering dependencies and which effects are essential.

### The 14-Step Chain

Order matters. Verified sequence from doc 11, Section 4 Phase 9 + doc 32, Section 6:

```
POST-PROCESSING CHAIN (after deferred lighting)
================================================

 #   Stage              Key Shader(s)                        Essential?
 --  -----              -------------                        ----------
 1.  Fog Volumes        DeferredGeomFogBoxOutside_p/v        LUXURY
                        3DFog_RayMarching_c (volumetric)

 2.  Global Fog         DeferredFogGlobal_p                  ESSENTIAL
                        DeferredFog_p

 3.  Lens Flares        LensFlareOccQuery_v                  LUXURY
                        2dFlareAdd_Hdr_p (HDR composite)

 4.  Depth of Field     DoF_T3_BlurAtDepth_p                 LUXURY
                                                              (only in replays)

 5.  Motion Blur        MotionBlur2d_p                       LUXURY
                        (default intensity: 0.35)

 6.  General Blur       BlurHV_p (separable Gaussian)        INTERNAL
                        BilateralBlur_p

 7.  Colors             Colors_p (brightness/contrast/sat)   ESSENTIAL

 8.  Color Grading      ColorGrading_p (3D LUT lookup)       NICE-TO-HAVE
                        ColorBlindnessCorrection_p            (accessibility!)

 9.  Tone Mapping       TM_GetLumi_p -> ...chain...          ESSENTIAL
                        TM_GlobalFilmCurve_p

10.  Bloom              BloomSelectFilterDown2_p -> chain     ESSENTIAL
                        Bloom_HorizonBlur_p -> chain
                        Bloom_StreaksWorkDir_p (anamorphic)
                        Bloom_Final_p

11.  Anti-Aliasing      FXAA_p  OR  TemporalAA_p            ESSENTIAL
                        (NVIDIA GFSDK TXAA as hardware path)

12.  SSR                SSReflect_Deferred_p                 NICE-TO-HAVE
                        SSReflect_UpSample_p

13.  SSS                SeparableSSS_p (Jimenez technique)   LUXURY

14.  Final Blit         RasterBitmapBlend*_p -> back buffer  ESSENTIAL
                        DownSSAA if supersampling
```

(Source: doc 32, Section 6; doc 11, Section 4 Phases 9-13)

### TXAA -- Temporal Anti-Aliasing

TM2020 has TWO implementations:
1. **NVIDIA GFSDK TXAA** -- hardware vendor SDK, at `0x141c0f178`. Optimized for NVIDIA GPUs.
2. **Ubisoft Custom TXAA** (`UBI_TXAA`) -- software fallback via `TemporalAA_p.hlsl`. Cross-vendor.

```
TEMPORAL AA:

  Frame N-1 (history)     Frame N (current, with sub-pixel jitter)
  +------------------+    +------------------+
  |                  |    |  o  (jittered     |
  |   smooth, but    | -->|   projection     |
  |   may ghost      |    |   matrix)        |
  +------------------+    +------------------+
           |                       |
           v                       v
      REPROJECT via           CURRENT pixels
      motion vectors          (noisy, aliased)
           |                       |
           +--------> BLEND <------+
                        |
                        v
                  RESULT: smooth
                  AND temporally stable
```

Each frame, the projection matrix gets a tiny sub-pixel offset. Over multiple frames, different sub-pixel locations are sampled. TAA blends current frame with reprojected history (typically 90-95% history, 5-10% current).

Ghost rejection uses neighborhood clamping and motion rejection.
(Source: doc 15, Section 8; doc 11, Section 11)

### Bloom

```
HDR Scene Buffer
      |
      v
BloomSelectFilterDown2_p    -- Threshold + 2x downsample
      |
      v
BloomSelectFilterDown4_p    -- 4x downsample
      |
      v
Bloom_HorizonBlur_p         -- Horizontal Gaussian at each mip
      |
      v
Bloom_StreaksWorkDir_p       -- Directional streaks (anamorphic!)
      |
      v
Bloom_Final_p               -- Composite back onto HDR buffer
```

(Source: doc 11, Section 9; doc 32, Section 6)

### Tone Mapping

Filmic curve with power segments (similar to Hable/Uncharted 2):

```
TM_GetLumi_p            -- Extract luminance from HDR
TM_GetLog2LumiDown1_p   -- Progressive log2 luminance downsample
TM_GetAvgLumiCurr_p     -- Average luminance (auto-exposure target)
TM_GlobalFilmCurve_p    -- Apply filmic curve (shoulder+linear+toe)
```

(Source: doc 11, Section 9)

### HBAO+ Ambient Occlusion

Full 6-step pipeline:
```
Step 1: LinearizeDepth_p.hlsl        -- Hardware depth -> linear Z
Step 2: DeinterleaveDepth_p.hlsl     -- Split into 4x4 interleaved layers
Step 3: ReconstructNormal_p.hlsl     -- Normals from depth derivatives
Step 4: CoarseAO_p.hlsl             -- Main AO at quarter resolution
Step 5: ReinterleaveAO_p.hlsl       -- Recombine layers
Step 6: BlurX_p.hlsl + BlurY_p.hlsl -- Bilateral blur
```

**It runs TWICE.** Two parameter sets from the decompiled config at `0x14091f4e0`:
- `NvHBAO.*` -- Small-scale (contact shadows, fine detail)
- `NvHBAO_BigScale.*` -- Big-scale (room-scale ambient occlusion)

Results are multiplied for the final AO term. Fallback: `UseHomeMadeHBAO` switches to Nadeo's custom AO.
(Source: doc 11, Section 6; `NSysCfgVision_SSSAmbOcc_HBAO_14091f4e0.c`)

---

## Performance

This chapter covers frame budget, GPU culling, and LOD. You will understand how TM2020 fits a dense scene into 16.67ms.

### 16.67ms Frame Budget

```
ESTIMATED FRAME BUDGET (16.67ms at 60 FPS):
============================================
CPU Phase (overlapped):
  Input + Physics (100Hz)              ~1-2 ms
  Scene graph + Visibility             ~1-2 ms
  Command buffer recording             ~2-3 ms

GPU Phase:
  Shadow maps (4 cascades)             ~1.5-2.0 ms
  Scene prep (cubemap, particles)      ~0.5-1.0 ms
  G-buffer fill (DeferredWrite)        ~2.0-3.0 ms
  Screen-space (shadows, AO, motion)   ~1.5-2.0 ms
  Deferred lighting                    ~1.0-1.5 ms
  Forward pass (trees, glass, alpha)   ~1.0-2.0 ms
  Post-processing chain                ~2.0-3.0 ms
  Particles                            ~1.0-1.7 ms (budgeted!)
                                       -----------
  GPU total:                           ~10-16 ms
```

The particle system has a HARD budget: `ParticleMaxGpuLoadMs` at offset `0xB4`, default 1.7ms. The system dynamically reduces particle count to stay within budget.
(Source: doc 11, Section 12; decompiled `CSystemConfigDisplay_140936810.c`)

### GPU Frustum Culling

`DipCulling` runs compute shaders for GPU-side frustum culling + LOD selection:

```
Engines/Instances_Cull_SetLOD_c.hlsl     -- Frustum test + LOD per instance
Engines/Instances_Merge_c.hlsl           -- Merge surviving instance lists
Engines/IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl -- Write indirect draw args
```

Fully indirect rendering. The GPU decides what to draw and at what LOD. No CPU readback. Critical for thousands of block instances.

Forward+ tile culling (`Engines/ForwardTileCull_c.hlsl`) divides the screen into tiles for the transparent pass.
(Source: doc 11, Section 14; doc 32, Section 2.2)

### Mobile Browser -- What Would I Cut?

```
MOBILE BROWSER BUDGET (targeting 30 FPS on mid-range phone):
============================================================
KEEP:
  - Forward rendering (NO deferred -- mobile GPUs hate MRT bandwidth)
  - 1 directional light + hemisphere ambient
  - 1 shadow cascade (512x512)
  - FXAA
  - Simple fog (analytical, not ray-marched)
  - Albedo textures only
  - 720p or lower with render scaling

CUT:
  - Entire deferred pipeline
  - All 3 extra normal buffers
  - HBAO+ (replace with baked AO in vertex color)
  - SSR, bloom, TAA, volumetric fog, shadow cache
  - GPU culling compute shaders (do CPU-side frustum cull)
  - Lightmaps (bake into vertex color)

TARGET: NONE (forward renderer)
  - 1 color RT + 1 depth RT = 8 bytes/pixel at 720p = ~7 MB
  vs 148 MB for full deferred at 1080p. 20x reduction.
```

(Source: doc 03, Section 1 "Tier 0")

---

## My Rendering Plan

This chapter covers my phased build plan and WebGPU feature requirements. You will understand the path from forward Tier 0 to full deferred Tier 3.

### Build Order

```
Phase 1: Forward Renderer (Tier 0)
  - Single-pass forward shading, 1 light + ambient
  - Albedo textures only, depth buffer, no post-processing
  - Get blocks rendering and driveable

Phase 2: Deferred Upgrade (Tier 1)
  - 4-MRT G-buffer (albedo, specular, normal, mask)
  - Deferred ambient + 1 directional light
  - 2-cascade PSSM, FXAA, simple tone mapping, flat lightmap

Phase 3: Full Quality (Tier 2)
  - GPU frustum culling (compute), 4-cascade PSSM
  - SSAO, TAA with motion vectors, bloom, global fog
  - Deferred decals, GPU particles

Phase 4: Ultra (Tier 3, stretch goal)
  - Dual-pass AO, volumetric fog, SSR
  - Water reflections, DoF, motion blur, lens effects
```

### 4-Tier Quality System

| Tier | Rendering | GPU Class | Draw Calls | FPS Target |
|------|-----------|-----------|------------|------------|
| 0 | Forward | Intel UHD 620 | ~500 | 60 |
| 1 | Deferred 4 MRT | GTX 1060 / M1 | ~2000 | 60 |
| 2 | Deferred + Compute | RTX 2060 / M1 Pro | ~5000 (indirect) | 60 @ 1080p |
| 3 | Everything | RTX 3070 / M2 Pro | ~5000+ | 60 @ 1440p |

(Source: doc 03, Section 1)

### Top 10 Rendering Lessons

1. **Deferred rendering is not the whole frame.** The 19-pass pipeline is maybe 20% of GPU time.
2. **Three normal buffers serve different consumers.** But reconstructing face normals from depth saves a full RT.
3. **Specular/glossiness PBR is not dead.** It makes sense for metallic racing surfaces.
4. **Uber-shaders solve variant explosion.** 1,112 compiled shaders collapse to ~38 modules.
5. **GPU culling via compute is essential for dense scenes.** Indirect draw avoids CPU readback.
6. **HBAO+ runs twice (small + big scale).** Contact shadows and room-scale occlusion are perceptually different.
7. **Particle budgets are enforced in GPU milliseconds.** `ParticleMaxGpuLoadMs = 1.7ms`.
8. **Post-processing order matters.** Fog before DoF, AA after tone mapping, color grading last.
9. **Lightmaps are H-basis, not flat.** Directional baked data enables per-pixel lighting from static sources.
10. **Triple buffering + immediate present.** Minimizes input latency for competitive racing.

### Open Questions

1. Exact PSSM cascade split distances?
2. What is PreShade actually storing?
3. TAA jitter pattern -- Halton(2,3)? 8-sample rotated grid?
4. Exact filmic tone curve parameters?
5. Is normal encoding definitely octahedral?
6. What does `AlphaBlendSoap` render? (Best shader name ever.)
7. How does the `ShadowClipMap` system work?
8. `CPlugMaterialFxFur` -- is fur rendering used anywhere in TM2020?

---

## Related Pages

- [Rendering Deep Dive](../re/11-rendering-deep-dive.md)
- [Rendering & Graphics Pipeline](../re/05-rendering-graphics.md)
- [Ghidra Research Findings](../re/15-ghidra-research-findings.md)
- [Shader Catalog](../re/32-shader-catalog.md) (if exists)
- [WebGPU Renderer Design](../re/03-webgpu-renderer-design.md) (if exists)
- [Openplanet Intelligence](../re/19-openplanet-intelligence.md)
- [Real File Analysis](../re/26-real-file-analysis.md)

<details><summary>Document metadata</summary>

**Author**: Maya Chen, PhD Student (Real-Time Rendering)
**Date**: 2026-03-27
**Goal**: Understand exactly how TM2020 achieves its visual quality at 60+ FPS, and plan a WebGPU recreation.

**Sources studied**:
- doc 11: Rendering Deep Dive (1823 lines) -- primary reference
- doc 32: Shader Catalog (1410 lines, 1112 shaders)
- doc 15: Ghidra Research Findings (deferred pipeline, TXAA)
- doc 05: Rendering & Graphics Pipeline overview
- doc 19: Openplanet Intelligence (display config, rendering internals)
- doc 03: WebGPU Renderer Design (4-tier architecture)
- 5 decompiled C files in `decompiled/rendering/`

</details>

# Maya's Rendering Notes: Trackmania 2020 Deep Dive

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

---

## Chapter 1: The Deferred Pipeline

### What IS Deferred Rendering?

Okay, let me make sure I really understand this before writing it down.

In **forward rendering**, you draw each object and light it on the spot. If you have 100 objects and 50 lights, you either do 100x50 = 5000 shader invocations (multi-pass), or you cram all 50 lights into one uber-shader (single-pass forward). Either way, you pay for lights even when they don't touch a pixel.

In **deferred rendering**, you split the work:
1. **G-Buffer Fill**: Draw all geometry ONCE. Instead of computing lighting, just write material properties (albedo, normal, roughness) into multiple render targets.
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

**Why is this good for a racing game?** TM2020 tracks have LOTS of lights -- checkpoint gates, lamp posts, neon signs, dynamic car headlights. The track geometry is dense (blocks, scenery, trees). Deferred lets you decouple geometry complexity from lighting complexity. Whether you have 5 or 500 lights, the G-buffer fill costs the same.

The downside? Transparent objects (glass, particles, ghost cars) can't be deferred -- they need blending. TM2020 handles this with a hybrid: deferred for opaques, forward for transparents. That's standard.
(Source: doc 05, Section 2; doc 11, Section 4; doc 15, Section 7)

### The 19 Deferred Passes -- What Does Each One DO?

This is the verified pass ordering from doc 15, Section 7 and doc 11, Section 4. I'm going to walk through every single one.

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

### The Full Frame -- Beyond the 19 Deferred Passes

The 19 passes above are just the deferred core. A complete frame is much bigger:

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

(Source: doc 11, Section 1 -- the ASCII pipeline overview, which I verified against the full pass ordering in Section 4)

### Data Flow: What Goes Into the G-Buffer, What Comes Out

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
**Outputs**: 9 named render targets (see Chapter 2), consumed by lighting to produce HDR.
(Source: doc 11, Sections 3-4)

### "I Was Surprised That There Are THREE Normal Buffers -- Why?"

This threw me. Most engines I've studied (UE5, Unity HDRP) store ONE normal in the G-buffer. TM2020 stores THREE:

1. **PixelNormalInC** -- The bump-mapped per-pixel normal in camera space. This is the "real" normal used for lighting. Written during DeferredWrite from tangent-space normal maps.

2. **FaceNormalInC** -- The flat geometric face normal. Uses:
   - HBAO+ needs geometric normals for stable AO (bump maps would cause flickering)
   - FXAA/TXAA edge detection uses geometric discontinuities for silhouette finding
   - Shadow bias needs the true surface angle, not the bumped one
   - Can be reconstructed from depth via `DeferredFaceNormalFromDepth_p.hlsl`

3. **VertexNormalInC** -- Smooth vertex-interpolated normal. Uses:
   - Bilateral blur edge detection (smooth normals find surface boundaries without bump noise)
   - Subsurface scattering direction needs the smooth surface normal

**My thought**: For a WebGPU recreation, I'd probably reconstruct face normals from depth derivatives in-shader (like TM2020 already can with `DeferredFaceNormalFromDepth_p.hlsl`) instead of storing a separate buffer. That saves a full RT at 4 bytes/pixel. The vertex normal buffer is harder to skip if you want SSS, but maybe I can use the pixel normal with a blur pass?

**Question**: Is there a quality difference between "reconstructed from depth" vs "stored as a separate pass" for face normals? The depth derivative approach can have artifacts at silhouette edges...

(Source: doc 11, Section 3 "Why Three Normal Buffers?"; doc 15, Section 7)

---

## Chapter 2: G-Buffer Anatomy

### 9 Named Render Targets

Here's every render target I found, with what's stored in each channel:

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

**Important**: Not all 9 are bound simultaneously as MRT outputs. The core MRT during DeferredWrite is **4 targets + depth** (RT0-RT3 + depth). The additional targets (face normal, vertex normal, PreShade, DiffuseAmbient) are written in separate sub-passes.

### Format Choices (from doc 03)

The WebGPU renderer design document (doc 03) justifies every format choice against the RE evidence:

| Target | WebGPU Format | Memory/pixel | Justification |
|--------|---------------|-------------|---------------|
| Albedo (RT0) | `rgba8unorm-srgb` | 4 bytes | sRGB matches perceptual color; 8-bit is sufficient for albedo from 8-bit textures |
| Specular (RT1) | `rgba8unorm` | 4 bytes | F0 ranges 0.02-0.05 for dielectrics, maps to 8-bit [5-13]; roughness is perceptually non-linear so 256 levels works |
| Normal (RT2) | `rg16float` | 4 bytes | Octahedral encoding needs 2 channels; 16-bit float gives ~0.001 angular precision; Z is reconstructable |
| LightMask (RT3) | `rgba8unorm` | 4 bytes | Flag buffer, not color; 4 independent channels for LM tier, self-illum, shadow receive, LM receive |
| Depth | `depth24plus-stencil8` | 4 bytes | Verified from D3D11 log; stencil needed for deferred light volumes |
| HDR Accumulation | `rgba16float` | 8 bytes | Must exceed [0,1] for bright lights before tone mapping |

(Source: doc 03, Section 2)

### Memory Cost at Different Resolutions

From doc 03, Section 2 -- the G-buffer memory budget at Tier 2:

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

That 148 MB at 1080p is significant. On a phone browser, I'd need to cut this hard.

(Source: doc 03, Section 2 "G-Buffer Memory Budget")

### "PreShade" vs "DiffuseAmbient" vs "MDiffuse" -- What's the Difference?

This confused me at first. Let me draw it out:

```
TIMELINE OF A PIXEL'S COLOR:

1. MDiffuse        = raw albedo from texture. "M" means "Material."
                     This is the BASE COLOR. Written during G-buffer fill.
                     Input data, not lit.

2. PreShade        = [UNKNOWN] -- possibly pre-computed BRDF response,
                     emissive term, or simplified pre-lit diffuse for
                     static geometry. (Source: doc 11, Section 3 "What PreShade Means")

3. DiffuseAmbient  = MDiffuse * (ambient + lightmap + indirect lighting).
                     This is the LIGHTING RESULT -- accumulated diffuse irradiance.
                     Computed during DeferredRead/DeferredReadFull.
                     HDR output.

In equation form:
   MDiffuse         = texture_sample(albedo_map, uv)
   DiffuseAmbient   = MDiffuse * (Ambient + Lightmap + IndirectLight)
```

So: MDiffuse is an INPUT (material property), DiffuseAmbient is an OUTPUT (lighting result), and PreShade is somewhere in between (still unclear exactly what).

(Source: doc 11, Section 3 "DiffuseAmbient vs MDiffuse")

### How Does This Compare to Other Engines?

| Feature | TM2020 | UE5 | Unity HDRP |
|---------|--------|-----|------------|
| Normal count | 3 (pixel, face, vertex) | 1 (GBufferB) | 1 (NormalBuffer) |
| PBR workflow | Specular/Glossiness | Metallic/Roughness | Metallic/Roughness |
| Specular storage | RGB F0 + roughness | GBufferA.a = metallic | SpecularBuffer |
| G-buffer MRT count | 4 + depth (core) | 6 + depth | 4 + depth |
| Normal encoding | Octahedral 2-ch (likely) | Octahedral 2-ch | Octahedral 2-ch |
| Light mask | Dedicated RT3 | Uses stencil bits | Uses material flags in GBuffer |

TM2020's specular/glossiness workflow is less common in modern engines but has a real advantage: metals have colored F0 reflectance (copper is orange, gold is yellow), which spec/gloss stores directly in RGB. Metallic/roughness has to reconstruct this from the albedo when metallic=1. For a racing game with lots of metallic surfaces (car bodies, railings, chrome), spec/gloss is arguably a better fit.

**My question**: Should I use spec/gloss in my WebGPU engine for consistency with TM2020, or metallic/roughness for compatibility with the broader tooling ecosystem (Blender, Substance)?

(Source: doc 11, Section 10; doc 03, Section 2)

---

## Chapter 3: Shaders

### 1,112 Shaders Collapse to ~38 Uber-Shaders -- How?

The shader cache (`GpuCache_D3D11_SM5.zip`) contains 1,112 compiled DXBC shader stages. But when I analyzed the naming patterns, I found massive combinatorial explosion from a small number of core programs.

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

The block shader family ALONE accounts for 180 entries, all derived from ~6 core programs:

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

### The Tech3 Naming Convention -- Decode It!

Let me decode an actual shader name:

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

Full naming convention:
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

### Material Shader Variants -- How Does One Block Material Become 5+ Shaders?

Take the simplest block material, `Block_TDSN`:

```
Block_TDSN_p.hlsl                 -- Forward rendering (fallback)
Block_TDSN_v.hlsl                 -- Forward vertex shader
Block_TDSN_DefWrite_p.hlsl        -- G-buffer fill pixel shader
Block_TDSN_DefWrite_v.hlsl        -- G-buffer fill vertex shader
Block_DefReadP1_LM0_p.hlsl        -- Deferred read, lightmap tier 0
Block_DefReadP1_LM1_p.hlsl        -- Deferred read, lightmap tier 1
Block_DefReadP1_LM2_p.hlsl        -- Deferred read, lightmap tier 2
Block_DefReadP1_COut_p.hlsl       -- Deferred read, color output (stickers)
Block_DefReadP1_SI_p.hlsl         -- Deferred read, self-illumination
Block_TDSN_Anim_v.hlsl            -- Animated UV coordinates vertex
Block_TDSN_Shadow_v.hlsl          -- Shadow caster depth-only
Block_TDSN_ZOnly_p.hlsl           -- Z-prepass pixel
Block_TDSN_ZOnly_v.hlsl           -- Z-prepass vertex
Block_TDSN_PeelDiff_p.hlsl        -- Depth peeling for lightmap bake
Block_TDSN_PeelDiff_v.hlsl        -- Depth peeling vertex
```

That's 15+ shaders from ONE material! And this is the simplest case.

(Source: doc 32, Section 5 "Variant Explosion Analysis")

### What the CORE Deferred Write Shader Does (Conceptually)

The G-buffer fill shader does this, conceptually:

```
VERTEX STAGE:
  1. Transform vertex position: world -> clip space (with TAA jitter on projection)
  2. Transform TBN vectors (tangent, bitangent, normal) to CAMERA SPACE
     using: view_matrix * normal_matrix * tangent
  3. Pass through UV0 (material) and UV1 (lightmap)
  4. For triplanar projection modes, compute UVs from world position

FRAGMENT STAGE:
  1. Sample albedo texture (or triplanar blend for Py/Pxz modes)
  2. Apply vertex color tint and material diffuse tint
  3. Sample specular texture -> F0 (RGB) + roughness (A)
  4. Sample normal map -> transform from tangent space to camera space
  5. Encode camera-space normal to octahedral 2-channel format
  6. Build light mask flags (LM tier, self-illum, shadow receive)

  OUTPUT (4 MRT):
    RT0 = vec4(albedo.rgb, material_id / 255.0)
    RT1 = vec4(F0.rgb * spec_scale, roughness * rough_scale)
    RT2 = vec2(octahedral_normal.xy)
    RT3 = vec4(lm_tier_flag, self_illum_amount, shadow_flag, lm_receive_flag)
```

The WGSL implementation from doc 03 (Section 3) gives exact code for this, including octahedral encoding (Cigolle et al. 2014) and triplanar sampling for PyPxz projection modes.

(Source: doc 03, Section 3 "Core WGSL Shader Code"; doc 11, Section 1 Phase 3)

### "What's the Minimum Set of Shaders for a Playable Game?"

From doc 32, Section 3:

**Tier 1 -- Absolutely Required (renders a visible scene)**: 12 shaders
- G-buffer fill for blocks
- Depth-only pass
- Deferred ambient/indirect lighting
- Point light and spot light
- PSSM shadow sampling
- Fullscreen triangle utility
- Face normal reconstruction
- Linear depth conversion
- Tone mapping + auto-exposure
- Sky dome
- Motion vectors

**Tier 2 -- Visual Quality (needed for acceptable appearance)**: +12 = 24 total
- Car skin/details/glass
- Deferred decals
- Global fog
- Bloom
- FXAA
- Color grading
- SSAO
- GPU culling
- Trees
- Grass

**Tier 3 -- Full Feature Set**: +14 = 38 total
- SSR, TAA, particles, volumetric fog, fog boxes, water, clouds, DoF, motion blur, lens flares, ghost car, burn marks, impostors, PBR precompute

The massive 1,112 count collapses because most TM2020 shaders are permutations of the same logic with different texture slot configurations.

(Source: doc 32, Section 3)

---

## Chapter 4: Lighting & Shadows

### PBR Model: Specular/Glossiness (NOT Metallic/Roughness!)

This was surprising. Most modern engines use metallic/roughness. TM2020 uses **specular/glossiness**.

**Evidence**:
- `Engines/Pbr_Spec_to_Roughness_c.hlsl` -- converts specular to roughness (specular workflow INPUT)
- Separate `MDiffuse` and `MSpecular` G-buffer targets -- in spec/gloss, specular F0 is a full RGB color
- `Pbr_IntegrateBRDF_GGX_c.hlsl` -- GGX BRDF LUT (standard Cook-Torrance)

**Why spec/gloss?** For a racing game, I think this is a good call:
- Metal surfaces (car chrome, railings, checkpoint gates) have COLORED reflections. In spec/gloss, you store this directly: copper F0 = (0.95, 0.64, 0.54). In metallic/roughness, you'd need the albedo for metal color, which requires the shader to branch on metallic=1.
- The TM2020 content pipeline uses NadeoImporter which outputs spec/gloss textures natively.
- Legacy compatibility with the ManiaPlanet engine lineage.

**The tradeoff**: Most external tools (Substance Painter, Blender) use metallic/roughness by default. If I'm building my own game with community-created content, metallic/roughness has better tooling support.

```
SPECULAR/GLOSSINESS:
  MDiffuse  = RGB albedo (for dielectrics AND metals)
  MSpecular = RGB F0 reflectance + A glossiness

  Metal: F0 = metal_color (RGB), diffuse = black
  Dielectric: F0 = ~0.04 (grey), diffuse = albedo

METALLIC/ROUGHNESS:
  Albedo    = RGB base color (albedo for dielectrics, F0 for metals)
  MetalRough = R metallic (0/1), G roughness

  Metal: F0 = albedo, diffuse = black
  Dielectric: F0 = lerp(0.04, albedo, metallic), diffuse = albedo * (1-metallic)
```

(Source: doc 11, Section 10; doc 32, Section 2.2 "PBR / IBL Tooling")

### GGX BRDF -- What Is It? How Does It Create Realistic Reflections?

GGX (Trowbridge-Reitz) is the microfacet distribution function used in TM2020's specular BRDF. Here's what that means visually:

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

The actual specular BRDF is:
```
specular = (D * G * F) / (4 * NdotV * NdotL)
```

TM2020 pre-computes a **BRDF integration LUT** via `Pbr_IntegrateBRDF_GGX_c.hlsl` -- a 2D texture indexed by (NdotV, roughness) that stores the integral of the BRDF over all directions. This is the "split-sum" approximation for image-based lighting (IBL).

The doc 03 WGSL deferred lighting shader (Section 3) implements this exactly:
- `distribution_ggx()` for the D term
- `geometry_smith_ggx()` for the G term
- `fresnel_schlick()` for the F term
- `brdf_lut` texture for IBL split-sum

(Source: doc 11, Section 10; doc 03, Section 3; doc 32, Section 2.2 "Pbr_IntegrateBRDF_GGX_c")

### PSSM Shadow Cascades

PSSM = Parallel Split Shadow Maps. The idea: close objects need high-resolution shadows, distant objects can get away with lower resolution.

```
PSSM CASCADE LAYOUT (from camera):

Camera  Cascade 0   Cascade 1    Cascade 2      Cascade 3
  |     (near)      (mid-near)   (mid-far)      (far)
  |<--->|<--------->|<---------->|<------------>|
  |  highest res    medium res    lower res       lowest res
  |  MapShadowSplit0             MapShadowSplit2
  |          MapShadowSplit1              MapShadowSplit3
```

**Configuration from decompiled code** (`CVisionViewport::VisibleZonePrepareShadowAndProjectors` at `0x14095d430`):
- Default: **4 cascades** (when `*(int *)(param_1 + 0x680) < 2` or standard path)
- Simplified: **1 cascade** (when `flag & 0x40` at offset `0x5d0` -- "Minimum" shadow quality)
- Shadow map format: likely `DXGI_FORMAT_D16_UNORM` or `D24_UNORM` (standard practice)
- Resolution: configurable via `"ShadowMapTexelSize"` setting
- Filtering: PCF baseline + `"HqSoftShadows"` toggle for higher quality

**Shadow quality tiers**:
| Quality | Cascades | Behavior |
|---------|----------|----------|
| None | 0 | All shadow passes skipped |
| Minimum | 1 | `flag & 0x40` triggers single cascade |
| Medium | 4 | Default |
| High | 4 | Larger shadow maps |
| Very High | 4 | Maximum resolution + HqSoftShadows |

**Shadow cache**: Static geometry shadows are cached (`ShadowCacheUpdate` pass + `ShadowCache/UpdateShadowIndex_c.hlsl` compute shader) and only re-rendered when geometry changes.

**Fake shadows**: For distant objects, `ShaderGeomFakeShadows` / `ShaderShadowFakeQuad` / `FlatCubeShadow` project simple darkened shapes -- virtually free compared to real shadow maps.

(Source: doc 11, Section 5; decompiled `CVisionViewport_PrepareShadowAndProjectors_14095d430.c`)

### Lightmap Integration: Baked + Dynamic

TM2020 uses a sophisticated lightmap system:

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

**H-basis encoding** means the lightmap stores directional information, not just flat irradiance. This allows per-pixel directional lighting from the lightmap when combined with bump-mapped normals -- you get the visual richness of dynamic lighting from baked data.

**For dynamic objects** (cars): `LightFromMap` pass samples the baked lightmap AT the car's position to approximate environment lighting. Light probe grid (`ProbeGrid_Sample_c.hlsl`) provides SH-based indirect lighting.

(Source: doc 11, Section 10 "Lightmap Integration"; doc 32, Section 2.4)

### "How Would I Simplify This for a Browser?"

For my WebGPU racing game, I'd simplify shadows and lighting:
1. **Shadows**: Start with 2 cascades instead of 4 (doc 03 Tier 1 uses 2). PCF with 4 taps (matches TM2020's baseline). Skip shadow cache -- less important for smaller scenes.
2. **Lightmaps**: Standard flat irradiance instead of H-basis. Skip YCbCr compression -- just store RGB8.
3. **PBR**: Use the split-sum approximation but with a smaller BRDF LUT (128x128 instead of 256x256). One environment probe instead of a grid.
4. **Lights**: Cap at 16 point/spot lights. Use Forward+ tile culling only for the forward transparent pass.

---

## Chapter 5: Post-Processing

### The 14-Step Post-Processing Chain (In Order)

The order matters! Here's the verified sequence from doc 11, Section 4 Phase 9 + doc 32, Section 6:

```
POST-PROCESSING CHAIN (after deferred lighting)
================================================

 #   Stage              Key Shader(s)                        Essential?
 --  -----              -------------                        ----------
 1.  Fog Volumes        DeferredGeomFogBoxOutside_p/v        LUXURY
                        3DFog_RayMarching_c (volumetric)

 2.  Global Fog         DeferredFogGlobal_p                  ESSENTIAL
                        DeferredFog_p                        (without fog,
                                                              distance = ugly)

 3.  Lens Flares        LensFlareOccQuery_v                  LUXURY
                        2dFlareAdd_Hdr_p (HDR composite)
                        2dLensDirtAdd_p (lens dirt)

 4.  Depth of Field     DoF_T3_BlurAtDepth_p                 LUXURY
                                                              (only in replays)

 5.  Motion Blur        MotionBlur2d_p                       LUXURY
                        (default intensity: 0.35)             (player pref)

 6.  General Blur       BlurHV_p (separable Gaussian)        INTERNAL
                        BilateralBlur_p                       (used by other FX)

 7.  Colors             Colors_p (brightness/contrast/sat)   ESSENTIAL

 8.  Color Grading      ColorGrading_p (3D LUT lookup)       NICE-TO-HAVE
                        ColorBlindnessCorrection_p            (accessibility!)

 9.  Tone Mapping       TM_GetLumi_p -> ...chain...          ESSENTIAL
                        TM_GlobalFilmCurve_p                  (HDR -> LDR)

10.  Bloom              BloomSelectFilterDown2_p -> chain     ESSENTIAL
                        Bloom_HorizonBlur_p -> chain           (defines the "look")
                        Bloom_StreaksWorkDir_p (anamorphic)
                        Bloom_Final_p

11.  Anti-Aliasing      FXAA_p  OR  TemporalAA_p            ESSENTIAL
                        (NVIDIA GFSDK TXAA as hardware path)   (aliasing = ugly)

12.  SSR                SSReflect_Deferred_p                 NICE-TO-HAVE
                        SSReflect_Deferred_LastFrames_p
                        SSReflect_UpSample_p

13.  SSS                SeparableSSS_p (Jimenez technique)   LUXURY
                        (car paint, translucent materials)

14.  Final Blit         RasterBitmapBlend*_p -> back buffer  ESSENTIAL
                        DownSSAA if supersampling
```

(Source: doc 32, Section 6; doc 11, Section 4 Phases 9-13; doc 11, Section 9)

### TXAA -- How Does Temporal AA Work?

TM2020 has TWO implementations:

1. **NVIDIA GFSDK TXAA** -- hardware vendor SDK, uses `GFSDK_TXAA_DX11_ResolveFromMotionVectors` (at `0x141c0f178`). Optimized for NVIDIA GPUs.
2. **Ubisoft Custom TXAA** (`UBI_TXAA`) -- software fallback via `TemporalAA_p.hlsl`. Cross-vendor.

The principle:
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

Each frame, the projection matrix gets a tiny sub-pixel offset (`PosOffsetAA` / `PosOffsetAAInW`). Over multiple frames, different sub-pixel locations are sampled. The TAA shader blends the current frame with the reprojected previous frame (typically 90-95% history, 5-10% current).

**Ghost rejection**: When an object moves or gets disoccluded, the history is wrong. Standard approaches:
- Neighborhood clamping: clamp history to the min/max of the current frame's 3x3 neighborhood
- Motion rejection: discard history in high-velocity regions

The `CameraMotion` pass generates motion vectors via `DeferredCameraMotion_p.hlsl` -- per-pixel reprojection using the previous frame's view-projection matrix.

(Source: doc 15, Section 8; doc 11, Section 11)

### Bloom

The bloom pipeline from doc 32/doc 11:

```
HDR Scene Buffer
      |
      v
BloomSelectFilterDown2_p    -- Threshold: keep only pixels above brightness cutoff
      |                        + 2x downsample
      v
BloomSelectFilterDown4_p    -- Additional 4x downsample
      |
      v
Bloom_HorizonBlur_p         -- Horizontal Gaussian blur at each mip level
      |                        (done at multiple resolution levels)
      v
Bloom_StreaksWorkDir_p       -- Directional streaks (anamorphic lens effect!)
      |
      v
Bloom_StreaksSelectSrc_p     -- Select streak intensity
      |
      v
Bloom_Final_p               -- Composite bloom back onto HDR buffer
      |
      v
Tonemapped + bloomed scene
```

Configuration: `"BloomIntensUseCurve"`, `"MinIntensInBloomSrc"` (threshold), `"Bloom_Down%d"` (multi-level targets).

(Source: doc 11, Section 9 "Bloom HDR"; doc 32, Section 6)

### Tone Mapping

TM2020's tone mapper uses a **filmic curve with power segments** (similar to Hable/Uncharted 2 but parameterized differently):

```
TM_GetLumi_p            -- Extract luminance from HDR
TM_GetLog2LumiDown1_p   -- Progressive log2 luminance downsample
TM_GetAvgLumiCurr_p     -- Average luminance (auto-exposure target)
TM_GlobalFilmCurve_p    -- Apply filmic curve (piecewise power: shoulder+linear+toe)
```

The filmic curve uses `NFilmicTone_PowerSegments::SCurveParamsUser` -- a piecewise function model.

(Source: doc 11, Section 9 "Tone Mapping")

### HBAO+ Ambient Occlusion

The full HBAO+ pipeline is a 6-step beast:

```
Step 1: LinearizeDepth_p.hlsl        -- Hardware depth -> linear eye-space Z
Step 2: DeinterleaveDepth_p.hlsl     -- Split into 4x4 interleaved layers (16 quarter-res)
Step 3: ReconstructNormal_p.hlsl     -- Reconstruct normals from depth derivatives
Step 4: CoarseAO_p.hlsl             -- Main AO computation at quarter resolution
Step 5: ReinterleaveAO_p.hlsl       -- Recombine 4x4 layers back to full resolution
Step 6: BlurX_p.hlsl + BlurY_p.hlsl -- Separable bilateral blur (edge-preserving)
```

And here's the kicker: **it runs TWICE**. The decompiled HBAO config at `0x14091f4e0` shows two parameter sets:
- `NvHBAO.*` -- Small-scale pass (contact shadows, fine detail)
- `NvHBAO_BigScale.*` -- Big-scale pass (room-scale ambient occlusion)

The results are combined (multiplied) for the final AO term. Each pass has its own radius, bias, and power exponent settings.

There's also a fallback: `UseHomeMadeHBAO` (at offset 0x04) switches to Nadeo's custom AO when NVIDIA HBAO+ isn't available.

(Source: doc 11, Section 6; decompiled `NSysCfgVision_SSSAmbOcc_HBAO_14091f4e0.c`)

### Screen-Space Reflections

```
SSReflect_Deferred_p.hlsl            -- Ray march in screen space using depth
SSReflect_Deferred_LastFrames_p.hlsl  -- Fill gaps with temporal reprojection
SSReflect_Forward_p.hlsl              -- Forward path variant
SSReflect_UpSample_p.hlsl            -- Half-res SSR upsampled to full res

Pipeline: SSLReflects -> SSLReflects_GlobalCube -> SSLReflects_Add
                                        ^
                                        |
                              Fallback for ray-march misses
```

SSR traces rays in screen space and falls back to a global cubemap when the ray leaves the screen.

(Source: doc 11, Section 4 Phase 6; doc 32, Section 8.5)

### "Which Post-Effects Are Essential and Which Are Luxury?"

My ranking for a browser racing game:

**ESSENTIAL** (the game looks wrong without them):
- Tone mapping (HDR -> LDR, auto-exposure)
- Global fog (hides draw distance, adds atmosphere)
- Bloom (defines the bright, clean racing game aesthetic)
- Anti-aliasing (FXAA minimum, TAA ideal)
- Basic color adjustment

**NICE-TO-HAVE** (noticeable quality upgrade):
- SSAO (adds depth perception and grounding)
- SSR (wet road reflections are iconic)
- Color grading (mood/atmosphere)
- Lens dirt (subtle but atmospheric)

**LUXURY** (cut first for performance):
- Volumetric fog (expensive compute, most maps don't need it)
- Depth of field (only visible in replays)
- Motion blur (player preference, many disable it)
- Subsurface scattering (barely visible at racing speed)
- Lens flares
- Anamorphic bloom streaks

---

## Chapter 6: Performance

### 16.67ms Frame Budget -- How Is It Split?

At 60 FPS, each frame must complete in 16.67ms. Based on the pipeline structure:

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

The particle system has a HARD budget: `ParticleMaxGpuLoadMs` at offset `0xB4` in `CSystemConfigDisplay`, default 1.7ms. The system dynamically reduces particle count to stay within budget.

(Source: doc 11, Section 12 "GPU Load Management"; decompiled `CSystemConfigDisplay_140936810.c`)

### GPU Frustum Culling via Compute Shaders

The `DipCulling` pass runs a compute shader for GPU-side frustum culling + LOD selection:

```
Engines/Instances_Cull_SetLOD_c.hlsl     -- Frustum test + LOD level per instance
Engines/Instances_Merge_c.hlsl           -- Merge surviving instance lists
Engines/IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl -- Write DrawIndexedInstancedIndirect args
```

This is a fully indirect rendering pipeline. The compute shader writes draw arguments directly -- NO CPU readback needed. The GPU decides what to draw and at what LOD. This is critical for scenes with thousands of block instances.

There's also **Forward+ tile culling**: `Engines/ForwardTileCull_c.hlsl` divides the screen into tiles and assigns lights per tile for the forward transparent pass.

(Source: doc 11, Section 14; doc 32, Section 2.2 "Culling and Instancing")

### LOD System with Impostor Fallback

```
LOD PIPELINE:

Close      Medium      Far          Very Far
[Full Mesh] -> [LOD 1] -> [LOD 2] -> [Impostor Billboard]
                                           |
                                           v
                               DeferredOutput_ImpostorConvert_c.hlsl
                               (compute: render 3D -> 2D billboard texture)
```

- `GeomLodScaleZ` (offset `0xEC` in `CSystemConfigDisplay`) controls LOD transition distances. Default = 1.0. Higher = more aggressive (objects simplify closer). Lower = objects stay detailed longer.
- Tree impostors use `SCBufferDrawV_TreeImpostor` for billboard orientation.
- Impostor conversion is done by a compute shader that captures the 3D object's appearance from the current viewpoint.

(Source: doc 11, Section 14; doc 19, Section 8; decompiled `CSystemConfigDisplay_140936810.c`)

### 32m Block Grid for Spatial Organization

The world is divided into a grid of **32-meter blocks**. Evidence: `Math::Ceil(distance / 32.0f)` from the Openplanet `Finetuner` plugin.

Culling operates at this granularity:
- `m_ZClipNbBlock` (offset `0xE4`) controls how many blocks are visible
- `m_ZClip` (offset `0xDC`) and `m_ZClipAuto` (offset `0xE0`) control the far clip distance
- TMF had a 50,000m far clip; TM2020 is likely similar

(Source: doc 19, Section 8; doc 11, Section 14)

### Texture Compression (BCn/DDS)

TM2020 uses standard BC (Block Compression) texture formats:
- `BC1` (DXT1) -- RGB, 4:1 compression, for simple textures
- `BC3` (DXT5) -- RGBA, 4:1 compression, for textures with alpha
- `BC7` -- RGBA, 4:1 compression, highest quality
- Encoding shaders: `Encode_BC4_p/v`, `Encode_BC5_p/v`

WebGPU supports BCn via `texture-compression-bc` feature (optional but widely available on desktop).

(Source: doc 11, Section 15; doc 32, Section 2.2)

### "Can This Run on a Phone Browser? What Would I Cut?"

Honestly? The full pipeline -- absolutely not. Here's what I'd cut for a mobile browser:

```
MOBILE BROWSER BUDGET (targeting 30 FPS on mid-range phone):
============================================================
KEEP:
  - Forward rendering (NO deferred -- mobile GPUs hate MRT bandwidth)
  - 1 directional light (sun) + hemisphere ambient
  - 1 shadow cascade (512x512 resolution)
  - FXAA (cheap)
  - Simple fog (analytical height formula, not ray-marched)
  - Albedo textures only (skip specular/normal maps)
  - Resolution: 720p or lower with render scaling

CUT:
  - Entire deferred pipeline (switch to forward)
  - All 3 extra normal buffers
  - HBAO+ (replace with baked AO in vertex color)
  - SSR
  - Bloom (or very simplified 2-level bloom)
  - TAA (use FXAA only)
  - Volumetric fog
  - Particles (minimal billboard particles only)
  - GPU culling compute shaders (do CPU-side frustum cull)
  - Shadow cache
  - Lightmaps (bake into vertex color)

TARGET G-BUFFER: NONE (forward renderer)
  - 1 color RT (rgba8unorm) = 4 bytes/pixel
  - 1 depth RT (depth24plus) = 4 bytes/pixel
  = 8 bytes/pixel at 720p = ~7 MB total RT memory
  vs 148 MB for the full deferred pipeline at 1080p

That's a 20x reduction in render target memory alone.
```

Doc 03 calls this "Tier 0: Absolute Minimum" -- forward rendering with 1 light, no compute, no MRT. Expected to run at 60 FPS on Intel UHD 620 class. Draw call budget: ~500.

(Source: doc 03, Section 1 "Tier 0"; doc 11, Section 15 "Safe Mode Configuration")

---

## Chapter 7: My Rendering Plan

### What I'd Build First

```
BUILD ORDER:
============

Phase 1: Forward Renderer (Tier 0)
  - Single-pass forward shading
  - 1 directional light + ambient
  - Albedo textures only
  - Depth buffer
  - No post-processing
  - Get blocks rendering and driveable

Phase 2: Deferred Upgrade (Tier 1)
  - 4-MRT G-buffer (albedo, specular, normal, mask)
  - Deferred ambient + 1 directional light
  - 2-cascade PSSM shadows
  - FXAA
  - Simple tone mapping
  - Lightmap sampling (flat, not H-basis)

Phase 3: Full Quality (Tier 2)
  - GPU frustum culling (compute)
  - 4-cascade PSSM
  - SSAO (simplified: SAO not HBAO+)
  - TAA with motion vectors
  - Bloom (4-level chain)
  - Global fog
  - Deferred decals
  - GPU particles

Phase 4: Ultra (Tier 3, stretch goal)
  - Dual-pass AO
  - Volumetric fog
  - SSR
  - Water reflections + refraction
  - DoF, motion blur, lens effects
```

### WebGPU Feature Requirements

From doc 03, Section 10:

```javascript
// Tier 1 (basic deferred):
const requiredFeatures = [
    'float32-filterable',           // Shadow map comparison sampling
];
const requiredLimits = {
    maxColorAttachments: 4,         // G-buffer MRT
    maxBindGroups: 4,               // Frame/Pass/Shader/Draw
};

// Tier 2 (compute-enhanced):
requiredFeatures.push(
    'rg11b10ufloat-renderable',    // Compact HDR render targets
);
requiredLimits.maxStorageBufferBindingSize = 134217728;  // 128MB for particles
requiredLimits.maxTextureDimension2D = 8192;             // Shadow maps

// Tier 3 (ultra):
requiredFeatures.push(
    'texture-compression-bc',       // BCn/DDS texture support (optional)
);
requiredLimits.maxTextureDimension3D = 256;              // Volumetric fog grid
```

**Browser compatibility concern**: `float32-filterable` is needed even for basic deferred (shadow map comparison sampling). Without it, I'd need to do manual PCF in the shader instead of hardware shadow comparison. That's doable but slower.

(Source: doc 03, Section 10)

### 4-Tier Quality System

| Tier | Name | Rendering | GPU Class | Draw Calls | FPS Target |
|------|------|-----------|-----------|------------|------------|
| 0 | Minimum | Forward | Intel UHD 620 | ~500 | 60 |
| 1 | Basic Deferred | Deferred 4 MRT | GTX 1060 / M1 | ~2000 | 60 |
| 2 | Full Quality | Deferred + Compute | RTX 2060 / M1 Pro | ~5000 (indirect) | 60 @ 1080p |
| 3 | Ultra | Everything | RTX 3070 / M2 Pro | ~5000+ | 60 @ 1440p |

(Source: doc 03, Section 1)

### My Top 10 Rendering Lessons from Studying TM2020

1. **Deferred rendering is not the whole frame.** The 19-pass deferred pipeline is just one part. Shadow prep, scene prep, forward transparency, particles, and post-processing each take significant time. The G-buffer fill is maybe 20% of GPU time.

2. **Three normal buffers serve different consumers.** Pixel normals for lighting, face normals for AO and edge detection, vertex normals for blur and SSS. Each consumer needs different normal quality. But for a smaller project, reconstructing face normals from depth saves a full RT.

3. **Specular/glossiness PBR is not dead.** TM2020 uses it and it makes sense for metallic racing game surfaces. Don't assume metallic/roughness is always the right choice.

4. **Uber-shaders are the answer to variant explosion.** 1,112 compiled shaders collapse to ~38 uber-shader modules. WebGPU's `override` constants can replicate this at pipeline compile time without runtime branching.

5. **GPU culling via compute is essential for dense scenes.** The `DipCulling` pass uses indirect draw to avoid CPU readback. This is how you handle thousands of block instances without the CPU becoming a bottleneck.

6. **HBAO+ runs twice (small + big scale) and it matters.** Contact shadows (small radius) and room-scale occlusion (big radius) are perceptually different. The dual-pass approach gives both without compromising either.

7. **Particle budgets are enforced in GPU milliseconds.** `ParticleMaxGpuLoadMs = 1.7ms` -- the system dynamically reduces particle count. This is how you prevent particles from tanking your frame rate. I need to implement this.

8. **The post-processing order matters.** Fog before DoF (fog is part of the scene). Tone mapping before bloom (or after? -- doc 11 notes this needs investigation). AA after tone mapping. Color grading last. Getting this wrong creates subtle but visible artifacts.

9. **Lightmaps are H-basis, not flat.** This means directional information is baked, enabling per-pixel lighting from static light sources. Just storing flat irradiance loses significant visual quality for bumpy surfaces.

10. **Triple buffering + immediate present (no VSync).** The swap chain uses 3 back buffers with `VK_PRESENT_MODE_IMMEDIATE_KHR`. This means tearing is possible but input latency is minimized -- critical for a competitive racing game.

### Open Questions I Still Have

1. What are the exact PSSM cascade split distances? Logarithmic? Practical split scheme?
2. What is the `PreShade` buffer actually storing?
3. What TAA jitter pattern does TM2020 use -- Halton(2,3)? 8-sample rotated grid?
4. What are the exact filmic tone curve parameters (`NFilmicTone_PowerSegments`)?
5. Is the normal encoding definitely octahedral, or could it be spheremap transform?
6. What exactly does `AlphaBlendSoap` render? (Best shader name ever.)
7. How does the `ShadowClipMap` system work for large-scale terrain shadows?
8. The engine has `CPlugMaterialFxFur` -- is fur rendering actually used anywhere in TM2020?

(Sources for open questions: doc 11, Section "Unknowns and Future Investigation")

---

*These notes are based on reverse-engineered evidence from the TM2020 binary. All confidence levels (VERIFIED, PLAUSIBLE, SPECULATIVE) are inherited from the source documents. Code citations reference decompiled files in `decompiled/rendering/` and specific addresses in `Trackmania.exe`.*

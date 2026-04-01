# Trackmania 2020 Shader Catalog

Trackmania 2020 ships 1,112 compiled HLSL shaders in a 16 MB `GpuCache_D3D11_SM5.zip` archive. This catalog inventories every shader by category, maps each to its pipeline role, and identifies the subset you need for a WebGPU recreation. The massive count collapses to roughly 35-40 uber-shader modules because most files are permutations of the same logic with different texture slot configurations.

**Start here if you are building an MVP**: Jump to [Which shaders you need for an MVP](#which-shaders-you-need-for-an-mvp) for a prioritized list of 12 essential, 12 quality, and 14 full-feature shaders.

---

## How the shader cache is structured

Each entry in the zip is compiled D3D11 SM5 bytecode wrapped in a GameBox (`.GpuCache.Gbx`) container. These are NOT source code -- they are pre-compiled DXBC blobs. The `.Gbx` wrapper adds Nadeo-specific metadata (permutation keys, constant buffer layout hints).

Two naming conventions exist:

1. **Direct HLSL**: `Category/ShaderName_stage.hlsl.GpuCache.Gbx` -- the majority.
2. **Text-referenced**: `Category/Media/Text/PHLSL/ShaderName.PHlsl.Txt.GpuCache.Gbx` -- material templates using text resource indirection.

### Shader stage suffixes

| Suffix | D3D11 Stage | Count | WebGPU Equivalent |
|--------|------------|-------|-------------------|
| `_p.hlsl` | Pixel (Fragment) Shader | 515 | `@fragment` |
| `_v.hlsl` | Vertex Shader | 388 | `@vertex` |
| `_c.hlsl` | Compute Shader | 105 | `@compute` |
| `.PHlsl` | Pixel (via text reference) | 51 | `@fragment` |
| `.VHlsl` | Vertex (via text reference) | 40 | `@vertex` |
| `_g.hlsl` | Geometry Shader | 5 | Emulate via vertex + storage buffers |
| `_d.hlsl` | Domain (Tessellation Eval) | 4 | Not available in WebGPU |
| `_h.hlsl` | Hull (Tessellation Control) | 4 | Not available in WebGPU |

**Total**: 1,112 shader stages + 1 `SourceVersionInfo.txt` = 1,113 entries.

### WebGPU stage mapping notes

**Geometry shaders** (5 total) handle particle voxelization, energy FX, cubemap batching, and HBAO+ CoarseAO. Replace with vertex shader expansions or compute pre-passes.

**Tessellation shaders** (8 total: 4 hull + 4 domain) appear only for ocean (`Ocean_h/d.hlsl`, `Ocean_tri_h/d.hlsl`, `Ocean_trigeom_h/d.hlsl`) and one terrain shader (`Block_TAddLighted_Domain_h/d.hlsl`). Replace with pre-tessellated meshes or compute-based displacement.

### Top-level category counts

| Category | Count | Purpose |
|----------|-------|---------|
| `Tech3/` | 533 | Material shaders, deferred pipeline, scene objects |
| `Engines/` | 218 | Engine utilities, PBR tooling, culling, blitting |
| `Effects/` | 154 | Post-processing, particles, fog, lens effects |
| `Lightmap/` | 78 | Baked lighting, probe grids, irradiance |
| `Painter/` | 16 | Car skin painting / sticker system |
| `Menu/` | 16 | UI background, HUD, minimap |
| `Techno3/` | 12 | Material template text references |
| `ShootMania/` | 12 | ShootMania-specific (shared engine; not used in TM) |
| `Garage/` | 10 | Car garage/showroom rendering |
| `Clouds/` | 9 | Cloud rendering and god rays |
| `Bench/` | 7 | GPU benchmarking |
| `Editor/` | 4 | Editor debug visualization |
| `Test/` | 4 | PBR test and noise test shaders |
| `Sky/` | 2 | Sky dome rendering |
| `ShadowCache/` | 1 | Shadow cache index update (compute) |
| `Noise/` | 1 | 3D noise volume generation (compute) |
| Root-level | 26 | Misc material templates (TEmblem, PC3, switches) |

---

## Which shaders you need for an MVP

The 1,112 shaders collapse to approximately 38 WebGPU shader programs. Here they are ranked by priority.

### Tier 1: Absolutely required (renders a visible scene)

These 12 shaders produce a lit, shadowed scene with track geometry, sky, and basic tone mapping.

| # | WebGPU Shader | TM2020 Originals | Purpose |
|---|---------------|-------------------|---------|
| 1 | `gbuffer_fill.wgsl` | `Block_TDSN_DefWrite_p/v`, `Block_PyPxz_*_DefWrite_p/v`, all block DefWrite variants | G-buffer write for track geometry |
| 2 | `depth_only.wgsl` | `ZOnly_p/v`, `ZOnly_Alpha01_p/v` | Z-prepass |
| 3 | `deferred_ambient.wgsl` | `Deferred_SetILightDir_p`, `Deferred_AddAmbient_Fresnel_p`, `Deferred_AddLightLm_p`, `Deferred_SetLDirFromMask_p` | Ambient/indirect lighting |
| 4 | `deferred_light_point.wgsl` | `DeferredGeomLightBall_p` | Point light accumulation |
| 5 | `deferred_light_spot.wgsl` | `DeferredGeomLightSpot_p` | Spot light accumulation |
| 6 | `deferred_shadow_pssm.wgsl` | `DeferredShadowPssm_p/v` | PSSM shadow sampling |
| 7 | `fullscreen_tri.wgsl` | `FullTriangle_v`, `FullTriangle_TexCoord_v` | Full-screen passes |
| 8 | `face_normal.wgsl` | `DeferredFaceNormalFromDepth_p` | Face normal reconstruction |
| 9 | `linear_depth.wgsl` | `DeferredZBufferToDist01_p`, `DepthGetLinearZ01_p` | Linear depth conversion |
| 10 | `tone_map.wgsl` | `TM_GlobalFilmCurve_p`, `TM_GetAvgLumiCurr_p`, `TM_GetLog2LumiDown1_p` | Tone mapping + auto-exposure |
| 11 | `sky.wgsl` | `Sky_p/v` | Sky rendering |
| 12 | `motion_vectors.wgsl` | `DeferredCameraMotion_p/v` | Motion vector generation |

### Tier 2: Visual quality (needed for acceptable appearance)

| # | WebGPU Shader | TM2020 Originals | Purpose |
|---|---------------|-------------------|---------|
| 13 | `car_skin.wgsl` | `CarSkin_DefWrite_p/v`, `CarSkin_DefRead_p/v` | Car body rendering |
| 14 | `car_details.wgsl` | `CarDetails_DefWrite_p/v`, `CarDetails_DefRead_p/v` | Car parts |
| 15 | `car_glass.wgsl` | `CarGlass_p1_p/v`, `CarGlass_p2_p/v`, `CarGlassRefract_p/v` | Car windshield |
| 16 | `decal_deferred.wgsl` | `DeferredDecalGeom_p/v`, `DeferredDecal_Boxs_p` | Deferred decals |
| 17 | `fog_global.wgsl` | `DeferredFogGlobal_p`, `DeferredFog_p` | Global fog |
| 18 | `bloom.wgsl` | `BloomSelectFilterDown*_p`, `Bloom_HorizonBlur_p`, `Bloom_Final_p` | HDR bloom |
| 19 | `fxaa.wgsl` | `FXAA_p` | Anti-aliasing |
| 20 | `color_grading.wgsl` | `ColorGrading_p`, `Colors_p` | Color grading |
| 21 | `ao_ssao.wgsl` | HBAO+ pipeline (9 shaders) | Ambient occlusion |
| 22 | `gpu_cull.wgsl` | `Instances_Cull_SetLOD_c`, `Instances_Merge_c` | GPU frustum culling |
| 23 | `tree.wgsl` | `Tree_SelfAO_DefWrite_p/v`, `Tree_SelfAO_DefRead_p/v` | Tree rendering |
| 24 | `grass.wgsl` | `Grass_p/v`, `Chunk_AddInstances_c` | Grass rendering |

### Tier 3: Full feature set

| # | WebGPU Shader | TM2020 Originals | Purpose |
|---|---------------|-------------------|---------|
| 25 | `ssr.wgsl` | `SSReflect_Deferred_p`, `SSReflect_Deferred_LastFrames_p` | Screen-space reflections |
| 26 | `temporal_aa.wgsl` | `TemporalAA_p` | Temporal anti-aliasing |
| 27 | `particles.wgsl` | `MgrParticleUpdate_c`, `MgrParticleRender_p/v` | GPU particles |
| 28 | `fog_volumetric.wgsl` | `3DFog_RayMarching_c`, `3DFog_ComputeInScatteringAndDensity_c` | Volumetric fog |
| 29 | `fog_box.wgsl` | `DeferredGeomFogBoxInside_p/v`, `DeferredGeomFogBoxOutside_p/v` | Fog box volumes |
| 30 | `water.wgsl` | `Sea_p/v`, `Sea_DefWrite_p/v`, `WaterFog*` | Water surface |
| 31 | `clouds.wgsl` | `CloudsT3b_p/v`, `CloudsGodLight_p` | Clouds and god rays |
| 32 | `dof.wgsl` | `DoF_T3_BlurAtDepth_p` | Depth of field |
| 33 | `motion_blur.wgsl` | `MotionBlur2d_p` | Motion blur |
| 34 | `lens_flare.wgsl` | `2dFlareAdd_Hdr_p`, `2dLensDirtAdd_p`, `LensFlareOccQuery_v` | Lens effects |
| 35 | `ghost_car.wgsl` | `CarGhost_p/v` | Ghost car overlay |
| 36 | `burn_marks.wgsl` | `DeferredGeomBurnSphere_p/v` | Tire scorch marks |
| 37 | `impostor.wgsl` | `Tree_Impostor_DefWrite_p/v`, `DeferredOutput_ImpostorConvert_c` | Billboard impostors |
| 38 | `pbr_precompute.wgsl` | `Pbr_IntegrateBRDF_GGX_c`, `Pbr_PreFilterEnvMap_GGX_c` | Pre-compute PBR LUTs |

**Summary**: 12 shaders for a minimal scene, 24 for acceptable quality, 38 for feature-complete.

---

## Deferred pipeline shader map

Each of the 19 deferred pipeline passes and its associated shaders, with WebGPU implementation notes:

```
PASS                    SHADER(S)                                    WebGPU PLAN
=======================================================================================
 1. DipCulling          Instances_Cull_SetLOD_c.hlsl                 Compute pass
                        IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl      Writes indirect args
---------------------------------------------------------------------------------------
 2. DeferredWrite       Block_TDSN_DefWrite_p/v.hlsl                 Uber G-buffer shader
                        Block_PyPxz_*_DefWrite_p/v.hlsl              (variants via defines)
                        CarSkin_DefWrite_p/v.hlsl
                        Tree_SelfAO_DefWrite_p/v.hlsl
                        BodyAnim_DefWrite_p/v.hlsl
                        CharAnimSkel_*_DefWrite_p/v.hlsl
                        Dyna*_DefWrite_*.hlsl
                        DynaFacing_DefWrite_p/v.hlsl
                        DynaSpriteDiffuse_DefWrite_p/v.hlsl
                        Sea_DefWrite_p/v.hlsl
                        DecalSprite_DefWrite_p/v.hlsl
                        Block_TreeSprite_DefWrite_p/v.hlsl
                        MenuBox_DefWrite_v.hlsl
                        IceWall_DefWrite_p/v.hlsl
                        Voxel_DefWrite_TDSN_p/v.hlsl
                        VoxelIce_DefWrite_p/v.hlsl
                        GrassFence_VDepLight_DefWrite_p/v.hlsl
                        DeferredWrite_BlackNoSpec_p/v.hlsl
                        Warp_*_DefWrite_*.hlsl
                        Block_PyPxzTLayered_DefWrite_p/v.hlsl
---------------------------------------------------------------------------------------
 3. DeferredWriteFNormal DeferredFaceNormalFromDepth_p.hlsl           Reconstruct from depth
                        DeferredDeCompFaceNormal_p.hlsl              Or decompress stored
---------------------------------------------------------------------------------------
 4. DeferredWriteVNormal (Vertex normals written during DeferredWrite MRT -- no separate shader)
---------------------------------------------------------------------------------------
 5. DeferredDecals      DeferredDecalGeom_p/v.hlsl                   Box projection
                        DeferredDecal_Boxs_p.hlsl                   Batched box decals
                        DeferredDecal_FullTri_p/v.hlsl              Full-screen decal
                        Decal_2d_CV_DefDecal_p/v.hlsl               2D vertex-color decal
---------------------------------------------------------------------------------------
 6. DeferredBurn        DeferredGeomBurnSphere_p/v.hlsl             Sphere-shaped burns
---------------------------------------------------------------------------------------
 7. DeferredShadow      DeferredShadowPssm_p/v.hlsl                 Sample PSSM cascades
                        DeferredGeomShadowVol_p/v.hlsl              Shadow volume stencil
---------------------------------------------------------------------------------------
 8. DeferredAmbientOcc  HBAO_plus/LinearizeDepth_p.hlsl              6-step HBAO+ pipeline
                        HBAO_plus/DeinterleaveDepth_p.hlsl           (run twice: small+big)
                        HBAO_plus/ReconstructNormal_p.hlsl
                        HBAO_plus/CoarseAO_p.hlsl
                        HBAO_plus/ReinterleaveAO_p.hlsl
                        HBAO_plus/BlurX_p.hlsl
                        HBAO_plus/BlurY_p.hlsl
---------------------------------------------------------------------------------------
 9. DeferredFakeOcc     DeferredGeomFakeOcc_p/v.hlsl                Cheap distant AO
---------------------------------------------------------------------------------------
10. CameraMotion        DeferredCameraMotion_p/v.hlsl               Motion vectors
---------------------------------------------------------------------------------------
11. DeferredRead        Deferred_SetILightDir_p.hlsl                Indirect light setup
                        Deferred_AddAmbient_Fresnel_p.hlsl          Ambient + Fresnel
                        Deferred_AddLightLm_p.hlsl                  Lightmap contribution
                        Deferred_SetLDirFromMask_p.hlsl             Light dir from mask
                        Block_DefReadP1_*.hlsl (23 variants)        Per-material read
                        CarSkin_DefRead_p/v.hlsl
                        CarDetails_DefRead_p/v.hlsl
                        Tree_SelfAO_DefRead_p/v.hlsl
                        Tree_Impostor_DefRead_p/v.hlsl
                        BodyAnim_DefRead_p/v.hlsl
                        CharAnimSkel_*_DefRead_p/v.hlsl
                        GrassFence_VDepLight_DefRead_p/v.hlsl
                        DynaSpriteDiffuse_DefRead_p/v.hlsl
                        DecalSprite_DefRead_p/v.hlsl
                        Block_PyPxzTLayered_DefRead_p/v.hlsl
                        Warp_TDiffSpec_VertexTween_DefRead_p/v.hlsl
                        Voxel_DefRead_TDSNI_COut_p.hlsl
---------------------------------------------------------------------------------------
12. DeferredReadFull    DeferredFull_Warp_p.hlsl                    Warp distortion
                        Deferred_ReProjectLm_p.hlsl                 Lightmap reprojection
---------------------------------------------------------------------------------------
13. Reflects_CullObjects (CPU-side pass; no shader)                  Reflection probe cull
---------------------------------------------------------------------------------------
14. DeferredLighting    DeferredGeomLightBall_p.hlsl                 Point lights
                        DeferredGeomLightSpot_p.hlsl                Spot lights
                        DeferredGeomLightFxSphere_p.hlsl            Sphere FX lights
                        DeferredGeomLightFxCylinder_p.hlsl          Cylinder FX lights
                        DeferredGeomProjector_p/v.hlsl              Projected textures
---------------------------------------------------------------------------------------
15. CustomEnding        DeferredGeomCameraMap_p/v.hlsl              Camera-mapped effects
---------------------------------------------------------------------------------------
16. DeferredFogVolumes  DeferredGeomFogBoxOutside_p/v.hlsl          Fog box (outside)
                        DeferredGeomFogBoxInside_p/v.hlsl           Fog box (inside)
                        3DFog_RayMarching_c.hlsl                    Volumetric ray march
                        3DFog_ComputeInScatteringAndDensity_c.hlsl  Scattering
                        3DFog_BlendInCamera_p.hlsl                  Blend fog
---------------------------------------------------------------------------------------
17. DeferredFog         DeferredFogGlobal_p.hlsl                    Global height fog
                        DeferredFog_p.hlsl                          Distance fog
                        DeferredWaterFog_p/v.hlsl                   Water fog
                        DeferredWaterFog_FullTri_p/v.hlsl           Full-screen water fog
---------------------------------------------------------------------------------------
18. LensFlares          LensFlareOccQuery_v.hlsl                    Occlusion query
                        2dFlareAdd_Hdr_p/v.hlsl                     HDR flare composite
                        2dLensDirtAdd_p/v.hlsl                      Lens dirt overlay
---------------------------------------------------------------------------------------
19. FxTXAA              TemporalAA_p.hlsl                           Temporal AA resolve
                        (or NVIDIA GFSDK_TXAA via SDK)              (hardware path)
=======================================================================================
```

---

## Tech3 material and scene shaders (533 shaders)

"Tech3" is Nadeo's 3rd-generation shader framework. Every material in the game maps to a Tech3 shader.

### Block shaders (180 shaders) -- track geometry

The largest single group. Renders all track blocks (road, platform, dirt, ice, grass, plastic).

**Naming convention**: `Block_<TextureSlots>_<Pipeline>_<Variant>_<Stage>.hlsl`

Texture slot codes:
- `T` = albedo Texture, `D` = Diffuse color, `S` = Specular, `N` = Normal map
- `Py` = Y-axis projection (top-down triplanar), `Pxz` = XZ-plane projection (side triplanar)
- `X2` / `H2` = double-resolution variant, `ids` = material ID indexing

Pipeline stages:
- `DefWrite` = G-buffer fill (DeferredWrite pass)
- `DefReadP1` = Deferred lighting read, pass 1
- `PeelDiff` = Depth peeling for lightmap baking
- (no suffix) = forward rendering fallback

| Shader Family | Count | Purpose | WebGPU Approach |
|---------------|-------|---------|-----------------|
| `Block_TDSN_*` | 32 | Standard PBR block (Texture+Diffuse+Specular+Normal) | Single uber-shader with defines |
| `Block_PyPxz_*` | 40 | Triplanar-mapped blocks (Y + XZ projection blend) | Triplanar sampling in fragment |
| `Block_PyDSNX2_*` | 12 | High-res Y-projected blocks | Same as TDSN, higher mip |
| `Block_PTDSN_*` | 8 | Blocks with extra projection layer | Uber-shader variant |
| `Block_PxzDSN_*` | 6 | XZ-only projected blocks (walls, cliffs) | Triplanar sampling |
| `Block_PxzTDSN_*` | 6 | XZ-projected with texture layer | Triplanar + texture |
| `Block_PyPxzTLayered_*` | 8 | Layered triplanar (terrain blend) | Multi-layer blend |
| `Block_DefReadP1_*` | 23 | Lighting read variants (LM0/LM1/LM2, COut, SI) | Deferred read uber-shader |
| `Block_TreeSprite_*` | 9 | Billboard tree sprites on blocks | Billboard vertex shader |
| `Block_TAdd*` | 12 | Additive-blend blocks (signs, lights, energy) | Forward alpha-add pass |
| `Block_TSelfI_*` | 5 | Self-illuminated blocks (emissive) | Emissive channel in G-buffer |
| `Block_Ice*` / `Block_WaterWall*` | 4 | Ice and water wall surfaces | Specialized material |
| `Block_DecalGeom_*` | 6 | Geometric decals on blocks | Decal projection shader |
| `Block_LQ_*` | 2 | Low-quality fallback blocks | Simplified material |
| `Block_ReflectLQ_*` | 2 | Low-quality reflective blocks | Cube sample + tint |

### Variant explosion analysis

The 180 block shaders derive from approximately 6 core programs:

```
CORE BLOCK SHADERS:
1. Block_TDSN          -- Standard PBR (single texture + Diffuse/Specular/Normal)
2. Block_PyPxz         -- Triplanar Y + XZ (terrain-like, two projections)
3. Block_PyDSNX2       -- High-res Y-projected
4. Block_PxzDSN        -- XZ-projected walls
5. Block_PTDSN         -- Extra projection layer + TDSN
6. Block_PyPxzTLayered -- Layered triplanar terrain blend

EACH CORE has up to 8 pipeline variants:
  - _p/_v              (forward rendering)
  - _DefWrite_p/_v     (G-buffer fill)
  - _DefReadP1_*       (deferred lighting, with LM0/LM1/LM2/COut/SI sub-variants)
  - _PeelDiff_p/_v     (depth peeling for lightmap baking)
  - _Anim_v            (animated texture coordinates)
  - _Shadow_v          (shadow caster)
  - _ZOnly_p/_v        (depth-only)
  - _DecalMod_*        (decal-modulated)

MODIFIERS create additional sub-variants:
  - COut / CIn         (color output / input -- sticker/paint system)
  - DispIn / Parallax  (displacement input / parallax mapping)
  - Hue                (hue-shift for color variants)
  - X2H2               (resolution multiplier)
  - ids                (material ID indexing)
  - TI / SI            (texture illumination / self-illumination)
  - OpBlend / OpTest   (opacity blend / opacity test)
```

### WebGPU consolidation strategy

Implement **1 uber-shader** with pipeline overrides instead of 180+ block files:

```wgsl
// block_material.wgsl -- single uber-shader
// Compile-time variants via pipeline overrides:
//   PROJECTION_MODE: 0=TDSN, 1=PyPxz, 2=PxzDSN, 3=PTDSN, 4=Layered
//   PIPELINE_STAGE:  0=GBuffer, 1=DeferredRead, 2=Forward, 3=DepthOnly, 4=Shadow
//   HAS_SELF_ILLUM:  0/1
//   HAS_COLOR_OUT:   0/1
//   LIGHTMAP_TIER:   0/1/2
//   HAS_PARALLAX:    0/1
```

This collapses ~180 block shaders into ~30 pipeline specializations. Apply the same pattern for cars (~31 shaders -> 1 uber-shader) and trees (~30 shaders -> 1 uber-shader).

### Car shaders (31 shaders)

| Shader | Pipeline | Purpose |
|--------|----------|---------|
| `CarSkin_DefWrite_p/v` | G-buffer | Main car body with skin texture |
| `CarSkin_DefRead_p/v` | Deferred read | Lighting on car body |
| `CarSkin_p/v` | Forward | Forward-rendered car body |
| `CarSkin_SpecAmbient_p` | Ambient | Specular ambient for car |
| `CarDetails_DefWrite_p/v` | G-buffer | Car detail parts (spoiler, wheels) |
| `CarDetails_DefRead_p/v` | Deferred read | Lighting on details |
| `CarDetails_p/v` | Forward | Forward detail rendering |
| `CarDetails_SpecAmbient_p/v` | Ambient | Detail specular ambient |
| `CarGems_DefWrite_p/v` | G-buffer | Gem/crystal car parts |
| `CarGems_p/v` | Forward | Forward gem rendering |
| `CarGlass_p1_p/v` | Forward pass 1 | Windshield, first layer |
| `CarGlass_p2_p/v` | Forward pass 2 | Windshield, second layer |
| `CarGlass_Opacity_p/v` | Forward | Glass opacity pass |
| `CarGlassRefract_p/v` | Forward | Refractive glass |
| `CarGhost_p/v` | Ghost layer | Transparent ghost car |
| `CarAnimSkelDmg_v` | Vertex | Skeletal damage animation |
| `CarAnimSkelDmg_Teleport_v` | Vertex | Teleport effect on damaged car |
| `CarAnimSkelDmg_VertexAddLight_v` | Vertex | Per-vertex lighting for damaged car |
| `PeelDepthDiffuse_Car_p/v` | Lightmap bake | Depth peel for car lightmap |

### Deferred pipeline shaders (53 shaders)

Core infrastructure for the 19-pass deferred pipeline.

| Shader | Pass | Purpose |
|--------|------|---------|
| `Deferred_SetILightDir_p` | DeferredRead | Set indirect light direction from probes |
| `Deferred_AddAmbient_Fresnel_p` | DeferredRead | Add ambient with Fresnel at grazing angles |
| `Deferred_AddLightLm_p` | DeferredRead | Add baked lightmap contribution |
| `Deferred_SetLDirFromMask_p` | DeferredRead | Derive light direction from LightMask buffer |
| `Deferred_ReProjectLm_p` | DeferredRead | Reproject lightmap for temporal stability |
| `DeferredCameraMotion_p/v` | CameraMotion | Per-pixel motion vectors |
| `DeferredShadowPssm_p/v` | DeferredShadow | Sample 4-cascade PSSM shadow maps |
| `DeferredDecalGeom_p/v` | DeferredDecals | Box-projected deferred decals |
| `DeferredDecalGeom_TIntens_PyDiff_p/v` | DeferredDecals | Intensity-modulated Y-projected decal |
| `DeferredDecalGeom_VDiff_p/v` | DeferredDecals | Vertex-colored decal |
| `DeferredDecalGeom_VtxAmbient_v` | DeferredDecals | Vertex ambient decal |
| `DeferredDecal_Boxs_p` | DeferredDecals | Batched box decals (pixel) |
| `DeferredDecal_Boxs_CBuffer_v` | DeferredDecals | Box decals via constant buffer |
| `DeferredDecal_Boxs_SRView_v` | DeferredDecals | Box decals via SRV |
| `DeferredDecal_FullTri_p/v` | DeferredDecals | Full-screen-triangle decal |
| `DeferredGeomBurnSphere_p/v` | DeferredBurn | Tire/scorch burn marks |
| `DeferredGeomFakeOcc_p/v` | DeferredFakeOcc | Fake AO for distant objects |
| `DeferredGeomCameraMap_p/v` | CustomEnding | Camera-mapped texture projection |
| `DeferredGeomLightBall_p` | DeferredLighting | Point light (sphere proxy) |
| `DeferredGeomLightSpot_p` | DeferredLighting | Spot light (cone proxy) |
| `DeferredGeomLightFxSphere_p` | DeferredLighting | Decorative sphere light |
| `DeferredGeomLightFxCylinder_p` | DeferredLighting | Decorative cylinder light |
| `DeferredGeomProjector_p/v` | DeferredLighting | Projected texture light |
| `DeferredGeomShadowVol_p/v` | DeferredShadow | Shadow volume stencil |
| `DeferredGeomFogBoxOutside_p/v` | DeferredFogVolumes | Fog box (camera outside) |
| `DeferredGeomFogBoxInside_p/v` | DeferredFogVolumes | Fog box (camera inside) |
| `DeferredFog_p` | DeferredFog | Global distance fog |
| `DeferredFogGlobal_p` | DeferredFog | Full global fog |
| `DeferredFaceNormalFromDepth_p` | DeferredWriteFNormal | Reconstruct face normals from depth |
| `DeferredDeCompFaceNormal_p` | DeferredWriteFNormal | Decompress stored face normals |
| `DeferredFull_Warp_p` | DeferredReadFull | Full-screen warp distortion |
| `DeferredZBufferToDist01_p` | Utility | Convert Z-buffer to linear [0,1] distance |
| `DeferredWrite_BlackNoSpec_p/v` | DeferredWrite | Black material with no specular |
| `DeferredRain_p` | Post-lighting | Rain screen-space effect |
| `DeferredWaterFog_p/v` | DeferredFog | Water-influenced fog |
| `DeferredWaterFog_FullTri_p/v` | DeferredFog | Full-screen water fog |
| `DeferredOutput_ImpostorConvert_c` | Impostors | Compute: convert 3D to impostor billboard |

### Water/ocean shaders (18 shaders)

| Shader | Stage | Purpose |
|--------|-------|---------|
| `Ocean_p/v` | VS/PS | Main ocean surface rendering |
| `Ocean_h/d` | Hull/Domain | Tessellation for ocean mesh |
| `Ocean_tri_h/d/v` | Tessellation | Triangle tessellation path |
| `Ocean_trigeom_h/d/v` | Tessellation | Triangle geometry tessellation |
| `Ocean_Flow_c` | Compute | Flow map simulation |
| `Ocean_FlowStream_c` | Compute | Stream flow computation |
| `Ocean_Gradient_c` | Compute | Wave gradient computation |
| `Ocean_ProfileBuffer_c` | Compute | Wave profile buffer generation |
| `Ocean_ObjectDepthMask_p/v` | Depth | Object depth mask for ocean |
| `Ocean_Particles_p/v` | Forward | Ocean spray particles |
| `Sea_p/v` | Forward | Simpler sea surface rendering |
| `Sea_DefWrite_p/v` | G-buffer | Sea G-buffer write |
| `Sea_BlendRefract_p` | Forward | Sea refraction blend |
| `WaterFall_p/v` | Forward | Waterfall rendering |
| `WaterFog_WGeomUnder_p/v` | Fog | Underwater geometry fog |
| `WaterFogFromDepthH_p/v` | Fog | Height-based water fog |
| `WaterFogFromDepthH_FullTri_p` | Fog | Full-screen water fog |
| `WaterNormals_p/v` | Utility | Water normal map generation |

### Tree/vegetation shaders (30 shaders)

| Shader Family | Count | Purpose |
|---------------|-------|---------|
| `Tree_SelfAO_DefWrite_p/v` | 3 | Tree G-buffer with self-AO |
| `Tree_SelfAO_DefRead_p/v` | 2 | Tree deferred lighting |
| `Tree_SelfAO_p/v` | 2 | Tree forward rendering |
| `Tree_SelfAO_TDSN_p/v` | 2 | Tree with full TDSN material |
| `Tree_SelfAO_Shadow_p` | 1 | Tree shadow caster |
| `Tree_SelfAO_ZOnly_p/v` | 2 | Tree depth-only pass |
| `Tree_SelfAO_NoInstance_DefWrite_v` | 1 | Non-instanced tree variant |
| `Tree_Impostor_DefWrite_p/v` | 2 | Tree impostor G-buffer |
| `Tree_Impostor_DefRead_p/v` | 2 | Tree impostor lighting |
| `Tree_Impostor_p/v` | 2 | Tree impostor forward |
| `Tree_Instance_AddLight_c` | 1 | Compute: per-instance lighting |
| `Tree_Shadow_v` | 2 | Tree shadow vertex |
| `Tree_VertexAddLight_p/v` | 2 | Per-vertex light addition |
| `PeelDepthDiffuse_Tree_p/v` | 2 | Depth peel for lightmap bake |
| `DepthColor_Upscale2x2_p` | 1 | Upscale tree depth/color |
| `MergeColor_p` / `MergeDepth_p` etc. | 4 | Merge/composite tree layers |

### Grass shaders (10 shaders)

| Shader | Purpose |
|--------|---------|
| `Grass/Grass_p/v` | Main grass blade rendering |
| `Grass/Chunk_AddInstances_c` | Compute: populate grass instances per chunk |
| `Grass/SetMatterId_p/v` | Set material ID for grass |
| `GrassFence_p/v` | Grass fence border rendering |
| `GrassFence_VDepLight_DefWrite_p/v` | Grass fence G-buffer with vertex lighting |
| `GrassFence_VDepLight_DefRead_p/v` | Grass fence deferred read |
| `GrassFence_VDepLight_p/v` | Grass fence forward |
| `GrassFence_VDepLight_ZOnly_p/v` | Grass fence depth only |

### Dynamic object shaders (55 shaders)

Animated/dynamic objects including characters, kinematic items, and moving decorations.

| Family | Count | Purpose |
|--------|-------|---------|
| `BodyAnim_*` | 22 | Skeletal animated bodies (DefWrite, DefRead, forward, energy, shield, teleport) |
| `BodyAnimSkel_*` | 3 | Skeletal body with per-vertex lighting and depth peel |
| `Body_Tween_*` | 3 | Vertex morph/tween animated bodies |
| `BodyParticule_p/v` | 2 | Particle-system driven body |
| `CharAnimSkel_Body_*` | 6 | Character body (DefWrite, DefRead, forward) |
| `CharAnimSkel_Part_*` | 6 | Character parts (helmet, accessories) |
| `CharAnimSkel_Anim_v` | 1 | Character skeletal animation vertex |
| `Dyna_TDSN_DefWrite_p` | 1 | Dynamic TDSN G-buffer |
| `Dyna_TDSNE_DefRead_p` / `Dyna_TDSNI_DefRead_p` | 2 | Dynamic deferred read (emissive / illuminated) |
| `Dyna0_TN_*` / `Dyna1_TN_*` | 9 | Dynamic LOD 0/1 shaders |
| `DynaFacing_*` | 6 | Camera-facing dynamic sprites |
| `DynaSpriteDiffuse_*` | 6 | Dynamic diffuse sprites |

### Warp shaders (31 shaders)

Surface warping/distortion for terrain blending and animated materials.

| Family | Count | Purpose |
|--------|-------|---------|
| `Warp_Py_To_PyPgx2_*` | 4 | Y-projection to Y+Grass X2 warp |
| `Warp_PyaDiff_To_PDiffPGrassX2_*` | 4 | Y-alpha-Diffuse to Grass warp |
| `Warp_PyaPxz_*` / `Warp_PyPxz_*` | 8 | Triplanar projection warps |
| `Warp_TDiffSpec_VertexTween_*` | 7 | Vertex tween with diffuse+specular |
| `Warp_TDiffSpecNorm_*` | 8 | Full TDSN warp variants |

### Other Tech3 shaders

| Shader | Count | Purpose |
|--------|-------|---------|
| `Voxel_*` / `VoxelIce_*` | 13 | Voxel-based geometry rendering (ice, terrain) |
| `Decal2d_*` / `Decal3d_*` / `DecalSprite*` | 18 | 2D/3D/sprite decals |
| `Ice_*` / `IceWall_*` / `IcePathBorder_*` | 7 | Ice surface variants |
| `MenuBox_*` | 6 | Menu/UI 3D boxes |
| `Sky_p/v` | 2 | Sky dome rendering |
| `Stars_p/v` | 2 | Star field rendering |
| `SSReflect_*` | 5 | Screen-space reflections |
| `SpriteAdd*` / `SpriteBlendSoft*` | 6 | Additive/blended sprite effects |
| `SphereShield*` | 4 | Shield sphere effects (ShootMania origin) |
| `Impostor_p/v` | 2 | Generic impostor billboard |
| `GlassBasic_p/v` | 2 | Basic glass material |
| `EditorHelpers_p/v` | 2 | Editor helper visualization |
| `SelfIllumAtHue_p/v` | 2 | Self-illuminated with hue shift |

---

## Engine infrastructure shaders (218 shaders)

Low-level rendering utilities shared across all game modes.

### Culling and instancing (7 shaders)

| Shader | Type | Purpose |
|--------|------|---------|
| `Instances_Cull_SetLOD_c` | Compute | GPU frustum culling + LOD selection (DipCulling pass) |
| `Instances_Merge_c` | Compute | Merge culled instance lists |
| `Instances_AddCount_ToN_c` | Compute | Accumulate instance counts |
| `Instances_AddCounts_c` | Compute | Sum instance counts |
| `IndexedInst_SetDrawArgs_LOD_SGs_c` | Compute | Write indirect draw arguments per LOD/shadow group |
| `ForwardTileCull_c` | Compute | Forward+ tile-based light culling |
| `ForwardTileCull_DbgDraw_p` | Pixel | Debug visualization of tile culling |

### PBR / IBL tooling (6 shaders)

| Shader | Type | Purpose |
|--------|------|---------|
| `Pbr_IntegrateBRDF_GGX_c` | Compute | Pre-compute GGX BRDF LUT (NdotV x roughness) |
| `Pbr_PreFilterEnvMap_GGX_c` | Compute | Split-sum IBL env map pre-filtering |
| `Pbr_FastFilterEnvMap_GGX_c` | Compute | Fast env map filter variant |
| `Pbr_FastFilterEnvMap_MirrorDiagXZ_c` | Compute | Mirror diagonal XZ for symmetric env maps |
| `Pbr_RoughnessFilterNormalInMips_c` | Compute | Filter normal maps by roughness in mip chain |
| `Pbr_Spec_to_Roughness_c` | Compute | Convert specular power to roughness |

### Buffer / texture utilities (30+ shaders)

| Family | Purpose |
|--------|---------|
| `Buffer_Fill/Copy/Add/IndexCopy_c` | Compute buffer operations |
| `BufferReduction_*_c` | Parallel reduction (min/max, SH2, SH3) |
| `CopyRawTexture2D/3D_c` | Raw texture copies |
| `CopyTexture2dArray_c` | Texture array copies |
| `MakeMips*_c` | Compute mipmap generation |
| `Texture_Fill_c` / `Texture3d_CopyFromBuffer_c` | Texture fill/copy |
| `Convert_RGB_to_YCC_c` | Color space conversion |
| `Encode_BC4/BC5_p/v` | Block compression encoding |

### Depth / Z-buffer (15 shaders)

| Shader | Purpose |
|--------|---------|
| `ZOnly_p/v` | Depth-only pass (Z-prepass) |
| `ZOnly_Alpha01_p/v` | Alpha-tested depth pass |
| `ZOnly_InstancingStatic_v` | Instanced static depth |
| `ZOnly_InstScaleAniso_v` | Anisotropic-scaled instanced depth |
| `ZOnly_ClipFarZ_v` | Far-Z clipped depth |
| `ZOnly_Peel_p` | Depth peeling pass |
| `ZOnly_StaticKillMesh_*` | Kill-mesh depth (visibility masks) |
| `ZOnlyParaboloid_v` | Paraboloid projection depth |
| `DepthDown2x2_Max/MinMax/Range_p` | Depth hierarchy downsampling |
| `DepthDown3x3_Max_p` | 3x3 depth downsample |
| `DepthGetLinearZ01_p` | Linear depth extraction |
| `DepthGutterMax_p` | Depth gutter fill |
| `DepthUp_p` | Depth upsampling |

### Cubemap / environment (12 shaders)

| Shader | Purpose |
|--------|---------|
| `CubeMap_EyeInWorld_p/v` | Cubemap rendering (eye position) |
| `CubeMap_EyeInWorld_HdrAlpha2_p` | HDR cubemap with alpha |
| `CubeMap_EyeInWorld_GradientV_p` | Cubemap with vertical gradient |
| `CubeMapFromNormal_p/v` | Cubemap lookup from normal |
| `CubeToSphereHdrA2_p` | Cube-to-sphere HDR conversion |
| `Cube_CopyAndMirrorDiag_c` | Mirror cubemap diagonal |
| `Cube_Down2x2_c` | Cubemap downsample |
| `Cube_MulBounceFactor_c` | Multiply bounce factor into cubemap |
| `CubeFromEquirectMirror_c` | Equirectangular to cubemap |
| `CubeFilterDown4x4_Cube3x2_p/v` | 4x4 cubemap filter |
| `EquiRectFromCube_p` | Cubemap to equirectangular |
| `EquiRectFromCubeFace_p` | Per-face cubemap to equirect |

### Rasterization / blitting (30+ shaders)

| Family | Purpose |
|--------|---------|
| `RasterBitmapBlend*_p` | Bitmap compositing (various modes) |
| `RasterBitmapAlpha_p` | Alpha bitmap |
| `RasterBitmapMsaa_p` | MSAA bitmap resolve |
| `RasterMsaaResolve_p` / `_Hdr_p` | MSAA resolve (LDR and HDR) |
| `RasterBink_YCrCb_*` | Bink video decode/render |
| `RasterConst_p` / `ConstPreMod_p` | Constant-color fill |
| `RasterBlendFogUp*_TestZ_p` | Upscale fog with depth test |

### Full-screen triangle (5 shaders)

| Shader | Purpose |
|--------|---------|
| `FullTriangle_v` | Minimal full-screen triangle vertex |
| `FullTriangle_TexCoord_v` | Full-screen triangle with UVs |
| `FullTriangle_TcRect_v` | Full-screen triangle with rect UVs |
| `FullTriangle_Batch_v/g` | Batched full-screen triangle (uses geometry shader) |

### Normal map baking (6 shaders)

| Shader | Purpose |
|--------|---------|
| `ComputeGrid3D_Allocate_c` | Allocate 3D grid for baking |
| `ComputeGrid3D_FillGrid_c` | Fill 3D grid |
| `NormalMapBaker_p/v` | Bake normal maps from geometry |
| `NormalMapDownSize4x4_c` | Downsample baked normals |
| `NormalMapGutter_p` | Fill gutter pixels |
| `Grid3D_DebugRender_p/v` | Debug: render 3D grid |

### Mesh occlusion (6 shaders)

| Shader | Purpose |
|--------|---------|
| `MeshOcclusionProj_p` | Project occlusion geometry |
| `MeshOcclusionSelf_p/v` | Self-occlusion computation |
| `MeshOcclusionSelf_AccumPerTri_c` | Compute: per-triangle occlusion |
| `MeshOcclusionSelf_AccumNormalize_c` | Compute: normalize AO accumulation |
| `MeshOccDownAndComp_p` | Downsample and compose occlusion |

### Miscellaneous engine shaders

| Shader | Purpose |
|--------|---------|
| `GeomImGui_p/v` | Dear ImGui rendering (developer overlay) |
| `GeomToFaceNormal_Alpha01_p/v` | Geometry to face normal (alpha tested) |
| `GeomToReflectCubeDist/Map_p/v` | Geometry to reflection cubemap |
| `LensFlareOccQuery_v` | Lens flare occlusion query |
| `LmILight_*_c` | Lightmap indirect light compute shaders |
| `PixelBlendCubes_g/p/v` | Blend cubemaps (geometry shader path) |
| `SortLib/*_c` | GPU parallel bitonic sort (4 shaders) |
| `DriverCrash_p/v` | Intentional crash shader (debug) |

---

## Post-processing and particle shaders (154 shaders)

### Post-processing (40 shaders)

**Bloom** (6 shaders):

| Shader | Purpose |
|--------|---------|
| `BloomSelectFilterDown2_p` | Threshold + 2x downsample |
| `BloomSelectFilterDown4_p` | 4x downsample |
| `Bloom_HorizonBlur_p` | Horizontal Gaussian blur per mip |
| `Bloom_StreaksWorkDir_p` | Directional light streaks (anamorphic) |
| `Bloom_StreaksSelectSrc_p` | Select streak source intensity |
| `Bloom_Final_p` | Composite bloom back to HDR |

**Tone mapping** (8 shaders):

| Shader | Purpose |
|--------|---------|
| `TM_GetLumi_p` | Extract luminance from HDR |
| `TM_GetLog2LumiDown1_p/v` | Log2 luminance + downsample |
| `TM_GetAvgLumiCurr_p` | Average luminance (current frame) |
| `TM_GetAvgLumiCurr_VeryFast_p` | Fast luminance average |
| `TM_GetLdrALogFromCopyFirst_p` | LDR adaptive log |
| `TM_GlobalOp_p` | Global Reinhard operator |
| `TM_GlobalOpAutoExp_p` | Global + auto-exposure |
| `TM_GlobalFilmCurve_p` | Filmic curve (Hable-style power segments) |
| `TM_LocalOp_p` | Local per-pixel adaptive tone map |

**Anti-aliasing** (2 shaders):

| Shader | Purpose |
|--------|---------|
| `FXAA_p` | FXAA 3.11 implementation |
| `TemporalAA/TemporalAA_p` | Ubisoft custom TXAA (cross-vendor TAA) |

**Color grading** (3 shaders):

| Shader | Purpose |
|--------|---------|
| `ColorGrading_p` | LUT-based 3D color grading |
| `Colors_p` | Brightness/contrast/saturation |
| `ColorBlindnessCorrection_p` | Accessibility: color blindness filter |

**HBAO+** (9 shaders):

| Shader | Purpose |
|--------|---------|
| `LinearizeDepth_p` | Step 1: Convert depth to linear Z |
| `DeinterleaveDepth_p` | Step 2: Split into 4x4 interleaved layers |
| `ReconstructNormal_p` | Step 3: Reconstruct normals from depth |
| `CoarseAO_p` | Step 4: Main AO computation (quarter-res) |
| `CoarseAO_g` | Step 4 alt: Geometry shader variant |
| `ReinterleaveAO_p` | Step 5: Recombine layers to full-res |
| `BlurX_p` | Step 6a: Bilateral blur horizontal |
| `BlurY_p` | Step 6b: Bilateral blur vertical |
| `FullScreenTriangle_v` | Utility: full-screen triangle for HBAO+ |

**Other PostFx** (12 shaders):

| Shader | Purpose |
|--------|---------|
| `DoF_T3_BlurAtDepth_p` | Depth of field blur |
| `BlurWeighted_p` | Weighted Gaussian blur |
| `EdgeBlender_Detect_p/v` | Edge detection for blending |
| `EdgeBlender_Gutter_p` | Gutter fill for edge blend |
| `StereoAnaglyph*_p` (3) | Stereoscopic 3D modes |
| `DebugBitmap_p` | Debug: display any render target |

### Particles (51 shaders)

**Core particle pipeline** (14 shaders):

| Shader | Type | Purpose |
|--------|------|---------|
| `MgrParticleSpawn_p/v` | VS/PS | Spawn new particles |
| `MgrParticleSpawnPoints_p/v` | VS/PS | Spawn at specific points |
| `MgrParticleUpdate_c` | Compute | Main particle simulation |
| `MgrParticleUpdateFromCPU_c` | Compute | CPU-driven parameter update |
| `MgrParticleRender_p/v` | VS/PS | Alpha-blended particle rendering |
| `MgrParticleRenderOpaques_p/v` | VS/PS | Opaque particle rendering |
| `MgrParticleRenderStatic_p/v` | VS/PS | Static (non-animated) particles |
| `MgrParticleRenderStaticFakeOcc_p/v` | VS/PS | Static particles with fake occlusion |
| `MgrParticleShadow_p/v` | VS/PS | Particle shadow casting |

**Self-shadowing** (5 shaders):

| Shader | Purpose |
|--------|---------|
| `SelfShadow/ParticleVoxelization_g/p/v` | Voxelize particles via geometry shader |
| `SelfShadow/ParticlePropagation_p/v` | Propagate shadow through volume |
| `SelfShadow/ParticlesShadowOnOpaque_p/v` | Apply particle shadow on opaque |

**Water interaction** (7 shaders):

| Shader | Purpose |
|--------|---------|
| `WaterSplash_IntersectTriangles_p` | GPU triangle intersection for splash |
| `WaterSplash_SpawnParticles_p/v` | Spawn splash at collision |
| `CameraWaterDroplets/CameraWaterDroplets_Spawn_c` | Spawn screen droplets |
| `CameraWaterDroplets/CameraWaterDroplets_Update_c` | Update screen droplets |
| `CameraWaterDroplets/CameraWaterDroplets_Render_p` | Render screen droplets |

### Fog (12 shaders)

| Shader | Type | Purpose |
|--------|------|---------|
| `3DFog_RayMarching_c` | Compute | Volumetric fog ray marching |
| `3DFog_ComputeInScatteringAndDensity_c` | Compute | In-scattering + density field |
| `3DFog_BlendInCamera_p` | Pixel | Blend fog into camera view |
| `3DFog_UpdateNoiseTexture_c` | Compute | Animated fog noise |
| `ComputeFogSpaceInfo_c` | Compute | Fog space transform setup |
| `FogInC_Compute_c` | Compute | Camera-space fog compute |
| `FogInC_Copy_c` | Compute | Copy fog buffer |
| `FogInC_Propagate_c` | Compute | Propagate fog |
| `FogInC_Propagate_WithLuminance_c` | Compute | Propagate fog with luminance |
| `UpdateFog_c` | Compute | Update fog state |
| `FogSpaceInfoRender_p/v` | VS/PS | Render fog space debug info |

### Other effects

| Shader | Purpose |
|--------|---------|
| `MotionBlur2d_p` | Per-pixel velocity motion blur |
| `PlaneReflect_BumpScale_HyperZ_p` | Planar reflection with bump |
| `SubSurface/SeparableSSS_p` | Jimenez separable SSS |
| `SignedDistanceField/*` (4) | SDF generation and rendering |
| `Energy/*` (5) | Energy beam/field effects |
| `2dFlareAdd_Hdr_p/v` | HDR lens flare composite |
| `2dLensDirtAdd_p/v` | Lens dirt overlay |
| `2dMoon_p/v` | Moon billboard rendering |

---

## Lightmap shaders (78 shaders)

### Lightmap baking and compression

| Shader | Type | Purpose |
|--------|------|---------|
| `LmCompress_HBasis_YCbCr4_c` | Compute | Compress lightmap to H-basis in YCbCr4 |
| `LmLBumpILighting_Inst_p/v` | VS/PS | Bumped indirect lighting from lightmap |
| `LmLBumpAmbient_Inst_p` | PS | Bumped ambient from lightmap |
| `LmLBumpDirect_Inst_p` | PS | Bumped direct light from lightmap |
| `LmLBumpLDir_Inst_p` | PS | Bumped light direction from lightmap |
| `LmLBumpProj_Inst_p` | PS | Bumped projected light from lightmap |
| `LmLHBasisDirect_Inst_p` | PS | H-basis direct lighting |
| `LmLHBasisILighting_Inst_p` | PS | H-basis indirect lighting |
| `LmLIndex_Inst_p` | PS | Lightmap index lookup |
| `LmLIndex_Sort_c` | Compute | Sort lightmap indices |
| `LmILightDir_Set_p` | PS | Set indirect light direction |
| `LmILightDir_AddAmbient_c` | Compute | Add ambient to indirect light direction |

### Light probe grid (12 shaders)

| Shader | Type | Purpose |
|--------|------|---------|
| `ProbeGrid_Sample_c` | Compute | Sample probe grid at position |
| `ProbeGrid_Sample_CbTrans_c` | Compute | Sample with transform |
| `ProbeGrid_LightListSample_QuatTrans_c` | Compute | Sample with quaternion transform |
| `ProbeGrid_ListMerge_c` | Compute | Merge probe lists |
| `ProbeGrid_LightAcc_p` | PS | Accumulate probe light |
| `ProbeGrid_LightWeightMax_p` | PS | Max probe weight |
| `ProbeGrid_SetILightDir_p` | PS | Set indirect direction from probe |
| `ProbeGrid_SetIsValid_p` | PS | Mark valid probes |
| `ProbeGrid_AddSkyVisibility_p` | PS | Add sky visibility term |
| `ProgeGrid_List_Sort_c` | Compute | Sort probe list (note typo "Proge") |

### Dynamic lightmap (DynaBox) (10 shaders)

| Shader | Type | Purpose |
|--------|------|---------|
| `DynaBox_AddLight_c` | Compute | Add dynamic light to box |
| `DynaBox_SetDiffuse_c` | Compute | Set dynamic diffuse |
| `DynaBox_LightAccumMulDiffuse_c` | Compute | Multiply accumulated light by diffuse |
| `DynaBox_SetLightAmb_FromHandle_c` | Compute | Set ambient from handle |
| `DynaBox_ILightDir_SetFromPeel_c` | Compute | Set indirect direction from peel |
| `DynaBox_ILightDir_AddToAccum_c` | Compute | Add indirect direction to accumulator |
| `LightFromMapT3_p/v` | VS/PS | Sample baked lightmap for dynamic objects |

---

## Other shader categories

### Painter (16 shaders) -- car skin system

| Shader | Purpose |
|--------|---------|
| `BlendLayer_p/v` | Blend paint layers |
| `BlendLayer_TextureOp_p` | Blend with texture operation |
| `BlendLayerStencil_p` | Stencil-masked layer blend |
| `ModulateLayer_p/v` | Modulate (multiply) layer |
| `ModulateSvg_p` | Modulate SVG overlay |
| `FillSvg_p/v` | Fill SVG shape |
| `PaintWithAlpha_p/v` | Alpha paint brush |
| `ShadingImage_p/v` | Shading image generation |

### Menu (16 shaders) -- UI rendering

| Shader | Purpose |
|--------|---------|
| `BackgroundLayer_p/v` | Menu background |
| `BackgroundLayerBlur_p/v` | Blurred background |
| `BackgroundLayerHueShift_p/v` | Hue-shifted background |
| `BlendTextureAndBorderMask_p/v` | Texture + border mask blend |
| `BlendTextureSuperSample_p/v` | Super-sampled texture blend |
| `CutOff_p/v` | Cutoff transition effect |
| `Hud3d_p/v` | 3D HUD elements |
| `ShowMiniMap_p/v` | Minimap display |

### Clouds (9 shaders)

| Shader | Purpose |
|--------|---------|
| `CloudsT3b_p/v` | Cloud rendering (Tech3b variant) |
| `CloudsTech3_p/v` | Cloud rendering (Tech3) |
| `CloudsTech3_Opacity_p/v` | Cloud opacity pass |
| `CloudsEdgeLight_p` | Cloud edge lighting (silver lining) |
| `CloudsGodLight_p` | God ray light shafts |
| `CloudsGodMask_p` | God ray masking |

### Garage (10 shaders)

| Shader | Purpose |
|--------|---------|
| `Garage_TDiff_p/v` | Garage floor diffuse |
| `Garage_TDiff_GroundReflect_p/v` | Garage ground reflection |
| `Garage_TSelfI_p/v` | Garage self-illuminated elements |
| `PlaneReflect_InMenus_p/v` | Planar reflection in menu scenes |
| `PlaneReflect_InMenus_DefRead_p/v` | Deferred read for menu reflection |

### Root-level material templates (26 entries)

`.PHlsl.Txt` / `.VHlsl.Txt` material templates referenced by `.Shader.Gbx` files:

| Template | Purpose |
|----------|---------|
| `PC3` (4 pixel + 2 vertex) | Base material template (multiple variants) |
| `TEmblem` (2p + 2v) | Emblem/logo overlay shader |
| `TEnergySwitch` (1p + 1v) | Energy switch effect |
| `TDiff_Spec_Norm_Switch` (1p + 1v) | Diffuse+Specular+Normal with switch |
| `TNorm_Switch` (1p + 1v) | Normal-only switch |
| `TRenderOverlay` (1p + 1v) | Render overlay shader |
| `PyDiffSpecNormSwitch_PyGrassX2` (1p + 1v) | Y-projected material with grass X2 |
| `PoleEnergy` / `PoleEnergyInt` (2p + 2v) | Energy pole effects |
| `GeomLProbe` (1p + 1v) | Geometry light probe |
| `DefReadP1_Probe` (1p) | Deferred read pass 1 with probe |

---

## Complete post-processing shader sequence

Executed after deferred lighting in this order:

```
STAGE                SHADER(S)                              WEBGPU APPROACH
===============================================================================
1. Fog Volumes       DeferredGeomFogBoxOutside_p/v          Render fog box geom
                     DeferredGeomFogBoxInside_p/v           Inside variant
                     3DFog_RayMarching_c                    Compute ray march
                     3DFog_ComputeInScatteringAndDensity_c  Compute scattering
                     3DFog_UpdateNoiseTexture_c             Compute noise
                     3DFog_BlendInCamera_p                  Composite fog
-------------------------------------------------------------------------------
2. Global Fog        DeferredFogGlobal_p                    Full-screen pass
                     DeferredFog_p                          Distance-based fog
                     DeferredWaterFog_p/v                   Water fog overlay
                     WaterFogFromDepthH_p/v                 Height-based water fog
-------------------------------------------------------------------------------
3. Lens Flares       LensFlareOccQuery_v                    Occlusion query -> readback
                     2dFlareAdd_Hdr_p/v                     Sprite composite
                     2dLensDirtAdd_p/v                      Screen-space dirt
                     2dMoon_p/v                             Moon billboard
-------------------------------------------------------------------------------
4. Depth of Field    DoF_T3_BlurAtDepth_p                   Variable-kernel blur
-------------------------------------------------------------------------------
5. Motion Blur       MotionBlur2d_p                         Per-pixel velocity blur
-------------------------------------------------------------------------------
6. Blur              BlurHV_p                               Separable Gaussian
                     BlurHV_DepthMask_p                     Depth-masked blur
                     BilateralBlur_p                        Edge-preserving blur
                     BlurWeighted_p                         Weighted blur
-------------------------------------------------------------------------------
7. Colors            Colors_p                               Brightness/contrast/sat
                     ColorBlindnessCorrection_p             Accessibility
                     ColorGrading_p                         3D LUT
-------------------------------------------------------------------------------
8. Tone Mapping      TM_GetLumi_p                           Extract luminance
                     TM_GetLog2LumiDown1_p/v                Log downsample (chain)
                     TM_GetAvgLumiCurr_p                    Average luminance
                     TM_GlobalFilmCurve_p                   Filmic tone map
                     (or TM_GlobalOpAutoExp_p)              (auto-exposure)
                     (or TM_LocalOp_p)                      (local operator)
-------------------------------------------------------------------------------
9. Bloom             BloomSelectFilterDown2_p               Threshold + 2x down
                     BloomSelectFilterDown4_p               4x down
                     Bloom_HorizonBlur_p                    Horizontal blur (per mip)
                     Bloom_StreaksWorkDir_p                  Anamorphic streaks
                     Bloom_StreaksSelectSrc_p               Streak source
                     Bloom_Final_p                          Composite onto scene
-------------------------------------------------------------------------------
10. Anti-Aliasing    FXAA_p                                 FXAA 3.11
                     (or TemporalAA_p)                      TAA resolve
                     EdgeBlender_Detect_p/v                 Edge detection
-------------------------------------------------------------------------------
11. SSR (deferred)   SSReflect_Deferred_p                   Screen-space ray march
                     SSReflect_Deferred_LastFrames_p        Temporal reprojection
                     SSReflect_Forward_p                    Forward path variant
                     SSReflect_UpSample_p                   Half-res upsample
-------------------------------------------------------------------------------
12. SubSurface       SeparableSSS_p                         Jimenez separable SSS
-------------------------------------------------------------------------------
13. MSAA Resolve     RasterMsaaResolve_p                    LDR resolve
                     RasterMsaaResolveHdr_p                 HDR resolve
-------------------------------------------------------------------------------
14. Final Blit       RasterBitmapBlend*_p (various)         Copy to back buffer
                     DownSize2x2AvgInLdr / 3x3AvgInLdr     Downsample
===============================================================================
```

---

## Compute shaders (105 total)

### GPU culling and instancing (7)

```
Engines/Instances_Cull_SetLOD_c.hlsl         -- Frustum cull + LOD select
Engines/Instances_Merge_c.hlsl               -- Merge instance lists
Engines/Instances_AddCount_ToN_c.hlsl        -- Count accumulation
Engines/Instances_AddCounts_c.hlsl           -- Sum counts
Engines/IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl -- Write indirect draw args
Engines/ForwardTileCull_c.hlsl               -- Forward+ tile light culling
Tech3/Grass/Chunk_AddInstances_c.hlsl        -- Grass instance population
```

### Particle system (11)

```
Effects/Particles/MgrParticleUpdate_c.hlsl           -- Main particle sim
Effects/Particles/MgrParticleUpdateFromCPU_c.hlsl    -- CPU parameter update
Effects/Particles/Particles_ComputeBBox_c.hlsl       -- Bounding boxes
Effects/Particles/Particles_ComputeDepth_c.hlsl      -- Depth for sorting
Effects/Particles/Particles_InitBBoxes_c.hlsl        -- Init bounding boxes
Effects/Particles/ParticlesToFog_c.hlsl              -- Inject into fog
Effects/Particles/CameraWaterDroplets_Spawn_c.hlsl   -- Screen droplet spawn
Effects/Particles/CameraWaterDroplets_Update_c.hlsl  -- Screen droplet update
Effects/Particles/VortexSimulation/VortexSpawn_c.hlsl   -- Vortex spawn
Effects/Particles/VortexSimulation/VortexUpdate_c.hlsl  -- Vortex update
```

### Volumetric fog (9)

```
Effects/Fog/3DFog_RayMarching_c.hlsl                       -- Ray march
Effects/Fog/3DFog_ComputeInScatteringAndDensity_c.hlsl     -- Scattering
Effects/Fog/3DFog_UpdateNoiseTexture_c.hlsl                -- Animated noise
Effects/Fog/ComputeFogSpaceInfo_c.hlsl                     -- Fog space setup
Effects/Fog/FogInC_Compute_c.hlsl                          -- Camera fog compute
Effects/Fog/FogInC_Copy_c.hlsl                             -- Copy fog
Effects/Fog/FogInC_Propagate_c.hlsl                        -- Propagate fog
Effects/Fog/FogInC_Propagate_WithLuminance_c.hlsl          -- Propagate + lumi
Effects/Fog/UpdateFog_c.hlsl                               -- Update fog state
```

### Lightmap and probe grid (16)

```
Lightmap/DynaBox_AddLight_c.hlsl                           -- Dynamic light add
Lightmap/DynaBox_ILightDir_AddToAccum_c.hlsl               -- ILight dir accum
Lightmap/DynaBox_ILightDir_SetFromPeel_c.hlsl              -- ILight from peel
Lightmap/DynaBox_LightAccumMulDiffuse_c.hlsl               -- Light * diffuse
Lightmap/DynaBox_SetDiffuse_c.hlsl                         -- Set diffuse
Lightmap/DynaBox_SetLightAmb_FromHandle_c.hlsl             -- Set ambient
Lightmap/DynaGridProbeId_Sample_CbTrans_c.hlsl             -- Probe sample
Lightmap/DynaGridProbeId_Sample_CbTransOutId_c.hlsl        -- Probe + output ID
Lightmap/LmCompress_HBasis_YCbCr4_c.hlsl                  -- Compress LM
Lightmap/LmILightDir_AddAmbient_c.hlsl                     -- Add ambient
Lightmap/LmLIndex_Sort_c.hlsl                              -- Sort LM indices
Lightmap/LmSSResolve_Spread_ListMerge_c.hlsl               -- SS resolve merge
Lightmap/ProbeGrid_LightListSample_QuatTrans_c.hlsl        -- Probe light sample
Lightmap/ProbeGrid_ListMerge_c.hlsl                         -- Merge probe lists
Lightmap/ProbeGrid_Sample_c.hlsl                            -- Sample probe grid
Lightmap/ProbeGrid_Sample_CbTrans_c.hlsl                    -- Sample w/ transform
Lightmap/ProgeGrid_List_Sort_c.hlsl                         -- Sort probe list
```

### PBR / IBL precomputation (6)

```
Engines/Pbr_IntegrateBRDF_GGX_c.hlsl                -- BRDF LUT
Engines/Pbr_PreFilterEnvMap_GGX_c.hlsl               -- IBL pre-filter
Engines/Pbr_FastFilterEnvMap_GGX_c.hlsl              -- Fast filter
Engines/Pbr_FastFilterEnvMap_MirrorDiagXZ_c.hlsl     -- Mirror diagonal
Engines/Pbr_RoughnessFilterNormalInMips_c.hlsl       -- Normal mip filter
Engines/Pbr_Spec_to_Roughness_c.hlsl                -- Spec to roughness
```

### Buffer utilities (14)

```
Engines/Buffer_Add_c.hlsl                   -- Buffer addition
Engines/Buffer_CopyOrTransform_c.hlsl       -- Copy or transform
Engines/Buffer_CopyRaw_c.hlsl               -- Raw copy
Engines/Buffer_Fill_c.hlsl                  -- Fill buffer
Engines/Buffer_IndexCopy_c.hlsl             -- Indexed copy
Engines/Buffer_IndexedCopy_c.hlsl           -- Indexed copy variant
Engines/Buffer_ScatteredCopy_c.hlsl         -- Scattered write
Engines/BufferReduction_MinOrMax_c.hlsl     -- Min/max reduction
Engines/BufferReduction_SH2_Norm4_c.hlsl    -- SH2 reduction
Engines/BufferReduction_SH3_Rgb_c.hlsl      -- SH3 RGB reduction
Engines/ClearHTilePSVR_c.hlsl              -- Clear H-tile (PSVR)
Engines/PixelCountInBuckets_c.hlsl          -- Pixel histogram
Engines/PixelGetBoundPos_c.hlsl             -- Get bounding position
Engines/PixelMinOrMax_c.hlsl                -- Pixel min/max
```

### Texture utilities (10)

```
CopyTextureFloatToInt_c.hlsl                -- Float to int texture
CopyTextureIntToFloat_c.hlsl                -- Int to float texture
Engines/CopyRawTexture2D_c.hlsl             -- Raw 2D copy
Engines/CopyRawTexture3D_c.hlsl             -- Raw 3D copy
Engines/CopyTexture2dArray_c.hlsl           -- Texture array copy
Engines/Convert_RGB_to_YCC_c.hlsl           -- RGB to YCbCr
Engines/FillDebugPattern_Texture2D_c.hlsl   -- Debug pattern fill
Engines/Texture_Fill_c.hlsl                 -- Texture fill
Engines/Texture3d_CopyFromBuffer_c.hlsl     -- 3D texture from buffer
Noise/FillNoiseVolume_c.hlsl                -- Fill 3D noise volume
```

### Other compute shaders

```
Engines/Cube_CopyAndMirrorDiag_c.hlsl       -- Mirror cubemap diagonal
Engines/Cube_Down2x2_c.hlsl                 -- Cubemap 2x2 downsample
Engines/Cube_MulBounceFactor_c.hlsl         -- Cubemap bounce factor
Engines/CubeFromEquirectMirror_c.hlsl       -- Equirect to cubemap
Engines/MakeMips1D64_c.hlsl                  -- 1D mipmap (64 texels)
Engines/MakeMips8x8_c.hlsl                   -- 8x8 mipmap
Engines/MakeMipsTail8x8_c.hlsl               -- 8x8 mip tail
Engines/NormalMapBaking/ComputeGrid3D_Allocate_c.hlsl  -- Allocate grid
Engines/NormalMapBaking/ComputeGrid3D_FillGrid_c.hlsl  -- Fill grid
Engines/NormalMapBaking/NormalMapDownSize4x4_c.hlsl     -- Downsize normals
Engines/MeshOcclusionSelf_AccumNormalize_c.hlsl  -- Normalize AO
Engines/MeshOcclusionSelf_AccumPerTri_c.hlsl     -- Per-tri AO
Tech3/Ocean_Flow_c.hlsl           -- Ocean flow map simulation
Tech3/Ocean_FlowStream_c.hlsl    -- Stream flow
Tech3/Ocean_Gradient_c.hlsl      -- Wave gradient
Tech3/Ocean_ProfileBuffer_c.hlsl -- Wave profile buffer
Effects/SortLib/InitSortArgs_c.hlsl   -- Init sort args
Effects/SortLib/Sort_c.hlsl           -- Main sort
Effects/SortLib/SortInner_c.hlsl      -- Inner sort
Effects/SortLib/SortStep_c.hlsl       -- Sort step
Effects/SignedDistanceField/SignedDistanceField_Analytic_c.hlsl    -- Analytic SDF
Effects/SignedDistanceField/SignedDistanceField_BruteForce_c.hlsl  -- Brute force SDF
ShadowCache/UpdateShadowIndex_c.hlsl           -- Shadow cache index update
Tech3/DeferredOutput_ImpostorConvert_c.hlsl     -- Convert 3D to impostor
Tech3/Trees/Tree_Instance_AddLight_c.hlsl       -- Per-instance tree light
Engines/LmILight_Bilinear_c.hlsl       -- Bilinear indirect light
Engines/LmILight_MergeBuffers_c.hlsl   -- Merge light buffers
Engines/LmILight_SetFromVideo_c.hlsl   -- Set from video
Engines/LmILight_UpdateTime_c.hlsl     -- Update time-varying light
Engines/ProjectCubeFlat3x2_SH2_Norm4_c.hlsl -- Project cube to SH2
Engines/ProjectCubeFlat3x2_SH3_Rgb_c.hlsl   -- Project cube to SH3 RGB
```

### WebGPU compute compatibility

All 105 compute shaders translate to WebGPU `@compute` shaders. Key mappings:

| TM2020 Feature | WebGPU Equivalent | Notes |
|----------------|-------------------|-------|
| `RWStructuredBuffer` | `storage` buffer | Direct mapping |
| `RWTexture2D/3D` | `storage` texture | Requires `"bgra8unorm-storage"` for some |
| `GroupMemoryBarrier` | `workgroupBarrier()` | Direct mapping |
| `InterlockedAdd` | `atomicAdd()` | Direct mapping |
| `Append/ConsumeBuffer` | No direct equivalent | Use atomic counter + storage buffer |
| Indirect dispatch args | `dispatchWorkgroupsIndirect()` | Direct mapping |

---

## Special effects shaders

### Water system (31 shaders total)

```
OCEAN (deep water):
  Compute:  Ocean_Flow_c -> Ocean_FlowStream_c -> Ocean_Gradient_c -> Ocean_ProfileBuffer_c
  Tessellation: Ocean_h -> Ocean_d -> Ocean_v -> Ocean_p
  Depth mask: Ocean_ObjectDepthMask_p/v

SEA (shallow/pool water):
  Deferred: Sea_DefWrite_p/v -> Sea_p/v
  Refraction: Sea_BlendRefract_p

WATER SURFACE FX:
  WaterNormals_p/v        -- Normal map animation
  WaterFall_p/v           -- Waterfall
  WaterFog_WGeomUnder_p/v -- Underwater geometry fog
  WaterFogFromDepthH_p/v  -- Height-based water fog
  Block_WaterWall_p/v     -- Water wall block surface

PARTICLE INTERACTION:
  WaterSplash_IntersectTriangles_p    -- GPU collision test
  WaterSplash_SpawnParticles_p/v      -- Spawn splash
  CameraWaterDroplets_Spawn/Update_c  -- Screen droplets
  CameraWaterDroplets_Render_p        -- Render droplets
```

**WebGPU approach**: Ocean tessellation must be pre-computed or replaced with compute-based displacement. Flow/gradient/profile compute shaders translate directly.

### Fog system (20 shaders)

Two fog systems exist:

1. **Volumetric 3D Fog** (compute-based): Ray-marches through a froxel grid, renders into a 3D texture, then composites onto the scene.
2. **Deferred Fog** (geometry/screen-space): Full-screen global height/distance fog + box fog volumes placed by map editors.

### Lens effects (6 shaders)

```
Engines/LensFlareOccQuery_v.hlsl       -- Render tiny quad at sun, occlusion query
Effects/2dFlareAdd_Hdr_p/v.hlsl       -- Composite HDR flare sprites
Effects/2dLensDirtAdd_p/v.hlsl        -- Screen-space lens dirt (modulated by bloom)
Effects/2dMoon_p/v.hlsl               -- Moon billboard
```

**WebGPU note**: D3D11 occlusion queries translate to `occlusionQuerySet`. Alternatively, read the depth buffer at the sun position via compute.

### Cloud system (9 shaders)

```
CloudsT3b_p/v.hlsl                -- Main cloud rendering (Tech3 billboards)
CloudsTech3_p/v.hlsl               -- Alternative cloud variant
CloudsTech3_Opacity_p/v.hlsl       -- Cloud opacity pass
CloudsEdgeLight_p.hlsl             -- Silver lining on cloud edges
CloudsGodLight_p.hlsl              -- God ray light shafts from clouds
CloudsGodMask_p.hlsl               -- Mask for god ray regions
```

### Screen-space reflections (5 shaders)

```
SSReflect_Deferred_p.hlsl            -- Ray march in screen space
SSReflect_Deferred_LastFrames_p.hlsl -- Temporal reprojection (fill gaps)
SSReflect_Forward_p.hlsl             -- Forward path variant
SSReflect_Forward_LastFrames_p.hlsl  -- Forward temporal
SSReflect_UpSample_p.hlsl            -- Half-res to full-res upscale
```

### Ice effects (7 shaders)

```
Tech3/Ice_p/v.hlsl                    -- Ice surface (refraction + blue tint)
Tech3/IceWall_DefWrite_p/v.hlsl       -- Ice wall G-buffer
Tech3/IceWall_p/v.hlsl                -- Ice wall forward
Tech3/IcePathBorder_p/v.hlsl          -- Ice path border (transition)
Tech3/Block_Ice_p/v.hlsl              -- Ice block variant
Tech3/VoxelIce_DefWrite_p/v.hlsl      -- Voxel ice G-buffer
Tech3/VoxelIce_p/v.hlsl               -- Voxel ice forward
```

### Energy / shield effects (11 shaders)

```
Effects/Energy/EnergyAnalytic_p/v.hlsl   -- Analytic energy field
Effects/Energy/EnergyGeom_g/p/v.hlsl     -- Energy geometry (uses GS!)
Tech3/SphereShield_p/v.hlsl              -- Sphere shield
Tech3/SphereShieldOpaque_p/v.hlsl        -- Opaque sphere shield
Tech3/BodyAnim_Energy_p/v.hlsl           -- Energy body animation
Tech3/BodyAnim_Shield_p/v.hlsl           -- Shield body animation
Tech3/Tech3VehicleShield_p.hlsl          -- Vehicle shield
```

Primarily ShootMania effects; in Trackmania they appear as item energy gates.

---

## Shader count summary

| Category | Pixel | Vertex | Compute | Geometry | Hull | Domain | Text PS | Text VS | **Total** |
|----------|-------|--------|---------|----------|------|--------|---------|---------|-----------|
| Tech3 | 263 | 216 | 7 | 0 | 3 | 3 | 0 | 0 | **533** |
| Engines | 105 | 62 | 47 | 1 | 0 | 0 | 9 | 8 | **218** |
| Effects | 93 | 30 | 26 | 2 | 0 | 0 | 12 | 9 | **154** |
| Lightmap | 38 | 13 | 16 | 0 | 0 | 0 | 2 | 2 | **78** |
| Painter | 10 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | **16** |
| Menu | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | **16** |
| Others | 40 | 28 | 2 | 0 | 0 | 0 | 20 | 18 | **97** |
| **Total** | **515** | **388** | **105** | **5** | **4** | **4** | **51** | **40** | **1,112** |

Unique shader programs (combining `_p` + `_v` pairs): approximately **580**.

For WebGPU recreation, these collapse to approximately **35-40 uber-shader modules** due to the variant explosion pattern of the Tech3 framework.

---

## Related Pages

- [11-rendering-deep-dive.md](11-rendering-deep-dive.md) -- Full rendering pipeline documentation with pass-by-pass breakdown.
- [15-ghidra-research-findings.md](15-ghidra-research-findings.md) -- Ghidra decompilation findings referenced by shader addresses.
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Browser recreation architecture using these shaders.
- [02-class-hierarchy.md](02-class-hierarchy.md) -- RTTI class hierarchy including CPlugShader classes.

<details><summary>Analysis metadata</summary>

**Source**: `GpuCache_D3D11_SM5.zip` (16 MB, 1,113 compiled HLSL shaders)
**Date**: 2026-03-27
**Purpose**: Complete shader inventory for WebGPU recreation of the rendering pipeline
**Cross-references**: [11-rendering-deep-dive.md](11-rendering-deep-dive.md), [15-ghidra-research-findings.md](15-ghidra-research-findings.md)

</details>

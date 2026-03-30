# Trackmania.exe Rendering & Graphics Pipeline

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
**Related decompiled code**: `decompiled/rendering/`

---

## 1. Graphics API

### Direct3D 11 (Primary and Only Active API)

Trackmania 2020 uses **Direct3D 11** exclusively for rendering.

**Imports**:
| Import | DLL | Address |
|--------|-----|---------|
| `D3D11CreateDevice` | `D3D11.DLL` | `EXTERNAL:0000000e` |
| `CreateDXGIFactory1` | `DXGI.DLL` | `EXTERNAL:0000000f` |

- **No D3D12 runtime imports**. Three D3D12-related strings exist (`NPlugGpuHlsl_D3D12::NRootSign_SParam`, `NPlugGpuHlsl_D3D12::SRootSign`, `NPlugGpuHlsl_D3D12::NRootSign::EParamType`) indicating some D3D12 root signature data structures are defined in the engine for future use or cross-platform code, but D3D12 is **not used at runtime**.
- **No Vulkan imports**. A single string `"Vulkan"` exists at `0x141c099e8`, likely an enum label in rendering API selection UI (no code references it). No `vulkan-1.dll` or `vk*` API calls.
- The engine has a `"RenderingApi"` configuration field (member `m_RenderingApi` at offset `0xb0` in `CSystemConfigDisplay`), suggesting the architecture was designed for multiple backends, but only D3D11 is active.

### D3D11 Device Creation

The D3D11 device is created in `FUN_1409aa750` (labeled internally as `CDx11Viewport::DeviceCreate`):

- Calls `D3D11CreateDevice` with feature level checks
- Checks for feature level `0xb000` (11.0) and `0xa100` (10.1)
- Sets `DAT_14201d2ec` to `0x400` (shader model 4.0) or `0x500` (shader model 5.0) based on feature level
- Queries `D3D11_FEATURE_DATA_D3D11_OPTIONS` via `CheckFeatureSupport`
- Detects MSAA sample count support (1, 2, 4, 8 samples)
- Handles device lost (`DeviceRemoved`) gracefully

Key string references in device init:
- `"[Dx11] D3D11CreateDevice() failed: %s"` -- error logging
- `"[D3D11] D3D11Device references still present ("` -- leak detection at shutdown
- `"[D3D11] Failed to create D3D11_QUERY_TIMESTAMP_DISJOINT !!"` -- GPU timer queries
- `"[Dx11] DeviceRemoved in D3D11SwapChain::ResizeBuffers()"` -- device lost handling
- `"D3D11 SetFullscreenState(True)"` -- fullscreen transitions

**Decompiled**: `decompiled/rendering/CDx11Viewport_DeviceCreate_1409aa750.c`

---

## 2. Rendering Pipeline Architecture

### Deferred Rendering (Primary Path)

Trackmania 2020 uses a **deferred shading** pipeline as its primary rendering path. Evidence:

The string `"Current shading pipeline, if true Antialias_Deferred setting is used, otherwise it is Antialias_Forward."` confirms the engine supports both deferred and forward, with deferred as the default for the main scene.

The configuration field `"IsDeferred"` (at `0x141cc3e88`) controls the pipeline selection. Two separate antialiasing settings exist:
- `"Antialias_Deferred"` -- FXAA or TXAA when in deferred mode
- `"Antialias_Forward"` -- MSAA (2/4/6/8/16 samples) when in forward mode

### G-Buffer Layout

The deferred pipeline writes multiple render targets. Identified G-buffer components:

| Buffer | String Reference | Notes |
|--------|-----------------|-------|
| Diffuse | `"DeferredMDiffuse"`, `"BitmapDeferredMDiffuse"` | Material diffuse color |
| Specular | `"DeferredMSpecular"`, `"BitmapDeferredMSpecular"` | Material specular |
| Face Normal | `"DeferredPixelNormalInC"`, `"BitmapDeferredFaceNormalInC"` | Face normals in camera space |
| Vertex Normal | `"BitmapDeferredVertexNormalInC"` | Vertex normals |
| Pixel Normal | `"BitmapDeferredPixelNormalInC"` | Per-pixel normals (bump-mapped) |
| Depth | `"BitmapDeferredZ"`, `"DeferredDepth"` | Depth buffer |
| PreShade | `"BitmapDeferredPreShade"` | [UNKNOWN] pre-shading buffer |
| Light Mask | `"BitmapDeferredLightMask"`, `"DeferredLightMask"` | Light contribution mask |
| Diffuse Ambient | `"Bitmap_DeferredDiffuseAmbient"`, `"DeferredDiffuseAmb"` | Combined diffuse + ambient |

Key HLSL shaders for G-buffer:
- `Tech3/Block_TDSN_DefWrite_p.hlsl` / `_v.hlsl` -- Block geometry deferred write (Texture, Diffuse, Specular, Normal)
- `Tech3/CarSkin_DefWrite_p.hlsl` -- Car skin deferred write
- `Tech3/Trees/Tree_SelfAO_DefWrite_p.hlsl` -- Tree deferred write with self-AO
- `Tech3/DeferredDecalGeom_p.hlsl` -- Deferred decal geometry
- Various `Tech3/Block_DefReadP1_*.hlsl` -- Deferred read pass 1

### Deferred Lighting

- `Tech3/DeferredGeomLightBall_p.hlsl` -- Point light geometry
- `Tech3/DeferredGeomLightSpot_p.hlsl` -- Spot light geometry
- `Tech3/DeferredGeomLightFxSphere_p.hlsl` -- Sphere light FX
- `Tech3/DeferredGeomLightFxCylinder_p.hlsl` -- Cylinder light FX
- `Tech3/Deferred_SetILightDir_p.hlsl` -- Set indirect light direction
- `Tech3/Deferred_AddAmbient_Fresnel_p.hlsl` -- Add ambient with Fresnel
- `Tech3/Deferred_AddLightLm_p.hlsl` -- Add lightmap lighting
- `Tech3/Deferred_SetLDirFromMask_p.hlsl` -- Set light direction from mask

---

## 3. Full Render Pass Order

The engine uses a hierarchical render pass system. Pass ordering is encoded in `"Down3x3"` / `"Down2x2"` dependency strings. Reconstructed full pipeline order:

### Early Passes
```
SetCst_Frame
  -> SetCst_Zone
    -> GenAutoMipMap
      -> ShadowCreateVolumes
        -> ShadowRenderCaster
          -> ShadowRenderPSSM
            -> ShadowCacheUpdate
              -> CreateProjectors
                -> UpdateTexture
                  -> Decal3dDiscard
                    -> ParticlesUpdateEmitters
                      -> ParticlesUpdate
```

### Geometry / Scene Setup
```
ParticlesUpdate
  -> CubeReflect
    -> TexOverlay
      -> LightFromMap
        -> VertexAnim
          -> Hemisphere
            -> LightOcc
              -> WaterReflect
                -> Underlays
```

### Deferred Geometry Write (G-Buffer Fill)
```
Underlays
  -> DipCulling
    -> DeferredWrite
      -> DeferredWriteFNormal
        -> DeferredWriteVNormal
          -> DeferredDecals
            -> DeferredBurn
              -> DeferredShadow
                -> DeferredAmbientOcc
```

### Deferred Read / Lighting
```
DeferredAmbientOcc
  -> DeferredFakeOcc
    -> CameraMotion
      -> DeferredRead
        -> DeferredReadFull
          -> DeferredLighting
            -> Reflects_CullObjects
```

### Forward / Transparent
```
DeferredLighting
  -> ... (forward geometry)
    -> ShadowRender
      -> CustomAfterDecals
        -> Alpha01 (alpha-tested)
```

### Effects / Vegetation
```
ForestRender -> ForestRender_MSAA -> GrassUpdateInstances -> GrassRender
ParticleSelfShadow_ComputeBBoxes -> ... -> ParticleSelfShadow_Propagation
VolumetricFog_ComputeScattering -> VolumetricFog_IntegrateScattering -> VolumetricFog_ApplyFog
```

### Particles / Transparency
```
VortexParticle -> VortexParticle_UpScale
ParticlesRender -> ParticlesRenderRefract -> ParticlesRender_UpScale
AlphaBlend -> AlphaBlendSoap -> BufferRefract
GhostLayer -> GhostLayerBlend
```

### Post-Processing Chain
```
DeferredFogVolumes -> DeferredFog
  -> LensFlares
    -> FxDepthOfField
      -> FxMotionBlur
        -> FxBlur
          -> FxColors
            -> FxColorGrading
              -> FxExtraOutput
                -> Overlays -> GUI -> StretchRect
```

### Tone Mapping / Bloom / AA (inserted in post chain)
```
FxFXAA -> FxToneMap -> FxBloom -> CustomEnding
```

### Final Output
```
ResolveMsaaHdr -> ResolveMsaa -> StretchRect
  -> BlurAA -> DownSSAA
    -> SwapChainPresent
```

---

## 4. The CDx11* Wrapper Layer

The engine wraps Direct3D 11 through a `CDx11*` class hierarchy. Classes are identified from string references (not debug symbols):

| Class | Evidence | Purpose |
|-------|----------|---------|
| `CDx11Viewport` | `"CDx11Viewport::DeviceCreate"` | Manages D3D11 device, swap chain, fullscreen state |
| `CDx11RenderContext` | `"CDx11RenderContext::CopyFromStagingBuffer"` | Wraps `ID3D11DeviceContext`, draw calls, resource management |
| `CDx11Texture` | `"[Dx11] Failed to create Texture..."`, `"D3D11Device::CreateTexture"` | Texture creation/management |
| [UNKNOWN] CDx11Shader | `"[Dx11] ComputeShaders_Plus_RawAndStructuredBuffers_Via_Shader_4_x"` | Shader compilation/management (class name unconfirmed) |
| [UNKNOWN] CDx11Device | Inferred from pattern | [UNKNOWN] whether separate from CDx11Viewport |

Key D3D11 operations logged:
- `"D3D11DeviceContext::Flush"` -- context flush
- `"D3D11::UpdateSubresource"` -- resource updates
- `"D3D11::CopyResource"` -- resource copies
- `"D3D11::Map"` / `"D3D11::Unmap"` -- buffer mapping
- `"GpuCache_D3D11"` -- GPU-side caching layer

The `CDx11Viewport::DeviceCreate` function at `0x1409aa750` is the main initialization point. It:
1. Creates the DXGI factory via `CreateDXGIFactory1`
2. Enumerates adapters
3. Calls `D3D11CreateDevice` with feature level negotiation
4. Sets up the swap chain
5. Queries MSAA support
6. Initializes shader model capabilities

---

## 5. Vision Engine Subsystem (CVision*)

The rendering engine is called **Vision** (likely Nadeo's custom engine, evolved from their earlier tech). Key classes:

### CVisionViewport

The central rendering orchestrator. Identified methods from string references:

| Method | Address (of referencing function) | Purpose |
|--------|----------------------------------|---------|
| `CVisionViewport::VisibleZonePrepareShadowAndProjectors` | `0x14095d430` | Shadow preparation per visible zone |
| `CVisionViewport::Shadow_UpdateGroups` | `0x140a43610` | Shadow group management |
| `CVisionViewport::Shadow_RenderDelayed` | referenced | Delayed shadow rendering |
| `CVisionViewport::Shadow_BlendReceivers` | mangled symbol | Shadow blending on receivers |
| `CVisionViewport::AllShaderBindTextures` | `0x14097ed30` | Bind all shader textures |
| `CVisionViewport::OnDebugValueChanged_ReCompileShaders` | referenced | Runtime shader recompilation |
| `CVisionViewport::StdShaderLoad` | referenced | Standard shader loading |

The viewport manages the render context through `CVisionRenderContext` (seen in mangled C++ symbols in the namespace list).

### CVisionShader / CVisionResourceShaders

- `"Vision::VisionShader_GetOrCreate"` at `0x14097cfb0` -- Shader creation/caching
- `"CVisionResourceShaders"` -- Resource management for shaders
- `"Retrieving VisionShader with removed device: even ShaderZOnly is not valid !!"` -- Device loss handling

### NVis Namespace

Low-level Vision rendering utilities:

| Symbol | Purpose |
|--------|---------|
| `NVis::RenderTargetLastResolveAA` | MSAA resolve |
| `NVis::SGpuIntersectTriangles` | GPU triangle intersection |
| `NVis::SGpuTransformVertices_SM3` | SM3.0 vertex transform |
| `NVis::SGpuTransformVertices_SM4` | SM4.0 vertex transform |
| `NVisionResourceFile::UDepthUp::SGpu` | Depth upsampling GPU resource |
| `NVisionMgrParticle::MgrParticle_Render` | Particle rendering manager |

**Decompiled**: `decompiled/rendering/Vision_VisionShader_GetOrCreate_14097cfb0.c`

---

## 6. Shader System

### Architecture

Shaders are pre-compiled into binary packages loaded at runtime:

- `"Shaders\\"` -- shader binary directory
- `"Shaders binary loaded from \"%s\""` -- binary loading log
- `"Shaders binary link error: %s"` -- link-time errors
- `"Shader binary is not up to date (GitHash): %016I64x != %016I64x"` -- version validation via git hash
- `"Shader binary is not up to date (GitVersion): %u < %u"` -- version check

### Shader Types

All five D3D11 shader stages are used:
- `"VertexShader"` -- Vertex shaders
- `"HullShader"` -- Hull shaders (tessellation)
- `"DomainShader"` -- Domain shaders (tessellation)
- `"GeometryShader"` -- Geometry shaders
- `"PixelShader"` -- Pixel shaders
- Compute shaders are also used extensively (`.hlsl` files ending in `_c.hlsl`)

### Shader Quality Levels

The `"ShaderQuality"` setting has these levels (from `CSystemConfigDisplay::EShaderQ`):
- `"Very Fast"` -- Lowest quality
- `"Fast"` -- Low quality
- `"Nice"` -- Medium quality
- `"Very Nice"` -- Highest quality

### CPlugShader Class Hierarchy

| Class | Purpose |
|-------|---------|
| `CPlugShader` | Base shader class |
| `CPlugShaderApply` | Applied shader instance |
| `CPlugShaderPass` | Single render pass within a shader |
| `CPlugShaderGeneric` | Generic/configurable shader |
| `CPlugShaderCBufferStatic` | Static constant buffer |
| `CPlugBitmapShader` | Bitmap/texture shader |
| `CPlugAdnShader_Skin` | Character skin shader |
| `CPlugAdnShader_Part` | Character part shader |
| `CFuncShader` / `CFuncShaders` / `CFuncShaderLayerUV` | Shader function layers |

### HLSL Shader File Organization

Shaders are organized into directories by purpose:

| Directory | Count (approx) | Purpose |
|-----------|----------------|---------|
| `Tech3/Block_*` | ~60+ | Block/terrain geometry rendering |
| `Tech3/Deferred*` | ~25+ | Deferred pipeline passes |
| `Tech3/Car*` | ~12 | Car rendering (skin, details, ghost, glass) |
| `Tech3/Trees/*` | ~15 | Tree/vegetation rendering |
| `Tech3/Sea_*` | ~4 | Sea/water surface |
| `Tech3/BodyAnim_*` | ~12 | Character body animation |
| `Effects/PostFx/*` | ~20+ | Post-processing effects |
| `Effects/Particles/*` | ~20+ | Particle system shaders |
| `Effects/Fog/*` | ~8 | Volumetric fog |
| `Engines/*` | ~60+ | Low-level engine utilities |
| `Lightmap/*` | ~30+ | Lightmap computation and sampling |
| `Effects/Particles/SelfShadow/*` | ~6 | Particle self-shadowing |
| `Effects/Particles/CameraWaterDroplets/*` | ~5 | Camera water droplet effect |
| `Effects/Particles/VortexSimulation/*` | ~3 | Vortex particle simulation |
| `Garage/*` | ~3 | Garage/menu plane reflections |
| `Painter/*` | ~8 | Skin/livery painter |
| `Bench/*` | ~5 | GPU benchmark shaders |
| `Clouds/*` | ~3 | Cloud/sky rendering |

### "Tech3" Naming Convention

The dominant shader prefix `"Tech3/"` refers to Nadeo's third-generation rendering technology. The `"T3"` prefix appears in many internal names:
- `"T3Bloom"`, `"T3ToneMap"` -- Post-processing
- `"T3HdrScales_Block_Particle_Player"` -- HDR scaling
- `"Tech3ToneMapAutoExp"` -- Auto-exposure tone mapping

The block material shaders follow a naming convention:
- `TDSN` = Texture + Diffuse + Specular + Normal
- `Py` / `Pxz` = [UNKNOWN] likely projection modes (Y-axis / XZ-plane)
- `DefWrite` / `DefRead` = Deferred write (G-buffer fill) / Deferred read (lighting)
- `COut` / `CIn` = Color output / Color input
- `SI` = Self-illumination
- `LM0` / `LM1` / `LM2` = Lightmap variants

---

## 7. Post-Processing Effects

### HBAO+ (Horizon-Based Ambient Occlusion)

Nadeo implements **NVIDIA HBAO+** as a full post-processing pass, with an alternative homemade fallback:

**Configuration** (from `NSysCfgVision::SSSAmbOcc` struct, registered at `0x14091f4e0`):

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `IsEnabled` | `0x00` | bool | Master AO enable |
| `UseHomeMadeHBAO` | `0x04` | bool | Use Nadeo's custom AO instead of NVIDIA |
| `DelayGrassFences` | `0x08` | bool | [UNKNOWN] |
| `ImageSize` | `0x0C` | int2 | AO render resolution |
| `WorldSize` | `0x10` | float | AO world-space radius |
| `Exponent` | `0x14` | float | AO exponent |
| `BlurTexelCount` | `0x18` | int | Blur kernel size |
| `NvHBAO.Enabled` | `0x1C` | bool | NVIDIA HBAO+ enable |
| `NvHBAO.Radius` | `0x20` | float | HBAO+ radius |
| `NvHBAO.Bias` | `0x24` | float | HBAO+ bias |
| `NvHBAO.LargeScaleAO` | `0x28` | float | Large-scale AO factor |
| `NvHBAO.SmallScaleAO` | `0x2C` | float | Small-scale AO factor |
| `NvHBAO.PowerExponent` | `0x30` | float | Power exponent |
| `NvHBAO_BigScale.Enabled` | `0x34` | bool | Big-scale pass enable |
| `NvHBAO_BigScale.Radius` | `0x38` | float | Big-scale radius |
| `NvHBAO_BigScale.Bias` | `0x3C` | float | Big-scale bias |
| `NvHBAO_BigScale.LargeScaleAO` | `0x40` | float | Big-scale large-scale factor |
| `NvHBAO_BigScale.SmallScaleAO` | `0x44` | float | Big-scale small-scale factor |
| `NvHBAO_BigScale.PowerExponent` | `0x48` | float | Big-scale power exponent |

HBAO+ shader files:
- `Effects/PostFx/HBAO_plus/DeinterleaveDepth_p.hlsl`
- `Effects/PostFx/HBAO_plus/ReconstructNormal_p.hlsl`
- `Effects/PostFx/HBAO_plus/LinearizeDepth_p.hlsl`
- `Effects/PostFx/HBAO_plus/CoarseAO_p.hlsl` / `_g.hlsl`
- `Effects/PostFx/HBAO_plus/BlurX_p.hlsl` / `BlurY_p.hlsl`
- `Effects/PostFx/HBAO_plus/ReinterleaveAO_p.hlsl`
- `Effects/PostFx/HBAO_plus/FullScreenTriangle_v.hlsl`

**Decompiled**: `decompiled/rendering/NSysCfgVision_SSSAmbOcc_HBAO_14091f4e0.c`

### Bloom HDR

Class `CVisPostFx_BloomHdr` (registered at `0x140053470`, class ID `0xC032000`, size `0x168` bytes, constructor `FUN_1409a45a0`).

Quality levels (`CSystemConfigDisplay::EFxBloomHdr`):
- `None`
- `Medium`
- `High`

Bloom shaders:
- `Effects/PostFx/BloomSelectFilterDown2_p.hlsl` -- Downsample 2x filter
- `Effects/PostFx/BloomSelectFilterDown4_p.hlsl` -- Downsample 4x filter
- `Effects/PostFx/Bloom_HorizonBlur_p.hlsl` -- Horizontal blur pass
- `Effects/PostFx/Bloom_StreaksWorkDir_p.hlsl` -- Light streak direction
- `Effects/PostFx/Bloom_StreaksSelectSrc_p.hlsl` -- Streak source selection
- `Effects/PostFx/Bloom_Final_p.hlsl` -- Final bloom composite
- `Effects/PostFx/Bloom_EdShowBlow_p.hlsl` -- [UNKNOWN] editor blow-out preview

Configuration fields:
- `"BloomIntensUseCurve"` -- Use intensity curve
- `"MinIntensInBloomSrc"` -- Minimum intensity threshold
- `"HdrNormMaxInv_ScaleAlpha"` -- HDR normalization
- `"Bloom_Down%d"` -- Multi-level downsample targets

### Tone Mapping

Class `CVisPostFx_ToneMapping` (registered at `0x140053250`, class ID `0xC030000`, size `0x6F0` bytes, constructor `FUN_14099dce0`).

Tone mapping shaders:
- `Effects/PostFx/TM_GetLumi_p.hlsl` -- Luminance extraction
- `Effects/PostFx/TM_GetLog2LumiDown1_p.hlsl` / `_v.hlsl` -- Log2 luminance downsample
- `Effects/PostFx/TM_GetAvgLumiCurr_p.hlsl` -- Average luminance (current frame)
- `Effects/PostFx/TM_GetAvgLumiCurr_VeryFast_p.hlsl` -- Fast average luminance
- `Effects/PostFx/TM_GetLdrALogFromCopyFirst_p.hlsl` -- LDR from log
- `Effects/PostFx/TM_GlobalOp_p.hlsl` -- Global tone map operator
- `Effects/PostFx/TM_GlobalOpAutoExp_p.hlsl` -- Auto-exposure global operator
- `Effects/PostFx/TM_GlobalFilmCurve_p.hlsl` -- Filmic tone curve
- `Effects/PostFx/TM_LocalOp_p.hlsl` -- Local tone map operator
- `Effects/PostFx/TM_DebugCurve_v.hlsl` -- Debug curve visualization

Features:
- `"ToneMapAutoExp_FidAvgLumiToKeyValue"` -- Auto-exposure key value mapping
- `"NFilmicTone_PowerSegments::SCurveParamsUser"` -- Filmic curve parameterization (power segment model)
- `"ToneMapExposureStaticBase"` -- Static exposure base
- `"ToneMapFilmCurve"` -- Film curve toggle
- `"HdrToneMap"` -- HDR tone map mode
- `"ToneMapAutoScale"` -- Auto-scaling

### Motion Blur

Class `CVisPostFx_MotionBlur` (registered at `0x1400532f0`).

- `Effects/MotionBlur2d_p.hlsl` -- 2D motion blur shader
- `"MotionBlur2d.Intensity01"` -- Intensity parameter (0-1)
- Quality: On / Off (`CSystemConfigDisplay::EFxMotionBlur`)
- `"FxMotionBlurIntens"` / `"m_FxMotionBlurIntens"` -- Intensity setting

### Depth of Field

- `Effects/PostFx/DoF_T3_BlurAtDepth_p.hlsl` -- DoF blur at depth
- `"FxDOF_FocalBlur_InvZ_MAD"` -- Focal blur inverse-Z multiply-add
- `"FxDOF_FocusZ01_Scale"` -- Focus Z scale (0-1 range)
- `"DofSampleCount"` -- Sample count for DoF quality
- `"VideoHqDOF"` -- High-quality DoF for video recording
- `"DofLensSize"` / `"DofFocusZ"` -- Camera lens parameters
- `"Depth_DofBlur"` -- Depth-based DoF blur pass marker

### FXAA (Fast Approximate Anti-Aliasing)

- `Effects/PostFx/FXAA_p.hlsl` -- FXAA pixel shader
- Used as `"DeferredAntialiasing| FXAA"` option in deferred mode

### TXAA (Temporal Anti-Aliasing)

- `Effects/TemporalAA/TemporalAA_p.hlsl` -- Temporal AA shader
- Referenced as `"DeferredAntialiasing| TXAA"` and `"FxTXAA"` pass name
- `"PosOffsetAA"` / `"PosOffsetAAInW"` -- Per-frame jitter offset for temporal sampling

### Color Grading & Color Correction

- `Effects/PostFx/ColorGrading_p.hlsl` -- LUT-based color grading
- `Effects/PostFx/Colors_p.hlsl` -- Color adjustments
- `Effects/PostFx/ColorBlindnessCorrection_p.hlsl` -- Accessibility color blindness filter

### Other Post-Processing

- `Effects/PostFx/BlurWeighted_p.hlsl` -- Weighted blur
- `Effects/PostFx/StereoAnaglyphHalfColor_p.hlsl` / `Linear` / `FullColor` -- Stereoscopic 3D support
- `Effects/PostFx/DebugBitmap_p.hlsl` -- Debug visualization
- `Engines/BilateralBlur_p.hlsl` -- Bilateral blur (edge-preserving)
- `Engines/BlurHV_p.hlsl` / `_DepthTest_p.hlsl` / `_DepthMask_p.hlsl` -- Horizontal/vertical blur with depth awareness

---

## 8. Shadow System

### Architecture

The shadow system is multi-layered with several techniques:

**Shadow Types:**
- **PSSM (Parallel-Split Shadow Maps)** -- Primary directional light shadows
  - `"ShadowRenderPSSM"` render pass
  - `"Tech3/DeferredShadowPssm_p.hlsl"` / `"_v.hlsl"` -- Deferred PSSM shaders
  - `"MapShadowSplit0"` through `"MapShadowSplit3"` -- 4 cascade splits
- **Shadow Volumes** -- For specific geometry
  - `"ShadowCreateVolumes"` render pass
  - `"Tech3/DeferredGeomShadowVol_p.hlsl"` / `"_v.hlsl"`
  - `"ShadowVolEnable"` / `"ShadowVolUseBestZFunc"` / `"ShadowVolShowPixelFill"`
- **Shadow Cache** -- Caching static shadows
  - `"ShadowCacheMgr"` / `"ShadowCache_Enable"` / `"SVisShadowCacheMgr"`
  - `"ShadowCache/UpdateShadowIndex_c.hlsl"` -- Compute shader for cache index updates
  - `"ShadowCacheUpdate"` render pass
- **Clip Map Shadows** -- [UNKNOWN] Possibly for large-scale terrain
  - `"ShadowClipMap_Grp%u"` / `"P3ClipMapShadowLDir0"`
- **Static Shadows** (baked)
  - `"StaticShadow0"` / `"CastStaticShadow"` / `"StaticShadowAsNat"`
- **Fake Shadows** (for performance)
  - `"ShaderGeomFakeShadows"` / `"ShaderShadowFakeQuad"` / `"FlatCubeShadow"`

**Shadow Groups** (up to 4):
- `"CastShadowGrp0"` through `"CastShadowGrp3"`
- `"RecvShadowGrp0"` through `"RecvShadowGrp3"`
- `"CHmsShadowGroup"` -- Group management class
- `"MaxShadowCountGrp0"` -- Per-group shadow limit

**Shadow Quality Settings** (`CSystemConfigDisplay::EShadows`):
- `None`
- `Minimum`
- `Medium`
- `High`
- `Very High`

**Player-Specific Shadows** (`CSystemConfig::EPlayerShadow`):
- `None`
- `Me` (only own car)
- `All` (all players)

**Shadow Configuration**:
- `"ShadowBiasConstSlope"` -- Slope-scaled depth bias
- `"ShadowCasterAlphaRef"` / `"ShadowCasterAlphaCut"` / `"ShadowCasterIgnoreAlpha"` -- Alpha test for shadow casters
- `"ShadowSoftCorners"` -- Soft shadow edges
- `"HqSoftShadows"` -- High quality soft shadows
- `"ShadowMapTexelSize"` -- Shadow map resolution control
- `"ShadowGrayShade"` -- Shadow darkness level
- `"ShadowCountCarHuman"` / `"ShadowCountCarOpponent"` -- Per-category shadow counts

**Decompiled**: `decompiled/rendering/CVisionViewport_PrepareShadowAndProjectors_14095d430.c`

---

## 9. Particle System

### GPU-Accelerated Particles

The particle system is heavily GPU-driven with compute shaders:

**Core Classes:**
| Class | Purpose |
|-------|---------|
| `CPlugParticleEmitterModel` | Particle emitter definition |
| `CPlugParticleEmitterSubModel` | Sub-emitter model |
| `CPlugParticleEmitterSubModelGpu` | GPU sub-emitter |
| `CPlugParticleGpuModel` | GPU particle model |
| `CPlugParticleGpuSpawn` | GPU spawn parameters |
| `CPlugParticleGpuVortex` | GPU vortex interaction |
| `CPlugParticleImpactModel` | Impact-spawned particles |
| `CPlugParticleMaterialImpactModel` | Material-dependent impacts |
| `CPlugParticleSplashModel` | Water splash particles |

**GPU Particle Shaders:**
- `Effects/Particles/MgrParticleUpdate_c.hlsl` -- Compute: particle state update
- `Effects/Particles/MgrParticleUpdateFromCPU_c.hlsl` -- Compute: CPU-driven update
- `Effects/Particles/MgrParticleSpawn_p.hlsl` / `_v.hlsl` -- Spawn pass
- `Effects/Particles/MgrParticleSpawnPoints_p.hlsl` / `_v.hlsl` -- Point-based spawn
- `Effects/Particles/MgrParticleRender_p.hlsl` / `_v.hlsl` -- Main render
- `Effects/Particles/MgrParticleRenderOpaques_p.hlsl` / `_v.hlsl` -- Opaque particles
- `Effects/Particles/MgrParticleRenderStatic_p.hlsl` / `_v.hlsl` -- Static particles
- `Effects/Particles/MgrParticleRenderStaticFakeOcc_p.hlsl` / `_v.hlsl` -- Static with fake occlusion
- `Effects/Particles/MgrParticleShadow_p.hlsl` / `_v.hlsl` -- Particle shadow casting
- `Effects/Particles/MgrParticleShowStates_p.hlsl` / `_v.hlsl` -- Debug state visualization
- `Effects/Particles/Particles_ComputeDepth_c.hlsl` -- Compute: depth computation
- `Effects/Particles/ParticlesToFog_c.hlsl` -- Compute: particle-to-fog interaction

**Particle Self-Shadowing Pipeline:**
1. `ParticleSelfShadow_ComputeBBoxes` -- Compute bounding boxes
2. `ParticleSelfShadow_OpaqueShadow` -- Render opaque shadow
3. `ParticleSelfShadow_Render` -- Render self-shadow
4. `ParticleSelfShadow_Merge` -- Merge results
5. `ParticleSelfShadow_Propagation` -- Propagate through volume
6. `ParticleSelfShadow_Voxelization` -- Voxelize particles

Self-shadow shaders use geometry shaders for voxelization:
- `Effects/Particles/SelfShadow/ParticleVoxelization_p.hlsl` / `_g.hlsl` / `_v.hlsl`
- `Effects/Particles/SelfShadow/ParticlePropagation_p.hlsl` / `_v.hlsl`
- `Effects/Particles/SelfShadow/ParticlesShadowOnOpaque_p.hlsl` / `_v.hlsl`

**Vortex Simulation:**
- `Effects/Particles/VortexSimulation/VortexSpawn_c.hlsl` -- Compute: spawn
- `Effects/Particles/VortexSimulation/VortexUpdate_c.hlsl` -- Compute: update
- `Effects/Particles/VortexSimulation/VortexDebugRender_p.hlsl` / `_v.hlsl` -- Debug render

**Water Effects:**
- `Effects/Particles/WaterSplash_IntersectTriangles_p.hlsl` -- Triangle intersection for splashes
- `Effects/Particles/WaterSplash_TransformVertices_p.hlsl` -- Vertex transformation
- `Effects/Particles/WaterSplash_SpawnParticles_p.hlsl` / `_v.hlsl` -- Spawn water particles
- `Effects/Particles/CameraWaterDroplets/CameraWaterDroplets_Spawn_c.hlsl` -- Screen-space water droplets
- `Effects/Particles/CameraWaterDroplets/CameraWaterDroplets_Update_c.hlsl` -- Droplet update
- `Effects/Particles/CameraWaterDroplets/CameraWaterDroplets_Render_p.hlsl` -- Droplet render

**Particle Quality** (`CSystemConfig::ETmCarParticlesQuality`):
- `"All Low"`
- `"All Medium"`
- `"All High"`
- `"High,Medium Opponents"` (high for player, medium for opponents)

**GPU Load Management:**
- `"ParticleMaxGpuLoadMs"` / `"m_ParticleMaxGpuLoadMs"` -- GPU time budget for particles
- `"TimeGpuMs_Particles"` -- GPU time measurement

---

## 10. Scene Graph (CHms* Classes)

The scene graph is built on a hierarchical system prefixed `CHms` (likely "Hierarchical Management System" or similar):

### Identified CHms Classes

| Class | Purpose |
|-------|---------|
| `CHmsShadowGroup` | Shadow group management |
| `CHmsVolumeShadow` | Volume shadow objects |
| `CHmsItemShadow` | Per-item shadow data |
| `CHmsLightMap` | Lightmap management (see `CHmsLightMap::ComputeLighting_CancelByDisablingShadows`) |
| `CHmsMgrVisParticle` | Visual particle manager (see `CHmsMgrVisParticle::MeshRegister`) |

### NHms Namespaces

| Namespace | Purpose |
|-----------|---------|
| `NHmsMgrInstDyna` | Dynamic instance manager (`AsyncRender_ApplyDeferredChanges`) |
| `NHmsMgrInstDyna2` | Second-gen dynamic instance manager |
| `NHmsMgrParticle::SMgr` | Particle manager struct |
| `NHmsLightMap` | Lightmap utilities (`YCbCr_to_RGB`) |

### Render Pass System

The `SHms*` structs define render state:
- `"SHmsFxBloomHdr"` -- Bloom HDR effect state
- `"SHmsFxToneMap"` -- Tone map effect state
- `"SHmsPostFxState"` -- Post-FX state
- `"HmsPacker::StaticOptimUpdate_ShadowCasters"` -- Static optimization for shadow casters

### Hms Configuration Output

`"[Hms] Shadows="` and `"[Hms] ShaderQuality="` -- The Hms system logs its configuration at startup.

---

## 11. Additional Rendering Features

### Volumetric Fog

Full 3D volumetric fog with ray marching:
- `Effects/Fog/3DFog_RayMarching_c.hlsl` -- Ray marching compute shader
- `Effects/Fog/3DFog_ComputeInScatteringAndDensity_c.hlsl` -- In-scattering and density
- `Effects/Fog/3DFog_BlendInCamera_p.hlsl` -- Camera-space blend
- `Effects/Fog/3DFog_UpdateNoiseTexture_c.hlsl` -- Noise texture animation
- `Effects/Fog/FogInC_Propagate_WithLuminance_c.hlsl` -- Fog propagation with luminance
- `Effects/Fog/FogInC_Compute_c.hlsl` / `_Propagate_c.hlsl` / `_Copy_c.hlsl` -- Fog grid compute
- `Effects/Fog/ComputeFogSpaceInfo_c.hlsl` -- Fog space computation
- `Effects/Fog/FogSpaceInfoRender_p.hlsl` / `_v.hlsl` -- Fog space rendering
- Render passes: `VolumetricFog_ComputeScattering` -> `VolumetricFog_IntegrateScattering` -> `VolumetricFog_ApplyFog`
- `"DeferredFog"` / `"DeferredFogVolumes"` / `"DeferredWaterFog"` passes in the deferred pipeline

### Screen-Space Reflections

- `Tech3/SSReflect_Deferred_p.hlsl` -- Deferred SSR
- `Tech3/SSReflect_Deferred_LastFrames_p.hlsl` -- Temporal SSR (uses previous frames)
- `Tech3/SSReflect_Forward_p.hlsl` / `_LastFrames_p.hlsl` -- Forward path SSR
- `Tech3/SSReflect_UpSample_p.hlsl` -- SSR upsampling
- Render pass: `SSLReflects` -> `SSLReflects_GlobalCube` -> `SSLReflects_Add`

### Lens Flares

- `Engines/LensFlareOccQuery_v.hlsl` -- Occlusion query for lens flares
- `Effects/2dFlareAdd_Hdr_p.hlsl` / `_v.hlsl` -- HDR flare compositing
- `Effects/2dLensDirtAdd_p.hlsl` / `_v.hlsl` -- Lens dirt overlay
- `CPlugFxLensFlareArray` -- Lens flare array class
- `"LensFlares"` render pass occurs after `DeferredFog`

### PBR (Physically Based Rendering)

- `Engines/Pbr_IntegrateBRDF_GGX_c.hlsl` -- GGX BRDF integration LUT
- `Engines/Pbr_PreFilterEnvMap_GGX_c.hlsl` -- Pre-filtered environment map
- `Engines/Pbr_FastFilterEnvMap_GGX_c.hlsl` -- Fast environment map filter
- `Engines/Pbr_Spec_to_Roughness_c.hlsl` -- Specular to roughness conversion
- `Engines/Pbr_RoughnessFilterNormalInMips_c.hlsl` -- Normal roughness filtering

### Lightmapping

Extensive lightmap system for static lighting:
- `Lightmap/LmLBumpILighting_Inst_p.hlsl` / `_v.hlsl` -- Bumped indirect lighting
- `Lightmap/LmLHBasisILighting_Inst_p.hlsl` -- H-basis indirect lighting
- `Lightmap/LmILightDir_AddAmbient_c.hlsl` -- Indirect light direction + ambient
- `Lightmap/LmCompress_HBasis_YCbCr4_c.hlsl` -- H-basis YCbCr4 compression
- `Lightmap/ProbeGrid_Sample_c.hlsl` -- Light probe grid sampling
- `Lightmap/ProbeGrid_LightAcc_p.hlsl` -- Probe grid light accumulation

### Instancing and Culling

- `Engines/Instances_Cull_SetLOD_c.hlsl` -- Compute: GPU frustum culling with LOD
- `Engines/Instances_Merge_c.hlsl` -- Instance merging
- `Engines/IndexedInst_SetDrawArgs_LOD_SGs_c.hlsl` -- Indirect draw argument setup
- `Engines/ForwardTileCull_c.hlsl` -- Forward+ tile-based light culling
- `"DipCulling"` render pass -- Draw-indexed-primitive culling

### GPU Sorting

- `Effects/SortLib/Sort_c.hlsl` -- GPU sort compute shader
- `Effects/SortLib/SortInner_c.hlsl` -- Inner sort kernel
- `Effects/SortLib/SortStep_c.hlsl` -- Sort step
- `Effects/SortLib/InitSortArgs_c.hlsl` -- Sort argument initialization
- Render passes: `GpuSort_SendData` -> `GpuSort_Dispatch` -> `GpuSort_RetrieveData`
- Used for particle depth sorting (`ParticleSort_PrePass` -> `ParticleSort_Sort`)

### Sub-Surface Scattering

- `Effects/SubSurface/SeparableSSS_p.hlsl` -- Separable SSS (Jorge Jimenez technique)

### Signed Distance Fields

- `Effects/SignedDistanceField/SignedDistanceField_Render_p.hlsl` / `_v.hlsl`
- `Effects/SignedDistanceField/SignedDistanceField_BruteForce_c.hlsl`
- `Effects/SignedDistanceField/SignedDistanceField_Analytic_c.hlsl`

---

## 12. Display Configuration (CSystemConfigDisplay)

The `CSystemConfigDisplay` class (registered at `0x140936810`, class ID `0xB013000`, size `0x160` bytes) contains all rendering settings:

| Field | Offset | Type | Description |
|-------|--------|------|-------------|
| `m_AdapterDesc` | `0x20` | string | GPU adapter description |
| `m_ScreenSizeFS` | `0x40` | int2 | Fullscreen resolution |
| `m_ScreenSizeWin` | `0x48` | int2 | Windowed resolution |
| `m_Antialiasing` | `0x4C` | enum | Forward AA (MSAA samples) |
| `m_DeferredAA` | `0x50` | enum | Deferred AA (None/FXAA/TXAA) |
| `m_RefreshRate` | `0x54` | int | Refresh rate |
| `m_DisplaySync` | `0x58` | enum | VSync mode |
| `m_DisplayMode` | `0x5C` | enum | Display mode |
| `m_StereoscopyByDefault` | `0x60` | bool | Stereo 3D default |
| `m_StereoscopyAdvanced` | `0x64` | bool | Advanced stereo settings |
| `m_TripleBuffer` | `0x68` | enum | Triple buffering |
| `m_AllowVRR` | `0x74` | bool | Variable refresh rate |
| `m_ShowPerformance` | `0x78` | enum | Performance display |
| `m_Customize` | `0x7C` | bool | Custom settings enabled |
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

**Decompiled**: `decompiled/rendering/CSystemConfigDisplay_140936810.c`

---

## 13. Key Addresses

| Address | Function/Data | Description |
|---------|---------------|-------------|
| `0x1409aa750` | `CDx11Viewport::DeviceCreate` | D3D11 device + swap chain creation |
| `0x14093d2d0` | [UNKNOWN] | d3d11.dll loading and initialization |
| `0x14091f4e0` | `NSysCfgVision::SSSAmbOcc` registration | HBAO+ configuration setup |
| `0x140053470` | `CVisPostFx_BloomHdr` class registration | Bloom HDR class init |
| `0x140053250` | `CVisPostFx_ToneMapping` class registration | Tone mapping class init |
| `0x1400532f0` | `CVisPostFx_MotionBlur` class registration | Motion blur class init |
| `0x14095d430` | `CVisionViewport::VisibleZonePrepareShadowAndProjectors` | Shadow preparation |
| `0x140a43610` | `CVisionViewport::Shadow_UpdateGroups` | Shadow group update |
| `0x14097ed30` | `CVisionViewport::AllShaderBindTextures` | Shader texture binding |
| `0x14097cfb0` | `Vision::VisionShader_GetOrCreate` | Shader cache/creation |
| `0x140a24ac0` | `MgrParticle_Update` | GPU particle update |
| `0x140936810` | `CSystemConfigDisplay` registration | Display settings class |
| `0x1409d2310` | [UNKNOWN] | Shadow/rendering quality setup (references Shadows, ShaderQuality) |
| `0x142057f98` | [UNKNOWN] global | DXGI adapter info [UNKNOWN exact contents] |
| `0x142057f90` | [UNKNOWN] global | Vendor ID (value `0x8086` = Intel detected in code) |

---

## 14. Unknowns and Open Questions

- **[UNKNOWN]** The exact CDx11Device class -- whether it exists separately from CDx11Viewport or if the viewport encapsulates device management directly.
- **[UNKNOWN]** Full G-buffer format (DXGI_FORMAT for each render target). The buffer names are known but pixel formats would require tracing texture creation calls.
- **[UNKNOWN]** The `"PreShade"` deferred buffer purpose.
- **[UNKNOWN]** Whether the forward rendering path is used for any main scene geometry or only for UI/transparent objects.
- **[UNKNOWN]** The `".A2U"` and `".D."` non-standard code sections' relationship to rendering code -- whether rendering code lives there or only in `.text`.
- **[UNKNOWN]** The `"UseHomeMadeHBAO"` implementation details -- how the custom AO differs from NVIDIA HBAO+.
- **[UNKNOWN]** The `"Py"` and `"Pxz"` prefixes in shader naming (possibly projection-axis variants for triplanar mapping).
- **[UNKNOWN]** Complete `CVisionViewport` struct layout and vtable.
- **[UNKNOWN]** Whether `"FClusterShadows"` refers to clustered shadow rendering or some other technique.
- **[UNKNOWN]** The `"Dxgi_Present_HookCallback"` export at `0x140a811a0` -- whether this is for internal overlay or external tool integration.
- **[UNKNOWN]** The `"11_1_SHADER_EXTENSIONS"` and `"VIEWPORT_AND_RT_ARRAY_INDEX_FROM_ANY_SHADER_FEEDING_RASTERIZER"` feature flags -- which D3D 11.1+ features are actually used.

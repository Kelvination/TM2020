# Ghidra Research Findings

Ghidra analysis of Trackmania.exe revealed detailed internals for 10 subsystems. Key discoveries include the full deferred rendering pipeline (19 passes), OpenAL audio initialization with XOR-obfuscated function pointers, all ManiaScript token types, and the dual zlib/LZO compression story.

Findings come from both the automated Ghidra agent and manual queries via `bridge_query.py`.

## Audio: OpenAL Initialization

The game uses OpenAL (via `OpenAL64_bundled.dll`) for all spatial audio.

`COalAudioPort::InitImplem` at `0x14138c090` runs this sequence:

1. Dynamically loads OpenAL DLL via `LoadLibrary`
2. Resolves function pointers: `alcOpenDevice`, `alcGetProcAddress`, `alcGetError`, `alcIsExtensionPresent`
3. Attempts named audio device, falls back to default
4. Creates ALC context
5. Queries ALC version (1.x)
6. Queries mono/stereo source counts
7. Checks for EFX (Environmental effects) support
8. Logs: `"[Audio] Initialized, using device '<name>', sources = N+M, EFX enabled/disabled"`

Function pointers at +0x298 and +0x2B1 are XOR/ADD obfuscated as an anti-tamper measure.

**COalAudioPort struct offsets**:
| Offset | Type | Description |
|--------|------|-------------|
| +0x298 | ptr | `alcOpenDevice` (XOR obfuscated) |
| +0x2A0 | ptr | `alcCloseDevice` |
| +0x2A8 | ptr | `alcGetProcAddress` |
| +0x2B1 | ptr | `alcGetError` (XOR obfuscated) |
| +0x2C8 | ptr | OpenAL DLL handle |
| +0x2D9 | str | Device name |
| +0x31D | byte | Initialized flag |
| +0x321 | ptr | ALC device handle |
| +0x338 | lock | Mutex |

**ALC constants used**: 0x1000 (MAJOR_VERSION), 0x1001 (MINOR_VERSION), 0x1005 (DEFAULT_DEVICE_SPECIFIER), 0x1010 (MONO_SOURCES), 0x1011 (STEREO_SOURCES)

Confidence: VERIFIED

## Input: Per-Frame Update

`CInputPort::Update_StartFrame` (`0x1402acea0`) processes input each frame. It reads a global tick counter, checks a 150ms device connectivity timeout, processes the input event queue, calls virtual methods for per-device updates, then clears the queue.

**CInputPort struct offsets**:
| Offset | Type | Description |
|--------|------|-------------|
| +0x18 | bool | Keyboard connected |
| +0x1C | bool | Mouse connected |
| +0x1A8 | ptr | Device array pointer |
| +0x1B0 | u32 | Device count |
| +0x7DC | buf | Input state output |
| +0x12AC | buf | Input event buffer |
| +0x17EC | u32 | Last activity timestamp |
| +0x17F4 | u32 | Frame input flags |

Event types 0xC and 0x5 set activity flags. Virtual method offsets: +0x120 (device state change), +0x128 (per-device update), +0x1A8 (main polling).

Confidence: VERIFIED

## Camera: 12 Controller Classes

`NGameCamera::SCamSys` allocates **0x6C0 = 1728 bytes** per instance. Twelve camera controller classes were found:

| Class | Description |
|-------|-------------|
| `CGameControlCameraTrackManiaRace` | Primary race camera (3rd person) |
| `CGameControlCameraTrackManiaRace2` | Alternative race camera |
| `CGameControlCameraTrackManiaRace3` | Third race camera variant |
| `CGameControlCameraFirstPerson` | First-person view |
| `CGameControlCameraFree` | Free camera |
| `CGameControlCameraOrbital3d` | Orbital camera |
| `CGameControlCameraEditorOrbital` | Editor orbital |
| `CGameControlCameraHelico` | Helicopter-style |
| `CGameControlCameraVehicleInternal` | Internal vehicle view |
| `CGameControlCameraHmdExternal` | VR headset external |
| `CGameControlCameraTarget` | Target-following |
| `CGameControlCameraEffectShake` | Camera shake |

Camera model files loaded from `.gbx`: `VehicleCameraRace2Model.gbx`, `VehicleCameraRace3Model.gbx`, `VehicleCameraInternalModel.gbx`, `VehicleCameraHelicoModel.gbx`, `VehicleCameraHmdExternalModel.gbx`.

Spectator camera types (from ForceSpectator XML-RPC): 0=replay, 1=follow, 2=free. Audio-camera coupling uses `CameraWooshVolumedB` and `CameraWooshMinSpeedKmh`.

Confidence: VERIFIED

## Compression: zlib Present, GBX Body Uses LZO1X

zlib strings appear in the binary. LZO does not appear as a string -- but LZO1X is the actual GBX body compressor.

**zlib**: CONFIRMED present in binary strings
- `0x14199b2b8`: `"zlib compression"`
- `0x141b36c10`: `" unzip 1.01 Copyright 1998-2004 Gilles Vollant - http://www.winimage.com/zLibDll"`
- `0x141be0f40`: `"zlib corrupt"`
- `0x141be0ff0`: `"bad zlib header"`

**LZO**: NOT FOUND as a string (0 matches)

**CORRECTION (from docs 16, 26, 29)**: The original conclusion that "TM2020 uses zlib exclusively for GBX body compression" was **incorrect**. Real file analysis (doc 26) confirmed GBX body compression uses **LZO1X**, not zlib:
- Compressed data in real .Map.Gbx and .Profile.Gbx files fails zlib/deflate decompression
- Byte patterns match LZO1X encoding (first byte encodes literal run length)
- Community tools (GBX.NET, pygbx) all use LZO for GBX body decompression
- The decompression function `FUN_140127aa0` implements LZO1X (no "LZO" string because the algorithm is compiled in, not linked as a named library)

**Both are present**: zlib strings exist for **other purposes** (likely lightmap compression, ghost data, or internal data streams per doc 29 Section 2.6). LZO1X handles GBX body compression but has no string signature.

Confidence: PARTIALLY CORRECTED

## Gravity: Normalized 0-1 Coefficient with 250ms Delay

GravityCoef is a normalized value (0 to 1), not a physical m/s^2 value. Setting gravity has a 250ms smoothed transition. The GravityCoef API is deprecated in favor of `SetPlayer_Delayed_AccelCoef`.

**Gravity-related strings found**:

| Address | String | Purpose |
|---------|--------|---------|
| `0x141bb3e18` | `"GravityCoef"` | Gravity coefficient parameter |
| `0x141bb6a60` | `"Gravity"` | Base gravity reference |
| `0x141bbc740` | `"TechGravityChange"` | Gameplay surface: gravity modifier |
| `0x141bbc820` | `"TechGravityReset"` | Gameplay surface: gravity reset |
| `0x141bd5af8` | `"Modifiers.GravityCoef"` | Modifier system gravity |
| `0x141bd7588` | `"DefaultGravitySpawn"` | Default gravity at spawn |
| `0x141cf26b0` | `"Changes player's vehicle gravity coef with a 250ms delay"` | API description |
| `0x141cf3bb0` | `"SetPlayer_Delayed_GravityCoef"` | ManiaScript function |
| `0x141cf4eb8` | `"GravityCoef has to be between 0 and 1"` | Validation string |
| `0x141cf6890` | `"This way of setting GravityCoef is deprecated, please use SetPlayer_Delayed_AccelCoef instead"` | Deprecation notice |

`TechGravityChange` and `TechGravityReset` are gameplay surface effects (blocks/items can modify gravity). `DefaultGravitySpawn` provides the initial gravity configuration.

**Cross-reference with TMNF**: The TMNF diary documents GravityCoef=3.0 (a multiplier on base 9.81). TM2020's 0-1 range works differently -- 1.0 likely means full gravity.

Confidence: VERIFIED

## Thread Model: Dual Thread Pool

TM2020 uses a dual thread pool system. The custom pool maps well to Web Workers for browser recreation.

**Windows Thread Pool API** (imported via kernel32):
- `CreateThreadpoolTimer`, `SetThreadpoolTimer`, `WaitForThreadpoolTimerCallbacks`, `CloseThreadpoolTimer`
- `CreateThreadpoolWait`, `SetThreadpoolWait`, `CloseThreadpoolWait`
- `CreateThreadpoolWork`, `SubmitThreadpoolWork`, `CloseThreadpoolWork`

**Custom NClassicThreadPool**:
- `NClassicThreadPool::Destroy` (`0x141d094b8`)
- `NThreadPool_AddJobs` (`0x141d094f8`)
- `NClassicThreadPool::TaskWaitComplete` (`0x141d09510`)

The `AddJobs`/`TaskWaitComplete` pattern is a standard fork-join model.

Confidence: VERIFIED

## Deferred Rendering: 19-Pass Pipeline

108 string matches confirm a Tech3 shader framework with this pass ordering (reconstructed from `Down3x3`/`Down2x2` dependency chain strings):

```
Pipeline Execution Order:
═══════════════════════════════════════════════════════
1.  DipCulling              - Frustum/occlusion culling
2.  DeferredWrite           - G-buffer fill (albedo, material)
3.  DeferredWriteFNormal    - Face normal generation
4.  DeferredWriteVNormal    - Vertex normal pass
5.  DeferredDecals          - Deferred decal projection
6.  DeferredBurn            - Burn mark effects
7.  DeferredShadow          - Shadow map sampling (PSSM)
8.  DeferredAmbientOcc      - SSAO/HBAO+ pass
9.  DeferredFakeOcc         - Fake occlusion (far objects)
10. CameraMotion            - Motion vector generation
11. DeferredRead            - G-buffer read (start lighting)
12. DeferredReadFull        - Full G-buffer resolve
13. Reflects_CullObjects    - Reflection probe culling
14. DeferredLighting        - Light accumulation
15. CustomEnding            - Custom post-lighting effects
16. DeferredFogVolumes      - Volumetric fog (box volumes)
17. DeferredFog             - Global fog
18. LensFlares              - Lens flare effects
19. FxTXAA                  - Temporal anti-aliasing
═══════════════════════════════════════════════════════
```

### G-Buffer Layout

Three separate normal buffers (face, vertex, pixel) suggest the engine blends them for different quality levels or effects.

| Target Name | Purpose |
|-------------|---------|
| `BitmapDeferredDiffuseAmbient` | Diffuse color + ambient term |
| `BitmapDeferredFaceNormalInC` | Face (geometric) normal in camera space |
| `BitmapDeferredVertexNormalInC` | Vertex normal in camera space |
| `BitmapDeferredPixelNormalInC` | Per-pixel normal in camera space |
| `BitmapDeferredZ` | Depth buffer |
| `BitmapDeferredPreShade` | Pre-shading data |
| `BitmapDeferredLightMask` | Light mask / stencil |
| `BitmapDeferredMSpecular` | Specular material properties |
| `BitmapDeferredMDiffuse` | Diffuse material properties |

### AA Options

- `|DeferredAntialiasing| FXAA` -- Fast approximate AA
- `|DeferredAntialiasing| TXAA` -- Temporal AA (NVIDIA + Ubisoft)
- `|DeferredAntialiasing|None` -- No AA

Config: `CSystemConfigDisplay::EDeferredAA`, stored as `m_DeferredAA`

### HLSL Shader File List (Tech3 Framework)

All shaders live under the `Tech3/` path prefix.

**Deferred Pipeline Shaders**:
- `DeferredDecalGeom_p.hlsl` / `_v.hlsl` -- Decal projection
- `DeferredFull_Warp_p.hlsl` -- Full-screen warp effect
- `DeferredCameraMotion_p.hlsl` / `_v.hlsl` -- Motion vectors
- `DeferredZBufferToDist01_p.hlsl` -- Depth to linear distance
- `DeferredGeomFakeOcc_p.hlsl` / `_v.hlsl` -- Fake occlusion
- `DeferredGeomCameraMap_p.hlsl` / `_v.hlsl` -- Camera map effect
- `DeferredFogGlobal_p.hlsl` -- Global fog
- `DeferredFaceNormalFromDepth_p.hlsl` -- Normal reconstruction from depth
- `DeferredDeCompFaceNormal_p.hlsl` -- Normal decompression
- `DeferredGeomLightFxSphere_p.hlsl` -- Sphere light
- `DeferredGeomLightFxCylinder_p.hlsl` -- Cylinder light
- `DeferredGeomLightSpot_p.hlsl` -- Spot light
- `DeferredGeomLightBall_p.hlsl` -- Ball/point light
- `DeferredGeomFogBoxOutside_p.hlsl` / `_v.hlsl` -- Fog volume (outside)
- `DeferredGeomFogBoxInside_p.hlsl` / `_v.hlsl` -- Fog volume (inside)
- `DeferredDecal_FullTri_p.hlsl` / `_v.hlsl` -- Full-triangle decal
- `DeferredGeomShadowVol_p.hlsl` / `_v.hlsl` -- Shadow volumes
- `DeferredGeomProjector_p.hlsl` / `_v.hlsl` -- Projected textures
- `DeferredGeomBurnSphere_p.hlsl` / `_v.hlsl` -- Burn sphere effects
- `SSReflect_Deferred_LastFrames_p.hlsl` -- Temporal SSR
- `SSReflect_Deferred_p.hlsl` -- Screen-space reflections
- `DeferredFog_p.hlsl` -- Fog
- `DeferredDecal_Boxs_p.hlsl` -- Box decals
- `DeferredDecal_Boxs_CBuffer_v.hlsl` / `_SRView_v.hlsl` -- Box decal variants
- `DeferredWaterFog_p.hlsl` / `_v.hlsl` -- Water fog
- `DeferredWaterFog_FullTri_p.hlsl` / `_v.hlsl` -- Full-tri water fog
- `DeferredShadowPssm_p.hlsl` / `_v.hlsl` -- PSSM shadows
- `DeferredOutput_ImpostorConvert_c.hlsl` -- Impostor compute
- `Deferred_AddAmbient_Fresnel_p.hlsl` -- Ambient + Fresnel
- `Deferred_SetILightDir_p.hlsl` -- Set indirect light direction
- `Deferred_ReProjectLm_p.hlsl` -- Lightmap reprojection
- `Deferred_AddLightLm_p.hlsl` -- Add lightmap lighting
- `Deferred_SetLDirFromMask_p.hlsl` -- Light direction from mask

**Specialty shaders**:
- `Tech3 DeferredWrite CarSkinSkelDmg.Shader.Gbx` -- Car skin with skeletal damage
- `Tech3 DeferredWrite TreeSprite.Shader.Gbx` -- Tree sprite billboard
- `Tech3 DeferredInput DecalSprite.Shader.Gbx` -- Decal sprite

Confidence: VERIFIED

## TXAA: NVIDIA GFSDK + Ubisoft Custom

Two TXAA implementations exist. Uses `ResolveFromMotionVectors`, confirming motion vector-based temporal reprojection generated by the `CameraMotion` pass.

**NVIDIA GFSDK TXAA** (SDK integration):
- `GFSDK_TXAA_DX11_InitializeContext` (`0x141c0f120`)
- `GFSDK_TXAA_DX11_ResolveFromMotionVectors` (`0x141c0f178`)
- `GFSDK_TXAA_DX11_ReleaseContext` (`0x141c0f638`)

**Ubisoft Custom TXAA** (`UBI_TXAA` / `UBI TXAA`):
- Likely a custom Ubisoft/Nadeo implementation
- May serve as fallback when NVIDIA hardware is absent

TAA can be implemented in WebGPU using compute shaders with motion vectors. The motion vector pass + history buffer approach is standard.

Confidence: VERIFIED

## Graphics APIs: D3D11 Active, D3D12 Infrastructure Exists

D3D11 is the sole active rendering API. D3D12 shader infrastructure exists but appears unused. Vulkan has minimal presence.

**D3D12**: 3 string references, all in shader infrastructure:
- `NPlugGpuHlsl_D3D12::NRootSign_SParam` -- Root signature parameter struct
- `NPlugGpuHlsl_D3D12::NRootSign::EParamType` -- Parameter type enum
- `NPlugGpuHlsl_D3D12::SRootSign` -- Root signature struct

**Vulkan**: 1 string reference (`"Vulkan"` at `0x141c099e8`), likely a graphics API enum label. No Vulkan API calls found in imports.

D3D12/Vulkan are NOT actively used for rendering. The D3D12 code may exist for the Nadeo engine's cross-project sharing or future use.

Confidence: VERIFIED (code exists) / PLAUSIBLE (not actively used)

## ManiaScript: Complete Token Specification

40+ token strings reveal a full scripting language. The token list below defines the complete lexer specification for browser recreation.

### Data Types
| Token | Type |
|-------|------|
| `MANIASCRIPT_TYPE_VOID` | Void return |
| `MANIASCRIPT_TYPE_BOOLEAN` | Boolean |
| `MANIASCRIPT_TYPE_INTEGER` | Integer |
| `MANIASCRIPT_TYPE_REAL` | Float/real |
| `MANIASCRIPT_TYPE_TEXT` | String |
| `MANIASCRIPT_TYPE_VEC2` | 2D vector |
| `MANIASCRIPT_TYPE_VEC3` | 3D vector |
| `MANIASCRIPT_TYPE_INT2` | 2D integer vector |
| `MANIASCRIPT_TYPE_INT3` | 3D integer vector |
| `MANIASCRIPT_TYPE_ISO4` | 4x4 isometric transform |
| `MANIASCRIPT_TYPE_IDENT` | Resource identifier |
| `MANIASCRIPT_TYPE_CLASS` | Class reference |

### Keywords
| Token | Purpose |
|-------|---------|
| `SLEEP` | Coroutine sleep (ms) |
| `YIELD` | Yield to scheduler |
| `WAIT` | Wait for condition |
| `MEANWHILE` | Concurrent execution block |
| `ASSERT` | Debug assertion |
| `DUMP` / `DUMPTYPE` | Debug output |
| `LOG` | Log message |

### Collection Operations
All dot-prefixed operations on arrays/maps:
- `.add`, `.addfirst`, `.remove`, `.removekey`
- `.count`, `.clear`, `.get`, `.slice`
- `.sort`, `.sortrev`, `.sortkey`, `.sortkeyrev`
- `.existskey`, `.existselem`
- `.containsonly`, `.containsoneof`
- `.keyof`
- `.tojson`, `.fromjson`
- `.cloudrequestsave`, `.cloudisready` (cloud storage)

### Directives
| Directive | Purpose |
|-----------|---------|
| `#RequireContext` | Set required script context |
| `#Setting` | Declare a setting variable |
| `#Struct` | Define a struct type |
| `#Include` | Include another script |
| `#Extends` | Extend a base script |
| `#Command` | Register a command |
| `#Const` | Define a constant |

### Tuning System
- `TUNING_START` -- Begin tuning block
- `TUNING_END` -- End tuning block
- `TUNING_MARK` -- Mark a tuning checkpoint

### Lexer Token Types
- WHITESPACE, STRING, STRING_AND_CONCAT, NATURAL, FLOAT
- IDENT, COMMENT, STRING_OPERATOR, CONCAT_AND_STRING
- LOCAL_STRUCT

Confidence: VERIFIED

## Related Pages

- [22-ghidra-gap-findings.md](22-ghidra-gap-findings.md) -- Additional gap-filling research including force models and surface effects
- [18-validation-review.md](18-validation-review.md) -- Corrections to claims made in this and other documents
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- How these findings translate to browser implementation
- [23-visual-reference.md](23-visual-reference.md) -- Visual diagrams of the rendering pipeline and engine architecture

<details><summary>Analysis metadata</summary>

- **Binary**: `Trackmania.exe` (Trackmania 2020)
- **Date**: 2026-03-27
- **Tools**: PyGhidra bridge via `bridge_query.py`
- **Note**: Findings from both the automated Ghidra agent and manual queries

</details>

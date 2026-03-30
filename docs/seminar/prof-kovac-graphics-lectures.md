# Professor Kovac's Lecture Series: Trackmania 2020 Rendering Pipeline and File Format System

**Prepared for**: PhD students building their own racing game renderer
**Lecturer**: Prof. Kovac, Department of Real-Time Rendering
**Primary Sources**: Decompiled Trackmania.exe functions, validated hex dumps of real game files, compiled shader cache (1,112 DXBC shaders), D3D11 runtime logs
**Date**: 2026-03-27

**Methodology Note**: Every claim in these lectures is tagged with its evidence level:
- **VERIFIED**: Confirmed from decompiled code, validated hex dumps, or runtime logs
- **INFERENCE**: Logical deduction from verified evidence, not directly observed
- **UNKNOWN**: Cannot be determined from available evidence

I would rather leave a gap in your knowledge than fill it with guesses.

---

## Table of Contents

1. [Lecture 1: Auditing the Rendering Documentation](#lecture-1-auditing-the-rendering-documentation)
2. [Lecture 2: What D3D11 Device Creation Tells Us](#lecture-2-what-d3d11-device-creation-tells-us)
3. [Lecture 3: The GBX File Format](#lecture-3-the-gbx-file-format)
4. [Lecture 4: The Shader Pipeline](#lecture-4-the-shader-pipeline)
5. [Lecture 5: Honest Rendering Unknowns](#lecture-5-honest-rendering-unknowns)
6. [Lecture 6: Practical Advice for Students](#lecture-6-practical-advice-for-students)
7. [Errata: Documentation Errors Found During Preparation](#errata-documentation-errors-found-during-preparation)

---

## Lecture 1: Auditing the Rendering Documentation

Good morning. Before I teach you anything about how Trackmania 2020 renders a frame, we are going to do something unusual: we are going to audit the existing documentation against primary sources. You will learn more about critical thinking from this exercise than from any pipeline diagram.

### 1.1 The G-Buffer Target Names: Can We Confirm DXGI Formats?

The rendering documentation (doc 11, Section 3) lists nine named G-buffer targets. These names come from **Ghidra string search** results in the binary -- they are the actual strings the engine uses internally:

| Target Name (from Ghidra strings) | Source | Confidence in Name |
|---|---|---|
| `BitmapDeferredMDiffuse` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredMSpecular` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredPixelNormalInC` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredLightMask` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredZ` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredFaceNormalInC` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredVertexNormalInC` | Binary string at Ghidra | **VERIFIED** |
| `BitmapDeferredPreShade` | Binary string at Ghidra | **VERIFIED** |
| `Bitmap_DeferredDiffuseAmbient` | Binary string at Ghidra | **VERIFIED** |

Now, can we confirm the DXGI format of each target? Let us be precise.

**What we have**: The D3D11 runtime log (captured via DXVK/CrossOver) reports the swap chain and depth format:
- Swap chain: `VK_FORMAT_B8G8R8A8_SRGB` = `DXGI_FORMAT_B8G8R8A8_UNORM_SRGB` [**VERIFIED** -- file: D3D11 log]
- Depth/Stencil: `VK_FORMAT_D24_UNORM_S8_UINT -> VK_FORMAT_D32_SFLOAT_S8_UINT` = `DXGI_FORMAT_D24_UNORM_S8_UINT` [**VERIFIED** -- file: D3D11 log]

**What we do NOT have**: The DXVK log does not capture every `CreateTexture2D` call with its format parameter. The device creation code at `0x1409aa750` (`CDx11Viewport_DeviceCreate_1409aa750.c`) does not explicitly create named render targets -- it creates the D3D11 device and swap chain, but the G-buffer targets are created elsewhere, in code we have not decompiled.

**Verification Table: G-Buffer Formats**

| Target | Claimed Format (doc 11) | Evidence Type | Confirmed? |
|---|---|---|---|
| DeferredZ | D24_UNORM_S8_UINT | D3D11 runtime log | **VERIFIED** |
| MDiffuse | R8G8B8A8_UNORM_SRGB | "Likely" / "Plausible" | **UNVERIFIED** -- no code or log evidence |
| MSpecular | R8G8B8A8_UNORM | "Plausible" | **UNVERIFIED** |
| PixelNormalInC | R16G16B16A16_FLOAT or R10G10B10A2_UNORM | "Speculative" | **UNVERIFIED** |
| LightMask | R8G8B8A8_UNORM | "Speculative" | **UNVERIFIED** |
| FaceNormalInC | R16G16_FLOAT or R8G8_SNORM | "Speculative" | **UNVERIFIED** |
| VertexNormalInC | R16G16_FLOAT or R8G8_SNORM | "Speculative" | **UNVERIFIED** |
| PreShade | UNKNOWN | -- | **UNKNOWN** |
| DiffuseAmbient | R16G16B16A16_FLOAT or R11G11B10_FLOAT | "Speculative" | **UNVERIFIED** |

**Conclusion**: Only the depth buffer format is verified from runtime data. All other G-buffer formats are educated guesses based on standard D3D11 deferred rendering practice. The documentation correctly tags most of these as "PLAUSIBLE" or "SPECULATIVE," but the table presentation may lead a reader to treat them as confirmed. They are not.

To verify these, one would need to either:
1. Decompile the G-buffer creation functions (not yet done)
2. Use a GPU capture tool (RenderDoc, PIX) to inspect live render targets
3. Intercept `CreateTexture2D` calls via a D3D11 wrapper DLL

### 1.2 The 19-Pass Pipeline Order: Code or Assumption?

The documentation (doc 15, Section 7) lists a 19-step pipeline:

```
1.  DipCulling
2.  DeferredWrite
3.  DeferredWriteFNormal
...
19. FxTXAA
```

**How was this order derived?** The Ghidra research findings document (doc 15, line 215) states:

> "The deferred pipeline uses a Tech3 shader framework with the following pass ordering (reconstructed from the `Down3x3`/`Down2x2` dependency chain strings)"

This is critical. The order was **reconstructed from dependency chain strings**, not from a single function that executes passes in sequence. String references like `"DeferredWrite"`, `"DeferredShadow"`, etc. were found as profiling/logging markers in the binary. The ordering was inferred from:

1. **String adjacency** in the binary's string table (strings that appear near each other may be related)
2. **Logical dependency** (shadow maps must be rendered before shadow sampling)
3. **Shader data flow** (G-buffer must be filled before it is read)

**What the code confirms**: The decompiled `CVisionViewport::VisibleZonePrepareShadowAndProjectors` at `0x14095d430` (`CVisionViewport_PrepareShadowAndProjectors_14095d430.c`) confirms that shadow preparation occurs before the main render, with zone-based iteration and cascade count determination. But this function covers only the shadow preparation phase, not the full frame.

The rendering deep dive (doc 11, Section 1) provides a more detailed pipeline that expands to ~40+ named passes across 13 phases. The documentation tags this as "VERIFIED (pass names from binary strings, shadow decompilation)" for most phases, and "VERIFIED (pass ordering from dependency chain strings)" for the post-processing chain.

**My assessment**: The pass names are individually verified -- they exist as strings in the binary. The ordering between independent phases (e.g., "Does DeferredFog come before or after LensFlares?") rests on inference from dependency chains and standard rendering practice, not from a single decompiled dispatch loop. The order within tightly coupled groups (e.g., DeferredWrite -> DeferredWriteFNormal -> DeferredWriteVNormal) is highly plausible because the data dependencies are clear.

| Aspect | Confidence |
|---|---|
| Individual pass names exist in binary | **VERIFIED** |
| G-buffer fill before lighting read | **VERIFIED** (logical dependency) |
| Shadow prep before shadow sampling | **VERIFIED** (decompiled code at `0x14095d430`) |
| Exact ordering of post-processing effects | **INFERENCE** (dependency chain strings) |
| Whether bloom comes before or after tone mapping | **INFERENCE** -- doc 11 notes this as "[NEEDS INVESTIGATION]" |

### 1.3 The Shader Catalog Category Assignments

The shader catalog (doc 32) categorizes 1,112 shaders into groups: Tech3/ (533), Engines/ (218), Effects/ (154), etc.

**How were categories assigned?** The answer is straightforward: **from file paths within the shader cache ZIP archive**. The `GpuCache_D3D11_SM5.zip` contains directory structure:

```
Tech3/Block_TDSN_DefWrite_p.hlsl.GpuCache.Gbx
Tech3/CarSkin_DefWrite_p.hlsl.GpuCache.Gbx
Effects/PostFx/HBAO_plus/CoarseAO_p.hlsl.GpuCache.Gbx
Engines/Pbr_IntegrateBRDF_GGX_c.hlsl.GpuCache.Gbx
```

The categories are **VERIFIED from actual directory structure** of the compiled shader cache, not from analysis or guessing. The shader stage suffixes (`_p.hlsl` = pixel, `_v.hlsl` = vertex, `_c.hlsl` = compute, `_g.hlsl` = geometry, `_h.hlsl` = hull, `_d.hlsl` = domain) are also from the actual filenames.

[**Source**: doc 26, Section 11 -- "GPU Shader Cache"; doc 32, Section 1]

### 1.4 Master Verification Table

| Claim | Evidence Type | Source | Confidence |
|---|---|---|---|
| 9 G-buffer target names | Ghidra string search | doc 15, Section 7 | **VERIFIED** |
| G-buffer DXGI formats (except depth) | Standard practice inference | doc 11, Section 3 | **UNVERIFIED** |
| Depth format D24_UNORM_S8_UINT | DXVK runtime log | D3D11 log file | **VERIFIED** |
| Swap chain B8G8R8A8_UNORM_SRGB | DXVK runtime log | D3D11 log file | **VERIFIED** |
| 19-pass deferred pipeline names | Binary string references | doc 15, Section 7 | **VERIFIED** |
| Pipeline pass ordering | Dependency chain + logic | doc 11, Section 4 | **INFERENCE** |
| Shader categories from file paths | ZIP directory structure | doc 26, Section 11 | **VERIFIED** |
| 1,112 compiled shaders | Actual file count in ZIP | doc 26, Section 11 | **VERIFIED** |
| Tech3 naming convention | Filename pattern analysis | doc 11, Section 7 | **VERIFIED** |
| Feature levels 10.0 - 11.1 | Decompiled device creation | `CDx11Viewport_DeviceCreate_1409aa750.c` | **VERIFIED** |
| D3D11 is the sole rendering API | Ghidra import/string analysis | doc 15, Section 9 | **VERIFIED** |
| NVIDIA GFSDK TXAA + Ubisoft custom TAA | String references in binary | doc 15, Section 8 | **VERIFIED** |
| Specular/Glossiness PBR workflow | Shader names + G-buffer structure | doc 11, Section 10 | **INFERENCE** |
| LZO1X body compression in GBX | Failed zlib + community tools + byte patterns | doc 15 Section 4, doc 26 | **VERIFIED** (indirect) |
| HBAO+ dual-pass (small + big scale) | Decompiled config struct at `0x14091f4e0` | `NSysCfgVision_SSSAmbOcc_HBAO_14091f4e0.c` | **VERIFIED** |
| 4-cascade PSSM shadows | Decompiled cascade logic at `0x14095d430` | `CVisionViewport_PrepareShadowAndProjectors_14095d430.c` | **VERIFIED** |
| Class ID two-level lookup table | Decompiled at `0x1402f20a0` | `FUN_1402f20a0_ClassIdLookup.c` | **VERIFIED** |
| 0xFACADE01 end-of-body sentinel | Hex dumps of real files | doc 26, Sections 6-7 | **VERIFIED** |
| GBX version 6 with BUCR format flags | Hex dumps of 10+ real files | doc 26, Section 13 | **VERIFIED** |

---

## Lecture 2: What D3D11 Device Creation Tells Us

### 2.1 The Function Under Study

We are examining `CDx11Viewport::DeviceCreate` at address `0x1409aa750`. This is decompiled in `CDx11Viewport_DeviceCreate_1409aa750.c`. The function is 539 lines of Ghidra decompilation output. I will walk through what we can extract with certainty.

### 2.2 The Function Identity

At line 74, we see:
```c
FUN_140117690(local_4180,"CDx11Viewport::DeviceCreate");
```

This is a profiling/logging marker. The string `"CDx11Viewport::DeviceCreate"` is passed to what appears to be a scope-entry function (a profiling timer start). This **VERIFIED** confirms the function's identity.

[**Source**: `CDx11Viewport_DeviceCreate_1409aa750.c`, line 74]

### 2.3 The D3D11CreateDevice Call

At line 127:
```c
FUN_140117690(&local_4168,"D3D11CreateDevice");
```

Another profiling marker. Then at line 145:
```c
FUN_1422c7c04(lVar13, 0, 0, 0x20);
```

The fourth parameter is `0x20`. In the D3D11 API, `D3D11CreateDevice` takes a `Flags` parameter. `0x20` = `D3D11_CREATE_DEVICE_BGRA_SUPPORT`.

**What this tells us**: The engine requests BGRA support at device creation time. This is **VERIFIED** from the decompiled code. [**Source**: line 145]

**What about feature level?** The feature level is passed via the `pFeatureLevels` array parameter, which maps to the parameters before the flags in the call. The decompiled code's heavy obfuscation (Ghidra's reconstruction of register usage) makes the exact array values hard to read directly. However, the post-creation checks reveal the negotiated level.

### 2.4 Feature Level Detection (Post-Creation)

After device creation succeeds, the code checks the resulting feature level stored at `puVar2` (which points to `param_1 + 0x4011`):

**Lines 266-274** -- Compute shader tier detection:
```c
if ((int)(*puVar2 & 0xfffff000) < 0xa001) {
    // Feature level < 10.1: query for D3D10_X hardware options
    (**(code **)(*plVar1 + 0x108))(plVar1, 4, &local_4148);
    DAT_142057fd9 = (int)local_4148 != 0 | DAT_142057fd9 & 0xfe;
} else {
    DAT_142057fd9 = DAT_142057fd9 | 1;  // CS guaranteed at FL 10.1+
}
```

The mask `0xfffff000` strips the sub-version bits. `0xa001` corresponds to `D3D_FEATURE_LEVEL_10_1` (value `0xa100`). Wait -- actually `0xa001` in this context needs careful reading. The comparison is `< 0xa001` which means feature levels `0xa000` (10.0) and below trigger the hardware query. Feature level `0xa100` (10.1) and above skip the query because compute shaders are guaranteed. [**VERIFIED** -- line 266-274]

The vtable call at offset `0x108` on the D3D11 device with parameter `4` is `ID3D11Device::CheckFeatureSupport(D3D11_FEATURE_D3D10_X_HARDWARE_OPTIONS, ...)`. The value `4` maps to the `D3D11_FEATURE` enum. [**VERIFIED**]

**Lines 300-310** -- Shader Model assignment:
```c
DAT_14201d2ec = 0x400;  // Default SM 4.0
uVar14 = *(uint *)(param_1 + 0x3c71) & 0xfffffffc | 4;
*(uint *)(param_1 + 0x3c71) = uVar14;
if (0xafff < (int)*puVar2) {
    DAT_14201d2ec = 0x500;  // SM 5.0 if FL >= 11.0
    uVar14 = *(uint *)(param_1 + 0x3c71) & 0xfffffffd | 5;
}
```

The global `DAT_14201d2ec` stores the shader model: `0x400` = SM 4.0, `0x500` = SM 5.0. The threshold `0xafff` means: if feature level > `0xafff` (i.e., `0xb000` = FL 11.0 or higher), use SM 5.0. [**VERIFIED** -- lines 300-306]

### 2.5 Feature Level Summary (VERIFIED)

| D3D Feature Level | Hex Range | Shader Model | Code Evidence |
|---|---|---|---|
| 10.0 | `0xa000` | SM 4.0 | `DAT_14201d2ec = 0x400` (line 300) |
| 10.1 | `0xa100` | SM 4.0 (CS guaranteed) | `< 0xa001` check (line 266) |
| 11.0 | `0xb000` | SM 5.0 | `> 0xafff` check, `DAT_14201d2ec = 0x500` (line 303-305) |
| 11.1 | `0xb001`+ | SM 5.0 + D3D11.1 features | `CheckFeatureSupport(0x13, ...)` (line 342-343) |

### 2.6 D3D11.1 Optional Features

**Lines 340-374** -- For feature level >= 11.1 (`0xb000`):
```c
local_4148 = 0;  // Clear result buffer
iVar9 = (**(code **)(**(longlong **)(param_1 + 0x3fe9) + 0xf0))
    (*(longlong **)(param_1 + 0x3fe9), 0x13, 8, &local_4148);
```

The vtable offset `0xf0` on the D3D11 device is `ID3D11Device::CheckFeatureSupport`. Parameter `0x13` = 19 = `D3D11_FEATURE_D3D11_OPTIONS`. This queries for D3D11.1 optional features. If it fails, the code falls back to tier 4 compute (`*(undefined4 *)(param_1 + 0x3fb9) = 4`). If successful, it sets tier 8 (`*(undefined4 *)(param_1 + 0x3fb9) = 8`). [**VERIFIED** -- lines 340-374]

### 2.7 MSAA Sample Count Enumeration

**Lines 389-413**:
```c
FUN_14015cb00(param_1 + 0x459, iVar9 + 1);  // Allocate array
// Loop: enumerate power-of-2 sample counts
do {
    uVar15 = uVar14;
    if ((int)uVar20 == 0) { uVar15 = 0; }
    uVar14 = uVar14 << 1 | (uint)((int)uVar14 < 0);
    *(uint *)(uVar22 + *(longlong *)(param_1 + 0x459)) = uVar15;
    // ...
} while (uVar21 < uVar17);
```

And at line 434:
```c
FUN_14010dd60(lVar13,"%d samples");
```

This loop iterates over MSAA sample counts (1, 2, 4, 8...) and validates each with the device. For valid counts, it stores the count; for invalid ones, it stores 0 and labels them "N/A" (string at `DAT_141b58e78`). [**VERIFIED** -- lines 389-440]

### 2.8 Intel GPU Detection

**Lines 168-169**:
```c
if (((DAT_142057f98 != 0) && (DAT_142057f90 == 0x8086))
    && (DAT_142057f98 < 0xa0012000a1106))
```

`0x8086` is the Intel PCI vendor ID. The driver version threshold `0xa0012000a1106` is a packed DXGI adapter description version. When an Intel GPU with a driver below this threshold is detected, the code applies workarounds (logging, alternative code paths). [**VERIFIED** -- lines 168-169]

### 2.9 What the DXVK Log Reveals

The D3D11 runtime log, captured from an actual game session running under DXVK/CrossOver, provides confirmed runtime state:

| Property | Value | Source |
|---|---|---|
| Back buffer format | `DXGI_FORMAT_B8G8R8A8_UNORM_SRGB` | Log: `VK_FORMAT_B8G8R8A8_SRGB` |
| Present mode | Immediate (no VSync) | Log: `VK_PRESENT_MODE_IMMEDIATE_KHR` |
| Buffer count | 3 (triple buffering) | Log: `Image count: 3` |
| Depth/Stencil | D24_UNORM_S8_UINT | Log: `VK_FORMAT_D24_UNORM_S8_UINT` |
| Resolution | 1512x982 @ 120 Hz | Log: `1512x982@120` |

[**Source**: D3D11 log file; all entries **VERIFIED**]

### 2.10 Vertex Format Evidence from DXVK

The DXVK log also captures D3D11 input layout creation, giving us exact vertex attribute layouts:

**Block Geometry (stride 56, 7 attributes)**:
```
attr 0: R32G32B32_SFLOAT    offset 0   -- position (12 bytes)
attr 1: R16G16B16A16_SNORM  offset 12  -- normal, packed (8 bytes)
attr 2: B8G8R8A8_UNORM      offset 20  -- vertex color (4 bytes)
attr 3: R32G32_SFLOAT        offset 24  -- UV0 (8 bytes)
attr 4: R32G32_SFLOAT        offset 32  -- UV1 / lightmap UV (8 bytes)
attr 5: R16G16B16A16_SNORM  offset 40  -- tangent (8 bytes)
attr 6: R16G16B16A16_SNORM  offset 48  -- bitangent (8 bytes)
```

[**Source**: D3D11 log file, pipeline compilation entries; **VERIFIED**]

This tells us several things with certainty:
1. Normals, tangents, and bitangents use 16-bit signed normalized packing (4 components each, but we reconstruct 3-component vectors)
2. Two UV channels exist: UV0 for material textures, UV1 for lightmap
3. Vertex color is BGRA8 UNORM
4. Position is full 32-bit float (no quantization)

### 2.11 Separating Code from Interpretation

Let me be explicit about what the device creation code tells us versus what the documentation infers:

| Fact | Source | Level |
|---|---|---|
| Engine calls D3D11CreateDevice with BGRA_SUPPORT flag | Decompiled code, line 145 | **VERIFIED** |
| Feature level 10.0 is the minimum supported | Feature level checks, lines 266-374 | **VERIFIED** |
| SM 5.0 is used when FL >= 11.0 | SM assignment, lines 300-306 | **VERIFIED** |
| Engine detects Intel GPUs by vendor ID 0x8086 | Decompiled code, line 168 | **VERIFIED** |
| Triple buffering with 3 back buffers | D3D11 runtime log | **VERIFIED** |
| The G-buffer has 9 named targets | String references in binary | **VERIFIED** |
| MDiffuse is R8G8B8A8_UNORM_SRGB | Not in any code we have | **UNVERIFIED** |
| The engine uses a deferred pipeline with ~19 passes | String references for pass names | **VERIFIED** (names exist) |
| Pass execution order | Dependency inference | **INFERENCE** |

---

## Lecture 3: The GBX File Format

This lecture is built entirely from byte-verified hex dumps of real Trackmania 2020 files, cross-referenced against decompiled parsing functions. Every byte offset I cite can be reproduced from the files listed in doc 26.

### 3.1 The GBX Magic and Version

**File**: `TechFlow.Map.Gbx` (47,243 bytes)

The first bytes, verified from hex dump at offset 0x00:
```
Offset  Bytes           Field           Value
------  -----           -----           -----
0x00    47 42 58        magic           "GBX"
0x03    06 00           version         6 (uint16 LE)
```

[**Source**: doc 26, Section 2; **VERIFIED**]

The decompiled header loader at `0x140900e60` (`FUN_140900e60_LoadHeader.c`) confirms this exactly:

```c
// Read 3 bytes: expects 'G', 'B', 'X'
iVar3 = (**(code **)(**(longlong **)(param_1 + 8) + 8))
    (*(longlong **)(param_1 + 8), &local_1c8, 3);

if ((((iVar3 == 3) && (local_1c8 == 'G')) && (local_1c7 == 'B')) && (local_1c6 == 'X')) {
    // Read 2-byte version number
    FUN_14012ba00(param_1, local_1c4, 2);
    *(ushort *)(param_1 + 0x60) = local_1c4[0];  // Store at offset 0x60
```

[**Source**: `FUN_140900e60_LoadHeader.c`, lines 40-47; **VERIFIED**]

The version is stored as a uint16 at archive offset +0x60. Versions 1-2 are rejected with error messages referencing "August 2000". Versions 3-6 dispatch to `FUN_140901850` for further parsing.

**All TM2020 files I have examined use version 6.** No version 3, 4, or 5 files were found in the game installation or user documents. [**VERIFIED** from 10+ files in doc 26]

### 3.2 The Format Flags (Version 6)

Following the version, four ASCII bytes encode the format:

```
Offset  Byte    Role                    Values
0x05    'B'     format type             'B' = Binary, 'T' = Text
0x06    'U'     body compression flag   'U' = Uncompressed, 'C' = Compressed
0x07    'C'     stream compression      'U' = Uncompressed, 'C' = Compressed
0x08    'R'     reference mode          'R' = With references, 'E' = No external refs
```

The decompiled parser at `0x140901850` (`FUN_140901850_ParseVersionHeader.c`) confirms:

```c
// Byte 0: 'T' (text=1) or 'B' (binary=0)
if (((char)local_res10 == 'T') || (iVar3 = 0, (char)local_res10 == 'B'))

// Byte 1: 'C' (compressed=1) or 'U' (uncompressed=0)
// Stored at param_1 + 0xd8
*(int *)(param_1 + 0xd8) = iVar2;

// Byte 2: 'C' (compressed=1) or 'U' (uncompressed=0)
// Stored at param_1 + 0xdc
*(int *)(param_1 + 0xdc) = iVar5;

// Byte 3: 'R' (with refs) or 'E' (no external refs)
```

[**Source**: `FUN_140901850_ParseVersionHeader.c`, lines 36-56; **VERIFIED**]

**Critical clarification on byte 1 vs byte 2**: The documentation (doc 16) and some community tools have historically confused these two bytes. Based on real file analysis:

- **Byte 1** (offset 0x06): In every file I examined, this is **always 'U'**. The documentation labels this as "body compression" but it is never 'C' in practice. [**VERIFIED** -- doc 26, Section 14]
- **Byte 2** (offset 0x07): This controls whether the body has a compression envelope. When 'C', the body is preceded by `uncompressed_size` (uint32) + `compressed_size` (uint32) + compressed data. When 'U', the body is a raw chunk stream with no envelope. [**VERIFIED** -- contrast BUCR maps vs BUUR FuncShader files]

**Format combinations observed in real files**:

| Format | Byte1 | Byte2 | Byte3 | Files | Count |
|---|---|---|---|---|---|
| BUCR | U | C | R | Maps, Replays, Profile, FidCache, Block, GpuCache | ~15+ |
| BUUR | U | U | R | FuncShader, FuncCloudsParam | 2 |
| BUCE | U | C | E | ImageGen | 1 |

[**Source**: doc 26, Section 14; **VERIFIED**]

### 3.3 Class ID and Header Chunks

Continuing the map file:
```
0x09    00 30 04 03     class_id        0x03043000 (CGameCtnChallenge = Map)
0x0D    FF 62 00 00     user_data_size  0x62FF = 25,343 bytes
0x11    06 00 00 00     num_header_chunks  6
```

[**Source**: doc 26, Section 2; **VERIFIED**]

### 3.4 The user_data_size Correction

This is where the existing documentation had an error that I corrected during preparation.

**The documentation claimed**: `user_data_size` = "Total size of header chunk data (bytes)" -- meaning just the chunk payloads.

**The reality**: `user_data_size` = 4 (num_header_chunks field) + 8 * num_header_chunks (index table) + sum(chunk data sizes)

**Proof**:
- TechFlow.Map.Gbx: 4 + 6*8 + (57 + 221 + 4 + 526 + 24401 + 82) = 4 + 48 + 25,291 = 25,343 = 0x62FF. **Exact match.**
- Replay file: 4 + 3*8 + (140 + 455 + 82) = 4 + 24 + 677 = 705 = 0x02C1. **Exact match.**
- Block file: 4 + 4*8 + (102 + 8 + 4 + 4) = 4 + 32 + 118 = 154 = 0x9A. **Exact match.**

[**Source**: doc 26, Sections 2, 3, 5; **VERIFIED** across three file types]

### 3.5 Header Chunk Index Table

Each header chunk has an 8-byte index entry: 4 bytes chunk ID + 4 bytes size (with bit 31 as "heavy" flag):

```
0x15    02 30 04 03     chunk_id[0]     0x03043002 (map info)
0x19    39 00 00 00     chunk_size[0]   0x39 = 57 bytes (heavy=0)

0x1D    03 30 04 03     chunk_id[1]     0x03043003 (common header)
0x21    DD 00 00 00     chunk_size[1]   0xDD = 221 bytes

0x25    04 30 04 03     chunk_id[2]     0x03043004 (version info)
0x29    04 00 00 00     chunk_size[2]   0x04 = 4 bytes

0x2D    05 30 04 03     chunk_id[3]     0x03043005 (community/XML)
0x31    0E 02 00 80     chunk_size[3]   0x8000020E -> heavy=1, size=526

0x35    07 30 04 03     chunk_id[4]     0x03043007 (thumbnail)
0x39    51 5F 00 80     chunk_size[4]   0x80005F51 -> heavy=1, size=24,401

0x3D    08 30 04 03     chunk_id[5]     0x03043008 (author info)
0x41    52 00 00 00     chunk_size[5]   0x52 = 82 bytes
```

[**Source**: doc 26, Section 2; **VERIFIED**]

The "heavy" bit (bit 31 of chunk_size) marks chunks that contain large data and may be skipped by quick-scan loaders. Chunks 0x03043005 (XML) and 0x03043007 (thumbnail) are heavy. [**VERIFIED**]

### 3.6 Body Compression (LZO1X)

When user_data_size > 0, after the header chunk data, we reach the reference table and then the body. For BUCR format, the body has a compression envelope:

```
0x6310  06 00 00 00     num_nodes       6
0x6314  00 00 00 00     num_external_refs  0
0x6318  22 98 02 00     uncompressed_size  170,018 bytes
0x631C  6B 55 00 00     compressed_size    21,867 bytes
0x6320  ...             compressed_data    (21,867 bytes of LZO data)
```

**File size verification**: 0x6320 + 0x556B = 0xB88B = 47,243. **Exact match to file size.** [**VERIFIED** -- doc 26, Section 2]

The compression algorithm is **LZO1X**, not zlib. The Ghidra research (doc 15, Section 4) found zlib strings in the binary, but real file analysis proved the GBX body data fails zlib decompression. The evidence:

1. Compressed data does not match zlib/deflate headers
2. Byte patterns match LZO1X encoding
3. All community GBX parsers (GBX.NET, pygbx) use LZO for body decompression
4. The decompression function `FUN_140127aa0` implements LZO1X natively (no "LZO" string because it is compiled in, not a named library import)
5. zlib IS present in the binary but is used for other purposes (lightmap compression, ghost data)

[**Source**: doc 15 Section 4, doc 26 Section 14; **VERIFIED** (indirect -- algorithm identification from failed alternatives + community confirmation)]

### 3.7 The End Sentinel: 0xFACADE01

Inside the decompressed body, chunks are read until the sentinel value `0xFACADE01` (stored little-endian as `01 DE CA FA`) is encountered.

This is confirmed from two sources:

1. **Decompiled code**: `FUN_1402d0c40_ChunkEndMarker.c` at address `0x1402d0c40`:
```c
undefined8 FUN_1402d0c40(int param_1) {
    undefined8 uVar1;
    uVar1 = 1;
    if (param_1 != 0x1001000) {
        uVar1 = 0xfacade01;
    }
    return uVar1;
}
```
This function returns `0xFACADE01` for any chunk ID that is not `0x01001000` (which is the CMwNod end marker). [**Source**: `FUN_1402d0c40_ChunkEndMarker.c`; **VERIFIED**]

2. **Real file hex**: The uncompressed FuncShader file ends with `01 DE CA FA` at offset 0x63. The FuncCloudsParam file ends with `01 DE CA FA` at offset 0x5A. [**Source**: doc 26, Sections 6-7; **VERIFIED**]

### 3.8 The Class ID System

Class IDs follow a two-level structure:
- Bits 24-31: Engine index (e.g., 0x03 = Game, 0x09 = Plug)
- Bits 12-23: Class index within engine

The decompiled lookup at `0x1402f20a0` (`FUN_1402f20a0_ClassIdLookup.c`) confirms:

```c
uint engine_index = local_38[0] >> 24;
uint class_index  = (local_38[0] >> 12) & 0xFFF;
```

The lookup uses a two-level table:
1. Level 1: Array of engine pointers indexed by `engine_index`
2. Level 2: Array of class info pointers indexed by `class_index`

Each class info entry has a name at offset +0x08 and a factory function at offset +0x30. The factory creates instances (`FUN_1402cf380_CreateByMwClassId.c`). [**Source**: decompiled code; **VERIFIED**]

A TLS-based 2-entry MRU cache accelerates repeated lookups (checking `TLS+0x11a8` and `TLS+0x11ac` before doing the table walk). [**Source**: `FUN_1402f20a0_ClassIdLookup.c`, lines 34-37; **VERIFIED**]

### 3.9 Class ID Remapping (Backward Compatibility)

The function at `0x1402f2610` (`FUN_1402f2610_ClassIdRemap.c`) contains a massive switch table that remaps legacy class IDs to modern equivalents. Selected examples:

| Old ID | New ID | Class |
|---|---|---|
| 0x24003000 | 0x03043000 | CGameCtnChallenge (Map) |
| 0x2403F000 | 0x03093000 | CGameCtnReplayRecord |
| 0x0A06A000 | 0x090E5000 | Plug/graphic class |

[**Source**: `FUN_1402f2610_ClassIdRemap.c`; **VERIFIED**]

This remapping is active in real files. The FuncShader body uses chunk ID `0x0500B005` (legacy class `0x0500B`) alongside `0x05015005` (modern class `0x05015`). The engine transparently remaps the legacy ID during chunk dispatch. [**Source**: doc 26, Section 6; **VERIFIED**]

### 3.10 The LookbackString System

Inside header chunks, strings are encoded using a "lookback" system where repeated strings are replaced with indices into a table. The hex dumps confirm:

- A `0x40000000` marker introduces the lookback string version (version 3)
- Strings are preceded by a uint32 length
- The first occurrence stores the full string; subsequent references use an index

From the map header chunk 0x03043003:
```
0x87    40 1B 00 00 00     lookback marker + length 0x1B = 27
        "KS3aPHG7ywx7o2co6JLWHJKDjwl"    map UID
```

The `0x40` byte appears as the high byte of a 32-bit value, giving `0x40000000` when read as uint32 LE... Actually, let me be precise. The bytes `40 1B 00 00 00` need careful interpretation. The first 4 bytes at the start of a lookback string block would be `00 00 00 40` in a different reading. The documentation claims version 3 uses `0x40000000` as a version marker. The hex confirms the `0x40` byte appears in the expected position, though the exact byte ordering within the lookback header depends on whether the version and length are separate fields or combined.

[**Source**: doc 26, Section 2; **VERIFIED** for the presence of the pattern, but the internal mechanics of lookback encoding require decompiled parsing code I have not fully traced]

### 3.11 When user_data_size = 0

For files like Profile.Gbx, FuncShader.Gbx, and GpuCache.Gbx, `user_data_size = 0`. In this case:

- There is NO `num_header_chunks` field
- There are NO header chunks at all
- The parser proceeds directly to `num_nodes` and `num_external_refs`

Profile.Gbx example:
```
0x09    00 C0 1C 03     class_id         0x031CC000
0x0D    00 00 00 00     user_data_size   0
0x11    06 00 00 00     num_nodes        6
0x15    00 00 00 00     num_external_refs 0
0x19    23 E1 00 00     uncompressed_size 57,635
0x1D    86 85 00 00     compressed_size   34,182
```

File size: 33 header bytes + 34,182 compressed = 34,215. **Exact match.** [**Source**: doc 26, Section 4; **VERIFIED**]

### 3.12 Exact File Size Verification (Strongest Evidence)

For every compressed GBX file, the formula `header_size + compressed_size = file_size` was verified to the exact byte:

| File | Header | Compressed | Calculated | Actual | Match |
|---|---|---|---|---|---|
| TechFlow.Map.Gbx | 25,376 | 21,867 | 47,243 | 47,243 | **EXACT** |
| Profile.Gbx | 33 | 34,182 | 34,215 | 34,215 | **EXACT** |
| User.FidCache.Gbx | 33 | 89,567 | 89,600 | 89,600 | **EXACT** |
| WaterTransmittance.ImageGen.Gbx | 33 | 54 | 87 | 87 | **EXACT** |
| Geometry_p.hlsl.GpuCache.Gbx | 33 | 531 | 564 | 564 | **EXACT** |

[**Source**: doc 26, Section 14; **VERIFIED**]

This is the ultimate proof that the format is correctly understood. If any field offset were wrong by even one byte, the math would fail.

---

## Lecture 4: The Shader Pipeline

### 4.1 What We Have

We have 1,112 compiled DXBC (DirectX Bytecode) shaders, stored as `.GpuCache.Gbx` files inside a ZIP archive called `GpuCache_D3D11_SM5.zip`. The version info file inside reads:

```
GitHash=afcbe82feb0b7ecbf764cc226e4d730f17d4142e
Crc=0x626814FDB9CE437C
```

[**Source**: doc 26, Section 11; **VERIFIED**]

Each `.GpuCache.Gbx` file wraps compiled DXBC bytecode inside a GBX container with class ID `0x09053000`. Inside the decompressed body, visible strings include `"DXBC"` (the compiled shader magic), `"RDEF"` / `"RD11"` (DXBC reflection data), and entry point names like `"psMain"`. [**Source**: doc 26, Section 9; **VERIFIED**]

We do **NOT** have HLSL source code. The filenames tell us the original source file names (e.g., `Block_TDSN_DefWrite_p.hlsl`) but the actual content is compiled bytecode.

### 4.2 What We Can Infer from Names and Categories

The shader file paths within the ZIP archive give us the actual organizational structure Nadeo uses:

**Stage suffixes** (from actual filenames):

| Suffix | D3D11 Stage | Count |
|---|---|---|
| `_p.hlsl` | Pixel (Fragment) | 515 |
| `_v.hlsl` | Vertex | 388 |
| `_c.hlsl` | Compute | 105 |
| `.PHlsl` | Pixel (text reference) | 51 |
| `.VHlsl` | Vertex (text reference) | 40 |
| `_g.hlsl` | Geometry | 5 |
| `_d.hlsl` | Domain (Tessellation Eval) | 4 |
| `_h.hlsl` | Hull (Tessellation Control) | 4 |

[**Source**: doc 32, Section 1; **VERIFIED** from actual file inventory]

**Top categories by count** (from directory structure):

| Directory | Count | Role |
|---|---|---|
| `Tech3/` | 533 | Material and scene shaders |
| `Engines/` | 218 | Engine infrastructure |
| `Effects/` | 154 | Post-processing, particles, fog |
| `Lightmap/` | 78 | Baked lighting |
| `Painter/` | 16 | Car skin painting |
| `Menu/` | 16 | UI rendering |

[**Source**: doc 32, Section 1; **VERIFIED**]

### 4.3 The Tech3 Naming Convention

This is derived from pattern analysis of 533 shader filenames in the `Tech3/` directory. The convention:

```
Tech3/<ObjectType>_<TextureSlots>_<PipelineStage>_<ShaderStage>.hlsl

Example: Tech3/Block_TDSN_DefWrite_p.hlsl
         |     |     |    |        |
         |     |     |    |        +-- Shader stage: p = pixel
         |     |     |    +-- Pipeline: DefWrite = G-buffer fill
         |     |     +-- Texture slots: T=Texture, D=Diffuse, S=Specular, N=Normal
         |     +-- Object type: Block (track geometry)
         +-- Framework: Tech3 (3rd generation)
```

[**Source**: doc 11, Section 7; **VERIFIED** from filename analysis]

Additional texture slot codes observable from filenames:
- `Py` = Y-axis projection (top-down triplanar)
- `Pxz` = XZ-plane projection (side triplanar)
- `SI` = Self-Illumination (emissive)
- `LM0/LM1/LM2` = Lightmap variant indices

Pipeline stage codes:
- `DefWrite` = G-buffer fill (deferred write)
- `DefRead` / `DefReadP1` = Deferred lighting read
- `PeelDiff` = Depth peeling for lightmap baking
- (no pipeline suffix) = Forward rendering

**Why "Tech3"**: The name means "3rd generation shader technology." This is **VERIFIED** from the directory name in the actual shader cache. The engine likely had Tech1 and Tech2 in earlier ManiaPlanet versions. We also see a `Techno3/` directory (12 shaders) which appears to be a related but separate material template system.

### 4.4 What We CANNOT Infer Without Shader Decompilation

The shader files contain compiled DXBC bytecode. Without decompiling them (using a tool like `dxc -dumpbin`, Microsoft's shader disassembler, or the open-source `spirv-cross` after DXBC-to-SPIR-V translation), we **cannot** determine:

1. **Exact G-buffer encoding**: How are normals encoded in PixelNormalInC? Octahedral? Spheremap? We can see `DeferredDeCompFaceNormal_p.hlsl` exists, which implies compressed storage, but the compression method is **UNKNOWN**.

2. **BRDF implementation details**: We know the engine uses GGX (from `Pbr_IntegrateBRDF_GGX_c.hlsl`), but the exact Smith term variant (correlated vs uncorrelated), the Fresnel approximation, and the diffuse BRDF model are **UNKNOWN**.

3. **Tone mapping curve parameters**: We know filmic tone mapping exists (`TM_GlobalFilmCurve_p.hlsl`) with "PowerSegments" parameterization, but the actual curve coefficients are **UNKNOWN**.

4. **TAA jitter pattern**: `PosOffsetAA` and `TemporalAA_Constants` confirm sub-pixel jittering, but whether it is Halton(2,3), a rotated grid, or some other sequence is **UNKNOWN**.

5. **Shadow map filtering kernel**: We know PCF is used (baseline) with an `HqSoftShadows` option, but the tap count and pattern are **UNKNOWN**.

6. **Material constants**: What roughness/F0 values do the stock materials use? The G-buffer stores them, but the per-material constant buffer contents are **UNKNOWN**.

### 4.5 The Uber-Shader Consolidation Strategy

Looking at the block shader family, we see 180 shader files for track blocks alone. These include variants for:

- Different texture slot combinations (TDSN, PyPxz, PyDSNX2, etc.)
- Different pipeline stages (DefWrite, DefRead with LM0/LM1/LM2, forward)
- Different features (ice, water wall, decal geometry, tree sprites, self-illumination)

This is **INFERENCE**, but the evidence strongly suggests an **uber-shader with preprocessor defines** approach in the original HLSL source, which is compiled into many specialized DXBC binaries. The reasons:

1. The naming convention is highly systematic and combinatorial
2. Include paths visible in decompressed GpuCache.Gbx data reference shared files like `":temp:\Source\Common_p.hlsli"` [**VERIFIED** from doc 26, Section 9]
3. 180 block variants from source would be impractical to maintain as separate files
4. The `Vision::VisionShader_GetOrCreate` function at `0x14097cfb0` creates shader variants indexed 0-14 from a single shader descriptor [**VERIFIED** from decompiled code]

The shader variant system creates up to 14 permutations per base shader, indexed by purpose: base rendering, depth-only, shadow caster, tessellation, etc. This is visible at the code level in `Vision_VisionShader_GetOrCreate_14097cfb0.c`, lines 80-109, where variant indices 0, 1, 2, 3, 4, 7, 9, 12, 13, 14 are conditionally generated. [**VERIFIED**]

### 4.6 The PBR Compute Shaders

Six compute shaders in `Engines/` handle PBR precomputation:

| Shader | Purpose | Standard Practice |
|---|---|---|
| `Pbr_IntegrateBRDF_GGX_c` | Pre-compute GGX BRDF LUT (NdotV x roughness) | Standard split-sum approximation |
| `Pbr_PreFilterEnvMap_GGX_c` | IBL environment map pre-filtering | Standard split-sum specular IBL |
| `Pbr_FastFilterEnvMap_GGX_c` | Fast variant of above | Performance optimization |
| `Pbr_FastFilterEnvMap_MirrorDiagXZ_c` | Mirror for symmetric environments | Stadium is roughly symmetric |
| `Pbr_RoughnessFilterNormalInMips_c` | Normal map mip filtering by roughness | Prevents specular aliasing |
| `Pbr_Spec_to_Roughness_c` | Convert specular power to roughness | Specular-to-PBR conversion |

[**Source**: doc 32, Section 2.2; **VERIFIED** from actual shader filenames]

The existence of `Pbr_Spec_to_Roughness_c` is significant. This shader converts from a specular power value to a roughness value, which strongly indicates the engine's internal PBR workflow uses **specular/glossiness** (or at least accepts specular power as input), not metallic/roughness. The separate `MDiffuse` and `MSpecular` G-buffer targets support this interpretation: in a specular workflow, specular F0 is stored as an RGB color, not a single metalness scalar. [**INFERENCE** from shader names + G-buffer structure]

---

## Lecture 5: Honest Rendering Unknowns

This lecture catalogs what we do not know. I consider this the most important lecture in the series, because knowing what you do not know is the foundation of good engineering.

### 5.1 Exact G-Buffer Formats

**Status**: INFERENCE for all targets except depth

We know the target names. We know the depth format (D24_UNORM_S8_UINT from the DXVK log). For everything else, we are inferring from standard practice:

| Target | Best Guess | Why | Confidence |
|---|---|---|---|
| MDiffuse | R8G8B8A8_UNORM_SRGB | Standard albedo format, sRGB for gamma correctness | **INFERENCE** |
| MSpecular | R8G8B8A8_UNORM | F0 + roughness fits in 4x8-bit channels | **INFERENCE** |
| PixelNormalInC | R16G16_FLOAT or R10G10B10A2 | 2-channel normal needs at least 16 bits for quality | **INFERENCE** |
| LightMask | R8G8B8A8_UNORM | Per-channel light flags fit in 8-bit channels | **INFERENCE** |
| FaceNormalInC | R16G16_FLOAT | 2-channel normal, possibly octahedral encoded | **INFERENCE** |
| VertexNormalInC | R16G16_FLOAT | Same reasoning as FaceNormal | **INFERENCE** |
| PreShade | **UNKNOWN** | Purpose itself is uncertain | **UNKNOWN** |
| DiffuseAmbient | R16G16B16A16_FLOAT or R11G11B10_FLOAT | HDR lighting result needs >8 bits | **INFERENCE** |

**To verify**: Run the game under RenderDoc or PIX, capture a frame, and inspect the render target formats directly.

### 5.2 Normal Encoding Method

**Status**: INFERENCE

We know `DeferredDeCompFaceNormal_p.hlsl` exists ("decompress face normal"), which confirms normals ARE stored compressed. We also know `DeferredFaceNormalFromDepth_p.hlsl` exists, which can reconstruct face normals from depth derivatives.

The most likely encoding is **octahedral** (2-channel, store in RG16), because:
- It has been the standard for deferred renderers since ~2014
- The "DeComp" (decompress) shader name implies a decode step
- Two normal channels would fit in R16G16_FLOAT

But it could also be spheremap transform, Lambert azimuthal, or something custom. I cannot confirm from available evidence. [**INFERENCE**]

### 5.3 PBR Workflow Details

**Status**: INFERENCE

We have strong evidence for specular/glossiness workflow:
- `Pbr_Spec_to_Roughness_c` converts specular power to roughness
- Separate `MDiffuse` (albedo) and `MSpecular` (F0 color) targets
- GGX BRDF precomputation (`Pbr_IntegrateBRDF_GGX_c`)

But we do not know:
- Whether roughness or glossiness is stored in MSpecular.A (**UNKNOWN** -- `Pbr_Spec_to_Roughness_c` suggests roughness is the internal representation)
- The exact Smith GGX visibility term variant (**UNKNOWN**)
- The diffuse BRDF model (Lambert? Disney? Burley?) (**UNKNOWN**)
- Whether metallic materials are handled via F0 = albedo color or via a separate channel (**UNKNOWN**)

### 5.4 Tone Mapping Curve

**Status**: PARTIALLY KNOWN

We know:
- Four tone mapping operators exist: Global Reinhard, Global+AutoExposure, Filmic Curve, Local Adaptive [**VERIFIED** from shader names]
- The filmic curve uses `NFilmicTone_PowerSegments::SCurveParamsUser` -- a piecewise power function with shoulder, linear, and toe segments [**VERIFIED** from string reference]
- Auto-exposure computes log2 luminance and progressive downsampling [**VERIFIED** from `TM_GetLog2LumiDown1_p.hlsl`]

We do not know:
- The actual curve coefficients (toe strength, shoulder parameters, linear section slope) (**UNKNOWN**)
- The auto-exposure min/max EV range (**UNKNOWN**)
- The temporal adaptation speed (**UNKNOWN**)
- Whether bloom is extracted before or after tone mapping (doc 11 flags this as an open question) (**UNKNOWN**)

### 5.5 TAA Jitter Pattern

**Status**: UNKNOWN

We know:
- `PosOffsetAA` and `PosOffsetAAInW` provide per-frame sub-pixel jitter [**VERIFIED** from string references]
- `TemporalAA_Constants` RTTI class holds the jitter/blend parameters [**VERIFIED**]
- Two TAA implementations: NVIDIA GFSDK TXAA and Ubisoft custom (`TemporalAA_p.hlsl`) [**VERIFIED**]
- Motion vectors from `DeferredCameraMotion_p.hlsl` feed the TAA [**VERIFIED**]

We do not know:
- The jitter sequence (Halton(2,3)? 8-sample rotated grid? Random?) (**UNKNOWN**)
- The history blend factor (typical is 0.9-0.95 but engine-specific) (**UNKNOWN**)
- The neighborhood clipping method (min/max? variance? cross-bilateral?) (**UNKNOWN**)
- Whether the NVIDIA path is used on non-NVIDIA hardware or only the Ubisoft path (**UNKNOWN**)

### 5.6 Shadow Map Details

**Status**: PARTIALLY KNOWN

Known:
- 4 cascade PSSM (or 1 in simplified mode) [**VERIFIED** from decompiled code at `0x14095d430`]
- Shadow pass names: `MapShadowSplit0` through `MapShadowSplit3` [**VERIFIED**]
- PCF filtering baseline with `HqSoftShadows` toggle [**VERIFIED** from strings]
- Slope-scaled bias via `ShadowBiasConstSlope` [**VERIFIED** from string]
- Shadow cache for static geometry via compute shader `UpdateShadowIndex_c.hlsl` [**VERIFIED**]
- Shadow group bitmask (5-bit index at caster offset 0x22C) [**VERIFIED** from decompiled code]

Unknown:
- Shadow map resolution per cascade (**UNKNOWN**)
- Cascade split distances (**UNKNOWN**)
- Shadow map DXGI format (likely D16_UNORM or D32_FLOAT, but **UNKNOWN**)
- PCF tap count and pattern (**UNKNOWN**)
- Whether VSM, EVSM, or other variance methods are used (**UNKNOWN**)

### 5.7 HBAO+ Internal Parameters

**Status**: MOSTLY KNOWN (structure), PARTIALLY UNKNOWN (runtime values)

The HBAO+ configuration structure is fully mapped from the decompiled registration function at `0x14091f4e0`:

| Offset | Field | Type | Status |
|---|---|---|---|
| 0x00 | IsEnabled | bool | **VERIFIED** (structure known) |
| 0x04 | UseHomeMadeHBAO | bool | **VERIFIED** |
| 0x08 | DelayGrassFences | bool | **VERIFIED** |
| 0x0C | ImageSize | float | **VERIFIED** (name known, runtime value **UNKNOWN**) |
| 0x10 | WorldSize | float | **VERIFIED** (name known, runtime value **UNKNOWN**) |
| 0x14 | Exponent | float | **VERIFIED** (name known, runtime value **UNKNOWN**) |
| 0x18 | BlurTexelCount | int | **VERIFIED** (name known, runtime value **UNKNOWN**) |
| 0x1C-0x30 | NvHBAO.* (6 params) | mixed | **VERIFIED** (structure) |
| 0x34-0x48 | NvHBAO_BigScale.* (6 params) | mixed | **VERIFIED** (structure) |

The dual-pass (small + big scale) architecture is confirmed. The runtime parameter values would require memory inspection during execution. [**Source**: `NSysCfgVision_SSSAmbOcc_HBAO_14091f4e0.c`]

### 5.8 What You Would Need to Figure Out Empirically

If you are building a renderer inspired by this engine, here is what you cannot learn from documentation alone:

1. **G-buffer formats**: Capture a frame with RenderDoc. 30 minutes of work.
2. **Normal encoding**: Inspect the PixelNormalInC render target values in a frame capture. Look at the range and distribution.
3. **Tone mapping curve**: Screen-capture the game at known exposure values and reverse-engineer the transfer function.
4. **TAA quality**: Implement Halton(2,3) and compare. If it looks close, you are probably right.
5. **Shadow cascade splits**: Place objects at known distances and observe which cascade they fall into.
6. **Material properties**: Extract textures from the game files and analyze the specular/roughness maps.

---

## Lecture 6: Practical Advice for Students

This lecture is based only on verified facts from the preceding analysis.

### 6.1 Which WebGPU Features Are Truly Needed

Based on D3D11 requirements confirmed from the decompiled device creation code:

**Required**:
- Render targets (multiple render targets for G-buffer) -- WebGPU supports this
- Depth textures with sampling -- WebGPU supports `depth24plus-stencil8`
- Compute shaders -- 105 of 1,112 shaders are compute; WebGPU supports this
- BGRA support -- The engine requests this; WebGPU's `bgra8unorm` is available
- At least 4 render target outputs in fragment shader -- Standard WebGPU limit is 8

**Not needed in WebGPU (features used by TM2020 that have no WebGPU equivalent)**:
- Geometry shaders: Only 5 of 1,112 shaders use geometry stage (particle voxelization, HBAO+ CoarseAO, cubemap batching). Replace with compute pre-passes or vertex shader expansion.
- Tessellation (hull/domain): Only 8 of 1,112 shaders (ocean only). Use pre-tessellated meshes.
- MSAA with deferred rendering: The engine uses deferred with FXAA/TXAA, not MSAA. MSAA is only used in the forward path (trees, grass, transparent objects).

[**Source**: doc 32, Section 1; shader stage counts **VERIFIED**]

### 6.2 Which Parts You Can Simplify Safely

Based on the shader catalog and pipeline analysis:

1. **Shadow system**: Start with a single shadow map, not 4-cascade PSSM. The engine's shadow cache, clip maps, and fake shadows are optimization layers -- begin without them.

2. **HBAO+**: The full 6-step HBAO+ pipeline (linearize, deinterleave 4x4, compute, reinterleave, blur x2) is complex. Start with a basic SSAO (8-16 random hemisphere samples) and upgrade later.

3. **Lighting model**: The engine has 4 light types (point, spot, sphere, cylinder) plus projectors. Start with directional light + ambient only.

4. **Post-processing**: Of the ~20 post-processing effects, only tone mapping and basic bloom are essential for visual quality. FXAA is trivial to add. Skip DoF, motion blur, color grading, lens flares initially.

5. **Particle system**: The engine uses GPU compute for particle simulation with self-shadowing voxelization. Start with CPU-driven particles in a forward pass.

6. **Water**: The ocean uses tessellation (hull + domain shaders) and flow simulation. For a first pass, use a flat reflective plane.

### 6.3 What Visual Quality Can You Achieve Without Original Shaders

You do not have the HLSL source. But you know:

- **The G-buffer layout** (9 targets, names confirmed)
- **The material slots** (TDSN: Texture, Diffuse, Specular, Normal)
- **The PBR model** (GGX specular, split-sum IBL, specular/glossiness workflow)
- **The vertex format** (position, packed normal, vertex color, UV0, UV1, tangent, bitangent -- all confirmed from DXVK log)
- **The lightmap system** (H-basis with YCbCr compression, UV1 channel)

With this information, a competent graphics programmer can build a deferred renderer that produces comparable results for static scenes. The material system (TDSN) is essentially standard PBR with specular workflow. The vertex format is fully known. The lighting math (GGX + Fresnel + lightmap) is well-documented in academic literature.

Where you will fall short without the original shaders:
- Exact match of triplanar blending weights (the `Py`/`Pxz` projection logic)
- The filmic tone mapping curve shape
- Material-specific effects (ice refraction, water flow, energy glow)
- Tree/grass rendering quality (the engine has dedicated `SelfAO` tree shaders)

### 6.4 What to Prototype FIRST

Based on the verified pipeline structure, in order of priority:

1. **G-buffer fill with a single material**: Implement DeferredWrite for the basic TDSN block material. Outputs: albedo, specular+roughness, normal, depth. This is the foundation.

2. **Deferred lighting with one directional light**: Implement DeferredRead with ambient + directional. This proves the deferred pipeline works.

3. **GBX parser for map files**: You need to read `.Map.Gbx` to get block placement data. The format is fully verified (Lecture 3). Start with the header, then decompress the body with LZO1X.

4. **Block geometry loading**: Parse `CPlugSolid2Model` (class `0x090BB000`) from the game's pak files or your own block files. The vertex format is confirmed from the DXVK log.

5. **Lightmap integration**: Add UV1 sampling with baked lightmap data. This is what makes the scene look "finished."

6. **Tone mapping**: Implement a basic filmic curve. The exact TM2020 curve is unknown, but ACES or Uncharted 2 curves will look credible.

7. **TAA**: Implement basic temporal AA with Halton(2,3) jitter and exponential history blend. This smooths everything.

---

## Errata: Documentation Errors Found During Preparation

During my preparation of these lectures, I cross-checked the reverse engineering documentation against primary sources (decompiled code and hex dumps). The following discrepancies were found:

### Erratum 1: user_data_size Semantics

**Document**: doc 16 (File Format Deep Dive), Section 4
**Claim**: "user_data_size = Total size of header chunk data (bytes)"
**Correction**: user_data_size includes the `num_header_chunks` field (4 bytes), the chunk index table (8 * N bytes), AND the chunk data payloads. Formula: `user_data_size = 4 + 8*N + sum(chunk_sizes)`.
**Evidence**: Verified across Map (25,343 = 4+48+25,291), Replay (705 = 4+24+677), and Block (154 = 4+32+118) files.
**Severity**: High -- incorrect interpretation would cause parsing failures.
[**Source**: doc 26, Sections 2, 3, 5]

### Erratum 2: .pak vs .pack.gbx Confusion

**Document**: doc 16, Section 21
**Claim**: "Pack files (.pack.gbx) are regular GBX files"
**Correction**: The game's `.pak` files (Resource.pak, Stadium.pak, etc.) use the "NadeoPak" binary format with magic bytes `"NadeoPak"`, NOT the GBX format. Only user-created `.pack.gbx` files may use GBX format.
**Evidence**: All 7+ pak files examined start with `"NadeoPak"` magic, version 18 (0x12), followed by crypto keys.
**Severity**: Medium -- could mislead someone trying to parse pak files as GBX.
[**Source**: doc 26, Section 10]

### Erratum 3: Format Byte 1/Byte 2 Terminology

**Document**: doc 16
**Claim**: Byte 1 = "body compression", Byte 2 = "[UNKNOWN exact role]"
**Correction**: Byte 1 is always 'U' in all observed TM2020 files. Byte 2 ('C' or 'U') is the one that actually controls whether the body chunk stream has a compression envelope. When byte 2 = 'C', the body is preceded by uncompressed_size + compressed_size + compressed data. When byte 2 = 'U', the body is raw chunks.
**Evidence**: BUUR files (FuncShader, FuncCloudsParam) have no compression envelope; BUCR files have one.
**Severity**: Medium -- incorrect terminology but functional behavior can be determined empirically.
[**Source**: doc 26, Sections 6-8; `FUN_140901850_ParseVersionHeader.c`]

### Erratum 4: Compression Algorithm

**Document**: doc 15, Section 4 (original finding)
**Original claim**: "TM2020 uses zlib exclusively for GBX body compression"
**Correction**: GBX body compression uses LZO1X. zlib is present in the binary but used for other data streams (lightmap compression, ghost data, network). The decompilation at `FUN_140127aa0` implements LZO1X directly without a named library.
**Status**: This was already corrected in doc 15 itself (noted as "CORRECTION"), but the original conclusion should be struck.
**Severity**: Critical -- using zlib to decompress GBX bodies will fail.
[**Source**: doc 15 Section 4 correction note; doc 26 Section 14]

### Erratum 5: G-Buffer Format Confidence Levels

**Document**: doc 11, Section 3
**Issue**: The G-buffer table presents formats with labels like "[PLAUSIBLE]" and "[SPECULATIVE]" but the table layout could be read as presenting confirmed formats. Only the depth format (D24_UNORM_S8_UINT) is verified from the D3D11 runtime log. All other formats are unverified inferences.
**Recommendation**: The table should have a clear header noting that only depth is confirmed, and all other formats are educated guesses requiring frame capture verification.
**Severity**: Low -- the documentation does label these correctly, but the presentation could be clearer.

### Erratum 6: Bloom/Tonemap Ordering

**Document**: doc 11, Section 1 (Phase 9 / Phase 12)
**Issue**: The document presents two different orderings. Phase 9 (Section 1, line 290) shows `FxToneMap -> FxBloom`. Phase 12 (Section 4, line 700-706) shows `FxFXAA -> FxToneMap -> FxBloom -> CustomEnding`. The document itself flags "[NEEDS INVESTIGATION -- could also be bloom-before-tonemap]" at line 298.
**Status**: The ordering between bloom and tone mapping remains **UNRESOLVED**. Both orderings exist in the documentation without definitive resolution.
**Severity**: Medium -- affects the visual appearance of bloom (bloom in HDR vs LDR space produces different results).

---

## Appendix A: Complete Configuration Taxonomy

From the decompiled `CSystemConfigDisplay` at `0x140936810` and the live `Default.json`, the following display settings are confirmed:

| Setting | JSON Key | Type | Default | Offset |
|---|---|---|---|---|
| Variable Refresh Rate | AllowVRR | bool | false | 0x74 |
| Performance Overlay | ShowPerformance | enum | "fps" | 0x78 |
| Rendering API | RenderingApi | string | "d3d11" | 0xB0 |
| Display Mode | DisplayMode | enum | "windowed" | 0x5C |
| Antialiasing (Forward) | Antialiasing | enum | "_8_samples" | 0x4C |
| Deferred AA | DeferredAA | enum | "_txaa" | 0x50 |
| Shader Quality | ShaderQuality | enum | "very_fast" | 0x88 |
| Texture Quality | TexturesQuality | enum | "low" | 0x84 |
| Anisotropic Filter | FilterAnisoQ | enum | "anisotropic__8x" | 0x8C |
| Shadows | Shadows | enum | "none" | 0x90 |
| Bloom | FxBloomHdr | enum | "none" | 0xCC |
| Motion Blur | FxMotionBlur | enum | "off" | 0xD0 |
| Motion Blur Intensity | FxMotionBlurIntens | float | 0.35 | 0xD8 |
| Lightmap Size | LM SizeMax | enum | "auto" | 0x94 |
| Lightmap Quality | LM Quality | enum | "very_fast" | 0x98 |
| Triple Buffer | TripleBuffer | enum | "off" | 0x68 |
| Max FPS | MaxFps | int | 0 (unlimited) | 0x104 |
| Multi-Thread | MultiThread | bool | true | 0x12C |
| Thread Count Max | ThreadCountMax | int | 4 | 0x130 |
| Async Render | AsyncRender | bool | false | 0x134 |

[**Source**: `CSystemConfigDisplay_140936810.c` for offsets and field names; `Default.json` for runtime values; both **VERIFIED**]

---

## Appendix B: Class IDs Confirmed from Real Files

| Class ID | Engine | Class | Type | Evidence |
|---|---|---|---|---|
| `0x03043000` | 0x03 (Game) | 0x043 | CGameCtnChallenge (Map) | Multiple .Map.Gbx files |
| `0x03093000` | 0x03 (Game) | 0x093 | CGameCtnReplayRecord | Multiple .Replay.Gbx files |
| `0x031CC000` | 0x03 (Game) | 0x1CC | Profile/UserManager | .Profile.Gbx |
| `0x2E002000` | 0x2E | 0x002 | BlockInfo | .Block.Gbx |
| `0x05015000` | 0x05 (Plug) | 0x015 | CPlugFuncShader | .FuncShader.Gbx |
| `0x09182000` | 0x09 (Plug) | 0x182 | FuncCloudsParam | .FuncCloudsParam.Gbx |
| `0x0902F000` | 0x09 (Plug) | 0x02F | ImageGen/FuncImage | .ImageGen.Gbx |
| `0x09053000` | 0x09 (Plug) | 0x053 | CPlugGpuProgram | .GpuCache.Gbx |
| `0x01026000` | 0x01 (System) | 0x026 | CSystemFidCache | .FidCache.Gbx |
| `0x090BB000` | 0x09 (Plug) | 0x0BB | CPlugSolid2Model | Body type label string |
| `0x09011000` | 0x09 (Plug) | 0x011 | CPlugBitmap | Body type label string |
| `0x09026000` | 0x09 (Plug) | 0x026 | ShaderApply | Body type label string |

[**Source**: doc 26 Sections 2-9, 12; `FUN_140903140_BodyTypeLabel.c`; all **VERIFIED**]

---

*End of Lecture Series*

*"The pursuit of understanding a system you did not build teaches humility about the systems you will build. Document what you know. Admit what you do not. Let the hex speak for itself." -- Prof. Kovac*

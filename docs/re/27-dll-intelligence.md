# DLL Intelligence Report

Deep binary analysis of all DLL/EXE files in the Trackmania 2020 install directory. Every DLL was inspected via `file` and `strings` commands on macOS (CrossOver bottle).

## DLL Summary

| DLL | Size | Purpose | Recreation Relevance |
|-----|------|---------|---------------------|
| `vivoxsdk.dll` | 11.87 MB | Vivox voice chat SDK | LOW |
| `VoiceChat.dll` | 1.24 MB | Nadeo voice wrapper (Harbour SDK) | LOW |
| `upc_r2_loader64.dll` | 426 KB | Ubisoft Connect platform | MEDIUM (auth) |
| `libfbxsdk.dll` | 7.95 MB | Autodesk FBX SDK (asset import) | LOW |
| `anzu.dll` | 3.75 MB | In-game advertising (Anzu.io) | NONE |
| `OpenAL64_bundled.dll` | 1.38 MB | OpenAL Soft 3D audio | HIGH |
| `libwebp64.dll` | 662 KB | WebP image codec | LOW |
| `vorbis64.dll` | 846 KB | Ogg Vorbis audio codec | MEDIUM |
| `ntdll_o.dll` | 672 KB | Wine NTDLL backup | NONE |
| `Openplanet.dll` | 12.17 MB | Mod framework | HIGH (reflection data) |
| `NadeoImporter.exe` | 8.27 MB | Asset pipeline tool | HIGH (class hierarchy) |
| `dinput8.dll` | 14 KB | Openplanet hook loader | NONE |
| `d3dcompiler_47.dll` | 4.15 MB | D3D shader compiler | HIGH (shader target) |

---

## vivoxsdk.dll -- Vivox Voice Chat SDK

Vivox provides real-time voice communication. This SDK handles SIP signaling, audio codecs, and 3D positional audio.

| Property | Value |
|----------|-------|
| Size | 12,441,688 bytes (11.87 MB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| SDK Version | `5.19.2.33478.213423bef1` |
| Build | Unity build pipeline (`c:\build\output\unity\vivox-sdk\`) |

### Protocols and Networking
- **SIP** (Session Initiation Protocol): Primary signaling protocol
  - `sip:confctl-e-` -- Echo conference control
  - `sip:confctl-g-` -- Group conference control
  - `sip:confctl-d-%s%s%s!p-%d-%d-%.3f-%d@%s` -- Dynamic conference URI format
- **XMPP**: Presence/messaging alongside SIP
  - `<?xml version='1.0'?><stream:stream to='` -- XMPP stream setup
  - `VIVOX_XMPP_CLEARTEXT_PORT` -- XMPP cleartext port config
- **STUN/ICE**: NAT traversal
  - `ND_E_CANT_CONTACT_STUN_SERVER_ON_UDP_PORT_3478` -- Standard STUN port
- **RTP/SRTP**: Media transport
  - Built on `amsip-4.0.3-vivox-srtp` -- aMSIP SIP stack with SRTP
- **STRO**: Vivox's proprietary streaming/real-time overlay protocol
- **TLS**: `starttls`, `urn:ietf:params:xml:ns:xmpp-tls`, `VIVOX_IGNORE_SSL_ERRORS`

### Audio Codecs
- **Opus**: Primary codec (`VIVOXVANI_V2_AUDIO_DATA_MONO_OPUS_48000` -- 48kHz)
- **Siren14**: Polycom wideband at 32kHz
- **Siren7**: Polycom narrowband at 16kHz
- **Speex**: Resampler only (not primary codec)

### Audio Processing
- AEC (Acoustic Echo Cancellation)
- AGC (Automatic Gain Control)
- Full per-participant, per-session voice processing pipeline

### Key Exported Functions
```
vx_get_message_internal
vx_issue_request_internal
vx_uninitialize
vx_req_connector_create_create_internal
vx_req_account_login_create_internal
vx_req_session_create_create_internal
vx_req_session_set_3d_position_create_internal
vx_req_session_set_voice_font_create_internal
vx_req_channel_mute_user_create_internal
```

### Source Code Structure (from build paths)
```
vivox.api/          -- Public API layer
vivox.client/       -- Client logic (voiceprocessor, encode)
vivox.stro/         -- STRO protocol (connection, session, RTP)
vivox.media/        -- Audio processing (AEC, AGC)
vivox.media.vxa/    -- Audio unit abstraction
vivox.system/       -- Infrastructure (HTTP, message queue)
vivox.web/          -- Web client
amsip-4.0.3-vivox-srtp/ortp/ -- RTP library (oRTP by Linphone)
```

### Environment Variables
```
VIVOX_BLOCK_OUTBOUND_SIP
VIVOX_BLOCK_RTP_OUT / VIVOX_BLOCK_RTP_IN
VIVOX_ENABLE_PERSISTENT_HTTP
VIVOX_SIP_LOG_LEVEL
VIVOX_STUN_TIMEOUT
VIVOX_XMPP_CLEARTEXT_PORT
VIVOX_IGNORE_SSL_ERRORS
VIVOX_RTP_LOG_LEVEL
VX_VAR_RTP_ENCRYPTION
```

**Relevance**: LOW. Voice chat is not needed for core gameplay. The 3D positional audio support (`vx_req_session_set_3d_position`) reveals that voice positions tie to game coordinates.

---

## VoiceChat.dll -- Nadeo Voice Wrapper (Harbour SDK)

Nadeo's voice chat wrapper built on **Harbour**, a Ubisoft/Nadeo dependency-injection service-container framework.

| Property | Value |
|----------|-------|
| Size | 1,298,648 bytes (1.24 MB) |
| Type | PE32+ executable (DLL) (GUI) x86-64 |
| PDB Path | `D:\Codebase\Nadeo\Out\x64_Release_ImportLib_Harbour\VoiceChat.pdb` |
| Signed By | NADEO SAS |

### Harbour SDK -- Four Voice Backends

The Harbour SDK supports four voice backends compiled into the DLL:

```
HARBOUR_TAG_VOICECHAT_VIVOX            -- Vivox (active)
HARBOUR_TAG_VOICECHAT_GME              -- Tencent GME
HARBOUR_TAG_VOICECHAT_DISCORD          -- Discord voice
HARBOUR_TAG_VOICECHAT_PLAYFAB          -- PlayFab Party voice
```

Trackmania uses Vivox. The framework is multi-backend capable.

### Vivox Configuration Parameters
```
voicechat.vivox.server_url         -- https://hyxd.www.vivox.com/api2
voicechat.vivox.token_issuer       -- Auth token issuer
voicechat.vivox.access_token_key   -- Auth token key
voicechat.vivox.domain             -- Vivox domain
voicechat.vivox.codec_selection    -- Codec choice
voicechat.vivox.codec_bitrate      -- 16/24/32/40 kbit/s options
```

### 3D Positional Audio
```
voicechat.vivox.3d                    -- Enable 3D voice
voicechat.vivox.3d.max_range          -- Max hearing distance
voicechat.vivox.3d.clamping_distance  -- Clamping distance
voicechat.vivox.3d.rolloff            -- Volume rolloff curve
voicechat.vivox.3d.distance_model     -- Distance attenuation model
```

### Text-to-Speech / Speech-to-Text (Accessibility)
```
voicechat.vivox.default_language.text_to_speech
voicechat.vivox.default_language.speech_to_text
TTS_Enable / TTS_Disable
```

**Relevance**: LOW. The Harbour SDK discovery is architecturally interesting but not relevant to gameplay recreation.

---

## upc_r2_loader64.dll -- Ubisoft Connect Platform

A loader stub that dynamically loads the full Ubisoft Connect runtime. Handles authentication, achievements, cloud saves, and social features.

| Property | Value |
|----------|-------|
| Size | 436,032 bytes (426 KB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| PDB Path | `D:\JenkinsWorkspace\workspace\client_build_installer\...` |
| Signed By | Ubisoft Entertainment Sweden AB |

### Complete Exported UPC API (103 functions)

**Initialization**: `UPC_Init`, `UPC_Uninit`, `UPC_Update`, `UPC_ContextCreate`, `UPC_ContextFree`

**Identity**: `UPC_IdGet`, `UPC_NameGet`, `UPC_EmailGet`, `UPC_AvatarGet`, `UPC_TicketGet`

**Application**: `UPC_ApplicationIdGet`, `UPC_LaunchApp`, `UPC_InstallLanguageGet`

**Social**: `UPC_FriendAdd`, `UPC_FriendRemove`, `UPC_FriendListGet`, `UPC_BlacklistAdd`

**Multiplayer**: `UPC_MultiplayerInvite`, `UPC_MultiplayerSessionGet/Set/Clear`

**Achievements**: `UPC_AchievementListGet`, `UPC_AchievementUnlock`

**Store/Products**: `UPC_ProductListGet`, `UPC_ProductConsume`, `UPC_StoreCheckout`, `UPC_StorePartnerGet`

**Cloud Storage**: `UPC_StorageFileOpen/Close/Read/Write/Delete`

**Overlay**: `UPC_OverlayShow`, `UPC_OverlayBrowserUrlShow`, `UPC_OverlayMicroAppShow`

**Rich Presence**: `UPC_RichPresenceSet`

**Streaming** (Ubisoft+ cloud gaming):
- `UPC_StreamingTypeGet`, `UPC_StreamingDeviceTypeGet`, `UPC_StreamingInputTypeGet`
- `UPC_StreamingNetworkDelayForInputGet/ForVideoGet/RoundtripGet`
- `UPC_StreamingResolutionGet`

**Hardware Scoring**: `UPC_CPUScoreGet`, `UPC_GPUScoreGet`

### Key Findings
- This is a **loader stub**, not the full UPC SDK. It loads the real runtime via `LoadLibraryW`.
- The streaming APIs confirm Trackmania supports **Ubisoft+ cloud gaming**.
- `UPC_StorePartnerGet` indicates Steam store integration alongside Ubisoft Store.

**Relevance**: MEDIUM. The auth ticket system (`UPC_TicketGet`) authenticates with Nadeo services. Cloud storage handles save games/profiles.

---

## libfbxsdk.dll -- Autodesk FBX SDK

Used by NadeoImporter.exe for 3D model import during asset pipeline processing. Not loaded at game runtime.

| Property | Value |
|----------|-------|
| Size | 8,341,944 bytes (7.95 MB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| File Date | 2018-07-09 |

### Supported File Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| FBX Binary | .fbx | Primary format |
| FBX ASCII | .fbx | Human-readable variant |
| FBX Encrypted | .fbx | DRM-protected models |
| 3D Studio | .3ds | Legacy 3DS Max format |
| Alias OBJ | .obj | Wavefront OBJ |
| Collada | .dae | XML-based interchange |
| AutoCAD DXF | .dxf | 2D/3D CAD format |

### Class Hierarchy (106 classes)

Key classes: `FbxScene`, `FbxMesh`, `FbxSkin`, `FbxSkeleton`, `FbxSurfaceMaterial`, `FbxSurfacePhong`, `FbxAnimStack`, `FbxAnimCurve`, `FbxCamera`, `FbxLight`, `FbxImporter`, `FbxExporter`

**Relevance**: LOW. Only used by NadeoImporter.exe, not at game runtime.

---

## anzu.dll -- In-Game Advertising (Anzu.io)

In-game advertising SDK with an embedded JavaScript engine and video ad support.

| Property | Value |
|----------|-------|
| Size | 3,930,968 bytes (3.75 MB) |
| SDK Version | 5.41 |

### Key Findings
- Contains a full JavaScript runtime with polyfills (`setTimeout`, `setInterval`, `document.createEvent`)
- Video ads via Theora codec and animated PNG
- Real-time ad events via MQTT over WebSocket
- Campaign system with placement, interstitials, and display ads

**Relevance**: NONE. Advertising SDK, irrelevant to gameplay.

---

## OpenAL64_bundled.dll -- OpenAL Soft Audio

The game's 3D spatial audio engine. This is the most relevant DLL for browser audio recreation.

| Property | Value |
|----------|-------|
| Size | 1,446,928 bytes (1.38 MB) |
| Version | **1.23.99** (development/pre-release of 1.24) |
| Library | OpenAL Soft |

### Audio Extensions (37 AL + 14 ALC)

Key extensions:
- `AL_EXT_BFORMAT` -- B-format ambisonic
- `AL_EXT_FLOAT32` / `AL_EXT_DOUBLE` -- High-precision samples
- `AL_EXT_source_distance_model` -- Per-source distance model
- `AL_SOFT_source_spatialize` -- Spatialization toggle
- `AL_SOFT_loop_points` -- Loop start/end points
- `ALC_SOFT_HRTF` -- HRTF headphone rendering
- `ALC_EXT_EFX` -- Effects framework (reverb, chorus)
- `ALC_SOFT_output_mode` -- Output mode selection

### Audio Backend
- **WASAPI** -- Primary backend (Windows Audio Session API)
- Full HRTF support for headphone spatialization
- Higher-order ambisonic processing

**Relevance**: HIGH. Web Audio API must replicate: 3D positional audio with distance models, HRTF for headphones, effect chains (reverb), loop points, and buffer streaming.

---

## libwebp64.dll -- WebP Image Codec

| Property | Value |
|----------|-------|
| Size | 677,960 bytes (662 KB) |

75 exported functions covering decoding (17), encoding (10), incremental decoding (8), and picture operations (16). Supports lossy/lossless, alpha channel, YUV/RGB, and incremental streaming decode.

**Relevance**: LOW. Browsers natively support WebP.

---

## vorbis64.dll -- Ogg Vorbis Audio

| Property | Value |
|----------|-------|
| Size | 866,304 bytes (846 KB) |
| Library | Xiph.Org libVorbis |
| Version | **1.3.5** (2015-01-05) |

Exports **both encoder and decoder** functions (40 total). The encoder could be used for replay audio or voice recording.

**Relevance**: MEDIUM. Browsers support Ogg Vorbis natively via `<audio>` and Web Audio API.

---

## ntdll_o.dll -- Wine NTDLL Backup

| Property | Value |
|----------|-------|
| Size | 687,696 bytes (672 KB) |
| Origin | Wine builtin DLL |

Identical in size to `system32/ntdll.dll`. The `_o` suffix stands for "original" -- placed by Openplanet's dinput8.dll hook to preserve the original.

**Relevance**: NONE. Wine/CrossOver infrastructure artifact.

---

## Openplanet.dll -- Mod Framework

The modding framework that injects into the game. Contains the AngelScript engine, ImGui overlay, and game engine reflection system.

| Property | Value |
|----------|-------|
| Size | 12,764,672 bytes (12.17 MB) |
| Version | **1.29.1** |
| Build Path | `e:\Dev\openplanet\Openplanet\Openplanet\` |

### Hooking Architecture
- **Entry Point**: dinput8.dll proxy loads Openplanet.dll
- **Graphics**: Hooks D3D11 swap chain Present for overlay rendering
- **Window**: Intercepts WndProc for input handling
- **Game Logic**: Hooks main update loop and auth token interception

### Code Injection System
```
HookInfo@ Hook(IntPtr ptr, int padding, const string &in func, int pushRegisters = 0, ...)
void Unhook(HookInfo@ hook)
bool ProcIntercept(CMwStack &in)
void InterceptProc(const string &in className, const string &in procName, ...)
string Patch(IntPtr ptr, const string &in pattern)
```

### AngelScript Scripting Engine
Uses AngelScript with coroutine support, compilation logging, and execution timeouts.

### ImGui Overlay
- dear imgui for all UI rendering
- Docking support, DPI scaling
- Custom styling via TOML, custom fonts (DroidSans, ManiaIcons)

### Game Engine Reflection

**Core Access**:
```
CGameCtnApp@ GetApp()                              -- Main application
array<CGameManialinkPage@>@ GetManialinkPages()     -- ManiaLink UI pages
```

**Nod System**:
```
CMwNod@ Preload(CSystemFidFile@ fid)               -- Asset preloading
int GetRefCount(CMwNod@ nod)                        -- Reference counting
CMwNod@ GetOffsetNod(const ?&in nod, uint offset)   -- Raw memory offset access
void SetOffset(const ?&in nod, uint offset, ...)    -- Raw memory write
```

**Relevance**: HIGH. Reflection data reveals actual game engine class names, member layouts, and function signatures.

---

## NadeoImporter.exe -- Asset Pipeline

The offline asset processing tool that converts FBX/OBJ models into GBX game files. Contains the most comprehensive CPlug class listing found in any binary.

| Property | Value |
|----------|-------|
| Size | 8,675,328 bytes (8.27 MB) |
| Type | PE32+ executable (console) x86-64 |
| Crypto | Statically linked OpenSSL (RSA, AES, SHA for GBX signing) |

### GBX File Types Produced/Consumed

**Item/Object**: `.Item.gbx`, `.Mesh.gbx`, `.Shape.gbx`, `.Material.gbx`, `.Texture.Gbx`, `.Skel.gbx`, `.Rig.gbx`, `.Anim.gbx`

**Engine Resources**: `FuncShader.Gbx`, `FuncTree.Gbx`, `Visual.Gbx`, `Material.Gbx`, `MaterialFx.Gbx`, `Decal.Gbx`, `TexturePack.Gbx`

**LOD Processing**: `.Reduction40.Gbx`, `.Remesh.Gbx`, `.ReductionRetextured.Gbx`, `.Impostor.Gbx`, `.GpuCache.Gbx`

### Vehicle Data

All vehicle ObjectInfo references:
```
\Trackmania\Items\Vehicles\BayCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\CanyonCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\CoastCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\DesertCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\IslandCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\LagoonCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\RallyCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\SnowCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx
\Trackmania\Items\Vehicles\ValleyCar.ObjectInfo.Gbx
```

### Complete CPlug Class Hierarchy (250+ classes)

**Visual/Rendering** (40+): `CPlugVisual`, `CPlugVisual3D`, `CPlugVisualIndexedTriangles`, `CPlugTree`, `CPlugSolid2Model`, `CPlugLight`, `CPlugBitmap`, `CPlugBitmapRender*` (13 variants)

**Materials/Shaders** (15+): `CPlugMaterial`, `CPlugMaterialCustom`, `CPlugMaterialFx*`, `CPlugShader`, `CPlugShaderApply`, `CPlugShaderGeneric`

**Animation** (50+): `CPlugAnimClip`, `CPlugAnimGraph`, `CPlugAnimRigNode_*` (25+ variants including `Blend`, `Blend2d`, `ClipPlay`, `JointIK2`, `StateMachine`, `LayeredBlend`)

**Vehicle** (17): `CPlugVehicleCarPhyShape`, `CPlugVehicleGearBox`, `CPlugVehiclePhyModelCustom`, `CPlugVehicleWheelPhyModel`, `CPlugVehicleVisModel*`, camera models (Race, Race2, Race3, Internal, Helico, HMD)

**Physics/Dynamics**: `NPlugDyna::SKinematicConstraint`, `NPlugDyna::SConstraintModel`, `NPlugDyna::SForceFieldModel`, `CPlugDynaModel`, `CPlugDynaObjectModel`, `CPlugDynaWaterModel`

**Particles/VFX** (15+): `CPlugParticleEmitterModel`, `CPlugParticleGpuModel`, `CPlugFxSystem`, `CPlugFxLensFlareArray`, `CPlugVFXNode_*`

**Audio** (12): `CPlugSound`, `CPlugSoundEngine`, `CPlugSoundEngine2`, `CPlugSoundMood`, `CPlugSoundSurface`, `CPlugMusic`

**Terrain/Environment**: `CPlugClouds`, `CPlugFogMatter`, `CPlugFogVolume`, `CPlugWeather`, `CPlugMoodSetting`, `CPlugDayTime`, `CPlugGrassMatterArray`

### Shader System Strings
```
DiffuseIntensity, DoSpecular, SpecularRGB, DynaSpecular
Normal, CameraNormal, WorldNormal, EyeNormal
NormalRotate, NormalAreSigned, NoMipNormalize
OpacityIsDiffuseAlpha, LightMapOnly
```

These reveal a **PBR-adjacent material system** with diffuse, specular, normal mapping, and lightmap support.

### Texture Processing
- DDS output (`mipmapped_texture::write_dds`)
- Crunch texture compression (`crn_comp_params`)
- Texture cropping, clamping, and resampling

**Relevance**: HIGH. The complete CPlug class hierarchy reveals the game's data structures. Vehicle physics classes, material system, and LOD pipeline are directly relevant.

---

## dinput8.dll -- Openplanet Hook Loader

A tiny proxy DLL that bootstraps Openplanet into the game process.

| Property | Value |
|----------|-------|
| Size | 14,336 bytes (14 KB) |
| Export | `DirectInput8Create` (single function) |

### Hook Sequence
1. Check `UPLAY_ARGUMENTS` environment variable
2. Check if Pause key held (bypass: `Pause key held - not loading Openplanet.`)
3. Find `Openplanet\Lib` subdirectory
4. Modify `PATH` to include Openplanet libraries
5. Load `Openplanet.dll` via `LoadLibraryA`
6. Call `DinputInit` function in Openplanet.dll
7. Load original `\dinput8.dll` from system directory
8. Forward `DirectInput8Create` calls to real DLL

**Relevance**: NONE. Mod framework hook mechanism.

---

## d3dcompiler_47.dll -- D3D Shader Compiler

Microsoft's shader compiler supporting all D3D11 shader stages.

| Property | Value |
|----------|-------|
| Size | 4,346,120 bytes (4.15 MB) |

### Shader Model Support
- All six stages: Vertex, Pixel, Geometry, Hull, Domain, Compute
- Shader Model 5.0 (D3D11) with D3D11.1 extensions
- UAVs at every shader stage
- `StructuredBuffer`, `Texture2D`, `Texture2DArray`, `Texture2DMS`
- D3D11 Linker for shader linking

**Relevance**: HIGH. Confirms SM5/D3D11.1 as the shader target. WebGPU's WGSL must replicate equivalent functionality.

---

## DLL Dependency Map

```
Trackmania.exe (not present in CrossOver install)
  |
  +-- d3dcompiler_47.dll          [Microsoft D3D Shader Compiler]
  +-- OpenAL64_bundled.dll        [OpenAL Soft 1.23.99 - 3D Audio]
  +-- vorbis64.dll                [Xiph libVorbis 1.3.5 - Audio Codec]
  +-- libwebp64.dll               [Google WebP - Texture Codec]
  +-- vivoxsdk.dll                [Vivox SDK 5.19.2 - Voice Chat]
  +-- VoiceChat.dll               [Nadeo/Harbour - Voice Wrapper]
  |     +-- vivoxsdk.dll          (runtime dependency)
  +-- upc_r2_loader64.dll         [Ubisoft Connect Platform]
  |     +-- KERNEL32.dll          (LoadLibraryW for UPC runtime)
  +-- anzu.dll                    [Anzu 5.41 - In-Game Ads]
  |
  +-- dinput8.dll                 [Openplanet Hook Proxy]
        +-- Openplanet.dll        [Openplanet 1.29.1 - Mod Framework]
              +-- (hooks into Trackmania.exe at runtime)

NadeoImporter.exe                 [Asset Pipeline Tool]
  +-- libfbxsdk.dll               [Autodesk FBX SDK ~2018]
  +-- OpenSSL (static)            [Crypto for GBX signing]

ntdll_o.dll                       [Wine NTDLL backup - not loaded]
```

---

## Third-Party SDK Version Catalog

| SDK | Version | Vendor | Purpose | Confirmed |
|-----|---------|--------|---------|-----------|
| Vivox SDK | 5.19.2.33478 | Vivox (Unity) | Voice chat | YES (string) |
| Harbour SDK | Unknown | Ubisoft/Nadeo | Service framework | YES (strings) |
| Anzu SDK | 5.41 | Anzu.io | In-game advertising | YES (string) |
| OpenAL Soft | 1.23.99 | OpenAL Community | 3D spatial audio | YES (string) |
| libVorbis | 1.3.5 (2015-01-05) | Xiph.Org | Audio codec | YES (string) |
| libWebP | Unknown exact | Google | Image codec | YES (exports) |
| Autodesk FBX SDK | ~2018 | Autodesk | 3D model import | YES (file date) |
| D3D Compiler | 47 | Microsoft | Shader compilation | YES (filename) |
| OpenSSL | Unknown | OpenSSL Project | Crypto (static in NadeoImporter) | YES (strings) |
| aMSIP | 4.0.3 | Linphone/Vivox fork | SIP stack (in Vivox) | YES (path) |
| oRTP | Unknown | Linphone | RTP transport (in Vivox) | YES (path) |
| ixwebsocket | Unknown | IXWebSocket | WebSocket (in Anzu) | YES (string) |
| AngelScript | Unknown | angelcode.com | Scripting (in Openplanet) | YES (string) |
| dear imgui | Unknown | Omar Cornut | UI overlay (in Openplanet) | YES (string) |
| AsmJit | 2008-2025 | AsmJit Authors | JIT assembly (in Openplanet) | YES (copyright) |
| Crunch | Unknown | Rich Geldreich | Texture compression (in NadeoImporter) | YES (string) |
| zlib/unzip | 1.01 | Gilles Vollant | ZIP decompression (in NadeoImporter) | YES (string) |

---

## Cross-Reference with Existing Docs

### Confirmations of 09-game-files-analysis.md
- Anzu SDK version 5.41: **CONFIRMED**
- dinput8.dll as Openplanet proxy: **CONFIRMED**, expanded with full hook sequence
- libfbxsdk.dll as Autodesk FBX: **CONFIRMED**, expanded with complete class list
- OpenAL for 3D audio: **CONFIRMED**, version now identified as 1.23.99
- ntdll_o.dll as Wine backup: **CONFIRMED**, size comparison proves identity

### New Findings Not in Existing Docs

1. **Vivox SDK version 5.19.2.33478** -- Previously unversioned
2. **Vivox codec support**: Opus (default), Siren14, Siren7
3. **Vivox protocol stack**: SIP + XMPP + STRO + RTP/SRTP
4. **Harbour SDK framework** in VoiceChat.dll
5. **Four voice backends**: Vivox, Tencent GME, Discord, PlayFab Party
6. **Vivox server URL**: `https://hyxd.www.vivox.com/api2`
7. **3D positional voice chat** parameters (max_range, rolloff, distance_model)
8. **Text-to-speech/Speech-to-text** accessibility features
9. **Complete UPC API** (103 functions) including cloud streaming support
10. **Ubisoft+ cloud gaming** APIs in UPC loader
11. **OpenAL Soft 1.23.99** with 37 AL + 14 ALC extensions
12. **HRTF headphone spatialization** support
13. **250+ CPlug engine classes** in NadeoImporter (previously ~50 known)
14. **NPlugDyna::SKinematicConstraint** confirmed in NadeoImporter
15. **Vehicle physics classes**: `CPlugVehicleCarPhyShape`, `CPlugVehicleGearBox`, `CPlugVehiclePhyModelCustom`
16. **Shader system material properties**: DiffuseIntensity, DoSpecular, NormalRotate, LightMapOnly
17. **LOD pipeline**: Reduction40, Remesh, ReductionRetextured, Impostor
18. **Crunch texture compression** in NadeoImporter

---

## Related Pages

- [09-game-files-analysis.md](09-game-files-analysis.md) -- Initial game files analysis this report expands
- [24-audio-deep-dive.md](24-audio-deep-dive.md) -- Audio system using OpenAL
- [05-rendering-graphics.md](05-rendering-graphics.md) -- Rendering pipeline using D3D11/shader compiler
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Openplanet plugin data extraction
- [07-networking.md](07-networking.md) -- Networking using UPC auth and Nadeo services

---

<details><summary>Analysis metadata</summary>

- **Analysis Date**: 2026-03-27
- **Install Path**: `/Users/kelvinnewton/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Trackmania/`
- **Tools**: `file`, `strings` commands on macOS (CrossOver bottle)
- **Binary types analyzed**: PE32+ x86-64 DLLs and EXEs

</details>

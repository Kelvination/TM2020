# 09 - Trackmania 2020 Game Files Analysis

> Comprehensive reverse-engineering analysis of all files in the Trackmania install directory.
>
> **Install Path**: `/Users/kelvinnewton/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Trackmania/`
>
> **Analysis Date**: 2026-03-27

---

## Table of Contents

1. [DLL Analysis](#1-dll-analysis)
2. [NadeoImporterMaterialLib.txt - Complete Material Database](#2-nadeoimportermateriallibtxt---complete-material-database)
3. [Pack Files](#3-pack-files)
4. [GfxDevicePerfs.txt - GPU Performance Database](#4-gfxdeviceperfstxt---gpu-performance-database)
5. [Openplanet Directory](#5-openplanet-directory)
6. [DXVK / D3D11 Log Analysis](#6-dxvk--d3d11-log-analysis)
7. [NadeoImporter.exe - Asset Pipeline](#7-nadeoimporterexe---asset-pipeline)
8. [updater_files.txt - Update System](#8-updater_filestxt---update-system)
9. [Nadeo.ini - Configuration](#9-nadeoini---configuration)
10. [Shader System (GpuCache)](#10-shader-system-gpucache)
11. [Key Findings for Browser Recreation](#11-key-findings-for-browser-recreation)

---

## 1. DLL Analysis

### 1.1 anzu.dll - In-Game Advertising SDK (Anzu.io)

**File Size**: 3,930,968 bytes (3.75 MB)
**Evidence**: Strings `Anzu SDK 5.41 is being initialized`, `https://l1-1.anzu.io/`, `AnzuSDK/5.41 (native;`
**Confidence**: VERIFIED

**Purpose**: Anzu.io is an in-game advertising SDK that renders programmatic ads on 3D surfaces within the game world (billboards, track-side screens). This is NOT cosmetic -- it dynamically fetches and renders real ad content onto in-game textures.

**Key functionality strings found**:
- `AnzuSDK_Init(` -- SDK initialization entry point
- `https://l1-1.anzu.io/` -- Anzu L1 (first-level) server endpoint
- `RenderScreen` -- Renders ad content to screen surfaces
- `placement` -- Ad placement system
- `impression` -- Ad impression tracking
- `interstitial` -- Interstitial ad format support
- `video` / `videotextures` -- Video ad support
- `texture` / `web texture id=%d entrypoint` -- Web-sourced texture rendering
- `mqtt message for %s : %s` -- MQTT-based real-time ad updates
- `Anzu Scheduler Thread` -- Background thread for ad scheduling
- `AnzuSDK/5.41 (native;` -- HTTP User-Agent identifying SDK version
- `ScriptableSDKObj.prototype.` -- Embedded JavaScript engine for ad logic
- JavaScript polyfills for `window.setInterval`, `window.setTimeout`, `Date.now`, `console.log`
- `error extracting %s from zip` -- Downloaded ad assets arrive as zip packages
- `PNG Decoder Error` -- PNG image decoding for ad textures
- `anzu::PngAnimatedTexture::ReadPng` -- Animated PNG texture support
- `anzu::BaseAnimatedTexture::OnStreamOpened` -- Streaming texture support
- `Error on channel '%s': Creating duplicate channels` -- Ad channel system

**Version**: 5.41
**Network**: HTTPS to `l1-1.anzu.io`, MQTT for real-time updates
**Relevance to browser recreation**: LOW -- This is a monetization SDK. No gameplay impact. Browser version would not need this.

---

### 1.2 d3dcompiler_47.dll - Microsoft D3D Shader Compiler

**File Size**: 4,346,120 bytes (4.15 MB)
**Evidence**: Strings `Microsoft (R) D3D Shader Disassembler`, `Microsoft (R) Optimizing Compiler`, HLSL-related strings
**Confidence**: VERIFIED

**Purpose**: Official Microsoft Direct3D shader compiler. Compiles HLSL shaders at runtime when precompiled cache misses occur.

**Key functionality strings found**:
- `PixelShader`, `VertexShader`, `GeometryShader`, `HullShader`, `DomainShader`, `ComputeShader` -- All shader stages supported
- `S_COMPILE2`, `S_COMPILE3` -- PDB symbol types for compiled shaders
- `S_DEFRANGE_HLSL`, `S_GDATA_HLSL`, `S_LDATA_HLSL` -- HLSL debug info types
- `UAVs at every shader stage` -- Unordered Access Views at all stages (DX11.1 feature)
- `SV_RenderTargetArrayIndex or SV_ViewportArrayIndex from any shader feeding rasterizer` -- Advanced instanced rendering
- `enable11_1ShaderExtensions` -- D3D 11.1 shader extension support
- `Shader extensions for 11.1` -- Confirms D3D11.1 feature requirements
- `Microsoft (R) D3DX9 Shader Disassembler` -- Legacy D3DX9 support included
- `D3DCOMPILER_DISASSEMBLY_FORCE_HEX_LITERALS` -- Disassembly flag

**Relevance to browser recreation**: HIGH -- Tells us Trackmania uses D3D11.1 features. WebGPU/WebGL2 must replicate equivalent shader functionality. Shader model SM5 is the target.

---

### 1.3 dinput8.dll - Openplanet Hook Loader (DirectInput8 Proxy)

**File Size**: 14,336 bytes (14 KB)
**Evidence**: Strings `Starting on %d-%02d-%02d`, `Openplanet.dll`, `DirectInput8Create`, `G:\Games\Trackmania\dinput8.pdb`
**Confidence**: VERIFIED

**Purpose**: This is NOT the real DirectInput8 DLL. It is a tiny proxy/hook DLL placed by Openplanet that intercepts the game's attempt to load dinput8.dll. It loads the real dinput8.dll from the system directory and also injects Openplanet.dll.

**Hook mechanism (verified from strings)**:
1. `[%02d:%02d:%02d]` -- Timestamped logging
2. `UPLAY_ARGUMENTS` -- Checks environment variable
3. `Pause key held - not loading Openplanet.` -- Pause key bypass for troubleshooting
4. `Finding libs path` -- Locates `Openplanet\Lib` subdirectory
5. `Updating PATH to add: '%s'` -- Modifies PATH to include Openplanet libraries
6. `Attaching DLL to: '%s'` -- Identifies target process (Trackmania.exe)
7. `Openplanet.dll` / `Failed to load Openplanet module, error %d` -- Loads main Openplanet DLL
8. `Try installing this: https://aka.ms/vs/17/release/vc_redist.x64.exe` -- MSVC runtime dependency
9. `Assuming you are on Wine/Linux` -- Wine/CrossOver detection
10. `\dinput8.dll` / `Couldn't load original dinput8.dll!` -- Loads real dinput8.dll from system directory
11. `DirectInput8Create` -- Exported function that forwards to real DLL

**PDB Path**: `G:\Games\Trackmania\dinput8.pdb` (developer build path)
**Relevance to browser recreation**: NONE -- Mod framework hook, not part of game.

---

### 1.4 libfbxsdk.dll - Autodesk FBX SDK (2018)

**File Size**: 8,341,944 bytes (7.95 MB)
**Evidence**: Strings `FbxScene`, `FBX Extensions SDK`, `FbxSDKBindPose`, `FbxImporter`, file date 2018-07-09
**Confidence**: VERIFIED

**Purpose**: Autodesk FBX SDK for importing 3D model files (.fbx format). Used by NadeoImporter.exe to convert FBX models into Nadeo's internal GBX format.

**Key classes found in strings**:
- `FbxScene` -- Scene container
- `FbxNode`, `FbxMesh`, `FbxSkin`, `FbxCluster` -- Mesh and skinning
- `FbxBlendShape`, `FbxBlendShapeChannel` -- Morph targets
- `FbxAnimEvaluator` -- Animation evaluation
- `FbxGeometryConverter` -- Geometry conversion utilities
- `FbxImporter`, `FbxIOSettings` -- File import pipeline
- `FbxGlobalSettings`, `FbxSystemUnit` -- Scene units/settings
- `FbxPose`, `FbxCharacterPose` -- Character poses
- `FbxDocument`, `FbxLibrary` -- Document management

**Build Date**: July 9, 2018
**Relevance to browser recreation**: LOW -- Only used for asset import pipeline, not runtime.

---

### 1.5 libwebp64.dll - WebP Image Codec

**File Size**: 677,960 bytes (662 KB)
**Evidence**: Strings `WebPDecode`, `WebPEncode`, `SharpYuv`, `libwebp64.dll`
**Confidence**: VERIFIED

**Purpose**: Google WebP image format encoder/decoder. Used for texture compression in the game.

**Exported functions (sample)**:
- `WebPDecode`, `WebPDecodeRGBA`, `WebPDecodeRGBAInto` -- Decoding
- `WebPEncode`, `WebPEncodeBGR` -- Encoding
- `WebPConfigInitInternal`, `WebPConfigLosslessPreset` -- Configuration
- `WebPBlendAlpha`, `WebPCleanupTransparentArea`, `WebPCopyPixels` -- Pixel operations
- `SharpYuvComputeConversionMatrix`, `SharpYuvGetVersion` -- YUV conversion

**Relevance to browser recreation**: MEDIUM -- Browser natively supports WebP, but understanding the texture pipeline is useful.

---

### 1.6 ntdll_o.dll - Wine/CrossOver NTDLL Backup

**File Size**: 687,696 bytes (672 KB)
**Evidence**: String `Wine builtin DLL` at offset 0, `ntdll.dll` references, `wine: could not open working directory`
**Confidence**: VERIFIED

**Purpose**: This is a backup/original copy of Wine's `ntdll.dll`. The `_o` suffix indicates it was renamed by Openplanet or CrossOver during the DLL hooking process. The real ntdll.dll in the system directory may have been replaced or patched, and this is the original Wine builtin version.

**Key strings**:
- `Wine builtin DLL` -- Identifies as Wine-generated
- `ntdll` (multiple references) -- Self-identifies as ntdll
- `loaddll` -- DLL loading subsystem
- `LdrSetAppCompatDllRedirectionCallback` -- DLL redirection
- `LdrSetDllManifestProber` -- Manifest probing
- `wine: could not open working directory %s, starting in the Windows directory.`
- `Wrong version definition in manifest file (%s)`

**Relevance to browser recreation**: NONE -- Wine/CrossOver infrastructure artifact.

---

### 1.7 OpenAL64_bundled.dll - OpenAL Soft Audio Library

**File Size**: 1,446,928 bytes (1.38 MB)
**Evidence**: OpenAL buffer/source management strings, extensive audio API
**Confidence**: VERIFIED

**Purpose**: OpenAL Soft -- cross-platform 3D audio API. Bundled with the game to ensure consistent audio behavior across systems.

**Key functionality strings found**:
- Buffer management: `Generating %d buffers`, `Deleting in-use buffer %u`, `Mapping buffer %u`
- Source management: audio source positioning and control
- `Modifying in-use buffer %u's ambisonic layout` -- Ambisonic (spatial) audio support
- `Modifying in-use buffer %u's ambisonic scaling` -- Ambisonic scaling
- `Modifying in-use buffer %u's loop points` -- Audio looping
- `alBufferSamplesSOFT not supported` -- OpenAL Soft extensions
- Extensive error handling for buffer operations

**Audio Features**: 3D positional audio, ambisonic support, loop points, buffer streaming
**Relevance to browser recreation**: HIGH -- Web Audio API can replicate most OpenAL functionality for 3D spatial audio.

---

### 1.8 Openplanet.dll - Openplanet Mod Framework (v1.29.1)

**File Size**: 12,764,672 bytes (12.17 MB)
**Evidence**: String `\$z Openplanet 1.29.1`, `1.29.1 (next, Public, 2026-01-31)`, `e:\Dev\openplanet\`
**Confidence**: VERIFIED

**Purpose**: The main Openplanet modding framework DLL. Provides plugin system, script engine, ImGui overlay, and game hooking infrastructure.

**Version**: 1.29.1 (next, Public, 2026-01-31)
**Build Path**: `e:\Dev\openplanet\` (developer machine)

**Key components identified from strings**:
- **Script Engine**: `Angelscript` -- AngelScript scripting language
- **UI Framework**: `dear imgui` version `1.92.1 WIP` -- ImGui for overlay UI
- **Markdown**: `imgui_md` -- Markdown rendering in ImGui
- **TOML Parser**: `e:\Dev\openplanet\Libs\toml11\include\toml11\parser.hpp`
- **Crypto**: `RC4 for x86_64, CRYPTOGAMS`, `AES for x86_64, CRYPTOGAMS`, `Montgomery Multiplication for x86_64, CRYPTOGAMS`, `VIA Padlock x86_64 module` -- Cryptographic operations (signature verification)
- **AES-NI GCM**: `AES-NI GCM module for x86_64, CRYPTOGAMS` -- Hardware-accelerated encryption

**Game hooks (verified)**:
- `GamePhysics` -- Physics update hook
- `Update_GameAppAsync` -- Async game update hook
- `GamePhysics_Late` -- Late physics hook
- `AllScripts_Before`, `AllScripts_After` -- Script execution hooks
- `Fatal: Unable to detect MainUpdate hook pointer.` -- Main game loop hook
- `Fatal: Unable to detect SetAuthToken hook pointer.` -- Auth system hook
- `SModel` -- Model data access

**Plugin system**: `Plugin render early`, `Plugin render interface`, `Plugin render` -- Multiple render passes for plugins

**Relevance to browser recreation**: LOW -- Mod framework, not game code. However, the hook points reveal game architecture: physics loop, script execution, rendering pipeline order.

---

### 1.9 upc_r2_loader64.dll - Ubisoft Connect (UPC) SDK

**File Size**: 436,032 bytes (426 KB)
**Evidence**: 98 exported `UPC_*` functions found
**Confidence**: VERIFIED

**Purpose**: Ubisoft Connect platform integration library. Handles authentication, achievements, friends, multiplayer sessions, cloud storage, overlay, and store interactions.

**Complete exported API (98 functions)**:

| Category | Functions |
|----------|-----------|
| **Lifecycle** | `UPC_Init`, `UPC_Uninit`, `UPC_Update`, `UPC_ContextCreate`, `UPC_ContextFree`, `UPC_Cancel` |
| **Error** | `UPC_ErrorToString` |
| **Events** | `UPC_EventNextPoll`, `UPC_EventNextPeek`, `UPC_EventRegisterHandler`, `UPC_EventUnregisterHandler` |
| **Achievements** | `UPC_AchievementUnlock`, `UPC_AchievementListGet`, `UPC_AchievementListFree`, `UPC_AchievementImageGet`, `UPC_AchievementImageFree` |
| **User/Identity** | `UPC_IdGet`, `UPC_IdGet_Extended`, `UPC_NameGet`, `UPC_NameGet_Extended`, `UPC_EmailGet`, `UPC_EmailGet_Extended`, `UPC_UserGet`, `UPC_UserFree`, `UPC_UserPlayedWithAdd`, `UPC_UserPlayedWithAdd_Extended`, `UPC_AvatarGet`, `UPC_AvatarFree`, `UPC_ApplicationIdGet` |
| **Friends/Social** | `UPC_FriendListGet`, `UPC_FriendListFree`, `UPC_FriendAdd`, `UPC_FriendRemove`, `UPC_FriendCheck`, `UPC_FriendCheck_Extended`, `UPC_BlacklistHas`, `UPC_BlacklistHas_Extended`, `UPC_BlacklistAdd` |
| **Multiplayer** | `UPC_MultiplayerSessionSet`, `UPC_MultiplayerSessionSet_Extended`, `UPC_MultiplayerSessionGet`, `UPC_MultiplayerSessionFree`, `UPC_MultiplayerInvite`, `UPC_MultiplayerInviteAnswer`, `UPC_MultiplayerSessionClear`, `UPC_MultiplayerSessionClear_Extended` |
| **Cloud Storage** | `UPC_StorageFileListGet`, `UPC_StorageFileListFree`, `UPC_StorageFileOpen`, `UPC_StorageFileClose`, `UPC_StorageFileDelete`, `UPC_StorageFileRead`, `UPC_StorageFileWrite` |
| **Store/Products** | `UPC_ProductListGet`, `UPC_ProductListFree`, `UPC_ProductConsume`, `UPC_ProductConsumeSignatureFree`, `UPC_StoreProductListGet`, `UPC_StoreProductListFree`, `UPC_StoreCheckout`, `UPC_StoreProductDetailsShow`, `UPC_StoreProductsShow`, `UPC_StorePartnerGet`, `UPC_StorePartnerGet_Extended`, `UPC_StoreIsEnabled`, `UPC_StoreIsEnabled_Extended`, `UPC_StoreLanguageSet` |
| **Overlay** | `UPC_OverlayShow`, `UPC_OverlayBrowserUrlShow`, `UPC_OverlayMicroAppShow`, `UPC_OverlayNotificationShow`, `UPC_OverlayNotificationShow_Extended`, `UPC_OverlayFriendInvitationShow`, `UPC_OverlayFriendInvitationShow_Extended`, `UPC_OverlayFriendSelectionShow`, `UPC_OverlayFriendSelectionFree`, `UPC_ShowBrowserUrl` |
| **Install** | `UPC_InstallChunkListGet`, `UPC_InstallChunkListFree`, `UPC_InstallChunksOrderUpdate`, `UPC_InstallChunksOrderUpdate_Extended`, `UPC_InstallChunksPresenceCheck`, `UPC_InstallLanguageGet`, `UPC_InstallLanguageGet_Extended` |
| **Hardware** | `UPC_CPUScoreGet`, `UPC_GPUScoreGet` |
| **Streaming** | `UPC_StreamingCurrentUserCountryFree`, `UPC_StreamingCurrentUserCountryGet`, `UPC_StreamingDeviceTypeGet`, `UPC_StreamingInputGamepadTypeGet`, `UPC_StreamingInputTypeGet`, `UPC_StreamingNetworkDelayForInputGet`, `UPC_StreamingNetworkDelayForVideoGet`, `UPC_StreamingNetworkDelayRoundtripGet`, `UPC_StreamingResolutionFree`, `UPC_StreamingResolutionGet`, `UPC_StreamingTypeGet` |
| **Auth** | `UPC_TicketGet`, `UPC_TicketGet_Extended` |
| **Rich Presence** | `UPC_RichPresenceSet`, `UPC_RichPresenceSet_Extended` |

**UPlay App ID**: 7015 (from Nadeo.ini)
**Relevance to browser recreation**: MEDIUM -- Need to replicate auth flow. The UPC API reveals what platform features Trackmania depends on.

---

### 1.10 vivoxsdk.dll - Vivox Voice Chat SDK (v5.19.2)

**File Size**: 12,441,688 bytes (11.87 MB)
**Evidence**: String `<VivoxSDK><SDK_VERSION>5.19.2.33478.213423bef1</SDK_VERSION>`
**Confidence**: VERIFIED

**Purpose**: Vivox real-time voice communication SDK. Provides voice chat, text-to-speech, speech-to-text, and 3D positional audio communication.

**Version**: 5.19.2.33478.213423bef1
**Protocol**: SIP (Session Initiation Protocol) based, with STUN, RTP, HTTP

**Key features from strings**:
- Voice: `vx_audio_device_hot_swap_event_type_active_capture_device_changed` -- Audio device management
- 3D Spatial: `channel_rolloff_curve_type_inverse_distance_clamped`, `channel_rolloff_curve_type_linear_distance_clamped`, `channel_rolloff_curve_type_exponential_distance_clamped` -- 3D voice rolloff curves
- Channel types: `sip:confctl-e-` (echo), `sip:confctl-g-` (group), `sip:confctl-d-` (direct)
- Session management: `session_media_connecting`, `session_media_connected`, `session_media_disconnected`
- Text: `session_text_connecting`, `session_text_connected`
- Audio processing: `VIVOX_FORCE_NO_AEC` (echo cancellation), `VIVOX_FORCE_NO_AGC` (gain control), `VIVOX_FORCE_NO_VAD` (voice activity detection)
- Buffer management: `aux_buffer_audio_capture`, `aux_buffer_audio_render`
- Recovery: `connection_state_recovering`, `connection_state_recovered`, `connection_state_failed_to_recover`

**Relevance to browser recreation**: LOW -- Voice chat can use WebRTC in a browser implementation.

---

### 1.11 VoiceChat.dll - Nadeo Voice Chat Wrapper

**File Size**: 1,298,648 bytes (1.24 MB)
**Evidence**: Strings `VivoxTrackmania`, `voicechat.vivox.*` config keys, `HARBOUR_TAG_VOICECHAT_VIVOX_*`
**Confidence**: VERIFIED

**Purpose**: Nadeo's wrapper around the Vivox SDK, integrating voice chat into Trackmania's game architecture ("Harbour" framework).

**Configuration keys discovered**:
- `voicechat.vivox.server_url` -- Vivox server URL
- `voicechat.vivox.token_issuer` -- Token authentication issuer
- `voicechat.vivox.access_token_key` -- Access token key
- `voicechat.vivox.log_level` -- Logging verbosity
- `voicechat.vivox.domain` -- Vivox domain
- `voicechat.vivox.channel_uri` -- Channel URI
- `voicechat.vivox.account_uri` -- Account URI
- `voicechat.vivox.profile_id` -- User profile ID
- `voicechat.vivox.token` -- Auth token
- `voicechat.vivox.token_type` -- Token type
- `voicechat.vivox.account_name` -- Account name
- `voicechat.vivox.3d` -- 3D positional audio enabled
- `voicechat.vivox.default_language.text_chat` -- Default text language
- `voicechat.vivox.default_language.voice_chat` -- Default voice language
- `voicechat.vivox.default_language.text_to_speech` -- TTS language
- `voicechat.vivox.default_language.speech_to_text` -- STT language
- `voicechat.vivox.platform_check_permission` -- Permission checks
- `voicechat.vivox.delay_connect` -- Delayed connection
- `voicechat.vivox.logfileName` -- `VivoxTrackmania`

**Default Vivox server**: `https://hyxd.www.vivox.com/api2`

**Harbour Tags** (internal module tagging system):
- `HARBOUR_TAG_VOICECHAT_VIVOX_SDK`
- `HARBOUR_TAG_VOICECHAT_VIVOX_CONFIG`
- `HARBOUR_TAG_VOICECHAT_VIVOX_CONTEXT`
- `HARBOUR_TAG_VOICECHAT_VIVOX_CHANNEL`
- `HARBOUR_TAG_VOICECHAT_VIVOX_USER`
- `HARBOUR_TAG_VOICECHAT_VIVOX_REQUIREMENT`
- `HARBOUR_TAG_VOICECHAT_VIVOX_BINDINGS`
- `HARBOUR_TAG_VOICECHAT_VIVOX_DOTNET`
- `HARBOUR_TAG_VOICECHAT_VIVOX_TEST`
- `HARBOUR_TAG_VOICECHAT_VIVOX_EXAMPLE`

**Operations**: `MuteLocal`, `MuteRemote`, `Unmute`, `SetVoiceDetection`, `ChannelJoin`, `ChannelLeave`

**Relevance to browser recreation**: LOW -- Voice chat is a separate system from core gameplay.

---

### 1.12 vorbis64.dll - Ogg Vorbis Audio Codec

**File Size**: 866,304 bytes (846 KB)
**Evidence**: Strings `Xiph.Org libVorbis I 20150105`, `Xiph.Org libVorbis 1.3.5`
**Confidence**: VERIFIED

**Purpose**: Ogg Vorbis lossy audio codec for game audio (music, sound effects).

**Version**: libVorbis 1.3.5 (January 5, 2015)

**Exported functions**:
- `vorbis_analysis`, `vorbis_analysis_blockout`, `vorbis_analysis_buffer`, `vorbis_analysis_headerout`, `vorbis_analysis_init`, `vorbis_analysis_wrote` -- Encoding
- `vorbis_block_clear`, `vorbis_block_init` -- Block management
- `vorbis_comment_add`, `vorbis_comment_add_tag`, `vorbis_comment_clear`, `vorbis_comment_init` -- Metadata
- `vorbis_dsp_clear` -- DSP cleanup
- `vorbis_encode_init`, `vorbis_encode_init_vbr`, `vorbis_encode_setup_init`, `vorbis_encode_setup_managed`, `vorbis_encode_setup_vbr` -- Encoder setup
- `vorbis_info_blocksize` -- Block size info
- `vorbis_bitrate_addblock`, `vorbis_bitrate_flushpacket` -- Bitrate management
- `vorbis_granule_time` -- Timestamp conversion

**Relevance to browser recreation**: MEDIUM -- Browser can decode Ogg Vorbis natively. Useful to know game audio is in this format.

---

## DLL Summary Table

| DLL | Size | Purpose | Version | Relevance |
|-----|------|---------|---------|-----------|
| `anzu.dll` | 3.75 MB | Anzu.io in-game advertising SDK | 5.41 | LOW |
| `d3dcompiler_47.dll` | 4.15 MB | Microsoft D3D HLSL shader compiler | 47 | HIGH |
| `dinput8.dll` | 14 KB | Openplanet hook loader (DI8 proxy) | N/A | NONE |
| `libfbxsdk.dll` | 7.95 MB | Autodesk FBX SDK for 3D import | 2018 | LOW |
| `libwebp64.dll` | 662 KB | Google WebP image codec | [UNKNOWN] | MEDIUM |
| `ntdll_o.dll` | 672 KB | Wine builtin ntdll backup | N/A | NONE |
| `OpenAL64_bundled.dll` | 1.38 MB | OpenAL Soft 3D audio | [UNKNOWN] | HIGH |
| `Openplanet.dll` | 12.17 MB | Openplanet mod framework | 1.29.1 | LOW |
| `upc_r2_loader64.dll` | 426 KB | Ubisoft Connect platform SDK | R2 | MEDIUM |
| `vivoxsdk.dll` | 11.87 MB | Vivox voice chat SDK | 5.19.2 | LOW |
| `VoiceChat.dll` | 1.24 MB | Nadeo Vivox wrapper | N/A | LOW |
| `vorbis64.dll` | 846 KB | Ogg Vorbis audio codec | 1.3.5 | MEDIUM |

---

## 2. NadeoImporterMaterialLib.txt - Complete Material Database

**File Path**: `NadeoImporterMaterialLib.txt`
**File Size**: 32,786 bytes
**Total Lines**: 1,375
**Confidence**: VERIFIED (entire file read and parsed)

### 2.1 Structure Format

The file uses a custom declaration format:
```
DLibrary(Stadium)                    -- Library declaration (only "Stadium")
DMaterial(MaterialName)              -- Material definition
    DSurfaceId  (SurfaceType)        -- Physics surface type
    DGameplayId (GameplayType)       -- Gameplay modifier type
    DUvLayer    (LayerType, index)   -- UV channel mapping
    DColor0     ()                   -- Color channel (for decals/non-lightmapped)
    DLinkFull   (Path\To\Resource)   -- External resource link for modifier materials
```

### 2.2 Complete Surface ID Enumeration

All unique surface IDs found in the material library:

| Surface ID | Physics Behavior | Materials Using It |
|------------|------------------|--------------------|
| `Asphalt` | Standard road grip | RoadTech, PlatformTech, OpenTechBorders |
| `RoadSynthetic` | Synthetic road surface | RoadBump, ScreenBack |
| `Dirt` | Loose dirt surface | RoadDirt, CustomDirt, PlatformDirt variants |
| `RoadIce` | Icy road surface | RoadIce, PlatformIce variants, PlatformPlastic variants |
| `Plastic` | Plastic surface | ItemInflatableFloor, ItemInflatableMat, ItemObstacle, PoolBorders, WaterBorders, Underwater |
| `Rubber` | Rubber surface | TrackBorders, TrackBordersOff, CustomPlastic, CustomPlasticShiny |
| `Metal` | Metal surface | Technics, TechnicsSpecials, TechnicsTrims, Pylon, ItemPillar, ItemPillar2, ItemTrackBarrier*, ItemBorder, ItemRamp, ItemBase, ItemCactus, ItemLamp*, RaceArchCheckpoint, RaceArchFinish, Speedometer, CustomMetal, CustomMetalPainted, ScreenPusher, ItemSupportConnector, ItemSupportTube, SpeedometerLight_Dyna |
| `ResonantMetal` | Resonant metal | TrackWallClips, Structure |
| `MetalTrans` | Transparent metal | LightSpot, LightSpot2, Ad screens (all), RaceAd6x1, RaceScreenStart*, SpecialSignTurbo, SpecialSignOff, modifier Sign materials, CustomModTrans* |
| `Wood` | Wood surface | TrackWall, CustomRoughWood |
| `Concrete` | Concrete surface | Waterground, ItemCurveSign*, ItemWrongWaySign, CustomConcrete, CustomMod* (Opaque, Colorize, SelfIllum variants) |
| `Grass` | Grass surface | Grass, DecoHill, DecoHill2 |
| `Green` | Green/vegetation | CustomGlass, CustomGrass, PlatformGrass variants |
| `Pavement` | Paved surface | CustomBricks |
| `Ice` | Pure ice surface | CustomIce |
| `Rock` | Rock surface | CustomRock |
| `Sand` | Sandy surface | CustomSand, PlatformDirt DecoHill variants |
| `Snow` | Snowy surface | CustomSnow, PlatformIce DecoHill variants |
| `NotCollidable` | No collision (visual only) | All Decal*, Chrono*, GlassWaterWall, SpecialFX, TriggerFX, CustomModDecal* |

### 2.3 Complete Gameplay ID Enumeration

**Every material in the file has `DGameplayId (None)`.** No gameplay-modifying materials are defined directly in the material library. Gameplay effects (boost, turbo, etc.) are instead applied through the block/item system, not the material system.

### 2.4 UV Layer Configurations

Three UV layer patterns are used:

| Pattern | UV0 | UV1 | Used By |
|---------|-----|-----|---------|
| **Standard Opaque** | `BaseMaterial, 0` | `Lightmap, 1` | Most solid materials |
| **Decal/Non-Lightmapped** | `BaseMaterial, 0` | `DColor0()` | All decals, glass, chrono displays |
| **Lightmap Only** | `Lightmap, 0` | -- | Grass, all Custom* materials |

### 2.5 Complete Material Catalog (by Category)

#### Roads (Lines 3-58)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| RoadTech | Asphalt | Main racing surface |
| RoadBump | RoadSynthetic | Bumpy road variant |
| RoadDirt | Dirt | Dirt road |
| RoadIce | RoadIce | Ice road |
| PlatformTech | Asphalt | Platform surface |
| OpenTechBorders | Asphalt | Open platform borders |
| ItemInflatableFloor | Plastic | Inflatable floor |
| ItemInflatableMat | Plastic | Inflatable mat |
| ItemInflatableTube | Metal | Inflatable tube |

#### Technics (Lines 61-158)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| TrackBorders | Rubber | Track edge barriers |
| TrackBordersOff | Rubber | Track borders (off variant) |
| PoolBorders | Plastic | Pool area borders |
| WaterBorders | Plastic | Water area borders |
| Underwater | Plastic | Underwater surface |
| Waterground | Concrete | Water ground surface |
| TrackWall | Wood | Track walls |
| TrackWallClips | ResonantMetal | Clipping track walls |
| Technics | Metal | General technical surfaces |
| TechnicsSpecials | Metal | Special technical surfaces |
| TechnicsTrims | Metal | Technical trim pieces |
| Pylon | Metal | Support pylons |
| ScreenBack | RoadSynthetic | Screen backing |
| Structure | ResonantMetal | Structural elements |
| LightSpot | MetalTrans | Light fixtures |
| LightSpot2 | MetalTrans | Light fixtures variant 2 |

#### Ad Screens (Lines 161-197)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| Ad1x1Screen | MetalTrans | 1:1 aspect ratio ad screen |
| Ad2x1Screen | MetalTrans | 2:1 aspect ratio ad screen |
| Ad4x1Screen | MetalTrans | 4:1 wide ad screen |
| Ad16x9Screen | MetalTrans | 16:9 widescreen ad screen |
| 16x9ScreenOff | MetalTrans | 16:9 screen (off state) |
| Ad2x3Screen | MetalTrans | 2:3 portrait ad screen |

#### Racing (Lines 200-382)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| RaceArchCheckpoint | Metal | Checkpoint arch structure |
| RaceArchFinish | Metal | Finish line arch |
| RaceAd6x1 | MetalTrans | 6:1 race ad screen |
| RaceScreenStart | MetalTrans | Start screen |
| RaceScreenStartSmall | MetalTrans | Small start screen |
| SpeedometerLight_Dyna | Metal | Dynamic speedometer light |
| Speedometer | Metal | Speedometer display |
| ChronoCheckpoint-XX-XX-XX | NotCollidable | Checkpoint chrono digits (7 digit positions) |
| ChronoFinish-XX-XX-XX | NotCollidable | Finish chrono digits (7 digit positions) |
| Chrono-XX-XX-XX | NotCollidable | General chrono digits (6 digit positions) |

**Chrono digit naming convention**: `Chrono{Type}-{tens_min}-{ones_min}-{tens_sec}-{ones_sec}-{tenths}-{hundredths}-{thousandths}`
Each position: `10-00-00`, `01-00-00`, `00-10-00`, `00-01-00`, `00-00-10`, `00-00-01`, `00-00-001`

#### Deco (Lines 386-410)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| Grass | Grass | Grass (lightmap UV0 only) |
| DecoHill | Grass | Hillside decoration |
| DecoHill2 | Grass | Hillside decoration variant |
| GlassWaterWall | NotCollidable | Glass water wall (visual only) |

#### Item Obstacles (Lines 413-491)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| ItemPillar | Metal | Pillar (obsolete, use ItemPillar2) |
| ItemPillar2 | Metal | Pillar v2 |
| ItemTrackBarrier | Metal | Track barrier |
| ItemTrackBarrierB | Metal | Track barrier variant B |
| ItemTrackBarrierC | Metal | Track barrier variant C |
| ItemBorder | Metal | Item border |
| ItemObstacle | Plastic | Obstacle (no lightmap) |
| ItemRamp | Metal | Ramp |
| ItemObstacleLight | Plastic | Light obstacle (no lightmap) |
| ItemObstaclePusher | Plastic | Pusher obstacle |
| ScreenPusher | Metal | Pusher screen |
| ItemSupportConnector | Metal | Support connector |
| ItemSupportTube | Metal | Support tube |

#### Item Deco (Lines 493-559)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| ItemBase | Metal | Base item surface |
| ItemCactus | Metal | Cactus decoration |
| ItemLamp | Metal | Lamp |
| ItemLampLight/B/C | Metal | Lamp light variants |
| ItemRoadSign | Metal | Road sign |
| ItemCurveSign/B/C | Concrete | Curve signs |
| ItemWrongWaySign | Concrete | Wrong way sign |

#### Decals - Markings (Lines 561-597)
All decals use `NotCollidable` + `BaseMaterial UV0` + `DColor0`:
- DecalCurbs, DecalMarks, DecalMarksItems, DecalMarksRamp, DecalMarksStart, DecalPlatform

#### Decals - Animated Obstacles (Lines 600-624)
- DecalObstaclePusher, DecalObstacleTube, DecalObstacleTurnstileLeft, DecalObstacleTurnstileRight

#### Decals - Sponsors & Branding (Lines 627-712)
Paint/sponsor decals in various configurations:
- DecalPaintLogo4x1, DecalPaint2Logo4x1, DecalPaintLogo8x1, DecalPaint2Logo8x1
- DecalPaintLogo8x1Colorize
- DecalPaintSponsor4x1A/B/C/D (and DecalPaint2 variants)
- DecalSponsor1x1BigA

#### Special Turbo (Lines 714-742)
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| DecalSpecialTurbo | NotCollidable | Turbo decal |
| SpecialSignTurbo | MetalTrans | Turbo sign |
| SpecialFXTurbo | NotCollidable | Turbo visual effect |
| SpecialSignOff | MetalTrans | Sign off state |
| TriggerFXTurbo | NotCollidable | Turbo trigger VFX |

#### Customizable Materials (Lines 744-815)
Custom materials for user-created content. Each uses `Lightmap UV0` only:
| Material | SurfaceId | Notes |
|----------|-----------|-------|
| CustomBricks | Pavement | Brick pattern |
| CustomConcrete | Concrete | Concrete |
| CustomDirt | Dirt | Dirt |
| CustomGlass | Green | Glass |
| CustomGrass | Green | Grass |
| CustomIce | Ice | Ice |
| CustomMetal | Metal | Metal |
| CustomMetalPainted | Metal | Painted metal |
| CustomPlastic | Rubber | Plastic |
| CustomPlasticShiny | Rubber | Shiny plastic |
| CustomRock | Rock | Rock |
| CustomRoughWood | Wood | Rough wood |
| CustomSand | Sand | Sand |
| CustomSnow | Snow | Snow |

#### Modable Materials (Lines 817-901)
Materials supporting custom textures/mods (pairs with numbered variants):
- CustomModAddSelfIllum/2 -- Additive self-illumination
- CustomModOpaque/2 -- Opaque with lightmap
- CustomModColorize/2 -- Colorizable
- CustomModSelfIllum/2 -- Self-illuminating
- CustomModSelfIllumSimple/2 -- Simple self-illuminating
- CustomModTrans/2 -- Transparent (MetalTrans surface)
- CustomModDecal/2 -- Decal (NotCollidable)

#### Modifier Materials with DLinkFull (Lines 905-1375)

These materials use `DLinkFull` to reference external resources in `Media\Modifier\{ModifierName}\{Part}`.

**Each modifier has 4-5 material parts**:
- `{Name}_Decal` -- Ground decal (NotCollidable)
- `{Name}_Sign` -- Sign display (MetalTrans + lightmap)
- `{Name}_SignOff` -- Sign off-state (some modifiers only)
- `{Name}_SpecialFX` -- Visual effect (NotCollidable)
- `{Name}_TriggerFX` -- Trigger visual effect (NotCollidable)

**Complete Modifier List**:

| Modifier | Path | Description |
|----------|------|-------------|
| **Boost** | `Media\Modifier\Boost\*` | Speed boost |
| **Boost2** | `Media\Modifier\Boost2\*` | Speed boost level 2 |
| **Cruise** | `Media\Modifier\Cruise\*` | Cruise control |
| **Fragile** | `Media\Modifier\Fragile\*` | Fragile mode |
| **NoBrake** | `Media\Modifier\NoBrake\*` | No braking |
| **NoEngine** | `Media\Modifier\NoEngine\*` | No engine |
| **NoSteering** | `Media\Modifier\NoSteering\*` | No steering |
| **Reset** | `Media\Modifier\Reset\*` | Car reset |
| **SlowMotion** | `Media\Modifier\SlowMotion\*` | Slow motion |
| **Turbo** | `Media\Modifier\Turbo\*` | Turbo boost |
| **Turbo2** | `Media\Modifier\Turbo2\*` | Turbo level 2 |
| **TurboRoulette** | `Media\Modifier\TurboRoulette\*` | Random turbo |

**Platform Modifier Materials** (modify the platform surface type):

| Modifier | Surface Override | Notes |
|----------|-----------------|-------|
| **PlatformDirt** | Dirt (road), Sand (deco hills) | Dirt platform |
| **PlatformGrass** | Green | Grass platform |
| **PlatformIce** | RoadIce (road), Snow (deco hills) | Ice platform |
| **PlatformPlastic** | RoadIce | Plastic platform (uses ice physics!) |

---

## 3. Pack Files

### 3.1 PAK Files (NadeoPak Format)

All `.pak` files use the `NadeoPak` format.

**Header structure** (from xxd analysis):
```
Offset  Size  Description
0x00    8     Magic: "NadeoPak" (ASCII)
0x08    4     Version: 0x00000012 (18)
0x0C    32    SHA-256 checksum (matches updater_files.txt checksums)
0x2C    4     Flags/type field (varies: 0x00000007, 0x00000000, 0x00000006)
0x30    4     Offset/alignment field (0x00003000 or 0x00004000)
0x34-3F 12    Reserved (zeros)
0x40    varies String table begins ("Titl..." for title-linked packs)
```

**Evidence**: All pak files start with bytes `4e61 6465 6f50 616b 1200 0000`, confirming NadeoPak v18 format. Checksums at offset 0x0C match SHA-256 values in `updater_files.txt`.
**Confidence**: PLAUSIBLE (from hex analysis, no decompiled parser available to confirm header field boundaries)

| Pack File | Size | Description |
|-----------|------|-------------|
| Stadium.pak | 1.63 GB | Main stadium environment (blocks, models, textures) |
| Skins_StadiumPrestige.pak | 959 MB | Prestige car skins |
| RedIsland.pak | 776 MB | Red Island environment theme |
| Trackmania.Title.Pack.Gbx | 744 MB | Title pack (GBX container wrapping NadeoPak) |
| GreenCoast.pak | 569 MB | Green Coast environment theme |
| BlueBay.pak | 530 MB | Blue Bay environment theme |
| WhiteShore.pak | 411 MB | White Shore environment theme |
| Skins_Stadium.pak | 264 MB | Stadium car skins |
| Maniaplanet_Skins.zip | 221 MB | Cross-game skin assets |
| Maniaplanet.pak | 169 MB | Core ManiaPlanet engine assets |
| Maniaplanet_ModelsSport.pak | 123 MB | Sport car models |
| Maniaplanet_Core.pak | 33.7 MB | Core engine resources |
| GpuCache_D3D11_SM5.zip | 16.2 MB | Precompiled D3D11 SM5 shaders |
| Maniaplanet_Flags.zip | 5.89 MB | Country/region flag images |
| Maniaplanet_Painter.zip | 3.45 MB | In-game painting tools |
| Translations.zip | 2.87 MB | Localization files |
| Maniaplanet_Extras.zip | 2.30 MB | Extra media (color gradings, effects) |
| Stadium_Skins.zip | 2.09 MB | Stadium-specific skin overlays |
| Maniaplanet_Live.zip | 1.63 MB | Live service scripts (ManiaApps) |
| Titles.pak | 1.41 MB | Title definitions |
| Resource.pak | 178 KB | Small resource pack |

**Total pack size**: ~6.4 GB

### 3.2 Environment Theme Packs

Four distinct environment themes identified:
- **GreenCoast** (597 MB) -- Lush green coastal theme
- **BlueBay** (556 MB) -- Blue bay/ocean theme
- **RedIsland** (813 MB) -- Red desert/volcanic island theme
- **WhiteShore** (431 MB) -- White/snowy shore theme

**Evidence**: Pack names and updater_files.txt group "TMStadium"
**Confidence**: VERIFIED

### 3.3 Trackmania.Title.Pack.Gbx

**Evidence**: Header starts with `NadeoPak` followed by `nadeo_game` string at offset 0x56, and location string `World|Europe|France|Ile-de-France|Paris` at offset 0x63.
**Confidence**: VERIFIED

This is the title pack that defines Trackmania as a game within the ManiaPlanet engine. Contains title metadata including publisher location (Nadeo, Paris, France).

### 3.4 ZIP Pack Contents

**GpuCache_D3D11_SM5.zip** -- See Section 10 (Shader System) below.

**Maniaplanet_Extras.zip** -- Media assets:
- `Media/Images/Effects/` -- Effect textures (BlackSquare.tga, FramingCenter/Phi/Thirds.dds, Vignette.dds)
- `Media/ColorGradings/` -- Color grading LUTs (~50+ presets: Abyss, Apocalypse, Arcade, Arizona, etc.)

**Maniaplanet_Flags.zip** -- Regional flags:
- `Media/Flags/` -- Thousands of flag images (.dds, .jpg, .png) for countries, states, regions worldwide

**Maniaplanet_Live.zip** -- Live service ManiaApp scripts:
- `Media/ManiaApps/Nadeo/System/` -- Core system scripts
- Subsystems: `Auth`, `NadeoFunctions`, `TrackmaniaAuth`, `advert`, `browser`, `channels`, `chat`, `keys`, `links`, `notifications`
- Script format: `.Script.txt` (ManiaScript) and `.xml` (ManiaLink UI definitions)

**Maniaplanet_Painter.zip** -- Skin painting tools:
- `Media/Painter/Stencils/` -- Brush stencils (EllipseRound, AirBrush, Square, etc.) with Brush.tga and Icon.dds

**Maniaplanet_Skins.zip** -- Skinning system:
- `Skins/Any/Advertisement1x1/` -- Ad screen skins (animated .webm, static .dds/.tga)
- Various themed advertisement skins (Desert, Fall, Snow, Valley, Summer, etc.)
- Stunt-colored variants (Blue, Cyan, Lime, Orange, Pink)
- Rally and Snow themed variants

**Stadium_Skins.zip** -- Stadium-specific skins:
- `Skins/Stadium/Canopy/` -- Canopy glass textures (_D, _N, _R, _D_HueMask) in 4 variants (ConcentricInside, ConcentricOutside, Opaque, TM)
- `Skins/Stadium/ItemFlag/` -- Seasonal flag skins (Fall, Spring, Summer, Winter, Nadeo)
- Texture channels: `_D` (Diffuse), `_N` (Normal), `_R` (Roughness), `_D_HueMask` (Color customization mask)

**Translations.zip** -- Localization:
- 14 language pairs: cs-CZ, de-DE, en-US, es-ES, fr-FR, it-IT, ja-JP, ko-KR, nl-NL, pl-PL, pt-BR, ru-RU, tr-TR, zh-CN
- Format: `.mo` (compiled gettext) with `core.{locale}.mo` + `trackmania.{locale}.mo` per language

---

## 4. GfxDevicePerfs.txt - GPU Performance Database

**File Path**: `GameData/GfxDevicePerfs.txt`
**File Size**: 82,909 bytes
**Total Lines**: 1,050 (1 header + 1,049 GPU entries)
**Confidence**: VERIFIED

### 4.1 Format

```
Vendor Device GVertexMath GPixelMath GOutputBytes GAniso1 GAniso2 GAniso4 GAniso8 GAniso16
```

**Column definitions**:
| Column | Type | Description |
|--------|------|-------------|
| Vendor | Hex | PCI Vendor ID |
| Device | Hex | PCI Device ID |
| GVertexMath | Float | Vertex shader arithmetic throughput benchmark score |
| GPixelMath | Float | Pixel/fragment shader arithmetic throughput benchmark score |
| GOutputBytes | Float | Render output bandwidth benchmark score |
| GAniso1 | Float | Anisotropic filtering x1 texture fill rate |
| GAniso2 | Float | Anisotropic filtering x2 texture fill rate |
| GAniso4 | Float | Anisotropic filtering x4 texture fill rate |
| GAniso8 | Float | Anisotropic filtering x8 texture fill rate |
| GAniso16 | Float | Anisotropic filtering x16 texture fill rate |

Followed by quoted GPU name string.

### 4.2 GPU Vendor Distribution

| PCI Vendor ID | Vendor | GPU Entries |
|---------------|--------|-------------|
| `10DE` | NVIDIA | 621 |
| `1002` | AMD/ATI | 334 |
| `8086` | Intel | 92 |
| `15AD` | VMware | 1 |
| `1AB8` | [UNKNOWN - possibly Parallels] | 1 |

**Total**: 1,049 GPU profiles

### 4.3 Purpose

This database is used by the game's auto-quality settings system. When the game first launches, it identifies the GPU by PCI vendor/device ID and looks up the pre-benchmarked performance scores. These scores determine the default graphics quality preset without requiring an in-game benchmark.

The GAniso columns show anisotropic filtering performance at different levels, allowing the game to choose the optimal aniso level per GPU.

**Evidence**: File named `GfxDevicePerfs.txt`, located in `GameData/`, header row matches benchmark metric naming convention, and values correlate with known GPU relative performance (e.g., RTX 4090 scores higher than GTX 1060).
**Confidence**: VERIFIED

### 4.4 Notable Entries

- Oldest GPUs: ATI Radeon 9500/9600 series (circa 2002-2003)
- Newest GPUs: AMD Radeon RX 7900 series, NVIDIA RTX 40-series, Intel Arc
- Zero-value entries (0.00 across all fields): GPUs known to exist but not benchmarked
- Some anomalous values in GAniso1 column (e.g., 255.34, 1044.63, 1324.65) -- likely measurement errors or driver bugs

---

## 5. Openplanet Directory

**Path**: `Openplanet/`
**Confidence**: VERIFIED

### 5.1 Directory Structure

```
Openplanet/
  cacert.pem          (225,076 bytes) - CA certificate bundle for HTTPS
  DefaultStyle.toml   (1,942 bytes)   - ImGui UI style configuration
  READ_ME.txt         (284 bytes)     - Warning about plugin placement
  Fonts/              - Font files for UI overlay
  Plugins/            - Bundled Openplanet plugins
  Scripts/            - AngelScript core scripts
```

### 5.2 cacert.pem

Standard Mozilla CA certificate bundle (225 KB). Used by Openplanet for HTTPS connections to `openplanet.dev` and other services. Contains the standard set of trusted root certificates.

### 5.3 DefaultStyle.toml

ImGui UI theme configuration in TOML format:

**Style settings**:
- `WindowRounding = 3`, `ChildRounding = 2`, `FrameRounding = 3` -- Rounded corners
- `WindowBorderSize = 0` -- No window borders
- `ScrollbarSize = 14`, `ScrollbarRounding = 2`
- `TabBarOverlineSize = 2`
- `ItemSpacing = [10, 6]`, `IndentSpacing = 22`, `FramePadding = [7, 4]`

**Color scheme** (dark theme with blue accent `#566AFF`):
- Background: `WindowBg = "#202020FD"`, `PopupBg = "#1C1C1CFD"`
- Text: `Text = "#FFFFFF"`, `TextDisabled = "#7F7F7F"`
- Primary accent: `ButtonHovered = "#566AFF"`, `HeaderActive = "#566AFF"`, `CheckMark = "#566AFF"`
- Active: `ButtonActive = "#394CAB"`
- Scrollbar: dark with gray grab handles
- Tables: alternating rows with `#2B2B2BA0` / `#242424A0`

### 5.4 Fonts Directory

| Font File | Size | Description |
|-----------|------|-------------|
| DroidSans.ttf | 41 KB | Google Droid Sans (regular) - main UI font |
| DroidSans-Bold.ttf | 42 KB | Google Droid Sans (bold) |
| DroidSansMono.ttf | 117 KB | Monospace font for code/console |
| ManiaIcons.ttf | 250 KB | ManiaPlanet icon font (game-specific glyphs) |
| Montserrat.ttf | 336 KB | Montserrat (regular) |
| Montserrat-Bold.ttf | 331 KB | Montserrat (bold) |
| Oswald.ttf | 88 KB | Oswald (regular) |
| Oswald-Bold.ttf | 88 KB | Oswald (bold) |

### 5.5 Plugins Directory

Bundled Openplanet plugins (each in its own subdirectory):

| Plugin | Description |
|--------|-------------|
| BigDecor | [UNKNOWN] Possibly landscape/decoration tool |
| Camera | Camera control/manipulation |
| ClassicMenu | Classic menu interface |
| Controls | Input control configuration |
| Discord | Discord Rich Presence integration |
| EditorDeveloper | Map editor development tools |
| Finetuner | Fine-tuning/adjustment tools |
| InfiniteEmbedSize | Removes embed size limitations |
| NadeoServices | Nadeo online services integration |
| PluginManager | Plugin management interface |
| Stats | Statistics display |
| UsefulInformation | Information display overlay |
| VehicleState | Vehicle state monitoring/display |

### 5.6 Scripts Directory

Core AngelScript files with signature verification:

| Script | Size | Description |
|--------|------|-------------|
| Compatibility.as | 4,274 bytes | Compatibility layer for different game versions |
| Compatibility.as.sig | 104 bytes | Digital signature |
| Dialogs.as | 3,043 bytes | Dialog/popup system |
| Dialogs.as.sig | 104 bytes | Digital signature |
| Patch.as | 2,512 bytes | Game patching utilities |
| Patch.as.sig | 104 bytes | Digital signature |
| Plugin_MapAudioFix.as | 965 bytes | Fix for map audio issues |
| Plugin_MapAudioFix.as.sig | 104 bytes | Digital signature |

**Signature system**: Every `.as` script has a corresponding `.sig` file (104 bytes each). This is a code-signing mechanism to prevent tampering with core Openplanet scripts.

### 5.7 READ_ME.txt

```
IMPORTANT!!

Do NOT place your own scripts in the Scripts or Plugins folders here!
When Openplanet updates, this folder is cleared, and you will lose any custom scripts.
Instead, use your Openplanet user data folder to place plugins:
    C:\Users\<Your Name>\OpenplanetNext\
```

### 5.8 OpenplanetHook.log

**File Path**: `OpenplanetHook.log` (in game root, not Openplanet/ directory)
**Size**: 126,720 bytes

Contains timestamped hook injection logs. Each game launch generates 6 log lines:
```
[HH:MM:SS] Starting on YYYY-MM-DD
[HH:MM:SS] Finding libs path
[HH:MM:SS] Updating PATH to add: '...\Openplanet\Lib'
[HH:MM:SS] Attaching DLL to: '...\Trackmania.exe'
[HH:MM:SS] Module handle: XXXXXXXXXXXXXXXX
[HH:MM:SS] DirectInput8Create
```

**Evidence**: First entry dated 2025-10-27, module handles vary between launches (ASLR), target is always `Trackmania.exe`.
**Confidence**: VERIFIED

---

## 6. DXVK / D3D11 Log Analysis

**File Path**: `Trackmania_d3d11.log`
**Size**: 22,121 bytes (354 lines)
**Confidence**: VERIFIED

### 6.1 Runtime Environment

- **DXVK Version**: `cxaddon-1.10.3-1-25-g737aacd` (CrossOver custom build of DXVK)
- **Game**: `Trackmania.exe`
- **D3D Feature Level**: `D3D_FEATURE_LEVEL_11_0`
- **GPU**: Apple M4 (Vulkan backend)
- **Driver**: 0.2.2018 (MoltenVK/Metal translation layer)

### 6.2 Vulkan Extensions Used

Required extensions revealing D3D11 feature needs:

| Extension | D3D11 Feature |
|-----------|---------------|
| VK_EXT_4444_formats | 4-bit-per-channel textures |
| VK_EXT_extended_dynamic_state | Dynamic pipeline state |
| VK_EXT_host_query_reset | CPU-side query management |
| VK_EXT_robustness2 | Robust buffer/image access |
| VK_EXT_shader_demote_to_helper_invocation | Pixel shader helper invocations |
| VK_EXT_shader_stencil_export | Stencil buffer writes from shaders |
| VK_EXT_shader_viewport_index_layer | Instanced rendering to array targets |
| VK_EXT_transform_feedback | Stream output (geometry shader output) |
| VK_EXT_vertex_attribute_divisor | Instanced vertex data |
| VK_KHR_sampler_mirror_clamp_to_edge | Mirror-clamp texture addressing |
| VK_KHR_swapchain | Present/display |
| VK_KHR_timeline_semaphore | GPU synchronization |

### 6.3 Required GPU Features

| Feature | Required | Notes |
|---------|----------|-------|
| robustBufferAccess | YES | Safe out-of-bounds buffer reads |
| fullDrawIndexUint32 | YES | 32-bit index buffers |
| imageCubeArray | YES | Cubemap arrays (environment maps) |
| independentBlend | YES | Per-RT blend states |
| geometryShader | YES | Geometry shaders used |
| tessellationShader | YES | Tessellation used |
| sampleRateShading | YES | Per-sample pixel shading |
| dualSrcBlend | YES | Dual-source blending |
| multiDrawIndirect | YES | Indirect draw calls |
| depthClamp | YES | Depth clamping |
| depthBiasClamp | YES | Depth bias clamping |
| fillModeNonSolid | YES | Wireframe rendering |
| multiViewport | YES | Multiple viewports |
| samplerAnisotropy | YES | Anisotropic filtering |
| textureCompressionBC | YES | BC texture compression (DXT/BCn) |
| occlusionQueryPrecise | YES | Precise occlusion queries |
| pipelineStatisticsQuery | YES | Pipeline statistics |
| shaderImageGatherExtended | YES | Texture gather operations |
| shaderClipDistance | YES | Custom clip distances |
| shaderCullDistance | YES | Custom cull distances |
| transformFeedback | YES | Stream output |

### 6.4 Vertex Formats (from Pipeline Compilation Errors)

The failed pipeline compilations reveal the game's vertex buffer layouts:

**Format A (28-byte vertex)** -- Simple geometry:
```
Location 0: R32G32B32_SFLOAT   (Position, 12 bytes, offset 0)
Location 1: R16G16B16A16_SNORM (Normal, 8 bytes, offset 12)
Location 2: R32G32_SFLOAT      (UV0, 8 bytes, offset 20)
Stride: 28 bytes
```

**Format B (44-byte vertex)** -- Standard with tangent frame:
```
Location 0: R32G32B32_SFLOAT   (Position, 12 bytes, offset 0)
Location 1: R16G16B16A16_SNORM (Normal, 8 bytes, offset 12)
Location 4: R32G32_SFLOAT      (UV0, 8 bytes, offset 20)
Location 2: R16G16B16A16_SNORM (Tangent, 8 bytes, offset 28)
Location 3: R16G16B16A16_SNORM (Binormal/Bitangent, 8 bytes, offset 36)
Stride: 44 bytes
```

**Format C (52-byte vertex)** -- Standard with dual UV:
```
Location 0: R32G32B32_SFLOAT   (Position, 12 bytes, offset 0)
Location 1: R16G16B16A16_SNORM (Normal, 8 bytes, offset 12)
Location 4: R32G32_SFLOAT      (UV0, 8 bytes, offset 20)
Location 5: R32G32_SFLOAT      (UV1/Lightmap, 8 bytes, offset 28)
Location 2: R16G16B16A16_SNORM (Tangent, 8 bytes, offset 36)
Location 3: R16G16B16A16_SNORM (Binormal, 8 bytes, offset 44)
Stride: 52 bytes
```

**Format D (56-byte vertex)** -- With vertex color:
```
Location 0: R32G32B32_SFLOAT   (Position, 12 bytes, offset 0)
Location 1: R16G16B16A16_SNORM (Normal, 8 bytes, offset 12)
Location 2: B8G8R8A8_UNORM     (VertexColor, 4 bytes, offset 20)
Location 5: R32G32_SFLOAT      (UV0, 8 bytes, offset 24)
Location 6: R32G32_SFLOAT      (UV1/Lightmap, 8 bytes, offset 32)
Location 3: R16G16B16A16_SNORM (Tangent, 8 bytes, offset 40)
Location 4: R16G16B16A16_SNORM (Binormal, 8 bytes, offset 48)
Stride: 56 bytes
```

### 6.5 Swap Chain Configuration

- **Format**: `VK_FORMAT_B8G8R8A8_SRGB` (sRGB backbuffer)
- **Present Mode**: `VK_PRESENT_MODE_IMMEDIATE_KHR` (no vsync, uncapped FPS)
- **Buffer Size**: 1512x982 (windowed/borderless)
- **Image Count**: 3 (triple buffering)
- **Depth Format**: D24_UNORM_S8_UINT mapped to D32_SFLOAT_S8_UINT (DXVK fallback)
- **Display Mode**: 1512x982@120Hz

---

## 7. NadeoImporter.exe - Asset Pipeline

**File Size**: 8,675,328 bytes (8.27 MB)
**Build Date**: July 12, 2022
**Confidence**: VERIFIED

### 7.1 Supported File Formats

| Extension | Purpose |
|-----------|---------|
| `.fbx` | Source 3D model (FBX format) |
| `.tga` | Source texture (Targa format) |
| `.dds` | Compiled texture (DirectDraw Surface) |
| `.Item.gbx` | Compiled item definition |
| `.Mesh.gbx` | Compiled mesh data |
| `.Shape.gbx` | Compiled collision shape |
| `.Material.gbx` | Compiled material definition |
| `.Material.txt` | Material text description |
| `.Skel.gbx` | Compiled skeleton data |
| `.Rig.gbx` | Compiled rig data |
| `.Anim.gbx` | Compiled animation data |
| `.AnimImportConfig.gbx.json` | Animation import configuration |
| `.MeshParams.xml` | Mesh import parameters |
| `.Item.xml` | Item definition XML |
| `.Model.fbx` | Model source file |
| `.Texture.Gbx` | Compiled texture |
| `.GpuCache.Gbx` | Compiled GPU shader cache |
| `.Impostor.Gbx` | LOD impostor |
| `.Reduction40.Gbx` | 40% polygon reduction LOD |
| `.ReductionRetextured.Gbx` | Retextured reduced LOD |
| `.Remesh.Gbx` | Remeshed variant |
| `.gbx.json` | GBX metadata/config |
| `.gbx.xml` | GBX XML representation |
| `.pack.gbx` | Asset pack |
| `.skin.pack.gbx` | Skin pack |
| `.environment.gbx` | Environment definition |

### 7.2 Class Hierarchy (from strings)

Key game engine classes referenced:

| Class | Purpose |
|-------|---------|
| `CGameBlockItem` | Block-based items |
| `CGameCtnBlock` | Track blocks |
| `CGameCtnBlockInfo` | Block metadata |
| `CGameCtnBlockInfoClip` | Block clip connections |
| `CGameCtnBlockInfoVariant` | Block variants (Ground/Air) |
| `CGameCtnBlockUnit` / `CGameCtnBlockUnitInfo` | Block unit definitions |
| `CGameCtnImporter` | Main import orchestrator |
| `CGameCtnMacroBlockInfo` | Macro block (multi-block) definitions |
| `CBlock`, `CBlockModel`, `CBlockClip` | Block system internals |
| `CCrystal` | Crystal/collision mesh system |

### 7.3 Block Types

**Evidence**: Strings `|BlockInfo|Checkpoint`, `|BlockInfo|Finish`, `|BlockInfo|Start`, `|BlockInfo|Start/Finish`
**Confidence**: VERIFIED

Block waypoint types:
- `Start` -- Race start position
- `Finish` -- Race finish line
- `Checkpoint` -- Intermediate checkpoint
- `Start/Finish` -- Combined start/finish (for multilap)

### 7.4 Mesh Processing Pipeline

From strings analysis:
1. FBX import via `FbxImporter` (libfbxsdk.dll)
2. Geometry conversion: `FbxGeometryConverter`
3. Skeleton/skinning: `FbxSkin`, `FbxCluster`, `FbxBlendShape`
4. Material mapping: references `MaterialLib` (NadeoImporterMaterialLib.txt)
5. Collision shape generation: `CCrystal::ArchiveCrystal`
6. LOD generation: Reduction40, ReductionRetextured, Remesh, Impostor
7. Lightmap UV handling: `TreeGen Solid's LightMapUVs: Mesh has no LM UVs => abort`
8. GBX output: `ArchiveNod::LoadGbx_Body(Solid1)`, `ArchiveNod::LoadGbx_Body(Solid2)`

### 7.5 Shader References

- `GbxVisualPw01Shadow` -- Shadow pass shader
- `GbxDebugValue` -- Debug visualization shader
- `GbxP_DbgTest0` -- Debug test output
- `MDbgId_Enabled(-1)` -- Debug ID system
- `!!!!  PLEASE USE RIGHT PRE-COMPILED SHADERS  !!!!` -- Shader compilation warning

### 7.6 Version String

**Evidence**: String `"Version" : "Tm2020"` -- Identifies as Trackmania 2020 importer variant.
**Confidence**: VERIFIED

### 7.7 Command Line Options

**Evidence**: Strings `/LogMeshStats`, `/MaterialList`, `/MeshSkipPrefix` -- command-line flags
**Confidence**: VERIFIED

- `/LogMeshStats` -- Log mesh statistics during import
- `/MaterialList` -- List available materials
- `/MeshSkipPrefix` -- Skip mesh prefix during processing

---

## 8. updater_files.txt - Update System

**File Path**: `GameData/updater_files.txt`
**Size**: 4,791 bytes
**Format**: XML
**Confidence**: VERIFIED

### 8.1 XML Structure

```xml
<updater AllowedVersion="2026-01-10" Description="Trackmania"
         UpdateVersion="2026-01-10" manialink="" version="1">
    <group name="GroupName" [demoappid=""] [mainappid=""]>
        <file [dontinstall="1"] [level="CanBeNewer"] [optional="1"] [forcenorestart="1"]>
            <filename>PackFile.ext</filename>
            <checksum>SHA256_HASH</checksum>
            <size>BYTES</size>
            <lastupdate>DD/MM/YYYY HH:MM</lastupdate>
        </file>
    </group>
</updater>
```

### 8.2 File Groups

| Group | Steam AppIDs | Description |
|-------|-------------|-------------|
| **ManiaPlanet** | -- | Core engine packs (5 files) |
| **Titles** | -- | Title/game definition packs (3 files) |
| **Common** | -- | Shared content packs (5 files) |
| **TMStadium** | demo=233070, main=232910 | Stadium-specific content (6 files) |

### 8.3 File Attributes

| Attribute | Values | Meaning |
|-----------|--------|---------|
| `dontinstall="1"` | GpuCache_D3D11_SM5.zip | Downloaded but not auto-extracted |
| `level="CanBeNewer"` | Various | Local copy can be newer than server version |
| `optional="1"` | Translations.zip | Optional download |
| `forcenorestart="1"` | Translations.zip | Update without game restart |

### 8.4 Steam App IDs

- **Main App**: 232910
- **Demo App**: 233070

> **Note**: These are legacy ManiaPlanet-era App IDs (TrackMania Canyon and its demo) preserved in the updater system's "TMStadium" group, NOT the actual Trackmania 2020 Steam App ID, which is **2225070**.

### 8.5 Update Version

**Current version**: 2026-01-10
**Checksum algorithm**: SHA-256 (256-bit / 64 hex characters)
**Date format**: DD/MM/YYYY HH:MM

---

## 9. Nadeo.ini - Configuration

**File Path**: `Nadeo.ini`
**Size**: 256 bytes
**Confidence**: VERIFIED

### 9.1 Full Contents

```ini
[Trackmania]
WindowTitle=Trackmania
Updater=Steam
Distro=AZURO
UPlayAppId=7015
UserDir={userdocs}\Trackmania
CommonDir={commondata}\Trackmania
```

### 9.2 Field Analysis

| Key | Value | Description |
|-----|-------|-------------|
| `WindowTitle` | `Trackmania` | Window title bar text |
| `Updater` | `Steam` | Update distribution platform |
| `Distro` | `AZURO` | Distribution channel codename |
| `UPlayAppId` | `7015` | Ubisoft Connect application ID |
| `UserDir` | `{userdocs}\Trackmania` | User data directory (expands to `Documents\Trackmania`) |
| `CommonDir` | `{commondata}\Trackmania` | Shared data directory (expands to `ProgramData\Trackmania`) |

**"AZURO"**: This is the internal codename for the Trackmania 2020 distribution. Previous ManiaPlanet distributions had different codenames. This identifies the specific build/distribution variant to the engine.

---

## 10. Shader System (GpuCache)

**Source**: `Packs/GpuCache_D3D11_SM5.zip`
**Size**: 16.2 MB (compressed), 23.9 MB (uncompressed)
**Total Files**: 1,113 compiled shader files
**Format**: `.hlsl.GpuCache.Gbx` (HLSL compiled into GBX containers)
**Confidence**: VERIFIED

### 10.1 Shader Categories

| Category | Description | Count (approx) |
|----------|-------------|-----------------|
| **Bench/** | GPU benchmarking shaders | ~5 |
| **Clouds/** | Volumetric cloud rendering | ~9 |
| **Editor/** | Map editor visualization | ~3 |
| **Effects/** | Post-processing and effects | ~100+ |
| **Effects/Energy** | Energy/glow effects | |
| **Effects/Fog** | Fog rendering | |
| **Effects/Particles** | Particle systems | |
| **Effects/Particles/CameraWaterDroplets** | Camera water droplet effect | |
| **Effects/Particles/SelfShadow** | Particle self-shadowing | |
| **Effects/Particles/VortexSimulation** | Vortex particle simulation | |
| **Effects/PostFx** | Post-processing pipeline | |
| **Effects/PostFx/HBAO_plus** | NVIDIA HBAO+ ambient occlusion | |
| **Effects/SignedDistanceField** | SDF rendering | |
| **Effects/SortLib** | GPU sort library | |
| **Effects/SubSurface** | Subsurface scattering | |
| **Effects/TemporalAA** | Temporal anti-aliasing | |
| **Engines/** | Core rendering engine shaders | |
| **Engines/NormalMapBaking** | Normal map generation | |
| **Garage/** | Garage/car viewer shaders | |
| **Lightmap/** | Lightmap baking/rendering | |
| **Menu/** | Menu UI rendering | |
| **Noise/** | Noise generation | |
| **Painter/** | Car skin painter | |
| **ShadowCache/** | Shadow map caching | |
| **ShootMania/** | ShootMania-specific (legacy) | |
| **Sky/** | Sky/atmosphere rendering | |
| **Tech3/** | Tech3 material system | |
| **Tech3/Grass** | Grass rendering | |
| **Tech3/Trees** | Tree rendering | |
| **Techno3/** | Techno3 advanced materials | |
| **Test/** | Test/debug shaders | |

### 10.2 Shader Naming Convention

```
{Category}/{ShaderName}_{stage}.hlsl.GpuCache.Gbx
```

Stages:
- `_v` = Vertex shader
- `_p` = Pixel/Fragment shader
- `_g` = Geometry shader
- `_c` = Compute shader
- `_h` = Hull shader (tessellation)
- `_d` = Domain shader (tessellation)

### 10.3 Key Shader Programs

**Benchmark shaders** (from `Bench/`):
- `Anisotropy_p/v` -- Anisotropic filtering benchmark
- `Geometry_p/v` -- Vertex processing benchmark
- `OutputBandwidth_p/v` -- Fill rate benchmark
- `PixelArithmetic_p` -- ALU benchmark

**Cloud shaders** (from `Clouds/`):
- `CloudsEdgeLight_p` -- Cloud edge lighting
- `CloudsGodLight_p` -- God ray/volumetric light through clouds
- `CloudsGodMask_p` -- God ray masking
- `CloudsT3b_p/v` -- Cloud Tech3b rendering (main cloud shader)
- `CloudsTech3_p/v` -- Cloud Tech3 base
- `CloudsTech3_Opacity_p/v` -- Cloud opacity pass

**Copy/Utility shaders**:
- `CopyTextureFloatToInt_c` -- Float to integer texture conversion (compute)
- `CopyTextureIntToFloat_c` -- Integer to float texture conversion (compute)

### 10.4 Rendering Pipeline Insights

The shader categories reveal Trackmania's rendering pipeline:

1. **Shadow Pass**: `ShadowCache/` -- Shadow map rendering and caching
2. **Lightmap**: `Lightmap/` -- Baked/dynamic lightmap rendering
3. **Main Geometry**: `Tech3/`, `Techno3/` -- Material rendering system
4. **Sky/Atmosphere**: `Sky/` -- Sky dome and atmospheric scattering
5. **Clouds**: `Clouds/` -- Volumetric cloud rendering
6. **Particles**: `Effects/Particles/` -- Particle rendering with self-shadow and water droplets
7. **Post-Processing**: `Effects/PostFx/` -- TAA, HBAO+, tone mapping
8. **Effects**: `Effects/` -- Flares, lens dirt, fog, subsurface, SDF
9. **UI**: `Menu/` -- Menu rendering
10. **Special**: `Garage/`, `Painter/` -- Car viewer and skin painting

---

## 11. Key Findings for Browser Recreation

### 11.1 Graphics Requirements

- **Target API**: D3D11.0 feature level (DX11 Shader Model 5.0)
- **WebGPU equivalent**: Fully achievable -- WebGPU supports compute shaders, geometry processing, and all required texture formats
- **Shader model**: SM5 (HLSL) -- 1,113 precompiled shaders in cache
- **Key features needed**: Geometry shaders, tessellation, transform feedback, compute shaders, BC texture compression, anisotropic filtering, dual-source blending
- **Render target format**: B8G8R8A8_SRGB (sRGB output)
- **Depth format**: D24_UNORM_S8_UINT (24-bit depth + 8-bit stencil)
- **Triple buffered** with immediate present (no vsync by default)

### 11.2 Vertex Buffer Formats

Four vertex formats identified with strides of 28, 44, 52, and 56 bytes. All use:
- Position: `R32G32B32_SFLOAT` (vec3)
- Normal: `R16G16B16A16_SNORM` (packed normalized)
- UV: `R32G32_SFLOAT` (vec2)
- Tangent/Binormal: `R16G16B16A16_SNORM` (optional)
- Vertex Color: `B8G8R8A8_UNORM` (optional)

### 11.3 Material System

- **19 unique surface types** controlling physics behavior
- **All gameplay IDs are "None"** in the material library -- gameplay effects come from block/item system, not materials
- **UV layouts**: BaseMaterial (UV0) + Lightmap (UV1) for most materials, Lightmap-only (UV0) for Custom* materials
- **Skin textures use 4 channels**: `_D` (diffuse), `_N` (normal), `_R` (roughness), `_D_HueMask` (color customization)

### 11.4 Audio System

- **3D audio**: OpenAL Soft with ambisonic support
- **Codec**: Ogg Vorbis 1.3.5
- **Browser equivalent**: Web Audio API with spatialization

### 11.5 Network/Platform Dependencies

- **Auth**: Ubisoft Connect (UPC SDK) with ticket-based authentication
- **Voice**: Vivox SDK (SIP-based) -- replaceable with WebRTC
- **Ads**: Anzu.io SDK -- not needed for recreation
- **Updates**: Custom XML-based updater with SHA-256 checksums

### 11.6 Asset Pipeline

- **Source format**: FBX (via Autodesk SDK 2018)
- **Runtime formats**: GBX containers (NadeoPak for archives)
- **Pack files**: ~6.4 GB total, NadeoPak v18 format with SHA-256 integrity
- **LOD system**: Full mesh, Reduction40, ReductionRetextured, Remesh, Impostor
- **Texture formats**: DDS (BC compressed), TGA, WebP, PNG

### 11.7 Environment Themes

Four environment variations (each ~400-800 MB of assets):
- GreenCoast, BlueBay, RedIsland, WhiteShore

### 11.8 Localization

14 supported languages via gettext (.mo files):
cs-CZ, de-DE, en-US, es-ES, fr-FR, it-IT, ja-JP, ko-KR, nl-NL, pl-PL, pt-BR, ru-RU, tr-TR, zh-CN

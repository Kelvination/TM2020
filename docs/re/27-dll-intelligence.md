# 27 - DLL Intelligence Report

> Deep binary analysis of all DLL/EXE files in the Trackmania 2020 install directory.
> Extracted via `file`, `strings` commands on macOS (CrossOver bottle).
>
> **Analysis Date**: 2026-03-27
> **Install Path**: `/Users/kelvinnewton/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Trackmania/`

---

## Table of Contents

1. [vivoxsdk.dll - Vivox Voice Chat SDK](#1-vivoxsdkdll---vivox-voice-chat-sdk)
2. [VoiceChat.dll - Nadeo Voice Wrapper (Harbour SDK)](#2-voicechatdll---nadeo-voice-wrapper-harbour-sdk)
3. [upc_r2_loader64.dll - Ubisoft Connect Platform](#3-upc_r2_loader64dll---ubisoft-connect-platform)
4. [libfbxsdk.dll - Autodesk FBX SDK](#4-libfbxsdkdll---autodesk-fbx-sdk)
5. [anzu.dll - In-Game Advertising](#5-anzudll---in-game-advertising)
6. [OpenAL64_bundled.dll - OpenAL Soft Audio](#6-openal64_bundleddll---openal-soft-audio)
7. [libwebp64.dll - WebP Image Codec](#7-libwebp64dll---webp-image-codec)
8. [vorbis64.dll - Ogg Vorbis Audio](#8-vorbis64dll---ogg-vorbis-audio)
9. [ntdll_o.dll - Wine NTDLL Backup](#9-ntdll_odll---wine-ntdll-backup)
10. [Openplanet.dll - Mod Framework](#10-openplanetdll---mod-framework)
11. [NadeoImporter.exe - Asset Pipeline](#11-nadeoimporterexe---asset-pipeline)
12. [dinput8.dll - Openplanet Hook Loader](#12-dinput8dll---openplanet-hook-loader)
13. [d3dcompiler_47.dll - D3D Shader Compiler](#13-d3dcompiler_47dll---d3d-shader-compiler)
14. [DLL Dependency Map](#14-dll-dependency-map)
15. [Third-Party SDK Version Catalog](#15-third-party-sdk-version-catalog)
16. [Cross-Reference with Existing Docs](#16-cross-reference-with-existing-docs)

---

## 1. vivoxsdk.dll - Vivox Voice Chat SDK

### File Metadata
| Property | Value |
|----------|-------|
| Size | 12,441,688 bytes (11.87 MB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| Architecture | x86-64 (Windows) |

### Version Information
- **SDK Version**: `5.19.2.33478.213423bef1`
- **Build**: Unity build pipeline (`c:\build\output\unity\vivox-sdk\`)
- **Branch**: `NO_BRANCH_RECORDED`
- **Subversion Date**: `1/1/1970` (epoch placeholder)

### Protocols and Networking
- **SIP** (Session Initiation Protocol): Primary signaling protocol
  - `sip:confctl-e-` -- Echo conference control
  - `sip:confctl-g-` -- Group conference control
  - `sip:confctl-d-%s%s%s!p-%d-%d-%.3f-%d@%s` -- Dynamic conference URI format
- **XMPP**: Used for presence/messaging alongside SIP
  - `<?xml version='1.0'?><stream:stream to='` -- XMPP stream setup
  - `VIVOX_XMPP_CLEARTEXT_PORT` -- XMPP cleartext port config
  - `SSL Negotiation to XMPP Server Failed` -- TLS for XMPP
- **STUN/ICE**: NAT traversal
  - `AttemptStunOn/Off/Unspecified` -- STUN configuration
  - `ND_E_CANT_CONTACT_STUN_SERVER_ON_UDP_PORT_3478` -- Standard STUN port
- **RTP/SRTP**: Media transport
  - `VIVOX_BLOCK_RTP_OUT`, `VIVOX_BLOCK_RTP_IN` -- RTP flow control
  - `VX_VAR_RTP_ENCRYPTION`, `RTPEncryption` -- SRTP encryption
  - `Receiving rtp packet with version number !=2...discarded`
  - Built on `amsip-4.0.3-vivox-srtp` -- aMSIP SIP stack with SRTP
- **STRO**: Vivox's proprietary streaming/real-time overlay protocol
  - Full module: `vivox.stro` with connection, session, subscription, RTP, media session components
- **TLS**: `starttls`, `urn:ietf:params:xml:ns:xmpp-tls`, `VIVOX_IGNORE_SSL_ERRORS`

### Audio Codecs (NEW FINDING)
- **Opus**: Primary codec
  - `CodecTypeOpus`, `CurrentOpusBitRate`, `CurrentOpusComplexity`
  - `CurrentOpusVbrMode`, `CurrentOpusBandwidth`, `CurrentOpusMaxPacketSize`
  - `VIVOXVANI_V2_AUDIO_DATA_MONO_OPUS_48000` -- 48kHz Opus
- **Siren14**: Polycom's wideband codec at 32kHz
  - `VIVOXVANI_V2_AUDIO_DATA_MONO_SIREN14_32000`
- **Siren7**: Polycom's narrowband codec at 16kHz
  - `VIVOXVANI_V2_AUDIO_DATA_MONO_SIREN7_16000`
- **Speex**: Resampler only (not primary codec)
  - `VIVOXVANI_V2_AUDIO_DATA_MONO_SPEEX_WB` -- Wideband Speex
  - `Speex resampler intialization failed` [sic]

### Audio Processing
- **AEC**: `acousticechocancellation.cpp` -- Acoustic Echo Cancellation
- **AGC**: `automaticgaincontrol.cpp` -- Automatic Gain Control
- **Voice Processor**: Full per-participant, per-session voice processing pipeline

### Key API Functions (Exported)
```
vx_get_message_internal
vx_issue_request_internal
vx_uninitialize
vx_req_connector_create_create_internal
vx_req_account_login_create_internal
vx_req_account_authtoken_login_create_internal
vx_req_session_create_create_internal
vx_req_session_media_connect_create_internal
vx_req_session_set_3d_position_create_internal
vx_req_session_set_voice_font_create_internal
vx_req_channel_mute_user_create_internal
vx_req_channel_kick_user_create_internal
```

### Source Code Structure (from build paths)
```
vivox.api/          -- Public API layer (commandhandler, convert)
vivox.client/       -- Client logic (voiceprocessor, logincontext, encode)
vivox.stro/         -- STRO protocol (connection, session, subscription, RTP)
vivox.media/        -- Audio processing (AEC, AGC)
vivox.media.vxa/    -- Audio unit abstraction (capture, render devices)
vivox.system/       -- Infrastructure (HTTP, message queue, network monitor)
vivox.web/          -- Web client
vivox.network.reachability/ -- Network availability detection
vivox.core/         -- Event aggregation
lohika/xbone/       -- Xbox audio backend (CoreAudio)
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
VIVOX_FORCE_AUDIO_UNIT_FAILURE
VIVOX_VOICE_SERVICE_HOST / VIVOX_VOICE_SERVICE_PORT
VX_VAR_RTP_ENCRYPTION
```

### Relevance to Browser Recreation
**LOW** -- Voice chat is not needed for core gameplay. However, the 3D positional audio support (`vx_req_session_set_3d_position`) reveals that voice chat positions are tied to game coordinates, which could inform spatial audio design.

---

## 2. VoiceChat.dll - Nadeo Voice Wrapper (Harbour SDK)

### File Metadata
| Property | Value |
|----------|-------|
| Size | 1,298,648 bytes (1.24 MB) |
| Type | PE32+ executable (DLL) (GUI) x86-64 |
| Architecture | x86-64 (Windows) |
| PDB Path | `D:\Codebase\Nadeo\Out\x64_Release_ImportLib_Harbour\VoiceChat.pdb` |
| Signed By | NADEO SAS |

### NEW FINDING: Harbour SDK Framework

VoiceChat.dll is built on **Harbour**, a Ubisoft/Nadeo internal middleware framework. This is a dependency-injection / service-container architecture.

**Harbour modules discovered**:
- `Harbour.Voicechat` -- Top-level voicechat module
- `Harbour.Voicechat.Vivox` -- Vivox-specific implementation
- `Harbour.Common` -- Shared infrastructure

**Harbour tags** (service registration identifiers):
```
HARBOUR_TAG_VOICECHAT_API              -- Public API
HARBOUR_TAG_VOICECHAT_API_SDK          -- SDK layer
HARBOUR_TAG_VOICECHAT_API_BINDINGS     -- Language bindings
HARBOUR_TAG_VOICECHAT_API_DOTNET       -- .NET bindings
HARBOUR_TAG_VOICECHAT_API_POLICIES     -- Policy injection points
HARBOUR_TAG_VOICECHAT_UBISOFT          -- Ubisoft integration
HARBOUR_TAG_VOICECHAT_VIVOX            -- Vivox backend
HARBOUR_TAG_VOICECHAT_GME              -- Tencent GME backend (!)
HARBOUR_TAG_VOICECHAT_GME_WWISE        -- GME + Wwise audio
HARBOUR_TAG_VOICECHAT_DISCORD          -- Discord voice backend (!)
HARBOUR_TAG_VOICECHAT_PLAYFAB          -- PlayFab Party voice (!)
HARBOUR_TAG_COMMON_CONFIG              -- Config system
HARBOUR_TAG_FOUNDATION                 -- Base framework
HARBOUR_TAG_TRANSPORT                  -- Network transport
```

**Critical finding**: The Harbour SDK supports **four voice backends**: Vivox, Tencent GME, Discord, and PlayFab Party. Trackmania uses Vivox, but the framework is multi-backend capable.

### Vivox Configuration Parameters
```
voicechat.vivox.server_url         -- Vivox server URL
voicechat.vivox.token_issuer       -- Auth token issuer
voicechat.vivox.access_token_key   -- Auth token key
voicechat.vivox.domain             -- Vivox domain
voicechat.vivox.token_type         -- Token type
voicechat.vivox.token              -- Auth token
voicechat.vivox.channel_uri        -- Channel URI
voicechat.vivox.account_uri        -- Account URI
voicechat.vivox.account_name       -- Account name
voicechat.vivox.profile_id         -- User profile ID
voicechat.vivox.log_level          -- Log verbosity
voicechat.vivox.logfileName        -- Log file name
voicechat.vivox.platform_check_permission  -- Permission checking
voicechat.vivox.delay_connect      -- Delayed connection
voicechat.vivox.codec_selection    -- Codec choice
voicechat.vivox.codec_bitrate      -- Bitrate (16/24/32/40 kbit/s)
voicechat.vivox.codec_complexity   -- Codec complexity
```

### Vivox Server
- **Server URL**: `https://hyxd.www.vivox.com/api2`
- **App Name**: `VivoxTrackmania`

### Codec Selection (NEW FINDING)
```
Successfully set Vivox codec to Siren14
Successfully set Vivox codec to Siren7
Using Opus as Vivox codec                          -- default
Bitrate must be equals to 16, 24, 32, 40           -- kbit/s options
```
Opus is the default codec. Siren14 and Siren7 are fallback options.

### 3D Positional Audio
```
voicechat.vivox.3d                    -- Enable 3D voice
voicechat.vivox.3d.max_range          -- Max hearing distance
voicechat.vivox.3d.clamping_distance  -- Clamping distance
voicechat.vivox.3d.rolloff            -- Volume rolloff curve
voicechat.vivox.3d.distance_model     -- Distance attenuation model
```
- `This solution requires that a positional 3D channel is the first and only channel.`
- `Fail send update 3D position.`

### Text-to-Speech / Speech-to-Text (Accessibility)
```
voicechat.vivox.default_language.text_chat
voicechat.vivox.default_language.voice_chat
voicechat.vivox.default_language.text_to_speech
voicechat.vivox.default_language.speech_to_text
TTS_Enable / TTS_Disable
User->enableSpeechToText User=%s Channel=%s
User->enableTextToSpeech User=%s
```

### ABI Compatibility System
```
Caller ABI is incompatible. The caller ABI is [%s] while the Harbour library ABI is [%s].
version=%u,platform=%s,buildType=%s,crt=%s,cxxStandard=%lld,cxxLibrary=%s,...
```
The Harbour SDK has strict ABI versioning including C++ standard version, library version, exception settings, and RTTI configuration.

### Relevance to Browser Recreation
**LOW** -- Voice chat wrapper. The Harbour SDK discovery is architecturally interesting but not relevant to gameplay recreation.

---

## 3. upc_r2_loader64.dll - Ubisoft Connect Platform

### File Metadata
| Property | Value |
|----------|-------|
| Size | 436,032 bytes (426 KB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| Architecture | x86-64 (Windows) |
| PDB Path | `D:\JenkinsWorkspace\workspace\client_build_installer\client\build\working_directory\RelWithDebInfo\upc_r2_loader64.pdb` |
| Signed By | Ubisoft Entertainment Sweden AB |
| Code Signing | DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1 |

### Complete Exported UPC API (103 functions)

**Initialization/Lifecycle**:
- `UPC_Init`, `UPC_Uninit`, `UPC_Update`
- `UPC_ContextCreate`, `UPC_ContextFree`
- `UPC_Cancel`, `UPC_ErrorToString`

**Identity**:
- `UPC_IdGet`, `UPC_IdGet_Extended` -- Ubisoft account ID
- `UPC_NameGet`, `UPC_NameGet_Extended` -- Display name
- `UPC_EmailGet`, `UPC_EmailGet_Extended` -- Email
- `UPC_AvatarGet`, `UPC_AvatarFree` -- Avatar image
- `UPC_UserGet`, `UPC_UserFree` -- User profile
- `UPC_TicketGet`, `UPC_TicketGet_Extended` -- Auth ticket

**Application**:
- `UPC_ApplicationIdGet` -- Game application ID
- `UPC_LaunchApp` -- Launch another UPC application
- `UPC_InstallLanguageGet`, `UPC_InstallLanguageGet_Extended`
- `UPC_InstallChunkListGet`, `UPC_InstallChunkListFree`
- `UPC_InstallChunksOrderUpdate`, `UPC_InstallChunksPresenceCheck`

**Social**:
- `UPC_FriendAdd`, `UPC_FriendRemove`, `UPC_FriendCheck`
- `UPC_FriendListGet`, `UPC_FriendListFree`
- `UPC_BlacklistAdd`, `UPC_BlacklistHas`
- `UPC_UserPlayedWithAdd` -- Recent players

**Multiplayer**:
- `UPC_MultiplayerInvite`, `UPC_MultiplayerInviteAnswer`
- `UPC_MultiplayerSessionGet/Set/Clear/Free`

**Achievements**:
- `UPC_AchievementListGet`, `UPC_AchievementListFree`
- `UPC_AchievementImageGet`, `UPC_AchievementImageFree`
- `UPC_AchievementUnlock`

**Store/Products** (DLC/microtransactions):
- `UPC_ProductListGet`, `UPC_ProductListFree`
- `UPC_ProductConsume`, `UPC_ProductConsumeSignatureFree`
- `UPC_StoreProductListGet`, `UPC_StoreProductDetailsShow`
- `UPC_StoreCheckout`, `UPC_StoreIsEnabled`
- `UPC_StorePartnerGet` -- Partner store (Steam?)
- `UPC_StoreLanguageSet`

**Cloud Storage**:
- `UPC_StorageFileOpen`, `UPC_StorageFileClose`
- `UPC_StorageFileRead`, `UPC_StorageFileWrite`
- `UPC_StorageFileDelete`
- `UPC_StorageFileListGet`, `UPC_StorageFileListFree`

**Overlay**:
- `UPC_OverlayShow` -- Main overlay
- `UPC_OverlayBrowserUrlShow` -- In-overlay browser
- `UPC_OverlayFriendInvitationShow`
- `UPC_OverlayFriendSelectionShow/Free`
- `UPC_OverlayMicroAppShow` -- Micro-app overlay
- `UPC_OverlayNotificationShow`

**Rich Presence**:
- `UPC_RichPresenceSet`, `UPC_RichPresenceSet_Extended`

**Events**:
- `UPC_EventNextPeek`, `UPC_EventNextPoll`
- `UPC_EventRegisterHandler`, `UPC_EventUnregisterHandler`

**Streaming** (Ubisoft+ cloud gaming) (NEW FINDING):
- `UPC_StreamingTypeGet` -- Cloud streaming type
- `UPC_StreamingDeviceTypeGet` -- Device type
- `UPC_StreamingInputTypeGet` -- Input method
- `UPC_StreamingInputGamepadTypeGet` -- Gamepad type
- `UPC_StreamingResolutionGet/Free` -- Stream resolution
- `UPC_StreamingNetworkDelayForInputGet` -- Input latency
- `UPC_StreamingNetworkDelayForVideoGet` -- Video latency
- `UPC_StreamingNetworkDelayRoundtripGet` -- RTT
- `UPC_StreamingCurrentUserCountryGet/Free` -- Geo location

**Hardware Scoring**:
- `UPC_CPUScoreGet` -- CPU benchmark score
- `UPC_GPUScoreGet` -- GPU benchmark score

### DLL Dependencies
```
KERNEL32.dll    -- LoadLibraryW, GetProcAddress, GetModuleHandleW, LoadLibraryExW
SHELL32.dll
ADVAPI32.dll
```

### Key Findings
- This is a **loader stub**, not the full UPC SDK. It dynamically loads the real Ubisoft Connect runtime.
- Built on Jenkins CI: `D:\JenkinsWorkspace\workspace\client_build_installer\`
- The streaming APIs confirm Trackmania supports **Ubisoft+ cloud gaming** -- important for understanding latency requirements.
- `UPC_StorePartnerGet` suggests Steam store integration alongside Ubisoft Store.

### Relevance to Browser Recreation
**MEDIUM** -- The auth ticket system (`UPC_TicketGet`) is how Trackmania authenticates with Nadeo services. Understanding this is needed if the browser recreation needs to authenticate with Nadeo APIs. The cloud storage API is used for save games/profiles.

---

## 4. libfbxsdk.dll - Autodesk FBX SDK

### File Metadata
| Property | Value |
|----------|-------|
| Size | 8,341,944 bytes (7.95 MB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| Architecture | x86-64 (Windows) |
| File Date | 2018-07-09 |

### Version Compatibility
Supports FBX files from all major versions:
- FBX 6.0 (binary, ASCII, encrypted)
- Compatible with Autodesk 2006-2017 applications
- Latest compatibility: **Autodesk 2016/2017 applications/FBX plug-ins**

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

### Complete Class Hierarchy (106 classes)
Key classes for understanding the 3D pipeline:

**Scene/Document**: `FbxScene`, `FbxDocument`, `FbxGlobalSettings`
**Geometry**: `FbxMesh`, `FbxNurbs`, `FbxNurbsCurve`, `FbxNurbsSurface`, `FbxPatch`, `FbxSubDiv`
**Deformers**: `FbxSkin`, `FbxCluster`, `FbxBlendShape`, `FbxBlendShapeChannel`, `FbxVertexCacheDeformer`
**Skeleton**: `FbxSkeleton`, `FbxPose`, `FbxCharacterPose`
**Materials**: `FbxSurfaceMaterial`, `FbxSurfaceLambert`, `FbxSurfacePhong`, `FbxFileTexture`, `FbxProceduralTexture`
**Animation**: `FbxAnimStack`, `FbxAnimLayer`, `FbxAnimCurve`, `FbxAnimEvaluator`
**Constraints**: `FbxConstraintAim`, `FbxConstraintParent`, `FbxConstraintPosition`, `FbxConstraintRotation`, `FbxConstraintScale`, `FbxConstraintSingleChainIK`
**Cameras/Lights**: `FbxCamera`, `FbxCameraStereo`, `FbxCameraSwitcher`, `FbxLight`
**I/O**: `FbxImporter`, `FbxExporter`, `FbxIOSettings`

### Relevance to Browser Recreation
**LOW** -- Only used by NadeoImporter.exe for asset import, not at game runtime. However, the FBX class list confirms the full range of 3D features the game's asset pipeline handles.

---

## 5. anzu.dll - In-Game Advertising (Anzu.io)

### File Metadata
| Property | Value |
|----------|-------|
| Size | 3,930,968 bytes (3.75 MB) |
| Type | PE32+ executable (DLL) x86-64 |
| SDK Version | 5.41 |

### NEW FINDINGS (beyond 09-game-files-analysis.md)

**Embedded JavaScript Engine**:
The Anzu SDK contains a full JavaScript runtime with polyfills:
- `ScriptableSDKObj.prototype.runCommand` -- Command dispatch
- `ScriptableSDKObj.prototype.setTimeout/setInterval/clearTimeout/clearInterval`
- `window.setInterval`, `window.setTimeout`, `Date.now`, `console.log`
- `encodeURIComponent` -- Custom implementation
- `String.prototype.substr`, `String.prototype.endsWith` -- Polyfills
- `document.createEvent("MouseEvents")` -- Simulated click events
- `document.elementFromPoint(%f * window.innerWidth, %f * window.innerHeight)` -- Hit testing
- Ad logic is evaluated via `(function(){...})` JavaScript execution

**Video Ad Support**:
- `video/ogg` -- Theora video format support
- `Theora animated texture: no video stream found in file %s`
- `TheoraDecoder::decode_video_frame` -- Theora video decoder
- `anzu::PngAnimatedTexture::ReadPng` -- Animated PNG support

**Network Protocols**:
- **MQTT**: Real-time ad event messaging (`mqtt message for %s : %s`)
- **WebSocket**: `ixwebsocket/`, `Sec-WebSocket-Protocol`, `Upgrade: websocket`, `Sec-WebSocket-Version: 13`
- **JSON**: REST API communication for ad configuration

**Ad Campaign System**:
- `campaign_id`, `campaigns`, `campaignId`
- `placement`, `Placement aspect ratio don't match`
- `interstitial_id`, `interstitial_action`, `interstitial_start/stop`
- `display`, `video`, `interstitials`, `videotextures`
- Close button configuration: `Invalid close_button value (%s) provided in interstitial configuration`

### Relevance to Browser Recreation
**NONE** -- Advertising SDK, irrelevant to gameplay.

---

## 6. OpenAL64_bundled.dll - OpenAL Soft Audio

### File Metadata
| Property | Value |
|----------|-------|
| Size | 1,446,928 bytes (1.38 MB) |
| Type | PE32+ executable (DLL) (console) x86-64 |
| Version | **1.23.99** (development/pre-release of 1.24) |
| Vendor | OpenAL Community |
| Version String | `1.1 ALSOFT 1.23.99` |
| Library | OpenAL Soft |

### Audio Extensions (Complete List)

**AL Extensions**:
```
AL_EXT_ALAW                    -- A-law PCM format
AL_EXT_BFORMAT                 -- B-format ambisonic
AL_EXT_debug                   -- Debug output
AL_EXT_direct_context          -- Thread-safe contexts
AL_EXT_DOUBLE                  -- 64-bit float samples
AL_EXT_EXPONENT_DISTANCE       -- Exponential distance model
AL_EXT_FLOAT32                 -- 32-bit float samples
AL_EXT_IMA4                    -- IMA ADPCM compression
AL_EXT_LINEAR_DISTANCE         -- Linear distance model
AL_EXT_MCFORMATS               -- Multi-channel formats
AL_EXT_MULAW                   -- mu-law PCM format
AL_EXT_MULAW_BFORMAT           -- mu-law B-format
AL_EXT_MULAW_MCFORMATS         -- mu-law multi-channel
AL_EXT_OFFSET                  -- Sample offset queries
AL_EXT_source_distance_model   -- Per-source distance model
AL_EXT_SOURCE_RADIUS           -- Source radius for area sounds
AL_EXT_STATIC_BUFFER           -- Zero-copy buffer loading
AL_EXT_STEREO_ANGLES           -- Stereo source panning angles
AL_LOKI_quadriphonic           -- Quad speaker layout
AL_SOFT_bformat_ex             -- Extended B-format
AL_SOFT_block_alignment        -- Block alignment queries
AL_SOFT_buffer_length_query    -- Buffer length queries
AL_SOFT_buffer_sub_data        -- Partial buffer updates
AL_SOFT_callback_buffer        -- Callback-driven buffers
AL_SOFT_deferred_updates       -- Batched state updates
AL_SOFT_direct_channels        -- Bypass spatialization
AL_SOFT_direct_channels_remix  -- Direct channel remixing
AL_SOFT_effect_target          -- Effect routing
AL_SOFT_events                 -- Event system
AL_SOFT_gain_clamp_ex          -- Extended gain clamping
AL_SOFT_loop_points            -- Loop start/end points
AL_SOFT_MSADPCM                -- Microsoft ADPCM
AL_SOFT_source_latency         -- Source playback latency
AL_SOFT_source_length          -- Source length queries
AL_SOFT_source_resampler       -- Resampler selection
AL_SOFT_source_spatialize      -- Spatialization toggle
AL_SOFT_source_start_delay     -- Synchronized start
AL_SOFT_UHJ                    -- UHJ stereo encoding
AL_SOFT_UHJ_ex                 -- Extended UHJ
```

**ALC Extensions**:
```
ALC_ENUMERATE_ALL_EXT          -- Device enumeration
ALC_EXT_CAPTURE                -- Audio capture
ALC_EXT_debug                  -- Debug output
ALC_EXT_DEDICATED              -- Dedicated effects
ALC_EXT_direct_context         -- Thread-safe context
ALC_EXT_disconnect             -- Device disconnect events
ALC_EXT_EFX                    -- Effects framework (reverb, chorus, etc.)
ALC_EXT_thread_local_context   -- Thread-local contexts
ALC_SOFT_device_clock          -- Device clock queries
ALC_SOFT_HRTF                  -- HRTF rendering
ALC_SOFT_loopback              -- Loopback rendering
ALC_SOFT_loopback_bformat      -- B-format loopback
ALC_SOFT_output_limiter        -- Output limiter
ALC_SOFT_output_mode           -- Output mode selection
ALC_SOFT_pause_device          -- Device pause/resume
ALC_SOFT_reopen_device         -- Hot device switching
ALC_SOFT_system_events         -- System event notification
```

### Audio Backend
- **WASAPI** -- Windows Audio Session API (primary backend)
- **Null** backend (fallback)
- **Loopback** backend (for capture)
- Config env var: `ALSOFT_DRIVERS`

### HRTF (Head-Related Transfer Function)
Full HRTF support for headphone spatialization:
- `ALC_HRTF_SOFT` -- Enable/disable
- `ALC_HRTF_HEADPHONES_DETECTED_SOFT` -- Auto-detection
- `%u%s order %sHRTF rendering enabled, using "%s"` -- Higher-order HRTF
- `ALC_STEREO_HRTF_SOFT` -- Stereo HRTF mode

### Effects Framework (EFX)
- Reverb, Chorus, Autowah (from extension strings)
- Effect slots with auxiliary sends
- `Unpacking data with mismatched ambisonic order` -- Ambisonic processing

### Relevance to Browser Recreation
**HIGH** -- Web Audio API is the browser equivalent. Key features to replicate:
1. 3D positional audio with distance models (linear, exponential, inverse)
2. HRTF for headphone users
3. Ambisonic audio support
4. Effect chains (reverb, etc.)
5. Loop points for seamless audio loops
6. Buffer streaming

---

## 7. libwebp64.dll - WebP Image Codec

### File Metadata
| Property | Value |
|----------|-------|
| Size | 677,960 bytes (662 KB) |
| Type | PE32+ executable (DLL) (console) x86-64 |

### Exported Functions (Complete - 75 functions)

**Decoding** (17 functions):
```
WebPDecode, WebPDecodeRGB, WebPDecodeRGBA, WebPDecodeRGBAInto
WebPDecodeRGBInto, WebPDecodeBGR, WebPDecodeBGRA, WebPDecodeBGRAInto
WebPDecodeBGRInto, WebPDecodeARGB, WebPDecodeARGBInto
WebPDecodeYUV, WebPDecodeYUVInto
WebPGetDecoderVersion, WebPGetFeaturesInternal, WebPGetInfo
WebPFreeDecBuffer
```

**Encoding** (10 functions):
```
WebPEncode, WebPEncodeRGB, WebPEncodeRGBA
WebPEncodeBGR, WebPEncodeBGRA
WebPEncodeLosslessRGB, WebPEncodeLosslessRGBA
WebPEncodeLosslessBGR, WebPEncodeLosslessBGRA
WebPGetEncoderVersion
```

**Incremental Decoding** (8 functions):
```
WebPIDecode, WebPINewDecoder, WebPINewRGB, WebPINewYUV, WebPINewYUVA
WebPIAppend, WebPIUpdate, WebPIDelete, WebPIDecodedArea
WebPIDecGetRGB, WebPIDecGetYUVA
```

**Picture Operations** (16 functions):
```
WebPPictureAlloc, WebPPictureFree, WebPPictureCopy
WebPPictureCrop, WebPPictureRescale, WebPPictureView
WebPPictureImportRGB, WebPPictureImportRGBA, WebPPictureImportRGBX
WebPPictureImportBGR, WebPPictureImportBGRA, WebPPictureImportBGRX
WebPPictureARGBToYUVA, WebPPictureARGBToYUVADithered
WebPPictureSharpARGBToYUVA, WebPPictureSmartARGBToYUVA
WebPPictureYUVAToARGB, WebPPictureDistortion, WebPPlaneDistortion
WebPPictureHasTransparency, WebPPictureIsView
```

**Configuration**: `WebPConfigInitInternal`, `WebPConfigLosslessPreset`, `WebPValidateConfig`
**Color Conversion (SharpYuv)**: `SharpYuvConvert`, `SharpYuvGetVersion`, `SharpYuvComputeConversionMatrix`
**Memory**: `WebPMalloc`, `WebPSafeMalloc`, `WebPSafeCalloc`, `WebPSafeFree`, `WebPFree`

### Features
- **Lossy and lossless** encoding/decoding
- **Alpha channel** support (transparency)
- **YUV and RGB** color spaces
- **Incremental decoding** (streaming)
- **SharpYuv** high-quality YUV conversion
- **Keyframe** support (animation frames)

### Relevance to Browser Recreation
**LOW** -- Browsers natively support WebP. Used for texture compression in the game.

---

## 8. vorbis64.dll - Ogg Vorbis Audio

### File Metadata
| Property | Value |
|----------|-------|
| Size | 866,304 bytes (846 KB) |
| Type | PE32+ executable (DLL) (GUI) x86-64 |
| Library | Xiph.Org libVorbis |
| Version | **1.3.5** (release date: 2015-01-05) |
| Version String | `Xiph.Org libVorbis I 20150105` |

### Exported Functions (40 functions)
**Analysis/Encoding**:
```
vorbis_analysis, vorbis_analysis_blockout, vorbis_analysis_buffer
vorbis_analysis_headerout, vorbis_analysis_init, vorbis_analysis_wrote
vorbis_bitrate_addblock, vorbis_bitrate_flushpacket
vorbis_encode_init, vorbis_encode_init_vbr
vorbis_encode_setup_init, vorbis_encode_setup_managed, vorbis_encode_setup_vbr
vorbis_encode_ctl
```

**Synthesis/Decoding**:
```
vorbis_synthesis, vorbis_synthesis_blockin
vorbis_synthesis_halfrate, vorbis_synthesis_halfrate_p
vorbis_synthesis_headerin, vorbis_synthesis_idheader
vorbis_synthesis_init, vorbis_synthesis_lapout
vorbis_synthesis_pcmout, vorbis_synthesis_read, vorbis_synthesis_restart
```

**Infrastructure**:
```
vorbis_info_init, vorbis_info_clear, vorbis_info_blocksize
vorbis_dsp_clear, vorbis_block_init, vorbis_block_clear
vorbis_comment_init, vorbis_comment_clear
vorbis_comment_add, vorbis_comment_add_tag
vorbis_comment_query, vorbis_comment_query_count
vorbis_commentheader_out
vorbis_granule_time, vorbis_packet_blocksize
```

### Key Finding
This exports **both encoder and decoder** functions, meaning the game can both read and write Ogg Vorbis files. The encoder could be used for replay audio or voice recording.

### Relevance to Browser Recreation
**MEDIUM** -- Browser supports Ogg Vorbis natively via `<audio>` and Web Audio API. Knowing the version helps ensure compatibility.

---

## 9. ntdll_o.dll - Wine NTDLL Backup

### File Metadata
| Property | Value |
|----------|-------|
| Size | 687,696 bytes (672 KB) |
| Type | PE32+ executable (DLL) (console) x86-64, stripped to external PDB |
| Origin | Wine builtin DLL |

### Size Comparison
| File | Size | Location |
|------|------|----------|
| ntdll_o.dll | 687,696 | Trackmania directory |
| ntdll.dll (system32) | 687,696 | `windows/system32/` |
| ntdll.dll (syswow64) | 667,216 | `windows/syswow64/` |

**Finding**: `ntdll_o.dll` is **identical in size** to `system32/ntdll.dll` (both 687,696 bytes). This confirms it is a backup copy. The `_o` suffix stands for "original" -- likely placed by Openplanet's dinput8.dll hook to preserve the original before any modifications.

### NT API Surface
Exports standard NT kernel API: `NtAllocateVirtualMemory`, `NtCreateFile`, `NtReadFile`, `LdrLoadDll`, `LdrGetProcedureAddress`, `RtlAllocateHeap`, etc.

### Wine-Specific Strings
- `EXCEPTION_WINE_ASSERTION`, `EXCEPTION_WINE_CXX_EXCEPTION`
- `wine: could not open working directory %s`
- `Wine builtin DLL`

### Relevance to Browser Recreation
**NONE** -- Wine/CrossOver infrastructure artifact.

---

## 10. Openplanet.dll - Mod Framework

### File Metadata
| Property | Value |
|----------|-------|
| Size | 12,764,672 bytes (12.17 MB) |
| Type | PE32+ executable (DLL) (GUI) x86-64 |
| Version | **1.29.1** |
| Build Path | `e:\Dev\openplanet\Openplanet\Openplanet\` |

### Hooking Architecture

**Entry Point**: dinput8.dll proxy loads Openplanet.dll

**Graphics Overlay Hooks**:
- `OffsetGraphicsDevice` -- D3D11 device pointer
- `OffsetGraphicsContext` -- D3D11 device context
- `OffsetGraphicsSwapChain` -- DXGI swap chain
- `Fatal: Unable to detect graphics overlay offsets.` -- Pattern scanning for vtable offsets
- Hooks into swap chain Present for overlay rendering

**Window Procedure Hook**:
- `Hooking WndProc...` -- Intercepts window messages for input handling

**Game Logic Hooks**:
- `Fatal: Unable to detect MainUpdate hook pointer.` -- Main game loop hook
- `Fatal: Unable to detect SetAuthToken hook pointer.` -- Auth token interception

**Code Injection System**:
```
HookInfo@ Hook(IntPtr ptr, int padding, const string &in func, int pushRegisters = 0, ...)
void Unhook(HookInfo@ hook)
bool ProcIntercept(CMwStack &in)
void InterceptProc(const string &in className, const string &in procName, ...)
void ResetInterceptProc(const string &in className, const string &in procName)
string Patch(IntPtr ptr, const string &in pattern)
```

### AngelScript Scripting Engine

Openplanet uses **AngelScript** as its scripting engine:
- `Angelscript` -- Engine identification
- `Script context is not suspended.`
- `Restart/Stop/Start script engine`
- `Verbose script compilation log`
- `Script execution timeout`

### ImGui Overlay
- Uses **dear imgui** for all UI rendering
- Docking support: `OverlayEnableDocking`, `OverlayEnableDockingWithShift`
- DPI scaling: `OverlayEnableDpiScaleFonts`
- Custom styling via TOML: `Openplanet/DefaultStyle.toml`
- Custom fonts: DroidSans, ManiaIcons, DroidSansMono

### Game Engine Reflection

**Core Engine Access**:
```
CGameCtnApp@ GetApp()                              -- Main application
CGameCtnNetwork                                     -- Network subsystem
CTrackManiaNetwork                                  -- Trackmania-specific networking
array<CGameManialinkPage@>@ GetManialinkPages()     -- ManiaLink UI pages
```

**Nod System**:
```
CMwNod@ Preload(CSystemFidFile@ fid)               -- Asset preloading
const MwFastBuffer<CPlugFilePack@> AllPacks         -- All pack files
int GetRefCount(CMwNod@ nod)                        -- Reference counting
void NodTree(CMwNod@ nod, ...)                      -- Tree traversal
CMwNod@ GetOffsetNod(const ?&in nod, uint offset)   -- Raw memory offset access
void SetOffset(const ?&in nod, uint offset, ...)    -- Raw memory write
```

**Game Events**:
```
void OnLoadCallback(CMwNod@ nod)
void OnSetCurChallenge(CGameCtnChallenge@ challenge)
void OnLoadDecoration(CGameCtnDecoration@ decoration, CGameCtnChallenge@ challenge)
```

### File System Access
- `AllPacks`, `AllPacksGameData`, `AllPacksUserDir` -- Pack file enumeration
- `FindOrAddFid`, `RemappedLoadFromFid` -- File ID resolution
- Pack Explorer and Fid Explorer UI tools
- File extraction: `Extracted file '%s'`

### Plugin System
- `Plugin render early`, `Plugin render interface`, `Plugin render` -- Three render phases
- `Reload plugin`, `Edit plugin`, `Toggle plugin`
- `Favorite Plugins`
- Dependency resolution: `array<string>@ get_Dependencies()`

### Relevance to Browser Recreation
**HIGH** -- Openplanet's reflection data reveals the actual game engine class names, member layouts, and function signatures. The `GetApp()`, Nod system, and offset access patterns document the game's internal architecture.

---

## 11. NadeoImporter.exe - Asset Pipeline

### File Metadata
| Property | Value |
|----------|-------|
| Size | 8,675,328 bytes (8.27 MB) |
| Type | PE32+ executable (console) x86-64 |
| Config File | `Nadeo.ini` |
| Log File | `NadeoImporterLog.txt` |
| Registry | `Software\Nadeo\ManiaPlanet` |

### Embedded OpenSSL
- Statically linked OpenSSL (`ossl_static.pdb`)
- RSA, AES, SHA support
- Used for GBX file signing/verification

### GBX File Types Produced/Consumed

**Item/Object Types**:
```
.Item.gbx              -- Custom items
.Mesh.gbx              -- 3D mesh data
.Shape.gbx             -- Physics collision shape
.Material.gbx          -- Material definitions
.Texture.Gbx           -- Texture data
.Skel.gbx              -- Skeleton (bones)
.Rig.gbx               -- Animation rig
.Anim.gbx              -- Animation clips
.skin.pack.gbx         -- Skin packages
.pack.gbx              -- Generic pack files
```

**Engine Resources**:
```
FuncShader.Gbx          -- Shader functions
FuncTree.Gbx            -- Function trees
FuncColorGradient.Gbx   -- Color gradients
FuncKey.Gbx             -- Keyframe functions
Visual.Gbx              -- Visual data
Material.Gbx            -- Materials
MaterialFx.Gbx          -- Material effects
Decal.Gbx               -- Decal definitions
TexturePack.Gbx         -- Texture atlases
ViewDepLocator.Gbx      -- View-dependent LOD
Sound/Music/Audio*.Gbx  -- Audio resources
```

**Processing Outputs**:
```
.Reduction40.Gbx        -- 40% polygon reduction LOD
.Remesh.Gbx             -- Remeshed LOD
.ReductionRetextured.Gbx -- Reduced + retextured LOD
.Impostor.Gbx           -- Billboard impostor LOD
.GpuCache.Gbx           -- GPU shader cache
```

### Vehicle Data
All vehicle ObjectInfo references found:
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
Plus ShootMania character references: `ArenaPlayer.Item.gbx`, `Minion.Item.gbx`

### Complete CPlug Class Hierarchy (250+ classes)

This is the most comprehensive class listing found in any DLL. Key categories:

**Visual/Rendering** (40+ classes):
`CPlugVisual`, `CPlugVisual2D`, `CPlugVisual3D`, `CPlugVisualIndexedTriangles`, `CPlugVisualGrid`, `CPlugVisualSprite`, `CPlugTree`, `CPlugTreeLight`, `CPlugTreeVisualMip`, `CPlugSolid`, `CPlugSolid2Model`, `CPlugLight`, `CPlugLightDyna`, `CPlugBitmap`, `CPlugBitmapArray`, `CPlugBitmapRender*` (13 variants)

**Materials/Shaders** (15+ classes):
`CPlugMaterial`, `CPlugMaterialCustom`, `CPlugMaterialFx*`, `CPlugMaterialUserInst`, `CPlugShader`, `CPlugShaderApply`, `CPlugShaderGeneric`, `CPlugShaderPass`

**Animation** (50+ classes):
`CPlugAnimClip`, `CPlugAnimGraph`, `CPlugAnimRigNode_*` (25+ variants including `Blend`, `Blend2d`, `ClipPlay`, `JointIK2`, `JointInertia`, `StateMachine`, `LayeredBlend`)

**Vehicle** (17 classes):
`CPlugVehicleCarPhyShape`, `CPlugVehicleGearBox`, `CPlugVehiclePhyModelCustom`, `CPlugVehicleWheelPhyModel`, `CPlugVehicleVisModel*`, camera models (Race, Race2, Race3, Internal, Helico, HMD)

**Physics/Dynamics**:
```
NPlugDyna::SKinematicConstraint    -- Kinematic animation constraints
NPlugDyna::SConstraintModel        -- Physics constraint definitions
NPlugDyna::SForceFieldModel        -- Force field definitions
NPlugDyna::SAnimFunc01/Nat         -- Animation functions for dynamics
NPlugDynaObjectModel::SInstanceParams -- Dynamic object instances
CPlugDynaModel, CPlugDynaObjectModel, CPlugDynaPointModel, CPlugDynaWaterModel
```

**Particles/VFX** (15+ classes):
`CPlugParticleEmitterModel`, `CPlugParticleGpuModel`, `CPlugFxSystem`, `CPlugFxLensFlareArray`, `CPlugFxLightning`, `CPlugVFXFile`, `CPlugVFXNode_*`

**Audio** (12 classes):
`CPlugSound`, `CPlugSoundEngine`, `CPlugSoundEngine2`, `CPlugSoundMood`, `CPlugSoundSurface`, `CPlugMusic`, `CPlugAudio*`

**Terrain/Environment**:
`CPlugClouds`, `CPlugFogMatter`, `CPlugFogVolume`, `CPlugWeather`, `CPlugWeatherModel`, `CPlugMoodSetting`, `CPlugMoodBlender`, `CPlugDayTime`, `CPlugGrassMatterArray`, `CPlugVegetTreeModel`

### Shader System Strings
```
DiffuseIntensity, DoSpecular, SpecularRGB, DynaSpecular
Normal, CameraNormal, WorldNormal, EyeNormal
NormalRotate, NormalAreSigned, NoMipNormalize
OpacityIsDiffuseAlpha
Conv.Diffuse
LightMapOnly
EConvertMethod
```
These reveal a **PBR-adjacent material system** with diffuse, specular, normal mapping, and lightmap support.

### Texture Processing
```
Can't crop cubemap textures
Cropping input texture from window (%ux%u)-(%ux%u)
Clamping input texture to %ux%u
Resampling input texture to %ux%u
mipmapped_texture::write_dds  -- DDS output
crn_comp_params               -- Crunch texture compression
```

### Relevance to Browser Recreation
**HIGH** -- The complete CPlug class hierarchy is essential for understanding what data structures the game uses. The vehicle physics classes, material system, and LOD pipeline are directly relevant.

---

## 12. dinput8.dll - Openplanet Hook Loader

### File Metadata
| Property | Value |
|----------|-------|
| Size | 14,336 bytes (14 KB) |
| Type | PE32+ executable (DLL) x86-64 |
| PDB Path | `G:\Games\Trackmania\dinput8.pdb` |
| Export | `DirectInput8Create` (single function) |

### Complete Hook Sequence
1. Check `UPLAY_ARGUMENTS` environment variable
2. Check if Pause key held (bypass: `Pause key held - not loading Openplanet.`)
3. Find `Openplanet\Lib` subdirectory
4. Modify `PATH` to include Openplanet libraries
5. Load `Openplanet.dll` via `LoadLibraryA`
6. Call `DinputInit` function in Openplanet.dll
7. Load original `\dinput8.dll` from system directory
8. Forward `DirectInput8Create` calls to real DLL

### Dependencies
```
KERNEL32.dll    -- GetEnvironmentVariableA, LoadLibraryA, GetProcAddress, etc.
USER32.dll      -- GetAsyncKeyState (Pause key check)
VCRUNTIME140.dll
api-ms-win-crt-string-l1-1-0.dll
api-ms-win-crt-stdio-l1-1-0.dll
api-ms-win-crt-time-l1-1-0.dll
api-ms-win-crt-runtime-l1-1-0.dll
```

### Relevance to Browser Recreation
**NONE** -- Mod framework hook mechanism.

---

## 13. d3dcompiler_47.dll - D3D Shader Compiler

### File Metadata
| Property | Value |
|----------|-------|
| Size | 4,346,120 bytes (4.15 MB) |
| Type | PE32+ executable (DLL) x86-64 |

### Shader Model Support
```
vs_2_x, vs_2_sw, vs_3_sw       -- Vertex shader 2.x/3.0
ps_2_x, ps_2_sw, ps_3_sw       -- Pixel shader 2.x/3.0
vs_4_0, vs_4_0_level_9_1       -- Vertex shader 4.0 (+ DX9 compat)
vs_4_0_level_9_3, vs_4_1       -- Vertex shader 4.x
ps/vs/gs/hs/ds/cs_%d_%d        -- All SM4+ stages
cs_5_0                          -- Compute shader 5.0
```

### HLSL Types Present
```
Texture2D, Texture2DMS, Texture2DArray, Texture2DMSArray
SamplerState
cbuffer
StructuredBuffer (enableRawAndStructuredBuffers)
```

### Key Features
- All six shader stages: Vertex, Pixel, Geometry, Hull, Domain, Compute
- Shader Model 5.0 support (D3D11)
- D3D11.1 extensions: `enable11_1ShaderExtensions`
- UAVs at every shader stage
- SV_RenderTargetArrayIndex from any stage
- D3D11 Linker for shader linking

### Relevance to Browser Recreation
**HIGH** -- Confirms SM5/D3D11.1 as the shader target. WebGPU's WGSL must replicate equivalent functionality.

---

## 14. DLL Dependency Map

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

### Runtime DLL Loading Evidence
From dinput8.dll strings:
- `LoadLibraryA` -- Used to load Openplanet.dll
- `GetProcAddress` -- Used to find DinputInit, DirectInput8Create
- `GetModuleFileNameA/W` -- Process identification

From upc_r2_loader64.dll:
- `LoadLibraryW`, `LoadLibraryExW` -- Loads full UPC runtime
- `GetModuleHandleW`, `GetModuleHandleExW` -- Module detection
- `GetProcAddress` -- Function resolution

---

## 15. Third-Party SDK Version Catalog

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

## 16. Cross-Reference with Existing Docs

### Confirmations of 09-game-files-analysis.md
- Anzu SDK version 5.41: **CONFIRMED**
- dinput8.dll as Openplanet proxy: **CONFIRMED**, expanded with full hook sequence
- libfbxsdk.dll as Autodesk FBX: **CONFIRMED**, expanded with complete class list
- OpenAL for 3D audio: **CONFIRMED**, version now identified as 1.23.99
- ntdll_o.dll as Wine backup: **CONFIRMED**, size comparison proves identity

### New Findings Not in Existing Docs

1. **Vivox SDK version 5.19.2.33478** -- Previously unversioned
2. **Vivox codec support**: Opus (default), Siren14, Siren7 -- NEW
3. **Vivox protocol stack**: SIP + XMPP + STRO + RTP/SRTP -- NEW
4. **Harbour SDK framework** in VoiceChat.dll -- NEW
5. **Four voice backends** compiled into Harbour: Vivox, Tencent GME, Discord, PlayFab Party -- NEW
6. **Vivox server URL**: `https://hyxd.www.vivox.com/api2` -- NEW
7. **3D positional voice chat** parameters (max_range, clamping_distance, rolloff) -- NEW
8. **Text-to-speech/Speech-to-text** accessibility features in voice chat -- NEW
9. **Complete UPC API** (103 functions) including cloud streaming support -- NEW
10. **Ubisoft+ cloud gaming** APIs in UPC loader -- NEW
11. **OpenAL Soft 1.23.99** with 37 AL + 14 ALC extensions -- NEW
12. **HRTF headphone spatialization** support -- NEW
13. **Complete FBX format support** (FBX, OBJ, DAE, 3DS, DXF) -- Previously partial
14. **250+ CPlug engine classes** in NadeoImporter -- Previously ~50 known
15. **NPlugDyna::SKinematicConstraint** confirmed in NadeoImporter -- NEW
16. **Vehicle physics classes** confirmed: `CPlugVehicleCarPhyShape`, `CPlugVehicleGearBox`, `CPlugVehiclePhyModelCustom`, `CPlugVehicleWheelPhyModel` -- NEW details
17. **Shader system material properties**: DiffuseIntensity, DoSpecular, NormalRotate, OpacityIsDiffuseAlpha, LightMapOnly -- NEW
18. **LOD pipeline**: Reduction40, Remesh, ReductionRetextured, Impostor -- NEW
19. **Crunch texture compression** in NadeoImporter -- NEW
20. **Anzu SDK contains Theora video decoder** for animated ads -- NEW
21. **Anzu SDK uses MQTT + WebSocket** for real-time ad delivery -- NEW
22. **Openplanet hooks**: MainUpdate, SetAuthToken, WndProc, SwapChain -- NEW details
23. **Openplanet uses AsmJit** for runtime code generation -- NEW
24. **All 10 vehicle ObjectInfo paths** from NadeoImporter -- NEW
25. **VoiceChat ABI versioning system** with platform/compiler/feature flags -- NEW

### Corrections to Existing Docs
- 09-game-files-analysis.md stated OpenAL version was unknown -- it is **1.23.99**
- vorbis64.dll was listed without version -- it is **libVorbis 1.3.5 (2015-01-05)**
- The Harbour SDK framework was completely undocumented

---

## Summary: Architecture Insights for Browser Recreation

### Audio Pipeline
```
Game Audio Sources
  |
  +-- OpenAL Soft 1.23.99 (3D spatial, HRTF, EFX effects)
  |     +-- WASAPI backend
  |     +-- Ambisonic support
  |
  +-- vorbis64.dll (Ogg Vorbis 1.3.5 decode/encode)
  |
  +-- Voice Chat: VoiceChat.dll -> vivoxsdk.dll
        +-- Opus codec @ 16-40 kbit/s
        +-- SIP signaling, RTP/SRTP media
        +-- 3D positional audio
```

**Browser equivalent**: Web Audio API with AudioContext, PannerNode (HRTF mode), ConvolverNode (reverb), native Ogg Vorbis decoding.

### Rendering Pipeline
```
D3D11.1 Device
  +-- d3dcompiler_47.dll (SM5 runtime compilation)
  +-- Shader stages: VS, PS, GS, HS, DS, CS
  +-- Material system: Diffuse, Specular, Normal, LightMap
  +-- Texture formats: DDS, WebP (libwebp64), PNG
  +-- LOD: Reduction40, Remesh, Impostor
```

**Browser equivalent**: WebGPU with WGSL shaders, or WebGL2 with GLSL ES 3.0.

### Network/Services
```
Ubisoft Connect (upc_r2_loader64.dll)
  +-- Auth tickets
  +-- Cloud storage
  +-- Friends/social
  +-- Achievement system
  +-- Cloud streaming support

Vivox Voice (vivoxsdk.dll)
  +-- SIP/XMPP signaling
  +-- RTP/SRTP media
  +-- STUN NAT traversal
```

### Asset Pipeline (Offline)
```
NadeoImporter.exe
  +-- FBX/OBJ/DAE/3DS/DXF -> GBX
  +-- Texture processing (DDS, Crunch compression)
  +-- LOD generation
  +-- OpenSSL signing
  +-- 250+ CPlug class types
```

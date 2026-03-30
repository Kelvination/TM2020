# 24 - Trackmania 2020 Audio System Deep Dive

> Comprehensive reverse-engineering analysis of TM2020's audio architecture, for the purpose of recreating it with the Web Audio API.
>
> **Date**: 2026-03-27
> **Sources**: Ghidra decompilation, DLL string extraction, class hierarchy analysis, game configuration, Openplanet plugin intelligence

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [OpenAL Integration Details](#2-openal-integration-details)
3. [Sound Type Catalog](#3-sound-type-catalog)
4. [Engine Sound Model](#4-engine-sound-model)
5. [Spatial Audio System](#5-spatial-audio-system)
6. [Music System](#6-music-system)
7. [Voice Chat](#7-voice-chat)
8. [Web Audio API Mapping](#8-web-audio-api-mapping)
9. [Complete Audio Class Catalog](#9-complete-audio-class-catalog)
10. [Audio Configuration Reference](#10-audio-configuration-reference)

---

## 1. Architecture Overview

### Q: What audio engine does TM2020 use?

**Answer**: TM2020 uses **OpenAL Soft** via `OpenAL64_bundled.dll` (1.38 MB) for all spatial and gameplay audio. Voice chat uses a separate **Vivox SDK** (v5.19.2) pipeline. Audio files are decoded with **libVorbis 1.3.5** (`vorbis64.dll`).

**Evidence**:
- `COalAudioPort::InitImplem` decompiled at address `0x14138c090` (see `decompiled/audio/COalAudioPort_InitImplem.c`)
- `strings OpenAL64_bundled.dll` yields `OpenAL Soft` and `openal-soft`
- `strings vorbis64.dll` yields `Xiph.Org libVorbis 1.3.5`
- `strings vivoxsdk.dll` yields `<VivoxSDK><SDK_VERSION>5.19.2.33478.213423bef1</SDK_VERSION>`

### High-Level Audio Pipeline

```
CAudioManager (orchestrator)
  |
  +-- CAudioPort (abstract output port)
  |     +-- COalAudioPort (OpenAL Soft implementation)
  |     +-- CAudioPortNull (silent/disabled)
  |
  +-- CAudioSource (abstract sound source)
  |     +-- CAudioSourceEngine   --> CPlugSoundEngine / CPlugSoundEngine2
  |     +-- CAudioSourceSurface  --> CPlugSoundSurface
  |     +-- CAudioSourceMood     --> CPlugSoundMood
  |     +-- CAudioSourceMusic    --> CPlugMusic
  |     +-- CAudioSourceGauge    --> CPlugSoundGauge
  |     +-- CAudioSourceMulti    --> CPlugSoundMulti
  |
  +-- CAudioListener             (3D listener position/orientation)
  +-- CAudioZone / CAudioZoneSource (spatial audio zones)
  +-- CAudioBufferKeeper         (buffer lifecycle management)
  +-- CAudioSettings             (volume, quality configuration)
  +-- CAudioScriptManager        (ManiaScript audio API)
```

**Evidence**: Class hierarchy extracted from `class_hierarchy.json` (2,027 Nadeo classes total, 30 in Audio category) and the subsystem class map (`13-subsystem-class-map.md` Section 1).

### Audio File Format Pipeline

```
.ogg (Ogg Vorbis) --[CPlugFileOggVorbis]--> CPlugSound --> CAudioSource --> OpenAL Buffer
.wav              --[CPlugFileWav]--------> CPlugSound --> CAudioSource --> OpenAL Buffer
.snd              --[CPlugFileSnd]--------> CPlugSound --> CAudioSource --> OpenAL Buffer
(procedural)      --[CPlugFileSndGen]-----> CPlugSound --> CAudioSource --> OpenAL Buffer
.AudioMotors      --[CPlugFileAudioMotors]-> CPlugSoundEngine / CPlugSoundEngine2 --> OpenAL Buffer
```

**Evidence**: File handler classes from `class_hierarchy.json`: `CPlugFileOggVorbis`, `CPlugFileWav`, `CPlugFileSnd`, `CPlugFileSndGen`, `CPlugFileAudioMotors`.

---

## 2. OpenAL Integration Details

### Initialization Sequence

The decompiled `COalAudioPort::InitImplem` (at `0x14138c090`) reveals the exact initialization:

1. **Dynamic loading**: `LoadLibrary("OpenAL64_bundled.dll")`
2. **Function resolution**: Resolves `alcOpenDevice`, `alcGetProcAddress`, `alcGetError`, `alcIsExtensionPresent`, `alcGetString`, `alcCloseDevice`
3. **Device opening**: Tries named device first (from config `AudioDevice_Oal`), falls back to `ALC_DEFAULT_DEVICE_SPECIFIER` (`0x1005`)
4. **Context creation**: `alcCreateContext` on the opened device
5. **Version query**: `alcGetIntegerv` with `ALC_MAJOR_VERSION` (`0x1000`) and `ALC_MINOR_VERSION` (`0x1001`) -- expects ALC 1.x
6. **Source count query**: `alcGetIntegerv` with `ALC_MONO_SOURCES` (`0x1010`) and `ALC_STEREO_SOURCES` (`0x1011`)
7. **String queries**: `alGetString` for `AL_VERSION` (`0xB002`), `AL_RENDERER` (`0xB003`), `AL_EXTENSIONS` (`0xB004`), `AL_VENDOR` (`0xB001`)
8. **EFX check**: `alcIsExtensionPresent` for EFX support
9. **Log output**: `"[Audio] Initialized, using device '<name>', sources = N+M, EFX enabled/disabled"`

**Evidence**: `decompiled/audio/COalAudioPort_InitImplem.c`, `15-ghidra-research-findings.md` Section 1.

### Anti-Tamper Obfuscation

Function pointers stored in the `COalAudioPort` struct are XOR/ADD obfuscated:

| Offset | Type | Description |
|--------|------|-------------|
| +0x298 | ptr | `alcOpenDevice` (XOR obfuscated) |
| +0x2A0 | ptr | `alcCloseDevice` |
| +0x2A8 | ptr | `alcGetProcAddress` |
| +0x2B1 | ptr | `alcGetError` (XOR obfuscated) |
| +0x2B9 | ptr | `alcGetString` |
| +0x2C1 | ptr | `alcIsExtensionPresent` (XOR obfuscated) |
| +0x2C8 | ptr | OpenAL DLL handle |
| +0x2D9 | str | Device name string |
| +0x2F9 | 4x short | DLL version |
| +0x31D | byte | Initialized flag |
| +0x321 | ptr | ALC device handle |
| +0x338 | lock | Mutex |

**Evidence**: Decompiled struct offsets from `COalAudioPort_InitImplem.c`.

### Simultaneous Source Count

The game queries `ALC_MONO_SOURCES` and `ALC_STEREO_SOURCES` at init and logs them as `"sources = N+M"`. The exact count depends on the audio device and OpenAL Soft configuration, but OpenAL Soft typically supports **256 mono sources** and **256 stereo sources** by default.

The actual log format is `sources = <mono>+<stereo>`, so on a typical system this would be `sources = 256+256`.

**Evidence**: ALC constants `0x1010` and `0x1011` in the decompiled init code.

### EFX (Environmental Effects) Support

The game checks for EFX support during initialization. When enabled (`AudioAllowEFX = true` in config), the following effects are available via OpenAL Soft:

**Effects available** (from `strings OpenAL64_bundled.dll`):
- `AL_EFFECT_REVERB` -- Standard reverb
- `AL_EFFECT_EAXREVERB` -- EAX reverb (22 parameters: density, diffusion, gain, gainHF, gainLF, decay time, decay HF/LF ratio, reflections gain/delay/pan, late reverb gain/delay/pan, echo time/depth, modulation time/depth, air absorption, room rolloff, HF reference, LF reference)
- `AL_EFFECT_CHORUS` -- Chorus effect
- `AL_EFFECT_DISTORTION` -- Distortion
- `AL_EFFECT_ECHO` -- Echo (damping, delay, feedback, LR delay, spread)
- `AL_EFFECT_FLANGER` -- Flanger
- `AL_EFFECT_FREQUENCY_SHIFTER` -- Frequency shift
- `AL_EFFECT_VOCAL_MORPHER` -- Vocal morph
- `AL_EFFECT_PITCH_SHIFTER` -- Pitch shift
- `AL_EFFECT_RING_MODULATOR` -- Ring modulation
- `AL_EFFECT_AUTOWAH` -- Auto-wah
- `AL_EFFECT_COMPRESSOR` -- Dynamic range compressor
- `AL_EFFECT_EQUALIZER` -- 4-band parametric EQ
- `AL_EFFECT_DEDICATED_DIALOGUE` -- Dedicated dialogue channel
- `AL_EFFECT_DEDICATED_LOW_FREQUENCY_EFFECT` -- Dedicated LFE
- `AL_EFFECT_CONVOLUTION_SOFT` -- Convolution reverb (OpenAL Soft extension)

**Filters available**:
- `AL_FILTER_LOWPASS` -- Low-pass filter (gain, gainHF)
- `AL_FILTER_HIGHPASS` -- High-pass filter (gain, gainLF)
- `AL_FILTER_BANDPASS` -- Band-pass filter (gain, gainHF, gainLF)

The game's `CPlugAudioEnvironment` class maps to these EFX reverb presets per audio zone. The `CPlugAudioBalance` class handles channel panning and balance.

**Evidence**: All effect/filter strings extracted from `OpenAL64_bundled.dll`. The `AudioAllowEFX` config key from `Default.json`.

### HRTF (Head-Related Transfer Function)

OpenAL Soft includes full HRTF support for binaural 3D audio:

**HRTF-related ALC extensions** (from `strings OpenAL64_bundled.dll`):
- `ALC_SOFT_HRTF` -- HRTF extension
- `ALC_HRTF_SOFT` -- HRTF enable attribute
- `ALC_HRTF_STATUS_SOFT` -- Query HRTF status
- `ALC_HRTF_ID_SOFT` -- Select HRTF dataset
- `ALC_HRTF_SPECIFIER_SOFT` -- HRTF dataset name
- `ALC_NUM_HRTF_SPECIFIERS_SOFT` -- Number of available HRTF datasets
- `ALC_STEREO_HRTF_SOFT` -- Stereo HRTF output mode

**HRTF status values**:
- `ALC_HRTF_ENABLED_SOFT` -- Active
- `ALC_HRTF_DISABLED_SOFT` -- Disabled
- `ALC_HRTF_DENIED_SOFT` -- Denied by system
- `ALC_HRTF_REQUIRED_SOFT` -- Required by system
- `ALC_HRTF_HEADPHONES_DETECTED_SOFT` -- Headphones auto-detected
- `ALC_HRTF_UNSUPPORTED_FORMAT_SOFT` -- Format incompatible

The log message `%u%s order %sHRTF rendering enabled, using "%s"` confirms HRTF is actively used when enabled.

The game config has `AudioAllowHRTF = true` (boolean toggle in `Default.json`). When headphones are detected, OpenAL Soft can automatically enable HRTF for proper 3D audio spatialization.

**Evidence**: ALC extension strings from the DLL. Config key `AudioAllowHRTF` from `Default.json`. Log format string from DLL.

### Supported Output Modes

From the OpenAL Soft DLL strings:
- Mono (`ALC_MONO_SOFT`)
- Stereo (`ALC_STEREO_SOFT`, `ALC_STEREO_BASIC_SOFT`)
- Stereo HRTF (`ALC_STEREO_HRTF_SOFT`)
- Stereo UHJ (`ALC_STEREO_UHJ_SOFT`)
- Quad (`ALC_QUAD_SOFT`)
- 5.1 Surround (`ALC_5POINT1_SOFT`, `ALC_SURROUND_5_1_SOFT`)
- 6.1 Surround (`ALC_6POINT1_SOFT`, `ALC_SURROUND_6_1_SOFT`)
- 7.1 Surround (`ALC_7POINT1_SOFT`, `ALC_SURROUND_7_1_SOFT`)
- 7.1.4 Surround (from `strings`: `7.1.4 Surround`, `7.1.4.4 Surround`)
- B-Format 3D (`ALC_BFORMAT3D_SOFT`) -- Ambisonics

**Evidence**: `strings OpenAL64_bundled.dll` output.

---

## 3. Sound Type Catalog

### Sound Categories (from class hierarchy)

Each sound category has a paired **source** class (runtime audio emitter) and **resource** class (loadable sound data):

| Category | Source Class | Resource Class | Description |
|----------|-------------|---------------|-------------|
| Engine | `CAudioSourceEngine` | `CPlugSoundEngine` / `CPlugSoundEngine2` | Vehicle motor sounds with RPM mapping |
| Surface | `CAudioSourceSurface` | `CPlugSoundSurface` | Tire-on-surface sounds (per material) |
| Mood | `CAudioSourceMood` | `CPlugSoundMood` | Ambient atmospheric loops |
| Music | `CAudioSourceMusic` | `CPlugMusic` / `CPlugMusicType` | Background music tracks |
| Gauge | `CAudioSourceGauge` | `CPlugSoundGauge` | Speed/RPM gauge UI sounds |
| Multi | `CAudioSourceMulti` | `CPlugSoundMulti` | Layered composite sounds |
| Located | (generic source) | `CPlugLocatedSound` | 3D-positioned point sounds |
| Video | (generic source) | `CPlugSoundVideo` | Video-associated audio |
| Component | (child of Multi) | `CPlugSoundComponent` | Individual layer within a multi-sound |

**Evidence**: `class_hierarchy.json` Audio category, `13-subsystem-class-map.md` Section 1.

### Audio Events by Gameplay Context

#### Car Sounds
| Event | Likely Sound Type | Evidence |
|-------|-------------------|----------|
| Engine idle/rev | `CPlugSoundEngine` / `CPlugSoundEngine2` | Dedicated class exists; RPM field (0-11000) in vehicle state |
| Tire rolling | `CPlugSoundSurface` | Per-material surface sounds; 19 surface IDs (Asphalt, Dirt, Grass, Ice, etc.) |
| Tire screech/slip | `CPlugSoundSurface` | `SlipCoef` (0-1) available per wheel in vehicle state |
| Wind noise | [UNKNOWN] | `CameraWooshVolumedB`, `CameraWooshMinSpeedKmh` strings found -- speed-dependent wind sound tied to camera |
| Collision/impact | `CPlugSoundMulti` (PLAUSIBLE) | Multi-sound likely crossfades impact layers by severity |
| Turbo activation | [UNKNOWN, likely `CPlugSoundMulti`] | `IsTurbo`, `TurboTime` fields exist in vehicle state; distinct turbo levels (None, Normal, Super, Roulette variants) |
| Gear shift | [UNKNOWN] | `CurGear` (0-7) tracked in vehicle state |
| Burnout | [UNKNOWN] | `IsWheelsBurning` bool in vehicle state |

#### Environment Sounds
| Event | Likely Sound Type | Evidence |
|-------|-------------------|----------|
| Map ambient | `CPlugSoundMood` | Dedicated mood/ambient class; `CGameCtnDecorationAudio` for map-level audio settings |
| Water splash/submersion | [UNKNOWN] | `WaterImmersionCoef` (0-1) and `WaterOverSurfacePos` in vehicle state |
| Zone-based ambience | `CAudioZone` / `CAudioZoneSource` | Spatial audio zone classes exist |

#### UI Sounds
| Event | Likely Sound Type | Evidence |
|-------|-------------------|----------|
| Checkpoint | [UNKNOWN, likely `CPlugSound`] | No dedicated class; generic sound resource |
| Finish line | [UNKNOWN, likely `CPlugSound`] | No dedicated class |
| Menu interactions | `CAudioScriptSound` | ManiaScript audio API for UI |
| Countdown | [UNKNOWN] | No dedicated class |

#### MediaTracker Sounds
| Event | Likely Sound Type | Evidence |
|-------|-------------------|----------|
| Music effect | `CGameCtnMediaBlockMusicEffect` | Dedicated class with `SKeyVal` method (keyframe values) |
| Sound effect | `CGameCtnMediaBlockSound` | Dedicated class with `SuperSKeyVal` method |

**Evidence**: Vehicle state fields from `19-openplanet-intelligence.md`, camera strings from `15-ghidra-research-findings.md`, surface materials from `09-game-files-analysis.md`.

---

## 4. Engine Sound Model

### Q: How does the engine sound work?

**Answer**: TM2020 has TWO engine sound systems -- `CPlugSoundEngine` (v1) and `CPlugSoundEngine2` (v2). The engine sound is **sample-based with RPM-mapped crossfading**, not pure synthesis. A dedicated file format (`CPlugFileAudioMotors`) stores motor sound profiles.

### Evidence for Sample-Based (Not Synthesized) Engine Sound

1. `CPlugFileAudioMotors` -- A dedicated file format class exists for motor audio, implying pre-recorded/processed samples
2. `CPlugSoundEngine` and `CPlugSoundEngine2` -- Two generations of engine sound, suggesting iterative improvement of a sample-based system
3. `CPlugSoundComponent` and `CPlugSoundMulti` -- Component-based layered sound architecture, consistent with crossfading between RPM-layer samples

### RPM-to-Pitch Mapping

From the vehicle state (`19-openplanet-intelligence.md`):
- `RPM`: float, range 0-11000 (via custom Openplanet offset, not default exposed)
- `CurGear`: uint, range 0-7
- `FrontSpeed`: float, m/s (multiply by 3.6 for km/h)
- `InputGasPedal`: float, 0.0-1.0

**Probable model** (PLAUSIBLE, not directly confirmed):
```
For each gear:
  1. Select RPM-appropriate sample layers from CPlugFileAudioMotors
  2. Crossfade between adjacent RPM layers based on current RPM
  3. Adjust playback rate (pitch) proportional to RPM within each layer's range
  4. Apply load modulation based on InputGasPedal (throttle position)
  5. On gear change, crossfade between gear-specific sound sets
```

### Load-Dependent Sound Changes

- `InputGasPedal` (0-1) likely modulates engine sound character (on-throttle vs. coasting)
- `InputIsBraking` likely triggers engine braking / deceleration sound
- `IsTurbo` and `TurboTime` (0-1) likely overlay a turbo/boost sound effect
- `ReactorBoostLvl` triggers reactor boost audio overlay

### CPlugSoundEngine vs CPlugSoundEngine2

| Feature | CPlugSoundEngine (v1) | CPlugSoundEngine2 (v2) |
|---------|----------------------|----------------------|
| Purpose | Legacy engine sound | Current engine sound |
| Relationship | Base engine class | Extended engine class |
| [UNKNOWN] | Simpler RPM mapping? | Multi-layer crossfade? |
| [UNKNOWN] | Single sample? | Per-gear sample sets? |

**What we do NOT know**:
- The exact crossfade algorithm between RPM layers
- How many RPM sample layers exist per gear
- The `CPlugFileAudioMotors` file format specification
- Whether v1 and v2 are used for different vehicle types (CarSport vs CarSnow vs CarRally vs CarDesert)
- The specific pitch curve shape (linear? exponential?)

**Evidence**: Class names from `class_hierarchy.json`. Vehicle state fields from `19-openplanet-intelligence.md`. The existence of `CPlugFileAudioMotors` as a dedicated format.

---

## 5. Spatial Audio System

### Q: How does 3D spatial audio work?

### Listener Position

`CAudioListener` represents the 3D audio listener (microphone). It is almost certainly tied to the active camera position and orientation.

**Evidence for camera-audio coupling**:
- `CameraWooshVolumedB` and `CameraWooshMinSpeedKmh` strings found in the binary (from `15-ghidra-research-findings.md` Section 3) -- these are camera-speed-dependent audio parameters
- The camera system has 12 camera types; the listener would follow whichever is active (Race, FirstPerson, Free, etc.)
- `CAudioListener` is a standalone class (not a subclass of any camera), so it likely receives position updates from the camera system each frame

### Distance Attenuation Models

OpenAL Soft supports all three standard distance models (all confirmed in `OpenAL64_bundled.dll` strings):

| Model | OpenAL Constant | Formula |
|-------|----------------|---------|
| Inverse Distance | `AL_INVERSE_DISTANCE` | `gain = refDist / (refDist + rolloff * (dist - refDist))` |
| Inverse Distance Clamped | `AL_INVERSE_DISTANCE_CLAMPED` | Same, but `dist` clamped to `[refDist, maxDist]` |
| Linear Distance | `AL_LINEAR_DISTANCE` | `gain = 1 - rolloff * (dist - refDist) / (maxDist - refDist)` |
| Linear Distance Clamped | `AL_LINEAR_DISTANCE_CLAMPED` | Same, clamped |
| Exponent Distance | `AL_EXPONENT_DISTANCE` | `gain = (dist / refDist) ^ (-rolloff)` |
| Exponent Distance Clamped | `AL_EXPONENT_DISTANCE_CLAMPED` | Same, clamped |

**Which model does TM2020 use?** [UNKNOWN] -- The default OpenAL distance model is `AL_INVERSE_DISTANCE_CLAMPED`. Without decompiling the source setup code, we cannot confirm which model TM2020 selects. However, `AL_INVERSE_DISTANCE_CLAMPED` is the most common choice for games and is the OpenAL default.

**Per-source attenuation parameters** (from OpenAL API, all available):
- `AL_REFERENCE_DISTANCE` -- Distance at which gain is 1.0
- `AL_MAX_DISTANCE` -- Maximum distance (clamped models)
- `AL_ROLLOFF_FACTOR` -- Rolloff rate multiplier
- `AL_CONE_INNER_ANGLE` / `AL_CONE_OUTER_ANGLE` / `AL_CONE_OUTER_GAIN` -- Directional sound cones
- `AL_AIR_ABSORPTION_FACTOR` -- High-frequency absorption over distance (EFX)

**Evidence**: All distance model strings from `OpenAL64_bundled.dll`. `AL_EXT_source_distance_model` extension present, allowing per-source distance models.

### Doppler Effect

The game supports Doppler effect and provides a user toggle:

- Config: `AudioDisableDoppler = false` (enabled by default in `Default.json`)
- OpenAL provides: `AL_DOPPLER_FACTOR`, `AL_SPEED_OF_SOUND` (default 343.3 m/s)
- Per-source: `AL_VELOCITY` (3D velocity vector) and `AL_POSITION` (3D position)
- The deprecated `AL_DOPPLER_VELOCITY` is also present in the DLL with a warning message: `"AL_DOPPLER_VELOCITY is deprecated in AL 1.1, use AL_SPEED_OF_SOUND; AL_DOPPLER_VELOCITY -> AL_SPEED_OF_SOUND / 343.3f"`

**Doppler formula** (OpenAL standard):
```
shift = SPEED_OF_SOUND / (SPEED_OF_SOUND + DOPPLER_FACTOR * listener_velocity_toward_source)
      * (SPEED_OF_SOUND + DOPPLER_FACTOR * source_velocity_toward_listener) / SPEED_OF_SOUND
```

Given that vehicle `WorldVel` (vec3, m/s) is available from the physics system, each car's sound sources likely have their velocity set to `WorldVel` each frame.

**Evidence**: `AudioDisableDoppler` in `Default.json`. Doppler strings from `OpenAL64_bundled.dll`. `WorldVel` from `19-openplanet-intelligence.md`.

### Audio Zones

`CAudioZone` and `CAudioZoneSource` provide zone-based spatial audio:
- Zones define spatial regions in the map where different audio environments apply
- `CPlugAudioEnvironment` stores per-zone reverb/effect settings
- `CGameCtnDecorationAudio` stores decoration-level (map theme) audio settings
- `CPlugSoundMood` provides ambient sounds per mood/zone

**[UNKNOWN]**: How zones blend at boundaries (crossfade? hard cut?), zone shape (box? sphere? convex hull?), how many zones a typical map has.

### Occlusion/Obstruction

**[UNKNOWN]**: No direct evidence of audio occlusion/obstruction was found. OpenAL EFX supports `AL_DIRECT_FILTER` and `AL_AUXILIARY_SEND_FILTER` which can implement occlusion by applying a lowpass filter to occluded sources. The `AL_FILTER_LOWPASS` filter is present in the DLL. However, whether TM2020 performs any raycast-based occlusion is unconfirmed.

**Evidence**: Filter strings from `OpenAL64_bundled.dll`. Absence of evidence for occlusion-specific code.

---

## 6. Music System

### Q: How does music work?

### Music Architecture

- `CPlugMusic` -- Music track resource (loadable from pack files)
- `CPlugMusicType` -- Music genre/type classification (menu music, race music, etc.)
- `CAudioSourceMusic` -- Runtime music playback source
- `CAudioScriptMusic` -- ManiaScript-accessible music control

### Music in MediaTracker

`CGameCtnMediaBlockMusicEffect` (with `SKeyVal` method) suggests music can be keyframed in MediaTracker clips:
- Volume changes over time
- Potentially tempo/effect changes synchronized to replay events

`CGameCtnMediaBlockSound` (with `SuperSKeyVal` method) handles sound effects in MediaTracker.

### Dynamic Music

**[UNKNOWN]**: Whether TM2020 has dynamic music that changes with gameplay state (e.g., different intensity near finish line, music reacting to speed). The `CPlugMusicType` class suggests at least categorization of music types, but dynamic layering is not confirmed.

### Track Transitions / Crossfades

**[UNKNOWN]**: No direct evidence of crossfade logic was found in the decompiled code. The `CAudioSourceMusic` class handles playback, but transition behavior between tracks is not decompiled.

### Volume Ducking

The config separates:
- `AudioSoundVolume` (0-1) -- Master SFX volume
- `AudioSoundLimit_Scene` (0-1) -- Scene/gameplay sound limit
- `AudioSoundLimit_Ui` (0-1) -- UI sound limit
- `AudioMusicVolume` (0-1) -- Music volume (independent)

This separation enables music ducking when gameplay sounds are important, but whether automatic ducking occurs is [UNKNOWN].

**Evidence**: Config keys from `Default.json`. Class names from `class_hierarchy.json`.

---

## 7. Voice Chat

### Q: How does voice chat work?

### Vivox SDK Integration

TM2020 uses a three-layer voice chat architecture:

```
Game (Trackmania.exe)
  |
  +-- VoiceChat.dll (Nadeo's "Harbour" framework wrapper, 1.24 MB)
        |
        +-- vivoxsdk.dll (Vivox SDK v5.19.2, 11.87 MB)
```

**Evidence**: DLL analysis from `09-game-files-analysis.md` Sections 1.10-1.11. `VoiceChat.dll` strings include `D:\Codebase\Nadeo\Out\x64_Release_ImportLib_Harbour\VoiceChat.pdb`.

### Vivox SDK Details

- **Version**: 5.19.2.33478.213423bef1
- **Protocol**: SIP (Session Initiation Protocol) with STUN, RTP for media
- **Server**: `https://hyxd.www.vivox.com/api2`
- **Log file**: `VivoxTrackmania`

### Channel Types

From `vivoxsdk.dll` strings:
- `sip:confctl-e-` -- Echo test channels
- `sip:confctl-g-` -- Group voice channels
- `sip:confctl-d-` -- Direct (1-to-1) voice channels

### 3D Positional Voice

The config key `voicechat.vivox.3d` enables 3D positional voice chat. Vivox supports three rolloff curve types:
- `channel_rolloff_curve_type_inverse_distance_clamped`
- `channel_rolloff_curve_type_linear_distance_clamped`
- `channel_rolloff_curve_type_exponential_distance_clamped`

The `VoiceChat.dll` string `Fail send update 3D position.` confirms that 3D position updates are sent during gameplay. The Vivox SDK has `vx_req_session_set_3d_position` and `vx_req_sessiongroup_set_session_3d_position` commands.

### Push-to-Talk vs Open Mic

From `Default.json`:
```json
"VoiceChat_VoiceDetection_Mode": "pushtotalk",
"VoiceChat_VoiceDetection_Sensitivity": 1,
"VoiceChat_VoiceDetection_Auto": false,
"VoiceChat_VoiceDetection": 1
```

Both modes are supported:
- **Push-to-talk** (default): Manual activation
- **Voice Activity Detection (VAD)**: Automatic, with configurable sensitivity

Vivox audio processing features (can be toggled via environment variables):
- `VIVOX_FORCE_NO_AEC` -- Acoustic Echo Cancellation
- `VIVOX_FORCE_NO_AGC` -- Automatic Gain Control
- `VIVOX_FORCE_NO_VAD` -- Voice Activity Detection

### Voice Chat Operations

From `VoiceChat.dll`: `MuteLocal`, `MuteRemote`, `Unmute`, `SetVoiceDetection`, `ChannelJoin`, `ChannelLeave`, `adjustMicVolume`

From `Default.json`:
```json
"VoiceChat_Device_In": "default",
"VoiceChat_Device_Out": "default",
"VoiceChat_SpeakerVolume": 1
```

### When Is Voice Chat Active?

**[UNKNOWN]**: Likely active in multiplayer lobbies and during online races. The `voicechat.vivox.delay_connect` key suggests connection can be deferred. Channel join/leave operations are explicit.

**Evidence**: All config keys from `Default.json`. DLL strings from `vivoxsdk.dll` and `VoiceChat.dll`. Analysis from `09-game-files-analysis.md`.

---

## 8. Web Audio API Mapping

### Q: How would I recreate this in Web Audio API?

### Architecture Mapping

| TM2020 (OpenAL) | Web Audio API | Notes |
|---|---|---|
| `alcOpenDevice` / `alcCreateContext` | `new AudioContext()` | Single AudioContext per page |
| `CAudioListener` / `alListenerfv` | `AudioContext.listener` | Built-in listener with position/orientation |
| `alGenSources` / `alSourcefv` | `new PannerNode()` | One PannerNode per 3D sound source |
| `alGenBuffers` / `alBufferData` | `decodeAudioData()` | Decode OGG/WAV to AudioBuffer |
| `alSourcePlay` | `AudioBufferSourceNode.start()` | Note: Web Audio sources are one-shot; create new node per play |
| `AL_GAIN` | `GainNode` | Per-source volume control |
| `AL_PITCH` | `AudioBufferSourceNode.playbackRate` | Pitch shift via playback rate |
| `AL_POSITION` / `AL_VELOCITY` | `PannerNode.positionX/Y/Z` | 3D position per source |
| `AL_DIRECTION` / `AL_CONE_*` | `PannerNode.coneInnerAngle` etc. | Directional sound cones |
| EFX Reverb | `ConvolverNode` | Requires impulse response samples |
| EFX Lowpass Filter | `BiquadFilterNode` (type: 'lowpass') | Built-in filter types |
| `AL_DOPPLER_FACTOR` | `PannerNode` with velocity | [LIMITATION] Web Audio PannerNode does not natively support Doppler; must be manually computed via `playbackRate` adjustment |
| HRTF | `PannerNode.panningModel = 'HRTF'` | Built-in HRTF in Web Audio |
| Source pooling | Custom pool of AudioBufferSourceNodes | Create/recycle nodes; ~100+ concurrent sources in modern browsers |

### Engine Sound Synthesis Node Graph

```
[AudioBufferSourceNode: RPM Layer 1] --> [GainNode: Crossfade 1] --+
[AudioBufferSourceNode: RPM Layer 2] --> [GainNode: Crossfade 2] --+--> [GainNode: Master Engine Volume]
[AudioBufferSourceNode: RPM Layer 3] --> [GainNode: Crossfade 3] --+         |
                                                                              v
                                                                    [BiquadFilterNode: Lowpass]
                                                                              |
                                                                              v
                                                                    [PannerNode: 3D Position]
                                                                              |
                                                                              v
                                                                    [AudioContext.destination]
```

**Per frame**:
1. Read `RPM` from vehicle state
2. Determine which two RPM layers bracket the current RPM
3. Calculate crossfade weight (linear interpolation between layers)
4. Set `GainNode` values for crossfade
5. Adjust `AudioBufferSourceNode.playbackRate` to fine-tune pitch within layer
6. Update `PannerNode` position from vehicle `Position` (vec3)

**Alternative approach (simpler, for MVP)**:
```
[AudioBufferSourceNode: Single engine sample, looping]
  .playbackRate = map(RPM, 0, 11000, 0.5, 2.5)  // pitch shift
      |
      v
  [GainNode: Volume based on throttle]
      |
      v
  [PannerNode: 3D position from car]
      |
      v
  [AudioContext.destination]
```

### Surface Sound Node Graph

```
For each surface type (Asphalt, Dirt, Grass, Ice, etc.):

[AudioBufferSourceNode: Surface loop] --> [GainNode: Volume based on SlipCoef + FrontSpeed]
                                                    |
                                                    v
                                          [PannerNode: Car position]
                                                    |
                                                    v
                                          [AudioContext.destination]

// Active surface determined by wheel.GroundContactMaterial (ESurfId)
// Volume scales with FrontSpeed (no sound when stopped)
// SlipCoef > threshold triggers screech overlay
```

### Spatial Audio with PannerNode

```javascript
const panner = new PannerNode(ctx, {
  panningModel: 'HRTF',           // or 'equalpower' for non-HRTF
  distanceModel: 'inverse',        // matches OpenAL default AL_INVERSE_DISTANCE_CLAMPED
  refDistance: 1.0,                 // AL_REFERENCE_DISTANCE
  maxDistance: 10000.0,             // AL_MAX_DISTANCE
  rolloffFactor: 1.0,              // AL_ROLLOFF_FACTOR
  coneInnerAngle: 360,             // AL_CONE_INNER_ANGLE (omnidirectional)
  coneOuterAngle: 0,               // AL_CONE_OUTER_ANGLE
  coneOuterGain: 0                 // AL_CONE_OUTER_GAIN
});

// Update each frame:
panner.positionX.value = carPos.x;
panner.positionY.value = carPos.y;
panner.positionZ.value = carPos.z;

// Listener follows camera:
ctx.listener.positionX.value = camPos.x;
ctx.listener.positionY.value = camPos.y;
ctx.listener.positionZ.value = camPos.z;
ctx.listener.forwardX.value = camDir.x;
ctx.listener.forwardY.value = camDir.y;
ctx.listener.forwardZ.value = camDir.z;
ctx.listener.upX.value = camUp.x;
ctx.listener.upY.value = camUp.y;
ctx.listener.upZ.value = camUp.z;
```

### Wind/Camera Woosh Sound

```javascript
// CameraWooshVolumedB and CameraWooshMinSpeedKmh from binary strings
const WOOSH_MIN_SPEED_KMH = 50;  // [UNKNOWN exact value, placeholder]
const WOOSH_MAX_DB = -6;          // [UNKNOWN exact value, placeholder]

function updateWindSound(speedKmh) {
  if (speedKmh < WOOSH_MIN_SPEED_KMH) {
    windGainNode.gain.value = 0;
    return;
  }
  // Map speed to volume (dB scale)
  const t = Math.min((speedKmh - WOOSH_MIN_SPEED_KMH) / 300, 1.0);
  const db = WOOSH_MAX_DB * t;
  windGainNode.gain.value = Math.pow(10, db / 20);
}
```

### Manual Doppler Effect (Web Audio Workaround)

Web Audio's PannerNode does not implement Doppler natively in most browsers. Manual implementation:

```javascript
function computeDopplerShift(sourcePos, sourceVel, listenerPos, listenerVel) {
  const SPEED_OF_SOUND = 343.3;
  const toListener = vec3.subtract(listenerPos, sourcePos);
  const dist = vec3.length(toListener);
  if (dist < 0.001) return 1.0;

  const dir = vec3.scale(toListener, 1.0 / dist);
  const vl = vec3.dot(listenerVel, dir);   // listener velocity toward source
  const vs = vec3.dot(sourceVel, dir);      // source velocity toward listener

  return (SPEED_OF_SOUND - vl) / (SPEED_OF_SOUND - vs);
}

// Apply to playback rate:
source.playbackRate.value = basePitch * computeDopplerShift(carPos, carVel, camPos, camVel);
```

### Reverb via ConvolverNode

```javascript
// Replace OpenAL EFX reverb with impulse response convolution
const convolver = new ConvolverNode(ctx);
const irBuffer = await fetch('impulse-response-tunnel.wav')
  .then(r => r.arrayBuffer())
  .then(b => ctx.decodeAudioData(b));
convolver.buffer = irBuffer;

// Route: source -> dry gain (direct) -> destination
//        source -> wet gain -> convolver -> destination
const dryGain = new GainNode(ctx, { gain: 0.7 });
const wetGain = new GainNode(ctx, { gain: 0.3 });
source.connect(dryGain).connect(ctx.destination);
source.connect(wetGain).connect(convolver).connect(ctx.destination);
```

### Streaming Music with MediaElementAudioSourceNode

```javascript
// For long music tracks, use streaming instead of full decode
const audio = new Audio('music-track.ogg');
audio.loop = true;
const source = ctx.createMediaElementSource(audio);
const musicGain = new GainNode(ctx, { gain: audioMusicVolume });
source.connect(musicGain).connect(ctx.destination);
audio.play();

// Crossfade between tracks:
function crossfadeTo(newTrackUrl, duration = 2.0) {
  const newAudio = new Audio(newTrackUrl);
  const newSource = ctx.createMediaElementSource(newAudio);
  const newGain = new GainNode(ctx, { gain: 0 });
  newSource.connect(newGain).connect(ctx.destination);

  const now = ctx.currentTime;
  musicGain.gain.linearRampToValueAtTime(0, now + duration);
  newGain.gain.linearRampToValueAtTime(audioMusicVolume, now + duration);
  newAudio.play();
}
```

### Complete Audio System Node Graph

```
GAMEPLAY AUDIO (OpenAL replacement):
=====================================

[Engine RPM Layers] ----+
[Surface/Tire Sound] ---+--> [Per-Source GainNode] --> [PannerNode (HRTF)] --+
[Turbo Sound] ----------+         ^                         ^                |
[Impact Sound] ---------+    volume control           3D position            |
[Checkpoint Sound] -----+                                                    |
                                                                             v
                              [BiquadFilterNode] ----> [Scene GainNode] ----+
                              (per-zone lowpass)       (AudioSoundLimit_Scene)|
                                                                             |
                                                                             v
AMBIENT AUDIO:                                                               |
=============                                                                |
[Mood/Ambient Loop] --> [GainNode: Zone blend] ---> [Scene GainNode] -------+
[Wind Woosh] ----------> [GainNode: Speed-based] -> [Scene GainNode] -------+
                                                                             |
                                                                             v
MUSIC:                                                              [Master GainNode]
======                                                          (AudioSoundVolume)
[MediaElementSource] --> [Music GainNode] --------------------------->      |
                        (AudioMusicVolume)                                  |
                                                                            v
UI:                                                                [AudioContext.destination]
===
[UI Sound Buffers] --> [UI GainNode] --------------------------------->
                      (AudioSoundLimit_Ui)

VOICE CHAT (separate system, WebRTC):
======================================
[RTCPeerConnection] --> [MediaStreamAudioSourceNode] --> [PannerNode (3D)] --> [destination]
```

---

## 9. Complete Audio Class Catalog

### From class_hierarchy.json (52 audio-related classes total)

#### Core Audio Classes (19 classes, "Audio" category)

| Class | Description | Parent |
|-------|-------------|--------|
| `CAudioManager` | Top-level audio orchestrator | CMwNod |
| `CAudioPort` | Audio output port abstraction | CMwNod |
| `CAudioPortNull` | Null/silent audio port (disabled audio) | CAudioPort |
| `CAudioBufferKeeper` | Audio buffer lifecycle management | CMwNod |
| `CAudioListener` | 3D audio listener position/orientation | CMwNod |
| `CAudioSettings` | Audio configuration (volume, quality) | CMwNod |
| `CAudioScriptManager` | ManiaScript audio API | CMwNod |
| `CAudioScriptMusic` | Script-accessible music control | CMwNod |
| `CAudioScriptSound` | Script-accessible sound control | CMwNod |
| `CAudioSoundImplem` | Sound implementation (platform-specific) | CMwNod |
| `CAudioSource` | Base audio source | CMwNod |
| `CAudioSourceEngine` | Engine/motor sounds | CAudioSource |
| `CAudioSourceGauge` | Gauge/meter UI sounds | CAudioSource |
| `CAudioSourceMood` | Ambient mood sounds | CAudioSource |
| `CAudioSourceMulti` | Multi-layered composite sounds | CAudioSource |
| `CAudioSourceMusic` | Music playback source | CAudioSource |
| `CAudioSourceSurface` | Surface-contact sounds (tires) | CAudioSource |
| `CAudioZone` | Spatial audio zone definition | CMwNod |
| `CAudioZoneSource` | Sound source within a zone | CMwNod |

#### OpenAL Implementation (1 class)

| Class | Description | Methods |
|-------|-------------|---------|
| `COalAudioPort` | OpenAL audio port implementation | `PushData` |

#### Sound Resource Classes (12 classes, "Plug" category)

| Class | Description |
|-------|-------------|
| `CPlugAudio` | Audio resource base |
| `CPlugAudioBalance` | Audio channel balance/panning |
| `CPlugAudioEnvironment` | Audio environment (reverb presets, etc.) |
| `CPlugSound` | Sound resource base |
| `CPlugSoundComponent` | Sound component within a composite |
| `CPlugSoundEngine` | Engine sound resource (v1) |
| `CPlugSoundEngine2` | Engine sound resource (v2, current) |
| `CPlugSoundGauge` | Gauge sound resource |
| `CPlugSoundMood` | Mood/ambient sound resource |
| `CPlugSoundMulti` | Multi-layered sound resource |
| `CPlugSoundSurface` | Surface-dependent sound resource |
| `CPlugSoundVideo` | Video-associated sound |

#### Located/Spatial Sound (1 class)

| Class | Description |
|-------|-------------|
| `CPlugLocatedSound` | 3D-positioned sound resource |

#### Music Resources (2 classes)

| Class | Description |
|-------|-------------|
| `CPlugMusic` | Music track resource |
| `CPlugMusicType` | Music genre/type classification |

#### Audio File Handlers (5 classes)

| Class | Description |
|-------|-------------|
| `CPlugFileAudioMotors` | Motor sound file format (.AudioMotors) |
| `CPlugFileOggVorbis` | OGG Vorbis audio file handler |
| `CPlugFileSnd` | Generic sound file handler |
| `CPlugFileSndGen` | Generated/procedural sound file |
| `CPlugFileWav` | WAV audio file handler |

#### Game Integration Classes (7 classes)

| Class | Description |
|-------|-------------|
| `CGameCtnDecorationAudio` | Map decoration audio settings |
| `CGameAudioSettingsWrapper` | Script-accessible audio settings |
| `CGameCtnMediaBlockMusicEffect` | MediaTracker music effect block (method: `SKeyVal`) |
| `CGameCtnMediaBlockSound` | MediaTracker sound block (method: `SuperSKeyVal`) |
| `CGameCtnDecorationMood` | Map decoration mood (includes audio atmosphere) |
| `CPlugFxSystemNode_SoundEmitter` | Particle/FX system sound emitter |
| `CPlugMoodSetting` | Mood configuration (visual + audio) |

#### Mood System Classes (audio-adjacent, 5 classes)

| Class | Description |
|-------|-------------|
| `CPlugMoodAtmo` | Atmosphere mood settings |
| `CPlugMoodBlender` | Mood transition blending |
| `CPlugMoodCurve` | Mood parameter curves |
| `CHmsLightMapMood` | Lightmap mood settings |
| `CHmsMoodBlender` | HMS-level mood blender |

#### CAudioPort Methods

| Method | Purpose |
|--------|---------|
| `ApplySystemConfig` | Apply audio system configuration changes |
| `CaptureUpdate` | Update audio capture (recording) |
| `PreloadResources` | Preload audio resources into memory |

---

## 10. Audio Configuration Reference

### From Default.json (actual game configuration file)

```json
{
  "AudioEnabled": false,
  "AudioDevice_Oal": "MacBook Pro Speakers [OpenAL Soft]",
  "AudioMuteWhenAppUnfocused": true,
  "AudioSoundVolume": 0.146386,
  "AudioSoundLimit_Scene": 1,
  "AudioSoundLimit_Ui": 0.0479181,
  "AudioMusicVolume": 0,
  "AudioGlobalQuality": "normal",
  "AudioAllowEFX": true,
  "AudioAllowHRTF": true,
  "AudioDisableDoppler": false
}
```

### Parameter Details

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `AudioEnabled` | bool | true | true/false | Master audio on/off (this config has it false -- audio is disabled in this CrossOver install) |
| `AudioDevice_Oal` | string | (system default) | Device name string | OpenAL device name. Format: `"<device> [OpenAL Soft]"`. Empty string = system default |
| `AudioMuteWhenAppUnfocused` | bool | true | true/false | Mute audio when game window loses focus |
| `AudioSoundVolume` | float | ~0.8 | 0.0 - 1.0 | Master sound effects volume. Maps to overall gain multiplier |
| `AudioSoundLimit_Scene` | float | 1.0 | 0.0 - 1.0 | Scene/gameplay sound volume limit. Multiplied with AudioSoundVolume for final scene gain |
| `AudioSoundLimit_Ui` | float | ~0.5 | 0.0 - 1.0 | UI sound volume limit. Multiplied with AudioSoundVolume for final UI gain |
| `AudioMusicVolume` | float | ~0.5 | 0.0 - 1.0 | Music volume (independent from SFX). 0 = music off |
| `AudioGlobalQuality` | string | "normal" | "normal" (others [UNKNOWN]) | Overall audio quality setting. May affect sample rate, source count, or processing quality |
| `AudioAllowEFX` | bool | true | true/false | Enable OpenAL EFX environmental effects (reverb, filters). Disable for lower CPU usage |
| `AudioAllowHRTF` | bool | true | true/false | Enable Head-Related Transfer Function for binaural 3D audio. Best with headphones |
| `AudioDisableDoppler` | bool | false | true/false | Disable Doppler effect. When false (default), moving sound sources shift in pitch |

### Voice Chat Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `VoiceChat_Device_In` | string | "default" | Microphone input device |
| `VoiceChat_Device_Out` | string | "default" | Speaker output device |
| `VoiceChat_SpeakerVolume` | float | 1.0 | Voice chat speaker volume (0-1) |
| `VoiceChat_VoiceDetection_Mode` | string | "pushtotalk" | Voice activation mode: "pushtotalk" or [UNKNOWN VAD mode string] |
| `VoiceChat_VoiceDetection_Sensitivity` | float | 1.0 | VAD sensitivity (0-1, higher = more sensitive) |
| `VoiceChat_VoiceDetection_Auto` | bool | false | Automatic voice detection |
| `VoiceChat_VoiceDetection` | int | 1 | Voice detection enabled (1) / disabled (0) |

### Volume Hierarchy

```
Final Scene Sound Volume  = AudioSoundVolume * AudioSoundLimit_Scene
Final UI Sound Volume     = AudioSoundVolume * AudioSoundLimit_Ui
Final Music Volume        = AudioMusicVolume (independent)
Final Voice Chat Volume   = VoiceChat_SpeakerVolume (independent)

Example from this config:
  Scene: 0.146386 * 1.0 = 0.146386 (14.6%)
  UI:    0.146386 * 0.0479181 = 0.00701 (0.7%)
  Music: 0.0 (muted)
  Voice: 1.0 (100%)
```

### Vivox Configuration Keys (from VoiceChat.dll strings)

| Key | Description |
|-----|-------------|
| `voicechat.vivox.server_url` | Vivox backend server URL (default: `https://hyxd.www.vivox.com/api2`) |
| `voicechat.vivox.token_issuer` | Token authentication issuer |
| `voicechat.vivox.access_token_key` | Access token key for auth |
| `voicechat.vivox.domain` | Vivox domain |
| `voicechat.vivox.channel_uri` | Channel URI for current session |
| `voicechat.vivox.account_uri` | Account URI |
| `voicechat.vivox.profile_id` | User profile ID |
| `voicechat.vivox.token` | Auth token |
| `voicechat.vivox.token_type` | Token type |
| `voicechat.vivox.account_name` | Account name |
| `voicechat.vivox.3d` | Enable 3D positional voice |
| `voicechat.vivox.log_level` | Log verbosity |
| `voicechat.vivox.delay_connect` | Deferred connection |
| `voicechat.vivox.logfileName` | Log file name (`VivoxTrackmania`) |
| `voicechat.vivox.default_language.text_chat` | Default text language |
| `voicechat.vivox.default_language.voice_chat` | Default voice language |
| `voicechat.vivox.default_language.text_to_speech` | TTS language |
| `voicechat.vivox.default_language.speech_to_text` | STT language |
| `voicechat.vivox.platform_check_permission` | Permission checks |

---

## Appendix A: OpenAL Soft Extensions Available in TM2020

The bundled `OpenAL64_bundled.dll` exposes the following ALC extension string (from `strings` extraction):

```
ALC_ENUMERATE_ALL_EXT
ALC_ENUMERATION_EXT
ALC_EXT_CAPTURE
ALC_EXT_debug
ALC_EXT_DEDICATED
ALC_EXT_direct_context
ALC_EXT_disconnect
ALC_EXT_EFX
ALC_EXT_thread_local_context
ALC_SOFT_device_clock
ALC_SOFT_HRTF
ALC_SOFT_loopback
ALC_SOFT_loopback_bformat
ALC_SOFT_output_limiter
ALC_SOFT_output_mode
ALC_SOFT_pause_device
ALC_SOFT_reopen_device
ALC_SOFT_system_events
```

Key AL extensions:
```
AL_EXT_ALAW, AL_EXT_BFORMAT, AL_EXT_DOUBLE, AL_EXT_EXPONENT_DISTANCE,
AL_EXT_FLOAT32, AL_EXT_IMA4, AL_EXT_LINEAR_DISTANCE, AL_EXT_MCFORMATS,
AL_EXT_MULAW, AL_EXT_MULAW_BFORMAT, AL_EXT_MULAW_MCFORMATS, AL_EXT_OFFSET,
AL_EXT_source_distance_model, AL_EXT_SOURCE_RADIUS, AL_EXT_STATIC_BUFFER,
AL_EXT_STEREO_ANGLES, AL_EXT_debug, AL_EXT_direct_context,
AL_SOFT_bformat_ex, AL_SOFT_block_alignment, AL_SOFT_buffer_length_query,
AL_SOFT_buffer_sub_data, AL_SOFT_callback_buffer, AL_SOFT_deferred_updates,
AL_SOFT_direct_channels, AL_SOFT_direct_channels_remix, AL_SOFT_effect_target,
AL_SOFT_events, AL_SOFT_gain_clamp_ex, AL_SOFT_loop_points, AL_SOFT_MSADPCM,
AL_SOFT_source_latency, AL_SOFT_source_length, AL_SOFT_source_resampler,
AL_SOFT_source_spatialize, AL_SOFT_source_start_delay, AL_SOFT_UHJ,
AL_SOFT_UHJ_ex, AL_SOFTX_bformat_hoa, AL_SOFTX_convolution_effect,
AL_SOFTX_hold_on_disconnect, AL_SOFTX_map_buffer, AL_SOFTX_source_panning
```

---

## Appendix B: Audio Format Support

### Confirmed via DLL Strings

| Format | DLL | Evidence |
|--------|-----|----------|
| Ogg Vorbis | `vorbis64.dll` | `Xiph.Org libVorbis 1.3.5` -- full encode/decode |
| WAV (PCM) | `OpenAL64_bundled.dll` | `AL_FORMAT_MONO8`, `AL_FORMAT_MONO16`, `AL_FORMAT_STEREO8`, `AL_FORMAT_STEREO16` |
| WAV (Float32) | `OpenAL64_bundled.dll` | `AL_FORMAT_MONO_FLOAT32`, `AL_FORMAT_STEREO_FLOAT32` |
| IMA ADPCM | `OpenAL64_bundled.dll` | `AL_FORMAT_MONO_IMA4`, `AL_FORMAT_STEREO_IMA4` |
| MS ADPCM | `OpenAL64_bundled.dll` | `AL_FORMAT_MONO_MSADPCM_SOFT`, `AL_FORMAT_STEREO_MSADPCM_SOFT` |
| A-Law | `OpenAL64_bundled.dll` | `AL_FORMAT_MONO_ALAW_EXT` |
| mu-Law | `OpenAL64_bundled.dll` | `AL_FORMAT_MONO_MULAW`, `AL_EXT_MULAW` |
| Multi-channel (5.1/6.1/7.1) | `OpenAL64_bundled.dll` | `AL_FORMAT_51CHN16`, `AL_FORMAT_61CHN16`, `AL_FORMAT_71CHN16` (and float/int/mulaw variants) |
| B-Format (Ambisonics) | `OpenAL64_bundled.dll` | `AL_FORMAT_BFORMAT2D_*`, `AL_FORMAT_BFORMAT3D_*` |
| UHJ Stereo | `OpenAL64_bundled.dll` | `AL_FORMAT_UHJ2CHN*`, `AL_FORMAT_UHJ3CHN*`, `AL_FORMAT_UHJ4CHN*` |

### Confirmed via Class Hierarchy

| Handler Class | Format |
|---------------|--------|
| `CPlugFileOggVorbis` | .ogg (Ogg Vorbis) |
| `CPlugFileWav` | .wav (RIFF WAVE) |
| `CPlugFileSnd` | .snd (generic sound, [UNKNOWN internal format]) |
| `CPlugFileSndGen` | (procedural/generated, no file) |
| `CPlugFileAudioMotors` | .AudioMotors (motor profile, [UNKNOWN internal format]) |

---

## Appendix C: Surface ID to Audio Mapping

Surface materials affect tire/surface sounds. `CPlugSoundSurface` + `CAudioSourceSurface` select the appropriate tire sound based on `GroundContactMaterial` (ESurfId, uint16) from each wheel's state.

| Surface ID | Physics Character | Expected Audio |
|-----------|-------------------|----------------|
| `Asphalt` | Road surface, high grip | Clean rolling, loud screech on slip |
| `Concrete` | Structural surface | Similar to asphalt, harder tone |
| `Dirt` | Off-road, lower grip | Gravel crunch, loose surface spray |
| `Grass` | Natural ground, low grip | Soft swishing, muted rolling |
| `Green` | Vegetation surface | Similar to grass |
| `Ice` | Very low grip | Smooth sliding, minimal friction sound |
| `Metal` | Metallic surface | Metallic ringing/clang |
| `MetalTrans` | Transparent metal | Similar to metal |
| `Pavement` | Sidewalk/paved | Between asphalt and concrete |
| `Plastic` | Inflatable/obstacle | Soft impact, bouncy |
| `ResonantMetal` | Resonant metallic | Metallic resonance, ringing |
| `RoadIce` | Icy road surface | Mix of road and ice sounds |
| `RoadSynthetic` | Synthetic road | Distinct synthetic surface texture |
| `Rock` | Natural rock | Rocky crunch |
| `Rubber` | Bouncy rubber | Rubber squeak, bouncy |
| `Sand` | Sandy surface | Soft granular sound |
| `Snow` | Snow surface | Crunchy, muffled |
| `Wood` | Wooden surface | Wooden clatter |
| `NotCollidable` | Pass-through | No sound (no contact) |

**Evidence**: 19 surface types from `NadeoImporterMaterialLib.txt` analysis in `09-game-files-analysis.md`. Wheel `GroundContactMaterial` field from `19-openplanet-intelligence.md`.

---

## Appendix D: Open Questions and Unknowns

| Question | Status | What Would Resolve It |
|----------|--------|-----------------------|
| Which OpenAL distance model does TM2020 use? | UNKNOWN | Decompile source setup code (where `alDistanceModel` or `alSourcei(AL_DISTANCE_MODEL)` is called) |
| CPlugSoundEngine vs CPlugSoundEngine2 differences? | UNKNOWN | Decompile both class vtables and compare update methods |
| CPlugFileAudioMotors format specification? | UNKNOWN | Extract .AudioMotors files from pack files and analyze binary format |
| How many RPM sample layers per engine? | UNKNOWN | Extract motor audio data from game packs |
| Audio zone blending algorithm? | UNKNOWN | Decompile CAudioZone update method |
| Audio zone shape (box/sphere/etc.)? | UNKNOWN | Decompile CAudioZone geometry |
| Does TM2020 use audio occlusion/obstruction? | UNKNOWN | Search for raycast + filter combination in audio update code |
| Music crossfade/transition logic? | UNKNOWN | Decompile CAudioSourceMusic state machine |
| Dynamic/adaptive music system? | UNKNOWN | Analyze CPlugMusicType categorization |
| AudioGlobalQuality "normal" vs other values? | UNKNOWN | Search for quality enum in binary strings |
| Exact CameraWoosh parameters? | UNKNOWN | Decompile camera audio coupling code |
| Source priority/virtualization system? | UNKNOWN | Decompile CAudioManager source management |
| CPlugFileSndGen procedural generation? | UNKNOWN | Decompile the SndGen class |
| Per-vehicle-type sound differences? | UNKNOWN | Compare audio resources for CarSport/CarSnow/CarRally/CarDesert |

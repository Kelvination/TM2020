# Trackmania 2020 Audio System Deep Dive

TM2020 uses **OpenAL Soft** via `OpenAL64_bundled.dll` for all spatial and gameplay audio. Voice chat uses a separate **Vivox SDK** (v5.19.2) pipeline. Audio files are decoded with **libVorbis 1.3.5** (`vorbis64.dll`). This document maps TM2020's audio architecture for recreation with the Web Audio API.

---

## How the Audio Pipeline Works

### High-Level Architecture

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

**Evidence**: Class hierarchy from `class_hierarchy.json` (2,027 Nadeo classes, 30 in Audio category).

### Audio File Format Pipeline

```
.ogg (Ogg Vorbis) --[CPlugFileOggVorbis]--> CPlugSound --> CAudioSource --> OpenAL Buffer
.wav              --[CPlugFileWav]--------> CPlugSound --> CAudioSource --> OpenAL Buffer
.snd              --[CPlugFileSnd]--------> CPlugSound --> CAudioSource --> OpenAL Buffer
(procedural)      --[CPlugFileSndGen]-----> CPlugSound --> CAudioSource --> OpenAL Buffer
.AudioMotors      --[CPlugFileAudioMotors]-> CPlugSoundEngine / CPlugSoundEngine2 --> OpenAL Buffer
```

---

## How OpenAL Is Initialized

The decompiled `COalAudioPort::InitImplem` (at `0x14138c090`) reveals the exact initialization:

1. **Dynamic loading**: `LoadLibrary("OpenAL64_bundled.dll")`
2. **Function resolution**: Resolves `alcOpenDevice`, `alcGetProcAddress`, `alcGetError`, `alcIsExtensionPresent`, `alcGetString`, `alcCloseDevice`
3. **Device opening**: Tries named device first (from config `AudioDevice_Oal`), falls back to `ALC_DEFAULT_DEVICE_SPECIFIER` (`0x1005`)
4. **Context creation**: `alcCreateContext` on the opened device
5. **Version query**: `alcGetIntegerv` with `ALC_MAJOR_VERSION`/`ALC_MINOR_VERSION` -- expects ALC 1.x
6. **Source count query**: `ALC_MONO_SOURCES` (`0x1010`) and `ALC_STEREO_SOURCES` (`0x1011`)
7. **String queries**: `AL_VERSION`, `AL_RENDERER`, `AL_EXTENSIONS`, `AL_VENDOR`
8. **EFX check**: `alcIsExtensionPresent` for EFX support
9. **Log output**: `"[Audio] Initialized, using device '<name>', sources = N+M, EFX enabled/disabled"`

### Anti-Tamper Obfuscation

Function pointers in the `COalAudioPort` struct are XOR/ADD obfuscated:

| Offset | Type | Description |
|--------|------|-------------|
| +0x298 | ptr | `alcOpenDevice` (XOR obfuscated) |
| +0x2A0 | ptr | `alcCloseDevice` |
| +0x2A8 | ptr | `alcGetProcAddress` |
| +0x2B1 | ptr | `alcGetError` (XOR obfuscated) |
| +0x2C8 | ptr | OpenAL DLL handle |
| +0x2D9 | str | Device name string |
| +0x31D | byte | Initialized flag |
| +0x321 | ptr | ALC device handle |
| +0x338 | lock | Mutex |

### Simultaneous Source Count

The game queries `ALC_MONO_SOURCES` and `ALC_STEREO_SOURCES` at init. OpenAL Soft typically supports **256 mono + 256 stereo sources**.

### EFX (Environmental Effects) Support

When `AudioAllowEFX = true`, these effects are available:

- `AL_EFFECT_REVERB` / `AL_EFFECT_EAXREVERB` (22 parameters)
- `AL_EFFECT_CHORUS`, `AL_EFFECT_DISTORTION`, `AL_EFFECT_ECHO`
- `AL_EFFECT_FLANGER`, `AL_EFFECT_FREQUENCY_SHIFTER`
- `AL_EFFECT_PITCH_SHIFTER`, `AL_EFFECT_RING_MODULATOR`
- `AL_EFFECT_COMPRESSOR`, `AL_EFFECT_EQUALIZER`
- `AL_EFFECT_DEDICATED_DIALOGUE`, `AL_EFFECT_DEDICATED_LOW_FREQUENCY_EFFECT`
- `AL_EFFECT_CONVOLUTION_SOFT` (OpenAL Soft extension)

**Filters**: `AL_FILTER_LOWPASS`, `AL_FILTER_HIGHPASS`, `AL_FILTER_BANDPASS`

`CPlugAudioEnvironment` maps to EFX reverb presets per audio zone. `CPlugAudioBalance` handles channel panning.

### HRTF (Head-Related Transfer Function)

OpenAL Soft includes full HRTF support for binaural 3D audio. Config: `AudioAllowHRTF = true` in `Default.json`. When headphones are detected, OpenAL Soft automatically enables HRTF.

HRTF-related extensions: `ALC_SOFT_HRTF`, `ALC_HRTF_STATUS_SOFT`, `ALC_HRTF_SPECIFIER_SOFT`, `ALC_STEREO_HRTF_SOFT`.

### Supported Output Modes

Mono, Stereo, Stereo HRTF, Quad, 5.1, 6.1, 7.1, 7.1.4 Surround, and B-Format 3D (Ambisonics).

---

## Sound Type Catalog

Each category has a **source** class (runtime emitter) and **resource** class (loadable data):

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

### Audio Events by Gameplay Context

**Car Sounds:**
| Event | Likely Sound Type | Evidence |
|-------|-------------------|----------|
| Engine idle/rev | `CPlugSoundEngine2` | RPM field (0-11000) in vehicle state |
| Tire rolling | `CPlugSoundSurface` | 19 surface IDs (Asphalt, Dirt, Grass, Ice, etc.) |
| Tire screech/slip | `CPlugSoundSurface` | `SlipCoef` (0-1) per wheel |
| Wind noise | [UNKNOWN] | `CameraWooshVolumedB`, `CameraWooshMinSpeedKmh` strings |
| Turbo activation | [UNKNOWN, likely `CPlugSoundMulti`] | `IsTurbo`, `TurboTime` fields |
| Gear shift | [UNKNOWN] | `CurGear` (0-7) tracked |

**Environment Sounds:**
| Event | Likely Sound Type | Evidence |
|-------|-------------------|----------|
| Map ambient | `CPlugSoundMood` | `CGameCtnDecorationAudio` for map audio |
| Water splash | [UNKNOWN] | `WaterImmersionCoef` (0-1) in vehicle state |
| Zone ambience | `CAudioZone` / `CAudioZoneSource` | Spatial zone classes exist |

---

## How Engine Sound Works

TM2020 has TWO engine sound systems -- `CPlugSoundEngine` (v1) and `CPlugSoundEngine2` (v2). The engine sound is **sample-based with RPM-mapped crossfading**, not pure synthesis. `CPlugFileAudioMotors` stores motor sound profiles.

### RPM-to-Pitch Mapping

From the vehicle state:
- `RPM`: float, range 0-11000
- `CurGear`: uint, range 0-7
- `FrontSpeed`: float, m/s
- `InputGasPedal`: float, 0.0-1.0

**Probable model** (PLAUSIBLE):
```
For each gear:
  1. Select RPM-appropriate sample layers from CPlugFileAudioMotors
  2. Crossfade between adjacent RPM layers based on current RPM
  3. Adjust playback rate (pitch) proportional to RPM within each layer's range
  4. Apply load modulation based on InputGasPedal
  5. On gear change, crossfade between gear-specific sound sets
```

### Load-Dependent Sound Changes

- `InputGasPedal` (0-1) modulates engine character (on-throttle vs coasting)
- `InputIsBraking` triggers engine braking sound
- `IsTurbo` and `TurboTime` (0-1) overlay boost effect
- `ReactorBoostLvl` triggers reactor audio

### Open Questions

- Exact crossfade algorithm between RPM layers
- How many RPM sample layers per gear
- `CPlugFileAudioMotors` file format specification
- Whether v1 and v2 are used for different vehicle types (CarSport vs CarSnow vs CarRally vs CarDesert)
- Pitch curve shape (linear? exponential?)

---

## How 3D Spatial Audio Works

### Listener Position

`CAudioListener` tracks the 3D audio listener. It is almost certainly tied to the active camera position and orientation.

**Evidence**: `CameraWooshVolumedB` and `CameraWooshMinSpeedKmh` strings confirm camera-audio coupling. The camera system has 12 types; the listener follows whichever is active.

### Distance Attenuation Models

OpenAL Soft supports inverse, linear, and exponent distance models (clamped and unclamped variants). [UNKNOWN] which model TM2020 selects. The default `AL_INVERSE_DISTANCE_CLAMPED` is most common.

Per-source parameters: `AL_REFERENCE_DISTANCE`, `AL_MAX_DISTANCE`, `AL_ROLLOFF_FACTOR`, cone angles, `AL_AIR_ABSORPTION_FACTOR`.

### Doppler Effect

Enabled by default (`AudioDisableDoppler = false`). OpenAL provides `AL_DOPPLER_FACTOR` and `AL_SPEED_OF_SOUND` (default 343.3 m/s). Vehicle `WorldVel` (vec3, m/s) from the physics system likely sets each car's source velocity.

### Audio Zones

`CAudioZone` and `CAudioZoneSource` provide zone-based spatial audio. `CPlugAudioEnvironment` stores per-zone reverb settings. `CPlugSoundMood` provides ambient sounds per zone.

[UNKNOWN]: Zone blending at boundaries, zone shape, and typical zone count per map.

### Occlusion/Obstruction

[UNKNOWN]: No direct evidence of audio occlusion found. OpenAL EFX supports occlusion via `AL_DIRECT_FILTER`, and `AL_FILTER_LOWPASS` is available. Whether TM2020 performs raycast-based occlusion is unconfirmed.

---

## How Music Works

- `CPlugMusic` -- Music track resource
- `CPlugMusicType` -- Genre/type classification
- `CAudioSourceMusic` -- Runtime playback
- `CAudioScriptMusic` -- ManiaScript control

`CGameCtnMediaBlockMusicEffect` (with `SKeyVal`) supports keyframed music in MediaTracker clips. `CGameCtnMediaBlockSound` (with `SuperSKeyVal`) handles sound effects in MediaTracker.

Volume channels are separated: `AudioSoundVolume` (SFX), `AudioSoundLimit_Scene`, `AudioSoundLimit_Ui`, `AudioMusicVolume` (independent).

[UNKNOWN]: Dynamic music that changes with gameplay, crossfade logic between tracks, and automatic ducking.

---

## How Voice Chat Works

### Vivox SDK Integration

```
Game (Trackmania.exe)
  |
  +-- VoiceChat.dll (Nadeo's "Harbour" framework wrapper, 1.24 MB)
        |
        +-- vivoxsdk.dll (Vivox SDK v5.19.2, 11.87 MB)
```

**Protocol**: SIP with STUN, RTP for media. **Server**: `https://hyxd.www.vivox.com/api2`.

### Channel Types

From `vivoxsdk.dll`: echo test (`sip:confctl-e-`), group voice (`sip:confctl-g-`), direct 1-to-1 (`sip:confctl-d-`).

### 3D Positional Voice

Config `voicechat.vivox.3d` enables positional voice. The string `Fail send update 3D position.` confirms position updates during gameplay.

### Push-to-Talk vs Open Mic

Default: push-to-talk. Both modes supported. Vivox audio processing features: AEC, AGC, VAD (togglable via environment variables).

---

## Mapping to Web Audio API

### Architecture Mapping

| TM2020 (OpenAL) | Web Audio API | Notes |
|---|---|---|
| `alcOpenDevice` / `alcCreateContext` | `new AudioContext()` | Single AudioContext per page |
| `CAudioListener` / `alListenerfv` | `AudioContext.listener` | Built-in listener |
| `alGenSources` / `alSourcefv` | `new PannerNode()` | One PannerNode per 3D source |
| `alGenBuffers` / `alBufferData` | `decodeAudioData()` | Decode OGG/WAV to AudioBuffer |
| `alSourcePlay` | `AudioBufferSourceNode.start()` | Web Audio sources are one-shot |
| `AL_GAIN` | `GainNode` | Per-source volume |
| `AL_PITCH` | `AudioBufferSourceNode.playbackRate` | Pitch via playback rate |
| `AL_POSITION` / `AL_VELOCITY` | `PannerNode.positionX/Y/Z` | 3D position per source |
| EFX Reverb | `ConvolverNode` | Requires impulse response samples |
| EFX Lowpass Filter | `BiquadFilterNode` (type: 'lowpass') | Built-in |
| `AL_DOPPLER_FACTOR` | Manual computation via `playbackRate` | [LIMITATION] PannerNode lacks native Doppler |
| HRTF | `PannerNode.panningModel = 'HRTF'` | Built-in |

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

**Per frame**: Read RPM, determine bracketing layers, calculate crossfade weight, set GainNode values, adjust playback rate, update PannerNode position.

**Simpler MVP approach**:
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

### Manual Doppler Effect (Web Audio Workaround)

```javascript
function computeDopplerShift(sourcePos, sourceVel, listenerPos, listenerVel) {
  const SPEED_OF_SOUND = 343.3;
  const toListener = vec3.subtract(listenerPos, sourcePos);
  const dist = vec3.length(toListener);
  if (dist < 0.001) return 1.0;

  const dir = vec3.scale(toListener, 1.0 / dist);
  const vl = vec3.dot(listenerVel, dir);
  const vs = vec3.dot(sourceVel, dir);

  return (SPEED_OF_SOUND - vl) / (SPEED_OF_SOUND - vs);
}

// Apply to playback rate:
source.playbackRate.value = basePitch * computeDopplerShift(carPos, carVel, camPos, camVel);
```

### Reverb via ConvolverNode

```javascript
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

## Complete Audio Class Catalog

### Core Audio Classes (19 classes)

| Class | Description | Parent |
|-------|-------------|--------|
| `CAudioManager` | Top-level orchestrator | CMwNod |
| `CAudioPort` | Output port abstraction | CMwNod |
| `CAudioPortNull` | Null/silent port | CAudioPort |
| `CAudioBufferKeeper` | Buffer lifecycle | CMwNod |
| `CAudioListener` | 3D listener | CMwNod |
| `CAudioSettings` | Volume/quality config | CMwNod |
| `CAudioScriptManager` | ManiaScript audio API | CMwNod |
| `CAudioScriptMusic` | Script music control | CMwNod |
| `CAudioScriptSound` | Script sound control | CMwNod |
| `CAudioSoundImplem` | Platform-specific impl | CMwNod |
| `CAudioSource` | Base source | CMwNod |
| `CAudioSourceEngine` | Engine/motor sounds | CAudioSource |
| `CAudioSourceGauge` | Gauge UI sounds | CAudioSource |
| `CAudioSourceMood` | Ambient mood | CAudioSource |
| `CAudioSourceMulti` | Multi-layered sounds | CAudioSource |
| `CAudioSourceMusic` | Music playback | CAudioSource |
| `CAudioSourceSurface` | Tire sounds | CAudioSource |
| `CAudioZone` | Spatial zone | CMwNod |
| `CAudioZoneSource` | Source within zone | CMwNod |

### Sound Resource Classes (12 classes)

| Class | Description |
|-------|-------------|
| `CPlugAudio` | Audio resource base |
| `CPlugAudioBalance` | Channel balance/panning |
| `CPlugAudioEnvironment` | Reverb presets |
| `CPlugSound` | Sound resource base |
| `CPlugSoundComponent` | Component in composite |
| `CPlugSoundEngine` | Engine sound v1 |
| `CPlugSoundEngine2` | Engine sound v2 (current) |
| `CPlugSoundGauge` | Gauge sound |
| `CPlugSoundMood` | Mood/ambient sound |
| `CPlugSoundMulti` | Multi-layered sound |
| `CPlugSoundSurface` | Surface-dependent sound |
| `CPlugSoundVideo` | Video-associated sound |

### Audio File Handlers (5 classes)

| Class | Description |
|-------|-------------|
| `CPlugFileAudioMotors` | Motor sound format (.AudioMotors) |
| `CPlugFileOggVorbis` | OGG Vorbis handler |
| `CPlugFileSnd` | Generic sound handler |
| `CPlugFileSndGen` | Generated/procedural sound |
| `CPlugFileWav` | WAV handler |

### Game Integration Classes (7 classes)

| Class | Description |
|-------|-------------|
| `CGameCtnDecorationAudio` | Map decoration audio |
| `CGameAudioSettingsWrapper` | Script audio settings |
| `CGameCtnMediaBlockMusicEffect` | MediaTracker music (method: `SKeyVal`) |
| `CGameCtnMediaBlockSound` | MediaTracker sound (method: `SuperSKeyVal`) |
| `CGameCtnDecorationMood` | Map mood (includes audio) |
| `CPlugFxSystemNode_SoundEmitter` | FX system emitter |
| `CPlugMoodSetting` | Mood config (visual + audio) |

---

## Audio Configuration Reference

### Default.json Parameters

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `AudioEnabled` | bool | true/false | Master audio on/off |
| `AudioDevice_Oal` | string | Device name | OpenAL device. Format: `"<device> [OpenAL Soft]"` |
| `AudioMuteWhenAppUnfocused` | bool | true/false | Mute when window loses focus |
| `AudioSoundVolume` | float | 0.0-1.0 | Master SFX volume |
| `AudioSoundLimit_Scene` | float | 0.0-1.0 | Scene sound limit |
| `AudioSoundLimit_Ui` | float | 0.0-1.0 | UI sound limit |
| `AudioMusicVolume` | float | 0.0-1.0 | Music volume (independent) |
| `AudioGlobalQuality` | string | "normal" | Audio quality setting |
| `AudioAllowEFX` | bool | true/false | Enable environmental effects |
| `AudioAllowHRTF` | bool | true/false | Enable binaural 3D audio |
| `AudioDisableDoppler` | bool | true/false | Disable Doppler pitch shift |

### Volume Hierarchy

```
Final Scene Sound Volume  = AudioSoundVolume * AudioSoundLimit_Scene
Final UI Sound Volume     = AudioSoundVolume * AudioSoundLimit_Ui
Final Music Volume        = AudioMusicVolume (independent)
Final Voice Chat Volume   = VoiceChat_SpeakerVolume (independent)
```

### Voice Chat Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `VoiceChat_Device_In` | string | "default" | Microphone |
| `VoiceChat_Device_Out` | string | "default" | Speaker |
| `VoiceChat_SpeakerVolume` | float | 1.0 | Voice volume |
| `VoiceChat_VoiceDetection_Mode` | string | "pushtotalk" | Activation mode |
| `VoiceChat_VoiceDetection_Sensitivity` | float | 1.0 | VAD sensitivity |

### Surface ID to Audio Mapping

| Surface ID | Expected Audio |
|-----------|----------------|
| `Asphalt` | Clean rolling, loud screech on slip |
| `Concrete` | Similar to asphalt, harder tone |
| `Dirt` | Gravel crunch, loose surface spray |
| `Grass` | Soft swishing, muted rolling |
| `Ice` / `RoadIce` | Smooth sliding, minimal friction |
| `Metal` | Metallic ringing/clang |
| `Plastic` | Soft impact, bouncy |
| `Rubber` | Rubber squeak, bouncy |
| `Sand` | Soft granular |
| `Snow` | Crunchy, muffled |
| `Wood` | Wooden clatter |
| `NotCollidable` | No sound |

### Open Questions

| Question | What Would Resolve It |
|----------|-----------------------|
| Which OpenAL distance model does TM2020 use? | Decompile source setup code |
| CPlugSoundEngine vs CPlugSoundEngine2 differences? | Decompile both vtables |
| CPlugFileAudioMotors format? | Extract .AudioMotors from packs |
| How many RPM sample layers per engine? | Extract motor audio data |
| Audio zone blending algorithm? | Decompile CAudioZone update |
| Does TM2020 use audio occlusion? | Search for raycast + filter in audio code |
| Dynamic/adaptive music system? | Analyze CPlugMusicType |

## Related Pages

- [09-game-files-analysis.md](09-game-files-analysis.md) -- Game file analysis including DLL strings
- [13-subsystem-class-map.md](13-subsystem-class-map.md) -- Subsystem class catalog
- [15-ghidra-research-findings.md](15-ghidra-research-findings.md) -- Ghidra findings including audio strings
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Vehicle state fields (RPM, speed, etc.)
- [27-dll-intelligence.md](27-dll-intelligence.md) -- DLL analysis including OpenAL and Vivox
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Browser recreation architecture

<details><summary>Analysis metadata</summary>

**Date**: 2026-03-27
**Sources**: Ghidra decompilation, DLL string extraction, class hierarchy analysis, game configuration, Openplanet plugin intelligence
**Purpose**: Reverse-engineering analysis of TM2020's audio architecture for Web Audio API recreation

</details>

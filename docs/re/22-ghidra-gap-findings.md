# Ghidra Gap-Filling Research Findings

This research decompiled 13 critical functions to fill the biggest gaps in our RE documentation. Six of seven force models are now decompiled. The complete surface gameplay enum (22 values), ghost API (27+ functions), 23-step map loading pipeline, and pack file system are documented.

## Gap Severity Summary

| Gap | Severity | Status | Key Finding |
|:----|:--------:|:------:|:------------|
| Force model internals (7 functions) | CRITICAL | 6 of 7 resolved | Cases 0-3, 5, 6, 0xB decompiled; case 4 partial |
| Surface gameplay effects | HIGH | Resolved | Full 22-value EPlugSurfaceGameplayId enum |
| Ghost/replay binary format | HIGH | Partially resolved | Full API (27 functions), XML header; binary chunk format unknown |
| Map loading pipeline | MEDIUM | Resolved | 23-step pipeline with block/item placement |
| Audio system internals | MEDIUM | Resolved | 7 source types, layered engine sound model |
| Checkpoint/respawn system | MEDIUM | Resolved | Launched checkpoints with physics forces |
| Pack file format | LOW | Resolved | Full lifecycle, encryption, GBX body dispatch |

Decompiled functions are saved in `decompiled/physics/` (13 files).

## Force Model Internals

### 4-Wheel Base Model -- Cases 0/1/2 (FUN_140869cd0)

The base 4-wheel force model handles legacy/simple vehicle types. Fully decompiled at ~300 lines.

- Iterates over 4 wheels (stride 0xB8 per wheel, starting at car_state+0x1780)
- Per-wheel surface material lookup from vtable: `*car_state + 0x6B8 + surface_id * 8`
- Surface ID is a byte at wheel_state+0x40
- Applies forces via FUN_140845210 (linear force) and FUN_140845260 (torque)
- Speed-dependent coefficients sampled from curves via FUN_14042bcb0
- Uses `car_state[0x2EB]` as friction coefficient and `car_state[0x2EC]` as acceleration coefficient
- These map directly to `Tunings.CoefFriction` and `Tunings.CoefAcceleration` strings
- Anti-roll bar forces computed via cross products
- Speed clamping at min/max bounds from tuning data (offsets 0xAB0, 0xAB4)
- Air resistance proportional to v squared
- Engine braking torque at offset 0x19D0

Confidence: VERIFIED

### 2-Wheel Bicycle Model -- Case 3 (FUN_14086b060)

A simplified bicycle-model physics system. Fully decompiled at ~250 lines.

- Uses a single-axis (front/rear) force decomposition instead of 4 independent wheels
- Steering via atan2 of velocity components (FUN_14018d310)
- Sin/cos decomposition of steering angle for longitudinal/lateral force split
- **Drift state machine** with 3 states:
  - `offset+0x1460 == 0`: No drift
  - `offset+0x1460 == 1`: Drift building (slip accumulated at 0x1458)
  - `offset+0x1460 == 2`: Drift committed (using stored angle)
- Drift angle clamped by max value at tuning+0x1B78
- Drift builds proportional to `lateral_slip * drift_rate * delta_time` (tuning+0x1B6C)
- Lateral grip computation delegated to FUN_14086af20
- Yaw damping: linear term (tuning+0x1A54) + quadratic term (tuning+0x1A58)
- Suspension model at car_state+0x1280 (different from 4-wheel model at +0x250)

Confidence: VERIFIED

### CarSport Full Model -- Case 6 (FUN_14085c9e0)

The most complex force model, handling the Stadium car. Fully decompiled at ~350 lines.

- Receives 3 parameters including simulation timestamp (for time-dependent effects)
- Sub-function breakdown:
  - `FUN_1408570e0`: Per-wheel force calculation (called 4 times)
  - `FUN_14085ad30`: Steering model
  - `FUN_14085a0d0`: Suspension/contact update
  - `FUN_14085ba50`: Anti-roll bar
  - `FUN_140858c90`: Damping
  - `FUN_140857380`: Drift/skid model
  - `FUN_140857b20`: Boost/reactor forces
  - `FUN_14085c1b0`: Airborne control forces
  - `FUN_14085b600`: Final force integration
- **Launched checkpoint boost system**:
  - Checks timestamp against checkpoint grace period (offset+0x15A8)
  - Applies directional boost forces from checkpoint data
  - Uses force curves at checkpoint_data+0x30 for speed-dependent boost
- **Post-respawn force application**:
  - Duration at tuning+0x2B80
  - Applies fade-out force over 2x the stored duration
  - Linear fade from full to zero
- Grip state at car_state+0x2B9, clamped to minimum at tuning+0x2AFC
- Speed thresholds at tuning+0x2AE0 (low) and 0x2AE4 (high)
- Two steering sensitivity modes: normal at car_state+0x2B1, custom at car_state+0x158C
  - Selection based on flag at car_state+0x15DC

Confidence: VERIFIED

### Advanced 4-Wheel Model -- Case 5 (FUN_140851f00)

The second largest force model (~1185 lines). 4-wheel model with jump detection and crash damage.

- Per-wheel iteration (stride 0xB8, starting at car_state+0x1780)
- Surface material lookup: `*car_state + 0x6B8 + surface_id * 8` (same pattern as other models)
- **Jump/impact detection state machine** at car_state[0x28F]:
  - State 0: Normal driving
  - State 1: Jump initiated (timestamp stored at car_state+0x149C)
  - State 2: Delegated to FUN_14084e6e0 (early return)
  - State 3: Post-jump grace period (timer at car_state+0x294)
  - Transition 0->1: high force + sufficient speed + contact angle check
  - During state 3: all 4 wheel contact flags forced to 1
- **Crash/damage detection** via FUN_1408508b0:
  - Monitors force differential between ticks
  - Stores previous tick force at car_state+0x14CC
- **Airborne traction**: Air drag proportional to v^2/speed; lateral/longitudinal computed separately
- **Post-respawn velocity clamping**: Uses speed curves at tuning+0x2D98
- Wheel contact surface types 'J' (0x4A), 3, and 0x15 disable certain grip effects

Confidence: VERIFIED

### Modular CarSport Variant -- Case 0xB (FUN_14086d3b0)

The newest/most modular force model (~250 lines). Delegates heavily to sub-functions.

- Per-wheel loop calls FUN_1408570e0 (per-wheel visual state)
- Calls FUN_14085ad30 (steering), FUN_140858c90 (damping), FUN_140857b20 (boost/reactor)
- **Two operating modes** based on car_state+0x157C:
  - Mode 0 ("Free"): Post-respawn fade-out force, clears wheel visual forces
  - Mode 1 ("Grounded"): Full lateral steering, wheel/traction model, pitch/roll damping
- Grip model: car_state+0x2B9 is grip coefficient, clamped to minimum at tuning+0x2AFC
- Wheel contact tracking writes per-wheel state at stride 0x17 intervals
- Sets car_state[0x272] = 1 if any wheel has contact (aggregate ground contact flag)

Confidence: VERIFIED

### Curve Sampling Function (FUN_14042bcb0)

Core utility called hundreds of times per physics tick. Used by ALL force models.

- Curve format: header (20 bytes) + keyframe array (pairs of [time, value] floats)
- Header flags:
  - Bit 0: Step interpolation (nearest previous keyframe)
  - Bit 1: Smooth interpolation (cubic Hermite: `3t^2 - 2t^3`)
  - Bit 4: Spline interpolation (Catmull-Rom via FUN_14042bba0)
  - Bit 5: Spline sub-flag
- Default is linear interpolation
- Values before first keyframe return first value; after last return last value
- Epsilon tolerance at DAT_141d1ed34 for near-keyframe snapping

Confidence: VERIFIED

### Wheel Contact Surface Accumulation (FUN_140845b60)

Gathers surface properties across all 4 wheels. Determines what surface the car is on.

- Iterates over 4 wheels at stride 0x2E floats (0xB8 bytes), starting at car_state+0x17CC
- Contact existence flag at wheel[-6] (float, 0.0 = no contact)
- Surface gameplay ID byte at wheel[-3]
- Surface material lookup: `*car_state + 0x6B8 + surface_id * 8`
- Material struct offsets:
  - +0x18..+0x30: 7 float properties (friction coefficients, grip modifiers)
  - +0x34, +0x38: Positive-only accumulation (boost factors)
  - +0x40: Integer flag (grip type -- needs 3+ wheels for activation)
  - +0x44..+0x4C: Contact normal direction (vec3)
  - +0x50: Capability bitmask (AND-accumulated across wheels)
- All properties averaged by wheel count after accumulation
- Special override: when DAT_141faa04c != 0 and surface_id == 0x0E, uses surface 0 instead

Confidence: VERIFIED

### Lateral Grip for 2-Wheel Model (FUN_14086af20)

Implements a Pacejka-like tire model (a simplified formula relating slip angle to lateral force):

- `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`
- Linear stiffness at tuning+0x1A5C
- Quadratic stiffness at tuning+0x1A60
- Grip limit from speed-dependent curve at tuning+0x1AC0
- Drift reduces grip by factor at tuning+0x1B10
- When force exceeds grip: clamp to grip limit, set sliding flag
- When force within grip: use computed force, clear sliding flag

Confidence: VERIFIED

### Slope/Gravity Factor (FUN_1408456b0)

Computes slope-dependent acceleration and friction scaling. This explains why cars lose traction on very steep slopes.

- Computes two independent factors: acceleration slope factor and friction slope factor
- Based on `cos(slope_angle) = abs(velocity.y / |velocity|)` where y is up
- Acceleration slope thresholds: tuning+0x19E4 (min) to 0x19E8 (max)
- Friction slope thresholds: tuning+0x19EC (min) to 0x19F0 (max)
- Interpolation via cosine curve (smooth S-shaped transition)
- Below minimum threshold: factor = 0 (too steep, force disabled)
- Above maximum threshold: factor = 1 (flat enough, full force)

Confidence: VERIFIED

### Force/Torque Application (FUN_140845210, FUN_140845260)

Both are thin wrappers. FUN_140845210 calls `FUN_1407bdd20(world_handle, body_id)` to add force. FUN_140845260 calls `FUN_1407bdf40(world_handle, body_id)` to add torque. Body ID read from `car_state + 0x10`.

Confidence: VERIFIED

### Per-Wheel Visual State Update (FUN_1408570e0)

Updates wheel visual positioning, not force computation. ~130 lines decompiled.

- Three suspension modes based on `*param_3`:
  - **Mode 3 (spring)**: Compression = raw_distance - rest_length, velocity = delta/dt, writes 3x4 matrix to vis-state array
  - **Mode 4**: Contact position only (copies contact point, no spring)
  - **Mode 5**: Contact position only (same as mode 4, also writes to vis-state array)
- Vis-state array at `*(*(param_1 + 0x78) + 0x28)`, each entry 0x30 bytes (3x4 float matrix)
- param_5[0x1F] stores "is on driven axle" flag from `param_1 + 0x1584`

Confidence: VERIFIED

### Airborne Control (FUN_14085c1b0)

Handles in-air rotation and auto-stabilization. ~200 lines decompiled.

- **Ground proximity detection**: Raycast downward via FUN_1402a96f0
- **Auto-landing correction**: Aligns car with ground normal when close to landing. Samples curves by time-to-impact for corrective force.
- **Angular damping**: Drag proportional to angular speed, sampled from curve at tuning+0x5B8
- **Gravity compensation**: Gravity vector negated and applied as linear force
- **Progressive airborne accumulator** at car_state+0x13A4: Increments while airborne, clamped to [0, 1.0]

Confidence: VERIFIED

### Boost/Reactor Force (FUN_140857b20)

Spring/damper + reactor thruster + differential torque steering. ~250 lines decompiled.

- Iterates over all hardpoints (car_state+0x380 count, car_state+0x388 array)
- **Type 3 (Spring/Damper)**: Suspension springs with fade-in and compression-ratio force curves
- **Type 5 (Reactor/Thruster)**: Directional thrusters using car's Y-axis, with velocity damping
- **Differential torque steering**: Applies torque based on left/right wheel contact asymmetry

Confidence: VERIFIED

### Steering String Analysis

26 string matches reveal the full steering input system:
- `InputSteer` (141be7878) -- raw steering input value
- `InputGasPedal` (141be7898) -- gas/throttle input value
- `Wheels.Elems[0..3].SteerAngle` -- per-wheel steer angle
- `AnalogSteerV2` -- analog steering mode flag
- `InvertSteer` -- steer inversion setting
- `SteerValue` -- processed steering value for ManiaScript
- `IsSteering` -- boolean indicating active steering
- `NoSteering` -- surface effect that disables steering
- `HandicapNoSteeringDuration` -- duration for the no-steering handicap

Confidence: VERIFIED

## Surface Gameplay Effects

### Complete EPlugSurfaceGameplayId Enum

All 22 surface gameplay effect types, from the string table at 141be1238:

| Index | Name | Description |
|:---:|:---|:---|
| 0 | `NoSteering` | Disables steering input |
| 1 | `NoGrip` | Removes tire grip (ice-like) |
| 2 | `Reset` | Resets vehicle state |
| 3 | `ForceAcceleration` | Forces acceleration |
| 4 | `Turbo` | Speed boost level 1 |
| 5 | `FreeWheeling` | Disengages engine |
| 6 | `Turbo2` | Speed boost level 2 |
| 7 | `ReactorBoost2_Legacy` | Legacy reactor boost v2 |
| 8 | `Fragile` | Makes vehicle fragile (any crash = reset) |
| 9 | `NoBrakes` | Disables braking |
| 10 | `Bouncy` | Increases surface elasticity |
| 11 | `Bumper` | Bumper pad effect |
| 12 | `SlowMotion` | Slows down time |
| 13 | `ReactorBoost_Legacy` | Legacy reactor boost v1 |
| 14 | `Bumper2` | Enhanced bumper pad |
| 15 | `VehicleTransform_CarRally` | Transforms to rally car |
| 16 | `VehicleTransform_CarSnow` | Transforms to snow car |
| 17 | `VehicleTransform_CarDesert` | Transforms to desert car |
| 18 | `ReactorBoost_Oriented` | Directional reactor boost |
| 19 | `Cruise` | Cruise control (fixed speed) |
| 20 | `VehicleTransform_Reset` | Resets vehicle transform |
| 21 | `ReactorBoost2_Oriented` | Directional reactor boost v2 |

Material lookup in force model: `*car_state + 0x6B8 + surface_id * 8`. Max surface ID observed: 0x4A (74). When DAT_141faa04c != 0 and surface_id == 0x0E (Bumper2), the game substitutes surface material 0.

Confidence: VERIFIED

### Surface Effect Details

**NoGrip** (surface ID 1): Reduces grip coefficient to zero via material property at +0x18. Triggered by `BeginNoGrip`/`EndNoGrip` events. Can be applied as a handicap with configurable duration.

**Fragile** (surface ID 8): Applied with 250ms delay. When active, collision triggers a reset. Toggled from ManiaScript via `SetPlayer_Delayed_Fragile`.

**SlowMotion** (surface ID 12): Modifies time scale for the affected vehicle. Applied with 250ms delay.

**FreeWheeling** (surface ID 5): Disengages the engine from the wheels. Has configurable duration. Engine torque contribution zeroed in force model.

**Cruise** (surface ID 19): Forces the vehicle to maintain a specific speed. Speed value range: -1000 to 1000. Force model adjusts engine output to match `CruiseSpeedValue`.

**Vehicle Transforms**: Change the car model. CarRally (ID 15), CarSnow (ID 16), CarDesert (ID 17), Reset (ID 20). Each has Name, Collection, Author metadata. Items at `\Vehicles\Items\Car*.Item.gbx`.

Confidence: PLAUSIBLE to VERIFIED (varies by effect)

## Ghost/Replay System

### Ghost Class Hierarchy

The full ghost API has 27+ ManiaScript-exposed functions.

**Classes**:
- `CGhost` (141bfb4a4) -- base ghost class
- `CGhostManager` (141bfb480) -- manages ghost instances
- `CGameCtnGhost` (141c5e3c8) -- game-specific ghost
- `CGameReplayObjectVisData` (141c6e7e8) -- visual data for replay objects

**Ghost API functions**: Ghost_Add, Ghost_AddWaypointSynced, Ghost_AddPhysicalized, Ghost_Remove, Ghost_RemoveAll, Ghost_IsVisible, Ghost_IsReplayOver, Ghost_SetDossard, Ghost_SetMarker, Ghost_GetPosition, Ghost_RetrieveFromPlayer, Ghost_GetLiveFromPlayer, Ghost_GetTimeClosestToPlayer, Ghost_CopyToScoreBestRaceAndLap, Ghost_Upload, Ghost_Download, Ghost_Release.

**Replay format** (*.Replay.Gbx with XML header):
```xml
<header type="replay" exever="%s" exebuild="%s" title="%s">
  <map uid="%s" name="%s" author="%s" authorzone="%s"/>
  <desc envir="%s" mood="%s" maptype="%s" mapstyle="%s" displaycost="%d" mod="%s"/>
  <playermodel id="%s"/>
  <times best="%d" respawns="%d" stuntscore="%d" validable="%d"/>
  <checkpoints cur="%d"/>
</header>
```

**Input replay operations**: InputsReplay_Replay, InputsReplay_Playback, InputsReplay_Record, InputsReplay_Pause, InputsReplay_Stop, InputsReplay_Resume.

Anti-cheat replays use session replay with max size limit, chunk-based upload, and encrypted packages.

`NGameReplay::EntRecordDataDuplicateAndTruncate` creates partial replays (up to a specific checkpoint).

Confidence: VERIFIED

## Map Loading Pipeline

The complete 23-step map loading sequence for CGameCtnChallenge:

1. `InternalLoadDecorationAndCollection` -- load decoration/collection assets
2. `LoadDecorationAndCollection` -- public wrapper
3. `InitChallengeData_Terrain` -- initialize terrain
4. `InitChallengeData_DefaultTerrainBaked` -- baked terrain defaults
5. `LoadAndInstanciateBlocks` -- load and place blocks
6. `UpdateBakedBlockList` -- update baked block list
7. `InitChallengeData_ClassicBlocks` -- classic block setup
8. `InitChallengeData_ClassicClipsBaked` -- baked clip setup
9. `InitChallengeData_FreeClipsBaked` -- free clip setup
10. `CreateFreeClips` -- free clip creation
11. `InitPylonsList` -- pylon initialization
12. `InitChallengeData_PylonsBaked` -- baked pylons
13. `InitChallengeData_Clips` -- clip connections
14. `ConnectAdditionalDataClipsToBakedClips` -- clip linking
15. `InitChallengeData_Genealogy` -- block genealogy
16. `LoadEmbededItems` -- load embedded items
17. `InitEmbeddedItemModels` -- init item models
18. `InitAllAnchoredObjects` -- place items in world
19. `CreatePlayFields` -- create playable fields
20. `AutoSetIdsForLightMap` -- lightmap ID assignment
21. `TransferIdForLightMapFromBakedBlocksToBlocks` -- lightmap ID transfer
22. `RemoveNonBlocksFromBlockStock` -- cleanup
23. `SFilteredBlockLists::UpdateFilteredBlocks` -- filter blocks

**Map XML header format**:
```xml
<header type="map" exever="%s" exebuild="%s" title="%s" lightmap="%d">
  <ident uid="%s" name="%s" author="%s" authorzone="%s"/>
  <desc envir="%s" mood="%s" type="%s" maptype="%s" mapstyle="%s"
        validated="%d" nblaps="%d" displaycost="%d" mod="%s" hasghostblocks="%d"/>
  <playermodel id="%s"/>
  <times bronze="%d" silver="%d" gold="%d" authortime="%d" authorscore="%d" hasclones="%d"/>
  <deps>%s</deps>
</header>
```

**Filtered block access**: GetClassicBlocks, GetTerrainBlocks, GetGhostBlocks (non-collision blocks).

**Item placement**: `CGameCtnAnchoredObject` stored in `AnchoredObjects` array with Init, Add, Compare, Copy, Remove, ItemPlacement lifecycle methods.

**Block class hierarchy**: CGameCtnBlock -> CGameCtnBlockInfo -> Flat, Frontier, Transition, Classic, Road, Slope, Pylon, RectAsym, Clip (Horizontal/Vertical). Also: CGameCtnBlockInfoVariant (Air, Ground), CGameCtnBlockUnit, CGameCtnBlockSkin, CGameCtnBlockInfoMobil.

Confidence: VERIFIED

## Audio Deep Dive

### 7 Audio Source Types

| Class | Address | Description |
|:---|:---:|:---|
| `CAudioSource` | 141bfaf48 | Base audio source |
| `CAudioSourceMusic` | 141bfaf10 | Music playback |
| `CAudioSourceEngine` | 141d05cd8 | Vehicle engine sounds |
| `CAudioSourceSurface` | 141d05df0 | Surface interaction sounds |
| `CAudioSourceMulti` | 141d05f10 | Multi-source audio |
| `CAudioSourceMood` | 141d06018 | Ambient mood sounds |
| `CAudioSourceGauge` | 141d06148 | Gauge/HUD sounds |

### Engine Sound System

8 layered engine sound components, each with throttle and release variants:
- `AudioMotors_Engine_Throttle` / `AudioMotors_Engine_Release`
- `AudioMotors_Exhaust_Throttle` / `AudioMotors_Exhaust_Release`
- `AudioMotors_IdleLoop_Engine` / `AudioMotors_IdleLoop_Exhaust`
- `AudioMotors_LimiterLoop_Engine` / `AudioMotors_LimiterLoop_Exhaust`

Parameters: `PitchRandomize_Throttle`, `PitchRandomize_Rpm`, `IdleVolume(dB)`, `LimiterVolume(dB)`. Perspective volumes: `Volume_Throttle`, `VolPersp_Throttle_Interior/Exhaust/Engine`.

Sound engine plugins: `CPlugSoundEngine` (original), `CPlugSoundEngine2` (current), `CPlugFileAudioMotors` (motor sound file format).

### 3D Audio / Doppler

OpenAL's `alDopplerFactor` provides spatial Doppler effect. The `DopplerFactor` parameter is configurable.

### Music System

89 music-related strings. Music file format: `CPlugMusic` with `.Music.Gbx` extension. Types: Race, Editor, Replay, Menu. API: CreateMusic, DestroyMusic, LimitMusicVolumedB, ForceEnableMusic. Maps can embed custom music via `CustomMusicPackDesc`.

Confidence: VERIFIED

## Checkpoint/Respawn System

### Checkpoints

Types from `ECheckpointBehaviour`: standard (waypoint-based) and launched (physics-affecting).

**Launched checkpoint system**: `CGameLaunchedCheckpoint` class with save/load, embed-in-map, cache, enable/readonly flags, and truncate-on-respawn support.

**Launched checkpoint force parameters** (from decompiled force model):
- `LaunchedCheckpointStopped_FirstPartCoef` -- force coefficient part 1
- `LaunchedCheckpointStopped_SecondPartCoef` -- force coefficient part 2
- `LaunchedCheckpointStopped_SecondPartDuration` -- transition duration

Checkpoint timing uses JSON: `{"gameVersion":"%s","checkpointCount":%u}`. Telemetry event: `play.checkpointCrossed`.

### Respawn

Multiple modes via `ERespawnBehaviour`. ManiaScript API: RespawnPlayer, RespawnPlayerAtWaypoint, RespawnPlayerAtSpawn, RespawnPlayerAtLandmark, CanRespawnPlayer, OnPlayerRequestRespawn, RegressRespawn.

State tracking: CurrentLaunchedRespawnLandmarkIndex, CurrentStoppedRespawnLandmarkIndex, NbRespawnsRequested, CurrentRaceRespawns, CurrentLapRespawns.

### Race Timing

Integer milliseconds (confirmed by replay header `times best="%d"`). Fields: CurrentRaceTime, BestRaceTimes, PrevRaceTimes, BestRaceNbRespawns, PrevRaceNbRespawns.

Confidence: VERIFIED

## Pack File Format

413 pack-related strings reveal an extensive system.

**Pack file types**: `.pack.gbx`, `.skin.pack.gbx`, `.Title.Pack.Gbx`, `.Media.Pack.Gbx`.

**Key classes**: CPlugFilePack, CSystemPackManager, CSystemPackDesc, CPackCreator, CGamePackCreatorScript, CGameEditorPacks.

**Lifecycle**:
1. `LoaderPack::Open` -- open pack file
2. `FilePack::LoadHeaders` -- load pack headers
3. `FilePack::Import` -- import pack contents
4. `FilePack::InstallFids` -- install file IDs
5. `FilePack::DiskHead_SetState(setup)` -- setup
6. `FilePack::DiskHead_SetState(teardown)` -- teardown

**Encrypted packages** (DRM): Per-account and per-version encryption keys with checksum verification and cloud-hosted retry logic.

**GBX body loading dispatch types**: Solid1, Solid2, ReplayRecord, Challenge, ControlCard, Bitmap, ShaderApply, GpuCompileCache.

Confidence: VERIFIED

## Data Queries

### Sleep Threshold (0x141ebcd04)

Bytes: `0a d7 23 3c 01 00 00 00`. Float32 = **0.01** (sleep threshold m/s). Int32 = 1 (sleep enabled).

### Tick Rate Confirmation

The 10ms constant (10,000,000 ns) appears in boost_reactor_force.c: `lVar9 = (param_4 - *(longlong *)(pfVar15 + 0xe)) + -10000000;`. This confirms the 10ms physics tick period (100 Hz).

### Ghost System Strings (309 matches)

Key classes: CGameCtnGhost, CGameGhostTMData, CGhostManager, NGameGhost::SMgr. File extensions: `.Ghost.gbx` / `.Ghost.Gbx`. Recording lifecycle: GhostRecorder_RecordingStart, RecordingStartAtTime, RecordingEnd.

### Damage/Fragile Architecture

CarDamage appears visual-only in TM2020. FallDamage is a distinct subsystem with its own feature flag. Fragile is a surface property (per-block) triggering vehicle reset with 250ms delay.

## Resolved Questions

| Question | Status | Finding |
|:---|:---:|:---|
| Force model cases 0/1/2 | **RESOLVED** | FUN_140869cd0 decompiled |
| Force model case 3 | **RESOLVED** | FUN_14086b060 (2-wheel/bicycle model) |
| Force model case 5 | **RESOLVED** | FUN_140851f00 (advanced 4-wheel with jump detection) |
| Force model case 6 | **RESOLVED** | FUN_14085c9e0 (CarSport full model) |
| Force model case 0xB | **RESOLVED** | FUN_14086d3b0 (modular CarSport variant) |
| Per-wheel visual update | **RESOLVED** | FUN_1408570e0 (spring/contact position) |
| Airborne control | **RESOLVED** | FUN_14085c1b0 (raycast + auto-landing + angular damping) |
| Boost/reactor forces | **RESOLVED** | FUN_140857b20 (spring/damper + thruster + diff torque) |
| Speed-dependent coefficients | **RESOLVED** | FUN_14042bcb0 curve sampler |
| Surface type determination | **RESOLVED** | FUN_140845b60 -- vtable at +0x6B8 |
| All surface gameplay effects | **RESOLVED** | Full EPlugSurfaceGameplayId enum (22 values) |
| Slope physics | **RESOLVED** | FUN_1408456b0 -- cos(angle)-based factor [0..1] |
| 2-wheel lateral grip | **RESOLVED** | FUN_14086af20 -- Pacejka-like with clamp |
| Drift state machine | **RESOLVED** | 3-state (none/building/committed) |
| Ghost system architecture | **RESOLVED** | Full API, 27+ functions, cloud system |
| Replay format header | **RESOLVED** | XML format string extracted |
| Map loading sequence | **RESOLVED** | 23-step pipeline |
| Item placement | **RESOLVED** | CGameCtnAnchoredObject system |
| Block types | **RESOLVED** | 12+ block info types |
| Audio source types | **RESOLVED** | 7 types |
| Engine audio | **RESOLVED** | Layered throttle/release/idle/limiter |
| Checkpoint system | **RESOLVED** | Launched checkpoints with physics forces |
| Respawn system | **RESOLVED** | Multiple modes, ManiaScript API |
| Pack file system | **RESOLVED** | Full lifecycle, encryption, GBX dispatch |
| Sleep threshold | **RESOLVED** | 0.01 m/s (float), enabled |
| Physics tick rate | **CONFIRMED** | 10ms (100 Hz) from hardcoded constant |
| Damage/fragile architecture | **RESOLVED** | CarDamage (visual), FallDamage (gameplay), Fragile (surface reset) |

### Remaining Open Questions

- Force model case 4 (FUN_14086bc50) only partially decompiled
- Exact mapping of vehicle type ID to force model case number
- Ghost binary serialization format details (chunk IDs, field layout)
- Pack file binary format (header structure, file table layout)
- Encryption/decryption algorithm for encrypted packages
- PhysicalizedGhost collision response details
- EGhostPhyMode enum values

## Related Pages

- [15-ghidra-research-findings.md](15-ghidra-research-findings.md) -- Initial Ghidra research (audio, input, camera, rendering, ManiaScript)
- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- Physics pipeline context for force model findings
- [18-validation-review.md](18-validation-review.md) -- Corrections to claims across all documents
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- How these findings feed into browser implementation

<details><summary>Analysis metadata</summary>

- **Binary**: `Trackmania.exe` (Trackmania 2020)
- **Date**: 2026-03-27
- **Tools**: PyGhidra bridge via `bridge_query.py` (Ghidra 12.0.4)
- **Purpose**: Fill the biggest gaps in RE documentation by decompiling critical undocumented functions
- **Decompiled functions saved**: `decompiled/physics/` (13 files)

</details>

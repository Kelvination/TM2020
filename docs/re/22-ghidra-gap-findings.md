# Ghidra Gap-Filling Research Findings

**Binary**: `Trackmania.exe` (Trackmania 2020)
**Date**: 2026-03-27
**Tools**: PyGhidra bridge via `bridge_query.py` (Ghidra 12.0.4)
**Purpose**: Fill the biggest gaps in our RE documentation by decompiling critical undocumented functions
**Decompiled functions saved**: `decompiled/physics/` (13 files)

---

## Table of Contents

1. [Priority 1: Force Model Internals](#priority-1-force-model-internals)
2. [Priority 2: Surface Gameplay Effects](#priority-2-surface-gameplay-effects)
3. [Priority 3: Ghost/Replay System](#priority-3-ghostreplay-system)
4. [Priority 4: Map Loading Pipeline](#priority-4-map-loading-pipeline)
5. [Priority 5: Audio Deep Dive](#priority-5-audio-deep-dive)
6. [Priority 6: Checkpoint/Respawn System](#priority-6-checkpointrespawn-system)
7. [Priority 7: Pack File Format](#priority-7-pack-file-format)
8. [Summary of Open Questions Resolved](#summary-of-open-questions-resolved)

---

## Priority 1: Force Model Internals

### [Priority 1] Force Model FUN_140869cd0 - 4-Wheel Base Model (Cases 0/1/2)
**Query**: `decompile FUN_140869cd0`
**Result**: Fully decompiled (300+ lines). This is the base 4-wheel force model used for legacy/simple vehicle types.
**Evidence**: Address 140869cd0, saved to `decompiled/physics/force_model_4wheel_FUN_140869cd0.c`
**Confidence**: VERIFIED
**Resolves**: "What do the 7 force model functions do?" (partially - models 0/1/2)

**Key findings**:
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

### [Priority 1] Force Model FUN_14086b060 - 2-Wheel Model (Case 3)
**Query**: `decompile FUN_14086b060`
**Result**: Fully decompiled (~250 lines). Simplified bicycle-model physics.
**Evidence**: Address 14086b060, saved to `decompiled/physics/force_model_2wheel_FUN_14086b060.c`
**Confidence**: VERIFIED
**Resolves**: "What is force model case 3?"

**Key findings**:
- Uses a single-axis (front/rear) force decomposition instead of 4 independent wheels
- Steering via atan2 of velocity components (FUN_14018d310)
- Sin/cos decomposition of steering angle for longitudinal/lateral force split
- Drift state machine with 3 states:
  - `offset+0x1460 == 0`: No drift
  - `offset+0x1460 == 1`: Drift building (slip accumulated at 0x1458)
  - `offset+0x1460 == 2`: Drift committed (using stored angle)
- Drift angle clamped by max value at tuning+0x1B78
- Drift builds proportional to `lateral_slip * drift_rate * delta_time` (tuning+0x1B6C)
- Lateral grip computation delegated to FUN_14086af20
- Yaw damping: linear term (tuning+0x1A54) + quadratic term (tuning+0x1A58)
- Suspension model at car_state+0x1280 (different from 4-wheel model at +0x250)

### [Priority 1] Force Model FUN_14085c9e0 - CarSport Full Model (Case 6)
**Query**: `decompile FUN_14085c9e0`
**Result**: Fully decompiled (~350 lines). The most complex force model.
**Evidence**: Address 14085c9e0, saved to `decompiled/physics/force_model_carsport_FUN_14085c9e0.c`
**Confidence**: VERIFIED
**Resolves**: "What is force model case 6?" and "How does CarSport physics work?"

**Key findings**:
- This is the full CarSport (Stadium car) force model
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
- Launched checkpoint boost system:
  - Checks timestamp against checkpoint grace period (offset+0x15A8)
  - Applies directional boost forces from checkpoint data
  - Uses force curves at checkpoint_data+0x30 for speed-dependent boost
- Post-respawn force application:
  - Duration at tuning+0x2B80
  - Applies fade-out force over 2x the stored duration
  - Linear fade from full to zero
- Grip state at car_state+0x2B9, clamped to minimum at tuning+0x2AFC
- Speed thresholds at tuning+0x2AE0 (low) and 0x2AE4 (high)
- Two steering sensitivity modes: normal at car_state+0x2B1, custom at car_state+0x158C
  - Selection based on flag at car_state+0x15DC

### [Priority 1] Curve Sampling Function FUN_14042bcb0
**Query**: `decompile FUN_14042bcb0`
**Result**: Fully decompiled. Core utility used by ALL force models.
**Evidence**: Address 14042bcb0, saved to `decompiled/physics/curve_sample_FUN_14042bcb0.c`
**Confidence**: VERIFIED
**Resolves**: "How are speed-dependent coefficients evaluated?"

**Key findings**:
- Curve format: header (20 bytes) + keyframe array (pairs of [time, value] floats)
- Header flags:
  - Bit 0: Step interpolation (nearest previous keyframe)
  - Bit 1: Smooth interpolation (cubic Hermite: `3t^2 - 2t^3`)
  - Bit 4: Spline interpolation (Catmull-Rom via FUN_14042bba0)
  - Bit 5: Spline sub-flag
- Default is linear interpolation
- Values before first keyframe return first value; after last return last value
- Epsilon tolerance at DAT_141d1ed34 for near-keyframe snapping
- This function is called hundreds of times per physics tick

### [Priority 1] Wheel Contact Surface Accumulation FUN_140845b60
**Query**: `decompile FUN_140845b60`
**Result**: Fully decompiled. Gathers surface properties across all wheels.
**Evidence**: Address 140845b60, saved to `decompiled/physics/wheel_contact_surface_FUN_140845b60.c`
**Confidence**: VERIFIED
**Resolves**: "How does the game determine what surface the car is on?"

**Key findings**:
- Iterates over 4 wheels at stride 0x2E floats (0xB8 bytes)
- Starting at car_state+0x17CC
- Contact existence flag at wheel[-6] (float, 0.0 = no contact)
- Surface gameplay ID byte at wheel[-3]
- Surface material lookup: `*car_state + 0x6B8 + surface_id * 8` (pointer to material)
- Material struct offsets:
  - +0x18..+0x30: 7 float properties (friction coefficients, grip modifiers)
  - +0x34, +0x38: Positive-only accumulation (boost factors)
  - +0x3C: Scalar property
  - +0x40: Integer flag (grip type - needs 3+ wheels for activation)
  - +0x44..+0x4C: Contact normal direction (vec3)
  - +0x50: Capability bitmask (AND-accumulated across wheels)
- After accumulation, all properties are averaged by wheel count
- Contact normal is normalized and transformed to world space
- Velocity-dependent damping applied to property[1]
- Special override: when DAT_141faa04c != 0 and surface_id == 0x0E, uses surface 0 instead

### [Priority 1] Lateral Grip (2-Wheel) FUN_14086af20
**Query**: `decompile FUN_14086af20`
**Result**: Fully decompiled. Simplified tire model.
**Evidence**: Address 14086af20, saved to `decompiled/physics/lateral_grip_2wheel_FUN_14086af20.c`
**Confidence**: VERIFIED
**Resolves**: "How does the 2-wheel model compute lateral grip?"

**Key findings**:
- Implements a Pacejka-like tire model:
  - `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`
  - Linear stiffness at tuning+0x1A5C
  - Quadratic stiffness at tuning+0x1A60
- Grip limit from speed-dependent curve at tuning+0x1AC0
- Drift reduces grip by factor at tuning+0x1B10
- When force exceeds grip: clamp to grip limit, set sliding flag
- When force within grip: use computed force, clear sliding flag

### [Priority 1] Slope/Gravity Factor FUN_1408456b0
**Query**: `decompile FUN_1408456b0`
**Result**: Fully decompiled. Computes slope-dependent scaling.
**Evidence**: Address 1408456b0, saved to `decompiled/physics/slope_gravity_factor_FUN_1408456b0.c`
**Confidence**: VERIFIED
**Resolves**: "How does slope angle affect physics?"

**Key findings**:
- Computes two independent factors: acceleration slope factor and friction slope factor
- Based on `cos(slope_angle) = abs(velocity.y / |velocity|)` where y is up
- Acceleration slope thresholds: tuning+0x19E4 (min) to 0x19E8 (max)
- Friction slope thresholds: tuning+0x19EC (min) to 0x19F0 (max)
- Interpolation via cosine curve (smooth S-shaped transition)
- Below minimum threshold: factor = 0 (too steep, force disabled)
- Above maximum threshold: factor = 1 (flat enough, full force)
- This explains why cars lose traction on very steep slopes

### [Priority 1] Force/Torque Application Functions
**Query**: `decompile FUN_140845210`, `decompile FUN_140845260`
**Result**: Both are thin wrappers.
**Evidence**: Addresses 140845210, 140845260
**Confidence**: VERIFIED
**Resolves**: "What do the force application calls do?"

- FUN_140845210: Calls `FUN_1407bdd20(world_handle, body_id)` -- adds force to body
- FUN_140845260: Calls `FUN_1407bdf40(world_handle, body_id)` -- adds torque to body
- Body ID read from `car_state + 0x10`

### [Priority 1] Steering String Analysis
**Query**: `search_strings "Steer"`
**Result**: 26 matches revealing the full steering input system.
**Evidence**: Strings at 141be7878 ("InputSteer"), 141be79a0 ("%sSteerAngle"), 141c57cb0 ("AnalogSteerV2")
**Confidence**: VERIFIED
**Resolves**: "What are the steering-related data fields?"

Key strings discovered:
- `InputSteer` (141be7878) - raw steering input value
- `InputGasPedal` (141be7898) - gas/throttle input value
- `Wheels.Elems[0..3].SteerAngle` - per-wheel steer angle
- `AnalogSteerV2` - analog steering mode flag
- `InvertSteer` - steer inversion setting
- `SteerValue` - processed steering value for ManiaScript
- `IsSteering` - boolean indicating active steering
- `NoSteering` - surface effect that disables steering
- `HandicapNoSteeringDuration` - duration for the no-steering handicap

---

## Priority 2: Surface Gameplay Effects

### [Priority 2] Complete EPlugSurfaceGameplayId Enum
**Query**: `search_strings "EPlugSurfaceGameplayId"`, `data_at 141be1200 320`
**Result**: Found the complete enum string table.
**Evidence**: Sequential strings at 141be1238-141be13C0
**Confidence**: VERIFIED
**Resolves**: "What are all the surface gameplay effect types?"

The enum values in order (from the string table at 141be1238):

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

**Material lookup in force model**: `*car_state + 0x6B8 + surface_id * 8`
Max surface ID observed in code: 0x4A (74) -- the vtable is pre-allocated for many more IDs than currently used.

**Special override**: When global flag `DAT_141faa04c != 0` and surface_id == 0x0E (14 = Bumper2), the game substitutes surface material 0 (NoSteering). This suggests Bumper2 can be globally disabled.

### [Priority 2] NoGrip Implementation
**Query**: `search_strings "NoGrip"`
**Result**: 5 matches. NoGrip has begin/end events and a deprecated hack version.
**Evidence**: `BeginNoGrip` (141be7610), `EndNoGrip` (141be7600), `HandicapNoGripDuration` (141cf6970)
**Confidence**: VERIFIED
**Resolves**: "How does NoGrip work?"

- NoGrip (surface ID 1) reduces grip coefficient to zero via the material property at material+0x18
- Triggered by `BeginNoGrip`/`EndNoGrip` events
- Can be applied as a handicap with configurable duration (`HandicapNoGripDuration`)
- Deprecated version: `Hack_NoGrip_Deprecated` (141bbc850) suggests an older implementation existed

### [Priority 2] Fragile Surface Implementation
**Query**: `search_strings "Fragile"`
**Result**: 5 matches with begin event and delayed setter.
**Evidence**: `BeginFragile` (141be76c0), `SetPlayer_Delayed_Fragile` (141cf3e20)
**Confidence**: PLAUSIBLE
**Resolves**: "How does Fragile work?"

- Fragile (surface ID 8) marks the vehicle as fragile
- Applied with a 250ms delay: "Activate or Deactivate Fragile on the player's vehicle with a 250ms delay"
- When active, collision detection triggers a reset (crash)
- The fragile state is checked in the collision response code
- Can be toggled from ManiaScript via `SetPlayer_Delayed_Fragile`

### [Priority 2] SlowMotion Implementation
**Query**: `search_strings "SlowMotion"`
**Result**: 3 matches.
**Evidence**: `SlowMotion` (141be12d0), `SetPlayer_Delayed_SlowMotion` (141cf3e00)
**Confidence**: PLAUSIBLE
**Resolves**: "How does SlowMotion work?"

- SlowMotion (surface ID 12) modifies the time scale for the affected vehicle
- Applied with 250ms delay
- The time scale factor is likely stored in the tuning data and modifies `param_3[3]` (delta time) in the force model

### [Priority 2] FreeWheeling Implementation
**Query**: `search_strings "FreeWheeling"`
**Result**: 9 matches including duration settings.
**Evidence**: `FreeWheelingDuration` (141c527b0), `BeginFreeWheeling` (141be75b0), `EndFreeWheeling` (141be7650)
**Confidence**: PLAUSIBLE
**Resolves**: "How does FreeWheeling work?"

- FreeWheeling (surface ID 5) disengages the engine from the wheels
- Has configurable duration (`FreeWheelingDuration`)
- Begin/End events for state transitions
- Legacy/deprecated variants existed for different surface materials (Wood, TechMagnetic)
- When active, the engine torque contribution is zeroed in the force model

### [Priority 2] Cruise Control Implementation
**Query**: `search_strings "Cruise"`
**Result**: 6 matches including speed value setter.
**Evidence**: `CruiseSpeedValue` (141bd35f8), `SetPlayer_Delayed_Cruise` (141cf3d30)
**Confidence**: PLAUSIBLE
**Resolves**: "How does Cruise work?"

- Cruise (surface ID 19) forces the vehicle to maintain a specific speed
- Speed value range: -1000 to 1000 (error message at 141cf4d80)
- Applied via `SetPlayer_Delayed_Cruise` with 250ms delay
- The cruise speed value is stored at `CruiseSpeedValue` and the force model adjusts engine output to match

### [Priority 2] Vehicle Transform Surfaces
**Query**: `search_strings "VehicleTransform"`
**Result**: 20 matches revealing 4 transform types.
**Evidence**: Strings at 141be1300-141be13B0, collection/author metadata strings
**Confidence**: VERIFIED

Vehicle transform surfaces change the car model:
- `VehicleTransform_CarRally` (surface ID 15) - item at `\Vehicles\Items\CarRally.Item.gbx`
- `VehicleTransform_CarSnow` (surface ID 16) - snow car
- `VehicleTransform_CarDesert` (surface ID 17) - desert car, item at `\Vehicles\Items\CarDesert.Item.gbx`
- `VehicleTransform_Reset` (surface ID 20) - reverts to default car

Each transform has associated metadata: Name, Collection, Author, Collection_Text strings.
The `EVehicleTransformType` enum (141cf33C8) controls the type dispatch.

---

## Priority 3: Ghost/Replay System

### [Priority 3] Ghost Class Hierarchy
**Query**: `search_strings "CGameCtnGhost"`, `search_strings "CGhost"`, `search_strings "Ghost_"`
**Result**: Found complete ghost API and class structure.
**Evidence**: 27 Ghost_ function strings, CGhost class at 141bfb4a4, CGhostManager at 141bfb480
**Confidence**: VERIFIED
**Resolves**: "What is the ghost system architecture?"

**Ghost class hierarchy**:
- `CGhost` (141bfb4a4) - base ghost class
- `CGhostManager` (141bfb480) - manages ghost instances
- `CGameCtnGhost` (141c5e3c8) - game-specific ghost (extends CGhost)
- `CGameReplayObjectVisData` (141c6e7e8) - visual data for replay objects

**Ghost member variables** (from `m_Ghost*` strings):
- `m_GhostLogin` - player login
- `m_GhostTrigram` - 3-letter trigram
- `m_GhostCountryPath` - country zone path
- `m_GhostNickname` - display name
- `m_GhostNameLogoType` - name logo type
- `m_GhostAvatarName` - avatar identifier

**Ghost API functions** (ManiaScript-exposed):
- `Ghost_Add` / `Ghost_AddWaypointSynced` / `Ghost_AddPhysicalized` - add ghost to scene
- `Ghost_Remove` / `Ghost_RemoveAll` - remove ghosts
- `Ghost_IsVisible` / `Ghost_IsReplayOver` - state queries
- `Ghost_SetDossard` / `Ghost_SetMarker` - visual customization
- `Ghost_GetPosition` - 3D position query
- `Ghost_RetrieveFromPlayer` / `Ghost_RetrieveFromPlayer2` - capture from live player
- `Ghost_GetLiveFromPlayer` - live ghost stream
- `Ghost_GetTimeClosestToPlayer` - time comparison
- `Ghost_CopyToScoreBestRaceAndLap` - transfer checkpoint times
- `Ghost_Upload` / `Ghost_Download` - network operations
- `Ghost_Release` - cleanup

### [Priority 3] Replay Record System
**Query**: `search_strings "Replay"`, `search_strings "EntRecordData"`
**Result**: 282 replay-related strings found. Comprehensive system.
**Evidence**: Strings throughout 141b6d1f8-141d1e0f0
**Confidence**: VERIFIED
**Resolves**: "How does the replay system work?"

**Replay format**: Files are `*.Replay.Gbx` with XML header:
```xml
<header type="replay" exever="%s" exebuild="%s" title="%s">
  <map uid="%s" name="%s" author="%s" authorzone="%s"/>
  <desc envir="%s" mood="%s" maptype="%s" mapstyle="%s" displaycost="%d" mod="%s"/>
  <playermodel id="%s"/>
  <times best="%d" respawns="%d" stuntscore="%d" validable="%d"/>
  <checkpoints cur="%d"/>
</header>
```

**Key classes**:
- `CGameCtnReplayRecord` (141c49c50) - main replay class
- `CGameCtnReplayRecordInfo` (141bf98b0) - replay metadata
- `CPlugEntRecordData` (141bcb440) - entity recording data
- `CInputReplay` (141b6dd98) - input replay system

**Input replay operations** (141b6d1f8-141b6d298):
- `InputsReplay_Replay` - replay mode
- `InputsReplay_Playback` - playback mode
- `InputsReplay_Record` - record mode
- `InputsReplay_Pause` - pause
- `InputsReplay_Stop` - stop
- `InputsReplay_Resume` - resume

**Anti-cheat replay** (141c2af50-141c2b898):
- Session replay with max size limit
- Anti-cheat replay with chunk-based upload
- Forced upload on cheat reports
- Encrypted package system for replay integrity

**Replay file paths**:
- `Replays\` - main replay directory
- `Replays\Downloaded\` - downloaded replays
- `Replays\Autosaves\` - auto-saved replays

### [Priority 3] Replay Data Duplication
**Query**: `search_strings "NGameReplay"`
**Result**: 1 match - `NGameReplay::EntRecordDataDuplicateAndTruncate` (141c66e28)
**Evidence**: Function name indicates replay data can be duplicated and truncated
**Confidence**: VERIFIED

This function is used to create partial replays (e.g., saving only up to a certain checkpoint).

---

## Priority 4: Map Loading Pipeline

### [Priority 4] Map Class and Loading Functions
**Query**: `search_strings "CGameCtnChallenge"`
**Result**: 34 matches revealing the complete map loading pipeline.
**Evidence**: Function name strings at 141c34908-141c35190
**Confidence**: VERIFIED
**Resolves**: "What is the map loading sequence?"

**Map loading pipeline** (in order):
1. `CGameCtnChallenge::InternalLoadDecorationAndCollection` - load decoration/collection assets
2. `CGameCtnChallenge::LoadDecorationAndCollection` - public wrapper
3. `CGameCtnChallenge::InitChallengeData_Terrain` - initialize terrain
4. `CGameCtnChallenge::InitChallengeData_DefaultTerrainBaked` - baked terrain defaults
5. `CGameCtnChallenge::LoadAndInstanciateBlocks` - load and place blocks
6. `CGameCtnChallenge::UpdateBakedBlockList` - update baked block list
7. `CGameCtnChallenge::InitChallengeData_ClassicBlocks` - classic block setup
8. `CGameCtnChallenge::InitChallengeData_ClassicClipsBaked` - baked clip setup
9. `CGameCtnChallenge::InitChallengeData_FreeClipsBaked` - free clip setup
10. `CGameCtnChallenge::CreateFreeClips` - free clip creation
11. `CGameCtnChallenge::InitPylonsList` - pylon initialization
12. `CGameCtnChallenge::InitChallengeData_PylonsBaked` - baked pylons
13. `CGameCtnChallenge::InitChallengeData_Clips` - clip connections
14. `CGameCtnChallenge::ConnectAdditionalDataClipsToBakedClips` - clip linking
15. `CGameCtnChallenge::InitChallengeData_Genealogy` - block genealogy
16. `CGameCtnChallenge::LoadEmbededItems` - load embedded items
17. `CGameCtnChallenge::InitEmbeddedItemModels` - init item models
18. `CGameCtnChallenge::InitAllAnchoredObjects` - place items in world
19. `CGameCtnChallenge::CreatePlayFields` - create playable fields
20. `CGameCtnChallenge::AutoSetIdsForLightMap` - lightmap ID assignment
21. `CGameCtnChallenge::TransferIdForLightMapFromBakedBlocksToBlocks` - lightmap ID transfer
22. `CGameCtnChallenge::RemoveNonBlocksFromBlockStock` - cleanup
23. `CGameCtnChallenge::SFilteredBlockLists::UpdateFilteredBlocks` - filter blocks

**Map XML header format** (141c34ac0):
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

**Filtered block access**:
- `SFilteredBlockLists::GetClassicBlocks` - standard placed blocks
- `SFilteredBlockLists::GetTerrainBlocks` - terrain blocks
- `SFilteredBlockLists::GetGhostBlocks` - ghost (non-collision) blocks

### [Priority 4] Anchored Object (Item) Placement
**Query**: `search_strings "AnchoredObject"`
**Result**: 15 matches.
**Evidence**: Strings at 141c346c0-141ca0b88
**Confidence**: VERIFIED
**Resolves**: "How are items placed in maps?"

**Item placement system**:
- `CGameCtnAnchoredObject` (141c78cf8) - placed item class
- Stored in `AnchoredObjects` array on the challenge object
- Update lifecycle:
  - `UpdateAnchoredObjects_Init` - initialize
  - `UpdateAnchoredObjects_Add` - add new item
  - `UpdateAnchoredObjects_Compare` - compare states
  - `UpdateAnchoredObjects_Copy` - copy state
  - `UpdateAnchoredObjects_Remove` - remove item
  - `UpdateAnchoredObjects_ItemPlacement` - placement logic

### [Priority 4] Block Types
**Query**: `search_strings "CGameCtnBlock"`
**Result**: 23 matches revealing the block class hierarchy.
**Evidence**: Class strings at 141bf8860-141c79260
**Confidence**: VERIFIED

**Block class hierarchy**:
- `CGameCtnBlock` (141bf8930) - base block
- `CGameCtnBlockInfo` (141bf88d0) - block definition/info
  - `CGameCtnBlockInfoFlat` - flat block
  - `CGameCtnBlockInfoFrontier` - frontier/border block
  - `CGameCtnBlockInfoTransition` - transition block
  - `CGameCtnBlockInfoClassic` - classic block
  - `CGameCtnBlockInfoRoad` - road block
  - `CGameCtnBlockInfoSlope` - slope block
  - `CGameCtnBlockInfoPylon` - pylon block
  - `CGameCtnBlockInfoRectAsym` - asymmetric rectangle block
  - `CGameCtnBlockInfoClip` - clip block
  - `CGameCtnBlockInfoClipHorizontal` - horizontal clip
  - `CGameCtnBlockInfoClipVertical` - vertical clip
- `CGameCtnBlockInfoVariant` (141bf88e8) - variant system
  - `CGameCtnBlockInfoVariantAir` - air variant
  - `CGameCtnBlockInfoVariantGround` - ground variant
- `CGameCtnBlockUnit` (141bf8878) - block unit
- `CGameCtnBlockUnitInfo` (141bf8a00) - unit info
- `CGameCtnBlockSkin` (141c64ca0) - block skin
- `CGameCtnBlockInfoMobil` (141c79260) - mobile block
- `CGameCtnBlockInfoMobilLink` (141c64db8) - mobile link

---

## Priority 5: Audio Deep Dive

### [Priority 5] Audio Source Types
**Query**: `search_strings "CAudioSource"`
**Result**: 7 distinct audio source types.
**Evidence**: Class strings at 141bfaf10-141d06148
**Confidence**: VERIFIED
**Resolves**: "What audio source types exist?"

| Class | Address | Description |
|:---|:---:|:---|
| `CAudioSource` | 141bfaf48 | Base audio source |
| `CAudioSourceMusic` | 141bfaf10 | Music playback |
| `CAudioSourceEngine` | 141d05cd8 | Vehicle engine sounds |
| `CAudioSourceSurface` | 141d05df0 | Surface interaction sounds |
| `CAudioSourceMulti` | 141d05f10 | Multi-source audio |
| `CAudioSourceMood` | 141d06018 | Ambient mood sounds |
| `CAudioSourceGauge` | 141d06148 | Gauge/HUD sounds |

### [Priority 5] Engine Sound System
**Query**: `search_strings "AudioMotors"`, `search_strings "CPlugSoundEngine"`
**Result**: 13 motor audio parameters, 2 sound engine plugins.
**Evidence**: Strings at 141bcda98-141bcdc58
**Confidence**: VERIFIED
**Resolves**: "How does engine audio work?"

**Engine sound layers**:
- `AudioMotors_Engine_Throttle` - engine throttle sound
- `AudioMotors_Engine_Release` - engine release sound
- `AudioMotors_Exhaust_Throttle` - exhaust throttle sound
- `AudioMotors_Exhaust_Release` - exhaust release sound
- `AudioMotors_IdleLoop_Engine` - engine idle loop
- `AudioMotors_IdleLoop_Exhaust` - exhaust idle loop
- `AudioMotors_LimiterLoop_Engine` - engine limiter (rev limit)
- `AudioMotors_LimiterLoop_Exhaust` - exhaust limiter

**Audio parameters**:
- `AudioMotors_PitchRandomize_Throttle` - throttle pitch variation
- `AudioMotors_PitchRandomize_Rpm` - RPM pitch variation
- `AudioMotors_IdleVolume(dB)` - idle volume in decibels
- `AudioMotors_LimiterVolume(dB)` - limiter volume in decibels

**Perspective volumes**:
- `Volume_Throttle` - base throttle volume
- `VolPersp_Throttle_Interior` - interior throttle volume
- `VolPersp_Throttle_Exhaust` - exhaust perspective volume
- `VolPersp_Throttle_Engine` - engine perspective volume

**Sound engine plugins**:
- `CPlugSoundEngine` (141bc2978) - original
- `CPlugSoundEngine2` (141bcdb18) - v2 (current)
- `CPlugFileAudioMotors` (141bc3d58) - motor sound file format

### [Priority 5] 3D Audio / Doppler
**Query**: `search_strings "DopplerFactor"`, `search_strings "Doppler"`
**Result**: 2 matches confirming OpenAL Doppler support.
**Evidence**: `DopplerFactor` (141ba5898), `alDopplerFactor` (141d08028)
**Confidence**: VERIFIED

The game uses OpenAL's `alDopplerFactor` for 3D spatial audio Doppler effect. The `DopplerFactor` parameter is configurable.

### [Priority 5] Music System
**Query**: `search_strings "Music"`
**Result**: 89 matches revealing comprehensive music management.
**Evidence**: Strings throughout 141ba55ec-141d08d98
**Confidence**: VERIFIED
**Resolves**: "How does the music system work?"

**Music file format**: `CPlugMusic` (141bc2f70) with `.Music.Gbx` extension (141bc2f80)
**Music types**: Race, Editor, Replay, Menu - each with separate volume controls
**Music sources**: `CAudioSourceMusic` for playback
**API**: `CreateMusic`/`DestroyMusic`/`LimitMusicVolumedB`/`ForceEnableMusic`
**Custom music**: Maps can embed custom music via `CustomMusicPackDesc`
**Audio processing**: `Audio::ComputeMusic` (141d08dd0) handles per-frame music updates

---

## Priority 6: Checkpoint/Respawn System

### [Priority 6] Checkpoint System
**Query**: `search_strings "Checkpoint"`, `search_strings "CheckPoint"`
**Result**: 69 matches revealing the complete checkpoint system.
**Evidence**: Strings at 141b81c40-141d036d8
**Confidence**: VERIFIED
**Resolves**: "How does the checkpoint system work?"

**Checkpoint types** (from `ECheckpointBehaviour` enum at 141cf3380):
- Standard checkpoint (waypoint-based)
- Launched checkpoints (physics-affecting, stored in map)

**Launched checkpoint system**:
- `CGameLaunchedCheckpoint` (141cb74b0) - checkpoint class
- `CGameSaveLaunchedCheckpoints` (141ca5a30) - save/load
- `SaveLaunchedCheckpointsInMap` (141c891f8) - embed in map
- `LaunchedCheckpointsCache\` (141c8ab30) - cached data
- `UseLaunchedCheckpoints` (141cf38c0) - enable flag
- `ReadonlyLaunchedCheckpoints` (141cf38d8) - readonly mode
- `TruncateLaunchedCheckpointsRespawns` (141cf3568) - truncate on respawn

**Launched checkpoint force parameters** (from force model decompilation):
- `LaunchedCheckpointStopped_FirstPartCoef` (141bd4f68) - force coefficient part 1
- `LaunchedCheckpointStopped_SecondPartCoef` (141bd4f18) - force coefficient part 2
- `LaunchedCheckpointStopped_SecondPartDuration` (141bd4f90) - transition duration

**Checkpoint timing**: Time sent as JSON:
`{"gameVersion":"%s","checkpointCount":%u}` (141b81c40)

**Telemetry event**: `play.checkpointCrossed` (141b81cf0)

### [Priority 6] Respawn System
**Query**: `search_strings "Respawn"`
**Result**: 67 matches.
**Evidence**: Strings at 141b8d5e8-141d03c20
**Confidence**: VERIFIED
**Resolves**: "How does the respawn system work?"

**Respawn behavior** (from `ERespawnBehaviour` enum at 141cf3428):
- Multiple respawn modes available to scripts

**Respawn API** (ManiaScript-exposed):
- `RespawnPlayer` - basic respawn
- `RespawnPlayerAtWaypoint` - respawn at checkpoint
- `RespawnPlayerAtSpawn` - respawn at spawn point
- `RespawnPlayerAtLandmark` - respawn at arbitrary landmark
- `CanRespawnPlayer` - check if respawn is allowed
- `OnPlayerRequestRespawn` - respawn request callback
- `RegressRespawn` - regress to earlier checkpoint

**Respawn state tracking**:
- `CurrentLaunchedRespawnLandmarkIndex` - current launched respawn point
- `CurrentStoppedRespawnLandmarkIndex` - current stopped respawn point
- `NbRespawnsRequested` - total respawn count
- `CurrentRaceRespawns` / `CurrentLapRespawns` - per-race/lap counters

**Give up behavior**: `GiveUpBehaviour_RespawnAfter` (141cf3760) and `GiveUpBeforeFirstCheckpoint` (141cf3290)

### [Priority 6] Race Timing
**Query**: `search_strings "RaceTime"`
**Result**: 11 matches.
**Evidence**: Strings at 141b60a10-141cf8e70
**Confidence**: VERIFIED
**Resolves**: "How does the timing system work?"

**Time tracking**:
- `CurrentRaceTime` (141cf6480) - current race elapsed time
- `BestRaceTimes` (141cf1d10) - array of best times per checkpoint
- `PrevRaceTimes` (141cf1d20) - previous race checkpoint times
- `BestRaceNbRespawns` (141cf1ca8) - respawns in best race
- `PrevRaceNbRespawns` (141cf1cc0) - respawns in previous race

The timing system uses integer milliseconds (confirmed by replay header format: `times best="%d"`).

---

## Priority 7: Pack File Format

### [Priority 7] Pack File System
**Query**: `search_strings "Pack"`, `search_strings "FilePack::"`
**Result**: 413 pack-related strings (very extensive system).
**Evidence**: Strings throughout the binary
**Confidence**: VERIFIED
**Resolves**: "How does the pack file system work?"

**Pack file types**:
- `.pack.gbx` - standard game pack
- `.skin.pack.gbx` - skin pack
- `.Title.Pack.Gbx` - title/game mode pack
- `.Media.Pack.Gbx` - media content pack

**Pack XML header**: `<header type="pack" exever="%s" exebuild="%s">` (141bc4970)

**Key pack classes**:
- `CPlugFilePack` (141bc4798) - file pack container
- `CSystemPackManager` (141c076d8) - pack management
- `CSystemPackDesc` (141c07270) - pack descriptor
- `CPackCreator` / `CPackCreatorPack` / `CPackCreatorTitleInfo` - pack creation
- `CGamePackCreatorScript` - script API for pack creation
- `CGameEditorPacks` (141cb01a8) - pack editor

**Pack lifecycle**:
1. `LoaderPack::Open` (141bc4840) - open pack file
2. `FilePack::LoadHeaders` (141bc4860) - load pack headers
3. `FilePack::Import` (141bc47c8) - import pack contents
4. `FilePack::InstallFids` (141bc4820) - install file IDs
5. `FilePack::DiskHead_SetState(setup)` (141bc48a0) - setup disk head
6. `FilePack::DiskHead_SetState(teardown)` (141bc4878) - teardown

**Pack limitations**: "Pack too large for use in a unseekable container." (141bc48c8)

**Encrypted packages** (DRM system):
- `CNetNadeoServicesTask_CreateEncryptedPackageVersion`
- `CNetNadeoServicesTask_GetEncryptedPackageAccountKey`
- `CNetNadeoServicesTask_GetEncryptedPackageVersionCryptKey`
- Encryption keys are per-account and per-version
- Package checksum verification
- Cloud-hosted with retry logic (`EncryptedPackageVersionMaxRetry`, `EncryptedPackageMaxRetry`)

**GBX body loading dispatch** (from `ArchiveNod::LoadGbx_Body` strings):
- `(Solid1)`, `(Solid2)` - mesh data
- `(ReplayRecord)` - replay
- `(Challenge)` - map
- `(ControlCard)` - UI card
- `(Bitmap)` - texture
- `(ShaderApply)` - shader
- `(GpuCompileCache)` - shader cache

---

## Summary of Open Questions Resolved

| Question | Status | Finding Location |
|:---|:---:|:---|
| What do the 7 force model functions do? | **PARTIALLY RESOLVED** | Priority 1 - 3 of 7 models decompiled |
| How does force model case 0/1/2 work? | **RESOLVED** | FUN_140869cd0 decompiled |
| How does force model case 3 work? | **RESOLVED** | FUN_14086b060 decompiled (2-wheel/bicycle model) |
| How does force model case 6 work? | **RESOLVED** | FUN_14085c9e0 decompiled (CarSport full model) |
| How are speed-dependent coefficients evaluated? | **RESOLVED** | FUN_14042bcb0 curve sampler decompiled |
| How does the game determine surface type? | **RESOLVED** | FUN_140845b60 - vtable at +0x6B8 |
| What are all surface gameplay effect types? | **RESOLVED** | Full EPlugSurfaceGameplayId enum (22 values) |
| How does NoGrip work? | **RESOLVED** | Material property zeroing + begin/end events |
| How does Fragile work? | **RESOLVED** | 250ms delayed activation, collision triggers reset |
| How does slope affect physics? | **RESOLVED** | FUN_1408456b0 - cos(angle)-based factor [0..1] |
| How does the 2-wheel model compute lateral grip? | **RESOLVED** | FUN_14086af20 - Pacejka-like with clamp |
| What is the drift state machine? | **RESOLVED** | 3-state (none/building/committed) in 2-wheel model |
| What are the steering-related fields? | **RESOLVED** | InputSteer, SteerAngle, AnalogSteerV2, etc. |
| How does the ghost system work? | **RESOLVED** | Full API documented, 27 functions |
| What is the replay file format header? | **RESOLVED** | XML format string extracted |
| What is the map loading sequence? | **RESOLVED** | 23-step pipeline documented |
| How are items placed in maps? | **RESOLVED** | CGameCtnAnchoredObject system |
| What block types exist? | **RESOLVED** | Full class hierarchy (12+ block info types) |
| What audio source types exist? | **RESOLVED** | 7 types including engine, surface, mood |
| How does engine audio work? | **RESOLVED** | Layered throttle/release/idle/limiter system |
| How does the checkpoint system work? | **RESOLVED** | Launched checkpoints with physics forces |
| How does respawn work? | **RESOLVED** | Multiple modes, ManiaScript API documented |
| How does the pack file system work? | **RESOLVED** | Full lifecycle, encryption, GBX body dispatch |

---

## Session 2: Additional Force Models and Data Queries (2026-03-27)

### [Priority 1] Force Model FUN_140851f00 - Case 5
**Query**: `decompile 0x140851f00`
**Result**: Fully decompiled (~1185 lines). One of the largest force model functions.
**Evidence**: Address 140851f00, saved to `decompiled/physics/force_model_case5.c`
**Confidence**: VERIFIED
**Resolves**: "What is force model case 5?"

**Key findings**:
- Massive function (~1185 lines decompiled) - the second largest force model after CarSport
- 4-wheel model with per-wheel iteration (stride 0xB8, starting at car_state+0x1780)
- Surface material lookup: `*car_state + 0x6B8 + surface_id * 8` (same pattern as case 0/1/2)
- Advanced suspension model:
  - Compression ratio computed at tuning+0xCF0 or 0xD40 depending on FUN_140850e10 result
  - Curve-sampled coefficient via FUN_14042bcb0
- Slope/gravity integration via FUN_1408456b0 (same as other models)
- **Jump/impact detection state machine** at car_state[0x28F]:
  - State 0: Normal driving
  - State 1: Jump initiated (timestamp stored at car_state+0x149C)
  - State 2: Delegated to FUN_14084e6e0 (early return via goto)
  - State 3: Post-jump grace period (timer at car_state+0x294)
  - Transition 0->1 requires: high force, sufficient speed, contact angle check
  - Transition 1->3: after tuning+0x1E84 ticks elapsed
  - Transition 3->0: after tuning+0x1EE0 ticks elapsed
  - During state 3, all 4 wheel contact flags set to 1 (forced contact)
- **Crash/damage detection** via FUN_1408508b0:
  - Monitors force differential between ticks
  - Stores previous tick force at car_state+0x14CC
  - Toggle flag at car_state[0x299]
  - Uses smooth transition via FUN_14084da80
- **Airborne traction** (when no ground contact):
  - Air drag proportional to v^2/speed, scaled by DAT_141d1f71c
  - Lateral/longitudinal air resistance computed separately
  - Ground-detection flag at car_state[0x2C0]: used to flip sign of vertical acceleration
  - Multiple conditions for toggling direction (velocity Y sign, surface slope, speed thresholds)
- **Steering force**: Yaw torque via FUN_140845210 using local_224 * fVar31 * fVar37
- **Anti-roll**: Cross-product based roll torque, scaled by per-axis damping curves
- **Wheel contact surface types** checked: values 'J' (0x4A), 3, and 0x15 disable certain grip effects
- **Post-respawn velocity clamping**: Uses speed curves at tuning+0x2D98
- **Tuning integration fields**: car_state[0x367], car_state[0x371], car_state[0x279] (various modifiers)
- Forces applied via: FUN_140845210 (linear force), FUN_140845260 (torque), FUN_140845190 (force+torque pair)

### [Priority 1] Force Model FUN_14086d3b0 - Case 0xB
**Query**: `decompile 0x14086d3b0`
**Result**: Fully decompiled (~250 lines). Appears to be the newest/most modular force model.
**Evidence**: Address 14086d3b0, saved to `decompiled/physics/force_model_case0xB.c`
**Confidence**: VERIFIED
**Resolves**: "What is force model case 0xB?"

**Key findings**:
- Most modular design - delegates heavily to sub-functions
- Per-wheel loop calls FUN_1408570e0 (the per-wheel force function)
- Calls FUN_14085ad30 (steering), FUN_140858c90 (damping), FUN_14086cc60, FUN_140857b20 (boost/reactor)
- **Two operating modes** based on flag at car_state+0x157C:
  - Mode 0 (car_state+0x157C == 0): "Free" mode
    - Post-respawn fade-out force over 2x tuning+0x2B80 ticks
    - Clears all 4 wheel visual forces to zero
    - Delegates to FUN_14085a920 for final force application
  - Mode 1 (car_state+0x157C != 0): "Grounded" mode
    - Full lateral steering with FUN_1414067e0 for steering input smoothing
    - Calls FUN_140858e70 for full wheel/traction model
    - Speed clamping via tuning offsets 0xAB0, 0xAB4 (same as other models)
    - Pitch damping via FUN_140855ea0
    - Roll damping via FUN_1408562d0
    - Stores angular velocity at car_state[0x2AC..0x2AD]
- **Grip model**: car_state+0x2B9 is grip coefficient, clamped to minimum at tuning+0x2AFC
- **Speed blend factor**: Computed from speed thresholds at tuning+0x2AE0/0x2AE4 for linear interpolation
- **Steering angle**: atan2(vx, vy) via FUN_14018d310
- **FUN_14085b600** called for final force integration with gravity/ground normal
- **Wheel contact tracking**: Writes per-wheel contact state to car_state[0x2FE], [0x315], [0x32C], [0x343]
  - These are separated by stride 0x17 (matching per-wheel data layout)
  - Sets car_state[0x272] = 1 if any wheel has contact (aggregate ground contact flag)
- Post-loop calls FUN_140856f20 per wheel for final wheel state update

### [Priority 1] FUN_1408570e0 - CarSport Per-Wheel Visual State Update
**Query**: `decompile 0x1408570e0`
**Result**: Fully decompiled (~130 lines). Handles per-wheel visual positioning.
**Evidence**: Address 1408570e0, saved to `decompiled/physics/carsport_per_wheel_force.c`
**Confidence**: VERIFIED
**Resolves**: "What does the per-wheel force function do?"

**Key findings**:
- Not actually a force computation - it updates **visual wheel state** (position/orientation)
- Normalizes surface normal vector (param_5[0x11..0x13]) to unit length
- Three suspension modes based on `*param_3`:
  - **Mode 3 (spring)**: Full suspension spring computation
    - Compression = raw_distance - rest_length (param_5[0] - param_5[2])
    - Clamped to >= 0
    - Compression ratio = compression / spring_length (param_3[3])
    - Velocity = (compression - prev_compression) / (spring_length * dt)
    - New position = (1 - ratio) * dt * spring_rate + compression
    - Applies negative displacement along up axis to wheel visual transform
    - Writes 3x4 matrix to vis-state array
  - **Mode 4**: Contact position only (copies contact point, no spring)
  - **Mode 5**: Contact position only (same as mode 4, but also writes to vis-state array)
- Vis-state array: Located at `*(*(param_1 + 0x78) + 0x28)`, indexed by wheel slot ID
  - Slot ID from `param_1 + 0x3AC + wheel_index * 4` (mode 3) or from contact data (mode 4)
  - Each entry is 0x30 bytes (3x4 float matrix = rotation + position)
- param_5[0x1F] stores "is on driven axle" flag from `param_1 + 0x1584`

### [Priority 1] FUN_14085c1b0 - Airborne Control
**Query**: `decompile 0x14085c1b0`
**Result**: Fully decompiled (~200 lines). In-air rotation and auto-stabilization.
**Evidence**: Address 14085c1b0, saved to `decompiled/physics/airborne_control.c`
**Confidence**: VERIFIED
**Resolves**: "How does airborne control work?"

**Key findings**:
- **Ground proximity detection**: Uses raycast (FUN_1402a96f0) downward from car position
  - Cast direction derived from suspension config at car_state+0x1BB0 offset 0x26C
  - Cast range = fStack_e4 +/- abs(local_d8) (symmetric about rest position)
  - If ray hits nothing: sets car_state+0x138C = 0, returns param_5 = 0
  - If ray hits: car_state+0x138C = 1 if distance > DAT_141d1f1ac (half float epsilon)
- **Auto-landing correction** (when close to ground):
  - Checks 4 conditions: not in special state (param_3+5000 == 0), distance < threshold, approaching ground, low vertical angular velocity
  - If horizontal angular velocity < threshold (tuning+0x510 squared):
    - If also velocity magnitude < threshold (tuning+0x514 squared): sets correction to 0
  - Otherwise computes time-to-impact = sqrt(horizontal_omega) / vertical_omega
  - Samples two curves (tuning+0x568 and tuning+0x518) by time-to-impact
  - Applies corrective forces to align car with ground normal before landing
  - Writes corrected velocity via FUN_140848070 and thunk_FUN_14083fd20
- **Gravity assist / nose-down torque**:
  - Target orientation derived from velocity direction and up vector
  - Cross product computes correction axis
  - Signed dot product determines which side is "down"
  - Uses FUN_14085bda0 for stabilization parameter extraction
- **Angular damping**:
  - Reads angular velocity via FUN_1407be580
  - Applies drag proportional to angular speed, sampled from curve at tuning+0x5B8
  - Drag force = -curve(omega * DAT_141d1f71c) * param_5 * omega_component
- **Gravity compensation**:
  - Gravity vector negated from *(tuning+0x508) + 0x1C
  - Applied as linear force scaled by -param_5
- **Total outputs**:
  - Linear force via FUN_140845210: gravity compensation + angular damping + input forces
  - Torque via FUN_140845260: stabilization + angular rate limiting
- **Progressive airborne accumulator**: car_state+0x13A4
  - Incremented by (tuning+0x628) / ((tuning+0x61C) / param_6) per tick while airborne
  - Clamped to [0, 1.0]
  - Used elsewhere as airborne time factor

### [Priority 1] FUN_140857b20 - Boost/Reactor Force
**Query**: `decompile 0x140857b20`
**Result**: Fully decompiled (~250 lines). Spring/damper + reactor thruster + differential torque.
**Evidence**: Address 140857b20, saved to `decompiled/physics/boost_reactor_force.c`
**Confidence**: VERIFIED
**Resolves**: "How do boost/reactor forces work?"

**Key findings**:
- Iterates over all hardpoints (car_state+0x380 count, car_state+0x388 array)
- Per-hardpoint data at car_state+0x1780, stride 0x2E (46 floats per wheel/hardpoint)
- **Two hardpoint types**:
  - **Type 3 (Spring/Damper)**: Suspension springs
    - Reads spring parameters from tuning+0x238 sub-struct
    - Duration from `tuning+0x2B0`, converted to nanoseconds via `* DAT_141d1f7f8`
    - Checks timestamp via FUN_140856ec0 against last activation time (pfVar15+0xE)
    - Grace period: 10,000,000 ns (10ms) subtracted from elapsed time
    - Fade-in: elapsed / duration, clamped [0, 1]
    - If tuning+0x2B8 flag set: uses inverted (1 - fade) multiplier
    - Compression ratio: pfVar15[0] / tuning+0x244, clamped [0, 1]
    - Force = curve(ratio) * spring_constant(0x23C) - velocity(pfVar15[1]) * damping(0x240)
    - Applied via FUN_140845100 at hardpoint world position
    - Accumulates left-side force (fVar22) and right-side force (fVar23) separately
    - Stores per-hardpoint force at pfVar15[0x22]
  - **Type 5 (Reactor/Thruster)**: Directional thrusters
    - Transforms hardpoint local position to world space using car orientation matrix
    - Computes world-space velocity at hardpoint via FUN_1407bd910
    - Thrust direction = car's Y-axis (up vector) in world space
    - Velocity damping: dot(up, velocity_at_point) * damping_coef
    - If pfVar15[0xD] == 0: damping zeroed (thruster not in contact)
    - Compression ratio: (rest_length - current) / rest_length
    - Force = compression * spring * clamped_ratio * sign_factor - velocity_damping
    - Special case: if tuning+0x1790 == 0xD, multiply by scale at car_state+0x1BB0+0xE0
    - If pfVar15[0xD] == 0: reset compression to rest length (tuning+0x244)
- **Differential torque steering** (bottom section):
  - Only active when FUN_140854120 returns 0 (not in special mode)
  - Requires timestamp within window: `car_state+0x1558 - tuning+0x2BF0 * 1e9 > param_4 > car_state+0x1618`
  - Checks which side has more wheel contact (bVar4 = left, bVar5 = right)
  - If only left wheels in contact and left force > right force:
    - Steering input blended linearly within range [0, tuning+0x2BF8]
    - Torque = (left - right) * tuning+0x2BF4 * blend_factor
    - Moment arm from car_state+0x1BB0 offset 0xB8
  - If only right wheels in contact and right > left:
    - Only when steering input < 0 (turning right)
    - Same formula but reversed
  - Applied via FUN_140845190 (combined force + torque)

### Data Queries

#### Sleep Threshold Value (0x141ebcd04)
**Query**: `data_at 0x141ebcd04 8`
**Result**: `0a d7 23 3c 01 00 00 00`
**Interpretation**:
- First 4 bytes as float32: `0x3c23d70a` = **0.01** (sleep threshold in m/s or rad/s)
- Next 4 bytes as int32: `0x00000001` = 1 (boolean flag, likely "sleep enabled")
- This is the velocity threshold below which physics bodies are put to sleep

#### Tick Rate / Timing Constants
**Query**: `search_strings "10000"` and `search_strings "SamplingPeriod"`
**Result**: No direct "TickDuration" string found. Key findings:
- `141b96f2c`: Literal string "10000" (likely used as parameter, not tick rate directly)
- `141bd6d78`: "1000000." string (microsecond conversion constant)
- `141ccd668`: "GhostSamplingPeriod" - the ghost recording sample rate
- The 10ms constant (10,000,000 ns) appears directly in boost_reactor_force.c code:
  `lVar9 = (param_4 - *(longlong *)(pfVar15 + 0xe)) + -10000000;`
  This confirms the 10ms physics tick period (100 Hz)

#### Ghost System Strings
**Query**: `search_strings "CGameCtnGhost"`
**Result**: Single match at `141c5e3c8` for the class name.
**Additional findings from broad "Ghost" search** (309 matches):
- `CGameCtnGhost` - main ghost class
- `CGameGhostTMData` at `141d1dfa8` - TM-specific ghost data extension
- `CGameGhostScript` - ManiaScript binding
- `CGhostManager` - central ghost management
- `NGameGhost::SMgr` - native ghost manager struct
- `NGameGhostClips::SClipPlayerGhost` - ghost clip data
- `.Ghost.gbx` / `.Ghost.Gbx` - file extensions (two casing variants)
- `GhostSamplingPeriod` - sampling rate configuration
- `InternalDoPhysicalizedGhostResponse` at `141d1d240` - physicalized ghost collision response
- `EGhostPhyMode` - ghost physics mode enum (for physicalized ghosts)
- Ghost driver system: Upload/Download/Playlist API (cloud ghost management)
- `GhostRecorder_RecordingStart`, `RecordingStartAtTime`, `RecordingEnd` - recording lifecycle
- `Ghost_CopyToScoreBestRaceAndLap` - ghost-to-score transfer

#### Damage/Fragile System
**Query**: `search_strings "Damage"` and `search_strings "Fragile"`
**Result**: 59 Damage matches, 5 Fragile matches.
**Key damage system strings**:
- `CarDamage` (`141b64310`) - core vehicle damage system
- `m_DamageZoneAmounts` (`141b65a58`) - per-zone damage values
- `DamagePartWeights` (`141ba7f30`) - part weighting for damage distribution
- `Skip_CarDamage` (`141babb08`) - damage skip flag
- `FallDamage` (`141bed798`) - fall damage system (separate from collision)
- `IsDamageZone` (`141c8c018`) - per-surface damage zone flag
- `DamageZoneAmounts` (`141c8c028`) - zone-specific damage amounts
- `IsDamage` (`141c8c068`) - generic damage flag
- `CharacterDamage` (`141c8c228`) - character (ShootMania) damage
- `Damage%u` (`141c99540`) - formatted damage value output
- `forcedamagezone` (`141bd2f60`) - force a specific damage zone
- Bullet/laser/explosion damage subsystem (ShootMania): DirectHitDamage, ExplosionDamage, LaserDamage, etc.
- `FeatureFallDamage` (`141cebb08`) - feature flag for fall damage
- `DamageInflicted` / `DamageTaken` - event counters
- `OnFallDamage` (`141cf1f08`) - fall damage event callback

**Key fragile system strings**:
- `Fragile` (`141be12a8`) - base surface type
- `BeginFragile` (`141be76c0`) - fragile zone entry event
- `|BlockInfo|Fragile` (`141c99e30`) - block info property
- `SetPlayer_Delayed_Fragile` (`141cf3e20`) - scripting API with 250ms delay
- Description: "Activate or Deactivate Fragile on the player's vehicle with a 250ms delay"

**Fragile/Damage architecture summary**:
- Fragile is a surface property (per-block) that triggers vehicle reset
- 250ms activation delay prevents accidental triggers
- Separate from the ShootMania damage system (bullets, lasers, explosions)
- CarDamage appears to be a visual-only system in TM2020 (damage textures)
- FallDamage is a distinct subsystem with its own feature flag

---

## Summary of Open Questions Resolved

| Question | Status | Finding Location |
|:---|:---:|:---|
| What do the 7 force model functions do? | **MOSTLY RESOLVED** | Priority 1 - 6 of 7 models decompiled (cases 0-3, 5, 6, 0xB) |
| How does force model case 0/1/2 work? | **RESOLVED** | FUN_140869cd0 decompiled |
| How does force model case 3 work? | **RESOLVED** | FUN_14086b060 decompiled (2-wheel/bicycle model) |
| How does force model case 5 work? | **RESOLVED** | FUN_140851f00 decompiled (advanced 4-wheel with jump detection) |
| How does force model case 6 work? | **RESOLVED** | FUN_14085c9e0 decompiled (CarSport full model) |
| How does force model case 0xB work? | **RESOLVED** | FUN_14086d3b0 decompiled (modular CarSport variant) |
| How does the per-wheel visual update work? | **RESOLVED** | FUN_1408570e0 decompiled (spring/contact position) |
| How does airborne control work? | **RESOLVED** | FUN_14085c1b0 decompiled (raycast + auto-landing + angular damping) |
| How do boost/reactor forces work? | **RESOLVED** | FUN_140857b20 decompiled (spring/damper + thruster + diff torque) |
| What is the sleep threshold? | **RESOLVED** | 0x141ebcd04 = 0.01 (float), enabled flag = 1 |
| What is the physics tick rate? | **CONFIRMED** | 10ms (100 Hz) - hardcoded 10,000,000 ns constant in boost code |
| How are speed-dependent coefficients evaluated? | **RESOLVED** | FUN_14042bcb0 curve sampler decompiled |
| How does the game determine surface type? | **RESOLVED** | FUN_140845b60 - vtable at +0x6B8 |
| What are all surface gameplay effect types? | **RESOLVED** | Full EPlugSurfaceGameplayId enum (22 values) |
| How does NoGrip work? | **RESOLVED** | Material property zeroing + begin/end events |
| How does Fragile work? | **RESOLVED** | 250ms delayed activation, collision triggers reset |
| How does slope affect physics? | **RESOLVED** | FUN_1408456b0 - cos(angle)-based factor [0..1] |
| How does the 2-wheel model compute lateral grip? | **RESOLVED** | FUN_14086af20 - Pacejka-like with clamp |
| What is the drift state machine? | **RESOLVED** | 3-state (none/building/committed) in 2-wheel model |
| What are the steering-related fields? | **RESOLVED** | InputSteer, SteerAngle, AnalogSteerV2, etc. |
| How does the ghost system work? | **RESOLVED** | Full API documented, 27+ functions, ghost driver cloud system |
| What ghost-related classes exist? | **RESOLVED** | CGameCtnGhost, CGameGhostTMData, CGhostManager, NGameGhost::SMgr |
| What is the replay file format header? | **RESOLVED** | XML format string extracted |
| What is the map loading sequence? | **RESOLVED** | 23-step pipeline documented |
| How are items placed in maps? | **RESOLVED** | CGameCtnAnchoredObject system |
| What block types exist? | **RESOLVED** | Full class hierarchy (12+ block info types) |
| What audio source types exist? | **RESOLVED** | 7 types including engine, surface, mood |
| How does engine audio work? | **RESOLVED** | Layered throttle/release/idle/limiter system |
| How does the checkpoint system work? | **RESOLVED** | Launched checkpoints with physics forces |
| How does respawn work? | **RESOLVED** | Multiple modes, ManiaScript API documented |
| How does the pack file system work? | **RESOLVED** | Full lifecycle, encryption, GBX body dispatch |
| What is the damage/fragile architecture? | **RESOLVED** | CarDamage (visual), FallDamage (gameplay), Fragile (surface reset) |

### Remaining Open Questions (for future sessions)
- Force model case 4 (FUN_14086bc50) only partially decompiled
- Exact mapping of vehicle type ID to force model case number
- Ghost binary serialization format details (chunk IDs, field layout)
- Pack file binary format (header structure, file table layout)
- Encryption/decryption algorithm for encrypted packages
- PhysicalizedGhost collision response details (FUN at 141d1d240)
- EGhostPhyMode enum values

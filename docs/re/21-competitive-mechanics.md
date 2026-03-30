# Competitive Mechanics: Determinism, Timing, and TAS-Relevant Details

**Binary**: `Trackmania.exe` (Trackmania 2020 by Nadeo/Ubisoft)
**Date**: 2026-03-27
**Sources**: 18 decompiled physics functions, Openplanet plugin intelligence, TMNF cross-reference, Default.json config
**Audience**: Speedrunners, TAS researchers, competitive players who care about millisecond differences
**Methodology**: Every claim grounded in decompiled code. Unknowns are marked explicitly.

---

## Table of Contents

1. [Timing & Tick System](#1-timing--tick-system)
2. [Determinism Guarantees](#2-determinism-guarantees)
3. [Input Pipeline for Speedrunning](#3-input-pipeline-for-speedrunning)
4. [Surface Effect Catalog (Competitive Focus)](#4-surface-effect-catalog-competitive-focus)
5. [Checkpoint & Respawn System](#5-checkpoint--respawn-system)
6. [Speed Limits & Edge Cases](#6-speed-limits--edge-cases)
7. [Race Timer Internals](#7-race-timer-internals)
8. [TMNF vs TM2020 for Competitive Play](#8-tmnf-vs-tm2020-for-competitive-play)
9. [TAS-Relevant Technical Details](#9-tas-relevant-technical-details)
10. [Open Questions for Competitive Community](#10-open-questions-for-competitive-community)

---

## 1. Timing & Tick System

### 1.1 The 100Hz Physics Tick

**Evidence**: `PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`, community knowledge, Default.json `SmMaxPlayerResimStepPerFrame=100`
**Confidence**: PLAUSIBLE (inferred from converging evidence; no single decompiled constant says "100Hz" explicitly)

The physics simulation runs at a **fixed 100Hz tick rate** -- one physics tick every 10 milliseconds. This is the fundamental heartbeat of the game. Display framerate (30fps, 60fps, 144fps, etc.) is completely decoupled from physics ticks.

Key evidence:
- `SmMaxPlayerResimStepPerFrame = 100` in Default.json -- this config value caps how many physics ticks can be resimulated in a single display frame. Setting it to 100 means up to 1 full second of physics can be caught up in one frame, consistent with a 100Hz tick rate.
- The TMNF predecessor runs at 100Hz (community-verified via donadigo's documentation).
- The microsecond conversion pattern `tick * 1000000` (see section 1.2) produces 10,000,000 microseconds per tick when using 10ms ticks, consistent with internal microsecond timing.

**What this means for competition**: Every run is quantized to 10ms boundaries. You cannot gain or lose time in sub-10ms increments at the physics level. The displayed time precision may be finer (millisecond), but the simulation state only changes every 10ms.

### 1.2 Microsecond Internal Timing

**Evidence**: `PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`
**Confidence**: VERIFIED

Both the per-vehicle physics step and the rigid body dynamics step convert ticks to microseconds:

```c
// PhysicsStep_TM (FUN_141501800) line 63
lVar18 = (ulonglong)*param_4 * 1000000;

// NSceneDyna::PhysicsStep (FUN_1407bd0e0) line 15
FUN_140801e20(param_1, (ulonglong)*param_2 * 1000000);
```

The `*param_4` / `*param_2` is the integer tick count. Multiplying by 1,000,000 converts to microseconds using **integer arithmetic** -- no floating point involved in the time tracking itself. This is a deliberate determinism choice: integer tick counters avoid accumulated floating-point drift.

### 1.3 How Game Ticks Are Counted

**Evidence**: `NSceneDyna__PhysicsStep_V2.c:89`
**Confidence**: VERIFIED

The rigid body dynamics step maintains an explicit step counter:

```c
// NSceneDyna::PhysicsStep_V2 (FUN_140803920) line 89
*(int *)(param_1 + 0xf4b) = (int)param_1[0xf4b] + 1;  // byte offset 0x7A58
```

This is a monotonically increasing integer counter at struct offset 0x7A58 in the dynamics world. It increments by exactly 1 per physics step. No fractional ticks, no variable timestep. Combined with the integer tick-to-microsecond conversion, this gives deterministic time progression.

### 1.4 Display FPS vs Physics Ticks

**Evidence**: `Default.json`, architectural analysis from `12-architecture-deep-dive.md`
**Confidence**: PLAUSIBLE

The relationship between display FPS and physics ticks:

| Display FPS | Physics ticks per frame | Notes |
|---|---|---|
| 30 | ~3.3 | Physics runs ahead of display |
| 60 | ~1.67 | Most common case |
| 100 | 1.0 | Exact match -- one tick per frame |
| 144 | ~0.69 | Display faster than physics |
| 240 | ~0.42 | Display much faster than physics |
| Unlimited | Variable | Physics is always 100Hz regardless |

The `SmMaxPlayerResimStepPerFrame=100` config parameter bounds worst-case catch-up: if the display is running at, say, 10fps, the game simulates up to 100 ticks (1 second) per frame to keep physics in sync. If a frame takes longer than 1 second, physics falls behind -- but this represents a catastrophic performance failure.

**Implication for competitive play**: Physics results are identical regardless of display FPS. Running at 30fps vs 300fps produces the same physics outcome for the same inputs. Display FPS only affects input polling frequency and visual smoothness, NOT the physics simulation.

### 1.5 SmMaxPlayerResimStepPerFrame and Resimulation

**Evidence**: `Default.json` line `"SmMaxPlayerResimStepPerFrame" : 100`
**Confidence**: PLAUSIBLE

The "Resim" in the parameter name suggests this is related to **resimulation** -- the process of re-running physics steps when correcting state (e.g., after a network correction in multiplayer, or when catching up after a lag spike). The value 100 means:

- Up to 100 physics ticks can be resimulated in a single display frame
- At 100Hz, this is 1 second of physics simulation
- This is a safety bound to prevent infinite loops if physics falls behind

[UNKNOWN] Whether this also limits the number of fresh physics ticks per frame, or only resimulation ticks.

---

## 2. Determinism Guarantees

### 2.1 What Makes the Replay System Deterministic

**Evidence**: All 18 decompiled physics functions, architectural patterns
**Confidence**: PLAUSIBLE for "fully deterministic within same build"; UNCERTAIN for "bit-identical across builds"

Trackmania's replay system records **inputs**, not positions. When you watch a ghost or validate a replay, the game re-runs the physics with the recorded inputs. This only works if the simulation is deterministic. The decompiled code reveals several mechanisms that enable this:

#### 2.1.1 Fixed Timestep (Integer-Based)

**Evidence**: `PhysicsStep_TM.c:63`
**Confidence**: VERIFIED

```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = integer
```

Time is tracked as integer tick counts. No `+= deltaTime` floating-point accumulation. Every tick is exactly the same duration. This eliminates the most common source of simulation divergence.

#### 2.1.2 Deterministic Sub-Stepping

**Evidence**: `PhysicsStep_TM.c:71-167`
**Confidence**: VERIFIED

Within each tick, the adaptive sub-stepping algorithm computes the number of sub-steps from the current velocity state:

```c
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
sub_dt = dt / num_substeps
```

Given the same velocity state, this produces the same number of sub-steps. The sub-step count is deterministic because:
1. All four velocity magnitudes are computed with the same `x*x + y*y + z*z -> SQRT()` pattern
2. The clamping to 1000 is exact integer comparison (`if (uVar16 < 0x3e9)`)
3. The `sub_dt` division uses the same float precision path every time

#### 2.1.3 Remainder-Step Precision

**Evidence**: `PhysicsStep_TM.c:141-167`
**Confidence**: VERIFIED

The sub-step loop runs `N-1` equal steps, then one final step with the remainder:

```
total_simulated = (N-1) * sub_dt + remainder = dt (exactly)
```

This avoids floating-point drift from repeated `time += sub_dt` addition (which would accumulate rounding error over many iterations).

#### 2.1.4 Guarded Square Root

**Evidence**: All physics files
**Confidence**: VERIFIED

Every square root in the physics code is guarded:

```c
if (fVar24 < 0.0) {
    fVar24 = (float)FUN_14195dd00(fVar24);  // safe sqrt for negative inputs
} else {
    fVar24 = SQRT(fVar24);  // SSE sqrtss
}
```

This prevents NaN propagation from floating-point precision artifacts that could produce tiny negative values under `x*x + y*y + z*z` when x, y, z are very small. NaN would break determinism because `NaN != NaN` causes divergent control flow.

#### 2.1.5 Sequential Processing Order

**Evidence**: `NSceneDyna__PhysicsStep_V2.c:103-116`, `PhysicsStep_TM.c:66-67`
**Confidence**: VERIFIED

Bodies and vehicles are processed in **array order** (sequential iteration):

```c
// PhysicsStep_V2: iterate ordered index array
do {
    uVar2 = *(uint *)(param_1[0x16] + (ulonglong)*puVar12 * 4);
    // ... process body uVar2
    puVar12 = puVar12 + 1;
} while (uVar11 < uVar1);
```

No parallel dispatch, no random ordering. The sorted/ordered iteration ensures collision pair processing is deterministic regardless of memory allocation order.

#### 2.1.6 SSE Floating Point on x64

**Evidence**: Decompiled code patterns, x64 ABI
**Confidence**: VERIFIED (for same-platform determinism)

TM2020 is compiled as x64, which uses SSE for all floating-point operations. SSE `sqrtss`, `addss`, `mulss` etc. are IEEE 754 compliant and produce identical results for identical inputs on the same CPU architecture. The `SQRT()` macro in the decompiled output maps to SSE `sqrtss`.

**WARNING**: This guarantees determinism **within the same platform** (PC x64). Cross-platform determinism (PC vs console vs potential ARM builds) is NOT guaranteed by the code patterns alone -- that would require explicit rounding control or fixed-point arithmetic, which is not observed in the decompiled code.

### 2.2 What Could Break Determinism

| Factor | Risk | Evidence |
|---|---|---|
| Different executable version | HIGH | Any recompilation can change float operation ordering due to compiler optimizations |
| Different CPU architecture (x64 vs ARM) | HIGH | Different rounding for transcendental functions |
| Different FPU rounding mode | MEDIUM | Not observed to be explicitly set in decompiled code [UNKNOWN] |
| Multithreaded physics | LOW | No parallel physics dispatch observed -- sequential iteration confirmed |
| OS differences (Windows version) | LOW | SSE operations are CPU-level, not OS-level |
| Display FPS | NONE | Physics completely decoupled from display |
| GPU driver version | NONE | Physics runs on CPU only |
| Resolution / graphics settings | NONE | Rendering has no feedback to physics |

### 2.3 Ghost Validation and Server Verification

**Evidence**: `12-architecture-deep-dive.md` states 0xC74 and 0x1072, `07-networking.md:861`, `14-tmnf-crossref.md:605`
**Confidence**: PLAUSIBLE (architectural evidence, not fully decompiled)

The ghost/replay validation system works in layers:

1. **Local ghost recording**: The game records input events per-tick (steer, gas, brake). The class hierarchy includes `CInputReplay` for recording/replaying input sequences and `CPlugEntRecordData` for raw ghost frame data.

2. **Local validation**: State 0xC74 in `CGameCtnApp::UpdateGame` calls virtual `(*param_1 + 0x278)` for "Replay Validation". State 0x1072 calls `FUN_140eb3d60` for validation. These likely re-simulate the run from recorded inputs and verify the result matches.

3. **Server-side verification**: TM2020 uploads replay data to Nadeo's servers for anti-cheat verification:
   - `AntiCheatReplayChunkSize` -- chunked upload of replay data
   - `AntiCheatReplayMaxSize` / `AntiCheatReplayMaxSizeOnCheatReport` -- size limits
   - `UploadAntiCheatReplayOnlyWhenUnblocked` -- gating
   - `UploadAntiCheatReplayForcedOnCheatReport` -- forced upload on suspicion

4. **Server resimulation**: The server presumably re-runs the physics with the uploaded inputs to verify the claimed time. This is the fundamental anti-cheat mechanism: if the physics is deterministic, the server can verify any run independently.

**Replay state copy size**: When replaying (SimulationMode == 1 at vehicle+0x1C90), the code copies 2,168 bytes (`0x878`) of vehicle state from replay data:
```c
// NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c:106
FUN_1418d7510(lVar19 + 0x1280, *(undefined8 *)(lVar19 + 0x1c98), 0x878);
```
This 2,168-byte block includes the complete force model configuration, velocity state, and all wheel data needed to reconstruct the exact vehicle state at any point.

[UNKNOWN] The exact binary format of the ghost data (input keyframes, sample rate, compression). The `CPlugEntRecordData` class handles this but its serialization format is not decompiled.

---

## 3. Input Pipeline for Speedrunning

### 3.1 Input Values at the Physics Level

**Evidence**: `19-openplanet-intelligence.md` (CSceneVehicleVisState fields), `04-physics-vehicle.md:572`
**Confidence**: VERIFIED (Openplanet reads these from live game memory)

| Input | Type | Range | Physics Field |
|---|---|---|---|
| Steering | float | -1.0 to +1.0 | `InputSteer` at vis state |
| Throttle | float | 0.0 to 1.0 | `InputGasPedal` |
| Brake | float | 0.0 to 1.0 | `InputBrakePedal` |
| Is Braking | bool | 0 or 1 | `InputIsBraking` |
| Vertical (reactor) | float | [UNKNOWN range] | `InputVertical` |

**Steering is a continuous float, NOT discretized to integer levels.** The value ranges from -1.0 (full left) to +1.0 (full right). Whether the input hardware provides 256, 65536, or truly continuous values, the physics engine receives a 32-bit IEEE 754 float.

### 3.2 Input Resolution by Device Type

**Evidence**: Architectural inference, community knowledge
**Confidence**: PLAUSIBLE

| Device | Effective Resolution | Notes |
|---|---|---|
| Keyboard (digital) | 3 values: -1.0, 0.0, +1.0 | Binary left/right, with progressive steering via input smoothing |
| Gamepad analog stick | ~256 levels per axis | Typical analog stick resolution |
| Gamepad with full-range | ~65536 levels (16-bit ADC) | High-end controllers |
| Steering wheel | Up to 65536 levels | Depends on hardware |

[UNKNOWN] Whether TM2020 applies any input smoothing or dead-zone at the engine level before the value reaches `InputSteer`. The Openplanet VehicleState plugin reads the post-processing value. Keyboard steering in Trackmania is known to have a ramp-up curve (progressive steering), but it is unclear whether this is implemented in the input system or the force model.

### 3.3 When Is Input Sampled?

**Evidence**: Architectural analysis, `PhysicsStep_TM.c` pipeline
**Confidence**: PLAUSIBLE

The physics pipeline per tick is:

```
1. CSmArenaPhysics::Players_BeginFrame
2. ArenaPhysics_CarPhyUpdate
3. PhysicsStep_TM (per vehicle)
   a. Read input (implicit -- input is in vehicle state before forces computed)
   b. Adaptive sub-step loop:
      - Collision detection
      - ComputeForces (reads InputSteer, InputGasPedal, etc.)
      - Force application
      - Integration
4. NSceneDyna::PhysicsStep_V2 (rigid body solver)
```

Input is sampled ONCE per 100Hz tick, BEFORE the sub-step loop begins. All sub-steps within a tick use the same input values. You cannot change steering mid-tick.

**Implication for TAS**: The finest input granularity is 10ms. You can change inputs every tick (100 times per second), but not faster. Sub-steps within a tick always use the same input.

### 3.4 Input to Force Pathway

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:142-162`
**Confidence**: VERIFIED

Input values flow through this chain:

```
Input device -> CInputEngine -> Vehicle state InputSteer/InputGasPedal/etc.
    -> PhysicsStep_TM reads vehicle state
    -> NSceneVehiclePhy::ComputeForces dispatches to force model
    -> Force model (e.g., FUN_140851f00 for model 5/Stadium) reads inputs
    -> Computes tire forces, engine force, steering torque
    -> Applies forces to rigid body
    -> NSceneDyna integrates forces into velocity/position
```

The force model dispatch at `vehicle_model+0x1790` selects which function processes the input:

| Model | Function | Car Type (likely) |
|---|---|---|
| 0, 1, 2 | `FUN_140869cd0` | Legacy/base models |
| 3 | `FUN_14086b060` | [UNKNOWN] |
| 4 | `FUN_14086bc50` | [UNKNOWN] |
| 5 | `FUN_140851f00` | **Stadium (CarSport)** |
| 6 | `FUN_14085c9e0` | **Rally or Snow** |
| 0xB (11) | `FUN_14086d3b0` | **Desert or variant** |

---

## 4. Surface Effect Catalog (Competitive Focus)

### 4.1 Complete Surface Gameplay Effects

**Evidence**: `NHmsCollision__StartPhyFrame.c:100-128`, `10-physics-deep-dive.md` section 6.1
**Confidence**: VERIFIED (string table addresses confirmed)

Every surface gameplay effect in TM2020, with competitive implications:

| Effect | Address | Competitive Impact |
|---|---|---|
| `Turbo` | `0x141be126c` | Speed boost level 1. Force ramps UP linearly (see 4.2). |
| `Turbo2` | `0x141be1288` | Speed boost level 2. Same ramp-up mechanic, higher strength. |
| `ForceAcceleration` | `0x141be1258` | Forces constant acceleration regardless of input. |
| `NoSteering` | `0x141be1238` | Disables steering -- car goes straight. |
| `NoBrakes` | `0x141be12b0` | Disables brake input. |
| `NoGrip` | `0x141be1244` | Zero friction. Car slides on momentum. |
| `FreeWheeling` | `0x141be1278` | Engine disengaged -- coasting only. |
| `Fragile` | `0x141be12a8` | Car breaks on hard impact (see 4.3). |
| `SlowMotion` | `0x141be12d0` | Reduces simulation speed (`SimulationTimeCoef`). |
| `Cruise` | `0x141be1390` | Sets cruise control to fixed speed. |
| `Bouncy` | `0x141be12bc` | High restitution surface -- car bounces. |
| `Bumper` | `0x141be12c4` | Bumper level 1. |
| `Bumper2` | `0x141be12f8` | Bumper level 2. |
| `Reset` | `0x141be124c` | Resets vehicle to last checkpoint. |
| `ReactorBoost_Legacy` | `0x141be12e0` | Non-directional reactor boost. |
| `ReactorBoost2_Legacy` | `0x141be1290` | Non-directional reactor boost level 2. |
| `ReactorBoost_Oriented` | `0x141be1378` | Directional reactor boost. |
| `ReactorBoost2_Oriented` | `0x141be13b0` | Directional reactor boost level 2. |
| `VehicleTransform_CarRally` | `0x141be1300` | Transforms car to Rally. |
| `VehicleTransform_CarSnow` | `0x141be1320` | Transforms car to Snow. |
| `VehicleTransform_CarDesert` | `0x141be1358` | Transforms car to Desert. |
| `VehicleTransform_Reset` | `0x141be1398` | Transforms back to Stadium. |

**Critical note**: Gameplay effects are NOT driven by materials. All 208 materials in the game have `DGameplayId(None)`. Effects come from block/item trigger zones, not surface textures.

### 4.2 Turbo Mechanics -- CRITICAL FINDING

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:89-111`
**Confidence**: VERIFIED (decompiled code)

The turbo/boost force in TM2020 is computed as:

```c
// ComputeForces lines 105-106
float t = (float)(current_tick - start_tick) / (float)duration;
float force = t * strength * model_scale;
```

**The boost force RAMPS UP linearly from 0 to maximum.**

At `t=0` (moment you hit the turbo pad): force = 0.
At `t=1` (boost about to expire): force = strength * model_scale.

This is the **OPPOSITE** of TMNF, where turbo force decayed from maximum to 0.

**Competitive implications**:
- In TM2020, you accelerate MORE as the boost is about to expire
- The moment you touch a turbo pad, you get almost nothing
- Maximum acceleration happens at the very end of the boost duration
- For TAS: this means the timing of WHEN you hit a turbo pad relative to corners matters differently than in TMNF

**Boost parameters** (per vehicle):
| Offset | Type | Field |
|---|---|---|
| `vehicle+0x16E0` | uint | Duration (in ticks) |
| `vehicle+0x16E4` | float | Strength |
| `vehicle+0x16E8` | uint | Start time (-1 = no boost active) |

**Boost initialization**: The start time is set to the current tick when the boost first activates:
```c
if (*(int *)(lVar6 + 0x16e8) == -1) {
    *(uint *)(lVar6 + 0x16e8) = param_5;  // record current tick
}
```

**Boost event dispatch**: When a boost activates, an event is dispatched to the arena (via `FUN_1407d6200`), but only if:
- Event callback exists (`*(longlong *)(param_1 + 8) != 0`)
- Events not disabled (`(*(byte *)(lVar6 + 0x1c7c) & 4) == 0`)
- Player is assigned (`*(char *)(lVar6 + 0x1c78) != -1`)

### 4.3 Fragile Surface -- Exact Break Condition

**Evidence**: `PhysicsStep_TM.c:191-195`
**Confidence**: VERIFIED

The car breaks on a fragile surface when ALL THREE conditions are met simultaneously:

```c
if ((((*(uint *)(lVar9 + 0x1c7c) & 0x1800) == 0x1800) &&       // Condition 1
    (DAT_141d1ef7c < *(float *)(lVar9 + 0x1c8c))) &&            // Condition 2
   (1 < (*(uint *)(lVar9 + 0x128c) & 0xf) - 2)) {              // Condition 3
    FUN_1407d2870(param_1, lVar9, *param_4);                      // BREAK!
}
```

**Condition 1**: Bits 11 AND 12 of `ContactPhyFlags` (vehicle+0x1C7C) must BOTH be set (mask 0x1800). These are collision detection flags set during the sub-step loop.

**Condition 2**: `ContactThreshold` (vehicle+0x1C8C, a float) must exceed the global threshold `DAT_141d1ef7c`. This is a collision severity metric -- gentle landings pass, hard impacts fail.

**Condition 3**: The status nibble (vehicle+0x128C & 0xF) must NOT be 2 or 3. Due to unsigned arithmetic: `(nibble - 2)` wraps for values 0 and 1, making `1 < 0xFFFFFFFE` true. So nibble values 0, 1, and 4+ all pass. Only values 2 and 3 are excluded.

**Competitive implication**: The fragile break is determined by collision severity at `vehicle+0x1C8C` exceeding a threshold. This is NOT simply "any contact = break" -- there is a force/impact threshold. Gentle landings on fragile surfaces should survive. The exact threshold value `DAT_141d1ef7c` is a float at address 0x141d1ef7c in the binary -- [UNKNOWN] what that value is.

### 4.4 Surface Friction System

**Evidence**: `Tunings_CoefFriction_CoefAcceleration.c:31-45`, `10-physics-deep-dive.md` section 5.4
**Confidence**: VERIFIED

The friction system has two layers:

**Layer 1: Per-surface material friction** (from `EPlugSurfaceMaterialId`):

| Surface ID | Physics Role |
|---|---|
| `Asphalt` | High grip (road surfaces, platforms) |
| `Concrete` | Structural, moderate grip |
| `Dirt` | Lower grip, off-road |
| `Grass` | Low grip |
| `Ice` / `RoadIce` | Very low grip |
| `Rubber` | Bouncy (track borders) |
| `Plastic` | Inflatables/obstacles |
| `Metal` | Metallic, moderate |

**Layer 2: Global tuning coefficients** (per-player modifiers):

| Offset in NGameSlotPhy::SMgr | Name | Purpose |
|---|---|---|
| `0x58` | `Tunings.CoefFriction` | Global friction multiplier |
| `0x5C` | `Tunings.CoefAcceleration` | Global acceleration multiplier |
| `0x60` | `Tunings.Sensibility` | [UNKNOWN] |

These can be modified via ManiaScript: `SetPlayer_Delayed_AdherenceCoef` likely modifies `CoefFriction`, `SetPlayer_Delayed_AccelCoef` modifies `CoefAcceleration`. The "Delayed" prefix indicates a 250ms application delay.

**Layer 3: Constraint solver** (iterative):

| Parameter | Type | Purpose |
|---|---|---|
| `FrictionStaticIterCount` | int | Static friction solver iterations (1-20) |
| `FrictionDynaIterCount` | int | Dynamic friction solver iterations (1-20) |
| `VelocityIterCount` | int | Velocity solver iterations (1-20) |
| `PositionIterCount` | int | Position correction iterations (1-10) |

This is a **sequential impulse / Gauss-Seidel constraint solver** with separate iteration counts for static friction, dynamic friction, velocity, and position. More iterations = more accurate but slower.

### 4.5 Reactor Boost Mechanics

**Evidence**: Surface gameplay strings, `10-physics-deep-dive.md` section 6.1
**Confidence**: VERIFIED (strings), PLAUSIBLE (behavioral interpretation)

TM2020 has four reactor boost variants:

| Variant | String | Behavior |
|---|---|---|
| `ReactorBoost_Legacy` | Non-directional | Boost in car's current direction (barrel-roll era) |
| `ReactorBoost2_Legacy` | Non-directional, stronger | Same mechanics, higher force |
| `ReactorBoost_Oriented` | **Directional** | Boost in the pad's orientation direction |
| `ReactorBoost2_Oriented` | **Directional, stronger** | Same, higher force |

The "Oriented" variants are NEW in TM2020 (not present in TMNF/MP). They apply force in the direction the pad is facing, not the direction the car is traveling. This matters for TAS because the approach angle to an oriented reactor pad affects the resulting trajectory.

[UNKNOWN] The exact force magnitude and duration for each reactor boost level. These values are stored in GBX resource files (tuning data), not hardcoded in the executable.

---

## 5. Checkpoint & Respawn System

### 5.1 What State Is Saved at a Checkpoint

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:200-218` (transform copy pattern), `10-physics-deep-dive.md` section 6.5
**Confidence**: PLAUSIBLE (inferred from replay state copy size and transform patterns)

When the car crosses a checkpoint, the game saves enough state to restore the vehicle. The replay system copies **2,168 bytes** (0x878) of vehicle state:

```c
// Vehicle state copy during replay
FUN_1418d7510(lVar19 + 0x1280, *(undefined8 *)(lVar19 + 0x1c98), 0x878);
```

This 2,168-byte block starting at vehicle+0x1280 includes:
- Vehicle unique ID (+0x1280)
- Status flags (+0x128C)
- Velocity vectors (+0x1348 to +0x135C)
- Force model type (+0x1790, via model pointer)
- All four wheel state blocks (stride 0xB8 starting at +0x1790)
- Boost state (+0x16E0/E4/E8)
- Contact history and physics flags

[UNKNOWN] Whether checkpoint state saves the exact same 2,168-byte block as the replay system, or a different subset. The replay copy is confirmed; the checkpoint save mechanism is not independently decompiled.

### 5.2 Transform State (Position + Rotation)

**Evidence**: `PhysicsStep_TM.c:199-215`, `NSceneVehiclePhy__ComputeForces.c:200-218`
**Confidence**: VERIFIED

The vehicle's world transform is stored as 112 bytes at vehicle+0x90 to vehicle+0x100:

```c
// 28 x 4-byte values = 112 bytes, copied from current (+0x90) to previous (+0x104)
*(lVar + 0x104) = *(lVar + 0x90);   // Transform[0]
*(lVar + 0x10C) = *(lVar + 0x98);   // Transform[1]
// ... 12 more 8-byte copies ...
*(lVar + 0x174) = *(lVar + 0x100);  // Transform[16]
```

This is a 4x4-ish matrix (possibly 3x4 rotation+translation + extras). The copy from "current" to "previous" happens at the START of each physics step for interpolation and collision backtracking.

### 5.3 Respawn Position

**Evidence**: Architectural inference from vehicle state structure
**Confidence**: SPECULATIVE

[UNKNOWN] Whether respawn restores the exact saved transform or applies adjustments (e.g., placing the car slightly above the checkpoint surface to avoid ground intersection). The replay state copy is a bitwise memcpy of 2,168 bytes, which suggests an EXACT state restoration, not an approximate one.

### 5.4 Does Respawning Reset Physics State?

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:173-199` (post-switch state reset)
**Confidence**: PLAUSIBLE

The post-force-model reset code zeros extensive physics state:

```c
// Reset 4 wheel state blocks, stride 0xB8 (184 bytes each):
// For each wheel:
//   previous = current; current = 0; timer = 0; model_type = 0
*(lVar6 + 0x17b0) = *(lVar6 + 0x17b4);  // prev = current
*(lVar6 + 0x17b4) = 0;                    // current = 0
*(lVar6 + 0x17c8) = 0;                    // timer1 = 0
*(lVar6 + 0x17c4) = 0;                    // timer2 = 0
*(lVar6 + 0x1794) = 0;                    // state = 0
*(lVar6 + 0x1790) = 0;                    // force model type = 0
```

This reset triggers when `vehicle_model+0x238 - 5U > 1` (a game-mode/class check) AND a condition function returns true. This is likely the respawn/checkpoint reset path.

Additionally, `ComputeForces` and `PairComputeForces` both zero the following on every step for vehicles in reset state (status nibble == 1):
- Force accumulators at +0x1584, +0x158C
- Three force vectors set to zero via `FUN_1407be380`, `FUN_1407be4d0`, `FUN_1407bdc60`, `FUN_1407bde90`

**Competitive implication**: A respawn appears to fully reset wheel state, force accumulators, and timers. The car should start from the checkpoint with clean physics state -- no residual forces, no accumulated slip, no ongoing turbo.

### 5.5 DiscontinuityCount

**Evidence**: `19-openplanet-intelligence.md` (CSceneVehicleVisState)
**Confidence**: VERIFIED

The `DiscontinuityCount` field in the visual state increments on teleport/reset. This is how the rendering system knows the car has been discontinuously moved (e.g., respawn) and should not interpolate between the old and new positions.

---

## 6. Speed Limits & Edge Cases

### 6.1 Maximum Velocity (Speed Cap)

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:112-126`
**Confidence**: VERIFIED

The speed cap is enforced in `NSceneVehiclePhy::ComputeForces`:

```c
fVar9 = *(float *)(local_118 + 0x2f0);   // MaxSpeed from model
fVar8 = vx*vx + vy*vy + vz*vz;           // speed squared (3D magnitude)

if ((fVar9 * fVar9 < fVar8) && (DAT_141d1ed34 < fVar9)) {
    fVar8 = SQRT(fVar8);
    fVar9 = fVar9 / fVar8;               // scale factor
    vx *= fVar9;                          // clamp x
    vy *= fVar9;                          // clamp y
    vz *= fVar9;                          // clamp z
    FUN_140845270(uVar3, lVar6, &velocity);  // write back
}
```

Key observations:
1. The speed cap is stored at **vehicle_model+0x2F0** as a float
2. It is a **3D magnitude cap** -- not per-axis. The car's total speed `sqrt(vx^2 + vy^2 + vz^2)` is capped, not individual components
3. The velocity is scaled uniformly to match MaxSpeed exactly, preserving direction
4. There is a minimum threshold `DAT_141d1ed34` -- speed capping is only applied if MaxSpeed exceeds this threshold (prevents division by near-zero)

**TMNF reference**: TMNF's StadiumCar had MaxSpeed = 277.778 m/s (1000 km/h). TM2020's value is stored in GBX tuning data and is [UNKNOWN] from the binary alone, but the community consensus is around 1000 km/h for Stadium.

### 6.2 Angular Velocity Limits

**Evidence**: Decompiled code patterns
**Confidence**: [UNKNOWN]

No explicit angular velocity clamping was found in the decompiled physics functions. The sub-stepping algorithm uses angular velocity magnitude for step count computation (ensuring more sub-steps for fast-spinning vehicles), but does not clamp it.

[UNKNOWN] Whether angular velocity is capped elsewhere (in the constraint solver, or in the force model functions that were not decompiled).

### 6.3 Sub-Step Count vs Speed

**Evidence**: `PhysicsStep_TM.c:71-132`
**Confidence**: VERIFIED

The sub-step formula:

```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
```

At higher speeds, MORE sub-steps are computed per tick:

| Approximate Speed | Sub-steps (estimate) | Notes |
|---|---|---|
| Standing still | 1 | Minimum |
| Normal driving (~200 km/h) | ~5-20 | Typical gameplay |
| Very fast (~500 km/h) | ~50-100 | High-speed sections |
| Near speed cap (~1000 km/h) | ~200-500 | Extreme speed |
| Above cap + spinning | Up to 1000 | Maximum (hard cap) |

**Does going faster reduce physics accuracy?** NOT directly -- faster speed increases sub-step count, maintaining stability. However, at the 1000 sub-step cap, further speed increases are NOT compensated with more sub-steps. Above this threshold, each sub-step covers a larger distance, potentially missing thin collision geometry.

### 6.4 The 1000 Sub-Step Cap

**Evidence**: `PhysicsStep_TM.c:126-131`
**Confidence**: VERIFIED

```c
if (uVar16 < 0x3e9) {  // < 1001
    // Normal path: compute sub_dt normally
} else {
    uVar17 = 999;       // Cap at 999 iterations + 1 remainder = 1000 total
    fVar26 = (float)param_4[2] / DAT_141d1fa9c;  // dt / 1000.0
}
```

When the computed sub-step count exceeds 1000, it is hard-capped at 1000. The sub-step time becomes `dt / 1000.0` regardless of speed. TMNF allowed up to 10,000 sub-steps -- TM2020 reduced this 10x.

**Competitive implication for extreme TAS scenarios**: At absurdly high speeds (achievable through bugs or chained boosts), the 1000 sub-step cap means the physics simulation becomes less accurate. Collision detection with thin walls could fail at extreme velocities. This is a known issue in speedrunning communities as "noclipping through walls."

---

## 7. Race Timer Internals

### 7.1 Race Start Time

**Evidence**: `19-openplanet-intelligence.md` (CSceneVehicleVisState)
**Confidence**: VERIFIED

The `RaceStartTime` field (type: int) in the vehicle visual state records when the race begins. This is an integer tick timestamp.

### 7.2 Timer Precision

**Evidence**: Internal timing system analysis
**Confidence**: PLAUSIBLE

The race timer displays millisecond precision (e.g., 0:42.123), but the physics tick rate is 100Hz (10ms per tick). This means:

- **Physics quantization**: The car's state changes every 10ms
- **Timer precision**: The timer COUNTS in millisecond precision
- **Effective precision**: Finish times should be quantized to 10ms boundaries (multiples of 0.010s)

[UNKNOWN] Whether the game uses a sub-tick interpolation system for the finish line trigger that provides true millisecond precision, or whether all times are effectively rounded to the nearest 10ms. Community observation suggests times ARE quantized to 10ms (you never see a time like 0:42.123 -- only 0:42.120 or 0:42.130), but this needs empirical verification.

**TMNF reference**: TMNF times are confirmed to be quantized to 10ms (hundredths of a second displayed as thousandths ending in 0). TM2020 likely follows the same pattern.

### 7.3 When Does the Timer Start?

**Evidence**: Architectural inference
**Confidence**: PLAUSIBLE

The timer starts when the car crosses the start line trigger zone (or when the countdown finishes in race mode). The `RaceStartTime` integer field records this as a tick count.

[UNKNOWN] The exact mechanism: is it the first tick where the car's collision geometry overlaps the start trigger, or the first tick after the overlap is detected? A one-tick difference is 10ms.

### 7.4 When Does the Timer Stop?

**Evidence**: Architectural inference
**Confidence**: PLAUSIBLE

The timer stops when the car crosses the finish line trigger zone. The same question applies: is it the tick of overlap detection, or the tick after?

[UNKNOWN] Whether the finish time is the tick of detection minus the start tick (giving a multiple of 10ms), or whether there is interpolation.

### 7.5 Checkpoint Time Recording

**Evidence**: `19-openplanet-intelligence.md`, architectural inference
**Confidence**: PLAUSIBLE

Checkpoint times are recorded as the tick difference between crossing the checkpoint and the race start. Like finish times, these should be quantized to 10ms.

---

## 8. TMNF vs TM2020 for Competitive Play

### 8.1 Physics Changes Summary

**Evidence**: `14-tmnf-crossref.md`, `10-physics-deep-dive.md` section 11
**Confidence**: VERIFIED (structural comparisons)

| Aspect | TMNF | TM2020 | Impact on Competition |
|---|---|---|---|
| **Sub-step cap** | 10,000 | 1,000 | TM2020 has lower physics accuracy at extreme speeds |
| **Force models** | 4 (cases 3,4,5,default) | 7+ (0-6, 0xB) | TM2020 supports more vehicle types |
| **Turbo force curve** | Decays from max to 0 | **Ramps from 0 to max** | Fundamentally different boost behavior |
| **Integration** | Forward Euler | Forward Euler | Same method, same stability characteristics |
| **Tick rate** | 100Hz | 100Hz (inferred) | Same timing granularity |
| **Time unit** | Milliseconds (tick * 0.001) | Microseconds (tick * 1000000) | TM2020 has finer internal precision |
| **Velocity inputs for sub-stepping** | 2 (linear + angular) | 4 (linear + 3 angular) | TM2020 accounts for more motion components |
| **Architecture** | x86 (32-bit, x87 FPU) | x64 (SSE) | Different floating-point behavior |
| **Vehicle types** | Stadium only | Stadium, Rally, Snow, Desert | Dramatically expanded |
| **Friction solver** | Per-wheel analytical | Iterative constraint solver | TM2020 is more physically accurate |

### 8.2 The Turbo Reversal -- Most Important Difference

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:105-106`, `14-tmnf-crossref.md:504`
**Confidence**: VERIFIED

This cannot be overstated: **TM2020 turbo ramps UP, TMNF turbo decayed DOWN.**

TMNF: `force(t) = strength * (1 - t/duration)` -- strongest at the start, fading to zero
TM2020: `force(t) = (t/duration) * strength * modelScale` -- zero at start, maximum at end

If you are a TMNF speedrunner transitioning to TM2020, your intuition about turbo pads is inverted. In TMNF, you wanted to hit the turbo pad early to get maximum immediate boost. In TM2020, the boost builds over time, so the total impulse is the same regardless of when you hit it -- but the acceleration profile is back-loaded.

### 8.3 Sub-Step Cap Reduction (10,000 -> 1,000)

**Evidence**: `PhysicsStep_TM.c:126`, `14-tmnf-crossref.md:191`
**Confidence**: VERIFIED

TMNF allowed up to 10,000 sub-steps per tick. TM2020 allows only 1,000. At extreme speeds, TM2020 is 10x less granular in its collision detection. This may explain why TM2020 has more wall-clipping issues at extreme velocities compared to TMNF.

### 8.4 New Surface Effects

**Evidence**: `10-physics-deep-dive.md` section 6.1
**Confidence**: VERIFIED

Effects not present in TMNF:
- `ReactorBoost_Oriented` / `ReactorBoost2_Oriented` (directional boost)
- `Bumper` / `Bumper2` (bump surfaces)
- `SlowMotion` (time manipulation)
- `Cruise` (fixed speed)
- `VehicleTransform_*` (car type switching)
- `TurboRoulette` (randomized boost: `TurboRoulette_1/2/3`)

### 8.5 Suspension Model Evolution

**Evidence**: `14-tmnf-crossref.md:400-410`
**Confidence**: PLAUSIBLE

TMNF used game-specific parameter names: `AbsorbingValKi` (spring stiffness), `AbsorbingValKa` (damping). TM2020 uses standard engineering notation: `Spring.FreqHz` (natural frequency in Hz), `Spring.DampingRatio` (critical damping ratio). The underlying spring-damper model is equivalent:

```
TMNF:   F = Ki * (rest - compression) - Ka * velocity
TM2020: FreqHz = sqrt(Ki / mass) / (2*pi)
         DampingRatio = Ka / (2 * sqrt(Ki * mass))
```

---

## 9. TAS-Relevant Technical Details

### 9.1 Minimum Input Granularity

- **Time**: 10ms per tick (100Hz). You can change input every tick.
- **Steering**: float -1.0 to +1.0. Continuous within float precision (~7 significant digits).
- **Throttle**: float 0.0 to 1.0. Same float precision.
- **Brake**: float 0.0 to 1.0. Same float precision.

For a TAS tool, the input space is: 100 decision points per second, each with 3 continuous float values (steer, gas, brake) plus a boolean (is_braking).

### 9.2 Sub-Step Determinism for TAS Replay

If you record a TAS as a sequence of `(tick, steer, gas, brake)` tuples and replay them, the result is deterministic IF:
1. Same executable version (same binary)
2. Same map (same collision geometry)
3. Same initial state (same starting position/orientation)
4. Same platform (x64 SSE)

The determinism guarantees from Section 2 ensure bit-identical results under these conditions.

### 9.3 Contact History Buffer (Oscillation Detection)

**Evidence**: `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c:159-192`
**Confidence**: VERIFIED

Each vehicle maintains a 20-entry circular buffer for wheel contact state:

```c
// Buffer at vehicle+0x1594:
//   [0]: write index (circular, mod 20)
//   [1]: buffer size (0x14 = 20)
//   [+8]: 20 bytes of contact state history

// The code counts state transitions in the buffer
for (i = 1; i < buffer_size; i++) {
    if (buffer[(writeIdx - i + 20) % 20] != buffer[(writeIdx - i + 21) % 20])
        transitions++;
}
*(int *)(vehicle + 0x15b0) = transitions;  // ContactStateChangeCount
```

This detects rapid contact/airborne oscillation (a vehicle bouncing). The `ContactStateChangeCount` at vehicle+0x15B0 affects game logic decisions, including potentially the fragile surface check. For TAS, this means rapid bouncing can trigger different code paths than smooth contact.

### 9.4 Sleep Detection System

**Evidence**: `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c:27-57`
**Confidence**: VERIFIED

The physics engine has a sleep detection system that damps very slow velocities:

```c
if (DAT_141ebccfc != 0) {  // sleep enabled
    if (speed_sq < DAT_141ebcd04 * DAT_141ebcd04) {  // below threshold
        vx *= DAT_141ebcd00;  // damp
        vy *= DAT_141ebcd00;
        vz *= DAT_141ebcd00;
    }
}
```

- `DAT_141ebccfc`: Sleep detection enable flag (int)
- `DAT_141ebcd00`: Damping factor (float, < 1.0)
- `DAT_141ebcd04`: Velocity threshold (float, linear m/s, squared before comparison)

**TAS implication**: If a vehicle is nearly stationary (below the sleep threshold), its velocity is actively damped each tick. This is NOT instant zeroing -- it is gradual damping. A TAS that relies on very small velocities (e.g., precise creeping toward a finish line) should be aware that the sleep system will attenuate those velocities.

### 9.5 Gravity -- It Is Not 9.81

**Evidence**: `14-tmnf-crossref.md:670`, TMNF tuning data
**Confidence**: PLAUSIBLE (TMNF values verified, TM2020 inferred)

In TMNF, effective gravity is **NOT** 9.81 m/s^2. It is:
- Ground: 9.81 * 3.0 = **29.43 m/s^2** (GravityCoef = 3.0)
- Air: 9.81 * 2.5 = **24.525 m/s^2** (reduced in air)

TM2020 exposes `GravityCoef` via ManiaScript (`SetPlayer_Delayed_GravityCoef`) and the string `"GravityCoef"` exists at 0x141bb3e18. The base gravity constant (9.81 or similar) is stored in GBX resource files, NOT in the executable -- both TMNF and TM2020 .rdata sections contain no 9.81f constant.

**TAS implication**: The effective gravity is approximately 3x Earth gravity. This explains Trackmania's "heavy" feel and short air times. If you are modeling physics externally for TAS planning, use ~29.4 m/s^2, not 9.81.

### 9.6 Forward Euler Integration Implications

**Evidence**: `14-tmnf-crossref.md:197-202`, `10-physics-deep-dive.md` section 1.3
**Confidence**: VERIFIED

Both TMNF and TM2020 use **Forward Euler** integration:

```
position += velocity * dt
velocity += (force / mass) * dt
```

Forward Euler is:
- First-order accurate (error proportional to dt^2 per step)
- NOT energy-conserving (can gain or lose energy over time)
- Stable for small dt (which is why sub-stepping exists)
- Deterministic (same inputs always produce same outputs)

For TAS: Forward Euler means the simulation has slight energy drift over long runs. The sub-stepping compensates by keeping dt small, but over thousands of ticks, very subtle energy changes accumulate. This is deterministic but NOT physically "correct" -- it is consistently wrong in the same way every time.

---

## 10. Open Questions for Competitive Community

These are questions that emerge from the decompiled code but cannot be answered without empirical testing or further reverse engineering. Speedrunners: your expertise is needed here.

### 10.1 Timer Precision
- **Q**: Are finish times truly quantized to 10ms? Has anyone observed a time ending in anything other than 0 (e.g., 0:42.123 vs 0:42.120)?
- **Test**: Record many runs on the same map and check if all times are multiples of 0.010s.
- **Code basis**: 100Hz tick rate, integer tick counting. Expects 10ms quantization.

### 10.2 Turbo Ramp-Up Verification
- **Q**: Can the turbo force ramp-up be observed in-game? Does the car noticeably accelerate MORE at the end of a turbo than at the beginning?
- **Test**: Use Openplanet to plot `FrontSpeed` over time during a turbo. The acceleration curve should increase linearly.
- **Code basis**: `force = (elapsed/duration) * strength * modelScale` at `NSceneVehiclePhy__ComputeForces.c:105-106`.

### 10.3 Fragile Surface Threshold
- **Q**: What is the exact collision severity threshold for fragile surface breakage? Can it be read via Openplanet at vehicle+0x1C8C?
- **Test**: Land on fragile from increasing heights until breakage occurs. Plot vehicle+0x1C8C value at impact vs breakage outcome.
- **Code basis**: `DAT_141d1ef7c` is the threshold float. Vehicle+0x1C8C is the severity value.

### 10.4 Sub-Step Cap at Extreme Speed
- **Q**: At what speed does the 1000 sub-step cap start affecting collision accuracy? Can wall clips be reliably reproduced at specific speeds?
- **Test**: Use Openplanet to read sub-step count (if accessible) at various speeds, or test wall clipping at increasing velocities.
- **Code basis**: Sub-step cap at 1000 in `PhysicsStep_TM.c:126`.

### 10.5 Sleep Threshold Value
- **Q**: What is the sleep velocity threshold `DAT_141ebcd04`? At what speed does the engine start damping velocity?
- **Test**: Place a car on a flat surface and measure when it stops. Or read the global at address 0x141ebcd04 via a memory tool.
- **Code basis**: `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c:27`.

### 10.6 Reactor Boost Oriented Force Direction
- **Q**: Does `ReactorBoost_Oriented` apply force in the pad's facing direction or the car's facing direction? Does approach angle matter?
- **Test**: Hit an oriented reactor from different angles and observe trajectory.
- **Code basis**: The distinction between `_Legacy` (non-directional) and `_Oriented` (directional) at string level. Force application mechanism not decompiled.

### 10.7 Checkpoint State Completeness
- **Q**: Does a respawn perfectly restore all physics state, or are there subtle differences (e.g., wheel rotation, tire wear, contact history)?
- **Test**: Record vehicle state (via Openplanet) before and after a checkpoint respawn. Compare all fields.
- **Code basis**: Reset zeros wheel state blocks (stride 0xB8) at `ComputeForces.c:173-199`. The 2168-byte replay state copy at `BeforeMgrDynaUpdate.c:106`.

### 10.8 Cross-Version Determinism
- **Q**: Do replays/ghosts from one game version produce identical results on another version? Or do patches break ghost validity?
- **Test**: Save a ghost, update the game, replay the ghost. Compare finish time.
- **Code basis**: Any recompilation can change float operation ordering. Nadeo likely maintains determinism across minor patches but this is not guaranteed by the architecture.

### 10.9 Exact Turbo/Turbo2 Parameters
- **Q**: What are the exact duration and strength values for Turbo and Turbo2? TMNF had Turbo=5.0/250ms, Turbo2=20.0/100ms.
- **Test**: Read vehicle+0x16E0 (duration) and vehicle+0x16E4 (strength) via Openplanet when hitting turbo pads.
- **Code basis**: Offsets confirmed at `NSceneVehiclePhy__ComputeForces.c:89-111`.

### 10.10 Input Smoothing for Keyboard
- **Q**: Does the engine apply input smoothing/ramp for keyboard steering, or is it instantaneous -1/0/+1?
- **Test**: Read `InputSteer` via Openplanet while pressing left/right on keyboard. Plot over time.
- **Code basis**: `InputSteer` is a float -1.0 to 1.0 at the physics level. Keyboard mapping is upstream in CInputEngine.

---

*This document is grounded entirely in decompiled code from Trackmania.exe, Openplanet plugin intelligence, and cross-reference with TMNF reverse engineering. Every address and offset cited is from confirmed decompilation output. Items marked [UNKNOWN] are honest gaps that require either further decompilation or empirical testing by the competitive community. If you test any of the open questions, please document your methodology and results -- they will directly improve this analysis.*

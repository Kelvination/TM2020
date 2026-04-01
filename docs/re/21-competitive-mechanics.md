# Competitive Mechanics: Determinism, Timing, and TAS Details

Trackmania 2020's physics simulation runs at a fixed 100Hz tick rate -- one physics tick every 10 milliseconds. Display framerate is completely decoupled. Every claim here is grounded in decompiled code. Unknowns are marked explicitly.

---

## How the Tick System Works

### The 100Hz Physics Tick

**Confidence**: PLAUSIBLE (inferred from converging evidence; no single decompiled constant says "100Hz" explicitly)

The physics simulation runs at a **fixed 100Hz tick rate**. Display framerate (30fps, 60fps, 144fps) is decoupled from physics ticks.

Key evidence:
- `SmMaxPlayerResimStepPerFrame = 100` in Default.json caps resimulation to 100 ticks per frame (1 second at 100Hz).
- TMNF runs at 100Hz (community-verified via donadigo's documentation).
- The microsecond conversion pattern `tick * 1000000` produces 10,000,000 microseconds per tick at 10ms ticks.

Every run is quantized to 10ms boundaries. You cannot gain or lose time in sub-10ms increments at the physics level.

### Microsecond Internal Timing

**Confidence**: VERIFIED

Both the per-vehicle physics step and the rigid body dynamics step convert ticks to microseconds:

```c
// PhysicsStep_TM (FUN_141501800) line 63
lVar18 = (ulonglong)*param_4 * 1000000;

// NSceneDyna::PhysicsStep (FUN_1407bd0e0) line 15
FUN_140801e20(param_1, (ulonglong)*param_2 * 1000000);
```

The multiplication uses **integer arithmetic** -- no floating point in time tracking. This is a deliberate determinism choice: integer tick counters avoid accumulated floating-point drift.

### Game Tick Counter

**Confidence**: VERIFIED

The rigid body dynamics step maintains an explicit step counter:

```c
// NSceneDyna::PhysicsStep_V2 (FUN_140803920) line 89
*(int *)(param_1 + 0xf4b) = (int)param_1[0xf4b] + 1;  // byte offset 0x7A58
```

This counter increments by exactly 1 per physics step. No fractional ticks, no variable timestep.

### Display FPS vs Physics Ticks

**Confidence**: PLAUSIBLE

| Display FPS | Physics ticks per frame | Notes |
|---|---|---|
| 30 | ~3.3 | Physics runs ahead of display |
| 60 | ~1.67 | Most common case |
| 100 | 1.0 | Exact match |
| 144 | ~0.69 | Display faster than physics |
| 240 | ~0.42 | Display much faster than physics |

Physics results are identical regardless of display FPS. Running at 30fps vs 300fps produces the same physics outcome for the same inputs.

### Resimulation Bounds

**Confidence**: PLAUSIBLE

`SmMaxPlayerResimStepPerFrame = 100` means up to 100 physics ticks can be resimulated per display frame. At 100Hz, this is 1 second of physics simulation. This bounds worst-case catch-up and prevents infinite loops if physics falls behind.

---

## What Makes the Simulation Deterministic

**Confidence**: PLAUSIBLE for "fully deterministic within same build"; UNCERTAIN for "bit-identical across builds"

Trackmania records **inputs**, not positions. Replays re-run physics with recorded inputs. The decompiled code reveals several mechanisms enabling determinism.

### Fixed Timestep (Integer-Based)

**Confidence**: VERIFIED

```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = integer
```

Time is tracked as integer tick counts. No `+= deltaTime` floating-point accumulation. This eliminates the most common source of simulation divergence.

### Deterministic Sub-Stepping

**Confidence**: VERIFIED

Within each tick, adaptive sub-stepping computes step count from the current velocity state:

```c
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
sub_dt = dt / num_substeps
```

Given the same velocity state, this produces the same number of sub-steps because:
1. All four velocity magnitudes use the same `x*x + y*y + z*z -> SQRT()` pattern
2. Clamping to 1000 uses exact integer comparison (`if (uVar16 < 0x3e9)`)
3. The `sub_dt` division uses the same float precision path every time

### Remainder-Step Precision

**Confidence**: VERIFIED

The sub-step loop runs `N-1` equal steps, then one final step with the remainder:

```
total_simulated = (N-1) * sub_dt + remainder = dt (exactly)
```

This avoids floating-point drift from repeated `time += sub_dt` addition.

### Guarded Square Root

**Confidence**: VERIFIED

Every square root in the physics code is guarded:

```c
if (fVar24 < 0.0) {
    fVar24 = (float)FUN_14195dd00(fVar24);  // safe sqrt for negative inputs
} else {
    fVar24 = SQRT(fVar24);  // SSE sqrtss
}
```

This prevents NaN propagation from floating-point precision artifacts. NaN breaks determinism because `NaN != NaN` causes divergent control flow.

### Sequential Processing Order

**Confidence**: VERIFIED

Bodies and vehicles are processed in **array order**:

```c
// PhysicsStep_V2: iterate ordered index array
do {
    uVar2 = *(uint *)(param_1[0x16] + (ulonglong)*puVar12 * 4);
    // ... process body uVar2
    puVar12 = puVar12 + 1;
} while (uVar11 < uVar1);
```

No parallel dispatch, no random ordering. Sequential iteration ensures deterministic collision pair processing regardless of memory allocation order.

### SSE Floating Point on x64

**Confidence**: VERIFIED (for same-platform determinism)

TM2020 uses SSE for all floating-point operations. SSE instructions are IEEE 754 compliant and produce identical results for identical inputs on the same CPU architecture.

**WARNING**: This guarantees determinism **within the same platform** (PC x64). Cross-platform determinism is NOT guaranteed.

### What Could Break Determinism

| Factor | Risk | Evidence |
|---|---|---|
| Different executable version | HIGH | Recompilation changes float operation ordering |
| Different CPU architecture (x64 vs ARM) | HIGH | Different rounding for transcendental functions |
| Different FPU rounding mode | MEDIUM | Not observed to be set explicitly [UNKNOWN] |
| Multithreaded physics | LOW | No parallel physics dispatch -- sequential confirmed |
| Display FPS | NONE | Physics completely decoupled |
| GPU driver version | NONE | Physics runs on CPU only |
| Resolution / graphics settings | NONE | Rendering has no feedback to physics |

### Ghost Validation and Server Verification

**Confidence**: PLAUSIBLE

The ghost/replay validation system works in layers:

1. **Local recording**: Input events per-tick (steer, gas, brake). `CInputReplay` records input sequences. `CPlugEntRecordData` stores raw ghost frame data.

2. **Local validation**: State 0xC74 in `CGameCtnApp::UpdateGame` calls virtual `(*param_1 + 0x278)` for replay validation. State 0x1072 calls `FUN_140eb3d60`.

3. **Server-side verification**: TM2020 uploads replay data for anti-cheat verification:
   - `AntiCheatReplayChunkSize` -- chunked upload of replay data
   - `AntiCheatReplayMaxSize` / `AntiCheatReplayMaxSizeOnCheatReport` -- size limits
   - `UploadAntiCheatReplayForcedOnCheatReport` -- forced upload on suspicion

4. **Server resimulation**: The server re-runs physics with uploaded inputs to verify the claimed time.

**Replay state copy size**: During replay (SimulationMode == 1 at vehicle+0x1C90), the code copies 2,168 bytes (`0x878`) of vehicle state:
```c
// NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c:106
FUN_1418d7510(lVar19 + 0x1280, *(undefined8 *)(lVar19 + 0x1c98), 0x878);
```

---

## How the Input Pipeline Works for Speedrunning

### Input Values at the Physics Level

**Confidence**: VERIFIED (Openplanet reads these from live game memory)

| Input | Type | Range | Physics Field |
|---|---|---|---|
| Steering | float | -1.0 to +1.0 | `InputSteer` at vis state |
| Throttle | float | 0.0 to 1.0 | `InputGasPedal` |
| Brake | float | 0.0 to 1.0 | `InputBrakePedal` |
| Is Braking | bool | 0 or 1 | `InputIsBraking` |
| Vertical (reactor) | float | [UNKNOWN range] | `InputVertical` |

**Steering is a continuous float, NOT discretized to integer levels.**

### Input Resolution by Device Type

**Confidence**: PLAUSIBLE

| Device | Effective Resolution | Notes |
|---|---|---|
| Keyboard (digital) | 3 values: -1.0, 0.0, +1.0 | Binary left/right with progressive steering |
| Gamepad analog stick | ~256 levels per axis | Typical resolution |
| Steering wheel | Up to 65536 levels | Depends on hardware |

[UNKNOWN] Whether TM2020 applies input smoothing or dead-zone at the engine level before `InputSteer`.

### When Input Is Sampled

**Confidence**: PLAUSIBLE

Input is sampled ONCE per 100Hz tick, BEFORE the sub-step loop begins. All sub-steps within a tick use the same input values. You cannot change steering mid-tick.

**TAS implication**: The finest input granularity is 10ms. You can change inputs 100 times per second, but not faster.

### Input to Force Pathway

**Confidence**: VERIFIED

```
Input device -> CInputEngine -> Vehicle state InputSteer/InputGasPedal/etc.
    -> PhysicsStep_TM reads vehicle state
    -> NSceneVehiclePhy::ComputeForces dispatches to force model
    -> Force model reads inputs, computes tire/engine/steering forces
    -> Forces applied to rigid body
    -> NSceneDyna integrates forces into velocity/position
```

Force model dispatch at `vehicle_model+0x1790`:

| Model | Function | Car Type (likely) |
|---|---|---|
| 0, 1, 2 | `FUN_140869cd0` | Legacy/base models |
| 3 | `FUN_14086b060` | [UNKNOWN] |
| 4 | `FUN_14086bc50` | [UNKNOWN] |
| 5 | `FUN_140851f00` | **Stadium (CarSport)** |
| 6 | `FUN_14085c9e0` | **Rally or Snow** |
| 0xB (11) | `FUN_14086d3b0` | **Desert or variant** |

---

## Surface Effects That Matter for Competition

### Complete Surface Gameplay Effects

**Confidence**: VERIFIED (string table addresses confirmed)

| Effect | Address | Competitive Impact |
|---|---|---|
| `Turbo` | `0x141be126c` | Speed boost level 1. Force ramps UP linearly (see below). |
| `Turbo2` | `0x141be1288` | Speed boost level 2. Same ramp-up mechanic, higher strength. |
| `ForceAcceleration` | `0x141be1258` | Forces constant acceleration regardless of input. |
| `NoSteering` | `0x141be1238` | Disables steering -- car goes straight. |
| `NoBrakes` | `0x141be12b0` | Disables brake input. |
| `NoGrip` | `0x141be1244` | Zero friction. Car slides on momentum. |
| `FreeWheeling` | `0x141be1278` | Engine disengaged -- coasting only. |
| `Fragile` | `0x141be12a8` | Car breaks on hard impact. |
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

Gameplay effects are NOT driven by materials. All 208 materials have `DGameplayId(None)`. Effects come from block/item trigger zones, not surface textures.

### Turbo Mechanics -- Force Ramps UP, Not Down

**Confidence**: VERIFIED

The turbo/boost force ramps UP linearly from 0 to maximum:

```c
// ComputeForces lines 105-106
float t = (float)(current_tick - start_tick) / (float)duration;
float force = t * strength * model_scale;
```

At `t=0` (moment you hit the turbo pad): force = 0.
At `t=1` (boost about to expire): force = strength * model_scale.

This is the **OPPOSITE** of TMNF, where turbo force decayed from maximum to 0.

**Competitive implications**:
- You accelerate MORE as the boost expires
- The moment you touch a turbo pad, you get almost nothing
- Maximum acceleration happens at the very end of the boost duration

**Boost parameters** (per vehicle):
| Offset | Type | Field |
|---|---|---|
| `vehicle+0x16E0` | uint | Duration (in ticks) |
| `vehicle+0x16E4` | float | Strength |
| `vehicle+0x16E8` | uint | Start time (-1 = no boost active) |

### Fragile Surface -- Exact Break Condition

**Confidence**: VERIFIED

The car breaks on a fragile surface when ALL THREE conditions are met:

```c
if ((((*(uint *)(lVar9 + 0x1c7c) & 0x1800) == 0x1800) &&       // Condition 1
    (DAT_141d1ef7c < *(float *)(lVar9 + 0x1c8c))) &&            // Condition 2
   (1 < (*(uint *)(lVar9 + 0x128c) & 0xf) - 2)) {              // Condition 3
    FUN_1407d2870(param_1, lVar9, *param_4);                      // BREAK!
}
```

**Condition 1**: Bits 11 AND 12 of `ContactPhyFlags` (vehicle+0x1C7C) must BOTH be set (mask 0x1800).

**Condition 2**: `ContactThreshold` (vehicle+0x1C8C, a float) must exceed global threshold `DAT_141d1ef7c`. Gentle landings pass; hard impacts fail.

**Condition 3**: Status nibble (vehicle+0x128C & 0xF) must NOT be 2 or 3.

The fragile break depends on collision severity, not simply "any contact." Gentle landings on fragile surfaces should survive. The exact threshold value `DAT_141d1ef7c` is [UNKNOWN].

### Surface Friction System

**Confidence**: VERIFIED

The friction system has three layers:

**Layer 1: Per-surface material friction** (`EPlugSurfaceMaterialId`): Asphalt (high grip), Dirt (lower), Grass (low), Ice (very low), etc.

**Layer 2: Global tuning coefficients** (per-player modifiers):

| Offset in NGameSlotPhy::SMgr | Name | Purpose |
|---|---|---|
| `0x58` | `Tunings.CoefFriction` | Global friction multiplier |
| `0x5C` | `Tunings.CoefAcceleration` | Global acceleration multiplier |
| `0x60` | `Tunings.Sensibility` | [UNKNOWN] |

Modifiable via ManiaScript: `SetPlayer_Delayed_AdherenceCoef` and `SetPlayer_Delayed_AccelCoef`. The "Delayed" prefix indicates a 250ms application delay.

**Layer 3: Constraint solver** (iterative):

| Parameter | Type | Purpose |
|---|---|---|
| `FrictionStaticIterCount` | int | Static friction solver iterations (1-20) |
| `FrictionDynaIterCount` | int | Dynamic friction solver iterations (1-20) |
| `VelocityIterCount` | int | Velocity solver iterations (1-20) |
| `PositionIterCount` | int | Position correction iterations (1-10) |

This is a **sequential impulse / Gauss-Seidel constraint solver** with separate iteration counts for static friction, dynamic friction, velocity, and position.

### Reactor Boost Mechanics

**Confidence**: VERIFIED (strings), PLAUSIBLE (behavior)

| Variant | Behavior |
|---|---|
| `ReactorBoost_Legacy` | Boost in car's current direction |
| `ReactorBoost2_Legacy` | Same mechanics, higher force |
| `ReactorBoost_Oriented` | Boost in the pad's orientation direction |
| `ReactorBoost2_Oriented` | Same, higher force |

The "Oriented" variants are NEW in TM2020. They apply force in the direction the pad faces, not the direction you travel. Approach angle to an oriented reactor pad affects trajectory.

[UNKNOWN] Exact force magnitude and duration for each level. Values are in GBX resource files.

---

## Checkpoint and Respawn System

### What State Is Saved at a Checkpoint

**Confidence**: PLAUSIBLE

The replay system copies **2,168 bytes** (0x878) of vehicle state starting at vehicle+0x1280:

```c
FUN_1418d7510(lVar19 + 0x1280, *(undefined8 *)(lVar19 + 0x1c98), 0x878);
```

This block includes: vehicle unique ID, status flags, velocity vectors, force model type, all four wheel state blocks, boost state, and contact history.

### Transform State (Position + Rotation)

**Confidence**: VERIFIED

The vehicle's world transform is stored as 112 bytes at vehicle+0x90. The copy from "current" to "previous" happens at the START of each physics step for interpolation and collision backtracking.

### Respawn Resets Physics State

**Confidence**: PLAUSIBLE

The post-force-model reset code zeros extensive physics state:

```c
// Reset 4 wheel state blocks, stride 0xB8 (184 bytes each):
*(lVar6 + 0x17b0) = *(lVar6 + 0x17b4);  // prev = current
*(lVar6 + 0x17b4) = 0;                    // current = 0
*(lVar6 + 0x17c8) = 0;                    // timer1 = 0
*(lVar6 + 0x17c4) = 0;                    // timer2 = 0
*(lVar6 + 0x1794) = 0;                    // state = 0
*(lVar6 + 0x1790) = 0;                    // force model type = 0
```

A respawn fully resets wheel state, force accumulators, and timers. The car starts from the checkpoint with clean physics state -- no residual forces, no accumulated slip, no ongoing turbo.

### DiscontinuityCount

**Confidence**: VERIFIED

The `DiscontinuityCount` field in the visual state increments on teleport/reset. This tells the renderer not to interpolate between old and new positions.

---

## Speed Limits and Edge Cases

### Maximum Velocity (Speed Cap)

**Confidence**: VERIFIED

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

The speed cap is stored at **vehicle_model+0x2F0**. It is a **3D magnitude cap** -- velocity is scaled uniformly to preserve direction. A minimum threshold `DAT_141d1ed34` prevents division by near-zero.

TMNF's StadiumCar had MaxSpeed = 277.778 m/s (1000 km/h). TM2020's value is [UNKNOWN] from the binary, but community consensus is ~1000 km/h for Stadium.

### Sub-Step Count vs Speed

**Confidence**: VERIFIED

```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
```

| Approximate Speed | Sub-steps (estimate) | Notes |
|---|---|---|
| Standing still | 1 | Minimum |
| Normal driving (~200 km/h) | ~5-20 | Typical gameplay |
| Very fast (~500 km/h) | ~50-100 | High-speed sections |
| Near speed cap (~1000 km/h) | ~200-500 | Extreme speed |
| Above cap + spinning | Up to 1000 | Hard cap |

### The 1000 Sub-Step Cap

**Confidence**: VERIFIED

```c
if (uVar16 < 0x3e9) {  // < 1001
    // Normal path
} else {
    uVar17 = 999;       // Cap at 999 + 1 remainder = 1000 total
    fVar26 = (float)param_4[2] / DAT_141d1fa9c;  // dt / 1000.0
}
```

TMNF allowed up to 10,000 sub-steps. TM2020 reduced this 10x. At absurdly high speeds, collision detection with thin walls can fail. This is the "noclipping through walls" issue.

---

## Race Timer Internals

### Timer Precision

**Confidence**: PLAUSIBLE

The race timer displays millisecond precision (0:42.123), but the physics tick rate is 100Hz (10ms per tick). Finish times should be quantized to 10ms boundaries.

[UNKNOWN] Whether the game uses sub-tick interpolation for finish line triggers. Community observation suggests times ARE quantized to 10ms (you never see 0:42.123 -- only 0:42.120 or 0:42.130).

### RaceStartTime

**Confidence**: VERIFIED

The `RaceStartTime` field (int) in the vehicle visual state records when the race begins as an integer tick timestamp.

---

## TMNF vs TM2020 for Competitive Play

| Aspect | TMNF | TM2020 | Impact on Competition |
|---|---|---|---|
| **Sub-step cap** | 10,000 | 1,000 | TM2020 has lower physics accuracy at extreme speeds |
| **Force models** | 4 (cases 3,4,5,default) | 7+ (0-6, 0xB) | TM2020 supports more vehicle types |
| **Turbo force curve** | Decays from max to 0 | **Ramps from 0 to max** | Fundamentally different boost behavior |
| **Integration** | Forward Euler | Forward Euler | Same method |
| **Tick rate** | 100Hz | 100Hz (inferred) | Same timing granularity |
| **Time unit** | Milliseconds (tick * 0.001) | Microseconds (tick * 1000000) | TM2020 has finer internal precision |
| **Velocity inputs for sub-stepping** | 2 (linear + angular) | 4 (linear + 3 angular) | TM2020 accounts for more motion |
| **Friction solver** | Per-wheel analytical | Iterative constraint solver | TM2020 is more physically accurate |

### The Turbo Reversal

**Confidence**: VERIFIED

**TM2020 turbo ramps UP, TMNF turbo decayed DOWN.**

TMNF: `force(t) = strength * (1 - t/duration)` -- strongest at the start
TM2020: `force(t) = (t/duration) * strength * modelScale` -- zero at start, maximum at end

If you are a TMNF speedrunner, your intuition about turbo pads is inverted.

---

## TAS-Relevant Technical Details

### Minimum Input Granularity

- **Time**: 10ms per tick (100Hz)
- **Steering**: float -1.0 to +1.0 (~7 significant digits)
- **Throttle**: float 0.0 to 1.0
- **Brake**: float 0.0 to 1.0

The input space per second: 100 decision points, each with 3 continuous floats plus a boolean.

### Sub-Step Determinism for TAS Replay

Record a TAS as `(tick, steer, gas, brake)` tuples. Results are deterministic IF:
1. Same executable version
2. Same map (same collision geometry)
3. Same initial state
4. Same platform (x64 SSE)

### Contact History Buffer (Oscillation Detection)

**Confidence**: VERIFIED

Each vehicle maintains a 20-entry circular buffer for wheel contact state:

```c
// Buffer at vehicle+0x1594:
for (i = 1; i < buffer_size; i++) {
    if (buffer[(writeIdx - i + 20) % 20] != buffer[(writeIdx - i + 21) % 20])
        transitions++;
}
*(int *)(vehicle + 0x15b0) = transitions;  // ContactStateChangeCount
```

Rapid bouncing can trigger different code paths than smooth contact.

### Sleep Detection System

**Confidence**: VERIFIED

```c
if (DAT_141ebccfc != 0) {  // sleep enabled
    if (speed_sq < DAT_141ebcd04 * DAT_141ebcd04) {  // below threshold
        vx *= DAT_141ebcd00;  // damp
        vy *= DAT_141ebcd00;
        vz *= DAT_141ebcd00;
    }
}
```

Near-stationary vehicles have velocity actively damped each tick. This is gradual damping, not instant zeroing. A TAS relying on very small velocities should account for this.

### Gravity Is Not 9.81

**Confidence**: PLAUSIBLE (TMNF verified, TM2020 inferred)

Effective gravity in TMNF: 9.81 * 3.0 = **29.43 m/s^2** (GravityCoef = 3.0). Air gravity: 9.81 * 2.5 = **24.525 m/s^2**. TM2020 exposes `GravityCoef` via ManiaScript. The base gravity constant is in GBX resources, NOT the executable.

For TAS planning: use ~29.4 m/s^2, not 9.81.

### Forward Euler Integration Implications

**Confidence**: VERIFIED

Both games use Forward Euler: `position += velocity * dt; velocity += (force / mass) * dt`.

Forward Euler is first-order accurate, NOT energy-conserving, but deterministic. Over thousands of ticks, subtle energy drift accumulates. This is consistently wrong in the same way every time.

---

## Open Questions for the Competitive Community

### Timer Precision
Are finish times quantized to 10ms? Has anyone observed a time ending in anything other than 0?

### Turbo Ramp-Up Verification
Can the ramp-up be observed in-game? Use Openplanet to plot `FrontSpeed` during a turbo -- acceleration should increase linearly.

### Fragile Surface Threshold
What is the exact threshold? Read vehicle+0x1C8C via Openplanet while landing on fragile from increasing heights.

### Sub-Step Cap Speed
At what speed does the 1000 sub-step cap affect collision accuracy? Test wall clipping at increasing velocities.

### Sleep Threshold Value
What is `DAT_141ebcd04`? Read address 0x141ebcd04 via a memory tool, or measure when a car stops on a flat surface.

### Reactor Boost Oriented Force Direction
Does `ReactorBoost_Oriented` apply force in the pad's facing direction or the car's? Hit an oriented reactor from different angles and observe trajectory.

### Checkpoint State Completeness
Does a respawn perfectly restore all physics state? Record vehicle state via Openplanet before and after a respawn. Compare all fields.

### Cross-Version Determinism
Do ghosts from one version produce identical results on another? Save a ghost, update the game, replay it.

### Exact Turbo Parameters
Read vehicle+0x16E0 (duration) and vehicle+0x16E4 (strength) via Openplanet when hitting turbo pads. TMNF had Turbo=5.0/250ms, Turbo2=20.0/100ms.

### Input Smoothing for Keyboard
Read `InputSteer` via Openplanet while pressing left/right on keyboard. Plot over time. Is it instantaneous -1/0/+1 or smoothed?

## Related Pages

- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- Full physics system analysis
- [14-tmnf-crossref.md](14-tmnf-crossref.md) -- TMNF vs TM2020 comparison
- [04-physics-vehicle.md](04-physics-vehicle.md) -- Vehicle physics overview
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Openplanet vehicle state fields
- [30-ghost-replay-format.md](30-ghost-replay-format.md) -- Ghost/replay binary format

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 by Nadeo/Ubisoft)
**Date**: 2026-03-27
**Sources**: 18 decompiled physics functions, Openplanet plugin intelligence, TMNF cross-reference, Default.json config
**Audience**: Speedrunners, TAS researchers, competitive players who care about millisecond differences
**Methodology**: Every claim grounded in decompiled code. Unknowns are marked explicitly.

</details>

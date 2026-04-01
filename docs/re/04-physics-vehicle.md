# Physics and Vehicle Simulation

Trackmania 2020 runs its physics through three cooperating subsystems: NSceneDyna (rigid body dynamics -- gravity, forces, collision response, velocity integration), NSceneVehiclePhy (vehicle-specific forces -- car handling, wheel contact, turbo), and NHmsCollision (collision detection -- broadphase, narrowphase, contact merging). The key insight is that every vehicle gets its own adaptive sub-stepping loop inside `PhysicsStep_TM`, where faster vehicles receive more sub-steps per physics tick to maintain stability.

This document covers the full physics pipeline from top-level orchestration through force computation, collision, and integration. All function identities were recovered via cross-references to profiling string literals embedded in the stripped binary (e.g., `"NSceneVehiclePhy::ComputeForces"` passed to a profiling scope function).

---

## How the physics simulation pipeline works

The simulation runs as a multi-stage pipeline each physics tick. `CSmArenaPhysics` manages per-player physics state. `PhysicsStep_TM` drives the per-vehicle simulation loop.

```
CSmArenaClient::UpdatePhysics (FUN_141312870 @ 0x141312870)
  or
CSmArenaServer::UpdatePhysics (FUN_141339cc0 @ 0x141339cc0)
  |
  +-> CSmArenaPhysics::Players_BeginFrame (FUN_1412c2cc0 @ 0x1412c2cc0)
  +-> CSmArenaPhysics::UpdatePlayersInputs (FUN_1412bf000 @ 0x1412bf000)
  +-> CSmArenaPhysics::Players_UpdateTimed (FUN_1412c7d10 @ 0x1412c7d10)
  |     |
  |     +-> ArenaPhysics_CarPhyUpdate (FUN_1412e8490 @ 0x1412e8490)
  |     +-> PhysicsStep_TM (FUN_141501800 @ 0x141501800)  -- per-vehicle
  |           |
  |           +-> Adaptive sub-stepping loop (velocity-dependent)
  |           |     |
  |           |     +-> Collision check (FUN_141501090)
  |           |     +-> NSceneVehiclePhy::ComputeForces (FUN_1408427d0)
  |           |     +-> Force application (FUN_1414ffee0)
  |           |     +-> Post-force update (FUN_1414ff9d0)
  |           |     +-> Physics step dispatch (FUN_1415009d0)
  |           |     +-> Integration (FUN_14083df50)
  |           |
  |           +-> NSceneDyna::PhysicsStep (FUN_1407bd0e0 @ 0x1407bd0e0)
  |                 +-> NSceneDyna::PhysicsStep_V2 (FUN_140803920 @ 0x140803920)
  |                       +-> NSceneDyna::DynamicCollisionCreateCache
  |                       +-> NSceneDyna::InternalPhysicsStep (FUN_1408025a0)
  |                       +-> Body force clearing (stride 0x38)
  |
  +-> CSmArenaPhysics::Bullet_UpdateBeforeMgr (FUN_141317300 @ 0x141317300)
  +-> CSmArenaPhysics::Bullet_AfterMgr [UNKNOWN addr]
  +-> CSmArenaPhysics::Gates_UpdateTimed [UNKNOWN addr]
  +-> CSmArenaPhysics::Players_ObjectsInContact_UpdateBeforeCharPhyStep [UNKNOWN addr]
  +-> CSmArenaPhysics::BestTargets_BeginFrame [UNKNOWN addr]
  +-> CSmArenaPhysics::Players_FindBestTarget [UNKNOWN addr]
  +-> CSmArenaPhysics::ArmorReplenish_EndFrame [UNKNOWN addr]
  +-> CSmArenaPhysics::Actors_ObjectsBeginFrame [UNKNOWN addr]
  +-> CSmArenaPhysics::Actors_UpdateTimed [UNKNOWN addr]
  +-> CSmArenaPhysics::Players_EndFrame [UNKNOWN addr]
```

### PhysicsStep_TM per-vehicle loop

**Evidence**: `PhysicsStep_TM.c:7-224`
**Confidence**: VERIFIED
**Address**: FUN_141501800

The profiling scope string `"PhysicsStep_TM"` confirms this is the main per-vehicle physics step.

```c
// FUN_141501800 - PhysicsStep_TM
void FUN_141501800(param_1, param_2, param_3, param_4) {
    // 1. Convert tick to microseconds
    lVar18 = (ulonglong)*param_4 * 1000000;   // line 63

    // 2. Iterate over all vehicles
    for each vehicle lVar9 in param_3:

        // 3. Check vehicle status nibble
        if (((byte)*(lVar9 + 0x128c) & 0xf) != 2)  // skip state 2

        // 4. Clear physics flags
        *(lVar9 + 0x1c7c) &= 0xfffff5ff;           // line 69

        // 5. Check simulation mode (0 or 3 = normal)
        if (*(lVar9 + 0x1c90) == 0 || *(lVar9 + 0x1c90) == 3)

        // 6. Compute adaptive sub-step count
        // 7. Run sub-step loop
        // 8. Copy transform (current -> previous)

    // State 1/2 path: copy transform directly
    *(lVar9 + 0x104) = *(lVar9 + 0x90);  // etc (lines 199-215)
}
```

### Simulation timing

**Evidence**: `PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`
**Confidence**: VERIFIED

Both functions convert tick values to microseconds using integer arithmetic (a deliberate determinism choice):

```c
// PhysicsStep_TM
lVar18 = (ulonglong)*param_4 * 1000000;

// NSceneDyna::PhysicsStep
FUN_140801e20(param_1, (ulonglong)*param_2 * 1000000);
```

Given TM2020 runs at 100Hz (10ms per physics tick), this produces 10,000,000 microseconds per tick.

A separate `CSmArena::SimulationStep` function (at `FUN_1412e9ea0`, referenced at `0x141cec210`) orchestrates the overall simulation step. The strings `"SimulationTime"` and `"SimulationRelativeSpeed"` suggest the simulation tracks both absolute and relative (slow-motion/speed-up) time.

| String | Address | Notes |
|--------|---------|-------|
| `"SimulationTime"` | `0x141b723a0` | Absolute simulation clock |
| `"SimulationRelativeSpeed"` | `0x141b723d0` | Speed multiplier for the simulation |
| `"PeriodEstimated"` | `0x141b723c0` | [UNKNOWN] Estimated frame period |
| `"PeriodSmoothing"` | `0x141b723e8` | [UNKNOWN] Frame period smoothing factor |
| `"SimulationTimeCoef"` | `0x141be7e40` | [UNKNOWN] Time coefficient for visuals |
| `"FixedStepCount"` | `0x141bd9a78` | Referenced by `FUN_14062c780` -- animation fixed step count |
| `"Use_TM_Simulation"` | `0x141bb3fc8` | Flag distinguishing TM physics from generic dyna |
| `"DynaModel.Use_TM_Simulation"` | `0x141d1aab0` | Per-model flag for TM-specific simulation |

### PhysicsStep_V2 orchestration

**Evidence**: `NSceneDyna__PhysicsStep_V2.c:1-237`
**Confidence**: VERIFIED
**Address**: FUN_140803920

PhysicsStep_V2 is the rigid body dynamics orchestrator.

1. **Step counter increment**: `*(param_1 + 0xf4b) += 1` (line 89)
2. **Time scale**: `fVar16 = (float)param_2[2] * DAT_141d1fa9c` (line 133)
3. **Collision cache creation**: Calls `FUN_1407f9da0` (DynamicCollisionCreateCache) (line 150)
4. **InternalPhysicsStep dispatch**: Calls `FUN_1408025a0` if bodies need updating (line 201)
5. **Body force clearing**: Loop zeros `+0x8` in body array with stride `0x38` (56 bytes) (lines 214-232)

**Struct Offset**: `param_1[0xf4b]` = physics step counter (byte offset 0x7A58).

The body force clearing uses both strides `0x38` (56 bytes, unrolled 4x as `0xE0` = 224 bytes) and single-iteration `0x38`. This confirms the per-body data structure is 56 bytes with forces at offset `+0x8`.

---

## How velocity-adaptive sub-stepping works

Sub-stepping (velocity-adaptive subdivision of a physics tick) keeps the simulation stable at high speeds. The engine computes more sub-steps for faster vehicles.

**Quick version**: The sub-step count equals `floor(total_speed * scale * dt / step_size) + 1`, capped at 1000. Each sub-step runs the full force computation and integration pipeline.

**Evidence**: `PhysicsStep_TM.c:71-167`
**Confidence**: VERIFIED

### The 4-velocity computation

TM2020 uses **four separate velocity magnitudes** to determine sub-step count. This is a notable difference from TMNF, which used only two.

```
|v1| = sqrt(body.linear_vel.x^2 + body.linear_vel.y^2 + body.linear_vel.z^2)
|v2| = sqrt(body.angular_vel.x^2 + body.angular_vel.y^2 + body.angular_vel.z^2)
|v3| = sqrt(vehicle.vel1.x^2 + vehicle.vel1.y^2 + vehicle.vel1.z^2)
|v4| = sqrt(vehicle.vel2.x^2 + vehicle.vel2.y^2 + vehicle.vel2.z^2)
```

Each sqrt has a guard: `if (val < 0.0) call safe_sqrt else SQRT()`. The linear velocity comes from the rigid body at `(lVar15+0x40..0x48)`. The angular velocity comes from `(lVar15+0x4C..0x54)`. The two additional velocities come from vehicle state at `(+0x1348..0x1350)` and `(+0x1354..0x135C)`.

### Sub-step formula

```c
// Compute a velocity magnitude from linear + angular velocity vectors
fVar24 = SQRT(v_linear.x^2 + v_linear.y^2 + v_linear.z^2);
fVar27 = SQRT(v_angular1.x^2 + v_angular1.y^2 + v_angular1.z^2);
fVar28 = SQRT(v_angular2.x^2 + v_angular2.y^2 + v_angular2.z^2);
fVar26 = SQRT(v_angular3.x^2 + v_angular3.y^2 + v_angular3.z^2);

// Determine sub-step count based on velocity
uVar17 = (uint)(((fVar24 + fVar27 + fVar28 + fVar26) * fVar25) / *(float *)(lVar15 + 0x54));
uVar16 = uVar17 + 1;

// Cap at 1000 sub-steps (constant DAT_141d1fa9c likely = 1000.0f)
if (uVar16 >= 0x3e9) {   // 1001
    uVar17 = 999;
    fVar26 = (float)param_4[2] / DAT_141d1fa9c;
}
```

In compact form:

```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
sub_dt = dt / num_substeps
```

### Sub-step loop execution

The loop runs `N-1` equal-size steps, then one final step with the remainder:

```c
// Run (num_substeps - 1) equal-size steps
for (i = 0; i < num_substeps - 1; i++) {
    collision_result = FUN_141501090(&bounds, transform);
    flags |= (collision_result & 1) << 16;       // store in bit 16 of ContactPhyFlags

    FUN_140801e20(dyna_mgr, time_us);            // set dyna time
    FUN_1414ffee0(dyna, dyna_mgr, ..., sub_dt);  // compute forces
    FUN_1414ff9d0(dyna_mgr, vehicle, sub_dt);    // post-force
    FUN_1415009d0(dyna_mgr, ..., sub_dt);        // physics step
    FUN_14083df50(arena, dyna_mgr, vehicle, tick, sub_dt);  // integrate

    time_us -= (longlong)(sub_dt * 1000000.0);   // advance time
}

// Final step with remainder
remainder = scaled_dt - (scaled_dt_per_step * (num_substeps - 1));
// ... same 6 function calls with remainder instead of sub_dt
```

This remainder approach avoids floating-point drift from repeated `time += sub_dt` addition:

```
total_simulated = (N-1) * sub_dt + remainder = dt (exactly)
```

### Sub-step count estimates by speed

| Approximate Speed | Sub-steps (estimate) | Notes |
|---|---|---|
| Standing still | 1 | Minimum |
| Normal driving (~200 km/h) | ~5-20 | Typical gameplay |
| Very fast (~500 km/h) | ~50-100 | High-speed sections |
| Near speed cap (~1000 km/h) | ~200-500 | Extreme speed |
| Above cap + spinning | Up to 1000 | Maximum (hard cap) |

### The 1000 sub-step cap

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

TMNF allowed up to 10,000 sub-steps. TM2020 reduced this 10x. At the 1000 sub-step cap, further speed increases are NOT compensated with more sub-steps. Each sub-step covers a larger distance, potentially missing thin collision geometry.

| Parameter | Value | Evidence |
|:---|:---|:---|
| Maximum sub-steps | **1000** (0x3E9 - 1 = 0x3E8) | `if (uVar16 >= 0x3E9)` then cap at 999 |
| Divisor at +0x54 | float from body state | `*(float *)(lVar15 + 0x54)` |
| Time constant | `DAT_141d1fa9c` | Used as divisor when capping (likely 1000.0f) |
| Microsecond conversion | `_DAT_141d1fe58` (double) | Multiplied by sub_dt for time advance |

---

## How vehicle forces are computed (NSceneVehiclePhy)

NSceneVehiclePhy handles all vehicle-specific physics: car forces, wheel contact, turbo. The core entry point is `NSceneVehiclePhy::ComputeForces`, which dispatches to one of seven force models based on vehicle type.

### Key functions

| Function Label | Address | Size | Description |
|----------------|---------|------|-------------|
| `NSceneVehiclePhy::ComputeForces` | `0x1408427d0` | 1713 B | Main vehicle force computation |
| `NSceneVehiclePhy::PairComputeForces` | `0x140842ed0` | 635 B | Vehicle-vs-vehicle force computation |
| `NSceneVehiclePhy::PhysicsStep_BeforeMgrDynaUpdate` | `0x1407cfce0` | 1723 B | Pre-dynamics update (transforms, collision prep) |
| `NSceneVehiclePhy::PhysicsStep_ProcessContactPoints` | `0x1407d2b90` | 339 B | Process collision contact points |
| `NSceneVehiclePhy::ExtractVisStates` | `0x1407d29a0` | 338 B | Copy physics state to visual state |
| `NSceneVehiclePhy::Replica_SnapshotTake` | [UNKNOWN] | [UNKNOWN] | Snapshot for network replication |
| `NSceneVehiclePhy::M3to6_AbsorbContact` | [UNKNOWN] | [UNKNOWN] | Contact absorption [UNKNOWN purpose] |
| `NSceneVehiclePhy::SStuntStatus` | [UNKNOWN] | [UNKNOWN] | Stunt tracking data structure |
| `NSceneVehiclePhy::SStuntFigure` | [UNKNOWN] | [UNKNOWN] | Stunt figure detection data |

### The 7 force models

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:142-162`
**Confidence**: VERIFIED
**Struct Offset**: `vehicle_model+0x1790` (force model type selector)

The switch at offset `+0x1790` dispatches to different force computation functions:

```c
switch(*(undefined4 *)(local_118 + 0x1790)) {
    case 0:
    case 1:
    case 2:
        FUN_140869cd0(param_3, &local_158);      // Standard/base model
        break;
    case 3:
        FUN_14086b060(param_3, &local_158);      // Alternate model A
        break;
    case 4:
        FUN_14086bc50(param_3, &local_158);      // Alternate model B
        break;
    case 5:
        FUN_140851f00(param_3, param_4, &local_158);  // Extended model A (takes extra param)
        break;
    case 6:
        FUN_14085c9e0(param_3, param_4, &local_158);  // Extended model B (takes extra param)
        break;
    case 0xb:
        FUN_14086d3b0(param_3, param_4, &local_158);  // Model 11
        break;
}
```

### Force model identification

**Evidence**: Cross-reference with TMNF `ESteerModel` enum and gbx-net field names
**Confidence**: PLAUSIBLE (mapping inferred from TMNF analysis + TM2020 switch values)

| Switch Value | Function Address | TMNF Equivalent | Likely Car Type | Notes |
|:---:|:---:|:---:|:---:|:---|
| 0, 1, 2 | `FUN_140869cd0` | Steer01/02/03 (default) | Base/legacy models | 2 params, simplest model |
| 3 | `FUN_14086b060` | Steer04 (M4) | [UNKNOWN] | 2 params, lateral friction focus |
| 4 | `FUN_14086bc50` | Steer05 (M5) | [UNKNOWN] | 2 params, TMNF-era model |
| 5 | `FUN_140851f00` | Steer06 (M6) | **CarSport (Stadium)** | 3 params, full simulation |
| 6 | `FUN_14085c9e0` | [NEW in TM2020] | **SnowCar** or **RallyCar** | 3 params, new model |
| 0xB (11) | `FUN_14086d3b0` | [NEW in TM2020] | **DesertCar** or variant | 3 params, newest model |

**Models 0-4** (2-parameter) take only the dynamics state and vehicle context. They represent simpler force models.

**Models 5, 6, 0xB** (3-parameter) receive an additional tick/time parameter, enabling time-dependent features like turbo decay curves, time-limited boost effects, cruise control timing, and vehicle transform transition physics.

### Pre-force-model path: force accumulator selection

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:128-137`
**Confidence**: VERIFIED

Before the switch, the code selects different force source offsets:

```c
if (*(int *)(local_118 + 0x1790) < 6) {
    // Models 0-5: read force from vehicle+0x144C (12 bytes)
    local_b8 = *(lVar6 + 0x144c);
    uStack_b4 = *(lVar6 + 0x1450);   // implied from 8-byte read
    uStack_b0 = *(lVar6 + 0x1454);
} else {
    // Models 6+: read force from vehicle+0x1534 (12 bytes)
    local_b8 = *(lVar6 + 0x1534);
    uStack_b4 = *(lVar6 + 0x1538);   // implied
    uStack_b0 = *(lVar6 + 0x153c);
}
```

Models 6+ use a different force accumulator location. The offsets `+0x144C` and `+0x1534` are separated by `0xE8` (232 bytes), large enough for an entire wheel-set of per-wheel data.

### Vehicle state byte and speed clamping

**Vehicle state byte at offset +0x128C**: A status nibble `(byte & 0xF)` controls vehicle behavior:
- Value `1`: Vehicle is in a reset/inactive state -- forces are zeroed out
- Value `2`: Vehicle is [UNKNOWN state] -- checked in PhysicsStep_TM
- Other values: Normal force computation proceeds

**Speed clamping** (offset +0x2F0 on the model object):

```c
fVar9 = *(float *)(local_118 + 0x2f0);  // maxSpeed from model
fVar8 = vx*vx + vy*vy + vz*vz;          // velocity magnitude squared
if ((fVar9 * fVar9 < fVar8) && (DAT_141d1ed34 < fVar9)) {
    fVar8 = SQRT(fVar8);
    fVar9 = fVar9 / fVar8;
    // Scale velocity to max speed
    local_130 = local_130 * fVar9;
    local_12c = local_12c * fVar9;
    local_128 = local_128 * fVar9;
}
```

The speed cap is a **3D magnitude cap** (not per-axis). The car's total speed `sqrt(vx^2 + vy^2 + vz^2)` is clamped, preserving direction. The constant `DAT_141d1ed34` is a minimum threshold that prevents division by near-zero.

### Checkpoint reset logic

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:173-199`
**Confidence**: VERIFIED

After the force model switch, the code checks whether to reset physics state:

```c
if ((1 < *(int *)(local_118 + 0x238) - 5U) &&
    (iVar5 = FUN_14083db20(local_150 + 0x1280), iVar5 != 0)) {
    // Reset 4 parallel wheel state blocks, each with same pattern:
    // previous = current; current = 0; clear timers/state

    // Block 1: offsets 0x1790-0x17C8
    *(lVar6 + 0x17b0) = *(lVar6 + 0x17b4);   // prev = current
    *(lVar6 + 0x17b4) = 0;                     // current = 0
    *(lVar6 + 0x17c8) = 0;                     // timer = 0
    *(lVar6 + 0x17c4) = 0;
    *(lVar6 + 0x1794) = 0;
    *(lVar6 + 0x1790) = 0;                     // force model type = 0

    // Block 2: offsets 0x1848-0x1880 (stride 0xB8 from block 1)
    *(lVar6 + 0x1868) = *(lVar6 + 0x186c);
    *(lVar6 + 0x186c) = 0;
    // ... (identical pattern)

    // Block 3: offsets 0x1900-0x1938 (stride 0xB8 from block 2)
    // Block 4: offsets 0x19B8-0x19F0 (stride 0xB8 from block 3)
}
```

The 4 blocks at stride `0xB8` (184 bytes) correspond to the 4 wheels, each containing:
- `+0x00`: Force model type (the 0x1790 selector)
- `+0x04`: [UNKNOWN]
- `+0x20`: Previous value
- `+0x24`: Current value
- `+0x34`: Timer/counter
- `+0x38`: Timer/counter

### Vehicle type to force model mapping

**Evidence**: Surface gameplay strings in `NHmsCollision__StartPhyFrame.c:100-128`, `04-physics-vehicle.md`
**Confidence**: SPECULATIVE

| Vehicle | Likely Model | Reasoning |
|:---|:---:|:---|
| **CarSport (Stadium)** | 5 | The M6/Steer06 model from TMNF, confirmed as the full simulation model. CarSport is the primary racing car. |
| **RallyCar** | 6 | Rally requires different tire physics (loose surface, sliding), new model with time param. |
| **SnowCar** | 6 or 0xB | Snow physics need unique slip/ice model; may share model 6 with different tuning or use 0xB. |
| **DesertCar** | 0xB | Desert is the most different driving style; likely the newest model (value 11). |
| **Legacy/inactive** | 0, 1, 2 | Base models for backward compatibility or simplified simulation. |

---

## How the turbo and boost system works

Turbo in TM2020 applies a time-varying directional force that **ramps UP** linearly. This is the opposite of TMNF, where turbo decayed from maximum to zero.

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:89-111`
**Confidence**: VERIFIED

### Turbo force computation

```c
// Initialize boost start time if first activation
if (*(int *)(lVar6 + 0x16e8) == -1) {
    *(uint *)(lVar6 + 0x16e8) = param_5;   // record current tick

    // If has event callback and not disabled
    if (*(longlong *)(param_1 + 8) != 0 &&
        (*(byte *)(lVar6 + 0x1c7c) & 4) == 0 &&
        *(char *)(lVar6 + 0x1c78) != -1) {
        // Dispatch boost event to arena
        FUN_1407d6200();
    }
}

// Apply boost force if within duration window
uVar2 = *(uint *)(lVar6 + 0x16e8);
if (uVar2 <= param_5 && param_5 <= uVar2 + *(uint *)(lVar6 + 0x16e0)) {
    // Linearly interpolate force over duration
    float t = (float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0);
    float force = t * *(float *)(lVar6 + 0x16e4)    // strength
                    * *(float *)(model + 0xe0);       // model scale

    // Apply as directional force
    FUN_1407bdf40(dyna_mgr, dyna_id, &force_vec);
}
```

At `t=0` (moment you hit the turbo pad): force = 0. At `t=1` (boost about to expire): force = strength * model_scale.

### Boost state offsets

| Offset | Type | Field |
|---|---|---|
| `vehicle+0x16E0` | uint | Duration (in ticks) |
| `vehicle+0x16E4` | float | Strength |
| `vehicle+0x16E8` | uint | Start time (-1 = no boost active) |

### Turbo levels and variants

Two primary turbo levels exist:
- **Turbo** (level 1) -- `"Turbo"` at `0x141be126c`
- **Turbo2** (level 2) -- `"Turbo2"` at `0x141be1288`

Turbo parameters are configurable per track via `"TurboDuration"` / `"TurboVal"` (`0x141c52720`-`0x141c52780`).

A separate **reactor boost** system exists:
- `"ReactorBoost_Legacy"` / `"ReactorBoost2_Legacy"` -- Non-oriented boosts
- `"ReactorBoost_Oriented"` / `"ReactorBoost2_Oriented"` -- Direction-sensitive boosts (NEW in TM2020)

Reactor boost state fields:
- `"ReactorBoostLvl"` (at `0x141be7818`) -- Current boost level
- `"ReactorBoostType"` (at `0x141be7850`) -- Boost type enum
- `"ReactorAirControl"` (at `0x141be7838`) -- Air control when using reactor
- `"IsReactorGroundMode"` (at `0x141be7918`) -- Whether reactor works on ground

A randomized **turbo roulette** system provides `TurboRoulette_1`, `TurboRoulette_2`, `TurboRoulette_3` (`0x141cdfce8`-`0x141cdfec8`) with corresponding color variants.

### Complete turbo code path

```
Surface Contact Detection
    |
    v
Gameplay Effect System (EPlugSurfaceGameplayId)
    recognizes "Turbo" (0x141be126c) or "Turbo2" (0x141be1288)
    |
    v
Vehicle State Update:
    vehicle+0x16E0 = duration (uint, in ticks)
    vehicle+0x16E4 = strength (float)
    vehicle+0x16E8 = 0xFFFFFFFF (not yet started)
    |
    v
NSceneVehiclePhy::ComputeForces (FUN_1408427d0)
    called each sub-step within PhysicsStep_TM
```

The actual duration and strength values for each turbo level are NOT hardcoded in the executable. They load from GBX resource files. From TMNF cross-reference: TMNF used TurboBoost=5.0/Duration=250ms and Turbo2Boost=20.0/Duration=100ms.

---

## How vehicle types and transforms work

Strings reveal the known vehicle types and transform triggers:

| String | Address | Notes |
|--------|---------|-------|
| `"VehicleTransform_CarRally"` | `0x141be1300` | Rally car transform |
| `"VehicleTransform_CarSnow"` | `0x141be1320` | Snow car transform |
| `"VehicleTransform_CarDesert"` | `0x141be1358` | Desert car transform |
| `"VehicleTransform_Reset"` | `0x141be1398` | Reset to default car |
| `"CarSport"` | `0x141c3c7c8` | Stadium car model name |
| `"StadiumCar"` | `0x141bd3a00` | Alternate name for Stadium car |
| `"SnowCar"` | `0x141c5a348` | Snow car model name |
| `"RallyCar"` | `0x141c5a338` | Rally car model name |
| `"DesertCar"` | `0x141c5a318` | Desert car model name |

Vehicle item files load from:
- `\Vehicles\Items\CarSport.Item.gbx`
- `\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\SnowCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\RallyCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\DesertCar.ObjectInfo.Gbx`

Each car type uses a different force model function. The force model selector at `vehicle_model+0x1790` determines which function computes tire forces. Models 0-5 read forces from `vehicle+0x144C`; models 6+ read from `vehicle+0x1534`. Different cars also have different max speeds (read from `model+0x2F0`) and large blocks of tuning data at `model+0x30D8` and `model+0x31A8`.

---

## How wheels and suspension work

Each vehicle has 4 wheels (indices 0-3). Per-wheel state fields are exposed as named properties for telemetry/scripting.

### Wheel state structure

| Field | Example Address | Description |
|-------|-----------------|-------------|
| `Wheels.Elems[N].RotSpeed` | `0x141be7950` | Wheel rotational speed |
| `Wheels.Elems[N].DamperLength` | `0x141be7980` | Suspension damper extension length |
| `Wheels.Elems[N].SteerAngle` | `0x141be79b0` | Current steering angle |
| `Wheels.Elems[N].Rot` | `0x141be79e0` | Wheel rotation angle |
| `Wheels.Elems[N].TireWear01` | `0x141be7a08` | Tire wear factor (0.0 to 1.0) |
| `Wheels.Elems[N].BreakNormedCoef` | `0x141be7a40` | Brake force coefficient (normalized) |
| `Wheels.Elems[N].SlipCoef` | `0x141be7a70` | Wheel slip coefficient |
| `Wheels.Elems[N].Icing01` | `0x141be7aa0` | Ice coverage factor (0.0 to 1.0) |

### Wheel naming convention

Wheels follow a standard automotive convention:
- **FL** = Front Left, **FR** = Front Right, **RL** = Rear Left, **RR** = Rear Right

Each wheel has a static (`s`) and dynamic (`d`) representation:

```
WheelFLs / sFLWheel   (Front Left static)
WheelFLd / dFLWheel   (Front Left dynamic)
WheelFRs / sFRWheel   (Front Right static)
WheelFRd / dFRWheel   (Front Right dynamic)
WheelRLs / sRLWheel   (Rear Left static)
WheelRLd / dRLWheel   (Rear Left dynamic)
WheelRRs / sRRWheel   (Rear Right static)
WheelRRd / dRRWheel   (Rear Right dynamic)
```

### Suspension / damper model

The class `CPlugVehicleWheelPhyModel` (string at `0x141bd55e8`) defines the wheel physics model:

| String | Address | Notes |
|--------|---------|-------|
| `"Spring.FreqHz"` | `0x141bb3ec0` | Spring natural frequency in Hz |
| `"Spring.DampingRatio"` | `0x141bb3ed0` | Damping ratio (critical = 1.0) |
| `"Spring.Length"` | `0x141bb3ee8` | Spring rest length |
| `"DamperCompression"` | `0x141bd3b00` | Damper compression coefficient |
| `"DamperRestStateValue"` | `0x141bd3b50` | Rest state damper value |
| `"CollisionDamper"` | `0x141bb69a0` | Collision damper coefficient |
| `"CollisionBounce"` | `0x141bb68c8` | Bounce coefficient on collision |

The `SPlugVehiclePhyRestStateValues` structure (string at `0x141bd3b18`) stores the vehicle rest state.

`CPlugVehicleCarPhyShape` (string at `0x141bd5608`) defines the car's physical shape, including `"IsSteering"` (at `0x141bd5620`) which flags whether a wheel can steer.

### Reactor (jet) model

Four reactors are named `FLReactor`, `FRReactor`, `RLReactor`, `RRReactor` (at `0x141bd2cc8`-`0x141bd2cf8`). Each wheel position can have an associated thruster/reactor for "reactor" gameplay elements.

### Contact point processing

**Evidence**: `NSceneVehiclePhy__PhysicsStep_ProcessContactPoints.c:1-51`
**Confidence**: VERIFIED
**Address**: FUN_1407d2b90

Contact points are processed in two phases:

```c
// Phase 1: Process vehicle-world contacts (stride 0x58 = 88 bytes per contact)
if (*(uint *)(param_1 + 400) != 0) {
    for each contact at param_1 + 0x188 + i*0x58:
        FUN_1407cc640(param_1, contact_ptr);  // Process single contact
}
FUN_14010be60(param_1 + 0x188);  // Clear contact buffer

// Phase 2: Process vehicle-vehicle contacts (stride 0x58)
if (*(uint *)(param_1 + 0x1a0) != 0) {
    for each contact at *(param_1 + 0x198) + i*0x58:
        FUN_1407d41d0(*(contact + 0x38), param_1, tick*1000000);
}
// Clear all contact buffers:
FUN_14010be60(param_1 + 0x198);   // vehicle-vehicle contacts
FUN_14010be60(param_1 + 0x1b8);   // [UNKNOWN] buffer
FUN_14010be60(param_1 + 0x1c8);   // [UNKNOWN] buffer
FUN_14010be60(param_1 + 0x1d8);   // [UNKNOWN] buffer
FUN_14010be60(param_1 + 0x1a8);   // [UNKNOWN] buffer
```

At least 7 separate contact buffers exist (at offsets 0x188, 0x198, 0x1A8, 0x1B8, 0x1C8, 0x1D8, 0x1E8). This suggests categorized contact types: wheel-ground, body-body, body-wall, etc.

**Contact structure** (88 bytes / 0x58 stride):

| Offset | Type | Purpose |
|:---|:---:|:---|
| `+0x00` | varies | Contact point position |
| `+0x38` | ptr | Referenced object pointer (for vehicle-vehicle) |
| ... | | [UNKNOWN remaining fields] |

### Wheel contact history (circular buffer)

**Evidence**: `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c:159-192`
**Confidence**: VERIFIED

Each vehicle maintains a 20-entry circular buffer for wheel contact state tracking at `vehicle+0x1594`:

```c
// Quantize surface height to byte and store in circular buffer
fVar21 = (float)FUN_1407d5780(fVar21);
*(char *)((ulonglong)*puVar16 + 8 + (longlong)puVar16) = (char)(int)fVar21;

// Count state transitions in the buffer
uVar17 = puVar16[1];
cVar1 = buffer[writeIndex];
iVar9 = 0;
for (uVar11 = 1; uVar11 < uVar17; uVar11++) {
    uVar5 = (writeIndex - uVar11 + 0x14) % 0x14;  // wrap-around
    cVar2 = buffer[uVar5];
    if (cVar2 != cVar1) iVar9++;
    cVar1 = cVar2;
}
*(int *)(lVar19 + 0x15b0) = iVar9;  // ContactStateChangeCount
```

This detects rapid contact/airborne oscillation (a vehicle bouncing). The `ContactStateChangeCount` at `vehicle+0x15B0` affects game logic decisions like fragile surface checks.

### Vehicle-to-vehicle interaction (PairComputeForces)

**Evidence**: `NSceneVehiclePhy__PairComputeForces.c:1-93`
**Confidence**: VERIFIED
**Address**: FUN_140842ed0

When two vehicles collide, `PairComputeForces` prepares the two-body state:

1. Resolves both vehicle entities via `FUN_1407bea40`
2. Fetches velocity, position, and force data for BOTH vehicles
3. Initializes boost start time for both if needed
4. Copies current transform to previous for BOTH vehicles
5. Resets force accumulators for BOTH vehicles

This function does NOT compute forces itself. It prepares state for the dynamics solver to handle the collision response.

---

## How surface types and friction work

The surface system uses two independent ID schemes: one for physics (friction, sound, particles) and one for gameplay (turbo, reset, no-grip).

### The two-ID surface system

```
EPlugSurfaceMaterialId (physical)     EPlugSurfaceGameplayId (gameplay)
    |                                       |
    | Controls:                             | Controls:
    | - Friction coefficients               | - Turbo boost
    | - Sound effects                       | - Vehicle reset
    | - Particle type                       | - No-grip
    | - Skid marks                          | - Slow motion
    v                                       v
Per-wheel GroundContactMaterial        Block/item trigger zones
(updated per physics tick)             (applied on contact)
```

The material system exposes:
- `"SurfaceIds.PhysicId"` (at `0x141bba768`)
- `"SurfaceIds.GameplayId"` (at `0x141bba780`)
- `"MaterialPhysicsId"` (at `0x141cbb890`)
- `"MaterialPhysics_GameplayRemap"` (at `0x141cbb760`) -- mapping table from physics material to gameplay effect

### Surface gameplay effects

The `EPlugSurfaceGameplayId` enum values, in address order:

| Effect | Address | Description |
|--------|---------|-------------|
| `"NoSteering"` | `0x141be1238` | Disables steering |
| `"NoGrip"` | `0x141be1244` | Zero grip surface |
| `"Reset"` | `0x141be124c` | Resets vehicle |
| `"ForceAcceleration"` | `0x141be1258` | Forces acceleration |
| `"Turbo"` | `0x141be126c` | Turbo boost (level 1) |
| `"FreeWheeling"` | `0x141be1278` | Free-wheeling mode |
| `"Turbo2"` | `0x141be1288` | Turbo boost (level 2) |
| `"ReactorBoost2_Legacy"` | `0x141be1290` | Legacy reactor boost level 2 |
| `"Fragile"` | `0x141be12a8` | Fragile (crash) surface |
| `"NoBrakes"` | `0x141be12b0` | Disables braking |
| `"Bouncy"` | `0x141be12bc` | Bouncy surface |
| `"Bumper"` | `0x141be12c4` | Bumper surface |
| `"SlowMotion"` | `0x141be12d0` | Slow motion effect |
| `"ReactorBoost_Legacy"` | `0x141be12e0` | Legacy reactor boost |
| `"Bumper2"` | `0x141be12f8` | Bumper level 2 |
| `"VehicleTransform_CarRally"` | `0x141be1300` | Transform to Rally |
| `"VehicleTransform_CarSnow"` | `0x141be1320` | Transform to Snow |
| `"VehicleTransform_CarDesert"` | `0x141be1358` | Transform to Desert |
| `"ReactorBoost_Oriented"` | `0x141be1378` | Oriented reactor boost |
| `"Cruise"` | `0x141be1390` | Cruise control surface |
| `"VehicleTransform_Reset"` | `0x141be1398` | Transform back to Stadium |
| `"ReactorBoost2_Oriented"` | `0x141be13b0` | Oriented reactor boost level 2 |

Deprecated effect names (e.g., `Turbo_Deprecated`, `TurboTechMagnetic_Deprecated`, `FreeWheelingWood_Deprecated`) suggest these effects were surface-specific in older versions and have since been unified.

### Known surface material names

- `"Stadium\Media\Material_BlockCustom\CustomConcrete"` (`0x141ce4b48`)
- `"Stadium\Media\Material_BlockCustom\CustomDirt"` (`0x141ce4b80`)
- `"Stadium\Media\Material_BlockCustom\CustomGrass"` (`0x141ce4be0`)
- `"Stadium\Media\Material_BlockCustom\CustomPlasticShiny"` (`0x141ce4d10`)
- `"Stadium\Media\Material_BlockCustom\CustomRoughWood"` (`0x141ce4d78`)
- `"DecalOnRoadIce"` (`0x141ce4c40`)

### Friction configuration

| String | Address | Function Ref | Notes |
|--------|---------|--------------|-------|
| `"FrictionDynaIterCount"` | `0x141bed9e8` | `FUN_1407f3fc0` | Dynamic friction solver iteration count |
| `"FrictionStaticIterCount"` | `0x141beda38` | `FUN_1407f3fc0` | Static friction solver iteration count |
| `"Tunings.CoefFriction"` | `0x141cb72c8` | `FUN_141071b20` | Friction tuning coefficient |
| `"Tunings.CoefAcceleration"` | `0x141cb72a8` | `FUN_141071b20` | Acceleration tuning coefficient |
| `"Tunings.Sensibility"` | [decompiled] | `FUN_141071b20` | [UNKNOWN] Sensibility tuning |

The separate dynamic vs static iteration counts suggest an iterative Gauss-Seidel-style contact solver with different convergence requirements for static and dynamic friction.

Tuning coefficients are registered in `NGameSlotPhy::SMgr`:
- `Tunings.CoefFriction` at struct offset `0x58`
- `Tunings.CoefAcceleration` at struct offset `0x5C`
- `Tunings.Sensibility` at struct offset `0x60`

### Friction solver configuration

**Evidence**: `FrictionIterCount_Config.c:1-105`
**Confidence**: VERIFIED
**Address**: FUN_1407f3fc0

The `NSceneDyna::SSolverParams` struct (0x2C = 44 bytes):

| Struct Offset | Type | Name | Description |
|:---:|:---:|:---|:---|
| `0x00` | int | `FrictionStaticIterCount` | Static friction solver iterations |
| `0x04` | int | `FrictionDynaIterCount` | Dynamic friction solver iterations |
| `0x08` | int | `VelocityIterCount` | Velocity solver iterations |
| `0x0C` | int | `PositionIterCount` | Position correction iterations |
| `0x10` | float | `DepenImpulseFactor` | Depenetration impulse scaling factor |
| `0x14` | float | `MaxDepenVel` | Maximum depenetration velocity |
| `0x18` | bool | `EnablePositionConstraint` | Whether position correction is active |
| `0x1C` | float | `AllowedPen` | Allowed penetration depth (auto if negative) |
| `0x20` | int | `VelBiasMode` | Velocity bias computation mode |
| `0x24` | bool | `UseConstraints2` | Whether to use second-generation constraints |
| `0x28` | float | `MinVelocityForRestitution` | Minimum velocity to apply restitution |

This is a sequential impulse / Gauss-Seidel constraint solver with separate iteration counts for static friction, dynamic friction, velocity, and position.

### Surface expressions

Surface effects can be driven by runtime expressions:
- `"Surface_SkidSpeedKmhExpr"` (`0x141bd6d30`)
- `"Surface_SkidIntensityExpr"` (`0x141bd6d50`)
- `"Surface_SpeedKmhExpr"` (`0x141bd6dd0`)
- `"Surface_SurfaceIdExpr"` (`0x141bd6de8`)

---

## How collision detection works (NHmsCollision)

The collision system follows a broad-phase / narrow-phase architecture under the `NHmsCollision` namespace.

### Core functions

| Function Label | Address | Size | Callers | Notes |
|----------------|---------|------|---------|-------|
| `NHmsCollision::StartPhyFrame` | `0x1402a9c60` | 297 B | 1 | Begin-of-frame setup |
| `NHmsCollision::UpdateStatic` | `0x1402a6da0` | 360 B | 11 | Update static collision world |
| `NHmsCollision::UpdateDiscrete` | `0x1402a6960` | 114 B | 7 | Discrete collision detection |
| `NHmsCollision::UpdateContinuous` | `0x1402a6360` | 328 B | 3 | Continuous collision detection (CCD) |
| `NHmsCollision::MergeContacts` | `0x1402a8a70` | 1717 B | 1 | Merge/resolve contact points |
| `NHmsCollision::ComputePenetrations` | [UNKNOWN] | [UNKNOWN] | [UNKNOWN] | Penetration depth calculation |

### Collision modes

Three collision update modes:
1. **Static** (`UpdateStatic`) -- Non-moving world geometry (blocks, terrain). Called from 11 contexts.
2. **Discrete** (`UpdateDiscrete`) -- Standard per-tick collision for dynamic objects.
3. **Continuous** (`UpdateContinuous`) -- CCD (Continuous Collision Detection) for fast-moving objects to prevent tunneling.

### Frame initialization (StartPhyFrame)

**Evidence**: `NHmsCollision__StartPhyFrame.c:1-57`
**Confidence**: VERIFIED

```c
// 1. Update static collision world if needed
if (*(int *)(param_1 + 0x28) != 0) {
    FUN_1402a6da0(param_1);   // NHmsCollision::UpdateStatic
}

// 2. Reset acceleration structure
FUN_1402a9880(param_1 + 0x1e0);

// 3. Process dynamic collision items (set 1: offset 0x9C8)
for each item in set at param_1 + 0x9C8:
    // Copy current position to previous position
    *(item + 0x94) = *(item + 0x74);  // prev_x = cur_x
    *(item + 0x98) = *(item + 0x78);  // prev_y = cur_y
    *(item + 0x9C) = *(item + 0x7C);  // prev_z = cur_z
    FUN_140194860();                    // Reset collision state
    *(item + 0xA4) = 0xFFFFFFFF;        // Reset hit body index

// 4. Process dynamic collision items (set 2: offset 0xA58)
for each item in set at param_1 + 0xA58:
    // Same position copy pattern
```

Each collidable item has:
- `+0x74`: Current position (vec3)
- `+0x94`: Previous position (vec3, copied from current at frame start)
- `+0xA4`: Hit body index (uint, 0xFFFFFFFF = no hit)

Two collision item sets exist at offsets `+0x9C8` and `+0xA58`, separating static-collidable and dynamic-collidable objects.

### Dynamic collision cache

**Evidence**: `NSceneDyna__DynamicCollisionCreateCache.c:1-88`
**Confidence**: VERIFIED

Cache entry layout (56 bytes / 0x38 stride):

| Offset | Size | Purpose |
|:---:|:---:|:---|
| 0x00-0x0F | 16 | AABB / position data |
| 0x10-0x1F | 16 | Impulse accumulators (zeroed each frame) |
| 0x20 | 4 | Collision layer mask (filtered) |
| 0x24 | 4 | Collision layer bit |
| 0x28 | 4 | Collision property |
| 0x2C | 4 | Body reference index |
| 0x30 | 1 | Collision type byte |
| 0x31 | 1 | Flags (sleep | kinematic) |

The global table at `DAT_141fabc20` maps collision type bytes (0x00-0xFF) to layer masks. The actual mask is `layer_table[type] & ~body_exclusion_mask`.

### Contact merging algorithm

**Evidence**: `NHmsCollision__MergeContacts.c:1-271`
**Confidence**: VERIFIED

The algorithm reduces redundant contact points to improve solver stability:

```
Phase 1: Find merge candidates
    For each contact pair (i, j) where j > i:
        if dist > param_3: skip
        if dot(normal_i, normal_j) < param_2: skip
        if type_i == 1 OR type_j == 1: skip
        Add to merge group

Phase 2: Execute merges
    For each merge group:
        survivor = last contact in group
        avg_position += contact.position
        avg_normal += contact.normal
        avg_impulse += contact.impulse
        Normalize averaged normal
        Write merged result to survivor contact

Phase 3: Remove consumed contacts
    Sort indices of consumed contacts
    Remove from contact array in reverse order
```

### Raycasting / query functions

| Function Label | Notes |
|----------------|-------|
| `NHmsCollision::PointCast_FirstClip` | Raycast returning first hit |
| `NHmsCollision::PointCast_AllClips` | Raycast returning all hits |
| `NHmsCollision::MultiPointCast_FirstClip` | Multi-ray first hit |
| `NHmsCollision::MultiPointCast_AllClips` | Multi-ray all hits |
| `NHmsCollision::SurfCast_FirstClip` | Surface-cast first hit |
| `NHmsCollision::SurfCast_AllClips` | Surface-cast all hits |
| `NHmsCollision::OverlapAABB` | AABB overlap test |
| `NHmsCollision::OverlapAABBSegment` | AABB-segment overlap |
| `NHmsCollision::ComputeMinDistFromSegment_MinOnly` | Minimum distance from segment |
| `NHmsCollision::SurfInterDiscrete` | Discrete surface intersection |

`NHmsCollision::BuildDiscreteItems_AccelStructure` and `NHmsCollision::ProgressiveTreeBuild_PrepareInput` suggest a tree-based spatial acceleration structure (likely BVH or k-d tree) for broadphase collision queries.

### Collision in dynamics

- `NSceneDyna::DynamicCollisionCreateCache` (`FUN_1407f9da0`) -- Pre-allocates collision cache
- `NSceneDyna::Dynas_StaticCollisionDetection` (`FUN_1407fc730`) -- Runs static collision for dynamic objects
- `NSceneDyna::Dyna_GetItemsForStaticCollision` (`FUN_1407fc3c0`) -- Gathers items for collision
- `NSceneDyna::BroadPhase_BruteForce` -- Brute-force broadphase fallback

---

## How gravity and sleep detection work

Gravity is not hardcoded to 9.81. It is passed as a parameter vector, enabling the `GravityCoef` modifier.

**Evidence**: `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c:1-103`
**Confidence**: VERIFIED

### Gravity computation

```c
// param_8 = gravity direction vector (x, y, z)
// fVar8 = mass * deltaTime
fVar7 = fVar8 * param_8[0] + accumulated_force.x;  // gravity_x
fVar10 = fVar8 * param_8[1] + accumulated_force.y;  // gravity_y
fVar9 = fVar8 * param_8[2] + accumulated_force.z;  // gravity_z

// Apply to linear velocity
pfVar2[-1] = fVar10 * fVar8_dt + pfVar2[-1];  // vel.y += force.y * dt
pfVar2[-2] = fVar7 * fVar8_dt + pfVar2[-2];   // vel.x += force.x * dt
*pfVar2 = fVar9 * fVar8_dt + *pfVar2;          // vel.z += force.z * dt

// Apply angular velocity similarly
pfVar2[1] = angular_force.x * angular_mass.x * param_9 + pfVar2[1];
pfVar2[2] = angular_force.y * angular_mass.y * param_9 + pfVar2[2];
pfVar2[3] = angular_force.z * angular_mass.z * param_9 + pfVar2[3];
```

A scan of `.rdata` and `.data` for `9.81` found **zero matches**. The gravity constant is stored in loaded `.Gbx` resource files or in the protected sections (`.A2U`/`.D."`).

### Sleep detection

Bodies with velocities below a threshold are gradually damped:

```
for each body:
    if (body_flags & 2) == 0:  // not kinematic/static
        if DAT_141ebccfc != 0:  // sleep enabled
            if linear_speed_sq < DAT_141ebcd04^2:
                vx *= DAT_141ebcd00   // damp
                vy *= DAT_141ebcd00
                vz *= DAT_141ebcd00
            if angular_speed_sq < DAT_141ebcd04^2:
                wx *= DAT_141ebcd00
                wy *= DAT_141ebcd00
                wz *= DAT_141ebcd00
```

Sleep detection does NOT immediately zero velocity. It applies gradual damping over multiple frames.

| Global | Purpose | Type |
|:---|:---|:---:|
| `DAT_141ebccfc` | Sleep detection enabled flag | int |
| `DAT_141ebcd00` | Sleep velocity damping factor | float |
| `DAT_141ebcd04` | Sleep velocity threshold (linear m/s; squared before comparison) | float |

### Force field system

`NPlugDyna::SForceFieldModel` (at `0x141bb3e60`) and `NPlugDyna::EForceFieldType` (at `0x141bb3e80`) indicate a force field system. `CSmArenaPhysics::ComputeForceFieldAction` (at `0x141cea540`) applies force field effects in the arena.

---

## How water physics works

Water force computation uses a two-tier lookup: per-body custom water zones and a global fallback.

**Evidence**: `NSceneDyna__ComputeWaterForces.c:1-53`
**Confidence**: VERIFIED

```c
if (param_8 != 0) {
    for each body:
        if (body_flags & 2) == 0:  // not kinematic
            lVar1 = *(*(body_pair_array + body_index) + 0x60);
            if (lVar1 != 0 && lVar1 + 0x18 != 0):
                if (*(lVar1 + 0x128) == 0):
                    lVar3 = *(*param_2 + 0x48);   // global water shape
                else:
                    lVar3 = *(*(lVar1 + 0x128) + 0x38); // per-body water
                if (lVar3 != 0):
                    FUN_1407fb580(..., lVar1 + 0x18, lVar3, param_8, 0);
}
```

The function takes the body's collision shape and the water shape. This strongly suggests submerged volume computation for buoyancy.

From the Openplanet data, `WaterImmersionCoef` (0-1) tracks how submerged the car is. The `FallingState` enum includes `FallingWater` (2) and `RestingWater` (6). TMNF cross-reference mentions `WaterReboundMinHSpeed = 55.556 m/s` (200 km/h), suggesting cars can skip across water at sufficient speed.

---

## How determinism works in the physics engine

TM2020's replay system records inputs, not positions. The engine re-runs physics with recorded inputs. Several mechanisms ensure deterministic results.

### Fixed timestep (integer-based)

**Confidence**: VERIFIED

```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = integer
```

Time is tracked as integer tick counts. No `+= deltaTime` float accumulation. Every tick has exactly the same duration.

### Deterministic sub-stepping

Given the same velocity state, the sub-step formula produces the same count. All four velocity magnitudes use the same `x*x + y*y + z*z -> SQRT()` pattern. The clamping to 1000 is exact integer comparison.

### Remainder-step precision

The sub-step loop runs `N-1` equal steps, then one final step with the remainder. Total simulated time equals `dt` exactly.

### Guarded square root

Every square root is guarded against negative inputs:

```c
if (fVar24 < 0.0) {
    fVar24 = (float)FUN_14195dd00(fVar24);  // safe sqrt for negative inputs
} else {
    fVar24 = SQRT(fVar24);  // SSE sqrtss
}
```

This prevents NaN propagation from floating-point precision artifacts.

### Sequential processing order

Bodies and vehicles are processed in array order (sequential iteration):

```c
do {
    uVar2 = *(uint *)(param_1[0x16] + (ulonglong)*puVar12 * 4);
    puVar12 = puVar12 + 1;
} while (uVar11 < uVar1);
```

No parallel dispatch, no random ordering. Collision pair processing is deterministic regardless of memory allocation order.

### SSE floating point on x64

TM2020 uses SSE for all floating-point operations. SSE `sqrtss`, `addss`, `mulss` are IEEE 754 compliant and produce identical results on the same CPU architecture.

**WARNING**: This guarantees determinism **within the same platform** (PC x64). Cross-platform determinism is NOT guaranteed by code patterns alone.

---

## How the fragile surface check works

**Evidence**: `PhysicsStep_TM.c:191-195`
**Confidence**: VERIFIED

The car breaks on a fragile surface when ALL THREE conditions are met:

```c
if ((((*(uint *)(lVar9 + 0x1c7c) & 0x1800) == 0x1800) &&       // Condition 1
    (DAT_141d1ef7c < *(float *)(lVar9 + 0x1c8c))) &&            // Condition 2
   (1 < (*(uint *)(lVar9 + 0x128c) & 0xf) - 2)) {              // Condition 3
    FUN_1407d2870(param_1, lVar9, *param_4);                      // BREAK!
}
```

**Condition 1**: Bits 11 AND 12 of `ContactPhyFlags` (`vehicle+0x1C7C`) must BOTH be set (mask 0x1800).

**Condition 2**: `ContactThreshold` (`vehicle+0x1C8C`, a float) must exceed the global threshold `DAT_141d1ef7c`. This is a collision severity metric -- gentle landings pass, hard impacts fail.

**Condition 3**: The status nibble (`vehicle+0x128C & 0xF`) must NOT be 2 or 3. Unsigned arithmetic: `(0 - 2) = 0xFFFFFFFE`, so `1 < 0xFFFFFFFE` is true. Nibble values 0, 1, and 4+ all pass.

---

## What the wall/loop adhesion physics look like

There is **no special "sticky" force** in the decompiled dispatcher-level code. Wall/loop adhesion emerges from the interaction of multiple systems.

1. **Exaggerated gravity**: TMNF's `GravityCoef = 3.0` multiplies base gravity by 3x (~29.43 m/s^2). TM2020 exposes `GravityCoef` via ManiaScript.

2. **Contact normals direct forces**: Wheel contact normals point away from the surface. The friction solver resolves constraints along these normals, pressing the car to the surface.

3. **Centripetal force from speed**: At sufficient speed, the car's velocity around a loop generates centripetal force pushing it into the surface.

4. **Speed threshold for falling off**: No explicit "minimum speed for wall riding" constant exists. The car falls when gravity exceeds centripetal force plus tire friction. This is emergent.

The actual per-wheel force model functions (FUN_140851f00 for CarSport, etc.) are NOT decompiled. The force computation that makes wall-riding work is inside those un-decompiled functions.

---

## Complete vehicle state structure

**Evidence**: All 18 decompiled files, aggregated
**Confidence**: VERIFIED for offsets observed in code; [UNKNOWN] for gaps

| Offset | Size | Type | Field Name | Evidence / Source |
|:---|:---:|:---:|:---|:---|
| `+0x10` | 4 | int | `DynaBodyId` | ComputeForces: compared to -1 |
| `+0x50` | 8 | ptr | `CollisionObjectAlt` | BeforeMgrDynaUpdate |
| `+0x80` | 8 | ptr | `CollisionObject` | BeforeMgrDynaUpdate |
| `+0x88` | 8 | ptr | `PhyModelPtr` | ComputeForces, PhysicsStep_TM |
| `+0x90` | 112 | mat4x3+ | `CurrentTransform[0-16]` | PhysicsStep_TM |
| `+0x104` | 112 | mat4x3 | `PreviousTransform` | PhysicsStep_TM: copied from +0x90 |
| `+0x194` | 4 | int | `ResetFlag` | BeforeMgrDynaUpdate |
| `+0x4E8` | varies | struct | `WheelVisStateBase` | ExtractVisStates |
| `+0x848` | varies | struct | `WheelVisStateAlt` | ExtractVisStates |
| `+0x9C` | 4 | f32 | `SurfaceHeightOrParam` | BeforeMgrDynaUpdate |
| `+0x1280` | 4 | uint | `VehicleUniqueId` | Multiple: used as identifier |
| `+0x1284` | 4 | int | `PairId / TeamId` | BeforeMgrDynaUpdate |
| `+0x128C` | 4 | uint | `StatusFlags` | Multiple: low nibble = state enum |
| `+0x12C8` | 4 | int | `NegatedSomething` | ArenaPhysics_CarPhyUpdate |
| `+0x12D8` | varies | struct | `ContactData` | BeforeMgrDynaUpdate |
| `+0x12DC` | 4 | uint | `TickStamp` | BeforeMgrDynaUpdate: 0xFFFFFFFF = unset |
| `+0x12E0` | 48+ | mat3x4 | `TransformData` | BeforeMgrDynaUpdate |
| `+0x12F0` | varies | struct | `MatchData` | ArenaPhysics_CarPhyUpdate |
| `+0x1314` | varies | struct | `IntermediateTransform` | BeforeMgrDynaUpdate |
| `+0x1338` | 4 | uint | `Param` | BeforeMgrDynaUpdate |
| `+0x1348` | 12 | vec3 | `VelocityVec1` | PhysicsStep_TM: sub-step magnitude |
| `+0x1354` | 12 | vec3 | `VelocityVec2` | PhysicsStep_TM: sub-step magnitude |
| `+0x1408` | 4 | int | `ForceAccumFlag` | ComputeForces, PairComputeForces: zeroed |
| `+0x144C` | 12 | vec3 | `ForceAccum_Model0to5` | ComputeForces: models < 6 |
| `+0x1534` | 12 | vec3 | `ForceAccum_Model6plus` | ComputeForces: models >= 6 |
| `+0x156C` | 4 | int | `SlipCounter` | ComputeForces, PairComputeForces: zeroed |
| `+0x1570` | 8 | f64/2xf32 | `InitialVelocity_XY` | ComputeForces: set to zero |
| `+0x1578` | 4 | f32 | `InitialVelocity_Z` | ComputeForces: set to zero |
| `+0x1584` | 8 | f64/2xf32 | `ResetForce` | ComputeForces: zeroed on state 1 reset |
| `+0x1594` | varies | circular buf | `WheelContactHistory` | BeforeMgrDynaUpdate: ring buffer |
| `+0x15B0` | 4 | int | `ContactStateChangeCount` | BeforeMgrDynaUpdate |
| `+0x175C` | 4 | f32 | `CustomForceParam` | ComputeForces: if != 0.0, applies custom force |
| `+0x1790` | 4 | int | `ForceModelType` | ComputeForces: switch case 0-6, 0xB |
| `+0x17B0-0x19F0` | 4x184 | struct[4] | `WheelStateBlocks` | ComputeForces: stride 0xB8 |
| `+0x1AF8` | 4 | uint | `PrevBoostState` | ComputeForces: prev = current(5000) |
| `+0x1388` | 4 | uint | `CurrentBoostState` | ComputeForces: zeroed after copy |
| `+0x16E0` | 4 | uint | `BoostDuration` | ComputeForces: checked != 0 |
| `+0x16E4` | 4 | f32 | `BoostStrength` | ComputeForces: multiplied into force |
| `+0x16E8` | 4 | uint | `BoostStartTime` | ComputeForces: -1 = no boost |
| `+0x1BB0` | 8 | ptr | `VehicleModelPtr` | Multiple |
| `+0x1BB8` | 8 | ptr | `AuxPhysicsPtr` | BeforeMgrDynaUpdate |
| `+0x1BC0` | 1 | byte | `PhyFlags` | BeforeMgrDynaUpdate: bit 0 checked |
| `+0x1BC8` | 8 | ptr | `ContactProcessorPtr` | BeforeMgrDynaUpdate |
| `+0x1BD8` | 4 | int | `ClearForce1` | ComputeForces: zeroed |
| `+0x1BDC` | 8 | f64/2xf32 | `ClearForce2` | ComputeForces: zeroed |
| `+0x1BF0` | 4 | uint | `ArenaZoneId` | ArenaPhysics_CarPhyUpdate |
| `+0x1C78` | 1 | char | `PlayerIndex` | BeforeMgrDynaUpdate: -1 = no player |
| `+0x1C7C` | 4 | uint | `ContactPhyFlags` | Multiple: complex bitfield |
| `+0x1C8C` | 4 | f32 | `ContactThreshold` | PhysicsStep_TM: compared to `DAT_141d1ef7c` |
| `+0x1C90` | 4 | int | `SimulationMode` | 0=normal, 1=replay, 2=spectator, 3=normal-alt |
| `+0x1C98` | 8 | ptr | `ReplayDataPtr` | BeforeMgrDynaUpdate: memcpy source |

**Total estimated struct size**: at least **0x1CA0** (~7,328 bytes).

### ContactPhyFlags bitfield (+0x1C7C)

**Confidence**: VERIFIED for bit positions, PLAUSIBLE for meanings

```
Bit 0   (0x01): [UNKNOWN]
Bit 1   (0x02): [UNKNOWN]
Bit 2   (0x04): DisableEvents -- prevents event dispatching
Bit 3   (0x08): HasContactThisTick -- set in ArenaPhysics_CarPhyUpdate
Bit 4   (0x10): SubStepCollisionDetected -- checked in BeforeMgrDynaUpdate
Bits 5-7 (0xE0): ContactType -- cleared with mask 0xFFFFE1F
Bits 9-10 (0x600): Cleared with mask 0xFFFFF5FF in PhysicsStep_TM
Bit 11  (0x800): Part of fragile check (with bit 12)
Bit 12  (0x1000): Part of fragile check (with bit 11)
Bit 16  (0x10000): SubStepCollisionResult -- set from FUN_141501090 return
```

### StatusFlags low nibble (+0x128C & 0xF)

| Value | State | Behavior |
|:---:|:---|:---|
| 0 | Active/Ready | Normal physics |
| 1 | Reset/Inactive | Forces zeroed, visual interpolation = 0 |
| 2 | Excluded | Skipped entirely in PhysicsStep_TM |
| 3 | [UNKNOWN] | Checked as `(nibble - 2) < 2` in BeforeMgrDynaUpdate |

### Vehicle model structure (via vehicle+0x88)

| Offset | Type | Field | Evidence |
|:---|:---:|:---|:---|
| `+0x238` | int | GameModeOrClass | ComputeForces: `*(int *)(local_118 + 0x238) - 5U` |
| `+0x1790` | int | ForceModelType | ComputeForces: switch dispatch |
| `+0x2F0` | f32 | MaxSpeed | ComputeForces: speed clamping |
| `+0x30D8` | varies | [UNKNOWN] | ComputeForces: tuning data block 1 |
| `+0x31A8` | varies | [UNKNOWN] | ComputeForces: tuning data block 2 |

### Vehicle model class (via vehicle+0x1BB0)

| Offset | Type | Field | Evidence |
|:---|:---:|:---|:---|
| `+0x278` | f32 | TimeOrStateParam | ComputeForces: `*pfVar1 <= 0.0 && *pfVar1 != 0.0` check |
| `+0x2B0` | ptr | TransformVtablePtr | PhysicsStep_TM: virtual call |
| `+0xE0` | f32 | ModelScale | ComputeForces: multiplied into boost force |

### Transform copy pattern

All physics functions contain identical transform copy code: 112 bytes from `+0x90` to `+0x104`. This preserves the last frame's position for interpolation and collision backtracking.

---

## How the dynamics engine works (NSceneDyna)

NSceneDyna is the rigid body dynamics engine (a namespace for gravity, forces, collision response, velocity integration).

### Key functions

| Function Label | Address | Size | Notes |
|----------------|---------|------|-------|
| `NSceneDyna::PhysicsStep` | `0x1407bd0e0` | 126 B | Thin wrapper calling PhysicsStep_V2 |
| `NSceneDyna::PhysicsStep_V2` | `0x140803920` | 1351 B | Main physics step orchestrator |
| `NSceneDyna::InternalPhysicsStep` | `0x1408025a0` | 4991 B | Core integration/solver loop |
| `NSceneDyna::ComputeGravityAndSleepStateAndNewVels` | `0x1407f89d0` | 790 B | Gravity + sleep + velocity integration |
| `NSceneDyna::ComputeExternalForces` | `0x1407f81c0` | 202 B | External force accumulation |
| `NSceneDyna::ComputeWaterForces` | `0x1407f8290` | 370 B | Buoyancy/water forces |
| `NSceneDyna::DynamicCollisionCreateCache` | `0x1407f9da0` | 472 B | Collision cache creation |
| `NSceneDyna::Dynas_StaticCollisionDetection` | `0x1407fc730` | 180 B | Static collision dispatch |
| `NSceneDyna::Dyna_GetItemsForStaticCollision` | `0x1407fc3c0` | 318 B | Gather items for collision |

---

## How the vehicle physics model classes are organized

```
CPlugVehiclePhyModelCustom          (0x141bd5b48) -- Custom vehicle physics
  |
  +-- CPlugVehicleWheelPhyModel     (0x141bd55e8) -- Wheel physics model
  +-- CPlugVehicleCarPhyShape       (0x141bd5608) -- Car collision shape
  +-- CPlugVehicleGearBox           (0x141bcea70) -- Gearbox model
  +-- SPlugVehiclePhyRestStateValues(0x141bd3b18) -- Rest state
  +-- SPlugVehicleOccupantSpawn     (0x141bd5630) -- Occupant spawn point
  +-- SPlugVehicleOccupantSlot      (0x141bd5650) -- Occupant slot
```

### Runtime managers

| Class / Namespace | String Address | Notes |
|-------------------|----------------|-------|
| `NGameVehiclePhy::SMgr` | `0x141cb7248` | Game-level vehicle physics manager |
| `CGameVehiclePhy` | `0x141cb7260` | Game vehicle physics wrapper |
| `NSceneVehicleVis::SMgr` | `0x141be7e98` | Visual state manager |
| `NGameSlotPhy::SMgr` | (decompiled) | Per-slot physics manager (holds tuning coefficients) |

### Vehicle visual state

The visual system (`NSceneVehicleVis`) operates separately from physics:

| Function Label | Notes |
|----------------|-------|
| `NSceneVehicleVis::ModelRelease` | Release visual model |
| `NSceneVehicleVis::ModelQuery` | Query visual model |
| `NSceneVehicleVis::Update1_AfterRadialLod` | LOD-based update |
| `NSceneVehicleVis::UpdateAsync_PostCameraVisibility` | Post-camera visibility update |
| `NSceneVehicleVis::Update2_AfterAnim` | Post-animation update |

---

## How input flows to physics

| Input Name | Address | Notes |
|------------|---------|-------|
| `"InputSteer"` | `0x141be7878` | Steering input value |
| `"InputBrakePedal"` | `0x141be7888` | Brake pedal input |
| `"AccelInput"` | `0x141ce46f0` | Acceleration input |
| `"SteerValue"` | `0x141cf3358` | Steering value (scripting) |
| `"BrakeValue"` | `0x141cf3348` | Brake value (scripting) |

### Physics modifiers (delayed application)

All modifiers apply with a 250ms delay:

| Modifier | Address | Range | Notes |
|----------|---------|-------|-------|
| `"AccelCoef"` | `0x141bd35b8` | 0.0 - 1.0 | Acceleration coefficient |
| `"AdherenceCoef"` | `0x141bd35d8` | 0.0 - 1.0 | Grip/adherence coefficient |
| `"GravityCoef"` | `0x141bb3e18` | 0.0 - 1.0 | Gravity coefficient |
| `"TireWear"` | `0x141bd35c8` | 0.0 - 1.0 | Tire wear level |
| `"MaxSpeedValue"` | `0x141bd35e8` | [UNKNOWN] | Maximum speed |
| `"CruiseSpeedValue"` | `0x141bd35f8` | [UNKNOWN] | Cruise control speed |
| `"ControlCoef"` | [via deprecation msg] | 0.0 - 1.0 | Control responsiveness |

`GravityCoef`, `AdherenceCoef`, `AccelCoef`, and `ControlCoef` are deprecated in favor of `SetPlayer_Delayed_AccelCoef`.

### Gameplay handicaps

- `"HandicapNoGripDuration"` (`0x141cf6970`)
- `"HandicapNoSteeringDuration"` (`0x141cf6950`)
- `"HandicapNoBrakesDuration"` (`0x141cf6a98`)

---

## How the kinematic constraint system works (NPlugDyna)

The `NPlugDyna` namespace defines a constraint system for animated/kinematic objects:

| Type | String Address | Notes |
|------|----------------|-------|
| `NPlugDyna::SKinematicConstraint` | `0x141bb4188` | Kinematic constraint definition |
| `NPlugDyna::SConstraintModel` | `0x141bb3ef8` | General constraint model |
| `NPlugDyna::EDynaConstraintType` | `0x141bb3ea0` | Constraint type enum |
| `NPlugDyna::SForceFieldModel` | `0x141bb3e60` | Force field definition |
| `NPlugDyna::EForceFieldType` | `0x141bb3e80` | Force field type enum |
| `NPlugDyna::SAnimFunc01Base` | `0x141bb4050` | Animation function base (0-1 range) |
| `NPlugDyna::SAnimFunc01` | `0x141bb40b8` | Animation function (0-1 range) |
| `NPlugDyna::SAnimFuncNat` | `0x141bb4110` | Natural animation function |
| `NPlugDyna::EAxis` | `0x141bb4070` | Axis enum (X/Y/Z) |
| `NPlugDyna::EAnimFuncBase` | `0x141bb4088` | Animation function type enum |
| `NPlugDyna::SPrefabConstraintParams` | `0x141bb4240` | Prefab constraint parameters |
| `NPlugDynaObjectModel::SInstanceParams` | `0x141bd5e10` | Per-instance parameters |

The `AngularSpeedClamp` string at `0x141bb3fe0` suggests angular velocity limits on constrained objects.

---

## How the audio motor simulation ties to physics

The engine sound system is coupled to physics state:

| String | Address | Notes |
|--------|---------|-------|
| `"EngineRpm"` | `0x141bea4b8` | Engine RPM value |
| `"EngineOn"` | `0x141be7dc8` | Engine on/off state |
| `"AudioMotors_Engine_Throttle"` | `0x141bcdab8` | Throttle audio parameter |
| `"AudioMotors_Engine_Release"` | `0x141bcdad8` | Engine release audio |
| `"AudioMotors_IdleLoop_Engine"` | `0x141bcdbf8` | Idle loop sound |
| `"AudioMotors_LimiterLoop_Engine"` | `0x141bcdc18` | Rev limiter sound |
| `"RpmMaxFromEngine"` | `0x141bcdcd0` | Max RPM from engine model |

The gearbox class `CPlugVehicleGearBox` at `0x141bcea70` feeds gear ratios and shift logic into the RPM calculation. From Openplanet data, `CurGear` ranges 0-7 (8 gears) and `RPM` ranges 0-11000.

RPM IS simulated (not cosmetic). In TMNF's M6 model, RPM determines gear shifts, engine torque output, and burnout state machine entry.

---

## What the vehicle contact / event system tracks

### Vehicle events

| Event | Address | Notes |
|-------|---------|-------|
| `"ImpactWheelFront"` | `0x141be7590` | Front wheel impact |
| `"ImpactWheelBack"` | `0x141be75c8` | Rear wheel impact |
| `"BeginFreeWheeling"` | `0x141be75b0` | Start free-wheeling |
| `"EndFreeWheeling"` | `0x141be7650` | End free-wheeling |
| `"BeginBoost_1"` | `0x141be76e0` | Boost level 1 start |
| `"BeginBoost_2"` | `0x141be76f0` | Boost level 2 start |
| `"EndBoost"` | `0x141be76d0` | Boost end |
| `"BeginNoGrip"` | `0x141be7610` | No-grip start |
| `"EndNoGrip"` | `0x141be7600` | No-grip end |
| `"BeginBulletTime"` | `0x141be7630` | Bullet time start |
| `"EndBulletTime"` | `0x141be7620` | Bullet time end |
| `"OnVehicleCollision"` | `0x141cf2020` | Vehicle collision callback |
| `"OnVehicleVsVehicleCollision"` | `0x141cf2038` | Vehicle-vs-vehicle collision |

### Contact counts

- `"WheelsContactCount"` (`0x141cf6768`) -- Number of wheels in contact with ground
- `"WheelsSkiddingCount"` (`0x141cf6ab8`) -- Number of wheels skidding
- `"IsWheelsBurning"` (`0x141be78b8`) -- Burnout state

### Tire marks

`CSceneVehicleCarMarksModel` (`0x141becc18`) drives tire mark visuals. Mark parameters include `"WidthCoefForceZ"`, `"WidthCoefForceX"`, `"AlphaCoefForceZ"`, `"AlphaCoefForceX"` -- tire marks are modulated by force magnitude.

---

## Differences from TMNF

| Feature | TMNF | TM2020 |
|:---|:---|:---|
| Force model count | 4 (cases 3,4,5,default) | 7 (cases 0-2,3,4,5,6,0xB) |
| Max sub-steps | 10,000 | 1,000 |
| Velocity inputs for sub-step calc | 2 (linear + angular) | 4 (linear + 3 angular) |
| Vehicle state struct size | ~2,112 bytes | ~7,328 bytes |
| Architecture | x86 (32-bit, x87 FPU) | x64 (64-bit, SSE) |
| Time conversion | `tick * 0.001` (ms) | `tick * 1000000` (us) |
| Transform copy | 48 bytes | 112 bytes |
| RTTI | Full type descriptors | Stripped (identified by profiling strings) |
| Pair physics | Not observed | Explicit `PairComputeForces` |
| Boost force curve | Decays: starts high, decreases to 0 | Ramps UP: starts at 0, increases to max |
| Vehicle types | Stadium only | Stadium + Rally + Snow + Desert |
| Friction solver | Per-wheel analytical | Iterative constraint solver |

### The turbo reversal

**Confidence**: VERIFIED

**TMNF**: `boost_force = (1.0 - t/duration) * strength` -- force DECAYS from max to zero.

**TM2020**: `boost_force = (t/duration) * strength * modelScale` -- force RAMPS UP from zero to max.

TM2020 acceleration is back-loaded. The car accelerates MORE as the boost expires.

### Suspension model evolution

TMNF used `AbsorbingValKi` (spring stiffness) and `AbsorbingValKa` (damping). TM2020 uses standard engineering notation: `Spring.FreqHz` and `Spring.DampingRatio`. The underlying spring-damper model is equivalent:

```
TMNF:   F = Ki * (rest - compression) - Ka * velocity
TM2020: FreqHz = sqrt(Ki / mass) / (2*pi)
         DampingRatio = Ka / (2 * sqrt(Ki * mass))
```

---

## Comprehensive constants table

### Global data constants

| Address | Name | Type | Likely Value | Used In | Purpose |
|:---|:---|:---:|:---:|:---|:---|
| `DAT_141d1fa9c` | MAX_SUBSTEP_FLOAT | float | 1000.0f | PhysicsStep_TM:132 | Divisor when sub-step count capped |
| `DAT_141d1fe58` | MICROSECOND_SCALE | double | 1000000.0 | PhysicsStep_TM:136 | Converts sub_dt to microseconds |
| `DAT_141d1ed34` | MIN_SPEED_THRESHOLD | float | [UNKNOWN] | ComputeForces:114 | Minimum maxSpeed for clamping |
| `DAT_141d1ee10` | STEP_PARAM | float | [UNKNOWN] | PhysicsStep_TM:118,187 | Parameter to step functions |
| `DAT_141d1ef7c` | FRAGILE_SEVERITY | float | [UNKNOWN] | PhysicsStep_TM:192 | Collision severity for fragile break |
| `DAT_141d1fa18` | SURFACE_HEIGHT_SCALE | float | [UNKNOWN] | BeforeMgrDynaUpdate:77 | Surface height scale factor |
| `DAT_141d1ecc4` | MIN_NORMAL_LEN_SQ | float | ~0.0001 | MergeContacts:219 | Prevents zero-division |
| `DAT_141d1fc24` | MAX_NORMAL_LEN_SQ | float | ~100.0 | MergeContacts:219 | Sanity check |
| `DAT_141d1f3c8` | UNIT_NORMAL_SCALE | float | 1.0f | MergeContacts:226 | Normalized normal scale |
| `DAT_141a64350` | ZERO_VEC_XY | 2xfloat | {0.0, 0.0} | ComputeForces:222 | Zero vector constant |
| `DAT_141a64358` | ZERO_VEC_Z | float | 0.0f | ComputeForces:223 | Zero Z component |
| `DAT_141ebccfc` | SLEEP_ENABLED | int | [UNKNOWN] | Gravity:40 | Sleep detection toggle |
| `DAT_141ebcd00` | SLEEP_DAMPING | float | [UNKNOWN, <1.0] | Gravity:45-56 | Velocity damping factor |
| `DAT_141ebcd04` | SLEEP_THRESHOLD | float | [UNKNOWN] | Gravity:27 | Sleep velocity threshold |
| `DAT_141e64060` | STACK_COOKIE | uint64 | [random] | Multiple | Security check cookie |
| `DAT_141fabc20` | COLLISION_LAYER_TABLE | uint[256] | [256 entries] | DynCollisionCache:42 | Collision type to layer mask |

### Hardcoded integer constants

| Value | Hex | Context | Meaning |
|:---:|:---:|:---|:---|
| 1000000 | 0xF4240 | PhysicsStep_TM, ProcessContactPoints | Tick to microsecond multiplier |
| 1001 | 0x3E9 | PhysicsStep_TM:126 | Max sub-step count + 1 |
| 999 | 0x3E7 | PhysicsStep_TM:131 | Actual max sub-step count |
| 88 | 0x58 | ProcessContactPoints | Contact point struct stride |
| 56 | 0x38 | PhysicsStep_V2, ComputeExternalForces | Body data struct stride |
| 224 | 0xE0 | PhysicsStep_V2:220 | 4x body stride (loop unrolling) |
| 184 | 0xB8 | ComputeForces reset blocks | Per-wheel state block stride |
| 44 | 0x2C | FrictionIterCount_Config:21 | SSolverParams struct size |
| 144 | 0x90 | Tunings registration:21 | NGameSlotPhy::SMgr struct size |
| 2168 | 0x878 | BeforeMgrDynaUpdate:107 | Replay state copy size |
| 20 | 0x14 | BeforeMgrDynaUpdate | Wheel contact history buffer size |
| 13 | 0x0D | DynCollisionCache:77 | Compound collision shape type ID |
| 0xFFFFFFFF | -1 | Multiple | Sentinel: "no value" / "uninitialized" |

### Bitfield constants

| Value | Bits | Context | Meaning |
|:---:|:---|:---|:---|
| 0x0F | bits 0-3 | StatusFlags | Low nibble mask for vehicle state |
| 0x04 | bit 2 | ContactPhyFlags | DisableEvents flag |
| 0x08 | bit 3 | ContactPhyFlags | HasContactThisTick |
| 0x10 | bit 4 | ContactPhyFlags | SubStepCollisionDetected |
| 0xE0 | bits 5-7 | ContactPhyFlags | ContactType field |
| 0x0600 | bits 9-10 | ContactPhyFlags | Cleared each tick in PhysicsStep_TM |
| 0x1800 | bits 11-12 | PhysicsStep_TM:191 | Both must be set for fragile break |
| 0x10000 | bit 16 | ContactPhyFlags | SubStepCollisionResult |

---

## Curious questions answered

### "What happens when I crash into a wall?"

The collision pipeline runs through these stages:

```
NHmsCollision::StartPhyFrame (FUN_1402a9c60)
    |  - Copies current positions to previous positions
    |  - Resets hit body indices to 0xFFFFFFFF
    |  - Resets acceleration structure
    v
NSceneDyna::DynamicCollisionCreateCache (FUN_1407f9da0)
    |  - Creates 56-byte cache entries per body
    |  - Computes collision layer masks
    |  - Handles compound shapes (type 0xD)
    v
NSceneDyna::InternalPhysicsStep (FUN_1408025a0)
    |  - Runs the constraint solver
    |  - Uses SSolverParams for iteration counts
    v
NHmsCollision::MergeContacts (FUN_1402a8a70)
    |  - Merges nearby contacts with similar normals
    |  - Averages positions, normals, impulses
    v
NSceneVehiclePhy::PhysicsStep_ProcessContactPoints (FUN_1407d2b90)
    |  - Processes vehicle-world contacts (stride 0x58)
    |  - Processes vehicle-vehicle contacts
    |  - Clears 7 contact buffers
    v
Post-collision checks (PhysicsStep_TM.c:191-195)
    |  - Fragile surface check
    |  - Collision severity threshold
```

The `MinVelocityForRestitution` parameter at SSolverParams offset `0x28` defines the minimum impact velocity required for a bounce. Below this threshold, the collision is purely inelastic. The `Bouncy` gameplay surface explicitly creates high-restitution behavior.

### "How does ice/dirt/grass affect driving?"

Each wheel independently detects its surface. The friction coefficient changes instantly when a wheel crosses a surface boundary. The per-wheel `GroundContactMaterial` field (`uint16`) updates every physics tick based on which surface the wheel's raycast hits.

| Surface ID | Physics Role | Friction Level |
|:---|:---|:---|
| `Asphalt` | Road surface | HIGH grip |
| `Concrete` | Structural | HIGH grip |
| `Dirt` | Off-road | MEDIUM grip |
| `Grass` | Natural ground | LOW grip |
| `Ice` / `RoadIce` | Frozen surface | VERY LOW grip |
| `Rubber` | Track borders | HIGH grip, bouncy |
| `Plastic` | Inflatables/obstacles | MEDIUM grip, bouncy |

`NoGrip` (`0x141be1244`) is NOT a material -- it is a gameplay trigger zone that overrides normal friction. `SlowMotion` (`0x141be12d0`) reduces `SimulationTimeCoef`, slowing the entire physics simulation for that vehicle.

### "How does the gearbox/engine simulation work?"

The decompiled `ComputeForces` dispatcher does NOT contain engine/gearbox logic. That code lives inside the force model functions (FUN_140851f00 etc.).

From TMNF cross-reference (where the M6/Steer06 model was fully decompiled):
- 6 gear ratios stored in the tuning GBX (TM2020 expanded to 8 gears)
- RPM computed from wheel rotation speed and current gear ratio
- Gear shifts triggered by RPM thresholds
- Engine torque via `CFuncKeysReal` piecewise linear curves
- Accelerator pedal maps to engine torque, which maps to wheel drive force

TM2020 has RPM range up to 11,000 (vs TMNF ~10,000). The `EngineOn` flag enables explicit engine disabling (FreeWheeling surface effect).

---

## Open questions and future work

1. **Gravity constant location**: The 9.81 m/s^2 constant was not found in scanned sections. It may reside in `.Gbx` files or protected sections.

2. **Force model variants**: The 7 force computation functions need decompilation to reveal the actual per-wheel tire model.

3. **Tire model details**: The wheel has SlipCoef and TireWear but the slip curve function is buried inside force model functions. Decompiling `FUN_140869cd0` (standard car) would reveal the tire model.

4. **Friction solver**: `NSceneDyna::InternalPhysicsStep` (4991 bytes) likely contains the full Gauss-Seidel solver loop.

5. **Network replication**: `NSceneVehiclePhy::Replica_SnapshotTake` handles deterministic state sync. Snapshot size and fields need investigation.

6. **Surface physics IDs**: Exact integer values of `EPlugSurfaceMaterialId` and `EPlugSurfaceGameplayId` enums need extraction.

7. **Protected sections**: The `.A2U` and `.D."` sections contain ~10 MB of unscanned code.

8. **Vehicle model data**: The `VehiclePhyModelCustom.Gbx` file format contains tunable parameters (spring rates, damper values, engine curves, gear ratios).

9. **Water buoyancy/drag formulas**: FUN_1407fb580 needs decompilation.

10. **Cross-version determinism**: Whether replays/ghosts from one game version produce identical results on another.

---

## Decompiled code files

The following decompiled functions are saved in `/decompiled/physics/`:

| File | Function | Size |
|------|----------|------|
| `NSceneVehiclePhy__ComputeForces.c` | Vehicle force computation | 1713 B |
| `NSceneVehiclePhy__PairComputeForces.c` | Vehicle-vs-vehicle forces | 635 B |
| `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c` | Pre-dynamics prep | 1723 B |
| `NSceneVehiclePhy__PhysicsStep_ProcessContactPoints.c` | Contact processing | 339 B |
| `NSceneVehiclePhy__ExtractVisStates.c` | Physics-to-visual copy | 338 B |
| `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c` | Gravity + integration | 790 B |
| `NSceneDyna__ComputeExternalForces.c` | External force loop | 202 B |
| `NSceneDyna__ComputeWaterForces.c` | Buoyancy | 370 B |
| `NSceneDyna__PhysicsStep.c` | Physics step wrapper | 126 B |
| `NSceneDyna__PhysicsStep_V2.c` | Main physics orchestrator | 1351 B |
| `NSceneDyna__DynamicCollisionCreateCache.c` | Collision cache | 472 B |
| `NHmsCollision__MergeContacts.c` | Contact merging | 1717 B |
| `NHmsCollision__StartPhyFrame.c` | Frame initialization | 297 B |
| `PhysicsStep_TM.c` | TM-specific vehicle step | 1729 B |
| `FrictionIterCount_Config.c` | Friction solver config | 606 B |
| `ArenaPhysics_CarPhyUpdate.c` | Arena car physics update | 325 B |
| `CSmArenaPhysics__Players_BeginFrame.c` | Players begin frame | 196 B |
| `Tunings_CoefFriction_CoefAcceleration.c` | Tuning registration | 265 B |

---

## Function reference

| Function Label | Address | File | Key Purpose |
|:---|:---:|:---|:---|
| `PhysicsStep_TM` | `0x141501800` | `PhysicsStep_TM.c` | Per-vehicle physics step with adaptive sub-stepping |
| `NSceneDyna::PhysicsStep` | `0x1407bd0e0` | `NSceneDyna__PhysicsStep.c` | Thin wrapper, converts time to microseconds |
| `NSceneDyna::PhysicsStep_V2` | `0x140803920` | `NSceneDyna__PhysicsStep_V2.c` | Main rigid body dynamics orchestrator |
| `NSceneVehiclePhy::ComputeForces` | `0x1408427d0` | `NSceneVehiclePhy__ComputeForces.c` | Vehicle force computation dispatch |
| `NSceneVehiclePhy::PairComputeForces` | `0x140842ed0` | `NSceneVehiclePhy__PairComputeForces.c` | Vehicle-vehicle pair setup |
| `NSceneVehiclePhy::PhysicsStep_BeforeMgrDynaUpdate` | `0x1407cfce0` | `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c` | Pre-dynamics: transforms, contacts, history |
| `NSceneVehiclePhy::PhysicsStep_ProcessContactPoints` | `0x1407d2b90` | `NSceneVehiclePhy__PhysicsStep_ProcessContactPoints.c` | Contact point processing |
| `NSceneVehiclePhy::ExtractVisStates` | `0x1407d29a0` | `NSceneVehiclePhy__ExtractVisStates.c` | Physics to visual state extraction |
| `NSceneDyna::ComputeGravityAndSleepStateAndNewVels` | `0x1407f89d0` | `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c` | Gravity, sleep detection, velocity integration |
| `NSceneDyna::ComputeExternalForces` | `0x1407f81c0` | `NSceneDyna__ComputeExternalForces.c` | External force accumulation |
| `NSceneDyna::ComputeWaterForces` | `0x1407f8290` | `NSceneDyna__ComputeWaterForces.c` | Buoyancy/drag for water volumes |
| `NSceneDyna::DynamicCollisionCreateCache` | `0x1407f9da0` | `NSceneDyna__DynamicCollisionCreateCache.c` | Collision cache for solver |
| `FrictionIterCount_Config` | `0x1407f3fc0` | `FrictionIterCount_Config.c` | SSolverParams registration |
| `CSmArenaPhysics::Players_BeginFrame` | `0x1412c2cc0` | `CSmArenaPhysics__Players_BeginFrame.c` | Arena physics frame start |
| `ArenaPhysics_CarPhyUpdate` | `0x1412e8490` | `ArenaPhysics_CarPhyUpdate.c` | Car physics update (zone, events) |
| `Tunings_CoefFriction_CoefAcceleration` | `0x141071b20` | `Tunings_CoefFriction_CoefAcceleration.c` | NGameSlotPhy tuning registration |
| `NHmsCollision::MergeContacts` | `0x1402a8a70` | `NHmsCollision__MergeContacts.c` | Contact point merging |
| `NHmsCollision::StartPhyFrame` | `0x1402a9c60` | `NHmsCollision__StartPhyFrame.c` | Collision frame initialization |

### Force model function addresses

| Model | Switch Value | Address | Param Count | Estimated Size |
|:---:|:---:|:---:|:---:|:---|
| Base | 0, 1, 2 | `FUN_140869cd0` | 2 | [UNKNOWN] |
| M4 | 3 | `FUN_14086b060` | 2 | [UNKNOWN] |
| M5 | 4 | `FUN_14086bc50` | 2 | [UNKNOWN] |
| M6 (CarSport) | 5 | `FUN_140851f00` | 3 | [UNKNOWN -- likely >4KB based on TMNF's M6] |
| New Model A | 6 | `FUN_14085c9e0` | 3 | [UNKNOWN] |
| New Model B | 0xB | `FUN_14086d3b0` | 3 | [UNKNOWN] |

### Key struct sizes

| Struct | Size | Evidence |
|:---|:---:|:---|
| Per-vehicle state | ~0x1CA0 (7328 bytes) | Highest offset +0x1C98 + ptr size |
| Per-body dynamics | 0x38 (56 bytes) | Force clearing loop stride |
| Contact point | 0x58 (88 bytes) | Contact processing loop stride |
| Collision cache entry | 0x38 (56 bytes) | DynamicCollisionCreateCache stride |
| SSolverParams | 0x2C (44 bytes) | Registration function size parameter |
| NGameSlotPhy::SMgr | 0x90 (144 bytes) | Registration function size parameter |
| Per-wheel state block | 0xB8 (184 bytes) | ComputeForces reset stride |
| Wheel contact history | 28 bytes (8 header + 20 data) | Circular buffer |
| Vehicle model (partial) | >0x31A8 | Highest offset via vehicle+0x88 |
| Transform copy | 112 bytes | 28 x 4-byte values |

---

## Related Pages

- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- Redirects here (merged)
- [14-tmnf-crossref.md](14-tmnf-crossref.md) -- TMNF reverse engineering cross-reference
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Live game memory fields from Openplanet
- [21-competitive-mechanics.md](21-competitive-mechanics.md) -- Competitive and TAS-relevant details
- [12-architecture-deep-dive.md](12-architecture-deep-dive.md) -- Game architecture and state machine
- [07-networking.md](07-networking.md) -- Networking and replication
- [00-master-overview.md](00-master-overview.md) -- Master overview of all RE documents

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
**Data sources**: String cross-references, decompiled functions, float scanning, namespace enumeration, 18 decompiled physics functions, cross-referenced with TMNF RE diary

</details>

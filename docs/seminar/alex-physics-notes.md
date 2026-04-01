# Alex's Physics Engine Study Notes: Trackmania 2020

## The Physics Tick

This chapter covers the fixed-timestep simulation loop, adaptive sub-stepping, and per-tick vehicle processing. You will understand how TM2020 achieves deterministic physics at competitive speed.

### 100Hz Fixed Tick Rate

TM2020's heartbeat is a **100Hz fixed physics tick** -- one step every 10 milliseconds. This is completely decoupled from display framerate. Whether you run at 30fps or 300fps, physics outcomes are identical for the same inputs.

The docs mark this as PLAUSIBLE rather than VERIFIED. No single decompiled constant says "100Hz." The evidence converges from multiple sources:

- `SmMaxPlayerResimStepPerFrame=100` in Default.json caps resimulation to 100 ticks per frame (= 1 second at 100Hz). (21-competitive-mechanics.md, line 30-36)
- TMNF ran at 100Hz (community-verified via donadigo's documentation). (14-tmnf-crossref.md, line 185)
- The microsecond conversion pattern `tick * 1000000` produces 10,000,000us per tick at 10ms ticks. (PhysicsStep_TM.c, line 63)

I found this fascinating -- the tick rate is never hardcoded in the binary. It is presumably set in a configuration or GBX resource file. The code only cares about "here is one tick, process it."

### Walk Through One Tick (Step by Step)

From `PhysicsStep_TM.c` (FUN_141501800):

**Step 1: Profiling and time setup** (lines 59, 63)
```c
FUN_140117690(local_108, "PhysicsStep_TM");  // profiling scope
lVar18 = (ulonglong)*param_4 * 1000000;      // tick -> microseconds (INTEGER math!)
```

**Step 2: Iterate over all vehicles** (lines 64-67)
The function loops over a vehicle array at `*param_3`, checking each vehicle's status nibble at offset `+0x128C`. Vehicles with status nibble == 2 are SKIPPED entirely. (10-physics-deep-dive.md, line 68)

**Step 3: Clear physics flags** (line 69)
`vehicle+0x1C7C &= 0xFFFFF5FF` -- clears bits 9 and 10 of the ContactPhyFlags bitfield at the start of each tick. These bits track collision state within the tick.

**Step 4: Check simulation mode** (line 70)
Only modes 0 (normal) and 3 (normal-alt) proceed to physics computation. Mode 1 is replay (state copied from replay data), mode 2 is spectator. (10-physics-deep-dive.md, line 376)

**Step 5: Compute velocity scale** (line 71)
```c
fVar21 = FUN_14083dca0(vehicle + 0x1280, model_ptr);
fVar25 = fVar21 * (float)param_4[2];  // scale * dt
```
This scale factor feeds into the sub-step count computation.

**Step 6: Compute four velocity magnitudes** (lines 78-116)
TM2020 computes FOUR separate velocity magnitudes:
1. `|v_linear|` from body at `lVar15+0x40..0x48` -- linear velocity of the rigid body
2. `|v_angular|` from body at `lVar15+0x4C..0x54` -- angular velocity of the rigid body
3. `|v_wheel1|` from vehicle at `+0x1348..0x1350` -- first auxiliary velocity vector
4. `|v_wheel2|` from vehicle at `+0x1354..0x135C` -- second auxiliary velocity vector

TMNF only used 2 velocity terms (linear + angular). TM2020 uses 4. (14-tmnf-crossref.md, line 191)

Every single sqrt is guarded:
```c
fVar24 = x*x + y*y + z*z;
if (fVar24 < 0.0) {
    fVar24 = (float)FUN_14195dd00(fVar24);  // safe sqrt
} else {
    fVar24 = SQRT(fVar24);  // SSE sqrtss
}
```
(PhysicsStep_TM.c, lines 87-95)

**Step 7: Compute sub-step count** (lines 121-132)
```
total_speed = |v1| + |v2| + |v3| + |v4|
raw_count = (uint)((total_speed * scaled_dt) / body_step_size)
num_substeps = raw_count + 1  // always at least 1
```
If `num_substeps >= 1001`, it caps at 1000 and uses `sub_dt = dt / 1000.0f`.

**Step 8: Sub-step loop** (lines 137-167)
Runs `num_substeps - 1` equal-size steps, each executing:
1. `FUN_141501090` -- Collision detection (result stored in bit 16 of ContactPhyFlags)
2. `FUN_140801e20` -- Set dynamics time
3. `FUN_1414ffee0` -- Compute forces
4. `FUN_1414ff9d0` -- Post-force update
5. `FUN_1415009d0` -- Physics step dispatch
6. `FUN_14083df50` -- Integration

**Step 9: Final remainder step** (lines 169-190)
Same 6 function calls, but with remaining time (`scaled_dt - (sub_dt * (N-1))`). This ensures total simulated time exactly equals dt -- no floating-point drift!

**Step 10: Fragile check** (lines 191-195)
After all sub-steps, checks if the vehicle should break:
```c
if ((flags & 0x1800) == 0x1800 &&         // both collision bits set
    DAT_141d1ef7c < vehicle+0x1C8C &&      // severity exceeds threshold
    1 < (status_nibble - 2)) {             // status allows it
    FUN_1407d2870(arena, vehicle, tick);    // BREAK!
}
```

**Step 11: Transform copy** (lines 199+)
Copies current transform (112 bytes at `+0x90`) to previous transform (at `+0x104`) for interpolation and collision backtracking.

### Adaptive Sub-stepping

Forward Euler integration (which TM2020 uses) is notoriously unstable at high velocities. Sub-stepping prevents a fast car from tunneling through thin geometry or developing unstable oscillations.

**The formula** (10-physics-deep-dive.md, Section 7.3):
```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
sub_dt = dt / num_substeps
```

The cap is **1000 sub-steps**, reduced from TMNF's 10,000. (14-tmnf-crossref.md, line 188). I think the reduction has several reasons:

- TM2020's constraint solver is more robust (iterative Gauss-Seidel vs TMNF's analytical friction)
- 1000 sub-steps at 100Hz = 100,000 sub-steps per second, already extreme
- TM2020 has 4 vehicle types requiring 4x the testing
- Exceeding 1000 does not crash -- it uses `dt/1000`, which may cause artifacts

### Questions I Still Have

1. What exactly does `FUN_14083dca0` compute for the velocity scale factor?
2. The `body_step_size` at `lVar15+0x54` -- where does this value come from?
3. Why 4 velocity terms instead of TMNF's 2? Are `v_wheel1` and `v_wheel2` the wheel spin velocities?
4. What is the exact value of the tick duration `param_4[2]`?
5. The "safe sqrt" function `FUN_14195dd00` -- does it return `sqrt(abs(x))` or just `0.0`?

### If I Were Building This

I would absolutely use the same fixed-tick approach. The 100Hz rate is a sweet spot -- fast enough for responsive gameplay, slow enough to not burn CPU. I might consider 120Hz for smoother feel on modern displays.

The adaptive sub-stepping is genius. I would implement it the same way, but add a second cap: if `num_substeps > 50`, log a warning. The remainder-step approach (N-1 equal steps + 1 remainder) is much better than just `N * sub_dt` which drifts. I am changing this in my prototype immediately.

### What Surprised Me

The 4-velocity-term sub-step count. I expected only linear velocity to matter. Including angular velocities makes sense for rapid spinning. The two extra "wheel velocity" terms suggest the sub-stepping captures wheel dynamics, not just chassis. Very clever.

Also, the tick rate is never hardcoded as a constant. The entire system works with whatever tick duration it receives. You could theoretically run at 200Hz by changing a config value.

---

## Vehicle Forces

This chapter covers the force model dispatch system, pre-model setup, and the CarSport model. You will understand how TM2020 routes vehicle physics through 6 distinct force computation functions.

### The Force Model Dispatch System

A **switch statement** at `NSceneVehiclePhy__ComputeForces.c:142-162` dispatches to different force computation functions based on the value at `vehicle_model+0x1790`:

```c
switch(*(undefined4 *)(local_118 + 0x1790)) {
    case 0: case 1: case 2: FUN_140869cd0(param_3, &local_158);  // 2 params
    case 3:                  FUN_14086b060(param_3, &local_158);  // 2 params
    case 4:                  FUN_14086bc50(param_3, &local_158);  // 2 params
    case 5:                  FUN_140851f00(param_3, param_4, &local_158);  // 3 params!
    case 6:                  FUN_14085c9e0(param_3, param_4, &local_158);  // 3 params!
    case 0xB:                FUN_14086d3b0(param_3, param_4, &local_158);  // 3 params!
}
```

(NSceneVehiclePhy__ComputeForces.c, lines 142-162; 10-physics-deep-dive.md, lines 140-162)

**8 case values** map to **6 actual functions**:

| Switch Value | Function | TMNF Equivalent | Likely Car Type | Param Count |
|:---:|:---:|:---:|:---:|:---:|
| 0, 1, 2 | FUN_140869cd0 | Steer01/02/03 | Base/legacy | 2 |
| 3 | FUN_14086b060 | Steer04 (M4) | Bicycle/simplified | 2 |
| 4 | FUN_14086bc50 | Steer05 (M5) | TMNF-era | 2 |
| 5 | FUN_140851f00 | Steer06 (M6) | CarSport/Stadium | 3 |
| 6 | FUN_14085c9e0 | NEW | Rally/Snow | 3 |
| 0xB | FUN_14086d3b0 | NEW | Desert/variant | 3 |

(10-physics-deep-dive.md, lines 170-177; 14-tmnf-crossref.md, lines 350-372)

**Models 5, 6, and 0xB receive an extra `param_4` (tick/time parameter)** enabling time-dependent effects: turbo decay curves, time-limited boost, cruise control timing, and vehicle transform transition physics. (10-physics-deep-dive.md, lines 192-198)

### Pre-Model Setup

Before dispatching, ComputeForces does several things.

**Force accumulator selection** (lines 128-137):
```c
if (model+0x1790 < 6) {
    force_vec = vehicle+0x144C;  // old layout
} else {
    force_vec = vehicle+0x1534;  // new layout (232 bytes later!)
}
```
Models 6+ use a reorganized force layout within the vehicle state. The 232-byte gap (`0x1534 - 0x144C = 0xE8`) is large enough for an entire set of per-wheel data. (10-physics-deep-dive.md, lines 200-221)

**Speed clamping** (lines 112-126):
```c
maxSpeed = model+0x2F0;
speed_sq = vx*vx + vy*vy + vz*vz;
if (maxSpeed^2 < speed_sq && epsilon < maxSpeed) {
    scale = maxSpeed / sqrt(speed_sq);
    velocity *= scale;  // clamp to maxSpeed
}
```
The velocity is hard-clamped to `MaxSpeed` from the vehicle model. (NSceneVehiclePhy__ComputeForces.c, lines 112-126)

### The CarSport Force Model (Case 6 -- FUN_14085c9e0)

**A contradiction I need to flag.** The documentation in 10-physics-deep-dive.md (line 275) says CarSport is model 5. But 22-ghidra-gap-findings.md (lines 67-99) identifies FUN_14085c9e0 (case 6) as "the full CarSport (Stadium car) force model." The decompiled file header agrees. I accept the decompiled file headers as more authoritative.

The CarSport model (case 6) breaks down into 12 sub-functions (22-ghidra-gap-findings.md, lines 77-86):

1. `FUN_1408570e0` -- Per-wheel force calculation (called 4 times)
2. `FUN_14085ad30` -- Steering model
3. `FUN_14085a0d0` -- Suspension/contact update
4. `FUN_14085ba50` -- Anti-roll bar
5. `FUN_140858c90` -- Damping
6. `FUN_140857380` -- Drift/skid model
7. `FUN_140857b20` -- Boost/reactor forces
8. `FUN_14085c1b0` -- Airborne control forces (pitch/roll/yaw when airborne)
9. `FUN_14085b600` -- Final force integration
10. Surface grip interpolation via FUN_140869c90
11. Gravity/air damping coefficient lookup
12. Throttle-based engine force via curve at `+0x310/+0x314`

Key state fields discovered (force_model_carsport_FUN_14085c9e0.c, header comments):
- `plVar1+0x2EB` = friction coefficient state (maps to `Tunings.CoefFriction`)
- `plVar1+0x2EC` = acceleration coefficient state (maps to `Tunings.CoefAcceleration`)
- `plVar1+0x2B9` = grip state, clamped to minimum at tuning+0x2AFC
- `plVar1+0x2B1` = steering sensitivity (normal mode)
- `plVar1+0x158C` = steering sensitivity (custom mode, selected by flag at +0x15DC)

**Speed thresholds**: `tuning+0x2AE0` (low) and `+0x2AE4` (high) define a speed range affecting grip behavior.

**Post-respawn force**: A fade-out force is applied for `2x duration` stored at `tuning+0x2B80`, linearly fading from full to zero. (22-ghidra-gap-findings.md, lines 92-94)

### The Pacejka-Like Tire Model

The 2-wheel model (case 3, FUN_14086b060) has its lateral grip function fully decompiled as `FUN_14086af20` (22-ghidra-gap-findings.md, lines 144-159):

```
lateral_force = -slip * linear_coef - slip * |slip| * quadratic_coef
```

This is a **simplified Pacejka-like model**. The real Pacejka Magic Formula is `F = D * sin(C * atan(B*x - E*(B*x - atan(B*x))))`. TM2020 uses a quadratic approximation:

- Linear stiffness at `tuning+0x1A5C` (the "cornering stiffness")
- Quadratic stiffness at `tuning+0x1A60` (the self-limiting term)
- Grip limit from speed-dependent curve at `tuning+0x1AC0`
- Drift reduces grip by factor at `tuning+0x1B10`

When force exceeds grip: clamp to grip limit, set sliding flag. When force is within grip: use computed force, clear sliding flag.

The linear term provides realistic feel at small slip angles. The quadratic term (`slip * |slip|`) naturally saturates at high slip -- it is slip squared but preserving sign. No need for a complex sin/atan chain.

### The 3-State Drift Machine

The drift system in the 2-wheel model has 3 discrete states stored at `offset+0x1460` (22-ghidra-gap-findings.md, lines 58-63; force_model_2wheel_FUN_14086b060.c, lines 12-16):

| State | Value at +0x1460 | Behavior |
|:---:|:---:|:---|
| No drift | 0 | Normal lateral grip, no drift angle |
| Drift building | 1 | Slip accumulating at +0x1458, building drift angle |
| Drift committed | 2 | Using stored drift angle, reduced grip |

**Drift builds** proportional to `lateral_slip * drift_rate * delta_time` (tuning+0x1B6C). **Drift angle** is clamped by max value at `tuning+0x1B78`.

This is a state machine, not a continuous model. Transitions are discrete. When you start sliding, you enter state 1. Slip accumulates. Once the drift angle reaches threshold, you commit (state 2). In state 2, the stored angle drives force calculations and grip is reduced.

### Engine / RPM Simulation

From Openplanet data (19-openplanet-intelligence.md, lines 56-59):
- `CurGear`: uint, 0-7 (8 gears total -- TMNF only had 6!)
- `RPM`: float, 0-11000 (vs TMNF's ~10000)
- `EngineOn`: bool

**Is RPM real or cosmetic?** Based on the TMNF analysis (where M6 was fully decompiled), RPM IS simulated. RPM determines gear shift timing, engine torque output via the torque curve, and burnout state machine entry conditions. (10-physics-deep-dive.md, lines 1626-1631)

The gearbox defaults (from `CPlugVehicleGearBox`, 10-tuning-loading-analysis.md, lines 145-157):

| Gear | Speed (km/h) |
|:---:|:---:|
| 1 | 56 |
| 2 | 84 |
| 3 | 100 |
| 4 | 143 |
| 5 | 207 |
| 6 | 297 |
| 7 | 338 |

Max RPM = 7000, Shift RPM = 6500. These are DEFAULT constructor values. Actual values loaded from GBX may differ.

### What Makes TM2020 Feel Different

The "TM2020 feel" comes from several interacting systems:

1. **Exaggerated gravity** (~3x Earth, see later chapter) makes the car feel heavy and planted
2. **Turbo ramps UP** not down -- you feel the kick at the END of the boost
3. **State-machine drift** gives discrete, predictable transitions
4. **Speed-dependent curves everywhere** -- grip, engine force, steering all change with speed
5. **4 independent wheels** each detecting their own surface and computing their own forces
6. **Reactive sub-stepping** -- simulation gets finer when you go faster

### Questions I Still Have

1. Which force model does each car ACTUALLY use? The documentation contradicts itself (CarSport = 5 vs CarSport = 6).
2. How does the burnout state machine work in TM2020?
3. What are the actual tire force curves? They are in GBX tuning data, not the binary.
4. How does the per-wheel force function (`FUN_1408570e0`) work?
5. What is the airborne control model? How much control does the player actually have?

### If I Were Building This

I would start with the 2-wheel bicycle model (case 3) as my base. It captures the essential physics: longitudinal/lateral force decomposition via sin/cos, the quadratic lateral grip model, and the 3-state drift machine.

Then I would add per-wheel forces as a second iteration. I would NOT try to match TM2020's exact feel immediately. Focus on getting the structural architecture right and tune the curves later.

---

## Turbo and Surface Effects

This chapter covers turbo ramp-up, all 22 gameplay surface effects, and the dual-surface-system architecture. You will understand why TM2020's boost feels different from TMNF.

### Turbo Ramps UP (Not Down!)

This was the single most surprising finding. Here is the evidence.

**The decompiled code** at NSceneVehiclePhy__ComputeForces.c, lines 104-106:
```c
local_b8 = ((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) *
           *(float *)(lVar6 + 0x16e4) * *(float *)(*(longlong *)(lVar6 + 0x1bb0) + 0xe0);
```

Translating:
```
force = ((current_tick - start_tick) / duration) * strength * model_scale
```

At `t=0` (moment you hit the turbo pad): `force = 0 * strength = 0`. At `t=duration` (boost about to expire): `force = 1.0 * strength * scale = MAX`.

**TMNF was the opposite**: `force = (1.0 - t/duration) * strength` -- force DECAYS from max to zero. (14-tmnf-crossref.md, lines 488-504)

In TM2020, when you hit a turbo pad, you get nothing initially. The force builds gradually, reaching maximum at the instant the boost expires. This creates a smooth acceleration curve rather than an instant jolt. (10-physics-deep-dive.md, lines 1307-1318)

**Competitive implications** (21-competitive-mechanics.md, lines 381-393):
- The moment you touch a turbo pad, you get almost nothing
- Maximum acceleration happens at the very end of the boost duration
- For TAS: the timing of WHEN you hit a turbo relative to corners matters differently than in TMNF

### Boost Parameters

The boost system uses three fields per vehicle (10-physics-deep-dive.md, lines 539-576):

| Offset | Type | Field | Purpose |
|:---:|:---:|:---:|:---|
| `+0x16E0` | uint | Duration | Duration in ticks |
| `+0x16E4` | float | Strength | Force multiplier |
| `+0x16E8` | uint | StartTime | Tick when boost started (-1 = no boost) |

When start time is -1 (0xFFFFFFFF), the first ComputeForces call with an active boost records the current tick. An event dispatches to the arena for audio/visual effects.

Actual duration and strength values for Turbo and Turbo2 are NOT in the binary -- they are in GBX tuning data. From TMNF cross-reference: Turbo=5.0/250ms, Turbo2=20.0/100ms. TM2020 values may differ. (10-physics-deep-dive.md, lines 1326-1330)

### All 22 Surface Gameplay Effects

From the complete `EPlugSurfaceGameplayId` enum (22-ghidra-gap-findings.md, lines 218-243; 10-physics-deep-dive.md, lines 878-903):

| ID | Effect | What It Does |
|:---:|:---|:---|
| 0 | NoSteering | Disables steering input |
| 1 | NoGrip | Removes tire grip (zero friction) |
| 2 | Reset | Resets vehicle to last checkpoint |
| 3 | ForceAcceleration | Forces constant acceleration regardless of input |
| 4 | Turbo | Speed boost level 1 (ramp-up force) |
| 5 | FreeWheeling | Disengages engine (coasting only) |
| 6 | Turbo2 | Speed boost level 2 (ramp-up, stronger) |
| 7 | ReactorBoost2_Legacy | Legacy non-directional reactor boost v2 |
| 8 | Fragile | Vehicle breaks on hard impact |
| 9 | NoBrakes | Disables brake input |
| 10 | Bouncy | High restitution surface |
| 11 | Bumper | Bumper pad level 1 |
| 12 | SlowMotion | Slows down physics simulation time |
| 13 | ReactorBoost_Legacy | Legacy non-directional reactor boost v1 |
| 14 | Bumper2 | Enhanced bumper pad |
| 15 | VehicleTransform_CarRally | Transforms to rally car |
| 16 | VehicleTransform_CarSnow | Transforms to snow car |
| 17 | VehicleTransform_CarDesert | Transforms to desert car |
| 18 | ReactorBoost_Oriented | Directional reactor boost |
| 19 | Cruise | Cruise control (fixed speed, range -1000 to 1000) |
| 20 | VehicleTransform_Reset | Resets vehicle back to stadium car |
| 21 | ReactorBoost2_Oriented | Directional reactor boost v2 |

**Gameplay effects are NOT driven by surface materials.** All 208 materials have `DGameplayId(None)`. Effects come from block/item trigger zones, not surface textures. (21-competitive-mechanics.md, line 366)

Two independent surface systems exist (10-physics-deep-dive.md, lines 1422-1438):
- `EPlugSurfaceMaterialId` -- controls friction, sound, particles, skid marks (per-wheel, updated per tick)
- `EPlugSurfaceGameplayId` -- controls turbo, reset, no-grip, slow-motion etc. (block/item trigger zones)

### NoGrip

NoGrip (surface ID 1) reduces the grip coefficient to zero via `material+0x18`. Triggered by `BeginNoGrip`/`EndNoGrip` events. Can also be applied as a handicap with configurable duration. (22-ghidra-gap-findings.md, lines 250-261)

### SlowMotion

SlowMotion (surface ID 12) modifies the time scale for the affected vehicle. Applied with a 250ms delay. It does not slow the ENTIRE game, just that vehicle's physics simulation. Other vehicles continue at normal speed.

The time scale factor modifies delta time in the force model. From Openplanet: `SimulationTimeCoef` (float, 0-1) is exposed in the VisState. (22-ghidra-gap-findings.md, lines 276-285; 19-openplanet-intelligence.md, line 106)

### Fragile

The fragile break condition requires ALL THREE conditions simultaneously (PhysicsStep_TM.c, lines 191-195; 21-competitive-mechanics.md, lines 413-434):

1. Bits 11 AND 12 of ContactPhyFlags both set (mask 0x1800)
2. Collision severity at `vehicle+0x1C8C` exceeds global threshold `DAT_141d1ef7c`
3. Status nibble is NOT 2 or 3

**Fragile is NOT "any contact = break."** A collision severity threshold exists. Gentle landings survive. The threshold is a float at `0x141d1ef7c`, identified as value 0.1. (07-physics-constants.md, line 22)

Applied with a 250ms delay. (22-ghidra-gap-findings.md, line 272)

### Reactor Boost -- The Flying Car

TM2020 has four reactor boost variants (21-competitive-mechanics.md, lines 482-493):

| Variant | Behavior |
|:---|:---|
| ReactorBoost_Legacy | Non-directional -- boost in car's current direction |
| ReactorBoost2_Legacy | Non-directional, stronger |
| ReactorBoost_Oriented | **Directional** -- boost in the PAD'S orientation |
| ReactorBoost2_Oriented | **Directional, stronger** |

The "Oriented" variants are NEW in TM2020. They apply force in the direction the pad faces, not the car. Approach angle matters. This creates a much richer optimization space for competitive play.

The CarSport model has a dedicated airborne control sub-function: `FUN_14085c1b0` applies pitch/yaw/roll forces when wheels are not in contact. (22-ghidra-gap-findings.md, line 85; 19-openplanet-intelligence.md, line 83)

### How Would I Implement Surface Effects

I would use a component-based approach:

```
SurfaceEffect (enum) -> EffectHandler (trait/interface) -> VehicleState mutation
```

Each effect as a discrete component:
- **Modifier effects** (NoGrip, NoBrakes, NoSteering): zero out the relevant coefficient
- **Force effects** (Turbo, ReactorBoost, ForceAcceleration): add to force accumulator
- **Time effects** (SlowMotion): scale dt before passing to force model
- **State effects** (Fragile, FreeWheeling): set flags that alter behavior
- **Transform effects** (VehicleTransform_*): swap the force model and tuning data

The 250ms delay for ManiaScript-triggered effects prevents exploits from toggling effects at exact tick boundaries.

---

## Collision System

This chapter covers the full collision pipeline, the Gauss-Seidel solver, and contact merging. You will understand how wall bounces and ground contact work.

### The Full Pipeline

From the decompiled code (10-physics-deep-dive.md, lines 1364-1392):

```
NHmsCollision::StartPhyFrame (FUN_1402a9c60)
    |  Copy current positions to previous
    |  Reset hit body indices to 0xFFFFFFFF
    |  Reset acceleration structure
    v
NSceneDyna::DynamicCollisionCreateCache (FUN_1407f9da0)
    |  Create 56-byte cache entries per body
    |  Compute collision layer masks
    |  Handle compound shapes (type 0xD)
    v
NSceneDyna::InternalPhysicsStep (FUN_1408025a0)
    |  Run the constraint solver
    |  Uses SSolverParams for iteration counts
    v
NHmsCollision::MergeContacts (FUN_1402a8a70)
    |  Merge nearby contacts with similar normals
    |  Average positions, normals, impulses
    v
NSceneVehiclePhy::PhysicsStep_ProcessContactPoints (FUN_1407d2b90)
    |  Process vehicle-world contacts (stride 0x58 = 88 bytes)
    |  Process vehicle-vehicle contacts
    |  Clear 7 contact buffers
    v
Post-collision checks (PhysicsStep_TM.c:191-195)
    |  Fragile surface check
    |  Collision severity threshold
```

### StartPhyFrame -- Broadphase Setup

Each physics frame begins by copying current positions to "previous" (10-physics-deep-dive.md, lines 650-690):

```c
for each collidable item:
    item+0x94 = item+0x74;  // prev_pos = cur_pos (vec3)
    item+0xA4 = 0xFFFFFFFF; // reset hit body index
```

Two separate collision item sets exist at manager offsets `+0x9C8` and `+0xA58`. This suggests separation of static and dynamic collidable objects.

### DynamicCollisionCreateCache

For each dynamic body, a 56-byte cache entry is created (10-physics-deep-dive.md, lines 692-750):

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

The layer system uses a global table at `DAT_141fabc20` mapping type bytes to layer masks: `actual_mask = layer_table[type] & ~body_exclusion_mask`.

Compound shapes (type 0x0D) get special treatment: sub-shape pointer and body transform are stored in the cache entry. (10-physics-deep-dive.md, lines 730-734)

### The Gauss-Seidel Impulse Solver

The friction solver is configured via `NSceneDyna::SSolverParams` (44 bytes) with separate iteration counts (10-physics-deep-dive.md, lines 838-867):

| Parameter | Type | Purpose |
|:---|:---:|:---|
| FrictionStaticIterCount | int | Static friction solver iterations |
| FrictionDynaIterCount | int | Dynamic friction solver iterations |
| VelocityIterCount | int | Velocity solver iterations |
| PositionIterCount | int | Position correction iterations |
| DepenImpulseFactor | float | Depenetration impulse scaling |
| MaxDepenVel | float | Maximum depenetration velocity |
| EnablePositionConstraint | bool | Whether position correction is active |
| AllowedPen | float | Allowed penetration depth (negative = auto) |
| VelBiasMode | int | Velocity bias computation mode |
| UseConstraints2 | bool | Whether to use second-generation constraints |
| MinVelocityForRestitution | float | Minimum velocity for bounce |

This is **sequential impulse / Gauss-Seidel**. Separate iteration counts per constraint type is a significant design choice. Most engines use a single count. Separate counts let you tune convergence per category -- very accurate static friction to prevent ramp sliding, fewer dynamic friction iterations since sliding is less sensitive.

### Contact Merging Algorithm

From `NHmsCollision__MergeContacts.c` (10-physics-deep-dive.md, lines 752-808):

**Phase 1: Find merge candidates**
For each pair (i, j) where j > i: check distance, normal dot product, and layer type.

**Phase 2: Execute merges**
Average positions, normals, impulses across the group. Normalize the averaged normal.

**Phase 3: Remove consumed contacts**
Sort consumed indices, remove in reverse order.

This reduces solver jitter from redundant constraints at the same point.

### Contact Structure

Each contact point is 88 bytes (0x58 stride) (10-physics-deep-dive.md, lines 815-836):

| Offset | Purpose |
|:---:|:---|
| +0x10..+0x18 | Impulse vector (xyz) |
| +0x1C..+0x24 | Contact normal (xyz) |
| +0x28..+0x30 | Contact position (xyz) |
| +0x34..+0x3C | Alternate normal (xyz) |
| +0x40..+0x48 | Secondary position (xyz) |
| +0x52 | Contact type (short) |
| +0x54 | Contact flags (bit 1 = has alternate) |

At least **7 separate contact buffers** exist (at vehicle offsets 0x188, 0x198, 0x1A8, 0x1B8, 0x1C8, 0x1D8, 0x1E8), each cleared after processing. (10-physics-deep-dive.md, line 497)

### Minimal Viable Collision System

For my game, the minimal system needs:
1. **Broadphase**: Grid or BVH for spatial acceleration
2. **Per-wheel raycasts**: 4 rays from chassis downward for ground detection
3. **Contact generation**: Mesh-vs-convex hull for car body collisions
4. **Sequential impulse solver**: With separate static/dynamic friction iterations
5. **Contact merging**: Average nearby same-normal contacts
6. **Depenetration**: Position correction to prevent sinking into walls

I could skip compound shapes, the 7 contact buffer categories, and the layer mask system initially. The core "feel" comes from solver parameters and the tire friction model.

---

## Determinism

This chapter covers the 6 mechanisms TM2020 uses for deterministic physics and why WASM can match (and exceed) them. You will understand how replays and ghost validation work.

### Why Determinism Matters

Trackmania's replay system records **inputs**, not positions. The game re-runs physics with recorded inputs for ghost playback and server validation. Non-deterministic physics breaks this entire system. (21-competitive-mechanics.md, lines 111-116)

The replay state copy is 2,168 bytes (`0x878`), including the complete force model configuration, velocity state, and all wheel data. (21-competitive-mechanics.md, lines 236-241)

### The 6 Mechanisms

**Mechanism 1: Integer-based timing** (PhysicsStep_TM.c, line 63; 21-competitive-mechanics.md, lines 117-127)
```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = integer
```
Time is NEVER accumulated as floating-point. The tick counter is an integer. No `time += deltaTime` float accumulation. This eliminates the most common source of simulation divergence.

**Mechanism 2: Deterministic sub-stepping** (PhysicsStep_TM.c, lines 71-167; 21-competitive-mechanics.md, lines 130-158)
Given the same velocity state, the sub-step formula produces the same sub-step count. The remainder handling avoids float drift from repeated addition.

**Mechanism 3: Guarded square root** (all physics files; 21-competitive-mechanics.md, lines 162-175)
```c
if (fVar24 < 0.0) {
    fVar24 = safe_sqrt(fVar24);  // prevents NaN
} else {
    fVar24 = SQRT(fVar24);       // SSE sqrtss
}
```
NaN propagation breaks determinism because `NaN != NaN` causes divergent control flow.

**Mechanism 4: Sequential processing order** (NSceneDyna__PhysicsStep_V2.c, lines 103-116; 21-competitive-mechanics.md, lines 178-193)
Bodies and vehicles are processed in **array order**. No parallel dispatch, no random ordering. Collision pair processing order is deterministic.

**Mechanism 5: SSE floating point on x64** (21-competitive-mechanics.md, lines 196-202)
SSE `sqrtss`, `addss`, `mulss` are IEEE 754 compliant. No x87 FPU with 80-bit intermediate precision issues.

**Mechanism 6: Step counter** (NSceneDyna__PhysicsStep_V2.c, line 89; 21-competitive-mechanics.md, lines 60-71)
```c
*(int *)(param_1 + 0xf4b) = (int)param_1[0xf4b] + 1;  // monotonic integer counter
```
No fractional ticks, no variable timestep.

### What Could Break Determinism

| Factor | Risk |
|:---|:---|
| Different executable version | HIGH -- recompilation changes float operation ordering |
| Different CPU architecture (x64 vs ARM) | HIGH -- different rounding for transcendentals |
| Different FPU rounding mode | MEDIUM -- not observed to be explicitly set |
| Multithreaded physics | LOW -- no parallel dispatch observed |
| OS differences | LOW -- SSE is CPU-level, not OS-level |
| Display FPS | NONE -- physics completely decoupled |
| GPU driver | NONE -- physics runs on CPU only |

**WARNING**: TM2020's determinism is "within same build, same platform." Cross-platform determinism is NOT guaranteed. (21-competitive-mechanics.md, line 202)

### WASM Matches and Exceeds This

WASM provides a STRONGER guarantee than TM2020's native SSE approach (06-determinism-analysis.md, lines 26-29):

- TM2020: deterministic within same x64 platform
- WASM: deterministic across ALL platforms (x64, ARM, etc.)

Key WASM advantages (06-determinism-analysis.md, lines 37-43):
- Round-to-nearest, ties-to-even (only mode available)
- No extended precision
- No fast-math allowed by spec
- Full IEEE 754 subnormal support
- Implementations cannot fuse operations

**Critical requirement**: NEVER import browser `Math` functions for physics. Use compiled-in `libm` instead. Browser `Math.sin` varies between implementations. (06-determinism-analysis.md, lines 103-113)

### Fixed-Point vs Floating-Point

I initially considered fixed-point. The analysis (06-determinism-analysis.md, lines 345-399) convinced me NOT to:
- Q16.16 overflows at 32768 -- TM velocities reach 1000+ km/h
- 10-20x slower for basic arithmetic
- WASM's float determinism makes fixed-point unnecessary

### How Confident Am I?

**Very confident**, following these rules (06-determinism-analysis.md, Section 5.2):

1. Use f32 for all physics (same as TM2020)
2. Compile ALL math into WASM (use `libm`, NEVER JavaScript Math)
3. No relaxed SIMD
4. Guard every sqrt (clamp to >= 0.0)
5. Guard every division (check for zero)
6. Integer tick counting (`tick * 1_000_000`)
7. Fixed timestep (100Hz)
8. Sequential processing (no threads in physics)
9. Single `.wasm` binary shipped to all clients
10. Determinism verification hash every tick

---

## The Feel

This chapter covers what makes TM2020's car physics feel distinctive -- gravity, speed, and the interaction of multiple systems. You will understand the design choices behind the "feel."

### What Makes a Car "Feel" Right?

"Feel" comes from:
1. **Responsiveness**: 100Hz physics = max 10ms input delay at the physics level
2. **Predictability**: 3-state drift is more learnable than continuous sliding
3. **Weight**: Exaggerated gravity makes the car feel grounded
4. **Speed sensation**: The 3.6 conversion and block grid scale give consistent speed sense
5. **Surface variety**: 22 gameplay effects create diverse challenges
6. **Consistency**: Deterministic physics means the same inputs always produce the same output

### Gravity is ~3x Earth

From TMNF cross-reference (14-tmnf-crossref.md, lines 216-223):
- TMNF's `GravityCoef = 3.0` multiplies base gravity by 3x
- This gives roughly `3 * 9.81 = 29.43 m/s^2`
- TM2020 exposes `GravityCoef` via ManiaScript
- Default `Modifiers.GravityCoef` in `CPlugVehiclePhyModelCustom` is 1.0 (a multiplier on the base gravity from the spawn model)

Higher gravity means:
- The car lands faster after jumps (less floaty)
- Loop-the-loops require less speed
- Steering feels more responsive (car pushed harder into ground)
- The car feels "heavy" and "planted"

The gravity vector comes from `CPlugSpawnModel` at offset `+0x54`, default `(0, -1.0, 0)`. The binary contains NO hardcoded 9.81 -- gravity magnitude is entirely data-driven. (07-physics-constants.md, lines 7-8; 10-tuning-loading-analysis.md, lines 176-182)

### Speed Display: FrontSpeed x 3.6 = km/h

From Openplanet (19-openplanet-intelligence.md, line 44):
- `FrontSpeed` (float, m/s) is the forward speed component
- `SideSpeed` (float, m/s) is the lateral speed

The displayed speed is FrontSpeed, not total 3D velocity. When you drift sideways, you do not feel faster even though total velocity is higher. This design is correct.

### My Top 10 Takeaways for Building a Physics Engine

1. **Fixed timestep is non-negotiable.** Use integer tick counting. Never accumulate floating-point time. (PhysicsStep_TM.c, line 63)

2. **Adaptive sub-stepping is essential for stability.** Cap at 1000, use velocity-dependent count. (PhysicsStep_TM.c, lines 121-132)

3. **Guard EVERY square root.** The `if (x < 0) safe_sqrt else SQRT` pattern prevents NaN from ever entering the simulation. (PhysicsStep_TM.c, lines 90-95)

4. **Exaggerate gravity.** 3x Earth gravity makes the car feel heavy, responsive, and grounded.

5. **Turbo should ramp UP.** `force = elapsed/duration * strength` creates smooth acceleration peaking at the end. (NSceneVehiclePhy__ComputeForces.c, line 105)

6. **Use a state machine for drift.** 3 discrete states give learnable transitions. (force_model_2wheel_FUN_14086b060.c, lines 12-16)

7. **Separate material physics from gameplay effects.** Two-ID system is a clean architectural separation. (10-physics-deep-dive.md, lines 1422-1438)

8. **Make tuning data-driven.** TM2020 has ZERO hardcoded tuning constants. Everything comes from GBX resource files. (07-physics-constants.md, lines 7-8)

9. **Use speed-dependent curves for everything.** Grip, engine force, steering -- all sampled from piecewise curves via cubic Hermite interpolation. (22-ghidra-gap-findings.md, lines 100-117)

10. **Sequential processing for determinism.** No parallel physics dispatch. Process in array order. (NSceneDyna__PhysicsStep_V2.c, lines 103-116)

### Bonus Observations

**Vehicle state is HUGE.** 7,328+ bytes per entity, 3.5x TMNF's 2,112 bytes. (10-physics-deep-dive.md, line 379)

**The sleep system is elegant.** When velocity drops below threshold (0.01 m/s), velocity is multiplied by 0.9 each frame, gradually damping to rest. No visual popping. (NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c, lines 40-57)

**No sticky forces for wall-riding.** The car stays on loops purely through centripetal force + 3x gravity + tire friction. This is emergent physics. (10-physics-deep-dive.md, lines 1334-1356)

**Per-wheel surface detection is independent.** Front wheels can be on asphalt while rear wheels are on ice. Surface friction changes instantly at the boundary. (10-physics-deep-dive.md, lines 1456-1462)

---

## Open Questions (For Future Investigation)

1. **Force model mapping**: Which model (5, 6, or 0xB) does each car type use?
2. **Actual tuning values**: All curves are in encrypted GBX files inside .pak archives. Need Openplanet's Fid Loader to extract. (09-tuning-data-extraction.md, lines 81-95)
3. **Per-wheel force computation**: `FUN_1408570e0` is the heart of the tire model but not fully documented.
4. **Airborne control specifics**: How much pitch/roll/yaw control when airborne?
5. **Solver iteration counts**: Actual values in GBX data.
6. **Water physics**: TMNF data suggests `WaterReboundMinHSpeed = 200 km/h` for skipping.
7. **Steering model**: How does keyboard digital input convert to smooth steering curves?
8. **Anti-roll bar**: `FUN_14085ba50` stiffness and cornering effects.
9. **Burnout state machine**: TMNF had 4 states. Does TM2020 preserve this?
10. **CCD implementation**: The collision system mentions Continuous Collision Detection but I did not find the implementation.

---

## What I Would Do Differently In My Game

1. **Start with the bicycle model.** The 2-wheel model captures 80% of the feel with 20% of the complexity.
2. **Use 120Hz instead of 100Hz.** Cleaner division for 60fps/120fps displays.
3. **Consider Verlet integration.** More stable for the same step count than Forward Euler.
4. **Implement the speed-dependent curve system from day one.** `CFuncKeysReal` with 4 interpolation modes is a fantastic tool.
5. **Build determinism verification hash from the start.** Catches bugs early.
6. **Use WASM for physics.** Stronger determinism guarantees than native code.
7. **Expose vehicle state for modding.** Design the state struct to be modder-friendly from the start.

---

## Related Pages

- [Physics Deep Dive](../re/10-physics-deep-dive.md)
- [Ghidra Gap Findings](../re/22-ghidra-gap-findings.md)
- [Competitive Mechanics](../re/21-competitive-mechanics.md)
- [TMNF Cross-Reference](../re/14-tmnf-crossref.md)
- [Determinism Analysis](../re/06-determinism-analysis.md)
- [Physics Constants](../re/07-physics-constants.md)
- [Openplanet Intelligence](../re/19-openplanet-intelligence.md)
- [Tuning Loading Analysis](../re/10-tuning-loading-analysis.md)

<details><summary>Document metadata</summary>

**Author**: Alex (PhD student, game physics research)
**Date**: 2026-03-27
**Goal**: Learn everything about TM2020's physics to inform my own racing game engine
**Sources**: 18 decompiled C files, 10+ RE documents, TMNF cross-reference, WASM determinism analysis, tuning system analysis

</details>

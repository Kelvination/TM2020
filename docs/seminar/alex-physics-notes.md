# Alex's Physics Engine Study Notes: Trackmania 2020

**Author**: Alex (PhD student, game physics research)
**Date**: 2026-03-27
**Goal**: Learn everything about TM2020's physics to inform my own racing game engine
**Sources**: 18 decompiled C files, 10+ RE documents, TMNF cross-reference, WASM determinism analysis, tuning system analysis

---

## Chapter 1: The Physics Tick

### What I Learned

The fundamental heartbeat of TM2020 is a **100Hz fixed physics tick** -- one simulation step every 10 milliseconds. This is completely decoupled from the display framerate. Whether you run at 30fps or 300fps, the physics outcome is identical for the same inputs.

**Evidence for 100Hz**: The docs mark this as PLAUSIBLE rather than VERIFIED, which is interesting. There is no single decompiled constant that says "100Hz." Instead, the evidence converges from multiple sources:
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
`vehicle+0x1C7C &= 0xFFFFF5FF` -- clears bits 9 and 10 of the ContactPhyFlags bitfield at the start of each tick. These bits are used for collision state tracking within the tick.

**Step 4: Check simulation mode** (line 70)
Only modes 0 (normal) and 3 (normal-alt) proceed to physics computation. Mode 1 is replay (state is copied from replay data instead), mode 2 is spectator. (10-physics-deep-dive.md, line 376)

**Step 5: Compute velocity scale** (line 71)
```c
fVar21 = FUN_14083dca0(vehicle + 0x1280, model_ptr);
fVar25 = fVar21 * (float)param_4[2];  // scale * dt
```
This scale factor feeds into the sub-step count computation.

**Step 6: Compute four velocity magnitudes** (lines 78-116)
This is where it gets really interesting. TM2020 computes FOUR separate velocity magnitudes:
1. `|v_linear|` from body at `lVar15+0x40..0x48` -- the linear velocity of the rigid body
2. `|v_angular|` from body at `lVar15+0x4C..0x54` -- the angular velocity of the rigid body
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
Same 6 function calls, but with the remaining time (`scaled_dt - (sub_dt * (N-1))`). This ensures the total simulated time exactly equals dt -- no floating-point drift!

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

### Adaptive Sub-stepping -- Why and How

The sub-stepping system exists because Forward Euler integration (which TM2020 uses) is notoriously unstable at high velocities. Without sub-stepping, a fast car could tunnel through thin geometry or develop unstable oscillations.

**The formula** (10-physics-deep-dive.md, Section 7.3):
```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
sub_dt = dt / num_substeps
```

The cap is **1000 sub-steps**, reduced from TMNF's 10,000. (14-tmnf-crossref.md, line 188). Why the reduction? I think there are several reasons:
- TM2020's constraint solver is more robust (iterative Gauss-Seidel vs TMNF's analytical friction)
- 1000 sub-steps at 100Hz = 100,000 sub-steps per second, which is already extreme
- TM2020 has 4 vehicle types requiring 4x the testing
- Exceeding 1000 doesn't crash -- it just uses `dt/1000`, which may cause artifacts

### Questions I Still Have

1. What exactly does `FUN_14083dca0` compute for the velocity scale factor? Is it a constant or does it depend on the vehicle's state?
2. The `body_step_size` at `lVar15+0x54` -- where does this value come from? Is it in the tuning data?
3. Why 4 velocity terms instead of TMNF's 2? Are `v_wheel1` and `v_wheel2` the wheel spin velocities?
4. What is the exact value of the tick duration `param_4[2]`? Is it always 0.01 seconds?
5. The "safe sqrt" function `FUN_14195dd00` -- does it return `sqrt(abs(x))` or just `0.0`?

### If I Were Building This

I would absolutely use the same fixed-tick approach. The 100Hz rate is a sweet spot -- fast enough for responsive gameplay, slow enough to not burn CPU time. I might consider 120Hz for smoother feel on modern displays, but the 100Hz quantization means times are always multiples of 10ms, which is clean for competitive timing.

The adaptive sub-stepping is genius. I would implement it exactly the same way, but I might add a second cap: if `num_substeps > 50`, log a warning because something unusual is happening (very high speed or small step size parameter).

The remainder-step approach (N-1 equal steps + 1 remainder) is much better than what I initially had in my prototype (just `N * sub_dt` which drifts). I am changing this immediately.

### What Surprised Me

The 4-velocity-term sub-step count. I expected only linear velocity to matter. Including angular velocities makes sense for rapid spinning, but the two extra "wheel velocity" terms from the vehicle state are unexpected. This suggests the sub-stepping is trying to capture the dynamics of the WHEELS, not just the chassis. Very clever.

Also, the fact that the tick rate is never hardcoded as a constant. The entire system works with whatever tick duration it receives. This is good engineering -- it means you could theoretically run at 200Hz just by changing a config value.

---

## Chapter 2: Vehicle Forces

### The Force Model Dispatch System

At the heart of TM2020's vehicle physics is a **switch statement** at `NSceneVehiclePhy__ComputeForces.c:142-162` that dispatches to different force computation functions based on the value at `vehicle_model+0x1790`:

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

There are **8 case values** mapping to **6 actual functions**. The mapping:

| Switch Value | Function | TMNF Equivalent | Likely Car Type | Param Count |
|:---:|:---:|:---:|:---:|:---:|
| 0, 1, 2 | FUN_140869cd0 | Steer01/02/03 | Base/legacy | 2 |
| 3 | FUN_14086b060 | Steer04 (M4) | Bicycle/simplified | 2 |
| 4 | FUN_14086bc50 | Steer05 (M5) | TMNF-era | 2 |
| 5 | FUN_140851f00 | Steer06 (M6) | CarSport/Stadium | 3 |
| 6 | FUN_14085c9e0 | NEW | Rally/Snow | 3 |
| 0xB | FUN_14086d3b0 | NEW | Desert/variant | 3 |

(10-physics-deep-dive.md, lines 170-177; 14-tmnf-crossref.md, lines 350-372)

The critical difference: **models 5, 6, and 0xB receive an extra `param_4` (tick/time parameter)** that enables time-dependent effects like turbo decay curves, time-limited boost effects, cruise control timing, and vehicle transform transition physics. (10-physics-deep-dive.md, lines 192-198)

### Before the Switch: The Pre-Model Setup

Before dispatching to the force model, ComputeForces does several things:

**Force accumulator selection** (lines 128-137):
```c
if (model+0x1790 < 6) {
    force_vec = vehicle+0x144C;  // old layout
} else {
    force_vec = vehicle+0x1534;  // new layout (232 bytes later!)
}
```
Models 6+ use a fundamentally reorganized force layout within the vehicle state. The 232-byte gap (`0x1534 - 0x144C = 0xE8`) is large enough for an entire set of per-wheel data. (10-physics-deep-dive.md, lines 200-221)

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

**Wait -- I initially thought CarSport was case 5.** The documentation in 10-physics-deep-dive.md (line 275) says CarSport is model 5, but the Ghidra gap findings (22-ghidra-gap-findings.md, lines 67-99) explicitly identify FUN_14085c9e0 (case 6) as "the full CarSport (Stadium car) force model." The comment header in the decompiled file `force_model_carsport_FUN_14085c9e0.c` says "This is the primary force model for the Stadium car (CarSport)."

This is a contradiction I need to flag. The mapping is uncertain. Let me accept the decompiled file headers as more authoritative since they are based on deeper analysis.

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

**Speed thresholds**: `tuning+0x2AE0` (low) and `+0x2AE4` (high) define a speed range that affects grip behavior.

**Post-respawn force**: A fade-out force is applied for `2x duration` stored at `tuning+0x2B80`, linearly fading from full to zero. (22-ghidra-gap-findings.md, lines 92-94)

### The Pacejka-Like Tire Model

The 2-wheel model (case 3, FUN_14086b060) has its lateral grip function fully decompiled as `FUN_14086af20` (22-ghidra-gap-findings.md, lines 144-159):

```
lateral_force = -slip * linear_coef - slip * |slip| * quadratic_coef
```

This is a **simplified Pacejka-like model**. The real Pacejka Magic Formula is `F = D * sin(C * atan(B*x - E*(B*x - atan(B*x))))`, which is much more complex. TM2020's version uses a quadratic approximation:
- Linear stiffness at `tuning+0x1A5C` (the "cornering stiffness")
- Quadratic stiffness at `tuning+0x1A60` (the self-limiting term)
- Grip limit from speed-dependent curve at `tuning+0x1AC0`
- Drift reduces grip by factor at `tuning+0x1B10`

When force exceeds grip: clamp to grip limit, set sliding flag.
When force is within grip: use computed force, clear sliding flag.

This is elegant. The linear term provides realistic feel at small slip angles. The quadratic term (`slip * |slip|`) naturally saturates at high slip -- it is the slip squared but preserving sign. No need for a complex sin/atan chain.

### The 3-State Drift Machine

The drift system in the 2-wheel model has 3 discrete states stored at `offset+0x1460` (22-ghidra-gap-findings.md, lines 58-63; force_model_2wheel_FUN_14086b060.c, lines 12-16):

| State | Value at +0x1460 | Behavior |
|:---:|:---:|:---|
| No drift | 0 | Normal lateral grip, no drift angle |
| Drift building | 1 | Slip accumulating at +0x1458, building drift angle |
| Drift committed | 2 | Using stored drift angle, reduced grip |

**Drift builds** proportional to `lateral_slip * drift_rate * delta_time` (tuning+0x1B6C).
**Drift angle** is clamped by max value at `tuning+0x1B78`.

This is a state machine, not a continuous model. The transitions are discrete. When you start sliding, you enter state 1. Slip accumulates. Once the drift angle reaches some threshold, you commit (state 2). In state 2, the stored angle is used for force calculations and grip is reduced by the factor at `tuning+0x1B10`.

### Engine / RPM Simulation

From the Openplanet data (19-openplanet-intelligence.md, lines 56-59):
- `CurGear`: uint, 0-7 (8 gears total -- TMNF only had 6!)
- `RPM`: float, 0-11000 (vs TMNF's ~10000)
- `EngineOn`: bool

**Is RPM real or cosmetic?** Based on the TMNF analysis (where M6 was fully decompiled), RPM IS simulated. In TMNF's M6 model, RPM determines gear shift timing, engine torque output via the torque curve, and burnout state machine entry conditions. (10-physics-deep-dive.md, lines 1626-1631)

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

Max RPM = 7000, Shift RPM = 6500.

I note these are DEFAULT values from the constructor. The actual values loaded from GBX may differ. But these give a sense of the gear ratios.

### What Makes TM2020 Feel Different

After reading all of this, I think the "TM2020 feel" comes from several interacting systems:

1. **Exaggerated gravity** (~3x Earth, see Chapter 6) makes the car feel heavy and planted
2. **Turbo ramps UP** not down -- you feel the kick at the END of the boost, not the beginning
3. **State-machine drift** gives discrete, predictable transitions rather than a continuous sliding feel
4. **Speed-dependent curves everywhere** -- grip, engine force, steering sensitivity all change with speed
5. **The 4 independent wheels** each detecting their own surface and computing their own forces
6. **Reactive sub-stepping** -- the simulation gets finer when you go faster, preventing artifacts

### Questions I Still Have

1. Which force model does each car ACTUALLY use? The documentation contradicts itself (CarSport = 5 vs CarSport = 6).
2. How does the burnout state machine work in TM2020? TMNF had 4 states (normal/burnout/donut/after-burnout).
3. What are the actual tire force curves? They are in GBX tuning data, not the binary.
4. How does the per-wheel force function (`FUN_1408570e0`) work? It is called 4 times in the CarSport model.
5. What is the airborne control model? `FUN_14085c1b0` applies pitch/yaw/roll forces when airborne -- how much control does the player actually have?

### If I Were Building This

I would start with the 2-wheel bicycle model (case 3) as my base. It is simpler but captures the essential physics:
- Longitudinal/lateral force decomposition via sin/cos of steering angle
- The quadratic lateral grip model (`-slip * B - slip*|slip| * C`) is elegant and cheap
- The 3-state drift machine is easy to tune and gives predictable behavior

Then I would add per-wheel forces as a second iteration, using the 4-wheel base model (case 0/1/2) as reference.

I would NOT try to match TM2020's exact feel immediately. Instead I would focus on getting the structural architecture right (sub-stepping, force dispatch, surface system) and tune the curves later.

---

## Chapter 3: Turbo and Surface Effects

### Turbo Ramps UP (Not Down!)

This was the single most surprising finding in all the documentation. Let me lay out the evidence.

**The decompiled code** at NSceneVehiclePhy__ComputeForces.c, lines 104-106:
```c
local_b8 = ((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) *
           *(float *)(lVar6 + 0x16e4) * *(float *)(*(longlong *)(lVar6 + 0x1bb0) + 0xe0);
```

Translating:
```
force = ((current_tick - start_tick) / duration) * strength * model_scale
```

At `t=0` (moment you hit the turbo pad): `force = 0 * strength = 0`.
At `t=duration` (boost about to expire): `force = 1.0 * strength * scale = MAX`.

**TMNF was the opposite**: `force = (1.0 - t/duration) * strength` -- force DECAYS from max to zero. (14-tmnf-crossref.md, lines 488-504)

**What this feels like**: In TM2020, when you hit a turbo pad, you get... nothing initially. The force builds gradually, reaching maximum at the instant the boost expires. This creates a smooth acceleration curve rather than an instant jolt. (10-physics-deep-dive.md, lines 1307-1318)

**Competitive implications** (21-competitive-mechanics.md, lines 381-393):
- The moment you touch a turbo pad, you get almost nothing
- Maximum acceleration happens at the very end of the boost duration
- For TAS: the timing of WHEN you hit a turbo relative to corners matters differently than in TMNF
- You accelerate MORE as the boost is about to expire

### Boost Parameters

The boost system uses three fields per vehicle (10-physics-deep-dive.md, lines 539-576):

| Offset | Type | Field | Purpose |
|:---:|:---:|:---:|:---|
| `+0x16E0` | uint | Duration | Duration in ticks |
| `+0x16E4` | float | Strength | Force multiplier |
| `+0x16E8` | uint | StartTime | Tick when boost started (-1 = no boost) |

When the start time is -1 (0xFFFFFFFF), the first ComputeForces call with an active boost records the current tick. An event is dispatched to the arena (for audio/visual effects) if the event system is active.

The actual duration and strength values for Turbo and Turbo2 are NOT in the binary -- they are in GBX tuning data. From TMNF cross-reference: Turbo=5.0/250ms, Turbo2=20.0/100ms. TM2020 values may differ. (10-physics-deep-dive.md, lines 1326-1330)

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

**Critical architectural insight**: Gameplay effects are NOT driven by surface materials. All 208 materials in the game have `DGameplayId(None)`. Effects come from block/item trigger zones, not surface textures. (21-competitive-mechanics.md, line 366)

This means there are TWO independent surface systems (10-physics-deep-dive.md, lines 1422-1438):
- `EPlugSurfaceMaterialId` -- controls friction, sound, particles, skid marks (per-wheel, updated per tick)
- `EPlugSurfaceGameplayId` -- controls turbo, reset, no-grip, slow-motion etc. (block/item trigger zones)

### NoGrip

NoGrip (surface ID 1) reduces the grip coefficient to zero via the material property at `material+0x18`. It is triggered by `BeginNoGrip`/`EndNoGrip` events. Can also be applied as a handicap with configurable duration (`HandicapNoGripDuration`). A deprecated version (`Hack_NoGrip_Deprecated`) exists, suggesting an older implementation. (22-ghidra-gap-findings.md, lines 250-261)

### SlowMotion

SlowMotion (surface ID 12) modifies the time scale for the affected vehicle. Applied with a 250ms delay. The time scale factor is stored in tuning data and modifies the delta time parameter in the force model. From Openplanet: `SimulationTimeCoef` (float, 0-1) is exposed in the VisState. (22-ghidra-gap-findings.md, lines 276-285; 19-openplanet-intelligence.md, line 106)

This is fascinating -- it does not slow down the ENTIRE game, just that vehicle's physics simulation. Other vehicles continue at normal speed.

### Fragile

The fragile surface break condition requires ALL THREE conditions simultaneously (PhysicsStep_TM.c, lines 191-195; 21-competitive-mechanics.md, lines 413-434):

1. Bits 11 AND 12 of ContactPhyFlags both set (mask 0x1800)
2. Collision severity at `vehicle+0x1C8C` exceeds global threshold `DAT_141d1ef7c`
3. Status nibble is NOT 2 or 3

**Key insight**: Fragile is NOT "any contact = break." There is a collision severity threshold. Gentle landings survive. The exact threshold value is unknown (it is a float at address `0x141d1ef7c`, which the physics constants doc identifies as value 0.1). (07-physics-constants.md, line 22)

Applied with a 250ms delay: "Activate or Deactivate Fragile on the player's vehicle with a 250ms delay." (22-ghidra-gap-findings.md, line 272)

### Reactor Boost -- The Flying Car

TM2020 has four reactor boost variants (21-competitive-mechanics.md, lines 482-493):

| Variant | Behavior |
|:---|:---|
| ReactorBoost_Legacy | Non-directional -- boost in car's current direction |
| ReactorBoost2_Legacy | Non-directional, stronger |
| ReactorBoost_Oriented | **Directional** -- boost in the PAD'S orientation |
| ReactorBoost2_Oriented | **Directional, stronger** |

The "Oriented" variants are NEW in TM2020. They apply force in the direction the pad is facing, not the car. This means approach angle to the pad matters. For competitive play, this creates a much richer optimization space.

The CarSport model has a dedicated sub-function for airborne control: `FUN_14085c1b0` applies pitch/yaw/roll control forces when wheels are not in contact with ground. The reactor air control vector is exposed in Openplanet as `ReactorAirControl` (vec3). (22-ghidra-gap-findings.md, line 85; 19-openplanet-intelligence.md, line 83)

### How Would I Implement Surface Effects

I would use a component-based approach:

```
SurfaceEffect (enum) -> EffectHandler (trait/interface) -> VehicleState mutation
```

Each effect would be a discrete component that can be applied/removed:
- **Modifier effects** (NoGrip, NoBrakes, NoSteering): zero out the relevant coefficient
- **Force effects** (Turbo, ReactorBoost, ForceAcceleration): add to force accumulator
- **Time effects** (SlowMotion): scale dt before passing to force model
- **State effects** (Fragile, FreeWheeling): set flags that alter behavior
- **Transform effects** (VehicleTransform_*): swap the force model and tuning data

The 250ms delay for most ManiaScript-triggered effects (Fragile, SlowMotion, Cruise, etc.) is interesting. I think this prevents exploits where map creators could toggle effects at the exact tick boundary to cause unexpected behavior.

---

## Chapter 4: Collision System

### The Full Pipeline

From the decompiled code, the collision pipeline runs as follows (10-physics-deep-dive.md, lines 1364-1392):

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

Each physics frame begins by copying current positions to "previous" for collision backtracking (10-physics-deep-dive.md, lines 650-690):

```c
for each collidable item:
    item+0x94 = item+0x74;  // prev_pos = cur_pos (vec3)
    item+0xA4 = 0xFFFFFFFF; // reset hit body index
```

Two separate collision item sets exist at manager offsets `+0x9C8` and `+0xA58`, suggesting separation of static and dynamic collidable objects.

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

The layer system uses a global table at `DAT_141fabc20` mapping collision type bytes to layer masks: `actual_mask = layer_table[type] & ~body_exclusion_mask`. This allows per-body collision filtering.

Compound collision shapes (type 0x0D) get special treatment: their sub-shape pointer and body transform are stored in the cache entry. (10-physics-deep-dive.md, lines 730-734)

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

This is a **sequential impulse / Gauss-Seidel style** constraint solver. The separate iteration counts for static friction, dynamic friction, velocity, and position are a huge design choice. Most game physics engines (like Box2D or Bullet) use a single iteration count for all constraint types. Having separate counts lets you tune convergence per category -- for example, you might want very accurate static friction (to prevent sliding on ramps) but fewer dynamic friction iterations (because sliding is less sensitive to exact values).

### Contact Merging Algorithm

From `NHmsCollision__MergeContacts.c` (10-physics-deep-dive.md, lines 752-808):

When a car hits a wall, multiple contact points are generated (one per mesh triangle in the collision zone). The merge algorithm:

**Phase 1: Find merge candidates**
For each pair (i, j) where j > i:
- Distance check: `|pos_i - pos_j| < distance_threshold`
- Normal check: `dot(normal_i, normal_j) > dot_threshold`
- Layer check: neither contact has type 1
- If all pass, add to merge group

**Phase 2: Execute merges**
For each group:
- Average positions, normals, impulses across all contacts in the group
- Normalize the averaged normal
- Write result to the "survivor" contact
- Clear the "needs merge" flag (bit 1)

**Phase 3: Remove consumed contacts**
Sort consumed indices, remove in reverse order.

This reduces solver jitter from too many redundant constraints at the same point. Without merging, the solver might oscillate between conflicting constraints.

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

There are at least **7 separate contact buffers** (at vehicle offsets 0x188, 0x198, 0x1A8, 0x1B8, 0x1C8, 0x1D8, 0x1E8), each cleared after processing. This suggests categorized contact types. (10-physics-deep-dive.md, line 497)

### How Does the Car Bounce Off Walls?

The `MinVelocityForRestitution` parameter defines the minimum impact velocity for a bounce. Below this threshold, the collision is purely inelastic (no bounce). The actual coefficient of restitution is likely per-material, not in the solver params. The `Bouncy` gameplay surface confirms restitution is per-surface configurable. (10-physics-deep-dive.md, lines 1394-1402)

### What is the Simplest Collision System That Would Feel Right?

For my game, I think the minimal viable system needs:
1. **Broadphase**: Grid or BVH for spatial acceleration (TM2020 uses tree-based spatial acceleration)
2. **Per-wheel raycasts**: 4 rays from the chassis downward for ground detection (both TMNF and TM2020 do this)
3. **Contact generation**: Mesh-vs-convex hull for car body collisions
4. **Sequential impulse solver**: With at least separate static/dynamic friction iterations
5. **Contact merging**: Average nearby same-normal contacts to prevent jitter
6. **Depenetration**: Position correction to prevent the car from sinking into walls

I could skip compound shapes (type 0xD), the 7 contact buffer categories, and the layer mask system initially. The core "feel" comes from the solver parameters and the tire friction model, not from collision detection sophistication.

### Questions I Still Have

1. What are the actual iteration counts? Are they 4? 8? 16? The typical range is 1-20 per the SSolverParams definition.
2. How does continuous collision detection (CCD) work? The code mentions "Discrete" and "Continuous" modes but I did not see CCD implemented in the decompiled files.
3. The "VelBiasMode" parameter -- what modes exist? This likely controls how penetration correction interacts with velocity.
4. Why 7 contact buffers? What are they categorized by?

---

## Chapter 5: Determinism

### Why Determinism Matters

Trackmania's replay system records **inputs**, not positions. When you watch a ghost or validate a replay, the game re-runs the physics with the recorded inputs. The server re-simulates runs to verify claimed times. If the physics is not deterministic, this entire system breaks. (21-competitive-mechanics.md, lines 111-116)

The replay state copy is 2,168 bytes (`0x878`), which includes the complete force model configuration, velocity state, and all wheel data. (21-competitive-mechanics.md, lines 236-241)

### The 6 Mechanisms TM2020 Uses

**Mechanism 1: Integer-based timing** (PhysicsStep_TM.c, line 63; 21-competitive-mechanics.md, lines 117-127)
```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = integer
```
Time is NEVER accumulated as floating-point. The tick counter is an integer. The conversion to microseconds uses integer multiplication. No `time += deltaTime` floating-point accumulation. This eliminates the most common source of simulation divergence.

**Mechanism 2: Deterministic sub-stepping** (PhysicsStep_TM.c, lines 71-167; 21-competitive-mechanics.md, lines 130-158)
Given the same velocity state, the sub-step formula produces the same number of sub-steps. The remainder handling (`(N-1) * sub_dt + remainder = dt exactly`) avoids float drift from repeated addition.

**Mechanism 3: Guarded square root** (all physics files; 21-competitive-mechanics.md, lines 162-175)
```c
if (fVar24 < 0.0) {
    fVar24 = safe_sqrt(fVar24);  // prevents NaN
} else {
    fVar24 = SQRT(fVar24);       // SSE sqrtss
}
```
This prevents NaN propagation. NaN would break determinism because `NaN != NaN` causes divergent control flow.

**Mechanism 4: Sequential processing order** (NSceneDyna__PhysicsStep_V2.c, lines 103-116; 21-competitive-mechanics.md, lines 178-193)
Bodies and vehicles are processed in **array order** (sequential iteration over a sorted index array). No parallel dispatch, no random ordering. Collision pair processing order is deterministic regardless of memory allocation order.

**Mechanism 5: SSE floating point on x64** (21-competitive-mechanics.md, lines 196-202)
TM2020 uses SSE for all floating-point. SSE `sqrtss`, `addss`, `mulss` are IEEE 754 compliant and produce identical results for identical inputs on the same CPU architecture. No x87 FPU (which had 80-bit intermediate precision issues).

**Mechanism 6: Step counter** (NSceneDyna__PhysicsStep_V2.c, line 89; 21-competitive-mechanics.md, lines 60-71)
```c
*(int *)(param_1 + 0xf4b) = (int)param_1[0xf4b] + 1;  // monotonic integer counter
```
A monotonically increasing integer counter at struct offset 0x7A58. Increments by exactly 1 per physics step. No fractional ticks, no variable timestep.

### What Could Break Determinism

From 21-competitive-mechanics.md, lines 204-215:

| Factor | Risk |
|:---|:---|
| Different executable version | HIGH -- recompilation changes float operation ordering |
| Different CPU architecture (x64 vs ARM) | HIGH -- different rounding for transcendentals |
| Different FPU rounding mode | MEDIUM -- not observed to be explicitly set |
| Multithreaded physics | LOW -- no parallel dispatch observed |
| OS differences | LOW -- SSE is CPU-level, not OS-level |
| Display FPS | NONE -- physics completely decoupled |
| GPU driver | NONE -- physics runs on CPU only |
| Resolution / graphics | NONE -- rendering has no feedback to physics |

**WARNING**: TM2020's determinism is "within same build, same platform." Cross-platform determinism is NOT guaranteed. (21-competitive-mechanics.md, line 202)

### Can WASM Match This? YES.

This is where the WASM determinism analysis (06-determinism-analysis.md) gets really exciting.

**WASM's core guarantee** (06-determinism-analysis.md, lines 26-29):
> If neither the inputs to nor the output from a floating-point instruction is NaN, then the output is deterministic and agrees across all platforms.

WASM actually provides a STRONGER guarantee than TM2020's native SSE approach:
- TM2020: deterministic within same x64 platform
- WASM: deterministic across ALL platforms (x64, ARM, etc.)

**Key WASM advantages** (06-determinism-analysis.md, lines 37-43):
- Round-to-nearest, ties-to-even (only mode available)
- No extended precision (no x87-style 80-bit intermediates)
- No fast-math allowed by spec
- Full IEEE 754 subnormal support
- Implementations cannot fuse operations (`a*b + c` always rounds twice)

**The critical requirement**: NEVER import browser `Math` functions for physics. Use compiled-in `libm` instead. Browser `Math.sin` is explicitly allowed to vary between implementations. A compiled `libm` produces identical WASM bytecode on all engines. (06-determinism-analysis.md, lines 103-113)

**The NaN question**: The ONLY nondeterminism in WASM is NaN bit patterns. But if NaN never appears in the simulation (prevented by TM2020's guarded-sqrt pattern), this does not matter. (06-determinism-analysis.md, lines 74-82, 97-101)

### Fixed-Point vs Floating-Point

I was initially considering fixed-point arithmetic for my game. The analysis at 06-determinism-analysis.md (lines 345-399) convinced me NOT to:

- Q16.16 overflows at 32768 -- velocities in TM reach 1000+ km/h
- Basic arithmetic is 10-20x slower in fixed-point
- Every formula must be rewritten
- WASM's float determinism makes fixed-point unnecessary

Fixed-point is for situations where you cannot control the float implementation (native cross-compilation). WASM gives us a controlled, spec-compliant environment.

### How Confident Am I That My Game Could Be Deterministic?

**Very confident**, if I follow these rules (06-determinism-analysis.md, Section 5.2):

1. Use f32 for all physics (same as TM2020)
2. Compile ALL math into WASM (use `libm` for sin/cos/atan2, NEVER JavaScript Math)
3. No relaxed SIMD (standard SIMD only)
4. Guard every sqrt (clamp to >= 0.0)
5. Guard every division (check for zero)
6. Integer tick counting (`tick * 1_000_000`)
7. Fixed timestep (100Hz)
8. Sequential processing (no threads in physics)
9. Single `.wasm` binary shipped to all clients
10. Determinism verification hash every tick

The reasoning chain is clear: WASM basic float ops are spec-deterministic -> NaN prevention eliminates the nondeterministic path -> compiled `libm` ensures transcendentals are deterministic -> same `.wasm` binary ensures identical bytecode -> fixed timestep and integer time ensure identical seeding.

---

## Chapter 6: The Feel

### What Makes a Car "Feel" Right?

After studying all of this, I think "feel" in a racing game comes from:

1. **Responsiveness**: Input-to-visual-response latency. TM2020's 100Hz physics means max 10ms input delay at the physics level.
2. **Predictability**: The state machine drift (3 states) is more predictable than a continuous model. Players can learn the transitions.
3. **Weight**: Exaggerated gravity makes the car feel grounded and substantial.
4. **Speed sensation**: The 3.6 conversion factor (m/s to km/h) and the block grid scale give a consistent sense of speed.
5. **Surface variety**: 22 gameplay effects and multiple material types create diverse challenges.
6. **Consistency**: Deterministic physics means the same inputs always produce the same output. Players can practice.

### Gravity is ~3x Earth

From the TMNF cross-reference (14-tmnf-crossref.md, lines 216-223):
- TMNF's `GravityCoef = 3.0` (from tuning GBX) multiplies base gravity by 3x
- This gives roughly `3 * 9.81 = 29.43 m/s^2`
- TM2020 exposes `GravityCoef` via `SetPlayer_Delayed_GravityCoef` ManiaScript
- The default `Modifiers.GravityCoef` in `CPlugVehiclePhyModelCustom` is 1.0 (a multiplier on the base gravity from the spawn model)

**Why 3x gravity?** This is the secret sauce. Higher gravity means:
- The car lands faster after jumps (less floaty)
- Loop-the-loops require less speed to maintain contact (centripetal force threshold is lower relative to gravity)
- Steering feels more responsive because the car is pushed harder into the ground
- Acceleration/braking is more dramatic
- The car feels "heavy" and "planted" even at high speeds

The gravity vector comes from `CPlugSpawnModel` at offset `+0x54` (DefaultGravitySpawn), default `(0, -1.0, 0)`. The binary contains NO hardcoded 9.81 or 29.43 -- the actual gravity magnitude is entirely data-driven. (07-physics-constants.md, lines 7-8; 10-tuning-loading-analysis.md, lines 176-182)

From the gravity computation code (NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c, lines 59-84):
```
gravity_scale = FUN_1407f5130_result * body_mass
force += gravity_scale * gravity_direction
vel += force * inv_mass * dt
```
Gravity is applied as a force, not as a direct velocity change. This means it interacts naturally with the constraint solver.

### The 32m Block Grid

TM2020's track blocks are 32 meters on a side. This constrains the physics design:
- Road width determines minimum turn radius
- Block height determines jump distances
- The car must feel good at the speeds that emerge from 32m turns

The 3.6 conversion factor (m/s to km/h) at address `0x141d1f71c` (07-physics-constants.md, line 20) is the standard conversion. So when the game shows 300 km/h, that is 83.3 m/s internally. At that speed, you cross one 32m block every 0.38 seconds. The physics tick (10ms) gives about 38 ticks per block at full speed.

### Speed Display: FrontSpeed x 3.6 = km/h

From Openplanet (19-openplanet-intelligence.md, line 44):
- `FrontSpeed` (float, m/s) is the forward speed
- Multiply by 3.6 for km/h display
- `SideSpeed` (float, m/s) is the lateral speed

Is this the "real" speed? FrontSpeed is the component of velocity along the car's forward direction. The total 3D speed (magnitude of `WorldVel`) could be different if the car is sliding sideways or falling. The speed displayed to the player is FrontSpeed -- the speed in the direction you are facing. This feels "right" because when you are drifting sideways, you do not feel faster even though your total velocity is higher.

There is also `CruiseDisplaySpeed` (int) which shows the speed during cruise control mode. (19-openplanet-intelligence.md, line 109)

### My Top 10 Takeaways for Building a Physics Engine

1. **Fixed timestep is non-negotiable.** Use integer tick counting. Never accumulate floating-point time. TM2020 uses `tick * 1000000` (integer multiplication) and it eliminates the most common source of simulation divergence. (PhysicsStep_TM.c, line 63)

2. **Adaptive sub-stepping is essential for stability.** The velocity-dependent sub-step count (`floor(speed * scale * dt / step_size) + 1`, capped at 1000) prevents tunneling and instability at high speeds while avoiding unnecessary work at low speeds. (PhysicsStep_TM.c, lines 121-132)

3. **Guard EVERY square root.** The `if (x < 0) safe_sqrt else SQRT` pattern prevents NaN from ever entering the simulation. NaN propagation is the silent killer of determinism. (PhysicsStep_TM.c, lines 90-95)

4. **Exaggerate gravity.** 3x Earth gravity makes the car feel heavy, responsive, and grounded. Real gravity would make loops, wall-rides, and jumps feel floaty and unrealistic for an arcade racer.

5. **Turbo should ramp UP.** TM2020's ramp-up boost (`force = elapsed/duration * strength`) creates smooth acceleration that peaks at the end. This feels more controlled than an instant kick that decays. (NSceneVehiclePhy__ComputeForces.c, line 105)

6. **Use a state machine for drift.** The 3-state drift machine (no drift / building / committed) gives discrete, learnable transitions. Players can predict when the car will start and stop sliding. (force_model_2wheel_FUN_14086b060.c, lines 12-16)

7. **Separate material physics from gameplay effects.** TM2020's two-ID system (EPlugSurfaceMaterialId for friction, EPlugSurfaceGameplayId for turbo/reset/etc.) is a clean architectural separation. (10-physics-deep-dive.md, lines 1422-1438)

8. **Make tuning data-driven.** TM2020 has ZERO hardcoded tuning constants in the binary. Everything -- gravity, friction curves, engine curves, gear ratios, suspension parameters -- comes from GBX resource files. This means you can tune without recompiling. (07-physics-constants.md, lines 7-8)

9. **Use speed-dependent curves for everything.** Grip, engine force, steering sensitivity, braking force -- all are sampled from piecewise curves via `CFuncKeysReal` (cubic Hermite: `3t^2 - 2t^3` interpolation). This gives designers fine-grained control over how the car feels at every speed. (22-ghidra-gap-findings.md, lines 100-117)

10. **Sequential processing for determinism.** No parallel physics dispatch. Process vehicles and bodies in array order. The determinism guarantee that enables replays and ghost validation depends on this. (NSceneDyna__PhysicsStep_V2.c, lines 103-116)

### Bonus Observations

**The vehicle state struct is HUGE.** 7,328+ bytes per vehicle entity. That is 3.5x TMNF's 2,112 bytes, reflecting 64-bit pointers, 4 vehicle types, reactor/boost systems, and expanded contact tracking. (10-physics-deep-dive.md, line 379)

**The sleep system is elegant.** When a body's velocity drops below a threshold (stored at `DAT_141ebcd04`, value 0.01 m/s per 07-physics-constants.md line 54), its velocity is multiplied by a damping factor (0.9 per 07-physics-constants.md line 53) each frame. It is NOT immediately zeroed -- it gradually damps to rest over multiple frames. This prevents visual popping from bodies snapping to zero velocity. (NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c, lines 40-57)

**There are NO sticky forces for wall-riding.** The car stays on loops and walls purely through centripetal force + 3x gravity + tire friction. No special "adhesion" code. This is an emergent property of the physics, which is beautiful. (10-physics-deep-dive.md, lines 1334-1356)

**The gearbox defaults are fascinating.** 7 forward gears with speed thresholds from 56 to 338 km/h. Max RPM = 7000, shift RPM = 6500. These are constructor defaults that may be overridden by GBX data. (10-tuning-loading-analysis.md, lines 145-157)

**Per-wheel surface detection is independent.** Each wheel's `GroundContactMaterial` is updated every physics tick based on raycast hit. You can have front wheels on asphalt and rear wheels on ice simultaneously. Surface friction changes instantly at the boundary (no blending). (10-physics-deep-dive.md, lines 1456-1462)

---

## Open Questions (For Future Investigation)

These are things I could not answer from the available documentation:

1. **Force model mapping**: Which force model (5, 6, or 0xB) does each car type actually use? The documentation contradicts itself.

2. **Actual tuning values**: All friction curves, engine curves, suspension parameters, gear ratios are in encrypted GBX files inside .pak archives. Need to extract via Openplanet's Fid Loader plugin. (09-tuning-data-extraction.md, lines 81-95)

3. **Per-wheel force computation**: `FUN_1408570e0` (called 4 times in the CarSport model) is the heart of the tire model but is not fully documented in the files I read.

4. **Airborne control specifics**: How much pitch/roll/yaw control does the player have when airborne? What forces does `FUN_14085c1b0` apply?

5. **Solver iteration counts**: The actual values for FrictionStaticIterCount, FrictionDynaIterCount, VelocityIterCount, and PositionIterCount are in GBX data.

6. **Water physics**: `FUN_1407fb580` computes buoyancy and drag but is not decompiled. TMNF data suggests `WaterReboundMinHSpeed = 200 km/h` for skipping across water.

7. **The steering model**: How does keyboard digital input get converted to the smooth steering curves? Is there a ramp-up filter in the input system or in the force model?

8. **Anti-roll bar**: `FUN_14085ba50` applies anti-roll forces. What is the bar stiffness? How does it affect cornering?

9. **Burnout state machine**: TMNF had 4 burnout states. Does TM2020 preserve this? It would affect grip at low speeds.

10. **CCD implementation**: The collision system mentions Continuous Collision Detection modes but I did not find the CCD implementation in the decompiled files.

---

## What I Would Do Differently In My Game

1. **Start with the bicycle model.** The 2-wheel model (case 3) captures 80% of the feel with 20% of the complexity. Add 4-wheel physics later.

2. **Use 120Hz instead of 100Hz.** Cleaner division for 60fps and 120fps displays. Still very efficient. Times would be multiples of ~8.33ms instead of 10ms, which is acceptable.

3. **Consider Verlet integration instead of Forward Euler.** Verlet is more stable for the same step count. TM2020 uses Forward Euler with sub-stepping for stability, but Verlet could let me use fewer sub-steps.

4. **Implement the speed-dependent curve system from day one.** TM2020's `CFuncKeysReal` with 4 interpolation modes (step, linear, cubic Hermite, Catmull-Rom) is a fantastic tool for designers. I would build this as a core data type.

5. **Build the determinism verification hash from the start.** Do not bolt it on later. Compute a state hash every tick from the beginning. This catches determinism bugs early.

6. **Use WASM for the physics engine.** The WASM determinism guarantees are stronger than native code. Ship one `.wasm` binary to all clients. Use compiled `libm` for transcendentals. This gives me cross-platform determinism that TM2020 does not have.

7. **Expose the vehicle state for modding.** TM2020's Openplanet community has done incredible work because the VehicleState is readable from plugins. I would design my state struct to be modder-friendly from the start.

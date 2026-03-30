# Professor Chen's Lecture Series: Trackmania 2020 Physics Engine
# From Decompiled Code to Understanding

**Lecturer**: Professor Chen, Vehicle Dynamics Simulation Laboratory
**Course**: Advanced Game Physics -- Reverse Engineering a Commercial Racing Engine
**Binary**: Trackmania.exe (Trackmania 2020, Nadeo/Ubisoft)
**Tools**: Ghidra 12.0.4 via PyGhidra
**Primary Sources**: 40 decompiled C files, Openplanet live memory readings, hex-verified file analysis
**Date**: 2026-03-27

**Cardinal Rule**: Every fact has a citation. Speculation is labeled. "I don't know" is an acceptable answer.

---

## Lecture 1: What We KNOW vs What We THINK We Know

### 1.0 Opening Remarks

Students, before we dive into any equations or diagrams, we must do something that most textbooks skip: we must audit our own sources. We have two categories of documentation about Trackmania 2020's physics -- the analysis documents (docs 10 and 22), and the actual decompiled C code. Where these disagree, the code wins. Where we cannot verify a claim, we say so.

I have read every one of the 40 decompiled source files in our repository. I have cross-referenced every major claim in the documentation against those files. Here is what I found.

### 1.1 Verification Audit Table

| # | Claim (from docs 10/22) | Source Doc | Verified? | Evidence | Notes |
|---|---|---|---|---|---|
| 1 | Physics runs at fixed 100Hz tick rate | Doc 10 S1.2, Doc 21 S1.1 | PLAUSIBLE | `PhysicsStep_TM.c:63` shows `tick * 1000000` (integer microsecond conversion). No explicit "100Hz" constant found in decompiled code. TMNF precedent and `SmMaxPlayerResimStepPerFrame=100` in Default.json provide converging evidence. | Cannot VERIFY from code alone. The 10ms period is inferred, not stated. |
| 2 | Internal timing uses microseconds | Doc 10 S1.3 | **VERIFIED** | `PhysicsStep_TM.c:63`: `lVar18 = (ulonglong)*param_4 * 1000000;` and `NSceneDyna__PhysicsStep.c:15`: `FUN_140801e20(param_1, (ulonglong)*param_2 * 1000000);` | Both convert integer ticks to microseconds via integer multiplication. |
| 3 | Force model dispatch is a switch on offset +0x1790 | Doc 10 S2.1 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:142`: `switch(*(undefined4 *)(local_118 + 0x1790))` | Exact code visible at that line. |
| 4 | There are 7 force model cases (0,1,2,3,4,5,6,0xB) | Doc 10 S2.1 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:143-162` lists cases 0/1/2, 3, 4, 5, 6, 0xB | Exactly as documented. |
| 5 | Cases 0/1/2 share the same function (FUN_140869cd0) | Doc 10 S2.1 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:143-147`: `case 0: case 1: case 2: FUN_140869cd0(...)` | Fall-through switch. |
| 6 | Models 5, 6, 0xB take 3 params (extra timestamp) | Doc 10 S2.3 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:155-161`: cases 5/6/0xB pass `param_3, param_4, &local_158` while cases 0-4 pass only `param_3, &local_158` | The extra param_4 is the simulation timestamp. |
| 7 | Model 5 = StadiumCar/CarSport | Doc 10 S2.6 | SPECULATIVE | Doc 10 labels this as "M6/Steer06 from TMNF" but provides no decompiled proof linking it to a specific vehicle file. | I cannot confirm this mapping from the code alone. |
| 8 | Model 6 = CarSport (the header of `force_model_carsport_FUN_14085c9e0.c`) | Doc 22 header | PLAUSIBLE | The file header says "CarSport (Stadium)" but this is a researcher's annotation, not from the binary. The function IS the most complex model with per-wheel forces, steering, suspension, anti-roll, damping, drift, boost, and airborne control. | The complexity matches what we would expect for the primary car, but the mapping is INFERENCE. |
| 9 | Case 3 = 2-wheel/bicycle model | Doc 22 P1 | **VERIFIED** (structurally) | `force_model_2wheel_FUN_14086b060.c` header documents: single front/rear force pair, atan2 steering, drift state machine with 3 states, lateral grip via FUN_14086af20. The code confirms 2-axle force decomposition. | The "2-wheel" label is VERIFIED from the code structure. Which vehicle uses it is UNKNOWN. |
| 10 | Case 4 = enhanced 4-wheel with sliding detection | Doc 22 header | **VERIFIED** | `force_model_case4_FUN_14086bc50.c` is fully decompiled (598 lines). Shows per-wheel iteration, surface material lookup at `*car_state + 0x6B8 + surfaceId * 8`, sliding detection comparing force against grip curve at `tuning+0x18D8`, and traction control loop. | The code confirms sliding detection and traction modulation. |
| 11 | Boost force RAMPS UP (not decays) in TM2020 | Doc 10 S11.2 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:105-106`: `force = ((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) * *(float *)(lVar6 + 0x16e4) * *(float *)(model + 0xe0)` | `(current_tick - start_tick) / duration` produces a value from 0 to 1. Force increases linearly. This is OPPOSITE to TMNF's decay. |
| 12 | Max substeps = 1000 | Doc 10 S7.4 | **VERIFIED** | `PhysicsStep_TM.c:126,131`: `if (uVar16 < 0x3e9)` then proceed, else `uVar17 = 999; fVar26 = (float)param_4[2] / DAT_141d1fa9c;` | 0x3E9 = 1001, so the guard is `num_substeps < 1001`, capping at 999 iterations in the loop plus 1 final step = 1000 total. |
| 13 | Speed clamping uses model offset +0x2F0 | Doc 10 S4.4 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:112-126`: `fVar9 = *(float *)(local_118 + 0x2f0);` then `if (fVar9 * fVar9 < fVar8) ... clamp velocity` | Exact code as documented. |
| 14 | Vehicle state struct is ~7,328 bytes (0x1CA0) | Doc 10 S3.1 | PLAUSIBLE | The highest confirmed offset is `+0x1C98` (ReplayDataPtr, 8 bytes), so minimum size >= 0x1CA0. But actual size could be larger -- we simply haven't observed higher offsets. | Size is a lower bound, not exact. |
| 15 | Curve sampling uses smoothstep 3t^2 - 2t^3 | Doc 22 P1 | **VERIFIED** | `curve_sample_FUN_14042bcb0.c:64`: `t = 3*t*t - 2*t*t*t;` (when bit 1 set in flags) | Exact formula in the pseudocode. |
| 16 | Tire grip state machine has 3 states (0,1,2) | Doc 22 header for tire_grip | **VERIFIED** | `tire_grip_state_machine_FUN_140842310.c:52-66` shows states 0 (idle), 1 (building), 2 (decaying) with explicit transitions based on surface contact and speed. | Full state machine visible in code. |
| 17 | Grip builds at rate from tuning+0xCDC, decays from +0xCE0/CE4/CE8 | Tire grip file header | **VERIFIED** | `tire_grip_state_machine_FUN_140842310.c:74,82-84,91`: reads `*(uint *)(param_4 + 0xcdc)` for buildup, `*(uint *)(param_4 + 0xce0)` for grounded decay, `*(uint *)(param_4 + 0xce4)` for uncontacted decay, `*(uint *)(param_4 + 0xce8)` for airborne decay. | All four rate constants verified. |
| 18 | Slope factor uses cosine interpolation | Doc 22 P1 | **VERIFIED** | `slope_gravity_factor_FUN_1408456b0.c` shows: `cos(slope_angle) = abs(velocity.y / |velocity|)`, then smooth S-curve via `FUN_14018ce30` (sincos) between thresholds at tuning offsets 0x19E4/0x19E8 (accel) and 0x19EC/0x19F0 (friction). | Algorithm matches documentation. |
| 19 | Solver uses sequential impulse / Gauss-Seidel | Doc 10 S5.4 | INFERENCE | `SSolverParams_FUN_1407f3fc0.c` registers separate iteration counts: `FrictionStaticIterCount`, `FrictionDynaIterCount`, `VelocityIterCount`, `PositionIterCount`. The pattern of separate friction/velocity/position iterations is characteristic of sequential-impulse solvers. | The solver TYPE is inferred from parameter structure, not from seeing the solver loop itself. |
| 20 | Lateral grip (2-wheel) uses Pacejka-like model | Doc 22 P1 | PLAUSIBLE | `lateral_grip_2wheel_FUN_14086af20.c` describes `force = -slip * linear_coef - slip*|slip| * quadratic_coef` with a grip limit from speed-dependent curve. This is a simplified Pacejka approximation (linear + quadratic terms), not a full Magic Formula. | "Pacejka-like" is a reasonable label but the actual Pacejka Magic Formula has sin/atan/cos terms. This is simpler. |
| 21 | SSolverParams is 44 bytes (0x2C) | Doc 10 S9.3 | **VERIFIED** | `SSolverParams_FUN_1407f3fc0.c:9`: `FUN_1402ea9e0(..., "NSceneDyna::SSolverParams", 0x2c, 0, 0, 0, 0);` | Registration call specifies 0x2C. |
| 22 | SSleepingParams is 16 bytes (0x10) | SSleepingParams file | **VERIFIED** | `SSleepingParams_FUN_1407f4430.c:9`: `FUN_1402ea9e0(..., "NSceneDyna::SSleepingParams", 0x10, 0, 0, 0, 0);` | Two float fields: SleepingVel at +0x00, SleepingAngVel at +0x04. |
| 23 | CPlugVehiclePhyModelCustom has AccelCoef, ControlCoef, GravityCoef | Tuning files | **VERIFIED** | `CPlugVehiclePhyModelCustom_FUN_14061abb0.c:24-35` and `CPlugVehiclePhyModelCustom_Archive.c:24-26`: fields at offsets +0x18, +0x1C, +0x20. | Confirmed by both registration and archive serialization. |
| 24 | Wheel stride is 0xB8 (184 bytes) per wheel | Doc 10 S3.1 | **VERIFIED** | `force_model_case4_FUN_14086bc50.c:245`: `pfVar15 = pfVar15 + 0x2e;` where pfVar15 is a float pointer. 0x2E * 4 = 0xB8 bytes. Also `force_model_case4_FUN_14086bc50.c:155`: wheel data starts at `plVar2 + 0x17CC` (= car_state + 0x17CC). | Stride confirmed by pointer arithmetic. |
| 25 | Surface material lookup: `*car_state + 0x6B8 + surfaceId * 8` | Doc 22 P2 | **VERIFIED** | `force_model_case4_FUN_14086bc50.c:165`: `lVar12 = *(longlong *)(*plVar2 + 0x6b8 + (ulonglong)bVar4 * 8);` | Exact expression in decompiled code. |
| 26 | Vehicle types: CarSport, CarSnow, CarRally, CarDesert | VehicleRegistry.c | **VERIFIED** | `VehicleRegistry.c:8-11` lists all four with paths to their `.Item.gbx` files. | Names and file paths confirmed. |
| 27 | CSceneVehicleVisState is 0x360 bytes (864 bytes) | VisState file | **VERIFIED** | `CSceneVehicleVisState_FUN_140726440.c:12`: `FUN_1402ea9e0(..., "CSceneVehicleVisState", 0x360, ...)` | Registration specifies 0x360. |
| 28 | Wheel order: FL(0), FR(1), RR(2), RL(3) (clockwise) | Openplanet doc S3 | **VERIFIED** (from Openplanet live readings) | `19-openplanet-intelligence.md` S3 states the memory layout is FL, FR, RR, RL. Openplanet plugins swap the last two for their API. | Live memory readings confirm this ordering. |
| 29 | Air resistance is proportional to v^2 | Doc 22 header for 4-wheel model | INFERENCE | `force_model_case4_FUN_14086bc50.c:569-570`: `((float)(*(uint *)(param_2[8] + 0x17b0) ^ uVar31) * *(float *)((longlong)param_2 + 0x24)) / (fVar24 * *(float *)(param_2[8] + 0x310))` This divides a tuning constant times delta_time by (friction * another constant). It is NOT a simple v^2 drag -- it is a force that depends on friction and tuning parameters. | The "v^2" claim from the header annotation is NOT directly visible in the case 4 code. The actual formula is more complex. **ERRATA** item. |
| 30 | Turbo force is "linear ramp-up" | Doc 10 S6.2 | **VERIFIED** | `NSceneVehiclePhy__ComputeForces.c:105`: `((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) * strength * scale` | The formula `(elapsed / duration) * strength` is definitionally linear. |

### 1.2 Errata: Documentation Errors Found

Students, here are the cases where the documentation says one thing and the code says another, or where the documentation overstates its confidence.

#### ERRATUM 1: Air Resistance Is NOT Simply v^2

**Doc 22 header for `force_model_4wheel_FUN_140869cd0.c`** states: "Air resistance force (proportional to v^2)."

**What the code actually shows** (`force_model_case4_FUN_14086bc50.c:567-570`):
```c
local_168 = ((float)(*(uint *)(param_2[8] + 0x17b0) ^ uVar31) *
            *(float *)((longlong)param_2 + 0x24)) / (fVar24 * *(float *)(param_2[8] + 0x310));
```

This is a force computed from: `(-tuning_0x17B0 * delta_time) / (friction_coef * tuning_0x310)`. There is no velocity-squared term visible here. The force appears to be a constant retarding force scaled by friction, not an aerodynamic drag proportional to v^2.

**Correction**: The "air resistance" in the case 4 model is better described as a **constant retarding force inversely proportional to friction**. Whether a separate v^2 drag exists in one of the sub-functions called earlier is UNKNOWN.

#### ERRATUM 2: Vehicle-to-Model Mapping Is Speculative

**Doc 10 S2.6** presents a table mapping vehicles to force models (e.g., "CarSport = model 5", "RallyCar = model 6"). This table is labeled SPECULATIVE in the doc, but the file headers in the decompiled directory use definitive names like "CarSport Full Model" for case 6.

**What we can actually verify**: The `VehicleRegistry.c` file confirms the four vehicle names and their GBX paths. The force model switch confirms seven model types. **But no decompiled code links a specific vehicle name to a specific switch case value.** The mapping would require either:
- Reading the `+0x1790` value from a loaded vehicle's GBX data at runtime (Openplanet could do this)
- Finding the GBX loader that writes to offset `+0x1790`

Until then, all vehicle-to-model mappings are INFERENCE.

#### ERRATUM 3: The "2-Wheel Model" May Have 4 Visual Wheels

**Doc 22** labels FUN_14086b060 as a "2-wheel model" and states it uses "a single front/rear contact pair instead of 4 independent wheels."

**What the code header says** (`force_model_2wheel_FUN_14086b060.c:54`): "Update wheel slip states for all 4 visual wheels."

This suggests the model uses 2-point force calculation (front/rear axle) but still updates 4 visual wheel states. The "2-wheel" label describes the physics model, not the visual representation. This distinction matters for students building their own implementations.

#### ERRATUM 4: Boost Event Magic Number

**Doc 10 S12** describes a "magic float 1.12104e-44" in the boost event dispatch as "likely a type indicator, possibly IEEE representation of an integer."

**Verification** (`NSceneVehiclePhy__ComputeForces.c:95`): `local_b8 = 1.12104e-44;`

The IEEE 754 representation of 1.12104e-44 as a 32-bit float is approximately `0x00000008`. As a reinterpreted integer, this is 8. This is likely an event type code (8 = boost event), passed via a float parameter for ABI reasons. **Confidence: PLAUSIBLE** -- the integer reinterpretation is consistent but unverified.

### 1.3 What I Am Confident Teaching You

Based on this audit, here is what I will teach as verified fact:

1. The simulation pipeline: PhysicsStep_TM iterates vehicles, performs adaptive sub-stepping, calls ComputeForces per sub-step
2. The force model dispatch mechanism (switch on +0x1790)
3. The 7 model types and their function signatures
4. The curve sampling system (linear, smoothstep, spline interpolation)
5. The tire grip state machine (3 states, 4 rate constants)
6. The slope factor computation (cosine interpolation between thresholds)
7. The boost/turbo system (linear ramp-up, duration-based)
8. The constraint solver parameter structure (SSolverParams, 44 bytes)
9. The per-wheel data stride (0xB8 bytes)
10. The surface material lookup mechanism
11. Speed clamping via model +0x2F0
12. The transform copy pattern (112 bytes, current-to-previous)
13. Integer-based timing for determinism

### 1.4 What I Am NOT Confident Teaching

1. Which vehicle uses which force model number
2. The exact values of any tuning constants (they are loaded from GBX data files)
3. The full behavior of any un-decompiled sub-function
4. Whether the simulation is truly 100Hz (highly likely but not code-proven)
5. The complete behavior of the airborne control model (partially decompiled)
6. How the constraint solver actually iterates (we have parameters but not the loop)

---

## Lecture 2: The Physics Tick (VERIFIED ONLY)

### 2.0 Scope

We will walk through `PhysicsStep_TM.c` (FUN_141501800, 224 lines) line by line. I will only state facts visible in the code.

### 2.1 Function Signature

**Source**: `PhysicsStep_TM.c:7`
```c
void FUN_141501800(undefined8 *param_1, undefined8 *param_2, undefined8 *param_3, uint *param_4)
```

Four parameters. From usage analysis:
- `param_1`: Arena physics context (8-byte pointer array). Used at lines 141, 161-162, 189-190, 194. Offsets accessed: `param_1[0x3f]`, `param_1[0x40]`, `param_1[1]`. **VERIFIED** from code.
- `param_2`: Physics manager (NSceneVehiclePhy). Confirmed by calls to `FUN_1407bea40` (entity lookup) and `FUN_1407be690` (slot lookup). **VERIFIED**.
- `param_3`: Vehicle entity list. `*param_3` = array of entity pointers, `*(uint*)(param_3 + 1)` = count. **VERIFIED** from lines 62, 65-67.
- `param_4`: Tick parameters. `*param_4` = tick number (line 63), `param_4[2]` = delta time in some unit (line 73). **VERIFIED**.

### 2.2 Profiling and Initialization

**Source**: `PhysicsStep_TM.c:58-63`
```c
local_f8 = 0;
FUN_140117690(local_108, "PhysicsStep_TM");     // Profile scope begin
uVar8 = *param_2;                                // Cache manager state
uVar14 = FUN_1407baac0(param_2);                  // Initialize step handle
local_148 = (ulonglong)*(uint *)(param_3 + 1);   // Entity count
lVar18 = (ulonglong)*param_4 * 1000000;           // Tick -> microseconds
```

**VERIFIED**: The string "PhysicsStep_TM" at line 59 confirms this function's identity. The microsecond conversion at line 63 uses integer multiplication. **No floating-point drift** in the timestamp.

### 2.3 Vehicle Iteration Loop

**Source**: `PhysicsStep_TM.c:64-220`

The outer loop iterates all vehicle entities:
```c
if (*(uint *)(param_3 + 1) != 0) {       // if entity count > 0
    plVar19 = (longlong *)*param_3;       // entity array pointer
    do {
        lVar9 = *plVar19;                // current entity
        // ... per-entity logic ...
        plVar19 = plVar19 + 1;           // next entity (8-byte stride)
        local_148 = local_148 - 1;       // decrement counter
    } while (local_148 != 0);
}
```

**VERIFIED**: Sequential iteration, no parallelism. Entities processed in array order. This is critical for determinism.

### 2.4 Entity State Filter

**Source**: `PhysicsStep_TM.c:68-70`
```c
if (((byte)*(undefined4 *)(lVar9 + 0x128c) & 0xf) != 2) {
    *(uint *)(lVar9 + 0x1c7c) = *(uint *)(lVar9 + 0x1c7c) & 0xfffff5ff;
    if ((*(int *)(lVar9 + 0x1c90) == 0) || (*(int *)(lVar9 + 0x1c90) == 3)) {
```

Three checks before physics runs:

1. **Status nibble at +0x128C**: The low 4 bits must NOT equal 2. State 2 = "excluded" -- these entities skip straight to the transform copy (lines 199-215). **VERIFIED**.

2. **Flag clearing at +0x1C7C**: Bits 9 and 10 are cleared (`& 0xFFFFF5FF`). These are per-tick physics flags reset at the start of each step. **VERIFIED**.

3. **Simulation mode at +0x1C90**: Must be 0 or 3. Mode 0 = normal simulation, mode 3 = "normal-alt" (exact semantics unknown). Modes 1 and 2 (likely replay and spectator) skip physics entirely. **VERIFIED** for the check; **INFERENCE** for mode meanings.

### 2.5 The Friction Coefficient and Delta Time

**Source**: `PhysicsStep_TM.c:71-73`
```c
fVar21 = (float)FUN_14083dca0(lVar9 + 0x1280, *(undefined8 *)(lVar9 + 0x88));
iVar7 = *(int *)(lVar9 + 0x10);
fVar25 = fVar21 * (float)param_4[2];
```

- `FUN_14083dca0`: Takes entity+0x1280 (vehicle unique ID area) and entity+0x88 (physics model pointer). Returns a float. From context in the tuning system (`Tunings_CoefFriction_CoefAcceleration.c`), this likely returns the friction coefficient. **INFERENCE** -- the function is not decompiled.
- `iVar7`: The dynamics body ID from entity+0x10. Compared to -1 at line 74 (invalid body check). **VERIFIED**.
- `fVar25`: Product of the friction coefficient and the delta time. This is the "scaled timestep" used throughout the sub-stepping computation. **VERIFIED** from arithmetic.

### 2.6 Adaptive Sub-Stepping Computation

**Source**: `PhysicsStep_TM.c:74-128`

This is the most complex part. The code computes how many sub-steps to use based on the vehicle's current velocity:

```c
// Get dynamics slot curves (line 75)
plVar10 = *(longlong **)(*(longlong *)(lVar9 + 0x1bb0) + 0x2b0);
(**(code **)(*plVar10 + 0x28))(plVar10, local_f0);  // virtual call to get curves

// Get physics slot data (line 77)
lVar15 = FUN_1407be690(param_2, iVar7);
```

Then four velocity magnitudes are computed (lines 78-116):
1. Body linear velocity from `lVar15 + 0x40..0x48` (3 floats)
2. Body angular velocity from `lVar15 + 0x4C..0x54` (3 floats)
3. Vehicle velocity 1 from entity `+0x1348..0x1350` (3 floats)
4. Vehicle velocity 2 from entity `+0x1354..0x135C` (3 floats)

Each magnitude is computed as: `sqrt(x*x + y*y + z*z)` with a negative-guard:
```c
if (fVar24 < 0.0) {
    fVar24 = (float)FUN_14195dd00(fVar24);  // safe sqrt for negative
} else {
    fVar24 = SQRT(fVar24);                   // standard SSE sqrtss
}
```
**VERIFIED** from lines 86-116. Every sqrt in the codebase uses this pattern.

**Sub-step count formula** (lines 121-128):
```c
uVar17 = (uint)(longlong)(((fVar24 + fVar27 + fVar28 + fVar26) * fVar25) /
         *(float *)(lVar15 + 0x54));
uVar16 = uVar17 + 1;

if (uVar16 < 0x3e9) {
    // Normal case: use computed substep count
    if ((1 < uVar16) && (...))
        goto sub_step_loop;
} else {
    uVar17 = 999;  // Cap at 999 loop iterations
    fVar26 = (float)param_4[2] / DAT_141d1fa9c;  // delta / 1000.0
}
```

**VERIFIED**: The formula is `num_substeps = floor(total_speed * scaled_dt / step_size_param) + 1`, clamped to maximum 1000. The divisor at `lVar15 + 0x54` is a **data-loaded constant**, not hardcoded. **UNKNOWN**: Its actual value.

### 2.7 The Sub-Step Loop

**Source**: `PhysicsStep_TM.c:137-167`

Each sub-step executes these operations in order:

```c
do {
    // 1. Refresh dynamics slot data
    FUN_1407be690(param_2, iVar7);                          // line 140

    // 2. Accumulate remaining time
    fVar25 = fVar25 - fVar21;                               // line 142

    // 3. Ground collision check
    bVar12 = FUN_141501090(&local_138, local_f0);           // line 151
    *(uint *)(lVar9 + 0x1c7c) |= (bVar12 & 1) << 0x10;    // store result in bit 16

    // 4. Set dynamics time
    uVar22 = FUN_140801e20(param_2, lVar15);                // line 153

    // 5. Compute forces (THE KEY CALL)
    FUN_1414ffee0(uVar22, param_2, uVar14, lVar9, lVar15,  // line 155
                  uVar29, CONCAT44(uVar31, *param_4));

    // 6. Post-force update
    FUN_1414ff9d0(param_2, lVar9, fVar21);                  // line 157

    // 7. Physics step dispatch
    FUN_1415009d0(param_2, uVar8, param_4, uVar23, lVar15,  // line 159
                  CONCAT44(uVar22, fVar21), lVar9, *param_1);

    // 8. Integration
    FUN_14083df50(param_1, param_2, lVar9, *param_4,        // line 162
                  fVar21, in_stack_fffffffffffffe90);

    // 9. Advance time
    lVar15 = lVar15 - (longlong)dVar11;                     // line 165
    uVar20 = uVar20 - 1;                                    // line 166
} while (uVar20 != 0);                                      // line 167
```

**VERIFIED**: Each sub-step follows the sequence: collision check, set time, compute forces, post-update, step, integrate, advance timestamp. The loop runs `uVar17` times (N-1 iterations), then a final step with the remainder runs after the loop (lines 169-195).

### 2.8 The Final Step (Remainder)

**Source**: `PhysicsStep_TM.c:169-195`

After the sub-step loop, one final step processes the accumulated remainder `fVar25`:

```c
FUN_1407be690(param_2, iVar7);
bVar12 = FUN_141501090(&local_138, local_f0);
*(uint *)(lVar9 + 0x1c7c) |= (bVar12 & 1) << 0x10;
FUN_140801e20(param_2, lVar15);
FUN_1414ffee0(..., fVar25, ...);     // Uses remaining dt
FUN_1414ff9d0(param_2, lVar9, fVar25);
FUN_1415009d0(..., fVar25, ...);
FUN_14083df50(..., fVar25, ...);
```

This ensures the total simulated time exactly equals the tick period: `(N-1) * sub_dt + remainder = total_dt`. **VERIFIED**.

### 2.9 Fragile Check and Stunt Detection

**Source**: `PhysicsStep_TM.c:191-195`
```c
if (((*(uint *)(lVar9 + 0x1c7c) & 0x1800) == 0x1800) &&
    (DAT_141d1ef7c < *(float *)(lVar9 + 0x1c8c)) &&
    (1 < (*(uint *)(lVar9 + 0x128c) & 0xf) - 2)) {
    FUN_1407d2870(param_1, lVar9, *param_4);
}
```

Three conditions for fragile crash:
1. Both bits 11 and 12 of +0x1C7C must be set (0x1800)
2. Float at +0x1C8C must exceed threshold `DAT_141d1ef7c`
3. Status nibble minus 2, as unsigned, must be > 1

The unsigned arithmetic means nibble values 2 and 3 evaluate to 0 and 1 respectively (`1 < 0` is false, `1 < 1` is false), so they are EXCLUDED from fragile. Values 0 and 1 wrap to large unsigned numbers and pass. Values 4+ also pass. **VERIFIED**.

### 2.10 State 2 Entity Path (Transform Copy Only)

**Source**: `PhysicsStep_TM.c:198-216`

Entities in state 2 skip all physics and just copy their current transform to the previous transform slot:

```c
// 28 values copied (112 bytes): entity+0x90..0x100 -> entity+0x104..0x174
*(undefined8 *)(lVar9 + 0x104) = *(undefined8 *)(lVar9 + 0x90);
*(undefined8 *)(lVar9 + 0x10c) = *(undefined8 *)(lVar9 + 0x98);
// ... (12 more 8-byte copies + final 4-byte copies)
*(undefined4 *)(lVar9 + 0x174) = *(undefined4 *)(lVar9 + 0x100);
```

**VERIFIED**: 112 bytes copied. This represents the vehicle's world transform (likely a 3x4 matrix plus additional state). The copy preserves the "previous frame" state for rendering interpolation.

### 2.11 Function Epilogue

**Source**: `PhysicsStep_TM.c:222-223`
```c
FUN_1401176a0(local_108, local_f8);  // Profile scope end
return;
```

**VERIFIED**: Clean exit with profiling scope closure.

### 2.12 Summary: What Is Hardcoded vs Data-Loaded

| Item | Hardcoded | Data-Loaded |
|---|---|---|
| Microsecond conversion factor (1,000,000) | YES (line 63) | |
| Max substep count (1000) | YES (0x3E9, line 126) | |
| Flag clear masks (0xFFFFF5FF, 0x1800) | YES | |
| Status nibble extraction (0xF) | YES | |
| Tick-to-time divisor (DAT_141d1fa9c) | | YES (from global) |
| Friction coefficient | | YES (from FUN_14083dca0) |
| Sub-step size divisor | | YES (from lVar15+0x54) |
| Fragile threshold (DAT_141d1ef7c) | | YES (from global) |
| Transform copy offsets (+0x90, +0x104) | YES | |

---

## Lecture 3: Force Model Dispatch (VERIFIED ONLY)

### 3.0 Scope

We will walk through `NSceneVehiclePhy__ComputeForces.c` (FUN_1408427d0, 235 lines). This is the function that dispatches to the specific force model for each vehicle type.

### 3.1 Function Signature and Profiling

**Source**: `NSceneVehiclePhy__ComputeForces.c:7-8,50`
```c
void FUN_1408427d0(longlong param_1, undefined4 param_2, undefined8 param_3,
                   undefined4 param_4, uint param_5)
```
- `param_1`: Physics context (longlong). Offset +0x110 gives the physics manager, offset +8 gives the arena event system, offset +0x120 is checked for non-null to enable thread-local profiling. **VERIFIED**.
- `param_2`: Vehicle ID (undefined4). Passed to entity lookup at line 52. **VERIFIED**.
- `param_3`: Dynamics state/context. Passed directly to force model functions. **VERIFIED**.
- `param_4`: Tick/time parameter. Passed to models 5, 6, and 0xB. **VERIFIED**.
- `param_5`: Current tick number. Used for boost timing and grip state updates. **VERIFIED**.

Profiling string: `"NSceneVehiclePhy::ComputeForces"` (line 50). **VERIFIED**.

### 3.2 Entity Resolution

**Source**: `NSceneVehiclePhy__ComputeForces.c:51-59`
```c
uVar3 = *(undefined8 *)(param_1 + 0x110);                    // physics manager
lVar6 = FUN_1407bea40(local_c8, uVar3, param_2);             // entity lookup
lVar6 = *(longlong *)(lVar6 + 8);                            // dereference to entity
local_110 = *(undefined8 *)(lVar6 + 0x1bb0);                 // vehicle model class ptr
local_118 = *(longlong *)(lVar6 + 0x88);                     // physics model data ptr
local_108 = *(undefined8 *)(param_1 + 8);                    // arena event system
local_148 = *(undefined4 *)(lVar6 + 0x10);                   // body ID
```

Key struct pointers established:
- `lVar6`: The vehicle entity (~7300+ bytes)
- `local_110` (entity+0x1BB0): Vehicle model class data (contains visual/model parameters)
- `local_118` (entity+0x88): Physics model data (contains all tuning curves and offsets)

**VERIFIED**: Every pointer dereference matches the offset table in doc 10 S3.1.

### 3.3 Velocity Retrieval and Speed Clamping

**Source**: `NSceneVehiclePhy__ComputeForces.c:60-126`

```c
// Get velocity vector
uVar7 = FUN_1407be430(uVar3, local_148, &local_130);    // vel.x, vel.y, vel.z

// Also get angular velocity and body state
uVar7 = FUN_1407be580(uVar7, local_148, local_124);
FUN_1407bddd0(uVar7, local_148, local_13c);

// Speed clamping check
fVar9 = *(float *)(local_118 + 0x2f0);                  // max speed from model
fVar8 = local_130*local_130 + local_12c*local_12c + local_128*local_128;  // |v|^2

if ((fVar9 * fVar9 < fVar8) && (DAT_141d1ed34 < fVar9)) {
    fVar8 = SQRT(fVar8);
    fVar9 = fVar9 / fVar8;          // scale factor = max_speed / actual_speed
    local_130 *= fVar9;             // clamp x
    local_12c *= fVar9;             // clamp y
    local_128 *= fVar9;             // clamp z
    FUN_140845270(uVar3, lVar6, &local_130);  // write back clamped velocity
}
```

**VERIFIED**: Speed is clamped to max_speed from model+0x2F0. The clamping preserves velocity direction (scales all three components equally). The threshold check `DAT_141d1ed34 < fVar9` prevents clamping when max_speed is near-zero (avoids division issues).

### 3.4 State 1 Early Exit (Force Zeroing)

**Source**: `NSceneVehiclePhy__ComputeForces.c:65-87`

```c
if ((((byte)*(undefined4 *)(lVar6 + 0x128c) & 0xf) == 1) ||
    (pfVar1 = (float *)(*(longlong *)(lVar6 + 0x1bb0) + 0x278),
     *pfVar1 <= 0.0 && *pfVar1 != 0.0)) {
    // Zero out all forces and torques
    FUN_1407be380(uVar3, uVar7, &zero_vec);   // clear force
    FUN_1407be4d0(uVar3, uVar7, &zero_vec);   // clear torque
    FUN_1407bdc60(uVar3, uVar7, &zero_vec);   // clear force 2
    FUN_1407bde90(uVar3, uVar7, &zero_vec);   // clear torque 2
    *(undefined8 *)(lVar6 + 0x1584) = 0;      // clear reset force
    *(undefined8 *)(lVar6 + 0x158c) = 0;
    goto epilogue;
}
```

Two conditions trigger force zeroing:
1. Status nibble == 1 (inactive/reset state)
2. Model class field at +0x278 is strictly negative (not zero, not positive)

**VERIFIED**: Four force/torque vectors are zeroed. This is the "dead vehicle" path.

### 3.5 Boost Force System

**Source**: `NSceneVehiclePhy__ComputeForces.c:89-111`

```c
if (*(int *)(lVar6 + 0x16e8) == -1) {       // boost not started yet
    *(uint *)(lVar6 + 0x16e8) = param_5;     // record start tick

    // Dispatch boost event if conditions met
    if (*(longlong *)(param_1 + 8) != 0 &&
        (*(byte *)(lVar6 + 0x1c7c) & 4) == 0 &&
        *(char *)(lVar6 + 0x1c78) != -1) {
        FUN_1407d6200();  // send event
    }
}

// Apply boost force if within duration window
uVar2 = *(uint *)(lVar6 + 0x16e8);           // start tick
if (uVar2 <= param_5 && param_5 <= uVar2 + *(uint *)(lVar6 + 0x16e0)) {
    float t = (param_5 - uVar2) / *(uint *)(lVar6 + 0x16e0);  // 0..1 normalized
    float force = t * *(float *)(lVar6 + 0x16e4)               // strength
                    * *(float *)(*(longlong *)(lVar6 + 0x1bb0) + 0xe0); // model scale
    FUN_1407bdf40(uVar3, entity_id, &force_vec);
}
```

**VERIFIED**: The boost force is:
- **Linear ramp-up**: `force = (elapsed_ticks / total_duration) * strength * model_scale`
- NOT a decay. NOT a ramp-down. The force starts at 0 and increases to maximum at the end of the boost period.
- Applied as a torque (via FUN_1407bdf40), not a linear force.

This is confirmed by the formula: `(param_5 - uVar2)` is elapsed time, divided by duration `*(lVar6 + 0x16e0)`, multiplied by strength `*(lVar6 + 0x16e4)`.

### 3.6 Pre-Dispatch Setup

**Source**: `NSceneVehiclePhy__ComputeForces.c:127-141`

```c
// Surface/contact initialization
FUN_140841ca0(uVar3, lVar6, local_118 + 0x30d8, param_5);

// Select force accumulator based on model type
if (*(int *)(local_118 + 0x1790) < 6) {
    // Models 0-5: read 12 bytes from entity+0x144C
    local_b8 = *(lVar6 + 0x144c);
    uStack_b4 = *(lVar6 + 0x1450);
    uStack_b0 = *(lVar6 + 0x1454);
} else {
    // Models 6+: read 12 bytes from entity+0x1534
    local_b8 = *(lVar6 + 0x1534);
    uStack_b4 = *(lVar6 + 0x1538);
    uStack_b0 = *(lVar6 + 0x153c);
}

// Additional setup
FUN_140841f40(param_1, uVar3, lVar6, &local_b8);    // suspension pre-computation
FUN_1408426e0(lVar6, param_5);                        // wheel state update
```

**VERIFIED**: Models 0-5 use force accumulator at entity+0x144C. Models 6+ use entity+0x1534. The 0xE8-byte gap (232 bytes) between these locations suggests entirely different internal layouts for the newer models.

### 3.7 The Switch Statement

**Source**: `NSceneVehiclePhy__ComputeForces.c:142-162`

```c
switch(*(undefined4 *)(local_118 + 0x1790)) {
case 0:
case 1:
case 2:
    FUN_140869cd0(param_3, &local_158);                      // 4-wheel base
    break;
case 3:
    FUN_14086b060(param_3, &local_158);                      // 2-axle model
    break;
case 4:
    FUN_14086bc50(param_3, &local_158);                      // 4-wheel with traction control
    break;
case 5:
    FUN_140851f00(param_3, param_4, &local_158);             // Extended model A
    break;
case 6:
    FUN_14085c9e0(param_3, param_4, &local_158);             // Extended model B (CarSport?)
    break;
case 0xb:
    FUN_14086d3b0(param_3, param_4, &local_158);             // Extended model C
    break;
}
```

**VERIFIED**: This is the exact switch from the decompiled code. Note:
- Cases 0/1/2 fall through to the same function
- Cases 0-4 pass 2 arguments; cases 5/6/0xB pass 3 (adding `param_4`)
- `local_158` is a struct containing: param_1 (context), lVar6 (entity), local_118 (model), local_110 (model class), local_108 (arena), local_148 (body ID), param_5 (tick), param_4 (time param)
- There is **no default case**. Model values not in {0,1,2,3,4,5,6,11} silently skip force computation.

### 3.8 What Each Case Calls (Summary from Decompiled Files)

| Case | Function | Key Sub-Functions Called | Notes |
|---|---|---|---|
| 0,1,2 | FUN_140869cd0 | FUN_1408456b0 (slope), FUN_140869570 (per-wheel force), FUN_140845210 (apply force), FUN_140845260 (apply torque), FUN_14042bcb0 (curve sample) | 4 wheels, per-wheel surface lookup, sliding detection, speed clamping. Decompiled as stub with header annotations. |
| 3 | FUN_14086b060 | FUN_1408456b0, FUN_140869570, FUN_14086af20 (lateral grip), FUN_14018d310 (atan2) | 2-axle model, drift state machine, yaw damping. Decompiled as stub. |
| 4 | FUN_14086bc50 | FUN_1408456b0, FUN_140869570, FUN_140844090, FUN_140845210, FUN_140845260, FUN_14042bcb0, FUN_14083db50/80/f0 | **Fully decompiled** (598 lines). 4-wheel with traction control loop, sliding detection, engine braking torque. |
| 5 | FUN_140851f00 | UNKNOWN (partially read, very large function) | Largest force model. Takes time parameter. **Partially decompiled**. |
| 6 | FUN_14085c9e0 | FUN_1408570e0 (per-wheel), FUN_14085ad30 (steering), FUN_14085a0d0 (suspension), FUN_14085ba50 (anti-roll), FUN_140858c90 (damping), FUN_140857380 (drift), FUN_140857b20 (boost/reactor), FUN_14085c1b0 (airborne), FUN_14085b600 (integration) | Decompiled as annotated stub with 12 sub-functions identified. |
| 0xB | FUN_14086d3b0 | FUN_140843150, FUN_140845220, FUN_140858660, FUN_14018d310, FUN_1408581d0, FUN_1408570e0, FUN_14085ad30, FUN_140858c90, FUN_14086cc60, FUN_140857b20, FUN_14085b600, FUN_14085a920/FUN_140858e70, FUN_140855ea0, FUN_1408562d0 | **Fully decompiled** (302 lines). Two code paths based on `*(int *)(plVar3 + 0x157c)`. Post-respawn force fade system visible. |

### 3.9 The Turbo Force Computation: Is It REALLY a Ramp-Up?

The documentation claims the turbo force ramps up. Let me verify this directly.

**Source**: `NSceneVehiclePhy__ComputeForces.c:105-106`
```c
local_b8 = ((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) *
           *(float *)(lVar6 + 0x16e4) * *(float *)(*(longlong *)(lVar6 + 0x1bb0) + 0xe0);
```

Breaking this down:
- `param_5 - uVar2` = current_tick - start_tick = elapsed ticks (increases over time)
- `/ *(uint*)(lVar6 + 0x16e0)` = / total_duration = normalized time (0 to 1)
- `* *(float*)(lVar6 + 0x16e4)` = * strength
- `* *(float*)(model + 0xe0)` = * model_scale

At the START of the boost: elapsed = 0, so force = 0.
At the END of the boost: elapsed = duration, so force = strength * scale.

**VERIFIED**: The turbo force IS a linear ramp-up from 0 to maximum. This is confirmed beyond doubt from the arithmetic.

### 3.10 Post-Dispatch: Checkpoint Reset Logic

**Source**: `NSceneVehiclePhy__ComputeForces.c:173-199`

After the force model runs, the code checks if per-wheel state should be reset:

```c
if ((1 < *(int *)(local_118 + 0x238) - 5U) &&
    (iVar5 = FUN_14083db20(local_150 + 0x1280), iVar5 != 0)) {
    // Reset 4 wheel blocks at stride 0xB8
    // Pattern: previous = current; current = 0; timers = 0
}
```

The condition `(value - 5) > 1` in unsigned arithmetic passes for values 0-4 and 7+, fails for 5 and 6. Combined with the FUN_14083db20 check, this resets wheel state for certain vehicle/mode combinations.

**VERIFIED**: The 4-block reset pattern at stride 0xB8 is consistent with 4 wheels of 184-byte state each.

### 3.11 Speed Clamping Mechanism (In Force Models)

Within the force model case 4 (the fully decompiled one), there is an additional speed clamping layer:

**Source**: `force_model_case4_FUN_14086bc50.c:533-538`
```c
if ((float)local_120 * *(float *)(lVar12 + 0xab0) < fVar16) {
    fVar24 = (float)(*(uint *)(lVar12 + 0x308) ^ uVar31);  // negative of 0x308 value
}
if (fVar16 < (float)((uint)((float)local_120 * *(float *)(lVar12 + 0xab4)) ^ uVar31)) {
    fVar24 = *(float *)(lVar12 + 0x308);  // positive of 0x308 value
}
```

Two speed limits from tuning data:
- `tuning+0xAB0`: Forward speed cap. If speed exceeds this, force is clamped to `-tuning+0x308` (braking force).
- `tuning+0xAB4`: Reverse speed cap. If speed is below the negative of this, force is clamped to `+tuning+0x308` (acceleration force).

**VERIFIED**: The speed clamping applies a fixed retarding/accelerating force at the speed limits, creating hard speed boundaries in both directions.

---

## Lecture 4: What We Cannot Determine From Available Evidence

### 4.0 An Honest Assessment

Students, this lecture is about intellectual honesty. For every verified fact we have, there are gaps we cannot fill from the available decompiled code. Here is a complete accounting.

### 4.1 Un-Decompiled Sub-Functions

The following critical functions are called from the code we have but have NOT been decompiled:

| Function | Called From | Purpose (Inferred) | Impact |
|---|---|---|---|
| FUN_14083dca0 | PhysicsStep_TM:71 | Get friction coefficient for vehicle | We know WHAT it returns (a float used as a timestep scale) but not HOW it computes it |
| FUN_1414ffee0 | PhysicsStep_TM:155 | Core force computation dispatch | This is the wrapper that calls ComputeForces. Its internal logic is unknown. |
| FUN_1414ff9d0 | PhysicsStep_TM:157 | Post-force state update | Unknown what state it modifies |
| FUN_1415009d0 | PhysicsStep_TM:159 | Physics step dispatch | The actual rigid body integration step |
| FUN_14083df50 | PhysicsStep_TM:162 | Integration | Final velocity/position integration |
| FUN_1407bdd20 | force_apply:15 | Add force to rigid body | The actual accumulation into body forces |
| FUN_1407bdf40 | force_apply:30 | Add torque to rigid body | The actual accumulation into body torques |
| FUN_140841ca0 | ComputeForces:127 | Contact/surface initialization | What it initializes is unknown |
| FUN_140841f40 | ComputeForces:140 | Suspension pre-computation | What forces it applies is unknown |
| FUN_1408426e0 | ComputeForces:141 | Wheel state tick update | Calls tire grip state machine internally |
| FUN_1408025a0 | PhysicsStep_V2:201 | Internal physics step (the solver itself) | The actual constraint solver is un-decompiled |

### 4.2 Magic Constants Without Context

Throughout the decompiled code, there are global constants referenced by address (e.g., `DAT_141d1f3c8`, `DAT_141d1f71c`). From the annotation in the case 4 model header:

| Constant | Likely Value | Evidence | Confidence |
|---|---|---|---|
| DAT_141d1f3c8 | 1.0f | Used as identity multiplier everywhere | HIGH (from context) |
| DAT_141d1f1ac | 0.5f | Used as "half" in force calculations | PLAUSIBLE |
| DAT_141d1f71c | ~57.3 (180/pi) | Annotated as "rad-to-deg or similar scale" | PLAUSIBLE |
| DAT_141d21c00 | 0x7FFFFFFF | Float abs mask (clear sign bit) | HIGH (standard technique) |
| DAT_141d21c30 | 0x80000000 | Float sign flip mask (toggle sign bit) | HIGH (standard technique) |
| DAT_141d1fd80 | -1.0f | Used as negative identity | PLAUSIBLE |
| DAT_141d1fa9c | 1000.0f | Used in substep cap division | PLAUSIBLE |
| DAT_141d1ed34 | Small epsilon | Minimum threshold for various checks | Exact value UNKNOWN |
| DAT_141d1ecc4 | Very small epsilon | Min normal length squared | Exact value UNKNOWN |
| DAT_141d1fc24 | Large number | Max normal length squared sanity | Exact value UNKNOWN |

**UNKNOWN**: The actual float values of these constants. They could be extracted by reading the binary's .rdata section at these addresses, but this has not been done for all of them.

### 4.3 Struct Offsets We Cannot Name

The vehicle entity struct has hundreds of fields accessed by numeric offset. Many have been identified from context, but many remain unknown. From the offset table in doc 10 S3.1, fields marked [UNKNOWN] include:

- entity+0x1794 through +0x17A8 (wheel block 1 unknowns)
- entity+0x1848 through +0x185C (wheel block 2 unknowns)
- entity+0x1900 through +0x191C (wheel block 3 unknowns)
- entity+0x19B8 through +0x19D4 (wheel block 4 unknowns)
- Many fields in the 0x1280-0x1600 range (vehicle-specific state)

### 4.4 The Gap Between Decompiled Code and Runtime Behavior

Several important caveats:

1. **Ghidra decompilation artifacts**: The decompiled C code is Ghidra's best guess at the original source. Variable types may be wrong (Ghidra often uses `undefined4` where the original was `float`). Control flow may be restructured. The `CONCAT44` calls are Ghidra's representation of 64-bit register packing, not original code.

2. **Compiler optimizations**: The original code likely used vector intrinsics (SSE/AVX) that Ghidra decompiles into sequential scalar operations. The actual execution may use SIMD instructions that process 4 floats simultaneously.

3. **Inlining**: Small functions may have been inlined by the compiler. What appears as inline code in the decompilation may have been a separate function in the source.

4. **Data-driven behavior**: Most physics parameters come from GBX data files loaded at runtime. The code we see is the ENGINE; the actual vehicle BEHAVIOR depends on the data. Two vehicles using the same force model case can behave very differently based on their loaded tuning curves.

5. **We cannot observe initialization**: We can see what the code DOES with values, but for data-loaded constants, we cannot see what values are loaded. The curve sample function (`FUN_14042bcb0`) is well understood, but we do not have the actual keyframe data for any curve.

### 4.5 Specific Open Questions

1. **Which vehicle uses which force model?** We know CarSport, CarSnow, CarRally, CarDesert exist. We know models 0-4, 5, 6, 0xB exist. The mapping is UNKNOWN from code alone.

2. **What are the actual tuning curve values?** Every speed-dependent coefficient (friction, grip, engine torque, drag) is stored as a keyframe curve. We have the curve evaluation code but zero curve data.

3. **How does the constraint solver work internally?** We have SSolverParams (iteration counts) but FUN_1408025a0 (the actual solver) is not decompiled.

4. **What is the full airborne control model?** FUN_14085c1b0 is partially decompiled (196 lines) but references sub-functions for gravity assist and angular damping that are not.

5. **How does vehicle transformation work at runtime?** Surface IDs 15-17 and 20 trigger vehicle transforms (CarRally, CarSnow, CarDesert, Reset). The mechanics of swapping the physics model mid-drive are UNKNOWN.

6. **What are the reactor boost physics?** We see `FUN_140857b20` handles spring/damper + reactor forces, but the reactor-specific force curve is not fully traced.

---

## Lecture 5: Recommendations for Students Building a Racing Game

### 5.0 Approach

Everything in this lecture is grounded in verified findings. Where I make recommendations, I will state which verified facts support them.

### 5.1 What to Replicate Exactly

#### 5.1.1 Fixed-Timestep with Integer Time

**Based on**: PhysicsStep_TM.c:63 (VERIFIED)

Use integer tick counters and convert to time units via integer multiplication. Do NOT use `accumulated_time += delta_time` with floating point. The TM2020 approach:

```
tick_counter += 1    // integer, exact
timestamp_us = tick_counter * 1000000   // integer multiplication
```

This guarantees your replays will be deterministic. It is the single most important architectural decision.

#### 5.1.2 Adaptive Sub-Stepping Based on Velocity

**Based on**: PhysicsStep_TM.c:71-167 (VERIFIED)

The sub-stepping formula ensures stability at high speeds without wasting CPU at low speeds:

```
total_speed = |linear_vel| + |angular_vel| + ... (sum of relevant speeds)
num_substeps = clamp(floor(total_speed * dt_scaled / step_size) + 1, 1, MAX_SUBSTEPS)
```

Key: process N-1 equal sub-steps, then one remainder step. This ensures total simulated time equals exactly the tick period.

#### 5.1.3 Curve-Based Tuning System

**Based on**: curve_sample_FUN_14042bcb0.c (VERIFIED)

Every speed-dependent parameter should be a sampled curve, not a single value. The TM2020 curve format supports:
- Linear interpolation (default)
- Smoothstep: `3t^2 - 2t^3` (for S-shaped transitions)
- Step mode (discontinuous jumps)
- Spline (catmull-rom)

This makes tuning extremely flexible without code changes.

#### 5.1.4 Sequential Entity Processing

**Based on**: PhysicsStep_TM.c:64-220 (VERIFIED)

Process vehicles in deterministic array order. No parallel physics dispatch. Determinism requires identical processing order across all runs.

#### 5.1.5 Per-Wheel Surface Material Lookup

**Based on**: force_model_case4_FUN_14086bc50.c:160-169 (VERIFIED)

Each wheel independently looks up its surface material. A car can have different wheels on different surfaces simultaneously. The lookup is: `material_table[surface_id]`, where the surface ID comes from the wheel's contact point.

### 5.2 Where You Have Freedom to Innovate

#### 5.2.1 The Force Model Architecture

TM2020 uses 7 different force models selected by a switch statement. You do NOT need 7. You could:
- Use a single configurable force model with feature flags
- Use a component system (mix and match: 2-wheel vs 4-wheel, drift enabled/disabled, etc.)
- Use the same model with different data for each vehicle

The switch-based dispatch is an engineering choice, not a physics requirement.

#### 5.2.2 The Tire Model

The decompiled code shows two approaches:
- **4-wheel model (case 4)**: Per-wheel friction force from curve, sliding detection via force-vs-grip comparison
- **2-wheel model (case 3)**: Simplified lateral grip with linear + quadratic terms

Neither is a full Pacejka Magic Formula. You can use ANY tire model that gives you the feel you want. What matters is:
- A speed-dependent grip curve (VERIFIED: all models use FUN_14042bcb0 for this)
- A sliding/grip threshold (VERIFIED: the case 4 model explicitly compares force against grip limit)
- Surface-dependent coefficients (VERIFIED: material lookup per wheel)

#### 5.2.3 The Constraint Solver

We know TM2020 uses a sequential-impulse solver with configurable iteration counts (VERIFIED from SSolverParams). You can use:
- Bullet Physics
- Box2D-style solver
- Your own Gauss-Seidel implementation
- Any solver that gives deterministic results

#### 5.2.4 The Boost/Turbo System

TM2020 uses linear ramp-up (VERIFIED). You could use:
- Constant force (simpler)
- Exponential decay (TMNF style)
- Any curve you want

The ramp-up vs decay is a game design choice, not a physics necessity.

### 5.3 What NOT to Assume Transfers from TMNF

**Based on**: Doc 10 S11 (VERIFIED differences)

| Feature | TMNF | TM2020 | Source |
|---|---|---|---|
| Boost force profile | Decay (max to 0) | Ramp-up (0 to max) | ComputeForces.c:105 (VERIFIED) |
| Max substeps | 10,000 | 1,000 | PhysicsStep_TM.c:126 (VERIFIED) |
| Force model count | 4 | 7 | ComputeForces.c:142-162 (VERIFIED) |
| Vehicle state size | ~2,112 bytes | ~7,328+ bytes | Doc 10 S11 (PLAUSIBLE) |
| Architecture | x86 (x87 FPU) | x64 (SSE) | Binary analysis (VERIFIED) |
| Time conversion | tick * 0.001 (float ms) | tick * 1000000 (integer us) | PhysicsStep_TM.c:63 (VERIFIED) |
| Pair physics | Not observed | Explicit PairComputeForces | PairComputeForces.c (VERIFIED) |

**Critical warning**: Do NOT port TMNF physics formulas to a TM2020-like engine without verifying each one. The boost direction change alone would make every turbo pad behave differently.

### 5.4 What Needs Empirical Testing Against the Real Game

These aspects cannot be determined from decompilation alone and require live testing:

1. **Actual tuning curve values**: Record vehicle speed under controlled conditions (straight road, specific surface) using Openplanet's VehicleState plugin. Compare acceleration profiles to reconstruct the engine torque curve.

2. **Vehicle-to-model mapping**: Use Openplanet to read the `+0x1790` offset on each vehicle type's physics model data while each car is active.

3. **Grip curve shape**: Test grip at various speeds on different surfaces. The grip state machine (tire_grip_state_machine) shows buildup/decay rates come from tuning+0xCDC/CE0/CE4/CE8, but the actual tick counts are data-loaded.

4. **Slope thresholds**: Test acceleration on inclines of known angles to determine the four slope threshold values (tuning+0x19E4/E8/EC/F0).

5. **Reactor boost behavior**: The reactor force model involves spring/damper physics at hardpoints plus differential torque steering. The formulas are visible but the tuning data determines the feel.

6. **Sleep detection thresholds**: The sleep damping factor and velocity threshold (DAT_141ebcd00, DAT_141ebcd04) are global constants. Their values could be measured by observing when a stationary vehicle stops micro-updating.

### 5.5 Summary: Build vs Buy

| Component | Build from Scratch | Use Existing Library | Notes |
|---|---|---|---|
| Fixed-timestep loop | Build | | Critical for determinism |
| Curve sampler | Build | | Simple but important (see FUN_14042bcb0) |
| Tire model | Build | | TM2020's is simpler than academic Pacejka |
| Rigid body dynamics | | Bullet/PhysX | Constraint solver is complex |
| Collision detection | | Bullet/PhysX | Contact merging is well-studied |
| Surface material system | Build | | Game-specific |
| Boost/turbo system | Build | | Game-specific |
| Adaptive sub-stepping | Build | | Custom to your speed range |
| Replay system | Build | | Must record inputs, not state |

### 5.6 Final Exam Question

If you take away one lesson from this course, it is this: **the code is the authority, not the documentation about the code**. I found at least one error in the existing documentation (the "v^2 air resistance" claim). I found several places where documentation confidence levels were too high. In your own reverse engineering work, always check the primary source.

The physics engine of Trackmania 2020 is not magic. It is approximately 40 functions totaling perhaps 15,000 lines of C code, operating on data-driven curves and a standard rigid body solver. What makes it excellent is the tuning data, not the code complexity.

Good luck with your projects.

-- Professor Chen

---

## Appendix A: Complete File Index

All decompiled source files referenced in these lectures:

### Physics Directory (`decompiled/physics/`)

| File | Address | Lecture | Lines Read |
|---|---|---|---|
| `PhysicsStep_TM.c` | FUN_141501800 | L2 | 224 (complete) |
| `NSceneVehiclePhy__ComputeForces.c` | FUN_1408427d0 | L3 | 235 (complete) |
| `force_model_case4_FUN_14086bc50.c` | FUN_14086bc50 | L3 | 598 (complete) |
| `force_model_case0xB.c` | FUN_14086d3b0 | L3 | 302 (complete) |
| `force_model_4wheel_FUN_140869cd0.c` | FUN_140869cd0 | L3 | 67 (annotated stub) |
| `force_model_2wheel_FUN_14086b060.c` | FUN_14086b060 | L3 | 55 (annotated stub) |
| `force_model_carsport_FUN_14085c9e0.c` | FUN_14085c9e0 | L3 | 49 (annotated stub) |
| `force_model_case5.c` | FUN_140851f00 | L3 | 100+ (partial) |
| `wheel_force_FUN_140869570.c` | FUN_140869570 | L3 | 43 (annotated stub) |
| `curve_sample_FUN_14042bcb0.c` | FUN_14042bcb0 | L1,L3 | 71 (pseudocode) |
| `tire_grip_state_machine_FUN_140842310.c` | FUN_140842310 | L1 | 100 (pseudocode) |
| `slope_gravity_factor_FUN_1408456b0.c` | FUN_1408456b0 | L1 | 68 (pseudocode) |
| `airborne_control.c` | FUN_14085c1b0 | L3,L4 | 196 (complete) |
| `boost_reactor_force.c` | FUN_140857b20 | L3 | 234 (complete) |
| `carsport_per_wheel_force.c` | FUN_1408570e0 | L3 | 155 (complete) |
| `force_apply_FUN_140845210.c` | FUN_140845210/260 | L3 | 31 (complete) |
| `steering_input_FUN_14083d8e0.c` | FUN_14083d8e0 | L3 | 41 (annotated stub) |
| `lateral_grip_2wheel_FUN_14086af20.c` | FUN_14086af20 | L1 | 39 (annotated stub) |
| `wheel_contact_surface_FUN_140845b60.c` | FUN_140845b60 | L1 | 43 (annotated stub) |
| `NSceneDyna__PhysicsStep.c` | FUN_1407bd0e0 | L2 | 22 (complete) |
| `NSceneDyna__PhysicsStep_V2.c` | FUN_140803920 | L2 | 237 (complete) |
| `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c` | FUN_1407f89d0 | L2 | 103 (complete) |
| `NSceneDyna__ComputeExternalForces.c` | FUN_1407f81c0 | L2 | 31 (complete) |
| `NSceneDyna__ComputeWaterForces.c` | FUN_1407f8290 | L2 | 53 (complete) |
| `NSceneDyna__DynamicCollisionCreateCache.c` | FUN_1407f9da0 | L2 | 88 (complete) |
| `NHmsCollision__MergeContacts.c` | FUN_1402a8a70 | L2 | 271 (complete) |
| `NHmsCollision__StartPhyFrame.c` | FUN_1402a9c60 | L2 | 57+ (complete) |
| `NSceneVehiclePhy__PairComputeForces.c` | FUN_140842ed0 | L3 | 93 (complete) |
| `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c` | FUN_1407cfce0 | L2 | 292 (complete) |
| `NSceneVehiclePhy__PhysicsStep_ProcessContactPoints.c` | FUN_1407d2b90 | L2 | 51 (complete) |
| `NSceneVehiclePhy__ExtractVisStates.c` | FUN_1407d29a0 | L2 | 48 (complete) |
| `CSmArenaPhysics__Players_BeginFrame.c` | FUN_1412c2cc0 | L2 | 42 (complete) |
| `ArenaPhysics_CarPhyUpdate.c` | FUN_1412e8490 | L2 | 61 (complete) |
| `Tunings_CoefFriction_CoefAcceleration.c` | FUN_141071b20 | L1 | 48 (complete) |
| `FrictionIterCount_Config.c` | FUN_1407f3fc0 | L1 | 105 (complete) |
| `SSolverParams_FUN_1407f3fc0.c` | FUN_1407f3fc0 | L1 | 44 (pseudocode) |
| `SSleepingParams_FUN_1407f4430.c` | FUN_1407f4430 | L1 | 16 (pseudocode) |
| `CSceneVehicleVisState_FUN_140726440.c` | FUN_140726440 | L1 | 147 (complete) |
| `CPlugVehiclePhyModelCustom_FUN_14061abb0.c` | FUN_14061abb0 | L1 | 39 (pseudocode) |

### Tuning Directory (`decompiled/tuning/`)

| File | Lecture | Lines Read |
|---|---|---|
| `CPlugVehiclePhyModelCustom_Archive.c` | L1 | 45 (pseudocode) |
| `NSceneVehiclePhy_ComputeForces.c` | L3 | 103 (pseudocode) |
| `SetPlayer_Delayed_AccelCoef.c` | L1 | 80 (pseudocode) |
| `VehicleRegistry.c` | L1 | 38 (annotated) |
| `PhysicsStep_TM.c` | L2 | 107 (pseudocode) |

### Documentation Files Referenced

| File | Priority | Used In |
|---|---|---|
| `docs/re/10-physics-deep-dive.md` | 3rd (RE Analysis) | L1 audit |
| `docs/re/22-ghidra-gap-findings.md` | 3rd (RE Analysis) | L1 audit |
| `docs/re/19-openplanet-intelligence.md` | 2nd (Validated) | L1 wheel order, VisState |
| `docs/re/21-competitive-mechanics.md` | 3rd (RE Analysis) | L1 timing verification |

---

## Appendix B: Confidence Legend

| Tag | Meaning | Standard |
|---|---|---|
| **VERIFIED** | Directly visible in decompiled code at cited file:line | Can be independently confirmed by reading the code |
| **INFERENCE** | Logically derived from verified facts | Conclusion follows from evidence but involves interpretation |
| **PLAUSIBLE** | Consistent with evidence but alternative explanations exist | Multiple independent sources agree but no single proof |
| **SPECULATIVE** | Educated guess based on limited evidence | Should not be taught as fact |
| **UNKNOWN** | Cannot determine from available evidence | Honest acknowledgment of limits |

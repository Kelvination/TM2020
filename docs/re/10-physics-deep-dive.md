# Physics Deep Dive: Trackmania 2020 Decompiled Physics Engine

**Binary**: `Trackmania.exe` (Trackmania 2020 by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
**Sources**: 18 decompiled physics functions, cross-referenced with TMNF RE diary and existing `04-physics-vehicle.md`

---

## Table of Contents

1. [Simulation Pipeline Overview](#1-simulation-pipeline-overview)
2. [The 7 Force Models](#2-the-7-force-models)
3. [Complete Vehicle State Structure](#3-complete-vehicle-state-structure)
4. [Tire/Wheel Contact Model](#4-tirewheelcontact-model)
5. [Collision System](#5-collision-system)
6. [Surface Effects](#6-surface-effects)
7. [Gravity and Sub-stepping](#7-gravity-and-sub-stepping)
8. [Water Physics](#8-water-physics)
9. [Tuning Parameters and Numeric Constants](#9-tuning-parameters-and-numeric-constants)
10. [Determinism](#10-determinism)
11. [Differences from TMNF](#11-differences-from-tmnf)
12. [Curious Questions Answered](#12-curious-questions-answered)
13. [Comprehensive Constants Table](#13-comprehensive-constants-table)

---

## 1. Simulation Pipeline Overview

### 1.1 Top-Level Call Chain

**Evidence**: `PhysicsStep_TM.c`, `NSceneDyna__PhysicsStep.c`, `NSceneDyna__PhysicsStep_V2.c`
**Confidence**: VERIFIED

The physics pipeline runs each game tick as follows:

```
CSmArenaPhysics::Players_BeginFrame (FUN_1412c2cc0)
  |
  +-> ArenaPhysics_CarPhyUpdate (FUN_1412e8490)
  +-> PhysicsStep_TM (FUN_141501800) -- per-vehicle main loop
        |
        +-> Adaptive sub-stepping loop (velocity-dependent)
        |     |
        |     +-> Collision check (FUN_141501090)
        |     +-> NSceneVehiclePhy::ComputeForces (FUN_1408427d0)
        |     +-> Force application (FUN_1414ffee0)
        |     +-> Post-force update (FUN_1414ff9d0)
        |     +-> Physics step dispatch (FUN_1415009d0)
        |     +-> Integration (FUN_14083df50)
        |
        +-> NSceneDyna::PhysicsStep (FUN_1407bd0e0)
              +-> NSceneDyna::PhysicsStep_V2 (FUN_140803920)
                    +-> NSceneDyna::DynamicCollisionCreateCache
                    +-> NSceneDyna::InternalPhysicsStep (FUN_1408025a0)
                    +-> Body force clearing (stride 0x38)
```

### 1.2 Per-Vehicle Physics Step (PhysicsStep_TM)

**Evidence**: `PhysicsStep_TM.c:7-224`
**Confidence**: VERIFIED
**Address**: FUN_141501800

The profiling scope string `"PhysicsStep_TM"` confirms this is the main per-vehicle physics step. Key operations:

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

### 1.3 Timing System

**Evidence**: `PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`
**Confidence**: VERIFIED

Both functions convert tick values to microseconds:
```c
// PhysicsStep_TM
lVar18 = (ulonglong)*param_4 * 1000000;

// NSceneDyna::PhysicsStep
FUN_140801e20(param_1, (ulonglong)*param_2 * 1000000);
```

The internal time unit is **microseconds**. The input tick is multiplied by 1,000,000. Given TM2020 runs at 100Hz (10ms per tick), this produces 10,000,000 microseconds per tick, consistent with the standard physics timestep.

### 1.4 PhysicsStep_V2 Orchestration

**Evidence**: `NSceneDyna__PhysicsStep_V2.c:1-237`
**Confidence**: VERIFIED
**Address**: FUN_140803920

PhysicsStep_V2 is the rigid body dynamics orchestrator. Key observations:

1. **Step counter increment**: `*(param_1 + 0xf4b) += 1` (line 89)
2. **Time scale**: `fVar16 = (float)param_2[2] * DAT_141d1fa9c` (line 133) -- `DAT_141d1fa9c` is likely 1000.0f (the max substep cap value reused as a divisor)
3. **Collision cache creation**: Calls `FUN_1407f9da0` (DynamicCollisionCreateCache) (line 150)
4. **InternalPhysicsStep dispatch**: Calls `FUN_1408025a0` if bodies need updating (line 201)
5. **Body force clearing**: Loop zeros `+0x8` in body array with stride `0x38` (56 bytes) (lines 214-232)

**Struct Offset**: `param_1[0xf4b]` = physics step counter (8-byte aligned: byte offset 0x7A58)

The body force clearing uses both strides `0x38` (56 bytes, unrolled 4x as `0xE0` = 224 bytes) and single-iteration `0x38`, confirming the per-body data structure is 56 bytes with forces at offset `+0x8`.

---

## 2. The 7 Force Models

### 2.1 Force Model Dispatch Switch

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:142-162`
**Confidence**: VERIFIED
**Struct Offset**: `vehicle_model+0x1790` (force model type selector)

The switch at offset `+0x1790` on the vehicle model object dispatches to different force computation functions:

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

### 2.2 Model Identification and Mapping

**Evidence**: Cross-reference with TMNF `ESteerModel` enum and gbx-net field names
**Confidence**: PLAUSIBLE (mapping inferred from TMNF analysis + TM2020 switch values)

| Switch Value | Function Address | TMNF Equivalent | Likely Car Type | Notes |
|:---:|:---:|:---:|:---:|:---|
| 0, 1, 2 | `FUN_140869cd0` | Steer01/02/03 (default) | Base/legacy models | 2 params, simplest model |
| 3 | `FUN_14086b060` | Steer04 (M4) | [UNKNOWN] | 2 params, lateral friction focus |
| 4 | `FUN_14086bc50` | Steer05 (M5) | [UNKNOWN] | 2 params, TMNF-era model |
| 5 | `FUN_140851f00` | Steer06 (M6) | **StadiumCar / CarSport** | 3 params, full simulation |
| 6 | `FUN_14085c9e0` | [NEW in TM2020] | **SnowCar** or **RallyCar** | 3 params, new model |
| 0xB (11) | `FUN_14086d3b0` | [NEW in TM2020] | **DesertCar** or variant | 3 params, newest model |

### 2.3 Key Differences Between Models

**Evidence**: Parameter signatures from `NSceneVehiclePhy__ComputeForces.c:142-162`
**Confidence**: VERIFIED (signatures), PLAUSIBLE (interpretations)

**Models 0-4** (2-parameter):
```c
FUN_140869cd0(param_3, &local_158);  // param_3 = dyna_state, local_158 = vehicle_context
```
These take only the dynamics state and vehicle context. They represent simpler force models that don't need the additional `param_4` parameter.

**Models 5, 6, 0xB** (3-parameter):
```c
FUN_140851f00(param_3, param_4, &local_158);  // adds param_4 (tick/time parameter)
```
These receive an additional parameter (passed through from ComputeForces' `param_4`, which is a tick/time value). This enables time-dependent features like:
- Turbo decay curves
- Time-limited boost effects
- Cruise control timing
- Vehicle transform transition physics

### 2.4 The Pre-Model-6 Force Path

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:128-137`
**Confidence**: VERIFIED

Before the switch, the code selects different force source offsets based on the model:

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

This shows that models 6+ use a different force accumulator location within the vehicle state, suggesting a fundamentally reorganized force layout. The offsets `+0x144C` and `+0x1534` are separated by `0xE8` (232 bytes), large enough for an entire wheel-set of per-wheel data.

### 2.5 Post-Switch State Reset (Checkpoint Reset Logic)

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:173-199`
**Confidence**: VERIFIED

After the force model switch, the code checks if the vehicle should reset its physics state:

```c
// Condition: model value > 5 (i.e., the subtraction 5 wraps unsigned, so > 5 means models 0-4 excluded)
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

**Struct Offset**: `vehicle_model+0x238` is checked against value 5 (unsigned). This is likely a game-mode or vehicle-class identifier that determines whether checkpoint resets should clear the force model.

The 4 blocks at stride `0xB8` (184 bytes) likely correspond to the 4 wheels, each containing:
- `+0x00`: Force model type (the 0x1790 selector)
- `+0x04`: [UNKNOWN]
- `+0x20`: Previous value
- `+0x24`: Current value
- `+0x34`: Timer/counter
- `+0x38`: Timer/counter

### 2.6 Vehicle Type to Force Model Mapping

**Evidence**: Surface gameplay strings in `NHmsCollision__StartPhyFrame.c:100-128`, `04-physics-vehicle.md`
**Confidence**: SPECULATIVE

Based on the known vehicle types and force model count:

| Vehicle | Likely Model | Reasoning |
|:---|:---:|:---|
| **CarSport (Stadium)** | 5 | The M6/Steer06 model from TMNF, confirmed as the full simulation model. CarSport is the primary racing car. |
| **RallyCar** | 6 | Rally requires different tire physics (loose surface, sliding), new model with time param. |
| **SnowCar** | 6 or 0xB | Snow physics need unique slip/ice model; may share model 6 with different tuning or use 0xB. |
| **DesertCar** | 0xB | Desert is the most different driving style; likely the newest model (value 11). |
| **Legacy/inactive** | 0, 1, 2 | Base models for backward compatibility or simplified simulation. |

---

## 3. Complete Vehicle State Structure

### 3.1 Vehicle Entity State (accessed via `lVar6` / `lVar9`)

**Evidence**: All 18 decompiled files, aggregated
**Confidence**: VERIFIED for offsets observed in code; [UNKNOWN] for gaps

| Offset | Size | Type | Field Name | Evidence / Source |
|:---|:---:|:---:|:---|:---|
| `+0x10` | 4 | int | `DynaBodyId` | ComputeForces: `*(int *)(lVar6 + 0x10)`, compared to -1 |
| `+0x50` | 8 | ptr | `CollisionObjectAlt` | BeforeMgrDynaUpdate: `*(longlong *)(lVar20 + 0x50)` |
| `+0x80` | 8 | ptr | `CollisionObject` | BeforeMgrDynaUpdate: `*(longlong *)(lVar20 + 0x80)` |
| `+0x88` | 8 | ptr | `PhyModelPtr` | ComputeForces: `*(longlong *)(lVar6 + 0x88)`, PhysicsStep_TM |
| `+0x90` | 8 | f64/2xf32 | `CurrentTransform[0]` | PhysicsStep_TM: source of transform copy |
| `+0x98` | 8 | f64/2xf32 | `CurrentTransform[1]` | PhysicsStep_TM |
| `+0xA0` | 8 | f64/2xf32 | `CurrentTransform[2]` | PhysicsStep_TM |
| `+0xA8` | 8 | f64/2xf32 | `CurrentTransform[3]` | PhysicsStep_TM |
| `+0xB0` | 8 | f64/2xf32 | `CurrentTransform[4]` | PhysicsStep_TM |
| `+0xB8` | 8 | f64/2xf32 | `CurrentTransform[5]` | PhysicsStep_TM |
| `+0xC0` | 8 | f64/2xf32 | `CurrentTransform[6]` | PhysicsStep_TM |
| `+0xC8` | 8 | f64/2xf32 | `CurrentTransform[7]` | PhysicsStep_TM |
| `+0xD0` | 8 | f64/2xf32 | `CurrentTransform[8]` | PhysicsStep_TM |
| `+0xD8` | 8 | f64/2xf32 | `CurrentTransform[9]` | PhysicsStep_TM |
| `+0xE0` | 8 | f64/2xf32 | `CurrentTransform[10]` | PhysicsStep_TM |
| `+0xE8` | 8 | f64/2xf32 | `CurrentTransform[11]` | PhysicsStep_TM |
| `+0xF0` | 4 | f32 | `CurrentTransform[12]` | PhysicsStep_TM |
| `+0xF4` | 4 | f32 | `CurrentTransform[13]` | PhysicsStep_TM |
| `+0xF8` | 4 | f32 | `CurrentTransform[14]` | PhysicsStep_TM |
| `+0xFC` | 4 | f32 | `CurrentTransform[15]` | PhysicsStep_TM |
| `+0x100` | 4 | f32 | `CurrentTransform[16]` | PhysicsStep_TM |
| `+0x104` | 112 | mat4x3 | `PreviousTransform` | PhysicsStep_TM: destination of copy from +0x90 |
| `+0x194` | 4 | int | `ResetFlag` | BeforeMgrDynaUpdate: checked != 0, then zeroed |
| `+0x4E8` | varies | struct | `WheelVisStateBase` | ExtractVisStates: `lVar2 + 0x4E8` |
| `+0x848` | varies | struct | `WheelVisStateAlt` | ExtractVisStates: `lVar2 + 0x848` |
| `+0x9C` | 4 | f32 | `SurfaceHeightOrParam` | BeforeMgrDynaUpdate: `*(float *)(lVar19 + 0x9c)` used in surface calc |
| `+0x1280` | 4 | uint | `VehicleUniqueId` | Multiple: used as identifier, passed to event system |
| `+0x1284` | 4 | int | `PairId / TeamId` | BeforeMgrDynaUpdate: compared for pair exclusion |
| `+0x128C` | 4 | uint | `StatusFlags` | Multiple: low nibble = state enum |
| `+0x12C8` | 4 | int | `NegatedSomething` | ArenaPhysics_CarPhyUpdate: `-*(int *)(lVar3 + 0x12c8)` |
| `+0x12D8` | varies | struct | `ContactData` | BeforeMgrDynaUpdate: `FUN_14084c840(ptr, lVar19 + 0x12D8)` |
| `+0x12DC` | 4 | uint | `TickStamp` | BeforeMgrDynaUpdate: 0xFFFFFFFF = unset |
| `+0x12E0` | 48+ | mat3x4 | `TransformData` | BeforeMgrDynaUpdate: read as transform |
| `+0x12F0` | varies | struct | `MatchData` | ArenaPhysics_CarPhyUpdate: `FUN_141403460(uVar4, lVar3 + 0x12F0)` |
| `+0x1314` | varies | struct | `IntermediateTransform` | BeforeMgrDynaUpdate |
| `+0x1338` | 4 | uint | `Param` | BeforeMgrDynaUpdate: `FUN_1407be770(uVar4, *(lVar19 + 0x10), *(lVar19 + 0x1338))` |
| `+0x1348` | 12 | vec3 | `VelocityVec1` | PhysicsStep_TM: used in substep magnitude |
| `+0x1354` | 12 | vec3 | `VelocityVec2` | PhysicsStep_TM: used in substep magnitude |
| `+0x1408` | 4 | int | `ForceAccumFlag` | ComputeForces, PairComputeForces: zeroed |
| `+0x144C` | 12 | vec3 | `ForceAccum_Model0to5` | ComputeForces: read for models < 6 |
| `+0x1534` | 12 | vec3 | `ForceAccum_Model6plus` | ComputeForces: read for models >= 6 |
| `+0x156C` | 4 | int | `SlipCounter` | ComputeForces, PairComputeForces: zeroed |
| `+0x1570` | 8 | f64/2xf32 | `InitialVelocity_XY` | ComputeForces: set to `DAT_141a64350` (zero) |
| `+0x1578` | 4 | f32 | `InitialVelocity_Z` | ComputeForces: set to `DAT_141a64358` (zero) |
| `+0x1584` | 8 | f64/2xf32 | `ResetForce` | ComputeForces: zeroed on state 1 reset |
| `+0x158C` | 8 | [UNKNOWN] | [UNKNOWN] | ComputeForces: zeroed with +0x1584 |
| `+0x1594` | varies | circular buf | `WheelContactHistory` | BeforeMgrDynaUpdate: ring buffer for contact tracking |
| `+0x15B0` | 4 | int | `ContactStateChangeCount` | BeforeMgrDynaUpdate: counts transitions in contact history |
| `+0x175C` | 4 | f32 | `CustomForceParam` | ComputeForces: if != 0.0, applies custom force |
| `+0x1790` | 4 | int | `ForceModelType` | ComputeForces: switch case 0-6, 0xB |
| `+0x1794` | 8 | [UNKNOWN] | [UNKNOWN] | ComputeForces: zeroed on reset |
| `+0x17B0` | 4 | [UNKNOWN] | `WheelState_Prev[0]` | ComputeForces: prev = current pattern |
| `+0x17B4` | 4 | [UNKNOWN] | `WheelState_Curr[0]` | ComputeForces: zeroed on reset |
| `+0x17C4` | 4 | [UNKNOWN] | `WheelTimer1[0]` | ComputeForces: zeroed on reset |
| `+0x17C8` | 8 | [UNKNOWN] | `WheelTimer2[0]` | ComputeForces: zeroed on reset |
| `+0x1848` | 4 | int | `WheelBlock2_Base` | ComputeForces: block 2 base (stride 0xB8 from 0x1790) |
| `+0x1868` | 4 | [UNKNOWN] | `WheelState_Prev[1]` | ComputeForces: prev = current |
| `+0x186C` | 4 | [UNKNOWN] | `WheelState_Curr[1]` | ComputeForces: zeroed |
| `+0x187C` | 4 | [UNKNOWN] | `WheelTimer1[1]` | ComputeForces |
| `+0x1880` | 8 | [UNKNOWN] | `WheelTimer2[1]` | ComputeForces |
| `+0x1900` | 4 | int | `WheelBlock3_Base` | ComputeForces: block 3 |
| `+0x1920` | 4 | [UNKNOWN] | `WheelState_Prev[2]` | ComputeForces |
| `+0x1924` | 4 | [UNKNOWN] | `WheelState_Curr[2]` | ComputeForces |
| `+0x1934` | 4 | [UNKNOWN] | `WheelTimer1[2]` | ComputeForces |
| `+0x1938` | 8 | [UNKNOWN] | `WheelTimer2[2]` | ComputeForces |
| `+0x19B8` | 4 | int | `WheelBlock4_Base` | ComputeForces: block 4 |
| `+0x19D8` | 4 | [UNKNOWN] | `WheelState_Prev[3]` | ComputeForces |
| `+0x19DC` | 4 | [UNKNOWN] | `WheelState_Curr[3]` | ComputeForces |
| `+0x19EC` | 4 | [UNKNOWN] | `WheelTimer1[3]` | ComputeForces |
| `+0x19F0` | 8 | [UNKNOWN] | `WheelTimer2[3]` | ComputeForces |
| `+0x1AF8` | 4 | uint | `PrevBoostState` | ComputeForces, PairComputeForces: `prev = current(5000)` |
| `+0x1388` (5000) | 4 | uint | `CurrentBoostState` | ComputeForces: `*(lVar6 + 5000) = 0` zeroed after copy |
| `+0x16E0` | 4 | uint | `BoostDuration` | ComputeForces: checked != 0 for boost active |
| `+0x16E4` | 4 | f32 | `BoostStrength` | ComputeForces: multiplied into force |
| `+0x16E8` | 4 | uint | `BoostStartTime` | ComputeForces: -1 = no boost, compared to current tick |
| `+0x1BB0` | 8 | ptr | `VehicleModelPtr` | Multiple: `*(longlong *)(lVar6 + 0x1BB0)` |
| `+0x1BB8` | 8 | ptr | `AuxPhysicsPtr` | BeforeMgrDynaUpdate: if set, calls FUN_1407cf3d0 |
| `+0x1BC0` | 1 | byte | `PhyFlags` | BeforeMgrDynaUpdate: bit 0 checked |
| `+0x1BC8` | 8 | ptr | `ContactProcessorPtr` | BeforeMgrDynaUpdate: if set, calls FUN_14084c840 |
| `+0x1BD8` | 4 | int | `ClearForce1` | ComputeForces, PairComputeForces: zeroed |
| `+0x1BDC` | 8 | f64/2xf32 | `ClearForce2` | ComputeForces, PairComputeForces: zeroed |
| `+0x1BF0` | 4 | uint | `ArenaZoneId` | ArenaPhysics_CarPhyUpdate: written from zone lookup |
| `+0x1C78` | 1 | char | `PlayerIndex` | BeforeMgrDynaUpdate: -1 = no player |
| `+0x1C7C` | 4 | uint | `ContactPhyFlags` | Multiple: complex bitfield (see section 3.2) |
| `+0x1C8C` | 4 | f32 | `ContactThreshold` | PhysicsStep_TM: compared to `DAT_141d1ef7c` |
| `+0x1C90` | 4 | int | `SimulationMode` | BeforeMgrDynaUpdate, PhysicsStep_TM: 0=normal, 1=replay, 2=spectator, 3=normal-alt |
| `+0x1C98` | 8 | ptr | `ReplayDataPtr` | BeforeMgrDynaUpdate: memcpy source when mode==1 |

**Total estimated struct size**: at least **0x1CA0** (~7,328 bytes).

### 3.2 ContactPhyFlags Bitfield (+0x1C7C)

**Evidence**: Multiple files
**Confidence**: VERIFIED for bit positions, PLAUSIBLE for meanings

```
Bit 0   (0x01): [UNKNOWN]
Bit 1   (0x02): [UNKNOWN]
Bit 2   (0x04): DisableEvents -- prevents event dispatching
Bit 3   (0x08): HasContactThisTick -- set in ArenaPhysics_CarPhyUpdate
Bit 4   (0x10): SubStepCollisionDetected -- checked in BeforeMgrDynaUpdate
Bits 5-7 (0xE0): ContactType -- cleared with mask 0xFFFFE1F in BeforeMgrDynaUpdate
Bits 9-10 (0x600): Cleared with mask 0xFFFFF5FF in PhysicsStep_TM
Bit 11  (0x800): [UNKNOWN] -- checked with 0x1800 in PhysicsStep_TM
Bit 12  (0x1000): [UNKNOWN] -- checked with 0x1800 in PhysicsStep_TM
Bit 16  (0x10000): SubStepCollisionResult -- set from FUN_141501090 return
```

### 3.3 StatusFlags Low Nibble (+0x128C & 0xF)

**Evidence**: `PhysicsStep_TM.c:68`, `ComputeForces.c:65`, `BeforeMgrDynaUpdate.c:97`, `ExtractVisStates.c:37`
**Confidence**: VERIFIED

| Value | State | Behavior |
|:---:|:---|:---|
| 0 | Active/Ready | Normal physics, checked in BeforeMgrDynaUpdate |
| 1 | Reset/Inactive | Forces zeroed (ComputeForces line 66), visual interpolation = 0 |
| 2 | Excluded | Skipped entirely in PhysicsStep_TM (line 68) |
| 3 | [UNKNOWN] | Checked as `(nibble - 2) < 2` in BeforeMgrDynaUpdate (values 2,3) |

### 3.4 Vehicle Model Structure (accessed via vehicle+0x88)

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:51-56, 112-128`
**Confidence**: VERIFIED

Key offsets on the model object (accessed through `local_118 = *(longlong *)(lVar6 + 0x88)`):

| Offset | Type | Field | Evidence |
|:---|:---:|:---|:---|
| `+0x238` | int | GameModeOrClass | ComputeForces: `*(int *)(local_118 + 0x238) - 5U` |
| `+0x1790` | int | ForceModelType | ComputeForces: switch dispatch |
| `+0x2F0` | f32 | MaxSpeed | ComputeForces: speed clamping |
| `+0x30D8` | varies | [UNKNOWN] | ComputeForces: `FUN_140841ca0(uVar3, lVar6, local_118 + 0x30D8, param_5)` |
| `+0x31A8` | varies | [UNKNOWN] | ComputeForces: `local_168 = local_118 + 0x31A8` |

### 3.5 Vehicle Model Class (accessed via vehicle+0x1BB0)

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:54,66,106`
**Confidence**: VERIFIED

Key offsets on the vehicle model class pointer:

| Offset | Type | Field | Evidence |
|:---|:---:|:---|:---|
| `+0x278` | f32 | TimeOrStateParam | ComputeForces: `*pfVar1 <= 0.0 && *pfVar1 != 0.0` check |
| `+0x2B0` | ptr | TransformVtablePtr | PhysicsStep_TM: `(**(code **)(*plVar10 + 0x28))(plVar10, local_f0)` |
| `+0xE0` | f32 | ModelScale | ComputeForces: multiplied into boost force |

### 3.6 Transform Copy Pattern

**Evidence**: `PhysicsStep_TM.c:199-215`, `ComputeForces.c:200-218`, `PairComputeForces.c:43-90`
**Confidence**: VERIFIED

All three functions contain identical transform copy code, copying 112 bytes from `+0x90` to `+0x104`:

```c
// Copy current transform to previous transform (28 4-byte values = 112 bytes)
*(lVar + 0x104) = *(lVar + 0x90);
*(lVar + 0x10C) = *(lVar + 0x98);
// ... (12 more 8-byte copies)
*(lVar + 0x174) = *(lVar + 0x100);
```

This is a 4x4 matrix (with possible 3x4 + extras) representing the vehicle's world transform. The copy to "previous" happens at the START of each physics step, preserving the last frame's position for interpolation and collision backtracking.

---

## 4. Tire/Wheel Contact Model

### 4.1 Contact Point Processing

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

**Contact structure** (88 bytes / 0x58 stride):

| Offset | Type | Purpose |
|:---|:---:|:---|
| `+0x00` | varies | Contact point position |
| `+0x38` | ptr | Referenced object pointer (for vehicle-vehicle) |
| ... | | [UNKNOWN remaining fields] |

**Key observation**: There are at least 7 separate contact buffers (at param_1 offsets 0x188, 0x198, 0x1A8, 0x1B8, 0x1C8, 0x1D8, 0x1E8), each cleared after processing. This suggests categorized contact types: wheel-ground, body-body, body-wall, etc.

### 4.2 Wheel Contact History (Circular Buffer)

**Evidence**: `NSceneVehiclePhy__PhysicsStep_BeforeMgrDynaUpdate.c:159-192`
**Confidence**: VERIFIED

Each vehicle maintains a circular buffer for wheel contact state tracking:

```c
// Compute surface height parameter (0.0 to 1.0 range)
fVar21 = (*(float *)(lVar19 + 0x9c) - 0.0) * fVar7;  // fVar7 = DAT_141d1fa18
if (fVar21 < 0.0) fVar21 = 0.0;
else if (fVar7 <= fVar21) fVar21 = fVar7;

// Quantize to byte and store in circular buffer
fVar21 = (float)FUN_1407d5780(fVar21);
*(char *)((ulonglong)*puVar16 + 8 + (longlong)puVar16) = (char)(int)fVar21;

// puVar16 is the buffer header at vehicle+0x1594:
//   puVar16[0] = write index (circular)
//   puVar16[1] = buffer size (0x14 = 20 entries)
//   puVar16 + 8 = buffer data (20 bytes)

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

**Struct Offset**: `vehicle+0x1594` = circular buffer header (8 bytes header + 20 bytes data)
**Struct Offset**: `vehicle+0x15B0` = contact state change counter (oscillation detection)

This is used for detecting rapid contact/airborne oscillation (a vehicle bouncing), which affects game logic decisions like fragile surface checks.

### 4.3 Boost/Turbo Force Application

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:89-111`
**Confidence**: VERIFIED
**Struct Offsets**: `vehicle+0x16E0` (duration), `vehicle+0x16E4` (strength), `vehicle+0x16E8` (start time)

The turbo/boost system applies a time-varying directional force:

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

The boost force is:
- **Linearly interpolated**: from 0 at start to `strength * modelScale` at end of duration
- **Direction**: applied via `FUN_1407bdf40` (a force-at-direction function on the dyna manager)
- **Model-scaled**: multiplied by the model object's `+0xE0` field (a global scale factor)

### 4.4 Speed Clamping

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:112-126`
**Confidence**: VERIFIED
**Struct Offset**: `vehicle_model+0x2F0` = MaxSpeed

```c
fVar9 = *(float *)(local_118 + 0x2f0);   // maxSpeed
fVar8 = local_130 * local_130 + local_12c * local_12c + local_128 * local_128;           // speed squared

if ((fVar9 * fVar9 < fVar8) && (DAT_141d1ed34 < fVar9)) {
    fVar8 = SQRT(fVar8);
    fVar9 = fVar9 / fVar8;               // scale factor
    local_130 = local_130 * fVar9;        // clamp velocity x
    local_12c = local_12c * fVar9;        // clamp velocity y
    local_128 = local_128 * fVar9;        // clamp velocity z
    FUN_140845270(uVar3, lVar6, &local_130);  // update velocity
}
```

The speed clamping:
1. Reads max speed from model at `+0x2F0`
2. Computes velocity magnitude squared
3. If exceeds max speed AND max speed > threshold (`DAT_141d1ed34`), scales velocity to exactly match max speed
4. Writes back the clamped velocity

### 4.5 Suspension and Wheel Initialization (Pre-Model Update)

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:127,140-141`
**Confidence**: VERIFIED

Before the force model switch, two setup functions are called:

```c
FUN_140841ca0(uVar3, lVar6, local_118 + 0x30d8, param_5);  // line 127
FUN_140841f40(param_1, uVar3, lVar6, &local_b8);            // line 140
FUN_1408426e0(lVar6, param_5);                               // line 141
```

- `FUN_140841ca0`: Takes the dyna manager, vehicle, model offset `+0x30D8`, and tick. This likely initializes per-wheel contact state and surface detection.
- `FUN_140841f40`: Takes the arena, dyna manager, vehicle, and the force vector (from either `+0x144C` or `+0x1534`). This likely applies pre-computed suspension forces.
- `FUN_1408426e0`: Takes just the vehicle and tick. This likely updates wheel rotation/position state.

### 4.6 PairComputeForces (Vehicle-to-Vehicle Interaction)

**Evidence**: `NSceneVehiclePhy__PairComputeForces.c:1-93`
**Confidence**: VERIFIED
**Address**: FUN_140842ed0

When two vehicles collide, `PairComputeForces` handles the interaction. It:

1. Resolves both vehicle entities via `FUN_1407bea40` (lines 25-29)
2. Fetches velocity, position, and force data for BOTH vehicles (lines 30-36)
3. Initializes boost start time for both if needed (lines 37-42)
4. Copies current transform to previous for BOTH vehicles (lines 43-90)
5. Resets force accumulators for BOTH vehicles:
   - `+0x1BDC` = 0 (clear force)
   - `+0x1BD8` = 0 (clear force)
   - `+0x1AF8` = `+0x1388` (copy boost state)
   - `+0x1388` = 0 (clear boost)
   - `+0x156C` = 0 (clear slip counter)
   - `+0x1570` = zero vector
   - `+0x1578` = zero
   - `+0x1408` = 0 (clear accumulator flag)

This function does NOT compute forces itself -- it prepares two-body state for the dynamics solver to handle the collision response.

---

## 5. Collision System

### 5.1 StartPhyFrame (Frame Initialization)

**Evidence**: `NHmsCollision__StartPhyFrame.c:1-57`
**Confidence**: VERIFIED
**Address**: FUN_1402a9c60

Each physics frame begins with collision initialization:

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
    *(item + 0x94) = *(item + 0x74);
    *(item + 0x98) = *(item + 0x78);
    *(item + 0x9C) = *(item + 0x7C);
    FUN_140194860();
```

**Key structure**: Each collidable item has:
- `+0x74`: Current position (3 x float32 = vec3)
- `+0x94`: Previous position (3 x float32 = vec3, copied from current at frame start)
- `+0xA4`: Hit body index (uint, 0xFFFFFFFF = no hit)

Two separate collision item sets exist at manager offsets `+0x9C8` and `+0xA58`, suggesting separation of static-collidable and dynamic-collidable objects.

### 5.2 DynamicCollisionCreateCache

**Evidence**: `NSceneDyna__DynamicCollisionCreateCache.c:1-88`
**Confidence**: VERIFIED
**Address**: FUN_1407f9da0

This function creates a collision cache for the dynamics solver. For each dynamic body:

```c
// Cache entry is 0x38 bytes (56 bytes = 14 uint32s), stride matches body struct

// Read collision shape type and filter masks
puVar7[8] = *(uint *)(&DAT_141fabc20 + *(byte *)(lVar2 + 0x11) * 4)
          & ~*(uint *)(lVar2 + 0x18);     // collision_layer_mask & ~exclusion_mask

// Copy AABB or position data
puVar7[0..3] = local_48/uStack_40;        // AABB min or position

// Compute collision layer bit
if (*(char *)(lVar2 + 0x11) != 0) {
    iVar9 = 1 << (*(char *)(lVar2 + 0x11) - 1);  // layer bit from layer index
}
puVar7[9] = iVar9;                         // collision_layer_bit

// Copy additional collision properties
puVar7[10] = *(lVar2 + 0x14);             // [UNKNOWN] collision property
puVar7[11] = *(lVar2 + 0xa4);             // hit body index reference

// Copy collision type byte
*(byte *)(puVar7 + 0xc) = *(byte *)(lVar2 + 0x11);  // collision type

// Check if body is sleeping or static
bVar5 = (body_is_sleeping || body_has_no_solver_pair) ? 1 : 0;
bVar6 = (body_has_kinematic_flag) ? 2 : 0;

// Clear impulse accumulators
*(puVar7 + 4..7) = 0;                     // 16 bytes of impulse data cleared

// Check for compound collision shape (type 0xD)
if (*(int *)(shape + 0xC) == 0xD && *(int *)(shape + 0x58) != 0) {
    *(puVar7 + 4) = shape + 0x50;          // compound shape sub-shapes pointer
    *(puVar7 + 6) = lVar2 + 0x50;          // body transform pointer
}
```

**Cache entry layout** (56 bytes / 0x38 stride):

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

**Layer system**: The global table at `DAT_141fabc20` maps collision type bytes (0x00-0xFF) to layer masks. The actual mask is computed as `layer_table[type] & ~body_exclusion_mask`, allowing per-body collision filtering.

### 5.3 Contact Merging Algorithm

**Evidence**: `NHmsCollision__MergeContacts.c:1-271`
**Confidence**: VERIFIED
**Address**: FUN_1402a8a70

The contact merging algorithm reduces redundant contact points to improve solver stability:

**Parameters**:
- `param_1`: Contact manager (array + count)
- `param_2`: Normal dot threshold (float, minimum dot product for normals to be "similar")
- `param_3`: Distance threshold (float, maximum distance between contact points)

**Algorithm**:

```
Phase 1: Find merge candidates
    For each contact pair (i, j) where j > i:
        // Position check
        dist = |position_i - position_j|
        if dist > param_3: skip

        // Normal check
        dot = normal_i . normal_j
        if dot < param_2: skip

        // Layer check (collision type != 1 for both)
        if type_i == 1 OR type_j == 1: skip

        // If all checks pass, add to merge group
        FUN_1402a9130(shape, merge_groups, group_indices, (i, j))

Phase 2: Execute merges
    For each merge group:
        survivor = last contact in group

        For each contact in group (if type != 0xD):
            // Accumulate averaged contact data:
            avg_position += contact.position
            avg_normal += contact.normal
            avg_impulse += contact.impulse
            count++

        // Normalize accumulated normal
        if |avg_normal|^2 > DAT_141d1ecc4 AND < DAT_141d1fc24:
            avg_normal = normalize(avg_normal) * DAT_141d1f3c8  // scale to unit

        // Write merged result to survivor contact
        survivor.normal = avg_normal
        survivor.position = avg_position / count
        survivor.impulse = avg_impulse / count
        survivor.flags &= ~0x02   // clear "needs merge" flag

Phase 3: Remove consumed contacts
    Sort indices of consumed contacts
    Remove from contact array in reverse order (FUN_1402aa090)
```

**Key constants**:
- `DAT_141d1ecc4`: Minimum normal length squared (prevents zero-division)
- `DAT_141d1fc24`: Maximum normal length squared (sanity check)
- `DAT_141d1f3c8`: Normal scale factor (likely 1.0f for unit normalization)

**Contact structure fields used in merging** (from the contact array with stride 0x58 = 88 bytes):

| Offset | Purpose | Accessed by |
|:---:|:---|:---|
| `+0x08` | Shape reference pointer | Layer check |
| `+0x10` | Impulse x | Accumulated in merge |
| `+0x14` | Impulse y | Accumulated in merge |
| `+0x18` | Impulse z | Accumulated in merge |
| `+0x1C` | Contact normal x | Dot product, accumulation |
| `+0x20` | Contact normal y | Dot product, accumulation |
| `+0x24` | Contact normal z | Dot product, accumulation |
| `+0x28` | Contact position x | Distance check, averaging |
| `+0x2C` | Contact position y | Distance check, averaging |
| `+0x30` | Contact position z | Distance check, averaging |
| `+0x34` | Alternate normal x | Used when normal dot < threshold |
| `+0x38` | Alternate normal y | Used when normal dot < threshold |
| `+0x3C` | Alternate normal z | Used when normal dot < threshold |
| `+0x40` | [UNKNOWN] position x (secondary) | Used for dual-point contacts |
| `+0x44` | [UNKNOWN] position y (secondary) | Used for dual-point contacts |
| `+0x48` | [UNKNOWN] position z (secondary) | Used for dual-point contacts |
| `+0x52` | Contact type (short) | Checked for 0x0D (compound) |
| `+0x54` | Contact flags | Bit 1 = has alternate; bit 0 = [UNKNOWN] |

### 5.4 Friction Solver Configuration

**Evidence**: `FrictionIterCount_Config.c:1-105`
**Confidence**: VERIFIED
**Address**: FUN_1407f3fc0

The friction solver is configured via the `NSceneDyna::SSolverParams` struct (0x2C = 44 bytes):

```c
// Struct: NSceneDyna::SSolverParams (44 bytes)
FUN_1402ea9e0(*puVar1, "NSceneDyna::SSolverParams", 0x2c, 0, 0, 0, 0);
```

| Struct Offset | Type | Name | Description |
|:---:|:---:|:---|:---|
| `0x00` | int | `FrictionStaticIterCount` | Number of static friction solver iterations |
| `0x04` | int | `FrictionDynaIterCount` | Number of dynamic friction solver iterations |
| `0x08` | int | `VelocityIterCount` | Number of velocity solver iterations |
| `0x0C` | int | `PositionIterCount` | Number of position correction iterations |
| `0x10` | float | `DepenImpulseFactor` | Depenetration impulse scaling factor |
| `0x14` | float | `MaxDepenVel` | Maximum depenetration velocity |
| `0x18` | bool | `EnablePositionConstraint` | Whether position correction is active |
| `0x1C` | float | `AllowedPen` | Allowed penetration depth (auto if negative) |
| `0x20` | int | `VelBiasMode` | Velocity bias computation mode |
| `0x24` | bool | `UseConstraints2` | Whether to use second-generation constraints |
| `0x28` | float | `MinVelocityForRestitution` | Minimum velocity to apply restitution |

**Key insight**: The solver has **separate iteration counts** for static friction, dynamic friction, velocity solving, and position correction. This is a **sequential impulse / Gauss-Seidel style** constraint solver with configurable convergence per category.

The note `"auto AllowedPen if negative"` (line 81) means a negative AllowedPen value triggers automatic computation of the penetration tolerance.

---

## 6. Surface Effects

### 6.1 Complete Surface Gameplay Effect Enum

**Evidence**: `NHmsCollision__StartPhyFrame.c:100-128` (string table)
**Confidence**: VERIFIED (strings confirmed at addresses)

The `EPlugSurfaceGameplayId` enum values, in address order:

| String Address | Effect Name | Description |
|:---|:---|:---|
| `0x141be1238` | `NoSteering` | Disables steering input |
| `0x141be1244` | `NoGrip` | Zero friction surface |
| `0x141be124c` | `Reset` | Resets vehicle to last checkpoint |
| `0x141be1258` | `ForceAcceleration` | Forces constant acceleration |
| `0x141be126c` | `Turbo` | Turbo boost level 1 |
| `0x141be1278` | `FreeWheeling` | Disengages engine (coasting) |
| `0x141be1288` | `Turbo2` | Turbo boost level 2 |
| `0x141be1290` | `ReactorBoost2_Legacy` | Legacy reactor boost level 2 (non-directional) |
| `0x141be12a8` | `Fragile` | Vehicle breaks on hard impact |
| `0x141be12b0` | `NoBrakes` | Disables brake input |
| `0x141be12bc` | `Bouncy` | High-restitution surface |
| `0x141be12c4` | `Bumper` | Bumper surface level 1 |
| `0x141be12d0` | `SlowMotion` | Reduces simulation speed |
| `0x141be12e0` | `ReactorBoost_Legacy` | Legacy reactor boost (non-directional) |
| `0x141be12f8` | `Bumper2` | Bumper surface level 2 |
| `0x141be1300` | `VehicleTransform_CarRally` | Transforms vehicle to Rally car |
| `0x141be1320` | `VehicleTransform_CarSnow` | Transforms vehicle to Snow car |
| `0x141be1358` | `VehicleTransform_CarDesert` | Transforms vehicle to Desert car |
| `0x141be1378` | `ReactorBoost_Oriented` | Directional reactor boost |
| `0x141be1390` | `Cruise` | Sets cruise control speed |
| `0x141be1398` | `VehicleTransform_Reset` | Transforms vehicle back to Stadium car |
| `0x141be13b0` | `ReactorBoost2_Oriented` | Directional reactor boost level 2 |

### 6.2 Turbo Implementation Details

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:89-111`
**Confidence**: VERIFIED

The turbo system in TM2020 uses the same boost mechanism described in section 4.3:

- **Turbo (level 1)**: Sets `vehicle+0x16E0` (duration), `+0x16E4` (strength), `+0x16E8` (start time)
- **Turbo2 (level 2)**: Same offsets, different duration/strength values
- **Turbo3Roulette**: Randomized turbo that selects from `TurboRoulette_1`, `_2`, `_3` with different strengths

The force is applied linearly over the duration: `force(t) = (t / duration) * strength * modelScale`.

### 6.3 Fragile Surface Check

**Evidence**: `PhysicsStep_TM.c:191-195`
**Confidence**: VERIFIED

```c
if ((((*(uint *)(lVar9 + 0x1c7c) & 0x1800) == 0x1800) &&
    (DAT_141d1ef7c < *(float *)(lVar9 + 0x1c8c))) &&
   (1 < (*(uint *)(lVar9 + 0x128c) & 0xf) - 2)) {
    FUN_1407d2870(param_1, lVar9, *param_4);
}
```

The fragile check requires ALL THREE conditions:
1. **Flags 0x1800 both set**: Both collision flags at bits 11 and 12 must be active
2. **Threshold exceeded**: Float at `vehicle+0x1C8C` must exceed global `DAT_141d1ef7c` (a collision severity threshold)
3. **Status nibble check**: The expression `(nibble - 2)` uses unsigned arithmetic, so `1 < (nibble - 2)` passes for nibble values **0, 1, and 4+**. Only nibble values 2 and 3 are excluded. (Nibble values 0 and 1 cause unsigned underflow: e.g., 0-2 = 0xFFFFFFFE, and `1 < 0xFFFFFFFE` is true in unsigned comparison.)

`FUN_1407d2870` is the crash/reset handler that triggers the fragile vehicle breakage.

---

## 7. Gravity and Sub-stepping

### 7.1 Gravity Computation

**Evidence**: `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c:1-103`
**Confidence**: VERIFIED
**Address**: FUN_1407f89d0

The gravity function iterates over all dynamic bodies and applies gravity, sleep detection, and velocity integration:

```
for each body i in 0..param_1:
    if (body_flags & 2) == 0:  // not kinematic/static

        // ===== SLEEP DETECTION =====
        if DAT_141ebccfc != 0:  // sleep enabled
            linear_speed_sq = vx^2 + vy^2 + vz^2
            if linear_speed_sq < DAT_141ebcd04^2:
                vx *= DAT_141ebcd00   // damp
                vy *= DAT_141ebcd00
                vz *= DAT_141ebcd00

            angular_speed_sq = wx^2 + wy^2 + wz^2
            if angular_speed_sq < DAT_141ebcd04^2:
                wx *= DAT_141ebcd00
                wy *= DAT_141ebcd00
                wz *= DAT_141ebcd00

        // ===== GRAVITY APPLICATION =====
        gravity_scale = FUN_1407f5130_result * body_mass

        if body_pair == -1:
            velocity = (0, 0, 0)       // fully static
            angular = (0, 0, 0)
        else:
            // Apply gravity to force accumulator
            force += gravity_scale * gravity_direction

            // Integrate linear velocity: v += F * inv_mass * dt
            vel += force * inv_mass * dt

            // Integrate angular velocity: w += torque * inv_inertia * dt
            ang += torque * inv_inertia * dt

        // Clear force accumulators for next frame
        force_accumulator = (0, 0, 0, 0, 0, 0)
```

### 7.2 Sleep Detection Constants

**Evidence**: `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c:27,40-57`
**Confidence**: VERIFIED

| Global | Purpose | Type |
|:---|:---|:---:|
| `DAT_141ebccfc` | Sleep detection enabled flag | int |
| `DAT_141ebcd00` | Sleep velocity damping factor | float |
| `DAT_141ebcd04` | Sleep velocity threshold (linear m/s; squared by code before comparison) | float |

The sleep system:
1. Check if sleep detection is enabled (`DAT_141ebccfc != 0`)
2. Compute velocity magnitude squared
3. If below threshold, multiply each component by damping factor (< 1.0)
4. Applied separately to linear and angular velocity
5. Does NOT immediately zero velocity -- gradual damping over multiple frames

### 7.3 Adaptive Sub-stepping Algorithm

**Evidence**: `PhysicsStep_TM.c:71-167`
**Confidence**: VERIFIED

```
Step 1: velocity_scale = FUN_14083dca0(vehicle+0x1280, model_ptr)
Step 2: scaled_dt = velocity_scale * dt

Step 3: Compute 4 velocity magnitudes:
   |v_linear|  from body at (lVar15+0x40..0x48)
   |v_angular| from body at (lVar15+0x4C..0x54)
   |v_wheel1|  from vehicle at (+0x1348..0x1350)
   |v_wheel2|  from vehicle at (+0x1354..0x135C)

Step 4: num_substeps = floor((total_speed * scaled_dt) / body_step_size) + 1

Step 5: Clamp to 1000
   if num_substeps >= 1001:
       num_substeps = 1000
       sub_dt = dt / 1000.0

Step 6: Sub-step loop (N-1 iterations):
   for i in 0..num_substeps-1:
       a. Collision detection
       b. Set dyna time
       c. Compute forces (FUN_1414ffee0)
       d. Post-force update (FUN_1414ff9d0)
       e. Physics step (FUN_1415009d0)
       f. Integration (FUN_14083df50)
       g. Advance time counter

Step 7: Final step with accumulated remainder
```

### 7.4 Sub-stepping Key Parameters

| Parameter | Value | Evidence |
|:---|:---|:---|
| Maximum substeps | **1000** (0x3E9 - 1 = 0x3E8) | `if (uVar16 >= 0x3E9)` then cap at 999 |
| Divisor at +0x54 | float from body state | `*(float *)(lVar15 + 0x54)` |
| Time constant | `DAT_141d1fa9c` | Used as divisor when capping (likely 1000.0f) |
| Microsecond conversion | `_DAT_141d1fe58` (double) | Multiplied by sub_dt for time advance |

**Sub-step formula**:
```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = floor((total_speed * velocity_scale * dt) / step_size_param) + 1
num_substeps = clamp(num_substeps, 1, 1000)
sub_dt = dt / num_substeps
```

---

## 8. Water Physics

### 8.1 Water Force Computation

**Evidence**: `NSceneDyna__ComputeWaterForces.c:1-53`
**Confidence**: VERIFIED
**Address**: FUN_1407f8290

```c
// Only compute if water exists (param_8 != 0)
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

### 8.2 Water Model Architecture

Two-tier water lookup:
```
Body collision item -> offset +0x128 -> custom water reference
    If null:
        Global water -> *param_2 + 0x48 -> default water
    Else:
        Custom water -> *(item+0x128) + 0x38 -> specific water shape
```

The `+0x128` offset on the collision item is a pointer to a water-zone association, allowing bodies in different water volumes to experience different water properties.

---

## 9. Tuning Parameters and Numeric Constants

### 9.1 Global Constants from Decompiled Code

| Address | Context | Likely Purpose | Type | Evidence |
|:---|:---|:---|:---:|:---|
| `DAT_141d1fa9c` | PhysicsStep_TM: `/ DAT_141d1fa9c` when cap at 1000 | 1000.0f (max substep count) | float | `if (uVar16 >= 0x3E9)` then divide by this |
| `DAT_141d1fe58` | PhysicsStep_TM: `dVar11 = (double)fVar26 * _DAT_141d1fe58` | 1,000,000.0 (microsecond conversion) | double | Converts sub_dt seconds to microseconds |
| `DAT_141d1ed34` | ComputeForces: speed clamping threshold | Min speed threshold for clamping | float | `DAT_141d1ed34 < fVar9` |
| `DAT_141d1ee10` | PhysicsStep_TM: used in force loop | [UNKNOWN] constant | float | Used as parameter to step functions |
| `DAT_141d1ef7c` | PhysicsStep_TM: fragile threshold | Collision severity threshold for fragile | float | `DAT_141d1ef7c < *(float *)(lVar9 + 0x1c8c)` |
| `DAT_141d1fa18` | BeforeMgrDynaUpdate: surface height scale | Surface parameter scale factor | float | `fVar7 = DAT_141d1fa18` used in height calc |
| `DAT_141d1ecc4` | MergeContacts: min normal length | Minimum squared normal length | float | Prevents zero-division |
| `DAT_141d1fc24` | MergeContacts: max normal length | Maximum squared normal length | float | Sanity check |
| `DAT_141d1f3c8` | MergeContacts: normal scale | Scale for normalized normal (1.0f) | float | `DAT_141d1f3c8 / sqrt(length)` |
| `DAT_141a64350` | Multiple: zero velocity constant | `{0.0f, 0.0f}` (8 bytes) | 2xfloat | Used to zero velocity vectors |
| `DAT_141a64358` | Multiple: zero z component | `0.0f` | float | Z component of zero vector |
| `DAT_141ebccfc` | Gravity: sleep enabled flag | Sleep detection toggle | int | `if (DAT_141ebccfc != 0)` |
| `DAT_141ebcd00` | Gravity: sleep damping | Sleep velocity damping factor (< 1.0) | float | `velocity *= DAT_141ebcd00` |
| `DAT_141ebcd04` | Gravity: sleep threshold | Sleep velocity threshold (linear m/s) | float | `if (speed_sq < DAT_141ebcd04^2)` |
| `DAT_141e64060` | Multiple: stack cookie | Security check cookie | uint64 | `local_d8 = DAT_141e64060 ^ (ulonglong)stack` |
| `DAT_141fabc20` | DynCollision: layer table | Collision layer mask lookup table | uint[] | `*(DAT_141fabc20 + type * 4)` |

### 9.2 Tuning Coefficient System

**Evidence**: `Tunings_CoefFriction_CoefAcceleration.c:1-48`
**Confidence**: VERIFIED

The `NGameSlotPhy::SMgr` struct (0x90 = 144 bytes):

| Struct Offset | Type | Name | Purpose |
|:---:|:---:|:---|:---|
| `0x58` | float | `Tunings.CoefFriction` | Global friction multiplier |
| `0x5C` | float | `Tunings.CoefAcceleration` | Global acceleration multiplier |
| `0x60` | float | `Tunings.Sensibility` | [UNKNOWN] Sensibility tuning |

### 9.3 Solver Parameter Structure

Complete SSolverParams layout (44 bytes):

| Offset | Type | Name | Typical Range |
|:---:|:---:|:---|:---|
| `0x00` | int | `FrictionStaticIterCount` | 1-20 |
| `0x04` | int | `FrictionDynaIterCount` | 1-20 |
| `0x08` | int | `VelocityIterCount` | 1-20 |
| `0x0C` | int | `PositionIterCount` | 1-10 |
| `0x10` | float | `DepenImpulseFactor` | 0.0 - 1.0 |
| `0x14` | float | `MaxDepenVel` | > 0.0 |
| `0x18` | bool | `EnablePositionConstraint` | 0 or 1 |
| `0x1C` | float | `AllowedPen` | negative = auto |
| `0x20` | int | `VelBiasMode` | 0, 1, 2... |
| `0x24` | bool | `UseConstraints2` | 0 or 1 |
| `0x28` | float | `MinVelocityForRestitution` | > 0.0 |

### 9.4 Known Numeric Constants from Code

| Constant | Value | Context |
|:---|:---:|:---|
| `0x3E9` | 1001 | Max substep count + 1 (PhysicsStep_TM) |
| `999` | 999 | Actual max substep count (PhysicsStep_TM) |
| `1000000` | 1,000,000 | Tick to microsecond conversion |
| `0x58` | 88 | Contact point stride (bytes) |
| `0x38` | 56 | Body data stride (bytes) |
| `0xE0` | 224 | 4 * body stride (unrolled loop) |
| `0xB8` | 184 | Per-wheel state block stride (ComputeForces reset) |
| `0x2C` | 44 | SSolverParams struct size |
| `0x90` | 144 | NGameSlotPhy::SMgr struct size |
| `0x878` | 2168 | Replay state copy size |
| `0x14` | 20 | Wheel contact history buffer size |
| `0x0D` | 13 | Compound collision shape type |
| `0x0F` | 15 | Mask value for status nibble extraction |
| `0x1800` | Bits 11+12 | Fragile contact flags mask |
| `0xE0` | Bits 5-7 | Contact type flags mask |
| `0xFFFFF5FF` | ~(bits 9-10) | Physics flags clear mask |
| `0xFFFFE1F` | ~(bits 5-7, bit 8) | Contact type clear mask |

---

## 10. Determinism

### 10.1 Fixed Timestep Architecture

**Evidence**: `PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`, TMNF diary
**Confidence**: PLAUSIBLE

The physics engine uses a **fixed 100Hz tick rate** (10ms per tick). Key determinism features:

1. **Integer tick counter**: All timing is driven by integer tick counts, not floating-point accumulated time
2. **Tick-to-microseconds**: `tick * 1000000` uses integer multiplication, avoiding float precision issues in time tracking
3. **Adaptive sub-stepping**: Within each fixed tick, sub-stepping is deterministic given the same velocity state

### 10.2 Consistent Floating Point Patterns

1. **Magnitude computation**: Always uses `x*x + y*y + z*z` then `SQRT()`, never `length()` utilities that might vary
2. **Negative sqrt guard**: Every sqrt call is preceded by a `< 0.0` check:
   ```c
   if (fVar24 < 0.0) {
       fVar24 = (float)FUN_14195dd00(fVar24);  // safe sqrt
   } else {
       fVar24 = SQRT(fVar24);
   }
   ```
3. **FUN_14195dd00**: A "safe sqrt" function called when the value is negative. Likely returns `sqrt(abs(x))` or `0.0f`.

### 10.3 Sub-step Remainder Handling

The sub-step loop processes `N-1` equal steps, then one final step with the accumulated remainder:

```
total = (N-1) * sub_dt + remainder
      = (N-1) * (dt/N) + (dt - (N-1) * dt/N)
      = dt  (exactly)
```

### 10.4 Platform Considerations

The code uses standard `float` (32-bit IEEE 754) throughout, with occasional `double` (64-bit) for time conversion. The x64 target uses SSE for floating-point, which provides deterministic results within the same platform. The `SQRT()` macro maps to the SSE `sqrtss` instruction, which is IEEE 754 compliant.

### 10.5 Ordering Guarantees

Bodies and vehicles are processed in array order (sequential iteration, no parallel dispatch):

```c
// PhysicsStep_V2: iterate ordered indices
do {
    uVar2 = *(uint *)(param_1[0x16] + (ulonglong)*puVar12 * 4);
    puVar12 = puVar12 + 1;
} while (uVar11 < uVar1);

// PhysicsStep_TM: iterate vehicle array
plVar19 = (longlong *)*param_3;
do {
    lVar9 = *plVar19;
    plVar19 = plVar19 + 1;
} while (local_148 != 0);
```

---

## 11. Differences from TMNF

### 11.1 Summary Table

| Feature | TMNF | TM2020 |
|:---|:---|:---|
| Force model count | 4 (cases 3,4,5,default) | 7 (cases 0-2,3,4,5,6,0xB) |
| Max substeps | 10,000 | 1,000 |
| Velocity inputs for substep calc | 2 (linear + angular) | 4 (linear + 3 angular) |
| Vehicle state struct size | ~2,112 bytes | ~7,328 bytes |
| Architecture | x86 (32-bit, x87 FPU) | x64 (64-bit, SSE) |
| Time conversion | `tick * 0.001` (ms) | `tick * 1000000` (us) |
| Transform copy | 48 bytes | 112 bytes |
| RTTI | Full type descriptors | Stripped (identified by profiling strings) |
| Pair physics | Not observed | Explicit `PairComputeForces` |
| Boost force curve | Decays: starts high, decreases to 0 | Ramps UP: starts at 0, increases to max |
| Vehicle types | Stadium only | Stadium + Rally + Snow + Desert |

### 11.2 Critical Boost Force Direction Change

**Evidence**: `NSceneVehiclePhy__ComputeForces.c:105-106` vs TMNF diary
**Confidence**: VERIFIED

**TMNF**: `boost_force = (1.0 - t/duration) * strength` -- force DECAYS from max to zero
**TM2020**: `boost_force = (t/duration) * strength * modelScale` -- force RAMPS UP from zero to max

This means in TM2020, the car accelerates MORE as the boost is about to expire. This is a fundamental behavioral change from TMNF.

---

## 12. Curious Questions Answered

### Q1: "I just hit a turbo pad. What EXACTLY happens?"

#### The Complete Turbo Code Path

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

**Step-by-step from `NSceneVehiclePhy__ComputeForces.c:89-111`:**

1. **First tick with boost pending** (line 89): The code checks `if (*(int *)(lVar6 + 0x16e8) == -1)`. If the boost start time is uninitialized (`0xFFFFFFFF`), it records the current tick: `*(uint *)(lVar6 + 0x16e8) = param_5`.

2. **Event dispatch** (lines 91-99): If the boost has a non-zero duration AND the arena has an event callback AND events are not disabled (bit 2 of `+0x1C7C` is clear) AND the vehicle has a valid player index, it dispatches a boost event via `FUN_1407d6200()`. The event data includes the vehicle ID (`+0x1280`), a magic float `1.12104e-44` (likely a type indicator, possibly IEEE representation of an integer), and the tick stamp.

3. **Force computation** (lines 101-108): Each tick while `start_time <= current_tick <= start_time + duration`:
   ```c
   float t = (float)(current_tick - start_time) / (float)duration;
   float force = t * strength * model_scale;
   FUN_1407bdf40(dyna_mgr, body_id, &force_vec);
   ```

4. **Force direction**: The force vector `local_b8` is initialized as a scalar and applied via `FUN_1407bdf40`, which applies force along the body's forward direction (inferred from it being a directional force function on the dynamics manager).

#### The Ramp-Up Controversy -- RESOLVED

The decompiled code at `ComputeForces.c:105` is unambiguous:

```c
local_b8 = ((float)(param_5 - uVar2) / (float)*(uint *)(lVar6 + 0x16e0)) *
           *(float *)(lVar6 + 0x16e4) * *(float *)(*(longlong *)(lVar6 + 0x1bb0) + 0xe0);
```

This computes `(elapsed / duration) * strength * modelScale`. When `elapsed = 0`, force = 0. When `elapsed = duration`, force = `strength * modelScale`. **The boost force linearly ramps UP over its duration.** This is the opposite of TMNF's decay model.

**Implication for gameplay**: The initial "kick" from a turbo pad is zero. The force builds gradually, reaching maximum at the instant the boost expires. This creates a smooth acceleration curve rather than an instant jolt.

#### Turbo Levels

From the `EPlugSurfaceGameplayId` enum:

| Level | String | Duration/Strength |
|:---:|:---|:---|
| Turbo | `"Turbo"` at `0x141be126c` | [NEEDS INVESTIGATION - stored in GBX tuning, not in .exe] |
| Turbo2 | `"Turbo2"` at `0x141be1288` | [NEEDS INVESTIGATION - stored in GBX tuning, not in .exe] |
| TurboRoulette | `TurboRoulette_1/2/3` | [NEEDS INVESTIGATION - randomized selection] |

The actual duration and strength values for each turbo level are NOT hardcoded in the executable. They are loaded from GBX resource files (vehicle tuning data). From TMNF cross-reference: TMNF used TurboBoost=5.0/Duration=250ms and Turbo2Boost=20.0/Duration=100ms. TM2020 values may differ.

---

### Q2: "How does the car stay on a vertical wall or a loop?"

#### What the Code Shows

There is **no special "sticky" force** in the decompiled dispatcher-level code. The wall/loop adhesion comes from the interaction of multiple systems:

1. **Gravity with GravityCoef**: From `NSceneDyna__ComputeGravityAndSleepStateAndNewVels.c:68-77`, gravity is applied as:
   ```
   force += gravity_scale * gravity_direction * body_mass * dt
   ```
   The `gravity_scale` comes from `FUN_1407f5130`, which reads a per-body mass property. TMNF's `GravityCoef = 3.0` (from the tuning GBX) multiplies the base gravity by 3x. This means the game's gravity is roughly `3 * 9.81 = 29.43 m/s^2` -- much stronger than real life.

2. **Contact normals direct forces**: When the car's wheels contact a wall or loop surface, the contact normal points AWAY from the surface (inward, toward the car). The friction solver (configured in `FrictionIterCount_Config.c`) resolves constraints along these normals, keeping the car pressed to the surface.

3. **Centripetal force from speed**: At sufficient speed, the car's velocity around a loop generates centripetal force that pushes it into the surface. Combined with the exaggerated gravity coefficient, this keeps the car attached.

4. **Speed threshold for falling off**: There is no explicit "minimum speed for wall riding" constant in the decompiled code. Instead, the car falls off when the combination of gravity pulling it away from the surface exceeds the centripetal force plus tire friction. This is an emergent property of:
   - The car's speed (lower speed = less centripetal force)
   - The surface curvature (tighter loop = more centripetal force needed)
   - The GravityCoef (higher = harder to stay on)
   - The friction coefficients

**What we cannot answer from the decompiled code**: The actual force model functions (FUN_140851f00 for CarSport, etc.) are NOT decompiled. The per-wheel force computation that generates lateral/longitudinal tire forces -- the code that actually makes wall-riding work -- is inside those large, un-decompiled functions. [NEEDS INVESTIGATION: decompile FUN_140851f00]

---

### Q3: "What happens when I crash into a wall?"

#### The Collision Pipeline

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

#### The Bounce/Response (Coefficient of Restitution)

From `FrictionIterCount_Config.c:102`:
```c
FUN_1402eb040("MinVelocityForRestitution", 0x28, &local_48);
```

The `MinVelocityForRestitution` parameter at SSolverParams offset `0x28` defines the minimum impact velocity required for a bounce. Below this threshold, the collision is purely inelastic (no bounce). The actual coefficient of restitution value is [NEEDS INVESTIGATION -- likely stored per-material in the `EPlugSurfaceMaterialId` data, not in the solver params].

The `Bouncy` gameplay surface (`0x141be12bc`) explicitly creates high-restitution behavior, confirming that restitution is a per-surface property.

#### Contact Merging Details

From `NHmsCollision__MergeContacts.c`:

When the car hits a wall, multiple contact points may be generated (one per mesh triangle in the collision zone). The merge algorithm:

1. Groups contacts where `distance < threshold` AND `dot(normal_i, normal_j) > dot_threshold`
2. Averages position, normal, and impulse across the group
3. Normalizes the averaged normal
4. Keeps one "survivor" contact per group
5. Removes all consumed contacts in reverse index order

This reduces solver jitter from having too many redundant constraints at the same point.

---

### Q4: "How does ice/dirt/grass affect driving?"

#### The Two-ID Surface System

From `04-physics-vehicle.md` and string evidence:

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

**Key insight**: Surface PHYSICS (friction) come from `EPlugSurfaceMaterialId`, while surface GAMEPLAY EFFECTS come from `EPlugSurfaceGameplayId`. These are independent systems.

#### Known Material Types and Their Physics Role

From `19-openplanet-intelligence.md` (Material Library, 208 materials):

| Surface ID | Physics Role | Friction Level |
|:---|:---|:---|
| `Asphalt` | Road surface | HIGH grip |
| `Concrete` | Structural | HIGH grip |
| `Dirt` | Off-road | MEDIUM grip |
| `Grass` | Natural ground | LOW grip |
| `Ice` | Frozen surface | VERY LOW grip |
| `RoadIce` | Icy road | VERY LOW grip |
| `Plastic` | Inflatable | MEDIUM grip, bouncy |
| `Rubber` | Track borders | HIGH grip, bouncy |

#### How Surface Transitions Work

The per-wheel `GroundContactMaterial` field (an `ESurfId` / `uint16`) is updated every physics tick based on which surface the wheel's raycast hits. This means:

1. **Each wheel independently detects its surface** -- you can have front wheels on asphalt and rear wheels on ice
2. **The friction coefficient changes instantly** when the wheel crosses a surface boundary (no blending/transition period visible in the decompiled code)
3. **The actual friction multiplier** is applied inside the force model functions (FUN_140851f00 etc.), which read the per-wheel material and look up the corresponding friction value from the tuning data

#### NoGrip and SlowMotion

- `NoGrip` (`0x141be1244`): A gameplay effect that sets friction to zero. This is NOT a material -- it is a gameplay trigger zone that overrides the normal friction computation.
- `SlowMotion` (`0x141be12d0`): Reduces the `SimulationTimeCoef` (visible in Openplanet's `CSceneVehicleVisState`), slowing down the entire physics simulation for that vehicle.

**What we cannot fully answer**: The exact friction coefficient values per material are stored in GBX tuning resources, not in the executable. The `Tunings.CoefFriction` at NGameSlotPhy offset `0x58` provides a global multiplier, but per-material base values are [NEEDS INVESTIGATION -- extract from StadiumCar tuning GBX].

---

### Q5: "How does the sub-stepping algorithm work?"

#### Complete Walkthrough (from `PhysicsStep_TM.c`)

Here is the algorithm, line by line:

**1. Time setup** (line 63):
```c
lVar18 = (ulonglong)*param_4 * 1000000;  // tick -> microseconds
```
If the tick value is 1 (one 100Hz tick = 10ms), this produces 1,000,000 microseconds = 0.01 seconds.

**2. Velocity scale factor** (line 71):
```c
fVar21 = FUN_14083dca0(vehicle + 0x1280, model_ptr);
fVar25 = fVar21 * (float)param_4[2];  // scale * dt
```
`FUN_14083dca0` computes a velocity-dependent scale factor from the vehicle state. `param_4[2]` is the delta time in seconds (e.g., 0.01 for 100Hz).

**3. Four velocity magnitudes** (lines 78-116):
```
|v1| = sqrt(body.linear_vel.x^2 + body.linear_vel.y^2 + body.linear_vel.z^2)
|v2| = sqrt(body.angular_vel.x^2 + body.angular_vel.y^2 + body.angular_vel.z^2)
|v3| = sqrt(vehicle.vel1.x^2 + vehicle.vel1.y^2 + vehicle.vel1.z^2)
|v4| = sqrt(vehicle.vel2.x^2 + vehicle.vel2.y^2 + vehicle.vel2.z^2)
```
Each sqrt has a guard: `if (val < 0.0) call safe_sqrt else SQRT()`.

**4. Substep count** (lines 121-132):
```c
total_speed = |v1| + |v2| + |v3| + |v4|;
raw_count = (uint)(total_speed * scaled_dt / body_step_size);
num_substeps = raw_count + 1;  // always at least 1

if (num_substeps >= 1001) {
    // Cap at 1000
    num_substeps = 1000;
    sub_dt = dt / 1000.0f;  // DAT_141d1fa9c
} else if (num_substeps > 1) {
    sub_dt = dt / (float)num_substeps;
}
```

**5. The sub-step loop** (lines 137-167):
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

#### Why 1000 Instead of TMNF's 10,000?

TMNF allowed 10,000 substeps. TM2020 caps at 1,000. Possible reasons:
- TM2020 has 4 vehicle types (4x the tuning work, testing)
- TM2020's solver is more robust (iterative constraint solver vs analytical friction)
- 1000 substeps at 100Hz = 100,000 substeps/second, which is already very high
- Exceeding 1000 causes `sub_dt = dt / 1000.0f`, which may produce simulation artifacts but prevents CPU starvation

#### What Happens If You Exceed the Cap?

When `num_substeps >= 1001` (line 126-132), the game:
1. Clamps to 1000 substeps
2. Each substep uses `dt / 1000.0f` seconds
3. The total simulated time is `1000 * (dt/1000) = dt` -- still exact
4. But the step size may be too large for the actual velocity, potentially causing tunneling through thin geometry or unstable oscillation

---

### Q6: "What makes each car type feel different?"

#### Force Model Dispatch

From `NSceneVehiclePhy__ComputeForces.c:142-162`, each car type uses a different force model function:

| Car Type | Force Model | Function | Extra Time Param? |
|:---:|:---:|:---:|:---:|
| **CarSport (Stadium)** | 5 | `FUN_140851f00` | YES |
| **CarRally** | 6 (likely) | `FUN_14085c9e0` | YES |
| **CarSnow** | 6 or 0xB | `FUN_14085c9e0` or `FUN_14086d3b0` | YES |
| **CarDesert** | 0xB (likely) | `FUN_14086d3b0` | YES |
| Legacy/inactive | 0, 1, 2 | `FUN_140869cd0` | NO |

#### What Changes Between Cars

The force model selector at `vehicle_model+0x1790` determines WHICH function computes tire forces. Additionally:

1. **Force accumulator location**: Models 0-5 read from `vehicle+0x144C`, models 6+ read from `vehicle+0x1534` (`ComputeForces.c:128-137`). This means the new cars have a reorganized internal force layout.

2. **Max speed**: Read from `model+0x2F0` per vehicle type. Different cars have different speed caps.

3. **Tuning data**: At `model+0x30D8` and `model+0x31A8`, large blocks of tuning data are passed to the force model. These contain all the car-specific parameters (spring rates, friction curves, gear ratios, etc.) loaded from the vehicle's GBX tuning file.

4. **Wheel state blocks**: The 4 wheel blocks at stride `0xB8` starting at `+0x1790` have their own per-car state that gets reset on checkpoint (lines 173-199 of ComputeForces).

#### What We Cannot Answer

The actual force model functions (`FUN_140851f00`, `FUN_14085c9e0`, `FUN_14086d3b0`) are **not decompiled** in our 18-file set. Each is likely 4,000-10,000+ bytes of code containing:
- Per-wheel lateral and longitudinal tire force computation
- Burnout/slip state machine
- Engine/gear simulation
- Suspension force integration
- Steering response curves

[NEEDS INVESTIGATION: Decompile FUN_140851f00 (CarSport), FUN_14085c9e0 (model 6), FUN_14086d3b0 (model 0xB) to see the actual differences]

---

### Q7: "How does the gearbox/engine simulation work?"

#### What the Openplanet Data Tells Us

From `19-openplanet-intelligence.md`:

| Field | Range | Description |
|:---:|:---:|:---|
| `CurGear` | 0-7 | Current gear (8 gears total) |
| `RPM` | 0-11000 | Engine RPM |
| `EngineOn` | bool | Whether engine is running |

#### What the Decompiled Code Shows

The decompiled ComputeForces dispatcher does NOT contain engine/gearbox logic. This is entirely inside the force model functions (FUN_140851f00 etc.).

From TMNF cross-reference (the M6/Steer06 model was fully decompiled for TMNF):

**TMNF's engine model** (which TM2020 likely preserves in concept):
- 6 gear ratios stored in the tuning GBX
- RPM computed from wheel rotation speed and current gear ratio
- Gear shifts triggered by RPM thresholds
- Engine torque curve (via `CFuncKeysReal` piecewise linear curves)
- Accelerator pedal maps to engine torque, which maps to wheel drive force

**TM2020 expansion**:
- 8 gears (vs TMNF's 6) based on `CurGear` range 0-7
- RPM range up to 11,000 (vs TMNF's typical ~10,000)
- `EngineOn` flag suggests the engine can be explicitly disabled (FreeWheeling surface effect)

#### Is RPM Simulated or Cosmetic?

Based on the TMNF analysis: RPM IS simulated (not cosmetic). In TMNF's M6 model, RPM determines:
- When to shift gears
- Engine torque output (via the torque curve)
- The burnout state machine entry condition

TM2020 almost certainly preserves this -- the RPM field is exposed at a custom memory offset in the VisState, suggesting it is computed by the physics engine and copied to the visual state via `ExtractVisStates` (FUN_1407d29a0).

[NEEDS INVESTIGATION: Decompile force model functions to confirm gear ratio storage and shift logic]

---

### Q8: "What happens when the car goes into water?"

#### The Water Physics Code Path

From `NSceneDyna__ComputeWaterForces.c`:

```
NSceneDyna::ComputeWaterForces (FUN_1407f8290)
    |
    +-> Check if water volume exists (param_8 != 0)
    |
    +-> For each dynamic body:
    |     |
    |     +-> Get collision item reference (body_pair + 0x60)
    |     +-> Check for per-body water zone (item + 0x128)
    |     |     If null: use global water (*param_2 + 0x48)
    |     |     If set: use custom water zone
    |     +-> Call FUN_1407fb580(body_shape, water_shape, water_params)
    |
    v
FUN_1407fb580 (not decompiled -- the actual buoyancy/drag computation)
```

#### What We Know About the Water Model

1. **Two-tier lookup**: Bodies can be in a global water volume or a custom per-zone water volume. The custom water is referenced at `collision_item + 0x128 -> +0x38`.

2. **Body shape intersection**: The function takes `lVar1 + 0x18` (the body's collision shape) and `lVar3` (the water shape). This strongly suggests **submerged volume computation** for buoyancy.

3. **The ninth parameter is 0**: `FUN_1407fb580(..., param_8, 0)` -- the trailing `0` may be a mode flag (e.g., 0 = normal water, other values for special water behavior).

4. **WaterImmersionCoef**: From Openplanet data, `WaterImmersionCoef` (0-1) tracks how submerged the car is. This is likely computed by `FUN_1407fb580` and stored in the vis state.

#### Can You Drive Underwater?

From the `FallingState` enum in `19-openplanet-intelligence.md`:
- `FallingWater` (2): Falling through water
- `RestingWater` (6): Resting on water surface

The existence of `RestingWater` and `WaterImmersionCoef` (0-1, not just 0/1) suggests the car can be partially submerged and drive on/through water. The TMNF cross-reference mentions `WaterReboundMinHSpeed = 55.556 m/s` (200 km/h) -- suggesting cars can skip across water at sufficient speed.

[NEEDS INVESTIGATION: Decompile FUN_1407fb580 for the actual buoyancy/drag formulas]

---

### Q9: "How does the game guarantee deterministic physics?"

#### Determinism Mechanisms Found in the Code

**1. Fixed-tick integer timing** (`PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`):
```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = no float error
```
Time is NEVER accumulated as floating-point. The tick counter is an integer, and the conversion to microseconds uses integer multiplication.

**2. Deterministic sub-stepping** (`PhysicsStep_TM.c:121-167`):
The substep count is computed from velocity magnitudes via a deterministic formula. Given the same velocity state, the same number of substeps will be computed. The remainder handling ensures total time = dt exactly.

**3. Ordered iteration** (`PhysicsStep_TM.c:66-67`, `NSceneDyna__PhysicsStep_V2.c:103-116`):
All bodies and vehicles are iterated in array order. No parallel dispatch is visible. This means collision pairs are always processed in the same order.

**4. Safe sqrt** (`PhysicsStep_TM.c:90-116`):
Every square root computation has a `< 0.0` guard that calls `FUN_14195dd00` for negative inputs. This prevents NaN propagation from floating-point rounding.

**5. SSE floating-point** (platform-level):
The x64 build uses SSE instructions (`sqrtss`, etc.) which are IEEE 754 compliant and produce identical results on all x64 CPUs. No x87 FPU (which had 80-bit intermediate precision issues) is used.

**6. Network replay validation**:
From `BeforeMgrDynaUpdate.c:106-108`: when `SimulationMode == 1` (replay), the game copies 2,168 bytes of vehicle state from a replay data pointer:
```c
FUN_1418d7510(lVar19 + 0x1280, *(lVar19 + 0x1c98), 0x878);
```
This is a `memcpy` of the authoritative state, used for validation. If the local simulation diverges from the server's state, the replay data corrects it.

#### What Could Break Determinism

- **Cross-platform**: Different CPUs might have different rounding for denormalized numbers. The code has no visible `_controlfp` or FPU control word manipulation.
- **Compiler differences**: Different optimization levels might reorder floating-point operations. Nadeo likely uses a specific compiler with specific flags.
- **Uninitialized memory**: Some fields are not explicitly initialized to zero in the decompiled code. If they contain stale values, behavior could vary.

---

### Q10: "What are ALL the numeric constants and what do they control?"

See [Section 13: Comprehensive Constants Table](#13-comprehensive-constants-table) below for the complete table extracted from all 18 decompiled files.

---

## 13. Comprehensive Constants Table

### 13.1 Global Data Constants (from .rdata / .data sections)

| Address | Name | Type | Likely Value | Used In | Purpose |
|:---|:---|:---:|:---:|:---|:---|
| `DAT_141d1fa9c` | MAX_SUBSTEP_FLOAT | float | 1000.0f | PhysicsStep_TM:132 | Divisor when substep count capped at 1000 |
| `DAT_141d1fe58` | MICROSECOND_SCALE | double | 1000000.0 | PhysicsStep_TM:136 | Converts sub_dt (seconds) to microseconds |
| `DAT_141d1ed34` | MIN_SPEED_THRESHOLD | float | [UNKNOWN] | ComputeForces:114 | Minimum maxSpeed value for clamping to apply |
| `DAT_141d1ee10` | STEP_PARAM | float | [UNKNOWN] | PhysicsStep_TM:118,187 | Parameter passed to step functions |
| `DAT_141d1ef7c` | FRAGILE_SEVERITY | float | [UNKNOWN] | PhysicsStep_TM:192 | Collision severity threshold for fragile break |
| `DAT_141d1fa18` | SURFACE_HEIGHT_SCALE | float | [UNKNOWN] | BeforeMgrDynaUpdate:77 | Scale factor for surface height parameter |
| `DAT_141d1ecc4` | MIN_NORMAL_LEN_SQ | float | ~0.0001 | MergeContacts:219 | Minimum squared normal length (prevents /0) |
| `DAT_141d1fc24` | MAX_NORMAL_LEN_SQ | float | ~100.0 | MergeContacts:219 | Maximum squared normal length (sanity) |
| `DAT_141d1f3c8` | UNIT_NORMAL_SCALE | float | 1.0f | MergeContacts:226 | Scale factor for normalized normals |
| `DAT_141a64350` | ZERO_VEC_XY | 2xfloat | {0.0, 0.0} | ComputeForces:222, PairComputeForces:63 | Zero vector constant for clearing |
| `DAT_141a64358` | ZERO_VEC_Z | float | 0.0f | ComputeForces:223, Gravity:62-65 | Zero Z component |
| `DAT_141ebccfc` | SLEEP_ENABLED | int | [UNKNOWN] | Gravity:40 | Sleep detection toggle (0=off, non-zero=on) |
| `DAT_141ebcd00` | SLEEP_DAMPING | float | [UNKNOWN, <1.0] | Gravity:45-49,52-56 | Velocity damping factor when below sleep threshold |
| `DAT_141ebcd04` | SLEEP_THRESHOLD | float | [UNKNOWN] | Gravity:27 | Sleep velocity threshold (m/s, squared by code) |
| `DAT_141e64060` | STACK_COOKIE | uint64 | [random] | Multiple | Security check cookie for stack protection |
| `DAT_141fabc20` | COLLISION_LAYER_TABLE | uint[256] | [256 entries] | DynCollisionCache:42 | Maps collision type byte to layer mask |

### 13.2 Hardcoded Integer Constants

| Value | Hex | Context | Meaning |
|:---:|:---:|:---|:---|
| 1000000 | 0xF4240 | PhysicsStep_TM:63, ProcessContactPoints:31 | Tick to microsecond multiplier |
| 1001 | 0x3E9 | PhysicsStep_TM:126 | Max substep count + 1 (comparison threshold) |
| 999 | 0x3E7 | PhysicsStep_TM:131 | Actual max substep count |
| 88 | 0x58 | ProcessContactPoints:22,30 | Contact point struct stride |
| 56 | 0x38 | PhysicsStep_V2:227,231, ComputeExternalForces:26 | Body data struct stride |
| 224 | 0xE0 | PhysicsStep_V2:220 | 4x body stride (loop unrolling) |
| 184 | 0xB8 | ComputeForces reset blocks | Per-wheel state block stride |
| 44 | 0x2C | FrictionIterCount_Config:21 | SSolverParams struct size |
| 144 | 0x90 | Tunings registration:21 | NGameSlotPhy::SMgr struct size |
| 2168 | 0x878 | BeforeMgrDynaUpdate:107 | Replay state copy size |
| 20 | 0x14 | BeforeMgrDynaUpdate (circular buffer) | Wheel contact history buffer size |
| 13 | 0x0D | DynCollisionCache:77 | Compound collision shape type ID |
| 0xFFFFFFFF | -1 | Multiple (boost start, hit body, body id) | Sentinel: "no value" / "uninitialized" |

### 13.3 Bitfield Constants

| Value | Bits | Context | Meaning |
|:---:|:---|:---|:---|
| 0x0F | bits 0-3 | StatusFlags nibble extraction | Low nibble mask for vehicle state |
| 0x01 | bit 0 | PhyFlags (+0x1BC0) | [UNKNOWN] physics flag |
| 0x02 | bit 1 | Body flags, contact flags | Kinematic/static body flag |
| 0x04 | bit 2 | ContactPhyFlags (+0x1C7C) | DisableEvents flag |
| 0x08 | bit 3 | ContactPhyFlags (+0x1C7C) | HasContactThisTick |
| 0x10 | bit 4 | ContactPhyFlags (+0x1C7C) | SubStepCollisionDetected |
| 0x20 | bit 5 | Body flags (DynCollisionCache) | Kinematic flag for cache |
| 0xE0 | bits 5-7 | ContactPhyFlags (+0x1C7C) | ContactType field |
| 0x0600 | bits 9-10 | ContactPhyFlags (+0x1C7C) | Cleared each tick in PhysicsStep_TM |
| 0x0800 | bit 11 | ContactPhyFlags (+0x1C7C) | Part of fragile check (with bit 12) |
| 0x1000 | bit 12 | ContactPhyFlags (+0x1C7C) | Part of fragile check (with bit 11) |
| 0x1800 | bits 11-12 | PhysicsStep_TM:191 | Both bits must be set for fragile break |
| 0x10000 | bit 16 | ContactPhyFlags (+0x1C7C) | SubStepCollisionResult |
| 0x400 | bit 10 | Players_BeginFrame:24 | Arena state flag check |
| 0xFFFFF5FF | ~(0x0600) | PhysicsStep_TM:69 | Clears bits 9-10 |
| 0xFFFFE1F | ~(0x1E0) | BeforeMgrDynaUpdate:151 | Clears bits 5-8 |
| 0xFFFFFFFD | ~(0x02) | MergeContacts:236 | Clears "needs merge" flag |

### 13.4 Struct Offset Constants

| Offset | Struct | Field | Type |
|:---:|:---|:---|:---:|
| +0x10 | Vehicle | DynaBodyId | int |
| +0x50 | Vehicle | CollisionObjectAlt | ptr |
| +0x74 | CollisionItem | CurrentPosition | vec3 |
| +0x80 | Vehicle | CollisionObject | ptr |
| +0x88 | Vehicle | PhyModelPtr | ptr |
| +0x90 | Vehicle | CurrentTransform | 112B |
| +0x94 | CollisionItem | PreviousPosition | vec3 |
| +0x9C | Vehicle | SurfaceHeightParam | float |
| +0xA4 | CollisionItem | HitBodyIndex | uint |
| +0xE0 | VehicleModel | ModelScale | float |
| +0x104 | Vehicle | PreviousTransform | 112B |
| +0x128C | Vehicle | StatusFlags | uint |
| +0x1280 | Vehicle | VehicleUniqueId | uint |
| +0x1348 | Vehicle | VelocityVec1 | vec3 |
| +0x1354 | Vehicle | VelocityVec2 | vec3 |
| +0x144C | Vehicle | ForceAccum (models 0-5) | vec3 |
| +0x1534 | Vehicle | ForceAccum (models 6+) | vec3 |
| +0x1594 | Vehicle | WheelContactHistory | circular buf |
| +0x15B0 | Vehicle | ContactStateChangeCount | int |
| +0x16E0 | Vehicle | BoostDuration | uint |
| +0x16E4 | Vehicle | BoostStrength | float |
| +0x16E8 | Vehicle | BoostStartTime | uint |
| +0x1790 | PhyModel | ForceModelType | int |
| +0x1BB0 | Vehicle | VehicleModelClassPtr | ptr |
| +0x1C7C | Vehicle | ContactPhyFlags | uint |
| +0x1C90 | Vehicle | SimulationMode | int |
| +0x2F0 | PhyModel | MaxSpeed | float |
| +0x30D8 | PhyModel | TuningDataBlock1 | varies |
| +0x31A8 | PhyModel | TuningDataBlock2 | varies |

### 13.5 Named Parameter Registration (from Decompiled Config Functions)

#### SSolverParams (NSceneDyna::SSolverParams, 0x2C bytes)

| Offset | Name | Type | Notes |
|:---:|:---|:---:|:---|
| 0x00 | FrictionStaticIterCount | int | Registered via `FUN_1401dc2a0` (int type) |
| 0x04 | FrictionDynaIterCount | int | Registered via `FUN_1401dc2a0` |
| 0x08 | VelocityIterCount | int | Registered via `FUN_1401dc2a0` |
| 0x0C | PositionIterCount | int | Registered via `FUN_1401dc2a0` |
| 0x10 | DepenImpulseFactor | float | Registered via `FUN_14016e290` (float type) |
| 0x14 | MaxDepenVel | float | Registered via `FUN_14016e290` |
| 0x18 | EnablePositionConstraint | bool | Registered via `FUN_1401dc110` (bool type) |
| 0x1C | AllowedPen | float | "auto AllowedPen if negative" |
| 0x20 | VelBiasMode | int | Registered via `FUN_1401dc2a0` |
| 0x24 | UseConstraints2 | bool | Registered via `FUN_1401dc110` |
| 0x28 | MinVelocityForRestitution | float | Registered via `FUN_14016e290` |

#### NGameSlotPhy::SMgr (0x90 bytes)

| Offset | Name | Type | Notes |
|:---:|:---|:---:|:---|
| 0x58 | Tunings.CoefFriction | float | Registered via `FUN_14016e290` |
| 0x5C | Tunings.CoefAcceleration | float | Registered via `FUN_14016e290` |
| 0x60 | Tunings.Sensibility | float | Registered via `FUN_14016e290` |

---

## Appendix A: Function Reference

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

## Appendix B: Force Model Function Addresses

| Model | Switch Value | Address | Param Count | Estimated Size |
|:---:|:---:|:---:|:---:|:---|
| Base | 0, 1, 2 | `FUN_140869cd0` | 2 | [UNKNOWN] |
| M4 | 3 | `FUN_14086b060` | 2 | [UNKNOWN] |
| M5 | 4 | `FUN_14086bc50` | 2 | [UNKNOWN] |
| M6 (StadiumCar) | 5 | `FUN_140851f00` | 3 | [UNKNOWN -- likely large, >4KB based on TMNF's M6 at 10660 bytes] |
| New Model A | 6 | `FUN_14085c9e0` | 3 | [UNKNOWN] |
| New Model B | 0xB | `FUN_14086d3b0` | 3 | [UNKNOWN] |

## Appendix C: Key Struct Sizes

| Struct | Size | Evidence |
|:---|:---:|:---|
| Per-vehicle state | ~0x1CA0 (7328 bytes) | Highest offset +0x1C98 + ptr size |
| Per-body dynamics | 0x38 (56 bytes) | Force clearing loop stride |
| Contact point | 0x58 (88 bytes) | Contact processing loop stride |
| Collision cache entry | 0x38 (56 bytes) | DynamicCollisionCreateCache stride |
| SSolverParams | 0x2C (44 bytes) | FUN_1402ea9e0 size parameter |
| NGameSlotPhy::SMgr | 0x90 (144 bytes) | FUN_1402ea9e0 size parameter |
| Per-wheel state block | 0xB8 (184 bytes) | ComputeForces reset stride |
| Wheel contact history | 28 bytes (8 header + 20 data) | BeforeMgrDynaUpdate circular buffer |
| Vehicle model (partial) | >0x31A8 | Highest offset accessed via vehicle+0x88 |
| Transform copy | 112 bytes | 28 x 4-byte values from +0x90 to +0x174 |

## Appendix D: Needs Investigation Summary

These questions could not be fully answered from the 18 decompiled dispatcher-level files:

| Question | What's Missing | How to Resolve |
|:---|:---|:---|
| Exact turbo duration/strength values | Stored in GBX tuning, not .exe | Extract from StadiumCar VehiclePhyTuning.Gbx |
| Per-wheel tire force formulas | Inside force model functions | Decompile FUN_140851f00 (CarSport, ~10KB) |
| Friction coefficients per material | Inside force model + tuning data | Decompile force models + extract GBX |
| Gear ratio values | Inside force model or tuning GBX | Same as above |
| Water buoyancy/drag formulas | Inside FUN_1407fb580 | Decompile FUN_1407fb580 |
| Exact sleep threshold values | Global vars with unknown values | Read memory at runtime or find in .rdata |
| Coefficient of restitution per surface | Per-material property in tuning | Extract from material physics data |
| How Rally/Snow/Desert differ | Force model 6 and 0xB not decompiled | Decompile FUN_14085c9e0 and FUN_14086d3b0 |
| Reactor boost force direction | Not in dispatcher code | Decompile oriented reactor boost handler |
| Cruise control implementation | Not in dispatcher code | Trace from "Cruise" gameplay effect to force model |

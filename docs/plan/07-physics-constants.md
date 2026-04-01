# TM2020 Physics Constants -- Extracted from Binary

TM2020 uses NO hardcoded gravity constant (9.81, 29.43, etc.) in the binary. The gravity vector loads entirely from GBX files (DefaultGravitySpawn in CPlugSpawnModel at +0x54). All friction curves, engine curves, and surface parameters likewise load from GBX at runtime. The binary contains only the code framework and a handful of mathematical/utility constants.

---

## Hardcoded Mathematical Constants (`.rdata`)

| Constant | Value | Address | Context | Confidence |
|----------|-------|---------|---------|------------|
| Float 1.0 | 1.0 | `0x141d1f3c8` | Unity value, used everywhere as DAT_141d1f3c8 | Confirmed |
| Float -1.0 | -1.0 | `0x141d1fd80` | Negative direction flip | Confirmed |
| Float 0.5 | 0.5 | `0x141d1f1ac` | Half multiplier (e.g. half-force in friction) | Confirmed |
| Float 3.0 | 3.0 | `0x141d1f6e0` | Smoothstep coefficient: `3t^2 - 2t^3` | Confirmed |
| Float 3.6 | 3.6 | `0x141d1f71c` | m/s to km/h conversion factor | Confirmed |
| Float 2.0 | 2.0 | `0x141d1f624` | Speed threshold for brake/reverse detection (m/s) | Confirmed |
| Float 0.1 | 0.1 | `0x141d1ef7c` | Velocity threshold for sliding detection | Confirmed |
| Pi | 3.14159274 | `0x141d1f6f8` | Angle calculations | Confirmed |
| 2*Pi | 6.28318548 | `0x141d1f79c` | Full rotation (wheel spin range) | Confirmed |
| Pi/6 | 0.52359879 | `0x141d1f1c8` | +30 degrees (max steer angle display range) | Confirmed |
| -Pi/6 | -0.52359879 | `0x141d1fcfc` | -30 degrees (min steer angle display range) | Confirmed |
| Epsilon | 1.0e-5 | `0x141d1ed34` | Curve lookup tolerance | Confirmed |
| Tiny Epsilon | 1.0e-10 | `0x141d1ecc4` | Near-zero velocity threshold | Confirmed |
| Float Max | 3.4028235e+38 | `0x141d1fc24` | Max float sentinel | Confirmed |
| 1000.0 | 1000.0 | `0x141d1fa9c` | Timestep conversion (ms to internal units) | Confirmed |
| 15.0 | 15.0 | `0x141d1f81c` | Max ground detection distance | Confirmed |

### Bit Manipulation Masks

| Constant | Value | Address | Context | Confidence |
|----------|-------|---------|---------|------------|
| Sign flip | 0x80000000 | `0x141d21c30` | XOR to negate float | Confirmed |
| Abs mask | 0x7FFFFFFF | `0x141d21c00` | AND to get absolute value | Confirmed |

### Vector Constants

| Constant | Value | Address | Context | Confidence |
|----------|-------|---------|---------|------------|
| Unit Vec4 | (1.0, 1.0, 1.0, 1.0) | `0x141d21110` | Default identity multiplier | Confirmed |
| Down Vec4 | (0.0, 0.0, 0.0, -1.0) | `0x141d21d30` | Gravity direction setup | Confirmed |

---

## Dynamics Sleep/Damping Constants

| Constant | Value | Address | Context | Confidence |
|----------|-------|---------|---------|------------|
| Sleep damping | 0.9 | `0x141ebcd00` | Velocity damping when near-sleep | Confirmed |
| Sleep threshold | 0.01 | `0x141ebcd04` | Velocity below this = candidate for sleep | Confirmed |
| Sleep enable flag | 1 | `0x141ebccfc` | Sleep system enabled | Confirmed |
| Max iterations | 1000 | `0x141ebccf8` | Pre-sleep iteration count | Confirmed |

---

## Tuning Parameters (Runtime Coefficients)

These are multiplier fields in the vehicle state, not hardcoded constants. Default value is 1.0 for all.

### NGameSlotPhy::SMgr Tuning (FUN_141071b20)

| Parameter | Offset | Default | String | Confidence |
|-----------|--------|---------|--------|------------|
| CoefFriction | +0x58 | 1.0 | `"Tunings.CoefFriction"` at `0x141cb72c8` | Confirmed |
| CoefAcceleration | +0x5C | 1.0 | `"Tunings.CoefAcceleration"` at `0x141cb72a8` | Confirmed |
| Sensibility | +0x60 | 1.0 | `"Tunings.Sensibility"` at `0x141cb7290` | Confirmed |

### CPlugVehiclePhyModelCustom Modifiers (FUN_14061abb0)

| Parameter | Offset | Default | String | Confidence |
|-----------|--------|---------|--------|------------|
| AccelCoef | +0x18 | 1.0 (0x3f800000) | `"Modifiers.AccelCoef"` at `0x141bd5b68` | Confirmed |
| ControlCoef | +0x1C | 1.0 (0x3f800000) | `"Modifiers.ControlCoef"` at `0x141bd5b10` | Confirmed |
| GravityCoef | +0x20 | 1.0 (0x3f800000) | `"Modifiers.GravityCoef"` at `0x141bd5af8` | Confirmed |

### CGameVehiclePhy State Fields

| Parameter | Offset | Default | String | Confidence |
|-----------|--------|---------|--------|------------|
| AccelCoef | varies | 1.0 (0x3f800000) | `"AccelCoef"` at `0x141bd35b8` | Confirmed |
| ControlCoef | varies | 1.0 (0x3f800000) | `"ControlCoef"` at `0x141bd35a8` | Confirmed |
| GravityCoef | varies | 1.0 (0x3f800000) | `"GravityCoef"` at `0x141bb3e18` | Confirmed |
| AdherenceCoef | varies | 1.0 (0x3f800000) | `"AdherenceCoef"` at `0x141bd35d8` | Confirmed |

---

## Vehicle Physics Model Offsets (from GBX data at `car_state+0x88`)

All values are data-driven (not hardcoded). Offsets are within the physics model struct loaded from GBX.

### Speed and Acceleration Curves

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| MaxSpeed | +0x2F0 | Speed cap (m/s) - checked in ComputeForces | Confirmed |
| Engine accel force curve | +0xAB8 | FUN_14042bf60 curve lookup | Confirmed |
| Engine brake force | +0xAB0 | Forward brake threshold | Confirmed |
| Engine reverse force | +0xAB4 | Reverse brake threshold | Confirmed |
| Engine force value | +0x308 | Absolute force value for engine | Confirmed |
| Engine RPM force curve | +0x9A8 | RPM-dependent force multiplier curve | Confirmed |
| Engine RPM force curve 2 | +0x9F8 | RPM-dependent grip limiting curve | Confirmed |

### Friction and Grip

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| Grip multiplier (forward) | +0x18D0 | Main tire grip force value | Confirmed |
| Lateral grip curve | +0x1AC0 | Slip angle to lateral force curve | Confirmed |
| Lateral force linear coef | +0x1A5C | Linear grip coefficient | Confirmed |
| Lateral force quadratic coef | +0x1A60 | Quadratic grip coefficient | Confirmed |
| Lateral grip override (braking) | +0x1B10 | Grip value used when braking | Confirmed |
| Grip curve (speed-dependent) | +0x18D8 | Friction vs speed curve | Confirmed |
| Surface friction multiplier | surface_ptr+0x24 | Per-material friction coefficient | Confirmed |
| Friction smooth blend factor | +0x192C | Blend between static/dynamic friction | Confirmed |

### Tire Icing/Grip State Machine

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| Speed threshold for grip | +0xCD8 | Speed above which grip drops | Confirmed |
| Grip recovery rate | +0xCDC | Ticks to recover grip | Confirmed |
| Grip decay grounded | +0xCE0 | Ticks to lose grip (grounded, contact) | Confirmed |
| Grip decay rate 2 | +0xCE4 | Ticks to lose grip (grounded, no contact) | Confirmed |
| Grip decay airborne | +0xCE8 | Ticks to lose grip (airborne) | Confirmed |
| Friction reduction curve | +0xD40 | Curve for friction reduction factor | Confirmed |
| Friction blend threshold | +0xCD4 | Threshold for friction blending | Confirmed |

### Steering and Control

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| Steer reduction start speed | +0x19E4 | Speed at which steering begins to reduce | Confirmed |
| Steer reduction end speed | +0x19E8 | Speed at which steering is fully reduced | Confirmed |
| Accel reduction start speed | +0x19EC | Speed at which accel begins to reduce | Confirmed |
| Accel reduction end speed | +0x19F0 | Speed at which accel is fully reduced | Confirmed |
| Slide friction blend | +0x19F4 | Blend factor for slide vs normal friction | Confirmed |

### Turbo System

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| Turbo start duration | +0x16E0 | Duration of turbo effect (ticks) | Confirmed |
| Turbo force value | +0x16E4 | Turbo force multiplier | Confirmed |
| Turbo model coef | +0xE0 (in VehiclePhyModelCustom) | Scales turbo force | Confirmed |

### Braking

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| Max brake force grounded | +0x17A4 | Normal brake force cap | Confirmed |
| Max brake force sliding | +0x17A0 | Brake force cap when sliding | Confirmed |
| Brake linear coef | +0x1798 | Brake force = coef + speed * slope | Confirmed |
| Brake speed slope | +0x179C | Brake force speed multiplier | Confirmed |

### Air Control and Reactor

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| ReactorBoostLvl | vis+0x174 | Current reactor boost level (0/1/2) | Confirmed |
| ReactorBoostType | vis+0x178 | Boost type enum | Confirmed |
| ReactorAirControl | vis+0x180 | Air control vector for reactor | Confirmed |

### Suspension

| Field | Model Offset | Context | Confidence |
|-------|-------------|---------|------------|
| Engine torque Y-moment | +0x19D0 | Torque applied around Y axis from engine | Confirmed |

---

## Spring/Damper Constraint Model (NPlugDyna::SConstraintModel)

Loaded from GBX, size 0x74 bytes.

| Field | Offset | Context | Confidence |
|-------|--------|---------|------------|
| Spring.Length | +0x04 | Natural spring length | Confirmed |
| Spring.DampingRatio | +0x08 | Damping ratio (0=undamped, 1=critical) | Confirmed |
| Spring.FreqHz | +0x0C | Spring frequency in Hz | Confirmed |

---

## Solver Parameters (NSceneDyna::SSolverParams)

Size 0x2C bytes. All loaded from GBX.

| Field | Offset | Type | Confidence |
|-------|--------|------|------------|
| FrictionStaticIterCount | +0x00 | uint32 | Confirmed |
| FrictionDynaIterCount | +0x04 | uint32 | Confirmed |
| VelocityIterCount | +0x08 | uint32 | Confirmed |
| PositionIterCount | +0x0C | uint32 | Confirmed |
| DepenImpulseFactor | +0x10 | float | Confirmed |
| MaxDepenVel | +0x14 | float | Confirmed |
| EnablePositionConstraint | +0x18 | bool | Confirmed |
| AllowedPen | +0x1C | float | Confirmed |
| VelBiasMode | +0x20 | uint32 | Confirmed |
| UseConstraints2 | +0x24 | bool | Confirmed |
| MinVelocityForRestitution | +0x28 | float | Confirmed |

---

## CSceneVehicleVisState Layout (size 0x360)

The per-frame visual/physics output state.

| Field | Offset | Type | Confidence |
|-------|--------|------|------------|
| InputSteer | +0x10 | float [-1,1] | Confirmed |
| InputGasPedal | +0x14 | float [0,1] | Confirmed |
| InputBrakePedal | +0x18 | float [0,1] | Confirmed |
| InputVertical | +0x1C | float [-1,1] | Confirmed |
| InputIsBraking | +0x20 | bool | Confirmed |
| Loc.translation (Position) | +0x50 | Vec3 | Confirmed |
| WorldVel | +0x5C | Vec3 | Confirmed |
| FrontSpeed | +0x74 | float (m/s) | Confirmed |
| Wheels[0].DamperLength | +0xA8 | float | Confirmed |
| Wheels[0].Rot | +0xAC | float [0, 2pi] | Confirmed |
| Wheels[0].RotSpeed | +0xB0 | float | Confirmed |
| Wheels[0].SteerAngle | +0xB4 | float [-pi/6, pi/6] | Confirmed |
| Wheels[0].SlipCoef | +0xBC | float [0,1] | Confirmed |
| Wheels[0].Icing01 | +0xC4 | float [0,1] | Confirmed |
| Wheels[0].TireWear01 | +0xC8 | float [0,1] | Confirmed |
| Wheels[0].BreakNormedCoef | +0xCC | float [0,1] | Confirmed |
| Wheels[1].* | +0xD4-0xF8 | same layout, +0x2C stride | Confirmed |
| Wheels[2].* | +0x100-0x124 | same layout, +0x2C stride | Confirmed |
| Wheels[3].* | +0x12C-0x150 | same layout, +0x2C stride | Confirmed |
| ReactorBoostLvl | +0x174 | enum | Confirmed |
| ReactorBoostType | +0x178 | enum | Confirmed |
| ReactorAirControl | +0x180 | Vec3? | Confirmed |
| WorldCarUp | +0x18C | Vec3 | Confirmed |
| CurGear | +0x1A4 | uint32 | Confirmed |
| TurboTime | +0x1AC | float | Confirmed |
| RaceStartTime | +0x1B4 | uint32 | Confirmed |
| CamGrpStates | +0x1DC | array | Confirmed |
| GroundDist | +0x218 | float [-1, 15] | Confirmed |
| SimulationTimeCoef | +0x230 | float | Confirmed |
| BulletTimeNormed | +0x234 | float [0,1] | Confirmed |
| AirBrakeNormed | +0x238 | float [0,1] | Confirmed |
| SpoilerOpenNormed | +0x23C | float [0,1] | Confirmed |
| WingsOpenNormed | +0x240 | float [0,1] | Confirmed |
| WaterImmersionCoef | +0x314 | float | Confirmed |
| WaterOverDistNormed | +0x318 | float | Confirmed |
| WaterOverSurfacePos | +0x31C | Vec3 | Confirmed |
| WetnessValue01 | +0x328 | float | Confirmed |
| DiscontinuityCount | +0x0A | uint16 | Confirmed |

---

## Surface Gameplay IDs (EPlugSurfaceGameplayId)

Enum table at `0x141eb2f60`, 25 values. These IDs map to surface physics via `car_state+0x6B8` pointer table.

| Name | Hex Address |
|------|-------------|
| None | `0x141b58e78` |
| NoSteering | `0x141be1238` |
| NoGrip | `0x141be1244` |
| Reset | `0x141be124c` |
| ForceAcceleration | `0x141be1258` |
| Turbo | `0x141be126c` |
| FreeWheeling | `0x141be1278` |
| Turbo2 | `0x141be1288` |
| ReactorBoost2_Legacy | `0x141be1290` |
| Fragile | `0x141be12a8` |
| NoBrakes | `0x141be12b0` |
| Bouncy | `0x141be12bc` |
| Bumper | `0x141be12c4` |
| SlowMotion | `0x141be12d0` |
| ReactorBoost_Legacy | `0x141be12e0` |
| Bumper2 | `0x141be12f8` |
| VehicleTransform_CarRally | `0x141be1300` |
| VehicleTransform_CarSnow | `0x141be1320` |
| ReactorBoost_Oriented | `0x141be1378` |
| ReactorBoost2_Oriented | `0x141be13b0` |

---

## Physics Model Type Switch

In `NSceneVehiclePhy::ComputeForces` (FUN_1408427d0), the physics model type at `model+0x1790` selects the force computation:

| Type | Function | Description |
|------|----------|-------------|
| 0, 1, 2 | FUN_140869cd0 | Standard car physics (4-wheel) |
| 3 | FUN_14086b060 | 2-wheel vehicle model |
| 4 | FUN_14086bc50 | Special vehicle type 4 |
| 5 | FUN_140851f00 | CarSport model |
| 6 | FUN_14085c9e0 | CarSport extended model |
| 0xB (11) | FUN_14086d3b0 | Additional model type |

---

## Tire Force Model (FUN_14086af20 -- Lateral Grip)

The tire force model uses a slip-angle based friction curve, not a direct Pacejka formula:

```
slip_dot = dot(velocity, contact_normal)
force_linear = abs(slip_dot) * model[+0x1A5C] - slip_dot^2 * model[+0x1A60]

slip_angle_scaled = abs(slip_dot) * 3.6  // m/s to km/h
grip_from_curve = curve_sample(model+0x1AC0, slip_angle_scaled)

max_force = grip_from_curve * param_5 * param_4[+0xC] * friction_coef
```

Where:
- `3.6` at `0x141d1f71c` converts m/s to km/h for curve lookup
- If `force_linear > max_force`: clamp to `sign * max_force` (grip saturated)
- If `force_linear <= max_force`: use full linear force (within grip)
- `friction_coef` is 1.0 normally, or `model[+0x1B10]` when braking

---

## Gravity System

No hardcoded gravity constant exists in the binary. The gravity:

1. Loads as a Vec3 from `CPlugSpawnModel.DefaultGravitySpawn` (+0x54)
2. Stores in the scene dynamics manager at offset `*param_1 + 0xA10` (3 floats)
3. Passes to `NSceneDyna::ComputeGravityAndSleepStateAndNewVels` as `param_8`
4. Can be modified at runtime via `GravityCoef` multiplier (default 1.0)

The gravity vector is multiplied by mass * inverse_mass_scale before application.

### Sleep State
When velocity < `0.01` m/s, the damping factor `0.9` applies to velocities each tick, gradually bringing the body to rest.

---

## Key Function Addresses

| Function | Address | Role |
|----------|---------|------|
| NSceneVehiclePhy::ComputeForces | `0x1408427d0` | Main force computation entry |
| Standard car physics (case 0/1/2) | `0x140869cd0` | 4-wheel car model |
| Lateral grip (tire model) | `0x14086af20` | Slip-angle to lateral force |
| Curve interpolation | `0x14042bcb0` | Parameterized curve sampling |
| Steering reduction | `0x1408456b0` | Speed-dependent steer limiting |
| Tire grip state machine | `0x140842310` | Icing/grip recovery per wheel |
| Turbo timer update | `0x1408426e0` | Per-wheel turbo state |
| ComputeGravity | `0x1407f89d0` | Gravity + sleep state |
| MgrDyna_Integrate | `0x1408025a0` | Physics integration step |
| PhysicsStep_V2 | `0x140803920` | Outer physics step |
| Tunings registration | `0x141071b20` | CoefFriction/CoefAcceleration/Sensibility |
| VehiclePhyModelCustom reg | `0x14061abb0` | Modifiers.AccelCoef/ControlCoef/GravityCoef |
| CSceneVehicleVisState reg | `0x140726440` | Visual state struct layout |
| SSolverParams reg | `0x1407f3fc0` | Solver iteration counts |
| SSleepingParams reg | `0x1407f4430` | Sleep velocity thresholds |
| SConstraintModel reg | `0x1404a6d20` | Spring length/damping/frequency |

---

## Related Pages

- [Physics Engine](02-physics-engine.md) -- Force model implementation using these constants
- [Tuning Data Extraction](09-tuning-data-extraction.md) -- How to extract the GBX files containing tuning values
- [Tuning Loading Analysis](10-tuning-loading-analysis.md) -- How values flow from GBX to runtime
- [Determinism Analysis](06-determinism-analysis.md) -- Float determinism for these constants

<details><summary>Document metadata</summary>

- **Date**: 2026-03-27
- **Source**: Extracted from `Trackmania.exe` via Ghidra decompilation

</details>

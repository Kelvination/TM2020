# TM2020 Tuning Data Extraction Plan

**Date**: 2026-03-27
**Status**: CRITICAL PATH -- Physics engine cannot function without tuning constants
**Predecessor**: `07-physics-constants.md` (confirmed all tuning is data-driven)

---

## Executive Summary

TM2020's physics constants (gravity, friction curves, engine curves, suspension parameters, gear ratios) are NOT hardcoded in `Trackmania.exe`. They are loaded at runtime from GBX resource files embedded within encrypted `.pak` archives. This document identifies exactly where these files live, how to extract them, what parameters they contain, and fallback strategies.

**The key class chain is:**

```
CGameItemModel (StadiumCar.ObjectInfo.Gbx)
  -> CPlugVehiclePhyModelCustom (VehiclePhyModelCustom.Gbx)
    -> CPlugVehicleCarPhyTuning (the 106-chunk tuning blob, class ID 0x090ED)
      -> CPlugVehicleGearBox (gear ratios, RPM limits)
      -> CFuncKeysReal[] (speed-dependent curves)
  -> CPlugSpawnModel (Spawn.Gbx -- contains DefaultGravitySpawn)
  -> CPlugDynaObjectModel (DynaObject.Gbx -- collision/dynamics model)
```

---

## 1. Where Tuning Files Live

### 1.1 Primary Location: Inside Pack Files

The tuning data lives inside encrypted `.pak` archives in the game's `Packs/` directory. Based on NadeoImporter string analysis, the vehicle data follows this path hierarchy:

```
Packs/
  Maniaplanet_ModelsSport.pak     (129 MB -- contains CarSport vehicle data)
    Vehicles/Cars/CarSport/       (confirmed via strings)
    Vehicles/Cars/CarDesert/
    Vehicles/Cars/CarRally/
    Vehicles/Cars/CarSnow/
  Stadium.pak                     (1.75 GB -- environment-specific assets)
  Trackmania.Title.Pack.Gbx       (780 MB -- title pack, references vehicle models)
  Maniaplanet.pak                 (177 MB -- core engine resources)
  Maniaplanet_Core.pak            (35 MB -- base engine resources)
```

NadeoImporter.exe references these internal paths:
- `\Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\BayCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\CoastCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\DesertCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\RallyCar.ObjectInfo.Gbx`
- `\Trackmania\Items\Vehicles\SnowCar.ObjectInfo.Gbx`
- (plus Bay, Canyon, Island, Lagoon, Valley from older environments)

And these component GBX files:
- `VehiclePhyModelCustom.Gbx` -- the physics model with tuning data
- `VehicleVisModel.Gbx` -- visual model
- `VehicleStyles.gbx` -- skin/style data
- `VehicleCameraRace2Model.gbx` / `VehicleCameraRace3Model.gbx` -- camera
- `DynaObject.Gbx` -- dynamic object model
- `GameObjectPhyModel.Gbx` -- game object physics

### 1.2 PAK File Encryption

PAK files use **Blowfish cipher in CBC mode** with a 16-byte key:
- Keys are derived from server-provided "sub-keys" stored in profile chunks
- Key derivation: `md5("[sub-key]" + "NadeoPak")`
- Files within PAKs may be zlib-compressed (check `FileDesc.flags & 0x7C`)
- A non-standard CBC modification XORs the IV every 256 bytes

### 1.3 Secondary Locations (Not Confirmed to Contain Tuning)

- **User data**: `/Users/kelvinnewton/Library/Application Support/CrossOver/Bottles/Steam/drive_c/users/crossover/Documents/Trackmania/Items/zzz_ImportedItems/Vehicles/Vehicles/` -- only contains custom items (e.g., `Bus.Item.Gbx`)
- **Openplanet cache**: No extracted GBX files found in the Openplanet directory
- **No standalone tuning files**: Unlike TMNF which had `StadiumCar.VehicleTunings.Gbx` as a discrete file, TM2020 restructured vehicle data into the `VehiclePhyModelCustom.Gbx` container

---

## 2. How to Extract Tuning Data

### 2.1 Method A: Openplanet Fid Loader (RECOMMENDED -- Runtime Extraction)

The **Fid Loader** Openplanet plugin (by AurisTFG) can extract files from the running game by file path. This bypasses PAK encryption entirely because the game has already decrypted the files in memory.

**Steps:**
1. Install Fid Loader from Openplanet: https://openplanet.dev/plugin/fidloader
2. Launch TM2020 with Openplanet
3. Open Openplanet overlay (F3)
4. Use Fid Loader to request these paths:
   - `Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx`
   - `Vehicles\Cars\CarSport\VehiclePhyModelCustom.Gbx`
   - `Vehicles\Cars\CarSport\DynaObject.Gbx`
   - `Vehicles\Cars\CarSport\GameObjectPhyModel.Gbx`
5. Extract to filesystem
6. Parse with GBX.NET (see Method C)

**Alternative**: Use Openplanet's built-in Pack Explorer (System -> Packs) to browse and extract files. Note that many filenames in packs are hashed; the Pack Explorer resolves names using `FileHashes.txt` cache plus community hash lists available at https://openplanet.dev/file/21.

### 2.2 Method B: TMPakTool (Offline Extraction)

TMPakTool is an open-source C# tool that can open and edit `.pak` files.

**Challenges:**
- Requires the correct Blowfish decryption key for TM2020 packs
- TM2020 uses newer PAK format versions that may need key derivation from profile data
- May not support the newest PAK version used by TM2020

**Repository**: Available as open-source with C# library

### 2.3 Method C: GBX.NET Parsing (After Extraction)

Once the GBX files are extracted, use **GBX.NET** (https://github.com/BigBang1112/gbx-net) to parse them.

**GBX.NET support status for relevant classes:**

| Class | Class ID | GBX.NET Support |
|-------|----------|-----------------|
| `CPlugVehiclePhyTunings` | `0x090EC000` | Read/Write up to TM2 |
| `CPlugVehicleCarPhyTuning` | `0x090ED000` (remapped from `0x0A029000`) | Partial |
| `CPlugVehiclePhyModelCustom` | `0x0911E000` | Partial (AccelCoef, ControlCoef, GravityCoef) |
| `CPlugVehicleGearBox` | `0x09094000` | Partial |
| `CPlugVehiclePhyModel` | varies | Partial |
| `CPlugVehicleWheelPhyModel` | `0x0912E000` | Partial (IsDriving, IsSteering, WheelId) |
| `CPlugVehicleCarPhyShape` | varies | Unknown |
| `CGameSpawnModel` | varies | Read/Write |
| `CSceneVehicleCar` | varies | Read/Write (TMUF only) |

**IMPORTANT**: GBX.NET's `VehicleTunings.Gbx` support ends at TM2 (TrackMania 2). TM2020 files may use newer chunk versions that GBX.NET does not fully parse. However, the chunk format is backward-compatible (class ID remapping from `0x0A029` to `0x090ED` is confirmed), so partial parsing should work.

### 2.4 Method D: Openplanet Memory Dump (Runtime Sniffing)

Write a custom Openplanet plugin that reads tuning values directly from game memory at runtime using `Dev::GetOffsetFloat()`. The VehicleState plugin already demonstrates this technique for visual state data.

**Key offsets from binary analysis** (relative to physics model pointer at `car_state+0x88`):

| Parameter | Model Offset | Description |
|-----------|-------------|-------------|
| MaxSpeed | +0x2F0 | Speed cap (m/s) |
| Engine force | +0x308 | Absolute engine force value |
| Engine accel curve | +0xAB8 | CFuncKeysReal curve |
| Grip multiplier | +0x18D0 | Main tire grip force |
| Lateral grip curve | +0x1AC0 | Slip angle to lateral force |
| Brake linear coef | +0x1798 | Brake force coefficient |
| Turbo duration | +0x16E0 | Boost effect duration |
| Turbo force | +0x16E4 | Boost force multiplier |
| Force model type | +0x1790 | ESteerModel enum value |
| Steer reduction start | +0x19E4 | Speed for steer reduction |
| Spring icing threshold | +0xCD8 | Speed threshold for grip loss |

This method extracts exact runtime values but requires the game to be running with a loaded vehicle.

### 2.5 Method E: GBX Explorer Web Tool

The online GBX Explorer at https://explorer.gbx.tools/ can analyze extracted GBX files in the browser. Upload extracted files to view their structure, chunk contents, and field values.

---

## 3. What Parameters Exist

### 3.1 CPlugVehicleCarPhyTuning (106 Chunks, ~150+ Parameters)

This is the core tuning class. From GBX.NET's `.chunkl` definition and TMNF cross-reference, the chunks map to these parameter categories:

#### Core Physics (Chunks 0x000-0x00B)
| Chunk | Parameters |
|-------|-----------|
| 0x000 | SteeringRadius |
| 0x001 | MaxSpeed |
| 0x002 | MaxReverseSpeed |
| 0x003 | Mass |
| 0x004 | GravityCoef |
| 0x005 | InertiaRoll, InertiaYaw |
| 0x006 | TurboBoostForce |
| 0x007 | SteerSpeed |
| 0x008 | ReverseSpeed |
| 0x009 | BrakeBase |
| 0x00A | FluidFriction |
| 0x00B | ShockModel (enum: Demo01/Demo02/Demo03) |

#### Steering & Braking (Chunks 0x007-0x010)
| Chunk | Parameters |
|-------|-----------|
| 0x010 | ESteerModel (enum: Steer01-Steer06) |

#### Friction & Suspension (Chunks 0x011-0x028)
| Chunk | Parameters |
|-------|-----------|
| 0x011-0x014 | TireMaterial references |
| 0x015-0x018 | GroundFriction coefficients |
| 0x019-0x01C | Lateral adherence curves |
| 0x01D-0x020 | Rollover parameters |
| 0x021-0x024 | Suspension spring/damper (Ki, Ka, Rest) |
| 0x025-0x028 | Shock absorber parameters |

#### Suspension (Spring/Damper Model)
| Parameter | TMNF Value | TM2020 Equivalent |
|-----------|-----------|-------------------|
| AbsorbingValKi (spring stiffness) | 40.0 | Spring.FreqHz = sqrt(Ki/mass)/(2*pi) |
| AbsorbingValKa (damping) | 1.0 | Spring.DampingRatio = Ka/(2*sqrt(Ki*mass)) |
| AbsorbingRestValue (rest length) | 0.2 | Spring.Length |
| ShockModel | Demo03 (=2) | [Likely same model] |

#### Audio (Chunks 0x012-0x032)
| Chunk | Parameters |
|-------|-----------|
| 0x012-0x016 | Engine volume, RPM curves |
| 0x017-0x01C | Skid sound thresholds |
| 0x01D-0x022 | Impact thresholds |

#### M6/Steer06 Model (Chunks 0x030-0x05D)
| Chunk | Parameters |
|-------|-----------|
| 0x030-0x038 | Burnout mechanics, slip angles |
| 0x039-0x042 | Air control coefficients |
| 0x043-0x048 | Water physics (gravity, rebound, friction) |
| 0x049-0x056 | Engine RPM curves, gear simulation |
| 0x057-0x05D | Gear ratios, brake modulation, RPM management |

#### Camera & Visual (Chunks 0x05E-0x088)
| Chunk | Parameters |
|-------|-----------|
| 0x05E-0x068 | Air control coefficients |
| 0x069-0x088 | Visual steering angle representation |

### 3.2 CPlugVehiclePhyModelCustom

From GBX.NET source (class ID `0x0911E000`, chunk `0x000`):

```
version   -- format version
AccelCoef -- float, acceleration multiplier (default 1.0)
ControlCoef -- float, control/steering multiplier (default 1.0)
GravityCoef -- float, gravity multiplier (default 1.0)
```

These are the runtime modifier coefficients exposed via ManiaScript `SetPlayer_Delayed_*` functions.

### 3.3 CPlugVehicleGearBox

From GBX.NET source (class ID `0x09094000`, chunk `0x001`):

```
version
float[]   -- gear ratio array
bool      -- [unknown flag]
int       -- [unknown, likely gear count]
int       -- [unknown]
float     -- [unknown, likely idle RPM]
float     -- [unknown, likely max RPM]
float     -- [unknown]
float     -- [unknown]
float     -- [unknown]
float     -- [unknown]
v1+: float? -- [optional field added in v1]
v2+: float? -- [optional field added in v2]
```

### 3.4 CPlugSpawnModel (Gravity Source)

Contains `DefaultGravitySpawn` at offset +0x54 -- this is the Vec3 gravity vector loaded at map start. The base gravity constant (likely 9.81 m/s^2 or similar) is stored here, NOT in the executable.

### 3.5 Speed-Dependent Curves (CFuncKeysReal)

All speed-dependent parameters use piecewise linear curves with keyframes in km/h:

| Curve | TMNF Shape | Purpose |
|-------|-----------|---------|
| AccelCurve | Peak 16 at 0 km/h, drops to 1 at 800 km/h | Engine force vs speed |
| MaxSideFriction | 80 at 0-100 km/h, drops to 55 at 500 km/h | Lateral grip vs speed |
| SteerDriveTorque | Peak 16 at 0, plateaus 3.75 above 500 km/h | Torque vs speed |
| ModulationFromWheelCompression | 10% at 0, 100% at 97.5% compression | Grip vs suspension |
| FrictionReductionCurve | At model+0xD40 | Friction reduction factor |

---

## 4. Known/Inferred Values

### 4.1 Confirmed from TMNF (Likely Similar in TM2020 Stadium)

| Parameter | TMNF Value | TM2020 Status | Confidence |
|-----------|-----------|---------------|------------|
| Base gravity | 9.81 m/s^2 (stored in GBX) | Same engine, likely same | PLAUSIBLE |
| GravityCoef (ground) | 3.0 | Unknown, likely similar | PLAUSIBLE |
| GravityCoef (air) | 2.5 | Unknown | UNCERTAIN |
| Effective gravity (ground) | ~29.43 m/s^2 | ~29.4 m/s^2 (from doc 10) | PLAUSIBLE |
| Mass | 1.0 (normalized) | Unknown | UNCERTAIN |
| MaxSpeed | 277.778 m/s (1000 km/h) | Community consensus ~1000 km/h | PLAUSIBLE |
| SideFriction1 | 40.0 | Unknown | UNCERTAIN |
| BrakeBase | 1.0 | Unknown | UNCERTAIN |
| Spring stiffness (Ki) | 40.0 | Reparameterized as FreqHz | PLAUSIBLE |
| Damping (Ka) | 1.0 | Reparameterized as DampingRatio | PLAUSIBLE |
| Spring rest length | 0.2 | Unknown | UNCERTAIN |
| MaxSideFrictionBlendCoef | 0.018 | Unknown (iterative solver now) | UNCERTAIN |
| ESteerModel | Steer06 (M6) | Likely case 5 | PLAUSIBLE |
| TurboBoost | 5.0 | Unknown | UNCERTAIN |
| TurboDuration | 250 ms | Unknown | UNCERTAIN |
| Turbo2Boost | 20.0 | Unknown | UNCERTAIN |
| Turbo2Duration | 100 ms | Unknown | UNCERTAIN |
| WaterGravity | 1.0 | Unknown | UNCERTAIN |
| WaterReboundMinHSpeed | 55.556 m/s (200 km/h) | Unknown | UNCERTAIN |
| WaterAngularFriction | 0.1 | Unknown | UNCERTAIN |

### 4.2 Confirmed from TM2020 Binary Analysis

| Parameter | Source | Value/Nature |
|-----------|--------|-------------|
| Speed display conversion | .rdata `0x141d1f71c` | 3.6 (m/s to km/h) |
| Max steer angle range | .rdata | +/- pi/6 (30 degrees) |
| Sleep damping | .rdata `0x141ebcd00` | 0.9 |
| Sleep threshold | .rdata `0x141ebcd04` | 0.01 m/s |
| Max ground detection | .rdata `0x141d1f81c` | 15.0 units |
| Brake/reverse threshold | .rdata `0x141d1f624` | 2.0 m/s |
| Sliding detection threshold | .rdata `0x141d1ef7c` | 0.1 m/s |
| All tuning coefficients | Default | 1.0 (CoefFriction, CoefAcceleration, etc.) |

### 4.3 Confirmed Differences from TMNF

| Aspect | TMNF | TM2020 | Source |
|--------|------|--------|--------|
| Turbo force direction | Decays from max to 0 | Ramps UP from 0 to max | Decompiled code verified |
| Max sub-steps | 10,000 | 1,000 | Binary analysis verified |
| Suspension parameterization | Ki/Ka/Rest (game-specific) | FreqHz/DampingRatio/Length (engineering) | String evidence |
| Friction solver | Per-wheel analytical | Iterative Gauss-Seidel-style | Iteration count fields |
| Force model count | 4 (cases 3/4/5/default) | 7+ (cases 0-6, 0xB) | Switch statement |

---

## 5. Extraction Action Plan

### Phase 1: Runtime Memory Dump (Fastest, This Week)

**Tool**: Custom Openplanet plugin using `Dev::GetOffset*()` calls

1. Write an Openplanet AngelScript plugin that:
   - Gets the vehicle physics model pointer from `car_state+0x88`
   - Reads all known offsets from doc 07-physics-constants.md
   - Dumps values to a JSON file
2. Run in-game on a Stadium map
3. Capture values for all 4 vehicle types (CarSport, CarSnow, CarRally, CarDesert)

**Output**: JSON with ~80 float values per vehicle type

**Key offsets to dump**:
```
model+0x2F0   MaxSpeed
model+0x308   EngineForce
model+0x1790  SteerModel (int)
model+0x1798  BrakeLinearCoef
model+0x179C  BrakeSpeedSlope
model+0x17A0  MaxBrakeForceSliding
model+0x17A4  MaxBrakeForceGrounded
model+0x18D0  GripMultiplier
model+0x192C  FrictionSmoothBlend
model+0x19D0  EngineTorqueY
model+0x19E4  SteerReductionStart
model+0x19E8  SteerReductionEnd
model+0x19EC  AccelReductionStart
model+0x19F0  AccelReductionEnd
model+0x19F4  SlideFrictionBlend
model+0x1A5C  LateralForceLinearCoef
model+0x1A60  LateralForceQuadCoef
model+0xAB0   EngineBrakeForce
model+0xAB4   EngineReverseForce
model+0xCD4   FrictionBlendThreshold
model+0xCD8   SpeedThresholdGrip
model+0xCDC   GripRecoveryRate
model+0xCE0   GripDecayGrounded
model+0xCE4   GripDecayRate2
model+0xCE8   GripDecayAirborne
model+0x16E0  TurboStartDuration
model+0x16E4  TurboForceValue
```

Also dump the gravity vector from the spawn model (CPlugSpawnModel+0x54).

### Phase 2: GBX File Extraction (This Week)

**Tool**: Openplanet Fid Loader or Pack Explorer

1. Install Fid Loader plugin
2. Extract `VehiclePhyModelCustom.Gbx` for CarSport
3. Extract `StadiumCar.ObjectInfo.Gbx`
4. Extract the spawn model GBX
5. Parse with GBX.NET or manual hex analysis

### Phase 3: Full Tuning Parse (Next Week)

**Tool**: GBX.NET with custom extensions

1. If GBX.NET's TM2 support covers the chunk format (which uses backward-compatible IDs):
   - Parse `CPlugVehicleCarPhyTuning` chunks 0x000-0x09F
   - Extract all 150+ parameter values
   - Extract all CFuncKeysReal curve keyframes
2. If GBX.NET fails on TM2020 version chunks:
   - Use hex editor on extracted GBX
   - Match chunk IDs against the known 0x0A029000-0x0A029069 range
   - Manually deserialize using TMNF field-to-chunk mapping

### Phase 4: Community Cross-Validation (Ongoing)

1. Compare extracted values against TMInterface (TMNF) known-good physics
2. Use Openplanet's Record Raw Vehicle Data plugin to capture telemetry
3. Validate extracted gravity by measuring free-fall time in-game
4. Validate max speed by recording top speed on a long straight

---

## 6. Fallback Strategy

If we cannot extract exact TM2020 tuning values, we have these fallbacks in decreasing order of fidelity:

### Fallback A: TMNF Values + TM2020 Behavioral Calibration

Use TMNF StadiumCar values as starting point, then calibrate against recorded TM2020 telemetry:
- Record position/velocity traces using Record Raw Vehicle Data plugin
- Run identical inputs through TMNF-parameterized physics
- Adjust parameters to minimize position error

**TMNF baseline values** (from cross-reference doc 14):
```
Mass = 1.0
GravityCoef = 3.0 (ground), 2.5 (air)
SideFriction1 = 40.0
MaxSpeed = 277.778 m/s (1000 km/h)
BrakeBase = 1.0
Ki = 40.0, Ka = 1.0, Rest = 0.2
MaxSideFrictionBlendCoef = 0.018
ESteerModel = Steer06 (5)
TurboBoost = 5.0, Duration = 250ms
Turbo2Boost = 20.0, Duration = 100ms
```

### Fallback B: Behavioral Measurement

Empirically measure physics parameters through controlled experiments:
- **Gravity**: Drop car from known height, measure fall time -> g = 2h/t^2
- **Max speed**: Long flat straight, measure terminal velocity
- **Friction**: Coast on flat surface, measure deceleration rate
- **Steer rate**: Full steer input, measure angular velocity
- **Spring frequency**: Drive off small bump, measure oscillation period
- **Turbo force**: Measure speed delta from turbo pad

### Fallback C: Community TAS Data

The TMInterface community (donadigo et al.) has extensive replay analysis tools and may have already measured some physics parameters empirically. TMInterface is TMNF-only, but the Openplanet community has equivalent tools for TM2020.

---

## 7. GBX Class Hierarchy for Vehicle Data

```
CGameItemModel (ObjectInfo.Gbx)
 |-- EntityModelEdition
 |-- EntityModel
 |    |-- StaticObject (CPlugStaticObjectModel)
 |    |-- PhyModel (CGameObjectPhyModel -> GameObjectPhyModel.Gbx)
 |    |    |-- DynaObject (CPlugDynaObjectModel -> DynaObject.Gbx)
 |    |    |-- VehiclePhyModelCustom (CPlugVehiclePhyModelCustom -> VehiclePhyModelCustom.Gbx)
 |    |    |    |-- AccelCoef (float, default 1.0)
 |    |    |    |-- ControlCoef (float, default 1.0)
 |    |    |    |-- GravityCoef (float, default 1.0)
 |    |    |-- PhyModel (CPlugVehiclePhyModel)
 |    |    |    |-- PhyShape (CPlugVehicleCarPhyShape)
 |    |    |    |-- Tuning (CPlugVehiclePhyTunings)
 |    |    |    |    |-- Tuning[] (CPlugVehiclePhyTuning array, deprecated)
 |    |    |    |    |-- TuningIndex (int)
 |    |    |    |    |    |-- CPlugVehicleCarPhyTuning (106 chunks, 150+ params)
 |    |    |    |    |    |    |-- GearBox (CPlugVehicleGearBox)
 |    |    |    |    |    |    |-- CFuncKeysReal[] (speed curves)
 |    |    |    |-- WheelPhyModel[] (CPlugVehicleWheelPhyModel)
 |    |    |    |    |-- IsDriving, IsSteering, WheelId
 |    |-- VisModel (CPlugVehicleVisModel -> VehicleVisModel.Gbx)
 |-- SpawnModel (CGameSpawnModel -> Spawn.Gbx / CPlugSpawnModel)
 |    |-- DefaultGravitySpawn (+0x54, Vec3)
```

---

## 8. Critical Findings Summary

| Finding | Implication | Action |
|---------|-------------|--------|
| ALL physics constants are in GBX files | Must extract before physics engine works | Extract via Openplanet (Phase 1-2) |
| GBX.NET has partial TM2020 support | May need custom parsing for newer chunks | Start with GBX.NET, fall back to hex |
| Openplanet Fid Loader can extract from running game | Bypasses PAK encryption | Use as primary extraction method |
| Memory offsets for ~30 key values are known | Can dump at runtime without file parsing | Write Openplanet plugin (Phase 1) |
| TMNF values provide a plausible baseline | Can start physics implementation immediately | Use as initial constants, calibrate later |
| Turbo force direction REVERSED from TMNF | Critical behavioral difference | Must verify via extraction, not assume TMNF values |
| TM2020 suspension uses FreqHz/DampingRatio | Mathematical equivalence to TMNF Ki/Ka known | Convert TMNF values as starting point |
| PAK files are Blowfish-encrypted | Cannot parse offline without keys | Prefer runtime extraction via Openplanet |

---

## 9. Priority Order

1. **IMMEDIATE**: Write Openplanet memory dump plugin to extract all known model offsets at runtime
2. **THIS WEEK**: Use Fid Loader to extract VehiclePhyModelCustom.Gbx and parse with GBX.NET
3. **THIS WEEK**: Start physics engine with TMNF baseline values as placeholder constants
4. **NEXT WEEK**: Parse full CPlugVehicleCarPhyTuning blob (106 chunks) for complete parameter set
5. **NEXT WEEK**: Extract and parse all CFuncKeysReal curves (accel, grip, steer torque, etc.)
6. **ONGOING**: Validate extracted values against in-game telemetry recordings
7. **ONGOING**: Compare all 4 vehicle types (CarSport, CarSnow, CarRally, CarDesert)

---

## References

- `/Users/kelvinnewton/Projects/tm/TM2020/docs/plan/07-physics-constants.md` -- Confirmed data-driven architecture
- `/Users/kelvinnewton/Projects/tm/TM2020/docs/re/14-tmnf-crossref.md` -- TMNF/TM2020 tuning comparison
- `/Users/kelvinnewton/Projects/tm/TM2020/docs/re/10-physics-deep-dive.md` -- Physics model offsets
- `/Users/kelvinnewton/Projects/tm/TM2020/docs/re/21-competitive-mechanics.md` -- Gravity/suspension analysis
- GBX.NET: https://github.com/BigBang1112/gbx-net
- Fid Loader: https://github.com/AurisTFG/tm-fid-loader
- PAK format: https://wiki.xaseco.org/wiki/PAK
- GBX Explorer: https://explorer.gbx.tools/
- Openplanet: https://openplanet.dev/

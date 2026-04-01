# Tuning Data Extraction Plan

TM2020's physics constants (gravity, friction curves, engine curves, suspension parameters, gear ratios) are NOT hardcoded in `Trackmania.exe`. They load at runtime from GBX resource files inside encrypted `.pak` archives. The physics engine cannot function without these values.

The key class chain is:

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

## Where Tuning Files Live

### Inside Pack Files

The tuning data resides inside encrypted `.pak` archives in the game's `Packs/` directory:

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
- `\Trackmania\Items\Vehicles\CoastCar.ObjectInfo.Gbx` (plus Desert, Rally, Snow, and older environments)

Component GBX files include VehiclePhyModelCustom.Gbx, VehicleVisModel.Gbx, VehicleStyles.gbx, VehicleCameraRace2Model.gbx / VehicleCameraRace3Model.gbx, DynaObject.Gbx, and GameObjectPhyModel.Gbx.

### PAK File Encryption

PAK files use Blowfish cipher in CBC mode with a 16-byte key. Key derivation: `md5("[sub-key]" + "NadeoPak")`. Files within PAKs may be zlib-compressed. A non-standard CBC modification XORs the IV every 256 bytes.

---

## Extraction Methods

### Method A: Openplanet Fid Loader (RECOMMENDED -- Runtime Extraction)

The Fid Loader Openplanet plugin (by AurisTFG) extracts files from the running game by file path. This bypasses PAK encryption because the game has already decrypted the files in memory.

1. Install Fid Loader from https://openplanet.dev/plugin/fidloader
2. Launch TM2020 with Openplanet
3. Use Fid Loader to request paths like `Vehicles\Cars\CarSport\VehiclePhyModelCustom.Gbx`
4. Extract to filesystem
5. Parse with GBX.NET

Alternative: Use Openplanet's Pack Explorer (System -> Packs) to browse and extract files. Filenames in packs are hashed; the Pack Explorer resolves names using `FileHashes.txt` cache plus community hash lists at https://openplanet.dev/file/21.

### Method B: TMPakTool (Offline Extraction)

TMPakTool is an open-source C# tool for opening `.pak` files. It requires the correct Blowfish decryption key for TM2020 packs and may not support the newest PAK version.

### Method C: GBX.NET Parsing (After Extraction)

Once extracted, GBX.NET (https://github.com/BigBang1112/gbx-net) parses the files.

| Class | Class ID | GBX.NET Support |
|-------|----------|-----------------|
| `CPlugVehiclePhyTunings` | `0x090EC000` | Read/Write up to TM2 |
| `CPlugVehicleCarPhyTuning` | `0x090ED000` (remapped from `0x0A029000`) | Partial |
| `CPlugVehiclePhyModelCustom` | `0x0911E000` | Partial (AccelCoef, ControlCoef, GravityCoef) |
| `CPlugVehicleGearBox` | `0x09094000` | Partial |
| `CPlugVehicleWheelPhyModel` | `0x0912E000` | Partial (IsDriving, IsSteering, WheelId) |
| `CGameSpawnModel` | varies | Read/Write |

GBX.NET's `VehicleTunings.Gbx` support ends at TM2. TM2020 files may use newer chunk versions. The chunk format is backward-compatible (class ID remapping from `0x0A029` to `0x090ED` is confirmed).

### Method D: Openplanet Memory Dump (Runtime Sniffing)

Write a custom Openplanet plugin that reads tuning values from game memory using `Dev::GetOffsetFloat()`.

Key offsets to dump (relative to physics model pointer at `car_state+0x88`):
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

### Method E: GBX Explorer Web Tool

The online GBX Explorer at https://explorer.gbx.tools/ analyzes extracted GBX files in the browser. Upload extracted files to view structure, chunk contents, and field values.

---

## Parameter Catalog

### CPlugVehicleCarPhyTuning (106 Chunks, ~150+ Parameters)

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

#### Suspension (Spring/Damper Model)
| Parameter | TMNF Value | TM2020 Equivalent |
|-----------|-----------|-------------------|
| AbsorbingValKi (spring stiffness) | 40.0 | Spring.FreqHz = sqrt(Ki/mass)/(2*pi) |
| AbsorbingValKa (damping) | 1.0 | Spring.DampingRatio = Ka/(2*sqrt(Ki*mass)) |
| AbsorbingRestValue (rest length) | 0.2 | Spring.Length |

#### Speed-Dependent Curves (CFuncKeysReal)

| Curve | TMNF Shape | Purpose |
|-------|-----------|---------|
| AccelCurve | Peak 16 at 0 km/h, drops to 1 at 800 km/h | Engine force vs speed |
| MaxSideFriction | 80 at 0-100 km/h, drops to 55 at 500 km/h | Lateral grip vs speed |
| SteerDriveTorque | Peak 16 at 0, plateaus 3.75 above 500 km/h | Torque vs speed |
| ModulationFromWheelCompression | 10% at 0, 100% at 97.5% compression | Grip vs suspension |
| FrictionReductionCurve | At model+0xD40 | Friction reduction factor |

---

## Known and Inferred Values

### Confirmed from TMNF (Likely Similar in TM2020 Stadium)

| Parameter | TMNF Value | Confidence |
|-----------|-----------|------------|
| Base gravity | 9.81 m/s^2 (stored in GBX) | PLAUSIBLE |
| GravityCoef (ground) | 3.0 | PLAUSIBLE |
| Effective gravity (ground) | ~29.43 m/s^2 | PLAUSIBLE |
| MaxSpeed | 277.778 m/s (1000 km/h) | PLAUSIBLE |
| ESteerModel | Steer06 (M6) | PLAUSIBLE |

### Confirmed from TM2020 Binary Analysis

| Parameter | Source | Value |
|-----------|--------|-------|
| Speed display conversion | .rdata `0x141d1f71c` | 3.6 (m/s to km/h) |
| Max steer angle range | .rdata | +/- pi/6 (30 degrees) |
| Sleep damping | .rdata `0x141ebcd00` | 0.9 |
| Sleep threshold | .rdata `0x141ebcd04` | 0.01 m/s |
| Brake/reverse threshold | .rdata `0x141d1f624` | 2.0 m/s |

### Confirmed Differences from TMNF

| Aspect | TMNF | TM2020 |
|--------|------|--------|
| Turbo force direction | Decays from max to 0 | Ramps UP from 0 to max |
| Max sub-steps | 10,000 | 1,000 |
| Suspension parameterization | Ki/Ka/Rest (game-specific) | FreqHz/DampingRatio/Length (engineering) |
| Friction solver | Per-wheel analytical | Iterative Gauss-Seidel-style |
| Force model count | 4 (cases 3/4/5/default) | 7+ (cases 0-6, 0xB) |

---

## Action Plan

### Phase 1: Runtime Memory Dump (Fastest, This Week)

Write an Openplanet AngelScript plugin that gets the vehicle physics model pointer from `car_state+0x88`, reads all known offsets, and dumps values to JSON. Run in-game on a Stadium map. Capture values for all 4 vehicle types (CarSport, CarSnow, CarRally, CarDesert). Output: JSON with ~80 float values per vehicle type.

### Phase 2: GBX File Extraction (This Week)

Install Fid Loader plugin. Extract VehiclePhyModelCustom.Gbx for CarSport, StadiumCar.ObjectInfo.Gbx, and the spawn model GBX. Parse with GBX.NET or manual hex analysis.

### Phase 3: Full Tuning Parse (Next Week)

If GBX.NET's TM2 support covers the chunk format, parse CPlugVehicleCarPhyTuning chunks 0x000-0x09F and extract all 150+ parameter values plus CFuncKeysReal curve keyframes. If GBX.NET fails on TM2020 chunks, use hex editor and manually deserialize using TMNF field-to-chunk mapping.

### Phase 4: Community Cross-Validation (Ongoing)

Compare extracted values against TMInterface (TMNF) known-good physics. Use Openplanet's Record Raw Vehicle Data plugin for telemetry. Validate extracted gravity by measuring free-fall time in-game. Validate max speed on a long straight.

---

## Fallback Strategy

### Fallback A: TMNF Values + TM2020 Behavioral Calibration

Use TMNF StadiumCar values as starting point, then calibrate against recorded TM2020 telemetry. Record position/velocity traces, run identical inputs through TMNF-parameterized physics, adjust parameters to minimize position error.

TMNF baseline values:
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

Measure physics parameters through controlled experiments:
- **Gravity**: Drop car from known height, measure fall time -> g = 2h/t^2
- **Max speed**: Long flat straight, measure terminal velocity
- **Friction**: Coast on flat surface, measure deceleration rate
- **Spring frequency**: Drive off small bump, measure oscillation period
- **Turbo force**: Measure speed delta from turbo pad

### Fallback C: Community TAS Data

The TMInterface community has extensive replay analysis tools. The Openplanet community has equivalent tools for TM2020.

---

## GBX Class Hierarchy for Vehicle Data

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

## Critical Findings

| Finding | Implication | Action |
|---------|-------------|--------|
| ALL physics constants are in GBX files | Must extract before physics engine works | Extract via Openplanet (Phase 1-2) |
| GBX.NET has partial TM2020 support | May need custom parsing for newer chunks | Start with GBX.NET, fall back to hex |
| Openplanet Fid Loader bypasses PAK encryption | Extracts from running game | Use as primary extraction method |
| Memory offsets for ~30 key values are known | Can dump at runtime without file parsing | Write Openplanet plugin (Phase 1) |
| TMNF values provide a plausible baseline | Can start physics implementation immediately | Use as initial constants, calibrate later |
| Turbo force direction REVERSED from TMNF | Critical behavioral difference | Verify via extraction, not assume TMNF values |
| TM2020 suspension uses FreqHz/DampingRatio | Mathematical equivalence to TMNF Ki/Ka known | Convert TMNF values as starting point |
| PAK files are Blowfish-encrypted | Cannot parse offline without keys | Prefer runtime extraction via Openplanet |

---

## Priority Order

1. **IMMEDIATE**: Write Openplanet memory dump plugin for all known model offsets at runtime
2. **THIS WEEK**: Use Fid Loader to extract VehiclePhyModelCustom.Gbx and parse with GBX.NET
3. **THIS WEEK**: Start physics engine with TMNF baseline values as placeholder constants
4. **NEXT WEEK**: Parse full CPlugVehicleCarPhyTuning blob (106 chunks)
5. **NEXT WEEK**: Extract and parse all CFuncKeysReal curves
6. **ONGOING**: Validate extracted values against in-game telemetry recordings
7. **ONGOING**: Compare all 4 vehicle types

---

## Related Pages

- [Physics Constants](07-physics-constants.md) -- Confirmed data-driven architecture
- [Tuning Loading Analysis](10-tuning-loading-analysis.md) -- GBX to runtime data flow
- [Physics Engine](02-physics-engine.md) -- Force model using these parameters
- [Block Mesh Research](05-block-mesh-research.md) -- Same PAK extraction pipeline

## References

- GBX.NET: https://github.com/BigBang1112/gbx-net
- Fid Loader: https://github.com/AurisTFG/tm-fid-loader
- PAK format: https://wiki.xaseco.org/wiki/PAK
- GBX Explorer: https://explorer.gbx.tools/
- Openplanet: https://openplanet.dev/

<details><summary>Document metadata</summary>

- **Date**: 2026-03-27
- **Status**: CRITICAL PATH -- Physics engine cannot function without tuning constants
- **Predecessor**: `07-physics-constants.md` (confirmed all tuning is data-driven)

</details>

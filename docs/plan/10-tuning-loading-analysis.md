# Tuning Loading Analysis - How Vehicle Physics Parameters Flow from GBX to Runtime

## Executive Summary

Vehicle tuning in Trackmania 2020 is **entirely data-driven via GBX files**. There are no hardcoded tuning tables. The game loads physics parameters through the GBX class system, where each class has a registered Archive (serialize/deserialize) function that reads/writes specific fields at known struct offsets. At runtime, these deserialized structs are referenced by pointer from the vehicle entity state, and physics computation functions read values directly from these loaded model data structures.

This document traces the complete data flow: GBX file -> Archive deserialization -> runtime struct -> physics force computation.

---

## 1. GBX Class System Architecture

### 1.1 Class Registration Pattern

Every physics-related GBX class follows the same registration pattern (function `FUN_1402EA9E0`):

```c
RegisterClass(class_id, "ClassName", struct_size, flags, parent_class, 0, 0);
RegisterConstructor(constructor_func);
RegisterArchiveFunction(archive_func, secondary_func);
RegisterFileExtension("ShortName", "ShortName.Gbx");
// Register individual fields for editor/ManiaScript access
RegisterField("FieldName", offset, type_descriptor);
```

### 1.2 Archive (Serialization) Pattern

Every class has an Archive function that handles both reading and writing:

```c
void Archive(longlong this_ptr, longlong archive_stream, int chunk_id) {
    if (chunk_id == MY_CLASS_CHUNK_ID) {
        int version = MAX_VERSION;
        ReadChunkVersion(this_ptr, archive_stream, chunk_id, &version);
        // Read/write fields based on version
        ArchiveFloat(archive_stream, this_ptr + FIELD_OFFSET);
        // Version-gated fields
        if (version > 2) {
            ArchiveFloat(archive_stream, this_ptr + NEW_FIELD_OFFSET);
        }
    }
}
```

The `ArchiveFloat` function (`FUN_14012C310`) checks a mode flag:
- **Mode 0 (read)**: Calls `FUN_14012B9D0` to read 4 bytes from the stream into the target address
- **Mode != 0 (write)**: Calls `FUN_14012B790` to write 4 bytes from the target address to the stream

### 1.3 GBX Loading Pipeline

```
ArchiveNod::LoadGbx (FUN_140904730)
  -> Opens file stream
  -> Reads GBX header (magic "GBX", version, class ID)
  -> Creates class instance via registered constructor
  -> FUN_140903D30 (body loader)
    -> FUN_140902530 (header chunks)
    -> FUN_1409031D0 (body chunks)
      -> For each chunk: calls Archive function with chunk ID
      -> Resolves internal node references to other GBX objects
```

The body loader (`FUN_1409031D0`) handles compressed data (LZO decompression at chunk level), internal cross-references between nodes, and version compatibility via the chunk version system.

---

## 2. Vehicle Physics Class Hierarchy

### 2.1 CGameItemModel (Top Level)

**Address**: Registration at `0x140057760`
**Class ID**: `0x2E002000`
**Size**: `0x2C0` bytes

This is the root item container. For vehicles, key offsets:

| Offset | Field | Description |
|--------|-------|-------------|
| 0x120 | PhyModelCustom | `CPlugVehiclePhyModelCustom*` - runtime tuning modifiers |
| 0x128 | VisModelCustom | Visual model customization |
| 0x148 | MaterialModifier | Material override |
| 0x158 | Camera array | Camera definitions |
| 0x168 | DefaultCam | Default camera selection |
| 0x180 | WaypointType | Start/Checkpoint/Finish |
| 0x1B8 | GroundPoint | Ground contact reference |
| 0xF8 | ArchetypeRef | Base archetype reference |

### 2.2 CPlugVehiclePhyModelCustom (Tuning Modifiers)

**Address**: Registration at `0x14061ABB0`, Archive at `0x14061AAE0`
**Class ID**: `0x0911E000`
**Size**: `0x38` bytes
**GBX file**: `VehiclePhyModelCustom.Gbx`

| Offset | Field | Type | Default | Description |
|--------|-------|------|---------|-------------|
| 0x18 | AccelCoef | float | 1.0 | Acceleration multiplier |
| 0x1C | ControlCoef | float | 1.0 | Steering/control multiplier |
| 0x20 | GravityCoef | float | 1.0 | Gravity multiplier |

These are the three primary tuning coefficients that modify vehicle physics behavior. They're exposed as `Modifiers.AccelCoef`, `Modifiers.ControlCoef`, `Modifiers.GravityCoef` to the engine.

### 2.3 CPlugVehicleCarPhyShape (Car Physics Shape)

**Address**: Registration at `0x140619210`, Archive at `0x140618A60`
**Class ID**: `0x0910E000`
**Size**: `400` bytes
**Archive version**: Up to 6

This is the richest tuning data class, containing suspension geometry, collision shape, mass distribution, and physics curves. Key deserialized fields:

| Offset | Type | Default | Likely Purpose |
|--------|------|---------|----------------|
| 0x18 | Curve | - | Main physics curve (accel/brake response?) |
| 0x24 | float | -1.0 | Unknown (axis?) |
| 0x28 | float | -1.0 | Unknown |
| 0x2C | float | -1.0 | Unknown |
| 0x30-0x44 | 6 floats | various | Shape geometry parameters |
| 0x38 | float | 1.0 | Unknown |
| 0x3C | float | -1.0 | Unknown |
| 0x40 | float | 1.0 | Unknown |
| 0x44 | float | 1.0 | Unknown |
| 0x48 | float | - | Shape parameter |
| 0x4C-0x58 | 4 floats | 0.5 each | Inertia/mass distribution? |
| 0x60 | NodeRef | - | Solid collision mesh |
| 0x70, 0x78 | NodeRef | - | Additional collision meshes (v6+) |
| 0x80, 0x88 | Data | - | Mesh collision data (v3+) |
| 0x98 | NodeRef | - | Solid2 reference (v5+) |
| 0xA0 | Curve | - | Secondary physics curve |
| 0xA4 | float | 0.6 | Unknown |
| 0xA8 | float | 0.1 | Unknown |
| 0xB0 | float | 0.6 | Unknown |
| 0xB4 | float | 2.1 | Unknown |
| 0xC0 | SubStruct | - | Unknown sub-structure |
| 0xD0 | Array | - | Dynamic array of {float, float, subdata} elements |
| 0xE0-0x124 | 14 floats | - | Extended shape properties |
| 0x148+ | float[6][3] | - | 6-element 3D data (v4+, likely contact points) |

### 2.4 CPlugVehicleGearBox

**Address**: Registration at `0x1405B58A0`, Constructor at `0x1405B55A0`
**Class ID**: `0x09094000`
**Size**: `0x58` bytes

Default gear speed thresholds (7 gears, km/h):

| Gear | Speed (km/h) | Hex |
|------|-------------|-----|
| 1 | 56.0 | 0x42600000 |
| 2 | 84.0 | 0x42A80000 |
| 3 | 100.0 | 0x42C80000 |
| 4 | 143.0 | 0x430F0000 |
| 5 | 207.0 | 0x434F0000 |
| 6 | 297.0 | 0x43948000 |
| 7 | 338.0 | 0x43A90000 |

Other defaults: Max RPM = 7000, Shift RPM = 6500.

### 2.5 CPlugVehicleWheelPhyModel

**Address**: Registration at `0x1406190C0`
**Size**: `0x0C` bytes

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0x00 | (unnamed) | NodeRef | Wheel physics data |
| 0x04 | IsDriving | bool | Whether this wheel provides drive |
| 0x08 | IsSteering | bool | Whether this wheel steers |

### 2.6 CPlugSpawnModel

**Address**: Registration at `0x1406219A0`
**Size**: `0x60` bytes
**GBX file**: `Spawn.gbx`

| Offset | Field | Type | Default | Description |
|--------|-------|------|---------|-------------|
| 0x18 | (unnamed) | NodeRef | - | Spawn position reference |
| 0x4C | TorqueX | float | 0.0 | Spawn torque X component |
| 0x50 | TorqueDuration | int | 0 | Duration of spawn torque |
| 0x54 | DefaultGravitySpawn | vec3 | (0, -1.0, 0) | Gravity direction at spawn |

---

## 3. Runtime Vehicle Entity Layout

When a vehicle is spawned, a large runtime entity struct (~0x1C90+ bytes) is created. Key offsets observed in `ComputeForces` and `PhysicsStep_TM`:

| Offset | Type | Description |
|--------|------|-------------|
| 0x10 | int | Vehicle sub-ID |
| 0x88 | ptr | Vehicle config/state data pointer |
| 0x90-0x100 | matrix | Current position/rotation state (13 floats + extras) |
| 0x104-0x174 | matrix | Previous frame state (copied at end of step) |
| 0x1280 | struct | Friction/physics coefficients area |
| 0x128C | int | Vehicle state flags (& 0xF = state enum) |
| 0x1338 | float | Current force multiplier (set by FUN_140845220) |
| 0x1348-0x135C | vec3+vec3 | Position delta components |
| 0x1534-0x153C | vec3 | Alternative state vector (for type >= 6) |
| 0x158C | float | Some coefficient value |
| 0x175C | float | Custom gravity override (0 = use default) |
| 0x1790+ | per-wheel | Per-wheel force accumulation data |
| 0x1B74-0x1B9C | struct | Modifier state 1 |
| 0x1B8C-0x1B9C | struct | Modifier state 2 |
| 0x1BB0 | ptr | **Physics model data pointer** (the loaded GBX model) |
| 0x1C7C | uint | Per-tick flags |
| 0x1C78 | char | Some state byte |
| 0x1C8C | float | Speed or similar |
| 0x1C90 | int | Entity physics mode (0=active, 2=frozen, 3=active-alt) |
| 0x2E8+ | array | **Delayed modification queue** (16 bytes per entry) |

### 3.1 Physics Model Data (at entity + 0x1BB0)

This pointer references the **loaded GBX physics model data**. Key offsets observed:

| Offset | Type | Description |
|--------|------|-------------|
| 0x88 | int | Some physics type/mode |
| 0x238 | int | Vehicle type selector (-5 = check) |
| 0x278 | float | Some threshold (checked < 0) |
| 0x2AE0 | float | Speed threshold low |
| 0x2AE4 | float | Speed threshold high |
| 0x2AFC | float | Minimum grip coefficient |
| 0x2B0 | ptr | Dynamics curves object |
| 0x2B14 | float | Lateral force multiplier |
| 0x2B30 | Curve | Speed-dependent curve |
| 0x2B80 | uint | Recovery time (ticks) |
| 0x2C1C | int | Mode flag |
| 0x308 | float | Anti-roll force |
| 0x310/314 | float | Max lateral/longitudinal force |
| 0xAB0/AB4 | float | Pitch force thresholds |
| 0xC48 | float | Yaw threshold |
| 0xCD4 | float | Speed normalization factor |
| 0xD40 | Curve | Speed-dependent curve |
| 0xE0 | float | Engine power coefficient (accessed via entity+0x1BB0+0xE0) |
| 0x1298 | struct | Contact point data |
| 0x1790 | int | **Vehicle type enum** (0-6, 0xB) |
| 0x15A8 | struct | Reactor boost state |

---

## 4. Force Computation Pipeline

### 4.1 Call Chain

```
PhysicsStep_TM (0x141501800)
  -> For each vehicle entity:
    -> Calculate sub-step count based on velocity
    -> For each sub-step:
      -> NSceneVehiclePhy::ComputeForces (0x1408427D0)
        -> Speed clamping
        -> switch (model_data + 0x1790):
          -> case 6: FUN_14085C9E0 (TM2020 car)
            -> FUN_14083D8E0 (contact force setup)
            -> FUN_140858660 (tire force computation)
            -> FUN_1408581D0 (engine force)
            -> FUN_1408570E0 (per-wheel force loop)
            -> FUN_14085AD30 (aerodynamic forces)
            -> FUN_14085A0D0 (some additional forces)
            -> FUN_14085BA50 (unknown)
            -> FUN_140858C90 (wheel state update)
            -> FUN_140857380 (steering response)
            -> FUN_140857B20 (stability?)
            -> FUN_14085C1B0 (final integration)
            -> FUN_140858E70 (airborne physics)
            -> FUN_140855EA0 (reactor/boost)
            -> FUN_1408562D0 (ground effect)
```

### 4.2 Vehicle Type Dispatch

The `model_data + 0x1790` value selects which force model to use:

| Value | Handler | Likely Vehicle |
|-------|---------|----------------|
| 0,1,2 | FUN_140869CD0 | Legacy/ShootMania |
| 3 | FUN_14086B060 | Unknown |
| 4 | FUN_14086BC50 | Unknown |
| 5 | FUN_140851F00 | TM2/TurboMania |
| 6 | FUN_14085C9E0 | **TM2020 car** (CarSport, CarSnow, CarRally, CarDesert) |
| 11 | FUN_14086D3B0 | Unknown |

### 4.3 How Tuning Modifiers Are Applied

In the case 6 force computation (`FUN_14085C9E0`):

1. **AccelCoef** is read from the loaded model at `model + 0xA54` (via `*plVar1[0] + 0xA54`) and multiplied with the dynamic accel state at `plVar1 + 0x2EB`
2. The combined coefficient is clamped to [0, 1]
3. If modifier state 1 is active (`entity + 0x1B8C != 0`), it's further multiplied by `entity + 0x1B9C`
4. If modifier state 2 is active (`entity + 0x1B74 != 0`), it's further multiplied by `entity + 0x1B7C`
5. The final value is passed to the wheel force computation

The **GravityCoef** flows through the spawn model's `DefaultGravitySpawn` (offset 0x54) and the gravity override at `entity + 0x175C`.

---

## 5. ManiaScript Runtime Tuning Interface

### 5.1 NGameSlotPhy::SMgr Tuning Parameters

**Registration**: `0x141071B20`
**Size**: `0x90` bytes

| Offset | ManiaScript Name | Type | Description |
|--------|-----------------|------|-------------|
| 0x58 | Tunings.CoefFriction | float | Global friction coefficient |
| 0x5C | Tunings.CoefAcceleration | float | Global acceleration coefficient |
| 0x60 | Tunings.Sensibility | float | Steering sensitivity |

### 5.2 Delayed Modification System

ManiaScript modifies vehicle physics via `SetPlayer_Delayed_*` functions. These queue modifications that take effect after a delay (approximately +600 ticks).

The queue lives at `entity + 0x2E8`, each entry being 16 bytes:

```c
struct DelayedModification {
    int apply_tick;        // +0x00: When to apply (current_tick + 600)
    int type;              // +0x04: What to modify
    float value;           // +0x08: New value
    short duration;        // +0x0C: Duration
    byte sub_type;         // +0x0E: Sub-type flag
    int extra;             // +0x10: Extra data
};
```

Available modifications:
- **NoBrakes** / **NoSteer** / **NoEngine** / **ForceEngine** - binary toggles
- **AccelCoef** (type 0xD) - acceleration multiplier [0..1]
- **ControlCoef** - steering multiplier [0..1]
- **GravityCoef** - gravity multiplier [0..1]
- **AdherenceCoef** - friction/grip multiplier [0..1]
- **BoostUp/BoostDown/Boost2Up/Boost2Down** - boost state changes
- **TireWear** - tire degradation
- **Cruise** - cruise control mode
- **Fragile** - fragile mode (car breaks easily)
- **SlowMotion** - slow motion effect
- **VehicleTransform** - vehicle transformation
- **Reset** - full vehicle reset

### 5.3 Deprecation Notes

Several older ManiaScript functions are deprecated with messages pointing to `SetPlayer_Delayed_AccelCoef`:
- "This way of setting GravityCoef is deprecated..."
- "This way of setting AdherenceCoef is deprecated..."
- "This way of setting AccelCoef is deprecated..."
- "This way of setting ControlCoef is deprecated..."

This suggests the delayed modification system is the newer, preferred API.

---

## 6. Vehicle Type Registry

The game maintains a static registry of all vehicle types at `0x141F75540`, initialized by `FUN_140CD5590`:

### TM2020 Vehicles (Items)
| Name | GBX Path | Type | Flags |
|------|----------|------|-------|
| CarSport | \Vehicles\Items\CarSport.Item.gbx | 0x10 | 0x21 |
| CarSnow | \Vehicles\Items\CarSnow.Item.gbx | 0x10 | 0x20 |
| CarRally | \Vehicles\Items\CarRally.Item.gbx | 0x10 | 0x21 |
| CarDesert | \Vehicles\Items\CarDesert.Item.gbx | 0x10 | 0x22 |

### Legacy TM Vehicles (ObjectInfo)
| Name | GBX Path | Type | Flags |
|------|----------|------|-------|
| CanyonCar | \Trackmania\Items\Vehicles\CanyonCar.ObjectInfo.Gbx | 0x0F | 0x33 |
| StadiumCar | \Trackmania\Items\Vehicles\StadiumCar.ObjectInfo.Gbx | 0x0F | 0x34 |
| ValleyCar | \Trackmania\Items\Vehicles\ValleyCar.ObjectInfo.Gbx | 0x0F | 0x33 |
| LagoonCar | \Trackmania\Items\Vehicles\LagoonCar.ObjectInfo.Gbx | 0x0F | 0x33 |
| (and more...) | | | |

---

## 7. Key Function Addresses

| Address | Function | Description |
|---------|----------|-------------|
| 0x141501800 | PhysicsStep_TM | Main physics tick |
| 0x1408427D0 | ComputeForces | Force dispatcher |
| 0x14085C9E0 | Case6_ComputeForces | TM2020 car forces |
| 0x14061ABB0 | CPlugVehiclePhyModelCustom::Register | Tuning class registration |
| 0x14061AAE0 | CPlugVehiclePhyModelCustom::Archive | Tuning deserialization |
| 0x140618A60 | CPlugVehicleCarPhyShape::Archive | Car shape deserialization |
| 0x1405B58A0 | CPlugVehicleGearBox::Register | Gearbox registration |
| 0x1406219A0 | CPlugSpawnModel::Register | Spawn model registration |
| 0x1406190C0 | CPlugVehicleWheelPhyModel::Register | Wheel model registration |
| 0x140CD5590 | VehicleRegistry::Init | Vehicle type registry |
| 0x141071B20 | NGameSlotPhy::Register | ManiaScript tuning |
| 0x141342950 | SetDelayed_AccelCoef | ManiaScript AccelCoef handler |
| 0x141342450 | QueueDelayedModification | Modification queue |
| 0x140904730 | ArchiveNod::LoadGbx | GBX body loader |
| 0x140903D30 | ArchiveNod::LoadBody | GBX body parser |
| 0x1409031D0 | ArchiveNod::ReadChunks | Chunk iteration |
| 0x1402D0D70 | ReadChunkVersion | Version negotiation |
| 0x14012C310 | ArchiveFloat | Float serialize/deserialize |
| 0x140ABCE80 | CGameObjectPhyModel::LoadData | Physics model assembly |

---

## 8. Implications for Physics Recreation

### 8.1 What This Means

1. **ALL tuning parameters are in GBX files** - There are no hardcoded tuning tables in the executable. The CarSport's acceleration curve, grip model, suspension geometry, etc. are all loaded from `CarSport.Item.gbx` and its referenced sub-GBX files.

2. **The physics model pointer chain is**: `CGameItemModel -> PhyModelCustom (offset 0x120) -> CPlugVehiclePhyModelCustom` for the high-level modifiers, and `CGameObjectPhyModel -> LoadData -> sub-GBX references` for the full physics model.

3. **Runtime access is direct pointer dereference** - The physics code reads tuning values directly from the loaded GBX struct memory. No intermediate processing or caching layer exists.

4. **Vehicle type dispatch at offset 0x1790** determines which force model runs. TM2020 cars use type 6.

### 8.2 To Extract All Tuning Data

1. Parse `CarSport.Item.gbx` using GBX.NET to extract the `CPlugVehiclePhyModelCustom` reference
2. Follow all sub-node references to find `CPlugVehicleCarPhyShape`, `CPlugVehicleGearBox`, `CPlugSpawnModel`, `CPlugVehicleWheelPhyModel`
3. The Archive functions documented here tell you exactly which bytes at which offsets correspond to which parameters
4. The default values from constructors provide fallback values when GBX data doesn't specify them

### 8.3 Missing Pieces

- The large physics model struct referenced at `entity + 0x1BB0` with offsets up to 0x2C1C+ is NOT directly a single GBX class - it appears to be a runtime-assembled composite from multiple loaded GBX nodes
- The exact mapping of CarPhyShape fields (0x30-0x44, 0xE0-0x124, etc.) to named physics parameters requires either: (a) finding additional registration functions that name them, or (b) systematic float extraction from known GBX files and correlation with observed behavior
- The per-wheel force computation functions (FUN_1408570E0, FUN_140858660, etc.) need deeper analysis to understand the exact force model

---

## 9. Decompiled Functions

All decompiled functions are saved to: `decompiled/tuning/`

- `CPlugVehiclePhyModelCustom_Archive.c` - Tuning modifier serialization
- `CPlugVehicleCarPhyShape_Archive.c` - Car shape serialization (richest data class)
- `CPlugVehicleGearBox_Constructor.c` - Default gear ratios
- `CPlugSpawnModel_Registration.c` - Spawn physics data
- `NSceneVehiclePhy_ComputeForces.c` - Force computation dispatcher
- `PhysicsStep_TM.c` - Main physics tick
- `ManiaScript_Tuning_Registration.c` - Runtime tuning parameters
- `SetPlayer_Delayed_AccelCoef.c` - ManiaScript modification handler
- `VehicleRegistry.c` - All registered vehicle types

# OpenTM Physics Engine Design

The physics engine reproduces TM2020 vehicle physics bit-for-bit where decompiled code exists, with documented approximations elsewhere. It compiles from Rust to WASM (wasm32-unknown-unknown) and targets the `opentm-physics` crate.

---

## Rust Module Structure

```
opentm-physics/
  Cargo.toml
  src/
    lib.rs                  -- WASM entry points, tick dispatch, SharedArrayBuffer bridge
    vehicle.rs              -- VehicleState struct (complete ~7328-byte entity state)
    vehicle_model.rs        -- VehicleModel struct (tuning/physics model data)
    step.rs                 -- PhysicsStep_TM equivalent (FUN_141501800)
    input.rs                -- Input state (steer, gas, brake, reactor)
    timing.rs               -- Integer tick counter, microsecond conversion
    math.rs                 -- Guarded sqrt, vec3, mat3x4, quaternion, IEEE 754 helpers
    curve.rs                -- CFuncKeysReal curve sampling (FUN_14042bcb0)

    forces/
      mod.rs                -- Force model dispatcher (switch on model_type)
      compute_forces.rs     -- NSceneVehiclePhy::ComputeForces (FUN_1408427d0)
      base_4wheel.rs        -- Cases 0/1/2 (FUN_140869cd0) - base 4-wheel model
      bicycle.rs            -- Case 3 (FUN_14086b060) - 2-wheel bicycle model
      case4.rs              -- Case 4 (FUN_14086bc50) - TMNF M5 equivalent
      case5.rs              -- Case 5 (FUN_140851f00) - CarSport/Stadium full model
      carsport.rs           -- Case 6 (FUN_14085c9e0) - Extended CarSport model
      case0xb.rs            -- Case 0xB (FUN_14086d3b0) - Desert/variant model
      per_wheel.rs          -- FUN_1408570e0 - per-wheel force (used by cases 5/6/0xB)
      steering.rs           -- FUN_14085ad30 - steering model
      suspension.rs         -- FUN_14085a0d0 - suspension/contact update
      antiroll.rs           -- FUN_14085ba50 - anti-roll bar
      damping.rs            -- FUN_140858c90 - velocity damping
      drift.rs              -- FUN_140857380 - drift/skid model
      boost.rs              -- FUN_140857b20 - boost/reactor spring forces
      airborne.rs           -- FUN_14085c1b0 - airborne control (pitch/roll/yaw)
      final_integration.rs  -- FUN_14085b600 - final force integration
      slope.rs              -- FUN_1408456b0 - slope gravity factor
      wheel_surface.rs      -- FUN_140845b60 - wheel contact surface accumulation
      lateral_grip.rs       -- FUN_14086af20 - lateral grip (2-wheel model)

    collision/
      mod.rs                -- Collision pipeline orchestration
      broadphase.rs         -- Spatial acceleration (grid or BVH)
      cache.rs              -- DynamicCollisionCreateCache (FUN_1407f9da0)
      contacts.rs           -- Contact point structure (88-byte stride)
      merge.rs              -- NHmsCollision::MergeContacts (FUN_1402a8a70)
      friction.rs           -- Gauss-Seidel sequential impulse solver
      process.rs            -- ProcessContactPoints (FUN_1407d2b90)
      start_frame.rs        -- StartPhyFrame (FUN_1402a9c60)

    dynamics/
      mod.rs                -- Rigid body integration orchestrator
      step_v2.rs            -- NSceneDyna::PhysicsStep_V2 (FUN_140803920)
      internal_step.rs      -- NSceneDyna::InternalPhysicsStep (FUN_1408025a0)
      gravity.rs            -- ComputeGravityAndSleepStateAndNewVels (FUN_1407f89d0)
      water.rs              -- ComputeWaterForces (FUN_1407f8290)
      body.rs               -- Body struct (56 bytes, stride 0x38)
      solver_params.rs      -- SSolverParams (44 bytes)

    surfaces.rs             -- 22 gameplay surface effects + 19 material surface IDs
    tuning.rs               -- Tuning parameter structs, GBX chunk loading bridge
    events.rs               -- Boost events, fragile break, checkpoint triggers
```

### Dependency Graph

```
lib.rs
  -> step.rs (PhysicsStep_TM)
       -> forces/compute_forces.rs
            -> forces/{base_4wheel, bicycle, case4, case5, carsport, case0xb}.rs
                 -> forces/{per_wheel, steering, suspension, antiroll, damping, drift, boost, airborne, slope, wheel_surface, lateral_grip}.rs
       -> dynamics/step_v2.rs
            -> dynamics/{internal_step, gravity, water, body}.rs
       -> collision/{start_frame, cache, merge, process, friction}.rs
  -> vehicle.rs
  -> tuning.rs
  -> surfaces.rs
  -> curve.rs
  -> math.rs
```

---

## VehicleState Struct

Derived from aggregated decompiled offsets across all 34 physics .c files, cross-referenced with Openplanet's CSceneVehicleVisState.

### Complete Rust Definition

```rust
/// Complete vehicle entity state. ~7328 bytes in TM2020 (highest known offset: 0x1CA0).
/// Offsets are from decompiled code; names are best-effort from string analysis.
///
/// VERIFIED = offset confirmed in decompiled code
/// OPENPLANET = field name from Openplanet plugin (visual state, may differ from physics state)
/// UNKNOWN = purpose not determined
#[repr(C)]
pub struct VehicleState {
    // --- Core Identity ---
    // +0x00..+0x0F: [UNKNOWN] - likely vtable pointer and ref counts
    _header: [u8; 16],

    /// +0x10: Dynamics body ID in the NSceneDyna world. -1 = no body.
    /// Read: ComputeForces, PhysicsStep_TM. Written: initialization.
    pub dyna_body_id: i32,                  // VERIFIED

    _pad_14: [u8; 60],                      // +0x14..+0x4F

    /// +0x50: Alternate collision object pointer
    /// Read: BeforeMgrDynaUpdate
    pub collision_object_alt: u64,          // VERIFIED

    _pad_58: [u8; 40],                      // +0x58..+0x7F

    /// +0x80: Primary collision object pointer
    /// Read: BeforeMgrDynaUpdate
    pub collision_object: u64,              // VERIFIED

    /// +0x88: Pointer to physics model (VehiclePhyModel). Contains tuning data.
    /// Read: ComputeForces, PhysicsStep_TM.
    pub phy_model_ptr: u64,                 // VERIFIED

    /// +0x90..+0x103: Current world transform.
    /// 3x4 rotation+translation matrix stored as 28 x f32 = 112 bytes.
    /// The first 9 floats are the 3x3 rotation matrix (row-major or column-major TBD).
    /// The last 3 floats are the position (x, y, z).
    /// The remaining 16 bytes (4 floats) are auxiliary transform data.
    /// Written: dynamics integrator. Read: PhysicsStep_TM, ComputeForces.
    pub current_transform: [f32; 28],       // VERIFIED (112 bytes)

    /// +0x104..+0x177: Previous frame's world transform.
    /// Copied from current_transform at START of each PhysicsStep_TM.
    /// Used for interpolation and collision backtracking.
    pub previous_transform: [f32; 29],      // VERIFIED (116 bytes, slightly larger to 0x178)

    _pad_178: [u8; 28],                     // +0x178..+0x193

    /// +0x194: Reset flag. Checked != 0 in BeforeMgrDynaUpdate, then zeroed.
    pub reset_flag: i32,                    // VERIFIED

    _pad_198: [u8; 0x34C],                  // +0x198..+0x4E3

    // --- Visual State Region ---
    // +0x4E8..+0x847: Wheel visual state base (used by ExtractVisStates)
    _vis_state_region: [u8; 0x360],         // VERIFIED region exists

    // +0x848: Alternate wheel visual state (ExtractVisStates)
    _vis_state_alt: [u8; 0x438],            // VERIFIED region

    // --- Vehicle Identity ---
    /// +0x1280: Vehicle unique ID. Used as entity identifier in events.
    /// Read: ComputeForces (event dispatch), ArenaPhysics.
    pub vehicle_unique_id: u32,             // VERIFIED

    /// +0x1284: Pair ID / Team ID. Used for collision pair exclusion.
    pub pair_id: i32,                       // VERIFIED

    _pad_1288: [u8; 4],                     // +0x1288..+0x128B

    /// +0x128C: Status flags. Low nibble is state enum:
    ///   0 = Active/Ready (normal physics)
    ///   1 = Reset/Inactive (forces zeroed)
    ///   2 = Excluded (skipped in PhysicsStep_TM)
    ///   3 = [UNKNOWN] (checked as "excluded-like" in BeforeMgrDynaUpdate)
    pub status_flags: u32,                  // VERIFIED

    _pad_1290: [u8; 0x38],                  // +0x1290..+0x12C7

    /// +0x12C8: Negated parameter (used in ArenaPhysics_CarPhyUpdate)
    pub negated_something: i32,             // VERIFIED

    _pad_12cc: [u8; 0xC],                   // +0x12CC..+0x12D7

    /// +0x12D8: Contact data base (passed to FUN_14084c840)
    pub contact_data: [u8; 4],              // VERIFIED

    /// +0x12DC: Tick stamp. 0xFFFFFFFF = unset.
    pub tick_stamp: u32,                    // VERIFIED

    /// +0x12E0: Transform data (48+ bytes, mat3x4)
    pub transform_data: [u8; 0x30],         // VERIFIED

    _pad_1310: [u8; 4],                     // +0x1310..+0x1313

    /// +0x1314: Intermediate transform data
    pub intermediate_transform: [u8; 0x24], // VERIFIED

    /// +0x1338: Param passed to FUN_1407be770
    pub dyna_param: u32,                    // VERIFIED

    _pad_133c: [u8; 0xC],                   // +0x133C..+0x1347

    /// +0x1348: Velocity vector 1 (3 x f32). Used in sub-step magnitude calculation.
    /// Likely wheel-related angular velocity.
    pub velocity_vec1: [f32; 3],            // VERIFIED

    /// +0x1354: Velocity vector 2 (3 x f32). Used in sub-step magnitude calculation.
    pub velocity_vec2: [f32; 3],            // VERIFIED

    _pad_1360: [u8; 0x28],                  // +0x1360..+0x1387

    /// +0x1388 (decimal 5000): Current boost state. Copied to prev_boost_state, then zeroed.
    pub current_boost_state: u32,           // VERIFIED

    /// +0x138C: Ground contact flag for airborne model.
    /// 0 = no ground detected; 1 = ground within raycast range.
    pub ground_detected: i32,               // VERIFIED (airborne_control.c)

    _pad_1390: [u8; 0x14],                  // +0x1390..+0x13A3

    /// +0x13A4: Airborne nose-down accumulator.
    /// Gradually increases while airborne for nose-down pitch effect.
    pub airborne_pitch_accum: f32,          // VERIFIED (airborne_control.c)

    /// +0x1408: Force accumulator flag. Zeroed each frame.
    pub force_accum_flag: i32,              // VERIFIED

    _pad_140c: [u8; 0x40],                  // +0x140C..+0x144B

    /// +0x144C: Force accumulator for models 0-5 (3 x f32 = vec3).
    pub force_accum_model_0to5: [f32; 3],   // VERIFIED

    _pad_1458: [u8; 0xDC],                  // +0x1458..+0x1533

    /// +0x1534: Force accumulator for models 6+ (3 x f32 = vec3).
    pub force_accum_model_6plus: [f32; 3],  // VERIFIED

    _pad_1540: [u8; 0x18],                  // +0x1540..+0x1557

    /// +0x1558: Last checkpoint timestamp (for launched checkpoint boost).
    pub last_checkpoint_time: i64,          // VERIFIED (boost_reactor_force.c)

    _pad_1560: [u8; 0xC],                   // +0x1560..+0x156B

    /// +0x156C: Slip counter. Zeroed each frame.
    pub slip_counter: i32,                  // VERIFIED

    /// +0x1570: Initial velocity XY (zeroed each frame).
    pub initial_velocity_xy: [f32; 2],      // VERIFIED

    /// +0x1578: Initial velocity Z (zeroed each frame).
    pub initial_velocity_z: f32,            // VERIFIED

    _pad_157c: [u8; 8],                     // +0x157C..+0x1583

    /// +0x1584: Reset force vector (zeroed on state-1 reset).
    pub reset_force: [f32; 2],              // VERIFIED

    /// +0x158C: Alternative steering sensitivity / reset force continued.
    pub alt_steering_or_reset: [u8; 8],     // VERIFIED

    /// +0x1594: Wheel contact history circular buffer.
    ///   [0..3]: write_index (u32), buffer_size (u32, always 0x14 = 20)
    ///   [8..27]: 20 bytes of quantized surface state
    pub contact_history_header: [u32; 2],   // VERIFIED
    pub contact_history_data: [u8; 20],      // VERIFIED

    /// +0x15B0: Contact state change count (oscillation detection).
    pub contact_state_change_count: i32,    // VERIFIED

    _pad_15b4: [u8; 0xF4],                  // +0x15B4..+0x16A7 (includes checkpoint data at 0x15A8)

    _pad_16a8: [u8; 0x38],                  // +0x16A8..+0x16DF

    /// +0x16E0: Boost duration (in ticks). 0 = no boost.
    pub boost_duration: u32,                // VERIFIED

    /// +0x16E4: Boost strength (force magnitude).
    pub boost_strength: f32,                // VERIFIED

    /// +0x16E8: Boost start time (tick). 0xFFFFFFFF = no active boost.
    pub boost_start_time: u32,              // VERIFIED

    _pad_16ec: [u8; 0x70],                  // +0x16EC..+0x175B

    /// +0x175C: Custom force parameter. If != 0.0, applies custom force.
    pub custom_force_param: f32,            // VERIFIED

    _pad_1760: [u8; 0x30],                  // +0x1760..+0x178F

    // --- Per-Wheel State Blocks (4 wheels, stride 0xB8 = 184 bytes each) ---
    // Starting at +0x1790, each wheel block contains:
    //   +0x00 (0x1790): force_model_type / base value
    //   +0x04 (0x1794): state [UNKNOWN]
    //   +0x20 (0x17B0): prev_value
    //   +0x24 (0x17B4): curr_value (contact state for this hardpoint)
    //   +0x34 (0x17C4): timer1
    //   +0x38 (0x17C8): timer2
    //   ... per-wheel physics data up to +0xB7
    // The stride is 0xB8 = 184 bytes.
    // FL = +0x1790, FR = +0x1848, RR = +0x1900, RL = +0x19B8
    // Wheel order: FL(0), FR(1), RR(2), RL(3) -- clockwise from front-left.

    /// +0x1790..+0x1A6F: Four per-wheel state blocks.
    pub wheel_blocks: [WheelPhyBlock; 4],   // VERIFIED (stride 0xB8)

    _pad_1a70: [u8; 0x88],                  // +0x1A70..+0x1AF7

    /// +0x1AF8: Previous boost state (copied from current_boost_state each frame).
    pub prev_boost_state: u32,              // VERIFIED

    _pad_1afc: [u8; 0xB4],                  // +0x1AFC..+0x1BAF

    /// +0x1BB0: Vehicle model class pointer.
    /// Read: ComputeForces, PhysicsStep_TM. Points to object with:
    ///   +0xE0: model scale (multiplied into boost force)
    ///   +0x278: time/state param (checked for <= 0.0 && != 0.0)
    ///   +0x2A0..+0x2A8: airborne control params
    ///   +0x2B0: transform vtable pointer
    pub vehicle_model_ptr: u64,             // VERIFIED

    /// +0x1BB8: Auxiliary physics pointer.
    pub aux_physics_ptr: u64,               // VERIFIED

    /// +0x1BC0: Physics flags byte. Bit 0 checked in BeforeMgrDynaUpdate.
    pub phy_flags: u8,                      // VERIFIED

    _pad_1bc1: [u8; 7],                     // +0x1BC1..+0x1BC7

    /// +0x1BC8: Contact processor pointer.
    pub contact_processor_ptr: u64,         // VERIFIED

    _pad_1bd0: [u8; 8],                     // +0x1BD0..+0x1BD7

    /// +0x1BD8: Clear force 1 (zeroed each frame).
    pub clear_force_1: i32,                 // VERIFIED

    /// +0x1BDC: Clear force 2 (8 bytes, zeroed each frame).
    pub clear_force_2: [u8; 8],             // VERIFIED

    _pad_1be4: [u8; 0xC],                   // +0x1BE4..+0x1BEF

    /// +0x1BF0: Arena zone ID. Written from zone lookup in ArenaPhysics_CarPhyUpdate.
    pub arena_zone_id: u32,                 // VERIFIED

    _pad_1bf4: [u8; 0x84],                  // +0x1BF4..+0x1C77

    /// +0x1C78: Player index. -1 (0xFF) = no player assigned.
    pub player_index: i8,                   // VERIFIED

    _pad_1c79: [u8; 3],                     // +0x1C79..+0x1C7B

    /// +0x1C7C: Contact physics flags (complex bitfield).
    ///   Bit 2 (0x04): DisableEvents
    ///   Bit 3 (0x08): HasContactThisTick
    ///   Bit 4 (0x10): SubStepCollisionDetected
    ///   Bits 5-7 (0xE0): ContactType
    ///   Bits 9-10 (0x600): Cleared each frame in PhysicsStep_TM
    ///   Bit 11 (0x800): Fragile check flag 1
    ///   Bit 12 (0x1000): Fragile check flag 2
    ///   Bit 16 (0x10000): SubStepCollisionResult
    pub contact_phy_flags: u32,             // VERIFIED

    _pad_1c80: [u8; 0xC],                   // +0x1C80..+0x1C8B

    /// +0x1C8C: Contact threshold (collision severity metric).
    /// Compared against global DAT_141d1ef7c for fragile surface check.
    pub contact_threshold: f32,             // VERIFIED

    /// +0x1C90: Simulation mode.
    ///   0 = Normal, 1 = Replay, 2 = Spectator, 3 = Normal-alt
    pub simulation_mode: i32,               // VERIFIED

    _pad_1c94: [u8; 4],                     // +0x1C94..+0x1C97

    /// +0x1C98: Replay data pointer. Source for memcpy when mode == 1.
    pub replay_data_ptr: u64,               // VERIFIED
}

/// Per-wheel physics block. 184 bytes (0xB8 stride).
/// Wheel order: FL(0), FR(1), RR(2), RL(3).
#[repr(C)]
pub struct WheelPhyBlock {
    /// +0x00: Base value / force model type for this wheel.
    pub base_value: u32,                    // VERIFIED (0x1790 for wheel 0)

    /// +0x04: State word [UNKNOWN].
    pub state: u32,                         // VERIFIED

    _pad_08: [u8; 0x18],                    // +0x08..+0x1F

    /// +0x20: Previous contact/force value.
    pub prev_value: u32,                    // VERIFIED

    /// +0x24: Current contact/force value. Zeroed on reset.
    pub curr_value: u32,                    // VERIFIED

    _pad_28: [u8; 0xC],                     // +0x28..+0x33

    /// +0x34: Timer 1. Zeroed on reset.
    pub timer1: u32,                        // VERIFIED

    /// +0x38: Timer 2 (8 bytes). Zeroed on reset.
    pub timer2: u64,                        // VERIFIED

    _pad_40: [u8; 0x78],                    // +0x40..+0xB7
    // Total: 0xB8 = 184 bytes
}
```

### Vehicle Model Structure (via vehicle+0x88)

```rust
/// Physics model data. Accessed through VehicleState::phy_model_ptr.
/// Contains tuning curves, force model parameters, and speed thresholds.
/// These values are loaded from .Gbx tuning files.
pub struct VehiclePhyModel {
    // +0x238: Game mode or vehicle class identifier.
    //   Checked as (value - 5) unsigned > 1 for reset path.
    pub game_mode_class: i32,               // VERIFIED

    // +0x244: Suspension rest length (used by boost/reactor spring model).
    pub suspension_rest_length: f32,        // VERIFIED (boost_reactor_force.c)

    // +0x260: Spring force curve (CFuncKeysReal pointer).
    pub spring_force_curve: u64,            // VERIFIED (boost_reactor_force.c)

    // +0x2F0: Maximum speed (m/s). Velocity magnitude is clamped to this.
    pub max_speed: f32,                     // VERIFIED

    // +0x308: Speed limit force direction (y-component).
    pub speed_limit_force_y: u32,           // VERIFIED (case0xb)

    // +0x310: Engine force coefficient (airborne mode).
    pub engine_force_airborne: f32,         // VERIFIED

    // +0x314: Engine force coefficient (grounded mode).
    pub engine_force_grounded: f32,         // VERIFIED

    // +0x510: Airborne velocity threshold (squared).
    pub airborne_vel_threshold_sq: f32,     // VERIFIED (airborne_control.c)

    // +0x514: Airborne velocity max threshold (squared).
    pub airborne_vel_max_sq: f32,           // VERIFIED (airborne_control.c)

    // +0x518: Nose-down force curve (CFuncKeysReal).
    pub nosedown_force_curve: u64,          // VERIFIED (airborne_control.c)

    // +0x568: Lateral airborne force curve (CFuncKeysReal).
    pub lateral_air_curve: u64,             // VERIFIED (airborne_control.c)

    // +0x5B8: Airborne damping vs speed curve.
    pub air_damping_curve: u64,             // VERIFIED (airborne_control.c)

    // +0x608: Angular damping base (negated in code).
    pub angular_damping_base: u32,          // VERIFIED (airborne_control.c)

    // +0x60C: Angular damping speed factor.
    pub angular_damping_speed: f32,         // VERIFIED (airborne_control.c)

    // +0x61C: Airborne pitch rate denominator (uint, divided by param_6).
    pub pitch_rate_denom: u32,              // VERIFIED (airborne_control.c)

    // +0x628: Airborne pitch rate numerator.
    pub pitch_rate_numer: f32,              // VERIFIED (airborne_control.c)

    // +0xA54: Friction coefficient source (multiplied with tuning CoefFriction).
    pub friction_base: f32,                 // VERIFIED (case0xb, base_4wheel)

    // +0xAB0: Speed min threshold (for speed limit force).
    pub speed_min: f32,                     // VERIFIED (case0xb, base_4wheel)

    // +0xAB4: Speed max threshold (for speed limit force).
    pub speed_max: f32,                     // VERIFIED (case0xb, base_4wheel)

    // +0xC48: Drift speed threshold (used in case0xb steering logic).
    pub drift_speed_threshold: f32,         // VERIFIED (case0xb)

    // +0xCD4: Air damping reference value.
    pub air_damping_ref: f32,               // VERIFIED (force_model_case5.c)

    // +0xCF0/0xD40: Grip reduction curves (selected by iVar8 from FUN_140850e10).
    pub grip_curve_a: u64,                  // VERIFIED (force_model_case5.c)
    pub grip_curve_b: u64,                  // VERIFIED (force_model_case5.c)

    // +0x1790: Force model type selector (0-6, 0xB).
    pub force_model_type: i32,              // VERIFIED

    // +0x19D0: Engine braking torque.
    pub engine_braking_torque: f32,         // VERIFIED (base_4wheel)

    // +0x1A54: Yaw damping linear term (bicycle model).
    pub yaw_damping_linear: f32,            // VERIFIED (bicycle model)

    // +0x1A58: Yaw damping quadratic term (bicycle model).
    pub yaw_damping_quadratic: f32,         // VERIFIED (bicycle model)

    // +0x1A5C: Lateral stiffness linear (bicycle model).
    pub lateral_stiffness_linear: f32,      // VERIFIED (lateral_grip_2wheel)

    // +0x1A60: Lateral stiffness quadratic (bicycle model).
    pub lateral_stiffness_quadratic: f32,   // VERIFIED (lateral_grip_2wheel)

    // +0x1AC0: Grip limit curve (speed-dependent, bicycle model).
    pub grip_limit_curve: u64,             // VERIFIED (lateral_grip_2wheel)

    // +0x1B10: Drift grip reduction factor (bicycle model).
    pub drift_grip_reduction: f32,          // VERIFIED (lateral_grip_2wheel)

    // +0x1B6C: Drift build rate (bicycle model).
    pub drift_build_rate: f32,              // VERIFIED (bicycle model)

    // +0x1B78: Max drift angle (bicycle model).
    pub max_drift_angle: f32,               // VERIFIED (bicycle model)

    // +0x19E4..+0x19F0: Slope thresholds.
    pub accel_slope_min: f32,               // VERIFIED (slope_gravity_factor)
    pub accel_slope_max: f32,               // VERIFIED
    pub friction_slope_min: f32,            // VERIFIED
    pub friction_slope_max: f32,            // VERIFIED

    // +0x2AE0: Speed low threshold (for grip interpolation in case 6/0xB).
    pub speed_low_threshold: f32,           // VERIFIED

    // +0x2AE4: Speed high threshold.
    pub speed_high_threshold: f32,          // VERIFIED

    // +0x2AFC: Minimum grip value.
    pub min_grip: f32,                      // VERIFIED

    // +0x2B14: Grip reduction factor (case 0xB).
    pub grip_reduction_factor: f32,         // VERIFIED (case0xb)

    // +0x2B18: Use dynamic grip flag (case 0xB).
    pub use_dynamic_grip: i32,              // VERIFIED (case0xb)

    // +0x2B30: Grip vs speed curve (CFuncKeysReal).
    pub grip_speed_curve: u64,              // VERIFIED

    // +0x2B80: Post-respawn force duration (uint, in something - likely ticks).
    pub respawn_force_duration: u32,        // VERIFIED

    // +0x2BF0: Differential torque time threshold.
    pub diff_torque_time: f32,              // VERIFIED (boost_reactor_force.c)

    // +0x2BF4: Differential torque coefficient.
    pub diff_torque_coef: f32,              // VERIFIED (boost_reactor_force.c)

    // +0x2BF8: Differential torque speed range.
    pub diff_torque_speed_range: f32,       // VERIFIED (boost_reactor_force.c)

    // +0x2C1C: Force accumulator selection flag (case 0xB).
    pub force_accum_select: i32,            // VERIFIED (case0xb)

    // +0x30D8: Extended tuning data block (passed to FUN_140841ca0).
    // +0x31A8: Extended tuning data block 2.
}
```

### Openplanet Visual State Mapping

The visual state (`CSceneVehicleVisState`) is a SEPARATE struct from the physics state, populated by `ExtractVisStates` (FUN_1407d5780). For OpenTM, we copy from our physics state to a vis-state struct at the end of each tick for rendering.

| Openplanet Field | Type | Physics Source |
|---|---|---|
| `InputSteer` | f32 | Input system -> vehicle state |
| `InputGasPedal` | f32 | Input system -> vehicle state |
| `InputBrakePedal` | f32 | Input system -> vehicle state |
| `FrontSpeed` | f32 | Computed: dot(velocity, forward_dir) |
| `SideSpeed` | f32 | Computed: dot(velocity, left_dir) |
| `WorldVel` | vec3 | From dynamics body linear velocity |
| `Position` | vec3 | current_transform[9..11] |
| `Dir` / `Left` / `Up` | vec3 | current_transform rotation columns |
| `CurGear` | u32 | Force model internal (cases 5/6/0xB) |
| `RPM` | f32 | Force model internal |
| `IsGroundContact` | bool | Any wheel curr_value != 0 |
| `IsTurbo` | bool | boost_start_time != 0xFFFFFFFF && within duration |
| `TurboTime` | f32 | (current_tick - boost_start_time) / boost_duration |
| `ReactorBoostLvl` | i32 | From surface gameplay effect state |
| `WheelRot` | f32 | Per-wheel accumulator (force model internal) |
| `DamperLen` | f32 | Per-wheel at pfVar15[0] (spring compression) |
| `SlipCoef` | f32 | Per-wheel from force model |
| `SteerAngle` | f32 | From steering model output |

---

## Physics Step Algorithm

### Direct Translation: PhysicsStep_TM (FUN_141501800)

Source: `decompiled/physics/PhysicsStep_TM.c`

```rust
/// PhysicsStep_TM - per-vehicle main physics loop.
/// Called once per 100Hz tick for each vehicle.
///
/// param_1: arena context
/// param_2: dynamics manager (NSceneDyna world)
/// param_3: vehicle array (pointer + count)
/// param_4: tick data [tick_count, ???, delta_time_seconds]
pub fn physics_step_tm(
    arena: &mut ArenaContext,
    dyna_mgr: &mut DynaMgr,
    vehicles: &mut [VehicleState],
    tick: u32,
    dt: f32,  // param_4[2], typically 0.01 for 100Hz
) {
    // Line 63: Convert tick to microseconds (integer arithmetic)
    let time_us: i64 = (tick as u64 * 1_000_000) as i64;

    for vehicle in vehicles.iter_mut() {
        // Line 68: Skip vehicles in state 2 (excluded)
        let status_nibble = vehicle.status_flags & 0xF;
        if status_nibble == 2 {
            continue;
        }

        // Line 69: Clear physics flags bits 9-10
        vehicle.contact_phy_flags &= 0xFFFFF5FF;

        // Line 70: Only process if simulation mode is 0 (normal) or 3 (normal-alt)
        if vehicle.simulation_mode != 0 && vehicle.simulation_mode != 3 {
            // State 1/2 path: just copy current transform to previous
            copy_transform_current_to_previous(vehicle);
            continue;
        }

        // Line 71: Compute velocity-dependent scale factor
        let velocity_scale = compute_velocity_scale(vehicle);
        let scaled_dt = velocity_scale * dt;

        // Lines 72-74: Check if vehicle has a valid dynamics body
        let body_id = vehicle.dyna_body_id;
        if body_id == -1 {
            continue;
        }
        if !dyna_mgr.is_body_active(body_id) {
            copy_transform_current_to_previous(vehicle);
            continue;
        }

        // Lines 75-76: Get vehicle model transform vtable, call setup
        let model = vehicle.get_model();
        model.prepare_transform(&mut vehicle.transform_workspace);

        // Lines 77-116: Compute 4 velocity magnitudes with guarded sqrt
        let body = dyna_mgr.get_body(body_id);
        let v_linear = guarded_magnitude(&body.linear_velocity);
        let v_angular_body = guarded_magnitude(&body.angular_velocity);
        let v_extra1 = guarded_magnitude(&vehicle.velocity_vec1);
        let v_extra2 = guarded_magnitude(&vehicle.velocity_vec2);

        let total_speed = v_linear + v_angular_body + v_extra1 + v_extra2;

        // Lines 121-132: Compute sub-step count
        let body_step_size = body.step_size_param; // lVar15 + 0x54
        let raw_count = ((total_speed * scaled_dt) / body_step_size) as u32;
        let mut num_substeps = raw_count + 1;
        let sub_dt: f32;

        if num_substeps >= 1001 {
            // Cap at 1000
            num_substeps = 1000; // actually 999 iterations + 1 remainder
            sub_dt = dt / 1000.0;
        } else if num_substeps > 1 {
            sub_dt = dt / (num_substeps as f32);
        } else {
            sub_dt = dt; // single step
            num_substeps = 1;
        }

        // Track scaled sub-dt for velocity_scale
        let scaled_sub_dt = velocity_scale * sub_dt;
        let sub_dt_us = (sub_dt as f64 * 1_000_000.0) as i64;
        let mut remaining_time_us = time_us;
        let mut remaining_scaled = scaled_dt;

        // Lines 137-167: Sub-step loop (N-1 equal steps)
        let iterations = if num_substeps > 1 { num_substeps - 1 } else { 0 };
        for _ in 0..iterations {
            remaining_scaled -= scaled_sub_dt;

            // a. Collision detection (line 151)
            let collision_result = collision_check(arena, &vehicle.transform_workspace);
            vehicle.contact_phy_flags |= ((collision_result & 1) as u32) << 16;

            // b. Set dynamics time (line 153)
            dyna_mgr.set_time(remaining_time_us);

            // c. Compute forces (line 155) - dispatches to force model
            compute_forces_dispatch(arena, dyna_mgr, vehicle, remaining_time_us, sub_dt, tick);

            // d. Post-force update (line 157)
            post_force_update(dyna_mgr, vehicle, sub_dt);

            // e. Physics step dispatch (line 159)
            physics_step_dispatch(dyna_mgr, vehicle, tick, sub_dt);

            // f. Integration (line 162)
            integrate(arena, dyna_mgr, vehicle, tick, sub_dt);

            // g. Advance time (line 165)
            remaining_time_us -= sub_dt_us;
        }

        // Lines 169-190: Final step with remainder
        let remainder_dt = if iterations > 0 { remaining_scaled / velocity_scale } else { dt };
        {
            let collision_result = collision_check(arena, &vehicle.transform_workspace);
            vehicle.contact_phy_flags |= ((collision_result & 1) as u32) << 16;
            dyna_mgr.set_time(remaining_time_us);
            compute_forces_dispatch(arena, dyna_mgr, vehicle, remaining_time_us, remainder_dt, tick);
            post_force_update(dyna_mgr, vehicle, remainder_dt);
            physics_step_dispatch(dyna_mgr, vehicle, tick, remainder_dt);
            integrate(arena, dyna_mgr, vehicle, tick, remainder_dt);
        }

        // Lines 191-195: Fragile surface check
        if (vehicle.contact_phy_flags & 0x1800) == 0x1800
            && vehicle.contact_threshold > FRAGILE_THRESHOLD  // DAT_141d1ef7c
            && (status_nibble.wrapping_sub(2) > 1)  // excludes nibble values 2 and 3
        {
            trigger_fragile_break(arena, vehicle, tick);
        }
    }
}
```

### Guarded Square Root

Every sqrt in TM2020's physics is guarded against negative inputs:

```rust
/// Exact reproduction of TM2020's guarded sqrt pattern.
/// Maps to: `if (val < 0.0) FUN_14195dd00(val) else SQRT(val)`
///
/// FUN_14195dd00 is the "safe sqrt" for negative values.
/// Likely returns sqrt(abs(x)) or 0.0. We assume sqrt(abs(x)).
#[inline(always)]
pub fn guarded_sqrt(val: f32) -> f32 {
    if val < 0.0 {
        // APPROXIMATION: TM2020 calls FUN_14195dd00 which is not fully decompiled.
        // Most likely behavior: sqrt(abs(val)) to handle floating-point underflow.
        ((-val).max(0.0)).sqrt()
    } else {
        val.sqrt()  // Maps to wasm f32.sqrt instruction (IEEE 754)
    }
}

/// Compute magnitude of a vec3 with guarded sqrt.
#[inline(always)]
pub fn guarded_magnitude(v: &[f32; 3]) -> f32 {
    let sq = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    guarded_sqrt(sq)
}
```

### Timing System

```rust
/// TM2020 physics timing.
/// Base tick rate: 100Hz (10ms per tick).
/// Internal time unit: microseconds (integer).
/// Time progression: monotonically increasing integer counter.
pub struct PhysicsTiming {
    /// Monotonically increasing step counter (0x7A58 in NSceneDyna world).
    /// Increments by exactly 1 per PhysicsStep_V2 call.
    pub step_counter: u32,

    /// Current tick count (integer, no floating-point accumulation).
    pub current_tick: u32,

    /// Delta time in seconds. Fixed at 0.01 for 100Hz.
    pub dt: f32,
}

impl PhysicsTiming {
    pub const TICK_RATE_HZ: u32 = 100;
    pub const TICK_DT: f32 = 0.01; // 1.0 / 100.0
    pub const TICK_US: i64 = 10_000; // 10ms in microseconds

    /// Convert tick to microseconds (integer multiplication, no float).
    /// Source: PhysicsStep_TM.c line 63
    #[inline(always)]
    pub fn tick_to_microseconds(tick: u32) -> i64 {
        (tick as u64 * 1_000_000) as i64
    }
}
```

---

## Force Model Implementation Strategy

### Overview

| Case | Function | Name | Params | Decompiled? | Fidelity Target |
|---|---|---|---|---|---|
| 0, 1, 2 | FUN_140869cd0 | Base 4-Wheel | 2 | YES (300+ lines) | **Exact match** |
| 3 | FUN_14086b060 | Bicycle (2-Wheel) | 2 | YES (250+ lines) | **Exact match** |
| 4 | FUN_14086bc50 | Case 4 (M5) | 2 | YES (decompiled) | **Exact match** |
| 5 | FUN_140851f00 | CarSport (Stadium) | 3 | YES (500+ lines) | **Exact match** |
| 6 | FUN_14085c9e0 | Extended CarSport | 3 | YES (header + sub-functions) | **Close match** |
| 0xB | FUN_14086d3b0 | Desert/Variant | 3 | YES (300+ lines) | **Close match** |

Sub-functions shared across models 5, 6, and 0xB:

| Function | Purpose | Decompiled? |
|---|---|---|
| FUN_1408570e0 | Per-wheel force | YES (partially, called 4x) |
| FUN_14085ad30 | Steering model | Referenced, not fully decompiled |
| FUN_14085a0d0 | Suspension/contact | Referenced |
| FUN_14085ba50 | Anti-roll bar | Referenced |
| FUN_140858c90 | Damping | Referenced |
| FUN_140857380 | Drift/skid | Referenced |
| FUN_140857b20 | Boost/reactor | YES (234 lines) |
| FUN_14085c1b0 | Airborne control | YES (196 lines) |
| FUN_14085b600 | Final force integration | Referenced |
| FUN_14042bcb0 | Curve sampling | YES (fully decompiled) |
| FUN_1408456b0 | Slope gravity factor | YES (fully decompiled) |
| FUN_140845b60 | Wheel contact surface | YES (fully decompiled) |
| FUN_14086af20 | Lateral grip (2-wheel) | YES (fully decompiled) |
| FUN_14083d8e0 | Steering input processing | YES (decompiled) |

### Cases 0/1/2: Base 4-Wheel Model

**What we know**: Fully decompiled (force_model_4wheel_FUN_140869cd0.c).
- Iterates 4 wheels at stride 0xB8, starting car_state+0x1780
- Per-wheel surface material lookup: `*car_state + 0x6B8 + surface_id * 8`
- Surface ID is byte at wheel_state+0x40
- Force application via FUN_140845210 (force) and FUN_140845260 (torque)
- Speed-dependent coefficients from curve sampling (FUN_14042bcb0)
- Uses car_state[0x2EB] as friction coefficient, car_state[0x2EC] as acceleration coefficient
- Anti-roll bar via cross products
- Speed clamping at tuning offsets 0xAB0, 0xAB4
- Air resistance proportional to v^2
- Engine braking torque at offset 0x19D0

**What we DON'T know**:
- Surface material struct layout beyond offsets +0x18 through +0x50 (7 floats + flags)
- Exact values of the speed-dependent curves (stored in GBX, not binary)
- The vtable function at `*car_state + 0x6B8 + surface_id * 8`

**Implementation**: Direct port from decompiled C. All control flow, offsets, and arithmetic operations are preserved exactly.

**Expected fidelity**: **Exact match** given correct tuning data.

### Case 3: Bicycle (2-Wheel) Model

**What we know**: Fully decompiled (force_model_2wheel_FUN_14086b060.c).
- Single front/rear axis force decomposition
- Steering via atan2 of velocity components
- Drift state machine: 3 states (no drift, building, committed)
  - State at offset+0x1460
  - Slip accumulated at offset+0x1458
  - Drift builds: lateral_slip * drift_rate * dt (tuning+0x1B6C)
  - Max drift angle at tuning+0x1B78
- Lateral grip via FUN_14086af20 (Pacejka-like):
  - `force = -slip * linear_coef - slip*|slip| * quadratic_coef`
  - Grip limit from speed curve at tuning+0x1AC0
  - Drift reduces grip by factor at tuning+0x1B10
- Yaw damping: linear (tuning+0x1A54) + quadratic (tuning+0x1A58)

**What we DON'T know**:
- The exact tuning values (from GBX)
- Which vehicle type uses this model (likely not used for any current TM2020 car)

**Implementation**: Direct port.

**Expected fidelity**: **Exact match**.

### Case 4: TMNF M5 Equivalent

**What we know**: Decompiled (force_model_case4_FUN_14086bc50.c).
- Similar structure to cases 0-2 but different coefficient paths
- Legacy model from TMNF era

**What we DON'T know**:
- Whether any current TM2020 vehicle uses this model

**Implementation**: Direct port.

**Expected fidelity**: **Exact match**.

### Case 5: CarSport / Stadium Full Model

**What we know**: The largest decompilation (force_model_case5.c, 500+ lines). This is the primary Stadium car model.
- Sub-function breakdown matches the CarSport header documentation:
  1. Steering input processing (FUN_14083d8e0)
  2. Grip state interpolation: `(1.0 - car[0x1C44]) / (1.0 - tuning[0xCD4])`
  3. Grip curve selection: FUN_140850e10 selects between tuning+0xCF0 and tuning+0xD40
  4. Per-wheel force (FUN_1408570e0, called for each of `plVar3+0x70` wheels)
  5. Steering model (FUN_14085ad30)
  6. Damping (FUN_140858c90)
  7. Boost/reactor (FUN_140857b20)
  8. Airborne control (FUN_14085c1b0)
  9. Final integration (FUN_14085b600)
- Speed thresholds: tuning+0x2AE0 (low), +0x2AE4 (high)
- Grip state at car_state+0x2B9, minimum at tuning+0x2AFC
- Two steering sensitivity modes: car_state+0x2B1 (normal), car_state+0x158C (custom)
- Selection based on flag at car_state+0x15DC
- Post-respawn force: duration at tuning+0x2B80, linear fade over 2x duration

**What we DON'T know**:
- Full internals of FUN_14085ad30 (steering model) - referenced but not fully decompiled
- Full internals of FUN_14085a0d0 (suspension) - referenced
- Full internals of FUN_14085ba50 (anti-roll) - referenced
- Full internals of FUN_140857380 (drift) - referenced
- Exact gear ratios, RPM curves, engine torque map
- The exact tuning curve data from StadiumCar GBX

**Implementation**: Direct port of the main orchestrator. Sub-functions that are decompiled (boost, airborne, per-wheel, curve sampling) are ported directly. Sub-functions that are only referenced require additional Ghidra decompilation.

**Expected fidelity**: **Close match**. The orchestrator and several key sub-functions are exact. Missing sub-function internals (steering, suspension, anti-roll, drift) need decompilation for exact match.

### Case 6: Extended CarSport (Rally/Snow)

**What we know**: Header comments document the complete sub-function breakdown (identical to case 5 with additions). The decompiled header at force_model_carsport_FUN_14085c9e0.c confirms:
- Same 12-phase pipeline as case 5
- Launched checkpoint boost system at offset+0x15A8
- Checkpoint force curves at checkpoint_data+0x30
- Post-respawn force with 2x duration fade

**What we DON'T know**:
- Which of the sub-functions differ between case 5 and case 6
- Whether Rally and Snow share this model or have separate configurations
- The full decompiled body (only header/comments available)

**Implementation**: Start with case 5 as base. Differences are likely in tuning data, not code structure. If decompilation reveals structural differences, fork.

**Expected fidelity**: **Close match** (same confidence as case 5, plus uncertainty about case-6-specific branches).

### Case 0xB: Desert/Variant Model

**What we know**: Fully decompiled (force_model_case0xB.c, 302 lines). Structural analysis:
- Same sub-function calls as cases 5/6: FUN_1408570e0, FUN_14085ad30, FUN_140858c90, FUN_140857b20, FUN_14085b600
- Additional calls: FUN_14086cc60 (unique to 0xB), FUN_140858e70 (extended steering)
- Speed thresholds at lVar11+0x2AE0/0x2AE4 (same offsets as case 5/6)
- Grip clamping to minimum at lVar11+0x2AFC
- Per-wheel contact state check at plVar3+0x17B4 with stride 0x2E floats
- Post-respawn force using same pattern as case 5/6
- Drift speed threshold at lVar11+0xC48
- 4-wheel contact state output: tracks which wheels have contact at offsets plVar3+0x2FE, +0x315, +0x32C, +0x343

**What we DON'T know**:
- What FUN_14086cc60 does (unique to this model)
- What FUN_140858e70 does (extended steering)
- Full internals of shared sub-functions

**Implementation**: Direct port of orchestrator. Unique sub-functions (FUN_14086cc60, FUN_140858e70) need Ghidra decompilation.

**Expected fidelity**: **Close match**. Orchestrator is exact; unique sub-functions are gaps.

### Curve Sampling (Critical Shared Utility)

The curve sampler FUN_14042bcb0 is called hundreds of times per physics tick and is **fully decompiled**:

```rust
/// CFuncKeysReal curve evaluator.
/// Source: curve_sample_FUN_14042bcb0.c
///
/// Curve format: 20-byte header + array of (time, value) float pairs.
/// Header flags:
///   Bit 0: Step interpolation (nearest previous keyframe)
///   Bit 1: Smooth interpolation (cubic Hermite: 3t^2 - 2t^3)
///   Bit 4: Spline (Catmull-Rom via FUN_14042bba0)
///   Bit 5: Spline sub-flag
///   Default: Linear interpolation
///
/// Values before first keyframe return first value.
/// Values after last keyframe return last value.
/// Epsilon tolerance at DAT_141d1ed34 for near-keyframe snapping.
pub fn sample_curve(curve_ptr: &CurveData, t: f32) -> f32 {
    let num_keys = curve_ptr.num_keys;
    if num_keys == 0 {
        return 0.0;
    }
    if num_keys == 1 {
        return curve_ptr.keys[0].value;
    }

    // Clamp to curve bounds
    if t <= curve_ptr.keys[0].time {
        return curve_ptr.keys[0].value;
    }
    if t >= curve_ptr.keys[num_keys - 1].time {
        return curve_ptr.keys[num_keys - 1].value;
    }

    // Binary search for segment
    let (idx, frac) = find_segment(&curve_ptr.keys, t);

    // Interpolation mode from header flags
    match curve_ptr.interp_mode {
        InterpMode::Step => curve_ptr.keys[idx].value,
        InterpMode::Linear => {
            let a = curve_ptr.keys[idx].value;
            let b = curve_ptr.keys[idx + 1].value;
            a + (b - a) * frac
        }
        InterpMode::SmoothHermite => {
            let a = curve_ptr.keys[idx].value;
            let b = curve_ptr.keys[idx + 1].value;
            let t2 = frac * frac;
            let t3 = t2 * frac;
            let blend = 3.0 * t2 - 2.0 * t3;  // Hermite smoothstep
            a + (b - a) * blend
        }
        InterpMode::Spline => {
            catmull_rom_sample(&curve_ptr.keys, idx, frac)
        }
    }
}
```

---

## Determinism Strategy

### The Core Challenge

TM2020's determinism relies on:
1. Fixed 100Hz integer tick counter (no float accumulation)
2. SSE f32 arithmetic on x86-64 (IEEE 754 compliant)
3. Sequential body processing (no parallelism)
4. Guarded sqrt preventing NaN propagation

For WASM, we must achieve **identical floating-point results across all browsers**.

### WASM Floating-Point Guarantees

**What WASM guarantees (IEEE 754)**:
- `f32.add`, `f32.sub`, `f32.mul`, `f32.div`: **Deterministic**. WASM mandates IEEE 754 single-precision with round-to-nearest-even. These produce identical results across V8, SpiderMonkey, and JavaScriptCore.
- `f32.sqrt`: **Deterministic**. IEEE 754 mandates a correctly rounded result.
- `f32.min`, `f32.max`: **Deterministic** (WASM specifies NaN propagation rules).
- Integer arithmetic: **Deterministic**.

**What WASM does NOT guarantee**:
- `sin`, `cos`, `tan`, `atan2`, `exp`, `log`: These are NOT WASM opcodes. They are implemented via libm in the Rust standard library, which compiles to WASM as software implementations. The Rust `core::f32::sin()` etc. use MUSL libm when targeting WASM, which IS deterministic (pure software, no hardware dependency).
- **NaN bit patterns**: WASM specifies NaN propagation but allows arithmetic NaN to have non-deterministic payload bits. However, `f32.sqrt` of a negative number produces a canonical NaN in WASM (the spec mandates this), so our guarded_sqrt avoids this entirely.

### f32 vs f64 Decision

**TM2020's actual behavior**:
- **Physics computations use f32** (confirmed by decompiled code: `float` type throughout, SSE `sqrtss`/`addss`/`mulss` instructions).
- **Time conversion uses integer arithmetic**: `tick * 1000000` is integer multiply (verified in PhysicsStep_TM.c line 63).
- **Occasional f64 for time sub-step calculation**: `dVar11 = (double)fVar26 * _DAT_141d1fe58` (line 136) - the sub-step time-to-microseconds conversion uses f64 to avoid precision loss.
- **Transform copy is raw bytes**: The 112-byte transform copy is memcpy-equivalent, no float interpretation.

**OpenTM decision**: Use **f32 for all physics math**, matching TM2020. Use **f64 only** for the specific time conversion where TM2020 uses it (sub-dt to microseconds). Use **i64 for tick counters**.

**Implications**: f32 in WASM is IEEE 754 binary32 with round-to-nearest-even, identical to SSE `sqrtss`. Basic arithmetic will match bit-for-bit. The only divergence risk is in transcendental functions (atan2, sin, cos), which we address below.

### Transcendental Function Strategy

TM2020 uses `atan2` (steering angle computation in the bicycle model, FUN_14018d310) and potentially `sin`/`cos`. These map to x87/SSE library functions on x86-64.

**Problem**: WASM's `sin`/`cos`/`atan2` implementations (via MUSL libm) may not produce bit-identical results to MSVC's math library used by TM2020.

**Mitigation**:
1. **Identify all transcendental calls**: From decompiled code, `atan2` is used in the bicycle model (case 3) and airborne control. `sin`/`cos` appear in slope factor computation and steering.
2. **Use a known-deterministic libm**: The `libm` Rust crate (pure Rust, no hardware dependency) produces identical results across all WASM runtimes. We will use this instead of `std::f32::sin` etc.
3. **Document divergence**: Any transcendental that does not match TM2020's MSVC implementation will produce a small error. This is acceptable for non-competitive use. For competitive validation (replay comparison), we would need to match MSVC's specific transcendental implementation.

**KNOWN DIVERGENCE RISK**: The `atan2` and `sin`/`cos` results in our WASM build will likely differ from TM2020 by a few ULP (units in the last place). Over many ticks, this could cause trajectory divergence. Exact replay validation requires either:
- Extracting TM2020's exact libm implementation (from MSVC runtime)
- Using a lookup table approximation tuned to match TM2020's output

### Cross-Runtime Determinism

| Runtime | f32 basic ops | f32.sqrt | Transcendentals (libm) | Overall |
|---|---|---|---|---|
| V8 (Chrome) | Deterministic | Deterministic | Deterministic (same WASM bytecode) | **Identical** |
| SpiderMonkey (Firefox) | Deterministic | Deterministic | Deterministic | **Identical** |
| JavaScriptCore (Safari) | Deterministic | Deterministic | Deterministic | **Identical** |

Since we compile transcendentals to WASM bytecode (not native intrinsics), all runtimes execute the same instruction sequence. **Cross-browser determinism is guaranteed**.

### Sub-Step Ordering Guarantees

TM2020 processes vehicles in array order (PhysicsStep_TM.c lines 66-220). Bodies are processed in sorted index order (PhysicsStep_V2.c lines 103-116). OpenTM must preserve this sequential ordering. No parallel dispatch, no shuffling.

```rust
// CRITICAL: process in array order, never parallelize
for i in 0..vehicle_count {
    physics_step_single_vehicle(&mut vehicles[i], ...);
}
```

---

## Collision System Design

### Architecture Overview

```
Per-Tick Pipeline:
  StartPhyFrame (FUN_1402a9c60)
    -> Copy current positions to previous
    -> Reset acceleration structure
    -> Reset hit body indices to 0xFFFFFFFF

  DynamicCollisionCreateCache (FUN_1407f9da0)
    -> Build 56-byte cache entries per body
    -> Compute collision layer masks
    -> Handle compound shapes (type 0xD)

  Per-Sub-Step:
    -> Collision check (FUN_141501090)
    -> InternalPhysicsStep with constraint solver (FUN_1408025a0)

  Post-Step:
    -> MergeContacts (FUN_1402a8a70)
    -> ProcessContactPoints (FUN_1407d2b90, 7 contact buffers)
```

### Broadphase

**TM2020 approach**: Tree-based spatial acceleration (BVH or k-d tree), inferred from `NHmsCollision::SMgr` namespace and the `DynamicCollisionCreateCache` function which builds per-body AABB entries.

**OpenTM approach**: Uniform spatial hash grid with 32-meter cells (matching TM2020's block size, confirmed by Openplanet rendering plugin: `Math::Ceil(distance / 32.0f)`).

```rust
pub struct SpatialGrid {
    cell_size: f32,         // 32.0 meters
    cells: HashMap<(i32, i32, i32), Vec<BodyIndex>>,
}

impl SpatialGrid {
    pub fn query_aabb(&self, min: Vec3, max: Vec3) -> impl Iterator<Item = BodyIndex> {
        // Return all bodies in overlapping cells
    }
}
```

**APPROXIMATION**: TM2020 likely uses a BVH (more efficient for static geometry). Our grid is simpler but may have different performance characteristics. Physics results are unaffected as long as all overlapping pairs are found.

### Narrowphase

TM2020 uses `NHmsCollision::PointCast_FirstClip/AllClips` for per-wheel raycasts and a constraint-based solver for body-body collision.

**OpenTM approach**: GJK/EPA for convex hull intersection, plus raycasts for wheel-ground contact.

```rust
/// Per-wheel raycast against terrain.
/// Direction: local down (along suspension axis).
/// Max length: suspension rest length + travel.
pub fn wheel_raycast(
    collision_world: &CollisionWorld,
    origin: Vec3,
    direction: Vec3,
    max_dist: f32,
) -> Option<RaycastHit> {
    // Returns: hit position, normal, distance, surface_material_id, surface_gameplay_id
}
```

### Contact Structure (88 bytes)

From MergeContacts decompilation (stride 0x58):

```rust
#[repr(C)]
pub struct ContactPoint {
    _reserved: [u8; 8],        // +0x00
    pub shape_ref: u64,         // +0x08: shape reference pointer
    pub impulse: Vec3,          // +0x10: accumulated impulse
    pub normal: Vec3,           // +0x1C: contact normal
    pub position: Vec3,         // +0x28: contact position
    pub alt_normal: Vec3,       // +0x34: alternate normal
    pub secondary_pos: Vec3,    // +0x40: secondary contact point
    _pad_4c: [u8; 6],          // +0x4C
    pub contact_type: u16,      // +0x52: type (0x0D = compound)
    pub flags: u16,             // +0x54: bit 0 = unknown, bit 1 = has_alternate
    _pad_56: [u8; 2],          // +0x56
}
// Total: 0x58 = 88 bytes
```

### Contact Merging (FUN_1402a8a70)

Direct port from decompiled code (271 lines):

```rust
/// Merge contacts with similar normals and positions.
/// Parameters:
///   normal_dot_threshold: minimum dot product for normals to be "similar"
///   distance_threshold: maximum distance between contact points
///
/// Algorithm:
///   Phase 1: Find merge candidates (O(n^2) pair check)
///     - Skip if distance > threshold
///     - Skip if dot(normal_i, normal_j) < threshold
///     - Skip if either contact type == 1
///   Phase 2: Execute merges
///     - Average position, normal, impulse across group
///     - Normalize averaged normal
///     - Write to survivor contact, clear "needs merge" flag
///   Phase 3: Remove consumed contacts in reverse order
pub fn merge_contacts(
    contacts: &mut Vec<ContactPoint>,
    normal_dot_threshold: f32,
    distance_threshold: f32,
) {
    // ... exact port of NHmsCollision__MergeContacts.c
}
```

### Friction Solver

From FrictionIterCount_Config.c, the solver uses Gauss-Seidel sequential impulses with configurable iteration counts:

```rust
/// NSceneDyna::SSolverParams (44 bytes / 0x2C).
#[repr(C)]
pub struct SolverParams {
    pub friction_static_iter_count: i32,    // +0x00
    pub friction_dyna_iter_count: i32,      // +0x04
    pub velocity_iter_count: i32,           // +0x08
    pub position_iter_count: i32,           // +0x0C
    pub depen_impulse_factor: f32,          // +0x10
    pub max_depen_vel: f32,                 // +0x14
    pub enable_position_constraint: bool,   // +0x18
    _pad_19: [u8; 3],
    pub allowed_pen: f32,                   // +0x1C (negative = auto)
    pub vel_bias_mode: i32,                 // +0x20
    pub use_constraints_2: bool,            // +0x24
    _pad_25: [u8; 3],
    pub min_velocity_for_restitution: f32,  // +0x28
}

/// Sequential impulse constraint solver.
/// Iterates contact constraints to converge on friction and restitution.
pub fn solve_constraints(
    bodies: &mut [RigidBody],
    contacts: &[ContactPoint],
    params: &SolverParams,
    dt: f32,
) {
    // Static friction iterations
    for _ in 0..params.friction_static_iter_count {
        for contact in contacts {
            apply_static_friction_impulse(bodies, contact, dt);
        }
    }

    // Dynamic friction iterations
    for _ in 0..params.friction_dyna_iter_count {
        for contact in contacts {
            apply_dynamic_friction_impulse(bodies, contact, dt);
        }
    }

    // Velocity iterations
    for _ in 0..params.velocity_iter_count {
        for contact in contacts {
            apply_velocity_constraint(bodies, contact, params, dt);
        }
    }

    // Position correction iterations
    if params.enable_position_constraint {
        for _ in 0..params.position_iter_count {
            for contact in contacts {
                apply_position_correction(bodies, contact, params);
            }
        }
    }
}
```

---

## Surface Effect System

### Two-ID System

TM2020 has two independent surface classification systems:

1. **EPlugSurfaceMaterialId** (physical properties): Controls friction coefficients, sound, particles, skid marks. Stored per-material in the material library. Per-wheel `GroundContactMaterial` updated each tick via raycast.

2. **EPlugSurfaceGameplayId** (gameplay triggers): Controls turbo, reset, no-grip, etc. Applied through block/item trigger zones, NOT through materials. All 208 stock materials have `DGameplayId(None)`.

### Complete Gameplay Surface Effects (22 effects)

| ID | Name | Implementation | Constants Needed | Unknown |
|---|---|---|---|---|
| 0 | `NoSteering` | Zero steering input for duration | Duration (from `HandicapNoSteeringDuration`) | Exact duration value |
| 1 | `NoGrip` | Set friction coefficient to 0 via material+0x18 | None (zero is zero) | None - fully understood |
| 2 | `Reset` | Trigger vehicle reset to last checkpoint | None | Reset state restoration details |
| 3 | `ForceAcceleration` | Override gas pedal to 1.0 | Duration | Duration value |
| 4 | `Turbo` | Set boost_duration, boost_strength, boost_start_time=-1 | Duration (ticks), Strength (float) | **Exact values from GBX** |
| 5 | `FreeWheeling` | Zero engine torque contribution | `FreeWheelingDuration` | Duration value |
| 6 | `Turbo2` | Same as Turbo with higher strength | Duration, Strength | **Exact values from GBX** |
| 7 | `ReactorBoost2_Legacy` | Non-directional boost (velocity direction) | Force magnitude, duration | **Exact values from GBX** |
| 8 | `Fragile` | Enable fragile flag; collision severity > threshold = reset | Threshold (`DAT_141d1ef7c`), 250ms delay | **Threshold value from binary** |
| 9 | `NoBrakes` | Zero brake input for duration | Duration | Duration value |
| 10 | `Bouncy` | Set surface restitution to high value | Restitution coefficient | **Exact coefficient** |
| 11 | `Bumper` | Apply impulse on contact | Impulse magnitude, direction | **Exact force from GBX** |
| 12 | `SlowMotion` | Modify `SimulationTimeCoef` | Time scale factor, 250ms delay | **Exact time scale** |
| 13 | `ReactorBoost_Legacy` | Same as ReactorBoost2 but weaker | Force, duration | **Exact values** |
| 14 | `Bumper2` | Enhanced bumper (can be globally disabled via DAT_141faa04c) | Impulse magnitude | **Exact force** |
| 15 | `VehicleTransform_CarRally` | Switch force model + tuning to Rally | Rally tuning GBX data | Rally tuning extraction |
| 16 | `VehicleTransform_CarSnow` | Switch force model + tuning to Snow | Snow tuning GBX data | Snow tuning extraction |
| 17 | `VehicleTransform_CarDesert` | Switch force model + tuning to Desert | Desert tuning GBX data | Desert tuning extraction |
| 18 | `ReactorBoost_Oriented` | Boost in pad's facing direction | Direction from trigger, force, duration | **Exact force from GBX** |
| 19 | `Cruise` | Force vehicle to specific speed | Speed value (-1000 to 1000 from ManiaScript) | Engine force adjustment algorithm |
| 20 | `VehicleTransform_Reset` | Revert to Stadium car | Stadium tuning GBX data | None beyond case 5 model |
| 21 | `ReactorBoost2_Oriented` | Stronger oriented boost | Direction, force, duration | **Exact force from GBX** |

### Material Surface Physics (19 types)

From the NadeoImporter material library:

| Surface ID | Friction Level | Restitution | Notes |
|---|---|---|---|
| `Asphalt` | HIGH | LOW | Default road. RoadTech, PlatformTech |
| `Concrete` | HIGH | LOW | Structural surfaces |
| `Dirt` | MEDIUM | LOW | RoadDirt, off-road |
| `Grass` | LOW | LOW | Natural ground |
| `Green` | LOW | LOW | Vegetation |
| `Ice` | VERY LOW | LOW | PlatformIce |
| `Metal` | MEDIUM | MEDIUM | Technics, pylons |
| `MetalTrans` | N/A (visual only) | N/A | Glass/screens |
| `NotCollidable` | N/A | N/A | Pass-through |
| `Pavement` | MEDIUM-HIGH | LOW | Sidewalks |
| `Plastic` | MEDIUM | HIGH | Inflatables, obstacles |
| `ResonantMetal` | MEDIUM | MEDIUM | Different sound from Metal |
| `RoadIce` | VERY LOW | LOW | RoadIce variant |
| `RoadSynthetic` | HIGH | LOW | RoadBump |
| `Rock` | MEDIUM | LOW | Decorative |
| `Rubber` | HIGH | HIGH | Track borders (bouncy) |
| `Sand` | LOW | LOW | Decorative |
| `Snow` | LOW | LOW | Decorative |
| `Wood` | MEDIUM | MEDIUM | TrackWall |

**UNKNOWN**: The exact friction and restitution coefficient values for each material. These are stored in the material property table accessed via `*car_state + 0x6B8 + surface_id * 8`, which points to a struct with 7 floats at offsets +0x18 through +0x30, plus additional flags. The actual numeric values must be extracted from TM2020's runtime memory or GBX resource files.

### Surface Material Lookup (from decompiled code)

```rust
/// Per-wheel surface property accumulation.
/// Source: wheel_contact_surface_FUN_140845b60.c
///
/// Iterates 4 wheels at stride 0x2E floats (0xB8 bytes).
/// Starting at car_state + 0x17CC.
/// Contact flag at wheel[-6], surface gameplay ID at wheel[-3].
/// Material lookup: *car_state + 0x6B8 + surface_id * 8
pub fn accumulate_wheel_surfaces(
    car_state: &VehicleState,
    material_table: &MaterialTable,
) -> AccumulatedSurfaceProperties {
    let mut accum = AccumulatedSurfaceProperties::default();
    let mut contact_count = 0u32;

    for wheel_idx in 0..4 {
        let wheel_base = 0x17CC / 4 + wheel_idx * 0x2E; // float offset
        let contact_flag = car_state.wheel_floats[wheel_base - 6];

        if contact_flag == 0.0 {
            continue; // No contact on this wheel
        }

        let surface_id = car_state.wheel_bytes[wheel_base - 3] as usize;
        let material = &material_table.entries[surface_id];

        // Accumulate 7 float properties from material+0x18..+0x30
        for i in 0..7 {
            accum.properties[i] += material.properties[i];
        }

        // Positive-only accumulation for boost factors (+0x34, +0x38)
        if material.boost_factor_a > 0.0 {
            accum.boost_a += material.boost_factor_a;
        }
        if material.boost_factor_b > 0.0 {
            accum.boost_b += material.boost_factor_b;
        }

        // AND-accumulate capability bitmask (+0x50)
        accum.capability_mask &= material.capability_mask;

        contact_count += 1;
    }

    // Average by wheel count
    if contact_count > 0 {
        let inv = 1.0 / contact_count as f32;
        for p in &mut accum.properties {
            *p *= inv;
        }
    }

    accum
}
```

---

## Tuning Parameter Loading

### GBX to Physics Pipeline

```
.Gbx file (CPlugVehicleCarPhyTuning, class ID 0x090ED)
  |
  v
GBX Parser (opentm-gbx crate)
  -> Reads chunk-based serialization
  -> Class ID remapping: 0x0A029XXX -> 0x090EDXXX (TMNF compat)
  -> 106+ chunks for vehicle tuning (0x0A029000 - 0x0A029069)
  |
  v
TuningParams struct (Rust)
  -> Spring.FreqHz, Spring.DampingRatio, Spring.Length
  -> DamperCompression, DamperRestStateValue
  -> CollisionDamper, CollisionBounce
  -> Tunings.CoefFriction, Tunings.CoefAcceleration, Tunings.Sensibility
  -> MaxSpeed, GravityCoef
  -> Force model curves (CFuncKeysReal serialized data)
  -> Gear ratios, engine torque curves
  |
  v
VehiclePhyModel (populated at vehicle spawn)
  -> Offsets match decompiled code exactly
  -> Curves deserialized into CurveData structs
```

### Known Tuning Parameters

From TMNF cross-reference and TM2020 string analysis:

| Parameter | TMNF Name | TM2020 Name | Tuning Offset | GBX Source |
|---|---|---|---|---|
| Mass | `Mass` | (via CPlugVehiclePhyModelCustom) | Body property | Vehicle GBX |
| Gravity multiplier | `GravityCoef` (3.0) | `"GravityCoef"` (0x141bb3e18) | Dynamics param | Vehicle GBX |
| Max speed | `MaxSpeed` (277.778 m/s) | model+0x2F0 | +0x2F0 | Vehicle GBX |
| Spring frequency | `AbsorbingValKi` | `"Spring.FreqHz"` (0x141bb3ec0) | Suspension | Vehicle GBX |
| Damping ratio | `AbsorbingValKa` | `"Spring.DampingRatio"` (0x141bb3ed0) | Suspension | Vehicle GBX |
| Spring rest length | `rest=0.2` | `"Spring.Length"` | +0x244 | Vehicle GBX |
| Friction coefficient | (per-surface) | `"Tunings.CoefFriction"` (0x141cb72c8) | NGameSlotPhy+0x58 | Per-player |
| Accel coefficient | (per-surface) | `"Tunings.CoefAcceleration"` (0x141cb72a8) | NGameSlotPhy+0x5C | Per-player |
| Side friction | `SideFriction1=40.0` | Inside force model | Model-specific | Vehicle GBX |
| Brake force | `BrakeBase=1.0` | Inside force model | Model-specific | Vehicle GBX |
| Turbo1 boost | `TurboBoost=5.0` | `+0x16E4` (strength) | Per-effect | Vehicle GBX |
| Turbo1 duration | `TurboDuration=250ms` | `+0x16E0` (ticks) | Per-effect | Vehicle GBX |
| Turbo2 boost | `Turbo2Boost=20.0` | `+0x16E4` (strength) | Per-effect | Vehicle GBX |
| Turbo2 duration | `Turbo2Duration=100ms` | `+0x16E0` (ticks) | Per-effect | Vehicle GBX |
| Water gravity | `WaterGravity=1.0` | NSceneDyna::ComputeWaterForces | Water params | Vehicle GBX |
| Water min speed | `WaterReboundMinHSpeed=200km/h` | Inside water model | Water params | Vehicle GBX |

### Suspension Model Translation

TMNF-to-TM2020 parameter equivalence:

```rust
/// Convert TMNF-style suspension params to TM2020 Spring/Damper.
/// TMNF: F = Ki * (rest - compression) - Ka * velocity
/// TM2020: FreqHz = sqrt(Ki / mass) / (2 * PI)
///         DampingRatio = Ka / (2 * sqrt(Ki * mass))
pub fn tmnf_to_tm2020_suspension(ki: f32, ka: f32, mass: f32) -> (f32, f32) {
    let freq_hz = (ki / mass).sqrt() / (2.0 * std::f32::consts::PI);
    let damping_ratio = ka / (2.0 * (ki * mass).sqrt());
    (freq_hz, damping_ratio)
}
```

### Tuning Coefficient Runtime State

```rust
/// NGameSlotPhy::SMgr (144 bytes / 0x90).
/// Per-player tuning modifier state.
pub struct SlotPhyState {
    _pad_00: [u8; 0x58],
    /// +0x58: Global friction multiplier. Default 1.0.
    /// Modified by ManiaScript SetPlayer_Delayed_AdherenceCoef.
    pub coef_friction: f32,         // VERIFIED
    /// +0x5C: Global acceleration multiplier. Default 1.0.
    /// Modified by ManiaScript SetPlayer_Delayed_AccelCoef.
    pub coef_acceleration: f32,     // VERIFIED
    /// +0x60: Sensibility tuning. [UNKNOWN purpose]
    pub sensibility: f32,           // VERIFIED
    _pad_64: [u8; 0x2C],
}
```

---

## WASM Interface (SharedArrayBuffer)

### Memory Layout

The physics engine communicates with the JavaScript render thread via a SharedArrayBuffer. The layout is designed for lock-free read (render) / write (physics) with double-buffering.

```
SharedArrayBuffer Layout (per vehicle):
Total: 512 bytes per vehicle (aligned to 64 bytes for cache lines)

=== Transform (48 bytes) ===
Offset 0x0000: position.x          (f32)
Offset 0x0004: position.y          (f32)
Offset 0x0008: position.z          (f32)
Offset 0x000C: rotation.x          (f32, quaternion)
Offset 0x0010: rotation.y          (f32, quaternion)
Offset 0x0014: rotation.z          (f32, quaternion)
Offset 0x0018: rotation.w          (f32, quaternion)
Offset 0x001C: velocity.x          (f32, m/s)
Offset 0x0020: velocity.y          (f32, m/s)
Offset 0x0024: velocity.z          (f32, m/s)
Offset 0x0028: angular_vel.x       (f32, rad/s)
Offset 0x002C: angular_vel.y       (f32, rad/s)

=== Speed & Input (16 bytes) ===
Offset 0x0030: front_speed          (f32, m/s, dot(vel, forward))
Offset 0x0034: side_speed           (f32, m/s, dot(vel, left))
Offset 0x0038: input_steer          (f32, -1.0 to 1.0)
Offset 0x003C: input_gas            (f32, 0.0 to 1.0)

=== Per-Wheel State (4 wheels x 32 bytes = 128 bytes) ===
// Wheel 0 (FL):
Offset 0x0040: wheel0_damper_len    (f32, 0.0 to 0.2)
Offset 0x0044: wheel0_rot           (f32, radians, cumulative)
Offset 0x0048: wheel0_rot_speed     (f32, rad/s)
Offset 0x004C: wheel0_steer_angle   (f32, -1.0 to 1.0)
Offset 0x0050: wheel0_surface_id    (u16, ESurfId)
Offset 0x0052: wheel0_ground_contact (u16, 1=touching)
Offset 0x0054: wheel0_slip_coef     (f32, 0.0 to 1.0)
Offset 0x0058: wheel0_dirt          (f32, 0.0 to 1.0)
Offset 0x005C: wheel0_tire_wear     (f32, 0.0 to 1.0)
// Wheel 1 (FR): Offset 0x0060..0x007F (same layout)
// Wheel 2 (RR): Offset 0x0080..0x009F
// Wheel 3 (RL): Offset 0x00A0..0x00BF

=== Engine/Drivetrain (16 bytes) ===
Offset 0x00C0: rpm                  (f32, 0-11000)
Offset 0x00C4: cur_gear             (u32, 0-7)
Offset 0x00C8: engine_on            (u32, bool)
Offset 0x00CC: input_brake          (f32, 0.0 to 1.0)

=== Turbo/Boost (24 bytes) ===
Offset 0x00D0: is_turbo             (u32, bool)
Offset 0x00D4: turbo_time           (f32, 0.0 to 1.0 remaining)
Offset 0x00D8: reactor_boost_lvl    (i32)
Offset 0x00DC: reactor_boost_type   (i32)
Offset 0x00E0: reactor_air_ctrl.x   (f32)
Offset 0x00E4: reactor_air_ctrl.y   (f32)
Offset 0x00E8: reactor_air_ctrl.z   (f32)

=== Contact/Surface State (24 bytes) ===
Offset 0x00EC: is_ground_contact    (u32, bool)
Offset 0x00F0: is_top_contact       (u32, bool)
Offset 0x00F4: ground_dist          (f32, 0-20)
Offset 0x00F8: water_immersion      (f32, 0.0 to 1.0)
Offset 0x00FC: wetness               (f32, 0.0 to 1.0)

=== Race State (16 bytes) ===
Offset 0x0100: race_start_time      (i32, tick)
Offset 0x0104: sim_time_coef        (f32, 0.0 to 1.0)
Offset 0x0108: discontinuity_count  (i32)
Offset 0x010C: falling_state        (u32)

=== Visual Effects (16 bytes) ===
Offset 0x0110: air_brake_normed     (f32, 0.0 to 1.0)
Offset 0x0114: spoiler_open_normed  (f32, 0.0 to 1.0)
Offset 0x0118: wheels_burning       (u32, bool)
Offset 0x011C: cruise_display_speed (i32)

=== Frame Sync (16 bytes) ===
Offset 0x0120: physics_tick         (u32, current tick number)
Offset 0x0124: buffer_index         (u32, 0 or 1 for double-buffer)
Offset 0x0128: flags                (u32, dirty bits)
Offset 0x012C: _reserved            (u32)

=== Direction Vectors (36 bytes) ===
Offset 0x0130: dir.x                (f32, forward)
Offset 0x0134: dir.y                (f32)
Offset 0x0138: dir.z                (f32)
Offset 0x013C: left.x               (f32)
Offset 0x0140: left.y               (f32)
Offset 0x0144: left.z               (f32)
Offset 0x0148: up.x                 (f32)
Offset 0x014C: up.y                 (f32)
Offset 0x0150: up.z                 (f32)

=== Padding to 512 bytes ===
Offset 0x0154..0x01FF: reserved

=== Global State (separate from per-vehicle, at buffer start) ===
Offset 0x0000 (global): current_physics_tick  (u32)
Offset 0x0004 (global): vehicle_count         (u32)
Offset 0x0008 (global): gravity_x             (f32)
Offset 0x000C (global): gravity_y             (f32)
Offset 0x0010 (global): gravity_z             (f32)
Offset 0x0014..0x003F: reserved global state
Per-vehicle data starts at offset 0x0040 + vehicle_index * 512.
```

### Double-Buffering Protocol

```rust
/// Physics thread writes to buffer[write_idx].
/// Render thread reads from buffer[1 - write_idx].
/// Atomics ensure visibility.
pub fn physics_tick_complete(sab: &SharedArrayBuffer, vehicle_idx: usize) {
    let base = GLOBAL_HEADER_SIZE + vehicle_idx * VEHICLE_STRIDE;

    // Write all vehicle state...
    write_vehicle_state(sab, base, &vehicle);

    // Atomic store of tick number (release semantics)
    Atomics::store_u32(sab, base + OFFSET_PHYSICS_TICK, current_tick);

    // Swap buffer index
    let old_idx = Atomics::load_u32(sab, base + OFFSET_BUFFER_INDEX);
    Atomics::store_u32(sab, base + OFFSET_BUFFER_INDEX, 1 - old_idx);
}
```

---

## Test Strategy

### Replay Validation (Gold Standard)

The highest-fidelity test: play a TM2020 ghost replay's inputs through our physics engine and compare the resulting positions frame-by-frame.

```
Input: TM2020 .Replay.Gbx file
  -> Extract input sequence: [(tick, steer, gas, brake), ...]
  -> Extract position checkpoints: [(tick, position, velocity), ...]

Process:
  1. Initialize OpenTM physics with matching map collision geometry
  2. Load matching vehicle tuning GBX
  3. Feed input sequence tick-by-tick
  4. Record output positions

Compare:
  - Position error per tick (should be < 0.001m for close match)
  - Velocity error per tick
  - Cumulative error over full run (should not diverge)
  - Checkpoint time error (should be 0ms for exact match)
```

**Replay state block**: TM2020 copies 2,168 bytes (0x878) of vehicle state for replay. This block can be compared byte-for-byte.

### Unit Tests Per Force Model

```rust
#[cfg(test)]
mod tests {
    /// Test base 4-wheel model (cases 0/1/2):
    /// - Zero velocity -> zero force output
    /// - Constant velocity -> air resistance proportional to v^2
    /// - Surface friction coefficient applied correctly
    /// - Anti-roll bar cross product computation
    #[test]
    fn test_base_4wheel_zero_velocity() { ... }

    /// Test bicycle model (case 3):
    /// - Drift state machine transitions: 0 -> 1 -> 2
    /// - Lateral grip Pacejka model: force = -slip * linear - slip*|slip| * quadratic
    /// - Drift build rate proportional to dt
    #[test]
    fn test_bicycle_drift_state_machine() { ... }

    /// Test curve sampling:
    /// - Linear interpolation between keyframes
    /// - Smooth Hermite (3t^2 - 2t^3)
    /// - Edge cases: before first key, after last key, single key
    /// - Epsilon snapping near keyframes
    #[test]
    fn test_curve_sample_linear() { ... }

    /// Test sub-stepping:
    /// - 1 substep for stationary vehicle
    /// - Cap at 1000 substeps
    /// - Remainder step ensures total simulated time = dt
    /// - Higher speed -> more substeps
    #[test]
    fn test_substep_count_velocity_dependent() { ... }

    /// Test turbo force ramp-up:
    /// - t=0: force = 0
    /// - t=0.5: force = 0.5 * strength * model_scale
    /// - t=1.0: force = strength * model_scale
    /// - Direction: applied along forward axis
    #[test]
    fn test_turbo_ramp_up() { ... }

    /// Test fragile break conditions:
    /// - All three conditions required simultaneously
    /// - Bits 11+12 of contact_phy_flags
    /// - contact_threshold > global threshold
    /// - Status nibble != 2 and != 3
    #[test]
    fn test_fragile_three_conditions() { ... }

    /// Test contact merging:
    /// - Similar normals and positions -> merge
    /// - Averaged position/normal/impulse
    /// - Type 1 contacts excluded from merge
    #[test]
    fn test_contact_merge_similar_normals() { ... }

    /// Test slope gravity factor:
    /// - Flat surface (cos=1.0) -> factor = 1.0
    /// - Vertical surface (cos=0.0) -> factor = 0.0
    /// - Cosine-based S-curve interpolation
    #[test]
    fn test_slope_factor() { ... }
}
```

### Determinism Regression Tests

```rust
/// Run the same input sequence twice and verify bit-identical output.
#[test]
fn test_determinism_identical_runs() {
    let inputs = load_test_input_sequence();
    let result1 = run_simulation(&inputs);
    let result2 = run_simulation(&inputs);

    for tick in 0..result1.len() {
        assert_eq!(
            result1[tick].position.to_bits(),
            result2[tick].position.to_bits(),
            "Position diverged at tick {}",
            tick
        );
    }
}

/// Run in WASM and native, compare results.
/// KNOWN DIVERGENCE: transcendental functions (atan2, sin, cos) may differ.
/// Test only basic arithmetic paths.
#[test]
fn test_cross_platform_basic_arithmetic() {
    // Test that f32 add/mul/div/sqrt produce identical results
    // across native and WASM builds
}
```

### Community Telemetry Comparison

Using Openplanet telemetry recordings from real TM2020 sessions:

```
Input: Telemetry JSON from ~/Documents/Trackmania/Telemetry/
  Contains per-tick: InputSteer, InputGasPedal, InputBrakePedal, Position, Velocity, etc.

Compare:
  - Feed inputs to OpenTM
  - Compare output Position/Velocity against telemetry
  - Measure drift rate (error per second)
  - Identify systematic biases (e.g., consistently faster/slower)
```

---

## Honest Assessment of Unknowns

### Critical Unknowns (Block Implementation)

| Unknown | Impact | Mitigation | Research Action |
|---|---|---|---|
| **Exact tuning values from GBX** (friction coefficients, spring rates, curve keyframes, gear ratios, turbo strength/duration) | **BLOCKS**: Cannot produce correct forces without correct constants | Extract from StadiumCar GBX using gbx-net or custom parser | Parse `\Vehicles\Items\CarSport.Item.gbx` and extract CPlugVehicleCarPhyTuning chunks |
| **Surface material friction table** (the 7-float property struct at material+0x18) | **BLOCKS**: Wheels will have wrong grip on every surface | Dump from runtime memory via Openplanet, or extract from GBX | Write Openplanet plugin to dump `*car_state + 0x6B8 + i*8` for each material ID |
| **Gravity constant** (not found as 9.81 in binary; loaded from GBX) | **BLOCKS**: Vehicle weight/fall speed will be wrong | Use TMNF's `GravityCoef=3.0` as starting point; measure in-game fall time | Extract from GBX resource or measure empirically (drop car, time fall) |

### High-Impact Unknowns (Degrade Quality)

| Unknown | Impact | Mitigation | Research Action |
|---|---|---|---|
| **Steering model internals** (FUN_14085ad30, ~unknown size) | **DEGRADES**: Car will steer with wrong responsiveness | Approximate with TMNF M6 steering model as base | Decompile FUN_14085ad30 in Ghidra |
| **Suspension/contact update** (FUN_14085a0d0) | **DEGRADES**: Wrong suspension behavior, bump response | Port TMNF suspension model (spring+damper, well understood) | Decompile FUN_14085a0d0 in Ghidra |
| **Anti-roll bar** (FUN_14085ba50) | **DEGRADES**: Wrong body roll in corners | Standard anti-roll bar implementation (well-known physics) | Decompile FUN_14085ba50 in Ghidra |
| **Drift/skid model** (FUN_140857380) | **DEGRADES**: Wrong drift initiation and recovery | Use case 3 bicycle drift model as reference for state machine | Decompile FUN_140857380 in Ghidra |
| **Transcendental function precision** (atan2, sin, cos) | **DEGRADES**: Slow trajectory divergence over many ticks | Use MUSL libm (deterministic across WASM runtimes) | Compare MUSL vs MSVC output for critical input ranges |
| **FUN_14195dd00** (safe sqrt for negative inputs) | **DEGRADES**: Edge case behavior for tiny negative values | Assume `sqrt(abs(x))` | Decompile FUN_14195dd00 (likely trivial) |
| **Sleep detection constants** (DAT_141ebccfc/cd00/cd04) | **DEGRADES**: Bodies may not sleep/wake correctly | Set sleep threshold very low (effectively disabled) | Read values from binary at known addresses |

### Medium-Impact Unknowns (Noticeable Differences)

| Unknown | Impact | Mitigation | Research Action |
|---|---|---|---|
| **Water physics internals** (FUN_1407fb580, the actual buoyancy/drag computation) | **NOTICEABLE**: Water handling will feel different | Use standard buoyancy model calibrated to TMNF water params | Decompile FUN_1407fb580 |
| **Collision shape data** (exact mesh/convex hull data per block) | **NOTICEABLE**: Slightly different collision boundaries | Extract collision meshes from block GBX files | Parse CPlugStaticObjectModel collision data |
| **Per-vehicle type force model assignment** (which car uses which case) | **NOTICEABLE**: Wrong physics model for Rally/Snow/Desert | Test empirically by vehicle-transforming in-game and observing behavior | Trace vehicle spawn code to find model_type assignment |
| **Solver iteration counts** (default values for SSolverParams) | **NOTICEABLE**: Different constraint solver convergence | Start with reasonable defaults (4 static, 4 dynamic, 8 velocity, 4 position) | Extract from runtime memory |
| **Cruise control implementation** | **NOTICEABLE**: Wrong speed maintenance behavior | PID controller approximation targeting cruise speed | Decompile cruise force model path |

### Low-Impact Unknowns (Cosmetic / Minor)

| Unknown | Impact | Mitigation | Research Action |
|---|---|---|---|
| **Contact history circular buffer** semantics | **MINOR**: Oscillation detection may differ | Implement as documented (20-entry ring buffer with state transition counting) | Already well-understood from decompilation |
| **Event dispatch timing** (250ms delay for surface effects) | **MINOR**: Effects apply at slightly wrong time | Implement 25-tick delay (250ms at 100Hz) | Confirmed from string analysis |
| **TurboRoulette random selection** | **MINOR**: Wrong randomization of turbo levels | Use PRNG seeded from tick + vehicle ID | Find RNG function in Ghidra |
| **Vehicle-vehicle collision response** (PairComputeForces) | **MINOR**: Multiplayer car-to-car impacts | Port PairComputeForces (already decompiled, prepares state for solver) | Already decompiled |
| **DiscontinuityCount increment** | **COSMETIC**: Visual interpolation on teleport | Increment on checkpoint reset | Already understood |

### What Makes TM2020 Physics FEEL Unique

Based on the decompiled code, these are the critical elements that define the "TM feel" and must be preserved:

1. **Exaggerated gravity** (`GravityCoef=3.0` in TMNF, likely similar in TM2020): The car feels heavy and responsive because gravity is 3x Earth's. This is the single most important tuning parameter.

2. **Turbo ramp-up** (force increases linearly from 0 to max): The boost builds gradually rather than kicking instantly. This creates a distinctive "wave" of acceleration.

3. **Adaptive sub-stepping**: The car maintains stability at high speed because the simulation automatically increases resolution. This prevents the jittery feel of fixed-step engines at extreme velocities.

4. **Per-wheel independent surfaces**: Each wheel detects its own surface independently. Half-on-half-off surface transitions create distinctive handling.

5. **Slope gravity factor**: The cosine-based S-curve that reduces traction on steep slopes creates the distinctive "falling off the wall" feeling when speed drops on loops/wallrides.

6. **Airborne nose-down effect**: The gradual pitch accumulator (vehicle+0x13A4) that pitches the car nose-down when airborne creates the distinctive arc of TM jumps.

7. **Contact-based rather than force-based friction**: The iterative Gauss-Seidel solver with separate static/dynamic friction iterations produces more stable contact than the analytical approach, giving the car its "planted" feel.

8. **Fragile surface 3-condition check**: The severity threshold means gentle landings survive. This creates the tense "will it break?" moments that define fragile gameplay.

---

## Appendix A: Global Constants (from Binary)

| Address | Likely Value | Purpose | Confidence |
|---|---|---|---|
| `DAT_141d1fa9c` | 1000.0f | Max substep count divisor | HIGH (contextual) |
| `_DAT_141d1fe58` | 1000000.0 (double) | Microsecond conversion | HIGH (contextual) |
| `DAT_141d1ed34` | Small epsilon (~1e-7) | Min speed threshold for clamping, zero comparison | MEDIUM |
| `DAT_141d1ef7c` | [UNKNOWN] | Fragile collision severity threshold | UNKNOWN - must extract |
| `DAT_141d1f3c8` | 1.0f | Normal scale / unity constant | HIGH (used as clamp max) |
| `DAT_141d1fd80` | 0.0f or small negative | Floor/minimum clamp value | MEDIUM |
| `DAT_141d1f71c` | 3.6f | m/s to km/h conversion (= 3600/1000) | HIGH (matches physics convention) |
| `DAT_141d1f1ac` | ~0.1f | Small threshold | LOW |
| `DAT_141d21c00` | 0x7FFFFFFF | Absolute value bitmask (clear sign bit) | HIGH (standard IEEE trick) |
| `DAT_141d21c30` | 0x80000000 | Sign flip bitmask (toggle sign bit) | HIGH (standard IEEE trick) |
| `DAT_141ebccfc` | 1 (int) | Sleep detection enabled | MEDIUM |
| `DAT_141ebcd00` | ~0.99f | Sleep velocity damping | MEDIUM |
| `DAT_141ebcd04` | ~0.01 m/s | Sleep velocity threshold | MEDIUM |
| `DAT_141a64350` | 0.0, 0.0 (8 bytes) | Zero vector XY | HIGH |
| `DAT_141a64358` | 0.0f | Zero vector Z | HIGH |

## Appendix B: Function Address Reference

| Address | Name | Purpose | Decompiled? |
|---|---|---|---|
| 0x141501800 | PhysicsStep_TM | Per-vehicle main loop | YES |
| 0x1408427d0 | NSceneVehiclePhy::ComputeForces | Force dispatcher | YES |
| 0x140803920 | NSceneDyna::PhysicsStep_V2 | Rigid body orchestrator | YES |
| 0x1408025a0 | NSceneDyna::InternalPhysicsStep | Constraint solver dispatch | NO |
| 0x1407f89d0 | ComputeGravityAndSleepStateAndNewVels | Gravity + sleep | YES |
| 0x1407f8290 | ComputeWaterForces | Water buoyancy/drag | YES (stub) |
| 0x140869cd0 | Force model cases 0/1/2 | Base 4-wheel | YES |
| 0x14086b060 | Force model case 3 | Bicycle 2-wheel | YES |
| 0x14086bc50 | Force model case 4 | M5 equivalent | YES |
| 0x140851f00 | Force model case 5 | CarSport full | YES |
| 0x14085c9e0 | Force model case 6 | Extended CarSport | YES (header) |
| 0x14086d3b0 | Force model case 0xB | Desert/variant | YES |
| 0x1408570e0 | Per-wheel force | Shared by 5/6/0xB | Partial |
| 0x14085ad30 | Steering model | Shared by 5/6/0xB | NO |
| 0x14085a0d0 | Suspension/contact | Shared by 5/6/0xB | NO |
| 0x14085ba50 | Anti-roll bar | Shared by 5/6/0xB | NO |
| 0x140858c90 | Damping | Shared by 5/6/0xB | NO |
| 0x140857380 | Drift/skid | Shared by 5/6/0xB | NO |
| 0x140857b20 | Boost/reactor force | Shared by 5/6/0xB | YES |
| 0x14085c1b0 | Airborne control | Shared by 5/6/0xB | YES |
| 0x14085b600 | Final force integration | Shared by 5/6/0xB | NO |
| 0x14042bcb0 | Curve sampling | Utility | YES |
| 0x1408456b0 | Slope gravity factor | Utility | YES |
| 0x140845b60 | Wheel contact surface | Utility | YES |
| 0x14086af20 | Lateral grip (2-wheel) | Case 3 helper | YES |
| 0x14083d8e0 | Steering input | Input processing | YES |
| 0x140845210 | Apply force | Thin wrapper | YES |
| 0x140845260 | Apply torque | Thin wrapper | YES |
| 0x1402a9c60 | StartPhyFrame | Collision init | YES |
| 0x1407f9da0 | DynamicCollisionCreateCache | Collision cache | YES |
| 0x1402a8a70 | MergeContacts | Contact merging | YES |
| 0x1407d2b90 | ProcessContactPoints | Contact processing | YES |
| 0x1407f3fc0 | FrictionIterCount_Config | Solver config | YES |
| 0x140842ed0 | PairComputeForces | Vehicle-vehicle | YES |
| 0x1407d2870 | Fragile break handler | Crash/reset | NO |
| 0x14083dca0 | Velocity scale factor | Sub-step calc | NO |

---

## Related Pages

- [Physics Constants](07-physics-constants.md) -- All extracted constants and struct layouts
- [Determinism Analysis](06-determinism-analysis.md) -- WASM float determinism guarantees
- [Tuning Data Extraction](09-tuning-data-extraction.md) -- How to extract GBX tuning files
- [Tuning Loading Analysis](10-tuning-loading-analysis.md) -- GBX to runtime data flow
- [System Architecture](01-system-architecture.md) -- Threading model and SAB layout
- [MVP Tasks](08-mvp-tasks.md) -- Physics task breakdown (MVP-034 through MVP-044)

<details><summary>Document metadata</summary>

- **Version**: 1.0
- **Date**: 2026-03-27
- **Crate**: `opentm-physics`
- **Target**: WASM (wasm32-unknown-unknown), compiled from Rust
- **Goal**: Bit-for-bit reproduction of TM2020 vehicle physics where decompiled code exists; documented approximations elsewhere

</details>

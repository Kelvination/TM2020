# OpenTM MVP Task Breakdown

Load a TM2020 map file, render it in 3D, and drive a car on it with physics. 68 tasks across 10 groups. Estimated timeline: 12 weeks (one developer, full-time).

**Priority framing**: The critical path runs through physics (23 working days). Block mesh extraction (MVP-021) is both on the critical path AND has the highest risk. Any delay there delays the entire project. The renderer and parser chains run in parallel and must converge at MVP-053.

---

## Group 1: Project Setup (Week 1)

### Task ID: MVP-001
**Title**: Initialize monorepo with TypeScript and Vite
**Module**: core
**Depends on**: nothing
**Effort**: 1 day
**Description**: Create the project repository with a pnpm workspace monorepo structure. Set up packages for `@opentm/app` (Vite SPA entry point), `@opentm/gbx` (GBX parser library), `@opentm/renderer` (WebGPU rendering), and `@opentm/physics` (Rust WASM physics). Configure TypeScript strict mode, ESLint, and Prettier across all packages.
**Acceptance**: `pnpm install` succeeds. `pnpm dev` starts a Vite dev server on localhost serving an HTML page that says "OpenTM". Each package compiles with `tsc --noEmit`.
**Unknowns**: None.

---

### Task ID: MVP-002
**Title**: Configure Rust WASM toolchain with wasm-pack
**Module**: physics
**Depends on**: MVP-001
**Effort**: 1 day
**Description**: Add a `crates/physics` Rust crate with `cdylib` target. Install and configure wasm-pack. Create a minimal Rust function (`pub fn ping() -> u32`) that compiles to WASM. Wire the WASM output into the `@opentm/physics` TypeScript package so that importing it loads the module. Verify the Vite dev server can call the Rust function from TypeScript.
**Acceptance**: Browser console logs the return value of the Rust `ping()` function on page load. `wasm-pack build --target web` succeeds without errors.
**Unknowns**: None.

---

### Task ID: MVP-003
**Title**: WebGPU canvas setup with device/adapter initialization
**Module**: renderer
**Depends on**: MVP-001
**Effort**: 1 day
**Description**: In `@opentm/renderer`, create a `GPUContext` class that requests a WebGPU adapter and device, configures a canvas context with `bgra8unorm` format, and clears the canvas to a sky-blue color each frame using `requestAnimationFrame`. Handle the fallback case where WebGPU is unavailable (display an error message).
**Acceptance**: Page shows a solid sky-blue canvas filling the viewport. No WebGPU errors in console. Resize handler updates canvas dimensions correctly.
**Unknowns**: None.

---

### Task ID: MVP-004
**Title**: Dev server with hot reload and WASM rebuild
**Module**: core
**Depends on**: MVP-002, MVP-003
**Effort**: half day
**Description**: Configure Vite to watch for Rust source changes and trigger `wasm-pack build` automatically (via vite-plugin-wasm or a custom plugin). Verify that editing a `.rs` file triggers a WASM rebuild and the browser reloads with the updated module.
**Acceptance**: Change a constant in Rust code, save, and see the updated value in the browser within 5 seconds without a manual refresh.
**Unknowns**: None.

---

### Task ID: MVP-005
**Title**: CI pipeline with build, lint, and test
**Module**: core
**Depends on**: MVP-001, MVP-002
**Effort**: half day
**Description**: Create a GitHub Actions workflow that runs on push to main and on pull requests. Steps: install pnpm, install Rust/wasm-pack, `pnpm install`, `pnpm lint`, `pnpm build` (TypeScript + WASM), `pnpm test` (Vitest). Cache pnpm store and Rust target directory for speed.
**Acceptance**: CI runs green on a commit that passes all checks. A deliberately broken commit (type error) fails CI.
**Unknowns**: None.

---

## Group 2: Math Foundation (Week 1-2)

### Task ID: MVP-006
**Title**: Vec3, Vec4, Mat4, Quat types in Rust
**Module**: physics
**Depends on**: MVP-002
**Effort**: 2 days
**Description**: Implement `Vec3`, `Vec4`, `Mat4` (column-major 4x4), and `Quat` types in the Rust physics crate. Operations needed: add, sub, scale, dot, cross, normalize, length, mat4 multiply, mat4 inverse, mat4 from translation/rotation/scale, quat from axis-angle, quat from Euler angles, quat slerp, quat to mat4, mat4 to quat. Use `f32` throughout. Do NOT use an external math library -- full control over floating-point behavior is needed for determinism.
**Acceptance**: All operations pass unit tests with known reference values. 50+ test cases covering edge cases (zero vector normalize, identity transforms, quat composition).
**Unknowns**: None.

---

### Task ID: MVP-007
**Title**: Iso4 transform type in Rust
**Module**: physics
**Depends on**: MVP-006
**Effort**: 1 day
**Description**: Implement `Iso4` (3x3 rotation matrix + Vec3 position, 48 bytes total, matching TM2020's internal representation documented in doc 10 Section 3.1). Operations: from position + rotation quat, to/from Mat4, transform point, transform direction, inverse, compose two Iso4s. TM2020 uses Y-up left-handed coordinates -- document this in code comments.
**Acceptance**: Unit tests verify round-trip conversion (Iso4 -> Mat4 -> Iso4), composition correctness, and Y-up left-handed convention.
**Unknowns**: None.

---

### Task ID: MVP-008
**Title**: AABB and Ray types in Rust
**Module**: physics
**Depends on**: MVP-006
**Effort**: 1 day
**Description**: Implement `AABB` (axis-aligned bounding box with min/max Vec3) and `Ray` (origin Vec3 + direction Vec3). Operations: AABB-AABB intersection test, Ray-AABB intersection (slab method), AABB expand by point, AABB merge, AABB center/extents, Ray-plane intersection, Ray-triangle intersection (Moller-Trumbore). These are needed for collision broadphase and wheel raycasts.
**Acceptance**: Unit tests cover intersection/miss cases for all combinations. Ray-triangle test verified against known geometric configurations.
**Unknowns**: None.

---

### Task ID: MVP-009
**Title**: TypeScript math bindings and glue
**Module**: renderer
**Depends on**: MVP-006
**Effort**: 1 day
**Description**: Create a `@opentm/math` TypeScript package with Vec3, Vec4, Mat4, and Quat classes mirroring the Rust types. Use `Float32Array` backing for GPU upload compatibility. Include conversion functions to/from WASM linear memory layout so transforms can be shared between JS and Rust without copying.
**Acceptance**: TypeScript math types pass equivalent unit tests to the Rust types. A round-trip test writes a Mat4 to WASM memory from Rust and reads it back correctly in TypeScript.
**Unknowns**: None.

---

## Group 3: GBX Parser (Week 2-4)

### Task ID: MVP-010
**Title**: BinaryReader class with cursor and endianness
**Module**: gbx
**Depends on**: MVP-001
**Effort**: half day
**Description**: Implement a `BinaryReader` class in TypeScript wrapping `DataView` with a cursor position. Methods: `readByte`, `readUint16`, `readInt32`, `readUint32`, `readFloat32`, `readBytes(n)`, `readString(n)` (UTF-8), `skip(n)`, `position` getter/setter, `remaining` getter. All multi-byte reads are little-endian (GBX format is little-endian throughout, per doc 16 Section 12).
**Acceptance**: Unit tests read known byte sequences and produce correct values. Cursor advances correctly after each read.
**Unknowns**: None.

---

### Task ID: MVP-011
**Title**: LZO1X decompression for GBX body
**Module**: gbx
**Depends on**: MVP-010
**Effort**: 1 day
**Description**: Integrate LZO1X decompression for GBX body data. The GBX body uses LZO1X (confirmed in doc 26 from real file analysis, NOT zlib as initially assumed). Options: (a) use an existing npm package like `lzo-wasm` or `minilzo-js`, (b) port miniLZO to TypeScript. The decompressor takes compressed `Uint8Array` and known uncompressed size, returning decompressed `Uint8Array`.
**Acceptance**: Decompress a known compressed GBX body (extract test fixture from a real `.Map.Gbx` file) and verify output matches expected uncompressed bytes.
**Unknowns**: **RISK** -- need to verify which LZO1X JS implementation works correctly. Doc 26 confirmed LZO for body compression; zlib strings in the binary are used for other data.

---

### Task ID: MVP-012
**Title**: GBX header parser (magic, version, format flags)
**Module**: gbx
**Depends on**: MVP-010
**Effort**: half day
**Description**: Parse the GBX header: read magic bytes ("GBX"), version (uint16, expect 6 for TM2020), format flags (4 bytes: B/T, C/U, C/U, R/E for version >= 6), root class ID (uint32), user data size (uint32). Reject non-binary format (byte 0 != 'B'). Reference: doc 16 Sections 1-3.
**Acceptance**: Parse the header of 3+ real `.Map.Gbx` files. Verify class ID is `0x03043000` (CGameCtnChallenge). Verify format flags are "BUCR" or "BUCE". Reject a corrupted file with wrong magic bytes.
**Unknowns**: None.

---

### Task ID: MVP-013
**Title**: Header chunk table parser
**Module**: gbx
**Depends on**: MVP-012
**Effort**: 1 day
**Description**: Parse the header chunk index table: read `num_header_chunks`, then for each chunk read `chunk_id` (uint32) and `chunk_size_raw` (uint32, bit 31 = "heavy" skip flag, bits 0-30 = size). Then read concatenated header chunk data payloads. Build a `Map<number, Uint8Array>` of chunk ID to chunk data. Reference: doc 16 Section 4.
**Acceptance**: Parse header chunks from 3+ map files. Verify known chunk IDs are present (0x03043002, 0x03043003, 0x03043005, 0x03043007, 0x03043008).
**Unknowns**: None.

---

### Task ID: MVP-014
**Title**: LookbackString reader
**Module**: gbx
**Depends on**: MVP-010
**Effort**: 1 day
**Description**: Implement the LookbackString deserialization system. Read a uint32, check the 2-bit flag in bits 30-31: `0b01` (0x40000000) = new inline string (read length-prefixed string, add to table), `0b10` = reference to previous string by index, `0b00` = empty string. TM2020 uses `0b01` exclusively for new strings (confirmed doc 26). Maintain a per-archive string lookup table that resets at the start of each body chunk stream. Reference: doc 16 Section 29 (corrected).
**Acceptance**: Parse LookbackStrings from real GBX body chunk data. Verify block names, author names, and environment strings decode correctly.
**Unknowns**: None -- the 0b01 vs 0b11 ambiguity was resolved in doc 26.

---

### Task ID: MVP-015
**Title**: Class ID registry with legacy remapping
**Module**: gbx
**Depends on**: MVP-010
**Effort**: 1 day
**Description**: Build a class ID registry: a `Map<number, string>` mapping known class IDs to names (e.g., `0x03043000` -> "CGameCtnChallenge"). Include the 200+ legacy-to-modern class ID remappings from doc 16 Section 11. Implement `remapClassId(id: number): number`. Also implement chunk ID to class ID extraction: `classId = chunkId & 0xFFFFF000`.
**Acceptance**: Remap table covers all 200+ entries from doc 16. `remapClassId` correctly translates at least 10 known legacy IDs.
**Unknowns**: None.

---

### Task ID: MVP-016
**Title**: Map header chunks parser (0x03043002, 003, 005, 007, 008)
**Module**: gbx
**Depends on**: MVP-013, MVP-014, MVP-015
**Effort**: 2 days
**Description**: Implement parsers for the 5 known map header chunks. Chunk 0x03043002: map UID, environment, author login. Chunk 0x03043003: map name, author display name, mood, map type, decoration, map size. Chunk 0x03043005: community/title reference. Chunk 0x03043007: thumbnail (JPEG data) and comments. Chunk 0x03043008: author zone path. Each chunk starts with an internal version byte. Use gbx-net source as authoritative reference.
**Acceptance**: Parse all 5 header chunks from 5+ map files. Display map name, author, environment, and thumbnail.
**Unknowns**: None -- these chunks are the best-documented part of the format.

---

### Task ID: MVP-017
**Title**: GBX body decompression and chunk stream parser
**Module**: gbx
**Depends on**: MVP-011, MVP-012, MVP-015
**Effort**: 2 days
**Description**: After parsing the header, read the node count (uint32), then the reference table (doc 16 Section 5). Then handle the body: if format flag byte 2 is 'C', read `uncompressed_size` and `compressed_size`, then decompress LZO1X data. Parse the decompressed body as a chunk stream: repeatedly read `chunk_id` (uint32), check for `0xFACADE01` end sentinel, then read chunk data. For skippable chunks (identified by "SKIP" marker `0x534B4950`), read `chunk_size` and skip. For non-skippable chunks, delegate to the per-chunk parser or throw on unknown.
**Acceptance**: Parse the full body of 3+ map files. Log all encountered chunk IDs. Encounter the `0xFACADE01` sentinel without errors.
**Unknowns**: **RISK** -- non-skippable unknown chunks halt parsing. Start with maps that use well-known chunks.

---

### Task ID: MVP-018
**Title**: Map body chunks: blocks and items (0x03043011, 0x0304301F, 0x03043040)
**Module**: gbx
**Depends on**: MVP-017, MVP-014
**Effort**: 3 days
**Description**: Implement the critical map body chunk parsers. Chunk 0x03043011 (block data): read block count, then per block: block name (LookbackString), direction (byte: 0=N, 1=E, 2=S, 3=W), coordinates (Nat3: 3x uint32), flags (uint32). If `flags == 0xFFFFFFFF`, read additional free block data (Vec3 position, rotation). Chunk 0x0304301F (block data v2): similar structure with version differences. Chunk 0x03043040 (items/anchored objects): read item count, per item: model reference, position, rotation, waypoint property. Use gbx-net source as authoritative reference.
**Acceptance**: Parse blocks and items from 5+ map files. Print block names, positions, and rotations. Verify block count matches gbx-net output.
**Unknowns**: **RISK** -- chunk versions may vary between maps. The gbx-net source handles many version branches.

---

### Task ID: MVP-019
**Title**: GBX parser integration test with real map files
**Module**: gbx
**Depends on**: MVP-018
**Effort**: 1 day
**Description**: Write integration tests that parse 5+ real `.Map.Gbx` files end-to-end. Test files: one simple A01-style map, one complex community map, one with items, one with free blocks, one multilap. Verify header metadata, block counts, and positions within map bounds (0-48 on X/Z for Stadium). Compare output against gbx-net reference snapshots.
**Acceptance**: All 5 test files parse successfully. Block and item counts match reference. Test suite runs in CI.
**Unknowns**: **RISK** -- some community maps may use unhandled chunks.

---

## Group 4: Block System (Week 3-5)

### Task ID: MVP-020
**Title**: Block data model (name, position, rotation, variant)
**Module**: renderer
**Depends on**: MVP-018
**Effort**: 1 day
**Description**: Define TypeScript types for the block system: `BlockDef` (name, dimensions, surface type, waypoint type), `BlockInstance` (def reference, grid coords or free position, direction/rotation, ground/air variant, flags). Implement coordinate conversion from grid to world: `world_x = grid_x * 32.0`, `world_y = grid_y * 8.0`, `world_z = grid_z * 32.0` (doc 28 Section 1.2). Block direction 0-3 maps to 0/90/180/270 degree rotation around Y axis.
**Acceptance**: Given parsed block data, produce `BlockInstance` objects with correct world-space positions and orientations. Unit test: block at grid (10, 9, 10) direction=1 produces world position (320, 72, 320) and 90-degree Y rotation.
**Unknowns**: None.

---

### Task ID: MVP-021
**Title**: Block mesh extraction pipeline (offline tool) **[CRITICAL PATH + HIGHEST RISK]**
**Module**: tools
**Depends on**: nothing (can start in parallel)
**Effort**: 3 days
**Description**: Build a Node.js CLI tool that extracts block meshes from TM2020's game files and converts them to glTF format. Approach: use NadeoImporter to export block meshes as .fbx, then convert to glTF. Alternatively, use gbx-net to read .Block.Gbx and .Item.Gbx files and extract vertex/index data from CPlugSolid2Model. Target: extract the ~50 most common Stadium road blocks. Output: one `.glb` file per block, named to match the block's LookbackString name.
**Acceptance**: 50+ block meshes extracted as `.glb` files. Each loads in a glTF viewer and looks recognizable. Files under 1MB each.
**Unknowns**: **HIGH RISK** -- This is one of the hardest problems (doc 20 Section 17.2). Block mesh data lives in encrypted .pak files. Mitigation: (1) try NadeoImporter first, (2) try GPU mesh cache extraction, (3) as last resort, generate procedural geometry per block type.

---

### Task ID: MVP-022
**Title**: Block mesh registry and loader
**Module**: renderer
**Depends on**: MVP-020, MVP-021
**Effort**: 1 day
**Description**: Build a `BlockMeshRegistry` that maps block names to loaded GPU mesh data. Load pre-extracted `.glb` files from a static asset server. Parse glTF vertex data into WebGPU vertex/index buffers. Handle missing blocks: substitute a colored wireframe cube (32x8x32 meters), logged as a warning.
**Acceptance**: Registry loads 50+ block meshes. Unknown blocks return the fallback wireframe cube. No GPU errors during buffer creation.
**Unknowns**: **RISK** -- glTF vertex attributes must match WebGPU vertex buffer layout.

---

### Task ID: MVP-023
**Title**: Block instancing with transform buffer
**Module**: renderer
**Depends on**: MVP-022, MVP-009
**Effort**: 2 days
**Description**: Implement instanced rendering for blocks. Group all instances of the same block type together. For each group, create a GPU storage buffer containing per-instance Mat4 transforms. Use a single draw call per block type. This is critical for performance: a map can have 1000+ blocks but only ~100 unique types.
**Acceptance**: Render 500+ block instances at 60fps. Draw calls equal roughly the number of unique block types (not instances).
**Unknowns**: None.

---

### Task ID: MVP-024
**Title**: Scene graph with spatial hierarchy
**Module**: renderer
**Depends on**: MVP-009, MVP-023
**Effort**: 2 days
**Description**: Build a simple scene graph: `SceneNode` tree with local transform (Mat4), children, and optional renderable data. Implement frustum culling: each node has a bounding AABB, nodes outside the camera frustum are skipped. Collect visible renderables into a flat array for draw call submission.
**Acceptance**: Frustum culling reduces draw calls by 50%+ when viewing a quarter of a large map. Frame time improves measurably with culling enabled.
**Unknowns**: None.

---

## Group 5: Renderer (Week 4-7)

### Task ID: MVP-025
**Title**: WebGPU forward renderer with basic pipeline
**Module**: renderer
**Depends on**: MVP-003, MVP-009
**Effort**: 2 days
**Description**: Create a forward rendering pipeline: single render pass writing to swap chain color + depth-stencil (depth24plus-stencil8). Vertex buffer layout for block geometry (position f32x3, normal f32x3, uv f32x2 = stride 32 bytes). Basic vertex shader (MVP matrix transform) and fragment shader (Lambertian diffuse). Depth testing, backface culling, triangle list topology.
**Acceptance**: Render a single textured cube with correct perspective, depth testing, and basic lighting.
**Unknowns**: None.

---

### Task ID: MVP-026
**Title**: Render a colored triangle, then a textured block
**Module**: renderer
**Depends on**: MVP-025, MVP-022
**Effort**: 1 day
**Description**: Load one block mesh from the registry, upload to GPU, and render it centered at origin. Apply solid gray material if textures are not yet available. Verify proportions relative to 32x8x32 meter dimensions.
**Acceptance**: A single block renders with correct geometry, lighting, and proportions.
**Unknowns**: None.

---

### Task ID: MVP-027
**Title**: Orbital camera controller
**Module**: renderer
**Depends on**: MVP-025, MVP-009
**Effort**: 1 day
**Description**: Implement orbital camera using the exact math from doc 20 Section 7 (verified from Openplanet): `h = (HAngle + PI/2) * -1`, `v = VAngle`, axis rotated by v around Z then h around Y, `cameraPos = targetPos + axis.xyz * distance`. Mouse drag rotates, scroll wheel adjusts distance, middle-click pans. Clamp VAngle to -85 to +85 degrees.
**Acceptance**: Camera orbits smoothly. Mouse drag, scroll zoom, and pan all work. No gimbal lock.
**Unknowns**: None.

---

### Task ID: MVP-028
**Title**: Grid and axis helper for debugging
**Module**: renderer
**Depends on**: MVP-025
**Effort**: half day
**Description**: Render a ground-plane grid showing the 32m block grid and coordinate axes (red=X, green=Y, blue=Z). Grid covers standard Stadium extent (48x48 blocks = 1536x1536 meters). Grid lines fade at distance. Toggle with G key.
**Acceptance**: Grid is visible, correctly spaced, and fades at distance. Axis arrows at origin.
**Unknowns**: None.

---

### Task ID: MVP-029
**Title**: Basic PBR material system
**Module**: renderer
**Depends on**: MVP-025
**Effort**: 2 days
**Description**: Implement basic PBR material with albedo color/texture, metallic, roughness, and normal map. Cook-Torrance BRDF with GGX normal distribution (matches TM2020's approach per doc 20 Section 3). Support textured and un-textured materials. Default material: gray, roughness 0.5, metallic 0.0.
**Acceptance**: A sphere shows correct metallic/roughness response. Normal mapping produces visible surface detail.
**Unknowns**: None.

---

### Task ID: MVP-030
**Title**: Directional light with basic shadow map (1 cascade)
**Module**: renderer
**Depends on**: MVP-025, MVP-029
**Effort**: 3 days
**Description**: Add directional light (sun). Single-cascade shadow map: render scene from light's perspective into 2048x2048 depth texture, sample during lighting pass. Orthographic projection covering camera's near frustum. PCF 3x3 kernel. Slope-scaled depth bias.
**Acceptance**: Blocks cast shadows onto ground and each other. No major acne or peter-panning.
**Unknowns**: None.

---

### Task ID: MVP-031
**Title**: Texture extraction and loading pipeline
**Module**: tools / renderer
**Depends on**: MVP-021, MVP-029
**Effort**: 2 days
**Description**: Extend block mesh extraction tool to also extract diffuse/albedo textures for each block. Convert to WebP or PNG. Create a texture cache that loads textures by name and creates WebGPU texture + sampler objects. Associate textures with block materials. Fallback: checkerboard pattern for missing textures.
**Acceptance**: 20+ distinct textures loaded. Blocks render with correct textures.
**Unknowns**: **RISK** -- texture data may be in DDS format requiring a decoder.

---

### Task ID: MVP-032
**Title**: Deferred G-buffer pipeline (4 MRT + depth)
**Module**: renderer
**Depends on**: MVP-030, MVP-029
**Effort**: 3 days
**Description**: Upgrade from forward to deferred rendering. G-buffer with 4 render targets: diffuse (rgba8unorm), specular/roughness/metallic (rgba8unorm), world-space normal (rgba16float), emissive/flags (rgba8unorm), plus depth (depth24plus-stencil8). G-buffer fill pass outputs material properties to MRT. Full-screen lighting pass reads G-buffer and computes final color. Follows TM2020's architecture (doc 20 Section 3) but simplified to 4 targets instead of 9.
**Acceptance**: Visual output matches forward renderer. G-buffer textures viewable via debug keys (1-4).
**Unknowns**: None -- WebGPU supports up to 8 color attachments.

---

### Task ID: MVP-033
**Title**: Gamma correction and tone mapping
**Module**: renderer
**Depends on**: MVP-032
**Effort**: 1 day
**Description**: Post-processing pass after deferred lighting. Apply Reinhard or ACES filmic tone mapping. Apply gamma correction (linear to sRGB). Render to swap chain's sRGB surface.
**Acceptance**: Scene looks correctly exposed. Toggle tone mapping to see the difference.
**Unknowns**: None.

---

## Group 6: Physics (Week 5-8)

### Task ID: MVP-034
**Title**: VehicleState struct in Rust
**Module**: physics
**Depends on**: MVP-007
**Effort**: 1 day
**Description**: Define `VehicleState` struct matching Openplanet documentation (doc 20 Section 2, doc 10 Section 3). Fields: position, orientation (Iso4), velocity, angular velocity, front/side speed, input steer/gas/brake, RPM, gear, turbo state, grounded state, per-wheel state (4 wheels: damper_len, wheel_rot, steer_angle, slip_coef, ground_material). Export via wasm-bindgen.
**Acceptance**: Struct compiles, readable from both Rust and TypeScript. All fields serialize correctly across WASM boundary.
**Unknowns**: None.

---

### Task ID: MVP-035
**Title**: Fixed-timestep game loop at 100Hz
**Module**: physics
**Depends on**: MVP-034
**Effort**: 1 day
**Description**: Physics `step(dt_microseconds: u64)` runs one tick. JS side uses `requestAnimationFrame` with fixed-timestep accumulator, calling `step(10_000_000)` (10ms = TM2020's internal unit from doc 10 Section 1.3). Cap at 10 steps per frame. Interpolate render state between previous and current physics state.
**Acceptance**: Physics runs at exactly 100 ticks per second regardless of display refresh rate. Reducing browser frame rate still produces correct physics.
**Unknowns**: None.

---

### Task ID: MVP-036
**Title**: Forward Euler integration with gravity
**Module**: physics
**Depends on**: MVP-035, MVP-006
**Effort**: 1 day
**Description**: Forward Euler integration: `velocity += acceleration * dt`, `position += velocity * dt`, `orientation += angular_velocity * dt` (via quaternion integration). Apply gravity as constant 9.81 m/s^2 downward (-Y). Update vehicle's Iso4 each step.
**Acceptance**: Vehicle at Y=100 falls under gravity. Position at t=1s matches kinematic equation (y = 100 - 0.5 * 9.81 = 95.095m).
**Unknowns**: None.

---

### Task ID: MVP-037
**Title**: Ground plane collision response
**Module**: physics
**Depends on**: MVP-036
**Effort**: 1 day
**Description**: If vehicle Y drops below ground height (Y=72m, standard Stadium terrain from doc 28 Section 1.4), clamp position, zero downward velocity, set `is_grounded = true`. Apply normal force opposing gravity. Temporary placeholder before full map collision.
**Acceptance**: Vehicle falls, lands on ground plane at Y=72, stops bouncing within a few frames. No ground penetration.
**Unknowns**: None.

---

### Task ID: MVP-038
**Title**: Basic steering model (yaw torque)
**Module**: physics
**Depends on**: MVP-037
**Effort**: 2 days
**Description**: When grounded: apply yaw torque proportional to `input_steer * speed * steer_factor`. Speed-dependent steering: `yaw_rate = steer * max_yaw_rate / (1 + speed * speed_sensitivity)`. Apply yaw rotation to orientation quaternion each tick. Compute `front_speed` and `side_speed` via dot products with forward/right directions.
**Acceptance**: Vehicle turns left/right. At low speed, turns are tight. At high speed, turns are wider. Maintains forward momentum during turns.
**Unknowns**: **RISK** -- actual steering uses tire forces and slip angles. Constants need iterative tuning.

---

### Task ID: MVP-039
**Title**: Engine force (throttle) and brake force
**Module**: physics
**Depends on**: MVP-038
**Effort**: 2 days
**Description**: Engine force: `gas * engine_force_max * gear_ratio` along forward axis when grounded. Simple 5-gear system with RPM-based shifting (up at 10000, down at 4000). Brake force: opposing current velocity, proportional to `brake * brake_force_max`. Aerodynamic drag: `drag_force = -drag_coef * speed^2 * velocity_normalized`. Top speed emerges from engine vs drag equilibrium.
**Acceptance**: Vehicle accelerates to ~300 km/h holding gas. Decelerates when braking. Coasts to stop from drag alone. RPM ranges 0-11000.
**Unknowns**: **RISK** -- force constants are guesswork until TMInterface validation. Actual model has 8 gears with complex curves.

---

### Task ID: MVP-040
**Title**: Map collision mesh generation from block data
**Module**: physics
**Depends on**: MVP-018, MVP-022, MVP-008
**Effort**: 3 days
**Description**: Generate collision mesh from loaded map. For each block instance, take glTF geometry and transform by world-space transform. Use top surface and wall triangles (skip decorative geometry). Flat array of triangles with surface IDs. Build BVH for efficient ray and overlap queries. Runs once at map load.
**Acceptance**: Collision mesh generated in under 2 seconds. BVH ray casts return correct hit points and normals. Under 500K triangles. Aligns with rendered geometry.
**Unknowns**: **RISK** -- block meshes may mix decorative and collision geometry. TM2020 separates them internally.

---

### Task ID: MVP-041
**Title**: AABB broadphase collision detection
**Module**: physics
**Depends on**: MVP-040, MVP-034
**Effort**: 2 days
**Description**: Collision detection between vehicle and map. Broadphase: vehicle AABB (~4.6m x 1.5m x 2.0m for CarSport) queries BVH for overlapping triangles. Narrowphase: SAT or GJK test against vehicle collision box. Return contact points with depth, normal, and surface ID.
**Acceptance**: Ground contact detected with correct upward normals. Wall contact with correct wall normals. Broadphase eliminates 95%+ of triangles.
**Unknowns**: None.

---

### Task ID: MVP-042
**Title**: Collision response with friction
**Module**: physics
**Depends on**: MVP-041
**Effort**: 2 days
**Description**: For each contact: (1) resolve penetration along normal, (2) normal impulse to prevent further penetration (restitution ~0 for road, ~0.3 for walls), (3) friction force tangent to surface. Friction coefficient varies by surface ID: asphalt ~1.0, dirt ~0.7, grass ~0.5, ice ~0.1. Use the 19 surface types from doc 28 Section 10.
**Acceptance**: Vehicle drives without falling through road. Slides on ice, grips on asphalt. Bounces off walls. No jittering on slopes.
**Unknowns**: **RISK** -- friction constants are approximations. Use TMInterface for calibration.

---

### Task ID: MVP-043
**Title**: Simplified CarSport force model **[CRITICAL PATH + HIGHEST COMPLEXITY]**
**Module**: physics
**Depends on**: MVP-042, MVP-039
**Effort**: 3 days
**Description**: Replace simplified physics with a more realistic CarSport force model (model 6, FUN_14085c9e0). Implement: 4-wheel suspension raycasts, spring-damper forces per wheel, per-wheel tire force based on slip angle (Pacejka-like: `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`, from doc 10 Section 2.3), engine torque to rear wheels, brake torque to all wheels, anti-roll bar, aerodynamic downforce. The CarSport force model was decompiled at 350+ lines (doc 22 Priority 1) with 9 sub-functions.
**Acceptance**: Vehicle feels roughly like driving in TM2020: responsive steering, controlled drifting at speed, stable on straights. Can complete a lap without falling through road or flying off. A TM2020 player would say "this feels like a rough approximation."
**Unknowns**: **HIGH RISK** -- This is the hardest physics task (doc 20 Section 17.1). Many coefficient values come from .Gbx resource files that cannot be read. Mitigation: (1) TMInterface reference trajectories, (2) iterative tuning, (3) accept "approximately right."

---

### Task ID: MVP-044
**Title**: Turbo/boost force application
**Module**: physics
**Depends on**: MVP-043
**Effort**: 1 day
**Description**: Turbo pad boost: on turbo surface contact, apply timed forward force. Ramps linearly from 0 to `strength * modelScale` over duration (doc 10 Section 4.3). Support Turbo (normal) and Turbo2 (super) with different strength/duration. Track `is_turbo` and `turbo_time` in VehicleState.
**Acceptance**: Turbo pad produces speed boost beyond normal top speed. Turbo expires after correct duration. Turbo1 and Turbo2 differ in magnitude.
**Unknowns**: **RISK** -- decompiled code shows ramp UP, not decay (doc 18 Issue 6). Test both directions.

---

## Group 7: Input (Week 6-8)

### Task ID: MVP-045
**Title**: Keyboard input handler
**Module**: input
**Depends on**: MVP-001
**Effort**: 1 day
**Description**: Keyboard input mapping. Arrow keys: up=gas (digital 0/1), down=brake (digital 0/1), left=steer left (-1), right=steer right (+1). R=respawn, Enter=restart. `InputState` struct: `{ steer: f32, gas: f32, brake: f32, respawn: bool, restart: bool }`. Update on keydown/keyup. Handle simultaneous keys (left+right = 0). Prevent default browser behavior for game keys.
**Acceptance**: Arrow keys update InputState correctly. Left+up produces steer=-1, gas=1. Browser does not scroll on arrow keys.
**Unknowns**: None.

---

### Task ID: MVP-046
**Title**: Gamepad input handler
**Module**: input
**Depends on**: MVP-045
**Effort**: 1 day
**Description**: Gamepad API. Left stick X = steer (analog -1 to 1), right trigger = gas (analog 0-1), left trigger = brake (analog 0-1). Poll each frame via `navigator.getGamepads()`. Deadzone 0.1 on stick axes. Merge with keyboard: use larger absolute value per axis. Handle connect/disconnect.
**Acceptance**: Analog stick steering works with smooth gradation. Triggers produce analog gas/brake. Deadzone prevents drift. Disconnection falls back to keyboard.
**Unknowns**: None.

---

### Task ID: MVP-047
**Title**: Input to physics bridge
**Module**: input / physics
**Depends on**: MVP-046, MVP-034
**Effort**: 1 day
**Description**: Each physics tick, copy current `InputState` into `VehicleState` input fields. If physics runs in Web Worker, use `SharedArrayBuffer` for zero-copy sharing. If on main thread (simpler initial approach), direct function call.
**Acceptance**: Gas key causes acceleration. Steering turns the vehicle. Input latency under 1 frame (16ms).
**Unknowns**: **RISK** -- SharedArrayBuffer requires `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers.

---

### Task ID: MVP-048
**Title**: Input recording buffer
**Module**: input
**Depends on**: MVP-047
**Effort**: 1 day
**Description**: Record input state changes during a race. `InputSample` objects: `{ tick: u32, steer: f32, gas: f32, brake: f32 }`. Delta encoding (record only on change). Methods: `startRecording()`, `stopRecording()`, `getRecording()`. Export as JSON. Foundation for ghost replay.
**Acceptance**: 100-tick drive exports correct input values at correct ticks. 60-second drive produces under 100KB JSON. Replaying inputs produces matching physics output.
**Unknowns**: None.

---

## Group 8: Camera (Week 7-8)

### Task ID: MVP-049
**Title**: Race camera (3rd-person chase)
**Module**: camera
**Depends on**: MVP-027, MVP-034
**Effort**: 2 days
**Description**: Chase camera following the vehicle. Target: ~10m behind, ~4m above in vehicle-local space. Spring-damper system for smooth tracking with configurable stiffness. Look-at point slightly ahead of vehicle. Rotate with vehicle yaw but dampen pitch.
**Acceptance**: Camera follows smoothly during driving. Lags slightly on quick turns. Settles behind vehicle when stopped.
**Unknowns**: **RISK** -- TM2020's actual camera parameters are in VehicleCameraRace2Model.gbx which cannot be parsed. Approximate and tune by feel.

---

### Task ID: MVP-050
**Title**: Free camera for debugging
**Module**: camera
**Depends on**: MVP-027
**Effort**: half day
**Description**: Free-fly camera. WASD movement relative to facing direction, mouse drag for look, Shift for speed, scroll for speed adjustment. Toggle between race/free camera with Tab. Physics continues running in free mode.
**Acceptance**: Smooth movement in all directions. No gimbal lock. Toggle preserves vehicle state.
**Unknowns**: None.

---

### Task ID: MVP-051
**Title**: Camera collision avoidance
**Module**: camera
**Depends on**: MVP-049, MVP-040
**Effort**: 1 day
**Description**: Prevent chase camera from clipping through map geometry. Ray cast from look-at target toward desired camera position. If ray hits geometry, move camera to hit point with normal offset. Smooth transitions entering/exiting collision avoidance.
**Acceptance**: No wall/road clipping. Camera smoothly pulls closer near geometry and returns when clear. No flickering at edges.
**Unknowns**: None.

---

## Group 9: Integration (Week 8-10)

### Task ID: MVP-052
**Title**: Map load pipeline: file to rendered scene
**Module**: integration
**Depends on**: MVP-019, MVP-022, MVP-023, MVP-024, MVP-040
**Effort**: 2 days
**Description**: End-to-end map loading. User drops or selects `.Map.Gbx`. Pipeline: (1) read ArrayBuffer, (2) parse GBX header and body, (3) extract blocks and items, (4) look up mesh per block, create scene node with transform, (5) build collision mesh, (6) build BVH, (7) spawn vehicle at Start waypoint. Show loading progress. Handle errors gracefully.
**Acceptance**: Load 3+ different map files. Each renders correctly. Vehicle spawns at start gate. Loading under 5 seconds. Errors show meaningful messages.
**Unknowns**: **RISK** -- maps referencing unknown block types will use wireframe fallback.

---

### Task ID: MVP-053
**Title**: Connect physics to renderer: vehicle driving on map
**Module**: integration
**Depends on**: MVP-052, MVP-043, MVP-047, MVP-049
**Effort**: 2 days
**Description**: Wire all systems: input -> physics -> renderer. Each frame: (1) poll input, (2) run physics ticks, (3) read vehicle state from WASM, (4) update vehicle scene node from physics transform, (5) update chase camera, (6) cull and render. Render vehicle as simple red box (4.6m x 1.5m x 2.0m) until car model is available.
**Acceptance**: Vehicle drives on map, follows road, hits walls, camera follows. Driving is recognizable as "car racing on a Trackmania map." No desync between physics and rendering.
**Unknowns**: None.

---

### Task ID: MVP-054
**Title**: HUD: speedometer and race timer
**Module**: ui
**Depends on**: MVP-053
**Effort**: 1 day
**Description**: Minimal HUD via HTML/CSS overlay on WebGPU canvas. Speedometer: `FrontSpeed * 3.6` as km/h, bottom-center. Race timer: `MM:SS.mmm` format, top-center. Timer starts on first gas input.
**Acceptance**: Speed shows 0 stationary, 300+ at top speed. Timer starts on gas press. Format is correct. Readable over any map background.
**Unknowns**: None.

---

### Task ID: MVP-055
**Title**: Checkpoint detection system
**Module**: gameplay
**Depends on**: MVP-018, MVP-053
**Effort**: 2 days
**Description**: Detect vehicle passing through checkpoint and finish gates. Identify waypoint blocks (Start, Finish, Checkpoint, StartFinish) via block name matching (doc 28 Section 3.1: names containing "Gate" with waypoint tags). Create trigger volumes per waypoint. Sweep test each tick to prevent tunneling. Enforce ordering (CP N before CP N+1). Support multilap (StartFinish = lap counter).
**Acceptance**: Checkpoint triggers on pass-through. Out-of-order skips do not count. Finish triggers after all checkpoints. Multilap counts laps correctly.
**Unknowns**: **RISK** -- waypoint identification relies on naming conventions. Parse waypoint property from GBX data as fallback.

---

### Task ID: MVP-056
**Title**: Finish detection and race result
**Module**: gameplay
**Depends on**: MVP-055
**Effort**: 1 day
**Description**: On finish (all checkpoints collected), stop timer, display result. Store checkpoint splits. Show result screen: final time, per-checkpoint times, "Restart" button. Reset on restart. Multilap: per-lap times and total.
**Acceptance**: Correct finish time. Checkpoint times recorded. Restart resets everything. Multilap shows laps and total.
**Unknowns**: None.

---

### Task ID: MVP-057
**Title**: Countdown sequence at race start
**Module**: gameplay
**Depends on**: MVP-054, MVP-053
**Effort**: half day
**Description**: 3-2-1-GO countdown. "3" 1s, "2" 1s, "1" 1s, "GO!" 0.5s, then hide. Input locked during countdown. Timer starts at "GO!". Large centered text.
**Acceptance**: Countdown displays correctly. Vehicle locked during countdown. Timer starts at GO.
**Unknowns**: None.

---

### Task ID: MVP-058
**Title**: Respawn/reset to checkpoint
**Module**: gameplay
**Depends on**: MVP-055, MVP-048
**Effort**: 1 day
**Description**: R or Delete resets vehicle to last collected checkpoint. No checkpoint = reset to start. Zero velocity and angular velocity. Face track direction. Timer continues. 0.5s invulnerability after respawn. Increment respawn counter.
**Acceptance**: R teleports to last checkpoint facing correct direction. Velocity zeroed. Timer continues. Multiple respawns work. Pre-checkpoint respawn goes to start.
**Unknowns**: **RISK** -- "facing direction" requires knowing track route direction. Use checkpoint block rotation as proxy.

---

## Group 10: Polish (Week 10-12)

### Task ID: MVP-059
**Title**: Loading screen with progress indication
**Module**: ui
**Depends on**: MVP-052
**Effort**: 1 day
**Description**: Loading screen during map load. Show: map name, author, thumbnail (JPEG from header chunk 0x03043007), progress bar with step labels ("Parsing map...", "Loading block meshes...", "Building collision mesh...", "Ready!"). Fade out on complete.
**Acceptance**: Loading screen appears immediately. Thumbnail displays. Progress bar advances. Fade reveals loaded map.
**Unknowns**: None.

---

### Task ID: MVP-060
**Title**: Map selection UI
**Module**: ui
**Depends on**: MVP-059
**Effort**: 1 day
**Description**: Start screen with file picker. "Open Map File" button for `.Map.Gbx` dialog. Drag-and-drop zone. Recently loaded maps from localStorage. OpenTM logo/title and instructions.
**Acceptance**: File dialog works filtered to `.Map.Gbx`. Drag-and-drop triggers loading. Invalid files show errors.
**Unknowns**: None.

---

### Task ID: MVP-061
**Title**: Bloom post-processing effect
**Module**: renderer
**Depends on**: MVP-033
**Effort**: 2 days
**Description**: HDR bloom. (1) Extract bright pixels (luminance > 1.0), (2) 5-level mip downsample chain, (3) 9-tap Gaussian blur per level, (4) upsample and accumulate, (5) add bloom to tone-mapped scene. Compute shaders. Matches TM2020's 3-level bloom (doc 20 Section 3).
**Acceptance**: Bright areas glow. Intensity controllable. No banding artifacts. Under 2ms at 1080p.
**Unknowns**: None.

---

### Task ID: MVP-062
**Title**: FXAA anti-aliasing
**Module**: renderer
**Depends on**: MVP-033
**Effort**: 1 day
**Description**: FXAA 3.11 as full-screen post-processing after tone mapping. Smooths jagged edges without MSAA cost. Single shader pass.
**Acceptance**: Edges visibly smoother. Toggle shows difference. No HUD blurring. Under 1ms at 1080p.
**Unknowns**: None.

---

### Task ID: MVP-063
**Title**: Sky rendering (gradient + sun disc)
**Module**: renderer
**Depends on**: MVP-032
**Effort**: 1 day
**Description**: Procedural sky via full-screen quad at max depth. Vertical gradient (horizon to zenith) plus sun disc. Colors from map mood: Day (blue/yellow), Sunset (orange/red), Night (dark blue/dim moon). Read mood from parsed header (chunk 0x03043003).
**Acceptance**: Sky renders behind all geometry. Day=blue, Sunset=warm, Night=dark. Sun disc visible. No horizon seams.
**Unknowns**: None.

---

### Task ID: MVP-064
**Title**: Vehicle mesh (CarSport model)
**Module**: renderer
**Depends on**: MVP-021, MVP-053
**Effort**: 2 days
**Description**: Extract or create CarSport 3D model to replace placeholder box. Options: extract from game files, community model, or simplified low-poly. Needs: body mesh, 4 independent wheel meshes (rotating via wheel_rot, steering via steer_angle). Apply vehicle Iso4 transform.
**Acceptance**: Recognizable car (not a box). Wheels rotate when driving. Front wheels turn when steering. Proportions match CarSport (~4.6m long).
**Unknowns**: **RISK** -- actual model is in encrypted pack file. Simplified stand-in may be needed.

---

### Task ID: MVP-065
**Title**: Performance profiling and optimization pass
**Module**: core
**Depends on**: MVP-053, MVP-061
**Effort**: 2 days
**Description**: Profile on mid-range laptop (integrated GPU). Measure: frame time breakdown, draw calls, triangle count, GPU memory, WASM overhead, GC pauses. Fix top 3 bottlenecks. Target: 60fps at 1080p on integrated Intel/AMD GPU.
**Acceptance**: 60fps on M1 MacBook Air or Intel 12th gen integrated. Frame time under 16ms. Performance overlay (P key) shows live stats.
**Unknowns**: **RISK** -- if WebGPU performance is insufficient, reduce rendering quality.

---

### Task ID: MVP-066
**Title**: Settings panel (quality, input, display)
**Module**: ui
**Depends on**: MVP-060, MVP-065
**Effort**: 1 day
**Description**: Settings panel (Escape key toggle). Quality: shadow quality (off/low/high), bloom (on/off), FXAA (on/off), render scale (0.5x/1.0x/1.5x). Input: keyboard bindings, gamepad deadzone. Display: FPS counter, debug grid, collision wireframe. Store in localStorage.
**Acceptance**: All settings work. Render scale changes visually. Settings persist across reloads.
**Unknowns**: None.

---

### Task ID: MVP-067
**Title**: Mobile browser compatibility testing and touch input
**Module**: core / input
**Depends on**: MVP-065
**Effort**: 2 days
**Description**: Test on Chrome Android and Safari iOS. Touch controls: left side = virtual joystick for steering, right side = tap for gas, swipe down for brake. Landscape lock. WebGPU availability check with fallback message. Auto-reduce quality on mobile GPU. WebGPU mobile support is limited as of 2026.
**Acceptance**: Loads on Chrome Android with WebGPU. Touch controls allow basic driving. Landscape enforced. Clear "not supported" message on incompatible browsers.
**Unknowns**: **RISK** -- WebGPU mobile support still rolling out. iOS Safari may have issues. Best-effort, not required.

---

### Task ID: MVP-068
**Title**: End-to-end acceptance testing
**Module**: integration
**Depends on**: all previous tasks
**Effort**: 2 days
**Description**: Final validation on 10+ maps (simple A01 through complex community). Per map verify: (1) loads without errors, (2) blocks in correct positions, (3) vehicle spawns at start, (4) physics feel reasonable, (5) checkpoints trigger, (6) finish completes race, (7) timer correct, (8) restart works, (9) respawn works, (10) camera behaves. Document remaining bugs with severity. Fix critical bugs.
**Acceptance**: 8/10 maps complete a full race without critical bugs. No crashes. A first-time user can load a map and race without instructions.
**Unknowns**: None.

---

## Critical Path

The critical path is the longest dependency chain through the task graph.

### Primary Chain (Physics -- 23 days)

```
MVP-001 (1d) Monorepo setup
  -> MVP-002 (1d) Rust WASM toolchain
    -> MVP-006 (2d) Math types
      -> MVP-007 (1d) Iso4 transform
        -> MVP-034 (1d) VehicleState struct
          -> MVP-035 (1d) Fixed timestep loop
            -> MVP-036 (1d) Euler integration + gravity
              -> MVP-037 (1d) Ground plane collision
                -> MVP-038 (2d) Basic steering
                  -> MVP-039 (2d) Engine/brake forces
                    -> MVP-043 (3d) CarSport force model
                      -> MVP-053 (2d) Connect physics to renderer
                        -> MVP-055 (2d) Checkpoint detection
                          -> MVP-056 (1d) Finish detection
                            -> MVP-068 (2d) Acceptance testing
```

### Parallel Chains (must converge at MVP-053)

**Renderer chain** (12 days):
```
MVP-001 (1d) -> MVP-003 (1d) -> MVP-025 (2d) -> MVP-029 (2d) -> MVP-030 (3d) -> MVP-032 (3d)
```

**Parser chain** (8.5 days):
```
MVP-001 (1d) -> MVP-010 (0.5d) -> MVP-011 (1d) -> MVP-017 (2d) -> MVP-018 (3d) -> MVP-019 (1d)
```

**Block mesh chain** (8 days, starts independently):
```
MVP-021 (3d) -> MVP-022 (1d) -> MVP-023 (2d) -> MVP-024 (2d)
```

### Critical Bottleneck

The collision path merges into physics after MVP-039:
```
MVP-021 (3d) -> MVP-022 (1d) -> MVP-040 (3d) -> MVP-041 (2d) -> MVP-042 (2d) -> MVP-043 (3d)
```

Collision path from start: 3+1+3+2+2+3 = **14 days**. Physics chain to MVP-039 also takes **14 days**. These run neck-and-neck. Any delay in block mesh extraction (MVP-021) directly delays the entire project.

**Realistic timeline**: 23 working days serial critical path + 2-3 days integration buffer = ~5.5 weeks for the core path. With parallel work on renderer, parser, and polish, the full MVP is achievable in **10-12 weeks** for a single developer.

---

## Risk Register

### Risk 1: Block Mesh Extraction Fails
**Probability**: MEDIUM | **Impact**: CRITICAL
Block meshes live in encrypted .pak files. NadeoImporter may not export built-in blocks directly.
**Mitigation**: (1) Try NadeoImporter. (2) Try gbx-net mesh reading. (3) Extract from GPU mesh cache. (4) Last resort: procedural geometry per block type.
**Owner**: MVP-021

### Risk 2: CarSport Physics Feel Wrong
**Probability**: HIGH | **Impact**: HIGH
Force model internals decompiled structurally (350+ lines, 9 sub-functions) but coefficient values come from inaccessible .Gbx resources.
**Mitigation**: (1) TMInterface reference trajectories. (2) Tuning workflow: compare position divergence, adjust constants. (3) TMNF physics docs as starting point. (4) Accept "approximately right."
**Owner**: MVP-043

### Risk 3: GBX Body Parsing Fails on Complex Maps
**Probability**: MEDIUM | **Impact**: MEDIUM
Non-skippable unknown chunks halt the parser. Complex maps may use unhandled features.
**Mitigation**: (1) gbx-net source as reference. (2) "Skip unknown skippable chunk" fallback. (3) Progressive testing. (4) Target 80%+ of simple-to-medium maps.
**Owner**: MVP-017, MVP-018

### Risk 4: LZO Decompression Library Issues
**Probability**: LOW | **Impact**: CRITICAL
GBX body uses LZO1X, not zlib. JS LZO implementations are less common.
**Mitigation**: (1) Test multiple npm packages. (2) Port miniLZO (750 lines C) to Rust WASM as fallback.
**Owner**: MVP-011

### Risk 5: WebGPU Performance Insufficient
**Probability**: LOW | **Impact**: HIGH
1000+ blocks with deferred rendering may exceed integrated GPU budget.
**Mitigation**: (1) Forward rendering fallback. (2) Adaptive quality. (3) Block instancing critical. (4) LOD for distant blocks.
**Owner**: MVP-065

### Risk 6: Turbo Ramp Direction Uncertainty
**Probability**: MEDIUM | **Impact**: LOW
Decompiled code shows ramp UP (doc 10 Section 4.3), contradicting TMNF and intuition.
**Mitigation**: Implement both directions. Use TMInterface to capture actual speed curves. Make configurable.
**Owner**: MVP-044

### Risk 7: Checkpoint Detection Unreliable
**Probability**: MEDIUM | **Impact**: MEDIUM
Relies on gate block identification and trigger volumes. Tunneling at high speed is possible.
**Mitigation**: (1) Conservative trigger volumes. (2) Sweep testing. (3) Parse waypoint properties from GBX data.
**Owner**: MVP-055

### Risk 8: SharedArrayBuffer Header Issues
**Probability**: LOW | **Impact**: MEDIUM
SharedArrayBuffer requires specific HTTP headers that may conflict with third-party resources.
**Mitigation**: (1) Configure headers from day one. (2) Main-thread physics fallback. (3) postMessage fallback (adds 1-2 frames latency).
**Owner**: MVP-047

### Risk 9: Mobile WebGPU Support Gaps
**Probability**: HIGH | **Impact**: LOW (mobile is stretch goal)
WebGPU mobile support still emerging. iOS Safari may have issues.
**Mitigation**: (1) Best-effort, not required. (2) Clear "not supported" message. (3) Consider WebGL2 fallback post-MVP.
**Owner**: MVP-067

### Risk 10: WASM-JS Boundary Overhead
**Probability**: LOW | **Impact**: MEDIUM
Serializing large structures across WASM boundary could exceed 10ms tick budget.
**Mitigation**: (1) SharedArrayBuffer for zero-copy. (2) Minimal interface: pointers to shared memory. (3) Batch physics ticks. (4) Profile early.
**Owner**: MVP-035, MVP-047

---

## Related Pages

- [20-browser-recreation-guide.md](../re/20-browser-recreation-guide.md) -- Full browser recreation feasibility guide
- [04-asset-pipeline.md](04-asset-pipeline.md) -- Asset pipeline design
- [10-physics-deep-dive.md](../re/10-physics-deep-dive.md) -- Physics pipeline decompilation
- [16-fileformat-deep-dive.md](../re/16-fileformat-deep-dive.md) -- GBX file format specification

<details>
<summary>Analysis metadata</summary>

**Date**: 2026-03-27
**MVP Definition**: Load a TM2020 map file, render it in 3D, and drive a car on it with physics.
**Estimated timeline**: 12 weeks (one developer, full-time)
**Total tasks**: 68

</details>

# OpenTM MVP Task Breakdown

**Date**: 2026-03-27
**MVP Definition**: Load a TM2020 map file, render it in 3D, and drive a car on it with physics.
**Estimated timeline**: 12 weeks (one developer, full-time)
**Total tasks**: 68

---

## Table of Contents

1. [Group 1: Project Setup (Week 1)](#group-1-project-setup-week-1)
2. [Group 2: Math Foundation (Week 1-2)](#group-2-math-foundation-week-1-2)
3. [Group 3: GBX Parser (Week 2-4)](#group-3-gbx-parser-week-2-4)
4. [Group 4: Block System (Week 3-5)](#group-4-block-system-week-3-5)
5. [Group 5: Renderer (Week 4-7)](#group-5-renderer-week-4-7)
6. [Group 6: Physics (Week 5-8)](#group-6-physics-week-5-8)
7. [Group 7: Input (Week 6-8)](#group-7-input-week-6-8)
8. [Group 8: Camera (Week 7-8)](#group-8-camera-week-7-8)
9. [Group 9: Integration (Week 8-10)](#group-9-integration-week-8-10)
10. [Group 10: Polish (Week 10-12)](#group-10-polish-week-10-12)
11. [Critical Path](#critical-path)
12. [Risk Register](#risk-register)

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
**Description**: Configure Vite to watch for Rust source changes and trigger `wasm-pack build` automatically (via vite-plugin-wasm or a custom plugin). Verify that editing a `.rs` file triggers a WASM rebuild and the browser reloads with the updated module. TypeScript hot module replacement should already work via Vite defaults.
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
**Description**: Implement `Vec3`, `Vec4`, `Mat4` (column-major 4x4), and `Quat` types in the Rust physics crate. Operations needed: add, sub, scale, dot, cross, normalize, length, mat4 multiply, mat4 inverse, mat4 from translation/rotation/scale, quat from axis-angle, quat from Euler angles, quat slerp, quat to mat4, mat4 to quat. Use `f32` throughout. Do NOT use an external math library -- we need full control over floating-point behavior for determinism.
**Acceptance**: All operations pass unit tests with known reference values. 50+ test cases covering edge cases (zero vector normalize, identity transforms, quat composition).
**Unknowns**: None.

---

### Task ID: MVP-007
**Title**: Iso4 transform type in Rust
**Module**: physics
**Depends on**: MVP-006
**Effort**: 1 day
**Description**: Implement `Iso4` (3x3 rotation matrix + Vec3 position, 48 bytes total, matching TM2020's internal representation documented in doc 10 Section 3.1). Operations: from position + rotation quat, to/from Mat4, transform point, transform direction, inverse, compose two Iso4s. TM2020 uses Y-up left-handed coordinates -- document this in code comments.
**Acceptance**: Unit tests verify round-trip conversion (Iso4 -> Mat4 -> Iso4), composition correctness, and that the Y-up left-handed convention is maintained. Transform of known points produces expected output.
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
**Description**: Create a `@opentm/math` TypeScript package with Vec3, Vec4, Mat4, and Quat classes that mirror the Rust types. These are used on the rendering/JS side (camera, scene graph, UI coordinates). Use `Float32Array` backing for GPU upload compatibility. Include conversion functions to/from the WASM linear memory layout so transforms can be shared between JS and Rust without copying (read directly from WASM memory via `Float32Array` view).
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
**Description**: Integrate LZO1X decompression for GBX body data. The GBX body is compressed with LZO1X (confirmed in doc 26 from real file analysis, NOT zlib as initially assumed from binary strings). Options: (a) use an existing npm package like `lzo-wasm` or `minilzo-js`, (b) port miniLZO to TypeScript. The decompressor takes a compressed `Uint8Array` and a known uncompressed size, returning the decompressed `Uint8Array`.
**Acceptance**: Decompress a known compressed GBX body (extract test fixture from a real `.Map.Gbx` file) and verify the output matches the expected uncompressed bytes. Decompression of the body from `A01-Race.Map.Gbx` (or any available map) succeeds without error.
**Unknowns**: **RISK** -- need to verify which LZO1X JS implementation works correctly. The doc 26 analysis confirmed LZO for body compression; zlib strings in the binary are used for other data (lightmap/ghost).

---

### Task ID: MVP-012
**Title**: GBX header parser (magic, version, format flags)
**Module**: gbx
**Depends on**: MVP-010
**Effort**: half day
**Description**: Parse the GBX header: read magic bytes ("GBX"), version (uint16, expect 6 for TM2020), format flags (4 bytes: B/T, C/U, C/U, R/E for version >= 6), root class ID (uint32), user data size (uint32). Reject non-binary format (byte 0 != 'B'). Store parsed header in a `GbxHeader` type. Reference: doc 16 Sections 1-3, byte-exact specification verified against 5 real files.
**Acceptance**: Parse the header of 3+ real `.Map.Gbx` files. Verify class ID is `0x03043000` (CGameCtnChallenge). Verify format flags are "BUCR" or "BUCE". Reject a corrupted file with wrong magic bytes.
**Unknowns**: None.

---

### Task ID: MVP-013
**Title**: Header chunk table parser
**Module**: gbx
**Depends on**: MVP-012
**Effort**: 1 day
**Description**: Parse the header chunk index table: read `num_header_chunks`, then for each chunk read `chunk_id` (uint32) and `chunk_size_raw` (uint32, bit 31 = "heavy" skip flag, bits 0-30 = size). Then read concatenated header chunk data payloads. Build a `Map<number, Uint8Array>` of chunk ID to chunk data. Reference: doc 16 Section 4.
**Acceptance**: Parse header chunks from 3+ map files. Verify known chunk IDs are present (0x03043002, 0x03043003, 0x03043005, 0x03043007, 0x03043008). Chunk data sizes match the declared sizes.
**Unknowns**: None.

---

### Task ID: MVP-014
**Title**: LookbackString reader
**Module**: gbx
**Depends on**: MVP-010
**Effort**: 1 day
**Description**: Implement the LookbackString deserialization system. Read a uint32, check the 2-bit flag in bits 30-31: `0b01` (0x40000000) = new inline string (read length-prefixed string, add to table), `0b10` = reference to previous string by index, `0b00` = empty string. TM2020 uses `0b01` exclusively for new strings (confirmed doc 26). Maintain a per-archive string lookup table that resets at the start of each body chunk stream. Reference: doc 16 Section 29 (corrected).
**Acceptance**: Parse LookbackStrings from real GBX body chunk data. Verify block names, author names, and environment strings are decoded correctly. String table references resolve to previously-seen strings.
**Unknowns**: None -- the 0b01 vs 0b11 ambiguity was resolved in doc 26.

---

### Task ID: MVP-015
**Title**: Class ID registry with legacy remapping
**Module**: gbx
**Depends on**: MVP-010
**Effort**: 1 day
**Description**: Build a class ID registry: a `Map<number, string>` mapping known class IDs to their names (e.g., `0x03043000` -> "CGameCtnChallenge"). Include the 200+ legacy-to-modern class ID remappings from doc 16 Section 11 (e.g., old ManiaPlanet-era IDs that must be translated to TM2020 IDs). Implement `remapClassId(id: number): number` that applies the remapping table. Also implement chunk ID to class ID extraction: `classId = chunkId & 0xFFFFF000`.
**Acceptance**: Remap table covers all 200+ entries from doc 16. `remapClassId` correctly translates at least 10 known legacy IDs. Chunk ID `0x03043011` correctly maps to class `0x03043000`.
**Unknowns**: None.

---

### Task ID: MVP-016
**Title**: Map header chunks parser (0x03043002, 003, 005, 007, 008)
**Module**: gbx
**Depends on**: MVP-013, MVP-014, MVP-015
**Effort**: 2 days
**Description**: Implement parsers for the 5 known map header chunks. Chunk 0x03043002: map UID, environment name, author login. Chunk 0x03043003: map name, author display name, time of day mood, map type, decoration environment, map size. Chunk 0x03043005: community/title reference. Chunk 0x03043007: thumbnail (JPEG data) and comments string. Chunk 0x03043008: author zone path and extra info. Each chunk starts with an internal version byte. Use gbx-net source code as the authoritative reference for field order and version handling. Reference: doc 16 Section 4, doc 28 Section 7.
**Acceptance**: Parse all 5 header chunks from 5+ map files. Display map name, author name, environment, and thumbnail. Verify extracted metadata matches the map info shown in-game (compare against Openplanet output or GBX.NET Explorer).
**Unknowns**: None -- these chunks are the best-documented part of the format.

---

### Task ID: MVP-017
**Title**: GBX body decompression and chunk stream parser
**Module**: gbx
**Depends on**: MVP-011, MVP-012, MVP-015
**Effort**: 2 days
**Description**: After parsing the header, read the node count (uint32), then the reference table (doc 16 Section 5: external ref count, ancestor folders, ref entries). Then handle the body: if format flag byte 2 is 'C', read `uncompressed_size` (uint32) and `compressed_size` (uint32), then decompress `compressed_size` bytes of LZO1X data. Parse the decompressed body as a chunk stream: repeatedly read `chunk_id` (uint32), check for `0xFACADE01` end sentinel, then read chunk data. For skippable chunks (identified by "SKIP" marker `0x534B4950` after chunk ID), read `chunk_size` and skip. For non-skippable chunks, delegate to the per-chunk parser or throw on unknown.
**Acceptance**: Parse the full body of 3+ map files. Log all encountered chunk IDs. Encounter the `0xFACADE01` sentinel without errors. Count of chunks matches expectations (compare against gbx-net output for the same file).
**Unknowns**: **RISK** -- non-skippable unknown chunks will halt parsing. Mitigation: start with maps that use only well-known chunks. The community gbx-net codebase documents which chunks are skippable.

---

### Task ID: MVP-018
**Title**: Map body chunks: blocks and items (0x03043011, 0x0304301F, 0x03043040)
**Module**: gbx
**Depends on**: MVP-017, MVP-014
**Effort**: 3 days
**Description**: Implement the critical map body chunk parsers. Chunk 0x03043011 (block data): read block count, then per block: block name (LookbackString), direction (byte: 0=N, 1=E, 2=S, 3=W), coordinates (Nat3: 3x uint32), flags (uint32). If `flags == 0xFFFFFFFF`, read additional free block data (Vec3 position, rotation). Chunk 0x0304301F (block data v2, commonly used): similar structure with version differences. Chunk 0x03043040 (items/anchored objects): read item count, then per item: model reference (LookbackString), position (Vec3), rotation (Vec3 Euler or Quat), waypoint property. Build arrays of `BlockPlacement` and `ItemPlacement` structs. Reference: doc 28 Section 2.4, doc 28 Section 4.2. Use gbx-net source as the authoritative reference for version-specific field layouts.
**Acceptance**: Parse blocks and items from 5+ map files. Print block names, positions, and rotations. Verify block count matches gbx-net output for the same file. Verify at least one known block name appears (e.g., "StadiumRoadMainStraight"). Items parse without error on maps that contain placed items.
**Unknowns**: **RISK** -- chunk versions may vary between maps. The gbx-net source handles many version branches. Need to handle the "must read all intervening chunks in order" constraint for non-skippable chunks between 0x03043011 and 0x0304301F.

---

### Task ID: MVP-019
**Title**: GBX parser integration test with real map files
**Module**: gbx
**Depends on**: MVP-018
**Effort**: 1 day
**Description**: Write integration tests that parse 5+ real `.Map.Gbx` files end-to-end (header through body). Test files should include: one simple A01-style map, one complex community map with many blocks, one map with items, one map with free blocks, one multilap map. For each, verify: header metadata is correct, block count > 0, all blocks have valid names and positions within map bounds (0-48 on X/Z for Stadium), no parsing errors. Compare output against a reference snapshot generated by running gbx-net on the same files.
**Acceptance**: All 5 test files parse successfully. Block and item counts match the reference. No uncaught exceptions. Test suite runs in CI.
**Unknowns**: **RISK** -- some community maps may use chunks or features not yet handled. Accept partial parsing for edge cases; log warnings for skipped unknown chunks.

---

## Group 4: Block System (Week 3-5)

### Task ID: MVP-020
**Title**: Block data model (name, position, rotation, variant)
**Module**: renderer
**Depends on**: MVP-018
**Effort**: 1 day
**Description**: Define TypeScript types for the block system: `BlockDef` (name, dimensions, surface type, waypoint type), `BlockInstance` (def reference, grid coords or free position, direction/rotation, ground/air variant, flags). Implement the coordinate conversion from grid coords to world position: `world_x = grid_x * 32.0`, `world_y = grid_y * 8.0`, `world_z = grid_z * 32.0` (doc 28 Section 1.2). Implement block rotation: direction 0-3 maps to 0/90/180/270 degree rotation around Y axis. For free blocks, apply the full position + rotation transform.
**Acceptance**: Given parsed block data from MVP-018, produce a list of `BlockInstance` objects with correct world-space positions and orientations. Unit test: a block at grid (10, 9, 10) with direction=1 produces world position (320, 72, 320) and 90-degree Y rotation.
**Unknowns**: None.

---

### Task ID: MVP-021
**Title**: Block mesh extraction pipeline (offline tool)
**Module**: tools
**Depends on**: nothing (can start in parallel)
**Effort**: 3 days
**Description**: Build a Node.js CLI tool that extracts block meshes from TM2020's game files and converts them to glTF format. Approach: use NadeoImporter (Nadeo's official tool, documented at doc.trackmania.com/nadeoimporter) to export block meshes as .fbx, then convert to glTF using a converter. Alternatively, use gbx-net to read .Block.Gbx and .Item.Gbx files from the game's pack files and extract vertex/index data from CPlugSolid2Model. Target: extract the ~50 most common Stadium road blocks (StadiumRoadMainStraight, Curve, Slope, etc.), platforms, and gate blocks. Output: one `.glb` file per block, named to match the block's LookbackString name.
**Acceptance**: 50+ block meshes extracted as `.glb` files. Each can be loaded in a glTF viewer (e.g., https://gltf-viewer.donmccurdy.com/) and looks recognizable. Road surfaces, walls, and basic geometry are present. Files are under 1MB each.
**Unknowns**: **HIGH RISK** -- This is one of the hardest problems (doc 20 Section 17.2). Block mesh data lives in encrypted .pak files. NadeoImporter can export items but may not export built-in blocks directly. Mitigation: (1) try NadeoImporter first, (2) try extracting from the GPU mesh cache in GameData, (3) as last resort, create simplified procedural geometry for each block type based on block dimensions and naming patterns.

---

### Task ID: MVP-022
**Title**: Block mesh registry and loader
**Module**: renderer
**Depends on**: MVP-020, MVP-021
**Effort**: 1 day
**Description**: Build a `BlockMeshRegistry` that maps block names (e.g., "StadiumRoadMainStraight") to loaded GPU mesh data. Load pre-extracted `.glb` files from a static asset server or bundled directory. Parse glTF vertex data (position, normal, UV) into WebGPU vertex/index buffers. Handle missing blocks gracefully: substitute a colored wireframe cube (32x8x32 meters) for any block without an extracted mesh, logged as a warning.
**Acceptance**: Registry loads 50+ block meshes. Requesting a known block returns valid vertex/index buffer handles. Requesting an unknown block returns the fallback wireframe cube. No GPU errors during buffer creation.
**Unknowns**: **RISK** -- glTF vertex attributes must match the WebGPU vertex buffer layout. May need to re-encode normals or UVs during load.

---

### Task ID: MVP-023
**Title**: Block instancing with transform buffer
**Module**: renderer
**Depends on**: MVP-022, MVP-009
**Effort**: 2 days
**Description**: Implement instanced rendering for blocks. Group all instances of the same block type together. For each group, create a GPU storage buffer containing per-instance Mat4 transforms. Use a single draw call per block type with `drawIndexedIndirect` or instanced draw. The transform for each instance comes from its grid position + rotation (from MVP-020). This is critical for performance: a map can have 1000+ blocks but only ~100 unique block types.
**Acceptance**: Render 500+ block instances at 60fps. Profile: total draw calls should equal roughly the number of unique block types loaded (not the number of instances). Verify instances appear at correct positions by visual inspection against a screenshot of the same map in-game.
**Unknowns**: None.

---

### Task ID: MVP-024
**Title**: Scene graph with spatial hierarchy
**Module**: renderer
**Depends on**: MVP-009, MVP-023
**Effort**: 2 days
**Description**: Build a simple scene graph: a `SceneNode` tree where each node has a local transform (Mat4), a list of children, and optional renderable data (mesh + material reference). The root node is the world. Block instances are leaf nodes. Implement world-transform computation (multiply parent chain). Implement frustum culling at the node level: each node has a bounding AABB, and nodes outside the camera frustum are skipped during rendering. Use a flat array of visible renderables (collected during traversal) for draw call submission.
**Acceptance**: Frustum culling reduces draw calls by 50%+ when the camera views a quarter of a large map. Toggling culling on/off shows correct visual difference (all blocks visible vs only visible subset). Frame time improves measurably with culling enabled.
**Unknowns**: None.

---

## Group 5: Renderer (Week 4-7)

### Task ID: MVP-025
**Title**: WebGPU forward renderer with basic pipeline
**Module**: renderer
**Depends on**: MVP-003, MVP-009
**Effort**: 2 days
**Description**: Create a forward rendering pipeline in WebGPU: a single render pass that writes to the swap chain color attachment + a depth-stencil attachment (depth24plus-stencil8). Define vertex buffer layouts for block geometry (position f32x3, normal f32x3, uv f32x2 = stride 32 bytes). Write a basic vertex shader (MVP matrix transform) and fragment shader (Lambertian diffuse with a hardcoded directional light). Create pipeline state with depth testing enabled (less), backface culling, and triangle list topology.
**Acceptance**: Render a single textured cube with correct perspective projection, depth testing, and basic lighting. Rotating the camera shows correct 3D perspective. No Z-fighting or culling artifacts.
**Unknowns**: None.

---

### Task ID: MVP-026
**Title**: Render a colored triangle, then a textured block
**Module**: renderer
**Depends on**: MVP-025, MVP-022
**Effort**: 1 day
**Description**: Milestone validation task. Load one block mesh from the registry (e.g., StadiumRoadMainStraight), upload to GPU, and render it centered at the origin with the forward pipeline from MVP-025. Apply a solid gray material if textures are not yet available. Verify the block looks approximately correct (road surface on top, walls on sides, correct proportions relative to 32x8x32 meter dimensions).
**Acceptance**: A single block renders on screen with correct geometry, lighting, and proportions. Screenshot comparison against the in-game block is recognizably the same shape.
**Unknowns**: None.

---

### Task ID: MVP-027
**Title**: Orbital camera controller
**Module**: renderer
**Depends on**: MVP-025, MVP-009
**Effort**: 1 day
**Description**: Implement an orbital camera for map exploration. Use the exact math from doc 20 Section 7 (verified from Openplanet): `h = (HAngle + PI/2) * -1`, `v = VAngle`, axis rotated by v around Z then h around Y, `cameraPos = targetPos + axis.xyz * distance`. Mouse drag rotates (horizontal = HAngle, vertical = VAngle), scroll wheel adjusts distance, middle-click drag pans the target point. Clamp VAngle to avoid gimbal lock (-85 to +85 degrees).
**Acceptance**: Camera orbits around a target point smoothly. Mouse drag, scroll zoom, and pan all work. Camera never flips or exhibits gimbal lock artifacts. Works on trackpad (two-finger scroll for zoom, two-finger drag for pan).
**Unknowns**: None.

---

### Task ID: MVP-028
**Title**: Grid and axis helper for debugging
**Module**: renderer
**Depends on**: MVP-025
**Effort**: half day
**Description**: Render a ground-plane grid showing the 32m block grid (thin gray lines) and coordinate axes (red=X, green=Y, blue=Z) at the origin. The grid should cover the standard Stadium map extent (48x48 blocks = 1536x1536 meters). Grid lines should fade at distance to avoid visual noise. This is a debugging aid that will be used throughout development.
**Acceptance**: Grid is visible, correctly spaced at 32m intervals, and fades at distance. Axis arrows are visible at origin. Grid can be toggled on/off with a keypress (G key).
**Unknowns**: None.

---

### Task ID: MVP-029
**Title**: Basic PBR material system
**Module**: renderer
**Depends on**: MVP-025
**Effort**: 2 days
**Description**: Implement a basic PBR material with albedo color/texture, metallic, roughness, and normal map. Create a uniform buffer for material parameters and a bind group layout for textures (albedo sampler, normal sampler). Write a PBR fragment shader using the standard Cook-Torrance BRDF with GGX normal distribution (this matches TM2020's approach per doc 20 Section 3). Support both textured and un-textured materials (solid color fallback). Create a default material (gray, roughness 0.5, metallic 0.0) for blocks without extracted textures.
**Acceptance**: A sphere rendered with the PBR shader shows correct metallic/roughness response. Changing roughness from 0 to 1 shows a visible specular-to-matte transition. Normal mapping produces visible surface detail.
**Unknowns**: None.

---

### Task ID: MVP-030
**Title**: Directional light with basic shadow map (1 cascade)
**Module**: renderer
**Depends on**: MVP-025, MVP-029
**Effort**: 3 days
**Description**: Add a directional light (sun) to the scene. Implement a single-cascade shadow map: render the scene from the light's perspective into a depth-only texture (2048x2048), then sample this shadow map during the main lighting pass. Use a basic orthographic projection sized to cover the camera's near frustum. Apply PCF (percentage-closer filtering) with a 3x3 kernel for soft shadow edges. Apply slope-scaled depth bias to reduce shadow acne.
**Acceptance**: Blocks cast shadows onto the ground plane and onto each other. Shadows are visually correct (no major acne, no peter-panning). Moving the camera updates the shadow cascade to follow. Shadow quality is acceptable at close range.
**Unknowns**: None.

---

### Task ID: MVP-031
**Title**: Texture extraction and loading pipeline
**Module**: tools / renderer
**Depends on**: MVP-021, MVP-029
**Effort**: 2 days
**Description**: Extend the block mesh extraction tool (MVP-021) to also extract diffuse/albedo textures for each block. TM2020 materials reference texture files by name from the material library (doc 28 Section 10). Extract the most common textures (road surface, platform, grass, concrete, dirt, ice) from the game's texture files or from the material pack. Convert to WebP or PNG format. In the renderer, create a texture cache that loads textures by name and creates WebGPU texture + sampler objects. Associate textures with block materials.
**Acceptance**: 20+ distinct textures loaded. Block meshes render with their correct textures (road looks like asphalt, grass looks like grass). Texture cache handles missing textures by falling back to a checkerboard pattern.
**Unknowns**: **RISK** -- texture data may be in DDS format or embedded in pack files. May need a DDS decoder for browser use.

---

### Task ID: MVP-032
**Title**: Deferred G-buffer pipeline (4 MRT + depth)
**Module**: renderer
**Depends on**: MVP-030, MVP-029
**Effort**: 3 days
**Description**: Upgrade from forward to deferred rendering. Create a G-buffer with 4 render targets: diffuse (rgba8unorm), specular/roughness/metallic (rgba8unorm), world-space normal (rgba16float), and emissive/flags (rgba8unorm), plus depth (depth24plus-stencil8). Write a G-buffer fill pass that outputs material properties to the MRT. Write a full-screen lighting pass that reads the G-buffer and computes final color using the PBR shader + directional light + shadow map. This follows TM2020's architecture (doc 20 Section 3) but simplified to 4 targets instead of 9.
**Acceptance**: Visual output matches the forward renderer (same scene, same lighting, same shadows). G-buffer textures can be visualized individually via debug key (press 1-4 to view each target). No banding artifacts in normals (16-bit float precision).
**Unknowns**: None -- WebGPU supports up to 8 color attachments per render pass.

---

### Task ID: MVP-033
**Title**: Gamma correction and tone mapping
**Module**: renderer
**Depends on**: MVP-032
**Effort**: 1 day
**Description**: Add a post-processing pass after the deferred lighting pass. Apply Reinhard or ACES filmic tone mapping to convert HDR lighting values to displayable range. Apply gamma correction (linear to sRGB). Render the tone-mapped result to the swap chain's sRGB surface. This ensures the scene looks correct under varying light intensities and prevents washed-out or overly dark rendering.
**Acceptance**: Scene looks correctly exposed -- dark areas are visible, bright areas are not blown out. A/B comparison: toggle tone mapping to see the difference (raw HDR looks washed out, tone-mapped looks natural).
**Unknowns**: None.

---

## Group 6: Physics (Week 5-8)

### Task ID: MVP-034
**Title**: VehicleState struct in Rust
**Module**: physics
**Depends on**: MVP-007
**Effort**: 1 day
**Description**: Define the `VehicleState` struct in Rust matching the fields documented from Openplanet (doc 20 Section 2, doc 10 Section 3). Fields: `position: Vec3`, `orientation: Iso4`, `velocity: Vec3`, `angular_velocity: Vec3`, `front_speed: f32`, `side_speed: f32`, `input_steer: f32` (-1 to 1), `input_gas: f32` (0-1), `input_brake: f32` (0-1), `rpm: f32`, `gear: u8`, `is_turbo: bool`, `turbo_time: f32`, `is_grounded: bool`, per-wheel state (4 wheels: `damper_len: f32`, `wheel_rot: f32`, `steer_angle: f32`, `slip_coef: f32`, `ground_material: u8`). Export via wasm-bindgen for JS access.
**Acceptance**: Struct compiles, can be created and read from both Rust and TypeScript. Memory layout matches expected size. All fields serialize/deserialize correctly across WASM boundary.
**Unknowns**: None.

---

### Task ID: MVP-035
**Title**: Fixed-timestep game loop at 100Hz
**Module**: physics
**Depends on**: MVP-034
**Effort**: 1 day
**Description**: Implement the physics step loop in Rust. The main `step(dt_microseconds: u64)` function runs one tick of physics. On the JS side, use `requestAnimationFrame` with a fixed-timestep accumulator: accumulate real elapsed time, and call `step(10_000_000)` (10ms = 10,000,000 microseconds, matching TM2020's internal unit from doc 10 Section 1.3) repeatedly until the accumulator is drained. Cap at 10 steps per frame to prevent spiral of death. Interpolate render state between previous and current physics state for smooth display.
**Acceptance**: Physics runs at exactly 100 ticks per second regardless of display refresh rate. A profiler shows consistent 10ms step intervals. Reducing browser frame rate (throttle to 30fps) still produces correct physics behavior (3-4 physics steps per frame).
**Unknowns**: None.

---

### Task ID: MVP-036
**Title**: Forward Euler integration with gravity
**Module**: physics
**Depends on**: MVP-035, MVP-006
**Effort**: 1 day
**Description**: Implement Forward Euler integration in the physics step: `velocity += acceleration * dt`, `position += velocity * dt`, `orientation += angular_velocity * dt` (via quaternion integration). Apply gravity as a constant downward acceleration (9.81 m/s^2 in -Y direction). TM2020 uses parameterized gravity with GravityCoef (doc 10 Section 7), but start with a hardcoded 9.81 for now. Update the vehicle's Iso4 transform each step.
**Acceptance**: A vehicle spawned at Y=100 falls under gravity, accelerating correctly. Position at t=1s (100 ticks) matches kinematic equation (y = 100 - 0.5 * 9.81 * 1^2 = 95.095m). Velocity at t=1s = -9.81 m/s.
**Unknowns**: None.

---

### Task ID: MVP-037
**Title**: Ground plane collision response
**Module**: physics
**Depends on**: MVP-036
**Effort**: 1 day
**Description**: Implement basic ground collision: if vehicle Y position drops below a ground height (initially Y=72m, the standard Stadium terrain height from doc 28 Section 1.4), clamp position to ground, zero the downward velocity component, and set `is_grounded = true`. Apply a simple normal force (opposing gravity) when grounded. This is a temporary placeholder before full map collision; it lets the car drive on a flat plane.
**Acceptance**: Vehicle falls from spawn, lands on ground plane at Y=72, stops bouncing within a few frames. Vehicle stays on ground when stationary. No penetration through the ground plane.
**Unknowns**: None.

---

### Task ID: MVP-038
**Title**: Basic steering model (yaw torque)
**Module**: physics
**Depends on**: MVP-037
**Effort**: 2 days
**Description**: Implement simplified steering. When grounded: apply a yaw torque proportional to `input_steer * speed * steer_factor`. The steer factor should decrease with speed (speed-dependent steering, a core TM behavior). Use a simple formula: `yaw_rate = steer * max_yaw_rate / (1 + speed * speed_sensitivity)`. Apply the yaw rotation to the vehicle's orientation quaternion each tick. Compute `front_speed` (dot product of velocity with forward direction) and `side_speed` (dot product with right direction).
**Acceptance**: Vehicle turns left/right in response to steer input. At low speed, turns are tight. At high speed, turns are wider. Vehicle maintains forward momentum during turns. Front speed and side speed values are correct.
**Unknowns**: **RISK** -- The actual steering model uses tire forces and slip angles (doc 10 Section 2), which we are approximating here. Constants will need iterative tuning later.

---

### Task ID: MVP-039
**Title**: Engine force (throttle) and brake force
**Module**: physics
**Depends on**: MVP-038
**Effort**: 2 days
**Description**: Implement engine force: when `input_gas > 0` and grounded, apply a forward force along the vehicle's forward axis. Force = `gas * engine_force_max * gear_ratio`. Implement a simple gear system: 5 forward gears with RPM-based shifting (shift up at 10000 RPM, shift down at 4000 RPM). Implement brake force: when `input_brake > 0`, apply a force opposing the current velocity direction, proportional to `brake * brake_force_max`. Implement basic aerodynamic drag: `drag_force = -drag_coef * speed^2 * velocity_normalized`. Top speed emerges naturally from engine force vs drag equilibrium.
**Acceptance**: Vehicle accelerates from standstill to approximately 300 km/h (83 m/s, rough CarSport top speed) when holding gas. Vehicle decelerates when braking. Vehicle coasts to a stop from aerodynamic drag alone. Gear shifts are audible in the RPM value (saw-tooth pattern). RPM ranges 0-11000 (doc 20 Section 2).
**Unknowns**: **RISK** -- Force constants are guesswork until we can compare against TMInterface validation data. The actual engine model has 8 gears (doc 20 Section 2) and complex curves.

---

### Task ID: MVP-040
**Title**: Map collision mesh generation from block data
**Module**: physics
**Depends on**: MVP-018, MVP-022, MVP-008
**Effort**: 3 days
**Description**: Generate a collision mesh from the loaded map. For each block instance, take its glTF geometry (from the mesh registry) and transform it by the block's world-space transform. Simplify: use only the top surface and wall triangles (skip decorative geometry). Build a static triangle mesh suitable for collision queries. Store as a flat array of triangles with associated surface IDs (asphalt, dirt, ice, etc., from doc 28 Section 10). Build a BVH (bounding volume hierarchy) for efficient ray and overlap queries. This runs once at map load time.
**Acceptance**: Collision mesh generated for a test map in under 2 seconds. BVH queries (ray cast from above, hitting the road surface) return correct hit points and surface normals. Triangle count is reasonable (under 500K for a typical map). Collision mesh aligns with rendered geometry (no visible offset).
**Unknowns**: **RISK** -- block meshes may have decorative geometry mixed with collision geometry. TM2020 separates visual and collision meshes internally. We may need to tag or filter collision-relevant faces during extraction (MVP-021). Mitigation: start with all geometry as collision; refine later.

---

### Task ID: MVP-041
**Title**: AABB broadphase collision detection
**Module**: physics
**Depends on**: MVP-040, MVP-034
**Effort**: 2 days
**Description**: Implement collision detection between the vehicle and the map collision mesh. Broadphase: compute the vehicle's AABB (approximately 4.6m long x 1.5m tall x 2.0m wide for CarSport, centered on position). Query the BVH for all triangles overlapping the vehicle AABB. Narrowphase: for each candidate triangle, perform SAT (separating axis theorem) or GJK test against the vehicle's simplified collision box. Return contact points with penetration depth, contact normal, and surface ID.
**Acceptance**: Vehicle driving on the road detects ground contact with correct normals (pointing up on flat road). Vehicle hitting a wall detects side contact with correct wall normal. No false positives when vehicle is clearly not touching anything. Broadphase eliminates 95%+ of triangles from narrowphase checks.
**Unknowns**: None.

---

### Task ID: MVP-042
**Title**: Collision response with friction
**Module**: physics
**Depends on**: MVP-041
**Effort**: 2 days
**Description**: Implement collision response. For each contact point: (1) resolve penetration by moving the vehicle out along the contact normal, (2) apply a normal impulse to prevent further penetration (coefficient of restitution near 0 for road contact, ~0.3 for walls), (3) apply friction force tangent to the contact surface. Friction coefficient varies by surface ID: asphalt ~1.0, dirt ~0.7, grass ~0.5, ice ~0.1. Use the surface ID table from doc 28 Section 10 (19 surface types with gameplay effects). TM2020's friction solver uses iterative resolution with separate static/dynamic iteration counts (doc 10 Section 5), but start with a simple impulse-based solver.
**Acceptance**: Vehicle drives on road without falling through. Vehicle slides on ice surfaces, grips on asphalt. Vehicle bounces slightly off walls and does not penetrate. Surface transitions (road to grass) produce a visible change in grip. No jittering when stationary on a slope.
**Unknowns**: **RISK** -- friction constants are approximations. The actual values come from force model tuning curves that we have not decompiled. Mitigation: use TMInterface to record speed on different surfaces and calibrate.

---

### Task ID: MVP-043
**Title**: Simplified CarSport force model
**Module**: physics
**Depends on**: MVP-042, MVP-039
**Effort**: 3 days
**Description**: Replace the simplified physics from MVP-038/039 with a more realistic force model inspired by the CarSport (model 6, FUN_14085c9e0). Implement: 4-wheel suspension raycasts (downward from wheel positions), spring-damper suspension forces per wheel, per-wheel tire force based on slip angle (Pacejka-like: `lateral_force = -slip * linear_coef - slip*|slip| * quadratic_coef`, from doc 10 Section 2.3), engine torque distributed to rear wheels, brake torque to all wheels, anti-roll bar force between left/right wheel pairs, aerodynamic downforce. The CarSport force model was decompiled at 350+ lines (doc 22 Priority 1) with 9 sub-functions -- use the documented structure as a guide but approximate the constants.
**Acceptance**: Vehicle feels roughly like driving in TM2020: responsive steering, controlled drifting when turning hard at speed, stable at high speed on straights. Vehicle can complete a lap on a simple Stadium map without falling through the road or flying off into space. Qualitative comparison: a TM2020 player would say "this feels like a rough approximation of Stadium car."
**Unknowns**: **HIGH RISK** -- This is the hardest physics task (doc 20 Section 17.1). The force model internals use tuning curves we do not have. The decompiled code gives structural guidance but many coefficient values come from .Gbx resource files we cannot read. Mitigation: (1) use TMInterface to capture reference trajectories, (2) iteratively tune constants, (3) accept "approximately right" for MVP.

---

### Task ID: MVP-044
**Title**: Turbo/boost force application
**Module**: physics
**Depends on**: MVP-043
**Effort**: 1 day
**Description**: Implement turbo pad boost. When the vehicle contacts a turbo surface (detected via surface ID or block name containing "Turbo"), activate a timed boost: for `duration` ticks, apply an additional forward force. The force ramps linearly from 0 to `strength * modelScale` over the duration (doc 10 Section 4.3, verified from decompilation). Support Turbo (normal) and Turbo2 (super) with different strength/duration values. Track `is_turbo` and `turbo_time` in VehicleState.
**Acceptance**: Driving over a turbo pad produces a speed boost. Speed increases beyond normal top speed during turbo. Turbo expires after the correct duration. Multiple turbos can chain. Turbo1 and Turbo2 produce different boost magnitudes.
**Unknowns**: **RISK** -- The decompiled code shows the turbo force ramps UP linearly, not decaying (doc 10 Section 4.3). This contradicts intuition and TMNF behavior (doc 18 Issue 6). Need to test both directions and compare against in-game behavior. Start with ramp-up as the decompilation suggests.

---

## Group 7: Input (Week 6-8)

### Task ID: MVP-045
**Title**: Keyboard input handler
**Module**: input
**Depends on**: MVP-001
**Effort**: 1 day
**Description**: Implement keyboard input mapping for driving. Arrow keys: up = gas (digital, 0 or 1), down = brake (digital, 0 or 1), left = steer left (-1), right = steer right (+1). Additional: R = respawn/reset, Enter = restart. Maintain an `InputState` struct: `{ steer: f32, gas: f32, brake: f32, respawn: bool, restart: bool }`. Update on keydown/keyup events. Handle simultaneous keys correctly (left+right = steer 0). Prevent default browser behavior for game keys (no page scrolling on arrow keys).
**Acceptance**: Pressing arrow keys updates InputState with correct values. Releasing keys returns values to 0/neutral. Holding left+up simultaneously produces steer=-1, gas=1, brake=0. Browser does not scroll when arrow keys are pressed.
**Unknowns**: None.

---

### Task ID: MVP-046
**Title**: Gamepad input handler
**Module**: input
**Depends on**: MVP-045
**Effort**: 1 day
**Description**: Implement gamepad input using the Gamepad API. Map: left stick X axis = steer (analog, -1 to 1), right trigger = gas (analog, 0 to 1), left trigger = brake (analog, 0 to 1). Poll gamepad state each frame via `navigator.getGamepads()`. Apply a deadzone of 0.1 on the stick axes (values under 0.1 map to 0). Merge gamepad input with keyboard input: use whichever source has the larger absolute value for each axis. Handle gamepad connect/disconnect events.
**Acceptance**: Analog stick steering works with smooth gradation (partial turns). Triggers produce analog gas/brake. Deadzone prevents drift from stick noise. Keyboard overrides work when no gamepad is present. Gamepad disconnection falls back to keyboard gracefully.
**Unknowns**: None.

---

### Task ID: MVP-047
**Title**: Input to physics bridge
**Module**: input / physics
**Depends on**: MVP-046, MVP-034
**Effort**: 1 day
**Description**: Connect the input system to the physics engine. Each physics tick, copy the current `InputState` values into the `VehicleState` input fields (`input_steer`, `input_gas`, `input_brake`). If physics runs in a Web Worker (for performance), use `SharedArrayBuffer` to share input state without message-passing latency: write InputState from the main thread, read from the worker thread. If physics runs on the main thread (simpler initial approach), direct function call is sufficient. Include a 1-frame input delay option for determinism testing.
**Acceptance**: Pressing gas key causes the vehicle to accelerate. Steering input turns the vehicle. Input latency is imperceptible (under 1 frame / 16ms). SharedArrayBuffer path works on Chrome with correct COOP/COEP headers.
**Unknowns**: **RISK** -- SharedArrayBuffer requires specific HTTP headers (`Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Embedder-Policy: require-corp`). The dev server must be configured to send these.

---

### Task ID: MVP-048
**Title**: Input recording buffer
**Module**: input
**Depends on**: MVP-047
**Effort**: 1 day
**Description**: Record all input state changes during a race run. Store as an array of `InputSample` objects: `{ tick: u32, steer: f32, gas: f32, brake: f32 }`. Only record a new sample when any input value changes (delta encoding for efficiency). Provide `startRecording()`, `stopRecording()`, and `getRecording(): InputSample[]` methods. Export recordings as JSON for debugging. This is the foundation for ghost replay and replay validation.
**Acceptance**: Complete a short drive (100 ticks / 1 second), export the recording, and verify it contains correct input values at correct tick numbers. Recording of a 60-second drive produces under 100KB of JSON. Replaying the recording by feeding inputs back produces the same physics output (positions match within floating-point epsilon).
**Unknowns**: None.

---

## Group 8: Camera (Week 7-8)

### Task ID: MVP-049
**Title**: Race camera (3rd-person chase)
**Module**: camera
**Depends on**: MVP-027, MVP-034
**Effort**: 2 days
**Description**: Implement a chase camera that follows the vehicle. Target: a point above and behind the vehicle (offset approximately -10m behind, +4m up in vehicle-local space). Use a spring-damper system for smooth tracking: the camera position lerps toward the target position each frame with configurable stiffness (higher stiffness = more responsive, lower = more cinematic lag). Look-at target: a point slightly ahead of the vehicle along its forward direction. Rotate with the vehicle's yaw but dampen pitch to avoid nauseating oscillation on bumps.
**Acceptance**: Camera follows the vehicle smoothly during driving. Camera lags slightly when the vehicle turns quickly (natural feel). Camera is positioned behind and above the vehicle at all times. Fast steering shows the camera swinging to catch up. Stopping shows the camera settling behind the vehicle.
**Unknowns**: **RISK** -- TM2020's actual camera parameters (follow distance, height, stiffness curves) are stored in VehicleCameraRace2Model.gbx which we cannot parse. Use approximations and tune by feel.

---

### Task ID: MVP-050
**Title**: Free camera for debugging
**Module**: camera
**Depends on**: MVP-027
**Effort**: half day
**Description**: Implement a free-fly camera for debugging. WASD for movement (relative to camera facing direction), mouse drag for look rotation, Shift for fast movement, scroll wheel for speed adjustment. Toggle between race camera and free camera with a key (Tab). When in free camera mode, physics still runs but the camera is decoupled from the vehicle.
**Acceptance**: Free camera moves smoothly in all directions. Look rotation works without gimbal lock. Toggling between free and race camera preserves the vehicle's current state. Speed adjustment via scroll provides a useful range from slow inspection to fast map traversal.
**Unknowns**: None.

---

### Task ID: MVP-051
**Title**: Camera collision avoidance
**Module**: camera
**Depends on**: MVP-049, MVP-040
**Effort**: 1 day
**Description**: Prevent the chase camera from clipping through map geometry. Cast a ray from the camera look-at target toward the desired camera position. If the ray hits map geometry before reaching the desired position, move the camera to the hit point (with a small offset along the normal to prevent Z-fighting). Apply smooth transitions when entering/exiting collision avoidance to prevent jarring camera jumps.
**Acceptance**: Camera does not clip through walls or road surfaces when the vehicle drives near geometry. Camera smoothly pulls closer when a wall is between it and the vehicle, and smoothly returns to the desired distance when clear. No flickering or oscillation at geometry edges.
**Unknowns**: None.

---

## Group 9: Integration (Week 8-10)

### Task ID: MVP-052
**Title**: Map load pipeline: file to rendered scene
**Module**: integration
**Depends on**: MVP-019, MVP-022, MVP-023, MVP-024, MVP-040
**Effort**: 2 days
**Description**: Build the end-to-end map loading pipeline. User drops or selects a `.Map.Gbx` file. Pipeline: (1) read file as ArrayBuffer, (2) parse GBX header and body (MVP-019), (3) extract block placements and item placements, (4) for each block, look up mesh in registry, create scene node with transform, (5) build collision mesh from all block geometry, (6) build BVH, (7) spawn vehicle at the Start waypoint position. Display a loading progress indicator during steps 4-6. Handle errors gracefully (show which step failed).
**Acceptance**: Load 3+ different map files from file picker. Each renders correctly with all blocks in correct positions. Vehicle spawns at the map's start gate. Loading completes in under 5 seconds for a standard map. Error on a corrupted file shows a meaningful message.
**Unknowns**: **RISK** -- maps with many unique block types may reference blocks we have not extracted meshes for. The wireframe fallback (MVP-022) handles this, but maps with mostly missing meshes will look bad.

---

### Task ID: MVP-053
**Title**: Connect physics to renderer: vehicle driving on map
**Module**: integration
**Depends on**: MVP-052, MVP-043, MVP-047, MVP-049
**Effort**: 2 days
**Description**: Wire all systems together: input -> physics -> renderer. Each frame: (1) poll input, (2) run physics tick(s), (3) read vehicle state from WASM, (4) update vehicle scene node transform from physics position/orientation, (5) update chase camera from vehicle state, (6) cull and render the scene. Render the vehicle as a simple box (4.6m x 1.5m x 2.0m, colored red) until a car model is available. The vehicle should drive on the map surface, affected by gravity and road collision.
**Acceptance**: Vehicle drives on the map, follows the road surface, hits walls, and the camera follows. The driving experience is recognizable as "car racing on a Trackmania map." No desync between physics and rendering (vehicle does not visibly pop or teleport).
**Unknowns**: None.

---

### Task ID: MVP-054
**Title**: HUD: speedometer and race timer
**Module**: ui
**Depends on**: MVP-053
**Effort**: 1 day
**Description**: Overlay a minimal HUD on the 3D canvas using HTML/CSS (positioned absolutely over the WebGPU canvas). Speedometer: display `FrontSpeed * 3.6` as km/h, updated each frame, positioned bottom-center. Race timer: display elapsed race time in `MM:SS.mmm` format, positioned top-center. Use CSS for styling (large, readable font, semi-transparent background). The timer starts on first gas input and counts up.
**Acceptance**: Speed display shows 0 when stationary and approximately 300+ km/h at top speed. Timer starts counting when gas is pressed for the first time. Timer format is correct. HUD elements are readable over any map background.
**Unknowns**: None.

---

### Task ID: MVP-055
**Title**: Checkpoint detection system
**Module**: gameplay
**Depends on**: MVP-018, MVP-053
**Effort**: 2 days
**Description**: Detect when the vehicle passes through checkpoint and finish gates. From the parsed map data, identify blocks with waypoint properties (Start, Finish, Checkpoint, StartFinish) using the block name matching against known gate names (doc 28 Section 3.1: names containing "Gate" with waypoint tags). For each waypoint, create a trigger volume (AABB covering the gate's geometry bounds). Each physics tick, check if the vehicle's position has crossed through any active trigger volume (entered from one side, exited the other). Maintain a checkpoint list and track which have been collected. Enforce ordering: checkpoint N must be collected before checkpoint N+1. Support multilap (StartFinish block means lap counter increments).
**Acceptance**: Driving through a checkpoint triggers a "checkpoint collected" event. Driving through checkpoints out of order does not count. The finish line triggers only after all checkpoints are collected. Multilap maps correctly count laps. Display current checkpoint count (e.g., "CP 3/5") in the HUD.
**Unknowns**: **RISK** -- waypoint identification relies on block naming conventions. If gate blocks use unexpected names, they will not be detected. Mitigation: parse the waypoint special property field from the GBX data if available, rather than relying solely on block names.

---

### Task ID: MVP-056
**Title**: Finish detection and race result
**Module**: gameplay
**Depends on**: MVP-055
**Effort**: 1 day
**Description**: When the vehicle crosses the finish line with all checkpoints collected, stop the race timer and display the finish time. Store checkpoint split times (time at each checkpoint relative to race start). Display the result screen: final time, each checkpoint time, and a "Restart" button. On restart, reset vehicle to start position, clear timer and checkpoints, and begin a new run. For multilap maps, track per-lap times and show total time at final finish.
**Acceptance**: Completing a race shows the correct finish time. Checkpoint times are recorded and displayed. Restarting resets everything for a fresh run. Finishing a 3-lap map shows lap times and total time.
**Unknowns**: None.

---

### Task ID: MVP-057
**Title**: Countdown sequence at race start
**Module**: gameplay
**Depends on**: MVP-054, MVP-053
**Effort**: half day
**Description**: Implement a 3-2-1-GO countdown at the start of a race. When the map finishes loading and the vehicle is spawned at the start position: display "3" for 1 second, "2" for 1 second, "1" for 1 second, "GO!" for 0.5 seconds, then hide. Vehicle input is locked during the countdown (gas/steer ignored). Timer starts at "GO!". Display countdown numbers as large centered text over the 3D view.
**Acceptance**: Countdown displays correctly. Vehicle does not move during countdown even if keys are pressed. Timer starts exactly when "GO!" appears. Visual countdown is readable and prominent.
**Unknowns**: None.

---

### Task ID: MVP-058
**Title**: Respawn/reset to checkpoint
**Module**: gameplay
**Depends on**: MVP-055, MVP-048
**Effort**: 1 day
**Description**: When the player presses the respawn key (R or Delete), reset the vehicle to the last collected checkpoint position. If no checkpoint has been collected, reset to the start position. Reset vehicle state: zero velocity, zero angular velocity, restore orientation to face the track direction at that checkpoint, preserve the race timer (do not reset it). Apply a brief invulnerability period (0.5s) after respawn to prevent immediate re-collision. Increment a respawn counter for the run.
**Acceptance**: Pressing R teleports vehicle to last checkpoint. Vehicle faces the correct direction after respawn. Velocity is zeroed. Timer continues running. Multiple respawns work correctly (always goes to the latest checkpoint). Respawning before any checkpoint returns to start.
**Unknowns**: **RISK** -- determining the "facing direction" at a checkpoint requires knowing the track route direction, which is not explicitly stored. Mitigation: use the checkpoint block's rotation direction as a proxy.

---

## Group 10: Polish (Week 10-12)

### Task ID: MVP-059
**Title**: Loading screen with progress indication
**Module**: ui
**Depends on**: MVP-052
**Effort**: 1 day
**Description**: Display a loading screen while a map is being loaded. Show: map name (from header, available early), author name, thumbnail (from header chunk 0x03043007, JPEG data), and a progress bar with step labels ("Parsing map...", "Loading block meshes...", "Building collision mesh...", "Ready!"). The loading screen covers the canvas and fades out when loading completes.
**Acceptance**: Loading screen appears immediately when a map file is selected. Thumbnail displays correctly. Progress bar advances through distinct stages. Screen fades to reveal the loaded map. Works for maps both with and without embedded thumbnails.
**Unknowns**: None.

---

### Task ID: MVP-060
**Title**: Map selection UI
**Module**: ui
**Depends on**: MVP-059
**Effort**: 1 day
**Description**: Build a start screen with a file picker for loading maps. Two options: (1) "Open Map File" button that triggers a file input dialog for `.Map.Gbx` files, (2) a drag-and-drop zone that accepts dropped `.Map.Gbx` files. Optionally, show a list of recently-loaded maps (stored in localStorage) for quick re-loading. Show the OpenTM logo/title and basic instructions ("Drop a .Map.Gbx file or click to browse").
**Acceptance**: Clicking the button opens a file dialog filtered to `.Map.Gbx` files. Dragging a file onto the page triggers map loading. Recently loaded maps appear as clickable items (if localStorage feature is implemented). Invalid file types show an error message.
**Unknowns**: None.

---

### Task ID: MVP-061
**Title**: Bloom post-processing effect
**Module**: renderer
**Depends on**: MVP-033
**Effort**: 2 days
**Description**: Implement HDR bloom as a post-processing effect. Steps: (1) extract bright pixels from the lit scene (threshold at luminance > 1.0), (2) downsample the bright pixels through a 5-level mip chain (each level is half resolution), (3) blur each mip level with a 9-tap Gaussian kernel, (4) upsample and accumulate back to full resolution, (5) add the bloom result to the tone-mapped scene with a configurable intensity. Use compute shaders for the downscale/blur/upscale passes. This matches TM2020's 3-level bloom (doc 20 Section 3).
**Acceptance**: Bright areas (sun-facing surfaces, turbo pads) produce a visible bloom glow. Bloom intensity is controllable. Disabling bloom shows a clear visual difference. No visible artifact banding in bloom gradients. Performance impact is under 2ms at 1080p.
**Unknowns**: None.

---

### Task ID: MVP-062
**Title**: FXAA anti-aliasing
**Module**: renderer
**Depends on**: MVP-033
**Effort**: 1 day
**Description**: Implement FXAA (Fast Approximate Anti-Aliasing) as a full-screen post-processing pass. Apply after tone mapping, before final output to swap chain. Use the standard FXAA 3.11 algorithm (publicly available, well-documented). This smooths jagged edges on block geometry and the vehicle without the cost of MSAA. FXAA runs in a single compute or fragment shader pass.
**Acceptance**: Edges are visibly smoother with FXAA enabled. Toggle FXAA on/off to see the difference. No visible blurring of text or HUD elements (FXAA only applies to the 3D scene). Performance impact is under 1ms at 1080p.
**Unknowns**: None.

---

### Task ID: MVP-063
**Title**: Sky rendering (gradient + sun disc)
**Module**: renderer
**Depends on**: MVP-032
**Effort**: 1 day
**Description**: Replace the solid-color sky with a procedural sky. Render a full-screen quad behind all geometry (at max depth). Fragment shader computes a vertical gradient (horizon color at bottom, zenith color at top) plus a sun disc in the directional light direction. Colors based on the map's "mood" / time of day: Day (blue sky, yellow sun), Sunset (orange gradient, red sun), Night (dark blue, dim moon). Read the mood string from the parsed map header (chunk 0x03043003).
**Acceptance**: Sky renders behind all geometry. Day mood shows blue sky. Sunset shows warm gradient. Night shows dark sky. Sun disc is visible in the light direction. No seams or artifacts at the horizon.
**Unknowns**: None.

---

### Task ID: MVP-064
**Title**: Vehicle mesh (CarSport model)
**Module**: renderer
**Depends on**: MVP-021, MVP-053
**Effort**: 2 days
**Description**: Extract or create a CarSport (Stadium car) 3D model and render it in place of the placeholder box. Options: (1) extract from TM2020's game files using the block mesh extraction pipeline, (2) use a community-created model, (3) create a simplified low-poly model that resembles the CarSport silhouette. The model needs: body mesh, 4 wheel meshes that rotate independently (wheel_rot from VehicleState), steering rotation on front wheels (steer_angle from VehicleState). Apply the vehicle's Iso4 transform for body position/orientation.
**Acceptance**: Vehicle renders as a recognizable car (not a box). Wheels rotate when driving. Front wheels turn when steering. Vehicle proportions approximately match CarSport (4.6m long, low profile, wide stance). Model renders at correct position matching physics.
**Unknowns**: **RISK** -- extracting the actual CarSport model from game files may be difficult (it is in an encrypted pack file). A simplified stand-in model may be needed for MVP.

---

### Task ID: MVP-065
**Title**: Performance profiling and optimization pass
**Module**: core
**Depends on**: MVP-053, MVP-061
**Effort**: 2 days
**Description**: Profile the full application on target hardware (mid-range laptop with integrated GPU). Measure: frame time breakdown (physics, culling, render, post-processing), draw call count, triangle count, GPU memory usage, WASM call overhead, GC pauses. Identify and fix the top 3 bottlenecks. Common targets: reduce draw calls via better instancing, reduce overdraw with front-to-back sorting, reduce shader complexity for distant objects, reduce collision mesh BVH queries per frame. Target: 60fps at 1080p on integrated Intel/AMD GPU.
**Acceptance**: Application runs at 60fps on a mid-range laptop (e.g., M1 MacBook Air or Intel 12th gen with integrated graphics) with a standard Stadium map loaded. Frame time stays under 16ms with no regular spikes. A performance overlay (toggle with P key) shows live frame time, draw calls, and triangle count.
**Unknowns**: **RISK** -- if WebGPU performance on the target hardware is insufficient, may need to reduce rendering quality (fewer shadow cascades, lower resolution bloom, simpler materials).

---

### Task ID: MVP-066
**Title**: Settings panel (quality, input, display)
**Module**: ui
**Depends on**: MVP-060, MVP-065
**Effort**: 1 day
**Description**: Build a settings panel (HTML/CSS overlay, toggled with Escape key) with: (1) Quality: shadow quality (off/low/high), bloom (on/off), FXAA (on/off), render scale (0.5x/1.0x/1.5x), (2) Input: keyboard binding display, gamepad deadzone slider, (3) Display: show FPS counter, show debug grid, show collision mesh wireframe. Store settings in localStorage and apply on page load.
**Acceptance**: All settings work as described. Changing render scale visually changes resolution. Toggling shadows on/off is visible. Settings persist across page reloads. Settings panel does not interfere with gameplay when closed.
**Unknowns**: None.

---

### Task ID: MVP-067
**Title**: Mobile browser compatibility testing and touch input
**Module**: core / input
**Depends on**: MVP-065
**Effort**: 2 days
**Description**: Test the application on mobile browsers (Chrome Android, Safari iOS). Fix issues: (1) touch input for driving (virtual joystick or tilt steering), (2) viewport scaling and orientation lock (landscape), (3) WebGPU availability check (fallback message if unavailable), (4) performance on mobile GPU (reduce quality preset automatically). Implement basic touch controls: left side of screen = virtual joystick for steering, right side = tap for gas, swipe down for brake. Note: WebGPU support on mobile is limited as of 2026; this task may result in a "not supported" message on many devices.
**Acceptance**: Application loads on Chrome Android (Pixel 6 or equivalent) with WebGPU support. Touch controls allow basic driving. Landscape orientation is enforced. On devices without WebGPU, a clear "WebGPU not supported" message is shown.
**Unknowns**: **RISK** -- WebGPU support on mobile browsers is still rolling out. iOS Safari WebGPU may have compatibility issues. This task may be partially blocked by browser vendor support.

---

### Task ID: MVP-068
**Title**: End-to-end acceptance testing
**Module**: integration
**Depends on**: all previous tasks
**Effort**: 2 days
**Description**: Final validation of the complete MVP. Test on 10+ maps (simple A01-style through complex community maps). For each map: (1) file loads without errors, (2) blocks render in correct positions, (3) vehicle spawns at start, (4) driving physics feel reasonable, (5) checkpoints trigger correctly, (6) finish line completes the race, (7) timer shows correct finish time, (8) restart works, (9) respawn works, (10) camera behaves correctly. Document any remaining bugs with severity ratings. Fix critical bugs (crashes, soft-locks). Accept known issues for non-critical visual or physics glitches.
**Acceptance**: 8 out of 10 test maps complete a full race without critical bugs. Known issues are documented with severity and workaround. The application does not crash on any tested map. A first-time user can load a map and complete a race without instructions beyond the start screen.
**Unknowns**: None.

---

## Critical Path

The critical path determines the minimum calendar time to complete the MVP. It is the longest dependency chain through the task graph:

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

**Critical path length**: 1+1+2+1+1+1+1+1+2+2+3+2+2+1+2 = **23 working days** (~4.6 weeks)

However, this does not account for the renderer dependency chain which must merge at MVP-053:

```
MVP-001 (1d) -> MVP-003 (1d) -> MVP-025 (2d) -> MVP-029 (2d) -> MVP-030 (3d) -> MVP-032 (3d)
```

Renderer chain: 1+1+2+2+3+3 = **12 days**

And the GBX parser chain which must merge at MVP-052:

```
MVP-001 (1d) -> MVP-010 (0.5d) -> MVP-011 (1d) -> MVP-017 (2d) -> MVP-018 (3d) -> MVP-019 (1d)
```

Parser chain: 1+0.5+1+2+3+1 = **8.5 days**

And the block mesh pipeline:

```
MVP-021 (3d, parallel) -> MVP-022 (1d) -> MVP-023 (2d) -> MVP-024 (2d)
```

Block chain: 3+1+2+2 = **8 days** (but starts independently)

**True critical path** (considering all merge points):

The physics chain (23 days) is the longest. The renderer chain (12 days) and parser chain (8.5 days) finish in time to merge at MVP-053 if started in week 1. The block mesh extraction (MVP-021, 3 days) is independent and can start immediately.

**The map collision mesh (MVP-040, 3d)** depends on both the parser (MVP-018) and block meshes (MVP-022), and feeds into the physics chain at MVP-041. This adds a potential bottleneck:

```
MVP-021 (3d) -> MVP-022 (1d) -> MVP-040 (3d) -> MVP-041 (2d) -> MVP-042 (2d) -> MVP-043 (3d)
```

Collision path from start: 3+1+3+2+2+3 = **14 days**

This merges into the physics chain after MVP-039. Since the physics chain up to MVP-039 takes 14 days, and the collision path also takes 14 days, these are neck-and-neck. Any delay in block mesh extraction directly delays the entire project.

**Flagged critical path bottleneck**: MVP-021 (Block mesh extraction) is both on the critical path AND has the highest risk. If this task takes 5 days instead of 3, the entire project slips by 2 days.

**Realistic timeline**: 23 working days of serial critical path, plus 2-3 days of integration buffer = **~5.5 weeks** for the core path. With parallel work on renderer, parser, and polish, the full MVP is achievable in **10-12 weeks** for a single developer.

---

## Risk Register

### Risk 1: Block Mesh Extraction Fails
**Probability**: MEDIUM
**Impact**: CRITICAL -- cannot render maps without block geometry
**Description**: Block meshes are stored in encrypted .pak files. NadeoImporter may not export built-in blocks directly. The CPlugSolid2Model internal format is partially documented but complex (doc 16 Section 19).
**Mitigation**: (1) Try NadeoImporter first. (2) Try gbx-net's mesh reading capabilities. (3) Extract from GPU mesh cache. (4) As last resort, generate procedural geometry per block type (boxes with correct dimensions, roads as flat planes with correct width/curve). Procedural fallback maintains gameplay even without visual fidelity.
**Owner**: MVP-021

### Risk 2: CarSport Physics Feel Wrong
**Probability**: HIGH
**Impact**: HIGH -- the MVP is a driving game; bad physics ruin the experience
**Description**: The force model internals (FUN_14085c9e0) have been decompiled structurally (350+ lines, 9 sub-functions) but many coefficient values come from .Gbx resource files we cannot access. The tire model uses curves we do not have.
**Mitigation**: (1) Use TMInterface to capture reference trajectories (input + position at each tick for known runs). (2) Build a tuning workflow: run same inputs through our physics, compare position divergence, adjust constants. (3) Use community physics documentation from TMNF as a starting point (doc 14 cross-reference). (4) Accept "approximately right" for MVP -- the car should be drivable and fun, not physics-exact.
**Owner**: MVP-043

### Risk 3: GBX Body Parsing Fails on Complex Maps
**Probability**: MEDIUM
**Impact**: MEDIUM -- some maps will not load, but simple maps will work
**Description**: The GBX body chunk stream may contain non-skippable chunks we do not handle, halting the parser. Complex community maps may use features (custom blocks, embedded items, special chunk versions) beyond what we have implemented.
**Mitigation**: (1) Use gbx-net source as the authoritative reference for chunk parsing. (2) Add a "skip unknown skippable chunk" fallback. (3) Test with progressively more complex maps. (4) Accept partial compatibility for MVP -- target 80%+ of simple-to-medium maps.
**Owner**: MVP-017, MVP-018

### Risk 4: LZO Decompression Library Buggy or Unavailable
**Probability**: LOW
**Impact**: CRITICAL -- cannot decompress GBX body data at all
**Description**: GBX body data uses LZO1X compression, not zlib. JavaScript LZO implementations are less common and less tested than zlib implementations.
**Mitigation**: (1) Test multiple npm packages (lzo-wasm, minilzo-js). (2) Port miniLZO (750 lines of C) to Rust WASM as a fallback. (3) Use pako for any zlib-compressed secondary data (lightmaps, ghosts).
**Owner**: MVP-011

### Risk 5: WebGPU Performance Insufficient
**Probability**: LOW
**Impact**: HIGH -- application will not run at 60fps
**Description**: A map with 1000+ blocks and full deferred rendering with shadows and bloom may exceed the GPU budget on integrated graphics.
**Mitigation**: (1) Forward rendering fallback for low-end devices (MVP-025 remains available). (2) Adaptive quality: reduce render scale, disable shadows/bloom based on measured frame time. (3) Block instancing (MVP-023) is critical for draw call reduction. (4) LOD system: render distant blocks as simple boxes.
**Owner**: MVP-065

### Risk 6: Turbo Ramp Direction Uncertainty
**Probability**: MEDIUM
**Impact**: LOW -- turbo will work but feel wrong
**Description**: Decompiled code shows turbo force ramps UP linearly over duration (doc 10 Section 4.3). This contradicts TMNF behavior and intuition. If the ramp direction is wrong, turbo pads will feel unnatural.
**Mitigation**: (1) Implement ramp-up as decompilation suggests. (2) Also implement ramp-down (decay). (3) Use TMInterface to capture actual speed curves during turbo activation. (4) Make the ramp direction a configurable parameter that can be toggled during testing.
**Owner**: MVP-044

### Risk 7: Waypoint/Checkpoint Detection Unreliable
**Probability**: MEDIUM
**Impact**: MEDIUM -- races cannot be completed if checkpoints are missed
**Description**: Checkpoint detection relies on identifying gate blocks and creating trigger volumes. If gate dimensions are wrong or the vehicle passes through too quickly (tunneling), checkpoints may not register.
**Mitigation**: (1) Use conservative trigger volumes (larger than the visual gate). (2) Implement sweep testing: check if the vehicle's movement vector between ticks intersects the trigger volume (prevents tunneling at high speed). (3) Parse waypoint properties from GBX data rather than relying solely on block name matching.
**Owner**: MVP-055

### Risk 8: SharedArrayBuffer COOP/COEP Header Issues
**Probability**: LOW
**Impact**: MEDIUM -- physics must run on main thread, reducing performance
**Description**: SharedArrayBuffer requires `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers. These can conflict with third-party resource loading. Some hosting platforms may not support these headers.
**Mitigation**: (1) Configure dev server with correct headers from day one. (2) If headers are problematic, run physics on main thread (simpler, slightly worse performance). (3) Use `postMessage` as a fallback for worker communication (adds 1-2 frames of latency).
**Owner**: MVP-047

### Risk 9: Mobile Browser WebGPU Support Gaps
**Probability**: HIGH
**Impact**: LOW (mobile is stretch goal for MVP)
**Description**: WebGPU support on mobile browsers (especially iOS Safari) is still emerging in 2026. Some features (compute shaders, specific texture formats) may not be available.
**Mitigation**: (1) Treat mobile as a best-effort feature, not a requirement. (2) Show a clear "not supported" message on incompatible browsers. (3) Consider WebGL2 fallback for wider compatibility (post-MVP).
**Owner**: MVP-067

### Risk 10: WASM-JS Boundary Overhead for Physics
**Probability**: LOW
**Impact**: MEDIUM -- physics tick may take too long if data transfer is slow
**Description**: Each physics tick reads input from JS and writes vehicle state back. If this involves serializing/deserializing large structures across the WASM boundary, the overhead could exceed the 10ms tick budget.
**Mitigation**: (1) Use SharedArrayBuffer for zero-copy data sharing between JS and WASM. (2) Keep the WASM-JS interface minimal: pass pointers to shared memory, not serialized objects. (3) Batch multiple physics ticks before reading state back to JS. (4) Profile WASM call overhead early (MVP-035).
**Owner**: MVP-035, MVP-047

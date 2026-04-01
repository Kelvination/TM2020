# WASM Floating-Point Determinism Analysis

WebAssembly can guarantee bit-identical floating-point physics across browsers for ghost validation and competitive integrity. This requires specific engineering constraints but no exotic techniques.

**Verdict**: CONDITIONALLY YES -- achievable with discipline.

---

## WASM Float Specification

### The Core Guarantee

The WASM specification (v3.0, 2026) guarantees: if neither the inputs nor the output of a floating-point instruction is NaN, the output is deterministic across all platforms. Dan Gohman (WASM spec contributor) confirmed in [design issue #1385](https://github.com/WebAssembly/design/issues/1385): "Yes, it's correct. Wasm's floating-point is deterministic, other than NaN bit patterns."

### IEEE 754 Compliance

WASM specifies round-to-nearest ties-to-even (the IEEE 754 default). No other rounding modes are accessible. Operations on f32 produce f32 results with no extended precision (no x87-style 80-bit intermediates). Compiler optimizations that change effective precision, rounding, or range are explicitly forbidden. Implementations may NOT contract or fuse operations to elide intermediate rounding steps. Full IEEE 754 subnormal support is required for scalar operations.

### Deterministic Operations

| Category | Operations | Deterministic? |
|---|---|---|
| Arithmetic | `f32.add`, `f32.sub`, `f32.mul`, `f32.div` | YES |
| Square root | `f32.sqrt` | YES |
| Comparison | `f32.eq`, `f32.lt`, `f32.gt`, `f32.le`, `f32.ge` | YES |
| Min/Max | `f32.min`, `f32.max` | YES |
| Rounding | `f32.ceil`, `f32.floor`, `f32.trunc`, `f32.nearest` | YES |
| Conversion | `f32.convert_i32_s`, `i32.trunc_f32_s`, etc. | YES |
| Reinterpret | `f32.reinterpret_i32` | YES |
| Sign manipulation | `f32.neg`, `f32.abs`, `f32.copysign` | YES (even NaN bits preserved) |
| Fused multiply-add | `f32.fma` (proposed) | YES (single rounding) |

### Missing Operations

WASM has no built-in `sin`, `cos`, `tan`, `atan2`, `exp`, `log`, `pow`, `asin`, `acos`. These must come from library code compiled to WASM or imported from the host. This is good for determinism -- see the mitigation strategies below.

### The NaN Exception

The ONLY floating-point nondeterminism is NaN bit patterns. When multiple NaN inputs are present, which payload propagates is nondeterministic. When an operation produces NaN from non-NaN inputs (e.g., `0.0 / 0.0`), the sign bit is nondeterministic. The WASM 3.0 deterministic profile produces a positive canonical NaN in ambiguous cases. Browser adoption status is unclear.

---

## Known Nondeterminism Sources

### Sources That Affect Us

**NaN Bit Patterns (MEDIUM RISK)**: NaN values should NEVER appear in normal simulation. TM2020 guards against this with negative-sqrt checks. If NaN appears, the simulation is invalid regardless.

**Transcendental Functions (HIGH RISK if mishandled)**: `sin`, `cos`, `atan2` are NOT WASM built-ins.
- **Option A: Import from JavaScript `Math`** -- NONDETERMINISTIC. Browser engines use different algorithms.
- **Option B: Compile a software implementation (Rust `libm`)** -- DETERMINISTIC. The same WASM bytecode runs identically on all engines.
- **Option C: Custom lookup tables** -- DETERMINISTIC.

MUST use compiled-in implementations. NEVER import browser Math functions for physics.

**Relaxed SIMD (HIGH RISK if used)**: Explicitly introduces local non-determinism. Do not use for physics.

**Rust Compiler Nondeterminism (MEDIUM RISK)**: Rust does not guarantee bit-identical WASM output across compiler versions or host OS during compilation. This does NOT affect whether the SAME WASM binary produces the same results across browsers. Ship one WASM binary to all clients.

### Sources That Do NOT Affect Us

| Source | Why It's Not a Problem |
|---|---|
| SharedArrayBuffer / threads | Single-threaded physics (same as TM2020) |
| FMA instruction fusion | WASM spec forbids implicit fusion; `f32.mul` + `f32.add` always rounds twice |
| x87 extended precision | WASM uses 32/64-bit only |
| Subnormal flush-to-zero | WASM scalar ops require full subnormal support |
| Rounding mode differences | WASM only supports round-to-nearest |

### The FMA Question

In native code, compilers may implicitly fuse `a * b + c` into a single FMA instruction, changing rounding. In WASM, this is NOT a problem. The specification explicitly states implementations are not permitted to contract or fuse operations. A `f32.mul` followed by `f32.add` always produces two rounding steps.

---

## Mitigation Strategies

### Compiled-In Math Library (RECOMMENDED)

Use Rust's `libm` crate for ALL transcendental functions. This compiles sin, cos, atan2, exp, log to pure WASM bytecode using only basic operations. If the WASM bytecode is identical and basic operations are deterministic, the composed function is deterministic. Performance: compiled libm sin/cos is approximately 10x slower than browser-native Math.sin. For a physics engine computing a few trig functions per tick per vehicle, this is negligible.

### NaN Prevention (REQUIRED)

Follow TM2020's pattern: prevent NaN from entering the simulation. Guard every `sqrt` call (`if x < 0.0 { x = 0.0 } sqrt(x)`). Guard every division (check for zero denominator). Clamp velocities and positions. Validate all inputs.

### Avoid Relaxed SIMD

Use only standard WASM SIMD (128-bit fixed-width) for physics. Standard SIMD follows the same determinism rules as scalar operations.

### Single WASM Binary

Ship exactly one `.wasm` binary to all clients. The binary IS the physics specification.

### Determinism Hash Verification

After each physics tick, compute a hash of the full simulation state. Compare between client and server, between clients in multiplayer, and between live play and ghost replay.

---

## TM2020's Approach (from Decompilation)

TM2020 achieves determinism through:

**Integer-Based Timing**: Time tracks as integer tick counts (100Hz = 10ms per tick). Tick-to-microsecond conversion uses integer multiplication. No `time += deltaTime` accumulation. This eliminates time-base drift.

**Fixed 100Hz Timestep**: Physics runs at exactly 100Hz. Display framerate is decoupled. Running at 30fps vs 300fps produces identical physics.

**Deterministic Sub-Stepping**: Within each 10ms tick, adaptive sub-stepping divides the timestep based on velocity:
```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = clamp(floor(total_speed * scale * dt / step_size) + 1, 1, 1000)
sub_dt = dt / num_substeps
```

**Guarded Square Root**: Every sqrt call has a negative check:
```c
if (fVar24 < 0.0) {
    fVar24 = safe_sqrt(fVar24);  // handles negative input
} else {
    fVar24 = SQRT(fVar24);       // SSE sqrtss
}
```

**Sequential Body Processing**: Bodies process in array order via sequential iteration. No parallel dispatch, no random ordering.

**SSE on x64**: TM2020 is compiled for x64, using SSE for all float operations. Determinism is guaranteed within the same build and platform. Cross-architecture determinism is NOT guaranteed.

**Input-Based Replays**: The ghost system records inputs per tick, not positions. Server-side anti-cheat re-runs the physics to verify claimed times.

### OpenTM Mapping

| TM2020 Mechanism | OpenTM WASM Equivalent |
|---|---|
| SSE (same-platform deterministic) | WASM spec (cross-platform deterministic) |
| Same binary = same results | Same `.wasm` binary = same results (stronger guarantee) |
| Integer tick counting | Identical approach (i32/i64 ticks) |
| Guarded sqrt | Identical approach |
| Sequential processing | Identical approach (WASM is single-threaded) |
| 100Hz fixed timestep | Same (100Hz) |

OpenTM has a STRONGER determinism foundation. WASM guarantees cross-architecture consistency for basic float operations, while SSE only guarantees same-architecture consistency.

---

## Recommended Strategy for OpenTM

### Architecture

```
[Physics Engine (Rust)] --> [Compiled to .wasm] --> [Same binary to all clients]
                                                         |
                                    +--------------------+--------------------+
                                    |                    |                    |
                               Chrome/V8          Firefox/SpiderMonkey   Safari/JSC
                                    |                    |                    |
                              Identical results    Identical results    Identical results
```

### Engineering Rules

1. Use f32 for all physics (same as TM2020). f64 is unnecessary.
2. Compile ALL math into WASM via `libm`. NEVER call JavaScript Math functions from physics.
3. No relaxed SIMD. Standard SIMD only, or pure scalar.
4. Guard every sqrt. Clamp input to >= 0.0.
5. Guard every division. Check for zero/near-zero denominators.
6. Integer tick counting. `tick * 1_000_000` for microseconds, integer multiply only.
7. Fixed 100Hz timestep. No variable timestep.
8. Sequential processing. No threading in physics.
9. Single .wasm binary. Pin Rust compiler version.
10. Determinism verification hash every tick.

### What This Does NOT Require

- No fixed-point arithmetic
- No software float emulation (softfloat)
- No NaN canonicalization pass
- No special browser flags or APIs
- No platform-specific code paths

---

## Fixed-Point Alternative Analysis

Fixed-point arithmetic (e.g., Q16.16) represents real numbers as integers with an implicit scale factor. It provides absolute determinism but carries significant costs.

**Precision**: Q16.16 provides ~4.8 decimal digits vs f32's ~7.2. The overflow problem is severe -- velocities reach 1000+ km/h in TM, and Q16.16 overflows at 32768.

**Performance**: Basic arithmetic is 10-20x slower. Fixed-point division requires widening to 64-bit.

**Verdict**: Not recommended. The engineering cost and performance penalty are not justified when WASM's float determinism guarantees are sufficient. Fixed-point becomes the fallback strategy only if cross-browser testing reveals WASM float nondeterminism in practice.

---

## Test Plan

### Phase 1: Basic Operation Verification

Write a WASM module that performs every float operation used in physics and hashes the results:

```rust
// test_determinism.rs -> test_determinism.wasm
fn test_basic_ops() -> u64 {
    let mut hasher = FnvHasher::new();

    // Basic arithmetic
    hash(&mut hasher, 1.0f32 + 0.1f32);
    hash(&mut hasher, 1.0f32 - 0.1f32);
    hash(&mut hasher, 1.0f32 * 0.1f32);
    hash(&mut hasher, 1.0f32 / 0.3f32);

    // Edge cases
    hash(&mut hasher, f32::MIN_POSITIVE * 0.5); // subnormal
    hash(&mut hasher, 1.0e38f32 + 1.0e38f32);  // overflow to inf
    hash(&mut hasher, f32::sqrt(2.0));
    hash(&mut hasher, f32::sqrt(0.0));

    // Transcendental (compiled libm)
    hash(&mut hasher, libm::sinf(0.1));
    hash(&mut hasher, libm::cosf(0.1));
    hash(&mut hasher, libm::atan2f(1.0, 1.0));

    hasher.finish()
}
```

Run across Chrome (V8), Firefox (SpiderMonkey), Safari (JSC) on Windows x64, macOS ARM64, Linux x64. Expect identical hash.

### Phase 2: Physics Simulation Divergence

Run the physics engine for 10,000 ticks (100 seconds) with predefined inputs. Hash the full vehicle state every tick. Compare across browsers and architectures.

### Phase 3: Edge Case Stress

| Test Case | Why It's Risky |
|---|---|
| Very high speed (1000+ km/h) | Large sub-step counts |
| Very slow speed (< 0.01 km/h) | Subnormal values possible |
| Grazing collision angle | Near-zero contact normals |
| Extended air time (10+ seconds) | Accumulated gravity integration |
| Rapid surface transitions | Many contact state changes per tick |

### Phase 4: Long-Duration Ghost Validation

Record a ghost on Chrome. Replay on Firefox and Safari. Compare final position (bit-identical), final time (identical), and intermediate checkpoints. Test runs of 10s, 60s, 300s, 900s.

---

## Verdict: Determinism is Achievable

### Required Conditions

| # | Condition | Difficulty |
|---|---|---|
| 1 | Ship same `.wasm` binary to all clients | Easy |
| 2 | Compile all math into WASM via `libm` | Easy |
| 3 | Never import JavaScript `Math` for physics | Easy |
| 4 | Never use relaxed SIMD for physics | Easy |
| 5 | Prevent NaN from entering simulation | Medium |
| 6 | Use fixed timestep with integer tick counting | Medium |
| 7 | Process bodies in deterministic order | Medium |
| 8 | Pin Rust compiler version | Easy |
| 9 | Run cross-browser determinism tests in CI | Medium |

### Remaining Risks

1. **Browser engine bugs**: A JIT compiler could miscompile a WASM float operation. Mitigation: hash verification catches this at runtime.
2. **Spec loopholes**: The WASM spec is large. Mitigation: exhaustive testing.
3. **Future WASM proposals**: Relaxed SIMD, flexible vectors. Mitigation: never use them for physics.
4. **Rust `libm` changes**: Updating the crate may break replay compatibility. Mitigation: pin version, version ghost format.

### Comparison to TM2020

| Aspect | TM2020 | OpenTM (WASM) |
|---|---|---|
| Float determinism basis | SSE on x64 (same-platform) | WASM spec (cross-platform) |
| Cross-architecture | NOT guaranteed | Guaranteed by spec |
| Cross-build | NOT guaranteed | Same `.wasm` binary = guaranteed |
| Transcendental functions | Native x64 (compiler-determined) | Compiled `libm` (deterministic) |
| NaN prevention | Guarded sqrt pattern | Same pattern |

**Proceed with f32 floating-point physics in WASM. Do not use fixed-point. Implement NaN prevention and compiled-in math. Test across browsers early and continuously.**

---

## Sources

### WebAssembly Specification
- [WebAssembly 3.0 Numerics](https://webassembly.github.io/spec/core/exec/numerics.html)
- [WebAssembly 3.0 Values](https://webassembly.github.io/spec/core/syntax/values.html)
- [WebAssembly Design: Nondeterminism](https://github.com/WebAssembly/design/blob/master/Nondeterminism.md)
- [WebAssembly Design Issue #1385: Determinism with non-NaN results](https://github.com/WebAssembly/design/issues/1385)
- [WebAssembly Design Issue #619: NaN bits not fully deterministic](https://github.com/WebAssembly/design/issues/619)
- [WebAssembly Design Issue #148: Subnormals](https://github.com/WebAssembly/design/issues/148)
- [WebAssembly Design Issue #1463: NaN canonicalization motivation](https://github.com/WebAssembly/design/issues/1463)

### FMA and SIMD
- [WebAssembly Relaxed SIMD: Deterministic FMA](https://github.com/WebAssembly/relaxed-simd/issues/44)
- [WebAssembly SIMD: FMA instruction](https://github.com/WebAssembly/design/issues/1391)
- [WebAssembly SIMD: Quasi-FMA proposal](https://github.com/WebAssembly/simd/pull/79)

### Rust and WASM
- [Rust Float Semantics RFC 3514](https://rust-lang.github.io/rfcs/3514-float-semantics.html)
- [Rust Issue #117597: Non-deterministic wasm32 output across OS](https://github.com/rust-lang/rust/issues/117597)
- [Hunting down a non-determinism-bug in Rust WASM build](https://dev.to/gnunicorn/hunting-down-a-non-determinism-bug-in-our-rust-wasm-build-4fk1)
- [Rapier Physics: Determinism](https://rapier.rs/docs/user_guides/rust/determinism/)
- [rust-lang/libm](https://deepwiki.com/rust-lang/libm)

### Game Physics Determinism
- [Gaffer on Games: Floating Point Determinism](https://gafferongames.com/post/floating_point_determinism/)
- [Gaffer on Games: Deterministic Lockstep](https://gafferongames.com/post/deterministic_lockstep/)
- [Box2D: Determinism](https://box2d.org/posts/2024/08/determinism/)
- [Deterministic Physics in TypeScript: Fixed-Point Engine](https://dev.to/shaisrc/deterministic-physics-in-ts-why-i-wrote-a-fixed-point-engine-4b0l)
- [Cross-Platform RTS Synchronization](https://www.gamedeveloper.com/programming/cross-platform-rts-synchronization-and-floating-point-indeterminism)

### WASM Determinism in Practice
- [Determinism & WASM (Haderech/Medium)](https://medium.com/haderech-dev/determinism-wasm-40e0a03a9b45)
- [Wasmtime: Deterministic Execution](https://docs.wasmtime.dev/examples-deterministic-wasm-execution.html)
- [WASM Float Determinism Test (Zig)](https://github.com/meheleventyone/wasm-float-determinism-test)
- [Arbitrum: WAVM Floating Point](https://docs.arbitrum.io/how-arbitrum-works/fraud-proofs/wavm-floats)
- [Trigonometric Functions in WebAssembly](https://www.nhatcher.com/post/should_i_import_or_should_i_roll/)

### Browser-Based Lockstep
- [Deterministic Lockstep Demo (browser)](https://github.com/pietrobassi/deterministic-lockstep-demo)
- [Babylon.js: Deterministic Lockstep](https://forum.babylonjs.com/t/how-do-i-use-deterministic-lockstep-to-help-sync-clients/17008)

---

## Related Pages

- [Physics Engine](02-physics-engine.md) -- Determinism strategy and transcendental function handling
- [Physics Constants](07-physics-constants.md) -- Data-driven constants loaded from GBX
- [Executive Summary](00-executive-summary.md) -- Risk assessment for WASM determinism

<details><summary>Document metadata</summary>

- **Date**: 2026-03-27
- **Purpose**: Determine whether WebAssembly can guarantee bit-identical floating-point physics across browsers for ghost validation and competitive integrity.

</details>

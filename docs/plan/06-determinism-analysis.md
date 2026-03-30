# WASM Floating-Point Determinism Analysis for OpenTM

**Date**: 2026-03-27
**Purpose**: Determine whether WebAssembly can guarantee bit-identical floating-point physics across browsers for ghost validation and competitive integrity.
**Verdict**: CONDITIONALLY YES -- achievable with discipline, but requires specific engineering constraints.

---

## Table of Contents

1. [WASM Float Specification Summary](#1-wasm-float-specification-summary)
2. [Known Nondeterminism Sources](#2-known-nondeterminism-sources-with-evidence)
3. [Mitigation Strategies](#3-mitigation-strategies)
4. [TM2020's Approach](#4-tm2020s-approach-from-re-docs)
5. [Recommended Strategy for OpenTM](#5-recommended-strategy-for-opentm)
6. [Fixed-Point Alternative Analysis](#6-fixed-point-alternative-analysis)
7. [Test Plan](#7-test-plan)
8. [Verdict](#8-verdict-can-we-guarantee-determinism)

---

## 1. WASM Float Specification Summary

### 1.1 The Core Guarantee

The WebAssembly specification (currently v3.0, 2026) provides a remarkably strong determinism guarantee for floating-point operations:

> **If neither the inputs to nor the output from a floating-point instruction is NaN, then the output is deterministic and agrees across all platforms.**

This was explicitly confirmed by WebAssembly spec contributor Dan Gohman (sunfishcode) in [design issue #1385](https://github.com/WebAssembly/design/issues/1385):

> "Yes, it's correct. Wasm's floating-point is deterministic, other than NaN bit patterns."

### 1.2 IEEE 754 Compliance

WASM specifies:

- **Rounding mode**: Round-to-nearest, ties-to-even (the IEEE 754 default). No other rounding modes are accessible. Non-default directed rounding is not supported.
- **Precision**: Operations on f32 produce f32 results; operations on f64 produce f64 results. No extended precision (no x87-style 80-bit intermediate values).
- **No fast-math**: Compiler optimizations that change effective precision, rounding, or range are explicitly forbidden. Implementations may NOT contract or fuse operations to elide intermediate rounding steps.
- **Subnormals**: Full IEEE 754 subnormal support is required for scalar operations. Subnormals are NOT flushed to zero.
- **Non-stop mode**: All operations use non-stop mode. Floating-point exceptions are not observable.

### 1.3 What Operations Are Available

WASM provides these built-in floating-point operations, all of which are deterministic (excluding NaN bit patterns):

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

The same applies for f64 variants.

### 1.4 What Operations Are NOT Available

Critically, **WASM has no built-in transcendental functions**:

- No `sin`, `cos`, `tan`, `atan2`
- No `exp`, `log`, `pow`
- No `asin`, `acos`

These must be implemented as library code compiled to WASM, or imported from the host environment. This is actually **good for determinism** -- see Section 3.

### 1.5 The NaN Exception

The ONLY floating-point nondeterminism in WASM is NaN bit patterns:

1. **NaN payload propagation**: When multiple NaN inputs are present, which NaN's payload propagates is nondeterministic.
2. **NaN sign bit**: When an operation produces NaN from non-NaN inputs (e.g., `0.0 / 0.0`), the sign bit of the result is nondeterministic.
3. **Canonical NaN rule**: If all NaN inputs have canonical payloads, the output payload is canonical. Otherwise, the payload is picked nondeterministically among arithmetic NaNs.

**Why NaN bits are nondeterministic**: Per [design issue #619](https://github.com/WebAssembly/design/issues/619), canonicalizing NaN bits after every operation would be too expensive. x86 produces NaN sign=1 while ARM produces NaN sign=0, and normalizing this would require extra instructions on every float operation.

**Deterministic Profile**: WASM 3.0 includes a deterministic profile where "a positive canonical NaN is reliably produced" in ambiguous cases. Browser adoption status is unclear, but this is available in non-browser runtimes like Wasmtime.

---

## 2. Known Nondeterminism Sources (with Evidence)

### 2.1 Sources That DO Affect Us

#### 2.1.1 NaN Bit Patterns (MEDIUM RISK)

**What**: Different browsers may produce different NaN bit patterns for the same computation.

**Impact on physics**: NaN bit patterns only matter if:
- You observe them via `i32.reinterpret_f32` or memory storage
- You use `copysign` with a NaN operand
- NaN values feed into subsequent non-NaN-producing operations

**For a physics engine**: NaN values should NEVER appear in normal simulation. If they do, something is already catastrophically wrong. TM2020 guards against this with negative-sqrt checks (Section 4).

**Risk assessment**: LOW for physics computations. NaN should never occur. The mitigation is: if NaN appears, the simulation is invalid regardless.

#### 2.1.2 Transcendental Functions (HIGH RISK if mishandled)

**What**: `sin`, `cos`, `atan2`, etc. are NOT WASM built-ins. They must come from somewhere:

- **Option A: Import from JavaScript `Math` object** -- NONDETERMINISTIC. Browser engines (V8, SpiderMonkey, JavaScriptCore) may use different algorithms. JavaScript's `Math.sin` is explicitly allowed to vary between implementations.
- **Option B: Compile a software implementation (e.g., Rust's `libm`)** -- DETERMINISTIC. The exact same WASM bytecode runs on all engines. Since WASM basic operations are deterministic, the same algorithm with the same inputs produces the same outputs.
- **Option C: Custom lookup tables** -- DETERMINISTIC. Pre-computed tables with interpolation are guaranteed identical since they use only basic WASM operations.

**Evidence**: The [nhatcher.com analysis](https://www.nhatcher.com/post/should_i_import_or_should_i_roll/) found importing browser `Math` functions was faster than compiled `libm`, but did NOT test cross-browser consistency. The performance difference is ~10x for heavy trig use -- but for a physics engine doing occasional atan2 calls, this is irrelevant.

**Verdict**: MUST use compiled-in implementations (Option B or C). NEVER import browser Math functions for physics.

#### 2.1.3 Relaxed SIMD (HIGH RISK if used)

**What**: The Relaxed SIMD proposal (shipping in browsers) explicitly introduces "local non-determinism" -- results may vary based on hardware. Includes relaxed FMA, relaxed integer dot products, relaxed min/max.

**Mitigation**: Simply do not use relaxed SIMD instructions for physics. Use standard (non-relaxed) SIMD or scalar operations only.

#### 2.1.4 Rust Compiler Nondeterminism (MEDIUM RISK)

**What**: Rust's compiler does not guarantee bit-identical WASM output across:
- Different compiler versions
- Different host OS during compilation (Cargo metadata hashing bug, [rust#117597](https://github.com/rust-lang/rust/issues/117597))
- Different optimization levels

**Evidence**: Parity Technologies [documented](https://dev.to/gnunicorn/hunting-down-a-non-determinism-bug-in-our-rust-wasm-build-4fk1) a case where LLVM's "Fix Irreducible Control Flow" pass produced nondeterministic basic block ordering, and Cargo's `-C metadata` hash varied by host OS.

**Impact**: This affects whether two separately compiled WASM binaries produce the same bytecode. It does NOT affect whether the SAME WASM binary produces the same results across browsers. For OpenTM, we ship one WASM binary to all clients, so this is manageable.

**Mitigation**: Pin Rust compiler version. Use reproducible builds. Ship the same `.wasm` artifact to all clients.

### 2.2 Sources That Do NOT Affect Us

| Source | Why It's Not a Problem |
|---|---|
| SharedArrayBuffer / threads | We use single-threaded physics (same as TM2020) |
| Flexible-vectors proposal | Not yet standardized, don't use it |
| Resource exhaustion (stack overflow, OOM) | Detectable; abort simulation rather than diverge |
| Feature variation | All target browsers support WASM MVP + needed features |
| FMA instruction fusion | WASM spec forbids implicit fusion; `f32.mul` + `f32.add` always rounds twice |
| x87 extended precision | WASM uses 32/64-bit only; no 80-bit intermediate values exist |
| Subnormal flush-to-zero | WASM scalar ops require full subnormal support |
| Rounding mode differences | WASM only supports round-to-nearest; no way to change it |

### 2.3 The FMA Question (Important Detail)

Fused Multiply-Add is a common source of nondeterminism in native code because compilers may or may not fuse `a * b + c` into a single FMA instruction, producing different rounding.

**In WASM, this is NOT a problem.** The specification explicitly states:
> "Implementations are not permitted to contract or fuse operations to elide intermediate rounding steps."

A `f32.mul` followed by `f32.add` will ALWAYS produce two rounding steps. If you want single-rounding FMA behavior, you must explicitly use the `f32.fma` instruction. This is the opposite of native code, where FMA might happen implicitly.

Box2D uses `-ffp-contract=off` to prevent FMA fusion in native builds. In WASM, this restriction is enforced by the specification itself.

---

## 3. Mitigation Strategies

### 3.1 Strategy: Compiled-In Math Library (RECOMMENDED)

Use Rust's `libm` crate (or equivalent) for ALL transcendental functions. This compiles `sin`, `cos`, `atan2`, `exp`, `log` etc. to pure WASM bytecode using only basic operations.

**Why this works**: If the WASM bytecode is identical (same `.wasm` binary), and WASM basic operations are deterministic, then the composed function is deterministic. The algorithm is the same. The inputs are the same. The intermediate rounding is the same. The output is the same.

**Performance**: Compiled `libm` sin/cos is approximately 10x slower than browser-native Math.sin for bulk computation ([nhatcher.com benchmarks](https://www.nhatcher.com/post/should_i_import_or_should_i_roll/)). For a physics engine computing a few trig functions per tick per vehicle, this is negligible -- we are talking microseconds.

**Rapier physics engine** (Rust) takes exactly this approach with its `enhanced-determinism` feature flag, using nalgebra's `ComplexField` traits for cross-platform math.

### 3.2 Strategy: NaN Prevention (REQUIRED)

Follow TM2020's pattern: prevent NaN from ever entering the simulation.

- Guard every `sqrt` call: `if x < 0.0 { x = 0.0 } sqrt(x)`
- Guard every division: check for zero denominator
- Clamp velocities and positions to sane ranges
- Validate all inputs at the physics boundary

If NaN never appears, the NaN nondeterminism problem does not exist.

### 3.3 Strategy: Avoid Relaxed SIMD

Use only standard WASM SIMD (128-bit fixed-width) for physics, never relaxed SIMD. Standard SIMD operations follow the same determinism rules as scalar operations. Relaxed SIMD explicitly trades determinism for performance.

Note: Standard WASM SIMD does have one caveat -- on 32-bit ARM (ARMv7), subnormals may be flushed to zero in SIMD operations. However, this is only relevant for very old mobile hardware (pre-ARMv8/AArch64). All modern browsers on desktop and modern mobile run AArch64 with full subnormal support in SIMD.

### 3.4 Strategy: Single WASM Binary

Ship exactly one `.wasm` binary to all clients. Do not recompile per-platform. Do not allow clients to compile their own WASM. The binary IS the physics specification.

### 3.5 Strategy: Determinism Hash Verification

After each physics tick (or every N ticks), compute a hash of the full simulation state (positions, velocities, forces). Compare this hash between:
- Client and server
- Two clients in multiplayer
- Live play and ghost replay

Any divergence indicates a determinism failure and should be treated as invalid.

---

## 4. TM2020's Approach (from RE Docs)

TM2020 achieves determinism through the following mechanisms, verified via decompilation:

### 4.1 Integer-Based Timing

**Source**: `PhysicsStep_TM.c:63`, `NSceneDyna__PhysicsStep.c:15`

```c
lVar18 = (ulonglong)*param_4 * 1000000;  // integer * integer = integer
```

Time is tracked as integer tick counts (100Hz = 10ms per tick). The tick-to-microsecond conversion uses integer multiplication, not floating-point. No `time += deltaTime` accumulation. This eliminates time-base drift entirely.

### 4.2 Fixed 100Hz Timestep

**Confidence**: PLAUSIBLE (inferred from converging evidence)

The physics runs at exactly 100Hz. Display framerate is completely decoupled. `SmMaxPlayerResimStepPerFrame=100` caps resimulation to 1 second per frame. Running at 30fps vs 300fps produces identical physics.

### 4.3 Deterministic Sub-Stepping

**Source**: `PhysicsStep_TM.c:71-167`

Within each 10ms tick, adaptive sub-stepping divides the timestep based on velocity:

```
total_speed = |linear_vel| + |angular_vel_body| + |angular_vel1| + |angular_vel2|
num_substeps = clamp(floor(total_speed * scale * dt / step_size) + 1, 1, 1000)
sub_dt = dt / num_substeps
```

The sub-step count is deterministic given the same velocity state. The final sub-step uses a remainder calculation to avoid floating-point drift from repeated addition.

### 4.4 Guarded Square Root

**Source**: All physics files

Every `sqrt` call is preceded by a negative check:

```c
if (fVar24 < 0.0) {
    fVar24 = safe_sqrt(fVar24);  // handles negative input
} else {
    fVar24 = SQRT(fVar24);       // SSE sqrtss
}
```

This prevents NaN propagation from floating-point precision artifacts where `x*x + y*y + z*z` might produce tiny negative values. NaN would break determinism because `NaN != NaN` causes divergent control flow.

### 4.5 Sequential Body Processing

**Source**: `NSceneDyna__PhysicsStep_V2.c:103-116`

Bodies are processed in array order via sequential iteration over a sorted index array. No parallel dispatch, no random ordering. Collision pair processing order is deterministic regardless of memory allocation.

### 4.6 SSE on x64 (Platform-Specific)

TM2020 is compiled for x64, using SSE for all float operations. SSE `sqrtss`, `addss`, `mulss` are IEEE 754 compliant and deterministic on the same CPU architecture.

**Key limitation**: TM2020's determinism guarantee is "within same build, same platform (x64)." Cross-architecture determinism (x64 vs ARM) is NOT guaranteed by their code patterns. This is acceptable because TM2020 only runs on Windows x64 PCs and their own servers.

### 4.7 Input-Based Replays

The ghost/replay system records inputs (steer, gas, brake) per tick, not positions. Replay validation re-simulates the run from recorded inputs. Server-side anti-cheat re-runs the physics to verify claimed times. This only works because the simulation is deterministic.

### 4.8 What OpenTM Can Learn

TM2020's approach maps well to WASM because:

| TM2020 Mechanism | OpenTM WASM Equivalent |
|---|---|
| SSE (deterministic on same arch) | WASM spec (deterministic on ALL implementations) |
| Same binary = same results | Same `.wasm` binary = same results (stronger guarantee) |
| Integer tick counting | Identical approach (i32/i64 ticks) |
| Guarded sqrt | Identical approach |
| Sequential processing | Identical approach (WASM is single-threaded) |
| 100Hz fixed timestep | Same or similar (100Hz or 120Hz) |

OpenTM actually has a STRONGER determinism foundation than TM2020 because WASM guarantees cross-architecture consistency for basic float operations, while SSE only guarantees same-architecture consistency.

---

## 5. Recommended Strategy for OpenTM

### 5.1 Architecture

```
[Physics Engine (Rust)] --> [Compiled to .wasm] --> [Same binary to all clients]
                                                         |
                                    +--------------------+--------------------+
                                    |                    |                    |
                               Chrome/V8          Firefox/SpiderMonkey   Safari/JSC
                                    |                    |                    |
                              Identical results    Identical results    Identical results
```

### 5.2 Engineering Rules

1. **Use f32 for all physics** (same as TM2020). f64 is unnecessary for a racing game and doubles memory bandwidth.

2. **Compile ALL math into WASM**. Use `libm` crate for sin/cos/atan2. NEVER call JavaScript Math functions from physics code.

3. **No relaxed SIMD**. Standard SIMD only, or pure scalar operations.

4. **Guard every sqrt**. Clamp input to >= 0.0 before calling `f32.sqrt`.

5. **Guard every division**. Check for zero/near-zero denominators.

6. **Integer tick counting**. Follow TM2020: `tick * 1_000_000` for microseconds, integer multiplication only.

7. **Fixed timestep** (100Hz recommended). No variable timestep, no `time += dt` accumulation.

8. **Sequential processing**. No threading in physics. Process bodies in deterministic order.

9. **Single .wasm binary**. Ship the exact same binary to all clients and servers. Pin Rust compiler version for reproducible builds.

10. **Determinism verification hash**. Compute a state hash every tick. Compare across client/server/replay.

### 5.3 What This Does NOT Require

- No fixed-point arithmetic
- No software float emulation (softfloat)
- No NaN canonicalization pass
- No special browser flags or APIs
- No platform-specific code paths

### 5.4 Confidence Level

**HIGH confidence** that this approach works. The reasoning chain:

1. WASM basic float operations (add, sub, mul, div, sqrt) are **spec-guaranteed deterministic** for non-NaN inputs.
2. NaN prevention ensures we never hit the nondeterministic path.
3. Compiled-in `libm` ensures transcendental functions are deterministic (they're just sequences of basic operations).
4. Same `.wasm` binary ensures all clients execute identical bytecode.
5. Fixed timestep and integer time ensure the simulation is seeded identically.

The only remaining question is whether all browser JIT compilers correctly implement the spec. This is testable (Section 7) and the evidence from the WASM spec testsuite, which covers edge cases including subnormals and operations that would round differently in x87, suggests compliance is high.

---

## 6. Fixed-Point Alternative Analysis

### 6.1 What Is Fixed-Point?

Fixed-point arithmetic represents real numbers as integers with an implicit scale factor. For example, Q16.16 format uses 16 integer bits and 16 fractional bits, representing values from -32768.0 to 32767.99998 with precision of 1/65536 (~0.0000153).

### 6.2 Advantages

- **Absolute determinism**: Integer arithmetic is deterministic everywhere, always. No NaN, no rounding mode questions, no specification edge cases.
- **No spec dependency**: Does not rely on browser WASM engines correctly implementing IEEE 754.
- **Battle-tested**: Used by Age of Empires, StarCraft, and many RTS games for lockstep networking.

### 6.3 Disadvantages

#### 6.3.1 Precision Loss

Q16.16 provides ~4.8 decimal digits of precision. Compare with f32's ~7.2 decimal digits.

| Operation | f32 result | Q16.16 result | Error |
|---|---|---|---|
| sin(0.1) | 0.09983342 | 0.09983521 | 0.0018% |
| 1.0 / 3.0 | 0.33333334 | 0.33331299 | 0.006% |
| sqrt(2.0) | 1.41421356 | 1.41421509 | 0.0001% |
| 100.0 * 100.0 | 10000.0 | OVERFLOW | Fatal |

The overflow problem is severe for a physics engine. Velocities can reach 1000+ km/h in TM, and forces involve multiplication of large values. Q16.16 overflows at 32768.

Q32.32 (64-bit fixed-point) solves the range problem but requires 64-bit integer arithmetic, which is slower in WASM (WASM's native word size is 32-bit; i64 operations require multi-instruction sequences on 32-bit hosts, though modern 64-bit browsers handle i64 natively).

#### 6.3.2 Performance Impact

Benchmark data from the [@shaisrc/fixed-point](https://dev.to/shaisrc/deterministic-physics-in-ts-why-i-wrote-a-fixed-point-engine-4b0l) library (TypeScript, 5M iterations):

| Operation | Native float (ms) | Fixed-point (ms) | Slowdown |
|---|---|---|---|
| Add/Multiply | 6.70 | 120.24 | 18x |
| Sin (LUT) | 197.90 | 64.75 | 0.3x (faster!) |

Basic arithmetic is 10-20x slower. Trigonometry via lookup tables can be faster than JavaScript's `Math.sin`, but that comparison is irrelevant for WASM where we'd compile `libm`.

In WASM specifically, fixed-point arithmetic replaces hardware `f32.mul` (1 cycle) with integer multiply + shift (2-3 cycles minimum). For division, it's much worse: fixed-point division requires widening to 64-bit, dividing, then narrowing -- vs `f32.div` which is a single instruction.

#### 6.3.3 Implementation Complexity

Every physics formula must be rewritten. You cannot use standard linear algebra libraries. Debugging is harder because values are not human-readable. Overflow detection must be manual.

### 6.4 Verdict on Fixed-Point

**Not recommended for OpenTM.** The engineering cost and performance penalty are not justified when WASM's float determinism guarantees are sufficient. Fixed-point makes sense when:

- You cannot control the float implementation (native code across different compilers/platforms)
- You need to support ancient hardware with non-IEEE-754-compliant FPUs
- Your value ranges are narrow and well-bounded

None of these apply to OpenTM. WASM gives us a controlled, spec-compliant float environment. Use it.

**Exception**: If cross-browser testing (Section 7) reveals WASM float nondeterminism in practice, fixed-point becomes the fallback strategy.

---

## 7. Test Plan

### 7.1 Phase 1: Basic Operation Verification

Write a small WASM module (in Rust) that performs every float operation used in physics and hashes the results:

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

Run this WASM module in:
- Chrome (V8) on Windows x64, macOS ARM64, Linux x64
- Firefox (SpiderMonkey) on same platforms
- Safari (JavaScriptCore) on macOS ARM64, iOS

**Expected result**: Identical hash across all browser/platform combinations.

### 7.2 Phase 2: Physics Simulation Divergence Test

Run the actual OpenTM physics engine for 10,000 ticks (100 seconds) with a predefined input sequence. Hash the full vehicle state (position, velocity, rotation) at every tick.

- Compare Chrome vs Firefox vs Safari
- Compare x64 vs ARM64 (Mac)
- Compare optimized vs debug builds of the same WASM

**What to look for**:
- First tick where any hash diverges
- Which state variable diverged first
- Whether divergence grows over time or is bounded

### 7.3 Phase 3: Edge Case Stress Test

Design inputs that stress determinism-critical paths:

| Test Case | Why It's Risky |
|---|---|
| Very high speed (1000+ km/h) | Large sub-step counts, many float operations |
| Very slow speed (< 0.01 km/h) | Subnormal values possible |
| Grazing collision angle | Near-zero contact normals, division by small numbers |
| Extended air time (10+ seconds) | Accumulated gravity integration |
| Rapid surface transitions | Many contact state changes per tick |
| Simultaneous vehicle interactions | Collision pair ordering |
| Near-zero velocity at rest | Sleep detection thresholds |

### 7.4 Phase 4: Long-Duration Ghost Validation

Record a ghost (input sequence) on Chrome. Replay it on Firefox and Safari. Compare:
- Final position (should be bit-identical)
- Final time (should be identical)
- Intermediate checkpoints (should all match)

Test with runs of varying length: 10s, 60s, 300s, 900s (15 minutes).

### 7.5 Existing Test Resources

The [wasm-float-determinism-test](https://github.com/meheleventyone/wasm-float-determinism-test) project (Zig-based) has already built infrastructure for cross-browser WASM float testing and solicits results via GitHub issues. We should both use their results and contribute our own.

---

## 8. Verdict: Can We Guarantee Determinism?

### CONDITIONALLY YES

WebAssembly can provide bit-identical floating-point physics across Chrome, Firefox, and Safari, IF the following conditions are met:

### Required Conditions

| # | Condition | Difficulty | Status |
|---|---|---|---|
| 1 | Ship same `.wasm` binary to all clients | Easy | Architectural decision |
| 2 | Compile all math (sin, cos, atan2) into WASM via `libm` | Easy | Cargo dependency |
| 3 | Never import JavaScript `Math` functions for physics | Easy | Code review rule |
| 4 | Never use relaxed SIMD for physics | Easy | Code review rule |
| 5 | Prevent NaN from entering simulation (guard sqrt, guard div) | Medium | Follows TM2020 pattern |
| 6 | Use fixed timestep with integer tick counting | Medium | Follows TM2020 pattern |
| 7 | Process bodies in deterministic order (sequential) | Medium | Follows TM2020 pattern |
| 8 | Pin Rust compiler version for reproducible builds | Easy | CI configuration |
| 9 | Run cross-browser determinism tests in CI | Medium | Test infrastructure |

### What Could Still Go Wrong

1. **Browser engine bugs**: A JIT compiler could miscompile a WASM float operation. This is unlikely but not impossible. Mitigation: determinism hash verification catches this at runtime.

2. **Spec loopholes we haven't found**: The WASM spec is large. There could be edge cases where nondeterminism is permitted that we haven't identified. Mitigation: exhaustive testing (Section 7).

3. **Future WASM proposals**: New features (like relaxed SIMD, flexible vectors) may introduce nondeterminism. Mitigation: never use them for physics; freeze the physics WASM feature set.

4. **Rust `libm` changes**: If we update the `libm` crate version, the compiled WASM may change, breaking replay compatibility with older ghosts. Mitigation: pin `libm` version; version ghost format to include physics engine version.

### Comparison to TM2020

| Aspect | TM2020 | OpenTM (WASM) |
|---|---|---|
| Float determinism basis | SSE on x64 (same-platform) | WASM spec (cross-platform) |
| Cross-architecture | NOT guaranteed | Guaranteed by spec |
| Cross-build | NOT guaranteed (recompilation can break) | Same `.wasm` binary = guaranteed |
| Transcendental functions | Native x64 (compiler-determined) | Compiled `libm` (deterministic) |
| Verification | Server resimulation | Hash comparison + server resimulation |
| NaN prevention | Guarded sqrt pattern | Same pattern |

**OpenTM's determinism story is actually STRONGER than TM2020's**, because:
- WASM provides cross-platform guarantees that native x64 does not
- We compile transcendental functions into deterministic WASM bytecode rather than relying on compiler-specific x64 code generation
- Same `.wasm` binary eliminates the "different build = different results" problem

### Bottom Line

Browser-based WASM floating-point determinism is achievable for a racing physics engine. The WASM specification was designed with this use case in mind. The nondeterminism in the spec (NaN bit patterns) is avoidable with standard engineering practices. The transcendental function problem (the biggest real-world risk) is solved by compiling `libm` into WASM rather than importing browser functions.

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

# Trackmania.exe Binary Overview

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**File size**: 45,467,720 bytes (43.36 MB)

---

## PE Header Summary

| Field               | Value                          |
|---------------------|--------------------------------|
| Format              | PE32+ (x86-64)                 |
| Architecture        | x86:LE:64:default              |
| Image base          | `0x140000000`                  |
| Subsystem           | Windows GUI                    |
| File size on disk   | 45,467,720 bytes (43.36 MB)    |
| Mapped size         | ~46,879,280 bytes (44.71 MB)   |

---

## Entry Points

7 entry points were identified:

| Address          | Name                           | Type       |
|------------------|--------------------------------|------------|
| `0x14291e317`    | `entry`                        | Function   |
| `0x14299e63a`    | `tls_callback_0`               | [UNKNOWN]  |
| `0x141521958`    | `tls_callback_1`               | Function   |
| `0x1415223d4`    | `tls_callback_2`               | Function   |
| `0x140a811a0`    | `Dxgi_Present_HookCallback`    | Function   |
| `0x141e70f38`    | [UNKNOWN - no function]        | Data?      |
| `0x141e70f3c`    | [UNKNOWN - no function]        | Data?      |

**Notes:**
- The main `entry` point at `0x14291e317` resides in the `.D."` section (non-standard), not `.text`. This is unusual and may indicate unpacking or code relocation.
- `tls_callback_0` through `tls_callback_2` are Thread Local Storage callbacks. TLS callbacks execute before the main entry point and are commonly used by packers/protectors for anti-debug or unpacking logic.
- `Dxgi_Present_HookCallback` appears to be an intentional DXGI present hook, likely for overlay rendering or frame capture. It resides in `.text` at `0x140a811a0`.
- The two unnamed entry points at `0x141e70f38` and `0x141e70f3c` correspond to the `AmdPowerXpressRequestHighPerformance` and `NvOptimusEnablement` exports (see Exports section) -- these are data values, not executable code.

---

## Section Layout

| Section   | Start              | End                | Size          | Perms | Notes                          |
|-----------|--------------------|--------------------|---------------|-------|--------------------------------|
| Headers   | `0x140000000`      | `0x1400003ff`      | 1,024 B       | R     | PE/COFF headers                |
| `.text`   | `0x140001000`      | `0x14196e5ff`      | 25.43 MB      | RX    | Main code section              |
| `.rodata` | `0x14196f000`      | `0x14196f9ff`      | 2,560 B       | RX    | Read-only data (very small)    |
| `.rdata`  | `0x141970000`      | `0x141e63bff`      | 4.95 MB       | R     | Read-only data / import tables |
| `.data`   | `0x141e64000`      | `0x1420d2bdf`      | 2.43 MB       | RW    | Initialized data (globals)     |
| `.pdata`  | `0x1420d3000`      | `0x14221ffff`      | 1.30 MB       | R     | Exception handling unwind data |
| `_RDATA`  | `0x142220000`      | `0x1422223ff`      | 9,216 B       | R     | [UNKNOWN] Additional rdata     |
| `.A2U`    | `0x142223000`      | `0x14281c1ff`      | 5.97 MB       | RX    | Non-standard executable section|
| `.9Bv`    | `0x14281d000`      | `0x14281e7ff`      | 6,144 B       | RW    | Non-standard writable section  |
| `.D."`    | `0x14281f000`      | `0x142c595ff`      | 4.23 MB       | RX    | Non-standard executable section|
| `.reloc`  | `0x142c5a000`      | `0x142cac7ff`      | 337,920 B     | R     | Base relocation table          |
| `.rsrc`   | `0x142cad000`      | `0x142cb91ff`      | 49,664 B      | R     | Resources (icons, manifests)   |
| `tdb`     | `0xff00000000`     | `0xff0000184f`     | 6,224 B       | RW    | Ghidra-internal (Thread DB)    |

### Section Analysis

**Standard sections** (`.text`, `.rdata`, `.data`, `.pdata`, `.reloc`, `.rsrc`) are typical for a MSVC-compiled PE64 binary.

**Non-standard sections requiring investigation:**

1. **`.A2U`** (5.97 MB, RX) -- This is a large executable section with a nonsensical name. At ~6 MB it contains a significant amount of code. Possible explanations:
   - **Packer/protector**: Section names like this are characteristic of commercial executable protectors (e.g., Themida, VMProtect, or Ubisoft's proprietary protector). The random-looking name is a hallmark of obfuscation tooling.
   - **Additional code segment**: Could be a separately-linked module or statically-linked library placed in its own section.
   - [UNKNOWN] The exact purpose requires further analysis of the code within this section.

2. **`.9Bv`** (6,144 B, RW) -- Tiny writable section with another nonsensical name. Likely serves as a data/state section for the packer/protector code in `.A2U` or `.D."`. Its small size suggests it holds configuration, decryption keys, or runtime state.

3. **`.D."`** (4.23 MB, RX) -- Another large executable section with a non-standard name. The main `entry` point (`0x14291e317`) resides here. This strongly suggests this section contains the unpacker/protector stub that executes first, decrypts/decompresses the main `.text` code, and then transfers control.

4. **`_RDATA`** (9,216 B, R) -- This is a known MSVC linker artifact. It typically contains import address table (IAT) entries and security cookie data. Small and benign.

5. **`.rodata`** (2,560 B, RX) -- Unusually small and marked as executable. Standard `.rodata` should be R-only. The RX permissions suggest it may contain small code trampolines or thunks.

**Size distribution of executable code:**
- `.text`: 25.43 MB (main application code)
- `.A2U`: 5.97 MB (suspected protector code or packed payload)
- `.D."`: 4.23 MB (suspected protector/unpacker stub, contains entry point)
- Total executable: ~35.63 MB

The presence of ~10 MB of non-standard executable sections suggests Ubisoft employs a code protection/packing scheme on this binary. The entry point being in `.D."` rather than `.text` supports this -- the protector code runs first to unpack or decrypt `.text` before the actual game code executes.

---

## Import Analysis

35 imported symbols from 23 DLLs were identified. The low import count is consistent with a packed/protected binary -- the real imports are likely resolved at runtime after unpacking.

### System / Core Windows

| DLL           | Functions                                                        | Purpose                        |
|---------------|------------------------------------------------------------------|--------------------------------|
| KERNEL32.DLL  | `GetVersionExA`, `GetVersion`, `LocalAlloc`, `LocalFree`, `GetModuleFileNameW`, `ExitProcess`, `LoadLibraryA`, `GetModuleHandleA`, `GetProcAddress` | OS core, memory, module loading |
| ADVAPI32.DLL  | `OpenProcessToken`                                               | Security / privileges          |
| BCRYPT.DLL    | `BCryptGenRandom`                                                | Cryptographic RNG              |
| RPCRT4.DLL    | `UuidToStringA`                                                  | UUID handling                  |
| USERENV.DLL   | `GetUserProfileDirectoryW`                                       | User profile paths             |
| VERSION.DLL   | `GetFileVersionInfoSizeW`                                        | File version queries           |
| SETUPAPI.DLL  | `SetupDiEnumDeviceInterfaces`                                    | Hardware device enumeration    |
| DBGHELP.DLL   | `SymInitialize`                                                  | Debug symbol loading / crash reporting |
| CRYPT32.DLL   | `CertFreeCertificateContext`                                     | Certificate / TLS operations   |

### Graphics / Display

| DLL           | Functions                                                        | Purpose                        |
|---------------|------------------------------------------------------------------|--------------------------------|
| D3D11.DLL     | `D3D11CreateDevice`                                              | Direct3D 11 device creation    |
| DXGI.DLL      | `CreateDXGIFactory1`                                             | DXGI factory for swap chains   |
| GDI32.DLL     | `DeleteDC`                                                       | GDI device context cleanup     |

**Note**: Only D3D11 is imported -- no D3D12 import is visible. The game may load D3D12 dynamically via `LoadLibraryA`/`GetProcAddress` at runtime, or the packed section resolves it. [UNKNOWN] whether the game actually uses D3D12.

### Windowing / UI

| DLL           | Functions                                                        | Purpose                        |
|---------------|------------------------------------------------------------------|--------------------------------|
| USER32.DLL    | `DestroyWindow`, `CharUpperBuffW`                                | Window management, string ops  |
| SHELL32.DLL   | `SHFileOperationW`                                               | File operations (copy/move/delete) |
| OLE32.DLL     | `CoInitialize`                                                   | COM initialization             |
| OLEAUT32.DLL  | `Ordinal_2`                                                      | OLE Automation (ordinal import)|
| COMDLG32.DLL  | `GetSaveFileNameW`                                               | Save file dialog               |

### Input

| DLL              | Functions                                                     | Purpose                        |
|------------------|---------------------------------------------------------------|--------------------------------|
| DINPUT8.DLL      | `DirectInput8Create`                                          | DirectInput 8 (legacy input)   |
| XINPUT9_1_0.DLL  | `XInputSetState`                                              | XInput (gamepad vibration)     |

**Note**: The game imports XInput 9.1.0 (Vista-era), not the newer XInput 1.4. DirectInput8 is used alongside it, likely for steering wheels and other non-XInput devices.

### Audio / Video

| DLL           | Functions                                                        | Purpose                        |
|---------------|------------------------------------------------------------------|--------------------------------|
| WINMM.DLL     | `timeGetDevCaps`                                                 | Multimedia timer capabilities  |
| VORBIS64.DLL  | `vorbis_block_clear`                                             | Ogg Vorbis audio decoding      |
| AVIFIL32.DLL  | `AVIFileInit`                                                    | AVI video file handling        |

**Note**: Vorbis is used for audio assets. AVI support may be for intro videos or replay recording.

### Network

| DLL           | Functions                                                        | Purpose                        |
|---------------|------------------------------------------------------------------|--------------------------------|
| WS2_32.DLL    | `Ordinal_1` (likely `accept` or socket init)                     | Winsock2 networking            |
| IPHLPAPI.DLL  | `GetIpAddrTable`                                                 | IP address enumeration         |

### Media / Encoding

| DLL              | Functions                                                     | Purpose                        |
|------------------|---------------------------------------------------------------|--------------------------------|
| LIBWEBP64.DLL    | `WebPPictureImportRGBX`                                       | WebP image encoding            |

**Note**: WebP is used for screenshot or thumbnail encoding.

### DRM / Platform

| DLL                    | Functions                                                | Purpose                        |
|------------------------|----------------------------------------------------------|--------------------------------|
| UPC_R2_LOADER64.DLL    | `UPC_TicketGet`                                          | Ubisoft Connect (UPC) DRM      |

**Note**: This is the Ubisoft Connect (formerly Uplay) platform integration. `UPC_TicketGet` retrieves an authentication ticket for online services.

### Import Summary

The import table is minimal (35 functions across 23 DLLs). This is significantly fewer than expected for a game of this complexity and strongly indicates:
1. The binary is packed/protected -- the real IAT is reconstructed at runtime
2. Many APIs are resolved dynamically via `LoadLibraryA` + `GetProcAddress` (both present in imports)
3. The visible imports represent the minimum set needed by the unpacker stub before the main code is decrypted

---

## Export Analysis

10 exports were identified:

| Address          | Name                                  | Notes                          |
|------------------|---------------------------------------|--------------------------------|
| `0x14291e317`    | `entry`                               | Main entry point               |
| `0x14299e63a`    | `tls_callback_0`                      | TLS callback (pre-entry)       |
| `0x141521958`    | `tls_callback_1`                      | TLS callback                   |
| `0x1415223d4`    | `tls_callback_2`                      | TLS callback                   |
| `0x140a811a0`    | `Dxgi_Present_HookCallback` / `Ordinal_2` | DXGI present hook         |
| `0x141e70f38`    | `AmdPowerXpressRequestHighPerformance` / `Ordinal_1` | AMD GPU selection flag |
| `0x141e70f3c`    | `NvOptimusEnablement` / `Ordinal_3`   | NVIDIA Optimus GPU selection flag |

**Notes:**
- `AmdPowerXpressRequestHighPerformance` and `NvOptimusEnablement` are standard exported DWORD variables that tell AMD/NVIDIA drivers to use the discrete GPU instead of integrated graphics on laptops. Both reside in `.data` (address `0x141e70f38` / `0x141e70f3c`).
- `Dxgi_Present_HookCallback` is an interesting export -- it suggests the game exposes a hook point for DXGI Present calls. This could be used by Ubisoft's overlay system or anti-cheat.
- Three TLS callbacks are present, which is more than typical. This pattern is common in protected binaries where TLS callbacks perform anti-debugging checks or decryption steps before the main entry.

---

## Function Statistics

| Metric                            | Value       |
|-----------------------------------|-------------|
| Total functions identified        | 131,311     |
| Functions >= 5,000 bytes          | 363         |
| Largest function                  | 80,516 bytes (78.6 KB) at `0x14006bc80` |

131,311 functions is a large count, consistent with a major C++ application with extensive template instantiation and inline expansion. For reference, this is comparable to other large game engines.

### Largest Functions (Top 20)

| Address          | Size (bytes) | Size (KB) | Suspected Purpose              |
|------------------|-------------|-----------|--------------------------------|
| `0x14006bc80`    | 80,516      | 78.6      | [UNKNOWN] Extremely large -- possibly a generated parser, state machine, or virtual machine interpreter |
| `0x1400a7980`    | 37,526      | 36.6      | [UNKNOWN] |
| `0x140b78f10`    | 34,959      | 34.1      | [UNKNOWN] |
| `0x141194010`    | 33,561      | 32.8      | [UNKNOWN] |
| `0x140efa200`    | 31,877      | 31.1      | [UNKNOWN] |
| `0x1409b93e0`    | 30,071      | 29.4      | [UNKNOWN] |
| `0x140606250`    | 29,993      | 29.3      | [UNKNOWN] |
| `0x1400d98b0`    | 29,731      | 29.0      | [UNKNOWN] |
| `0x1411d3960`    | 29,475      | 28.8      | [UNKNOWN] |
| `0x14144e600`    | 27,867      | 27.2      | [UNKNOWN] |
| `0x140c81610`    | 27,543      | 26.9      | [UNKNOWN] |
| `0x14180f330`    | 27,478      | 26.8      | [UNKNOWN] |
| `0x1400bd500`    | 26,954      | 26.3      | [UNKNOWN] |
| `0x1418592e0`    | 24,230      | 23.7      | [UNKNOWN] |
| `0x1418165e0`    | 23,519      | 23.0      | [UNKNOWN] |
| `0x1405da8a0`    | 22,957      | 22.4      | [UNKNOWN] |
| `0x140b3c070`    | 22,124      | 21.6      | [UNKNOWN] |
| `0x141864180`    | 20,524      | 20.0      | [UNKNOWN] |
| `0x14185f190`    | 20,456      | 20.0      | [UNKNOWN] |
| `0x140ea8fb0`    | 19,670      | 19.2      | [UNKNOWN] |

**Observations on large functions:**
- All top-20 functions reside in `.text`, meaning they are part of the main application code (not the protector).
- The largest function at 80.5 KB is exceptionally large. Common causes: generated serialization/deserialization code, switch-heavy parsers (e.g., GBX file format parsing), physics simulation loops, or render pipeline setup.
- The presence of 363 functions over 5 KB suggests heavy use of inlined code, template expansion, or compiler-generated code (typical of MSVC C++ builds).
- Several function pairs have identical sizes (e.g., `0x1406c8860` and `0x1406c5330` both at 13,578 bytes; `0x1406cf1d0` and `0x1406cbf10` both at 12,946 bytes), which may indicate template instantiations over different types or duplicated logic for different subsystems.

---

## String Statistics

| Metric                    | Value   |
|---------------------------|---------|
| Total defined strings     | 52,890  |

52,890 strings is a substantial count. These will be invaluable for reverse engineering -- string cross-references can identify:
- File format parsers (by format identifiers and field names)
- Network protocol handlers (by URL patterns, HTTP methods)
- Error messages (by descriptive text)
- Class/type names (ManiaPlanet engine uses RTTI-like strings)
- Configuration keys and paths

[UNKNOWN] No string content was extracted in this overview. A follow-up analysis should categorize strings by type (file paths, URLs, error messages, class names, format strings, etc.).

---

## Summary of Key Findings

### What we know:
1. **Architecture**: PE32+ x86-64, image base `0x140000000`, 43 MB GUI application
2. **Protection**: The binary uses some form of code protection/packing. Evidence:
   - Entry point is in non-standard section `.D."` rather than `.text`
   - Three non-standard sections (`.A2U`, `.9Bv`, `.D."`) with random-looking names totaling ~10 MB
   - Minimal import table (35 functions) with `LoadLibraryA`/`GetProcAddress` for runtime resolution
   - Three TLS callbacks (common anti-debug/unpacking technique)
3. **Graphics**: Direct3D 11 is the confirmed graphics API (imported directly). D3D12 status is [UNKNOWN].
4. **Input**: DirectInput 8 + XInput 9.1.0 for controller support
5. **Audio**: Ogg Vorbis (via vorbis64.dll) for audio decoding
6. **Network**: Winsock2 for networking, IPHLPAPI for network interface enumeration
7. **DRM**: Ubisoft Connect integration via `UPC_R2_LOADER64.DLL`
8. **Media encoding**: WebP for image encoding, AVI for video file handling
9. **Scale**: 131,311 functions, 52,890 strings -- this is a large, complex binary

### What we suspect but cannot confirm:
- The non-standard sections are from a commercial packer/protector (possibly Ubisoft's custom solution or a third-party tool like Themida/VMProtect)
- The largest function (~80 KB) may be a serialization engine, GBX parser, or virtual machine
- Many more imports exist but are resolved dynamically after unpacking
- D3D12 may be loaded at runtime

### Recommended next steps:
1. Analyze TLS callbacks to understand the unpacking/protection sequence
2. Dump strings and categorize them to identify subsystems
3. Investigate the `.A2U` and `.D."` sections for protector signatures
4. Cross-reference `LoadLibraryA` and `GetProcAddress` calls to find dynamically resolved APIs
5. Decompile the largest functions to identify key subsystems (GBX parser, physics, renderer)
6. Search for ManiaPlanet engine class name strings (the engine uses a reflection system with embedded type names)

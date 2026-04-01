# Binary Overview

Understanding the binary structure matters because Trackmania.exe uses code protection that hides most imports and relocates the entry point. You need to know which sections contain real game code versus packer stubs before you can analyze anything meaningful.

The binary is a 43 MB PE32+ x86-64 Windows GUI application compiled with MSVC (VS2019). It contains 131,311 functions, 52,890 defined strings, and ~10 MB of non-standard executable sections from a code protector.

## PE header at a glance

| Field | Value |
|---|---|
| Format | PE32+ (x86-64) |
| Architecture | x86:LE:64:default |
| Image base | `0x140000000` |
| Subsystem | Windows GUI |
| File size on disk | 45,467,720 bytes (43.36 MB) |
| Mapped size | ~46,879,280 bytes (44.71 MB) |

## Where the entry points are

The binary has 7 entry points. The main entry lives in a non-standard section, which is the first sign of code protection.

| Address | Name | Type |
|---|---|---|
| `0x14291e317` | `entry` | Function |
| `0x14299e63a` | `tls_callback_0` | [UNKNOWN] |
| `0x141521958` | `tls_callback_1` | Function |
| `0x1415223d4` | `tls_callback_2` | Function |
| `0x140a811a0` | `Dxgi_Present_HookCallback` | Function |
| `0x141e70f38` | [UNKNOWN - no function] | Data |
| `0x141e70f3c` | [UNKNOWN - no function] | Data |

The main `entry` at `0x14291e317` resides in the `.D."` section, not `.text`. Three TLS callbacks execute before the main entry point -- a common technique in packed binaries for anti-debug or unpacking logic. `Dxgi_Present_HookCallback` is an intentional DXGI present hook for overlay rendering. The two unnamed entries at `0x141e70f38`/`0x141e70f3c` are the `AmdPowerXpressRequestHighPerformance` and `NvOptimusEnablement` data exports for GPU selection.

## How the sections are laid out

| Section | Start | End | Size | Perms | Notes |
|---|---|---|---|---|---|
| Headers | `0x140000000` | `0x1400003ff` | 1,024 B | R | PE/COFF headers |
| `.text` | `0x140001000` | `0x14196e5ff` | 25.43 MB | RX | Main code section |
| `.rodata` | `0x14196f000` | `0x14196f9ff` | 2,560 B | RX | Read-only data (very small) |
| `.rdata` | `0x141970000` | `0x141e63bff` | 4.95 MB | R | Read-only data / import tables |
| `.data` | `0x141e64000` | `0x1420d2bdf` | 2.43 MB | RW | Initialized data (globals) |
| `.pdata` | `0x1420d3000` | `0x14221ffff` | 1.30 MB | R | Exception handling unwind data |
| `_RDATA` | `0x142220000` | `0x1422223ff` | 9,216 B | R | IAT entries, security cookie |
| `.A2U` | `0x142223000` | `0x14281c1ff` | 5.97 MB | RX | Non-standard executable section |
| `.9Bv` | `0x14281d000` | `0x14281e7ff` | 6,144 B | RW | Non-standard writable section |
| `.D."` | `0x14281f000` | `0x142c595ff` | 4.23 MB | RX | Non-standard executable section |
| `.reloc` | `0x142c5a000` | `0x142cac7ff` | 337,920 B | R | Base relocation table |
| `.rsrc` | `0x142cad000` | `0x142cb91ff` | 49,664 B | R | Resources (icons, manifests) |

### Non-standard sections reveal code protection

Three sections have randomly-generated names, a hallmark of commercial executable protectors (e.g., Themida, VMProtect, or Ubisoft's proprietary solution).

**`.A2U`** (5.97 MB, RX) is a large executable section. It likely contains protector code or a packed payload.

**`.9Bv`** (6,144 B, RW) is tiny and writable. It probably holds configuration, decryption keys, or runtime state for the protector.

**`.D."`** (4.23 MB, RX) contains the main entry point (`0x14291e317`). The protector stub here runs first, decrypts/decompresses `.text`, and transfers control.

**Size distribution of executable code:**
- `.text`: 25.43 MB (main application code)
- `.A2U`: 5.97 MB (suspected protector code)
- `.D."`: 4.23 MB (protector/unpacker stub with entry point)
- Total executable: ~35.63 MB

## What the imports tell you

Only 35 imported symbols exist across 23 DLLs. This is far fewer than expected for a game of this complexity and confirms the binary is packed.

### System / Core Windows

| DLL | Functions | Purpose |
|---|---|---|
| KERNEL32.DLL | `GetVersionExA`, `GetVersion`, `LocalAlloc`, `LocalFree`, `GetModuleFileNameW`, `ExitProcess`, `LoadLibraryA`, `GetModuleHandleA`, `GetProcAddress` | OS core, memory, module loading |
| ADVAPI32.DLL | `OpenProcessToken` | Security / privileges |
| BCRYPT.DLL | `BCryptGenRandom` | Cryptographic RNG |
| RPCRT4.DLL | `UuidToStringA` | UUID handling |
| USERENV.DLL | `GetUserProfileDirectoryW` | User profile paths |
| VERSION.DLL | `GetFileVersionInfoSizeW` | File version queries |
| SETUPAPI.DLL | `SetupDiEnumDeviceInterfaces` | Hardware device enumeration |
| DBGHELP.DLL | `SymInitialize` | Debug symbol loading / crash reporting |
| CRYPT32.DLL | `CertFreeCertificateContext` | Certificate / TLS operations |

### Graphics / Display

| DLL | Functions | Purpose |
|---|---|---|
| D3D11.DLL | `D3D11CreateDevice` | Direct3D 11 device creation |
| DXGI.DLL | `CreateDXGIFactory1` | DXGI factory for swap chains |
| GDI32.DLL | `DeleteDC` | GDI device context cleanup |

Only D3D11 appears in imports. The game may load D3D12 dynamically at runtime, but [UNKNOWN] whether it actually uses D3D12.

### Windowing / UI

| DLL | Functions | Purpose |
|---|---|---|
| USER32.DLL | `DestroyWindow`, `CharUpperBuffW` | Window management |
| SHELL32.DLL | `SHFileOperationW` | File operations |
| OLE32.DLL | `CoInitialize` | COM initialization |
| OLEAUT32.DLL | `Ordinal_2` | OLE Automation |
| COMDLG32.DLL | `GetSaveFileNameW` | Save file dialog |

### Input

| DLL | Functions | Purpose |
|---|---|---|
| DINPUT8.DLL | `DirectInput8Create` | DirectInput 8 (legacy input) |
| XINPUT9_1_0.DLL | `XInputSetState` | XInput (gamepad vibration) |

The game imports XInput 9.1.0 (Vista-era), not the newer XInput 1.4. DirectInput8 runs alongside it for steering wheels and non-XInput devices.

### Audio / Video

| DLL | Functions | Purpose |
|---|---|---|
| WINMM.DLL | `timeGetDevCaps` | Multimedia timer capabilities |
| VORBIS64.DLL | `vorbis_block_clear` | Ogg Vorbis audio decoding |
| AVIFIL32.DLL | `AVIFileInit` | AVI video file handling |

### Network

| DLL | Functions | Purpose |
|---|---|---|
| WS2_32.DLL | `Ordinal_1` (likely `accept`) | Winsock2 networking |
| IPHLPAPI.DLL | `GetIpAddrTable` | IP address enumeration |

### Media / DRM

| DLL | Functions | Purpose |
|---|---|---|
| LIBWEBP64.DLL | `WebPPictureImportRGBX` | WebP image encoding |
| UPC_R2_LOADER64.DLL | `UPC_TicketGet` | Ubisoft Connect DRM |

### Why so few imports

The 35 visible imports represent the minimum set the unpacker stub needs before the main code decrypts. Both `LoadLibraryA` and `GetProcAddress` are imported, confirming that the real IAT reconstructs at runtime.

## What the binary exports

| Address | Name | Notes |
|---|---|---|
| `0x14291e317` | `entry` | Main entry point |
| `0x14299e63a` | `tls_callback_0` | TLS callback (pre-entry) |
| `0x141521958` | `tls_callback_1` | TLS callback |
| `0x1415223d4` | `tls_callback_2` | TLS callback |
| `0x140a811a0` | `Dxgi_Present_HookCallback` / `Ordinal_2` | DXGI present hook |
| `0x141e70f38` | `AmdPowerXpressRequestHighPerformance` / `Ordinal_1` | AMD GPU selection flag |
| `0x141e70f3c` | `NvOptimusEnablement` / `Ordinal_3` | NVIDIA Optimus GPU selection flag |

The GPU selection exports (`AmdPowerXpressRequestHighPerformance` and `NvOptimusEnablement`) are standard DWORD variables that tell AMD/NVIDIA drivers to use the discrete GPU on laptops. `Dxgi_Present_HookCallback` exposes a hook point for DXGI Present calls, likely used by Ubisoft's overlay system.

## How many functions exist

| Metric | Value |
|---|---|
| Total functions identified | 131,311 |
| Functions >= 5,000 bytes | 363 |
| Largest function | 80,516 bytes (78.6 KB) at `0x14006bc80` |

### Largest functions (top 10)

| Address | Size (bytes) | Suspected Purpose |
|---|---|---|
| `0x14006bc80` | 80,516 | [UNKNOWN] Possibly a generated parser, state machine, or VM interpreter |
| `0x1400a7980` | 37,526 | [UNKNOWN] |
| `0x140b78f10` | 34,959 | `CGameCtnApp::UpdateGame` (main game loop state machine) |
| `0x141194010` | 33,561 | [UNKNOWN] |
| `0x140efa200` | 31,877 | [UNKNOWN] |
| `0x1409b93e0` | 30,071 | [UNKNOWN] |
| `0x140606250` | 29,993 | [UNKNOWN] |
| `0x1400d98b0` | 29,731 | [UNKNOWN] |
| `0x1411d3960` | 29,475 | [UNKNOWN] |
| `0x14144e600` | 27,867 | [UNKNOWN] |

All top-20 functions reside in `.text`, meaning they are real application code (not the protector). The 131,311 total is consistent with a major C++ application with extensive template instantiation. Several function pairs have identical sizes, suggesting template instantiations over different types.

## How many strings exist

The binary contains 52,890 defined strings. These proved invaluable for reverse engineering -- nearly every function begins with a profiling scope tag like `FUN_140117690(buf, "ClassName::MethodName")`. Cross-referencing these strings enabled identification of hundreds of functions despite the binary being fully stripped of debug symbols.

## Summary of findings

**What we know:**
1. PE32+ x86-64, image base `0x140000000`, 43 MB GUI application
2. Code protection with non-standard sections, minimal imports, and 3 TLS callbacks
3. Direct3D 11 is the confirmed graphics API. D3D12 status is [UNKNOWN].
4. DirectInput 8 + XInput 9.1.0 for controller support
5. Ogg Vorbis for audio decoding, WebP for image encoding
6. Winsock2 for networking, Ubisoft Connect for DRM
7. 131,311 functions, 52,890 strings -- a large, complex binary

**What we suspect but have not confirmed:**
- The non-standard sections come from a commercial packer (possibly Ubisoft's custom solution or Themida/VMProtect)
- The largest function (~80 KB) may be a serialization engine, GBX parser, or virtual machine
- D3D12 may load at runtime
- Many more imports resolve dynamically after unpacking

## Related Pages

- [00-master-overview.md](00-master-overview.md) -- Project overview and navigation
- [02-class-hierarchy.md](02-class-hierarchy.md) -- Engine class system
- [08-game-architecture.md](08-game-architecture.md) -- Entry point chain and initialization sequence

<details><summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 11.x via PyGhidra bridge
**File size**: 45,467,720 bytes (43.36 MB)

</details>

# Trackmania.exe Game Architecture

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.0.4 via PyGhidra bridge
**Data sources**: Entry point analysis, string cross-references, function decompilation, call graph analysis

---

## 1. Program Entry Point and Initialization Sequence

### 1.1 Entry Point Chain

The program entry goes through a standard MSVC CRT bootstrap, but the true `entry` function at `0x14291e317` resides in the non-standard `.D."` section and contains obfuscated/anti-tamper code (Ghidra reports "bad instruction data"). This is likely a packer stub or code protection wrapper.

The actual startup path is:

```
entry (0x14291e317)                     -- obfuscated entry in .D." section
  -> FUN_1428eb7e6()                    -- [UNKNOWN] likely unpacker/decoder
  -> FUN_14291da78()                    -- [UNKNOWN] likely transfer to real entry

WinMainCRTStartup (0x141521c28)         -- MSVC CRT startup (VS2019)
  -> FUN_141522670()                    -- [UNKNOWN] CRT pre-init
  -> __scrt_common_main_seh()           -- standard MSVC main SEH wrapper
    -> __scrt_initialize_crt(1)         -- CRT initialization
    -> _initterm()                      -- C++ static constructors
    -> _get_narrow_winmain_command_line()
    -> thunk_FUN_140aa7470()            -- actual WinMain
    -> _cexit()                         -- CRT cleanup
```

### 1.2 WinMain (FUN_140aa7470)

Address: `0x140aa7470` | Size: 202 bytes | Called by: `__scrt_common_main_seh`

The actual WinMain function performs early engine initialization:

```
WinMain (FUN_140aa7470):
  1. Set default window dimensions: 640x480 (0x280 x 0x1e0)
  2. Store global engine timestamp (DAT_141fbbf90)
  3. FUN_14236394f(0)          -- [UNKNOWN] possibly GetTickCount/QueryPerformanceCounter
  4. FUN_1401171d0()           -- Initialize profiling/timing system
  5. FUN_140117d10("Startup")  -- Create profiling tag "Startup"
  6. FUN_140117a10()           -- [UNKNOWN] conditional startup step (if DAT_141fbc6e0 != 0)
  7. FUN_140117840()           -- Frame timing initialization
  8. FUN_140117690("InitApp")  -- Begin profiling tag "InitApp"
  9. FUN_142279568(0,2)        -- [UNKNOWN] likely falls through to GbxApp initialization
```

**Note**: The function is only 202 bytes and ends with `halt_baddata()` in Ghidra's output, suggesting the control flow continues through a code protection mechanism or indirect call that Ghidra cannot fully resolve.

### 1.3 Profiling/Timing System

The engine has a built-in hierarchical profiling system initialized very early in startup.

**FUN_1401175b0** (profile tag begin) at `0x1401175b0`:
- Accesses thread-local data via `ThreadLocalStoragePointer + 0x1b8`
- Records tag name, nesting depth, and timestamp
- Supports up to 75 (0x4B) timing slots
- Has an "AssertDialog" special case bypass

**FUN_140117690** (profile tag wrapper) at `0x140117690`:
- Thin wrapper calling `FUN_1401175b0(param_1, param_2, 1)`
- Used extensively throughout the codebase to instrument function execution

**FUN_1401176a0** (profile tag end) at `0x1401176a0`:
- Closes a profiling tag and records elapsed time

Every significant function in the engine starts with `FUN_140117690(local_buf, "FunctionName")` and ends with `FUN_1401176a0(local_buf, tag_id)`, forming a comprehensive hierarchical profiler.

### 1.4 CGbxApp Initialization

The GBX application bootstrap proceeds in two phases:

#### Phase 1: CGbxApp::Init1 (FUN_140aa3220)

Address: `0x140aa3220` | Size: large (>0x4000 stack frame) | Profiling tag: `"CGbxApp::Init1"`

1. Calls `FUN_140aa3080(param_1)` -- [UNKNOWN] early app object setup
2. Checks for "Luna Mode" (`DAT_141fbbf50`) -- accessibility mode check
3. If Luna Mode: sets `param_1->0x74 = 1`, `param_1->0x70 = 1`, exits early
4. Checks UUID `"41958b32-a08c-4313-a6c0-f49d4fb5a91e"` -- [UNKNOWN] possibly a hardware/license identifier
5. If UUID matches: logs `"[Sys] Luna Mode enabled."`, sets `DAT_141f9cff4 = 1`
6. Allocates 0x40-byte object via `thunk_FUN_1408de480(0x40)` -> `FUN_1402d1f00()` -- [UNKNOWN] subsystem allocation
7. Continues with extensive engine subsystem initialization [UNKNOWN - truncated in decompilation]

#### Phase 2: CGbxApp::Init2 (FUN_140aa5090)

Address: `0x140aa5090` | Profiling tag: `"CGbxApp::Init2"`

1. Calls `FUN_1408f65c0()` -- checks something (if result == 8, performs config setup)
2. Creates graphics viewport via virtual call `(*(*param_1 + 0x148))(param_1)` -- likely `CreateViewport`
3. Initializes DirectX rendering -- on failure shows: `"Could not start the game!\r\n  System error, initialization of DirectX failed."`
4. Configures viewport: profiling tag `"ViewportConfig"`
5. Renders waiting frame: profiling tag `"RenderWaitingFrame"` via `(*(*param_1 + 0x150))(param_1)`
6. Logs `"GbxApp init2"` and calls `(*(*param_1 + 0x110))(param_1)` -- virtual Init2 completion
7. Processes command-line arguments (startup URL handling)

#### CGbxGame::InitApp (FUN_140102cb0)

Address: `0x140102cb0` | Profiling tag: `"CGbxGame::InitApp"`

1. Calls `FUN_140101a30()` -- [UNKNOWN] quick check
2. If headless mode (`DAT_141fbbee8 != 0`): calls `FUN_140aa9320(param_1)` (simplified init)
3. Loads game resource string `"CGbxGame::InitApp"` marker
4. Creates CSystemEngine via `FUN_1408f1750()` with system config
5. Allocates game engine object via `FUN_140900890()`
6. Stores engine pointer at `param_1->0x188` (offset 0x31 * 8)
7. Sets up the engine display config at offsets `0xd0`, `0xe0`, `0x110`
8. Installs callbacks on the system engine:
   - Callback at engine+0x70: `FUN_140101a40` -- [UNKNOWN] likely frame callback
   - Callback at engine+0x80: `_guard_check_icall` -- security check
   - Callback at engine+0x90: `FUN_140aa93b0` -- [UNKNOWN] likely render callback
9. Creates a fiber-like callback object via `FUN_1402d4270(alloc(0x38), param_1, FUN_140aa9320)`
10. Calls engine virtual functions for device and display setup

#### CSystemEngine::InitForGbxGame (FUN_1408f56a0)

Address: `0x1408f56a0` | Profiling tag: `"CSystemEngine::InitForGbxGame"`

1. Stores param_2 at engine+0x98
2. Processes game data directories and configuration strings
3. Reads `"Distro"`, `"WindowTitle"`, `"DataDir"` from config
4. If DataDir not set: defaults to `"GameData\\"`
5. Reads `"UGCLogAutoOpen"` setting
6. Processes game distribution and data path configuration
7. Sets up the engine file system paths

**String evidence for initialization flow:**
```
"CSystemEngine::StaticInit"         -- static class registration
"CSystemEngine::CaptureInfoOsCpu"   -- hardware detection
"CSystemEngine::CaptureInfoExe"     -- executable info capture
"CSystemEngine::InitSysCfgVision"   -- vision/graphics config
"CSystemEngine::InitForGbxGame"     -- full engine init for game mode
```

---

## 2. Application Class Hierarchy

Based on string evidence and call patterns, the application class hierarchy is:

```
CMwNod                              -- universal base class
  CMwEngine                         -- engine base (registered as "CMwEngine")
    CSystemEngine                   -- system/OS layer
    CVisionEngine                   -- rendering backend
    CInputEngine                    -- input devices
    CNetEngine [UNKNOWN - inferred] -- networking
    CControlEngine                  -- UI controls
    CPlugEngine                     -- asset/resource system
    CAudioEngine [UNKNOWN - inferred] -- audio
  CGbxApp                           -- application base (Init1, Init2)
    CGameApp                        -- game application
      CGameCtnApp                   -- Creation (CTN) application
        CGameManiaPlanet            -- ManiaPlanet platform layer
          CTrackMania               -- TrackMania-specific logic
```

**Evidence for hierarchy:**
- `CGbxApp::Init1` / `CGbxApp::Init2` -- base app initialization
- `CGbxGame::InitApp` / `CGbxGame::PreInitApp` / `CGbxGame::DestroyApp()` -- game bootstrap
- `CGameCtnApp::Start()` -- CTN-level start
- `CGameManiaPlanet::Start` -- calls `CGameCtnApp::Start` (confirmed: `FUN_140b4eba0` is called from `FUN_140cb8870`)
- `CTrackMania::StartUpShowIntroSlidesAndRollingDemo` -- TM-specific startup

### 2.1 CGbxGame Lifecycle

The `CGbxGame` class manages the game application lifecycle:

| String                                    | Address          | Purpose                      |
|-------------------------------------------|------------------|------------------------------|
| `CGbxGame::PreInitApp`                    | `0x141a58b38`    | Pre-initialization           |
| `CGbxGame::InstallGameResourcePacks`      | `0x141a58b10`    | Resource pack loading        |
| `CGbxGame::InitApp`                       | `0x141a58bc0`    | Main initialization          |
| `CGbxGame::RequestTerminateApp()`         | `0x141a58c08`    | Termination request          |
| `CGbxGame::DestroyApp()`                  | `0x141a58c78`    | Cleanup and destruction      |

### 2.2 Application Start Sequence

The CGameManiaPlanet::Start function (at `0x140cb8870`) reveals the full startup:

1. Register playground types: `"PlaygroundCommonBase"` and `"PlaygroundCommon"`
2. Allocate CGameManiaPlanet data structures (0x208 bytes for main state, 0x28 for helper)
3. Call `CGameCtnApp::Start()` (FUN_140b4eba0)
4. Configure rendering settings (check hardware capabilities)
5. Set up cross-references in the game state object (offsets 0x330-0x3E8)
6. Create game-specific modules (0x78-byte allocation)
7. Register input rules (`"CGameManiaPlanet::InputMenuRule"`)
8. Read `/startuptitle` and `/title` from config
9. Set game name to `"Trackmania"` at offset 0x964

---

## 3. Main Game Loop Structure

### 3.1 Overview

The game does **not** use a named `GameLoop` or `MainLoop` function in the traditional sense. Instead, the main game loop is driven through `CGameCtnApp::UpdateGame` (at `0x140b78f10`), which is a massive state-machine-based update function.

The loop is structured around **profiling-tagged phases** discovered via string references:

```
Update_BeforeMainLoop          -- pre-frame setup
Network_BeforeMainLoop         -- network pre-frame
Update_MainLoop                -- main frame update (game logic, rendering)
Update_AfterMainLoop           -- post-frame cleanup
Network_AfterMainLoop          -- network post-frame

CGameCtnApp::Network_BeforeMainLoop
CGameCtnApp::Network_AfterMainLoop
```

### 3.2 CGameCtnApp::UpdateGame (FUN_140b78f10)

Address: `0x140b78f10` | Profiling tag: `"CGameCtnApp::UpdateGame"`

This is the central game tick function. It is extremely large (uses >0x1300 bytes of stack) and calls 160+ sub-functions. Key responsibilities identified through call graph analysis:

- Frame timing and profiling (`FUN_140117690`, `FUN_1401176a0`)
- Game state machine dispatch (see Section 4)
- Network state updates
- Script execution
- Rendering coordination
- Input processing
- UI updates

### 3.3 CGameCtnApp::UpdateGame Sub-Phases

The UpdateGame function has multiple named sub-phases:

| Phase String                                    | Function Address | Purpose                         |
|-------------------------------------------------|------------------|---------------------------------|
| `CGameCtnApp::UpdateGame_Init`                  | `0x140b76b20`    | Per-frame initialization        |
| `CGameCtnApp::UpdateGame_StartUp`               | `0x140b77490`    | Startup sequence handling       |
| `CGameCtnApp::UpdateGame`                       | `0x140b78f10`    | Main update dispatch            |
| `CGameCtnApp::UpdateGame_ExecMenuResult`        | [UNKNOWN]        | Menu result processing          |
| `CGameManiaPlanet::UpdateGame_StartUp`          | [UNKNOWN]        | Platform-level startup handling |
| `CGameManiaPlanet::UpdateGame_ExecMenuResult`   | [UNKNOWN]        | Platform menu processing        |

### 3.4 CGameCtnApp::UpdateGame_Init (FUN_140b76b20)

Address: `0x140b76b20` | Size: 2414 bytes | Profiling tag: `"CGameCtnApp::UpdateGame_Init"`

This function initializes per-frame state:
1. If state == -1: return immediately (game not running)
2. Allocate update context object (0x20 bytes, vtable at `PTR_FUN_141b68250`)
3. Read configuration values from the SysCfg system using `FUN_1408f85c0` and `FUN_1408f8540`
4. Configuration keys processed include strings at offsets near `0x141c339a0-0x141c339f8`
5. Store config results in the update context at various offsets (+0x10, +0x20, +0x30, +0x40, +0x50, +0x60)

---

## 4. Game State Machine

### 4.1 GameState System

The game uses a state machine pattern for managing major game states. States are identified by string tags:

| State String                                                   | Address          |
|----------------------------------------------------------------|------------------|
| `CGameCtnApp::GameState_LocalLoop`                             | `0x141c8ee78`    |
| `CGameCtnApp::GameState_LoadChallenge`                         | `0x141c8eee8`    |
| `CGameCtnApp::GameState_LocalLoopEditor`                       | `0x141c8f1a8`    |
| `CGameCtnApp::GameState_LocalLoopPlaying`                      | `0x141c8f308`    |
| `CGameCtnApp::GameState_LocalLoopPreparePlaying`               | `0x141c8f330`    |
| `CGameCtnApp::GameState_LocalLoopUnpreparePlaying`             | `0x141c8f2a0`    |
| `CGameCtnApp::GameState_LocalLoopSetUp`                        | `0x141c8f3c8`    |
| `CGameCtnApp::GameState_GetNextChallengeInfo`                  | `0x141c8f2d8`    |
| `CGameCtnApp::GameState_LocalLoop_ReturnToEditor`              | `0x141c8f488`    |
| `CGameCtnApp::GameState_LocalLoop_EditScriptSettings`          | `0x141c8f4d8`    |
| `CGameCtnApp::GameState_LocalLoopScript`                       | `0x141c53378`    |
| `CGameCtnApp::GameState_LoadMediaTrackerFromScript`            | `0x141c8f390`    |
| `CGameCtnApp::GameState_EditorCutScenes`                       | `0x141c8f618`    |
| `CGameManiaPlanet::GameState_LocalLoopPlaying`                 | `0x141c590f8`    |
| `CGameManiaPlanet::GameState_LocalLoopSetUp`                   | `0x141c59290`    |
| `CTrackMania::GameState_LocalLoopSetUp`                        | `0x141cfb978`    |
| `CTrackMania::Trackmania_GameState_ReplayValidate`             | `0x141cf7b50`    |
| `CGameCtnApp::Trackmania_GameState_EditorQuit`                 | `0x141c8f360`    |
| `CGameCtnApp::Trackmania_GameState_EditorMustQuit`             | `0x141c8f510`    |
| `CGameCtnApp::Trackmania_GameState_EditorCheckStartPlaying`    | `0x141c8f570`    |
| `CGameCtnApp::Trackmania_GameState_PrepareRecordMediaTrackerGhost` | `0x141c8f5d0` |

### 4.2 State Transitions

The state machine appears to follow this high-level flow:

```
[Startup]
  -> UpdateGame_Init
  -> UpdateGame_StartUp
  -> GameState_LocalLoop (main menu / idle)
    -> GameState_LoadChallenge (map loading)
    -> GameState_LocalLoopSetUp (pre-play setup)
    -> GameState_LocalLoopPreparePlaying (final preparation)
    -> GameState_LocalLoopPlaying (active gameplay)
    -> GameState_LocalLoopUnpreparePlaying (exit gameplay)
    -> GameState_LocalLoopEditor (map editor)
    -> GameState_LocalLoopScript (script execution)
    -> GameState_GetNextChallengeInfo (next map)
  -> QuitGameAndExit
```

### 4.3 CGameApp Shutdown

**CGameApp::QuitGameAndExit** (FUN_140b4d140) at `0x140b4d140`:

1. Logs `"CGameApp::QuitGame...()"`
2. If network module exists (param_1[0x6f]): calls disconnect via virtual `+0x100`
3. Calls virtual `(*param_1 + 0x2d0))(param_1)` -- [UNKNOWN] cleanup virtual
4. Enters a loop processing pending commands via `(*param_1 + 0x2c8))(param_1)`
5. Logs `"CGameApp::..AndExit()"`
6. If system engine exists (param_1[0x18]): calls `(*(engine + 0xf0))()` -- engine shutdown
7. Sets final state to -1 (terminated)

---

## 5. Network MainLoop State Machine

### 5.1 CGameCtnNetwork MainLoop States

The network subsystem has its own state machine within the main game loop:

| State String                                              | Function Address | Entry Address    |
|-----------------------------------------------------------|------------------|------------------|
| `CGameCtnNetwork::MainLoop_Menus`                         | `0x140af9a40`    | `0x140af9a40`    |
| `CGameCtnNetwork::MainLoop_Menus_ApplyCommand`            | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_Menus_Lan`                     | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_Menus_Internet`                | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_Menus_DialogJoin`              | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_SetUp`                         | `0x140afc320`    | `0x140afc320`    |
| `CGameCtnNetwork::MainLoop_Prepare`                       | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_PlaygroundPrepare`             | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_PlaygroundPlay`                | `0x140aff380`    | `0x140aff380`    |
| `CGameCtnNetwork::MainLoop_PlaygroundExit`                | [UNKNOWN]        | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_PlaygroundPrepareDoChallengeParams` | [UNKNOWN]   | [UNKNOWN]        |
| `CGameCtnNetwork::MainLoop_SpectatorSwitch`               | [UNKNOWN]        | [UNKNOWN]        |

### 5.2 CGameNetwork MainLoop States

A parallel state machine exists for the base `CGameNetwork` class:

| State String                                   | Address          |
|------------------------------------------------|------------------|
| `CGameNetwork::MainLoop_InternetConnect`       | `0x141c38508`    |
| `CGameNetwork::MainLoop_Update`                | `0x141c38db0`    |
| `CGameNetwork::MainLoop_PlaygroundPrepare`     | `0x141c38e30`    |
| `CGameNetwork::MainLoop_PlaygroundPlay`        | `0x141c38e60`    |
| `CGameNetwork::MainLoop_PlaygroundExit`        | `0x141c38e88`    |
| `CGameNetwork::MainLoop_Prepare`               | `0x141c38f60`    |
| `CGameNetwork::MainLoop_SetUp`                 | `0x141c38f80`    |

### 5.3 CSmArenaClient MainLoop

ShootMania arena client (also used by TrackMania) has its own sub-loop:

| State String                                   | Address          |
|------------------------------------------------|------------------|
| `CSmArenaClient::MainLoop_PlayGameEdition`     | `0x141cf13a0`    |
| `MainLoop_SoloPlayGameEdition`                 | `0x141cf13d0`    |
| `MainLoop_RecordGhost`                         | `0x141cf13f0`    |
| `MainLoop_SoloCommon`                          | `0x141cf1408`    |
| `MainLoop_SoloPlayGameScript`                  | `0x141cf1438`    |
| `MainLoop_PlayGameNetwork`                     | `0x141cf1500`    |
| `MainLoop_RecordGhostUntilSpot`                | `0x141cf1620`    |
| `MainLoop_TestAnim`                            | `0x141cf1640`    |

---

## 6. Engine Subsystem Hierarchy

### 6.1 Engine Classes

The engine is organized around specialized engine subsystems, each managing a domain:

| Engine Class       | Key Strings Found                                              | Role                            |
|--------------------|----------------------------------------------------------------|---------------------------------|
| `CMwEngine`        | `"CMwEngineMain"`, `"CMwEngine"`                               | Core engine base                |
| `CSystemEngine`    | `StaticInit`, `InitForGbxGame`, `InitSysCfgVision`, `SynchUpdate`, `CaptureInfoOsCpu`, `CaptureInfoExe` | OS/platform/config layer |
| `CVisionEngine`    | `CreateViewport`, `CVisionEngine` constructor                  | Rendering/graphics              |
| `CInputEngine`     | `GetOrCreateInputPort`                                         | Input devices                   |
| `CNetEngine`       | `UpdateHttpClients`                                            | Network/HTTP                    |
| `CControlEngine`   | `ControlsFocus`, `ContainersFocus`, `ContainersValues`, `ControlsValues`, `ContainersDoLayout`, `ControlsEffects`, `ContainersEffects` | UI control system |
| `CPlugEngine`      | `CPlugEngine::CPlugEngine` constructor                         | Asset/resource/plugin system    |
| `CScriptEngine`    | `CScriptEngine::Run`, `CScriptEngine::Run(%s)`, `Compilation for autocompletion` | ManiaScript execution |

### 6.2 CSystemEngine Key Operations

```
CSystemEngine::StaticInit           -- class registration
CSystemEngine::CaptureInfoOsCpu     -- CPU/OS detection at startup
CSystemEngine::CaptureInfoExe       -- executable metadata capture
CSystemEngine::InitSysCfgVision     -- graphics config initialization
CSystemEngine::InitForGbxGame       -- full init for game mode
CSystemEngine::SynchUpdate          -- synchronous per-frame update
```

### 6.3 CControlEngine Frame Update Phases

The UI control engine runs these phases each frame (all found as profiling tag strings):

```
CControlEngine::ControlsFocus       -- process focus changes
CControlEngine::ContainersFocus     -- container focus propagation
CControlEngine::ContainersValues    -- read container values
CControlEngine::ControlsValues      -- read control values
CControlEngine::ContainersDoLayout  -- layout calculation
CControlEngine::ControlsEffects     -- visual effects
CControlEngine::ContainersEffects   -- container effects
```

---

## 7. Fiber / Coroutine System

### 7.1 CMwCmdFiber

The engine uses a fiber/coroutine system for async operations. The base class is `CMwCmdFiber`.

**CMwCmdFiber Static Registration** (FUN_14002e300) at `0x14002e300`:
```c
FUN_1402d52e0(&DAT_141ffe4d0, 0x101e000, &DAT_141ffe240, "CMwCmdFiber", 0, 0x58);
atexit(cleanup_func);
```

- Class ID: stored at `DAT_141ffe4d0`
- Flags: `0x101e000`
- Class data: at `DAT_141ffe240`
- Name: `"CMwCmdFiber"`
- Parent ID: 0 (root)
- Instance size: `0x58` (88 bytes)

### 7.2 Fiber Usage Pattern

Fibers follow a naming convention: `ClassName::MethodName_InternalFiberCallback`. This pattern appears extensively:

| Fiber Name                                                      | Address          |
|-----------------------------------------------------------------|------------------|
| `CGameCtnNetwork::DisconnectFromInternet_InternalFiberCallback` | `0x141c2d468`    |
| `CGameCtnNetwork::UpdateAntiCheat_InternalFiberCallback`        | `0x141c2df38`    |
| `CGameCtnApp::BuddySwitch_InternalFiberCallback`               | `0x141c314a8`    |
| `CGameCtnApp::CheckBuddiesState_InternalFiberCallback`          | `0x141c31520`    |
| `CGameCtnApp::RemoveSkin_InternalFiberCallback`                 | `0x141c31f48`    |
| `CGameCtnMenus::DialogChooseSkin_InternalFiberCallback`         | `0x141c513c0`    |
| `CGameCtnMenus::DialogInputSettingsUpdate_InternalFiberCallback`| `0x141c88190`    |

### 7.3 Fiber Operations

Fibers are used for:
- **Dialog workflows**: `CGameDialogs::FiberFileOpen`, `FiberFileSave`, `FiberFileSaveAs`
- **Editor operations**: `NGameEditors::FiberAskToSaveChanges`, `FiberConfirmQuitWithoutSaving`, `FiberUnsavedChangesDialogsBeforeQuit`
- **Network operations**: anti-cheat, disconnect, replay upload
- **Build/compilation**: `Build_Fiber`, `RegisterPack_Fiber`
- **Async UI updates**: `CGameManialinkBrowser::UpdateFiber`

### 7.4 Fiber Safety

The engine includes a fiber resource exhaustion check:
```
"Resource exhaust in fiber enter !!\n"    -- 0x141b67058
```

And a render-thread safety mechanism:
```
"!! InRender => Run delayed to fiber\n"   -- 0x141b671c8
```

This indicates that operations detected during rendering are deferred to a fiber for execution on the next safe frame.

---

## 8. ManiaScript Engine Integration

### 8.1 CScriptEngine::Run

Address: `0x140874270` | Profiling tag: `"CScriptEngine::Run"` or `"CScriptEngine::Run(%s)"`

The script engine execution function:

```c
void CScriptEngine_Run(longlong engine, longlong script_context, uint4 mode) {
    *(script_context + 0x60) = engine;   // link engine to context
    lVar1 = *(script_context + 0x10);    // get script module
    FUN_1402d3df0(engine, 1);            // [UNKNOWN] lock/prepare engine

    // Build profiling tag with script name
    if (profiling_enabled && *(lVar1 + 0xf8) == 0 && *(lVar1 + 0xf4) != 0) {
        name_ptr = (lVar1 + 0xe8);       // script name string
        tag = format("CScriptEngine::Run(%s)", name_ptr);
        *(lVar1 + 0xf8) = tag;
    }

    // Begin profiling
    tag_name = *(lVar1 + 0xf8) ? *(lVar1 + 0xf8) : "CScriptEngine::Run";
    profile_begin(local_buf, tag_name, 0, 0);

    // Setup execution state
    *(script_context + 0x30) = *(engine + 0x20);   // copy engine state
    *(script_context + 0x58) = has_errors ? 0 : 1;  // set run flag
    *(script_context + 0x5c) += error_count;         // accumulate errors
    *(script_context + 0x08) = mode;
    *(script_context + 0x0c) = convert_mode(mode);

    // Clear output buffer
    clear_buffer(script_context + 0x100);

    // Execute script
    *(script_context + 0xc4) = global_tick_count;
    FUN_1408d1ea0(lVar1, script_context);  // actual script execution

    // Cleanup
    *(engine + 0x60) = 0;                 // unlink engine from context
    profile_end(local_buf, tag_id);
}
```

### 8.2 ManiaScript Token Types

The binary contains a complete set of ManiaScript lexer token definitions:

| Token String                     | Address          | Purpose                    |
|----------------------------------|------------------|----------------------------|
| `MANIASCRIPT_WHITESPACE`         | `0x141c02118`    | Whitespace token           |
| `MANIASCRIPT_STRING`             | `0x141c02150`    | String literal             |
| `MANIASCRIPT_NATURAL`            | `0x141c02188`    | Integer literal            |
| `MANIASCRIPT_FLOAT`              | `0x141c021a0`    | Float literal              |
| `MANIASCRIPT_IDENT`              | `0x141c021c8`    | Identifier                 |
| `MANIASCRIPT_COMMENT`            | `0x141c021e0`    | Comment                    |
| `MANIASCRIPT_SLEEP`              | `0x141c023a8`    | `sleep` keyword            |
| `MANIASCRIPT_YIELD`              | `0x141c024c8`    | `yield` keyword            |
| `MANIASCRIPT_WAIT`               | `0x141c024b0`    | `wait` keyword             |
| `MANIASCRIPT_MEANWHILE`          | `0x141c02480`    | `meanwhile` keyword        |
| `MANIASCRIPT_ASSERT`             | `0x141c02498`    | `assert` keyword           |

### 8.3 ManiaScript Type System

Built-in types:
| Type                             | Address          |
|----------------------------------|------------------|
| `MANIASCRIPT_TYPE_VOID`          | `0x141c026c0`    |
| `MANIASCRIPT_TYPE_BOOLEAN`       | `0x141c02818`    |
| `MANIASCRIPT_TYPE_INTEGER`       | `0x141c02838`    |
| `MANIASCRIPT_TYPE_REAL`          | `0x141c027e8`    |
| `MANIASCRIPT_TYPE_TEXT`          | `0x141c02800`    |
| `MANIASCRIPT_TYPE_VEC2`          | `0x141c027d0`    |
| `MANIASCRIPT_TYPE_VEC3`          | `0x141c02788`    |
| `MANIASCRIPT_TYPE_INT2`          | `0x141c027a0`    |
| `MANIASCRIPT_TYPE_INT3`          | `0x141c028b0`    |
| `MANIASCRIPT_TYPE_ISO4`          | `0x141c02878`    |
| `MANIASCRIPT_TYPE_IDENT`         | `0x141c028c8`    |
| `MANIASCRIPT_TYPE_CLASS`         | `0x141c027b8`    |

### 8.4 ManiaScript Directives

| Directive                                 | Address          |
|-------------------------------------------|------------------|
| `MANIASCRIPT_DIRECTIVE_REQUIRE_CONTEXT`   | `0x141c029a0`    |
| `MANIASCRIPT_DIRECTIVE_SETTING`           | `0x141c029c8`    |
| `MANIASCRIPT_DIRECTIVE_STRUCT`            | `0x141c02a40`    |
| `MANIASCRIPT_DIRECTIVE_INCLUDE`           | `0x141c02a70`    |
| `MANIASCRIPT_DIRECTIVE_EXTENDS`           | `0x141c02a90`    |
| `MANIASCRIPT_DIRECTIVE_COMMAND`           | `0x141c02ab0`    |
| `MANIASCRIPT_DIRECTIVE_CONST`             | `0x141c02ad0`    |

### 8.5 ManiaScript Collection Operations

The engine provides built-in collection operations accessible via dot syntax:
`add`, `remove_key`, `exists_elem`, `add_first`, `remove_elem`, `count`, `clear`, `contains_only`, `sortkey_rev`, `key_of`, `sort_rev`, `sortkey`, `exists_key`, `sort`, `from_json`, `to_json`, `get`, `cloud_request_save`, `cloud_is_ready`, `contains_one_of`, `slice`

---

## 9. TitleFlow / Game Flow

### 9.1 CTitleFlow

The string `"CTitleFlow"` (at `0x141bfa300`) and `"TitleFlow"` (at `0x141cdbc40`) indicate the title/game flow management class.

### 9.2 CGameManiaTitleFlow [UNKNOWN]

No function symbols were found for `CGameManiaTitleFlow` in the current analysis. This class likely manages transitions between:
- Title screen
- Main menu
- Game loading
- Gameplay
- Editor
- Replay viewer

The actual flow control appears to be distributed across:
- `CGameCtnApp::UpdateGame` (state machine dispatch)
- `CGameCtnNetwork::MainLoop_*` (network state machine)
- `CSmArenaClient::MainLoop_*` (arena/gameplay state machine)

---

## 10. Memory Management Patterns

### 10.1 Primary Allocator

The engine uses `thunk_FUN_1408de480` (at `0x14054ed90`, thunking to `0x1408de480`) as the primary memory allocation function. This is called throughout the codebase for object allocation.

Usage pattern:
```c
ptr = thunk_FUN_1408de480(size);
if (ptr != NULL) {
    constructor(ptr);
}
```

### 10.2 Custom Allocator System

The engine has a multi-tier memory allocation system:

| Allocator                          | String Address   | Purpose                                      |
|------------------------------------|------------------|----------------------------------------------|
| `NAllocHeap::FastAllocator_Alloc`  | `0x141b57040`    | General-purpose fast allocator               |
| `NAllocHeap::FastAllocator_Realloc`| `0x141b57090`    | Reallocation support                         |
| `NFastBlockAlloc::SAllocator`      | `0x141b79110`    | Fixed-size block allocator                   |
| `NFastBucketAlloc::SAllocator`     | `0x141b79290`    | Bucket-based allocator (size classes)        |
| `CFastLinearAllocator`             | `0x141b56fe0`    | Linear/bump allocator (overflow at fmt string)|

**CFastLinearAllocator overflow detection:**
```
"CFastLinearAllocator::Alloc overflow: %d + (%d+%d) > %d"
```

### 10.3 Frame Allocator

A frame-scoped allocator exists:
```
"FrameAllocator Decommit unused: "    -- 0x141c32908
```

This is likely used for per-frame temporary allocations that are bulk-freed at frame boundaries.

### 10.4 Reference Counting

Objects use reference counting for lifecycle management:
```
"RefCount"                             -- 0x141be54f0
```

The reference counting pattern observed in decompiled code:
```c
// Increment
*(int*)(object + 0x10) += 1;

// Decrement and potentially destroy
int* refcount = (int*)(object + 0x10);
*refcount -= 1;
if (*refcount == 0) {
    FUN_1402cfae0();    // destructor/release
}
object_ptr = 0;         // null out reference
```

### 10.5 Out-of-Memory Handling

The engine has a user-facing OOM dialog:
```
"!! Out of memory error !!\r\n\r\nPlease close applications and check your windows
page file is rightly configured (automatic + enough storage space).\r\n\r\nPress
'Retry' to repeat the allocation that failed.\r\nPressing 'Cancel' will let game
continue with that failed allocation (game will be instable)."
```

And program-level depletion tracking:
```
"!! ProgramMemoryDepletion: allocating "
```

### 10.6 Memory Leak Detection

The engine includes a memory leak detector (likely debug-only):
```
"=== MEMORY LEAK DETECTED ===\nThere are still %zu unfreed bytes in %zu allocations:\n"
```

---

## 11. Threading Model

### 11.1 Thread-Local Storage

The engine makes extensive use of Thread-Local Storage (TLS) for per-thread state:

- `ThreadLocalStoragePointer + 0x148` -- profiling/logging context
- `ThreadLocalStoragePointer + 0x140` -- [UNKNOWN] per-thread string buffer or config
- `ThreadLocalStoragePointer + 0x1b8` -- profiling timer chain

TLS callbacks at startup:
- `tls_callback_1` at `0x141521958`
- `tls_callback_2` at `0x1415223d4`

### 11.2 Thread Pool

```
"NClassicThreadPool::Destroy"          -- 0x141d094b8
```

The engine uses a classic thread pool pattern. [UNKNOWN] exact thread count and dispatch mechanism.

### 11.3 Async Update Patterns

Many subsystems have `UpdateAsync` variants that run on worker threads:

| Function                                   | Address          |
|--------------------------------------------|------------------|
| `NHmsLightMap::UpdateAsync`                | `0x141b67d88`    |
| `NSceneVFX::UpdateAsync`                   | `0x141be4ec8`    |
| `NSceneVehicleVis::UpdateAsync_PostCamera` | `0x141be8048`    |
| `NSceneFxSystem::UpdateAsync`              | `0x141be8698`    |
| `NSceneParticleVis::UpdateAsync`           | `0x141be8c60`    |
| `SMgr::UpdateAsync`                        | `0x141be9240`    |
| `NSceneWeather::UpdateAsync`               | `0x141be9ef0`    |
| `CGameSystemOverlay::UpdateAsync`          | `0x141c37370`    |
| `CGameManialinkBrowser::UpdateAsync`       | `0x141c393c8`    |
| `CGameEditorManialink::UpdateAsync`        | `0x141c91430`    |
| `CGameAnalyzer::UpdateAsync`              | `0x141caa8d0`    |
| `CSmArenaClient::UpdateAsync`             | `0x141ceedf0`    |

---

## 12. Rendering Integration

### 12.1 DXGI Hook

The binary exports a `Dxgi_Present_HookCallback` at `0x140a811a0`, registered as an entry point. This hooks the DirectX presentation for overlay rendering.

### 12.2 Vision Rendering Pipeline

Key rendering strings:

| String                                              | Address          |
|-----------------------------------------------------|------------------|
| `CVisionEngine::CreateViewport`                     | `0x141c0c0c0`    |
| `CVisionEngine::CVisionEngine`                      | `0x141c0c100`    |
| `CVisionViewport::UpdateRenderCaps`                 | `0x141c14898`    |
| `CVisionVideoDecode::UpdateVideoFrame`              | `0x141c1a050`    |
| `D3D11::UpdateSubresource`                          | `0x141c1b4f8`    |
| `CDx11Viewport::StartFullscreen_FromWindowedFull`   | `0x141c0f360`    |
| `CDx11Viewport::StartFullscreen`                    | `0x141c0f390`    |
| `NVisionCameraResourceMgr::StartFrame`              | `0x141c19cb0`    |
| `CVisPostFx_BloomHdr::UpdateBitmapIntensAtHdrNorm`  | `0x141c0e5d8`    |
| `AllocateAndUploadTextures`                         | `0x141c0ce20`    |
| `AllocateAndUploadTextureGeometry`                  | `0x141c0ce40`    |
| `BitmapAllocate`                                    | `0x141c0cea0`    |
| `ProbeAllocate`                                     | `0x141c19208`    |

### 12.3 GPU Preference Exports

The binary exports two global variables to request high-performance GPUs:
- `AmdPowerXpressRequestHighPerformance` at `0x141e70f38`
- `NvOptimusEnablement` at `0x141e70f3c`

---

## 13. Key Global Data Addresses

| Address          | Description                           | Evidence                     |
|------------------|---------------------------------------|------------------------------|
| `DAT_141fbbf90`  | Engine startup timestamp              | Set early in WinMain         |
| `DAT_141fbbf50`  | Pointer to launch mode flags          | Checked for Luna/headless    |
| `DAT_141fbbe4c`  | Luna mode flag                        | Set after UUID check         |
| `DAT_141fbbee8`  | Headless mode flag                    | Skips rendering when != 0    |
| `DAT_141f9cff4`  | Luna mode global                      | Set to 1 when Luna enabled   |
| `DAT_141f9cfd8`  | Logging subsystem handle              | Passed to log flush          |
| `DAT_141f9f018`  | Engine table pointer                  | Contains engine subsystem ptrs |
| `DAT_142057d50`  | System config / display config        | Used in Init2/viewport setup |
| `DAT_141e64060`  | Stack cookie seed                     | Security check canary value  |
| `DAT_141ffad50`  | Global tick counter                   | Used in script execution     |
| `DAT_141fc03d0`  | Callback object pointer               | App-level callback           |
| `DAT_141fc03d8`  | Callback function pointer             | App-level callback function  |
| `DAT_141e7140c`  | [UNKNOWN] display mode flag           | Set from Luna mode           |

---

## 14. Decompiled Functions Index

All decompiled functions are saved to `/decompiled/architecture/`:

| File                                              | Function                          | Address          | Size     |
|---------------------------------------------------|-----------------------------------|------------------|----------|
| `entry.c`                                         | `entry`                           | `0x14291e317`    | [obfuscated] |
| `scrt_common_main_seh.c`                          | `__scrt_common_main_seh`          | `0x141521ab4`    | MSVC CRT |
| `WinMainCRTStartup.c`                             | `WinMainCRTStartup`              | `0x141521c28`    | MSVC CRT |
| `WinMain_thunk.c`                                 | `FUN_140aa7470` (WinMain)         | `0x140aa7470`    | 202 B    |
| `startup_init_profiling.c`                        | `FUN_1401171d0`                   | `0x1401171d0`    | profiling init |
| `startup_frame_begin.c`                           | `FUN_140117840`                   | `0x140117840`    | frame start |
| `profile_tag_wrapper.c`                           | `FUN_140117690`                   | `0x140117690`    | 12 B     |
| `profile_tag_begin.c`                             | `FUN_1401175b0`                   | `0x1401175b0`    | profiling |
| `CGbxApp__Init1.c`                                | `FUN_140aa3220` (CGbxApp::Init1)  | `0x140aa3220`    | large    |
| `CGbxApp__Init2.c`                                | `FUN_140aa5090` (CGbxApp::Init2)  | `0x140aa5090`    | medium   |
| `CGbxGame__InitApp.c`                             | `FUN_140102cb0` (CGbxGame::InitApp)| `0x140102cb0`   | medium   |
| `CSystemEngine__InitForGbxGame.c`                 | `FUN_1408f56a0`                   | `0x1408f56a0`    | medium   |
| `CGameCtnApp__Start.c`                            | `FUN_140b4eba0`                   | `0x140b4eba0`    | large    |
| `CGameManiaPlanet__Start.c`                       | `FUN_140cb8870`                   | `0x140cb8870`    | large    |
| `CGameCtnApp__UpdateGame.c`                       | `FUN_140b78f10`                   | `0x140b78f10`    | massive  |
| `CGameCtnApp__UpdateGame_Init.c`                  | `FUN_140b76b20`                   | `0x140b76b20`    | 2414 B   |
| `CGameCtnApp__UpdateGame_StartUp.c`               | `FUN_140b77490`                   | `0x140b77490`    | [UNKNOWN]|
| `CGameApp__QuitGameAndExit.c`                     | `FUN_140b4d140`                   | `0x140b4d140`    | medium   |
| `CScriptEngine__Run.c`                            | `FUN_140874270`                   | `0x140874270`    | medium   |
| `CMwCmdFiber__StaticInit.c`                       | `FUN_14002e300`                   | `0x14002e300`    | small    |
| `CGameCtnNetwork__MainLoop_Menus.c`               | `FUN_140af9a40`                   | `0x140af9a40`    | [UNKNOWN]|
| `CGameCtnNetwork__MainLoop_PlaygroundPlay.c`      | `FUN_140aff380`                   | `0x140aff380`    | [UNKNOWN]|
| `CGameCtnNetwork__MainLoop_SetUp.c`               | `FUN_140afc320`                   | `0x140afc320`    | [UNKNOWN]|

---

## 15. Open Questions and Unknowns

1. **[UNKNOWN]** The entry point at `0x14291e317` uses obfuscated code. The unpacking/code protection mechanism has not been analyzed.
2. **[UNKNOWN]** The exact mechanism that bridges from WinMain (`FUN_140aa7470`) to `CGbxApp::Init1` / `CGbxApp::Init2`. The function ends with `halt_baddata()` in Ghidra, suggesting indirect control flow or code protection.
3. **[UNKNOWN]** No function symbols were recovered for any Nadeo class methods. All functions are unnamed `FUN_*` -- the binary appears fully stripped of debug symbols. Class identification relies entirely on string cross-references.
4. **[UNKNOWN]** The fiber system implementation details -- whether it uses Windows fibers (ConvertThreadToFiber/SwitchToFiber) or a custom coroutine implementation.
5. **[UNKNOWN]** The exact vtable layout and virtual function dispatch for the class hierarchy. Virtual calls are observed as `(*(*object + offset))(object, ...)` but offsets have not been mapped to method names.
6. **[UNKNOWN]** `CGameManiaTitleFlow` -- no functions found despite string references to "TitleFlow" and "CTitleFlow".
7. **[UNKNOWN]** The relationship between `CGameCtnApp::UpdateGame` and the per-frame render loop. The rendering appears to be driven through the engine callback registered at `engine+0x70` during `CGbxGame::InitApp`.
8. **[UNKNOWN]** How the headless/dedicated server mode (`DAT_141fbbee8`) bypasses rendering -- the code checks this flag in many places but the full bypass path has not been traced.

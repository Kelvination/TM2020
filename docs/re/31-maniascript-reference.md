# ManiaScript Language Reference

**Date**: 2026-03-27
**Sources**: Ghidra RE (docs 12, 13, 15), decompiled `CScriptEngine__Run.c`, `class_hierarchy.json`, community documentation (ManiaScript Book, boss-bravo.fr, maniaplanet/documentation, maniaplanet.github.io/maniascript-reference)
**Confidence**: VERIFIED (binary tokens) + COMMUNITY-CONFIRMED (syntax/semantics)

---

## Table of Contents

1. [Language Overview](#1-language-overview)
2. [Data Types (12 Primitive Types)](#2-data-types-12-primitive-types)
3. [Variable Declarations](#3-variable-declarations)
4. [Operators](#4-operators)
5. [Control Flow](#5-control-flow)
6. [Functions](#6-functions)
7. [Collections (Arrays and Maps)](#7-collections-arrays-and-maps)
8. [Collection Operations (17 Dot Methods)](#8-collection-operations-17-dot-methods)
9. [Coroutines and Cooperative Multitasking](#9-coroutines-and-cooperative-multitasking)
10. [Preprocessor Directives (7)](#10-preprocessor-directives-7)
11. [Script Contexts](#11-script-contexts)
12. [Classes and Object Model](#12-classes-and-object-model)
13. [Events](#13-events)
14. [Network Variables](#14-network-variables)
15. [Persistent and Cloud Storage](#15-persistent-and-cloud-storage)
16. [Serialization (JSON)](#16-serialization-json)
17. [Debug and Tuning](#17-debug-and-tuning)
18. [Built-in API: Script Managers](#18-built-in-api-script-managers)
19. [Game Mode Scripting](#19-game-mode-scripting)
20. [ManiaLink Scripting](#20-manialink-scripting)
21. [Map Editor Plugin Scripting](#21-map-editor-plugin-scripting)
22. [Standard Libraries](#22-standard-libraries)
23. [Lexer and Token Types](#23-lexer-and-token-types)
24. [Script Engine Internals (from RE)](#24-script-engine-internals-from-re)
25. [Browser Recreation: Interpreter/Transpiler Approach](#25-browser-recreation-interpretertranspiler-approach)

---

## 1. Language Overview

ManiaScript is the embedded scripting language in the ManiaPlanet/Trackmania engine, created by Nadeo. It is interpreted by `CScriptEngine`, a singleton engine class confirmed at binary address `0x140874270` (the `CScriptEngine::Run` entry point).

**Key characteristics**:
- **Statically typed** with type inference on declarations
- **Cooperative multitasking** via `yield`, `sleep`, `wait`, `meanwhile`
- **No user-defined classes** -- scripts work exclusively with engine-provided class instances
- **Pointer/alias semantics** for object references (`=` for stable ID binding, `<=>` for dynamic alias)
- **Main-thread execution only** -- all script runs on the main thread, even when triggered from `CGameManialinkBrowser::UpdateAsync` on a worker thread
- **Interpreted** -- bytecode interpreter at `FUN_1408d1ea0`, invoked by `CScriptEngine::Run`
- **Frame-synchronized** -- scripts yield control each frame via `yield;` and are resumed by the engine

**Language targets**:
- Game mode rules (server-side)
- ManiaLink UI pages (client-side)
- Map editor plugins
- MediaTracker scripted camera effects
- Server plugins

---

## 2. Data Types (12 Primitive Types)

All 12 types confirmed via binary strings at `MANIASCRIPT_TYPE_*` tokens in the Trackmania.exe binary.

| # | Token (Binary) | ManiaScript Type | C++ Equivalent | Size | Literal Syntax |
|---|----------------|-----------------|----------------|------|----------------|
| 1 | `MANIASCRIPT_TYPE_VOID` | `Void` | void | 0 | -- (return type only) |
| 2 | `MANIASCRIPT_TYPE_BOOLEAN` | `Boolean` | bool | 4 bytes (GBX convention) | `True`, `False` |
| 3 | `MANIASCRIPT_TYPE_INTEGER` | `Integer` | int32_t | 4 bytes | `42`, `-7`, `0xFF` |
| 4 | `MANIASCRIPT_TYPE_REAL` | `Real` | float | 4 bytes | `3.14`, `2.` (trailing dot required) |
| 5 | `MANIASCRIPT_TYPE_TEXT` | `Text` | string | SSO string | `"hello"`, `"""multiline"""` |
| 6 | `MANIASCRIPT_TYPE_VEC2` | `Vec2` | float[2] | 8 bytes | `<1.0, 2.0>` |
| 7 | `MANIASCRIPT_TYPE_VEC3` | `Vec3` | float[3] | 12 bytes | `<1.0, 2.0, 3.0>` |
| 8 | `MANIASCRIPT_TYPE_INT2` | `Int2` | int32_t[2] | 8 bytes | `<1, 2>` |
| 9 | `MANIASCRIPT_TYPE_INT3` | `Int3` | int32_t[3] | 12 bytes | `<1, 2, 3>` |
| 10 | `MANIASCRIPT_TYPE_ISO4` | `Iso4` | float[12] | 48 bytes | 3x3 rotation matrix + vec3 translation |
| 11 | `MANIASCRIPT_TYPE_IDENT` | `Ident` | uint32_t (MwId) | 4 bytes | Interned resource identifier |
| 12 | `MANIASCRIPT_TYPE_CLASS` | `Class` | pointer | 8 bytes | Reference to engine class instance |

### 2.1 Type Details

**Boolean**: Always `True` or `False` (capitalized). Default value: `False`.

**Integer**: Signed 32-bit. Default: `0`.

**Real**: IEEE 754 single-precision float. Literals require a trailing dot if no decimal digits: `2.` not `2`. Default: `0.0`.

**Text**: UTF-8 string. Default: `""`. Supports:
- Escape sequences: `\n`, `\\`, `\"`
- Triple-quoted multiline: `"""content with "quotes" inside"""`
- String interpolation in triple-quoted: `"""{{{expression}}}"""`
- Concatenation operator: `^` (also auto-converts Integer, Real, Boolean to Text)

**Vec2 / Vec3**: Floating-point vectors. Components accessed via `.X`, `.Y`, `.Z`.

**Int2 / Int3**: Integer vectors. Same component access as Vec2/Vec3.

**Iso4**: 4x4 isometric transform (3x3 rotation + translation). Used for positions and orientations in 3D space.

**Ident**: Interned identifier (MwId). Used for referencing resources like models, sounds, and images. `NullId` is the empty ident.

**Class**: A reference (pointer) to an engine-provided object. Cannot be user-instantiated. Accessed through engine API properties.

---

## 3. Variable Declarations

### 3.1 Basic Declaration

```maniascript
declare Integer MyVar;              // Explicit type, default value (0)
declare Integer MyVar = 42;         // Explicit type with initial value
declare MyVar = 42;                 // Type inferred from initializer (Integer)
declare Text[] Names;               // Array of Text (requires explicit type)
declare Text[Integer] Lookup;       // Associative array (map)
```

### 3.2 Scope Rules

- **Local variables**: Declared inside functions with `declare`. Block-scoped (curly brackets).
- **Global variables**: Declared outside functions. Cannot use initial values; explicit type required.
- Variables are immutable in type once declared.
- Default values: `0` for Integer, `0.0` for Real, `False` for Boolean, `""` for Text, `NullId` for Ident.

### 3.3 Extension Variables (Attached to Objects)

Variables can be attached to engine objects using the `for` keyword:

```maniascript
declare Integer CustomScore for Players[0];
declare Text Tag for LocalUser = "default";
```

When reading an extension variable from an object that has not had it set, the default value is returned. The `= value` in the declaration sets the read-default, not an assignment.

### 3.4 Aliases (`as`)

Extension variables can be given local aliases to avoid ambiguity:

```maniascript
declare Integer CustomScore for Players[0] as Score1;
declare Integer CustomScore for Players[1] as Score2;
```

### 3.5 Pointer vs. Alias Binding

Two binding modes for object references:

```maniascript
// Alias binding (dynamic) -- tracks array position
declare CPlayer FirstPlayer <=> Players[0];
// If Players[0] changes, FirstPlayer follows the new Players[0]

// Assignment binding (stable) -- tracks object identity
declare CPlayer StableRef = Players[0];
// Tracks this specific player even if their array index changes
```

### 3.6 Declaration Modifiers

| Modifier | Syntax | Purpose |
|----------|--------|---------|
| `persistent` | `declare persistent Integer SavedScore for LocalUser;` | Saved across sessions (cloud/profile) |
| `netread` | `declare netread Integer Net_Score for UI;` | Readable network variable |
| `netwrite` | `declare netwrite Integer Net_Score for UI;` | Writable network variable |
| `metadata` | `declare metadata Integer Meta_Version for Map;` | Stored in map/replay metadata |

---

## 4. Operators

### 4.1 Arithmetic

| Operator | Types | Result | Notes |
|----------|-------|--------|-------|
| `+` | Integer, Real | Same type / Real if mixed | Addition |
| `-` | Integer, Real | Same type / Real if mixed | Subtraction |
| `*` | Integer, Real | Same type / Real if mixed | Multiplication |
| `/` | Integer, Real | Same type / Real if mixed | Division (integer division truncates) |
| `%` | Integer | Integer | Modulo |

### 4.2 String

| Operator | Purpose | Example |
|----------|---------|---------|
| `^` | Concatenation (auto-converts types to Text) | `"Score: " ^ Score` |

### 4.3 Comparison

| Operator | Valid Types | Notes |
|----------|------------|-------|
| `==` | All types | Equality |
| `!=` | All types | Inequality |
| `<` | Integer, Real, Text | Less than (not valid for Boolean) |
| `>` | Integer, Real, Text | Greater than |
| `<=` | Integer, Real, Text | Less than or equal |
| `>=` | Integer, Real, Text | Greater than or equal |

### 4.4 Logical

| Operator | Purpose |
|----------|---------|
| `!` | Logical NOT |
| `&&` | Logical AND (short-circuit) |
| `\|\|` | Logical OR (short-circuit) |

### 4.5 Assignment

| Operator | Purpose |
|----------|---------|
| `=` | Assignment (stable identity binding for objects) |
| `<=>` | Alias binding (dynamic reference) |
| `+=`, `-=`, `*=`, `/=` | Compound assignment |
| `^=` | String append |

### 4.6 Vector Construction

```maniascript
declare Vec3 Pos = <1.0, 2.0, 3.0>;
declare Int3 Coord = <5, 10, 15>;
```

---

## 5. Control Flow

### 5.1 Conditional

```maniascript
if (Condition) {
    // ...
} else if (OtherCondition) {
    // ...
} else {
    // ...
}
```

### 5.2 While Loop

```maniascript
while (Condition) {
    // ...
}
```

### 5.3 For Loop (Range-based)

```maniascript
for (I, 0, 10) {
    // I goes from 0 to 10 inclusive
    log(I);
}
```

### 5.4 Foreach

```maniascript
// Iterate values
foreach (Player in Players) {
    log(Player.Login);
}

// Iterate key-value pairs
foreach (Key => Value in MyMap) {
    log(Key ^ ": " ^ Value);
}
```

### 5.5 Switch / Case

```maniascript
switch (Event.Type) {
    case CMlScriptEvent::Type::MouseClick: {
        log("Click on " ^ Event.ControlId);
    }
    case CMlScriptEvent::Type::KeyPress: {
        log("Key: " ^ Event.KeyName);
    }
    default: {
        // ...
    }
}
```

### 5.6 SwitchType (Type-based dispatch)

```maniascript
switchtype (Event) {
    case CSmModeEvent: {
        // Handle ShootMania event
    }
    case CMlScriptEvent: {
        // Handle ManiaLink event
    }
    default: {
        // Unknown event type
    }
}
```

### 5.7 Flow Control Keywords

| Keyword | Purpose |
|---------|---------|
| `break` | Exit current loop |
| `continue` | Skip to next iteration |
| `return` | Return from function (with optional value) |

---

## 6. Functions

### 6.1 Declaration

```maniascript
Integer Add(Integer A, Integer B) {
    return A + B;
}

Void SayHello(Text Name) {
    log("Hello, " ^ Name);
}

Text GetGreeting() {
    return "Welcome!";
}
```

### 6.2 Entry Point

The `main()` function is the script entry point:

```maniascript
main() {
    while (True) {
        // Main loop
        yield;
    }
}
```

For simple scripts (ManiaLink), a bare script body without `main()` is allowed.

### 6.3 No Overloading or Variadic Functions

ManiaScript does not support function overloading or variadic parameters. Engine API methods may have overloaded variants, but user-defined functions cannot.

---

## 7. Collections (Arrays and Maps)

### 7.1 Array (Ordered List)

```maniascript
declare Text[] Names = ["Alice", "Bob", "Charlie"];
declare Integer[] Empty;

// Access by index (0-based)
log(Names[0]);  // "Alice"

// Iteration
foreach (Name in Names) {
    log(Name);
}
```

### 7.2 Associative Array (Map)

```maniascript
declare Text[Integer] IdToName = [1 => "Alice", 2 => "Bob"];
declare Integer[Text] NameToScore;

// Access by key
log(IdToName[1]);  // "Alice"

// Iteration with keys
foreach (Id => Name in IdToName) {
    log(Id ^ ": " ^ Name);
}
```

### 7.3 Valid Key/Value Type Combinations

Keys can be: `Integer`, `Text`, `Ident`, `Boolean`, enum types, or Class references.
Values can be: any ManiaScript type including arrays (nested).

---

## 8. Collection Operations (17 Dot Methods)

All confirmed via binary string search in Trackmania.exe. These are dot-prefixed method calls on array/map instances.

### 8.1 Mutation Operations

| Operation | Signature | Description |
|-----------|-----------|-------------|
| `.add` | `Array.add(Elem)` | Append element to end of array |
| `.addfirst` | `Array.addfirst(Elem)` | Insert element at beginning |
| `.remove` | `Array.remove(Elem)` | Remove first occurrence of element |
| `.removekey` | `Map.removekey(Key)` | Remove entry by key |
| `.clear` | `Collection.clear()` | Remove all elements |

### 8.2 Access Operations

| Operation | Signature | Description |
|-----------|-----------|-------------|
| `.count` | `Collection.count` | Number of elements (property, not method) |
| `.get` | `Map.get(Key, Default)` | Get value by key with default fallback |
| `.slice` | `Array.slice(Start, Count)` | Extract sub-array |
| `.keyof` | `Array.keyof(Elem)` | Get key/index of first occurrence |

### 8.3 Sorting Operations

| Operation | Signature | Description |
|-----------|-----------|-------------|
| `.sort` | `Array.sort()` | Sort ascending |
| `.sortrev` | `Array.sortrev()` | Sort descending |
| `.sortkey` | `Array.sortkey()` | Sort by key ascending |
| `.sortkeyrev` | `Array.sortkeyrev()` | Sort by key descending |

### 8.4 Query Operations

| Operation | Signature | Description |
|-----------|-----------|-------------|
| `.existskey` | `Map.existskey(Key)` | Check if key exists; returns `Boolean` |
| `.existselem` | `Array.existselem(Elem)` | Check if element exists; returns `Boolean` |
| `.containsonly` | `A.containsonly(B)` | Set operation: all elements of A are in B |
| `.containsoneof` | `A.containsoneof(B)` | Set operation: at least one element of A is in B |

---

## 9. Coroutines and Cooperative Multitasking

ManiaScript has built-in cooperative multitasking through four coroutine primitives. All confirmed as lexer tokens in the binary (addresses `0x141c023a8`, `0x141c024c8`, `0x141c024b0`).

### 9.1 Yield

```maniascript
yield;
```

Pauses execution and returns control to the engine. The script resumes at the next frame. This is the fundamental scheduling primitive.

**Implementation**: The script sets its return state and returns from the bytecode interpreter `FUN_1408d1ea0`. The engine re-enters the same context on the next frame.

**Usage**: Every ManiaScript main loop must include `yield;` to prevent infinite loops:

```maniascript
main() {
    while (True) {
        foreach (Event in PendingEvents) {
            // Process events
        }
        yield;
    }
}
```

### 9.2 Sleep

```maniascript
sleep(1000);  // Pause for 1000 milliseconds
```

Pauses execution for the specified duration in milliseconds. The engine checks the timer each frame by comparing the timestamp at `*(context+0xC4)` against the global tick counter `DAT_141ffad50`.

### 9.3 Wait

```maniascript
wait(Player.IsSpawned);
wait(Http.IsCompleted);
```

Evaluates the condition expression each frame. If `False`, the script yields. When the condition becomes `True`, execution continues. Equivalent to:

```maniascript
while (!Condition) yield;
```

### 9.4 Meanwhile

```maniascript
// The meanwhile block runs concurrently with the parent flow
meanwhile {
    // This block executes each frame alongside the outer code
    UpdateUI();
}
```

Creates a parallel execution branch within the script using the same fiber mechanism but with additional context for tracking multiple execution points. This enables concurrent tasks within a single script (e.g., updating a HUD while the main game logic runs).

### 9.5 Execution Model

ManiaScript runs at specific points within each frame, always on the main thread:

1. **During gameplay states** (state machine values 0xFE4, 0x1013, 0x1032): Script is invoked as part of the gameplay dispatch.
2. **During menu/UI**: `CGameManialinkBrowser::UpdateAsync` runs on a worker thread, but actual script execution via `CScriptEngine::Run` is always main-thread.
3. **Relative to physics**: Script runs AFTER the physics step. The arena client processes physics first, then dispatches script events.

---

## 10. Preprocessor Directives (7)

All 7 confirmed as lexer tokens in the binary.

### 10.1 `#RequireContext`

```maniascript
#RequireContext CSmMode
```

Specifies the required script execution context class. This provides type safety: the script will only load if attached to the correct context. Available contexts are listed in [Section 11](#11-script-contexts).

### 10.2 `#Setting`

```maniascript
#Setting S_TimeLimit 300 as "Time limit"
#Setting S_PointsLimit 100 as _("Points limit")
#Setting S_UseTieBreak True as "Use tie-break"
```

Declares a configurable setting variable. Settings can be modified by server administrators and players without editing script code. The `as` clause provides a display name; `_()` marks it for translation. Supported types: Integer, Real, Boolean, Text.

### 10.3 `#Struct`

```maniascript
#Struct K_PlayerData {
    Integer Score;
    Text Name;
    Boolean IsAlive;
}
```

Defines a struct type. Struct names conventionally start with `K_`. Structs can be used as variable types, in arrays, and serialized to/from JSON.

### 10.4 `#Include`

```maniascript
#Include "MathLib" as MathLib
#Include "TextLib" as TextLib
#Include "Libs/Nadeo/Message.Script.txt" as Message
```

Imports a library script. The `as` clause provides a namespace alias. Library functions are called as `Namespace::FunctionName()`.

### 10.5 `#Extends`

```maniascript
#Extends "Modes/TrackMania/Base/TrackmaniaBase.Script.txt"
```

Extends a base script. Used primarily for game modes to inherit from Nadeo's base mode framework. The base script provides the `main()` function with structured labels for code injection (see [Section 19](#19-game-mode-scripting)).

### 10.6 `#Command`

```maniascript
#Command MyCommand(Integer Param) as "Execute my command"
```

Registers a callable command. Commands can be invoked from the server admin interface or other scripts.

### 10.7 `#Const`

```maniascript
#Const C_MaxPlayers 64
#Const C_Version "1.0.0"
#Const CompatibleMapTypes "TrackMania\\TM_Race,TrackMania\\TM_Royal"
```

Defines a compile-time constant. Constants conventionally start with `C_`. Standard game mode constants include `CompatibleMapTypes`, `Version`, and `ScriptName`.

---

## 11. Script Contexts

Each ManiaScript script runs within a specific context class that determines which API is available. The context is set via `#RequireContext` and validated at load time.

### 11.1 Context Class Hierarchy

| Context Class | Purpose | Where It Runs |
|---------------|---------|---------------|
| `CSmMode` | ShootMania/TrackMania game mode rules | Server (authoritative) |
| `CMapType` | Map type validation plugin | Map editor / server |
| `CSmMapType` | ShootMania-specific map type | Map editor |
| `CMlScript` | ManiaLink page script (standalone) | Client UI |
| `CMlScriptIngame` | ManiaLink script during gameplay | Client in-game UI |
| `CTmMlScriptIngame` | TrackMania-specific in-game ManiaLink | Client in-game UI |
| `CManiaApp` | Maniaplanet client application script | Client |
| `CManiaAppPlayground` | Client ManiaApp for game modes | Client during gameplay |
| `CManiaAppTitle` | Title screen application | Client title/menu |
| `CManiaAppStation` | Station (title lobby) | Client station |
| `CManiaAppBrowser` | ManiaLink browser | Client browser |
| `CMapEditorPlugin` | Map editor plugin | Map editor |
| `CEditorMainPlugin` | Main editor plugin | Editor |
| `CServerPlugin` | Dedicated server plugin | Server |

### 11.2 Context-Specific API Access

Each context provides different global variables and managers:

**CSmMode** (game mode):
- `Players[]`, `Spectators[]`, `AllPlayers[]`
- `Map`, `MapList[]`
- `UIManager`, `Scores[]`
- `ServerAdmin`, `XmlRpc`
- `Http`, `Xml`, `DataFileMgr`

**CMlScript** (ManiaLink):
- `Page` (CMlPage -- the current ManiaLink page)
- `PendingEvents[]` (CMlScriptEvent)
- `LocalUser`, `LoadedTitle`
- `Http`, `Xml`, `Audio`, `Video`, `Input`
- `DataFileMgr`, `ScoreMgr`, `AnimMgr`, `System`
- Mouse/keyboard state: `MouseX`, `MouseY`, `KeyUp/Down/Left/Right`, `IsKeyPressed()`

**CMapEditorPlugin** (editor):
- `Map`, `MapName`, `MapFileName`
- `PendingEvents[]` (CMapEditorPluginEvent)
- `PlaceMode`, `EditMode`
- Block/item placement methods

### 11.3 Context Classes in Binary

From the class hierarchy (2,027 classes), the script engine infrastructure consists of 9 core classes:

```
CScriptEngine                    -- Script VM singleton (has Run, Compilation methods)
CScriptBaseEvent                 -- Script event base
CScriptBaseConstEvent            -- Const script event base
CScriptEvent                     -- Script event
CScriptInterfacableValue         -- Script-exposed value
CScriptPoison                    -- Script memory poison (debug tool)
CScriptSetting                   -- Script setting (#Setting storage)
CScriptTraitsMetadata            -- Script traits
CScriptTraitsPersistent          -- Persistent script traits
```

---

## 12. Classes and Object Model

### 12.1 No User-Defined Classes

ManiaScript does **not** allow defining new classes. Scripts interact exclusively with engine-provided class instances. You cannot instantiate objects directly; you work with objects provided by the context (e.g., `Players[0]`, `Page.GetFirstChild("id")`).

### 12.2 Class References

```maniascript
// Get a reference to an existing object
declare CSmPlayer Target = Players[0];

// Access properties
log(Target.Login);
log(Target.Score.Points);

// Null check
if (Target != Null) {
    // Safe to use
}
```

### 12.3 Casting

```maniascript
declare MyLabel <=> (Page.GetFirstChild("label_id") as CMlLabel);
declare MyQuad <=> (Page.GetFirstChild("quad_id") as CMlQuad);
```

The `as` operator casts a class reference to a more specific type. Returns `Null` if the cast is invalid.

### 12.4 Enum Access

Enums are accessed via their class scope:

```maniascript
if (Event.Type == CMlScriptEvent::Type::MouseClick) { ... }
if (Player.SpawnStatus == CSmPlayer::ESpawnStatus::Spawned) { ... }
```

### 12.5 Key API Classes (TM2020)

From the Doxygen-generated reference (boss-bravo.fr, BigBang1112/maniascript-reference) and our binary class hierarchy:

| Class | Description | Script API Role |
|-------|-------------|-----------------|
| `CSmMode` | Game mode rules API | Server-side game logic |
| `CSmPlayer` | Player incarnation | Player state + control |
| `CSmPlayerDriver` | Bot AI controller | Bot behavior scripting |
| `CUser` | User profile | Identity + stats |
| `CClient` | Connected user | Network client |
| `CMap` | Map data | Current map info |
| `CMapLandmark` | Map landmark | Spawn/checkpoint/finish positions |
| `CBlockModel` | Block model | Block properties |
| `CUIConfig` | UI configuration | HUD layer management |
| `CUILayer` | UI layer | ManiaLink page overlay |
| `CScore` | Player score | Points/time tracking |
| `CGhostManager` | Ghost manager | Ghost recording/playback |
| `CScoreMgr` | Score manager | Leaderboard access |
| `CHttpManager` | HTTP manager | Web requests |
| `CHttpRequest` | HTTP request | Single request handle |
| `CDataFileMgr` | Data file manager | File I/O |
| `CParsingManager` | XML/JSON parser | Data parsing |
| `CAudioManager` | Audio manager | Sound playback |
| `CInputManager` | Input manager | Gamepad/keyboard access |
| `CVideoManager` | Video manager | Video playback |
| `CAnimManager` | Animation manager | UI animations |
| `CSystemPlatform` | System platform | OS-level operations |
| `CServerPlugin` | Server plugin | Dedicated server scripting |

---

## 13. Events

### 13.1 Event-Driven Architecture

ManiaScript uses a pull-based event model. Events accumulate in `PendingEvents` arrays and are processed in the script's main loop:

```maniascript
foreach (Event in PendingEvents) {
    switch (Event.Type) {
        case CSmModeEvent::EType::OnPlayerRequestRespawn: {
            // Handle respawn request
        }
        case CSmModeEvent::EType::OnPlayerTriggersWaypoint: {
            // Handle checkpoint/finish
        }
    }
}
```

### 13.2 Game Mode Events (CSmModeEvent)

Key event types for TrackMania game modes:

| Event Type | Trigger |
|------------|---------|
| `OnPlayerRequestRespawn` | Player presses respawn |
| `OnPlayerTriggersWaypoint` | Player crosses checkpoint/finish |
| `OnPlayerTriggersStart` | Player crosses start line |
| `OnPlayerAdded` | Player joins server |
| `OnPlayerRemoved` | Player leaves server |
| `OnCommand` | Admin/script command received |

### 13.3 ManiaLink Events (CMlScriptEvent)

| Event Type | Trigger |
|------------|---------|
| `MouseClick` | Mouse click on element (requires `scriptevents="1"`) |
| `MouseOver` | Mouse enters element |
| `MouseOut` | Mouse leaves element |
| `KeyPress` | Keyboard key pressed |
| `EntrySubmit` | Text entry submitted |
| `MenuNavigation` | Gamepad/keyboard menu navigation |
| `PluginCustomEvent` | Custom event from another layer |

**Event properties**:
- `Event.ControlId` -- ID of the UI element that triggered the event
- `Event.KeyCode` -- Key code for KeyPress events
- `Event.KeyName` -- Key name string
- `Event.CustomEventType` -- Type string for custom events
- `Event.CustomEventData` -- Data array for custom events

### 13.4 Map Editor Events (CMapEditorPluginEvent)

| Event Type | Trigger |
|------------|---------|
| `MapModified` | Map was changed |
| `StartTest` | Test mode started |
| `StartValidation` | Validation started |
| `EditAnchor` | Anchor edited |

### 13.5 Custom Events (Cross-Layer Communication)

```maniascript
// Sending from ManiaLink layer:
SendCustomEvent("MyEventType", ["data1", "data2"]);

// Receiving in game mode:
foreach (Event in PendingEvents) {
    if (Event.Type == CManiaAppEvent::EType::LayerCustomEvent) {
        if (Event.CustomEventType == "MyEventType") {
            log(Event.CustomEventData[0]);
        }
    }
}
```

---

## 14. Network Variables

ManiaScript provides `netread` and `netwrite` modifiers for cross-layer communication between game mode scripts and ManiaLink UI scripts.

### 14.1 Declaration

```maniascript
// In game mode script (server-side):
declare netwrite Integer Net_Score for UI;
declare netwrite Text Net_Message for UI;

// In ManiaLink script (client-side):
declare netread Integer Net_Score for UI;
declare netread Text Net_Message for UI;
```

### 14.2 Scopes

Network variables can be scoped to three object types:

| Scope | Declaration | Visibility |
|-------|-------------|------------|
| `for UI` | Per-player UI | Only visible to that player's ManiaLink |
| `for Teams[N]` | Per-team | Visible to all players on team N |
| `for Players[N]` | Per-player | Visible to all ManiaLink layers for that player |

### 14.3 Naming Convention

Network variables should be prefixed with `Net_` by convention.

### 14.4 Limitations

- Cannot name a `netread`/`netwrite` variable with the same name as a standard variable
- Cannot modify a `netread` variable (will crash the script)
- Do not work with bots (will crash)
- Alternative approach: use triple-bracket interpolation `{{{S_PointLimit}}}` for simple value passing from game mode to ManiaLink, but this does not allow dynamic updates

---

## 15. Persistent and Cloud Storage

### 15.1 Persistent Variables

```maniascript
declare persistent Integer Persistent_BestScore for LocalUser;
declare persistent Text Persistent_Settings for LocalUser;
```

Persistent variables are saved in the player's profile. They survive server changes, game restarts, and reinstalls (if profile is preserved). The `persistent` modifier was historically called "script cloud" by Nadeo.

### 15.2 Cloud Storage Operations

Two collection operations for cloud persistence are confirmed in the binary:

| Operation | Description |
|-----------|-------------|
| `.cloudrequestsave` | Request save of collection data to Nadeo cloud storage |
| `.cloudisready` | Check if a pending cloud operation has completed |

These enable asynchronous cloud save/load for script data beyond simple persistent variables.

---

## 16. Serialization (JSON)

### 16.1 Collection Serialization

Two collection operations confirmed in binary:

```maniascript
// Serialize to JSON
declare Text JsonString = MyStruct.tojson();

// Deserialize from JSON
declare K_PlayerData Data;
Data.fromjson(JsonString);
```

### 16.2 Usage with Structs

```maniascript
#Struct K_Config {
    Integer MaxPlayers;
    Text ServerName;
    Boolean IsPublic;
}

// Serialize
declare K_Config Config;
Config.MaxPlayers = 64;
Config.ServerName = "My Server";
Config.IsPublic = True;
declare Text Json = Config.tojson();
// Json == '{"MaxPlayers":64,"ServerName":"My Server","IsPublic":true}'

// Deserialize
declare K_Config Loaded;
Loaded.fromjson(Json);
```

### 16.3 XML Parsing

Via the `CParsingManager` (`Xml` global):

```maniascript
declare CXmlDocument Doc = Xml.Create(XmlText);
declare CXmlNode Root = Doc.Root;
// Traverse nodes...
Xml.Destroy(Doc);
```

---

## 17. Debug and Tuning

### 17.1 Debug Statements (4)

All confirmed as binary tokens:

| Keyword | Purpose | Example |
|---------|---------|---------|
| `log` | Output message to script console | `log("Player count: " ^ Players.count);` |
| `assert` | Debug assertion (halts in debug builds) | `assert(Player != Null);` |
| `dump` | Print variable value to debug output | `dump(MyVariable);` |
| `dumptype` | Print variable type information | `dumptype(MyVariable);` |

### 17.2 Tuning System (3)

Performance profiling keywords confirmed in binary:

| Keyword | Purpose |
|---------|---------|
| `TUNING_START` | Begin a tuning/profiling block |
| `TUNING_END` | End a tuning block |
| `TUNING_MARK` | Mark a profiling checkpoint |

These insert profiling instrumentation into the script for performance measurement by the engine's profiling system (the same system that uses `"CScriptEngine::Run(%s)"` profiling tags).

---

## 18. Built-in API: Script Managers

The engine exposes subsystem functionality to ManiaScript through `*Script*` and `*ScriptHandler*` classes. From the binary class hierarchy:

### 18.1 Script Manager Classes

| Manager | Purpose | Key Methods/Properties |
|---------|---------|----------------------|
| `CInputScriptManager` | Input devices | Pad state, events |
| `CInputScriptPad` | Individual gamepad | Button states, axis values |
| `CInputScriptEvent` | Input events | Key presses, pad events |
| `CAudioScriptManager` | Audio playback | Create/destroy sounds |
| `CAudioScriptMusic` | Background music | Play, stop, volume |
| `CAudioScriptSound` | Sound effects | 3D positioned audio |
| `CGamePlaygroundScript` | Gameplay API | Player management, scores |
| `CGamePlaygroundClientScriptAPI` | Client gameplay | Local player state |
| `CGameEditorPluginAPI` | Editor plugins | Block/item manipulation |
| `CGameEditorPluginMap` | Map editor plugin | Map modification |
| `CGameManialinkScriptHandler` | ManiaLink handler | Page events, UI control |
| `CGameGhostMgrScript` | Ghost management | Record/replay ghosts |
| `CGameGhostScript` | Ghost instance | Ghost data access |
| `CGameScriptEntity` | Script entity | Positioned game object |
| `CGameScriptPlayer` | Script player | Player gameplay state |
| `CGameScriptVehicle` | Script vehicle | Vehicle control |
| `CGameDataFileManagerScript` | File management | Read/write game data |
| `CXmlScriptParsingManager` | XML/JSON parsing | Document creation/destruction |

### 18.2 Script Handler Architecture

Script handlers bridge ManiaLink layers to the game logic:

```
CGameManialinkScriptHandler           -- Mutable script handler
CGameManialinkScriptHandler_ReadOnly  -- Read-only variant
CGameManialinkNavigationScriptHandler -- Navigation-specific handler
CGameEditorPluginLayerScriptHandler   -- Editor plugin layer
CGameCtnEditorMapTypeScriptHandler    -- Map type handler
CGameCtnEditorPluginScriptHandler     -- CTN plugin handler
CGameScriptHandlerBrowser             -- Browser handler
CGameScriptHandlerPlaygroundInterface -- Playground UI handler
CGameScriptHandlerPlaygroundInterface_ReadOnly -- Read-only playground handler
```

### 18.3 HTTP API

```maniascript
// Create request
declare CHttpRequest Req = Http.CreateGet("https://api.example.com/data");

// Wait for completion
wait(Req.IsCompleted);

// Read response
if (Req.StatusCode == 200) {
    declare Text Body = Req.Result;
    // Parse JSON...
}

// Clean up
Http.Destroy(Req);
```

Available methods: `CreateGet()`, `CreatePost()`, `CreatePut()`, `CreateDelete()`, `CreatePatch()`.

---

## 19. Game Mode Scripting

### 19.1 Script Location

Game mode scripts are located at:
```
Scripts/Modes/TrackMania/<ModeName>.Script.txt
```

### 19.2 Base Mode Framework

TM2020 game modes extend Nadeo's base framework using `#Extends`:

```maniascript
#Extends "Modes/TrackMania/Base/TrackmaniaBase.Script.txt"
```

The base script provides a `main()` function with a structured lifecycle of **labels** that child scripts inject code into.

### 19.3 Lifecycle Labels

The game mode lifecycle follows this hierarchy:

```
Server -> Match -> Map -> Round -> Turn -> PlayLoop
```

Each level has Init/Start/End labels:

| Label | Timing | Purpose |
|-------|--------|---------|
| `***Yield***` | Every tick | Called every frame |
| `***Settings***` | Load time | Process settings |
| `***LoadLibraries***` | Load time | Initialize libraries |
| `***InitServer***` | Server start | One-time server setup |
| `***StartServer***` | Server start | Server ready |
| `***InitMatch***` | Match start | Per-match initialization |
| `***StartMatch***` | Match start | Match begins |
| `***InitMap***` | Map load | Per-map initialization |
| `***StartMap***` | Map load | Map begins |
| `***InitRound***` | Round start | Per-round initialization |
| `***StartRound***` | Round start | Round begins |
| `***InitTurn***` | Turn start | Per-turn initialization |
| `***StartTurn***` | Turn start | Turn begins |
| `***PlayLoop***` | During play | Main gameplay tick |
| `***EndTurn***` | Turn end | Turn cleanup |
| `***EndRound***` | Round end | Round cleanup |
| `***EndMap***` | Map unload | Map cleanup |
| `***EndMatch***` | Match end | Match cleanup |
| `***EndServer***` | Server stop | Server cleanup |

Labels are prefixed by context: `Match_StartMap` vs `Lobby_StartMap` depending on matchmaking status.

### 19.4 Built-in Nadeo Game Modes

Available base modes for `#Extends`:

| Mode | Description |
|------|-------------|
| `TM_TimeAttack_Online` | Time attack (default) |
| `TM_Rounds_Online` | Rounds-based scoring |
| `TM_Cup_Online` | Cup elimination |
| `TM_Champion_Online` | Champion mode |
| `TM_Knockout_Online` | Knockout elimination |
| `TM_Laps_Online` | Lap-based racing |
| `TM_Teams_Online` | Team-based racing |

### 19.5 Player Management

```maniascript
// Spawn a player
declare CSmPlayer Player <=> Players[0];
SpawnPlayer(Player, 0, -1, MapLandmarks_PlayerSpawn[0].PlayerSpawn, Now + 1000);

// Access player state
log(Player.Login);
log(Player.Score.Points);
log(Player.SpawnStatus);  // CSmPlayer::ESpawnStatus::Spawned

// Unspawn
UnspawnPlayer(Player);
```

### 19.6 Score Management

```maniascript
// Set points
Player.Score.Points = 100;

// Set race time
Player.Score.BestRace.Time = RaceTime;

// Custom score columns
Scores_SetSortCriteria("BestRace");
```

### 19.7 UI Layer Management

```maniascript
// Create a ManiaLink UI layer
declare CUILayer Layer = UIManager.UILayerCreate();
Layer.ManialinkPage = """
<manialink version="3">
    <label id="info" text="Hello!" pos="0 80" halign="center"/>
    <script><!--
        main() {
            while (True) {
                yield;
            }
        }
    --></script>
</manialink>
""";

// Attach to all players
UIManager.UIAll.UILayers.add(Layer);

// Or attach to specific player
declare CUIConfig PlayerUI = UIManager.GetUI(Player);
PlayerUI.UILayers.add(Layer);
```

### 19.8 Multiplayer Determinism

In multiplayer, game mode scripts at state 0x1032 execute via `virtual (*param_1 + 0x370)` for network-synchronized script execution. Scripts must execute deterministically across all clients to maintain synchronization.

---

## 20. ManiaLink Scripting

### 20.1 ManiaLink XML Structure

ManiaLink is an XML-based UI description language. Scripts are embedded within `<script>` tags:

```xml
<manialink version="3">
    <quad id="myButton" pos="0 0" size="30 8"
          bgcolor="09F" scriptevents="1"/>
    <label id="myLabel" pos="0 -10" text="Click the button"/>
    <script><!--
        main() {
            declare MyLabel <=> (Page.GetFirstChild("myLabel") as CMlLabel);

            while (True) {
                foreach (Event in PendingEvents) {
                    if (Event.Type == CMlScriptEvent::Type::MouseClick) {
                        if (Event.ControlId == "myButton") {
                            MyLabel.Value = "Button clicked!";
                        }
                    }
                }
                yield;
            }
        }
    --></script>
</manialink>
```

### 20.2 Element Access

```maniascript
// Get element by ID (returns CMlControl, must cast)
declare CMlLabel Label <=> (Page.GetFirstChild("label_id") as CMlLabel);
declare CMlQuad Quad <=> (Page.GetFirstChild("quad_id") as CMlQuad);
declare CMlEntry Entry <=> (Page.GetFirstChild("entry_id") as CMlEntry);
declare CMlGauge Gauge <=> (Page.GetFirstChild("gauge_id") as CMlGauge);

// Manipulate properties
Label.Value = "New text";
Label.TextColor = <1.0, 0.0, 0.0>;  // Red
Label.Opacity = 0.5;

Quad.ImageUrl = "file://Media/Images/myimage.dds";
Quad.Colorize = <0.0, 1.0, 0.0>;  // Green tint
Quad.Opacity = 0.8;

Entry.Value;  // Read text input
Gauge.Ratio = 0.75;  // 75% filled
```

### 20.3 UI Control Types

From the official ManiaScript reference:

| Class | Element | Key Properties |
|-------|---------|---------------|
| `CMlLabel` | `<label>` | `Value`, `TextColor`, `TextSizeReal`, `Opacity`, `MaxLine`, `AutoNewLine` |
| `CMlQuad` | `<quad>` | `ImageUrl`, `Colorize`, `BgColor`, `Opacity`, `KeepRatio`, `Blend` |
| `CMlEntry` | `<entry>` | `Value`, `TextFormat`, `MaxLine`, `StartEdition()` |
| `CMlTextEdit` | `<textedit>` | `Value`, `ShowLineNumbers`, `LineSpacing` |
| `CMlGauge` | `<gauge>` | `Ratio`, `GradingRatio`, `Clan`, `Color` |
| `CMlGraph` | `<graph>` | `CoordsMin`, `CoordsMax`, `AddCurve()`, `Curves[]` |
| `CMlMinimap` | `<minimap>` | `WorldPosition`, `MapPosition`, `ZoomFactor` |
| `CMlMediaPlayer` | `<video>` | `Url`, `Play()`, `Stop()`, `Volume`, `IsLooping` |
| `CMlFrame` | `<frame>` | Container for other elements |

### 20.4 Visibility and Interaction

```maniascript
// Show/hide elements
Label.Show();
Label.Hide();
Label.Visible = True;

// Position and size
Label.RelativePosition_V3 = <10.0, -20.0, 0.0>;
Label.Size = <50.0, 10.0>;

// Interaction attributes (in XML)
// scriptevents="1" -- Required for mouse events
// focusareacolor1/2 -- Hover colors
```

### 20.5 Page Actions

```maniascript
// Trigger a page action (navigates to URL or triggers callback)
TriggerPageAction("MyAction");

// Open external link
OpenLink("https://trackmania.com", CMlScript::LinkType::ExternalBrowser);
```

### 20.6 Menu Navigation (Gamepad)

```maniascript
EnableMenuNavigation(True, True, BackButton, 0);
// Parameters: EnableInputs, WithAutoFocus, AutoBackControl, InputPriority
```

---

## 21. Map Editor Plugin Scripting

### 21.1 Context

```maniascript
#RequireContext CMapEditorPlugin
```

### 21.2 Available Properties

| Property | Type | Description |
|----------|------|-------------|
| `Map` | `CMap` | Current map being edited |
| `MapName` | `Text` | Map filename |
| `PendingEvents` | `CMapEditorPluginEvent[]` | Editor events |
| `PlaceMode` | `EPlaceMode` | Current placement mode |
| `EditMode` | `EEditMode` | Current edit mode |
| `IsEditorReadyForRequest` | `Boolean` | Can accept placement commands |

### 21.3 Place Modes

```
Unknown, Terraform, Block, Macroblock, Skin, CopyPaste,
Test, Plugin, CustomSelection, OffZone, BlockProperty,
Path, GhostBlock, Item, Light
```

### 21.4 Block Operations

```maniascript
// Test if a block can be placed
declare Boolean CanPlace = CanPlaceBlock(BlockModel, Coord, Dir);

// Place a block
PlaceBlock(BlockModel, Coord, Dir);

// Remove a block
RemoveBlock(Coord);

// Undo/Redo
Undo();
Redo();
```

### 21.5 Shadow Computation

```maniascript
ComputeShadows(CMapEditorPlugin::ShadowsQuality::High);
```

Quality levels: `NotComputed`, `VeryFast`, `Fast`, `Default`, `High`, `Ultra`.

### 21.6 Testing

```maniascript
TestMapFromStart();
TestMapFromCoord(<10, 5, 10>, CMapEditorPlugin::CardinalDirections::North);
TestMapWithMode("TrackMania/TM_TimeAttack_Online");
```

---

## 22. Standard Libraries

ManiaScript includes standard libraries imported via `#Include`:

### 22.1 MathLib

```maniascript
#Include "MathLib" as MathLib
```

| Function | Description |
|----------|-------------|
| `MathLib::Abs(Real)` | Absolute value |
| `MathLib::Sin(Real)` | Sine (radians) |
| `MathLib::Cos(Real)` | Cosine (radians) |
| `MathLib::Tan(Real)` | Tangent (radians) |
| `MathLib::Atan2(Real, Real)` | Two-argument arctangent |
| `MathLib::Sqrt(Real)` | Square root |
| `MathLib::Pow(Real, Real)` | Power |
| `MathLib::Min(Real, Real)` | Minimum |
| `MathLib::Max(Real, Real)` | Maximum |
| `MathLib::Clamp(Real, Min, Max)` | Clamp to range |
| `MathLib::Rand(Min, Max)` | Random integer in range |
| `MathLib::NearestInteger(Real)` | Round to nearest |
| `MathLib::FloorInteger(Real)` | Floor |
| `MathLib::CeilingInteger(Real)` | Ceiling |
| `MathLib::Distance(Vec3, Vec3)` | 3D distance |
| `MathLib::DotProduct(Vec3, Vec3)` | Dot product |
| `MathLib::CrossProduct(Vec3, Vec3)` | Cross product |
| `MathLib::PI` | Pi constant |

### 22.2 TextLib

```maniascript
#Include "TextLib" as TextLib
```

| Function | Description |
|----------|-------------|
| `TextLib::SubText(Text, Start, Length)` | Substring |
| `TextLib::Length(Text)` | String length |
| `TextLib::Find(Text, Pattern, Case, Start)` | Find substring |
| `TextLib::Replace(Text, Old, New)` | Replace occurrences |
| `TextLib::Split(Separator, Text)` | Split into array |
| `TextLib::Join(Separator, Array)` | Join array into text |
| `TextLib::ToUpperCase(Text)` | Convert to uppercase |
| `TextLib::ToLowerCase(Text)` | Convert to lowercase |
| `TextLib::Trim(Text)` | Remove leading/trailing whitespace |
| `TextLib::ToInteger(Text)` | Parse integer |
| `TextLib::ToReal(Text)` | Parse real |
| `TextLib::ToText(Value)` | Convert to text |
| `TextLib::ToColor(Text)` | Parse color string |
| `TextLib::FormatInteger(Int, Digits)` | Format with leading zeros |
| `TextLib::TimeToText(Integer)` | Convert ms to "M:SS.mmm" |
| `TextLib::RegexMatch(Pattern, Text, Flags)` | Regex match |
| `TextLib::RegexReplace(Pattern, Text, Replace, Flags)` | Regex replace |
| `TextLib::URLEncode(Text)` | URL-encode |

### 22.3 AnimLib

```maniascript
#Include "AnimLib" as AnimLib
```

Animation easing functions for UI animations.

### 22.4 Nadeo Libraries

Nadeo provides additional libraries for game mode development:

```maniascript
#Include "Libs/Nadeo/Message.Script.txt" as Message
#Include "Libs/Nadeo/Layers.Script.txt" as Layers
#Include "Libs/Nadeo/Scores.Script.txt" as Scores
#Include "Libs/Nadeo/Interface.Script.txt" as Interface
```

---

## 23. Lexer and Token Types

From binary string search at the ManiaScript token table in Trackmania.exe.

### 23.1 Lexer Token Categories

| Token Category | Description | Binary Evidence |
|----------------|-------------|-----------------|
| `WHITESPACE` | Spaces, tabs, newlines | Skipped by parser |
| `STRING` | Quoted string literal `"..."` | Stored as Text |
| `STRING_AND_CONCAT` | String ending with concatenation | `"text" ^` |
| `NATURAL` | Integer literal | `42`, `0xFF` |
| `FLOAT` | Floating-point literal | `3.14`, `2.` |
| `IDENT` | Identifier | Variable/function names |
| `COMMENT` | Comment block | `//` single-line, `/* */` multi-line |
| `STRING_OPERATOR` | String operation token | Operators on Text |
| `CONCAT_AND_STRING` | Concatenation followed by string | `^ "text"` |
| `LOCAL_STRUCT` | Local struct declaration | `#Struct` instances |

### 23.2 Keyword Tokens

All confirmed in binary:

**Coroutine**: `SLEEP`, `YIELD`, `WAIT`, `MEANWHILE`

**Debug**: `ASSERT`, `DUMP`, `DUMPTYPE`, `LOG`

**Tuning**: `TUNING_START`, `TUNING_END`, `TUNING_MARK`

**Type tokens**: `MANIASCRIPT_TYPE_VOID`, `MANIASCRIPT_TYPE_BOOLEAN`, `MANIASCRIPT_TYPE_INTEGER`, `MANIASCRIPT_TYPE_REAL`, `MANIASCRIPT_TYPE_TEXT`, `MANIASCRIPT_TYPE_VEC2`, `MANIASCRIPT_TYPE_VEC3`, `MANIASCRIPT_TYPE_INT2`, `MANIASCRIPT_TYPE_INT3`, `MANIASCRIPT_TYPE_ISO4`, `MANIASCRIPT_TYPE_IDENT`, `MANIASCRIPT_TYPE_CLASS`

**Control flow** (from grammar): `if`, `else`, `while`, `for`, `foreach`, `switch`, `switchtype`, `case`, `default`, `break`, `continue`, `return`

**Declarations**: `declare`, `persistent`, `netread`, `netwrite`, `metadata`

**Operators**: `as`, `is` (type check)

---

## 24. Script Engine Internals (from RE)

### 24.1 CScriptEngine::Run (0x140874270)

Decompiled from `Trackmania.exe`. Size: 316 bytes.

```c
void CScriptEngine__Run(longlong engine, longlong context, undefined4 mode) {
    // 1. Link context to engine
    *(longlong *)(engine + 0x60) = context;

    // 2. Get program/bytecode
    longlong program = *(longlong *)(context + 0x10);

    // 3. Reset execution timer
    FUN_1402d3df0(engine, 1);

    // 4. Build dynamic profiling tag: "CScriptEngine::Run(<scriptname>)"
    if (profiling_enabled && *(program + 0xF8) == 0 && *(program + 0xF4) != 0) {
        char* name = read_sso_string(program + 0xE8);
        *(program + 0xF8) = format("CScriptEngine::Run(%s)", name);
    }

    // 5. Begin profiling
    char* tag = *(program + 0xF8) ?: "CScriptEngine::Run";
    FUN_1401175b0(local_buf, tag, 0, 0);

    // 6. Copy debug mode from engine to context
    *(context + 0x30) = *(engine + 0x20);

    // 7. Set execution mode (0 = debug/step, 1 = normal)
    if (debug_mode || *(context + 0x2C)) {
        *(context + 0x5C) += 1;   // Increment debug step counter
        *(context + 0x58) = 0;    // Debug mode
    } else {
        *(context + 0x58) = 1;    // Normal execution
    }

    // 8. Set entry point
    *(context + 0x08) = mode;
    *(context + 0x0C) = FUN_14018cb30(mode);  // Resolve entry address

    // 9. Clear output buffer
    FUN_14010be60(context + 0x100);

    // 10. Record timestamp from global tick counter
    *(context + 0xC4) = DAT_141ffad50;

    // 11. EXECUTE: Call bytecode interpreter
    FUN_1408d1ea0(program, context);

    // 12. Unlink context from engine
    *(engine + 0x60) = 0;

    // 13. Error check: -1 means execution error
    if (return_value == -1) {
        *(*(context + 200) + 400) = 2;  // Error code 2
    }

    // 14. End profiling
    FUN_1401176a0(local_buf, local_18);
}
```

### 24.2 Key Memory Layout

**CScriptEngine offsets**:
| Offset | Type | Description |
|--------|------|-------------|
| `+0x20` | int | Debug mode flag |
| `+0x60` | ptr | Current execution context (cleared after run) |

**Script context offsets**:
| Offset | Type | Description |
|--------|------|-------------|
| `+0x08` | int | Entry point / function ID |
| `+0x0C` | int | Resolved entry address |
| `+0x10` | ptr | Program/bytecode pointer |
| `+0x2C` | int | Force-debug flag |
| `+0x30` | int | Debug mode copy (from engine) |
| `+0x58` | int | Execution mode (1=normal, 0=debug) |
| `+0x5C` | int | Debug step counter |
| `+0xC4` | int | Timestamp at execution start |
| `+0xC8` | ptr | Error context object |
| `+0xE8` | str | Script name (SSO string) |
| `+0xF4` | int | Script name length |
| `+0xF8` | ptr | Cached profiling tag |
| `+0x100` | buf | Output buffer |

**Program offsets** (bytecode container):
| Offset | Type | Description |
|--------|------|-------------|
| `+0xE8` | str | Script filename (SSO string) |
| `+0xF3` | byte | SSO flag (0=inline, nonzero=heap) |
| `+0xF4` | int | Filename length |
| `+0xF8` | ptr | Cached profiling tag string |

### 24.3 Bytecode Interpreter

The actual bytecode interpreter is at `FUN_1408d1ea0`. Its internal structure is **UNKNOWN** -- the opcode format, instruction encoding, and stack layout have not been reverse-engineered. This is identified as one of the highest-priority unknowns in the RE documentation.

### 24.4 Script-to-Engine Binding

ManiaScript calls engine functions through a binding layer protected by MSVC Control Flow Guard (`_guard_check_icall`). This validates function pointer targets before indirect calls, including script-to-engine bindings.

### 24.5 Engine Singleton

`CScriptEngine` is one of 12 engine singletons:

```
CMwEngine -> CMwEngineMain, CGameEngine, CPlugEngine, CSceneEngine,
             CVisionEngine, CNetEngine, CInputEngine, CSystemEngine,
             CScriptEngine, CControlEngine, CAudioSourceEngine
```

The engine has two confirmed methods in the binary: `Compilation` and `Run`.

---

## 25. Browser Recreation: Interpreter/Transpiler Approach

### 25.1 Overview

For a browser-based recreation of Trackmania, ManiaScript requires either:
1. **JavaScript interpreter**: Parse ManiaScript source, build AST, interpret in JS
2. **JavaScript transpiler**: Parse ManiaScript source, compile to equivalent JS

### 25.2 Lexer Specification

The complete lexer token set is documented in [Section 23](#23-lexer-and-token-types). A ManiaScript lexer needs to handle:
- C-style comments (`//`, `/* */`)
- String literals with escape sequences and triple-quoting
- Numeric literals (integer and float with mandatory trailing dot)
- Vector literals (`<1.0, 2.0>`)
- All operators including `<=>` (alias), `^` (concat), `::` (enum scope)
- Directive tokens (`#RequireContext`, `#Setting`, etc.)
- The 40+ keyword tokens

### 25.3 Type System Mapping

| ManiaScript | JavaScript Equivalent |
|-------------|----------------------|
| `Boolean` | `boolean` |
| `Integer` | `number` (with integer constraint) |
| `Real` | `number` |
| `Text` | `string` |
| `Vec2` | `Float32Array(2)` or `{x, y}` |
| `Vec3` | `Float32Array(3)` or `{x, y, z}` |
| `Int2` | `Int32Array(2)` or `{x, y}` |
| `Int3` | `Int32Array(3)` or `{x, y, z}` |
| `Iso4` | `Float32Array(12)` or `Matrix3x4` class |
| `Ident` | `number` (uint32 interned ID) |
| `Class` | JS object with prototype chain |
| `Array` | `Array` with type enforcement |
| `Map` | `Map` with type enforcement |

### 25.4 Coroutine Implementation

The `yield`/`sleep`/`wait`/`meanwhile` coroutine model maps to several JavaScript approaches:

**Option A: Generator functions** (recommended)
```javascript
function* scriptMain(ctx) {
    while (true) {
        for (const event of ctx.PendingEvents) {
            // Process events
        }
        yield; // Returns control to engine, resumed next frame
    }
}
```

**Option B: Async/await with frame promises**
```javascript
async function scriptMain(ctx) {
    while (true) {
        for (const event of ctx.PendingEvents) {
            // Process events
        }
        await nextFrame(); // Promise resolved on next frame
    }
}
```

`sleep(ms)` maps to yielding until `performance.now()` exceeds the target time.
`wait(condition)` maps to yielding until a condition closure returns true.
`meanwhile` requires spawning a secondary generator/coroutine.

### 25.5 Collection Operations

All 17 dot operations need custom Array/Map wrapper classes:

```javascript
class MsArray {
    add(elem) { this._data.push(elem); }
    addfirst(elem) { this._data.unshift(elem); }
    remove(elem) { /* remove first occurrence */ }
    removekey(key) { this._data.splice(key, 1); }
    get count() { return this._data.length; }
    clear() { this._data.length = 0; }
    sort() { this._data.sort((a, b) => a - b); }
    sortrev() { this._data.sort((a, b) => b - a); }
    existskey(key) { return key >= 0 && key < this._data.length; }
    existselem(elem) { return this._data.includes(elem); }
    containsonly(other) { return this._data.every(e => other.existselem(e)); }
    containsoneof(other) { return this._data.some(e => other.existselem(e)); }
    keyof(elem) { return this._data.indexOf(elem); }
    slice(start, count) { return this._data.slice(start, start + count); }
    tojson() { return JSON.stringify(this._data); }
    fromjson(str) { this._data = JSON.parse(str); }
}
```

### 25.6 Engine API Binding

Each script context class needs a JavaScript counterpart that exposes the same properties and methods. The 700+ ManiaScript API classes require stubs or implementations:

```javascript
class CSmMode {
    get Players() { return this._players; }
    get Map() { return this._map; }
    get Now() { return this._engine.tickMs; }

    SpawnPlayer(player, clan, raceStartTime, spawn, startTime) { ... }
    UnspawnPlayer(player) { ... }
}
```

### 25.7 Network Variable Simulation

For browser recreation, `netread`/`netwrite` can be simulated using:
- SharedArrayBuffer for multi-worker scenarios
- Simple object properties for single-thread
- WebSocket messages for true client-server separation

### 25.8 Complexity Estimate

| Component | Estimated Effort | Priority |
|-----------|-----------------|----------|
| Lexer | Medium (40+ tokens) | High |
| Parser | High (full grammar) | High |
| Type system | Medium (12 types + collections) | High |
| Coroutine runtime | Medium (generator-based) | High |
| Basic API stubs | Very High (700+ classes) | Medium |
| ManiaLink renderer | Very High (HTML/CSS mapping) | Medium |
| Game mode framework | High (lifecycle labels) | Low (custom modes) |

---

## Appendix A: Complete Script Class Inventory

From `class_hierarchy.json` (2,027 total classes), script-relevant classes:

### Core Script Engine
- `CScriptEngine` (methods: `Compilation`, `Run`)
- `CScriptBaseEvent`, `CScriptBaseConstEvent`
- `CScriptEvent`
- `CScriptInterfacableValue`
- `CScriptPoison`
- `CScriptSetting`
- `CScriptTraitsMetadata`, `CScriptTraitsPersistent`

### Game Mode
- `CSmMode` (methods: `EActionInput`, `SpawnBotPlayer`, `SpawnPlayer`)
- `CSmPlayer` (methods: `ESpawnStatus`)
- `CSmPlayerDriver` (methods: `ESmDriverPathState`)
- `CSmArena` (methods: `SimulationStep`, `RaceStates_BeforeScript`, etc.)
- `CSmArenaRules` (methods: `CreateAndDestroyEntities`, `UpdateEvents`, `UpdateTimed`)
- `CMapType`

### Script Handlers
- `CGameManialinkScriptHandler`
- `CGameManialinkScriptHandler_ReadOnly`
- `CGameManialinkNavigationScriptHandler`
- `CGameEditorPluginLayerScriptHandler`
- `CGameCtnEditorMapTypeScriptHandler`
- `CGameCtnEditorPluginScriptHandler`
- `CGameScriptHandlerBrowser`
- `CGameScriptHandlerPlaygroundInterface`
- `CGameScriptHandlerPlaygroundInterface_ReadOnly`

### Script Managers
- `CInputScriptManager`, `CInputScriptPad`, `CInputScriptEvent`
- `CAudioScriptManager`, `CAudioScriptMusic`, `CAudioScriptSound`
- `CGamePlaygroundScript`, `CGamePlaygroundClientScriptAPI`
- `CGameGhostMgrScript`, `CGameGhostScript`
- `CGameScriptEntity`, `CGameScriptPlayer`, `CGameScriptVehicle`
- `CGameDataFileManagerScript`
- `CXmlScriptParsingManager`

---

## Appendix B: Community Reference Links

| Resource | URL | Scope |
|----------|-----|-------|
| ManiaScript Reference (BigBang1112) | https://github.com/BigBang1112/maniascript-reference | Auto-generated Doxygen for TM2020/MP/Turbo |
| ManiaScript Reference (boss-bravo) | https://maniascript.boss-bravo.fr/ | TM2020 class reference |
| ManiaScript Book | https://maniaplanet-community.gitbook.io/maniascript | Community tutorial/guide |
| Official ManiaScript Docs | https://doc.maniaplanet.com/maniascript | Nadeo official docs |
| Syntax Basics (GitHub) | https://github.com/maniaplanet/documentation/blob/master/08.maniascript/01.syntax-basics/docs.md | Language syntax reference |
| ManiaScript in ManiaLink | https://doc.maniaplanet.com/maniascript/maniascript-in-manialink | UI scripting guide |
| Game Modes Wiki | https://wiki.trackmania.io/en/ManiaScript/Advanced/Gamemode | TM2020 game mode docs |
| Official Maniascript Reference | https://maniaplanet.github.io/maniascript-reference/ | ManiaPlanet class reference |

---

## Appendix C: Cross-Reference to RE Documentation

| Topic | RE Source | Section in This Document |
|-------|-----------|--------------------------|
| Token types (40+) | doc 15 Section 10 | Sections 2, 8, 23 |
| Script engine runtime | doc 12 Sections 5, 15 | Section 24 |
| CScriptEngine::Run decompilation | `decompiled/architecture/CScriptEngine__Run.c` | Section 24.1 |
| Script class hierarchy | `class_hierarchy.json` | Appendix A |
| Subsystem class map | doc 13 Sections 13.4, 14.3, 18 | Sections 11, 18 |
| Community knowledge | doc 29 Section 5 | Sections 11-22 |
| Frame loop integration | doc 12 Section 6 | Section 9.5 |
| Network state machine | doc 12 Section 16 | Section 19.8 |

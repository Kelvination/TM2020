# Trackmania 2020 Subsystem Class Map

**Source**: `class_hierarchy.json` (5,886 lines), `02-class-hierarchy.md`
**Total Nadeo classes**: 2,027
**Total MSVC RTTI classes**: 55 (not covered here)
**Date**: 2026-03-27

This document maps every one of the 2,027 Nadeo engine classes to exactly one subsystem, with detailed analysis of 12 major subsystems and their inter-relationships.

---

## Table of Contents

1. [Audio Subsystem](#1-audio-subsystem) (30 classes)
2. [Input Subsystem](#2-input-subsystem) (17 classes)
3. [Camera System](#3-camera-system) (22 classes)
4. [UI/Control System](#4-uicontrol-system) (70 classes)
5. [Editor System](#5-editor-system) (71 classes)
6. [Replay/Ghost System](#6-replayghost-system) (14 classes)
7. [Map/Block System](#7-mapblock-system) (60 classes)
8. [Vehicle/Car System](#8-vehiclecar-system) (27 classes)
9. [Web Services](#9-web-services) (713 classes)
10. [Scene Graph](#10-scene-graph) (93 classes)
11. [MediaTracker Blocks](#11-mediatracker-blocks) (74 classes)
12. [Plugin/Mod System](#12-plugmod-system) (392 classes)
13. [Remaining Subsystems](#13-remaining-subsystems) (444 classes)
14. [Cross-Cutting Concerns](#14-cross-cutting-concerns)
15. [Completeness Verification](#15-completeness-verification)
16. [Content Creator Guide](#16-content-creator-guide) -- Item pipeline, material assignment, UV requirements
17. [Complete Material Reference (All 208)](#17-complete-material-reference-all-208-materials) -- Every material with SurfaceId, UV layers, and use
18. [ManiaScript Language Reference](#18-maniascript-language-reference) -- Types, directives, coroutines, collections
19. [Editor Capabilities Matrix](#19-editor-capabilities-matrix) -- All 18 editors and what they do
20. [MediaTracker Block Type Catalog](#20-complete-mediatracker-block-type-catalog) -- All 65+ block types
21. [Block Naming Convention Decoder](#21-block-naming-convention-decoder) -- Coordinates, rotation, clips, waypoints
22. [Audio System for Custom Content](#22-audio-system-for-custom-content) -- Sound types, formats, how they attach
23. [Skins and Customization System](#23-skins-and-customization-system) -- Skins, badges, vehicle customization

---

## 1. Audio Subsystem

**Class count**: 30
**Prefixes**: `CAudio*`, `CPlug*Sound*`, `CPlug*Audio*`, `CPlug*Music*`, `COal*`

### 1.1 Class Hierarchy

```
CMwNod
  +-- CAudioManager                       -- Top-level audio orchestrator
  +-- CAudioPort                          -- Audio output port abstraction
  |     +-- CAudioPortNull                -- Null/silent audio port
  +-- COalAudioPort                       -- OpenAL audio port implementation
  +-- CAudioBufferKeeper                  -- Audio buffer lifecycle management
  +-- CAudioListener                      -- 3D audio listener position/orientation
  +-- CAudioSettings                      -- Audio configuration (volume, quality)
  +-- CAudioScriptManager                 -- ManiaScript audio API
  +-- CAudioScriptMusic                   -- Script-accessible music control
  +-- CAudioScriptSound                   -- Script-accessible sound control
  +-- CAudioSoundImplem                   -- Sound implementation (platform-specific)
  +-- CAudioSource                        -- Base audio source
  |     +-- CAudioSourceEngine            -- Engine/motor sounds
  |     +-- CAudioSourceGauge             -- Gauge/meter UI sounds
  |     +-- CAudioSourceMood              -- Ambient mood sounds
  |     +-- CAudioSourceMulti             -- Multi-layered composite sounds
  |     +-- CAudioSourceMusic             -- Music playback source
  |     +-- CAudioSourceSurface           -- Surface-contact sounds (tires)
  +-- CAudioZone                          -- Spatial audio zone definition
  +-- CAudioZoneSource                    -- Sound source within a zone
  +-- CPlugAudio                          -- Audio resource base
  +-- CPlugAudioBalance                   -- Audio channel balance/panning
  +-- CPlugAudioEnvironment               -- Audio environment (reverb, etc.)
  +-- CPlugSound                          -- Sound resource base
  +-- CPlugSoundComponent                 -- Sound component within a composite
  +-- CPlugSoundEngine                    -- Engine sound resource (v1)
  +-- CPlugSoundEngine2                   -- Engine sound resource (v2)
  +-- CPlugSoundGauge                     -- Gauge sound resource
  +-- CPlugSoundMood                      -- Mood/ambient sound resource
  +-- CPlugSoundMulti                     -- Multi-layered sound resource
  +-- CPlugSoundSurface                   -- Surface-dependent sound resource
  +-- CPlugSoundVideo                     -- Video-associated sound
  +-- CPlugLocatedSound                   -- 3D-positioned sound resource
  +-- CPlugMusic                          -- Music track resource
  +-- CPlugMusicType                      -- Music genre/type classification
  +-- CPlugFileAudioMotors                -- Motor sound file format
  +-- CPlugFileOggVorbis                  -- OGG Vorbis audio file handler
  +-- CPlugFileSnd                        -- Generic sound file handler
  +-- CPlugFileSndGen                     -- Generated/procedural sound file
  +-- CPlugFileWav                        -- WAV audio file handler
  +-- CGameCtnDecorationAudio             -- Map decoration audio settings
  +-- CGameAudioSettingsWrapper           -- Script-accessible audio settings
```

### 1.2 Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CAudioPort` | `ApplySystemConfig`, `CaptureUpdate`, `PreloadResources` | Port lifecycle |
| `COalAudioPort` | `PushData` | OpenAL data submission |

### 1.3 Architecture

**Audio Engine Flow**:
1. `CAudioManager` orchestrates all audio
2. `CAudioPort` (or `COalAudioPort`) handles OS audio output
3. `CAudioSource*` types represent different sound categories
4. `CPlugSound*` types are loadable sound resources
5. `CAudioZone`/`CAudioZoneSource` handle spatial audio

**Sound Categories**:
- **Engine**: `CAudioSourceEngine` + `CPlugSoundEngine`/`CPlugSoundEngine2` -- vehicle motor sounds with RPM mapping
- **Surface**: `CAudioSourceSurface` + `CPlugSoundSurface` -- tire-on-surface sounds
- **Mood**: `CAudioSourceMood` + `CPlugSoundMood` -- ambient atmospheric loops
- **Music**: `CAudioSourceMusic` + `CPlugMusic` -- background music tracks
- **Gauge**: `CAudioSourceGauge` + `CPlugSoundGauge` -- speed/RPM gauge UI sounds
- **Multi**: `CAudioSourceMulti` + `CPlugSoundMulti` -- layered composite sounds

**Audio Formats**: WAV (`CPlugFileWav`), OGG Vorbis (`CPlugFileOggVorbis`), generic SND (`CPlugFileSnd`/`CPlugFileSndGen`), motor profiles (`CPlugFileAudioMotors`)

### 1.4 Browser Recreation Implications

For a browser recreation, the audio subsystem needs:
- Web Audio API for spatial audio (replacing OpenAL)
- Decoding pipeline for WAV and OGG
- Engine sound synthesis with RPM-based interpolation
- Zone-based ambient audio blending
- Surface-dependent tire sounds mapped to physics material

---

## 2. Input Subsystem

**Class count**: 17
**Prefixes**: `CInput*`

### 2.1 Class Hierarchy

```
CMwNod
  +-- CInputEngine                        -- Input system singleton
  +-- CInputManager                       -- Input state aggregation
  +-- CInputPort                          -- Input port abstraction
  |     +-- CInputPortDx8                 -- DirectInput 8 port
  |     +-- CInputPortNull                -- Null input port
  +-- CInputDevice                        -- Base input device
  |     +-- CInputDeviceDx8Keyboard       -- DirectInput keyboard
  |     +-- CInputDeviceDx8Mouse          -- DirectInput mouse
  |     +-- CInputDeviceDx8Pad            -- DirectInput gamepad
  |     +-- CInputDeviceMouse             -- Generic mouse device
  +-- CInputPad                           -- Gamepad/steering wheel abstraction
  +-- CInputEvent                         -- Raw input event
  +-- CInputReplay                        -- Input recording/playback for replays
  +-- CInputBindingsConfig                -- Key binding configuration
  +-- CInputScriptManager                 -- ManiaScript input API
  +-- CInputScriptEvent                   -- Script-accessible input event
  +-- CInputScriptPad                     -- Script-accessible pad state
  +-- CGameHapticDevice                   -- Force feedback / haptic device [CROSS-CUTTING]
```

### 2.2 Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CInputEngine` | `GetOrCreateInputPort` | Port creation |
| `CInputPort` | `Tick`, `Update_StartFrame`, `Update_EndFrame` | Per-frame input polling |

### 2.3 Architecture

**Input Event Flow**:
1. `CInputEngine` creates `CInputPort` instances (DirectInput 8 on Windows)
2. `CInputPort` polls `CInputDevice` objects each frame (`Tick`)
3. Raw events feed into `CInputManager`
4. `CInputBindingsConfig` maps raw inputs to game actions
5. `CInputScriptManager` exposes input to ManiaScript
6. `CInputReplay` can record/replay input sequences for ghost recording

**Device Types**:
- Keyboard: `CInputDeviceDx8Keyboard`
- Mouse: `CInputDeviceDx8Mouse` / `CInputDeviceMouse`
- Gamepad: `CInputDeviceDx8Pad` / `CInputPad`
- Haptic: `CGameHapticDevice` (force feedback for steering wheels)

### 2.4 Browser Recreation Implications

- Replace DirectInput with Gamepad API + keyboard/mouse events
- Input binding system maps well to a configurable binding table
- `CInputReplay` format is key for ghost data -- input-based deterministic replay
- Force feedback via Gamepad API haptic actuators (limited support)

---

## 3. Camera System

**Class count**: 22
**Prefixes**: `CGameControlCamera*`, `CPlugVehicleCamera*`, `CSceneLocationCamera`, `CMapEditorCamera`, `CGameCtnEdControlCam*`

### 3.1 Class Hierarchy

```
CMwNod
  +-- CGameControlCamera                  -- Base camera controller
  |     +-- CGameControlCameraEditorOrbital   -- Editor orbital camera
  |     +-- CGameControlCameraFirstPerson     -- First-person camera
  |     +-- CGameControlCameraFree            -- Free-look camera
  |     +-- CGameControlCameraHelico          -- Helicopter-style camera
  |     +-- CGameControlCameraHmdExternal     -- VR HMD external camera
  |     +-- CGameControlCameraOrbital3d       -- 3D orbital camera
  |     +-- CGameControlCameraTarget          -- Target-following camera
  |     +-- CGameControlCameraThirdPerson     -- Third-person chase camera
  |     +-- CGameControlCameraTrackManiaRace  -- TM race camera v1
  |     +-- CGameControlCameraTrackManiaRace2 -- TM race camera v2
  |     +-- CGameControlCameraTrackManiaRace3 -- TM race camera v3 (current)
  |     +-- CGameControlCameraVehicleInternal -- Interior cockpit camera
  +-- CGameControlCameraEffect            -- Camera post-effect base
  |     +-- CGameControlCameraEffectShake -- Camera shake effect
  +-- CPlugVehicleCameraRaceModel         -- Race camera tuning parameters (v1)
  +-- CPlugVehicleCameraRace2Model        -- Race camera tuning parameters (v2)
  +-- CPlugVehicleCameraRace3Model        -- Race camera tuning parameters (v3)
  +-- CPlugVehicleCameraInternalModel     -- Internal camera model
  +-- CPlugVehicleCameraHelicoModel       -- Helicopter camera model
  +-- CPlugVehicleCameraHmdExternalModel  -- VR external camera model
  +-- CPlugVehicleCamInternalVisOffset    -- Internal camera visual offset
  +-- CPlugCamControlModel                -- Generic camera control model
  +-- CPlugCamShakeModel                  -- Camera shake parameters
  +-- CSceneLocationCamera                -- Scene-space camera location
  +-- CMapEditorCamera                    -- Map editor camera (script API)
  +-- CGameCtnEdControlCam               -- Editor camera control base
  |     +-- CGameCtnEdControlCamCustom    -- Custom editor camera
  |     +-- CGameCtnEdControlCamPath      -- Path-based editor camera
  +-- CHmsCamera                          -- HMS (render) camera
```

### 3.2 Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CHmsCamera` | `EViewportRatio` | Viewport aspect ratio enum |
| `CGameCtnPlayground` | `UpdateCamsAll` | Per-frame camera update |

### 3.3 Camera Types

| Camera | Use Case | Key Behavior |
|--------|----------|--------------|
| `TrackManiaRace3` | Default race camera | Chase cam with spring physics, terrain avoidance |
| `VehicleInternal` | Cockpit view | Fixed to car interior |
| `Free` | Replay/spectator | 6DOF free movement |
| `Helico` | Helicopter view | Top-down with adjustable angle |
| `FirstPerson` | First person | Eye-level camera |
| `EditorOrbital` | Map editor | Orbit around cursor position |
| `HmdExternal` | VR mode | External VR tracking |

### 3.4 Browser Recreation Implications

- Three generations of race camera (`Race`, `Race2`, `Race3`) -- need the v3 parameters
- Camera models (`CPlugVehicleCameraRace3Model`) define spring stiffness, lag, terrain avoidance
- Camera shake system for impacts and rough terrain
- Editor camera is independent from gameplay camera

---

## 4. UI/Control System

**Class count**: 70
**Prefixes**: `CControl*`, `CGameManialink*`, `CGameControl*` (UI subset)

### 4.1 Native Controls (39 classes)

```
CMwNod
  +-- CControlBase                        -- Base UI control
  |     +-- CControlButton                -- Clickable button
  |     +-- CControlLabel                 -- Text label
  |     +-- CControlText                  -- Text display
  |     +-- CControlTextEdition           -- Text input field
  |     +-- CControlEntry                 -- Entry/input control
  |     +-- CControlEnum                  -- Dropdown/enum selector
  |     +-- CControlSlider                -- Slider control
  |     +-- CControlQuad                  -- Quad/image display
  |     +-- CControlGrid                  -- Grid layout
  |     +-- CControlGraph                 -- Graph/chart display
  |     +-- CControlListCard              -- Card list item
  |     +-- CControlListItem              -- List item
  |     +-- CControlPager                 -- Pagination control
  |     +-- CControlMediaPlayer           -- Video player
  |     +-- CControlMiniMap               -- Mini-map display
  |     +-- CControlColorChooser          -- Color picker v1
  |     +-- CControlColorChooser2         -- Color picker v2
  |     +-- CControlCamera                -- Camera preview
  |     +-- CControlScriptConsole         -- Script debug console
  |     +-- CControlScriptEditor          -- Script editor
  |     +-- CControlTimeLine2             -- Timeline control
  |     +-- CControlUiRange               -- Range control
  |     +-- CControlUrlLinks              -- URL link handler
  +-- CControlContainer                   -- Control grouping
  +-- CControlFrame                       -- Frame container
  |     +-- CControlFrameAnimated         -- Animated frame
  |     +-- CControlFrameStyled           -- Styled frame
  +-- CControlEffect                      -- UI effect base
  |     +-- CControlEffectCombined        -- Combined effects
  |     +-- CControlEffectMaster          -- Master effect controller
  |     +-- CControlEffectMotion          -- Motion effect
  |     +-- CControlEffectMoveFrame       -- Frame movement effect
  |     +-- CControlEffectSimi            -- Similarity transform effect
  +-- CControlLayout                      -- Layout manager
  +-- CControlStyle                       -- Individual control style
  +-- CControlStyleSheet                  -- Style collection
  +-- CControlSimi2                       -- 2D similarity transform
  +-- CControlEngine                      -- UI engine singleton
```

### 4.2 Manialink Controls (28 classes)

```
CMwNod
  +-- CGameManialinkControl               -- Base Manialink control (script API)
  |     +-- CGameManialinkArrow           -- Arrow/direction indicator
  |     +-- CGameManialinkCamera          -- Camera view in UI
  |     +-- CGameManialinkColorChooser    -- Color picker
  |     +-- CGameManialinkEntry           -- Text entry
  |     +-- CGameManialinkFileEntry       -- File chooser
  |     +-- CGameManialinkFrame           -- Frame container
  |     +-- CGameManialinkGauge           -- Gauge/progress bar
  |     +-- CGameManialinkGraph           -- Graph display
  |     +-- CGameManialinkLabel           -- Text label
  |     +-- CGameManialinkMediaPlayer     -- Video player
  |     +-- CGameManialinkMiniMap         -- Mini-map
  |     +-- CGameManialinkOldTable        -- Legacy table
  |     +-- CGameManialinkPlayerList      -- Player list
  |     +-- CGameManialinkQuad            -- Image/quad
  |     +-- CGameManialinkSlider          -- Slider
  |     +-- CGameManialinkTextEdit        -- Text editor
  |     +-- CGameManialinkTimeLine        -- Timeline
  +-- CGameManialinkGraphCurve            -- Graph curve data
  +-- CGameManialinkPage                  -- Page container
  +-- CGameManialinkManager               -- Manialink system manager
  +-- CGameManialinkBrowser               -- Manialink page browser
  +-- CGameManialinkAnimManager           -- UI animation manager
  +-- CGameManialinkStylesheet            -- Manialink CSS-like styles
  +-- CGameManialinkScriptEvent           -- UI script event
  +-- CGameManialinkScriptHandler         -- Script event handler
  +-- CGameManialinkScriptHandler_ReadOnly -- Read-only script handler
  +-- CGameManialinkNavigationScriptHandler -- Navigation script handler
  +-- CGameManialink3dMood                -- 3D scene mood in UI
  +-- CGameManialink3dStyle               -- 3D scene style in UI
  +-- CGameManialink3dWorld               -- 3D scene world in UI
```

### 4.3 Game Control Cards (17 classes)

```
CGameControlCard                          -- Base card widget
  +-- CGameControlCardBuddy              -- Friend/buddy card
  +-- CGameControlCardCtnArticle         -- Article info card
  +-- CGameControlCardCtnChallengeInfo   -- Map info card
  +-- CGameControlCardCtnChapter         -- Chapter card
  +-- CGameControlCardCtnGhostInfo       -- Ghost info card
  +-- CGameControlCardCtnNetServerInfo   -- Server info card
  +-- CGameControlCardCtnReplayRecordInfo -- Replay info card
  +-- CGameControlCardCtnVehicle         -- Vehicle card
  +-- CGameControlCardGeneric            -- Generic card
  +-- CGameControlCardLadderRanking      -- Ranking card
  +-- CGameControlCardLeague             -- League card
  +-- CGameControlCardMessage            -- Message card
  +-- CGameControlCardProfile            -- Player profile card
CGameControlCardManager                   -- Card widget manager
CGameControlDataType                      -- Card data type definition
CGameControlGrid                          -- Game-specific grid
CGameControlGridCard                      -- Grid of cards
```

### 4.4 Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CControlEngine` | `ContainersDoLayout`, `ContainersEffects`, `ContainersFocus`, `ContainersValues`, `ControlsEffects`, `ControlsFocus`, `ControlsValues` | UI frame update pipeline |
| `CControlTextEdition` | `GenerateTree`, `UpdateControlBoundingBox`, `UpdateDisplaylinesNear`, `UpdateFormattedTextNear` | Text layout |
| `CControlEffectSimi` | `SKeyVal` | Keyframe value struct |
| `CGameManialinkAnimManager` | `EAnimManagerEasing` | Animation easing enum |
| All `CGameManialink*` | `UpdateControl` | Per-frame control update |

### 4.5 Browser Recreation Implications

- Manialink is essentially an XML-based UI markup language -- maps well to HTML/CSS
- `CControlEffect*` system provides UI animations (motion, frame moves, similarity transforms)
- Style system (`CControlStyle`/`CControlStyleSheet`) is CSS-like
- Layout engine (`CControlLayout`) handles positioning
- The card system is a reusable widget pattern for data display

---

## 5. Editor System

**Class count**: 71
**Prefixes**: `CGameEditor*`, `CGameCtnEditor*`, `CInteraction*`, `CGameModuleEditor*`

### 5.1 Editor Types (15+ editors)

```
CMwNod
  +-- CGameEditorBase                     -- Abstract base for all editors
  |     +-- CGameEditorAction             -- Action (ability) editor
  |     +-- CGameEditorAnimChar           -- Character animation editor
  |     +-- CGameEditorAnimClip           -- Animation clip editor
  |     +-- CGameEditorBullet             -- Bullet/projectile editor
  |     +-- CGameEditorCustomBullet       -- Custom bullet editor
  |     +-- CGameEditorItem               -- Item editor
  |     +-- CGameEditorManialink          -- Manialink UI editor
  |     +-- CGameEditorMaterial           -- Material editor
  |     +-- CGameEditorMediaTracker       -- MediaTracker editor
  |     +-- CGameEditorMesh               -- Mesh/3D model editor
  |     +-- CGameEditorModule             -- Module editor
  |     +-- CGameEditorPacks              -- Pack/title editor
  |     +-- CGameEditorScript             -- Script editor
  |     +-- CGameEditorSkin               -- Skin/paint editor
  |     +-- CGameEditorVehicle            -- Vehicle editor
  +-- CGameCtnEditor                      -- CTN map editor base
  |     +-- CGameCtnEditorCommon          -- Common editor functionality
  |     +-- CGameCtnEditorFree            -- Free-place map editor
  |     +-- CGameCtnEditorPuzzle          -- Puzzle mode editor
  |     +-- CGameCtnEditorSimple          -- Simple mode editor
  +-- CGameEditorEditor                   -- Editor-of-editors (meta-editor)
  +-- CGameEditorParent                   -- Parent editor container
```

### 5.2 Editor Supporting Classes

```
CGameEditorAnimChar_Interface             -- Animation char editor UI
CGameEditorAnimSet                        -- Animation set editor
CGameEditorAsset                          -- Generic asset editor
CGameEditorBadgeScript                    -- Badge editor script API
CGameEditorActionScript                   -- Action editor script API
CGameEditorCanvas                         -- Editor canvas/viewport
CGameEditorEvent                          -- Editor event
CGameEditorFileToolBar                    -- File toolbar (save/load)
CGameEditorGenericInventory               -- Item inventory browser
CGameEditorMainPlugin                     -- Main editor plugin
CGameEditorMapMacroBlockInstance          -- Macroblock instance in editor
CGameEditorMapScriptClip                  -- Editor clip script wrapper
CGameEditorMapScriptClipList              -- Editor clip list script wrapper
CGameEditorModel                          -- Editor model container
CGameEditorPlugin                         -- Editor plugin base
CGameEditorPluginAPI                      -- Plugin scripting API
CGameEditorPluginCameraAPI                -- Plugin camera API
CGameEditorPluginCameraManager            -- Plugin camera manager
CGameEditorPluginCursorAPI                -- Plugin cursor API
CGameEditorPluginCursorManager            -- Plugin cursor manager
CGameEditorPluginHandle                   -- Plugin handle
CGameEditorPluginLayerScriptHandler       -- Plugin layer script handler
CGameEditorPluginMap                      -- Map editor plugin
CGameEditorPluginMapConnectResults        -- Block connection validation
CGameEditorPluginMapLayerScriptHandler    -- Map layer script handler
CGameEditorPluginMapManager               -- Map plugin manager
CGameEditorPluginMapMapType               -- Map type plugin
CGameEditorPluginMapScriptEvent           -- Map editor script event
CGameEditorPluginModuleScriptEvent        -- Module editor script event
CGameEditorProcGenPluginAPI               -- Procedural generation API
CGameEditorPropertyList                   -- Property list editor
CGameEditorSkinPluginAPI                  -- Skin editor plugin API
CGameEditorTimeLine                       -- Timeline editor component
CGameEditorTrigger                        -- Trigger editor
CGameEditorUndoSystem_State               -- Undo/redo state
CGameEditorMediaTrackerPluginAPI          -- MediaTracker plugin API
CGameCtnEditorBody                        -- Editor body/main area
CGameCtnEditorCommonInterface             -- Common editor interface
CGameCtnEditorCommonInterface_CreateHierarchy -- Interface hierarchy builder
CGameCtnEditorHistory                     -- Editor undo history
CGameCtnEditorMapTypeScriptHandler        -- Map type script handler
CGameCtnEditorPlugin                      -- CTN editor plugin
CGameCtnEditorPluginLayerScriptHandler    -- CTN plugin layer handler
CGameCtnEditorPluginMapType               -- CTN map type plugin
CGameCtnEditorPluginScriptEvent           -- CTN plugin script event
CGameCtnEditorPluginScriptHandler         -- CTN plugin script handler
CGameCtnEditorScriptAnchoredObject        -- Script-accessible anchored object
CGameCtnEditorScriptSpecialProperty       -- Script-accessible special property
CGameModuleEditorBase                     -- Module editor base
CGameModuleEditorGraphEditionModel        -- Module graph editor model
CGameModuleEditorModel                    -- Module editor model
```

### 5.3 Interaction System (5 classes)

```
CInteraction                              -- Editor interaction mode base
  +-- CInteraction_Action                 -- Action editing interaction
  +-- CInteraction_CustomBullet           -- Custom bullet editing
  +-- CInteraction_Script                 -- Script editing interaction
  +-- CInteraction_Skin                   -- Skin editing interaction
```

### 5.4 Key Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CGameEditorMesh` | `CreateNew`, `ImportPlugCrystal*`, `Interaction_DoTranslation`, `Interaction_DoVoxelPickDrag_*`, `InternalPickEdge/Face/Vertex`, `RunEditor` | Voxel/mesh editing |
| `CGameEditorItem` | `CbBeforeIsCheckpoint/Finish/Start/StartFinish`, `PrepareEditCrystal/Mesh/Shape`, `RunEditor` | Item creation |
| `CGameEditorPluginMap` | `CanPlaceBlock/GhostBlock/Macroblock`, `PlaceBlock/Macroblock`, `RemoveBlock/Macroblock`, `GetConnectResults` | Programmatic map editing |
| `CGameCtnEditorCommon` | `AutoSave`, `BuildTerrain`, `CanPlaceMacroBlock`, `PlaceMacroBlock`, `PlaceSolution`, `RunEditor` | Core editor operations |

### 5.5 Browser Recreation Implications

- Map editor is the most complex editor -- block/item placement with clip-based connectivity
- Mesh editor uses voxel pick-drag paradigm
- Plugin API (`CGameEditorPluginMap`) enables scripted map generation
- Undo system (`CGameCtnEditorHistory`, `CGameEditorUndoSystem_State`) needed for any editor
- The `RunEditor` pattern appears on every editor type -- likely a main loop method

---

## 6. Replay/Ghost System

**Class count**: 14
**Prefixes**: `CGameCtnGhost*`, `CGameCtnReplay*`, `CGameGhost*`, `CGhostManager`, `CReplayInfo`, `CGameReplayObjectVisData`

### 6.1 Class Hierarchy

```
CMwNod
  +-- CGameCtnGhost                       -- Ghost data (recorded car state per tick)
  +-- CGameCtnReplayRecord                -- Complete replay record
  +-- CGameCtnReplayRecordInfo            -- Replay metadata
  +-- CGameGhost                          -- Base ghost object
  +-- CGameGhostTMData                    -- TrackMania-specific ghost data
  +-- CGameGhostMgrScript                 -- Ghost manager script API
  +-- CGameGhostScript                    -- Ghost script interface
  +-- CGhostManager                       -- Ghost lifecycle manager
  +-- CReplayInfo                         -- Replay file info
  +-- CGameReplayObjectVisData            -- Replay object visual data
  +-- CPlugEntRecordData                  -- Entity record data (raw ghost frames)
  +-- CPlugSimuDump                       -- Simulation state dump
  +-- CInputReplay                        -- Input recording [CROSS-CUTTING with Input]
  +-- CGameSaveLaunchedCheckpoints        -- Checkpoint state saves during run
```

### 6.2 Architecture

**Ghost Recording Pipeline**:
1. `CInputReplay` captures raw input each simulation tick
2. `CPlugEntRecordData` stores entity state (position, rotation, speed per tick)
3. `CGameCtnGhost` / `CGameGhostTMData` wraps ghost-specific data
4. `CGhostManager` manages active ghosts
5. `CGameCtnReplayRecord` bundles ghost(s) + map reference + metadata

**Ghost Data vs Input Replay**:
- **Ghost**: Visual replay -- position/rotation/visual state per frame
- **Input replay**: Deterministic replay -- raw inputs that reproduce the exact run
- Both are present in the system, suggesting Nadeo uses both approaches

### 6.3 Related Task Classes (counted under Web Services)

- `CGameDataFileTask_GhostDriver`, `_GhostDriver_Download`, `_GhostDriver_Upload`, `_GhostDriver_UploadLimits`
- `CGameDataFileTask_GhostLoadMedal`, `_GhostLoadUserRecord_Maniaplanet`, `_GhostStoreUserRecord_Maniaplanet`

### 6.4 Browser Recreation Implications

- Ghost format needs reverse engineering -- `CPlugEntRecordData` is the raw format
- Replays bundle ghost + map UID + metadata
- Deterministic physics allows input-based replay (smallest data)
- Ghost visual playback is interpolation of position/rotation keyframes
- Checkpoint state saving (`CGameSaveLaunchedCheckpoints`) enables respawns

---

## 7. Map/Block System

**Class count**: 60
**Prefixes**: `CGameCtnBlock*`, `CGameCtnChallenge*`, `CGameCtnZone*`, `CBlock*`, `CMapEditorInventory*`

### 7.1 Map Structure

```
CMwNod
  +-- CGameCtnChallenge                   -- THE map class (legacy name "Challenge")
  +-- CGameCtnChallengeInfo               -- Map metadata (UID, name, author)
  +-- CGameCtnChallengeParameters         -- Map parameters (time limits, medals)
  +-- CGameCtnChallengeGroup              -- Group of maps
  +-- CGameCtnCollection                  -- Block collection (environment)
  +-- CGameCtnCatalog                     -- Block catalog
  +-- CGameCtnCampaign                    -- Campaign structure
  +-- CGameCtnChapter                     -- Campaign chapter
  +-- CGameCtnDecoration                  -- Map decoration/skybox
  +-- CGameCtnDecorationMaterialModifiers -- Decoration material adjustments
  +-- CGameCtnDecorationMood              -- Decoration time-of-day mood
  +-- CGameCtnDecorationSize              -- Decoration dimensions
```

### 7.2 Block System

```
CMwNod
  +-- CGameCtnBlock                       -- Placed block instance on map
  +-- CGameCtnBlockInfo                   -- Block type definition
  |     +-- CGameCtnBlockInfoClassic      -- Classic grid-snapped block
  |     +-- CGameCtnBlockInfoClip         -- Clip connection block
  |     |     +-- CGameCtnBlockInfoClipHorizontal  -- Horizontal clip
  |     |     +-- CGameCtnBlockInfoClipVertical    -- Vertical clip
  |     +-- CGameCtnBlockInfoFlat         -- Flat terrain block
  |     +-- CGameCtnBlockInfoFrontier     -- Zone frontier block
  |     +-- CGameCtnBlockInfoMobil        -- Mobile/moveable block
  |     +-- CGameCtnBlockInfoMobilLink    -- Mobile block link
  |     +-- CGameCtnBlockInfoPylon        -- Pylon (pillar) block
  |     +-- CGameCtnBlockInfoRectAsym     -- Rectangular asymmetric block
  |     +-- CGameCtnBlockInfoRoad         -- Road block
  |     +-- CGameCtnBlockInfoSlope        -- Slope/hill block
  |     +-- CGameCtnBlockInfoTransition   -- Terrain transition block
  +-- CGameCtnBlockInfoVariant            -- Block variant base
  |     +-- CGameCtnBlockInfoVariantAir   -- Air variant (elevated)
  |     +-- CGameCtnBlockInfoVariantGround -- Ground variant
  +-- CGameCtnBlockSkin                   -- Block skin/appearance
  +-- CGameCtnBlockUnit                   -- Block unit (single cell)
  +-- CGameCtnBlockUnitInfo               -- Block unit info
  +-- CBlockModel                         -- Script-API block model
  +-- CBlockModelClip                     -- Script-API clip model
  +-- CBlockModelVariant                  -- Script-API variant
  |     +-- CBlockModelVariantAir         -- Air variant
  |     +-- CBlockModelVariantGround      -- Ground variant
  +-- CBlockClip                          -- Block clip connection
  +-- CBlockClipList                      -- Block clip list
  +-- CBlockUnit                          -- Block unit (script API)
  +-- CBlockUnitModel                     -- Block unit model (script API)
  +-- CGameCtnMacroBlockInfo              -- Macroblock (multi-block template)
  +-- CGameCtnMacroBlockJunction          -- Macroblock junction
  +-- CGameCtnMacroDecals                 -- Macroblock decals
```

### 7.3 Item/Anchor System

```
CMwNod
  +-- CGameCtnAnchoredObject             -- Placed item on map
  +-- CGameCtnAnchorPoint                -- Anchor point on block
  +-- CGameItemModel                      -- Item model definition
  +-- CGameItemModelTreeRoot              -- Item model tree
  +-- CGameItemPlacementParam             -- Item placement parameters
  +-- CItemAnchor                         -- Item anchor point
  +-- CGameBlockItem                      -- Block-as-item wrapper
  +-- CGameBlockItemVariantChooser        -- Block item variant selection
  +-- CGameBlockInfoGroups                -- Block info group collection
  +-- CGameBlockInfoTreeRoot              -- Block info tree root
  +-- CAnchorData                         -- Anchor/waypoint data
```

### 7.4 Zone System

```
CMwNod
  +-- CGameCtnZone                        -- Base zone
  |     +-- CGameCtnZoneFlat              -- Flat terrain zone
  |     +-- CGameCtnZoneFrontier          -- Zone border
  |     +-- CGameCtnZoneTransition        -- Zone transition
  +-- CGameCtnZoneFusionInfo              -- Zone fusion data
  +-- CGameCtnZoneGenealogy               -- Zone genealogy/history
  +-- CGameCtnAutoTerrain                 -- Auto-generated terrain
  +-- CGameCtnPylonColumn                 -- Pylon column
  +-- CGameWaypointSpecialProperty        -- Waypoint properties (start/finish/CP)
```

### 7.5 Map Editor Inventory (Script API)

```
CMapEditorInventory                       -- Script inventory
CMapEditorInventoryNode                   -- Inventory tree node
  +-- CMapEditorInventoryArticle          -- Inventory leaf (block/item)
  +-- CMapEditorInventoryDirectory        -- Inventory folder
CMapEditorPlugin                          -- Script map editor plugin
CMapEditorPluginEvent                     -- Script editor event
CMapEditorPluginLayer                     -- Script editor layer
CMapEditorCursor                          -- Script editor cursor
CMapEditorConnectResults                  -- Script connectivity check results
```

### 7.6 Key Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CGameCtnChallenge` | `InitChallengeData_*` (8 methods), `LoadAndInstanciateBlocks`, `CreatePlayFields`, `InitAllAnchoredObjects` | Map loading pipeline |
| `CBlockModel` | `EWayPointType` | Block waypoint type enum |
| `CAnchorData` | `EWaypointType` | Waypoint type enum (Start/Finish/Checkpoint/etc.) |

### 7.7 Browser Recreation Implications

- Map is a 3D grid of blocks (`CGameCtnBlock`) + free-placed items (`CGameCtnAnchoredObject`)
- Block connectivity uses the clip system (`CGameCtnBlockInfoClip*`)
- Block types determine terrain shape: Road, Slope, Flat, Frontier, Transition
- Waypoint types (Start, Finish, Checkpoint, StartFinish) define race logic
- Macroblock system (`CGameCtnMacroBlockInfo`) allows block templates
- Zone system manages terrain LOD and fusion

---

## 8. Vehicle/Car System

**Class count**: 27
**Prefixes**: `CPlugVehicle*`, `CSceneVehicle*`, `CGameVehicle*`, `CVehicleSettings`

### 8.1 Class Hierarchy

```
CMwNod
  +-- CGameVehicleModel                   -- Game-level vehicle model
  +-- CGameVehiclePhy                     -- Game-level vehicle physics
  +-- CGameScriptVehicle                  -- Script API vehicle wrapper
  +-- CGameScriptMgrVehicle               -- Script vehicle manager
  +-- CVehicleSettings                    -- Vehicle configuration
  +-- CPlugVehiclePhyModelCustom          -- Custom physics model
  +-- CPlugVehicleCarPhyShape             -- Car physics collision shape
  +-- CPlugVehicleGearBox                 -- Transmission model
  +-- CPlugVehicleWheelPhyModel           -- Wheel/tire physics model
  +-- CPlugVehicleMaterialGroup           -- Vehicle material group
  +-- CPlugVehicleVisModel                -- Vehicle visual model
  +-- CPlugVehicleVisModelShared          -- Shared visual model data
  +-- CPlugVehicleVisGeomModel            -- Visual geometry model
  +-- CPlugVehicleVisEmitterModel         -- Visual particle emitter
  +-- CPlugVehicleVisStyles               -- Visual style collection
  +-- CPlugVehicleVisStyleRandomGroup     -- Random style selection
  +-- CPlugVehicleCamInternalVisOffset    -- [already counted in Camera]
  +-- CSceneVehicleVis                    -- Scene vehicle visual instance
  +-- CSceneVehicleVisState               -- Vehicle visual state (pose)
  +-- CSceneVehicleVisParams              -- Vehicle visual parameters
  +-- CSceneVehicleVisVFXExtraContext      -- Vehicle VFX extra context
  +-- CSceneVehicleCarMarksModel          -- Tire mark model
  +-- CSceneVehicleCarMarksModelSub       -- Tire mark sub-model
  +-- CSceneVehicleCarMarksSamples        -- Tire mark sample points
  +-- CSceneWagonPhy                      -- Wagon physics (train)
  +-- CSceneWagonVis                      -- Wagon visual (train)
  +-- CPlugTrainModel                     -- Train model
  +-- CPlugTrainWagonModel                -- Train wagon model
  +-- CPlugTrainWagonModelCustom          -- Custom wagon model
```

### 8.2 Architecture

**Vehicle Model/Phy/Vis Decomposition**:
- **Model**: `CGameVehicleModel` + `CPlugVehiclePhyModelCustom` -- defines the car
- **Physics**: `CGameVehiclePhy` + `CPlugVehicleCarPhyShape` + `CPlugVehicleWheelPhyModel` + `CPlugVehicleGearBox`
- **Visual**: `CPlugVehicleVisModel` + `CSceneVehicleVis` + `CSceneVehicleVisState`

**Physics Components**:
- `CPlugVehicleCarPhyShape` -- collision hull
- `CPlugVehicleWheelPhyModel` -- suspension, grip, radius
- `CPlugVehicleGearBox` -- gear ratios, shift timing
- `CPlugVehiclePhyModelCustom` -- custom physics overrides

**Visual Components**:
- `CPlugVehicleVisModel` -- base visual model
- `CPlugVehicleVisGeomModel` -- geometry (mesh)
- `CPlugVehicleVisEmitterModel` -- particle emitters (exhaust, sparks)
- `CPlugVehicleVisStyles` -- paint/style variants
- `CSceneVehicleCarMarksModel` -- tire marks on road surface

### 8.3 Related Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CHmsSolidVisCst_TmCar` | `SPrestige` | Prestige visual constants |
| `CSystemConfig` | `ETmCarQuality`, `ETmCarParticlesQuality` | Car quality settings |

### 8.4 Browser Recreation Implications

- Vehicle physics is the most critical subsystem for gameplay feel
- `CPlugVehicleWheelPhyModel` contains suspension/grip parameters
- `CPlugVehicleGearBox` defines transmission behavior
- Tire marks (`CSceneVehicleCarMarksSamples`) need real-time mesh generation
- Train system (`CPlugTrainModel*`, `CSceneWagon*`) is for scenery trains
- Visual styles enable car skin/paint customization

---

## 9. Web Services

**Class count**: 713 (largest subsystem by far)
**Prefixes**: `CWebServices*`, `CNetNadeoServicesTask_*`, `CNetUbiServicesTask_*`, `CNetMasterServer*`, `CNetUplayPC*`, `CGameDataFileTask_*`, `CGameScoreTask_*`, `CGameMasterServer*`, `CGameUserTask_*`

### 9.1 Architecture Overview

The web services system uses a **Task/Result** pattern throughout. Every online operation is an async task that produces a typed result.

### 9.2 Service Facades (20 classes)

```
CWebServices                              -- Top-level web services manager
CWebServicesAchievementService            -- Achievement management
CWebServicesActivityService               -- Activity/match reporting
CWebServicesClientService                 -- Client configuration
CWebServicesEventService                  -- Event tracking/telemetry
CWebServicesFriendService                 -- Friend list management
CWebServicesIdentityManager               -- Identity resolution
CWebServicesIdentityTaskManager           -- Identity task management
CWebServicesMapRecordService              -- Map record (leaderboard) service
CWebServicesMapService                    -- Map upload/download service
CWebServicesNewsService                   -- News/notifications
CWebServicesNotificationManager           -- Push notifications
CWebServicesPartyService                  -- Party/group management
CWebServicesPermissionService             -- Permission/privilege checks
CWebServicesPreferenceService             -- User preferences
CWebServicesPrestigeService               -- Prestige/cosmetic management
CWebServicesStatService                   -- Statistics tracking
CWebServicesTagService                    -- Tag/label management
CWebServicesUserManager                   -- User session management
CWebServicesZoneService                   -- Geographic zone management
CWebServicesUserInfo                      -- User info container
CWebServicesTaskScheduler                 -- Task scheduling/queuing
```

All have a `Terminate` method.

### 9.3 Nadeo Services Tasks (157 classes)

`CNetNadeoServicesTask_*` -- grouped by API domain:

| Domain | Count | Examples |
|--------|------:|---------|
| Account/Profile | ~40 | `GetAccountXp`, `GetAccountZone`, `SetAccountSkin`, `GetAccountPrestige*` |
| Maps | ~15 | `GetMap`, `GetMapList`, `SetMap`, `GetMapRecordList`, `GetMapVote` |
| Seasons/Campaigns | ~10 | `GetSeason`, `GetSeasonList`, `SetSeason`, `GetCampaignList` |
| Item Collections | ~10 | `GetItemCollection*`, `CreateItemCollectionVersion`, `SetItemCollectionActivityId` |
| Skins | ~8 | `GetSkin`, `CreateSkin`, `GetCreatorSkinList` |
| Squads | ~8 | `CreateSquad`, `AcceptSquadInvitation`, `LeaveSquad`, `SetSquadLeader` |
| Authentication | ~6 | `AuthenticateWithBasicCredentials`, `AuthenticateWithUbiServices`, `RefreshNadeoServicesAuthenticationToken` |
| Trophies | ~4 | `GetTrophySettings`, `SetTrophyCompetitionMatchAchievementResult` |
| Encrypted Packages | ~5 | `GetEncryptedPackageAccountKey`, `CreateEncryptedPackageVersion` |
| Prestige | ~5 | `GetAccountPrestigeCurrent`, `SetAccountPrestigeCurrent` |
| Client Config | ~5 | `GetClientConfig`, `GetClientFileList`, `SetClientCaps` |
| Upload | ~3 | `CreateUpload`, `Upload`, `UploadPart` |
| Subscriptions | ~3 | `AddSubscription`, `GetAccountSubscriptionList` |
| Other | ~35 | Profile chunks, clubs, servers, stations, bots, telemetry, etc. |

### 9.4 Ubisoft Services Tasks (38 classes)

`CNetUbiServicesTask_*`:

| Domain | Count | Examples |
|--------|------:|---------|
| Party | ~15 | `Party_CreateParty`, `Party_LeaveParty`, `Party_GetPartyMemberList` |
| Profile | ~5 | `Profile_RetrieveProfileInfoList*` |
| Social | ~5 | `GetFriendList`, `Blocklist_Get`, `SendNotification` |
| Player | ~5 | `PlayerConsents_*`, `PlayerPreferences_*` |
| Session | ~3 | `CreateSession`, `DeleteSession`, `RefreshSession` |
| Other | ~5 | `AcceptNDA`, `GetNews`, `GetStatList`, `GetUnsentEvents` |

### 9.5 UplayPC Tasks (11 classes)

`CNetUplayPCTask_*`: `Achievement_GetCompletionList`, `Achievement_Unlock`, `GetFriendList`, `GetUserConsumableItemList`, `JoinSession`, `LeaveSession`, `Overlay_ShowMicroApp`, `ShowBrowserUrl`, `ShowInviteUI`

### 9.6 WebServices Tasks (108 classes)

`CWebServicesTask_*` -- high-level orchestration tasks:

| Domain | Count | Examples |
|--------|------:|---------|
| Connection | ~8 | `Connect`, `Disconnect`, `ConnectToNadeoServices`, `PostConnect*` |
| Prestige | ~8 | `GetPrestige*`, `SetUserPrestigeSelected`, `RetrievePrestigeInfoList` |
| Party | ~12 | `Party_Create`, `Party_Leave`, `Party_RetrievePartyCompleteInfo` |
| Permission | ~12 | `Permission_Check*` (cross-play, multiplayer, UGC, presence) |
| Maps/Records | ~5 | `GetMapList`, `GetMapRecordList*`, `StartMapRecordAttempt` |
| Social | ~5 | `GetFriendList`, `GetBlockList`, `RetrieveFriendList` |
| Profile | ~5 | `SynchronizeProfileChunks`, `UploadProfileChunks` |
| Title | ~5 | `Title_GetConfig`, `Title_GetLadderInfo` |
| User | ~10 | `GetUserClubTag*`, `GetUserZone*`, `SetUserZone` |
| Other | ~38 | News, stations, zones, achievements, stats, etc. |

### 9.7 WebServices Task Results (168 classes)

`CWebServicesTaskResult_*` -- typed result containers:

| Prefix | Count | Type |
|--------|------:|------|
| `_NS*` | ~65 | Nadeo Services results (maps, skins, items, seasons, etc.) |
| `_WS*` | ~20 | Web Services results (friends, parties, prestige, news) |
| `_NadeoServices*` | ~15 | Nadeo Services script-accessible results |
| `_UbiServices*` | ~12 | Ubisoft Services results (party, profile, consent) |
| `_UPC*` | ~3 | Uplay PC results (achievements, friends) |
| Generic | ~53 | `Bool`, `Integer`, `String`, `Natural`, `Ghost*`, `Season*`, etc. |

### 9.8 Game-Level Task Classes (counted under Web Services total)

- `CGameDataFileTask_*` (44 classes): Map, skin, ghost, item collection operations
- `CGameScoreTask_*` (21 classes): Season, trophy, map record operations
- `CGameMasterServerTask_*` (12 classes): Legacy master server operations
- `CGameUserTask_Squad_*` (10 classes): Squad management operations
- `CGameMasterServerRichPresenceTask_*` (2 classes): Presence operations
- `CGameCtnMasterServerTask_*` (3 classes): Legacy CTN server operations
- `CGameWebServicesNotificationTask_*` (2 classes): Notification operations
- `CGameZoneTask_UpdateZoneList` (1 class): Zone list operations
- `CNetMasterServerTask_*` (18 classes): Legacy master server tasks

Infrastructure:
- `CWebServicesTaskSequence`, `CWebServicesTaskVoid`, `CWebServicesTaskWait`, `CWebServicesTaskWaitMultiple`

### 9.9 Authentication Flow

Based on class names, the authentication chain is:
1. `CNetNadeoServicesTask_AuthenticateWithUbiServices` -- Ubi token -> Nadeo token
2. `CNetNadeoServicesTask_AuthenticateWithBasicCredentials` -- Username/password (legacy)
3. `CNetNadeoServicesTask_RefreshNadeoServicesAuthenticationToken` -- Token refresh
4. `CNetNadeoServicesTask_GetAuthenticationToken` -- Get current token

### 9.10 Browser Recreation Implications

- The web services layer is the thickest abstraction -- 713 classes
- For browser recreation, these map to REST API calls to Nadeo services
- The Task/Result pattern maps well to Promise/async-await
- Service facades group related operations logically
- Permission system (`CWebServicesTask_Permission_*`) gates UGC and multiplayer access
- Ghost upload/download (`CGameDataFileTask_GhostDriver_*`) is essential for leaderboards

---

## 10. Scene Graph

**Class count**: 93
**Prefixes**: `CScene*`, `CHms*`

### 10.1 HMS (Hierarchical Managed Scene) -- 41 classes

```
CMwNod
  +-- CHmsZone                            -- Root scene zone
  |     +-- CHmsZoneElem                  -- Zone element
  |     +-- CHmsZoneOverlay               -- Zone overlay (2D)
  +-- CHmsZoneVPacker                     -- Zone vertex packer (geometry baking)
  +-- CHmsPortal                          -- Portal for visibility culling
  +-- CHmsPortalProperty                  -- Portal properties
  +-- CHmsItem                            -- Scene item (renderable)
  +-- CHmsItemShadow                      -- Shadow-casting item
  +-- CHmsCorpus                          -- 3D corpus (body)
  +-- CHmsCorpus2d                        -- 2D corpus
  +-- CHmsSolid2                          -- Solid2 instance in scene
  +-- CHmsCamera                          -- Scene camera
  +-- CHmsLight                           -- Scene light
  +-- CHmsLightArray                      -- Array of lights
  +-- CHmsLightMap                        -- Lightmap data
  +-- CHmsLightMapAllocT3                 -- Lightmap allocation
  +-- CHmsLightMapCache                   -- Lightmap cache
  +-- CHmsLightMapCacheSH                 -- Spherical harmonics lightmap cache
  +-- CHmsLightMapMood                    -- Lightmap mood settings
  +-- CHmsLightMapParam                   -- Lightmap parameters
  +-- CHmsLightProbeGrid                  -- Light probe grid
  +-- CHmsLightProbePartition             -- Light probe spatial partition
  +-- CHmsShadowGroup                     -- Shadow group
  +-- CHmsVolumeShadow                    -- Volume shadow
  +-- CHmsAmbientOcc                      -- Ambient occlusion
  +-- CHmsFogPlane                        -- Fog plane
  +-- CHmsMoodBlender                     -- Time-of-day mood blending
  +-- CHmsDecalArray                      -- Decal batch
  +-- CHmsPicker                          -- Mouse picking
  +-- CHmsPoc                             -- Point of contact
  +-- CHmsPrecalcRender                   -- Precalculated rendering
  +-- CHmsConfig                          -- HMS configuration
  +-- CHmsViewport                        -- HMS viewport
  +-- CHmsViewportPerfDbg                 -- Viewport performance debug
  +-- CHmsVisMiniMap                      -- Mini-map visual
  +-- CHmsSolidVisCst_TmCar              -- TM car rendering constants
  +-- CHmsMgrVisDyna                      -- Dynamic visual manager
  +-- CHmsMgrVisDynaDecal2d              -- Dynamic 2D decal manager
  +-- CHmsMgrVisEnvMap                    -- Environment map manager
  +-- CHmsMgrVisParticle                  -- Particle manager
  +-- CHmsMgrVisVolume                    -- Volume visual manager
```

### 10.2 Scene Objects -- 52 classes

```
CMwNod
  +-- CSceneEngine                        -- Scene engine singleton
  +-- CSceneConfig                        -- Scene configuration
  +-- CSceneConfigVision                  -- Vision-specific config
  +-- CSceneObject                        -- Base scene object
  +-- CSceneMobil                         -- Mobile/moveable scene object
  +-- CSceneSector                        -- Scene sector (spatial region)
  +-- CSceneLayout                        -- Scene layout
  +-- CSceneLocation                      -- Scene location
  +-- CSceneLocationCamera                -- Camera location
  +-- CSceneLight                         -- Scene light instance
  +-- CScenePoc                           -- Point of contact
  +-- CSceneSolid2Vis                     -- Solid2 visual instance
  +-- CSceneCloudSystem                   -- Cloud rendering
  +-- CSceneProfiler                      -- Scene performance profiler
  +-- CScenePickerManager                 -- Mouse picking manager
  +-- CSceneMgrGUI                        -- GUI overlay manager
  +-- CSceneMgrPhy                        -- Physics manager
  +-- CSceneTriggerAction                 -- Trigger action
  +-- CSceneTrafficPhy                    -- Traffic physics
  +-- CSceneFxMgr                         -- Post-FX manager
  +-- CSceneFxNod                         -- FX node base
  +-- CSceneFx                            -- Base post-processing effect
  |     +-- CSceneFxBloom                 -- Bloom effect
  |     +-- CSceneFxBloomData             -- Bloom data
  |     +-- CSceneFxBlur                  -- Blur effect
  |     +-- CSceneFxCameraBlend           -- Camera blend transition
  |     +-- CSceneFxCellEdge              -- Cel-shading edge
  |     +-- CSceneFxColors                -- Color grading
  |     +-- CSceneFxCompo                 -- Composite effect
  |     +-- CSceneFxDepthOfField          -- Depth of field
  |     +-- CSceneFxDistor2d              -- 2D distortion
  |     +-- CSceneFxEdgeBlender           -- Edge blending
  |     +-- CSceneFxFlares                -- Lens flares
  |     +-- CSceneFxHeadTrack             -- Head tracking
  |     +-- CSceneFxOverlay               -- Screen overlay
  |     +-- CSceneFxStereoscopy           -- Stereoscopic 3D
  |     +-- CSceneFxSuperSample           -- Supersampling AA
  +-- CSceneBulletPhy                     -- Bullet physics
  +-- CSceneBulletVis                     -- Bullet visual
  +-- CSceneGunPhy                        -- Gun physics
  +-- CSceneGunVis                        -- Gun visual
  +-- CSceneCharVis                       -- Character visual
  +-- CSceneCharVisState                  -- Character visual state
  +-- CSceneVehicleVis                    -- [counted in Vehicle]
  +-- CSceneVehicleVisState               -- [counted in Vehicle]
  +-- CSceneVehicleVisParams              -- [counted in Vehicle]
  +-- CSceneVehicleVisVFXExtraContext      -- [counted in Vehicle]
  +-- CSceneVehicleCarMarksModel          -- [counted in Vehicle]
  +-- CSceneVehicleCarMarksModelSub       -- [counted in Vehicle]
  +-- CSceneVehicleCarMarksSamples        -- [counted in Vehicle]
  +-- CSceneWagonPhy                      -- [counted in Vehicle]
  +-- CSceneWagonVis                      -- [counted in Vehicle]
```

*Note: Vehicle-related scene classes are counted under the Vehicle subsystem to avoid double-counting.*

### 10.3 Key Methods

| Class | Methods | Purpose |
|-------|---------|---------|
| `CHmsZoneVPacker` | `PrecalcLighting`, `UpdatePackedGeom_LightMapTc`, `StaticOptimUpdate_ReflectLQ`, `UpdateStaticOptims_AfterPreLoad` | Geometry baking |
| `CHmsLightMap` | `ComputeLighting_*`, `Compute_MDiffuse`, `ImageRealAddRGBA`, `SH_UpdateMapping` | Lightmap computation |
| `CHmsMgrVisDyna` | `InstanceCreate`, `InstanceDestroy` | Dynamic instance management |
| `CScenePickerManager` | `BeginFocus`, `DoFocus`, `EndFocus`, `PickerUpdate` | Object picking |
| `CSceneFxSuperSample` | `OnActiveChange`, `SetInit` | AA activation |

### 10.4 Browser Recreation Implications

- Portal-based visibility (HMS portals) can be replaced with frustum culling in WebGL
- Lightmap system (`CHmsLightMap*`) is baked -- need to load pre-computed lightmaps
- Post-processing chain (`CSceneFx*`) maps to WebGL shader passes
- Dynamic instances (`CHmsMgrVisDyna`) are instanced rendering
- Mood blending (`CHmsMoodBlender`) handles day/night transitions

---

## 11. MediaTracker Blocks

**Class count**: 74
**Prefixes**: `CGameCtnMediaBlock*`, `CGameCtnMediaClip*`, `CGameCtnMediaTrack`, `CMediaTracker*`

### 11.1 MediaTracker Infrastructure

```
CMwNod
  +-- CGameCtnMediaClip                   -- Clip (sequence of tracks)
  +-- CGameCtnMediaClipGroup              -- Group of clips
  +-- CGameCtnMediaClipPlayer             -- Clip playback engine
  +-- CGameCtnMediaClipViewer             -- Clip viewer/preview
  +-- CGameCtnMediaClipConfigScriptContext -- Script context config
  +-- CGameCtnMediaTrack                  -- Track (timeline of blocks)
  +-- CGameCtnMediaVideoShooter           -- Video rendering/export
  +-- CGameCtnMediaShootParams            -- Video shoot parameters
  +-- CMediaTrackerBlock                  -- Script-API block wrapper
  +-- CMediaTrackerClip                   -- Script-API clip wrapper
  +-- CMediaTrackerClipGroup              -- Script-API clip group wrapper
  +-- CMediaTrackerTrack                  -- Script-API track wrapper
```

### 11.2 All 65+ MediaTracker Block Types

```
CGameCtnMediaBlock                        -- Base media block
  +-- Camera Blocks (8):
  |     CGameCtnMediaBlockCamera          -- Camera base
  |     CGameCtnMediaBlockCameraCustom    -- Custom keyframed camera
  |     CGameCtnMediaBlockCameraGame      -- In-game camera (chase, cockpit)
  |     CGameCtnMediaBlockCameraOrbital   -- Orbital camera
  |     CGameCtnMediaBlockCameraPath      -- Path-following camera
  |     CGameCtnMediaBlockCameraSimple    -- Simple fixed camera
  |     CGameCtnMediaBlockCameraEffect    -- Camera effect base
  |     CGameCtnMediaBlockCameraEffectInertialTracking -- Inertial tracking
  |     CGameCtnMediaBlockCameraEffectScript -- Scripted camera effect
  |     CGameCtnMediaBlockCameraEffectShake -- Camera shake
  +-- Visual FX Blocks (11):
  |     CGameCtnMediaBlockFx              -- FX base
  |     CGameCtnMediaBlockFxBloom         -- Bloom
  |     CGameCtnMediaBlockFxBlur          -- Blur
  |     CGameCtnMediaBlockFxBlurDepth     -- Depth blur (DOF)
  |     CGameCtnMediaBlockFxBlurMotion    -- Motion blur
  |     CGameCtnMediaBlockFxCameraBlend   -- Camera transition blend
  |     CGameCtnMediaBlockFxCameraMap     -- Camera mapping effect
  |     CGameCtnMediaBlockFxColors        -- Color adjustment
  |     CGameCtnMediaBlockBloomHdr        -- HDR bloom
  |     CGameCtnMediaBlockDOF             -- Depth of field
  |     CGameCtnMediaBlockDirtyLens       -- Dirty lens effect
  +-- Overlay/2D Blocks (8):
  |     CGameCtnMediaBlockText            -- Text overlay
  |     CGameCtnMediaBlockImage           -- Image overlay
  |     CGameCtnMediaBlockDecal2d         -- 2D decal
  |     CGameCtnMediaBlockTriangles       -- Triangle mesh overlay
  |     CGameCtnMediaBlockTriangles2D     -- 2D triangle overlay
  |     CGameCtnMediaBlockTriangles3D     -- 3D triangle overlay
  |     CGameCtnMediaBlockManialink       -- Manialink UI overlay
  |     CGameCtnMediaBlockInterface       -- Interface overlay
  +-- Scene Blocks (6):
  |     CGameCtnMediaBlockEntity          -- Entity in scene
  |     CGameCtnMediaBlockGhostTM         -- TrackMania ghost display
  |     CGameCtnMediaBlockObject          -- 3D object
  |     CGameCtnMediaBlockScenery         -- Scenery element
  |     CGameCtnMediaBlockSkel            -- Skeleton animation
  |     CGameCtnMediaBlockVehicleLight    -- Vehicle light control
  +-- Audio Blocks (2):
  |     CGameCtnMediaBlockSound           -- Sound playback
  |     CGameCtnMediaBlockMusicEffect     -- Music effect
  +-- Environment Blocks (4):
  |     CGameCtnMediaBlockFog             -- Fog settings
  |     CGameCtnMediaBlockToneMapping     -- Tone mapping
  |     CGameCtnMediaBlockColorGrading    -- Color grading LUT
  |     CGameCtnMediaBlockLightmap        -- Lightmap settings
  +-- Timing Blocks (2):
  |     CGameCtnMediaBlockTime            -- Time key
  |     CGameCtnMediaBlockTimeSpeed       -- Playback speed
  +-- Transition Blocks (2):
  |     CGameCtnMediaBlockTransition      -- Transition base
  |     CGameCtnMediaBlockTransitionFade  -- Fade transition
  +-- Coloring Blocks (2):
  |     CGameCtnMediaBlockColoringBase    -- Base coloring
  |     CGameCtnMediaBlockColoringCapturable -- Capturable coloring
  +-- Gameplay Blocks (3):
  |     CGameCtnMediaBlockSpectators      -- Spectator crowd
  |     CGameCtnMediaBlockOpponentVisibility -- Opponent visibility
  |     CGameCtnMediaBlockTrails          -- Trail effects
  +-- Special Blocks (5):
  |     CGameCtnMediaBlock3dStereo        -- 3D stereoscopic
  |     CGameCtnMediaBlockUi              -- UI block
  |     CGameCtnMediaBlockShoot           -- Screenshot trigger
  |     CGameCtnMediaBlockTurret          -- Turret control
  |     CGameCtnMediaBlockEditor          -- Editor view
  |     CGameCtnMediaBlockEditorDecal2d   -- Editor 2D decal
  |     CGameCtnMediaBlockEditorTriangles -- Editor triangles
  +-- Deprecated Blocks (2):
        CGameCtnMediaBlockBulletFx_Deprecated
        CGameCtnMediaBlockCharVis_Deprecated
        CGameCtnMediaBlockEvent_deprecated
```

### 11.3 Key Methods

Most media blocks expose a `SKeyVal` or `SuperSKeyVal` struct for keyframe interpolation:

| Class | Methods | Purpose |
|-------|---------|---------|
| `CGameCtnMediaBlockCameraCustom` | `ECamInterp`, `SKeyVal` | Camera interpolation type, keyframe values |
| `CGameCtnMediaBlockEntity` | `ComputeInterpolatedVisStatesAtTime`, `Update` | Entity state interpolation |
| `CGameCtnMediaBlockEditorTriangles` | `EEditMode` | Triangle editing mode |
| `CGameCtnMediaVideoShooter` | `DoShoot`, `ShootClip` | Video rendering |

### 11.4 Browser Recreation Implications

- MediaTracker is a cutscene/replay editor with timeline-based block composition
- Each block type controls one aspect (camera, audio, FX, overlay) at a given time range
- `SKeyVal` / `SuperSKeyVal` are keyframe structures for interpolation
- Clips contain tracks, tracks contain blocks, blocks have time ranges and keyframes
- Camera blocks are the most important for replay viewing
- Color grading and tone mapping blocks affect post-processing
- Ghost display (`CGameCtnMediaBlockGhostTM`) renders car ghosts in replays

---

## 12. Plugin/Mod System (CPlug*)

**Class count**: 392 (entire CPlug* family minus audio/vehicle/camera classes already counted)
**Note**: Audio classes (CPlugSound*, CPlugMusic*, CPlugAudio*, CPlugFile audio), vehicle classes (CPlugVehicle*), and camera models (CPlugCam*) are counted in their respective subsystems. This section covers the remaining ~310 CPlug* classes.

### 12.1 Animation System (77 classes)

```
CPlugAnimGraph                            -- Animation state graph
CPlugAnimGraphNode_* (41 types)          -- Graph node types
  AirTrajectoryPrediction, AssertVar, AvatarPoseEditor, AvatarV0,
  AvatarV3_Global/Idle/Jump/Locomotion/Resting/Seated/Swim,
  Avatar_Climb, Blend, Blend2d, ClipGroupPlay, ClipPlay,
  DebugHelper, ExtractMotion, ExtractUnit, Funnel,
  GlobalToLocal, Graph, GraphInput, GraphOutput, Group,
  JointAlignTo, JointIK2, JointInertia, JointKeepRefGlobalRot,
  JointLock, JointRotConstraint, JointRotate, JointRotateFrom,
  JointTransConstraint, JointTranslate, JointTranslateDistConstraint,
  LayeredBlend, LocalToGlobal, LodSwitch, PoseGrid,
  RefGlobalPose, RefLocalPose, SetJointExpr, SetSkel,
  SetVar, StateMachine
CPlugAnimGraphStack                       -- Graph stack
CPlugAnimGraphState                       -- Graph state
CPlugAnimGraphTransition                  -- State transition
CPlugAnimClip / Baked / Edition / EditionPose / Flags  -- Clips
CPlugAnimFile / FileXml                   -- Animation files
CPlugAnimImport                           -- Animation import
CPlugAnimChannelGroup                     -- Animation channels
CPlugAnimJointExprGroup                   -- Joint expressions
CPlugAnimLocSimple                        -- Simple location animation
CPlugAnimNode                             -- Legacy animation node
  +-- CPlugAnimNodeAim / Blend2d / Clip / Jump / LocoGroup / ProceduralAttractor / Sequence
CPlugAnimPoseGrid / PoseGroup             -- Pose data
CPlugAnimRigUIConfig                      -- Rig UI configuration
CPlugAnimRootYaw                          -- Root yaw control
CPlugAnimSpotModel                        -- Spot animation model
CPlugAnimTimingFixedPeriod                -- Fixed-period timing
CPlugAnimTransition                       -- Animation transition
CPlugAnimVariantGroup                     -- Animation variants
```

### 12.2 ADN Animation System (11 classes)

```
CPlugAdnModel                             -- ADN model
CPlugAdnProject                           -- ADN project
CPlugAdnPart / PartInstance               -- ADN parts
CPlugAdnAnimClip                          -- ADN animation clip
CPlugAdnRandomGen / GenList / Group       -- Randomization
CPlugAdnShader_Part / Skin               -- ADN shaders
CPlugAdnTagFidCache                       -- Tag file cache
```

### 12.3 Bitmap/Texture System (28 classes)

```
CPlugBitmapBase                           -- Base bitmap
CPlugBitmap                               -- Main bitmap class
CPlugBitmapAddress                        -- Bitmap memory address
CPlugBitmapApplyArray                     -- Bitmap application
CPlugBitmapArray / ArrayBuilder           -- Bitmap arrays
CPlugBitmapAtlas                          -- Texture atlas
CPlugBitmapDecals                         -- Decal bitmaps
CPlugBitmapHighLevel                      -- High-level bitmap
CPlugBitmapPack / PackElem / PackInput / Packer -- Bitmap packing
CPlugBitmapRender                         -- Render target base
  +-- Camera, CubeMap, Hemisphere, LightFromMap, LightOcc,
      Overlay, PlaneR, Portal, Shadow, Solid, Sub, VDepPlaneY, Water
CPlugBitmapSampler                        -- Texture sampler
CPlugBitmapShader                         -- Bitmap shader binding
```

### 12.4 Material System (14 classes)

```
CPlugMaterial                             -- Base material
CPlugMaterialCustom                       -- Custom material
CPlugMaterialUserInst                     -- User material instance
CPlugMaterialPack                         -- Material pack
CPlugMaterialColorTargetTable             -- Color target table
CPlugMaterialFx                           -- Material effect base
  +-- CPlugMaterialFxDynaBump             -- Dynamic bump mapping
  +-- CPlugMaterialFxDynaMobil            -- Dynamic mobile effect
  +-- CPlugMaterialFxFlags                -- Material effect flags
  +-- CPlugMaterialFxFur                  -- Fur material effect
  +-- CPlugMaterialFxGenCV                -- Generic CV effect
CPlugMaterialFxs                          -- Material effects collection
CPlugMaterialWaterArray                   -- Water material array
CPlugMaterial_VertexIndex                 -- Vertex index material data
```

### 12.5 Model/Mesh System (12 classes)

```
CPlugModel                                -- Base model
CPlugModelMesh                            -- Mesh model
CPlugModelLodMesh                         -- LOD mesh model
CPlugModelFences                          -- Fence model
CPlugModelFur                             -- Fur model
CPlugModelShading                         -- Shading model
CPlugModelTree                            -- Model tree
CPlugModelTools_MeshOptimizeVertexCache   -- Mesh optimization
CPlugSolid                                -- Legacy solid model
CPlugSolid2Model                          -- Current solid model (primary mesh format)
CPlugSolidTools                           -- Solid manipulation tools
CPlugStaticObjectModel                    -- Static object model (items)
```

### 12.6 Visual Primitives (18 classes)

```
CPlugVisual                               -- Base visual
  +-- CPlugVisual2D                       -- 2D visual base
  |     +-- CPlugVisualLines2D            -- 2D lines
  |     +-- CPlugVisualQuads2D            -- 2D quads
  +-- CPlugVisual3D                       -- 3D visual base
        +-- CPlugVisualIndexed            -- Indexed geometry base
        |     +-- CPlugVisualIndexedLines -- Indexed lines
        |     +-- CPlugVisualIndexedStrip -- Indexed strips
        |     +-- CPlugVisualIndexedTriangles -- Indexed triangles
        +-- CPlugVisualLines              -- Lines
        +-- CPlugVisualQuads              -- Quads
        +-- CPlugVisualSprite             -- Sprites
        +-- CPlugVisualStrip              -- Strips
        +-- CPlugVisualTriangles          -- Triangles
        +-- CPlugVisualVertexs            -- Vertex cloud
        +-- CPlugVisualGrid              -- Grid
        +-- CPlugVisualOctree            -- Octree visual
        +-- CPlugVisualCelEdge           -- Cel-shading edge
```

### 12.7 File Format Handlers (36 classes)

```
CPlugFile                                 -- Base file handler
  Image: CPlugFileDds, CPlugFileExr, CPlugFileImg, CPlugFileJpg,
         CPlugFilePng, CPlugFileSvg, CPlugFileTga, CPlugFileWebP
  3D Model: CPlugFileModel, CPlugFileModel3ds, CPlugFileModelCollada,
            CPlugFileModelFbx, CPlugFileModelObj
  Audio: [counted in Audio subsystem]
  Shader: CPlugFileGPU, CPlugFileGPUP, CPlugFileGPUV,
          CPlugFilePHlsl, CPlugFileVHlsl
  Video: CPlugFileBink, CPlugFileVideo, CPlugFileWebM
  Text: CPlugFileText, CPlugFileTextScript, CPlugFileI18n, CPlugFileFont
  Data: CPlugFilePack, CPlugFileZip, CPlugFileGen
  Cache: CPlugFileFidCache, CPlugFileFidContainer,
         CPlugFileFidContainer_SystemUserSaveProxy
```

### 12.8 Particle System (9 classes)

```
CPlugParticleEmitterModel                 -- CPU particle emitter
CPlugParticleEmitterSubModel              -- Sub-emitter
CPlugParticleEmitterSubModelGpu           -- GPU sub-emitter
CPlugParticleGpuModel                     -- GPU particle model
CPlugParticleGpuSpawn                     -- GPU particle spawn
CPlugParticleGpuVortex                    -- GPU particle vortex
CPlugParticleImpactModel                  -- Particle on impact
CPlugParticleMaterialImpactModel          -- Material-dependent impact
CPlugParticleSplashModel                  -- Splash particle
```

### 12.9 FX System (15 classes)

```
CPlugFxSystem                             -- FX system base
CPlugFxSystemNode                         -- FX graph node
  +-- CPlugFxSystemNode_Condition         -- Conditional node
  +-- CPlugFxSystemNode_Parallel          -- Parallel execution
  +-- CPlugFxSystemNode_ParticleEmitter   -- Particle emission
  +-- CPlugFxSystemNode_SoundEmitter      -- Sound emission
  +-- CPlugFxSystemNode_SubFxSystem       -- Sub-system
  +-- CPlugFxSystemNode_UpdateVar         -- Variable update
CPlugFxAnimFromTexture1dArray             -- Texture animation
CPlugFxHdrScales_Tech3                    -- HDR scaling
CPlugFxLensDirtGen                        -- Lens dirt generation
CPlugFxLensFlareArray                     -- Lens flare array
CPlugFxLightning                          -- Lightning effect
CPlugFxWindOnDecal                        -- Wind-on-decal effect
CPlugFxWindOnTreeSprite                   -- Wind-on-tree effect
```

### 12.10 VFX Node System (7 classes)

```
CPlugVFXFile                              -- VFX file container
CPlugVFXNode                              -- VFX node base
  +-- CPlugVFXNode_EmissionGroup          -- Emission group
  +-- CPlugVFXNode_Emit                   -- Emit node
  +-- CPlugVFXNode_EmitterModel           -- Emitter model
  +-- CPlugVFXNode_Graph                  -- VFX graph
  +-- CPlugVFXNode_SubEmitterModel        -- Sub-emitter model
  +-- CPlugVFXNode_VortexEmitterModel     -- Vortex emitter
```

### 12.11 Scene Tree (6 classes)

```
CPlugTree                                 -- Base scene tree node
CPlugTreeGenSolid                         -- Generate solid from tree
CPlugTreeGenText                          -- Generate text from tree
CPlugTreeGenerator                        -- Tree generator
CPlugTreeLight                            -- Light tree node
CPlugTreeVisualMip                        -- Visual MIP-mapped tree
```

### 12.12 Shader System (5 classes)

```
CPlugShader                               -- Shader base
CPlugShaderApply                          -- Shader application
CPlugShaderCBufferStatic                  -- Static constant buffer
CPlugShaderGeneric                        -- Generic shader
CPlugShaderPass                           -- Shader pass
```

### 12.13 Physics/Dynamics (5 classes)

```
CPlugDynaModel                            -- Dynamic physics model
CPlugDynaObjectModel                      -- Dynamic object (kinematic items)
CPlugDynaConstraintModel                  -- Physics constraint
CPlugDynaPointModel                       -- Point mass physics
CPlugDynaWaterModel                       -- Water dynamics
```

### 12.14 Character System (8 classes)

```
CPlugCharPhyModel                         -- Character physics base
CPlugCharPhyModelCustom                   -- Custom character physics
CPlugCharPhyMaterial / Materials          -- Character physics materials
CPlugCharPhyRecoilModel                   -- Recoil physics
CPlugCharPhySpecialProperty               -- Special physics properties
CPlugCharVisModel                         -- Character visual model
CPlugCharVisModelCustom                   -- Custom character visual
```

### 12.15 Environment/Weather (10 classes)

```
CPlugWeather                              -- Weather system
CPlugWeatherModel                         -- Weather model
CPlugWeather_DayTimeElem_Compat           -- Day time compatibility
CPlugWeather_WindBlockerElem              -- Wind blocker
CPlugMoodAtmo                             -- Mood atmosphere
CPlugMoodBlender                          -- Mood blending
CPlugMoodCurve                            -- Mood interpolation curve
CPlugMoodSetting                          -- Mood settings
CPlugDayTime                              -- Day/night time
CPlugClouds / CloudsParam / CloudsSolids  -- Cloud system
```

### 12.16 Remaining CPlug* Classes (~50)

```
CPlugEngine                               -- Plugin engine singleton
CPlugEntRecordData                        -- [counted in Replay]
CPlugEntitySpawner                        -- Entity spawning
CPlugEditorHelper                         -- Editor helper utilities
CPlugBeamEmitterModel / SubModel          -- Beam effects
CPlugBulletModel / BulletPhyModel         -- Bullet physics
CPlugCustomBeamModel / CustomBulletModel  -- Custom beam/bullet
CPlugShieldEmitterModel / ShieldModel     -- Shield effects
CPlugBlendShapes                          -- Morph targets
CPlugBodyGraph / BodyPath                 -- Body animation
CPlugCamControlModel                      -- [counted in Camera]
CPlugCamShakeModel                        -- [counted in Camera]
CPlugCitizenModel                         -- NPC citizen model
CPlugCrystal                              -- Crystal geometry editor format
CPlugCurveEnvelopeDeprec / CurveSimpleNod -- Curves
CPlugDataTape                             -- Data tape storage
CPlugDecalModel                           -- Decal definition
CPlugDecoratorSolid / DecoratorTree       -- Decorators
CPlugDestructibleFx                       -- Destruction effects
CPlugFlockModel                           -- Flock/swarm AI
CPlugFogMatter / FogVolume / FogVolumeBox -- Fog volumes
CPlugFont / FontBitmap                    -- Font resources
CPlugFurWind                              -- Fur wind simulation
CPlugGameSkin / GameSkinAndFolder         -- Game skin
CPlugGpuBuffer / GpuCompileCache          -- GPU resources
CPlugGraphNode / _Graph / _Group / _StateMachine -- Graph nodes
CPlugGrassMatterArray                     -- Grass rendering
CPlugIconIndex                            -- Icon atlas index
CPlugImageArray                           -- Image array
CPlugImportMeshParam                      -- Mesh import parameters
CPlugIndexBuffer                          -- Index buffer
CPlugLight / LightDyna / LightMapCustom / LightUserModel -- Lights
CPlugLocatedSound                         -- [counted in Audio]
CPlugMapAINode                            -- AI navigation node
CPlugMediaClipList                        -- Media clip list
CPlugMetaData                             -- Metadata container
CPlugOpModel                              -- Operation model
CPlugPath / PlacementPatch / Podium       -- Paths and placement
CPlugPointsInSphereOpt / PoissonDiscDistribution -- Math utilities
CPlugPolyLine3 / Spline3D                 -- Curves/splines
CPlugPrefab                               -- Prefab composition
CPlugProbe                                -- Light/reflection probe
CPlugPuffLull                             -- Puff wind effect
CPlugRecastPolyMeshData                   -- Navigation mesh
CPlugResource                             -- Generic resource
CPlugRoadChunk / Citizen / Traffic        -- Road chunks
CPlugScriptWithSettings                   -- Script with settings
CPlugSkel / SkelSetup                     -- Skeleton
CPlugSpawnModel                           -- Spawn point model
CPlugSphericalHarmonics                   -- SH lighting
CPlugSpriteParam                          -- Sprite parameters
CPlugSurface / SurfaceGeomDeprecated      -- Collision surfaces
CPlugSymlink                              -- Symbolic link
CPlugTimedPixelArray                      -- Timed pixel data
CPlugTriggerAction                        -- Trigger action
CPlugTurret                               -- Turret model
CPlugVegetMaterialVariation / VegetSubSurfaceParams / VegetTreeModel -- Vegetation
CPlugVertexStream                         -- Vertex stream
CPlugViewDepLocator                       -- View-dependent locator
CPlugVisEntFxModel                        -- Entity visual FX
CPlugVoxelResource                        -- Voxel data
```

### 12.17 Browser Recreation Implications

- `CPlugSolid2Model` is the primary mesh format -- must parse this for 3D rendering
- Material system (`CPlugMaterial*`) maps to WebGL shader uniforms and textures
- Bitmap system loads DDS, PNG, JPG, TGA, WebP, EXR textures
- Particle system has both CPU (`CPlugParticleEmitterModel`) and GPU (`CPlugParticleGpuModel`) paths
- Skeleton/animation system is complex -- 77+ animation classes
- Crystal (`CPlugCrystal`) is the mesh editor's internal format
- Navigation mesh (`CPlugRecastPolyMeshData`) uses Recast library

---

## 13. Remaining Subsystems

### 13.1 Core/MwNod System (17 classes)

```
CMwNod                                    -- Universal base class
CMwEngine / CMwEngineMain                 -- Engine singletons
CMwCmd / CmdBuffer / CmdBufferCore / CmdContainer  -- Command system
CMwCmdFastCall / FastCallStatic / FastCallStaticParam / FastCallUser  -- Fast command calls
CMwCmdFiber                               -- Fiber-based async commands
CMwId                                     -- Interned string/identifier
CMwClassInfoViewer                        -- Runtime class introspection
CMwNetworkEntitiesManager                 -- Networked entity replication
CMwRefBuffer                              -- Reference-counted buffer
CMwStatsValue                             -- Statistics value
```

### 13.2 System Layer (24 classes)

```
CSystemEngine                             -- System engine singleton
CSystemConfig / ConfigDisplay             -- System configuration
CSystemData / DependenciesList            -- System data
CSystemFidFile / FidContainer / FidsDrive / FidsFolder / File -- File system
CSystemManagerFile                        -- File manager
CSystemPackDesc / PackManager             -- Package management
CSystemKeyboard / Mouse                   -- OS input devices
CSystemPlatform / PlatformScript          -- Platform abstraction
CSystemWindow                             -- OS window
CSystemMemoryMonitor                      -- Memory tracking
CSystemArchiveNod / NodWrapper            -- Serialization
CSystemSteam                              -- Steam integration
CSystemUplayPC                            -- Uplay PC integration
CSystemUserMgr                            -- OS user management
```

### 13.3 Networking Core (17 classes)

```
CNetEngine                                -- Network engine singleton
CNetClient / CNetClientInfo               -- Client connection
CNetServer / CNetServerInfo               -- Server
CNetConnection                            -- Connection abstraction
CNetSource / IPSource / URLSource         -- Network sources
CNetNod                                   -- Network node base
CNetSystem                                -- Network system init
CNetUPnP                                  -- UPnP port forwarding
CNetFileTransfer / Download / Form / Nod / Upload  -- File transfer
CNetHttpClient / CNetHttpResult           -- HTTP client
CNetScriptHttpEvent / Manager / Request   -- Script HTTP API
CNetFormConnectionAdmin / EnumSessions / NewPing / Ping / QuerrySessions / RpcCall / Timed -- Network forms
CNetXmpp / Xmpp_Timer                    -- XMPP messaging
CNetIPC                                   -- IPC (inter-process communication)
CNetMasterHost / Server / Download / Info / Request / RequestTask / UptoDateCheck / UserInfo -- Master server
CNetNadeoServices / Request / RequestManager / RequestTask / UserInfo -- Nadeo services infrastructure
CNetUbiServices / Task                    -- Ubisoft services infrastructure
CNetUplayPC / UserInfo                    -- Uplay infrastructure
```

### 13.4 Script Engine (9 classes)

```
CScriptEngine                             -- Script VM singleton
CScriptBaseEvent / BaseConstEvent         -- Script event base
CScriptEvent                              -- Script event
CScriptInterfacableValue                  -- Script-exposed value
CScriptPoison                             -- Script memory poison (debug)
CScriptSetting                            -- Script setting
CScriptTraitsMetadata / Persistent        -- Script traits
```

### 13.5 Vision/Rendering Backend (10 classes)

```
CVisionEngine                             -- Vision engine singleton
CVisionViewport / ViewportNull            -- Rendering viewport
CVisionHmsZone                            -- Vision-HMS bridge
CVisionResourceFile / ResourceShaders     -- Resource management
CVisionShader                             -- Vision shader
CVisionVideoDecode                        -- Video decoder
CVisionVisual                             -- Vision visual
CVisPostFx_BloomHdr                       -- Bloom HDR post-FX
```

### 13.6 DirectX 11 Layer (3 classes)

```
CDx11RenderContext                        -- DX11 render context
CDx11Texture                              -- DX11 texture
CDx11Viewport                             -- DX11 viewport/swap chain
```

### 13.7 XML/JSON (10 classes)

```
CXmlDocument / Manager / Node             -- XML DOM
CXmlRpc / RpcEvent                        -- XML-RPC
CXmlScriptParsingManager                  -- Script parsing manager
CXmlScriptParsingDocumentJson / Xml       -- JSON/XML document
CXmlScriptParsingNodeJson / Xml           -- JSON/XML node
```

### 13.8 HTTP (4 classes)

```
CHttpClient_Internal                      -- HTTP client implementation
CHttpEvent                                -- HTTP event
CHttpManager                              -- HTTP manager
CHttpRequest                              -- HTTP request
```

### 13.9 ShootMania (12 classes)

```
CShootMania                               -- ShootMania game mode
CSmActionEvent / ActionMgr                -- Action system
CSmArena / ArenaClient / ArenaInterfaceUI / ArenaPhysics / ArenaRules / ArenaServer -- Arena
CSmMode                                   -- Game mode
CSmPlayer / PlayerDriver                  -- Player
```

### 13.10 Dedicated Server (4 classes)

```
CServerAdmin                              -- Server administration
CServerInfo                               -- Server information
CServerPlugin / PluginEvent               -- Server plugin system
```

### 13.11 TrackMania-Specific (4 classes)

```
CTrackMania                               -- TrackMania top-level
CTrackManiaIntro                          -- Intro sequence
CTrackManiaMenus                          -- TrackMania menus
CTrackManiaNetwork                        -- TrackMania networking
```

### 13.12 GameBox Application (2 classes)

```
CGbxApp                                   -- Base application
CGbxGame                                  -- Game application
```

### 13.13 Title/Pack Management (3 classes)

```
CTitleControl                             -- Title flow control
CTitleEdition                             -- Title edition/creation
CTitleFlow                                -- Title selection flow
```

### 13.14 User System (4 classes)

```
CUserPrestige                             -- User prestige data
CUserV2 / V2Manager / V2Profile           -- User V2 system
```

### 13.15 Game Logic Classes (~200+ classes)

These CGame* classes that don't fit neatly into the subsystems above:

**Playground (Gameplay Session)**:
```
CGamePlayground / Basic / Common          -- Gameplay session
CGamePlaygroundInterface                  -- Gameplay UI
CGamePlaygroundClientScriptAPI            -- Client script API
CGamePlaygroundScript                     -- Server gameplay script
CGamePlaygroundSpectating                 -- Spectator mode
CGamePlaygroundUIConfig / ConfigEvent / ConfigMgrScript -- UI configuration
CGamePlaygroundScore                      -- Player score
CGamePlaygroundControlMessages / Scores / SmPlayers -- Gameplay controls
CGamePlaygroundResources                  -- Gameplay resources
CGamePlaygroundModuleManagerClient / Server -- Module manager
CGamePlaygroundModuleClient/Server + 9 specializations each:
  Altimeter, Chrono, Hud, Inventory, PlayerState,
  ScoresTable, SpeedMeter, Store, TeamState, Throttle
CGamePlaygroundModuleConfig               -- Module config
CGameCtnPlayground                        -- CTN playground
```

**Game Mode/Module**:
```
CGameModeInfo / GameModeInfoScript        -- Game mode definition
CGameModuleModelCommon                    -- Module model base
CGameModuleMenuBase / Browser / Component / Components
CGameModuleMenuLadderRankings / Model / Page / PageModel / ServerBrowser
CGameModulePlaygroundChronoModel / HudModel / HudModelModule
CGameModulePlaygroundInventoryModel / Model
CGameModulePlaygroundPlayerStateComponentModel / GaugeModel / ListModel / StateModel
CGameModulePlaygroundScoresTableModel / SpeedMeterModel / StoreModel / TeamStateModel
CGameModuleScriptItem / ScriptStoreCategory / ScriptStoreItem
CGameModuleInventoryCategory
CGameModuleNodForPropertyList
CGameModuleEditorBase / EditorGraphEditionModel / EditorModel
CModulePlaygroundPlayerStateComponentModel
CHudModule
```

**ManiaApp/ManiaPlanet**:
```
CGameManiaApp / Browser / GraphWindow / Minimal / Playground / PlaygroundCommon
CGameManiaAppPlaygroundScriptEvent / ScriptEvent / Station / TextSet / Title
CGameManiaAppTitleLayerScriptHandler
CGameManiaNetResource
CGameManiaPlanet / MenuStations / Network / ScriptAPI
CGameManiaTitle / TitleControlScriptAPI / TitleCore / TitleEditionScriptAPI
CGameManiaplanetPlugin / Event / Interface / InterfaceEvent
```

**Player/Profile**:
```
CGamePlayer / PlayerInfo / PlayerProfile
CGamePlayerProfileChunk + 14 specializations
CGamePlayerProfileCompatibilityChunk
CGameArenaPlayer
CGameConnectedClient
CGameTeamProfile
CGameUserProfile / ProfileWrapper / ProfileWrapper_VehicleSettings
CGameUserManagerScript + 6 VoiceChatEvent specializations
CGameUserPrivilegesManagerScript / Script / Service
CGameUserVoiceChat / VoiceChatConfigScript
```

**Score/Leaderboard**:
```
CGameScoreAndLeaderBoardManager / Script
CGameScoreComputer_MultiAsyncLevel
CGameScoreLoaderAndSynchronizer
CGameScoreTask_* (21 classes)
CGameMapScoreManager / MapRecord / MultiAsyncLevel
CGameSeasonScoreManager / MapRecord / MultiAsyncLevel
CGameHighScore / HighScoreList
CGameLadderRanking / CtnChallengeAchievement / League / Player / Skill
```

**Networking (Game-level)**:
```
CGameNetwork / CGameCtnNetwork
CGameCtnNetForm / CGameCtnNetServerInfo
CGameNetDataDownload / FileTransfer / Form + 7 specializations
CGameNetOnlineMessage / PlayerInfo / ServerInfo
CGameMasterServer / PlayerOnlinePresence / Request / RichPresenceManager / etc.
CGameManiaPlanetNetwork
CTrackManiaNetwork
```

**Dialogs/Menus**:
```
CGameDialogs / DialogsScript / DialogsScriptEvent / DialogShootParams
CDialogsManager
CGameMenu / MenuColorEffect / MenuFrame / MenuScaleEffect / MenuScene / MenuSceneScriptManager
CMenuSceneManager
CGameCtnMenus / CGameCtnMenusManiaPlanet
CGameCtnMenuProfileScene
```

**Deep Links**:
```
CGameDirectLinkScript + 13 specializations:
  ArcadeServer, Garage, Home, Hotseat, JoinServer, JoinSession,
  NewMap, OfficialCampaign, Ranked, Royal, Splitscreen, TrackOfTheDay, WaitingPage
```

**Script Handlers/Entities**:
```
CGameScriptHandlerBrowser / ManiaPlanetPlugin / MediaTrack
CGameScriptHandlerPlaygroundInterface / _ReadOnly / ModuleInventory / ModuleStore / Station / TitleModuleMenu
CGameScriptMapBotPath / BotSpawn / Fondation / Landmark / ObjectAnchor / Sector / Spawn / VehicleAnchor / Waypoint
CGameScriptMgrTurret / Vehicle
CGameScriptNotificationsConsumer / Event / Notification / Producer / ProducerEvent
CGameScriptAction / ChatContact / ChatEvent / ChatHistory / etc.
CGameScriptPlayer / ServerAdmin / Turret / Vehicle / Entity
CGameScriptCloudManager / Debugger / DebuggerWorkspace
```

**Miscellaneous Game Classes**:
```
CGameAction / ActionFxPhy / ActionFxResources / ActionFxVis / ActionMaker / ActionModel
CGameAnimClipNod / AnimSet
CGameArmorModel / Avatar / BadgeScript / BadgeStickerSlots
CGameBuddy / CaptureZoneModel / CharacterModel
CGameClientTrackingScript
CGameCommonItemEntityModel / Edition
CGameControlCamera [counted in Camera]
CGameCoverFlowDesc
CGameCursorBlock / CursorItem
CGameDataFileManager / ManagerScript
CGameDisplaySettingsWrapper
CGameEditorBadgeScript
CGameEnvironmentManager
CGameFid
CGameGateModel / GatePhy / GateVis
CGameHapticDevice [counted in Input]
CGameHud3dMarkerConfig
CGameLeague / LeagueManager / ManagerBadgeScript
CGameMatchSettingsManager / ManagerScript / PlaylistItemScript / Script
CGameMgrAction / ActionFxPhy / AutoPilot / ShieldVis
CGameNod
CGameObjectItem / Model / Phy / PhyCompoundModel / PhyModel / Vis / VisModel
CGameOutlineBox
CGamePackCreatorScript / PackScript / RecipientScript / TitleInfoScript
CGamePixelArtModel
CGamePluginInterfacesScript
CGameRemoteBuffer / DataInfo / DataInfoFinds / DataInfoSearchs / Pool
CGameReplayObjectVisData [counted in Replay]
CGameResources / SaveLaunchedCheckpoints [counted in Replay]
CGameSaveLaunchedCheckpoints
CGameSessionArchive
CGameShield / ShootIconConfig / ShootIconSetting
CGameSkinnedNod / SlotPhy / SlotVis
CGameStation / Switcher / SwitcherModule / SystemOverlay
CGameTeleporterModel / Terminal
CGameTriggerGate / TriggerScreen / TriggerTeleport
CGameTurbineModel / TurretPhy / TurretVis
CGameUIAnimManager / UILayer
CGameVideoScriptManager / VideoScriptVideo
CGameWebServicesNotificationManagerScript / NotificationService / NotificationTask_*
CGameZoneManagerScript / ZoneTask_UpdateZoneList
CGhostManager [counted in Replay]
CGmHelper
CNodSystem
CNGameActionFxVis
CIPCRemoteControl
```

### 13.16 Miscellaneous Non-Prefix Classes (4 classes)

```
Clouds                                    -- Cloud instance manager
Cluster                                   -- Spatial clustering
ConnectionClient                          -- Network connection client
ConsoleClient                             -- Debug console client
```

### 13.17 Classic Archive (2 classes)

```
CClassicArchive                           -- GBX file reader/writer
CClassicBuffer                            -- Compressed data buffer
```

### 13.18 Other Standalone Classes

```
CCrystal                                  -- Crystal mesh geometry
CFastAlgo                                 -- CRC32, CRC64, MD5, SHA256, HMAC
CFastLinearAllocator                      -- Fast memory allocator
CFastString / CFastStringInt              -- Fast string types
CFuncLight                                -- Light function
CReplayInfo                               -- Replay file info
CVehicleSettings                          -- Vehicle settings
```

---

## 14. Cross-Cutting Concerns

### 14.1 Task/Result Pattern

Appears in 6+ subsystems with ~574 total task+result classes:
- `CNetNadeoServicesTask_*` (157)
- `CWebServicesTask_*` (108) + `CWebServicesTaskResult_*` (168)
- `CGameDataFileTask_*` (44)
- `CNetUbiServicesTask_*` (38)
- `CGameScoreTask_*` (21)
- `CNetMasterServerTask_*` (18)
- `CGameMasterServerTask_*` (12)
- `CGameUserTask_*` (10)
- `CNetUplayPCTask_*` (9)

### 14.2 Model/Physics/Visual (Phy/Vis/Model) Decomposition

Used consistently across subsystems:

| Entity | Model | Physics | Visual |
|--------|-------|---------|--------|
| Vehicle | `CGameVehicleModel` | `CGameVehiclePhy` | `CSceneVehicleVis` |
| Object | `CGameObjectModel` | `CGameObjectPhy` | `CGameObjectVis` |
| Gate | `CGameGateModel` | `CGameGatePhy` | `CGameGateVis` |
| Turret | -- | `CGameTurretPhy` | `CGameTurretVis` |
| Bullet | `CPlugBulletModel` | `CSceneBulletPhy` | `CSceneBulletVis` |
| Character | `CPlugCharPhyModel` | -- | `CPlugCharVisModel` |
| Gun | -- | `CSceneGunPhy` | `CSceneGunVis` |
| Wagon | -- | `CSceneWagonPhy` | `CSceneWagonVis` |
| Slot | -- | `CGameSlotPhy` | `CGameSlotVis` |

### 14.3 Script API Layer

Many subsystems expose ManiaScript APIs via `*Script*` or `*ScriptHandler*` classes:
- `CInputScriptManager` / `CInputScriptPad` / `CInputScriptEvent`
- `CAudioScriptManager` / `CAudioScriptMusic` / `CAudioScriptSound`
- `CGamePlaygroundScript` / `CGamePlaygroundClientScriptAPI`
- `CGameEditorPluginAPI` / `CGameEditorPluginMap`
- `CGameManialinkScriptHandler` / `CGameManialinkScriptEvent`
- `CGameGhostMgrScript` / `CGameGhostScript`
- `CGameScriptEntity` / `CGameScriptPlayer` / `CGameScriptVehicle`
- `CGameDataFileManagerScript`
- `CXmlScriptParsingManager`

### 14.4 Engine Singleton Pattern

12 engine singletons form the engine backbone:
```
CMwEngine -> CMwEngineMain, CGameEngine, CPlugEngine, CSceneEngine,
             CVisionEngine, CNetEngine, CInputEngine, CSystemEngine,
             CScriptEngine, CControlEngine, CAudioSourceEngine [UNCERTAIN]
```

---

## 15. Completeness Verification

### 15.1 Class Counts by Subsystem

| # | Subsystem | Count | Notes |
|---|-----------|------:|-------|
| 1 | Audio | 30 | CAudio* + CPlugSound* + CPlugMusic* + audio file handlers + COal |
| 2 | Input | 17 | CInput* + CGameHapticDevice |
| 3 | Camera | 22 | CGameControlCamera* + CPlugVehicleCamera* + editor cams + CHmsCamera |
| 4 | UI/Control | 70 | CControl* (39) + CGameManialink* (28) + CGameControlCard* (17) - overlaps |
| 5 | Editor | 71 | CGameEditor* + CGameCtnEditor* + CInteraction* + CGameModuleEditor* |
| 6 | Replay/Ghost | 14 | Ghost/Replay classes |
| 7 | Map/Block | 60 | Block, zone, item, anchor, map structure |
| 8 | Vehicle/Car | 27 | CPlugVehicle* + CSceneVehicle* + CGameVehicle* + train |
| 9 | Web Services | 713 | All task/result/service classes |
| 10 | Scene Graph | 93 | CHms* (41) + CScene* (52, minus vehicle/wagon counted elsewhere) |
| 11 | MediaTracker | 74 | CGameCtnMediaBlock* + clips + tracks + infrastructure |
| 12 | Plugin/Asset | 392 | CPlug* remainder (animation, bitmap, material, model, particle, etc.) |
| 13 | Remaining | 444 | Core, system, net core, script, vision, DX11, XML, HTTP, SM, server, TM, game logic, misc |
| -- | **Total** | **2,027** | **All Nadeo classes accounted for** |

### 15.2 Verification Notes

- Some classes appear in discussions of multiple subsystems but are counted in exactly one
- The "Remaining" category includes ~200+ CGame* logic classes that span multiple concerns
- Vehicle-related CScene* classes are counted under Vehicle, not Scene Graph
- Audio-related CPlug* classes are counted under Audio, not Plugin
- Camera-related CPlug* classes are counted under Camera, not Plugin
- The 4 non-C-prefix classes (Clouds, Cluster, ConnectionClient, ConsoleClient) are included in Remaining

### 15.3 Classes with [UNCERTAIN] Categorization

- `CAudioSourceEngine` -- Name suggests audio source type, but registered as an engine singleton
- `CControlEngine` -- May or may not inherit from `CMwEngine`
- `CGameHapticDevice` -- Cross-cuts Input and Vehicle subsystems
- `CGameCtnDecorationAudio` -- Cross-cuts Audio and Map subsystems
- `CInputReplay` -- Cross-cuts Input and Replay subsystems
- `CPlugEntRecordData` -- Cross-cuts Plugin and Replay subsystems
- `CHmsSolidVisCst_TmCar` -- Cross-cuts Scene Graph and Vehicle subsystems
- `CGameSaveLaunchedCheckpoints` -- Cross-cuts Replay and Map subsystems

---

## Appendix A: Subsystem Dependency Map

```
                    CMwNod (base)
                       |
            +----------+----------+
            |          |          |
        CMwEngine  CMwCmd*    CMwId
            |
    +-------+-------+-------+-------+
    |       |       |       |       |
 CSystem CGame   CPlug   CScene  CNet
 Engine  Engine  Engine  Engine  Engine
    |       |       |       |       |
    v       v       v       v       v
  Files   Logic   Assets  Render  Network
  Config  Editors Models  HMS     HTTP
  Pack    UI      Anim    FX      Nadeo
  Steam   Script  Bitmap  Light   Ubi
          Play-   Sound   Shadow  XMPP
          ground  Mesh    Vehicle
          Replay  Particle
          Ghost
```

**Key Inter-Subsystem Relationships**:
1. **Map -> Block -> Plugin**: Maps reference blocks, which reference CPlug* assets
2. **Replay -> Ghost -> Input**: Replays contain ghosts, which record input
3. **Editor -> Map -> Block**: Editors manipulate maps by placing/removing blocks
4. **MediaTracker -> Camera + Audio + Scene**: MT blocks control camera, play sounds, modify scene
5. **Vehicle -> Plugin + Scene**: Vehicle uses CPlug* physics/visual models rendered via CScene*
6. **Web Services -> Score + Ghost**: Online leaderboards require ghost upload/download
7. **UI -> Manialink -> Script**: UI controls are driven by ManiaScript via Manialink
8. **Scene -> HMS -> Vision -> DX11**: Rendering pipeline from scene graph to GPU

---

## 16. Content Creator Guide

This section documents the engine from the perspective of someone making custom items, maps, materials, and scripts for Trackmania 2020.

### 16.1 Item/Asset Pipeline: Blender to In-Game

**Evidence**: NadeoImporterMaterialLib.txt (208 materials), `09-game-files-analysis.md` (mesh pipeline strings), class_hierarchy.json (`CGameCtnImporter`, `CPlugSolid2Model`, `CPlugStaticObjectModel`)

The complete pipeline for getting a custom item from Blender into the game:

```
1. MODELING (Blender)
   +-- Create mesh geometry
   +-- Assign UV layers:
   |     UV Layer 0 = "BaseMaterial" (diffuse/PBR texture mapping)
   |     UV Layer 1 = "Lightmap" (baked lighting -- required for most materials)
   +-- Assign material names from NadeoImporterMaterialLib.txt
   +-- Export as .fbx

2. NADEOIMPORTER (Command-line tool)
   +-- Reads .fbx via FbxImporter (libfbxsdk.dll)
   +-- Geometry conversion: FbxGeometryConverter
   +-- Material lookup: matches material names against NadeoImporterMaterialLib.txt
   +-- Collision shape generation: CCrystal::ArchiveCrystal
   +-- LOD generation: Reduction40, ReductionRetextured, Remesh, Impostor
   +-- Lightmap UV validation: "Mesh has no LM UVs => abort" (WILL FAIL if missing)
   +-- Output: .Item.Gbx (CGameItemModel -> CPlugStaticObjectModel -> CPlugSolid2Model)

3. IN-GAME
   +-- CGameItemModel is the root item class
   +-- CPlugStaticObjectModel wraps the visual + collision mesh
   +-- CPlugSolid2Model is the primary mesh format (geometry, materials, LODs)
   +-- Items placed in editor as CGameCtnAnchoredObject instances
```

**NadeoImporter command-line flags** (from binary strings):
- `/LogMeshStats` -- Log mesh statistics during import
- `/MaterialList` -- List available materials
- `/MeshSkipPrefix` -- Skip mesh prefix during processing

**Critical requirement**: Every drivable surface mesh MUST have a Lightmap UV layer (layer 1). Without it, NadeoImporter will abort. The only materials that skip the lightmap layer are decals, some FX materials, and a few special cases (Grass uses Lightmap at layer 0 instead of BaseMaterial).

### 16.2 Material Assignment Process

When you name a material in Blender, NadeoImporter looks up that exact name in `NadeoImporterMaterialLib.txt`. The library file defines:

```
DLibrary(Stadium)           -- All TM2020 materials are in the "Stadium" library

  DMaterial(<MaterialName>)
    DSurfaceId(<SurfaceType>) -- Determines collision physics (friction, tire sound)
    DGameplayId(<GameplayType>) -- Gameplay effect (ALWAYS "None" for stock materials)
    DUvLayer(BaseMaterial, 0) -- UV channel 0 for diffuse/PBR texture
    DUvLayer(Lightmap, 1)     -- UV channel 1 for baked lighting
    DColor0()                 -- Optional: vertex color support
    DLinkFull(<MediaPath>)    -- Optional: links to external media (modifier materials)
```

**Why are all GameplayIds "None"?**

This is the single most important finding for content creators: **Gameplay effects (turbo, reactor boost, no-grip, slow motion, etc.) are NOT driven by materials.** Every one of the 208 stock materials has `DGameplayId(None)`. Gameplay effects come from:
- **Block types** (`CGameCtnBlockInfo` waypoint types: Start, Finish, Checkpoint)
- **Trigger zones** (via `CSceneTriggerAction`, `CGameTriggerGate`, `CGameTriggerTeleport`)
- **Gameplay surface effects** (strings: `TechGravityChange`, `TechGravityReset`)
- **The block/item model itself**, not its material

Materials ONLY control: visual appearance, collision physics (via SurfaceId), and tire sounds.

### 16.3 UV Layer Requirements by Material Type

| Material Category | UV Layer 0 | UV Layer 1 | DColor0 | Notes |
|---|---|---|---|---|
| Roads (RoadTech, RoadDirt, etc.) | BaseMaterial | Lightmap | No | Standard 2-layer setup |
| Platforms (PlatformTech, etc.) | BaseMaterial | Lightmap | No | Same as roads |
| Technics (Structure, Pylon, etc.) | BaseMaterial | Lightmap | No | Structural elements |
| Chrono digits | BaseMaterial | Lightmap | Yes | Vertex color for digit tinting |
| Decals (DecalCurbs, etc.) | BaseMaterial | -- | Yes | NO lightmap, projected onto surfaces |
| Grass | Lightmap | -- | No | UNUSUAL: Lightmap on layer 0, no BaseMaterial |
| SpeedometerLight_Dyna | BaseMaterial | -- | No | Dynamic (no lightmap) |
| ItemObstacle, ItemObstacleLight | BaseMaterial | -- | No | No lightmap (dynamic objects) |
| Custom* materials | Lightmap | -- | No | Use engine-provided textures |
| CustomMod* materials | BaseMaterial | Lightmap | Varies | User-moddable materials |
| Modifier FX (Boost_SpecialFX, etc.) | BaseMaterial | -- | No | Visual FX only |

---

## 17. Complete Material Reference (All 208 Materials)

**Source**: `NadeoImporterMaterialLib.txt`, verified line by line
**Library**: `DLibrary(Stadium)`

### 17.1 Road Materials (4)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| RoadTech | Asphalt | BaseMaterial | Lightmap | Main racing road surface |
| RoadBump | RoadSynthetic | BaseMaterial | Lightmap | Bumpy/synthetic road variant |
| RoadDirt | Dirt | BaseMaterial | Lightmap | Dirt/off-road surface |
| RoadIce | RoadIce | BaseMaterial | Lightmap | Ice road surface |

### 17.2 Platform Materials (3)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| PlatformTech | Asphalt | BaseMaterial | Lightmap | Platform asphalt surface |
| OpenTechBorders | Asphalt | BaseMaterial | Lightmap | Open platform edge borders |
| ItemInflatableFloor | Plastic | BaseMaterial | Lightmap | Inflatable floor surface |

### 17.3 Inflatable Materials (2)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| ItemInflatableMat | Plastic | BaseMaterial | Lightmap | Inflatable mat surface |
| ItemInflatableTube | Metal | BaseMaterial | Lightmap | Inflatable tube (metal physics) |

### 17.4 Track/Technics Materials (14)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| TrackBorders | Rubber | BaseMaterial | Lightmap | Track edge borders (bouncy) |
| TrackBordersOff | Rubber | BaseMaterial | Lightmap | Off-track borders |
| PoolBorders | Plastic | BaseMaterial | Lightmap | Pool/water area borders |
| WaterBorders | Plastic | BaseMaterial | Lightmap | Water edge borders |
| Underwater | Plastic | BaseMaterial | Lightmap | Underwater surfaces |
| Waterground | Concrete | BaseMaterial | Lightmap | Ground under water |
| TrackWall | Wood | BaseMaterial | Lightmap | Track wall panels |
| TrackWallClips | ResonantMetal | BaseMaterial | Lightmap | Track wall clip connectors |
| Technics | Metal | BaseMaterial | Lightmap | General technical surface |
| TechnicsSpecials | Metal | BaseMaterial | Lightmap | Special technical elements |
| TechnicsTrims | Metal | BaseMaterial | Lightmap | Technical trim pieces |
| Pylon | Metal | BaseMaterial | Lightmap | Support pylons/pillars |
| ScreenBack | RoadSynthetic | BaseMaterial | Lightmap | Screen backing surface |
| Structure | ResonantMetal | BaseMaterial | Lightmap | Structural framework |

### 17.5 Light Materials (2)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| LightSpot | MetalTrans | BaseMaterial | Lightmap | Light spot (semi-transparent) |
| LightSpot2 | MetalTrans | BaseMaterial | Lightmap | Light spot variant 2 |

### 17.6 Ad Screen Materials (6)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| Ad1x1Screen | MetalTrans | BaseMaterial | Lightmap | 1:1 aspect ratio ad screen |
| Ad2x1Screen | MetalTrans | BaseMaterial | Lightmap | 2:1 aspect ratio ad screen |
| Ad4x1Screen | MetalTrans | BaseMaterial | Lightmap | 4:1 wide ad banner |
| Ad16x9Screen | MetalTrans | BaseMaterial | Lightmap | 16:9 widescreen ad |
| 16x9ScreenOff | MetalTrans | BaseMaterial | Lightmap | 16:9 screen (off state) |
| Ad2x3Screen | MetalTrans | BaseMaterial | Lightmap | 2:3 portrait ad screen |

### 17.7 Racing Materials (7)

| Material | SurfaceId | UV0 | UV1 | DColor0 | Use |
|----------|-----------|-----|-----|---------|-----|
| RaceArchCheckpoint | Metal | BaseMaterial | Lightmap | No | Checkpoint arch structure |
| RaceArchFinish | Metal | BaseMaterial | Lightmap | No | Finish arch structure |
| RaceAd6x1 | MetalTrans | BaseMaterial | Lightmap | No | 6:1 race ad banner |
| RaceScreenStart | MetalTrans | BaseMaterial | Lightmap | No | Start screen |
| RaceScreenStartSmall | MetalTrans | BaseMaterial | Lightmap | No | Small start screen |
| SpeedometerLight_Dyna | Metal | BaseMaterial | -- | No | Dynamic speedometer light (NO lightmap) |
| Speedometer | Metal | BaseMaterial | Lightmap | No | Speedometer display |

### 17.8 Chrono Digit Materials (20)

All chrono materials: `SurfaceId(NotCollidable)`, `DColor0()` (vertex color support), `BaseMaterial` + `Lightmap`.

**Naming pattern**: `Chrono{Context}-{digit_position}`
- Contexts: (none), `Checkpoint`, `Finish`
- Digit positions: `10-00-00`, `01-00-00`, `00-10-00`, `00-01-00`, `00-00-10`, `00-00-01`, `00-00-001`
- Position meaning: `{tens_min}-{ones_min}-{tens_sec}-{ones_sec}-{tenths}-{hundredths}-{thousandths}`

| Context | Count | Materials |
|---------|-------|-----------|
| ChronoCheckpoint | 7 | ChronoCheckpoint-10-00-00 through ChronoCheckpoint-00-00-001 |
| ChronoFinish | 7 | ChronoFinish-10-00-00 through ChronoFinish-00-00-001 |
| Chrono (general) | 6 | Chrono-10-00-00 through Chrono-00-00-01 |

### 17.9 Decoration Materials (4)

| Material | SurfaceId | UV0 | UV1 | DColor0 | Use |
|----------|-----------|-----|-----|---------|-----|
| Grass | Grass | Lightmap | -- | No | Ground grass (ONLY Lightmap at layer 0!) |
| DecoHill | Grass | BaseMaterial | Lightmap | No | Hill decoration |
| DecoHill2 | Grass | BaseMaterial | Lightmap | No | Hill decoration variant |
| GlassWaterWall | NotCollidable | BaseMaterial | -- | Yes | Glass water wall (pass-through) |

### 17.10 Item Obstacle Materials (12)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| ItemPillar | Metal | BaseMaterial | Lightmap | Pillar (OBSOLETE, use ItemPillar2) |
| ItemPillar2 | Metal | BaseMaterial | Lightmap | Pillar v2 (current) |
| ItemTrackBarrier | Metal | BaseMaterial | Lightmap | Track barrier |
| ItemTrackBarrierB | Metal | BaseMaterial | Lightmap | Track barrier variant B |
| ItemTrackBarrierC | Metal | BaseMaterial | Lightmap | Track barrier variant C |
| ItemBorder | Metal | BaseMaterial | Lightmap | Item border/edge |
| ItemObstacle | Plastic | BaseMaterial | -- | Obstacle (NO lightmap, dynamic) |
| ItemRamp | Metal | BaseMaterial | Lightmap | Ramp surface |
| ItemObstacleLight | Plastic | BaseMaterial | -- | Light obstacle (NO lightmap) |
| ItemObstaclePusher | Plastic | BaseMaterial | Lightmap | Pusher obstacle |
| ScreenPusher | Metal | BaseMaterial | Lightmap | Pusher screen display |
| ItemSupportConnector | Metal | BaseMaterial | Lightmap | Support connector piece |

### 17.11 Item Support / Deco Materials (3)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| ItemSupportTube | Metal | BaseMaterial | Lightmap | Support tube element |
| ItemBase | Metal | BaseMaterial | Lightmap | Item base/pedestal |
| ItemCactus | Metal | BaseMaterial | Lightmap | Cactus decoration |

### 17.12 Item Lamp Materials (4)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| ItemLamp | Metal | BaseMaterial | Lightmap | Lamp body |
| ItemLampLight | Metal | BaseMaterial | Lightmap | Lamp light element |
| ItemLampLightB | Metal | BaseMaterial | Lightmap | Lamp light variant B |
| ItemLampLightC | Metal | BaseMaterial | Lightmap | Lamp light variant C |

### 17.13 Item Sign Materials (4)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| ItemRoadSign | Metal | BaseMaterial | Lightmap | Road sign |
| ItemCurveSign | Concrete | BaseMaterial | Lightmap | Curve warning sign |
| ItemCurveSignB | Concrete | BaseMaterial | Lightmap | Curve sign variant B |
| ItemCurveSignC | Concrete | BaseMaterial | Lightmap | Curve sign variant C |

### 17.14 Item Wrong Way Sign (1)

| Material | SurfaceId | UV0 | UV1 | Use |
|----------|-----------|-----|-----|-----|
| ItemWrongWaySign | Concrete | BaseMaterial | Lightmap | Wrong-way indicator sign |

### 17.15 Decal Materials -- Road Markings (5)

All: `SurfaceId(NotCollidable)`, `BaseMaterial` layer 0, `DColor0()`, NO lightmap.

| Material | Use |
|----------|-----|
| DecalCurbs | Curb edge markings |
| DecalMarks | General road markings |
| DecalMarksItems | Item-related road markings |
| DecalMarksRamp | Ramp markings |
| DecalMarksStart | Start line markings |

### 17.16 Decal Materials -- Platform (1)

| Material | Use |
|----------|-----|
| DecalPlatform | Platform surface decal |

### 17.17 Decal Materials -- Animated Obstacles (4)

All: `SurfaceId(NotCollidable)`, `BaseMaterial` layer 0, `DColor0()`.

| Material | Use |
|----------|-----|
| DecalObstaclePusher | Pusher obstacle decal |
| DecalObstacleTube | Tube obstacle decal |
| DecalObstacleTurnstileLeft | Left turnstile decal |
| DecalObstacleTurnstileRight | Right turnstile decal |

### 17.18 Decal Materials -- Sponsors and Branding (13)

All: `SurfaceId(NotCollidable)`, `BaseMaterial` layer 0, `DColor0()`.

| Material | Use |
|----------|-----|
| DecalPaintLogo4x1 | 4:1 logo paint |
| DecalPaint2Logo4x1 | 4:1 logo paint variant 2 |
| DecalPaintLogo8x1 | 8:1 logo paint |
| DecalPaint2Logo8x1 | 8:1 logo paint variant 2 |
| DecalPaintLogo8x1Colorize | 8:1 colorizable logo paint |
| DecalPaintSponsor4x1A | 4:1 sponsor A |
| DecalPaint2Sponsor4x1A | 4:1 sponsor A variant 2 |
| DecalPaintSponsor4x1B | 4:1 sponsor B |
| DecalPaint2Sponsor4x1B | 4:1 sponsor B variant 2 |
| DecalPaintSponsor4x1C | 4:1 sponsor C |
| DecalPaint2Sponsor4x1C | 4:1 sponsor C variant 2 |
| DecalPaintSponsor4x1D | 4:1 sponsor D (NOTE: uses `Color0()` not `DColor0()`, likely a typo in the file) |
| DecalPaint2Sponsor4x1D | 4:1 sponsor D variant 2 |

### 17.19 Decal Materials -- Sponsor Big (1)

| Material | Use |
|----------|-----|
| DecalSponsor1x1BigA | 1:1 large sponsor decal |

### 17.20 Special Turbo Materials (5)

| Material | SurfaceId | UV0 | UV1 | DColor0 | Use |
|----------|-----------|-----|-----|---------|-----|
| DecalSpecialTurbo | NotCollidable | BaseMaterial | -- | Yes | Turbo zone decal |
| SpecialSignTurbo | MetalTrans | BaseMaterial | Lightmap | No | Turbo zone sign |
| SpecialFXTurbo | NotCollidable | BaseMaterial | -- | No | Turbo FX visual |
| SpecialSignOff | MetalTrans | BaseMaterial | Lightmap | No | Turbo sign off state |
| TriggerFXTurbo | NotCollidable | BaseMaterial | -- | No | Turbo trigger zone FX |

### 17.21 Customizable Materials (14)

These use engine-provided textures. `Lightmap` at layer 0, NO `BaseMaterial`.

| Material | SurfaceId | Physics Feel |
|----------|-----------|-------------|
| CustomBricks | Pavement | Paved brick surface |
| CustomConcrete | Concrete | Concrete surface |
| CustomDirt | Dirt | Loose dirt |
| CustomGlass | Green | Glass-like (green surface physics) |
| CustomGrass | Green | Grass-like (green surface physics) |
| CustomIce | Ice | Icy surface |
| CustomMetal | Metal | Metallic surface |
| CustomMetalPainted | Metal | Painted metal |
| CustomPlastic | Rubber | Plastic/rubber surface |
| CustomPlasticShiny | Rubber | Shiny plastic/rubber |
| CustomRock | Rock | Rocky surface |
| CustomRoughWood | Wood | Rough wood surface |
| CustomSand | Sand | Sandy surface |
| CustomSnow | Snow | Snow surface |

### 17.22 Moddable Materials (14)

User-moddable materials with `BaseMaterial` + `Lightmap`. All have `SurfaceId(Concrete)` unless noted.

| Material | SurfaceId | DColor0 | Shader Type |
|----------|-----------|---------|-------------|
| CustomModAddSelfIllum | Concrete | Yes | Additive self-illumination |
| CustomModAddSelfIllum2 | Concrete | Yes | Additive self-illumination v2 |
| CustomModOpaque | Concrete | No | Opaque surface |
| CustomModOpaque2 | Concrete | No | Opaque surface v2 |
| CustomModColorize | Concrete | No | Colorizable surface |
| CustomModColorize2 | Concrete | No | Colorizable surface v2 |
| CustomModSelfIllum | Concrete | No | Self-illuminated |
| CustomModSelfIllum2 | Concrete | No | Self-illuminated v2 |
| CustomModSelfIllumSimple | Concrete | No | Simple self-illumination |
| CustomModSelfIllumSimple2 | Concrete | No | Simple self-illumination v2 |
| CustomModTrans | MetalTrans | No | Transparent/glass |
| CustomModTrans2 | MetalTrans | No | Transparent/glass v2 |
| CustomModDecal | NotCollidable | Yes | Decal projection (no collision) |
| CustomModDecal2 | NotCollidable | Yes | Decal projection v2 |

### 17.23 Modifier Materials (88 total, in 11 modifier groups)

Each modifier group has 4-5 visual sub-materials used by the block's appearance. All use `DLinkFull` to reference external media. The pattern is:

```
{Modifier}_Decal     -- NotCollidable, BaseMaterial + DColor0 (ground decal)
{Modifier}_Sign      -- MetalTrans, BaseMaterial + Lightmap (informational sign)
{Modifier}_SignOff   -- MetalTrans, BaseMaterial + Lightmap (sign in off state) [Boost only]
{Modifier}_SpecialFX -- NotCollidable, BaseMaterial only (visual FX particles)
{Modifier}_TriggerFX -- NotCollidable, BaseMaterial only (trigger zone visual)
```

**Special Modifier Groups** (40 materials):

| Modifier | Media Path | Gameplay Effect |
|----------|-----------|-----------------|
| Boost | Media\Modifier\Boost\ | Speed boost (Turbo) |
| Boost2 | Media\Modifier\Boost2\ | Super speed boost (Turbo2) |
| Cruise | Media\Modifier\Cruise\ | Cruise control |
| Fragile | Media\Modifier\Fragile\ | Fragile (break on contact) |
| NoBrake | Media\Modifier\NoBrake\ | Disable braking |
| NoEngine | Media\Modifier\NoEngine\ | Disable engine |
| NoSteering | Media\Modifier\NoSteering\ | Disable steering |
| Reset | Media\Modifier\Reset\ | Reset car |
| SlowMotion | Media\Modifier\SlowMotion\ | Slow motion effect |
| Turbo | Media\Modifier\Turbo\ | Turbo speed |
| Turbo2 | Media\Modifier\Turbo2\ | Super turbo |
| TurboRoulette | Media\Modifier\TurboRoulette\ | Random turbo level |

**Platform Modifier Groups** (28 materials):

| Modifier | Sub-materials | Surface Mapping |
|----------|--------------|-----------------|
| PlatformDirt | DecalPlatform, DecoHill, DecoHill2, OpenTechBorders, PlatformTech | Dirt/Sand surfaces |
| PlatformGrass | DecalPlatform, OpenTechBorders, PlatformTech | Green surfaces |
| PlatformIce | DecalPlatform, DecoHill, DecoHill2, OpenTechBorders, PlatformTech | RoadIce/Snow surfaces |
| PlatformPlastic | DecalPlatform, PlatformTech | RoadIce surface |

### 17.24 Complete Surface ID Physics Reference

| SurfaceId | Count | Grip Level | Tire Sound | Description |
|-----------|------:|------------|-----------|-------------|
| Asphalt | 3 | High | Road tire | Standard racing surface |
| Concrete | 19 | Medium-High | Hard | Structural concrete |
| Dirt | 4 | Low-Medium | Gravel | Off-road loose surface |
| Grass | 3 | Low | Soft swish | Natural ground |
| Green | 4 | Low | Vegetation | Green/vegetation surface |
| Ice | 1 | Very Low | Icy scrape | Ice surface |
| Metal | 26 | Medium | Metallic clank | General metallic surface |
| MetalTrans | 25 | Medium | Metallic (muted) | Semi-transparent metal/glass |
| NotCollidable | 79 | -- | -- | No collision (pass-through) |
| Pavement | 1 | Medium | Paved | Brick/paved surface |
| Plastic | 8 | Medium-Low | Plastic thud | Inflatable/obstacle |
| ResonantMetal | 2 | Medium | Resonant ring | Resonant metal (loud) |
| RoadIce | 5 | Very Low | Icy road | Road-type ice |
| RoadSynthetic | 2 | Medium | Synthetic hum | Synthetic road surface |
| Rock | 1 | Medium | Rocky crunch | Natural rock |
| Rubber | 4 | High | Rubber squeak | Bouncy rubber borders |
| Sand | 3 | Low | Sandy | Sand surface |
| Snow | 3 | Low | Crunchy | Snow surface |
| Wood | 2 | Medium | Woody thump | Wooden surface |

**Total: 208 materials across 19 surface IDs**

---

## 18. ManiaScript Language Reference

**Source**: Ghidra binary strings (`15-ghidra-research-findings.md`), `CScriptEngine__Run.c` decompilation
**Confidence**: VERIFIED (40+ token strings found in binary)

ManiaScript is the scripting language embedded in the ManiaPlanet/Trackmania engine. It is interpreted by `CScriptEngine` (confirmed by decompiled `CScriptEngine::Run` function at `0x140874270`).

### 18.1 Data Types (12 primitive types)

| Token | ManiaScript Type | Equivalent | Notes |
|-------|-----------------|------------|-------|
| `MANIASCRIPT_TYPE_VOID` | Void | -- | Function return type only |
| `MANIASCRIPT_TYPE_BOOLEAN` | Boolean | bool | `True` / `False` |
| `MANIASCRIPT_TYPE_INTEGER` | Integer | int32 | Signed integer |
| `MANIASCRIPT_TYPE_REAL` | Real | float | Floating-point number |
| `MANIASCRIPT_TYPE_TEXT` | Text | string | String type |
| `MANIASCRIPT_TYPE_VEC2` | Vec2 | float[2] | 2D vector `<x, y>` |
| `MANIASCRIPT_TYPE_VEC3` | Vec3 | float[3] | 3D vector `<x, y, z>` |
| `MANIASCRIPT_TYPE_INT2` | Int2 | int[2] | 2D integer vector `<x, y>` |
| `MANIASCRIPT_TYPE_INT3` | Int3 | int[3] | 3D integer vector `<x, y, z>` |
| `MANIASCRIPT_TYPE_ISO4` | Iso4 | float[12] | 3x3 rotation + vec3 position (48 bytes) |
| `MANIASCRIPT_TYPE_IDENT` | Ident | uint32 | Interned resource identifier (MwId) |
| `MANIASCRIPT_TYPE_CLASS` | Class | pointer | Reference to engine class |

### 18.2 Preprocessor Directives (7)

| Directive | Syntax | Purpose |
|-----------|--------|---------|
| `#RequireContext` | `#RequireContext CGameCtnApp` | Set required script execution context (type safety) |
| `#Setting` | `#Setting S_TimeLimit 300 as "Time limit"` | Declare a configurable setting variable |
| `#Struct` | `#Struct K_MyData { Integer Count; Text Name; }` | Define a struct type |
| `#Include` | `#Include "MathLib" as MathLib` | Include a library script |
| `#Extends` | `#Extends "Modes/TrackMania/Base.Script.txt"` | Extend a base script |
| `#Command` | `#Command MyCommand(Integer Param)` | Register a callable command |
| `#Const` | `#Const C_MaxPlayers 64` | Define a compile-time constant |

### 18.3 Coroutine Primitives (4)

ManiaScript has built-in cooperative multitasking:

| Keyword | Behavior | Use |
|---------|----------|-----|
| `sleep` | Pause execution for N milliseconds | `sleep(1000);` -- wait 1 second |
| `yield` | Yield to scheduler, resume next frame | `yield();` -- used in main loops |
| `wait` | Block until condition becomes true | `wait(Player.IsSpawned);` |
| `meanwhile` | Run block concurrently while parent continues | Concurrent execution blocks |

**Evidence**: Openplanet `EditorDeveloper/Main.as` uses `yield()` in its main loop (line 202), confirming the cooperative scheduling model.

### 18.4 Collection Operations (17)

All collection operations are dot-prefixed method calls on arrays/maps:

| Operation | Signature | Description |
|-----------|-----------|-------------|
| `.add` | `array.add(elem)` | Append element to end |
| `.addfirst` | `array.addfirst(elem)` | Insert at beginning |
| `.remove` | `array.remove(elem)` | Remove first occurrence |
| `.removekey` | `map.removekey(key)` | Remove by key |
| `.count` | `array.count` | Number of elements |
| `.clear` | `array.clear()` | Remove all elements |
| `.get` | `map.get(key)` | Get value by key |
| `.slice` | `array.slice(start, count)` | Extract sub-array |
| `.sort` | `array.sort()` | Sort ascending |
| `.sortrev` | `array.sortrev()` | Sort descending |
| `.sortkey` | `array.sortkey()` | Sort by key ascending |
| `.sortkeyrev` | `array.sortkeyrev()` | Sort by key descending |
| `.existskey` | `map.existskey(key)` | Check if key exists |
| `.existselem` | `array.existselem(elem)` | Check if element exists |
| `.containsonly` | `a.containsonly(b)` | Set: a is subset of b |
| `.containsoneof` | `a.containsoneof(b)` | Set: a intersects b |
| `.keyof` | `array.keyof(elem)` | Get key/index of element |

### 18.5 Serialization / Cloud Operations (3)

| Operation | Description |
|-----------|-------------|
| `.tojson` | Serialize collection/struct to JSON text |
| `.fromjson` | Deserialize JSON text into collection/struct |
| `.cloudrequestsave` | Request save to Nadeo cloud storage |
| `.cloudisready` | Check if cloud operation completed |

### 18.6 Debug Statements (4)

| Keyword | Purpose |
|---------|---------|
| `assert` | Debug assertion (crashes in debug builds) |
| `dump` | Print variable value to debug output |
| `dumptype` | Print variable type info to debug output |
| `log` | Log message to script console |

### 18.7 Tuning System (3)

| Keyword | Purpose |
|---------|---------|
| `TUNING_START` | Begin a tuning block (performance profiling) |
| `TUNING_END` | End a tuning block |
| `TUNING_MARK` | Mark a tuning checkpoint |

### 18.8 Lexer Token Types

The ManiaScript lexer recognizes these token categories:
- `WHITESPACE` -- Spaces, tabs, newlines
- `STRING` -- Quoted string literal
- `STRING_AND_CONCAT` -- String with concatenation operator
- `NATURAL` -- Integer literal
- `FLOAT` -- Floating-point literal
- `IDENT` -- Identifier (variable/function name)
- `COMMENT` -- Comment (// or /* */)
- `STRING_OPERATOR` -- String operation
- `CONCAT_AND_STRING` -- Concatenation + string
- `LOCAL_STRUCT` -- Local struct declaration

### 18.9 Script Engine Runtime

From `CScriptEngine__Run` decompilation (`0x140874270`):

1. Sets script context pointer at `param_1 + 0x60`
2. Initializes profiling label: `"CScriptEngine::Run(%s)"` with script name
3. Reads global tick counter (`DAT_141ffad50`) into execution context at `+0xc4`
4. Calls script execution function `FUN_1408d1ea0`
5. On error (`iVar2 == -1`): sets error flag at offset +400 of the script result object to value 2

---

## 19. Editor Capabilities Matrix

**Source**: class_hierarchy.json (2,027 classes), `EditorDeveloper/Main.as` (Openplanet plugin)
**Confidence**: VERIFIED

### 19.1 All Editor Types (18 editors)

| Editor Class | In-Game Access | What It Edits | Key Methods |
|---|---|---|---|
| `CGameCtnEditorFree` | Map Editor (main) | Block/item placement, terrain | `PlaceMacroBlock`, `BuildTerrain`, `AutoSave` |
| `CGameCtnEditorSimple` | Map Editor (simple mode) | Simplified block placement | Same as Free but restricted |
| `CGameCtnEditorPuzzle` | Map Editor (puzzle mode) | Block puzzles | Limited block set |
| `CGameEditorItem` | Item Editor | Custom items (.Item.Gbx) | `PrepareEditCrystal`, `PrepareEditMesh`, `PrepareEditShape` |
| `CGameEditorMesh` | Mesh Modeler | 3D meshes, voxel editing | `Interaction_DoVoxelPickDrag_*`, `InternalPickEdge/Face/Vertex` |
| `CGameEditorMaterial` | Material Editor | Material properties | Via mesh/item editors |
| `CGameEditorMediaTracker` | MediaTracker | Cutscenes, replays | Timeline-based block editing |
| `CGameEditorSkin` | Skin Editor | Car skins/paint | `CGameEditorSkinPluginAPI` |
| `CGameEditorManialink` | Manialink Editor | UI layouts (XML) | Manialink page editing |
| `CGameEditorScript` | Script Editor | ManiaScript code | Text editing with syntax highlighting |
| `CGameEditorVehicle` | Vehicle Editor | Vehicle tuning | (limited in TM2020) |
| `CGameEditorAction` | Action Editor | Gameplay actions | `CGameEditorActionScript` |
| `CGameEditorAnimChar` | Character Anim Editor | Character animations | `CGameEditorAnimChar_Interface` |
| `CGameEditorAnimClip` | Animation Clip Editor | Animation clips | Clip timeline editing |
| `CGameEditorBullet` | Bullet Editor | Projectile definitions | (ShootMania legacy) |
| `CGameEditorCustomBullet` | Custom Bullet Editor | Custom projectiles | (ShootMania legacy) |
| `CGameEditorModule` | Module Editor | HUD modules | `CGameModuleEditorBase` |
| `CGameEditorPacks` | Pack/Title Editor | Title packs | Package management |

### 19.2 Map Editor Architecture (CGameCtnEditorFree)

**Evidence**: Openplanet `EditorDeveloper/Main.as` directly accesses the editor's internal structure.

```
CGameCtnEditorFree
  +-- EditorInterface                    (CGameCtnEditorCommonInterface)
  |     +-- InterfaceScene.Mobils[0]     (CControlContainer -- root UI)
  |           +-- FrameDeveloperTools    (hidden Nadeo dev tools)
  |           +-- FrameEditTools         (main toolbar)
  |           |     +-- ButtonOffZone    (offzone button, hidden by default)
  |           +-- FrameLightTools        (lighting controls)
  +-- OrbitalCameraControl
  |     +-- m_ParamScrollAreaStart = 0.7
  |     +-- m_ParamScrollAreaMax = 0.98
  |     +-- m_CurrentHAngle / m_CurrentVAngle
  |     +-- m_TargetedPosition / m_CameraToTargetDistance
  +-- EditorHistory                      (CGameCtnEditorHistory -- undo/redo)
  +-- Plugin API                         (CGameEditorPluginMap)
        +-- CanPlaceBlock / PlaceBlock / RemoveBlock
        +-- CanPlaceGhostBlock / CanPlaceMacroblock
        +-- GetConnectResults
```

**Hidden features accessible via Openplanet**:
- `FrameDeveloperTools`: Nadeo's internal dev tools (hidden by default)
- `ButtonOffZone`: Off-zone placement button (hidden, requires binary patch to enable: NOP `0F 84 ?? ?? ?? ?? 4C 8D 45 ?? BA 13`)
- `FrameLightTools`: Light manipulation controls

### 19.3 Item Editor Capabilities (CGameEditorItem)

| Capability | Method | Description |
|---|---|---|
| Checkpoint designation | `CbBeforeIsCheckpoint` | Mark item as checkpoint |
| Finish designation | `CbBeforeIsFinish` | Mark item as finish |
| Start designation | `CbBeforeIsStart` | Mark item as start |
| StartFinish designation | `CbBeforeIsStartFinish` | Mark item as multilap start/finish |
| Crystal editing | `PrepareEditCrystal` | Edit collision/crystal mesh |
| Mesh editing | `PrepareEditMesh` | Edit visual mesh |
| Shape editing | `PrepareEditShape` | Edit placement shape |

### 19.4 Mesh Editor Capabilities (CGameEditorMesh)

| Capability | Method | Description |
|---|---|---|
| Create new mesh | `CreateNew` | Start with empty mesh |
| Import crystal | `ImportPlugCrystal*` | Import crystal geometry |
| Voxel pick-drag | `Interaction_DoVoxelPickDrag_*` | Voxel-based editing |
| Translation | `Interaction_DoTranslation` | Move geometry |
| Edge picking | `InternalPickEdge` | Select edges |
| Face picking | `InternalPickFace` | Select faces |
| Vertex picking | `InternalPickVertex` | Select vertices |
| Run editor | `RunEditor` | Enter editor main loop |

---

## 20. Complete MediaTracker Block Type Catalog

**Source**: class_hierarchy.json (all `CGameCtnMediaBlock*` classes)
**Confidence**: VERIFIED

MediaTracker is a timeline-based cutscene/replay editor. The hierarchy is: **ClipGroup -> Clip -> Track -> Block**. Each block controls one visual/audio/timing aspect at a given time range.

### 20.1 Camera Blocks (10)

| Block Class | In-Editor Name | Use | Replay Useful? |
|---|---|---|---|
| `CGameCtnMediaBlockCameraCustom` | Custom Camera | Keyframed camera path with full control | YES |
| `CGameCtnMediaBlockCameraGame` | Game Camera | Use in-game chase/cockpit camera | YES |
| `CGameCtnMediaBlockCameraOrbital` | Orbital Camera | Orbit around a point | YES |
| `CGameCtnMediaBlockCameraPath` | Camera Path | Follow a predefined path | YES |
| `CGameCtnMediaBlockCameraSimple` | Simple Camera | Fixed position camera | YES |
| `CGameCtnMediaBlockCameraEffect` | Camera Effect | Base camera post-effect | YES |
| `CGameCtnMediaBlockCameraEffectInertialTracking` | Inertial Tracking | Smooth inertial camera follow | YES |
| `CGameCtnMediaBlockCameraEffectScript` | Scripted Effect | ManiaScript-driven camera | YES |
| `CGameCtnMediaBlockCameraEffectShake` | Camera Shake | Impact/terrain camera shake | YES |
| `CGameCtnMediaBlockCamera` | Camera (base) | Abstract base, not directly used | -- |

### 20.2 Visual FX Blocks (11)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockFxBloom` | Bloom | Glow around bright areas |
| `CGameCtnMediaBlockBloomHdr` | HDR Bloom | High dynamic range bloom |
| `CGameCtnMediaBlockFxBlur` | Blur | Full-screen blur |
| `CGameCtnMediaBlockFxBlurDepth` | Depth Blur (DOF) | Depth-of-field bokeh |
| `CGameCtnMediaBlockFxBlurMotion` | Motion Blur | Directional motion blur |
| `CGameCtnMediaBlockFxCameraBlend` | Camera Blend | Smooth transition between cameras |
| `CGameCtnMediaBlockFxCameraMap` | Camera Map | Camera mapping/projection effect |
| `CGameCtnMediaBlockFxColors` | Color Adjustment | Brightness, contrast, saturation |
| `CGameCtnMediaBlockDOF` | Depth of Field | Alternative DOF block |
| `CGameCtnMediaBlockDirtyLens` | Dirty Lens | Simulated dirty lens overlay |
| `CGameCtnMediaBlockFx` | FX (base) | Abstract FX base |

### 20.3 Overlay / 2D Blocks (8)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockText` | Text Overlay | Display text on screen |
| `CGameCtnMediaBlockImage` | Image Overlay | Display image on screen |
| `CGameCtnMediaBlockDecal2d` | 2D Decal | Projected 2D decal |
| `CGameCtnMediaBlockTriangles` | Triangles | Triangle mesh overlay (base) |
| `CGameCtnMediaBlockTriangles2D` | 2D Triangles | 2D triangle mesh overlay |
| `CGameCtnMediaBlockTriangles3D` | 3D Triangles | 3D triangle mesh in world |
| `CGameCtnMediaBlockManialink` | Manialink | Manialink UI layer overlay |
| `CGameCtnMediaBlockInterface` | Interface | Game interface overlay |

### 20.4 Scene / Entity Blocks (6)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockEntity` | Entity | Place/animate an entity in the scene |
| `CGameCtnMediaBlockGhostTM` | TM Ghost | Display a car ghost (critical for replays) |
| `CGameCtnMediaBlockObject` | 3D Object | Place a 3D object in the scene |
| `CGameCtnMediaBlockScenery` | Scenery | Control scenery elements |
| `CGameCtnMediaBlockSkel` | Skeleton | Skeletal animation playback |
| `CGameCtnMediaBlockVehicleLight` | Vehicle Light | Control vehicle headlights/taillights |

### 20.5 Audio Blocks (2)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockSound` | Sound | Play a sound at a time/position |
| `CGameCtnMediaBlockMusicEffect` | Music Effect | Music volume/filter effect |

### 20.6 Environment Blocks (4)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockFog` | Fog | Control fog density/color/distance |
| `CGameCtnMediaBlockToneMapping` | Tone Mapping | HDR tone mapping parameters |
| `CGameCtnMediaBlockColorGrading` | Color Grading | LUT-based color grading |
| `CGameCtnMediaBlockLightmap` | Lightmap | Lightmap intensity/settings |

### 20.7 Timing Blocks (2)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockTime` | Time | Set game time at a point on timeline |
| `CGameCtnMediaBlockTimeSpeed` | Time Speed | Control playback speed (slow-mo/fast-forward) |

### 20.8 Transition Blocks (2)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockTransition` | Transition (base) | Abstract transition |
| `CGameCtnMediaBlockTransitionFade` | Fade | Fade to/from black/white |

### 20.9 Coloring Blocks (2)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockColoringBase` | Base Coloring | Base object color override |
| `CGameCtnMediaBlockColoringCapturable` | Capturable Coloring | Capturable zone color |

### 20.10 Gameplay Blocks (3)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockSpectators` | Spectators | Control spectator crowd |
| `CGameCtnMediaBlockOpponentVisibility` | Opponent Visibility | Show/hide opponents |
| `CGameCtnMediaBlockTrails` | Trails | Vehicle trail/streak effects |

### 20.11 Special Blocks (6)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlock3dStereo` | 3D Stereo | Stereoscopic 3D settings |
| `CGameCtnMediaBlockUi` | UI | UI display control |
| `CGameCtnMediaBlockShoot` | Screenshot | Trigger screenshot capture |
| `CGameCtnMediaBlockTurret` | Turret | Turret camera/control |
| `CGameCtnMediaBlockEditor` | Editor View | Editor perspective block |
| `CGameCtnMediaBlockEditorDecal2d` | Editor Decal 2D | Editor-only 2D decal |

### 20.12 Editor-Only Blocks (1)

| Block Class | Effect | Use |
|---|---|---|
| `CGameCtnMediaBlockEditorTriangles` | Editor Triangles | Editor-only triangle overlay |

### 20.13 Deprecated Blocks (3)

| Block Class | Status |
|---|---|
| `CGameCtnMediaBlockBulletFx_Deprecated` | Removed (ShootMania) |
| `CGameCtnMediaBlockCharVis_Deprecated` | Removed (character visual) |
| `CGameCtnMediaBlockEvent_deprecated` | Removed (event trigger) |

### 20.14 Replay Editing Essentials

For creating replay edits, these blocks are most useful:

1. **CGameCtnMediaBlockGhostTM** -- Display car ghosts (the car itself)
2. **CGameCtnMediaBlockCameraCustom** -- Keyframed camera for cinematic shots
3. **CGameCtnMediaBlockCameraGame** -- In-game camera for driving perspective
4. **CGameCtnMediaBlockTimeSpeed** -- Slow-motion for dramatic moments
5. **CGameCtnMediaBlockDOF** / **FxBlurDepth** -- Depth of field for focus
6. **CGameCtnMediaBlockColorGrading** -- Color grading for mood
7. **CGameCtnMediaBlockTransitionFade** -- Fade transitions between cuts
8. **CGameCtnMediaBlockText** -- Text overlays for titles/credits
9. **CGameCtnMediaBlockSound** -- Sound effects
10. **CGameCtnMediaBlockFog** -- Atmospheric fog

---

## 21. Block Naming Convention Decoder

**Source**: Block names from game files, `09-game-files-analysis.md` block analysis, class_hierarchy.json

### 21.1 Block Name Structure

TM2020 Stadium block names follow this hierarchical pattern:

```
{Environment}{Category}{Shape}{Variant}{Modifier}
```

**Environment prefix**: Always `Stadium` for TM2020.

**Common categories**:
- `Road` -- Drivable road surface
- `Platform` -- Flat platform surface
- `DecoWall` / `DecoHill` -- Decorative elements
- `Pillar` -- Support pillars
- `Gate` -- Start/Finish/Checkpoint gates
- `Water` -- Water elements
- `Grass` -- Grass terrain

**Shape descriptors**:
- `Straight` -- Straight segment
- `Curve` / `Turn` -- Curved segment
- `Slope` / `Tilt` -- Inclined surface
- `Cross` -- Intersection/crossroad
- `DiagLeft` / `DiagRight` -- Diagonal pieces
- `Chicane` -- S-curve
- `SlopeBase` / `SlopeEnd` -- Slope transition pieces

**Variant suffixes**:
- `x2` / `x3` / `x4` -- Width multiplier
- `Narrow` -- Narrower variant
- `Mirror` -- Mirrored version
- `In` / `Out` -- Border direction (inward/outward)

### 21.2 Coordinate System

**Evidence**: Openplanet rendering code (`distance / 32.0f`), camera system Y-up convention

| Property | Value |
|----------|-------|
| Grid unit | **32 meters** per block |
| Y-axis | **UP** |
| Z-axis | Forward |
| Coordinate system | **Left-handed** (consistent with D3D11) |
| Block position | Integer grid coordinates (x, y, z) |
| Block height unit | 8 meters (4 sub-grid positions per block height) |

### 21.3 Block Rotation System

Blocks can be placed in 4 cardinal orientations:

| Direction | Value | Facing |
|-----------|-------|--------|
| North | 0 | +Z |
| East | 1 | +X |
| South | 2 | -Z |
| West | 3 | -X |

### 21.4 Block Placement Modes

| Mode | Snapping | Description |
|------|----------|-------------|
| Grid placement | 32m grid | Standard block placement, snaps to integer coordinates |
| Free placement | No grid | Items/blocks placed at arbitrary positions (CGameCtnAnchoredObject) |
| Ghost blocks | 32m grid | Overlapping blocks (no collision validation) |
| Macroblock | 32m grid | Multi-block templates (CGameCtnMacroBlockInfo) |

### 21.5 Block Connectivity (Clip System)

**Evidence**: `CGameCtnBlockInfoClip`, `CGameCtnBlockInfoClipHorizontal`, `CGameCtnBlockInfoClipVertical`, `CBlockClip`, `CBlockClipList`

Blocks connect to adjacent blocks via the **clip system**:

```
CGameCtnBlockInfoClip          -- Base clip connection type
  +-- CGameCtnBlockInfoClipHorizontal  -- Connects blocks side-by-side
  +-- CGameCtnBlockInfoClipVertical    -- Connects blocks vertically (stacking)
```

- Clips define connection points on block faces
- The editor validates connectivity via `CGameEditorPluginMapConnectResults` / `GetConnectResults`
- Blocks with matching clip types on adjacent faces connect seamlessly
- Invalid connections produce visible seams or "red" invalid placement indicators

### 21.6 Waypoint Types

**Evidence**: Binary strings `|BlockInfo|Checkpoint`, `|BlockInfo|Finish`, `|BlockInfo|Start`, `|BlockInfo|Start/Finish`; class `CGameWaypointSpecialProperty`, `CAnchorData.EWaypointType`

| Waypoint Type | Purpose | Required? |
|---|---|---|
| Start | Race start spawn position | Yes (exactly 1) |
| Finish | Race finish line | Yes (1 for point-to-point) |
| Checkpoint | Intermediate checkpoint | No (but standard for validation) |
| StartFinish | Combined start/finish for multilap | Yes (1 for multilap maps) |

### 21.7 Block Type Hierarchy

```
CGameCtnBlockInfo                    -- Base block definition
  +-- CGameCtnBlockInfoClassic       -- Standard grid-snapped block
  +-- CGameCtnBlockInfoClip          -- Clip connection block
  |     +-- ClipHorizontal           -- Horizontal clip
  |     +-- ClipVertical             -- Vertical clip
  +-- CGameCtnBlockInfoFlat          -- Flat terrain
  +-- CGameCtnBlockInfoFrontier      -- Zone boundary
  +-- CGameCtnBlockInfoMobil         -- Moving/animated block
  +-- CGameCtnBlockInfoPylon         -- Auto-generated pylon/pillar
  +-- CGameCtnBlockInfoRectAsym      -- Rectangular asymmetric
  +-- CGameCtnBlockInfoRoad          -- Road block
  +-- CGameCtnBlockInfoSlope         -- Sloped surface
  +-- CGameCtnBlockInfoTransition    -- Terrain transition
```

Each block type has **variants** for ground-level and elevated placement:
- `CGameCtnBlockInfoVariantGround` -- Placed at ground level
- `CGameCtnBlockInfoVariantAir` -- Placed elevated (needs pylons)

---

## 22. Audio System for Custom Content

**Source**: class_hierarchy.json (30 audio classes), `15-ghidra-research-findings.md` (OpenAL init), `19-openplanet-intelligence.md` (audio config)

### 22.1 Sound Types Available

| Sound Category | Source Class | Resource Class | Description |
|---|---|---|---|
| Engine sounds | `CAudioSourceEngine` | `CPlugSoundEngine` / `CPlugSoundEngine2` | Vehicle motor sounds with RPM mapping |
| Surface sounds | `CAudioSourceSurface` | `CPlugSoundSurface` | Tire-on-surface sounds (per SurfaceId) |
| Ambient mood | `CAudioSourceMood` | `CPlugSoundMood` | Atmospheric ambient loops |
| Music | `CAudioSourceMusic` | `CPlugMusic` | Background music tracks |
| Gauge sounds | `CAudioSourceGauge` | `CPlugSoundGauge` | Speed/RPM gauge UI sounds |
| Multi-layer | `CAudioSourceMulti` | `CPlugSoundMulti` | Layered composite sounds |
| Located sound | -- | `CPlugLocatedSound` | 3D-positioned sound in world |
| Video sound | -- | `CPlugSoundVideo` | Sound attached to video playback |

### 22.2 Audio File Formats

| Format | Handler Class | Use |
|--------|--------------|-----|
| WAV | `CPlugFileWav` | Uncompressed audio |
| OGG Vorbis | `CPlugFileOggVorbis` | Compressed audio (primary format) |
| Generic SND | `CPlugFileSnd` | Generic sound container |
| Generated SND | `CPlugFileSndGen` | Procedurally generated sound |
| Motor profiles | `CPlugFileAudioMotors` | Engine sound RPM profile data |

### 22.3 How Sounds Attach to Items

Items do not directly reference audio. Sound is driven by:

1. **Surface contact**: `CAudioSourceSurface` + `CPlugSoundSurface` plays sounds based on the `SurfaceId` of the material the wheel is touching. Each of the 19 surface IDs has a corresponding tire sound.

2. **Spatial zones**: `CAudioZone` + `CAudioZoneSource` define 3D regions where ambient audio plays. Items placed in zones inherit the zone's audio.

3. **Engine sounds**: `CAudioSourceEngine` plays RPM-mapped engine audio that varies with `CSceneVehicleVisState.RPM` and gear.

4. **Decoration audio**: `CGameCtnDecorationAudio` defines map-wide audio settings (ambient mood, music).

### 22.4 Audio Configuration Parameters

**Evidence**: Default.json configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| `AudioDevice_Oal` | string | OpenAL device name |
| `AudioSoundVolume` | float (0-1) | Master SFX volume |
| `AudioSoundLimit_Scene` | float (0-1) | Scene sound limit |
| `AudioSoundLimit_Ui` | float (0-1) | UI sound limit |
| `AudioMusicVolume` | float (0-1) | Music volume |
| `AudioGlobalQuality` | string | Audio quality (`"normal"`) |
| `AudioAllowEFX` | bool | Environmental audio effects (reverb) |
| `AudioAllowHRTF` | bool | Head-related transfer function (3D audio) |
| `AudioDisableDoppler` | bool | Doppler effect toggle |

**Backend**: OpenAL via `OpenAL64_bundled.dll` (confirmed by Ghidra decompilation of `COalAudioPort::InitImplem`). EFX (Environmental effects) is optional and checked at init time.

---

## 23. Skins and Customization System

**Source**: class_hierarchy.json, web services task classes

### 23.1 Skin-Related Classes

| Class | Purpose |
|---|---|
| `CGameEditorSkin` | Skin/paint editor |
| `CGameEditorSkinPluginAPI` | Skin editor scripting API |
| `CGameCtnBlockSkin` | Block appearance skin |
| `CPlugGameSkin` | Game skin resource |
| `CPlugGameSkinAndFolder` | Skin + folder reference |
| `CPlugVehicleVisStyles` | Vehicle visual style collection |
| `CPlugVehicleVisStyleRandomGroup` | Random style selection |
| `CPlugVehicleVisModel` | Vehicle visual model |
| `CPlugVehicleMaterialGroup` | Vehicle material group |
| `CGameSkinnedNod` | Generic skinned node |
| `CGameSlotPhy` / `CGameSlotVis` | Slot physics/visuals (attachment points) |

### 23.2 Player Identity Classes

| Class | Purpose |
|---|---|
| `CGameNetPlayerInfo` | Network player info (name, skin, etc.) |
| `CGamePlayerInfo` | Local player info |
| `CGamePlayerProfile` | Player profile data |
| `CGamePlayerProfileChunk` (14 specializations) | Profile data chunks |
| `CGameConnectedClient` | Connected client data |
| `CGameArenaPlayer` | Arena player instance |
| `CGameAvatar` | Player avatar |
| `CGameBadgeScript` | Badge (club tag) script API |
| `CGameBadgeStickerSlots` | Badge sticker placement slots |

### 23.3 Skin Web Services

| Task Class | Operation |
|---|---|
| `CGameDataFileTask_Skin_NadeoServices_Get` | Download a skin |
| `CGameDataFileTask_Skin_NadeoServices_GetAccountList` | List account skins |
| `CGameDataFileTask_Skin_NadeoServices_GetList` | List available skins |
| `CGameDataFileTask_Skin_NadeoServices_Set` | Upload/set a skin |
| `CGameDataFileTask_AccountSkin_NadeoServices_AddFavorite` | Favorite a skin |
| `CGameDataFileTask_AccountSkin_NadeoServices_GetFavoriteList` | List favorite skins |
| `CGameDataFileTask_AccountSkin_NadeoServices_RemoveFavorite` | Unfavorite a skin |

### 23.4 Vehicle Customization

The vehicle visual system separates concerns:

```
CGameVehicleModel
  +-- CPlugVehicleVisModel           -- Base visual model (mesh + textures)
  |     +-- CPlugVehicleVisModelShared -- Shared visual data (LODs)
  |     +-- CPlugVehicleVisGeomModel   -- Geometry (mesh data)
  +-- CPlugVehicleVisStyles          -- Available paint/skin styles
  |     +-- CPlugVehicleVisStyleRandomGroup -- Random selection pool
  +-- CPlugVehicleMaterialGroup      -- Material assignments
  +-- CPlugVehicleVisEmitterModel    -- Particle emitters (exhaust, sparks)
```

**Prestige system**: `CUserPrestige`, `CWebServicesPrestigeService`, `CHmsSolidVisCst_TmCar.SPrestige` -- prestige skins are special visual styles earned through gameplay progression.

### 23.5 Club Tags (Badges)

Club tag customization uses:
- `CGameBadgeScript` -- Script API for badge manipulation
- `CGameBadgeStickerSlots` -- Sticker placement on the badge
- `CGameManagerBadgeScript` -- Badge management API
- `CWebServicesTask_GetUserClubTag*` -- Club tag web service queries

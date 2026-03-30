# UI/ManiaLink System Reference

**Source**: `class_hierarchy.json` (2,027 classes), `13-subsystem-class-map.md` (Section 4), `19-openplanet-intelligence.md`, `29-community-knowledge.md`, Openplanet `DefaultStyle.toml`, ManiaLink community documentation
**Confidence**: MIXED -- Native control hierarchy is VERIFIED from binary RTTI; ManiaLink XML format is community-documented (HIGH confidence); scripting API is VERIFIED via Openplanet; HUD module system is VERIFIED from class hierarchy
**Date**: 2026-03-27

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [CControl Class Hierarchy (Native Controls)](#2-ccontrol-class-hierarchy-native-controls)
3. [CGameManialink Class Hierarchy (Script-Exposed Controls)](#3-cgamemanialink-class-hierarchy-script-exposed-controls)
4. [ManiaLink XML Format](#4-manialink-xml-format)
5. [Layout System (Positioning, Sizing, Anchoring)](#5-layout-system-positioning-sizing-anchoring)
6. [Style System](#6-style-system)
7. [Built-in Controls Reference](#7-built-in-controls-reference)
8. [ManiaLink Scripting](#8-manialink-scripting)
9. [ManiaApp System (Application Layer)](#9-maniaapp-system-application-layer)
10. [HUD Elements and Playground Modules](#10-hud-elements-and-playground-modules)
11. [Game Control Cards](#11-game-control-cards)
12. [UI Effect and Animation System](#12-ui-effect-and-animation-system)
13. [Openplanet DefaultStyle (Modern UI Theme)](#13-openplanet-defaultstyle-modern-ui-theme)
14. [Browser HTML/CSS Equivalents](#14-browser-htmlcss-equivalents)
15. [Unknowns and Gaps](#15-unknowns-and-gaps)

---

## 1. Architecture Overview

The Trackmania 2020 UI system operates on three layers:

```
Layer 3: ManiaLink XML + ManiaScript     (Content creators / Game modes)
         |
         v  [parsed by CGameManialinkManager]
Layer 2: CGameManialink* classes          (Script-accessible wrappers)
         |
         v  [wraps underlying native controls]
Layer 1: CControl* classes                (Native C++ UI controls, Engine 0x07)
         |
         v  [rendered by CControlEngine]
Layer 0: CHms* / CDx11*                   (GPU rendering)
```

### Key Singletons

| Class | Role |
|-------|------|
| `CControlEngine` | Native UI update pipeline (layout, effects, focus, values) |
| `CGameManialinkManager` | Parses ManiaLink XML, manages pages |
| `CGameManialinkBrowser` | Navigates between ManiaLink pages |
| `CGameManialinkAnimManager` | Manages UI animations with easing |
| `CControlStyleSheet` | Style collection for native controls |
| `CGameManialinkStylesheet` | ManiaLink CSS-like styles |

### Engine Assignment

The UI/Control system spans two engine IDs:

| Engine ID | Namespace | Classes | Description |
|-----------|-----------|---------|-------------|
| `0x07` | ENGINE_CONTROL | 39 `CControl*` classes | Native UI controls |
| `0x03` | ENGINE_GAME | 31 `CGameManialink*` classes | Script-exposed ManiaLink wrappers |

**Total UI classes**: 70 (39 native + 31 ManiaLink)

---

## 2. CControl Class Hierarchy (Native Controls)

**Source**: Binary RTTI extraction (class_hierarchy.json)
**Confidence**: VERIFIED

These are the C++ engine controls that render on screen. They are not directly accessible from ManiaScript; instead, `CGameManialink*` wrappers expose them to scripts.

### 2.1 Complete Hierarchy (39 classes)

```
CMwNod
  +-- CControlBase                        -- Base UI control (all visual controls inherit)
  |     +-- CControlButton                -- Clickable button
  |     +-- CControlLabel                 -- Text label (static text display)
  |     +-- CControlText                  -- Text display (rich text)
  |     +-- CControlTextEdition           -- Text input field (editable text)
  |     +-- CControlEntry                 -- Entry/input control (single-line input)
  |     +-- CControlEnum                  -- Dropdown/enum selector
  |     +-- CControlSlider                -- Slider control (continuous value)
  |     +-- CControlQuad                  -- Quad/image display (rectangle with texture or color)
  |     +-- CControlGrid                  -- Grid layout container
  |     +-- CControlGraph                 -- Graph/chart display (line charts)
  |     +-- CControlListCard              -- Card list item
  |     +-- CControlListItem              -- List item
  |     +-- CControlPager                 -- Pagination control
  |     +-- CControlMediaPlayer           -- Video player control
  |     +-- CControlMiniMap               -- Mini-map display
  |     +-- CControlColorChooser          -- Color picker (v1)
  |     +-- CControlColorChooser2         -- Color picker (v2, improved)
  |     +-- CControlCamera                -- Camera preview widget
  |     +-- CControlScriptConsole         -- Script debug console
  |     +-- CControlScriptEditor          -- Script editor (syntax highlighting)
  |     +-- CControlTimeLine2             -- Timeline control (MediaTracker)
  |     +-- CControlUiRange               -- Range control (min/max slider)
  |     +-- CControlUrlLinks              -- URL link handler (clickable links)
  +-- CControlContainer                   -- Control grouping (holds child controls)
  +-- CControlFrame                       -- Frame container (visible/styled container)
  |     +-- CControlFrameAnimated         -- Animated frame (transition effects)
  |     +-- CControlFrameStyled           -- Styled frame (themed container)
  +-- CControlEffect                      -- UI effect base (visual transitions)
  |     +-- CControlEffectCombined        -- Combined effects (chains multiple effects)
  |     +-- CControlEffectMaster          -- Master effect controller
  |     +-- CControlEffectMotion          -- Motion effect (translate/rotate)
  |     +-- CControlEffectMoveFrame       -- Frame movement effect
  |     +-- CControlEffectSimi            -- Similarity transform effect (scale+rotate+translate)
  +-- CControlLayout                      -- Layout manager (positioning algorithm)
  +-- CControlStyle                       -- Individual control style definition
  +-- CControlStyleSheet                  -- Style collection (maps IDs to styles)
  +-- CControlSimi2                       -- 2D similarity transform (scale/rotate/translate)
  +-- CControlEngine                      -- UI engine singleton (update pipeline)
```

### 2.2 CControlEngine Update Pipeline

The `CControlEngine` singleton drives the per-frame UI update through 7 methods:

| Method | Phase | Purpose |
|--------|-------|---------|
| `ContainersDoLayout` | Layout | Recompute positions and sizes of all containers |
| `ContainersEffects` | Effects | Apply visual effects to containers |
| `ContainersFocus` | Focus | Update focus state for containers |
| `ContainersValues` | Values | Propagate data values to container children |
| `ControlsEffects` | Effects | Apply visual effects to individual controls |
| `ControlsFocus` | Focus | Update focus/hover state for controls |
| `ControlsValues` | Values | Update control display values |

### 2.3 CControlTextEdition Methods

| Method | Purpose |
|--------|---------|
| `GenerateTree` | Build the internal text layout tree |
| `UpdateControlBoundingBox` | Recalculate bounding box after text change |
| `UpdateDisplaylinesNear` | Update visible lines near cursor |
| `UpdateFormattedTextNear` | Update formatted/styled text near cursor |

### 2.4 CControlEffectSimi

Has a nested `SKeyVal` struct for keyframe animation data. This drives the ManiaLink animation system at the native level.

---

## 3. CGameManialink Class Hierarchy (Script-Exposed Controls)

**Source**: Binary RTTI extraction (class_hierarchy.json)
**Confidence**: VERIFIED

These classes wrap native `CControl*` instances and expose them to ManiaScript. Each has an `UpdateControl` method called per-frame.

### 3.1 Complete Hierarchy (31 classes)

```
CMwNod
  +-- CGameManialinkControl               -- Base ManiaLink control (script API)
  |     +-- CGameManialinkArrow           -- Arrow/direction indicator
  |     +-- CGameManialinkCamera          -- Camera view embedded in UI
  |     +-- CGameManialinkColorChooser    -- Color picker widget
  |     +-- CGameManialinkEntry           -- Text entry (single-line input)
  |     +-- CGameManialinkFileEntry       -- File chooser (local file browser)
  |     +-- CGameManialinkFrame           -- Frame container (groups children)
  |     +-- CGameManialinkGauge           -- Gauge/progress bar
  |     +-- CGameManialinkGraph           -- Graph display (line charts)
  |     +-- CGameManialinkLabel           -- Text label
  |     +-- CGameManialinkMediaPlayer     -- Video player
  |     +-- CGameManialinkMiniMap         -- Mini-map
  |     +-- CGameManialinkOldTable        -- Legacy table (deprecated)
  |     +-- CGameManialinkPlayerList      -- Player list
  |     +-- CGameManialinkQuad            -- Image/quad (rectangle)
  |     +-- CGameManialinkSlider          -- Slider
  |     +-- CGameManialinkTextEdit        -- Multi-line text editor
  |     +-- CGameManialinkTimeLine        -- Timeline control
  +-- CGameManialinkGraphCurve            -- Graph curve data (attached to Graph)
  +-- CGameManialinkPage                  -- Page container (root of ManiaLink document)
  +-- CGameManialinkManager               -- ManiaLink system manager (parses XML)
  +-- CGameManialinkBrowser               -- ManiaLink page browser/navigator
  +-- CGameManialinkAnimManager           -- UI animation manager (easing functions)
  +-- CGameManialinkStylesheet            -- ManiaLink CSS-like style definitions
  +-- CGameManialinkScriptEvent           -- UI script event (MouseClick, etc.)
  +-- CGameManialinkScriptHandler         -- Script event handler (processes events)
  +-- CGameManialinkScriptHandler_ReadOnly -- Read-only script handler
  +-- CGameManialinkNavigationScriptHandler -- Navigation script handler
  +-- CGameManialink3dMood                -- 3D scene mood settings in UI
  +-- CGameManialink3dStyle               -- 3D scene style in UI
  +-- CGameManialink3dWorld               -- 3D scene world embedded in UI
```

### 3.2 Native-to-Script Control Mapping

| Native (CControl*) | Script (CGameManialink*) | ManiaLink XML | ManiaScript Cast |
|---------------------|--------------------------|---------------|------------------|
| `CControlQuad` | `CGameManialinkQuad` | `<quad>` | `CMlQuad` |
| `CControlLabel` | `CGameManialinkLabel` | `<label>` | `CMlLabel` |
| `CControlEntry` | `CGameManialinkEntry` | `<entry>` | `CMlEntry` |
| `CControlTextEdition` | `CGameManialinkTextEdit` | `<textedit>` | `CMlTextEdit` |
| `CControlFrame` | `CGameManialinkFrame` | `<frame>` | `CMlFrame` |
| `CControlGraph` | `CGameManialinkGraph` | `<graph>` | `CMlGraph` |
| `CControlSlider` | `CGameManialinkSlider` | `<gauge>` | `CMlGauge` |
| `CControlMediaPlayer` | `CGameManialinkMediaPlayer` | `<video>` / `<audio>` | `CMlMediaPlayer` |
| `CControlMiniMap` | `CGameManialinkMiniMap` | `<minimap>` | `CMlMinimap` |
| `CControlColorChooser2` | `CGameManialinkColorChooser` | (not in XML) | `CMlColorChooser` |
| `CControlCamera` | `CGameManialinkCamera` | (not in XML) | `CMlCamera` |
| `CControlTimeLine2` | `CGameManialinkTimeLine` | (not in XML) | -- |
| -- | `CGameManialinkArrow` | (not in XML) | -- |
| -- | `CGameManialinkPlayerList` | (not in XML) | -- |
| -- | `CGameManialinkOldTable` | (not in XML, deprecated) | -- |
| -- | `CGameManialinkFileEntry` | `<fileentry>` | `CMlFileEntry` |

### 3.3 Per-Frame Update

Every `CGameManialink*` control has an `UpdateControl` method called each frame. The `CGameManialinkPage` has both `SetContents` (XML parsing) and `Update` (per-frame). The `CGameManialinkBrowser` has `UpdateAsync` and `UpdateFiber` for asynchronous page loading.

---

## 4. ManiaLink XML Format

**Source**: Community documentation (doc.maniaplanet.com, wiki.trackmania.io, maniaplanet-community.gitbook.io)
**Confidence**: HIGH (widely used by content creators, consistent across sources)

### 4.1 Basic Structure

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<manialink version="3" name="MyManialink">
  <!-- UI elements go here -->

  <script><!--
    // ManiaScript code goes here
    main() {
      while (True) {
        foreach (Event in PendingEvents) {
          // Handle events
        }
        yield;
      }
    }
  --></script>
</manialink>
```

### 4.2 Version History

| Version | Engine | Era | Key Changes |
|---------|--------|-----|-------------|
| 0 | TMF | 2008 | Original ManiaLink format |
| 1 | ManiaPlanet 1 | 2011 | Frame support, improved layout |
| 2 | ManiaPlanet 3 | 2014 | ScriptEvents, improved styling |
| 3 | ManiaPlanet 4 / TM2020 | 2017+ | **Current version** -- new coordinate system, `z-index`, `scale`, `rot`, class attribute |

**TM2020 uses version 3 exclusively.**

### 4.3 Root Element Attributes

```xml
<manialink version="3" name="UniqueIdentifier" background="...">
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `version` | Integer | ManiaLink version (always "3" for TM2020) |
| `name` | String | Unique identifier for the ManiaLink page |
| `background` | String | Background type: `default_image`, `True`/`1`, `hide`/`False`/`0`, `stars`, `stations`, `title` |

### 4.4 Complete Element Reference

#### Common Attributes (all elements)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `id` | String | -- | Unique identifier for script access |
| `class` | String | -- | Style class reference |
| `pos` | "X Y" | "0 0" | Position relative to parent frame |
| `z-index` | Float | 0 | Depth layer (-999 to 999) |
| `size` | "W H" | varies | Width and height in ManiaLink units |
| `scale` | Float | 1.0 | Scale factor |
| `rot` | Float | 0 | Rotation in degrees |
| `hidden` | Bool | 0 | Whether element is hidden (1=hidden) |
| `halign` | Enum | "left" | Horizontal alignment: `left`, `center`, `right` |
| `valign` | Enum | "top" | Vertical alignment: `top`, `center`, `center2`, `bottom` |
| `scriptevents` | Bool | 0 | Enable script event generation (1=enabled) |
| `opacity` | Float | 1.0 | Transparency (0=invisible, 1=opaque) |
| `action` | String | -- | ManiaLink action URL on click |
| `url` | String | -- | External URL to open on click |
| `manialink` | String | -- | ManiaLink page to navigate to on click |

#### `<quad>` -- Image/Rectangle Display

Displays an image, colored rectangle, or built-in style element.

| Attribute | Type | Description |
|-----------|------|-------------|
| `image` | URL | Image source (.png, .jpg, .dds) |
| `imagefocus` | URL | Image shown on hover/focus |
| `style` | String | Built-in style name (e.g., "Bgs1") |
| `substyle` | String | Sub-style within style (e.g., "BgWindow1") |
| `styleselected` | String | Style when selected |
| `bgcolor` | Hex | Background color (RGB, RGBA, RRGGBB, RRGGBBAA) |
| `colorize` | Hex | Colorize filter (recolors green channel) |
| `modulatecolor` | Hex | Modulate color (multiply blend) |
| `autoscale` | Bool | Auto-scale image to fit |
| `keepratio` | Enum | Aspect ratio: `Inactive`, `Clip`, `Fit` |

**HTML equivalent**: `<div>` with `background-image` or `<img>`

#### `<label>` -- Text Display

Displays text with formatting options.

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | String | Text content to display |
| `textid` | String | Translation key for localized text |
| `textprefix` | String | Prefix prepended to text |
| `style` | String | Built-in label style |
| `textfont` | String | Font name |
| `textsize` | Float | Font size (default: 1) |
| `textcolor` | Hex | Text color (RGB or RRGGBB) |
| `textemboss` | Bool | Embossed text effect |
| `autonewline` | Bool | Automatic line wrapping |
| `maxline` | Integer | Maximum number of lines |
| `translate` | Bool | Enable automatic translation |
| `focusareacolor1` | Hex | Focus area primary color |
| `focusareacolor2` | Hex | Focus area secondary color |

**HTML equivalent**: `<span>` or `<p>` with CSS `font-*` properties

#### `<entry>` -- Single-Line Text Input

| Attribute | Type | Description |
|-----------|------|-------------|
| `default` | String | Default/initial value |
| `name` | String | Name for HTTP POST submission |
| `selecttext` | Bool | Select all text on focus |
| `textformat` | String | Input format constraint: `Basic`, `Script`, `Password`, `Newpassword` |
| `style` | String | Visual style |
| `textfont` | String | Font name |
| `textsize` | Float | Font size |
| `textcolor` | Hex | Text color |
| `focusareacolor1` | Hex | Focus background primary |
| `focusareacolor2` | Hex | Focus background secondary |

**HTML equivalent**: `<input type="text">`

#### `<textedit>` -- Multi-Line Text Editor

| Attribute | Type | Description |
|-----------|------|-------------|
| `default` | String | Default text content |
| `name` | String | Name for HTTP POST |
| `showlinenumbers` | Bool | Display line numbers |
| `autonewline` | Bool | Auto line wrapping |
| `maxline` | Integer | Maximum lines |
| `linespacing` | Float | Space between lines |
| `textformat` | String | Input format: `Basic`, `Script`, `Password`, `Newpassword` |
| `style` | String | Visual style |
| `textfont` | String | Font |
| `textsize` | Float | Font size |
| `textcolor` | Hex | Text color |
| `focusareacolor1` | Hex | Focus background primary |
| `focusareacolor2` | Hex | Focus background secondary |

**HTML equivalent**: `<textarea>`

#### `<fileentry>` -- File Chooser

| Attribute | Type | Description |
|-----------|------|-------------|
| `default` | String | Default file path |
| `name` | String | Name for submission |
| `selecttext` | Bool | Select text on focus |
| `type` | String | File type filter |
| `folder` | String | Starting folder path |
| `style` | String | Visual style |
| `textfont` | String | Font |
| `textsize` | Float | Font size |
| `textcolor` | Hex | Text color |
| `focusareacolor1` | Hex | Focus background primary |
| `focusareacolor2` | Hex | Focus background secondary |

**HTML equivalent**: `<input type="file">`

#### `<gauge>` -- Progress Bar

| Attribute | Type | Description |
|-----------|------|-------------|
| `style` | String | Gauge style (e.g., "EnergyBar") |
| `ratio` | Float | Fill ratio (0.0 to 1.0) |
| `grading` | String | Grading mode |
| `clan` | Integer | Team/clan color assignment |
| `drawbg` | Bool | Draw background |
| `drawblockbg` | Bool | Draw block background |
| `color` | Hex | Gauge fill color |

**HTML equivalent**: `<progress>` or `<div>` with percentage width

#### `<graph>` -- Line Chart

Populated via ManiaScript. The XML element just establishes the container.

| Attribute | Type | Description |
|-----------|------|-------------|
| (common attributes only) | -- | Use ManiaScript to add curves |

**ManiaScript API**:
```
declare CMlGraph Graph = (Page.GetFirstChild("graphId") as CMlGraph);
declare CMlGraphCurve Curve = Graph.AddCurve();
Curve.Points.add(<X, Y>);
Curve.Color = <R, G, B>;
Curve.Width = 2.0;
```

**HTML equivalent**: `<canvas>` or `<svg>` with chart.js / d3.js

#### `<frame>` -- Container/Group

Groups child elements with shared position offset.

| Attribute | Type | Description |
|-----------|------|-------------|
| (common attrs: `id`, `pos`, `z-index`, `scale`, `rot`, `hidden`, `class`) | -- | No size-specific display |

```xml
<frame id="MyFrame" pos="10 -20">
  <quad pos="0 0" size="30 10" bgcolor="000A" />
  <label pos="2 -2" text="Hello" />
</frame>
```

**HTML equivalent**: `<div>` with `position: relative`

#### `<framemodel>` -- Reusable Frame Template

Defines a template that can be instantiated multiple times.

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | String | **Required** -- template identifier |

```xml
<framemodel id="ItemTemplate">
  <quad size="40 8" bgcolor="000A" />
  <label id="ItemLabel" pos="2 -2" textsize="2" />
</framemodel>
```

**HTML equivalent**: `<template>` element

#### `<frameinstance>` -- Template Instance

Creates an instance of a `<framemodel>`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `modelid` | String | **Required** -- references a framemodel id |

```xml
<frameinstance modelid="ItemTemplate" pos="0 0" />
<frameinstance modelid="ItemTemplate" pos="0 -10" />
```

**HTML equivalent**: JavaScript `template.content.cloneNode(true)`

#### `<audio>` -- Audio Playback

| Attribute | Type | Description |
|-----------|------|-------------|
| `data` | URL | Audio source (.ogg, .wav, .mux) |
| `play` | Bool | Auto-play on load |
| `loop` | Bool | Loop playback |
| `music` | Bool | Treat as background music (true) vs. sound effect (false) |
| `volume` | Float | Volume (0.0 to 1.0) |

**HTML equivalent**: `<audio>`

#### `<video>` -- Video Playback

| Attribute | Type | Description |
|-----------|------|-------------|
| `data` | URL | Video source (.webm) |
| `play` | Bool | Auto-play |
| `loop` | Bool | Loop playback |
| `music` | Bool | Audio routing |
| `volume` | Float | Volume |

**HTML equivalent**: `<video>`

#### `<include>` -- Include External File

| Attribute | Type | Description |
|-----------|------|-------------|
| `url` | String | Path to external ManiaLink XML file |

```xml
<include url="file://Media/Manialinks/Common/Header.xml" />
```

**HTML equivalent**: Server-side includes / JavaScript `fetch()`

#### `<dico>` -- Translation Dictionary

Defines translations for multilingual ManiaLink pages.

```xml
<dico>
  <language id="en">
    <greeting>Hello!</greeting>
  </language>
  <language id="fr">
    <greeting>Bonjour!</greeting>
  </language>
</dico>
<label text="" textid="greeting" translate="1" />
```

**HTML equivalent**: i18n libraries (i18next, etc.)

---

## 5. Layout System (Positioning, Sizing, Anchoring)

### 5.1 Coordinate System

ManiaLink version 3 uses a screen-relative coordinate system:

```
        (-160, 90)              (0, 90)               (160, 90)
            +-------------------------+-------------------------+
            |                         |                         |
            |      Top-Left           |      Top-Right          |
            |                         |                         |
(-160, 0)   +------------- (0, 0) ORIGIN ----------------------+ (160, 0)
            |                         |                         |
            |      Bottom-Left        |      Bottom-Right       |
            |                         |                         |
            +-------------------------+-------------------------+
        (-160, -90)             (0, -90)              (160, -90)
```

| Property | Value | Notes |
|----------|-------|-------|
| Origin | (0, 0) | Center of screen |
| Total width | 320 units | -160 to +160 |
| Total height | 180 units | -90 to +90 |
| X-axis | Left (-160) to Right (+160) | |
| Y-axis | Bottom (-90) to Top (+90) | **Y increases upward** (opposite of HTML) |
| Z-axis | Depth layering | Higher z-index = rendered on top |
| Aspect ratio | 16:9 | Units maintain aspect ratio |

**CRITICAL**: Unlike HTML/CSS where Y increases downward, ManiaLink Y increases **upward**. This means `pos="0 -10"` moves an element **down** from its parent.

### 5.2 Positioning

Elements are positioned relative to their parent frame:

```xml
<!-- Absolute position (relative to screen center) -->
<quad pos="-100 50" size="40 20" bgcolor="F00A" />

<!-- Relative to parent frame -->
<frame pos="-100 50">
  <quad pos="0 0" size="40 20" bgcolor="F00A" />
  <quad pos="0 -25" size="40 20" bgcolor="0F0A" />  <!-- 25 units below first -->
</frame>
```

### 5.3 Alignment (Anchor Point)

`halign` and `valign` control the anchor point of the element:

```
halign="left" (default)     halign="center"          halign="right"
  +--------+                   +--------+                +--------+
  * pos here                       * pos                      pos *
  +--------+                   +--------+                +--------+

valign="top" (default)      valign="center"          valign="bottom"
  * pos here                                             +--------+
  +--------+                   +--------+                +--------+
  |        |                   | * pos  |                |        |
  +--------+                   +--------+                * pos here
```

| halign | Meaning | CSS equivalent |
|--------|---------|----------------|
| `left` | Anchor at left edge (default) | `transform-origin: left` |
| `center` | Anchor at horizontal center | `transform-origin: center` |
| `right` | Anchor at right edge | `transform-origin: right` |

| valign | Meaning | CSS equivalent |
|--------|---------|----------------|
| `top` | Anchor at top edge (default) | -- |
| `center` | Anchor at vertical center | -- |
| `center2` | Alternative center (legacy) | -- |
| `bottom` | Anchor at bottom edge | -- |

### 5.4 Scale and Rotation

```xml
<quad pos="0 0" size="20 10" scale="1.5" rot="45" bgcolor="F00A" />
```

- `scale="1.5"` -- scales the element to 150% around its anchor point
- `rot="45"` -- rotates 45 degrees clockwise around its anchor point

### 5.5 Z-Index Layering

```xml
<quad pos="0 0" z-index="-1" size="320 180" bgcolor="000F" />  <!-- Background -->
<quad pos="0 0" z-index="0" size="100 50" bgcolor="F00A" />    <!-- Content -->
<label pos="0 0" z-index="1" text="On Top" />                   <!-- Foreground -->
```

Range: approximately -999 to 999. Higher values render on top.

---

## 6. Style System

### 6.1 Built-in Quad Styles

ManiaLink provides a rich library of pre-built visual styles. Apply with `style="StyleName" substyle="SubStyleName"`:

```xml
<quad pos="0 0" size="40 20" style="Bgs1" substyle="BgWindow1" />
<quad pos="0 0" size="64 64" style="Icons64x64_1" substyle="ArrowGreen" />
```

#### Major Style Categories

| Style | Purpose | Substyle Count | Examples |
|-------|---------|----------------|----------|
| `Bgs1` | General backgrounds | 65+ | BgWindow1-4, BgCard, BgButton, BgList, Shadow, ProgressBar |
| `Bgs1InRace` | In-race backgrounds | Same as Bgs1 | Same substyles, race-optimized rendering |
| `BgRaceScore2` | Scoreboard backgrounds | 27 | BgScores, Podium, Warmup, Spectator, TV, LadderRank |
| `BgsPlayerCard` | Player card backgrounds | 13 | BgPlayerCard, BgPlayerName, BgPlayerScore, ProgressBar |
| `BgsChallengeMedals` | Medal backgrounds | 6 | BgBronze, BgSilver, BgGold, BgNadeo, BgPlayed, BgNotPlayed |
| `BgsButtons` | Button backgrounds | 7 | BgButtonLarge, BgButtonMedium, BgButtonSmall, BgButtonXSmall |
| `Icons64x64_1` | 64x64 icon set | 80+ | ArrowGreen, Check, Close, Refresh, Camera, TV, Save |
| `Icons64x64_2` | 64x64 icon set 2 | 15 | ArrowElimination, Calendar, Disconnected, ServerNotice |
| `Icons128x128_1` | 128x128 icon set | 65+ | Solo, Multiplayer, Editor, Options, Replay, Quit |
| `Icons128x32_1` | Wide icons | 30+ | Music, Sound, Settings, RT_Cup, RT_Laps, RT_Rounds |
| `UIConstruction_Buttons` | Editor toolbar | 50+ | Camera, Drive, Save, Undo, Redo, Delete, Pick, Paint |
| `321Go` | Countdown numbers | 4 | 1, 2, 3, Go! |
| `Copilot` | Direction arrows | 12 | Up, Down, Left, Right + Good/Wrong variants |
| `EnergyBar` | Energy/health bars | 6 | EnergyBar, BgText, HeaderGaugeLeft/Right |
| `Hud3dEchelons` | Echelon badges | 9 | EchelonBronze1-3, Silver1-3, Gold1-3 |
| `ManiaPlanetLogos` | Platform logos | 7 | ManiaPlanetLogoBlack/White, IconPlanets |
| `ManiaPlanetMainMenu` | Main menu elements | 11 | MainBg, TopBar, BottomBar, IconHome, IconPlay, IconQuit |
| `MedalsBig` | Large medal icons | 7 | MedalBronze, MedalSilver, MedalGold, MedalNadeo |
| `TitleLogos` | Title pack logos | 4 | Author, Collection, Icon, Title |
| `UiSMSpectatorScoreBig` | Spectator score UI | 18 | PlayerSlot, HandleLeft/Right, TableBg, UIRange |

#### Bgs1 Complete Substyle List

```
ArrowDown, ArrowLeft, ArrowRight, ArrowUp,
BgButton, BgButtonBig, BgButtonGlow, BgButtonGrayed, BgButtonOff, BgButtonShadow, BgButtonSmall,
BgCard, BgCard1, BgCard2, BgCard3, BgCardBuddy, BgCardChallenge, BgCardFolder,
BgCardInventoryItem, BgCardList, BgCardOnline, BgCardPlayer, BgCardProperty, BgCardSystem, BgCardZone,
BgColorContour, BgDialogBlur, BgEmpty, BgGlow2,
BgGradBottom, BgGradLeft, BgGradRight, BgGradTop, BgGradV,
BgHealthBar, BgIconBorder, BgList, BgListLine, BgMetalBar, BgPager, BgProgressBar,
BgShadow, BgSlider, BgSystemBar,
BgTitle, BgTitle2, BgTitle3, BgTitle3_1, BgTitle3_2, BgTitle3_3, BgTitle3_4, BgTitle3_5,
BgTitleGlow, BgTitlePage, BgTitleShadow,
BgWindow1, BgWindow2, BgWindow3, BgWindow4,
EnergyBar, EnergyTeam2, Glow, HealthBar,
NavButton, NavButtonBlink, NavButtonQuit,
ProgressBar, ProgressBarSmall, Shadow
```

### 6.2 Label Styles

Label styles control text appearance:

| Style | Description |
|-------|-------------|
| `Default` | Default text style |
| `Manialink_Body` | Body text for ManiaLink pages |
| `AvatarButtonNormal` | Avatar button text |
| `BgMainMenuTitleHeader` | Main menu title header |
| (60+ additional styles) | Various text styles for specific UI contexts |

### 6.3 Frame3d Styles

For 3D frame elements:

| Style | Description |
|-------|-------------|
| `BaseStation` | Station background |
| `BaseBoxCase` | Box container |
| `Titlelogo` | Title logo frame |
| `ButtonBack` | Back button frame |
| `ButtonNav` | Navigation button |
| `ButtonH` | Horizontal button |
| `Station3x3` | 3x3 station grid |
| `Title` | Title frame |
| `TitleEditor` | Editor title |
| `Window` | Window frame |

### 6.4 Color Format

Colors use hexadecimal notation with multiple formats:

| Format | Example | Description |
|--------|---------|-------------|
| `RGB` | `F00` | Red=F, Green=0, Blue=0 (each expanded to FF, 00, 00) |
| `RGBA` | `F00A` | RGB + Alpha (A expanded to AA) |
| `RRGGBB` | `FF0000` | Full RGB |
| `RRGGBBAA` | `FF0000AA` | Full RGBA |

**Note**: In the 4-digit RGBA format, the alpha channel follows a convention where `0` = opaque and `F` = transparent. This is **inverted** from the `opacity` attribute and standard CSS convention. In the 8-digit RRGGBBAA format, `00` = transparent and `FF` = opaque (standard convention).

---

## 7. Built-in Controls Reference

### 7.1 Quad (CControlQuad / CGameManialinkQuad)

The most versatile element. Displays images, colors, or built-in styles.

```xml
<!-- Solid color background -->
<quad size="60 40" bgcolor="000C" />

<!-- Image -->
<quad size="20 20" image="file://Media/Images/logo.png" keepratio="Fit" />

<!-- Built-in style icon -->
<quad size="8 8" style="Icons64x64_1" substyle="Check" />

<!-- Interactive with hover image -->
<quad size="30 8" image="btn.png" imagefocus="btn_hover.png" scriptevents="1" id="MyButton" />
```

| ManiaScript Property | Type | Description |
|---------------------|------|-------------|
| `ImageUrl` | Text | Current image URL |
| `ImageUrlFocus` | Text | Hover image URL |
| `Style` | Text | Current style |
| `Substyle` | Text | Current substyle |
| `Colorize` | Vec3 | Colorize RGB |
| `ModulateColor` | Vec3 | Modulate color RGB |
| `BgColor` | Vec3 | Background color RGB |
| `Opacity` | Real | Opacity (0-1) |

### 7.2 Label (CControlLabel / CGameManialinkLabel)

Text display with rich formatting.

```xml
<!-- Simple text -->
<label pos="0 0" text="Hello World" textsize="4" textcolor="FFF" />

<!-- Multi-line with wrapping -->
<label pos="0 0" size="80 20" text="Long text that wraps..." autonewline="1" maxline="3" />

<!-- Clickable label -->
<label pos="0 0" text="Click Me" scriptevents="1" id="ClickLabel" focusareacolor1="F00" />
```

| ManiaScript Property | Type | Description |
|---------------------|------|-------------|
| `Value` | Text | Get/set displayed text |
| `TextFont` | Text | Font name |
| `TextSize` | Real | Font size |
| `TextSizeReal` | Real | Computed real text size |
| `TextColor` | Vec3 | Text color RGB |
| `MaxLine` | Integer | Max visible lines |
| `Opacity` | Real | Opacity |

### 7.3 Entry (CControlEntry / CGameManialinkEntry)

Single-line text input field.

```xml
<entry id="NameInput" pos="0 0" size="40 6"
       default="Enter name..." textsize="2"
       focusareacolor1="333F" focusareacolor2="555F"
       scriptevents="1" />
```

| ManiaScript Property | Type | Description |
|---------------------|------|-------------|
| `Value` | Text | Current text value |
| `MaxLine` | Integer | Max characters |
| `StartEdition()` | Method | Focus the input |
| `HtmlControl` | -- | Corresponding HTML input |

### 7.4 TextEdit (CControlTextEdition / CGameManialinkTextEdit)

Multi-line text editor with optional line numbers.

```xml
<textedit id="CodeEditor" pos="-60 30" size="120 60"
          showlinenumbers="1" textformat="Script"
          textfont="RajdhaniMono" textsize="2"
          default="// Write code here" />
```

| ManiaScript Property | Type | Description |
|---------------------|------|-------------|
| `Value` | Text | Full text content |
| `MaxLine` | Integer | Max lines |
| `LineCount` | Integer | Current line count (read-only) |

### 7.5 Gauge (CControlSlider / CGameManialinkGauge)

Progress bar / gauge display.

```xml
<gauge id="HealthBar" pos="0 -80" size="60 8"
       style="EnergyBar" drawbg="1"
       ratio="0.75" color="0F0" />
```

| ManiaScript Property | Type | Description |
|---------------------|------|-------------|
| `Ratio` | Real | Fill ratio (0.0 to 1.0) |
| `GradingRatio` | Real | Grading position |
| `Color` | Vec3 | Gauge color |
| `DrawBg` | Boolean | Whether to draw background |
| `Clan` | Integer | Clan/team color |

### 7.6 Graph (CControlGraph / CGameManialinkGraph)

Line chart display populated via script.

```xml
<graph id="SpeedGraph" pos="-60 -20" size="120 40" scriptevents="1" />
```

| ManiaScript Method/Property | Type | Description |
|---------------------------|------|-------------|
| `AddCurve()` | CMlGraphCurve | Create a new curve |
| `RemoveCurve(Curve)` | Void | Remove a curve |
| `Curves` | CMlGraphCurve[] | All curves |

**CMlGraphCurve properties**:

| Property | Type | Description |
|----------|------|-------------|
| `Points` | Vec2[] | Array of (X, Y) data points |
| `Color` | Vec3 | Curve color |
| `Width` | Real | Line width |
| `SortPoints` | Boolean | Auto-sort points by X |

### 7.7 Frame (CControlFrame / CGameManialinkFrame)

Invisible container that groups elements.

```xml
<frame id="Panel" pos="-60 40">
  <quad size="120 80" bgcolor="111C" />
  <label pos="5 -5" text="Panel Title" textsize="4" />
  <!-- More children... -->
</frame>
```

| ManiaScript Method/Property | Type | Description |
|---------------------------|------|-------------|
| `Controls` | CMlControl[] | Child controls |
| `GetFirstChild(Id)` | CMlControl | Find child by ID |
| `ScrollOffset` | Vec2 | Scroll position |
| `ScrollAnimOffset` | Vec2 | Animated scroll offset |
| `DisablePreload` | Boolean | Disable texture preloading |

### 7.8 MiniMap (CControlMiniMap / CGameManialinkMiniMap)

Displays a top-down map view.

```xml
<minimap id="MapView" pos="50 -50" size="40 40" />
```

| ManiaScript Property | Type | Description |
|---------------------|------|-------------|
| `WorldPosition` | Vec3 | Center position in world |
| `MapPosition` | Vec2 | Center position on map |
| `MapYaw` | Real | Map rotation |
| `ZoomFactor` | Real | Zoom level |

### 7.9 Audio (CGameManialinkMediaPlayer)

```xml
<audio data="file://Media/Sounds/click.ogg" play="0" loop="0" id="ClickSound" />
```

| ManiaScript Method | Description |
|-------------------|-------------|
| `Play()` | Start playback |
| `Stop()` | Stop playback |
| `IsPlaying` | Check if currently playing |
| `Volume` | Get/set volume |

### 7.10 Video (CGameManialinkMediaPlayer)

```xml
<video id="IntroVideo" pos="-80 45" size="160 90"
       data="file://Media/Videos/intro.webm" play="1" loop="0" />
```

Shares the same ManiaScript API as Audio.

---

## 8. ManiaLink Scripting

### 8.1 Script Context

ManiaLink scripts run within specific context classes depending on where the ManiaLink is loaded:

| Context | Class | When Used |
|---------|-------|-----------|
| Standalone ManiaLink page | `CMlScript` | Default ManiaLink pages |
| Game mode HUD layer | `CMlScriptIngame` / `CSmMlScriptIngame` / `CTmMlScriptIngame` | In-game UI layers |
| Title pack menu | `CMlScript` | Menu pages |
| Editor plugin | `CMlScript` | Editor UI |

### 8.2 Script Structure

```xml
<script><!--
  #RequireContext CMlScriptIngame  // Optional: specify required context

  // Global variable declarations
  declare Integer G_Counter;

  // Helper functions
  Void UpdateDisplay() {
    declare Label = (Page.GetFirstChild("CounterLabel") as CMlLabel);
    Label.Value = "" ^ G_Counter;
  }

  // Main entry point
  main() {
    G_Counter = 0;
    while (True) {
      foreach (Event in PendingEvents) {
        if (Event.Type == CMlScriptEvent::Type::MouseClick) {
          if (Event.ControlId == "IncrementBtn") {
            G_Counter += 1;
            UpdateDisplay();
          }
        }
        if (Event.Type == CMlScriptEvent::Type::KeyPress) {
          if (Event.KeyName == "F1") {
            // Handle F1 key
          }
        }
      }
      yield;  // Yield to engine, resume next frame
    }
  }
--></script>
```

### 8.3 Event Types (CMlScriptEvent::Type)

| Event Type | Trigger | Event Properties |
|------------|---------|-----------------|
| `MouseClick` | Click on element with `scriptevents="1"` | `ControlId`, `Control` |
| `MouseOver` | Mouse enters element | `ControlId`, `Control` |
| `MouseOut` | Mouse leaves element | `ControlId`, `Control` |
| `KeyPress` | Keyboard key pressed | `KeyName`, `KeyCode`, `CharPressed` |
| `EntrySubmit` | Enter pressed in entry field | `ControlId`, `Control` |
| `MenuNavigation` | Gamepad/keyboard menu navigation | `MenuCmd` |
| `PluginCustomEvent` | Custom event from server/plugin | `CustomEventType`, `CustomEventData` |

### 8.4 Event Properties

| Property | Type | Description |
|----------|------|-------------|
| `Type` | CMlScriptEvent::Type | Event type enum |
| `ControlId` | Text | ID of the control that triggered the event |
| `Control` | CMlControl | Reference to the control object |
| `KeyName` | Text | Key identifier (e.g., "F1", "Escape", "Return") |
| `KeyCode` | Integer | Numeric key code |
| `CharPressed` | Text | Character typed (for text input) |
| `CustomEventType` | Text | Custom event type string |
| `CustomEventData` | Text[] | Custom event data array |

### 8.5 Page API (CMlPage)

The `Page` global object provides access to all controls:

| Method/Property | Type | Description |
|----------------|------|-------------|
| `Page.GetFirstChild(Id)` | CMlControl | Find control by ID (returns base type) |
| `Page.MainFrame` | CMlFrame | Root frame of the page |
| `Page.FocusedControl` | CMlControl | Currently focused control |

**Type Casting**: Controls must be cast to their specific type:

```
declare MyQuad = (Page.GetFirstChild("qid") as CMlQuad);
declare MyLabel = (Page.GetFirstChild("lid") as CMlLabel);
declare MyEntry = (Page.GetFirstChild("eid") as CMlEntry);
declare MyGauge = (Page.GetFirstChild("gid") as CMlGauge);
declare MyFrame = (Page.GetFirstChild("fid") as CMlFrame);
declare MyGraph = (Page.GetFirstChild("grid") as CMlGraph);
```

### 8.6 Common Control Properties (CMlControl base)

All ManiaLink controls expose:

| Property | Type | Description |
|----------|------|-------------|
| `ControlId` | Text | Control's ID |
| `RelativePosition_V3` | Vec2 | Position relative to parent |
| `Size` | Vec2 | Width and height |
| `HorizontalAlign` | CMlControl::AlignHorizontal | Left/Center/Right |
| `VerticalAlign` | CMlControl::AlignVertical | Top/Center/Bottom |
| `Visible` | Boolean | Whether control is visible |
| `RelativeScale` | Real | Scale factor |
| `RelativeRotation` | Real | Rotation in degrees |
| `ZIndex` | Real | Depth layer |
| `DataAttributeGet(Key)` | Text | Get custom data attribute |
| `DataAttributeSet(Key, Val)` | Void | Set custom data attribute |
| `Show()` | Void | Make visible |
| `Hide()` | Void | Make hidden |
| `Focus()` | Void | Set keyboard focus |

### 8.7 Animation API (AnimMgr)

The `AnimMgr` global provides programmatic UI animation:

```
// Animate position over 300ms with EaseOutQuad
AnimMgr.Add(MyControl, "<control pos=\"10 -20\" />", 300, CAnimManager::EAnimManagerEasing::EaseOutQuad);

// Animate size and opacity
AnimMgr.Add(MyQuad, "<quad size=\"40 20\" opacity=\"0.5\" />", 500, CAnimManager::EAnimManagerEasing::Linear);

// Flush all animations on a control
AnimMgr.Flush(MyControl);
```

**Easing Functions** (`CAnimManager::EAnimManagerEasing` / `CGameManialinkAnimManager::EAnimManagerEasing`):

| Easing | Description |
|--------|-------------|
| `Linear` | Constant speed |
| `EaseInQuad` | Accelerating from zero |
| `EaseOutQuad` | Decelerating to zero |
| `EaseInOutQuad` | Accelerate then decelerate |
| `EaseInCubic` | Cubic acceleration |
| `EaseOutCubic` | Cubic deceleration |
| `EaseInOutCubic` | Cubic accel/decel |
| `EaseInQuart` | Quartic acceleration |
| `EaseOutQuart` | Quartic deceleration |
| `EaseInOutQuart` | Quartic accel/decel |
| `EaseInQuint` | Quintic acceleration |
| `EaseOutQuint` | Quintic deceleration |
| `EaseInOutQuint` | Quintic accel/decel |
| `EaseInSine` | Sine acceleration |
| `EaseOutSine` | Sine deceleration |
| `EaseInOutSine` | Sine accel/decel |
| `EaseInExp` | Exponential acceleration |
| `EaseOutExp` | Exponential deceleration |
| `EaseInOutExp` | Exponential accel/decel |
| `EaseInCirc` | Circular acceleration |
| `EaseOutCirc` | Circular deceleration |
| `EaseInOutCirc` | Circular accel/decel |
| `EaseInBack` | Overshoot back start |
| `EaseOutBack` | Overshoot back end |
| `EaseInOutBack` | Overshoot both |
| `EaseInElastic` | Elastic start |
| `EaseOutElastic` | Elastic end |
| `EaseInOutElastic` | Elastic both |
| `EaseInBounce` | Bounce start |
| `EaseOutBounce` | Bounce end |
| `EaseInOutBounce` | Bounce both |

### 8.8 Declare Modes (for UI Layers)

When ManiaLink runs as a game mode UI layer, variables can have special persistence:

```
// Local to this page instance (default)
declare Integer MyVar;

// Persistent across page reloads
declare persistent Integer MyPersistentVar;

// Shared from server to client (netwrite/netread)
declare netwrite Integer Net_ServerValue for UI;
declare netread Integer Net_ServerValue for UI;
```

---

## 9. ManiaApp System (Application Layer)

### 9.1 ManiaApp Hierarchy

The `CGameManiaApp*` classes form the application layer that hosts ManiaLink pages:

```
CGameManiaApp                             -- Base ManiaApp (has Update method)
  +-- CGameManiaAppBrowser                -- ManiaLink browser app (UpdateAsync)
  +-- CGameManiaAppGraphWindow            -- Graph window app
  +-- CGameManiaAppMinimal                -- Minimal app (lightweight)
  +-- CGameManiaAppPlayground             -- In-game UI app
  +-- CGameManiaAppPlaygroundCommon       -- Shared playground UI (Update)
  +-- CGameManiaAppStation                -- Station/menu app
  +-- CGameManiaAppTextSet                -- Text set app
  +-- CGameManiaAppTitle                  -- Title pack app (Update)
  +-- CGameManiaAppTitleLayerScriptHandler -- Title layer scripting
```

### 9.2 CGameManiaAppPlayground

The primary entry point for in-game UI. Available as the script context for game mode ManiaLink layers.

**Key capabilities**:
- Access to `UILayers[]` -- array of ManiaLink pages shown during gameplay
- Access to `GUIPlayer` -- the current player's state
- Access to game state, scores, and other players
- Can send/receive `CustomEvents` between layers

### 9.3 UI Layer System (CGameUILayer)

Game modes create UI by adding **layers** -- each layer is a ManiaLink page:

```
CGamePlaygroundUIConfig               -- Manages UI layers
  +-- UILayers[] : CGameUILayer[]    -- Array of active layers
```

Each `CGameUILayer` has:

| Property | Type | Description |
|----------|------|-------------|
| `ManialinkPage` | Text | The ManiaLink XML content |
| `Type` | EUILayerType | Layer type (Normal, ScoresTable, AltMenu, etc.) |
| `IsVisible` | Boolean | Visibility toggle |
| `AttachId` | Text | Which player/entity this layer attaches to |

### 9.4 ManiaPlanet Application Root

```
CGameManiaPlanet                          -- Top-level application
  +-- CGameManiaPlanetMenuStations        -- Menu station manager
  +-- CGameManiaPlanetNetwork             -- Network subsystem
  +-- CGameManiaPlanetScriptAPI           -- Script API for the platform
  +-- CGameManiaTitle                     -- Current title pack
  +-- CGameManiaTitleCore                 -- Title core (GameStartUp, NetLoop)
  +-- CGameManiaTitleControlScriptAPI     -- Title control API
  +-- CGameManiaTitleEditionScriptAPI     -- Title edition API
```

---

## 10. HUD Elements and Playground Modules

### 10.1 Module Architecture

The HUD in Trackmania uses a module system with client/server components:

```
CGamePlaygroundModuleManagerClient / Server
  +-- CGamePlaygroundModuleClient* / Server*
       +-- Altimeter      -- Altitude display
       +-- Chrono         -- Race timer
       +-- Hud            -- Main HUD container
       +-- Inventory      -- Item inventory (ShootMania)
       +-- PlayerState    -- Player state display
       +-- ScoresTable    -- Scoreboard
       +-- SpeedMeter     -- Speed display
       +-- Store          -- In-game store (ShootMania)
       +-- TeamState      -- Team state display
       +-- Throttle       -- Throttle/input display
```

### 10.2 HUD Model Classes

| Class | Purpose |
|-------|---------|
| `CGameModulePlaygroundHudModel` | Main HUD layout model |
| `CGameModulePlaygroundHudModelModule` | Individual HUD module model |
| `CGameModulePlaygroundChronoModel` | Timer/chronometer model |
| `CGameModulePlaygroundSpeedMeterModel` | Speedometer model |
| `CGameModulePlaygroundScoresTableModel` | Scores table layout model |
| `CGameModulePlaygroundPlayerStateModel` | Player state display model |
| `CGameModulePlaygroundPlayerStateGaugeModel` | Player gauge (health, etc.) |
| `CGameModulePlaygroundPlayerStateListModel` | Player list display |
| `CGameModulePlaygroundPlayerStateComponentModel` | Player state component |
| `CGameModulePlaygroundTeamStateModel` | Team state display |
| `CGameModulePlaygroundInventoryModel` | Inventory model |
| `CGameModulePlaygroundStoreModel` | Store model |
| `CGameModulePlaygroundModel` | Base module model |
| `CHudModule` | Abstract HUD module base |
| `CModulePlaygroundPlayerStateComponentModel` | Concrete player state component |

### 10.3 Standard TM2020 HUD Elements

These are the built-in HUD elements visible during gameplay:

| HUD Element | Module Class | ManiaLink Layer | Description |
|-------------|-------------|-----------------|-------------|
| **Speed display** | `SpeedMeter` | Game mode layer | Current speed in km/h |
| **Race timer** | `Chrono` | Game mode layer | Current race time / checkpoint diff |
| **Checkpoint diff** | `Chrono` | Game mode layer | +/- time vs personal best or ghost |
| **Lap counter** | `Chrono` | Game mode layer | Current lap / total laps |
| **Scoreboard** | `ScoresTable` | ScoresTable layer | Full player rankings (Tab key) |
| **Minimap** | Custom layer | Game mode layer | Top-down map view |
| **Input display** | `Throttle` | Game mode layer | Steering/throttle/brake visualization |
| **Gear/RPM** | Custom layer | Openplanet plugin | Engine data overlay |
| **Respawn counter** | Custom layer | Game mode layer | Number of respawns |

### 10.4 Custom HUD via ManiaLink

Game mode scripts can create custom HUD layers:

```
// In game mode script (CSmMode / CTmMode)
declare CUILayer MyLayer = UIManager.UILayerCreate();
MyLayer.ManialinkPage = """
<manialink version="3" name="CustomSpeed">
  <frame pos="0 -80">
    <label id="SpeedLabel" text="0" textsize="8" textcolor="FFF"
           halign="center" valign="center" />
    <label text="km/h" textsize="2" textcolor="888"
           pos="0 -6" halign="center" />
  </frame>
</manialink>
""";
MyLayer.Type = CUILayer::EUILayerType::Normal;
```

---

## 11. Game Control Cards

### 11.1 Card Widget System (17 classes)

Cards are reusable UI widgets for displaying structured data:

```
CGameControlCard                          -- Base card widget
  +-- CGameControlCardBuddy              -- Friend/buddy info card
  +-- CGameControlCardCtnArticle         -- Article/content card
  +-- CGameControlCardCtnChallengeInfo   -- Map/challenge info card
  +-- CGameControlCardCtnChapter         -- Campaign chapter card
  +-- CGameControlCardCtnGhostInfo       -- Ghost/replay info card
  +-- CGameControlCardCtnNetServerInfo   -- Server info card (multiplayer browser)
  +-- CGameControlCardCtnReplayRecordInfo -- Replay recording info card
  +-- CGameControlCardCtnVehicle         -- Vehicle selection card
  +-- CGameControlCardGeneric            -- Generic data card
  +-- CGameControlCardLadderRanking      -- Ranking position card
  +-- CGameControlCardLeague             -- League info card
  +-- CGameControlCardMessage            -- Message/notification card
  +-- CGameControlCardProfile            -- Player profile card
CGameControlCardManager                   -- Card widget lifecycle manager
CGameControlDataType                      -- Card data type schema definition
CGameControlGrid                          -- Game-specific grid layout
CGameControlGridCard                      -- Grid of card widgets
```

### 11.2 TrackMania-Specific Cards

From the class_hierarchy.json, TrackMania adds its own card specializations:

| Class | Engine ID | Purpose |
|-------|-----------|---------|
| `CTrackManiaControlCard` | `0x2408F000` | TM-specific card base |
| `CTrackManiaControlCheckPointList` | `0x2406E000` | Checkpoint time list |
| `CTrackManiaControlPlayerInfoCard` | `0x2408C000` | TM player info display |
| `CTrackManiaControlMatchSettingsCard` | `0x240C4000` | Match settings card |

---

## 12. UI Effect and Animation System

### 12.1 Native Effect Classes

```
CControlEffect                            -- Base effect
  +-- CControlEffectCombined              -- Chains multiple effects
  +-- CControlEffectMaster                -- Master controller (orchestrates)
  +-- CControlEffectMotion                -- Translation/rotation motion
  +-- CControlEffectMoveFrame             -- Frame position animation
  +-- CControlEffectSimi                  -- Similarity transform (scale+rotate+translate)
```

### 12.2 CControlEffectSimi Keyframes

The `SKeyVal` struct defines keyframe values for similarity transform animations. This is the underlying mechanism for ManiaLink's `AnimMgr`.

### 12.3 CControlSimi2

A 2D similarity transform (3 DOF: translate X/Y, uniform scale, rotation). Used for efficient 2D UI transformations.

### 12.4 Animation System Flow

```
ManiaScript: AnimMgr.Add(control, xmlTarget, duration, easing)
    |
    v
CGameManialinkAnimManager (EAnimManagerEasing enum)
    |
    v
CControlEffectSimi / CControlEffectMotion (SKeyVal keyframes)
    |
    v
CControlEngine::ControlsEffects() (per-frame interpolation)
    |
    v
Native rendering (GPU)
```

---

## 13. Openplanet DefaultStyle (Modern UI Theme)

**Source**: `Trackmania/Openplanet/DefaultStyle.toml`
**Confidence**: VERIFIED (actual file from game installation)

Openplanet uses ImGui-style theming. While not ManiaLink, it shows the modern TM2020 UI aesthetic:

### 13.1 Layout Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `DisplayWindowPadding` | [16, 16] | Window content padding |
| `DisplaySafeAreaPadding` | [0, 0] | Safe area margins |
| `WindowRounding` | 3 | Window corner radius |
| `ChildRounding` | 2 | Child window corner radius |
| `FrameRounding` | 3 | Frame corner radius |
| `WindowBorderSize` | 0 | No window border |
| `ScrollbarSize` | 14 | Scrollbar width |
| `ScrollbarRounding` | 2 | Scrollbar corner radius |
| `TabBarOverlineSize` | 2 | Tab bar overline thickness |
| `GrabRounding` | 2 | Grab handle corner radius |
| `ItemSpacing` | [10, 6] | Space between items |
| `IndentSpacing` | 22 | Tree indent depth |
| `FramePadding` | [7, 4] | Frame content padding |
| `Alpha` | 1 | Global opacity |

### 13.2 Color Palette

| Element | Color | Hex | Description |
|---------|-------|-----|-------------|
| Text | White | `#FFFFFF` | Primary text |
| TextDisabled | Gray | `#7F7F7F` | Disabled text |
| WindowBg | Dark gray | `#202020FD` | Window background (near-opaque) |
| PopupBg | Darker gray | `#1C1C1CFD` | Popup background |
| FrameBg | Near-black | `#0F0F0FEF` | Input field background |
| FrameBgHovered | Blue tint | `#566AFF66` | Hovered input |
| FrameBgActive | Blue tint | `#566AFFAA` | Active input |
| **Primary accent** | **Blue** | **`#566AFF`** | **Buttons, highlights, checks** |
| Button | Blue/semi | `#566AFF66` | Button default |
| ButtonHovered | Blue | `#566AFF` | Button hover |
| ButtonActive | Dark blue | `#394CAB` | Button pressed |
| CheckMark | Blue | `#566AFF` | Checkbox mark |
| SliderGrab | Blue | `#5767FF` | Slider handle |
| Header | Blue/semi | `#566AFF4F` | Header background |
| Tab | Blue | `#424CB1DB` | Active tab |
| Separator | Light gray | `#BABABA` | Separator line |
| TableHeaderBg | Dark | `#0F0F0FA5` | Table header |
| TableBorderStrong | Black | `#0F0F0F` | Strong table border |
| TableBorderLight | Blue | `#566AFF` | Light table border |
| TableRowBg | Dark gray | `#2B2B2BA0` | Table row |
| TableRowBgAlt | Darker gray | `#242424A0` | Alternating row |
| TextLink | Blue | `#3366FF` | Hyperlinks |
| ModalWindowDimBg | Near-black | `#0F0F0FE5` | Modal overlay |

**Design language**: Dark theme with `#566AFF` blue accent. Very consistent with TM2020's overall dark/neon aesthetic.

---

## 14. Browser HTML/CSS Equivalents

### 14.1 Element Mapping

| ManiaLink Element | HTML Equivalent | CSS Properties Needed |
|-------------------|----------------|----------------------|
| `<manialink>` | `<div class="manialink-root">` | `position: relative; width: 320vmin; height: 180vmin; overflow: hidden;` |
| `<frame>` | `<div>` | `position: absolute;` (with Y-axis inversion) |
| `<framemodel>` | `<template>` | Not rendered |
| `<frameinstance>` | JS `cloneNode()` | Clone template content |
| `<quad>` | `<div>` or `<img>` | `position: absolute; background-image/color;` |
| `<label>` | `<span>` or `<p>` | `position: absolute; font-*; color;` |
| `<entry>` | `<input type="text">` | `position: absolute;` |
| `<textedit>` | `<textarea>` | `position: absolute; font-family: monospace;` |
| `<fileentry>` | `<input type="file">` | `position: absolute;` |
| `<gauge>` | `<progress>` or `<div>` | `position: absolute;` with inner width% div |
| `<graph>` | `<canvas>` or `<svg>` | Chart.js, D3.js, or similar |
| `<audio>` | `<audio>` | Standard HTML5 audio |
| `<video>` | `<video>` | Standard HTML5 video |
| `<minimap>` | `<canvas>` | Custom 2D rendering |
| `<dico>` | i18next / i18n lib | Translation system |
| `<include>` | `fetch()` + DOM insert | Async include |

### 14.2 Coordinate System Conversion

ManiaLink coordinates must be converted for browser rendering:

```javascript
// ManiaLink: origin at center, Y-up, 320x180 viewport
// Browser: origin at top-left, Y-down, variable viewport

function manialinkToCSS(mlX, mlY, mlW, mlH, halign, valign) {
  // Convert to top-left origin
  let cssLeft = mlX + 160;  // ML range [-160,160] -> CSS range [0,320]
  let cssTop = 90 - mlY;    // ML Y-up -> CSS Y-down

  // Adjust for alignment anchor
  let transformX = 0, transformY = 0;
  if (halign === 'center') transformX = -50;
  if (halign === 'right') transformX = -100;
  if (valign === 'center') transformY = -50;
  if (valign === 'bottom') transformY = -100;

  return {
    left: `${(cssLeft / 320) * 100}%`,
    top: `${(cssTop / 180) * 100}%`,
    width: `${(mlW / 320) * 100}%`,
    height: `${(mlH / 180) * 100}%`,
    transform: `translate(${transformX}%, ${transformY}%)`
  };
}
```

### 14.3 Style System Mapping

| ManiaLink | CSS Equivalent |
|-----------|---------------|
| `bgcolor="F00A"` | `background-color: rgba(255, 0, 0, 0.67);` |
| `opacity="0.5"` | `opacity: 0.5;` |
| `textsize="4"` | `font-size: calc(4 * var(--ml-unit));` |
| `textcolor="FFF"` | `color: #FFFFFF;` |
| `halign="center"` | `transform: translateX(-50%);` |
| `valign="center"` | `transform: translateY(-50%);` |
| `hidden="1"` | `display: none;` |
| `scale="1.5"` | `transform: scale(1.5);` |
| `rot="45"` | `transform: rotate(45deg);` |
| `style="Bgs1" substyle="BgWindow1"` | Background image from sprite sheet |

### 14.4 Animation Mapping

| ManiaLink AnimMgr | CSS/JS Equivalent |
|-------------------|-------------------|
| `EaseOutQuad` | `cubic-bezier(0.25, 0.46, 0.45, 0.94)` |
| `EaseInOutQuad` | `cubic-bezier(0.455, 0.03, 0.515, 0.955)` |
| `EaseOutBack` | `cubic-bezier(0.175, 0.885, 0.32, 1.275)` |
| `EaseOutBounce` | JS function (no CSS equivalent) |
| `EaseOutElastic` | JS function (no CSS equivalent) |
| `Linear` | `linear` |
| `AnimMgr.Add(ctrl, xml, dur, ease)` | `element.animate([...], { duration, easing })` or CSS transitions |

---

## 15. Unknowns and Gaps

### 15.1 Known Unknowns (Need Further RE)

| Area | Gap | Priority |
|------|-----|----------|
| CControlLayout algorithms | How does the layout engine resolve positions, sizes, and overflow? | HIGH |
| CControlStyle internal format | What properties does CControlStyle store and how are they resolved? | HIGH |
| Frame3d rendering | How do 3D frames (`CGameManialink3dWorld/Mood/Style`) render 3D content in ManiaLink? | MEDIUM |
| CControlEngine update order | Exact per-frame update order between layout, effects, focus, and values passes | MEDIUM |
| ManiaLink XML parser details | How does `CGameManialinkPage::SetContents` parse XML and build the control tree? | MEDIUM |
| CGameManialinkBrowser navigation | How does the browser handle ManiaLink-to-ManiaLink navigation and history? | LOW |
| CGameManialinkOldTable | What was the old table format and is it still supported? | LOW |
| CGameManialinkArrow | When is this used and what does it render? | LOW |
| CGameManialinkPlayerList | How does this differ from a frame with label children? | LOW |
| Style sprite sheet format | How are built-in quad styles stored on disk? | MEDIUM |

### 15.2 What We Know Well (60%+)

- Complete class hierarchy (all 70 UI classes enumerated)
- ManiaLink XML elements and attributes (community-documented)
- Coordinate system and layout basics
- ManiaScript event model and control API
- Animation system and easing functions
- HUD module architecture
- Card widget system
- Openplanet UI theme parameters

### 15.3 What Remains Poorly Understood (20%)

- Native CControl rendering pipeline internals
- CControlLayout algorithm specifics
- CControlStyleSheet binary format
- Frame3d / 3D-in-UI rendering
- ManiaLink parser implementation details
- How CGameManialinkManager maps XML elements to CControl instances
- Performance characteristics and rendering optimization strategies
- Built-in style sprite sheet asset format

---

## Sources

- Binary RTTI: `class_hierarchy.json` (5,886 lines, 2,027 Nadeo classes)
- Subsystem analysis: `13-subsystem-class-map.md` (Section 4: UI/Control System)
- Openplanet intelligence: `19-openplanet-intelligence.md` (Editor UI structure)
- Community knowledge: `29-community-knowledge.md` (ManiaScript references)
- Openplanet theme: `Trackmania/Openplanet/DefaultStyle.toml`
- [Trackmania Wiki - Manialinks](https://wiki.trackmania.io/en/ManiaScript/UI-Manialinks/Manialinks)
- [ManiaPlanet Documentation - Getting Started](https://doc.maniaplanet.com/manialink/getting-started)
- [ManiaPlanet Documentation - ManiaScript in Manialink](https://doc.maniaplanet.com/maniascript/maniascript-in-manialink)
- [ManiaPlanet Documentation - ManiaLink Styles](https://doc.maniaplanet.com/manialink/references/manialink-styles)
- [ManiaScript Community Documentation](https://maniaplanet-community.gitbook.io/maniascript/manialink/manialinks)
- [ManiaScript Reference (BigBang1112)](https://github.com/BigBang1112/maniascript-reference)
- [ManiaScript Reference (boss-bravo)](https://maniascript.boss-bravo.fr/)
- [ManiaPlanet Library Manialink](https://github.com/maniaplanet/library-manialink)
- [MLHook Openplanet Plugin](https://openplanet.dev/plugin/mlhook)
- [CMlScriptIngame Reference](https://maniaplanet.github.io/maniascript-reference/struct_c_ml_script_ingame.html)

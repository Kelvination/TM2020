# Trackmania 2020 Networking Deep Dive

**Binary**: `Trackmania.exe` (Trackmania 2020 by Nadeo/Ubisoft)
**Date**: 2026-03-27
**Source**: Ghidra 12.x decompilation, RTTI class extraction, debug string analysis
**Purpose**: Exhaustive networking documentation for browser engine recreation

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Authentication Tutorial](#2-authentication-tutorial)
3. [Authentication Flow (Decompiled)](#3-authentication-flow-decompiled)
4. [HTTP Client Architecture](#4-http-client-architecture)
5. [API Reference](#5-api-reference)
6. [Web Services Task Taxonomy](#6-web-services-task-taxonomy)
7. [Game Protocol (TCP+UDP)](#7-game-protocol-tcpudp)
8. [Real-time Multiplayer Protocol](#8-real-time-multiplayer-protocol)
9. [XML-RPC Dedicated Server Protocol](#9-xml-rpc-dedicated-server-protocol)
10. [Voice and Text Chat](#10-voice-and-text-chat)
11. [Anti-Cheat System](#11-anti-cheat-system)
12. [Matchmaking](#12-matchmaking)
13. [File Transfer and Ghost Upload System](#13-file-transfer-and-ghost-upload-system)
14. [Complete Class Taxonomy](#14-complete-class-taxonomy)
15. [Browser Multiplayer Architecture](#15-browser-multiplayer-architecture)
16. [Minimum Viable Online Specification](#16-minimum-viable-online-specification)
17. [Key Unknowns](#17-key-unknowns)
18. [Sequence Diagrams](#18-sequence-diagrams)

---

## 1. Architecture Overview

The networking subsystem is a deeply layered architecture spanning 11 logical layers, from raw sockets up to game-specific online services.

```
+=========================================================================+
|  Layer 11: Game Logic / ManiaScript                                     |
|    CGameCtnNetwork, CGameManiaPlanetNetwork, CGameNetwork               |
|    CPlaygroundClient, CGameNetPlayerInfo                                |
+=========================================================================+
|  Layer 10: Game Network Forms (Wire Messages)                           |
|    CGameNetForm, CGameNetFormPlayground, CGameNetFormTimeSync           |
|    CGameNetFormPlaygroundSync, CGameNetFormVoiceChat                    |
+=========================================================================+
|  Layer 9: Web Services Facade                                           |
|    CWebServices (297 classes)                                           |
|    CWebServicesTask_*, CWebServicesTaskResult_*, 18 Service Managers    |
+=========================================================================+
|  Layer 8: Nadeo Services API                                            |
|    CNetNadeoServices, CNetNadeoServicesTask_* (175+ task classes)       |
|    Domains: core.trackmania.nadeo.live, *.nadeo.club                    |
+=========================================================================+
|  Layer 7: Ubisoft Services API                                          |
|    CNetUbiServices, CNetUbiServicesTask_* (30+ task classes)            |
|    Domain: public-ubiservices.ubi.com                                   |
+=========================================================================+
|  Layer 6: Ubisoft Connect / UPC SDK                                     |
|    CNetUplayPC, CNetUplayPCTask_* (9 task classes)                      |
|    DLL: upc_r2_loader64.dll                                             |
+=========================================================================+
|  Layer 5: XML-RPC Protocol                                              |
|    CXmlRpc, CXmlRpcEvent, CGameServerScriptXmlRpc                      |
|    xmlrpc-c library (static)                                            |
+=========================================================================+
|  Layer 4: Master Server (Legacy)                                        |
|    CNetMasterServer, CNetMasterServerTask_* (15 task classes)           |
|    CGameMasterServer, CGameMasterServerTask_*                           |
+=========================================================================+
|  Layer 3: File Transfer                                                 |
|    CNetFileTransfer, CNetFileTransferDownload/Upload/Nod                |
|    CGameNetFileTransfer, CGameNetDataDownload                           |
+=========================================================================+
|  Layer 2: Network Engine                                                |
|    CNetEngine, CNetServer, CNetClient, CNetConnection                  |
|    CNetHttpClient (262 CNet* classes total)                             |
+=========================================================================+
|  Layer 1: Transport / Platform                                          |
|    WS2_32 (Winsock2), libcurl (static), OpenSSL 1.1.1t+quic (static)   |
|    CNetSystem, CNetIPSource, CNetUPnP, CNetIPC                         |
+=========================================================================+
|  Layer 0: External Services                                             |
|    UPC SDK (upc_r2_loader64.dll)                                        |
|    Vivox (VoiceChat.dll)                                                |
|    XMPP (*.chat.maniaplanet.com)                                        |
+=========================================================================+
```

### State Machine Architecture

The game network operates as a state machine driven by `CGameCtnNetwork::MainLoop_*` methods. The states are:

```
                                    +------------------+
                                    |    Terminated    |
                                    +------------------+
                                           ^
                                           |
+--------+    +-------+    +----------+    +-------------------+    +-------------------+
| Menus  |--->| SetUp |--->| Prepare  |--->| PlaygroundPrepare |--->| PlaygroundPlay    |
+--------+    +-------+    +----------+    +-------------------+    +-------------------+
    |             |                                                        |
    |             |                                                        v
    |             |                                                 +-------------------+
    |             +<------------------------------------------------| PlaygroundExit    |
    |                                                               +-------------------+
    |
    +---> Menus_Lan
    +---> Menus_Internet
    +---> Menus_DialogJoin
    +---> Menus_ApplyCommand
    +---> SpectatorSwitch
```

**Evidence**: String references at addresses `0x141c2b328` through `0x141c2dae0`.

### Decompiled State Machine Details

From `CGameCtnNetwork__MainLoop_Menus` (at `FUN_140af9a40`):
- Allocates a 0x48-byte state context object with vtable at `PTR_FUN_141c2e840`
- State field at offset +0x08, with states:
  - `0x0000` = Initial state (first entry, may trigger internet connection)
  - `0x0EA5` = [UNKNOWN - intermediate state, decimal 3749]
  - `0x0EA9` = Sub-state processing (calls `FUN_140afa000`)
  - `0x0EAE` = [UNKNOWN - intermediate state, decimal 3758]
  - `0x0EC1` = [UNKNOWN - intermediate state, decimal 3777]
- Checks global flags at `DAT_141fbbee8` and `DAT_141fbbf0c` for network connectivity state
- Sub-state at offset +0x30 drives menu-level logic (values 0, 1, 2)
- Offset +0x44 stores a menu command type, derived from `param_1[0x5b]`

From `CGameCtnNetwork__MainLoop_SetUp` (at `FUN_140afc320`):
- Allocates a 0x20-byte state context with vtable at `PTR_FUN_141b68250`
- State field at offset +0x08, with states:
  - `0x0000` = Initial (calls `FUN_140bd1180` for setup)
  - `0x125F` = [UNKNOWN - decimal 4703]
  - `0x1271` = [UNKNOWN - decimal 4721]
  - `0x1292` = [UNKNOWN - decimal 4754, network connection state]
  - `0x129D` = [UNKNOWN - decimal 4765]
- Calls `FUN_140bc5a00` (network subsystem init) and `FUN_140bc1a90` during completion
- Checks `DAT_141fbbee8`/`DAT_141fbbf0c` for ongoing network flags

From `CGameCtnNetwork__MainLoop_PlaygroundPlay` (at `FUN_140aff380`):
- Simplest loop -- allocates 0x18-byte context with vtable at `PTR_FUN_141b683c0`
- Only state 0 = initial, immediately sets `*param_3 = 0` (result code)
- Cleanup via virtual call at vtable+8 then sets `*param_2 = -1`

### Network Update Cycle (Deterministic)

The per-frame network update follows a strict order:

```
1. CGameCtnNetwork::NetUpdate_BeforePhy   (0x141c2b348)
   - Receive remote inputs and state updates
   - Buffer for deterministic consumption

2. Physics Step (deterministic simulation tick)
   - All clients simulate identically given same inputs
   - CSmArenaPhysics::Players_BeginFrame initiates

3. CGameCtnNetwork::NetUpdate_AfterPhy    (0x141c2b388)
   - Send local results, positions, and completed inputs
   - CGameCtnNetwork::PlaygroundSync_UpdateInfos (0x141cf75d8)

4. CGameCtnNetwork::NetLoop_Synchronize   (0x141c49c28)
   - CGameCtnNetwork::SynchronizeGameTimer (0x141c49bb0)
   - Ensures all clients share the same game timer
```

**Evidence**: Debug strings at listed addresses; the BeforePhy/AfterPhy naming convention confirms deterministic lockstep.

---

## 2. Authentication Tutorial

This section is a practical guide for implementing authentication in a browser client. It synthesizes information from decompiled binary analysis, Openplanet plugin source code, and community-verified API behavior.

### End-to-End Authentication Overview

```
+--------+     +--------+     +--------+     +--------+     +--------+
| Step 1 |---->| Step 2 |---->| Step 3 |---->| Step 4 |---->| Step 5 |
| Ubi    |     | Ubi    |     | Nadeo  |     | Get    |     | Use    |
| Login  |     | Session|     | Token  |     | Audience|    | APIs   |
|        |     |        |     | Exchg  |     | Token  |     |        |
+--------+     +--------+     +--------+     +--------+     +--------+
  Email/PW      Ubi ticket     Ubi session    Core token     nadeo_v1
  or UPC SDK    -> session     -> Nadeo JWT   -> audience    t=<tok>
                                              specific tok
```

### Token Types and Audiences [VERIFIED]

There are three distinct audiences, each granting access to different API domains:

| Audience | API Domain | Token Source | Purpose |
|----------|-----------|-------------|---------|
| `NadeoServices` | `prod.trackmania.core.nadeo.online` | Direct from auth exchange | Core APIs: auth, maps, records, accounts |
| `NadeoLiveServices` | `live-services.trackmania.nadeo.live` | Exchange from NadeoServices token | Live APIs: leaderboards, competitions, clubs |
| `NadeoLiveServices` | `meet.trackmania.nadeo.club` | Same as above | Meet APIs: matchmaking, ranked |

**DEPRECATED** (as of 2024-01-31): `NadeoClubServices` audience. Now maps to `NadeoLiveServices`.

Source: Openplanet NadeoServices plugin (`NadeoServices/NadeoServices.as`) -- VERIFIED against running game.

### JWT Structure [VERIFIED]

Nadeo access tokens are JWTs (JSON Web Tokens). Decoded, they contain:

```
Header: { "typ": "JWT", "alg": "..." }
Payload: {
  "jti": "<unique-token-id>",
  "iss": "NadeoServices",
  "aud": "NadeoServices" | "NadeoLiveServices",
  "iat": <issued-at-unix-timestamp>,
  "rat": <refresh-at-unix-timestamp>,
  "exp": <expiry-unix-timestamp>,
  "sub": "<account-id-uuid>",
  ...
}
```

**Token Lifetime** [VERIFIED from Openplanet]: 55 minutes effective lifetime + random 1-60 seconds jitter added by the client before refresh. The Openplanet plugin notes "this is intentionally mimicking Nadeo's code" for the retry timing.

### Authentication Flow Diagram

```
Browser Client             Auth Proxy Server          Ubisoft APIs              Nadeo APIs
     |                          |                         |                         |
     | 1. Login(email, pw)      |                         |                         |
     |------------------------->|                         |                         |
     |                          |                         |                         |
     |                          | 2. POST /v3/profiles/sessions                     |
     |                          | Headers:                |                         |
     |                          |   Ubi-AppId: 86263886-...                         |
     |                          |   Authorization: Basic  |                         |
     |                          |     base64(email:pw)    |                         |
     |                          |------------------------>|                         |
     |                          |                         |                         |
     |                          | 3. Response:            |                         |
     |                          |   { ticket, sessionId,  |                         |
     |                          |     expiration, ... }   |                         |
     |                          |<------------------------|                         |
     |                          |                         |                         |
     |                          | 4. POST /v2/authentication/token/ubiservices      |
     |                          | Headers:                                          |
     |                          |   Content-Type: application/json                  |
     |                          |   Authorization: ubi_v1 t=<ticket>                |
     |                          |-------------------------------------------------->|
     |                          |                                                   |
     |                          | 5. Response:                                      |
     |                          |   { accessToken (JWT), refreshToken }             |
     |                          |<--------------------------------------------------|
     |                          |                         |                         |
     | 6. { accessToken,        |                         |                         |
     |      refreshToken }      |                         |                         |
     |<-------------------------|                         |                         |
     |                          |                         |                         |
     | 7. GET /api/endpoint     |                         |                         |
     | Headers:                 |                         |                         |
     |   Authorization: nadeo_v1 t=<accessToken>          |                         |
     |-------------------------------------------------------------...------------->|
     |                          |                         |                         |
```

### Step-by-Step Walkthrough

**Step 1: Ubisoft Session** [SPECULATIVE -- community-documented, not from decompilation]

The native game uses `UPC_TicketGet()` to obtain a UPlay ticket from the running Ubisoft Connect client. For browser/third-party access, the community has documented an alternative using email/password:

```
POST https://public-ubiservices.ubi.com/v3/profiles/sessions
Headers:
  Content-Type: application/json
  Ubi-AppId: 86263886-327a-4328-ac69-527f0d20a237
  Authorization: Basic <base64(email:password)>
Body: (empty or {})

Response:
{
  "ticket": "<ubiservices-ticket>",
  "sessionId": "<session-uuid>",
  "expiration": "2026-03-28T12:00:00Z",
  "platformType": "uplay",
  ...
}
```

The `Ubi-AppId` value `86263886-327a-4328-ac69-527f0d20a237` is the Trackmania 2020 application ID.

**Step 2: Nadeo Token Exchange** [VERIFIED from decompiled function at 0x140356160]

The decompiled function `nadeoservices_token_create_from_ubiservices_v2` creates a Nadeo access token from the Ubisoft session:

```
POST https://prod.trackmania.core.nadeo.online/v2/authentication/token/ubiservices
Headers:
  Content-Type: application/json
  Authorization: ubi_v1 t=<ubiservices-ticket>
Body:
{
  "audience": "NadeoServices"
}

Response:
{
  "accessToken": "<jwt>",
  "refreshToken": "<opaque-token>"
}
```

**Step 3: Audience-Specific Token** [VERIFIED from Openplanet]

To access Live or Meet APIs, exchange the NadeoServices token for an audience-specific token:

```
POST https://prod.trackmania.core.nadeo.online/v2/authentication/token/nadeoservices
Headers:
  Content-Type: application/json
  Authorization: nadeo_v1 t=<nadeoservices-access-token>
Body:
{
  "audience": "NadeoLiveServices"
}

Response:
{
  "accessToken": "<jwt-for-live-services>",
  "refreshToken": "<refresh-token>"
}
```

**Step 4: Token Refresh** [VERIFIED from debug string `nadeoservices_token_refresh_v2` at 0x141b85ef0]

```
POST https://prod.trackmania.core.nadeo.online/v2/authentication/token/refresh
Headers:
  Content-Type: application/json
  Authorization: nadeo_v1 t=<current-access-token>
Body:
{
  "refreshToken": "<refresh-token>"
}

Response:
{
  "accessToken": "<new-jwt>",
  "refreshToken": "<new-refresh-token>"
}
```

**Retry Strategy** [VERIFIED from Openplanet]: On failure, use exponential backoff: 1s, 2s, 4s, 8s, 16s, ...

### All Authentication APIs (from Binary)

| API Request Name | Binary Address | HTTP Method | Purpose |
|-----------------|----------------|-------------|---------|
| `nadeoservices_token_create_from_basic_v2` | `0x141b85ad8` | POST | Basic credentials auth (email/pw, debug/dev) |
| `nadeoservices_token_create_from_ubiservices_v2` | `0x141b85ce8` | POST | Production auth via UbiServices ticket |
| `nadeoservices_token_create_from_nadeoservices_v2` | `0x141b862a0` | POST | Token-to-token exchange (audience swap) |
| `nadeoservices_token_refresh_v2` | `0x141b85ef0` | POST | Token refresh |

### Account ID and Login Conversion [VERIFIED from Openplanet]

Trackmania uses two ID formats interchangeably:

- **Account ID**: Standard hyphenated UUID (e.g., `3fa85f64-5717-4562-b3fc-2c963f66afa6`)
- **Login**: Base64-encoded UUID bytes (e.g., `P6hfZFcXRWKz/CyWP2avpg==`)

```
Account ID -> Login:
  Remove hyphens -> hex string -> decode hex to bytes -> base64 encode

Login -> Account ID:
  Base64 decode -> hex encode -> insert hyphens (8-4-4-4-12 pattern)
```

### Authorization Header Format [VERIFIED from Openplanet]

All Nadeo API calls use:
```
Authorization: nadeo_v1 t=<access-token>
```

This is NOT a standard Bearer token format. The `nadeo_v1` prefix and `t=` parameter are specific to Nadeo's auth system.

---

## 3. Authentication Flow (Decompiled)

### Complete Authentication Chain

The authentication system uses a 4-step token exchange chain. This is the most critical system for browser recreation.

```
Step 1: UPC Ticket                    Step 2: UbiServices Session
+---------------------------+         +---------------------------+
| Ubisoft Connect Client    |         | public-ubiservices.ubi.com|
| (upc_r2_loader64.dll)    |         | /v3/profiles/sessions     |
|                           |         |                           |
| UPC_TicketGet() --------->|         | POST with UPC ticket      |
| Returns: UPlay ticket     |-------->| Returns: Ubi-AppId header |
| (opaque base64 blob)     |         | + access_token + sessionId|
+---------------------------+         +---------------------------+
                                                   |
                                                   v
Step 3: Nadeo Token Exchange          Step 4: Token Refresh
+---------------------------+         +---------------------------+
| core.trackmania.nadeo.live|         | core.trackmania.nadeo.live|
| /v2/authentication/token/ |         | /v2/authentication/token/ |
| ubiservices               |         | refresh                   |
|                           |         |                           |
| POST with Ubi session ----+         | POST with refreshToken    |
| Returns:                  |         | Returns: new accessToken  |
|   accessToken (JWT)       |         |   + new refreshToken      |
|   refreshToken            |         +---------------------------+
+---------------------------+
```

### Step 1: Ubisoft Connect SDK (UPC) [VERIFIED from binary]

**DLL**: `upc_r2_loader64.dll` loaded at `0x14285ab28`
**Direct import**: `UPC_TicketGet` at IAT `0x1428c80d2`

The UPC SDK is initialized and ticked every frame:

| UPC Function | Address | Purpose |
|-------------|---------|---------|
| `UPC_ContextCreate` | `0x141a12950` | Create UPC context |
| `UPC_ContextFree` | `0x141a12968` | Destroy UPC context |
| `UPC_Update` | `0x141a12978` | Per-frame tick |
| `UPC_Cancel` | `0x141a12988` | Cancel async operation |
| `UPC_ErrorToString` | `0x141a12998` | Error messages |
| `UPC_EventRegisterHandler` | `0x141a129b0` | Event callbacks |
| `UPC_TicketGet` | IAT `0x1428c80d2` | Obtain UPlay ticket |
| `UPC_StoreProductListGet` | `0x141a129d0` | Store product listing |
| `UPC_ProductListGet` | `0x141a12a08` | Owned products query |

**Cloud Streaming Support** (separate set of UPC APIs):

| Function | Address |
|----------|---------|
| `UPC_StreamingCurrentUserCountryGet` | `0x141a12a38` |
| `UPC_StreamingDeviceTypeGet` | `0x141a12a88` |
| `UPC_StreamingInputGamepadTypeGet` | `0x141a12aa8` |
| `UPC_StreamingInputTypeGet` | `0x141a12ad0` |
| `UPC_StreamingNetworkDelayForInputGet` | `0x141a12af0` |
| `UPC_StreamingNetworkDelayForVideoGet` | `0x141a12b18` |
| `UPC_StreamingNetworkDelayRoundtripGet` | `0x141a12b40` |
| `UPC_StreamingResolutionGet` | `0x141a12b68` |
| `UPC_StreamingTypeGet` | `0x141a12ba8` |

The game has explicit support for Ubisoft's cloud gaming/streaming service.

**UPC Event Handling**:

| Event | Address |
|-------|---------|
| `UPC_Event_ProductAdded notification received. ProductId:%d Balance:%d` | `0x141a1e9b0` |
| `UPC_Event_ProductBalanceUpdated notification received. ProductId:%d New Balance:%d` | `0x141a1ea00` |
| `UPC_Event_ProductOwnershipUpdated notification received. ProductId:%d New Ownership:%d` | `0x141a1ea60` |
| `UPC_Event_ProductStateUpdated notification received. ProductId:%d New State:%d` | `0x141a1eac0` |

### Step 2: UbiServices Session Creation

**Wrapper class**: `CNetUbiServices` (`0x141b7d880`)
**Task**: `CNetUbiServicesTask_CreateSession` (`0x141b7df80`)

API endpoints (templated):

| URL Template | Address | Purpose |
|-------------|---------|---------|
| `https://{env}public-ubiservices.ubi.com/{version}` | `0x141a1c5b0` | Main Ubisoft services |
| `https://public-ubiservices.ubisoft.cn/{version}` | `0x141a1c5e8` | China (GAAP-compliant) |
| `https://gaap.ubiservices.ubi.com:12000/{version}` | `0x141a1c628` | GAAP services (port 12000) |

The `{env}` placeholder allows switching between prod/staging/dev environments. The `{version}` is the API version (e.g., `v3`).

UbiServices SDK build path (from debug strings):
```
D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\harbourcommon\libraries\_fetch\
```

The "harbourcommon" namespace refers to Ubisoft's common services framework ("Harbour").

### Step 3: Nadeo Services Token Exchange

**Decompiled function**: `FUN_140356160` at `0x140356160`
**API name**: `nadeoservices_token_create_from_ubiservices_v2` (string at `0x141b85ce8`)

From the decompiled code:
```c
void FUN_140356160(undefined8 param_1, undefined8 param_2)
{
    // Sets API request name to "nadeoservices_token_create_from_ubiservices_v2"
    local_38 = "nadeoservices_token_create_from_ubiservices_v2";
    uStack_30 = 0x2e;   // String length = 46 bytes
    FUN_14010db20(&local_28, &local_38);   // String copy
    FUN_140355fe0(param_2, &local_28);     // Execute API request
    // ... cleanup
}
```

This is a thin wrapper that delegates to `FUN_140355fe0` (the actual HTTP request executor). The function at `0x140355fe0` constructs a POST request to `core.trackmania.nadeo.live` with the UbiServices session token.

### Step 4: Token Refresh

**API name**: `nadeoservices_token_refresh_v2` (string at `0x141b85ef0`)

Token fields:

| Field | Address |
|-------|---------|
| `"refreshToken"` | `0x141b85f50` |
| `"accessToken"` | `0x141b85f60` |

### All Authentication Token APIs

| API Request Name | Address | Purpose |
|-----------------|---------|---------|
| `nadeoservices_token_create_from_basic_v2` | `0x141b85ad8` | Basic/password auth (debug/dev) |
| `nadeoservices_token_create_from_ubiservices_v2` | `0x141b85ce8` | Production auth via UbiServices |
| `nadeoservices_token_create_from_nadeoservices_v2` | `0x141b862a0` | Token-to-token exchange (service-to-service) |
| `nadeoservices_token_refresh_v2` | `0x141b85ef0` | Token refresh |

### Authentication Task Classes (7 total)

| Task Class | Address | Purpose |
|-----------|---------|---------|
| `CNetNadeoServicesTask_AuthenticateWithBasicCredentials` | `0x141b85b08` | Dev/debug login |
| `CNetNadeoServicesTask_AuthenticateWithUbiServices` | `0x141b85d18` | Production login |
| `CNetNadeoServicesTask_AuthenticateWithUnsecureAccountId` | `0x141b85eb8` | [UNKNOWN] Insecure fallback? |
| `CNetNadeoServicesTask_AuthenticateCommon` | `0x141b9e6a0` | Shared auth logic |
| `CNetNadeoServicesTask_RefreshNadeoServicesAuthenticationToken` | `0x141b85f10` | Token refresh |
| `CNetNadeoServicesTask_GetAuthenticationToken` | `0x141b862d8` | Token retrieval |
| `CNetNadeoServicesTask_CheckLoginExists` | [class hierarchy] | Login validation |

### Connection Workflow (High-Level)

The full connection sequence orchestrated by CWebServices:

```
CWebServicesTask_Connect
  |
  +--> CWebServicesTask_ConnectToNadeoServices
  |      |
  |      +--> CNetUbiServicesTask_CreateSession
  |      |      (UPC ticket -> Ubi session)
  |      |
  |      +--> nadeoservices_token_create_from_ubiservices_v2
  |             (Ubi session -> Nadeo token)
  |
  +--> CWebServicesTask_PostConnect
         |
         +--> CWebServicesTask_PostConnect_UrlConfig
         |      (Fetch service URL configuration)
         |
         +--> CWebServicesTask_PostConnect_PlugInList
         |      (Download plugin list)
         |
         +--> CWebServicesTask_PostConnect_AdditionalFileList
         |      (Additional files)
         |
         +--> CWebServicesTask_PostConnect_BannedCryptedChecksumsList
         |      (Anti-cheat checksums)
         |
         +--> CWebServicesTask_PostConnect_Tag
         |      (Club tag initialization)
         |
         +--> CWebServicesTask_PostConnect_Zone
                (Zone/region initialization)
```

### Session Management Tasks

| Task | Address | Purpose |
|------|---------|---------|
| `CNetUbiServicesTask_CreateSession` | `0x141b7df80` | Create Ubi session |
| `CNetUbiServicesTask_RefreshSession` | `0x141b7e4d8` | Refresh Ubi session |
| `CNetUbiServicesTask_DeleteSession` | `0x141b7e620` | Delete Ubi session |
| `CWebServicesTask_Connect` | `0x141b837f0` | Full connection |
| `CWebServicesTask_Disconnect` | `0x141b83aa0` | Full disconnect |
| `CWebServicesTask_DisconnectFromNadeoServices` | `0x141b9e008` | Nadeo disconnect |

### CGameCtnNetwork::ConnectToInternet

**Decompiled function**: `FUN_140b00500` at `0x140b00500`
**String reference**: `"CGameCtnNetwork::ConnectToInternet"` at `0x141c2ba20`

State machine flow:
```
State 0x0000: Initial / connecting
  - Allocates 0x40-byte connection context
  - Logs "Connecting to master server..."
  - Calls FUN_140bc5a00 (network subsystem init)
  - Calls FUN_140c8f930 (session params setup)
  |
  v
State 0x17D2 (6098): Connecting to master server
  - Sends "ClientConfigMessage" request
  |
  v
State 0x17E8 (6120): [UNKNOWN state]
  |
  v
State 0x17F1 (6129): [UNKNOWN state]
  |
  v
State 0x17F6 (6134): [UNKNOWN state]
  - On success: proceeds to connected state
  - On failure: logs error, optionally retries
  |
  v
Completion: cleanup via vtable, set *param_2 = -1
```

References CWebServices tasks at `this + 0x3B8`.

### Offline Fallback

Evidence for offline mode:
- `CWebServicesTask_CheckNetworkAvailability` exists as a task class
- `CGameNetwork::CheckInternetAtStart` (from methods list) runs at startup
- The state machine in `MainLoop_Menus` checks global flags `DAT_141fbbee8` / `DAT_141fbbf0c` before deciding whether to connect
- If both flags are zero, the game can proceed to menus without internet (`goto LAB_140af9c4e`)
- The `DemoToken*` system (see below) provides time-limited access with periodic server-side validation

---

## 4. HTTP Client Architecture

### curl Multi-Handle Architecture

**Source file**: `C:\Nadeo\CodeBase_tm-retail\Nadeo\Engines\NetEngine\source\NetHttpClient_Curl.cpp`
**Class**: `CNetHttpClient` at `0x141b7c610`

The HTTP client uses libcurl's multi interface for non-blocking I/O.

```
CNetHttpClient
  |
  +-- curl_multi handle (at this+0x78)
  |     Initialized in InternalConnect()
  |     Ticked in PlatformUpdate()
  |
  +-- Request Pool
  |     Each request = 0x1A8 byte structure
  |     Submitted via curl_multi_add_handle
  |
  +-- CNetEngine::UpdateHttpClients (per-frame tick)
        Calls curl_multi_perform
        Calls curl_multi_info_read for completions
```

### CNetHttpClient::InternalConnect (Decompiled)

**Address**: `0x1403050a0`

```c
bool FUN_1403050a0(longlong param_1)
{
    // param_1 = CNetHttpClient* this

    FUN_140117690(local_28, "CNetHttpClient::InternalConnect");  // Profile begin

    lVar1 = *DAT_1420ba2f8;           // = curl_multi_init() result (global)
    *(longlong*)(param_1 + 0x78) = lVar1;  // Store multi handle at this+0x78

    if (lVar1 == 0) {
        // Error path
        FUN_14010fab0(param_1 + 0x30, "Failed in call to curl_multi_init");
        // Sets error on log buffer at this+0x30
    }

    FUN_1401176a0(local_28, local_18);  // Profile end
    return lVar1 != 0;
}
```

Key insight: The curl multi handle comes from a **global** pointer at `DAT_1420ba2f8`, meaning there is one shared curl multi-handle for all HTTP clients.

### CNetHttpClient::CreateRequest (Decompiled)

**Address**: `0x14030c3f0`

Request creation details:
- Allocates **0x1A8 byte** request structure per request
- Constructs URL: prepends "/" if path is relative
- HTTP method selection via `param_3`:
  - `0` = POST
  - `1` = GET
  - `3-5` = [UNKNOWN methods, possibly PUT/DELETE/PATCH]

Headers set automatically:

| Header | Condition | Value |
|--------|-----------|-------|
| `Accept-Encoding` | GET requests (param_3 == 1) | `gzip,deflate` |
| `Content-Type` | POST/PUT with body | `application/binary` |
| `Range` | Partial requests | `bytes=N-M` |
| `Timezone` | param_10 != 0 | [UNKNOWN format] |

Request lifecycle:
```
InternalCreateRequest_Initiate   (0x141b7b700)  -- allocate + configure curl easy handle
InternalCreateRequest_AddOrReplaceHeader (0x141b7b790)  -- set headers
InternalCreateRequest_Launch     (0x141b7b830)  -- curl_multi_add_handle
PlatformUpdate                   (0x141b7b9a0)  -- curl_multi_perform tick
InternalTerminateReq             (0x141b7b8d0)  -- curl_multi_remove_handle + cleanup
```

### HTTP Client Methods (Full List)

| Method | Address | Purpose |
|--------|---------|---------|
| `CNetHttpClient::InternalConnect` | `0x141b7b5a0` | curl_multi_init |
| `CNetHttpClient::InternalDisconnect` | `0x141b7b6d0` | curl_multi_cleanup |
| `CNetHttpClient::InternalCreateRequest_Initiate` | `0x141b7b700` | curl_easy_init + config |
| `CNetHttpClient::InternalCreateRequest_AddOrReplaceHeader` | `0x141b7b790` | curl_slist_append |
| `CNetHttpClient::InternalCreateRequest_Launch` | `0x141b7b830` | curl_multi_add_handle |
| `CNetHttpClient::InternalTerminateReq` | `0x141b7b8d0` | curl_multi_remove_handle |
| `CNetHttpClient::PlatformUpdate` | `0x141b7b9a0` | curl_multi_perform |
| `CNetHttpClient::CreateRequest` | `0x141b7c950` | High-level request creation |
| `CNetHttpClient::TerminateReq` | `0x141b7c688` | High-level termination |
| `CNetHttpClient::PlatformInit` | [methods] | Platform-specific init |
| `CNetHttpClient::UpdateTransfertSizeCmd` | `0x141b7c748` | Transfer metrics |

### Cookie and Cache Management

| Feature | String | Address |
|---------|--------|---------|
| Cookie persistence | `"# Netscape HTTP Cookie File\n# https://curl.se/..."` | `0x1419fdef0` |
| Alt-Svc cache | `"# Your alt-svc cache. https://curl.se/..."` | `0x1419ff230` |

The presence of Alt-Svc caching suggests the game may opportunistically use HTTP/2 or HTTP/3 when servers advertise Alt-Svc headers.

### UbiServices SDK HTTP Layer

The UbiServices SDK has its own curl wrapper (separate from the game's):

| String | Address |
|--------|---------|
| `HttpRequestCurl::stepWaitForResume` | `0x141a24f20` |
| `HttpRequestCurl::stepWaitStatusCode` | `0x141a24f48` |
| `HttpRequestCurl::stepWaitForComplete` | `0x141a24f90` |

Build path: `D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\dependencies\_fetch\curl\lib\vtls\openssl.c`

### OpenSSL

**Version**: `OpenSSL 1.1.1t+quic  7 Feb 2023` (string at `0x141983c80`)

The `+quic` variant indicates QUIC protocol support is compiled in (via the quictls fork). Whether QUIC/HTTP3 is actively used is [UNKNOWN].

### CNetEngine HTTP Integration

| Method | Address | Notes |
|--------|---------|-------|
| `CNetEngine::UpdateHttpClients` | `0x141b7caa8` | Per-frame HTTP tick |
| `[Net] CNetSystem::Init() failed !` | `0x141b7d4b0` | Init failure |
| `[Net] CNetHttpClient::PlatformInit() failed !` | `0x141b7d4d8` | HTTP init failure |
| `[Net] HTTP: curl_version=` | `0x141b7b298` | Version logging at init |
| `CurlPerform` | `0x141b7b530` | Profiling marker |

### Dual-Threaded Processing

From debug strings:
```
CWebServices::Update_MainThread        (0x141b7dda8)  -- main thread: process results, update UI
CWebServices::Update_WebServicesThread  (0x141b7ddf0)  -- background: HTTP I/O
CWebServicesTaskScheduler::DispatchTasks (0x141b7dc78)  -- task dispatch
```

The web services layer uses a dedicated background thread for HTTP I/O, with results dispatched back to the main thread.

### ManiaScript HTTP API

Exposed to ManiaScript via:

| Class | Purpose |
|-------|---------|
| `CNetScriptHttpManager` | Script-accessible HTTP manager |
| `CNetScriptHttpRequest` | Script-accessible HTTP request |
| `CNetScriptHttpEvent` | Script-accessible HTTP event |
| `CHttpManager` | Higher-level HTTP manager |
| `CHttpClient_Internal` | Internal HTTP client |
| `CHttpRequest` | HTTP request object |
| `CHttpEvent` | HTTP event object |

---

## 5. API Reference

### Confidence Legend

Throughout this section:
- **[VERIFIED]** -- Confirmed from Openplanet plugin source, community tools, or decompiled URL strings
- **[SPECULATIVE]** -- Inferred from task class names following naming conventions; actual URL paths may differ
- **[COMMUNITY]** -- Documented by community API projects (e.g., trackmania.io, openplanet.dev) but not confirmed from decompilation

### Domain Structure [VERIFIED]

| Domain | Address | Service Layer | Purpose |
|--------|---------|---------------|---------|
| `core.trackmania.nadeo.live` | `0x141b85858` | NadeoServices | Core game API (auth, maps, records) |
| `*.nadeo.live` | `0x141b7c6e0` | NadeoServices | Nadeo Live services (main API) |
| `*.nadeo.club` | `0x141b7c718` | NadeoServices | Club/community services |
| `*.maniaplanet.com` | `0x141b7c700` | NadeoServices | Legacy ManiaPlanet services |
| `public-ubiservices.ubi.com` | `0x141a1c5b0` | UbiServices | Ubisoft platform services |
| `public-ubiservices.ubisoft.cn` | `0x141a1c5e8` | UbiServices | China GAAP endpoint |
| `gaap.ubiservices.ubi.com:12000` | `0x141a1c628` | UbiServices | GAAP services |
| `http://test.nadeo.com` | `0x141b964c8` | Test | Test environment |
| `http://test2.nadeo.com` | `0x141b96510` | Test | Test environment 2 |
| `squad.chat.maniaplanet.com` | `0x141c444d0` | XMPP | Squad chat server |
| `channel.chat.maniaplanet.com` | `0x141c444f0` | XMPP | Channel chat server |

### Verified Base URLs [VERIFIED from Openplanet]

These URLs are confirmed from the working Openplanet NadeoServices plugin:

| Service | Base URL | Audience Token |
|---------|----------|---------------|
| **Core** | `https://prod.trackmania.core.nadeo.online` | `NadeoServices` |
| **Live** | `https://live-services.trackmania.nadeo.live` | `NadeoLiveServices` |
| **Meet** | `https://meet.trackmania.nadeo.club` | `NadeoLiveServices` |

### Inferred API Endpoint Map [SPECULATIVE]

> **Warning**: All URL paths in this section are speculative guesses based on task class naming conventions. They have NOT been observed in network traffic or confirmed from decompiled URL-construction code. Actual API paths may differ significantly. Community projects like trackmania.io have documented some of these endpoints, but this document only marks things as VERIFIED when confirmed from decompilation or Openplanet source.

Based on the task class naming pattern `CNetNadeoServicesTask_<Verb><Resource>`, we can infer the REST API structure. The naming convention maps to HTTP methods:

| Verb Prefix | HTTP Method | Example |
|-------------|-------------|---------|
| `Get` | GET | `GetMap` -> `GET /maps/{id}` |
| `Set` | PUT/PATCH | `SetMap` -> `PUT /maps/{id}` |
| `Create` | POST | `CreateSkin` -> `POST /skins` |
| `Add` | POST | `AddAccountMapFavorite` -> `POST /accounts/{id}/map-favorites` |
| `Remove` | DELETE | `RemoveAccountMapFavorite` -> `DELETE /accounts/{id}/map-favorites/{id}` |
| `Delete` | DELETE | `DeleteServer` -> `DELETE /servers/{id}` |
| `Upload` | POST (multipart) | `Upload` -> `POST /uploads` |
| `Patch` | PATCH | `PatchMapRecordSecureAttempt` -> `PATCH /map-records/secure-attempts/{id}` |
| `Incr` | POST/PATCH | `IncrAccountMapZen` -> `POST /accounts/{id}/map-zen/increment` |
| `Vote` | POST | `VoteMap` -> `POST /maps/{id}/votes` |

### Core API Endpoints [SPECULATIVE] (Inferred from Task Classes)

#### Authentication (prod.trackmania.core.nadeo.online) [VERIFIED]

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/v2/authentication/token/ubiservices` | `AuthenticateWithUbiServices` | POST |
| `/v2/authentication/token/basic` | `AuthenticateWithBasicCredentials` | POST |
| `/v2/authentication/token/nadeoservices` | `GetAuthenticationToken` | POST |
| `/v2/authentication/token/refresh` | `RefreshNadeoServicesAuthenticationToken` | POST |

#### Maps [SPECULATIVE paths, VERIFIED task classes exist]

| Inferred Endpoint | Task Class | Method | Confidence |
|-------------------|-----------|--------|-----------|
| `/maps/{mapId}` | `GetMap` | GET | SPECULATIVE |
| `/maps` | `GetMapList` | GET | SPECULATIVE |
| `/maps` | `SetMap` | PUT | SPECULATIVE |
| `/accounts/{accountId}/maps` | `GetAccountMapList` | GET | SPECULATIVE |
| `/maps/{mapId}/vote` | `GetMapVote` | GET | SPECULATIVE |
| `/maps/{mapId}/vote` | `VoteMap` | POST | SPECULATIVE |

#### Map Records / Leaderboards (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/map-records/secure-attempts` | `CreateMapRecordSecureAttempt` | POST |
| `/map-records/secure-attempts/{id}` | `PatchMapRecordSecureAttempt` | PATCH |
| `/map-records/attempts` | `SetMapRecordAttempt` | PUT |
| `/map-records` | `GetMapRecordList` | GET |
| `/accounts/{id}/map-records` | `GetAccountMapRecordList` | GET |

#### Campaigns / Seasons (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/campaigns` | `GetCampaignList` | GET |
| `/campaigns` | `SetCampaign` | PUT |
| `/campaigns/{id}/maps` | `AddMapListToCampaign` | POST |
| `/campaigns/{id}/maps` | `RemoveMapListFromCampaign` | DELETE |
| `/seasons/{id}` | `GetSeason` | GET |
| `/seasons` | `GetSeasonList` | GET |
| `/seasons` | `SetSeason` | PUT |
| `/accounts/{id}/seasons` | `GetAccountSeasonList` | GET |
| `/accounts/{id}/playable-seasons` | `GetAccountPlayableSeasonList` | GET |

#### Skins (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/skins` | `CreateSkin` | POST |
| `/skins/{id}` | `GetSkin` | GET |
| `/skins` | `GetSkinList` | GET |
| `/skins/creator` | `GetCreatorSkinList` | GET |
| `/accounts/{id}/skins` | `GetAccountSkinList` | GET |
| `/accounts/{id}/skin` | `SetAccountSkin` | PUT |
| `/accounts/{id}/skin` | `UnsetAccountSkin` | DELETE |

#### Item Collections (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/item-collections/{id}` | `GetItemCollection` | GET |
| `/item-collections` | `GetItemCollectionList` | GET |
| `/item-collections` | `SetItemCollection` | PUT |
| `/item-collections/{id}/versions` | `CreateItemCollectionVersion` | POST |
| `/item-collections/{id}/versions/{vId}` | `GetItemCollectionVersion` | GET |
| `/item-collections/{id}/activity-id` | `SetItemCollectionActivityId` | PUT |

#### Accounts & Identity (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/accounts/{id}/zone` | `GetAccountZone` | GET |
| `/accounts/zones` | `GetAccountZoneList` | GET |
| `/accounts/{id}/zone` | `SetAccountZone` | PUT |
| `/zones` | `GetZones` | GET |
| `/accounts/{id}/xp` | `GetAccountXp` | GET |
| `/accounts/display-names` | `GetAccountDisplayNameList` | GET |
| `/accounts/webservices-identity` | `GetWebServicesIdentityFromAccountId` | GET |
| `/accounts/from-webservices-identity` | `GetAccountIdFromWebServicesIdentity` | GET |

#### Clubs (*.nadeo.club)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/clubs/{id}` | `GetClub` | GET |
| `/clubs` | `GetClubList` | GET |
| `/accounts/{id}/club-tag` | `GetAccountClubTag` | GET |
| `/accounts/club-tags` | `GetAccountClubTagList` | GET |
| `/accounts/{id}/club-tag` | `SetAccountClubTag` | PUT |

#### Trophies (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/trophy/settings` | `GetTrophySettings` | GET |
| `/accounts/{id}/trophy/gain-history` | `GetAccountTrophyGainHistory` | GET |
| `/accounts/{id}/trophy/last-year-summary` | `GetAccountTrophyLastYearSummary` | GET |
| `/trophy/competition-match` | `SetTrophyCompetitionMatchAchievementResult` | POST |
| `/trophy/live-time-attack` | `SetTrophyLiveTimeAttackAchievementResult` | POST |

#### Prestige (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/prestige` | `GetAllPrestigeList` | GET |
| `/prestige/{id}` | `GetPrestigeList` | GET |
| `/prestige/mode-year-type` | `GetPrestigeListFromModeYearType` | GET |
| `/prestige/year/{year}` | `GetPrestigeListFromYear` | GET |
| `/accounts/{id}/prestige/current` | `GetAccountPrestigeCurrent` | GET |
| `/accounts/{id}/prestige` | `GetAccountPrestigeList` | GET |
| `/accounts/{id}/prestige/current` | `SetAccountPrestigeCurrent` | PUT |
| `/accounts/{id}/prestige/current` | `UnsetAccountPrestigeCurrent` | DELETE |

#### Squads / Party (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/squads` | `CreateSquad` | POST |
| `/squads/{id}` | `GetSquad` | GET |
| `/accounts/{id}/squad` | `GetAccountSquad` | GET |
| `/squads/{id}/invitations` | `AddSquadInvitation` | POST |
| `/squads/{id}/invitations/{invId}/accept` | `AcceptSquadInvitation` | POST |
| `/squads/{id}/invitations/{invId}/decline` | `DeclineSquadInvitation` | POST |
| `/squads/{id}/invitations/{invId}` | `RemoveSquadInvitation` | DELETE |
| `/squads/{id}/leave` | `LeaveSquad` | POST |
| `/squads/{id}/members/{mId}` | `RemoveSquadMember` | DELETE |
| `/squads/{id}/leader` | `SetSquadLeader` | PUT |

#### Uploads (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/uploads` | `CreateUpload` | POST |
| `/uploads/{id}` | `GetUpload` | GET |
| `/uploads/{id}` | `Upload` | PUT |
| `/uploads/{id}/parts` | `UploadPart` | POST |

#### Favorites (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/accounts/{id}/map-favorites` | `AddAccountMapFavorite` | POST |
| `/accounts/{id}/map-favorites` | `GetAccountMapFavoriteList` | GET |
| `/accounts/{id}/map-favorites/by-map-uid` | `GetAccountMapFavoriteListByMapUid` | GET |
| `/accounts/{id}/map-favorites/{fId}` | `RemoveAccountMapFavorite` | DELETE |
| `/accounts/{id}/skin-favorites` | `AddAccountSkinFavorite` | POST |
| `/accounts/{id}/skin-favorites` | `GetAccountSkinFavoriteList` | GET |
| `/accounts/{id}/skin-favorites/{fId}` | `RemoveAccountSkinFavorite` | DELETE |
| `/accounts/{id}/item-collection-favorites` | `AddAccountItemCollectionFavorite` | POST |
| `/accounts/{id}/item-collection-favorites` | `GetAccountItemCollectionFavoriteList` | GET |
| `/accounts/{id}/item-collection-favorites/{fId}` | `RemoveAccountItemCollectionFavorite` | DELETE |

#### Encrypted Packages / DRM (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/encrypted-packages` | `SetEncryptedPackage` | PUT |
| `/encrypted-packages` | `GetEncryptedPackageList` | GET |
| `/encrypted-packages/{id}/versions` | `CreateEncryptedPackageVersion` | POST |
| `/encrypted-packages/{id}/versions` | `GetEncryptedPackageVersionList` | GET |
| `/encrypted-packages/{id}/versions/{vId}/crypt-key` | `GetEncryptedPackageVersionCryptKey` | GET |
| `/encrypted-packages/{id}/account-key` | `GetEncryptedPackageAccountKey` | GET |
| `/accounts/{id}/encrypted-packages` | `GetAccountEncryptedPackageList` | GET |

#### Client Config / Telemetry (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/client/config` | `GetClientConfig` | GET |
| `/client/files` | `GetClientFileList` | GET |
| `/client/updater-file` | `GetClientUpdaterFile` | GET |
| `/client/caps` | `SetClientCaps` | PUT |
| `/client/log` | `AddClientLog` | POST |
| `/client/debug-info` | `AddClientDebugInfo` | POST |
| `/telemetry/map-session` | `AddTelemetryMapSession` | POST |

#### Servers (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/servers/{id}` | `GetServer` | GET |
| `/servers/{id}` | `SetServer` | PUT |
| `/servers/{id}` | `DeleteServer` | DELETE |

#### Activity / Match Reporting (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/activity/matches` | `Activity_CreateMatch` | POST |
| `/activity/matches/{id}` | `Activity_UpdateMatch` | PUT |
| `/activity/matches/{id}/result` | `Activity_ReportMatchResult` | POST |

#### Accounts / Misc (*.nadeo.live)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/accounts/{id}/map-zen` | `GetAccountMapZen` | GET |
| `/accounts/{id}/map-zen/increment` | `IncrAccountMapZen` | POST |
| `/accounts/{id}/subscriptions` | `GetAccountSubscriptionList` | GET |
| `/subscriptions` | `AddSubscription` | POST |
| `/subscriptions/psn` | `AddSubscriptionFromPSN` | POST |
| `/accounts/{id}/presence` | `SetAccountPresence` | PUT |
| `/accounts/{id}/presence` | `DeleteAccountPresence` | DELETE |
| `/accounts/{id}/policy-rule-values` | `GetAccountPolicyRuleValueList` | GET |
| `/profile-chunks` | `GetProfileChunkList` | GET |
| `/profile-chunks` | `SetProfileChunk` | PUT |
| `/profile-chunks/{id}` | `DeleteProfileChunk` | DELETE |
| `/visual-notification-url-info` | `GetVisualNotificationUrlInfo` | GET |
| `/waiting-queue` | `AddToWaitingQueue` | POST |
| `/driver-bot-groups` | `GetDriverBotGroupList` | GET |
| `/driver-bot-groups` | `AddDriverBotGroupList` | POST |
| `/driver-bot-groups/add-limit` | `AddDriverBotGroupList_GetLimit` | GET |

### UbiServices API Endpoints (Inferred)

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/v3/profiles/sessions` | `CreateSession` | POST |
| `/v3/profiles/sessions` | `RefreshSession` | PUT |
| `/v3/profiles/sessions` | `DeleteSession` | DELETE |
| `/v3/profiles` | `Profile_RetrieveProfileInfoList` | GET |
| `/v3/profiles/me/uplay` | `Profile_RetrieveUplayProfileInfoList` | GET |
| `/v3/profiles/platform` | `Profile_RetrieveProfileInfoListFromPlatform` | GET |
| `/v3/blocklist` | `Blocklist_Get` | GET |
| `/v3/friends` | `GetFriendList` | GET |
| `/v3/news` | `GetNews` | GET |
| `/v3/stats` | `GetStatList` | GET |
| `/v3/events/unsent` | `GetUnsentEvents` | GET |
| `/v3/notifications/check` | `CheckNewNotification` | GET |
| `/v3/notifications` | `SendNotification` | POST |
| `/v3/nda/accept` | `AcceptNDA` | POST |
| `/v3/beta-user-info` | `RetrieveBetaUserInfo` | GET |
| `/v3/legal-optins` | `RequestUserLegalOptinsStatus` | GET |
| `/v3/player-consents` | `PlayerConsents_GetConsent` | GET |
| `/v3/player-consents/acceptances` | `PlayerConsents_GetAcceptanceList` | GET |
| `/v3/player-preferences/standard` | `PlayerPreferences_GetStandardPreferences` | GET |
| `/v3/player-preferences/standard` | `PlayerPreferences_SetStandardPreferences` | PUT |

### UbiServices Party Endpoints

| Inferred Endpoint | Task Class | Method |
|-------------------|-----------|--------|
| `/v3/parties` | `Party_CreateParty` | POST |
| `/v3/parties/{id}` | `Party_GetPartyInfo` | GET |
| `/v3/parties/{id}` | `Party_UpdateParty` | PUT |
| `/v3/parties/{id}/invitations` | `Party_GetPartyInvitationList` | GET |
| `/v3/parties/{id}/invitations` | `Party_UpdateInvitation` | PUT |
| `/v3/parties/{id}/join-requests` | `Party_GetPartyJoinRequestList` | GET |
| `/v3/parties/{id}/members` | `Party_GetPartyMemberList` | GET |
| `/v3/parties/{id}/leave` | `Party_LeaveParty` | POST |
| `/v3/parties/{id}/max-member-limit` | `Party_SetMaxMemberLimit` | PUT |
| `/v3/parties/{id}/max-member-limit` | `Party_GetMaxMemberLimit` | GET |
| `/v3/parties/{id}/lock-state` | `Party_UpdateLockState` | PUT |
| `/v3/parties/{id}/renew-expiration` | `Party_RenewExpiration` | POST |
| `/v3/parties/{id}/first-party-session-id` | `Party_ChangeFirstPartySessionId` | PUT |
| `/v3/parties/{id}/first-party-session-info` | `Party_GetFirstPartySessionInfo` | GET |
| `/v3/parties/{id}/auto-remove-on-disconnect` | `Party_AutoRemovePartyMemberOnDisconnect` | PUT |

---

## 6. Web Services Task Taxonomy

### Overview

The web services layer consists of 562 classes across three prefixes:

| Prefix | Count | Role |
|--------|-------|------|
| `CNet*` | 262 | Low-level network engine + service tasks |
| `CWebServices*` | 297 | Game-facing facade + result types |
| `CGame*Network*` | 3 | Game-level network management |

### CNet* Class Breakdown (262 classes)

#### Core Network Engine (19 classes)

| Class | Purpose |
|-------|---------|
| `CNetNod` | Base class for all network objects |
| `CNetSystem` | Network system initialization |
| `CNetEngine` | Network engine (HTTP tick, connection management) |
| `CNetServer` | Game server (DoReception, DoSending, CheckDisconnections) |
| `CNetClient` | Game client (DoReception, DoSending, InitNetwork) |
| `CNetConnection` | TCP+UDP connection object |
| `CNetServerInfo` | Server metadata |
| `CNetClientInfo` | Client metadata |
| `CNetSource` | Network source |
| `CNetURLSource` | URL-based source |
| `CNetHttpClient` | HTTP client (curl wrapper) |
| `CNetHttpResult` | HTTP result |
| `CNetIPSource` | IP source management |
| `CNetUPnP` | UPnP port forwarding |
| `CNetIPC` | Inter-process communication |
| `CNetXmpp` | XMPP chat client |
| `CNetXmpp_Timer` | XMPP timer |
| `CNetScriptHttpManager` | ManiaScript HTTP |
| `CNetScriptHttpRequest` | ManiaScript HTTP request |
| `CNetScriptHttpEvent` | ManiaScript HTTP event |

#### Network Message Forms (8 classes)

| Class | Purpose |
|-------|---------|
| `CNetFormConnectionAdmin` | Connection management messages |
| `CNetFormEnumSessions` | Session enumeration |
| `CNetFormQuerrySessions` | Session queries (note: typo "Querry" in original) |
| `CNetFormTimed` | Timestamped messages |
| `CNetFormPing` | Ping/latency measurement |
| `CNetFormNewPing` | Updated ping protocol |
| `CNetFormRpcCall` | RPC invocations |
| `CNetFileTransferForm` | File transfer wire protocol |

#### File Transfer (4 classes)

| Class | Purpose |
|-------|---------|
| `CNetFileTransfer` | Base file transfer |
| `CNetFileTransferDownload` | Download handler |
| `CNetFileTransferUpload` | Upload handler |
| `CNetFileTransferNod` | Serialized object (Nod) transfer |

#### Master Server (16 classes)

| Class | Purpose |
|-------|---------|
| `CNetMasterHost` | Master host |
| `CNetMasterServer` | Master server connection |
| `CNetMasterServerDownload` | File downloads from master |
| `CNetMasterServerInfo` | Server info |
| `CNetMasterServerRequest` | Request base class |
| `CNetMasterServerRequestTask` | Async request task |
| `CNetMasterServerUptoDateCheck` | Version checking |
| `CNetMasterServerUserInfo` | User info from master |
| `CNetMasterServerTask_Connect` | Initial connection |
| `CNetMasterServerTask_GetApplicationConfig` | App config |
| `CNetMasterServerTask_GetClientConfigUrls` | Config URLs |
| `CNetMasterServerTask_GetWaitingParams` | Queue params |
| `CNetMasterServerTask_GetFeatureTimeLimit` | Feature time gates |
| `CNetMasterServerTask_CheckFeatureTimeLimit` | Feature access check |
| `CNetMasterServerTask_SetFeatureTimeUse` | Feature usage |
| ... (+ 5 more session/account tasks) |

#### UbiServices Tasks (30 classes)

**Session Management (3)**:
- `CNetUbiServicesTask_CreateSession`
- `CNetUbiServicesTask_RefreshSession`
- `CNetUbiServicesTask_DeleteSession`

**Profile & Social (7)**:
- `CNetUbiServicesTask_Profile_RetrieveProfileInfoList`
- `CNetUbiServicesTask_Profile_RetrieveProfileInfoListFromPlatform`
- `CNetUbiServicesTask_Profile_RetrieveProfileInfoListFromPlatformTypeAndUserId`
- `CNetUbiServicesTask_Profile_RetrieveUplayProfileInfoList`
- `CNetUbiServicesTask_Blocklist_Get`
- `CNetUbiServicesTask_GetFriendList`
- `CNetUbiServicesTask_GetNews`

**Party System (14)**:
- `CNetUbiServicesTask_Party_CreateParty`
- `CNetUbiServicesTask_Party_GetPartyInfo`
- `CNetUbiServicesTask_Party_GetPartyInvitationList`
- `CNetUbiServicesTask_Party_GetPartyJoinRequestList`
- `CNetUbiServicesTask_Party_GetPartyMemberList`
- `CNetUbiServicesTask_Party_GetMaxMemberLimit`
- `CNetUbiServicesTask_Party_GetFirstPartySessionInfo`
- `CNetUbiServicesTask_Party_LeaveParty`
- `CNetUbiServicesTask_Party_SetMaxMemberLimit`
- `CNetUbiServicesTask_Party_UpdateInvitation`
- `CNetUbiServicesTask_Party_UpdateLockState`
- `CNetUbiServicesTask_Party_UpdateParty`
- `CNetUbiServicesTask_Party_RenewExpiration`
- `CNetUbiServicesTask_Party_ChangeFirstPartySessionId`
- `CNetUbiServicesTask_Party_AutoRemovePartyMemberOnDisconnect`

**Player Preferences & Consent (5)**:
- `CNetUbiServicesTask_PlayerConsents_GetConsent`
- `CNetUbiServicesTask_PlayerConsents_GetAcceptanceList`
- `CNetUbiServicesTask_PlayerPreferences_GetStandardPreferences`
- `CNetUbiServicesTask_PlayerPreferences_SetStandardPreferences`
- `CNetUbiServicesTask_RequestUserLegalOptinsStatus`

**Misc (4)**:
- `CNetUbiServicesTask_AcceptNDA`
- `CNetUbiServicesTask_CheckNewNotification`
- `CNetUbiServicesTask_SendNotification`
- `CNetUbiServicesTask_GetStatList`
- `CNetUbiServicesTask_GetUnsentEvents`
- `CNetUbiServicesTask_RetrieveBetaUserInfo`

#### UPlay PC Tasks (11 classes)

| Class | Purpose |
|-------|---------|
| `CNetUplayPC` | UPlay PC wrapper |
| `CNetUplayPCUserInfo` | User info |
| `CNetUplayPCTask_Achievement_GetCompletionList` | Achievement queries |
| `CNetUplayPCTask_Achievement_Unlock` | Achievement unlocking |
| `CNetUplayPCTask_GetUserConsumableItemList` | Consumable items |
| `CNetUplayPCTask_GetFriendList` | Friends list |
| `CNetUplayPCTask_ShowBrowserUrl` | Open URL in overlay |
| `CNetUplayPCTask_Overlay_ShowMicroApp` | Overlay micro-apps |
| `CNetUplayPCTask_JoinSession` | Join game session |
| `CNetUplayPCTask_LeaveSession` | Leave game session |
| `CNetUplayPCTask_ShowInviteUI` | Invitation UI |

#### Nadeo Services Tasks (175 classes)

Categorized by service domain:

**Authentication (7)**: `AuthenticateWith*`, `RefreshNadeoServicesAuthenticationToken`, `GetAuthenticationToken`, `CheckLoginExists`

**Maps (10)**: `GetMap`, `GetMapList`, `SetMap`, `GetAccountMapList`, `GetMapVote`, `VoteMap`, `AddAccountMapFavorite`, `GetAccountMapFavoriteList`, `GetAccountMapFavoriteListByMapUid`, `RemoveAccountMapFavorite`

**Map Records (5)**: `CreateMapRecordSecureAttempt`, `PatchMapRecordSecureAttempt`, `SetMapRecordAttempt`, `GetMapRecordList`, `GetAccountMapRecordList`

**Campaigns (4)**: `GetCampaignList`, `SetCampaign`, `AddMapListToCampaign`, `RemoveMapListFromCampaign`

**Seasons (8)**: `GetSeason`, `GetSeasonList`, `SetSeason`, `AddMapListToSeason`, `RemoveMapListFromSeason`, `GetAccountSeasonList`, `GetAccountPlayableSeasonList`

**Item Collections (10)**: `GetItemCollection`, `GetItemCollectionList`, `GetItemCollectionListByUniqueIdentifierList`, `SetItemCollection`, `SetItemCollectionActivityId`, `CreateItemCollectionVersion`, `GetItemCollectionVersion`, `GetItemCollectionVersionList`, `AddAccountItemCollectionFavorite`, `RemoveAccountItemCollectionFavorite`, `GetAccountItemCollectionFavoriteList`, `GetAccountItemCollectionList`

**Skins (11)**: `CreateSkin`, `GetSkin`, `GetSkinList`, `GetCreatorSkinList`, `GetAccountSkinList`, `GetAccountSkinListByAccountList`, `SetAccountSkin`, `UnsetAccountSkin`, `AddAccountSkinFavorite`, `GetAccountSkinFavoriteList`, `RemoveAccountSkinFavorite`

**Clubs (3)**: `GetClub`, `GetClubList`, `GetAccountClubTag`, `GetAccountClubTagList`, `SetAccountClubTag`

**Trophies (5)**: `GetTrophySettings`, `GetAccountTrophyGainHistory`, `GetAccountTrophyLastYearSummary`, `SetTrophyCompetitionMatchAchievementResult`, `SetTrophyLiveTimeAttackAchievementResult`

**Prestige (8)**: `GetAllPrestigeList`, `GetPrestigeList`, `GetPrestigeListFromModeYearType`, `GetPrestigeListFromYear`, `GetAccountPrestigeCurrent`, `GetCurrentAccountPrestige`, `GetAccountPrestigeList`, `GetCurrentAccountPrestigeList`, `SetAccountPrestigeCurrent`, `UnsetAccountPrestigeCurrent`

**Squads (9)**: `CreateSquad`, `GetSquad`, `GetAccountSquad`, `AddSquadInvitation`, `AcceptSquadInvitation`, `DeclineSquadInvitation`, `RemoveSquadInvitation`, `LeaveSquad`, `RemoveSquadMember`, `SetSquadLeader`

**Accounts & Identity (11)**: `GetAccountZone`, `GetAccountZoneList`, `SetAccountZone`, `GetZones`, `GetAccountXp`, `GetAccountDisplayNameList`, `GetWebServicesIdentityFromAccountId`, `GetAccountIdFromWebServicesIdentity`, `GetAccountGroupList`, `GetAccountLadderInfo`

**Subscriptions (3)**: `AddSubscription`, `AddSubscriptionFromPSN`, `GetAccountSubscriptionList`

**Encrypted Packages / DRM (6)**: `SetEncryptedPackage`, `GetEncryptedPackageList`, `CreateEncryptedPackageVersion`, `GetEncryptedPackageVersionList`, `GetEncryptedPackageVersionCryptKey`, `GetEncryptedPackageAccountKey`, `GetAccountEncryptedPackageList`

**Uploads (4)**: `CreateUpload`, `GetUpload`, `Upload`, `UploadPart`

**Servers (3)**: `GetServer`, `SetServer`, `DeleteServer`

**Activity / Match (3)**: `Activity_CreateMatch`, `Activity_UpdateMatch`, `Activity_ReportMatchResult`

**Client Config (6)**: `GetClientConfig`, `GetClientFileList`, `GetClientUpdaterFile`, `SetClientCaps`, `AddClientLog`, `AddClientDebugInfo`

**Telemetry (1)**: `AddTelemetryMapSession`

**Presence (2)**: `SetAccountPresence`, `DeleteAccountPresence`

**Profile Chunks (3)**: `GetProfileChunkList`, `SetProfileChunk`, `DeleteProfileChunk`

**Driver Bots (2)**: `GetDriverBotGroupList`, `AddDriverBotGroupList`, `AddDriverBotGroupList_GetLimit`

**Map Zen (2)**: `GetAccountMapZen`, `IncrAccountMapZen`

**Stations (3)**: `LoadStation`, `UnloadStation`, `GetAccountStationList`

**Titles (2)**: `GetAccountTitleList`, `SetTitle`

**Waiting Queue (1)**: `AddToWaitingQueue`

**Misc (5)**: `GetApiRequests`, `GetVisualNotificationUrlInfo`, `GetAccountPolicyRuleValueList`, `GetAccountClientSignature`, `GetAccountClientUrls`, `GetAccountClientPluginList`, `GetAccountAdditionalFileList`

**User Accounts (5)**: `CreateUserAccount`, `UpdateUserAccount`, `GetUserAccount`, `AddAccountPasswordReset`, `ResetAccountPassword`, `SetAccountPassword`

### CWebServices* Class Breakdown (297 classes)

#### Core Infrastructure (8)

| Class | Purpose |
|-------|---------|
| `CWebServices` | Main service facade |
| `CWebServicesTaskScheduler` | Task dispatch (dual-threaded) |
| `CWebServicesTask` | Base task class |
| `CWebServicesTaskResult` | Base result class |
| `CWebServicesTaskSequence` | Sequential task chain |
| `CWebServicesTaskVoid` | No-op task |
| `CWebServicesTaskWait` | Wait/delay task |
| `CWebServicesTaskWaitMultiple` | Wait for multiple tasks |

#### Service Managers (18)

| Manager | Service Domain |
|---------|----------------|
| `CWebServicesUserManager` | User identity and profile |
| `CWebServicesIdentityManager` | Cross-platform identity resolution |
| `CWebServicesIdentityTaskManager` | Identity task management |
| `CWebServicesNotificationManager` | Push notification handling |
| `CWebServicesAchievementService` | Achievement tracking |
| `CWebServicesActivityService` | Activity/match reporting |
| `CWebServicesClientService` | Client config and updates |
| `CWebServicesEventService` | Event tracking |
| `CWebServicesFriendService` | Friend list management |
| `CWebServicesMapService` | Map management |
| `CWebServicesMapRecordService` | Leaderboard management |
| `CWebServicesNewsService` | News/announcements |
| `CWebServicesPartyService` | Party/squad management |
| `CWebServicesPermissionService` | Permission checking |
| `CWebServicesPreferenceService` | User preferences |
| `CWebServicesPrestigeService` | Prestige/cosmetics |
| `CWebServicesStatService` | Statistics |
| `CWebServicesTagService` | Club tags |
| `CWebServicesZoneService` | Geographic zones |
| `CWebServicesUserInfo` | User info structure |

#### Task Classes (~90 unique tasks)

**Connection (7)**: `Connect`, `ConnectToNadeoServices`, `Disconnect`, `DisconnectFromNadeoServices`, `PostConnect`, `PostConnect_*` (6 sub-tasks)

**Network/Auth (4)**: `CheckNetworkAvailability`, `CheckLoginExists`, `CreateAccount`, `CheckSubscription`, `CheckWaitingQueue`

**Maps (5)**: `GetMapList`, `GetMapZen`, `IncrMapZen`, `StartMapRecordAttempt`, `StopMapRecordAttempt`, `GetMapRecordListByMapRecordContextAndUserList`

**Social (7)**: `GetFriendList`, `RetrieveFriendList`, `GetBlockList`, `GetDisplayNameFromWebServicesIdentity`, `GetDisplayNameFromWebServicesUserId`, `GetWebIdentityFromWebServicesUserId`, `GetWebServicesUserIdFromWebIdentity`

**Party (12)**: `Party_Create`, `Party_Leave`, `Party_CancelInvitation`, `Party_RenewPartyExpiration`, `Party_RequestAutoRemovePartyMemberOnDisconnect`, `Party_RetrievePartyCompleteInfo`, `Party_RetrievePartyInfo`, `Party_RetrievePartyInvitationList`, `Party_RetrievePartyJoinRequestList`, `Party_RetrievePartyMemberList`, `Party_SetLocked`, `Party_SetMaxMemberLimit`, `Party_Update`

**Permissions (11)**: All `Permission_Check*` variants including `CheckCrossPlay`, `CheckPlayMultiplayer*`, `CheckUseUserCreatedContent`, `CheckViewOnlinePresence`, `GetPlayerInteractionRestriction`, `GetPlayerInteractionStatusList`, `CheckTargetedUseUserCreatedContent*`, `CheckTargetedViewUserGameHistory`, `CheckPrivilegeForAllUsers`

**Prestige (7)**: `GetPrestige`, `GetPrestigeList`, `GetPrestigeListByYear`, `GetUserPrestigeList`, `GetUserPrestigeSelected*`, `SetUserPrestigeSelected`, `RetrievePrestigeInfoList`, `RetrieveUserPrestigeLevelList`

**Profile (6)**: `SynchronizeProfileChunks`, `UploadProfileChunks`, `UserProfile_GetAvatarUrl`, `UserProfile_ShowUbisoftConnectProfile`, `UbisoftConnect_Show`

**Zone/Tag (6)**: `GetUserZone`, `GetUserZoneList`, `GetZoneList`, `SetUserZone`, `GetUserClubTag`, `GetUserClubTagList`, `SetUserClubTag`

**Season (2)**: `GetSeasonPlayableList`

**Title (5)**: `GetTitlePackagesInfos`, `Title_GetConfig`, `Title_GetLadderInfo`, `Title_GetPlayerInfos`, `Title_GetPolicyRuleValues`

**Ghost/Replay (1)**: `UploadSessionReplay`

**Misc (8)**: `GetStatList`, `GetServerInfo`, `SetServerInfo`, `GetUserNewsList`, `OpenNewsLink`, `GetAccountXp`, `GetPackageUpdateUrl`, `GetPlayerCreditedPackagesGroups`, `GetFirstPartyAchievementList`, `UpdateFirstPartyAchievementCompletion`, `LoadStation`, `UnloadStation`, `UpdateClientConfig`, `UpdateUserConfig`, `Preference_RetrieveUserPreference`, `Event_AddMapSession`, `SendResetPasswordRequest`, `ResetPassword`, `Empty`

#### Result Types (~165 classes)

Result types follow the pattern `CWebServicesTaskResult_<DataType>`. Key categories:

**NS (NadeoServices) Result Types (60+)**:
- `CWebServicesTaskResult_NSMap`, `_NSMapList`, `_NSMapRecordList`, `_NSMapRecordAttempt`, `_NSMapRecordSecureAttempt`
- `CWebServicesTaskResult_NSSeason`, `_NSSeasonList`, `_NSCampaignList`
- `CWebServicesTaskResult_NSSkin`, `_NSSkinList`, `_NSAccountSkin*`
- `CWebServicesTaskResult_NSItemCollection*`, `_NSItemCollectionVersion*`
- `CWebServicesTaskResult_NSSquad`, `_NSStation`, `_NSTitle*`
- `CWebServicesTaskResult_NSPrestigeList`, `_NSAccountPrestige*`
- `CWebServicesTaskResult_NSTrophySettings`, `_NSAccountTrophyGain*`
- `CWebServicesTaskResult_NSEncryptedPackage*`
- `CWebServicesTaskResult_NSProfileChunk*`
- `CWebServicesTaskResult_NSLadderAccountInfo`
- `CWebServicesTaskResult_NSServer`, `_NSUpload`, `_NSUserAccount`
- `CWebServicesTaskResult_NSWaitingInfo`, `_NSWebServicesIdentityList`, `_NSZoneList`
- `CWebServicesTaskResult_NSDriverBotGroup*`, `_NSPolicyRuleValueList`
- `CWebServicesTaskResult_NSClientFileList`, `_NSClubList`

**WS (WebServices) Result Types (15+)**:
- `CWebServicesTaskResult_WSBlockedUserList`, `_WSFriendInfoList`, `_WSFriendList`
- `CWebServicesTaskResult_WSMapPtrList`, `_WSMapRecordList`, `_WSNewsList`
- `CWebServicesTaskResult_WSNotification*`, `_WSParty*`, `_WSPrestige*`, `_WSZone*`

**UbiServices Result Types (10+)**:
- `CWebServicesTaskResult_UbiServicesBlockList`, `_UbiServicesNewsList`
- `CWebServicesTaskResult_UbiServicesParty*`, `_UbiServicesPlayerPreferencesStandard`
- `CWebServicesTaskResult_UbiServicesProfileAcceptanceList`, `_UbiServicesProfileConsent`
- `CWebServicesTaskResult_UbiServicesStatList`, `_UbiServicesVisualNotificationUrlInfo`

**UPC Result Types (3)**:
- `CWebServicesTaskResult_UPCAchievementCompletionList`
- `CWebServicesTaskResult_UPCConsumableItemList`
- `CWebServicesTaskResult_UPCFriendList`

**Script-Facing Result Types (20+)**: `*Script` variants that expose data to ManiaScript.

**Generic Result Types (6)**: `Bool`, `Integer`, `Natural`, `String`, `StringInt`, `StringIntList`, `StringList`

---

## 7. Game Protocol (TCP+UDP)

### Dual-Stack Architecture

The game uses **both TCP and UDP simultaneously** per connection:

```
+------------------------------------------------------------------+
|                    CNetConnection                                 |
|                                                                   |
|  +---------------------------+  +-----------------------------+   |
|  |    TCP Channel            |  |    UDP Channel              |   |
|  |                           |  |                             |   |
|  |  ConnectionTCP object     |  |  TestingUDP flag            |   |
|  |  TCPPort / LocalTCPPort   |  |  UDPPort / LocalUDPPort     |   |
|  |  RemoteTCPPort            |  |  RemoteUDPPort              |   |
|  |  CanSendTCP               |  |  CanSendUDP                 |   |
|  |  CanReceiveTCP            |  |  CanReceiveUDP              |   |
|  |  TCPEmissionQueue         |  |  WasUDPPacketDropped        |   |
|  |  IsTCPSaturated           |  |  LatestUDPActivity          |   |
|  |                           |  |                             |   |
|  |  Used for:                |  |  Used for:                  |   |
|  |  - Reliable state         |  |  - Player positions         |   |
|  |  - Chat messages          |  |  - Input data               |   |
|  |  - Admin commands          |  |  - Time-critical sync       |   |
|  |  - File transfers          |  |  - Ping measurements        |   |
|  |  - Nod serialization       |  |  - Voice chat frames        |   |
|  +---------------------------+  +-----------------------------+   |
+------------------------------------------------------------------+
```

### Evidence for Dual-Stack

| String | Address | Channel |
|--------|---------|---------|
| `"TCP initialization failed."` | `0x141b7bbe8` | TCP |
| `"UDP initialization failed."` | `0x141b7bbc8` | UDP |
| `"Could not establish UDP connection."` | `0x141b7be68` | UDP |
| `"UDP connection lost."` | `0x141b7bed0` | UDP |
| `"TotalTcpUdpReceivingSize"` | `0x141c37d78` | Both |

### Per-Channel Metrics

| Metric | TCP Address | UDP Address |
|--------|------------|-------------|
| Sending data rate | `0x141b7bb68` | `0x141b7bb50` |
| Receiving data rate | `0x141b7bb80` | `0x141b7bbb0` |
| Sending packet total | `0x141b7b088` | `0x141b7b040` |
| Reception packet total | `0x141b7b010` | `0x141b7b028` |
| Sending nod total | `0x141b7b110` | `0x141b7b0d0` |
| Reception nod total | `0x141b7b0a0` | `0x141b7b0b8` |

"Nod" totals refer to serialized game objects (ManiaPlanet's base object class is `CMwNod`).

### Connection Lifecycle

```
1. TCP Handshake
   CNetServer/CNetClient::InitNetwork
   "NetEngine(server): successfully connected from '%s' (IP = %s)"  (0x141b7bfc0)
   "NetEngine (client): successfully connected to '%s' (IP = %s)"   (0x141d15648)

2. UDP Probing
   CNetConnection.TestingUDP = true
   Attempts UDP hole-punching
   Falls back to TCP-only if UDP fails

3. Session Establishment
   CNetFormConnectionAdmin messages exchanged
   CNetFormEnumSessions / CNetFormQuerrySessions for session negotiation

4. Active Connection
   CNetServer::TickReception  (per-tick receive)
   CNetServer::DoReception    (full receive loop)
   CNetServer::DoSending      (full send loop)
   CNetServer::CheckDisconnections (disconnect detection)

   CNetClient::TickReception
   CNetClient::DoReception
   CNetClient::DoSending

5. Keepalive
   CNetFormPing / CNetFormNewPing
   LatestUDPActivity timestamp monitoring

6. Disconnection
   CNetServer::CheckDisconnections detects lost connections
   IsTCPSaturated flag indicates TCP backpressure
   WasUDPPacketDropped flag indicates UDP packet loss
```

### Network Forms (Typed Messages)

The engine uses a "form" system for typed network messages, inherited from ManiaPlanet:

#### Engine-Level Forms

| Form Class | Purpose | Wire Format |
|-----------|---------|-------------|
| `CNetFormConnectionAdmin` | Connection management (connect, disconnect, auth) | [UNKNOWN] |
| `CNetFormEnumSessions` | Session enumeration | [UNKNOWN] |
| `CNetFormQuerrySessions` | Session queries | [UNKNOWN] |
| `CNetFormTimed` | Timestamped messages (base for game forms) | [UNKNOWN] |
| `CNetFormPing` | Ping/latency measurement | [UNKNOWN] |
| `CNetFormNewPing` | Updated ping protocol | [UNKNOWN] |
| `CNetFormRpcCall` | XML-RPC method invocation | [UNKNOWN] |
| `CNetFileTransferForm` | File transfer protocol | [UNKNOWN] |

#### Game-Level Forms

| Form Class | Purpose | Channel |
|-----------|---------|---------|
| `CGameNetForm` | Base game form | TCP/UDP |
| `CGameNetFormPlayground` | Gameplay event synchronization | UDP |
| `CGameNetFormPlaygroundSync` | Playground state sync | UDP |
| `CGameNetFormTimeSync` | Game timer synchronization | UDP |
| `CGameNetFormCallVote` | Vote system | TCP |
| `CGameNetFormAdmin` | Server admin commands | TCP |
| `CGameNetFormTunnel` | Tunneled data (arbitrary payload) | TCP |
| `CGameNetFormBuddy` | Friend/buddy system | TCP |
| `CGameNetFormVoiceChat` | Voice chat audio frames | UDP |

### NAT Traversal

| Class | Purpose |
|-------|---------|
| `CNetUPnP` | UPnP port forwarding |
| `CNetIPSource` | IP source management |

The game supports UPnP for automatic port forwarding. [UNKNOWN] whether STUN/TURN is also used.

---

## 8. Real-time Multiplayer Protocol

### Deterministic Simulation Model

The networking follows a **deterministic lockstep** model (evidenced by the BeforePhy/AfterPhy naming):

```
Frame N:
  +-- NetUpdate_BeforePhy (receive)
  |     Read remote player inputs from network
  |     Buffer inputs for deterministic application
  |
  +-- Physics Step (deterministic)
  |     All clients simulate with identical inputs
  |     NSceneVehiclePhy::ComputeForces
  |     NSceneDyna::PhysicsStep
  |     NSceneVehiclePhy::PhysicsStep_BeforeMgrDynaUpdate
  |
  +-- NetUpdate_AfterPhy (send)
  |     Send local player input + state
  |     PlaygroundSync_UpdateInfos
  |
  +-- NetLoop_Synchronize
        SynchronizeGameTimer
        Ensure all clients share game time
```

### Synchronization Components

| Method | Address | Purpose |
|--------|---------|---------|
| `NetUpdate_BeforePhy` | `0x141c2b348` | Receive remote inputs before physics |
| `NetUpdate_AfterPhy` | `0x141c2b388` | Send local results after physics |
| `NetLoop_Synchronize` | `0x141c49c28` | Master synchronization loop |
| `SynchronizeGameTimer` | `0x141c49bb0` | Game timer sync |
| `PlaygroundSync_UpdateInfos` | `0x141cf75d8` | Gameplay info sync |

### Player State Classes

| Class | Purpose |
|-------|---------|
| `CGameNetPlayerInfo` | Per-player network state |
| `CGameNetServerInfo` | Server-side game state |
| `CGameNetOnlineMessage` | Online message exchange |
| `CGameGhost` | Ghost replay data (recorded inputs) |
| `CGameGhostTMData` | Trackmania-specific ghost data |
| `CGameCtnGhost` | Ghost with car type info |
| `CInputReplay` | Recorded input sequence |
| `CGhostManager` | Ghost management |
| `CGameGhostMgrScript` | Script-facing ghost manager |

### Ghost System (Input Recording)

Ghosts are the core mechanism for both replay and multiplayer validation:

```
Local Play:
  CInputReplay captures every input frame
  CGameGhostTMData stores TM-specific metadata
  CGameCtnGhost wraps with car/map context

Online Validation:
  Ghost data uploaded via CWebServicesTask_UploadSessionReplay
  or via CGameDataFileTask_GhostDriver_Upload
  Server validates input sequence produces claimed time

Ghost Download:
  CGameDataFileTask_GhostDriver_Download
  CGameScoreTask_GetPlayerMapRecordGhost
  Ghosts replayed locally for leaderboard display
```

### Data Synchronization [UNKNOWN Details]

The exact wire format for the following is [UNKNOWN]:

1. **Player position sync**: Likely sent via `CGameNetFormPlayground` over UDP
2. **Input sync**: Likely encoded in `CGameNetFormPlaygroundSync`
3. **Server authority**: Evidence of server-authoritative model from `CGameNetServerInfo` and anti-cheat upload system
4. **Client prediction**: [UNKNOWN] whether clients predict ahead or wait for server confirmation
5. **Lag compensation**: [UNKNOWN] specific mechanisms, though `CGameNetFormTimeSync` handles timer alignment

### Tunnel System

| Method | Address |
|--------|---------|
| `CGameNetwork::Tunnel_Update` | [methods] |
| `CGameNetFormTunnel` | `0x141c616f0` |
| `ManiaPlanet.TunnelDataReceived` | `0x141d04938` |

The tunnel system allows arbitrary data to be sent through the game connection, used by server controllers and plugins.

---

## 9. XML-RPC Dedicated Server Protocol

### Architecture

The game includes a full XML-RPC implementation inherited from ManiaPlanet for dedicated server scripting and remote control. This is the primary interface for server controllers (e.g., PyPlanet, EvoSC, ManiaControl).

```
External Controller              Game Server
  (OpenPlanet, etc.)              (Dedicated)
        |                              |
        |  XML-RPC over TCP            |
        |----------------------------->|
        |     Method Call              |
        |                              |
        |     CXmlRpc processes        |
        |     CXmlRpcEvent generated   |
        |     CGameServerScriptXmlRpc  |
        |       dispatches to script   |
        |                              |
        |<-----------------------------|
        |     Callback notification    |
        |     (e.g., PlayerConnect)    |
```

### xmlrpc-c Library (Static)

| String | Address |
|--------|---------|
| `"New XmlRpc request : \n"` | `0x141b6ff10` |
| `"XmlRpc request failed : \n"` | `0x141b6ff28` |
| `"XmlRpc request succeeded : \n"` | `0x141b6ff68` |
| `"Xmlrpc-c global client instance has already been created..."` | `0x141b70f50` |
| `"Xmlrpc-c global client instance has not been created..."` | `0x141b70fd0` |

### XML-RPC Classes

| Class | Purpose |
|-------|---------|
| `CXmlRpc` | Core XML-RPC handler |
| `CXmlRpcEvent` | RPC event object |
| `CGameServerScriptXmlRpc` | Server-side script RPC interface |
| `CGameServerScriptXmlRpcEvent` | Server RPC event |
| `CNetFormRpcCall` | RPC wire protocol form |
| `CGameServerPlugin` | Server plugin interface |
| `CGameServerPluginEvent` | Server plugin event |
| `CServerAdmin` | Server administration |
| `CServerInfo` | Server info (script-facing) |
| `CServerPlugin` | Plugin interface |
| `CServerPluginEvent` | Plugin event |

### ManiaPlanet XML-RPC Callbacks (25 callbacks)

These are the standard ManiaPlanet server XML-RPC callbacks present in the binary:

| Callback | Address | Trigger |
|----------|---------|---------|
| `ManiaPlanet.ServerStart` | `0x141d045f8` | Server started |
| `ManiaPlanet.ServerStop` | `0x141d04568` | Server stopped |
| `ManiaPlanet.PlayerConnect` | `0x141d044a8` | Player connected |
| `ManiaPlanet.PlayerDisconnect` | `0x141d044e8` | Player disconnected |
| `ManiaPlanet.PlayerChat` | `0x141d04690` | Chat message |
| `ManiaPlanet.PlayerInfoChanged` | `0x141d04808` | Player info updated |
| `ManiaPlanet.BeginMap` | `0x141d04778` | Map started |
| `ManiaPlanet.EndMap` | `0x141d04730` | Map ended |
| `ManiaPlanet.BeginMatch` | `0x141d04588` | Match started |
| `ManiaPlanet.EndMatch` | `0x141d04790` | Match ended |
| `ManiaPlanet.BeginRound` | `0x141d04760` | Round started |
| `ManiaPlanet.EndRound` | `0x141d046c8` | Round ended |
| `ManiaPlanet.StatusChanged` | `0x141d046f8` | Server status changed |
| `ManiaPlanet.Echo` | `0x141d04610` | Echo test |
| `ManiaPlanet.BillUpdated` | `0x141d047f0` | Planets transaction updated |
| `ManiaPlanet.VoteUpdated` | `0x141d048b0` | Vote state changed |
| `ManiaPlanet.PlayerAlliesChanged` | `0x141d048d0` | Player allies changed |
| `ManiaPlanet.MapListModified` | `0x141d048f0` | Map list changed |
| `ManiaPlanet.TunnelDataReceived` | `0x141d04938` | Tunnel data received |
| `ManiaPlanet.ModeScriptCallback` | `0x141d049a0` | Script callback (single value) |
| `ManiaPlanet.ModeScriptCallbackArray` | `0x141d04978` | Script callback (array) |
| `ManiaPlanet.PlayerManialinkPageAnswer` | `0x141d045b8` | ManiaLink page interaction |
| `Anticheat.EndOfScript` | `0x141d046e0` | Anti-cheat script ended |
| `Anticheat.SendResult` | `0x141d04860` | Anti-cheat result |

### ManiaLink Integration

The `ManiaPlanet.PlayerManialinkPageAnswer` callback connects XML-RPC to the ManiaLink UI system, allowing server controllers to:
1. Send ManiaLink pages to players (XML-based UI)
2. Receive button clicks and form submissions via XML-RPC callbacks
3. Update UI dynamically based on game state

### Server Controller Architecture [COMMUNITY]

The XML-RPC protocol is well-documented by the community. A server controller connects to a dedicated server's XML-RPC port (default: 5000) and can:

```
Server Controller              Dedicated Server (XML-RPC port 5000)
      |                              |
      | system.listMethods()         |
      |----------------------------->|  Returns: list of all available methods
      |<-----------------------------|
      |                              |
      | Authenticate(user, pw)       |
      |----------------------------->|  SuperAdmin/Admin/User levels
      |<-----------------------------|
      |                              |
      | EnableCallbacks(true)        |
      |----------------------------->|  Start receiving callbacks
      |                              |
      |     ManiaPlanet.PlayerConnect|
      |<-----------------------------|  (async callback)
      |                              |
      | SendDisplayManialinkPageTo   |
      | LoginList(xml, login, ...)   |
      |----------------------------->|  Send UI to specific players
      |                              |
      | TriggerModeScriptEventArray  |
      | ("method", ["param1"])       |
      |----------------------------->|  Trigger ManiaScript events
      |                              |
```

### Key XML-RPC Method Categories [COMMUNITY]

| Category | Example Methods | Purpose |
|----------|----------------|---------|
| System | `system.listMethods`, `Authenticate` | Connection setup |
| Server | `GetServerName`, `SetServerName`, `GetStatus` | Server management |
| Map | `GetMapList`, `AddMap`, `RemoveMap`, `NextMap` | Map rotation |
| Player | `GetPlayerList`, `ForceSpectator`, `Kick`, `Ban` | Player management |
| Chat | `ChatSendServerMessage`, `ChatSendToLogin` | Server chat |
| ManiaLink | `SendDisplayManialinkPage*`, `SendHideManialinkPage` | UI overlay |
| Mode Script | `TriggerModeScriptEvent*`, `GetModeScriptInfo` | Game mode scripting |
| Callbacks | `EnableCallbacks`, `SetApiVersion` | Event subscription |

### Callback Mechanism

Callbacks are asynchronous notifications from the server to connected controllers. They are sent as XML-RPC method calls FROM the server TO the controller:

1. Controller calls `EnableCallbacks(true)` to opt in
2. Controller calls `SetApiVersion("2023-04-01")` to select callback format version
3. Server sends callbacks as they occur (player events, round events, etc.)
4. The `ManiaPlanet.ModeScriptCallbackArray` callback is the primary mechanism for custom game mode events -- it carries a method name and array of string parameters

---

## 10. Voice and Text Chat

### Vivox Voice Chat

**DLL**: `VoiceChat.dll` (loaded at `0x141d0d748`)
**Authentication**: Token-based

| String | Address | Purpose |
|--------|---------|---------|
| `voicechatTokenVivox` | `0x141a0dd98` | Config key for Vivox token |
| `voicechatConfigVivox` | `0x141a0ddb0` | Config key for Vivox config |
| `VoicechatClient::createVivoxVoicechatToken` | `0x141a22860` | Token creation |
| `VoicechatClient::getVivoxVoicechatConfig` | `0x141a22890` | Config retrieval |

#### Vivox Architecture

```
Game Client                 Vivox Servers
    |                           |
    | Token request             |
    | (via Nadeo Services)      |
    |-------------------------->|
    |                           |
    | VoiceChat.dll loads       |
    | Connects to Vivox         |
    |<=========================>|
    | Audio stream (RTP/SRTP)   |
    |                           |
```

#### Voice Chat Script API

| Class | Purpose |
|-------|---------|
| `CGameUserVoiceChat` | User voice chat state |
| `CGameVoiceChatConfigScript` | Script-facing voice config |
| `CGameUserManagerScript_VoiceChatEvent` | Base voice event |
| `CGameUserManagerScript_VoiceChatEvent_DisplayUI` | UI display event |
| `CGameUserManagerScript_VoiceChatEvent_Message` | Voice message event |
| `CGameUserManagerScript_VoiceChatEvent_SpeakingHasChanged` | Speaking state change |
| `CGameUserManagerScript_VoiceChatEvent_UserChange_IsConnected` | Connection change |
| `CGameUserManagerScript_VoiceChatEvent_UserChange_IsMuted` | Mute change |
| `CGameUserManagerScript_VoiceChatEvent_UserChange_IsSpeaking` | Speaking change |
| `CGameNetFormVoiceChat` | Voice frames over game connection |

### XMPP Text Chat

The game uses XMPP/Jabber for persistent text chat.

```
Game Client                XMPP Servers
    |                      (*.chat.maniaplanet.com)
    |                           |
    | TLS connection            |
    |<=========================>|
    |                           |
    | Squad chat:               |
    | squad.chat.maniaplanet.com|
    |                           |
    | Channel chat:             |
    | channel.chat.maniaplanet.com
    |                           |
```

#### XMPP Protocol Features

| Protocol | Address | Purpose |
|----------|---------|---------|
| `http://jabber.org/protocol/muc#user` | `0x141d10f00` | Multi-user chat rooms |
| `jabber:x:conference` | `0x141d10f40` | Conference invitations |
| `jabber:iq:roster` | `0x141d11110` | Contact list management |
| `http://jabber.org/protocol/disco#info` | `0x141d11300` | Service discovery |
| `urn:xmpp:bob` | `0x141d110e8` | Binary data over XMPP |
| `urn:xmpp:ping` | `0x141d11218` | Keepalive ping |

#### XMPP Classes

| Class | Purpose |
|-------|---------|
| `CNetXmpp` | XMPP client (HighFreqPoll method) |
| `CNetXmpp_Timer` | Timer-based XMPP updates |
| `CGameScriptChatManager` | Script-facing chat manager |
| `CGameScriptChatRoom` | Chat room |
| `CGameScriptChatContact` | Chat contact |
| `CGameScriptChatEvent` | Chat event |
| `CGameScriptChatHistory` | Chat history |
| `CGameScriptChatHistoryEntry` | History entry |
| `CGameScriptChatHistoryEntryMessage` | Message in history |
| `CGameScriptChatSquadInvitation` | Squad invite via chat |

#### XMPP Servers

| Server | Address | Purpose |
|--------|---------|---------|
| `squad.chat.maniaplanet.com` | `0x141c444d0` | Squad/party private chat |
| `channel.chat.maniaplanet.com` | `0x141c444f0` | Public channel chat (server-wide) |

### Inter-Process Communication

| String | Address | Purpose |
|--------|---------|---------|
| `CNetIPC` | `0x141d10d38` | IPC class |
| `CNetIPC::Tick` | `0x141d10d78` | Per-tick update |
| `CNetIPC::HighFreqPoll` | `0x141d10d88` | High-frequency polling |

[UNKNOWN] The IPC target. May be used for Ubisoft Connect overlay, Vivox voice process, or anti-cheat monitor.

---

## 11. Anti-Cheat System

### Architecture

```
Game Client                     Anti-Cheat Server
    |                               |
    | OpenAntiCheatSession          |
    |------------------------------>|
    |                               |
    | During gameplay:              |
    |   Record inputs (ghost)       |
    |   Record state snapshots      |
    |                               |
    | UpdateAntiCheat (per-frame)   |
    |                               |
    | On PB / suspicious activity:  |
    | UpdateAntiCheatReplayUpload   |
    |------------------------------>|
    | (chunked upload)              |
    |                               |
    | Server validates:             |
    |   - Input sequence            |
    |   - Resulting physics state   |
    |   - Final time                |
    |   - Client checksums          |
    |                               |
    | Anticheat.SendResult          |
    |<------------------------------|
    | (via XML-RPC callback)        |
```

### Anti-Cheat Methods

| Method | Address | Purpose |
|--------|---------|---------|
| `CGameCtnNetwork::UpdateAntiCheat` | `0x141c2df10` | Per-frame anti-cheat update |
| `CGameCtnNetwork::OpenAntiCheatSession` | `0x141c2df70` | Create anti-cheat session |
| `CGameCtnNetwork::UpdateAntiCheatReplayUpload` | `0x141c2e050` | Upload replay for verification |
| `CGameCtnNetwork::UpdateAntiCheatReplayUpload_InternalFiberCallback` | [methods] | Fiber-based upload |
| `CGameCtnNetwork::UpdateAntiCheat_InternalFiberCallback` | [methods] | Fiber-based check |
| `CGameCtnNetwork::CheckCryptedChecksumsForInternet` | `0x141c2b860` | Internet integrity check |
| `CGameCtnNetwork::CheckCryptedChecksumsForLan` | `0x141c2ba48` | LAN integrity check |
| `CWebServicesTask_PostConnect_BannedCryptedChecksumsList` | `0x141cd9300` | Download banned checksums |

### Anti-Cheat Configuration

| Config Key | Address | Purpose |
|-----------|---------|---------|
| `AntiCheatServerUrl` | `0x141c04d68` | Anti-cheat server endpoint URL |
| `AntiCheatReplayChunkSize` | `0x141c2af98` | Upload chunk size |
| `AntiCheatReplayMaxSize` | `0x141c2afe0` | Maximum replay size for upload |
| `AntiCheatReplayMaxSizeOnCheatReport` | `0x141c2afb8` | Enhanced size for cheat reports |
| `UploadAntiCheatReplayOnlyWhenUnblocked` | `0x141c2af78` | Upload gating |
| `UploadAntiCheatReplayForcedOnCheatReport` | `0x141c2b118` | Force upload when cheat detected |

### Validation Flow

1. **Client-side recording**: During gameplay, the client records a complete input sequence as a ghost (`CInputReplay` / `CGameGhostTMData`)
2. **Checksum computation**: Client computes crypted checksums of game files
3. **Replay upload**: On PB (personal best) or suspicious activity, replay data is uploaded in chunks
4. **Server-side validation**: Server replays the input sequence through a deterministic physics simulation and verifies:
   - The final time matches what the client reported
   - Physics state is consistent throughout
   - No impossible states (e.g., clipping through walls)
   - Client file checksums are not in the banned list
5. **Result reporting**: Server reports result via `Anticheat.SendResult` XML-RPC callback

### Secure Record Attempt Flow

For leaderboard submissions:

```
1. CNetNadeoServicesTask_CreateMapRecordSecureAttempt
   POST to create a secure attempt token

2. Player completes the map

3. CNetNadeoServicesTask_PatchMapRecordSecureAttempt
   PATCH with ghost data + result

4. CWebServicesTask_UploadSessionReplay
   Upload full replay for server validation

5. Server verifies and posts to leaderboard
```

### Demo Token System

A separate access-control system with periodic server verification:

| Config Key | Address | Purpose |
|-----------|---------|---------|
| `DemoTokenKickingTimeOut` | `0x141c2b068` | Time before kick for invalid token |
| `DemoTokenCheckingTimeOut` | `0x141c2b080` | Token check timeout |
| `DemoTokenAskingTimeOut` | `0x141c2b0a0` | Token request timeout |
| `DemoTokenTimeBetweenCheck` | `0x141c2b0b8` | Periodic check interval |
| `DemoTokenWaitingTimeAfterFirstAnswer` | `0x141c2b0d8` | Wait after first validation |
| `DemoTokenRetryMax` | `0x141c2b100` | Maximum retries |
| `DemoTokenCost` | `0x141c2c178` | Token cost (Planets currency?) |
| `Invalid demo token` | `0x141c2e2a0` | Error message |

---

## 12. Matchmaking

### Architecture

The matchmaking system integrates with Ubisoft's "Harbour" social platform:

```
Game Client                 Harbour/Matchmaking Server
    |                              |
    | Join matchmaking queue       |
    |----------------------------->|
    |                              |
    | Wait for match               |
    |<..........................-->|  (polling)
    |                              |
    | Match found                  |
    |<-----------------------------|
    |   Server IP + port           |
    |   Match parameters           |
    |                              |
    | Connect to game server       |
    |----------------------------->| (Game Server)
    |                              |
```

### Matchmaking Configuration

| Config Key | Address | Purpose |
|-----------|---------|---------|
| `Matchmaking` | `0x141a115f0` | Feature name |
| `profilesPreciseMatchmakingClient` | `0x141a0d168` | Client-side matchmaking profile |
| `profilesPreciseMatchmakingMatch` | `0x141a0d190` | Match-side matchmaking profile |
| `matchmakingGroupsMatchesPrecise` | `0x141a0d1b0` | Group match precision settings |
| `matchmakingSpaceGlobalHarboursocial` | `0x141a0d1d0` | Social matchmaking space |
| `matchmakingProfilesGlobalHarboursocial` | `0x141a0d218` | Social matchmaking profiles |
| `profilesMatchmakingOnlineAccess` | `0x141a0d1f8` | Online access gating |

### Matchmaking UI Strings

| String | Address |
|--------|---------|
| `"Join matchmaking"` | `0x141c059a8` |
| `"Join the matchmaking queue to find a match."` | `0x141c059c0` |
| `"Play and compete with your friends on a 2v2 matchmaking game."` | `0x141c05a80` |

### Matchmaking Integration Points

| Integration | Evidence |
|------------|----------|
| Ladder | `Ladder_SetMatchMakingMatchId` at `0x141c5cf38` |
| Activity | `CNetNadeoServicesTask_Activity_CreateMatch` |
| Match result | `CNetNadeoServicesTask_Activity_ReportMatchResult` |

### Matchmaking Classes

| Class | Purpose |
|-------|---------|
| `CGameLadderRanking` | Base ladder ranking |
| `CGameLadderRankingPlayer` | Player ladder data |
| `CGameLadderRankingSkill` | Skill-based rating |
| `CGameLadderRankingLeague` | League ranking |
| `CGameLadderRankingCtnChallengeAchievement` | Challenge-based ranking |
| `CWebServicesTaskResult_NSLadderAccountInfo` | Ladder API result |
| `CWebServicesTask_Title_GetLadderInfo` | Get ladder config |
| `CNetNadeoServicesTask_GetAccountLadderInfo` | Get player ladder info |

### Matchmaking Modes

The "Precise" variants in config keys suggest multiple precision levels for matching:
- **Standard matchmaking**: Broader skill range, faster queue times
- **Precise matchmaking**: Narrower skill range, longer queue times

Confirmed mode: **2v2 matchmaking** (from UI string "Play and compete with your friends on a 2v2 matchmaking game.")

[UNKNOWN] The exact matchmaking algorithm, ELO/Glicko parameters, queue timeout thresholds, and whether there are additional modes beyond 2v2.

### Related Network Methods

| Method | Class | Purpose |
|--------|-------|---------|
| `CheckMasterServerWaitingQueue` | `CGameNetwork` | Check queue status |
| `CheckNadeoServicesWaitingQueue` | `CGameNetwork` | Check Nadeo queue |
| `ShowNadeoServicesWaitingQueue` | `CGameNetwork` | Display queue UI |
| `WaitInMasterServerQueue` | `CGameNetwork` | Wait in queue |
| `FindServers` | `CGameNetwork` | Server browser |

---

## 13. File Transfer and Ghost Upload System

### Architecture

```
Sender                          Receiver
  |                                |
  | CNetFileTransferUpload         |
  |------------------------------->|  CNetFileTransferDownload
  |  CNetFileTransferForm          |
  |  (TCP channel, chunked)        |
  |                                |
  | For Nod objects:               |
  | CNetFileTransferNod            |
  |  Serializes CMwNod             |
  |  Binary game object format     |
  |                                |
```

### File Transfer Classes

| Class | Address | Purpose |
|-------|---------|---------|
| `CNetFileTransfer` | `0x141d13a68` | Base file transfer |
| `CNetFileTransferDownload` | `0x141d14ec8` | Download handler |
| `CNetFileTransferUpload` | `0x141d1a228` | Upload handler |
| `CNetFileTransferNod` | `0x141d1a680` | Serialized game object transfer |
| `CNetFileTransferForm` | `0x141b7d868` | Wire protocol |
| `CGameNetFileTransfer` | [class hierarchy] | Game-level file transfer |
| `CGameNetDataDownload` | [class hierarchy] | Game data download |

### Transfer Types

1. **Map files (.Map.Gbx)**: Transferred when joining a server with a map the client doesn't have
2. **Skin files**: Player customization data
3. **Replay files**: Ghost data for validation
4. **Plugin files**: Server plugins
5. **Nod objects**: Serialized game objects (arbitrary CMwNod subclass instances)

### Transfer Metrics

| Metric | Address |
|--------|---------|
| `CNetFileTransfer::UpdateTransfertSizeCmd` | `0x141d14ad0` |

File transfers use the TCP channel exclusively for reliability.

### HTTP-Based Downloads

In addition to the game protocol file transfer, the game downloads content via HTTP:

| Method | Address | Purpose |
|--------|---------|---------|
| `CGameCtnNetwork::DownloadFile` | `0x141c2c940` | Generic HTTP download |
| `CGameCtnNetwork::DownloadFileInfoFromHttpHeader` | `0x141c2c960` | HTTP header parsing |
| `CGameCtnNetwork::DownloadOrUpdateFile` | `0x141c2cab8` | Download with version check |
| `CGameCtnNetwork::DownloadOrUpdatePlugFilePack` | `0x141c2ca60` | Plugin pack |
| `CGameCtnNetwork::DownloadOrUpdateTitlePackages` | `0x141c2d220` | Title packages |
| `CGameCtnNetwork::UploadTitlePackage` | `0x141c2d3d0` | Title package upload |
| `CGameCtnNetwork::GetPackCloudUrl` | `0x141c2cab8` | Cloud URL resolution |
| `CGameCtnNetwork::DownloadManiaNetResource` | `0x141c2d928` | ManiaNet resource |
| `CGameCtnNetwork::GetManiaNetResource` | `0x141c2d598` | ManiaNet getter |
| `CGameCtnNetwork::CheckManiaNetResourceIsUpToDate` | `0x141c2d750` | Version check |

### Ghost Upload/Download

| Class | Purpose |
|-------|---------|
| `CGameDataFileTask_GhostDriver` | Base ghost driver task |
| `CGameDataFileTask_GhostDriver_Download` | Download ghost from server |
| `CGameDataFileTask_GhostDriver_Upload` | Upload ghost to server |
| `CGameDataFileTask_GhostDriver_UploadLimits` | Upload rate limits |
| `CGameDataFileTask_GhostLoadMedal` | Load medal ghost |
| `CGameDataFileTask_GhostLoadUserRecord_Maniaplanet` | Load user record ghost |
| `CGameDataFileTask_GhostStoreUserRecord_Maniaplanet` | Store user record ghost |
| `CGameScoreTask_GetPlayerMapRecordGhost` | Get ghost for leaderboard position |

### Ghost/Replay Upload System (Detailed)

The ghost upload system is central to how records get validated and posted to leaderboards. The flow involves multiple API calls and data formats.

#### Ghost Data Format for Transmission [PARTIAL]

Ghosts are stored in GBX format (`.Ghost.Gbx`). Key classes:
- `CGameGhost` -- Base ghost object containing recorded input data
- `CGameGhostTMData` -- Trackmania-specific metadata (car type, map UID, validation checkpoints)
- `CGameCtnGhost` -- Full ghost with embedded replay data
- `CInputReplay` -- Raw input recording (steer, gas, brake per tick at 100Hz)

The ghost contains:
1. **Header**: Map UID, player account ID, car type, race time
2. **Input sequence**: Every input frame at the physics tick rate (100Hz based on `SmMaxPlayerResimStepPerFrame=100`)
3. **Checkpoint times**: Intermediate checkpoint timestamps for validation
4. **Validation data**: Cryptographic validation allowing server-side replay

#### Leaderboard Submission Flow

```
Client                              Nadeo Core API
  |                                      |
  | 1. CreateMapRecordSecureAttempt      |
  |   POST /map-records/secure-attempts  |
  |------------------------------------->|
  |   { mapId, gameMode, ... }           |
  |                                      |
  |   Response: { attemptId, ... }       |
  |<-------------------------------------|
  |                                      |
  | 2. Player drives the map...          |
  |                                      |
  | 3. PatchMapRecordSecureAttempt       |
  |   PATCH /map-records/secure-attempts/{attemptId}
  |------------------------------------->|
  |   { time, respawnCount, ... }        |
  |                                      |
  | 4. Upload ghost data                 |
  |   (via multipart upload system)      |
  |------------------------------------->|
  |                                      |
  | 5. Server validates ghost:           |
  |    - Replays input sequence          |
  |    - Verifies physics determinism    |
  |    - Checks claimed time matches     |
  |    - Verifies checkpoint integrity   |
  |                                      |
  | 6. Record posted to leaderboard      |
  |<-------------------------------------|
```

#### Upload Mechanism

The upload uses a multi-part system (evidenced by the task classes):

1. `CNetNadeoServicesTask_CreateUpload` -- Initialize upload session
2. `CNetNadeoServicesTask_UploadPart` -- Upload chunks (for large files)
3. `CNetNadeoServicesTask_Upload` -- Complete/finalize upload
4. `CNetNadeoServicesTask_GetUpload` -- Check upload status

Rate limiting is enforced via `CGameDataFileTask_GhostDriver_UploadLimits`.

#### Validation on Upload [SPECULATIVE]

Based on the anti-cheat system architecture:
- Server runs the same deterministic physics simulation
- Input sequence from ghost is fed into server-side physics
- Resulting time and checkpoint crossings must match what client reported
- If client file checksums are in the banned list, record is rejected
- This is why physics determinism is critical -- any deviation between client and server physics invalidates the record

---

## 14. Complete Class Taxonomy

### CNet* (262 classes) -- Full Categorization

#### Infrastructure (20)
```
CNetNod                          -- Base network object
CNetSystem                       -- System init
CNetEngine                       -- Engine tick
CNetServer                       -- Server (DoReception/DoSending)
CNetClient                       -- Client (DoReception/DoSending)
CNetConnection                   -- TCP+UDP connection
CNetServerInfo                   -- Server metadata
CNetClientInfo                   -- Client metadata
CNetSource                       -- Network source
CNetURLSource                    -- URL source
CNetHttpClient                   -- HTTP (curl wrapper)
CNetHttpResult                   -- HTTP result
CNetIPSource                     -- IP management
CNetUPnP                         -- NAT traversal
CNetIPC                          -- Inter-process communication
CNetXmpp                         -- XMPP chat
CNetXmpp_Timer                   -- XMPP timer
CNetScriptHttpManager            -- Script HTTP
CNetScriptHttpRequest            -- Script HTTP request
CNetScriptHttpEvent              -- Script HTTP event
```

#### Wire Protocol Forms (8)
```
CNetFormConnectionAdmin          -- Connection management
CNetFormEnumSessions             -- Session enumeration
CNetFormQuerrySessions           -- Session queries
CNetFormTimed                    -- Timestamped messages
CNetFormPing                     -- Ping measurement
CNetFormNewPing                  -- Updated ping
CNetFormRpcCall                  -- XML-RPC calls
CNetFileTransferForm             -- File transfer
```

#### File Transfer (4)
```
CNetFileTransfer                 -- Base
CNetFileTransferDownload         -- Download
CNetFileTransferUpload           -- Upload
CNetFileTransferNod              -- Nod serialization
```

#### Master Server (16)
```
CNetMasterHost
CNetMasterServer
CNetMasterServerDownload
CNetMasterServerInfo
CNetMasterServerRequest
CNetMasterServerRequestTask
CNetMasterServerUptoDateCheck
CNetMasterServerUserInfo
CNetMasterServerTask_Connect
CNetMasterServerTask_GetApplicationConfig
CNetMasterServerTask_GetClientConfigUrls
CNetMasterServerTask_GetWaitingParams
CNetMasterServerTask_GetFeatureTimeLimit
CNetMasterServerTask_CheckFeatureTimeLimit
CNetMasterServerTask_SetFeatureTimeUse
CNetMasterServerTask_CheckLoginForSubscribe
CNetMasterServerTask_ImportAccount
CNetMasterServerTask_ImportAccount_IsFinished
CNetMasterServerTask_OpenSession
CNetMasterServerTask_Session_Get
CNetMasterServerTask_Session_InviteBuddy
CNetMasterServerTask_Session_JoinOrCreate
CNetMasterServerTask_Session_Leave
CNetMasterServerTask_Subscribe
```

#### UbiServices (32)
```
CNetUbiServices                  -- Service manager
CNetUbiServicesTask              -- Base task
  + 30 task subclasses (see Section 6)
```

#### UPlay PC (11)
```
CNetUplayPC                      -- UPlay wrapper
CNetUplayPCUserInfo              -- User info
  + 9 task subclasses (see Section 6)
```

#### Nadeo Services (175)
```
CNetNadeoServices                -- Service manager
CNetNadeoServicesRequest         -- Request base
CNetNadeoServicesRequestManager  -- Request manager
CNetNadeoServicesRequestTask     -- Async task
CNetNadeoServicesUserInfo        -- User info
  + 170 task subclasses (see Section 6)
```

### CWebServices* (297 classes) -- Full Categorization

#### Infrastructure (8)
```
CWebServices
CWebServicesTaskScheduler
CWebServicesTask
CWebServicesTaskResult
CWebServicesTaskSequence
CWebServicesTaskVoid
CWebServicesTaskWait
CWebServicesTaskWaitMultiple
```

#### Service Managers (20)
```
CWebServicesUserManager
CWebServicesUserInfo
CWebServicesIdentityManager
CWebServicesIdentityTaskManager
CWebServicesNotificationManager
CWebServicesAchievementService
CWebServicesActivityService
CWebServicesClientService
CWebServicesEventService
CWebServicesFriendService
CWebServicesMapService
CWebServicesMapRecordService
CWebServicesNewsService
CWebServicesPartyService
CWebServicesPermissionService
CWebServicesPreferenceService
CWebServicesPrestigeService
CWebServicesStatService
CWebServicesTagService
CWebServicesZoneService
```

#### Task Classes (~104)
```
  (See full listing in Section 6 -- approximately 104 unique task classes)
```

#### Result Types (~165)
```
  (See full listing in Section 6 -- approximately 165 result type classes)
```

### CGame*Network* (3 classes)
```
CGameNetwork                     -- Base game network
CGameCtnNetwork                  -- CTN (competition/trackmania) network
CGameManiaPlanetNetwork          -- ManiaPlanet-level network
```

### Game Network Forms (10 classes)
```
CGameNetForm                     -- Base game form
CGameNetFormPlayground           -- Gameplay events
CGameNetFormPlaygroundSync       -- Playground state sync
CGameNetFormTimeSync             -- Timer sync
CGameNetFormCallVote             -- Voting
CGameNetFormAdmin                -- Admin commands
CGameNetFormTunnel               -- Tunneled data
CGameNetFormBuddy                -- Friends
CGameNetFormVoiceChat            -- Voice frames
CGameNetOnlineMessage            -- Online messages
```

### Supporting Game Network Classes (5)
```
CGameNetPlayerInfo               -- Player state
CGameNetServerInfo               -- Server state
CGameNetFileTransfer             -- File transfer
CGameNetDataDownload             -- Data download
CGameNetwork                     -- Base network
```

### Total: 562+ networking-related classes

---

## 15. Browser Multiplayer Architecture

This section provides a concrete architecture for implementing Trackmania 2020's multiplayer features in a web browser.

### 15.1 Architecture Overview

```
+-------------------------------------------------------------------+
|                        BROWSER CLIENT                              |
|                                                                    |
|  +------------------+  +------------------+  +-----------------+   |
|  | Auth Manager     |  | REST API Client  |  | Game Engine     |   |
|  | (token refresh)  |  | (fetch + nadeo_v1)|  | (WebGL render) |   |
|  +--------+---------+  +--------+---------+  +--------+--------+   |
|           |                     |                     |            |
|  +--------+---------+  +--------+---------+  +--------+--------+   |
|  | WebSocket Client |  | GBX Parser       |  | Physics Engine  |   |
|  | (reliable chan)   |  | (map/ghost)      |  | (deterministic) |   |
|  +--------+---------+  +------------------+  +--------+--------+   |
|           |                                           |            |
|  +--------+-------------------------------------------+--------+   |
|  | WebRTC DataChannel (unreliable channel)                     |   |
|  +-------------------------------------------------------------+   |
+-------------------------------------------------------------------+
           |              |                      |
           v              v                      v
+-------------------+  +-------------------+  +-------------------+
| Auth Proxy Server |  | CORS Proxy        |  | Game Relay Server |
| (handles UPC/Ubi  |  | (routes to Nadeo  |  | (WS/WebRTC <->   |
|  token exchange)  |  |  APIs)            |  |  TCP/UDP bridge)  |
+-------------------+  +-------------------+  +-------------------+
           |              |                      |
           v              v                      v
+-------------------+  +-------------------+  +-------------------+
| Ubisoft APIs      |  | Nadeo APIs        |  | TM2020 Dedicated  |
| (ubi.com)         |  | (nadeo.live/club) |  | Server (TCP+UDP)  |
+-------------------+  +-------------------+  +-------------------+
```

### 15.2 Authentication: OAuth2 Flow Adaptation

The native game uses `UPC_TicketGet()` from a Windows DLL. For browser clients, there are two approaches:

**Approach A: Server-Side Auth Proxy (Recommended)**

```
Browser                 Auth Proxy (Node.js)         External APIs
   |                         |                            |
   | POST /auth/login        |                            |
   | { email, password }     |                            |
   |------------------------>|                            |
   |                         | POST public-ubiservices    |
   |                         |  .ubi.com/v3/profiles/     |
   |                         |  sessions                  |
   |                         |--------------------------->|
   |                         |  { ticket, sessionId }     |
   |                         |<---------------------------|
   |                         |                            |
   |                         | POST prod.trackmania.core  |
   |                         |  .nadeo.online/v2/         |
   |                         |  authentication/token/     |
   |                         |  ubiservices               |
   |                         |--------------------------->|
   |                         |  { accessToken, refresh }  |
   |                         |<---------------------------|
   |                         |                            |
   | { accessToken,          |                            |
   |   refreshToken,         |                            |
   |   expiresAt }           |                            |
   |<------------------------|                            |
   |                         |                            |
   | (client stores tokens,  |                            |
   |  refreshes at 55min)    |                            |
```

The auth proxy never stores tokens long-term -- it performs the exchange and returns tokens to the browser. The browser manages its own refresh cycle.

**Approach B: Dedicated Auth Token (for custom servers only)**

If building a fully custom multiplayer server (not connecting to Nadeo's infrastructure), skip the Nadeo auth entirely and implement standard OAuth2/JWT on your own server.

**Why a proxy is required**:
1. `UPC_TicketGet()` is a native DLL call -- impossible in browser
2. CORS: Ubisoft and Nadeo APIs do not set `Access-Control-Allow-Origin` for browser origins
3. Credentials: The Ubi-AppId and auth flow should not be exposed in client-side JavaScript

### 15.3 Real-Time Multiplayer: WebSocket vs WebRTC

The native game uses TCP+UDP dual-stack per connection. In the browser, the mapping is:

| Native Channel | Browser Equivalent | Use Case |
|---------------|-------------------|----------|
| TCP (reliable, ordered) | WebSocket | Chat, admin commands, file transfer, reliable state sync |
| UDP (unreliable, fast) | WebRTC DataChannel (unreliable mode) | Player positions, inputs, time-critical sync, voice |

**Option A: Full Fidelity (WebSocket + WebRTC)**

```javascript
// Reliable channel (replaces TCP)
const ws = new WebSocket('wss://relay.example.com/game/server123');
ws.binaryType = 'arraybuffer';
ws.onmessage = (e) => handleReliableMessage(new Uint8Array(e.data));

// Unreliable channel (replaces UDP)
const pc = new RTCPeerConnection(iceConfig);
const dc = pc.createDataChannel('game', {
    ordered: false,           // UDP-like: no ordering guarantee
    maxRetransmits: 0         // UDP-like: no retransmission
});
dc.binaryType = 'arraybuffer';
dc.onmessage = (e) => handleUnreliableMessage(new Uint8Array(e.data));
```

This is the highest-fidelity approach. The WebRTC DataChannel in unreliable mode closely mirrors UDP behavior: messages may arrive out of order, may be dropped, and have minimal overhead.

**Option B: WebSocket Only (Simpler)**

Tunnel everything over a single WebSocket connection. Add a 1-byte channel header:

```
+--------+--------+-----------+
| 0x01   | Length | Payload   |   <- Reliable channel (TCP-like)
+--------+--------+-----------+
| 0x02   | Length | Payload   |   <- "Unreliable" channel (still ordered)
+--------+--------+-----------+
```

Simpler to implement but adds ~1-5ms latency for time-critical data due to TCP head-of-line blocking.

**Option C: Custom Game Server (No Proxy)**

Reimplement the game server natively with WebSocket/WebRTC endpoints. No translation proxy needed. This is the right approach if building a custom multiplayer experience rather than connecting to existing Nadeo dedicated servers.

### 15.4 REST API: Standard fetch()

All Nadeo REST APIs can be called with standard `fetch()`:

```javascript
// Helper function for Nadeo API calls
async function nadeoFetch(url, token, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Authorization': `nadeo_v1 t=${token}`,
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
    return response.json();
}

// Example: Get map info
const map = await nadeoFetch(
    `https://prod.trackmania.core.nadeo.online/maps/${mapUid}`,
    coreToken
);

// Example: Get leaderboard
const records = await nadeoFetch(
    `https://live-services.trackmania.nadeo.live/api/token/leaderboard/group/Personal_Best/map/${mapUid}/top`,
    liveToken
);
```

**Note**: These calls will likely need to go through a CORS proxy since Nadeo's servers do not set browser-friendly CORS headers.

### 15.5 What Needs Server-Side Proxy

| Component | Needs Proxy? | Reason |
|-----------|-------------|--------|
| Authentication (Ubi/Nadeo) | YES | CORS + credential security |
| Nadeo REST APIs | LIKELY | CORS headers not set for browsers |
| Game server connection | YES | TCP/UDP not available in browsers |
| XMPP chat | LIKELY | No WebSocket endpoint on *.chat.maniaplanet.com |
| Vivox voice | N/A | Replace with WebRTC entirely |
| Ghost upload/download | LIKELY | CORS on upload endpoints |

### 15.6 Vivox Voice Chat Replacement

The native game uses Vivox (`VoiceChat.dll`) for voice chat with token-based authentication:

```
Native: Game -> Nadeo API (get Vivox token) -> VoiceChat.dll -> Vivox servers (RTP/SRTP)
Browser: Game -> Signaling server -> WebRTC peer connection (DTLS-SRTP)
```

Vivox integration in the native game:
- Token obtained via config keys `voicechatTokenVivox` / `voicechatConfigVivox`
- `VoicechatClient::createVivoxVoicechatToken` creates session tokens
- Voice frames can also be sent in-band via `CGameNetFormVoiceChat` over the game connection
- Channel management is per-server (one voice channel per game server)

For browser: use standard WebRTC audio with a signaling server. The channel management maps naturally to WebRTC "rooms."

---

### Legacy Browser Recreation Strategy (Feature Matrix)

| Feature | Effort | Impact | Priority | Browser Tech |
|---------|--------|--------|----------|-------------|
| Auth (via proxy) | Medium | CRITICAL | P0 | fetch() + server proxy |
| REST API (maps, records, seasons) | Low | HIGH | P0 | fetch() + CORS proxy |
| Ghost download/display | Medium | HIGH | P1 | fetch() + GBX parser |
| Real-time multiplayer | VERY HIGH | HIGH | P1 | WebSocket + WebRTC |
| XMPP chat (via proxy) | Medium | MEDIUM | P2 | XMPP.js + WS proxy |
| WebRTC voice chat | High | LOW | P3 | WebRTC audio |
| XML-RPC controller | Medium | MEDIUM | P2 | WS proxy + xmlrpc |
| Anti-cheat integration | High | MEDIUM | P2 | JS input recording |
| Matchmaking | Medium | MEDIUM | P2 | REST API polling |

---

## 16. Minimum Viable Online Specification

This section defines the minimum set of features needed for a browser-based Trackmania experience with online functionality. Each tier builds on the previous.

### Tier 0: Offline with Online Data (Easiest)

**Goal**: Play maps offline but load maps/ghosts from Nadeo's servers.

**Required Components**:
1. Auth proxy server (handles Ubi+Nadeo token exchange)
2. CORS proxy for Nadeo API calls
3. GBX map parser (JavaScript)
4. GBX ghost parser (JavaScript)
5. Physics engine (deterministic, 100Hz tick)
6. Renderer (WebGL)

**API Calls Needed**:

| API | Method | Endpoint [SPECULATIVE] | Purpose |
|-----|--------|----------------------|---------|
| Auth | POST | `/v2/authentication/token/ubiservices` | Get NadeoServices token |
| Auth | POST | `/v2/authentication/token/nadeoservices` | Get NadeoLiveServices token |
| Auth | POST | `/v2/authentication/token/refresh` | Refresh tokens |
| Maps | GET | `/maps/{mapId}` | Get map metadata |
| Maps | GET | (download URL from metadata) | Download .Map.Gbx file |
| Ghosts | GET | (ghost download URL) | Download ghost for display |
| Seasons | GET | `/seasons` | Get current campaign maps |

**Architecture**:
```
Browser                    CORS Proxy               Nadeo APIs
   |                          |                         |
   | fetch(/api/maps/...)     |                         |
   |------------------------->| GET /maps/...           |
   |                          |------------------------>|
   |   map metadata           |                         |
   |<-------------------------|<------------------------|
   |                          |                         |
   | fetch(map download URL)  |                         |
   |------------------------->| GET (CDN URL)           |
   |                          |------------------------>|
   |   .Map.Gbx binary        |                         |
   |<-------------------------|<------------------------|
```

**Estimated effort**: 2-4 weeks (assuming physics engine and renderer exist)

### Tier 1: Leaderboards and Record Submission

**Goal**: Submit times and view leaderboards.

**Additional Components**:
1. Ghost recording (capture inputs at 100Hz)
2. Ghost serialization (produce .Ghost.Gbx)
3. Secure attempt flow implementation

**Additional API Calls**:

| API | Method | Endpoint [SPECULATIVE] | Purpose |
|-----|--------|----------------------|---------|
| Records | POST | `/map-records/secure-attempts` | Create secure attempt |
| Records | PATCH | `/map-records/secure-attempts/{id}` | Submit result |
| Upload | POST | `/uploads` | Create upload session |
| Upload | PUT | `/uploads/{id}` | Upload ghost data |
| Records | GET | `/map-records` | View leaderboard |
| Display | GET | `/accounts/display-names` | Resolve player names |

**Critical challenge**: Ghost format must match what Nadeo's server-side validator expects. The physics must be byte-for-byte deterministic with the native game.

**Estimated effort**: 4-8 weeks (ghost format RE is the bottleneck)

### Tier 2: Real-Time Multiplayer (Spectate)

**Goal**: Connect to a live game server and spectate.

**Additional Components**:
1. WebSocket relay server (WS <-> TCP bridge)
2. Game protocol parser (CNetForm* binary format)
3. Player position interpolation
4. Game timer synchronization

**Network Protocol Required**:
- Parse `CGameNetFormPlayground` messages for player state
- Parse `CGameNetFormTimeSync` for timer sync
- Parse `CGameNetFormPlaygroundSync` for checkpoint data
- Handle `CNetFormConnectionAdmin` for session setup

**Critical challenge**: The CNetForm* wire protocol is [UNKNOWN]. Reverse engineering the binary format of each form type is the primary blocker.

**Estimated effort**: 8-16 weeks (wire protocol RE is the bottleneck)

### Tier 3: Real-Time Multiplayer (Play)

**Goal**: Full participation in multiplayer races.

**Additional Components**:
1. WebRTC DataChannel for unreliable input transmission
2. Input encoding matching native format
3. Full game state synchronization
4. Checkpoint/finish detection
5. Anti-cheat ghost submission from browser

**This tier is where the full TCP+UDP dual-stack architecture matters**:
- Inputs sent via unreliable channel (WebRTC DataChannel) at 100Hz
- State sync and admin messages via reliable channel (WebSocket)
- Server processes inputs identically to native clients

**Estimated effort**: 16-32 weeks

### Tier 4: Full Feature Parity

**Goal**: Complete online experience including chat, voice, matchmaking.

**Additional Components**:
1. XMPP proxy for text chat
2. WebRTC audio for voice chat
3. Matchmaking queue integration
4. Squad/party system
5. Club features

**Estimated effort**: 32-64 weeks

### Minimum Technology Stack

For Tier 0 (minimum viable):

| Component | Technology | Notes |
|-----------|-----------|-------|
| Auth Proxy | Node.js + Express | ~200 lines, handles token exchange |
| CORS Proxy | nginx or Cloudflare Worker | Simple header rewriting |
| GBX Parser | JavaScript (ArrayBuffer) | Community libs exist (gbx.js) |
| Physics | JavaScript/WASM | Must be deterministic at 100Hz |
| Renderer | WebGL2 / Three.js | Block-based rendering |
| UI | HTML/CSS | ManiaLink could map to HTML |

---

## 17. Key Unknowns

### Critical Unknowns (Block Browser Recreation)

1. **[UNKNOWN]** Exact wire protocol format for TCP/UDP game connections (CNetForm* binary layout, header structure, framing) -- this is the single biggest blocker for real-time multiplayer
2. **[PARTIALLY RESOLVED]** Complete REST API URL structure -- base URLs now VERIFIED from Openplanet (`prod.trackmania.core.nadeo.online`, `live-services.trackmania.nadeo.live`, `meet.trackmania.nadeo.club`); specific endpoint paths are still SPECULATIVE based on task class names
3. **[RESOLVED]** Authentication header format -- confirmed as `Authorization: nadeo_v1 t=<token>` from Openplanet NadeoServices plugin source
4. **[UNKNOWN]** Ghost binary format details for upload/download -- community tools (GBX.NET, gbx.js) have partially documented the GBX container format, but the secure-attempt validation data embedded in ghosts is unknown

### Important Unknowns

5. **[UNKNOWN]** Whether QUIC/HTTP3 is actively used (OpenSSL +quic is present but may be dormant)
6. **[UNKNOWN]** Anti-cheat server endpoint URL (only config key name `"AntiCheatServerUrl"` found)
7. **[UNKNOWN]** CNetIPC target process identity (possibly Ubisoft Connect overlay or anti-cheat monitor)
8. **[UNKNOWN]** Exact matchmaking algorithm parameters (ELO/Glicko2 settings, queue timeouts, skill ranges)
9. **[UNKNOWN]** Whether the game uses peer-to-peer connections or only dedicated servers
10. **[UNKNOWN]** CNetFormTimed and CNetFormPing wire format details
11. **[UNKNOWN]** How CNetFileTransferNod serializes game objects for in-game transfer
12. **[UNKNOWN]** Details of the "Harbour" social platform integration beyond config key names
13. **[UNKNOWN]** Client prediction and lag compensation specifics
14. **[UNKNOWN]** XMPP authentication mechanism (likely token-based, but exact flow unknown)
15. **[UNKNOWN]** Vivox token generation parameters

### Resolved (Previously Unknown, Now Known)

- ~~Authentication header format~~: **RESOLVED** -- `Authorization: nadeo_v1 t=<token>` confirmed from Openplanet plugin source
- ~~Nadeo Services token format~~: **RESOLVED** -- Confirmed as JWT with `iss`, `aud`, `sub`, `exp`, `rat` claims (from Openplanet)
- ~~Base URLs for Nadeo APIs~~: **RESOLVED** -- Core: `prod.trackmania.core.nadeo.online`, Live: `live-services.trackmania.nadeo.live`, Meet: `meet.trackmania.nadeo.club` (from Openplanet)

### Partially Known

16. **[PARTIAL]** HTTP request format -- we know headers (gzip, application/binary, Range, Timezone) but not all content type variations
17. **[PARTIAL]** State machine state values -- we have hex values but not semantic meanings for most intermediate states
18. **[PARTIAL]** Ghost binary format -- community tools (gbx.js, GBX.NET) have partially documented this, but the secure-attempt validation data format is unknown

---

## Appendix A: Function Address Reference

### Decompiled Functions

| Address | Function | File |
|---------|----------|------|
| `0x1403050a0` | `CNetHttpClient::InternalConnect` | `CNetHttpClient_InternalConnect.c` |
| `0x14030c3f0` | `CNetHttpClient::CreateRequest` | `CNetHttpClient_CreateRequest.c` |
| `0x140b00500` | `CGameCtnNetwork::ConnectToInternet` | `CGameCtnNetwork_ConnectToInternet.c` |
| `0x140356160` | Nadeo token creation wrapper | `nadeoservices_token_create_from_ubiservices.c` |
| `0x140af9a40` | `CGameCtnNetwork::MainLoop_Menus` | `CGameCtnNetwork__MainLoop_Menus.c` |
| `0x140aff380` | `CGameCtnNetwork::MainLoop_PlaygroundPlay` | `CGameCtnNetwork__MainLoop_PlaygroundPlay.c` |
| `0x140afc320` | `CGameCtnNetwork::MainLoop_SetUp` | `CGameCtnNetwork__MainLoop_SetUp.c` |

### Key Undecompiled Functions

| Address | Probable Function | Evidence |
|---------|-------------------|----------|
| `0x1403089f0` | `CNetServer::DoReception` | String xref |
| `0x1414a1c80` | `CNetClient::DoReception` | String xref |
| `0x140355fe0` | Nadeo API request executor | Called from token wrapper |
| `0x140bc5a00` | Network subsystem init | Called from ConnectToInternet + MainLoop_SetUp |
| `0x140c8f930` | Session params setup | Called from ConnectToInternet |
| `0x140bd1180` | Setup state handler | Called from MainLoop_SetUp |
| `0x140b28fa0` | [UNKNOWN] | Called from MainLoop_SetUp state 0x1271 |
| `0x140afa000` | Menu sub-state handler | Called from MainLoop_Menus |
| `0x140afa950` | Menu command handler | Called from MainLoop_Menus |
| `0x140afa480` | [UNKNOWN] | Called from MainLoop_Menus |
| `0x140afb0a0` | Menu connection handler | Called from MainLoop_Menus |
| `0x140bc2a20` | [UNKNOWN] network helper | Called from MainLoop_Menus, MainLoop_SetUp |
| `0x140affcf0` | [UNKNOWN] | Called from MainLoop_SetUp |
| `0x140b00240` | [UNKNOWN] | Called from MainLoop_SetUp |
| `0x140bc1a90` | [UNKNOWN] network setup | Called at end of MainLoop_SetUp |

## Appendix B: Build Environment

### Nadeo Code Path
```
C:\Nadeo\CodeBase_tm-retail\Nadeo\Engines\NetEngine\source\NetHttpClient_Curl.cpp
```

### UbiServices SDK Path
```
D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\harbourcommon\libraries\_fetch\
Dependencies: openssl (1.1.1t+quic), curl
```

### External Libraries (Static)
- **libcurl**: Multi-handle async HTTP
- **OpenSSL 1.1.1t+quic**: TLS + potential QUIC
- **xmlrpc-c**: XML-RPC implementation
- **Vivox SDK**: Voice chat (VoiceChat.dll -- dynamic)
- **UPC SDK**: Ubisoft Connect (upc_r2_loader64.dll -- dynamic)

---

## 18. Sequence Diagrams

### 18.1 Full Authentication Sequence (Native Game)

```
UbiConnect    Game Client      UPC DLL        Ubisoft API          Nadeo Core API
  Client       (TM2020)     (upc_r2)      (ubi.com)          (nadeo.online)
    |              |             |               |                    |
    | Running      |             |               |                    |
    |              |             |               |                    |
    |              | UPC_ContextCreate            |                    |
    |              |------------>|               |                    |
    |              |  context    |               |                    |
    |              |<------------|               |                    |
    |              |             |               |                    |
    |              | UPC_TicketGet               |                    |
    |              |------------>|               |                    |
    |              |             | (reads from   |                    |
    |              |             |  UbiConnect   |                    |
    |              |             |  client)      |                    |
    |              |  ticket     |               |                    |
    |              |<------------|               |                    |
    |              |             |               |                    |
    |              | CNetUbiServicesTask_CreateSession                |
    |              |             |               |                    |
    |              | POST /v3/profiles/sessions  |                    |
    |              | Ubi-AppId: 86263886-...     |                    |
    |              | Authorization: ubi_v1 t=<ticket>                 |
    |              |---------------------------->|                    |
    |              |   { ticket, sessionId }     |                    |
    |              |<----------------------------|                    |
    |              |             |               |                    |
    |              | CNetNadeoServicesTask_AuthenticateWithUbiServices|
    |              |             |               |                    |
    |              | POST /v2/authentication/token/ubiservices        |
    |              | Authorization: ubi_v1 t=<ubi-ticket>             |
    |              | Body: { audience: "NadeoServices" }              |
    |              |---------------------------------------------------->|
    |              |   { accessToken (JWT), refreshToken }               |
    |              |<----------------------------------------------------|
    |              |             |               |                    |
    |              | CWebServicesTask_PostConnect (6 sub-tasks)       |
    |              |   PostConnect_UrlConfig                          |
    |              |   PostConnect_PlugInList                         |
    |              |   PostConnect_AdditionalFileList                 |
    |              |   PostConnect_BannedCryptedChecksumsList         |
    |              |   PostConnect_Tag                                |
    |              |   PostConnect_Zone                               |
    |              |---------------------------------------------------->|
    |              |   (various config/init data)                        |
    |              |<----------------------------------------------------|
    |              |             |               |                    |
    |              | CONNECTED -- can now make API calls              |
    |              |             |               |                    |
    |              | ... 55 minutes later ...    |                    |
    |              |             |               |                    |
    |              | CNetNadeoServicesTask_RefreshNadeoServicesAuthenticationToken
    |              | POST /v2/authentication/token/refresh            |
    |              | Body: { refreshToken: "..." }                    |
    |              |---------------------------------------------------->|
    |              |   { new accessToken, new refreshToken }             |
    |              |<----------------------------------------------------|
```

### 18.2 Joining a Game Server

```
Game Client             Nadeo API              Game Server (Dedicated)
    |                      |                         |
    | 1. FindServers()     |                         |
    | GET /servers         |                         |
    |--------------------->|                         |
    |   [{ ip, port, ... }]|                         |
    |<---------------------|                         |
    |                      |                         |
    | 2. CNetClient::InitNetwork                     |
    |   TCP connect to server:2350                   |
    |----------------------------------------------->|
    |   TCP handshake complete                       |
    |<-----------------------------------------------|
    |                      |                         |
    | 3. CNetConnection: TestingUDP = true           |
    |   UDP probe to server:2350                     |
    |----------------------------------------------->|
    |   UDP response (or timeout -> TCP-only mode)   |
    |<-----------------------------------------------|
    |                      |                         |
    | 4. CNetFormConnectionAdmin                     |
    |   Session negotiation                          |
    |<---------------------------------------------->|
    |                      |                         |
    | 5. CNetFormEnumSessions                        |
    |   Query available sessions                     |
    |----------------------------------------------->|
    |   Session list                                 |
    |<-----------------------------------------------|
    |                      |                         |
    | 6. Map check -- do we have the map?            |
    |   If no: CNetFileTransferDownload              |
    |   (TCP channel, chunked .Map.Gbx transfer)     |
    |<---------------------------------------------->|
    |                      |                         |
    | 7. CGameCtnNetwork::MainLoop_PlaygroundPrepare |
    |   Load map, init physics                       |
    |                      |                         |
    | 8. CGameCtnNetwork::MainLoop_PlaygroundPlay    |
    |   Begin gameplay loop                          |
    |                      |                         |
    | 9. Per-frame sync:                             |
    |   NetUpdate_BeforePhy: recv remote inputs      |
    |<-----------------------------------------------|
    |   Physics step (deterministic at 100Hz)        |
    |   NetUpdate_AfterPhy: send local state         |
    |----------------------------------------------->|
    |   NetLoop_Synchronize: align game timer        |
    |<---------------------------------------------->|
    |                      |                         |
    | 10. CGameNetFormPlayground (UDP)               |
    |   Player position + input each tick            |
    |<---------------------------------------------->|
    |                      |                         |
    | 11. CGameNetFormTimeSync (UDP)                 |
    |   Game timer alignment                         |
    |<---------------------------------------------->|
```

### 18.3 Submitting a Time (Leaderboard)

```
Game Client                     Nadeo Core API             Nadeo Live API
    |                                |                          |
    | 1. Start race                  |                          |
    |                                |                          |
    | CreateMapRecordSecureAttempt   |                          |
    | POST .../secure-attempts       |                          |
    | { mapId, gameMode }            |                          |
    |------------------------------->|                          |
    |   { attemptId }                |                          |
    |<-------------------------------|                          |
    |                                |                          |
    | 2. Race in progress...         |                          |
    |   Recording inputs at 100Hz    |                          |
    |   Recording checkpoint times   |                          |
    |                                |                          |
    | 3. Cross finish line           |                          |
    |   raceTime = 42.371s           |                          |
    |                                |                          |
    | 4. PatchMapRecordSecureAttempt |                          |
    | PATCH .../secure-attempts/{id} |                          |
    | { time: 42371, respawnCount,   |                          |
    |   checkpointTimes: [...] }     |                          |
    |------------------------------->|                          |
    |   { status: "pending" }        |                          |
    |<-------------------------------|                          |
    |                                |                          |
    | 5. Upload ghost                |                          |
    | CreateUpload                   |                          |
    | POST /uploads                  |                          |
    |------------------------------->|                          |
    |   { uploadId, uploadUrl }      |                          |
    |<-------------------------------|                          |
    |                                |                          |
    | PUT /uploads/{id}              |                          |
    | Body: <ghost binary data>      |                          |
    |------------------------------->|                          |
    |   { status: "complete" }       |                          |
    |<-------------------------------|                          |
    |                                |                          |
    | 6. Server-side validation      |                          |
    |   (async, takes seconds)       |                          |
    |   - Replay ghost inputs        |                          |
    |   - Verify physics determinism |                          |
    |   - Check time matches         |                          |
    |   - Verify checksums           |                          |
    |                                |                          |
    | 7. Record appears on LB        |                          |
    |                                | sync ------------------>|
    |                                |                          |
    | 8. GET .../leaderboard/...     |                          |
    |                                |                          |
    |------------------------------------------------->|
    |   [{ accountId, time, ... }]                     |
    |<-------------------------------------------------|
```

### 18.4 Matchmaking Flow

```
Game Client              Nadeo API           Harbour/Matchmaking      Game Server
    |                       |                      |                      |
    | 1. Join matchmaking   |                      |                      |
    | AddToWaitingQueue     |                      |                      |
    | POST /waiting-queue   |                      |                      |
    |---------------------->|                      |                      |
    |                       | Forward to Harbour   |                      |
    |                       |--------------------->|                      |
    |                       |                      |                      |
    | 2. Wait in queue      |                      |                      |
    |   (polling or push)   |                      |                      |
    |<.......................| ..................-->|                      |
    |                       |                      |                      |
    |                       |                      | 3. Match found       |
    |                       |                      | Assign server        |
    |                       |                      |--------------------->|
    |                       |                      |   server ready       |
    |                       |                      |<---------------------|
    |                       |                      |                      |
    | 4. Match details      |                      |                      |
    | { serverIp, port,     |                      |                      |
    |   matchId, ... }      |                      |                      |
    |<----------------------|<---------------------|                      |
    |                       |                      |                      |
    | 5. Connect to server (see "Joining a Game Server" diagram)         |
    |------------------------------------------------------------------>|
    |                       |                      |                      |
    | 6. Play match         |                      |                      |
    |<=================================================================>|
    |                       |                      |                      |
    | 7. Match complete     |                      |                      |
    | Activity_ReportMatchResult                   |                      |
    | POST /activity/matches/{id}/result           |                      |
    |---------------------->|                      |                      |
    |                       | Update rankings      |                      |
    |                       |--------------------->|                      |
    |                       |                      |                      |
    | 8. Ladder update      |                      |                      |
    | Ladder_SetMatchMakingMatchId                  |                      |
    |                       |                      |                      |
```

### 18.5 Voice Chat Session (Vivox)

```
Game Client               Nadeo API              Vivox Servers
    |                         |                       |
    | 1. Join server with     |                       |
    |    voice enabled        |                       |
    |                         |                       |
    | 2. Request Vivox token  |                       |
    | (voicechatTokenVivox    |                       |
    |  config key)            |                       |
    |------------------------>|                       |
    |   { vivoxToken,         |                       |
    |     vivoxConfig }       |                       |
    |<------------------------|                       |
    |                         |                       |
    | 3. VoiceChat.dll loads  |                       |
    | createVivoxVoicechatToken                       |
    |                         |                       |
    | 4. Connect to Vivox     |                       |
    |   (with token)          |                       |
    |---------------------------------------->|
    |   session established   |               |
    |<----------------------------------------|
    |                         |               |
    | 5. Audio stream         |               |
    |   (RTP/SRTP)            |               |
    |<===============================>|
    |                         |               |
    | 6. In-band voice also   |               |
    |   possible via          |               |
    |   CGameNetFormVoiceChat |               |
    |   (UDP, game conn)      |               |
    |                         |               |
    | 7. Speaking state       |               |
    |   changes trigger       |               |
    |   script events:        |               |
    |   VoiceChatEvent_       |               |
    |   SpeakingHasChanged    |               |
```

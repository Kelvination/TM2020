# Trackmania 2020 Network Stack

Trackmania 2020 uses an 11-layer network architecture built on the ManiaPlanet engine. The stack spans raw sockets at the bottom, through HTTP/REST services, up to game-specific online services with 562+ networking classes total.

This page covers the full network system: stack overview, connection lifecycle, authentication, APIs, real-time multiplayer protocol, and browser recreation strategy.

---

## Network Stack Overview

The network stack divides into three groups: transport (layers 0-1), services (layers 2-9), and game logic (layers 10-11). Each layer wraps the one below it.

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

### Connection Types

| Type | Transport | Purpose |
|------|-----------|---------|
| Game Server (P2P/Dedicated) | TCP + UDP (Winsock2) | Gameplay, file transfer |
| Nadeo Services API | HTTPS (libcurl + OpenSSL) | REST API for maps, records, auth |
| Ubisoft Services API | HTTPS (libcurl + OpenSSL) | Sessions, friends, achievements |
| Master Server | HTTPS (libcurl) | Server listing, authentication tokens |
| XMPP Chat | TCP (TLS) | Text chat, presence |
| Voice Chat | [UNKNOWN] (Vivox SDK) | Voice communication |
| IPC | [UNKNOWN] (CNetIPC) | Local process communication |

### Game Network State Machine

The game network operates as a state machine. `CGameCtnNetwork::MainLoop_*` methods drive transitions through connection, setup, and gameplay phases.

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

| Method | Address | Phase |
|--------|---------|-------|
| `"CGameCtnNetwork::MainLoop_Menus"` | `0x141c2b328` | Menu/lobby phase |
| `"CGameCtnNetwork::MainLoop_Menus_Lan"` | `0x141c2b4f0` | LAN browsing |
| `"CGameCtnNetwork::MainLoop_Menus_Internet"` | `0x141c2b518` | Internet browsing |
| `"CGameCtnNetwork::MainLoop_Menus_DialogJoin"` | `0x141c2b568` | Join dialog |
| `"CGameCtnNetwork::MainLoop_Menus_ApplyCommand"` | `0x141c2b4c0` | Apply menu command |
| `"CGameCtnNetwork::MainLoop_SetUp"` | `0x141c2b6e8` | Pre-game setup |
| `"CGameCtnNetwork::MainLoop_Prepare"` | `0x141c2b708` | Preparation phase |
| `"CGameCtnNetwork::MainLoop_PlaygroundPrepare"` | `0x141c2b828` | Map loading |
| `"CGameCtnNetwork::MainLoop_PlaygroundPlay"` | `0x141c2b8e0` | Active gameplay |
| `"CGameCtnNetwork::MainLoop_PlaygroundExit"` | `0x141c2b8b0` | Map exit/cleanup |
| `"CGameCtnNetwork::MainLoop_SpectatorSwitch"` | `0x141c2dae0` | Spectator mode transition |

<details>
<summary>Decompiled state machine details</summary>

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

</details>

---

## How Connections Work

### TCP + UDP Dual-Stack Protocol

Every game connection uses TCP and UDP simultaneously. TCP carries reliable data (chat, admin, file transfers). UDP carries time-critical data (player positions, inputs).

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

"Nod" totals refer to serialized game objects. ManiaPlanet's base object class is `CMwNod`.

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

### Joining a Game Server

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

### NAT Traversal

The game supports UPnP for automatic port forwarding via `CNetUPnP` and `CNetIPSource`. [UNKNOWN] whether STUN/TURN is also used.

---

## Authentication

Authentication uses a 4-step token exchange chain. The native game gets a UPC ticket from Ubisoft Connect, exchanges it for a Ubisoft session, then converts that into Nadeo JWTs.

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

Three audiences grant access to different API domains:

| Audience | API Domain | Token Source | Purpose |
|----------|-----------|-------------|---------|
| `NadeoServices` | `prod.trackmania.core.nadeo.online` | Direct from auth exchange | Core APIs: auth, maps, records, accounts |
| `NadeoLiveServices` | `live-services.trackmania.nadeo.live` | Exchange from NadeoServices token | Live APIs: leaderboards, competitions, clubs |
| `NadeoLiveServices` | `meet.trackmania.nadeo.club` | Same as above | Meet APIs: matchmaking, ranked |

**DEPRECATED** (as of 2024-01-31): `NadeoClubServices` audience. Now maps to `NadeoLiveServices`.

Source: Openplanet NadeoServices plugin (`NadeoServices/NadeoServices.as`) -- VERIFIED against running game.

### JWT Structure [VERIFIED]

Nadeo access tokens are JWTs (JSON Web Tokens, a compact URL-safe token format carrying signed JSON claims). Decoded:

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

### Authorization Header Format [VERIFIED from Openplanet]

All Nadeo API calls use:
```
Authorization: nadeo_v1 t=<access-token>
```

This is NOT a standard Bearer token format. The `nadeo_v1` prefix and `t=` parameter are Nadeo-specific.

### Full Authentication Sequence (Native Game)

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

### Authentication for Browser Clients

The native game uses `UPC_TicketGet()` from a Windows DLL. For browser/third-party access, the community has documented an email/password alternative:

**Step 1: Ubisoft Session** [SPECULATIVE -- community-documented, not from decompilation]

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

<details>
<summary>Decompiled authentication flow</summary>

**Step 1: UPC SDK** [VERIFIED from binary]

**DLL**: `upc_r2_loader64.dll` loaded at `0x14285ab28`
**Direct import**: `UPC_TicketGet` at IAT `0x1428c80d2`

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

**Step 3: Nadeo Token Exchange (decompiled)**

**Decompiled function**: `FUN_140356160` at `0x140356160`

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

This thin wrapper delegates to `FUN_140355fe0` (the actual HTTP request executor). The function at `0x140355fe0` constructs a POST request to `core.trackmania.nadeo.live` with the UbiServices session token.

**Connection Workflow (High-Level)**

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

**CGameCtnNetwork::ConnectToInternet (decompiled)**

**Address**: `0x140b00500`

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

**Offline Fallback**

Evidence for offline mode:
- `CWebServicesTask_CheckNetworkAvailability` exists as a task class
- `CGameNetwork::CheckInternetAtStart` runs at startup
- The state machine in `MainLoop_Menus` checks global flags `DAT_141fbbee8` / `DAT_141fbbf0c` before deciding whether to connect
- If both flags are zero, the game proceeds to menus without internet (`goto LAB_140af9c4e`)

</details>

---

## HTTP Client Architecture

The HTTP client wraps libcurl for all REST communication. It uses curl's multi interface (asynchronous, non-blocking I/O) with a dual-threaded processing model.

**Source file**: `C:\Nadeo\CodeBase_tm-retail\Nadeo\Engines\NetEngine\source\NetHttpClient_Curl.cpp`

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

The web services layer uses a dedicated background thread for HTTP I/O:
```
CWebServices::Update_MainThread        (0x141b7dda8)  -- main thread: process results, update UI
CWebServices::Update_WebServicesThread  (0x141b7ddf0)  -- background: HTTP I/O
CWebServicesTaskScheduler::DispatchTasks (0x141b7dc78)  -- task dispatch
```

### Request Creation

HTTP method selection uses `param_3`: `0` = POST, `1` = GET, `3-5` = [UNKNOWN methods, possibly PUT/DELETE/PATCH].

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

<details>
<summary>Decompiled CNetHttpClient::InternalConnect</summary>

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

Key insight: The curl multi handle comes from a **global** pointer at `DAT_1420ba2f8`. One shared curl multi-handle serves all HTTP clients.

</details>

### Transport Layer Details

**Winsock2 (WS2_32.DLL)**: Only `WS2_32.DLL::Ordinal_1` appears in the IAT. Additional Winsock functions resolve at runtime via `LoadLibraryA`/`GetProcAddress`.

**libcurl**: Statically compiled into the binary.

| String | Address | Significance |
|--------|---------|--------------|
| `"[Net] HTTP: curl_version="` | `0x141b7b298` | Version logging at init |
| `"CurlPerform"` | `0x141b7b530` | Profiling marker |
| `"Failed in call to curl_multi_init"` | `0x141b7b578` | Multi-handle creation |
| `"Failed in call to curl_easy_init"` | `0x141b7b748` | Easy-handle creation |
| `"# Netscape HTTP Cookie File\n# https://curl.se/..."` | `0x1419fdef0` | Cookie persistence |
| `"# Your alt-svc cache. https://curl.se/..."` | `0x1419ff230` | Alt-Svc caching |

The Alt-Svc cache suggests the game may opportunistically use HTTP/2 or HTTP/3 when servers advertise Alt-Svc headers.

**OpenSSL**: Statically compiled, version `OpenSSL 1.1.1t+quic  7 Feb 2023` (`0x141983c80`). The `+quic` variant indicates QUIC protocol support via the quictls fork. Whether QUIC/HTTP3 is actively used is [UNKNOWN].

**UbiServices SDK HTTP Layer** (separate curl wrapper):

| String | Address |
|--------|---------|
| `HttpRequestCurl::stepWaitForResume` | `0x141a24f20` |
| `HttpRequestCurl::stepWaitStatusCode` | `0x141a24f48` |
| `HttpRequestCurl::stepWaitForComplete` | `0x141a24f90` |

Build path: `D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\dependencies\_fetch\curl\lib\vtls\openssl.c`

---

## Real-Time Multiplayer Protocol

### Deterministic Simulation Model

The networking follows a deterministic lockstep model. The BeforePhy/AfterPhy naming confirms that physics runs identically on all clients given the same inputs.

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

| Method | Address | Purpose |
|--------|---------|---------|
| `NetUpdate_BeforePhy` | `0x141c2b348` | Receive remote inputs before physics |
| `NetUpdate_AfterPhy` | `0x141c2b388` | Send local results after physics |
| `NetLoop_Synchronize` | `0x141c49c28` | Master synchronization loop |
| `SynchronizeGameTimer` | `0x141c49bb0` | Game timer sync |
| `PlaygroundSync_UpdateInfos` | `0x141cf75d8` | Gameplay info sync |

### Network Message Forms

The engine uses typed "form" messages inherited from ManiaPlanet. Engine-level forms handle infrastructure. Game-level forms handle gameplay.

**Engine-Level Forms**

| Form Class | Purpose | Wire Format |
|-----------|---------|-------------|
| `CNetFormConnectionAdmin` | Connection management (connect, disconnect, auth) | [UNKNOWN] |
| `CNetFormEnumSessions` | Session enumeration | [UNKNOWN] |
| `CNetFormQuerrySessions` | Session queries (note: typo "Querry" in original) | [UNKNOWN] |
| `CNetFormTimed` | Timestamped messages (base for game forms) | [UNKNOWN] |
| `CNetFormPing` | Ping/latency measurement | [UNKNOWN] |
| `CNetFormNewPing` | Updated ping protocol | [UNKNOWN] |
| `CNetFormRpcCall` | XML-RPC method invocation | [UNKNOWN] |
| `CNetFileTransferForm` | File transfer protocol | [UNKNOWN] |

**Game-Level Forms**

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

### Ghost System (Input Recording)

Ghosts record inputs for replay and multiplayer validation:

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

### Data Synchronization [UNKNOWN Details]

The exact wire format for the following is [UNKNOWN]:

1. **Player position sync**: Sent via `CGameNetFormPlayground` over UDP
2. **Input sync**: Encoded in `CGameNetFormPlaygroundSync`
3. **Server authority**: Evidence of server-authoritative model from `CGameNetServerInfo` and anti-cheat upload system
4. **Client prediction**: [UNKNOWN] whether clients predict ahead or wait for server confirmation
5. **Lag compensation**: [UNKNOWN] specific mechanisms, though `CGameNetFormTimeSync` handles timer alignment

### Tunnel System

The tunnel system sends arbitrary data through the game connection. Server controllers and plugins use it.

| Method | Address |
|--------|---------|
| `CGameNetwork::Tunnel_Update` | [methods] |
| `CGameNetFormTunnel` | `0x141c616f0` |
| `ManiaPlanet.TunnelDataReceived` | `0x141d04938` |

---

## API Reference

### Confidence Legend

- **[VERIFIED]** -- Confirmed from Openplanet plugin source, community tools, or decompiled URL strings
- **[SPECULATIVE]** -- Inferred from task class names following naming conventions; actual URL paths may differ
- **[COMMUNITY]** -- Documented by community API projects but not confirmed from decompilation

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

| Service | Base URL | Audience Token |
|---------|----------|---------------|
| **Core** | `https://prod.trackmania.core.nadeo.online` | `NadeoServices` |
| **Live** | `https://live-services.trackmania.nadeo.live` | `NadeoLiveServices` |
| **Meet** | `https://meet.trackmania.nadeo.club` | `NadeoLiveServices` |

### Inferred API Endpoint Map [SPECULATIVE]

> **Warning**: All URL paths below are speculative guesses based on task class naming conventions. They have NOT been observed in network traffic or confirmed from decompiled URL-construction code. Actual API paths may differ.

The naming convention `CNetNadeoServicesTask_<Verb><Resource>` maps to HTTP methods:

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

<details>
<summary>Complete inferred endpoint tables</summary>

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

#### UbiServices API Endpoints

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

#### UbiServices Party Endpoints

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

</details>

---

## XML-RPC Dedicated Server Protocol

The game includes a full XML-RPC implementation inherited from ManiaPlanet. Server controllers (PyPlanet, EvoSC, ManiaControl) use this protocol to script and remotely control dedicated servers.

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

### XML-RPC Callbacks (25 callbacks)

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

A server controller connects to the dedicated server's XML-RPC port (default: 5000). Callbacks are asynchronous notifications sent from server to controller. The `ManiaPlanet.ModeScriptCallbackArray` callback carries custom game mode events as a method name and array of string parameters.

---

## Voice and Text Chat

### Vivox Voice Chat

TM2020 uses a three-layer voice chat architecture. Token-based authentication gates access.

```
Game (Trackmania.exe)
  |
  +-- VoiceChat.dll (Nadeo's "Harbour" framework wrapper, 1.24 MB)
        |
        +-- vivoxsdk.dll (Vivox SDK v5.19.2, 11.87 MB)
```

| String | Address | Purpose |
|--------|---------|---------|
| `voicechatTokenVivox` | `0x141a0dd98` | Config key for Vivox token |
| `voicechatConfigVivox` | `0x141a0ddb0` | Config key for Vivox config |
| `VoicechatClient::createVivoxVoicechatToken` | `0x141a22860` | Token creation |
| `VoicechatClient::getVivoxVoicechatConfig` | `0x141a22890` | Config retrieval |
| `VoiceChat.dll` | `0x141d0d748` | Vivox DLL name |

Voice chat script API classes: `CGameUserVoiceChat`, `CGameVoiceChatConfigScript`, `CGameUserManagerScript_VoiceChatEvent_*` (DisplayUI, Message, SpeakingHasChanged, IsConnected, IsMuted, IsSpeaking), and `CGameNetFormVoiceChat` for in-band voice frames.

### XMPP Text Chat

The game uses XMPP/Jabber for persistent text chat via dedicated servers at `*.chat.maniaplanet.com`.

| Protocol | Address | Purpose |
|----------|---------|---------|
| `http://jabber.org/protocol/muc#user` | `0x141d10f00` | Multi-user chat rooms |
| `jabber:x:conference` | `0x141d10f40` | Conference invitations |
| `jabber:iq:roster` | `0x141d11110` | Contact list management |
| `http://jabber.org/protocol/disco#info` | `0x141d11300` | Service discovery |
| `urn:xmpp:bob` | `0x141d110e8` | Binary data over XMPP |
| `urn:xmpp:ping` | `0x141d11218` | Keepalive ping |

| Server | Address | Purpose |
|--------|---------|---------|
| `squad.chat.maniaplanet.com` | `0x141c444d0` | Squad/party private chat |
| `channel.chat.maniaplanet.com` | `0x141c444f0` | Public channel chat (server-wide) |

---

## Anti-Cheat System

The anti-cheat system uploads replay data to a server-side verification service. The server replays inputs through deterministic physics and validates the result.

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

| Config Key | Address | Purpose |
|-----------|---------|---------|
| `AntiCheatServerUrl` | `0x141c04d68` | Anti-cheat server endpoint URL |
| `AntiCheatReplayChunkSize` | `0x141c2af98` | Upload chunk size |
| `AntiCheatReplayMaxSize` | `0x141c2afe0` | Maximum replay size for upload |
| `AntiCheatReplayMaxSizeOnCheatReport` | `0x141c2afb8` | Enhanced size for cheat reports |
| `UploadAntiCheatReplayOnlyWhenUnblocked` | `0x141c2af78` | Upload gating |
| `UploadAntiCheatReplayForcedOnCheatReport` | `0x141c2b118` | Force upload when cheat detected |

### Leaderboard Submission Flow

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

### Demo Token System

A separate time-limited access system with periodic server-side validation:

| Config Key | Address | Purpose |
|-----------|---------|---------|
| `DemoTokenKickingTimeOut` | `0x141c2b068` | Time before kick for invalid token |
| `DemoTokenCheckingTimeOut` | `0x141c2b080` | Token check timeout |
| `DemoTokenAskingTimeOut` | `0x141c2b0a0` | Token request timeout |
| `DemoTokenTimeBetweenCheck` | `0x141c2b0b8` | Periodic check interval |
| `DemoTokenRetryMax` | `0x141c2b100` | Maximum retries |
| `DemoTokenCost` | `0x141c2c178` | Token cost (Planets currency?) |
| `Invalid demo token` | `0x141c2e2a0` | Error message |

---

## Matchmaking

The matchmaking system integrates with Ubisoft's "Harbour" social platform. It supports at least 2v2 matchmaking with ranked ladder integration.

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

| Config Key | Address | Purpose |
|-----------|---------|---------|
| `profilesPreciseMatchmakingClient` | `0x141a0d168` | Client-side matchmaking profile |
| `profilesPreciseMatchmakingMatch` | `0x141a0d190` | Match-side matchmaking profile |
| `matchmakingGroupsMatchesPrecise` | `0x141a0d1b0` | Group match precision settings |
| `matchmakingSpaceGlobalHarboursocial` | `0x141a0d1d0` | Social matchmaking space |

Confirmed mode: **2v2 matchmaking** (from UI string "Play and compete with your friends on a 2v2 matchmaking game."). The "Precise" variants suggest multiple precision levels for matching.

[UNKNOWN] The exact matchmaking algorithm, ELO/Glicko parameters, queue timeout thresholds, and additional modes.

### Matchmaking Classes

| Class | Purpose |
|-------|---------|
| `CGameLadderRanking` | Base ladder ranking |
| `CGameLadderRankingPlayer` | Player ladder data |
| `CGameLadderRankingSkill` | Skill-based rating |
| `CGameLadderRankingLeague` | League ranking |
| `CGameLadderRankingCtnChallengeAchievement` | Challenge-based ranking |

---

## File Transfer and Ghost Upload

File transfers (maps, skins, replays) use a dedicated subsystem over the TCP channel.

| Class | Address | Purpose |
|-------|---------|---------|
| `CNetFileTransfer` | `0x141d13a68` | Base file transfer |
| `CNetFileTransferDownload` | `0x141d14ec8` | Download handler |
| `CNetFileTransferUpload` | `0x141d1a228` | Upload handler |
| `CNetFileTransferNod` | `0x141d1a680` | Serialized game object transfer |
| `CNetFileTransferForm` | `0x141b7d868` | Wire protocol |

Transfer types: Map files (.Map.Gbx), skin files, replay/ghost files, plugin files, and serialized game objects (Nods).

HTTP-based downloads also exist for content fetched from CDNs:

| Method | Address | Purpose |
|--------|---------|---------|
| `CGameCtnNetwork::DownloadFile` | `0x141c2c940` | Generic HTTP download |
| `CGameCtnNetwork::DownloadOrUpdateFile` | `0x141c2cab8` | Download with version check |
| `CGameCtnNetwork::DownloadOrUpdateTitlePackages` | `0x141c2d220` | Title package updates |
| `CGameCtnNetwork::DownloadManiaNetResource` | `0x141c2d928` | ManiaNet resource download |

### Ghost Upload/Download

| Class | Purpose |
|-------|---------|
| `CGameDataFileTask_GhostDriver_Download` | Download ghost from server |
| `CGameDataFileTask_GhostDriver_Upload` | Upload ghost to server |
| `CGameDataFileTask_GhostDriver_UploadLimits` | Upload rate limits |
| `CGameScoreTask_GetPlayerMapRecordGhost` | Get ghost for leaderboard position |

Ghosts contain: header (map UID, account ID, car type, race time), input sequence at 100Hz, checkpoint times, and cryptographic validation data.

---

## Browser Recreation Architecture

This section maps the native architecture to browser technologies for recreating TM2020's multiplayer in a web browser.

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
```

### Channel Mapping

| Native Channel | Browser Equivalent | Use Case |
|---------------|-------------------|----------|
| TCP (reliable, ordered) | WebSocket | Chat, admin commands, file transfer, reliable state sync |
| UDP (unreliable, fast) | WebRTC DataChannel (unreliable mode) | Player positions, inputs, time-critical sync, voice |

### What Needs Server-Side Proxy

| Component | Needs Proxy? | Reason |
|-----------|-------------|--------|
| Authentication (Ubi/Nadeo) | YES | CORS + credential security |
| Nadeo REST APIs | LIKELY | CORS headers not set for browsers |
| Game server connection | YES | TCP/UDP not available in browsers |
| XMPP chat | LIKELY | No WebSocket endpoint on *.chat.maniaplanet.com |
| Vivox voice | N/A | Replace with WebRTC entirely |
| Ghost upload/download | LIKELY | CORS on upload endpoints |

### Minimum Viable Online Tiers

**Tier 0: Offline with Online Data** -- Play maps offline, load maps/ghosts from Nadeo servers. Requires auth proxy, CORS proxy, GBX parser, physics engine, renderer. Estimated effort: 2-4 weeks.

**Tier 1: Leaderboards and Record Submission** -- Submit times and view leaderboards. Requires ghost recording/serialization, secure attempt flow. Critical challenge: ghost format must match Nadeo's validator. Estimated effort: 4-8 weeks.

**Tier 2: Real-Time Multiplayer (Spectate)** -- Connect to a live server and spectate. Requires WebSocket relay, game protocol parser, player interpolation, timer sync. Critical challenge: CNetForm* wire protocol is [UNKNOWN]. Estimated effort: 8-16 weeks.

**Tier 3: Real-Time Multiplayer (Play)** -- Full participation in races. Requires WebRTC DataChannel, input encoding, full state sync. Estimated effort: 16-32 weeks.

**Tier 4: Full Feature Parity** -- Chat, voice, matchmaking, clubs. Estimated effort: 32-64 weeks.

### REST API Usage

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

**Note**: These calls need a CORS proxy since Nadeo's servers do not set browser-friendly CORS headers.

---

## Web Services Class Taxonomy

The web services layer has 562 classes across three prefixes:

| Prefix | Count | Role |
|--------|-------|------|
| `CNet*` | 262 | Low-level network engine + service tasks |
| `CWebServices*` | 297 | Game-facing facade + result types |
| `CGame*Network*` | 3 | Game-level network management |

### Service Managers (18)

| Manager | Service Domain |
|---------|----------------|
| `CWebServicesUserManager` | User identity and profile |
| `CWebServicesIdentityManager` | Cross-platform identity resolution |
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

<details>
<summary>Complete class taxonomy (562+ classes)</summary>

### CNet* Infrastructure (20)
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

### Wire Protocol Forms (8)
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

### File Transfer (4)
```
CNetFileTransfer                 -- Base
CNetFileTransferDownload         -- Download
CNetFileTransferUpload           -- Upload
CNetFileTransferNod              -- Nod serialization
```

### Master Server (16+)
```
CNetMasterHost, CNetMasterServer, CNetMasterServerDownload, CNetMasterServerInfo,
CNetMasterServerRequest, CNetMasterServerRequestTask, CNetMasterServerUptoDateCheck,
CNetMasterServerUserInfo, CNetMasterServerTask_Connect, CNetMasterServerTask_GetApplicationConfig,
CNetMasterServerTask_GetClientConfigUrls, CNetMasterServerTask_GetWaitingParams,
CNetMasterServerTask_GetFeatureTimeLimit, CNetMasterServerTask_CheckFeatureTimeLimit,
CNetMasterServerTask_SetFeatureTimeUse, CNetMasterServerTask_CheckLoginForSubscribe, ...
```

### UbiServices (32)
```
CNetUbiServices + 30 task subclasses (sessions, profiles, parties, preferences, notifications)
```

### UPlay PC (11)
```
CNetUplayPC + CNetUplayPCUserInfo + 9 task subclasses (achievements, friends, sessions, overlay)
```

### Nadeo Services (175)
```
CNetNadeoServices + CNetNadeoServicesRequest + CNetNadeoServicesRequestManager +
CNetNadeoServicesRequestTask + CNetNadeoServicesUserInfo + 170 task subclasses
```

### CWebServices* Infrastructure (8)
```
CWebServices, CWebServicesTaskScheduler, CWebServicesTask, CWebServicesTaskResult,
CWebServicesTaskSequence, CWebServicesTaskVoid, CWebServicesTaskWait, CWebServicesTaskWaitMultiple
```

### CWebServices* Result Types (~165)

NS (NadeoServices) results: `_NSMap`, `_NSMapList`, `_NSMapRecordList`, `_NSSeason`, `_NSSkin`, `_NSItemCollection*`, `_NSSquad`, `_NSPrestigeList`, `_NSTrophySettings`, `_NSEncryptedPackage*`, `_NSServer`, etc.

WS (WebServices) results: `_WSBlockedUserList`, `_WSFriendInfoList`, `_WSMapPtrList`, `_WSParty*`, `_WSPrestige*`, `_WSZone*`, etc.

UbiServices results: `_UbiServicesBlockList`, `_UbiServicesParty*`, `_UbiServicesProfileConsent`, `_UbiServicesStatList`, etc.

UPC results: `_UPCAchievementCompletionList`, `_UPCConsumableItemList`, `_UPCFriendList`.

Generic results: `Bool`, `Integer`, `Natural`, `String`, `StringInt`, `StringIntList`, `StringList`.

### Game Network Forms (10)
```
CGameNetForm, CGameNetFormPlayground, CGameNetFormPlaygroundSync, CGameNetFormTimeSync,
CGameNetFormCallVote, CGameNetFormAdmin, CGameNetFormTunnel, CGameNetFormBuddy,
CGameNetFormVoiceChat, CGameNetOnlineMessage
```

### Game Network Classes (5)
```
CGameNetPlayerInfo, CGameNetServerInfo, CGameNetFileTransfer, CGameNetDataDownload, CGameNetwork
```

### Inferred Class Hierarchy
```
CMwNod (base engine object)
 +-- CNetNod
 |    +-- CNetConnection
 |    +-- CNetServer
 |    +-- CNetClient
 |    +-- CNetServerInfo
 |    +-- CNetClientInfo
 |    +-- CNetSource
 |    +-- CNetURLSource
 +-- CNetEngine
 |    +-- CNetHttpClient
 |    +-- CNetHttpResult
 +-- CNetMasterServer
 |    +-- CNetMasterServerRequest
 |    +-- CNetMasterServerRequestTask
 |    +-- CNetMasterServerInfo
 +-- CNetUbiServices
 |    +-- CNetUbiServicesTask_* (50+ task types)
 +-- CNetNadeoServices
 |    +-- CNetNadeoServicesRequestManager
 |    +-- CNetNadeoServicesRequest
 |    +-- CNetNadeoServicesRequestTask
 |    +-- CNetNadeoServicesTask_* (100+ task types)
 +-- CNetUplayPC
 |    +-- CNetUplayPCTask_*
 +-- CNetFileTransfer
 |    +-- CNetFileTransferDownload
 |    +-- CNetFileTransferUpload
 |    +-- CNetFileTransferNod
 +-- CNetXmpp
 +-- CNetIPC
 +-- CNetIPSource
 +-- CNetUPnP
 +-- CNetScriptHttpManager
 |    +-- CNetScriptHttpRequest
 |    +-- CNetScriptHttpEvent
```

</details>

---

## Key Unknowns

### Critical (Block Browser Recreation)

1. **[UNKNOWN]** Exact wire protocol format for TCP/UDP game connections (CNetForm* binary layout, header structure, framing) -- the single biggest blocker for real-time multiplayer
2. **[PARTIALLY RESOLVED]** Complete REST API URL structure -- base URLs VERIFIED from Openplanet; specific endpoint paths are SPECULATIVE
3. **[RESOLVED]** Authentication header format -- confirmed as `Authorization: nadeo_v1 t=<token>`
4. **[UNKNOWN]** Ghost binary format details for upload/download -- community tools have partially documented GBX containers, but secure-attempt validation data is unknown

### Important

5. **[UNKNOWN]** Whether QUIC/HTTP3 is actively used
6. **[UNKNOWN]** Anti-cheat server endpoint URL
7. **[UNKNOWN]** CNetIPC target process identity
8. **[UNKNOWN]** Exact matchmaking algorithm parameters
9. **[UNKNOWN]** Whether the game uses peer-to-peer connections or only dedicated servers
10. **[UNKNOWN]** Client prediction and lag compensation specifics

### Partially Known

11. **[PARTIAL]** HTTP request format -- headers known, not all content type variations
12. **[PARTIAL]** State machine state values -- hex values known, semantic meanings mostly unknown
13. **[PARTIAL]** Ghost binary format -- community tools partially document GBX containers

---

## Related Pages

- [01-binary-overview.md](01-binary-overview.md) -- Binary structure and entry points
- [09-game-files-analysis.md](09-game-files-analysis.md) -- DLL analysis including VoiceChat.dll and vivoxsdk.dll
- [10-physics-deep-dive.md](10-physics-deep-dive.md) -- Deterministic physics simulation (100Hz tick rate)
- [15-ghidra-research-findings.md](15-ghidra-research-findings.md) -- Decompiled function analysis
- [19-openplanet-intelligence.md](19-openplanet-intelligence.md) -- Openplanet-sourced API verification
- [20-browser-recreation-guide.md](20-browser-recreation-guide.md) -- Full browser recreation roadmap
- [30-ghost-replay-format.md](30-ghost-replay-format.md) -- Ghost/replay GBX format details

<details>
<summary>Analysis metadata</summary>

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.x via PyGhidra bridge
**Source**: RTTI class extraction, debug string analysis, decompilation
**Note**: Binary is stripped -- all function names are from embedded log/debug strings, not symbols.

### Function Address Reference

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

### Build Environment

Nadeo code path: `C:\Nadeo\CodeBase_tm-retail\Nadeo\Engines\NetEngine\source\NetHttpClient_Curl.cpp`

UbiServices SDK path: `D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\harbourcommon\libraries\_fetch\`

External libraries (static): libcurl, OpenSSL 1.1.1t+quic, xmlrpc-c. Dynamic: Vivox SDK (VoiceChat.dll), UPC SDK (upc_r2_loader64.dll).

### UPC Cloud Streaming APIs

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

</details>

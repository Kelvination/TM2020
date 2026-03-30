# Trackmania.exe Networking & Online Services

**Binary**: `Trackmania.exe` (Trackmania 2020 / Trackmania Nations remake by Nadeo/Ubisoft)
**Date of analysis**: 2026-03-27
**Tools**: Ghidra 12.x via PyGhidra bridge
**Note**: Binary is stripped -- all function names are from embedded log/debug strings, not symbols.

---

## Architecture Overview

The networking subsystem is organized in a layered architecture spanning from low-level socket operations up to game-specific online services. The layers, from bottom to top:

```
+-----------------------------------------------------------------------+
|                    Game Logic / ManiaScript                            |
|   CGameManiaPlanetNetwork, CGameCtnNetwork, CPlaygroundClient         |
+-----------------------------------------------------------------------+
|                    Web Services / Online Services                      |
|   CWebServices*, CNetNadeoServices*, CNetUbiServices*                 |
+-----------------------------------------------------------------------+
|                    Master Server / Legacy                              |
|   CNetMasterServer, CGameMasterServer, CXmlRpc                       |
+-----------------------------------------------------------------------+
|                    Network Engine                                      |
|   CNetEngine, CNetServer, CNetClient, CNetHttpClient                 |
+-----------------------------------------------------------------------+
|                    Transport / Platform                                |
|   WS2_32 (Winsock2), libcurl, OpenSSL 1.1.1t+quic                   |
+-----------------------------------------------------------------------+
|                    External Services                                   |
|   UPC (Ubisoft Connect SDK), Vivox (Voice Chat), XMPP (Chat)        |
+-----------------------------------------------------------------------+
```

---

## Layer 1: Transport Layer

### Winsock2 (WS2_32.DLL)

Only a single ordinal import is visible in the IAT:

| Import | Symbol |
|--------|--------|
| `WS2_32.DLL::Ordinal_1` | Likely `accept` or winsock init |

The minimal import count is due to binary protection/packing. Additional Winsock functions are resolved at runtime via `LoadLibraryA`/`GetProcAddress`.

### libcurl (Statically Linked)

libcurl is statically compiled into the binary and used as the HTTP client backend. Key evidence:

| String | Address | Significance |
|--------|---------|--------------|
| `"[Net] HTTP: curl_version="` | `0x141b7b298` | Version logging at init |
| `"CurlPerform"` | `0x141b7b530` | Profiling marker |
| `"Failed in call to curl_multi_init"` | `0x141b7b578` | Multi-handle creation |
| `"Failed in call to curl_easy_init"` | `0x141b7b748` | Easy-handle creation |
| `"Failed in call to curl_multi_add_handle, Error: "` | `0x141b7b7f8` | Request submission |
| `"Failed in call to curl_multi_remove_handle, Error: "` | `0x141b7b898` | Request cleanup |
| `"Failed in curl_multi_info_read, URL: "` | `0x141b7b9d8` | Response processing |
| `"# Netscape HTTP Cookie File\n# https://curl.se/..."` | `0x1419fdef0` | Cookie persistence |
| `"# Your alt-svc cache. https://curl.se/..."` | `0x1419ff230` | Alt-Svc caching |

**Source file path** (leaked from debug strings):
`C:\Nadeo\CodeBase_tm-retail\Nadeo\Engines\NetEngine\source\NetHttpClient_Curl.cpp`

The HTTP client uses curl's multi interface (asynchronous/non-blocking I/O).

**Curl request wrapper** (from `HttpRequestCurl` class in the UbiServices SDK):

| String | Address |
|--------|---------|
| `"HttpRequestCurl::stepWaitForResume"` | `0x141a24f20` |
| `"HttpRequestCurl::stepWaitStatusCode"` | `0x141a24f48` |
| `"HttpRequestCurl::stepWaitForComplete"` | `0x141a24f90` |

The UbiServices SDK also uses curl internally, with its own build path:
`D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\dependencies\_fetch\curl\lib\vtls\openssl.c`

### OpenSSL (Statically Linked)

OpenSSL is statically compiled, version identified from string:

| String | Address |
|--------|---------|
| `"OpenSSL 1.1.1t+quic  7 Feb 2023"` | `0x141983c80` |

The `+quic` variant indicates QUIC protocol support is compiled in (via the quictls fork). This is notable as it means the binary has the capability for QUIC/HTTP3, though whether it is actively used is [UNKNOWN].

OpenSSL source paths are from the UbiServices SDK dependency tree:
`D:\CodeBase_Ext\externallibs\ubiservices\ubiservices\external\harbourcommon\libraries\_fetch\openssl\crypto\...`

---

## Layer 2: Network Engine (CNet*)

The core networking engine is built on the ManiaPlanet engine's `CNet*` class hierarchy. This layer handles TCP/UDP connections, packet framing, and connection management.

### CNetEngine

| String | Address | Notes |
|--------|---------|-------|
| `"CNetEngine::UpdateHttpClients"` | `0x141b7caa8` | HTTP client tick |
| `"NetEngine(server): successfully connected from '%s' (IP = %s)"` | `0x141b7bfc0` | Server accept log |
| `"NetEngine (client): successfully connected to '%s' (IP = %s)"` | `0x141d15648` | Client connect log |
| `"[Net] CNetSystem::Init() failed !"` | `0x141b7d4b0` | Init failure |
| `"[Net] CNetHttpClient::PlatformInit() failed !"` | `0x141b7d4d8` | HTTP init failure |

### CNetServer

| String | Address | Notes |
|--------|---------|-------|
| `"CNetServer"` | `0x141b7ba98` | Class name |
| `"CNetServer::CheckDisconnections"` | `0x141b7bc20` | Disconnect polling |
| `"CNetServer::DoReception"` | `0x141b7bc88` | Receive loop (at `FUN_1403089f0`) |
| `"CNetServer::TickReception"` | `0x141b7bca0` | Per-tick receive |
| `"CNetServer::DoSending"` | `0x141b7bd40` | Send loop |
| `"CNetServer::UpdateTransfertSizeCmd"` | `0x141b7c000` | Transfer metrics |

### CNetClient

| String | Address | Notes |
|--------|---------|-------|
| `"CNetClient"` | `0x141d15420` | Class name |
| `"CNetClient::DoReception"` | `0x141d15470` | Receive loop (at `FUN_1414a1c80`) |
| `"CNetClient::DoSending"` | `0x141d15488` | Send loop |
| `"CNetClient::TickReception"` | `0x141d154c8` | Per-tick receive |
| `"CNetClient::InitNetwork"` | `0x141d155a8` | Network initialization |
| `"CNetClient::CNetClient"` | `0x141d155c0` | Constructor |
| `"CNetClient::UpdateTransfertSizeCmd"` | `0x141d15620` | Transfer metrics |

### CNetConnection

| String | Address | Notes |
|--------|---------|-------|
| `"CNetConnection"` | `0x141b7aeb0` | Class name |
| `"TCPPort"` | `0x141b7aec0` | TCP port field |
| `"UDPPort"` | `0x141b7aed8` | UDP port field |
| `"ConnectionTCP"` | `0x141b7aee0` | TCP connection object |
| `"TestingUDP"` | `0x141b7af38` | UDP connectivity test flag |
| `"CanSendTCP"` / `"CanReceiveTCP"` | `0x141b7af48/58` | TCP capability flags |
| `"CanSendUDP"` / `"CanReceiveUDP"` | `0x141b7af68/78` | UDP capability flags |
| `"TCPEmissionQueue"` | `0x141b7afa0` | TCP outgoing queue |
| `"IsTCPSaturated"` | `0x141b7afd0` | TCP backpressure flag |
| `"WasUDPPacketDropped"` | `0x141b7af88` | UDP packet loss detection |
| `"LatestUDPActivity"` | `0x141b7aff8` | UDP keepalive timestamp |
| `"LocalTCPPort"` / `"RemoteTCPPort"` | `0x141b7ce08/18` | Port fields |
| `"LocalUDPPort"` / `"RemoteUDPPort"` | `0x141b7cde0/28` | Port fields |

### Protocol: TCP + UDP Dual-Stack

The game uses **both TCP and UDP simultaneously** per connection:

- **TCP**: Reliable ordered channel for game state, chat, admin commands, file transfers
- **UDP**: Unreliable channel for time-critical data (player positions, inputs)

Evidence for dual-stack:

| String | Address |
|--------|---------|
| `"TCP initialization failed."` | `0x141b7bbe8` |
| `"UDP initialization failed."` | `0x141b7bbc8` |
| `"Could not establish UDP connection."` | `0x141b7be68` |
| `"Error for connection from %s : Could not establish UDP connection"` | `0x141b7bdd0` |
| `"UDP connection lost."` | `0x141b7bed0` |
| `"TotalTcpUdpReceivingSize"` | `0x141c37d78` |

Data rate metrics exist for both:

| Metric | TCP Address | UDP Address |
|--------|------------|-------------|
| Sending data rate | `0x141b7bb68` | `0x141b7bb50` |
| Receiving data rate | `0x141b7bb80` | `0x141b7bbb0` |
| Sending packet total | `0x141b7b088` | `0x141b7b040` |
| Reception packet total | `0x141b7b010` | `0x141b7b028` |
| Sending nod total | `0x141b7b110` | `0x141b7b0d0` |
| Reception nod total | `0x141b7b0a0` | `0x141b7b0b8` |

The "Nod" totals refer to serialized game objects (ManiaPlanet engine calls its base object "Nod"/"CMwNod").

### CNetHttpClient

The HTTP client layer wraps libcurl for REST API communication.

| String | Address | Notes |
|--------|---------|-------|
| `"CNetHttpClient"` | `0x141b7c610` | Class name |
| `"CNetHttpClient::InternalConnect"` | `0x141b7b5a0` | At `FUN_1403050a0` |
| `"CNetHttpClient::InternalDisconnect"` | `0x141b7b6d0` | Disconnect |
| `"CNetHttpClient::InternalCreateRequest_Initiate"` | `0x141b7b700` | Request init |
| `"CNetHttpClient::InternalCreateRequest_AddOrReplaceHeader"` | `0x141b7b790` | Header manipulation |
| `"CNetHttpClient::InternalCreateRequest_Launch"` | `0x141b7b830` | Submit request |
| `"CNetHttpClient::InternalTerminateReq"` | `0x141b7b8d0` | Request cleanup |
| `"CNetHttpClient::PlatformUpdate"` | `0x141b7b9a0` | Platform tick |
| `"CNetHttpClient::CreateRequest"` | `0x141b7c950` | At `FUN_14030c3f0` |
| `"CNetHttpClient::TerminateReq"` | `0x141b7c688` | High-level terminate |
| `"CNetHttpClient::UpdateTransfertSizeCmd"` | `0x141b7c748` | Transfer size tracking |

**Decompiled `CNetHttpClient::CreateRequest`** (at `0x14030c3f0`):
- Allocates a 0x1a8-byte request structure
- Constructs URL: if path starts with `/`, uses as-is; otherwise prepends a base URL prefix
- Sets headers based on request type:
  - GET (param_3 == 1): `Accept-Encoding: gzip,deflate`
  - POST/PUT with body: `Content-Type: application/binary`
  - Partial requests: `Range: bytes=N-M`
  - Timezone header (when enabled)
- Submits to curl multi handle

See: `/decompiled/networking/CNetHttpClient_CreateRequest.c`

### CNetHttpResult

| String | Address |
|--------|---------|
| `"CNetHttpResult"` | `0x141b7d218` |

[UNKNOWN] Internal structure of HTTP result objects.

### Network Message Forms (CNetForm*)

The engine uses a "form" system for typed network messages:

| Form Class | Address | Purpose |
|------------|---------|---------|
| `"CNetFormConnectionAdmin"` | `0x141b7ce38` | Connection management |
| `"CNetFormEnumSessions"` | `0x141b7d090` | Session enumeration |
| `"CNetFormQuerrySessions"` | `0x141b7dc08` | Session queries (note: typo "Querry" in original) |
| `"CNetFormTimed"` | `0x141b7d1c8` | Timestamped messages |
| `"CNetFormPing"` | `0x141b7d1d8` | Ping/latency |
| `"CNetFormNewPing"` | `0x141b7d1e8` | Updated ping protocol |
| `"CNetFormRpcCall"` | `0x141b7d1f8` | RPC invocations |
| `"CNetFileTransferForm"` | `0x141b7d868` | File transfer protocol |

### Game-Level Network Forms (CGameNetForm*)

| Form Class | Address | Purpose |
|------------|---------|---------|
| `"CGameNetForm"` | `0x141c615c0` | Base game form |
| `"CGameNetFormPlayground"` | `0x141c61960` | Gameplay synchronization |
| `"CGameNetFormPlaygroundSync"` | `0x141c3cb08` | Playground state sync |
| `"CGameNetFormTimeSync"` | `0x141c61488` | Game timer synchronization |
| `"CGameNetFormCallVote"` | `0x141c5e1a8` | Vote system |
| `"CGameNetFormAdmin"` | `0x141c61330` | Server admin commands |
| `"CGameNetFormTunnel"` | `0x141c616f0` | Tunneled data |
| `"CGameNetFormBuddy"` | `0x141c61828` | Friend/buddy system |
| `"CGameNetFormVoiceChat"` | `0x141c61a98` | Voice chat frames |

---

## Layer 3: File Transfer System (CNetFileTransfer*)

File transfers (maps, skins, replays) use a dedicated subsystem:

| String | Address | Notes |
|--------|---------|-------|
| `"CNetFileTransfer"` | `0x141d13a68` | Base class |
| `"CNetFileTransfer::UpdateTransfertSizeCmd"` | `0x141d14ad0` | Transfer progress |
| `"CNetFileTransferDownload"` | `0x141d14ec8` | Download handler |
| `"CNetFileTransferUpload"` | `0x141d1a228` | Upload handler |
| `"CNetFileTransferNod"` | `0x141d1a680` | Serialized object transfer |
| `"CNetFileTransferForm"` | `0x141b7d868` | Wire protocol form |

The file transfer system supports both upload and download of game objects ("Nods") and raw files. Transfers use the TCP channel for reliability.

---

## Layer 4: Master Server (CNetMasterServer)

The legacy ManiaPlanet master server system handles authentication, session management, and server browsing:

### CNetMasterServer

| String | Address | Notes |
|--------|---------|-------|
| `"CNetMasterServer"` | `0x141d11b90` | Class name |
| `"CNetMasterServer::Terminate"` | `0x141d11c18` | Shutdown |
| `"CNetMasterServer::UpdateMasterServerRequests"` | `0x141d11cf8` | Request pump |
| `"CNetMasterServerRequest"` | `0x141d151a0` | Request base class |
| `"CNetMasterServerRequestTask"` | `0x141d174c0` | Async task wrapper |
| `"CNetMasterServerInfo"` | `0x141d18f88` | Server info structure |
| `"CNetMasterServerDownload"` | `0x141d159b8` | File downloads |
| `"CNetMasterServerUptoDateCheck"` | `0x141d15b30` | Version checking |

### Master Server Tasks

| Task | Address | Purpose |
|------|---------|---------|
| `"CNetMasterServerTask_Connect"` | `0x141d17768` | Initial connection |
| `"CNetMasterServerTask_GetApplicationConfig"` | `0x141d190a8` | App config retrieval |
| `"CNetMasterServerTask_GetClientConfigUrls"` | `0x141d19258` | Config URL list |
| `"CNetMasterServerTask_GetWaitingParams"` | `0x141d192a0` | Queue parameters |
| `"CNetMasterServerTask_CheckLoginForSubscribe"` | `0x141d19420` | Login validation |
| `"CNetMasterServerTask_Subscribe"` | `0x141d19450` | Account creation |
| `"CNetMasterServerTask_ImportAccount"` | `0x141d19488` | Account import |
| `"CNetMasterServerTask_OpenSession"` | `0x141d197c0` | Session creation |
| `"CNetMasterServerTask_Session_Get"` | `0x141d19960` | Session query |
| `"CNetMasterServerTask_Session_JoinOrCreate"` | `0x141d19aa8` | Session join/create |
| `"CNetMasterServerTask_Session_Leave"` | `0x141d19c78` | Session departure |
| `"CNetMasterServerTask_Session_InviteBuddy"` | `0x141d19dc0` | Friend invitation |
| `"CNetMasterServerTask_GetFeatureTimeLimit"` | `0x141d19df0` | Feature time gates |
| `"CNetMasterServerTask_CheckFeatureTimeLimit"` | `0x141d19e38` | Feature access check |
| `"CNetMasterServerTask_SetFeatureTimeUse"` | `0x141d19fc8` | Feature usage logging |

### CGameMasterServer

Higher-level game master server interface:

| String | Address | Purpose |
|--------|---------|---------|
| `"CGameMasterServer"` | `0x141c41fe0` | Class name |
| `"CGameMasterServer::GetMSConnectionAndGameParams"` | `0x141c54180` | Connection params |
| `"CGameMasterServerTask_Connect"` | `0x141cad710` | Game-level connect |
| `"CGameMasterServerTask_GetOnlineProfile"` | `0x141cad8c0` | Profile retrieval |
| `"CGameMasterServerTask_GetAuthenticationToken"` | `0x141cadc38` | Auth token request |
| `"CGameMasterServerTask_GetTitlePackagesInfos"` | `0x141cadc68` | Title/DLC info |
| `"CGameMasterServerTask_GetAccountFromUplayUser"` | `0x141cae4c0` | UPlay account mapping |
| `"CGameMasterServerTask_SetBuddies"` | `0x141ca5df0` | Friends list sync |
| `"CGameMasterServerTask_UpdateOnlineProfile"` | `0x141cadac0` | Profile update |
| `"CGameMasterServerTask_GetSubscribedGroups"` | `0x141cad878` | Group membership |

---

## Layer 5: XML-RPC Protocol

The engine includes a full XML-RPC implementation (inherited from ManiaPlanet) for server scripting and remote control:

### xmlrpc-c Library (Statically Linked)

| String | Address | Notes |
|--------|---------|-------|
| `"New XmlRpc request : \n"` | `0x141b6ff10` | Request logging |
| `"XmlRpc request failed : \n"` | `0x141b6ff28` | Error logging |
| `"XmlRpc request succeeded : \n"` | `0x141b6ff68` | Success logging |
| `"Xmlrpc-c global client instance has already been created..."` | `0x141b70f50` | Singleton guard |
| `"Xmlrpc-c global client instance has not been created..."` | `0x141b70fd0` | Init check |

### XML-RPC Classes

| Class | Address | Purpose |
|-------|---------|---------|
| `"CXmlRpc"` | `0x141bfaf58` | Core XML-RPC handler |
| `"CXmlRpcEvent"` | `0x141bfaf60` | RPC event |
| `"CGameServerScriptXmlRpc"` | `0x141bf91e0` | Server-side script RPC |
| `"CGameServerScriptXmlRpcEvent"` | `0x141bf9188` | Server RPC event |

### XML-RPC Callbacks (ManiaPlanet Protocol)

The standard ManiaPlanet server XML-RPC callbacks are present:

| Callback | Address |
|----------|---------|
| `"ManiaPlanet.ServerStart"` | `0x141d045f8` |
| `"ManiaPlanet.ServerStop"` | `0x141d04568` |
| `"ManiaPlanet.PlayerConnect"` | `0x141d044a8` |
| `"ManiaPlanet.PlayerDisconnect"` | `0x141d044e8` |
| `"ManiaPlanet.PlayerChat"` | `0x141d04690` |
| `"ManiaPlanet.PlayerInfoChanged"` | `0x141d04808` |
| `"ManiaPlanet.BeginMap"` | `0x141d04778` |
| `"ManiaPlanet.EndMap"` | `0x141d04730` |
| `"ManiaPlanet.BeginMatch"` | `0x141d04588` |
| `"ManiaPlanet.EndMatch"` | `0x141d04790` |
| `"ManiaPlanet.BeginRound"` | `0x141d04760` |
| `"ManiaPlanet.EndRound"` | `0x141d046c8` |
| `"ManiaPlanet.StatusChanged"` | `0x141d046f8` |
| `"ManiaPlanet.Echo"` | `0x141d04610` |
| `"ManiaPlanet.BillUpdated"` | `0x141d047f0` |
| `"ManiaPlanet.VoteUpdated"` | `0x141d048b0` |
| `"ManiaPlanet.PlayerAlliesChanged"` | `0x141d048d0` |
| `"ManiaPlanet.MapListModified"` | `0x141d048f0` |
| `"ManiaPlanet.TunnelDataReceived"` | `0x141d04938` |
| `"ManiaPlanet.ModeScriptCallback"` | `0x141d049a0` |
| `"ManiaPlanet.ModeScriptCallbackArray"` | `0x141d04978` |
| `"ManiaPlanet.PlayerManialinkPageAnswer"` | `0x141d045b8` |

These callbacks allow external tools (server controllers) to interact with the game server via XML-RPC. This is the same protocol used by TMNF/TM2 server controllers.

---

## Layer 6: Ubisoft Connect / UPC Integration

### UPC SDK (upc_r2_loader64.dll)

The game integrates with Ubisoft Connect through the UPC (Ubisoft Platform Client) SDK, loaded from `upc_r2_loader64.dll` at `0x14285ab28`.

**Direct import**: `UPC_TicketGet` (visible in IAT at `0x1428c80d2`)

**Dynamically resolved UPC functions** (from string references):

| UPC Function | Address | Purpose |
|-------------|---------|---------|
| `"UPC_ContextCreate"` | `0x141a12950` | Create UPC context |
| `"UPC_ContextFree"` | `0x141a12968` | Destroy UPC context |
| `"UPC_Update"` | `0x141a12978` | Per-frame tick |
| `"UPC_Cancel"` | `0x141a12988` | Cancel async op |
| `"UPC_ErrorToString"` | `0x141a12998` | Error messages |
| `"UPC_EventRegisterHandler"` | `0x141a129b0` | Event callbacks |
| `"UPC_StoreProductListGet"` | `0x141a129d0` | Store product listing |
| `"UPC_StoreProductListFree"` | `0x141a129e8` | Free product list |
| `"UPC_ProductListGet"` | `0x141a12a08` | Owned products |
| `"UPC_ProductListFree"` | `0x141a12a20` | Free product list |

**Cloud Streaming Support (UPC_Streaming* API)**:

| Function | Address |
|----------|---------|
| `"UPC_StreamingCurrentUserCountryGet"` | `0x141a12a38` |
| `"UPC_StreamingDeviceTypeGet"` | `0x141a12a88` |
| `"UPC_StreamingInputGamepadTypeGet"` | `0x141a12aa8` |
| `"UPC_StreamingInputTypeGet"` | `0x141a12ad0` |
| `"UPC_StreamingNetworkDelayForInputGet"` | `0x141a12af0` |
| `"UPC_StreamingNetworkDelayForVideoGet"` | `0x141a12b18` |
| `"UPC_StreamingNetworkDelayRoundtripGet"` | `0x141a12b40` |
| `"UPC_StreamingResolutionGet"` | `0x141a12b68` |
| `"UPC_StreamingTypeGet"` | `0x141a12ba8` |

This shows the game has explicit support for Ubisoft's cloud gaming/streaming service, with APIs to query input latency, video latency, resolution, and device type.

### CNetUplayPC

| String | Address | Notes |
|--------|---------|-------|
| `"CNetUplayPC"` | `0x141b80f70` | UPlay PC wrapper class |
| `"CNetUplayPC::Terminate"` | `0x141b80f48` | Shutdown |
| `"CNetUplayPCUserInfo"` | `0x141b84c18` | User info structure |

### CNetUplayPC Tasks

| Task | Address | Purpose |
|------|---------|---------|
| `"CNetUplayPCTask_Achievement_GetCompletionList"` | `0x141b84d48` | Achievement queries |
| `"CNetUplayPCTask_Achievement_Unlock"` | `0x141b84ea0` | Achievement unlocking |
| `"CNetUplayPCTask_GetUserConsumableItemList"` | `0x141b84fe8` | Consumable items |
| `"CNetUplayPCTask_GetFriendList"` | `0x141b85138` | Friends list |
| `"CNetUplayPCTask_ShowBrowserUrl"` | `0x141b85278` | Open URL in overlay |
| `"CNetUplayPCTask_Overlay_ShowMicroApp"` | `0x141b853b8` | Overlay micro-apps |
| `"CNetUplayPCTask_JoinSession"` | `0x141b85520` | Join game session |
| `"CNetUplayPCTask_LeaveSession"` | `0x141b85660` | Leave game session |
| `"CNetUplayPCTask_ShowInviteUI"` | `0x141b857a0` | Invitation UI |

### UPC Event Handling

| Event String | Address |
|-------------|---------|
| `"UPC_Event_ProductAdded notification received. ProductId:%d Balance:%d"` | `0x141a1e9b0` |
| `"UPC_Event_ProductBalanceUpdated notification received. ProductId:%d New Balance:%d"` | `0x141a1ea00` |
| `"UPC_Event_ProductOwnershipUpdated notification received. ProductId:%d New Ownership:%d"` | `0x141a1ea60` |
| `"UPC_Event_ProductStateUpdated notification received. ProductId:%d New State:%d"` | `0x141a1eac0` |

---

## Layer 7: Ubisoft Services (CNetUbiServices)

The UbiServices SDK is a higher-level service layer that wraps Ubisoft's backend APIs.

### CNetUbiServices

| String | Address | Notes |
|--------|---------|-------|
| `"CNetUbiServices"` | `0x141b7d880` | Class name |
| `"CNetUbiServices::Terminate"` | `0x141b7d9d8` | Shutdown |

### UbiServices API Endpoints

| URL | Address | Purpose |
|-----|---------|---------|
| `"https://{env}public-ubiservices.ubi.com/{version}"` | `0x141a1c5b0` | Main Ubisoft services API (templated) |
| `"https://public-ubiservices.ubisoft.cn/{version}"` | `0x141a1c5e8` | China GAAP-compliant endpoint |
| `"https://gaap.ubiservices.ubi.com:12000/{version}"` | `0x141a1c628` | GAAP services (port 12000) |

The `{env}` and `{version}` placeholders are templated at runtime, allowing environment switching (prod/staging/dev).

### UbiServices Tasks

**Session Management:**

| Task | Address |
|------|---------|
| `"CNetUbiServicesTask_CreateSession"` | `0x141b7df80` |
| `"CNetUbiServicesTask_RefreshSession"` | `0x141b7e4d8` |
| `"CNetUbiServicesTask_DeleteSession"` | `0x141b7e620` |

**Profile & Social:**

| Task | Address |
|------|---------|
| `"CNetUbiServicesTask_Profile_RetrieveProfileInfoList"` | `0x141b7eb50` |
| `"CNetUbiServicesTask_Profile_RetrieveUplayProfileInfoList"` | `0x141b7efc0` |
| `"CNetUbiServicesTask_Blocklist_Get"` | `0x141b7f120` |
| `"CNetUbiServicesTask_GetFriendList"` | `0x141b7f2a0` |
| `"CNetUbiServicesTask_GetNews"` | `0x141b7f2e0` |

**Party System (Ubisoft-level):**

| Task | Address |
|------|---------|
| `"CNetUbiServicesTask_Party_CreateParty"` | `0x141b7f610` |
| `"CNetUbiServicesTask_Party_GetPartyInfo"` | `0x141b7f900` |
| `"CNetUbiServicesTask_Party_GetPartyInvitationList"` | `0x141b7fa68` |
| `"CNetUbiServicesTask_Party_GetPartyMemberList"` | `0x141b7fec8` |
| `"CNetUbiServicesTask_Party_LeaveParty"` | `0x141b7fec8` |
| `"CNetUbiServicesTask_Party_SetMaxMemberLimit"` | `0x141b80178` |
| `"CNetUbiServicesTask_Party_UpdateLockState"` | `0x141b80440` |
| `"CNetUbiServicesTask_Party_AutoRemovePartyMemberOnDisconnect"` | `0x141b7f440` |

**Player Preferences & Consent:**

| Task | Address |
|------|---------|
| `"CNetUbiServicesTask_PlayerConsents_GetConsent"` | `0x141b805c8` |
| `"CNetUbiServicesTask_PlayerConsents_GetAcceptanceList"` | `0x141b80738` |
| `"CNetUbiServicesTask_PlayerPreferences_GetStandardPreferences"` | `0x141b808e8` |
| `"CNetUbiServicesTask_PlayerPreferences_SetStandardPreferences"` | `0x141b80a68` |
| `"CNetUbiServicesTask_RequestUserLegalOptinsStatus"` | `0x141b7e768` |

**Notifications & Stats:**

| Task | Address |
|------|---------|
| `"CNetUbiServicesTask_CheckNewNotification"` | `0x141b821a8` |
| `"CNetUbiServicesTask_SendNotification"` | `0x141b82358` |
| `"CNetUbiServicesTask_GetStatList"` | `0x141b80bd0` |
| `"CNetUbiServicesTask_GetUnsentEvents"` | `0x141b7e980` |

---

## Layer 8: Nadeo Services (CNetNadeoServices)

Nadeo Services is the game-specific backend API layer, built on top of UbiServices.

### CNetNadeoServices

| String | Address | Notes |
|--------|---------|-------|
| `"CNetNadeoServices"` | `0x141b81180` | Class name |
| `"CNetNadeoServices::Terminate"` | `0x141b814f8` | Shutdown |
| `"CNetNadeoServicesRequestManager"` | `0x141b85878` | Request manager |
| `"CNetNadeoServicesUserInfo"` | `0x141b859a8` | User info |
| `"CNetNadeoServicesRequest"` | `0x141b9e270` | Request base |
| `"CNetNadeoServicesRequestTask"` | `0x141b9e4f8` | Async task |

### API Domains

| Domain | Address | Purpose |
|--------|---------|---------|
| `".nadeo.live"` | `0x141b7c6e0` | Nadeo Live services (main API) |
| `"core.trackmania.nadeo.live"` | `0x141b85858` | Core TM API (authentication, maps, records) |
| `".nadeo.club"` | `0x141b7c718` | Club/community services |
| `".maniaplanet.com"` | `0x141b7c700` | Legacy ManiaPlanet services |
| `"http://test.nadeo.com"` | `0x141b964c8` | Test environment |
| `"http://test2.nadeo.com"` | `0x141b96510` | Test environment 2 |

### Authentication Flow

The authentication system uses a multi-step token exchange:

1. **Ubisoft Connect login** --> UPC_TicketGet produces a UPlay ticket
2. **UbiServices session** --> `CNetUbiServicesTask_CreateSession` creates a Ubisoft session
3. **Nadeo token exchange** --> `nadeoservices_token_create_from_ubiservices_v2` exchanges the UbiServices session for a Nadeo access token
4. **Token refresh** --> `nadeoservices_token_refresh_v2` refreshes expired tokens

Token API endpoints:

| API Request Name | Address | Purpose |
|-----------------|---------|---------|
| `"nadeoservices_token_create_from_basic_v2"` | `0x141b85ad8` | Basic credentials auth (debug/dev?) |
| `"nadeoservices_token_create_from_ubiservices_v2"` | `0x141b85ce8` | Production auth via UbiServices |
| `"nadeoservices_token_create_from_nadeoservices_v2"` | `0x141b862a0` | Token-to-token exchange |
| `"nadeoservices_token_refresh_v2"` | `0x141b85ef0` | Token refresh |

Token fields:

| Field | Address |
|-------|---------|
| `"refreshToken"` | `0x141b85f50` |
| `"accessToken"` | `0x141b85f60` |

Authentication task classes:

| Task | Address |
|------|---------|
| `"CNetNadeoServicesTask_AuthenticateWithBasicCredentials"` | `0x141b85b08` |
| `"CNetNadeoServicesTask_AuthenticateWithUbiServices"` | `0x141b85d18` |
| `"CNetNadeoServicesTask_AuthenticateWithUnsecureAccountId"` | `0x141b85eb8` |
| `"CNetNadeoServicesTask_AuthenticateCommon"` | `0x141b9e6a0` |
| `"CNetNadeoServicesTask_RefreshNadeoServicesAuthenticationToken"` | `0x141b85f10` |
| `"CNetNadeoServicesTask_GetAuthenticationToken"` | `0x141b862d8` |

### Nadeo Services API Calls (Comprehensive)

The following API categories were identified:

**Maps:**
- `CNetNadeoServicesTask_GetMap`, `_GetMapList`, `_GetAccountMapList`, `_SetMap`
- `CNetNadeoServicesTask_GetMapVote`, `_VoteMap`
- `CNetNadeoServicesTask_AddAccountMapFavorite`, `_GetAccountMapFavoriteList`, `_RemoveAccountMapFavorite`
- `CNetNadeoServicesTask_GetAccountMapZen`, `_IncrAccountMapZen`

**Map Records (Leaderboards):**
- `CNetNadeoServicesTask_CreateMapRecordSecureAttempt`
- `CNetNadeoServicesTask_GetAccountMapRecordList`
- `CNetNadeoServicesTask_GetMapRecordList`
- `CNetNadeoServicesTask_PatchMapRecordSecureAttempt`
- `CNetNadeoServicesTask_SetMapRecordAttempt`

**Campaigns/Seasons:**
- `CNetNadeoServicesTask_GetCampaignList`, `_SetCampaign`, `_AddMapListToCampaign`, `_RemoveMapListFromCampaign`
- `CNetNadeoServicesTask_GetSeason`, `_GetSeasonList`, `_GetAccountSeasonList`, `_GetAccountPlayableSeasonList`
- `CNetNadeoServicesTask_AddMapListToSeason`, `_RemoveMapListFromSeason`, `_SetSeason`

**Item Collections (Custom Items):**
- `CNetNadeoServicesTask_GetItemCollection`, `_GetItemCollectionList`
- `CNetNadeoServicesTask_CreateItemCollectionVersion`, `_GetItemCollectionVersion`
- `CNetNadeoServicesTask_AddAccountItemCollectionFavorite`, `_RemoveAccountItemCollectionFavorite`
- `CNetNadeoServicesTask_SetItemCollection`, `_SetItemCollectionActivityId`

**Skins:**
- `CNetNadeoServicesTask_CreateSkin`, `_GetSkin`, `_GetSkinList`
- `CNetNadeoServicesTask_GetAccountSkinList`, `_SetAccountSkin`, `_UnsetAccountSkin`
- `CNetNadeoServicesTask_AddAccountSkinFavorite`, `_RemoveAccountSkinFavorite`

**Clubs:**
- `CNetNadeoServicesTask_GetClub`, `_GetClubList`
- `CNetNadeoServicesTask_GetAccountClubTag`, `_GetAccountClubTagList`, `_SetAccountClubTag`

**Trophies:**
- `CNetNadeoServicesTask_GetAccountTrophyGainHistory`
- `CNetNadeoServicesTask_GetAccountTrophyLastYearSummary`
- `CNetNadeoServicesTask_GetTrophySettings`
- `CNetNadeoServicesTask_SetTrophyCompetitionMatchAchievementResult`
- `CNetNadeoServicesTask_SetTrophyLiveTimeAttackAchievementResult`

**Prestige:**
- `CNetNadeoServicesTask_GetAllPrestigeList`, `_GetPrestigeList`
- `CNetNadeoServicesTask_GetAccountPrestigeCurrent`, `_GetAccountPrestigeList`
- `CNetNadeoServicesTask_SetAccountPrestigeCurrent`, `_UnsetAccountPrestigeCurrent`

**Squads (Party System):**
- `CNetNadeoServicesTask_CreateSquad`
- `CNetNadeoServicesTask_AddSquadInvitation`, `_AcceptSquadInvitation`, `_DeclineSquadInvitation`
- `CNetNadeoServicesTask_GetAccountSquad`, `_GetSquad`
- `CNetNadeoServicesTask_LeaveSquad`, `_RemoveSquadMember`, `_RemoveSquadInvitation`
- `CNetNadeoServicesTask_SetSquadLeader`

**Accounts & Zones:**
- `CNetNadeoServicesTask_GetAccountZone`, `_GetAccountZoneList`, `_SetAccountZone`, `_GetZones`
- `CNetNadeoServicesTask_GetAccountXp`
- `CNetNadeoServicesTask_GetWebServicesIdentityFromAccountId`
- `CNetNadeoServicesTask_GetAccountIdFromWebServicesIdentity`
- `CNetNadeoServicesTask_GetAccountDisplayNameList`

**Subscriptions:**
- `CNetNadeoServicesTask_AddSubscription`, `_AddSubscriptionFromPSN`
- `CNetNadeoServicesTask_GetAccountSubscriptionList`

**Encrypted Packages (DRM):**
- `CNetNadeoServicesTask_CreateEncryptedPackageVersion`
- `CNetNadeoServicesTask_GetEncryptedPackageAccountKey`
- `CNetNadeoServicesTask_GetEncryptedPackageList`
- `CNetNadeoServicesTask_GetEncryptedPackageVersionCryptKey`
- `CNetNadeoServicesTask_SetEncryptedPackage`

**Uploads:**
- `CNetNadeoServicesTask_Upload`, `_UploadPart`, `_CreateUpload`, `_GetUpload`

**Servers:**
- `CNetNadeoServicesTask_DeleteServer`, `_GetServer`, `_SetServer`

**Activity/Match Reporting:**
- `CNetNadeoServicesTask_Activity_CreateMatch`
- `CNetNadeoServicesTask_Activity_ReportMatchResult`
- `CNetNadeoServicesTask_Activity_UpdateMatch`

**Client/Config:**
- `CNetNadeoServicesTask_GetClientConfig`
- `CNetNadeoServicesTask_GetClientFileList`
- `CNetNadeoServicesTask_SetClientCaps`
- `CNetNadeoServicesTask_GetClientUpdaterFile`
- `CNetNadeoServicesTask_AddClientLog`, `_AddClientDebugInfo`

**Telemetry:**
- `CNetNadeoServicesTask_AddTelemetryMapSession`

**Waiting Queue:**
- `CNetNadeoServicesTask_AddToWaitingQueue`

**Driver Bots:**
- `CNetNadeoServicesTask_AddDriverBotGroupList`, `_GetDriverBotGroupList`

**Policy:**
- `CNetNadeoServicesTask_GetAccountPolicyRuleValueList`

**Presence:**
- `CNetNadeoServicesTask_DeleteAccountPresence`, `_SetAccountPresence`

**Notifications:**
- `CNetNadeoServicesTask_GetVisualNotificationUrlInfo`

**Profile Chunks:**
- `CNetNadeoServicesTask_DeleteProfileChunk`, `_GetProfileChunkList`, `_SetProfileChunk`

---

## Layer 9: Web Services (CWebServices)

The `CWebServices` layer is the game-facing facade over all online services (UbiServices + NadeoServices).

### Core Architecture

| String | Address | Notes |
|--------|---------|-------|
| `"CWebServices"` | `0x141b7dd98` | Class name |
| `"CWebServices::Update_MainThread"` | `0x141b7dda8` | Main thread update |
| `"CWebServices::Update_WebServicesThread"` | `0x141b7ddf0` | Background thread update |
| `"CWebServices::Terminate"` | `0x141b7ddc8` | Shutdown |
| `"CWebServicesTaskScheduler"` | `0x141b7dc58` | Task scheduler |
| `"CWebServicesTaskScheduler::DispatchTasks"` | `0x141b7dc78` | Task dispatch loop |

The web services system uses a **dual-threaded model**:
- Main thread: processes results, updates UI
- WebServices thread: performs HTTP requests, handles async I/O

### Service Managers

The CWebServices layer is decomposed into service-specific managers:

| Manager | Address (Terminate) |
|---------|---------------------|
| `CWebServicesUserManager` | `0x141b7df20` |
| `CWebServicesIdentityManager` | `0x141b81848` |
| `CWebServicesNotificationManager` | `0x141b81878` |
| `CWebServicesAchievementService` | `0x141b818b0` |
| `CWebServicesActivityService` | `0x141b818e8` |
| `CWebServicesClientService` | `0x141b81918` |
| `CWebServicesEventService` | `0x141b819b8` |
| `CWebServicesFriendService` | `0x141b81dd0` |
| `CWebServicesMapService` | `0x141b81e18` |
| `CWebServicesMapRecordService` | `0x141b81e60` |
| `CWebServicesNewsService` | `0x141b81ea8` |
| `CWebServicesPartyService` | `0x141b81ed0` |
| `CWebServicesPermissionService` | `0x141b81f00` |
| `CWebServicesPreferenceService` | `0x141b81f38` |
| `CWebServicesPrestigeService` | `0x141b81f98` |
| `CWebServicesStatService` | `0x141b820f0` |
| `CWebServicesTagService` | `0x141b82118` |
| `CWebServicesZoneService` | `0x141b82140` |

### Connection Workflow

| Task | Address | Purpose |
|------|---------|---------|
| `"CWebServicesTask_Connect"` | `0x141b837f0` | Full connection sequence |
| `"CWebServicesTask_ConnectToNadeoServices"` | `0x141b9de50` | Nadeo auth |
| `"CWebServicesTask_PostConnect"` | `0x141c97cb0` | Post-connect initialization |
| `"CWebServicesTask_PostConnect_UrlConfig"` | `0x141cd9008` | URL configuration |
| `"CWebServicesTask_PostConnect_PlugInList"` | `0x141cd9158` | Plugin list download |
| `"CWebServicesTask_PostConnect_AdditionalFileList"` | `0x141cd8ea8` | Additional files |
| `"CWebServicesTask_PostConnect_BannedCryptedChecksumsList"` | `0x141cd9300` | Anti-cheat checksums |
| `"CWebServicesTask_PostConnect_Tag"` | `0x141cd9478` | Club tag init |
| `"CWebServicesTask_PostConnect_Zone"` | `0x141cd9818` | Zone/region init |
| `"CWebServicesTask_Disconnect"` | `0x141b83aa0` | Disconnect |
| `"CWebServicesTask_DisconnectFromNadeoServices"` | `0x141b9e008` | Nadeo disconnect |

### Permission System

| Task | Address |
|------|---------|
| `"CWebServicesTask_Permission_CheckPlayMultiplayerAsync"` | `0x141b99c18` |
| `"CWebServicesTask_Permission_CheckPlayMultiplayerMode"` | `0x141b99da0` |
| `"CWebServicesTask_Permission_CheckPlayMultiplayerSession"` | `0x141b99ef8` |
| `"CWebServicesTask_Permission_CheckCrossPlay"` | `0x141b99ac8` |
| `"CWebServicesTask_Permission_CheckUseUserCreatedContent"` | `0x141b9a068` |
| `"CWebServicesTask_Permission_CheckViewOnlinePresence"` | `0x141b9a490` |
| `"CWebServicesTask_Permission_GetPlayerInteractionRestriction"` | `0x141b9aa50` |
| `"CWebServicesTask_Permission_GetPlayerInteractionStatusList"` | `0x141b9abb0` |

---

## Layer 10: Game Network (CGameCtnNetwork)

The highest-level game network class managing the full multiplayer lifecycle.

### State Machine

The main network loop is a state machine driven by `CGameCtnNetwork::MainLoop_*` methods:

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

### Network Update Cycle

| Method | Address | Notes |
|--------|---------|-------|
| `"CGameCtnNetwork::NetUpdate_BeforePhy"` | `0x141c2b348` | Network receive before physics |
| `"CGameCtnNetwork::NetUpdate_AfterPhy"` | `0x141c2b388` | Network send after physics |
| `"CGameCtnNetwork::NetLoop_Synchronize"` | `0x141c49c28` | Synchronization loop |
| `"CGameCtnNetwork::SynchronizeGameTimer"` | `0x141c49bb0` | Timer sync |
| `"CGameCtnNetwork::PlaygroundSync_UpdateInfos"` | `0x141cf75d8` | Gameplay info sync |

This reveals a deterministic simulation model:
1. **Before physics** (`NetUpdate_BeforePhy`): Receive remote inputs
2. **Physics step**: Deterministic simulation tick
3. **After physics** (`NetUpdate_AfterPhy`): Send local results

### Connection Management

| Method | Address | Notes |
|--------|---------|-------|
| `"CGameCtnNetwork::ConnectToInternet"` | `0x141c2ba20` | At `FUN_140b00500` |
| `"CGameCtnNetwork::DisconnectFromInternet"` | `0x141c2d440` | Disconnect |
| `"CGameCtnNetwork::DisconnectFromTitle"` | `0x141c2d4a8` | Title disconnect |
| `"CGameCtnNetwork::IdentifyOnInternet"` | `0x141c2bb60` | Identification |
| `"CGameCtnNetwork::GetOnlineProfileFromInternet"` | `0x141c2ba78` | Profile fetch |
| `"CGameCtnNetwork::CheckCryptedChecksumsForInternet"` | `0x141c2b860` | Integrity check |
| `"CGameCtnNetwork::CheckCryptedChecksumsForLan"` | `0x141c2ba48` | LAN integrity check |
| `"CGameCtnNetwork::CheckPermissionServiceForChallenge"` | `0x141c2b910` | Challenge permissions |

### File Management

| Method | Address | Notes |
|--------|---------|-------|
| `"CGameCtnNetwork::DownloadFile"` | `0x141c2c940` | Generic download |
| `"CGameCtnNetwork::DownloadFileInfoFromHttpHeader"` | `0x141c2c960` | HTTP header parsing |
| `"CGameCtnNetwork::DownloadOrUpdateFile"` | `0x141c2cab8` | Download with update check |
| `"CGameCtnNetwork::DownloadOrUpdatePlugFilePack"` | `0x141c2ca60` | Plugin pack download |
| `"CGameCtnNetwork::DownloadOrUpdateTitlePackages"` | `0x141c2d220` | Title package updates |
| `"CGameCtnNetwork::UploadTitlePackage"` | `0x141c2d3d0` | Upload title package |
| `"CGameCtnNetwork::GetPackCloudUrl"` | `0x141c2cab8` | Cloud URL resolution |
| `"CGameCtnNetwork::DownloadManiaNetResource"` | `0x141c2d928` | ManiaNet resource download |
| `"CGameCtnNetwork::GetManiaNetResource"` | `0x141c2d598` | ManiaNet resource getter |
| `"CGameCtnNetwork::CheckManiaNetResourceIsUpToDate"` | `0x141c2d750` | Version check |

### Anti-Cheat System

| String | Address | Notes |
|--------|---------|-------|
| `"AntiCheatServerUrl"` | `0x141c04d68` | Anti-cheat server endpoint |
| `"CGameCtnNetwork::UpdateAntiCheat"` | `0x141c2df10` | Anti-cheat update loop |
| `"CGameCtnNetwork::OpenAntiCheatSession"` | `0x141c2df70` | Session creation |
| `"CGameCtnNetwork::UpdateAntiCheatReplayUpload"` | `0x141c2e050` | Replay upload for verification |
| `"AntiCheatReplayChunkSize"` | `0x141c2af98` | Upload chunking config |
| `"AntiCheatReplayMaxSize"` | `0x141c2afe0` | Max replay size |
| `"AntiCheatReplayMaxSizeOnCheatReport"` | `0x141c2afb8` | Enhanced for cheat reports |
| `"UploadAntiCheatReplayOnlyWhenUnblocked"` | `0x141c2af78` | Upload gating |
| `"UploadAntiCheatReplayForcedOnCheatReport"` | `0x141c2b118` | Force upload on report |
| `"Anticheat.EndOfScript"` | `0x141d046e0` | Script callback |
| `"Anticheat.SendResult"` | `0x141d04860` | Result callback |

The anti-cheat system uploads replay data to a server-side verification service. Key parameters:
- **Chunked upload**: `AntiCheatReplayChunkSize` controls upload chunk size
- **Size limits**: Both normal and enhanced limits for cheat reports
- **Forced uploads**: Can be triggered on cheat detection

### Demo Token System

| String | Address |
|--------|---------|
| `"DemoTokenKickingTimeOut"` | `0x141c2b068` |
| `"DemoTokenCheckingTimeOut"` | `0x141c2b080` |
| `"DemoTokenAskingTimeOut"` | `0x141c2b0a0` |
| `"DemoTokenTimeBetweenCheck"` | `0x141c2b0b8` |
| `"DemoTokenWaitingTimeAfterFirstAnswer"` | `0x141c2b0d8` |
| `"DemoTokenRetryMax"` | `0x141c2b100` |
| `"DemoTokenCost"` | `0x141c2c178` |
| `"Invalid demo token"` | `0x141c2e2a0` |

This appears to be a time-limited access system with server-side validation.

### Account Mapping

| Method | Address |
|--------|---------|
| `"CGameCtnNetwork::GetAccountFromUplayUser"` | `0x141c2e340` |
| `"CGameCtnNetwork::GetAccountFromSteamUser"` | `0x141c2e370` |

The game supports mapping from both Ubisoft Connect and Steam accounts.

---

## Layer 11: CGameManiaPlanetNetwork

Higher-level game network for ManiaPlanet-specific features:

| String | Address | Notes |
|--------|---------|-------|
| `"CGameManiaPlanetNetwork"` | `0x141cae7e8` | Class name |
| `"CGameManiaPlanetNetwork::PlaygroundExit"` | `0x141cae670` | Exit handling |
| `"CGameManiaPlanetNetwork::PlaygroundPrepare"` | `0x141cae698` | Playground init |
| `"CGameManiaPlanetNetwork::MainLoop_PlaygroundPlay"` | `0x141cae760` | Play loop |
| `"CGameManiaPlanetNetwork::MainLoop_SetUp"` | `0x141cae798` | Setup |
| `"CGameManiaPlanetNetwork::ScriptCloudManager_Create"` | `0x141cae728` | Cloud scripting |
| `"CGameManiaPlanetNetwork::ScriptCloudManager_Destroy"` | `0x141cae6f0` | Cloud cleanup |

---

## Matchmaking

| String | Address | Notes |
|--------|---------|-------|
| `"Matchmaking"` | `0x141a115f0` | Feature name |
| `"profilesPreciseMatchmakingClient"` | `0x141a0d168` | Client matchmaking profile |
| `"profilesPreciseMatchmakingMatch"` | `0x141a0d190` | Match matchmaking profile |
| `"matchmakingGroupsMatchesPrecise"` | `0x141a0d1b0` | Group match precision |
| `"matchmakingSpaceGlobalHarboursocial"` | `0x141a0d1d0` | Social matchmaking space |
| `"matchmakingProfilesGlobalHarboursocial"` | `0x141a0d218` | Social profiles |
| `"profilesMatchmakingOnlineAccess"` | `0x141a0d1f8` | Online access profile |
| `"Join matchmaking"` | `0x141c059a8` | UI string |
| `"Join the matchmaking queue to find a match."` | `0x141c059c0` | UI description |
| `"Play and compete with your friends on a 2v2 matchmaking game."` | `0x141c05a80` | 2v2 description |
| `"Ladder_SetMatchMakingMatchId"` | `0x141c5cf38` | Ladder integration |

The matchmaking system is integrated with Ubisoft's "Harbour" social platform (referenced as "harboursocial" in config keys). It supports at least 2v2 matchmaking with ranked ladder integration.

[UNKNOWN] The exact matchmaking algorithm and parameters. The "Precise" variants suggest multiple precision levels for matching.

---

## XMPP Chat System (CNetXmpp)

XMPP/Jabber is used for in-game chat:

| String | Address | Notes |
|--------|---------|-------|
| `"CNetXmpp::HighFreqPoll"` | `0x141d11430` | High-frequency polling |
| `"CNetXmpp_Timer"` | `0x141d11498` | Timer-based updates |
| `"squad.chat.maniaplanet.com"` | `0x141c444d0` | Squad chat server |
| `"channel.chat.maniaplanet.com"` | `0x141c444f0` | Channel chat server |
| `"http://jabber.org/protocol/muc#user"` | `0x141d10f00` | Multi-user chat |
| `"jabber:x:conference"` | `0x141d10f40` | Conference protocol |
| `"jabber:iq:roster"` | `0x141d11110` | Roster management |
| `"http://jabber.org/protocol/disco#info"` | `0x141d11300` | Service discovery |
| `"urn:xmpp:bob"` | `0x141d110e8` | Binary data transfer |
| `"urn:xmpp:ping"` | `0x141d11218` | Keepalive ping |

The game uses dedicated XMPP servers at `*.chat.maniaplanet.com` for squad and channel chat.

---

## Voice Chat (Vivox)

Voice chat uses the Vivox middleware:

| String | Address | Notes |
|--------|---------|-------|
| `"voicechatTokenVivox"` | `0x141a0dd98` | Vivox token config key |
| `"voicechatConfigVivox"` | `0x141a0ddb0` | Vivox config key |
| `"VoicechatClient::createVivoxVoicechatToken"` | `0x141a22860` | Token creation |
| `"VoicechatClient::getVivoxVoicechatConfig"` | `0x141a22890` | Config retrieval |
| `"VoiceChat.dll"` | `0x141d0d748` | Vivox DLL name |

Vivox is loaded as a separate DLL (`VoiceChat.dll`). Token-based authentication is used for Vivox sessions.

---

## CNetIPC (Inter-Process Communication)

| String | Address | Notes |
|--------|---------|-------|
| `"CNetIPC"` | `0x141d10d38` | Class name |
| `"CNetIPC::Tick"` | `0x141d10d78` | Per-tick update |
| `"CNetIPC::HighFreqPoll"` | `0x141d10d88` | High-frequency polling |

[UNKNOWN] The IPC target. This may be used for communication with the Ubisoft Connect overlay process, the Vivox voice chat process, or an anti-cheat monitor.

---

## CNetIPSource / CNetUPnP

| String | Address | Notes |
|--------|---------|-------|
| `"CNetIPSource"` | `0x141d16010` | IP source management |
| `"CNetUPnP"` | `0x141d16110` | UPnP port mapping |

The game supports UPnP for automatic port forwarding (NAT traversal).

---

## UbiServices SDK Build Information

From leaked source file paths, the UbiServices SDK build environment:

```
Build root: D:\CodeBase_Ext\externallibs\ubiservices\
SDK path:   ubiservices\external\harbourcommon\libraries\_fetch\
Dependencies fetched:
  - openssl (1.1.1t+quic)
  - curl
```

The "harbourcommon" namespace refers to Ubisoft's common services framework ("Harbour").

Nadeo's own code base path:
```
C:\Nadeo\CodeBase_tm-retail\Nadeo\Engines\NetEngine\source\NetHttpClient_Curl.cpp
```

---

## Network Architecture Summary

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

### Authentication Chain

```
                    UPC_TicketGet
                         |
                         v
              +---------------------+
              | UPC Ticket (Ubisoft |
              | Connect)            |
              +---------------------+
                         |
          CNetUbiServicesTask_CreateSession
                         |
                         v
              +---------------------+
              | UbiServices Session |
              | (access token)      |
              +---------------------+
                         |
     nadeoservices_token_create_from_ubiservices_v2
                         |
                         v
              +---------------------+
              | Nadeo Services      |
              | Access Token        |
              +---------------------+
                         |
     nadeoservices_token_refresh_v2 (periodic)
                         |
                         v
              +---------------------+
              | Refreshed Access    |
              | Token               |
              +---------------------+
```

### Class Hierarchy (Inferred)

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
 +-- CWebServices
 |    +-- CWebServicesTask_* (100+ task types)
 |    +-- CWebServicesTaskResult_* (100+ result types)
 |    +-- CWebServicesTaskScheduler
 |    +-- CWebServices*Service (18 service managers)
 +-- CXmlRpc
 |    +-- CXmlRpcEvent
 +-- CGameCtnNetwork
 +-- CGameManiaPlanetNetwork
 +-- CGameMasterServer
```

---

## Key Unknowns

1. **[UNKNOWN]** Exact wire protocol format for TCP/UDP game connections (packet structure, serialization format)
2. **[UNKNOWN]** Whether QUIC/HTTP3 is actively used (OpenSSL +quic variant is present but may be unused)
3. **[UNKNOWN]** Anti-cheat server endpoint URL (only the config key name `"AntiCheatServerUrl"` was found)
4. **[UNKNOWN]** CNetIPC target process identity
5. **[UNKNOWN]** Exact matchmaking algorithm parameters
6. **[UNKNOWN]** Details of the "Harbour" social platform integration beyond config key names
7. **[UNKNOWN]** Whether the game uses peer-to-peer connections or only dedicated servers for gameplay
8. **[UNKNOWN]** CNetFormTimed and CNetFormPing wire format details
9. **[UNKNOWN]** How CNetFileTransferNod serializes game objects for transfer
10. **[UNKNOWN]** Full REST API URL structure for Nadeo Services endpoints (only domain suffixes visible)

---

## Decompiled Functions

See `/decompiled/networking/` for decompiled code:

| File | Function | Address |
|------|----------|---------|
| `CNetHttpClient_InternalConnect.c` | `CNetHttpClient::InternalConnect` | `0x1403050a0` |
| `CNetHttpClient_CreateRequest.c` | `CNetHttpClient::CreateRequest` | `0x14030c3f0` |
| `CGameCtnNetwork_ConnectToInternet.c` | `CGameCtnNetwork::ConnectToInternet` | `0x140b00500` |
| `nadeoservices_token_create_from_ubiservices.c` | Token exchange wrapper | `0x140356160` |

### Key Function Addresses (For Further Analysis)

| Address | Probable Function | Evidence |
|---------|-------------------|----------|
| `0x1403089f0` | `CNetServer::DoReception` | xref to string |
| `0x1414a1c80` | `CNetClient::DoReception` | xref to string |
| `0x14030c3f0` | `CNetHttpClient::CreateRequest` | xref to string |
| `0x1403050a0` | `CNetHttpClient::InternalConnect` | xref to string |
| `0x140b00500` | `CGameCtnNetwork::ConnectToInternet` | xref to string |
| `0x140356160` | Nadeo token creation from UbiServices | xref to API name string |

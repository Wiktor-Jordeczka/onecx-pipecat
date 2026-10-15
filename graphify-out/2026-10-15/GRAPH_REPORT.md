# Graph Report - onecx-pipecat  (2026-10-15)

## Corpus Check
- 34 files · ~18,821 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .adoc 6, (none) 1, .lock 1)

## Summary
- 444 nodes · 1218 edges · 15 communities (11 shown, 4 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6e498a3d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Principal
- Settings
- models.py
- Task 3: Verify typed configuration and the six replaceable adapter interfaces
- VoiceSession
- test_session.py
- adapters/__init__.py
- AgentConfigSnapshot
- create_app
- VoiceEntry
- test_adapters.py
- CLAUDE.md
- onecx-pipecat

## God Nodes (most connected - your core abstractions)
1. `VoiceSession` - 39 edges
2. `Settings` - 36 edges
3. `Principal` - 33 edges
4. `JwtAuthAdapter` - 26 edges
5. `AppContainer` - 26 edges
6. `AgentConfigSnapshot` - 24 edges
7. `McpServerSnapshot` - 23 edges
8. `_container()` - 23 edges
9. `_session()` - 23 edges
10. `create_app()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AgentConfigAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/agent_config.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AuthAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/auth.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `McpAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/mcp.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `PermissionAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/permission.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `ConversationPersistence`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/persistence.py

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 0 - "Principal"
Cohesion: 0.06
Nodes (18): AuthAdapter, AuthenticationError, JwtAuthAdapter, AuthSettings, Principal, FakeAuth, FakePermission, _rsa_jwk() (+10 more)

### Community 1 - "Settings"
Cohesion: 0.12
Nodes (25): Problem Statement, build_agent_config(), build_auth(), build_chat(), build_mcp(), build_permission(), build_persistence(), build_stt() (+17 more)

### Community 2 - "models.py"
Cohesion: 0.07
Nodes (21): HttpMcpAdapter, McpAdapter, McpDiscovery, McpToolResult, McpSettings, AudioState, McpServerSnapshot, PermissionDecision (+13 more)

### Community 3 - "Task 3: Verify typed configuration and the six replaceable adapter interfaces"
Cohesion: 0.06
Nodes (26): Approach, File-Level Task List, Global Constraints, Notes, Pipecat Application Foundation (#589) — Verify-and-Close Plan, Task 1: Verify install, static checks, and the async test suite, Task 2: Verify the app runs and serves the health path over a real socket, Task 3: Verify typed configuration and the six replaceable adapter interfaces (+18 more)

### Community 4 - "VoiceSession"
Cohesion: 0.12
Nodes (15): voice(), AssistantAudio, AssistantText, decode_command(), DegradedCapability, ErrorEvent, _optional_str(), _principal_token() (+7 more)

### Community 5 - "test_session.py"
Cohesion: 0.17
Nodes (29): ClientAudio, RefreshToken, SessionState, _container(), _session(), _snapshot_with_servers(), _start(), test_audio_before_start_is_rejected() (+21 more)

### Community 6 - "adapters/__init__.py"
Cohesion: 0.08
Nodes (8): Chat, ChatAccessError, ChatAdapter, HttpChatAdapter, PermissionAdapter, ChatSettings, FakeChat, test_chat_loads_from_internal_chat_endpoint()

### Community 8 - "AgentConfigSnapshot"
Cohesion: 0.11
Nodes (8): AgentConfigAdapter, AgentConfigError, HttpAgentConfigAdapter, _parse_configuration(), _parse_mcp_server(), AgentConfigSettings, AgentConfigSnapshot, FakeAgentConfig

### Community 10 - "create_app"
Cohesion: 0.16
Nodes (13): create_app(), healthz(), _pipecat_version(), fake_container(), _container(), _start(), test_ws_audio_before_start_reports_illegal_state(), test_ws_expired_token_ends_session() (+5 more)

### Community 11 - "VoiceEntry"
Cohesion: 0.19
Nodes (7): ConversationPersistence, InMemoryPersistence, PersistenceSettings, VoiceEntry, test_persistence_eviction_is_per_session(), test_persistence_evicts_oldest_entry_when_cap_exceeded(), test_persistence_round_trip()

### Community 12 - "test_adapters.py"
Cohesion: 0.09
Nodes (25): allowed_tools(), HttpPermissionAdapter, resolve_tool_permission(), PermissionSettings, AgentToolSnapshot, PermissionAction, _client(), _permission_adapter() (+17 more)

## Knowledge Gaps
- **14 isolated node(s):** `onecx-pipecat`, `graphify`, `Quick start`, `Linting and pre-commit`, `Documentation` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 151 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Principal` connect `Principal` to `models.py`, `VoiceSession`, `test_session.py`, `adapters/__init__.py`, `test_adapters.py`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `VoiceSession` (e.g. with `AgentConfigError` and `AuthenticationError`) actually correct?**
  _`VoiceSession` has 22 INFERRED edges - model-reasoned connections that need verification._
- **What connects `onecx-pipecat`, `graphify`, `Quick start` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Principal` be split into smaller, more focused modules?**
  _Cohesion score 0.055178652193577565 - nodes in this community are weakly interconnected._
- **Why does `VoiceSession` connect `VoiceSession` to `Principal`, `Settings`, `models.py`, `test_session.py`, `adapters/__init__.py`, `AgentConfigSnapshot`, `create_app`, `VoiceEntry`, `test_adapters.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `Settings` (e.g. with `Problem Statement` and `Task 3: Verify typed configuration and the six replaceable adapter interfaces`) actually correct?**
  _`Settings` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.12323232323232323 - nodes in this community are weakly interconnected._
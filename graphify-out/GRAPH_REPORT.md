# Graph Report - onecx-pipecat  (2026-10-16)

## Corpus Check
- 34 files · ~15,881 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .adoc 6, (none) 1, .lock 1)

## Summary
- 504 nodes · 1358 edges · 15 communities (11 shown, 4 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 143 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3f1fbf3e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_adapters.py
- Settings
- models.py
- adapters/__init__.py
- session.py
- test_session.py
- ChatAccessError
- Principal
- AgentConfigSnapshot
- AppContainer
- fakes.py
- CLAUDE.md
- onecx-pipecat

## God Nodes (most connected - your core abstractions)
1. `VoiceSession` - 39 edges
2. `Settings` - 37 edges
3. `Principal` - 33 edges
4. `JwtAuthAdapter` - 32 edges
5. `AppContainer` - 26 edges
6. `McpServerSnapshot` - 24 edges
7. `AgentConfigSnapshot` - 24 edges
8. `_container()` - 23 edges
9. `_session()` - 23 edges
10. `create_app()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AgentConfigAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/agent_config.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AuthAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/auth.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `ConversationPersistence`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/persistence.py
- `Task 2: Verify the app runs and serves the health path over a real socket` --references--> `InMemoryPersistence`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/persistence.py
- `Problem Statement` --references--> `Settings`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/config.py

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 0 - "test_adapters.py"
Cohesion: 0.05
Nodes (43): AuthenticationError, JwtAuthAdapter, _keycloak_endpoint(), HttpChatAdapter, AuthSettings, ChatSettings, _app_permissions(), _client() (+35 more)

### Community 1 - "Settings"
Cohesion: 0.12
Nodes (20): ClientCredentialsAuth, ServiceTokenError, build_agent_config(), build_auth(), build_chat(), build_mcp(), build_permission(), build_persistence() (+12 more)

### Community 2 - "models.py"
Cohesion: 0.08
Nodes (27): allowed_tools(), resolve_tool_permission(), ConversationPersistence, InMemoryPersistence, PersistenceSettings, AgentToolSnapshot, AudioState, PermissionAction (+19 more)

### Community 3 - "adapters/__init__.py"
Cohesion: 0.06
Nodes (28): Approach, File-Level Task List, Global Constraints, Notes, Pipecat Application Foundation (#589) — Verify-and-Close Plan, Task 1: Verify install, static checks, and the async test suite, Task 2: Verify the app runs and serves the health path over a real socket, Task 3: Verify typed configuration and the six replaceable adapter interfaces (+20 more)

### Community 4 - "session.py"
Cohesion: 0.11
Nodes (17): propagated_headers(), voice(), AssistantAudio, AssistantText, decode_command(), DegradedCapability, ErrorEvent, _optional_str() (+9 more)

### Community 5 - "test_session.py"
Cohesion: 0.22
Nodes (26): ClientAudio, RefreshToken, SessionState, _container(), _session(), _snapshot_with_servers(), _start(), test_audio_before_start_is_rejected() (+18 more)

### Community 6 - "ChatAccessError"
Cohesion: 0.14
Nodes (4): Chat, ChatAccessError, ChatAdapter, FakeChat

### Community 7 - "Principal"
Cohesion: 0.06
Nodes (10): AuthAdapter, HttpPermissionAdapter, PermissionSettings, Principal, FakeAuth, FakePermission, test_principal_round_trips(), test_start_verifies_token_from_message_not_url() (+2 more)

### Community 8 - "AgentConfigSnapshot"
Cohesion: 0.11
Nodes (8): AgentConfigAdapter, AgentConfigError, HttpAgentConfigAdapter, _parse_configuration(), _parse_mcp_server(), AgentConfigSettings, AgentConfigSnapshot, FakeAgentConfig

### Community 10 - "AppContainer"
Cohesion: 0.09
Nodes (21): Problem Statement, create_app(), healthz(), _pipecat_version(), get_settings(), AppContainer, run(), fake_container() (+13 more)

### Community 13 - "fakes.py"
Cohesion: 0.06
Nodes (16): HttpMcpAdapter, McpDiscovery, McpToolResult, _reason(), McpSettings, McpServerSnapshot, ToolProposal, FakeMcp (+8 more)

## Knowledge Gaps
- **14 isolated node(s):** `onecx-pipecat`, `graphify`, `Quick start`, `Linting and pre-commit`, `Documentation` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 177 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Principal` connect `Principal` to `test_adapters.py`, `Settings`, `models.py`, `adapters/__init__.py`, `session.py`, `test_session.py`, `fakes.py`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `VoiceSession` (e.g. with `AgentConfigError` and `AuthenticationError`) actually correct?**
  _`VoiceSession` has 22 INFERRED edges - model-reasoned connections that need verification._
- **What connects `onecx-pipecat`, `graphify`, `Quick start` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_adapters.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05132788559754852 - nodes in this community are weakly interconnected._
- **Why does `VoiceSession` connect `session.py` to `test_adapters.py`, `models.py`, `test_session.py`, `ChatAccessError`, `Principal`, `AgentConfigSnapshot`, `AppContainer`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `Settings` (e.g. with `Problem Statement` and `Task 3: Verify typed configuration and the six replaceable adapter interfaces`) actually correct?**
  _`Settings` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.11733615221987315 - nodes in this community are weakly interconnected._
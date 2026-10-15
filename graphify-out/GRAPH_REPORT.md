# Graph Report - onecx-pipecat  (2026-10-15)

## Corpus Check
- 34 files · ~19,985 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .adoc 6, (none) 1, .lock 1)

## Summary
- 504 nodes · 1353 edges · 21 communities (16 shown, 5 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 143 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6e498a3d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_adapters.py
- Settings
- models.py
- adapters/__init__.py
- VoiceSession
- test_session.py
- chat.py
- Principal
- AgentConfigSnapshot
- McpServerSnapshot
- AppContainer
- VoiceEntry
- HttpPermissionAdapter
- fakes.py
- ToolProposal
- AgentToolSnapshot
- CLAUDE.md
- onecx-pipecat
- _Hosts

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
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AuthAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/auth.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `ConversationPersistence`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/persistence.py
- `Task 2: Verify the app runs and serves the health path over a real socket` --references--> `InMemoryPersistence`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/persistence.py
- `Problem Statement` --references--> `Settings`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/config.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `Settings`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/config.py

## Import Cycles
- None detected.

## Communities (21 total, 5 thin omitted)

### Community 0 - "test_adapters.py"
Cohesion: 0.07
Nodes (26): AuthenticationError, JwtAuthAdapter, _keycloak_endpoint(), ServiceTokenError, AuthSettings, _issuer_token(), _jwks_endpoint(), _permission_adapter() (+18 more)

### Community 1 - "Settings"
Cohesion: 0.10
Nodes (22): HttpAgentConfigAdapter, ClientCredentialsAuth, build_agent_config(), build_auth(), build_chat(), build_mcp(), build_permission(), build_persistence() (+14 more)

### Community 2 - "models.py"
Cohesion: 0.15
Nodes (11): AudioState, PermissionAction, PermissionDecision, PermissionDecisionStatus, ToolRule, TranscriptState, test_agent_config_parses_ai_provider_configuration(), test_agent_config_snapshot_is_pinned() (+3 more)

### Community 3 - "adapters/__init__.py"
Cohesion: 0.05
Nodes (29): Approach, File-Level Task List, Global Constraints, Notes, Pipecat Application Foundation (#589) — Verify-and-Close Plan, Task 1: Verify install, static checks, and the async test suite, Task 2: Verify the app runs and serves the health path over a real socket, Task 3: Verify typed configuration and the six replaceable adapter interfaces (+21 more)

### Community 4 - "VoiceSession"
Cohesion: 0.13
Nodes (15): voice(), AssistantAudio, AssistantText, decode_command(), DegradedCapability, ErrorEvent, _optional_str(), _principal_token() (+7 more)

### Community 5 - "test_session.py"
Cohesion: 0.22
Nodes (26): ClientAudio, RefreshToken, SessionState, _container(), _session(), _snapshot_with_servers(), _start(), test_audio_before_start_is_rejected() (+18 more)

### Community 6 - "chat.py"
Cohesion: 0.07
Nodes (19): Chat, ChatAccessError, ChatAdapter, HttpChatAdapter, ChatSettings, FakeChat, _client(), _pin() (+11 more)

### Community 7 - "Principal"
Cohesion: 0.07
Nodes (8): AuthAdapter, Principal, FakeAuth, FakePermission, test_principal_round_trips(), test_start_verifies_token_from_message_not_url(), authenticate(), refresh()

### Community 8 - "AgentConfigSnapshot"
Cohesion: 0.18
Nodes (5): AgentConfigError, _parse_configuration(), _parse_mcp_server(), AgentConfigSnapshot, FakeAgentConfig

### Community 9 - "McpServerSnapshot"
Cohesion: 0.16
Nodes (3): HttpMcpAdapter, _reason(), McpServerSnapshot

### Community 10 - "AppContainer"
Cohesion: 0.09
Nodes (21): Problem Statement, create_app(), healthz(), _pipecat_version(), get_settings(), AppContainer, run(), fake_container() (+13 more)

### Community 11 - "VoiceEntry"
Cohesion: 0.18
Nodes (9): ConversationPersistence, InMemoryPersistence, PersistenceSettings, VoiceEntry, VoiceEntryKind, test_persistence_eviction_is_per_session(), test_persistence_evicts_oldest_entry_when_cap_exceeded(), test_persistence_round_trip() (+1 more)

### Community 12 - "HttpPermissionAdapter"
Cohesion: 0.19
Nodes (4): HttpPermissionAdapter, PermissionSettings, test_voice_permission_fails_closed_on_error_status(), test_voice_permission_fails_closed_when_unreachable()

### Community 13 - "fakes.py"
Cohesion: 0.14
Nodes (3): McpDiscovery, McpToolResult, FakeMcp

### Community 14 - "ToolProposal"
Cohesion: 0.24
Nodes (9): ToolProposal, _mcp(), _mcp_servers(), read(), test_mcp_discovers_tools_and_reports_failed_servers(), test_mcp_invokes_a_tool(), test_mcp_tool_error_is_a_sanitized_failure(), test_mcp_unreachable_server_is_a_sanitized_failure() (+1 more)

### Community 15 - "AgentToolSnapshot"
Cohesion: 0.31
Nodes (7): allowed_tools(), resolve_tool_permission(), AgentToolSnapshot, test_allowed_tools_filters_to_always_allow_only(), test_tool_from_unknown_server_is_denied(), test_tool_rule_wins_over_unlisted_policy(), test_unruled_tool_uses_its_servers_unlisted_policy()

## Knowledge Gaps
- **14 isolated node(s):** `onecx-pipecat`, `graphify`, `Quick start`, `Linting and pre-commit`, `Documentation` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 176 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Principal` connect `Principal` to `test_adapters.py`, `models.py`, `adapters/__init__.py`, `VoiceSession`, `test_session.py`, `HttpPermissionAdapter`, `fakes.py`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `VoiceSession` (e.g. with `AgentConfigError` and `AuthenticationError`) actually correct?**
  _`VoiceSession` has 22 INFERRED edges - model-reasoned connections that need verification._
- **What connects `onecx-pipecat`, `graphify`, `Quick start` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_adapters.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07033315705975675 - nodes in this community are weakly interconnected._
- **Why does `VoiceSession` connect `VoiceSession` to `test_adapters.py`, `test_session.py`, `chat.py`, `Principal`, `AgentConfigSnapshot`, `AppContainer`, `VoiceEntry`, `AgentToolSnapshot`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `Settings` (e.g. with `Problem Statement` and `Task 3: Verify typed configuration and the six replaceable adapter interfaces`) actually correct?**
  _`Settings` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.10283687943262411 - nodes in this community are weakly interconnected._
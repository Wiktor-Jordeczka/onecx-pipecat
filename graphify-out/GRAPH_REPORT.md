# Graph Report - onecx-pipecat  (2026-10-15)

## Corpus Check
- 33 files · ~19,858 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .adoc 6, (none) 1, .lock 1)

## Summary
- 465 nodes · 1284 edges · 20 communities (14 shown, 6 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 152 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e2f28f3c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_adapters.py
- Settings
- InMemoryMcpAdapter
- adapters/__init__.py
- VoiceSession
- test_session.py
- chat.py
- InMemoryPermissionAdapter
- AgentToolSnapshot
- Principal
- create_app
- VoiceEntry
- permission.py
- PermissionAction
- HttpAgentConfigAdapter
- models.py
- CLAUDE.md
- onecx-pipecat

## God Nodes (most connected - your core abstractions)
1. `Settings` - 41 edges
2. `VoiceSession` - 39 edges
3. `InMemoryPermissionAdapter` - 33 edges
4. `Principal` - 31 edges
5. `AgentToolSnapshot` - 31 edges
6. `PermissionAction` - 30 edges
7. `AgentConfigSnapshot` - 30 edges
8. `ToolProposal` - 29 edges
9. `JwtAuthAdapter` - 26 edges
10. `AppContainer` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AgentConfigAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/agent_config.py
- `Task 2: Verify the app runs and serves the health path over a real socket` --references--> `InMemoryAgentConfigAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/agent_config.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `AuthAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/auth.py
- `Task 2: Verify the app runs and serves the health path over a real socket` --references--> `InMemoryAuthAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/auth.py
- `Task 3: Verify typed configuration and the six replaceable adapter interfaces` --references--> `McpAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-08-pipecat-application-foundation.md → onecx_pipecat/adapters/mcp.py

## Import Cycles
- None detected.

## Communities (20 total, 6 thin omitted)

### Community 0 - "test_adapters.py"
Cohesion: 0.07
Nodes (23): AuthenticationError, InMemoryAuthAdapter, _InMemoryCredential, JwtAuthAdapter, AuthSettings, _rsa_jwk(), _rsa_jwks(), _signed_token() (+15 more)

### Community 1 - "Settings"
Cohesion: 0.13
Nodes (26): Problem Statement, build_agent_config(), build_auth(), build_chat(), build_mcp(), build_permission(), build_persistence(), build_stt() (+18 more)

### Community 2 - "InMemoryMcpAdapter"
Cohesion: 0.06
Nodes (13): HttpMcpAdapter, InMemoryMcpAdapter, McpAdapter, McpToolResult, McpSettings, test_mcp_discover_returns_registered_tools(), test_mcp_discover_skips_and_reports_failed_server(), test_mcp_invoke_with_only_proposal_uses_arguments() (+5 more)

### Community 3 - "adapters/__init__.py"
Cohesion: 0.06
Nodes (26): Approach, File-Level Task List, Global Constraints, Notes, Pipecat Application Foundation (#589) — Verify-and-Close Plan, Task 1: Verify install, static checks, and the async test suite, Task 2: Verify the app runs and serves the health path over a real socket, Task 3: Verify typed configuration and the six replaceable adapter interfaces (+18 more)

### Community 4 - "VoiceSession"
Cohesion: 0.13
Nodes (15): voice(), AssistantAudio, AssistantText, decode_command(), DegradedCapability, ErrorEvent, _optional_str(), _principal_token() (+7 more)

### Community 5 - "test_session.py"
Cohesion: 0.17
Nodes (29): McpDiscovery, ClientAudio, RefreshToken, SessionState, _container(), _session(), _start(), test_audio_before_start_is_rejected() (+21 more)

### Community 6 - "chat.py"
Cohesion: 0.10
Nodes (7): Chat, ChatAccessError, ChatAdapter, HttpChatAdapter, InMemoryChatAdapter, ChatSettings, test_chat_load_returns_registered_chat()

### Community 7 - "InMemoryPermissionAdapter"
Cohesion: 0.12
Nodes (16): InMemoryPermissionAdapter, PermissionSettings, ExecutionPolicy, PermissionDecisionStatus, ToolProposal, test_permission_exact_rule_can_deny_or_allow(), test_permission_exact_rule_wins(), test_permission_falls_back_to_server_default_ask() (+8 more)

### Community 8 - "AgentToolSnapshot"
Cohesion: 0.11
Nodes (9): AgentConfigAdapter, _parse_configuration(), _Pinned, AgentConfigSnapshot, AgentToolSnapshot, test_allowed_tools_filters_to_always_allow_only(), test_allowed_tools_uses_unlisted_permission_when_no_rule(), test_agent_config_snapshot_is_pinned() (+1 more)

### Community 9 - "Principal"
Cohesion: 0.10
Nodes (6): AuthAdapter, Principal, test_principal_round_trips(), test_start_verifies_token_from_message_not_url(), authenticate(), refresh()

### Community 10 - "create_app"
Cohesion: 0.17
Nodes (12): create_app(), healthz(), _pipecat_version(), _container(), _start(), test_ws_audio_before_start_reports_illegal_state(), test_ws_expired_token_ends_session(), test_ws_malformed_command_is_rejected() (+4 more)

### Community 11 - "VoiceEntry"
Cohesion: 0.18
Nodes (9): ConversationPersistence, InMemoryPersistence, PersistenceSettings, VoiceEntry, VoiceEntryKind, test_persistence_eviction_is_per_session(), test_persistence_evicts_oldest_entry_when_cap_exceeded(), test_persistence_round_trip() (+1 more)

### Community 12 - "permission.py"
Cohesion: 0.19
Nodes (4): PermissionAdapter, AgentMcpToolRule, PermissionDecision, test_permission_decision_carries_action()

### Community 13 - "PermissionAction"
Cohesion: 0.23
Nodes (7): AgentConfigError, InMemoryAgentConfigAdapter, PermissionAction, test_agent_config_pins_highest_version(), test_agent_config_snapshot_can_carry_tools_and_policy_hints(), test_agent_config_snapshot_carries_voice_and_unlisted_permission(), test_agent_config_voice_disabled_fails()

## Knowledge Gaps
- **14 isolated node(s):** `onecx-pipecat`, `graphify`, `Quick start`, `Linting and pre-commit`, `Documentation` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 152 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VoiceSession` connect `VoiceSession` to `test_adapters.py`, `Settings`, `test_session.py`, `chat.py`, `AgentToolSnapshot`, `Principal`, `create_app`, `VoiceEntry`, `PermissionAction`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `Settings` (e.g. with `Problem Statement` and `Task 3: Verify typed configuration and the six replaceable adapter interfaces`) actually correct?**
  _`Settings` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `onecx-pipecat`, `graphify`, `Quick start` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_adapters.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07422559906487435 - nodes in this community are weakly interconnected._
- **Why does `Principal` connect `Principal` to `test_adapters.py`, `VoiceSession`, `test_session.py`, `InMemoryPermissionAdapter`, `permission.py`, `models.py`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `VoiceSession` (e.g. with `AgentConfigError` and `AuthenticationError`) actually correct?**
  _`VoiceSession` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.12657004830917876 - nodes in this community are weakly interconnected._
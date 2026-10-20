# OneCX Pipecat: Architecture Overview

## Purpose

OneCX Pipecat is the foundation for **authenticated voice sessions** in OneCX.
It is a Python FastAPI service that exposes a single WebSocket voice endpoint.
Every external dependency (authentication, chat, agent configuration,
permissions, MCP tools, speech, persistence) sits behind a replaceable adapter,
so the service can run, be tested and be linted without cloud credentials.

> **Status:** this is a foundation. The Pipecat framework is a declared
> dependency, and its version is reported by the health endpoint, but the voice
> turn is not yet driven by a Pipecat pipeline. Speech-to-text and
> text-to-speech are in-memory fakes, and the "assistant" echoes what it heard.

## How Pipecat works (background)

[Pipecat](https://pipecat.ai) is an open-source Python framework for real-time
voice and multimodal agents.

| Concept | Description |
|---|---|
| **Frames** | Typed units of data flowing through the system: audio, transcriptions, LLM text, synthesized audio, and control signals (start, end, interrupt). |
| **Frame processors** | Single-purpose stages that consume frames and emit frames. |
| **Pipeline** | An ordered chain of processors, typically `transport in → VAD → STT → context aggregation → LLM → TTS → transport out`. |
| **Transport** | The real-time carrier: WebRTC, WebSocket or telephony. |
| **Services** | Pluggable STT, LLM and TTS vendors. The LLM can call tools, including MCP tools. |
| **Task and runner** | Run the pipeline asynchronously and handle interruptions (barge-in) and lifecycle events. |

OneCX Pipecat wraps this model with OneCX authentication, permissions, agent
configuration and tool policy.

## Component overview

Diagram: [component-overview.drawio](docs/diagrams/component-overview.drawio)

| Component | Responsibility |
|---|---|
| **Entrypoint** | Builds the container and the application, and starts uvicorn. |
| **HTTP / WebSocket app** | A health endpoint (status, Pipecat version, active adapter names) and the voice WebSocket. It handles framing, JSON decoding and the expiry watcher, and delegates all behaviour to the session. |
| **Composition root (container)** | Owns one instance of each adapter for the application's lifetime. |
| **Configuration** | Typed settings loaded from environment variables (prefix `ONECX_`, nested delimiter `__`), one group per adapter. |
| **Protocol** | A transport-neutral vocabulary of commands (client to server) and events (server to client). It is independent of the WebSocket so the carrier can later be swapped, for example for WebRTC. |
| **Voice session** | A state machine that consumes commands and returns events. It knows nothing about WebSocket, JSON or FastAPI. |
| **Domain models** | Principal, pinned agent configuration, MCP server and tool rules, permission actions, conversation entries, tool proposals, transcript and audio states. |
| **Adapters** | Interfaces with implementations for each external boundary (see below). |

### Adapters

| Adapter | Implementation | Backing service and behaviour |
|---|---|---|
| **Authentication** | JWT verification | Verifies the user's `apm-principal-token` (signature, issuer, audience) against the Keycloak JWKS and yields a principal. Can read expiry without enforcing it. |
| **Service authentication** | OIDC client credentials | Pipecat's own token for outbound OneCX calls, in the way a BFF does it. |
| **Agent configuration** | HTTP | Fetches the agent configuration from the AI provider service. Missing, invalid, unreachable or voice-disabled agents fail the session start. |
| **Chat** | HTTP | Loads a chat by id as the user and confirms the user is a member. |
| **Permission** | HTTP | Checks the user's existing OneCX voice permission. Any error counts as "no permission". |
| **MCP** | Streamable-HTTP MCP client | Discovers tools per server and invokes tools. Redirects are never followed, so user tokens cannot leak to another host. |
| **Tool policy** | Pure functions | Resolves each tool to a permission from its server's tool rules, else the server's default for unlisted tools. |
| **Speech (STT / TTS)** | In-memory fakes | Deterministic placeholders until real vendors are integrated. |
| **Persistence** | In-memory | Per-session conversation log with a per-session entry cap. |

The OneCX boundaries (authentication, agent configuration, chat, permission,
MCP) always use their real implementation. There is no in-memory fallback that
a deployment could silently run on. Only speech and persistence are in-memory.

## Session protocol

| Commands (client → server) | Events (server → client) |
|---|---|
| `start_session` (agent id, chat id, tokens) | `session_ready` |
| `audio` (base64 audio chunk) | `transcript`, `assistant_text`, `assistant_audio`, `turn_complete` |
| `refresh_token` | `degraded_capability` |
| `stop` | `error` (typed code), `session_closed` (reason) |

Error codes: `authentication_failed`, `chat_not_accessible`,
`voice_not_permitted`, `config_unavailable`, `token_expired`, `illegal_state`,
`principal_mismatch`, `bad_command`.

## Session lifecycle

### States

```
CREATED ──start ok──▶ READY ──stop / token expired──▶ CLOSED
   └────start fails (fail closed)─────────────────────▶ CLOSED
```

### Connection handling

1. The connection is rejected if it carries any query parameter. Tokens must
   never be in the URL.
2. The socket is accepted unauthenticated and a new session is created.
   Authentication is established by the first message.
3. A background watcher checks token expiry periodically, so an idle session
   still ends when its token expires.
4. Each text frame is parsed into a typed command. A malformed or unknown
   message produces a `bad_command` error and is otherwise ignored.
5. The session ends on `stop`, on token expiry, on a failed start, or on
   client disconnect. The watcher is always cancelled.

### Starting a session

Every step fails closed with a typed error, followed by `session_closed`.

1. **Authenticate** the token carried in the message.
2. **Load the chat** as the user and require that the user belongs to it.
3. **Check the voice permission.**
4. **Pin the agent configuration** for the whole session. Configuration changes
   apply to the next session.
5. **Discover MCP tools once** on the agent's own servers, forwarding the
   user's tokens.
6. **Filter the tools**: only tools resolved to `ALWAYS_ALLOW` are advertised.
   `ALWAYS_ASK` and `DENY` tools are withheld.
7. **Become ready**: emit `session_ready`, plus one `degraded_capability` per
   MCP server that failed. The session continues without that server's tools.

### While the session is ready

- **Expiry guard:** before each command (except refresh and stop), expired
  tokens end the session with `token_expired`.
- **Audio turn:** transcribe the audio. Empty or noise-only input stays
  ephemeral and emits nothing. Otherwise emit the final transcript, persist the
  human entry, produce the assistant reply, persist the assistant entry,
  synthesize speech, and emit `turn_complete`. If synthesis fails, the text
  answer is kept and the audio event is marked failed.
- **Token refresh:** the new token is verified and must belong to the same
  subject and tenant. A refresh can extend a session but never switch its user,
  because chat access and voice permission are only checked at start.
- **Tool invocation:** only tools in the session's allowed list can run, on
  servers from the pinned configuration, with the user's tokens forwarded.
- **Stop:** ends the session and returns the user to typed chat.

### Sequence

Diagram: [session-sequence.drawio](docs/diagrams/session-sequence.drawio)

## Security properties

- Tokens travel only in the first message, never in the URL.
- Every start step fails closed with a typed error.
- The agent configuration and the tool allow-list are fixed at session start.
- Pipecat's own service token is never sent to per-agent MCP servers. Only the
  user's tokens are.
- MCP calls never follow redirects.
- Token refresh cannot change the session's user.
- Tokens expire mid-session even when the client is idle.

## Quality and delivery

- **Tests:** async-first `pytest` suite covering the models, configuration,
  adapters, container, factory, session, application and WebSocket behaviour,
  using shared fakes for the external services.
- **Linting:** `ruff`, enforced by a pre-commit hook and CI.
- **CI:** tests, lint and documentation build on Python 3.11 and 3.12, without
  credentials.
- **Documentation:** an Antora module covering local setup, the configuration
  reference, adapter interfaces and the voice session.

## Known gaps and next steps

- Drive the voice turn with a real Pipecat pipeline (transport, VAD, STT, LLM,
  TTS).
- Add real STT/TTS vendors and durable persistence.
- Let an LLM invoke the allowed MCP tools. The session can invoke them, but
  nothing calls this yet.
- Support `ALWAYS_ASK` tool proposals and decisions. The models exist, but the
  flow does not.
- Add a WebRTC carrier, which the transport-neutral protocol is designed for.

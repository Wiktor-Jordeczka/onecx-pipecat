import pytest

from onecx_pipecat.adapters import (
    InMemoryAgentConfigAdapter,
    InMemoryAuthAdapter,
    InMemoryChatAdapter,
    InMemoryMcpAdapter,
    InMemoryPermissionAdapter,
    InMemoryPersistence,
    InMemorySttAdapter,
    InMemoryTtsAdapter,
)
from onecx_pipecat.adapters.agent_config import AgentConfigError
from onecx_pipecat.adapters.auth import AuthenticationError
from onecx_pipecat.adapters.chat import ChatAccessError
from onecx_pipecat.adapters.mcp import McpToolResult
from onecx_pipecat.config import McpSettings, PermissionSettings, PersistenceSettings
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    ExecutionPolicy,
    PermissionAction,
    PermissionDecisionStatus,
    Principal,
    ToolProposal,
    VoiceEntry,
    VoiceEntryKind,
)


async def test_auth_unknown_token_raises():
    auth = InMemoryAuthAdapter()
    with pytest.raises(AuthenticationError):
        await auth.authenticate("nope")


async def test_auth_seeded_token_returns_principal():
    auth = InMemoryAuthAdapter()
    auth.seed("t1", "user-1", "acme", ["operator"])
    p = await auth.authenticate("t1")
    assert p.subject == "user-1"
    assert p.tenant_id == "acme"
    assert p.roles == ["operator"]


async def test_agent_config_pins_highest_version():
    cfg = InMemoryAgentConfigAdapter()
    cfg.register("acme", "a", version=1, system_prompt="v1", tool_names=["w.get"])
    cfg.register("acme", "a", version=2, system_prompt="v2", tool_names=["w.get", "w.set"])
    snap = await cfg.pin("acme", "a", "tok")
    assert snap.version == 2
    assert snap.system_prompt == "v2"


async def test_agent_config_snapshot_can_carry_tools_and_policy_hints():
    cfg = InMemoryAgentConfigAdapter()
    cfg.register(
        "acme",
        "a",
        version=1,
        tools=[
            AgentToolSnapshot(
                tool_id="tool-1",
                tool_name="w.get",
                tool_description="Weather read",
                server_name="weather",
                server_url="https://weather.example/mcp",
                execution_policy=ExecutionPolicy.ALWAYS_ASK,
                allowed=PermissionAction.ALWAYS_ASK,
            )
        ],
    )

    snap = await cfg.pin("acme", "a", "tok")
    assert snap.tools[0].tool_id == "tool-1"
    assert snap.tools[0].tool_name == "w.get"
    assert snap.tools[0].server_name == "weather"
    assert snap.tools[0].allowed is PermissionAction.ALWAYS_ASK
    # tool_names remains available for older call paths.
    assert snap.tool_names == ["w.get"]


async def test_stt_tts_are_deterministic():
    stt = InMemorySttAdapter()
    tts = InMemoryTtsAdapter()
    text = await stt.transcribe(b"0" * 1024)
    assert text == "in-memory transcript"
    audio = await tts.synthesize(text)
    assert audio == text.encode("utf-8")


async def test_persistence_round_trip():
    store = InMemoryPersistence()
    entry = VoiceEntry(kind=VoiceEntryKind.HUMAN, text="hi", idempotency_key="k1")
    entry_id = await store.append("s1", entry)
    entries = await store.list_entries("s1")
    assert len(entries) == 1
    fetched = await store.get("s1", entry_id)
    assert fetched is not None and fetched.text == "hi"


async def test_permission_exact_rule_wins():
    perm = InMemoryPermissionAdapter()
    perm.set_rule("send_email", PermissionAction.ALWAYS_ASK)
    proposal = ToolProposal(
        proposal_id="p1",
        tool_name="send_email",
        arguments={"to": "a@b.c"},
        status=PermissionDecisionStatus.PENDING,
    )
    decision = await perm.evaluate(proposal)
    assert decision.action is PermissionAction.ALWAYS_ASK
    assert decision.reason == "agent tool rule"


async def test_permission_exact_rule_can_deny_or_allow():
    perm = InMemoryPermissionAdapter()
    perm.set_rule("drop_table", PermissionAction.DENY)
    perm.set_rule("list_items", PermissionAction.ALWAYS_ALLOW)
    assert (await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="drop_table"))).action is (
        PermissionAction.DENY
    )
    assert (await perm.evaluate(ToolProposal(proposal_id="p2", tool_name="list_items"))).action is (
        PermissionAction.ALWAYS_ALLOW
    )


async def test_permission_falls_back_to_server_default_ask():
    perm = InMemoryPermissionAdapter()
    perm.set_server_default(ExecutionPolicy.ALWAYS_ASK)
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.ALWAYS_ASK
    assert decision.reason == "server default policy"


async def test_permission_server_default_always_allow_maps_to_allow():
    """An ``ALWAYS_ALLOW`` server default advertises an unruled tool."""
    perm = InMemoryPermissionAdapter()
    perm.set_server_default(ExecutionPolicy.ALWAYS_ALLOW)
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.ALWAYS_ALLOW


async def test_permission_global_default_applies_without_rule_or_server_default():
    """With no rule and no server default, the configured global default applies."""
    perm = InMemoryPermissionAdapter()
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.ALWAYS_ASK
    assert decision.reason == "global default policy"


async def test_permission_global_default_deny_denies_unruled_tool():
    """`permission.default_action=deny` denies a tool with no rule/server default."""
    perm = InMemoryPermissionAdapter(PermissionSettings(default_action="deny"))
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.DENY


async def test_persistence_evicts_oldest_entry_when_cap_exceeded():
    store = InMemoryPersistence(PersistenceSettings(max_entries_per_session=3))
    for i in range(5):
        entry = VoiceEntry(
            kind=VoiceEntryKind.HUMAN,
            text=f"m{i}",
            idempotency_key=f"k{i}",
        )
        await store.append("s1", entry)
    entries = await store.list_entries("s1")
    assert len(entries) == 3
    # The oldest two entries (m0, m1) are evicted; the newest three remain.
    assert [e.text for e in entries] == ["m2", "m3", "m4"]


async def test_persistence_eviction_is_per_session():
    store = InMemoryPersistence(PersistenceSettings(max_entries_per_session=2))
    for i in range(3):
        await store.append("s1", VoiceEntry(kind=VoiceEntryKind.HUMAN, text=f"a{i}"))
    await store.append("s2", VoiceEntry(kind=VoiceEntryKind.HUMAN, text="s2-0"))
    assert [e.text for e in await store.list_entries("s1")] == ["a1", "a2"]
    assert [e.text for e in await store.list_entries("s2")] == ["s2-0"]


async def test_mcp_unknown_tool_is_sanitized_failure():
    mcp = InMemoryMcpAdapter()
    result = await mcp.invoke(ToolProposal(proposal_id="p1", tool_name="missing"))
    assert result.ok is False
    assert "unknown tool" in result.error
    assert isinstance(result, McpToolResult)


async def test_mcp_registered_tool_succeeds():
    mcp = InMemoryMcpAdapter()

    async def echo(args):
        return {"echo": args}

    mcp.register("echo", echo)
    result = await mcp.invoke(ToolProposal(proposal_id="p1", tool_name="echo"), {"x": 1})
    assert result.ok is True
    assert result.value == {"echo": {"x": 1}}


async def test_mcp_invoke_with_only_proposal_uses_arguments():
    """Regression test: omitting args parameter should use proposal.arguments.

    When a caller omits the args parameter (using the default None),
    the adapter should fall back to proposal.arguments instead of
    silently losing the tool's payload.
    """
    mcp = InMemoryMcpAdapter()

    async def echo(args):
        return {"echo": args}

    mcp.register("echo", echo)
    # Invoke with only proposal, no args parameter
    proposal = ToolProposal(
        proposal_id="p1",
        tool_name="echo",
        arguments={"x": 1, "y": "test"},
    )
    result = await mcp.invoke(proposal)  # args defaults to None
    assert result.ok is True
    assert result.value == {"echo": {"x": 1, "y": "test"}}


async def test_mcp_supports_multiple_servers():
    mcp = InMemoryMcpAdapter(
        McpSettings(
            default_server_name="alpha",
            servers={"alpha": "inmemory://alpha", "beta": "inmemory://beta"},
        )
    )

    async def alpha_echo(args):
        return {"server": "alpha", "echo": args}

    async def beta_echo(args):
        return {"server": "beta", "echo": args}

    mcp.register("echo", alpha_echo, server_name="alpha")
    mcp.register("echo", beta_echo, server_name="beta")

    default_result = await mcp.invoke(ToolProposal(proposal_id="p1", tool_name="echo"), {"x": 1})
    beta_result = await mcp.invoke(
        ToolProposal(proposal_id="p2", tool_name="echo", server_name="beta"),
        {"x": 2},
    )

    assert default_result.ok is True
    assert default_result.value == {"server": "alpha", "echo": {"x": 1}}
    assert beta_result.ok is True
    assert beta_result.value == {"server": "beta", "echo": {"x": 2}}


async def test_mcp_unknown_server_is_sanitized_failure():
    mcp = InMemoryMcpAdapter(
        McpSettings(default_server_name="alpha", servers={"alpha": "inmemory://alpha"})
    )
    result = await mcp.invoke(
        ToolProposal(proposal_id="p1", tool_name="echo", server_name="beta"),
        {"x": 1},
    )
    assert result.ok is False
    assert "unknown MCP server" in result.error


# --- authentication: expiry, refresh, service token ---------------------


async def test_auth_is_expired_flags_lapsed_token():
    auth = InMemoryAuthAdapter()
    auth.seed("t", "u", "t")
    assert auth.is_expired("t") is False
    auth.mark_expired("t")
    assert auth.is_expired("t") is True


async def test_auth_refresh_validates_new_token():
    auth = InMemoryAuthAdapter()
    auth.seed("new", "u", "t")
    p = await auth.refresh("new")
    assert p.subject == "u"
    with pytest.raises(AuthenticationError):
        await auth.refresh("stale")


async def test_auth_expired_token_refresh_fails():
    auth = InMemoryAuthAdapter()
    auth.seed("t", "u", "t", expired=True)
    with pytest.raises(AuthenticationError):
        await auth.refresh("t")


async def test_auth_service_token_defaults_to_pipecat_identity():
    auth = InMemoryAuthAdapter()
    assert await auth.service_token() == "pipecat-service-token"


# --- JWT/JWKS verification (real signature + issuer + expiry) -----------


def _rsa_jwks():
    """A throwaway RS256 keypair and its JWKS document (test-only, offline)."""
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    n = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
    e = pub.e.to_bytes(pub.e.bit_length(), "big")
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-key",
                "n": jwt.utils.base64url_encode(n).decode(),
                "e": jwt.utils.base64url_encode(e).decode(),
            }
        ]
    }
    return key, jwks


def _signed_token(key, *, issuer, audience, subject, exp):
    import jwt

    return jwt.encode(
        {"sub": subject, "tenant_id": "acme", "iss": issuer, "aud": audience, "exp": exp},
        key,
        algorithm="RS256",
    )


async def test_jwt_auth_verifies_signature_issuer_and_expiry():
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    key, jwks = _rsa_jwks()
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks(jwks)
    token = _signed_token(
        key,
        issuer=settings.issuer,
        audience=settings.audience,
        subject="user-1",
        exp=10_000_000_000,
    )
    p = await auth.authenticate(token)
    assert p.subject == "user-1"
    assert p.tenant_id == "acme"
    assert auth.is_expired(token) is False


async def test_jwt_auth_rejects_bad_signature():
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    key, jwks = _rsa_jwks()
    other, _ = _rsa_jwks()
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks(jwks)
    token = _signed_token(
        other,
        issuer=settings.issuer,
        audience=settings.audience,
        subject="user-1",
        exp=10_000_000_000,
    )
    with pytest.raises(AuthenticationError):
        await auth.authenticate(token)


async def test_jwt_auth_rejects_wrong_issuer_and_audience():
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    key, jwks = _rsa_jwks()
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks(jwks)
    bad_issuer = _signed_token(
        key,
        issuer="https://evil.example",
        audience="onecx-pipecat",
        subject="u",
        exp=10_000_000_000,
    )
    bad_aud = _signed_token(
        key,
        issuer="https://issuer.example",
        audience="someone-else",
        subject="u",
        exp=10_000_000_000,
    )
    with pytest.raises(AuthenticationError):
        await auth.authenticate(bad_issuer)
    with pytest.raises(AuthenticationError):
        await auth.authenticate(bad_aud)


async def test_jwt_auth_rejects_expired_token():
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    key, jwks = _rsa_jwks()
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks(jwks)
    token = _signed_token(
        key, issuer=settings.issuer, audience=settings.audience, subject="u", exp=1
    )
    with pytest.raises(AuthenticationError):
        await auth.authenticate(token)
    assert auth.is_expired(token) is True


def _rsa_jwk(kid: str):
    """A throwaway RS256 keypair and its JWK document entry (test-only)."""
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    n = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
    e = pub.e.to_bytes(pub.e.bit_length(), "big")
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": jwt.utils.base64url_encode(n).decode(),
        "e": jwt.utils.base64url_encode(e).decode(),
    }
    return key, jwk


def _signed_token_with_kid(key, *, kid, issuer, audience, subject, exp):
    import jwt

    return jwt.encode(
        {"sub": subject, "tenant_id": "acme", "iss": issuer, "aud": audience, "exp": exp},
        key,
        algorithm="RS256",
        headers={"kid": kid},
    )


async def test_jwt_auth_matches_key_by_kid_across_rotation():
    # A JWKS holding several rotated keys: a token signed by the second key
    # must verify, which only works if the key is chosen by the token's kid
    # rather than always taking the first key in the set.
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    first_key, first_jwk = _rsa_jwk("key-v1")
    second_key, second_jwk = _rsa_jwk("key-v2")
    jwks = {"keys": [first_jwk, second_jwk]}
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks(jwks)

    second_token = _signed_token_with_kid(
        second_key,
        kid="key-v2",
        issuer=settings.issuer,
        audience=settings.audience,
        subject="user-2",
        exp=10_000_000_000,
    )
    p = await auth.authenticate(second_token)
    assert p.subject == "user-2"
    assert auth.is_expired(second_token) is False

    first_token = _signed_token_with_kid(
        first_key,
        kid="key-v1",
        issuer=settings.issuer,
        audience=settings.audience,
        subject="user-1",
        exp=10_000_000_000,
    )
    assert (await auth.authenticate(first_token)).subject == "user-1"


async def test_jwt_auth_rejects_token_with_unknown_kid():
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    key, jwk = _rsa_jwk("key-v1")
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks({"keys": [jwk]})
    # A token whose kid is not in the JWKS must be rejected rather than tried
    # against the wrong (first) key.
    orphan = _signed_token_with_kid(
        key,
        kid="key-v9",
        issuer=settings.issuer,
        audience=settings.audience,
        subject="u",
        exp=10_000_000_000,
    )
    with pytest.raises(AuthenticationError):
        await auth.authenticate(orphan)
    assert auth.is_expired(orphan) is True


async def test_jwt_auth_falls_back_to_first_key_without_kid():
    from onecx_pipecat.adapters.auth import JwtAuthAdapter
    from onecx_pipecat.config import AuthSettings

    key, jwks = _rsa_jwks()
    settings = AuthSettings(issuer="https://issuer.example", audience="onecx-pipecat")
    auth = JwtAuthAdapter(settings)
    auth.set_jwks(jwks)
    # _signed_token carries no kid; the single-key set still verifies it.
    token = _signed_token(
        key,
        issuer=settings.issuer,
        audience=settings.audience,
        subject="user-1",
        exp=10_000_000_000,
    )
    assert (await auth.authenticate(token)).subject == "user-1"


# --- agent configuration: voice gate + unlisted permission --------------


async def test_agent_config_voice_disabled_fails():
    cfg = InMemoryAgentConfigAdapter()
    cfg.register("acme", "a", version=1, voice_enabled=False)
    with pytest.raises(AgentConfigError):
        await cfg.pin("acme", "a", "tok")


async def test_agent_config_snapshot_carries_voice_and_unlisted_permission():
    cfg = InMemoryAgentConfigAdapter()
    cfg.register(
        "acme",
        "a",
        version=1,
        unlisted_tool_permission=PermissionAction.ALWAYS_ALLOW,
        voice_enabled=True,
    )
    snap = await cfg.pin("acme", "a", "tok")
    assert snap.voice_enabled is True
    assert snap.unlisted_tool_permission is PermissionAction.ALWAYS_ALLOW


# --- chat adapter --------------------------------------------------------


async def test_chat_load_returns_registered_chat():
    chat = InMemoryChatAdapter()
    chat.register("c1", title="general")
    loaded = await chat.load("c1", "tok")
    assert loaded.chat_id == "c1"


async def test_chat_missing_chat_raises_access_error():
    chat = InMemoryChatAdapter()
    with pytest.raises(ChatAccessError):
        await chat.load("nope", "tok")


# --- mcp discovery: skip and report failures ----------------------------


async def test_mcp_discover_returns_registered_tools():
    mcp = InMemoryMcpAdapter()

    async def echo(args):
        return args

    mcp.register("echo", echo)
    discovery = await mcp.discover("tok")
    assert [t.tool_name for t in discovery.tools] == ["echo"]
    assert discovery.degraded == []


async def test_mcp_discover_skips_and_reports_failed_server():
    mcp = InMemoryMcpAdapter()
    mcp.mark_degraded("inmemory", "connection refused")
    discovery = await mcp.discover("tok")
    assert discovery.tools == []
    assert discovery.degraded == [("inmemory", "connection refused")]


# --- permission: voice eligibility + tool filtering ---------------------


async def test_voice_permission_default_allows_and_can_be_revoked():
    perm = InMemoryPermissionAdapter()
    principal = Principal(subject="user-1", tenant_id="local")
    assert await perm.has_voice_permission(principal, "tok") is True
    perm.set_voice_permission("user-1", False)
    assert await perm.has_voice_permission(principal, "tok") is False


async def test_allowed_tools_filters_to_always_allow_only():
    perm = InMemoryPermissionAdapter()
    snapshot = AgentConfigSnapshot(
        agent_id="a",
        version=1,
        unlisted_tool_permission=PermissionAction.ALWAYS_ASK,
    )
    discovered = [
        AgentToolSnapshot(tool_name="read"),
        AgentToolSnapshot(tool_name="write"),
    ]
    perm.set_rule("read", PermissionAction.ALWAYS_ALLOW)
    allowed = await perm.allowed_tools(snapshot, discovered)
    assert [t.tool_name for t in allowed] == ["read"]


async def test_allowed_tools_uses_unlisted_permission_when_no_rule():
    perm = InMemoryPermissionAdapter()
    snapshot = AgentConfigSnapshot(
        agent_id="a",
        version=1,
        unlisted_tool_permission=PermissionAction.ALWAYS_ALLOW,
    )
    discovered = [AgentToolSnapshot(tool_name="any")]
    allowed = await perm.allowed_tools(snapshot, discovered)
    assert [t.tool_name for t in allowed] == ["any"]

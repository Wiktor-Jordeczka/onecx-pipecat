import re

from onecx_pipecat.adapters.mcp import McpToolResult
from onecx_pipecat.models import AgentConfigSnapshot, AgentToolSnapshot, SkillSnapshot
from onecx_pipecat.pipeline.tools import (
    ACTIVATE_SKILL,
    build_tools_schema,
    mcp_function_schemas,
    register_mcp_tools,
    register_skills,
    skill_function_schema,
)

_SKILLS = [
    SkillSnapshot(name="Refund", description="d", instruction="Check the order."),
    SkillSnapshot(name="Escalate", instruction="Call a human."),
]


class _FakeLlm:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}

    def register_function(self, name, handler, **_kwargs) -> None:
        self.handlers[name] = handler


class _FakeParams:
    def __init__(self, arguments: dict) -> None:
        self.arguments = arguments
        self.results: list[dict] = []

    async def result_callback(self, result, **_kwargs) -> None:
        self.results.append(result)


def test_schema_enumerates_skill_names():
    schema = skill_function_schema(_SKILLS)
    assert schema.name == ACTIVATE_SKILL
    assert schema.required == ["name"]
    assert schema.properties["name"]["enum"] == ["Refund", "Escalate"]


async def test_activate_returns_instruction():
    llm = _FakeLlm()
    register_skills(llm, _SKILLS)
    params = _FakeParams({"name": "Refund"})
    await llm.handlers[ACTIVATE_SKILL](params)
    assert params.results == [{"name": "Refund", "instruction": "Check the order."}]


async def test_unknown_skill_returns_error():
    llm = _FakeLlm()
    register_skills(llm, _SKILLS)
    params = _FakeParams({"name": "Nope"})
    await llm.handlers[ACTIVATE_SKILL](params)
    assert "error" in params.results[0]
    assert "instruction" not in params.results[0]


async def test_registers_on_real_llm_service():
    from pipecat.services.openai.llm import OpenAILLMService

    llm = OpenAILLMService(api_key="k", settings=OpenAILLMService.Settings(model="m"))
    register_skills(llm, _SKILLS)
    assert llm.has_function(ACTIVATE_SKILL)


def _tool(server: str, name: str, schema: dict | None = None) -> AgentToolSnapshot:
    return AgentToolSnapshot(
        tool_name=name,
        server_name=server,
        server_url="https://x/mcp",
        tool_description="does things",
        input_schema=schema or {},
    )


class _Invoker:
    def __init__(self, result: McpToolResult) -> None:
        self.result = result
        self.calls: list[tuple] = []

    async def invoke_tool(self, server_name, tool_name, arguments=None) -> McpToolResult:
        self.calls.append((server_name, tool_name, arguments))
        return self.result


def test_mcp_function_names_are_llm_safe_unique_and_mapped_back():
    schemas, bindings = mcp_function_schemas(
        [_tool("my crm", "find.user"), _tool("my_crm", "find.user"), _tool("a", "activate_skill")]
    )
    names = [s.name for s in schemas]
    assert names[0] == "my_crm__find_user"
    assert len(set(names)) == 3
    assert all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", n) for n in names)
    assert bindings[names[0]] == ("my crm", "find.user")
    assert bindings[names[1]] == ("my_crm", "find.user")


def test_mcp_function_schema_uses_the_discovered_input_schema():
    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    (function,), _ = mcp_function_schemas([_tool("s", "t", schema)])
    assert function.properties == {"q": {"type": "string"}}
    assert function.required == ["q"]
    (permissive,), _ = mcp_function_schemas([_tool("s", "t")])
    assert permissive.properties == {} and permissive.required == []


async def test_mcp_handler_delegates_to_invoke_tool_and_returns_the_result():
    llm, invoker = _FakeLlm(), _Invoker(McpToolResult(ok=True, value="42"))
    register_mcp_tools(llm, invoker, [_tool("crm", "find")])
    params = _FakeParams({"q": "x"})
    await llm.handlers["crm__find"](params)
    assert invoker.calls == [("crm", "find", {"q": "x"})]
    assert params.results == [{"result": "42"}]


async def test_mcp_handler_reports_a_denied_or_failed_call_as_error():
    llm, invoker = _FakeLlm(), _Invoker(McpToolResult(ok=False, error="not permitted"))
    register_mcp_tools(llm, invoker, [_tool("crm", "find")])
    params = _FakeParams({})
    await llm.handlers["crm__find"](params)
    assert params.results == [{"error": "not permitted"}]


def test_tools_schema_contains_mcp_tools_and_skill_function_only_with_usable_skills():
    invoker = _Invoker(McpToolResult(ok=True))
    with_skills = AgentConfigSnapshot(agent_id="a", schema_version="1", skills=_SKILLS)
    llm = _FakeLlm()
    schema = build_tools_schema(llm, invoker, with_skills, [_tool("crm", "find")])
    assert [f.name for f in schema.standard_tools] == ["crm__find", ACTIVATE_SKILL]
    assert set(llm.handlers) == {"crm__find", ACTIVATE_SKILL}

    llm = _FakeLlm()
    bare = AgentConfigSnapshot(agent_id="a", schema_version="1")
    assert build_tools_schema(llm, invoker, bare, []).standard_tools == []
    assert llm.handlers == {}

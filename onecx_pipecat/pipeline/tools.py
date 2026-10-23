"""LLM function-calling tools for a voice session.

Skills and the session's ALWAYS_ALLOW MCP tools are exposed to the LLM as Pipecat
functions; ``build_tools_schema`` assembles the combined ``ToolsSchema``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema

from onecx_pipecat.adapters.mcp import McpToolResult
from onecx_pipecat.models import AgentConfigSnapshot, AgentToolSnapshot, SkillSnapshot
from onecx_pipecat.pipeline.prompt import usable_skills

if TYPE_CHECKING:
    from pipecat.services.llm_service import FunctionCallParams, LLMService

ACTIVATE_SKILL = "activate_skill"


def skill_function_schema(skills: list[SkillSnapshot]) -> FunctionSchema:
    """The ``activate_skill(name)`` schema, restricted to the given skill names."""
    return FunctionSchema(
        name=ACTIVATE_SKILL,
        description="Activate a skill and receive its instructions before applying them.",
        properties={
            "name": {
                "type": "string",
                "description": "Name of the skill to activate.",
                "enum": [skill.name for skill in skills],
            }
        },
        required=["name"],
    )


def register_skills(llm: LLMService, skills: list[SkillSnapshot]) -> None:
    """Register the ``activate_skill`` handler for ``skills`` on ``llm``."""
    by_name = {skill.name: skill for skill in skills}

    async def activate_skill(params: FunctionCallParams) -> None:
        name = str(params.arguments.get("name", "")).strip()
        skill = by_name.get(name)
        if skill is None:
            await params.result_callback({"error": f"unknown skill: {name}"})
            return
        await params.result_callback({"name": skill.name, "instruction": skill.instruction})

    llm.register_function(ACTIVATE_SKILL, activate_skill)


class ToolInvoker(Protocol):
    async def invoke_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> McpToolResult: ...


_UNSAFE = re.compile(r"[^a-zA-Z0-9_-]")
# Anthropic and OpenAI both cap function names at 64 characters.
_MAX_NAME = 64


def mcp_function_name(server_name: str, tool_name: str) -> str:
    """LLM-safe ``<server>__<tool>`` name."""
    return f"{_UNSAFE.sub('_', server_name)}__{_UNSAFE.sub('_', tool_name)}"[:_MAX_NAME]


def mcp_function_schemas(
    tools: list[AgentToolSnapshot],
) -> tuple[list[FunctionSchema], dict[str, tuple[str, str]]]:
    """Function schemas for MCP tools plus the unique name -> (server, tool) mapping."""
    schemas: list[FunctionSchema] = []
    bindings: dict[str, tuple[str, str]] = {}
    for tool in tools:
        name = base = mcp_function_name(tool.server_name, tool.tool_name)
        suffix = 2
        while name in bindings or name == ACTIVATE_SKILL:
            tail = f"_{suffix}"
            name = f"{base[: _MAX_NAME - len(tail)]}{tail}"
            suffix += 1
        bindings[name] = (tool.server_name, tool.tool_name)
        properties = tool.input_schema.get("properties")
        required = tool.input_schema.get("required")
        schemas.append(
            FunctionSchema(
                name=name,
                description=tool.tool_description or tool.tool_name,
                properties=properties if isinstance(properties, dict) else {},
                required=[r for r in required if isinstance(r, str)]
                if isinstance(required, list)
                else [],
            )
        )
    return schemas, bindings


def register_mcp_tools(
    llm: LLMService, invoker: ToolInvoker, tools: list[AgentToolSnapshot]
) -> list[FunctionSchema]:
    """Register a handler per ALWAYS_ALLOW MCP tool that delegates to ``invoker.invoke_tool``."""
    schemas, bindings = mcp_function_schemas(tools)

    def make_handler(server_name: str, tool_name: str):
        async def handler(params: FunctionCallParams) -> None:
            result = await invoker.invoke_tool(server_name, tool_name, dict(params.arguments))
            if result.ok:
                await params.result_callback({"result": result.value})
            else:
                await params.result_callback({"error": result.error})

        return handler

    for name, (server_name, tool_name) in bindings.items():
        llm.register_function(name, make_handler(server_name, tool_name))
    return schemas


def build_tools_schema(
    llm: LLMService,
    invoker: ToolInvoker,
    snapshot: AgentConfigSnapshot,
    allowed_tools: list[AgentToolSnapshot],
) -> ToolsSchema:
    """Register handlers and return the ``ToolsSchema`` of MCP tools plus ``activate_skill``."""
    schemas = register_mcp_tools(llm, invoker, allowed_tools)
    skills = usable_skills(snapshot)
    if skills:
        register_skills(llm, skills)
        schemas.append(skill_function_schema(skills))
    return ToolsSchema(standard_tools=schemas)

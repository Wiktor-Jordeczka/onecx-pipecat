"""System prompt composition, mirroring the OneCX Java runtime.

See ``ScaffoldPromptComposer`` and ``RuntimeSkillService`` in
onecx-ai-provider-runtime: skills without a name or instruction are dropped,
the rest are sorted by name (case-insensitive) and advertised after the
scaffold system prompt.
"""

from __future__ import annotations

from onecx_pipecat.models import AgentConfigSnapshot, SkillSnapshot


def usable_skills(snapshot: AgentConfigSnapshot) -> list[SkillSnapshot]:
    """Skills with a name and instruction, trimmed and sorted by name (case-insensitive)."""
    skills = [
        skill.model_copy(
            update={
                "name": skill.name.strip(),
                "description": skill.description.strip(),
                "instruction": skill.instruction.strip(),
            }
        )
        for skill in snapshot.skills
    ]
    return sorted(
        (s for s in skills if s.name and s.instruction),
        key=lambda s: s.name.lower(),
    )


def compose_system_prompt(snapshot: AgentConfigSnapshot) -> str:
    """Scaffold system prompt plus the available-skills block, joined by a blank line."""
    blocks: list[str] = []
    if snapshot.system_prompt.strip():
        blocks.append(snapshot.system_prompt.strip())
    skills = usable_skills(snapshot)
    if skills:
        lines = [f"- {s.name}: {s.description or s.name}" for s in skills]
        blocks.append(
            "Available skills:\n"
            + "\n".join(lines)
            + "\nActivate a relevant skill before applying its instructions."
        )
    return "\n\n".join(blocks)

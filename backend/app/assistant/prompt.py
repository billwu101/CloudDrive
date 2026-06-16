from __future__ import annotations

from app.assistant.skills.registry import SkillRegistry


def build_system_prompt(registry: SkillRegistry) -> str:
    skills = "\n".join(f"- {skill.name}: {skill.description}" for skill in registry.list_skills())
    return (
        "You are CloudDrive's in-app assistant. Help the user operate their own drive "
        "through approved tools only. Never claim a write operation is complete unless a "
        "tool result says so. For this first backend slice, only read-only tools are "
        "available.\n\n"
        "Available tools:\n"
        f"{skills}"
    )

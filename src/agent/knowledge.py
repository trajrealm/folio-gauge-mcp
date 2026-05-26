"""
src/agent/knowledge.py
----------------------
Utility module to load skills and prompts from markdown files.
Skills are domain knowledge files that guide agent reasoning.
Prompts are system prompts for LLM-based agents.
"""

from __future__ import annotations

import os
from functools import lru_cache

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "skills")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


@lru_cache(maxsize=32)
def load_skill(agent_name: str) -> str:
    """
    Load skill markdown file for an agent.
    """
    skill_path = os.path.join(SKILLS_DIR, f"{agent_name}.md")

    if not os.path.exists(skill_path):
        raise FileNotFoundError(f"Skill file not found: {skill_path}")

    with open(skill_path, "r") as f:
        return f.read()


@lru_cache(maxsize=32)
def load_prompt(agent_name: str) -> str:
    """
    Load prompt markdown file for an agent.
    """
    prompt_path = os.path.join(PROMPTS_DIR, f"{agent_name}.md")

    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, "r") as f:
        return f.read()


def get_skill_and_prompt(agent_name: str) -> tuple[str, str]:
    """
    Load both skill and prompt for an agent.
    """
    skill = load_skill(agent_name)
    prompt = load_prompt(agent_name)
    return skill, prompt


def get_system_message(agent_name: str, include_skill: bool = True) -> str:
    """
    Build system message for LLM by combining prompt and skill.
    For LLM-based agents, this becomes the 'system' role message.
    """
    prompt = load_prompt(agent_name)

    if include_skill:
        skill = load_skill(agent_name)
        return f"""{prompt}

            ## Domain Knowledge

            {skill}
            """

    return prompt


def get_available_agents() -> list[str]:
    """Get list of all agents with skills and prompts."""
    agents = []

    for filename in os.listdir(SKILLS_DIR):
        if filename.endswith(".md"):
            agent_name = filename.replace(".md", "")
            agents.append(agent_name)

    return sorted(agents)

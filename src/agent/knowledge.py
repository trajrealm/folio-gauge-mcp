"""
src/agent/knowledge.py
----------------------
Loads an agent's system prompt from prompts/<agent>.md.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parents[2] / "prompts"


@lru_cache(maxsize=32)
def load_prompt(agent_name: str) -> str:
    return (PROMPTS_DIR / f"{agent_name}.md").read_text()

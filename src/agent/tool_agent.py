"""
src/agent/tool_agent.py
-----------------------
Runs an analyst as a tool-calling agent (langchain create_agent) with a
structured response. Tools return (content, artifact): the LLM reads the
content, the analyst code reads the artifact (labels and signals computed
in code), so confidence and data gaps never depend on the LLM.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src import config
from src.agent.knowledge import load_prompt


def run_tool_agent[T: BaseModel](
    agent_name: str, tools: list[BaseTool], schema: type[T], task: str
) -> tuple[T, dict[str, Any]]:
    """Run the agent; return its structured response and {tool name: artifact of its last call}.
    Raises if the agent did not call every tool."""
    agent = create_agent(
        ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS),
        tools=tools,
        system_prompt=load_prompt(agent_name),
        response_format=schema,
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config={"run_name": f"{agent_name.capitalize()} Agent"},
    )
    artifacts = {m.name: m.artifact for m in result["messages"] if isinstance(m, ToolMessage)}
    missing = {t.name for t in tools} - artifacts.keys()
    if missing:
        raise RuntimeError(f"{agent_name} agent did not call: {', '.join(sorted(missing))}")
    return result["structured_response"], artifacts

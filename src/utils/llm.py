"""
src/utils/llm.py
----------------
Chat model on the configured OpenAI-compatible provider (config.LLM_BASE_URL).
"""

from langchain_openai import ChatOpenAI

from src import config


def get_llm(model: str, temperature: float) -> ChatOpenAI:
    # OpenRouter routes a model to one of several hosts; require one that supports
    # every parameter sent, so structured output is never silently dropped.
    openrouter = "openrouter.ai" in (config.LLM_BASE_URL or "")
    extra_body = {"provider": {"require_parameters": True}} if openrouter else None
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        extra_body=extra_body,
    )

"""
src/utils/batch.py
------------------
Batch chat completions with structured output, at about half the normal price
and up to 24 hours per batch. The provider follows config.LLM_BASE_URL:
  - OpenRouter: requests sent inline to /batches, results returned inline
    (any model with a :batch variant, e.g. Anthropic, Google, Mistral, OpenAI)
  - otherwise OpenAI: requests uploaded as a JSONL file, results downloaded
Both use chat-completions bodies and return {custom_id, response, error} per request.

The batch id is saved to a state file, so an interrupted wait resumes the
same batch; the file is removed once the results are collected.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
from openai import OpenAI
from pydantic import BaseModel

from src import config
from src.utils.llm import is_openrouter
from src.utils.logger import get_logger

logger = get_logger(__name__)

ENDPOINT = "/v1/chat/completions"
TERMINAL = {"completed", "failed", "expired", "cancelled"}


def response_format(schema: type[BaseModel]) -> dict:
    """Strict JSON-schema response format for a flat pydantic model."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": schema.model_json_schema() | {"additionalProperties": False},
            "strict": True,
        },
    }


def parse_results(items: list[dict], schema: type[BaseModel]) -> dict[str, BaseModel | str]:
    """Parsed output per custom_id, or the error message for a failed request."""
    parsed: dict[str, BaseModel | str] = {}
    for item in items:
        response = item.get("response") or {}
        if item.get("error") or response.get("status_code") != 200:
            parsed[item["custom_id"]] = json.dumps(item.get("error") or response.get("body"))
            continue
        content = response["body"]["choices"][0]["message"]["content"]
        try:
            parsed[item["custom_id"]] = schema.model_validate_json(content)
        except ValueError as e:
            parsed[item["custom_id"]] = f"invalid output: {e}"
    return parsed


# --- OpenAI: file upload ------------------------------------------------------


def _openai() -> OpenAI:
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


def _openai_submit(model: str, bodies: dict[str, dict]) -> str:
    lines = [{"custom_id": cid, "method": "POST", "url": ENDPOINT, "body": body} for cid, body in bodies.items()]
    content = "\n".join(json.dumps(line) for line in lines).encode()
    upload = _openai().files.create(file=("batch.jsonl", content), purpose="batch")
    return _openai().batches.create(input_file_id=upload.id, endpoint=ENDPOINT, completion_window="24h").id


def _openai_poll(batch_id: str) -> tuple[str, dict, list[dict] | None]:
    batch = _openai().batches.retrieve(batch_id)
    counts = batch.request_counts.model_dump() if batch.request_counts else {}
    if batch.status not in TERMINAL:
        return batch.status, counts, None
    items = []
    for file_id in (batch.output_file_id, batch.error_file_id):
        if file_id:
            items += [json.loads(line) for line in _openai().files.content(file_id).text.splitlines() if line]
    return batch.status, counts, items


# --- OpenRouter: inline -------------------------------------------------------


def _openrouter(method: str, path: str, **kwargs) -> dict:
    response = httpx.request(
        method,
        f"{config.LLM_BASE_URL.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        timeout=300,
        **kwargs,
    )
    if response.is_error:
        raise RuntimeError(f"OpenRouter {method} {path}: HTTP {response.status_code} {response.text}")
    return response.json()


def _openrouter_submit(model: str, bodies: dict[str, dict]) -> str:
    # endpoint and model must come before the (large) requests array.
    payload = {
        "endpoint": ENDPOINT,
        "model": model,
        "requests": [{"custom_id": cid, "body": body} for cid, body in bodies.items()],
    }
    return _openrouter("POST", "/batches", json=payload)["id"]


def _openrouter_poll(batch_id: str) -> tuple[str, dict, list[dict] | None]:
    batch = _openrouter("GET", f"/batches/{batch_id}")
    return batch["status"], batch.get("request_counts") or {}, batch.get("results")


# --- Run ----------------------------------------------------------------------


def run_batch(
    model: str,
    messages: dict[str, list[dict]],
    schema: type[BaseModel],
    temperature: float,
    state: Path,
) -> dict[str, BaseModel | str]:
    """
    Submit one chat completion per custom_id (or resume the batch saved in
    state), wait for it, and return the parsed output or an error message per
    custom_id. Requests missing from the results are reported as errors.
    """
    submit, poll = (_openrouter_submit, _openrouter_poll) if is_openrouter() else (_openai_submit, _openai_poll)

    if state.exists():
        batch_id = json.loads(state.read_text())["id"]
        logger.info(f"Resuming batch {batch_id}")
    else:
        bodies = {
            cid: {"model": model, "messages": msgs, "temperature": temperature, "response_format": response_format(schema)}
            for cid, msgs in messages.items()
        }
        batch_id = submit(model, bodies)
        state.write_text(json.dumps({"id": batch_id, "model": model}))
        logger.info(f"Submitted batch {batch_id}: {len(bodies)} requests to {model}")

    while True:
        status, counts, items = poll(batch_id)
        logger.info(f"Batch {batch_id}: {status} {counts}")
        if items is not None:
            break
        time.sleep(config.BATCH_POLL_SECONDS)

    parsed = parse_results(items, schema)
    state.unlink()
    return {cid: parsed.get(cid, f"missing from batch results (batch {status})") for cid in messages}

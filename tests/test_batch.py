"""
test_batch.py
-------------
Unit tests (no network) for src/utils/batch.py: the response format sent and
the parsing of OpenAI / OpenRouter batch results (same shape for both).
Run from project root:
    uv run pytest tests/test_batch.py
"""

import json

from src.analysts.earnings import EarningsAnalysis
from src.utils.batch import parse_results, response_format

ANALYSIS = {"score": 4, "guidance_signal": "raised", "reasoning": "r", "key_signals": [], "risk_flags": []}


def _ok(custom_id: str, content: str) -> dict:
    body = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    return {"custom_id": custom_id, "response": {"status_code": 200, "body": body}, "error": None}


def test_response_format_is_strict_schema():
    fmt = response_format(EarningsAnalysis)
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False
    assert set(fmt["json_schema"]["schema"]["required"]) == set(EarningsAnalysis.model_fields)


def test_parse_results():
    items = [
        _ok("AAPL|2025-05-02", json.dumps(ANALYSIS)),
        _ok("MSFT|2025-04-30", '{"score": 9}'),
        {"custom_id": "JPM|2025-05-01", "response": None, "error": {"code": "rate_limit", "message": "slow down"}},
        {"custom_id": "NVDA|2025-05-28", "response": {"status_code": 400, "body": {"error": "bad"}}, "error": None},
    ]
    parsed = parse_results(items, EarningsAnalysis)
    assert parsed["AAPL|2025-05-02"] == EarningsAnalysis(**ANALYSIS)
    assert parsed["MSFT|2025-04-30"].startswith("invalid output")
    assert "slow down" in parsed["JPM|2025-05-01"]
    assert "bad" in parsed["NVDA|2025-05-28"]

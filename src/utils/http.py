"""
utils/http.py
-------------
Shared retry policy for HTTP tools: retry only transient failures
(429, 5xx, network errors), up to 3 attempts with exponential backoff.
"""

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


retry_transient = retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


@retry_transient
def get_json(url: str, **kwargs) -> dict | list:
    """GET a URL and return JSON; raises on HTTP errors after transient retries."""
    response = httpx.get(url, timeout=15, **kwargs)
    response.raise_for_status()
    return response.json()

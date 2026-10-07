"""
utils/http.py
-------------
Shared HTTP client and retry policy for tools.
- One client with a named User-Agent: some sites reject httpx's default
  ("python-httpx/x"), e.g. Yahoo Finance RSS answers 404.
- Retry only transient failures (429, 5xx, network errors), up to 3 attempts
  with exponential backoff.
"""

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

_client = httpx.Client(
    headers={"User-Agent": "folio-gauge/1.0"}, timeout=15, follow_redirects=True
)


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
    response = _client.get(url, **kwargs)
    response.raise_for_status()
    return response.json()


@retry_transient
def get_text(url: str, **kwargs) -> str:
    """GET a URL and return the body as text; raises on HTTP errors after transient retries."""
    response = _client.get(url, **kwargs)
    response.raise_for_status()
    return response.text
